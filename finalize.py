"""Verify actual outputs and package evidence without synthetic client files."""
import csv,json,zipfile,unittest
from pathlib import Path
from osgeo import ogr
from engines import dump,source,sha
from test_engines import Engines
base=Path(__file__).resolve().parent; out=base/'actual_outputs'
manifest=json.loads((out/'run_manifest.json').read_text())
src=ogr.Open('/Users/aj/Downloads/Village Boundary Data-Base_MAHARASHTRA/MAHARASHTRA.shp',0)
bad=[]
for f in src.GetLayer():
    if str(f.GetField('District')).strip().upper()=='CHANDRAPUR':
        g=f.GetGeometryRef()
        if g is None or not g.IsValid(): bad.append([f.GetFID(),f.GetField('ORGI_Uniqu'),f.GetField('Vill_name'),'Missing geometry' if g is None else 'Invalid source geometry; retained without repair'])
with (out/'boundary_exceptions.csv').open('w',newline='') as f:
    csv.writer(f).writerows([['source_FID','source_unique_reference','village_name','exception']]+bad)
d=ogr.Open(str(out/'Chandrapur_villages_reference.geojson'),0); l=d.GetLayer()
assert l.GetFeatureCount()==1837
assert all(str(f.GetField('District')).strip().upper()=='CHANDRAPUR' for f in l)
assert len(bad)==4
manifest['boundary_verification']={'reopened_features':1837,'all_district_attributes_Chandrapur':True,'source_invalid_geometries':4,'missing_precision_metadata':'No cadastral survey accuracy established'}
manifest['excel_export_test']=json.loads((out/'excel_export_test.json').read_text())
with (out/'test_results.txt').open('w') as f:
    result=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Engines))
