"""
Modelado paramétrico de geometría externa de flautas.

Este módulo proporciona funcionalidad para generar perfiles externos
cuando no están disponibles en los datos medidos, usando modelos paramétricos
basados en el diámetro interno y espesor de pared.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from scipy.interpolate import interp1d
import logging

from constants import FLUTE_PARTS_ORDER, M_TO_MM_FACTOR

logger = logging.getLogger(__name__)


class ParametricExternalGeometry:
    """
    Genera geometría externa paramétrica basada en geometría interna.
    """
    
    def __init__(
        self,
        internal_measurements: List[Dict[str, float]],
        wall_thickness_type: str = 'constant',
        wall_thickness_mm: Optional[float] = None,
        wall_thickness_profile: Optional[List[Dict[str, float]]] = None,
        smoothing_factor: float = 1.0
    ):
        """
        Inicializa el modelador de geometría externa.
        
        Args:
            internal_measurements: Lista de mediciones internas [{'position': float, 'diameter': float}].
            wall_thickness_type: Tipo de espesor ('constant', 'variable', 'proportional').
            wall_thickness_mm: Espesor constante en mm (para 'constant').
            wall_thickness_profile: Perfil de espesor variable [{'position': float, 'thickness': float}].
            smoothing_factor: Factor de suavizado para transiciones (0-1, donde 1 es máximo suavizado).
        """
        self.internal_measurements = internal_measurements
        self.wall_thickness_type = wall_thickness_type
        self.wall_thickness_mm = wall_thickness_mm or 2.0  # Default: 2mm
        self.wall_thickness_profile = wall_thickness_profile
        self.smoothing_factor = max(0.0, min(1.0, smoothing_factor))  # Clamp entre 0 y 1
        
        # Validar y preparar datos
        if not internal_measurements:
            raise ValueError("Se requieren mediciones internas para generar geometría externa")
        
        self.positions = np.array([m['position'] for m in internal_measurements])
        self.internal_diameters = np.array([m['diameter'] for m in internal_measurements])
        self.internal_radii = self.internal_diameters / 2.0
    
    def generate_external_profile(self) -> List[Dict[str, float]]:
        """
        Genera el perfil externo basado en el modelo paramétrico.
        
        Returns:
            Lista de mediciones externas [{'position': float, 'external_diameter': float}].
        """
        if self.wall_thickness_type == 'constant':
            wall_thickness = np.full_like(self.positions, self.wall_thickness_mm)
        elif self.wall_thickness_type == 'variable' and self.wall_thickness_profile:
            # Interpolar perfil de espesor variable
            profile_positions = np.array([p['position'] for p in self.wall_thickness_profile])
            profile_thicknesses = np.array([p['thickness'] for p in self.wall_thickness_profile])
            
            # Crear función de interpolación
            if len(profile_positions) > 1:
                interp_func = interp1d(
                    profile_positions,
                    profile_thicknesses,
                    kind='linear',
                    fill_value='extrapolate'
                )
                wall_thickness = interp_func(self.positions)
            else:
                wall_thickness = np.full_like(self.positions, profile_thicknesses[0] if len(profile_thicknesses) > 0 else self.wall_thickness_mm)
        elif self.wall_thickness_type == 'proportional':
            # Espesor proporcional al diámetro interno (ej: 10% del diámetro)
            wall_thickness = self.internal_diameters * 0.1  # 10% por defecto
            # Aplicar límites mínimos y máximos
            wall_thickness = np.clip(wall_thickness, 1.0, 4.0)  # Entre 1mm y 4mm
        else:
            # Fallback a constante
            wall_thickness = np.full_like(self.positions, self.wall_thickness_mm)
        
        # Aplicar suavizado si es necesario
        if self.smoothing_factor > 0 and len(wall_thickness) > 2:
            wall_thickness = self._smooth_thickness_profile(wall_thickness)
        
        # Calcular diámetros externos
        external_radii = self.internal_radii + wall_thickness
        external_diameters = external_radii * 2.0
        
        # Generar lista de mediciones externas
        external_measurements = [
            {'position': float(pos), 'external_diameter': float(diam)}
            for pos, diam in zip(self.positions, external_diameters)
        ]
        
        return external_measurements
    
    def _smooth_thickness_profile(self, thickness_profile: np.ndarray) -> np.ndarray:
        """
        Suaviza el perfil de espesor usando un filtro de media móvil.
        
        Args:
            thickness_profile: Array de espesores.
        
        Returns:
            Array de espesores suavizados.
        """
        if len(thickness_profile) < 3:
            return thickness_profile
        
        # Tamaño de ventana basado en smoothing_factor
        window_size = max(3, int(len(thickness_profile) * self.smoothing_factor * 0.1))
        if window_size % 2 == 0:
            window_size += 1
        
        # Aplicar filtro de media móvil
        smoothed = np.convolve(
            thickness_profile,
            np.ones(window_size) / window_size,
            mode='same'
        )
        
        # Preservar valores en los extremos
        smoothed[0] = thickness_profile[0]
        smoothed[-1] = thickness_profile[-1]
        
        return smoothed
    
    @staticmethod
    def generate_from_internal_data(
        internal_measurements: List[Dict[str, float]],
        wall_thickness_mm: float = 2.0,
        wall_thickness_type: str = 'constant'
    ) -> List[Dict[str, float]]:
        """
        Método estático para generar geometría externa rápidamente.
        
        Args:
            internal_measurements: Lista de mediciones internas.
            wall_thickness_mm: Espesor de pared en mm.
            wall_thickness_type: Tipo de espesor.
        
        Returns:
            Lista de mediciones externas.
        """
        modeler = ParametricExternalGeometry(
            internal_measurements=internal_measurements,
            wall_thickness_type=wall_thickness_type,
            wall_thickness_mm=wall_thickness_mm
        )
        return modeler.generate_external_profile()


def load_external_geometry_from_json(
    part_data: Dict[str, Any]
) -> Optional[List[Dict[str, float]]]:
    """
    Carga geometría externa desde datos JSON de una parte.
    
    Args:
        part_data: Diccionario con datos de la parte (desde JSON).
    
    Returns:
        Lista de mediciones externas si existen, None en caso contrario.
    """
    # Buscar diferentes posibles nombres de campos
    external_fields = [
        'external_measurements',
        'external_geometry',
        'external_profile',
        'External measurements',
        'External geometry'
    ]
    
    for field in external_fields:
        if field in part_data:
            measurements = part_data[field]
            if isinstance(measurements, list) and len(measurements) > 0:
                # Validar formato
                if all('position' in m and 'external_diameter' in m for m in measurements):
                    return measurements
                elif all('position' in m and 'diameter' in m for m in measurements):
                    # Renombrar 'diameter' a 'external_diameter'
                    return [
                        {'position': m['position'], 'external_diameter': m['diameter']}
                        for m in measurements
                    ]
    
    return None

