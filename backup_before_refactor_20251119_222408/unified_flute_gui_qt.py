"""
GUI Unificada para Análisis de Flautas - Versión PyQt5
Integra visualización, análisis, planos de ingeniería y modelado 3D profesional.
"""

import sys
import os
import json
import logging
import tempfile
import signal
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import difflib
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QSpinBox, QDoubleSpinBox, QGroupBox, QFormLayout,
    QComboBox, QHeaderView, QSplitter, QTextEdit, QDialog,
    QDialogButtonBox, QCheckBox, QScrollArea, QLineEdit, QProgressDialog, QGridLayout
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

try:
    from pyvistaqt import QtInteractor
    import pyvista as pv
    PYVISTA_AVAILABLE = True
except ImportError:
    PYVISTA_AVAILABLE = False
    print("Warning: PyVista no disponible. Instalalo con: pip install pyvista pyvistaqt")

try:
    import cadquery as cq
    CADQUERY_AVAILABLE = True
except ImportError:
    CADQUERY_AVAILABLE = False
    print("Warning: CadQuery no disponible. Instalalo con: pip install cadquery")

# Imports del proyecto
from flute_data_db import FluteDataDB
from flute_operations import FluteOperations
from flute_db_manager import FluteDBManager
from analysis_module import FluteAnalyzer
from engineering_drawings import EngineeringDrawingGenerator
from constants import FLUTE_PARTS_ORDER, BASE_COLORS, LINESTYLES
from populate_database import (
    find_flute_directories, check_flute_files, analyze_flute_status,
    populate_flute, generate_detailed_report
)
from cleanup_database import cleanup_pressure_flow_data, get_database_size
from db_schema import DEFAULT_DB_PATH
from gcode_generator import (
    load_flute_data_from_dict,
    generate_gcode,
    parse_gcode,
    plot_intended_paths,
    plot_parsed_gcode,
    DEFAULT_PARAMS
)
from flute_geometry_editor_qt import FluteGeometryEditor

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s [%(name)s:%(funcName)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_JSON_DIR = SCRIPT_DIR.parent / "data_json"


# ==================== Utilidades de Corrección de Archivos ====================

class FileCorrector:
    """Corrige nombres de archivos JSON mal escritos."""
    
    CORRECT_NAMES = [
        "headjoint.json", "headjoint_external.json",
        "left.json", "left_external.json",
        "right.json", "right_external.json",
        "foot.json", "foot_external.json"
    ]
    
    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.corrections_log = []
    
    def find_closest_match(self, typo: str) -> Optional[str]:
        """Encuentra la coincidencia más cercana."""
        matches = difflib.get_close_matches(typo, self.CORRECT_NAMES, n=1, cutoff=0.8)
        return matches[0] if matches else None
    
    def scan_for_errors(self) -> List[Dict[str, str]]:
        """Escanea y retorna lista de correcciones sugeridas."""
        suggestions = []
        
        if not self.base_path.exists() or not self.base_path.is_dir():
            return suggestions
        
        for flute_dir in self.base_path.iterdir():
            if not flute_dir.is_dir():
                continue
            
            for file_path in flute_dir.glob("*.json"):
                filename = file_path.name
                if filename not in self.CORRECT_NAMES:
                    correct_name = self.find_closest_match(filename)
                    if correct_name:
                        suggestions.append({
                            'flute': flute_dir.name,
                            'old': filename,
                            'new': correct_name,
                            'path': str(file_path)
                        })
        
        return suggestions
    
    def apply_corrections(self, suggestions: List[Dict[str, str]]) -> List[str]:
        """Aplica las correcciones."""
        results = []
        for suggestion in suggestions:
            try:
                old_path = Path(suggestion['path'])
                new_path = old_path.parent / suggestion['new']
                old_path.rename(new_path)
                msg = f"✓ {suggestion['flute']}: '{suggestion['old']}' → '{suggestion['new']}'"
                results.append(msg)
                logger.info(msg)
            except Exception as e:
                msg = f"✗ Error en {suggestion['flute']}: {e}"
                results.append(msg)
                logger.error(msg)
        
        return results


class FileCorrectionDialog(QDialog):
    """Diálogo para mostrar y aplicar correcciones de archivos."""
    
    def __init__(self, suggestions: List[Dict[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Correcciones de Nombres de Archivo")
        self.setMinimumSize(700, 500)
        
        self.suggestions = suggestions
        self.checkboxes = []
        
        layout = QVBoxLayout(self)
        
        # Mensaje
        label = QLabel(
            f"Se encontraron {len(suggestions)} archivos con nombres incorrectos.\n"
            "Selecciona las correcciones que deseas aplicar:"
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        
        # Scroll area con checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        for suggestion in suggestions:
            cb = QCheckBox(
                f"{suggestion['flute']}: '{suggestion['old']}' → '{suggestion['new']}'"
            )
            cb.setChecked(True)
            self.checkboxes.append((cb, suggestion))
            scroll_layout.addWidget(cb)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Botones
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_selected_suggestions(self) -> List[Dict[str, str]]:
        """Retorna las correcciones seleccionadas."""
        return [
            suggestion for cb, suggestion in self.checkboxes if cb.isChecked()
        ]


# ==================== Utilidades 3D ====================

def interpolate_radius(y_pos: float, profile_points: List[Dict]) -> float:
    """Calcula el radio en una posición Y específica."""
    for i in range(len(profile_points) - 1):
        if profile_points[i]['position'] <= y_pos <= profile_points[i+1]['position']:
            p1, p2 = profile_points[i], profile_points[i+1]
            y1, r1 = p1['position'], p1['diameter'] / 2.0
            y2, r2 = p2['position'], p2['diameter'] / 2.0
            if abs(y2 - y1) < 1e-9:
                return r1
            return r1 + (r2 - r1) * ((y_pos - y1) / (y2 - y1))
    
    return profile_points[-1]['diameter'] / 2.0


class FluteAssembler3D:
    """Ensambla una pieza de flauta 3D con perfiles interno/externo."""
    
    def __init__(self, internal_data: Dict, external_data: Dict, cone_angle_deg: float = 5.0):
        self.internal_data = internal_data
        self.external_data = external_data
        self.cone_angle_deg = cone_angle_deg
    
    def _create_cq_solid_from_profile(self, profile_points: List[Dict]):
        """Crea un sólido de CadQuery a partir de un perfil."""
        if not CADQUERY_AVAILABLE:
            return None
        
        path_pts = [(p['diameter'] / 2, p['position']) for p in profile_points]
        if not path_pts:
            return None
        
        # Cerrar el perfil si es necesario
        if path_pts[0][0] > 1e-6:
            path_pts.insert(0, (0, path_pts[0][1]))
        if path_pts[-1][0] > 1e-6:
            path_pts.append((0, path_pts[-1][1]))
        
        try:
            solid = cq.Workplane("XZ").polyline(path_pts).close().revolve()
            return solid
        except Exception as e:
            logger.error(f"Error creando sólido CadQuery: {e}")
            return None
    
    def assemble(self):
        """Ensambla la pieza completa con agujeros."""
        if not CADQUERY_AVAILABLE:
            logger.warning("CadQuery no disponible")
            return None
        
        # Crear sólidos base
        external_solid = self._create_cq_solid_from_profile(
            self.external_data['measurements']
        )
        internal_solid = self._create_cq_solid_from_profile(
            self.internal_data['measurements']
        )
        
        if not external_solid or not internal_solid:
            return None
        
        # Crear cortadores de agujeros
        cutters = []
        cone_angle_rad = np.deg2rad(self.cone_angle_deg)
        
        for i in range(self.internal_data.get("Number of holes", 0)):
            z_pos = self.internal_data["Holes position"][i]
            d_outer_hole = self.internal_data["Holes diameter"][i]
            
            r_body_ext = interpolate_radius(z_pos, self.external_data['measurements'])
            r_body_int = interpolate_radius(z_pos, self.internal_data['measurements'])
            wall_thickness = r_body_ext - r_body_int
            cutter_height = wall_thickness + 4.0
            
            r_outer_hole = d_outer_hole / 2.0
            change_in_radius = wall_thickness * np.tan(cone_angle_rad)
            r_inner_hole = r_outer_hole + change_in_radius
            
            template_solid = cq.Solid.makeCone(r_outer_hole, r_inner_hole, cutter_height)
            template_wp = cq.Workplane(template_solid).translate((0, 0, -cutter_height/2))
            
            x_target = (r_body_ext + r_body_int) / 2
            cutter = template_wp.rotate((0, 0, 0), (0, 1, 0), -90).translate((x_target, 0, z_pos))
            cutters.append(cutter)
        
        # Operaciones booleanas
        try:
            result = external_solid.cut(internal_solid)
            for cutter in cutters:
                result = result.cut(cutter)
            return result
        except Exception as e:
            logger.error(f"Error en operaciones booleanas: {e}")
            return None


def cq_to_pyvista(cq_obj, quality: int = 100):
    """Convierte un objeto de CadQuery a PyVista."""
    if not PYVISTA_AVAILABLE or not CADQUERY_AVAILABLE or cq_obj is None:
        if PYVISTA_AVAILABLE:
            import pyvista as pv
            return pv.PolyData()
        return None
    
    import pyvista as pv
    
    tolerance = 0.5 / quality
    
    # Extraer shape
    if isinstance(cq_obj, cq.Assembly):
        shape = cq_obj.toCompound()
    elif isinstance(cq_obj, cq.Workplane):
        shape = cq_obj.val()
    elif isinstance(cq_obj, cq.Shape):
        shape = cq_obj
    else:
        return pv.PolyData()
    
    try:
        vertices_vector, faces = shape.tessellate(tolerance=tolerance)
        vertices_np = np.array([v.toTuple() for v in vertices_vector])
        
        if len(faces) == 0:
            return pv.PolyData()
        
        faces_pv = np.c_[np.full(len(faces), 3), faces].astype(np.int_)
        return pv.PolyData(vertices_np, faces_pv)
    except Exception as e:
        logger.error(f"Error convirtiendo a PyVista: {e}")
        return pv.PolyData()


# ==================== Diálogo de Selección de Flautas ====================

class FluteSelectionDialog(QDialog):
    """Diálogo para seleccionar flautas a cargar."""
    
    def __init__(self, data_dir: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Flautas")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        
        self.data_dir = data_dir
        self.selected_flutes = []
        self.checkboxes = {}
        
        self._create_ui()
        self._load_available_flutes()
    
    def _create_ui(self):
        """Crea la interfaz del diálogo."""
        layout = QVBoxLayout(self)
        
        # Etiqueta informativa
        info_label = QLabel(f"Directorio: {self.data_dir}")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Área de scroll para checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.checkbox_layout = QVBoxLayout(scroll_content)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Botones de selección rápida
        button_row = QHBoxLayout()
        select_all_btn = QPushButton("Seleccionar Todo")
        select_all_btn.clicked.connect(self._select_all)
        button_row.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deseleccionar Todo")
        deselect_all_btn.clicked.connect(self._deselect_all)
        button_row.addWidget(deselect_all_btn)
        
        layout.addLayout(button_row)
        
        # Botones de aceptar/cancelar
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _load_available_flutes(self):
        """Carga la lista de flautas disponibles."""
        data_path = Path(self.data_dir)
        if not data_path.exists():
            QMessageBox.warning(self, "Error", f"Directorio no existe: {self.data_dir}")
            return
        
        # Buscar subdirectorios
        flute_dirs = sorted([d for d in data_path.iterdir() if d.is_dir()])
        
        if not flute_dirs:
            label = QLabel("No se encontraron flautas en este directorio.")
            self.checkbox_layout.addWidget(label)
            return
        
        # Crear checkbox para cada flauta
        for flute_dir in flute_dirs:
            checkbox = QCheckBox(flute_dir.name)
            checkbox.setChecked(False)  # Por defecto ninguna seleccionada
            self.checkboxes[flute_dir.name] = checkbox
            self.checkbox_layout.addWidget(checkbox)
    
    def _select_all(self):
        """Selecciona todas las flautas."""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(True)
    
    def _deselect_all(self):
        """Deselecciona todas las flautas."""
        for checkbox in self.checkboxes.values():
            checkbox.setChecked(False)
    
    def _on_accept(self):
        """Maneja aceptación del diálogo."""
        self.selected_flutes = [
            name for name, checkbox in self.checkboxes.items()
            if checkbox.isChecked()
        ]
        
        if not self.selected_flutes:
            QMessageBox.warning(
                self, "Sin Selección",
                "Por favor selecciona al menos una flauta."
            )
            return
        
        self.accept()

# ==================== Diálogo de Reporte de BD ====================

class DatabaseReportDialog(QDialog):
    """Diálogo para mostrar reportes de base de datos."""
    
    def __init__(self, report_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reporte de Base de Datos")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Barra de búsqueda
        search_layout = QHBoxLayout()
        search_label = QLabel("Buscar:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Buscar en el reporte...")
        self.search_edit.textChanged.connect(self._search_text)
        search_btn = QPushButton("Buscar")
        search_btn.clicked.connect(self._search_text)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)
        
        # Área de texto con scroll
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Courier", 9))
        self.text_edit.setPlainText(report_text)
        layout.addWidget(self.text_edit)
        
        # Botones
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Guardar como...")
        save_btn.clicked.connect(self._save_report)
        button_layout.addWidget(save_btn)
        button_layout.addStretch()
        
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
    
    def _search_text(self):
        """Busca texto en el reporte."""
        search_term = self.search_edit.text()
        if not search_term:
            return
        
        # Buscar y resaltar
        cursor = self.text_edit.textCursor()
        cursor.movePosition(cursor.Start)
        
        # Buscar siguiente ocurrencia
        found = self.text_edit.find(search_term)
        if not found:
            QMessageBox.information(self, "Búsqueda", "No se encontró más texto.")
            cursor.movePosition(cursor.Start)
            self.text_edit.setTextCursor(cursor)
    
    def _save_report(self):
        """Guarda el reporte en un archivo."""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Reporte",
            "reporte_flautas.txt",
            "Archivos de Texto (*.txt);;Todos los archivos (*.*)"
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.text_edit.toPlainText())
                QMessageBox.information(self, "Éxito", f"Reporte guardado en:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error guardando reporte:\n{e}")


# ==================== GUI Principal ====================

class UnifiedFluteGUI_Qt(QMainWindow):
    """GUI principal unificada en PyQt5."""
    
    def __init__(self):
        try:
            logger.info("Iniciando GUI PyQt5...")
            super().__init__()
            logger.info("QMainWindow inicializado")
            
            self.setWindowTitle("Análisis y Visualización de Flautas Traverso")
            self.setGeometry(100, 100, 1600, 1000)
            logger.info("Ventana configurada")
            
            # Inicializar datos (sin operaciones pesadas)
            self.db_manager = None  # Se inicializa cuando se necesite
            self.data_dir = str(DEFAULT_DATA_JSON_DIR)
            self.flute_data_list: List[FluteDataDB] = []
            self.flute_ops_list: List[FluteOperations] = []
            self.analyzer: Optional[FluteAnalyzer] = None
            self.flutes_3d_data: Dict = {}  # Para visualización 3D
            
            # Bandera para lazy loading de 3D
            self._3d_initialized = False
            # Preferencia de guardado de pressure/flow data (default: False para ahorrar espacio)
            self.save_pressure_flow_data = False
            # Diapasón para cálculo de finger_frequencies (default: 415 Hz)
            self.la_frequency = 415.0
            logger.info("Variables inicializadas")
            
            # Crear UI (sin PyVista todavía)
            logger.info("Creando UI...")
            self._create_menu_bar()
            self._create_ui()
            logger.info("UI creada")
            
            # Inicializar DB en background (usar QTimer para no bloquear)
            # Pero hacerlo de forma más segura
            try:
                QTimer.singleShot(100, self._init_db_manager)
                logger.info("Timer para DB Manager configurado")
            except Exception as e:
                logger.error(f"Error configurando timer para DB Manager: {e}", exc_info=True)
                # Intentar inicializar directamente como fallback
                self._init_db_manager()
            
            logger.info("GUI PyQt5 inicializada completamente")
        except Exception as e:
            logger.error(f"Error durante inicialización de GUI: {e}", exc_info=True)
            raise
    
    def _create_ui(self):
        """Crea la interfaz de usuario."""
        try:
            logger.info("Creando central widget...")
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            
            main_layout = QVBoxLayout(central_widget)
            
            logger.info("Creando barra superior...")
            # Barra superior
            top_bar = self._create_top_bar()
            main_layout.addWidget(top_bar)
            
            logger.info("Creando splitter...")
            # Splitter principal: Panel izquierdo (árbol) + Tabs derecha
            splitter = QSplitter(Qt.Horizontal)
            
            logger.info("Creando panel izquierdo...")
            # Panel izquierdo: Control y árbol de flautas
            left_panel = self._create_left_panel()
            splitter.addWidget(left_panel)
            
            logger.info("Creando tabs...")
            # Panel derecho: Tabs
            self.tabs = QTabWidget()
            self._create_tabs()
            splitter.addWidget(self.tabs)
            
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 3)
            
            main_layout.addWidget(splitter)
            logger.info("UI creada exitosamente")
        except Exception as e:
            logger.error(f"Error creando UI: {e}", exc_info=True)
            raise
    
    def _create_menu_bar(self):
        """Crea la barra de menú con el menú de Base de Datos."""
        menubar = self.menuBar()
        
        # Menú Base de Datos
        db_menu = menubar.addMenu("Base de Datos")
        
        # Submenú: Agregar Flautas
        add_menu = db_menu.addMenu("Agregar Flautas")
        add_dir_action = add_menu.addAction("Desde Directorio...")
        add_dir_action.triggered.connect(self._add_flute_from_directory)
        add_file_action = add_menu.addAction("Desde Archivo JSON...")
        add_file_action.triggered.connect(self._add_flute_from_file)
        
        # Submenú: Reportes
        report_menu = db_menu.addMenu("Reportes")
        generate_report_action = report_menu.addAction("Generar Reporte Completo")
        generate_report_action.triggered.connect(self._generate_database_report)
        view_report_action = report_menu.addAction("Ver Reporte...")
        view_report_action.triggered.connect(self._view_database_report)
        
        # Submenú: Mantenimiento
        maintenance_menu = db_menu.addMenu("Mantenimiento")
        cleanup_action = maintenance_menu.addAction("Limpiar Datos (pressure_flow_data)")
        cleanup_action.triggered.connect(self._cleanup_database)
        optimize_action = maintenance_menu.addAction("Optimizar Base de Datos (VACUUM)")
        optimize_action.triggered.connect(self._optimize_database)
        delete_action = maintenance_menu.addAction("Eliminar Flauta...")
        delete_action.triggered.connect(self._delete_flute_from_db)
        
        # Estadísticas
        stats_action = db_menu.addAction("Ver Estadísticas de BD")
        stats_action.triggered.connect(self._show_database_statistics)
    
    def _create_top_bar(self) -> QWidget:
        """Crea la barra superior con botones principales."""
        top_bar = QWidget()
        layout = QHBoxLayout(top_bar)
        
        title_label = QLabel("Análisis y Visualización de Flautas Traverso")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        
        layout.addWidget(title_label)
        layout.addStretch()
        
        # Botón principal de carga (más prominente)
        load_btn = QPushButton("📁 Cargar Flautas")
        load_btn.setToolTip("Escanear y cargar flautas desde el directorio")
        load_btn.clicked.connect(self._load_flutes)
        load_font = QFont()
        load_font.setBold(True)
        load_btn.setFont(load_font)
        layout.addWidget(load_btn)
        
        # Botón secundario de cambio de directorio (más compacto)
        self.change_dir_btn = QPushButton("📂")
        self.change_dir_btn.setToolTip(f"Cambiar directorio\nActual: {self.data_dir}")
        self.change_dir_btn.clicked.connect(self._change_directory)
        self.change_dir_btn.setMaximumWidth(40)
        layout.addWidget(self.change_dir_btn)
        
        # Label del directorio actual (compacto)
        dir_display = self.data_dir if len(self.data_dir) <= 40 else f"...{self.data_dir[-37:]}"
        self.dir_label = QLabel(dir_display)
        self.dir_label.setStyleSheet("font-size: 9pt; color: gray; padding: 0 5px;")
        self.dir_label.setToolTip(self.data_dir)
        layout.addWidget(self.dir_label)
        
        # Botón de corrección de archivos
        fix_btn = QPushButton("🔧 Corregir Archivos")
        fix_btn.setToolTip("Escanea y corrige nombres de archivos JSON mal escritos")
        fix_btn.clicked.connect(self._check_and_fix_files)
        layout.addWidget(fix_btn)
        
        # Botón de editar geometría
        edit_btn = QPushButton("✏️ Editar Geometría")
        edit_btn.setToolTip("Abre el editor interactivo de geometría de flautas")
        edit_btn.clicked.connect(self._open_geometry_editor)
        layout.addWidget(edit_btn)
        
        # Botón de salir
        exit_btn = QPushButton("Salir")
        exit_btn.clicked.connect(self.close)
        layout.addWidget(exit_btn)
        
        return top_bar
    
    def _create_left_panel(self) -> QWidget:
        """Crea el panel izquierdo con controles compactos."""
        panel = QWidget()
        panel.setMaximumWidth(200)
        layout = QVBoxLayout(panel)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Panel izquierdo ahora está vacío, solo para mantener la estructura
        layout.addStretch()
        
        return panel
    
    def _create_tabs(self):
        """Crea las pestañas principales."""
        try:
            logger.info("Creando tab 2D...")
            # Tab 1: Geometría
            self.tab_2d = QWidget()
            self._create_2d_tab()
            self.tabs.addTab(self.tab_2d, "Geometría")
            
            logger.info("Creando tab Admitancia...")
            # Tab 2: Admitancia
            self.tab_admittance = QWidget()
            self._create_admittance_tab()
            self.tabs.addTab(self.tab_admittance, "Admitancia")
            
            logger.info("Creando tab Análisis...")
            # Tab 3: Análisis
            self.tab_analysis = QWidget()
            self._create_analysis_tab()
            self.tabs.addTab(self.tab_analysis, "Análisis Acústico")
            
            logger.info("Creando tab 3D...")
            # Tab 4: Visualización 3D
            self.tab_3d = QWidget()
            self._create_3d_tab()
            self.tabs.addTab(self.tab_3d, "Visualización 3D")
            
            logger.info("Creando tab Planos...")
            # Tab 5: Planos de Ingeniería
            self.tab_drawings = QWidget()
            self._create_drawings_tab()
            self.tabs.addTab(self.tab_drawings, "Planos de Ingeniería")
            
            logger.info("Creando tab G-code...")
            # Tab 6: Generación G-code
            self.tab_gcode = QWidget()
            self._create_gcode_tab()
            self.tabs.addTab(self.tab_gcode, "Generación G-code")
            logger.info("Todas las tabs creadas")
        except Exception as e:
            logger.error(f"Error creando tabs: {e}", exc_info=True)
            raise
    
    def _create_2d_tab(self):
        """Crea la pestaña de visualización 2D."""
        layout = QVBoxLayout(self.tab_2d)
        
        # Sub-tabs para perfil y partes
        sub_tabs = QTabWidget()
        
        # Perfil combinado - con sub-tabs para interno y sólido
        profile_widget = QWidget()
        profile_layout = QVBoxLayout(profile_widget)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        
        profile_sub_tabs = QTabWidget()
        
        # Perfil interno (existente)
        profile_internal_widget = QWidget()
        profile_internal_layout = QVBoxLayout(profile_internal_widget)
        profile_internal_layout.setContentsMargins(0, 0, 0, 0)
        self.profile_figure = Figure(figsize=(12, 8))
        self.profile_canvas = FigureCanvas(self.profile_figure)
        profile_internal_layout.addWidget(self.profile_canvas)
        profile_sub_tabs.addTab(profile_internal_widget, "Perfil Interno")
        
        # Vista sólido 2D (nuevo)
        profile_solid_widget = QWidget()
        profile_solid_layout = QVBoxLayout(profile_solid_widget)
        profile_solid_layout.setContentsMargins(0, 0, 0, 0)
        self.profile_solid_figure = Figure(figsize=(12, 8))
        self.profile_solid_canvas = FigureCanvas(self.profile_solid_figure)
        profile_solid_layout.addWidget(self.profile_solid_canvas)
        profile_sub_tabs.addTab(profile_solid_widget, "Vista Sólido 2D")
        
        # Corte axial del sólido (nuevo)
        profile_axial_widget = QWidget()
        profile_axial_layout = QVBoxLayout(profile_axial_widget)
        profile_axial_layout.setContentsMargins(0, 0, 0, 0)
        self.profile_axial_figure = Figure(figsize=(12, 8))
        self.profile_axial_canvas = FigureCanvas(self.profile_axial_figure)
        profile_axial_layout.addWidget(self.profile_axial_canvas)
        profile_sub_tabs.addTab(profile_axial_widget, "Corte Axial")
        
        profile_layout.addWidget(profile_sub_tabs)
        sub_tabs.addTab(profile_widget, "Perfil Combinado")
        
        # Partes individuales - con sub-tabs para interno y sólido
        parts_widget = QWidget()
        parts_layout = QVBoxLayout(parts_widget)
        parts_layout.setContentsMargins(0, 0, 0, 0)
        
        parts_sub_tabs = QTabWidget()
        
        # Partes internas (existentes)
        parts_internal_widget = QWidget()
        parts_internal_layout = QVBoxLayout(parts_internal_widget)
        parts_internal_layout.setContentsMargins(0, 0, 0, 0)
        self.parts_figure = Figure(figsize=(12, 8))
        self.parts_canvas = FigureCanvas(self.parts_figure)
        parts_internal_layout.addWidget(self.parts_canvas)
        parts_sub_tabs.addTab(parts_internal_widget, "Perfil Interno")
        
        # Vista sólido 2D de partes (nuevo)
        parts_solid_widget = QWidget()
        parts_solid_layout = QVBoxLayout(parts_solid_widget)
        parts_solid_layout.setContentsMargins(0, 0, 0, 0)
        self.parts_solid_figure = Figure(figsize=(12, 8))
        self.parts_solid_canvas = FigureCanvas(self.parts_solid_figure)
        parts_solid_layout.addWidget(self.parts_solid_canvas)
        parts_sub_tabs.addTab(parts_solid_widget, "Vista Sólido 2D")
        
        # Corte axial de partes (nuevo)
        parts_axial_widget = QWidget()
        parts_axial_layout = QVBoxLayout(parts_axial_widget)
        parts_axial_layout.setContentsMargins(0, 0, 0, 0)
        self.parts_axial_figure = Figure(figsize=(12, 8))
        self.parts_axial_canvas = FigureCanvas(self.parts_axial_figure)
        parts_axial_layout.addWidget(self.parts_axial_canvas)
        parts_sub_tabs.addTab(parts_axial_widget, "Corte Axial")
        
        parts_layout.addWidget(parts_sub_tabs)
        sub_tabs.addTab(parts_widget, "Partes Individuales")
        
        layout.addWidget(sub_tabs)
    
    def _create_admittance_tab(self):
        """Crea la pestaña de admitancia."""
        layout = QVBoxLayout(self.tab_admittance)
        
        # Selector de nota y opciones
        control_frame = QWidget()
        control_layout = QHBoxLayout(control_frame)
        control_layout.addWidget(QLabel("Nota:"))
        
        self.note_combo = QComboBox()
        self.note_combo.currentTextChanged.connect(self._update_admittance_plot)
        control_layout.addWidget(self.note_combo)
        control_layout.addStretch()
        
        # Checkbox para guardar pressure/flow data
        self.save_pf_checkbox = QCheckBox("Guardar datos de presión/flujo en BD")
        self.save_pf_checkbox.setChecked(False)
        self.save_pf_checkbox.setToolTip(
            "Si está marcado, los datos de presión y flujo se guardarán en la BD.\n"
            "Esto aumenta significativamente el tamaño de la base de datos.\n"
            "La preferencia se aplicará a las nuevas flautas que se carguen.\n\n"
            "IMPORTANTE: Para visualizar presión/flujo en flautas ya cargadas:\n"
            "1. Marca este checkbox\n"
            "2. Recarga la flauta (se recalculará y guardará con los datos)"
        )
        self.save_pf_checkbox.stateChanged.connect(self._on_pressure_flow_saving_changed)
        control_layout.addWidget(self.save_pf_checkbox)
        
        # Botón para recalcular flautas cargadas con datos de presión/flujo
        self.recalc_pf_btn = QPushButton("🔄 Recalcular con P/F")
        self.recalc_pf_btn.setToolTip(
            "Recalcula las flautas cargadas con datos de presión/flujo.\n"
            "Solo funciona si el checkbox 'Guardar datos' está marcado."
        )
        self.recalc_pf_btn.setEnabled(False)  # Inicialmente deshabilitado
        self.recalc_pf_btn.clicked.connect(self._recalculate_with_pressure_flow)
        control_layout.addWidget(self.recalc_pf_btn)
        
        layout.addWidget(control_frame)
        
        # Canvas
        self.admittance_figure = Figure(figsize=(12, 10))
        self.admittance_canvas = FigureCanvas(self.admittance_figure)
        layout.addWidget(self.admittance_canvas)
    
    def _create_analysis_tab(self):
        """Crea la pestaña de análisis acústico."""
        layout = QVBoxLayout(self.tab_analysis)
        
        # Controles superiores para diapasón
        controls_frame = QGroupBox("Configuración de Diapasón")
        controls_layout = QHBoxLayout(controls_frame)
        
        controls_layout.addWidget(QLabel("Diapasón (Hz):"))
        self.la_frequency_spinbox = QDoubleSpinBox()
        self.la_frequency_spinbox.setMinimum(300.0)
        self.la_frequency_spinbox.setMaximum(500.0)
        self.la_frequency_spinbox.setSingleStep(1.0)
        self.la_frequency_spinbox.setDecimals(1)
        self.la_frequency_spinbox.setValue(self.la_frequency)  # Usar el valor actual
        self.la_frequency_spinbox.setSuffix(" Hz")
        self.la_frequency_spinbox.valueChanged.connect(self._on_diapason_changed)
        controls_layout.addWidget(self.la_frequency_spinbox)
        
        controls_layout.addWidget(QLabel("(Frecuencia de referencia para A)"))
        controls_layout.addStretch()
        
        layout.addWidget(controls_frame)
        
        # Sub-tabs para diferentes análisis
        sub_tabs = QTabWidget()
        
        # 1. Resumen (Dashboard)
        summary_widget = QWidget()
        summary_layout = QVBoxLayout(summary_widget)
        
        # Scroll area para el resumen
        summary_scroll = QScrollArea()
        summary_scroll.setWidgetResizable(True)
        summary_content = QWidget()
        summary_content_layout = QVBoxLayout(summary_content)
        
        # Grid de métricas clave
        self.metrics_group = QGroupBox("Métricas Clave")
        self.metrics_layout = QGridLayout()
        self.summary_labels = {}
        self.metrics_group.setLayout(self.metrics_layout)
        summary_content_layout.addWidget(self.metrics_group)
        
        # Gráfico radar para comparación
        self.summary_figure = Figure(figsize=(12, 8))
        self.summary_canvas = FigureCanvas(self.summary_figure)
        summary_content_layout.addWidget(self.summary_canvas)
        
        summary_scroll.setWidget(summary_content)
        summary_layout.addWidget(summary_scroll)
        sub_tabs.addTab(summary_widget, "📊 Resumen")
        
        # 2. Inharmonicidad
        inharm_widget = QWidget()
        inharm_layout = QVBoxLayout(inharm_widget)
        self.inharm_figure = Figure(figsize=(10, 6))
        self.inharm_canvas = FigureCanvas(self.inharm_figure)
        inharm_layout.addWidget(self.inharm_canvas)
        sub_tabs.addTab(inharm_widget, "Inharmonicidad")
        
        # 3. Frecuencias de Resonancia
        resonance_widget = QWidget()
        resonance_layout = QVBoxLayout(resonance_widget)
        self.resonance_figure = Figure(figsize=(10, 6))
        self.resonance_canvas = FigureCanvas(self.resonance_figure)
        resonance_layout.addWidget(self.resonance_canvas)
        sub_tabs.addTab(resonance_widget, "Frecuencias")
        
        # 4. MOC
        moc_widget = QWidget()
        moc_layout = QVBoxLayout(moc_widget)
        self.moc_figure = Figure(figsize=(10, 6))
        self.moc_canvas = FigureCanvas(self.moc_figure)
        moc_layout.addWidget(self.moc_canvas)
        sub_tabs.addTab(moc_widget, "MOC")
        
        # 5. B_I y ESPE
        bi_widget = QWidget()
        bi_layout = QVBoxLayout(bi_widget)
        self.bi_figure = Figure(figsize=(10, 6))
        self.bi_canvas = FigureCanvas(self.bi_figure)
        bi_layout.addWidget(self.bi_canvas)
        sub_tabs.addTab(bi_widget, "B_I & ESPE")
        
        # 6. Altura de Picos
        peak_widget = QWidget()
        peak_layout = QVBoxLayout(peak_widget)
        self.peak_figure = Figure(figsize=(10, 6))
        self.peak_canvas = FigureCanvas(self.peak_figure)
        peak_layout.addWidget(self.peak_canvas)
        sub_tabs.addTab(peak_widget, "Altura de Picos")
        
        # 7. Q-Factor
        qfactor_widget = QWidget()
        qfactor_layout = QVBoxLayout(qfactor_widget)
        self.qfactor_figure = Figure(figsize=(10, 6))
        self.qfactor_canvas = FigureCanvas(self.qfactor_figure)
        qfactor_layout.addWidget(self.qfactor_canvas)
        sub_tabs.addTab(qfactor_widget, "Q-Factor")
        
        # 8. Características Tonales (Ratios + Fase)
        tonal_widget = QWidget()
        tonal_layout = QVBoxLayout(tonal_widget)
        self.tonal_figure = Figure(figsize=(12, 10))
        self.tonal_canvas = FigureCanvas(self.tonal_figure)
        tonal_layout.addWidget(self.tonal_canvas)
        sub_tabs.addTab(tonal_widget, "Características Tonales")
        
        # 9. Estabilidad (Pitch + Cut-off)
        stability_widget = QWidget()
        stability_layout = QVBoxLayout(stability_widget)
        self.stability_figure = Figure(figsize=(12, 10))
        self.stability_canvas = FigureCanvas(self.stability_figure)
        stability_layout.addWidget(self.stability_canvas)
        sub_tabs.addTab(stability_widget, "Estabilidad")
        
        layout.addWidget(sub_tabs)
    
    def _create_3d_tab(self):
        """Crea la pestaña de visualización 3D con PyVista (lazy loading)."""
        layout = QVBoxLayout(self.tab_3d)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        if not PYVISTA_AVAILABLE:
            label = QLabel(
                "PyVista no está disponible.\n"
                "Instala con: pip install pyvista pyvistaqt"
            )
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            return
        
        # Splitter principal: Panel izquierdo (árbol + controles) | Visor 3D
        splitter_3d = QSplitter(Qt.Horizontal)
        
        # ========== PANEL IZQUIERDO: Árbol + Controles ==========
        left_panel = QWidget()
        left_panel.setMaximumWidth(200)
        left_panel.setMinimumWidth(180)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)
        
        # Árbol de flautas (ocupa la mayor parte del panel izquierdo)
        tree_group = QGroupBox("Flautas y Piezas")
        tree_layout = QVBoxLayout(tree_group)
        tree_layout.setContentsMargins(3, 8, 3, 3)
        tree_layout.setSpacing(3)
        
        self.flute_tree = QTreeWidget()
        self.flute_tree.setHeaderLabel("Selecciona")
        self.flute_tree.setRootIsDecorated(True)
        self.flute_tree.itemClicked.connect(self._on_tree_item_clicked)
        self.flute_tree.setIndentation(15)
        tree_layout.addWidget(self.flute_tree)
        left_layout.addWidget(tree_group, stretch=1)  # Ocupa el espacio disponible
        
        # Controles compactos en la parte inferior del panel izquierdo
        controls_group = QGroupBox("Controles")
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setContentsMargins(5, 8, 5, 5)
        controls_layout.setSpacing(5)
        
        # Calidad de malla
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Calidad:"))
        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(50, 800)
        self.quality_spin.setValue(200)
        self.quality_spin.setSingleStep(25)
        self.quality_spin.setMaximumWidth(80)
        self.quality_spin.valueChanged.connect(self._refresh_3d_view)
        quality_layout.addWidget(self.quality_spin)
        quality_layout.addStretch()
        controls_layout.addLayout(quality_layout)
        
        # Botón exportar
        export_stl_btn = QPushButton("Exportar STL")
        export_stl_btn.clicked.connect(self._export_stl)
        controls_layout.addWidget(export_stl_btn)
        
        left_layout.addWidget(controls_group)
        left_layout.addStretch(0)  # No estirar más allá de lo necesario
        
        splitter_3d.addWidget(left_panel)
        
        # ========== PANEL DERECHO: Visor 3D ==========
        self.plotter_3d_container = QWidget()
        self.plotter_3d_layout = QVBoxLayout(self.plotter_3d_container)
        self.plotter_3d_layout.setContentsMargins(0, 0, 0, 0)
        splitter_3d.addWidget(self.plotter_3d_container)
        
        # Configurar proporciones: panel izquierdo pequeño, visor 3D grande
        splitter_3d.setStretchFactor(0, 0)  # Panel izquierdo no se estira
        splitter_3d.setStretchFactor(1, 1)  # Visor 3D ocupa todo el espacio restante
        
        layout.addWidget(splitter_3d)
        
        self.plotter_3d = None  # Se inicializa después
        
        # Conectar cambio de tab para inicializar PyVista solo cuando sea necesario
        self.tabs.currentChanged.connect(self._on_tab_changed)
    
    def _create_drawings_tab(self):
        """Crea la pestaña de planos de ingeniería."""
        layout = QVBoxLayout(self.tab_drawings)
        
        # Controles superiores
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        
        # Selector de flauta
        controls_layout.addWidget(QLabel("Flauta:"))
        self.drawings_flute_combo = QComboBox()
        self.drawings_flute_combo.setMinimumWidth(150)
        self.drawings_flute_combo.currentTextChanged.connect(self._on_drawings_flute_changed)
        controls_layout.addWidget(self.drawings_flute_combo)
        
        controls_layout.addSpacing(20)
        
        # Botón de generación (la vista previa se mostrará automáticamente)
        generate_btn = QPushButton("Generar PDF Completo")
        generate_btn.clicked.connect(self._generate_drawings)
        controls_layout.addWidget(generate_btn)
        
        controls_layout.addStretch()
        
        layout.addWidget(controls)
        
        # Canvas para vista previa
        self.drawings_figure = Figure(figsize=(10, 12))
        self.drawings_canvas = FigureCanvas(self.drawings_figure)
        layout.addWidget(self.drawings_canvas)
    
    def _create_gcode_tab(self):
        """Crea la pestaña de generación de G-code."""
        layout = QHBoxLayout(self.tab_gcode)
        
        # Panel izquierdo: Controles y parámetros
        left_panel = QWidget()
        left_panel.setMaximumWidth(350)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)
        left_layout.setContentsMargins(10, 10, 10, 10)
        
        # Selección de flauta y parte
        selection_group = QGroupBox("Selección")
        selection_layout = QFormLayout(selection_group)
        
        self.gcode_flute_combo = QComboBox()
        self.gcode_flute_combo.setMinimumWidth(200)
        self.gcode_flute_combo.currentTextChanged.connect(self._update_gcode_part_selection)
        selection_layout.addRow("Flauta:", self.gcode_flute_combo)
        
        self.gcode_part_combo = QComboBox()
        self.gcode_part_combo.setMinimumWidth(200)
        for part in FLUTE_PARTS_ORDER:
            self.gcode_part_combo.addItem(part.capitalize())
        selection_layout.addRow("Parte:", self.gcode_part_combo)
        
        left_layout.addWidget(selection_group)
        
        # Parámetros de corte
        params_group = QGroupBox("Parámetros de Corte")
        params_layout = QFormLayout(params_group)
        
        # Estrategia de desbaste
        self.gcode_roughing_strategy = QComboBox()
        self.gcode_roughing_strategy.addItems(["Layers", "Conical"])
        self.gcode_roughing_strategy.setCurrentText(DEFAULT_PARAMS["ROUGHING_STRATEGY"])
        params_layout.addRow("Estrategia Desbaste:", self.gcode_roughing_strategy)
        
        # Modo económico
        self.gcode_economy_mode = QCheckBox()
        self.gcode_economy_mode.setChecked(False)
        params_layout.addRow("Modo Económico:", self.gcode_economy_mode)
        
        # Parámetros numéricos
        self.gcode_params = {}
        param_widgets = {}
        
        for key, default_value in DEFAULT_PARAMS.items():
            if key in ["ROUGHING_STRATEGY", "ECONOMY_MODE"]:
                continue
            
            label_text = key.replace("_", " ").title()
            if "DIAMETER" in key:
                label_text += " (mm)"
            elif "DEPTH" in key:
                label_text += " (mm, Dia)"
            elif "ALLOWANCE" in key:
                label_text += " (mm, Rad)"
            elif "SPEED" in key:
                label_text += " (RPM)"
            elif "RATE" in key:
                label_text += " (mm/min)"
            elif "SAFE_Z" in key:
                label_text += " (mm)"
            elif "RETRACT" in key:
                label_text += " (mm, Rad)"
            
            if key == "SPINDLE_SPEED":
                widget = QSpinBox()
                widget.setRange(1, 10000)
                widget.setValue(int(default_value))
            else:
                widget = QDoubleSpinBox()
                widget.setRange(0.0, 1000.0)
                widget.setDecimals(3)
                widget.setValue(float(default_value))
                widget.setSingleStep(0.1)
            
            self.gcode_params[key] = widget
            param_widgets[key] = widget
            params_layout.addRow(f"{label_text}:", widget)
        
        left_layout.addWidget(params_group)
        
        # Botón de generación
        generate_btn = QPushButton("Generar G-code y Gráficos")
        generate_btn.setMinimumHeight(40)
        font = QFont()
        font.setBold(True)
        generate_btn.setFont(font)
        generate_btn.clicked.connect(self._generate_gcode_for_part)
        left_layout.addWidget(generate_btn)
        
        left_layout.addStretch()
        
        layout.addWidget(left_panel)
        
        # Panel derecho: Visualizaciones
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        # Splitter vertical para los dos gráficos
        splitter = QSplitter(Qt.Vertical)
        
        # Gráfico 1: Trayectorias Intencionales
        plot1_widget = QWidget()
        plot1_layout = QVBoxLayout(plot1_widget)
        plot1_layout.setContentsMargins(0, 0, 0, 0)
        
        self.gcode_figure1 = Figure(figsize=(8, 5))
        self.gcode_canvas1 = FigureCanvas(self.gcode_figure1)
        self.gcode_ax1 = self.gcode_figure1.add_subplot(111)
        self.gcode_ax1.set_title("Trayectorias Intencionales")
        self.gcode_ax1.grid(True)
        self.gcode_ax1.set_xlabel("Posición Z' (+ Profundidad)")
        self.gcode_ax1.set_ylabel("Radio (mm)")
        
        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
        toolbar1 = NavigationToolbar2QT(self.gcode_canvas1, self)
        plot1_layout.addWidget(toolbar1)
        plot1_layout.addWidget(self.gcode_canvas1)
        
        splitter.addWidget(plot1_widget)
        
        # Gráfico 2: Trayectorias desde Archivo NC
        plot2_widget = QWidget()
        plot2_layout = QVBoxLayout(plot2_widget)
        plot2_layout.setContentsMargins(0, 0, 0, 0)
        
        self.gcode_figure2 = Figure(figsize=(8, 5))
        self.gcode_canvas2 = FigureCanvas(self.gcode_figure2)
        self.gcode_ax2 = self.gcode_figure2.add_subplot(111)
        self.gcode_ax2.set_title("Trayectorias desde Archivo NC")
        self.gcode_ax2.grid(True)
        self.gcode_ax2.set_xlabel("Posición Z G-code")
        self.gcode_ax2.set_ylabel("Radio (mm)")
        
        toolbar2 = NavigationToolbar2QT(self.gcode_canvas2, self)
        plot2_layout.addWidget(toolbar2)
        plot2_layout.addWidget(self.gcode_canvas2)
        
        splitter.addWidget(plot2_widget)
        
        # Configurar proporciones del splitter
        splitter.setSizes([400, 400])
        
        right_layout.addWidget(splitter)
        layout.addWidget(right_panel)
    
    # ==================== Métodos de Funcionalidad ====================
    
    def _init_db_manager(self):
        """Inicializa el gestor de BD en background."""
        try:
            logger.info("Inicializando DB Manager...")
            # Procesar eventos para mantener UI responsiva
            QApplication.processEvents()
            
            # Verificar tamaño de la base de datos antes de inicializar
            from db_schema import DEFAULT_DB_PATH
            db_path = Path(DEFAULT_DB_PATH)
            if db_path.exists():
                db_size_mb = db_path.stat().st_size / (1024 * 1024)
                logger.info(f"Tamaño de BD: {db_size_mb:.2f} MB")
                
                # Si la BD es muy grande (> 1 GB), no intentar inicializarla
                # para evitar problemas de memoria
                if db_size_mb > 1000:
                    logger.error(f"Base de datos demasiado grande ({db_size_mb:.2f} MB = {db_size_mb/1024:.2f} GB)")
                    logger.error("La base de datos es demasiado grande para cargar en memoria.")
                    logger.error("La aplicación funcionará sin caché de base de datos.")
                    self.db_manager = None
                    
                    try:
                        QMessageBox.warning(
                            self, "Base de Datos Demasiado Grande",
                            f"La base de datos es muy grande ({db_size_mb/1024:.2f} GB) y no se puede cargar.\n\n"
                            "La aplicación funcionará sin caché de base de datos.\n"
                            "Los cálculos se realizarán directamente desde los archivos JSON."
                        )
                    except:
                        pass
                    return
                elif db_size_mb > 500:
                    logger.warning(f"Base de datos muy grande ({db_size_mb:.2f} MB), podría causar problemas de memoria")
            
            QApplication.processEvents()
            
            # Intentar inicializar de forma simple
            # Si hay un problema, lo manejamos graciosamente
            logger.info("Creando instancia de FluteDBManager...")
            QApplication.processEvents()
            
            self.db_manager = FluteDBManager()
            logger.info("DB Manager inicializado exitosamente")
            
        except MemoryError as e:
            logger.error(f"Error de memoria inicializando DB Manager: {e}")
            self.db_manager = None
            try:
                QMessageBox.critical(
                    self, "Error de Memoria",
                    "No hay suficiente memoria para inicializar la base de datos.\n"
                    "La aplicación funcionará en modo sin caché."
                )
            except:
                pass
        except Exception as e:
            logger.error(f"Error inicializando DB Manager: {e}", exc_info=True)
            self.db_manager = None
            # No mostrar mensaje si la ventana aún no está lista
            try:
                QMessageBox.warning(
                    self, "Advertencia",
                    f"No se pudo inicializar la base de datos: {e}\n"
                    "La aplicación funcionará en modo sin caché."
                )
            except:
                pass  # Si la ventana no está lista, solo loguear
    
    def _on_tab_changed(self, index: int):
        """Maneja cambio de tab para lazy loading."""
        # Si es el tab 3D y no está inicializado, inicializarlo ahora
        if index == 3 and not self._3d_initialized and PYVISTA_AVAILABLE:
            self._init_3d_viewer()
    
    def _init_3d_viewer(self):
        """Inicializa el visor 3D solo cuando se necesita."""
        if self._3d_initialized or not PYVISTA_AVAILABLE:
            return
        
        try:
            logger.info("Inicializando visor PyVista...")
            self.plotter_3d = QtInteractor(self.plotter_3d_container)
            self.plotter_3d_layout.addWidget(self.plotter_3d.interactor)
            self._3d_initialized = True
            logger.info("Visor PyVista inicializado")
        except Exception as e:
            logger.error(f"Error inicializando PyVista: {e}")
            error_label = QLabel(f"Error inicializando visor 3D:\n{e}")
            error_label.setAlignment(Qt.AlignCenter)
            self.plotter_3d_layout.addWidget(error_label)
    
    def _change_directory(self):
        """Cambia el directorio de datos."""
        directory = QFileDialog.getExistingDirectory(
            self, "Seleccionar Directorio de Datos", self.data_dir
        )
        if directory:
            self.data_dir = directory
            # Actualizar label con el nuevo formato compacto (mismo que en la barra superior)
            dir_display = self.data_dir if len(self.data_dir) <= 40 else f"...{self.data_dir[-37:]}"
            self.dir_label.setText(dir_display)
            self.dir_label.setToolTip(self.data_dir)
            # Actualizar tooltip del botón
            if hasattr(self, 'change_dir_btn'):
                self.change_dir_btn.setToolTip(f"Cambiar directorio\nActual: {self.data_dir}")
    
    def _check_and_fix_files(self):
        """Escanea y corrige archivos mal nombrados."""
        corrector = FileCorrector(Path(self.data_dir))
        suggestions = corrector.scan_for_errors()
        
        if not suggestions:
            QMessageBox.information(
                self, "Sin Errores",
                "No se encontraron archivos con nombres incorrectos."
            )
            return
        
        # Mostrar diálogo
        dialog = FileCorrectionDialog(suggestions, self)
        if dialog.exec_() == QDialog.Accepted:
            selected = dialog.get_selected_suggestions()
            if selected:
                results = corrector.apply_corrections(selected)
                QMessageBox.information(
                    self, "Correcciones Aplicadas",
                    "\n".join(results)
                )
    
    def _open_geometry_editor(self):
        """Abre el editor de geometría interactivo."""
        if not self.flute_data_list:
            QMessageBox.warning(
                self, "Sin Flautas",
                "Primero debe cargar al menos una flauta."
            )
            return
        
        # Mostrar diálogo de selección si hay múltiples flautas
        if len(self.flute_data_list) == 1:
            selected_flute = self.flute_data_list[0]
        else:
            # Crear diálogo de selección
            flute_names = [fd.flute_model for fd in self.flute_data_list]
            from PyQt5.QtWidgets import QInputDialog
            flute_name, ok = QInputDialog.getItem(
                self, "Seleccionar Flauta",
                "Seleccione la flauta a editar:",
                flute_names, 0, False
            )
            
            if not ok:
                return
            
            selected_flute = next(
                (fd for fd in self.flute_data_list if fd.flute_model == flute_name),
                None
            )
        
        if not selected_flute:
            QMessageBox.warning(
                self, "Error",
                "No se pudo encontrar la flauta seleccionada."
            )
            return
        
        try:
            # Crear y abrir editor
            editor = FluteGeometryEditor(selected_flute, self)
            
            # Conectar señal para actualizar GUI cuando se guarde una nueva flauta
            editor.flute_modified.connect(self._on_flute_modified)
            
            editor.exec_()
        
        except Exception as e:
            logger.error(f"Error abriendo editor de geometría: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Error",
                f"Error abriendo editor de geometría:\n{e}"
            )
    
    def _on_flute_modified(self, new_flute_name: str):
        """Maneja la señal cuando se modifica/guarda una flauta."""
        reply = QMessageBox.question(
            self, "Flauta Guardada",
            f"La flauta '{new_flute_name}' ha sido guardada.\n¿Desea cargarla ahora?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Intentar cargar la nueva flauta
            try:
                base_dir = Path(self.data_dir)
                new_flute_dir = base_dir / new_flute_name
                
                if new_flute_dir.exists():
                    # Cargar la nueva flauta
                    new_flute_data = FluteDataDB(
                        str(new_flute_dir),
                        db_manager=self.db_manager,
                        la_frequency=415.0
                    )
                    
                    self.flute_data_list.append(new_flute_data)
                    
                    # Actualizar selectores en tabs
                    self._update_flute_selectors()
                    
                    QMessageBox.information(
                        self, "Flauta Cargada",
                        f"La flauta '{new_flute_name}' ha sido cargada exitosamente."
                    )
                else:
                    QMessageBox.warning(
                        self, "Directorio no encontrado",
                        f"No se encontró el directorio de la flauta '{new_flute_name}'."
                    )
            
            except Exception as e:
                logger.error(f"Error cargando flauta modificada: {e}", exc_info=True)
                QMessageBox.critical(
                    self, "Error",
                    f"Error cargando la flauta:\n{e}"
                )
    
    def _update_flute_selectors(self):
        """Actualiza los selectores de flautas en todas las tabs."""
        # Actualizar selector de G-code
        if hasattr(self, 'gcode_flute_combo'):
            current_selection = self.gcode_flute_combo.currentText()
            self.gcode_flute_combo.clear()
            for flute_data in self.flute_data_list:
                self.gcode_flute_combo.addItem(flute_data.flute_model)
            
            # Restaurar selección si aún existe
            index = self.gcode_flute_combo.findText(current_selection)
            if index >= 0:
                self.gcode_flute_combo.setCurrentIndex(index)
        
        # Actualizar selector de planos de ingeniería
        if hasattr(self, 'drawings_flute_combo'):
            current_selection = self.drawings_flute_combo.currentText()
            self.drawings_flute_combo.clear()
            for flute_data in self.flute_data_list:
                self.drawings_flute_combo.addItem(flute_data.flute_model)
            
            # Restaurar selección si aún existe
            index = self.drawings_flute_combo.findText(current_selection)
            if index >= 0:
                self.drawings_flute_combo.setCurrentIndex(index)
    
    def _load_flutes(self):
        """Muestra diálogo para seleccionar y cargar flautas."""
        # No intentar inicializar DB Manager si ya sabemos que es demasiado grande
        # (se habrá establecido como None en _init_db_manager)
        # Si es None por otra razón, intentar inicializarlo
        if self.db_manager is None:
            # Verificar tamaño primero para evitar intentar inicializar una BD enorme
            from db_schema import DEFAULT_DB_PATH
            db_path = Path(DEFAULT_DB_PATH)
            if db_path.exists():
                db_size_mb = db_path.stat().st_size / (1024 * 1024)
                if db_size_mb > 1000:
                    logger.info(f"BD demasiado grande ({db_size_mb/1024:.2f} GB), no intentando inicializar")
                else:
                    self._init_db_manager()
            else:
                self._init_db_manager()
        
        # Mostrar diálogo de selección
        dialog = FluteSelectionDialog(self.data_dir, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        
        selected_flutes = dialog.selected_flutes
        if not selected_flutes:
            return
        
        data_path = Path(self.data_dir)
        
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()  # Mantener UI responsiva
        
        self.flute_data_list.clear()
        self.flute_ops_list.clear()
        self.flutes_3d_data.clear()
        
        # Limpiar árbol si existe (se crea cuando se accede a la pestaña 3D)
        if hasattr(self, 'flute_tree') and self.flute_tree:
            self.flute_tree.clear()
        
        # Cargar solo las flautas seleccionadas
        for idx, flute_name in enumerate(selected_flutes):
            flute_dir = data_path / flute_name
            if not flute_dir.exists():
                logger.warning(f"Directorio no existe: {flute_dir}")
                continue
            
            try:
                logger.info(f"Cargando {flute_name} ({idx+1}/{len(selected_flutes)})...")
                QApplication.processEvents()  # Mantener UI responsiva
                
                logger.debug(f"Creando FluteDataDB para {flute_name}...")
                # Pasar el db_manager si existe, para evitar crear uno nuevo
                # Usar la preferencia del usuario para guardar pressure/flow data
                flute_data = FluteDataDB(
                    str(flute_dir), 
                    db_manager=self.db_manager,
                    include_pressure_flow=self.save_pressure_flow_data
                )
                logger.debug(f"FluteDataDB creado para {flute_name} (include_pressure_flow={self.save_pressure_flow_data})")
                QApplication.processEvents()
                
                if flute_data.validation_errors:
                    logger.warning(f"Errores de validación en {flute_name}")
                    QMessageBox.warning(
                        self, "Error de Validación",
                        f"La flauta '{flute_name}' tiene errores de validación y no se cargó."
                    )
                    QApplication.processEvents()
                    continue
                
                logger.debug(f"Añadiendo {flute_name} a listas...")
                self.flute_data_list.append(flute_data)
                self.flute_ops_list.append(FluteOperations(flute_data))
                QApplication.processEvents()
                
                logger.debug(f"Añadiendo {flute_name} al árbol...")
                # Añadir al árbol con piezas (si el árbol existe, se crea cuando se accede a la pestaña 3D)
                flute_item = None
                if hasattr(self, 'flute_tree') and self.flute_tree:
                    flute_item = QTreeWidgetItem(self.flute_tree, [flute_data.flute_model])
                    flute_item.setData(0, Qt.UserRole, {'type': 'flute', 'name': flute_data.flute_model})
                QApplication.processEvents()
                
                logger.debug(f"Escaneando archivos 3D para {flute_name}...")
                # Cargar datos 3D y añadir piezas al árbol
                parts_found = self._scan_3d_files_for_flute(flute_dir, flute_data.flute_model)
                QApplication.processEvents()
                
                if parts_found and flute_item is not None:
                    logger.debug(f"Encontradas {len(parts_found)} piezas para {flute_name}")
                    for part_name in sorted(parts_found):
                        part_item = QTreeWidgetItem(flute_item, [part_name])
                        part_item.setData(0, Qt.UserRole, {
                            'type': 'part',
                            'flute': flute_data.flute_model,
                            'part': part_name
                        })
                    QApplication.processEvents()
                
                logger.info(f"✓ {flute_name} cargada exitosamente")
                
            except Exception as e:
                logger.error(f"Error cargando {flute_name}: {e}", exc_info=True)
                QMessageBox.warning(
                    self, "Error de Carga",
                    f"No se pudo cargar '{flute_name}':\n{str(e)}"
                )
                QApplication.processEvents()  # Mantener UI responsiva
        
        QApplication.restoreOverrideCursor()
        
        # Actualizar estado del botón de recálculo
        if hasattr(self, 'recalc_pf_btn'):
            self.recalc_pf_btn.setEnabled(self.save_pressure_flow_data and len(self.flute_data_list) > 0)
        
        # Actualizar selector de flautas en la pestaña de planos
        if hasattr(self, 'drawings_flute_combo'):
            self.drawings_flute_combo.clear()
            for flute_data in self.flute_data_list:
                self.drawings_flute_combo.addItem(flute_data.flute_model)
        
        # Actualizar selector de flautas en la pestaña de G-code
        if hasattr(self, 'gcode_flute_combo'):
            self.gcode_flute_combo.clear()
            for flute_data in self.flute_data_list:
                self.gcode_flute_combo.addItem(flute_data.flute_model)
        
        if self.flute_data_list:
            # Calcular finger_frequencies automáticamente si no están disponibles
            self._ensure_finger_frequencies()
            
            # Verificar finger_frequencies antes de crear analizador
            for flute_data in self.flute_data_list:
                if not hasattr(flute_data, 'finger_frequencies') or not flute_data.finger_frequencies:
                    logger.warning(f"Flauta {flute_data.flute_model} no tiene finger_frequencies después del cálculo automático.")
                else:
                    logger.info(f"Flauta {flute_data.flute_model} tiene {len(flute_data.finger_frequencies)} finger_frequencies: {list(flute_data.finger_frequencies.keys())}")
                    # Mostrar algunos valores de ejemplo
                    sample_notes = list(flute_data.finger_frequencies.keys())[:3]
                    for note in sample_notes:
                        logger.info(f"  {note}: {flute_data.finger_frequencies[note]:.2f} Hz")
            
            # Crear analizador
            self.analyzer = FluteAnalyzer(self.flute_data_list)
            logger.info(f"FluteAnalyzer creado: {len(self.analyzer.acoustic_analysis_list)} flautas, {len(self.analyzer.finger_frequencies_map)} con finger_frequencies en el mapa")
            if self.analyzer.finger_frequencies_map:
                for flute_name, freq_dict in self.analyzer.finger_frequencies_map.items():
                    logger.info(f"  {flute_name}: {len(freq_dict)} frecuencias - {list(freq_dict.keys())}")
            
            # Actualizar visualizaciones
            self._update_all_plots()
            
            # No mostrar pop-up de éxito, solo mostrar errores
            logger.info(f"Carga completa: {len(self.flute_data_list)} flautas cargadas exitosamente")
        else:
            # Solo mostrar pop-up cuando hay un error (no se cargó ninguna flauta)
            QMessageBox.warning(self, "Sin Datos", "No se pudo cargar ninguna flauta.")
    
    def _scan_3d_files_for_flute(self, flute_dir: Path, flute_name: str) -> List[str]:
        """Escanea archivos 3D para una flauta (sin generar sólidos todavía)."""
        if not CADQUERY_AVAILABLE:
            return []
        
        part_files = defaultdict(dict)
        
        for file_path in flute_dir.glob("*.json"):
            filename = file_path.name
            part_name = filename.replace(".json", "").replace("_external", "")
            
            if "external" in filename:
                part_files[part_name]['external'] = file_path
            else:
                part_files[part_name]['internal'] = file_path
        
        if not part_files:
            return []
        
        # Solo guardar las rutas, no generar los sólidos todavía
        self.flutes_3d_data[flute_name] = {}
        parts_found = []
        
        for part_name, files in part_files.items():
            if 'internal' in files and 'external' in files:
                self.flutes_3d_data[flute_name][part_name] = {
                    'files': files,
                    'solid': None,  # Se genera cuando se necesite
                    'loaded': False
                }
                parts_found.append(part_name)
        
        return parts_found
    
    def _load_3d_solid_for_part(self, flute_name: str, part_name: str):
        """Carga el sólido 3D de una parte específica (lazy loading)."""
        if flute_name not in self.flutes_3d_data:
            return None
        
        if part_name not in self.flutes_3d_data[flute_name]:
            return None
        
        part_info = self.flutes_3d_data[flute_name][part_name]
        
        # Si ya está cargado, retornar
        if part_info.get('loaded') and part_info.get('solid'):
            return part_info['solid']
        
        # Cargar y generar sólido
        try:
            files = part_info['files']
            
            # Verificar que los archivos existan
            if 'internal' not in files or not files['internal'].exists():
                logger.error(f"Archivo interno no encontrado para {flute_name}/{part_name}")
                return None
            
            if 'external' not in files or not files['external'].exists():
                logger.warning(f"Archivo externo no encontrado para {flute_name}/{part_name}, usando geometría paramétrica")
                # Intentar cargar desde FluteDataDB si está disponible
                for flute_data in self.flute_data_list:
                    if flute_data.flute_model == flute_name:
                        # Usar geometría externa generada paramétricamente
                        if hasattr(flute_data, 'external_geometry') and part_name in flute_data.external_geometry:
                            external_measurements = flute_data.external_geometry[part_name]
                            # Convertir a formato esperado (de external_diameter a diameter si es necesario)
                            formatted_measurements = []
                            for m in external_measurements:
                                if isinstance(m, dict):
                                    formatted_m = m.copy()
                                    if 'external_diameter' in formatted_m and 'diameter' not in formatted_m:
                                        formatted_m['diameter'] = formatted_m.pop('external_diameter')
                                    formatted_measurements.append(formatted_m)
                            external_data = {'measurements': formatted_measurements}
                        else:
                            logger.error(f"No hay geometría externa disponible para {flute_name}/{part_name}")
                            return None
                        break
                else:
                    logger.error(f"Flauta {flute_name} no encontrada en datos cargados")
                    return None
            else:
                with open(files['external'], 'r', encoding='utf-8') as f:
                    external_data = json.load(f)
                
                # Convertir formato si es necesario (de external_diameter a diameter)
                if 'measurements' in external_data:
                    for m in external_data['measurements']:
                        if 'external_diameter' in m and 'diameter' not in m:
                            m['diameter'] = m.pop('external_diameter')
            
            with open(files['internal'], 'r', encoding='utf-8') as f:
                internal_data = json.load(f)
            
            # Verificar que los datos tengan la estructura esperada
            if 'measurements' not in internal_data:
                logger.error(f"Datos internos de {flute_name}/{part_name} no tienen 'measurements'")
                return None
            
            if 'measurements' not in external_data:
                logger.error(f"Datos externos de {flute_name}/{part_name} no tienen 'measurements'")
                return None
            
            # Verificar que haya mediciones
            if not internal_data['measurements']:
                logger.error(f"No hay mediciones internas para {flute_name}/{part_name}")
                return None
            
            if not external_data['measurements']:
                logger.error(f"No hay mediciones externas para {flute_name}/{part_name}")
                return None
            
            assembler = FluteAssembler3D(internal_data, external_data)
            solid = assembler.assemble()
            
            if solid:
                part_info['solid'] = solid
                part_info['internal'] = internal_data
                part_info['external'] = external_data
                part_info['loaded'] = True
                logger.info(f"Sólido 3D generado: {flute_name}/{part_name}")
                return solid
            else:
                logger.error(f"No se pudo ensamblar sólido 3D para {flute_name}/{part_name}")
        except Exception as e:
            logger.error(f"Error generando sólido 3D {flute_name}/{part_name}: {e}", exc_info=True)
        
        return None
    
    def _on_tree_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Maneja clics en el árbol de flautas."""
        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return
        
        item_type = item_data.get('type')
        
        if item_type == 'flute':
            flute_name = item_data.get('name')
            logger.info(f"Seleccionada flauta completa: {flute_name}")
            self._show_complete_flute_3d(flute_name)
        
        elif item_type == 'part':
            flute_name = item_data.get('flute')
            part_name = item_data.get('part')
            logger.info(f"Seleccionada pieza: {flute_name}/{part_name}")
            self._show_single_part_3d(flute_name, part_name)
    
    def _draw_holes_on_physical_assembly(self, ax, flute_ops, color):
        """Dibuja los agujeros en el ensamblaje físico usando el mismo método que gui_db.py."""
        try:
            # Calcular posiciones físicas absolutas de agujeros
            # Usar EXACTAMENTE la misma lógica que plot_physical_assembly para consistencia
            part_physical_starts = {}
            current_physical_plot_start_abs = 0.0
            next_part_connection_point_abs = 0.0
            
            for idx_part, part_name in enumerate(FLUTE_PARTS_ORDER):
                part_data = flute_ops.flute_data.data.get(part_name, {})
                total_length = part_data.get("Total length", 0.0)
                mortise_length = part_data.get("Mortise length", 0.0)
                
                # Misma lógica exacta que plot_physical_assembly
                if idx_part == 0:  # Headjoint
                    current_physical_plot_start_abs = 0.0
                    part_physical_starts[part_name] = current_physical_plot_start_abs
                    # Para Headjoint, next_part_connection_point_abs se calcula después del socket
                    hj_total_length = total_length
                    hj_mortise_length = mortise_length
                    next_part_connection_point_abs = hj_total_length - hj_mortise_length
                elif idx_part == 1:  # Body (Left) - se inserta en Headjoint
                    # Left comienza donde termina el cuerpo de Headjoint (antes del socket de HJ)
                    hj_data = flute_ops.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
                    hj_total_length = hj_data.get("Total length", 0.0)
                    hj_mortise_length = hj_data.get("Mortise length", 0.0)
                    current_physical_plot_start_abs = hj_total_length - hj_mortise_length
                    part_physical_starts[part_name] = current_physical_plot_start_abs
                    next_part_connection_point_abs = current_physical_plot_start_abs + total_length
                else:  # Foot (Right) - se inserta en la anterior
                    # El inicio físico de Right/Foot es el final físico de Left/Right menos el socket de Right/Foot
                    current_physical_plot_start_abs = next_part_connection_point_abs - mortise_length
                    part_physical_starts[part_name] = current_physical_plot_start_abs
                    next_part_connection_point_abs = current_physical_plot_start_abs + total_length
            
            # Calcular posición Y para los agujeros (similar a gui_db.py)
            y_pos_holes = 0.0
            
            # Dibujar agujeros usando ax.plot() con marker='o' (como en gui_db.py)
            for part_name in FLUTE_PARTS_ORDER:
                part_data = flute_ops.flute_data.data.get(part_name, {})
                part_start_abs = part_physical_starts.get(part_name, 0.0)
                hole_positions = part_data.get("Holes position", [])
                hole_diameters = part_data.get("Holes diameter", [])
                
                if hole_positions and hole_diameters:
                    for pos_rel_mm, diam_mm in zip(hole_positions, hole_diameters):
                        abs_pos_mm = part_start_abs + pos_rel_mm
                        
                        # Usar ax.plot() con marker='o' como en gui_db.py
                        marker_size_scaled = max(diam_mm * 2.0, 4)
                        ax.plot(abs_pos_mm, y_pos_holes, marker='o',
                               color=color, markersize=marker_size_scaled,
                               linestyle='None', alpha=0.7)
        except Exception as e:
            logger.error(f"Error dibujando agujeros en ensamblaje físico: {e}")
    
    def _draw_holes_on_acoustic_profile(self, ax, flute_ops, stopper_pos, color):
        """Dibuja los agujeros en el perfil acústico usando el mismo método que gui_db.py."""
        try:
            # Calcular posiciones físicas absolutas de agujeros
            # Usar la misma lógica que plot_physical_assembly para consistencia
            part_physical_starts = {}
            current_physical_plot_start_abs = 0.0
            next_part_connection_point_abs = 0.0
            
            for idx_part, part_name in enumerate(FLUTE_PARTS_ORDER):
                part_data = flute_ops.flute_data.data.get(part_name, {})
                total_length = part_data.get("Total length", 0.0)
                mortise_length = part_data.get("Mortise length", 0.0)
                
                # Misma lógica que plot_physical_assembly
                if idx_part == 0:  # Headjoint
                    part_physical_starts[part_name] = 0.0
                    next_part_connection_point_abs = total_length - mortise_length
                elif idx_part == 1:  # Body (Left)
                    part_physical_starts[part_name] = next_part_connection_point_abs
                    next_part_connection_point_abs = part_physical_starts[part_name] + total_length
                else:  # Foot (Right)
                    part_physical_starts[part_name] = next_part_connection_point_abs - mortise_length
                    next_part_connection_point_abs = part_physical_starts[part_name] + total_length
            
            # Calcular posición Y para los agujeros (similar a gui_db.py)
            # En gui_db.py usan: y_pos_holes_acoustic = (min_diam_all_acoustic_profiles if min_diam_all_acoustic_profiles != float('inf') else 10) - (3 + i * 1.5)
            # Para simplificar, usamos y=0 como en la versión actual, pero podríamos ajustarlo
            y_pos_holes = 0.0
            
            # Dibujar agujeros con offset acústico usando ax.plot() con marker='o' (como en gui_db.py)
            # Esto hace que los círculos se vean circulares automáticamente
            for part_name in FLUTE_PARTS_ORDER:
                part_data = flute_ops.flute_data.data.get(part_name, {})
                part_start_abs = part_physical_starts.get(part_name, 0.0)
                hole_positions = part_data.get("Holes position", [])
                hole_diameters = part_data.get("Holes diameter", [])
                
                if hole_positions and hole_diameters:
                    for pos_rel_mm, diam_mm in zip(hole_positions, hole_diameters):
                        abs_pos_mm = part_start_abs + pos_rel_mm
                        # Aplicar offset acústico (restar posición del corcho)
                        acoustic_pos_mm = abs_pos_mm - stopper_pos
                        
                        # Usar ax.plot() con marker='o' como en gui_db.py
                        # Esto hace que los círculos se vean circulares automáticamente
                        marker_size_scaled = max(diam_mm * 2.0, 4)
                        ax.plot(acoustic_pos_mm, y_pos_holes, marker='o',
                               color=color, markersize=marker_size_scaled,
                               linestyle='None', alpha=0.7)
        except Exception as e:
            logger.error(f"Error dibujando agujeros en perfil acústico: {e}")
    
    def _update_all_plots(self):
        """Actualiza todos los gráficos."""
        self._update_2d_plots()
        self._update_admittance_options()
        self._update_analysis_plots()
    
    def _update_2d_plots(self):
        """Actualiza gráficos 2D."""
        if not self.flute_ops_list:
            return
        
        # Perfil combinado
        self.profile_figure.clear()
        ax1 = self.profile_figure.add_subplot(211)
        ax2 = self.profile_figure.add_subplot(212)
        
        for i, flute_ops in enumerate(self.flute_ops_list):
            flute_model_name = flute_ops.flute_data.flute_model
            current_color = BASE_COLORS[i % len(BASE_COLORS)]
            current_style = LINESTYLES[i % len(LINESTYLES)]
            
            # Físico (max_x es el largo físico total)
            max_x = flute_ops.plot_physical_assembly(
                ax=ax1,
                plot_label_suffix="_nolegend_",
                overall_linestyle=current_style
            )
            
            # Agregar línea invisible para la leyenda con el largo físico
            if max_x is not None and max_x > 0:
                ax1.plot([], [], color=current_color, linestyle=current_style,
                        label=f"{flute_model_name} (Físico: {max_x:.1f} mm)")
            
            # Dibujar agujeros en el ensamblaje físico
            self._draw_holes_on_physical_assembly(ax1, flute_ops, current_color)
            
            # Acústico
            stopper_pos = flute_ops.flute_data.data.get(FLUTE_PARTS_ORDER[0], {}).get(
                '_calculated_stopper_absolute_position_mm', 0.0
            )
            
            # Calcular largo acústico
            acoustic_length = 0.0
            combined_measurements = flute_ops.flute_data.combined_measurements
            if combined_measurements:
                acoustic_start_abs = stopper_pos
                acoustic_end_abs = max(m['position'] for m in combined_measurements)
                acoustic_length = acoustic_end_abs - acoustic_start_abs
            
            flute_ops.plot_combined_flute_data(
                ax=ax2,
                plot_label=f"{flute_model_name} (Acústico: {acoustic_length:.1f} mm)",
                flute_color=current_color,
                flute_style=current_style,
                show_mortise_markers=True,  # Mostrar líneas punteadas de los mortises
                x_axis_origin_offset=stopper_pos
            )
            
            # Dibujar agujeros en el perfil acústico
            self._draw_holes_on_acoustic_profile(ax2, flute_ops, stopper_pos, current_color)
        
        ax1.set_title("Ensamblaje Físico")
        ax2.set_title("Perfil Acústico")
        
        # Solo añadir legends si hay elementos con label
        handles1, labels1 = ax1.get_legend_handles_labels()
        if handles1 and labels1:
            ax1.legend()
        handles2, labels2 = ax2.get_legend_handles_labels()
        if handles2 and labels2:
            ax2.legend()
        
        ax1.grid(True)
        ax2.grid(True)
        
        self.profile_figure.tight_layout()
        self.profile_canvas.draw()
        
        # Partes individuales
        self.parts_figure.clear()
        axes = []
        for i in range(len(FLUTE_PARTS_ORDER)):
            ax = self.parts_figure.add_subplot(2, 2, i+1)
            axes.append(ax)
        
        for flute_idx, flute_ops in enumerate(self.flute_ops_list):
            current_flute_color = BASE_COLORS[flute_idx % len(BASE_COLORS)]
            current_flute_style = LINESTYLES[flute_idx % len(LINESTYLES)]
            
            for part_idx, part_name in enumerate(FLUTE_PARTS_ORDER):
                if part_idx < len(axes):
                    ax_part = axes[part_idx]
                    adjusted_pos, diams = flute_ops._calculate_adjusted_positions(part_name, 0.0)
                    
                    if adjusted_pos and diams:
                        # Dibujar perfil
                        ax_part.plot(
                            adjusted_pos, diams, marker='.',
                            linestyle=current_flute_style,
                            color=current_flute_color,
                            markersize=3,
                            label=flute_ops.flute_data.flute_model
                        )
                        
                        # Calcular y mostrar largos físicos y acústicos
                        part_data = flute_ops.flute_data.data.get(part_name, {})
                        part_physical_total_length = part_data.get("Total length", 0.0)
                        part_mortise_length = part_data.get("Mortise length", 0.0)
                        
                        if part_name == FLUTE_PARTS_ORDER[0]:  # Headjoint
                            part_acoustic_length = part_physical_total_length - part_mortise_length
                        elif part_name == FLUTE_PARTS_ORDER[1]:  # Body
                            part_acoustic_length = part_physical_total_length
                        else:  # Foot
                            part_acoustic_length = part_physical_total_length - part_mortise_length
                        
                        # Mostrar texto con largos
                        text_str = f"L. Total: {part_physical_total_length:.1f} mm\nL. Acústica: {part_acoustic_length:.1f} mm"
                        ax_part.text(
                            0.02, 0.98 - (flute_idx * 0.12),
                            text_str, transform=ax_part.transAxes,
                            ha='left', va='top', fontsize=6, color=current_flute_color,
                            bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.75, ec='grey')
                        )
                        
                        # Dibujar agujeros
                        hole_positions = part_data.get("Holes position", [])
                        hole_diameters = part_data.get("Holes diameter", [])
                        side_holes = part_data.get("Side holes", [])
                        
                        # Formato 1: Holes position y Holes diameter
                        if hole_positions and hole_diameters and len(hole_positions) == len(hole_diameters):
                            min_diam = min(diams) if diams else 0
                            y_pos_for_holes = min_diam - (5 + flute_idx * 1.5)
                            
                            for h_pos, h_diam in zip(hole_positions, hole_diameters):
                                if h_pos is not None and h_diam is not None:
                                    marker_size = max(h_diam * 2.0, 4)
                                    ax_part.plot(
                                        h_pos, y_pos_for_holes,
                                        marker='o', color=current_flute_color,
                                        markersize=marker_size, linestyle='None', alpha=0.7
                                    )
                        
                        # Formato 2: Side holes
                        if side_holes:
                            min_diam = min(diams) if diams else 0
                            y_pos_for_holes = min_diam - (5 + flute_idx * 1.5)
                            
                            for hole_info in side_holes:
                                if isinstance(hole_info, dict):
                                    h_pos = hole_info.get("position", hole_info.get("Position", None))
                                    h_diam = hole_info.get("diameter", hole_info.get("Diameter", None))
                                    if h_pos is not None and h_diam is not None:
                                        marker_size = max(h_diam * 2.0, 4)
                                        ax_part.plot(
                                            h_pos, y_pos_for_holes,
                                            marker='o', color=current_flute_color,
                                            markersize=marker_size, linestyle='None', alpha=0.7
                                        )
                        
                        ax_part.set_title(part_name.capitalize(), fontsize=9)
                        ax_part.set_xlabel("Posición en parte (mm)", fontsize=8)
                        ax_part.set_ylabel("Diámetro (mm)", fontsize=8)
                        ax_part.grid(True, linestyle=':', alpha=0.5)
                        ax_part.tick_params(axis='both', which='major', labelsize=7)
        
        for ax in axes:
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                by_label = dict(zip(labels, handles))
                ax.legend(by_label.values(), by_label.keys(), loc='upper right', fontsize=7)
        
        self.parts_figure.tight_layout()
        self.parts_canvas.draw()
        
        # Vista sólido 2D - Perfil combinado
        self.profile_solid_figure.clear()
        ax_solid_combined = self.profile_solid_figure.add_subplot(111)
        
        has_solid_data = False
        for i, flute_ops in enumerate(self.flute_ops_list):
            current_color = BASE_COLORS[i % len(BASE_COLORS)]
            stopper_pos = flute_ops.flute_data.data.get(FLUTE_PARTS_ORDER[0], {}).get(
                '_calculated_stopper_absolute_position_mm', 0.0
            )
            
            result_ax = flute_ops.plot_solid_2d_view(
                ax=ax_solid_combined,
                plot_label=flute_ops.flute_data.flute_model,
                flute_color=current_color,
                x_axis_origin_offset=stopper_pos
            )
            
            if result_ax is not None:
                has_solid_data = True
        
        if not has_solid_data:
            ax_solid_combined.text(0.5, 0.5, 
                                  "No hay perfil externo disponible para las flautas cargadas.\n"
                                  "Los gráficos del sólido 2D requieren datos de perfil externo.",
                                  ha='center', va='center', transform=ax_solid_combined.transAxes,
                                  fontsize=12, color='gray')
            ax_solid_combined.set_title("Vista Sólido 2D - Perfil Combinado", fontsize=10)
        else:
            handles, labels = ax_solid_combined.get_legend_handles_labels()
            if handles:
                ax_solid_combined.legend()
        
        ax_solid_combined.grid(True, linestyle=':', alpha=0.5)
        self.profile_solid_figure.tight_layout()
        self.profile_solid_canvas.draw()
        
        # Corte axial del sólido - Perfil combinado
        self.profile_axial_figure.clear()
        ax_axial_combined = self.profile_axial_figure.add_subplot(111)
        
        has_axial_data = False
        for i, flute_ops in enumerate(self.flute_ops_list):
            current_color = BASE_COLORS[i % len(BASE_COLORS)]
            stopper_pos = flute_ops.flute_data.data.get(FLUTE_PARTS_ORDER[0], {}).get(
                '_calculated_stopper_absolute_position_mm', 0.0
            )
            
            result_ax = flute_ops.plot_axial_cut_2d(
                ax=ax_axial_combined,
                plot_label=flute_ops.flute_data.flute_model,
                internal_color='red',
                external_color='blue',
                hole_color='gold',
                x_axis_origin_offset=stopper_pos,
                cone_angle_deg=5.0
            )
            
            if result_ax is not None:
                has_axial_data = True
        
        if not has_axial_data:
            ax_axial_combined.text(0.5, 0.5, 
                                  "No hay datos suficientes para el corte axial.\n"
                                  "Se requieren perfiles interno y externo.",
                                  ha='center', va='center', transform=ax_axial_combined.transAxes,
                                  fontsize=12, color='gray')
            ax_axial_combined.set_title("Corte Axial del Sólido - Perfil Combinado", fontsize=10)
        else:
            handles, labels = ax_axial_combined.get_legend_handles_labels()
            if handles:
                ax_axial_combined.legend()
        
        ax_axial_combined.grid(True, linestyle=':', alpha=0.5)
        self.profile_axial_figure.tight_layout()
        self.profile_axial_canvas.draw()
        
        # Vista sólido 2D - Partes individuales
        self.parts_solid_figure.clear()
        axes_solid = []
        for i in range(len(FLUTE_PARTS_ORDER)):
            ax = self.parts_solid_figure.add_subplot(2, 2, i+1)
            axes_solid.append(ax)
        
        for flute_idx, flute_ops in enumerate(self.flute_ops_list):
            current_flute_color = BASE_COLORS[flute_idx % len(BASE_COLORS)]
            
            for part_idx, part_name in enumerate(FLUTE_PARTS_ORDER):
                if part_idx < len(axes_solid):
                    ax_part_solid = axes_solid[part_idx]
                    
                    result_ax = flute_ops.plot_individual_part_solid_2d(
                        part_name=part_name,
                        ax=ax_part_solid,
                        plot_label=flute_ops.flute_data.flute_model,
                        part_color=current_flute_color
                    )
                    
                    if result_ax is None and flute_idx == 0:
                        # Solo mostrar mensaje en la primera flauta si no hay datos
                        ax_part_solid.text(0.5, 0.5,
                                          f"No hay perfil externo para {part_name}",
                                          ha='center', va='center',
                                          transform=ax_part_solid.transAxes,
                                          fontsize=9, color='gray')
                        ax_part_solid.set_title(f"{part_name.capitalize()} - Vista Sólido 2D", fontsize=9)
                        ax_part_solid.grid(True, linestyle=':', alpha=0.5)
        
        for ax in axes_solid:
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                by_label = dict(zip(labels, handles))
                ax.legend(by_label.values(), by_label.keys(), loc='upper right', fontsize=7)
        
        self.parts_solid_figure.tight_layout()
        self.parts_solid_canvas.draw()
        
        # Corte axial - Partes individuales
        self.parts_axial_figure.clear()
        axes_axial = []
        for i in range(len(FLUTE_PARTS_ORDER)):
            ax = self.parts_axial_figure.add_subplot(2, 2, i+1)
            axes_axial.append(ax)
        
        for flute_idx, flute_ops in enumerate(self.flute_ops_list):
            current_flute_color = BASE_COLORS[flute_idx % len(BASE_COLORS)]
            
            for part_idx, part_name in enumerate(FLUTE_PARTS_ORDER):
                if part_idx < len(axes_axial):
                    ax_part_axial = axes_axial[part_idx]
                    
                    result_ax = flute_ops.plot_individual_part_axial_cut_2d(
                        part_name=part_name,
                        ax=ax_part_axial,
                        plot_label=flute_ops.flute_data.flute_model,
                        internal_color='red',
                        external_color='blue',
                        hole_color='gold'
                    )
                    
                    if result_ax is None and flute_idx == 0:
                        # Solo mostrar mensaje en la primera flauta si no hay datos
                        ax_part_axial.text(0.5, 0.5,
                                          f"No hay datos suficientes para corte axial de {part_name}",
                                          ha='center', va='center',
                                          transform=ax_part_axial.transAxes,
                                          fontsize=9, color='gray')
                        ax_part_axial.set_title(f"{part_name.capitalize()} - Corte Axial", fontsize=9)
                        ax_part_axial.grid(True, linestyle=':', alpha=0.5)
        
        for ax in axes_axial:
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                by_label = dict(zip(labels, handles))
                ax.legend(by_label.values(), by_label.keys(), loc='upper right', fontsize=7)
        
        self.parts_axial_figure.tight_layout()
        self.parts_axial_canvas.draw()
    
    def _update_admittance_options(self):
        """Actualiza opciones de notas en admitancia."""
        if not self.flute_data_list:
            self.note_combo.clear()
            return
        
        # Obtener todas las notas disponibles
        all_notes = set()
        for flute_data in self.flute_data_list:
            if hasattr(flute_data, 'acoustic_analysis'):
                all_notes.update(flute_data.acoustic_analysis.keys())
        
        # Ordenar canónicamente
        canonical_order = ["D", "D#", "E", "F", "Fs", "G", "G#", "A", "A#", "B", "C", "Cs"]
        ordered_notes = [n for n in canonical_order if n in all_notes]
        ordered_notes.extend(sorted(list(all_notes - set(ordered_notes))))
        
        self.note_combo.clear()
        self.note_combo.addItems(ordered_notes)
        
        if ordered_notes:
            self._update_admittance_plot()
    
    def _update_admittance_plot(self):
        """Actualiza el gráfico de admitancia."""
        note = self.note_combo.currentText()
        if not note or not self.flute_data_list:
            return
        
        acoustic_list = [(fd.acoustic_analysis, fd.flute_model) for fd in self.flute_data_list]
        measurements_list = [(fd.combined_measurements, fd.flute_model) for fd in self.flute_data_list]
        
        # Crear nueva figura, pasando los objetos FluteData completos para que pueda dibujar agujeros
        temp_fig = FluteOperations.plot_individual_admittance_analysis(
            acoustic_list, measurements_list, note,
            flute_data_list=self.flute_data_list  # Pasar objetos completos para acceso a data y fing_chart_file_path
        )
        
        # Copiar a nuestra figura (incluyendo todos los elementos gráficos, no solo líneas)
        self.admittance_figure.clear()
        num_subplots = len(temp_fig.axes)
        for i, ax_src in enumerate(temp_fig.axes):
            ax_dst = self.admittance_figure.add_subplot(num_subplots, 1, i+1)
            
            # Copiar líneas
            for line in ax_src.lines:
                ax_dst.plot(
                    line.get_xdata(), line.get_ydata(),
                    color=line.get_color(), linestyle=line.get_linestyle(),
                    linewidth=line.get_linewidth(), label=line.get_label(),
                    alpha=line.get_alpha() if line.get_alpha() is not None else 1.0
                )
            
            # Copiar patches (círculos de agujeros, rellenos, etc.)
            for patch in ax_src.patches:
                from matplotlib.patches import Circle, FancyBboxPatch, Patch
                try:
                    if isinstance(patch, Circle):
                        # Obtener propiedades del círculo original
                        center = patch.center
                        radius = patch.radius
                        facecolor = patch.get_facecolor()
                        edgecolor = patch.get_edgecolor()
                        linewidth = patch.get_linewidth()
                        alpha = patch.get_alpha() if patch.get_alpha() is not None else 1.0
                        
                        # Crear nuevo círculo en el eje destino
                        circle = Circle(
                            center, radius,
                            facecolor=facecolor,
                            edgecolor=edgecolor,
                            linewidth=linewidth,
                            alpha=alpha,
                            transform=ax_dst.transData  # Usar transformación de datos
                        )
                        ax_dst.add_patch(circle)
                    else:
                        # Para otros tipos de patches, intentar recrear
                        # Esto es más complejo, así que por ahora solo intentamos con Circle
                        pass
                except Exception as e:
                    logger.debug(f"Error copiando patch: {e}")
                    pass  # Si no se puede copiar, continuar
            
            # Copiar textos (etiquetas de agujeros, etc.)
            for text in ax_src.texts:
                ax_dst.text(
                    text.get_position()[0], text.get_position()[1],
                    text.get_text(),
                    fontsize=text.get_fontsize(),
                    color=text.get_color(),
                    ha=text.get_ha(),
                    va=text.get_va(),
                    weight=text.get_weight(),
                    transform=ax_dst.transData if text.get_transform() == ax_src.transData else ax_dst.transAxes
                )
            
            # Copiar vlines (líneas verticales de armónicos)
            for collection in ax_src.collections:
                # Las vlines se almacenan como LineCollection
                try:
                    segments = collection.get_segments()
                    colors = collection.get_colors()
                    linestyles = collection.get_linestyles()
                    linewidths = collection.get_linewidths()
                    for seg, color, ls, lw in zip(segments, colors, linestyles, linewidths):
                        ax_dst.plot(seg[:, 0], seg[:, 1], color=color, linestyle=ls, linewidth=lw, alpha=collection.get_alpha())
                except:
                    pass
            
            ax_dst.set_xlabel(ax_src.get_xlabel())
            ax_dst.set_ylabel(ax_src.get_ylabel())
            ax_dst.set_title(ax_src.get_title())
            ax_dst.set_xlim(ax_src.get_xlim())
            
            # Para el gráfico de geometría (el último), ajustar ylim basado en los datos
            if 'Geometría' in ax_src.get_title():
                # Obtener los datos de todas las líneas para calcular un ylim apropiado
                all_y_data = []
                for line in ax_dst.lines:
                    y_data = line.get_ydata()
                    if len(y_data) > 0:
                        all_y_data.extend(y_data)
                
                if all_y_data:
                    y_min, y_max = min(all_y_data), max(all_y_data)
                    y_range = y_max - y_min
                    # Agregar un margen del 20% arriba y 10% abajo para los agujeros
                    margin_bottom = y_range * 0.1
                    margin_top = y_range * 0.2
                    ax_dst.set_ylim(y_min - margin_bottom, y_max + margin_top)
                else:
                    # Si no hay datos, usar el ylim original
                    ax_dst.set_ylim(ax_src.get_ylim())
            else:
                # Para otros gráficos, usar el ylim original
                ax_dst.set_ylim(ax_src.get_ylim())
            
            ax_dst.grid(True)
            
            # Copiar leyenda si existe
            legend_src = ax_src.get_legend()
            if legend_src:
                handles, labels = ax_src.get_legend_handles_labels()
                if handles:
                    # Obtener la ubicación de la leyenda original
                    try:
                        # Intentar obtener el loc de la leyenda original
                        # _loc es el atributo interno que almacena la ubicación
                        loc = getattr(legend_src, '_loc', None)
                        # Si loc es None o no válido, usar 'best' como fallback
                        if loc is None or not isinstance(loc, (str, int)):
                            loc = 'best'
                    except:
                        loc = 'best'
                    ax_dst.legend(handles, labels, loc=loc)
        
        plt.close(temp_fig)
        
        # Aplicar tight_layout con parámetros específicos para evitar redimensionamiento
        try:
            self.admittance_figure.tight_layout(pad=1.5, h_pad=1.0)
        except Exception as e:
            logger.debug(f"No se pudo aplicar tight_layout: {e}")
        
        # Forzar redibujo del canvas
        self.admittance_canvas.draw_idle()
    
    def _on_pressure_flow_saving_changed(self, state: int):
        """Maneja el cambio en el checkbox de guardado de pressure/flow data."""
        self.save_pressure_flow_data = (state == Qt.Checked)
        logger.info(f"Preferencia de guardado de pressure/flow data: {self.save_pressure_flow_data}")
        
        # Habilitar/deshabilitar botón de recálculo
        if hasattr(self, 'recalc_pf_btn'):
            self.recalc_pf_btn.setEnabled(self.save_pressure_flow_data and len(self.flute_data_list) > 0)
        
        # Mostrar mensaje informativo
        if self.save_pressure_flow_data:
            QMessageBox.information(
                self,
                "Preferencia Actualizada",
                "Los datos de presión y flujo se guardarán en la BD para las nuevas flautas que se carguen.\n\n"
                "Para visualizar presión/flujo en flautas ya cargadas:\n"
                "1. Usa el botón '🔄 Recalcular con P/F' en esta pestaña, o\n"
                "2. Recarga las flautas manualmente."
            )
    
    def _recalculate_with_pressure_flow(self):
        """Recalcula las flautas cargadas con datos de presión/flujo."""
        if not self.save_pressure_flow_data:
            QMessageBox.warning(
                self,
                "Checkbox Desmarcado",
                "Por favor marca primero el checkbox 'Guardar datos de presión/flujo en BD'."
            )
            return
        
        if not self.flute_data_list:
            QMessageBox.information(
                self,
                "Sin Flautas Cargadas",
                "No hay flautas cargadas para recalcular."
            )
            return
        
        reply = QMessageBox.question(
            self,
            "Recalcular con Presión/Flujo",
            f"¿Recalcular {len(self.flute_data_list)} flauta(s) cargada(s) con datos de presión/flujo?\n\n"
            "Esto puede tardar varios minutos y aumentará el tamaño de la base de datos.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for idx, flute_data in enumerate(self.flute_data_list):
                if not isinstance(flute_data, FluteDataDB):
                    continue
                
                logger.info(f"Recalculando {flute_data.flute_model} ({idx+1}/{len(self.flute_data_list)})...")
                QApplication.processEvents()
                
                # Forzar recálculo con include_pressure_flow=True
                flute_data.include_pressure_flow = True
                flute_data.force_recalculate = True
                
                # Recalcular análisis acústico
                try:
                    flute_data._compute_and_save_acoustic_analysis(
                        temperature=20.0,  # Usar valores por defecto
                        la_frequency=415.0
                    )
                    logger.info(f"✓ {flute_data.flute_model} recalculada exitosamente")
                except Exception as e:
                    logger.error(f"Error recalculando {flute_data.flute_model}: {e}", exc_info=True)
                    QMessageBox.warning(
                        self,
                        "Error de Recálculo",
                        f"Error recalculando {flute_data.flute_model}:\n{e}"
                    )
                
                QApplication.processEvents()
            
            # Actualizar gráficos
            self._update_admittance_plot()
            
            QMessageBox.information(
                self,
                "Recálculo Completado",
                f"Se recalcularon {len(self.flute_data_list)} flauta(s) con datos de presión/flujo.\n\n"
                "Los gráficos se han actualizado automáticamente."
            )
        finally:
            QApplication.restoreOverrideCursor()
    
    def _calculate_finger_frequencies(self, la_frequency: float) -> Dict[str, float]:
        """
        Calcula finger_frequencies automáticamente basándose en el diapasón.
        
        Args:
            la_frequency: Frecuencia de referencia para A (en Hz)
            
        Returns:
            Diccionario con las frecuencias para cada nota
        """
        semitone_mapping = {"D": -7, "E": -5, "Fs": -3, "G": -2, "A": 0, "B": 2, "Cs": 4}
        finger_frequencies = {}
        
        for note, semitones in semitone_mapping.items():
            frequency = la_frequency * (2 ** (semitones / 12.0))
            finger_frequencies[note] = frequency
            logger.debug(f"  {note}: {frequency:.2f} Hz (semitones: {semitones})")
        
        logger.info(f"Calculados {len(finger_frequencies)} finger_frequencies para diapasón {la_frequency} Hz")
        return finger_frequencies
    
    def _ensure_finger_frequencies(self):
        """Asegura que todas las flautas tengan finger_frequencies calculados."""
        for flute_data in self.flute_data_list:
            # Verificar si finger_frequencies existe y tiene datos válidos
            needs_calculation = False
            
            if not hasattr(flute_data, 'finger_frequencies'):
                needs_calculation = True
                logger.info(f"Flauta {flute_data.flute_model} no tiene atributo finger_frequencies")
            elif not isinstance(flute_data.finger_frequencies, dict):
                needs_calculation = True
                logger.info(f"Flauta {flute_data.flute_model} tiene finger_frequencies de tipo incorrecto: {type(flute_data.finger_frequencies)}")
            elif len(flute_data.finger_frequencies) == 0:
                needs_calculation = True
                logger.info(f"Flauta {flute_data.flute_model} tiene finger_frequencies vacío (0 elementos)")
            else:
                # Verificar que tenga al menos algunas notas comunes
                expected_notes = {"D", "E", "Fs", "G", "A", "B", "Cs"}
                has_expected_notes = any(note in flute_data.finger_frequencies for note in expected_notes)
                if not has_expected_notes:
                    needs_calculation = True
                    logger.info(f"Flauta {flute_data.flute_model} tiene finger_frequencies pero sin notas esperadas: {list(flute_data.finger_frequencies.keys())}")
            
            if needs_calculation:
                # Calcular automáticamente usando el diapasón actual
                flute_data.finger_frequencies = self._calculate_finger_frequencies(self.la_frequency)
                logger.info(f"✓ Calculados finger_frequencies automáticamente para {flute_data.flute_model} con diapasón {self.la_frequency} Hz: {list(flute_data.finger_frequencies.keys())}")
            else:
                logger.info(f"Flauta {flute_data.flute_model} ya tiene finger_frequencies válidos: {list(flute_data.finger_frequencies.keys())}")
    
    def _on_diapason_changed(self, value: float):
        """Se llama cuando se cambia el diapasón."""
        self.la_frequency = value
        logger.info(f"Diapasón cambiado a {value} Hz")
        
        # Recalcular finger_frequencies para todas las flautas
        if self.flute_data_list:
            for flute_data in self.flute_data_list:
                flute_data.finger_frequencies = self._calculate_finger_frequencies(self.la_frequency)
            
            # Recrear analizador con los nuevos finger_frequencies
            if self.analyzer:
                self.analyzer = FluteAnalyzer(self.flute_data_list)
                
                # Actualizar solo los gráficos de análisis (MOC y B_I_ESPE)
                self._update_analysis_plots()
            else:
                # Si no hay analizador, crearlo
                self.analyzer = FluteAnalyzer(self.flute_data_list)
                self._update_analysis_plots()
    
    def _update_analysis_plots(self):
        """Actualiza gráficos de análisis."""
        if not self.analyzer:
            return
        
        # 1. Resumen (Dashboard)
        self._update_summary_dashboard()
        
        # 2. Inharmonicidad
        fig_inharm = self.analyzer.plot_inharmonicity()
        self.inharm_figure.clear()
        for i, ax_src in enumerate(fig_inharm.axes):
            ax_dst = self.inharm_figure.add_subplot(1, 1, i+1)
            for line in ax_src.lines:
                ax_dst.plot(line.get_xdata(), line.get_ydata(), 
                           color=line.get_color(), label=line.get_label())
            ax_dst.set_xlabel(ax_src.get_xlabel())
            ax_dst.set_ylabel(ax_src.get_ylabel())
            ax_dst.set_title(ax_src.get_title())
            
            # Copiar configuración de ejes X (notas)
            ax_dst.set_xticks(ax_src.get_xticks())
            ax_dst.set_xticklabels(ax_src.get_xticklabels(), rotation=45, ha='right')
            ax_dst.set_xlim(ax_src.get_xlim())
            ax_dst.set_ylim(ax_src.get_ylim())
            
            # Solo añadir legend si hay elementos con label válido
            handles, labels = ax_dst.get_legend_handles_labels()
            if handles and labels and any(not label.startswith('_') for label in labels):
                ax_dst.legend()
            ax_dst.grid(True)
        plt.close(fig_inharm)
        self.inharm_canvas.draw()
        
        # 3. Frecuencias de Resonancia
        reference_pitch = self.la_frequency_spinbox.value()
        fig_resonance = self.analyzer.plot_resonance_frequencies(reference_pitch=reference_pitch)
        self._copy_figure_to_canvas(fig_resonance, self.resonance_figure, self.resonance_canvas)
        plt.close(fig_resonance)
        
        # MOC
        fig_moc = self.analyzer.plot_moc()
        self.moc_figure.clear()
        logger.debug(f"MOC: figura tiene {len(fig_moc.axes)} ejes")
        for i, ax_src in enumerate(fig_moc.axes):
            ax_dst = self.moc_figure.add_subplot(1, 1, i+1)
            
            logger.debug(f"MOC: eje {i} tiene {len(ax_src.lines)} líneas")
            
            # Verificar si hay datos válidos
            has_valid_data = False
            
            # Copiar todas las líneas con sus propiedades completas
            for line_idx, line in enumerate(ax_src.lines):
                xdata = line.get_xdata()
                ydata = line.get_ydata()
                
                # Convertir a arrays de numpy si son listas
                if not isinstance(xdata, np.ndarray):
                    xdata = np.array(xdata)
                if not isinstance(ydata, np.ndarray):
                    ydata = np.array(ydata)
                
                logger.debug(f"MOC: línea {line_idx}: xdata.shape={xdata.shape}, ydata.shape={ydata.shape}, label={line.get_label()}")
                
                # Filtrar NaN
                valid_mask = ~(np.isnan(xdata) | np.isnan(ydata))
                if np.any(valid_mask):
                    has_valid_data = True
                    xdata_valid = xdata[valid_mask]
                    ydata_valid = ydata[valid_mask]
                    ax_dst.plot(
                        xdata_valid, ydata_valid,
                        color=line.get_color(),
                        linestyle=line.get_linestyle(),
                        marker=line.get_marker(),
                        markersize=line.get_markersize(),
                        markerfacecolor=line.get_markerfacecolor(),
                        markeredgecolor=line.get_markeredgecolor(),
                        markeredgewidth=line.get_markeredgewidth(),
                        alpha=line.get_alpha(),
                        label=line.get_label(),
                        linewidth=line.get_linewidth()
                    )
                else:
                    logger.warning(f"MOC: línea {line_idx} no tiene datos válidos (todos NaN)")
            
            # Si no hay datos válidos, mostrar mensaje
            if not has_valid_data:
                ax_dst.text(0.5, 0.5, 
                           "No hay datos disponibles para MOC.\n\n"
                           "Los gráficos MOC requieren 'finger_frequencies'\n"
                           "en los datos de la flauta.",
                           ha='center', va='center', transform=ax_dst.transAxes,
                           fontsize=12, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
                ax_dst.set_title("MOC - Sin Datos")
            
            # Copiar configuración de ejes
            ax_dst.set_xlabel(ax_src.get_xlabel())
            ax_dst.set_ylabel(ax_src.get_ylabel())
            ax_dst.set_title(ax_src.get_title())
            
            # Copiar ticks y labels del eje X
            try:
                ax_dst.set_xticks(ax_src.get_xticks())
                ticklabels_src = ax_src.xaxis.get_ticklabels()
                if ticklabels_src:
                    rotation = ticklabels_src[0].get_rotation()
                    ha = ticklabels_src[0].get_ha()
                    ax_dst.set_xticklabels(ax_src.get_xticklabels(), rotation=rotation, ha=ha)
                else:
                    ax_dst.set_xticklabels(ax_src.get_xticklabels())
            except Exception as e:
                logger.warning(f"Error copiando ticks del eje X en MOC: {e}")
                ax_dst.set_xticks(ax_src.get_xticks())
                ax_dst.set_xticklabels(ax_src.get_xticklabels(), rotation=45, ha='right')
            
            # Copiar grid
            try:
                if ax_src.gridlines:
                    grid_linestyle = ax_src.gridlines[0].get_linestyle() if ax_src.gridlines else ':'
                    grid_alpha = ax_src.gridlines[0].get_alpha() if ax_src.gridlines else 0.7
                    ax_dst.grid(True, linestyle=grid_linestyle, alpha=grid_alpha)
                else:
                    ax_dst.grid(True, linestyle=':', alpha=0.7)
            except Exception:
                ax_dst.grid(True, linestyle=':', alpha=0.7)
            
            # Copiar límites de ejes
            try:
                ax_dst.set_xlim(ax_src.get_xlim())
                ax_dst.set_ylim(ax_src.get_ylim())
            except Exception as e:
                logger.warning(f"Error copiando límites de ejes en MOC: {e}")
            
            # Copiar legend si existe
            try:
                if ax_src.legend_:
                    handles_src, labels_src = ax_src.get_legend_handles_labels()
                    if handles_src and labels_src and any(not label.startswith('_') for label in labels_src):
                        legend_loc = 'best'
                        if hasattr(ax_src.legend_, '_loc'):
                            legend_loc = ax_src.legend_._loc
                        legend_fontsize = 9
                        if ax_src.legend_.get_texts():
                            legend_fontsize = ax_src.legend_.get_texts()[0].get_fontsize()
                        ax_dst.legend(handles_src, labels_src, loc=legend_loc, fontsize=legend_fontsize)
            except Exception as e:
                logger.warning(f"Error copiando legend en MOC: {e}")
                handles, labels = ax_dst.get_legend_handles_labels()
                if handles and labels and any(not label.startswith('_') for label in labels):
                    ax_dst.legend()
        plt.close(fig_moc)
        self.moc_figure.tight_layout()
        self.moc_canvas.draw()
        
        # B_I y ESPE
        fig_bi = self.analyzer.plot_bi_espe()
        self.bi_figure.clear()
        logger.debug(f"B_I_ESPE: figura tiene {len(fig_bi.axes)} ejes")
        for i, ax_src in enumerate(fig_bi.axes):
            ax_dst = self.bi_figure.add_subplot(1, 1, i+1)
            
            logger.debug(f"B_I_ESPE: eje {i} tiene {len(ax_src.lines)} líneas")
            
            # Verificar si hay datos válidos
            has_valid_data = False
            
            # Copiar todas las líneas con sus propiedades completas
            for line_idx, line in enumerate(ax_src.lines):
                xdata = line.get_xdata()
                ydata = line.get_ydata()
                
                # Convertir a arrays de numpy si son listas
                if not isinstance(xdata, np.ndarray):
                    xdata = np.array(xdata)
                if not isinstance(ydata, np.ndarray):
                    ydata = np.array(ydata)
                
                logger.debug(f"B_I_ESPE: línea {line_idx}: xdata.shape={xdata.shape}, ydata.shape={ydata.shape}, label={line.get_label()}")
                
                # Filtrar NaN
                valid_mask = ~(np.isnan(xdata) | np.isnan(ydata))
                if np.any(valid_mask):
                    has_valid_data = True
                    xdata_valid = xdata[valid_mask]
                    ydata_valid = ydata[valid_mask]
                    
                    # Preparar parámetros de plot
                    plot_kwargs = {
                        'color': line.get_color(),
                        'linestyle': line.get_linestyle(),
                        'marker': line.get_marker(),
                        'markersize': line.get_markersize(),
                        'markerfacecolor': line.get_markerfacecolor(),
                        'markeredgecolor': line.get_markeredgecolor(),
                        'markeredgewidth': line.get_markeredgewidth(),
                        'alpha': line.get_alpha(),
                        'label': line.get_label(),
                        'linewidth': line.get_linewidth()
                    }
                    
                    # Solo agregar dashes si existe y no es None
                    if hasattr(line, 'get_dashes'):
                        dashes = line.get_dashes()
                        if dashes is not None:
                            plot_kwargs['dashes'] = dashes
                    
                    ax_dst.plot(xdata_valid, ydata_valid, **plot_kwargs)
                else:
                    logger.warning(f"B_I_ESPE: línea {line_idx} no tiene datos válidos (todos NaN)")
            
            # Si no hay datos válidos, mostrar mensaje
            if not has_valid_data:
                ax_dst.text(0.5, 0.5, 
                           "No hay datos disponibles para B_I y ESPE.\n\n"
                           "Los gráficos B_I y ESPE requieren 'finger_frequencies'\n"
                           "en los datos de la flauta.",
                           ha='center', va='center', transform=ax_dst.transAxes,
                           fontsize=12, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
                ax_dst.set_title("B_I y ESPE - Sin Datos")
            
            # Copiar líneas horizontales (axhline) - buscar líneas que sean horizontales
            for hline in ax_src.lines:
                try:
                    ydata = hline.get_ydata()
                    xdata = hline.get_xdata()
                    # Una línea horizontal tiene todos los valores de y iguales
                    if len(ydata) > 1 and len(set(ydata)) == 1 and len(set(xdata)) > 1:
                        y_val = ydata[0]
                        ax_dst.axhline(y=y_val, color=hline.get_color(), linestyle=hline.get_linestyle(),
                                      linewidth=hline.get_linewidth(), alpha=hline.get_alpha())
                except Exception:
                    pass  # Ignorar errores al copiar líneas horizontales
            
            # Copiar configuración de ejes
            ax_dst.set_xlabel(ax_src.get_xlabel())
            ax_dst.set_ylabel(ax_src.get_ylabel())
            ax_dst.set_title(ax_src.get_title())
            
            # Copiar ticks y labels del eje X
            try:
                ax_dst.set_xticks(ax_src.get_xticks())
                ticklabels_src = ax_src.xaxis.get_ticklabels()
                if ticklabels_src:
                    rotation = ticklabels_src[0].get_rotation()
                    ha = ticklabels_src[0].get_ha()
                    ax_dst.set_xticklabels(ax_src.get_xticklabels(), rotation=rotation, ha=ha)
                else:
                    ax_dst.set_xticklabels(ax_src.get_xticklabels())
            except Exception as e:
                logger.warning(f"Error copiando ticks del eje X en B_I_ESPE: {e}")
                ax_dst.set_xticks(ax_src.get_xticks())
                ax_dst.set_xticklabels(ax_src.get_xticklabels(), rotation=45, ha='right')
            
            # Copiar grid
            try:
                if ax_src.gridlines:
                    grid_linestyle = ax_src.gridlines[0].get_linestyle() if ax_src.gridlines else ':'
                    grid_alpha = ax_src.gridlines[0].get_alpha() if ax_src.gridlines else 0.7
                    ax_dst.grid(True, linestyle=grid_linestyle, alpha=grid_alpha)
                else:
                    ax_dst.grid(True, linestyle=':', alpha=0.7)
            except Exception:
                ax_dst.grid(True, linestyle=':', alpha=0.7)
            
            # Copiar límites de ejes
            try:
                ax_dst.set_xlim(ax_src.get_xlim())
                ax_dst.set_ylim(ax_src.get_ylim())
            except Exception as e:
                logger.warning(f"Error copiando límites de ejes en B_I_ESPE: {e}")
            
            # Copiar legend si existe
            try:
                if ax_src.legend_:
                    handles_src, labels_src = ax_src.get_legend_handles_labels()
                    if handles_src and labels_src and any(not label.startswith('_') for label in labels_src):
                        legend_loc = 'best'
                        if hasattr(ax_src.legend_, '_loc'):
                            legend_loc = ax_src.legend_._loc
                        legend_fontsize = 8
                        if ax_src.legend_.get_texts():
                            legend_fontsize = ax_src.legend_.get_texts()[0].get_fontsize()
                        legend_ncol = 1
                        if hasattr(ax_src.legend_, 'ncol'):
                            legend_ncol = ax_src.legend_.ncol
                        ax_dst.legend(handles_src, labels_src, loc=legend_loc, fontsize=legend_fontsize, ncol=legend_ncol)
            except Exception as e:
                logger.warning(f"Error copiando legend en B_I_ESPE: {e}")
                handles, labels = ax_dst.get_legend_handles_labels()
                if handles and labels and any(not label.startswith('_') for label in labels):
                    ax_dst.legend()
        plt.close(fig_bi)
        self.bi_figure.tight_layout()
        self.bi_canvas.draw()
        
        # 4. Altura de Picos
        fig_peak = self.analyzer.plot_peak_heights()
        self._copy_figure_to_canvas(fig_peak, self.peak_figure, self.peak_canvas)
        plt.close(fig_peak)
        
        # 5. Q-Factor
        fig_qfactor = self.analyzer.plot_q_factor()
        self._copy_figure_to_canvas(fig_qfactor, self.qfactor_figure, self.qfactor_canvas)
        plt.close(fig_qfactor)
        
        # 6. Características Tonales (Ratios + Fase)
        self.tonal_figure.clear()
        
        # Subplot 1: Ratios de armónicos
        ax1 = self.tonal_figure.add_subplot(2, 1, 1)
        fig_ratios = self.analyzer.plot_harmonic_ratios(ax=ax1)
        
        # Subplot 2: Coherencia de fase
        ax2 = self.tonal_figure.add_subplot(2, 1, 2)
        fig_phase = self.analyzer.plot_phase_coherence(ax=ax2)
        
        self.tonal_figure.tight_layout()
        self.tonal_canvas.draw()
        plt.close(fig_ratios)
        plt.close(fig_phase)
        
        # 7. Estabilidad (Pitch Stability + Cut-off)
        self.stability_figure.clear()
        
        # Subplot 1: Estabilidad de pitch
        ax1 = self.stability_figure.add_subplot(2, 1, 1)
        fig_pitch = self.analyzer.plot_pitch_stability(ax=ax1)
        
        # Subplot 2: Frecuencia de corte
        ax2 = self.stability_figure.add_subplot(2, 1, 2)
        fig_cutoff = self.analyzer.plot_cutoff_frequency(ax=ax2)
        
        self.stability_figure.tight_layout()
        self.stability_canvas.draw()
        plt.close(fig_pitch)
        plt.close(fig_cutoff)
    
    def _copy_figure_to_canvas(self, fig_src: plt.Figure, fig_dst: Figure, canvas_dst: FigureCanvas):
        """
        Helper para copiar figura de matplotlib a FigureCanvas de Qt.
        """
        fig_dst.clear()
        for i, ax_src in enumerate(fig_src.axes):
            ax_dst = fig_dst.add_subplot(1, 1, i+1)
            
            # Copiar líneas
            for line in ax_src.lines:
                ax_dst.plot(line.get_xdata(), line.get_ydata(), 
                           color=line.get_color(), 
                           linestyle=line.get_linestyle(),
                           marker=line.get_marker(),
                           markersize=line.get_markersize(),
                           label=line.get_label(),
                           linewidth=line.get_linewidth(),
                           alpha=line.get_alpha())
            
            # Copiar configuración de ejes
            ax_dst.set_xlabel(ax_src.get_xlabel())
            ax_dst.set_ylabel(ax_src.get_ylabel())
            ax_dst.set_title(ax_src.get_title())
            
            # Copiar ticks
            ax_dst.set_xticks(ax_src.get_xticks())
            ax_dst.set_xticklabels(ax_src.get_xticklabels(), rotation=45, ha='right')
            ax_dst.set_xlim(ax_src.get_xlim())
            ax_dst.set_ylim(ax_src.get_ylim())
            
            # Grid
            ax_dst.grid(True, linestyle=':', alpha=0.7)
            
            # Legend
            handles, labels = ax_dst.get_legend_handles_labels()
            if handles and labels and any(not label.startswith('_') for label in labels):
                ax_dst.legend()
        
        fig_dst.tight_layout()
        canvas_dst.draw()
    
    def _update_summary_dashboard(self):
        """Actualiza el dashboard de resumen con métricas clave y gráfico radar."""
        if not self.analyzer:
            return
        
        try:
            # Calcular todas las métricas
            inharmonicity_data = self.analyzer.calculate_inharmonicity()
            moc_data = self.analyzer.calculate_moc()
            bi_espe_data = self.analyzer.calculate_bi_espe()
            
            # Actualizar grid de métricas
            # Limpiar widgets anteriores
            for widget in self.summary_labels.values():
                widget.deleteLater()
            self.summary_labels.clear()
            
            # Agregar encabezados
            headers = ["Flauta", "Inharmonicidad", "MOC", "B_I", "ESPE"]
            for col, header in enumerate(headers):
                header_label = QLabel(f"<b>{header}</b>")
                header_label.setStyleSheet("font-weight: bold; background-color: #e0e0e0; padding: 5px;")
                self.metrics_layout.addWidget(header_label, 0, col)
                self.summary_labels[f"header_{col}"] = header_label
            
            # Agregar datos de cada flauta
            row = 1
            for flute_name in inharmonicity_data.keys():
                # Calcular promedios
                inharm_vals = [v for v in inharmonicity_data[flute_name].values() if not np.isnan(v)]
                moc_vals = [v for v in moc_data[flute_name].values() if not np.isnan(v)]
                bi_vals = [v[0] for v in bi_espe_data[flute_name].values() if not np.isnan(v[0])]
                espe_vals = [v[1] for v in bi_espe_data[flute_name].values() if not np.isnan(v[1])]
                
                avg_inharm = np.mean(inharm_vals) if inharm_vals else np.nan
                avg_moc = np.mean(moc_vals) if moc_vals else np.nan
                avg_bi = np.mean(bi_vals) if bi_vals else np.nan
                avg_espe = np.mean(espe_vals) if espe_vals else np.nan
                
                # Crear y agregar labels
                name_label = QLabel(f"<b>{flute_name}</b>")
                name_label.setStyleSheet("padding: 5px;")
                self.metrics_layout.addWidget(name_label, row, 0)
                self.summary_labels[f"{flute_name}_name"] = name_label
                
                inharm_text = f"{avg_inharm:.1f} cents" if not np.isnan(avg_inharm) else "N/A"
                inharm_label = QLabel(inharm_text)
                inharm_label.setStyleSheet("padding: 5px;")
                self.metrics_layout.addWidget(inharm_label, row, 1)
                self.summary_labels[f"{flute_name}_inharm"] = inharm_label
                
                moc_text = f"{avg_moc:.3f}" if not np.isnan(avg_moc) else "N/A"
                moc_label = QLabel(moc_text)
                moc_label.setStyleSheet("padding: 5px;")
                self.metrics_layout.addWidget(moc_label, row, 2)
                self.summary_labels[f"{flute_name}_moc"] = moc_label
                
                bi_text = f"{avg_bi:.1f} cents" if not np.isnan(avg_bi) else "N/A"
                bi_label = QLabel(bi_text)
                bi_label.setStyleSheet("padding: 5px;")
                self.metrics_layout.addWidget(bi_label, row, 3)
                self.summary_labels[f"{flute_name}_bi"] = bi_label
                
                espe_text = f"{avg_espe:.1f} cents" if not np.isnan(avg_espe) else "N/A"
                espe_label = QLabel(espe_text)
                espe_label.setStyleSheet("padding: 5px;")
                self.metrics_layout.addWidget(espe_label, row, 4)
                self.summary_labels[f"{flute_name}_espe"] = espe_label
                
                row += 1
            
            # Crear gráfico radar comparativo
            self.summary_figure.clear()
            ax = self.summary_figure.add_subplot(111, projection='polar')
            
            # Categorías para el gráfico radar
            categories = ['Inharmonicidad\n(invertida)', 'MOC', 'B_I\n(abs)', 'ESPE\n(abs)', 'Q-Factor\n(promedio)']
            num_vars = len(categories)
            
            # Ángulos para el gráfico radar
            angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
            angles += angles[:1]
            
            # Plotear para cada flauta
            from constants import BASE_COLORS
            for idx, flute_name in enumerate(inharmonicity_data.keys()):
                # Preparar valores normalizados
                inharm_vals = [abs(v) for v in inharmonicity_data[flute_name].values() if not np.isnan(v)]
                moc_vals = [v for v in moc_data[flute_name].values() if not np.isnan(v)]
                bi_vals = [abs(v[0]) for v in bi_espe_data[flute_name].values() if not np.isnan(v[0])]
                espe_vals = [abs(v[1]) for v in bi_espe_data[flute_name].values() if not np.isnan(v[1])]
                
                # Calcular promedios (invertir inharmonicidad para que menor sea mejor)
                avg_inharm_inv = 100 - np.mean(inharm_vals) if inharm_vals else 50
                avg_moc = np.mean(moc_vals) * 100 if moc_vals else 50
                avg_bi = 100 - np.mean(bi_vals) if bi_vals else 50
                avg_espe = 100 - np.mean(espe_vals) if espe_vals else 50
                avg_q = 70  # Placeholder - se calculará con datos reales
                
                values = [avg_inharm_inv, avg_moc, avg_bi, avg_espe, avg_q]
                values += values[:1]
                
                color = BASE_COLORS[idx % len(BASE_COLORS)]
                ax.plot(angles, values, 'o-', linewidth=2, label=flute_name, color=color)
                ax.fill(angles, values, alpha=0.15, color=color)
            
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(categories, size=10)
            ax.set_ylim(0, 100)
            ax.set_title("Comparación Multi-Métrica", size=14, weight='bold', pad=20)
            ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
            ax.grid(True)
            
            self.summary_figure.tight_layout()
            self.summary_canvas.draw()
            
        except Exception as e:
            logger.error(f"Error actualizando dashboard de resumen: {e}", exc_info=True)
    
    def _show_single_part_3d(self, flute_name: str, part_name: str):
        """Muestra una pieza individual en 3D."""
        if not self._3d_initialized or not self.plotter_3d:
            QMessageBox.warning(self, "Error", "Visor 3D no inicializado. Accede primero al tab 3D.")
            return
        
        if not PYVISTA_AVAILABLE:
            return
        
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            # Cargar sólido con lazy loading
            solid = self._load_3d_solid_for_part(flute_name, part_name)
            
            if not solid:
                QMessageBox.warning(self, "Error", f"No se pudo generar el modelo 3D para {part_name}")
                return
            
            # Limpiar plotter
            self.plotter_3d.clear()
            
            # Convertir CadQuery a PyVista mesh usando calidad del spin
            quality = self.quality_spin.value() if hasattr(self, 'quality_spin') else 100
            mesh = self._cq_to_pyvista(solid, quality=quality)
            
            if mesh and mesh.n_points > 0:
                self.plotter_3d.add_mesh(mesh, color='tan', show_edges=True, label=part_name)
                self.plotter_3d.reset_camera()
                self.plotter_3d.add_legend()
                self.plotter_3d.show()
                logger.info(f"Mostrando 3D: {flute_name}/{part_name}")
            else:
                QMessageBox.warning(
                    self, "Error",
                    f"No se pudo convertir el modelo a malla PyVista para {part_name}.\n"
                    "Verifica que existan los archivos JSON de geometría externa."
                )
        
        except Exception as e:
            logger.error(f"Error mostrando pieza 3D: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error mostrando modelo 3D:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()
    
    def _show_complete_flute_3d(self, flute_name: str):
        """Muestra la flauta completa ensamblada en 3D."""
        if not self._3d_initialized or not self.plotter_3d:
            QMessageBox.warning(self, "Error", "Visor 3D no inicializado. Accede primero al tab 3D.")
            return
        
        if not PYVISTA_AVAILABLE:
            return
        
        if flute_name not in self.flutes_3d_data or not self.flutes_3d_data[flute_name]:
            QMessageBox.warning(self, "Sin Datos 3D", f"No hay datos 3D disponibles para {flute_name}")
            return
        
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            # Limpiar plotter
            self.plotter_3d.clear()
            
            # Usar FLUTE_PARTS_ORDER para el orden correcto
            # El orden es: headjoint, left, right, foot (pero visualizamos de abajo hacia arriba)
            part_order = list(reversed(FLUTE_PARTS_ORDER))  # foot, right, left, headjoint
            colors = {
                'headjoint': 'burlywood',
                'left': 'wheat',
                'right': 'wheat',
                'foot': 'tan'
            }
            
            # Obtener el objeto FluteDataDB para acceder a los datos de las partes
            flute_data_obj = None
            for fd in self.flute_data_list:
                if fd.flute_model == flute_name:
                    flute_data_obj = fd
                    break
            
            if not flute_data_obj:
                logger.warning(f"No se encontró FluteDataDB para {flute_name}")
                QMessageBox.warning(self, "Error", f"No se encontraron datos para {flute_name}")
                return
            
            # Calcular posiciones físicas de inicio de cada parte usando la misma lógica que combine_measurements
            # Replicar la lógica exacta de ensamblaje acústico
            part_physical_starts = {}
            next_part_connection_point_abs = 0.0
            
            for i, part_name in enumerate(FLUTE_PARTS_ORDER):
                part_data = flute_data_obj.data.get(part_name, {})
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
                    hj_data = flute_data_obj.data.get(FLUTE_PARTS_ORDER[0], {})
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
                logger.debug(f"Parte {part_name}: inicio físico = {current_physical_start_abs:.2f}mm")
            
            # Ahora ensamblar las partes en 3D usando los offsets calculados
            # Visualizamos de abajo hacia arriba (foot, right, left, headjoint)
            meshes_added = []
            
            for part_name in part_order:
                # Verificar si la parte existe en los datos de la flauta
                if (flute_name not in self.flutes_3d_data or 
                    part_name not in self.flutes_3d_data[flute_name]):
                    logger.debug(f"Parte {part_name} no encontrada en datos 3D para {flute_name}")
                    continue
                
                # Cargar sólido
                solid = self._load_3d_solid_for_part(flute_name, part_name)
                
                if not solid:
                    logger.warning(f"No se pudo cargar sólido para {part_name}")
                    continue
                
                # Convertir a mesh usando calidad del spin
                quality = self.quality_spin.value() if hasattr(self, 'quality_spin') else 100
                mesh = self._cq_to_pyvista(solid, quality=quality)
                
                if mesh and mesh.n_points > 0:
                    # Obtener el offset físico calculado para esta parte
                    part_offset_z = part_physical_starts.get(part_name, 0.0)
                    
                    # Aplicar desplazamiento en Z para ensamblar según la lógica de combine_measurements
                    mesh.translate((0, 0, part_offset_z), inplace=True)
                    
                    # Añadir al plotter con label
                    color = colors.get(part_name, 'tan')
                    self.plotter_3d.add_mesh(mesh, color=color, show_edges=True, label=part_name)
                    meshes_added.append(part_name)
                    
                    logger.info(f"Añadida parte {part_name} en z={part_offset_z:.2f}mm (inicio físico calculado)")
            
            if not meshes_added:
                QMessageBox.warning(
                    self, "Sin Datos 3D",
                    f"No se pudieron cargar piezas 3D para {flute_name}.\n"
                    "Verifica que existan los archivos JSON de geometría externa."
                )
                return
            
            self.plotter_3d.reset_camera()
            
            # Solo agregar leyenda si hay meshes con labels
            if meshes_added:
                self.plotter_3d.add_legend()
            
            self.plotter_3d.show()
            logger.info(f"Mostrando flauta completa: {flute_name} ({len(meshes_added)} piezas)")
        
        except Exception as e:
            logger.error(f"Error mostrando flauta completa: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error mostrando flauta completa:\n{e}")
        finally:
            QApplication.restoreOverrideCursor()
    
    def _cq_to_pyvista(self, solid, quality: int = 100):
        """Convierte un sólido CadQuery a malla PyVista."""
        # Usar la función global cq_to_pyvista que ya está definida
        return cq_to_pyvista(solid, quality=quality)
    
    def _refresh_3d_view(self):
        """Refresca la vista 3D con nueva calidad."""
        if not self._3d_initialized or not self.plotter_3d:
            return
        
        # TODO: Reimplementar con el modelo actual cargado
        logger.info(f"Calidad de malla cambiada a: {self.quality_spin.value()}")
    
    def _export_stl(self):
        """Exporta el modelo 3D actual a STL."""
        if not self.flutes_3d_data:
            QMessageBox.warning(self, "Sin Datos", "No hay modelos 3D cargados.")
            return
        
        # Verificar que el árbol existe (se crea cuando se accede a la pestaña 3D)
        if not hasattr(self, 'flute_tree') or not self.flute_tree:
            QMessageBox.warning(self, "Error", "Por favor accede primero a la pestaña 3D para inicializar el árbol.")
            return
        
        # Obtener item seleccionado en el árbol
        selected_items = self.flute_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Sin Selección", "Por favor selecciona una flauta o pieza del árbol.")
            return
        
        item_data = selected_items[0].data(0, Qt.UserRole)
        if not item_data:
            return
        
        item_type = item_data.get('type')
        
        # Diálogo para elegir ubicación
        default_filename = "modelo_3d.stl"
        
        if item_type == 'part':
            flute_name = item_data.get('flute')
            part_name = item_data.get('part')
            default_filename = f"{flute_name}_{part_name}.stl"
        elif item_type == 'flute':
            flute_name = item_data.get('name')
            default_filename = f"{flute_name}_completo.stl"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exportar STL", default_filename, "STL Files (*.stl)"
        )
        
        if not file_path:
            return
        
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if item_type == 'part':
                self._export_part_stl(flute_name, part_name, file_path)
            elif item_type == 'flute':
                self._export_complete_flute_stl(flute_name, file_path)
            
            QApplication.restoreOverrideCursor()
            QMessageBox.information(
                self, "Éxito",
                f"Modelo exportado exitosamente a:\n{file_path}"
            )
        
        except Exception as e:
            QApplication.restoreOverrideCursor()
            logger.error(f"Error exportando STL: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Error exportando STL:\n{e}")
    
    def _export_part_stl(self, flute_name: str, part_name: str, file_path: str):
        """Exporta una pieza individual a STL."""
        solid = self._load_3d_solid_for_part(flute_name, part_name)
        
        if not solid:
            raise ValueError(f"No se pudo cargar el sólido para {part_name}")
        
        # Exportar directamente con CadQuery
        solid.exportStl(file_path)
        logger.info(f"Exportado {flute_name}/{part_name} a {file_path}")
    
    def _export_complete_flute_stl(self, flute_name: str, file_path: str):
        """Exporta la flauta completa ensamblada a STL."""
        import cadquery as cq
        
        if flute_name not in self.flutes_3d_data or not self.flutes_3d_data[flute_name]:
            raise ValueError(f"No hay datos 3D para {flute_name}")
        
        # Orden de ensamblaje
        part_order = ['foot', 'corps', 'headjoint']
        
        # Ensamblar todas las piezas
        assembly = None
        offset_z = 0.0
        
        for part_name in part_order:
            if part_name not in self.flutes_3d_data[flute_name]:
                continue
            
            solid = self._load_3d_solid_for_part(flute_name, part_name)
            
            if not solid:
                continue
            
            # Desplazar en Z
            if offset_z > 0:
                solid = solid.translate((0, 0, offset_z))
            
            # Combinar geometrías
            if assembly is None:
                assembly = solid
            else:
                assembly = assembly.union(solid)
            
            # Calcular siguiente offset
            bbox = solid.val().BoundingBox()
            part_length = bbox.zlen
            offset_z += part_length
        
        if assembly is None:
            raise ValueError("No se pudo ensamblar ninguna pieza")
        
        # Exportar
        assembly.exportStl(file_path)
        logger.info(f"Exportada flauta completa {flute_name} a {file_path}")
    
    def _on_drawings_flute_changed(self, flute_name: str):
        """Maneja el cambio de flauta seleccionada en la pestaña de planos."""
        # Este método puede usarse para actualizar la vista previa automáticamente si se desea
        pass
    
    def _get_selected_flute_for_drawings(self):
        """Obtiene la flauta seleccionada en el combo de planos."""
        if not hasattr(self, 'drawings_flute_combo') or not self.drawings_flute_combo.count():
            return None
        
        selected_name = self.drawings_flute_combo.currentText()
        for flute_data in self.flute_data_list:
            if flute_data.flute_model == selected_name:
                return flute_data
        return None
    
    def _display_pdf_preview(self, pdf_path: str):
        """Muestra la vista previa de todas las páginas del PDF en el canvas."""
        self.drawings_figure.clear()
        
        try:
            import fitz  # PyMuPDF
            pdf_doc = fitz.open(pdf_path)
            num_pages = len(pdf_doc)
            
            if num_pages == 0:
                ax = self.drawings_figure.add_subplot(111)
                ax.text(0.5, 0.5, "PDF vacío", ha='center', va='center', 
                       transform=ax.transAxes, fontsize=12)
                ax.axis('off')
            else:
                # Crear subplots para todas las páginas (una columna, múltiples filas)
                # Limitar a máximo 10 páginas para no sobrecargar la vista
                max_pages_to_show = min(num_pages, 10)
                
                # Crear grid de subplots
                for i in range(max_pages_to_show):
                    ax = self.drawings_figure.add_subplot(max_pages_to_show, 1, i + 1)
                    
                    page = pdf_doc[i]
                    pix = page.get_pixmap(dpi=120)  # DPI más bajo para múltiples páginas
                    img_data = pix.tobytes("png")
                    
                    from PIL import Image
                    import io
                    img = Image.open(io.BytesIO(img_data))
                    
                    ax.imshow(img)
                    ax.axis('off')
                    ax.set_title(f"Página {i + 1} de {num_pages}", 
                               fontsize=9, pad=5)
                
                # Si hay más páginas, mostrar mensaje
                if num_pages > max_pages_to_show:
                    ax = self.drawings_figure.add_subplot(max_pages_to_show + 1, 1, max_pages_to_show + 1)
                    ax.text(0.5, 0.5, 
                           f"... y {num_pages - max_pages_to_show} página(s) más",
                           ha='center', va='center', transform=ax.transAxes,
                           fontsize=10, style='italic')
                    ax.axis('off')
                
                pdf_doc.close()
                
        except ImportError:
            # Si PyMuPDF no está disponible, mostrar mensaje
            ax = self.drawings_figure.add_subplot(111)
            ax.text(0.5, 0.5, 
                   f"PDF generado en:\n{pdf_path}\n\n"
                   "(Instale PyMuPDF para vista previa en GUI:\npip install PyMuPDF)",
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=10, wrap=True)
            ax.axis('off')
        except Exception as e:
            logger.error(f"Error mostrando vista previa del PDF: {e}", exc_info=True)
            ax = self.drawings_figure.add_subplot(111)
            ax.text(0.5, 0.5, 
                   f"Error mostrando vista previa:\n{str(e)}",
                   ha='center', va='center', transform=ax.transAxes,
                   fontsize=10, color='red')
            ax.axis('off')
        
        self.drawings_figure.tight_layout()
        self.drawings_canvas.draw()
    
    def _update_gcode_part_selection(self):
        """Actualiza la lista de partes disponibles cuando cambia la flauta seleccionada."""
        # Este método se puede usar para validar que la parte seleccionada tenga datos
        pass
    
    def _generate_gcode_for_part(self):
        """Genera G-code para la parte seleccionada de la flauta cargada."""
        if not self.flute_data_list:
            QMessageBox.warning(self, "Sin Datos", "No hay flautas cargadas. Carga flautas primero.")
            return
        
        # Obtener flauta seleccionada
        selected_flute_name = self.gcode_flute_combo.currentText()
        if not selected_flute_name:
            QMessageBox.warning(self, "Sin Selección", "Selecciona una flauta del menú desplegable.")
            return
        
        flute_data = None
        for fd in self.flute_data_list:
            if fd.flute_model == selected_flute_name:
                flute_data = fd
                break
        
        if not flute_data:
            QMessageBox.warning(self, "Error", f"Flauta '{selected_flute_name}' no encontrada.")
            return
        
        # Obtener parte seleccionada
        selected_part_index = self.gcode_part_combo.currentIndex()
        if selected_part_index < 0 or selected_part_index >= len(FLUTE_PARTS_ORDER):
            QMessageBox.warning(self, "Error", "Parte inválida seleccionada.")
            return
        
        part_name = FLUTE_PARTS_ORDER[selected_part_index]
        
        # Verificar que la parte tenga datos
        if part_name not in flute_data.data or not flute_data.data[part_name]:
            QMessageBox.warning(
                self, "Sin Datos",
                f"La parte '{part_name}' no tiene datos para la flauta '{selected_flute_name}'."
            )
            return
        
        part_data = flute_data.data[part_name]
        
        # Validar parámetros
        params = {}
        params["ROUGHING_STRATEGY"] = self.gcode_roughing_strategy.currentText()
        params["ECONOMY_MODE"] = self.gcode_economy_mode.isChecked()
        
        for key, widget in self.gcode_params.items():
            if key == "SPINDLE_SPEED":
                params[key] = widget.value()
            else:
                params[key] = widget.value()
        
        # Validar que INITIAL_BORE_DIAMETER sea menor que el diámetro mínimo a mecanizar
        try:
            measurements = part_data.get('measurements', [])
            if not measurements:
                raise ValueError("No hay mediciones en la parte seleccionada.")
            
            min_diameter = min([m['diameter'] for m in measurements])
            if params["INITIAL_BORE_DIAMETER"] >= min_diameter - 1e-6:
                raise ValueError(
                    f"DIÁM INICIAL ({params['INITIAL_BORE_DIAMETER']:.2f}) debe ser MENOR "
                    f"que D mín a mecanizar ({min_diameter:.2f})."
                )
        except Exception as e:
            QMessageBox.critical(self, "Error de Validación", str(e))
            return
        
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            # Cargar datos de la parte
            logger.info(f"Cargando datos para {part_name} de {selected_flute_name}...")
            QApplication.processEvents()
            
            (part_type, mortise_length_original, mortise_diameter,
             profile_start_diameter, profile_end_diameter, profile_measurements,
             total_length, profile_origin_z, profile_end_z) = load_flute_data_from_dict(
                part_data, part_name
            )
            
            # Generar G-code
            logger.info("Generando G-code...")
            QApplication.processEvents()
            
            gcode_output, toolpath_points_data = generate_gcode(
                part_type, mortise_length_original, mortise_diameter,
                profile_start_diameter, profile_end_diameter, profile_measurements,
                total_length, profile_origin_z, profile_end_z, params
            )
            
            # Guardar archivo .nc en el mismo directorio que el JSON de origen
            # Obtener ruta del directorio de la flauta
            if hasattr(flute_data, 'source') and isinstance(flute_data.source, str):
                flute_dir = Path(flute_data.source)
            else:
                # Intentar obtener desde data_dir
                flute_dir = Path(self.data_dir) / selected_flute_name
            
            if not flute_dir.exists():
                # Fallback: usar directorio actual
                flute_dir = Path.cwd()
            
            output_gcode_path = flute_dir / f"{part_name}.nc"
            
            logger.info(f"Guardando G-code en: {output_gcode_path}")
            QApplication.processEvents()
            
            with open(output_gcode_path, 'w', encoding='utf-8') as f:
                for line in gcode_output:
                    f.write(line + '\n')
            
            logger.info(f"G-code guardado exitosamente")
            
            # Actualizar visualizaciones
            logger.info("Generando Gráfico 1 (Intencional)...")
            QApplication.processEvents()
            
            machine_profile_z = np.array([m['position'] for m in profile_measurements]) if profile_measurements else np.array([])
            machine_profile_r = np.array([m['diameter'] for m in profile_measurements]) / 2.0 if profile_measurements else np.array([])
            
            plot_intended_paths(
                self.gcode_ax1, mortise_length_original, mortise_diameter,
                machine_profile_z, machine_profile_r, toolpath_points_data,
                total_length, params
            )
            self.gcode_canvas1.draw()
            
            logger.info("Parseando G-code y Generando Gráfico 2 (Desde NC)...")
            QApplication.processEvents()
            
            g0_segments, g1_segments = parse_gcode(str(output_gcode_path))
            if g0_segments is not None and g1_segments is not None:
                plot_parsed_gcode(self.gcode_ax2, g0_segments, g1_segments, total_length, params)
                self.gcode_canvas2.draw()
                logger.info("Gráfico 2 (Desde NC) generado.")
            else:
                self.gcode_ax2.clear()
                self.gcode_ax2.text(
                    0.5, 0.5, "Error al parsear archivo NC",
                    ha='center', va='center',
                    transform=self.gcode_ax2.transAxes, color='red'
                )
                self.gcode_ax2.set_title("Trayectorias desde Archivo NC")
                self.gcode_ax2.set_xlabel("Posición Z (mm) - Coords Máquina")
                self.gcode_ax2.set_ylabel("Radio (mm)")
                self.gcode_ax2.grid(True)
                self.gcode_canvas2.draw()
                logger.warning("Error al generar Gráfico 2.")
            
            QMessageBox.information(
                self, "Proceso Completado",
                f"G-code generado y gráficos actualizados.\n\n"
                f"Archivo guardado en:\n{output_gcode_path}"
            )
            
        except Exception as e:
            logger.error(f"Error generando G-code: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Error Generación",
                f"Ocurrió un error:\n\n{type(e).__name__}: {e}\n\nVer consola para más detalles."
            )
        finally:
            QApplication.restoreOverrideCursor()
    
    def _generate_drawings(self):
        """Genera el PDF completo de planos y muestra automáticamente la vista previa."""
        flute_data = self._get_selected_flute_for_drawings()
        if not flute_data:
            QMessageBox.warning(self, "Sin Datos", "Selecciona una flauta del menú desplegable.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Guardar Planos", f"{flute_data.flute_model}_planos.pdf", "PDF files (*.pdf)"
        )
        
        if filename:
            try:
                generator = EngineeringDrawingGenerator(
                    flute_data, filename, include_external=True
                )
                generator.generate_complete_drawing()
                
                # Mostrar automáticamente la vista previa después de generar el PDF
                self._display_pdf_preview(filename)
                
                # No mostrar pop-up de éxito, solo registrar en logs
                logger.info(f"Planos generados exitosamente: {filename}")
            except Exception as e:
                logger.error(f"Error generando planos: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Error generando planos: {e}")
    
    # ==================== Métodos de Gestión de Base de Datos ====================
    
    def _check_db_manager(self) -> bool:
        """Verifica que db_manager esté disponible."""
        if self.db_manager is None:
            QMessageBox.warning(
                self,
                "Base de Datos No Disponible",
                "La base de datos no está disponible.\n"
                "Puede estar deshabilitada si es muy grande (>1GB)."
            )
            return False
        return True
    
    def _add_flute_from_directory(self):
        """Agrega una flauta desde un directorio JSON."""
        if not self._check_db_manager():
            return
        
        # Seleccionar directorio
        directory = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar Directorio de Flauta",
            self.data_dir
        )
        if not directory:
            return
        
        flute_dir = Path(directory)
        
        # Verificar que tenga archivos JSON
        has_json = any(f.name.endswith('.json') for f in flute_dir.iterdir())
        if not has_json:
            QMessageBox.warning(
                self,
                "Directorio Inválido",
                "El directorio seleccionado no contiene archivos JSON."
            )
            return
        
        # Mostrar diálogo de progreso
        progress = QProgressDialog("Agregando flauta a la base de datos...", "Cancelar", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()
        
        try:
            # Poblar flauta
            result, report = populate_flute(
                flute_dir,
                temperature=20.0,
                la_frequency=415.0,
                force_recalculate=False,
                generate_report=True
            )
            
            progress.close()
            
            if result:
                QMessageBox.information(
                    self,
                    "Éxito",
                    f"Flauta agregada exitosamente:\n{flute_dir.name}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Advertencia",
                    f"Hubo problemas al agregar la flauta:\n{flute_dir.name}\n\n"
                    f"Revisa el reporte para más detalles."
                )
        except Exception as e:
            progress.close()
            logger.error(f"Error agregando flauta: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error agregando flauta:\n{e}"
            )
    
    def _add_flute_from_file(self):
        """Agrega una flauta desde un archivo JSON individual."""
        if not self._check_db_manager():
            return
        
        # Seleccionar archivo
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Archivo JSON de Flauta",
            self.data_dir,
            "Archivos JSON (*.json);;Todos los archivos (*.*)"
        )
        if not filename:
            return
        
        json_file = Path(filename)
        
        # Verificar que sea un archivo de parte válido
        part_name = json_file.stem
        if part_name not in FLUTE_PARTS_ORDER and not part_name.endswith('_external'):
            reply = QMessageBox.question(
                self,
                "Confirmar",
                f"El archivo '{json_file.name}' no parece ser un archivo de parte estándar.\n"
                f"¿Desea continuar de todas formas?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # Buscar directorio padre
        flute_dir = json_file.parent
        
        # Mostrar diálogo de progreso
        progress = QProgressDialog("Agregando flauta a la base de datos...", "Cancelar", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()
        
        try:
            # Poblar flauta
            result, report = populate_flute(
                flute_dir,
                temperature=20.0,
                la_frequency=415.0,
                force_recalculate=False,
                generate_report=True
            )
            
            progress.close()
            
            if result:
                QMessageBox.information(
                    self,
                    "Éxito",
                    f"Flauta agregada exitosamente desde:\n{json_file.name}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Advertencia",
                    f"Hubo problemas al agregar la flauta.\n\n"
                    f"Revisa el reporte para más detalles."
                )
        except Exception as e:
            progress.close()
            logger.error(f"Error agregando flauta: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error agregando flauta:\n{e}"
            )
    
    def _generate_database_report(self):
        """Genera un reporte completo de la base de datos."""
        if not self._check_db_manager():
            return
        
        # Buscar todos los directorios de flautas
        data_path = Path(self.data_dir)
        if not data_path.exists():
            QMessageBox.warning(
                self,
                "Directorio No Encontrado",
                f"El directorio de datos no existe:\n{self.data_dir}"
            )
            return
        
        # Mostrar diálogo de progreso
        progress = QProgressDialog("Generando reporte...", "Cancelar", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()
        
        try:
            # Encontrar directorios de flautas
            flute_dirs = find_flute_directories(data_path)
            total = len(flute_dirs)
            
            if total == 0:
                progress.close()
                QMessageBox.information(
                    self,
                    "Sin Flautas",
                    "No se encontraron directorios de flautas en:\n" + str(data_path)
                )
                return
            
            reports = []
            
            for i, flute_dir in enumerate(flute_dirs):
                progress.setLabelText(f"Analizando {flute_dir.name} ({i+1}/{total})...")
                QApplication.processEvents()
                
                try:
                    # Verificar archivos
                    files_info = check_flute_files(flute_dir)
                    
                    # Cargar flauta
                    flute_data = FluteDataDB(str(flute_dir), db_manager=self.db_manager)
                    
                    # Analizar estado
                    status = analyze_flute_status(flute_data, files_info)
                    status['files_info'] = files_info
                    status['flute_dir'] = str(flute_dir)
                    reports.append(status)
                    
                except Exception as e:
                    logger.error(f"Error analizando {flute_dir.name}: {e}")
                    reports.append({
                        'flute_name': flute_dir.name,
                        'success': False,
                        'errors': [{'message': str(e)}],
                        'has_errors': True
                    })
            
            progress.close()
            
            # Generar reporte
            report_text = generate_detailed_report(reports)
            
            # Mostrar en diálogo
            dialog = DatabaseReportDialog(report_text, self)
            dialog.exec_()
            
        except Exception as e:
            progress.close()
            logger.error(f"Error generando reporte: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error generando reporte:\n{e}"
            )
    
    def _view_database_report(self):
        """Carga y muestra un reporte guardado previamente."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir Reporte",
            "",
            "Archivos de Texto (*.txt);;Todos los archivos (*.*)"
        )
        if not filename:
            return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                report_text = f.read()
            
            dialog = DatabaseReportDialog(report_text, self)
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error cargando reporte:\n{e}"
            )
    
    def _cleanup_database(self):
        """Limpia los datos de pressure_flow_data de la base de datos."""
        if not self._check_db_manager():
            return
        
        db_path = Path(DEFAULT_DB_PATH)
        if not db_path.exists():
            QMessageBox.warning(self, "Error", "La base de datos no existe.")
            return
        
        # Mostrar estadísticas antes
        stats_before = get_database_size(db_path)
        pf_size_mb = stats_before.get('impedance_results_pressure_flow_mb', 0)
        total_size_mb = stats_before.get('total_size_mb', 0)
        
        # Confirmar
        reply = QMessageBox.question(
            self,
            "Confirmar Limpieza",
            f"Esto eliminará todos los datos de pressure_flow_data de la base de datos.\n\n"
            f"Tamaño actual de pressure_flow_data: {pf_size_mb:.2f} MB\n"
            f"Tamaño total de BD: {total_size_mb:.2f} MB ({total_size_mb/1024:.2f} GB)\n\n"
            f"¿Desea continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Mostrar progreso
        progress = QProgressDialog("Limpiando base de datos...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        QApplication.processEvents()
        
        try:
            cleanup_pressure_flow_data(db_path, backup=True)
            progress.close()
            
            # Mostrar estadísticas después
            stats_after = get_database_size(db_path)
            total_size_after_mb = stats_after.get('total_size_mb', 0)
            space_freed = total_size_mb - total_size_after_mb
            
            QMessageBox.information(
                self,
                "Limpieza Completada",
                f"Limpieza completada exitosamente.\n\n"
                f"Espacio liberado: {space_freed:.2f} MB\n"
                f"Nuevo tamaño: {total_size_after_mb:.2f} MB ({total_size_after_mb/1024:.2f} GB)"
            )
        except Exception as e:
            progress.close()
            logger.error(f"Error limpiando BD: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error limpiando base de datos:\n{e}"
            )
    
    def _optimize_database(self):
        """Optimiza la base de datos ejecutando VACUUM."""
        if not self._check_db_manager():
            return
        
        db_path = Path(DEFAULT_DB_PATH)
        if not db_path.exists():
            QMessageBox.warning(self, "Error", "La base de datos no existe.")
            return
        
        # Confirmar
        reply = QMessageBox.question(
            self,
            "Confirmar Optimización",
            "Esto ejecutará VACUUM en la base de datos para optimizar el espacio.\n"
            "Puede tomar varios minutos si la BD es grande.\n\n"
            "¿Desea continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Mostrar progreso
        progress = QProgressDialog("Optimizando base de datos...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        QApplication.processEvents()
        
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Obtener tamaño antes
            size_before = db_path.stat().st_size / (1024 * 1024)
            
            # Ejecutar VACUUM
            cursor.execute("VACUUM")
            conn.commit()
            conn.close()
            
            progress.close()
            
            # Obtener tamaño después
            size_after = db_path.stat().st_size / (1024 * 1024)
            space_freed = size_before - size_after
            
            QMessageBox.information(
                self,
                "Optimización Completada",
                f"Optimización completada exitosamente.\n\n"
                f"Espacio recuperado: {space_freed:.2f} MB\n"
                f"Nuevo tamaño: {size_after:.2f} MB ({size_after/1024:.2f} GB)"
            )
        except Exception as e:
            progress.close()
            logger.error(f"Error optimizando BD: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error optimizando base de datos:\n{e}"
            )
    
    def _delete_flute_from_db(self):
        """Elimina una flauta de la base de datos."""
        if not self._check_db_manager():
            return
        
        # Obtener lista de flautas
        try:
            flutes = self.db_manager.get_flute_list()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error obteniendo lista de flautas:\n{e}"
            )
            return
        
        if not flutes:
            QMessageBox.information(
                self,
                "Sin Flautas",
                "No hay flautas en la base de datos."
            )
            return
        
        # Diálogo de selección
        from PyQt5.QtWidgets import QListWidget, QListWidgetItem
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Eliminar Flauta")
        dialog.setMinimumSize(400, 300)
        layout = QVBoxLayout(dialog)
        
        label = QLabel("Seleccione la flauta a eliminar:")
        layout.addWidget(label)
        
        list_widget = QListWidget()
        for flute in flutes:
            item = QListWidgetItem(f"{flute['name']} (ID: {flute['id']})")
            item.setData(Qt.UserRole, flute['id'])
            list_widget.addItem(item)
        layout.addWidget(list_widget)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec_() != QDialog.Accepted:
            return
        
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Advertencia", "Por favor seleccione una flauta.")
            return
        
        flute_id = selected_items[0].data(Qt.UserRole)
        flute_name = selected_items[0].text()
        
        # Confirmar eliminación
        reply = QMessageBox.question(
            self,
            "Confirmar Eliminación",
            f"¿Está seguro de que desea eliminar la flauta:\n{flute_name}?\n\n"
            f"Esta acción no se puede deshacer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Eliminar
        try:
            success = self.db_manager.delete_flute(flute_id)
            if success:
                QMessageBox.information(
                    self,
                    "Éxito",
                    f"Flauta eliminada exitosamente:\n{flute_name}"
                )
            else:
                QMessageBox.warning(
                    self,
                    "Advertencia",
                    f"No se pudo eliminar la flauta:\n{flute_name}"
                )
        except Exception as e:
            logger.error(f"Error eliminando flauta: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Error eliminando flauta:\n{e}"
            )
    
    def _show_database_statistics(self):
        """Muestra estadísticas de la base de datos."""
        if not self._check_db_manager():
            return
        
        try:
            stats = self.db_manager.get_database_statistics()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error obteniendo estadísticas:\n{e}"
            )
            return
        
        # Formatear estadísticas
        stats_text = f"""
ESTADÍSTICAS DE BASE DE DATOS
{'=' * 50}

Tamaño Total:
  {stats.get('total_size_mb', 0):.2f} MB ({stats.get('total_size_gb', 0):.2f} GB)

Contenido:
  Flautas: {stats.get('total_flutes', 0)}
  Cálculos de impedancia: {stats.get('total_calculations', 0)}
  Resultados de impedancia: {stats.get('total_impedance_results', 0)}
  Resultados con pressure_flow_data: {stats.get('results_with_pressure_flow', 0)}
  Tamaño de pressure_flow_data: {stats.get('pressure_flow_size_mb', 0):.2f} MB
  Geometría externa: {stats.get('total_external_geometry', 0)}
  Geometría de flauta: {stats.get('total_flute_geometry', 0)}

Registros por Tabla:
"""
        
        table_sizes = stats.get('table_sizes', {})
        for table, count in sorted(table_sizes.items()):
            stats_text += f"  {table}: {count}\n"
        
        # Mostrar en diálogo
        dialog = QDialog(self)
        dialog.setWindowTitle("Estadísticas de Base de Datos")
        dialog.setMinimumSize(500, 400)
        layout = QVBoxLayout(dialog)
        
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Courier", 9))
        text_edit.setPlainText(stats_text)
        layout.addWidget(text_edit)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.exec_()


def signal_handler(sig, frame):
    """Maneja señales de terminación."""
    logger.warning(f"Señal recibida: {sig}")
    import traceback
    traceback.print_stack(frame)
    sys.exit(0)


def main():
    """Función principal."""
    # Registrar handlers de señales para debugging
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        logger.info("Iniciando aplicación PyQt5...")
        app = QApplication(sys.argv)
        logger.info("QApplication creado")
        
        app.setStyle('Fusion')  # Estilo moderno
        logger.info("Estilo Fusion aplicado")
        
        logger.info("Creando ventana principal...")
        window = UnifiedFluteGUI_Qt()
        logger.info("Ventana principal creada")
        
        logger.info("Mostrando ventana...")
        window.show()
        logger.info("Ventana mostrada, iniciando event loop...")
        
        exit_code = app.exec_()
        logger.info(f"Event loop terminado con código: {exit_code}")
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        logger.info("Interrupción por teclado")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error fatal en main: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

