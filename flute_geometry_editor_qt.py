"""
Editor Interactivo de Geometría de Flautas con PyQt5
Permite editar geometría, comparar respuestas acústicas, iterar con versiones.
"""

import sys
import json
import copy
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QWidget, QLabel,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem, QGroupBox,
    QListWidget, QMessageBox, QProgressDialog, QInputDialog, QApplication,
    QHeaderView, QFormLayout, QSpinBox, QCheckBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Ellipse

from flute_data import FluteData
from flute_data_db import FluteDataDB
from constants import FLUTE_PARTS_ORDER

logger = logging.getLogger(__name__)


class VersionHistory:
    """Maneja el historial de versiones de una flauta editada."""
    
    def __init__(self, base_flute_name: str, initial_data: Dict[str, Any]):
        self.base_flute_name = base_flute_name
        self.versions: List[Dict[str, Any]] = []
        self.current_version_index = -1
        
        # Guardar versión inicial
        self.save_version(initial_data, "Original")
    
    def save_version(self, data: Dict[str, Any], description: str = "") -> int:
        """Guarda una nueva versión y retorna su índice."""
        # Si no estamos al final del historial, eliminar versiones futuras
        if self.current_version_index < len(self.versions) - 1:
            self.versions = self.versions[:self.current_version_index + 1]
        
        version_num = len(self.versions)
        version_info = {
            'data': copy.deepcopy(data),
            'timestamp': datetime.now().isoformat(),
            'description': description or f"v{version_num}",
            'version_number': version_num
        }
        
        self.versions.append(version_info)
        self.current_version_index = len(self.versions) - 1
        return self.current_version_index
    
    def undo(self) -> Optional[Dict[str, Any]]:
        """Deshacer: volver a la versión anterior."""
        if self.current_version_index > 0:
            self.current_version_index -= 1
            return copy.deepcopy(self.versions[self.current_version_index]['data'])
        return None
    
    def redo(self) -> Optional[Dict[str, Any]]:
        """Rehacer: avanzar a la versión siguiente."""
        if self.current_version_index < len(self.versions) - 1:
            self.current_version_index += 1
            return copy.deepcopy(self.versions[self.current_version_index]['data'])
        return None
    
    def get_current_version(self) -> Dict[str, Any]:
        """Obtiene los datos de la versión actual."""
        if 0 <= self.current_version_index < len(self.versions):
            return copy.deepcopy(self.versions[self.current_version_index]['data'])
        return {}
    
    def get_version_names(self) -> List[str]:
        """Obtiene lista de nombres de versiones para mostrar en UI."""
        return [
            f"v{v['version_number']}: {v['description']} ({v['timestamp'][:16]})"
            for v in self.versions
        ]
    
    def can_undo(self) -> bool:
        return self.current_version_index > 0
    
    def can_redo(self) -> bool:
        return self.current_version_index < len(self.versions) - 1


