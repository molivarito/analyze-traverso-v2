"""
Módulo de modificación geométrica interactiva para flautas.

Permite modificar la geometría de flautas y comparar con la versión original,
incluyendo visualización 3D y análisis acústico comparativo.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import logging
import copy

from flute_data import FluteData
from flute_operations import FluteOperations
from flute_3d_visualizer import Flute3DModel, compare_flutes_3d
from analysis_module import FluteAnalyzer
from constants import FLUTE_PARTS_ORDER

logger = logging.getLogger(__name__)


class GeometryModifier:
    """
    Modificador de geometría con capacidades de comparación.
    """
    
    def __init__(self, original_flute_data):
        """
        Inicializa el modificador.
        
        Args:
            original_flute_data: Instancia de FluteData o FluteDataDB original.
        """
        self.original_flute_data = original_flute_data
        self.modified_flute_data: Optional[FluteData] = None
        self.modification_history: List[Dict[str, Any]] = []
    
    def modify_measurement(
        self,
        part_name: str,
        measurement_index: int,
        new_position: Optional[float] = None,
        new_diameter: Optional[float] = None
    ) -> bool:
        """
        Modifica una medición específica.
        
        Args:
            part_name: Nombre de la parte.
            measurement_index: Índice de la medición.
            new_position: Nueva posición (opcional).
            new_diameter: Nuevo diámetro (opcional).
        
        Returns:
            True si la modificación fue exitosa.
        """
        if not self.modified_flute_data:
            self._create_modified_copy()
        
        part_data = self.modified_flute_data.data.get(part_name, {})
        measurements = part_data.get("measurements", [])
        
        if measurement_index >= len(measurements):
            logger.warning(f"Índice de medición {measurement_index} fuera de rango para {part_name}")
            return False
        
        original_measurement = copy.deepcopy(measurements[measurement_index])
        
        if new_position is not None:
            measurements[measurement_index]['position'] = new_position
        if new_diameter is not None:
            measurements[measurement_index]['diameter'] = max(0.1, new_diameter)  # Mínimo 0.1mm
        
        # Registrar modificación
        self.modification_history.append({
            'type': 'measurement',
            'part_name': part_name,
            'measurement_index': measurement_index,
            'original': original_measurement,
            'modified': copy.deepcopy(measurements[measurement_index])
        })
        
        logger.debug(f"Medición {measurement_index} en {part_name} modificada")
        return True
    
    def modify_hole(
        self,
        part_name: str,
        hole_index: int,
        new_position: Optional[float] = None,
        new_diameter: Optional[float] = None,
        new_chimney: Optional[float] = None
    ) -> bool:
        """
        Modifica un agujero específico.
        
        Args:
            part_name: Nombre de la parte.
            hole_index: Índice del agujero.
            new_position: Nueva posición (opcional).
            new_diameter: Nuevo diámetro (opcional).
            new_chimney: Nueva chimenea (opcional).
        
        Returns:
            True si la modificación fue exitosa.
        """
        if not self.modified_flute_data:
            self._create_modified_copy()
        
        part_data = self.modified_flute_data.data.get(part_name, {})
        hole_positions = part_data.get("Holes position", [])
        hole_diameters = part_data.get("Holes diameter", [])
        hole_chimneys = part_data.get("Holes chimney", [])
        
        if hole_index >= len(hole_positions):
            logger.warning(f"Índice de agujero {hole_index} fuera de rango para {part_name}")
            return False
        
        original_hole = {
            'position': hole_positions[hole_index] if hole_index < len(hole_positions) else None,
            'diameter': hole_diameters[hole_index] if hole_index < len(hole_diameters) else None,
            'chimney': hole_chimneys[hole_index] if hole_index < len(hole_chimneys) else None
        }
        
        if new_position is not None and hole_index < len(hole_positions):
            hole_positions[hole_index] = new_position
        if new_diameter is not None and hole_index < len(hole_diameters):
            hole_diameters[hole_index] = max(0.1, new_diameter)
        if new_chimney is not None:
            if not hole_chimneys:
                hole_chimneys = [3.0] * len(hole_positions)
                part_data["Holes chimney"] = hole_chimneys
            if hole_index < len(hole_chimneys):
                hole_chimneys[hole_index] = max(0.1, new_chimney)
        
        # Registrar modificación
        self.modification_history.append({
            'type': 'hole',
            'part_name': part_name,
            'hole_index': hole_index,
            'original': original_hole,
            'modified': {
                'position': hole_positions[hole_index] if hole_index < len(hole_positions) else None,
                'diameter': hole_diameters[hole_index] if hole_index < len(hole_diameters) else None,
                'chimney': hole_chimneys[hole_index] if hole_index < len(hole_chimneys) else None
            }
        })
        
        logger.debug(f"Agujero {hole_index} en {part_name} modificado")
        return True
    
    def _create_modified_copy(self) -> None:
        """Crea una copia modificable de los datos de la flauta."""
        modified_data = {}
        for part_name in FLUTE_PARTS_ORDER:
            if part_name in self.original_flute_data.data:
                modified_data[part_name] = copy.deepcopy(self.original_flute_data.data[part_name])
        
        self.modified_flute_data = FluteData(
            source=modified_data,
            source_name=f"{self.original_flute_data.flute_model}_modified",
            skip_acoustic_analysis=False,
            temperature=self.original_flute_data.temperature if hasattr(self.original_flute_data, 'temperature') else 20.0,
            la_frequency=self.original_flute_data.la_frequency if hasattr(self.original_flute_data, 'la_frequency') else 415.0
        )
        logger.info(f"Copia modificable creada para {self.original_flute_data.flute_model}")
    
    def reset_modifications(self) -> None:
        """Resetea todas las modificaciones."""
        self.modified_flute_data = None
        self.modification_history = []
        logger.info("Modificaciones reseteadas")
    
    def get_comparison_summary(self) -> Dict[str, Any]:
        """
        Obtiene un resumen comparativo entre original y modificado.
        
        Returns:
            Diccionario con información comparativa.
        """
        if not self.modified_flute_data:
            return {'has_modifications': False}
        
        summary = {
            'has_modifications': True,
            'num_modifications': len(self.modification_history),
            'original_model': self.original_flute_data.flute_model,
            'modified_model': self.modified_flute_data.flute_model,
            'original_has_analysis': bool(self.original_flute_data.acoustic_analysis),
            'modified_has_analysis': bool(self.modified_flute_data.acoustic_analysis)
        }
        
        # Comparar longitudes totales
        orig_combined = self.original_flute_data.combined_measurements
        mod_combined = self.modified_flute_data.combined_measurements
        
        if orig_combined and mod_combined:
            orig_length = max(m.get('position', 0) for m in orig_combined) - min(m.get('position', 0) for m in orig_combined)
            mod_length = max(m.get('position', 0) for m in mod_combined) - min(m.get('position', 0) for m in mod_combined)
            summary['length_difference_mm'] = mod_length - orig_length
        
        return summary
    
    def compare_acoustic_analysis(self) -> Dict[str, Dict[str, float]]:
        """
        Compara análisis acústico entre original y modificado.
        
        Returns:
            Diccionario con diferencias por nota.
        """
        if not self.modified_flute_data or not self.modified_flute_data.acoustic_analysis:
            return {}
        
        comparison = {}
        
        for note in self.original_flute_data.acoustic_analysis.keys():
            orig_analysis = self.original_flute_data.acoustic_analysis.get(note)
            mod_analysis = self.modified_flute_data.acoustic_analysis.get(note)
            
            if not orig_analysis or not mod_analysis:
                continue
            
            try:
                orig_antires = list(orig_analysis.antiresonance_frequencies())
                mod_antires = list(mod_analysis.antiresonance_frequencies())
                
                comparison[note] = {
                    'first_antires_diff_hz': mod_antires[0] - orig_antires[0] if len(orig_antires) > 0 and len(mod_antires) > 0 else 0.0,
                    'num_antires_orig': len(orig_antires),
                    'num_antires_mod': len(mod_antires)
                }
            except Exception as e:
                logger.warning(f"Error comparando análisis para nota {note}: {e}")
        
        return comparison
    
    def visualize_3d_comparison(self, ax=None):
        """
        Visualiza comparación 3D entre original y modificado.
        
        Args:
            ax: Eje de matplotlib 3D (opcional).
        
        Returns:
            Eje de matplotlib.
        """
        if not self.modified_flute_data:
            logger.warning("No hay modificaciones para visualizar")
            return None
        
        original_model = Flute3DModel(self.original_flute_data)
        modified_model = Flute3DModel(self.modified_flute_data)
        
        return compare_flutes_3d([original_model, modified_model], ax=ax)
    
    def export_comparison_report(self, output_path: str) -> None:
        """
        Exporta un reporte comparativo.
        
        Args:
            output_path: Ruta al archivo de salida (PDF o JSON).
        """
        import json
        from pathlib import Path
        
        output_path = Path(output_path)
        
        if output_path.suffix == '.json':
            report = {
                'summary': self.get_comparison_summary(),
                'modification_history': self.modification_history,
                'acoustic_comparison': self.compare_acoustic_analysis()
            }
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Reporte comparativo exportado a JSON: {output_path}")
        else:
            # Generar PDF con matplotlib
            from matplotlib.backends.backend_pdf import PdfPages
            
            with PdfPages(str(output_path)) as pdf:
                # Página de resumen
                fig, ax = plt.subplots(figsize=(8.5, 11))
                ax.axis('off')
                
                summary = self.get_comparison_summary()
                text = f"Reporte Comparativo\n\n"
                text += f"Original: {summary.get('original_model', 'N/A')}\n"
                text += f"Modificado: {summary.get('modified_model', 'N/A')}\n"
                text += f"Número de modificaciones: {summary.get('num_modifications', 0)}\n"
                
                if 'length_difference_mm' in summary:
                    text += f"Diferencia de longitud: {summary['length_difference_mm']:.2f} mm\n"
                
                ax.text(0.5, 0.5, text, ha='center', va='center', fontsize=12)
                pdf.savefig(fig, bbox_inches='tight')
                plt.close(fig)
            
            logger.info(f"Reporte comparativo exportado a PDF: {output_path}")

