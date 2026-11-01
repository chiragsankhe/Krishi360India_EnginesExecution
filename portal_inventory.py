"""Read-only inventory of the Krishi ArcGIS web map / web scene layers (Step 2 intake, Steps 9 and 14 evidence).

Mirrors the portal client logic: reads the item's /data, walks operationalLayers (groups included), classifies
each layer by state exactly like portalStateOf() (ccmc|maharashtra|india -> maharashtra, otherwise telangana),
then reads each service's REST metadata: fields, geometry type, CRS, extent, feature counts, candidate plot
identifier fields and, for image services, pixel type, bands, cell size and raster attribute table.

Python standard library only. Nothing is written to the portal. Credentials are read from the environment and
are never written to the outputs:
  ARCGIS_TOKEN         one token used for every server, or
  ARCGIS_TOKENS_JSON   path to (or literal) JSON list [{"server": "...", "token": "..."}] as /api/portal-tokens returns, or
  ARCGIS_USERNAME + ARCGIS_PASSWORD   a short-lived token is generated at PORTAL/sharing/rest/generateToken.

A portal token is sent only to the portal host (its federated servers); other hosts are called anonymously.

Usage:
  python portal_inventory.py --portal https://bmc3dmumbai.com/portal --webmap bf308acdb69c432fab3e44c292fd077f \
      [--webscene WEBSCENE_ID] [--export LAYER_URL ...] --out runs/RUN_ID/metadata/portal
--export downloads every feature of a layer (native CRS Esri JSON, view-only EPSG:4326 GeoJSON, attribute CSV,
manifest with counts and SHA256) into OUT/exports/. Layers above --max-features (default 5000) are refused.
"""
import argparse, csv, json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl
from urllib.request import Request, urlopen

# Same rules as usePortalLayers.js
NOT_LISTED = re.compile(r'india (state|district)|maharashtra village', re.I)
STATE_RULE = re.compile(r'ccmc|maharashtra|india ', re.I)
CCMC_RULE = re.compile(r'ccmc|chandrapur', re.I)
NDVI_RULE = re.compile(r'ndvi', re.I)
ID_NAME_RULE = re.compile(r'uuid|^uid$|guid|globalid|survey|sur_?no|gat|plot|parcel|khasra|farmer', re.I)
MONTH_RULE = re.compile(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[_\s-]*(\d{4})', re.I)


def redact(url):
    """Drop any token query parameter before a URL is stored."""
    if not url:
        return url
    p = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() != 'token']
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), p.fragment))


class Client:
    def __init__(self, portal, timeout=60):
        self.portal = portal.rstrip('/')
        self.timeout = timeout
        self.tokens = []  # (server prefix, token)
        raw = os.environ.get('ARCGIS_TOKENS_JSON')
        if raw:
            data = json.loads(Path(raw).read_text() if Path(raw).is_file() else raw)
            data = data if isinstance(data, list) else data.get('tokens') or data.get('results') or []
            self.tokens = [(t['server'].rstrip('/'), t['token']) for t in data if t.get('token') and t.get('server')]
        self.default = os.environ.get('ARCGIS_TOKEN')
        self.auth = 'tokens_json' if self.tokens else 'token' if self.default else None
        if not self.tokens and not self.default and os.environ.get('ARCGIS_USERNAME'):
            self.default = self.generate_token()
            self.auth = 'generated'

    def generate_token(self):
        body = urlencode({'username': os.environ['ARCGIS_USERNAME'], 'password': os.environ.get('ARCGIS_PASSWORD', ''),
                          'client': 'referer', 'referer': self.portal, 'expiration': 120, 'f': 'json'}).encode()
        data = self._open(Request(self.portal + '/sharing/rest/generateToken', data=body, method='POST'))
        if 'token' not in data:
            raise RuntimeError('generateToken failed: ' + json.dumps(data.get('error', data))[:300])
        return data['token']

    def token_for(self, url):
        best = None
        for server, token in self.tokens:
            if url.startswith(server) and (best is None or len(server) > len(best[0])):
                best = (server, token)
        if best:
            return best[1]
        # A portal token is only valid on the portal host and its federated servers. Other hosts (TGRAC, Esri
        # Living Atlas) reject it with 498 even when the service itself is public, so they are called anonymously.
        return self.default if urlsplit(url).netloc.lower() == urlsplit(self.portal).netloc.lower() else None

    def _open(self, req):
        req.add_header('Referer', self.portal)
        req.add_header('User-Agent', 'krishi360-portal-inventory/1.0')
        with urlopen(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode('utf-8'))

    def get(self, url, **params):
        params.setdefault('f', 'json')
        token = self.token_for(url)
        sep = '&' if '?' in url else '?'
        data = self._open(Request(url + sep + urlencode(dict(params, token=token) if token else params)))
        if token and isinstance(data, dict) and (data.get('error') or {}).get('code') in (498, 499):
            data = self._open(Request(url + sep + urlencode(params)))  # token not accepted here; try as public
        if isinstance(data, dict) and 'error' in data:
            e = data['error']
            raise RuntimeError(f"ArcGIS error {e.get('code')}: {e.get('message')} {e.get('details') or ''}".strip())
        return data


