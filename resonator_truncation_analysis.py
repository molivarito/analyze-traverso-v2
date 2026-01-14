"""
Módulo de análisis de resonador truncado.

Analiza la respuesta acústica del resonador de la flauta sin considerar los agujeros,
truncando progresivamente la geometría desde el final para estudiar el efecto de la
longitud y conicidad en la respuesta acústica.
"""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import matplotlib.pyplot as plt
import logging
from openwind import Player, ImpedanceComputation  # type: ignore

from constants import (
    FLUTE_PARTS_ORDER, DEFAULT_EMBOUCHURE_CHIMNEY_HEIGHT,
    get_speed_of_sound, M_TO_MM_FACTOR
)

logger = logging.getLogger(__name__)


class ResonatorTruncationAnalyzer:
    """
    Analizador de resonador truncado para flautas.
    
    Analiza la respuesta acústica del bore sin agujeros, truncando progresivamente
    la geometría por porcentajes de longitud total para estudiar cómo la conicidad
    y longitud afectan las frecuencias de resonancia.
    """
    
    def __init__(
        self,
        flute_data: Any,  # FluteData o FluteDataDB
        truncation_percentages: Optional[List[float]] = None,
        freq_range: Optional[np.ndarray] = None,
        temperature: float = 20.0,
        min_length_mm: float = 50.0,
        include_embouchure: bool = True
    ):
        """
        Inicializa el analizador.
        
        Args:
            flute_data: Instancia de FluteData o FluteDataDB.
            truncation_percentages: Lista de porcentajes de longitud a analizar
                (por defecto: [100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 25, 20]).
            freq_range: Rango de frecuencias para análisis (por defecto: 100-3000 Hz, paso 2 Hz).
            temperature: Temperatura en Celsius.
            min_length_mm: Longitud mínima en mm para considerar una sección válida.
            include_embouchure: Si True, incluye la embocadura en el análisis.
        """
        self.flute_data = flute_data
        self.temperature = temperature
        self.min_length_mm = min_length_mm
        self.include_embouchure = include_embouchure
        
        # Porcentajes de truncamiento por defecto
        if truncation_percentages is None:
            self.truncation_percentages = list(range(100, 15, -5))  # 100, 95, 90, ..., 20
        else:
            self.truncation_percentages = sorted(truncation_percentages, reverse=True)
        
        # Rango de frecuencias por defecto
        if freq_range is None:
            self.freq_range = np.arange(100, 3000, 2.0)
        else:
            self.freq_range = freq_range
        
        # Validar datos de entrada
        if not hasattr(flute_data, 'combined_measurements') or not flute_data.combined_measurements:
            raise ValueError("FluteData debe tener combined_measurements válidos")
        
        if flute_data.validation_errors:
            logger.warning(f"FluteData tiene errores de validación: {flute_data.validation_errors}")
        
        # Resultados del análisis
        self.results: Dict[float, Dict[str, Any]] = {}
        
        # Calcular longitud total del resonador
        self._calculate_total_length()
    
    def _calculate_total_length(self) -> None:
        """Calcula la longitud total del resonador desde el corcho hasta el final."""
        if not self.flute_data.combined_measurements:
            self.total_length_mm = 0.0
            return
        
        # Obtener posición del corcho
        headjoint_data = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
        stopper_pos_mm = headjoint_data.get('_calculated_stopper_absolute_position_mm', 0.0)
        
        # Encontrar la posición máxima (final del resonador)
        max_pos = max(m["position"] for m in self.flute_data.combined_measurements)
        
        self.total_length_mm = max_pos - stopper_pos_mm
        logger.info(f"Longitud total del resonador: {self.total_length_mm:.2f} mm")
    
    def _truncate_geometry(self, percentage: float) -> List[List[float]]:
        """
        Trunca la geometría del bore al porcentaje especificado.
        
        Args:
            percentage: Porcentaje de longitud a mantener (0-100).
        
        Returns:
            Lista de puntos [x_m, r_m] en metros, relativa al corcho.
        """
        if not self.flute_data.combined_measurements:
            return []
        
        # Obtener posición del corcho
        headjoint_data = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
        stopper_pos_mm = headjoint_data.get('_calculated_stopper_absolute_position_mm', 0.0)
        stopper_offset_m = stopper_pos_mm / 1000.0
        
        # Calcular posición de truncamiento
        truncation_length_mm = self.total_length_mm * (percentage / 100.0)
        truncation_pos_abs_mm = stopper_pos_mm + truncation_length_mm
        
        # Filtrar mediciones que estén dentro del rango truncado
        truncated_measurements = []
        for m in self.flute_data.combined_measurements:
            pos_mm = m["position"]
            if pos_mm <= truncation_pos_abs_mm + 1e-6:  # Tolerancia pequeña
                # Convertir a coordenadas relativas al corcho en metros
                x_m = (pos_mm / 1000.0) - stopper_offset_m
                r_m = (m["diameter"] / 2.0) / 1000.0
                truncated_measurements.append([x_m, r_m])
        
        # Asegurar que tenemos al menos el punto del corcho y el punto final truncado
        if not truncated_measurements:
            logger.warning(f"No hay mediciones para truncamiento al {percentage}%")
            return []
        
        # Si el último punto no está exactamente en la posición de truncamiento,
        # añadir un punto interpolado en el extremo truncado
        last_point = truncated_measurements[-1]
        target_x_m = truncation_length_mm / 1000.0
        
        if abs(last_point[0] - target_x_m) > 1e-6:
            # Interpolar el radio en la posición de truncamiento
            if len(truncated_measurements) >= 2:
                # Interpolar entre el último punto y el anterior
                prev_point = truncated_measurements[-2]
                if prev_point[0] < target_x_m and last_point[0] > target_x_m:
                    # Interpolación lineal entre prev_point y last_point
                    ratio = (target_x_m - prev_point[0]) / (last_point[0] - prev_point[0]) if abs(last_point[0] - prev_point[0]) > 1e-9 else 0.0
                    r_interp = prev_point[1] + ratio * (last_point[1] - prev_point[1])
                    truncated_measurements.append([target_x_m, r_interp])
                elif last_point[0] < target_x_m:
                    # El último punto está antes del target, necesitamos el siguiente punto
                    # Buscar el siguiente punto en combined_measurements
                    next_point_found = False
                    for m in self.flute_data.combined_measurements:
                        pos_mm = m["position"]
                        x_m = (pos_mm / 1000.0) - stopper_offset_m
                        if x_m > target_x_m:
                            # Interpolar entre last_point y este punto
                            if last_point[0] < x_m:
                                ratio = (target_x_m - last_point[0]) / (x_m - last_point[0]) if abs(x_m - last_point[0]) > 1e-9 else 0.0
                                r_next = (m["diameter"] / 2.0) / 1000.0
                                r_interp = last_point[1] + ratio * (r_next - last_point[1])
                                truncated_measurements.append([target_x_m, r_interp])
                                next_point_found = True
                                break
                    if not next_point_found:
                        # Usar el último punto disponible
                        truncated_measurements.append([target_x_m, last_point[1]])
                else:
                    # Usar el último punto disponible
                    truncated_measurements.append([target_x_m, last_point[1]])
            else:
                # Solo un punto, usar su radio
                truncated_measurements.append([target_x_m, last_point[1]])
        
        # Validar longitud mínima
        if truncated_measurements:
            length_m = truncated_measurements[-1][0] - truncated_measurements[0][0]
            if length_m * 1000.0 < self.min_length_mm:
                logger.warning(f"Sección truncada al {percentage}% tiene longitud {length_m*1000:.2f}mm < {self.min_length_mm}mm. Puede ser inválida.")
        
        return truncated_measurements
    
    def _create_side_holes(self) -> List[List[Any]]:
        """
        Crea una lista vacía de agujeros laterales (solo encabezado).
        
        NOTA: No agregamos la embocadura aquí porque Player("FLUTE") con
        source_location="entrance" ya maneja automáticamente la embocadura.
        Agregar 'entrance' a side_holes causaría un conflicto (conector duplicado).
        
        Returns:
            Lista con solo el encabezado de agujeros (sin agujeros reales).
        """
        return [['label', 'position', 'chimney', 'radius', 'radius_out']]
    
    def _create_dummy_fingering_chart(self) -> List[List[str]]:
        """
        Crea un fingering chart mínimo (sin agujeros, solo para compatibilidad con OpenWind).
        
        OpenWind requiere un fingering chart. Como no hay agujeros laterales y usamos
        source_location="entrance", solo necesitamos el encabezado sin filas de componentes.
        
        Returns:
            Fingering chart mínimo con solo encabezado (sin filas de componentes).
        """
        # Solo encabezado, sin filas. OpenWind maneja 'entrance' automáticamente
        # cuando usamos source_location="entrance" con Player("FLUTE")
        return [['label', 'D_dummy']]
    
    def _calculate_impedance_for_truncated_geometry(
        self,
        truncated_geom: List[List[float]],
        percentage: float
    ) -> Optional[ImpedanceComputation]:
        """
        Calcula la impedancia para una geometría truncada.
        
        Args:
            truncated_geom: Geometría truncada como lista de [x_m, r_m].
            percentage: Porcentaje de truncamiento (para logging).
        
        Returns:
            Objeto ImpedanceComputation o None si falla.
        """
        if not truncated_geom or len(truncated_geom) < 2:
            logger.warning(f"Geometría truncada insuficiente para {percentage}%")
            return None
        
        try:
            # Configurar Player
            player = Player("FLUTE")
            
            # Configurar radio de embocadura si se incluye
            if self.include_embouchure:
                headjoint_data = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                emb_hole_diameters = headjoint_data.get("Holes diameter", [])
                Rw = 0.006  # Default
                
                if emb_hole_diameters:
                    emb_diam_spec = emb_hole_diameters[0]
                    if isinstance(emb_diam_spec, (list, tuple)) and len(emb_diam_spec) == 2:
                        emb_diam_mm = float(emb_diam_spec[0])
                    else:
                        emb_diam_mm = float(emb_diam_spec) if isinstance(emb_diam_spec, (int, float)) else 0.0
                    
                    if emb_diam_mm > 0:
                        Rw = (emb_diam_mm / 2.0) / 1000.0
                
                player.update_curve("section", np.pi * Rw**2)
            
            # Crear lista de agujeros (con embocadura si include_embouchure=True)
            side_holes = self._create_side_holes()
            
            # Crear fingering chart dummy
            fing_chart = self._create_dummy_fingering_chart()
            
            # Determinar source_location: 'entrance' si hay embocadura, 'entrance' si no
            # (OpenWind siempre reconoce 'entrance' como el extremo de entrada)
            source_loc = "entrance"
            
            # Calcular impedancia
            ic = ImpedanceComputation(
                self.freq_range,
                truncated_geom,
                side_holes,
                fing_chart,
                player=player,
                note="D_dummy",  # Nota dummy
                temperature=self.temperature,
                interp=True,
                source_location=source_loc
            )
            
            logger.debug(f"Impedancia calculada exitosamente para truncamiento al {percentage}%")
            return ic
            
        except Exception as e:
            logger.error(f"Error calculando impedancia para truncamiento al {percentage}%: {e}", exc_info=True)
            return None
    
    def _extract_metrics(self, ic: ImpedanceComputation, percentage: float) -> Dict[str, Any]:
        """
        Extrae todas las métricas acústicas de un ImpedanceComputation.
        
        Args:
            ic: Objeto ImpedanceComputation.
            percentage: Porcentaje de truncamiento (para referencia).
        
        Returns:
            Diccionario con todas las métricas extraídas.
        """
        metrics: Dict[str, Any] = {
            'percentage': percentage,
            'length_mm': self.total_length_mm * (percentage / 100.0)
        }
        
        try:
            # Frecuencias y impedancia (son atributos, no métodos)
            frequencies = ic.frequencies
            impedance = ic.impedance
            admittance = np.abs(1.0 / (impedance + 1e-10))
            
            metrics['frequencies'] = frequencies
            metrics['impedance'] = impedance
            metrics['admittance'] = admittance
            
            # Frecuencias de antiresonancia
            antires = list(ic.antiresonance_frequencies())
            metrics['antiresonance_frequencies'] = antires
            
            if len(antires) > 0:
                f0 = antires[0]
                metrics['f0'] = f0
                
                # Longitud efectiva calculada desde f0
                speed_of_sound = get_speed_of_sound(self.temperature)
                # Para un tubo abierto: L_eff = c / (2 * f0)
                metrics['effective_length_mm'] = (speed_of_sound / (2.0 * f0)) * 1000.0 if f0 > 0 else np.nan
                
                if len(antires) >= 2:
                    f1 = antires[1]
                    metrics['f1'] = f1
                    metrics['harmonic_ratio_f1_f0'] = f1 / f0 if f0 > 0 else np.nan
                    
                    if len(antires) >= 3:
                        f2 = antires[2]
                        metrics['f2'] = f2
                        metrics['harmonic_ratio_f2_f0'] = f2 / f0 if f0 > 0 else np.nan
                        metrics['harmonic_ratio_f2_f1'] = f2 / f1 if f1 > 0 else np.nan
                
                # Inharmonicidad (necesita frecuencia de referencia)
                # Por ahora, calculamos la desviación del segundo armónico respecto a 2*f0
                if len(antires) >= 2:
                    f1 = antires[1]
                    expected_f1 = 2.0 * f0
                    if expected_f1 > 0:
                        inharmonicity_cents = 1200.0 * np.log2(f1 / expected_f1)
                        metrics['inharmonicity_cents'] = inharmonicity_cents
                    else:
                        metrics['inharmonicity_cents'] = np.nan
                else:
                    metrics['inharmonicity_cents'] = np.nan
            
            # Q-factor para cada modo
            q_factors = []
            for i, freq in enumerate(antires[:5]):  # Primeros 5 modos
                if freq > 0:
                    try:
                        idx_peak = np.argmin(np.abs(frequencies - freq))
                        
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
                        
                        bandwidth_hz = frequencies[right_idx] - frequencies[left_idx] if right_idx > left_idx else np.nan
                        q_factor = freq / bandwidth_hz if bandwidth_hz > 0 else np.nan
                        q_factors.append(q_factor)
                    except Exception as e:
                        logger.warning(f"Error calculando Q-factor para modo {i} (f={freq:.1f}Hz): {e}")
                        q_factors.append(np.nan)
            
            metrics['q_factors'] = q_factors
            
        except Exception as e:
            logger.error(f"Error extrayendo métricas: {e}", exc_info=True)
            metrics['error'] = str(e)
        
        return metrics
    
    def analyze(self) -> Dict[float, Dict[str, Any]]:
        """
        Ejecuta el análisis completo para todos los porcentajes de truncamiento.
        
        Returns:
            Diccionario {percentage: metrics_dict} con los resultados.
        """
        logger.info(f"Iniciando análisis de resonador truncado para {self.flute_data.flute_model}")
        logger.info(f"Porcentajes a analizar: {self.truncation_percentages}")
        
        self.results = {}
        
        for percentage in self.truncation_percentages:
            logger.info(f"Analizando truncamiento al {percentage}%...")
            
            # Truncar geometría
            truncated_geom = self._truncate_geometry(percentage)
            
            if not truncated_geom or len(truncated_geom) < 2:
                logger.warning(f"Geometría truncada insuficiente para {percentage}%, saltando...")
                continue
            
            # Calcular impedancia
            ic = self._calculate_impedance_for_truncated_geometry(truncated_geom, percentage)
            
            if ic is None:
                logger.warning(f"No se pudo calcular impedancia para {percentage}%, saltando...")
                continue
            
            # Extraer métricas
            metrics = self._extract_metrics(ic, percentage)
            metrics['impedance_computation'] = ic  # Guardar referencia al objeto
            metrics['truncated_geometry'] = truncated_geom  # Guardar geometría truncada
            
            self.results[percentage] = metrics
        
        logger.info(f"Análisis completado. {len(self.results)} secciones analizadas exitosamente.")
        return self.results
    
    def plot_resonance_frequencies_vs_length(
        self,
        ax: Optional[plt.Axes] = None,
        max_modes: int = 5
    ) -> plt.Figure:
        """
        Grafica las frecuencias de resonancia vs. porcentaje de longitud.
        
        Args:
            ax: Eje de matplotlib (opcional).
            max_modes: Número máximo de modos a graficar.
        
        Returns:
            Figura de matplotlib.
        """
        if not self.results:
            logger.warning("No hay resultados para graficar. Ejecutar analyze() primero.")
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(0.5, 0.5, "No hay datos para graficar", ha='center', va='center')
            return fig
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))
        else:
            fig = ax.figure
        
        percentages = sorted(self.results.keys(), reverse=True)
        colors = plt.cm.viridis(np.linspace(0, 1, max_modes))
        
        for mode_idx in range(max_modes):
            frequencies = []
            valid_percentages = []
            
            for pct in percentages:
                result = self.results[pct]
                antires = result.get('antiresonance_frequencies', [])
                if len(antires) > mode_idx:
                    frequencies.append(antires[mode_idx])
                    valid_percentages.append(pct)
            
            if frequencies:
                ax.plot(valid_percentages, frequencies, 'o-', 
                       color=colors[mode_idx], label=f'Modo {mode_idx+1} (f{mode_idx})',
                       linewidth=2, markersize=6)
        
        ax.set_xlabel('Porcentaje de Longitud (%)', fontsize=12)
        ax.set_ylabel('Frecuencia (Hz)', fontsize=12)
        ax.set_title(f'Frecuencias de Resonancia vs. Longitud Truncada\n{self.flute_data.flute_model}', fontsize=14)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        
        return fig
    
    def plot_inharmonicity_vs_length(self, ax: Optional[plt.Axes] = None) -> plt.Figure:
        """
        Grafica la inharmonicidad vs. porcentaje de longitud.
        
        Args:
            ax: Eje de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        if not self.results:
            logger.warning("No hay resultados para graficar. Ejecutar analyze() primero.")
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(0.5, 0.5, "No hay datos para graficar", ha='center', va='center')
            return fig
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))
        else:
            fig = ax.figure
        
        percentages = sorted(self.results.keys(), reverse=True)
        inharmonicities = []
        valid_percentages = []
        
        for pct in percentages:
            result = self.results[pct]
            inharm = result.get('inharmonicity_cents')
            if inharm is not None and not np.isnan(inharm):
                inharmonicities.append(inharm)
                valid_percentages.append(pct)
        
        if inharmonicities:
            ax.plot(valid_percentages, inharmonicities, 'o-', 
                   color='#d62728', linewidth=2, markersize=8)
            ax.axhline(y=0, color='k', linestyle='--', alpha=0.3, label='Armónico perfecto')
        
        ax.set_xlabel('Porcentaje de Longitud (%)', fontsize=12)
        ax.set_ylabel('Inharmonicidad (cents)', fontsize=12)
        ax.set_title(f'Inharmonicidad vs. Longitud Truncada\n{self.flute_data.flute_model}', fontsize=14)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        
        return fig
    
    def plot_harmonic_ratios_vs_length(self, ax: Optional[plt.Axes] = None) -> plt.Figure:
        """
        Grafica las relaciones armónicas vs. porcentaje de longitud.
        
        Args:
            ax: Eje de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        if not self.results:
            logger.warning("No hay resultados para graficar. Ejecutar analyze() primero.")
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(0.5, 0.5, "No hay datos para graficar", ha='center', va='center')
            return fig
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))
        else:
            fig = ax.figure
        
        percentages = sorted(self.results.keys(), reverse=True)
        ratios_f1_f0 = []
        ratios_f2_f0 = []
        ratios_f2_f1 = []
        valid_percentages = []
        
        for pct in percentages:
            result = self.results[pct]
            r1 = result.get('harmonic_ratio_f1_f0')
            r2 = result.get('harmonic_ratio_f2_f0')
            r21 = result.get('harmonic_ratio_f2_f1')
            
            if r1 is not None and not np.isnan(r1):
                ratios_f1_f0.append(r1)
                ratios_f2_f0.append(r2 if r2 is not None and not np.isnan(r2) else np.nan)
                ratios_f2_f1.append(r21 if r21 is not None and not np.isnan(r21) else np.nan)
                valid_percentages.append(pct)
        
        if ratios_f1_f0:
            ax.plot(valid_percentages, ratios_f1_f0, 'o-', 
                   color='#1f77b4', label='f1/f0', linewidth=2, markersize=6)
            ax.axhline(y=2.0, color='#1f77b4', linestyle='--', alpha=0.3)
        
        if ratios_f2_f0:
            valid_r2 = [r for r in ratios_f2_f0 if not np.isnan(r)]
            if valid_r2:
                ax.plot(valid_percentages, ratios_f2_f0, 'o-', 
                       color='#ff7f0e', label='f2/f0', linewidth=2, markersize=6)
                ax.axhline(y=3.0, color='#ff7f0e', linestyle='--', alpha=0.3)
        
        if ratios_f2_f1:
            valid_r21 = [r for r in ratios_f2_f1 if not np.isnan(r)]
            if valid_r21:
                ax.plot(valid_percentages, ratios_f2_f1, 'o-', 
                       color='#2ca02c', label='f2/f1', linewidth=2, markersize=6)
                ax.axhline(y=1.5, color='#2ca02c', linestyle='--', alpha=0.3)
        
        ax.set_xlabel('Porcentaje de Longitud (%)', fontsize=12)
        ax.set_ylabel('Relación Armónica', fontsize=12)
        ax.set_title(f'Relaciones Armónicas vs. Longitud Truncada\n{self.flute_data.flute_model}', fontsize=14)
        ax.legend(loc='best')
        ax.grid(True, alpha=0.3)
        
        return fig
    
    def plot_impedance_curves_overlay(
        self,
        selected_percentages: Optional[List[float]] = None,
        ax: Optional[plt.Axes] = None
    ) -> plt.Figure:
        """
        Grafica curvas de impedancia superpuestas para diferentes longitudes.
        
        Args:
            selected_percentages: Lista de porcentajes a mostrar (None = todos).
            ax: Eje de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        if not self.results:
            logger.warning("No hay resultados para graficar. Ejecutar analyze() primero.")
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.text(0.5, 0.5, "No hay datos para graficar", ha='center', va='center')
            return fig
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 6))
        else:
            fig = ax.figure
        
        if selected_percentages is None:
            percentages = sorted(self.results.keys(), reverse=True)
            # Mostrar solo algunos para no saturar el gráfico
            step = max(1, len(percentages) // 8)
            selected_percentages = percentages[::step]
        
        colors = plt.cm.viridis(np.linspace(0, 1, len(selected_percentages)))
        
        for i, pct in enumerate(selected_percentages):
            if pct not in self.results:
                continue
            
            result = self.results[pct]
            frequencies = result.get('frequencies')
            admittance = result.get('admittance')
            
            if frequencies is not None and admittance is not None:
                ax.plot(frequencies, admittance, 
                       color=colors[i], label=f'{pct:.0f}%', 
                       linewidth=1.5, alpha=0.7)
        
        ax.set_xlabel('Frecuencia (Hz)', fontsize=12)
        ax.set_ylabel('Admitancia |Y|', fontsize=12)
        ax.set_title(f'Curvas de Admitancia para Diferentes Longitudes\n{self.flute_data.flute_model}', fontsize=14)
        ax.legend(loc='best', ncol=2)
        ax.grid(True, alpha=0.3)
        ax.set_xlim(100, 2000)  # Rango útil
        
        return fig
    
    def plot_3d_frequency_length_amplitude(self, ax: Optional[Any] = None) -> plt.Figure:
        """
        Grafica un mapa 3D de frecuencia vs. longitud vs. amplitud.
        
        Args:
            ax: Eje 3D de matplotlib (opcional).
        
        Returns:
            Figura de matplotlib.
        """
        from mpl_toolkits.mplot3d import Axes3D  # type: ignore
        
        if not self.results:
            logger.warning("No hay resultados para graficar. Ejecutar analyze() primero.")
            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection='3d')
            ax.text(0.5, 0.5, 0.5, "No hay datos para graficar", ha='center', va='center')
            return fig
        
        if ax is None:
            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection='3d')
        else:
            fig = ax.figure
        
        percentages = sorted(self.results.keys(), reverse=True)
        
        # Crear malla de datos
        all_frequencies = []
        all_percentages = []
        all_amplitudes = []
        
        for pct in percentages:
            result = self.results[pct]
            frequencies = result.get('frequencies')
            admittance = result.get('admittance')
            
            if frequencies is not None and admittance is not None:
                # Submuestrear para no saturar
                step = max(1, len(frequencies) // 200)
                all_frequencies.extend(frequencies[::step])
                all_percentages.extend([pct] * len(frequencies[::step]))
                all_amplitudes.extend(admittance[::step])
        
        if all_frequencies:
            # Crear superficie usando scatter para mejor visualización
            scatter = ax.scatter(all_frequencies, all_percentages, all_amplitudes,
                               c=all_amplitudes, cmap='viridis', alpha=0.6, s=1)
            fig.colorbar(scatter, ax=ax, label='Admitancia |Y|')
        
        ax.set_xlabel('Frecuencia (Hz)', fontsize=11)
        ax.set_ylabel('Porcentaje de Longitud (%)', fontsize=11)
        ax.set_zlabel('Admitancia |Y|', fontsize=11)
        ax.set_title(f'Mapa 3D: Frecuencia vs. Longitud vs. Amplitud\n{self.flute_data.flute_model}', fontsize=14)
        
        return fig
    
    def generate_summary_report(self, output_path: str) -> None:
        """
        Genera un reporte PDF con todos los análisis y gráficos.
        
        Args:
            output_path: Ruta al archivo PDF de salida.
        """
        from matplotlib.backends.backend_pdf import PdfPages
        
        if not self.results:
            logger.warning("No hay resultados para generar reporte. Ejecutar analyze() primero.")
            return
        
        with PdfPages(output_path) as pdf:
            # Página de título
            fig, ax = plt.subplots(figsize=(8.5, 11))
            ax.axis('off')
            title_text = f"Reporte de Análisis de Resonador Truncado\n\n"
            title_text += f"Flauta: {self.flute_data.flute_model}\n"
            title_text += f"Longitud Total: {self.total_length_mm:.2f} mm\n"
            title_text += f"Temperatura: {self.temperature}°C\n"
            title_text += f"Secciones Analizadas: {len(self.results)}\n"
            ax.text(0.5, 0.5, title_text, ha='center', va='center', 
                   fontsize=16, fontweight='bold')
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            
            # Gráfico de frecuencias de resonancia
            fig = self.plot_resonance_frequencies_vs_length()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            
            # Gráfico de inharmonicidad
            fig = self.plot_inharmonicity_vs_length()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            
            # Gráfico de relaciones armónicas
            fig = self.plot_harmonic_ratios_vs_length()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            
            # Curvas de impedancia superpuestas
            fig = self.plot_impedance_curves_overlay()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            
            # Gráfico 3D
            fig = self.plot_3d_frequency_length_amplitude()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
        
        logger.info(f"Reporte generado: {output_path}")

