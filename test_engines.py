"""Synthetic fixtures only. No fixture represents a Chandrapur client plot."""
import csv, json, tempfile, unittest, uuid, zipfile
from pathlib import Path
import numpy as np
from osgeo import gdal,ogr,osr
from engines import engine1,safe_extract,inspect_vector,plot_areas,srs
from client import prepare,read_xlsx

class Engines(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.p=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def raster(self,name,a,shift=0):
        p=self.p/name; d=gdal.GetDriverByName('GTiff').Create(str(p),2,2,1,gdal.GDT_Float32)
        d.SetProjection(srs('EPSG:32644').ExportToWkt()); d.SetGeoTransform((300000+shift,10,0,2200000,0,-10))
        d.GetRasterBand(1).WriteArray(np.array(a)); d.GetRasterBand(1).SetNoDataValue(-9999); d=None
        return p
    def test_ndvi_values_and_mask_roundtrip(self):
        r=self.raster('r.tif',[[1,0],[-9999,2]]); n=self.raster('n.tif',[[3,2],[3,-2]])
        q=self.raster('given.tif',[[.5,1],[-9999,-9999]])
        qa=engine1(r,n,self.p/'out',q)
        self.assertEqual(qa['valid_pixels'],2); self.assertEqual(qa['comparison']['mae'],0)
        d=gdal.Open(str(self.p/'out/ndvi_preliminary.tif'))
        np.testing.assert_array_equal(d.ReadAsArray(),[[.5,1],[-9999,-9999]])
        self.assertEqual(d.GetGeoTransform(),gdal.Open(str(r)).GetGeoTransform())
        self.assertFalse(qa['cloud_mask_applied']); self.assertFalse(qa['reflectance_encoding_verified'])
    def test_mismatched_band_grid_rejected(self):
        r=self.raster('r.tif',[[1,1],[1,1]]); n=self.raster('n.tif',[[3,3],[3,3]],1)
        with self.assertRaises(ValueError): engine1(r,n,self.p/'out')
    def test_supplied_grid_difference_not_compared(self):
        r=self.raster('r.tif',[[1,1],[1,1]]); q=self.raster('q.tif',[[.5,.5],[.5,.5]],1)
        qa=engine1(r,r,self.p/'out',q); self.assertFalse(qa['comparison_same_grid']); self.assertNotIn('comparison',qa)
    def test_offset_changes_ndvi(self):
        r=self.raster('r.tif',[[2000,2000],[2000,2000]]); n=self.raster('n.tif',[[4000,4000],[4000,4000]])
        qa=engine1(r,n,self.p/'out',scale=.0001,offset=-.1)
        self.assertAlmostEqual(qa['min'],.5)
    def test_archive_safety_and_47_members(self):
        z=self.p/'gdb.zip'
        with zipfile.ZipFile(z,'w') as f:
            for i in range(47): f.writestr(f'Merge.gdb/a{i:03d}.gdbtable','fixture')
        self.assertEqual(len(safe_extract(z,self.p/'extract')),47)
        bad=self.p/'bad.zip'
        with zipfile.ZipFile(bad,'w') as f: f.writestr('../escape','bad')
        with self.assertRaises(ValueError): safe_extract(bad,self.p/'bad')
        self.assertFalse((self.p/'escape').exists())
    def test_polygon_area_missing_and_duplicate_keys(self):
        p=self.p/'plots.gpkg'; d=ogr.GetDriverByName('GPKG').CreateDataSource(str(p))
        l=d.CreateLayer('plots',srs('EPSG:32644'),ogr.wkbPolygon); l.CreateField(ogr.FieldDefn('UUID',ogr.OFTString))
        for key in ['one','duplicate','duplicate']:
            f=ogr.Feature(l.GetLayerDefn()); f.SetField('UUID',key)
            f.SetGeometry(ogr.CreateGeometryFromWkt('POLYGON ((300000 2200000,300100 2200000,300100 2200100,300000 2200100,300000 2200000))')); l.CreateFeature(f)
        d=None
        q=plot_areas(p,'plots','UUID',{'one','missing'},self.p/'areas.json')
        self.assertEqual(q['rows'][0]['area_m2'],10000); self.assertEqual(q['missing_client_keys'],['missing'])
        self.assertIsNone(q['rows'][1]['area_m2'])
        info=inspect_vector(p,self.p/'inspect.json',{'one'}); self.assertEqual(info[0]['exact_key_match_counts']['UUID'],1)
    def client_fixture(self):
        h=['UUID','Survey ID']+[f'SYNTHETIC FIELD {i}' for i in range(3,38)]
        rows=[[str(uuid.UUID(int=i+1)),f'{i}/2/_']+[i]*35 for i in range(87)]
        old=self.p/'original.csv'; new=self.p/'new.csv'
        with old.open('w',newline='') as f: csv.writer(f).writerows([h]+rows)
        nr=[r+['uid-'+str(i)] for i,r in enumerate(rows)]
        nr[0][1]='192/2/?'; nr[1][1]='175/2/?'
        rows[0][1]='192/2/_'; rows[1][1]='175/2/_'
        with old.open('w',newline='') as f: csv.writer(f).writerows([h]+rows)
        with new.open('w',newline='') as f: csv.writer(f).writerows([h+['UID']]+nr)
        return old,new,h
    def test_87_reconciliation_two_exceptions_and_37_headers(self):
        old,new,h=self.client_fixture(); q=prepare(old,new,'UUID',self.p/'prepared.json')
        self.assertEqual(q['manifest']['unique_matched_UUIDs'],87)
        self.assertEqual(q['manifest']['substantive_differences'],2)
        self.assertEqual(q['sheets']['Client Output'][0],h)
        self.assertEqual(q['sheets']['Client Output'][1][1],'192/2/_')
    def test_duplicate_UUID_rejected(self):
        old,new,h=self.client_fixture(); rows=list(csv.reader(new.open())); rows[2][0]=rows[1][0]
        with new.open('w',newline='') as f: csv.writer(f).writerows(rows)
        with self.assertRaisesRegex(ValueError,'Duplicate'): prepare(old,new,'UUID',self.p/'out')
    def test_wrong_literal_header_rejected(self):
        old,new,h=self.client_fixture(); rows=list(csv.reader(new.open())); rows[0][1]='Survey ID '
        with new.open('w',newline='') as f: csv.writer(f).writerows(rows)
        with self.assertRaisesRegex(ValueError,'headings'): prepare(old,new,'UUID',self.p/'out')
    def test_missing_record_rejected(self):
        old,new,h=self.client_fixture(); rows=list(csv.reader(new.open()))[:-1]
        with new.open('w',newline='') as f: csv.writer(f).writerows(rows)
        with self.assertRaisesRegex(ValueError,'count'): prepare(old,new,'UUID',self.p/'out')

if __name__=='__main__': unittest.main(verbosity=2)
