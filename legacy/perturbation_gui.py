"""
GUI interactiva para aplicar perturbaciones geométricas a flautas.

Permite variar interactivamente:
- Ángulo de agujeros
- Chimenea de agujeros
- Tamaño de agujeros
Con visualización en tiempo real.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

from geometry_perturbation import GeometryPerturbator
from flute_operations import FluteOperations
from constants import FLUTE_PARTS_ORDER, BASE_COLORS

logger = logging.getLogger(__name__)


class PerturbationGUI(tk.Toplevel):
    """
    Ventana GUI para aplicar perturbaciones geométricas.
    """
    
    def __init__(self, parent, flute_data):
        """
        Inicializa la GUI de perturbaciones.
        
        Args:
            parent: Ventana padre.
            flute_data: Instancia de FluteData o FluteDataDB.
        """
        super().__init__(parent)
        self.title(f"Perturbaciones Geométricas - {flute_data.flute_model}")
        self.geometry("1400x900")
        
        self.flute_data = flute_data
        self.perturbator = GeometryPerturbator(flute_data)
        self.current_perturbations: List[Dict[str, Any]] = []
        
        self._create_widgets()
        self._update_plots()
    
    def _create_widgets(self) -> None:
        """Crea los widgets de la interfaz."""
        # Frame principal con paneles
        main_paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Panel izquierdo: Controles
        control_frame = ttk.Frame(main_paned, width=350)
        main_paned.add(control_frame, weight=0)
        
        # Panel derecho: Visualizaciones
        viz_frame = ttk.Frame(main_paned)
        main_paned.add(viz_frame, weight=1)
        
        self._create_control_panel(control_frame)
        self._create_visualization_panel(viz_frame)
    
    def _create_control_panel(self, parent: ttk.Frame) -> None:
        """Crea el panel de controles."""
        # Título
        title_label = ttk.Label(parent, text="Controles de Perturbación", font=('Arial', 12, 'bold'))
        title_label.pack(pady=10)
        
        # Selector de parte
        part_frame = ttk.LabelFrame(parent, text="Parte", padding=10)
        part_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.part_var = tk.StringVar(value=FLUTE_PARTS_ORDER[0])
        part_combo = ttk.Combobox(part_frame, textvariable=self.part_var, values=FLUTE_PARTS_ORDER, state='readonly')
        part_combo.pack(fill=tk.X)
        part_combo.bind('<<ComboboxSelected>>', lambda e: self._update_hole_list())
        
        # Selector de agujero
        hole_frame = ttk.LabelFrame(parent, text="Agujero", padding=10)
        hole_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.hole_var = tk.StringVar()
        self.hole_combo = ttk.Combobox(hole_frame, textvariable=self.hole_var, state='readonly')
        self.hole_combo.pack(fill=tk.X)
        self._update_hole_list()
        
        # Tipo de perturbación
        pert_type_frame = ttk.LabelFrame(parent, text="Tipo de Perturbación", padding=10)
        pert_type_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.pert_type_var = tk.StringVar(value='size')
        ttk.Radiobutton(pert_type_frame, text="Tamaño (diámetro)", variable=self.pert_type_var, value='size').pack(anchor=tk.W)
        ttk.Radiobutton(pert_type_frame, text="Chimenea (altura)", variable=self.pert_type_var, value='chimney').pack(anchor=tk.W)
        ttk.Radiobutton(pert_type_frame, text="Ángulo", variable=self.pert_type_var, value='angle').pack(anchor=tk.W)
        
        # Valor de perturbación
        value_frame = ttk.LabelFrame(parent, text="Valor de Perturbación", padding=10)
        value_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.value_var = tk.DoubleVar(value=0.0)
        self.value_scale = ttk.Scale(value_frame, from_=-5.0, to=5.0, variable=self.value_var, orient=tk.HORIZONTAL)
        self.value_scale.pack(fill=tk.X, padx=5)
        
        self.value_label = ttk.Label(value_frame, text="0.00")
        self.value_label.pack()
        self.value_scale.configure(command=self._on_value_change)
        
        # Tipo de variación (solo para tamaño)
        self.variation_type_var = tk.StringVar(value='absolute')
        variation_type_frame = ttk.LabelFrame(parent, text="Tipo de Variación", padding=10)
        variation_type_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Radiobutton(variation_type_frame, text="Absoluta (mm)", variable=self.variation_type_var, value='absolute').pack(anchor=tk.W)
        ttk.Radiobutton(variation_type_frame, text="Relativa (%)", variable=self.variation_type_var, value='relative').pack(anchor=tk.W)
        
        # Botones
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Button(button_frame, text="Aplicar Perturbación", command=self._apply_perturbation).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="Limpiar Todas", command=self._clear_perturbations).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="Guardar Configuración", command=self._save_configuration).pack(fill=tk.X, pady=2)
        ttk.Button(button_frame, text="Cargar Configuración", command=self._load_configuration).pack(fill=tk.X, pady=2)
        
        # Lista de perturbaciones aplicadas
        pert_list_frame = ttk.LabelFrame(parent, text="Perturbaciones Aplicadas", padding=10)
        pert_list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.pert_listbox = tk.Listbox(pert_list_frame, height=8)
        self.pert_listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(pert_list_frame, orient=tk.VERTICAL, command=self.pert_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.pert_listbox.configure(yscrollcommand=scrollbar.set)
    
    def _create_visualization_panel(self, parent: ttk.Frame) -> None:
        """Crea el panel de visualizaciones."""
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Pestaña de geometría
        geom_frame = ttk.Frame(notebook)
        notebook.add(geom_frame, text="Geometría")
        
        self.fig_geom, self.ax_geom = plt.subplots(figsize=(10, 6))
        self.canvas_geom = FigureCanvasTkAgg(self.fig_geom, geom_frame)
        self.canvas_geom.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Pestaña de análisis acústico
        acoustic_frame = ttk.Frame(notebook)
        notebook.add(acoustic_frame, text="Análisis Acústico")
        
        self.fig_acoustic, self.ax_acoustic = plt.subplots(figsize=(10, 6))
        self.canvas_acoustic = FigureCanvasTkAgg(self.fig_acoustic, acoustic_frame)
        self.canvas_acoustic.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def _update_hole_list(self) -> None:
        """Actualiza la lista de agujeros disponibles."""
        part_name = self.part_var.get()
        part_data = self.flute_data.data.get(part_name, {})
        hole_positions = part_data.get("Holes position", [])
        
        hole_labels = [f"Agujero {i} (pos: {pos:.1f}mm)" for i, pos in enumerate(hole_positions)]
        self.hole_combo['values'] = hole_labels
        if hole_labels:
            self.hole_var.set(hole_labels[0])
    
    def _on_value_change(self, value: str) -> None:
        """Actualiza la etiqueta cuando cambia el valor."""
        val = float(value)
        self.value_label.config(text=f"{val:.2f}")
    
    def _apply_perturbation(self) -> None:
        """Aplica la perturbación actual."""
        part_name = self.part_var.get()
        hole_selection = self.hole_var.get()
        
        if not hole_selection:
            messagebox.showwarning("Advertencia", "Seleccione un agujero")
            return
        
        # Extraer índice del agujero
        try:
            hole_index = int(hole_selection.split()[1])
        except (ValueError, IndexError):
            messagebox.showerror("Error", "Error al determinar índice del agujero")
            return
        
        pert_type = self.pert_type_var.get()
        variation = self.value_var.get()
        
        pert = {
            'type': pert_type,
            'part_name': part_name,
            'hole_index': hole_index,
            'variation': variation
        }
        
        if pert_type == 'size':
            pert['variation_type'] = self.variation_type_var.get()
        
        self.current_perturbations.append(pert)
        self._update_perturbation_list()
        self._update_plots()
    
    def _update_perturbation_list(self) -> None:
        """Actualiza la lista de perturbaciones aplicadas."""
        self.pert_listbox.delete(0, tk.END)
        for i, pert in enumerate(self.current_perturbations):
            desc = f"{i+1}. {pert['part_name']}, agujero {pert['hole_index']}, {pert['type']}: {pert['variation']:.2f}"
            self.pert_listbox.insert(tk.END, desc)
    
    def _clear_perturbations(self) -> None:
        """Limpia todas las perturbaciones."""
        if messagebox.askyesno("Confirmar", "¿Limpiar todas las perturbaciones?"):
            self.current_perturbations = []
            self._update_perturbation_list()
            self._update_plots()
    
    def _save_configuration(self) -> None:
        """Guarda la configuración de perturbaciones."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            import json
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.current_perturbations, f, indent=2)
            messagebox.showinfo("Éxito", f"Configuración guardada en {filename}")
    
    def _load_configuration(self) -> None:
        """Carga una configuración de perturbaciones."""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            import json
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.current_perturbations = json.load(f)
                self._update_perturbation_list()
                self._update_plots()
                messagebox.showinfo("Éxito", f"Configuración cargada desde {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Error cargando configuración: {e}")
    
    def _update_plots(self) -> None:
        """Actualiza los gráficos."""
        # Aplicar perturbaciones si hay alguna
        if self.current_perturbations:
            perturbed_data = self.perturbator.apply_multiple_perturbations(self.current_perturbations)
            if perturbed_data:
                self._plot_geometry_comparison(perturbed_data)
                self._plot_acoustic_comparison(perturbed_data)
            else:
                self._plot_geometry_original()
                self._plot_acoustic_original()
        else:
            self._plot_geometry_original()
            self._plot_acoustic_original()
    
    def _plot_geometry_comparison(self, perturbed_data) -> None:
        """Dibuja comparación de geometría original vs perturbada."""
        self.ax_geom.clear()
        
        # Original
        ops_orig = FluteOperations(self.flute_data)
        combined_orig = self.flute_data.combined_measurements
        if combined_orig:
            positions_orig = [m.get('position', 0) for m in combined_orig]
            diameters_orig = [m.get('diameter', 0) for m in combined_orig]
            radii_orig = [d / 2.0 for d in diameters_orig]
            self.ax_geom.plot(positions_orig, radii_orig, 'b-', linewidth=2, label='Original')
            self.ax_geom.plot(positions_orig, [-r for r in radii_orig], 'b-', linewidth=2)
        
        # Perturbado
        combined_pert = perturbed_data.combined_measurements
        if combined_pert:
            positions_pert = [m.get('position', 0) for m in combined_pert]
            diameters_pert = [m.get('diameter', 0) for m in combined_pert]
            radii_pert = [d / 2.0 for d in diameters_pert]
            self.ax_geom.plot(positions_pert, radii_pert, 'r--', linewidth=2, label='Perturbado')
            self.ax_geom.plot(positions_pert, [-r for r in radii_pert], 'r--', linewidth=2)
        
        self.ax_geom.set_xlabel('Posición (mm)')
        self.ax_geom.set_ylabel('Radio (mm)')
        self.ax_geom.set_title('Comparación de Geometría')
        self.ax_geom.legend()
        self.ax_geom.grid(True, linestyle=':', alpha=0.7)
        self.canvas_geom.draw()
    
    def _plot_geometry_original(self) -> None:
        """Dibuja solo la geometría original."""
        self.ax_geom.clear()
        ops = FluteOperations(self.flute_data)
        combined = self.flute_data.combined_measurements
        if combined:
            positions = [m.get('position', 0) for m in combined]
            diameters = [m.get('diameter', 0) for m in combined]
            radii = [d / 2.0 for d in diameters]
            self.ax_geom.plot(positions, radii, 'b-', linewidth=2, label='Original')
            self.ax_geom.plot(positions, [-r for r in radii], 'b-', linewidth=2)
        
        self.ax_geom.set_xlabel('Posición (mm)')
        self.ax_geom.set_ylabel('Radio (mm)')
        self.ax_geom.set_title('Geometría Original')
        self.ax_geom.legend()
        self.ax_geom.grid(True, linestyle=':', alpha=0.7)
        self.canvas_geom.draw()
    
    def _plot_acoustic_comparison(self, perturbed_data) -> None:
        """Dibuja comparación de análisis acústico."""
        self.ax_acoustic.clear()
        
        # Obtener primera nota disponible
        notes_orig = list(self.flute_data.acoustic_analysis.keys())
        notes_pert = list(perturbed_data.acoustic_analysis.keys()) if perturbed_data.acoustic_analysis else []
        
        if not notes_orig:
            self.ax_acoustic.text(0.5, 0.5, "No hay análisis acústico disponible", ha='center', va='center', transform=self.ax_acoustic.transAxes)
            self.canvas_acoustic.draw()
            return
        
        note = notes_orig[0]
        analysis_orig = self.flute_data.acoustic_analysis.get(note)
        analysis_pert = perturbed_data.acoustic_analysis.get(note) if perturbed_data.acoustic_analysis else None
        
        if analysis_orig:
            try:
                freq_orig = analysis_orig.frequencies
                imp_orig = analysis_orig.impedance
                self.ax_acoustic.plot(freq_orig, np.abs(imp_orig), 'b-', linewidth=2, label=f'Original ({note})')
            except Exception as e:
                logger.warning(f"Error plotando análisis original: {e}")
        
        if analysis_pert:
            try:
                freq_pert = analysis_pert.frequencies
                imp_pert = analysis_pert.impedance
                self.ax_acoustic.plot(freq_pert, np.abs(imp_pert), 'r--', linewidth=2, label=f'Perturbado ({note})')
            except Exception as e:
                logger.warning(f"Error plotando análisis perturbado: {e}")
        
        self.ax_acoustic.set_xlabel('Frecuencia (Hz)')
        self.ax_acoustic.set_ylabel('|Impedancia|')
        self.ax_acoustic.set_title('Comparación de Impedancia')
        self.ax_acoustic.legend()
        self.ax_acoustic.grid(True, linestyle=':', alpha=0.7)
        self.canvas_acoustic.draw()
    
    def _plot_acoustic_original(self) -> None:
        """Dibuja solo el análisis acústico original."""
        self.ax_acoustic.clear()
        
        notes = list(self.flute_data.acoustic_analysis.keys())
        if not notes:
            self.ax_acoustic.text(0.5, 0.5, "No hay análisis acústico disponible", ha='center', va='center', transform=self.ax_acoustic.transAxes)
            self.canvas_acoustic.draw()
            return
        
        note = notes[0]
        analysis = self.flute_data.acoustic_analysis.get(note)
        if analysis:
            try:
                freq = analysis.frequencies
                imp = analysis.impedance
                self.ax_acoustic.plot(freq, np.abs(imp), 'b-', linewidth=2, label=f'Original ({note})')
            except Exception as e:
                logger.warning(f"Error plotando análisis: {e}")
        
        self.ax_acoustic.set_xlabel('Frecuencia (Hz)')
        self.ax_acoustic.set_ylabel('|Impedancia|')
        self.ax_acoustic.set_title('Impedancia Original')
        self.ax_acoustic.legend()
        self.ax_acoustic.grid(True, linestyle=':', alpha=0.7)
        self.canvas_acoustic.draw()

