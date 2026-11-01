"""Synthetic ArcGIS REST fixture for portal_inventory.py. No response represents real portal content.
The portal is served as 127.0.0.1 and a non-portal ("foreign") server as localhost on the same port."""
import json, os, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import portal_inventory

TOKEN = 'SYNTHETIC-SECRET-TOKEN'


def plot(oid):
    ring = [[300000 + oid, 2200000], [300100 + oid, 2200000], [300100 + oid, 2200100], [300000 + oid, 2200000]]
    return {'attributes': {'OBJECTID': oid, 'uid': f'UID-{oid}', 'survey_no': f'{oid}/2/_'}, 'geometry': {'rings': [ring]}}


class Fake(BaseHTTPRequestHandler):
    seen = []  # (host, token)

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlsplit(self.path); q = parse_qs(u.query); port = self.server.server_port
        base, foreign = f'http://127.0.0.1:{port}', f'http://localhost:{port}'
        host = self.headers['Host'].split(':')[0]
        token = q.get('token', [None])[0]
        Fake.seen.append((host, token))
        ext = {'xmin': 0, 'ymin': 0, 'xmax': 100, 'ymax': 100, 'spatialReference': {'wkid': 32643}}
        routes = {
            '/portal/sharing/rest/content/items/WM': {'id': 'WM', 'title': 'Krishi fixture', 'type': 'Web Map', 'owner': 'fixture'},
            '/portal/sharing/rest/content/items/WM/data': {'operationalLayers': [
                {'title': 'CCMC', 'layerType': 'GroupLayer', 'layers': [
                    {'title': 'Plots fixture', 'layerType': 'ArcGISFeatureLayer', 'url': f'{base}/srv/Plots/FeatureServer/0?token=LEAK'},
                    {'title': 'NDVI October_2026', 'layerType': 'ArcGISImageServiceLayer', 'url': f'{base}/srv/NDVI/ImageServer'},
                    {'title': 'Oct 1_15 NDVI', 'layerType': 'ArcGISMapServiceLayer', 'url': f'{base}/srv/NDVI2/MapServer'}]},
                {'title': 'TGRAC Admin', 'layerType': 'ArcGISMapServiceLayer', 'url': f'{base}/srv/Admin/MapServer'},
                {'title': 'Public elsewhere', 'layerType': 'ArcGISFeatureLayer', 'url': f'{foreign}/ext/FeatureServer/0'},
                {'title': 'Maharashtra Village Boundary', 'layerType': 'ArcGISFeatureLayer', 'url': f'{base}/srv/Missing/FeatureServer/0'}]},
            '/srv/Plots/FeatureServer/0': {'name': 'Plots V4', 'type': 'Feature Layer', 'geometryType': 'esriGeometryPolygon',
                                            'extent': ext, 'fields': [
                                                {'name': 'OBJECTID', 'type': 'esriFieldTypeOID'}, {'name': 'uid', 'type': 'esriFieldTypeString'},
                                                {'name': 'survey_no', 'type': 'esriFieldTypeString'}]},
            '/srv/NDVI/ImageServer': {'name': 'NDVI', 'pixelType': 'U8', 'bandCount': 1, 'pixelSizeX': 10, 'pixelSizeY': 10,
                                      'hasRasterAttributeTable': True, 'extent': {'spatialReference': {'wkid': 32644}}},
            '/srv/NDVI/ImageServer/keyProperties': {'AcquisitionDate': None},
            '/srv/NDVI/ImageServer/rasterAttributeTable': {'features': [{'attributes': {'Value': 1, 'ClassName': 'Water'}}]},
            '/srv/NDVI2/MapServer': {'layers': [{'id': 0, 'name': 'Oct.tif'}]},
            '/srv/NDVI2/MapServer/0': {'name': 'Oct.tif', 'type': 'Raster Layer', 'extent': ext},
            '/srv/NDVI2/MapServer/legend': {'layers': [{'layerId': 0, 'legend': [{'label': 'High : 0.9'}, {'label': 'Low : -0.2'}]}]},
            '/srv/NDVI2/MapServer/identify': {'results': [{'attributes': {'Pixel Value': '0.4567'}}]},
            '/srv/Admin/MapServer': {'layers': [{'id': 3, 'name': 'Mandals'}, {'id': 4, 'name': 'Villages'}]},
            '/srv/Admin/MapServer/3': {'name': 'Mandals', 'type': 'Feature Layer', 'geometryType': 'esriGeometryPolygon', 'fields': []},
            '/srv/Admin/MapServer/4': {'name': 'Villages', 'type': 'Feature Layer', 'geometryType': 'esriGeometryPolygon', 'fields': []},
            '/ext/FeatureServer/0': {'name': 'Public', 'type': 'Feature Layer', 'geometryType': 'esriGeometryPoint', 'fields': []},
        }
        path = u.path.rstrip('/')
        if host == 'localhost' and token:  # a foreign server rejects the portal's token, as TGRAC/Esri did
            body = {'error': {'code': 498, 'message': 'Invalid Token'}}
        elif path == '/srv/Plots/FeatureServer/0/query':
            if q.get('returnCountOnly'):
                body = {'count': 3}
            elif q.get('returnIdsOnly'):
                body = {'objectIdFieldName': 'OBJECTID', 'objectIds': [3, 1, 2]}
            elif q.get('objectIds'):
                oids = [int(x) for x in q['objectIds'][0].split(',')]
                if q.get('f') == ['geojson']:
                    body = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': plot(o)['attributes'],
                                                                       'geometry': None} for o in oids]}
                else:
                    body = {'spatialReference': {'wkid': 32643}, 'features': [plot(o) for o in oids]}
            else:
                body = {'features': [{'attributes': {'uid': 'fixture'}}]}
        elif path.endswith('/query'):
            body = {'count': 0} if q.get('returnCountOnly') else {'features': []}
        elif path in routes:
            body = routes[path]
        else:
            body = {'error': {'code': 404, 'message': 'Not found'}}
        data = json.dumps(body).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(data)


