"""
Módulo para extracción de estadísticas de la base de datos y generación de reportes.

Este módulo proporciona funcionalidad para:
- Extraer métricas geométricas de todas las flautas en la base de datos
- Calcular estadísticas descriptivas (promedio, std, min, max, mediana)
- Generar reportes PDF con visualizaciones comparativas
"""

import json
import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
import sqlite3

from constants import FLUTE_PARTS_ORDER, M_TO_MM_FACTOR
from flute_db_manager import FluteDBManager

logger = logging.getLogger(__name__)


class DatabaseStatisticsExtractor:
    """Extrae métricas geométricas de todas las flautas en la base de datos."""
    
    def __init__(self, db_manager: FluteDBManager):
        """
        Inicializa el extractor de estadísticas.
        
        Args:
            db_manager: Gestor de base de datos de flautas.
        """
        self.db_manager = db_manager
    
    def extract_all_flutes_metrics(self, flute_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Extrae todas las métricas geométricas de las flautas en la BD.
        
        Args:
            flute_names: Lista opcional de nombres de flautas a procesar. Si es None, procesa todas.
        
        Returns:
            Lista de diccionarios con métricas por flauta.
        """
        conn = self.db_manager._get_connection()
        cursor = conn.cursor()
        
        try:
            # Obtener todas las flautas
            if flute_names:
                placeholders = ','.join('?' * len(flute_names))
                cursor.execute(f"SELECT id, flute_model FROM flutes WHERE flute_model IN ({placeholders})", flute_names)
            else:
                cursor.execute("SELECT id, flute_model FROM flutes")
            
            flutes = cursor.fetchall()
            logger.info(f"Extrayendo métricas de {len(flutes)} flautas...")
            
            all_metrics = []
            
            for flute_row in flutes:
                flute_id = flute_row['id']
                flute_model = flute_row['flute_model']
                
                try:
                    metrics = self._extract_flute_metrics(flute_id, flute_model)
                    if metrics:
                        all_metrics.append(metrics)
                except Exception as e:
                    logger.error(f"Error extrayendo métricas de {flute_model}: {e}", exc_info=True)
                    continue
            
            logger.info(f"Métricas extraídas exitosamente de {len(all_metrics)} flautas")
            return all_metrics
            
        finally:
            conn.close()
    
    def _extract_flute_metrics(self, flute_id: int, flute_model: str) -> Optional[Dict[str, Any]]:
        """
        Extrae todas las métricas de una flauta específica.
        
        Args:
            flute_id: ID de la flauta en la BD.
            flute_model: Nombre del modelo de flauta.
        
        Returns:
            Diccionario con todas las métricas de la flauta.
        """
        metrics = {
            'flute_model': flute_model,
            'flute_id': flute_id,
            'slopes_by_part': {},
            'cone_angles_by_part': {},
            'holes_diameters': {},
            'holes_positions': {},
            'part_physical_lengths': {},
            'part_acoustic_lengths': {},
            'embouchure_diameter': None,
            'total_acoustic_length': None,
            'combined_measurements': None,
            'stopper_position': None
        }
        
        # Obtener geometría de cada parte
        geometry_dict = self.db_manager.get_flute_geometry(flute_id)
        
        if not geometry_dict:
            logger.warning(f"No se encontró geometría para {flute_model}")
            return None
        
        # Extraer métricas de cada parte
        for part_name in FLUTE_PARTS_ORDER:
            part_data = geometry_dict.get(part_name, {})
            
            if not part_data:
                continue
            
            # Pendiente y ángulo del cono
            measurements = part_data.get('measurements', [])
            if measurements and len(measurements) >= 2:
                slope, cone_angle = self._calculate_slope_and_angle(measurements)
                metrics['slopes_by_part'][part_name] = slope
                metrics['cone_angles_by_part'][part_name] = cone_angle
            
            # Largos físicos
            total_length = part_data.get('Total length', 0.0)
            metrics['part_physical_lengths'][part_name] = total_length
            
            # Largos acústicos
            mortise_length = part_data.get('Mortise length', 0.0)
            if part_name == FLUTE_PARTS_ORDER[0]:  # Headjoint
                acoustic_length = total_length - mortise_length
            elif part_name == FLUTE_PARTS_ORDER[1]:  # Body (left)
                acoustic_length = total_length
            else:  # Foot (right)
                acoustic_length = total_length - mortise_length
            metrics['part_acoustic_lengths'][part_name] = acoustic_length
            
            # Agujeros (diámetros y posiciones)
            holes_pos = part_data.get('Holes position', [])
            holes_diam = part_data.get('Holes diameter', [])
            
            if holes_pos and holes_diam:
                for i, (pos, diam) in enumerate(zip(holes_pos, holes_diam)):
                    hole_label = f"{part_name}_hole_{i+1}"
                    metrics['holes_positions'][hole_label] = pos
                    metrics['holes_diameters'][hole_label] = diam
                    
                    # Embocadura (primer agujero del headjoint)
                    if part_name == FLUTE_PARTS_ORDER[0] and i == 0:
                        metrics['embouchure_diameter'] = diam
        
        # Calcular largo acústico total y posición del corcho
        headjoint_data = geometry_dict.get(FLUTE_PARTS_ORDER[0], {})
        stopper_pos = headjoint_data.get('_calculated_stopper_absolute_position_mm', 0.0)
        metrics['stopper_position'] = stopper_pos
        
        # Reconstruir combined_measurements para calcular largo acústico total
        combined_measurements = self._reconstruct_combined_measurements(geometry_dict)
        metrics['combined_measurements'] = combined_measurements
        
        if combined_measurements and len(combined_measurements) > 0:
            acoustic_start = stopper_pos
            acoustic_end = max(m['position'] for m in combined_measurements)
            metrics['total_acoustic_length'] = acoustic_end - acoustic_start
        
        return metrics
    
    def _calculate_slope_and_angle(self, measurements: List[Dict]) -> Tuple[float, float]:
        """
        Calcula la pendiente y ángulo del cono usando regresión lineal.
        
        Args:
            measurements: Lista de mediciones [{'position': float, 'diameter': float}]
        
        Returns:
            Tupla (pendiente en mm/mm, ángulo en grados)
        """
        if len(measurements) < 2:
            return 0.0, 0.0
        
        try:
            positions = np.array([m.get('position', 0.0) for m in measurements])
            diameters = np.array([m.get('diameter', 0.0) for m in measurements])
            
            # Regresión lineal: diámetro = pendiente * posición + intercepto
            slope, intercept = np.polyfit(positions, diameters, 1)
            
            # Ángulo del cono: atan(dr/dx) = atan(pendiente/2)
            cone_angle_deg = np.arctan(slope / 2.0) * 180.0 / np.pi
            
            return float(slope), float(cone_angle_deg)
        except Exception as e:
            logger.warning(f"Error calculando pendiente: {e}")
            return 0.0, 0.0
    
    def _reconstruct_combined_measurements(self, geometry_dict: Dict[str, Any]) -> List[Dict[str, float]]:
        """
        Reconstruye las mediciones combinadas desde la geometría de partes.
        
        Args:
            geometry_dict: Diccionario con geometría de todas las partes.
        
        Returns:
            Lista de mediciones combinadas [{'position': float, 'diameter': float}]
        """
        combined = []
        current_position = 0.0
        
        for part_name in FLUTE_PARTS_ORDER:
            part_data = geometry_dict.get(part_name, {})
            
            if not part_data:
                continue
            
            measurements = part_data.get('measurements', [])
            total_length = part_data.get('Total length', 0.0)
            mortise_length = part_data.get('Mortise length', 0.0)
            
            # Ajustar posiciones según ensamblaje
            if part_name == FLUTE_PARTS_ORDER[0]:  # Headjoint
                # Agregar mediciones desde el inicio hasta antes del mortise
                for m in measurements:
                    pos = m.get('position', 0.0)
                    if pos <= (total_length - mortise_length):
                        combined.append({
                            'position': current_position + pos,
                            'diameter': m.get('diameter', 0.0)
                        })
                current_position += total_length - mortise_length
            else:
                # Para left y foot, agregar desde después del mortise
                acoustic_start = mortise_length if part_name != FLUTE_PARTS_ORDER[1] else 0.0
                for m in measurements:
                    pos = m.get('position', 0.0)
                    if pos >= acoustic_start:
                        combined.append({
                            'position': current_position + (pos - acoustic_start),
                            'diameter': m.get('diameter', 0.0)
                        })
                current_position += total_length - acoustic_start
        
        return combined


class StatisticsReportGenerator:
    """Genera reportes PDF con estadísticas y visualizaciones."""
    
    def __init__(self, metrics_data: List[Dict[str, Any]]):
        """
        Inicializa el generador de reportes.
        
        Args:
            metrics_data: Lista de métricas extraídas de todas las flautas.
        """
        self.metrics_data = metrics_data
        self.stats = {}
    
    def generate_report(
        self,
        output_path: Path,
        config: Dict[str, Any]
    ) -> None:
        """
        Genera el reporte PDF completo.
        
        Args:
            output_path: Ruta donde guardar el PDF.
            config: Configuración del reporte (qué métricas incluir, formato, etc.)
        """
        logger.info(f"Generando reporte estadístico en {output_path}...")
        
        with PdfPages(output_path) as pdf:
            # Portada
            self._generate_cover_page(pdf, config)
            
            # Resumen ejecutivo
            if config.get('include_summary', True):
                self._generate_summary_page(pdf)
            
            # Tabla detallada de todas las flautas (NUEVO)
            self._generate_detailed_table(pdf, config)
            
            # Pendientes por parte
            if config.get('include_slopes', True):
                self._generate_slopes_section(pdf, config)
            
            # Tamaños de agujeros
            if config.get('include_holes', True):
                self._generate_holes_section(pdf, config)
            
            # Largos físicos por parte
            if config.get('include_physical_lengths', True):
                self._generate_physical_lengths_section(pdf, config)
            
            # Diámetro de embocadura
            if config.get('include_embouchure', True):
                self._generate_embouchure_section(pdf, config)
            
            # Largo acústico total
            if config.get('include_acoustic_length', True):
                self._generate_acoustic_length_section(pdf, config)
            
            # Correlaciones
            if config.get('include_correlations', False):
                self._generate_correlations_section(pdf, config)
        
        logger.info(f"Reporte generado exitosamente: {output_path}")
    
    def _generate_cover_page(self, pdf: PdfPages, config: Dict[str, Any]) -> None:
        """Genera la portada del reporte."""
        fig = Figure(figsize=(8.5, 11))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # Título
        ax.text(0.5, 0.7, 'Reporte Estadístico de Base de Datos',
                ha='center', va='center', fontsize=24, weight='bold',
                transform=ax.transAxes)
        
        ax.text(0.5, 0.6, 'Análisis Comparativo de Flautas Traverso',
                ha='center', va='center', fontsize=16,
                transform=ax.transAxes)
        
        # Información del reporte
        info_text = f"""
        Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M')}
        
        Número de flautas analizadas: {len(self.metrics_data)}
        
        Métricas incluidas:
        {'✓ Pendientes por parte' if config.get('include_slopes', True) else ''}
        {'✓ Tamaños de agujeros' if config.get('include_holes', True) else ''}
        {'✓ Largos físicos por parte' if config.get('include_physical_lengths', True) else ''}
        {'✓ Diámetro de embocadura' if config.get('include_embouchure', True) else ''}
        {'✓ Largo acústico total' if config.get('include_acoustic_length', True) else ''}
        {'✓ Análisis de correlaciones' if config.get('include_correlations', False) else ''}
        """
        
        ax.text(0.5, 0.35, info_text,
                ha='center', va='center', fontsize=10,
                transform=ax.transAxes, family='monospace')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _generate_summary_page(self, pdf: PdfPages) -> None:
        """Genera página de resumen ejecutivo con tabla de estadísticas."""
        fig = Figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        ax.text(0.5, 0.95, 'Resumen Ejecutivo',
                ha='center', va='top', fontsize=18, weight='bold',
                transform=ax.transAxes)
        
        # Preparar datos para tabla
        summary_data = []
        
        # Estadísticas de largo acústico
        acoustic_lengths = [m['total_acoustic_length'] for m in self.metrics_data 
                           if m['total_acoustic_length'] is not None]
        if acoustic_lengths:
            summary_data.append([
                'Largo Acústico Total (mm)',
                f"{np.mean(acoustic_lengths):.1f}",
                f"{np.std(acoustic_lengths):.1f}",
                f"{np.min(acoustic_lengths):.1f}",
                f"{np.max(acoustic_lengths):.1f}",
                f"{np.median(acoustic_lengths):.1f}"
            ])
        
        # Estadísticas de diámetro de embocadura
        emb_diameters = [m['embouchure_diameter'] for m in self.metrics_data 
                        if m['embouchure_diameter'] is not None]
        if emb_diameters:
            summary_data.append([
                'Diámetro Embocadura (mm)',
                f"{np.mean(emb_diameters):.2f}",
                f"{np.std(emb_diameters):.2f}",
                f"{np.min(emb_diameters):.2f}",
                f"{np.max(emb_diameters):.2f}",
                f"{np.median(emb_diameters):.2f}"
            ])
        
        # Estadísticas de pendientes por parte
        for part_name in FLUTE_PARTS_ORDER:
            slopes = [m['slopes_by_part'].get(part_name, np.nan) 
                     for m in self.metrics_data]
            slopes = [s for s in slopes if not np.isnan(s)]
            
            if slopes:
                summary_data.append([
                    f'Pendiente {part_name} (mm/mm)',
                    f"{np.mean(slopes):.4f}",
                    f"{np.std(slopes):.4f}",
                    f"{np.min(slopes):.4f}",
                    f"{np.max(slopes):.4f}",
                    f"{np.median(slopes):.4f}"
                ])
        
        # Crear tabla
        if summary_data:
            col_labels = ['Métrica', 'Promedio', 'Desv. Std', 'Mínimo', 'Máximo', 'Mediana']
            table = ax.table(cellText=summary_data, colLabels=col_labels,
                           cellLoc='center', loc='center',
                           bbox=[0.1, 0.1, 0.8, 0.7])
            
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1, 2)
            
            # Estilo de encabezados
            for i in range(len(col_labels)):
                table[(0, i)].set_facecolor('#4472C4')
                table[(0, i)].set_text_props(weight='bold', color='white')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _generate_detailed_table(self, pdf: PdfPages, config: Dict[str, Any]) -> None:
        """Genera tabla detallada con todas las métricas de cada flauta."""
        # Determinar qué métricas incluir
        include_slopes = config.get('include_slopes', True)
        include_holes = config.get('include_holes', True)
        include_physical_lengths = config.get('include_physical_lengths', True)
        include_embouchure = config.get('include_embouchure', True)
        include_acoustic_length = config.get('include_acoustic_length', True)
        
        # Preparar encabezados de columnas
        col_labels = ['Flauta']
        col_types = ['name']  # Para saber qué tipo de dato es cada columna
        
        if include_slopes:
            for part in FLUTE_PARTS_ORDER:
                col_labels.append(f'Pend.\n{part[:4]}.')  # Abreviar nombres
                col_types.append(f'slope_{part}')
        
        if include_embouchure:
            col_labels.append('Emb.\n(mm)')
            col_types.append('embouchure')
        
        if include_acoustic_length:
            col_labels.append('L.Acús.\n(mm)')
            col_types.append('acoustic_length')
        
        if include_physical_lengths:
            for part in FLUTE_PARTS_ORDER:
                col_labels.append(f'L.Fís.\n{part[:4]}.')
                col_types.append(f'physical_{part}')
        
        # Calcular estadísticas para identificar outliers (±2 desviaciones estándar)
        stats_by_metric = {}
        
        # Estadísticas de pendientes
        if include_slopes:
            for part in FLUTE_PARTS_ORDER:
                values = [m['slopes_by_part'].get(part, np.nan) for m in self.metrics_data]
                values = [v for v in values if not np.isnan(v)]
                if values:
                    mean = np.mean(values)
                    std = np.std(values)
                    stats_by_metric[f'slope_{part}'] = {
                        'mean': mean,
                        'std': std,
                        'lower': mean - 2*std,
                        'upper': mean + 2*std
                    }
        
        # Estadísticas de embocadura
        if include_embouchure:
            values = [m['embouchure_diameter'] for m in self.metrics_data if m['embouchure_diameter'] is not None]
            if values:
                mean = np.mean(values)
                std = np.std(values)
                stats_by_metric['embouchure'] = {
                    'mean': mean,
                    'std': std,
                    'lower': mean - 2*std,
                    'upper': mean + 2*std
                }
        
        # Estadísticas de largo acústico
        if include_acoustic_length:
            values = [m['total_acoustic_length'] for m in self.metrics_data if m['total_acoustic_length'] is not None]
            if values:
                mean = np.mean(values)
                std = np.std(values)
                stats_by_metric['acoustic_length'] = {
                    'mean': mean,
                    'std': std,
                    'lower': mean - 2*std,
                    'upper': mean + 2*std
                }
        
        # Estadísticas de largos físicos
        if include_physical_lengths:
            for part in FLUTE_PARTS_ORDER:
                values = [m['part_physical_lengths'].get(part, np.nan) for m in self.metrics_data]
                values = [v for v in values if not np.isnan(v)]
                if values:
                    mean = np.mean(values)
                    std = np.std(values)
                    stats_by_metric[f'physical_{part}'] = {
                        'mean': mean,
                        'std': std,
                        'lower': mean - 2*std,
                        'upper': mean + 2*std
                    }
        
        # Preparar datos de tabla y marcar outliers
        table_data = []
        outlier_flags = []  # Para marcar qué celdas son outliers
        
        for metric in self.metrics_data:
            row = [metric['flute_model'][:20]]  # Limitar longitud del nombre
            row_outliers = [False]  # Primera columna (nombre) nunca es outlier
            
            # Pendientes
            if include_slopes:
                for part in FLUTE_PARTS_ORDER:
                    slope = metric['slopes_by_part'].get(part, np.nan)
                    if np.isnan(slope):
                        row.append('-')
                        row_outliers.append(False)
                    else:
                        row.append(f"{slope:.4f}")
                        # Verificar si es outlier
                        metric_key = f'slope_{part}'
                        if metric_key in stats_by_metric:
                            stats = stats_by_metric[metric_key]
                            is_outlier = slope < stats['lower'] or slope > stats['upper']
                            row_outliers.append(is_outlier)
                        else:
                            row_outliers.append(False)
            
            # Embocadura
            if include_embouchure:
                emb = metric['embouchure_diameter']
                if emb is None or np.isnan(emb):
                    row.append('-')
                    row_outliers.append(False)
                else:
                    row.append(f"{emb:.2f}")
                    if 'embouchure' in stats_by_metric:
                        stats = stats_by_metric['embouchure']
                        is_outlier = emb < stats['lower'] or emb > stats['upper']
                        row_outliers.append(is_outlier)
                    else:
                        row_outliers.append(False)
            
            # Largo acústico
            if include_acoustic_length:
                lac = metric['total_acoustic_length']
                if lac is None or np.isnan(lac):
                    row.append('-')
                    row_outliers.append(False)
                else:
                    row.append(f"{lac:.1f}")
                    if 'acoustic_length' in stats_by_metric:
                        stats = stats_by_metric['acoustic_length']
                        is_outlier = lac < stats['lower'] or lac > stats['upper']
                        row_outliers.append(is_outlier)
                    else:
                        row_outliers.append(False)
            
            # Largos físicos
            if include_physical_lengths:
                for part in FLUTE_PARTS_ORDER:
                    length = metric['part_physical_lengths'].get(part, np.nan)
                    if np.isnan(length):
                        row.append('-')
                        row_outliers.append(False)
                    else:
                        row.append(f"{length:.1f}")
                        metric_key = f'physical_{part}'
                        if metric_key in stats_by_metric:
                            stats = stats_by_metric[metric_key]
                            is_outlier = length < stats['lower'] or length > stats['upper']
                            row_outliers.append(is_outlier)
                        else:
                            row_outliers.append(False)
            
            table_data.append(row)
            outlier_flags.append(row_outliers)
        
        # Dividir en múltiples páginas si es necesario
        rows_per_page = 25
        num_pages = (len(table_data) + rows_per_page - 1) // rows_per_page
        
        for page_idx in range(num_pages):
            fig = Figure(figsize=(11, 8.5))
            ax = fig.add_subplot(111)
            ax.axis('off')
            
            # Título
            title = 'Tabla Detallada de Métricas por Flauta'
            if num_pages > 1:
                title += f' (Página {page_idx + 1} de {num_pages})'
            
            ax.text(0.5, 0.98, title,
                    ha='center', va='top', fontsize=14, weight='bold',
                    transform=ax.transAxes)
            
            # Obtener datos para esta página
            start_idx = page_idx * rows_per_page
            end_idx = min(start_idx + rows_per_page, len(table_data))
            page_data = table_data[start_idx:end_idx]
            
            # Crear tabla
            if page_data:
                # Calcular posición y tamaño de la tabla
                num_rows = len(page_data)
                num_cols = len(col_labels)
                
                # Ajustar altura de celdas según número de filas
                row_height = min(0.7 / num_rows, 0.035)
                table_height = row_height * (num_rows + 1)  # +1 para el encabezado
                
                # Calcular posición vertical
                y_pos = 0.5 - (table_height / 2)
                
                table = ax.table(
                    cellText=page_data,
                    colLabels=col_labels,
                    cellLoc='center',
                    loc='center',
                    bbox=[0.05, y_pos, 0.9, table_height]
                )
                
                table.auto_set_font_size(False)
                table.set_fontsize(7)
                table.scale(1, 1.5)
                
                # Estilo de encabezados
                for i in range(len(col_labels)):
                    cell = table[(0, i)]
                    cell.set_facecolor('#4472C4')
                    cell.set_text_props(weight='bold', color='white', fontsize=7)
                
                # Colorear celdas según tipo de valor
                actual_start_idx = start_idx
                for i in range(1, len(page_data) + 1):
                    data_idx = actual_start_idx + i - 1
                    for j in range(len(col_labels)):
                        cell = table[(i, j)]
                        
                        # Obtener flags de outlier para esta fila
                        if data_idx < len(outlier_flags):
                            is_outlier = outlier_flags[data_idx][j]
                        else:
                            is_outlier = False
                        
                        cell_text = table[(i, j)].get_text().get_text()
                        
                        # Prioridad de colores:
                        # 1. Outliers (valores anómalos) - Naranja
                        # 2. Datos faltantes - Rojo claro
                        # 3. Filas alternas - Gris claro
                        if is_outlier:
                            cell.set_facecolor('#FFD700')  # Amarillo/naranja para outliers
                            cell.set_text_props(weight='bold')
                        elif cell_text == '-':
                            cell.set_facecolor('#FFE6E6')  # Rojo claro para datos faltantes
                        elif i % 2 == 0:
                            cell.set_facecolor('#F2F2F2')  # Gris claro para filas alternas
                
                # Agregar leyenda en la parte inferior
                legend_text = (
                    "Pend. = Pendiente (mm/mm) | Emb. = Embocadura | L.Acús. = Largo Acústico | "
                    "L.Fís. = Largo Físico\n"
                    "🟡 Amarillo = Valores anómalos (±2 desv. std) | "
                    "🔴 Rosado = Datos faltantes"
                )
                ax.text(0.5, 0.02, legend_text,
                       ha='center', va='bottom', fontsize=7, style='italic',
                       transform=ax.transAxes)
            
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
        
        # Generar página de resumen de anomalías
        self._generate_anomalies_summary(
            pdf, 
            table_data, 
            outlier_flags, 
            col_labels,
            col_types,
            stats_by_metric
        )
    
    def _generate_anomalies_summary(
        self, 
        pdf: PdfPages, 
        table_data: List[List[str]], 
        outlier_flags: List[List[bool]],
        col_labels: List[str],
        col_types: List[str],
        stats_by_metric: Dict[str, Dict[str, float]]
    ) -> None:
        """Genera una página con resumen de valores anómalos detectados."""
        fig = Figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # Título
        ax.text(0.5, 0.98, 'Resumen de Valores Anómalos Detectados',
                ha='center', va='top', fontsize=16, weight='bold',
                transform=ax.transAxes)
        
        # Recopilar todas las anomalías
        anomalies_list = []
        
        for row_idx, (row_data, row_outliers) in enumerate(zip(table_data, outlier_flags)):
            flute_name = row_data[0]
            
            for col_idx, (value, is_outlier) in enumerate(zip(row_data[1:], row_outliers[1:])):
                if is_outlier and value != '-':
                    metric_name = col_labels[col_idx + 1]
                    metric_type = col_types[col_idx + 1]
                    
                    # Obtener estadísticas de esta métrica
                    if metric_type in stats_by_metric:
                        stats = stats_by_metric[metric_type]
                        mean = stats['mean']
                        std = stats['std']
                        
                        # Calcular cuántas desviaciones estándar se aleja
                        try:
                            numeric_value = float(value)
                            deviations = abs(numeric_value - mean) / std if std > 0 else 0
                            
                            anomalies_list.append({
                                'flute': flute_name,
                                'metric': metric_name.replace('\n', ' '),
                                'value': value,
                                'mean': f"{mean:.3f}",
                                'std_devs': f"{deviations:.1f}"
                            })
                        except:
                            pass
        
        if not anomalies_list:
            # No hay anomalías
            ax.text(0.5, 0.5, 
                   '✓ No se detectaron valores anómalos\n\n'
                   'Todas las métricas están dentro del rango esperado\n'
                   '(±2 desviaciones estándar de la media)',
                   ha='center', va='center', fontsize=14,
                   transform=ax.transAxes)
        else:
            # Crear tabla de anomalías
            ax.text(0.5, 0.92, 
                   f'Se detectaron {len(anomalies_list)} valores fuera del rango esperado (±2σ):',
                   ha='center', va='top', fontsize=12,
                   transform=ax.transAxes)
            
            # Preparar datos para la tabla
            anomaly_table_data = []
            for anomaly in anomalies_list[:40]:  # Limitar a 40 anomalías para que quepa
                anomaly_table_data.append([
                    anomaly['flute'],
                    anomaly['metric'],
                    anomaly['value'],
                    anomaly['mean'],
                    f"±{anomaly['std_devs']}σ"
                ])
            
            if anomaly_table_data:
                col_headers = ['Flauta', 'Métrica', 'Valor', 'Media', 'Desviación']
                
                # Calcular altura de tabla
                num_rows = len(anomaly_table_data)
                row_height = min(0.75 / num_rows, 0.03)
                table_height = row_height * (num_rows + 1)
                y_pos = 0.45 - (table_height / 2)
                
                table = ax.table(
                    cellText=anomaly_table_data,
                    colLabels=col_headers,
                    cellLoc='center',
                    loc='center',
                    bbox=[0.05, y_pos, 0.9, table_height]
                )
                
                table.auto_set_font_size(False)
                table.set_fontsize(8)
                table.scale(1, 1.8)
                
                # Estilo de encabezados
                for i in range(len(col_headers)):
                    cell = table[(0, i)]
                    cell.set_facecolor('#FF6B6B')
                    cell.set_text_props(weight='bold', color='white')
                
                # Alternar colores de filas
                for i in range(1, len(anomaly_table_data) + 1):
                    for j in range(len(col_headers)):
                        cell = table[(i, j)]
                        if i % 2 == 0:
                            cell.set_facecolor('#FFF3CD')
                        else:
                            cell.set_facecolor('#FFE6E6')
                
                # Nota al pie
                note_y = y_pos - 0.05
                if len(anomalies_list) > 40:
                    ax.text(0.5, note_y,
                           f'Nota: Se muestran las primeras 40 de {len(anomalies_list)} anomalías detectadas',
                           ha='center', va='top', fontsize=8, style='italic',
                           transform=ax.transAxes)
                
                ax.text(0.5, 0.02,
                       'Recomendación: Revisar estas flautas para verificar si los valores son correctos\n'
                       'o si hay errores en las mediciones.',
                       ha='center', va='bottom', fontsize=9, style='italic',
                       transform=ax.transAxes,
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _generate_slopes_section(self, pdf: PdfPages, config: Dict[str, Any]) -> None:
        """Genera sección de análisis de pendientes."""
        # Página 1: Box plot comparativo
        fig1 = Figure(figsize=(11, 8.5))
        fig1.suptitle('Análisis de Pendientes por Parte', fontsize=16, weight='bold')
        
        # Preparar datos
        slopes_by_part = {part: [] for part in FLUTE_PARTS_ORDER}
        flute_labels = []
        
        for metric in self.metrics_data:
            flute_labels.append(metric['flute_model'])
            for part in FLUTE_PARTS_ORDER:
                slope = metric['slopes_by_part'].get(part, np.nan)
                slopes_by_part[part].append(slope)
        
        # Box plot comparativo
        ax1 = fig1.add_subplot(111)
        box_data = [slopes_by_part[part] for part in FLUTE_PARTS_ORDER]
        bp = ax1.boxplot(box_data, labels=FLUTE_PARTS_ORDER, patch_artist=True)
        
        for patch in bp['boxes']:
            patch.set_facecolor('#4472C4')
            patch.set_alpha(0.7)
        
        ax1.set_ylabel('Pendiente (mm/mm)', fontsize=12)
        ax1.set_title('Distribución de Pendientes - Comparación por Parte', fontsize=14)
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', rotation=15)
        
        fig1.tight_layout()
        pdf.savefig(fig1, bbox_inches='tight')
        plt.close(fig1)
        
        # Página 2: Histogramas por parte (2x2 grid)
        fig2 = Figure(figsize=(11, 8.5))
        fig2.suptitle('Distribución de Pendientes por Parte', fontsize=16, weight='bold')
        
        for i, part in enumerate(FLUTE_PARTS_ORDER):
            ax = fig2.add_subplot(2, 2, i+1)
            data = [s for s in slopes_by_part[part] if not np.isnan(s)]
            
            if data:
                ax.hist(data, bins=10, color='#4472C4', alpha=0.7, edgecolor='black')
                ax.set_xlabel('Pendiente (mm/mm)')
                ax.set_ylabel('Frecuencia')
                ax.set_title(f'{part}')
                ax.grid(True, alpha=0.3)
                
                # Añadir línea de promedio
                mean_val = np.mean(data)
                ax.axvline(mean_val, color='red', linestyle='--', linewidth=2,
                          label=f'Promedio: {mean_val:.4f}')
                ax.legend()
            else:
                ax.text(0.5, 0.5, 'Sin datos', ha='center', va='center',
                       transform=ax.transAxes)
                ax.set_title(f'{part}')
        
        fig2.tight_layout()
        pdf.savefig(fig2, bbox_inches='tight')
        plt.close(fig2)
        
        # Tabla de estadísticas
        if config.get('include_tables', True):
            self._generate_slopes_table(pdf, slopes_by_part)
    
    def _generate_slopes_table(self, pdf: PdfPages, slopes_by_part: Dict) -> None:
        """Genera tabla de estadísticas de pendientes."""
        fig = Figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        ax.text(0.5, 0.95, 'Estadísticas de Pendientes por Parte',
                ha='center', va='top', fontsize=14, weight='bold',
                transform=ax.transAxes)
        
        table_data = []
        for part in FLUTE_PARTS_ORDER:
            data = [s for s in slopes_by_part[part] if not np.isnan(s)]
            if data:
                table_data.append([
                    part,
                    f"{np.mean(data):.4f}",
                    f"{np.std(data):.4f}",
                    f"{np.min(data):.4f}",
                    f"{np.max(data):.4f}",
                    f"{np.median(data):.4f}",
                    str(len(data))
                ])
        
        if table_data:
            col_labels = ['Parte', 'Promedio', 'Desv. Std', 'Mínimo', 'Máximo', 'Mediana', 'N']
            table = ax.table(cellText=table_data, colLabels=col_labels,
                           cellLoc='center', loc='center',
                           bbox=[0.1, 0.3, 0.8, 0.5])
            
            table.auto_set_font_size(False)
            table.set_fontsize(10)
            table.scale(1, 2.5)
            
            for i in range(len(col_labels)):
                table[(0, i)].set_facecolor('#4472C4')
                table[(0, i)].set_text_props(weight='bold', color='white')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _generate_holes_section(self, pdf: PdfPages, config: Dict[str, Any]) -> None:
        """Genera sección de análisis de agujeros."""
        fig = Figure(figsize=(11, 8.5))
        fig.suptitle('Análisis de Tamaños de Agujeros', fontsize=16, weight='bold')
        
        # Recopilar todos los agujeros por posición
        all_holes = {}
        for metric in self.metrics_data:
            for hole_label, diameter in metric['holes_diameters'].items():
                if hole_label not in all_holes:
                    all_holes[hole_label] = []
                all_holes[hole_label].append(diameter)
        
        # Box plot de diámetros
        ax1 = fig.add_subplot(2, 1, 1)
        hole_labels = sorted(all_holes.keys())
        box_data = [all_holes[label] for label in hole_labels]
        
        if box_data:
            bp = ax1.boxplot(box_data, labels=hole_labels, patch_artist=True)
            
            for patch in bp['boxes']:
                patch.set_facecolor('#ED7D31')
                patch.set_alpha(0.7)
            
            ax1.set_ylabel('Diámetro (mm)')
            ax1.set_title('Distribución de Diámetros por Agujero')
            ax1.grid(True, alpha=0.3)
            ax1.tick_params(axis='x', rotation=45, labelsize=7)
        
        # Histograma general de diámetros
        ax2 = fig.add_subplot(2, 1, 2)
        all_diameters = [d for holes in all_holes.values() for d in holes]
        
        if all_diameters:
            ax2.hist(all_diameters, bins=15, color='#ED7D31', alpha=0.7, edgecolor='black')
            ax2.set_xlabel('Diámetro (mm)')
            ax2.set_ylabel('Frecuencia')
            ax2.set_title('Distribución General de Diámetros de Agujeros')
            ax2.grid(True, alpha=0.3)
            
            mean_val = np.mean(all_diameters)
            ax2.axvline(mean_val, color='red', linestyle='--', linewidth=2,
                       label=f'Promedio: {mean_val:.2f} mm')
            ax2.legend()
        
        fig.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _generate_physical_lengths_section(self, pdf: PdfPages, config: Dict[str, Any]) -> None:
        """Genera sección de análisis de largos físicos."""
        fig = Figure(figsize=(11, 8.5))
        fig.suptitle('Análisis de Largos Físicos por Parte', fontsize=16, weight='bold')
        
        # Preparar datos
        lengths_by_part = {part: [] for part in FLUTE_PARTS_ORDER}
        
        for metric in self.metrics_data:
            for part in FLUTE_PARTS_ORDER:
                length = metric['part_physical_lengths'].get(part, np.nan)
                if not np.isnan(length):
                    lengths_by_part[part].append(length)
        
        # Box plot
        ax1 = fig.add_subplot(2, 1, 1)
        box_data = [lengths_by_part[part] for part in FLUTE_PARTS_ORDER]
        bp = ax1.boxplot(box_data, labels=FLUTE_PARTS_ORDER, patch_artist=True)
        
        for patch in bp['boxes']:
            patch.set_facecolor('#70AD47')
            patch.set_alpha(0.7)
        
        ax1.set_ylabel('Largo Físico (mm)')
        ax1.set_title('Distribución de Largos Físicos')
        ax1.grid(True, alpha=0.3)
        
        # Histograma comparativo
        ax2 = fig.add_subplot(2, 1, 2)
        for i, part in enumerate(FLUTE_PARTS_ORDER):
            data = lengths_by_part[part]
            if data:
                ax2.hist(data, bins=10, alpha=0.5, label=part, edgecolor='black')
        
        ax2.set_xlabel('Largo Físico (mm)')
        ax2.set_ylabel('Frecuencia')
        ax2.set_title('Distribución de Largos Físicos por Parte')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        fig.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _generate_embouchure_section(self, pdf: PdfPages, config: Dict[str, Any]) -> None:
        """Genera sección de análisis de embocadura."""
        fig = Figure(figsize=(11, 8.5))
        fig.suptitle('Análisis de Diámetro de Embocadura', fontsize=16, weight='bold')
        
        # Recopilar diámetros de embocadura
        emb_diameters = [m['embouchure_diameter'] for m in self.metrics_data 
                        if m['embouchure_diameter'] is not None]
        
        if not emb_diameters:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, 'No hay datos de embocadura disponibles',
                   ha='center', va='center', fontsize=14)
            ax.axis('off')
        else:
            # Histograma
            ax1 = fig.add_subplot(2, 2, 1)
            ax1.hist(emb_diameters, bins=15, color='#FFC000', alpha=0.7, edgecolor='black')
            ax1.set_xlabel('Diámetro (mm)')
            ax1.set_ylabel('Frecuencia')
            ax1.set_title('Distribución de Diámetros de Embocadura')
            ax1.grid(True, alpha=0.3)
            
            mean_val = np.mean(emb_diameters)
            ax1.axvline(mean_val, color='red', linestyle='--', linewidth=2,
                       label=f'Promedio: {mean_val:.2f} mm')
            ax1.legend()
            
            # Box plot
            ax2 = fig.add_subplot(2, 2, 2)
            bp = ax2.boxplot([emb_diameters], labels=['Embocadura'], patch_artist=True)
            bp['boxes'][0].set_facecolor('#FFC000')
            bp['boxes'][0].set_alpha(0.7)
            ax2.set_ylabel('Diámetro (mm)')
            ax2.set_title('Box Plot de Embocadura')
            ax2.grid(True, alpha=0.3)
            
            # Tabla de estadísticas
            ax3 = fig.add_subplot(2, 1, 2)
            ax3.axis('off')
            
            stats_data = [[
                f"{np.mean(emb_diameters):.2f}",
                f"{np.std(emb_diameters):.2f}",
                f"{np.min(emb_diameters):.2f}",
                f"{np.max(emb_diameters):.2f}",
                f"{np.median(emb_diameters):.2f}",
                str(len(emb_diameters))
            ]]
            
            col_labels = ['Promedio', 'Desv. Std', 'Mínimo', 'Máximo', 'Mediana', 'N']
            table = ax3.table(cellText=stats_data, colLabels=col_labels,
                            cellLoc='center', loc='center',
                            bbox=[0.1, 0.3, 0.8, 0.3])
            
            table.auto_set_font_size(False)
            table.set_fontsize(12)
            table.scale(1, 3)
            
            for i in range(len(col_labels)):
                table[(0, i)].set_facecolor('#FFC000')
                table[(0, i)].set_text_props(weight='bold')
        
        fig.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _generate_acoustic_length_section(self, pdf: PdfPages, config: Dict[str, Any]) -> None:
        """Genera sección de análisis de largo acústico."""
        fig = Figure(figsize=(11, 8.5))
        fig.suptitle('Análisis de Largo Acústico Total', fontsize=16, weight='bold')
        
        # Recopilar largos acústicos
        acoustic_lengths = [m['total_acoustic_length'] for m in self.metrics_data 
                           if m['total_acoustic_length'] is not None]
        
        if not acoustic_lengths:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, 'No hay datos de largo acústico disponibles',
                   ha='center', va='center', fontsize=14)
            ax.axis('off')
        else:
            # Histograma
            ax1 = fig.add_subplot(2, 2, 1)
            ax1.hist(acoustic_lengths, bins=15, color='#5B9BD5', alpha=0.7, edgecolor='black')
            ax1.set_xlabel('Largo Acústico (mm)')
            ax1.set_ylabel('Frecuencia')
            ax1.set_title('Distribución de Largo Acústico Total')
            ax1.grid(True, alpha=0.3)
            
            mean_val = np.mean(acoustic_lengths)
            ax1.axvline(mean_val, color='red', linestyle='--', linewidth=2,
                       label=f'Promedio: {mean_val:.1f} mm')
            ax1.legend()
            
            # Box plot
            ax2 = fig.add_subplot(2, 2, 2)
            bp = ax2.boxplot([acoustic_lengths], labels=['Largo Acústico'], patch_artist=True)
            bp['boxes'][0].set_facecolor('#5B9BD5')
            bp['boxes'][0].set_alpha(0.7)
            ax2.set_ylabel('Largo Acústico (mm)')
            ax2.set_title('Box Plot de Largo Acústico')
            ax2.grid(True, alpha=0.3)
            
            # Tabla de estadísticas
            ax3 = fig.add_subplot(2, 1, 2)
            ax3.axis('off')
            
            stats_data = [[
                f"{np.mean(acoustic_lengths):.1f}",
                f"{np.std(acoustic_lengths):.1f}",
                f"{np.min(acoustic_lengths):.1f}",
                f"{np.max(acoustic_lengths):.1f}",
                f"{np.median(acoustic_lengths):.1f}",
                str(len(acoustic_lengths))
            ]]
            
            col_labels = ['Promedio', 'Desv. Std', 'Mínimo', 'Máximo', 'Mediana', 'N']
            table = ax3.table(cellText=stats_data, colLabels=col_labels,
                            cellLoc='center', loc='center',
                            bbox=[0.1, 0.3, 0.8, 0.3])
            
            table.auto_set_font_size(False)
            table.set_fontsize(12)
            table.scale(1, 3)
            
            for i in range(len(col_labels)):
                table[(0, i)].set_facecolor('#5B9BD5')
                table[(0, i)].set_text_props(weight='bold')
        
        fig.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    
    def _generate_correlations_section(self, pdf: PdfPages, config: Dict[str, Any]) -> None:
        """Genera sección de análisis de correlaciones."""
        fig = Figure(figsize=(11, 8.5))
        fig.suptitle('Análisis de Correlaciones', fontsize=16, weight='bold')
        
        # Scatter plot: Largo acústico vs Diámetro de embocadura
        ax1 = fig.add_subplot(2, 2, 1)
        
        acoustic_lengths = []
        emb_diameters = []
        labels = []
        
        for m in self.metrics_data:
            if m['total_acoustic_length'] is not None and m['embouchure_diameter'] is not None:
                acoustic_lengths.append(m['total_acoustic_length'])
                emb_diameters.append(m['embouchure_diameter'])
                labels.append(m['flute_model'])
        
        if acoustic_lengths and emb_diameters:
            ax1.scatter(acoustic_lengths, emb_diameters, alpha=0.6, s=50)
            ax1.set_xlabel('Largo Acústico (mm)')
            ax1.set_ylabel('Diámetro Embocadura (mm)')
            ax1.set_title('Largo Acústico vs Diámetro Embocadura')
            ax1.grid(True, alpha=0.3)
            
            # Línea de tendencia
            if len(acoustic_lengths) > 1:
                z = np.polyfit(acoustic_lengths, emb_diameters, 1)
                p = np.poly1d(z)
                ax1.plot(acoustic_lengths, p(acoustic_lengths), "r--", alpha=0.8,
                        label=f'y = {z[0]:.4f}x + {z[1]:.2f}')
                ax1.legend()
        
        # Más scatter plots pueden agregarse aquí
        
        fig.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

