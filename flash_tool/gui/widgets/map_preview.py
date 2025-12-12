"""Map Preview dialog: 2D heatmap and optional 3D surface using matplotlib.

Falls back to a simple text summary if matplotlib is not installed.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

try:
    from PySide6 import QtWidgets, QtCore
except Exception:
    try:
        from PyQt5 import QtWidgets, QtCore
    except Exception as exc:
        raise ImportError('Qt bindings not available for Map Preview') from exc

try:
    import matplotlib
    matplotlib.use('QtAgg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False


class MapPreviewDialog(QtWidgets.QDialog):
    def __init__(self, rows: int, cols: int, data: bytes, parent: Optional[Any] = None):
        super().__init__(parent)
        self.setWindowTitle('Map Preview')
        self.resize(700, 500)
        layout = QtWidgets.QVBoxLayout(self)

        if not MATPLOTLIB_AVAILABLE:
            label = QtWidgets.QLabel('matplotlib not available; install with `pip install matplotlib` to enable map previews.')
            layout.addWidget(label)
            return

        # Convert data into 2D list
        vals = list(data)
        if len(vals) != rows * cols:
            label = QtWidgets.QLabel('Data size does not match rows*cols; cannot preview grid.')
            layout.addWidget(label)
            return

        import numpy as np
        arr = np.array(vals, dtype=float).reshape((rows, cols))

        # Tabs for 2D/3D
        tabs = QtWidgets.QTabWidget()
        layout.addWidget(tabs)

        # 2D heatmap
        fig2d = Figure(figsize=(5, 4))
        canvas2d = FigureCanvas(fig2d)
        ax2d = fig2d.add_subplot(111)
        cax = ax2d.imshow(arr, cmap='viridis', aspect='auto')
        fig2d.colorbar(cax, ax=ax2d)
        ax2d.set_title('2D Heatmap View')
        tabs.addTab(canvas2d, '2D Heatmap')

        # 3D surface
        fig3d = Figure(figsize=(5, 4))
        canvas3d = FigureCanvas(fig3d)
        ax3d = fig3d.add_subplot(111, projection='3d')
        X, Y = np.meshgrid(range(cols), range(rows))
        ax3d.plot_surface(X, Y, arr, cmap='viridis')
        ax3d.set_title('3D Surface View')
        tabs.addTab(canvas3d, '3D Surface')

        # Refresh canvases
        canvas2d.draw()
        canvas3d.draw()


def create_qt_widget(rows: int, cols: int, data: bytes, parent: Optional[Any] = None):
    return MapPreviewDialog(rows, cols, data, parent)