# KRISHI360 Chandrapur: execution plan and data-gap register

Prepared 1 November 2026 from the V1 and V2 team instructions, the code in this repository and the portal
client code. This is a plan. It is not run evidence. Nothing below has been executed on client data.

## 1. What has been inspected

| Source | Status | Finding |
|---|---|---|
| Team instructions V1 and V2 (.docx) | Read in full | Same Steps 1 to 20. V2 adds an owner, a supporting role and a reviewer for each step. |
| This repository (`engines.py`, `client.py`, `exporter.mjs`, tests) | Code reviewed | The code is development-only. It has passed tests on synthetic data but has never run on Chandrapur data. Defects are listed in section 5. |
| `actual_outputs/Chandrapur_villages_reference.geojson` | Opened | 1,837 administrative villages, lon 78.80 to 79.99, lat 19.46 to 20.74. `Chandrapur (M Corp)` covers lon 79.27 to 79.33. Four geometries are invalid. These are reference boundaries and must not be used as plots. |
| Web map `bf308acdb69c432fab3e44c292fd077f` "Krishi (Telangana)" | Inventoried by the user with `portal_inventory.py` (first version); outputs uploaded | 65 service rows, 20 of them Maharashtra/CCMC. See section 3. 45 rows failed with `498 Invalid Token` because of a script defect, now fixed. |
| Web scene `76fc30b961374111b38101460079b308` "BMC Map" | Inventoried | Mumbai (BMC) 3D city data, 682 rows. Nothing relates to Chandrapur, so it is out of scope. |
| Portal client code (`usePortalLayers`, field-data sources) | Read | See section 3. |

## 2. Input availability (Step 2: missing_input_exceptions)

| Required input | Needed for | Available? |
|---|---|---|
| `01.Krishi360_Chandrapur_PoC_plot_level_monitoring_Cleaned_v2(1).xlsx` | 37 headings, 87 records, everything in the workbook | **Missing**. This is the critical blocker. |
| `Krishi369.csv` (37 headings + UID) | 87-to-87 reconciliation, UID mapping, survey differences | **Missing** |
| `Merge.gdb.zip` | Plot polygons, UUID join, areas | **Missing as a file.** The portal has a hosted 87-polygon layer, `Krishi369 Data`. Once the GIS engineer approves it, it can serve as the plot source (section 3). |
| B04 / B08 GeoTIFFs, 24 Oct 2026 plus the Sep/Oct scenes | Engine 1 NDVI | **Missing everywhere**, including the portal. The portal has only NDVI products, no reflectance bands, so Engine 1 cannot calculate NDVI. |
| Supplied NDVI GeoTIFF (continuous) | Step 12 comparison | **Missing as a file.** The portal's CCMC NDVI exists only as map-service rasters. Whether the pixels are continuous or classified is not yet known (section 3). |
| SCL / cloud-probability rasters | Step 13 cloud masking | **Missing everywhere**. Without them `cloud_mask_applied = false`. |
| Earlier 86-record dataset | Step 8 explanation of the 86 count | **Missing**. It stays unresolved unless supplied. |
| Maharashtra village shapefile (SHP/SHX/DBF/PRJ...) | Reference geography and hashes | Only the derived GeoJSON is in the repo. The original sidecar files are on the Mac (`/Users/aj/Downloads/...`). |
| Krishi369 Data full attributes and geometry | 54-field schema, UUID field identity, area work | **Not exported yet.** Run `--export` (section 3). |

## 3. Portal findings (web map inventory, user run of 1 November 2026)

Layers relevant to Chandrapur (all on `bmc3dmumbai.com/server`, EPSG:32643 unless noted):

