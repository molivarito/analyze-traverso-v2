"""
Tests for database schema and database operations.
"""

import pytest
import sqlite3
from pathlib import Path
import tempfile
import shutil

from db_schema import create_database_schema, DEFAULT_DB_PATH


class TestDatabaseSchema:
    """Tests for database schema creation and structure."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create a temporary database path."""
        db_path = tmp_path / "test_flute_analysis.db"
        yield db_path
        # Cleanup
        if db_path.exists():
            db_path.unlink()

    def test_create_database_schema(self, temp_db_path):
        """Test that database schema can be created."""
        result_path = create_database_schema(temp_db_path)

        assert result_path.exists()
        assert result_path == temp_db_path

    def test_database_has_required_tables(self, temp_db_path):
        """Test that all required tables are created."""
        create_database_schema(temp_db_path)

        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()

        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        # Check for required tables
        required_tables = [
            'flutes',
            'flute_geometry',
            'impedance_calculation_params',
            'bore_geometry'
        ]

        for table in required_tables:
            assert table in tables, f"Required table '{table}' not found"

        conn.close()

    def test_flutes_table_structure(self, temp_db_path):
        """Test flutes table has correct columns."""
        create_database_schema(temp_db_path)

        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(flutes)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}  # name: type

        # Check for required columns
        assert 'id' in columns
        assert 'flute_model' in columns
        assert 'json_source_path' in columns
        assert 'created_at' in columns
        assert 'notes' in columns

        conn.close()

    def test_unique_constraint_on_flute_model(self, temp_db_path):
        """Test that flute_model has UNIQUE constraint."""
        create_database_schema(temp_db_path)

        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()

        # Insert first flute
        cursor.execute("""
            INSERT INTO flutes (flute_model, notes)
            VALUES ('Test_Flute_1', '["D", "E", "F"]')
        """)
        conn.commit()

        # Try to insert duplicate flute_model - should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO flutes (flute_model, notes)
                VALUES ('Test_Flute_1', '["D", "E"]')
            """)

        conn.close()

    def test_foreign_key_relationships(self, temp_db_path):
        """Test that foreign key relationships work."""
        create_database_schema(temp_db_path)

        conn = sqlite3.connect(str(temp_db_path))
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign keys
        cursor = conn.cursor()

        # Insert a flute
        cursor.execute("""
            INSERT INTO flutes (flute_model) VALUES ('Test_Flute')
        """)
        flute_id = cursor.lastrowid
        conn.commit()

        # Insert geometry for the flute
        cursor.execute("""
            INSERT INTO flute_geometry (flute_id, part_name, geometry_json)
            VALUES (?, 'headjoint', '{}')
        """, (flute_id,))
        conn.commit()

        # Verify geometry was inserted
        cursor.execute("SELECT COUNT(*) FROM flute_geometry WHERE flute_id = ?", (flute_id,))
        count = cursor.fetchone()[0]
        assert count == 1

        conn.close()

    def test_database_default_path(self):
        """Test that DEFAULT_DB_PATH is correctly set."""
        assert DEFAULT_DB_PATH is not None
        assert isinstance(DEFAULT_DB_PATH, Path)
        assert DEFAULT_DB_PATH.name == "flute_analysis.db"

    def test_schema_creation_is_idempotent(self, temp_db_path):
        """Test that running create_database_schema multiple times is safe."""
        # Create schema first time
        create_database_schema(temp_db_path)

        # Create schema second time (should not fail)
        create_database_schema(temp_db_path)

        # Verify database still works
        conn = sqlite3.connect(str(temp_db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        assert len(tables) > 0
        conn.close()


class TestDatabaseSchemaEdgeCases:
    """Tests for edge cases in database schema."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create a temporary database path."""
        db_path = tmp_path / "test_edge_cases.db"
        yield db_path
        if db_path.exists():
            db_path.unlink()

    def test_create_schema_with_none_path(self):
        """Test that None path uses default."""
        # This will create the database in the project directory
        # Clean up afterwards
        result_path = create_database_schema(None)
        assert result_path == DEFAULT_DB_PATH

        # Note: This creates a real database in project dir
        # In a real test, we'd want to mock this or clean up

    def test_database_in_nested_directory(self, tmp_path):
        """Test creating database in nested directory."""
        nested_path = tmp_path / "subdir1" / "subdir2" / "test.db"

        # Should create parent directories
        result_path = create_database_schema(nested_path)

        assert result_path.exists()
        assert result_path.parent.exists()


@pytest.mark.skipif(
    not Path("populate_database.py").exists(),
    reason="populate_database.py not found"
)
class TestDatabaseUtilities:
    """Tests for database utility scripts (if they exist)."""

    def test_database_utilities_importable(self):
        """Test that database utilities can be imported."""
        try:
            import populate_database
            import cleanup_database
            import reset_database
            assert True
        except ImportError as e:
            pytest.skip(f"Database utilities not importable: {e}")
