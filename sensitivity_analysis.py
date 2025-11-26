"""
Módulo para análisis de sensibilidad/perturbaciones de flautas.

Permite variar parámetros geométricos de una flauta base y analizar
el impacto en su respuesta acústica.
"""

import logging
import copy
import csv
import numpy as np
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from flute_data_db import FluteDataDB
from constants import FLUTE_PARTS_ORDER, get_speed_of_sound
from analysis_module import FluteAnalyzer
from flute_operations import FluteOperations

logger = logging.getLogger(__name__)


class SensitivityParameter(Enum):
    """Parámetros que se pueden variar en el análisis de sensibilidad."""
    HOLE_UNDERCUT = "hole_undercut"
    PART_TAPER = "part_taper"
    STOPPER_POSITION = "stopper_position"
    HOLE_DIAMETER = "hole_diameter"
    EMBOUCHURE_DIAMETER = "embouchure_diameter"
    HOLE_POSITION = "hole_position"
    
    def get_display_name(self) -> str:
        """Retorna nombre para mostrar en UI."""
        names = {
            self.HOLE_UNDERCUT: "Ángulo de Undercut de Agujeros",
            self.PART_TAPER: "Ángulo de Conicidad de Partes",
            self.STOPPER_POSITION: "Posición del Corcho",
            self.HOLE_DIAMETER: "Diámetro de Agujeros Laterales",
            self.EMBOUCHURE_DIAMETER: "Diámetro de Embocadura",
            self.HOLE_POSITION: "Posición de Agujeros Laterales"
        }
        return names[self]
    
    def get_unit(self) -> str:
        """Retorna la unidad de medida del parámetro."""
        units = {
            self.HOLE_UNDERCUT: "deg",
            self.PART_TAPER: "%",
            self.STOPPER_POSITION: "mm",
            self.HOLE_DIAMETER: "mm",
            self.EMBOUCHURE_DIAMETER: "mm",
            self.HOLE_POSITION: "mm"
        }
        return units[self]


@dataclass
class VariationConfig:
    """Configuración de una variación de parámetro."""
    parameter: SensitivityParameter
    base_value: float
    min_value: float
    max_value: float
    num_steps: int = 10
    step_size: Optional[float] = None
    target_part: Optional[str] = None  # Para parámetros específicos de parte
    target_hole: Optional[int] = None  # Para parámetros específicos de agujero
    
    def __post_init__(self):
        """Calcula step_size si no está especificado."""
        if self.step_size is None and self.num_steps > 1:
            self.step_size = (self.max_value - self.min_value) / (self.num_steps - 1)
        elif self.step_size is not None:
            self.num_steps = int((self.max_value - self.min_value) / self.step_size) + 1
    
    def get_values(self) -> List[float]:
        """Retorna lista de valores a generar."""
        if self.num_steps == 1:
            return [self.base_value]
        return [self.min_value + i * self.step_size for i in range(self.num_steps)]


