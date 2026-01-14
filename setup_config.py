#!/usr/bin/env python3
"""
Automatic configuration setup for Traverso Analyzer.

Detects your system and creates an appropriate config.json file.
"""

import json
import os
import platform
from pathlib import Path


def detect_google_drive_path():
    """Detect Google Drive path on macOS."""
    system = platform.system()
    home = Path.home()

    if system == "Darwin":  # macOS
        # Check for Google Drive (multiple possible locations)
        possible_paths = [
            home / "Library/CloudStorage",
            home / "Google Drive",
            home / "GoogleDrive"
        ]

        for base_path in possible_paths:
            if base_path.exists():
                # Look for Google Drive folders
                if "CloudStorage" in str(base_path):
                    # Modern Google Drive location
                    for item in base_path.iterdir():
                        if item.is_dir() and "GoogleDrive" in item.name:
                            return item
                else:
                    return base_path

    elif system == "Linux":
        # Common Linux Google Drive locations
        possible_paths = [
            home / "GoogleDrive",
            home / "Google Drive",
            home / "gdrive"
        ]
        for path in possible_paths:
            if path.exists():
                return path

    elif system == "Windows":
        possible_paths = [
            Path("G:/My Drive"),  # Common mapped drive
            home / "Google Drive",
        ]
        for path in possible_paths:
            if path.exists():
                return path

    return None


def find_data_json_in_drive(drive_path):
    """Try to find data_json directory in Google Drive."""
    if not drive_path or not drive_path.exists():
        return None

    # Common patterns
    search_patterns = [
        "**/data_json",
        "**/*Traverso*/data_json",
        "**/*traverso*/data_json",
        "**/*INVESTIGACION*/data_json",
        "**/*flute*/data_json"
    ]

    for pattern in search_patterns:
        matches = list(drive_path.glob(pattern))
        if matches:
            # Return the first match that contains JSON files
            for match in matches:
                if any(match.glob("*.json")):
                    return match

    return None


def get_user_email():
    """Try to detect Google account email from Drive path."""
    drive_path = detect_google_drive_path()
    if drive_path and "GoogleDrive-" in str(drive_path):
        # Extract email from path like "GoogleDrive-user@gmail.com"
        name = drive_path.name
        if "-" in name:
            email_part = name.split("-", 1)[1]
            return email_part
    return None


def create_config_interactive():
    """Interactive configuration creation."""
    print("=" * 60)
    print("Traverso Analyzer - Configuration Setup")
    print("=" * 60)
    print()

    system = platform.system()
    print(f"Detected system: {system}")
    print()

    # Try to auto-detect Google Drive
    drive_path = detect_google_drive_path()
    data_json_path = None

    if drive_path:
        print(f"✓ Found Google Drive at: {drive_path}")
        data_json_path = find_data_json_in_drive(drive_path)
        if data_json_path:
            print(f"✓ Found data_json at: {data_json_path}")
    else:
        print("✗ Google Drive not auto-detected")

    print()
    print("Please choose a configuration option:")
    print()
    print("1. Use auto-detected paths (if available)")
    print("2. Enter paths manually")
    print("3. Use local data (./data_json)")
    print("4. Copy from config.json.example and edit manually")
    print()

    choice = input("Enter choice (1-4): ").strip()

    config = {}

    if choice == "1" and data_json_path:
        config["data_dir"] = str(data_json_path)
        config["db_path"] = str(Path.home() / ".flute_analysis" / "flute_analysis.db")
        config["fingering_chart"] = str(data_json_path / "traverso_fingerchart.txt")

    elif choice == "2":
        print()
        print("Enter your paths (use ~ for home directory):")
        data_dir = input("Data directory (data_json): ").strip()
        db_path = input("Database path [~/.flute_analysis/flute_analysis.db]: ").strip()
        fingering = input("Fingering chart (leave empty to auto-detect): ").strip()

        config["data_dir"] = data_dir
        config["db_path"] = db_path or "~/.flute_analysis/flute_analysis.db"
        if fingering:
            config["fingering_chart"] = fingering

    elif choice == "3":
        config["data_dir"] = "./data_json"
        config["db_path"] = "./flute_analysis.db"
        config["fingering_chart"] = "./data_json/traverso_fingerchart.txt"

    elif choice == "4":
        if Path("config.json.example").exists():
            import shutil
            shutil.copy("config.json.example", "config.json")
            print()
            print("✓ Copied config.json.example to config.json")
            print("Please edit config.json with your paths.")
            return True
        else:
            print("✗ config.json.example not found")
            return False
    else:
        print("Invalid choice")
        return False

    # Add helpful comments
    config["_comment"] = f"Auto-generated configuration for {system}"
    config["_created_by"] = "setup_config.py"

    # Write config file
    config_path = Path("config.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print()
    print("=" * 60)
    print(f"✓ Created config.json at: {config_path.resolve()}")
    print("=" * 60)
    print()
    print("Configuration:")
    for key, value in config.items():
        if not key.startswith("_"):
            print(f"  {key}: {value}")
    print()
    print("Next steps:")
    print("  1. Validate: python config.py --validate")
    print("  2. Check: python config.py --print")
    print("  3. Run: python unified_flute_gui_qt.py")
    print()

    return True


def create_config_for_user_pdelac():
    """Create pre-configured config.json for user pdelac (macOS + Google Drive)."""
    print("Creating pre-configured setup for macOS + Google Drive...")

    config = {
        "_comment": "Pre-configured for macOS with Google Drive - User: pdelac",
        "data_dir": "~/Library/CloudStorage/GoogleDrive-patodelac@gmail.com/My Drive/Main/3.-INVESTIGACION/codigo/software_en_uso/2025-Traverso-analysis/data_json",
        "db_path": "~/.flute_analysis/flute_analysis.db",
        "fingering_chart": "~/Library/CloudStorage/GoogleDrive-patodelac@gmail.com/My Drive/Main/3.-INVESTIGACION/codigo/software_en_uso/2025-Traverso-analysis/data_json/traverso_fingerchart.txt",
        "_notes": {
            "data_dir": "Apunta a tu Google Drive donde están todos los archivos JSON de flautas",
            "db_path": "Base de datos compartida en ~/.flute_analysis/ (contiene resultados pre-calculados)",
            "fingering_chart": "Archivo de digitaciones requerido por OpenWind",
            "conda_env": "Recuerda activar: conda activate OpenWind"
        }
    }

    config_path = Path("config.json")
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"✓ Created config.json at: {config_path.resolve()}")
    print()
    print("Next steps:")
    print("  1. conda activate OpenWind")
    print("  2. python config.py --validate")
    print("  3. python unified_flute_gui_qt.py")
    return True


if __name__ == "__main__":
    import sys

    # Check if config.json already exists
    if Path("config.json").exists():
        print("⚠️  config.json already exists!")
        print()
        response = input("Overwrite? (y/N): ").strip().lower()
        if response != 'y':
            print("Aborted.")
            sys.exit(0)
        print()

    # Check for special flag for pre-configured setup
    if len(sys.argv) > 1 and sys.argv[1] == "--pdelac":
        success = create_config_for_user_pdelac()
    else:
        success = create_config_interactive()

    sys.exit(0 if success else 1)
