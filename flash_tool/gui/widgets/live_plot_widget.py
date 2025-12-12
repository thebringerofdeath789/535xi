"""Live Plot widget for GUI using pyqtgraph for high-performance plotting.

Features:
- Load CSV logs and plot a selected data series.
    - Supports simple 2-column CSV (x,y) or 1-column (y only).
    - Supports multi-column logs such as OBD Logger output:
        "timestamp,PID1,PID2,..."; you can pick which PID column to view.
- Export plot as PNG (uses pyqtgraph exporter if available, otherwise widget snapshot).
- Clear plot.

If `pyqtgraph` is not installed the widget shows a helpful message and disables plotting actions.
"""
from __future__ import annotations

from typing import Any, Optional, List
import csv

try:
    from PySide6 import QtWidgets, QtCore
except Exception:
    try:
        from PyQt5 import QtWidgets, QtCore
    except Exception as exc:
        raise ImportError('Qt bindings not available for Live Plot Widget') from exc

try:
    import pyqtgraph as pg
    try:
        import pyqtgraph.exporters as pgexporters
    except Exception:
        pgexporters = None
except Exception:
    pg = None
    pgexporters = None

class LivePlotWidget(QtWidgets.QWidget):
    def __init__(self, parent: Optional[Any] = None):
        super().__init__(parent)
        self.setWindowTitle('Live Plot')
        layout = QtWidgets.QVBoxLayout(self)

        ctrl_row = QtWidgets.QHBoxLayout()
        self.load_btn = QtWidgets.QPushButton('Load CSV')
        self.export_btn = QtWidgets.QPushButton('Export PNG')
        self.clear_btn = QtWidgets.QPushButton('Clear')
        ctrl_row.addWidget(self.load_btn)
        ctrl_row.addWidget(self.export_btn)
        ctrl_row.addWidget(self.clear_btn)
        layout.addLayout(ctrl_row)

        if pg is None:
            self.notice = QtWidgets.QLabel('pyqtgraph is not installed. Install with `pip install pyqtgraph` to enable plotting.')
            layout.addWidget(self.notice)
            self.load_btn.setEnabled(False)
            self.export_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
            return

        self.plot_widget = pg.PlotWidget()
        layout.addWidget(self.plot_widget)
        self.curve = self.plot_widget.plot([], [], pen=pg.mkPen('y', width=2))

        # Series selection for multi-column logs (e.g., OBD Logger CSV)
        series_row = QtWidgets.QHBoxLayout()
        self.series_label = QtWidgets.QLabel('Series:')
        self.series_combo = QtWidgets.QComboBox()
        self.series_combo.setEnabled(False)
        series_row.addWidget(self.series_label)
        series_row.addWidget(self.series_combo, 1)
        layout.addLayout(series_row)

        # Internal CSV cache
        self._csv_headers: List[str] = []
        self._csv_rows: List[list[str]] = []

        # connections
        self.load_btn.clicked.connect(self._on_load_csv)
        self.export_btn.clicked.connect(self._on_export_png)
        self.clear_btn.clicked.connect(self._on_clear)
        self.series_combo.currentIndexChanged.connect(self._on_series_changed)

    def _on_load_csv(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Open CSV', '', 'CSV Files (*.csv);;All Files (*)')
        if not path:
            return
        self.load_csv_path(path)

    def load_csv_path(self, path: str):
        """Load data from a specific CSV file path.

        For simple CSVs (1-2 numeric columns) the first data column is plotted.
        For multi-column logs (e.g., timestamp + multiple PID columns), a
        series selector is populated so the user can choose which column to
        display.
        """
        # Reset internal state
        self._csv_headers = []
        self._csv_rows = []
        self.series_combo.clear()
        self.series_combo.setEnabled(False)

        try:
            with open(path, 'r', newline='') as f:
                rdr = csv.reader(f)
                header_read = False
                for row in rdr:
                    if not row:
                        continue
                    if not header_read:
                        # First non-empty row is treated as header
                        self._csv_headers = [col.strip() for col in row]
                        header_read = True
                        continue
                    # Cache raw data rows as strings
                    self._csv_rows.append([col.strip() for col in row])
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'CSV Load Failed', f'Could not read CSV: {e}')
            return

        if not self._csv_rows:
            QtWidgets.QMessageBox.information(self, 'No Data', 'No data rows found in CSV.')
            return

        # Populate series combo with all data columns after the first (x / timestamp)
        if self._csv_headers and len(self._csv_headers) > 1:
            for col in range(1, len(self._csv_headers)):
                name = self._csv_headers[col] or f'Column {col}'
                self.series_combo.addItem(name, col)
        else:
            # No explicit header; synthesize names from first row length
            first_row_len = max(len(r) for r in self._csv_rows)
            if first_row_len == 1:
                self.series_combo.addItem('Series', 0)
            else:
                for col in range(1, first_row_len):
                    self.series_combo.addItem(f'Column {col}', col)

        if self.series_combo.count() == 0:
            QtWidgets.QMessageBox.information(self, 'No Data', 'No numeric data series found in CSV.')
            return

        self.series_combo.setEnabled(True)
        # Select first series by default and plot
        self.series_combo.setCurrentIndex(0)
        self._plot_current_series()

    def _on_export_png(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Export PNG', 'plot.png', 'PNG Files (*.png);;All Files (*)')
        if not path:
            return
        try:
            if pgexporters is not None:
                exporter = pgexporters.ImageExporter(self.plot_widget.plotItem)
                exporter.parameters()['width'] = 1200
                exporter.export(path)
            else:
                # fallback to widget snapshot
                pix = self.plot_widget.grab()
                pix.save(path)
            QtWidgets.QMessageBox.information(self, 'Export Saved', f'Plot exported to {path}')
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Export Failed', f'Could not export plot: {e}')

    def _on_clear(self):
        try:
            self.curve.setData([], [])
        except Exception:
            pass

    def _on_series_changed(self, index: int):
        if index < 0 or self.series_combo.count() == 0:
            return
        self._plot_current_series()

    def _plot_current_series(self):
        """Plot the currently selected data series from the cached CSV rows."""
        if not self._csv_rows:
            return

        # Determine which column to use for Y
        data_col = self.series_combo.currentData()
        if data_col is None:
            return

        xs: List[float] = []
        ys: List[float] = []

        for row in self._csv_rows:
            if len(row) == 0:
                continue
            # Determine X: first column if numeric, otherwise fall back to index
            try:
                x = float(row[0])
            except Exception:
                x = float(len(xs))

            if data_col >= len(row):
                continue
            try:
                y = float(row[data_col])
            except Exception:
                continue

            xs.append(x)
            ys.append(y)

        if not ys:
            QtWidgets.QMessageBox.information(self, 'No Data', 'No numeric data found for the selected series.')
            return

        try:
            self.curve.setData(xs, ys)
            self.plot_widget.autoRange()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Plot Failed', f'Could not plot data: {e}')


def create_qt_widget(parent: Optional[Any] = None):
    return LivePlotWidget(parent)