class FluteVariantGenerator:
    """Genera variantes de una flauta modificando parámetros geométricos."""
    
    def __init__(self, base_flute_data: Dict[str, Any], base_flute_name: str):
        """
        Inicializa el generador de variantes.
        
        Args:
            base_flute_data: Diccionario con datos de la flauta base (JSON)
            base_flute_name: Nombre de la flauta base
        """
        self.base_data = base_flute_data
        self.base_name = base_flute_name
    
    def generate_variants(
        self, 
        config: VariationConfig
    ) -> List[Tuple[Dict[str, Any], str, float]]:
        """
        Genera N variantes modificando el parámetro especificado.
        
        Args:
            config: Configuración de la variación
        
        Returns:
            Lista de tuplas (flute_data, variant_name, parameter_value)
        """
        values = config.get_values()
        variants = []
        
        for idx, value in enumerate(values):
            # Clonar datos base
            variant_data = copy.deepcopy(self.base_data)
            
            # Aplicar modificación según parámetro
            if config.parameter == SensitivityParameter.HOLE_UNDERCUT:
                self._apply_hole_undercut(variant_data, config.target_hole, value)
            elif config.parameter == SensitivityParameter.PART_TAPER:
                self._apply_part_taper(variant_data, config.target_part, value)
            elif config.parameter == SensitivityParameter.STOPPER_POSITION:
                self._apply_stopper_position(variant_data, value)
            elif config.parameter == SensitivityParameter.HOLE_DIAMETER:
                self._apply_hole_diameter(variant_data, config.target_hole, value)
            elif config.parameter == SensitivityParameter.EMBOUCHURE_DIAMETER:
                self._apply_embouchure_diameter(variant_data, value)
            elif config.parameter == SensitivityParameter.HOLE_POSITION:
                self._apply_hole_position(variant_data, config.target_hole, value)
            
            # Generar nombre descriptivo
            variant_name = self._generate_variant_name(config, value, idx)
            
            variants.append((variant_data, variant_name, value))
        
        logger.info(f"Generadas {len(variants)} variantes para {config.parameter.value}")
        return variants
    
    def _convert_hole_to_cone(self, hole_diam_spec: Any, wall_thickness_mm: float, angle_deg: float) -> List[float]:
        """
        Convierte un agujero cilíndrico a cónico o actualiza un agujero cónico existente.
        
        Args:
            hole_diam_spec: Especificación del agujero (número para cilindro, [diam_out, diam_in] para cono)
            wall_thickness_mm: Espesor del muro en mm
            angle_deg: Ángulo de undercut en grados
        
        Returns:
            Lista [diam_out, diam_in] para el agujero cónico
        """
        # Detectar si ya es un cono
        is_cone = isinstance(hole_diam_spec, (list, tuple)) and len(hole_diam_spec) == 2
        
        if is_cone:
            # Ya es un cono: actualizar diam_in basado en el ángulo
            diam_out, _ = float(hole_diam_spec[0]), float(hole_diam_spec[1])
        else:
            # Es un cilindro: usar el diámetro como diam_out
            diam_out = float(hole_diam_spec) if isinstance(hole_diam_spec, (int, float)) else 7.0
        
        # Calcular diam_in basado en el ángulo de undercut
        if angle_deg > 0:
            angle_rad = np.deg2rad(angle_deg)
            # Fórmula: diam_in = diam_out + 2 * wall_thickness * tan(angle)
            change_in_radius = wall_thickness_mm * np.tan(angle_rad)
            diam_in = diam_out + 2.0 * change_in_radius
        else:
            # Ángulo 0: mantener como cilindro (diam_in = diam_out)
            diam_in = diam_out
        
        return [diam_out, diam_in]
    
    def _estimate_wall_thickness(self, part_data: Dict, hole_pos_rel_mm: float) -> float:
        """
        Estima el espesor del muro en la posición de un agujero.
        Usa una estimación simple basada en los datos disponibles.
        
        Args:
            part_data: Datos de la parte
            hole_pos_rel_mm: Posición relativa del agujero en mm
        
        Returns:
            Espesor estimado en mm (por defecto 2.0mm)
        """
        measurements = part_data.get('measurements', [])
        if not measurements:
            return 2.0  # Valor por defecto
        
        # Interpolar diámetro interno en la posición del agujero
        positions = np.array([m.get('position', 0.0) for m in measurements])
        diameters = np.array([m.get('diameter', 0.0) for m in measurements])
        
        if len(positions) == 0 or len(diameters) == 0:
            return 2.0
        
        diam_int = np.interp(hole_pos_rel_mm, positions, diameters)
        
        # Estimar diámetro externo (asumir 4mm adicionales de diámetro = 2mm de espesor por lado)
        # Esta es una estimación simple; en producción se debería usar external_geometry si está disponible
        diam_ext = diam_int + 4.0
        
        wall_thickness = (diam_ext - diam_int) / 2.0
        return max(wall_thickness, 1.0)  # Mínimo 1mm
    
    def _apply_hole_undercut(self, flute_data: Dict, hole_idx: Optional[int], angle_deg: float) -> None:
        """
        Aplica ángulo de undercut a agujeros, convirtiéndolos a formato cónico si es necesario.
        
        Args:
            flute_data: Datos de la flauta a modificar
            hole_idx: Índice del agujero (None = todos)
            angle_deg: Ángulo en grados (0 = cilindro, >0 = undercut creciente hacia dentro)
        """
        for part_name in FLUTE_PARTS_ORDER:
            if part_name not in flute_data:
                continue
            
            part_data = flute_data[part_name]
            
            # Procesar formato Holes position/diameter
            holes_pos = part_data.get('Holes position', [])
            holes_diam = part_data.get('Holes diameter', [])
            
            if holes_pos and holes_diam:
                # Asegurar que holes_diam tenga la misma longitud que holes_pos
                while len(holes_diam) < len(holes_pos):
                    holes_diam.append(0.0)
                
                for i in range(len(holes_pos)):
                    if hole_idx is None or i == hole_idx:
                        hole_pos_rel_mm = holes_pos[i]
                        hole_diam_spec = holes_diam[i]
                        
                        # Estimar espesor del muro
                        wall_thickness = self._estimate_wall_thickness(part_data, hole_pos_rel_mm)
                        
                        # Convertir a cono y aplicar ángulo
                        if angle_deg != 0:
                            # Aplicar undercut: convertir a cono
                            cone_spec = self._convert_hole_to_cone(hole_diam_spec, wall_thickness, angle_deg)
                            holes_diam[i] = cone_spec
                            logger.debug(f"Agujero {i} en {part_name}: convertido a cono [diam_out={cone_spec[0]:.2f}, diam_in={cone_spec[1]:.2f}] con ángulo {angle_deg:.1f}°")
                        else:
                            # Ángulo 0: mantener como cilindro si no es ya un cono
                            if not (isinstance(hole_diam_spec, (list, tuple)) and len(hole_diam_spec) == 2):
                                # Ya es cilindro, mantener
                                pass
                            else:
                                # Era cono, convertir a cilindro (usar diam_out)
                                diam_out = float(hole_diam_spec[0])
                                holes_diam[i] = diam_out
                                logger.debug(f"Agujero {i} en {part_name}: convertido a cilindro (diam={diam_out:.2f})")
                
                # Actualizar en part_data
                part_data['Holes diameter'] = holes_diam
            
            # Procesar formato Side holes si existe
            if 'Side holes' in part_data:
                side_holes = part_data['Side holes']
                for i, hole in enumerate(side_holes):
                    if hole_idx is None or i == hole_idx:
                        hole_pos_rel_mm = hole.get('position', 0.0)
                        hole_diam_spec = hole.get('diameter', 0.0)
                        
                        # Estimar espesor del muro
                        wall_thickness = self._estimate_wall_thickness(part_data, hole_pos_rel_mm)
                        
                        # Convertir a cono y aplicar ángulo
                        if angle_deg != 0:
                            cone_spec = self._convert_hole_to_cone(hole_diam_spec, wall_thickness, angle_deg)
                            hole['diameter'] = cone_spec
                            hole['undercut_angle_deg'] = angle_deg
                        else:
                            # Ángulo 0: mantener como cilindro
                            if isinstance(hole_diam_spec, (list, tuple)) and len(hole_diam_spec) == 2:
                                hole['diameter'] = float(hole_diam_spec[0])
                            hole.pop('undercut_angle_deg', None)
    
    def _apply_part_taper(self, flute_data: Dict, part_name: str, taper_change_pct: float) -> None:
        """
        Aplica cambio en el ángulo de conicidad de una parte.
        
        Args:
            flute_data: Datos de la flauta a modificar
            part_name: Nombre de la parte (headjoint, left, right, foot)
            taper_change_pct: Cambio porcentual de la pendiente (-50 a +50)
        """
        if part_name not in flute_data:
            logger.warning(f"Parte {part_name} no encontrada")
            return
        
        part_data = flute_data[part_name]
        measurements = part_data.get('measurements', [])
        
        if len(measurements) < 2:
            logger.warning(f"Parte {part_name} tiene menos de 2 mediciones")
            return
        
        # Calcular pendiente actual
        positions = [m['position'] for m in measurements]
        diameters = [m['diameter'] for m in measurements]
        
        if len(positions) >= 2:
            current_slope, _ = np.polyfit(positions, diameters, 1)
            
            # Nueva pendiente
            new_slope = current_slope * (1.0 + taper_change_pct / 100.0)
            
            # Punto de referencia (inicio de la parte)
            ref_pos = measurements[0]['position']
            ref_diam = measurements[0]['diameter']
            
            # Aplicar nueva pendiente
            for m in measurements:
                relative_pos = m['position'] - ref_pos
                new_diameter = ref_diam + new_slope * relative_pos
                m['diameter'] = max(new_diameter, 1.0)  # Evitar valores negativos
            
            logger.debug(f"Parte {part_name}: pendiente {current_slope:.5f} -> {new_slope:.5f}")
    
    def _apply_stopper_position(self, flute_data: Dict, offset_change_mm: float) -> None:
        """
        Aplica cambio en la posición del corcho.
        
        Args:
            flute_data: Datos de la flauta a modificar
            offset_change_mm: Cambio en posición (mm), positivo = más profundo
        """
        headjoint = flute_data.get(FLUTE_PARTS_ORDER[0], {})
        
        if '_calculated_stopper_absolute_position_mm' in headjoint:
            current_pos = headjoint['_calculated_stopper_absolute_position_mm']
            new_pos = current_pos + offset_change_mm
            headjoint['_calculated_stopper_absolute_position_mm'] = new_pos
            logger.debug(f"Posición del corcho: {current_pos:.2f} -> {new_pos:.2f} mm")
        else:
            logger.warning("No se encontró posición del corcho en headjoint")
    
    def _apply_hole_diameter(self, flute_data: Dict, hole_idx: Optional[int], diameter_mm: float) -> None:
        """
        Aplica cambio en el diámetro de agujeros laterales.
        
        Args:
            flute_data: Datos de la flauta a modificar
            hole_idx: Índice del agujero (None = todos excepto embocadura)
            diameter_mm: Nuevo diámetro en mm
        """
        for part_name in FLUTE_PARTS_ORDER:
            if part_name not in flute_data:
                continue
            
            part_data = flute_data[part_name]
            
            # Modificar en Side holes
            if 'Side holes' in part_data:
                side_holes = part_data['Side holes']
                for i, hole in enumerate(side_holes):
                    if hole_idx is None or i == hole_idx:
                        # No modificar embocadura (primer agujero del headjoint)
                        if not (part_name == FLUTE_PARTS_ORDER[0] and i == 0):
                            hole['diameter'] = diameter_mm
            
            # Modificar en Holes diameter
            holes_diam = part_data.get('Holes diameter', [])
            if holes_diam:
                for i in range(len(holes_diam)):
                    if hole_idx is None or i == hole_idx:
                        # No modificar embocadura
                        if not (part_name == FLUTE_PARTS_ORDER[0] and i == 0):
                            holes_diam[i] = diameter_mm
    
    def _apply_embouchure_diameter(self, flute_data: Dict, diameter_mm: float) -> None:
        """
        Aplica cambio en el diámetro de embocadura.
        
        Args:
            flute_data: Datos de la flauta a modificar
            diameter_mm: Nuevo diámetro en mm
        """
        headjoint = flute_data.get(FLUTE_PARTS_ORDER[0], {})
        
        # Modificar en Holes diameter (primer agujero)
        holes_diam = headjoint.get('Holes diameter', [])
        if holes_diam:
            holes_diam[0] = diameter_mm
        
        # Modificar en Side holes (primer agujero)
        if 'Side holes' in headjoint:
            side_holes = headjoint['Side holes']
            if side_holes:
                side_holes[0]['diameter'] = diameter_mm
        
        logger.debug(f"Diámetro de embocadura: {diameter_mm:.2f} mm")
    
    def _apply_hole_position(self, flute_data: Dict, hole_idx: int, position_change_mm: float) -> None:
        """
        Aplica cambio en la posición de un agujero lateral.
        
        Args:
            flute_data: Datos de la flauta a modificar
            hole_idx: Índice del agujero
            position_change_mm: Cambio en posición (mm)
        """
        for part_name in FLUTE_PARTS_ORDER:
            if part_name not in flute_data:
                continue
            
            part_data = flute_data[part_name]
            
            # Modificar en Side holes
            if 'Side holes' in part_data:
                side_holes = part_data['Side holes']
                if hole_idx < len(side_holes):
                    current_pos = side_holes[hole_idx]['position']
                    side_holes[hole_idx]['position'] = current_pos + position_change_mm
            
            # Modificar en Holes position
            holes_pos = part_data.get('Holes position', [])
            if holes_pos and hole_idx < len(holes_pos):
                holes_pos[hole_idx] += position_change_mm
    
    def _generate_variant_name(self, config: VariationConfig, value: float, index: int) -> str:
        """
        Genera nombre descriptivo para una variante.
        
        Args:
            config: Configuración de la variación
            value: Valor del parámetro
            index: Índice de la variante
        
        Returns:
            Nombre como 'Base_undercut_5.0deg_v3'
        """
        # Abreviaturas para parámetros
        abbrev = {
            SensitivityParameter.HOLE_UNDERCUT: "undercut",
            SensitivityParameter.PART_TAPER: "taper",
            SensitivityParameter.STOPPER_POSITION: "cork",
            SensitivityParameter.HOLE_DIAMETER: "holeDiam",
            SensitivityParameter.EMBOUCHURE_DIAMETER: "embDiam",
            SensitivityParameter.HOLE_POSITION: "holePos"
        }
        
        param_abbr = abbrev[config.parameter]
        unit = config.parameter.get_unit()
        
        # Formatear valor según tipo
        if unit == "deg" or unit == "mm":
            value_str = f"{value:.1f}"
        elif unit == "%":
            value_str = f"{value:+.0f}pct"  # +15pct, -20pct
        else:
            value_str = f"{value:.2f}"
        
        # Añadir parte o agujero si aplica
        target_info = ""
        if config.target_part:
            target_info = f"_{config.target_part}"
        elif config.target_hole is not None:
            target_info = f"_h{config.target_hole}"
        
        return f"{self.base_name}_{param_abbr}{target_info}_{value_str}{unit}_v{index+1}"


