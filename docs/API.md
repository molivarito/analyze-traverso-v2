# API Documentation - Traverso Analyzer

Quick reference for using Traverso Analyzer programmatically.

## Table of Contents

- [Core Modules](#core-modules)
- [Data Models](#data-models)
- [Analysis](#analysis)
- [Visualization](#visualization)
- [Database](#database)
- [Utilities](#utilities)

---

## Core Modules

### `flute_data.py` - FluteData

Load and manage flute geometry from JSON files.

```python
from flute_data import FluteData

# Load flute from JSON
flute = FluteData("path/to/flute.json")

# Access properties
print(flute.flute_model)  # Flute name
print(flute.data)  # Raw geometry data
print(flute.acoustic_analysis)  # Analysis results (dict by note)
print(flute.finger_frequencies)  # Playing frequencies (dict by note)
```

**Key Methods**:
- `__init__(json_path)` - Load from JSON file
- `to_json(output_path)` - Save to JSON file

### `flute_data_db.py` - FluteDataDB

Database-backed flute data with caching.

```python
from flute_data_db import FluteDataDB

# Load from database (with caching)
flute = FluteDataDB("path/to/flute.json", db_path="flute_analysis.db")

# Same API as FluteData, but with automatic result caching
```

**Benefits**:
- Caches acoustic calculations
- Avoids redundant computations
- Faster for repeated analyses

---

## Data Models

### JSON Structure

```python
{
  "flute_model": "Example_Flute",
  "headjoint": {
    "measurements": [
      {"position": 0.0, "diameter": 19.0},  # mm
      {"position": 100.0, "diameter": 19.5}
    ],
    "holes": [
      {
        "position": 50.0,  # Position along part (mm)
        "diameter": 8.0,   # Hole diameter (mm)
        "height": 2.0,     # Chimney height (mm)
        "angle": 0.0       # Optional: hole angle (degrees)
      }
    ],
    "length": 100.0,  # Total part length (mm)
    "inner_diameter_at_tenon": 19.0,  # For joints
    "outer_diameter_at_tenon": 21.0
  },
  "left": { ... },    # Similar structure
  "right": { ... },   # Similar structure
  "foot": { ... }     # Similar structure
}
```

---

## Analysis

### `analysis_module.py` - FluteAnalyzer

Unified acoustic analysis.

```python
from analysis_module import FluteAnalyzer

# Create analyzer with one or more flutes
flutes = [FluteData("flute1.json"), FluteData("flute2.json")]
analyzer = FluteAnalyzer(flutes)

# Calculate metrics
inharmonicity = analyzer.calculate_inharmonicity()
moc = analyzer.calculate_moc()
bi_espe = analyzer.calculate_bi_espe()

# Access results
for flute_name, results in inharmonicity.items():
    for note, cents in results.items():
        print(f"{flute_name} - {note}: {cents:.2f} cents")
```

**Key Methods**:

| Method | Returns | Description |
|--------|---------|-------------|
| `calculate_inharmonicity()` | `Dict[str, Dict[str, float]]` | Cents difference per note |
| `calculate_moc()` | `Dict[str, Dict[str, float]]` | Modal Octave Compression |
| `calculate_bi_espe()` | `Dict[str, Dict[str, Tuple[float, float]]]` | B_I and ESPE metrics |

**Plotting Methods**:

```python
import matplotlib.pyplot as plt

# Generate plots
fig = analyzer.plot_inharmonicity()
plt.savefig('inharmonicity.pdf')

fig = analyzer.plot_moc()
fig = analyzer.plot_bi_espe()
fig = analyzer.plot_resonance_frequencies()
fig = analyzer.plot_peak_heights()
fig = analyzer.plot_q_factor()
```

**Export Methods**:

```python
# Export results
analyzer.export_results_to_csv("results.csv")
analyzer.export_results_to_json("results.json")
analyzer.generate_summary_report("report.pdf")
```

---

## Visualization

### `flute_operations.py` - FluteOperations

Core operations and plotting.

```python
from flute_operations import FluteOperations

# Create operations instance
ops = FluteOperations(flute_data)

# Generate various plots
fig = ops.plot_geometry_2d()
fig = ops.plot_admittance(note="D")
fig = ops.plot_impedance_curve(note="D")
```

### `flute_3d_visualizer.py` - 3D Visualization

```python
from flute_3d_visualizer import Flute3DModel, compare_flutes_3d

# Create 3D model
model = Flute3DModel(flute_data)
fig = model.plot_3d()

# Compare multiple flutes
fig = compare_flutes_3d([flute1, flute2])
```

---

## Database

### `flute_db_manager.py` - Database Operations

```python
from flute_db_manager import FluteDBManager

# Initialize manager
db_manager = FluteDBManager("flute_analysis.db")

# Add flute to database
db_manager.add_flute_from_json("flute.json")

# Query flutes
all_flutes = db_manager.get_all_flutes()
flute = db_manager.get_flute_by_name("Deppe")

# Update flute
db_manager.update_flute(flute_id, new_data)

# Delete flute
db_manager.delete_flute(flute_id)
```

### `impedance_serializer.py` - Result Caching

Automatic caching of expensive calculations.

```python
from impedance_serializer import CachedImpedanceComputation

# Create cached computation
cached = CachedImpedanceComputation(
    db_path="flute_analysis.db",
    flute_id=1,
    params=calculation_params
)

# Load from cache or compute
if cached.load_from_db():
    result = cached.get_result()
else:
    result = expensive_computation()
    cached.save_to_db(result)
```

---

## Utilities

### `constants.py` - Physical Constants

```python
from constants import (
    get_speed_of_sound,
    MM_TO_M,
    M_TO_MM,
    BASE_COLORS,
    LINESTYLES,
    FLUTE_PARTS_ORDER
)

# Calculate speed of sound at temperature
speed = get_speed_of_sound(20.0)  # m/s at 20°C

# Unit conversion
length_m = 100 * MM_TO_M  # 100mm to meters
length_mm = 0.1 * M_TO_MM  # 0.1m to millimeters

# Plotting constants
colors = BASE_COLORS  # Color palette for plots
styles = LINESTYLES   # Line styles for plots
parts = FLUTE_PARTS_ORDER  # ['headjoint', 'left', 'right', 'foot']
```

### `default_config.py` - Configuration

```python
from default_config import (
    DEFAULT_TEMPERATURE,
    DEFAULT_LA_FREQUENCY,
    DEFAULT_FREQ_RANGE,
    CANONICAL_NOTE_ORDER
)

# Use default values
temp = DEFAULT_TEMPERATURE  # 20.0°C
pitch = DEFAULT_LA_FREQUENCY  # 415.0 Hz
freq_range = DEFAULT_FREQ_RANGE  # (20, 3000, 0.5)
notes = CANONICAL_NOTE_ORDER  # ['D', 'D#', 'E', ...]
```

### `data_processing.py` - Data Processing

```python
from data_processing import (
    interpolate_measurements,
    combine_parts_to_full_bore,
    calculate_bore_volume
)

# Interpolate bore measurements
positions, diameters = interpolate_measurements(measurements)

# Combine multiple parts
full_bore = combine_parts_to_full_bore([headjoint, left, right, foot])

# Calculate volume
volume = calculate_bore_volume(positions, radii)
```

---

## Sensitivity Analysis

### `sensitivity_analysis.py` - Parameter Studies

```python
from sensitivity_analysis import SensitivityAnalyzer

# Create analyzer
analyzer = SensitivityAnalyzer(base_flute)

# Run parameter sweep
results = analyzer.vary_parameter(
    parameter='hole_undercut',
    values=[-0.5, 0, 0.5, 1.0],  # mm
    hole_index=5
)

# Analyze results
analyzer.plot_sensitivity_results(results)
analyzer.export_sensitivity_report("sensitivity.pdf")
```

---

## Fabrication

### `gcode_generator.py` - G-code Generation

```python
from gcode_generator import GCodeGenerator

# Create generator
generator = GCodeGenerator(flute_data)

# Generate G-code for part
gcode = generator.generate_for_part(
    part_name='headjoint',
    tool_diameter=6.0,  # mm
    spindle_speed=10000,  # RPM
    feed_rate=100  # mm/min
)

# Save G-code
with open('headjoint.nc', 'w') as f:
    f.write(gcode)
```

### `engineering_drawings.py` - Technical Drawings

```python
from engineering_drawings import EngineeringDrawingGenerator

# Create generator
generator = EngineeringDrawingGenerator(flute_data)

# Generate PDF drawings
generator.generate_complete_drawings("flute_drawings.pdf")

# Generate individual part drawings
generator.generate_part_drawing("headjoint", "headjoint.pdf")
```

---

## Error Handling

### Common Exceptions

```python
from flute_data import FluteDataInitializationError

try:
    flute = FluteData("invalid.json")
except FluteDataInitializationError as e:
    print(f"Failed to load flute: {e}")
except FileNotFoundError:
    print("JSON file not found")
```

### Best Practices

1. **Always use try/except** when loading flutes
2. **Check for None** in analysis results
3. **Validate inputs** before expensive calculations
4. **Use logging** for debugging

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("Starting analysis...")
logger.warning("Missing data for note D")
logger.error("Calculation failed", exc_info=True)
```

---

## Examples

See the `examples/` directory for complete working examples:
- `basic_analysis.py` - Simple analysis workflow
- More examples coming soon

---

## Further Reading

- **Architecture**: See `ARCHITECTURE.md` for system design
- **Contributing**: See `CONTRIBUTING.md` for development guidelines
- **Installation**: See `INSTALL.md` for setup instructions

---

**Note**: This is a quick reference. For complete details, see module docstrings and source code.

**Last Updated**: 2026-01-13
