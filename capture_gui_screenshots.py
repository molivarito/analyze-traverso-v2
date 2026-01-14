#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para capturar screenshots automáticamente de la GUI de análisis de flautas.
Este script debe ejecutarse DESPUÉS de lanzar unified_flute_gui_qt.py
"""

import time
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap

SCREENSHOTS_DIR = "presentation_screenshots"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def find_main_window():
    """Encuentra la ventana principal de la aplicación."""
    app = QApplication.instance()
    if app is None:
        print("No se encontró una aplicación Qt corriendo")
        return None
    
    for widget in app.topLevelWidgets():
        if widget.isVisible() and hasattr(widget, 'centralWidget'):
            return widget
    return None

def capture_widget(widget, filename):
    """Captura un screenshot de un widget específico."""
    pixmap = widget.grab()
    filepath = os.path.join(SCREENSHOTS_DIR, filename)
    pixmap.save(filepath)
    print(f"✓ Capturado: {filepath}")
    return filepath

def take_screenshots():
    """Toma capturas de pantalla de las diferentes vistas de la aplicación."""
    main_window = find_main_window()
    
    if main_window is None:
        print("ERROR: No se pudo encontrar la ventana principal")
        print("Asegúrate de que unified_flute_gui_qt.py esté corriendo")
        return
    
    print("Ventana principal encontrada, comenzando capturas...")
    
    # Captura ventana completa
    capture_widget(main_window, "real_gui_main_window.png")
    
    # Intentar acceder al tab widget
    if hasattr(main_window, 'tab_widget'):
        tab_widget = main_window.tab_widget
        
        # Guardar tab actual
        current_index = tab_widget.currentIndex()
        
        # Recorrer tabs y capturar
        tab_names = {
            0: "geometry",
            1: "acoustic_analysis", 
            2: "database",
            3: "sensitivity",
            4: "3d_visualization",
            5: "engineering_drawings",
            6: "gcode"
        }
        
        for index, name in tab_names.items():
            if index < tab_widget.count():
                tab_widget.setCurrentIndex(index)
                QApplication.processEvents()
                time.sleep(0.5)  # Esperar a que se renderice
                
                current_widget = tab_widget.currentWidget()
                if current_widget:
                    capture_widget(current_widget, f"real_{name}_tab.png")
        
        # Restaurar tab original
        tab_widget.setCurrentIndex(current_index)
    
    print("\n✓ Capturas completadas!")
    
    # Salir de la aplicación
    QTimer.singleShot(1000, QApplication.quit)

if __name__ == "__main__":
    app = QApplication.instance()
    if app is None:
        print("ERROR: Este script debe ejecutarse mientras unified_flute_gui_qt.py está corriendo")
        print("Intenta ejecutarlo desde la consola de Python dentro de la aplicación")
    else:
        # Esperar un momento para que la UI esté completamente cargada
        QTimer.singleShot(2000, take_screenshots)
        app.exec_()
