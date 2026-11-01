"""Execute real available boundary inspection; retain test evidence separately."""
import csv,json,subprocess,sys,unittest
from pathlib import Path
from datetime import datetime,timezone
from osgeo import ogr,osr,gdal
from engines import inspect_vector,source,dump,srs
from test_engines import Engines

base=Path(__file__).resolve().parent
out=base/'actual_outputs'; out.mkdir(exist_ok=True)
path=Path('/Users/aj/Downloads/Village Boundary Data-Base_MAHARASHTRA/MAHARASHTRA.shp')
info=inspect_vector(path,out/'maharashtra_boundary_inspection.json')
manifest={'run_utc':datetime.now(timezone.utc).isoformat(),'gdal':gdal.VersionInfo(),
 'source_files':[source(p) for p in sorted(path.parent.glob('MAHARASHTRA.*'))],
 'scope':'Administrative village boundaries only; not cadastral client plot boundaries',
 'client_release_status':'BLOCKED_MISSING_SOURCE_FILES',
 'unavailable_inputs':['01.Krishi360_Chandrapur_PoC_plot_level_monitoring_Cleaned_v2(1).xlsx','Krishi369.csv','Merge.gdb.zip','Chandrapur B04/B08 and supplied NDVI TIFFs'],
 'search_evidence':{'project_recursive':'Only manuals and earlier technical-data-requirements workbook present',
 'local_search':'Documents, Downloads and temporary storage searched by relevant names/extensions; broader home search to depth 5 also attempted',
 'referenced_chat':'read_thread returned conversation text and attachments=[]',
 'current_chat_artifacts':'list_artifacts returned artifacts=[]'},
 'prior_chat_reported_only':{'records':87,'unique_matches':87,'fields':37,'new_fields_including_UID':38,'survey_differences':['192/2/_ versus 192/2/?','175/2/_ versus 175/2/?']},
 'independent_client_reconciliation':'Not performed. No original records accessible. Earlier 86-count explanation remains unresolved.'}
d=ogr.Open(str(path),0); l=d.GetLayer()
target=out/'Chandrapur_villages_reference.geojson'
if target.exists(): raise RuntimeError('Use a fresh output directory to preserve prior boundary outputs')
dest=ogr.GetDriverByName('GeoJSON').CreateDataSource(str(target))
dstsr=srs('EPSG:4326'); ol=dest.CreateLayer('Chandrapur_villages',dstsr,ogr.wkbMultiPolygon)
for field in l.schema: ol.CreateField(field)
transform=osr.CoordinateTransformation(srs(l.GetSpatialRef().ExportToWkt()),dstsr)
count=0; invalid=0
for f in l:
    if str(f.GetField('District')).strip().upper()!='CHANDRAPUR': continue
    g=f.GetGeometryRef()
    if g is None: continue
    if not g.IsValid(): invalid+=1
    g=g.Clone(); g.Transform(transform)
    if g.GetGeometryName()=='POLYGON': g=ogr.ForceToMultiPolygon(g)
    nf=ogr.Feature(ol.GetLayerDefn()); nf.SetFrom(f); nf.SetGeometry(g); ol.CreateFeature(nf); count+=1
dest=None
manifest['boundary_result']={'maharashtra_features':info[0]['count'],'Chandrapur_features_exported':count,'invalid_source_geometries':invalid,
 'selection':"Python strip().upper() on District equals CHANDRAPUR",'output':source(target),'output_crs':'EPSG:4326',
 'area_status':'No cadastral plot area or agricultural area inferred from village boundaries'}
with (out/'test_results.txt').open('w') as f:
    result=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Engines))
manifest['tests']={'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'scope':'Synthetic fixtures only'}
dump(out/'run_manifest.json',manifest)
print(json.dumps(manifest['boundary_result'],indent=2)); print(manifest['tests'])
