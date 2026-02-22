# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qgis.gui import QgsMapLayerComboBox, QgsMapLayerProxyModel

from .locale import tr


class FengShuiDockWidget(QDockWidget):
    run_requested = pyqtSignal(object, object, object, str, str, str, str)
    terms_requested = pyqtSignal(object, str, str, str)

    def __init__(self, parent=None):
        super().__init__(tr("panel_title"), parent)
        self._build_ui()

    def _build_ui(self):
        container = QWidget(self)
        layout = QVBoxLayout(container)

        form = QFormLayout()

        self.sites_combo = QgsMapLayerComboBox(container)
        self.sites_combo.setFilters(QgsMapLayerProxyModel.PointLayer)
        form.addRow(tr("sites_label"), self.sites_combo)

        self.dem_combo = QgsMapLayerComboBox(container)
        self.dem_combo.setFilters(QgsMapLayerProxyModel.RasterLayer)
        form.addRow(tr("dem_label"), self.dem_combo)

        self.water_combo = QgsMapLayerComboBox(container)
        self.water_combo.setFilters(
            QgsMapLayerProxyModel.LineLayer | QgsMapLayerProxyModel.PolygonLayer
        )
        self.water_combo.setAllowEmptyLayer(True)
        self.water_combo.setCurrentIndex(-1)
        form.addRow(tr("water_label"), self.water_combo)

        self.hemisphere_combo = QComboBox(container)
        self.hemisphere_combo.addItem(tr("hemisphere_north"), "north")
        self.hemisphere_combo.addItem(tr("hemisphere_south"), "south")
        form.addRow(tr("hemisphere_label"), self.hemisphere_combo)

        self.profile_combo = QComboBox(container)
        self.profile_combo.addItem(tr("model_general"), "general")
        self.profile_combo.addItem(tr("model_tomb"), "tomb")
        self.profile_combo.addItem(tr("model_house"), "house")
        self.profile_combo.addItem(tr("model_village"), "village")
        self.profile_combo.addItem(tr("model_well"), "well")
        self.profile_combo.addItem(tr("model_temple"), "temple")
        form.addRow(tr("model_label"), self.profile_combo)

        self.culture_combo = QComboBox(container)
        self.culture_combo.addItem(tr("culture_east_asia"), "east_asia")
        self.culture_combo.addItem(tr("culture_korea"), "korea")
        self.culture_combo.addItem(tr("culture_china"), "china")
        self.culture_combo.addItem(tr("culture_japan"), "japan")
        self.culture_combo.addItem(tr("culture_ryukyu"), "ryukyu")
        form.addRow(tr("culture_label"), self.culture_combo)

        self.period_combo = QComboBox(container)
        self.period_combo.addItem(tr("period_ancient"), "ancient")
        self.period_combo.addItem(tr("period_medieval"), "medieval")
        self.period_combo.addItem(tr("period_early_modern"), "early_modern")
        self.period_combo.addItem(tr("period_modern"), "modern")
        self.period_combo.setCurrentIndex(2)
        form.addRow(tr("period_label"), self.period_combo)

        layout.addLayout(form)

        self.run_button = QPushButton(tr("run_button"), container)
        self.run_button.clicked.connect(self._emit_run_requested)
        layout.addWidget(self.run_button)

        self.extract_terms_button = QPushButton(tr("extract_terms_button"), container)
        self.extract_terms_button.clicked.connect(self._emit_terms_requested)
        layout.addWidget(self.extract_terms_button)

        self.status_label = QLabel(tr("status_idle"), container)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        layout.addStretch(1)
        self.setWidget(container)

    def set_status(self, text):
        self.status_label.setText(text)

    def _emit_run_requested(self):
        self.run_requested.emit(
            self.sites_combo.currentLayer(),
            self.dem_combo.currentLayer(),
            self.water_combo.currentLayer(),
            self.hemisphere_combo.currentData(),
            self.profile_combo.currentData(),
            self.culture_combo.currentData(),
            self.period_combo.currentData(),
        )

    def _emit_terms_requested(self):
        self.terms_requested.emit(
            self.dem_combo.currentLayer(),
            self.hemisphere_combo.currentData(),
            self.culture_combo.currentData(),
            self.period_combo.currentData(),
        )
