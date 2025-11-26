"""
Módulo para serializar y deserializar objetos ImpedanceComputation de OpenWind.

Permite guardar los resultados de cálculo de impedancia en la base de datos
y reconstruirlos posteriormente sin necesidad de recalcular.
"""

import json
import numpy as np
from typing import Dict, Any, Optional, Tuple
from openwind import ImpedanceComputation, Player, InstrumentGeometry  # type: ignore
import logging

logger = logging.getLogger(__name__)


class ImpedanceSerializer:
    """Clase para serializar y deserializar objetos ImpedanceComputation."""
    
    @staticmethod
    def serialize_impedance(impedance_obj: ImpedanceComputation, include_pressure_flow: bool = False) -> Dict[str, Any]:
        """
        Serializa un objeto ImpedanceComputation a un diccionario JSON-serializable.
        
        Args:
            impedance_obj: Objeto ImpedanceComputation a serializar.
            include_pressure_flow: Si False, no guarda datos de presión/flujo (ahorra espacio).
        
        Returns:
            Diccionario con los datos serializados.
        """
        try:
            # Extraer arrays de numpy
            frequencies = impedance_obj.frequencies.tolist() if hasattr(impedance_obj, 'frequencies') else []
            impedance = impedance_obj.impedance
            
            # Separar parte real e imaginaria
            impedance_real = np.real(impedance).tolist() if impedance is not None else []
            impedance_imag = np.imag(impedance).tolist() if impedance is not None else []
            
            # Extraer frecuencias antiresonantes
            antiresonance_freqs = []
            try:
                antires_freqs_list = list(impedance_obj.antiresonance_frequencies())
                antiresonance_freqs = [float(f) for f in antires_freqs_list]
            except Exception as e:
                logger.warning(f"Error extrayendo frecuencias antiresonantes: {e}")
            
            # Extraer datos de presión y flujo (solo si se solicita)
            # OPTIMIZACIÓN: Guardar solo los primeros 3 armónicos para reducir tamaño de BD
            pressure_flow_data = None
            if include_pressure_flow:
                try:
                    x_coords, pressure_modes, flow_modes = impedance_obj.get_pressure_flow()
                    
                    # Identificar índices de los primeros 3 armónicos (antirresonancias)
                    antires_freqs_list = list(impedance_obj.antiresonance_frequencies())
                    num_harmonics_to_save = min(3, len(antires_freqs_list))
                    
                    if num_harmonics_to_save > 0 and pressure_modes is not None and flow_modes is not None:
                        # Encontrar los índices de frecuencia más cercanos a las antirresonancias
                        freq_array = impedance_obj.frequencies
                        harmonic_indices = []
                        harmonic_frequencies = []
                        
                        for i in range(num_harmonics_to_save):
                            target_freq = antires_freqs_list[i]
                            # Encontrar índice más cercano
                            idx = np.argmin(np.abs(freq_array - target_freq))
                            harmonic_indices.append(int(idx))
                            harmonic_frequencies.append(float(freq_array[idx]))
                        
                        # Extraer solo los modos de los armónicos seleccionados
                        pressure_modes_harmonics = pressure_modes[harmonic_indices, :]
                        flow_modes_harmonics = flow_modes[harmonic_indices, :]
                        
                        pressure_flow_data = {
                            'x_coords': x_coords.tolist() if x_coords is not None else [],
                            'harmonic_frequencies': harmonic_frequencies,  # Frecuencias de los armónicos
                            'pressure_modes_real': np.real(pressure_modes_harmonics).tolist(),
                            'pressure_modes_imag': np.imag(pressure_modes_harmonics).tolist(),
                            'flow_modes_real': np.real(flow_modes_harmonics).tolist(),
                            'flow_modes_imag': np.imag(flow_modes_harmonics).tolist(),
                            'num_harmonics': num_harmonics_to_save
                        }
                        logger.debug(f"Guardando datos de presión/flujo para {num_harmonics_to_save} armónicos (optimizado)")
                    else:
                        logger.warning("No se pudieron extraer armónicos para presión/flujo")
                except Exception as e:
                    logger.warning(f"Error extrayendo datos de presión/flujo: {e}")
            
            return {
                'frequencies': frequencies,
                'impedance_real': impedance_real,
                'impedance_imag': impedance_imag,
                'antiresonance_freqs': antiresonance_freqs,
                'pressure_flow_data': pressure_flow_data
            }
        except Exception as e:
            logger.error(f"Error serializando ImpedanceComputation: {e}", exc_info=True)
            raise
    
    @staticmethod
    def deserialize_to_dict(serialized_data: Dict[str, Any]) -> Dict[str, np.ndarray]:
        """
        Deserializa datos JSON a arrays de numpy.
        
        Args:
            serialized_data: Diccionario con datos serializados.
        
        Returns:
            Diccionario con arrays de numpy reconstruidos.
        """
        try:
            frequencies = np.array(serialized_data.get('frequencies', []), dtype=float)
            impedance_real = np.array(serialized_data.get('impedance_real', []), dtype=float)
            impedance_imag = np.array(serialized_data.get('impedance_imag', []), dtype=float)
            impedance = impedance_real + 1j * impedance_imag
            
            antiresonance_freqs = np.array(serialized_data.get('antiresonance_freqs', []), dtype=float)
            
            pressure_flow_data = serialized_data.get('pressure_flow_data')
            if pressure_flow_data:
                x_coords = np.array(pressure_flow_data.get('x_coords', []), dtype=float)
                pressure_real = np.array(pressure_flow_data.get('pressure_modes_real', []), dtype=float)
                pressure_imag = np.array(pressure_flow_data.get('pressure_modes_imag', []), dtype=float)
                flow_real = np.array(pressure_flow_data.get('flow_modes_real', []), dtype=float)
                flow_imag = np.array(pressure_flow_data.get('flow_modes_imag', []), dtype=float)
                
                pressure_modes = pressure_real + 1j * pressure_imag
                flow_modes = flow_real + 1j * flow_imag
            else:
                x_coords = np.array([])
                pressure_modes = np.array([])
                flow_modes = np.array([])
            
            return {
                'frequencies': frequencies,
                'impedance': impedance,
                'antiresonance_freqs': antiresonance_freqs,
                'x_coords': x_coords,
                'pressure_modes': pressure_modes,
                'flow_modes': flow_modes
            }
        except Exception as e:
            logger.error(f"Error deserializando datos: {e}", exc_info=True)
            raise
    
    @staticmethod
    def create_impedance_computation_from_data(
        frequencies: np.ndarray,
        impedance: np.ndarray,
        geom_for_ic: list,
        side_holes_for_openwind: list,
        fing_chart_parsed: list,
        player: Player,
        note: str,
        temperature: float,
        **kwargs
    ) -> ImpedanceComputation:
        """
        Crea un objeto ImpedanceComputation a partir de datos deserializados.
        
        Nota: Esta función recrea el objeto calculando la impedancia nuevamente,
        ya que ImpedanceComputation no puede ser reconstruido directamente desde
        solo los arrays de resultados. Sin embargo, podemos usar los datos
        almacenados para validar que el cálculo es correcto.
        
        Args:
            frequencies: Array de frecuencias.
            impedance: Array de impedancia (complejo).
            geom_for_ic: Geometría del bore.
            side_holes_for_openwind: Lista de agujeros laterales.
            fing_chart_parsed: Tabla de digitaciones parseada.
            player: Objeto Player configurado.
            note: Nota a calcular.
            temperature: Temperatura en Celsius.
            **kwargs: Argumentos adicionales para ImpedanceComputation.
        
        Returns:
            Objeto ImpedanceComputation recalculado.
        """
        # Recalcular la impedancia (esto es necesario porque ImpedanceComputation
        # no puede reconstruirse solo desde los arrays de resultados)
        return ImpedanceComputation(
            frequencies,
            geom_for_ic,
            side_holes_for_openwind,
            fing_chart_parsed,
            player=player,
            note=note,
            temperature=temperature,
            **kwargs
        )


