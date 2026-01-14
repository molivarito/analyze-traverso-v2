# Installation Guide - Traverso Analyzer

Complete installation instructions for Traverso Analyzer on Linux, macOS, and Windows.

## Table of Contents

- [Quick Install (If OpenWind is Available)](#quick-install)
- [Detailed Installation](#detailed-installation)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Clone Repository](#2-clone-repository)
  - [3. Create Virtual Environment](#3-create-virtual-environment)
  - [4. Install Dependencies](#4-install-dependencies)
  - [5. Install OpenWind](#5-install-openwind)
  - [6. Verify Installation](#6-verify-installation)
  - [7. Configure Data Paths](#7-configure-data-paths)
- [Platform-Specific Notes](#platform-specific-notes)
- [Troubleshooting](#troubleshooting)
- [Optional Components](#optional-components)

---

## Quick Install

If OpenWind is available via pip (check with `pip search openwind`):

```bash
# Clone repository
git clone https://github.com/your-org/analyze-traverso-v2.git
cd analyze-traverso-v2

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run application
python unified_flute_gui_qt.py
```

⚠️ **Note**: OpenWind may not be available via pip and might require source installation. See [Install OpenWind](#5-install-openwind) below.

---

## Detailed Installation

### 1. Prerequisites

#### Required Software

| Software | Minimum Version | Purpose |
|----------|----------------|---------|
| Python | 3.8+ | Runtime environment |
| pip | 20.0+ | Package management |
| Git | 2.0+ | Version control |

#### Check Versions

```bash
python --version    # Should show Python 3.8 or higher
pip --version       # Should show pip 20.0 or higher
git --version       # Should show Git 2.0 or higher
```

#### Platform-Specific Prerequisites

**Linux (Ubuntu/Debian)**:
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git
sudo apt install python3-pyqt5 python3-tk  # GUI dependencies
sudo apt install build-essential  # For compiling packages
```

**macOS**:
```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python and dependencies
brew install python@3.10 git
```

**Windows**:
1. Download and install Python from [python.org](https://www.python.org/downloads/)
   - ✅ Check "Add Python to PATH" during installation
2. Download and install Git from [git-scm.com](https://git-scm.com/download/win)

### 2. Clone Repository

```bash
# Clone the repository
git clone https://github.com/your-org/analyze-traverso-v2.git
cd analyze-traverso-v2
```

### 3. Create Virtual Environment

Using a virtual environment is **strongly recommended** to avoid dependency conflicts.

#### Option A: Using Conda (Recommended if you have Anaconda/Miniconda) ⭐

```bash
# Create conda environment
conda create -n OpenWind python=3.10

# Activate environment
conda activate OpenWind

# Your prompt should now show (OpenWind)
```

**If you already have a conda environment called `OpenWind`** (like the project author):
```bash
# Just activate it
conda activate OpenWind

# Proceed to install dependencies
```

#### Option B: Using venv (Standard Python)

**Linux/macOS**:
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Your prompt should now show (venv)
```

**Windows**:
```cmd
REM Create virtual environment
python -m venv venv

REM Activate virtual environment
venv\Scripts\activate

REM Your prompt should now show (venv)
```

**Verification**: After activation, `which python` (or `where python` on Windows) should point to the environment directory.

### 4. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install main dependencies
pip install -r requirements.txt
```

This installs:
- NumPy (numerical computing)
- SciPy (scientific computing)
- Matplotlib (plotting)
- PyQt5 (GUI framework)

#### Development Dependencies (Optional)

For development work:

```bash
pip install pytest pytest-cov black flake8 mypy
```

Or using the pyproject.toml extras:

```bash
pip install -e ".[dev]"
```

### 5. Install OpenWind

OpenWind is the acoustic simulation library. **This is the most important dependency.**

#### Option A: Install from PyPI (If Available)

```bash
pip install openwind
```

If this works, you're done! Skip to [Verify Installation](#6-verify-installation).

#### Option B: Install from Source (Most Likely Required)

If OpenWind is not available via pip, install from source:

```bash
# Navigate to parent directory
cd ..

# Clone OpenWind repository
git clone https://gitlab.inria.fr/openwind/openwind.git

# Install OpenWind
cd openwind
pip install -e .

# Return to project directory
cd ../analyze-traverso-v2
```

**Alternative Gitlab URL** (if the above doesn't work):
```bash
git clone https://gitlab.inria.fr/openwind/openwind-project.git
```

#### Verify OpenWind Installation

```bash
python -c "import openwind; print(openwind.__version__)"
```

If this prints a version number without errors, OpenWind is installed correctly.

#### Troubleshooting OpenWind Installation

**Error**: "No module named 'openwind'"
- Solution: Ensure you installed OpenWind from source and your virtual environment is activated

**Error**: Compilation errors during OpenWind installation
- Linux/macOS: Install build tools:
  ```bash
  # Ubuntu/Debian
  sudo apt install build-essential gfortran

  # macOS
  brew install gcc gfortran
  ```
- Windows: Install Microsoft C++ Build Tools from [Visual Studio](https://visualstudio.microsoft.com/downloads/)

**Error**: Permission denied
- Solution: Don't use `sudo pip install`. Use virtual environment instead.

### 6. Verify Installation

#### Test Imports

```bash
python -c "import numpy, scipy, matplotlib, PyQt5, openwind; print('✅ All imports successful')"
```

#### Run Tests

```bash
# Run test suite
pytest

# If all tests pass, installation is verified
```

#### Launch GUI

```bash
python unified_flute_gui_qt.py
```

The main application window should open. If you see the GUI, **installation is complete!** 🎉

### 7. Configure Data Paths

After installation, you need to configure where your flute data and fingering chart files are located.

#### Quick Setup

**Option A: Automatic Setup (Recommended)** 🚀

```bash
# For macOS users with Google Drive (pre-configured)
python setup_config.py --pdelac

# Or for interactive auto-detection
python setup_config.py
```

The script will:
- Auto-detect your system (macOS/Linux/Windows)
- Try to find Google Drive location
- Search for data_json directory
- Create config.json automatically

**Option B: Manual Setup**

1. **Create configuration file**:
   ```bash
   cp config.json.example config.json
   ```

2. **Edit `config.json`** with your data paths:
   ```json
   {
     "data_dir": "~/traverso_data/data_json",
     "db_path": "~/.flute_analysis/flute_analysis.db"
   }
   ```

3. **Validate configuration**:
   ```bash
   python config.py --validate
   ```

   Expected output:
   ```
   ✓ Configuration is valid
   ```

#### For First-Time Users

If you don't have flute data yet, see the sample data:
```bash
ls data_json/sample/
```

#### For Users with Existing Data

If you already have flute data from a previous installation:

**Option A: Configure paths** (Recommended)
```bash
# Edit config.json to point to your existing data location
nano config.json
```

**Option B: Create symlink**
```bash
ln -s "/path/to/your/existing/data_json" ./data_json
```

**Option C: Copy database**
```bash
# If you have an existing database with cached results
cp ~/.flute_analysis/flute_analysis.db ./
```

#### For Conda Users ⭐

If you installed using conda (e.g., environment named `OpenWind`):

1. **Activate your conda environment first**:
   ```bash
   conda activate OpenWind
   ```

2. **Then configure data paths** as above

3. **Always activate environment before running**:
   ```bash
   conda activate OpenWind
   python unified_flute_gui_qt.py
   ```

#### Configuration Strategies

Choose the approach that works best for you:

| Strategy | Best For | Setup |
|----------|----------|-------|
| **config.json file** | Most users, cloud storage | Create config.json with paths |
| **Symbolic links** | Local data, simple setup | `ln -s /path/to/data ./data_json` |
| **Environment variables** | Developers, multiple configs | Export TRAVERSO_DATA_DIR |
| **Local copy** | Offline work, presentations | Copy data to project directory |

#### Required Files

Your data directory must contain:

1. **Flute geometry JSON files** (e.g., `Deppe.json`, `Grenser.json`)
2. **Fingering chart**: `traverso_fingerchart.txt` (required for OpenWind calculations)

Example structure:
```
data_json/
├── traverso_fingerchart.txt   # Required
├── Deppe.json
├── Grenser.json
└── ...
```

#### Verify Data Configuration

```bash
# Print current configuration
python config.py --print

# Validate all paths exist
python config.py --validate
```

#### Complete Guide

For detailed information about data management, including:
- Multiple configuration strategies
- Database management
- Troubleshooting data issues
- Best practices for cloud storage
- Collaboration setup

See **[DATA_SETUP.md](DATA_SETUP.md)** - Complete data configuration guide

---

## Platform-Specific Notes

### Linux

**Display Issues (Remote/SSH)**:

If running over SSH without X11 forwarding:
```bash
export QT_QPA_PLATFORM=offscreen  # For headless testing
# Or use X11 forwarding: ssh -X user@host
```

**Qt Plugin Errors**:
```bash
sudo apt install libxcb-xinerama0 libxkbcommon-x11-0
```

### macOS

**Matplotlib Backend Issues**:

If you get backend errors with matplotlib:
```bash
# Add to ~/.matplotlib/matplotlibrc
backend: TkAgg
```

**M1/M2 (Apple Silicon) Notes**:

Some packages may need Rosetta or native ARM builds:
```bash
# Use conda for better ARM support
conda create -n traverso python=3.10
conda activate traverso
conda install numpy scipy matplotlib pyqt
pip install -r requirements.txt
```

### Windows

**Long Path Issues**:

Enable long paths if you encounter path length errors:
```
# Run as Administrator in PowerShell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

**Qt Platform Plugin Errors**:

If you see "Could not find Qt platform plugin":
```cmd
set QT_QPA_PLATFORM_PLUGIN_PATH=%VIRTUAL_ENV%\Lib\site-packages\PyQt5\Qt5\plugins\platforms
```

---

## Troubleshooting

### Common Issues

#### "ImportError: No module named 'openwind'"

**Cause**: OpenWind not installed or not accessible in current environment.

**Solutions**:
1. Verify virtual environment is activated
2. Install OpenWind from source (see Option B above)
3. Check PYTHONPATH includes OpenWind directory

#### "Qt platform plugin error" or GUI doesn't open

**Cause**: Qt/PyQt5 installation issue or missing system libraries.

**Solutions**:

Linux:
```bash
sudo apt install libxcb-xinerama0 qt5-default
```

macOS:
```bash
brew install qt5
```

Windows:
```cmd
pip uninstall PyQt5
pip install PyQt5 --no-cache-dir
```

#### "Segmentation fault" or crashes on startup

**Cause**: Incompatible matplotlib backend or PyQt5 version conflict.

**Solutions**:
```bash
# Try different matplotlib backend
export MPLBACKEND=Qt5Agg

# Reinstall PyQt5 and matplotlib
pip uninstall PyQt5 matplotlib
pip install PyQt5==5.15.9 matplotlib==3.7.0
```

#### Tests fail with OpenWind errors

**Cause**: OpenWind not properly configured or test data missing.

**Solutions**:
1. Ensure OpenWind installation is complete
2. Check that test data exists in project directory
3. Run specific tests to isolate issue:
   ```bash
   pytest tests/test_imports.py -v
   ```

### Getting Help

If you encounter issues not covered here:

1. **Check existing issues**: Search [GitHub Issues](https://github.com/your-org/analyze-traverso-v2/issues)
2. **Create new issue**: Include:
   - Operating system and version
   - Python version (`python --version`)
   - Full error message
   - Steps to reproduce
3. **Community support**: Ask in discussions

---

## Optional Components

### Notion Integration (Optional)

For Notion report integration:

```bash
pip install notion-client requests
```

Then configure your Notion API token:
```bash
export NOTION_API_KEY="your-api-key-here"
```

See `notion_utils.py` for usage.

### Development Tools (Optional)

For contributing to the project:

```bash
# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pip install pre-commit
pre-commit install
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow.

---

## Verification Checklist

Before starting to use Traverso Analyzer, verify:

- [ ] Python 3.8+ installed and accessible
- [ ] Virtual environment created and activated
- [ ] All dependencies from requirements.txt installed
- [ ] OpenWind installed and importable
- [ ] Tests pass: `pytest`
- [ ] Main GUI launches: `python unified_flute_gui_qt.py`
- [ ] Can load and analyze a sample flute (if sample data available)

---

## Next Steps

After successful installation:

1. **Read Documentation**: Start with [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md)
2. **Try Examples**: Load sample flute data and explore the GUI
3. **Run Analysis**: See [SENSITIVITY_ANALYSIS_README.md](SENSITIVITY_ANALYSIS_README.md) for analysis workflows
4. **Contribute**: Read [CONTRIBUTING.md](CONTRIBUTING.md) if you want to contribute

---

## Quick Reference

```bash
# Activate environment
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Run main application
python unified_flute_gui_qt.py

# Run tests
pytest

# Format code (for development)
black .

# Lint code (for development)
flake8 .

# Deactivate environment
deactivate
```

---

**Having trouble?** Check [Troubleshooting](#troubleshooting) or open an issue on GitHub.

**Version**: 2.0.0
**Last Updated**: 2026-01-12