| Web map path | Service | What it is | Use in this milestone |
|---|---|---|---|
| CCMC / Cadastral / **Krishi369 Data** | `Hosted/Cadastral_V2/FeatureServer/7` (`Cadastral_Map_V4`) | **87 polygons**, 54 fields, including `uid`, `survey_no`, `plot_id__s`, `survey_are`, `plot_statu`, `irrigation` | The probable client plot layer (Steps 14 to 16). It needs the GIS engineer's approval: matching the UUID field, checking duplicates and validating geometry. |
| CCMC / Cadastral / Cadastral Boundary | `Hosted/Cadastral/FeatureServer/4` (`Cadastral_Map`) | 522,696 cadastral parcels, 11 fields, including `survey_no` and `uid` | Survey-number evidence for Step 8 (`192/2`, `175/2`). Too large to export whole; query only around the 87 plots. |
| CCMC / NDVI / Oct 1_15, Oct 15_30, Sep 15_30 | `Oct_1_15_NDVI`, `15_30_Oct_NDVI` (**EPSG:4326**), `Sep_15_30_NDVI` MapServers | Half-month NDVI rasters, served as map-service raster layers | Imported observations only. They are composites with unknown pixel selection and no cloud QA, and the CRS and grid differ between dates. The pixel type has not been read yet. |
| NDVI / NDVI_August, September, October_2026 | `NDVI_*_2026` MapServers | Monthly NDVI rasters. Your UI rule labels them Telangana, which only means the group title lacks "CCMC". | Location not confirmed; the extent decides. Your UI's `NDVI_CLASSES` suggests these are 5-class products. |
| DEM | `Hosted/DEM_WTL1` (EPSG:3857, tiled) | Elevation | Not needed for this milestone. |
| CCMC / Sentinel-2 / SPI, World Soils SOC, Sentinel-2 10m LULC | Esri Living Atlas (`services9.arcgis.com`, `tiledimageservices.arcgis.com`, `ic.imagery1.arcgis.com`) | Global context layers, despite the "Sentinel-2" group name | **Not** Sentinel-2 bands. They must not populate client fields. All failed with 498 (token defect, fixed). |
| Maharashtra Village Boundary, India district/state | `Hosted/Krishi/FeatureServer/2,1,0` (EPSG:4326) | 48,926 villages, 482 districts, 32 states | Reference only. Note: 48,926 portal villages vs 44,659 in the shapefile used before, so they are different sources. |

Other findings:

- **Location.** The web map's saved extent (78.99–79.04°E, 20.32–20.35°N) covers Tembhurda, Pimpalgaon Maroti,
  Atmurdi and Belgaon in **Warora taluka**, not the Chandrapur municipal area. "CCMC" is a group name, so the
  plot extent must be checked against Warora.
- **CRS for areas.** The plots are stored in UTM 43N (EPSG:32643), but Warora (about 79°E) lies in zone 44.
  At 79.01°E, 20.34°N the planar area scale is 1.00354 in 32643 (+0.35%) and 1.00027 in EPSG:32644 (+0.03%).
  Areas must therefore be computed in EPSG:32644, the engine default. Any stored `Shape__Area` in 32643 will read
  about 0.35% high.
- **Headings.** The field names are shapefile-truncated (`survey_are`, `plot_id__s`), so this layer cannot
  supply the 37 literal client headings. The original workbook is still required (Step 6).
- **No reflectance bands or SCL** exist anywhere in the web map, so Engine 1 (B04/B08 to NDVI) remains blocked.
- **TGRAC and Telangana layers** (Chinnambavi, Dagada, Agri_Admin) are another state. They must not populate
  any Chandrapur field.

Next portal run (fixed script, read-only, run where the portal is reachable):

```bash
ARCGIS_USERNAME=gisuserone ARCGIS_PASSWORD='YOUR_PASSWORD' python portal_inventory.py --portal https://bmc3dmumbai.com/portal --webmap bf308acdb69c432fab3e44c292fd077f --export https://bmc3dmumbai.com/server/rest/services/Hosted/Cadastral_V2/FeatureServer/7 --out portal_inventory_run2
```

Upload the whole output folder, including `portal_layer_inventory.json` (fields, sample rows, raster legends and
pixel probes) and `exports/` (the 87 plots in their native CRS, plus attributes and a manifest). The token is
now sent only to the portal host. Other hosts are called anonymously, and a 498 is retried without the token.
The outputs contain no credentials.

