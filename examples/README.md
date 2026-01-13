# Examples - Traverso Analyzer

This directory contains example scripts demonstrating how to use Traverso Analyzer programmatically.

## Available Examples

### `basic_analysis.py` - Basic Acoustic Analysis

Demonstrates:
- Loading a flute from JSON file
- Creating a FluteAnalyzer
- Calculating inharmonicity
- Displaying and exporting results

**Usage**:
```bash
# Edit the script to point to your flute JSON file
python examples/basic_analysis.py

# Or pass JSON file as argument
python examples/basic_analysis.py path/to/flute.json
```

### More Examples Coming Soon

Future examples will cover:
- Sensitivity analysis
- Geometry modification
- Comparing multiple flutes
- Generating engineering drawings
- Exporting to different formats

## Example Data Structure

All examples assume flute data is in JSON format. Here's a minimal structure:

```json
{
  "flute_model": "Example_Flute",
  "headjoint": {
    "measurements": [
      {"position": 0, "diameter": 19.0},
      {"position": 100, "diameter": 19.5}
    ],
    "holes": [
      {
        "position": 50,
        "diameter": 8.0,
        "height": 2.0
      }
    ],
    "length": 100
  },
  "left": { ... },
  "right": { ... },
  "foot": { ... }
}
```

For complete JSON structure, see existing data files or documentation.

## Tips for Using Examples

### 1. Virtual Environment

Always use a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Import Path

Examples assume they're run from the project root:

```bash
# From project root
python examples/basic_analysis.py
```

If running from elsewhere, you may need to adjust `sys.path`.

### 3. OpenWind Required

Most examples require OpenWind for acoustic calculations. See `INSTALL.md` for installation.

### 4. Data Files

Examples reference data files that you need to provide. Common locations:
- `data_json/` - JSON geometry files
- `data/` - Other data files

### 5. Error Handling

Examples include basic error handling but may need adjustments for your use case.

## Creating Your Own Scripts

Based on these examples, you can create your own analysis scripts:

### Template Structure

```python
#!/usr/bin/env python3
"""
Your custom analysis script.
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flute_data import FluteData
from analysis_module import FluteAnalyzer

def main():
    # Your analysis code here
    pass

if __name__ == '__main__':
    sys.exit(main())
```

### Common Patterns

**Loading multiple flutes**:
```python
flutes = []
for json_file in Path('data_json').glob('*.json'):
    flutes.append(FluteData(str(json_file)))
```

**Comparing flutes**:
```python
analyzer = FluteAnalyzer(flutes)
inharmonicity = analyzer.calculate_inharmonicity()

# Compare results
for flute_name, results in inharmonicity.items():
    print(f"{flute_name}: {results}")
```

**Generating plots**:
```python
import matplotlib.pyplot as plt

fig = analyzer.plot_inharmonicity()
plt.savefig('inharmonicity.pdf')
plt.show()
```

## Getting Help

- **Documentation**: See main README.md and ARCHITECTURE.md
- **API Reference**: Check docstrings in module files
- **Issues**: Report problems at GitHub Issues

## Contributing Examples

Have a useful example? Please contribute!

1. Create your example script
2. Test it thoroughly
3. Add documentation
4. Submit a pull request

See `CONTRIBUTING.md` for guidelines.

---

**Note**: These examples are for educational purposes. For production use, consider error handling, logging, and configuration management.
