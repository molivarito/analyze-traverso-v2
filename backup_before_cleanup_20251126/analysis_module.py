"""
Módulo unificado de análisis acústico para flautas.

Encapsula y unifica los análisis existentes:
- Inharmonicidad (diferencias en cents)
- MOC (Modal Octave Compression)
- B_I y ESPE
- Visualizaciones mejoradas
- Exportación de resultados
- Integración con base de datos
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import matplotlib.pyplot as plt
import logging
from pathlib import Path
import json
import csv

from flute_operations import FluteOperations
from constants import BASE_COLORS, LINESTYLES

logger = logging.getLogger(__name__)


class FluteAnalyzer:
    """
    Analizador unificado de flautas que encapsula todos los análisis acústicos.
    """
    
    def __init__(self, flute_data_list: List[Any], flute_operations_list: Optional[List[FluteOperations]] = None):
        """
        Inicializa el analizador.
        
        Args:
            flute_data_list: Lista de instancias de FluteData o FluteDataDB.
            flute_operations_list: Lista de instancias de FluteOperations (opcional).
        """
        self.flute_data_list = flute_data_list
        self.flute_operations_list = flute_operations_list or [
            FluteOperations(fd) for fd in flute_data_list
        ]
        
        # Preparar datos para análisis
        self.acoustic_analysis_list: List[Tuple[Dict[str, Any], str]] = []
        self.finger_frequencies_map: Dict[str, Dict[str, float]] = {}
        self.ordered_notes: List[str] = []
        
        self._prepare_analysis_data()
    
    def _prepare_analysis_data(self) -> None:
        """Prepara los datos para análisis."""
        for flute_data in self.flute_data_list:
            flute_name = flute_data.flute_model
            self.acoustic_analysis_list.append((flute_data.acoustic_analysis, flute_name))
            
            if flute_data.finger_frequencies:
                self.finger_frequencies_map[flute_name] = flute_data.finger_frequencies
        
        # Determinar orden de notas
        all_notes = set()
        for analysis_dict, _ in self.acoustic_analysis_list:
            all_notes.update(analysis_dict.keys())
        
        # Orden canónico
        canonical_order = ["D", "D#", "E", "F", "Fs", "G", "G#", "A", "A#", "B", "C", "Cs"]
        self.ordered_notes = [n for n in canonical_order if n in all_notes]
        self.ordered_notes.extend(sorted(list(all_notes - set(self.ordered_notes))))
    
    def calculate_inharmonicity(self) -> Dict[str, Dict[str, float]]:
        """
        Calcula inharmonicidad (diferencias en cents) para todas las flautas.
        
        Returns:
            Diccionario {flute_name: {note: cents_difference}}.
        """
        results = {}
        
        for analysis_dict, flute_name in self.acoustic_analysis_list:
            flute_results = {}
            finger_freqs = self.finger_frequencies_map.get(flute_name, {})
            
            for note in self.ordered_notes:
                analysis_obj = analysis_dict.get(note)
                f_play = finger_freqs.get(note)
                
                if analysis_obj is None or f_play is None or f_play <= 0:
                    flute_results[note] = np.nan
                    continue
                
                try:
                    antires = list(analysis_obj.antiresonance_frequencies())
                    if len(antires) > 0:
                        f0 = antires[0]
                        if f0 > 0:
                            cents_diff = 1200.0 * np.log2(f_play / f0)
                            flute_results[note] = cents_diff
                        else:
                            flute_results[note] = np.nan
                    else:
                        flute_results[note] = np.nan
                except Exception as e:
                    logger.warning(f"Error calculando inharmonicidad para {flute_name}, nota {note}: {e}")
                    flute_results[note] = np.nan
            
            results[flute_name] = flute_results
        
        return results
    
    def calculate_moc(self) -> Dict[str, Dict[str, float]]:
        """
        Calcula MOC (Modal Octave Compression) para todas las flautas.
        
        Returns:
            Diccionario {flute_name: {note: moc_value}}.
        """
        results = {}
        
        for analysis_dict, flute_name in self.acoustic_analysis_list:
            flute_results = {}
            finger_freqs = self.finger_frequencies_map.get(flute_name, {})
            
            for note in self.ordered_notes:
                analysis_obj = analysis_dict.get(note)
                f_play_I = finger_freqs.get(note)
                
                if analysis_obj is None or f_play_I is None or f_play_I <= 0:
                    flute_results[note] = np.nan
                    continue
                
                try:
                    antires = list(analysis_obj.antiresonance_frequencies())
                    if len(antires) >= 2:
                        f0, f1 = antires[0], antires[1]
                        f_play_II = 2.0 * f_play_I
                        
                        if f0 > 0 and f1 > 0 and f_play_II > 0:
                            # MOC = (f1 - f0) / (f_play_II - f_play_I)
                            moc = (f1 - f0) / (f_play_II - f_play_I)
                            flute_results[note] = moc
                        else:
                            flute_results[note] = np.nan
                    else:
                        flute_results[note] = np.nan
                except Exception as e:
                    logger.warning(f"Error calculando MOC para {flute_name}, nota {note}: {e}")
                    flute_results[note] = np.nan
            
            results[flute_name] = flute_results
        
        return results
    
    def calculate_bi_espe(self) -> Dict[str, Dict[str, Tuple[float, float]]]:
        """
        Calcula B_I y ESPE para todas las flautas.
        
        Returns:
            Diccionario {flute_name: {note: (bi_value, espe_value)}}.
        """
        from constants import get_speed_of_sound
        
        results = {}
        speed_of_sound_ref = get_speed_of_sound(20.0)
        
        for analysis_dict, flute_name in self.acoustic_analysis_list:
            flute_results = {}
            finger_freqs = self.finger_frequencies_map.get(flute_name, {})
            
            for note in self.ordered_notes:
                analysis_obj = analysis_dict.get(note)
                f_play_I = finger_freqs.get(note)
                
                if analysis_obj is None or f_play_I is None or f_play_I <= 0:
                    flute_results[note] = (np.nan, np.nan)
                    continue
                
                try:
                    antires = list(analysis_obj.antiresonance_frequencies())
                    if len(antires) >= 2:
                        f0, f1 = antires[0], antires[1]
                        f_play_II = 2.0 * f_play_I
                        
                        bi = np.nan
                        espe = np.nan
                        
                        if f0 > 0:
                            bi = 1200.0 * np.log2(f_play_I / f0)
                        
                        delta_l_I = (speed_of_sound_ref / 2.0) * ((1.0 / f_play_I) - (1.0 / f0)) if f0 > 0 else 0.0
                        delta_l_II = speed_of_sound_ref * ((1.0 / f_play_II) - (1.0 / f1)) if f1 > 0 and f_play_II > 0 else 0.0
                        delta_delta_l = delta_l_II - delta_l_I
                        L_eff_I = (speed_of_sound_ref / (2.0 * f_play_I))
                        
                        if L_eff_I > 0 and (L_eff_I + delta_delta_l) > 1e-9:
                            espe = 1200.0 * np.log2(L_eff_I / (L_eff_I + delta_delta_l))
                        
                        flute_results[note] = (bi, espe)
                    else:
                        flute_results[note] = (np.nan, np.nan)
                except Exception as e:
                    logger.warning(f"Error calculando B_I/ESPE para {flute_name}, nota {note}: {e}")
                    flute_results[note] = (np.nan, np.nan)
            
            results[flute_name] = flute_results
        
        return results
    
    def plot_inharmonicity(self, ax: Optional[plt.Axes] = None) -> plt.Figure:
        """
        Genera gráfico de inharmonicidad.
        
        Args:
            ax: Eje de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        return FluteOperations.plot_summary_cents_differences(
            self.acoustic_analysis_list,
            self.ordered_notes,
            ax=ax
        )
    
    def plot_moc(self, ax: Optional[plt.Axes] = None) -> plt.Figure:
        """
        Genera gráfico de MOC.
        
        Args:
            ax: Eje de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        return FluteOperations.plot_moc_summary(
            self.acoustic_analysis_list,
            self.finger_frequencies_map,
            self.ordered_notes,
            ax=ax
        )
    
    def plot_bi_espe(self, ax: Optional[plt.Axes] = None) -> plt.Figure:
        """
        Genera gráfico de B_I y ESPE.
        
        Args:
            ax: Eje de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        return FluteOperations.plot_bi_espe_summary(
            self.acoustic_analysis_list,
            self.finger_frequencies_map,
            self.ordered_notes,
            ax=ax
        )
    
    def plot_resonance_frequencies(self, reference_pitch: float = 415.0, ax: Optional[plt.Axes] = None) -> plt.Figure:
        """
        Genera gráfico de frecuencias de resonancia vs temperamento igual.
        
        Args:
            reference_pitch: Frecuencia de referencia (La, por defecto 415 Hz).
            ax: Eje de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        return FluteOperations.plot_resonance_frequencies_vs_equal_temperament(
            self.acoustic_analysis_list,
            self.ordered_notes,
            reference_pitch=reference_pitch,
            ax=ax
        )
    
    def plot_peak_heights(self, ax: Optional[plt.Axes] = None) -> plt.Figure:
        """
        Genera gráfico de altura de picos de admitancia.
        
        Args:
            ax: Eje de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        return FluteOperations.plot_peak_admittance_heights(
            self.acoustic_analysis_list,
            self.ordered_notes,
            ax=ax
        )
    
    def plot_q_factor(self, ax: Optional[plt.Axes] = None) -> plt.Figure:
        """
        Genera gráfico de Q-factor.
        
        Args:
            ax: Eje de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        return FluteOperations.plot_q_factor(
            self.acoustic_analysis_list,
            self.ordered_notes,
            ax=ax
        )
    
    def plot_harmonic_ratios(self, ax: Optional[plt.Axes] = None) -> plt.Figure:
        """
        Genera gráfico de ratio armónicos pares/impares.
        
        Args:
            ax: Eje de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        return FluteOperations.plot_harmonic_ratios(
            self.acoustic_analysis_list,
            self.ordered_notes,
            ax=ax
        )
    
    def plot_phase_coherence(self, ax: Optional[plt.Axes] = None) -> plt.Figure:
        """
        Genera gráfico de coherencia de fase.
        
        Args:
            ax: Eje de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        return FluteOperations.plot_phase_coherence(
            self.acoustic_analysis_list,
            self.ordered_notes,
            ax=ax
        )
    
    def plot_pitch_stability(self, ax: Optional[plt.Axes] = None) -> plt.Figure:
        """
        Genera gráfico de estabilidad de pitch.
        
        Args:
            ax: Eje de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        return FluteOperations.plot_pitch_stability(
            self.acoustic_analysis_list,
            self.ordered_notes,
            ax=ax
        )
    
    def plot_cutoff_frequency(self, threshold: float = 0.1, ax: Optional[plt.Axes] = None) -> plt.Figure:
        """
        Genera gráfico de frecuencia de corte.
        
        Args:
            threshold: Umbral para determinar cut-off (por defecto 0.1 = 10%).
            ax: Eje de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        return FluteOperations.plot_cutoff_frequency(
            self.acoustic_analysis_list,
            self.ordered_notes,
            threshold=threshold,
            ax=ax
        )
    
    def export_results_to_csv(self, output_path: str) -> None:
        """
        Exporta todos los resultados de análisis a CSV.
        
        Args:
            output_path: Ruta al archivo CSV de salida.
        """
        inharmonicity = self.calculate_inharmonicity()
        moc = self.calculate_moc()
        bi_espe = self.calculate_bi_espe()
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Encabezado
            writer.writerow(['Flauta', 'Nota', 'Inharmonicidad (cents)', 'MOC', 'B_I (cents)', 'ESPE (cents)'])
            
            # Datos
            for flute_name in self.ordered_notes:
                for note in self.ordered_notes:
                    inharm = inharmonicity.get(flute_name, {}).get(note, np.nan)
                    moc_val = moc.get(flute_name, {}).get(note, np.nan)
                    bi, espe = bi_espe.get(flute_name, {}).get(note, (np.nan, np.nan))
                    
                    writer.writerow([
                        flute_name,
                        note,
                        f"{inharm:.2f}" if not np.isnan(inharm) else "",
                        f"{moc_val:.4f}" if not np.isnan(moc_val) else "",
                        f"{bi:.2f}" if not np.isnan(bi) else "",
                        f"{espe:.2f}" if not np.isnan(espe) else ""
                    ])
        
        logger.info(f"Resultados de análisis exportados a CSV: {output_path}")
    
    def export_results_to_json(self, output_path: str) -> None:
        """
        Exporta todos los resultados de análisis a JSON.
        
        Args:
            output_path: Ruta al archivo JSON de salida.
        """
        results = {
            'inharmonicity': self.calculate_inharmonicity(),
            'moc': self.calculate_moc(),
            'bi_espe': {
                flute_name: {
                    note: {'bi': bi, 'espe': espe}
                    for note, (bi, espe) in note_data.items()
                }
                for flute_name, note_data in self.calculate_bi_espe().items()
            },
            'ordered_notes': self.ordered_notes,
            'flute_names': [name for _, name in self.acoustic_analysis_list]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Resultados de análisis exportados a JSON: {output_path}")
    
    def generate_summary_report(self, output_path: str) -> None:
        """
        Genera un reporte resumen con todos los análisis y gráficos.
        
        Args:
            output_path: Ruta al archivo PDF de salida.
        """
        from matplotlib.backends.backend_pdf import PdfPages
        
        with PdfPages(output_path) as pdf:
            # Página de título
            fig, ax = plt.subplots(figsize=(8.5, 11))
            ax.axis('off')
            title_text = f"Reporte de Análisis Acústico\n\n"
            for flute_data in self.flute_data_list:
                title_text += f"{flute_data.flute_model}\n"
            ax.text(0.5, 0.5, title_text, ha='center', va='center', fontsize=16, fontweight='bold')
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            
            # Gráfico de inharmonicidad
            fig = self.plot_inharmonicity()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            
            # Gráfico de MOC
            fig = self.plot_moc()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            
            # Gráfico de B_I y ESPE
            fig = self.plot_bi_espe()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
        
        logger.info(f"Reporte resumen generado: {output_path}")