def safe(fn, *a, **k):
    try:
        return fn(*a, **k), None
    except (HTTPError, URLError, RuntimeError, ValueError, TimeoutError, OSError) as e:
        return None, f'{type(e).__name__}: {e}'


def walk(layers, group=None, group_state=None, path=()):
    """Yield every operational layer with its group path; children inherit the group's state (as in scope())."""
    for l in layers or []:
        title = l.get('title') or l.get('id') or ''
        state = group_state or ('maharashtra' if STATE_RULE.search(title) else 'telangana')
        here = path + (title,)
        yield {'title': title, 'group': group, 'path': ' / '.join(here), 'state': state, 'raw': l}
        if l.get('layers'):
            yield from walk(l['layers'], title, state, here)


def describe_layer(c, url, meta):
    """Summarise one feature/map sublayer or image service from its REST JSON."""
    out = {'url': redact(url), 'service_type': meta.get('type') or ('ImageServer' if 'pixelType' in meta else None),
           'name': meta.get('name'), 'geometry_type': meta.get('geometryType'),
           'spatial_reference': (meta.get('extent') or {}).get('spatialReference') or meta.get('spatialReference'),
           'extent': meta.get('extent'), 'capabilities': meta.get('capabilities'),
           'max_record_count': meta.get('maxRecordCount'), 'description': (meta.get('description') or '')[:500]}
    fields = meta.get('fields') or []
    out['fields'] = [{'name': f.get('name'), 'type': f.get('type'), 'alias': f.get('alias'), 'length': f.get('length'),
                      'domain': bool(f.get('domain'))} for f in fields]
    out['candidate_id_fields'] = [f['name'] for f in fields
                                  if f.get('type') in ('esriFieldTypeGUID', 'esriFieldTypeGlobalID') or ID_NAME_RULE.search(f.get('name') or '')]
    if 'pixelType' in meta:  # image service
        out.update(pixel_type=meta.get('pixelType'), band_count=meta.get('bandCount'),
                   pixel_size_x=meta.get('pixelSizeX'), pixel_size_y=meta.get('pixelSizeY'),
                   band_names=meta.get('bandNames'), min_values=meta.get('minValues'), max_values=meta.get('maxValues'),
                   has_raster_attribute_table=meta.get('hasRasterAttributeTable'),
                   allow_raster_function=meta.get('allowRasterFunction'), has_multidimensions=meta.get('hasMultidimensions'))
        kp, err = safe(c.get, url + '/keyProperties')
        out['key_properties'] = kp if kp is not None else {'error': err}
        if meta.get('hasRasterAttributeTable'):
            rat, err = safe(c.get, url + '/rasterAttributeTable')
            out['raster_attribute_table'] = ([f.get('attributes') for f in rat.get('features', [])] if rat else {'error': err})
        out['interpretation'] = interpret_image(out)
    elif meta.get('type') == 'Raster Layer':  # raster inside a MapServer: no pixel type in its JSON
        root, lid = url.rsplit('/', 1)
        leg, err = safe(c.get, root + '/legend')
        labels = next((x.get('legend') for x in (leg or {}).get('layers', []) if str(x.get('layerId')) == lid), None)
        out['legend_labels'] = [x.get('label') for x in labels] if labels is not None else {'error': err}
        out['pixel_probes'] = probe_pixels(c, root, lid, meta.get('extent'))
        out['interpretation'] = interpret_map_raster(out['legend_labels'], out['pixel_probes'])
    elif meta.get('geometryType') or meta.get('type') in ('Feature Layer', 'Table'):
        cnt, err = safe(c.get, url + '/query', where='1=1', returnCountOnly='true')
        out['feature_count'] = cnt.get('count') if cnt else None
        out['count_error'] = err
        # One sample record (attributes only) so field meaning can be reviewed; no geometry is downloaded.
        smp, err = safe(c.get, url + '/query', where='1=1', outFields='*', returnGeometry='false', resultRecordCount=1)
        out['sample_attributes'] = (smp.get('features') or [{}])[0].get('attributes') if smp else {'error': err}
    return out


