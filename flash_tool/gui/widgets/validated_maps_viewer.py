"""Validated Maps Viewer widget for GUI.

Displays all validated maps, rejected maps, and forbidden regions from flash_tool/validated_maps.py.
Allows users to browse map definitions, see safety status, and understand forbidden regions visually.
"""
from __future__ import annotations

from typing import Any, Optional
from flash_tool import validated_maps
import csv

try:
    from PySide6 import QtWidgets, QtCore
except Exception:
    try:
        from PyQt5 import QtWidgets, QtCore
    except Exception as exc:
        raise ImportError('Qt bindings not available for Validated Maps Viewer') from exc

class ValidatedMapsViewer(QtWidgets.QWidget):
    def __init__(self, parent: Optional[Any] = None):
        super().__init__(parent)
        self.setWindowTitle('Validated Maps Viewer')
        layout = QtWidgets.QVBoxLayout(self)

        # Top controls: search, category filter, export, apply
        controls = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText('Search maps by name or offset...')
        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.addItem('All')
        for c in validated_maps.MapCategory:
            self.category_combo.addItem(c.value)
        self.export_btn = QtWidgets.QPushButton('Export CSV')
        self.apply_btn = QtWidgets.QPushButton('Apply Selected Map')
        self.apply_btn.setToolTip('Queue selected map for flashing via Flasher Wizard')
        controls.addWidget(self.search_edit)
        controls.addWidget(self.category_combo)
        controls.addWidget(self.export_btn)
        controls.addWidget(self.apply_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.tabs = QtWidgets.QTabWidget()
        layout.addWidget(self.tabs)

        # Validated Maps Tab
        self.validated_table = QtWidgets.QTableWidget()
        self.validated_table.setColumnCount(6)
        self.validated_table.setHorizontalHeaderLabels([
            'Name', 'Offset', 'Size', 'Category', 'Status', 'Warnings'
        ])
        self._populate_validated_maps()
        self.search_edit.textChanged.connect(self._on_filter_changed)
        self.category_combo.currentIndexChanged.connect(self._on_filter_changed)
        self.export_btn.clicked.connect(self._on_export_csv)
        self.apply_btn.clicked.connect(self._on_apply_selected)
        self.tabs.addTab(self.validated_table, 'Validated Maps')

        # Rejected Maps Tab
        self.rejected_table = QtWidgets.QTableWidget()
        self.rejected_table.setColumnCount(5)
        self.rejected_table.setHorizontalHeaderLabels([
            'Name', 'Offset', 'Size', 'Status', 'Warnings'
        ])
        self._populate_rejected_maps()
        self.tabs.addTab(self.rejected_table, 'Rejected Maps')

        # Forbidden Regions Tab
        self.forbidden_table = QtWidgets.QTableWidget()
        self.forbidden_table.setColumnCount(3)
        self.forbidden_table.setHorizontalHeaderLabels([
            'Start', 'End', 'Reason'
        ])
        self._populate_forbidden_regions()
        self.tabs.addTab(self.forbidden_table, 'Forbidden Regions')

    def _populate_validated_maps(self):
        # Fill the table using current filter settings
        maps = validated_maps.get_all_safe_maps()
        self._all_maps = maps
        self._refresh_validated_maps_table()

    def _refresh_validated_maps_table(self):
        term = self.search_edit.text().strip().lower() if hasattr(self, 'search_edit') else ''
        category = self.category_combo.currentText() if hasattr(self, 'category_combo') else 'All'

        filtered = []
        for m in getattr(self, '_all_maps', validated_maps.get_all_safe_maps()):
            if category != 'All' and m.category.value != category:
                continue
            if term:
                if term in m.name.lower() or term in f"0x{m.offset:06X}".lower():
                    filtered.append(m)
            else:
                filtered.append(m)

        self.validated_table.setRowCount(len(filtered))
        for i, m in enumerate(filtered):
            self.validated_table.setItem(i, 0, QtWidgets.QTableWidgetItem(m.name))
            self.validated_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"0x{m.offset:06X}"))
            self.validated_table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(m.size_bytes)))
            self.validated_table.setItem(i, 3, QtWidgets.QTableWidgetItem(str(m.category.value)))
            self.validated_table.setItem(i, 4, QtWidgets.QTableWidgetItem(str(m.status.value)))
            self.validated_table.setItem(i, 5, QtWidgets.QTableWidgetItem(", ".join(m.warnings)))
        self.validated_table.resizeColumnsToContents()

    def _on_filter_changed(self):
        self._refresh_validated_maps_table()

    def _on_export_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export Validated Maps', 'validated_maps.csv', 'CSV Files (*.csv);;All Files (*)')
        if not path:
            return
        try:
            # Export currently visible rows
            rows = self.validated_table.rowCount()
            cols = self.validated_table.columnCount()
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # headers
                headers = [self.validated_table.horizontalHeaderItem(c).text() for c in range(cols)]
                writer.writerow(headers)
                for r in range(rows):
                    row = []
                    for c in range(cols):
                        it = self.validated_table.item(r, c)
                        row.append(it.text() if it is not None else '')
                    writer.writerow(row)
            QtWidgets.QMessageBox.information(self, 'Exported', f'Validated maps exported to {path}')
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Export failed', f'Could not export CSV: {e}')

    def _populate_rejected_maps(self):
        maps = validated_maps.REJECTED_MAPS.values()
        self.rejected_table.setRowCount(len(list(maps)))
        for i, m in enumerate(maps):
            self.rejected_table.setItem(i, 0, QtWidgets.QTableWidgetItem(m.name))
            self.rejected_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"0x{m.offset:06X}"))
            self.rejected_table.setItem(i, 2, QtWidgets.QTableWidgetItem(str(m.size_bytes)))
            self.rejected_table.setItem(i, 3, QtWidgets.QTableWidgetItem(str(m.status.value)))
            self.rejected_table.setItem(i, 4, QtWidgets.QTableWidgetItem(", ".join(m.warnings)))
        self.rejected_table.resizeColumnsToContents()

    def _populate_forbidden_regions(self):
        regions = validated_maps.FORBIDDEN_REGIONS
        self.forbidden_table.setRowCount(len(regions))
        for i, (start, end, reason) in enumerate(regions):
            self.forbidden_table.setItem(i, 0, QtWidgets.QTableWidgetItem(f"0x{start:06X}"))
            self.forbidden_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"0x{end-1:06X}"))
            self.forbidden_table.setItem(i, 2, QtWidgets.QTableWidgetItem(reason))
        self.forbidden_table.resizeColumnsToContents()

    def _on_apply_selected(self):
        """Apply selected validated map to flasher wizard."""
        current_row = self.validated_table.currentRow()
        if current_row < 0:
            QtWidgets.QMessageBox.warning(self, 'No Selection', 'Select a map from the table first.')
            return
        
        # Get map name from current row
        name_item = self.validated_table.item(current_row, 0)
        if name_item is None:
            return
        
        map_name = name_item.text()
        QtWidgets.QMessageBox.information(
            self, 
            'Map Selected', 
            f'Map "{map_name}" selected.\n\nUse the Flasher Wizard to load this map file and apply changes.'
        )
        # Optionally emit a signal or call a callback if implemented in parent app

def create_qt_widget(parent: Optional[Any] = None):
    return ValidatedMapsViewer(parent)
