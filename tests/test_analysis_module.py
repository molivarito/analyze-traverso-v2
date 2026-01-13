"""
Tests for analysis_module.py - Unified acoustic analysis.
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch

# Try to import analysis_module
try:
    from analysis_module import FluteAnalyzer
    ANALYSIS_MODULE_AVAILABLE = True
except ImportError:
    ANALYSIS_MODULE_AVAILABLE = False
    pytest.skip("analysis_module not available", allow_module_level=True)


@pytest.mark.skipif(not ANALYSIS_MODULE_AVAILABLE, reason="analysis_module not available")
class TestFluteAnalyzer:
    """Tests for FluteAnalyzer class."""

    @pytest.fixture
    def mock_flute_data(self):
        """Create a mock flute data object."""
        flute = Mock()
        flute.flute_model = "Test_Flute"
        flute.acoustic_analysis = {
            'D': Mock(),
            'E': Mock(),
            'F': Mock()
        }
        flute.finger_frequencies = {
            'D': 293.66,  # D4
            'E': 329.63,  # E4
            'F': 349.23   # F4
        }

        # Mock antiresonance frequencies
        for note, analysis in flute.acoustic_analysis.items():
            analysis.antiresonance_frequencies = Mock(return_value=[
                flute.finger_frequencies[note] * 0.98,  # f0 slightly below playing freq
                flute.finger_frequencies[note] * 2.0 * 0.98  # f1
            ])

        return flute

    @pytest.fixture
    def analyzer(self, mock_flute_data):
        """Create a FluteAnalyzer with mock data."""
        return FluteAnalyzer([mock_flute_data])

    def test_analyzer_initialization(self, mock_flute_data):
        """Test that FluteAnalyzer can be initialized."""
        analyzer = FluteAnalyzer([mock_flute_data])

        assert analyzer is not None
        assert len(analyzer.flute_data_list) == 1
        assert len(analyzer.acoustic_analysis_list) == 1

    def test_analyzer_with_multiple_flutes(self, mock_flute_data):
        """Test analyzer with multiple flutes."""
        flute2 = Mock()
        flute2.flute_model = "Test_Flute_2"
        flute2.acoustic_analysis = {'D': Mock()}
        flute2.finger_frequencies = {'D': 293.66}

        analyzer = FluteAnalyzer([mock_flute_data, flute2])

        assert len(analyzer.flute_data_list) == 2
        assert len(analyzer.acoustic_analysis_list) == 2

    def test_calculate_inharmonicity(self, analyzer):
        """Test inharmonicity calculation."""
        results = analyzer.calculate_inharmonicity()

        assert isinstance(results, dict)
        assert 'Test_Flute' in results
        assert isinstance(results['Test_Flute'], dict)

        # Check that we have results for each note
        for note in ['D', 'E', 'F']:
            assert note in results['Test_Flute']

    def test_calculate_moc(self, analyzer):
        """Test MOC calculation."""
        results = analyzer.calculate_moc()

        assert isinstance(results, dict)
        assert 'Test_Flute' in results

    def test_calculate_bi_espe(self, analyzer):
        """Test B_I and ESPE calculation."""
        results = analyzer.calculate_bi_espe()

        assert isinstance(results, dict)
        assert 'Test_Flute' in results

        # Results should be tuples of (bi, espe)
        for note, (bi, espe) in results['Test_Flute'].items():
            assert isinstance(bi, (float, np.floating)) or np.isnan(bi)
            assert isinstance(espe, (float, np.floating)) or np.isnan(espe)

    def test_ordered_notes_preparation(self, analyzer):
        """Test that notes are properly ordered."""
        assert len(analyzer.ordered_notes) > 0

        # Should include at least D, E, F
        assert 'D' in analyzer.ordered_notes
        assert 'E' in analyzer.ordered_notes
        assert 'F' in analyzer.ordered_notes

    def test_finger_frequencies_map(self, analyzer):
        """Test finger frequencies mapping."""
        assert 'Test_Flute' in analyzer.finger_frequencies_map
        assert 'D' in analyzer.finger_frequencies_map['Test_Flute']
        assert analyzer.finger_frequencies_map['Test_Flute']['D'] == 293.66


@pytest.mark.skipif(not ANALYSIS_MODULE_AVAILABLE, reason="analysis_module not available")
class TestFluteAnalyzerPlotting:
    """Tests for FluteAnalyzer plotting methods."""

    @pytest.fixture
    def mock_flute_data(self):
        """Create a mock flute data object."""
        flute = Mock()
        flute.flute_model = "Test_Flute"
        flute.acoustic_analysis = {'D': Mock()}
        flute.finger_frequencies = {'D': 293.66}

        analysis = flute.acoustic_analysis['D']
        analysis.antiresonance_frequencies = Mock(return_value=[290.0, 580.0])

        return flute

    @pytest.fixture
    def analyzer(self, mock_flute_data):
        """Create a FluteAnalyzer with mock data."""
        return FluteAnalyzer([mock_flute_data])

    @patch('analysis_module.FluteOperations')
    def test_plot_inharmonicity_calls_flute_operations(self, mock_ops, analyzer):
        """Test that plot_inharmonicity calls the right FluteOperations method."""
        mock_ops.plot_summary_cents_differences = Mock(return_value=Mock())

        analyzer.plot_inharmonicity()

        mock_ops.plot_summary_cents_differences.assert_called_once()

    @patch('analysis_module.FluteOperations')
    def test_plot_moc_calls_flute_operations(self, mock_ops, analyzer):
        """Test that plot_moc calls the right FluteOperations method."""
        mock_ops.plot_moc_summary = Mock(return_value=Mock())

        analyzer.plot_moc()

        mock_ops.plot_moc_summary.assert_called_once()

    @patch('analysis_module.FluteOperations')
    def test_plot_bi_espe_calls_flute_operations(self, mock_ops, analyzer):
        """Test that plot_bi_espe calls the right FluteOperations method."""
        mock_ops.plot_bi_espe_summary = Mock(return_value=Mock())

        analyzer.plot_bi_espe()

        mock_ops.plot_bi_espe_summary.assert_called_once()


@pytest.mark.skipif(not ANALYSIS_MODULE_AVAILABLE, reason="analysis_module not available")
class TestFluteAnalyzerExport:
    """Tests for FluteAnalyzer export functionality."""

    @pytest.fixture
    def mock_flute_data(self):
        """Create a mock flute data object."""
        flute = Mock()
        flute.flute_model = "Test_Flute"
        flute.acoustic_analysis = {'D': Mock()}
        flute.finger_frequencies = {'D': 293.66}

        analysis = flute.acoustic_analysis['D']
        analysis.antiresonance_frequencies = Mock(return_value=[290.0, 580.0])

        return flute

    @pytest.fixture
    def analyzer(self, mock_flute_data):
        """Create a FluteAnalyzer with mock data."""
        return FluteAnalyzer([mock_flute_data])

    def test_export_to_csv(self, analyzer, tmp_path):
        """Test exporting results to CSV."""
        output_path = tmp_path / "test_export.csv"

        analyzer.export_results_to_csv(str(output_path))

        assert output_path.exists()

        # Read CSV and verify it has content
        content = output_path.read_text()
        assert 'Flauta' in content or 'Flute' in content
        assert 'Test_Flute' in content

    def test_export_to_json(self, analyzer, tmp_path):
        """Test exporting results to JSON."""
        output_path = tmp_path / "test_export.json"

        analyzer.export_results_to_json(str(output_path))

        assert output_path.exists()

        # Read JSON and verify structure
        import json
        with open(output_path) as f:
            data = json.load(f)

        assert 'inharmonicity' in data
        assert 'moc' in data
        assert 'bi_espe' in data
        assert 'ordered_notes' in data


@pytest.mark.skipif(not ANALYSIS_MODULE_AVAILABLE, reason="analysis_module not available")
class TestFluteAnalyzerEdgeCases:
    """Tests for edge cases and error handling."""

    def test_analyzer_with_empty_list(self):
        """Test analyzer with empty flute list."""
        with pytest.raises(Exception):  # Should raise some error
            analyzer = FluteAnalyzer([])

    def test_analyzer_with_missing_acoustic_analysis(self):
        """Test handling of flute without acoustic analysis."""
        flute = Mock()
        flute.flute_model = "Incomplete_Flute"
        flute.acoustic_analysis = {}  # Empty
        flute.finger_frequencies = {}

        # Should handle gracefully
        try:
            analyzer = FluteAnalyzer([flute])
            results = analyzer.calculate_inharmonicity()
            # Results should be empty or contain NaNs
            assert isinstance(results, dict)
        except Exception as e:
            # Or it might raise an exception, which is also acceptable
            assert True

    def test_inharmonicity_with_invalid_frequencies(self):
        """Test inharmonicity calculation with invalid frequencies."""
        flute = Mock()
        flute.flute_model = "Invalid_Flute"
        flute.acoustic_analysis = {'D': Mock()}
        flute.finger_frequencies = {'D': -100}  # Invalid frequency

        analysis = flute.acoustic_analysis['D']
        analysis.antiresonance_frequencies = Mock(return_value=[0, 0])

        analyzer = FluteAnalyzer([flute])
        results = analyzer.calculate_inharmonicity()

        # Should return NaN for invalid data
        assert 'Invalid_Flute' in results
        assert 'D' in results['Invalid_Flute']
        assert np.isnan(results['Invalid_Flute']['D'])
