# Data Setup Guide

Complete guide for setting up and managing data files in Traverso Analyzer.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Configuration Strategies](#configuration-strategies)
- [Data Directory Structure](#data-directory-structure)
- [Database Management](#database-management)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

---

## Overview

Traverso Analyzer requires two types of data:

1. **Flute geometry files** (JSON format) - Stored in `data_json/` directory
2. **Fingering chart** (`traverso_fingerchart.txt`) - Required for OpenWind calculations
3. **Analysis database** (SQLite) - Caches computed results

These files are **user-specific** and **NOT tracked in git** because:
- They can be large (hundreds of MB)
- Each user may store them in different locations (Google Drive, network shares, etc.)
- They contain research data specific to each user's work

---

## Quick Start

### First Time Setup

1. **Copy the configuration template**:
   ```bash
   cd /path/to/analyze-traverso-v2
   cp config.json.example config.json
   ```

2. **Edit `config.json`** with your data paths:
   ```json
   {
     "data_dir": "~/traverso_data/data_json",
     "db_path": "~/.flute_analysis/flute_analysis.db",
     "fingering_chart": "~/traverso_data/data_json/traverso_fingerchart.txt"
   }
   ```

3. **Validate configuration**:
   ```bash
   python config.py --validate
   ```

4. **Check configuration**:
   ```bash
   python config.py --print
   ```

### If You Already Have Data

If you already have flute data and database (e.g., from original installation):

**Option A: Configure paths to existing data**
```bash
# Edit config.json to point to your existing locations
nano config.json
```

**Option B: Copy data to new project**
```bash
# Copy database
cp ~/.flute_analysis/flute_analysis.db ./

# Create symlink to data
ln -s "/path/to/your/existing/data_json" ./data_json
```

---

## Configuration Strategies

### Strategy 1: External Data with Configuration File (Recommended)

**Best for**: Users with data in Google Drive, Dropbox, or network shares

**Setup**:
1. Keep data in its current location (e.g., Google Drive)
2. Create `config.json` pointing to that location
3. All project clones can use different `config.json` files

**Example `config.json`** (macOS with Google Drive):
```json
{
  "data_dir": "~/Library/CloudStorage/GoogleDrive-email@gmail.com/My Drive/Research/Traverso/data_json",
  "db_path": "~/.flute_analysis/flute_analysis.db",
  "fingering_chart": "~/Library/CloudStorage/GoogleDrive-email@gmail.com/My Drive/Research/Traverso/data_json/traverso_fingerchart.txt"
}
```

**Example `config.json`** (Linux):
```json
{
  "data_dir": "~/GoogleDrive/Research/Traverso/data_json",
  "db_path": "~/.flute_analysis/flute_analysis.db"
}
```

**Advantages**:
- ✅ Single source of truth for data
- ✅ Data synced across devices automatically
- ✅ No duplication
- ✅ Multiple project copies can share same data
- ✅ Easy to switch between projects

**Disadvantages**:
- ❌ Requires internet connection (for cloud storage)
- ❌ May have latency for large files

---

### Strategy 2: Symbolic Links

**Best for**: Users who want data to appear in project directory but stored elsewhere

**Setup**:
```bash
cd /path/to/analyze-traverso-v2

# Create symlink to data directory
ln -s "/actual/path/to/data_json" ./data_json

# Create symlink to database (optional)
ln -s ~/.flute_analysis/flute_analysis.db ./flute_analysis.db
```

**Example** (macOS with Google Drive):
```bash
ln -s "$HOME/Library/CloudStorage/GoogleDrive-email@gmail.com/My Drive/Research/Traverso/data_json" ./data_json
```

**Example** (Linux):
```bash
ln -s "$HOME/GoogleDrive/Research/Traverso/data_json" ./data_json
```

**Advantages**:
- ✅ Data appears in expected location
- ✅ Compatible with code that expects `./data_json`
- ✅ No configuration file needed
- ✅ Single source of truth

**Disadvantages**:
- ❌ Must create symlink in each project clone
- ❌ Symlinks can break if target moves
- ❌ Not portable (absolute paths)

---

### Strategy 3: Environment Variables

**Best for**: Developers working with multiple projects/configurations

**Setup**:

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
# Traverso Analyzer configuration
export TRAVERSO_DATA_DIR="$HOME/traverso_data/data_json"
export TRAVERSO_DB_PATH="$HOME/.flute_analysis/flute_analysis.db"
export TRAVERSO_FINGERING_CHART="$HOME/traverso_data/data_json/traverso_fingerchart.txt"
```

Then reload:
```bash
source ~/.bashrc  # or ~/.zshrc
```

**Advantages**:
- ✅ Highest priority (overrides config.json)
- ✅ Configuration travels with user profile
- ✅ Can be different per shell session
- ✅ Good for development/testing

**Disadvantages**:
- ❌ Must set up in shell profile
- ❌ Not portable across systems
- ❌ Less visible than config file

---

### Strategy 4: Local Data Copy

**Best for**: Working offline, presentations, or air-gapped systems

**Setup**:
```bash
# Copy data to project directory
cp -r /path/to/original/data_json/* ./data_json/

# Copy database
cp ~/.flute_analysis/flute_analysis.db ./flute_analysis.db

# Create config.json for local paths
cat > config.json <<EOF
{
  "data_dir": "./data_json",
  "db_path": "./flute_analysis.db"
}
EOF
```

**Advantages**:
- ✅ Works offline
- ✅ Fast access (no network latency)
- ✅ Self-contained project
- ✅ Easy to zip and share

**Disadvantages**:
- ❌ Takes up disk space
- ❌ Must sync manually when data changes
- ❌ Multiple copies can get out of sync
- ❌ Database can become stale

---

## Configuration Priority

The configuration system checks sources in this order (highest priority first):

1. **Environment variables** (`TRAVERSO_DATA_DIR`, etc.)
2. **config.json in project root** (`./config.json`)
3. **config.json in ~/.traverso/** (`~/.traverso/config.json`)
4. **Default values** (hardcoded fallbacks)

This allows flexibility:
- Use environment variables for temporary overrides
- Use `config.json` for stable configuration
- Defaults work for standard installations

---

## Data Directory Structure

### Required Structure

```
data_json/
├── traverso_fingerchart.txt       # Required: Fingering chart for OpenWind
├── [YourFlute1].json              # Your flute geometry files
├── [YourFlute2].json
└── ...
```

### Flute JSON Format

Each flute file contains geometry data:

```json
{
  "flute_model": "Deppe",
  "headjoint": {
    "measurements": [
      {"position": 0.0, "diameter": 19.0},
      {"position": 100.0, "diameter": 19.5}
    ],
    "holes": [
      {
        "position": 50.0,
        "diameter": 8.0,
        "height": 2.0,
        "angle": 0.0
      }
    ],
    "length": 100.0,
    "inner_diameter_at_tenon": 19.5,
    "outer_diameter_at_tenon": 21.0
  },
  "left": { /* similar structure */ },
  "right": { /* similar structure */ },
  "foot": { /* similar structure */ }
}
```

See `data_json/sample/example_flute.json` for complete example.

### Fingering Chart Format

Simple text format:

```
# Comment lines start with #
# Format: Note | Hole1 Hole2 Hole3 ... (0=closed, 1=open)

D  | 0 0 0 0 0 0
D# | 0 0 0 0 0 1
E  | 0 0 0 0 1 1
...
```

See `data_json/sample/traverso_fingerchart.txt` for example.

---

## Database Management

### Database Location Options

**Option A: Shared database in home directory** (Default, Recommended)
```json
{
  "db_path": "~/.flute_analysis/flute_analysis.db"
}
```

**Advantages**:
- ✅ Shared across all project clones
- ✅ No recalculation when switching projects
- ✅ Standard location

**Option B: Project-local database**
```json
{
  "db_path": "./flute_analysis.db"
}
```

**Advantages**:
- ✅ Self-contained project
- ✅ Easy to backup/share
- ✅ No conflicts between project versions

**Disadvantages**:
- ❌ Must recalculate for each project clone
- ❌ Takes up more space

### Database Operations

**Check database location**:
```bash
python config.py --print
```

**Copy existing database to new location**:
```bash
# From shared to local
cp ~/.flute_analysis/flute_analysis.db ./flute_analysis.db

# From local to shared
mkdir -p ~/.flute_analysis
cp ./flute_analysis.db ~/.flute_analysis/
```

**Clear database** (force recalculation):
```bash
# Backup first!
cp flute_analysis.db flute_analysis.db.backup

# Remove database
rm flute_analysis.db

# Next run will recalculate everything
```

**Check database size**:
```bash
ls -lh ~/.flute_analysis/flute_analysis.db
# or
ls -lh ./flute_analysis.db
```

Typical sizes:
- Empty database: ~0.1 MB
- With analysis results for 5-10 flutes: 10-20 MB
- Large projects: 50-100+ MB

---

## Troubleshooting

### Problem: "Archivo de digitaciones no encontrado"

**Symptom**: Error message about missing fingering chart file

**Cause**: Fingering chart file not found in configured location

**Solutions**:

1. **Check configuration**:
   ```bash
   python config.py --print
   # Look at "Fingering chart:" path
   ```

2. **Verify file exists**:
   ```bash
   ls -la "$(python -c 'from config import get_config; print(get_config().fingering_chart_path)')"
   ```

3. **Check data directory**:
   ```bash
   ls -la "$(python -c 'from config import get_config; print(get_config().data_dir)')"
   # Should show traverso_fingerchart.txt
   ```

4. **Fix configuration**:
   - Edit `config.json` to point to correct location
   - Or copy fingering chart to expected location
   - Or set `TRAVERSO_FINGERING_CHART` environment variable

---

### Problem: "data_dir does not exist"

**Symptom**: Configuration validation fails

**Solutions**:

1. **Create directory**:
   ```bash
   mkdir -p ~/traverso_data/data_json
   ```

2. **Or update config.json** to point to existing directory:
   ```json
   {
     "data_dir": "/actual/path/to/your/data"
   }
   ```

3. **Or create symlink**:
   ```bash
   ln -s "/actual/path/to/data" ./data_json
   ```

---

### Problem: Empty Database / Recalculating Everything

**Symptom**: Program says "RECALCULANDO análisis acústico" for already-analyzed flutes

**Cause**: Using new/empty database instead of existing one with cached results

**Solutions**:

1. **Check where database is**:
   ```bash
   python config.py --print
   # Note the "Database path:" location
   ```

2. **If you have existing database, copy it**:
   ```bash
   # From old location to new
   cp ~/.flute_analysis/flute_analysis.db ./flute_analysis.db
   ```

3. **Or configure to use existing database**:
   ```json
   {
     "db_path": "~/.flute_analysis/flute_analysis.db"
   }
   ```

4. **Verify database has data**:
   ```bash
   ls -lh ~/.flute_analysis/flute_analysis.db
   # Should be several MB if it has cached results
   # Only ~100KB if empty
   ```

---

### Problem: Symlink Broken

**Symptom**: `ls -la data_json` shows broken symlink (red text)

**Solutions**:

1. **Remove broken symlink**:
   ```bash
   rm data_json
   ```

2. **Create new symlink with correct path**:
   ```bash
   ln -s "/correct/path/to/data_json" ./data_json
   ```

3. **Or switch to configuration file approach**:
   ```bash
   rm data_json  # Remove symlink
   cp config.json.example config.json
   # Edit config.json with correct path
   ```

---

### Problem: Different Behavior in Different Project Clones

**Symptom**: One copy of project works, another doesn't

**Cause**: Different configurations or data locations

**Solutions**:

1. **Compare configurations**:
   ```bash
   # In first project
   cd ~/project1
   python config.py --print > /tmp/config1.txt

   # In second project
   cd ~/project2
   python config.py --print > /tmp/config2.txt

   # Compare
   diff /tmp/config1.txt /tmp/config2.txt
   ```

2. **Standardize configuration**:
   - Use same `config.json` in both projects
   - Or use environment variables (affects all projects)
   - Or use shared database location

---

## Best Practices

### For Single User, Single Computer

✅ **Recommended**:
- Store data in stable location (e.g., `~/traverso_data/data_json`)
- Use shared database (`~/.flute_analysis/flute_analysis.db`)
- Create `config.json` in project root pointing to data
- Commit `config.json.example` but not `config.json` to git

### For Data in Cloud Storage

✅ **Recommended**:
- Keep data in cloud (Google Drive, Dropbox, etc.)
- Use `config.json` to point to cloud location
- Use shared database in `~/.flute_analysis/`
- Consider copying database to cloud for backup

**Example**:
```json
{
  "data_dir": "~/Google Drive/Research/Traverso/data_json",
  "db_path": "~/.flute_analysis/flute_analysis.db"
}
```

### For Multiple Users / Collaboration

✅ **Recommended**:
- Share data via network drive or cloud
- Each user creates their own `config.json`
- Consider Git LFS for large JSON files (if committing data)
- Use environment variables for user-specific overrides

### For Development / Testing

✅ **Recommended**:
- Use sample data for basic tests: `./data_json/sample/`
- Use test fixtures in `tests/conftest.py`
- Keep production data separate
- Use environment variables for temporary config

### For Presentations / Offline Work

✅ **Recommended**:
- Copy data locally: `cp -r /path/to/data_json ./`
- Copy database: `cp ~/.flute_analysis/*.db ./`
- Create local `config.json`:
  ```json
  {
    "data_dir": "./data_json",
    "db_path": "./flute_analysis.db"
  }
  ```
- Zip entire directory for transport

---

## Version Control (Git)

### What's Tracked in Git

✅ **Tracked**:
- `config.py` (configuration module)
- `config.json.example` (template)
- `data_json/.gitkeep` (preserves directory structure)
- `data_json/README.md` (documentation)
- `data_json/sample/` (example files)
- `DATA_SETUP.md` (this guide)

❌ **NOT Tracked** (in `.gitignore`):
- `config.json` (user-specific)
- `data_json/` (except sample/ subdirectory)
- `*.db` (database files)
- Large JSON files (user data)

### Cloning Repository

When you clone the repository:

1. **Directory structure is preserved** (via `.gitkeep`)
2. **Sample data is included** (`data_json/sample/`)
3. **You must create `config.json`** to point to your data
4. **Database is not included** (will be created on first run)

**Setup after clone**:
```bash
git clone <repository-url>
cd analyze-traverso-v2

# Create configuration
cp config.json.example config.json
nano config.json  # Edit with your paths

# Validate
python config.py --validate

# Run
python unified_flute_gui_qt.py
```

---

## Migration from Original Version

If you're upgrading from the original version (without configuration system):

### Step 1: Locate Your Current Data

```bash
# Find data directory (usually in project root)
ls -la ./data_json

# Find database
ls -la ~/.flute_analysis/flute_analysis.db
# or
ls -la ./flute_analysis.db
```

### Step 2: Create Configuration

```bash
cd /path/to/new/analyze-traverso-v2
cp config.json.example config.json
```

Edit `config.json`:
```json
{
  "data_dir": "/path/to/your/old/data_json",
  "db_path": "~/.flute_analysis/flute_analysis.db"
}
```

### Step 3: Validate

```bash
python config.py --validate
```

### Step 4: Test

```bash
python unified_flute_gui_qt.py
```

Should load flutes without recalculating.

---

## Advanced Topics

### Custom Configuration Location

Use environment variable to specify custom config file:

```bash
export TRAVERSO_CONFIG="/custom/path/config.json"
python unified_flute_gui_qt.py
```

### Multiple Configurations

Create multiple config files for different scenarios:

```bash
# config.local.json - for local development
# config.cloud.json - for cloud data
# config.offline.json - for offline work

# Use with environment variable:
export TRAVERSO_CONFIG="./config.offline.json"
python unified_flute_gui_qt.py
```

### Programmatic Configuration

In Python scripts:

```python
from config import Config

# Load custom config
config = Config(config_file="custom_config.json")

# Check paths
print(f"Data: {config.data_dir}")
print(f"DB: {config.db_path}")

# Validate
if not config.validate():
    print("Configuration error!")
```

---

## Summary

| Strategy | Best For | Setup Complexity | Portability |
|----------|----------|------------------|-------------|
| External + config.json | Cloud storage users | Low | Medium |
| Symlinks | Local data, appearing in project | Low | Low |
| Environment variables | Developers | Medium | Low |
| Local copy | Offline work, presentations | Low | High |

**Recommendation for most users**:
1. Keep data in stable location (cloud or ~/traverso_data)
2. Create `config.json` pointing to that location
3. Use shared database in `~/.flute_analysis/`
4. Validate with `python config.py --validate`

---

## Questions or Issues?

- Check `INSTALL.md` for installation help
- Check `CONTRIBUTING.md` for reporting issues
- Run `python config.py --print` to debug configuration
- Check `data_json/README.md` for directory-specific help

**Configuration utility**:
```bash
python config.py --help
```

**Health check**:
```bash
python check_health.py
```

