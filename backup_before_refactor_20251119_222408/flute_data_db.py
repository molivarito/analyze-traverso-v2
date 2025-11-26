"""
FluteDataDB: Extensión de FluteData que usa base de datos para almacenar y recuperar
resultados de análisis acústico sin necesidad de recalcular.

Esta clase mantiene compatibilidad con FluteData pero:
- Guarda resultados de cálculo en la base de datos
- Carga resultados desde la base de datos si existen
- Recalcula automáticamente si los parámetros cambian
"""

from pathlib import Path
from typing import Optional, Dict, Any, Union, List
import json
import numpy as np
import logging

# Importar openwind de manera robusta (igual que en flute_data.py)
try:
    from openwind import Player, ImpedanceComputation  # type: ignore
except ImportError as e:
    raise ImportError(
        "El módulo 'openwind' no está instalado. "
        "Por favor, instálalo usando: pip install openwind"
    ) from e

from flute_data import FluteData, FluteDataInitializationError, DEFAULT_FING_CHART_PATH
from flute_db_manager import FluteDBManager
from impedance_serializer import ImpedanceCache, CachedImpedanceComputation
from constants import FLUTE_PARTS_ORDER
from external_geometry_modeler import (
    ParametricExternalGeometry,
    load_external_geometry_from_json
)

logger = logging.getLogger(__name__)


