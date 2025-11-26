import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Circle, Polygon
# import os # No se usa actualmente
from openwind import ImpedanceComputation, Player, InstrumentGeometry # type: ignore
import numpy as np
# from matplotlib.cm import tab10 # No se usa directamente
import logging
from typing import Any, List, Tuple, Optional, Dict

from constants import (
    BASE_COLORS, LINESTYLES, FLUTE_PARTS_ORDER,
    M_TO_MM_FACTOR
)
# Necesitas FluteData aquí si FluteOperations lo usa como tipo, pero solo se pasa como 'Any' en __init__
# from flute_data import FluteData # Descomentar si se usa FluteData como tipo explícito

# Importar CachedImpedanceComputation para verificaciones de tipo
try:
    from impedance_serializer import CachedImpedanceComputation
except ImportError:
    CachedImpedanceComputation = None  # type: ignore

logger = logging.getLogger(__name__)


def is_impedance_computation_like(obj: Any) -> bool:
    """
    Verifica si un objeto es compatible con ImpedanceComputation.
    Acepta tanto ImpedanceComputation real como CachedImpedanceComputation.
    
    Args:
        obj: Objeto a verificar.
    
    Returns:
        True si el objeto es compatible con ImpedanceComputation.
    """
    if isinstance(obj, ImpedanceComputation):
        return True
    if CachedImpedanceComputation and isinstance(obj, CachedImpedanceComputation):
        return True
    # Duck typing: verificar si tiene los atributos/métodos necesarios
    return (hasattr(obj, 'frequencies') and 
            hasattr(obj, 'impedance') and 
            hasattr(obj, 'antiresonance_frequencies') and
            callable(getattr(obj, 'antiresonance_frequencies', None)))

