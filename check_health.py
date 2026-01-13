#!/usr/bin/env python3
"""
Health check script for Traverso Analyzer.

Verifies that the environment is correctly set up and all
dependencies are available.
"""

import sys
import subprocess
from pathlib import Path


def print_header(text):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def print_success(text):
    """Print success message."""
    print(f"✅ {text}")


def print_error(text):
    """Print error message."""
    print(f"❌ {text}")


def print_warning(text):
    """Print warning message."""
    print(f"⚠️  {text}")


def check_python_version():
    """Check Python version."""
    print_header("Python Version")

    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if version.major == 3 and version.minor >= 8:
        print_success(f"Python {version_str} (meets requirement: >=3.8)")
        return True
    else:
        print_error(f"Python {version_str} (requires: >=3.8)")
        return False


def check_module(module_name, display_name=None):
    """Check if a Python module is available."""
    if display_name is None:
        display_name = module_name

    try:
        __import__(module_name)
        print_success(f"{display_name} available")
        return True
    except ImportError:
        print_error(f"{display_name} NOT available")
        return False


def check_dependencies():
    """Check core dependencies."""
    print_header("Core Dependencies")

    results = []
    results.append(check_module("numpy", "NumPy"))
    results.append(check_module("scipy", "SciPy"))
    results.append(check_module("matplotlib", "Matplotlib"))
    results.append(check_module("PyQt5", "PyQt5"))

    return all(results)


def check_openwind():
    """Check OpenWind installation."""
    print_header("OpenWind (Acoustic Simulation)")

    try:
        import openwind
        version = getattr(openwind, '__version__', 'unknown')
        print_success(f"OpenWind available (version: {version})")
        return True
    except ImportError:
        print_error("OpenWind NOT available")
        print("  Installation: see INSTALL.md for OpenWind setup instructions")
        return False


def check_optional_dependencies():
    """Check optional dependencies."""
    print_header("Optional Dependencies")

    check_module("notion_client", "Notion Client (for reports)")
    check_module("requests", "Requests (for Notion)")

    # These are informational only
    return True


def check_dev_tools():
    """Check development tools."""
    print_header("Development Tools (Optional)")

    check_module("pytest", "pytest")
    check_module("black", "black")
    check_module("flake8", "flake8")
    check_module("mypy", "mypy")

    return True


def check_project_files():
    """Check that key project files exist."""
    print_header("Project Structure")

    required_files = [
        "README.md",
        "requirements.txt",
        "pyproject.toml",
        "ARCHITECTURE.md",
        "CONTRIBUTING.md",
        "INSTALL.md",
    ]

    all_exist = True
    for filename in required_files:
        if Path(filename).exists():
            print_success(f"{filename} exists")
        else:
            print_error(f"{filename} missing")
            all_exist = False

    return all_exist


def check_main_applications():
    """Check that main application files exist."""
    print_header("Main Applications")

    apps = [
        ("unified_flute_gui_qt.py", "Main GUI (PyQt5)"),
        ("flute_experimenter.py", "Experimenter GUI"),
        ("flute_optimizer_gui.py", "Optimizer GUI"),
    ]

    all_exist = True
    for filename, description in apps:
        if Path(filename).exists():
            print_success(f"{description}: {filename}")
        else:
            print_error(f"{description}: {filename} missing")
            all_exist = False

    return all_exist


def check_database():
    """Check database setup."""
    print_header("Database")

    db_path = Path("flute_analysis.db")
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        print_success(f"Database exists: {db_path} ({size_mb:.2f} MB)")
    else:
        print_warning("Database not yet created (will be created on first use)")

    return True


def run_quick_test():
    """Run quick import test."""
    print_header("Quick Import Test")

    try:
        from constants import get_speed_of_sound
        speed = get_speed_of_sound(20.0)
        expected = 343.0  # Approximate

        if abs(speed - expected) < 5:
            print_success(f"Speed of sound calculation: {speed:.2f} m/s")
            return True
        else:
            print_warning(f"Speed of sound calculation: {speed:.2f} m/s (unexpected)")
            return True
    except Exception as e:
        print_error(f"Import test failed: {e}")
        return False


def main():
    """Run all health checks."""
    print("""
╔══════════════════════════════════════════════════════════╗
║          Traverso Analyzer - Health Check               ║
║                                                          ║
║  Verifying environment and dependencies...              ║
╚══════════════════════════════════════════════════════════╝
    """)

    results = {
        'Python Version': check_python_version(),
        'Core Dependencies': check_dependencies(),
        'OpenWind': check_openwind(),
        'Optional Dependencies': check_optional_dependencies(),
        'Dev Tools': check_dev_tools(),
        'Project Files': check_project_files(),
        'Main Applications': check_main_applications(),
        'Database': check_database(),
        'Quick Test': run_quick_test(),
    }

    # Summary
    print_header("Summary")

    critical = ['Python Version', 'Core Dependencies', 'Project Files', 'Main Applications']
    critical_passed = all(results[key] for key in critical if key in results)
    openwind_passed = results.get('OpenWind', False)

    if critical_passed and openwind_passed:
        print_success("All critical checks passed!")
        print_success("Environment is fully set up and ready to use.")
        print("\nYou can now run:")
        print("  python unified_flute_gui_qt.py")
        return 0
    elif critical_passed:
        print_warning("Critical checks passed, but OpenWind is not installed.")
        print("\n⚠️  OpenWind is required for acoustic analysis.")
        print("   See INSTALL.md for installation instructions.")
        return 1
    else:
        print_error("Some critical checks failed.")
        print("\nPlease fix the issues above before using the application.")
        print("See INSTALL.md for installation instructions.")
        return 2


if __name__ == '__main__':
    sys.exit(main())