class FluteDataDB(FluteData):
    """
    Extensión de FluteData que usa base de datos para cachear resultados.
    
    Mantiene la misma interfaz que FluteData pero:
    - Guarda resultados en BD después de calcular
    - Carga resultados desde BD si existen
    - Recalcula solo si los parámetros cambian
    """
    
    def __init__(
        self,
        source: Union[str, Dict[str, Any]],
        source_name: Optional[str] = None,
        notion_token: Optional[str] = None,
        database_id: Optional[str] = None,
        fing_chart_file: str = None,  # Se hereda de FluteData
        temperature: float = 20,
        la_frequency: float = 415.0,
        skip_acoustic_analysis: bool = False,
        db_path: Optional[Path] = None,
        force_recalculate: bool = False,
        db_manager: Optional['FluteDBManager'] = None,  # Permitir pasar un DB Manager existente
        include_pressure_flow: bool = False  # Controlar si se guardan datos de presión/flujo
    ):
        """
        Inicializa FluteDataDB.
        
        Args:
            source: Fuente de datos (ruta o diccionario).
            source_name: Nombre de la flauta (opcional).
            notion_token: Token de Notion (opcional).
            database_id: ID de base de datos de Notion (opcional).
            fing_chart_file: Ruta al archivo de digitaciones.
            temperature: Temperatura en Celsius.
            la_frequency: Frecuencia del La (diapason) en Hz.
            skip_acoustic_analysis: Si True, no calcula análisis acústico.
            db_path: Ruta a la base de datos (opcional).
            force_recalculate: Si True, fuerza recálculo incluso si existe en BD.
            db_manager: Gestor de BD existente (opcional). Si es None, intenta crear uno.
            include_pressure_flow: Si True, guarda datos de presión/flujo en BD (aumenta tamaño significativamente).
        """
        # Inicializar gestor de base de datos
        if db_manager is not None:
            self.db_manager = db_manager
        else:
            try:
                self.db_manager = FluteDBManager(db_path)
            except Exception as e:
                logger.warning(f"No se pudo inicializar DB Manager: {e}. Funcionando sin caché.")
                self.db_manager = None
        
        self.force_recalculate = force_recalculate
        self.include_pressure_flow = include_pressure_flow  # Guardar preferencia
        self._calc_params_id: Optional[int] = None
        self.source = source  # Guardar source para uso posterior
        
        # Si fing_chart_file es None, usar el valor por defecto de FluteData
        if fing_chart_file is None:
            fing_chart_file = DEFAULT_FING_CHART_PATH
        
        # Si la fuente es un string (ruta JSON), verificar si la flauta ya existe en BD
        # y cargar la posición del corcho guardada ANTES de validar
        stopper_pos_from_db = None
        if isinstance(source, str):
            source_path = Path(source)
            # Intentar obtener el nombre de la flauta desde el directorio o source_name
            flute_name_for_lookup = source_name or source_path.name
            existing_flute_id = self.db_manager.get_flute_id(flute_name_for_lookup)
            if existing_flute_id is not None:
                # Cargar geometría existente para obtener posición del corcho
                existing_geometry = self.db_manager.get_flute_geometry(existing_flute_id)
                headjoint_data_existing = existing_geometry.get(FLUTE_PARTS_ORDER[0], {})
                if '_calculated_stopper_absolute_position_mm' in headjoint_data_existing:
                    stopper_pos_from_db = headjoint_data_existing['_calculated_stopper_absolute_position_mm']
                    # Cargar los datos JSON y inyectar la posición del corcho
                    import json
                    temp_data = {}
                    for part in FLUTE_PARTS_ORDER:
                        json_file = source_path / f"{part}.json"
                        if json_file.exists():
                            with open(json_file, 'r', encoding='utf-8') as f:
                                temp_data[part] = json.load(f)
                    # Inyectar la posición del corcho guardada
                    if FLUTE_PARTS_ORDER[0] in temp_data:
                        temp_data[FLUTE_PARTS_ORDER[0]]['_calculated_stopper_absolute_position_mm'] = stopper_pos_from_db
                        source = temp_data  # Usar el diccionario modificado en lugar de la ruta
                        logger.debug(f"Usando posición del corcho desde BD para {flute_name_for_lookup}: {stopper_pos_from_db:.2f}mm")
        
        # Llamar al constructor de FluteData pero saltar el análisis acústico inicial
        # Lo haremos después de verificar la base de datos
        super().__init__(
            source=source,
            source_name=source_name,
            notion_token=notion_token,
            database_id=database_id,
            fing_chart_file=fing_chart_file,
            temperature=temperature,
            la_frequency=la_frequency,
            skip_acoustic_analysis=True  # Saltamos el cálculo inicial
        )
        
        # Guardar geometría en la base de datos si no existe (solo si hay DB Manager)
        if self.db_manager is not None:
            logger.info(f"[{self.flute_model}] Guardando geometría en BD...")
            self._save_geometry_to_db(source if isinstance(source, str) else None)
            logger.info(f"[{self.flute_model}] Geometría guardada en BD")
        else:
            logger.info(f"[{self.flute_model}] Sin DB Manager, saltando guardado en BD")
        
        # Cargar o generar geometría externa
        logger.info(f"[{self.flute_model}] Cargando/generando geometría externa...")
        self._load_or_generate_external_geometry()
        logger.info(f"[{self.flute_model}] Geometría externa lista")
        
        # Ahora intentar cargar o calcular análisis acústico
        if not skip_acoustic_analysis and not self.validation_errors:
            logger.info(f"[{self.flute_model}] Cargando/calculando análisis acústico...")
            self._load_or_compute_acoustic_analysis(temperature, la_frequency)
            logger.info(f"[{self.flute_model}] Análisis acústico listo")
    
    def _save_geometry_to_db(self, json_source_path: Optional[str]) -> None:
        """
        Guarda la geometría de la flauta en la base de datos.
        Si la flauta ya existe en BD, carga la posición del corcho guardada para mantener consistencia.
        
        Args:
            json_source_path: Ruta al directorio JSON de origen.
        """
        if self.db_manager is None:
            logger.debug(f"[{self.flute_model}] Sin DB Manager, saltando guardado de geometría")
            return
        
        try:
            # Verificar si la flauta ya existe en BD
            existing_flute_id = self.db_manager.get_flute_id(self.flute_model)
            
            notes_list = list(self.finger_frequencies.keys()) if self.finger_frequencies else None
            self._flute_db_id = self.db_manager.insert_flute_from_json(
                flute_model=self.flute_model,
                json_source_path=json_source_path,
                flute_data_dict=self.data,
                notes=notes_list,
                description=None
            )
            
            # Si la flauta ya existía, cargar la posición del corcho guardada para mantener consistencia
            if existing_flute_id is not None and existing_flute_id == self._flute_db_id:
                existing_geometry = self.db_manager.get_flute_geometry(self._flute_db_id)
                headjoint_data_existing = existing_geometry.get(FLUTE_PARTS_ORDER[0], {})
                if '_calculated_stopper_absolute_position_mm' in headjoint_data_existing:
                    # Usar la posición del corcho guardada en BD
                    self.data[FLUTE_PARTS_ORDER[0]]['_calculated_stopper_absolute_position_mm'] = headjoint_data_existing['_calculated_stopper_absolute_position_mm']
                    logger.debug(f"Usando posición del corcho guardada en BD para {self.flute_model}: {headjoint_data_existing['_calculated_stopper_absolute_position_mm']:.2f}mm")
            
            logger.info(f"Geometría de '{self.flute_model}' guardada en BD (ID: {self._flute_db_id})")
        except Exception as e:
            logger.error(f"Error guardando geometría en BD: {e}", exc_info=True)
            self._flute_db_id = None
    
    def _load_or_generate_external_geometry(self) -> None:
        """
        Carga geometría externa desde BD o JSON, o la genera usando modelo paramétrico.
        Almacena la geometría externa en self.external_geometry como diccionario por parte.
        """
        if self._flute_db_id is None:
            logger.debug(f"No hay ID de BD para {self.flute_model}, generando geometría externa sin guardar...")
            self._generate_external_geometry()
            return
        
        # Inicializar diccionario de geometría externa
        if not hasattr(self, 'external_geometry'):
            self.external_geometry: Dict[str, List[Dict[str, float]]] = {}
        
        # Intentar cargar desde BD
        external_geom_from_db = self.db_manager.get_external_geometry(self._flute_db_id)
        
        for part_name in FLUTE_PARTS_ORDER:
            if part_name in external_geom_from_db:
                # Cargar desde BD
                self.external_geometry[part_name] = external_geom_from_db[part_name]['measurements']
                logger.debug(f"Geometría externa cargada desde BD para {self.flute_model}, parte {part_name}")
            else:
                # Intentar cargar desde archivo *_external.json
                external_measurements = None
                if isinstance(self.source, (str, Path)):
                    source_path = Path(self.source)
                    if source_path.is_dir():
                        external_file = source_path / f"{part_name}_external.json"
                        if external_file.exists():
                            import json
                            try:
                                with open(external_file, 'r', encoding='utf-8') as f:
                                    external_data = json.load(f)
                                    if "measurements" in external_data:
                                        external_measurements = [
                                            {"position": m["position"], "external_diameter": m["diameter"]}
                                            for m in external_data["measurements"]
                                        ]
                                        logger.info(f"Geometría externa cargada desde {external_file}")
                            except Exception as e:
                                logger.error(f"Error cargando {external_file}: {e}")
                
                # Si no se encontró archivo externo, intentar desde part_data (legacy)
                if not external_measurements:
                    part_data = self.data.get(part_name, {})
                    external_measurements = load_external_geometry_from_json(part_data)
                
                if external_measurements:
                    # Guardar en BD
                    self.db_manager.save_external_geometry(
                        flute_id=self._flute_db_id,
                        part_name=part_name,
                        external_measurements=external_measurements,
                        source_type='measured'
                    )
                    self.external_geometry[part_name] = external_measurements
                    logger.info(f"Geometría externa guardada en BD para {self.flute_model}, parte {part_name}")
                else:
                    # Generar usando modelo paramétrico
                    self._generate_external_geometry_for_part(part_name)
    
    def _generate_external_geometry_for_part(self, part_name: str) -> None:
        """
        Genera geometría externa paramétrica para una parte específica.
        
        Args:
            part_name: Nombre de la parte.
        """
        part_data = self.data.get(part_name, {})
        measurements = part_data.get("measurements", [])
        
        if not measurements:
            logger.warning(f"No hay mediciones internas para generar geometría externa de {part_name} en {self.flute_model}")
            return
        
        # Obtener parámetros de modelo paramétrico desde BD o usar defaults
        params = self.db_manager.get_external_geometry_parameters(self._flute_db_id, part_name)
        
        if params:
            wall_thickness_type = params['wall_thickness_type']
            wall_thickness_mm = params['wall_thickness_mm']
            wall_thickness_profile = params['wall_thickness_profile']
            smoothing_factor = params['smoothing_factor']
        else:
            # Usar valores por defecto
            wall_thickness_type = 'constant'
            wall_thickness_mm = 2.0  # 2mm por defecto
            wall_thickness_profile = None
            smoothing_factor = 1.0
        
        # Generar geometría externa
        try:
            modeler = ParametricExternalGeometry(
                internal_measurements=measurements,
                wall_thickness_type=wall_thickness_type,
                wall_thickness_mm=wall_thickness_mm,
                wall_thickness_profile=wall_thickness_profile,
                smoothing_factor=smoothing_factor
            )
            external_measurements = modeler.generate_external_profile()
            
            # Guardar en BD
            if self._flute_db_id:
                self.db_manager.save_external_geometry(
                    flute_id=self._flute_db_id,
                    part_name=part_name,
                    external_measurements=external_measurements,
                    source_type='parametric'
                )
                # Guardar parámetros también
                self.db_manager.save_external_geometry_parameters(
                    flute_id=self._flute_db_id,
                    part_name=part_name,
                    wall_thickness_type=wall_thickness_type,
                    wall_thickness_mm=wall_thickness_mm,
                    wall_thickness_profile=wall_thickness_profile,
                    smoothing_factor=smoothing_factor
                )
            
            if not hasattr(self, 'external_geometry'):
                self.external_geometry = {}
            self.external_geometry[part_name] = external_measurements
            logger.info(f"Geometría externa paramétrica generada y guardada para {self.flute_model}, parte {part_name}")
        except Exception as e:
            logger.error(f"Error generando geometría externa para {part_name} en {self.flute_model}: {e}", exc_info=True)
    
    def _generate_external_geometry(self) -> None:
        """
        Genera geometría externa paramétrica para todas las partes.
        """
        if not hasattr(self, 'external_geometry'):
            self.external_geometry = {}
        
        for part_name in FLUTE_PARTS_ORDER:
            self._generate_external_geometry_for_part(part_name)
    
    def _load_or_compute_acoustic_analysis(self, temperature: float, la_frequency: float) -> None:
        """
        Carga análisis acústico desde BD o lo calcula si no existe.
        
        Args:
            temperature: Temperatura en Celsius.
            la_frequency: Frecuencia del La (diapason) en Hz.
        """
        if self.validation_errors or not self.combined_measurements:
            logger.warning(f"No se puede cargar/calcular análisis acústico para {self.flute_model} debido a errores de validación.")
            return
        
        # Si no hay DB Manager, calcular directamente sin intentar cargar desde BD
        if self.db_manager is None:
            logger.info(f"[{self.flute_model}] Sin DB Manager, calculando análisis acústico directamente...")
            self._compute_and_save_acoustic_analysis(temperature, la_frequency)
            return
        
        if self._flute_db_id is None:
            logger.warning(f"No hay ID de BD para {self.flute_model}, calculando sin guardar...")
            self._compute_and_save_acoustic_analysis(temperature, la_frequency)
            return
        
        # Preparar parámetros para buscar cálculo existente
        freq_range = np.arange(100, 3000, 2.0)  # Rango completo para análisis detallado de impedancia
        headjoint_data = self.data.get(FLUTE_PARTS_ORDER[0], {})
        stopper_offset_m = headjoint_data.get('_calculated_stopper_absolute_position_mm', 0.0) / 1000.0
        
        emb_hole_diameters = headjoint_data.get("Holes diameter", [])
        Rw = 0.006
        if emb_hole_diameters and emb_hole_diameters[0] > 0:
            Rw = (emb_hole_diameters[0] / 2.0) / 1000.0
        
        # Leer contenido del archivo de digitaciones
        fing_chart_content = ""
        try:
            if self.fing_chart_file_path:
                with open(self.fing_chart_file_path, 'r', encoding='utf-8') as f:
                    fing_chart_content = f.read()
        except Exception as e:
            logger.warning(f"Error leyendo archivo de digitaciones: {e}")
        
        # Buscar cálculo existente
        if not self.force_recalculate:
            logger.info(f"Buscando cálculo existente para {self.flute_model} (flute_id={self._flute_db_id}, temp={temperature}, la={la_frequency})...")
            existing_calc_id = self.db_manager.find_existing_calculation(
                flute_id=self._flute_db_id,
                temperature=temperature,
                la_frequency=la_frequency,
                freq_range=freq_range,
                fing_chart_file=self.fing_chart_file_path or "",
                fing_chart_content=fing_chart_content,
                stopper_offset_m=stopper_offset_m,
                embouchure_radius_m=Rw
            )
            
            if existing_calc_id is not None:
                logger.info(f"✓✓✓ Cálculo existente encontrado para {self.flute_model} (ID: {existing_calc_id}), cargando desde BD (SIN RECALCULAR)...")
                self._load_acoustic_analysis_from_db(existing_calc_id)
                self._calc_params_id = existing_calc_id
                return
            else:
                logger.info(f"✗ No se encontró cálculo existente para {self.flute_model}, se calculará nuevo")
        
        # No existe o se fuerza recálculo, calcular y guardar
        logger.info(f"⚠️ RECALCULANDO análisis acústico para {self.flute_model} (no existe en BD o force_recalculate=True)...")
        self._compute_and_save_acoustic_analysis(temperature, la_frequency)
    
    def _load_acoustic_analysis_from_db(self, calc_params_id: int) -> None:
        """
        Carga análisis acústico desde la base de datos.
        
        Args:
            calc_params_id: ID de los parámetros de cálculo.
        """
        try:
            logger.info(f"[{self.flute_model}] Cargando resultados desde BD (calc_params_id={calc_params_id})...")
            # Cargar resultados desde BD
            impedance_caches = self.db_manager.load_impedance_results(calc_params_id)
            logger.info(f"[{self.flute_model}] {len(impedance_caches)} resultados cargados desde BD")
            
            # Convertir ImpedanceCache a objetos compatibles con FluteData
            # Necesitamos recrear objetos ImpedanceComputation para compatibilidad
            # pero usaremos los datos cacheados cuando sea posible
            self.acoustic_analysis = {}
            
            logger.info(f"[{self.flute_model}] Obteniendo parámetros de cálculo...")
            # Obtener parámetros de cálculo para recrear objetos
            calc_params = self.db_manager.get_calculation_params(calc_params_id)
            if not calc_params:
                logger.error(f"No se encontraron parámetros de cálculo con ID {calc_params_id}")
                return
            
            logger.info(f"[{self.flute_model}] Recreando geometría OpenWind...")
            # Recrear geometría y configuración para ImpedanceComputation
            bore_segments, side_holes, fing_chart_parsed = self.get_openwind_geometry_inputs()
            logger.info(f"[{self.flute_model}] Geometría OpenWind recreada")
            
            headjoint_data = self.data.get(FLUTE_PARTS_ORDER[0], {})
            stopper_offset_m = headjoint_data.get('_calculated_stopper_absolute_position_mm', 0.0) / 1000.0
            geom_for_ic = [[(m["position"] / 1000.0) - stopper_offset_m, m["diameter"] / 2000.0] 
                          for m in self.combined_measurements]
            
            emb_hole_diameters = headjoint_data.get("Holes diameter", [])
            Rw = 0.006
            if emb_hole_diameters and emb_hole_diameters[0] > 0:
                Rw = (emb_hole_diameters[0] / 2.0) / 1000.0
            
            freq_range = np.arange(
                calc_params['freq_range_start'],
                calc_params['freq_range_end'],
                calc_params['freq_range_step']
            )
            
            player = Player(calc_params['player_type'])
            # Player("FLUTE") ya configura los parámetros de radiación apropiados
            player.update_curve("section", np.pi * Rw**2)
            
            # Para cada nota, crear un wrapper que use los datos cacheados SIN recalcular
            logger.info(f"[{self.flute_model}] Procesando {len(impedance_caches)} notas...")
            for note, impedance_cache in impedance_caches.items():
                try:
                    logger.info(f"[{self.flute_model}] Procesando nota {note}...")
                    # Usar CachedImpedanceComputation que simula ImpedanceComputation
                    # pero usa los datos de la BD directamente, sin recalcular
                    serialized_data = impedance_cache.serialized_data
                    if serialized_data:
                        logger.info(f"[{self.flute_model}] Deserializando datos para nota {note} (tamaño: {len(serialized_data)} chars)...")
                        cached_impedance = CachedImpedanceComputation(serialized_data)
                        self.acoustic_analysis[note] = cached_impedance
                        logger.info(f"✓ Análisis acústico cargado desde BD para nota {note} (sin recalcular)")
                    else:
                        logger.warning(f"No hay datos serializados para nota {note}, se recalculará")
                        # Si no hay datos, recalcular (esto no debería pasar normalmente)
                        impedance_obj = ImpedanceComputation(
                            freq_range,
                            geom_for_ic,
                            side_holes,
                            fing_chart_parsed,
                            player=player,
                            note=note,
                            temperature=calc_params['temperature'],
                            interp=bool(calc_params['interp']),
                            source_location=calc_params['source_location']
                        )
                        self.acoustic_analysis[note] = impedance_obj
                except Exception as e:
                    logger.error(f"Error cargando datos desde BD para nota {note}: {e}")
                    # Si falla, recalcular como fallback
                    try:
                        logger.warning(f"Recalculando nota {note} como fallback...")
                        impedance_obj = ImpedanceComputation(
                            freq_range,
                            geom_for_ic,
                            side_holes,
                            fing_chart_parsed,
                            player=player,
                            note=note,
                            temperature=calc_params['temperature'],
                            interp=bool(calc_params['interp']),
                            source_location=calc_params['source_location']
                        )
                        self.acoustic_analysis[note] = impedance_obj
                    except Exception as e2:
                        logger.error(f"Error también al recalcular nota {note}: {e2}")
            
            logger.info(f"Análisis acústico cargado desde BD para {self.flute_model} ({len(self.acoustic_analysis)} notas)")
            
        except Exception as e:
            logger.error(f"Error cargando análisis acústico desde BD: {e}", exc_info=True)
            # Si falla la carga, calcular normalmente
            self._compute_and_save_acoustic_analysis(
                calc_params['temperature'] if calc_params else 20.0,
                calc_params['la_frequency'] if calc_params else 415.0
            )
    
    def _compute_and_save_acoustic_analysis(self, temperature: float, la_frequency: float) -> None:
        """
        Calcula análisis acústico y lo guarda en la base de datos.
        
        Args:
            temperature: Temperatura en Celsius.
            la_frequency: Frecuencia del La (diapason) en Hz.
        """
        # Calcular usando el método de la clase padre
        self.compute_acoustic_analysis(self.fing_chart_file_path, temperature)
        
        # Guardar en base de datos (solo si hay DB Manager)
        if self.db_manager is not None and self._flute_db_id is not None and self.acoustic_analysis:
            try:
                # Preparar datos para guardar
                freq_range = np.arange(100, 3000, 2.0)  # Rango completo para análisis detallado de impedancia
                bore_segments, side_holes, fing_chart_parsed = self.get_openwind_geometry_inputs()
                
                headjoint_data = self.data.get(FLUTE_PARTS_ORDER[0], {})
                stopper_offset_m = headjoint_data.get('_calculated_stopper_absolute_position_mm', 0.0) / 1000.0
                
                emb_hole_diameters = headjoint_data.get("Holes diameter", [])
                Rw = 0.006
                if emb_hole_diameters and emb_hole_diameters[0] > 0:
                    Rw = (emb_hole_diameters[0] / 2.0) / 1000.0
                
                # Leer contenido del archivo de digitaciones
                fing_chart_content = ""
                try:
                    if self.fing_chart_file_path:
                        with open(self.fing_chart_file_path, 'r', encoding='utf-8') as f:
                            fing_chart_content = f.read()
                except Exception as e:
                    logger.warning(f"Error leyendo archivo de digitaciones para guardar: {e}")
                
                # Guardar en BD (usar preferencia del usuario)
                self._calc_params_id = self.db_manager.save_impedance_calculation(
                    flute_id=self._flute_db_id,
                    temperature=temperature,
                    la_frequency=la_frequency,
                    freq_range=freq_range,
                    fing_chart_file=self.fing_chart_file_path or "",
                    fing_chart_content=fing_chart_content,
                    stopper_offset_m=stopper_offset_m,
                    embouchure_radius_m=Rw,
                    bore_segments=bore_segments,
                    side_holes=side_holes,
                    combined_measurements=self.combined_measurements,
                    impedance_results=self.acoustic_analysis,
                    include_pressure_flow=self.include_pressure_flow  # Usar preferencia guardada
                )
                
                logger.info(f"Análisis acústico guardado en BD para {self.flute_model}")
            except Exception as e:
                logger.error(f"Error guardando análisis acústico en BD: {e}", exc_info=True)
                # No fallar si no se puede guardar, el cálculo ya se hizo