def interpret_image(info):
    """Flags whether a raster can serve as Engine 1 input (continuous reflectance / NDVI) or only as a class map."""
    pt = (info.get('pixel_type') or '').upper()
    n = info.get('band_count')
    if info.get('has_raster_attribute_table') or (pt in ('U8', 'S8', 'U4', 'U2', 'U1') and n == 1):
        return 'Probably classified (integer classes). Not a continuous NDVI; cannot be pixel-compared with Engine 1 NDVI.'
    if pt.startswith('F') and n == 1:
        return 'Single-band floating point. Possibly continuous NDVI; confirm with value range and provider metadata.'
    if n and n > 1:
        return 'Multi-band. Check band names for B04/B08 reflectance before using as Engine 1 input.'
    return 'Undetermined; review metadata.'


def probe_pixels(c, root, lid, extent):
    """Identify five points (centre and quarter points of the layer extent) and return the reported pixel values."""
    if not extent or extent.get('xmin') is None:
        return {'error': 'No extent'}
    x0, y0, x1, y1 = extent['xmin'], extent['ymin'], extent['xmax'], extent['ymax']
    sr = extent.get('spatialReference') or {}
    wkid = sr.get('latestWkid') or sr.get('wkid')
    probes = []
    for fx, fy in ((.5, .5), (.25, .25), (.75, .25), (.25, .75), (.75, .75)):
        x, y = x0 + (x1 - x0) * fx, y0 + (y1 - y0) * fy
        r, err = safe(c.get, root + '/identify', geometry=f'{x},{y}', geometryType='esriGeometryPoint', sr=wkid,
                      layers=f'all:{lid}', tolerance=0, mapExtent=f'{x0},{y0},{x1},{y1}', imageDisplay='600,600,96',
                      returnGeometry='false')
        attrs = ((r or {}).get('results') or [{}])[0].get('attributes') if r else None
        probes.append({'x': x, 'y': y, 'wkid': wkid, 'attributes': attrs, 'error': err})
    return probes


def interpret_map_raster(labels, probes):
    """Classified or continuous, judged from the stored pixel values first and the legend second."""
    values = []
    for p in probes if isinstance(probes, list) else []:
        v = (p.get('attributes') or {}).get('Pixel Value')
        try:
            values.append(float(v))
        except (TypeError, ValueError):
            pass
    if values and any(not v.is_integer() for v in values):
        return f'Continuous pixel values ({len(values)} probes, e.g. {values[0]}). Possibly NDVI; confirm range/provider.'
    text = ' '.join(str(x) for x in labels) if isinstance(labels, list) else ''
    if values and all(v.is_integer() for v in values) and not re.search(r'high|low', text, re.I):
        return f'Integer pixel values {sorted(set(values))} with legend {labels}: probably classified, not continuous NDVI.'
    if re.search(r'high|low', text, re.I):
        return 'Stretched legend (continuous display); no non-integer probe value confirms stored continuous NDVI.'
    return 'Undetermined (no readable probe values); review legend and source.'


def inspect_url(c, url):
    """Return a list of layer descriptions for a layer URL or a whole service root."""
    url = redact(url).rstrip('/')
    meta, err = safe(c.get, url)
    if meta is None:
        return [{'url': url, 'error': err}]
    if 'layers' in meta and not meta.get('geometryType') and 'pixelType' not in meta:  # service root
        rows = []
        for sub in (meta.get('layers') or []) + (meta.get('tables') or []):
            if sub.get('subLayerIds'):  # group sublayer: children are listed separately
                continue
            m, e = safe(c.get, f"{url}/{sub['id']}")
            rows.append(describe_layer(c, f"{url}/{sub['id']}", m) if m else {'url': f"{url}/{sub['id']}", 'error': e})
        return rows or [{'url': url, 'note': 'Service root without sublayers', 'service_meta_keys': sorted(meta)}]
    return [describe_layer(c, url, meta)]