## 4. Step-by-step procedure, mapped to the four deliverables

Run ID format: `RUN_20261101_R01`. All outputs go to `runs/RUN_ID/...` and `input/original` is never modified.

### Phase A: intake and setup (Steps 1 to 4)
1. Create the folder tree from Step 1 and `run_config.json` (lead, operators, reviewer, OS, reporting period, UTC).
2. Put every original into `input/original/`, then build `input_manifest.csv` (bytes, SHA256, role, read status)
   and `missing_input_exceptions.csv` (section 2 is the starting list).
3. Portal inventory: **done** (section 3). Run 2 is still to come: the `--export` of Krishi369 Data, plus raster
   legends and pixel probes. Add the export files and their SHA256 values to `input_manifest.csv`, with the role
   "plot polygons (hosted export)".
4. Set up the environment: GDAL/OGR, NumPy, openpyxl. This container can provide GDAL 3.8 through apt or GDAL 3.12
   through wheels. Record versions in `environment_versions.txt` and run the baseline tests.
5. Fix the code defects in section 5 and re-run the tests. **These form the "updated scripts" deliverable.**

### Phase B: client records (Steps 5 to 8). Feeds deliverable 1
6. Inspect the original workbook: sheets, header row, hidden rows and columns, merged cells, formulas, date cells.
   Save `client_headers.json` (37 literal strings) and `field_contract.csv` (unit, period, meaning, or "unresolved").
7. Reconcile with `client.py`: 87 = 87 rows, 87 unique UUIDs on each side, intersection 87.
   Outputs: `uuid_join_audit.csv`, `all_field_differences.csv`, `UID_mapping.csv`.
8. Locate the `192/2/_` vs `192/2/?` and `175/2/_` vs `175/2/?` cases by UUID and row. Keep the original strings.
   Output: `survey_reference_exceptions.csv`. Compare against the 86-record dataset if it is supplied.

### Phase C: NDVI. Deliverable 2, raster part (Steps 9 to 13)
9. `raster_inventory.csv` and `grid_comparison.json` for every TIFF: CRS, transform, NoData, scale/offset, tags, date
   evidence. Pair B04/B08 by metadata, not by filename.
10. `decoding_decision.md`: was the L2A offset applied (Sentinel-2 processing baseline 04.00 or later stores
    BOA_ADD_OFFSET = -1000)? If the evidence is missing, the result is a conditional development output.
11. `engines.py ndvi` for 24 Oct first, then each other date separately. Outputs per date: `ndvi_preliminary.tif` and
    `engine1_manifest.json`.
12. Compare with the supplied continuous NDVI only on the same grid, adding bias and percentiles. Produce
    `independent_pixel_checks.csv` (low NDVI, high NDVI, scene edge, masked pixel, zero denominator).
13. `cloud_QA_decision.md`: without SCL, `cloud_mask_applied = false` and the NDVI is labelled preliminary.

### Phase D: plot areas. Deliverable 2, geometry part (Steps 14 to 17)
14. If Merge.gdb is supplied: run `engines.py extract` and `inspect`. Otherwise run `inspect` on the exported
    Krishi369 Data layer. Output: `layer_inventory.json`, run with `--keys-json client_keys.json`. Expected
    candidates are `plot_id__s` and `uid`. Confirm the UUID against the workbook's UUID column; do not assume it.
15. `plot_layer_selection.json`: layer (`Cadastral_V2/FeatureServer/7`), UUID field, normalisation rule and
    rationale. Also check that the extent lies in Warora (section 3) and compare `survey_no` with the workbook.
16. `engines.py areas ... --target EPSG:32644`. UTM 44N fits: the district spans 78.80 to 79.99 E, and the native
    32643 would overstate area by 0.35%. Outputs:
    `plot_areas.json` (m², ha, acres) and `plot_geometry_QA.csv`. Invalid or duplicate geometries are withheld.
    A missing polygon is never recorded as zero.
