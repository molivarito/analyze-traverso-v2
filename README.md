# Traverso Analyzer

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Acoustic analysis, design, and optimization tool for traverso (baroque) flutes**

A comprehensive scientific tool for analyzing flute geometry, simulating acoustic response, and optimizing instrument design using OpenWind acoustic simulation.

---

## 🌍 Languages / Idiomas

- [English](#english-documentation)
- [Español](#documentación-en-español)

---

## English Documentation

### 📖 Quick Links

- **[Installation Guide](INSTALL.md)** - Detailed setup instructions
- **[Data Setup Guide](DATA_SETUP.md)** - Configure data paths and manage files
- **[Architecture](ARCHITECTURE.md)** - System design and module overview
- **[Contributing](CONTRIBUTING.md)** - Development guidelines
- **[Deprecations](DEPRECATIONS.md)** - Legacy code status

### ✨ Features

- **Acoustic Analysis**: Calculate impedance, admittance, resonances, and advanced metrics
  - Inharmonicity (cents differences)
  - MOC (Modal Octave Compression)
  - B_I and ESPE metrics
  - Q-factor, harmonic ratios, phase coherence

- **Geometric Modeling**: Design and modify flute geometry
  - Interactive 2D profile editing
  - 3D visualization
  - Part-based structure (headjoint, body sections, footjoint)

- **Sensitivity Analysis**: Study parameter variations
  - Hole undercut analysis
  - Bore taper sensitivity
  - Cork position optimization

- **Database Management**: SQLite-based persistence
  - Cached acoustic calculations
  - Flute geometry library
  - Result tracking

- **Fabrication Support**:
  - G-code generation for CNC machining
  - Engineering drawings (PDF)

- **Optimization**:
  - Embouchure height tuning
  - Multi-parameter optimization

### 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run main GUI application
python unified_flute_gui_qt.py

# Or run specialized tools
python flute_experimenter.py      # Interactive geometry editor
python flute_optimizer_gui.py     # Embouchure optimizer
```

See [INSTALL.md](INSTALL.md) for detailed installation instructions including OpenWind setup.

### 📱 Applications

#### ⭐ `unified_flute_gui_qt.py` - Main Application (Recommended)

Complete GUI with all features:
- Geometry visualization (2D and 3D)
- Acoustic analysis and comparison
- Database management
- Engineering drawings
- G-code generation
- Sensitivity analysis integration

**Framework**: PyQt5

#### `flute_experimenter.py` - Interactive Geometry Editor

- Load and analyze flutes
- **Interactive graphic editing** (drag points and holes)
- Real-time acoustic comparison (original vs. modified)
- Save modified geometries
- Study geometric impact on acoustics

#### `flute_optimizer_gui.py` - Embouchure Optimizer

- Optimize chimney/cork height for each note
- Target tuning based on reference pitch (e.g., A=415Hz) and temperature
- Compare before/after results
- Admittance and inharmonicity analysis

#### `flute_geometry_editor_qt.py` - Detailed Geometry Editor

Precise geometric modifications with detailed controls.

#### Legacy/Deprecated Applications

⚠️ The following may be legacy code (see [DEPRECATIONS.md](DEPRECATIONS.md)):
- `gui.py` - Original Tkinter GUI
- `gui_db.py` - Database-focused Tkinter GUI
- `unified_flute_gui.py` - Earlier unified Tkinter GUI

**Recommendation**: Use `unified_flute_gui_qt.py` for new work.

### 📚 Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture and design |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development guidelines |
| [DATA_SETUP.md](DATA_SETUP.md) | Data path configuration and file management |
| [DEPRECATIONS.md](DEPRECATIONS.md) | Legacy code status |
| [INSTALL.md](INSTALL.md) | Installation instructions |
| [SENSITIVITY_ANALYSIS_README.md](SENSITIVITY_ANALYSIS_README.md) | Sensitivity analysis guide |
| [REPORTE_ESTADISTICO_README.md](REPORTE_ESTADISTICO_README.md) | Statistical report guide |

### 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# See coverage report
open htmlcov/index.html
```

See [tests/README.md](tests/README.md) for testing details.

### 🛠️ Development

```bash
# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-cov black flake8 mypy

# Format code
black .

# Lint code
flake8 .

# Type check (gradually being adopted)
mypy .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed development workflow.

### 📄 License

MIT License - see LICENSE file for details.

### 🙏 Acknowledgments

- **OpenWind** - Acoustic simulation library
- Scientific community for acoustic modeling research

---

## Documentación en Español

### 📖 Enlaces Rápidos

- **[Guía de Instalación](INSTALL.md)** - Instrucciones detalladas de configuración
- **[Guía de Configuración de Datos](DATA_SETUP.md)** - Configurar rutas y gestionar archivos
- **[Arquitectura](ARCHITECTURE.md)** - Diseño del sistema y módulos
- **[Contribución](CONTRIBUTING.md)** - Guías de desarrollo
- **[Deprecaciones](DEPRECATIONS.md)** - Estado del código legacy

### ✨ Características

- **Análisis Acústico**: Calcula impedancia, admitancia, resonancias y métricas avanzadas
  - Inharmonicidad (diferencias en cents)
  - MOC (Modal Octave Compression)
  - Métricas B_I y ESPE
  - Factor Q, ratios armónicos, coherencia de fase

- **Modelado Geométrico**: Diseño y modificación de geometría de flautas
  - Edición interactiva de perfiles 2D
  - Visualización 3D
  - Estructura por partes (cabeza, cuerpo, pie)

- **Análisis de Sensibilidad**: Estudio de variaciones de parámetros
  - Análisis de undercut de agujeros
  - Sensibilidad de conicidad del tubo
  - Optimización de posición del corcho

- **Gestión de Base de Datos**: Persistencia basada en SQLite
  - Cálculos acústicos en caché
  - Biblioteca de geometrías de flautas
  - Seguimiento de resultados

- **Soporte de Fabricación**:
  - Generación de G-code para CNC
  - Planos de ingeniería (PDF)

- **Optimización**:
  - Ajuste de altura de embocadura
  - Optimización multi-parámetro

### 🚀 Inicio Rápido

```bash
# Instalar dependencias
pip install -r requirements.txt

# Ejecutar aplicación GUI principal
python unified_flute_gui_qt.py

# O ejecutar herramientas especializadas
python flute_experimenter.py      # Editor de geometría interactivo
python flute_optimizer_gui.py     # Optimizador de embocadura
```

Ver [INSTALL.md](INSTALL.md) para instrucciones detalladas incluyendo configuración de OpenWind.

### 📱 Aplicaciones

#### ⭐ `unified_flute_gui_qt.py` - Aplicación Principal (Recomendado)

GUI completa con todas las características:
- Visualización de geometría (2D y 3D)
- Análisis acústico y comparación
- Gestión de base de datos
- Planos de ingeniería
- Generación de G-code
- Integración de análisis de sensibilidad

**Framework**: PyQt5

#### `flute_experimenter.py` - Editor Geométrico Interactivo

- Carga y analiza flautas
- **Edición gráfica interactiva** (arrastrando puntos y agujeros)
- Comparación acústica en tiempo real (original vs. modificada)
- Guarda geometrías modificadas
- Estudia impacto geométrico en acústica

#### `flute_optimizer_gui.py` - Optimizador de Embocadura

- Optimiza altura de chimenea/corcho para cada nota
- Afinación objetivo basada en diapasón (ej. La=415Hz) y temperatura
- Compara resultados antes/después
- Análisis de admitancia e inharmonicidad

#### `flute_geometry_editor_qt.py` - Editor Geométrico Detallado

Modificaciones geométricas precisas con controles detallados.

#### Aplicaciones Legacy/Deprecadas

⚠️ Las siguientes pueden ser código legacy (ver [DEPRECATIONS.md](DEPRECATIONS.md)):
- `gui.py` - GUI Tkinter original
- `gui_db.py` - GUI Tkinter enfocada en base de datos
- `unified_flute_gui.py` - GUI Tkinter unificada anterior

**Recomendación**: Usar `unified_flute_gui_qt.py` para trabajo nuevo.

### 📚 Documentación Adicional

| Documento | Descripción |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Arquitectura y diseño del sistema |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Guías de desarrollo |
| [DATA_SETUP.md](DATA_SETUP.md) | Configuración de rutas y gestión de archivos |
| [DEPRECATIONS.md](DEPRECATIONS.md) | Estado del código legacy |
| [INSTALL.md](INSTALL.md) | Instrucciones de instalación |
| [SENSITIVITY_ANALYSIS_README.md](SENSITIVITY_ANALYSIS_README.md) | Guía de análisis de sensibilidad |
| [REPORTE_ESTADISTICO_README.md](REPORTE_ESTADISTICO_README.md) | Guía de reportes estadísticos |

### 🧪 Pruebas

```bash
# Ejecutar todas las pruebas
pytest

# Ejecutar con cobertura
pytest --cov=. --cov-report=html

# Ver reporte de cobertura
open htmlcov/index.html
```

Ver [tests/README.md](tests/README.md) para detalles sobre pruebas.

### 🛠️ Desarrollo

```bash
# Instalar dependencias de desarrollo
pip install -r requirements.txt
pip install pytest pytest-cov black flake8 mypy

# Formatear código
black .

# Lint código
flake8 .

# Type checking (adoptándose gradualmente)
mypy .
```

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para flujo de trabajo de desarrollo detallado.

### 📄 Licencia

Licencia MIT - ver archivo LICENSE para detalles.

### 🙏 Agradecimientos

- **OpenWind** - Biblioteca de simulación acústica
- Comunidad científica por investigación en modelado acústico

---

## Project Structure / Estructura del Proyecto

```
.
├── Core Data Models / Modelos de Datos Principales
│   ├── flute_data.py              # JSON-based flute data model
│   ├── flute_data_db.py           # Database-backed flute data
│   └── constants.py               # Physical constants and utilities
│
├── Business Logic / Lógica de Negocio
│   ├── analysis_module.py         # Unified acoustic analysis
│   ├── flute_operations.py        # Acoustic operations and plotting
│   ├── sensitivity_analysis.py    # Parametric sensitivity analysis
│   └── geometry_modifier.py       # Geometry modification tools
│
├── Database / Base de Datos
│   ├── db_schema.py              # SQLite schema
│   ├── flute_db_manager.py       # Database operations
│   └── impedance_serializer.py   # Result caching
│
├── GUI Applications / Aplicaciones GUI
│   ├── unified_flute_gui_qt.py   # ⭐ Main application
│   ├── flute_experimenter.py     # Interactive editor
│   └── flute_optimizer_gui.py    # Optimizer tool
│
├── Fabrication / Fabricación
│   ├── gcode_generator.py        # CNC code generation
│   └── engineering_drawings.py   # Technical drawings
│
├── Tests / Pruebas
│   └── tests/                    # Test suite
│
└── Documentation / Documentación
    ├── README.md                 # This file / Este archivo
    ├── ARCHITECTURE.md           # Architecture details
    ├── CONTRIBUTING.md           # Development guide
    └── INSTALL.md                # Installation guide
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation.

---

**Version**: 2.0.0
**Last Updated**: 2026-01-12
