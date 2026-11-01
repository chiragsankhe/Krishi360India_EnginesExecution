# KRISHI360 executable development package

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
