"""
Basic analysis example for Traverso Analyzer.

This example demonstrates how to:
1. Load a flute from JSON
2. Perform basic acoustic analysis
3. Calculate inharmonicity
4. Export results

This is a minimal example for getting started.
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Example imports (may need adjustment based on actual structure)
try:
    from flute_data import FluteData
    from analysis_module import FluteAnalyzer
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running this from the project root directory.")
    sys.exit(1)


def main():
    """
    Main example function.

    Note: This example requires a valid flute JSON file.
    """
    print("Traverso Analyzer - Basic Analysis Example")
    print("=" * 60)

    # Example JSON file path (adjust to your actual data)
    json_file = "path/to/your/flute.json"

    # Check if file exists
    if not Path(json_file).exists():
        print(f"\n⚠️  Example JSON file not found: {json_file}")
        print("\nTo run this example:")
        print("1. Update the 'json_file' variable with path to your flute JSON")
        print("2. Or use: python examples/basic_analysis.py /path/to/flute.json")
        print("\nExample JSON structure:")
        print("""
{
  "flute_model": "My_Flute",
  "headjoint": {
    "measurements": [
      {"position": 0, "diameter": 19.0},
      {"position": 100, "diameter": 19.5}
    ],
    "length": 100
  },
  ...
}
        """)
        return

    try:
        # Step 1: Load flute data
        print(f"\n1. Loading flute from: {json_file}")
        flute = FluteData(json_file)
        print(f"   ✅ Loaded: {flute.flute_model}")

        # Step 2: Create analyzer
        print("\n2. Creating acoustic analyzer...")
        analyzer = FluteAnalyzer([flute])
        print(f"   ✅ Analyzer created with {len(analyzer.ordered_notes)} notes")

        # Step 3: Calculate inharmonicity
        print("\n3. Calculating inharmonicity...")
        inharmonicity = analyzer.calculate_inharmonicity()
        print("   ✅ Inharmonicity calculated")

        # Step 4: Display results
        print("\n4. Results:")
        print(f"\n   Flute: {flute.flute_model}")
        print("   " + "-" * 50)

        for note in analyzer.ordered_notes:
            cents = inharmonicity[flute.flute_model].get(note, float('nan'))
            if not isnan(cents):
                print(f"   {note:3s}: {cents:+7.2f} cents")
            else:
                print(f"   {note:3s}: N/A")

        # Step 5: Export results (optional)
        export_csv = False  # Set to True to export
        if export_csv:
            output_path = "analysis_results.csv"
            print(f"\n5. Exporting results to: {output_path}")
            analyzer.export_results_to_csv(output_path)
            print(f"   ✅ Results exported")

        print("\n" + "=" * 60)
        print("Example completed successfully!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


def isnan(value):
    """Check if value is NaN."""
    import math
    return math.isnan(value)


if __name__ == '__main__':
    # Allow passing JSON file as command line argument
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
        # Update the json_file variable in main
        import inspect
        main.__code__ = main.__code__.replace(co_consts=(json_file,))

    sys.exit(main())
