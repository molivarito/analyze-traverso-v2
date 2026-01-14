"""
Widget para visualizar planos y diagramas de flautas.

Soporta visualización de archivos PDF e imágenes (PNG, JPG, JPEG)
con funcionalidades de zoom y navegación.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QComboBox, QMessageBox, QFileDialog
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap, QImage

logger = logging.getLogger(__name__)

# Intentar importar soporte para PDF (lazy import para evitar problemas con QApplication)
PDF_SUPPORT = None  # None = no verificado aún, True/False = ya verificado
PDF_BACKEND = None
_QWebEngineView = None

def _check_pdf_support():
    """
    Verifica y configura soporte PDF (lazy import).
    
    NOTA: Esta función NO realiza ningún import. Solo marca que se debe intentar
    importar cuando sea necesario. La verificación real se hace en _import_webengine_view().
    """
    global PDF_SUPPORT, PDF_BACKEND
    
    # Si ya fue verificado, retornar el resultado
    if PDF_SUPPORT is True:
        return True
    if PDF_SUPPORT is False:
        return False
    
    # Verificar que QApplication existe y está completamente inicializado
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            # No hay QApplication aún, retornar False sin intentar importar
            logger.debug("QApplication no existe aún, posponiendo verificación de PDF")
            return False
        
        # Verificar adicional que QApplication está completamente inicializado
        try:
            _ = app.applicationName()
        except:
            # QApplication existe pero no está completamente listo
            logger.debug("QApplication existe pero no está completamente inicializado")
            return False
            
    except Exception as e:
        # Si no se puede verificar QApplication, no intentar importar
        logger.debug(f"No se pudo verificar QApplication: {e}")
        return False
    
    # Simplemente marcar que QApplication está listo y que se debe intentar el import
    # NO hacer ningún import aquí, ni siquiera find_spec que puede causar efectos secundarios
    # La verificación real se hará en _import_webengine_view()
    logger.debug("QApplication está listo para intentar cargar soporte PDF")
    return True  # Retornar True para indicar que se puede intentar


def _import_webengine_view():
    """
    Importa QWebEngineView de manera segura, solo cuando realmente se necesita.
    
    Returns:
        La clase QWebEngineView o None si no está disponible.
    """
    global _QWebEngineView, PDF_SUPPORT, PDF_BACKEND
    
    # Si ya se importó, retornar la clase
    if _QWebEngineView is not None:
        return _QWebEngineView
    
    # Si ya se verificó que no está disponible, retornar None
    if PDF_SUPPORT is False:
        return None
    
    # Verificar que QApplication existe antes de importar
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            logger.debug("QApplication no existe, no se puede importar QWebEngineView")
            return None
        
        # Verificar que QApplication está completamente inicializado
        try:
            _ = app.applicationName()
        except:
            logger.debug("QApplication no está completamente inicializado")
            return None
    except Exception as e:
        logger.debug(f"Error verificando QApplication antes de importar QWebEngineView: {e}")
        return None
    
    # Ahora importar QWebEngineView - este es el ÚNICO lugar donde se hace el import
    try:
        from PyQt5.QtWebEngineWidgets import QWebEngineView
        _QWebEngineView = QWebEngineView
        PDF_SUPPORT = True
        PDF_BACKEND = 'webengine'
        logger.info("Soporte PDF disponible: PyQt5 WebEngine")
        return QWebEngineView
    except ImportError:
        logger.debug("QWebEngineView no está disponible (ImportError)")
        PDF_SUPPORT = False
        PDF_BACKEND = None
        return None
    except Exception as e:
        logger.warning(f"Error importando QWebEngineView: {e}")
        PDF_SUPPORT = False
        PDF_BACKEND = None
        return None


class FlutePlanViewer(QWidget):
    """
    Widget para visualizar planos de flautas.
    
    Soporta:
    - Archivos PDF (si PyQt5 tiene soporte)
    - Imágenes (PNG, JPG, JPEG)
    - Zoom in/out
    - Navegación entre múltiples planos
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_plan_path: Optional[Path] = None
        self.available_plans: List[Path] = []
        self.zoom_factor = 1.0
        self._init_ui()
    
    def _init_ui(self):
        """Inicializa la interfaz de usuario."""
        layout = QVBoxLayout(self)
        
        # Barra de herramientas superior
        toolbar = QHBoxLayout()
        
        # Selector de planos
        toolbar.addWidget(QLabel("Plano:"))
        self.plan_selector = QComboBox()
        self.plan_selector.currentTextChanged.connect(self._on_plan_selected)
        toolbar.addWidget(self.plan_selector)
        
        toolbar.addStretch()
        
        # Botones de zoom
        zoom_out_btn = QPushButton("🔍-")
        zoom_out_btn.setToolTip("Alejar")
        zoom_out_btn.clicked.connect(self._zoom_out)
        toolbar.addWidget(zoom_out_btn)
        
        zoom_reset_btn = QPushButton("🔍")
        zoom_reset_btn.setToolTip("Tamaño original")
        zoom_reset_btn.clicked.connect(self._zoom_reset)
        toolbar.addWidget(zoom_reset_btn)
        
        zoom_in_btn = QPushButton("🔍+")
        zoom_in_btn.setToolTip("Acercar")
        zoom_in_btn.clicked.connect(self._zoom_in)
        toolbar.addWidget(zoom_in_btn)
        
        # Botón para abrir en aplicación externa
        open_external_btn = QPushButton("Abrir Externamente")
        open_external_btn.setToolTip("Abrir el plano en la aplicación predeterminada del sistema")
        open_external_btn.clicked.connect(self._open_external)
        toolbar.addWidget(open_external_btn)
        
        layout.addLayout(toolbar)
        
        # Área de visualización con scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignCenter)
        
        # Widget contenedor para el contenido
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignCenter)
        
        # Label para mostrar contenido (imágenes o mensaje)
        self.display_label = QLabel()
        self.display_label.setAlignment(Qt.AlignCenter)
        self.display_label.setText("No hay planos disponibles para esta flauta")
        self.display_label.setStyleSheet("color: gray; font-size: 14px; padding: 50px;")
        self.content_layout.addWidget(self.display_label)
        
        scroll_area.setWidget(self.content_widget)
        layout.addWidget(scroll_area)
        
        # Almacenar referencia al scroll area para ajustar zoom
        self.scroll_area = scroll_area
    
    def set_plans(self, plans: Dict[str, Any]):
        """
        Establece los planos disponibles para mostrar.
        
        Args:
            plans: Diccionario con estructura:
                - 'general_plan': Path al plano general (opcional)
                - 'part_plans': Dict con planos por parte (opcional)
                - 'all_plans': Lista de todos los planos (requerido)
        """
        self.available_plans = plans.get('all_plans', [])
        
        # Actualizar selector
        self.plan_selector.clear()
        
        if not self.available_plans:
            self.display_label.setText("No hay planos disponibles para esta flauta")
            self.display_label.setStyleSheet("color: gray; font-size: 14px; padding: 50px;")
            self.current_plan_path = None
            return
        
        # Agregar planos al selector
        for plan_path in self.available_plans:
            plan_name = plan_path.name
            # Si es plano general, marcarlo
            if plans.get('general_plan') == plan_path:
                plan_name = f"📄 {plan_name} (General)"
            # Si es plano de parte, identificar la parte
            else:
                for part, part_plan in plans.get('part_plans', {}).items():
                    if part_plan == plan_path:
                        plan_name = f"📄 {plan_name} ({part})"
                        break
            self.plan_selector.addItem(plan_name, plan_path)
        
        # Mostrar el primer plano (o el general si existe)
        if plans.get('general_plan'):
            general_path = plans['general_plan']
            index = self.available_plans.index(general_path)
            self.plan_selector.setCurrentIndex(index)
        else:
            self.plan_selector.setCurrentIndex(0)
        
        # Cargar el plano seleccionado (solo si hay planos y QApplication existe)
        if self.available_plans:
            # Verificar que QApplication existe antes de cargar
            try:
                from PyQt5.QtWidgets import QApplication
                if QApplication.instance() is not None:
                    self._load_plan(self.available_plans[0])
                else:
                    # QApplication no existe aún, solo actualizar selector
                    self.current_plan_path = self.available_plans[0]
            except:
                # Si hay error, solo actualizar selector
                self.current_plan_path = self.available_plans[0] if self.available_plans else None
    
    def _on_plan_selected(self, text: str):
        """Maneja la selección de un plano diferente."""
        index = self.plan_selector.currentIndex()
        if index >= 0:
            plan_path = self.plan_selector.itemData(index)
            if plan_path:
                self._load_plan(plan_path)
    
    def _load_plan(self, plan_path: Optional[Path]):
        """
        Carga y muestra un plano.
        
        Args:
            plan_path: Ruta al archivo del plano.
        """
        if not plan_path or not plan_path.exists():
            self.display_label.setText("Error: El archivo del plano no existe")
            self.display_label.setStyleSheet("color: red; font-size: 14px; padding: 50px;")
            self.current_plan_path = None
            return
        
        # Verificar que QApplication existe antes de cargar
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app is None:
                # QApplication no existe aún, solo guardar la ruta
                self.current_plan_path = plan_path
                self.display_label.setText(f"Plano: {plan_path.name}\n\nQApplication no está listo aún.")
                self.display_label.setStyleSheet("color: blue; font-size: 14px; padding: 50px;")
                return
        except Exception as e:
            # Si no se puede verificar, no intentar cargar
            logger.debug(f"Error verificando QApplication en _load_plan: {e}")
            self.current_plan_path = plan_path
            return
        
        self.current_plan_path = plan_path
        self.zoom_factor = 1.0
        
        # Detectar tipo de archivo
        ext = plan_path.suffix.lower()
        
        if ext == '.pdf':
            self._load_pdf(plan_path)
        elif ext in ['.png', '.jpg', '.jpeg']:
            self._load_image(plan_path)
        else:
            self.display_label.setText(f"Formato no soportado: {ext}")
            self.display_label.setStyleSheet("color: red; font-size: 14px; padding: 50px;")
    
    def _load_pdf(self, pdf_path: Path):
        """
        Muestra información sobre el PDF y permite abrirlo externamente.
        
        NOTA: El visor PDF interno está desactivado debido a problemas de inicialización
        con QtWebEngine que causan crashes en algunas configuraciones. Los PDFs se pueden
        abrir externamente usando el botón 'Abrir Externamente'.
        """
        # Mostrar información del PDF con un ícono grande
        pdf_size = pdf_path.stat().st_size / 1024  # tamaño en KB
        
        info_text = f"""
📄 Plano PDF Disponible

Archivo: {pdf_path.name}
Tamaño: {pdf_size:.1f} KB

Use el botón 'Abrir Externamente' para visualizar
el PDF en su visor predeterminado.

Tip: Puede hacer doble clic en el nombre del archivo
arriba para cambiar entre diferentes planos.
"""
        
        self.display_label.setText(info_text.strip())
        self.display_label.setStyleSheet(
            "color: #2c3e50; font-size: 14px; padding: 50px; "
            "background-color: #ecf0f1; border-radius: 10px;"
        )
        logger.debug(f"PDF detectado: {pdf_path.name} ({pdf_size:.1f} KB)")
    
    def _load_image(self, image_path: Path):
        """Carga una imagen."""
        try:
            pixmap = QPixmap(str(image_path))
            if pixmap.isNull():
                raise ValueError("No se pudo cargar la imagen")
            
            # Ajustar tamaño inicial (mostrar completo pero no más grande que el widget)
            scaled_pixmap = pixmap.scaled(
                pixmap.size() * self.zoom_factor,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            self.display_label.setPixmap(scaled_pixmap)
            self.display_label.setStyleSheet("")
            self.current_pixmap = pixmap  # Guardar pixmap original para zoom
            
        except Exception as e:
            logger.error(f"Error cargando imagen {image_path}: {e}")
            self.display_label.setText(f"Error cargando imagen: {str(e)}")
            self.display_label.setStyleSheet("color: red; font-size: 14px; padding: 50px;")
    
    def _clear_content(self):
        """Limpia el contenido del widget."""
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def _zoom_in(self):
        """Aumenta el zoom."""
        if hasattr(self, 'current_pixmap') and self.current_pixmap:
            self.zoom_factor = min(self.zoom_factor * 1.2, 5.0)
            self._update_image_zoom()
    
    def _zoom_out(self):
        """Disminuye el zoom."""
        if hasattr(self, 'current_pixmap') and self.current_pixmap:
            self.zoom_factor = max(self.zoom_factor / 1.2, 0.1)
            self._update_image_zoom()
    
    def _zoom_reset(self):
        """Restablece el zoom al tamaño original."""
        if hasattr(self, 'current_pixmap') and self.current_pixmap:
            self.zoom_factor = 1.0
            self._update_image_zoom()
    
    def _update_image_zoom(self):
        """Actualiza la imagen con el factor de zoom actual."""
        if hasattr(self, 'current_pixmap') and self.current_pixmap:
            scaled_pixmap = self.current_pixmap.scaled(
                self.current_pixmap.size() * self.zoom_factor,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.display_label.setPixmap(scaled_pixmap)
    
    def _open_external(self):
        """Abre el plano en la aplicación externa predeterminada."""
        if not self.current_plan_path:
            QMessageBox.warning(self, "Sin plano", "No hay ningún plano seleccionado para abrir.")
            return
        
        try:
            import subprocess
            import platform
            
            path_str = str(self.current_plan_path.absolute())
            
            if platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', path_str])
            elif platform.system() == 'Windows':
                subprocess.run(['start', path_str], shell=True)
            else:  # Linux
                subprocess.run(['xdg-open', path_str])
        except Exception as e:
            logger.error(f"Error abriendo archivo externamente: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"No se pudo abrir el archivo externamente:\n{str(e)}"
            )

