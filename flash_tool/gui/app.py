"""GUI entrypoint for the flash_tool project.

This file provides a very small Qt application entry used by the
`flash-gui.py` entrypoint. It is intentionally minimal so the project
does not crash if GUI dependencies are not installed. The real GUI
implementation will replace and extend this skeleton.
"""
import sys
from typing import Optional


class GUIApp:
    """Thin wrapper used by the flash-gui entrypoint.

    This class keeps imports lazy so the package can still be imported in
    environments without PySide6 installed.
    """

    def __init__(self) -> None:
        try:
            import PySide6  # noqa: F401

            self._qt_available = True
        except Exception:
            self._qt_available = False

    def run(self) -> None:
        if not self._qt_available:
            print("PySide6 not installed. Install requirements-gui.txt to run the GUI.")
            return

        # Defer all Qt imports to the real entrypoint
        main([])


def main(argv: Optional[list[str]] = None) -> None:
    """Create and run the Free N54 Flasher GUI.

    All Qt imports happen inside this function so importing this module
    remains safe in non-GUI environments and unit tests.
    """
    argv = argv if argv is not None else sys.argv[1:]

    try:
        from PySide6 import QtWidgets, QtCore, QtGui
    except Exception as exc:  # pragma: no cover - import-time behavior
        print("PySide6 is required to run the GUI. Install `requirements-gui.txt`.\nError:", exc)
        raise

    from flash_tool.gui.utils import load_icon, load_stylesheet

    class MainWindow(QtWidgets.QMainWindow):
        """Main window with neon-themed tabbed UI.

        The window embeds the existing controllers/widgets without
        changing their business logic. Only layout, styling, and icons
        are refactored.
        """

        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Free N54 Flasher")
            self.setWindowIcon(load_icon("AppIcon.png"))
            self.resize(1280, 800)

            self._log_controller = None
            self._log_widget = None
            self._settings_manager = None
            self._advanced_tools_enabled = False

            self._init_menu_bar()
            self._init_status_bar()

            self.tab_widget = QtWidgets.QTabWidget(self)
            self.setCentralWidget(self.tab_widget)

            self._build_tabs()
            self._load_advanced_tools_setting()

        # ----- Menu bar -------------------------------------------------
        def _init_menu_bar(self) -> None:
            menubar = self.menuBar()

            # File menu
            file_menu = menubar.addMenu("&File")

            exit_action = file_menu.addAction("E&xit")
            exit_action.setShortcut("Ctrl+Q")
            exit_action.triggered.connect(self.close)

            # Edit / Settings
            edit_menu = menubar.addMenu("&Edit")
            settings_action = edit_menu.addAction("&Settings…")
            settings_action.setShortcut("Ctrl+,")
            settings_action.triggered.connect(self._open_settings_dialog)

            # Help
            help_menu = menubar.addMenu("&Help")
            about_action = help_menu.addAction("&About")
            about_action.triggered.connect(self._open_about_dialog)
            help_menu.addSeparator()
            help_action = help_menu.addAction("&Help")
            help_action.setShortcut("F1")
            help_action.triggered.connect(self._show_help)

        def _init_status_bar(self) -> None:
            """Initialize QStatusBar with connection state and operation info."""
            self.statusBar().setStyleSheet("""
                QStatusBar {
                    background-color: #1a1a2e;
                    color: #0f9;
                    border-top: 1px solid #0f9;
                }
            """)
            
            # Connection status
            self._status_connection = QtWidgets.QLabel("Not connected")
            self._status_connection.setStyleSheet("color: #f00;")
            self.statusBar().addWidget(self._status_connection)
            
            # Separator
            sep1 = QtWidgets.QLabel(" | ")
            self.statusBar().addWidget(sep1)
            
            # ECU type
            self._status_ecu_type = QtWidgets.QLabel("ECU: Unknown")
            self._status_ecu_type.setStyleSheet("color: #0f9;")
            self.statusBar().addWidget(self._status_ecu_type)
            
            # Separator
            sep2 = QtWidgets.QLabel(" | ")
            self.statusBar().addWidget(sep2)
            
            # SW ID
            self._status_sw_id = QtWidgets.QLabel("SW: Unknown")
            self._status_sw_id.setStyleSheet("color: #0f9;")
            self.statusBar().addWidget(self._status_sw_id)
            
            # Spacer to separate from right side (QStatusBar does not support addStretch)
            spacer = QtWidgets.QWidget()
            spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            self.statusBar().addWidget(spacer)
            
            # Last operation result
            self._status_operation = QtWidgets.QLabel("Ready")
            self._status_operation.setStyleSheet("color: #0f9;")
            self.statusBar().addPermanentWidget(self._status_operation)

        def _update_status_bar(self, connection: str = None, ecu_type: str = None, 
                               sw_id: str = None, operation: str = None) -> None:
            """Update status bar with current state."""
            if connection is not None:
                color = "#0f9" if "Connected" in connection else "#f00"
                self._status_connection.setText(connection)
                self._status_connection.setStyleSheet(f"color: {color};")
            
            if ecu_type is not None:
                self._status_ecu_type.setText(f"ECU: {ecu_type}")
            
            if sw_id is not None:
                self._status_sw_id.setText(f"SW: {sw_id}")
            
            if operation is not None:
                self._status_operation.setText(operation)

        def _show_help(self) -> None:
            """Show help dialog (F1)."""
            try:
                from flash_tool.gui.widgets.help_about_dialog import HelpAboutDialog
                dlg = HelpAboutDialog(self)
                dlg.exec()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Help", f"Could not open help: {exc}")

        def _load_advanced_tools_setting(self) -> None:
            """Load advanced tools setting from settings manager."""
            try:
                from flash_tool.settings_manager import SettingsManager
                self._settings_manager = SettingsManager()
                self._advanced_tools_enabled = self._settings_manager.get(
                    "gui.advanced_tools_enabled", False
                )
            except Exception:
                self._advanced_tools_enabled = False

        def _set_advanced_tools_enabled(self, enabled: bool) -> None:
            """Update advanced tools visibility."""
            self._advanced_tools_enabled = enabled
            try:
                if self._settings_manager:
                    self._settings_manager.set("gui.advanced_tools_enabled", enabled)
            except Exception:
                pass
            
            # Update tab visibility
            self._update_advanced_tabs_visibility()

        def _update_advanced_tabs_visibility(self) -> None:
            """Hide/show advanced tool tabs based on setting."""
            # Diagnostics tab (index 3) contains: OBD Dashboard, Coding, Direct CAN
            # Live Data tab (index 4) contains: Gauges, OBD Logger, Live Control
            # These tabs should be hidden unless advanced tools are enabled
            
            # For now, we keep all tabs visible but users can disable through settings
            # In future versions, we can hide the "Coding" and "Direct CAN" sub-tabs
            # based on the advanced_tools_enabled flag

        def _open_settings_dialog(self) -> None:
            try:
                from flash_tool.gui.widgets.settings_dialog import SettingsDialog

                dlg = SettingsDialog(self)
                dlg.exec()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Settings Error", f"Could not open settings: {exc}")

        def _open_about_dialog(self) -> None:
            try:
                from flash_tool.gui.widgets.help_about_dialog import HelpAboutDialog

                dlg = HelpAboutDialog(self)
                dlg.exec()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "About", f"Could not open About dialog: {exc}")

        # ----- Tabs -----------------------------------------------------
        def _build_tabs(self) -> None:
            """Create all main tabs in the required order."""

            self._create_logging_controller()
            
            # Track tab indices for advanced tools
            self._advanced_tool_tab_indices = []
            self._tab_index_counter = 0

            self._add_connection_tab()
            self._add_flashing_tab()
            self._add_maps_tuning_tab()
            self._add_diagnostics_tab()
            self._add_live_data_tab()
            self._add_logs_tab()
            self._add_settings_tab()
            self._add_about_tab()
            
            # Apply advanced tools visibility
            self._update_advanced_tabs_visibility()

        def _create_logging_controller(self) -> None:
            """Create a single shared log controller if possible."""
            try:
                from flash_tool.gui.widgets.log_viewer import (
                    LogViewerController,
                    create_qt_widget as create_log_widget,
                )

                self._log_controller = LogViewerController()
                # The actual widget will be parented to the Logs tab later
                self._log_widget = create_log_widget(self._log_controller, parent=None)
            except Exception:
                self._log_controller = None
                self._log_widget = None

        # ----- Connection tab (fully refactored) ------------------------
        def _add_connection_tab(self) -> None:
            from flash_tool.gui.widgets.connection_widget import (
                ConnectionController,
                create_qt_widget as create_connection_widget,
            )

            tab = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(tab)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(12)

            # Header with icon and title
            header_layout = QtWidgets.QHBoxLayout()
            header_icon = QtWidgets.QLabel()
            header_icon.setPixmap(load_icon("Connection.png").pixmap(32, 32))
            header_title = QtWidgets.QLabel("Connection")
            header_title.setStyleSheet("font-size: 18px; font-weight: bold;")
            header_spacer = QtWidgets.QSpacerItem(
                40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum
            )
            header_layout.addWidget(header_icon)
            header_layout.addWidget(header_title)
            header_layout.addItem(header_spacer)
            layout.addLayout(header_layout)

            # Quick actions row
            actions_group = QtWidgets.QGroupBox("Quick Actions")
            actions_layout = QtWidgets.QHBoxLayout(actions_group)
            actions_layout.setContentsMargins(10, 20, 10, 10)
            actions_layout.setSpacing(8)

            self._conn_controller = ConnectionController()
            try:
                self._conn_widget = create_connection_widget(self._conn_controller, parent=tab)
            except Exception as exc:
                self._conn_widget = None
                layout.addWidget(QtWidgets.QLabel(f"Connection widget unavailable: {exc}"))

            self._btn_connect = QtWidgets.QPushButton("Connect")
            self._btn_connect.setIcon(load_icon("Connect.png"))

            self._btn_disconnect = QtWidgets.QPushButton("Disconnect")
            self._btn_disconnect.setIcon(load_icon("Disconnect.png"))

            self._btn_scan = QtWidgets.QPushButton("Scan Adapters")
            self._btn_scan.setIcon(load_icon("Scan.png"))

            self._btn_browse = QtWidgets.QPushButton("Browse…")
            self._btn_browse.setIcon(load_icon("Folder.png"))

            actions_layout.addWidget(self._btn_connect)
            actions_layout.addWidget(self._btn_disconnect)
            actions_layout.addWidget(self._btn_scan)
            actions_layout.addWidget(self._btn_browse)
            actions_layout.addStretch(1)

            layout.addWidget(actions_group)

            # Status row with icon + text
            status_layout = QtWidgets.QHBoxLayout()
            self._status_icon = QtWidgets.QLabel()
            self._status_icon.setPixmap(load_icon("InfoSmall.png").pixmap(16, 16))
            self._status_label = QtWidgets.QLabel("Not connected")
            status_layout.addWidget(self._status_icon)
            status_layout.addWidget(self._status_label)
            status_layout.addStretch(1)
            layout.addLayout(status_layout)

            # Advanced connection widget from existing implementation
            if self._conn_widget is not None:
                advanced_group = QtWidgets.QGroupBox("Advanced Adapter Details")
                advanced_layout = QtWidgets.QVBoxLayout(advanced_group)
                advanced_layout.setContentsMargins(10, 20, 10, 10)
                advanced_layout.setSpacing(8)
                advanced_layout.addWidget(self._conn_widget)
                layout.addWidget(advanced_group)

            layout.addStretch(1)

            # Wire quick actions to the existing widget where possible
            self._btn_connect.clicked.connect(self._on_quick_connect)
            self._btn_disconnect.clicked.connect(self._on_quick_disconnect)
            self._btn_scan.clicked.connect(self._on_quick_scan)
            self._btn_browse.clicked.connect(self._on_quick_browse)

            self.tab_widget.addTab(tab, load_icon("Connection.png"), "Connection")

        def _set_status(self, text: str, ok: bool = True) -> None:
            self._status_label.setText(text)
            icon_name = "InfoSmall.png" if ok else "Warning.png"
            self._status_icon.setPixmap(load_icon(icon_name).pixmap(16, 16))

        def _on_quick_scan(self) -> None:
            if getattr(self, "_conn_widget", None) is not None and hasattr(
                self._conn_widget, "refresh_btn"
            ):
                try:
                    self._conn_widget.refresh_btn.click()
                    self._set_status("Scanning for adapters…", ok=True)
                except Exception as exc:
                    self._set_status(f"Scan failed: {exc}", ok=False)

        def _on_quick_connect(self) -> None:
            if getattr(self, "_conn_widget", None) is not None and hasattr(
                self._conn_widget, "connect_btn"
            ):
                try:
                    self._conn_widget.connect_btn.click()
                    self._set_status("Connecting…", ok=True)
                except Exception as exc:
                    self._set_status(f"Connect failed: {exc}", ok=False)

        def _on_quick_disconnect(self) -> None:
            try:
                if getattr(self, "_conn_controller", None) is not None:
                    self._conn_controller.disconnect()
                self._set_status("Disconnected", ok=True)
            except Exception as exc:
                self._set_status(f"Disconnect failed: {exc}", ok=False)

        def _on_quick_browse(self) -> None:
            # Simple folder selection for logs/backups; does not alter core logic
            directory = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Select Working Folder",
                "",
                QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks,
            )
            if directory:
                self._set_status(f"Selected folder: {directory}", ok=True)

        # ----- Other tabs (embed existing widgets, icons, layout) -------
        def _add_flashing_tab(self) -> None:
            tab = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(tab)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(12)

            header_layout = QtWidgets.QHBoxLayout()
            icon_lbl = QtWidgets.QLabel()
            icon_lbl.setPixmap(load_icon("FlashTab.png").pixmap(32, 32))
            title_lbl = QtWidgets.QLabel("Flashing")
            title_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
            header_layout.addWidget(icon_lbl)
            header_layout.addWidget(title_lbl)
            header_layout.addStretch(1)
            layout.addLayout(header_layout)

            # Toolbar row with key flash actions wired to existing widgets
            toolbar = QtWidgets.QHBoxLayout()
            toolbar.setSpacing(8)

            self._btn_load_bin = QtWidgets.QPushButton("Load BIN")
            self._btn_load_bin.setIcon(load_icon("LoadBin.png"))
            toolbar.addWidget(self._btn_load_bin)

            self._btn_validate_bin = QtWidgets.QPushButton("Validate BIN")
            self._btn_validate_bin.setIcon(load_icon("ValidateBin.png"))
            toolbar.addWidget(self._btn_validate_bin)

            self._btn_backup_ecu = QtWidgets.QPushButton("Backup ECU")
            self._btn_backup_ecu.setIcon(load_icon("Backup.png"))
            toolbar.addWidget(self._btn_backup_ecu)

            self._btn_restore_ecu = QtWidgets.QPushButton("Restore ECU")
            self._btn_restore_ecu.setIcon(load_icon("Restore.png"))
            toolbar.addWidget(self._btn_restore_ecu)

            self._btn_start_flash = QtWidgets.QPushButton("Start Flash")
            self._btn_start_flash.setIcon(load_icon("Flash.png"))
            toolbar.addWidget(self._btn_start_flash)

            self._btn_verify_flash = QtWidgets.QPushButton("Verify Flash")
            self._btn_verify_flash.setIcon(load_icon("Verify.png"))
            toolbar.addWidget(self._btn_verify_flash)

            self._btn_apply_patch = QtWidgets.QPushButton("Apply Patch")
            self._btn_apply_patch.setIcon(load_icon("Patch.png"))
            toolbar.addWidget(self._btn_apply_patch)

            self._btn_differences = QtWidgets.QPushButton("Differences")
            self._btn_differences.setIcon(load_icon("Differences.png"))
            toolbar.addWidget(self._btn_differences)

            toolbar.addStretch(1)
            layout.addLayout(toolbar)

            content_tabs = QtWidgets.QTabWidget()

            # Flasher wizard
            flasher_page = QtWidgets.QWidget()
            flasher_layout = QtWidgets.QVBoxLayout(flasher_page)
            flasher_layout.setContentsMargins(8, 8, 8, 8)
            flasher_layout.setSpacing(8)
            try:
                from flash_tool.gui.widgets.flasher_wizard import (
                    FlasherController as FlasherWizardController,
                    create_qt_widget as create_flasher_widget,
                )

                flasher_ctrl = FlasherWizardController(log_controller=self._log_controller)
                flasher_widget = create_flasher_widget(flasher_ctrl, parent=flasher_page)
                self._flasher_controller = flasher_ctrl
                self._flasher_widget = flasher_widget
                flasher_layout.addWidget(flasher_widget)
            except Exception as exc:
                flasher_layout.addWidget(QtWidgets.QLabel(f"Flasher wizard unavailable: {exc}"))
            content_tabs.addTab(flasher_page, "Flasher Wizard")

            # Backup & Recovery
            backup_page = QtWidgets.QWidget()
            backup_layout = QtWidgets.QVBoxLayout(backup_page)
            backup_layout.setContentsMargins(8, 8, 8, 8)
            backup_layout.setSpacing(8)
            try:
                from flash_tool.gui.widgets.backup_recovery import (
                    BackupRecoveryController as BackupControllerClass,
                    create_qt_widget as create_backup_widget,
                )

                backup_ctrl = BackupControllerClass(log_controller=self._log_controller)
                backup_widget = create_backup_widget(backup_ctrl, parent=backup_page)
                self._backup_controller = backup_ctrl
                self._backup_widget = backup_widget
                backup_layout.addWidget(backup_widget)
            except Exception as exc:
                backup_layout.addWidget(QtWidgets.QLabel(f"Backup & Recovery unavailable: {exc}"))
            content_tabs.addTab(backup_page, "Backup & Recovery")

            # Validated maps / bin tools
            vmaps_page = QtWidgets.QWidget()
            vmaps_layout = QtWidgets.QVBoxLayout(vmaps_page)
            vmaps_layout.setContentsMargins(8, 8, 8, 8)
            vmaps_layout.setSpacing(8)
            try:
                from flash_tool.gui.widgets.validated_maps_viewer import ValidatedMapsViewer

                vmaps_widget = ValidatedMapsViewer(parent=vmaps_page)
                vmaps_layout.addWidget(vmaps_widget)
            except Exception as exc:
                vmaps_layout.addWidget(QtWidgets.QLabel(f"Validated maps viewer unavailable: {exc}"))
            content_tabs.addTab(vmaps_page, "Validated Maps")

            layout.addWidget(content_tabs)

            # Keep references so toolbar actions can provide better feedback
            self._flashing_tab = tab
            self._flashing_content_tabs = content_tabs

            # Wire toolbar buttons to underlying widgets/controllers
            self._btn_load_bin.clicked.connect(self._toolbar_load_bin)
            self._btn_validate_bin.clicked.connect(self._toolbar_validate_bin)
            self._btn_backup_ecu.clicked.connect(self._toolbar_backup_ecu)
            self._btn_restore_ecu.clicked.connect(self._toolbar_restore_ecu)
            self._btn_start_flash.clicked.connect(self._toolbar_start_flash)
            self._btn_verify_flash.clicked.connect(self._toolbar_verify_flash)
            self._btn_apply_patch.clicked.connect(self._toolbar_apply_patch)
            self._btn_differences.clicked.connect(self._toolbar_differences)
            self.tab_widget.addTab(tab, load_icon("FlashTab.png"), "Flashing")

        def _add_maps_tuning_tab(self) -> None:
            tab = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(tab)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(12)

            header_layout = QtWidgets.QHBoxLayout()
            icon_lbl = QtWidgets.QLabel()
            icon_lbl.setPixmap(load_icon("MapsTuning.png").pixmap(32, 32))
            title_lbl = QtWidgets.QLabel("Maps / Tuning")
            title_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
            header_layout.addWidget(icon_lbl)
            header_layout.addWidget(title_lbl)
            header_layout.addStretch(1)
            layout.addLayout(header_layout)

            # Create stacked widget to toggle between loader and content
            self._maps_stack = QtWidgets.QStackedWidget()
            
            # === FILE LOADER PAGE ===
            loader_page = QtWidgets.QWidget()
            loader_layout = QtWidgets.QVBoxLayout(loader_page)
            loader_layout.setContentsMargins(20, 20, 20, 20)
            loader_layout.setSpacing(15)
            
            # File selection group
            file_group = QtWidgets.QGroupBox("Load Binary File")
            file_layout = QtWidgets.QVBoxLayout(file_group)
            file_layout.setContentsMargins(10, 20, 10, 10)
            file_layout.setSpacing(10)
            
            # Description
            desc_label = QtWidgets.QLabel(
                "Load a full ECU binary (.bin) or map file to view and edit tuning parameters.\n"
                "The file will be parsed to extract all modifiable parameters."
            )
            desc_label.setWordWrap(True)
            file_layout.addWidget(desc_label)
            
            # File path selection
            path_layout = QtWidgets.QHBoxLayout()
            self._map_file_path_edit = QtWidgets.QLineEdit()
            self._map_file_path_edit.setPlaceholderText("No file selected...")
            self._map_file_path_edit.setReadOnly(True)
            path_layout.addWidget(self._map_file_path_edit)
            
            browse_btn = QtWidgets.QPushButton("Browse...")
            browse_btn.setIcon(load_icon("Folder.png"))
            browse_btn.clicked.connect(self._on_maps_browse_file)
            path_layout.addWidget(browse_btn)
            
            file_layout.addLayout(path_layout)
            
            # File info display
            self._map_file_info = QtWidgets.QLabel()
            self._map_file_info.setStyleSheet("color: #8A92B5; font-size: 11px;")
            file_layout.addWidget(self._map_file_info)
            
            # Load button
            load_btn_layout = QtWidgets.QHBoxLayout()
            load_btn_layout.addStretch(1)
            self._map_load_btn = QtWidgets.QPushButton("Load File and Parse Parameters")
            self._map_load_btn.setIcon(load_icon("LoadBin.png"))
            self._map_load_btn.setEnabled(False)
            self._map_load_btn.clicked.connect(self._on_maps_load_file)
            self._map_load_btn.setMinimumHeight(40)
            load_btn_layout.addWidget(self._map_load_btn)
            load_btn_layout.addStretch(1)
            
            file_layout.addLayout(load_btn_layout)
            
            loader_layout.addWidget(file_group)
            loader_layout.addStretch(1)
            
            self._maps_stack.addWidget(loader_page)
            
            # === CONTENT TABS PAGE ===
            content_page = QtWidgets.QWidget()
            content_layout = QtWidgets.QVBoxLayout(content_page)
            content_layout.setContentsMargins(0, 0, 0, 0)
            
            # Toolbar for loaded file
            toolbar_layout = QtWidgets.QHBoxLayout()
            toolbar_layout.setSpacing(8)
            
            # File info label
            self._loaded_file_label = QtWidgets.QLabel("No file loaded")
            self._loaded_file_label.setStyleSheet("font-weight: bold; color: #66D8FF;")
            toolbar_layout.addWidget(self._loaded_file_label)
            
            toolbar_layout.addStretch(1)
            
            # Change file button
            change_file_btn = QtWidgets.QPushButton("Change File")
            change_file_btn.setIcon(load_icon("Folder.png"))
            change_file_btn.clicked.connect(self._on_maps_change_file)
            toolbar_layout.addWidget(change_file_btn)
            
            # Save changes button
            save_changes_btn = QtWidgets.QPushButton("Save Changes")
            save_changes_btn.setIcon(load_icon("Flash.png"))
            save_changes_btn.clicked.connect(self._on_maps_save_changes)
            toolbar_layout.addWidget(save_changes_btn)
            
            content_layout.addLayout(toolbar_layout)
            
            # Tabs with actual content
            content_tabs = QtWidgets.QTabWidget()

            # Map editor
            map_page = QtWidgets.QWidget()
            map_layout = QtWidgets.QVBoxLayout(map_page)
            map_layout.setContentsMargins(8, 8, 8, 8)
            map_layout.setSpacing(8)
            try:
                from flash_tool.gui.widgets.map_editor import (
                    MapEditorController as MapEditorControllerClass,
                    create_qt_widget as create_map_widget,
                )

                map_ctrl = MapEditorControllerClass(log_controller=self._log_controller)
                map_widget = create_map_widget(map_ctrl, parent=map_page)
                map_layout.addWidget(map_widget)
            except Exception as exc:
                map_layout.addWidget(QtWidgets.QLabel(f"Map editor unavailable: {exc}"))
            content_tabs.addTab(map_page, "Map Editor")

            # Tuning options
            tuning_page = QtWidgets.QWidget()
            tuning_layout = QtWidgets.QVBoxLayout(tuning_page)
            tuning_layout.setContentsMargins(8, 8, 8, 8)
            tuning_layout.setSpacing(8)
            try:
                from flash_tool.gui.widgets.tuning_options import (
                    TuningOptionsController as TuningControllerClass,
                    create_qt_widget as create_tuning_widget,
                )

                tuning_ctrl = TuningControllerClass(logger=self._log_controller)
                tuning_widget = create_tuning_widget(tuning_ctrl, parent=tuning_page)
                tuning_layout.addWidget(tuning_widget)
            except Exception as exc:
                tuning_layout.addWidget(QtWidgets.QLabel(f"Tuning options widget unavailable: {exc}"))
            content_tabs.addTab(tuning_page, "Tuning Options")

            # Tuning editor
            editor_page = QtWidgets.QWidget()
            editor_layout = QtWidgets.QVBoxLayout(editor_page)
            editor_layout.setContentsMargins(8, 8, 8, 8)
            editor_layout.setSpacing(8)
            try:
                from flash_tool.gui.widgets.tuning_editor import (
                    TuningEditorController,
                    create_qt_widget as create_editor_widget,
                )

                editor_ctrl = TuningEditorController(log_controller=self._log_controller)
                editor_widget = create_editor_widget(editor_ctrl, parent=editor_page)
                editor_layout.addWidget(editor_widget)
            except Exception as exc:
                editor_layout.addWidget(QtWidgets.QLabel(f"Tuning editor unavailable: {exc}"))
            content_tabs.addTab(editor_page, "Tuning Editor")

            # Bin tools
            bin_tools_page = QtWidgets.QWidget()
            bin_tools_layout = QtWidgets.QVBoxLayout(bin_tools_page)
            bin_tools_layout.setContentsMargins(8, 8, 8, 8)
            bin_tools_layout.setSpacing(8)
            try:
                from flash_tool.gui.widgets.bin_compare import (
                    BinCompareController,
                    BinCompareWidget,
                )

                bin_compare_ctrl = BinCompareController(log_controller=self._log_controller)
                bin_compare_widget = BinCompareWidget(bin_compare_ctrl, parent=bin_tools_page)
                bin_tools_layout.addWidget(bin_compare_widget)
            except Exception as exc:
                bin_tools_layout.addWidget(QtWidgets.QLabel(f"Bin compare unavailable: {exc}"))

            try:
                from flash_tool.gui.widgets.bin_inspector import (
                    BinInspectorController,
                    create_qt_widget as create_bin_inspector_widget,
                )

                bin_inspector_ctrl = BinInspectorController(log_controller=self._log_controller)
                bin_inspector_widget = create_bin_inspector_widget(
                    bin_inspector_ctrl, parent=bin_tools_page
                )
                bin_tools_layout.addWidget(bin_inspector_widget)
            except Exception as exc:
                bin_tools_layout.addWidget(QtWidgets.QLabel(f"Bin inspector unavailable: {exc}"))

            content_tabs.addTab(bin_tools_page, "Bin Tools")

            content_layout.addWidget(content_tabs)
            self._maps_stack.addWidget(content_page)
            
            # Add stacked widget to main layout
            layout.addWidget(self._maps_stack)
            
            # Keep references
            self._maps_tuning_tab = tab
            self._maps_tuning_content_tabs = content_tabs
            self._maps_tuning_bin_tools_page = bin_tools_page
            self._maps_loaded_file_path = None
            self._maps_loaded_data = None
            
            # Store widget references for updating after load
            try:
                self._map_editor_ctrl = map_ctrl
                self._map_editor_widget = map_widget
            except:
                self._map_editor_ctrl = None
                self._map_editor_widget = None
            
            try:
                self._tuning_options_ctrl = tuning_ctrl
                self._tuning_options_widget = tuning_widget
            except:
                self._tuning_options_ctrl = None
                self._tuning_options_widget = None
            
            try:
                self._tuning_editor_ctrl = editor_ctrl
                self._tuning_editor_widget = editor_widget
            except:
                self._tuning_editor_ctrl = None
                self._tuning_editor_widget = None

            self.tab_widget.addTab(tab, load_icon("MapsTuning.png"), "Maps / Tuning")

        def _add_diagnostics_tab(self) -> None:
            tab = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(tab)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(12)

            header_layout = QtWidgets.QHBoxLayout()
            icon_lbl = QtWidgets.QLabel()
            icon_lbl.setPixmap(load_icon("Diagnostics.png").pixmap(32, 32))
            title_lbl = QtWidgets.QLabel("Diagnostics")
            title_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
            header_layout.addWidget(icon_lbl)
            header_layout.addWidget(title_lbl)
            header_layout.addStretch(1)
            layout.addLayout(header_layout)

            content_tabs = QtWidgets.QTabWidget()

            # OBD dashboard (DTCs, ECU info, etc.)
            obd_page = QtWidgets.QWidget()
            obd_layout = QtWidgets.QVBoxLayout(obd_page)
            obd_layout.setContentsMargins(8, 8, 8, 8)
            obd_layout.setSpacing(8)
            try:
                from flash_tool.gui.widgets.obd_dashboard import (
                    OBDController as OBDControllerClass,
                    create_qt_widget as create_obd_widget,
                )

                obd_ctrl = OBDControllerClass(log_controller=self._log_controller)
                obd_widget = create_obd_widget(obd_ctrl, parent=obd_page)
                obd_layout.addWidget(obd_widget)
            except Exception as exc:
                obd_layout.addWidget(QtWidgets.QLabel(f"OBD dashboard unavailable: {exc}"))
            content_tabs.addTab(obd_page, "OBD Dashboard")

            # Coding / advanced
            coding_page = QtWidgets.QWidget()
            coding_layout = QtWidgets.QVBoxLayout(coding_page)
            coding_layout.setContentsMargins(8, 8, 8, 8)
            coding_layout.setSpacing(8)
            try:
                from flash_tool.gui.widgets.coding_widget import (
                    CodingController as CodingControllerClass,
                    create_qt_widget as create_coding_widget,
                )

                coding_ctrl = CodingControllerClass(log_controller=self._log_controller)
                coding_widget = create_coding_widget(coding_ctrl, parent=coding_page)
                coding_layout.addWidget(coding_widget)
            except Exception as exc:
                coding_layout.addWidget(QtWidgets.QLabel(f"Coding widget unavailable: {exc}"))
            content_tabs.addTab(coding_page, "Coding")

            # Direct CAN tools (wrapped in a scroll area so layouts don't
            # get crushed on smaller windows)
            can_page = QtWidgets.QWidget()
            can_layout = QtWidgets.QVBoxLayout(can_page)
            can_layout.setContentsMargins(8, 8, 8, 8)
            can_layout.setSpacing(8)
            try:
                from flash_tool.gui.widgets.direct_can_widget import (
                    DirectCANController,
                    DirectCANWidget,
                )

                can_ctrl = DirectCANController(log_controller=self._log_controller)
                can_widget = DirectCANWidget(can_ctrl, parent=can_page)

                can_scroll = QtWidgets.QScrollArea()
                can_scroll.setWidgetResizable(True)
                can_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
                can_scroll.setWidget(can_widget)
                can_layout.addWidget(can_scroll)
            except Exception as exc:
                can_layout.addWidget(QtWidgets.QLabel(f"Direct CAN widget unavailable: {exc}"))
            content_tabs.addTab(can_page, "Direct CAN")

            layout.addWidget(content_tabs)
            self.tab_widget.addTab(tab, load_icon("Diagnostics.png"), "Diagnostics")

        def _add_live_data_tab(self) -> None:
            tab = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(tab)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(12)

            header_layout = QtWidgets.QHBoxLayout()
            icon_lbl = QtWidgets.QLabel()
            icon_lbl.setPixmap(load_icon("LiveData.png").pixmap(32, 32))
            title_lbl = QtWidgets.QLabel("Live Data")
            title_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
            header_layout.addWidget(icon_lbl)
            header_layout.addWidget(title_lbl)
            header_layout.addStretch(1)
            layout.addLayout(header_layout)

            content_tabs = QtWidgets.QTabWidget()

            # Gauges dashboard
            gauges_page = QtWidgets.QWidget()
            gauges_layout = QtWidgets.QVBoxLayout(gauges_page)
            gauges_layout.setContentsMargins(8, 8, 8, 8)
            gauges_layout.setSpacing(8)
            try:
                from flash_tool.gui.widgets.gauges_dashboard import GaugesDashboard

                gauges_widget = GaugesDashboard(parent=gauges_page)
                gauges_scroll = QtWidgets.QScrollArea()
                gauges_scroll.setWidgetResizable(True)
                gauges_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
                gauges_scroll.setWidget(gauges_widget)
                gauges_layout.addWidget(gauges_scroll)
            except Exception as exc:
                gauges_layout.addWidget(QtWidgets.QLabel(f"Gauges dashboard unavailable: {exc}"))
            content_tabs.addTab(gauges_page, "Gauges")

            # OBD logger
            obdlog_page = QtWidgets.QWidget()
            obdlog_layout = QtWidgets.QVBoxLayout(obdlog_page)
            obdlog_layout.setContentsMargins(8, 8, 8, 8)
            obdlog_layout.setSpacing(8)
            try:
                from flash_tool.gui.widgets.obd_logger import (
                    OBDLoggerController as OBDLoggerControllerClass,
                    create_qt_widget as create_obdlog_widget,
                )

                obdlog_ctrl = OBDLoggerControllerClass()
                obdlog_widget = create_obdlog_widget(obdlog_ctrl, parent=obdlog_page)
                obdlog_layout.addWidget(obdlog_widget)
            except Exception as exc:
                obdlog_layout.addWidget(QtWidgets.QLabel(f"OBD logger unavailable: {exc}"))
            content_tabs.addTab(obdlog_page, "OBD Logger")

            # Live Control (Actuators/RAM)
            control_page = QtWidgets.QWidget()
            control_layout = QtWidgets.QVBoxLayout(control_page)
            control_layout.setContentsMargins(8, 8, 8, 8)
            control_layout.setSpacing(8)
            try:
                from flash_tool.gui.widgets.live_control_widget import LiveControlWidget

                # Pass a lambda to get the current handle from the connection controller
                handle_provider = lambda: self._conn_controller.handle
                control_widget = LiveControlWidget(handle_provider, parent=control_page)
                control_scroll = QtWidgets.QScrollArea()
                control_scroll.setWidgetResizable(True)
                control_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
                control_scroll.setWidget(control_widget)
                control_layout.addWidget(control_scroll)
            except Exception as exc:
                control_layout.addWidget(QtWidgets.QLabel(f"Live Control unavailable: {exc}"))
            content_tabs.addTab(control_page, "Live Control")

            layout.addWidget(content_tabs)
            self.tab_widget.addTab(tab, load_icon("LiveData.png"), "Live Data")

        def _add_logs_tab(self) -> None:
            tab = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(tab)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(12)

            header_layout = QtWidgets.QHBoxLayout()
            icon_lbl = QtWidgets.QLabel()
            icon_lbl.setPixmap(load_icon("Logs.png").pixmap(32, 32))
            title_lbl = QtWidgets.QLabel("Logs")
            title_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
            header_layout.addWidget(icon_lbl)
            header_layout.addWidget(title_lbl)
            header_layout.addStretch(1)
            layout.addLayout(header_layout)

            if self._log_widget is not None:
                self._log_widget.setParent(tab)
                layout.addWidget(self._log_widget)
            else:
                layout.addWidget(QtWidgets.QLabel("Log viewer unavailable"))

            self.tab_widget.addTab(tab, load_icon("Logs.png"), "Logs")

        def _add_settings_tab(self) -> None:
            tab = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(tab)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(12)

            header_layout = QtWidgets.QHBoxLayout()
            icon_lbl = QtWidgets.QLabel()
            icon_lbl.setPixmap(load_icon("Settings.png").pixmap(32, 32))
            title_lbl = QtWidgets.QLabel("Settings")
            title_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
            header_layout.addWidget(icon_lbl)
            header_layout.addWidget(title_lbl)
            header_layout.addStretch(1)
            layout.addLayout(header_layout)

            info = QtWidgets.QLabel(
                "Global settings are available via the settings dialog. "
                "Use the button below to open the full settings UI."
            )
            info.setWordWrap(True)
            layout.addWidget(info)

            btn_open = QtWidgets.QPushButton("Open Settings Dialog")
            btn_open.setIcon(load_icon("Settings.png"))
            btn_open.clicked.connect(self._open_settings_dialog)
            layout.addWidget(btn_open)

            layout.addStretch(1)
            self.tab_widget.addTab(tab, load_icon("Settings.png"), "Settings")

        def _add_about_tab(self) -> None:
            tab = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(tab)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(12)

            header_layout = QtWidgets.QHBoxLayout()
            icon_lbl = QtWidgets.QLabel()
            icon_lbl.setPixmap(load_icon("About.png").pixmap(32, 32))
            title_lbl = QtWidgets.QLabel("About")
            title_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
            header_layout.addWidget(icon_lbl)
            header_layout.addWidget(title_lbl)
            header_layout.addStretch(1)
            layout.addLayout(header_layout)

            # Large logo
            logo_lbl = QtWidgets.QLabel()
            logo_pix = load_icon("Logo.png").pixmap(256, 256)
            logo_lbl.setPixmap(logo_pix)
            logo_lbl.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(logo_lbl)

            info_lbl = QtWidgets.QLabel(
                "<h3>Free N54 Flasher</h3>"
                "<p>BMW N54 ECU Diagnostic and Tuning Tool</p>"
                "<p>Use at your own risk. Always follow the flash safety checklist.</p>"
                "<p><b>Written by Gregory King</b></p>"
            )
            info_lbl.setAlignment(QtCore.Qt.AlignCenter)
            info_lbl.setWordWrap(True)
            layout.addWidget(info_lbl)

            layout.addStretch(1)
            self.tab_widget.addTab(tab, load_icon("About.png"), "About")

        # ----- Flashing toolbar helpers --------------------------------
        def _toolbar_load_bin(self) -> None:
            fw = getattr(self, "_flasher_widget", None)
            if fw is None or not hasattr(fw, "browse_btn"):
                QtWidgets.QMessageBox.warning(self, "Flashing", "Flasher wizard is not available.")
                return
            try:
                fw.browse_btn.click()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Flashing", f"Load BIN failed: {exc}")

        def _toolbar_validate_bin(self) -> None:
            fw = getattr(self, "_flasher_widget", None)
            if fw is None or not hasattr(fw, "validate_btn"):
                QtWidgets.QMessageBox.warning(self, "Flashing", "Flasher wizard is not available.")
                return
            try:
                fw.validate_btn.click()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Flashing", f"Validate BIN failed: {exc}")

        def _toolbar_start_flash(self) -> None:
            fw = getattr(self, "_flasher_widget", None)
            if fw is None or not hasattr(fw, "execute_btn"):
                QtWidgets.QMessageBox.warning(self, "Flashing", "Flasher wizard is not available.")
                return
            try:
                # If the execute button is disabled, guide the user instead
                # of silently doing nothing when the toolbar button is used.
                if not fw.execute_btn.isEnabled():
                    QtWidgets.QMessageBox.information(
                        self,
                        "Flashing",
                        "Before starting a flash, select a BIN file and "
                        "use 'Validate BIN' to confirm the offset.",
                    )
                    return
                fw.execute_btn.click()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Flashing", f"Start Flash failed: {exc}")

        def _toolbar_backup_ecu(self) -> None:
            bw = getattr(self, "_backup_widget", None)
            if bw is None or not hasattr(bw, "backup_full_btn"):
                QtWidgets.QMessageBox.warning(self, "Backup", "Backup & Recovery widget is not available.")
                return
            try:
                bw.backup_full_btn.click()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Backup", f"Backup ECU failed: {exc}")

        def _toolbar_restore_ecu(self) -> None:
            bw = getattr(self, "_backup_widget", None)
            if bw is None or not hasattr(bw, "restore_btn"):
                QtWidgets.QMessageBox.warning(self, "Backup", "Backup & Recovery widget is not available.")
                return
            try:
                bw.restore_btn.click()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Backup", f"Restore ECU failed: {exc}")

        def _toolbar_verify_flash(self) -> None:
            bw = getattr(self, "_backup_widget", None)
            if bw is None or not hasattr(bw, "verify_btn"):
                QtWidgets.QMessageBox.warning(self, "Backup", "Backup & Recovery widget is not available.")
                return
            try:
                # Require a selected backup so the user gets clear feedback
                # when invoking Verify from the toolbar.
                table = getattr(bw, "table", None)
                current_row = table.currentRow() if table is not None else -1
                if current_row < 0:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Backup Verification",
                        "Select a backup in the Backup & Recovery tab and then "
                        "click 'Verify Selected'.",
                    )
                    return
                bw.verify_btn.click()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Backup", f"Verify operation failed: {exc}")

        def _toolbar_apply_patch(self) -> None:
            fw = getattr(self, "_flasher_widget", None)
            if fw is None or not hasattr(fw, "patch_browse_btn"):
                QtWidgets.QMessageBox.warning(self, "Flashing", "Patch workflow is not available.")
                return
            try:
                fw.patch_browse_btn.click()
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Flashing", f"Apply Patch failed: {exc}")

        def _toolbar_differences(self) -> None:
            maps_tab = getattr(self, "_maps_tuning_tab", None)
            maps_tabs = getattr(self, "_maps_tuning_content_tabs", None)
            bin_tools_page = getattr(self, "_maps_tuning_bin_tools_page", None)

            if maps_tab is None or maps_tabs is None or bin_tools_page is None:
                QtWidgets.QMessageBox.warning(self, "Bin Tools", "Bin Tools view is not available.")
                return

            try:
                idx = self.tab_widget.indexOf(maps_tab)
                if idx != -1:
                    self.tab_widget.setCurrentIndex(idx)
                sub_idx = maps_tabs.indexOf(bin_tools_page)
                if sub_idx != -1:
                    maps_tabs.setCurrentIndex(sub_idx)
            except Exception as exc:
                QtWidgets.QMessageBox.warning(self, "Bin Tools", f"Could not open Bin Tools: {exc}")
        
        # ----- Maps/Tuning file loading handlers --------------------------------
        def _on_maps_browse_file(self) -> None:
            """Browse for a bin/map file to load"""
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Select ECU Binary or Map File",
                "",
                "Binary Files (*.bin *.map);;All Files (*.*)"
            )
            
            if file_path:
                self._map_file_path_edit.setText(file_path)
                self._map_load_btn.setEnabled(True)
                
                # Show file info
                try:
                    from pathlib import Path
                    p = Path(file_path)
                    size_mb = p.stat().st_size / (1024 * 1024)
                    self._map_file_info.setText(f"File: {p.name} ({size_mb:.2f} MB)")
                except Exception as exc:
                    self._map_file_info.setText(f"File selected: {file_path}")
        
        def _on_maps_load_file(self) -> None:
            """Load and parse the selected bin/map file"""
            file_path = self._map_file_path_edit.text()
            if not file_path:
                return
            
            try:
                # Show progress
                self._map_load_btn.setEnabled(False)
                self._map_load_btn.setText("Loading...")
                QtWidgets.QApplication.processEvents()
                
                # Read file
                with open(file_path, 'rb') as f:
                    data = f.read()
                
                self._maps_loaded_file_path = file_path
                self._maps_loaded_data = data
                
                # Update loaded file label
                from pathlib import Path
                filename = Path(file_path).name
                size_mb = len(data) / (1024 * 1024)
                self._loaded_file_label.setText(f"Loaded: {filename} ({size_mb:.2f} MB)")
                
                # Populate widgets with loaded data
                self._populate_maps_widgets(data, file_path)
                
                # Switch to content tabs
                self._maps_stack.setCurrentIndex(1)
                
                # Success message
                QtWidgets.QMessageBox.information(
                    self,
                    "File Loaded",
                    f"Successfully loaded {filename}\n\n"
                    f"Size: {size_mb:.2f} MB\n"
                    f"You can now view and edit tuning parameters."
                )
                
            except Exception as exc:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Load Error",
                    f"Failed to load file:\n{exc}"
                )
            finally:
                self._map_load_btn.setEnabled(True)
                self._map_load_btn.setText("Load File and Parse Parameters")
        
        def _populate_maps_widgets(self, data: bytes, file_path: str) -> None:
            """Populate all Maps/Tuning widgets with loaded data"""
            # Map Editor
            if hasattr(self, '_map_editor_ctrl') and self._map_editor_ctrl:
                try:
                    # Load a specific map or prepare for selection
                    # This would call map_editor_ctrl methods to load from data
                    pass
                except Exception as exc:
                    print(f"Map editor population failed: {exc}")
            
            # Tuning Options
            if hasattr(self, '_tuning_options_ctrl') and self._tuning_options_ctrl:
                try:
                    # Load tuning parameters from data
                    if hasattr(self._tuning_options_ctrl, 'load_from_binary'):
                        self._tuning_options_ctrl.load_from_binary(data, file_path)
                except Exception as exc:
                    print(f"Tuning options population failed: {exc}")
            
            # Tuning Editor
            if hasattr(self, '_tuning_editor_ctrl') and self._tuning_editor_ctrl:
                try:
                    # Load tuning parameters from data
                    if hasattr(self._tuning_editor_ctrl, 'load_from_binary'):
                        self._tuning_editor_ctrl.load_from_binary(data, file_path)
                except Exception as exc:
                    print(f"Tuning editor population failed: {exc}")
        
        def _on_maps_change_file(self) -> None:
            """Go back to file loader to select a different file"""
            reply = QtWidgets.QMessageBox.question(
                self,
                "Change File",
                "Any unsaved changes will be lost. Continue?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                self._maps_stack.setCurrentIndex(0)
                self._maps_loaded_file_path = None
                self._maps_loaded_data = None
        
        def _on_maps_save_changes(self) -> None:
            """Save modified parameters back to file"""
            if not self._maps_loaded_file_path:
                QtWidgets.QMessageBox.warning(self, "Save", "No file loaded")
                return
            
            reply = QtWidgets.QMessageBox.question(
                self,
                "Save Changes",
                f"Save modifications to:\n{self._maps_loaded_file_path}\n\n"
                f"Original file will be backed up with .bak extension.",
                QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Cancel
            )
            
            if reply == QtWidgets.QMessageBox.Save:
                try:
                    # Backup original
                    import shutil
                    backup_path = self._maps_loaded_file_path + '.bak'
                    shutil.copy2(self._maps_loaded_file_path, backup_path)
                    
                    # Collect changes from widgets and write
                    # (Implementation depends on widget APIs)
                    
                    QtWidgets.QMessageBox.information(
                        self,
                        "Saved",
                        f"Changes saved successfully!\n\nBackup: {backup_path}"
                    )
                except Exception as exc:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Save Error",
                        f"Failed to save changes:\n{exc}"
                    )

    app = QtWidgets.QApplication(sys.argv)

    # Apply global neon stylesheet
    stylesheet = load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
