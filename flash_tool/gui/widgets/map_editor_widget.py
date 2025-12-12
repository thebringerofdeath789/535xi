"""Qt-backed Map Editor widget implementation.

This module contains the Qt-dependent widget factory used by
`flash_tool.gui.widgets.map_editor.create_qt_widget` via a lazy import.
Keeping Qt imports inside this file prevents importing Qt when the
controller-only unit tests import the lightweight `map_editor` scaffold.
"""
from typing import Any
from pathlib import Path

try:
    from PySide6 import QtWidgets, QtCore
except Exception:
    try:
        from PyQt5 import QtWidgets, QtCore
    except Exception as exc:
        raise ImportError('Qt bindings not available for Map Editor') from exc

from flash_tool.gui.widgets.map_preview import MapPreviewDialog
from flash_tool.gui.patch_manifest import make_manifest, write_manifest
import zlib
from flash_tool import validated_maps


def create_qt_widget(controller: Any, parent: Any = None):
    class MapEditorWidget(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._ctrl = controller
            self._current_mapdef = None
            self._current_model = None

            layout = QtWidgets.QVBoxLayout(self)

            # In-development warning
            warning = QtWidgets.QLabel(
                "⚠ MAP EDITOR: In Development\n"
                "This tool is for advanced map editing. Hex preview is read-only. "
                "Validate changes before applying to ECU."
            )
            warning.setStyleSheet("color: #ff6; background: #332; padding: 10px; border-radius: 5px;")
            warning.setWordWrap(True)
            layout.addWidget(warning)

            # file selector row
            file_row = QtWidgets.QHBoxLayout()
            self.file_edit = QtWidgets.QLineEdit()
            self.browse_btn = QtWidgets.QPushButton('Browse...')
            file_row.addWidget(QtWidgets.QLabel('Calibration binary:'))
            file_row.addWidget(self.file_edit)
            file_row.addWidget(self.browse_btn)
            layout.addLayout(file_row)

            h = QtWidgets.QHBoxLayout()
            self.list_widget = QtWidgets.QListWidget()
            self.load_btn = QtWidgets.QPushButton('Load Map')
            self.preview_btn = QtWidgets.QPushButton('Preview')
            self.export_btn = QtWidgets.QPushButton('Export Patch')
            self.undo_btn = QtWidgets.QPushButton('Undo')
            self.redo_btn = QtWidgets.QPushButton('Redo')
            self.save_btn = QtWidgets.QPushButton('Validate Map')
            h.addWidget(self.load_btn)
            h.addWidget(self.preview_btn)
            h.addWidget(self.export_btn)
            h.addWidget(self.undo_btn)
            h.addWidget(self.redo_btn)
            h.addWidget(self.save_btn)

            layout.addLayout(h)
            # file selection row
            file_row = QtWidgets.QHBoxLayout()
            self.file_edit = QtWidgets.QLineEdit()
            self.browse_btn = QtWidgets.QPushButton('Browse')
            self.load_file_btn = QtWidgets.QPushButton('Load From File')
            file_row.addWidget(self.file_edit)
            file_row.addWidget(self.browse_btn)
            file_row.addWidget(self.load_file_btn)
            layout.addLayout(file_row)

            layout.addWidget(self.list_widget)

            # Tabs for grid editor and hex preview
            self.tabs = QtWidgets.QTabWidget()
            
            # Grid editor tab (populated after loading a map)
            self.table = QtWidgets.QTableWidget()
            self.table.setEditTriggers(QtWidgets.QTableWidget.DoubleClicked | QtWidgets.QTableWidget.EditKeyPressed)
            self.tabs.addTab(self.table, "Grid Editor")
            
            # Hex preview tab (read-only)
            self.hex_text = QtWidgets.QPlainTextEdit()
            self.hex_text.setReadOnly(True)
            self.hex_text.setStyleSheet("font-family: monospace; font-size: 9pt;")
            self.tabs.addTab(self.hex_text, "Hex Preview")
            
            layout.addWidget(self.tabs)

            # populate list
            try:
                for m in self._ctrl.list_maps():
                    self.list_widget.addItem(str(m))
            except Exception:
                pass

            self.browse_btn.clicked.connect(self._on_browse)
            self.load_btn.clicked.connect(self._on_load)
            self.preview_btn.clicked.connect(self._on_preview)
            self.export_btn.clicked.connect(self._on_export)
            self.undo_btn.clicked.connect(self._do_undo)
            self.redo_btn.clicked.connect(self._do_redo)
            self.save_btn.clicked.connect(self._on_save)
            self.browse_btn.clicked.connect(self._on_browse)
            self.load_file_btn.clicked.connect(self._on_load_from_file)

        def _on_load(self):
            item = self.list_widget.currentItem()
            if not item:
                return
            ident = item.text()
            # Prefer loading from a selected binary if provided
            file_path = (self.file_edit.text() or '').strip()
            if file_path:
                res = self._ctrl.load_map_from_file(ident, file_path)
            else:
                res = self._ctrl.load_map(ident)

            if res.get('success'):
                try:
                    self._current_mapdef = res.get('mapdef')
                    self._current_model = res.get('model')
                    # capture original bytes if available
                    self._orig_bytes = res.get('orig_bytes')
                except Exception:
                    self._current_mapdef = None
                    self._current_model = None
                # populate grid from model
                try:
                    self._populate_grid_from_model()
                except Exception:
                    pass
                QtWidgets.QMessageBox.information(self, 'Map Loaded', f'Loaded {ident}')
            else:
                QtWidgets.QMessageBox.warning(self, 'Load Failed', str(res.get('error')))

        def _on_browse(self):
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select calibration binary', '', 'Binary Files (*.bin);;All Files (*)')
            if path:
                self.file_edit.setText(path)

        def _on_preview(self):
            if self._current_model is None or self._current_mapdef is None:
                QtWidgets.QMessageBox.information(self, 'No data', 'Load a validated map first')
                return
            rows = int(self._current_mapdef.rows or 0)
            cols = int(self._current_mapdef.cols or 0)
            data = self._current_model.export_bytes()
            dlg = MapPreviewDialog(rows, cols, data, parent=self)
            dlg.exec()

        def _on_export(self):
            if self._current_model is None or self._current_mapdef is None:
                QtWidgets.QMessageBox.information(self, 'No data', 'Load and modify a validated map first')
                return
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save Patch', 'patch.bin', 'Binary Files (*.bin);;All Files (*)')
            if not path:
                return

            try:
                # Use the controller's export_patch with auto CRC calculation
                res = self._ctrl.export_patch(
                    self._current_model,
                    self._current_mapdef,
                    vin='',
                    write_path=path,
                    auto_calc_crcs=True
                )
                
                if res.get('success'):
                    msg = f"Patch exported to {path}"
                    if res.get('manifest_path'):
                        msg += f"\nManifest: {res['manifest_path']}"
                    if res.get('manifest', {}).get('affected_crc_zones'):
                        zones = res['manifest']['affected_crc_zones']
                        msg += f"\nAffected CRC zones: {len(zones)} zone(s)"
                    QtWidgets.QMessageBox.information(self, 'Export Successful', msg)
                else:
                    QtWidgets.QMessageBox.warning(self, 'Export Failed', f"Error: {res.get('error', 'Unknown error')}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, 'Export Failed', f'Could not export patch: {e}')

        def _on_save(self):
            item = self.list_widget.currentItem()
            if not item:
                return
            ident = item.text()
            # Delegate to controller for non-destructive validation of the
            # current map payload. Persistent changes must be exported as a
            # patch and flashed via the flasher wizard.
            res = self._ctrl.save_map(ident, self._current_model or b'')
            if res.get('success'):
                QtWidgets.QMessageBox.information(
                    self,
                    'Map Validated',
                    f"{ident} validated successfully. No file has been written; "
                    "use 'Export Patch' to save changes for flashing.",
                )
            else:
                QtWidgets.QMessageBox.warning(self, 'Save Failed', str(res.get('error')))

        def _on_browse(self):
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Select binary', '', 'Binary Files (*.bin);;All Files (*)')
            if path:
                self.file_edit.setText(path)

        def _on_load_from_file(self):
            file_path = (self.file_edit.text() or '').strip()
            if not file_path:
                QtWidgets.QMessageBox.warning(self, 'No file', 'Select a calibration binary first')
                return
            item = self.list_widget.currentItem()
            if not item:
                QtWidgets.QMessageBox.warning(self, 'No map selected', 'Select a validated map to load from file')
                return
            ident = item.text()
            res = self._ctrl.load_map_from_file(ident, file_path)
            if res.get('success'):
                self._current_mapdef = res.get('mapdef')
                self._current_model = res.get('model')
                try:
                    self._populate_grid_from_model()
                except Exception:
                    pass
                QtWidgets.QMessageBox.information(self, 'Loaded', f'Loaded {ident} from file')
            else:
                QtWidgets.QMessageBox.warning(self, 'Load Failed', str(res.get('error')))

        def _populate_grid_from_model(self):
            if self._current_model is None:
                return
            rows, cols = self._current_model.shape()
            try:
                self.table.blockSignals(True)
                self.table.clear()
                self.table.setRowCount(rows)
                self.table.setColumnCount(cols)
                for r in range(rows):
                    for c in range(cols):
                        val = self._current_model.get(r, c)
                        item = QtWidgets.QTableWidgetItem(str(val))
                        item.setTextAlignment(QtCore.Qt.AlignCenter)
                        self.table.setItem(r, c, item)
                self.table.resizeColumnsToContents()
            finally:
                self.table.blockSignals(False)

            # Update hex preview (read-only)
            try:
                data = self._current_model.export_bytes()
                hex_lines = []
                for i in range(0, len(data), 16):
                    chunk = data[i:i+16]
                    hex_str = ' '.join(f'{b:02X}' for b in chunk)
                    ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                    hex_lines.append(f"{i:08X}  {hex_str:<48}  {ascii_str}")
                self.hex_text.setPlainText('\n'.join(hex_lines))
            except Exception:
                self.hex_text.setPlainText("(Hex preview unavailable)")

            # connect after population
            try:
                self.table.itemChanged.disconnect(self._on_item_changed)
            except Exception:
                # It is safe if there was no existing connection yet.
                pass
            self.table.itemChanged.connect(self._on_item_changed)

        def _on_item_changed(self, item: QtWidgets.QTableWidgetItem):
            if self._current_model is None:
                return
            r = item.row()
            c = item.column()
            txt = item.text().strip()
            try:
                if txt.lower().startswith('0x'):
                    v = int(txt, 16)
                elif txt.lower().endswith('h'):
                    v = int(txt[:-1], 16)
                else:
                    v = int(txt)
                if v < 0:
                    v = 0
                if v > 255:
                    v = 255
            except Exception:
                v = 0
                item.setText('0')

            try:
                self._current_model.set(r, c, v, record_undo=True)
            except Exception:
                pass

        def _do_undo(self):
            if self._current_model is None:
                return
            ok = self._current_model.undo()
            if ok:
                self._populate_grid_from_model()

        def _do_redo(self):
            if self._current_model is None:
                return
            ok = self._current_model.redo()
            if ok:
                self._populate_grid_from_model()

    return MapEditorWidget(parent)
