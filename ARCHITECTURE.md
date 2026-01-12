# Traverso Analyzer - Architecture Documentation

## Overview

This project is a scientific analysis, design, and optimization system for traverso flutes (baroque flutes). It combines acoustic simulation (via OpenWind), geometric modeling, database persistence, and interactive visualization.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface Layer                      │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ unified_flute_   │  │ Other GUI Apps   │                │
│  │ gui_qt.py        │  │ (experimenter,   │                │
│  │ (Main GUI)       │  │  optimizer, etc) │                │
│  └──────────────────┘  └──────────────────┘                │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                  Business Logic Layer                        │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Analysis & Operations                               │    │
│  │  - analysis_module.py (FluteAnalyzer)              │    │
│  │  - flute_operations.py (plotting, calculations)    │    │
│  │  - sensitivity_analysis.py                          │    │
│  └────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Geometry & Modification                             │    │
│  │  - geometry_modifier.py                             │    │
│  │  - geometry_perturbation.py                         │    │
│  │  - external_geometry_modeler.py                     │    │
│  └────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Fabrication                                         │    │
│  │  - gcode_generator.py                               │    │
│  │  - engineering_drawings.py                          │    │
│  └────────────────────────────────────────────────────┘    │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                    Data Layer                                │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Data Models                                         │    │
│  │  - flute_data.py (FluteData - JSON based)          │    │
│  │  - flute_data_db.py (FluteDataDB - DB based)       │    │
│  └────────────────────────────────────────────────────┘    │
│  ┌────────────────────────────────────────────────────┐    │
│  │ Database Management                                 │    │
│  │  - db_schema.py (schema definitions)                │    │
│  │  - flute_db_manager.py (CRUD operations)           │    │
│  │  - impedance_serializer.py (caching)                │    │
│  └────────────────────────────────────────────────────┘    │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                  External Services                           │
│  ┌────────────────────────────────────────────────────┐    │
│  │ - OpenWind (acoustic simulation)                    │    │
│  │ - SQLite Database (persistence)                     │    │
│  │ - Matplotlib (visualization)                        │    │
│  │ - PyQt5 (GUI framework)                             │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Core Modules

### Data Models

#### `flute_data.py`
- **Purpose**: Core data model for flute geometry (JSON-based)
- **Key Class**: `FluteData`
- **Responsibilities**:
  - Load/save flute geometry from/to JSON files
  - Calculate acoustic analysis via OpenWind
  - Store finger frequencies and analysis results
  - Handle part-based geometry (headjoint, left, right, foot)

#### `flute_data_db.py`
- **Purpose**: Database-backed extension of FluteData
- **Key Class**: `FluteDataDB` (extends `FluteData`)
- **Responsibilities**:
  - All FluteData capabilities
  - Automatic caching of acoustic analysis results in SQLite
  - Smart recalculation when parameters change
  - Reduced computation time via result reuse

### Business Logic

#### `analysis_module.py`
- **Purpose**: Unified acoustic analysis
- **Key Class**: `FluteAnalyzer`
- **Capabilities**:
  - Inharmonicity calculation (cents differences)
  - MOC (Modal Octave Compression)
  - B_I and ESPE metrics
  - Peak heights, Q-factor
  - Harmonic ratios, phase coherence
  - Export to CSV/JSON/PDF

#### `flute_operations.py`
- **Purpose**: Core acoustic and geometric operations
- **Key Class**: `FluteOperations`
- **Capabilities**:
  - Plot generation (geometry, admittance, analysis)
  - Interpolation and calculations
  - Comparative analysis across multiple flutes
- **⚠️ Note**: Large file (3606 lines) - candidate for refactoring

#### `sensitivity_analysis.py`
- **Purpose**: Parametric sensitivity analysis
- **Capabilities**:
  - Vary geometric parameters (undercut, taper, cork position, etc.)
  - Generate parameter sweep variants
  - Analyze acoustic impact of variations
  - Export sensitivity reports

#### `geometry_modifier.py` / `geometry_perturbation.py`
- **Purpose**: Geometric modification and perturbation
- **Capabilities**:
  - Apply systematic variations to geometry
  - Modify hole angles, positions, diameters
  - Adjust bore taper
  - Create variant flutes for analysis

### Fabrication

#### `gcode_generator.py`
- **Purpose**: Generate G-code for CNC machining
- **Capabilities**:
  - Convert flute geometry to toolpaths
  - Support for different CNC operations
  - Configurable parameters (spindle speed, feed rate, etc.)

#### `engineering_drawings.py`
- **Purpose**: Generate technical drawings
- **Capabilities**:
  - Create PDF engineering drawings
  - Dimensioned views of parts
  - Hole schedules and specifications

