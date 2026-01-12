"""
Pytest configuration and shared fixtures.

This module contains pytest fixtures that are shared across multiple test modules.
"""

import pytest
import json
import tempfile
from pathlib import Path
from typing import Dict, Any


@pytest.fixture
def minimal_flute_json() -> Dict[str, Any]:
    """
    Provide a minimal valid flute JSON structure for testing.

    Returns:
        Dictionary representing a minimal valid flute configuration.
    """
    return {
        "flute_model": "Test_Flute_Minimal",
        "headjoint": {
            "measurements": [
                {"position": 0.0, "diameter": 19.0},
                {"position": 100.0, "diameter": 18.0}
            ],
            "holes": [
                {
                    "label": "embouchure",
                    "position": 20.0,
                    "diameter": 12.0,
                    "chimney_height": 5.0
                }
            ],
            "external_measurements": [
                {"position": 0.0, "external_diameter": 25.0},
                {"position": 100.0, "external_diameter": 24.0}
            ],
            "joints": {
                "right_end": {
                    "male": True,
                    "overlap": 10.0,
                    "length": 15.0,
                    "diameter_internal_start": 18.0,
                    "diameter_internal_end": 17.5
                }
            }
        },
        "left": {
            "measurements": [
                {"position": 0.0, "diameter": 18.0},
                {"position": 150.0, "diameter": 16.0}
            ],
            "holes": [],
            "external_measurements": [
                {"position": 0.0, "external_diameter": 24.0},
                {"position": 150.0, "external_diameter": 22.0}
            ],
            "joints": {
                "left_end": {
                    "male": False,
                    "overlap": 10.0,
                    "length": 15.0
                },
                "right_end": {
                    "male": True,
                    "overlap": 10.0,
                    "length": 15.0,
                    "diameter_internal_start": 16.0,
                    "diameter_internal_end": 15.5
                }
            }
        },
        "right": {
            "measurements": [
                {"position": 0.0, "diameter": 16.0},
                {"position": 150.0, "diameter": 14.0}
            ],
            "holes": [
                {
                    "label": "hole_1",
                    "position": 50.0,
                    "diameter": 8.0,
                    "chimney_height": 3.0
                }
            ],
            "external_measurements": [
                {"position": 0.0, "external_diameter": 22.0},
                {"position": 150.0, "external_diameter": 20.0}
            ],
            "joints": {
                "left_end": {
                    "male": False,
                    "overlap": 10.0,
                    "length": 15.0
                },
                "right_end": {
                    "male": True,
                    "overlap": 10.0,
                    "length": 15.0,
                    "diameter_internal_start": 14.0,
                    "diameter_internal_end": 13.5
                }
            }
        },
        "foot": {
            "measurements": [
                {"position": 0.0, "diameter": 14.0},
                {"position": 100.0, "diameter": 12.0}
            ],
            "holes": [],
            "external_measurements": [
                {"position": 0.0, "external_diameter": 20.0},
                {"position": 100.0, "external_diameter": 18.0}
            ],
            "joints": {
                "left_end": {
                    "male": False,
                    "overlap": 10.0,
                    "length": 15.0
                }
            }
        }
    }


@pytest.fixture
def temp_flute_json_file(minimal_flute_json, tmp_path) -> Path:
    """
    Create a temporary JSON file with minimal flute data.

    Args:
        minimal_flute_json: Minimal flute JSON data fixture
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to the temporary JSON file.
    """
    json_file = tmp_path / "test_flute.json"
    with open(json_file, 'w') as f:
        json.dump(minimal_flute_json, f, indent=2)
    return json_file


@pytest.fixture
def temp_db_path(tmp_path) -> Path:
    """
    Provide a temporary database path for testing.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to temporary database file.
    """
    return tmp_path / "test_flute_analysis.db"