class FluteOperations:
    def __init__(self, flute_data_instance: Any) -> None: # flute_data_instance es una instancia de FluteData
        self.flute_data = flute_data_instance

    def _calculate_adjusted_positions(self, part: str, current_position: float) -> Tuple[List[float], List[float]]:
        # Asegurarse que self.flute_data.data[part] existe y tiene 'measurements'
        part_data = self.flute_data.data.get(part, {})
        measurements = part_data.get("measurements", [])
        positions = [item.get("position", 0.0) for item in measurements]
        diameters = [item.get("diameter", 0.0) for item in measurements]
        adjusted_positions = [pos + current_position for pos in positions]
        return adjusted_positions, diameters
    
    @staticmethod
    def _interpolate_external_diameter(
        external_measurements: List[Dict[str, float]],
        target_position: float
    ) -> Optional[float]:
        """
        Interpola el diámetro externo en una posición objetivo.
        
        Args:
            external_measurements: Lista de mediciones externas [{'position': float, 'external_diameter': float}]
            target_position: Posición objetivo en mm
        
        Returns:
            Diámetro externo interpolado en mm, o None si no hay datos suficientes
        """
        if not external_measurements or len(external_measurements) < 2:
            return None
        
        positions = np.array([m.get('position', 0.0) for m in external_measurements])
        diameters = np.array([m.get('external_diameter', 0.0) for m in external_measurements])
        
        # Validar que hay datos válidos
        if len(positions) == 0 or len(diameters) == 0:
            return None
        
        # Si la posición está exactamente en los datos, retornar ese valor
        if target_position in positions:
            idx = np.where(positions == target_position)[0][0]
            return float(diameters[idx])
        
        # Interpolación lineal
        try:
            # Ordenar por posición
            sorted_indices = np.argsort(positions)
            sorted_positions = positions[sorted_indices]
            sorted_diameters = diameters[sorted_indices]
            
            # Si está fuera del rango, usar extrapolación lineal o valores límite
            if target_position < sorted_positions[0]:
                return float(sorted_diameters[0])
            elif target_position > sorted_positions[-1]:
                return float(sorted_diameters[-1])
            
            # Interpolación lineal
            interpolated = np.interp(target_position, sorted_positions, sorted_diameters)
            return float(interpolated)
        except Exception as e:
            logger.warning(f"Error interpolando diámetro externo en posición {target_position}: {e}")
            return None
    
    def _get_combined_external_profile(self) -> Optional[List[Dict[str, float]]]:
        """
        Combina perfiles externos de todas las partes siguiendo la lógica de ensamblaje.
        
        Returns:
            Lista de mediciones externas combinadas con posiciones absolutas,
            o None si no hay perfil externo disponible.
        """
        if not hasattr(self.flute_data, 'external_geometry'):
            return None
        
        external_geometry = getattr(self.flute_data, 'external_geometry', {})
        if not external_geometry:
            return None
        
        combined_external = []
        current_abs_position = 0.0
        
        # Replicar la lógica de ensamblaje de combined_measurements
        for i, part_name in enumerate(FLUTE_PARTS_ORDER):
            part_data = self.flute_data.data.get(part_name, {})
            if not part_name in external_geometry:
                # Si no hay perfil externo para esta parte, continuar
                # pero actualizar posición para la siguiente parte
                part_total_length = part_data.get("Total length", 0.0)
                part_mortise_length = part_data.get("Mortise length", 0.0)
                
                if i == 0:  # Headjoint
                    current_abs_position = part_total_length - part_mortise_length
                elif i == 1:  # Body
                    current_abs_position += part_total_length
                else:  # Foot
                    current_abs_position += part_total_length - part_mortise_length
                continue
            
            external_measurements = external_geometry[part_name]
            if not external_measurements:
                continue
            
            # Calcular posición absoluta de inicio de esta parte
            part_total_length = part_data.get("Total length", 0.0)
            part_mortise_length = part_data.get("Mortise length", 0.0)
            
            if i == 0:  # Headjoint
                part_start_abs = 0.0
                current_abs_position = part_total_length - part_mortise_length
            elif i == 1:  # Body (se inserta en Headjoint)
                hj_data = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                hj_total_length = hj_data.get("Total length", 0.0)
                hj_mortise_length = hj_data.get("Mortise length", 0.0)
                part_start_abs = hj_total_length - hj_mortise_length
                current_abs_position = part_start_abs + part_total_length
            else:  # Foot (se inserta en Body)
                part_start_abs = current_abs_position - part_mortise_length
                current_abs_position = part_start_abs + part_total_length
            
            # Agregar mediciones externas con posiciones absolutas
            for ext_meas in external_measurements:
                rel_position = ext_meas.get('position', 0.0)
                abs_position = part_start_abs + rel_position
                combined_external.append({
                    'position': abs_position,
                    'external_diameter': ext_meas.get('external_diameter', 0.0),
                    'source_part_name': part_name
                })
        
        if not combined_external:
            return None
        
        # Ordenar por posición
        combined_external.sort(key=lambda x: x['position'])
        return combined_external

    def plot_individual_parts(self, axes_list: Optional[List[plt.Axes]] = None,
                              figure_title: Optional[str] = None,
                              flute_color: Optional[str] = None) -> Tuple[plt.Figure, List[plt.Axes]]:

        fig: plt.Figure
        ax_list_to_plot_on: List[plt.Axes]

        if axes_list is None:
            fig, axes_array = plt.subplots(2, 2, figsize=(10, 8))
            ax_list_to_plot_on = list(axes_array.flatten())
        elif isinstance(axes_list, list) and all(isinstance(ax_item, plt.Axes) for ax_item in axes_list) :
            if not axes_list: # Lista vacía de ejes
                 logger.warning("Se proporcionó una lista de ejes vacía a plot_individual_parts. Creando figura por defecto.")
                 fig, axes_array = plt.subplots(2, 2, figsize=(10, 8)); ax_list_to_plot_on = list(axes_array.flatten())
            else:
                fig = axes_list[0].figure
                ax_list_to_plot_on = axes_list
        else:
             logger.warning(f"Argumento 'axes_list' ({type(axes_list)}) inesperado en plot_individual_parts, creando figura por defecto.")
             fig, axes_array = plt.subplots(2, 2, figsize=(10, 8)); ax_list_to_plot_on = list(axes_array.flatten())


        actual_flute_name = self.flute_data.flute_model

        for i, part_name in enumerate(FLUTE_PARTS_ORDER):
            if i >= len(ax_list_to_plot_on):
                logger.warning(f"No hay suficientes ejes para la parte '{part_name}' en plot_individual_parts.")
                break
            current_ax = ax_list_to_plot_on[i]
            current_ax.clear()

            adjusted_positions, diameters = self._calculate_adjusted_positions(part_name, 0)

            linestyle = LINESTYLES[i % len(LINESTYLES)]
            color_to_use = flute_color if flute_color else BASE_COLORS[0]

            current_ax.plot(adjusted_positions, diameters, marker='o', linestyle=linestyle,
                       color=color_to_use, markersize=4, label=actual_flute_name)

            part_data = self.flute_data.data.get(part_name, {})
            hole_positions = part_data.get("Holes position", [])
            hole_diameters = part_data.get("Holes diameter", [])
            if hole_positions and hole_diameters:
                y_pos_for_holes = min(diameters) - 5 if diameters else -5
                for pos, diam in zip(hole_positions, hole_diameters):
                    current_ax.plot(pos, y_pos_for_holes, color=color_to_use,
                                    marker='o', markersize=max(diam * 0.5, 2), linestyle='None')

            current_ax.set_xlabel("Posición (mm)")
            current_ax.set_ylabel("Diámetro (mm)")
            current_ax.set_title(f"{part_name.capitalize()} ({actual_flute_name})", fontsize=9)
            current_ax.grid(True, linestyle=':', alpha=0.7)
            current_ax.legend(loc='best', fontsize=8)

        fig.tight_layout(rect=[0, 0.03, 1, 0.93])

        if figure_title:
            fig.suptitle(figure_title, fontsize=12)
        elif len(ax_list_to_plot_on) < len(FLUTE_PARTS_ORDER) and not figure_title:
             pass
        else:
             fig.suptitle(f"Detalle de Partes: {actual_flute_name}", fontsize=12)

        return fig, ax_list_to_plot_on

    def plot_all_parts_overlapping(self, ax: Optional[plt.Axes] = None,
                                   plot_label: Optional[str] = None,
                                   flute_color: Optional[str] = None, flute_style: Optional[str] = None) -> plt.Axes:
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(18, 6))
        else:
            fig = ax.figure
            ax.clear() # Limpiar el eje si se reutiliza

        current_position = 0.0
        actual_flute_name = self.flute_data.flute_model
        label_to_use = plot_label if plot_label else actual_flute_name

        for i, part_name in enumerate(FLUTE_PARTS_ORDER):
            part_data = self.flute_data.data.get(part_name, {})
            if not part_data: continue

            adjusted_positions, diameters = self._calculate_adjusted_positions(part_name, current_position)
            # Solo etiquetar la primera parte para la leyenda general de esta flauta
            current_part_label = label_to_use if i == 0 else None

            ax.plot(adjusted_positions, diameters, marker='o',
                    linestyle=flute_style if flute_style else LINESTYLES[0],
                    color=flute_color if flute_color else BASE_COLORS[0],
                    markersize=4, label=current_part_label)

            hole_positions = part_data.get("Holes position", [])
            hole_diameters = part_data.get("Holes diameter", [])
            if hole_positions and hole_diameters: # No dibujar si no hay diámetros de tubo
                y_pos_for_holes = min(diameters) - 5 if diameters else -5
                for pos, diam in zip(hole_positions, hole_diameters):
                    ax.plot(pos + current_position, y_pos_for_holes,
                            color=flute_color if flute_color else BASE_COLORS[0],
                            marker='o', markersize=max(diam * 0.5, 2), linestyle='None')

            total_length = part_data.get("Total length", 0.0)
            current_position += total_length

        ax.set_xlabel("Posición Acumulada (mm)")
        ax.set_ylabel("Diámetro (mm)")
        if label_to_use: ax.legend(loc='best', fontsize=9)
        ax.grid(True, linestyle=':', alpha=0.7)
        ax.set_title("Partes Desplegadas Secuencialmente" + (f" - {label_to_use}" if label_to_use else ""))
        return ax

    def plot_combined_flute_data(self, ax: Optional[plt.Axes] = None,
                                 plot_label: Optional[str] = None, 
                                 flute_color: Optional[str] = None, flute_style: Optional[str] = None,
                                 show_mortise_markers: bool = True,
                                 x_axis_origin_offset: float = 0.0) -> plt.Axes: # Nuevo parámetro
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(18, 6))
        else:
            fig = ax.figure
            # ax.clear() # Eliminado para permitir superposición por defecto

        combined_measurements = self.flute_data.combined_measurements
        if not combined_measurements or len(combined_measurements) < 2:
            logger.warning(f"No hay mediciones combinadas para {self.flute_data.flute_model} en plot_combined_flute_data.")
            return ax

        label_to_use = plot_label if plot_label else self.flute_data.flute_model

        # Dibujar el perfil por segmentos, coloreando cada segmento según su parte de origen.
        # REMOVED: if plot_label != "_nolegend_": # Evitar dibujar el perfil principal si solo se quieren marcadores
        current_segment_positions: List[float] = []
        current_segment_diameters: List[float] = []
        current_segment_part_name: Optional[str] = None
        flute_label_applied = False # Para aplicar la etiqueta general de la flauta solo una vez
        last_plotted_point_data: Optional[Dict[str, float]] = None # Para asegurar continuidad visual

        def _calculate_slope_and_angle(positions: List[float], diameters: List[float]) -> Tuple[float, float]:
            """Calcula la pendiente (mm/mm) y el ángulo del cono (grados) usando regresión lineal."""
            if len(positions) < 2:
                return 0.0, 0.0
            try:
                # Regresión lineal: diámetro = pendiente * posición + intercepto
                positions_arr = np.array(positions)
                diameters_arr = np.array(diameters)
                # Usar polyfit para regresión lineal (grado 1)
                slope, intercept = np.polyfit(positions_arr, diameters_arr, 1)
                # El ángulo del cono se calcula considerando que:
                # - La pendiente es dD/dx (cambio de diámetro por cambio de posición)
                # - El radio cambia como r = D/2, entonces dr/dx = pendiente/2
                # - El ángulo del cono es: atan(dr/dx) = atan(pendiente/2)
                cone_angle_deg = np.arctan(slope / 2.0) * 180.0 / np.pi
                return float(slope), float(cone_angle_deg)
            except Exception as e:
                logger.warning(f"Error calculando pendiente: {e}")
                return 0.0, 0.0

        def _draw_slope_annotation(ax, positions: List[float], diameters: List[float], 
                                   part_name: str, color: str):
            """Dibuja la anotación con la pendiente y ángulo del cono para una sección."""
            if len(positions) < 2:
                return
            slope, cone_angle = _calculate_slope_and_angle(positions, diameters)
            # Posición central de la sección
            center_x = (positions[0] + positions[-1]) / 2.0
            center_y = (diameters[0] + diameters[-1]) / 2.0
            
            # Formatear el texto
            slope_text = f"Pendiente: {slope:.4f} mm/mm"
            angle_text = f"Ángulo: {cone_angle:.2f}°"
            part_text = f"{part_name.capitalize()}"
            
            # Dibujar texto con fondo semitransparente
            text_str = f"{part_text}\n{slope_text}\n{angle_text}"
            ax.text(center_x, center_y, text_str, 
                   fontsize=8, color=color, ha='center', va='center',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor='white', 
                            alpha=0.8, edgecolor=color, linewidth=1.5))

        for i, point in enumerate(combined_measurements):
            point_part_name = point.get("source_part_name")
            adjusted_point_position = point["position"] - x_axis_origin_offset

            if point_part_name != current_segment_part_name and current_segment_positions:
                # Finalizar y dibujar el segmento anterior
                part_color_idx = FLUTE_PARTS_ORDER.index(current_segment_part_name) if current_segment_part_name in FLUTE_PARTS_ORDER else 0
                segment_color = BASE_COLORS[part_color_idx % len(BASE_COLORS)]
                current_plot_segment_label = label_to_use if not flute_label_applied else None

                ax.plot(current_segment_positions, current_segment_diameters,
                        linestyle=flute_style if flute_style else LINESTYLES[0],
                        color=segment_color, label=current_plot_segment_label)
                if current_plot_segment_label: flute_label_applied = True
                
                # Calcular y mostrar pendiente y ángulo del cono para esta sección
                _draw_slope_annotation(ax, current_segment_positions, current_segment_diameters,
                                       current_segment_part_name, segment_color)

                last_plotted_point_data = {"position": current_segment_positions[-1],
                                           "diameter": current_segment_diameters[-1]}
                current_segment_positions = []
                current_segment_diameters = []
            # Estas líneas deben estar fuera del if anterior, para ejecutarse en cada iteración.
            if not current_segment_positions and last_plotted_point_data: # Inicio de nuevo segmento
                current_segment_positions.append(last_plotted_point_data["position"])
                current_segment_diameters.append(last_plotted_point_data["diameter"])

            current_segment_positions.append(adjusted_point_position)
            current_segment_diameters.append(point["diameter"])
            current_segment_part_name = point_part_name
            
        # Dibujar el último segmento acumulado
        if current_segment_positions and len(current_segment_positions) > 1 and current_segment_part_name:
                part_color_idx = FLUTE_PARTS_ORDER.index(current_segment_part_name) if current_segment_part_name in FLUTE_PARTS_ORDER else 0
                segment_color = flute_color if flute_color else BASE_COLORS[part_color_idx % len(BASE_COLORS)] # Usar flute_color si se proporciona
                current_plot_segment_label = label_to_use if not flute_label_applied else None
                ax.plot(current_segment_positions, current_segment_diameters, linestyle=flute_style if flute_style else LINESTYLES[0], color=segment_color, label=current_plot_segment_label)
                
                # Calcular y mostrar pendiente y ángulo del cono para la última sección
                _draw_slope_annotation(ax, current_segment_positions, current_segment_diameters,
                                       current_segment_part_name, segment_color)
        
        if show_mortise_markers:
            # Calcular las posiciones físicas absolutas de los sockets usando la MISMA lógica que plot_physical_assembly
            # Luego aplicar el offset acústico (x_axis_origin_offset) para que coincidan con las zonas coloridas
            min_diam_for_marker, max_diam_for_marker = ax.get_ylim()
            # Ajustar un poco para que no estén exactamente en los bordes del plot
            marker_y_bottom = min_diam_for_marker + 0.1 * (max_diam_for_marker - min_diam_for_marker)
            marker_y_top = max_diam_for_marker - 0.1 * (max_diam_for_marker - min_diam_for_marker)

            # Calcular posiciones físicas usando la misma lógica que plot_physical_assembly
            current_physical_plot_start_abs = 0.0
            next_part_connection_point_abs = 0.0
            stopper_pos = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {}).get('_calculated_stopper_absolute_position_mm', 0.0)

            for i, part_name in enumerate(FLUTE_PARTS_ORDER):
                part_data = self.flute_data.data.get(part_name, {})
                part_total_length = part_data.get("Total length", 0.0)
                part_json_mortise_length = part_data.get("Mortise length", 0.0)

                # Misma lógica que plot_physical_assembly para calcular posiciones físicas
                if i == 0:  # Headjoint
                    current_physical_plot_start_abs = 0.0
                    # Socket de Headjoint está al final
                    socket_start_abs = current_physical_plot_start_abs + part_total_length - part_json_mortise_length
                    socket_end_abs = current_physical_plot_start_abs + part_total_length
                    next_part_connection_point_abs = socket_start_abs
                    
                    # Línea del corcho (Stopper)
                    ax.vlines(stopper_pos - x_axis_origin_offset, marker_y_bottom, marker_y_top, 
                             colors='gray', linestyles='dashdot', alpha=0.7, label="Stopper" if i==0 else None)
                    # Líneas punteadas rojas: límites del socket de Headjoint
                    ax.vlines(socket_start_abs - x_axis_origin_offset, marker_y_bottom, marker_y_top, 
                             colors='red', linestyles='dotted', alpha=0.6, label="HJ End/Socket Start" if i==0 else None)
                    ax.vlines(socket_end_abs - x_axis_origin_offset, marker_y_bottom, marker_y_top, 
                             colors='red', linestyles='dotted', alpha=0.6)

                elif i == 1:  # Body (Left)
                    # Left comienza donde termina el cuerpo de Headjoint (antes del socket de HJ)
                    hj_data = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                    hj_total_length = hj_data.get("Total length", 0.0)
                    hj_mortise_length = hj_data.get("Mortise length", 0.0)
                    current_physical_plot_start_abs = hj_total_length - hj_mortise_length
                    next_part_connection_point_abs = current_physical_plot_start_abs + part_total_length
                    
                    # Línea verde: Inicio de Left (coincide con fin del cuerpo de Headjoint)
                    ax.vlines(current_physical_plot_start_abs - x_axis_origin_offset, marker_y_bottom, marker_y_top, 
                             colors='green', linestyles='dotted', alpha=0.6, label="Tenon End/Body Start" if i==1 else None)
                    # Línea roja: Fin de Left / Inicio Socket Right
                    ax.vlines(next_part_connection_point_abs - x_axis_origin_offset, marker_y_bottom, marker_y_top, 
                             colors='red', linestyles='dotted', alpha=0.6)

                else:  # Right, Foot (socket al inicio)
                    # El inicio físico de Right/Foot es el final físico de Left/Right menos el socket de Right/Foot
                    current_physical_plot_start_abs = next_part_connection_point_abs - part_json_mortise_length
                    # Socket de Right/Foot está al inicio
                    socket_start_abs = current_physical_plot_start_abs
                    socket_end_abs = current_physical_plot_start_abs + part_json_mortise_length
                    next_part_connection_point_abs = current_physical_plot_start_abs + part_total_length
                    
                    # Líneas punteadas rojas: límites del socket de Right/Foot
                    ax.vlines(socket_start_abs - x_axis_origin_offset, marker_y_bottom, marker_y_top, 
                             colors='red', linestyles='dotted', alpha=0.6, label="Socket Start" if i==2 else None)
                    ax.vlines(socket_end_abs - x_axis_origin_offset, marker_y_bottom, marker_y_top, 
                             colors='green', linestyles='dotted', alpha=0.6)
                    # Línea roja: Fin de Right (si es Right, marca inicio de socket de Foot)
                    if part_name == FLUTE_PARTS_ORDER[2]:  # Right
                        ax.vlines(next_part_connection_point_abs - x_axis_origin_offset, marker_y_bottom, marker_y_top, 
                                 colors='red', linestyles='dotted', alpha=0.6)
        return ax

    def plot_solid_2d_view(self, ax: Optional[plt.Axes] = None,
                           plot_label: Optional[str] = None,
                           flute_color: Optional[str] = None,
                           x_axis_origin_offset: float = 0.0) -> Optional[plt.Axes]:
        """
        Dibuja el corte 2D del sólido 3D mostrando el perfil externo con agujeros como cortes del sólido.
        
        Args:
            ax: Eje de matplotlib donde dibujar. Si es None, se crea una nueva figura.
            plot_label: Etiqueta para la leyenda.
            flute_color: Color para el perfil externo.
            x_axis_origin_offset: Offset para el eje X.
        
        Returns:
            Eje de matplotlib, o None si no hay perfil externo disponible.
        """
        # Verificar si hay perfil externo disponible
        combined_external = self._get_combined_external_profile()
        if not combined_external:
            logger.debug(f"No hay perfil externo disponible para {self.flute_data.flute_model}")
            return None
        
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(18, 6))
        else:
            fig = ax.figure
        
        label_to_use = plot_label if plot_label else self.flute_data.flute_model
        
        # Extraer posiciones y diámetros externos
        ext_positions = np.array([m['position'] for m in combined_external])
        ext_diameters = np.array([m['external_diameter'] for m in combined_external])
        ext_radii = ext_diameters / 2.0
        
        # Ajustar posiciones con el offset
        adjusted_ext_positions = ext_positions - x_axis_origin_offset
        
        # Dibujar perfil externo superior e inferior
        color = flute_color if flute_color else 'gray'
        ax.plot(adjusted_ext_positions, ext_radii, 
                color=color, linestyle='-', linewidth=1.5, 
                label=label_to_use, zorder=5)
        ax.plot(adjusted_ext_positions, -ext_radii, 
                color=color, linestyle='-', linewidth=1.5, 
                zorder=5)
        
        # Rellenar entre perfiles para mostrar el sólido
        ax.fill_between(adjusted_ext_positions, -ext_radii, ext_radii,
                        alpha=0.3, color=color, zorder=1)
        
        # Dibujar agujeros como cortes del sólido
        # Obtener agujeros de todas las partes con posiciones absolutas
        current_abs_position = 0.0
        seen_hole_positions = set()  # Para evitar duplicados
        
        for i, part_name in enumerate(FLUTE_PARTS_ORDER):
            part_data = self.flute_data.data.get(part_name, {})
            if not part_data:
                continue
            
            # Calcular posición absoluta de inicio de esta parte
            part_total_length = part_data.get("Total length", 0.0)
            part_mortise_length = part_data.get("Mortise length", 0.0)
            
            if i == 0:  # Headjoint
                part_start_abs = 0.0
                current_abs_position = part_total_length - part_mortise_length
            elif i == 1:  # Body (se inserta en Headjoint)
                hj_data = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                hj_total_length = hj_data.get("Total length", 0.0)
                hj_mortise_length = hj_data.get("Mortise length", 0.0)
                part_start_abs = hj_total_length - hj_mortise_length
                current_abs_position = part_start_abs + part_total_length
            else:  # Foot (se inserta en Body)
                part_start_abs = current_abs_position - part_mortise_length
                current_abs_position = part_start_abs + part_total_length
            
            # Obtener agujeros de esta parte
            hole_positions = part_data.get("Holes position", [])
            hole_diameters = part_data.get("Holes diameter", [])
            side_holes = part_data.get("Side holes", [])
            
            # Procesar formato 2 (Side holes) - preferido si está disponible
            if side_holes and isinstance(side_holes, list) and len(side_holes) > 0:
                for hole_info in side_holes:
                    if isinstance(hole_info, dict):
                        h_pos_rel = hole_info.get('position', 0.0)
                        h_diam = hole_info.get('diameter', 0.0)
                        if h_pos_rel is not None and h_diam is not None:
                            abs_hole_pos = part_start_abs + h_pos_rel
                            if abs_hole_pos not in seen_hole_positions:
                                seen_hole_positions.add(abs_hole_pos)
                                hole_radius = h_diam / 2.0
                                
                                # Dibujar el agujero (círculo que representa el diámetro del agujero)
                                # El agujero es un cilindro perpendicular al eje principal de la flauta
                                adjusted_hole_pos = abs_hole_pos - x_axis_origin_offset
                                hole_circle = Circle(
                                    (adjusted_hole_pos, 0),
                                    hole_radius,
                                    fill=True,
                                    facecolor='white',
                                    edgecolor='black',
                                    linewidth=0.8,
                                    zorder=11
                                )
                                ax.add_patch(hole_circle)
            
            # Procesar formato 1 (Holes position/diameter) si no se usó formato 2
            elif hole_positions and hole_diameters and len(hole_positions) == len(hole_diameters):
                for h_pos_rel, h_diam in zip(hole_positions, hole_diameters):
                    if h_pos_rel is not None and h_diam is not None:
                        abs_hole_pos = part_start_abs + h_pos_rel
                        if abs_hole_pos not in seen_hole_positions:
                            seen_hole_positions.add(abs_hole_pos)
                            hole_radius = h_diam / 2.0
                            
                            # Dibujar el agujero (círculo que representa el diámetro del agujero)
                            # El agujero es un cilindro perpendicular al eje principal de la flauta
                            adjusted_hole_pos = abs_hole_pos - x_axis_origin_offset
                            hole_circle = Circle(
                                (adjusted_hole_pos, 0),
                                hole_radius,
                                fill=True,
                                facecolor='white',
                                edgecolor='black',
                                linewidth=0.8,
                                zorder=11
                            )
                            ax.add_patch(hole_circle)
        
        ax.set_title(f"Vista Sólido 2D: {self.flute_data.flute_model}", fontsize=10)
        ax.set_xlabel("Posición (mm)", fontsize=9)
        ax.set_ylabel("Radio (mm)", fontsize=9)
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True, linestyle=':', alpha=0.5)
        
        return ax

    def plot_individual_part_solid_2d(self, part_name: str, ax: Optional[plt.Axes] = None,
                                      plot_label: Optional[str] = None,
                                      part_color: Optional[str] = None) -> Optional[plt.Axes]:
        """
        Dibuja el sólido 2D de una parte individual.
        
        Args:
            part_name: Nombre de la parte (ej: 'headjoint', 'body', 'foot').
            ax: Eje de matplotlib donde dibujar. Si es None, se crea una nueva figura.
            plot_label: Etiqueta para la leyenda.
            part_color: Color para el perfil externo.
        
        Returns:
            Eje de matplotlib, o None si no hay perfil externo disponible para esta parte.
        """
        # Verificar si hay perfil externo para esta parte
        if not hasattr(self.flute_data, 'external_geometry'):
            return None
        
        external_geometry = getattr(self.flute_data, 'external_geometry', {})
        external_measurements = external_geometry.get(part_name, [])
        
        if not external_measurements:
            logger.debug(f"No hay perfil externo disponible para parte '{part_name}'")
            return None
        
        part_data = self.flute_data.data.get(part_name, {})
        if not part_data:
            return None
        
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 6))
        else:
            fig = ax.figure
        
        label_to_use = plot_label if plot_label else f"{part_name} - {self.flute_data.flute_model}"
        
        # Extraer posiciones y diámetros externos
        ext_positions = np.array([m.get('position', 0.0) for m in external_measurements])
        ext_diameters = np.array([m.get('external_diameter', 0.0) for m in external_measurements])
        ext_radii = ext_diameters / 2.0
        
        # Dibujar perfil externo superior e inferior
        color = part_color if part_color else 'gray'
        ax.plot(ext_positions, ext_radii, 
                color=color, linestyle='-', linewidth=1.5, 
                label=f"{label_to_use} (externo)", zorder=5)
        ax.plot(ext_positions, -ext_radii, 
                color=color, linestyle='-', linewidth=1.5, 
                zorder=5)
        
        # Rellenar entre perfiles para mostrar el sólido
        ax.fill_between(ext_positions, -ext_radii, ext_radii,
                        alpha=0.3, color=color, zorder=1)
        
        # Dibujar agujeros como cortes del sólido
        hole_positions = part_data.get("Holes position", [])
        hole_diameters = part_data.get("Holes diameter", [])
        side_holes = part_data.get("Side holes", [])
        
        # Procesar formato 2 (Side holes) - preferido si está disponible
        if side_holes and isinstance(side_holes, list) and len(side_holes) > 0:
            for hole_info in side_holes:
                if isinstance(hole_info, dict):
                    h_pos_rel = hole_info.get('position', 0.0)
                    h_diam = hole_info.get('diameter', 0.0)
                    if h_pos_rel is not None and h_diam is not None:
                        hole_radius = h_diam / 2.0
                        
                        # Dibujar el agujero (círculo que representa el diámetro del agujero)
                        # El agujero es un cilindro perpendicular al eje principal de la flauta
                        hole_circle = Circle(
                            (h_pos_rel, 0),
                            hole_radius,
                            fill=True,
                            facecolor='white',
                            edgecolor='black',
                            linewidth=0.8,
                            zorder=11
                        )
                        ax.add_patch(hole_circle)
        
        # Procesar formato 1 (Holes position/diameter) si no se usó formato 2
        elif hole_positions and hole_diameters and len(hole_positions) == len(hole_diameters):
            for h_pos_rel, h_diam in zip(hole_positions, hole_diameters):
                if h_pos_rel is not None and h_diam is not None:
                    hole_radius = h_diam / 2.0
                    
                    # Dibujar el agujero (círculo que representa el diámetro del agujero)
                    # El agujero es un cilindro perpendicular al eje principal de la flauta
                    hole_circle = Circle(
                        (h_pos_rel, 0),
                        hole_radius,
                        fill=True,
                        facecolor='white',
                        edgecolor='black',
                        linewidth=0.8,
                        zorder=11
                    )
                    ax.add_patch(hole_circle)
        
        ax.set_title(f"Vista Sólido 2D: {part_name} - {self.flute_data.flute_model}", fontsize=10)
        ax.set_xlabel("Posición (mm)", fontsize=9)
        ax.set_ylabel("Radio (mm)", fontsize=9)
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True, linestyle=':', alpha=0.5)
        
        return ax

    def plot_axial_cut_2d(self, ax: Optional[plt.Axes] = None,
                          plot_label: Optional[str] = None,
                          internal_color: Optional[str] = None,
                          external_color: Optional[str] = None,
                          hole_color: Optional[str] = None,
                          x_axis_origin_offset: float = 0.0,
                          cone_angle_deg: float = 5.0) -> Optional[plt.Axes]:
        """
        Dibuja un corte axial del sólido mostrando ambos perfiles (interno y externo)
        y los agujeros como cortes transversales a través de la pared.
        Similar a visualizador_flauta_3D.py.
        
        Args:
            ax: Eje de matplotlib donde dibujar. Si es None, se crea una nueva figura.
            plot_label: Etiqueta para la leyenda.
            internal_color: Color para el perfil interno.
            external_color: Color para el perfil externo.
            hole_color: Color para los agujeros.
            x_axis_origin_offset: Offset para el eje X.
            cone_angle_deg: Ángulo de conicidad por defecto (solo si no está en JSON).
        
        Returns:
            Eje de matplotlib, o None si no hay datos suficientes.
        
        Nota: El ángulo de conicidad se busca primero en los datos JSON del agujero
              (campos 'cone_angle' o 'Holes cone_angle'). Si no está configurado,
              se usa un cilindro (sin conicidad) en lugar del valor por defecto.
        """
        # Verificar si hay perfil externo disponible
        combined_external = self._get_combined_external_profile()
        combined_measurements = self.flute_data.combined_measurements
        
        if not combined_external or not combined_measurements:
            logger.debug(f"No hay datos suficientes para corte axial en {self.flute_data.flute_model}")
            return None
        
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(18, 6))
        else:
            fig = ax.figure
        
        label_to_use = plot_label if plot_label else self.flute_data.flute_model
        
        # Colores por defecto
        int_color = internal_color if internal_color else 'red'
        ext_color = external_color if external_color else 'blue'
        h_color = hole_color if hole_color else 'gold'
        
        # Extraer posiciones y diámetros internos
        int_positions = np.array([m['position'] for m in combined_measurements])
        int_diameters = np.array([m['diameter'] for m in combined_measurements])
        int_radii = int_diameters / 2.0
        
        # Extraer posiciones y diámetros externos
        ext_positions = np.array([m['position'] for m in combined_external])
        ext_diameters = np.array([m['external_diameter'] for m in combined_external])
        ext_radii = ext_diameters / 2.0
        
        # Ajustar posiciones con el offset
        adjusted_int_positions = int_positions - x_axis_origin_offset
        adjusted_ext_positions = ext_positions - x_axis_origin_offset
        
        # Dibujar perfil interno (superior e inferior)
        ax.plot(adjusted_int_positions, int_radii, 
                color=int_color, linestyle='--', linewidth=1.5, 
                label=f"{label_to_use} (interno)", zorder=5)
        ax.plot(adjusted_int_positions, -int_radii, 
                color=int_color, linestyle='--', linewidth=1.5, 
                zorder=5)
        
        # Dibujar perfil externo (superior e inferior)
        ax.plot(adjusted_ext_positions, ext_radii, 
                color=ext_color, linestyle='-', linewidth=1.5, 
                label=f"{label_to_use} (externo)", zorder=5)
        ax.plot(adjusted_ext_positions, -ext_radii, 
                color=ext_color, linestyle='-', linewidth=1.5, 
                zorder=5)
        
        # Dibujar agujeros como polígonos que muestran el corte a través de la pared
        cone_angle_rad = np.deg2rad(cone_angle_deg)
        current_abs_position = 0.0
        seen_hole_positions = set()  # Para evitar duplicados
        
        for i, part_name in enumerate(FLUTE_PARTS_ORDER):
            part_data = self.flute_data.data.get(part_name, {})
            if not part_data:
                continue
            
            # Calcular posición absoluta de inicio de esta parte
            part_total_length = part_data.get("Total length", 0.0)
            part_mortise_length = part_data.get("Mortise length", 0.0)
            
            if i == 0:  # Headjoint
                part_start_abs = 0.0
                current_abs_position = part_total_length - part_mortise_length
            elif i == 1:  # Body (se inserta en Headjoint)
                hj_data = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                hj_total_length = hj_data.get("Total length", 0.0)
                hj_mortise_length = hj_data.get("Mortise length", 0.0)
                part_start_abs = hj_total_length - hj_mortise_length
                current_abs_position = part_start_abs + part_total_length
            else:  # Foot (se inserta en Body)
                part_start_abs = current_abs_position - part_mortise_length
                current_abs_position = part_start_abs + part_total_length
            
            # Obtener agujeros de esta parte
            hole_positions = part_data.get("Holes position", [])
            hole_diameters = part_data.get("Holes diameter", [])
            side_holes = part_data.get("Side holes", [])
            
            # Procesar formato 2 (Side holes) - preferido si está disponible
            if side_holes and isinstance(side_holes, list) and len(side_holes) > 0:
                for hole_info in side_holes:
                    if isinstance(hole_info, dict):
                        h_pos_rel = hole_info.get('position', 0.0)
                        h_diam = hole_info.get('diameter', 0.0)
                        # Buscar ángulo de conicidad en los datos del agujero o de la parte
                        hole_cone_angle = hole_info.get('cone_angle', hole_info.get('angle', None))
                        if hole_cone_angle is None:
                            # Buscar en los datos de la parte (puede ser una lista)
                            hole_angles = part_data.get("Holes angle", [])
                            hole_cone_angles = part_data.get("Holes cone_angle", [])
                            hole_index = side_holes.index(hole_info) if hole_info in side_holes else None
                            if hole_index is not None and hole_index < len(hole_cone_angles):
                                hole_cone_angle = hole_cone_angles[hole_index]
                            elif hole_index is not None and hole_index < len(hole_angles):
                                # "Holes angle" podría ser el ángulo de inclinación, no conicidad
                                # Por ahora lo ignoramos y usamos cilindro
                                hole_cone_angle = None
                        
                        if h_pos_rel is not None and h_diam is not None:
                            abs_hole_pos = part_start_abs + h_pos_rel
                            if abs_hole_pos not in seen_hole_positions:
                                seen_hole_positions.add(abs_hole_pos)
                                
                                # Interpolar diámetro externo y radio interno en la posición del agujero
                                r_ext_diameter = self._interpolate_external_diameter(
                                    combined_external, abs_hole_pos
                                )
                                r_int = np.interp(abs_hole_pos, int_positions, int_radii)
                                
                                if r_ext_diameter is None:
                                    # Fallback: usar radio interno + espesor estimado
                                    r_ext = r_int + 2.0  # 2mm de espesor por lado (radio)
                                else:
                                    # Convertir diámetro externo a radio
                                    r_ext = r_ext_diameter / 2.0
                                
                                wall_thickness = r_ext - r_int
                                r_outer_hole = h_diam / 2.0
                                
                                # Si hay ángulo de conicidad configurado, usar cono; si no, usar cilindro
                                if hole_cone_angle is not None:
                                    hole_cone_angle_rad = np.deg2rad(float(hole_cone_angle))
                                    change_in_radius = wall_thickness * np.tan(hole_cone_angle_rad)
                                    r_inner_hole = r_outer_hole + change_in_radius
                                else:
                                    # Cilindro: mismo radio en ambas posiciones (externa e interna)
                                    r_inner_hole = r_outer_hole
                                
                                # Asegurar que el radio externo del agujero no sobrepase el borde externo
                                r_outer_hole = min(r_outer_hole, r_ext - 0.1)  # Pequeño margen de seguridad
                                r_inner_hole = min(r_inner_hole, r_ext - 0.1)
                                
                                # Asegurar que el agujero no sobrepase el espesor de la pared
                                # El agujero debe estar contenido entre r_int y r_ext
                                r_outer_hole = min(r_outer_hole, r_ext - 0.1)
                                r_inner_hole = max(r_inner_hole, r_int + 0.1)  # No puede ser menor que el radio interno
                                
                                # Para cilindro, usar el mismo radio en ambas posiciones
                                if hole_cone_angle is None:
                                    # Cilindro: usar el mismo radio en r_ext y r_int
                                    hole_radius = min(r_outer_hole, r_inner_hole)
                                    r_outer_hole = hole_radius
                                    r_inner_hole = hole_radius
                                
                                # Asegurar que el alto del agujero sea exactamente el espesor de la pared
                                # El agujero debe ir desde r_ext hasta r_int (wall_thickness de alto)
                                y_top = r_ext
                                y_bottom = r_int
                                
                                # Crear polígono que muestra el corte del agujero (solo mitad superior)
                                # El alto del polígono es exactamente wall_thickness (y_top - y_bottom)
                                adjusted_hole_pos = abs_hole_pos - x_axis_origin_offset
                                top_points = [
                                    [adjusted_hole_pos - r_outer_hole, y_top],
                                    [adjusted_hole_pos + r_outer_hole, y_top],
                                    [adjusted_hole_pos + r_inner_hole, y_bottom],
                                    [adjusted_hole_pos - r_inner_hole, y_bottom]
                                ]
                                
                                # Dibujar solo polígono superior (mitad superior del instrumento)
                                polygon_top = Polygon(top_points, closed=True, 
                                                     facecolor=h_color, alpha=0.6, 
                                                     edgecolor='black', linewidth=0.8, zorder=10)
                                ax.add_patch(polygon_top)
            
            # Procesar formato 1 (Holes position/diameter) si no se usó formato 2
            elif hole_positions and hole_diameters and len(hole_positions) == len(hole_diameters):
                # Buscar ángulos de conicidad en los datos de la parte
                hole_cone_angles = part_data.get("Holes cone_angle", [])
                
                for idx, (h_pos_rel, h_diam) in enumerate(zip(hole_positions, hole_diameters)):
                    if h_pos_rel is not None and h_diam is not None:
                        abs_hole_pos = part_start_abs + h_pos_rel
                        if abs_hole_pos not in seen_hole_positions:
                            seen_hole_positions.add(abs_hole_pos)
                            
                            # Interpolar diámetro externo y radio interno en la posición del agujero
                            r_ext_diameter = self._interpolate_external_diameter(
                                combined_external, abs_hole_pos
                            )
                            r_int = np.interp(abs_hole_pos, int_positions, int_radii)
                            
                            if r_ext_diameter is None:
                                # Fallback: usar radio interno + espesor estimado
                                r_ext = r_int + 2.0  # 2mm de espesor por lado (radio)
                            else:
                                # Convertir diámetro externo a radio
                                r_ext = r_ext_diameter / 2.0
                            
                            wall_thickness = r_ext - r_int
                            r_outer_hole = h_diam / 2.0
                            
                            # Si hay ángulo de conicidad configurado, usar cono; si no, usar cilindro
                            hole_has_cone_angle = idx < len(hole_cone_angles) and hole_cone_angles[idx] is not None
                            if hole_has_cone_angle:
                                hole_cone_angle_rad = np.deg2rad(float(hole_cone_angles[idx]))
                                change_in_radius = wall_thickness * np.tan(hole_cone_angle_rad)
                                r_inner_hole = r_outer_hole + change_in_radius
                            else:
                                # Cilindro: mismo radio en ambas posiciones (externa e interna)
                                r_inner_hole = r_outer_hole
                            
                            # Asegurar que el radio externo del agujero no sobrepase el borde externo
                            r_outer_hole = min(r_outer_hole, r_ext - 0.1)  # Pequeño margen de seguridad
                            r_inner_hole = min(r_inner_hole, r_ext - 0.1)
                            
                            # Asegurar que el agujero no sobrepase el espesor de la pared
                            # El agujero debe estar contenido entre r_int y r_ext
                            r_outer_hole = min(r_outer_hole, r_ext - 0.1)
                            r_inner_hole = max(r_inner_hole, r_int + 0.1)  # No puede ser menor que el radio interno
                            
                            # Para cilindro, usar el mismo radio en ambas posiciones
                            if not hole_has_cone_angle:
                                # Cilindro: usar el mismo radio en r_ext y r_int
                                hole_radius = min(r_outer_hole, r_inner_hole)
                                r_outer_hole = hole_radius
                                r_inner_hole = hole_radius
                            
                            # Asegurar que el alto del agujero sea exactamente el espesor de la pared
                            # El agujero debe ir desde r_ext hasta r_int (wall_thickness de alto)
                            y_top = r_ext
                            y_bottom = r_int
                            
                            # Crear polígono que muestra el corte del agujero (solo mitad superior)
                            # El alto del polígono es exactamente wall_thickness (y_top - y_bottom)
                            adjusted_hole_pos = abs_hole_pos - x_axis_origin_offset
                            top_points = [
                                [adjusted_hole_pos - r_outer_hole, y_top],
                                [adjusted_hole_pos + r_outer_hole, y_top],
                                [adjusted_hole_pos + r_inner_hole, y_bottom],
                                [adjusted_hole_pos - r_inner_hole, y_bottom]
                            ]
                            
                            # Dibujar solo polígono superior (mitad superior del instrumento)
                            polygon_top = Polygon(top_points, closed=True,
                                                 facecolor=h_color, alpha=0.6,
                                                 edgecolor='black', linewidth=0.8, zorder=10)
                            ax.add_patch(polygon_top)
        
        ax.set_title(f"Corte Axial del Sólido: {self.flute_data.flute_model}", fontsize=10)
        ax.set_xlabel("Posición (mm)", fontsize=9)
        ax.set_ylabel("Radio (mm)", fontsize=9)
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.legend()
        
        return ax

    def plot_individual_part_axial_cut_2d(self, part_name: str, ax: Optional[plt.Axes] = None,
                                          plot_label: Optional[str] = None,
                                          internal_color: Optional[str] = None,
                                          external_color: Optional[str] = None,
                                          hole_color: Optional[str] = None) -> Optional[plt.Axes]:
        """
        Dibuja un corte axial del sólido para una parte individual.
        
        Args:
            part_name: Nombre de la parte (ej: 'headjoint', 'body', 'foot').
            ax: Eje de matplotlib donde dibujar. Si es None, se crea una nueva figura.
            plot_label: Etiqueta para la leyenda.
            internal_color: Color para el perfil interno.
            external_color: Color para el perfil externo.
            hole_color: Color para los agujeros.
            Nota: El ángulo de conicidad se obtiene de los datos JSON si está disponible.
                  Si no está configurado, se usa un cilindro (sin conicidad).
        
        Returns:
            Eje de matplotlib, o None si no hay datos suficientes.
        """
        # Verificar si hay perfil externo para esta parte
        if not hasattr(self.flute_data, 'external_geometry'):
            return None
        
        external_geometry = getattr(self.flute_data, 'external_geometry', {})
        external_measurements = external_geometry.get(part_name, [])
        
        if not external_measurements:
            logger.debug(f"No hay perfil externo disponible para parte '{part_name}'")
            return None
        
        part_data = self.flute_data.data.get(part_name, {})
        if not part_data:
            return None
        
        measurements = part_data.get("measurements", [])
        if not measurements:
            return None
        
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 6))
        else:
            fig = ax.figure
        
        label_to_use = plot_label if plot_label else f"{part_name} - {self.flute_data.flute_model}"
        
        # Colores por defecto
        int_color = internal_color if internal_color else 'red'
        ext_color = external_color if external_color else 'blue'
        h_color = hole_color if hole_color else 'gold'
        
        # Extraer posiciones y diámetros internos
        int_positions = np.array([m.get('position', 0.0) for m in measurements])
        int_diameters = np.array([m.get('diameter', 0.0) for m in measurements])
        int_radii = int_diameters / 2.0
        
        # Extraer posiciones y diámetros externos
        ext_positions = np.array([m.get('position', 0.0) for m in external_measurements])
        ext_diameters = np.array([m.get('external_diameter', 0.0) for m in external_measurements])
        ext_radii = ext_diameters / 2.0
        
        # Dibujar perfil interno (superior e inferior)
        ax.plot(int_positions, int_radii, 
                color=int_color, linestyle='--', linewidth=1.5, 
                label=f"{label_to_use} (interno)", zorder=5)
        ax.plot(int_positions, -int_radii, 
                color=int_color, linestyle='--', linewidth=1.5, 
                zorder=5)
        
        # Dibujar perfil externo (superior e inferior)
        ax.plot(ext_positions, ext_radii, 
                color=ext_color, linestyle='-', linewidth=1.5, 
                label=f"{label_to_use} (externo)", zorder=5)
        ax.plot(ext_positions, -ext_radii, 
                color=ext_color, linestyle='-', linewidth=1.5, 
                zorder=5)
        
        # Dibujar agujeros como polígonos que muestran el corte a través de la pared
        hole_positions = part_data.get("Holes position", [])
        hole_diameters = part_data.get("Holes diameter", [])
        side_holes = part_data.get("Side holes", [])
        
        # Procesar formato 2 (Side holes) - preferido si está disponible
        if side_holes and isinstance(side_holes, list) and len(side_holes) > 0:
            for hole_info in side_holes:
                if isinstance(hole_info, dict):
                    h_pos_rel = hole_info.get('position', 0.0)
                    h_diam = hole_info.get('diameter', 0.0)
                    # Buscar ángulo de conicidad en los datos del agujero o de la parte
                    hole_cone_angle = hole_info.get('cone_angle', hole_info.get('angle', None))
                    if hole_cone_angle is None:
                        # Buscar en los datos de la parte (puede ser una lista)
                        hole_cone_angles = part_data.get("Holes cone_angle", [])
                        hole_index = side_holes.index(hole_info) if hole_info in side_holes else None
                        if hole_index is not None and hole_index < len(hole_cone_angles):
                            hole_cone_angle = hole_cone_angles[hole_index]
                    
                    if h_pos_rel is not None and h_diam is not None:
                        # Interpolar diámetro externo y radio interno en la posición del agujero
                        r_ext_diameter = self._interpolate_external_diameter(
                            external_measurements, h_pos_rel
                        )
                        r_int = np.interp(h_pos_rel, int_positions, int_radii)
                        
                        if r_ext_diameter is None:
                            # Fallback: usar radio interno + espesor estimado
                            r_ext = r_int + 2.0  # 2mm de espesor por lado (radio)
                        else:
                            # Convertir diámetro externo a radio
                            r_ext = r_ext_diameter / 2.0
                        
                        wall_thickness = r_ext - r_int
                        r_outer_hole = h_diam / 2.0
                        
                        # Si hay ángulo de conicidad configurado, usar cono; si no, usar cilindro
                        if hole_cone_angle is not None:
                            hole_cone_angle_rad = np.deg2rad(float(hole_cone_angle))
                            change_in_radius = wall_thickness * np.tan(hole_cone_angle_rad)
                            r_inner_hole = r_outer_hole + change_in_radius
                        else:
                            # Cilindro: mismo radio en ambas posiciones (externa e interna)
                            r_inner_hole = r_outer_hole
                        
                        # Asegurar que el radio externo del agujero no sobrepase el borde externo
                        r_outer_hole = min(r_outer_hole, r_ext - 0.1)  # Pequeño margen de seguridad
                        r_inner_hole = min(r_inner_hole, r_ext - 0.1)
                        
                        # Asegurar que el agujero no sobrepase el espesor de la pared
                        # El agujero debe estar contenido entre r_int y r_ext
                        r_outer_hole = min(r_outer_hole, r_ext - 0.1)
                        r_inner_hole = max(r_inner_hole, r_int + 0.1)  # No puede ser menor que el radio interno
                        
                        # Para cilindro, usar el mismo radio en ambas posiciones
                        if hole_cone_angle is None:
                            # Cilindro: usar el mismo radio en r_ext y r_int
                            hole_radius = min(r_outer_hole, r_inner_hole)
                            r_outer_hole = hole_radius
                            r_inner_hole = hole_radius
                        
                        # Crear polígono que muestra el corte del agujero (solo mitad superior)
                        top_points = [
                            [h_pos_rel - r_outer_hole, r_ext],
                            [h_pos_rel + r_outer_hole, r_ext],
                            [h_pos_rel + r_inner_hole, r_int],
                            [h_pos_rel - r_inner_hole, r_int]
                        ]
                        
                        # Dibujar solo polígono superior (mitad superior del instrumento)
                        polygon_top = Polygon(top_points, closed=True,
                                             facecolor=h_color, alpha=0.6,
                                             edgecolor='black', linewidth=0.8, zorder=10)
                        ax.add_patch(polygon_top)
        
        # Procesar formato 1 (Holes position/diameter) si no se usó formato 2
        elif hole_positions and hole_diameters and len(hole_positions) == len(hole_diameters):
            # Buscar ángulos de conicidad en los datos de la parte
            hole_cone_angles = part_data.get("Holes cone_angle", [])
            
            for idx, (h_pos_rel, h_diam) in enumerate(zip(hole_positions, hole_diameters)):
                if h_pos_rel is not None and h_diam is not None:
                    # Interpolar diámetro externo y radio interno en la posición del agujero
                    r_ext_diameter = self._interpolate_external_diameter(
                        external_measurements, h_pos_rel
                    )
                    r_int = np.interp(h_pos_rel, int_positions, int_radii)
                    
                    if r_ext_diameter is None:
                        # Fallback: usar radio interno + espesor estimado
                        r_ext = r_int + 2.0  # 2mm de espesor por lado (radio)
                    else:
                        # Convertir diámetro externo a radio
                        r_ext = r_ext_diameter / 2.0
                    
                    wall_thickness = r_ext - r_int
                    r_outer_hole = h_diam / 2.0
                    
                    # Si hay ángulo de conicidad configurado, usar cono; si no, usar cilindro
                    hole_has_cone_angle = idx < len(hole_cone_angles) and hole_cone_angles[idx] is not None
                    if hole_has_cone_angle:
                        hole_cone_angle_rad = np.deg2rad(float(hole_cone_angles[idx]))
                        change_in_radius = wall_thickness * np.tan(hole_cone_angle_rad)
                        r_inner_hole = r_outer_hole + change_in_radius
                    else:
                        # Cilindro: mismo radio en ambas posiciones (externa e interna)
                        r_inner_hole = r_outer_hole
                    
                    # Asegurar que el radio externo del agujero no sobrepase el borde externo
                    r_outer_hole = min(r_outer_hole, r_ext - 0.1)  # Pequeño margen de seguridad
                    r_inner_hole = min(r_inner_hole, r_ext - 0.1)
                    
                    # Asegurar que el agujero no sobrepase el espesor de la pared
                    # El agujero debe estar contenido entre r_int y r_ext
                    r_outer_hole = min(r_outer_hole, r_ext - 0.1)
                    r_inner_hole = max(r_inner_hole, r_int + 0.1)  # No puede ser menor que el radio interno
                    
                    # Para cilindro, usar el mismo radio en ambas posiciones
                    if not hole_has_cone_angle:
                        # Cilindro: usar el mismo radio en r_ext y r_int
                        hole_radius = min(r_outer_hole, r_inner_hole)
                        r_outer_hole = hole_radius
                        r_inner_hole = hole_radius
                    
                    # Asegurar que el alto del agujero sea exactamente el espesor de la pared
                    # El agujero debe ir desde r_ext hasta r_int (wall_thickness de alto)
                    y_top = r_ext
                    y_bottom = r_int
                    
                    # Crear polígono que muestra el corte del agujero (solo mitad superior)
                    # El alto del polígono es exactamente wall_thickness (y_top - y_bottom)
                    top_points = [
                        [h_pos_rel - r_outer_hole, y_top],
                        [h_pos_rel + r_outer_hole, y_top],
                        [h_pos_rel + r_inner_hole, y_bottom],
                        [h_pos_rel - r_inner_hole, y_bottom]
                    ]
                    
                    # Dibujar solo polígono superior (mitad superior del instrumento)
                    polygon_top = Polygon(top_points, closed=True,
                                         facecolor=h_color, alpha=0.6,
                                         edgecolor='black', linewidth=0.8, zorder=10)
                    ax.add_patch(polygon_top)
        
        ax.set_title(f"Corte Axial: {part_name} - {self.flute_data.flute_model}", fontsize=10)
        ax.set_xlabel("Posición (mm)", fontsize=9)
        ax.set_ylabel("Radio (mm)", fontsize=9)
        ax.set_aspect('equal', adjustable='box')
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.legend()
        
        return ax

    def plot_physical_assembly(self, ax: plt.Axes,
                               plot_label_suffix: Optional[str] = None,
                               overall_linestyle: Optional[str] = None) -> float:
        """Dibuja el ensamblaje físico estimado de las partes de la flauta en el eje proporcionado."""
        flute_model_name = self.flute_data.flute_model

        # --- Subplot Superior: Ensamblaje Físico con Solapamientos ---
        ax.set_title(f"Ensamblaje Físico Estimado (con solapamientos): {flute_model_name}", fontsize=10)
        ax.set_xlabel("Posición Absoluta Estimada (mm)", fontsize=9)
        logger.debug(f"Plotting PHYSICAL assembly. Number of parts in FLUTE_PARTS_ORDER: {len(FLUTE_PARTS_ORDER)}")
        ax.set_ylabel("Diámetro (mm)", fontsize=9)
        # ax_physical.grid(True, linestyle=':', alpha=0.7) # Grid se establece en GUI
        
        # current_physical_plot_start_abs: dónde comienza la parte actual físicamente en el gráfico.
        current_physical_plot_start_abs = 0.0
        # next_part_connection_point_abs: dónde se conectará la siguiente parte (final acústico de la actual).
        next_part_connection_point_abs = 0.0
        overall_max_x_physical = 0.0
        main_flute_label_applied = False
        headjoint_data_for_stopper = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})

        physical_plots_made = 0
        for i, part_name in enumerate(FLUTE_PARTS_ORDER):
            part_data = self.flute_data.data.get(part_name, {})
            if not part_data:
                logger.debug(f"  Part '{part_name}': No data found. Skipping physical plot for this part.")
                continue
            
            measurements = sorted(part_data.get("measurements", []), key=lambda m: m.get("position", 0.0))
            if not measurements:
                logger.debug(f"  Part '{part_name}': No measurements found. Skipping physical plot for this part.")
                continue
            part_total_length = part_data.get("Total length", 0.0)
            part_json_mortise_length = part_data.get("Mortise length", 0.0) # Profundidad del socket de esta parte

            # Determinar dónde comienza a dibujarse esta parte físicamente
            if i == 0: # Headjoint
                current_physical_plot_start_abs = 0.0
            elif i == 1: # Left (se inserta en Headjoint)
                # Left comienza donde termina el cuerpo de Headjoint (antes del socket de HJ)
                hj_data = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                hj_total_length = hj_data.get("Total length", 0.0)
                hj_mortise_length = hj_data.get("Mortise length", 0.0)
                current_physical_plot_start_abs = hj_total_length - hj_mortise_length
            else: # Right, Foot (se insertan en la anterior)
                # El inicio físico de Right/Foot es el final físico de Left/Right menos el socket de Right/Foot
                # Usamos el next_part_connection_point_abs calculado en la iteración anterior,
                # y restamos el socket de la parte actual para encontrar su inicio físico.
                current_physical_plot_start_abs = next_part_connection_point_abs - part_json_mortise_length


            part_plot_positions = [m['position'] + current_physical_plot_start_abs for m in measurements]
            part_plot_diameters = [m['diameter'] for m in measurements]

            color = BASE_COLORS[i % len(BASE_COLORS)]
            
            # Aplicar la etiqueta principal solo a la primera parte de la flauta
            current_part_plot_label = None
            if not main_flute_label_applied and plot_label_suffix and plot_label_suffix != "_nolegend_":
                current_part_plot_label = plot_label_suffix
                main_flute_label_applied = True
            
            linestyle_part = overall_linestyle if overall_linestyle else '-'
            
            ax.plot(part_plot_positions, part_plot_diameters, label=current_part_plot_label, color=color, linestyle=linestyle_part, alpha=0.7, zorder=i*2)

            # Resaltar la región del socket de esta parte (si lo tiene y es relevante)
            if part_name == FLUTE_PARTS_ORDER[0]: # Headjoint (socket al final)
                socket_start_abs = current_physical_plot_start_abs + part_total_length - part_json_mortise_length
                socket_end_abs = current_physical_plot_start_abs + part_total_length
                ax.axvspan(socket_start_abs, socket_end_abs, alpha=0.2, color=color, label=None, zorder=i*2-1)
                next_part_connection_point_abs = socket_start_abs # Left se conecta al inicio del socket de HJ
            elif part_name == FLUTE_PARTS_ORDER[1]: # Left (no tiene socket propio que afecte el ensamblaje así)
                next_part_connection_point_abs = current_physical_plot_start_abs + part_total_length # Right se conecta al final de Left
            else: # Right, Foot (socket al inicio)
                socket_start_abs = current_physical_plot_start_abs
                socket_end_abs = current_physical_plot_start_abs + part_json_mortise_length
                ax.axvspan(socket_start_abs, socket_end_abs, alpha=0.2, color=color, label=None, zorder=i*2-1)
                if part_name == FLUTE_PARTS_ORDER[2]: # Right
                     next_part_connection_point_abs = current_physical_plot_start_abs + part_total_length # Foot se conecta al final de Right
            
            if part_plot_positions:
                overall_max_x_physical = max(overall_max_x_physical, part_plot_positions[-1])
            else:
                overall_max_x_physical = max(overall_max_x_physical, current_physical_plot_start_abs + part_total_length)


            logger.debug(f"  Part '{part_name}': Plotted physical data. Number of measurement points: {len(measurements)}")
            physical_plots_made +=1
        logger.debug(f"Total physical part plots made: {physical_plots_made}")

        # Añadir marcador de corcho después de dibujar todas las partes de esta flauta
        stopper_pos_mm = headjoint_data_for_stopper.get('_calculated_stopper_absolute_position_mm')
        if stopper_pos_mm is not None:
            min_diam_marker, max_diam_marker = ax.get_ylim()
            # Usar una fracción del rango y para la altura del marcador, similar a plot_combined_flute_data
            marker_y_bottom = min_diam_marker + 0.05 * (max_diam_marker - min_diam_marker)
            marker_y_top = max_diam_marker - 0.05 * (max_diam_marker - min_diam_marker)
            ax.vlines(stopper_pos_mm, marker_y_bottom, marker_y_top, 
                      colors='purple', linestyles='dashdot', alpha=0.8, label=None) # No añadir a la leyenda principal

        # La leyenda y xlim se manejan en la GUI para el consolidado
        return overall_max_x_physical

    def plot_physical_assembly_and_acoustic_profile(self, fig: Optional[plt.Figure] = None) -> plt.Figure:
        """
        Genera una figura con dos subplots:
        1. Ensamblaje físico de las partes, mostrando solapamientos de espigas/cajas.
        2. Perfil acústico interno combinado resultante.
        """
        logger.debug(f"ENTERING plot_physical_assembly_and_acoustic_profile for {self.flute_data.flute_model}")
        if fig is None:
            fig, (ax_physical, ax_acoustic) = plt.subplots(2, 1, figsize=(18, 12), sharex=False) # Aumentar altura
        else:
            fig.clear()
            ax_physical, ax_acoustic = fig.subplots(2, 1, sharex=False)

        # --- Subplot Superior: Ensamblaje Físico ---
        max_x_phys = self.plot_physical_assembly(ax=ax_physical, plot_label_suffix=self.flute_data.flute_model)
        handles_phys, labels_phys = ax_physical.get_legend_handles_labels()
        by_label_phys = dict(zip(labels_phys, handles_phys)); ax_physical.legend(by_label_phys.values(), by_label_phys.keys(), fontsize='small', loc='best')
        if max_x_phys > 0 : ax_physical.set_xlim(-10, max_x_phys + 10)

        # --- Subplot Inferior: Perfil Acústico Combinado ---
        ax_acoustic.set_title(f"Perfil Acústico Interno Combinado (desde FluteData): {self.flute_data.flute_model}", fontsize=10)
        ax_acoustic.set_xlabel("Posición (mm) desde el corcho", fontsize=9)
        ax_acoustic.set_ylabel("Diámetro (mm)", fontsize=9)
        ax_acoustic.grid(True, linestyle=':', alpha=0.7)
        logger.debug(f"Plotting ACOUSTIC profile. Number of combined_measurements: {len(self.flute_data.combined_measurements)}")

        if self.flute_data.combined_measurements:
            acoustic_positions = [m['position'] for m in self.flute_data.combined_measurements]
            acoustic_diameters = [m['diameter'] for m in self.flute_data.combined_measurements]
            ax_acoustic.plot(acoustic_positions, acoustic_diameters, label="Perfil Acústico (de FluteData)", color='black')
            logger.debug("  Acoustic profile plotted.")
            
            # Superponer marcadores de unión acústica (del método plot_combined_flute_data)
            # Esto usa la lógica interna de plot_combined_flute_data para los marcadores,
            # que debería coincidir con cómo se calcula el perfil acústico.
            # Nota: plot_combined_flute_data espera show_mortise_markers=True para dibujar los marcadores.
            # También espera plot_label para la leyenda, usamos "_nolegend_" para evitar duplicar la leyenda principal.
            logger.debug("  Calling self.plot_combined_flute_data for acoustic markers.")
            self.plot_combined_flute_data(ax=ax_acoustic, show_mortise_markers=True, plot_label="_nolegend_") 
            logger.debug("  Finished calling self.plot_combined_flute_data for acoustic markers.")

            ax_acoustic.legend(fontsize='small', loc='best')
            if acoustic_positions: ax_acoustic.set_xlim(min(acoustic_positions)-10 if acoustic_positions else 0, max(acoustic_positions)+10 if acoustic_positions else 100)
        else:
            ax_acoustic.text(0.5, 0.5, "No hay datos de perfil acústico combinado.", ha='center', va='center', transform=ax_acoustic.transAxes)
            logger.debug("  No combined_measurements to plot for acoustic profile.")

        try:
            fig.tight_layout(rect=[0, 0, 1, 0.97])
        except Exception as e_layout:
            logger.error(f"Error during fig.tight_layout in plot_physical_assembly_and_acoustic_profile: {e_layout}", exc_info=True)

        logger.debug(f"EXITING plot_physical_assembly_and_acoustic_profile for {self.flute_data.flute_model}")
        return fig

    def plot_flute_2d_view(self, ax: Optional[plt.Axes] = None,
                           plot_label: Optional[str] = None, 
                           flute_color: Optional[str] = None, flute_style: Optional[str] = None) -> plt.Axes:
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(15, 4))
        else:
            fig = ax.figure
            ax.clear() # Limpiar si se reutiliza para una sola flauta

        combined_measurements = self.flute_data.combined_measurements
        if not combined_measurements:
            logger.warning(f"No hay mediciones combinadas para {self.flute_data.flute_model} en plot_flute_2d_view.")
            ax.text(0.5, 0.5, "No hay datos de mediciones combinadas", ha='center', va='center', transform=ax.transAxes)
            ax.set_title("Vista 2D de la Flauta" + (f" - {self.flute_data.flute_model}" if self.flute_data.flute_model else ""))
            return ax

        positions = [item["position"] for item in combined_measurements]
        diameters = [item["diameter"] for item in combined_measurements]

        label_to_use = plot_label if plot_label else self.flute_data.flute_model

        ax.plot(positions, [d / 2.0 for d in diameters],
                color=flute_color if flute_color else BASE_COLORS[0],
                linestyle=flute_style if flute_style else LINESTYLES[0],
                linewidth=2, label=label_to_use)
        ax.plot(positions, [-d / 2.0 for d in diameters],
                color=flute_color if flute_color else BASE_COLORS[0],
                linestyle=flute_style if flute_style else LINESTYLES[0],
                linewidth=2)

        ax.set_xlabel("Posición (mm)")
        ax.set_ylabel("Radio (mm)")
        ax.set_aspect('equal', adjustable='datalim')
        if label_to_use: ax.legend(loc='best', fontsize=9)
        ax.grid(True, linestyle=':', alpha=0.7)
        title_str = "Vista 2D de la Flauta"
        if self.flute_data.flute_model and self.flute_data.flute_model != label_to_use:
            title_str += f" ({self.flute_data.flute_model})"
        ax.set_title(title_str)
        return ax

    def plot_instrument_geometry(self, note: str = "D", ax: Optional[plt.Axes] = None) -> Optional[plt.Axes]:
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 4))
        else:
            fig = ax.figure
            ax.clear()

        try:
            if note not in self.flute_data.acoustic_analysis or not self.flute_data.acoustic_analysis[note]:
                msg = f"Análisis para nota '{note}' no disponible"
                logger.warning(f"{msg} en {self.flute_data.flute_model}.")
                ax.text(0.5,0.5, msg, ha='center', transform=ax.transAxes)
                ax.set_title(f"Geometría del Instrumento ({note}) - {self.flute_data.flute_model}")
                return ax

            acoustic_analysis_obj = self.flute_data.acoustic_analysis[note]
            if not is_impedance_computation_like(acoustic_analysis_obj):
                 msg = f"Datos de análisis inválidos para nota '{note}'"
                 logger.warning(f"{msg} en {self.flute_data.flute_model}.")
                 ax.text(0.5,0.5, msg, ha='center', transform=ax.transAxes)
                 ax.set_title(f"Geometría del Instrumento ({note}) - {self.flute_data.flute_model}")
                 return ax

            # Solo plot_instrument_geometry si es ImpedanceComputation real
            # CachedImpedanceComputation no tiene este método
            if isinstance(acoustic_analysis_obj, ImpedanceComputation):
                acoustic_analysis_obj.plot_instrument_geometry(ax=ax)
            else:
                # Para CachedImpedanceComputation, mostrar mensaje o usar geometría alternativa
                ax.text(0.5, 0.5, "Geometría detallada no disponible desde cache.\nUse datos originales para ver geometría completa.",
                       ha='center', va='center', transform=ax.transAxes, fontsize=9)

            ax.set_title(f"Geometría (Openwind) para {note} - {self.flute_data.flute_model}", fontsize=10)
            ax.set_xlabel("Posición relativa al corcho (m)")
            ax.set_ylabel("Radio (m)")
            ax.grid(True, linestyle=':', alpha=0.7)
            return ax
        except Exception as e:
            logger.error(f"Error graficando geometría del instrumento para nota {note} en {self.flute_data.flute_model}: {e}")
            ax.text(0.5,0.5, f"Error graficando geometría para '{note}'", ha='center', transform=ax.transAxes, color='red')
            ax.set_title(f"Geometría del Instrumento ({note}) - Error", fontsize=10)
            return ax
        
    @staticmethod
    def _plot_shape_static(shape_data: Tuple[np.ndarray, np.ndarray], ax: plt.Axes, mmeter_conversion: float, **kwargs: Any) -> None:
        x_m, r_m = shape_data
        x_plot = x_m * mmeter_conversion
        r_plot = r_m * mmeter_conversion
        radius_to_plot = np.concatenate([r_plot, [np.nan], np.flip(-r_plot)])
        position_to_plot = np.concatenate([x_plot, [np.nan], np.flip(x_plot)])
        ax.plot(position_to_plot, radius_to_plot, **kwargs)

    @staticmethod
    def _get_fingering_from_file(fing_chart_file: str, note: str) -> Dict[str, bool]:
        """
        Lee el archivo de digitaciones y retorna el estado (abierto/cerrado) de cada agujero para una nota.
        
        Args:
            fing_chart_file: Ruta al archivo de digitaciones.
            note: Nota musical (ej: 'D', 'E', 'Fs').
        
        Returns:
            Diccionario {hole_label: is_open} para cada agujero.
        """
        fingering_dict = {}
        try:
            logger.debug(f"Leyendo digitación para nota '{note}' desde archivo: {fing_chart_file}")
            with open(fing_chart_file, 'r', encoding='utf-8') as f:
                lines = [line.strip().split() for line in f if line.strip() and not line.startswith('#')]
            
            if not lines or len(lines) < 2:
                logger.warning(f"Archivo de digitaciones vacío o inválido: {fing_chart_file}")
                return fingering_dict
            
            # Primera línea es el encabezado
            header = lines[0]
            logger.debug(f"Encabezado del archivo de digitaciones: {header}")
            
            if 'label' not in [h.lower() for h in header]:
                logger.warning(f"Encabezado de digitaciones no contiene 'label': {fing_chart_file}, header={header}")
                return fingering_dict
            
            # Normalizar nota para comparación (convertir a minúsculas y manejar variantes)
            note_normalized = note.strip()
            # Mapeo de variantes comunes
            note_variants = {
                'f#': 'fs', 'fsharp': 'fs', 'f_sharp': 'fs',
                'c#': 'cs', 'csharp': 'cs', 'c_sharp': 'cs'
            }
            if note_normalized.lower() in note_variants:
                note_normalized = note_variants[note_normalized.lower()]
            
            # Encontrar índice de la nota en el encabezado (comparación case-insensitive)
            note_idx = None
            for idx, col in enumerate(header):
                if col.strip().lower() == note_normalized.lower():
                    note_idx = idx
                    break
            
            if note_idx is None:
                logger.warning(f"Nota '{note}' (normalizada: '{note_normalized}') no encontrada en archivo de digitaciones: {fing_chart_file}. Encabezado disponible: {header}")
                return fingering_dict
            
            logger.debug(f"Nota '{note}' encontrada en columna {note_idx} del archivo de digitaciones")
            
            # Leer cada línea (agujero)
            for row in lines[1:]:
                if not row or len(row) <= note_idx:
                    continue
                
                hole_label = row[0].lower().strip()
                # 'o' = abierto (círculo vacío), 'x' = cerrado (tapado, cruzado)
                state_char = row[note_idx].strip().lower() if note_idx < len(row) else 'o'
                is_open = (state_char == 'o')
                
                fingering_dict[hole_label] = is_open
                logger.debug(f"  Agujero '{hole_label}': {'abierto' if is_open else 'cerrado'} para nota '{note}'")
            
            logger.info(f"Digitación cargada para nota '{note}': {len(fingering_dict)} agujeros encontrados")
            
        except FileNotFoundError:
            logger.warning(f"Archivo de digitaciones no encontrado: {fing_chart_file}")
        except Exception as e:
            logger.error(f"Error leyendo archivo de digitaciones {fing_chart_file}: {e}", exc_info=True)
        
        return fingering_dict
    
    def _plot_holes_static(
        holes_info: List[Dict[str, Any]], 
        ax: plt.Axes,
        mmeter_conversion: float,
        default_color: str = 'black',
        show_labels: bool = True,
        **kwargs: Any) -> None:
        """
        Dibuja agujeros en el gráfico con visualización mejorada de digitación.
        
        Args:
            holes_info: Lista de diccionarios con información de agujeros.
            ax: Eje de matplotlib.
            mmeter_conversion: Factor de conversión de metros a milímetros.
            default_color: Color por defecto.
            show_labels: Si True, muestra etiquetas con nombres de agujeros.
            **kwargs: Argumentos adicionales para plot.
        """
        try:
            from matplotlib.patches import Circle
            legend_elements = []
            has_open = False
            has_closed = False
            
            for hole_detail in holes_info:
                pos_m = hole_detail['position_m']
                rad_m = hole_detail['radius_m']
                is_open = hole_detail.get('is_open', True)
                hole_label = hole_detail.get('label', '')
                
                x_center_plot = pos_m * mmeter_conversion
                rad_plot = rad_m * mmeter_conversion
                
                if is_open:
                    # Agujero abierto: círculo azul vacío (solo borde)
                    circle = Circle(
                        (x_center_plot, 0), rad_plot,
                        facecolor='none',
                        edgecolor='blue',
                        linewidth=2.5,
                        zorder=10
                    )
                    ax.add_patch(circle)
                    has_open = True
                else:
                    # Agujero cerrado: círculo verde relleno y opaco
                    circle = Circle(
                        (x_center_plot, 0), rad_plot,
                        facecolor='green',
                        edgecolor='darkgreen',
                        linewidth=2.0,
                        alpha=1.0,
                        zorder=10
                    )
                    ax.add_patch(circle)
                    has_closed = True
                
                # Agregar etiqueta con nombre del agujero
                if show_labels and hole_label:
                    # Posicionar etiqueta arriba del agujero
                    label_color = 'blue' if is_open else 'darkgreen'
                    ax.text(x_center_plot, rad_plot * 2.0, hole_label, 
                           ha='center', va='bottom', fontsize=7, 
                           color=label_color, weight='bold', zorder=11)
            
            # Agregar leyenda si hay ambos tipos
            if has_open or has_closed:
                from matplotlib.patches import Patch
                from matplotlib.lines import Line2D
                legend_items = []
                if has_open:
                    legend_items.append(
                        Line2D([0], [0], color='blue', linewidth=2.5, label='Abierto (o)', 
                               marker='o', markerfacecolor='none', markeredgecolor='blue', markersize=8)
                    )
                if has_closed:
                    legend_items.append(
                        Patch(facecolor='green', edgecolor='darkgreen', linewidth=2, label='Cerrado (x)')
                    )
                ax.legend(handles=legend_items, loc='upper right', fontsize=8)
        except Exception as e:
            logger.error(f"Error graficando agujeros (estático): {e}", exc_info=True)


    def plot_top_view_instrument_geometry(self, note: str = "D", ax: Optional[plt.Axes] = None) -> Optional[plt.Axes]:
        logger.info(f"plot_top_view_instrument_geometry llamado para nota '{note}' en {self.flute_data.flute_model}")
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(15, 3))
        else:
            fig = ax.figure
            ax.clear()

        ax.set_aspect('equal', adjustable='datalim')

        try:
            if note not in self.flute_data.acoustic_analysis or not self.flute_data.acoustic_analysis[note]:
                msg = f"Análisis para nota '{note}' no disponible"
                logger.error(f"{msg} en {self.flute_data.flute_model}")
                ax.text(0.5,0.5, msg, ha='center', transform=ax.transAxes)
            elif not is_impedance_computation_like(self.flute_data.acoustic_analysis[note]):
                msg = f"Datos de análisis inválidos para nota '{note}'"
                logger.error(f"{msg} en {self.flute_data.flute_model}")
                ax.text(0.5,0.5, msg, ha='center', transform=ax.transAxes)
            else:
                analysis_obj = self.flute_data.acoustic_analysis[note]
                instrument_geometry = analysis_obj.get_instrument_geometry() if hasattr(analysis_obj, 'get_instrument_geometry') else None
                
                # Si la geometría viene del cache (CachedImpedanceComputation), usar combined_measurements directamente
                is_cached = hasattr(instrument_geometry, 'is_cached') and instrument_geometry.is_cached if instrument_geometry else False
                
                # Calcular offset del corcho para mostrar solo la parte acústica
                headjoint_data = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                stopper_absolute_position_mm = headjoint_data.get('_calculated_stopper_absolute_position_mm', 0.0)
                
                if not instrument_geometry or is_cached:
                    # Usar combined_measurements directamente (especialmente para objetos cacheados)
                    combined_measurements = self.flute_data.combined_measurements
                    if combined_measurements:
                        try:
                            # Aplicar offset del corcho para mostrar solo la parte acústica
                            positions_mm = np.array([item["position"] - stopper_absolute_position_mm for item in combined_measurements])
                            diameters_mm = np.array([item["diameter"] for item in combined_measurements])
                            radii_mm = diameters_mm / 2.0
                            ax.plot(positions_mm, radii_mm, color='black', linestyle='-', linewidth=1)
                            ax.plot(positions_mm, -radii_mm, color='black', linestyle='-', linewidth=1)
                        except Exception as e_plot_bore:
                            logger.error(f"Error al dibujar el tubo principal usando combined_measurements para {self.flute_data.flute_model}: {e_plot_bore}")
                            ax.text(0.5, 0.5, "Error al dibujar tubo", ha='center', va='center', transform=ax.transAxes, color='red')
                    else:
                        logger.warning(f"No hay mediciones combinadas para {self.flute_data.flute_model} para dibujar el tubo en vista superior.")
                        ax.text(0.5, 0.5, "Error: Geometría del tubo no disponible", ha='center', va='center', transform=ax.transAxes)

                    # Para objetos cacheados, usar datos de la flauta para dibujar agujeros
                    if is_cached:
                        try:
                            # Obtener digitación desde archivo si está disponible
                            fingering_dict = {}
                            if hasattr(self.flute_data, 'fing_chart_file_path') and self.flute_data.fing_chart_file_path:
                                try:
                                    logger.info(f"Cargando digitación para nota '{note}' desde {self.flute_data.fing_chart_file_path}")
                                    fingering_dict = FluteOperations._get_fingering_from_file(
                                        self.flute_data.fing_chart_file_path, note
                                    )
                                    logger.info(f"Digitación cargada desde archivo para nota '{note}': {len(fingering_dict)} agujeros - {fingering_dict}")
                                except Exception as e:
                                    logger.error(f"Error cargando digitación desde archivo: {e}", exc_info=True)
                            else:
                                logger.warning(f"No hay fing_chart_file_path disponible para {self.flute_data.flute_model}")
                            
                            # Usar datos de la flauta para obtener información de agujeros
                            holes_details_for_plot = []
                            
                            # Calcular posiciones físicas absolutas de agujeros, considerando ensamblaje
                            # Replicar la lógica exacta de plot_physical_assembly
                            part_physical_starts = {}
                            next_part_connection_point_abs = 0.0
                            
                            for i, part_name in enumerate(FLUTE_PARTS_ORDER):
                                part_data = self.flute_data.data.get(part_name, {})
                                if not part_data:
                                    continue
                                    
                                part_total_length = part_data.get("Total length", 0.0)
                                part_mortise_length = part_data.get("Mortise length", 0.0)
                                
                                # Determinar dónde comienza físicamente esta parte
                                if i == 0:  # Headjoint
                                    current_physical_plot_start_abs = 0.0
                                    # Left se conecta al inicio del socket de HJ
                                    socket_start_abs = current_physical_plot_start_abs + part_total_length - part_mortise_length
                                    next_part_connection_point_abs = socket_start_abs
                                elif i == 1:  # Left (se inserta en Headjoint)
                                    # Left comienza donde termina el cuerpo de Headjoint (antes del socket de HJ)
                                    hj_data = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                                    hj_total_length = hj_data.get("Total length", 0.0)
                                    hj_mortise_length = hj_data.get("Mortise length", 0.0)
                                    current_physical_plot_start_abs = hj_total_length - hj_mortise_length
                                    # Right se conecta al final de Left
                                    next_part_connection_point_abs = current_physical_plot_start_abs + part_total_length
                                else:  # Right, Foot (se insertan en la anterior)
                                    # El inicio físico es el final de la parte anterior menos el socket de la parte actual
                                    current_physical_plot_start_abs = next_part_connection_point_abs - part_mortise_length
                                    if part_name == FLUTE_PARTS_ORDER[2]:  # Right
                                        # Foot se conecta al final de Right
                                        next_part_connection_point_abs = current_physical_plot_start_abs + part_total_length
                                
                                part_physical_starts[part_name] = current_physical_plot_start_abs
                            
                            # Ahora añadir agujeros con posiciones absolutas
                            # Usar un conjunto para evitar duplicados basados en posición
                            holes_positions_seen = set()  # Para evitar duplicados
                            TOLERANCE_MM = 0.1  # Tolerancia de 0.1mm para considerar agujeros duplicados
                            
                            # Contador global de agujeros (similar a get_openwind_geometry_inputs)
                            # Los agujeros se numeran globalmente: hole1, hole2, hole3, ... hole7
                            # No por parte, sino en orden de aparición en la flauta completa
                            global_hole_counter = 0
                            
                            # Buscar agujeros en múltiples formatos posibles
                            # Primero intentar con FLUTE_PARTS_ORDER, luego buscar en todas las partes disponibles
                            parts_to_check = list(FLUTE_PARTS_ORDER)
                            # Agregar todas las partes disponibles que no estén en FLUTE_PARTS_ORDER
                            all_available_parts = list(self.flute_data.data.keys())
                            for part in all_available_parts:
                                if part not in parts_to_check:
                                    parts_to_check.append(part)
                            
                            logger.debug(f"Buscando agujeros en partes: {parts_to_check} para {self.flute_data.flute_model}, nota {note}")
                            
                            for part_name in parts_to_check:
                                part_data = self.flute_data.data.get(part_name, {})
                                if not part_data:
                                    logger.debug(f"  Parte {part_name}: sin datos")
                                    continue
                                
                                # Verificar que part_data sea un diccionario
                                if not isinstance(part_data, dict):
                                    logger.warning(f"  Parte {part_name}: datos no son un diccionario (tipo: {type(part_data)})")
                                    continue
                                
                                part_start_abs = part_physical_starts.get(part_name, 0.0)
                                
                                # Formato 1: "Holes position" y "Holes diameter" (listas simples)
                                hole_positions = part_data.get("Holes position", [])
                                hole_diameters = part_data.get("Holes diameter", [])
                                
                                # Formato 2: "Side holes" (lista de diccionarios)
                                side_holes = part_data.get("Side holes", [])
                                
                                logger.debug(f"  Parte {part_name}: hole_positions={len(hole_positions) if hole_positions else 0}, "
                                           f"hole_diameters={len(hole_diameters) if hole_diameters else 0}, "
                                           f"side_holes={len(side_holes) if side_holes else 0}, "
                                           f"part_start_abs={part_start_abs:.2f}")
                                
                                # Para headjoint, buscar específicamente el agujero de embocadura
                                if part_name == FLUTE_PARTS_ORDER[0]:  # headjoint
                                    logger.debug(f"  Headjoint detectado, buscando embocadura...")
                                    # Verificar si hay información de embocadura
                                    if hole_positions and hole_diameters and len(hole_positions) > 0:
                                        logger.debug(f"  Headjoint tiene {len(hole_positions)} agujeros en 'Holes position'")
                                
                                # Procesar formato 1 (solo si no hay formato 2, para evitar duplicados)
                                if hole_positions and hole_diameters and not side_holes:
                                    if len(hole_positions) == len(hole_diameters):
                                        for idx, (pos_rel_mm, diam_mm) in enumerate(zip(hole_positions, hole_diameters)):
                                            if pos_rel_mm is not None and diam_mm is not None:
                                                abs_pos_mm = part_start_abs + pos_rel_mm
                                                # Aplicar offset acústico (restar posición del corcho)
                                                acoustic_pos_mm = abs_pos_mm - stopper_absolute_position_mm
                                                pos_m = acoustic_pos_mm / 1000.0
                                                rad_m = (diam_mm / 2.0) / 1000.0
                                                
                                                # Verificar si ya existe un agujero en esta posición (evitar duplicados)
                                                pos_key = round(pos_m * 1000 / TOLERANCE_MM)  # Redondear a múltiplos de tolerancia
                                                if pos_key in holes_positions_seen:
                                                    logger.debug(f"  Agujero duplicado ignorado en posición {pos_m*1000:.2f}mm (parte {part_name})")
                                                    continue
                                                holes_positions_seen.add(pos_key)
                                                
                                                # Usar contador global para numerar agujeros (hole1, hole2, ... hole7)
                                                # Solo contar agujeros de partes que no sean headjoint
                                                if part_name != FLUTE_PARTS_ORDER[0]:  # No contar agujeros del headjoint
                                                    global_hole_counter += 1
                                                    hole_label = f'hole{global_hole_counter}'
                                                else:
                                                    # Para headjoint, usar label especial si existe
                                                    hole_label = 'entrance'
                                                
                                                # Obtener estado desde digitación usando el label global
                                                is_open = fingering_dict.get(hole_label, True)  # Por defecto abierto si no se encuentra
                                                
                                                logger.debug(f"  Agujero en {part_name}, posición {pos_m*1000:.2f}mm: label={hole_label}, is_open={is_open}")
                                                
                                                holes_details_for_plot.append({
                                                    'label': hole_label,
                                                    'position_m': pos_m,
                                                    'radius_m': rad_m,
                                                    'is_open': is_open
                                                })
                                
                                # Procesar formato 2 (Side holes) - preferido si está disponible
                                if side_holes:
                                    for hole_info in side_holes:
                                        if isinstance(hole_info, dict):
                                            pos_rel_mm = hole_info.get("position", hole_info.get("Position", None))
                                            diam_mm = hole_info.get("diameter", hole_info.get("Diameter", None))
                                            hole_label_from_data = hole_info.get("label", hole_info.get("Label", None))
                                            
                                            if pos_rel_mm is not None and diam_mm is not None:
                                                abs_pos_mm = part_start_abs + pos_rel_mm
                                                # Aplicar offset acústico
                                                acoustic_pos_mm = abs_pos_mm - stopper_absolute_position_mm
                                                pos_m = acoustic_pos_mm / 1000.0
                                                rad_m = (diam_mm / 2.0) / 1000.0
                                                
                                                # Verificar si ya existe un agujero en esta posición (evitar duplicados)
                                                pos_key = round(pos_m * 1000 / TOLERANCE_MM)  # Redondear a múltiplos de tolerancia
                                                if pos_key in holes_positions_seen:
                                                    logger.debug(f"  Agujero duplicado ignorado en posición {pos_m*1000:.2f}mm (parte {part_name}, label={hole_label_from_data})")
                                                    continue
                                                holes_positions_seen.add(pos_key)
                                                
                                                # Usar etiqueta del dato o generar una basada en contador global
                                                if hole_label_from_data:
                                                    hole_label = hole_label_from_data.lower().strip()
                                                else:
                                                    # Si no hay label en los datos, usar contador global
                                                    if part_name != FLUTE_PARTS_ORDER[0]:  # No contar agujeros del headjoint
                                                        global_hole_counter += 1
                                                        hole_label = f'hole{global_hole_counter}'
                                                    else:
                                                        hole_label = 'entrance'
                                                
                                                # Obtener estado desde digitación usando el label
                                                is_open = fingering_dict.get(hole_label, True)
                                                
                                                logger.debug(f"  Agujero en {part_name}, posición {pos_m*1000:.2f}mm: label={hole_label}, is_open={is_open}")
                                                
                                                holes_details_for_plot.append({
                                                    'label': hole_label,
                                                    'position_m': pos_m,
                                                    'radius_m': rad_m,
                                                    'is_open': is_open
                                                })
                            if holes_details_for_plot:
                                logger.info(f"Dibujando {len(holes_details_for_plot)} agujeros para {self.flute_data.flute_model}, nota {note}")
                                FluteOperations._plot_holes_static(holes_details_for_plot, ax, M_TO_MM_FACTOR, 
                                                                  default_color='black', show_labels=True)
                            else:
                                logger.warning(f"No se encontraron agujeros para dibujar en {self.flute_data.flute_model}, nota {note}")
                        except Exception as e_holes:
                            logger.error(f"Error dibujando agujeros para {self.flute_data.flute_model}, nota {note}: {e_holes}", exc_info=True)
                    else:
                        # Para objetos ImpedanceComputation reales, usar su geometría
                        holes_details_for_plot = []
                        try:
                            fingering = instrument_geometry.fingering_chart.fingering_of(note)
                            for hole_obj in instrument_geometry.holes:
                                pos_m = hole_obj.position.get_value()
                                rad_m = hole_obj.shape.get_radius_at(0) if hasattr(hole_obj.shape, 'get_radius_at') else 0.003 
                                is_open = fingering.is_side_comp_open(hole_obj.label)
                                holes_details_for_plot.append({
                                    'label': hole_obj.label, 'position_m': pos_m, 'radius_m': rad_m, 'is_open': is_open
                                })
                        except Exception as e_holes:
                            logger.warning(f"Error obteniendo agujeros desde instrument_geometry para {self.flute_data.flute_model}, nota {note}: {e_holes}. Intentando desde datos de flauta...")
                        
                        # Si no se encontraron agujeros desde la geometría, intentar desde datos de flauta
                        if not holes_details_for_plot:
                            try:
                                # Obtener digitación desde archivo
                                fingering_dict = {}
                                if hasattr(self.flute_data, 'fing_chart_file_path') and self.flute_data.fing_chart_file_path:
                                    try:
                                        fingering_dict = FluteOperations._get_fingering_from_file(
                                            self.flute_data.fing_chart_file_path, note
                                        )
                                    except Exception as e:
                                        logger.warning(f"Error cargando digitación desde archivo: {e}")
                                
                                # Calcular posiciones físicas absolutas de agujeros
                                # Replicar la lógica exacta de ensamblaje acústico
                                part_physical_starts = {}
                                next_part_connection_point_abs = 0.0
                                
                                for i, part_name in enumerate(FLUTE_PARTS_ORDER):
                                    part_data = self.flute_data.data.get(part_name, {})
                                    if not part_data:
                                        continue
                                        
                                    part_total_length = part_data.get("Total length", 0.0)
                                    part_mortise_length = part_data.get("Mortise length", 0.0)
                                    
                                    # Determinar dónde comienza físicamente esta parte
                                    if i == 0:  # Headjoint
                                        current_physical_plot_start_abs = 0.0
                                        # Left se conecta al inicio del socket de HJ
                                        socket_start_abs = current_physical_plot_start_abs + part_total_length - part_mortise_length
                                        next_part_connection_point_abs = socket_start_abs
                                    elif i == 1:  # Left (se inserta en Headjoint)
                                        # Left comienza donde termina el cuerpo de Headjoint (antes del socket de HJ)
                                        hj_data = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                                        hj_total_length = hj_data.get("Total length", 0.0)
                                        hj_mortise_length = hj_data.get("Mortise length", 0.0)
                                        current_physical_plot_start_abs = hj_total_length - hj_mortise_length
                                        # Right se conecta al final de Left
                                        next_part_connection_point_abs = current_physical_plot_start_abs + part_total_length
                                    else:  # Right, Foot (se insertan en la anterior)
                                        # El inicio físico es el final de la parte anterior menos el socket de la parte actual
                                        current_physical_plot_start_abs = next_part_connection_point_abs - part_mortise_length
                                        if part_name == FLUTE_PARTS_ORDER[2]:  # Right
                                            # Foot se conecta al final de Right
                                            next_part_connection_point_abs = current_physical_plot_start_abs + part_total_length
                                    
                                    part_physical_starts[part_name] = current_physical_plot_start_abs
                                
                                # Buscar agujeros en múltiples formatos
                                # Usar un conjunto para evitar duplicados basados en posición
                                holes_positions_seen = set()  # Para evitar duplicados
                                TOLERANCE_MM = 0.1  # Tolerancia de 0.1mm para considerar agujeros duplicados
                                
                                # Contador global de agujeros (similar a get_openwind_geometry_inputs)
                                global_hole_counter = 0
                                
                                for part_name in FLUTE_PARTS_ORDER:
                                    part_data = self.flute_data.data.get(part_name, {})
                                    part_start_abs = part_physical_starts.get(part_name, 0.0)
                                    
                                    hole_positions = part_data.get("Holes position", [])
                                    hole_diameters = part_data.get("Holes diameter", [])
                                    side_holes = part_data.get("Side holes", [])
                                    
                                    # Formato 1 (solo si no hay formato 2, para evitar duplicados)
                                    if hole_positions and hole_diameters and len(hole_positions) == len(hole_diameters) and not side_holes:
                                        for idx, (pos_rel_mm, diam_mm) in enumerate(zip(hole_positions, hole_diameters)):
                                            if pos_rel_mm is not None and diam_mm is not None:
                                                abs_pos_mm = part_start_abs + pos_rel_mm
                                                acoustic_pos_mm = abs_pos_mm - stopper_absolute_position_mm
                                                pos_m = acoustic_pos_mm / 1000.0
                                                rad_m = (diam_mm / 2.0) / 1000.0
                                                
                                                # Verificar si ya existe un agujero en esta posición (evitar duplicados)
                                                pos_key = round(pos_m * 1000 / TOLERANCE_MM)
                                                if pos_key in holes_positions_seen:
                                                    logger.debug(f"  Agujero duplicado ignorado en posición {pos_m*1000:.2f}mm (parte {part_name})")
                                                    continue
                                                holes_positions_seen.add(pos_key)
                                                
                                                # Usar contador global para numerar agujeros (hole1, hole2, ... hole7)
                                                if part_name != FLUTE_PARTS_ORDER[0]:  # No contar agujeros del headjoint
                                                    global_hole_counter += 1
                                                    hole_label = f'hole{global_hole_counter}'
                                                else:
                                                    hole_label = 'entrance'
                                                
                                                # Obtener estado desde digitación usando el label global
                                                is_open = fingering_dict.get(hole_label, True)
                                                
                                                logger.debug(f"  Agujero en {part_name}, posición {pos_m*1000:.2f}mm: label={hole_label}, is_open={is_open}")
                                                
                                                holes_details_for_plot.append({
                                                    'label': hole_label,
                                                    'position_m': pos_m,
                                                    'radius_m': rad_m,
                                                    'is_open': is_open
                                                })
                                    
                                    # Formato 2 (Side holes) - preferido si está disponible
                                    if side_holes:
                                        for hole_info in side_holes:
                                            if isinstance(hole_info, dict):
                                                pos_rel_mm = hole_info.get("position", hole_info.get("Position", None))
                                                diam_mm = hole_info.get("diameter", hole_info.get("Diameter", None))
                                                hole_label_from_data = hole_info.get("label", hole_info.get("Label", None))
                                                
                                                if pos_rel_mm is not None and diam_mm is not None:
                                                    abs_pos_mm = part_start_abs + pos_rel_mm
                                                    acoustic_pos_mm = abs_pos_mm - stopper_absolute_position_mm
                                                    pos_m = acoustic_pos_mm / 1000.0
                                                    rad_m = (diam_mm / 2.0) / 1000.0
                                                    
                                                    # Verificar si ya existe un agujero en esta posición (evitar duplicados)
                                                    pos_key = round(pos_m * 1000 / TOLERANCE_MM)
                                                    if pos_key in holes_positions_seen:
                                                        logger.debug(f"  Agujero duplicado ignorado en posición {pos_m*1000:.2f}mm (parte {part_name}, label={hole_label_from_data})")
                                                        continue
                                                    holes_positions_seen.add(pos_key)
                                                    
                                                    # Usar etiqueta del dato o generar una basada en contador global
                                                    if hole_label_from_data:
                                                        hole_label = hole_label_from_data.lower().strip()
                                                    else:
                                                        # Si no hay label en los datos, usar contador global
                                                        if part_name != FLUTE_PARTS_ORDER[0]:  # No contar agujeros del headjoint
                                                            global_hole_counter += 1
                                                            hole_label = f'hole{global_hole_counter}'
                                                        else:
                                                            hole_label = 'entrance'
                                                    
                                                    # Obtener estado desde digitación usando el label
                                                    is_open = fingering_dict.get(hole_label, True)
                                                    
                                                    logger.debug(f"  Agujero en {part_name}, posición {pos_m*1000:.2f}mm: label={hole_label}, is_open={is_open}")
                                                    
                                                    holes_details_for_plot.append({
                                                        'label': hole_label,
                                                        'position_m': pos_m,
                                                        'radius_m': rad_m,
                                                        'is_open': is_open
                                                    })
                            except Exception as e_fallback:
                                logger.error(f"Error en fallback de agujeros para {self.flute_data.flute_model}, nota {note}: {e_fallback}")
                        
                        # Dibujar agujeros si se encontraron
                        if holes_details_for_plot:
                            FluteOperations._plot_holes_static(holes_details_for_plot, ax, M_TO_MM_FACTOR, 
                                                              default_color='black', show_labels=True)
                        else:
                            logger.warning(f"No se encontraron agujeros para dibujar en {self.flute_data.flute_model}, nota {note}")
                else:
                    # Caso original cuando instrument_geometry es válido y no es cacheado
                    combined_measurements = self.flute_data.combined_measurements
                    if combined_measurements:
                        try:
                            # Aplicar offset del corcho para mostrar solo la parte acústica
                            positions_mm = np.array([item["position"] - stopper_absolute_position_mm for item in combined_measurements])
                            diameters_mm = np.array([item["diameter"] for item in combined_measurements])
                            radii_mm = diameters_mm / 2.0
                            ax.plot(positions_mm, radii_mm, color='black', linestyle='-', linewidth=1)
                            ax.plot(positions_mm, -radii_mm, color='black', linestyle='-', linewidth=1)
                        except Exception as e_plot_bore:
                            logger.error(f"Error al dibujar el tubo principal usando combined_measurements para {self.flute_data.flute_model}: {e_plot_bore}")
                            ax.text(0.5, 0.5, "Error al dibujar tubo", ha='center', va='center', transform=ax.transAxes, color='red')
                    
                    holes_details_for_plot = []
                    try:
                        fingering = instrument_geometry.fingering_chart.fingering_of(note)
                        for hole_obj in instrument_geometry.holes:
                            pos_m = hole_obj.position.get_value()
                            rad_m = hole_obj.shape.get_radius_at(0) if hasattr(hole_obj.shape, 'get_radius_at') else 0.003 
                            is_open = fingering.is_side_comp_open(hole_obj.label)
                            holes_details_for_plot.append({
                                'label': hole_obj.label, 'position_m': pos_m, 'radius_m': rad_m, 'is_open': is_open
                            })
                    except Exception as e_holes:
                        logger.warning(f"Error obteniendo agujeros desde instrument_geometry para {self.flute_data.flute_model}, nota {note}: {e_holes}. Intentando desde datos de flauta...")
                    
                    # Si no se encontraron agujeros desde la geometría, intentar desde datos de flauta
                    if not holes_details_for_plot:
                        try:
                            # Obtener digitación desde archivo
                            fingering_dict = {}
                            if hasattr(self.flute_data, 'fing_chart_file_path') and self.flute_data.fing_chart_file_path:
                                try:
                                    fingering_dict = FluteOperations._get_fingering_from_file(
                                        self.flute_data.fing_chart_file_path, note
                                    )
                                except Exception as e:
                                    logger.warning(f"Error cargando digitación desde archivo: {e}")
                            
                            # Calcular posiciones físicas absolutas de agujeros
                            # Replicar la lógica exacta de ensamblaje acústico
                            part_physical_starts = {}
                            next_part_connection_point_abs = 0.0
                            
                            for i, part_name in enumerate(FLUTE_PARTS_ORDER):
                                part_data = self.flute_data.data.get(part_name, {})
                                if not part_data:
                                    continue
                                    
                                part_total_length = part_data.get("Total length", 0.0)
                                part_mortise_length = part_data.get("Mortise length", 0.0)
                                
                                # Determinar dónde comienza físicamente esta parte
                                if i == 0:  # Headjoint
                                    current_physical_plot_start_abs = 0.0
                                    # Left se conecta al inicio del socket de HJ
                                    socket_start_abs = current_physical_plot_start_abs + part_total_length - part_mortise_length
                                    next_part_connection_point_abs = socket_start_abs
                                elif i == 1:  # Left (se inserta en Headjoint)
                                    # Left comienza donde termina el cuerpo de Headjoint (antes del socket de HJ)
                                    hj_data = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                                    hj_total_length = hj_data.get("Total length", 0.0)
                                    hj_mortise_length = hj_data.get("Mortise length", 0.0)
                                    current_physical_plot_start_abs = hj_total_length - hj_mortise_length
                                    # Right se conecta al final de Left
                                    next_part_connection_point_abs = current_physical_plot_start_abs + part_total_length
                                else:  # Right, Foot (se insertan en la anterior)
                                    # El inicio físico es el final de la parte anterior menos el socket de la parte actual
                                    current_physical_plot_start_abs = next_part_connection_point_abs - part_mortise_length
                                    if part_name == FLUTE_PARTS_ORDER[2]:  # Right
                                        # Foot se conecta al final de Right
                                        next_part_connection_point_abs = current_physical_plot_start_abs + part_total_length
                                
                                part_physical_starts[part_name] = current_physical_plot_start_abs
                            
                            # Buscar agujeros en múltiples formatos
                            # Usar un conjunto para evitar duplicados basados en posición
                            holes_positions_seen = set()  # Para evitar duplicados
                            TOLERANCE_MM = 0.1  # Tolerancia de 0.1mm para considerar agujeros duplicados
                            
                            for part_name in FLUTE_PARTS_ORDER:
                                part_data = self.flute_data.data.get(part_name, {})
                                part_start_abs = part_physical_starts.get(part_name, 0.0)
                                
                                hole_positions = part_data.get("Holes position", [])
                                hole_diameters = part_data.get("Holes diameter", [])
                                side_holes = part_data.get("Side holes", [])
                                
                                # Formato 1 (solo si no hay formato 2, para evitar duplicados)
                                if hole_positions and hole_diameters and len(hole_positions) == len(hole_diameters) and not side_holes:
                                    for idx, (pos_rel_mm, diam_mm) in enumerate(zip(hole_positions, hole_diameters)):
                                        if pos_rel_mm is not None and diam_mm is not None:
                                            abs_pos_mm = part_start_abs + pos_rel_mm
                                            acoustic_pos_mm = abs_pos_mm - stopper_absolute_position_mm
                                            pos_m = acoustic_pos_mm / 1000.0
                                            rad_m = (diam_mm / 2.0) / 1000.0
                                            
                                            # Verificar si ya existe un agujero en esta posición (evitar duplicados)
                                            pos_key = round(pos_m * 1000 / TOLERANCE_MM)
                                            if pos_key in holes_positions_seen:
                                                logger.debug(f"  Agujero duplicado ignorado en posición {pos_m*1000:.2f}mm (parte {part_name})")
                                                continue
                                            holes_positions_seen.add(pos_key)
                                            
                                            # Intentar obtener etiqueta y estado desde digitación
                                            hole_label = f'hole{idx+1}'
                                            for key in fingering_dict.keys():
                                                if key.startswith('hole') and str(idx+1) in key:
                                                    hole_label = key
                                                    break
                                            
                                            is_open = fingering_dict.get(hole_label, True)
                                            
                                            holes_details_for_plot.append({
                                                'label': hole_label,
                                                'position_m': pos_m,
                                                'radius_m': rad_m,
                                                'is_open': is_open
                                            })
                                
                                # Formato 2 (Side holes) - preferido si está disponible
                                if side_holes:
                                    for hole_info in side_holes:
                                        if isinstance(hole_info, dict):
                                            pos_rel_mm = hole_info.get("position", hole_info.get("Position", None))
                                            diam_mm = hole_info.get("diameter", hole_info.get("Diameter", None))
                                            hole_label_from_data = hole_info.get("label", hole_info.get("Label", None))
                                            
                                            if pos_rel_mm is not None and diam_mm is not None:
                                                abs_pos_mm = part_start_abs + pos_rel_mm
                                                acoustic_pos_mm = abs_pos_mm - stopper_absolute_position_mm
                                                pos_m = acoustic_pos_mm / 1000.0
                                                rad_m = (diam_mm / 2.0) / 1000.0
                                                
                                                # Verificar si ya existe un agujero en esta posición (evitar duplicados)
                                                pos_key = round(pos_m * 1000 / TOLERANCE_MM)
                                                if pos_key in holes_positions_seen:
                                                    logger.debug(f"  Agujero duplicado ignorado en posición {pos_m*1000:.2f}mm (parte {part_name}, label={hole_label_from_data})")
                                                    continue
                                                holes_positions_seen.add(pos_key)
                                                
                                                if hole_label_from_data:
                                                    hole_label = hole_label_from_data.lower()
                                                else:
                                                    hole_label = f'hole_{len(holes_details_for_plot)}'
                                                
                                                is_open = fingering_dict.get(hole_label, True)
                                                
                                                holes_details_for_plot.append({
                                                    'label': hole_label,
                                                    'position_m': pos_m,
                                                    'radius_m': rad_m,
                                                    'is_open': is_open
                                                })
                        except Exception as e_fallback:
                            logger.error(f"Error en fallback de agujeros para {self.flute_data.flute_model}, nota {note}: {e_fallback}")
                    
                    # Dibujar agujeros si se encontraron
                    if holes_details_for_plot:
                        FluteOperations._plot_holes_static(holes_details_for_plot, ax, M_TO_MM_FACTOR, 
                                                          default_color='black', show_labels=True)
                    else:
                        logger.warning(f"No se encontraron agujeros para dibujar en {self.flute_data.flute_model}, nota {note}")

            ax.set_xlabel("Posición desde el corcho (mm)")
            ax.set_ylabel("Radio (mm)")
            ax.set_title(f"Vista Superior - Geometría Acústica '{note}' - {self.flute_data.flute_model}", fontsize=10)
            ax.grid(True, linestyle=':', alpha=0.7)
            return ax
        except Exception as e:
            logger.exception(f"Error generando vista superior de geometría para {self.flute_data.flute_model}, nota {note}: {e}")
            ax.text(0.5,0.5, f"Error generando vista para '{note}'", ha='center', transform=ax.transAxes, color='red')
            ax.set_title(f"Vista Superior ({note}) - Error", fontsize=10)
            return ax

    @staticmethod
    def plot_individual_admittance_analysis(
         acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
         combined_measurements_list: List[Tuple[List[Dict[str, float]], str]], 
         note: str,
         fig_to_use: Optional[plt.Figure] = None,
         base_colors: List[str] = BASE_COLORS,
         linestyles: List[str] = LINESTYLES,
         flute_data_list: Optional[List[Any]] = None  # Lista opcional de objetos FluteData completos
     ) -> plt.Figure :

     fig: plt.Figure
     axes: np.ndarray

     if fig_to_use is not None:
         fig = fig_to_use
         fig.clear()
         axes_array = fig.subplots(4, 1, gridspec_kw={'height_ratios': [2, 1, 1, 1]})
         if not isinstance(axes_array, np.ndarray): axes = np.array([axes_array])
         else: axes = axes_array
     else:
         fig, axes_array = plt.subplots(4, 1, figsize=(12,18), gridspec_kw={'height_ratios': [2, 1, 1, 1]})
         if not isinstance(axes_array, np.ndarray):
             axes = np.array([axes_array])
         else:
             axes = axes_array

     if not isinstance(axes, np.ndarray) or axes.ndim == 0 or axes.size < 4:
         logger.error("No se pudieron crear o obtener los ejes para plot_individual_admittance_analysis.")
         fig_fallback, ax_fallback = plt.subplots(); ax_fallback.text(0.5,0.5, "Error subplots")
         return fig_fallback

     ax_admittance, ax_pressure, ax_geometry, ax_flow = axes.flatten()
     
     if fig_to_use is not None:
         for ax_item in [ax_admittance, ax_pressure, ax_geometry, ax_flow]:
             ax_item.clear()

     legend_handles_adm, legend_handles_pres, legend_handles_flow = [], [], []

     for index, ((analysis_dict, flute_name_aa), (measurements_data, flute_name_cm)) in enumerate(zip(acoustic_analysis_list, combined_measurements_list)):
         style_idx = index % len(linestyles)
         color_idx = index % len(base_colors)
         linestyle = linestyles[style_idx]
         color = base_colors[color_idx]

         analysis_obj = analysis_dict.get(note)
         if flute_name_aa != flute_name_cm:
             logger.warning(f"Desajuste de nombres de flauta entre analysis_list ({flute_name_aa}) y measurements_list ({flute_name_cm}). Usando {flute_name_aa}.")
         flute_name = flute_name_aa 

         if not is_impedance_computation_like(analysis_obj):
             logger.debug(f"Análisis para nota '{note}' no disponible o inválido para {flute_name}.")
             continue

         frequencies = analysis_obj.frequencies
         impedance = analysis_obj.impedance
         valid_impedance = np.where(np.abs(impedance) < 1e-12, 1e-12, impedance)
         admittance_db = 20 * np.log10(np.abs(1.0 / valid_impedance))

         line_adm, = ax_admittance.plot(frequencies, admittance_db, linestyle=linestyle, color=color, label=flute_name, alpha=0.8)
         if not any(lh.get_label() == flute_name for lh in legend_handles_adm):
             legend_handles_adm.append(line_adm)

         antires_freqs = list(analysis_obj.antiresonance_frequencies())
         current_ymin_adm, current_ymax_adm = ax_admittance.get_ylim() if ax_admittance.has_data() else (np.min(admittance_db)-5 if admittance_db.size > 0 else -60, np.max(admittance_db)+5 if admittance_db.size > 0 else 0)
         ax_admittance.set_ylim(min(current_ymin_adm, np.min(admittance_db)-5 if admittance_db.size > 0 else -60),
                                max(current_ymax_adm, np.max(admittance_db)+5 if admittance_db.size > 0 else 0))
         ymin_adm, ymax_adm = ax_admittance.get_ylim()

         for i_ar, f_ar in enumerate(antires_freqs[:3]):
             ax_admittance.vlines(f_ar, ymin_adm, ymax_adm, color=color, linestyle=':', alpha=0.6)
             if i_ar < 3 :  # Mostrar los 3 primeros armónicos
                 ax_admittance.text(f_ar, ymin_adm + (ymax_adm - ymin_adm) * (0.95 - index*0.08), f"{f_ar:.0f}",
                                 rotation=90, color=color, fontsize=7, ha='right', va='top', bbox=dict(facecolor='white', alpha=0.5, pad=0.1, edgecolor='none'))

         x_coords, pressure_modes, flow_modes = analysis_obj.get_pressure_flow()
         
         # Verificar si hay datos de presión/flujo disponibles
         # Convertir a arrays numpy si es necesario
         if not isinstance(x_coords, np.ndarray):
             x_coords = np.array(x_coords) if x_coords is not None else np.array([])
         if not isinstance(pressure_modes, np.ndarray):
             pressure_modes = np.array(pressure_modes) if pressure_modes is not None else np.array([])
         if not isinstance(flow_modes, np.ndarray):
             flow_modes = np.array(flow_modes) if flow_modes is not None else np.array([])
         
         # Verificar que los datos sean válidos
         has_pressure_flow_data = (
             x_coords.size > 0 and 
             pressure_modes.size > 0 and 
             flow_modes.size > 0 and
             pressure_modes.ndim >= 2 and 
             flow_modes.ndim >= 2
         )
         
         if has_pressure_flow_data:
             logger.info(f"Datos de presión/flujo disponibles para {flute_name}, nota {note}: x_coords.shape={x_coords.shape}, pressure_modes.shape={pressure_modes.shape}, flow_modes.shape={flow_modes.shape}")
             pressure_abs = np.abs(pressure_modes.T)
             flow_abs = np.abs(flow_modes.T)
         else:
             # No hay datos de presión/flujo en cache, mostrar mensaje
             logger.warning(f"Datos de presión/flujo NO disponibles para {flute_name}, nota {note}. x_coords.size={x_coords.size if hasattr(x_coords, 'size') else 'N/A'}, pressure_modes.size={pressure_modes.size if hasattr(pressure_modes, 'size') else 'N/A'}, flow_modes.size={flow_modes.size if hasattr(flow_modes, 'size') else 'N/A'}")
             ax_pressure.text(0.5, 0.5, f"Datos de presión no disponibles\npara {flute_name}\n\nPara visualizar:\n1. Marca el checkbox 'Guardar datos'\n2. Recarga la flauta", 
                            ha='center', va='center', transform=ax_pressure.transAxes,
                            fontsize=9, color=color, alpha=0.7)
             ax_flow.text(0.5, 0.5, f"Datos de flujo no disponibles\npara {flute_name}\n\nPara visualizar:\n1. Marca el checkbox 'Guardar datos'\n2. Recarga la flauta", 
                        ha='center', va='center', transform=ax_flow.transAxes,
                        fontsize=9, color=color, alpha=0.7)
             pressure_abs = np.array([])
             flow_abs = np.array([])

         for i_mode, f_mode in enumerate(antires_freqs[:3]):  # Mostrar 3 primeros armónicos
             if has_pressure_flow_data and pressure_abs.shape[1] > 0 and flow_abs.shape[1] > 0:
                 # Detectar si los datos son optimizados (solo armónicos) o completos (todas las frecuencias)
                 is_optimized_data = pressure_abs.shape[1] <= 10  # Pocos modos = datos optimizados
                 
                 if is_optimized_data:
                     # Datos optimizados: usar directamente el índice del armónico
                     if i_mode < pressure_abs.shape[1]:
                         idx_f_mode = i_mode
                         logger.debug(f"Usando datos optimizados: armónico {i_mode} directamente")
                     else:
                         logger.debug(f"Armónico {i_mode} no disponible en datos optimizados (solo hay {pressure_abs.shape[1]} armónicos)")
                         continue
                 else:
                     # Datos completos: buscar el índice de frecuencia más cercano
                     idx_f_mode = np.argmin(np.abs(frequencies - f_mode))
                     logger.debug(f"Usando datos completos: buscando frecuencia {f_mode:.0f}Hz en índice {idx_f_mode}")
                 
                 if idx_f_mode < pressure_abs.shape[1]: 
                     # Diferentes estilos para los 3 modos
                     if i_mode == 0:
                         mode_linestyle = linestyle
                         mode_alpha = 0.8
                     elif i_mode == 1:
                         mode_linestyle = '--'
                         mode_alpha = 0.6
                     else:  # i_mode == 2
                         mode_linestyle = ':'
                         mode_alpha = 0.5
                     line_pres, = ax_pressure.plot(x_coords, pressure_abs[:, idx_f_mode], 
                                                  linestyle=mode_linestyle, color=color,
                                                  label=f"{flute_name} (AR{i_mode+1}: {f_mode:.0f}Hz)", alpha=mode_alpha)
                     if not any(lh.get_label() == line_pres.get_label() for lh in legend_handles_pres):
                         legend_handles_pres.append(line_pres)
                     line_flow, = ax_flow.plot(x_coords, flow_abs[:, idx_f_mode], 
                                                  linestyle=mode_linestyle, color=color,
                                                  label=f"{flute_name} (AR{i_mode+1}: {f_mode:.0f}Hz)", alpha=mode_alpha)
                     if not any(lh.get_label() == line_flow.get_label() for lh in legend_handles_flow):
                         legend_handles_flow.append(line_flow)
             else:
                 if not has_pressure_flow_data:
                     logger.debug(f"Datos de presión/flujo no disponibles para {flute_name}, nota {note}.")
                 else:
                     logger.debug(f"No hay frecuencias antiresonantes o datos de modo para {flute_name}, nota {note}.")

         # Solo dibujar geometría para la PRIMERA flauta (evitar superposiciones)
         if ax_geometry and index == 0:
             try:
                 # Intentar usar el objeto FluteData completo si está disponible
                 full_flute_data = None
                 if flute_data_list:
                     for fd in flute_data_list:
                         if hasattr(fd, 'flute_model') and fd.flute_model == flute_name:
                             full_flute_data = fd
                             break
                 
                 if full_flute_data:
                     # Usar el objeto FluteData completo (tiene acceso a data, fing_chart_file_path, etc.)
                     temp_flute_ops_for_top_view = FluteOperations(full_flute_data)
                     returned_ax = temp_flute_ops_for_top_view.plot_top_view_instrument_geometry(note=note, ax=ax_geometry)
                 else:
                     # Fallback: crear objeto mínimo si no hay FluteData completo disponible
                     class MinimalFluteDataForTopView:
                         def __init__(self, acoustic_analysis_data_for_note, model_name, combined_measurements_data):
                             self.acoustic_analysis = acoustic_analysis_data_for_note
                             self.flute_model = model_name
                             self.combined_measurements = combined_measurements_data
                             self.data = {"Flute Model": model_name}
                             self.fing_chart_file_path = None  # No disponible en este caso
                     
                     current_flute_measurements = []
                     for cm_data, cm_name in combined_measurements_list:
                         if cm_name == flute_name:
                             current_flute_measurements = cm_data
                             break
                     temp_flute_data_for_top_view = MinimalFluteDataForTopView({note: analysis_obj}, flute_name, current_flute_measurements)
                     temp_flute_ops_for_top_view = FluteOperations(temp_flute_data_for_top_view)
                     returned_ax = temp_flute_ops_for_top_view.plot_top_view_instrument_geometry(note=note, ax=ax_geometry)
                 
                 if returned_ax is None:
                     logger.error(f"Plotting top view geometry falló y devolvió None para {flute_name}, nota {note}")
                 elif returned_ax is not ax_geometry and returned_ax is not None : 
                     logger.warning("plot_top_view_instrument_geometry podría haber creado un nuevo eje inesperadamente. Cerrando figura extra.")
                     plt.close(returned_ax.figure) 
             except Exception as e_geom_top_view:
                 logger.error(f"Error al graficar la vista superior de la geometría para {flute_name}, nota {note}: {e_geom_top_view}", exc_info=True)
                 if ax_geometry: 
                     ax_geometry.clear() 
                     ax_geometry.text(0.5,0.5, f"Error geom. sup. {flute_name}", ha='center', va='center', transform=ax_geometry.transAxes, color='red')

     if ax_admittance:
         ax_admittance.set_title(f"Admitancia para {note}", fontsize=10); ax_admittance.set_xlabel("Frecuencia (Hz)")
         ax_admittance.set_ylabel("Admitancia (dB)"); ax_admittance.legend(handles=legend_handles_adm, loc='best', fontsize=8); ax_admittance.grid(True, linestyle=':', alpha=0.7)
     if ax_pressure:
        ax_pressure.set_title(f"Presión vs Posición ({note})", fontsize=10); ax_pressure.set_xlabel("Posición (m)")
        ax_pressure.set_ylabel("Presión (Pa)"); ax_pressure.legend(handles=legend_handles_pres, loc='best', fontsize=8); ax_pressure.grid(True, linestyle=':', alpha=0.7)
     if ax_geometry: 
        ax_geometry.set_title(f"Geometría Acústica para {note}", fontsize=10); ax_geometry.set_xlabel("Posición desde el corcho (mm)")
        ax_geometry.set_ylabel("Radio (mm)"); ax_geometry.grid(True, linestyle=':', alpha=0.7)
     if ax_flow:
         ax_flow.set_title(f"Flujo vs Posición ({note})", fontsize=10); ax_flow.set_xlabel("Posición (m)")
         ax_flow.set_ylabel("Flujo (m³/s)"); ax_flow.legend(handles=legend_handles_flow, loc='best', fontsize=8); ax_flow.grid(True, linestyle=':', alpha=0.7)

     try:
         fig.tight_layout(rect=[0,0,1,0.97])
     except Exception as e_layout:
         logger.debug(f"Error en tight_layout para individual_admittance_analysis: {e_layout}")
     return fig

    @staticmethod
    def plot_combined_admittance(
            acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
            ax: Optional[plt.Axes] = None,
            base_colors: List[str] = BASE_COLORS,
            linestyles: List[str] = LINESTYLES
        ) -> plt.Figure:

        fig: plt.Figure
        if ax is None: fig, ax = plt.subplots(figsize=(14, 8))
        else: fig = ax.figure; ax.clear()

        for index, (analysis_dict, flute_name) in enumerate(acoustic_analysis_list):
            linestyle = linestyles[index % len(linestyles)]
            color = base_colors[index % len(base_colors)]

            line_plotted_for_legend = False
            for note, analysis_obj in analysis_dict.items():
                if is_impedance_computation_like(analysis_obj):
                    frequencies = analysis_obj.frequencies
                    impedance = analysis_obj.impedance
                    valid_impedance = np.where(np.abs(impedance) < 1e-12, 1e-12, impedance)
                    admittance_db = 20 * np.log10(np.abs(1.0 / valid_impedance))

                    current_label = flute_name if not line_plotted_for_legend else "_nolegend_"
                    ax.plot(frequencies, admittance_db, linestyle=linestyle, color=color, label=current_label, alpha=0.6)
                    if not line_plotted_for_legend: line_plotted_for_legend = True

        handles, labels = ax.get_legend_handles_labels()
        unique_handles_labels = dict(zip(labels, handles))
        ax.legend(unique_handles_labels.values(), unique_handles_labels.keys(), loc='best', fontsize=9)

        ax.set_title("Admitancia Combinada (Todas las Notas, Superpuestas por Flauta)", fontsize=10)
        ax.set_xlabel("Frecuencia (Hz)"); ax.set_ylabel("Admitancia (dB)"); ax.grid(True, linestyle=':', alpha=0.7)
        return fig

    @staticmethod
    def plot_summary_antiresonances(
            acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
            notes_ordered: List[str],
            ax: Optional[plt.Axes] = None,
            base_colors: List[str] = BASE_COLORS
        ) -> plt.Figure:

        fig: plt.Figure
        if ax is None: fig, ax = plt.subplots(figsize=(14, 8))
        else: fig = ax.figure; ax.clear()

        num_flutes = len(acoustic_analysis_list)
        total_width_for_note = 0.7
        offsets = np.linspace(-total_width_for_note / 2, total_width_for_note / 2, num_flutes if num_flutes > 0 else 1) if num_flutes > 1 else [0]

        legend_handles = []

        for index, (analysis_dict, flute_name) in enumerate(acoustic_analysis_list):
            color = base_colors[index % len(base_colors)]

            for note_idx, note in enumerate(notes_ordered):
                analysis_obj = analysis_dict.get(note)
                if is_impedance_computation_like(analysis_obj):
                    antires_freqs = list(analysis_obj.antiresonance_frequencies())
                    if antires_freqs:
                        for i_ar, f_ar in enumerate(antires_freqs[:2]): 
                            x_pos = note_idx + offsets[index]
                            ax.plot(x_pos, f_ar, "o", color=color, markersize=6, alpha=0.7)
                            if i_ar < 2:
                                 ax.text(x_pos, f_ar + (10 * (-1)**i_ar), f"{f_ar:.0f}", fontsize=7,
                                         ha="center", va="bottom" if i_ar % 2 == 0 else "top", color=color,
                                         bbox=dict(facecolor='white', alpha=0.3, pad=0.1, edgecolor='none'))
            if not any(lh.get_label() == flute_name for lh in legend_handles):
                legend_handles.append(plt.Line2D([0], [0], marker='o', color=color, linestyle='None', label=flute_name, markersize=6))

        ax.set_xticks(range(len(notes_ordered)))
        ax.set_xticklabels(notes_ordered, rotation=45, ha="right")
        ax.legend(handles=legend_handles, loc='best', fontsize=9)
        ax.set_title("Frecuencias Antiresonantes (Primeras 2) vs. Nota", fontsize=10)
        ax.set_xlabel("Nota"); ax.set_ylabel("Frecuencia (Hz)"); ax.grid(True, axis='y', linestyle=':', alpha=0.7)
        fig.tight_layout()
        return fig

    @staticmethod
    def plot_summary_cents_differences(
            acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
            notes_ordered: List[str],
            ax: Optional[plt.Axes] = None,
            base_colors: List[str] = BASE_COLORS,
            linestyles: List[str] = LINESTYLES
        ) -> plt.Figure:

        fig: plt.Figure
        if ax is None: fig, ax = plt.subplots(figsize=(14, 8))
        else: fig = ax.figure; ax.clear()

        num_flutes = len(acoustic_analysis_list)
        offset_per_flute = 0.12
        base_x_positions = np.arange(len(notes_ordered))
 
        legend_handles = [] 
        for index, (analysis_dict, flute_name) in enumerate(acoustic_analysis_list):
            linestyle = linestyles[index % len(linestyles)]
            color = base_colors[index % len(base_colors)]
            cents_diffs = []
            current_x_offset = 0.0 # No offset entre flautas
            for note in notes_ordered:
                note_cents = np.nan
                analysis_obj = analysis_dict.get(note)
                if is_impedance_computation_like(analysis_obj):
                    antires_freqs = list(analysis_obj.antiresonance_frequencies())
                    if len(antires_freqs) >= 2:
                        f1, f2 = antires_freqs[0], antires_freqs[1]
                        if f1 > 0 and f2 > 0: note_cents = 1200 * np.log2(f2 / (2.0 * f1))
                cents_diffs.append(note_cents)
            line, = ax.plot(base_x_positions + current_x_offset, cents_diffs, marker="o", linestyle=linestyle, color=color, label=flute_name, markersize=5, alpha=0.8)
            if not any(lh.get_label() == flute_name for lh in legend_handles):
                legend_handles.append(line)

        if legend_handles: ax.legend(handles=legend_handles, loc='best', fontsize=9)
        ax.set_xticks(base_x_positions)
        ax.set_xticklabels(notes_ordered, rotation=45, ha="right")
        ax.axhline(0, color='grey', linestyle='--', lw=0.8)
        ax.set_title("Inharmonicidad (Cents: Pico 2 vs 2 * Pico 1)", fontsize=10)
        ax.set_xlabel("Nota"); ax.set_ylabel("Diferencia (cents)"); ax.grid(True, linestyle=':', alpha=0.7)
        fig.tight_layout()
        return fig

    @staticmethod
    def plot_single_flute_inharmonicity_comparison(
            initial_analysis_dict: Dict[str, ImpedanceComputation],
            optimized_analysis_dict: Dict[str, ImpedanceComputation],
            notes_ordered: List[str],
            flute_name: str,
            ax: Optional[plt.Axes] = None,
        ) -> plt.Figure:
        """
        Compara la inharmonicidad (cents: Pico 2 vs 2*Pico 1) antes y después de la optimización
        para una sola flauta.
        """
        fig: plt.Figure
        if ax is None: fig, ax = plt.subplots(figsize=(10, 6))
        else: fig = ax.figure; ax.clear()

        base_x_positions = np.arange(len(notes_ordered))

        def calculate_cents_diffs(analysis_dict_param: Dict[str, Any], notes: List[str], label_for_log: str) -> List[float]: # Modificado tipo y añadido label
            cents_diffs = []
            logger.debug(f"CHECKPOINT FluteOperations: Calculando cents_diffs para '{label_for_log}'")
            if not analysis_dict_param:
                logger.warning(f"CHECKPOINT FluteOperations: analysis_dict_param para '{label_for_log}' está vacío o es None.")
                return [np.nan] * len(notes)
            
            for note_log in notes: # Renombrado para evitar conflicto con variable externa 'note'
                note_cents = np.nan
                analysis_obj = analysis_dict_param.get(note_log)
                logger.debug(f"  Nota '{note_log}' ({label_for_log}): analysis_obj es de tipo {type(analysis_obj).__name__}")

                if is_impedance_computation_like(analysis_obj):
                    logger.debug(f"    Nota '{note_log}' ({label_for_log}): Es ImpedanceComputation.")
                    antires_freqs = list(analysis_obj.antiresonance_frequencies())
                    logger.debug(f"    Nota '{note_log}' ({label_for_log}): Antirresonancias: {antires_freqs[:3]}")
                    if len(antires_freqs) >= 2:
                        f1, f2 = antires_freqs[0], antires_freqs[1]
                        if f1 > 0 and f2 > 0:
                            note_cents = 1200 * np.log2(f2 / (2.0 * f1))
                            logger.debug(f"    Nota '{note_log}' ({label_for_log}): f1={f1:.2f}, f2={f2:.2f}, note_cents={note_cents:.2f}")
                        else:
                            logger.warning(f"    Nota '{note_log}' ({label_for_log}): Frecuencias de antirresonancia no positivas f1={f1}, f2={f2}")
                    else:
                        logger.warning(f"    Nota '{note_log}' ({label_for_log}): No hay suficientes antirresonancias ({len(antires_freqs)})")
                elif analysis_obj is None:
                    logger.warning(f"    Nota '{note_log}' ({label_for_log}): analysis_obj es None.")
                else:
                    logger.warning(f"    Nota '{note_log}' ({label_for_log}): NO es ImpedanceComputation (tipo: {type(analysis_obj).__name__}).")
                cents_diffs.append(note_cents)
            return cents_diffs

        cents_diffs_initial = calculate_cents_diffs(initial_analysis_dict, notes_ordered, "Inicial")
        cents_diffs_optimized = calculate_cents_diffs(optimized_analysis_dict, notes_ordered, "Optimizado")
        logger.debug(f"CHECKPOINT FluteOperations: Cents diffs calculados. Inicial: {cents_diffs_initial}, Optimizado: {cents_diffs_optimized}")

        ax.plot(base_x_positions, cents_diffs_initial, marker="o", linestyle='--', color='gray', label="Inicial", markersize=5, alpha=0.8)
        ax.plot(base_x_positions, cents_diffs_optimized, marker="o", linestyle='-', color='blue', label="Optimizado", markersize=5, alpha=0.8)

        ax.set_xticks(base_x_positions); ax.set_xticklabels(notes_ordered, rotation=45, ha="right")
        ax.axhline(0, color='grey', linestyle='--', lw=0.8); ax.set_title(f"Inharmonicidad (Cents) - {flute_name}", fontsize=10)
        ax.set_xlabel("Nota"); ax.set_ylabel("Diferencia (cents)"); ax.grid(True, linestyle=':', alpha=0.7); 
        if any(not np.isnan(c) for c in cents_diffs_initial) or any(not np.isnan(c) for c in cents_diffs_optimized):
            ax.legend(loc='best', fontsize=9)
        fig.tight_layout(); return fig

    @staticmethod
    def plot_moc_summary(
            acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
            finger_frequencies_map: Dict[str, Dict[str, float]],
            notes_ordered: List[str],
            ax: Optional[plt.Axes] = None,
            base_colors: List[str] = BASE_COLORS,
            linestyles: List[str] = LINESTYLES
        ) -> plt.Figure:

        fig: plt.Figure
        if ax is None: fig, ax = plt.subplots(figsize=(12, 7))
        else: fig = ax.figure; ax.clear()

        num_flutes = len(acoustic_analysis_list)
        offset_per_flute = 0.12
        base_x_positions = np.arange(len(notes_ordered))
 
        legend_handles = [] 
        for index, (analysis_dict, flute_name) in enumerate(acoustic_analysis_list):
            linestyle = linestyles[index % len(linestyles)]
            color = base_colors[index % len(base_colors)]
            moc_vals = []
            current_finger_freqs = finger_frequencies_map.get(flute_name, {})
            current_x_offset = 0.0 # No offset entre flautas
            for note in notes_ordered:
                moc = np.nan
                f_play = current_finger_freqs.get(note)
                analysis_obj = analysis_dict.get(note)
                if is_impedance_computation_like(analysis_obj) and f_play is not None and f_play > 0:
                    try:
                        antires = list(analysis_obj.antiresonance_frequencies())
                        if len(antires) >= 2:
                            f0, f1 = antires[0], antires[1]
                            if f0 > 0 and f1 > 0 and f_play > 0 and f0 != f_play and (2.0 * f_play) != 0 and f1 != (2.0*f_play):
                                num_term = (1.0 / f1) - (1.0 / (2.0 * f_play))
                                den_term = (1.0 / f0) - (1.0 / f_play)
                                if abs(den_term) > 1e-9: 
                                    moc = num_term / den_term
                    except Exception as e:
                        logger.warning(f"Error calculando MOC para {flute_name}, nota {note}: {e}")
                moc_vals.append(moc)
            line, = ax.plot(base_x_positions + current_x_offset, moc_vals, marker="o", linestyle=linestyle, color=color, label=flute_name, markersize=5, alpha=0.8)
            if not any(lh.get_label() == flute_name for lh in legend_handles):
                legend_handles.append(line)

        if legend_handles: ax.legend(handles=legend_handles, loc='best', fontsize=9)
        ax.set_xticks(base_x_positions)
        ax.set_xticklabels(notes_ordered, rotation=45, ha="right")
        ax.set_xlabel("Nota"); ax.set_ylabel("MOC (ratio)"); ax.set_title("Resumen de MOC por Nota", fontsize=10); ax.grid(True, linestyle=':', alpha=0.7)
        fig.tight_layout()
        return fig

    @staticmethod
    def plot_bi_espe_summary(
            acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
            finger_frequencies_map: Dict[str, Dict[str, float]],
            notes_ordered: List[str],
            ax: Optional[plt.Axes] = None,
            base_colors: List[str] = BASE_COLORS
        ) -> plt.Figure:

        fig: plt.Figure
        if ax is None: fig, ax = plt.subplots(figsize=(12, 7))
        else: fig = ax.figure; ax.clear()

        num_flutes = len(acoustic_analysis_list)
        base_x_positions = np.arange(len(notes_ordered))
        # total_width_per_flute_group ahora se usa para separar BI de ESPE para la misma flauta
        width_for_bi_espe_separation = 0.15 # Ancho para separar BI y ESPE de la misma flauta

        def get_speed_of_sound(temp_celsius=20.0): return 331.3 * np.sqrt(1 + temp_celsius / 273.15)
        speed_of_sound_ref = get_speed_of_sound(20.0)
        legend_items = {} 

        for idx, (analysis_dict, flute_name) in enumerate(acoustic_analysis_list):
            color = base_colors[idx % len(base_colors)]
            bi_vals, espe_vals = [], []
            current_finger_freqs = finger_frequencies_map.get(flute_name, {})
            for note in notes_ordered:
                bi, espe = np.nan, np.nan
                f_play_I = current_finger_freqs.get(note)
                analysis_obj = analysis_dict.get(note)
                if is_impedance_computation_like(analysis_obj) and f_play_I is not None and f_play_I > 0:
                    try:
                        antires = list(analysis_obj.antiresonance_frequencies())
                        if len(antires) >= 2:
                            f0, f1 = antires[0], antires[1]
                            f_play_II = 2.0 * f_play_I
                            if f0 > 0: bi = 1200.0 * np.log2(f_play_I / f0)
                            delta_l_I = (speed_of_sound_ref / 2.0) * ((1.0 / f_play_I) - (1.0 / f0)) if f0 > 0 else 0.0
                            delta_l_II = speed_of_sound_ref * ((1.0 / f_play_II) - (1.0 / f1)) if f1 > 0 and f_play_II > 0 else 0.0
                            delta_delta_l = delta_l_II - delta_l_I
                            L_eff_I = (speed_of_sound_ref / (2.0 * f_play_I))
                            if L_eff_I > 0 and (L_eff_I + delta_delta_l) > 1e-9: 
                                espe = 1200.0 * np.log2(L_eff_I / (L_eff_I + delta_delta_l))
                    except Exception as e:
                        logger.warning(f"Error calculando B_I/ESPE para {flute_name}, nota {note}: {e}")
                bi_vals.append(bi); espe_vals.append(espe)
            # group_center_offset es 0 para alinear todas las flautas
            # Se mantiene una pequeña separación entre BI y ESPE para la misma flauta
            line_bi, = ax.plot(base_x_positions - width_for_bi_espe_separation / 2, bi_vals,
                    linestyle='-', color=color, marker='o', markersize=5, alpha=0.8)
            line_espe, = ax.plot(base_x_positions + width_for_bi_espe_separation / 2, espe_vals,
                    linestyle='--', dashes=(4,2), color=color, marker='x', markersize=5, alpha=0.8) 
            if f"{flute_name} - $B_I$" not in legend_items:
                legend_items[f"{flute_name} - $B_I$"] = line_bi
            if f"{flute_name} - ESPE" not in legend_items:
                legend_items[f"{flute_name} - ESPE$"] = line_espe
        
        if legend_items:
            ax.legend(legend_items.values(), legend_items.keys(), fontsize=8, loc='best', ncol=max(1, num_flutes // 2))

        ax.set_xticks(base_x_positions)
        ax.set_xticklabels(notes_ordered, rotation=45, ha="right")
        ax.axhline(0, color='grey', linestyle='--', lw=0.8) 
        ax.set_title("$B_I$ y ESPE a Través de las Notas", fontsize=10); ax.set_xlabel("Nota"); ax.set_ylabel("Cents"); ax.grid(True, linestyle=':', alpha=0.7)
        fig.tight_layout()
        return fig

    @staticmethod
    def plot_resonance_frequencies_vs_equal_temperament(
            acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
            notes_ordered: List[str],
            reference_pitch: float = 415.0,
            ax: Optional[plt.Axes] = None,
            base_colors: List[str] = BASE_COLORS,
            linestyles: List[str] = LINESTYLES
        ) -> plt.Figure:
        """
        Grafica las desviaciones de frecuencias de resonancia respecto al temperamento igual.
        
        Args:
            acoustic_analysis_list: Lista de tuplas (diccionario de análisis, nombre de flauta)
            notes_ordered: Lista de notas ordenadas (ej: ["D", "E", "Fs", ...])
            reference_pitch: Frecuencia de referencia (La, por defecto 415 Hz)
            ax: Eje opcional para plotear
            base_colors: Colores para las flautas
            linestyles: Estilos de línea
            
        Returns:
            Figura de matplotlib
        """
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(14, 8))
        else:
            fig = ax.figure
        
        # Mapeo de notas a semitonos desde La (A=0)
        note_to_semitone = {
            "D": -7, "Ds": -6, "E": -5, "F": -4, "Fs": -3, "G": -2, "Gs": -1,
            "A": 0, "As": 1, "B": 2, "C": 3, "Cs": 4, "D2": 5, "Ds2": 6, "E2": 7
        }
        
        base_x_positions = np.arange(len(notes_ordered))
        legend_handles = []
        
        for index, (analysis_dict, flute_name) in enumerate(acoustic_analysis_list):
            linestyle_solid = linestyles[index % len(linestyles)]
            linestyle_dashed = (0, (5, 5))  # Punteado para 2da octava
            color = base_colors[index % len(base_colors)]
            
            deviations_1st = []  # Primera octava
            deviations_2nd = []  # Segunda octava
            
            for note in notes_ordered:
                analysis_obj = analysis_dict.get(note)
                semitone = note_to_semitone.get(note, 0)
                
                # Frecuencia temperada
                f_temperada = reference_pitch * (2.0 ** (semitone / 12.0))
                
                dev_1st = np.nan
                dev_2nd = np.nan
                
                if is_impedance_computation_like(analysis_obj):
                    try:
                        antires = list(analysis_obj.antiresonance_frequencies())
                        
                        # Primera octava (primera antiresonancia)
                        if len(antires) >= 1 and antires[0] > 0:
                            f_medida_1st = antires[0]
                            dev_1st = 1200.0 * np.log2(f_medida_1st / f_temperada)
                        
                        # Segunda octava (segunda antiresonancia)
                        if len(antires) >= 2 and antires[1] > 0:
                            f_medida_2nd = antires[1]
                            f_temperada_2nd = f_temperada * 2.0  # Octava superior
                            dev_2nd = 1200.0 * np.log2(f_medida_2nd / f_temperada_2nd)
                        
                    except Exception as e:
                        logger.warning(f"Error calculando desviación para {flute_name}, nota {note}: {e}")
                
                deviations_1st.append(dev_1st)
                deviations_2nd.append(dev_2nd)
            
            # Plotear primera octava (línea sólida)
            line_1st, = ax.plot(base_x_positions, deviations_1st, 
                               marker="o", linestyle=linestyle_solid, color=color, 
                               label=f"{flute_name} - 1ra octava", markersize=6, alpha=0.8, linewidth=2)
            
            # Plotear segunda octava (línea punteada)
            line_2nd, = ax.plot(base_x_positions, deviations_2nd, 
                               marker="s", linestyle=linestyle_dashed, color=color, 
                               label=f"{flute_name} - 2da octava", markersize=5, alpha=0.6, linewidth=1.5)
            
            legend_handles.append(line_1st)
            legend_handles.append(line_2nd)
        
        # Línea de referencia en y=0 (temperamento perfecto)
        ax.axhline(0, color='black', linestyle='-', linewidth=1.5, label='Temperamento Igual', zorder=0)
        
        # Configuración de ejes
        ax.set_xticks(base_x_positions)
        ax.set_xticklabels(notes_ordered, rotation=45, ha="right")
        ax.set_xlabel("Nota", fontsize=11)
        ax.set_ylabel("Desviación (cents)", fontsize=11)
        ax.set_title(f"Frecuencias de Resonancia vs Temperamento Igual (La = {reference_pitch} Hz)", fontsize=12)
        ax.grid(True, linestyle=':', alpha=0.7)
        
        if legend_handles:
            ax.legend(fontsize=9, loc='best', ncol=2)
        
        fig.tight_layout()
        return fig

    @staticmethod
    def plot_peak_admittance_heights(
            acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
            notes_ordered: List[str],
            ax: Optional[plt.Axes] = None,
            base_colors: List[str] = BASE_COLORS,
            linestyles: List[str] = LINESTYLES
        ) -> plt.Figure:
        """
        Grafica la altura de los picos de admitancia para cada nota.
        Indica la facilidad de emisión del sonido.
        """
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 7))
        else:
            fig = ax.figure
        
        base_x_positions = np.arange(len(notes_ordered))
        legend_handles = []
        
        for index, (analysis_dict, flute_name) in enumerate(acoustic_analysis_list):
            linestyle = linestyles[index % len(linestyles)]
            color = base_colors[index % len(base_colors)]
            
            peak_heights = []
            
            for note in notes_ordered:
                analysis_obj = analysis_dict.get(note)
                peak_height = np.nan
                
                if is_impedance_computation_like(analysis_obj):
                    try:
                        frequencies = np.array(analysis_obj.frequencies)
                        impedance = np.array(analysis_obj.impedance)
                        admittance = np.abs(1.0 / (impedance + 1e-10))
                        
                        antires = list(analysis_obj.antiresonance_frequencies())
                        if len(antires) >= 1 and antires[0] > 0:
                            # Encontrar el pico más cercano a la primera antiresonancia
                            target_freq = antires[0]
                            idx_closest = np.argmin(np.abs(frequencies - target_freq))
                            
                            # Buscar el máximo local alrededor
                            window = 20
                            idx_start = max(0, idx_closest - window)
                            idx_end = min(len(admittance), idx_closest + window)
                            peak_height = np.max(admittance[idx_start:idx_end])
                        
                    except Exception as e:
                        logger.warning(f"Error calculando altura de pico para {flute_name}, nota {note}: {e}")
                
                peak_heights.append(peak_height)
            
            line, = ax.plot(base_x_positions, peak_heights, 
                           marker="o", linestyle=linestyle, color=color, 
                           label=flute_name, markersize=6, alpha=0.8, linewidth=2)
            legend_handles.append(line)
        
        ax.set_xticks(base_x_positions)
        ax.set_xticklabels(notes_ordered, rotation=45, ha="right")
        ax.set_xlabel("Nota", fontsize=11)
        ax.set_ylabel("Admitancia Máxima", fontsize=11)
        ax.set_title("Altura de Picos de Admitancia (Facilidad de Emisión)", fontsize=12)
        ax.grid(True, linestyle=':', alpha=0.7)
        
        if legend_handles:
            ax.legend(fontsize=9, loc='best')
        
        fig.tight_layout()
        return fig

    @staticmethod
    def plot_q_factor(
            acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
            notes_ordered: List[str],
            ax: Optional[plt.Axes] = None,
            base_colors: List[str] = BASE_COLORS,
            linestyles: List[str] = LINESTYLES
        ) -> plt.Figure:
        """
        Grafica el Q-factor (factor de calidad) para cada nota.
        Q = f_resonancia / ancho_banda. Relacionado con el color tonal.
        """
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 7))
        else:
            fig = ax.figure
        
        base_x_positions = np.arange(len(notes_ordered))
        legend_handles = []
        
        for index, (analysis_dict, flute_name) in enumerate(acoustic_analysis_list):
            linestyle = linestyles[index % len(linestyles)]
            color = base_colors[index % len(base_colors)]
            
            q_factors = []
            
            for note in notes_ordered:
                analysis_obj = analysis_dict.get(note)
                q_factor = np.nan
                
                if is_impedance_computation_like(analysis_obj):
                    try:
                        frequencies = np.array(analysis_obj.frequencies)
                        impedance = np.array(analysis_obj.impedance)
                        admittance = np.abs(1.0 / (impedance + 1e-10))
                        
                        antires = list(analysis_obj.antiresonance_frequencies())
                        if len(antires) >= 1 and antires[0] > 0:
                            target_freq = antires[0]
                            idx_peak = np.argmin(np.abs(frequencies - target_freq))
                            
                            # Buscar máximo local
                            window = 30
                            idx_start = max(0, idx_peak - window)
                            idx_end = min(len(admittance), idx_peak + window)
                            idx_max_local = idx_start + np.argmax(admittance[idx_start:idx_end])
                            peak_value = admittance[idx_max_local]
                            
                            # Calcular ancho a -3dB (mitad de la altura del pico)
                            threshold = peak_value / np.sqrt(2)
                            
                            # Buscar puntos donde cruza el umbral
                            left_idx = idx_max_local
                            while left_idx > 0 and admittance[left_idx] > threshold:
                                left_idx -= 1
                            
                            right_idx = idx_max_local
                            while right_idx < len(admittance) - 1 and admittance[right_idx] > threshold:
                                right_idx += 1
                            
                            if left_idx < right_idx:
                                bandwidth = frequencies[right_idx] - frequencies[left_idx]
                                if bandwidth > 0:
                                    q_factor = target_freq / bandwidth
                        
                    except Exception as e:
                        logger.warning(f"Error calculando Q-factor para {flute_name}, nota {note}: {e}")
                
                q_factors.append(q_factor)
            
            line, = ax.plot(base_x_positions, q_factors, 
                           marker="o", linestyle=linestyle, color=color, 
                           label=flute_name, markersize=6, alpha=0.8, linewidth=2)
            legend_handles.append(line)
        
        ax.set_xticks(base_x_positions)
        ax.set_xticklabels(notes_ordered, rotation=45, ha="right")
        ax.set_xlabel("Nota", fontsize=11)
        ax.set_ylabel("Q-Factor", fontsize=11)
        ax.set_title("Factor de Calidad (Q-Factor) - Color Tonal", fontsize=12)
        ax.grid(True, linestyle=':', alpha=0.7)
        
        if legend_handles:
            ax.legend(fontsize=9, loc='best')
        
        fig.tight_layout()
        return fig

    @staticmethod
    def plot_harmonic_ratios(
            acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
            notes_ordered: List[str],
            ax: Optional[plt.Axes] = None,
            base_colors: List[str] = BASE_COLORS,
            linestyles: List[str] = LINESTYLES
        ) -> plt.Figure:
        """
        Grafica el ratio de armónicos pares/impares.
        Caracteriza el contenido tonal del instrumento.
        """
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 7))
        else:
            fig = ax.figure
        
        base_x_positions = np.arange(len(notes_ordered))
        legend_handles = []
        
        for index, (analysis_dict, flute_name) in enumerate(acoustic_analysis_list):
            linestyle = linestyles[index % len(linestyles)]
            color = base_colors[index % len(base_colors)]
            
            ratios = []
            
            for note in notes_ordered:
                analysis_obj = analysis_dict.get(note)
                ratio = np.nan
                
                if is_impedance_computation_like(analysis_obj):
                    try:
                        frequencies = np.array(analysis_obj.frequencies)
                        impedance = np.array(analysis_obj.impedance)
                        admittance = np.abs(1.0 / (impedance + 1e-10))
                        
                        antires = list(analysis_obj.antiresonance_frequencies())
                        if len(antires) >= 3:
                            # f1, f2, f3 = 1ro, 2do, 3er armónico
                            # Encontrar amplitudes de admitancia en estas frecuencias
                            odd_sum = 0  # f1 (fundamental) + f3 (3er armónico)
                            even_sum = 0  # f2 (2do armónico)
                            
                            for i, freq in enumerate(antires[:3]):
                                idx = np.argmin(np.abs(frequencies - freq))
                                window = 10
                                idx_start = max(0, idx - window)
                                idx_end = min(len(admittance), idx + window)
                                peak = np.max(admittance[idx_start:idx_end])
                                
                                if i in [0, 2]:  # 1er y 3er armónico (impares)
                                    odd_sum += peak
                                elif i == 1:  # 2do armónico (par)
                                    even_sum += peak
                            
                            if odd_sum > 0:
                                ratio = even_sum / odd_sum
                        
                    except Exception as e:
                        logger.warning(f"Error calculando ratio armónicos para {flute_name}, nota {note}: {e}")
                
                ratios.append(ratio)
            
            line, = ax.plot(base_x_positions, ratios, 
                           marker="o", linestyle=linestyle, color=color, 
                           label=flute_name, markersize=6, alpha=0.8, linewidth=2)
            legend_handles.append(line)
        
        ax.set_xticks(base_x_positions)
        ax.set_xticklabels(notes_ordered, rotation=45, ha="right")
        ax.set_xlabel("Nota", fontsize=11)
        ax.set_ylabel("Ratio Pares/Impares", fontsize=11)
        ax.set_title("Ratio de Armónicos Pares/Impares (Carácter Tonal)", fontsize=12)
        ax.grid(True, linestyle=':', alpha=0.7)
        
        if legend_handles:
            ax.legend(fontsize=9, loc='best')
        
        fig.tight_layout()
        return fig

    @staticmethod
    def plot_phase_coherence(
            acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
            notes_ordered: List[str],
            ax: Optional[plt.Axes] = None,
            base_colors: List[str] = BASE_COLORS,
            linestyles: List[str] = LINESTYLES
        ) -> plt.Figure:
        """
        Grafica la coherencia de fase entre armónicos.
        Relacionado con la claridad y coherencia del sonido.
        """
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 7))
        else:
            fig = ax.figure
        
        base_x_positions = np.arange(len(notes_ordered))
        legend_handles = []
        
        for index, (analysis_dict, flute_name) in enumerate(acoustic_analysis_list):
            linestyle = linestyles[index % len(linestyles)]
            color = base_colors[index % len(base_colors)]
            
            phase_diffs = []
            
            for note in notes_ordered:
                analysis_obj = analysis_dict.get(note)
                phase_diff = np.nan
                
                if is_impedance_computation_like(analysis_obj):
                    try:
                        frequencies = np.array(analysis_obj.frequencies)
                        impedance = np.array(analysis_obj.impedance)
                        phase = np.angle(impedance)  # Fase en radianes
                        
                        antires = list(analysis_obj.antiresonance_frequencies())
                        if len(antires) >= 2:
                            # Diferencia de fase entre 1er y 2do armónico
                            f1, f2 = antires[0], antires[1]
                            
                            idx1 = np.argmin(np.abs(frequencies - f1))
                            idx2 = np.argmin(np.abs(frequencies - f2))
                            
                            phase1 = phase[idx1]
                            phase2 = phase[idx2]
                            
                            # Normalizar diferencia de fase a [-π, π]
                            diff = phase2 - phase1
                            diff = np.arctan2(np.sin(diff), np.cos(diff))
                            phase_diff = np.degrees(diff)  # Convertir a grados
                        
                    except Exception as e:
                        logger.warning(f"Error calculando coherencia de fase para {flute_name}, nota {note}: {e}")
                
                phase_diffs.append(phase_diff)
            
            line, = ax.plot(base_x_positions, phase_diffs, 
                           marker="o", linestyle=linestyle, color=color, 
                           label=flute_name, markersize=6, alpha=0.8, linewidth=2)
            legend_handles.append(line)
        
        ax.set_xticks(base_x_positions)
        ax.set_xticklabels(notes_ordered, rotation=45, ha="right")
        ax.set_xlabel("Nota", fontsize=11)
        ax.set_ylabel("Diferencia de Fase (grados)", fontsize=11)
        ax.set_title("Coherencia de Fase entre Armónicos", fontsize=12)
        ax.grid(True, linestyle=':', alpha=0.7)
        
        if legend_handles:
            ax.legend(fontsize=9, loc='best')
        
        fig.tight_layout()
        return fig

    @staticmethod
    def plot_pitch_stability(
            acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
            notes_ordered: List[str],
            ax: Optional[plt.Axes] = None,
            base_colors: List[str] = BASE_COLORS,
            linestyles: List[str] = LINESTYLES
        ) -> plt.Figure:
        """
        Grafica la estabilidad de pitch basada en la pendiente de fase.
        Una pendiente de fase pronunciada indica mayor estabilidad.
        """
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 7))
        else:
            fig = ax.figure
        
        base_x_positions = np.arange(len(notes_ordered))
        legend_handles = []
        
        for index, (analysis_dict, flute_name) in enumerate(acoustic_analysis_list):
            linestyle = linestyles[index % len(linestyles)]
            color = base_colors[index % len(base_colors)]
            
            stabilities = []
            
            for note in notes_ordered:
                analysis_obj = analysis_dict.get(note)
                stability = np.nan
                
                if is_impedance_computation_like(analysis_obj):
                    try:
                        frequencies = np.array(analysis_obj.frequencies)
                        impedance = np.array(analysis_obj.impedance)
                        phase = np.angle(impedance)
                        
                        antires = list(analysis_obj.antiresonance_frequencies())
                        if len(antires) >= 1 and antires[0] > 0:
                            target_freq = antires[0]
                            idx_center = np.argmin(np.abs(frequencies - target_freq))
                            
                            # Calcular pendiente de fase alrededor de la resonancia
                            window = 15
                            idx_start = max(0, idx_center - window)
                            idx_end = min(len(phase), idx_center + window)
                            
                            if idx_end - idx_start > 2:
                                freq_window = frequencies[idx_start:idx_end]
                                phase_window = np.unwrap(phase[idx_start:idx_end])
                                
                                # Regresión lineal
                                if len(freq_window) > 2:
                                    slope, _ = np.polyfit(freq_window, phase_window, 1)
                                    stability = abs(slope)  # Mayor valor = mayor estabilidad
                        
                    except Exception as e:
                        logger.warning(f"Error calculando estabilidad pitch para {flute_name}, nota {note}: {e}")
                
                stabilities.append(stability)
            
            line, = ax.plot(base_x_positions, stabilities, 
                           marker="o", linestyle=linestyle, color=color, 
                           label=flute_name, markersize=6, alpha=0.8, linewidth=2)
            legend_handles.append(line)
        
        ax.set_xticks(base_x_positions)
        ax.set_xticklabels(notes_ordered, rotation=45, ha="right")
        ax.set_xlabel("Nota", fontsize=11)
        ax.set_ylabel("Estabilidad (|dφ/df|)", fontsize=11)
        ax.set_title("Estabilidad de Pitch (Pendiente de Fase)", fontsize=12)
        ax.grid(True, linestyle=':', alpha=0.7)
        
        if legend_handles:
            ax.legend(fontsize=9, loc='best')
        
        fig.tight_layout()
        return fig

    @staticmethod
    def plot_cutoff_frequency(
            acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
            notes_ordered: List[str],
            threshold: float = 0.1,
            ax: Optional[plt.Axes] = None,
            base_colors: List[str] = BASE_COLORS,
            linestyles: List[str] = LINESTYLES
        ) -> plt.Figure:
        """
        Grafica la frecuencia de corte (cut-off) para cada nota.
        Indica el límite superior de frecuencia útil del instrumento.
        """
        fig: plt.Figure
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 7))
        else:
            fig = ax.figure
        
        base_x_positions = np.arange(len(notes_ordered))
        legend_handles = []
        
        for index, (analysis_dict, flute_name) in enumerate(acoustic_analysis_list):
            linestyle = linestyles[index % len(linestyles)]
            color = base_colors[index % len(base_colors)]
            
            cutoff_freqs = []
            
            for note in notes_ordered:
                analysis_obj = analysis_dict.get(note)
                cutoff_freq = np.nan
                
                if is_impedance_computation_like(analysis_obj):
                    try:
                        frequencies = np.array(analysis_obj.frequencies)
                        impedance = np.array(analysis_obj.impedance)
                        admittance = np.abs(1.0 / (impedance + 1e-10))
                        
                        # Normalizar admitancia
                        max_admittance = np.max(admittance)
                        if max_admittance > 0:
                            normalized_adm = admittance / max_admittance
                            
                            # Buscar la última frecuencia donde admitancia > threshold
                            indices = np.where(normalized_adm > threshold)[0]
                            if len(indices) > 0:
                                cutoff_freq = frequencies[indices[-1]]
                        
                    except Exception as e:
                        logger.warning(f"Error calculando cut-off para {flute_name}, nota {note}: {e}")
                
                cutoff_freqs.append(cutoff_freq)
            
            line, = ax.plot(base_x_positions, cutoff_freqs, 
                           marker="o", linestyle=linestyle, color=color, 
                           label=flute_name, markersize=6, alpha=0.8, linewidth=2)
            legend_handles.append(line)
        
        ax.set_xticks(base_x_positions)
        ax.set_xticklabels(notes_ordered, rotation=45, ha="right")
        ax.set_xlabel("Nota", fontsize=11)
        ax.set_ylabel("Frecuencia de Corte (Hz)", fontsize=11)
        ax.set_title(f"Frecuencia de Corte (umbral={threshold*100:.0f}%)", fontsize=12)
        ax.grid(True, linestyle=':', alpha=0.7)
        
        if legend_handles:
            ax.legend(fontsize=9, loc='best')
        
        fig.tight_layout()
        return fig

    @staticmethod
    def generate_summary_pdf(
            pdf_filename: str,
            acoustic_analysis_list: List[Tuple[Dict[str, ImpedanceComputation], str]],
            finger_frequencies_map: Dict[str, Dict[str, float]],
            notes_ordered: List[str],
        ) -> str:
        with PdfPages(pdf_filename) as pdf:
            logger.info(f"Generando gráfico MOC para PDF: {pdf_filename}")
            fig_moc = FluteOperations.plot_moc_summary(acoustic_analysis_list, finger_frequencies_map, notes_ordered)
            pdf.savefig(fig_moc); plt.close(fig_moc)

            logger.info(f"Generando gráfico B_I/ESPE para PDF: {pdf_filename}")
            fig_bi_espe = FluteOperations.plot_bi_espe_summary(acoustic_analysis_list, finger_frequencies_map, notes_ordered)
            pdf.savefig(fig_bi_espe); plt.close(fig_bi_espe)

        logger.info(f"Reporte PDF de resumen guardado en: {pdf_filename}")
        return pdf_filename