### GUI Applications

#### `unified_flute_gui_qt.py` ⭐ **Main Application**
- **Purpose**: Comprehensive GUI for all operations
- **Framework**: PyQt5
- **Tabs**:
  1. **Geometry 2D**: Profile views, bore visualization
  2. **Admittance**: Frequency response plots
  3. **Acoustic Analysis**: Inharmonicity, MOC, B_I/ESPE, etc.
  4. **3D Visualization**: Interactive 3D model
  5. **Engineering Drawings**: Technical drawings generation
  6. **G-code**: CNC code generation
  7. **Database**: Browse/manage stored flutes
- **⚠️ Note**: Large file (4885 lines) - candidate for modularization

#### Other GUI Applications:
- `flute_experimenter.py`: Interactive geometry editor
- `flute_optimizer_gui.py`: Embouchure optimization tool
- `graphical_editor.py`: Graphical geometry manipulation
- `perturbation_gui.py`: Perturbation analysis UI

#### Legacy/Alternative GUIs:
- `gui.py`: Original GUI (Tkinter-based?) - **Status unclear**
- `gui_db.py`: Database-focused GUI variant - **Status unclear**
- `unified_flute_gui.py`: Earlier unified GUI - **Status unclear**

**⚠️ TODO**: Clarify status/purpose of legacy GUIs or deprecate them

### Database

#### `db_schema.py`
- **Purpose**: SQLite database schema definition
- **Tables**:
  - `flutes`: Flute metadata
  - `flute_geometry`: Part geometry (JSON)
  - `impedance_calculation_params`: Calculation parameters
  - `bore_geometry`: OpenWind bore segments
  - `impedance_results`: Cached impedance computations

#### `flute_db_manager.py`
- **Purpose**: Database CRUD operations
- **Capabilities**:
  - Insert/update/delete flutes
  - Query flutes by various criteria
  - Manage calculation results
  - Database maintenance

#### `impedance_serializer.py`
- **Purpose**: Cache impedance computation results
- **Key Class**: `CachedImpedanceComputation`
- **Benefit**: Avoid expensive recalculations

### Utilities

#### `constants.py`
- **Purpose**: Global constants and helper functions
- **Contents**:
  - Physical constants (speed of sound)
  - Conversion factors (mm ↔ m)
  - Plotting colors and styles
  - Part ordering

#### `default_config.py`
- **Purpose**: Default configuration parameters
- **Contents**:
  - Acoustic parameters (pitch, temperature)
  - Frequency ranges
  - OpenWind settings
  - Visualization defaults

#### `gui_constants.py`
- **Purpose**: GUI-specific constants
- **Contents**:
  - Figure sizes
  - Font sizes
  - Colors and styles
  - Plot parameters

#### `plot_updater.py`
- **Purpose**: Separate plot update logic from main GUI
- **Key Class**: `PlotUpdater`
- **Benefit**: Reduces complexity in main GUI file

### Database Utilities

- `populate_database.py`: Bulk import JSON flutes to DB
- `cleanup_database.py`: Database maintenance and cleanup
- `reset_database.py`: Reinitialize database
- `migrate_json_to_db.py`: Migration from JSON to DB
- `database_statistics.py`: Generate database statistics

### External Integrations

#### `notion_utils.py`
- **Purpose**: Integration with Notion for documentation
- **Capabilities**:
  - Upload analysis results to Notion
  - Create structured documentation

## Data Flow

### Loading a Flute

```
JSON File → FluteData.__init__() → Parse geometry → Store in .data dict
          ↓
     OpenWind calculation → ImpedanceComputation → .acoustic_analysis
          ↓
     Calculate finger frequencies → .finger_frequencies
```

### Loading from Database

```
DB Query → FluteDBManager.get_flute() → Reconstruct JSON → FluteDataDB.__init__()
        ↓
   Check cache → ImpedanceCache.load_from_db()
        ↓
   If cached: Use cached results
   If not: Recalculate and save to cache
```

### Sensitivity Analysis

```
Base Flute → SensitivityAnalysis.generate_variants()
          ↓
     Apply parameter variations → Create FluteDataDB instances
          ↓
     Calculate acoustic analysis for each variant
          ↓
     Compare results → Generate plots → Export reports
```

### CNC Fabrication

```
Flute Geometry → GCodeGenerator
          ↓
     Convert bore profile → Toolpaths
     Convert holes → Drill operations
          ↓
     Export G-code file
```

## Design Patterns

