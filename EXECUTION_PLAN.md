# KRISHI360 Chandrapur: execution plan and data-gap register

Prepared 1 November 2026 from the V1 and V2 team instructions, the code in this repository and the portal
client code. This is a plan. It is not run evidence. Nothing below has been executed on client data.

## 1. What has been inspected

| Source | Status | Finding |
|---|---|---|
| Team instructions V1 and V2 (.docx) | Read in full | Same Steps 1 to 20. V2 adds an owner, a supporting role and a reviewer for each step. |
| This repository (`engines.py`, `client.py`, `exporter.mjs`, tests) | Code reviewed | The code is development-only. It has passed tests on synthetic data but has never run on Chandrapur data. Defects are listed in section 5. |
| `actual_outputs/Chandrapur_villages_reference.geojson` | Opened | 1,837 administrative villages, lon 78.80 to 79.99, lat 19.46 to 20.74. `Chandrapur (M Corp)` covers lon 79.27 to 79.33. Four geometries are invalid. These are reference boundaries and must not be used as plots. |
| ArcGIS portal `bmc3dmumbai.com/portal`, web map `bf308acdb69c432fab3e44c292fd077f` | **Not reachable** | The session's network policy denies the host (proxy 403). A login token is also needed. See section 3. |
| Portal client code (`usePortalLayers`, field-data sources) | Read | See section 3. |

## 2. Input availability (Step 2: missing_input_exceptions)

| Required input | Needed for | Available? |
|---|---|---|
| `01.Krishi360_Chandrapur_PoC_plot_level_monitoring_Cleaned_v2(1).xlsx` | 37 headings, 87 records, everything in the workbook | **Missing**. This is the critical blocker. |
| `Krishi369.csv` (37 headings + UID) | 87-to-87 reconciliation, UID mapping, survey differences | **Missing** |
| `Merge.gdb.zip` | Plot polygons, UUID join, areas | **Missing**. It may be published on the portal; the portal inventory will show this. |
| B04 / B08 GeoTIFFs, 24 Oct 2026 plus the Sep/Oct scenes | Engine 1 NDVI | **Missing**. The portal NDVI appears to be classified (see 3), so it cannot replace these files. |
| Supplied NDVI GeoTIFF (continuous) | Step 12 comparison | **Missing** |
| SCL / cloud-probability rasters | Step 13 cloud masking | **Missing**. Without them `cloud_mask_applied = false`. |
| Earlier 86-record dataset | Step 8 explanation of the 86 count | **Missing**. It stays unresolved unless supplied. |
| Maharashtra village shapefile (SHP/SHX/DBF/PRJ...) | Reference geography and hashes | Only the derived GeoJSON is in the repo. The original sidecar files are on the Mac (`/Users/aj/Downloads/...`). |
| Web scene ID | Portal inventory | **Not provided** |

## 3. The portal: what the client code shows, and how to grant access

What the code shows:

- The web map mixes two states. `portalStateOf()` treats a title matching `ccmc|maharashtra|india ` as Maharashtra
  and everything else as Telangana. Layers inside a group inherit the group's state.
- Only the **CCMC / Maharashtra** layers are relevant to Chandrapur. The TGRAC layers (Chinnambavi mandal,
  Wanaparthy, Paddy 2021, Agri_Admin) are Telangana data. They must not populate any Chandrapur field, even
  though they carry crop, irrigation and soil attributes.
- `NDVI_CLASSES = ['Water','Bare soil','Sparse','Moderate','Dense']` indicates the portal NDVI rasters are **5-class
  classified products**, not continuous NDVI. If the inventory confirms this:
  - they cannot be the "supplied NDVI" in the Step 12 pixel comparison
  - they cannot replace B04/B08
  - they may be cited only as an imported, classified observation, with month, source and limitations recorded.
- Tokens come from your backend `/api/portal-tokens` as `[{server, token, expires}]`, one per server. That backend
  is also unreachable from this session.
- CCMC is a small area: the municipal polygon is about 6 km by 11 km. Any of the 87 plots outside it will have no
  CCMC layer coverage, and that must be checked.

How to grant access (choose one):

1. **This session reads the portal directly.** In the environment settings (cloud environment menu in the session's
   title bar, then Edit):
   - add `bmc3dmumbai.com` under Allowed domains, plus any other host the web map's services use
   - add a **read-only** token as the secret `ARCGIS_TOKEN`. Alternatively, set `ARCGIS_TOKENS_JSON` to the JSON your
     `/api/portal-tokens` returns.

   Do not paste credentials into the chat. A new session picks up the settings.
2. **You run the inventory on your own machine** (Python 3 only, no installs needed) and upload the output folder:

   ```bash
   ARCGIS_TOKEN=... python portal_inventory.py --portal https://bmc3dmumbai.com/portal --webmap bf308acdb69c432fab3e44c292fd077f --webscene WEBSCENE_ID --out portal_inventory_out
   ```

   The outputs contain no token. Every saved URL is redacted.

`portal_inventory.py` records, for every layer: the state rule, a CCMC flag, an NDVI month, the service type,
geometry type, CRS, extent and feature count. It also records fields, candidate UUID/survey fields and one sample
attribute row. For image services it records pixel type, bands, cell size, key properties and the raster attribute
table, plus a note on whether the raster is classified or continuous. It downloads no geometries or pixels.

## 4. Step-by-step procedure, mapped to the four deliverables

Run ID format: `RUN_20261101_R01`. All outputs go to `runs/RUN_ID/...` and `input/original` is never modified.

### Phase A: intake and setup (Steps 1 to 4)
1. Create the folder tree from Step 1 and `run_config.json` (lead, operators, reviewer, OS, reporting period, UTC).
2. Put every original into `input/original/`, then build `input_manifest.csv` (bytes, SHA256, role, read status)
   and `missing_input_exceptions.csv` (section 2 is the starting list).
3. Run `portal_inventory.py` (section 3). Record which CCMC layers exist and whether any of them holds the 87 plot
   polygons (look for a UUID field and feature count 87) or continuous NDVI.
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
14. `engines.py extract` and `inspect` on Merge.gdb, or the CCMC feature service if the plots are published
    there. Output: `layer_inventory.json`, run with `--keys-json client_keys.json`.
15. `plot_layer_selection.json`: layer, UUID field, normalisation rule, rationale.
16. `engines.py areas ... --target EPSG:32644`. UTM 44N fits: the district spans 78.80 to 79.99 E. Outputs:
    `plot_areas.json` (m², ha, acres) and `plot_geometry_QA.csv`. Invalid or duplicate geometries are withheld.
    A missing polygon is never recorded as zero.
17. Independent QGIS/ArcGIS area check: smallest, largest and suspect plots (`independent_GIS_checks.csv`).
    Also `area_comparison.csv` against the client survey area once its unit is confirmed, and
    `acquisition_coverage.csv` (footprint overlap and valid-data share per plot and date).
    Optional: a plot NDVI sheet, with pixel counts and valid fraction, labelled "not cloud screened".

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
| none | No end-to-end wrapper (S5). | Add `run_pipeline.py` with explicit paths, logs and nonzero exits on blocking failures. |

## 6. Decisions needed

- The deliverable name: the instructions say `..._Client_Excel_V0.xlsx`, while the request says V1.
- The named people for each role in the V2 responsibility matrix.
- Who supplies the missing originals in section 2, and from where.