class PortalInventory(unittest.TestCase):
    def setUp(self):
        Fake.seen = []
        self.srv = HTTPServer(('127.0.0.1', 0), Fake)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory(); self.out = Path(self.tmp.name) / 'inv'
        self.env = dict(os.environ)
        for k in ('ARCGIS_TOKEN', 'ARCGIS_TOKENS_JSON', 'ARCGIS_USERNAME', 'ARCGIS_PASSWORD'):
            os.environ.pop(k, None)
        os.environ['ARCGIS_TOKEN'] = TOKEN
        os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost'
        self.portal = f'http://127.0.0.1:{self.srv.server_port}/portal'

    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close(); self.tmp.cleanup()
        os.environ.clear(); os.environ.update(self.env)

    def run_inventory(self, *extra):
        rc = portal_inventory.main(['--portal', self.portal, '--webmap', 'WM', '--out', str(self.out), *extra])
        return rc, json.loads((self.out / 'portal_layer_inventory.json').read_text())

    def test_states_ccmc_and_services(self):
        rc, inv = self.run_inventory()
        self.assertEqual(rc, 0)
        by = {n['path']: n for n in inv['layers']}
        self.assertEqual(by['CCMC / Plots fixture']['state'], 'maharashtra')  # inherits group state
        self.assertTrue(by['CCMC / Plots fixture']['ccmc_specific'])
        self.assertEqual(by['TGRAC Admin']['state'], 'telangana')
        self.assertTrue(by['Maharashtra Village Boundary']['not_listed_rule'])
        plots = by['CCMC / Plots fixture']['services'][0]
        self.assertEqual(plots['feature_count'], 3)
        self.assertEqual(plots['candidate_id_fields'], ['uid', 'survey_no'])
        ndvi = by['CCMC / NDVI October_2026']
        self.assertEqual(ndvi['month'], 'Oct 2026')  # same label as the portal UI
        self.assertIn('classified', ndvi['services'][0]['interpretation'])
        self.assertEqual(len(by['TGRAC Admin']['services']), 2)  # map service root expanded
        self.assertIn('error', by['Maharashtra Village Boundary']['services'][0])  # failure recorded, not fatal

    def test_map_service_raster_legend_and_probe(self):
        rc, inv = self.run_inventory()
        s = {n['path']: n for n in inv['layers']}['CCMC / Oct 1_15 NDVI']['services'][0]
        self.assertEqual(s['legend_labels'], ['High : 0.9', 'Low : -0.2'])
        self.assertEqual(len(s['pixel_probes']), 5)
        self.assertTrue(s['interpretation'].startswith('Continuous'))

    def test_token_only_sent_to_portal_host(self):
        rc, inv = self.run_inventory()
        self.assertIn(('127.0.0.1', TOKEN), Fake.seen)
        self.assertNotIn(('localhost', TOKEN), Fake.seen)
        public = {n['path']: n for n in inv['layers']}['Public elsewhere']['services'][0]
        self.assertNotIn('error', public)
        self.assertEqual(public['name'], 'Public')

    def test_token_rejected_falls_back_to_anonymous(self):
        c = portal_inventory.Client(self.portal)
        c.portal = f'http://localhost:{self.srv.server_port}/portal'  # pretend the foreign host is the portal
        meta = c.get(f'http://localhost:{self.srv.server_port}/ext/FeatureServer/0')
        self.assertEqual(meta['name'], 'Public')
        self.assertEqual([t for h, t in Fake.seen if h == 'localhost'], [TOKEN, None])

    def test_token_never_stored(self):
        self.run_inventory('--export', f'http://127.0.0.1:{self.srv.server_port}/srv/Plots/FeatureServer/0')
        for p in self.out.rglob('*'):
            if p.is_file():
                text = p.read_text()
                self.assertNotIn(TOKEN, text, p.name)
                self.assertNotIn('token=LEAK', text, p.name)

    def test_export_pages_all_features(self):
        c = portal_inventory.Client(self.portal)
        m = portal_inventory.export_layer(c, f'http://127.0.0.1:{self.srv.server_port}/srv/Plots/FeatureServer/0',
                                          self.out, batch=2)
        self.assertEqual((m['object_ids_reported'], m['features_exported']), (3, 3))
        self.assertTrue(m['all_object_ids_exported_once'])
        esri = json.loads((self.out / 'exports' / 'Plots_V4.esri.json').read_text())
        self.assertEqual(esri['spatialReference'], {'wkid': 32643})
        self.assertEqual([f['attributes']['OBJECTID'] for f in esri['features']], [1, 2, 3])
        rows = (self.out / 'exports' / 'Plots_V4_attributes.csv').read_text().splitlines()
        self.assertEqual(rows[0], 'OBJECTID,uid,survey_no')
        self.assertEqual(len(rows), 4)
        for f in m['files'].values():
            self.assertEqual(len(f['sha256']), 64)

    def test_export_refuses_large_layer(self):
        rc = portal_inventory.main(['--portal', self.portal, '--out', str(self.out), '--max-features', '2',
                                    '--export', f'http://127.0.0.1:{self.srv.server_port}/srv/Plots/FeatureServer/0'])
        self.assertEqual(rc, 3)
        self.assertFalse((self.out / 'exports').exists())

    def test_unreadable_item_fails_nonzero(self):
        self.assertEqual(portal_inventory.main(['--portal', self.portal, '--webmap', 'NOPE', '--out', str(self.out)]), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
