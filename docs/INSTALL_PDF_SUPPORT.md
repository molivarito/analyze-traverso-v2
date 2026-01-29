# Instalación de Soporte PDF para Visualización de Planos

El visualizador de planos puede mostrar imágenes (PNG, JPG) sin dependencias adicionales, pero para ver archivos PDF necesita una de las siguientes opciones:

## Opción 1: PyQt5 WebEngine (Recomendado)

### Con conda (recomendado si usas el entorno conda OpenWind):
```bash
conda activate OpenWind
conda install pyqtwebengine
```

### Con pip:
```bash
pip install PyQtWebEngine
```

**Nota:** Si usas conda, es mejor usar `conda install` para evitar conflictos de dependencias.

## Opción 2: poppler-qt5 (Alternativa)

### macOS (con Homebrew):
```bash
brew install poppler
pip install PyQt5
```

**Nota:** Esta opción es menos común y puede requerir compilación adicional.

## Verificación

Después de instalar, puedes verificar que funciona ejecutando:

```python
from PyQt5.QtWebEngineWidgets import QWebEngineView
print("✓ Soporte PDF disponible")
```

## Uso sin Soporte PDF

Si no instalas el soporte PDF, el visualizador seguirá funcionando para:
- ✅ Imágenes PNG
- ✅ Imágenes JPG/JPEG
- ❌ PDFs (mostrará mensaje para abrir externamente)

Los PDFs siempre se pueden abrir usando el botón "Abrir Externamente" que abre el archivo en la aplicación predeterminada del sistema (Preview en macOS, Adobe Reader en Windows, etc.).

