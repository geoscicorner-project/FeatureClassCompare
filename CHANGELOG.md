## 0.8.34
- Fixed the missing `QProgressDialog` import that caused an error when starting Compare Attributes for Matched Geometries.
- Removed file extensions from default filenames in Save As dialogs; the selected file type determines the extension.

## 0.8.33
- ESRI Shapefile is now the default format in record export Save As dialogs; CSV remains available.
- Added a cancellable progress dialog with processed-pair counts for matched-geometry attribute comparison.

# Changelog

## 0.8.32
- Reorganized geometry-result exports into four actions: Geometry Summary, Match Record, Not Matched Reference Record, and Not Matched Target Record.
- Added CSV/Shapefile format selection for spatial record exports; Geometry Summary remains CSV because it is a non-spatial summary table.
- Added independent status selection for matched-record export: Match, Match with Different Vertex Order, and Match with Different Vertex Count.
- Matched exports use Target geometry and include both Reference and Target attributes plus `MATCH_STATUS`; Reference and Target FIDs are included.
- Added the same three independently selectable geometry-match categories before Compare Attributes runs.
- Refined grouped-header border and padding styling without changing the results table structure or column layout.


## 0.8.30
- Rebuilt the grouped header as four aligned sections: an empty row-number gutter, Reference, Target, and Comparing result.
- Synchronized each header section width with the corresponding table columns.
- Restored click-to-select field menus for all six Reference and Target attribute columns.
- Restricted sorting to the Status column; Reference/Target attribute columns and count columns do not trigger sorting.
- Preserved status filtering and the filtering/rendering progress indicators.

## 0.8.29
- Increased the size and weight of the grouped `Reference`, `Target`, and `Comparing result` headers.
- Extended the `Reference` group header to the table's left outer edge by incorporating the row-number gutter, while keeping the other group headers aligned with their columns.
- Added a dedicated filtering progress indicator with percentage and processed-row counts.
- Kept the existing result-rendering progress indicator and status filtering behavior.

## 0.8.28
- Added a dedicated `Displaying Results` progress stage (Stage 6/6) while rows are populated in the geometry results table.
- Updated the plugin status label and progress bar during table rendering so users can see the number of displayed rows and percentage completed.
- Processes Qt events during rendering to keep the interface responsive and visibly update the progress indicator.


## 0.8.27
- Added exact GEOS topological equality (`ST_Equals` semantics) for candidate pairs with different vertex counts after redundant collinear-vertex normalization.
- Different-count candidates that fail topological equality are now represented as two independent `Not matched` records.
- Added the `Match with Different Vertex Count` status and included it in matched totals.
- Updated summary counts to include all three matched statuses and count unmatched features separately by source.
- Disabled sorting for Reference and Target attribute columns while retaining sorting on comparison-result columns and status filtering.


## 0.8.26

- Unified unique 1-to-1 geometry fingerprint matches and exact vertex-confirmed matches under the single status `Match`.
- Removed `Match (1-to-1)` from the status filter to avoid exposing the internal matching method as a separate result category.
- Added normalization for `Different Vertex Count` candidates: intermediate vertices that lie on a straight segment are removed before the candidate geometries are compared again.
- Preserved line endpoints, polygon ring shape, repeated non-redundant vertices, and ring closure counting (the closing coordinate is counted only once).
- Updated the selected-pair detail panel to show original and normalized vertex counts.
- Candidates that still differ after normalization retain `Different Vertex Count`; coordinate differences remain `Not matched`.

## 0.8.25

- Kept `Not matched` as the status for features whose vertex coordinates do not match, even when their bounding boxes are identical.
- Split failed vertex-comparison candidates into two independent rows: Reference only (`Ref count = 1`, `Tgt count = 0`) and Target only (`Ref count = 0`, `Tgt count = 1`).
- Bounding-box IoU is treated only as a candidate-pair discovery step, not proof of geometry equality.
- Updated the status filter and user-facing summaries to use `Not matched`.
- Retained `Different Vertex Count` as a provisional paired status for later analysis.

## 0.8.24

- Added a status filter to the geometry results table.
- Enabled sorting in the results table, including the Status column.
- Displayed every unmatched Reference and Target feature as its own independent row instead of grouping unrelated records.
- Kept confirmed pairs together in one row, including exact hash matches and identical-bounding-box vertex comparison pairs.
- Standardized the status label to `Different Vertex Count`.


## 0.8.23

- Removed the separate identical-bounding-box vertex comparison table.
- Integrated IoU-identical Reference/Target pairs into the main geometry results table.
- Updated the main-row status with the vertex comparison result: `Match`, `Match with Different Vertex Order`, `Different vertex count`, or `Unmatched`.
- Added a selected-row detail panel showing Reference/Target FIDs, vertex counts, IoU, and the comparison status.
- Kept different-vertex-count pairs as a status only; no additional matching logic is applied to them.
- Preserved the existing hash comparison, IoU = 1.00 matching, attribute comparison workflow, exports, source selection, and original plugin icons.

## 0.8.22

- Added vertex-count, vertex-value, and vertex-order checks for identical unmatched bounding-box pairs (IoU = 1.00).

## 0.8.21

- Added exact bounding-box matching using IoU = 1.00 for unmatched features.

## 0.8.20

- Added in-memory unmatched bounding-box preparation and staged progress reporting.
- Renamed the first progress stage to `Reading Geometry`.

## 0.8.31
- Corrected the grouped header row-number gutter sizing so the blank first header cell aligns with the table row-number area.
- Restored explicit Status-only sorting; attribute field headers remain dedicated to field selection, and count columns remain non-sortable.
- Kept Reference and Target field-selection menus available from their respective attribute headers.
