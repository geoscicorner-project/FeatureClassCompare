# FeatureClass Compare

**FeatureClass Compare** is a QGIS plugin for comparing one reference Feature Class with one target Feature Class. It supports File Geodatabases (`.gdb`) and Shapefiles (`.shp`), including compatible loaded GDB and Shapefile layers from the current QGIS project.

## What's new in 0.8.24

- Filter geometry results by status and sort table columns, including Status.
- Show not-matched Reference and Target features on separate rows; only confirmed pairs share a row.

## What's new in 0.8.23

- Identical bounding-box pairs (IoU = 1.00) are now represented directly in the main geometry results table.
- Vertex comparison status is shown in the main table; the separate pair-results table has been removed.
- Selecting a result row displays its Reference/Target FIDs, vertex counts, IoU, and comparison explanation in a detail panel.
- Pairs with different vertex counts are labeled `Different vertex count` only. Further analysis is intentionally deferred.

## Main capabilities

- Compare feature class/layer names, geometry types, feature counts, and field definitions.
- Match geometries using normalized WKT coordinate fingerprints and SHA-256.
- Compare unmatched features with identical bounding boxes using IoU = 1.00.
- For identical bounding-box pairs, compare vertex count, coordinate occurrences, and vertex order.
- Compare attributes for unique one-to-one geometry matches.
- Select reference and target field pairs manually and configure text comparison options.
- Export geometry summaries and unmatched records to CSV or Shapefile.
- Select compatible loaded File Geodatabase and Shapefile layers from the current QGIS project.

## Vertex comparison rules

- The duplicated closing vertex of a polygon ring is counted once.
- Repeated coordinates elsewhere remain separate vertex occurrences.
- Equal vertex counts and equal coordinate occurrences with the same order produce `Match`.
- Equal vertex counts and equal coordinate occurrences in a different order produce `Match with Different Vertex Order`.
- Equal vertex counts with different coordinate occurrences produce `Not matched`.
- Different vertex counts produce `Different vertex count`; no further matching is performed for these pairs in this release.

## Requirements

- QGIS **3.22 or later**.
- GDAL/OGR available in the QGIS Python environment.

## Installation

Extract the `FeatureClass_Compare` folder into the active QGIS profile's `python/plugins` directory, restart QGIS, then enable **FeatureClass Compare** from Plugin Manager.

## Notes

- The plugin reads source datasets and does not modify them.
- Attribute comparison remains limited to unique one-to-one geometry matches based on the existing hash comparison.
- Shapefile field names are limited to 10 characters; exported names may be shortened to comply.

## Maintainer

**GeosciCorner Project**  
Email: geoscicorner@gmail.com  
Repository: https://github.com/geoscicorner-project/FeatureClassCompare

## License

GNU General Public License v2.0 or (at your option) any later version.


### Geometry result statuses (0.8.25)

- `Match` and `Match with Different Vertex Order` are displayed as paired Reference/Target rows.
- `Different Vertex Count` remains a provisional paired status for later analysis.
- `Not matched` features are displayed independently. An identical bounding box (IoU = 1.00) is only a candidate search criterion; if vertex coordinates differ, the Reference and Target features are split into separate rows with counts 1/0 and 0/1 respectively.


## Geometry normalization (0.8.27)

Unique one-to-one geometry fingerprint matches and exact vertex-confirmed matches are both displayed as `Match`. For identical-bounding-box candidates with different raw vertex counts, the plugin performs a normalization pass that removes only intermediate vertices lying on straight segments, then compares the normalized vertex structures. Ring closure is counted once; repeated vertices elsewhere are retained unless they are redundant collinear points on a straight segment. Candidates that still have different normalized vertex counts remain `Different Vertex Count` for later review.


### Geometry matching in 0.8.27

For candidates with different vertex counts, redundant collinear intermediate vertices are normalized and exact GEOS topological equality (`ST_Equals` semantics) is then applied. No coordinate tolerance or snapping is used. Equal geometries are reported as `Match with Different Vertex Count`; unequal geometries are reported as separate Reference-only and Target-only `Not matched` rows. The matched summary includes `Match`, `Match with Different Vertex Order`, and `Match with Different Vertex Count`. Sorting is disabled for Reference and Target attribute columns; comparison-result columns remain sortable.


### Matched record export (0.8.34)
The geometry comparison window provides separate exports for the geometry summary, matched records, unmatched Reference records, and unmatched Target records. Matched records can be filtered by geometry status. Shapefile matched exports use Target geometry and include Reference and Target attributes, both source FIDs, and `MATCH_STATUS`. Attribute comparison also lets users select which matched geometry statuses to include. Geometry Summary is exported as CSV because it is a non-spatial summary.
