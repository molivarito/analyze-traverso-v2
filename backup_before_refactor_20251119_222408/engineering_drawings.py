"""
Generación de planos de ingeniería en PDF para flautas.

Este módulo genera planos técnicos vectoriales con:
- Geometría interna por parte
- Geometría completa ensamblada
- Agujeros y dimensiones
- Tablas de dimensiones
- Capas detalladas para zoom y análisis
"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
import numpy as np

try:
    from reportlab.lib.pagesizes import A4, letter, A3
    from reportlab.lib.units import mm, cm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    # Fallback a matplotlib si ReportLab no está disponible
    import matplotlib
    matplotlib.use('PDF')
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.pyplot as plt
    import numpy as np

from constants import FLUTE_PARTS_ORDER, M_TO_MM_FACTOR

logger = logging.getLogger(__name__)


class EngineeringDrawingGenerator:
    """
    Generador de planos de ingeniería en PDF para flautas.
    """
    
    def __init__(
        self,
        flute_data,
        output_path: str,
        page_size: str = 'A4',
        scale: float = 1.0,
        include_tables: bool = True,
        include_external: bool = False
    ):
        """
        Inicializa el generador de planos.
        
        Args:
            flute_data: Instancia de FluteData o FluteDataDB.
            output_path: Ruta al archivo PDF de salida.
            page_size: Tamaño de página ('A4', 'A3', 'letter').
            scale: Escala del dibujo (1.0 = escala real, 0.5 = mitad, etc.).
            include_tables: Si incluir tablas de dimensiones.
            include_external: Si incluir geometría externa además de interna.
        """
        self.flute_data = flute_data
        self.output_path = Path(output_path)
        self.page_size = page_size
        self.scale = scale
        self.include_tables = include_tables
        self.include_external = include_external
        
        if not REPORTLAB_AVAILABLE:
            logger.warning("ReportLab no está disponible, usando matplotlib como fallback")
    
    def generate_complete_drawing(self) -> None:
        """
        Genera un plano completo con todas las partes y tablas.
        """
        if REPORTLAB_AVAILABLE:
            self._generate_with_reportlab()
        else:
            self._generate_with_matplotlib()
    
    def _generate_with_reportlab(self) -> None:
        """Genera PDF usando ReportLab (mejor calidad vectorial)."""
        # Determinar tamaño de página
        if self.page_size == 'A3':
            pagesize = A3
        elif self.page_size == 'letter':
            pagesize = letter
        else:
            pagesize = A4
        
        doc = SimpleDocTemplate(
            str(self.output_path),
            pagesize=pagesize,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=20*mm,
            bottomMargin=20*mm
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#000000'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        story.append(Paragraph(f"Plano de Ingeniería: {self.flute_data.flute_model}", title_style))
        story.append(Spacer(1, 12))
        
        # Información general
        info_text = f"""
        <b>Modelo:</b> {self.flute_data.flute_model}<br/>
        <b>Escala:</b> 1:{1/self.scale:.2f}<br/>
        <b>Fecha:</b> {self._get_current_date()}
        """
        story.append(Paragraph(info_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Planos por parte
        for part_name in FLUTE_PARTS_ORDER:
            story.append(PageBreak())
            story.extend(self._generate_part_drawing_reportlab(part_name))
        
        # Plano completo ensamblado
        story.append(PageBreak())
        story.extend(self._generate_assembly_drawing_reportlab())
        
        # Tablas de dimensiones
        if self.include_tables:
            story.append(PageBreak())
            story.extend(self._generate_dimension_tables_reportlab())
        
        doc.build(story)
        logger.info(f"Plano de ingeniería generado: {self.output_path}")
    
    def _generate_part_drawing_reportlab(self, part_name: str) -> List:
        """Genera dibujo de una parte usando ReportLab."""
        from reportlab.graphics.shapes import Drawing, Line, Circle, Rect
        from reportlab.graphics import renderPDF
        
        story = []
        styles = getSampleStyleSheet()
        
        # Título de la parte
        part_title = part_name.capitalize()
        story.append(Paragraph(f"<b>{part_title}</b>", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        # Aquí se generaría el dibujo vectorial usando ReportLab Drawing
        # Por simplicidad, generamos una tabla con las dimensiones
        part_data = self.flute_data.data.get(part_name, {})
        measurements = part_data.get("measurements", [])
        
        if measurements:
            # Crear tabla de dimensiones
            table_data = [['Posición (mm)', 'Diámetro Interno (mm)']]
            for m in measurements:
                table_data.append([
                    f"{m.get('position', 0):.2f}",
                    f"{m.get('diameter', 0):.2f}"
                ])
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(table)
        
        return story
    
    def _generate_assembly_drawing_reportlab(self) -> List:
        """Genera dibujo del ensamblaje completo usando ReportLab."""
        story = []
        styles = getSampleStyleSheet()
        
        story.append(Paragraph("<b>Vista Completa Ensamblada</b>", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        # Aquí se generaría el dibujo del ensamblaje
        # Por ahora, mostramos información
        combined = self.flute_data.combined_measurements
        if combined:
            total_length = max(m.get('position', 0) for m in combined) - min(m.get('position', 0) for m in combined)
            story.append(Paragraph(f"Longitud total acústica: {total_length:.2f} mm", styles['Normal']))
        
        return story
    
    def _generate_dimension_tables_reportlab(self) -> List:
        """Genera tablas detalladas de dimensiones para tornero usando ReportLab."""
        story = []
        styles = getSampleStyleSheet()
        
        story.append(Paragraph("<b>Tablas de Dimensiones Detalladas</b>", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        for part_name in FLUTE_PARTS_ORDER:
            part_data = self.flute_data.data.get(part_name, {})
            measurements = part_data.get("measurements", [])
            hole_positions = part_data.get("Holes position", [])
            hole_diameters = part_data.get("Holes diameter", [])
            
            if measurements:
                story.append(Paragraph(f"<b>{part_name.capitalize()}</b>", styles['Heading3']))
                story.append(Spacer(1, 6))
                
                # Tabla de diámetros internos
                table_data = [['Dist. desde extremo (mm)', 'Diámetro Interno (mm)', 'Radio (mm)']]
                if self.include_external and hasattr(self.flute_data, 'external_geometry'):
                    table_data[0].append('Diámetro Externo (mm)')
                    table_data[0].append('Espesor Pared (mm)')
                
                min_pos = min(m.get('position', 0) for m in measurements) if measurements else 0
                
                for m in measurements:
                    pos = m.get('position', 0)
                    diam = m.get('diameter', 0)
                    dist_from_top = pos - min_pos
                    radius = diam / 2.0
                    
                    row = [
                        f"{dist_from_top:.2f}",
                        f"{diam:.3f}",
                        f"{radius:.3f}"
                    ]
                    
                    if self.include_external and hasattr(self.flute_data, 'external_geometry'):
                        ext_geom = self.flute_data.external_geometry.get(part_name, [])
                        # Buscar diámetro externo más cercano
                        ext_diam = None
                        for ext_m in ext_geom:
                            if abs(ext_m.get('position', 0) - pos) < 0.1:
                                ext_diam = ext_m.get('external_diameter', 0)
                                break
                        
                        if ext_diam:
                            wall_thickness = (ext_diam - diam) / 2.0
                            row.append(f"{ext_diam:.3f}")
                            row.append(f"{wall_thickness:.3f}")
                        else:
                            row.append("-")
                            row.append("-")
                    
                    table_data.append(row)
                
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
                ]))
                story.append(table)
                story.append(Spacer(1, 10))
                
                # Tabla de agujeros
                if hole_positions and hole_diameters:
                    story.append(Paragraph(f"<b>Agujeros de {part_name.capitalize()}</b>", styles['Heading4']))
                    story.append(Spacer(1, 4))
                    
                    holes_table_data = [['N°', 'Dist. desde extremo (mm)', 'Diámetro (mm)', 'Radio (mm)']]
                    
                    for idx, (pos, diam) in enumerate(zip(hole_positions, hole_diameters)):
                        dist_from_top = pos - min_pos
                        radius = diam / 2.0
                        holes_table_data.append([
                            str(idx + 1),
                            f"{dist_from_top:.2f}",
                            f"{diam:.3f}",
                            f"{radius:.3f}"
                        ])
                    
                    holes_table = Table(holes_table_data)
                    holes_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 9),
                        ('FONTSIZE', (0, 1), (-1, -1), 7),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.lightblue),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.black)
                    ]))
                    story.append(holes_table)
                    story.append(Spacer(1, 15))
        
        return story
    
    def _generate_with_matplotlib(self) -> None:
        """Genera PDF usando matplotlib como fallback con todas las páginas."""
        with PdfPages(str(self.output_path)) as pdf:
            # Página de título
            fig, ax = plt.subplots(figsize=(8.5, 11))
            ax.axis('off')
            title_text = f"Plano de Ingeniería\n{self.flute_data.flute_model}\n\n"
            title_text += f"Escala: 1:{1/self.scale:.2f}\n"
            title_text += f"Fecha: {self._get_current_date()}"
            ax.text(0.5, 0.5, title_text, ha='center', va='center', fontsize=18, fontweight='bold')
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            
            # Planos por parte (una página por parte)
            for part_name in FLUTE_PARTS_ORDER:
                fig, ax = plt.subplots(figsize=(11, 8.5))
                self._draw_part_matplotlib(ax, part_name)
                pdf.savefig(fig, bbox_inches='tight')
                plt.close(fig)
            
            # Plano completo ensamblado
            fig, ax = plt.subplots(figsize=(11, 8.5))
            self._draw_assembly_matplotlib(ax)
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
            
            # Tablas de dimensiones detalladas
            if self.include_tables:
                for part_name in FLUTE_PARTS_ORDER:
                    fig = self._draw_dimension_table_matplotlib(part_name)
                    if fig:
                        pdf.savefig(fig, bbox_inches='tight')
                        plt.close(fig)
        
        logger.info(f"Plano de ingeniería generado (matplotlib): {self.output_path}")
    
    def _draw_dimension_table_matplotlib(self, part_name: str):
        """Dibuja tabla de dimensiones usando matplotlib."""
        part_data = self.flute_data.data.get(part_name, {})
        measurements = part_data.get("measurements", [])
        hole_positions = part_data.get("Holes position", [])
        hole_diameters = part_data.get("Holes diameter", [])
        
        if not measurements:
            return None
        
        fig, ax = plt.subplots(figsize=(11, 8.5))
        ax.axis('off')
        
        # Título sobrio y profesional
        ax.text(0.5, 0.96, f"TABLAS DE DIMENSIONES - {part_name.upper()}", 
               ha='center', va='top', fontsize=13, fontweight='bold', 
               color='#333333', transform=ax.transAxes)
        
        # Separador sutil
        ax.plot([0.05, 0.95], [0.94, 0.94], 'k-', linewidth=0.8, transform=ax.transAxes, clip_on=False)
        
        # Tabla de diámetros internos con título sobrio y bordes
        y_pos = 0.90
        ax.text(0.5, y_pos, "DIÁMETROS INTERNOS", fontsize=10, fontweight='bold', 
               color='#333333', ha='center', transform=ax.transAxes)
        y_pos -= 0.04
        
        # Encabezado con bordes
        headers = ['Dist. desde extremo (mm)', 'Diámetro (mm)', 'Radio (mm)']
        if self.include_external and hasattr(self.flute_data, 'external_geometry'):
            headers.extend(['Diámetro Ext. (mm)', 'Espesor (mm)'])
        
        col_width = 0.8 / len(headers)
        
        # Dibujar rectángulo de fondo para encabezados
        header_box = plt.Rectangle((0.1, y_pos - 0.025), 0.8, 0.025, 
                                   transform=ax.transAxes, facecolor='#E8E8E8', 
                                   edgecolor='black', linewidth=0.8, clip_on=False)
        ax.add_patch(header_box)
        
        # Líneas verticales entre columnas
        for idx in range(1, len(headers)):
            x_line = 0.1 + idx * col_width
            ax.plot([x_line, x_line], [y_pos - 0.025, y_pos], 'k-', linewidth=0.8, 
                   transform=ax.transAxes, clip_on=False)
        
        for idx, header in enumerate(headers):
            x_pos = 0.1 + (idx + 0.5) * col_width
            ax.text(x_pos, y_pos - 0.0125, header, ha='center', va='center', 
                   fontsize=7, fontweight='bold', color='#333333', transform=ax.transAxes)
        
        y_pos -= 0.025  # Espacio después del encabezado
        min_pos = min(m.get('position', 0) for m in measurements) if measurements else 0
        
        # Calcular espacio disponible para cada tabla (dividir la página)
        # Si hay agujeros, dividir en dos secciones; si no, usar todo el espacio
        if hole_positions and hole_diameters:
            # Reservar espacio: diámetros de 0.87 a 0.55, agujeros de 0.50 a 0.05
            max_diameter_rows = min(len(measurements), int((0.87 - 0.56) / 0.022))
        else:
            max_diameter_rows = min(len(measurements), int((0.87 - 0.05) / 0.022))
        
        # Datos de diámetros con bordes profesionales
        for idx, m in enumerate(measurements[:max_diameter_rows]):
            pos = m.get('position', 0)
            diam = m.get('diameter', 0)
            dist_from_top = pos - min_pos
            radius = diam / 2.0
            
            row_data = [f"{dist_from_top:.2f}", f"{diam:.3f}", f"{radius:.3f}"]
            
            if self.include_external and hasattr(self.flute_data, 'external_geometry'):
                ext_geom = self.flute_data.external_geometry.get(part_name, [])
                ext_diam = None
                for ext_m in ext_geom:
                    if abs(ext_m.get('position', 0) - pos) < 0.1:
                        ext_diam = ext_m.get('external_diameter', 0)
                        break
                
                if ext_diam:
                    wall_thickness = (ext_diam - diam) / 2.0
                    row_data.extend([f"{ext_diam:.3f}", f"{wall_thickness:.3f}"])
                else:
                    row_data.extend(["-", "-"])
            
            # Fondo alternado
            if idx % 2 == 1:
                row_box = plt.Rectangle((0.1, y_pos - 0.02), 0.8, 0.02, 
                                       transform=ax.transAxes, facecolor='#F5F5F5', 
                                       edgecolor='none', clip_on=False)
                ax.add_patch(row_box)
            
            # Bordes de la fila
            row_border = plt.Rectangle((0.1, y_pos - 0.02), 0.8, 0.02, 
                                      transform=ax.transAxes, facecolor='none', 
                                      edgecolor='#CCCCCC', linewidth=0.5, clip_on=False)
            ax.add_patch(row_border)
            
            # Líneas verticales entre columnas
            for col_idx in range(1, len(headers)):
                x_line = 0.1 + col_idx * col_width
                ax.plot([x_line, x_line], [y_pos - 0.02, y_pos], '#CCCCCC', linewidth=0.5, 
                       transform=ax.transAxes, clip_on=False)
            
            # Datos de la fila
            for col_idx, data in enumerate(row_data):
                x_pos = 0.1 + (col_idx + 0.5) * col_width
                ax.text(x_pos, y_pos - 0.01, data, ha='center', va='center', 
                       fontsize=7, transform=ax.transAxes)
            
            y_pos -= 0.022
        
        # Calcular posición de inicio para tabla de agujeros (con separación clara)
        holes_table_y_start = 0.50  # Posición fija en la mitad inferior de la página
        
        # Tabla de agujeros con título sobrio y bordes
        if hole_positions and hole_diameters:
            y_pos = holes_table_y_start
            ax.text(0.5, y_pos, "AGUJEROS", fontsize=10, fontweight='bold', 
                   color='#333333', ha='center', transform=ax.transAxes)
            y_pos -= 0.04
            
            hole_headers = ['N°', 'Dist. desde extremo (mm)', 'Diámetro (mm)', 'Radio (mm)']
            col_width_holes = 0.8 / len(hole_headers)
            
            # Dibujar rectángulo de fondo para encabezados
            header_box_holes = plt.Rectangle((0.1, y_pos - 0.025), 0.8, 0.025, 
                                            transform=ax.transAxes, facecolor='#E8E8E8', 
                                            edgecolor='black', linewidth=0.8, clip_on=False)
            ax.add_patch(header_box_holes)
            
            # Líneas verticales entre columnas
            for idx in range(1, len(hole_headers)):
                x_line = 0.1 + idx * col_width_holes
                ax.plot([x_line, x_line], [y_pos - 0.025, y_pos], 'k-', linewidth=0.8, 
                       transform=ax.transAxes, clip_on=False)
            
            for idx, header in enumerate(hole_headers):
                x_pos = 0.1 + (idx + 0.5) * col_width_holes
                ax.text(x_pos, y_pos - 0.0125, header, ha='center', va='center', 
                       fontsize=7, fontweight='bold', color='#333333', transform=ax.transAxes)
            
            y_pos -= 0.025
            
            for idx, (pos, diam) in enumerate(zip(hole_positions, hole_diameters)):
                dist_from_top = pos - min_pos
                rad = diam / 2.0
                
                hole_data_row = [f"{idx+1}", f"{dist_from_top:.2f}", f"{diam:.2f}", f"{rad:.2f}"]
                
                # Fondo alternado para filas
                if idx % 2 == 1:
                    row_box = plt.Rectangle((0.1, y_pos - 0.02), 0.8, 0.02, 
                                           transform=ax.transAxes, facecolor='#F5F5F5', 
                                           edgecolor='none', clip_on=False)
                    ax.add_patch(row_box)
                
                # Bordes de la fila
                row_border = plt.Rectangle((0.1, y_pos - 0.02), 0.8, 0.02, 
                                          transform=ax.transAxes, facecolor='none', 
                                          edgecolor='#CCCCCC', linewidth=0.5, clip_on=False)
                ax.add_patch(row_border)
                
                # Líneas verticales entre columnas
                for col_idx in range(1, len(hole_headers)):
                    x_line = 0.1 + col_idx * col_width_holes
                    ax.plot([x_line, x_line], [y_pos - 0.02, y_pos], '#CCCCCC', linewidth=0.5, 
                           transform=ax.transAxes, clip_on=False)
                
                for col_idx, val in enumerate(hole_data_row):
                    x_pos = 0.1 + (col_idx + 0.5) * col_width_holes
                    ax.text(x_pos, y_pos - 0.01, val, ha='center', va='center', fontsize=6,
                           transform=ax.transAxes)
                
                y_pos -= 0.02
                if y_pos < 0.05:
                    break
        
        return fig
    
    def _draw_part_matplotlib(self, ax, part_name: str) -> None:
        """Dibuja una parte usando matplotlib con estilo profesional de plano de ingeniería."""
        part_data = self.flute_data.data.get(part_name, {})
        measurements = part_data.get("measurements", [])
        
        if not measurements:
            ax.text(0.5, 0.5, f"No hay datos para {part_name}",
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_title(f"{part_name.capitalize()}")
            return
        
        # Configuración de estilo profesional
        ax.set_facecolor('#FAFAFA')
        
        positions = [m.get('position', 0) for m in measurements]
        diameters = [m.get('diameter', 0) for m in measurements]
        radii = [d / 2.0 for d in diameters]
        
        # Normalizar posiciones
        min_pos = min(positions) if positions else 0
        positions_normalized = [p - min_pos for p in positions]
        
        # Configurar grilla profesional
        x_max = max(positions_normalized) if positions_normalized else 100
        max_radius = max(radii) if radii else 10.0
        y_lim = max_radius * 1.5
        
        # Grilla mayor cada 10mm
        major_grid_x = np.arange(0, x_max + 20, 10)
        major_grid_y = np.arange(-y_lim, y_lim + 10, 5)
        ax.set_xticks(major_grid_x, minor=False)
        ax.set_yticks(major_grid_y, minor=False)
        ax.grid(True, which='major', linestyle='-', linewidth=0.8, alpha=0.4, color='#666666')
        
        # Grilla menor cada 1mm
        minor_grid_x = np.arange(0, x_max + 20, 1)
        minor_grid_y = np.arange(-y_lim, y_lim + 1, 1)
        ax.set_xticks(minor_grid_x, minor=True)
        ax.set_yticks(minor_grid_y, minor=True)
        ax.grid(True, which='minor', linestyle=':', linewidth=0.3, alpha=0.25, color='#AAAAAA')
        
        # Perfil interno con sombreado
        ax.plot(positions_normalized, radii, 'k-', linewidth=1.2, solid_capstyle='round', zorder=10)
        ax.plot(positions_normalized, [-r for r in radii], 'k-', linewidth=1.2, solid_capstyle='round', zorder=10)
        ax.fill_between(positions_normalized, radii, [-r for r in radii], alpha=0.1, color='blue', zorder=2)
        
        # Perfil externo
        if self.include_external and hasattr(self.flute_data, 'external_geometry'):
            ext_geom = self.flute_data.external_geometry.get(part_name, [])
            if ext_geom:
                ext_positions = [m.get('position', 0) for m in ext_geom]
                ext_diameters = [m.get('external_diameter', 0) for m in ext_geom]
                ext_radii = [d / 2.0 for d in ext_diameters]
                ext_positions_normalized = [p - min_pos for p in ext_positions]
                ax.plot(ext_positions_normalized, ext_radii, 'k--', linewidth=0.8, dashes=(4, 2), zorder=9)
                ax.plot(ext_positions_normalized, [-r for r in ext_radii], 'k--', linewidth=0.8, dashes=(4, 2), zorder=9)
        
        # Dibujar agujeros con estilo técnico
        hole_positions = part_data.get("Holes position", [])
        hole_diameters = part_data.get("Holes diameter", [])
        
        for idx, (pos, diam) in enumerate(zip(hole_positions, hole_diameters)):
            pos_norm = pos - min_pos
            radius_hole = diam / 2.0
            
            # Círculo del agujero en el centro
            circle = plt.Circle((pos_norm, 0), radius_hole, fill=False, edgecolor='red', 
                               linewidth=1.0, linestyle='-', zorder=15)
            ax.add_patch(circle)
            
            # Líneas de centro del agujero
            ax.plot([pos_norm, pos_norm], [-max_radius * 1.3, max_radius * 1.3], 
                   'r:', linewidth=0.7, alpha=0.3, zorder=5)
            
            # Etiqueta del agujero
            ax.text(pos_norm, max_radius * 1.25, f'H{idx+1}', ha='center', va='bottom',
                   fontsize=8, fontweight='bold', color='darkred',
                   bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='red', linewidth=0.8))
        
        # Línea de referencia en 0
        ax.axhline(0, color='k', linewidth=0.8, linestyle='-', alpha=0.4, zorder=8)
        
        # Cotas principales
        # Longitud total
        y_cota = -max_radius * 1.1
        ax.annotate('', xy=(max(positions_normalized), y_cota), xytext=(0, y_cota),
                   arrowprops=dict(arrowstyle='<->', lw=1.2, color='black'))
        ax.text(max(positions_normalized) / 2, y_cota - 2, f'L = {max(positions_normalized):.1f} mm',
               ha='center', va='top', fontsize=10, fontweight='bold', color='black',
               bbox=dict(boxstyle='square,pad=0.3', facecolor='white', edgecolor='black', linewidth=0.8))
        
        # Título y etiquetas profesionales
        ax.set_title(f"{part_name.upper()} - {self.flute_data.flute_model}", 
                    fontsize=12, fontweight='bold', pad=12)
        ax.set_xlabel('Distancia desde extremo superior [mm]', fontsize=10, fontweight='bold')
        ax.set_ylabel('Radio [mm]', fontsize=10, fontweight='bold')
        
        # Ajustar límites
        ax.set_xlim(-5, x_max + 10)
        ax.set_ylim(-y_lim, y_lim)
        ax.set_aspect('equal', adjustable='box')
        
        # Recuadro del plano
        ax.spines['top'].set_linewidth(1.0)
        ax.spines['right'].set_linewidth(1.0)
        ax.spines['bottom'].set_linewidth(1.0)
        ax.spines['left'].set_linewidth(1.0)
    
    def _draw_assembly_matplotlib(self, ax) -> None:
        """Dibuja el ensamblaje completo usando matplotlib con cotas."""
        combined = self.flute_data.combined_measurements
        if not combined:
            ax.text(0.5, 0.5, "No hay datos de ensamblaje",
                   ha='center', va='center', transform=ax.transAxes)
            ax.set_title("Vista Completa Ensamblada")
            return
        
        positions = [m.get('position', 0) for m in combined]
        diameters = [m.get('diameter', 0) for m in combined]
        radii = [d / 2.0 for d in diameters]
        
        # Normalizar posiciones
        min_pos = min(positions) if positions else 0
        positions_normalized = [p - min_pos for p in positions]
        
        # Grilla milimétrica profesional
        x_min, x_max = min(positions_normalized), max(positions_normalized)
        max_radius = max(radii) if radii else 10.0
        y_min, y_max = -max_radius * 1.5, max_radius * 1.5
        y_lim = max_radius * 1.5
        
        # Grilla mayor (cada 10mm para X, 5mm para Y)
        major_grid_x = np.arange(0, x_max + 20, 10)
        major_grid_y = np.arange(-y_lim, y_lim + 5, 5)
        ax.set_xticks(major_grid_x, minor=False)
        ax.set_yticks(major_grid_y, minor=False)
        ax.grid(True, which='major', linestyle='-', linewidth=0.6, alpha=0.4, color='#666666')
        
        # Grilla menor (cada 1mm)
        minor_grid_x = np.arange(0, x_max + 20, 1)
        minor_grid_y = np.arange(-y_lim, y_lim + 1, 1)
        ax.set_xticks(minor_grid_x, minor=True)
        ax.set_yticks(minor_grid_y, minor=True)
        ax.grid(True, which='minor', linestyle=':', linewidth=0.3, alpha=0.25, color='#AAAAAA')
        
        # Rotar etiquetas del eje X para evitar traslape
        ax.tick_params(axis='x', labelsize=9, rotation=45)
        ax.tick_params(axis='y', labelsize=9)
        
        # Dibujar perfil con líneas profesionales
        ax.plot(positions_normalized, radii, 'k-', linewidth=1.2, solid_capstyle='round', zorder=10)
        ax.plot(positions_normalized, [-r for r in radii], 'k-', linewidth=1.2, solid_capstyle='round', zorder=10)
        ax.fill_between(positions_normalized, radii, [-r for r in radii], alpha=0.1, color='blue', zorder=2)
        
        # Dibujar todos los agujeros de todas las partes
        for part_name in FLUTE_PARTS_ORDER:
            part_data = self.flute_data.data.get(part_name, {})
            hole_positions = part_data.get("Holes position", [])
            hole_diameters = part_data.get("Holes diameter", [])
            
            # Calcular posición absoluta de la parte
            part_start = self._get_part_absolute_start(part_name)
            
            for idx, (pos, diam) in enumerate(zip(hole_positions, hole_diameters)):
                abs_pos = part_start + pos - min_pos
                radius_hole = diam / 2.0
                
                # Círculo del agujero
                circle = plt.Circle((abs_pos, 0), radius_hole, fill=False, edgecolor='red',
                                   linewidth=1.0, linestyle='-', zorder=15)
                ax.add_patch(circle)
                
                # Línea de centro
                ax.plot([abs_pos, abs_pos], [-y_lim, y_lim], 'r:', linewidth=0.7, alpha=0.3, zorder=5)
        
        # Longitud total con cota profesional
        total_length = max(positions_normalized)
        y_cota = -max_radius * 1.15
        ax.annotate('', xy=(max(positions_normalized), y_cota), xytext=(0, y_cota),
                   arrowprops=dict(arrowstyle='<->', lw=1.2, color='black'))
        ax.text(max(positions_normalized) / 2, y_cota - 2, f'L = {total_length:.1f} mm',
               ha='center', va='top', fontsize=10, fontweight='bold', color='black',
               bbox=dict(boxstyle='square,pad=0.3', facecolor='white', edgecolor='black', linewidth=0.8))
        
        # Línea de referencia en 0
        ax.axhline(0, color='k', linewidth=0.8, linestyle='-', alpha=0.4, zorder=8)
        
        ax.set_xlabel('Distancia desde extremo superior [mm]', fontsize=10, fontweight='bold')
        ax.set_ylabel('Radio [mm]', fontsize=10, fontweight='bold')
        ax.set_title(f"ENSAMBLAJE COMPLETO - {self.flute_data.flute_model.upper()}", 
                    fontsize=12, fontweight='bold', pad=12)
        
        # Ajustar límites
        ax.set_xlim(-5, x_max + 10)
        ax.set_ylim(-y_lim, y_lim)
        ax.set_aspect('equal', adjustable='box')
        
        # Recuadro del plano
        ax.spines['top'].set_linewidth(1.0)
        ax.spines['right'].set_linewidth(1.0)
        ax.spines['bottom'].set_linewidth(1.0)
        ax.spines['left'].set_linewidth(1.0)
    
    def _get_part_absolute_start(self, part_name: str) -> float:
        """
        Calcula la posición absoluta de inicio de una parte.
        Usa la misma lógica que combine_measurements para asegurar consistencia.
        """
        from constants import FLUTE_PARTS_ORDER
        
        # Esta lógica debe coincidir exactamente con combine_measurements
        current_physical_connection_point_abs = 0.0
        
        for part in FLUTE_PARTS_ORDER:
            if part == part_name:
                # Calcular el inicio físico de esta parte
                is_headjoint = (part == FLUTE_PARTS_ORDER[0])
                part_data = self.flute_data.data.get(part, {})
                part_mortise_length = part_data.get("Mortise length", 0.0)
                
                if is_headjoint:
                    return 0.0
                elif part == FLUTE_PARTS_ORDER[1]:  # Left
                    return current_physical_connection_point_abs
                else:  # Right, Foot
                    return current_physical_connection_point_abs - part_mortise_length
            
            # Actualizar current_physical_connection_point_abs para la siguiente parte
            part_data = self.flute_data.data.get(part, {})
            part_total_length = part_data.get("Total length", 0.0)
            part_mortise_length = part_data.get("Mortise length", 0.0)
            
            is_headjoint = (part == FLUTE_PARTS_ORDER[0])
            if is_headjoint:
                current_physical_connection_point_abs = 0.0 + (part_total_length - part_mortise_length)
            elif part == FLUTE_PARTS_ORDER[1]:  # Left
                # Necesitamos el inicio físico de Left para calcular su final
                left_physical_start = current_physical_connection_point_abs
                current_physical_connection_point_abs = left_physical_start + part_total_length
            else:  # Right, Foot
                # Necesitamos el inicio físico de esta parte para calcular su final
                part_physical_start = current_physical_connection_point_abs - part_mortise_length
                current_physical_connection_point_abs = part_physical_start + part_total_length
        
        # Si no se encontró la parte, retornar 0
        return 0.0
    
    def _get_current_date(self) -> str:
        """Retorna la fecha actual formateada."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def generate_part_drawing(self, part_name: str, output_path: Optional[str] = None) -> None:
        """
        Genera un plano para una parte específica.
        
        Args:
            part_name: Nombre de la parte.
            output_path: Ruta de salida (opcional, usa self.output_path si no se proporciona).
        """
        if output_path:
            self.output_path = Path(output_path)
        
        if REPORTLAB_AVAILABLE:
            doc = SimpleDocTemplate(str(self.output_path), pagesize=A4)
            story = self._generate_part_drawing_reportlab(part_name)
            doc.build(story)
        else:
            with PdfPages(str(self.output_path)) as pdf:
                fig, ax = plt.subplots(figsize=(11, 8.5))
                self._draw_part_matplotlib(ax, part_name)
                pdf.savefig(fig, bbox_inches='tight')
                plt.close(fig)
        
        logger.info(f"Plano de {part_name} generado: {self.output_path}")
    
    def generate_impedance_plot(self, note: str, output_path: Optional[str] = None) -> None:
        """
        Genera un gráfico de impedancia para una nota específica en PDF.
        
        Args:
            note: Nombre de la nota.
            output_path: Ruta de salida.
        """
        if output_path:
            self.output_path = Path(output_path)
        
        if note not in self.flute_data.acoustic_analysis:
            logger.warning(f"No hay análisis acústico para nota {note}")
            return
        
        analysis_obj = self.flute_data.acoustic_analysis[note]
        
        if REPORTLAB_AVAILABLE:
            # Para ReportLab, generar una página con el gráfico
            # (se puede usar matplotlib para generar la imagen y luego insertarla)
            self._generate_impedance_plot_matplotlib(note)
        else:
            self._generate_impedance_plot_matplotlib(note)
    
    def _generate_impedance_plot_matplotlib(self, note: str) -> None:
        """Genera gráfico de impedancia usando matplotlib."""
        analysis_obj = self.flute_data.acoustic_analysis[note]
        
        if not hasattr(analysis_obj, 'frequencies') or not hasattr(analysis_obj, 'impedance'):
            logger.warning(f"Objeto de análisis no tiene atributos necesarios para nota {note}")
            return
        
        frequencies = analysis_obj.frequencies
        impedance = analysis_obj.impedance
        
        with PdfPages(str(self.output_path)) as pdf:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8.5))
            
            # Magnitud de impedancia
            ax1.plot(frequencies, np.abs(impedance), 'b-', linewidth=1.5)
            ax1.set_xlabel('Frecuencia (Hz)')
            ax1.set_ylabel('|Impedancia| (Pa·s/m³)')
            ax1.set_title(f"Impedancia - Nota {note} - {self.flute_data.flute_model}")
            ax1.grid(True, linestyle=':', alpha=0.7)
            
            # Fase de impedancia
            ax2.plot(frequencies, np.angle(impedance), 'r-', linewidth=1.5)
            ax2.set_xlabel('Frecuencia (Hz)')
            ax2.set_ylabel('Fase (rad)')
            ax2.set_title(f"Fase de Impedancia - Nota {note}")
            ax2.grid(True, linestyle=':', alpha=0.7)
            
            plt.tight_layout()
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
        
        logger.info(f"Gráfico de impedancia para nota {note} generado: {self.output_path}")