17. Independent QGIS/ArcGIS area check: smallest, largest and suspect plots (`independent_GIS_checks.csv`).
    Also `area_comparison.csv` against the client survey area once its unit is confirmed, and
    `acquisition_coverage.csv` (footprint overlap and valid-data share per plot and date).
    Optional: a plot NDVI sheet, with pixel counts and valid fraction, labelled "not cloud screened". Without B04/B08,
    the only plot NDVI source is the portal's CCMC NDVI. Any such value is an **imported** observation (source
    service, half-month window, CRS) and is never a KRISHI360 calculation.

### Phase E: workbook. Deliverable 1 (Step 18)
18. `client.py ... --areas-json plot_areas.json`, then the workbook writer. Sheets:
    - Client Output: exactly 37 columns, 87 rows, original order, no UID
    - Quality and Provenance: row-level
    - Exceptions
    - UID Mapping: with source row numbers
    - Geometry Calculations
    - Run Manifest

    Imported values keep their imported status. Unsupported fields stay blank, with the reason recorded in QA.

### Phase F: QA and delivery. Deliverables 3 and 4 (Steps 19 and 20)
19. Read the saved workbook back and compare it cell by cell with the source. Inspect the first, middle and last rows
    plus every exception. Run the failure-case tests and a fresh rerun in a new folder. Outputs:
    `test_summary.json`, `actual_data_validation.csv` and `QA_REPORT.md`, with passed, uncertain and unavailable
    results listed separately.
20. Build `delivery/RUN_ID/` with `SHA256SUMS.txt` and a ZIP integrity check. Record the release decision: accepted,
    accepted preliminary with limitations, or blocked.

## 5. Code defects found in review (to fix before the real run)

| File | Defect | Fix |
|---|---|---|
| `exporter.mjs` | Depends on `@oai/artifact-tool`, which is not on npm (`E404`); it only exists in the original runtime. | Replace with an openpyxl writer and repeat the round-trip tests. |
| `engines.py` | `dump(..., allow_nan=False)` crashes when a raster's NoData is NaN (common for float NDVI). | Serialise NaN NoData explicitly, as `"NaN"`. |
| `engines.py` | The NDVI comparison reports only count/MAE/RMSE/max. | Add signed bias and percentiles (Step 12). |
| `engines.py` | `inspect`/`areas` match keys exactly. | Add a validated canonical UUID comparison while keeping raw values (Step 15). Add hectares and per-geometry QA (Step 16). |
| `client.py` | Excel dates are read as bare serial numbers. | Read cell styles and the workbook date system (Step 5.5). |
| `client.py` | Rows are compacted, so the source Excel row numbers are lost. | Keep row references for UID Mapping and row-level provenance (Step 18). |
| `client.py` | Rejects any source formula. | Add a documented policy: preserve the expression, or accept the cached value. |
| `client.py` | Provenance is field-level only. | Extend to row-level (Step 18). |
| `execute_available.py`, `finalize.py`, `test_export.py`, `run_local.sh` | Hard-coded `/Users/aj/...` and QGIS Mac paths. `finalize.py` also **overwrites README.md and QA_REPORT.md** with fixed text. | Parameterise the paths. Stop overwriting the docs. |
| `portal_inventory.py` (v1) | Sent the portal token to non-portal hosts (TGRAC, Esri), which answered `498 Invalid Token` for 45 web-map rows. Read no legend or pixel type for MapServer raster layers. | **Fixed:** the token now goes only to the portal host, with an anonymous retry on 498/499. Legends and pixel probes are recorded, extents are in the CSV, and `--export` was added. 8 tests pass. |
| none | No end-to-end wrapper (S5). | Add `run_pipeline.py` with explicit paths, logs and nonzero exits on blocking failures. |

## 6. Decisions needed

- The deliverable name: the instructions say `..._Client_Excel_V0.xlsx`, while the request says V1.
- The named people for each role in the V2 responsibility matrix.
- Who supplies the missing originals in section 2, and from where.
