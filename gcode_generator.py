# -*- coding: utf-8 -*-
"""
Módulo para generación de código G-code para torno CNC.
Extraído y adaptado de Generate_gcode_general.py para trabajar con FluteDataDB.
"""

import json
import numpy as np
import re
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from scipy.interpolate import interp1d
import logging

logger = logging.getLogger(__name__)

# --- VALORES POR DEFECTO ---
DEFAULT_PARAMS = {
    "INITIAL_BORE_DIAMETER": 13.0,
    "ROUGHING_DEPTH_PER_PASS": 0.5,
    "FINISH_ALLOWANCE_1": 0.01,
    "FINISH_ALLOWANCE_2": 0.1,
    "SPINDLE_SPEED": 1500,
    "ROUGHING_FEED_RATE": 100,
    "FINISHING_FEED_RATE": 50,
    "SAFE_Z_START": 2.0,
    "SAFE_X_RETRACT_RADIAL": 1.0,
    "ROUGHING_STRATEGY": "Layers"
    # ECONOMY_MODE se controla por parámetro
}

# --- FUNCIONES AUXILIARES MODO ECONÓMICO ---

def spindle_stop_eco(gcode_list: List[str], is_economy_mode: bool, comment: str = ""):
    """Añade M5 si el modo económico está activo, con indentación opcional."""
    if is_economy_mode:
        indent = ""
        if gcode_list:
            last_line = gcode_list[-1]
            match = re.match(r'^(\s+)', last_line)
            if match:
                indent = match.group(1)
        gcode_list.append(f"{indent}M5 {comment}")

def spindle_start_eco(gcode_list: List[str], is_economy_mode: bool, comment: str = ""):
    """Añade M3 si el modo económico está activo, con indentación opcional."""
    if is_economy_mode:
        indent = ""
        if gcode_list:
            last_line = gcode_list[-1]
            match = re.match(r'^(\s+)', last_line)
            if match:
                indent = match.group(1)
        gcode_list.append(f"{indent}M3 {comment}")

# --- FUNCIONES PRINCIPALES ---

def load_flute_data_from_dict(part_data_dict: Dict[str, Any], part_type: str) -> Tuple:
    """
    Carga datos de flauta desde un diccionario (de FluteDataDB.data[part_name]).
    
    Args:
        part_data_dict: Diccionario con datos de la parte (measurements, Total length, etc.)
        part_type: Tipo de parte ("headjoint", "left", "right", "foot")
    
    Returns:
        Tupla: (part_type, mortise_length, mortise_diameter, profile_start_diameter,
                profile_end_diameter, profile_measurements, total_length,
                profile_origin_z, profile_end_z)
    """
    try:
        part_type = part_type.lower()
        measurements = part_data_dict.get('measurements', [])
        if not measurements:
            raise ValueError("Diccionario sin 'measurements'.")
        
        mortise_length_original = part_data_dict.get("Mortise length", 0.0)
        total_length = part_data_dict.get('Total length', 0.0)
        
        original_positions = np.array([m['position'] for m in measurements])
        original_diameters = np.array([m['diameter'] for m in measurements])
        
        if not total_length or total_length < np.max(original_positions):
            logger.warning(f"Advertencia: 'Total length' inválido. Usando Z máx: {np.max(original_positions)}.")
            total_length = np.max(original_positions)
        
        transformed_positions = original_positions.copy()
        
        if part_type in ["headjoint", "foot"]:
            logger.info(f"Detectado '{part_type}'. Invirtiendo Z (Z' = {total_length:.2f} - Z)")
            transformed_positions = total_length - original_positions
            transformed_measurements = [
                {"position": z_new, "diameter": d}
                for z_new, d in zip(transformed_positions, original_diameters)
            ]
            transformed_measurements.sort(key=lambda m: m['position'])
            all_positions = np.array([m['position'] for m in transformed_measurements])
            all_diameters = np.array([m['diameter'] for m in transformed_measurements])
            measurements = transformed_measurements
            logger.info(f"Coords Z transformadas. Rango Z': {all_positions[0]:.2f} a {all_positions[-1]:.2f}")
        else:
            measurements.sort(key=lambda m: m['position'])
            all_positions = np.array([m['position'] for m in measurements])
            all_diameters = np.array([m['diameter'] for m in measurements])
            logger.info(f"Parte '{part_type}'. Usando coords Z originales.")
        
        mortise_diameter = 0.0
        profile_start_diameter = 0.0
        profile_end_diameter = 0.0
        profile_measurements = []
        profile_origin_z = 0.0
        profile_end_z = total_length
        
        all_points_interpolator = None
        if len(all_positions) >= 2:
            unique_z_all, unique_indices_all = np.unique(all_positions, return_index=True)
            if len(unique_z_all) >= 2:
                all_points_interpolator = interp1d(
                    unique_z_all, all_diameters[unique_indices_all],
                    kind='linear', bounds_error=False, fill_value="extrapolate"
                )
            elif len(all_positions) >= 1:
                all_points_interpolator = lambda z: all_diameters[0]
        elif len(all_positions) == 1:
            all_points_interpolator = lambda z: all_diameters[0]
        
        if all_points_interpolator is None:
            raise ValueError("No hay suficientes mediciones válidas para interpolar.")
        
        if part_type == "foot":
            original_mortise_start_z = mortise_length_original
            profile_end_z = total_length - original_mortise_start_z
            profile_origin_z = 0.0
            profile_start_diameter = float(all_points_interpolator(0.0))
            profile_end_diameter = float(all_points_interpolator(profile_end_z))
            logger.info(f"'Foot': D inicio perfil (Z'~0): {profile_start_diameter:.3f}")
            logger.info(f"'Foot': D final perfil cónico (Z'={profile_end_z:.3f}): {profile_end_diameter:.3f}")
            
            profile_indices = np.where(
                (all_positions >= profile_origin_z - 1e-6) &
                (all_positions <= profile_end_z + 1e-6)
            )[0]
            
            if len(profile_indices) > 0:
                profile_measurements = [measurements[i] for i in profile_indices]
                if abs(profile_measurements[0]['position'] - profile_origin_z) > 1e-6:
                    profile_measurements.insert(0, {
                        "position": profile_origin_z,
                        "diameter": profile_start_diameter
                    })
                if abs(profile_measurements[-1]['position'] - profile_end_z) > 1e-6:
                    profile_measurements.append({
                        "position": profile_end_z,
                        "diameter": profile_end_diameter
                    })
                profile_measurements.sort(key=lambda m: m['position'])
                logger.info(f"'Foot': Perfil a mecanizar: {len(profile_measurements)} puntos.")
            else:
                logger.warning("Advertencia 'Foot': No se encontraron puntos de perfil.")
                profile_measurements = []
            mortise_diameter = float('inf')
            
        elif mortise_length_original > 1e-6:
            profile_origin_z = mortise_length_original
            idx_z0 = np.where(np.abs(all_positions) < 1e-6)[0]
            
            if len(idx_z0) > 0:
                mortise_diameter = all_diameters[idx_z0[0]]
                logger.info(f"Detectada Espiga/Caja (Z'~0): L={mortise_length_original:.3f}, D={mortise_diameter:.3f}")
                profile_start_diameter = float(all_points_interpolator(profile_origin_z))
                logger.info(f"D inicio perfil (Z'={profile_origin_z:.3f}): {profile_start_diameter:.3f}")
                
                profile_indices = np.where(all_positions >= profile_origin_z - 1e-6)[0]
                if len(profile_indices) > 0:
                    profile_measurements = [measurements[i] for i in profile_indices]
                    profile_end_z = profile_measurements[-1]['position']
                    profile_end_diameter = profile_measurements[-1]['diameter']
                    if abs(profile_measurements[0]['position'] - profile_origin_z) > 1e-6:
                        profile_measurements.insert(0, {
                            "position": profile_origin_z,
                            "diameter": profile_start_diameter
                        })
                    profile_measurements.sort(key=lambda m: m['position'])
                    logger.info(f"Perfil extraído: {len(profile_measurements)} pts, Z'={profile_origin_z:.3f} a Z'={profile_end_z:.3f}")
                else:
                    logger.warning("Advertencia: No hay perfil post-espiga.")
                    profile_measurements = []
                    profile_end_z = profile_origin_z
                    profile_end_diameter = profile_start_diameter
            else:
                logger.warning("Advertencia: Espiga > 0 pero sin Z'~0. Invalidando.")
                mortise_length_original = 0.0
        
        if part_type != "foot" and not (
            mortise_length_original > 1e-6 and
            'mortise_diameter' in locals() and
            mortise_diameter > 0 and
            np.isfinite(mortise_diameter)
        ):
            if measurements:
                profile_origin_z = measurements[0]['position']
                profile_end_z = measurements[-1]['position']
                profile_start_diameter = measurements[0]['diameter']
                profile_end_diameter = measurements[-1]['diameter']
                profile_measurements = measurements
                mortise_diameter = float('inf')
                logger.info(f"Perfil simple detectado: {len(profile_measurements)} pts, Z'={profile_origin_z:.3f} a Z'={profile_end_z:.3f}")
            else:
                logger.error("Error: Sin espiga/caja y sin mediciones.")
                profile_measurements = []
        
        if not isinstance(profile_measurements, list):
            profile_measurements = []
        
        return (
            part_type, mortise_length_original, mortise_diameter,
            profile_start_diameter, profile_end_diameter, profile_measurements,
            total_length, profile_origin_z, profile_end_z
        )
    except Exception as e:
        raise ValueError(f"Error procesando datos: {traceback.format_exc()}")

