"""
Diálogo Qt para configurar y ejecutar análisis de sensibilidad.

Este módulo proporciona:
- Un `QDialog` (`SensitivityAnalysisDialog`) donde el usuario elige la flauta
  base, el parámetro a variar, el rango de valores y las opciones de cálculo.
- Un worker en `QThread` (`SensitivityWorker`) que ejecuta el análisis en
  segundo plano usando `SensitivityAnalyzer`, emitiendo señales de progreso.

Flujo GUI → núcleo:
- El usuario configura el análisis y pulsa “Generar y Cargar Variantes”.
- El diálogo crea un `SensitivityAnalyzer` con la flauta base seleccionada.
- `SensitivityWorker` llama a `run_analysis` en un hilo separado.
- Al finalizar, se emite `variants_ready(list[FluteDataDB])`, que la GUI
  principal usa para cargar las variantes (por ejemplo, como nueva pestaña).
- Opcionalmente, el usuario puede exportar un reporte PDF completo desde aquí.
"""

import logging
import numpy as np
from typing import List, Optional, Tuple
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QDoubleSpinBox, QSpinBox, QRadioButton, QButtonGroup,
    QLabel, QPushButton, QTextEdit, QCheckBox, QProgressBar, QApplication,
    QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from sensitivity_analysis import (
    SensitivityParameter, VariationConfig,
    FluteVariantGenerator, SensitivityAnalyzer
)
from flute_data_db import FluteDataDB
from constants import FLUTE_PARTS_ORDER

logger = logging.getLogger(__name__)


class SensitivityWorker(QThread):
    """Worker thread para ejecutar el análisis de sensibilidad sin bloquear la GUI."""
    progress = pyqtSignal(int, int, str)  # current, total, message
    finished = pyqtSignal(list)  # variants generated
    error = pyqtSignal(str)  # error message
    
    def __init__(self, analyzer: SensitivityAnalyzer, config: VariationConfig,
                 temperature: float, la_frequency: float,
                 calculate_acoustic: bool, include_pressure_flow: bool):
        super().__init__()
        self.analyzer = analyzer
        self.config = config
        self.temperature = temperature
        self.la_frequency = la_frequency
        self.calculate_acoustic = calculate_acoustic
        self.include_pressure_flow = include_pressure_flow
    
    def run(self):
        """Ejecuta el análisis en el thread."""
        try:
            variants = self.analyzer.run_analysis(
                self.config,
                temperature=self.temperature,
                la_frequency=self.la_frequency,
                calculate_acoustic=self.calculate_acoustic,
                include_pressure_flow=self.include_pressure_flow,
                progress_callback=self.progress.emit
            )
            self.finished.emit(variants)
        except Exception as e:
            logger.error(f"Error en análisis de sensibilidad: {e}", exc_info=True)
            self.error.emit(str(e))