class CachedImpedanceComputation:
    """
    Wrapper que simula ImpedanceComputation usando datos cacheados de la BD.
    Evita recalcular la impedancia cuando se carga desde la base de datos.
    """
    
    def __init__(self, serialized_data: Dict[str, Any]):
        """
        Inicializa el wrapper con datos serializados.
        
        Args:
            serialized_data: Diccionario con datos serializados de la BD.
        """
        self._serialized_data = serialized_data
        self._arrays: Optional[Dict[str, np.ndarray]] = None
    
    @property
    def arrays(self) -> Dict[str, np.ndarray]:
        """Deserializa y retorna los arrays de numpy."""
        if self._arrays is None:
            self._arrays = ImpedanceSerializer.deserialize_to_dict(self._serialized_data)
        return self._arrays
    
    @property
    def frequencies(self) -> np.ndarray:
        """Array de frecuencias (compatible con ImpedanceComputation)."""
        return self.arrays['frequencies']
    
    @property
    def impedance(self) -> np.ndarray:
        """Array de impedancia compleja (compatible con ImpedanceComputation)."""
        return self.arrays['impedance']
    
    def antiresonance_frequencies(self, k: Optional[int] = None):
        """
        Retorna frecuencias antiresonantes (compatible con ImpedanceComputation).
        
        Args:
            k: Número de antirresonancias a retornar (opcional).
        
        Returns:
            Lista o generador de frecuencias antiresonantes.
        """
        antires_freqs = self.arrays['antiresonance_freqs']
        if k is not None:
            return antires_freqs[:k]
        # Retornar lista para compatibilidad con list(antiresonance_frequencies())
        return list(antires_freqs)
    
    def get_pressure_flow(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Retorna datos de presión y flujo (compatible con ImpedanceComputation).
        Si no están en cache, retorna arrays vacíos (se deben recalcular).
        
        NOTA: Con la optimización, solo se guardan los primeros 3 armónicos,
        no todas las frecuencias. Los arrays retornados tendrán dimensión
        [num_harmonics, num_spatial_points] en lugar de [num_freqs, num_spatial_points].
        
        Returns:
            Tupla (x_coords, pressure_modes, flow_modes).
        """
        arrays = self.arrays
        
        # Verificar si hay datos de presión/flujo disponibles
        has_data = (
            'x_coords' in arrays and 
            'pressure_modes' in arrays and 
            'flow_modes' in arrays and
            arrays.get('x_coords') is not None and
            arrays.get('pressure_modes') is not None and
            arrays.get('flow_modes') is not None
        )
        
        if has_data:
            x_coords = arrays['x_coords']
            pressure_modes = arrays['pressure_modes']
            flow_modes = arrays['flow_modes']
            
            # Convertir a numpy arrays si son listas
            if not isinstance(x_coords, np.ndarray):
                x_coords = np.array(x_coords) if x_coords else np.array([])
            if not isinstance(pressure_modes, np.ndarray):
                pressure_modes = np.array(pressure_modes) if pressure_modes else np.array([])
            if not isinstance(flow_modes, np.ndarray):
                flow_modes = np.array(flow_modes) if flow_modes else np.array([])
            
            # Verificar que no estén vacíos
            if len(x_coords) > 0 and len(pressure_modes) > 0 and len(flow_modes) > 0:
                # Log para debug: indicar si son datos optimizados (solo armónicos)
                if pressure_modes.shape[0] <= 10:  # Probablemente solo armónicos
                    logger.debug(f"Datos de presión/flujo optimizados: {pressure_modes.shape[0]} armónicos × {pressure_modes.shape[1] if len(pressure_modes.shape) > 1 else 0} puntos espaciales")
                return (x_coords, pressure_modes, flow_modes)
        
        # No hay datos en cache, retornar arrays vacíos
        # El código que los use deberá recalcularlos
        logger.debug("pressure_flow_data no disponible en cache, se deben recalcular")
        return (
            np.array([]),
            np.array([]),
            np.array([])
        )
    
    def get_instrument_geometry(self):
        """
        Retorna un diccionario con información básica de geometría para compatibilidad.
        Los datos completos de geometría no están disponibles desde el cache,
        pero retornamos un objeto que indica que la geometría está disponible
        para evitar errores en el código que la usa.
        """
        # Retornar un objeto que indique que la geometría está disponible
        # pero que viene del cache (no del objeto ImpedanceComputation original)
        class CachedGeometry:
            def __init__(self):
                self.is_cached = True
                self.note = None  # Se puede establecer si es necesario
        
        return CachedGeometry()


class ImpedanceCache:
    """
    Clase wrapper que almacena tanto el objeto ImpedanceComputation como
    los datos serializados para acceso rápido sin recalcular.
    """
    
    def __init__(self, impedance_obj: Optional[ImpedanceComputation] = None,
                 serialized_data: Optional[Dict[str, Any]] = None):
        """
        Inicializa el cache.
        
        Args:
            impedance_obj: Objeto ImpedanceComputation (opcional).
            serialized_data: Datos serializados (opcional).
        """
        self._impedance_obj = impedance_obj
        self._serialized_data = serialized_data
        self._deserialized_arrays: Optional[Dict[str, np.ndarray]] = None
    
    @property
    def impedance_obj(self) -> Optional[ImpedanceComputation]:
        """Retorna el objeto ImpedanceComputation si está disponible."""
        return self._impedance_obj
    
    @property
    def serialized_data(self) -> Optional[Dict[str, Any]]:
        """Retorna los datos serializados."""
        if self._serialized_data is None and self._impedance_obj is not None:
            self._serialized_data = ImpedanceSerializer.serialize_impedance(self._impedance_obj)
        return self._serialized_data
    
    @property
    def arrays(self) -> Optional[Dict[str, np.ndarray]]:
        """Retorna los arrays de numpy deserializados."""
        if self._deserialized_arrays is None and self._serialized_data is not None:
            self._deserialized_arrays = ImpedanceSerializer.deserialize_to_dict(self._serialized_data)
        return self._deserialized_arrays
    
    def get_frequencies(self) -> np.ndarray:
        """Obtiene el array de frecuencias."""
        if self._impedance_obj is not None:
            return self._impedance_obj.frequencies
        elif self.arrays is not None:
            return self.arrays['frequencies']
        else:
            raise ValueError("No hay datos disponibles")
    
    def get_impedance(self) -> np.ndarray:
        """Obtiene el array de impedancia."""
        if self._impedance_obj is not None:
            return self._impedance_obj.impedance
        elif self.arrays is not None:
            return self.arrays['impedance']
        else:
            raise ValueError("No hay datos disponibles")
    
    def get_antiresonance_frequencies(self) -> np.ndarray:
        """Obtiene las frecuencias antiresonantes."""
        if self._impedance_obj is not None:
            return np.array(list(self._impedance_obj.antiresonance_frequencies()))
        elif self.arrays is not None:
            return self.arrays['antiresonance_freqs']
        else:
            raise ValueError("No hay datos disponibles")
    
    def get_pressure_flow(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Obtiene los datos de presión y flujo."""
        if self._impedance_obj is not None:
            return self._impedance_obj.get_pressure_flow()
        elif self.arrays is not None:
            arrs = self.arrays
            return arrs['x_coords'], arrs['pressure_modes'], arrs['flow_modes']
        else:
            raise ValueError("No hay datos disponibles")