### Model-View Architecture
- **Models**: `FluteData`, `FluteDataDB`
- **Views**: PyQt5 widgets in `unified_flute_gui_qt.py`
- **Controllers**: `FluteOperations`, `FluteAnalyzer`

### Strategy Pattern
- Different analysis strategies in `analysis_module.py`
- Multiple plot types in `flute_operations.py`

### Caching
- Impedance computation results cached in DB
- Lazy loading of 3D models

### Factory Pattern
- Creating flute variants in `sensitivity_analysis.py`

## Configuration

### Acoustic Parameters
Defined in `default_config.py`:
- Reference pitch (e.g., A=415 Hz)
- Temperature (default: 20°C)
- Frequency range for analysis
- Number of harmonics

### Visualization
Defined in `gui_constants.py`:
- Figure sizes
- Color schemes
- Font sizes
- Grid and line styles

## External Dependencies

### OpenWind
- **Purpose**: Acoustic simulation library
- **Usage**: Calculate impedance, admittance, resonances
- **Note**: May require installation from source

### PyQt5
- **Purpose**: GUI framework
- **Usage**: All interactive applications

### NumPy/SciPy
- **Purpose**: Numerical computing
- **Usage**: Interpolation, calculations, array operations

### Matplotlib
- **Purpose**: Plotting and visualization
- **Usage**: All plots, engineering drawings

## File Organization

```
.
├── Core Data Models
│   ├── flute_data.py
│   ├── flute_data_db.py
│   └── constants.py
│
├── Business Logic
│   ├── analysis_module.py
│   ├── flute_operations.py
│   ├── sensitivity_analysis.py
│   ├── geometry_modifier.py
│   └── geometry_perturbation.py
│
├── Database
│   ├── db_schema.py
│   ├── flute_db_manager.py
│   ├── impedance_serializer.py
│   └── flute_analysis.db (generated)
│
├── GUI Applications
│   ├── unified_flute_gui_qt.py ⭐ (Main)
│   ├── flute_experimenter.py
│   ├── flute_optimizer_gui.py
│   ├── flute_geometry_editor_qt.py
│   └── [Legacy GUIs - status unclear]
│
├── Fabrication
│   ├── gcode_generator.py
│   └── engineering_drawings.py
│
├── Utilities
│   ├── default_config.py
│   ├── gui_constants.py
│   ├── plot_updater.py
│   └── data_processing.py
│
├── Database Scripts
│   ├── populate_database.py
│   ├── cleanup_database.py
│   ├── reset_database.py
│   └── database_statistics.py
│
└── Documentation
    ├── README.md
    ├── ARCHITECTURE.md (this file)
    ├── SENSITIVITY_ANALYSIS_README.md
    ├── REPORTE_ESTADISTICO_README.md
    └── [Other documentation]
```

## Testing Status

⚠️ **Current Status**: No automated tests exist

**Recommendation**: Add tests for:
1. Data model loading/saving
2. Acoustic calculations (regression tests)
3. Geometric modifications
4. Database operations

## Known Issues and Technical Debt

1. **Large Monolithic Files**
   - `unified_flute_gui_qt.py` (4885 lines)
   - `flute_operations.py` (3606 lines)
   - **Impact**: Hard to maintain, test, and extend
   - **Recommendation**: Modularize into smaller files

2. **Legacy Code**
   - Multiple GUI variants with unclear status
   - Backup directories in repository
   - **Recommendation**: Clarify/deprecate/remove

3. **No Automated Testing**
   - **Impact**: Hard to refactor safely
   - **Recommendation**: Add pytest-based test suite

4. **Mixed Language**
   - Code in English, comments in Spanish
   - **Recommendation**: Standardize (preferably English)

5. **No Dependency Management**
   - **Status**: ✅ Fixed (requirements.txt created)

## Future Improvements

1. **Modularization**: Split large files into logical modules
2. **Testing**: Comprehensive test suite
3. **CI/CD**: Automated testing and deployment
4. **API**: REST API for headless analysis
5. **Docker**: Containerized deployment
6. **Documentation**: API documentation with Sphinx
7. **Type Checking**: Full mypy compliance

## Entry Points

### Main GUI Application
```bash
python unified_flute_gui_qt.py
```

### Experimenter GUI
```bash
python flute_experimenter.py
```

### Optimizer GUI
```bash
python flute_optimizer_gui.py
```

### Database Population
```bash
python populate_database.py
```

### Database Statistics
```bash
python database_statistics.py
```

## Contributing

See `CONTRIBUTING.md` for development guidelines and contribution process.

## License

[TODO: Specify license]

---

**Last Updated**: 2026-01-12
**Version**: 2.0
