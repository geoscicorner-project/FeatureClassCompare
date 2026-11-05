# FeatureClass Compare

**FeatureClass Compare** is a QGIS plugin for comparing one reference Feature Class with one target Feature Class. It supports File Geodatabases (`.gdb`) and Shapefiles (`.shp`), including comparisons between different source formats. Version 0.8.18 also lets you select compatible GDB and Shapefile layers that are already loaded in the current QGIS project.

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
- Select an already-loaded File Geodatabase or Shapefile layer from the current QGIS project independently for Reference and Target.

## Selecting data sources

Each side (Reference and Target) can be configured independently using one of three source modes:

1. **File Geodatabase (.gdb)** — browse to a `.gdb` folder, then select a Feature Class.
2. **Shapefile (.shp)** — browse to a `.shp` file.
3. **Loaded Layer (QGIS Map)** — select a compatible File Geodatabase or Shapefile layer that is already loaded in the current QGIS project. The **Refresh** button reloads the list after layers are added or removed.

The Loaded Layer mode in this release is intentionally limited to OGR-backed File Geodatabase and Shapefile layers. Other providers and temporary/non-file layers are not included. The selected project layer is reopened read-only through GDAL/OGR, so the existing comparison and export engine remains in use. The source dataset is not modified.

## Requirements

- QGIS **3.22 or later**.
- GDAL/OGR available in the QGIS Python environment. This is normally included with standard QGIS installations.

## Installation

### From the QGIS Plugin Repository

When the plugin is approved and published, open **Plugins → Manage and Install Plugins**, search for **FeatureClass Compare**, and install it.

### Manual installation

1. Download the QGIS plugin ZIP from the repository's Releases page. For testing, use the GitHub source ZIP only after extracting it and ensuring the plugin folder is named `FeatureClass_Compare`.
2. Extract the `FeatureClass_Compare` folder into the active QGIS profile's `python/plugins` directory.
3. Restart QGIS, or refresh the plugin list if appropriate.
4. Enable **FeatureClass Compare** in **Plugins → Manage and Install Plugins → Installed**.

## Notes and limitations

- Loaded Layer mode currently supports only valid OGR-backed File Geodatabase and Shapefile layers. GeoPackage, PostGIS, Memory Layer, Virtual Layer, and other providers are outside the scope of this release; broader provider support is a possible future enhancement.
- A loaded layer must still point to an accessible source on disk. The plugin reopens that source through GDAL/OGR in read-only mode.
- Attribute comparison is performed only for unique one-to-one geometry matches. Duplicate geometry fingerprints are not treated as unambiguous pairs for attribute comparison.
- Shapefile field names are limited to 10 characters. Exported field names may therefore be shortened and made unique to comply with the format.
- Geometry fingerprints are based on geometry representations. Differences in vertex order or representation may affect whether two geometries are considered identical; use the comparison results as a data-quality aid and review important cases in GIS.
- The plugin compares the selected reference and target layers; it does not modify the source datasets during comparison.

## Compatibility and testing

The declared minimum version is QGIS 3.22. The updated Python file has been checked for Python syntax. A complete runtime test still needs to be performed in QGIS, including loaded GDB and Shapefile layers, direct Browse selections, mixed source modes, empty layers, duplicate geometries, and each export option. Please report reproducible issues through the GitHub issue tracker.

## License

This project is licensed under **GNU General Public License v2.0 or (at your option) any later version**. See [`LICENSE`](LICENSE).

## Maintainer

**GeosciCorner Project**  
Email: geoscicorner@gmail.com  
Repository: https://github.com/geoscicorner-project/FeatureClassCompare
