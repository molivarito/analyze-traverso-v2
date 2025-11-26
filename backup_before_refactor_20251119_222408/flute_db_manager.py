"""
Gestor de base de datos para flautas y análisis acústico.

Proporciona funciones de alto nivel para:
- Insertar datos de flautas desde JSON
- Guardar resultados de cálculos de impedancia
- Consultar datos almacenados
- Detectar si un cálculo ya existe antes de recalcular
"""

import json
import hashlib
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from datetime import datetime

from db_schema import get_database_connection, create_database_schema
from impedance_serializer import ImpedanceSerializer, ImpedanceCache
from constants import FLUTE_PARTS_ORDER
import logging

logger = logging.getLogger(__name__)


class FluteDBManager:
    """Gestor de base de datos para flautas y análisis acústico."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Inicializa el gestor de base de datos.
        
        Args:
            db_path: Ruta al archivo de base de datos. Si es None, usa la ruta por defecto.
        """
        self.db_path = db_path
        if db_path is None:
            from db_schema import DEFAULT_DB_PATH
            self.db_path = DEFAULT_DB_PATH
        
        # Asegurar que la base de datos existe
        create_database_schema(self.db_path)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Obtiene una conexión a la base de datos."""
        return get_database_connection(self.db_path)
    
    def _calculate_params_hash(
        self,
        temperature: float,
        la_frequency: float,
        freq_range_start: float,
        freq_range_end: float,
        freq_range_step: float,
        fing_chart_file: str,
        fing_chart_content: str,
        stopper_offset_m: float,
        embouchure_radius_m: float
    ) -> str:
        """
        Calcula un hash único para los parámetros de cálculo.
        
        Args:
            Parámetros de cálculo.
        
        Returns:
            Hash hexadecimal de los parámetros.
        """
        params_str = (
            f"{temperature:.6f}_{la_frequency:.6f}_"
            f"{freq_range_start:.6f}_{freq_range_end:.6f}_{freq_range_step:.6f}_"
            f"{fing_chart_file}_{fing_chart_content}_"
            f"{stopper_offset_m:.6f}_{embouchure_radius_m:.6f}"
        )
        return hashlib.sha256(params_str.encode()).hexdigest()
    
    def insert_flute_from_json(
        self,
        flute_model: str,
        json_source_path: Optional[str],
        flute_data_dict: Dict[str, Any],
        notes: Optional[List[str]] = None,
        description: Optional[str] = None
    ) -> int:
        """
        Inserta o actualiza una flauta en la base de datos desde datos JSON.
        
        Args:
            flute_model: Nombre del modelo de flauta.
            json_source_path: Ruta al directorio JSON de origen.
            flute_data_dict: Diccionario con datos de la flauta (como en FluteData.data).
            notes: Lista de notas disponibles (opcional).
            description: Descripción de la flauta (opcional).
        
        Returns:
            ID de la flauta en la base de datos.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Verificar si la flauta ya existe
            cursor.execute("SELECT id FROM flutes WHERE flute_model = ?", (flute_model,))
            existing_row = cursor.fetchone()
            
            if existing_row:
                # Actualizar flauta existente
                flute_id = existing_row['id']
                cursor.execute("""
                    UPDATE flutes 
                    SET json_source_path = ?, notes = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    json_source_path,
                    json.dumps(notes) if notes else None,
                    description,
                    flute_id
                ))
            else:
                # Insertar nueva flauta
                cursor.execute("""
                    INSERT INTO flutes 
                    (flute_model, json_source_path, notes, description)
                    VALUES (?, ?, ?, ?)
                """, (
                    flute_model,
                    json_source_path,
                    json.dumps(notes) if notes else None,
                    description
                ))
                flute_id = cursor.lastrowid
            
            if flute_id is None:
                raise ValueError(f"No se pudo obtener el ID de la flauta {flute_model}")
            
            # Insertar geometría de cada parte
            for part_name in FLUTE_PARTS_ORDER:
                if part_name in flute_data_dict:
                    part_data = flute_data_dict[part_name]
                    geometry_json = json.dumps(part_data, ensure_ascii=False)
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO flute_geometry
                        (flute_id, part_name, geometry_json)
                        VALUES (?, ?, ?)
                    """, (flute_id, part_name, geometry_json))
            
            conn.commit()
            logger.info(f"Flauta '{flute_model}' insertada/actualizada en la base de datos (ID: {flute_id})")
            return flute_id
            
        except sqlite3.Error as e:
            logger.error(f"Error insertando flauta en base de datos: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_flute_id(self, flute_model: str) -> Optional[int]:
        """
        Obtiene el ID de una flauta por su nombre.
        
        Args:
            flute_model: Nombre del modelo de flauta.
        
        Returns:
            ID de la flauta o None si no existe.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT id FROM flutes WHERE flute_model = ?", (flute_model,))
            row = cursor.fetchone()
            return row['id'] if row else None
        finally:
            conn.close()
    
    def get_flute_geometry(self, flute_id: int) -> Dict[str, Any]:
        """
        Obtiene la geometría de una flauta.
        
        Args:
            flute_id: ID de la flauta.
        
        Returns:
            Diccionario con la geometría de cada parte.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT part_name, geometry_json
                FROM flute_geometry
                WHERE flute_id = ?
            """, (flute_id,))
            
            geometry = {}
            for row in cursor.fetchall():
                part_name = row['part_name']
                geometry_json = row['geometry_json']
                geometry[part_name] = json.loads(geometry_json)
            
            return geometry
        finally:
            conn.close()
    
    def save_impedance_calculation(
        self,
        flute_id: int,
        temperature: float,
        la_frequency: float,
        freq_range: np.ndarray,
        fing_chart_file: str,
        fing_chart_content: str,
        stopper_offset_m: float,
        embouchure_radius_m: float,
        bore_segments: List[List[Any]],
        side_holes: List[List[Any]],
        combined_measurements: List[Dict[str, float]],
        impedance_results: Dict[str, Any],  # Dict[note, ImpedanceComputation]
        player_type: str = "FLUTE",
        radiation_category: Any = None,  # Puede ser str o dict
        source_location: str = "embouchure",
        interp: bool = True,
        include_pressure_flow: bool = False  # NUEVO: por defecto False para ahorrar espacio
    ) -> int:
        """
        Guarda los resultados de un cálculo de impedancia en la base de datos.
        
        Args:
            flute_id: ID de la flauta.
            temperature: Temperatura en Celsius.
            la_frequency: Frecuencia del La (diapason) en Hz.
            freq_range: Array de frecuencias.
            fing_chart_file: Ruta al archivo de digitaciones.
            fing_chart_content: Contenido del archivo de digitaciones.
            stopper_offset_m: Offset del corcho en metros.
            embouchure_radius_m: Radio de embocadura en metros.
            bore_segments: Segmentos del bore.
            side_holes: Agujeros laterales.
            combined_measurements: Mediciones combinadas.
            impedance_results: Diccionario de resultados por nota.
            player_type: Tipo de player.
            radiation_category: Categoría de radiación.
            source_location: Ubicación de la fuente.
            interp: Si usar interpolación.
        
        Returns:
            ID de los parámetros de cálculo guardados.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Serializar radiation_category si es un diccionario (manejo de compatibilidad)
            # Para nuevos cálculos, radiation_category debería ser None (usa defaults de OpenWind)
            radiation_category_str = None
            if radiation_category is not None:
                radiation_category_str = (
                    json.dumps(radiation_category, ensure_ascii=False) 
                    if isinstance(radiation_category, dict) 
                    else radiation_category
                )
            
            # Calcular hash de parámetros
            freq_range_start = float(freq_range[0]) if len(freq_range) > 0 else 100.0
            freq_range_end = float(freq_range[-1]) if len(freq_range) > 0 else 3000.0
            freq_range_step = float(freq_range[1] - freq_range[0]) if len(freq_range) > 1 else 2.0
            
            calc_hash = self._calculate_params_hash(
                temperature, la_frequency,
                freq_range_start, freq_range_end, freq_range_step,
                fing_chart_file, fing_chart_content,
                stopper_offset_m, embouchure_radius_m
            )
            
            # Verificar si ya existe este cálculo
            cursor.execute("""
                SELECT id FROM impedance_calculation_params
                WHERE flute_id = ? AND calculation_hash = ?
            """, (flute_id, calc_hash))
            
            existing_row = cursor.fetchone()
            if existing_row:
                calc_params_id = existing_row['id']
                logger.info(f"Cálculo existente encontrado (ID: {calc_params_id}), actualizando resultados...")
            else:
                # Insertar parámetros de cálculo
                cursor.execute("""
                    INSERT INTO impedance_calculation_params
                    (flute_id, calculation_hash, temperature, la_frequency,
                     freq_range_start, freq_range_end, freq_range_step,
                     fing_chart_file, fing_chart_content, player_type,
                     radiation_category, source_location, interp,
                     stopper_offset_m, embouchure_radius_m)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    flute_id, calc_hash, temperature, la_frequency,
                    freq_range_start, freq_range_end, freq_range_step,
                    fing_chart_file, fing_chart_content, player_type,
                    radiation_category_str, source_location, int(interp),
                    stopper_offset_m, embouchure_radius_m
                ))
                calc_params_id = cursor.lastrowid
            
            # Guardar geometría del bore
            cursor.execute("""
                INSERT OR REPLACE INTO bore_geometry
                (calculation_params_id, bore_segments_json, combined_measurements_json)
                VALUES (?, ?, ?)
            """, (
                calc_params_id,
                json.dumps(bore_segments, ensure_ascii=False),
                json.dumps(combined_measurements, ensure_ascii=False)
            ))
            
            # Guardar agujeros laterales
            cursor.execute("""
                INSERT OR REPLACE INTO side_holes
                (calculation_params_id, side_holes_json)
                VALUES (?, ?)
            """, (
                calc_params_id,
                json.dumps(side_holes, ensure_ascii=False)
            ))
            
            # Guardar resultados de impedancia por nota
            for note, impedance_obj in impedance_results.items():
                if impedance_obj is None:
                    continue
                
                serialized = ImpedanceSerializer.serialize_impedance(
                    impedance_obj, 
                    include_pressure_flow=include_pressure_flow
                )
                
                cursor.execute("""
                    INSERT OR REPLACE INTO impedance_results
                    (calculation_params_id, note, frequencies_json,
                     impedance_real_json, impedance_imag_json,
                     antiresonance_freqs_json, pressure_flow_data_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    calc_params_id,
                    note,
                    json.dumps(serialized['frequencies'], ensure_ascii=False),
                    json.dumps(serialized['impedance_real'], ensure_ascii=False),
                    json.dumps(serialized['impedance_imag'], ensure_ascii=False),
                    json.dumps(serialized['antiresonance_freqs'], ensure_ascii=False),
                    json.dumps(serialized['pressure_flow_data'], ensure_ascii=False) if serialized['pressure_flow_data'] else None
                ))
            
            conn.commit()
            logger.info(f"Cálculo de impedancia guardado (ID: {calc_params_id}) para flauta ID {flute_id}")
            return calc_params_id
            
        except sqlite3.Error as e:
            logger.error(f"Error guardando cálculo de impedancia: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def find_existing_calculation(
        self,
        flute_id: int,
        temperature: float,
        la_frequency: float,
        freq_range: np.ndarray,
        fing_chart_file: str,
        fing_chart_content: str,
        stopper_offset_m: float,
        embouchure_radius_m: float
    ) -> Optional[int]:
        """
        Busca si ya existe un cálculo con los mismos parámetros.
        
        Primero intenta buscar por hash exacto, luego por parámetros principales
        (flute_id, temperature, la_frequency) si no encuentra por hash.
        
        Args:
            Parámetros de cálculo.
        
        Returns:
            ID de los parámetros de cálculo si existe, None en caso contrario.
        """
        calc_hash = self._calculate_params_hash(
            temperature, la_frequency,
            float(freq_range[0]) if len(freq_range) > 0 else 100.0,
            float(freq_range[-1]) if len(freq_range) > 0 else 3000.0,
            float(freq_range[1] - freq_range[0]) if len(freq_range) > 1 else 2.0,
            fing_chart_file, fing_chart_content,
            stopper_offset_m, embouchure_radius_m
        )
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Primero buscar por hash exacto
            cursor.execute("""
                SELECT id FROM impedance_calculation_params
                WHERE flute_id = ? AND calculation_hash = ?
            """, (flute_id, calc_hash))
            
            row = cursor.fetchone()
            if row:
                logger.debug(f"✓ Cálculo existente encontrado por hash (ID: {row['id']}, hash: {calc_hash[:16]}...)")
                return row['id']
            
            # Si no se encuentra por hash, buscar por parámetros principales
            # (esto es más flexible y permite encontrar cálculos aunque haya pequeñas diferencias)
            logger.debug(f"No se encontró por hash exacto, buscando por parámetros principales...")
            cursor.execute("""
                SELECT id, calculation_hash, temperature, la_frequency, 
                       freq_range_start, freq_range_end, freq_range_step
                FROM impedance_calculation_params
                WHERE flute_id = ? 
                  AND ABS(temperature - ?) < 0.01
                  AND ABS(la_frequency - ?) < 0.01
                  AND ABS(freq_range_start - ?) < 0.1
                  AND ABS(freq_range_end - ?) < 0.1
                  AND ABS(freq_range_step - ?) < 0.01
            """, (
                flute_id,
                temperature,
                la_frequency,
                float(freq_range[0]) if len(freq_range) > 0 else 100.0,
                float(freq_range[-1]) if len(freq_range) > 0 else 3000.0,
                float(freq_range[1] - freq_range[0]) if len(freq_range) > 1 else 2.0
            ))
            
            rows = cursor.fetchall()
            if rows:
                # Si hay múltiples, tomar el más reciente (mayor ID)
                row = max(rows, key=lambda r: r['id'])
                logger.info(f"✓ Cálculo existente encontrado por parámetros principales (ID: {row['id']}, temp={row['temperature']}, la={row['la_frequency']})")
                return row['id']
            else:
                # Buscar todos los cálculos para esta flauta para debug
                cursor.execute("""
                    SELECT id, calculation_hash, temperature, la_frequency 
                    FROM impedance_calculation_params
                    WHERE flute_id = ?
                """, (flute_id,))
                all_calcs = cursor.fetchall()
                logger.debug(f"No se encontró cálculo para flute_id {flute_id} con temp={temperature}, la={la_frequency}")
                if all_calcs:
                    logger.debug(f"  Cálculos existentes para esta flauta: {[(c['id'], c['temperature'], c['la_frequency']) for c in all_calcs]}")
            return None
        finally:
            conn.close()
    
    def load_impedance_results(
        self,
        calc_params_id: int
    ) -> Dict[str, ImpedanceCache]:
        """
        Carga los resultados de impedancia desde la base de datos.
        
        Args:
            calc_params_id: ID de los parámetros de cálculo.
        
        Returns:
            Diccionario de ImpedanceCache por nota.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT note, frequencies_json, impedance_real_json,
                       impedance_imag_json, antiresonance_freqs_json,
                       pressure_flow_data_json
                FROM impedance_results
                WHERE calculation_params_id = ?
            """, (calc_params_id,))
            
            results = {}
            for row in cursor.fetchall():
                note = row['note']
                serialized_data = {
                    'frequencies': json.loads(row['frequencies_json']),
                    'impedance_real': json.loads(row['impedance_real_json']),
                    'impedance_imag': json.loads(row['impedance_imag_json']),
                    'antiresonance_freqs': json.loads(row['antiresonance_freqs_json']) if row['antiresonance_freqs_json'] else [],
                    'pressure_flow_data': json.loads(row['pressure_flow_data_json']) if row['pressure_flow_data_json'] else None
                }
                results[note] = ImpedanceCache(serialized_data=serialized_data)
            
            return results
        finally:
            conn.close()
    
    def get_calculation_params(self, calc_params_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene los parámetros de un cálculo.
        
        Args:
            calc_params_id: ID de los parámetros de cálculo.
        
        Returns:
            Diccionario con los parámetros o None si no existe.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM impedance_calculation_params
                WHERE id = ?
            """, (calc_params_id,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        finally:
            conn.close()
    
    def save_external_geometry(
        self,
        flute_id: int,
        part_name: str,
        external_measurements: List[Dict[str, float]],
        source_type: str = 'measured'
    ) -> int:
        """
        Guarda geometría externa medida para una parte de la flauta.
        
        Args:
            flute_id: ID de la flauta.
            part_name: Nombre de la parte ('headjoint', 'left', 'right', 'foot').
            external_measurements: Lista de mediciones externas [{'position': float, 'external_diameter': float}].
            source_type: Tipo de fuente ('measured' o 'parametric').
        
        Returns:
            ID del registro creado/actualizado.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            external_measurements_json = json.dumps(external_measurements, ensure_ascii=False)
            
            cursor.execute("""
                INSERT OR REPLACE INTO external_geometry
                (flute_id, part_name, external_measurements_json, source_type, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (flute_id, part_name, external_measurements_json, source_type))
            
            external_geom_id = cursor.lastrowid
            conn.commit()
            logger.debug(f"Geometría externa guardada para flute_id {flute_id}, parte {part_name}")
            return external_geom_id
        except sqlite3.Error as e:
            logger.error(f"Error guardando geometría externa: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_external_geometry(self, flute_id: int, part_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene geometría externa para una flauta.
        
        Args:
            flute_id: ID de la flauta.
            part_name: Nombre de la parte (opcional). Si es None, retorna todas las partes.
        
        Returns:
            Diccionario con geometría externa por parte, o de una parte específica.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if part_name:
                cursor.execute("""
                    SELECT part_name, external_measurements_json, source_type
                    FROM external_geometry
                    WHERE flute_id = ? AND part_name = ?
                """, (flute_id, part_name))
            else:
                cursor.execute("""
                    SELECT part_name, external_measurements_json, source_type
                    FROM external_geometry
                    WHERE flute_id = ?
                """, (flute_id,))
            
            results = {}
            for row in cursor.fetchall():
                part = row['part_name']
                results[part] = {
                    'measurements': json.loads(row['external_measurements_json']),
                    'source_type': row['source_type']
                }
            
            return results if not part_name else (results.get(part_name) if results else None)
        finally:
            conn.close()
    
    def save_external_geometry_parameters(
        self,
        flute_id: int,
        part_name: str,
        wall_thickness_type: str = 'constant',
        wall_thickness_mm: Optional[float] = None,
        wall_thickness_profile: Optional[List[Dict[str, float]]] = None,
        smoothing_factor: float = 1.0
    ) -> int:
        """
        Guarda parámetros de modelo paramétrico para geometría externa.
        
        Args:
            flute_id: ID de la flauta.
            part_name: Nombre de la parte.
            wall_thickness_type: Tipo de espesor ('constant', 'variable', 'proportional').
            wall_thickness_mm: Espesor constante en mm (para 'constant').
            wall_thickness_profile: Perfil de espesor variable [{'position': float, 'thickness': float}].
            smoothing_factor: Factor de suavizado para transiciones.
        
        Returns:
            ID del registro creado/actualizado.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            wall_thickness_profile_json = json.dumps(wall_thickness_profile, ensure_ascii=False) if wall_thickness_profile else None
            
            cursor.execute("""
                INSERT OR REPLACE INTO external_geometry_parameters
                (flute_id, part_name, wall_thickness_type, wall_thickness_mm,
                 wall_thickness_profile_json, smoothing_factor, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                flute_id,
                part_name,
                wall_thickness_type,
                wall_thickness_mm,
                wall_thickness_profile_json,
                smoothing_factor
            ))
            
            param_id = cursor.lastrowid
            conn.commit()
            logger.debug(f"Parámetros de geometría externa guardados para flute_id {flute_id}, parte {part_name}")
            return param_id
        except sqlite3.Error as e:
            logger.error(f"Error guardando parámetros de geometría externa: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_external_geometry_parameters(
        self,
        flute_id: int,
        part_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Obtiene parámetros de modelo paramétrico para geometría externa.
        
        Args:
            flute_id: ID de la flauta.
            part_name: Nombre de la parte (opcional). Si es None, retorna todas las partes.
        
        Returns:
            Diccionario con parámetros por parte, o de una parte específica.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if part_name:
                cursor.execute("""
                    SELECT part_name, wall_thickness_type, wall_thickness_mm,
                           wall_thickness_profile_json, smoothing_factor
                    FROM external_geometry_parameters
                    WHERE flute_id = ? AND part_name = ?
                """, (flute_id, part_name))
            else:
                cursor.execute("""
                    SELECT part_name, wall_thickness_type, wall_thickness_mm,
                           wall_thickness_profile_json, smoothing_factor
                    FROM external_geometry_parameters
                    WHERE flute_id = ?
                """, (flute_id,))
            
            results = {}
            for row in cursor.fetchall():
                part = row['part_name']
                results[part] = {
                    'wall_thickness_type': row['wall_thickness_type'],
                    'wall_thickness_mm': row['wall_thickness_mm'],
                    'wall_thickness_profile': json.loads(row['wall_thickness_profile_json']) if row['wall_thickness_profile_json'] else None,
                    'smoothing_factor': row['smoothing_factor']
                }
            
            return results if not part_name else (results.get(part_name) if results else None)
        finally:
            conn.close()
    
    def list_flutes(self) -> List[Dict[str, Any]]:
        """
        Lista todas las flautas en la base de datos.
        
        Returns:
            Lista de diccionarios con información de cada flauta.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, flute_model, json_source_path, created_at, updated_at, notes, description
                FROM flutes
                ORDER BY flute_model
            """)
            
            flutes = []
            for row in cursor.fetchall():
                flutes.append({
                    'id': row['id'],
                    'flute_model': row['flute_model'],
                    'json_source_path': row['json_source_path'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'notes': json.loads(row['notes']) if row['notes'] else [],
                    'description': row['description']
                })
            
            return flutes
        finally:
            conn.close()
    
    def delete_flute(self, flute_id: int) -> bool:
        """
        Elimina una flauta y todos sus datos relacionados de la base de datos.
        
        Args:
            flute_id: ID de la flauta a eliminar.
        
        Returns:
            True si se eliminó exitosamente, False en caso contrario.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Verificar que la flauta existe
            cursor.execute("SELECT id FROM flutes WHERE id = ?", (flute_id,))
            if not cursor.fetchone():
                logger.warning(f"Flauta con ID {flute_id} no existe")
                return False
            
            # Eliminar en orden (respetando foreign keys)
            # 1. Eliminar resultados de impedancia (a través de calculation_params)
            cursor.execute("""
                DELETE FROM impedance_results 
                WHERE calculation_params_id IN (
                    SELECT id FROM impedance_calculation_params WHERE flute_id = ?
                )
            """, (flute_id,))
            
            # 2. Eliminar geometría del bore y agujeros laterales
            cursor.execute("""
                DELETE FROM bore_geometry 
                WHERE calculation_params_id IN (
                    SELECT id FROM impedance_calculation_params WHERE flute_id = ?
                )
            """, (flute_id,))
            
            cursor.execute("""
                DELETE FROM side_holes 
                WHERE calculation_params_id IN (
                    SELECT id FROM impedance_calculation_params WHERE flute_id = ?
                )
            """, (flute_id,))
            
            # 3. Eliminar parámetros de cálculo
            cursor.execute("DELETE FROM impedance_calculation_params WHERE flute_id = ?", (flute_id,))
            
            # 4. Eliminar geometría externa
            cursor.execute("DELETE FROM external_geometry WHERE flute_id = ?", (flute_id,))
            cursor.execute("DELETE FROM external_geometry_parameters WHERE flute_id = ?", (flute_id,))
            
            # 5. Eliminar geometría de flauta
            cursor.execute("DELETE FROM flute_geometry WHERE flute_id = ?", (flute_id,))
            
            # 6. Eliminar la flauta
            cursor.execute("DELETE FROM flutes WHERE id = ?", (flute_id,))
            
            conn.commit()
            logger.info(f"Flauta ID {flute_id} eliminada exitosamente")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Error eliminando flauta ID {flute_id}: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_database_statistics(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas generales de la base de datos.
        
        Returns:
            Diccionario con estadísticas de la BD.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        try:
            # Tamaño total del archivo
            if self.db_path.exists():
                stats['total_size_mb'] = self.db_path.stat().st_size / (1024 * 1024)
                stats['total_size_gb'] = stats['total_size_mb'] / 1024
            else:
                stats['total_size_mb'] = 0
                stats['total_size_gb'] = 0
            
            # Contar flautas
            cursor.execute("SELECT COUNT(*) FROM flutes")
            stats['total_flutes'] = cursor.fetchone()[0]
            
            # Contar cálculos
            cursor.execute("SELECT COUNT(*) FROM impedance_calculation_params")
            stats['total_calculations'] = cursor.fetchone()[0]
            
            # Contar resultados de impedancia
            cursor.execute("SELECT COUNT(*) FROM impedance_results")
            stats['total_impedance_results'] = cursor.fetchone()[0]
            
            # Contar resultados con pressure_flow_data
            cursor.execute("""
                SELECT COUNT(*) FROM impedance_results 
                WHERE pressure_flow_data_json IS NOT NULL
            """)
            stats['results_with_pressure_flow'] = cursor.fetchone()[0]
            
            # Tamaño de pressure_flow_data
            cursor.execute("""
                SELECT SUM(LENGTH(pressure_flow_data_json)) 
                FROM impedance_results 
                WHERE pressure_flow_data_json IS NOT NULL
            """)
            pf_size = cursor.fetchone()[0]
            stats['pressure_flow_size_mb'] = (pf_size or 0) / (1024 * 1024)
            
            # Contar geometría externa
            cursor.execute("SELECT COUNT(*) FROM external_geometry")
            stats['total_external_geometry'] = cursor.fetchone()[0]
            
            # Contar geometría de flauta
            cursor.execute("SELECT COUNT(*) FROM flute_geometry")
            stats['total_flute_geometry'] = cursor.fetchone()[0]
            
            # Tamaño por tabla (aproximado)
            tables = [
                'flutes', 'flute_geometry', 'impedance_calculation_params',
                'bore_geometry', 'side_holes', 'impedance_results',
                'external_geometry', 'external_geometry_parameters'
            ]
            
            stats['table_sizes'] = {}
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    stats['table_sizes'][table] = count
                except Exception as e:
                    logger.debug(f"Error obteniendo tamaño de tabla {table}: {e}")
                    stats['table_sizes'][table] = 0
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de BD: {e}")
        finally:
            conn.close()
        
        return stats
    
    def get_flute_list(self) -> List[Dict[str, Any]]:
        """
        Retorna lista simplificada de flautas para selección.
        
        Returns:
            Lista de diccionarios con id y nombre de flauta.
        """
        flutes = self.list_flutes()
        return [{'id': f['id'], 'name': f['flute_model']} for f in flutes]