def inventory_item(c, item_id, out):
    base = f'{c.portal}/sharing/rest/content/items/{item_id}'
    item = c.get(base)
    data = c.get(base + '/data')
    (out / f'item_{item_id}.json').write_text(json.dumps({k: item.get(k) for k in (
        'id', 'title', 'type', 'owner', 'created', 'modified', 'access', 'snippet', 'description', 'tags', 'url', 'spatialReference', 'extent')},
        indent=2, default=str))
    # Store the definition with any token parameters removed.
    text = re.sub(r'([?&])token=[^"&]*', r'\1token=REDACTED', json.dumps(data, indent=2))
    (out / f'item_{item_id}_data.json').write_text(text)
    rows = []
    for node in walk(data.get('operationalLayers')):
        raw = node.pop('raw')
        node.update(item_id=item_id, item_type=item.get('type'), layer_type=raw.get('layerType'),
                    portal_item_id=(raw.get('itemId') or (raw.get('portalItem') or {}).get('id')),
                    url=redact(raw.get('url')), visibility=raw.get('visibility'),
                    is_group=bool(raw.get('layers')), not_listed_rule=bool(NOT_LISTED.search(node['title'])),
                    ccmc_specific=bool(CCMC_RULE.search(node['path'])), ndvi=bool(NDVI_RULE.search(node['title'])),
                    month=(lambda m: f'{m.group(1).title()} {m.group(2)}' if m else None)(MONTH_RULE.search(node['title'])),
                    definition_expression=(raw.get('layerDefinition') or {}).get('definitionExpression'))
        url = raw.get('url')
        if not url and node['portal_item_id']:
            it, err = safe(c.get, f"{c.portal}/sharing/rest/content/items/{node['portal_item_id']}")
            url = it.get('url') if it else None
            node['resolved_from_item'] = True if it else err
        node['services'] = inspect_url(c, url) if url and not node['is_group'] else []
        rows.append(node)
    return {'item': {k: item.get(k) for k in ('id', 'title', 'type', 'owner', 'modified')}, 'layers': rows}