def load_flute_data(json_path: str) -> Tuple:
    """
    Carga datos de flauta desde un archivo JSON (compatibilidad con código original).
    
    Args:
        json_path: Ruta al archivo JSON
    
    Returns:
        Tupla: (part_type, mortise_length, mortise_diameter, profile_start_diameter,
                profile_end_diameter, profile_measurements, total_length,
                profile_origin_z, profile_end_z)
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        part_type = data.get("Part", "").lower()
        return load_flute_data_from_dict(data, part_type)
    except FileNotFoundError:
        raise FileNotFoundError(f"No JSON: '{json_path}'")
    except Exception as e:
        raise ValueError(f"Error JSON: {traceback.format_exc()}")

def create_profile_interpolator(profile_measurements: List[Dict]) -> Optional[Any]:
    """Crea un interpolador para el perfil."""
    if len(profile_measurements) < 2:
        return None
    
    z_coords = np.array([m['position'] for m in profile_measurements])
    radii = np.array([m['diameter'] for m in profile_measurements]) / 2.0
    
    unique_z, unique_indices = np.unique(z_coords, return_index=True)
    unique_r = radii[unique_indices]
    
    if len(unique_z) < 2:
        return None
    
    return interp1d(
        unique_z, unique_r,
        kind='linear',
        bounds_error=False,
        fill_value=(unique_r[0], unique_r[-1])
    )

def generate_gcode(
    part_type: str,
    mortise_length: float,
    mortise_diameter: float,
    profile_start_diameter: float,
    profile_end_diameter: float,
    profile_measurements: List[Dict],
    total_length: float,
    profile_origin_z: float,
    profile_end_z: float,
    params: Dict[str, Any]
) -> Tuple[List[str], Dict]:
    """
    Genera código G-code para mecanizado.
    
    Returns:
        Tupla: (gcode_lines, toolpath_points)
    """
    initial_bore_diameter = params["INITIAL_BORE_DIAMETER"]
    roughing_depth_per_pass = params["ROUGHING_DEPTH_PER_PASS"]
    finish_allowance_1 = params["FINISH_ALLOWANCE_1"]
    finish_allowance_2 = params["FINISH_ALLOWANCE_2"]
    spindle_speed = params["SPINDLE_SPEED"]
    roughing_feed_rate = params["ROUGHING_FEED_RATE"]
    finishing_feed_rate = params["FINISHING_FEED_RATE"]
    safe_z_start = params["SAFE_Z_START"]
    safe_x_retract_radial = params["SAFE_X_RETRACT_RADIAL"]
    roughing_strategy = params.get("ROUGHING_STRATEGY", "Layers")
    economy_mode = params.get("ECONOMY_MODE", False)
    
    gcode_lines = []
    toolpath_points = {
        'stage1': {'roughing': [], 'finish1': [], 'finish2': []},
        'stage2': {'roughing': [], 'finish1': [], 'finish2': []}
    }
    
    initial_bore_radius = initial_bore_diameter / 2.0
    radial_roughing_step = roughing_depth_per_pass / 2.0
    total_finish_allowance_radial = finish_allowance_1 + finish_allowance_2
    
    has_mortise_feature = mortise_length > 1e-6 and np.isfinite(mortise_diameter)
    has_profile = len(profile_measurements) >= 2
    
    profile_interpolator = create_profile_interpolator(profile_measurements) if has_profile else None
    profile_start_radius = profile_start_diameter / 2.0 if profile_start_diameter > 1e-6 else initial_bore_radius
    profile_end_radius = profile_end_diameter / 2.0 if profile_end_diameter > 1e-6 else initial_bore_radius
    
    z_start_stage1 = 0.0
    z_end_stage1 = total_length
    
    if part_type == "foot":
        if not has_profile:
            raise ValueError("'Foot' sin datos de perfil para mecanizar.")
        z_start_stage1 = profile_origin_z
        z_end_stage1 = profile_end_z
        logger.info(f"Estrategia 'Foot': Mecanizando perfil de Z'={z_start_stage1:.2f} a Z'={z_end_stage1:.2f}")
        
        def get_stage1_target_radius(z):
            if profile_interpolator:
                prof_z_min = profile_measurements[0]['position']
                prof_z_max = profile_measurements[-1]['position']
                return float(profile_interpolator(np.clip(z, prof_z_min, prof_z_max)))
            else:
                return initial_bore_radius
    else:
        logger.info(f"Estrategia '{part_type}': Mecanizando perfil combinado de Z'=0 a Z'={total_length:.2f}")
        
        def get_stage1_target_radius(z):
            if has_mortise_feature and z < profile_origin_z:
                return profile_start_radius
            elif profile_interpolator:
                return float(profile_interpolator(max(z, profile_origin_z)))
            else:
                return profile_start_radius if has_mortise_feature else initial_bore_radius
    
    def stage1_rough_target_radius(z):
        return get_stage1_target_radius(z) - total_finish_allowance_radial
    
    num_eval_points_stage1 = max(500, int((z_end_stage1 - z_start_stage1) * 5))
    if num_eval_points_stage1 < 2:
        num_eval_points_stage1 = 100
    
    z_eval_stage1 = np.linspace(z_start_stage1, z_end_stage1, num_eval_points_stage1)
    stage1_radii = np.array([get_stage1_target_radius(z) for z in z_eval_stage1])
    
    if not np.all(np.isfinite(stage1_radii)):
        raise ValueError("Cálculo de radios Etapa 1 falló.")
    
    max_stage1_radius = np.max(stage1_radii) if len(stage1_radii) > 0 else initial_bore_radius
    max_rough_stage1_radius = max(
        np.max(stage1_radii) - total_finish_allowance_radial,
        initial_bore_radius
    )
    
    profile_slope = 0.0
    if has_profile and len(profile_measurements) >= 2:
        prof_z = np.array([m['position'] for m in profile_measurements])
        prof_r = np.array([m['diameter'] for m in profile_measurements]) / 2.0
        unique_prof_z, unique_prof_indices = np.unique(prof_z, return_index=True)
        if len(unique_prof_z) >= 2:
            coeffs = np.polyfit(unique_prof_z, prof_r[unique_prof_indices], 1)
            profile_slope = coeffs[0]
            logger.info(f"  Pendiente estimada perfil: {profile_slope:.4f}")
        else:
            logger.info("  Perfil sin suficientes puntos únicos para pendiente.")
    else:
        logger.info("  Sin perfil principal para calcular pendiente.")
    
    if roughing_strategy == "Conical" and profile_slope >= -1e-6:
        logger.warning(f"  ADVERTENCIA: Pendiente ({profile_slope:.4f}) no negativa. Usando desbaste por capas.")
        effective_roughing_strategy = "Layers"
    else:
        effective_roughing_strategy = roughing_strategy
    
    # Inicio del programa G-code
    gcode_lines.append("%")
    gcode_lines.append("O0001 (FLAUTA_{}_INT)".format(part_type.upper()))
    gcode_lines.append("G18 G21")
    gcode_lines.append("G54")
    gcode_lines.append("(OPERACION: TORNEADO INTERIOR ETAPA 1)")
    gcode_lines.append(f"S{int(spindle_speed)} M3")
    gcode_lines.append("M8")
    gcode_lines.append("G0 Z{:.3f}".format(safe_z_start))
    gcode_lines.append(f"\n(--- ETAPA 1: PERFIL INTERNO Z'={z_start_stage1:.3f} a Z'={z_end_stage1:.3f} ---)")
    gcode_lines.append(f"(Radio Max Desbaste: {max_rough_stage1_radius:.3f})")
    gcode_lines.append(f"(Estrategia Desbaste: {effective_roughing_strategy})")
    
    if economy_mode:
        gcode_lines.append("(Modo Economico Activado: Spindle puede parar en retracciones)")
    
    # Desbaste Etapa 1
    if effective_roughing_strategy == "Layers":
        current_roughing_radius = initial_bore_radius
        pass_num = 1
        gcode_lines.append("\n(Desbaste Etapa 1 - Por Segmentos)")
        
        while current_roughing_radius < max_rough_stage1_radius - 1e-6:
            next_roughing_radius = min(
                current_roughing_radius + radial_roughing_step,
                max_rough_stage1_radius
            )
            target_diameter = next_roughing_radius * 2.0
            gcode_lines.append(f"\n(Pasada Desbaste Etapa 1 {pass_num} - R:{next_roughing_radius:.3f})")
            
            rough_target_radii = np.array([stage1_rough_target_radius(z) for z in z_eval_stage1])
            is_valid = rough_target_radii >= next_roughing_radius - 1e-6
            diff = np.diff(is_valid.astype(int), prepend=0, append=0)
            
            start_indices = np.where(diff == 1)[0]
            end_indices = np.where(diff == -1)[0]
            
            if len(start_indices) == 0:
                logger.warning(f"  No se encontraron segmentos Z para R={next_roughing_radius:.3f}")
                break
            
            if is_valid[0] and (start_indices.size == 0 or start_indices[0] != 0):
                start_indices = np.insert(start_indices, 0, 0)
            if is_valid[-1] and (end_indices.size == 0 or end_indices[-1] != len(z_eval_stage1)):
                end_indices = np.append(end_indices, len(z_eval_stage1))
            
            if len(start_indices) != len(end_indices):
                logger.warning(f"Error: Desajuste inicios/fines segmento. Saltando R.")
                current_roughing_radius = next_roughing_radius
                pass_num += 1
                continue
            
            gcode_lines.append(f"  (Procesando {len(start_indices)} segmento(s) Z)")
            gcode_lines.append("    G0 Z{:.3f}".format(safe_z_start))
            spindle_stop_eco(gcode_lines, economy_mode and pass_num > 1, "(Eco Pre-X Seg)")
            gcode_lines.append("    G0 X{:.3f}".format(target_diameter))
            
            for i in range(len(start_indices)):
                start_idx = start_indices[i]
                end_idx = end_indices[i]
                z_start_seg = z_eval_stage1[start_idx]
                z_end_seg = z_eval_stage1[max(0, end_idx - 1)]
                
                if z_end_seg <= z_start_seg + 1e-6:
                    continue
                
                gcode_lines.append(f"    (Segmento {i+1}: Z'={z_start_seg:.3f} a Z'={z_end_seg:.3f})")
                gcode_lines.append("    G0 Z{:.3f}".format(-z_start_seg))
                spindle_start_eco(gcode_lines, economy_mode, "(Eco Pre-Corte Seg)")
                gcode_lines.append(f"    G1 Z{-z_end_seg:.3f} F{roughing_feed_rate:.1f}")
                toolpath_points['stage1']['roughing'].append([
                    (z_start_seg, next_roughing_radius),
                    (z_end_seg, next_roughing_radius)
                ])
                spindle_stop_eco(gcode_lines, economy_mode, "(Eco Post-Corte Seg)")
                gcode_lines.append("    G0 Z{:.3f}".format(safe_z_start))
            
            current_roughing_radius = next_roughing_radius
            pass_num += 1
            if pass_num > 500:
                raise RuntimeError("Demasiadas pasadas desbaste Etapa 1.")
        
        gcode_lines.append("(Fin Desbaste Etapa 1 - Por Segmentos)\n")
        spindle_stop_eco(gcode_lines, economy_mode and pass_num > 1, "(Eco Fin Desbaste)")
        
    elif effective_roughing_strategy == "Conical":
        gcode_lines.append("\n(Desbaste Etapa 1 - Cónico)")
        m = profile_slope
        current_entry_radius = initial_bore_radius
        pass_num = 1
        
        while True:
            next_entry_radius = current_entry_radius + radial_roughing_step
            if abs(m) < 1e-9:
                logger.info("  Pendiente baja para desbaste cónico, usando capas.")
                break
            
            z_end_cono_teorico = z_start_stage1 + (initial_bore_radius - next_entry_radius) / m
            z_end_cono = min(z_end_cono_teorico, z_end_stage1)
            r_end_cono = initial_bore_radius
            
            if z_end_cono < z_end_cono_teorico - 1e-6:
                r_end_cono = m * (z_end_cono - z_start_stage1) + next_entry_radius
            
            if z_end_cono <= z_start_stage1 + 1e-6:
                logger.info(f"  Cono {pass_num} omitido.")
                current_entry_radius = next_entry_radius
                pass_num += 1
                continue
            
            interferes = False
            z_check_points = np.linspace(z_start_stage1, z_end_cono, 20)
            cone_radii_at_check = m * (z_check_points - z_start_stage1) + next_entry_radius
            target_rough_radii_at_check = np.array([
                stage1_rough_target_radius(z) for z in z_check_points
            ])
            
            if np.any(cone_radii_at_check > target_rough_radii_at_check + 1e-6):
                interferes = True
                logger.info(f"  Cono {pass_num} interfiere.")
                break
            
            gcode_lines.append(f"\n(Pasada Desbaste Cónico {pass_num} - R_inicio:{next_entry_radius:.3f})")
            gcode_lines.append(f"  (Cono Z'={z_start_stage1:.3f}, R={next_entry_radius:.3f} -> Z'={z_end_cono:.3f}, R={r_end_cono:.3f})")
            gcode_lines.append("  G0 Z{:.3f}".format(safe_z_start))
            spindle_stop_eco(gcode_lines, economy_mode and pass_num > 1, "(Eco Pre-X Cono)")
            gcode_lines.append("  G0 X{:.3f}".format(next_entry_radius * 2.0))
            gcode_lines.append("  G0 Z{:.3f}".format(-z_start_stage1))
            spindle_start_eco(gcode_lines, economy_mode, "(Eco Pre-Corte Cono)")
            gcode_lines.append(f"  G1 Z{-z_end_cono:.3f} X{r_end_cono * 2.0:.3f} F{roughing_feed_rate:.1f}")
            toolpath_points['stage1']['roughing'].append([
                (z_start_stage1, next_entry_radius),
                (z_end_cono, r_end_cono)
            ])
            gcode_lines.append("  G1 X{:.3f} F{:.1f}".format(initial_bore_diameter, roughing_feed_rate * 2))
            spindle_stop_eco(gcode_lines, economy_mode, "(Eco Post-Corte Cono)")
            gcode_lines.append("  G0 Z{:.3f}".format(safe_z_start))
            
            current_entry_radius = next_entry_radius
            pass_num += 1
            if pass_num > 500:
                raise RuntimeError("Demasiadas pasadas desbaste cónico.")
        
        gcode_lines.append("(Fin Desbaste Etapa 1 - Cónico)\n")
        spindle_stop_eco(gcode_lines, economy_mode and pass_num > 1, "(Eco Fin Desbaste)")
    
    # Acabado Etapa 1
    num_finish_points = max(100, int((z_end_stage1 - z_start_stage1) * 5))
    if num_finish_points < 2:
        num_finish_points = 50
    
    z_finish_coords = np.linspace(z_start_stage1, z_end_stage1, num_finish_points)
    safe_approach_radius = max(initial_bore_radius - safe_x_retract_radial, 0.1)
    retract_dia_bore = params["INITIAL_BORE_DIAMETER"]
    
    # Acabado 1
    gcode_lines.append("(Acabado 1 Etapa 1)")
    allowance1_radial = finish_allowance_2
    finish1_radii = np.array([
        get_stage1_target_radius(z) - allowance1_radial
        for z in z_finish_coords
    ])
    finish1_radii = np.maximum(finish1_radii, initial_bore_radius + 1e-6)
    finish1_diameters = finish1_radii * 2.0
    start_z_finish_actual = z_finish_coords[0]
    start_x_finish1 = finish1_diameters[0]
    
    gcode_lines.append("G0 Z{:.3f}".format(safe_z_start))
    gcode_lines.append("G0 X{:.3f}".format(safe_approach_radius * 2.0))
    gcode_lines.append("G0 Z{:.3f}".format(-start_z_finish_actual))
    gcode_lines.append("G0 X{:.3f}".format(start_x_finish1))
    spindle_start_eco(gcode_lines, economy_mode, "(Eco Pre-Acab1)")
    
    path_segment1 = [(z_finish_coords[0], finish1_radii[0])]
    for i in range(1, num_finish_points):
        gcode_lines.append("G1 Z{:.3f} X{:.3f} F{:.1f}".format(
            -z_finish_coords[i], finish1_diameters[i], finishing_feed_rate
        ))
        path_segment1.append((z_finish_coords[i], finish1_radii[i]))
    
    toolpath_points['stage1']['finish1'].append(path_segment1)
    gcode_lines.append("G1 X{:.3f} F{:.1f}".format(retract_dia_bore, finishing_feed_rate * 2))
    spindle_stop_eco(gcode_lines, economy_mode, "(Eco Post-Acab1)")
    gcode_lines.append("G0 Z{:.3f}".format(safe_z_start))
    gcode_lines.append("(Fin Acabado 1 Etapa 1)\n")
    
    # Acabado 2
    gcode_lines.append("(Acabado 2 Etapa 1 - Repaso)")
    finish2_radii = np.array([get_stage1_target_radius(z) for z in z_finish_coords])
    finish2_radii = np.maximum(finish2_radii, initial_bore_radius + 1e-6)
    finish2_diameters = finish2_radii * 2.0
    start_x_finish2 = finish2_diameters[0]
    
    gcode_lines.append("G0 Z{:.3f}".format(safe_z_start))
    gcode_lines.append("G0 X{:.3f}".format(safe_approach_radius * 2.0))
    gcode_lines.append("G0 Z{:.3f}".format(-start_z_finish_actual))
    gcode_lines.append("G0 X{:.3f}".format(start_x_finish2))
    spindle_start_eco(gcode_lines, economy_mode, "(Eco Pre-Acab2)")
    
    path_segment2 = [(z_finish_coords[0], finish2_radii[0])]
    for i in range(1, num_finish_points):
        gcode_lines.append("G1 Z{:.3f} X{:.3f} F{:.1f}".format(
            -z_finish_coords[i], finish2_diameters[i], finishing_feed_rate
        ))
        path_segment2.append((z_finish_coords[i], finish2_radii[i]))
    
    toolpath_points['stage1']['finish2'].append(path_segment2)
    gcode_lines.append("G1 X{:.3f} F{:.1f}".format(retract_dia_bore, finishing_feed_rate * 2))
    spindle_stop_eco(gcode_lines, economy_mode, "(Eco Post-Acab2)")
    gcode_lines.append("G0 Z{:.3f}".format(safe_z_start))
    gcode_lines.append("(Fin Acabado 2 Etapa 1)\n")
    
    gcode_lines.append("(--- FIN ETAPA 1 ---)\n")
    
    # Etapa 2 (Espiga) si es necesario
    if part_type != "foot":
        profile_start_radius_check = (
            profile_start_diameter / 2.0
            if profile_start_diameter > 1e-6
            else initial_bore_radius
        )
    else:
        profile_start_radius_check = initial_bore_radius
    
    needs_stage2 = (
        has_mortise_feature and
        np.isfinite(mortise_diameter) and
        mortise_diameter / 2.0 > profile_start_radius_check + total_finish_allowance_radial + 1e-6
    )
    
    if part_type != "foot" and needs_stage2:
        gcode_lines.append("(--- PARADA CAMBIO HERRAMIENTA ESPIGA ---)")
        gcode_lines.append("M9")
        gcode_lines.append("M5")
        gcode_lines.append("G0 Z{:.3f}".format(safe_z_start + 30))
        gcode_lines.append("M00 (CAMBIAR A HERRAMIENTA PARA ESPIGA)")
        gcode_lines.append("(Reanudar programa)")
        gcode_lines.append("(--- REANUDAR ---)\n")
        
        gcode_lines.append("(--- ETAPA 2: MECANIZADO FINAL ESPIGA ---)")
        gcode_lines.append(f"(Rango Z: 0.0 a {-mortise_length:.3f})")
        gcode_lines.append(f"(Desde D~{profile_start_diameter:.3f} a D={mortise_diameter:.3f})")
        gcode_lines.append(f"S{int(spindle_speed)} M3")
        gcode_lines.append("M8")
        gcode_lines.append("G0 Z{:.3f}".format(safe_z_start))
        
        mortise_radius = mortise_diameter / 2.0
        start_rough_mortise_radius = profile_start_radius_check
        max_rough_mortise_radius = max(
            mortise_radius - total_finish_allowance_radial,
            start_rough_mortise_radius
        )
        current_roughing_radius = start_rough_mortise_radius
        pass_num = 1
        
        gcode_lines.append("\n(Desbaste Etapa 2 - Espiga)")
        
        while current_roughing_radius < max_rough_mortise_radius - 1e-6:
            next_roughing_radius = min(
                current_roughing_radius + radial_roughing_step,
                max_rough_mortise_radius
            )
            target_diameter = next_roughing_radius * 2.0
            gcode_lines.append(f"\n(Pasada Desbaste Espiga {pass_num} - R:{next_roughing_radius:.3f})")
            
            z_start_cut = 0.0
            z_end_cut = mortise_length
            
            gcode_lines.append("G0 Z{:.3f}".format(safe_z_start))
            spindle_stop_eco(gcode_lines, economy_mode and pass_num > 1, "(Eco Pre-X E2 Desb)")
            gcode_lines.append("G0 X{:.3f}".format(target_diameter))
            gcode_lines.append("G0 Z{:.3f}".format(-z_start_cut))
            spindle_start_eco(gcode_lines, economy_mode, "(Eco Pre-Corte E2 Desb)")
            gcode_lines.append(f"G1 Z{-z_end_cut:.3f} F{roughing_feed_rate:.1f}")
            toolpath_points['stage2']['roughing'].append([
                (z_start_cut, next_roughing_radius),
                (z_end_cut, next_roughing_radius)
            ])
            spindle_stop_eco(gcode_lines, economy_mode, "(Eco Post-Corte E2 Desb)")
            gcode_lines.append("G0 Z{:.3f}".format(safe_z_start))
            
            current_roughing_radius = next_roughing_radius
            pass_num += 1
            if pass_num > 500:
                raise RuntimeError("Demasiadas pasadas desbaste Etapa 2.")
        
        gcode_lines.append("(Fin Desbaste Etapa 2)\n")
        spindle_stop_eco(gcode_lines, economy_mode and pass_num > 1, "(Eco Fin Desb E2)")
        
        z_start_cut = 0.0
        z_end_cut = mortise_length
        safe_approach_radius_stage2 = max(initial_bore_radius - safe_x_retract_radial, 0.1)
        
        # Acabado 1 Etapa 2
        gcode_lines.append("(Acabado 1 Etapa 2)")
        allowance1_radial = finish_allowance_2
        finish1_radius = mortise_radius - allowance1_radial
        finish1_radius = max(finish1_radius, start_rough_mortise_radius + 1e-6)
        finish1_diameter = finish1_radius * 2.0
        
        gcode_lines.append("G0 Z{:.3f}".format(safe_z_start))
        gcode_lines.append("G0 X{:.3f}".format(safe_approach_radius_stage2 * 2.0))
        gcode_lines.append("G0 Z{:.3f}".format(-z_start_cut))
        gcode_lines.append("G0 X{:.3f}".format(finish1_diameter))
        spindle_start_eco(gcode_lines, economy_mode, "(Eco Pre-Acab1 E2)")
        gcode_lines.append(f"G1 Z{-z_end_cut:.3f} F{finishing_feed_rate:.1f}")
        toolpath_points['stage2']['finish1'].append([
            (z_start_cut, finish1_radius),
            (z_end_cut, finish1_radius)
        ])
        gcode_lines.append("G1 X{:.3f} F{:.1f}".format(retract_dia_bore, finishing_feed_rate * 2))
        spindle_stop_eco(gcode_lines, economy_mode, "(Eco Post-Acab1 E2)")
        gcode_lines.append("G0 Z{:.3f}".format(safe_z_start))
        gcode_lines.append("(Fin Acabado 1 Etapa 2)\n")
        
        # Acabado 2 Etapa 2
        gcode_lines.append("(Acabado 2 Etapa 2 - Repaso)")
        finish2_radius = mortise_radius
        finish2_radius = max(finish2_radius, start_rough_mortise_radius + 1e-6)
        finish2_diameter = finish2_radius * 2.0
        
        gcode_lines.append("G0 Z{:.3f}".format(safe_z_start))
        gcode_lines.append("G0 X{:.3f}".format(safe_approach_radius_stage2 * 2.0))
        gcode_lines.append("G0 Z{:.3f}".format(-z_start_cut))
        gcode_lines.append("G0 X{:.3f}".format(finish2_diameter))
        spindle_start_eco(gcode_lines, economy_mode, "(Eco Pre-Acab2 E2)")
        gcode_lines.append(f"G1 Z{-z_end_cut:.3f} F{finishing_feed_rate:.1f}")
        toolpath_points['stage2']['finish2'].append([
            (z_start_cut, finish2_radius),
            (z_end_cut, finish2_radius)
        ])
        gcode_lines.append("G1 X{:.3f} F{:.1f}".format(retract_dia_bore, finishing_feed_rate * 2))
        spindle_stop_eco(gcode_lines, economy_mode, "(Eco Post-Acab2 E2)")
        gcode_lines.append("G0 Z{:.3f}".format(safe_z_start))
        gcode_lines.append("(Fin Acabado 2 Etapa 2)\n")
        
        gcode_lines.append("(--- FIN ETAPA 2 ---)\n")
    elif has_mortise_feature:
        logger.info(f"Etapa 2 (Espiga) omitida: Parte es '{part_type}' o D no requiere mecanizado.")
    elif part_type == "foot":
        logger.info("Etapa 2 (Espiga) omitida por estrategia 'foot'.")
    
    # Fin del programa
    gcode_lines.append("(--- FIN DEL PROGRAMA ---)")
    gcode_lines.append("M9")
    gcode_lines.append("M5")
    gcode_lines.append("G0 Z{:.3f}".format(safe_z_start + 50))
    gcode_lines.append("M30")
    gcode_lines.append("%")
    
    logger.info("Generación de G-code completada.")
    return gcode_lines, toolpath_points

def parse_gcode(filepath: str) -> Tuple[Optional[List], Optional[List]]:
    """
    Lee G-code, extrae movs G0/G1 y devuelve segmentos. Z debería ser NEGATIVO.
    
    Returns:
        Tupla: (g0_segments, g1_segments)
    """
    g0_segments = []
    g1_segments = []
    g_command_re = re.compile(r'G([01])(?:\.\d+)?', re.IGNORECASE)
    x_coord_re = re.compile(r'X(-?\d*\.?\d*)', re.IGNORECASE)
    z_coord_re = re.compile(r'Z(-?\d*\.?\d*)', re.IGNORECASE)
    
    current_x_dia = np.nan
    current_z = np.nan
    current_mode = None
    
    logger.info("\n--- PARSEANDO G-CODE (Z Negativo) PARA GRAFICO 2 ---")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f):
                line = line.strip().upper()
                
                # Strip () comments
                while True:
                    start = line.find('(')
                    if start == -1:
                        break
                    end = line.find(')')
                    if end == -1 or end < start:
                        line = line[:start].strip()
                        break
                    line = line[:start].strip() + " " + line[end+1:].strip()
                    line = line.strip()
                
                # Strip ; comments
                comment_pos = line.find(';')
                if comment_pos != -1:
                    line = line[:comment_pos].strip()
                
                if not line or line.startswith('%') or line.startswith('O'):
                    continue
                
                g_match = g_command_re.search(line)
                x_match = x_coord_re.search(line)
                z_match = z_coord_re.search(line)
                
                if g_match:
                    current_mode = f'G{int(g_match.group(1))}'
                
                if current_mode is None or (not x_match and not z_match):
                    continue
                
                prev_z = current_z
                prev_x_dia = current_x_dia
                new_z = current_z
                new_x_dia = current_x_dia
                updated_z = False
                updated_x = False
                
                next_z_str = z_match.group(1) if z_match else None
                next_x_dia_str = x_match.group(1) if x_match else None
                
                try:
                    if next_z_str is not None:
                        val = next_z_str
                        if val:
                            new_z = float(val)
                            updated_z = True
                    if next_x_dia_str is not None:
                        val = next_x_dia_str
                        if val:
                            new_x_dia = float(val)
                            updated_x = True
                except ValueError:
                    logger.warning(f"Advertencia parse: Valor no numérico L{line_num+1}: '{line}'.")
                    continue
                
                can_plot = not np.isnan(prev_z) and not np.isnan(prev_x_dia)
                coord_changed = (
                    (updated_z and not np.isclose(prev_z, new_z)) or
                    (updated_x and not np.isclose(prev_x_dia, new_x_dia))
                )
                
                current_z = new_z
                current_x_dia = new_x_dia
                
                if can_plot and coord_changed:
                    start_radius = prev_x_dia / 2.0
                    end_radius = current_x_dia / 2.0
                    segment = (prev_z, start_radius, current_z, end_radius)
                    if current_mode == 'G0':
                        g0_segments.append(segment)
                    elif current_mode == 'G1':
                        g1_segments.append(segment)
                elif not can_plot and not np.isnan(current_z) and not np.isnan(current_x_dia):
                    logger.info(f"Parse: Pos inicial G-code Z={current_z:.3f}, X(dia)={current_x_dia:.3f} (L~{line_num+1})")
        
        logger.info("--- PARSING COMPLETE ---")
        return g0_segments, g1_segments
    except FileNotFoundError:
        logger.error(f"Error parse: No se encontró: {filepath}")
        return None, None
    except Exception as e:
        logger.error(f"Error parse: {e}")
        traceback.print_exc()
        return None, None

def plot_intended_paths(
    ax,
    mortise_length: float,
    mortise_diameter: float,
    machine_profile_z: np.ndarray,
    machine_profile_r: np.ndarray,
    toolpath_points: Dict,
    total_length: float,
    params: Dict[str, Any]
):
    """Genera visualización de trayectorias intencionales."""
    initial_bore_diameter_plot = params["INITIAL_BORE_DIAMETER"]
    initial_bore_radius_plot = initial_bore_diameter_plot / 2.0
    
    if not np.isfinite(initial_bore_radius_plot):
        raise ValueError("INITIAL_BORE_DIAMETER inválido.")
    
    ax.clear()
    ax.plot(
        [0, total_length],
        [initial_bore_radius_plot, initial_bore_radius_plot],
        'k--', linewidth=0.8,
        label=f'Agujero Inicial ({initial_bore_diameter_plot}mm Dia)'
    )
    
    plot_z_final = []
    plot_r_final = []
    has_mortise = mortise_length > 1e-6 and mortise_diameter > 1e-6
    mortise_radius_finite = mortise_diameter / 2.0 if np.isfinite(mortise_diameter) else float('inf')
    
    if has_mortise and np.isfinite(mortise_radius_finite):
        plot_z_final.extend([0, mortise_length])
        plot_r_final.extend([mortise_radius_finite, mortise_radius_finite])
    
    if len(machine_profile_z) > 0:
        prof_z = machine_profile_z
        prof_r = machine_profile_r
        if has_mortise and abs(prof_z[0] - mortise_length) > 1e-6:
            logger.info(f"Nota plot1: Gap Z perfil={prof_z[0]:.2f}, Z espiga={mortise_length:.2f}")
        plot_z_final.extend(prof_z)
        plot_r_final.extend(prof_r)
        if (has_mortise and np.isfinite(mortise_radius_finite) and
            len(prof_r) > 0 and np.isfinite(prof_r[0]) and
            abs(prof_z[0] - mortise_length) < 1e-6):
            ax.plot(
                [mortise_length, mortise_length],
                [mortise_radius_finite, prof_r[0]],
                'r-', linewidth=1.5
            )
    
    if len(plot_z_final) > 0:
        finite_indices = np.where(
            np.isfinite(plot_z_final) & np.isfinite(plot_r_final)
        )[0]
        if len(finite_indices) > 0:
            plot_z_final_finite = np.array(plot_z_final)[finite_indices]
            plot_r_final_finite = np.array(plot_r_final)[finite_indices]
            final_points = sorted(zip(plot_z_final_finite, plot_r_final_finite))
            
            if final_points:
                if len(final_points) >= 2:
                    plot_z_final_sorted, plot_r_final_sorted = zip(*final_points)
                    ax.plot(
                        plot_z_final_sorted, plot_r_final_sorted,
                        'ro-', label='Perfil Mecanizado Etapa 1',
                        markersize=3, linewidth=1.5
                    )
                elif len(final_points) == 1:
                    ax.plot(
                        final_points[0][0], final_points[0][1],
                        'ro', label='Perfil Mecanizado Etapa 1',
                        markersize=3
                    )
    
    def plot_valid_paths(paths, color, linestyle, linewidth, alpha, label_prefix):
        first = True
        for path in paths:
            if not isinstance(path, (list, tuple)) or len(path) < 2:
                continue
            try:
                z_vals, r_vals = zip(*path)
                if not all(np.isfinite(z_vals)) or not all(np.isfinite(r_vals)):
                    logger.warning(f"Advertencia plot1: Path NaN/Inf {label_prefix}, omitiendo: {path}")
                    continue
                label = label_prefix if first else None
                ax.plot(
                    z_vals, r_vals,
                    color=color, linestyle=linestyle,
                    linewidth=linewidth, alpha=alpha, label=label
                )
                first = False
            except (ValueError, TypeError) as e:
                logger.warning(f"Advertencia plot1: Error path {label_prefix}: {path}. Error: {e}")
                continue
    
    plot_valid_paths(
        toolpath_points['stage1'].get('roughing', []),
        'cyan', '-', 0.7, 0.7, 'Desbaste Etapa 1'
    )
    plot_valid_paths(
        toolpath_points['stage1'].get('finish1', []),
        'lime', '--', 1.0, 1.0, 'Acabado 1 Etapa 1'
    )
    plot_valid_paths(
        toolpath_points['stage1'].get('finish2', []),
        'magenta', '-', 1.2, 1.0, 'Acabado 2 Etapa 1'
    )
    plot_valid_paths(
        toolpath_points['stage2'].get('roughing', []),
        'blue', '-', 0.7, 0.7, 'Desbaste Etapa 2 (Espiga)'
    )
    plot_valid_paths(
        toolpath_points['stage2'].get('finish1', []),
        'green', '--', 1.0, 1.0, 'Acabado 1 Etapa 2 (Espiga)'
    )
    plot_valid_paths(
        toolpath_points['stage2'].get('finish2', []),
        'purple', '-', 1.2, 1.0, 'Acabado 2 Etapa 2 (Espiga)'
    )
    
    ax.set_xlabel("Posición Z' (mm) - Lógica Interna")
    ax.set_ylabel("Radio (mm)")
    ax.set_title(f"Visualización Trayectorias (INTENCIONAL)")
    
    min_radius_plot = initial_bore_radius_plot - 1.0
    max_radius_data = initial_bore_radius_plot
    
    if len(plot_r_final) > 0 and 'plot_r_final_sorted' in locals() and plot_r_final_sorted:
        valid_r_final = np.array(plot_r_final_sorted)[np.isfinite(plot_r_final_sorted)]
        if len(valid_r_final) > 0:
            max_radius_data = max(max_radius_data, np.max(valid_r_final))
        else:
            logger.warning("Advertencia plot1: Perfil final sin valores finitos para límite Y.")
    
    if has_mortise and mortise_diameter > 0 and np.isfinite(mortise_diameter):
        max_radius_data = max(max_radius_data, mortise_diameter / 2.0)
    
    if not np.isfinite(max_radius_data):
        logger.warning(f"Error plot1: max_radius_data inválido ({max_radius_data}). Usando default.")
        max_radius_data = initial_bore_radius_plot + 10
    
    max_radius_plot = max_radius_data + 1.0
    
    if not (np.isfinite(min_radius_plot) and np.isfinite(max_radius_plot)):
        raise ValueError(f"Límites Y inválidos plot1: min={min_radius_plot}, max={max_radius_plot}")
    if not np.isfinite(total_length):
        raise ValueError(f"total_length inválido plot1: {total_length}")
    
    ax.set_ylim(min_radius_plot, max_radius_plot)
    ax.set_xlim(-5, total_length + 5)
    ax.legend(loc='best', fontsize='small')
    ax.grid(True, linestyle=':', alpha=0.6)

def plot_parsed_gcode(
    ax,
    g0_segments: List,
    g1_segments: List,
    total_length: float,
    params: Dict[str, Any]
):
    """Genera visualización de G0/G1 parseados. Eje Z invertido."""
    initial_bore_diameter_plot = params["INITIAL_BORE_DIAMETER"]
    initial_bore_radius_plot = initial_bore_diameter_plot / 2.0
    
    if not np.isfinite(initial_bore_radius_plot):
        raise ValueError("INITIAL_BORE_DIAMETER inválido.")
    
    ax.clear()
    
    max_neg_z = 0
    safe_z_pos = params["SAFE_Z_START"]
    all_z_coords = [0, safe_z_pos]
    
    for z_start, _, z_end, _ in g0_segments:
        all_z_coords.extend([z_start, z_end])
    for z_start, _, z_end, _ in g1_segments:
        all_z_coords.extend([z_start, z_end])
    
    valid_z = np.array(all_z_coords)[np.isfinite(all_z_coords)]
    if len(valid_z) > 0:
        max_neg_z = min(0, np.min(valid_z))
        safe_z_pos = max(safe_z_pos, np.max(valid_z))
    
    plot_xlim_left = max_neg_z - 5
    plot_xlim_right = safe_z_pos + 5
    
    if not np.isfinite(plot_xlim_left):
        plot_xlim_left = -total_length - 5
    if not np.isfinite(plot_xlim_right):
        plot_xlim_right = 10
    
    ax.plot(
        [plot_xlim_left, plot_xlim_right],
        [initial_bore_radius_plot, initial_bore_radius_plot],
        'k--', linewidth=0.8, label=f'Agujero Inicial'
    )
    
    logger.info("\n--- PLOTTING PARSED G-CODE (Z Negativo en G-code) ---")
    
    g1_plotted = False
    if g1_segments:
        ax.plot([], [], 'b-', label='G1 Parsed (Corte)')
        for i, seg in enumerate(g1_segments):
            z_start, r_start, z_end, r_end = seg
            try:
                ax.plot([z_start, z_end], [r_start, r_end], 'b-', linewidth=1.0)
                g1_plotted = True
            except Exception as e:
                logger.error(f"Error plotting G1 segment {seg}: {e}")
    
    g0_plotted = False
    if g0_segments:
        ax.plot([], [], 'r:', label='G0 Parsed (Rápido)')
        for i, seg in enumerate(g0_segments):
            z_start, r_start, z_end, r_end = seg
            try:
                ax.plot([z_start, z_end], [r_start, r_end], 'r:', linewidth=0.8)
                g0_plotted = True
            except Exception as e:
                logger.error(f"Error plotting G0 segment {seg}: {e}")
    
    logger.info("--- FINISHED PLOTTING PARSED ---")
    
    ax.set_xlabel("Posición Z (mm) - G-Code (Negativo hacia adentro)")
    ax.set_ylabel("Radio (mm)")
    ax.set_title(f"Visualización desde Archivo NC")
    
    all_radii = [initial_bore_radius_plot]
    for _, r_start, _, r_end in g0_segments:
        all_radii.extend([r_start, r_end])
    for _, r_start, _, r_end in g1_segments:
        all_radii.extend([r_start, r_end])
    
    valid_radii = np.array(all_radii)[np.isfinite(all_radii)]
    if len(valid_radii) > 0:
        min_r_data = np.min(valid_radii)
        max_r_data = np.max(valid_radii)
        min_radius_plot = min_r_data - 1.0
        max_radius_plot = max_r_data + 1.0
    else:
        min_radius_plot = initial_bore_radius_plot - 1.0
        max_radius_plot = initial_bore_radius_plot + 10.0
    
    if not (np.isfinite(min_radius_plot) and np.isfinite(max_radius_plot)):
        raise ValueError(f"Límites Y inválidos plot2: min={min_radius_plot}, max={max_radius_plot}")
    if not np.isfinite(total_length):
        raise ValueError(f"total_length inválido plot2: {total_length}")
    
    ax.set_ylim(min_radius_plot, max_radius_plot)
    ax.set_xlim(plot_xlim_left, plot_xlim_right)
    ax.invert_xaxis()
    ax.legend(loc='best', fontsize='small')
    ax.grid(True, linestyle=':', alpha=0.6)

