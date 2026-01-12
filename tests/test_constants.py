"""
Tests for constants module.

Verifies that constants are defined correctly and utility functions work.
"""

import pytest
import numpy as np
from constants import (
    FLUTE_PARTS_ORDER,
    get_speed_of_sound,
    BASE_COLORS,
    MM_TO_M_FACTOR,
    M_TO_MM_FACTOR
)


class TestConstants:
    """Test constant values."""

    def test_flute_parts_order(self):
        """Test that flute parts are defined in correct order."""
        assert FLUTE_PARTS_ORDER == ["headjoint", "left", "right", "foot"]
        assert len(FLUTE_PARTS_ORDER) == 4

    def test_base_colors_defined(self):
        """Test that base colors list is defined."""
        assert isinstance(BASE_COLORS, list)
        assert len(BASE_COLORS) > 0
        # Check that colors are in hex format
        for color in BASE_COLORS:
            assert isinstance(color, str)
            assert color.startswith('#')

    def test_conversion_factors(self):
        """Test that conversion factors are correct."""
        assert MM_TO_M_FACTOR == 1e-3
        assert M_TO_MM_FACTOR == 1e3
        # Test that they're reciprocals
        assert abs(MM_TO_M_FACTOR * M_TO_MM_FACTOR - 1.0) < 1e-10


class TestSpeedOfSound:
    """Test speed of sound calculation."""

    def test_speed_at_20_celsius(self):
        """Test speed of sound at 20°C (reference)."""
        speed = get_speed_of_sound(20.0)
        # Should be approximately 343 m/s at 20°C
        assert 342 < speed < 344

    def test_speed_at_0_celsius(self):
        """Test speed of sound at 0°C."""
        speed = get_speed_of_sound(0.0)
        # Should be approximately 331 m/s at 0°C
        assert 330 < speed < 332

    def test_speed_increases_with_temperature(self):
        """Test that speed increases with temperature."""
        speed_0 = get_speed_of_sound(0.0)
        speed_10 = get_speed_of_sound(10.0)
        speed_20 = get_speed_of_sound(20.0)

        assert speed_10 > speed_0
        assert speed_20 > speed_10

    def test_negative_absolute_zero_handling(self):
        """Test behavior at absolute zero and below."""
        # At absolute zero (-273.15°C), formula should give 0
        speed = get_speed_of_sound(-273.15)
        assert abs(speed) < 1e-6

        # Below absolute zero is physically meaningless
        # Function should handle it (may give complex number or raise error)
        # Just test that it doesn't crash
        try:
            speed = get_speed_of_sound(-300.0)
            # If it returns a value, it should be NaN or raise
            assert np.isnan(speed) or not np.isreal(speed)
        except (ValueError, RuntimeWarning):
            pass  # This is also acceptable behavior

    def test_return_type(self):
        """Test that function returns float."""
        speed = get_speed_of_sound(20.0)
        assert isinstance(speed, (float, np.floating))