assert result.wasSuccessful()
manifest['code_files']=[source(p) for p in sorted(base.glob('*.py'))]+[source(base/'exporter.mjs'),source(base/'run_local.sh')]
dump(out/'run_manifest.json',manifest)
report='''# KRISHI360 Chandrapur execution QA — 1 November 2026

Status: partial implementation executed. Client release is blocked by inaccessible source files.

## Executed deliverables

Engine 1 (`engines.py ndvi`) reads real raster metadata, checks grids/CRS, decodes explicitly configured scale/offset, calculates float NDVI, writes a georeferenced compressed GeoTIFF, compares supplied NDVI only on the same grid, and records source/code/output hashes. Arithmetic, mask, zero-denominator, additive-offset and grid rejection behavior were executed against synthetic fixtures. No Chandrapur raster was available to process. Reflectance encoding is unverified by default. Missing SCL/cloud QA is explicit. Negative reflectances are retained and flagged; out-of-range NDVI is counted. Raster grid spacing remains in actual CRS units, never automatically labelled 10 metres. This version reads a scene into memory and has no SCL ingestion or fractional plot zonal statistics.

Engine 2 safely validates ZIP destinations, symlinks, duplicate paths, expanded size and CRC before extraction. It lists actual vector layers, schemas, CRS, extent, geometry types and exact candidate key match counts. Explicitly selected plot layers/keys can produce projected geometry areas; missing/invalid/duplicate geometries are withheld. Tests used a temporary 47-member synthetic archive, not the user's Merge.gdb. The actual geodatabase is unavailable. No real feature class, 47-file count, client plot area or cadastral join has been verified.

The actual Maharashtra village shapefile was inspected: 44,659 features, Lambert Conformal Conic on WGS84, projected metre coordinates. All 1,837 records whose District attribute is Chandrapur were exported to EPSG:4326 GeoJSON. Four invalid source geometries are listed in boundary_exceptions.csv. They were retained without repair. The export was reopened and its record count and district attributes checked. These administrative villages are reference geography, not the 87 client plot polygons. They provide no evidence for agricultural/crop area or satellite coverage. No independent official-boundary validation was performed.

Engine 3 (`client.py` plus `exporter.mjs`) reads original literal headings and rows, requires exactly 37 headings, checks the new CSV for the same 37 headings plus UID, validates 87 unique UUIDs on each side and identical key sets, preserves original values, records every substantive discrepancy, and writes companion provenance/exception/UID/manifest sheets. Optional geometry calculations stay in a companion sheet because mapping them to a particular client area field requires field semantics. It rejects uncached or unaccepted source formulas rather than silently changing them. The Excel export/import test passed for 87 synthetic records and 37 synthetic headings with exact cell equality. All five sheet previews were inspected. No actual client values or headings were available, so this is not the requested client workbook. No native Microsoft Excel application test was performed.

## Test evidence

10 automated GIS/data tests passed, plus one Excel export/read-back integration test. All test inputs are synthetic and are isolated from actual outputs. Passing these tests does not validate Chandrapur science, crop classifications or client records. The synthetic workbook is deliberately excluded from delivery.

## Precise source-access limitation

The project folder contains Handbook 3 and Step4A/4B manuals, plus an earlier technical-data-requirements workbook. Recursive searches of the project, Documents, Downloads and temporary files did not find the named Chandrapur source workbook, Krishi369.csv, Merge.gdb.zip or Chandrapur B04/B08/NDVI rasters. A broader home-directory name search through depth five also found no relevant inputs. This is a bounded search, not a claim that files do not exist anywhere. The referenced ChatGPT chat was read through the chat tool: it returned discussion text and attachments=[]. The current chat artifact tool returned artifacts=[]. The available local village boundary was found in Downloads and used directly.

Consequently no KRISHI360_Chandrapur_Client_Excel_V0.xlsx or Chandrapur NDVI GeoTIFF has been issued. Creating either from handbook summaries would invent the literal headers, 87 records or pixel evidence. The user is not being asked to upload files or supply credentials.

## Unresolved record checks

The previous chat reports 87 versus 87 matching unique references, 37 original fields and an added UID, plus 192/2/_ versus 192/2/? and 175/2/_ versus 175/2/?. These remain reported history, not independently reverified results. The implementation preserves original survey values and logs CSV differences; it does not equate underscore and question mark automatically. Explaining the earlier 86 count requires the underlying earlier dataset. No row is removed or fabricated to reconcile it.

No SatSure/sample values are represented as independent KRISHI360 output. No crop, yield, sowing, water or weather model has been run. This package is executable development code and actual administrative-boundary evidence, not a scientifically approved client release.
'''
(base/'QA_REPORT.md').write_text(report)
(base/'README.md').write_text('''# KRISHI360 executable development package

Read QA_REPORT.md for actual execution status and source-access evidence. Client V0 is not released.

GIS dependency: Python 3 with GDAL/OGR and NumPy. The included run_local.sh uses the installed QGIS Python and PROJ database. No installation or credentials were required. Excel writer dependency: Node with @oai/artifact-tool (bundled runtime used here). The node_modules link is local setup and is excluded from the ZIP.

Run from the extracted package directory. These are command templates; substitute actual accepted source paths/field names, not imaginary inputs:

```sh
sh run_local.sh test_engines.py
sh run_local.sh engines.py ndvi --red B04.tif --nir B08.tif --supplied NDVI.tif --out ndvi_run
sh run_local.sh engines.py extract Merge.gdb.zip new_extraction_directory
sh run_local.sh engines.py inspect new_extraction_directory/Merge.gdb layer_inventory.json
sh run_local.sh engines.py areas new_extraction_directory/Merge.gdb ACTUAL_LAYER ACTUAL_UUID_FIELD client_keys.json areas.json
sh run_local.sh client.py original.xlsx Krishi369.csv 'EXACT UUID HEADING' prepared.json --sheet 'ACTUAL SHEET' --areas-json areas.json
node exporter.mjs prepared.json KRISHI360_Chandrapur_Client_Excel_V0.xlsx
```

client_keys.json must contain the accepted UUID strings; inspect all feature classes and their match evidence before choosing a layer. The areas command defaults to UTM 44N in metres, appropriate only after verifying the source lies within that zone. Do not treat village boundaries as plot boundaries. Choose NDVI decoding parameters only from verified encoding evidence. Default identity decoding is explicitly unverified and not cloud masked.

Actual outputs: village reference GeoJSON, boundary inspection, boundary exceptions, run manifest, test results and Excel integration-test result. All synthetic client records/workbooks are excluded. Python source and the JavaScript exporter are included because executable scripts were requested.
''')
files=[p for p in base.rglob('*') if p.is_file() and 'node_modules' not in p.parts and '__pycache__' not in p.parts]
with (base/'SHA256SUMS.txt').open('w') as f:
    for p in sorted(files):
        if p.name!='SHA256SUMS.txt': f.write(sha(p)+'  '+str(p.relative_to(base))+'\n')
package=base.parent/'KRISHI360_Engines_1_3_Partial_Execution.zip'
with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files+[base/'SHA256SUMS.txt']: z.write(p,'krishi360_execution/'+str(p.relative_to(base)))
with zipfile.ZipFile(package) as z: assert z.testzip() is None
print(json.dumps({'package':str(package),'bytes':package.stat().st_size,'sha256':sha(package),'boundary_features':1837,'boundary_exceptions':4,'unit_tests':10,'excel_integration':'PASS'}))
