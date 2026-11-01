# KRISHI360 Chandrapur execution QA — 1 November 2026

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
