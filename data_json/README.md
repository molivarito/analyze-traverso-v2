# Data Directory (data_json)

This directory contains flute geometry JSON files and the fingering chart file required for acoustic analysis.

## ⚠️ Important: This Directory is User-Specific

**The actual data files are NOT tracked in git** because:
1. They can be large (hundreds of JSON files)
2. They may be stored in different locations (Google Drive, network shares, etc.)
3. Each user may have their own data organization

## Setup Options

You have several options for managing your data:

### Option 1: Store Data Externally (Recommended for Google Drive users)

If your data is in Google Drive or another cloud service:

1. Keep your data where it is (e.g., Google Drive)
2. Create a `config.json` file in the project root:
   ```bash
   cp config.json.example config.json
   ```
3. Edit `config.json` to point to your data location:
   ```json
   {
     "data_dir": "~/Library/CloudStorage/GoogleDrive-email@gmail.com/My Drive/path/to/data_json",
     "db_path": "~/.flute_analysis/flute_analysis.db"
   }
   ```
4. Validate configuration:
   ```bash
   python config.py --validate
   ```

**Advantages**:
- Data synced across devices via cloud
- Single source of truth
- No duplication

### Option 2: Create Symlink to External Data

If you want the data to appear in this directory:

```bash
ln -s "/path/to/your/actual/data_json" ./data_json
```

**Example** (macOS with Google Drive):
```bash
cd /path/to/analyze-traverso-v2
ln -s "$HOME/Library/CloudStorage/GoogleDrive-email@gmail.com/My Drive/Research/data_json" ./data_json
```

**Advantages**:
- Data appears in expected location
- Easy to navigate
- Compatible with code that expects `./data_json`

### Option 3: Copy Data Locally

If you want a local copy:

```bash
cp -r /path/to/your/data_json/* ./data_json/
```

**Advantages**:
- Works offline
- Fast access (no network latency)
- Independent of cloud service

**Disadvantages**:
- Takes up disk space
- Must sync manually when data changes
- Not tracked in git (by design)

### Option 4: Use Environment Variables

Set these in your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):

```bash
export TRAVERSO_DATA_DIR="$HOME/traverso_data/data_json"
export TRAVERSO_DB_PATH="$HOME/.flute_analysis/flute_analysis.db"
export TRAVERSO_FINGERING_CHART="$HOME/traverso_data/data_json/traverso_fingerchart.txt"
```

Then reload your shell:
```bash
source ~/.bashrc  # or ~/.zshrc
```

**Advantages**:
- Configuration travels with your user profile
- Can be different for different shell sessions
- Highest priority (overrides config.json)

## Required Files

Your data directory must contain:

1. **Flute geometry JSON files** (e.g., `Deppe.json`, `Grenser.json`, etc.)
   - Format: See `sample/example_flute.json` for structure

2. **Fingering chart file**: `traverso_fingerchart.txt`
   - Contains note fingerings for OpenWind calculations
   - Usually one file for all flutes
   - See `sample/traverso_fingerchart.txt` for example

## Directory Structure

```
data_json/
├── README.md                      # This file
├── .gitkeep                       # Preserves directory in git
├── sample/                        # Example files (tracked in git)
│   ├── example_flute.json        # Minimal flute geometry example
│   └── traverso_fingerchart.txt  # Example fingering chart
│
# User data (NOT tracked in git):
├── Deppe.json                     # Your actual flute files
├── Grenser.json
├── Hotteterre.json
├── traverso_fingerchart.txt       # Your actual fingering chart
└── ...
```

## Validation

After setting up your data, validate the configuration:

```bash
# Check configuration
python config.py --print

# Validate all paths exist
python config.py --validate
```

Expected output:
```
✓ Configuration is valid
```

## Troubleshooting

### Error: "Archivo de digitaciones no encontrado"

This means the fingering chart file is not found. Solutions:

1. **Check configuration**:
   ```bash
   python config.py --print
   ```
   Verify `data_dir` points to correct location

2. **Check file exists**:
   ```bash
   ls -la "$(python -c 'from config import get_config; print(get_config().data_dir)')/traverso_fingerchart.txt"
   ```

3. **Create config.json if needed**:
   ```bash
   cp config.json.example config.json
   # Edit config.json with your paths
   ```

### Error: "data_dir does not exist"

Solutions:

1. **Create the directory**:
   ```bash
   mkdir -p ~/traverso_data/data_json
   ```

2. **Or point to existing location** in `config.json`:
   ```json
   {
     "data_dir": "/actual/path/to/your/data"
   }
   ```

### Empty database / Recalculating everything

If you see "RECALCULANDO análisis acústico" for flutes you've already analyzed:

1. **Check database location**:
   ```bash
   python config.py --print
   ```

2. **Copy existing database** if you have one:
   ```bash
   cp ~/.flute_analysis/flute_analysis.db ./flute_analysis.db
   ```

3. **Or configure to use existing database** in `config.json`:
   ```json
   {
     "db_path": "~/.flute_analysis/flute_analysis.db"
   }
   ```

## Sample Data

The `sample/` subdirectory contains minimal example files for:
- Testing the installation
- Understanding the data format
- Running quick checks

These files are tracked in git and included with the repository.

## For Developers

If you're working on the code:

1. **Use sample data** for testing:
   ```json
   {
     "data_dir": "./data_json/sample"
   }
   ```

2. **Or use test fixtures** in `tests/conftest.py`

3. **Never commit production data** to git (it's ignored by `.gitignore`)

## Additional Resources

- Configuration reference: `config.py --help`
- Installation guide: `INSTALL.md`
- API documentation: `docs/API.md`

## Questions?

See `CONTRIBUTING.md` for how to report issues or ask questions.