def sha256(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export_layer(c, url, out, max_features=5000, batch=200):
    """Download every feature of one layer: native-CRS Esri JSON (for area work), server-reprojected EPSG:4326
    GeoJSON (viewing only) and an attribute CSV, plus a manifest with counts and hashes. Read-only."""
    url = redact(url).rstrip('/')
    meta = c.get(url)
    ids = c.get(url + '/query', where='1=1', returnIdsOnly='true')
    oids = sorted(ids.get('objectIds') or [])
    if len(oids) > max_features:
        raise ValueError(f'{len(oids)} features exceeds --max-features {max_features}; export a filtered subset instead')
    feats, gj, sr, gj_err = [], [], None, None
    for i in range(0, len(oids), batch):
        part = ','.join(map(str, oids[i:i + batch]))
        r = c.get(url + '/query', objectIds=part, outFields='*', returnGeometry='true')
        feats += r.get('features') or []
        sr = sr or r.get('spatialReference')
        if gj_err is None:
            g, gj_err = safe(c.get, url + '/query', objectIds=part, outFields='*', returnGeometry='true', outSR=4326, f='geojson')
            gj += (g or {}).get('features') or []
    name = re.sub(r'\W+', '_', meta.get('name') or 'layer').strip('_')
    dest = out / 'exports'
    dest.mkdir(parents=True, exist_ok=True)
    fields = [f['name'] for f in meta.get('fields') or []]
    files = {}
    p = dest / f'{name}.esri.json'
    p.write_text(json.dumps({'source_url': url, 'name': meta.get('name'), 'geometryType': meta.get('geometryType'),
                             'spatialReference': sr, 'fields': meta.get('fields'), 'objectIdField': ids.get('objectIdFieldName'),
                             'features': feats}, indent=1, default=str))
    files['esri_json_native_crs'] = p
    p = dest / f'{name}_attributes.csv'
    with p.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(fields)
        for ft in feats:
            a = ft.get('attributes') or {}
            w.writerow([a.get(k) for k in fields])
    files['attributes_csv'] = p
    if gj_err is None:
        p = dest / f'{name}_EPSG4326_view_only.geojson'
        p.write_text(json.dumps({'type': 'FeatureCollection', 'features': gj}))
        files['geojson_epsg4326_view_only'] = p
    got = sorted((ft.get('attributes') or {}).get(ids.get('objectIdFieldName')) for ft in feats)
    manifest = {'run_utc': datetime.now(timezone.utc).isoformat(), 'source_url': url, 'layer_name': meta.get('name'),
                'object_ids_reported': len(oids), 'features_exported': len(feats),
                'all_object_ids_exported_once': got == oids,
                'null_geometries': sum(1 for ft in feats if not ft.get('geometry')),
                'native_spatial_reference': sr, 'geojson_error': gj_err,
                'date_fields_note': 'esriFieldTypeDate values are epoch milliseconds (UTC) as returned by the service.',
                'limitation': 'Exported from a hosted service, not the original Merge.gdb. Use the native-CRS Esri JSON for '
                              'geometry and area work; the EPSG:4326 GeoJSON is server-reprojected for viewing only.',
                'files': {k: {'path': v.name, 'bytes': v.stat().st_size, 'sha256': sha256(v)} for k, v in files.items()}}
    (dest / f'{name}_export_manifest.json').write_text(json.dumps(manifest, indent=2, default=str))
    return manifest


def flat_rows(results):
    for res in results:
        for n in res['layers']:
            for s in n['services'] or [{}]:
                yield {'item_id': n['item_id'], 'item_type': n['item_type'], 'path': n['path'], 'state': n['state'],
                       'ccmc_specific': n['ccmc_specific'], 'ndvi': n['ndvi'], 'month': n['month'], 'is_group': n['is_group'],
                       'layer_type': n['layer_type'], 'service_url': s.get('url') or n.get('url'), 'service_type': s.get('service_type'),
                       'name': s.get('name'), 'geometry_type': s.get('geometry_type'),
                       'wkid': ((s.get('spatial_reference') or {}).get('latestWkid') or (s.get('spatial_reference') or {}).get('wkid')),
                       **{k: (s.get('extent') or {}).get(k) for k in ('xmin', 'ymin', 'xmax', 'ymax')},
                       'feature_count': s.get('feature_count'), 'field_count': len(s.get('fields') or []) or None,
                       'candidate_id_fields': ';'.join(s.get('candidate_id_fields') or []),
                       'pixel_type': s.get('pixel_type'), 'band_count': s.get('band_count'),
                       'pixel_size': f"{s.get('pixel_size_x')} x {s.get('pixel_size_y')}" if s.get('pixel_size_x') else None,
                       'raster_interpretation': s.get('interpretation'), 'error': s.get('error') or s.get('count_error')}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--portal', required=True)
    p.add_argument('--webmap')
    p.add_argument('--webscene')
    p.add_argument('--export', action='append', default=[], metavar='LAYER_URL',
                   help='Download all features of this layer (repeatable), e.g. .../Hosted/Cadastral_V2/FeatureServer/7')
    p.add_argument('--max-features', type=int, default=5000, help='Refuse to export layers larger than this')
    p.add_argument('--out', required=True, help='New output folder')
    a = p.parse_args(argv)
    if not a.webmap and not a.export:
        p.error('give --webmap and/or --export')
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    c = Client(a.portal)
    failed = False
    for url in a.export:
        m, err = safe(export_layer, c, url, out, a.max_features)
        print(json.dumps({'export': redact(url), 'error': err} if err else
                         {k: m[k] for k in ('layer_name', 'object_ids_reported', 'features_exported',
                                            'all_object_ids_exported_once', 'null_geometries', 'geojson_error')}, default=str))
        failed = failed or err is not None or not m['all_object_ids_exported_once']
    if not a.webmap:
        return 3 if failed else 0
    results = []
    for item_id in [a.webmap] + ([a.webscene] if a.webscene else []):
        res, err = safe(inventory_item, c, item_id, out)
        if res is None:
            print(f'FAILED to read item {item_id}: {err}', file=sys.stderr)
            return 2
        results.append(res)
    summary = {'run_utc': datetime.now(timezone.utc).isoformat(), 'portal': c.portal, 'auth': c.auth or 'anonymous',
               'items': [r['item'] for r in results], 'layers': [n for r in results for n in r['layers']]}
    (out / 'portal_layer_inventory.json').write_text(json.dumps(summary, indent=2, default=str))
    rows = list(flat_rows(results))
    with (out / 'portal_layer_inventory.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ['path'])
        w.writeheader(); w.writerows(rows)
    mh = [r for r in rows if r['state'] == 'maharashtra' and not r['is_group']]
    print(json.dumps({'items': summary['items'], 'leaf_services': len(rows),
                      'maharashtra_or_ccmc': [{k: r[k] for k in ('path', 'service_type', 'geometry_type', 'feature_count',
                                                                 'pixel_type', 'candidate_id_fields', 'error')} for r in mh],
                      'errors': sum(1 for r in rows if r['error'])}, indent=2, default=str))
    return 3 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