class FluteGeometryEditor(QDialog):
    """Editor interactivo de geometría de flautas."""
    
    flute_modified = pyqtSignal(str)  # Señal cuando se guarda una nueva flauta
    flute_loaded_for_analysis = pyqtSignal(object)  # Señal cuando se carga para análisis en GUI principal
    
    def __init__(self, flute_data: Any, parent=None):
        super().__init__(parent)
        
        self.original_flute_data = flute_data
        self.flute_name = flute_data.flute_model
        
        # Copiar datos para edición
        self.current_data = copy.deepcopy(flute_data.data)
        
        # Sistema de versiones
        self.version_history = VersionHistory(self.flute_name, self.current_data)
        
        # Estado del editor
        self.current_part = FLUTE_PARTS_ORDER[0] if FLUTE_PARTS_ORDER else 'headjoint'
        self.is_modified = False
        self.dragging_point = None
        self.dragging_hole = None
        
        # Parámetros acústicos (para cálculos al cargar en GUI)
        self.temperature = 20.0
        self.la_frequency = 415.0
        
        self._init_ui()
        self._update_all()
    
    def _init_ui(self):
        """Inicializa la interfaz de usuario."""
        self.setWindowTitle(f"Editor de Geometría: {self.flute_name}")
        self.setGeometry(100, 100, 1600, 900)
        
        # Hacer el diálogo no-modal para permitir navegar la GUI principal
        self.setModal(False)
        
        main_layout = QHBoxLayout(self)
        
        # Panel izquierdo: Controles
        left_panel = self._create_left_panel()
        
        # Panel central: Gráficos
        center_panel = self._create_center_panel()
        
        # Panel derecho: Tablas
        right_panel = self._create_right_panel()
        
        # Splitter principal
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 700, 400])
        
        main_layout.addWidget(splitter)
    
    def _create_left_panel(self) -> QWidget:
        """Crea el panel izquierdo con controles."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Selector de parte
        parts_group = QGroupBox("Seleccionar Parte")
        parts_layout = QVBoxLayout(parts_group)
        
        self.part_combo = QComboBox()
        for part in FLUTE_PARTS_ORDER:
            if part in self.current_data:
                self.part_combo.addItem(part.capitalize(), part)
        self.part_combo.currentIndexChanged.connect(self._on_part_changed)
        parts_layout.addWidget(self.part_combo)
        
        layout.addWidget(parts_group)
        
        # Historial de versiones
        history_group = QGroupBox("Historial de Versiones")
        history_layout = QVBoxLayout(history_group)
        
        self.version_list = QListWidget()
        self.version_list.itemClicked.connect(self._on_version_selected)
        history_layout.addWidget(self.version_list)
        
        # Botones de deshacer/rehacer
        undo_redo_layout = QHBoxLayout()
        self.undo_btn = QPushButton("← Deshacer")
        self.undo_btn.clicked.connect(self._undo)
        self.redo_btn = QPushButton("Rehacer →")
        self.redo_btn.clicked.connect(self._redo)
        undo_redo_layout.addWidget(self.undo_btn)
        undo_redo_layout.addWidget(self.redo_btn)
        history_layout.addLayout(undo_redo_layout)
        
        # Botón guardar versión
        save_version_btn = QPushButton("💾 Guardar Versión")
        save_version_btn.clicked.connect(self._save_version)
        history_layout.addWidget(save_version_btn)
        
        layout.addWidget(history_group)
        
        # Opciones de cálculo
        calc_group = QGroupBox("Opciones de Cálculo")
        calc_layout = QFormLayout(calc_group)
        
        self.include_pf_checkbox = QCheckBox()
        self.include_pf_checkbox.setChecked(False)
        self.include_pf_checkbox.setToolTip(
            "Si está marcado, se calcularán y guardarán datos de presión y flujo.\n"
            "Útil para visualización detallada en la pestaña de Admitancia."
        )
        calc_layout.addRow("Incluir presión/flujo:", self.include_pf_checkbox)
        
        self.temp_spinbox = QDoubleSpinBox()
        self.temp_spinbox.setRange(-20.0, 50.0)
        self.temp_spinbox.setValue(self.temperature)
        self.temp_spinbox.setDecimals(1)
        self.temp_spinbox.setSuffix(" °C")
        calc_layout.addRow("Temperatura:", self.temp_spinbox)
        
        self.la_freq_spinbox = QDoubleSpinBox()
        self.la_freq_spinbox.setRange(300.0, 500.0)
        self.la_freq_spinbox.setValue(self.la_frequency)
        self.la_freq_spinbox.setDecimals(1)
        self.la_freq_spinbox.setSuffix(" Hz")
        calc_layout.addRow("Diapasón (La):", self.la_freq_spinbox)
        
        layout.addWidget(calc_group)
        
        # Botones de acción
        actions_group = QGroupBox("Acciones")
        actions_layout = QVBoxLayout(actions_group)
        
        # Botón principal: Calcular y Visualizar en GUI
        self.calculate_and_load_btn = QPushButton("🔄 Calcular y Visualizar en GUI")
        self.calculate_and_load_btn.setStyleSheet(
            "QPushButton { font-weight: bold; background-color: #2196F3; color: white; padding: 10px; }"
        )
        self.calculate_and_load_btn.setToolTip(
            "Calcula análisis acústico y carga en la GUI principal para visualización completa.\n"
            "El editor permanece abierto para seguir editando."
        )
        self.calculate_and_load_btn.clicked.connect(self._load_in_main_gui)
        actions_layout.addWidget(self.calculate_and_load_btn)
        
        reset_btn = QPushButton("🔃 Resetear a Original")
        reset_btn.clicked.connect(self._reset_to_original)
        actions_layout.addWidget(reset_btn)
        
        layout.addWidget(actions_group)
        
        # Botón de guardado final
        save_btn = QPushButton("💾 Guardar como Nueva Flauta")
        save_btn.setStyleSheet("QPushButton { font-weight: bold; background-color: #4CAF50; color: white; padding: 10px; }")
        save_btn.clicked.connect(self._save_as_new_flute)
        layout.addWidget(save_btn)
        
        layout.addStretch()
        
        # Estado
        self.status_label = QLabel("Listo")
        self.status_label.setStyleSheet("color: blue; font-style: italic;")
        layout.addWidget(self.status_label)
        
        return panel
    
    def _create_center_panel(self) -> QWidget:
        """Crea el panel central con gráficos."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Gráfico de edición (ahora ocupa todo el espacio)
        edit_group = QGroupBox("Vista de Edición Interactiva")
        edit_layout = QVBoxLayout(edit_group)
        
        self.edit_figure = Figure(figsize=(10, 6), dpi=100)  # Más grande ahora
        self.edit_canvas = FigureCanvas(self.edit_figure)
        self.edit_ax = self.edit_figure.add_subplot(111)
        
        # Conectar eventos de matplotlib
        self.edit_canvas.mpl_connect('button_press_event', self._on_plot_click)
        self.edit_canvas.mpl_connect('motion_notify_event', self._on_plot_motion)
        self.edit_canvas.mpl_connect('button_release_event', self._on_plot_release)
        
        edit_layout.addWidget(self.edit_canvas)
        edit_toolbar = NavigationToolbar(self.edit_canvas, self)
        edit_layout.addWidget(edit_toolbar)
        
        layout.addWidget(edit_group)
        
        # Nota informativa
        info_label = QLabel(
            "💡 Tip: Usa el botón 'Calcular y Visualizar en GUI' para ver análisis completo\n"
            "en todas las pestañas de la GUI principal (Admitancia, Análisis Acústico, etc.)"
        )
        info_label.setStyleSheet("color: gray; font-style: italic; padding: 10px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        return panel
    
    def _create_right_panel(self) -> QWidget:
        """Crea el panel derecho con tablas editables."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Tabla de mediciones
        measurements_group = QGroupBox("Mediciones del Perfil")
        measurements_layout = QVBoxLayout(measurements_group)
        
        self.measurements_table = QTableWidget()
        self.measurements_table.setColumnCount(2)
        self.measurements_table.setHorizontalHeaderLabels(["Posición (mm)", "Diámetro (mm)"])
        self.measurements_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.measurements_table.cellChanged.connect(self._on_measurements_table_changed)
        measurements_layout.addWidget(self.measurements_table)
        
        # Botones para mediciones
        meas_buttons_layout = QHBoxLayout()
        add_meas_btn = QPushButton("+ Agregar Punto")
        add_meas_btn.clicked.connect(self._add_measurement_row)
        remove_meas_btn = QPushButton("- Eliminar Seleccionado")
        remove_meas_btn.clicked.connect(self._remove_measurement_row)
        meas_buttons_layout.addWidget(add_meas_btn)
        meas_buttons_layout.addWidget(remove_meas_btn)
        measurements_layout.addLayout(meas_buttons_layout)
        
        layout.addWidget(measurements_group)
        
        # Tabla de agujeros
        holes_group = QGroupBox("Agujeros")
        holes_layout = QVBoxLayout(holes_group)
        
        self.holes_table = QTableWidget()
        self.holes_table.setColumnCount(5)
        self.holes_table.setHorizontalHeaderLabels(["Posición", "Diámetro", "Diámetro Interno", "Chimenea", "Diam. Ext."])
        self.holes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.holes_table.cellChanged.connect(self._on_holes_table_changed)
        holes_layout.addWidget(self.holes_table)
        
        # Botones para agujeros
        holes_buttons_layout = QHBoxLayout()
        add_hole_btn = QPushButton("+ Agregar Agujero")
        add_hole_btn.clicked.connect(self._add_hole_row)
        remove_hole_btn = QPushButton("- Eliminar Seleccionado")
        remove_hole_btn.clicked.connect(self._remove_hole_row)
        holes_buttons_layout.addWidget(add_hole_btn)
        holes_buttons_layout.addWidget(remove_hole_btn)
        holes_layout.addLayout(holes_buttons_layout)
        
        layout.addWidget(holes_group)
        
        # Información sobre análisis
        info_group = QGroupBox("Análisis Acústico")
        info_layout = QVBoxLayout(info_group)
        
        info_label = QLabel(
            "💡 Para ver análisis completo:\n\n"
            "1. Edita la geometría\n"
            "2. Presiona 'Calcular y Visualizar en GUI'\n"
            "3. Revisa resultados en la GUI principal\n\n"
            "El editor permanece abierto para iteraciones rápidas."
        )
        info_label.setStyleSheet("color: gray; font-size: 9pt; padding: 10px;")
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        
        layout.addWidget(info_group)
        
        return panel
    
    def _on_part_changed(self):
        """Maneja el cambio de parte seleccionada."""
        self.current_part = self.part_combo.currentData()
        self._update_all()
    
    def _update_all(self):
        """Actualiza todos los componentes de la UI."""
        self._update_version_list()
        self._update_undo_redo_buttons()
        self._update_measurements_table()
        self._update_holes_table()
        self._update_edit_plot()
        self._set_status("Listo")
    
    def _update_version_list(self):
        """Actualiza la lista de versiones."""
        self.version_list.clear()
        version_names = self.version_history.get_version_names()
        for i, name in enumerate(version_names):
            self.version_list.addItem(name)
        self.version_list.setCurrentRow(self.version_history.current_version_index)
    
    def _update_undo_redo_buttons(self):
        """Actualiza el estado de los botones deshacer/rehacer."""
        self.undo_btn.setEnabled(self.version_history.can_undo())
        self.redo_btn.setEnabled(self.version_history.can_redo())
    
    def _update_measurements_table(self):
        """Actualiza la tabla de mediciones desde los datos actuales."""
        self.measurements_table.blockSignals(True)
        
        part_data = self.current_data.get(self.current_part, {})
        measurements = part_data.get('measurements', [])
        
        self.measurements_table.setRowCount(len(measurements))
        for i, meas in enumerate(measurements):
            pos_item = QTableWidgetItem(f"{meas['position']:.3f}")
            diam_item = QTableWidgetItem(f"{meas['diameter']:.3f}")
            self.measurements_table.setItem(i, 0, pos_item)
            self.measurements_table.setItem(i, 1, diam_item)
        
        self.measurements_table.blockSignals(False)
    
    def _update_holes_table(self):
        """Actualiza la tabla de agujeros desde los datos actuales."""
        self.holes_table.blockSignals(True)
        
        part_data = self.current_data.get(self.current_part, {})
        holes_pos = part_data.get('Holes position', [])
        holes_diam = part_data.get('Holes diameter', [])
        holes_chim = part_data.get('Holes chimney', [])
        holes_diam_out = part_data.get('Holes diameter_out', [])
        
        num_holes = len(holes_pos)
        self.holes_table.setRowCount(num_holes)
        
        for i in range(num_holes):
            pos_item = QTableWidgetItem(f"{holes_pos[i]:.3f}")
            
            # Detectar si el agujero es cónico (lista [diam_out, diam_in]) o cilindro (número)
            diam_spec = holes_diam[i] if i < len(holes_diam) else 0.0
            is_cone = isinstance(diam_spec, (list, tuple)) and len(diam_spec) == 2
            
            if is_cone:
                diam_out, diam_in = float(diam_spec[0]), float(diam_spec[1])
                diam_item = QTableWidgetItem(f"{diam_out:.3f}")
                diam_inner_item = QTableWidgetItem(f"{diam_in:.3f}")
            else:
                diam_mm = float(diam_spec) if isinstance(diam_spec, (int, float)) else 0.0
                diam_item = QTableWidgetItem(f"{diam_mm:.3f}")
                diam_inner_item = QTableWidgetItem("")  # Vacío para cilindros
            
            chim_item = QTableWidgetItem(f"{holes_chim[i]:.3f}" if i < len(holes_chim) else "0.0")
            diam_out_item = QTableWidgetItem(f"{holes_diam_out[i]:.3f}" if i < len(holes_diam_out) else "0.0")
            
            self.holes_table.setItem(i, 0, pos_item)
            self.holes_table.setItem(i, 1, diam_item)
            self.holes_table.setItem(i, 2, diam_inner_item)
            self.holes_table.setItem(i, 3, chim_item)
            self.holes_table.setItem(i, 4, diam_out_item)
        
        self.holes_table.blockSignals(False)
    
    def _update_edit_plot(self):
        """Actualiza el gráfico de edición."""
        self.edit_ax.clear()
        
        part_data = self.current_data.get(self.current_part, {})
        measurements = part_data.get('measurements', [])
        
        if not measurements:
            self.edit_ax.text(0.5, 0.5, "No hay mediciones para esta parte", 
                            ha='center', va='center', transform=self.edit_ax.transAxes)
            self.edit_canvas.draw_idle()
            return
        
        # Ordenar mediciones por posición
        measurements_sorted = sorted(measurements, key=lambda m: m['position'])
        positions = [m['position'] for m in measurements_sorted]
        diameters = [m['diameter'] for m in measurements_sorted]
        
        # Dibujar perfil
        self.edit_ax.plot(positions, diameters, 'b-', linewidth=2, label='Perfil', picker=5)
        
        # Dibujar puntos interactivos
        self.edit_ax.plot(positions, diameters, 'ro', markersize=8, picker=5, label='Puntos editables')
        
        self.edit_ax.set_xlabel('Posición (mm)', fontsize=10)
        self.edit_ax.set_ylabel('Diámetro (mm)', fontsize=10)
        self.edit_ax.set_title(f'Edición de Geometría: {self.current_part.capitalize()}', fontsize=12)
        self.edit_ax.legend(loc='best', fontsize=8)
        self.edit_ax.grid(True, alpha=0.3)
        
        # Asegurar que el gráfico se actualice correctamente
        self.edit_ax.relim()  # Recalcular límites
        self.edit_ax.autoscale_view()  # Ajustar vista automáticamente
        
        # Dibujar agujeros DESPUÉS de establecer los límites para calcular correctamente la relación de aspecto
        holes_pos = part_data.get('Holes position', [])
        holes_diam = part_data.get('Holes diameter', [])
        
        if holes_pos:
            # Asegurar que holes_diam tenga la misma longitud que holes_pos
            while len(holes_diam) < len(holes_pos):
                holes_diam.append(0.0)
            
            # Calcular la relación de aspecto de los ejes para dibujar círculos correctos
            xlim = self.edit_ax.get_xlim()
            ylim = self.edit_ax.get_ylim()
            x_range = xlim[1] - xlim[0]
            y_range = ylim[1] - ylim[0]
            
            # Obtener el tamaño de la figura en pulgadas
            fig_width, fig_height = self.edit_figure.get_size_inches()
            
            # Calcular la relación de aspecto de los ejes
            # Esto considera tanto el rango de datos como el tamaño físico del gráfico
            ax_bbox = self.edit_ax.get_position()
            ax_width = ax_bbox.width * fig_width
            ax_height = ax_bbox.height * fig_height
            
            # Relación de aspecto: cuántas unidades de Y por unidad de X en la pantalla
            aspect_ratio = (y_range / ax_height) / (x_range / ax_width)
            
            # Dibujar agujeros como círculos en el perfil
            for i, (h_pos, h_diam_spec) in enumerate(zip(holes_pos, holes_diam)):
                # Interpolar diámetro del perfil en la posición del agujero
                profile_diam = np.interp(h_pos, positions, diameters)
                
                # Detectar si el agujero es cónico (lista [diam_out, diam_in]) o cilindro (número)
                is_cone = isinstance(h_diam_spec, (list, tuple)) and len(h_diam_spec) == 2
                
                if is_cone:
                    diam_out, diam_in = float(h_diam_spec[0]), float(h_diam_spec[1])
                    # Agujero cónico: dibujar dos elipses concéntricas
                    # Elipse externa (más pequeña, diámetro externo)
                    ellipse_outer = Ellipse((h_pos, profile_diam), 
                                          width=diam_out, 
                                          height=diam_out * aspect_ratio,
                                          fill=False, edgecolor='green', linewidth=2, 
                                          linestyle='--', alpha=0.8, zorder=5)
                    self.edit_ax.add_patch(ellipse_outer)
                    # Elipse interna (más grande, diámetro interno)
                    ellipse_inner = Ellipse((h_pos, profile_diam), 
                                           width=diam_in, 
                                           height=diam_in * aspect_ratio,
                                           fill=False, edgecolor='green', linewidth=1.5, 
                                           linestyle=':', alpha=0.6, zorder=5)
                    self.edit_ax.add_patch(ellipse_inner)
                    
                    # También dibujar un punto central para facilitar la selección
                    self.edit_ax.plot(h_pos, profile_diam, 'go', markersize=8, picker=10, zorder=6)
                    
                    # Anotación con información del agujero
                    label_text = f'H{i+1}\nØ{diam_out:.1f}/{diam_in:.1f}mm'
                    self.edit_ax.annotate(label_text, (h_pos, profile_diam), 
                                        textcoords="offset points", xytext=(0,20), 
                                        ha='center', fontsize=8, color='green',
                                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                                                edgecolor='green', alpha=0.8), zorder=7)
                elif isinstance(h_diam_spec, (int, float)) and h_diam_spec > 0:
                    # Agujero cilíndrico
                    h_diam = float(h_diam_spec)
                    # Dibujar elipse que se verá como círculo
                    # El ancho en X es el diámetro, el alto en Y es el diámetro ajustado por aspect_ratio
                    ellipse = Ellipse((h_pos, profile_diam), 
                                    width=h_diam, 
                                    height=h_diam * aspect_ratio,
                                    fill=False, edgecolor='green', linewidth=2, 
                                    linestyle='--', alpha=0.8, zorder=5)
                    self.edit_ax.add_patch(ellipse)
                    
                    # También dibujar un punto central para facilitar la selección
                    self.edit_ax.plot(h_pos, profile_diam, 'go', markersize=8, picker=10, zorder=6)
                    
                    # Anotación con información del agujero
                    label_text = f'H{i+1}\nØ{h_diam:.1f}mm'
                    self.edit_ax.annotate(label_text, (h_pos, profile_diam), 
                                        textcoords="offset points", xytext=(0,20), 
                                        ha='center', fontsize=8, color='green',
                                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', 
                                                edgecolor='green', alpha=0.8), zorder=7)
                else:
                    # Si el diámetro es 0 o inválido, solo mostrar un punto pequeño
                    self.edit_ax.plot(h_pos, profile_diam, 'go', markersize=6, picker=10, zorder=6)
                    self.edit_ax.annotate(f'H{i+1}', (h_pos, profile_diam), 
                                        textcoords="offset points", xytext=(0,10), 
                                        ha='center', fontsize=8, color='green', zorder=7)
        
        self.edit_figure.tight_layout()
        self.edit_canvas.draw()  # Usar draw() en lugar de draw_idle() para actualización inmediata
    
    def _on_plot_click(self, event):
        """Maneja clicks en el gráfico de edición."""
        if event.inaxes != self.edit_ax or event.button != 1:
            return
        
        part_data = self.current_data.get(self.current_part, {})
        measurements = part_data.get('measurements', [])
        measurements_sorted = sorted(measurements, key=lambda m: m['position'])
        
        positions = np.array([m['position'] for m in measurements_sorted])
        diameters = np.array([m['diameter'] for m in measurements_sorted])
        
        # Detectar si se clickeó cerca de un punto existente
        threshold = 5  # pixels
        for i, (pos, diam) in enumerate(zip(positions, diameters)):
            display_coords = self.edit_ax.transData.transform((pos, diam))
            event_coords = np.array([event.x, event.y])
            distance = np.linalg.norm(display_coords - event_coords)
            
            if distance < threshold:
                # Iniciar drag de punto
                self.dragging_point = i
                return
        
        # Detectar si se clickeó cerca de un agujero
        holes_pos = part_data.get('Holes position', [])
        if holes_pos:
            for i, h_pos in enumerate(holes_pos):
                profile_diam = np.interp(h_pos, positions, diameters)
                display_coords = self.edit_ax.transData.transform((h_pos, profile_diam))
                event_coords = np.array([event.x, event.y])
                distance = np.linalg.norm(display_coords - event_coords)
                
                if distance < threshold * 1.5:
                    # Iniciar drag de agujero
                    self.dragging_hole = i
                    return
        
        # Si no se clickeó en un punto existente, agregar nuevo punto en la línea
        # (solo si está cerca de la línea del perfil)
        if len(positions) >= 2:
            # Verificar si el click está cerca de la línea
            x_click = event.xdata
            y_click = event.ydata
            
            if positions[0] <= x_click <= positions[-1]:
                y_interp = np.interp(x_click, positions, diameters)
                
                # Distancia en coordenadas de datos
                y_threshold = (diameters.max() - diameters.min()) * 0.05
                
                if abs(y_click - y_interp) < y_threshold:
                    # Agregar nuevo punto
                    new_meas = {'position': float(x_click), 'diameter': float(y_interp)}
                    measurements.append(new_meas)
                    self._mark_modified()
                    self._update_measurements_table()
                    self._update_edit_plot()
    
    def _on_plot_motion(self, event):
        """Maneja el movimiento del mouse durante drag."""
        if event.inaxes != self.edit_ax:
            return
        
        part_data = self.current_data.get(self.current_part, {})
        
        if self.dragging_point is not None:
            measurements = part_data.get('measurements', [])
            measurements_sorted = sorted(measurements, key=lambda m: m['position'])
            
            if 0 <= self.dragging_point < len(measurements_sorted):
                # Actualizar posición del punto
                measurements_sorted[self.dragging_point]['position'] = float(event.xdata)
                measurements_sorted[self.dragging_point]['diameter'] = float(event.ydata)
                
                # Actualizar datos
                part_data['measurements'] = measurements_sorted
                
                self._update_edit_plot()
        
        elif self.dragging_hole is not None:
            holes_pos = part_data.get('Holes position', [])
            
            if 0 <= self.dragging_hole < len(holes_pos):
                # Actualizar posición del agujero
                holes_pos[self.dragging_hole] = float(event.xdata)
                
                self._update_edit_plot()
    
    def _on_plot_release(self, event):
        """Maneja la liberación del botón del mouse."""
        if self.dragging_point is not None or self.dragging_hole is not None:
            self._mark_modified()
            
            if self.dragging_point is not None:
                self._update_measurements_table()
            
            if self.dragging_hole is not None:
                self._update_holes_table()
            
            self.dragging_point = None
            self.dragging_hole = None
    
    def _on_measurements_table_changed(self, row, column):
        """Maneja cambios en la tabla de mediciones."""
        if self.measurements_table.signalsBlocked():
            return
        
        try:
            part_data = self.current_data.get(self.current_part, {})
            measurements = part_data.get('measurements', [])
            
            if row >= len(measurements):
                return
            
            pos_text = self.measurements_table.item(row, 0).text()
            diam_text = self.measurements_table.item(row, 1).text()
            
            measurements[row]['position'] = float(pos_text)
            measurements[row]['diameter'] = float(diam_text)
            
            self._mark_modified()
            self._update_edit_plot()
        
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error actualizando medición: {e}")
    
    def _on_holes_table_changed(self, row, column):
        """Maneja cambios en la tabla de agujeros."""
        if self.holes_table.signalsBlocked():
            return
        
        try:
            part_data = self.current_data.get(self.current_part, {})
            
            holes_pos = part_data.setdefault('Holes position', [])
            holes_diam = part_data.setdefault('Holes diameter', [])
            holes_chim = part_data.setdefault('Holes chimney', [])
            holes_diam_out = part_data.setdefault('Holes diameter_out', [])
            
            # Asegurar que todos los arrays tengan la misma longitud
            max_len = max(len(holes_pos), len(holes_diam), len(holes_chim), len(holes_diam_out))
            
            # Extender arrays si es necesario
            while len(holes_pos) < max_len:
                holes_pos.append(0.0)
            while len(holes_diam) < max_len:
                holes_diam.append(0.0)
            while len(holes_chim) < max_len:
                holes_chim.append(0.0)
            while len(holes_diam_out) < max_len:
                holes_diam_out.append(0.0)
            
            if row >= len(holes_pos):
                return
            
            # Obtener el item de la tabla (puede ser None si se está editando)
            item = self.holes_table.item(row, column)
            if item is None:
                return
            
            # Actualizar el valor correspondiente según la columna
            if column == 0:
                # Posición
                new_value = float(item.text())
                holes_pos[row] = new_value
            elif column == 1:
                # Diámetro (externo)
                new_value = float(item.text())
                # Verificar si hay diámetro interno para determinar formato
                diam_inner_item = self.holes_table.item(row, 2)
                if diam_inner_item and diam_inner_item.text().strip():
                    # Hay diámetro interno: formato cónico [diam_out, diam_in]
                    diam_in = float(diam_inner_item.text())
                    holes_diam[row] = [new_value, diam_in]
                    logger.debug(f"Agujero {row} en {self.current_part} actualizado a cono: diam_out={new_value:.3f}mm, diam_in={diam_in:.3f}mm")
                else:
                    # Solo diámetro externo: formato cilíndrico (número)
                    holes_diam[row] = new_value
                    logger.debug(f"Agujero {row} en {self.current_part} actualizado a cilindro: diam={new_value:.3f}mm")
            elif column == 2:
                # Diámetro Interno
                diam_inner_text = item.text().strip()
                diam_out_item = self.holes_table.item(row, 1)
                if diam_out_item:
                    diam_out = float(diam_out_item.text())
                    if diam_inner_text:
                        # Hay diámetro interno: formato cónico [diam_out, diam_in]
                        diam_in = float(diam_inner_text)
                        holes_diam[row] = [diam_out, diam_in]
                        logger.debug(f"Agujero {row} en {self.current_part} actualizado a cono: diam_out={diam_out:.3f}mm, diam_in={diam_in:.3f}mm")
                    else:
                        # Sin diámetro interno: formato cilíndrico (número)
                        holes_diam[row] = diam_out
                        logger.debug(f"Agujero {row} en {self.current_part} actualizado a cilindro: diam={diam_out:.3f}mm")
            elif column == 3:
                # Chimenea
                new_value = float(item.text())
                holes_chim[row] = new_value
            elif column == 4:
                # Diámetro externo (diam_out)
                new_value = float(item.text())
                holes_diam_out[row] = new_value
            
            # Asegurar que los cambios se reflejen en current_data
            part_data['Holes position'] = holes_pos
            part_data['Holes diameter'] = holes_diam
            part_data['Holes chimney'] = holes_chim
            part_data['Holes diameter_out'] = holes_diam_out
            
            self._mark_modified()
            self._update_edit_plot()
        
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error actualizando agujero: {e}")
    
    def _add_measurement_row(self):
        """Agrega una nueva fila de medición."""
        part_data = self.current_data.get(self.current_part, {})
        measurements = part_data.setdefault('measurements', [])
        
        # Agregar punto al final
        if measurements:
            last_pos = max(m['position'] for m in measurements)
            last_diam = measurements[-1]['diameter']
            new_pos = last_pos + 10.0
        else:
            new_pos = 0.0
            last_diam = 10.0
        
        measurements.append({'position': new_pos, 'diameter': last_diam})
        
        self._mark_modified()
        self._update_measurements_table()
        self._update_edit_plot()
    
    def _remove_measurement_row(self):
        """Elimina la fila de medición seleccionada."""
        current_row = self.measurements_table.currentRow()
        if current_row < 0:
            return
        
        part_data = self.current_data.get(self.current_part, {})
        measurements = part_data.get('measurements', [])
        
        if 0 <= current_row < len(measurements):
            del measurements[current_row]
            
            self._mark_modified()
            self._update_measurements_table()
            self._update_edit_plot()
    
    def _add_hole_row(self):
        """Agrega una nueva fila de agujero."""
        part_data = self.current_data.get(self.current_part, {})
        
        holes_pos = part_data.setdefault('Holes position', [])
        holes_diam = part_data.setdefault('Holes diameter', [])
        holes_chim = part_data.setdefault('Holes chimney', [])
        holes_diam_out = part_data.setdefault('Holes diameter_out', [])
        
        # Agregar agujero al final
        if holes_pos:
            new_pos = max(holes_pos) + 10.0
        else:
            new_pos = 50.0
        
        holes_pos.append(new_pos)
        holes_diam.append(5.0)
        holes_chim.append(0.0)
        holes_diam_out.append(0.0)
        
        self._mark_modified()
        self._update_holes_table()
        self._update_edit_plot()
    
    def _remove_hole_row(self):
        """Elimina la fila de agujero seleccionada."""
        current_row = self.holes_table.currentRow()
        if current_row < 0:
            return
        
        part_data = self.current_data.get(self.current_part, {})
        
        holes_pos = part_data.get('Holes position', [])
        holes_diam = part_data.get('Holes diameter', [])
        holes_chim = part_data.get('Holes chimney', [])
        holes_diam_out = part_data.get('Holes diameter_out', [])
        
        if 0 <= current_row < len(holes_pos):
            del holes_pos[current_row]
            if current_row < len(holes_diam):
                del holes_diam[current_row]
            if current_row < len(holes_chim):
                del holes_chim[current_row]
            if current_row < len(holes_diam_out):
                del holes_diam_out[current_row]
            
            self._mark_modified()
            self._update_holes_table()
            self._update_edit_plot()
    
    def _mark_modified(self):
        """Marca el estado como modificado."""
        self.is_modified = True
        self._set_status("Modificado (sin guardar)")
    
    def _set_status(self, message: str):
        """Actualiza el mensaje de estado."""
        self.status_label.setText(message)
    
    def _save_version(self):
        """Guarda la versión actual en el historial."""
        description, ok = QInputDialog.getText(
            self, "Guardar Versión", 
            "Descripción de la versión (opcional):"
        )
        
        if ok:
            self.version_history.save_version(self.current_data, description or "")
            self.is_modified = False
            self._update_version_list()
            self._update_undo_redo_buttons()
            self._set_status("Versión guardada")
    
    def _undo(self):
        """Deshacer cambios."""
        data = self.version_history.undo()
        if data:
            self.current_data = data
            self._update_all()
            self._set_status("Deshecho")
    
    def _redo(self):
        """Rehacer cambios."""
        data = self.version_history.redo()
        if data:
            self.current_data = data
            self._update_all()
            self._set_status("Rehecho")
    
    def _on_version_selected(self, item):
        """Maneja la selección de una versión en la lista."""
        version_index = self.version_list.row(item)
        if 0 <= version_index < len(self.version_history.versions):
            self.version_history.current_version_index = version_index
            self.current_data = self.version_history.get_current_version()
            self._update_all()
    
    def _reset_to_original(self):
        """Resetea la geometría a la versión original."""
        reply = QMessageBox.question(
            self, "Confirmar Reset",
            "¿Está seguro de que desea resetear a la versión original? Se perderán los cambios no guardados.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.current_data = copy.deepcopy(self.original_flute_data.data)
            self._update_all()
            self._set_status("Reseteado a original")
    
    def _load_in_main_gui(self):
        """
        Carga la versión actual en la GUI principal para análisis completo.
        El editor permanece abierto para iteraciones rápidas.
        """
        try:
            # IMPORTANTE: Usar self.current_data directamente, no get_current_version()
            # porque get_current_version() devuelve la última versión guardada en el historial,
            # pero los cambios recientes en las tablas están en self.current_data
            current_data = copy.deepcopy(self.current_data)
            
            # Obtener información de la versión para el nombre
            version_info = self.version_history.versions[self.version_history.current_version_index]
            version_description = version_info.get('description', f"v{version_info['version_number']}")
            
            # Si hay cambios no guardados, agregar indicador
            if self.is_modified:
                version_description = f"{version_description}_unsaved"
            
            # Generar nombre descriptivo
            version_name = f"{self.flute_name}_edit_{version_description}"
            # Limpiar nombre (remover caracteres problemáticos)
            version_name = version_name.replace(" ", "_").replace("/", "_")
            
            # Obtener parámetros de cálculo
            self.temperature = float(self.temp_spinbox.value())
            self.la_frequency = float(self.la_freq_spinbox.value())
            include_pressure_flow = self.include_pf_checkbox.isChecked()
            
            # Deshabilitar botón durante el cálculo
            self.calculate_and_load_btn.setEnabled(False)
            self._set_status("Calculando análisis acústico...")
            QApplication.processEvents()
            
            # Crear FluteDataDB temporal (en memoria, no guardar en BD)
            temp_flute = FluteDataDB(
                source=current_data,
                source_name=version_name,
                temperature=self.temperature,
                la_frequency=self.la_frequency,
                skip_acoustic_analysis=False,  # Calcular análisis completo
                db_manager=None,  # No guardar en BD
                include_pressure_flow=include_pressure_flow
            )
            
            # IMPORTANTE: Preservar la geometría externa original del objeto base
            # en lugar de usar la geometría generada automáticamente
            if hasattr(self.original_flute_data, 'external_geometry') and self.original_flute_data.external_geometry:
                temp_flute.external_geometry = copy.deepcopy(self.original_flute_data.external_geometry)
                logger.debug(f"Geometría externa preservada de flauta original para versión {version_name}")
            
            # Emitir señal para que la GUI principal cargue esta flauta
            self.flute_loaded_for_analysis.emit(temp_flute)
            
            # Rehabilitar botón
            self.calculate_and_load_btn.setEnabled(True)
            
            # Mostrar mensaje de éxito
            QMessageBox.information(
                self, "Cargado en GUI",
                f"La versión '{version_description}' se ha cargado en la GUI principal.\n\n"
                f"Nombre: {version_name}\n\n"
                "Puedes revisar los resultados en las pestañas de análisis.\n"
                "El editor permanece abierto para seguir editando."
            )
            
            self._set_status(f"Cargado en GUI: {version_name}")
            
        except Exception as e:
            logger.error(f"Error cargando en GUI principal: {e}", exc_info=True)
            self.calculate_and_load_btn.setEnabled(True)
            QMessageBox.critical(
                self, "Error",
                f"Error calculando y cargando en GUI:\n{e}"
            )
            self._set_status("Error al cargar")
    
    # Métodos de comparación acústica (DEPRECADOS - ahora se usa GUI principal)
    # Mantenidos por compatibilidad pero ya no se usan
    
    def _recalculate_acoustic(self):
        """DEPRECADO: Usar _load_in_main_gui() en su lugar."""
        QMessageBox.information(
            self, "Funcionalidad Movida",
            "Esta funcionalidad ahora está disponible en el botón 'Calcular y Visualizar en GUI'.\n\n"
            "Los análisis se visualizan en la GUI principal con todas las pestañas disponibles."
        )
    
    def _update_comparison(self):
        """DEPRECADO: Usar _load_in_main_gui() en su lugar."""
        QMessageBox.information(
            self, "Funcionalidad Movida",
            "Esta funcionalidad ahora está disponible en el botón 'Calcular y Visualizar en GUI'.\n\n"
            "Los análisis se visualizan en la GUI principal con todas las pestañas disponibles."
        )
    
    def _update_comparison_plots(self):
        """DEPRECADO: Los gráficos de comparación fueron removidos. Usar GUI principal para análisis."""
        pass
    
    def _update_comparison_table(self):
        """DEPRECADO: La tabla de comparación fue removida. Usar GUI principal para análisis."""
        pass
    
    def _save_as_new_flute(self):
        """Guarda la geometría modificada como una nueva flauta."""
        # Determinar el número de versión
        version_num = self.version_history.current_version_index
        suggested_name = f"{self.flute_name}_v{version_num}"
        
        new_name, ok = QInputDialog.getText(
            self, "Guardar como Nueva Flauta",
            "Nombre de la nueva flauta:",
            text=suggested_name
        )
        
        if not ok or not new_name:
            return
        
        try:
            # Determinar directorio de guardado
            if hasattr(self.original_flute_data, 'source') and self.original_flute_data.source:
                base_dir = Path(self.original_flute_data.source).parent.parent
            else:
                base_dir = Path.cwd() / "data_json"
            
            new_flute_dir = base_dir / new_name
            new_flute_dir.mkdir(parents=True, exist_ok=True)
            
            # Guardar cada parte como JSON
            for part_name, part_data in self.current_data.items():
                if part_name in FLUTE_PARTS_ORDER:
                    json_path = new_flute_dir / f"{part_name}.json"
                    
                    # Crear copia profunda y limpiar datos temporales
                    save_data = copy.deepcopy(part_data)
                    
                    # Eliminar campos que no deben guardarse
                    fields_to_remove = ['_calculated_stopper_absolute_position_mm', 'Flute Model']
                    for field in fields_to_remove:
                        save_data.pop(field, None)
                    
                    # Asegurar que los arrays de agujeros estén completos y sincronizados
                    if 'Holes position' in save_data:
                        num_holes = len(save_data['Holes position'])
                        
                        # Asegurar que todos los arrays de agujeros tengan la misma longitud
                        for hole_field in ['Holes diameter', 'Holes chimney', 'Holes diameter_out']:
                            if hole_field not in save_data:
                                save_data[hole_field] = [0.0] * num_holes
                            elif len(save_data[hole_field]) < num_holes:
                                # Extender con valores por defecto
                                default_value = 0.0
                                save_data[hole_field].extend([default_value] * (num_holes - len(save_data[hole_field])))
                            elif len(save_data[hole_field]) > num_holes:
                                # Truncar
                                save_data[hole_field] = save_data[hole_field][:num_holes]
                    
                    # Ordenar mediciones por posición
                    if 'measurements' in save_data and isinstance(save_data['measurements'], list):
                        save_data['measurements'] = sorted(save_data['measurements'], key=lambda m: m.get('position', 0.0))
                    
                    # Agregar metadatos
                    # Actualizar valores de temperatura y diapasón desde los spinboxes
                    current_temp = float(self.temp_spinbox.value())
                    current_la_freq = float(self.la_freq_spinbox.value())
                    
                    save_data['_metadata'] = {
                        'created_from': self.flute_name,
                        'created_date': datetime.now().isoformat(),
                        'version': version_num,
                        'temperature': current_temp,
                        'la_frequency': current_la_freq,
                        'editor': 'flute_geometry_editor_qt'
                    }
                    
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(save_data, f, indent=2, ensure_ascii=False)
                    
                    logger.info(f"Guardado: {json_path}")
            
            QMessageBox.information(
                self, "Guardado Exitoso",
                f"Flauta guardada exitosamente en:\n{new_flute_dir}\n\n"
                f"Nota: Para recalcular el análisis acústico, cargue la flauta desde la GUI principal."
            )
            
            # Emitir señal
            self.flute_modified.emit(new_name)
            
            self.is_modified = False
            self._set_status(f"Guardado como {new_name}")
        
        except Exception as e:
            logger.error(f"Error guardando flauta: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error guardando flauta:\n{e}")


if __name__ == "__main__":
    # Test básico
    app = QApplication(sys.argv)
    
    # Crear datos de prueba
    test_data = {
        'headjoint': {
            'measurements': [
                {'position': 0.0, 'diameter': 19.0},
                {'position': 50.0, 'diameter': 19.5},
                {'position': 100.0, 'diameter': 20.0}
            ],
            'Holes position': [80.0],
            'Holes diameter': [12.0],
            'Holes chimney': [0.0],
            'Holes diameter_out': [0.0]
        }
    }
    
    # Mock FluteData
    class MockFluteData:
        def __init__(self):
            self.flute_model = "Test_Flute"
            self.data = test_data
            self.acoustic_analysis = {}
            self.source = None
    
    mock_flute = MockFluteData()
    editor = FluteGeometryEditor(mock_flute)
    editor.show()
    
    sys.exit(app.exec_())

