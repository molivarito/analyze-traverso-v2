"""
Constantes para la GUI Unificada de Análisis de Flautas.
Centraliza valores de configuración visual y dimensiones.
"""

# ==================== TAMAÑOS DE FIGURA ====================

# Tamaños estándar para plots de matplotlib
FIGURE_SIZE_SMALL = (10, 6)
FIGURE_SIZE_MEDIUM = (12, 7)
FIGURE_SIZE_LARGE = (14, 8)
FIGURE_SIZE_XLARGE = (12, 10)
FIGURE_SIZE_SUMMARY = (12, 8)

# ==================== FUENTES ====================

FONT_SIZE_SMALL = 9
FONT_SIZE_NORMAL = 10
FONT_SIZE_MEDIUM = 11
FONT_SIZE_LARGE = 12
FONT_SIZE_TITLE = 14

# ==================== DIMENSIONES DE GUI ====================

# Anchos de paneles
PANEL_WIDTH_3D = 200
PANEL_WIDTH_NARROW = 250
PANEL_WIDTH_MEDIUM = 300

# Márgenes y espaciado
LAYOUT_MARGIN = 5
LAYOUT_SPACING = 5
LAYOUT_MARGIN_TIGHT = 2

# Tamaños de widgets
SPINBOX_MIN_WIDTH = 80
BUTTON_MIN_HEIGHT = 30
TREE_MIN_WIDTH = 180

# ==================== COLORES Y ESTILOS ====================

# Colores para headers de tablas
COLOR_HEADER_BG = "#e0e0e0"
COLOR_WARNING_BG = "#fff3cd"
COLOR_ERROR_BG = "#f8d7da"
COLOR_SUCCESS_BG = "#d4edda"

# Estilos CSS
STYLE_HEADER = "font-weight: bold; background-color: #e0e0e0; padding: 5px;"
STYLE_CELL = "padding: 5px;"
STYLE_WARNING = "background-color: #fff3cd; padding: 10px; border-radius: 5px;"
STYLE_ERROR = "background-color: #f8d7da; padding: 10px; border-radius: 5px;"

# ==================== PARÁMETROS DE PLOTS ====================

# Grid
GRID_LINESTYLE = ':'
GRID_ALPHA = 0.7

# Líneas
LINE_WIDTH_NORMAL = 2
LINE_WIDTH_THIN = 1.5
LINE_WIDTH_THICK = 2.5

# Markers
MARKER_SIZE_SMALL = 5
MARKER_SIZE_NORMAL = 6
MARKER_SIZE_LARGE = 8

# Alpha (transparencia)
ALPHA_NORMAL = 0.8
ALPHA_LIGHT = 0.6
ALPHA_FILL = 0.15

# ==================== LÍMITES Y UMBRALES ====================

# Base de datos
DB_SIZE_LIMIT_MB = 1024  # 1 GB
DB_SIZE_WARNING_MB = 512  # 512 MB

# Análisis acústico
EPSILON_SMALL = 1e-9
EPSILON_TINY = 1e-10

# Ventanas para análisis
ANALYSIS_WINDOW_SMALL = 10
ANALYSIS_WINDOW_MEDIUM = 15
ANALYSIS_WINDOW_LARGE = 20
ANALYSIS_WINDOW_XLARGE = 30

# Q-factor
Q_FACTOR_THRESHOLD = 0.707  # -3dB = 1/sqrt(2)

# Cut-off frequency
CUTOFF_THRESHOLD_DEFAULT = 0.1  # 10% del máximo

# ==================== CALIDAD DE RENDERIZADO ====================

# 3D
QUALITY_3D_MIN = 10
QUALITY_3D_DEFAULT = 100
QUALITY_3D_MAX = 500

# PDF
PDF_DPI = 300

# ==================== TIMEOUTS Y DELAYS ====================

# Delays para operaciones GUI (ms)
DELAY_SHORT = 100
DELAY_MEDIUM = 250
DELAY_LONG = 500

# Progress dialog update frequency (ms)
PROGRESS_UPDATE_FREQ = 100

# ==================== MENSAJES DE USUARIO ====================

# Emojis para logging (opcional)
EMOJI_SUCCESS = "✅"
EMOJI_ERROR = "❌"
EMOJI_WARNING = "⚠️"
EMOJI_INFO = "ℹ️"
EMOJI_CHECKMARK = "✓"
EMOJI_CROSS = "✗"
EMOJI_ARROW = "→"

# Mensajes estándar
MSG_NO_DATA = "No hay datos disponibles"
MSG_LOADING = "Cargando..."
MSG_PROCESSING = "Procesando..."
MSG_CALCULATING = "Calculando..."
MSG_SAVING = "Guardando..."

# ==================== CONFIGURACIÓN DE TIGHT_LAYOUT ====================

TIGHT_LAYOUT_PAD = 1.5
TIGHT_LAYOUT_H_PAD = 1.0
TIGHT_LAYOUT_W_PAD = 1.0

