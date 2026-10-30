# -*- coding: utf-8 -*-
"""FeatureClass Compare: compare one reference feature class with one target feature class.

Supports File Geodatabase (.gdb) and Shapefile (.shp), including mixed-format pairs.
Designed for QGIS Python environment (PyQGIS + GDAL/OGR).
"""

import os
import csv
import hashlib
import traceback
from collections import defaultdict

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QColor, QBrush, QIcon
from qgis.PyQt.QtWidgets import (
    QApplication, QAction, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QMenu,
    QHeaderView, QComboBox, QProgressBar, QGroupBox, QFormLayout,
    QAbstractItemView, QSplitter, QCheckBox, QWidget
)
from osgeo import gdal, ogr


class FeatureClassCompareDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FeatureClass Compare — Feature Class Comparison")
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "icon.svg")))
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        desired_width, desired_height = 1120, 760
        if available:
            desired_width = min(desired_width, max(760, available.width() - 40))
            desired_height = min(desired_height, max(520, available.height() - 70))
        self.resize(desired_width, desired_height)
        if available:
            self.setMaximumSize(available.width(), available.height())
            self.move(available.x() + max(0, (available.width() - desired_width) // 2),
                      available.y() + max(0, (available.height() - desired_height) // 2))
        self.sources = {
            "ref": {"path": "", "layers": []},
            "target": {"path": "", "layers": []},
        }
        self.summary_results = []
        self.detail_results = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("FeatureClass Compare — Feature Class Comparison")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        root.addWidget(title)
        info = QLabel(
            "Compare one reference Feature Class with one target Feature Class. "
            "Sources can be a File Geodatabase (.gdb) or Shapefile (.shp), including mixed-format pairs. "
            "Field names are matched case-insensitively; ambiguous names are not paired automatically."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        source_group = QGroupBox("Data Sources")
        form = QFormLayout(source_group)
        self.source_widgets = {}
        for key, label in (("ref", "Reference"), ("target", "Target")):
            row = QHBoxLayout()
            kind = QComboBox()
            kind.addItem("File Geodatabase (.gdb)", "gdb")
            kind.addItem("Shapefile (.shp)", "shp")
            path = QLineEdit()
            path.setReadOnly(True)
            path.setPlaceholderText("Select a data source...")
            browse = QPushButton("Browse...")
            browse.clicked.connect(lambda checked=False, k=key: self._browse_source(k))
            row.addWidget(kind)
            row.addWidget(path, 1)
            row.addWidget(browse)
            layer_combo = QComboBox()
            layer_combo.setEnabled(False)
            kind.currentIndexChanged.connect(lambda index, k=key: self._source_kind_changed(k))
            layer_combo.currentIndexChanged.connect(lambda index, k=key: self._selection_changed())
            form.addRow(label + " — format/location:", row)
            form.addRow(label + " — Feature Class:", layer_combo)
            self.source_widgets[key] = {"kind": kind, "path": path, "browse": browse, "layer": layer_combo}
        root.addWidget(source_group)

        controls = QHBoxLayout()
        self.compare_btn = QPushButton("Compare Structure and Fields")
        self.compare_btn.setEnabled(False)
        self.compare_btn.setObjectName("primaryCompareButton")
        self.compare_btn.setMinimumHeight(34)
        self.compare_btn.setStyleSheet(
            "QPushButton#primaryCompareButton {"
            " background-color: #1769AA; color: white; font-weight: bold;"
            " border: 1px solid #0F568F; border-radius: 4px; padding: 6px 12px;"
            "}"
            "QPushButton#primaryCompareButton:hover { background-color: #0F568F; }"
            "QPushButton#primaryCompareButton:disabled {"
            " background-color: #B8C8D6; color: #F5F7F9; border-color: #B8C8D6;"
            "}"
        )
        self.compare_btn.clicked.connect(self.compare)
        controls.addWidget(self.compare_btn)
        self.geometry_btn = QPushButton("Compare Geometry → Attributes")
        self.geometry_btn.setToolTip(
            "First match records by geometry. The results window then lets you compare "
            "attributes for geometry matches that occur exactly once in both datasets (1-to-1)."
        )
        self.geometry_btn.setEnabled(False)
        self.geometry_btn.setObjectName("geometryCompareButton")
        self.geometry_btn.setMinimumHeight(34)
        self.geometry_btn.setStyleSheet(
            "QPushButton#geometryCompareButton {"
            " background-color: #087F8C; color: white; font-weight: bold;"
            " border: 1px solid #066873; border-radius: 4px; padding: 6px 12px;"
            "}"
            "QPushButton#geometryCompareButton:hover { background-color: #066873; }"
            "QPushButton#geometryCompareButton:disabled {"
            " background-color: #B8D1D3; color: #F5F7F9; border-color: #B8D1D3;"
            "}"
        )
        self.geometry_btn.setToolTip("Run geometry matching separately from structure and field checks.")
        self.geometry_btn.clicked.connect(self.compare_geometry_hashes)
        controls.addWidget(self.geometry_btn)
        self.export_btn = QPushButton("Export CSV...")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_csv)
        controls.addWidget(self.export_btn)
        controls.addStretch()
        controls.addWidget(QLabel("Summary filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All", "Different", "Match", "Needs attention"])
        self.filter_combo.currentIndexChanged.connect(self._render_summary)
        controls.addWidget(self.filter_combo)
        root.addLayout(controls)

        self.status_label = QLabel("Select a reference and target data source and Feature Class.")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        splitter = QSplitter(Qt.Vertical)
        summary_group = QGroupBox("Check summary — select a row to view details")
        summary_layout = QVBoxLayout(summary_group)
        self.summary_table = QTableWidget(0, 5)
        self.summary_table.setHorizontalHeaderLabels(["Check", "Reference", "Target", "Status", "Findings"])
        self._configure_table(self.summary_table)
        summary_header = self.summary_table.horizontalHeader()
        summary_header.setSectionResizeMode(QHeaderView.Interactive)
        summary_header.setStretchLastSection(False)
        # Descriptive/source columns use the available width; Findings is compact.
        summary_header.setSectionResizeMode(0, QHeaderView.Stretch)
        summary_header.setSectionResizeMode(1, QHeaderView.Stretch)
        summary_header.setSectionResizeMode(2, QHeaderView.Stretch)
        summary_header.setSectionResizeMode(3, QHeaderView.Interactive)
        summary_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.summary_table.setColumnWidth(0, 220)
        self.summary_table.setColumnWidth(1, 190)
        self.summary_table.setColumnWidth(2, 190)
        self.summary_table.setColumnWidth(3, 170)
        self.summary_table.setColumnWidth(4, 78)
        summary_header.setStyleSheet(
            "QHeaderView::section { padding: 5px; font-weight: bold; }"
        )
        for col, color, text_color in (
            (1, "#DCEBDD", "#285B35"),
            (2, "#DCE7F7", "#254F87"),
        ):
            header_item = self.summary_table.horizontalHeaderItem(col)
            if header_item is not None:
                header_item.setBackground(QBrush(QColor(color)))
                header_item.setForeground(QBrush(QColor(text_color)))
        self.summary_table.itemSelectionChanged.connect(self._show_selected_detail)
        summary_layout.addWidget(self.summary_table)
        splitter.addWidget(summary_group)

        detail_group = QGroupBox("Difference details")
        detail_layout = QVBoxLayout(detail_group)
        self.detail_table = QTableWidget(0, 7)
        self.detail_table.setHorizontalHeaderLabels(["Reference field", "Reference type", "Reference length", "Target field", "Target type", "Target length", "Result"])
        self.detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.detail_table.setColumnWidth(0, 145)
        self.detail_table.setColumnWidth(1, 155)
        self.detail_table.setColumnWidth(2, 105)
        self.detail_table.setColumnWidth(3, 145)
        self.detail_table.setColumnWidth(4, 155)
        self.detail_table.setColumnWidth(5, 105)
        self.detail_table.setColumnWidth(6, 150)
        self._configure_table(self.detail_table)
        detail_layout.addWidget(self.detail_table)
        splitter.addWidget(detail_group)
        splitter.setSizes([260, 340])
        root.addWidget(splitter, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

    @staticmethod
    def _configure_table(table):
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)

    def _source_kind_changed(self, key):
        # Changing the source format invalidates the previously selected source.
        self.sources[key] = {"path": "", "layers": []}
        widgets = self.source_widgets[key]
        widgets["path"].clear()
        widgets["layer"].clear()
        widgets["layer"].setEnabled(False)
        self._selection_changed()

    def _browse_source(self, key):
        widgets = self.source_widgets[key]
        kind = widgets["kind"].currentData()
        if kind == "gdb":
            path = QFileDialog.getExistingDirectory(self, "Select File Geodatabase (.gdb)")
            if not path:
                return
            if not path.lower().endswith(".gdb") or not os.path.isdir(path):
                QMessageBox.warning(self, "Invalid source", "Select a File Geodatabase folder ending in .gdb.")
                return
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select Shapefile", "", "Shapefile (*.shp)")
            if not path:
                return
            if not path.lower().endswith(".shp") or not os.path.isfile(path):
                QMessageBox.warning(self, "Invalid source", "Select a file with the .shp extension.")
                return

        try:
            layers = self._list_layers(path, kind)
            if not layers:
                QMessageBox.warning(self, "No Feature Class found", "The source can be opened, but no vector layer was found.")
                return
            self.sources[key] = {"path": os.path.normpath(path), "layers": layers}
            widgets["path"].setText(os.path.normpath(path))
            combo = widgets["layer"]
            combo.blockSignals(True)
            combo.clear()
            for layer in layers:
                combo.addItem(layer["name"], layer["index"])
            combo.blockSignals(False)
            combo.setEnabled(True)
            self.status_label.setText("Successfully read {} source. Select a Feature Class on both sides.".format("reference" if key == "ref" else "target"))
        except Exception as exc:
            QMessageBox.critical(self, "Failed to read source", "{}\n\n{}".format(exc, traceback.format_exc()))
        self._selection_changed()

    @staticmethod
    def _list_layers(path, kind):
        flags = gdal.OF_VECTOR | gdal.OF_READONLY
        ds = gdal.OpenEx(path, flags)
        if ds is None:
            raise RuntimeError("GDAL/OGR could not open source: {}".format(path))
        layers = []
        try:
            for index in range(ds.GetLayerCount()):
                layer = ds.GetLayerByIndex(index)
                if layer is None:
                    continue
                name = layer.GetName()
                layers.append({"index": index, "name": name})
        finally:
            ds = None
        # For a shapefile, the driver should expose one layer. Keep the same list format.
        return layers

    def _selection_changed(self):
        ready = True
        for key in ("ref", "target"):
            w = self.source_widgets[key]
            if not self.sources[key]["path"] or w["layer"].currentIndex() < 0:
                ready = False
        self.compare_btn.setEnabled(ready)
        self.geometry_btn.setEnabled(ready)

    def _open_selected_layer(self, key):
        source = self.sources[key]
        widget = self.source_widgets[key]
        if not source["path"] or widget["layer"].currentIndex() < 0:
            raise RuntimeError("A source or Feature Class has not been selected.")
        index = widget["layer"].currentData()
        ds = gdal.OpenEx(source["path"], gdal.OF_VECTOR | gdal.OF_READONLY)
        if ds is None:
            raise RuntimeError("Could not open source: {}".format(source["path"]))
        layer = ds.GetLayerByIndex(int(index))
        if layer is None:
            ds = None
            raise RuntimeError("Could not read Feature Class at index {}.".format(index))
        # Return the dataset as well so the OGR layer stays valid during inspection.
        return ds, layer

    @staticmethod
    def _geometry_name(layer):
        try:
            return ogr.GeometryTypeToName(ogr.GT_Flatten(layer.GetGeomType()))
        except Exception:
            return str(layer.GetGeomType())

    @staticmethod
    def _fields(layer):
        definition = layer.GetLayerDefn()
        fields = []
        for i in range(definition.GetFieldCount()):
            field = definition.GetFieldDefn(i)
            try:
                type_name = field.GetTypeName()
            except Exception:
                type_name = ogr.GetFieldTypeName(field.GetType())
            fields.append({
                "name": field.GetName(),
                "key": field.GetName().casefold(),
                "type": type_name or "Unknown",
                "type_code": field.GetType(),
                "width": int(field.GetWidth() or 0),
                "precision": int(field.GetPrecision() or 0),
            })
        return fields

    @staticmethod
    def _type_category(field):
        """Normalize common OGR field types to compare semantic categories."""
        name = (field.get("type") or "").lower()
        code = field.get("type_code")

        # Optional OGR constants are looked up safely for GDAL-version
        # compatibility. Unexpected exceptions are no longer swallowed.
        type_categories = {}

        for constant_name in ("OFTInteger", "OFTInteger64"):
            value = getattr(ogr, constant_name, None)
            if value is not None:
                type_categories[value] = "Integer"

        for constant_name, category in (
            ("OFTReal", "Real"),
            ("OFTString", "String"),
            ("OFTWideString", "String"),
            ("OFTDate", "Date"),
            ("OFTTime", "Time"),
            ("OFTDateTime", "DateTime"),
            ("OFTBinary", "Binary"),
            ("OFTIntegerList", "IntegerList"),
            ("OFTInteger64List", "IntegerList"),
            ("OFTRealList", "RealList"),
            ("OFTStringList", "StringList"),
            ("OFTWideStringList", "StringList"),
        ):
            value = getattr(ogr, constant_name, None)
            if value is not None:
                type_categories[value] = category

        return type_categories.get(code, name or "Unknown")

    @staticmethod
    def _ambiguities(fields):
        by_key = defaultdict(list)
        for field in fields:
            by_key[field["key"]].append(field)
        return {key: values for key, values in by_key.items() if len(values) > 1}

    def compare(self):
        if not self.compare_btn.isEnabled():
            QMessageBox.warning(self, "Incomplete selection", "Select the source and Feature Class for both reference and target.")
            return
        self.compare_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.progress.setValue(10)
        self.status_label.setText("Reading Feature Class definitions...")
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.processEvents()
        try:
            ds_ref, layer_ref = self._open_selected_layer("ref")
            self.progress.setValue(35)
            ds_target, layer_target = self._open_selected_layer("target")
            self.progress.setValue(55)

            ref_name = layer_ref.GetName()
            target_name = layer_target.GetName()
            ref_geom = self._geometry_name(layer_ref)
            target_geom = self._geometry_name(layer_target)
            ref_fields = self._fields(layer_ref)
            target_fields = self._fields(layer_target)
            self.summary_results = []
            self.detail_results = []

            name_status = self._name_status(ref_name, target_name)
            geom_status = "Match" if ref_geom.casefold() == target_geom.casefold() else "Different"
            self._add_summary("Feature Class Name", ref_name, target_name, name_status, 0)
            self._add_detail("Feature Class Name", ref_name, "—", "Feature Class Name", target_name, "—",
                             name_status, "Object names are compared exactly; capitalization differences are reported.", category="Feature Class Name")
            self._add_summary("Geometry Type", ref_geom, target_geom, geom_status, 0)
            self._add_detail("Geometry Type", ref_geom, "—", "Geometry Type", target_geom, "—",
                             geom_status, "Geometry type reported by GDAL/OGR.", category="Geometry Type")

            # Count records/features in each selected layer. Some drivers may return -1
            # when the count cannot be determined.
            ref_count = layer_ref.GetFeatureCount()
            target_count = layer_target.GetFeatureCount()
            ref_count_text = str(ref_count) if ref_count >= 0 else "Unavailable"
            target_count_text = str(target_count) if target_count >= 0 else "Unavailable"
            if ref_count < 0 or target_count < 0:
                count_status = "Unavailable"
                count_note = "GDAL/OGR could not provide the feature count for at least one layer."
            else:
                count_status = "Match" if ref_count == target_count else "Different"
                count_note = "Feature count in each layer."
            self._add_summary("Feature Count", ref_count_text, target_count_text,
                              count_status, 0 if count_status == "Match" else 1)
            self._add_detail("Feature Count", ref_count_text, "—",
                             "Feature Count", target_count_text, "—",
                             count_status, count_note, category="Feature Count")

            self._compare_fields(ref_fields, target_fields)

            ds_ref = None
            ds_target = None
            self.progress.setValue(100)
            self._render_summary()
            different = sum(1 for r in self.summary_results if r["status"] != "Match")
            self.status_label.setText(
                "Complete: {} summary checks, {} different/attention-needed, {} field details."
                .format(len(self.summary_results), different, len(self.detail_results))
            )
            self.export_btn.setEnabled(True)
        except Exception as exc:
            self.progress.setValue(0)
            QMessageBox.critical(self, "Comparison failed", "{}\n\n{}".format(exc, traceback.format_exc()))
            self.status_label.setText("Check failed.")
        finally:
            self._selection_changed()

    @staticmethod
    def _geometry_hash_counts(layer, progress_callback=None):
        """Return hash counts plus per-record attributes for raw geometry WKB."""
        counts = defaultdict(int)
        records = []
        null_or_empty = 0
        failed = 0
        total = 0
        field_names = [layer.GetLayerDefn().GetFieldDefn(i).GetName()
                       for i in range(layer.GetLayerDefn().GetFieldCount())]
        layer.ResetReading()
        feature = layer.GetNextFeature()
        while feature is not None:
            total += 1
            fid = feature.GetFID()
            attrs = {"FID": fid}
            for name in field_names:
                try:
                    attrs[name] = feature.GetField(name)
                except Exception:
                    attrs[name] = None
            digest = None
            geometry_wkb = None
            record_status = "OK"
            try:
                geom = feature.GetGeometryRef()
                if geom is None or geom.IsEmpty():
                    null_or_empty += 1
                    record_status = "Empty geometry"
                else:
                    # Raw WKB only; no geometry normalization.
                    wkb = geom.ExportToWkb(ogr.wkbNDR)
                    geometry_wkb = bytes(wkb)
                    digest = hashlib.sha256(bytearray(wkb)).hexdigest()
                    counts[digest] += 1
            except Exception:
                failed += 1
                record_status = "Extraction failed"
            records.append({"hash": digest, "attrs": attrs, "record_status": record_status,
                            "geometry_wkb": geometry_wkb})
            feature = None
            if progress_callback and total % 1000 == 0:
                progress_callback(total)
            feature = layer.GetNextFeature()
        layer.ResetReading()
        return counts, total, null_or_empty, failed, records, field_names

    def compare_geometry_hashes(self):
        """Run geometry SHA-256 comparison independently of structure comparison."""
        if not self.geometry_btn.isEnabled():
            QMessageBox.warning(self, "Incomplete selection",
                                "Select reference and target sources and Feature Classes first.")
            return
        from qgis.PyQt.QtWidgets import QApplication
        self.geometry_btn.setEnabled(False)
        self.status_label.setText("Checking geometry. This runs separately from structure and field checks...")
        self.progress.setValue(0)
        QApplication.processEvents()
        ds_ref = ds_target = None
        try:
            ds_ref, layer_ref = self._open_selected_layer("ref")
            ds_target, layer_target = self._open_selected_layer("target")

            def update_ref(n):
                self.status_label.setText("Checking reference geometry: {} features processed...".format(n))
                QApplication.processEvents()

            ref_counts, ref_total, ref_empty, ref_failed, ref_records, ref_fields = self._geometry_hash_counts(layer_ref, update_ref)
            self.progress.setValue(45)
            self.status_label.setText("Checking target geometry...")
            QApplication.processEvents()

            def update_target(n):
                self.status_label.setText("Checking target geometry: {} features processed...".format(n))
                QApplication.processEvents()

            target_counts, target_total, target_empty, target_failed, target_records, target_fields = self._geometry_hash_counts(layer_target, update_target)
            self.progress.setValue(80)

            all_hashes = sorted(set(ref_counts) | set(target_counts))
            rows = []
            match_11 = 0
            for digest in all_hashes:
                rc = ref_counts.get(digest, 0)
                tc = target_counts.get(digest, 0)
                status = "Match (1-to-1)" if rc == 1 and tc == 1 else "Not matched"
                if rc == 1 and tc == 1:
                    match_11 += 1
                rows.append((digest, rc, tc, status))

            matched_hashes = {digest for digest in all_hashes
                              if ref_counts.get(digest, 0) == 1 and target_counts.get(digest, 0) == 1}
            ref_unmatched = [r for r in ref_records
                             if r["hash"] is None or r["hash"] not in matched_hashes]
            target_unmatched = [r for r in target_records
                                if r["hash"] is None or r["hash"] not in matched_hashes]
            ref_match_records = sum(1 for r in ref_records if r["hash"] in matched_hashes)
            target_match_records = sum(1 for r in target_records if r["hash"] in matched_hashes)
            ref_nonmatch_records = ref_total - ref_match_records
            target_nonmatch_records = target_total - target_match_records
            ref_match_pct = (100.0 * ref_match_records / ref_total) if ref_total else 0.0
            ref_nonmatch_pct = (100.0 * ref_nonmatch_records / ref_total) if ref_total else 0.0
            target_match_pct = (100.0 * target_match_records / target_total) if target_total else 0.0
            target_nonmatch_pct = (100.0 * target_nonmatch_records / target_total) if target_total else 0.0

            dialog = QDialog(self)
            dialog.setWindowTitle("Compare Geometry")
            dialog.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "icon.svg")))
            screen = dialog.screen() or QApplication.primaryScreen()
            available = screen.availableGeometry() if screen else None
            desired_width = 1180
            desired_height = 760
            if available:
                desired_width = min(desired_width, max(760, available.width() - 40))
                desired_height = min(desired_height, max(480, available.height() - 70))
            dialog.resize(desired_width, desired_height)
            if available:
                dialog.setMaximumSize(available.width(), available.height())
                dialog.move(available.x() + max(0, (available.width() - desired_width) // 2),
                            available.y() + max(0, (available.height() - desired_height) // 2))
            layout = QVBoxLayout(dialog)
            summary = QLabel(
                "Reference: {} features ({} unique geometries) | Target: {} features ({} unique geometries)\\n"
                "1-to-1 geometry matches: {}\\n"
                "Empty geometries: reference {}, target {} | Extraction failures: reference {}, target {}"
                .format(ref_total, len(ref_counts), target_total, len(target_counts), match_11,
                        ref_empty, target_empty, ref_failed, target_failed)
            )
            summary.setWordWrap(True)
            layout.addWidget(summary)

            next_step = QLabel(
                "Next step: click “Compare Attributes for Matched Geometries...” to compare "
                "selected attribute fields for records whose geometry matches 1-to-1."
            )
            next_step.setWordWrap(True)
            next_step.setStyleSheet(
                "QLabel { background-color: #EAF3FF; color: #174A7E; "
                "border: 1px solid #B8D5F5; border-radius: 4px; padding: 7px; }"
            )
            layout.addWidget(next_step)

            def add_percent_bar(title_text, matched, unmatched, matched_pct, unmatched_pct):
                label = QLabel("{} — ✓ Match: {} ({:.2f}%) | ✗ Unmatched: {} ({:.2f}%)".format(
                    title_text, matched, matched_pct, unmatched, unmatched_pct))
                layout.addWidget(label)
                bar = QProgressBar()
                bar.setRange(0, 1000)
                bar.setValue(int(round(matched_pct * 10)))
                bar.setFormat("Match %p%")
                bar.setToolTip("✓ Match {:.2f}% | ✗ Unmatched {:.2f}%".format(matched_pct, unmatched_pct))
                layout.addWidget(bar)

            add_percent_bar("Reference data", ref_match_records, ref_nonmatch_records,
                            ref_match_pct, ref_nonmatch_pct)
            add_percent_bar("Target data", target_match_records, target_nonmatch_records,
                            target_match_pct, target_nonmatch_pct)
            # Show user-selected attribute previews instead of long geometry fingerprints.
            # Keep the fingerprints internally for matching and CSV export.
            ref_by_hash = {}
            target_by_hash = {}
            for record in ref_records:
                if record["hash"] is not None:
                    ref_by_hash.setdefault(record["hash"], record)
            for record in target_records:
                if record["hash"] is not None:
                    target_by_hash.setdefault(record["hash"], record)

            default_ref_fields = list(ref_fields[:3])
            default_target_fields = list(target_fields[:3])
            default_ref_fields += [None] * (3 - len(default_ref_fields))
            default_target_fields += [None] * (3 - len(default_target_fields))
            shown_ref_fields = default_ref_fields[:]
            shown_target_fields = default_target_fields[:]

            # Use the body table's own horizontal header for the nine field/result
            # columns. This guarantees that header sections and body cells share the
            # exact same Qt section geometry (unlike two independently sized tables).
            table = QTableWidget(0, 9)
            self._configure_table(table)
            table.horizontalHeader().setVisible(True)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.horizontalHeader().setStretchLastSection(False)
            table.setRowCount(len(rows))

            # A single grouped-label strip sits above the real table header.
            # Its three labels are sized from the live body-header section widths.
            header_container = QWidget()
            header_layout = QHBoxLayout(header_container)
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(0)

            header_gutter = QWidget()
            header_gutter.setFixedWidth(
                table.frameWidth() + table.verticalHeader().sizeHint().width()
            )
            header_layout.addWidget(header_gutter)

            group_labels = []
            for text, color, foreground in [
                ("Reference", "#E7F1E7", "#245B31"),
                ("Target", "#E5EDF7", "#28517F"),
                ("Comparing result", "#F3EBDD", "#665333"),
            ]:
                label = QLabel(text)
                label.setAlignment(Qt.AlignCenter)
                label.setStyleSheet(
                    "QLabel { background-color: %s; color: %s; "
                    "border: 1px solid #C9C9C9; padding: 5px; }" %
                    (color, foreground)
                )
                header_layout.addWidget(label)
                group_labels.append(label)

            shown_ref_fields = default_ref_fields[:]
            shown_target_fields = default_target_fields[:]

            def field_header_labels():
                return (
                    ["{}  ▾".format(n) if n else "— None —  ▾" for n in shown_ref_fields]
                    + ["{}  ▾".format(n) if n else "— None —  ▾" for n in shown_target_fields]
                    + ["Ref count", "Tgt count", "Status"]
                )

            def update_display_fields():
                labels = field_header_labels()
                table.setHorizontalHeaderLabels(labels)
                for col in range(9):
                    item = table.horizontalHeaderItem(col)
                    if item is None:
                        continue
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setForeground(QBrush(QColor(
                        "#245B31" if col < 3 else
                        "#28517F" if col < 6 else "#665333"
                    )))
                    item.setBackground(QBrush(QColor(
                        "#E7F1E7" if col < 3 else
                        "#E5EDF7" if col < 6 else "#F3EBDD"
                    )))
                for r_idx, (digest, rc, tc, status) in enumerate(rows):
                    ref_record = ref_by_hash.get(digest)
                    target_record = target_by_hash.get(digest)
                    ref_attrs = ref_record["attrs"] if ref_record else {}
                    target_attrs = target_record["attrs"] if target_record else {}
                    values = []
                    for field_name in shown_ref_fields:
                        values.append(ref_attrs.get(field_name) if field_name else "")
                    for field_name in shown_target_fields:
                        values.append(target_attrs.get(field_name) if field_name else "")
                    values.extend([rc, tc, "✓ Match (1-to-1)" if status == "Match (1-to-1)" else "✗ Not matched"])
                    for c_idx, value in enumerate(values):
                        item = QTableWidgetItem("" if value is None else str(value))
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        if c_idx < 3:
                            item.setBackground(QBrush(QColor("#F0F7F0")))
                            item.setForeground(QBrush(QColor("#234D2A")))
                        elif c_idx < 6:
                            item.setBackground(QBrush(QColor("#F0F5FC")))
                            item.setForeground(QBrush(QColor("#23456B")))
                        elif c_idx < 8:
                            item.setBackground(QBrush(QColor("#F8F3E9")))
                            item.setForeground(QBrush(QColor("#57482F")))
                        elif status == "Match (1-to-1)":
                            item.setBackground(QBrush(QColor("#DDF3E4")))
                            item.setForeground(QBrush(QColor("#176B36")))
                        else:
                            item.setBackground(QBrush(QColor("#FCE4E4")))
                            item.setForeground(QBrush(QColor("#9B1C1C")))
                        table.setItem(r_idx, c_idx, item)
                    table.setVerticalHeaderItem(r_idx, QTableWidgetItem(str(r_idx + 1)))

            def choose_header_field(section):
                if 0 <= section < 3:
                    selected, slot, fields = shown_ref_fields, section, ref_fields
                elif 3 <= section < 6:
                    selected, slot, fields = shown_target_fields, section - 3, target_fields
                else:
                    return
                menu = QMenu(table)
                none_action = menu.addAction("— None —")
                menu.addSeparator()
                actions = []
                for field_name in fields:
                    action = menu.addAction(field_name)
                    action.setCheckable(True)
                    action.setChecked(selected[slot] == field_name)
                    actions.append((action, field_name))
                from qgis.PyQt.QtCore import QPoint
                x = table.horizontalHeader().sectionViewportPosition(section)
                y = table.horizontalHeader().height()
                picked = menu.exec_(table.horizontalHeader().viewport().mapToGlobal(QPoint(x, y)))
                if picked == none_action:
                    selected[slot] = None
                    update_display_fields()
                else:
                    for action, field_name in actions:
                        if picked == action:
                            selected[slot] = field_name
                            update_display_fields()
                            break

            table.horizontalHeader().sectionClicked.connect(choose_header_field)
            update_display_fields()

            def sync_grouped_header_widths(*args):
                header = table.horizontalHeader()
                widths = [header.sectionSize(i) for i in range(table.columnCount())]
                header_gutter.setFixedWidth(
                    table.frameWidth() + table.verticalHeader().width()
                )
                for idx, label in enumerate(group_labels):
                    label.setFixedWidth(sum(widths[idx * 3:(idx + 1) * 3]))
                # Keep the strip exactly as wide as the table's data viewport plus
                # row-number gutter; do not stretch it independently across scrollbar space.
                header_container.setFixedWidth(
                    table.frameWidth() * 2 + table.verticalHeader().width() + sum(widths)
                )

            table.horizontalHeader().sectionResized.connect(sync_grouped_header_widths)
            table.verticalHeader().sectionResized.connect(sync_grouped_header_widths)
            table.horizontalScrollBar().rangeChanged.connect(sync_grouped_header_widths)
            QTimer.singleShot(0, sync_grouped_header_widths)

            layout.addWidget(header_container)
            layout.addWidget(table, 1)

            action_rows = QVBoxLayout()
            compare_row = QHBoxLayout()
            export_row = QHBoxLayout()
            attribute_btn = QPushButton("▶  Compare Attributes for Matched Geometries...")
            attribute_btn.setToolTip("Compare selected attribute fields for geometry pairs matched 1-to-1")
            attribute_btn.setMinimumHeight(36)
            attribute_btn.setStyleSheet(
                "QPushButton { background-color: #1769AA; color: white; "
                "font-weight: bold; padding: 7px 14px; border: 1px solid #0F568F; "
                "border-radius: 4px; }"
                "QPushButton:hover { background-color: #0F568F; }"
                "QPushButton:pressed { background-color: #0A416D; padding-top: 8px; }"
                "QPushButton:disabled { background-color: #B8C7D3; color: #F5F7F9; }"
            )
            export_btn = QPushButton("Export geometry summary to CSV...")
            export_ref_btn = QPushButton("Export unmatched reference records to CSV...")
            export_target_btn = QPushButton("Export unmatched target records to CSV...")
            export_ref_shp_btn = QPushButton("Export unmatched reference records to Shapefile...")
            export_target_shp_btn = QPushButton("Export unmatched target records to Shapefile...")
            close_btn = QPushButton("Close")
            compare_row.addWidget(attribute_btn)
            compare_row.addStretch()
            export_row.addWidget(export_btn)
            export_row.addWidget(export_ref_btn)
            export_row.addWidget(export_target_btn)
            export_row.addWidget(export_ref_shp_btn)
            export_row.addWidget(export_target_shp_btn)
            export_row.addWidget(close_btn)
            action_rows.addLayout(compare_row)
            action_rows.addLayout(export_row)
            layout.addLayout(action_rows)

            def export_hash_csv():
                path, _ = QFileDialog.getSaveFileName(dialog, "Save geometry summary", "Geometry_Comparison_Summary.csv", "CSV (*.csv)")
                if not path:
                    return
                if not path.lower().endswith(".csv"):
                    path += ".csv"
                try:
                    with open(path, "w", newline="", encoding="utf-8-sig") as stream:
                        writer = csv.writer(stream, delimiter=";")
                        writer.writerow(["Geometry_Fingerprint", "Reference_Count", "Target_Count", "Status"])
                        writer.writerows(rows)
                    QMessageBox.information(dialog, "Export complete", "Geometry summary saved to:\n{}".format(path))
                except Exception as exc:
                    QMessageBox.critical(dialog, "Export failed", str(exc))

            def export_unmatched(records, field_names, default_name, side_label):
                path, _ = QFileDialog.getSaveFileName(
                    dialog, "Export unmatched records — " + side_label,
                    default_name, "CSV (*.csv)")
                if not path:
                    return
                if not path.lower().endswith(".csv"):
                    path += ".csv"
                try:
                    with open(path, "w", newline="", encoding="utf-8-sig") as stream:
                        writer = csv.writer(stream, delimiter=";")
                        writer.writerow(["FID", "Geometry_Fingerprint", "Geometry_Status"] + field_names)
                        for record in records:
                            attrs = record["attrs"]
                            writer.writerow([attrs.get("FID"), record["hash"] or "",
                                             record["record_status"]] +
                                            [attrs.get(name) for name in field_names])
                    QMessageBox.information(dialog, "Export complete",
                                            "{} unmatched records saved to:\\n{}".format(
                                                len(records), path))
                except Exception as exc:
                    QMessageBox.critical(dialog, "Export failed", str(exc))

            def export_unmatched_shapefile(records, field_names, source_layer, default_name, side_label):
                path, _ = QFileDialog.getSaveFileName(
                    dialog, "Export Shapefile — " + side_label,
                    default_name, "ESRI Shapefile (*.shp)")
                if not path:
                    return
                if not path.lower().endswith(".shp"):
                    path += ".shp"
                driver = ogr.GetDriverByName("ESRI Shapefile")
                if driver is None:
                    QMessageBox.critical(dialog, "Export failed", "The ESRI Shapefile driver is unavailable.")
                    return
                if os.path.exists(path):
                    try:
                        driver.DeleteDataSource(path)
                    except Exception:
                        QMessageBox.warning(dialog, "Export failed",
                                            "The destination already exists and cannot be overwritten. Choose another name.")
                        return
                out_ds = None
                try:
                    srs = source_layer.GetSpatialRef()
                    geom_type = source_layer.GetGeomType()
                    out_ds = driver.CreateDataSource(path)
                    if out_ds is None:
                        raise RuntimeError("Could not create the Shapefile.")
                    out_layer = out_ds.CreateLayer(
                        os.path.splitext(os.path.basename(path))[0],
                        srs=srs, geom_type=geom_type)
                    if out_layer is None:
                        raise RuntimeError("Could not create the Shapefile layer.")

                    # Copy source schema; Shapefile limits field names to 10 characters.
                    source_defn = source_layer.GetLayerDefn()
                    source_field_names = []
                    for i in range(source_defn.GetFieldCount()):
                        src_fd = source_defn.GetFieldDefn(i)
                        out_fd = ogr.FieldDefn(src_fd.GetName()[:10], src_fd.GetType())
                        if src_fd.GetWidth() > 0:
                            out_fd.SetWidth(src_fd.GetWidth())
                        if src_fd.GetPrecision() > 0:
                            out_fd.SetPrecision(src_fd.GetPrecision())
                        if out_layer.CreateField(out_fd) != 0:
                            raise RuntimeError("Failed to create field: " + src_fd.GetName())
                        source_field_names.append(src_fd.GetName())

                    # Add concise provenance fields (within Shapefile's 10-char name limit).
                    for name, field_type, width in (
                        ("SRC_FID", ogr.OFTInteger64, 18),
                        ("GEOM_FP", ogr.OFTString, 64),
                        ("STATUS", ogr.OFTString, 24),
                    ):
                        fd = ogr.FieldDefn(name, field_type)
                        if width:
                            fd.SetWidth(width)
                        if out_layer.CreateField(fd) != 0:
                            raise RuntimeError("Failed to create additional field: " + name)

                    for record in records:
                        out_feature = ogr.Feature(out_layer.GetLayerDefn())
                        attrs = record["attrs"]
                        out_feature.SetField("SRC_FID", int(attrs.get("FID", -1)))
                        out_feature.SetField("GEOM_FP", record["hash"] or "")
                        out_feature.SetField("STATUS", record["record_status"] if record["record_status"] != "OK" else "UNMATCHED")
                        for field_name in source_field_names:
                            value = attrs.get(field_name)
                            if value is not None:
                                out_feature.SetField(field_name[:10], value)
                        if record.get("geometry_wkb"):
                            geom = ogr.CreateGeometryFromWkb(record["geometry_wkb"])
                            if geom is not None:
                                out_feature.SetGeometry(geom)
                        if out_layer.CreateFeature(out_feature) != 0:
                            raise RuntimeError("Failed to write a feature to the Shapefile.")
                        out_feature = None
                    out_ds = None
                    QMessageBox.information(
                        dialog, "Export complete",
                        "Shapefile with {} unmatched features created:\n{}\n\n"
                        "Note: Shapefile field names are limited to 10 characters.".format(len(records), path))
                except Exception as exc:
                    out_ds = None
                    QMessageBox.critical(dialog, "Shapefile export failed", str(exc))

            export_ref_btn.clicked.connect(
                lambda: export_unmatched(ref_unmatched, ref_fields,
                                         "Unmatched_Reference.csv", "reference"))
            export_target_btn.clicked.connect(
                lambda: export_unmatched(target_unmatched, target_fields,
                                         "Unmatched_Target.csv", "target"))
            export_ref_shp_btn.clicked.connect(
                lambda: export_unmatched_shapefile(ref_unmatched, ref_fields, layer_ref,
                                                   "Unmatched_Reference.shp", "reference"))
            export_target_shp_btn.clicked.connect(
                lambda: export_unmatched_shapefile(target_unmatched, target_fields, layer_target,
                                                   "Unmatched_Target.shp", "target"))
            def compare_matched_attributes():
                # Only exact 1-to-1 geometry matches are eligible for attribute comparison.
                ref_by_hash = {r["hash"]: r for r in ref_records
                               if r["hash"] and ref_counts.get(r["hash"], 0) == 1
                               and target_counts.get(r["hash"], 0) == 1}
                target_by_hash = {r["hash"]: r for r in target_records
                                  if r["hash"] and ref_counts.get(r["hash"], 0) == 1
                                  and target_counts.get(r["hash"], 0) == 1}
                if not ref_by_hash:
                    QMessageBox.information(dialog, "Attribute comparison",
                                            "No 1-to-1 geometry matches are available for attribute comparison.")
                    return

                ref_names = list(ref_fields)
                target_names = list(target_fields)
                setup = QDialog(dialog)
                setup.setWindowTitle("Select Attribute Pairs")
                setup.resize(760, 470)
                setup_layout = QVBoxLayout(setup)
                setup_layout.addWidget(QLabel(
                    "Select reference and target field pairs. Row order determines the canonical attribute order."))
                options_row = QHBoxLayout()
                case_check = QCheckBox("Preserve letter case")
                case_check.setChecked(True)
                trim_check = QCheckBox("Preserve leading/trailing spaces")
                trim_check.setChecked(True)
                options_row.addWidget(case_check)
                options_row.addWidget(trim_check)
                options_row.addStretch()
                setup_layout.addLayout(options_row)

                mapping_table = QTableWidget(0, 2)
                mapping_table.setHorizontalHeaderLabels(["Reference field", "Target field"])
                mapping_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
                mapping_table.setSelectionBehavior(QAbstractItemView.SelectRows)
                mapping_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
                setup_layout.addWidget(mapping_table, 1)

                def add_mapping_row(ref_default=None, target_default=None):
                    row = mapping_table.rowCount()
                    mapping_table.insertRow(row)
                    ref_combo = QComboBox()
                    target_combo = QComboBox()
                    ref_combo.addItem("-- Not selected --", "")
                    for field_name in ref_names:
                        ref_combo.addItem(field_name, field_name)
                    target_combo.addItem("-- Not selected --", "")
                    for field_name in target_names:
                        target_combo.addItem(field_name, field_name)
                    if ref_default in ref_names:
                        ref_combo.setCurrentText(ref_default)
                    if target_default in target_names:
                        target_combo.setCurrentText(target_default)
                    mapping_table.setCellWidget(row, 0, ref_combo)
                    mapping_table.setCellWidget(row, 1, target_combo)

                # Match same-name fields first; then add rows so every field from both sides is visible.
                target_lookup = {}
                for name in target_names:
                    target_lookup.setdefault(name.casefold(), []).append(name)
                used_ref = set()
                used_target = set()
                for name in ref_names:
                    matches = target_lookup.get(name.casefold(), [])
                    if len(matches) == 1 and name.casefold() not in used_ref and matches[0].casefold() not in used_target:
                        add_mapping_row(name, matches[0])
                        used_ref.add(name.casefold())
                        used_target.add(matches[0].casefold())

                remaining_ref = [n for n in ref_names if n.casefold() not in used_ref]
                remaining_target = [n for n in target_names if n.casefold() not in used_target]
                for idx in range(max(len(remaining_ref), len(remaining_target))):
                    add_mapping_row(
                        remaining_ref[idx] if idx < len(remaining_ref) else None,
                        remaining_target[idx] if idx < len(remaining_target) else None
                    )
                if mapping_table.rowCount() == 0:
                    add_mapping_row()

                mapping_buttons = QHBoxLayout()
                add_btn = QPushButton("Add pair")
                remove_btn = QPushButton("Remove selected row(s)")
                mapping_buttons.addWidget(add_btn)
                mapping_buttons.addWidget(remove_btn)
                mapping_buttons.addStretch()
                setup_layout.addLayout(mapping_buttons)
                def add_blank_mapping():
                    add_mapping_row()
                def remove_mapping():
                    rows_to_remove = sorted({idx.row() for idx in mapping_table.selectedIndexes()}, reverse=True)
                    for row in rows_to_remove:
                        mapping_table.removeRow(row)
                add_btn.clicked.connect(add_blank_mapping)
                remove_btn.clicked.connect(remove_mapping)

                action_row = QHBoxLayout()
                run_btn = QPushButton("Run comparison")
                cancel_btn = QPushButton("Cancel")
                action_row.addStretch()
                action_row.addWidget(run_btn)
                action_row.addWidget(cancel_btn)
                setup_layout.addLayout(action_row)
                run_btn.clicked.connect(setup.accept)
                cancel_btn.clicked.connect(setup.reject)
                if setup.exec_() != QDialog.Accepted:
                    return

                mappings = []
                used_ref = set()
                used_target = set()
                for row in range(mapping_table.rowCount()):
                    ref_combo = mapping_table.cellWidget(row, 0)
                    target_combo = mapping_table.cellWidget(row, 1)
                    if ref_combo and target_combo:
                        ref_field = ref_combo.currentData()
                        target_field = target_combo.currentData()
                        # An incomplete row is ignored; users can leave unmatched fields unused.
                        if not ref_field or not target_field:
                            continue
                        if ref_field.casefold() in used_ref or target_field.casefold() in used_target:
                            QMessageBox.warning(
                                setup, "Field used more than once",
                                "Each field can be used in only one pair. Please adjust the field mapping."
                            )
                            return
                        used_ref.add(ref_field.casefold())
                        used_target.add(target_field.casefold())
                        mappings.append((ref_field, target_field))
                if not mappings:
                    QMessageBox.warning(setup, "No field pairs selected",
                                        "Select at least one reference/target field pair.")
                    return

                def canonical_value(value, keep_case, keep_spaces):
                    # Preserve NULL separately from empty strings and use stable typed serialization.
                    if value is None:
                        return ["NULL", None]
                    if isinstance(value, str):
                        if not keep_spaces:
                            value = value.strip()
                        if not keep_case:
                            value = value.casefold()
                        return ["STRING", value]
                    if isinstance(value, bytes):
                        return ["BINARY", value.hex()]
                    if isinstance(value, (list, tuple)):
                        return ["LIST", [canonical_value(v, keep_case, keep_spaces) for v in value]]
                    # OGR may return date/time tuples; preserve their component values.
                    return [type(value).__name__, value]

                def stable_json_value(value):
                    import json
                    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=str)

                result_rows = []
                same_count = 0
                diff_count = 0
                keep_case = case_check.isChecked()
                keep_spaces = trim_check.isChecked()
                for digest in sorted(ref_by_hash):
                    ref_record = ref_by_hash[digest]
                    target_record = target_by_hash[digest]
                    ref_values = []
                    target_values = []
                    for ref_field, target_field in mappings:
                        ref_values.append(canonical_value(ref_record["attrs"].get(ref_field), keep_case, keep_spaces))
                        target_values.append(canonical_value(target_record["attrs"].get(target_field), keep_case, keep_spaces))
                    ref_canonical = stable_json_value(ref_values)
                    target_canonical = stable_json_value(target_values)
                    ref_attr_digest = hashlib.sha256(ref_canonical.encode("utf-8")).hexdigest()
                    target_attr_digest = hashlib.sha256(target_canonical.encode("utf-8")).hexdigest()
                    same = ref_attr_digest == target_attr_digest
                    if same:
                        same_count += 1
                    else:
                        diff_count += 1
                    result_rows.append({
                        "geom_hash": digest,
                        "ref_fid": ref_record["attrs"].get("FID"),
                        "target_fid": target_record["attrs"].get("FID"),
                        "status": "Attributes match" if same else "Attributes differ",
                        "ref_values": ref_values,
                        "target_values": target_values,
                        "ref_canonical": ref_canonical,
                        "target_canonical": target_canonical,
                    })

                result_dialog = QDialog(dialog)
                result_dialog.setWindowTitle("Attribute Comparison Results")
                result_dialog.resize(1050, 620)
                result_layout = QVBoxLayout(result_dialog)
                total_pairs = len(result_rows)
                same_pct = 100.0 * same_count / total_pairs if total_pairs else 0.0
                diff_pct = 100.0 * diff_count / total_pairs if total_pairs else 0.0
                result_layout.addWidget(QLabel(
                    "1-to-1 geometry pairs checked: {} | Matching attributes: {} ({:.2f}%) | "
                    "Different attributes: {} ({:.2f}%)".format(total_pairs, same_count, same_pct, diff_count, diff_pct)))
                bar = QProgressBar()
                bar.setRange(0, 1000)
                bar.setValue(int(round(same_pct * 10)))
                bar.setFormat("Matching attributes %p%")
                bar.setToolTip("Matching attributes {:.2f}% | different {:.2f}%".format(same_pct, diff_pct))
                result_layout.addWidget(bar)

                filter_combo = QComboBox()
                filter_combo.addItems(["All records", "Different attributes only", "Matching attributes only"])
                result_layout.addWidget(filter_combo)
                result_table = QTableWidget(0, 4)
                result_table.setHorizontalHeaderLabels(["Reference FID", "Target FID", "Status", "Different values"])
                self._configure_table(result_table)
                result_layout.addWidget(result_table, 1)

                def refresh_attribute_table():
                    selected = filter_combo.currentText()
                    visible = [r for r in result_rows
                               if selected == "All records"
                               or (selected == "Different attributes only" and r["status"] == "Attributes differ")
                               or (selected == "Matching attributes only" and r["status"] == "Attributes match")]
                    result_table.setRowCount(len(visible))
                    for row_idx, result in enumerate(visible):
                        # Show actual source values for differing fields.
                        ref_record = ref_by_hash[result["geom_hash"]]
                        target_record = target_by_hash[result["geom_hash"]]
                        differing = []
                        for ref_field, target_field in mappings:
                            rv = ref_record["attrs"].get(ref_field)
                            tv = target_record["attrs"].get(target_field)
                            cv_r = canonical_value(rv, keep_case, keep_spaces)
                            cv_t = canonical_value(tv, keep_case, keep_spaces)
                            if cv_r != cv_t:
                                differing.append("{}={!r} / {}={!r}".format(ref_field, rv, target_field, tv))
                        values = [result["ref_fid"], result["target_fid"], result["status"],
                                  "; ".join(differing) if differing else "—"]
                        is_different = result["status"] == "Attributes differ"
                        # Tint the complete record row by comparison status so differences
                        # are visible without having to inspect the Status column first.
                        row_bg = QColor("#FCE8E8" if is_different else "#EAF5EC")
                        normal_fg = QColor("#8F2525" if is_different else "#285F39")
                        for col, value in enumerate(values):
                            item = QTableWidgetItem(str(value))
                            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                            item.setBackground(QBrush(row_bg))
                            item.setForeground(QBrush(normal_fg))
                            if col == 2:
                                item.setFont(item.font())
                                font = item.font()
                                font.setBold(True)
                                item.setFont(font)
                                item.setText(("✕  " if is_different else "✓  ") + str(value))
                            elif col == 3 and is_different:
                                font = item.font()
                                font.setBold(True)
                                item.setFont(font)
                                item.setForeground(QBrush(QColor("#A12626")))
                            item.setToolTip(str(value))
                            result_table.setItem(row_idx, col, item)
                filter_combo.currentIndexChanged.connect(refresh_attribute_table)
                refresh_attribute_table()

                result_buttons = QHBoxLayout()
                export_diff_btn = QPushButton("Export records with different attributes to CSV...")
                export_combined_shp_btn = QPushButton("Export combined attribute differences to Shapefile...")
                close_result_btn = QPushButton("Close")
                result_buttons.addWidget(export_diff_btn)
                result_buttons.addWidget(export_combined_shp_btn)
                result_buttons.addStretch()
                result_buttons.addWidget(close_result_btn)
                result_layout.addLayout(result_buttons)

                def export_attribute_differences():
                    differences = [r for r in result_rows if r["status"] == "Attributes differ"]
                    path, _ = QFileDialog.getSaveFileName(
                        result_dialog, "Export records with different attributes",
                        "Different_Attribute_Records.csv", "CSV (*.csv)")
                    if not path:
                        return
                    if not path.lower().endswith(".csv"):
                        path += ".csv"
                    try:
                        with open(path, "w", newline="", encoding="utf-8-sig") as stream:
                            writer = csv.writer(stream, delimiter=";")
                            writer.writerow(["Reference_FID", "Target_FID", "Status"] +
                                            ["Reference_" + a for a, b in mappings] +
                                            ["Target_" + b for a, b in mappings])
                            for result in differences:
                                ref_record = ref_by_hash[result["geom_hash"]]
                                target_record = target_by_hash[result["geom_hash"]]
                                writer.writerow([result["ref_fid"], result["target_fid"], result["status"]] +
                                                [ref_record["attrs"].get(a) for a, b in mappings] +
                                                [target_record["attrs"].get(b) for a, b in mappings])
                        QMessageBox.information(result_dialog, "Export complete",
                                                "Records with different attributes saved to:\n{}".format(path))
                    except Exception as exc:
                        QMessageBox.critical(result_dialog, "Export failed", str(exc))
                def export_attribute_differences_shapefile():
                    differences = [r for r in result_rows if r["status"] == "Attributes differ"]
                    if not differences:
                        QMessageBox.information(
                            result_dialog, "No differences",
                            "There are no records with different attributes to export.")
                        return

                    path, _ = QFileDialog.getSaveFileName(
                        result_dialog, "Export combined attribute differences",
                        "Different_Attribute_Combined.shp", "ESRI Shapefile (*.shp)")
                    if not path:
                        return
                    if not path.lower().endswith(".shp"):
                        path += ".shp"

                    driver = ogr.GetDriverByName("ESRI Shapefile")
                    if driver is None:
                        QMessageBox.critical(result_dialog, "Export failed",
                                             "The ESRI Shapefile driver is unavailable.")
                        return
                    if os.path.exists(path):
                        try:
                            driver.DeleteDataSource(path)
                        except Exception:
                            QMessageBox.warning(
                                result_dialog, "Export failed",
                                "The destination already exists and cannot be overwritten. Choose another name.")
                            return

                    out_ds = None
                    try:
                        ref_defn = layer_ref.GetLayerDefn()
                        target_defn = layer_target.GetLayerDefn()
                        out_ds = driver.CreateDataSource(path)
                        if out_ds is None:
                            raise RuntimeError("Could not create the Shapefile.")
                        out_layer = out_ds.CreateLayer(
                            os.path.splitext(os.path.basename(path))[0],
                            srs=layer_ref.GetSpatialRef(),
                            geom_type=layer_ref.GetGeomType())
                        if out_layer is None:
                            raise RuntimeError("Could not create the Shapefile layer.")

                        # Shapefile field names are limited to 10 characters. Prefix all
                        # source fields so reference and target values remain distinguishable.
                        used_names = set()
                        def unique_output_name(prefix, source_name):
                            base = (prefix + source_name)[:10]
                            candidate = base
                            suffix = 1
                            while candidate.casefold() in used_names:
                                tail = str(suffix)
                                candidate = base[:10-len(tail)] + tail
                                suffix += 1
                            used_names.add(candidate.casefold())
                            return candidate

                        # Provenance fields first; keep their names short for SHP compatibility.
                        output_special = {}
                        for name, field_type, width in [
                                ("REF_FID", ogr.OFTInteger64, 18),
                                ("TGT_FID", ogr.OFTInteger64, 18),
                                ("STATUS", ogr.OFTString, 24),
                                ("DIFF_ATTR", ogr.OFTString, 254)]:
                            out_name = unique_output_name("", name)
                            fd = ogr.FieldDefn(out_name, field_type)
                            if width:
                                fd.SetWidth(width)
                            if out_layer.CreateField(fd) != 0:
                                raise RuntimeError("Failed to create output field: " + out_name)
                            output_special[name] = out_name

                        def add_source_fields(source_defn, prefix):
                            field_map = {}
                            for i in range(source_defn.GetFieldCount()):
                                src_fd = source_defn.GetFieldDefn(i)
                                out_name = unique_output_name(prefix, src_fd.GetName())
                                out_fd = ogr.FieldDefn(out_name, src_fd.GetType())
                                if src_fd.GetWidth() > 0:
                                    out_fd.SetWidth(min(src_fd.GetWidth(), 254) if src_fd.GetType() == ogr.OFTString else src_fd.GetWidth())
                                if src_fd.GetPrecision() > 0:
                                    out_fd.SetPrecision(src_fd.GetPrecision())
                                if out_layer.CreateField(out_fd) != 0:
                                    raise RuntimeError("Failed to create output field for: " + src_fd.GetName())
                                field_map[src_fd.GetName()] = out_name
                            return field_map

                        ref_output_fields = add_source_fields(ref_defn, "R_")
                        target_output_fields = add_source_fields(target_defn, "T_")

                        for result in differences:
                            digest = result["geom_hash"]
                            ref_record = ref_by_hash[digest]
                            target_record = target_by_hash[digest]
                            feature_out = ogr.Feature(out_layer.GetLayerDefn())
                            feature_out.SetField(output_special["REF_FID"], int(result["ref_fid"]))
                            feature_out.SetField(output_special["TGT_FID"], int(result["target_fid"]))
                            feature_out.SetField(output_special["STATUS"], "Attributes differ")

                            for source_name, output_name in ref_output_fields.items():
                                value = ref_record["attrs"].get(source_name)
                                if value is not None:
                                    feature_out.SetField(output_name, value)
                            for source_name, output_name in target_output_fields.items():
                                value = target_record["attrs"].get(source_name)
                                if value is not None:
                                    feature_out.SetField(output_name, value)

                            different_names = []
                            for ref_field, target_field in mappings:
                                rv = ref_record["attrs"].get(ref_field)
                                tv = target_record["attrs"].get(target_field)
                                if canonical_value(rv, keep_case, keep_spaces) != canonical_value(tv, keep_case, keep_spaces):
                                    different_names.append("R:" + ref_field + "/T:" + target_field)
                            feature_out.SetField(output_special["DIFF_ATTR"], ", ".join(different_names)[:254])

                            # The reference geometry is the common spatial representation for each pair.
                            if ref_record.get("geometry_wkb"):
                                geom = ogr.CreateGeometryFromWkb(ref_record["geometry_wkb"])
                                if geom is not None:
                                    feature_out.SetGeometry(geom)
                            if out_layer.CreateFeature(feature_out) != 0:
                                raise RuntimeError("Failed to write a feature to the Shapefile.")
                            feature_out = None

                        count = len(differences)
                        out_ds = None
                        QMessageBox.information(
                            result_dialog, "Export complete",
                            "Exported {} paired features with different attributes to:\n{}\n\n"
                            "The Shapefile contains reference and target attributes together. "
                            "R_ fields are from reference; T_ fields are from target. "
                            "REF_FID and TGT_FID identify the pair; DIFF_ATTR lists compared fields that differ. "
                            "Only 1-to-1 geometry pairs with differing attributes are included. "
                            "Shapefile field names are limited to 10 characters.".format(count, path))
                    except Exception as exc:
                        out_ds = None
                        QMessageBox.critical(result_dialog, "Shapefile export failed", str(exc))

                export_diff_btn.clicked.connect(export_attribute_differences)
                export_combined_shp_btn.clicked.connect(export_attribute_differences_shapefile)
                close_result_btn.clicked.connect(result_dialog.accept)
                result_dialog.exec_()

            attribute_btn.clicked.connect(compare_matched_attributes)
            export_btn.clicked.connect(export_hash_csv)
            close_btn.clicked.connect(dialog.accept)
            self.progress.setValue(100)
            self.status_label.setText("Geometry comparison complete. Results are shown in a separate window.")
            dialog.exec_()
        except Exception as exc:
            QMessageBox.critical(self, "Geometry comparison failed",
                                 "{}\n\n{}".format(exc, traceback.format_exc()))
            self.status_label.setText("Geometry comparison failed.")
        finally:
            ds_ref = None
            ds_target = None
            self._selection_changed()

    @staticmethod
    def _name_status(a, b):
        if a == b:
            return "Match"
        if a.casefold() == b.casefold():
            return "Case-only difference"
        return "Different"

    def _add_summary(self, check, ref_value, target_value, status, findings):
        self.summary_results.append({
            "check": check, "ref": str(ref_value), "target": str(target_value),
            "status": status, "findings": int(findings)
        })

    def _add_detail(self, ref_name, ref_type, ref_width, target_name, target_type, target_width, status, note="", category="Field"):
        self.detail_results.append({
            "ref_name": ref_name, "ref_type": ref_type, "ref_width": ref_width,
            "target_name": target_name, "target_type": target_type,
            "target_width": target_width, "status": status, "note": note,
            "category": category
        })

    def _compare_fields(self, ref_fields, target_fields):
        ref_amb = self._ambiguities(ref_fields)
        target_amb = self._ambiguities(target_fields)
        ambiguous_keys = set(ref_amb) | set(target_amb)
        matched = 0
        missing = 0
        extra = 0
        different = 0
        ambiguous_count = 0

        ref_by_key = defaultdict(list)
        target_by_key = defaultdict(list)
        for f in ref_fields:
            ref_by_key[f["key"]].append(f)
        for f in target_fields:
            target_by_key[f["key"]].append(f)

        for key in sorted(ambiguous_keys):
            rlist = ref_by_key.get(key, [])
            tlist = target_by_key.get(key, [])
            ambiguous_count += 1
            self._add_detail(
                ", ".join(f["name"] for f in rlist) or "—",
                ", ".join(f["type"] for f in rlist) or "—",
                ", ".join(str(f["width"]) for f in rlist) or "—",
                ", ".join(f["name"] for f in tlist) or "—",
                ", ".join(f["type"] for f in tlist) or "—",
                ", ".join(str(f["width"]) for f in tlist) or "—",
                "Ambiguous field names", "Tidak dipasangkan otomatis karena nama berulang setelah kapitalisasi diabaikan."
            )

        all_keys = set(ref_by_key) | set(target_by_key)
        for key in sorted(all_keys):
            # Ambiguous names are reported above and never paired automatically.
            if key in ambiguous_keys:
                continue
            rf = ref_by_key.get(key, [None])[0]
            tf = target_by_key.get(key, [None])[0]
            if rf is None:
                extra += 1
                self._add_detail("—", "—", "—", tf["name"], tf["type"], tf["width"], "Only in target")
                continue
            if tf is None:
                missing += 1
                self._add_detail(rf["name"], rf["type"], rf["width"], "—", "—", "—", "Only in reference")
                continue
            matched += 1
            type_same = self._type_category(rf) == self._type_category(tf)
            width_same = rf["width"] == tf["width"]
            case_same = rf["name"] == tf["name"]
            precision_same = rf["precision"] == tf["precision"]
            differences = []
            if not type_same:
                differences.append("Data type differs")
            if not width_same:
                differences.append("Length differs")
            if not precision_same:
                differences.append("Precision differs")
            if not case_same:
                differences.append("Name capitalization differs")
            status = "Match" if not differences else "Different"
            if differences:
                different += 1
            self._add_detail(rf["name"], "{} ({})".format(rf["type"], self._type_category(rf)), rf["width"],
                             tf["name"], "{} ({})".format(tf["type"], self._type_category(tf)), tf["width"],
                             status, "; ".join(differences) or "Type, length, and precision match.")

        # Field counts and field-level outcome are shown in the summary table.
        self._add_summary("Field Count", len(ref_fields), len(target_fields),
                          "Match" if len(ref_fields) == len(target_fields) else "Different", abs(len(ref_fields) - len(target_fields)))
        self._add_summary("Fields matched by name", matched, matched,
                          "Match", 0)
        self._add_summary("Fields only in reference", missing, 0,
                          "Match" if missing == 0 else "Different", missing)
        self._add_summary("Fields only in target", 0, extra,
                          "Match" if extra == 0 else "Different", extra)
        self._add_summary("Field definition differences", different, different,
                          "Match" if different == 0 else "Different", different)
        self._add_summary("Ambiguous field names", ambiguous_count, ambiguous_count,
                          "Needs attention" if ambiguous_count else "Match", ambiguous_count)
        self._add_summary("Total reference/target fields", len(ref_fields), len(target_fields),
                          "Needs attention" if ambiguous_count else ("Match" if len(ref_fields) == len(target_fields) and not missing and not extra and not different else "Different"),
                          missing + extra + different + ambiguous_count)

    def _render_summary(self, *args):
        self.summary_table.setRowCount(0)
        filter_value = self.filter_combo.currentText()
        rows = []
        for result in self.summary_results:
            status = result["status"]
            if filter_value == "Different" and status not in ("Different", "Case-only difference"):
                continue
            if filter_value == "Match" and status != "Match":
                continue
            if filter_value == "Needs attention" and status != "Needs attention":
                continue
            rows.append(result)
        self.summary_table.setRowCount(len(rows))
        for row, result in enumerate(rows):
            status = result["status"]
            status_labels = {
                "Match": "✓ Match",
                "Different": "✗ Different",
                "Case-only difference": "⚠ Case-only difference",
                "Needs attention": "⚠ Needs attention",
            }
            values = [result["check"], result["ref"], result["target"],
                      status_labels.get(status, status), result["findings"]]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                # Match the source-column colors used in Difference details below.
                if col == 1:
                    item.setBackground(QBrush(QColor("#E8F2E8")))
                    item.setForeground(QBrush(QColor("#285B35")))
                elif col == 2:
                    item.setBackground(QBrush(QColor("#E7EEF9")))
                    item.setForeground(QBrush(QColor("#254F87")))
                elif col == 3:
                    if status == "Match":
                        item.setBackground(QBrush(QColor("#DDF3E4")))
                        item.setForeground(QBrush(QColor("#176B36")))
                    elif status in ("Different", "Case-only difference"):
                        item.setBackground(QBrush(QColor("#FCE4E4" if status == "Different" else "#FFF1CC")))
                        item.setForeground(QBrush(QColor("#9B1C1C" if status == "Different" else "#805600")))
                        item.setToolTip("See the detail table for more information.")
                    elif status == "Needs attention":
                        item.setBackground(QBrush(QColor("#FFF1CC")))
                        item.setForeground(QBrush(QColor("#805600")))
                        item.setToolTip("See the detail table for more information.")
                self.summary_table.setItem(row, col, item)
        if rows:
            self.summary_table.selectRow(0)
        else:
            self.detail_table.setRowCount(0)

    def _show_selected_detail(self):
        selected = self.summary_table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        check_item = self.summary_table.item(row, 0)
        if check_item is None:
            return
        check = check_item.text()
        # Detail rows are organized by broad category. Clicking field-related summary rows shows all field details.
        field_checks = {
            "Field Count", "Fields matched by name", "Fields only in reference",
            "Fields only in target", "Field definition differences", "Ambiguous field names",
            "Total reference/target fields"
        }
        if check in field_checks:
            details = [d for d in self.detail_results if d["category"] == "Field"]
        else:
            details = [d for d in self.detail_results if d["category"] == check]
        self.detail_table.setRowCount(len(details))
        for r, d in enumerate(details):
            detail_status = d["status"]
            status_mark = "✓ " if detail_status == "Match" else ("⚠ " if "Ambiguous" in detail_status else "✗ ")
            values = [d["ref_name"], d["ref_type"], d["ref_width"],
                      d["target_name"], d["target_type"], d["target_width"],
                      "{}{}".format(status_mark, detail_status)]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                # Visually distinguish source sides; reserve the final column for the conclusion.
                if c <= 2:
                    item.setBackground(QBrush(QColor("#E7F1E7")))
                    item.setForeground(QBrush(QColor("#234D2A")))
                elif c <= 5:
                    item.setBackground(QBrush(QColor("#E5EDF7")))
                    item.setForeground(QBrush(QColor("#23456B")))
                else:
                    if detail_status == "Match":
                        item.setBackground(QBrush(QColor("#DDF3E4")))
                        item.setForeground(QBrush(QColor("#176B36")))
                    elif "Ambiguous" in detail_status:
                        item.setBackground(QBrush(QColor("#FFF1CC")))
                        item.setForeground(QBrush(QColor("#805600")))
                    else:
                        item.setBackground(QBrush(QColor("#FCE4E4")))
                        item.setForeground(QBrush(QColor("#9B1C1C")))
                if d["status"] != "Match":
                    item.setToolTip(d["note"])
                self.detail_table.setItem(r, c, item)

    def export_csv(self):
        if not self.summary_results:
            QMessageBox.information(self, "No results", "Run the comparison first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save comparison report as CSV", "FeatureClass_Compare_Report.csv", "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream, delimiter=";")
                writer.writerow(["Section", "Check", "Reference", "Target", "Status", "Findings", "Notes"])
                for r in self.summary_results:
                    writer.writerow(["Summary", r["check"], r["ref"], r["target"], r["status"], r["findings"], ""])
                for d in self.detail_results:
                    writer.writerow(["Detail", "Field", d["ref_name"], d["target_name"], d["status"], "",
                                     "Reference: {} / length {}; Target: {} / length {}; {}".format(
                                         d["ref_type"], d["ref_width"], d["target_type"], d["target_width"], d["note"])])
            QMessageBox.information(self, "Export complete", "Report saved to:\n{}".format(path))
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))


class FeatureClassComparePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QAction(QIcon(os.path.join(os.path.dirname(__file__), "icon.svg")),
                              "FeatureClass Compare", self.iface.mainWindow())
        self.action.setToolTip("Compare the structure of a Feature Class or Shapefile")
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("&FeatureClass Compare", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.action:
            self.iface.removePluginMenu("&FeatureClass Compare", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    def run(self):
        if self.dialog is None:
            self.dialog = FeatureClassCompareDialog(self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
