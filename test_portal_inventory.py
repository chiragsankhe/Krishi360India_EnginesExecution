"""Synthetic ArcGIS REST fixture for portal_inventory.py. No response represents real portal content."""
import json, os, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import portal_inventory

TOKEN = 'SYNTHETIC-SECRET-TOKEN'


class Fake(BaseHTTPRequestHandler):
    seen_tokens = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlsplit(self.path); q = parse_qs(u.query); base = f'http://127.0.0.1:{self.server.server_port}'
        Fake.seen_tokens.append(q.get('token', [None])[0])
        routes = {
            '/portal/sharing/rest/content/items/WM': {'id': 'WM', 'title': 'Krishi fixture', 'type': 'Web Map', 'owner': 'fixture'},
            '/portal/sharing/rest/content/items/WM/data': {'operationalLayers': [
                {'title': 'CCMC', 'layerType': 'GroupLayer', 'layers': [
                    {'title': 'Plots fixture', 'layerType': 'ArcGISFeatureLayer', 'url': f'{base}/srv/Plots/FeatureServer/0?token=LEAK'},
                    {'title': 'NDVI October_2026', 'layerType': 'ArcGISImageServiceLayer', 'url': f'{base}/srv/NDVI/ImageServer'}]},
                {'title': 'TGRAC Admin', 'layerType': 'ArcGISMapServiceLayer', 'url': f'{base}/srv/Admin/MapServer'},
                {'title': 'Maharashtra Village Boundary', 'layerType': 'ArcGISFeatureLayer', 'url': f'{base}/srv/Missing/FeatureServer/0'}]},
            '/srv/Plots/FeatureServer/0': {'name': 'Plots', 'type': 'Feature Layer', 'geometryType': 'esriGeometryPolygon',
                                            'extent': {'spatialReference': {'wkid': 4326}}, 'fields': [
                                                {'name': 'OBJECTID', 'type': 'esriFieldTypeOID'}, {'name': 'UUID', 'type': 'esriFieldTypeString'},
                                                {'name': 'Survey_No', 'type': 'esriFieldTypeString'}]},
            '/srv/NDVI/ImageServer': {'name': 'NDVI', 'pixelType': 'U8', 'bandCount': 1, 'pixelSizeX': 10, 'pixelSizeY': 10,
                                      'hasRasterAttributeTable': True, 'extent': {'spatialReference': {'wkid': 32644}}},
            '/srv/NDVI/ImageServer/keyProperties': {'AcquisitionDate': None},
            '/srv/NDVI/ImageServer/rasterAttributeTable': {'features': [{'attributes': {'Value': 1, 'ClassName': 'Water'}}]},
            '/srv/Admin/MapServer': {'layers': [{'id': 3, 'name': 'Mandals'}, {'id': 4, 'name': 'Villages'}]},
            '/srv/Admin/MapServer/3': {'name': 'Mandals', 'type': 'Feature Layer', 'geometryType': 'esriGeometryPolygon', 'fields': []},
            '/srv/Admin/MapServer/4': {'name': 'Villages', 'type': 'Feature Layer', 'geometryType': 'esriGeometryPolygon', 'fields': []},
        }
        path = u.path.rstrip('/')
        if path.endswith('/query'):
            body = {'count': 87} if q.get('returnCountOnly') else {'features': [{'attributes': {'UUID': 'fixture'}}]}
        elif path in routes:
            body = routes[path]
        else:
            body = {'error': {'code': 404, 'message': 'Not found'}}
        data = json.dumps(body).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(data)


class PortalInventory(unittest.TestCase):
    def setUp(self):
        self.srv = HTTPServer(('127.0.0.1', 0), Fake)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.tmp = tempfile.TemporaryDirectory(); self.out = Path(self.tmp.name) / 'inv'
        self.env = dict(os.environ)
        for k in ('ARCGIS_TOKEN', 'ARCGIS_TOKENS_JSON', 'ARCGIS_USERNAME', 'ARCGIS_PASSWORD'):
            os.environ.pop(k, None)
        os.environ['ARCGIS_TOKEN'] = TOKEN
        os.environ['NO_PROXY'] = os.environ['no_proxy'] = '127.0.0.1,localhost'

    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close(); self.tmp.cleanup()
        os.environ.clear(); os.environ.update(self.env)

    def run_inventory(self):
        portal = f'http://127.0.0.1:{self.srv.server_port}/portal'
        rc = portal_inventory.main(['--portal', portal, '--webmap', 'WM', '--out', str(self.out)])
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
        self.assertEqual(plots['feature_count'], 87)
        self.assertEqual(plots['candidate_id_fields'], ['UUID', 'Survey_No'])
        ndvi = by['CCMC / NDVI October_2026']
        self.assertEqual(ndvi['month'], 'Oct 2026')  # same label as the portal UI
        self.assertIn('classified', ndvi['services'][0]['interpretation'])
        self.assertEqual(len(by['TGRAC Admin']['services']), 2)  # map service root expanded
        self.assertIn('error', by['Maharashtra Village Boundary']['services'][0])  # failure recorded, not fatal

    def test_token_sent_but_never_stored(self):
        self.run_inventory()
        self.assertIn(TOKEN, Fake.seen_tokens)
        for p in self.out.iterdir():
            text = p.read_text()
            self.assertNotIn(TOKEN, text, p.name)
            self.assertNotIn('token=LEAK', text, p.name)

    def test_unreadable_item_fails_nonzero(self):
        portal = f'http://127.0.0.1:{self.srv.server_port}/portal'
        self.assertEqual(portal_inventory.main(['--portal', portal, '--webmap', 'NOPE', '--out', str(self.out)]), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
