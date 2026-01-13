# Changelog

All notable changes to the Traverso Analyzer project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive project infrastructure and documentation
- Test suite with pytest configuration
- GitHub Actions CI/CD workflows
- Pre-commit hooks configuration
- Development Makefile with useful commands
- Complete installation guide (INSTALL.md)
- Deprecation warnings for legacy GUI modules
- Bilingual README (English/Spanish)

### Changed
- Enhanced .gitignore with project-specific rules
- Updated README.md with modern structure and badges
- Improved documentation organization

### Deprecated
- `gui.py` - Legacy Tkinter GUI (use `unified_flute_gui_qt.py`)
- `gui_db.py` - Legacy database GUI (use `unified_flute_gui_qt.py`)
- `unified_flute_gui.py` - Legacy unified GUI (use `unified_flute_gui_qt.py`)

## [2.0.0] - 2026-01-12

### Added
- **Major refactoring for code quality** (November 2024)
  - Created `gui_constants.py` for centralized GUI constants
  - Created `default_config.py` for default configuration
  - Created `plot_updater.py` to separate plot logic from main GUI
  - Reduced complexity of `unified_flute_gui_qt.py`

- **Sensitivity Analysis Features**
  - Comprehensive sensitivity analysis module
  - Parameter variation studies (undercut, taper, cork position, etc.)
  - Detailed sensitivity reports and visualizations
  - See SENSITIVITY_ANALYSIS_README.md for details

- **Database Statistics**
  - Statistical analysis of flute database
  - Automated report generation
  - See REPORTE_ESTADISTICO_README.md for details

### Changed
- Improved code organization and modularity
- Enhanced logging throughout the application
- Better error handling and user feedback

### Fixed
- Various bug fixes in geometry calculations
- Improved stability of acoustic analysis
- Fixed database caching issues

## [1.0.0] - 2025-11-26

### Initial Release Features

#### Core Functionality
- **FluteData** and **FluteDataDB**: Core data models for flute geometry
  - JSON-based geometry storage
  - SQLite database integration for persistent storage
  - Automatic caching of acoustic calculations

- **Acoustic Analysis**:
  - OpenWind integration for impedance/admittance calculations
  - Inharmonicity analysis (cents differences)
  - MOC (Modal Octave Compression) calculations
  - B_I and ESPE metrics
  - Q-factor analysis
  - Harmonic ratios and phase coherence

- **Visualization**:
  - 2D geometry profiles (bore, holes)
  - Admittance plots for each note
  - 3D flute models (interactive)
  - Engineering drawings (PDF export)
  - Comparative analysis plots

#### Applications

- **unified_flute_gui_qt.py**: Main comprehensive GUI application
  - All-in-one interface for analysis and design
  - Multi-tab interface (Geometry, Analysis, 3D, Engineering, G-code, Database)
  - Database management
  - Export capabilities

- **flute_experimenter.py**: Interactive geometry editor
  - Real-time geometry modification
  - Drag-and-drop editing
  - Instant acoustic feedback

- **flute_optimizer_gui.py**: Embouchure optimizer
  - Cork/chimney height optimization
  - Target tuning based on reference pitch

- **flute_geometry_editor_qt.py**: Detailed geometry editor
  - Precise geometric modifications
  - Advanced editing tools

#### Database Features
- SQLite-based persistence
- Geometry storage
- Calculation result caching
- Database utilities:
  - `populate_database.py`: Bulk import from JSON
  - `cleanup_database.py`: Database maintenance
  - `reset_database.py`: Database reinitialization
  - `database_statistics.py`: Statistical analysis

#### Fabrication Support
- **G-code generation**: CNC machining code export
- **Engineering drawings**: Professional PDF technical drawings

#### Analysis Modules
- `analysis_module.py`: Unified acoustic analysis
- `sensitivity_analysis.py`: Parameter sensitivity studies
- `geometry_modifier.py`: Geometric transformation tools
- `geometry_perturbation.py`: Parameter perturbation

### Technical Details
- Python 3.8+ required
- PyQt5 for GUI framework
- NumPy/SciPy for numerical computations
- Matplotlib for plotting
- OpenWind for acoustic simulation
- SQLite for database

---

## Version History Summary

| Version | Date | Key Features |
|---------|------|--------------|
| 2.0.0 | 2026-01-12 | Refactoring, infrastructure, documentation |
| 1.0.0 | 2025-11-26 | Initial comprehensive release |

---

## Migration Guide

### From 1.x to 2.x

**No breaking changes** - Version 2.0.0 focuses on infrastructure improvements:

1. **GUI Applications**: Continue using `unified_flute_gui_qt.py` as main application
2. **Legacy GUIs**: If using `gui.py`, `gui_db.py`, or `unified_flute_gui.py`:
   - Consider migrating to `unified_flute_gui_qt.py`
   - Legacy GUIs still work but show deprecation warnings
   - See DEPRECATIONS.md for details

3. **Development**: New developer tools available:
   - Run `make install-dev` for development setup
   - Use `make test` to run test suite
   - Use `make format` to format code
   - See Makefile for all commands

4. **Testing**: Test suite now available - run `pytest` to verify functionality

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to this project.

---

## Links

- **Documentation**: [README.md](README.md)
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **Installation**: [INSTALL.md](INSTALL.md)
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)
- **Deprecations**: [DEPRECATIONS.md](DEPRECATIONS.md)

---

**Maintained by**: Traverso Analyzer Contributors
**License**: MIT
