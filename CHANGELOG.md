# Changelog

All notable, documented changes are listed here. This release adds a source-selection option while preserving the existing GDAL/OGR comparison engine.

## 0.8.18

- Added **Loaded Layer (QGIS Map)** as a source option for Reference and Target.
- The loaded-layer list includes valid OGR-backed File Geodatabase and Shapefile layers in the current QGIS project.
- Added a **Refresh** action to reload project layers after the dialog is opened.
- Loaded layers are reopened read-only through GDAL/OGR; existing structure, field, geometry, attribute, and export workflows remain in place.
- Kept the existing File Geodatabase and Shapefile Browse workflows.
- Loaded Layer support is intentionally limited to GDB and Shapefile in this release; other providers are not included.

## 0.8.15

- Prepared the v0.8.15 distribution package with repository metadata, licensing, and refreshed documentation.
- The feature set is described in `FeatureClass_Compare/README.md`.

## 0.8.11

- Combined Shapefile export for paired features whose compared attributes differ.
- The export includes reference geometry, reference and target attributes (prefixed `R_` and `T_`), `REF_FID`, `TGT_FID`, `STATUS`, and `DIFF_ATTR`.
- Export is limited to one-to-one geometry pairs with differing compared attribute values. Shapefile field names are shortened and made unique to respect the 10-character limit.

## 0.8.3

- Corrected the grouped geometry-results header by separating the row-number gutter from the seven data columns.
- Synchronized header and body column indexes and widths when resized.

## 0.8.2

- Fixed grouped-header alignment by adding a matching row-number gutter.
- Header column widths follow the geometry result table's actual column widths.
- Enabled interactive column sizing.

## 0.8.1

- Added a two-tier grouped header for Reference, Target, and Comparing result.
- Added two selectable attribute fields per dataset by default.
- Applied match-status colors to the correct status column.

## 0.8.0

- Added a plugin icon for the QGIS toolbar, plugin list, and dialogs.
- Reduced default geometry preview fields and compacted table headers and action layout.
- Adjusted dialog sizing for common desktop screens.

## 0.7.0

- Replaced visible geometry fingerprints in geometry results with configurable reference and target attribute fields.
- Added clickable attribute headers to select fields or None.
- Kept fingerprints for internal matching and CSV summaries.
- Improved dialog sizing and horizontal scrolling.

## 0.6.0

- Updated the geometry action label to indicate attribute comparison as the next step for one-to-one geometry matches.
- Added an explanatory note and visual status cues in the geometry results.
