"""
Visualización 3D de flautas usando CadQuery.

Este módulo genera modelos 3D de flautas completas y partes individuales,
permitiendo visualización y exportación a formatos CAD (STL, STEP).
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import logging

try:
    import cadquery as cq
    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("CadQuery no está disponible. Instalar con: pip install cadquery")

try:
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    MATPLOTLIB_3D_AVAILABLE = True
except ImportError:
    MATPLOTLIB_3D_AVAILABLE = False

from constants import FLUTE_PARTS_ORDER, M_TO_MM_FACTOR, MM_TO_M_FACTOR

logger = logging.getLogger(__name__)


class Flute3DModel:
    """
    Generador de modelos 3D de flautas.
    """
    
    def __init__(self, flute_data):
        """
        Inicializa el generador de modelos 3D.
        
        Args:
            flute_data: Instancia de FluteData o FluteDataDB.
        """
        self.flute_data = flute_data
        self.parts_3d: Dict[str, Any] = {}
        self.assembly_3d: Optional[Any] = None
    
    def generate_part_model(self, part_name: str) -> Optional[Any]:
        """
        Genera modelo 3D de una parte específica.
        
        Args:
            part_name: Nombre de la parte.
        
        Returns:
            Objeto CadQuery Workplane o None si no está disponible.
        """
        if not CADQUERY_AVAILABLE:
            logger.warning("CadQuery no está disponible para generar modelos 3D")
            return None
        
        part_data = self.flute_data.data.get(part_name, {})
        measurements = part_data.get("measurements", [])
        
        if not measurements:
            logger.warning(f"No hay mediciones para generar modelo 3D de {part_name}")
            return None
        
        # Obtener geometría externa si está disponible
        external_measurements = None
        if hasattr(self.flute_data, 'external_geometry'):
            external_measurements = self.flute_data.external_geometry.get(part_name)
        
        try:
            # Generar modelo usando geometría interna y externa
            model = self._create_cylindrical_model(measurements, external_measurements)
            self.parts_3d[part_name] = model
            return model
        except Exception as e:
            logger.error(f"Error generando modelo 3D para {part_name}: {e}", exc_info=True)
            return None
    
    def _create_cylindrical_model(
        self,
        internal_measurements: List[Dict[str, float]],
        external_measurements: Optional[List[Dict[str, float]]] = None
    ) -> Any:
        """
        Crea un modelo cilíndrico desde mediciones.
        
        Args:
            internal_measurements: Mediciones internas.
            external_measurements: Mediciones externas (opcional).
        
        Returns:
            Objeto CadQuery Workplane.
        """
        if not CADQUERY_AVAILABLE:
            return None
        
        # Convertir mediciones a arrays numpy
        positions = np.array([m.get('position', 0) for m in internal_measurements])
        internal_diameters = np.array([m.get('diameter', 0) for m in internal_measurements])
        internal_radii = internal_diameters / 2.0
        
        # Normalizar posiciones (empezar desde 0)
        positions = positions - positions[0]
        
        # Crear perfil externo si está disponible
        if external_measurements:
            ext_positions = np.array([m.get('position', 0) for m in external_measurements])
            ext_diameters = np.array([m.get('external_diameter', 0) for m in external_measurements])
            ext_radii = ext_diameters / 2.0
            ext_positions = ext_positions - ext_positions[0]
        else:
            # Usar espesor constante por defecto
            wall_thickness = 2.0  # mm
            ext_radii = internal_radii + wall_thickness
            ext_positions = positions
        
        # Crear modelo usando revoluciones
        # Para simplificar, creamos un modelo usando múltiples secciones cilíndricas
        model = cq.Workplane("XY")
        
        # Crear secciones a lo largo de la longitud
        num_sections = len(positions)
        for i in range(num_sections - 1):
            z_start = positions[i] * MM_TO_M_FACTOR
            z_end = positions[i + 1] * MM_TO_M_FACTOR
            r_start = ext_radii[i] * MM_TO_M_FACTOR
            r_end = ext_radii[i + 1] * MM_TO_M_FACTOR
            
            # Crear sección cilíndrica
            if abs(r_start - r_end) < 1e-6:
                # Cilindro uniforme
                height = abs(z_end - z_start)
                section = cq.Workplane("XY").circle(r_start).extrude(height)
            else:
                # Tronco de cono
                height = abs(z_end - z_start)
                # Crear perfil trapezoidal y revolucionar
                points = [
                    (0, 0),
                    (r_start, 0),
                    (r_end, height),
                    (0, height)
                ]
                section = cq.Workplane("XY").polyline(points).close().revolve(360)
            
            # Posicionar y unir
            if i == 0:
                model = section.translate((0, 0, z_start))
            else:
                section = section.translate((0, 0, z_start))
                model = model.union(section)
        
        # Crear hueco interno (bore)
        bore_model = cq.Workplane("XY")
        for i in range(num_sections - 1):
            z_start = positions[i] * MM_TO_M_FACTOR
            z_end = positions[i + 1] * MM_TO_M_FACTOR
            r_start = internal_radii[i] * MM_TO_M_FACTOR
            r_end = internal_radii[i + 1] * MM_TO_M_FACTOR
            
            height = abs(z_end - z_start)
            if abs(r_start - r_end) < 1e-6:
                bore_section = cq.Workplane("XY").circle(r_start).extrude(height)
            else:
                points = [
                    (0, 0),
                    (r_start, 0),
                    (r_end, height),
                    (0, height)
                ]
                bore_section = cq.Workplane("XY").polyline(points).close().revolve(360)
            
            if i == 0:
                bore_model = bore_section.translate((0, 0, z_start))
            else:
                bore_section = bore_section.translate((0, 0, z_start))
                bore_model = bore_model.union(bore_section)
        
        # Restar el bore del modelo externo
        model = model.cut(bore_model)
        
        return model
    
    def generate_assembly_model(self) -> Optional[Any]:
        """
        Genera modelo 3D del ensamblaje completo usando la misma lógica que combine_measurements.
        
        Returns:
            Objeto CadQuery Workplane o None.
        """
        if not CADQUERY_AVAILABLE:
            logger.warning("CadQuery no está disponible")
            return None
        
        # Calcular posiciones físicas de inicio de cada parte usando la misma lógica que combine_measurements
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
                current_physical_start_abs = 0.0
                # Left se conecta al inicio del socket de HJ
                socket_start_abs = current_physical_start_abs + part_total_length - part_mortise_length
                next_part_connection_point_abs = socket_start_abs
            elif i == 1:  # Left (se inserta en Headjoint)
                # Left comienza donde termina el cuerpo de Headjoint (antes del socket de HJ)
                hj_data = self.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                hj_total_length = hj_data.get("Total length", 0.0)
                hj_mortise_length = hj_data.get("Mortise length", 0.0)
                current_physical_start_abs = hj_total_length - hj_mortise_length
                # Right se conecta al final de Left
                next_part_connection_point_abs = current_physical_start_abs + part_total_length
            else:  # Right, Foot (se insertan en la anterior)
                # El inicio físico es el final de la parte anterior menos el socket de la parte actual
                current_physical_start_abs = next_part_connection_point_abs - part_mortise_length
                if part_name == FLUTE_PARTS_ORDER[2]:  # Right
                    # Foot se conecta al final de Right
                    next_part_connection_point_abs = current_physical_start_abs + part_total_length
            
            part_physical_starts[part_name] = current_physical_start_abs
        
        # Generar modelos de todas las partes y posicionarlas según los offsets calculados
        part_models = []
        
        for part_name in FLUTE_PARTS_ORDER:
            part_model = self.generate_part_model(part_name)
            if part_model:
                # Obtener el offset físico calculado para esta parte (convertir mm a m)
                part_offset_z_m = part_physical_starts.get(part_name, 0.0) * MM_TO_M_FACTOR
                
                # Posicionar la parte según su offset físico calculado
                positioned_model = part_model.translate((0, 0, part_offset_z_m))
                part_models.append(positioned_model)
        
        # Unir todas las partes
        if part_models:
            self.assembly_3d = part_models[0]
            for part_model in part_models[1:]:
                self.assembly_3d = self.assembly_3d.union(part_model)
        
        return self.assembly_3d
    
    def export_to_stl(self, output_path: str, part_name: Optional[str] = None) -> bool:
        """
        Exporta modelo 3D a formato STL.
        
        Args:
            output_path: Ruta al archivo STL de salida.
            part_name: Nombre de la parte (opcional). Si es None, exporta el ensamblaje.
        
        Returns:
            True si la exportación fue exitosa.
        """
        if not CADQUERY_AVAILABLE:
            logger.error("CadQuery no está disponible para exportar STL")
            return False
        
        try:
            if part_name:
                model = self.parts_3d.get(part_name)
                if not model:
                    model = self.generate_part_model(part_name)
            else:
                if not self.assembly_3d:
                    self.generate_assembly_model()
                model = self.assembly_3d
            
            if not model:
                logger.error("No hay modelo para exportar")
                return False
            
            # Exportar a STL
            cq.exporters.export(model, str(output_path))
            logger.info(f"Modelo 3D exportado a STL: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error exportando a STL: {e}", exc_info=True)
            return False
    
    def export_to_step(self, output_path: str, part_name: Optional[str] = None) -> bool:
        """
        Exporta modelo 3D a formato STEP.
        
        Args:
            output_path: Ruta al archivo STEP de salida.
            part_name: Nombre de la parte (opcional).
        
        Returns:
            True si la exportación fue exitosa.
        """
        if not CADQUERY_AVAILABLE:
            logger.error("CadQuery no está disponible para exportar STEP")
            return False
        
        try:
            if part_name:
                model = self.parts_3d.get(part_name)
                if not model:
                    model = self.generate_part_model(part_name)
            else:
                if not self.assembly_3d:
                    self.generate_assembly_model()
                model = self.assembly_3d
            
            if not model:
                logger.error("No hay modelo para exportar")
                return False
            
            # Exportar a STEP
            cq.exporters.export(model, str(output_path))
            logger.info(f"Modelo 3D exportado a STEP: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error exportando a STEP: {e}", exc_info=True)
            return False
    
    def visualize_with_matplotlib(self, part_name: Optional[str] = None, ax=None) -> None:
        """
        Visualiza el modelo 3D usando matplotlib (fallback si CadQuery no está disponible).
        
        Args:
            part_name: Nombre de la parte (opcional).
            ax: Eje de matplotlib 3D (opcional).
        """
        if not MATPLOTLIB_3D_AVAILABLE:
            logger.warning("Matplotlib 3D no está disponible")
            return
        
        if ax is None:
            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection='3d')
        
        if part_name:
            part_data = self.flute_data.data.get(part_name, {})
            measurements = part_data.get("measurements", [])
        else:
            measurements = self.flute_data.combined_measurements
        
        if not measurements:
            logger.warning("No hay mediciones para visualizar")
            return
        
        positions = np.array([m.get('position', 0) for m in measurements])
        diameters = np.array([m.get('diameter', 0) for m in measurements])
        radii = diameters / 2.0
        
        # Normalizar posiciones
        positions = positions - positions[0]
        
        # Crear superficie cilíndrica
        theta = np.linspace(0, 2 * np.pi, 50)
        z = positions
        theta_grid, z_grid = np.meshgrid(theta, z)
        
        # Interpolar radios
        r_interp = np.interp(z_grid.flatten(), positions, radii)
        r_grid = r_interp.reshape(z_grid.shape)
        
        x = r_grid * np.cos(theta_grid)
        y = r_grid * np.sin(theta_grid)
        
        ax.plot_surface(x, y, z_grid, alpha=0.7, color='lightblue')
        ax.set_xlabel('X (mm)')
        ax.set_ylabel('Y (mm)')
        ax.set_zlabel('Z (mm)')
        
        title = f"{part_name.capitalize() if part_name else 'Ensamblaje'} - {self.flute_data.flute_model}"
        ax.set_title(title)
        
        return ax


def compare_flutes_3d(flute_models: List[Flute3DModel], ax=None) -> None:
    """
    Compara múltiples flautas en 3D.
    
    Args:
        flute_models: Lista de objetos Flute3DModel.
        ax: Eje de matplotlib 3D (opcional).
    """
    if not MATPLOTLIB_3D_AVAILABLE:
        logger.warning("Matplotlib 3D no está disponible")
        return
    
    if ax is None:
        fig = plt.figure(figsize=(14, 10))
        ax = fig.add_subplot(111, projection='3d')
    
    colors_list = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
    
    for idx, flute_model in enumerate(flute_models):
        color = colors_list[idx % len(colors_list)]
        flute_model.visualize_with_matplotlib(ax=ax)
        # Cambiar color para cada flauta (simplificado)
    
    ax.set_title("Comparación de Flautas en 3D")
    return ax

