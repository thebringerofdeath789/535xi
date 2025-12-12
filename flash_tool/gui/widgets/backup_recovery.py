"""Backup & Recovery controller and Qt widget.

Provides VIN-scoped backup management: full backup, calibration-only backup,
list/verify backups, and restore from a selected backup. Uses existing
`map_flasher` and `backup_manager` APIs.

Enhanced with:
- Table columns: VIN, backup_type, created_at, file_size, ecu_type
- Right-hand detail panel showing metadata for selected backup
- Confirmation dialog before restore
- operation_logger entries for all operations
- Standardized {success, error, details} return objects
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime

from flash_tool.gui.worker import Worker, CancelToken


class BackupRecoveryController:
    def __init__(self, map_flasher_module: Optional[Any] = None, backup_manager_module: Optional[Any] = None, log_controller: Optional[Any] = None):
        if map_flasher_module is None:
            try:
                from flash_tool import map_flasher as _mf
                map_flasher_module = _mf
            except Exception:
                map_flasher_module = None
        if backup_manager_module is None:
            try:
                from flash_tool import backup_manager as _bm
                backup_manager_module = _bm
            except Exception:
                backup_manager_module = None

        self.map_flasher = map_flasher_module
        self.backup_manager = backup_manager_module
        self.log_controller = log_controller

    # ---------------------- Logging helper ----------------------
    def _log(self, message: str, level: str = "info") -> None:
        """Log to operation_logger and UI log controller."""
        try:
            from flash_tool.operation_logger import get_logger
            logger = get_logger()
            if level == "error":
                logger.error(message)
            elif level == "warning":
                logger.warning(message)
            else:
                logger.info(message)
        except Exception:
            pass
        
        try:
            if self.log_controller:
                self.log_controller.append(f"[{level.upper()}] {message}")
        except Exception:
            pass

    # ----------------------- Query/Listing helpers -----------------------
    def list_backups(self, vin: Optional[str] = None) -> List[Dict[str, Any]]:
        """List backups with enhanced metadata."""
        try:
            if self.backup_manager is None:
                return []
            backups = self.backup_manager.list_backups(vin=vin)
            # Enhance with additional metadata if possible
            enhanced = []
            for backup in backups:
                try:
                    backup['created_at'] = backup.get('date', 'Unknown')
                    backup['backup_type'] = backup.get('type', 'full')
                    # Ensure file_size is in MB
                    if 'file_size_mb' not in backup and 'file_size' in backup:
                        backup['file_size_mb'] = backup['file_size'] / (1024 * 1024)
                except Exception:
                    pass
                enhanced.append(backup)
            return enhanced
        except Exception as e:
            self._log(f"Failed to list backups: {e}", "error")
            return []

    def verify_backup(self, file_path: str) -> Dict[str, Any]:
        """Verify backup with standardized return format."""
        try:
            if self.backup_manager is None:
                return {
                    'success': False,
                    'error': 'backup manager unavailable',
                    'details': {}
                }
            result = self.backup_manager.verify_backup(Path(file_path))
            return {
                'success': result.get('valid', False),
                'error': None if result.get('valid') else ', '.join(result.get('errors', [])),
                'details': result
            }
        except Exception as e:
            self._log(f"Backup verification failed: {e}", "error")
            return {
                'success': False,
                'error': str(e),
                'details': {}
            }

    # ----------------------------- Operations --------------------------------
    def backup_full(self, vin: Optional[str] = None, progress_cb=None, cancel_token: Optional[CancelToken] = None) -> Dict[str, Any]:
        """Full ECU backup with standardized return format."""
        try:
            if self.map_flasher is None:
                return {
                    'success': False,
                    'error': 'map_flasher unavailable',
                    'details': {}
                }
            result = self.map_flasher.read_full_flash(vin=vin, progress_callback=progress_cb)
            success = result.get('success', False)
            self._log(
                f"Full ECU backup {'completed' if success else 'failed'}: {result.get('filepath', 'N/A')}",
                "info" if success else "error"
            )
            return {
                'success': success,
                'error': result.get('error') if not success else None,
                'details': result
            }
        except Exception as e:
            self._log(f"Full backup operation failed: {e}", "error")
            return {
                'success': False,
                'error': str(e),
                'details': {}
            }

    def backup_calibration(self, vin: Optional[str] = None, progress_cb=None, cancel_token: Optional[CancelToken] = None) -> Dict[str, Any]:
        """Calibration-only backup with standardized return format."""
        try:
            if self.map_flasher is None:
                return {
                    'success': False,
                    'error': 'map_flasher unavailable',
                    'details': {}
                }
            result = self.map_flasher.read_calibration_area(vin=vin, progress_callback=progress_cb)
            success = result.get('success', False)
            self._log(
                f"Calibration backup {'completed' if success else 'failed'}: {result.get('filepath', 'N/A')}",
                "info" if success else "error"
            )
            return {
                'success': success,
                'error': result.get('error') if not success else None,
                'details': result
            }
        except Exception as e:
            self._log(f"Calibration backup operation failed: {e}", "error")
            return {
                'success': False,
                'error': str(e),
                'details': {}
            }

    def restore_backup(self, file_path: str, vin: str, progress_cb=None, cancel_token: Optional[CancelToken] = None) -> Dict[str, Any]:
        """Restore from backup with standardized return format."""
        try:
            if self.map_flasher is None:
                return {
                    'success': False,
                    'error': 'map_flasher unavailable',
                    'details': {}
                }
            result = self.map_flasher.restore_from_backup(
                Path(file_path), vin=vin, safety_confirmed=True, progress_callback=progress_cb
            )
            success = result.get('success', False)
            self._log(
                f"ECU restore {'completed' if success else 'failed'} from {Path(file_path).name} (VIN: {vin})",
                "info" if success else "error"
            )
            return {
                'success': success,
                'error': result.get('error') if not success else None,
                'details': result
            }
        except Exception as e:
            self._log(f"Restore operation failed: {e}", "error")
            return {
                'success': False,
                'error': str(e),
                'details': {}
            }


def create_qt_widget(controller: BackupRecoveryController, parent: Optional[Any] = None):
    try:
        from PySide6 import QtWidgets, QtCore
    except Exception:
        try:
            from PyQt5 import QtWidgets, QtCore
        except Exception as exc:
            raise ImportError('Qt bindings not available for Backup & Recovery') from exc

    class _Widget(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._ctrl = controller
            self._worker: Optional[Worker] = None
            self._cancel: Optional[CancelToken] = None

            layout = QtWidgets.QVBoxLayout(self)

            # Top row: VIN filter and refresh
            top_h = QtWidgets.QHBoxLayout()
            self.vin_edit = QtWidgets.QLineEdit()
            self.vin_edit.setPlaceholderText('VIN filter (optional)')
            self.refresh_btn = QtWidgets.QPushButton('Refresh')
            top_h.addWidget(QtWidgets.QLabel('VIN:'))
            top_h.addWidget(self.vin_edit)
            top_h.addWidget(self.refresh_btn)
            layout.addLayout(top_h)

            # Actions row
            actions_h = QtWidgets.QHBoxLayout()
            self.backup_full_btn = QtWidgets.QPushButton('Backup Full ECU')
            self.backup_cal_btn = QtWidgets.QPushButton('Backup Calibration Only')
            self.verify_btn = QtWidgets.QPushButton('Verify Selected')
            self.restore_btn = QtWidgets.QPushButton('Restore Selected')
            actions_h.addWidget(self.backup_full_btn)
            actions_h.addWidget(self.backup_cal_btn)
            actions_h.addWidget(self.verify_btn)
            actions_h.addWidget(self.restore_btn)
            layout.addLayout(actions_h)

            # Main content: table on left, detail panel on right
            content_h = QtWidgets.QHBoxLayout()
            
            # Left side: table
            left_widget = QtWidgets.QWidget()
            left_layout = QtWidgets.QVBoxLayout(left_widget)
            left_layout.setContentsMargins(0, 0, 0, 0)
            
            self.table = QtWidgets.QTableWidget()
            self.table.setColumnCount(6)
            self.table.setHorizontalHeaderLabels([
                'Filename', 'VIN', 'ECU Type', 'Backup Type', 'Created At', 'Size (MB)'
            ])
            self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.table.itemSelectionChanged.connect(self._on_backup_selected)
            left_layout.addWidget(self.table)
            
            content_h.addWidget(left_widget, 2)
            
            # Right side: detail panel
            detail_widget = QtWidgets.QWidget()
            detail_layout = QtWidgets.QVBoxLayout(detail_widget)
            detail_layout.setContentsMargins(10, 0, 0, 0)
            
            detail_title = QtWidgets.QLabel("Backup Details")
            detail_title.setStyleSheet("font-weight: bold; font-size: 12px;")
            detail_layout.addWidget(detail_title)
            
            self.detail_text = QtWidgets.QPlainTextEdit()
            self.detail_text.setReadOnly(True)
            self.detail_text.setMaximumWidth(300)
            detail_layout.addWidget(self.detail_text)
            detail_layout.addStretch()
            
            content_h.addWidget(detail_widget, 1)
            
            layout.addLayout(content_h, 1)

            # Progress bar
            self.progress = QtWidgets.QProgressBar()
            self.progress.setRange(0, 100)
            layout.addWidget(self.progress)
            
            # Output log
            self.output = QtWidgets.QPlainTextEdit()
            self.output.setReadOnly(True)
            self.output.setMaximumHeight(120)
            layout.addWidget(self.output)

            # Wire signals
            self.refresh_btn.clicked.connect(self._on_refresh)
            self.backup_full_btn.clicked.connect(self._on_backup_full)
            self.backup_cal_btn.clicked.connect(self._on_backup_cal)
            self.verify_btn.clicked.connect(self._on_verify)
            self.restore_btn.clicked.connect(self._on_restore)

            # Initial load
            self._on_refresh()

        def _append(self, text: str):
            """Append to output log and operation_logger."""
            try:
                self.output.appendPlainText(text)
                if hasattr(self._ctrl, '_log'):
                    self._ctrl._log(text)
            except Exception:
                pass

        def _on_backup_selected(self):
            """Show details for selected backup."""
            try:
                row = self.table.currentRow()
                if row < 0:
                    self.detail_text.setPlainText("")
                    return
                
                details = []
                for col in range(self.table.columnCount()):
                    header = self.table.horizontalHeaderItem(col).text()
                    value = self.table.item(row, col).text()
                    details.append(f"{header}: {value}")
                
                self.detail_text.setPlainText("\n".join(details))
            except Exception:
                self.detail_text.setPlainText("")

        def _selected_backup_path(self) -> Optional[str]:
            """Get full path to selected backup."""
            try:
                row = self.table.currentRow()
                if row < 0:
                    return None
                fn = self.table.item(row, 0).text()
                vin = self.table.item(row, 1).text()
                # reconstruct expected path: backups/<VIN>/<filename>
                try:
                    from flash_tool import backup_manager
                    base = backup_manager.get_backups_directory() / vin
                    return str((base / fn).absolute())
                except Exception:
                    return fn
            except Exception:
                return None

        def _populate(self, items: List[Dict[str, Any]]):
            """Populate table with backup items."""
            self.table.setRowCount(len(items))
            for i, info in enumerate(items):
                def _set(col, val):
                    try:
                        self.table.setItem(i, col, QtWidgets.QTableWidgetItem(str(val)))
                    except Exception:
                        pass
                _set(0, info.get('filename', ''))
                _set(1, info.get('vin', ''))
                _set(2, info.get('ecu_type', ''))
                _set(3, info.get('backup_type', 'full'))
                _set(4, info.get('created_at', ''))
                _set(5, f"{float(info.get('file_size_mb', 0.0)):.2f}")
            try:
                self.table.resizeColumnsToContents()
            except Exception:
                pass

        def _on_refresh(self):
            """Refresh backup list."""
            vin = self.vin_edit.text().strip() or None
            try:
                items = self._ctrl.list_backups(vin=vin)
            except Exception as e:
                items = []
                self._append(f"Error listing backups: {e}")
            self._populate(items)
            self._append(f"Listed {len(items)} backup(s)")
            self.detail_text.setPlainText("")

        def _run(self, func, on_done):
            # Ensure any existing worker is stopped
            if getattr(self, '_worker', None) and self._worker.is_alive():
                try:
                    if getattr(self, '_cancel', None):
                        self._cancel.request_cancel()
                except Exception:
                    pass
            self._cancel = CancelToken()

            def ui_progress(evt):
                try:
                    pct = int(getattr(evt, 'progress', 0))
                    msg = getattr(evt, 'message', '')
                    if pct:
                        try:
                            self.progress.setValue(pct)
                        except Exception:
                            pass
                    if msg:
                        self._append(msg)
                except Exception:
                    pass

            self._worker = Worker(task=func, progress_cb=ui_progress, cancel_token=self._cancel)
            self._worker.start()

            def poll():
                if self._worker.is_alive():
                    QtCore.QTimer.singleShot(200, poll)
                    return
                try:
                    res = self._worker.result()
                except Exception as e:
                    res = {'success': False, 'error': str(e)}
                try:
                    on_done(res)
                except Exception:
                    pass

            QtCore.QTimer.singleShot(200, poll)

        def _on_backup_full(self):
            """Start full ECU backup in background worker."""
            vin = self.vin_edit.text().strip() or None
            self.progress.setValue(0)
            self._append('Starting full ECU backup...')
            self._run(lambda progress_cb=None, cancel_token=None: self._ctrl.backup_full(vin=vin, progress_cb=progress_cb, cancel_token=cancel_token), self._after_backup)

        def _on_backup_cal(self):
            """Start calibration-only backup in background worker."""
            vin = self.vin_edit.text().strip() or None
            self.progress.setValue(0)
            self._append('Starting calibration-only backup...')
            self._run(lambda progress_cb=None, cancel_token=None: self._ctrl.backup_calibration(vin=vin, progress_cb=progress_cb, cancel_token=cancel_token), self._after_backup)

        def _after_backup(self, res):
            """Handle backup completion."""
            if isinstance(res, dict) and res.get('success'):
                details = res.get('details', {})
                path = details.get('filepath')
                size = details.get('file_size')
                self._append(f"✓ Backup saved: {path} ({size} bytes)")
                self.progress.setValue(100)
                self._on_refresh()
            else:
                error = res.get('error') if isinstance(res, dict) else str(res)
                self._append(f"✗ Backup failed: {error}")
                self.progress.setValue(0)

        def _on_verify(self):
            """Verify selected backup."""
            path = self._selected_backup_path()
            if not path:
                self._append('No backup selected')
                return
            res = self._ctrl.verify_backup(path)
            if res.get('success'):
                details = res.get('details', {})
                self._append(f"✓ Backup valid — size={details.get('file_size')} checksum={str(details.get('checksum', ''))[:16]}...")
            else:
                error = res.get('error')
                self._append(f"✗ Backup invalid: {error}")

        def _on_restore(self):
            """Restore from selected backup with confirmation dialog."""
            path = self._selected_backup_path()
            if not path:
                self._append('No backup selected')
                return

            # Confirmation dialog
            reply = QtWidgets.QMessageBox.question(
                self,
                "Confirm ECU Restore",
                f"Restore ECU from:\n{Path(path).name}\n\n"
                "This will overwrite the current ECU flash.\n"
                "Make sure you have a verified backup first!",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                self._append('Restore cancelled')
                return

            # Get VIN (best-effort)
            ecu_vin_full = None
            try:
                from flash_tool.direct_can_flasher import DirectCANFlasher
                flasher = DirectCANFlasher()
                if flasher.connect():
                    v = flasher.read_vin() or ''
                    try:
                        flasher.disconnect()
                    except Exception:
                        pass
                    if v:
                        ecu_vin_full = v
            except Exception:
                ecu_vin_full = None

            self.progress.setValue(0)
            self._append(f'Restoring from backup: {path}')
            
            # Determine VIN: typed > ECU > backup metadata
            vin_text = self.vin_edit.text().strip() or None
            vin_for_restore = vin_text or ecu_vin_full
            if vin_for_restore is None:
                try:
                    from flash_tool import backup_manager
                    info = backup_manager.get_backup_info(Path(path))
                    vin_for_restore = info.get('vin')
                except Exception:
                    vin_for_restore = None
            
            if not vin_for_restore:
                self._append('✗ Restore aborted: could not determine VIN for safety checks')
                return

            self._run(
                lambda progress_cb=None, cancel_token=None: self._ctrl.restore_backup(
                    path, vin=vin_for_restore, progress_cb=progress_cb, cancel_token=cancel_token
                ),
                self._after_restore,
            )

        def _after_restore(self, res):
            """Handle restore completion."""
            if isinstance(res, dict) and res.get('success'):
                self._append('✓ Restore completed successfully')
                self.progress.setValue(100)
            else:
                error = res.get('error') if isinstance(res, dict) else str(res)
                self._append(f"✗ Restore failed: {error}")
                self.progress.setValue(0)

    return _Widget(parent)
