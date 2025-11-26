"""
Módulo para actualización de plots en la GUI.
Separa la lógica de plotting de la GUI principal para mejorar mantenibilidad.
"""

import logging
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from typing import List, Optional, Dict, Any
from PyQt5.QtWidgets import QLabel, QApplication
from PyQt5.QtCore import Qt

from constants import BASE_COLORS, LINESTYLES, FLUTE_PARTS_ORDER
from gui_constants import (
    FIGURE_SIZE_MEDIUM, FIGURE_SIZE_LARGE,
    GRID_LINESTYLE, GRID_ALPHA, TIGHT_LAYOUT_PAD, TIGHT_LAYOUT_H_PAD,
    FONT_SIZE_SMALL, FONT_SIZE_NORMAL
)

logger = logging.getLogger(__name__)


class PlotUpdater:
    """
    Maneja la actualización de todos los plots en la GUI.
    Centraliza la lógica de copiar figuras matplotlib a Qt canvas.
    """
    
    def __init__(self, parent_gui):
        """
        Inicializa el PlotUpdater.
        
        Args:
            parent_gui: Referencia a la GUI principal (UnifiedFluteGUI_Qt)
        """
        self.gui = parent_gui
    
    def copy_figure_to_canvas(
        self,
        fig_src: plt.Figure,
        fig_dst: Figure,
        canvas_dst: FigureCanvas
    ) -> None:
        """
        Copia una figura de matplotlib a un FigureCanvas de Qt.
        
        Args:
            fig_src: Figura fuente de matplotlib
            fig_dst: Figura destino (FigureCanvas de Qt)
            canvas_dst: Canvas destino donde se dibujará
        """
        fig_dst.clear()
        for i, ax_src in enumerate(fig_src.axes):
            ax_dst = fig_dst.add_subplot(1, 1, i+1)
            
            # Copiar líneas
            for line in ax_src.lines:
                ax_dst.plot(
                    line.get_xdata(), line.get_ydata(),
                    color=line.get_color(),
                    linestyle=line.get_linestyle(),
                    marker=line.get_marker(),
                    markersize=line.get_markersize(),
                    label=line.get_label(),
                    linewidth=line.get_linewidth(),
                    alpha=line.get_alpha()
                )
            
            # Copiar configuración de ejes
            ax_dst.set_xlabel(ax_src.get_xlabel())
            ax_dst.set_ylabel(ax_src.get_ylabel())
            ax_dst.set_title(ax_src.get_title())
            
            # Copiar ticks
            ax_dst.set_xticks(ax_src.get_xticks())
            ax_dst.set_xticklabels(ax_src.get_xticklabels(), rotation=45, ha='right')
            ax_dst.set_xlim(ax_src.get_xlim())
            ax_dst.set_ylim(ax_src.get_ylim())
            
            # Grid
            ax_dst.grid(True, linestyle=GRID_LINESTYLE, alpha=GRID_ALPHA)
            
            # Legend
            handles, labels = ax_dst.get_legend_handles_labels()
            if handles and labels and any(not label.startswith('_') for label in labels):
                ax_dst.legend()
        
        fig_dst.tight_layout()
        canvas_dst.draw()
    
    def update_inharmonicity_plot(self) -> None:
        """Actualiza el gráfico de inharmonicidad."""
        if not self.gui.analyzer:
            return
        
        fig_inharm = self.gui.analyzer.plot_inharmonicity()
        self.gui.inharm_figure.clear()
        
        for i, ax_src in enumerate(fig_inharm.axes):
            ax_dst = self.gui.inharm_figure.add_subplot(1, 1, i+1)
            
            # Copiar líneas
            for line in ax_src.lines:
                ax_dst.plot(
                    line.get_xdata(), line.get_ydata(),
                    color=line.get_color(), label=line.get_label()
                )
            
            # Copiar configuración
            ax_dst.set_xlabel(ax_src.get_xlabel())
            ax_dst.set_ylabel(ax_src.get_ylabel())
            ax_dst.set_title(ax_src.get_title())
            
            # Copiar configuración de ejes X (notas)
            ax_dst.set_xticks(ax_src.get_xticks())
            ax_dst.set_xticklabels(ax_src.get_xticklabels(), rotation=45, ha='right')
            ax_dst.set_xlim(ax_src.get_xlim())
            ax_dst.set_ylim(ax_src.get_ylim())
            
            # Legend y grid
            handles, labels = ax_dst.get_legend_handles_labels()
            if handles and labels and any(not label.startswith('_') for label in labels):
                ax_dst.legend()
            ax_dst.grid(True)
        
        plt.close(fig_inharm)
        self.gui.inharm_canvas.draw()
    
    def update_resonance_plot(self) -> None:
        """Actualiza el gráfico de frecuencias de resonancia."""
        if not self.gui.analyzer:
            return
        
        reference_pitch = self.gui.la_frequency_spinbox.value()
        fig_resonance = self.gui.analyzer.plot_resonance_frequencies(
            reference_pitch=reference_pitch
        )
        self.copy_figure_to_canvas(
            fig_resonance,
            self.gui.resonance_figure,
            self.gui.resonance_canvas
        )
        plt.close(fig_resonance)
    
    def update_moc_plot(self) -> None:
        """Actualiza el gráfico de MOC."""
        if not self.gui.analyzer:
            return
        
        fig_moc = self.gui.analyzer.plot_moc()
        self._copy_analysis_plot_with_validation(
            fig_moc,
            self.gui.moc_figure,
            self.gui.moc_canvas,
            "MOC"
        )
        plt.close(fig_moc)
    
    def update_bi_espe_plot(self) -> None:
        """Actualiza el gráfico de B_I y ESPE."""
        if not self.gui.analyzer:
            return
        
        fig_bi = self.gui.analyzer.plot_bi_espe()
        self._copy_analysis_plot_with_validation(
            fig_bi,
            self.gui.bi_figure,
            self.gui.bi_canvas,
            "B_I_ESPE"
        )
        plt.close(fig_bi)
    
    def update_peak_heights_plot(self) -> None:
        """Actualiza el gráfico de altura de picos."""
        if not self.gui.analyzer:
            return
        
        fig_peak = self.gui.analyzer.plot_peak_heights()
        self.copy_figure_to_canvas(
            fig_peak,
            self.gui.peak_figure,
            self.gui.peak_canvas
        )
        plt.close(fig_peak)
    
    def update_q_factor_plot(self) -> None:
        """Actualiza el gráfico de Q-factor."""
        if not self.gui.analyzer:
            return
        
        fig_qfactor = self.gui.analyzer.plot_q_factor()
        self.copy_figure_to_canvas(
            fig_qfactor,
            self.gui.qfactor_figure,
            self.gui.qfactor_canvas
        )
        plt.close(fig_qfactor)
    
    def update_tonal_characteristics_plots(self) -> None:
        """Actualiza los gráficos de características tonales (ratios + fase)."""
        if not self.gui.analyzer:
            return
        
        self.gui.tonal_figure.clear()
        
        # Subplot 1: Ratios de armónicos
        ax1 = self.gui.tonal_figure.add_subplot(2, 1, 1)
        fig_ratios = self.gui.analyzer.plot_harmonic_ratios(ax=ax1)
        
        # Subplot 2: Coherencia de fase
        ax2 = self.gui.tonal_figure.add_subplot(2, 1, 2)
        fig_phase = self.gui.analyzer.plot_phase_coherence(ax=ax2)
        
        self.gui.tonal_figure.tight_layout()
        self.gui.tonal_canvas.draw()
        
        plt.close(fig_ratios)
        plt.close(fig_phase)
    
    def update_stability_plots(self) -> None:
        """Actualiza los gráficos de estabilidad (pitch + cut-off)."""
        if not self.gui.analyzer:
            return
        
        self.gui.stability_figure.clear()
        
        # Subplot 1: Estabilidad de pitch
        ax1 = self.gui.stability_figure.add_subplot(2, 1, 1)
        fig_pitch = self.gui.analyzer.plot_pitch_stability(ax=ax1)
        
        # Subplot 2: Frecuencia de corte
        ax2 = self.gui.stability_figure.add_subplot(2, 1, 2)
        fig_cutoff = self.gui.analyzer.plot_cutoff_frequency(ax=ax2)
        
        self.gui.stability_figure.tight_layout()
        self.gui.stability_canvas.draw()
        
        plt.close(fig_pitch)
        plt.close(fig_cutoff)
    
    def update_summary_dashboard(self) -> None:
        """Actualiza el dashboard de resumen con métricas y gráfico radar."""
        if not self.gui.analyzer:
            return
        
        try:
            # Calcular métricas
            inharmonicity_data = self.gui.analyzer.calculate_inharmonicity()
            moc_data = self.gui.analyzer.calculate_moc()
            bi_espe_data = self.gui.analyzer.calculate_bi_espe()
            
            # Actualizar tabla de métricas
            self._update_metrics_table(inharmonicity_data, moc_data, bi_espe_data)
            
            # Actualizar gráfico radar
            self._update_radar_chart(inharmonicity_data, moc_data, bi_espe_data)
            
        except Exception as e:
            logger.error(f"Error actualizando dashboard de resumen: {e}", exc_info=True)
    
    def _update_metrics_table(
        self,
        inharmonicity_data: Dict,
        moc_data: Dict,
        bi_espe_data: Dict
    ) -> None:
        """
        Actualiza la tabla de métricas en el resumen.
        
        Args:
            inharmonicity_data: Datos de inharmonicidad
            moc_data: Datos de MOC
            bi_espe_data: Datos de B_I y ESPE
        """
        # Limpiar widgets anteriores
        for widget in self.gui.summary_labels.values():
            widget.deleteLater()
        self.gui.summary_labels.clear()
        
        # Agregar encabezados
        headers = ["Flauta", "Inharmonicidad", "MOC", "B_I", "ESPE"]
        for col, header in enumerate(headers):
            header_label = QLabel(f"<b>{header}</b>")
            header_label.setStyleSheet(
                "font-weight: bold; background-color: #e0e0e0; padding: 5px;"
            )
            self.gui.metrics_layout.addWidget(header_label, 0, col)
            self.gui.summary_labels[f"header_{col}"] = header_label
        
        # Agregar datos de cada flauta
        # Obtener todas las flautas cargadas (no solo las que tienen datos de inharmonicidad)
        all_flute_names = set()
        if self.gui.flute_data_list:
            all_flute_names = {fd.flute_model for fd in self.gui.flute_data_list}
        # También incluir las que están en los datos calculados
        all_flute_names.update(inharmonicity_data.keys())
        all_flute_names.update(moc_data.keys())
        all_flute_names.update(bi_espe_data.keys())
        
        row = 1
        for flute_name in sorted(all_flute_names):
            # Calcular promedios (usar .get() para evitar KeyError)
            inharm_vals = [v for v in inharmonicity_data.get(flute_name, {}).values() if not np.isnan(v)]
            moc_vals = [v for v in moc_data.get(flute_name, {}).values() if not np.isnan(v)]
            bi_vals = [v[0] for v in bi_espe_data.get(flute_name, {}).values() if not np.isnan(v[0])]
            espe_vals = [v[1] for v in bi_espe_data.get(flute_name, {}).values() if not np.isnan(v[1])]
            
            avg_inharm = np.mean(inharm_vals) if inharm_vals else np.nan
            avg_moc = np.mean(moc_vals) if moc_vals else np.nan
            avg_bi = np.mean(bi_vals) if bi_vals else np.nan
            avg_espe = np.mean(espe_vals) if espe_vals else np.nan
            
            # Crear labels
            name_label = QLabel(f"<b>{flute_name}</b>")
            name_label.setStyleSheet("padding: 5px;")
            self.gui.metrics_layout.addWidget(name_label, row, 0)
            self.gui.summary_labels[f"{flute_name}_name"] = name_label
            
            inharm_text = f"{avg_inharm:.1f} cents" if not np.isnan(avg_inharm) else "N/A"
            inharm_label = QLabel(inharm_text)
            inharm_label.setStyleSheet("padding: 5px;")
            self.gui.metrics_layout.addWidget(inharm_label, row, 1)
            self.gui.summary_labels[f"{flute_name}_inharm"] = inharm_label
            
            moc_text = f"{avg_moc:.3f}" if not np.isnan(avg_moc) else "N/A"
            moc_label = QLabel(moc_text)
            moc_label.setStyleSheet("padding: 5px;")
            self.gui.metrics_layout.addWidget(moc_label, row, 2)
            self.gui.summary_labels[f"{flute_name}_moc"] = moc_label
            
            bi_text = f"{avg_bi:.1f} cents" if not np.isnan(avg_bi) else "N/A"
            bi_label = QLabel(bi_text)
            bi_label.setStyleSheet("padding: 5px;")
            self.gui.metrics_layout.addWidget(bi_label, row, 3)
            self.gui.summary_labels[f"{flute_name}_bi"] = bi_label
            
            espe_text = f"{avg_espe:.1f} cents" if not np.isnan(avg_espe) else "N/A"
            espe_label = QLabel(espe_text)
            espe_label.setStyleSheet("padding: 5px;")
            self.gui.metrics_layout.addWidget(espe_label, row, 4)
            self.gui.summary_labels[f"{flute_name}_espe"] = espe_label
            
            row += 1
    
    def _update_radar_chart(
        self,
        inharmonicity_data: Dict,
        moc_data: Dict,
        bi_espe_data: Dict
    ) -> None:
        """
        Actualiza el gráfico radar comparativo.
        
        Args:
            inharmonicity_data: Datos de inharmonicidad
            moc_data: Datos de MOC
            bi_espe_data: Datos de B_I y ESPE
        """
        self.gui.summary_figure.clear()
        ax = self.gui.summary_figure.add_subplot(111, projection='polar')
        
        # Categorías para el gráfico radar
        categories = [
            'Inharmonicidad\n(invertida)', 'MOC',
            'B_I\n(abs)', 'ESPE\n(abs)', 'Q-Factor\n(promedio)'
        ]
        num_vars = len(categories)
        
        # Ángulos para el gráfico radar
        angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
        angles += angles[:1]
        
        # Plotear para cada flauta
        # Usar el mismo conjunto de flautas que en la tabla
        all_flute_names = set()
        if self.gui.flute_data_list:
            all_flute_names = {fd.flute_model for fd in self.gui.flute_data_list}
        all_flute_names.update(inharmonicity_data.keys())
        all_flute_names.update(moc_data.keys())
        all_flute_names.update(bi_espe_data.keys())
        
        # Primero, recopilar todos los valores para calcular rangos de normalización
        all_inharm_avgs = []
        all_moc_avgs = []
        all_bi_avgs = []
        all_espe_avgs = []
        all_q_avgs = []
        
        # Calcular Q-factor para cada flauta
        q_factor_data = {}
        if self.gui.analyzer:
            for analysis_dict, flute_name in self.gui.analyzer.acoustic_analysis_list:
                q_factors = []
                for note in self.gui.analyzer.ordered_notes:
                    analysis_obj = analysis_dict.get(note)
                    if analysis_obj is None:
                        continue
                    try:
                        frequencies = analysis_obj.frequencies()
                        impedance = analysis_obj.impedance()
                        admittance = np.abs(1.0 / (impedance + 1e-10))
                        
                        antires = list(analysis_obj.antiresonance_frequencies())
                        if len(antires) >= 1 and antires[0] > 0:
                            target_freq = antires[0]
                            idx_peak = np.argmin(np.abs(frequencies - target_freq))
                            
                            # Buscar máximo local
                            window = 30
                            idx_start = max(0, idx_peak - window)
                            idx_end = min(len(admittance), idx_peak + window)
                            idx_max_local = idx_start + np.argmax(admittance[idx_start:idx_end])
                            peak_value = admittance[idx_max_local]
                            
                            # Calcular ancho a -3dB
                            threshold = peak_value / np.sqrt(2)
                            
                            left_idx = idx_max_local
                            while left_idx > 0 and admittance[left_idx] > threshold:
                                left_idx -= 1
                            
                            right_idx = idx_max_local
                            while right_idx < len(admittance) - 1 and admittance[right_idx] > threshold:
                                right_idx += 1
                            
                            if left_idx < right_idx:
                                bandwidth = frequencies[right_idx] - frequencies[left_idx]
                                if bandwidth > 0:
                                    q_factor = target_freq / bandwidth
                                    q_factors.append(q_factor)
                    except Exception:
                        continue
                
                if q_factors:
                    q_factor_data[flute_name] = np.mean(q_factors)
        
        # Recopilar todos los valores para normalización
        for flute_name in sorted(all_flute_names):
            inharm_vals = [abs(v) for v in inharmonicity_data.get(flute_name, {}).values() if not np.isnan(v)]
            moc_vals = [v for v in moc_data.get(flute_name, {}).values() if not np.isnan(v)]
            bi_vals = [abs(v[0]) for v in bi_espe_data.get(flute_name, {}).values() if not np.isnan(v[0])]
            espe_vals = [abs(v[1]) for v in bi_espe_data.get(flute_name, {}).values() if not np.isnan(v[1])]
            q_vals = [q_factor_data.get(flute_name, np.nan)]
            
            if inharm_vals:
                all_inharm_avgs.append(np.mean(inharm_vals))
            if moc_vals:
                all_moc_avgs.append(np.mean(moc_vals))
            if bi_vals:
                all_bi_avgs.append(np.mean(bi_vals))
            if espe_vals:
                all_espe_avgs.append(np.mean(espe_vals))
            if q_vals and not np.isnan(q_vals[0]):
                all_q_avgs.append(q_vals[0])
        
        # Calcular rangos para normalización min-max
        def normalize_to_0_100(value, min_val, max_val):
            if max_val == min_val or np.isnan(value):
                return 50.0
            return ((value - min_val) / (max_val - min_val)) * 100.0
        
        # Rangos para normalización (invertir donde menor es mejor)
        inharm_min, inharm_max = (min(all_inharm_avgs), max(all_inharm_avgs)) if all_inharm_avgs else (0, 100)
        moc_min, moc_max = (min(all_moc_avgs), max(all_moc_avgs)) if all_moc_avgs else (0, 1)
        bi_min, bi_max = (min(all_bi_avgs), max(all_bi_avgs)) if all_bi_avgs else (0, 100)
        espe_min, espe_max = (min(all_espe_avgs), max(all_espe_avgs)) if all_espe_avgs else (0, 100)
        q_min, q_max = (min(all_q_avgs), max(all_q_avgs)) if all_q_avgs else (0, 100)
        
        # Plotear para cada flauta
        for idx, flute_name in enumerate(sorted(all_flute_names)):
            # Preparar valores (usar .get() para evitar KeyError)
            inharm_vals = [abs(v) for v in inharmonicity_data.get(flute_name, {}).values() if not np.isnan(v)]
            moc_vals = [v for v in moc_data.get(flute_name, {}).values() if not np.isnan(v)]
            bi_vals = [abs(v[0]) for v in bi_espe_data.get(flute_name, {}).values() if not np.isnan(v[0])]
            espe_vals = [abs(v[1]) for v in bi_espe_data.get(flute_name, {}).values() if not np.isnan(v[1])]
            q_val = q_factor_data.get(flute_name, np.nan)
            
            # Calcular promedios
            avg_inharm = np.mean(inharm_vals) if inharm_vals else np.nan
            avg_moc = np.mean(moc_vals) if moc_vals else np.nan
            avg_bi = np.mean(bi_vals) if bi_vals else np.nan
            avg_espe = np.mean(espe_vals) if espe_vals else np.nan
            avg_q = q_val if not np.isnan(q_val) else np.nan
            
            # Normalizar al rango 0-100 (invertir donde menor es mejor)
            # Inharmonicidad: menor es mejor, invertir
            norm_inharm = 100.0 - normalize_to_0_100(avg_inharm, inharm_min, inharm_max) if not np.isnan(avg_inharm) else 50.0
            # MOC: mayor es mejor, normalizar directamente
            norm_moc = normalize_to_0_100(avg_moc, moc_min, moc_max) * 100.0 if not np.isnan(avg_moc) else 50.0
            # B_I: menor es mejor, invertir
            norm_bi = 100.0 - normalize_to_0_100(avg_bi, bi_min, bi_max) if not np.isnan(avg_bi) else 50.0
            # ESPE: menor es mejor, invertir
            norm_espe = 100.0 - normalize_to_0_100(avg_espe, espe_min, espe_max) if not np.isnan(avg_espe) else 50.0
            # Q-Factor: mayor es mejor, normalizar directamente
            norm_q = normalize_to_0_100(avg_q, q_min, q_max) if not np.isnan(avg_q) else 50.0
            
            # Asegurar que todos los valores estén en el rango 0-100
            values = [
                max(0, min(100, norm_inharm)),
                max(0, min(100, norm_moc)),
                max(0, min(100, norm_bi)),
                max(0, min(100, norm_espe)),
                max(0, min(100, norm_q))
            ]
            values += values[:1]
            
            color = BASE_COLORS[idx % len(BASE_COLORS)]
            ax.plot(angles, values, 'o-', linewidth=2, label=flute_name, color=color)
            ax.fill(angles, values, alpha=0.15, color=color)
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, size=10)
        ax.set_ylim(0, 100)
        ax.set_title("Comparación Multi-Métrica", size=14, weight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        ax.grid(True)
        
        self.gui.summary_figure.tight_layout()
        self.gui.summary_canvas.draw()
    
    def _copy_analysis_plot_with_validation(
        self,
        fig_src: plt.Figure,
        fig_dst: Figure,
        canvas_dst: FigureCanvas,
        plot_name: str
    ) -> None:
        """
        Copia plot de análisis con validación de datos y manejo de errores.
        
        Args:
            fig_src: Figura fuente
            fig_dst: Figura destino
            canvas_dst: Canvas destino
            plot_name: Nombre del plot para mensajes de error
        """
        fig_dst.clear()
        logger.debug(f"{plot_name}: figura tiene {len(fig_src.axes)} ejes")
        
        for i, ax_src in enumerate(fig_src.axes):
            ax_dst = fig_dst.add_subplot(1, 1, i+1)
            
            logger.debug(f"{plot_name}: eje {i} tiene {len(ax_src.lines)} líneas")
            
            has_valid_data = False
            
            # Copiar todas las líneas con validación
            for line_idx, line in enumerate(ax_src.lines):
                xdata = np.array(line.get_xdata()) if not isinstance(line.get_xdata(), np.ndarray) else line.get_xdata()
                ydata = np.array(line.get_ydata()) if not isinstance(line.get_ydata(), np.ndarray) else line.get_ydata()
                
                # Filtrar NaN
                valid_mask = ~(np.isnan(xdata) | np.isnan(ydata))
                if np.any(valid_mask):
                    has_valid_data = True
                    xdata_valid = xdata[valid_mask]
                    ydata_valid = ydata[valid_mask]
                    
                    # Preparar parámetros
                    plot_kwargs = {
                        'color': line.get_color(),
                        'linestyle': line.get_linestyle(),
                        'marker': line.get_marker(),
                        'markersize': line.get_markersize(),
                        'alpha': line.get_alpha(),
                        'label': line.get_label(),
                        'linewidth': line.get_linewidth()
                    }
                    
                    # Agregar dashes solo si no es None
                    dashes = line.get_dashes()
                    if dashes is not None:
                        plot_kwargs['dashes'] = dashes
                    
                    ax_dst.plot(xdata_valid, ydata_valid, **plot_kwargs)
            
            # Si no hay datos válidos, mostrar mensaje
            if not has_valid_data:
                ax_dst.text(
                    0.5, 0.5,
                    f"No hay datos disponibles para {plot_name}.\n\n"
                    f"Los gráficos requieren 'finger_frequencies'\n"
                    "en los datos de la flauta.",
                    ha='center', va='center', transform=ax_dst.transAxes,
                    fontsize=12, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5)
                )
                ax_dst.set_title(f"{plot_name} - Sin Datos")
            
            # Copiar configuración de ejes
            ax_dst.set_xlabel(ax_src.get_xlabel())
            ax_dst.set_ylabel(ax_src.get_ylabel())
            ax_dst.set_title(ax_src.get_title())
            
            # Copiar ticks y labels
            try:
                ax_dst.set_xticks(ax_src.get_xticks())
                ticklabels_src = ax_src.xaxis.get_ticklabels()
                if ticklabels_src:
                    rotation = ticklabels_src[0].get_rotation()
                    ha = ticklabels_src[0].get_ha()
                    ax_dst.set_xticklabels(ax_src.get_xticklabels(), rotation=rotation, ha=ha)
                else:
                    ax_dst.set_xticklabels(ax_src.get_xticklabels())
            except Exception as e:
                logger.warning(f"Error copiando ticks del eje X en {plot_name}: {e}")
                ax_dst.set_xticks(ax_src.get_xticks())
                ax_dst.set_xticklabels(ax_src.get_xticklabels(), rotation=45, ha='right')
            
            # Copiar grid
            ax_dst.grid(True, linestyle=GRID_LINESTYLE, alpha=GRID_ALPHA)
            
            # Copiar límites de ejes
            try:
                ax_dst.set_xlim(ax_src.get_xlim())
                ax_dst.set_ylim(ax_src.get_ylim())
            except Exception as e:
                logger.warning(f"Error copiando límites de ejes en {plot_name}: {e}")
            
            # Copiar legend si existe
            try:
                if ax_src.legend_:
                    handles_src, labels_src = ax_src.get_legend_handles_labels()
                    if handles_src and labels_src and any(not label.startswith('_') for label in labels_src):
                        legend_loc = 'best'
                        if hasattr(ax_src.legend_, '_loc'):
                            legend_loc = ax_src.legend_._loc
                        legend_fontsize = FONT_SIZE_SMALL
                        if ax_src.legend_.get_texts():
                            legend_fontsize = ax_src.legend_.get_texts()[0].get_fontsize()
                        ax_dst.legend(handles_src, labels_src, loc=legend_loc, fontsize=legend_fontsize)
            except Exception as e:
                logger.warning(f"Error copiando legend en {plot_name}: {e}")
                handles, labels = ax_dst.get_legend_handles_labels()
                if handles and labels and any(not label.startswith('_') for label in labels):
                    ax_dst.legend()
        
        fig_dst.tight_layout()
        canvas_dst.draw()