class SensitivityAnalysisDialog(QDialog):
    """Diálogo para configurar y ejecutar análisis de sensibilidad."""
    
    # Señal emitida cuando las variantes están listas para cargar en la GUI
    variants_ready = pyqtSignal(list)
    
    def __init__(self, flute_ops_list, parent=None):
        super().__init__(parent)
        self.flute_ops_list = flute_ops_list
        self.generated_variants: List[FluteDataDB] = []
        
        self.setWindowTitle("Análisis de Sensibilidad")
        self.setModal(True)
        self.resize(700, 800)
        
        self._create_ui()
        
        # Conectar señales
        self._connect_signals()
        
        # Inicializar valores
        self._update_parameter_specific_controls()
    
    def _create_ui(self):
        """Crea la interfaz del diálogo."""
        layout = QVBoxLayout(self)
        
        # Sección 1: Selección de Flauta Base
        base_group = QGroupBox("Flauta Base")
        base_layout = QFormLayout(base_group)
        
        self.flute_combo = QComboBox()
        for flute_ops in self.flute_ops_list:
            self.flute_combo.addItem(flute_ops.flute_data.flute_model)
        base_layout.addRow("Flauta:", self.flute_combo)
        
        self.flute_info_label = QLabel()
        self.flute_info_label.setStyleSheet("color: gray; font-size: 9pt;")
        base_layout.addRow("Info:", self.flute_info_label)
        
        layout.addWidget(base_group)
        
        # Sección 2: Selección de Parámetro
        param_group = QGroupBox("Parámetro a Variar")
        param_layout = QFormLayout(param_group)
        
        # Ordenar parámetros por prioridad según las preferencias del usuario
        priority_order = [
            SensitivityParameter.HOLE_UNDERCUT,
            SensitivityParameter.PART_TAPER,
            SensitivityParameter.STOPPER_POSITION,
            SensitivityParameter.HOLE_DIAMETER,
            SensitivityParameter.EMBOUCHURE_DIAMETER,
            SensitivityParameter.HOLE_POSITION
        ]
        
        self.parameter_combo = QComboBox()
        for param in priority_order:
            self.parameter_combo.addItem(param.get_display_name(), param)
        param_layout.addRow("Parámetro:", self.parameter_combo)
        
        # Selectores específicos (se mostrarán según el parámetro)
        self.part_combo = QComboBox()
        for part in FLUTE_PARTS_ORDER:
            self.part_combo.addItem(part.capitalize(), part)
        self.part_label = QLabel("Parte:")
        param_layout.addRow(self.part_label, self.part_combo)
        
        self.hole_spinbox = QSpinBox()
        self.hole_spinbox.setMinimum(0)
        self.hole_spinbox.setMaximum(20)
        self.hole_spinbox.setValue(0)
        self.hole_spinbox.setSpecialValueText("Todos los agujeros")
        self.hole_label = QLabel("Agujero:")
        param_layout.addRow(self.hole_label, self.hole_spinbox)
        
        layout.addWidget(param_group)
        
        # Sección 3: Configuración de Variación
        variation_group = QGroupBox("Rango de Variación")
        variation_layout = QFormLayout(variation_group)
        
        self.current_value_label = QLabel("0.0")
        self.current_value_label.setStyleSheet("font-weight: bold;")
        variation_layout.addRow("Valor actual:", self.current_value_label)
        
        self.min_value_spinbox = QDoubleSpinBox()
        self.min_value_spinbox.setDecimals(2)
        self.min_value_spinbox.setRange(-1000.0, 1000.0)
        self.min_value_spinbox.setValue(0.0)
        variation_layout.addRow("Valor mínimo:", self.min_value_spinbox)
        
        self.max_value_spinbox = QDoubleSpinBox()
        self.max_value_spinbox.setDecimals(2)
        self.max_value_spinbox.setRange(-1000.0, 1000.0)
        self.max_value_spinbox.setValue(10.0)
        variation_layout.addRow("Valor máximo:", self.max_value_spinbox)
        
        # Radio buttons para seleccionar modo
        step_mode_layout = QHBoxLayout()
        self.num_steps_radio = QRadioButton("Número de pasos:")
        self.num_steps_radio.setChecked(True)
        self.step_size_radio = QRadioButton("Tamaño de paso:")
        
        step_mode_group = QButtonGroup(self)
        step_mode_group.addButton(self.num_steps_radio)
        step_mode_group.addButton(self.step_size_radio)
        
        step_mode_layout.addWidget(self.num_steps_radio)
        step_mode_layout.addWidget(self.step_size_radio)
        variation_layout.addRow("Modo:", step_mode_layout)
        
        self.num_steps_spinbox = QSpinBox()
        self.num_steps_spinbox.setMinimum(2)
        self.num_steps_spinbox.setMaximum(100)
        self.num_steps_spinbox.setValue(10)
        variation_layout.addRow("Número de pasos:", self.num_steps_spinbox)
        
        self.step_size_spinbox = QDoubleSpinBox()
        self.step_size_spinbox.setDecimals(3)
        self.step_size_spinbox.setRange(0.001, 100.0)
        self.step_size_spinbox.setValue(1.0)
        self.step_size_spinbox.setEnabled(False)
        variation_layout.addRow("Tamaño de paso:", self.step_size_spinbox)
        
        # Label calculado
        self.calculated_label = QLabel()
        self.calculated_label.setStyleSheet("color: blue; font-weight: bold;")
        variation_layout.addRow("", self.calculated_label)
        
        # Label para mostrar rango de pendientes (solo para PART_TAPER)
        self.slope_range_label = QLabel()
        self.slope_range_label.setStyleSheet("color: green; font-size: 9pt;")
        self.slope_range_label.setVisible(False)
        variation_layout.addRow("", self.slope_range_label)
        
        layout.addWidget(variation_group)
        
        # Sección 4: Previsualización
        preview_group = QGroupBox("Previsualización")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(100)
        preview_layout.addWidget(self.preview_text)
        
        layout.addWidget(preview_group)
        
        # Sección 5: Opciones de Cálculo
        calc_group = QGroupBox("Opciones de Cálculo")
        calc_layout = QFormLayout(calc_group)
        
        self.calc_acoustic_checkbox = QCheckBox()
        self.calc_acoustic_checkbox.setChecked(True)
        calc_layout.addRow("Calcular análisis acústico:", self.calc_acoustic_checkbox)
        
        self.include_pf_checkbox = QCheckBox()
        self.include_pf_checkbox.setChecked(False)
        calc_layout.addRow("Incluir datos de presión/flujo:", self.include_pf_checkbox)
        
        self.temperature_spinbox = QDoubleSpinBox()
        self.temperature_spinbox.setRange(-20.0, 50.0)
        self.temperature_spinbox.setValue(20.0)
        self.temperature_spinbox.setSuffix(" °C")
        calc_layout.addRow("Temperatura:", self.temperature_spinbox)
        
        self.la_freq_spinbox = QDoubleSpinBox()
        self.la_freq_spinbox.setRange(300.0, 500.0)
        self.la_freq_spinbox.setValue(415.0)
        self.la_freq_spinbox.setSuffix(" Hz")
        calc_layout.addRow("Diapasón (La):", self.la_freq_spinbox)
        
        layout.addWidget(calc_group)
        
        # Barra de progreso (inicialmente oculta)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        self.progress_label.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(self.progress_label)
        
        # Botones
        buttons_layout = QHBoxLayout()
        
        self.generate_btn = QPushButton("Generar y Cargar Variantes")
        self.generate_btn.setDefault(True)
        font = self.generate_btn.font()
        font.setBold(True)
        self.generate_btn.setFont(font)
        self.generate_btn.clicked.connect(self._generate_variants)
        
        self.export_pdf_btn = QPushButton("📄 Exportar Reporte PDF")
        self.export_pdf_btn.setEnabled(False)  # Deshabilitado hasta que se generen variantes
        self.export_pdf_btn.setToolTip("Genera un reporte PDF completo con todas las métricas y gráficos de evolución")
        self.export_pdf_btn.clicked.connect(self._export_pdf_report)
        
        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.generate_btn)
        buttons_layout.addWidget(self.export_pdf_btn)
        buttons_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(buttons_layout)
        
        # Guardar referencia al analyzer para exportación
        self.analyzer = None
        self.current_config = None
    
    def _connect_signals(self):
        """Conecta señales."""
        self.flute_combo.currentIndexChanged.connect(self._update_flute_info)
        self.parameter_combo.currentIndexChanged.connect(self._update_parameter_specific_controls)
        self.parameter_combo.currentIndexChanged.connect(self._update_current_value)
        self.part_combo.currentIndexChanged.connect(self._update_current_value)
        self.hole_spinbox.valueChanged.connect(self._update_current_value)
        
        # Conectar cambios en min/max para actualizar rango de pendientes y previsualización
        self.min_value_spinbox.valueChanged.connect(self._update_slope_range)
        self.max_value_spinbox.valueChanged.connect(self._update_slope_range)
        
        self.num_steps_radio.toggled.connect(self._update_step_mode)
        self.step_size_radio.toggled.connect(self._update_step_mode)
        
        self.min_value_spinbox.valueChanged.connect(self._update_preview)
        self.max_value_spinbox.valueChanged.connect(self._update_preview)
        self.num_steps_spinbox.valueChanged.connect(self._update_preview)
        self.step_size_spinbox.valueChanged.connect(self._update_preview)
        
        # Inicializar previsualización
        self._update_flute_info()
        self._update_preview()
    
    def _update_flute_info(self):
        """Actualiza información de la flauta seleccionada."""
        idx = self.flute_combo.currentIndex()
        if idx < 0 or idx >= len(self.flute_ops_list):
            return
        
        flute_data = self.flute_ops_list[idx].flute_data
        info_parts = []
        
        # Información básica
        if hasattr(flute_data, 'acoustic_length_mm'):
            info_parts.append(f"Largo acústico: {flute_data.acoustic_length_mm:.1f} mm")
        
        # Número de agujeros
        total_holes = 0
        for part_name in FLUTE_PARTS_ORDER:
            part_data = flute_data.data.get(part_name, {})
            holes_pos = part_data.get('Holes position', [])
            total_holes += len(holes_pos)
        
        info_parts.append(f"Agujeros: {total_holes}")
        
        self.flute_info_label.setText(" | ".join(info_parts))
        self._update_current_value()
    
    def _calculate_current_slope(self, part_name: str) -> Optional[float]:
        """
        Calcula la pendiente actual de una parte usando solo el cuerpo acústico.
        
        Usa combined_measurements si está disponible (más confiable), o calcula
        desde las mediciones de la parte aplicando el mismo filtrado que en
        _apply_part_taper.
        
        Returns:
            Pendiente en mm/mm, o None si no se puede calcular
        """
        idx = self.flute_combo.currentIndex()
        if idx < 0 or idx >= len(self.flute_ops_list):
            return None
        
        flute_data = self.flute_ops_list[idx].flute_data
        
        # Intentar usar combined_measurements primero (más confiable)
        combined_measurements = flute_data.combined_measurements
        if combined_measurements:
            # Filtrar mediciones de la parte específica desde combined_measurements
            part_measurements = [
                m for m in combined_measurements 
                if m.get('source_part_name') == part_name
            ]
            
            if len(part_measurements) >= 2:
                # Usar posiciones relativas a la parte (source_relative_position)
                # o posiciones absolutas, dependiendo de lo que esté disponible
                positions = []
                diameters = []
                
                for m in part_measurements:
                    # Para headjoint, las posiciones en combined_measurements son absolutas
                    # pero necesitamos posiciones relativas a la parte para calcular la pendiente
                    if part_name == FLUTE_PARTS_ORDER[0]:  # Headjoint
                        # Usar source_relative_position que es relativo a la parte
                        pos = m.get('source_relative_position', m.get('position', 0.0))
                    else:
                        # Para otras partes, usar source_relative_position
                        pos = m.get('source_relative_position', m.get('position', 0.0))
                    
                    positions.append(pos)
                    diameters.append(m.get('diameter', 0.0))
                
                if len(positions) >= 2:
                    try:
                        slope, _ = np.polyfit(positions, diameters, 1)
                        return slope
                    except:
                        pass
        
        # Fallback: calcular desde las mediciones de la parte directamente
        part_data = flute_data.data.get(part_name, {})
        if not part_data:
            return None
        
        measurements = part_data.get('measurements', [])
        if len(measurements) < 2:
            return None
        
        mortise_length = part_data.get('Mortise length', 0.0)
        total_length = part_data.get('Total length', 0.0)
        
        # Determinar el rango del cuerpo acústico (misma lógica que en _apply_part_taper)
        if part_name == FLUTE_PARTS_ORDER[0]:  # Headjoint
            # Intentar obtener la posición del corcho de varias formas
            stopper_pos = part_data.get('_calculated_stopper_absolute_position_mm')
            
            # Si no está en part_data, intentar desde flute_data directamente
            if stopper_pos is None:
                headjoint_data = flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                stopper_pos = headjoint_data.get('_calculated_stopper_absolute_position_mm')
            
            # Si aún no está disponible, usar combined_measurements para encontrar el inicio
            if stopper_pos is None and combined_measurements:
                # Buscar la primera medición del headjoint en combined_measurements
                for m in combined_measurements:
                    if m.get('source_part_name') == part_name:
                        stopper_pos = m.get('source_relative_position', m.get('position', 0.0))
                        break
            
            # Último fallback: usar primera medición
            if stopper_pos is None:
                stopper_pos = measurements[0]['position'] if measurements else 0.0
            
            acoustic_start = stopper_pos
            acoustic_end = total_length - mortise_length
        elif part_name == FLUTE_PARTS_ORDER[1]:  # Left
            acoustic_start = 0.0
            acoustic_end = total_length
        else:  # Right, Foot
            acoustic_start = mortise_length
            acoustic_end = total_length
        
        # Filtrar mediciones del cuerpo acústico
        acoustic_measurements = []
        for m in measurements:
            pos = m['position']
            if pos >= acoustic_start - 1e-6 and pos <= acoustic_end + 1e-6:
                acoustic_measurements.append(m)
        
        if len(acoustic_measurements) < 2:
            logger.debug(f"No hay suficientes mediciones acústicas para {part_name}: "
                        f"rango {acoustic_start:.2f} a {acoustic_end:.2f} mm, "
                        f"{len(acoustic_measurements)} mediciones encontradas")
            return None
        
        # Calcular pendiente
        positions = [m['position'] for m in acoustic_measurements]
        diameters = [m['diameter'] for m in acoustic_measurements]
        
        try:
            slope, _ = np.polyfit(positions, diameters, 1)
            return slope
        except Exception as e:
            logger.debug(f"Error calculando pendiente para {part_name}: {e}")
            return None
    
    def _update_parameter_specific_controls(self):
        """Muestra/oculta controles específicos según el parámetro seleccionado."""
        param = self.parameter_combo.currentData()
        
        # Determinar qué controles mostrar
        show_part = (param == SensitivityParameter.PART_TAPER)
        show_hole = (param in [SensitivityParameter.HOLE_UNDERCUT,
                              SensitivityParameter.HOLE_DIAMETER,
                              SensitivityParameter.HOLE_POSITION])
        
        self.part_label.setVisible(show_part)
        self.part_combo.setVisible(show_part)
        
        self.hole_label.setVisible(show_hole)
        self.hole_spinbox.setVisible(show_hole)
        
        # Configurar unidades y rangos según el parámetro
        unit = param.get_unit()
        
        if param == SensitivityParameter.HOLE_UNDERCUT:
            self.min_value_spinbox.setValue(0.0)
            self.max_value_spinbox.setValue(15.0)
            self.min_value_spinbox.setSuffix(f" {unit}")
            self.max_value_spinbox.setSuffix(f" {unit}")
            self.slope_range_label.setVisible(False)
        elif param == SensitivityParameter.PART_TAPER:
            # Para PART_TAPER, calcular rango razonable basado en pendiente actual
            self.slope_range_label.setVisible(True)
            # Los valores por defecto se ajustarán en _update_current_value
            self.min_value_spinbox.setValue(-50.0)
            self.max_value_spinbox.setValue(50.0)
            self.min_value_spinbox.setSuffix(f" {unit}")
            self.max_value_spinbox.setSuffix(f" {unit}")
        elif param == SensitivityParameter.STOPPER_POSITION:
            self.min_value_spinbox.setValue(-10.0)
            self.max_value_spinbox.setValue(10.0)
            self.min_value_spinbox.setSuffix(f" {unit}")
            self.max_value_spinbox.setSuffix(f" {unit}")
            self.slope_range_label.setVisible(False)
        elif param == SensitivityParameter.HOLE_DIAMETER:
            self.min_value_spinbox.setValue(-2.0)
            self.max_value_spinbox.setValue(2.0)
            self.min_value_spinbox.setSuffix(f" {unit}")
            self.max_value_spinbox.setSuffix(f" {unit}")
            self.slope_range_label.setVisible(False)
        elif param == SensitivityParameter.EMBOUCHURE_DIAMETER:
            self.min_value_spinbox.setValue(-2.0)
            self.max_value_spinbox.setValue(2.0)
            self.min_value_spinbox.setSuffix(f" {unit}")
            self.max_value_spinbox.setSuffix(f" {unit}")
            self.slope_range_label.setVisible(False)
        elif param == SensitivityParameter.HOLE_POSITION:
            self.min_value_spinbox.setValue(-10.0)
            self.max_value_spinbox.setValue(10.0)
            self.min_value_spinbox.setSuffix(f" {unit}")
            self.max_value_spinbox.setSuffix(f" {unit}")
            self.slope_range_label.setVisible(False)
        
        self._update_current_value()
        self._update_preview()
    
    def _update_current_value(self):
        """Actualiza el valor actual del parámetro."""
        idx = self.flute_combo.currentIndex()
        if idx < 0 or idx >= len(self.flute_ops_list):
            self.current_value_label.setText("N/A")
            return
        
        param = self.parameter_combo.currentData()
        unit = param.get_unit()
        
        if param == SensitivityParameter.PART_TAPER:
            # Calcular pendiente actual de la parte seleccionada
            part_name = self.part_combo.currentData()
            if part_name:
                current_slope = self._calculate_current_slope(part_name)
                if current_slope is not None:
                    self.current_value_label.setText(
                        f"Pendiente actual: {current_slope:.6f} mm/mm"
                    )
                    # Ajustar rango razonable basado en la pendiente
                    # Si la pendiente es muy pequeña (< 0.001), sugerir un rango porcentual más amplio
                    # para que haya variación significativa
                    if abs(current_slope) < 0.001:
                        # Pendiente muy pequeña: usar rango porcentual amplio para generar variación
                        # Por ejemplo, variar entre -200% y +200% para obtener variación significativa
                        self.min_value_spinbox.setValue(-200.0)
                        self.max_value_spinbox.setValue(200.0)
                    else:
                        # Pendiente normal: usar porcentaje estándar
                        self.min_value_spinbox.setValue(-50.0)
                        self.max_value_spinbox.setValue(50.0)
                    
                    self.min_value_spinbox.setSuffix(f" {unit}")
                    self.max_value_spinbox.setSuffix(f" {unit}")
                    self._update_slope_range()
                else:
                    self.current_value_label.setText("No se pudo calcular pendiente")
                    self.slope_range_label.setText("")
            else:
                self.current_value_label.setText("Selecciona una parte")
                self.slope_range_label.setText("")
        else:
            # Para otros parámetros, mostrar placeholder
            self.current_value_label.setText(f"0.0 {unit} (base)")
            self.slope_range_label.setVisible(False)
    
    def _update_step_mode(self):
        """Actualiza el modo de configuración de pasos."""
        use_num_steps = self.num_steps_radio.isChecked()
        
        self.num_steps_spinbox.setEnabled(use_num_steps)
        self.step_size_spinbox.setEnabled(not use_num_steps)
        
        self._update_preview()
    
    def _update_slope_range(self):
        """Actualiza el label que muestra el rango de pendientes para PART_TAPER."""
        param = self.parameter_combo.currentData()
        if param != SensitivityParameter.PART_TAPER:
            return
        
        part_name = self.part_combo.currentData()
        if not part_name:
            self.slope_range_label.setText("")
            return
        
        current_slope = self._calculate_current_slope(part_name)
        if current_slope is None:
            self.slope_range_label.setText("")
            return
        
        min_pct = self.min_value_spinbox.value()
        max_pct = self.max_value_spinbox.value()
        
        # Calcular pendientes resultantes (modo porcentual)
        min_slope = current_slope * (1.0 + min_pct / 100.0)
        max_slope = current_slope * (1.0 + max_pct / 100.0)
        
        # Mostrar rango de pendientes resultante
        self.slope_range_label.setText(
            f"Rango de pendientes resultante: {min_slope:.6f} a {max_slope:.6f} mm/mm "
            f"(variación: {min_pct:+.1f}% a {max_pct:+.1f}%)"
        )
    
    def _update_preview(self):
        """Actualiza la previsualización de variantes."""
        min_val = self.min_value_spinbox.value()
        max_val = self.max_value_spinbox.value()
        
        if min_val >= max_val:
            self.preview_text.setPlainText("Error: Valor mínimo debe ser menor que el máximo.")
            self.calculated_label.setText("")
            return
        
        # Calcular número de pasos o tamaño de paso
        if self.num_steps_radio.isChecked():
            num_steps = self.num_steps_spinbox.value()
            step_size = (max_val - min_val) / (num_steps - 1) if num_steps > 1 else 0
            self.calculated_label.setText(f"Tamaño de paso calculado: {step_size:.3f}")
        else:
            step_size = self.step_size_spinbox.value()
            num_steps = int((max_val - min_val) / step_size) + 1
            self.calculated_label.setText(f"Número de pasos calculado: {num_steps}")
        
        # Generar lista de valores
        if num_steps > 1:
            values = [min_val + i * step_size for i in range(num_steps)]
        else:
            values = [min_val]
        
        # Para PART_TAPER, mostrar valores de pendiente reales
        param = self.parameter_combo.currentData()
        unit = param.get_unit()
        
        if param == SensitivityParameter.PART_TAPER:
            part_name = self.part_combo.currentData()
            current_slope = self._calculate_current_slope(part_name) if part_name else None
            
            if current_slope is not None:
                # Modo porcentual: mostrar porcentajes y pendientes resultantes
                preview_lines = [f"Se generarán {len(values)} variantes:\n"]
                preview_lines.append(f"Pendiente actual: {current_slope:.6f} mm/mm\n")
                
                if len(values) <= 15:
                    for i, val in enumerate(values, 1):
                        new_slope = current_slope * (1.0 + val / 100.0)
                        preview_lines.append(
                            f"{i}. {val:+.1f}% → Pendiente: {new_slope:.6f} mm/mm"
                        )
                else:
                    for i, val in enumerate(values[:5], 1):
                        new_slope = current_slope * (1.0 + val / 100.0)
                        preview_lines.append(
                            f"{i}. {val:+.1f}% → Pendiente: {new_slope:.6f} mm/mm"
                        )
                    preview_lines.append(f"... ({len(values) - 10} más) ...")
                    for i, val in enumerate(values[-5:], len(values)-4):
                        new_slope = current_slope * (1.0 + val / 100.0)
                        preview_lines.append(
                            f"{i}. {val:+.1f}% → Pendiente: {new_slope:.6f} mm/mm"
                        )
                
                self.preview_text.setPlainText("\n".join(preview_lines))
            else:
                # No se pudo calcular pendiente, mostrar valores porcentuales normales
                preview_lines = [f"Se generarán {len(values)} variantes:\n"]
                if len(values) <= 15:
                    for i, val in enumerate(values, 1):
                        preview_lines.append(f"{i}. {val:.3f} {unit}")
                else:
                    for i, val in enumerate(values[:5], 1):
                        preview_lines.append(f"{i}. {val:.3f} {unit}")
                    preview_lines.append(f"... ({len(values) - 10} más) ...")
                    for i, val in enumerate(values[-5:], len(values)-4):
                        preview_lines.append(f"{i}. {val:.3f} {unit}")
                self.preview_text.setPlainText("\n".join(preview_lines))
        else:
            # Para otros parámetros, mostrar valores normales
            preview_lines = [f"Se generarán {len(values)} variantes:\n"]
            
            if len(values) <= 15:
                for i, val in enumerate(values, 1):
                    preview_lines.append(f"{i}. {val:.3f} {unit}")
            else:
                for i, val in enumerate(values[:5], 1):
                    preview_lines.append(f"{i}. {val:.3f} {unit}")
                preview_lines.append(f"... ({len(values) - 10} más) ...")
                for i, val in enumerate(values[-5:], len(values)-4):
                    preview_lines.append(f"{i}. {val:.3f} {unit}")
            
            self.preview_text.setPlainText("\n".join(preview_lines))
    
    def _generate_variants(self):
        """Genera las variantes usando un worker thread."""
        # Validar configuración
        idx = self.flute_combo.currentIndex()
        if idx < 0:
            QMessageBox.warning(self, "Error", "Selecciona una flauta base.")
            return
        
        min_val = self.min_value_spinbox.value()
        max_val = self.max_value_spinbox.value()
        
        if min_val >= max_val:
            QMessageBox.warning(self, "Error", "El valor mínimo debe ser menor que el máximo.")
            return
        
        # Obtener flauta base
        base_flute = self.flute_ops_list[idx].flute_data
        
        # Crear configuración
        param = self.parameter_combo.currentData()
        
        config = VariationConfig(
            parameter=param,
            base_value=0.0,  # Placeholder
            min_value=min_val,
            max_value=max_val,
            num_steps=self.num_steps_spinbox.value() if self.num_steps_radio.isChecked() else None,
            step_size=self.step_size_spinbox.value() if self.step_size_radio.isChecked() else None,
            target_part=self.part_combo.currentData() if self.part_combo.isVisible() else None,
            target_hole=self.hole_spinbox.value() if self.hole_spinbox.isVisible() and self.hole_spinbox.value() > 0 else None
        )
        
        # Confirmar
        reply = QMessageBox.question(
            self,
            "Confirmar Generación",
            f"¿Generar {config.num_steps} variantes de {base_flute.flute_model}?\n\n"
            f"Parámetro: {param.get_display_name()}\n"
            f"Rango: {min_val:.2f} a {max_val:.2f} {param.get_unit()}\n\n"
            f"{'Se calcularán los análisis acústicos.' if self.calc_acoustic_checkbox.isChecked() else 'Sin análisis acústico.'}\n"
            f"{'Se incluirán datos de presión/flujo.' if self.include_pf_checkbox.isChecked() else ''}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Deshabilitar controles
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_bar.setMaximum(config.num_steps)
        
        # Crear analyzer y worker
        analyzer = SensitivityAnalyzer(base_flute)
        self.analyzer = analyzer  # Guardar referencia para exportación
        self.current_config = config  # Guardar configuración para exportación
        
        self.worker = SensitivityWorker(
            analyzer, config,
            self.temperature_spinbox.value(),
            self.la_freq_spinbox.value(),
            self.calc_acoustic_checkbox.isChecked(),
            self.include_pf_checkbox.isChecked()
        )
        
        # Conectar señales del worker
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        
        # Iniciar worker
        self.worker.start()
    
    def _on_progress(self, current: int, total: int, message: str):
        """Actualiza la barra de progreso."""
        self.progress_bar.setValue(current)
        self.progress_label.setText(message)
        QApplication.processEvents()
    
    def _on_finished(self, variants: List[FluteDataDB]):
        """Maneja la finalización exitosa."""
        self.generated_variants = variants
        
        # Habilitar botón de exportación PDF
        self.export_pdf_btn.setEnabled(True)
        
        # Ocultar barra de progreso
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        
        # Cambiar texto del botón de generar para indicar que ya se completó
        self.generate_btn.setText("✓ Análisis Completado")
        self.generate_btn.setEnabled(False)
        
        # Cambiar texto del botón Cancelar a "Cerrar"
        self.cancel_btn.setText("Cerrar")
        
        # Cargar variantes en la GUI principal inmediatamente
        # Emitir señal para que la GUI principal cargue las variantes
        if hasattr(self, 'variants_ready'):
            self.variants_ready.emit(variants)
        
        QMessageBox.information(
            self,
            "Análisis Completado",
            f"Se generaron exitosamente {len(variants)} variantes.\n\n"
            f"Las variantes se han cargado en la GUI principal.\n\n"
            f"Puedes exportar un reporte PDF completo usando el botón 'Exportar Reporte PDF'.\n\n"
            f"El diálogo permanecerá abierto para que puedas exportar el PDF cuando desees."
        )
        
        # NO cerrar el diálogo automáticamente - el usuario puede exportar PDF y luego cerrar
    
    def _on_error(self, error_message: str):
        """Maneja errores."""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.generate_btn.setEnabled(True)
        
        QMessageBox.critical(
            self,
            "Error",
            f"Error durante el análisis de sensibilidad:\n\n{error_message}"
        )
    
    def get_generated_variants(self) -> List[FluteDataDB]:
        """Retorna las variantes generadas."""
        return self.generated_variants
    
    def _export_pdf_report(self):
        """Exporta reporte PDF del análisis de sensibilidad."""
        if not self.analyzer or not self.current_config or not self.generated_variants:
            QMessageBox.warning(
                self,
                "Error",
                "No hay variantes generadas para exportar.\n"
                "Primero debes generar las variantes."
            )
            return
        
        # Obtener nombre de flauta base
        base_flute_name = self.analyzer.base_flute.flute_model if self.analyzer else "flauta"
        
        # Diálogo para seleccionar ubicación del archivo
        default_filename = f"sensibilidad_{base_flute_name}_{self.current_config.parameter.value}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Reporte PDF de Análisis de Sensibilidad",
            default_filename,
            "PDF Files (*.pdf)"
        )
        
        if not file_path:
            return
        
        try:
            from pathlib import Path
            output_path = Path(file_path)
            
            # Mostrar mensaje de progreso
            QMessageBox.information(
                self,
                "Generando Reporte",
                f"Generando reporte PDF...\n\n"
                f"Esto puede tardar unos momentos.\n"
                f"El archivo se guardará en:\n{file_path}"
            )
            
            QApplication.processEvents()
            
            # Generar reporte
            self.analyzer.export_to_pdf(self.generated_variants, self.current_config, output_path)
            
            QMessageBox.information(
                self,
                "Éxito",
                f"Reporte PDF generado exitosamente:\n\n{file_path}\n\n"
                f"El reporte incluye:\n"
                f"- Portada con información del análisis\n"
                f"- Resumen ejecutivo\n"
                f"- Gráficos de evolución de todas las métricas\n"
                f"- Tabla comparativa de variantes\n"
                f"- Estadísticas resumen por métrica"
            )
            
        except Exception as e:
            logger.error(f"Error generando reporte PDF: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error al generar el reporte PDF:\n\n{str(e)}"
            )