class SensitivityAnalyzer:
    """Orquesta el análisis completo de sensibilidad."""
    
    def __init__(self, base_flute: FluteDataDB):
        """
        Inicializa el analizador de sensibilidad.
        
        Args:
            base_flute: Objeto FluteDataDB de la flauta base
        """
        self.base_flute = base_flute
        self.variants = []
    
    def run_analysis(
        self,
        config: VariationConfig,
        temperature: float = 20.0,
        la_frequency: float = 415.0,
        calculate_acoustic: bool = True,
        include_pressure_flow: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[FluteDataDB]:
        """
        Ejecuta análisis completo y retorna lista de FluteDataDB en memoria.
        
        Args:
            config: Configuración de la variación
            temperature: Temperatura para cálculo acústico (°C)
            la_frequency: Diapasón para cálculo acústico (Hz)
            calculate_acoustic: Si True, calcula análisis acústico completo
            include_pressure_flow: Si True, incluye datos de presión/flujo
            progress_callback: Función opcional para reportar progreso (current, total, message)
        
        Returns:
            Lista de objetos FluteDataDB (en memoria, no guardados en BD)
        """
        logger.info(f"Iniciando análisis de sensibilidad: {config.parameter.value}")
        logger.info(f"Rango: {config.min_value} a {config.max_value} en {config.num_steps} pasos")
        
        # Generar variantes geométricas
        if progress_callback:
            progress_callback(0, config.num_steps, "Generando variantes geométricas...")
        
        generator = FluteVariantGenerator(self.base_flute.data, self.base_flute.flute_model)
        variant_specs = generator.generate_variants(config)
        
        # Crear objetos FluteDataDB para cada variante
        self.variants = []
        
        for idx, (variant_data, variant_name, param_value) in enumerate(variant_specs):
            if progress_callback:
                progress_callback(
                    idx + 1, 
                    len(variant_specs),
                    f"Procesando variante {idx+1}/{len(variant_specs)}: {variant_name}"
                )
            
            try:
                # Crear FluteDataDB en memoria (no guardar en BD)
                variant_flute = FluteDataDB(
                    source=variant_data,
                    source_name=variant_name,
                    temperature=temperature,
                    la_frequency=la_frequency,
                    skip_acoustic_analysis=not calculate_acoustic,
                    db_manager=None,  # No guardar en BD
                    include_pressure_flow=include_pressure_flow
                )
                
                # IMPORTANTE: Preservar la geometría externa original del objeto base
                # en lugar de usar la geometría generada automáticamente
                if hasattr(self.base_flute, 'external_geometry') and self.base_flute.external_geometry:
                    variant_flute.external_geometry = copy.deepcopy(self.base_flute.external_geometry)
                    logger.debug(f"Geometría externa preservada de flauta base para variante {variant_name}")
                
                # Almacenar valor del parámetro para referencia
                variant_flute._sensitivity_parameter_value = param_value
                variant_flute._sensitivity_parameter = config.parameter
                
                self.variants.append(variant_flute)
                
            except Exception as e:
                logger.error(f"Error procesando variante {variant_name}: {e}", exc_info=True)
                continue
        
        logger.info(f"Análisis completado: {len(self.variants)} variantes generadas")
        return self.variants
    
    def export_to_csv(self, variants: List[FluteDataDB], output_path: Path) -> None:
        """
        Exporta resultados a CSV.
        
        Args:
            variants: Lista de variantes analizadas
            output_path: Ruta del archivo CSV de salida
        """
        logger.info(f"Exportando resultados a CSV: {output_path}")
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Encabezados
            headers = [
                'Variant_Name', 
                'Parameter', 
                'Parameter_Value',
                'Note'
            ]
            
            # Añadir columnas de métricas acústicas
            metric_cols = [
                'Freq_Hz', 
                'Inharm', 
                'Peak_Height',
                'Q_Factor',
                'Cutoff_Freq'
            ]
            headers.extend(metric_cols)
            
            writer.writerow(headers)
            
            # Datos
            for variant in variants:
                param_value = getattr(variant, '_sensitivity_parameter_value', 0.0)
                param_name = getattr(variant, '_sensitivity_parameter', SensitivityParameter.STOPPER_POSITION).value
                
                if not variant.acoustic_analysis:
                    # Sin análisis acústico
                    row = [
                        variant.flute_model,
                        param_name,
                        f"{param_value:.3f}",
                        '-', '-', '-', '-', '-', '-'
                    ]
                    writer.writerow(row)
                    continue
                
                # Una fila por nota
                for note, analysis in variant.acoustic_analysis.items():
                    freq = analysis.get('resonance_frequencies', [None])[0]
                    inharm = analysis.get('inharmonicity', None)
                    
                    # Altura de pico (primera resonancia)
                    peak_height = None
                    if hasattr(analysis, 'impedance') or 'impedance' in analysis:
                        # Extraer de impedancia si está disponible
                        pass
                    
                    row = [
                        variant.flute_model,
                        param_name,
                        f"{param_value:.3f}",
                        note,
                        f"{freq:.2f}" if freq else '-',
                        f"{inharm:.4f}" if inharm else '-',
                        '-',  # Peak height (requiere procesamiento adicional)
                        '-',  # Q-factor
                        '-'   # Cutoff freq
                    ]
                    writer.writerow(row)
        
        logger.info(f"CSV exportado exitosamente: {output_path}")
    
    def export_to_pdf(self, variants: List[FluteDataDB], config: VariationConfig, output_path: Path) -> None:
        """
        Exporta resultados a PDF con gráficos de evolución.
        
        Args:
            variants: Lista de variantes analizadas
            config: Configuración de la variación
            output_path: Ruta del archivo PDF de salida
        """
        logger.info(f"Generando reporte PDF de análisis de sensibilidad: {output_path}")
        
        generator = SensitivityReportGenerator(self.base_flute, variants, config)
        generator.generate_report(output_path)
        
        logger.info(f"Reporte PDF generado exitosamente: {output_path}")


class SensitivityReportGenerator:
    """Genera reportes PDF completos para análisis de sensibilidad."""
    
    def __init__(self, base_flute: FluteDataDB, variants: List[FluteDataDB], config: VariationConfig):
        """
        Inicializa el generador de reportes.
        
        Args:
            base_flute: Flauta base del análisis
            variants: Lista de variantes generadas
            config: Configuración de la variación
        """
        self.base_flute = base_flute
        self.variants = variants
        self.config = config
        self.metrics = {}
        self.ordered_notes = []
    
    def extract_metrics_from_variants(self) -> Dict[str, Any]:
        """
        Extrae todas las métricas acústicas de las variantes.
        
        Returns:
            Diccionario con métricas organizadas por variante y nota
        """
        logger.info("Extrayendo métricas acústicas de variantes...")
        
        # Obtener todas las notas disponibles
        all_notes = set()
        for variant in self.variants:
            if variant.acoustic_analysis:
                all_notes.update(variant.acoustic_analysis.keys())
        
        self.ordered_notes = sorted(list(all_notes))
        
        if not self.ordered_notes:
            logger.warning("No hay notas disponibles en las variantes")
            return {}
        
        # Obtener frecuencias de digitación de la flauta base
        finger_freqs = self.base_flute.finger_frequencies if hasattr(self.base_flute, 'finger_frequencies') else {}
        
        metrics = {
            'parameter_values': [],
            'variant_names': [],
            'resonance_frequencies': {},
            'inharmonicity': {},
            'moc': {},
            'bi_espe': {},
            'peak_heights': {},
            'q_factors': {}
        }
        
        speed_of_sound_ref = get_speed_of_sound(20.0)
        
        for variant in self.variants:
            param_value = getattr(variant, '_sensitivity_parameter_value', 0.0)
            variant_name = variant.flute_model
            
            metrics['parameter_values'].append(param_value)
            metrics['variant_names'].append(variant_name)
            
            if not variant.acoustic_analysis:
                continue
            
            # Inicializar diccionarios por nota
            for note in self.ordered_notes:
                if note not in metrics['resonance_frequencies']:
                    metrics['resonance_frequencies'][note] = []
                    metrics['inharmonicity'][note] = []
                    metrics['moc'][note] = []
                    metrics['bi_espe'][note] = []
                    metrics['peak_heights'][note] = []
                    metrics['q_factors'][note] = []
            
            # Extraer métricas para cada nota
            for note in self.ordered_notes:
                analysis_obj = variant.acoustic_analysis.get(note)
                f_play = finger_freqs.get(note)
                
                if analysis_obj is None:
                    metrics['resonance_frequencies'][note].append(np.nan)
                    metrics['inharmonicity'][note].append(np.nan)
                    metrics['moc'][note].append(np.nan)
                    metrics['bi_espe'][note].append((np.nan, np.nan))
                    metrics['peak_heights'][note].append(np.nan)
                    metrics['q_factors'][note].append(np.nan)
                    continue
                
                try:
                    # Frecuencias de antiresonancia
                    antires = list(analysis_obj.antiresonance_frequencies())
                    
                    if len(antires) > 0:
                        f0 = antires[0]
                        metrics['resonance_frequencies'][note].append(f0)
                        
                        # Inharmonicidad
                        if f_play and f_play > 0 and f0 > 0:
                            inharm = 1200.0 * np.log2(f_play / f0)
                            metrics['inharmonicity'][note].append(inharm)
                        else:
                            metrics['inharmonicity'][note].append(np.nan)
                        
                        # MOC
                        if len(antires) >= 2:
                            f1 = antires[1]
                            f_play_II = 2.0 * f_play if f_play else 0.0
                            
                            if f0 > 0 and f1 > 0 and f_play_II > 0:
                                moc = (f1 - f0) / (f_play_II - f_play)
                                metrics['moc'][note].append(moc)
                            else:
                                metrics['moc'][note].append(np.nan)
                            
                            # B_I y ESPE
                            bi = np.nan
                            espe = np.nan
                            
                            if f0 > 0 and f_play:
                                bi = 1200.0 * np.log2(f_play / f0)
                            
                            if f0 > 0 and f1 > 0 and f_play and f_play_II > 0:
                                delta_l_I = (speed_of_sound_ref / 2.0) * ((1.0 / f_play) - (1.0 / f0))
                                delta_l_II = speed_of_sound_ref * ((1.0 / f_play_II) - (1.0 / f1))
                                delta_delta_l = delta_l_II - delta_l_I
                                L_eff_I = (speed_of_sound_ref / (2.0 * f_play))
                                
                                if L_eff_I > 0 and (L_eff_I + delta_delta_l) > 1e-9:
                                    espe = 1200.0 * np.log2(L_eff_I / (L_eff_I + delta_delta_l))
                            
                            metrics['bi_espe'][note].append((bi, espe))
                        else:
                            metrics['moc'][note].append(np.nan)
                            metrics['bi_espe'][note].append((np.nan, np.nan))
                    else:
                        metrics['resonance_frequencies'][note].append(np.nan)
                        metrics['inharmonicity'][note].append(np.nan)
                        metrics['moc'][note].append(np.nan)
                        metrics['bi_espe'][note].append((np.nan, np.nan))
                    
                    # Altura de picos y Q-factor (desde impedancia)
                    try:
                        if hasattr(analysis_obj, 'impedance') and hasattr(analysis_obj, 'frequencies'):
                            impedance = analysis_obj.impedance
                            frequencies = analysis_obj.frequencies
                            
                            if len(impedance) > 0 and len(frequencies) > 0:
                                # Encontrar pico principal (máximo de admitancia)
                                admittance = np.abs(1.0 / impedance)
                                peak_idx = np.argmax(admittance)
                                peak_height = admittance[peak_idx]
                                peak_freq = frequencies[peak_idx]
                                
                                metrics['peak_heights'][note].append(peak_height)
                                
                                # Q-factor aproximado (ancho de banda a -3dB)
                                half_power = peak_height / np.sqrt(2)
                                above_half = admittance > half_power
                                if np.any(above_half):
                                    indices = np.where(above_half)[0]
                                    bandwidth = frequencies[indices[-1]] - frequencies[indices[0]]
                                    if bandwidth > 0:
                                        q_factor = peak_freq / bandwidth
                                        metrics['q_factors'][note].append(q_factor)
                                    else:
                                        metrics['q_factors'][note].append(np.nan)
                                else:
                                    metrics['q_factors'][note].append(np.nan)
                            else:
                                metrics['peak_heights'][note].append(np.nan)
                                metrics['q_factors'][note].append(np.nan)
                        else:
                            metrics['peak_heights'][note].append(np.nan)
                            metrics['q_factors'][note].append(np.nan)
                    except Exception as e:
                        logger.warning(f"Error extrayendo altura de picos/Q-factor para {variant_name}, nota {note}: {e}")
                        metrics['peak_heights'][note].append(np.nan)
                        metrics['q_factors'][note].append(np.nan)
                    
                except Exception as e:
                    logger.warning(f"Error extrayendo métricas para {variant_name}, nota {note}: {e}")
                    metrics['resonance_frequencies'][note].append(np.nan)
                    metrics['inharmonicity'][note].append(np.nan)
                    metrics['moc'][note].append(np.nan)
                    metrics['bi_espe'][note].append((np.nan, np.nan))
                    metrics['peak_heights'][note].append(np.nan)
                    metrics['q_factors'][note].append(np.nan)
        
        self.metrics = metrics
        logger.info(f"Métricas extraídas para {len(self.variants)} variantes y {len(self.ordered_notes)} notas")
        return metrics
    
    def generate_evolution_plot(self, metric_name: str, metric_data: Dict[str, List[float]], 
                                param_values: List[float], ylabel: str, unit: str = "") -> Figure:
        """
        Genera gráfico de evolución de una métrica vs parámetro variado.
        
        Args:
            metric_name: Nombre de la métrica
            metric_data: Diccionario {note: [values]}
            param_values: Valores del parámetro variado
            ylabel: Etiqueta del eje Y
            unit: Unidad de medida (opcional)
        
        Returns:
            Figura de matplotlib
        """
        fig = Figure(figsize=(10, 6))
        ax = fig.add_subplot(111)
        
        # Colores para diferentes notas
        colors = plt.cm.tab10(np.linspace(0, 1, len(self.ordered_notes)))
        
        for idx, note in enumerate(self.ordered_notes):
            values = metric_data.get(note, [])
            
            # Filtrar valores válidos (no NaN)
            valid_indices = [i for i, v in enumerate(values) if not np.isnan(v)]
            valid_params = [param_values[i] for i in valid_indices]
            valid_values = [values[i] for i in valid_indices]
            
            if len(valid_values) > 0:
                # Scatter plot
                ax.scatter(valid_params, valid_values, label=note, color=colors[idx], 
                          s=50, alpha=0.7, zorder=3)
                
                # Línea de tendencia (regresión lineal)
                if len(valid_values) >= 2:
                    try:
                        coeffs = np.polyfit(valid_params, valid_values, 1)
                        trend_line = np.poly1d(coeffs)
                        param_range = np.linspace(min(valid_params), max(valid_params), 100)
                        ax.plot(param_range, trend_line(param_range), 
                               color=colors[idx], linestyle='--', alpha=0.5, linewidth=1.5, zorder=2)
                    except:
                        pass  # Si falla la regresión, solo mostrar puntos
        
        ax.set_xlabel(f"{self.config.parameter.get_display_name()} ({self.config.parameter.get_unit()})", 
                     fontsize=11, fontweight='bold')
        ax.set_ylabel(f"{ylabel} {unit}".strip(), fontsize=11, fontweight='bold')
        ax.set_title(f"Evolución de {ylabel} vs {self.config.parameter.get_display_name()}", 
                    fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle=':')
        ax.legend(loc='best', fontsize=9, ncol=2)
        
        return fig
    
    def calculate_summary_statistics(self) -> Dict[str, Dict[str, Any]]:
        """
        Calcula estadísticas resumen para cada métrica.
        
        Returns:
            Diccionario con estadísticas por métrica y nota
        """
        stats = {}
        
        metric_names = {
            'resonance_frequencies': 'Frecuencia de Resonancia (Hz)',
            'inharmonicity': 'Inharmonicidad (cents)',
            'moc': 'MOC',
            'peak_heights': 'Altura de Picos',
            'q_factors': 'Q-Factor'
        }
        
        for metric_key, metric_label in metric_names.items():
            stats[metric_key] = {}
            
            for note in self.ordered_notes:
                values = self.metrics.get(metric_key, {}).get(note, [])
                valid_values = [v for v in values if not np.isnan(v)]
                
                if len(valid_values) > 0:
                    stats[metric_key][note] = {
                        'mean': np.mean(valid_values),
                        'std': np.std(valid_values),
                        'min': np.min(valid_values),
                        'max': np.max(valid_values),
                        'median': np.median(valid_values),
                        'count': len(valid_values)
                    }
                else:
                    stats[metric_key][note] = {
                        'mean': np.nan,
                        'std': np.nan,
                        'min': np.nan,
                        'max': np.nan,
                        'median': np.nan,
                        'count': 0
                    }
        
        # B_I y ESPE (tuplas)
        stats['bi_espe'] = {}
        for note in self.ordered_notes:
            bi_espe_list = self.metrics.get('bi_espe', {}).get(note, [])
            bi_values = [v[0] for v in bi_espe_list if not np.isnan(v[0])]
            espe_values = [v[1] for v in bi_espe_list if not np.isnan(v[1])]
            
            stats['bi_espe'][note] = {
                'bi': {
                    'mean': np.mean(bi_values) if bi_values else np.nan,
                    'std': np.std(bi_values) if bi_values else np.nan,
                    'min': np.min(bi_values) if bi_values else np.nan,
                    'max': np.max(bi_values) if bi_values else np.nan,
                    'median': np.median(bi_values) if bi_values else np.nan
                },
                'espe': {
                    'mean': np.mean(espe_values) if espe_values else np.nan,
                    'std': np.std(espe_values) if espe_values else np.nan,
                    'min': np.min(espe_values) if espe_values else np.nan,
                    'max': np.max(espe_values) if espe_values else np.nan,
                    'median': np.median(espe_values) if espe_values else np.nan
                }
            }
        
        return stats
    
    def generate_report(self, output_path: Path) -> None:
        """
        Genera el reporte PDF completo.
        
        Args:
            output_path: Ruta donde guardar el PDF
        """
        logger.info(f"Generando reporte PDF de análisis de sensibilidad: {output_path}")
        
        # Extraer métricas
        self.extract_metrics_from_variants()
        
        if not self.metrics:
            logger.error("No se pudieron extraer métricas. Abortando generación de reporte.")
            return
        
        with PdfPages(output_path) as pdf:
            # Portada
            self._generate_cover_page(pdf)
            
            # Resumen ejecutivo
            self._generate_summary_page(pdf)
            
            # Gráficos de evolución
            self._generate_evolution_plots(pdf)
            
            # Tabla comparativa
            self._generate_comparison_table(pdf)
            
            # Estadísticas resumen
            self._generate_summary_statistics(pdf)
            
            # Gráficos acústicos completos
            self._generate_acoustic_analysis_plots(pdf)
            
            # Gráficos geométricos
            self._generate_geometric_plots(pdf)
        
        logger.info(f"Reporte PDF generado exitosamente: {output_path}")
    
    def _generate_cover_page(self, pdf: PdfPages) -> None:
        """Genera la portada del reporte."""
        fig = Figure(figsize=(8.5, 11))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # Título
        ax.text(0.5, 0.8, 'Reporte de Análisis de Sensibilidad',
                ha='center', va='center', fontsize=24, weight='bold',
                transform=ax.transAxes)
        
        ax.text(0.5, 0.72, 'Análisis de Variación de Parámetros Geométricos',
                ha='center', va='center', fontsize=16,
                transform=ax.transAxes)
        
        # Información del análisis
        param_display = self.config.parameter.get_display_name()
        param_unit = self.config.parameter.get_unit()
        target_info = ""
        if self.config.target_part:
            target_info = f" - Parte: {self.config.target_part}"
        elif self.config.target_hole is not None:
            target_info = f" - Agujero: {self.config.target_hole}"
        
        info_text = f"""
        Flauta Base: {self.base_flute.flute_model}
        
        Parámetro Variado: {param_display}
        Rango: {self.config.min_value:.2f} a {self.config.max_value:.2f} {param_unit}
        Número de Pasos: {self.config.num_steps}
        {target_info}
        
        Número de Variantes: {len(self.variants)}
        Notas Analizadas: {len(self.ordered_notes)}
        
        Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M')}
        """
        
        ax.text(0.5, 0.4, info_text,
                ha='center', va='center', fontsize=11,
                transform=ax.transAxes, family='monospace')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _generate_summary_page(self, pdf: PdfPages) -> None:
        """Genera página de resumen ejecutivo."""
        stats = self.calculate_summary_statistics()
        
        fig = Figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        ax.text(0.5, 0.95, 'Resumen Ejecutivo',
                ha='center', va='top', fontsize=18, weight='bold',
                transform=ax.transAxes)
        
        # Preparar datos para tabla
        summary_data = []
        
        # Agregar estadísticas agregadas (promedio de todas las notas)
        for metric_key, metric_label in [
            ('inharmonicity', 'Inharmonicidad (cents)'),
            ('moc', 'MOC'),
            ('q_factors', 'Q-Factor')
        ]:
            all_values = []
            for note in self.ordered_notes:
                values = self.metrics.get(metric_key, {}).get(note, [])
                all_values.extend([v for v in values if not np.isnan(v)])
            
            if all_values:
                summary_data.append([
                    metric_label,
                    f"{np.mean(all_values):.2f}",
                    f"{np.std(all_values):.2f}",
                    f"{np.min(all_values):.2f}",
                    f"{np.max(all_values):.2f}",
                    f"{np.median(all_values):.2f}"
                ])
        
        # Crear tabla
        if summary_data:
            col_labels = ['Métrica', 'Promedio', 'Desv. Std', 'Mínimo', 'Máximo', 'Mediana']
            table = ax.table(cellText=summary_data, colLabels=col_labels,
                           cellLoc='center', loc='center',
                           bbox=[0.1, 0.3, 0.8, 0.5])
            
            table.auto_set_font_size(False)
            table.set_fontsize(9)
            table.scale(1, 2)
            
            # Estilo de encabezados
            for i in range(len(col_labels)):
                table[(0, i)].set_facecolor('#4472C4')
                table[(0, i)].set_text_props(weight='bold', color='white')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _generate_evolution_plots(self, pdf: PdfPages) -> None:
        """Genera gráficos de evolución para cada métrica."""
        param_values = self.metrics['parameter_values']
        
        # Gráficos por métrica
        plots = [
            ('inharmonicity', 'Inharmonicidad', 'cents'),
            ('moc', 'MOC', ''),
            ('resonance_frequencies', 'Frecuencia de Resonancia', 'Hz'),
            ('peak_heights', 'Altura de Picos', ''),
            ('q_factors', 'Q-Factor', '')
        ]
        
        for metric_key, metric_label, unit in plots:
            metric_data = self.metrics.get(metric_key, {})
            if metric_data:
                fig = self.generate_evolution_plot(metric_key, metric_data, param_values, metric_label, unit)
                pdf.savefig(fig, bbox_inches='tight')
                plt.close(fig)
        
        # B_I y ESPE (gráficos separados)
        bi_data = {}
        espe_data = {}
        for note in self.ordered_notes:
            bi_espe_list = self.metrics.get('bi_espe', {}).get(note, [])
            bi_data[note] = [v[0] for v in bi_espe_list]
            espe_data[note] = [v[1] for v in bi_espe_list]
        
        if bi_data:
            fig = self.generate_evolution_plot('bi', bi_data, param_values, 'B_I', 'cents')
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
        
        if espe_data:
            fig = self.generate_evolution_plot('espe', espe_data, param_values, 'ESPE', 'cents')
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
    
    def _generate_comparison_table(self, pdf: PdfPages) -> None:
        """Genera tabla comparativa de todas las variantes."""
        fig = Figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        ax.text(0.5, 0.98, 'Tabla Comparativa de Variantes',
                ha='center', va='top', fontsize=14, weight='bold',
                transform=ax.transAxes)
        
        # Preparar datos
        col_labels = ['Variante', 'Parámetro', 'Nota', 'Freq (Hz)', 'Inharm (¢)', 'MOC', 'Q-Factor']
        table_data = []
        
        for idx, variant in enumerate(self.variants):
            param_value = self.metrics['parameter_values'][idx]
            variant_name = self.metrics['variant_names'][idx]
            
            for note in self.ordered_notes:
                freq = self.metrics['resonance_frequencies'][note][idx] if idx < len(self.metrics['resonance_frequencies'][note]) else np.nan
                inharm = self.metrics['inharmonicity'][note][idx] if idx < len(self.metrics['inharmonicity'][note]) else np.nan
                moc = self.metrics['moc'][note][idx] if idx < len(self.metrics['moc'][note]) else np.nan
                q_factor = self.metrics['q_factors'][note][idx] if idx < len(self.metrics['q_factors'][note]) else np.nan
                
                row = [
                    variant_name[:15],
                    f"{param_value:.2f}",
                    note,
                    f"{freq:.1f}" if not np.isnan(freq) else '-',
                    f"{inharm:.2f}" if not np.isnan(inharm) else '-',
                    f"{moc:.4f}" if not np.isnan(moc) else '-',
                    f"{q_factor:.2f}" if not np.isnan(q_factor) else '-'
                ]
                table_data.append(row)
        
        # Dividir en páginas si es necesario
        rows_per_page = 30
        num_pages = (len(table_data) + rows_per_page - 1) // rows_per_page
        
        for page_idx in range(num_pages):
            if page_idx > 0:
                fig = Figure(figsize=(11, 8.5))
                ax = fig.add_subplot(111)
                ax.axis('off')
            
            start_idx = page_idx * rows_per_page
            end_idx = min(start_idx + rows_per_page, len(table_data))
            page_data = table_data[start_idx:end_idx]
            
            if page_data:
                table = ax.table(cellText=page_data, colLabels=col_labels,
                               cellLoc='center', loc='center',
                               bbox=[0.05, 0.1, 0.9, 0.8])
                
                table.auto_set_font_size(False)
                table.set_fontsize(7)
                table.scale(1, 1.5)
                
                # Estilo de encabezados
                for i in range(len(col_labels)):
                    table[(0, i)].set_facecolor('#4472C4')
                    table[(0, i)].set_text_props(weight='bold', color='white')
            
            if num_pages > 1:
                ax.text(0.5, 0.02, f'Página {page_idx + 1} de {num_pages}',
                       ha='center', va='bottom', fontsize=9,
                       transform=ax.transAxes)
            
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
    
    def _generate_summary_statistics(self, pdf: PdfPages) -> None:
        """Genera páginas con estadísticas resumen por métrica."""
        stats = self.calculate_summary_statistics()
        
        # Por cada métrica, crear una página
        for metric_key, metric_label in [
            ('inharmonicity', 'Inharmonicidad (cents)'),
            ('moc', 'MOC'),
            ('resonance_frequencies', 'Frecuencia de Resonancia (Hz)'),
            ('q_factors', 'Q-Factor')
        ]:
            if metric_key not in stats:
                continue
            
            fig = Figure(figsize=(11, 8.5))
            ax = fig.add_subplot(111)
            ax.axis('off')
            
            ax.text(0.5, 0.95, f'Estadísticas Resumen: {metric_label}',
                    ha='center', va='top', fontsize=14, weight='bold',
                    transform=ax.transAxes)
            
            # Preparar datos de tabla
            table_data = []
            for note in self.ordered_notes:
                if note in stats[metric_key]:
                    s = stats[metric_key][note]
                    table_data.append([
                        note,
                        f"{s['mean']:.2f}" if not np.isnan(s['mean']) else '-',
                        f"{s['std']:.2f}" if not np.isnan(s['std']) else '-',
                        f"{s['min']:.2f}" if not np.isnan(s['min']) else '-',
                        f"{s['max']:.2f}" if not np.isnan(s['max']) else '-',
                        f"{s['median']:.2f}" if not np.isnan(s['median']) else '-',
                        f"{s['count']}"
                    ])
            
            if table_data:
                col_labels = ['Nota', 'Promedio', 'Desv. Std', 'Mínimo', 'Máximo', 'Mediana', 'N']
                table = ax.table(cellText=table_data, colLabels=col_labels,
                               cellLoc='center', loc='center',
                               bbox=[0.1, 0.2, 0.8, 0.6])
                
                table.auto_set_font_size(False)
                table.set_fontsize(9)
                table.scale(1, 2)
                
                # Estilo de encabezados
                for i in range(len(col_labels)):
                    table[(0, i)].set_facecolor('#4472C4')
                    table[(0, i)].set_text_props(weight='bold', color='white')
            
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
        
        # B_I y ESPE (página combinada)
        if 'bi_espe' in stats:
            fig = Figure(figsize=(11, 8.5))
            ax = fig.add_subplot(111)
            ax.axis('off')
            
            ax.text(0.5, 0.95, 'Estadísticas Resumen: B_I y ESPE (cents)',
                    ha='center', va='top', fontsize=14, weight='bold',
                    transform=ax.transAxes)
            
            table_data = []
            for note in self.ordered_notes:
                if note in stats['bi_espe']:
                    s_bi = stats['bi_espe'][note]['bi']
                    s_espe = stats['bi_espe'][note]['espe']
                    table_data.append([
                        note,
                        f"{s_bi['mean']:.2f}" if not np.isnan(s_bi['mean']) else '-',
                        f"{s_bi['std']:.2f}" if not np.isnan(s_bi['std']) else '-',
                        f"{s_espe['mean']:.2f}" if not np.isnan(s_espe['mean']) else '-',
                        f"{s_espe['std']:.2f}" if not np.isnan(s_espe['std']) else '-'
                    ])
            
            if table_data:
                col_labels = ['Nota', 'B_I Promedio', 'B_I Desv. Std', 'ESPE Promedio', 'ESPE Desv. Std']
                table = ax.table(cellText=table_data, colLabels=col_labels,
                               cellLoc='center', loc='center',
                               bbox=[0.1, 0.2, 0.8, 0.6])
                
                table.auto_set_font_size(False)
                table.set_fontsize(9)
                table.scale(1, 2)
                
                # Estilo de encabezados
                for i in range(len(col_labels)):
                    table[(0, i)].set_facecolor('#4472C4')
                    table[(0, i)].set_text_props(weight='bold', color='white')
            
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
    
    def _generate_acoustic_analysis_plots(self, pdf: PdfPages) -> None:
        """Genera todos los gráficos del análisis acústico usando FluteAnalyzer."""
        logger.info("Generando gráficos acústicos completos...")
        
        # Crear FluteAnalyzer con todas las variantes (base + variantes)
        all_flutes = [self.base_flute] + self.variants
        analyzer = FluteAnalyzer(all_flutes)
        
        # Obtener frecuencia de referencia (del base_flute si está disponible)
        reference_pitch = 415.0
        if hasattr(self.base_flute, 'la_frequency') and self.base_flute.la_frequency:
            reference_pitch = self.base_flute.la_frequency
        
        # Lista de gráficos a generar
        acoustic_plots = [
            ('Inharmonicidad', lambda: analyzer.plot_inharmonicity()),
            ('MOC', lambda: analyzer.plot_moc()),
            ('B_I y ESPE', lambda: analyzer.plot_bi_espe()),
            ('Frecuencias de Resonancia', lambda: analyzer.plot_resonance_frequencies(reference_pitch=reference_pitch)),
            ('Altura de Picos', lambda: analyzer.plot_peak_heights()),
            ('Q-Factor', lambda: analyzer.plot_q_factor()),
            ('Ratios Armónicos', lambda: analyzer.plot_harmonic_ratios()),
            ('Coherencia de Fase', lambda: analyzer.plot_phase_coherence()),
            ('Estabilidad de Pitch', lambda: analyzer.plot_pitch_stability()),
            ('Frecuencia de Corte', lambda: analyzer.plot_cutoff_frequency())
        ]
        
        for plot_name, plot_func in acoustic_plots:
            try:
                fig = plot_func()
                if fig:
                    # Agregar título de sección (solo si no tiene suptitle ya)
                    if not hasattr(fig, '_suptitle') or fig._suptitle is None:
                        fig.suptitle(f'Análisis Acústico: {plot_name}', fontsize=14, fontweight='bold', y=0.98)
                    # Ajustar layout para evitar sobreposiciones
                    try:
                        fig.tight_layout(rect=[0, 0, 1, 0.96])
                    except:
                        pass  # Si tight_layout falla, continuar
                    pdf.savefig(fig, bbox_inches='tight')
                    plt.close(fig)
                    logger.info(f"  ✓ {plot_name} generado")
                else:
                    logger.warning(f"  ✗ {plot_name} no generó figura")
            except Exception as e:
                logger.warning(f"  ✗ Error generando {plot_name}: {e}")
    
    def _generate_geometric_plots(self, pdf: PdfPages) -> None:
        """Genera gráficos geométricos que muestran los cambios en los parámetros."""
        logger.info("Generando gráficos geométricos...")
        
        # Seleccionar algunas variantes representativas (mínimo, medio, máximo)
        if len(self.variants) < 3:
            selected_variants = self.variants
        else:
            # Seleccionar primera, media y última
            indices = [0, len(self.variants) // 2, len(self.variants) - 1]
            selected_variants = [self.variants[i] for i in indices]
        
        # Incluir también la flauta base
        all_selected = [self.base_flute] + selected_variants
        
        # Crear FluteOperations para cada flauta
        flute_ops_list = [FluteOperations(fd) for fd in all_selected]
        
        # Colores para diferenciar las variantes
        colors = plt.cm.tab10(np.linspace(0, 1, len(all_selected)))
        
        # 1. Perfil combinado (perfil acústico interno)
        try:
            fig = Figure(figsize=(14, 6))
            fig.suptitle('Perfil Acústico Interno - Comparación de Variantes', 
                        fontsize=14, fontweight='bold', y=0.98)
            ax = fig.add_subplot(111)
            
            for idx, (flute_ops, color) in enumerate(zip(flute_ops_list, colors)):
                label = flute_ops.flute_data.flute_model
                if idx == 0:
                    label += " (Base)"
                else:
                    param_val = getattr(flute_ops.flute_data, '_sensitivity_parameter_value', None)
                    if param_val is not None:
                        label += f" (Parámetro: {param_val:.2f})"
                
                # Obtener posición del corcho para offset
                stopper_pos = flute_ops.flute_data.data.get(FLUTE_PARTS_ORDER[0], {}).get(
                    '_calculated_stopper_absolute_position_mm', 0.0
                )
                
                flute_ops.plot_combined_flute_data(
                    ax=ax,
                    plot_label=label,
                    flute_color=color,
                    flute_style='-' if idx == 0 else '--',
                    x_axis_origin_offset=stopper_pos,
                    show_mortise_markers=(idx == 0)  # Solo mostrar marcadores en la base
                )
            
            ax.set_xlabel('Posición desde el corcho (mm)', fontsize=10)
            ax.set_ylabel('Diámetro (mm)', fontsize=10)
            ax.grid(True, alpha=0.3, linestyle=':')
            ax.legend(loc='best', fontsize=9)
            fig.tight_layout(rect=[0, 0, 1, 0.96])  # Dejar espacio para suptitle
            
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            logger.info("  ✓ Perfil combinado generado")
        except Exception as e:
            logger.warning(f"  ✗ Error generando perfil combinado: {e}")
        
        # 2. Corte axial 2D (mostrando agujeros y perfiles)
        try:
            fig = Figure(figsize=(14, 8))
            fig.suptitle('Corte Axial 2D - Comparación de Variantes', 
                        fontsize=14, fontweight='bold', y=0.98)
            ax = fig.add_subplot(111)
            
            for idx, (flute_ops, color) in enumerate(zip(flute_ops_list, colors)):
                label = flute_ops.flute_data.flute_model
                if idx == 0:
                    label += " (Base)"
                else:
                    param_val = getattr(flute_ops.flute_data, '_sensitivity_parameter_value', None)
                    if param_val is not None:
                        label += f" (Parámetro: {param_val:.2f})"
                
                stopper_pos = flute_ops.flute_data.data.get(FLUTE_PARTS_ORDER[0], {}).get(
                    '_calculated_stopper_absolute_position_mm', 0.0
                )
                
                flute_ops.plot_axial_cut_2d(
                    ax=ax,
                    plot_label=label,
                    internal_color=color,
                    external_color=color,
                    hole_color=color,
                    x_axis_origin_offset=stopper_pos,
                    cone_angle_deg=5.0
                )
            
            ax.set_xlabel('Posición desde el corcho (mm)', fontsize=10)
            ax.set_ylabel('Radio (mm)', fontsize=10)
            ax.grid(True, alpha=0.3, linestyle=':')
            ax.legend(loc='best', fontsize=9)
            ax.set_aspect('equal', adjustable='box')
            fig.tight_layout(rect=[0, 0, 1, 0.96])  # Dejar espacio para suptitle
            
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            logger.info("  ✓ Corte axial 2D generado")
        except Exception as e:
            logger.warning(f"  ✗ Error generando corte axial 2D: {e}")
        
        # 2b. Vista sólida 2D (perfil combinado con perfil externo)
        try:
            fig = Figure(figsize=(14, 6))
            fig.suptitle('Vista Sólida 2D - Perfil Combinado', 
                        fontsize=14, fontweight='bold', y=0.98)
            ax = fig.add_subplot(111)
            
            for idx, (flute_ops, color) in enumerate(zip(flute_ops_list, colors)):
                label = flute_ops.flute_data.flute_model
                if idx == 0:
                    label += " (Base)"
                else:
                    param_val = getattr(flute_ops.flute_data, '_sensitivity_parameter_value', None)
                    if param_val is not None:
                        label += f" (Parámetro: {param_val:.2f})"
                
                stopper_pos = flute_ops.flute_data.data.get(FLUTE_PARTS_ORDER[0], {}).get(
                    '_calculated_stopper_absolute_position_mm', 0.0
                )
                
                result_ax = flute_ops.plot_solid_2d_view(
                    ax=ax,
                    plot_label=label,
                    flute_color=color,
                    x_axis_origin_offset=stopper_pos
                )
            
            if ax.lines or ax.patches:  # Verificar que hay datos
                ax.set_xlabel('Posición desde el corcho (mm)', fontsize=10)
                ax.set_ylabel('Radio (mm)', fontsize=10)
                ax.grid(True, alpha=0.3, linestyle=':')
                ax.legend(loc='best', fontsize=9)
                fig.tight_layout(rect=[0, 0, 1, 0.96])
                
                pdf.savefig(fig, bbox_inches='tight')
                plt.close(fig)
                logger.info("  ✓ Vista sólida 2D generada")
            else:
                plt.close(fig)
                logger.warning("  ✗ No hay datos de perfil externo para vista sólida 2D")
        except Exception as e:
            logger.warning(f"  ✗ Error generando vista sólida 2D: {e}")
        
        # 2c. Partes individuales - Perfiles
        try:
            fig = Figure(figsize=(16, 10))
            fig.suptitle('Partes Individuales - Perfiles Internos', 
                        fontsize=14, fontweight='bold', y=0.98)
            axes = []
            for i in range(len(FLUTE_PARTS_ORDER)):
                ax = fig.add_subplot(2, 2, i+1)
                axes.append(ax)
            
            for flute_idx, (flute_ops, color) in enumerate(zip(flute_ops_list, colors)):
                label = flute_ops.flute_data.flute_model
                if flute_idx == 0:
                    label += " (Base)"
                else:
                    param_val = getattr(flute_ops.flute_data, '_sensitivity_parameter_value', None)
                    if param_val is not None:
                        label += f" (Parámetro: {param_val:.2f})"
                
                for part_idx, part_name in enumerate(FLUTE_PARTS_ORDER):
                    if part_idx < len(axes):
                        ax_part = axes[part_idx]
                        adjusted_pos, diams = flute_ops._calculate_adjusted_positions(part_name, 0.0)
                        
                        if adjusted_pos and diams:
                            ax_part.plot(adjusted_pos, diams, marker='.',
                                       linestyle='-' if flute_idx == 0 else '--',
                                       color=color, markersize=3, label=label)
                            ax_part.set_title(part_name.capitalize(), fontsize=10)
                            ax_part.set_xlabel("Posición (mm)", fontsize=9)
                            ax_part.set_ylabel("Diámetro (mm)", fontsize=9)
                            ax_part.grid(True, linestyle=':', alpha=0.5)
            
            for ax in axes:
                handles, labels_legend = ax.get_legend_handles_labels()
                if handles:
                    by_label = dict(zip(labels_legend, handles))
                    ax.legend(by_label.values(), by_label.keys(), loc='upper right', fontsize=7)
            
            fig.tight_layout(rect=[0, 0, 1, 0.96])
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            logger.info("  ✓ Partes individuales - perfiles generados")
        except Exception as e:
            logger.warning(f"  ✗ Error generando partes individuales: {e}")
        
        # 2d. Partes individuales - Corte axial
        try:
            fig = Figure(figsize=(16, 10))
            fig.suptitle('Partes Individuales - Corte Axial', 
                        fontsize=14, fontweight='bold', y=0.98)
            axes = []
            for i in range(len(FLUTE_PARTS_ORDER)):
                ax = fig.add_subplot(2, 2, i+1)
                axes.append(ax)
            
            for flute_idx, (flute_ops, color) in enumerate(zip(flute_ops_list, colors)):
                label = flute_ops.flute_data.flute_model
                if flute_idx == 0:
                    label += " (Base)"
                else:
                    param_val = getattr(flute_ops.flute_data, '_sensitivity_parameter_value', None)
                    if param_val is not None:
                        label += f" (Parámetro: {param_val:.2f})"
                
                for part_idx, part_name in enumerate(FLUTE_PARTS_ORDER):
                    if part_idx < len(axes):
                        ax_part = axes[part_idx]
                        result_ax = flute_ops.plot_individual_part_axial_cut_2d(
                            part_name=part_name,
                            ax=ax_part,
                            plot_label=label,
                            internal_color=color,
                            external_color=color,
                            hole_color=color
                        )
                        if result_ax:
                            ax_part.set_title(part_name.capitalize(), fontsize=10)
                            ax_part.set_xlabel("Posición (mm)", fontsize=9)
                            ax_part.set_ylabel("Radio (mm)", fontsize=9)
                            ax_part.grid(True, linestyle=':', alpha=0.5)
            
            for ax in axes:
                handles, labels_legend = ax.get_legend_handles_labels()
                if handles:
                    by_label = dict(zip(labels_legend, handles))
                    ax.legend(by_label.values(), by_label.keys(), loc='upper right', fontsize=7)
            
            fig.tight_layout(rect=[0, 0, 1, 0.96])
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            logger.info("  ✓ Partes individuales - corte axial generado")
        except Exception as e:
            logger.warning(f"  ✗ Error generando partes individuales corte axial: {e}")
        
        # 3. Vista superior (top view) - siempre generar si hay agujeros
        try:
            fig = Figure(figsize=(14, 6))
            ax = fig.add_subplot(111)
            
            has_holes = False
            
            for idx, (flute_ops, color) in enumerate(zip(flute_ops_list, colors)):
                label = flute_ops.flute_data.flute_model
                if idx == 0:
                    label += " (Base)"
                else:
                    param_val = getattr(flute_ops.flute_data, '_sensitivity_parameter_value', None)
                    if param_val is not None:
                        label += f" (Parámetro: {param_val:.2f})"
                
                # Calcular posiciones absolutas de agujeros (similar a plot_physical_assembly)
                part_physical_starts = {}
                current_physical_pos = 0.0
                next_connection_point = 0.0
                
                for part_idx, part_name in enumerate(FLUTE_PARTS_ORDER):
                    part_data = flute_ops.flute_data.data.get(part_name, {})
                    total_length = part_data.get("Total length", 0.0)
                    mortise_length = part_data.get("Mortise length", 0.0)
                    
                    if part_idx == 0:  # Headjoint
                        part_physical_starts[part_name] = 0.0
                        next_connection_point = total_length - mortise_length
                    elif part_idx == 1:  # Body (Left)
                        part_physical_starts[part_name] = next_connection_point
                        next_connection_point = part_physical_starts[part_name] + total_length
                    else:  # Foot (Right)
                        part_physical_starts[part_name] = next_connection_point - mortise_length
                        next_connection_point = part_physical_starts[part_name] + total_length
                
                # Dibujar agujeros con posiciones absolutas
                holes_drawn = []
                for part_name in FLUTE_PARTS_ORDER:
                    part_data = flute_ops.flute_data.data.get(part_name, {})
                    hole_positions = part_data.get("Holes position", [])
                    hole_diameters = part_data.get("Holes diameter", [])
                    part_start = part_physical_starts.get(part_name, 0.0)
                    
                    if hole_positions and hole_diameters:
                        for h_pos_rel, h_diam in zip(hole_positions, hole_diameters):
                            # Calcular posición absoluta
                            h_pos_abs = part_start + h_pos_rel
                            
                            # Determinar diámetro (puede ser número o lista [diam_out, diam_in])
                            if isinstance(h_diam, (list, tuple)) and len(h_diam) == 2:
                                # Cono: usar diámetro externo para vista superior
                                diam_out = float(h_diam[0])
                                diam_in = float(h_diam[1])
                                # Dibujar círculo externo
                                circle_out = plt.Circle((h_pos_abs, 0), diam_out/2.0, 
                                                      color=color, fill=False, 
                                                      linestyle='-' if idx == 0 else '--',
                                                      linewidth=2.0, alpha=0.8, label=label if not holes_drawn else "")
                                ax.add_patch(circle_out)
                                # Dibujar círculo interno (más delgado)
                                circle_in = plt.Circle((h_pos_abs, 0), diam_in/2.0, 
                                                      color=color, fill=False, 
                                                      linestyle='-' if idx == 0 else '--',
                                                      linewidth=1.0, alpha=0.6)
                                ax.add_patch(circle_in)
                                has_holes = True
                            else:
                                # Cilindro: usar el diámetro directamente
                                diam = float(h_diam) if isinstance(h_diam, (int, float)) else 0.0
                                if diam > 0:
                                    circle = plt.Circle((h_pos_abs, 0), diam/2.0, 
                                                      color=color, fill=False, 
                                                      linestyle='-' if idx == 0 else '--',
                                                      linewidth=2.0, alpha=0.8, label=label if not holes_drawn else "")
                                    ax.add_patch(circle)
                                    has_holes = True
                            
                            holes_drawn.append(True)
                
                # También dibujar embocadura si existe
                headjoint_data = flute_ops.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                emb_pos = headjoint_data.get("Embouchure position", 0.0)
                emb_diam = headjoint_data.get("Embouchure diameter", None)
                
                if emb_diam is not None:
                    if isinstance(emb_diam, (list, tuple)) and len(emb_diam) == 2:
                        emb_diam_out = float(emb_diam[0])
                        circle_emb_out = plt.Circle((emb_pos, 0), emb_diam_out/2.0,
                                                   color=color, fill=False,
                                                   linestyle='-' if idx == 0 else '--',
                                                   linewidth=2.0, alpha=0.8,
                                                   label=label if not holes_drawn else "")
                        ax.add_patch(circle_emb_out)
                        emb_diam_in = float(emb_diam[1])
                        circle_emb_in = plt.Circle((emb_pos, 0), emb_diam_in/2.0,
                                                  color=color, fill=False,
                                                  linestyle='-' if idx == 0 else '--',
                                                  linewidth=1.0, alpha=0.6)
                        ax.add_patch(circle_emb_in)
                    else:
                        emb_diam_val = float(emb_diam) if isinstance(emb_diam, (int, float)) else 0.0
                        if emb_diam_val > 0:
                            circle_emb = plt.Circle((emb_pos, 0), emb_diam_val/2.0,
                                                  color=color, fill=False,
                                                  linestyle='-' if idx == 0 else '--',
                                                  linewidth=2.0, alpha=0.8,
                                                  label=label if not holes_drawn else "")
                            ax.add_patch(circle_emb)
                    has_holes = True
            
            if has_holes:
                # Calcular límites del gráfico
                all_x_positions = []
                all_radii = []
                for flute_ops in flute_ops_list:
                    # Calcular posiciones absolutas igual que arriba
                    part_physical_starts = {}
                    next_connection_point = 0.0
                    
                    for part_idx, part_name in enumerate(FLUTE_PARTS_ORDER):
                        part_data = flute_ops.flute_data.data.get(part_name, {})
                        total_length = part_data.get("Total length", 0.0)
                        mortise_length = part_data.get("Mortise length", 0.0)
                        
                        if part_idx == 0:  # Headjoint
                            part_physical_starts[part_name] = 0.0
                            next_connection_point = total_length - mortise_length
                        elif part_idx == 1:  # Body (Left)
                            part_physical_starts[part_name] = next_connection_point
                            next_connection_point = part_physical_starts[part_name] + total_length
                        else:  # Foot (Right)
                            part_physical_starts[part_name] = next_connection_point - mortise_length
                            next_connection_point = part_physical_starts[part_name] + total_length
                    
                    for part_name in FLUTE_PARTS_ORDER:
                        part_data = flute_ops.flute_data.data.get(part_name, {})
                        hole_positions = part_data.get("Holes position", [])
                        hole_diameters = part_data.get("Holes diameter", [])
                        part_start = part_physical_starts.get(part_name, 0.0)
                        
                        if hole_positions and hole_diameters:
                            for h_pos_rel, h_diam in zip(hole_positions, hole_diameters):
                                h_pos_abs = part_start + h_pos_rel
                                all_x_positions.append(h_pos_abs)
                                
                                if isinstance(h_diam, (list, tuple)) and len(h_diam) == 2:
                                    all_radii.append(float(h_diam[0]) / 2.0)
                                else:
                                    diam = float(h_diam) if isinstance(h_diam, (int, float)) else 0.0
                                    if diam > 0:
                                        all_radii.append(diam / 2.0)
                    
                    # Incluir embocadura
                    headjoint_data = flute_ops.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                    emb_pos = headjoint_data.get("Embouchure position", 0.0)
                    emb_diam = headjoint_data.get("Embouchure diameter", None)
                    if emb_diam is not None:
                        all_x_positions.append(emb_pos)
                        if isinstance(emb_diam, (list, tuple)) and len(emb_diam) == 2:
                            all_radii.append(float(emb_diam[0]) / 2.0)
                        else:
                            emb_diam_val = float(emb_diam) if isinstance(emb_diam, (int, float)) else 0.0
                            if emb_diam_val > 0:
                                all_radii.append(emb_diam_val / 2.0)
                
                if all_x_positions:
                    x_min = min(all_x_positions) - 20
                    x_max = max(all_x_positions) + 20
                    r_max = max(all_radii) if all_radii else 10
                    
                    ax.set_xlim(x_min, x_max)
                    ax.set_ylim(-r_max * 1.5, r_max * 1.5)
                
                fig.suptitle('Vista Superior - Agujeros y Embocadura', 
                            fontsize=14, fontweight='bold', y=0.98)
                ax.set_xlabel('Posición desde el inicio (mm)', fontsize=10)
                ax.set_ylabel('Radio (mm)', fontsize=10)
                ax.grid(True, alpha=0.3, linestyle=':')
                ax.set_aspect('equal', adjustable='box')
                
                # Crear leyenda manualmente para evitar duplicados
                handles, labels_legend = ax.get_legend_handles_labels()
                if handles:
                    by_label = dict(zip(labels_legend, handles))
                    ax.legend(by_label.values(), by_label.keys(), loc='best', fontsize=9)
                
                fig.tight_layout(rect=[0, 0, 1, 0.96])
                pdf.savefig(fig, bbox_inches='tight')
                plt.close(fig)
                logger.info("  ✓ Vista superior generada")
            else:
                logger.warning("  ✗ No se encontraron agujeros para la vista superior")
                plt.close(fig)
        except Exception as e:
            logger.warning(f"  ✗ Error generando vista superior: {e}", exc_info=True)
        
        # 4. Ensamblaje físico (si el parámetro afecta geometría física)
        if self.config.parameter in [SensitivityParameter.PART_TAPER, 
                                     SensitivityParameter.STOPPER_POSITION]:
            try:
                fig = Figure(figsize=(14, 6))
                ax = fig.add_subplot(111)
                
                for idx, (flute_ops, color) in enumerate(zip(flute_ops_list, colors)):
                    label = flute_ops.flute_data.flute_model
                    if idx == 0:
                        label += " (Base)"
                    else:
                        param_val = getattr(flute_ops.flute_data, '_sensitivity_parameter_value', None)
                        if param_val is not None:
                            label += f" (Parámetro: {param_val:.2f})"
                    
                    max_x = flute_ops.plot_physical_assembly(
                        ax=ax,
                        plot_label_suffix=label,
                        overall_linestyle='-' if idx == 0 else '--'
                    )
                    
                    if max_x and max_x > 0:
                        ax.set_xlim(-10, max_x + 10)
                
                fig.suptitle('Ensamblaje Físico - Comparación de Variantes', 
                            fontsize=14, fontweight='bold', y=0.98)
                ax.set_xlabel('Posición (mm)', fontsize=10)
                ax.set_ylabel('Diámetro (mm)', fontsize=10)
                ax.grid(True, alpha=0.3, linestyle=':')
                ax.legend(loc='best', fontsize=9)
                fig.tight_layout(rect=[0, 0, 1, 0.96])
                
                pdf.savefig(fig, bbox_inches='tight')
                plt.close(fig)
                logger.info("  ✓ Ensamblaje físico generado")
            except Exception as e:
                logger.warning(f"  ✗ Error generando ensamblaje físico: {e}")

