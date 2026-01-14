"""
Configuración por defecto para el análisis de flautas.
Valores que pueden ser modificados por el usuario a través de la GUI.
"""

from pathlib import Path
import logging

# Importar sistema de configuración
try:
    from config import get_config
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    logging.warning("config.py no disponible, usando rutas por defecto")

# ==================== PARÁMETROS ACÚSTICOS ====================

# Diapasón (frecuencia de La en Hz)
DEFAULT_LA_FREQUENCY = 415.0  # Barroco estándar
LA_FREQUENCY_MIN = 380.0
LA_FREQUENCY_MAX = 450.0

# Temperatura (°C)
DEFAULT_TEMPERATURE = 20.0
TEMPERATURE_MIN = 0.0
TEMPERATURE_MAX = 40.0

# Presión atmosférica (Pa)
DEFAULT_PRESSURE = 101325.0

# Humedad relativa (%)
DEFAULT_HUMIDITY = 50.0

# ==================== RANGOS DE FRECUENCIA ====================

# Rango para cálculo de impedancia
IMPEDANCE_FREQ_MIN = 100.0  # Hz
IMPEDANCE_FREQ_MAX = 3000.0  # Hz
IMPEDANCE_FREQ_STEP = 2.0  # Hz

# Rango para análisis de resonancia
RESONANCE_FREQ_MIN = 200.0  # Hz
RESONANCE_FREQ_MAX = 2500.0  # Hz

# ==================== PARÁMETROS DE OPENWIND ====================

# Categorías de radiación
# None usa los defaults de OpenWind para cada tipo de instrumento
DEFAULT_RADIATION_CATEGORY = None

# Pérdidas en las paredes
DEFAULT_LOSSES = True

# Modelo de temperatura
DEFAULT_TEMPERATURE_MODEL = "Webster-Lokshin"

# ==================== PATHS Y DIRECTORIOS ====================

# Directorio base del script
SCRIPT_DIR = Path(__file__).resolve().parent

# Directorio de datos JSON (usar sistema de configuración si está disponible)
if CONFIG_AVAILABLE:
    try:
        DEFAULT_DATA_JSON_DIR = get_config().data_dir
    except Exception:
        DEFAULT_DATA_JSON_DIR = SCRIPT_DIR / "data_json"
else:
    DEFAULT_DATA_JSON_DIR = SCRIPT_DIR / "data_json"

# Base de datos (usar sistema de configuración si está disponible)
DEFAULT_DB_NAME = "flute_analysis.db"
if CONFIG_AVAILABLE:
    try:
        DEFAULT_DB_PATH = get_config().db_path
    except Exception:
        DEFAULT_DB_PATH = SCRIPT_DIR / DEFAULT_DB_NAME
else:
    DEFAULT_DB_PATH = SCRIPT_DIR / DEFAULT_DB_NAME

# Directorio para exports
DEFAULT_EXPORT_DIR = SCRIPT_DIR / "exports"

# Directorio para G-code
DEFAULT_GCODE_DIR = SCRIPT_DIR / "gcode_output"

# Directorio para planos de ingeniería
DEFAULT_DRAWINGS_DIR = SCRIPT_DIR / "engineering_drawings"

# ==================== NOTAS Y DIGITACIÓN ====================

# Orden canónico de notas
CANONICAL_NOTE_ORDER = [
    "D", "Ds", "E", "F", "Fs", "G", "Gs",
    "A", "As", "B", "C", "Cs", "D2", "Ds2", "E2"
]

# Archivo de digitación por defecto
DEFAULT_FINGERCHART_FILENAME = "traverso_fingerchart.txt"
if CONFIG_AVAILABLE:
    try:
        DEFAULT_FING_CHART_PATH = get_config().fingering_chart_path
    except Exception:
        DEFAULT_FING_CHART_PATH = SCRIPT_DIR / DEFAULT_FINGERCHART_FILENAME
else:
    DEFAULT_FING_CHART_PATH = SCRIPT_DIR / DEFAULT_FINGERCHART_FILENAME

# Notas mínimas esperadas para análisis completo
MINIMUM_NOTES_FOR_ANALYSIS = ["D", "E", "Fs", "G", "A", "B", "Cs"]

# ==================== CÁLCULO DE FRECUENCIAS ====================

# Semitonos desde La para cada nota
# La = 0, La# = 1, Si = 2, etc.
NOTE_SEMITONES_FROM_A = {
    "D": -7, "Ds": -6, "E": -5, "F": -4, "Fs": -3,
    "G": -2, "Gs": -1, "A": 0, "As": 1, "B": 2,
    "C": 3, "Cs": 4, "D2": 5, "Ds2": 6, "E2": 7
}

# ==================== G-CODE DEFAULTS ====================

# Parámetros de corte por defecto
GCODE_SPINDLE_SPEED = 2000  # RPM
GCODE_FEED_RATE = 50  # mm/min
GCODE_SAFE_Z = 5.0  # mm
GCODE_TOOL_DIAMETER = 3.0  # mm

# Estrategia de desbaste
GCODE_ROUGHING_STRATEGY = "longitudinal"  # "longitudinal" o "transversal"

# Modo económico
GCODE_ECONOMY_MODE = False

# Resolución de interpolación
GCODE_INTERPOLATION_STEP = 0.5  # mm

# ==================== PLANOS DE INGENIERÍA ====================

# Tamaño de página
DRAWING_PAGE_SIZE = "A3"  # "A3" o "A4"

# Orientación
DRAWING_ORIENTATION = "landscape"  # "landscape" o "portrait"

# Escala
DRAWING_SCALE = 1.0  # 1:1

# Grid
DRAWING_GRID_MM = 1.0  # Grilla de 1mm

# ==================== VISUALIZACIÓN 3D ====================

# Colores por defecto para partes
PART_COLORS_3D = {
    "headjoint": "lightblue",
    "left": "tan",
    "right": "wheat",
    "foot": "sandybrown"
}

# Calidad de malla (tessellation)
DEFAULT_MESH_QUALITY = 100
MESH_QUALITY_MIN = 10
MESH_QUALITY_MAX = 500

# ==================== ANÁLISIS ACÚSTICO AVANZADO ====================

# Número de armónicos a analizar
NUM_HARMONICS_DEFAULT = 3
NUM_HARMONICS_MAX = 6

# Umbrales para clasificación
INHARMONICITY_GOOD_THRESHOLD = 5.0  # cents
INHARMONICITY_ACCEPTABLE_THRESHOLD = 10.0  # cents

MOC_IDEAL = 1.0
MOC_GOOD_RANGE = (0.95, 1.05)
MOC_ACCEPTABLE_RANGE = (0.90, 1.10)

# ==================== CACHE Y PERFORMANCE ====================

# Guardar pressure/flow data por defecto
SAVE_PRESSURE_FLOW_DEFAULT = False

# Número máximo de flautas a cargar simultáneamente
MAX_FLUTES_TO_LOAD = 10

# Lazy loading para 3D
LAZY_LOAD_3D_MODELS = True

# ==================== LOGGING ====================

# Nivel de logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Formato de logging
LOG_FORMAT = '%(asctime)s - %(levelname)s [%(name)s:%(funcName)s:%(lineno)d] - %(message)s'

# Usar emojis en logging
USE_EMOJI_LOGGING = True

