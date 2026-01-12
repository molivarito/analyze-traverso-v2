"""
Test that all core modules can be imported successfully.

This basic test ensures that there are no syntax errors or missing
dependencies that would prevent modules from being imported.
"""

import pytest


class TestCoreImports:
    """Test importing core modules."""

    def test_import_constants(self):
        """Test importing constants module."""
        import constants
        assert hasattr(constants, 'FLUTE_PARTS_ORDER')
        assert hasattr(constants, 'get_speed_of_sound')

    def test_import_flute_data(self):
        """Test importing flute_data module."""
        import flute_data
        assert hasattr(flute_data, 'FluteData')

    def test_import_flute_operations(self):
        """Test importing flute_operations module."""
        import flute_operations
        assert hasattr(flute_operations, 'FluteOperations')

    def test_import_analysis_module(self):
        """Test importing analysis_module."""
        import analysis_module
        assert hasattr(analysis_module, 'FluteAnalyzer')

    def test_import_db_schema(self):
        """Test importing db_schema module."""
        import db_schema
        assert hasattr(db_schema, 'create_database_schema')

    def test_import_flute_db_manager(self):
        """Test importing flute_db_manager module."""
        import flute_db_manager
        assert hasattr(flute_db_manager, 'FluteDBManager')


class TestUtilityImports:
    """Test importing utility modules."""

    def test_import_default_config(self):
        """Test importing default_config module."""
        import default_config
        # Module should import successfully

    def test_import_gui_constants(self):
        """Test importing gui_constants module."""
        import gui_constants
        # Module should import successfully

    def test_import_geometry_modifier(self):
        """Test importing geometry_modifier module."""
        import geometry_modifier
        # Module should import successfully

    def test_import_sensitivity_analysis(self):
        """Test importing sensitivity_analysis module."""
        import sensitivity_analysis
        assert hasattr(sensitivity_analysis, 'SensitivityParameter')


class TestExternalDependencies:
    """Test that external dependencies are available."""

    def test_numpy_available(self):
        """Test that numpy is installed."""
        import numpy as np
        assert hasattr(np, 'array')

    def test_matplotlib_available(self):
        """Test that matplotlib is installed."""
        import matplotlib.pyplot as plt
        assert hasattr(plt, 'figure')

    def test_scipy_available(self):
        """Test that scipy is installed."""
        import scipy
        from scipy import interpolate
        assert hasattr(interpolate, 'interp1d')

    def test_pyqt5_available(self):
        """Test that PyQt5 is installed."""
        try:
            from PyQt5.QtWidgets import QApplication
            assert QApplication is not None
        except ImportError:
            pytest.skip("PyQt5 not available (optional for headless testing)")

    @pytest.mark.skip(reason="OpenWind requires special installation")
    def test_openwind_available(self):
        """Test that OpenWind is installed."""
        # Skip by default as OpenWind may not be available in CI
        import openwind
        assert hasattr(openwind, 'ImpedanceComputation')
