"""
Módulo de perturbación geométrica para flautas.

Permite aplicar variaciones sistemáticas a:
- Ángulo de agujeros de tono
- Chimenea (cork) de agujeros
- Tamaño de agujeros
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import logging
import copy

from constants import FLUTE_PARTS_ORDER, MM_TO_M_FACTOR, M_TO_MM_FACTOR

logger = logging.getLogger(__name__)


class GeometryPerturbator:
    """
    Aplica perturbaciones geométricas a flautas.
    """
    
    def __init__(self, flute_data):
        """
        Inicializa el perturbador.
        
        Args:
            flute_data: Instancia de FluteData o FluteDataDB.
        """
        self.original_flute_data = flute_data
        self.perturbed_flute_data: Optional[Any] = None
    
    def perturb_hole_angle(
        self,
        part_name: str,
        hole_index: int,
        angle_variation_degrees: float
    ) -> Dict[str, Any]:
        """
        Varía el ángulo de un agujero de tono.
        
        Args:
            part_name: Nombre de la parte.
            hole_index: Índice del agujero (0-based).
            angle_variation_degrees: Variación del ángulo en grados.
        
        Returns:
            Diccionario con los datos modificados de la parte.
        """
        part_data = copy.deepcopy(self.original_flute_data.data.get(part_name, {}))
        
        # Los agujeros pueden tener información de ángulo
        # Si no existe, se puede agregar
        hole_angles = part_data.get("Holes angle", [])
        
        if not hole_angles:
            # Inicializar con ángulos por defecto (90 grados = perpendicular)
            num_holes = len(part_data.get("Holes position", []))
            hole_angles = [90.0] * num_holes
        
        if hole_index < len(hole_angles):
            hole_angles[hole_index] += angle_variation_degrees
            part_data["Holes angle"] = hole_angles
            logger.debug(f"Ángulo del agujero {hole_index} en {part_name} variado en {angle_variation_degrees}°")
        else:
            logger.warning(f"Índice de agujero {hole_index} fuera de rango para {part_name}")
        
        return part_data
    
    def perturb_hole_chimney(
        self,
        part_name: str,
        hole_index: int,
        chimney_variation_mm: float
    ) -> Dict[str, Any]:
        """
        Varía la chimenea (altura) de un agujero.
        
        Args:
            part_name: Nombre de la parte.
            hole_index: Índice del agujero.
            chimney_variation_mm: Variación de la chimenea en mm.
        
        Returns:
            Diccionario con los datos modificados de la parte.
        """
        part_data = copy.deepcopy(self.original_flute_data.data.get(part_name, {}))
        
        # La chimenea puede estar en "Holes chimney" o "Holes chimney height"
        hole_chimneys = part_data.get("Holes chimney", [])
        if not hole_chimneys:
            hole_chimneys = part_data.get("Holes chimney height", [])
        
        if not hole_chimneys:
            # Inicializar con valores por defecto (3mm)
            num_holes = len(part_data.get("Holes position", []))
            hole_chimneys = [3.0] * num_holes
        
        if hole_index < len(hole_chimneys):
            new_chimney = max(0.1, hole_chimneys[hole_index] + chimney_variation_mm)  # Mínimo 0.1mm
            hole_chimneys[hole_index] = new_chimney
            part_data["Holes chimney"] = hole_chimneys
            logger.debug(f"Chimenea del agujero {hole_index} en {part_name} variada en {chimney_variation_mm}mm")
        else:
            logger.warning(f"Índice de agujero {hole_index} fuera de rango para {part_name}")
        
        return part_data
    
    def perturb_hole_size(
        self,
        part_name: str,
        hole_index: int,
        size_variation_mm: float,
        variation_type: str = 'absolute'
    ) -> Dict[str, Any]:
        """
        Varía el tamaño (diámetro) de un agujero.
        
        Args:
            part_name: Nombre de la parte.
            hole_index: Índice del agujero.
            size_variation_mm: Variación del tamaño en mm.
            variation_type: Tipo de variación ('absolute' o 'relative').
        
        Returns:
            Diccionario con los datos modificados de la parte.
        """
        part_data = copy.deepcopy(self.original_flute_data.data.get(part_name, {}))
        
        hole_diameters = part_data.get("Holes diameter", [])
        
        if not hole_diameters or hole_index >= len(hole_diameters):
            logger.warning(f"Índice de agujero {hole_index} fuera de rango para {part_name}")
            return part_data
        
        original_diameter = hole_diameters[hole_index]
        
        if variation_type == 'absolute':
            new_diameter = max(0.1, original_diameter + size_variation_mm)  # Mínimo 0.1mm
        else:  # relative
            new_diameter = max(0.1, original_diameter * (1.0 + size_variation_mm / 100.0))
        
        hole_diameters[hole_index] = new_diameter
        part_data["Holes diameter"] = hole_diameters
        logger.debug(f"Diámetro del agujero {hole_index} en {part_name} variado: {original_diameter:.2f}mm -> {new_diameter:.2f}mm")
        
        return part_data
    
    def apply_multiple_perturbations(
        self,
        perturbations: List[Dict[str, Any]]
    ) -> Any:
        """
        Aplica múltiples perturbaciones a la vez.
        
        Args:
            perturbations: Lista de diccionarios con especificaciones de perturbaciones.
                Cada diccionario debe tener:
                - 'type': 'angle', 'chimney', o 'size'
                - 'part_name': nombre de la parte
                - 'hole_index': índice del agujero
                - 'variation': valor de la variación
                - 'variation_type': (opcional, solo para 'size') 'absolute' o 'relative'
        
        Returns:
            Instancia de FluteData con las perturbaciones aplicadas.
        """
        # Crear copia profunda de los datos originales
        perturbed_data = {}
        for part_name in FLUTE_PARTS_ORDER:
            if part_name in self.original_flute_data.data:
                perturbed_data[part_name] = copy.deepcopy(self.original_flute_data.data[part_name])
        
        # Aplicar cada perturbación
        for pert in perturbations:
            pert_type = pert.get('type')
            part_name = pert.get('part_name')
            hole_index = pert.get('hole_index')
            variation = pert.get('variation')
            
            if part_name not in perturbed_data:
                logger.warning(f"Parte {part_name} no encontrada para perturbación")
                continue
            
            if pert_type == 'angle':
                modified_part = self.perturb_hole_angle(part_name, hole_index, variation)
                perturbed_data[part_name] = modified_part
            elif pert_type == 'chimney':
                modified_part = self.perturb_hole_chimney(part_name, hole_index, variation)
                perturbed_data[part_name] = modified_part
            elif pert_type == 'size':
                variation_type = pert.get('variation_type', 'absolute')
                modified_part = self.perturb_hole_size(part_name, hole_index, variation, variation_type)
                perturbed_data[part_name] = modified_part
            else:
                logger.warning(f"Tipo de perturbación desconocido: {pert_type}")
        
        # Crear nueva instancia de FluteData con datos perturbados
        from flute_data import FluteData
        try:
            self.perturbed_flute_data = FluteData(
                source=perturbed_data,
                source_name=f"{self.original_flute_data.flute_model}_perturbed",
                skip_acoustic_analysis=False,
                temperature=self.original_flute_data.temperature if hasattr(self.original_flute_data, 'temperature') else 20.0,
                la_frequency=self.original_flute_data.la_frequency if hasattr(self.original_flute_data, 'la_frequency') else 415.0
            )
            logger.info(f"Perturbaciones aplicadas a {self.original_flute_data.flute_model}")
            return self.perturbed_flute_data
        except Exception as e:
            logger.error(f"Error creando FluteData perturbado: {e}", exc_info=True)
            return None
    
    def batch_perturbation_analysis(
        self,
        perturbation_ranges: Dict[str, Tuple[float, float, int]],
        perturbation_type: str = 'size'
    ) -> List[Dict[str, Any]]:
        """
        Realiza análisis batch de perturbaciones sistemáticas.
        
        Args:
            perturbation_ranges: Diccionario {hole_key: (min, max, steps)}
                donde hole_key es una tupla (part_name, hole_index).
            perturbation_type: Tipo de perturbación ('angle', 'chimney', 'size').
        
        Returns:
            Lista de diccionarios con resultados de cada perturbación.
        """
        results = []
        
        for hole_key, (min_val, max_val, steps) in perturbation_ranges.items():
            part_name, hole_index = hole_key
            values = np.linspace(min_val, max_val, steps)
            
            for val in values:
                pert = [{
                    'type': perturbation_type,
                    'part_name': part_name,
                    'hole_index': hole_index,
                    'variation': val
                }]
                
                perturbed = self.apply_multiple_perturbations(pert)
                
                if perturbed and perturbed.acoustic_analysis:
                    # Calcular métricas de interés
                    # Por ejemplo, inharmonicidad promedio
                    analysis_results = {}
                    for note, analysis_obj in perturbed.acoustic_analysis.items():
                        try:
                            antires = list(analysis_obj.antiresonance_frequencies())
                            if len(antires) > 0:
                                analysis_results[note] = {
                                    'first_antiresonance': antires[0],
                                    'num_antiresonances': len(antires)
                                }
                        except Exception as e:
                            logger.warning(f"Error procesando análisis para nota {note}: {e}")
                    
                    results.append({
                        'hole_key': hole_key,
                        'perturbation_value': val,
                        'perturbation_type': perturbation_type,
                        'analysis_results': analysis_results
                    })
        
        return results
    
    def get_perturbation_summary(self) -> Dict[str, Any]:
        """
        Obtiene un resumen de las perturbaciones aplicadas.
        
        Returns:
            Diccionario con información de las perturbaciones.
        """
        if not self.perturbed_flute_data:
            return {}
        
        summary = {
            'original_model': self.original_flute_data.flute_model,
            'perturbed_model': self.perturbed_flute_data.flute_model,
            'has_acoustic_analysis': bool(self.perturbed_flute_data.acoustic_analysis),
            'notes_available': list(self.perturbed_flute_data.acoustic_analysis.keys()) if self.perturbed_flute_data.acoustic_analysis else []
        }
        
        return summary

