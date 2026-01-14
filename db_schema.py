"""
Esquema de base de datos para almacenar geometría de flautas y resultados de análisis acústico.

Este módulo define las tablas SQL necesarias para almacenar:
- Información geométrica de las flautas (desde JSON)
- Parámetros de cálculo de impedancia
- Resultados de los cálculos de impedancia (serializados)
"""

import sqlite3
from pathlib import Path
from typing import Optional
import logging
import time

logger = logging.getLogger(__name__)

# Nombre del archivo de base de datos por defecto
# Intentar usar ubicación local fuera de Google Drive si existe db_config
try:
    from db_config import DB_PATH as DEFAULT_DB_PATH
except ImportError:
    # Fallback a ubicación original si no existe db_config
    DEFAULT_DB_PATH = Path(__file__).parent / "flute_analysis.db"

# Timeout para operaciones de base de datos (en segundos)
DB_TIMEOUT = 10.0

# Número máximo de reintentos para operaciones de I/O
MAX_RETRIES = 3

# Tiempo de espera entre reintentos (en segundos)
RETRY_DELAY = 0.5


def create_database_schema(db_path: Optional[Path] = None) -> Path:
    """
    Crea el esquema de la base de datos si no existe.
    
    Args:
        db_path: Ruta al archivo de base de datos. Si es None, usa DEFAULT_DB_PATH.
    
    Returns:
        Path al archivo de base de datos creado.
    
    Raises:
        sqlite3.OperationalError: Si hay un error de I/O o acceso a la base de datos.
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Intentar conectar con reintentos para manejar errores de I/O
    conn = None
    for attempt in range(MAX_RETRIES):
        try:
            conn = sqlite3.connect(str(db_path), timeout=DB_TIMEOUT)
            break
        except (sqlite3.OperationalError, OSError) as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"Error conectando a la base de datos (intento {attempt + 1}/{MAX_RETRIES}): {e}. Reintentando...")
                time.sleep(RETRY_DELAY * (2 ** attempt))  # Backoff exponencial
            else:
                logger.error(f"Error crítico conectando a la base de datos después de {MAX_RETRIES} intentos: {e}")
                raise
    
    if conn is None:
        raise sqlite3.OperationalError("No se pudo establecer conexión con la base de datos")
    
    cursor = conn.cursor()
    
    try:
        # Tabla 1: Información general de flautas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flutes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flute_model TEXT NOT NULL UNIQUE,
                json_source_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,  -- JSON array de notas disponibles
                description TEXT
            )
        """)
        
        # Tabla 2: Geometría de las partes de la flauta (almacenada como JSON)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flute_geometry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flute_id INTEGER NOT NULL,
                part_name TEXT NOT NULL,  -- 'headjoint', 'left', 'right', 'foot'
                geometry_json TEXT NOT NULL,  -- JSON con measurements, holes, etc.
                FOREIGN KEY (flute_id) REFERENCES flutes(id) ON DELETE CASCADE,
                UNIQUE(flute_id, part_name)
            )
        """)
        
        # Tabla 3: Parámetros de cálculo de impedancia
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS impedance_calculation_params (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flute_id INTEGER NOT NULL,
                calculation_hash TEXT NOT NULL,  -- Hash único de los parámetros
                temperature REAL NOT NULL,  -- Temperatura en Celsius
                la_frequency REAL NOT NULL,  -- Frecuencia del La (diapason) en Hz
                freq_range_start REAL NOT NULL,  -- Inicio del rango de frecuencias
                freq_range_end REAL NOT NULL,  -- Fin del rango de frecuencias
                freq_range_step REAL NOT NULL,  -- Paso del rango de frecuencias
                fing_chart_file TEXT NOT NULL,  -- Ruta al archivo de digitaciones
                fing_chart_content TEXT,  -- Contenido del archivo de digitaciones (para reproducibilidad)
                player_type TEXT DEFAULT 'FLUTE',  -- Tipo de player
                radiation_category TEXT DEFAULT 'infinite_flanged',
                source_location TEXT DEFAULT 'embouchure',
                interp BOOLEAN DEFAULT 1,
                stopper_offset_m REAL,  -- Offset del corcho en metros
                embouchure_radius_m REAL,  -- Radio de embocadura en metros
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (flute_id) REFERENCES flutes(id) ON DELETE CASCADE,
                UNIQUE(flute_id, calculation_hash)
            )
        """)
        
        # Tabla 4: Geometría del bore para OpenWind (serializada)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bore_geometry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                calculation_params_id INTEGER NOT NULL,
                bore_segments_json TEXT NOT NULL,  -- JSON array de segmentos [x_start, x_end, r_start, r_end, type]
                combined_measurements_json TEXT,  -- JSON array de mediciones combinadas
                FOREIGN KEY (calculation_params_id) REFERENCES impedance_calculation_params(id) ON DELETE CASCADE
            )
        """)
        
        # Tabla 5: Agujeros laterales para OpenWind (serializada)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS side_holes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                calculation_params_id INTEGER NOT NULL,
                side_holes_json TEXT NOT NULL,  -- JSON array de agujeros [label, position, chimney, radius, radius_out]
                FOREIGN KEY (calculation_params_id) REFERENCES impedance_calculation_params(id) ON DELETE CASCADE
            )
        """)
        
        # Tabla 6: Resultados de impedancia por nota
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS impedance_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                calculation_params_id INTEGER NOT NULL,
                note TEXT NOT NULL,  -- Nombre de la nota (ej: 'D', 'E', 'F')
                frequencies_json TEXT NOT NULL,  -- JSON array de frecuencias
                impedance_real_json TEXT NOT NULL,  -- JSON array de parte real de impedancia
                impedance_imag_json TEXT NOT NULL,  -- JSON array de parte imaginaria de impedancia
                antiresonance_freqs_json TEXT,  -- JSON array de frecuencias antiresonantes
                pressure_flow_data_json TEXT,  -- JSON con datos de presión y flujo (serializado)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (calculation_params_id) REFERENCES impedance_calculation_params(id) ON DELETE CASCADE,
                UNIQUE(calculation_params_id, note)
            )
        """)
        
        # Tabla 7: Geometría externa medida (perfiles externos desde JSON)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS external_geometry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flute_id INTEGER NOT NULL,
                part_name TEXT NOT NULL,  -- 'headjoint', 'left', 'right', 'foot'
                external_measurements_json TEXT NOT NULL,  -- JSON array de mediciones externas [position, external_diameter]
                source_type TEXT DEFAULT 'measured',  -- 'measured' o 'parametric'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (flute_id) REFERENCES flutes(id) ON DELETE CASCADE,
                UNIQUE(flute_id, part_name)
            )
        """)
        
        # Tabla 8: Parámetros de modelo paramétrico para geometría externa
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS external_geometry_parameters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flute_id INTEGER NOT NULL,
                part_name TEXT NOT NULL,  -- 'headjoint', 'left', 'right', 'foot'
                wall_thickness_type TEXT DEFAULT 'constant',  -- 'constant', 'variable', 'proportional'
                wall_thickness_mm REAL,  -- Espesor de pared en mm (para constant)
                wall_thickness_profile_json TEXT,  -- JSON con perfil de espesor variable [position, thickness]
                smoothing_factor REAL DEFAULT 1.0,  -- Factor de suavizado para transiciones
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (flute_id) REFERENCES flutes(id) ON DELETE CASCADE,
                UNIQUE(flute_id, part_name)
            )
        """)
        
        # Tabla 9: Análisis de sensibilidad (runs)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensitivity_analysis_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                base_flute_id INTEGER NOT NULL,
                parameter_name TEXT NOT NULL,  -- 'hole_undercut', 'part_taper', etc.
                min_value REAL NOT NULL,
                max_value REAL NOT NULL,
                num_steps INTEGER NOT NULL,
                target_part TEXT,  -- Para parámetros específicos de parte
                target_hole INTEGER,  -- Para parámetros específicos de agujero
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT,
                FOREIGN KEY (base_flute_id) REFERENCES flutes(id) ON DELETE CASCADE
            )
        """)
        
        # Tabla 10: Variantes de análisis de sensibilidad
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensitivity_variants (
                variant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                parameter_value REAL NOT NULL,
                variant_name TEXT NOT NULL,
                calculation_params_id INTEGER,  -- Referencia a impedance_calculation_params
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES sensitivity_analysis_runs(run_id) ON DELETE CASCADE,
                FOREIGN KEY (calculation_params_id) REFERENCES impedance_calculation_params(id) ON DELETE SET NULL
            )
        """)
        
        # Índices para mejorar rendimiento de consultas
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_flutes_model ON flutes(flute_model)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_flute_geometry_flute_id ON flute_geometry(flute_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_calc_params_flute_id ON impedance_calculation_params(flute_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_calc_params_hash ON impedance_calculation_params(calculation_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_impedance_calc_params_id ON impedance_results(calculation_params_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_impedance_note ON impedance_results(note)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_external_geometry_flute_id ON external_geometry(flute_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_external_geometry_params_flute_id ON external_geometry_parameters(flute_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensitivity_runs_base_flute ON sensitivity_analysis_runs(base_flute_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensitivity_runs_created ON sensitivity_analysis_runs(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensitivity_variants_run_id ON sensitivity_variants(run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sensitivity_variants_calc_params ON sensitivity_variants(calculation_params_id)")
        
        conn.commit()
        logger.info(f"Esquema de base de datos creado/verificado en: {db_path}")
        
    except sqlite3.Error as e:
        logger.error(f"Error creando esquema de base de datos: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
    
    return db_path


def get_database_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Obtiene una conexión a la base de datos con manejo robusto de errores.
    
    Args:
        db_path: Ruta al archivo de base de datos. Si es None, usa DEFAULT_DB_PATH.
    
    Returns:
        Conexión SQLite.
    
    Raises:
        sqlite3.OperationalError: Si hay un error de I/O o acceso a la base de datos.
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    db_path = Path(db_path)
    
    # Asegurar que la base de datos existe (con manejo de errores)
    if not db_path.exists():
        try:
            create_database_schema(db_path)
        except sqlite3.OperationalError as e:
            logger.error(f"No se pudo crear/verificar el esquema de la base de datos: {e}")
            raise
    
    # Intentar conectar con reintentos
    conn = None
    for attempt in range(MAX_RETRIES):
        try:
            conn = sqlite3.connect(str(db_path), timeout=DB_TIMEOUT)
            conn.row_factory = sqlite3.Row  # Permite acceso por nombre de columna
            # Configurar modo WAL para mejor rendimiento y menor bloqueo
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError:
                # Si WAL no está disponible, continuar sin él
                pass
            break
        except (sqlite3.OperationalError, OSError) as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"Error conectando a la base de datos (intento {attempt + 1}/{MAX_RETRIES}): {e}. Reintentando...")
                time.sleep(RETRY_DELAY * (2 ** attempt))  # Backoff exponencial
            else:
                logger.error(f"Error crítico conectando a la base de datos después de {MAX_RETRIES} intentos: {e}")
                raise
    
    if conn is None:
        raise sqlite3.OperationalError("No se pudo establecer conexión con la base de datos")
    
    return conn


if __name__ == "__main__":
    # Crear la base de datos si se ejecuta directamente
    db_path = create_database_schema()
    print(f"Base de datos creada en: {db_path}")

