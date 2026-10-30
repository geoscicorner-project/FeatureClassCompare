# FeatureClass Compare

**FeatureClass Compare** is a QGIS plugin for comparing one reference Feature Class with one target Feature Class. It supports File Geodatabases (`.gdb`) and Shapefiles (`.shp`), including comparisons between different source formats.

## Capabilities

- Compare feature class/layer names and geometry types.
- Compare feature counts and field definitions, including field names, data types, and lengths.
- Match geometries using SHA-256 fingerprints of geometry representations.
- Compare attributes only for geometry matches that occur exactly once in each dataset (one-to-one matches).
- Select reference and target field pairs manually, including fields with different names.
- Configure text comparison to preserve or ignore letter case and leading/trailing spaces.
- Review comparison summaries and per-record attribute differences.
- Export geometry comparison summaries and unmatched records to CSV.
- Export unmatched reference or target features to separate Shapefiles.
- Export paired features with differing compared attributes to a combined Shapefile containing reference and target attributes, pair identifiers, status, and difference details.

## Requirements

- QGIS **3.22 or later**.
- GDAL/OGR available in the QGIS Python environment. This is normally included with standard QGIS installations.

## Installation

### From the QGIS Plugin Repository

When the plugin is approved and published, open **Plugins → Manage and Install Plugins**, search for **FeatureClass Compare**, and install it.

### Manual installation

1. Download the QGIS plugin ZIP from the repository's Releases page (or use the separately prepared QGIS upload ZIP).
2. Extract the `FeatureClass_Compare` folder into the active QGIS profile's `python/plugins` directory.
3. Restart QGIS, or refresh the plugin list if appropriate.
4. Enable **FeatureClass Compare** in **Plugins → Manage and Install Plugins → Installed**.

## Notes and limitations

- Attribute comparison is performed only for unique one-to-one geometry matches. Duplicate geometry fingerprints are not treated as unambiguous pairs for attribute comparison.
- Shapefile field names are limited to 10 characters. Exported field names may therefore be shortened and made unique to comply with the format.
- Geometry fingerprints are based on geometry representations. Differences in vertex order or representation may affect whether two geometries are considered identical; use the comparison results as a data-quality aid and review important cases in GIS.
- The plugin compares the selected reference and target layers; it does not modify the source datasets during comparison.

## Compatibility and testing

The declared minimum version is QGIS 3.22. The package has been checked for Python syntax and expected plugin package structure. A complete runtime test still needs to be performed in QGIS, including representative File Geodatabase and Shapefile datasets, mixed-format comparisons, empty layers, duplicate geometries, and each export option. Please report reproducible issues through the GitHub issue tracker.

## License

This project is licensed under **GNU General Public License v2.0 or (at your option) any later version**. See [`LICENSE`](LICENSE).

## Maintainer

**GeosciCorner Project**  
Email: geoscicorner@gmail.com  
Repository: https://github.com/geoscicorner-project/FeatureClassCompare
