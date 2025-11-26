"""
Diálogo para configuración y ejecución de análisis de sensibilidad.
"""

import logging
from typing import List, Optional
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
        elif param == SensitivityParameter.PART_TAPER:
            self.min_value_spinbox.setValue(-50.0)
            self.max_value_spinbox.setValue(50.0)
            self.min_value_spinbox.setSuffix(f" {unit}")
            self.max_value_spinbox.setSuffix(f" {unit}")
        elif param == SensitivityParameter.STOPPER_POSITION:
            self.min_value_spinbox.setValue(-10.0)
            self.max_value_spinbox.setValue(10.0)
            self.min_value_spinbox.setSuffix(f" {unit}")
            self.max_value_spinbox.setSuffix(f" {unit}")
        elif param == SensitivityParameter.HOLE_DIAMETER:
            self.min_value_spinbox.setValue(-2.0)
            self.max_value_spinbox.setValue(2.0)
            self.min_value_spinbox.setSuffix(f" {unit}")
            self.max_value_spinbox.setSuffix(f" {unit}")
        elif param == SensitivityParameter.EMBOUCHURE_DIAMETER:
            self.min_value_spinbox.setValue(-2.0)
            self.max_value_spinbox.setValue(2.0)
            self.min_value_spinbox.setSuffix(f" {unit}")
            self.max_value_spinbox.setSuffix(f" {unit}")
        elif param == SensitivityParameter.HOLE_POSITION:
            self.min_value_spinbox.setValue(-10.0)
            self.max_value_spinbox.setValue(10.0)
            self.min_value_spinbox.setSuffix(f" {unit}")
            self.max_value_spinbox.setSuffix(f" {unit}")
        
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
        
        # Por ahora, solo mostrar valor placeholder
        # TODO: Extraer valor real del JSON
        self.current_value_label.setText(f"0.0 {unit} (base)")
    
    def _update_step_mode(self):
        """Actualiza el modo de configuración de pasos."""
        use_num_steps = self.num_steps_radio.isChecked()
        
        self.num_steps_spinbox.setEnabled(use_num_steps)
        self.step_size_spinbox.setEnabled(not use_num_steps)
        
        self._update_preview()
    
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
        
        # Limitar visualización
        unit = self.parameter_combo.currentData().get_unit()
        
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

