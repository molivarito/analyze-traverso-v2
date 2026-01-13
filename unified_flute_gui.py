"""
GUI Unificada para Visualización y Análisis Completo de Flautas.

Integra todas las funcionalidades:
- Visualización 2D (planos de ingeniería, geometría, impedancias)
- Visualización 3D (modelos 3D interactivos, comparación)
- Análisis (inharmonicidad, MOC, B_I/ESPE)
- Perturbación (variación de parámetros)
- Modificación (editor de geometría)

⚠️ DEPRECATION WARNING ⚠️

This GUI module (unified_flute_gui.py) appears to be superseded.

**Recommended**: Use unified_flute_gui_qt.py (PyQt5-based) instead.

**Status**: Likely legacy - unified_flute_gui_qt.py is the current unified GUI.
See DEPRECATIONS.md for details.

This Tkinter-based version may be replaced by the PyQt5 version.
If you need this specific version, please document why in the project issues.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging
import numpy as np
import warnings

# Issue deprecation warning
warnings.warn(
    "unified_flute_gui.py (Tkinter) is likely superseded by unified_flute_gui_qt.py (PyQt5). "
    "See DEPRECATIONS.md for details.",
    DeprecationWarning,
    stacklevel=2
)

from flute_data_db import FluteDataDB
from flute_operations import FluteOperations
from flute_db_manager import FluteDBManager
from engineering_drawings import EngineeringDrawingGenerator
from flute_3d_visualizer import Flute3DModel, compare_flutes_3d
from analysis_module import FluteAnalyzer
from geometry_perturbation import GeometryPerturbator
from perturbation_gui import PerturbationGUI
from geometry_modifier import GeometryModifier
from constants import BASE_COLORS, FLUTE_PARTS_ORDER

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_JSON_DIR = SCRIPT_DIR.parent / "data_json"
if not DEFAULT_DATA_JSON_DIR.exists():
    DEFAULT_DATA_JSON_DIR = SCRIPT_DIR / "data_json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s [%(name)s:%(funcName)s:%(lineno)d] - %(message)s')
logger = logging.getLogger(__name__)


class UnifiedFluteGUI(tk.Tk):
    """
    Aplicación principal unificada para visualización y análisis de flautas.
    """
    
    def __init__(self):
        super().__init__()
        self.title("Sistema Unificado de Análisis de Flautas")
        self.geometry("1600x1000")
        
        self.data_dir = str(DEFAULT_DATA_JSON_DIR)
        self.db_manager = FluteDBManager()
        self.currently_selected_flute_dirs: List[str] = []
        self.source_mode: str = "db"
        
        # Datos cargados
        self.flute_data_list: List[FluteDataDB] = []
        self.flute_ops_list: List[FluteOperations] = []
        self.analyzer: Optional[FluteAnalyzer] = None
        
        self._create_menu()
        self._create_main_interface()
        
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_menu(self) -> None:
        """Crea el menú principal."""
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # Menú Archivo
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=file_menu)
        file_menu.add_command(label="Seleccionar Flautas...", command=self._open_flute_selection)
        file_menu.add_separator()
        file_menu.add_command(label="Exportar Planos PDF...", command=self._export_engineering_drawings)
        file_menu.add_command(label="Exportar Modelo 3D...", command=self._export_3d_model)
        file_menu.add_command(label="Exportar Análisis...", command=self._export_analysis)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self._on_close)
        
        # Menú Herramientas
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Herramientas", menu=tools_menu)
        tools_menu.add_command(label="Perturbaciones...", command=self._open_perturbation_gui)
        tools_menu.add_command(label="Modificar Geometría...", command=self._open_geometry_modifier)
    
    def _create_main_interface(self) -> None:
        """Crea la interfaz principal con pestañas."""
        # Barra de herramientas
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(toolbar, text="Seleccionar Flautas", command=self._open_flute_selection).pack(side=tk.LEFT, padx=5)
        self.flute_status_label = ttk.Label(toolbar, text="Ninguna flauta cargada")
        self.flute_status_label.pack(side=tk.LEFT, padx=10)
        
        # Notebook principal con pestañas
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Crear pestañas
        self._create_2d_visualization_tab()
        self._create_3d_visualization_tab()
        self._create_analysis_tab()
        self._create_engineering_drawings_tab()
    
    def _create_2d_visualization_tab(self) -> None:
        """Crea la pestaña de visualización 2D."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Visualización 2D")
        
        # Sub-notebook para diferentes vistas 2D
        sub_notebook = ttk.Notebook(frame)
        sub_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Perfil combinado
        profile_frame = ttk.Frame(sub_notebook)
        sub_notebook.add(profile_frame, text="Perfil Combinado")
        self.profile_canvas = self._create_plot_canvas(profile_frame)
        
        # Partes individuales
        parts_frame = ttk.Frame(sub_notebook)
        sub_notebook.add(parts_frame, text="Partes Individuales")
        self.parts_canvas = self._create_plot_canvas(parts_frame)
        
        # Admitancia
        admittance_frame = ttk.Frame(sub_notebook)
        sub_notebook.add(admittance_frame, text="Admitancia")
        
        # Selector de nota para admitancia
        note_frame = ttk.Frame(admittance_frame)
        note_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(note_frame, text="Nota:").pack(side=tk.LEFT, padx=5)
        self.admittance_note_var = tk.StringVar()
        self.admittance_note_combo = ttk.Combobox(note_frame, textvariable=self.admittance_note_var, state='readonly')
        self.admittance_note_combo.pack(side=tk.LEFT, padx=5)
        self.admittance_note_combo.bind('<<ComboboxSelected>>', lambda e: self._update_admittance_plot())
        
        self.admittance_canvas = self._create_plot_canvas(admittance_frame)
    
    def _create_3d_visualization_tab(self) -> None:
        """Crea la pestaña de visualización 3D."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Visualización 3D")
        
        # Controles
        control_frame = ttk.Frame(frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(control_frame, text="Parte:").pack(side=tk.LEFT, padx=5)
        self.part_3d_var = tk.StringVar(value="all")
        part_combo = ttk.Combobox(control_frame, textvariable=self.part_3d_var,
                                 values=["all"] + FLUTE_PARTS_ORDER, state='readonly', width=15)
        part_combo.pack(side=tk.LEFT, padx=5)
        part_combo.bind('<<ComboboxSelected>>', lambda e: self._update_3d_plot())
        
        ttk.Button(control_frame, text="Actualizar Vista 3D", command=self._update_3d_plot).pack(side=tk.LEFT, padx=5)
        
        # Canvas 3D
        self.fig_3d = plt.figure(figsize=(12, 8))
        self.ax_3d = self.fig_3d.add_subplot(111, projection='3d')
        self.canvas_3d = FigureCanvasTkAgg(self.fig_3d, frame)
        self.canvas_3d.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def _create_analysis_tab(self) -> None:
        """Crea la pestaña de análisis."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Análisis")
        
        # Sub-notebook para diferentes análisis
        sub_notebook = ttk.Notebook(frame)
        sub_notebook.pack(fill=tk.BOTH, expand=True)
        
        # Inharmonicidad
        inharm_frame = ttk.Frame(sub_notebook)
        sub_notebook.add(inharm_frame, text="Inharmonicidad")
        self.inharm_canvas = self._create_plot_canvas(inharm_frame)
        
        # MOC
        moc_frame = ttk.Frame(sub_notebook)
        sub_notebook.add(moc_frame, text="MOC")
        self.moc_canvas = self._create_plot_canvas(moc_frame)
        
        # B_I y ESPE
        bi_espe_frame = ttk.Frame(sub_notebook)
        sub_notebook.add(bi_espe_frame, text="B_I & ESPE")
        self.bi_espe_canvas = self._create_plot_canvas(bi_espe_frame)
    
    def _create_engineering_drawings_tab(self) -> None:
        """Crea la pestaña de planos de ingeniería."""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="Planos de Ingeniería")
        
        # Controles
        control_frame = ttk.Frame(frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(control_frame, text="Generar Plano Completo", command=self._generate_full_drawing).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Vista Previa", command=self._preview_drawing).pack(side=tk.LEFT, padx=5)
        
        # Canvas para vista previa
        preview_frame = ttk.LabelFrame(frame, text="Vista Previa", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.drawing_preview_canvas = self._create_plot_canvas(preview_frame)
        
        ttk.Label(preview_frame, text="Los planos se generan en PDF.\nUse los botones para crear planos de ingeniería.",
                 font=('Arial', 10)).pack(expand=True)
    
    def _create_plot_canvas(self, parent: ttk.Frame) -> FigureCanvasTkAgg:
        """Crea un canvas de matplotlib en un frame."""
        fig, ax = plt.subplots(figsize=(10, 6))
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        return canvas
    
    def _open_flute_selection(self) -> None:
        """Abre el diálogo de selección de flautas."""
        from gui_db import FluteSelectionDialogDB
        
        dialog = FluteSelectionDialogDB(self, self.data_dir, self.db_manager, self.currently_selected_flute_dirs)
        self.data_dir = dialog.final_data_dir_on_accept
        self.source_mode = getattr(dialog, 'source_mode_final', 'db')
        
        if dialog.selected_flute_dirs_on_accept:
            self.currently_selected_flute_dirs = dialog.selected_flute_dirs_on_accept
            self._load_flutes()
    
    def _load_flutes(self) -> None:
        """Carga las flautas seleccionadas."""
        self.flute_data_list = []
        self.flute_ops_list = []
        
        for flute_name in self.currently_selected_flute_dirs:
            try:
                if self.source_mode == "db":
                    flute_id = self.db_manager.get_flute_id(flute_name)
                    if flute_id:
                        # Cargar desde JSON pero usando FluteDataDB
                        json_path = Path(self.data_dir) / flute_name
                        if json_path.exists():
                            flute_data = FluteDataDB(str(json_path))
                        else:
                            # Intentar desde geometría de BD
                            geometry = self.db_manager.get_flute_geometry(flute_id)
                            flute_data = FluteDataDB(geometry, source_name=flute_name)
                    else:
                        json_path = Path(self.data_dir) / flute_name
                        if json_path.exists():
                            flute_data = FluteDataDB(str(json_path))
                        else:
                            messagebox.showerror("Error", f"Flauta '{flute_name}' no encontrada", parent=self)
                            continue
                else:
                    json_path = Path(self.data_dir) / flute_name
                    if not json_path.exists():
                        messagebox.showerror("Error", f"Directorio no encontrado: {json_path}", parent=self)
                        continue
                    flute_data = FluteDataDB(str(json_path))
                
                if flute_data.validation_errors:
                    messagebox.showerror("Error", f"Errores en '{flute_name}': {flute_data.validation_errors}", parent=self)
                    continue
                
                self.flute_data_list.append(flute_data)
                self.flute_ops_list.append(FluteOperations(flute_data))
                
            except Exception as e:
                logger.error(f"Error cargando flauta '{flute_name}': {e}", exc_info=True)
                messagebox.showerror("Error", f"Error cargando '{flute_name}': {e}", parent=self)
        
        if self.flute_data_list:
            self.analyzer = FluteAnalyzer(self.flute_data_list, self.flute_ops_list)
            self.flute_status_label.config(text=f"{len(self.flute_data_list)} flauta(s) cargada(s)")
            self._update_all_plots()
            self._update_admittance_note_options()
        else:
            self.flute_status_label.config(text="Ninguna flauta cargada")
    
    def _update_all_plots(self) -> None:
        """Actualiza todos los gráficos."""
        if not self.flute_ops_list:
            return
        
        self._update_profile_plot()
        self._update_parts_plot()
        self._update_analysis_plots()
    
    def _update_profile_plot(self) -> None:
        """Actualiza el gráfico de perfil combinado - DOS subplots como en gui.py original."""
        # Limpiar la figura existente para evitar ventanas superpuestas
        self.profile_canvas.figure.clear()
        
        if not self.flute_ops_list:
            ax_phys_ph, ax_acou_ph = self.profile_canvas.figure.subplots(2, 1)
            ax_phys_ph.text(0.5, 0.5, "Cargue flautas para ver el perfil físico.", 
                           ha='center', va='center', transform=ax_phys_ph.transAxes)
            ax_acou_ph.text(0.5, 0.5, "Cargue flautas para ver el perfil acústico.",
                           ha='center', va='center', transform=ax_acou_ph.transAxes)
            self.profile_canvas.draw()
            return
        
        ax_physical, ax_acoustic = self.profile_canvas.figure.subplots(2, 1)
        self.profile_canvas.figure.subplots_adjust(hspace=0.3)
        
        # --- Subplot 1: Ensamblaje Físico Estimado ---
        flute_names_str_list_phys = [fo.flute_data.flute_model for fo in self.flute_ops_list]
        title_physical = f"Ensamblaje Físico Estimado: {', '.join(flute_names_str_list_phys)}"
        ax_physical.set_title(title_physical)
        ax_physical.set_xlabel("Posición Absoluta Estimada (mm)")
        ax_physical.set_ylabel("Diámetro (mm)")
        ax_physical.grid(True, linestyle=':', alpha=0.7)
        overall_max_x_physical_all_flutes = 0
        physical_legend_handles = []
        
        # Calcular diámetro mínimo para posicionar agujeros en el subplot físico
        min_diam_physical = float('inf')
        for flute_ops_phys in self.flute_ops_list:
            for part_name in FLUTE_PARTS_ORDER:
                part_data = flute_ops_phys.flute_data.data.get(part_name, {})
                measurements = part_data.get("measurements", [])
                if measurements:
                    min_diam_part = min(m.get('diameter', float('inf')) for m in measurements)
                    min_diam_physical = min(min_diam_physical, min_diam_part)
        
        for i, flute_ops in enumerate(self.flute_ops_list):
            flute_model_name = flute_ops.flute_data.flute_model
            max_x_this_flute = flute_ops.plot_physical_assembly(
                ax=ax_physical,
                plot_label_suffix="_nolegend_",
                overall_linestyle='-'
            )
            if max_x_this_flute is not None:
                overall_max_x_physical_all_flutes = max(overall_max_x_physical_all_flutes, max_x_this_flute)
                phys_line, = ax_physical.plot([], [],
                                             color=BASE_COLORS[i % len(BASE_COLORS)],
                                             linestyle='-',
                                             label=f"{flute_model_name} (Físico: {max_x_this_flute:.1f} mm)")
                physical_legend_handles.append(phys_line)
            
            # Dibujar agujeros en el perfil físico
            y_pos_holes_physical = (min_diam_physical if min_diam_physical != float('inf') else 10) - (3 + i * 1.5)
            
            # Calcular posiciones físicas de las partes para los agujeros
            part_physical_starts_phys = {}
            current_connection = 0.0
            for idx_part, part_name in enumerate(FLUTE_PARTS_ORDER):
                part_data = flute_ops.flute_data.data.get(part_name, {})
                part_total_length = part_data.get("Total length", 0.0)
                part_mortise_length = part_data.get("Mortise length", 0.0)
                
                if idx_part == 0:  # headjoint
                    part_physical_starts_phys[part_name] = 0.0
                    current_connection = part_total_length - part_mortise_length
                elif idx_part == 1:  # body
                    part_physical_starts_phys[part_name] = current_connection
                    current_connection += part_total_length
                else:  # foot
                    part_physical_starts_phys[part_name] = current_connection - part_mortise_length
                    current_connection = part_physical_starts_phys[part_name] + part_total_length
            
            # Dibujar agujeros de todas las partes
            for part_name in FLUTE_PARTS_ORDER:
                part_data = flute_ops.flute_data.data.get(part_name, {})
                part_physical_start = part_physical_starts_phys.get(part_name, 0.0)
                hole_positions = part_data.get("Holes position", [])
                hole_diameters = part_data.get("Holes diameter", [])
                
                for h_pos_rel, h_diam in zip(hole_positions, hole_diameters):
                    abs_physical_hole_pos = part_physical_start + h_pos_rel
                    marker_size_scaled = max(h_diam * 2.0, 4)
                    ax_physical.plot(abs_physical_hole_pos, y_pos_holes_physical, marker='o',
                                   color=BASE_COLORS[i % len(BASE_COLORS)], markersize=marker_size_scaled,
                                   linestyle='None', alpha=0.7)
        
        if physical_legend_handles:
            ax_physical.legend(handles=physical_legend_handles, loc='best', fontsize='small')
        if overall_max_x_physical_all_flutes > 0:
            ax_physical.set_xlim(-10, overall_max_x_physical_all_flutes + 10)
        
        # --- Subplot 2: Perfil Acústico Interno Combinado ---
        flute_names_str_list_acou = [fo.flute_data.flute_model for fo in self.flute_ops_list]
        title_acoustic = f"Perfil Acústico Interno: {', '.join(flute_names_str_list_acou)}"
        ax_acoustic.set_title(title_acoustic)
        ax_acoustic.set_xlabel("Posición (mm) desde el corcho")
        ax_acoustic.set_ylabel("Diámetro (mm)")
        ax_acoustic.grid(True, linestyle=':', alpha=0.7)
        
        min_diam_all_acoustic_profiles = float('inf')
        max_overall_cork_relative_pos = -float('inf')
        min_overall_cork_relative_pos = float('inf')
        acoustic_legend_handles = []
        
        for flute_ops_ac in self.flute_ops_list:
            if flute_ops_ac.flute_data.combined_measurements:
                min_diam_this_flute = min(m['diameter'] for m in flute_ops_ac.flute_data.combined_measurements)
                min_diam_all_acoustic_profiles = min(min_diam_all_acoustic_profiles, min_diam_this_flute)
        
        for i, flute_ops in enumerate(self.flute_ops_list):
            flute_model_name = flute_ops.flute_data.flute_model
            headjoint_data_for_offset = flute_ops.flute_data.data.get(FLUTE_PARTS_ORDER[0], {})
            stopper_abs_pos_mm_for_offset = headjoint_data_for_offset.get('_calculated_stopper_absolute_position_mm', 0.0)
            
            acoustic_length_this_flute = 0.0
            combined_measurements_for_length = flute_ops.flute_data.combined_measurements
            if combined_measurements_for_length:
                acoustic_start_abs = stopper_abs_pos_mm_for_offset
                if combined_measurements_for_length:
                    acoustic_end_abs = max(m['position'] for m in combined_measurements_for_length)
                    acoustic_length_this_flute = acoustic_end_abs - acoustic_start_abs
                    
                    cork_rel_positions_this_flute = [(m['position'] - acoustic_start_abs) for m in combined_measurements_for_length]
                    if cork_rel_positions_this_flute:
                        max_overall_cork_relative_pos = max(max_overall_cork_relative_pos, max(cork_rel_positions_this_flute))
                        min_overall_cork_relative_pos = min(min_overall_cork_relative_pos, min(cork_rel_positions_this_flute))
            
            acoustic_line, = ax_acoustic.plot([], [],
                                              color=BASE_COLORS[i % len(BASE_COLORS)],
                                              linestyle='-',
                                              label=f"{flute_model_name} (Acústico: {acoustic_length_this_flute:.1f} mm)")
            acoustic_legend_handles.append(acoustic_line)
            
            flute_ops.plot_combined_flute_data(
                ax=ax_acoustic,
                plot_label="_nolegend_",
                flute_color=BASE_COLORS[i % len(BASE_COLORS)],
                flute_style='-',
                show_mortise_markers=False,
                x_axis_origin_offset=stopper_abs_pos_mm_for_offset
            )
            
            y_pos_holes_acoustic = (min_diam_all_acoustic_profiles if min_diam_all_acoustic_profiles != float('inf') else 10) - (3 + i * 1.5)
            part_physical_starts_map = {}
            current_physical_connection_point_abs = 0.0
            stopper_abs_pos_mm = stopper_abs_pos_mm_for_offset
            
            for idx_part_calc, part_name_calc in enumerate(FLUTE_PARTS_ORDER):
                part_data_calc = flute_ops.flute_data.data.get(part_name_calc, {})
                part_total_length_calc = part_data_calc.get("Total length", 0.0)
                part_mortise_length_calc = part_data_calc.get("Mortise length", 0.0)
                if idx_part_calc == 0:
                    part_physical_starts_map[part_name_calc] = 0.0
                    current_physical_connection_point_abs = part_total_length_calc - part_mortise_length_calc
                elif idx_part_calc == 1:
                    part_physical_starts_map[part_name_calc] = current_physical_connection_point_abs
                    current_physical_connection_point_abs += part_total_length_calc
                else:
                    part_physical_starts_map[part_name_calc] = current_physical_connection_point_abs - part_mortise_length_calc
                    current_physical_connection_point_abs = part_physical_starts_map[part_name_calc] + part_total_length_calc
            
            for part_name_hole in FLUTE_PARTS_ORDER:
                part_data_hole = flute_ops.flute_data.data.get(part_name_hole, {})
                part_physical_start_abs_mm = part_physical_starts_map.get(part_name_hole, 0.0)
                for h_pos_rel, h_diam in zip(part_data_hole.get("Holes position", []), part_data_hole.get("Holes diameter", [])):
                    abs_physical_hole_pos = part_physical_start_abs_mm + h_pos_rel
                    plot_pos_on_acoustic = abs_physical_hole_pos - stopper_abs_pos_mm
                    marker_size_scaled = max(h_diam * 2.0, 4)
                    ax_acoustic.plot(plot_pos_on_acoustic, y_pos_holes_acoustic, marker='o',
                                   color=BASE_COLORS[i % len(BASE_COLORS)], markersize=marker_size_scaled,
                                   linestyle='None', alpha=0.7)
        
        if acoustic_legend_handles:
            ax_acoustic.legend(handles=acoustic_legend_handles, loc='best', fontsize='small')
        if max_overall_cork_relative_pos > -float('inf'):
            ax_acoustic.set_xlim(min_overall_cork_relative_pos - 10, max_overall_cork_relative_pos + 10)
        else:
            ax_acoustic.set_xlim(-50, 600)
        
        self.profile_canvas.draw()
    
    def _update_parts_plot(self) -> None:
        """Actualiza el gráfico de partes individuales - exactamente como gui.py."""
        # Limpiar la figura existente para evitar ventanas superpuestas
        self.parts_canvas.figure.clear()
        
        if not self.flute_ops_list:
            axes_array = self.parts_canvas.figure.subplots(2, 2)
            for i, ax_ph_part in enumerate(axes_array.flatten()):
                ax_ph_part.text(0.5, 0.5, f"Cargue flautas para ver Parte {i+1}",
                              ha='center', va='center', transform=ax_ph_part.transAxes)
            self.parts_canvas.draw()
            return
        
        axes_array = self.parts_canvas.figure.subplots(2, 2)
        axes_flat = list(axes_array.flatten())
        
        flute_names_for_title = []
        
        for flute_idx, flute_ops_instance in enumerate(self.flute_ops_list):
            flute_model_name = flute_ops_instance.flute_data.flute_model
            if flute_model_name not in flute_names_for_title:
                flute_names_for_title.append(flute_model_name)
            
            current_flute_color = BASE_COLORS[flute_idx % len(BASE_COLORS)]
            current_flute_style = '-'
            
            for part_idx, part_name in enumerate(FLUTE_PARTS_ORDER):
                if part_idx >= len(axes_flat):
                    break
                
                ax_part = axes_flat[part_idx]
                adjusted_positions, diameters = flute_ops_instance._calculate_adjusted_positions(part_name, 0.0)
                
                if not adjusted_positions or not diameters:
                    continue
                
                # Dibujar con puntos discretos (marker='.')
                ax_part.plot(adjusted_positions, diameters, marker='.', linestyle=current_flute_style,
                           color=current_flute_color, markersize=3, label=f"{flute_model_name}")
                
                part_data_dict = flute_ops_instance.flute_data.data.get(part_name, {})
                
                # Calcular longitudes física y acústica
                part_physical_total_length = part_data_dict.get("Total length", 0.0)
                part_mortise_length = part_data_dict.get("Mortise length", 0.0)
                part_acoustic_length = 0.0
                if part_name == FLUTE_PARTS_ORDER[0]:  # headjoint
                    part_acoustic_length = part_physical_total_length - part_mortise_length
                elif part_name == FLUTE_PARTS_ORDER[1]:  # body
                    part_acoustic_length = part_physical_total_length
                else:  # foot
                    part_acoustic_length = part_physical_total_length - part_mortise_length
                
                # Mostrar longitudes en texto
                text_str = f"L. Total: {part_physical_total_length:.1f} mm\nL. Acústica: {part_acoustic_length:.1f} mm"
                ax_part.text(0.02, 0.98 - (flute_idx * 0.12), text_str, transform=ax_part.transAxes,
                           ha='left', va='top', fontsize=6, color=current_flute_color,
                           bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.75, ec='grey'))
                
                # Dibujar agujeros
                hole_positions_part = part_data_dict.get("Holes position", [])
                hole_diameters_part = part_data_dict.get("Holes diameter", [])
                
                if hole_positions_part and hole_diameters_part:
                    min_diam_this_part_this_flute = min(diameters) if diameters else 0
                    y_pos_for_holes = min_diam_this_part_this_flute - (5 + flute_idx * 1.5)
                    
                    for h_pos, h_diam in zip(hole_positions_part, hole_diameters_part):
                        marker_size_scaled_part = max(h_diam * 2.0, 4)
                        ax_part.plot(h_pos, y_pos_for_holes, marker='o', color=current_flute_color,
                                   markersize=marker_size_scaled_part, linestyle='None', alpha=0.7)
                
                ax_part.set_title(f"{part_name.capitalize()}", fontsize=9)
                ax_part.set_xlabel("Posición en parte (mm)", fontsize=8)
                ax_part.set_ylabel("Diámetro (mm)", fontsize=8)
                ax_part.grid(True, linestyle=':', alpha=0.5)
                ax_part.tick_params(axis='both', which='major', labelsize=7)
        
        # Consolidar leyendas
        for ax_p in axes_flat:
            handles, labels = ax_p.get_legend_handles_labels()
            if handles:
                by_label = dict(zip(labels, handles))
                ax_p.legend(by_label.values(), by_label.keys(), loc='upper right', fontsize=7)
        
        self.parts_canvas.figure.suptitle(f"Comparación de Partes Individuales: {', '.join(flute_names_for_title)}", fontsize=11)
        self.parts_canvas.figure.tight_layout(rect=[0, 0.03, 1, 0.95])
        self.parts_canvas.draw()
    
    def _update_admittance_note_options(self) -> None:
        """Actualiza las opciones de notas para admitancia."""
        all_notes = set()
        for flute_data in self.flute_data_list:
            all_notes.update(flute_data.acoustic_analysis.keys())
        
        if all_notes:
            # Orden canónico de notas
            canonical_order = ["D", "D#", "E", "F", "Fs", "G", "G#", "A", "A#", "B", "C", "Cs"]
            ordered_notes = [n for n in canonical_order if n in all_notes]
            # Agregar notas no canónicas al final
            ordered_notes.extend(sorted(list(all_notes - set(ordered_notes))))
            
            self.admittance_note_combo['values'] = ordered_notes
            if ordered_notes:
                self.admittance_note_var.set(ordered_notes[0])
            self._update_admittance_plot()
    
    def _update_admittance_plot(self) -> None:
        """Actualiza el gráfico de admitancia - exactamente como gui_db.py."""
        note = self.admittance_note_var.get()
        if not note or not self.flute_ops_list:
            return
        
        # Preparar listas para FluteOperations.plot_individual_admittance_analysis
        acoustic_list = [(fd.acoustic_analysis, fd.flute_model) for fd in self.flute_data_list]
        measurements_list = [(fd.combined_measurements, fd.flute_model) for fd in self.flute_data_list]
        
        # Usar el método estático - exactamente como en gui_db.py línea 698-702
        fig = FluteOperations.plot_individual_admittance_analysis(
            acoustic_list,
            measurements_list,
            note
        )
        
        # Recrear el canvas completamente - como _setup_plot_canvas en gui_db.py línea 392-400
        # Obtener el frame padre del canvas y destruir solo el canvas anterior
        parent_frame = self.admittance_canvas.get_tk_widget().master
        canvas_widget_old = self.admittance_canvas.get_tk_widget()
        canvas_widget_old.destroy()
        
        self.admittance_canvas = FigureCanvasTkAgg(fig, master=parent_frame)
        canvas_widget = self.admittance_canvas.get_tk_widget()
        canvas_widget.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.admittance_canvas.draw()
    
    def _update_3d_plot(self) -> None:
        """Actualiza la visualización 3D."""
        if not self.flute_data_list:
            return
        
        try:
            # Mostrar mensaje de procesamiento
            self.ax_3d.clear()
            self.ax_3d.text(0.5, 0.5, 0.5, "Generando modelo 3D...\nEsto puede tomar unos momentos.",
                           ha='center', va='center', fontsize=12, transform=self.ax_3d.transAxes)
            self.canvas_3d.draw()
            self.update()  # Forzar actualización de la GUI
            
            part_name = self.part_3d_var.get()
            
            self.ax_3d.clear()
            
            for idx, flute_data in enumerate(self.flute_data_list):
                try:
                    model_3d = Flute3DModel(flute_data)
                    
                    # Visualizar directamente con matplotlib (no generar modelo CadQuery completo)
                    if part_name == "all":
                        model_3d.visualize_with_matplotlib(ax=self.ax_3d)
                    else:
                        model_3d.visualize_with_matplotlib(part_name=part_name, ax=self.ax_3d)
                    
                except Exception as e:
                    logger.error(f"Error generando visualización 3D para {flute_data.flute_model}: {e}")
                    messagebox.showerror("Error", f"Error en visualización 3D: {e}", parent=self)
            
            self.ax_3d.set_title("Visualización 3D")
            self.canvas_3d.draw()
            
        except Exception as e:
            logger.error(f"Error en _update_3d_plot: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error actualizando vista 3D: {e}", parent=self)
    
    def _update_analysis_plots(self) -> None:
        """Actualiza los gráficos de análisis."""
        if not self.analyzer:
            return
        
        # Inharmonicidad - asignar figura directamente
        fig_inharm = self.analyzer.plot_inharmonicity()
        self.inharm_canvas.figure = fig_inharm
        self.inharm_canvas.draw()
        
        # MOC - asignar figura directamente
        fig_moc = self.analyzer.plot_moc()
        self.moc_canvas.figure = fig_moc
        self.moc_canvas.draw()
        
        # B_I y ESPE - asignar figura directamente
        fig_bi = self.analyzer.plot_bi_espe()
        self.bi_espe_canvas.figure = fig_bi
        self.bi_espe_canvas.draw()
    
    def _export_engineering_drawings(self) -> None:
        """Exporta planos de ingeniería."""
        if not self.flute_data_list:
            messagebox.showwarning("Advertencia", "Cargue al menos una flauta", parent=self)
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if filename:
            try:
                generator = EngineeringDrawingGenerator(
                    self.flute_data_list[0],
                    filename,
                    include_external=True
                )
                generator.generate_complete_drawing()
                messagebox.showinfo("Éxito", f"Plano generado: {filename}", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Error generando plano: {e}", parent=self)
    
    def _generate_full_drawing(self) -> None:
        """Genera plano completo con todas las partes."""
        self._export_engineering_drawings()
    
    def _preview_drawing(self) -> None:
        """Previsualiza el plano de ingeniería generando el PDF completo."""
        if not self.flute_data_list:
            messagebox.showwarning("Advertencia", "Cargue al menos una flauta", parent=self)
            return
        
        try:
            import tempfile
            from matplotlib.backends.backend_pdf import PdfPages
            import matplotlib.pyplot as plt
            from matplotlib.figure import Figure
            
            # Limpiar canvas
            self.drawing_preview_canvas.figure.clear()
            
            flute_data = self.flute_data_list[0]
            
            # Generar PDF temporal
            temp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
            temp_pdf_path = temp_pdf.name
            temp_pdf.close()
            
            # Crear generador y generar el PDF completo
            from engineering_drawings import EngineeringDrawingGenerator
            generator = EngineeringDrawingGenerator(flute_data, temp_pdf_path, include_external=True)
            generator.generate_complete_drawing()
            
            # Leer la primera página del PDF y mostrarla como vista previa
            try:
                import fitz  # PyMuPDF (opcional: pip install PyMuPDF)
                pdf_doc = fitz.open(temp_pdf_path)
                page = pdf_doc[1]  # Segunda página (primera parte individual)
                pix = page.get_pixmap(dpi=150)
                img_data = pix.tobytes("png")
                
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(img_data))
                
                ax = self.drawing_preview_canvas.figure.add_subplot(111)
                ax.imshow(img)
                ax.axis('off')
                ax.set_title(f"Vista Previa - Página 2: Headjoint - {flute_data.flute_model}", 
                           fontsize=10, pad=10)
                
                pdf_doc.close()
            except ImportError:
                # Si PyMuPDF no está disponible, mostrar mensaje
                ax = self.drawing_preview_canvas.figure.add_subplot(111)
                ax.text(0.5, 0.5, 
                       f"PDF generado en:\n{temp_pdf_path}\n\n(Instale PyMuPDF para vista previa en GUI:\npip install PyMuPDF)",
                       ha='center', va='center', transform=ax.transAxes,
                       fontsize=10, wrap=True)
                ax.axis('off')
            
            self.drawing_preview_canvas.figure.tight_layout()
            self.drawing_preview_canvas.draw()
            
        except Exception as e:
            logger.error(f"Error en vista previa: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error generando vista previa: {e}", parent=self)
    
    def _draw_part_preview(self, ax: plt.Axes, part_name: str, flute_data) -> None:
        """Dibuja una vista previa simplificada de una parte."""
        part_data = flute_data.data.get(part_name, {})
        measurements = part_data.get("measurements", [])
        
        if not measurements:
            return
        
        positions = [m.get('position', 0) for m in measurements]
        diameters = [m.get('diameter', 0) for m in measurements]
        radii = [d / 2.0 for d in diameters]
        
        # Normalizar posiciones
        min_pos = min(positions)
        positions_norm = [p - min_pos for p in positions]
        
        # Dibujar perfil
        ax.plot(positions_norm, radii, 'b-', linewidth=2, label='Interno')
        ax.plot(positions_norm, [-r for r in radii], 'b-', linewidth=2)
        ax.fill_between(positions_norm, radii, [-r for r in radii], alpha=0.2, color='blue')
        
        # Dibujar agujeros
        hole_positions = part_data.get("Holes position", [])
        hole_diameters = part_data.get("Holes diameter", [])
        
        for pos, diam in zip(hole_positions, hole_diameters):
            pos_norm = pos - min_pos
            radius = diam / 2.0
            ax.plot(pos_norm, 0, 'ro', markersize=8, markerfacecolor='red', markeredgecolor='darkred')
            ax.axvline(pos_norm, color='red', linestyle=':', alpha=0.3)
        
        ax.set_title(f"{part_name.capitalize()}", fontweight='bold')
        ax.set_xlabel("Distancia desde extremo (mm)")
        ax.set_ylabel("Radio (mm)")
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.legend()
    
    def _export_3d_model(self) -> None:
        """Exporta modelo 3D."""
        if not self.flute_data_list:
            messagebox.showwarning("Advertencia", "Cargue al menos una flauta", parent=self)
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".stl",
            filetypes=[("STL files", "*.stl"), ("STEP files", "*.step"), ("All files", "*.*")]
        )
        if filename:
            try:
                model_3d = Flute3DModel(self.flute_data_list[0])
                model_3d.generate_assembly_model()
                
                if filename.endswith('.stl'):
                    model_3d.export_to_stl(filename)
                elif filename.endswith('.step'):
                    model_3d.export_to_step(filename)
                
                messagebox.showinfo("Éxito", f"Modelo 3D exportado: {filename}", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Error exportando modelo 3D: {e}", parent=self)
    
    def _export_analysis(self) -> None:
        """Exporta resultados de análisis."""
        if not self.analyzer:
            messagebox.showwarning("Advertencia", "Cargue flautas para analizar", parent=self)
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("JSON files", "*.json"), ("PDF files", "*.pdf")]
        )
        if filename:
            try:
                if filename.endswith('.csv'):
                    self.analyzer.export_results_to_csv(filename)
                elif filename.endswith('.json'):
                    self.analyzer.export_results_to_json(filename)
                elif filename.endswith('.pdf'):
                    self.analyzer.generate_summary_report(filename)
                
                messagebox.showinfo("Éxito", f"Análisis exportado: {filename}", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Error exportando análisis: {e}", parent=self)
    
    def _open_perturbation_gui(self) -> None:
        """Abre la GUI de perturbaciones."""
        if not self.flute_data_list:
            messagebox.showwarning("Advertencia", "Cargue al menos una flauta", parent=self)
            return
        
        PerturbationGUI(self, self.flute_data_list[0])
    
    def _open_geometry_modifier(self) -> None:
        """Abre el editor de modificación de geometría."""
        if not self.flute_data_list:
            messagebox.showwarning("Advertencia", "Cargue al menos una flauta", parent=self)
            return
        
        # Por ahora, mostrar mensaje (se puede extender con una GUI completa)
        messagebox.showinfo("Información", "Funcionalidad de modificación de geometría disponible.\nUse el módulo geometry_modifier para programar modificaciones.", parent=self)
    
    def _on_close(self) -> None:
        """Maneja el cierre de la aplicación."""
        if messagebox.askokcancel("Salir", "¿Está seguro de que desea salir?"):
            plt.close('all')
            self.destroy()


if __name__ == "__main__":
    app = UnifiedFluteGUI()
    app.mainloop()

