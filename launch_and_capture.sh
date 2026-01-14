#!/bin/bash
# Script para lanzar la GUI y capturar screenshots automáticamente

# Activar entorno OpenWind
eval "$(conda shell.bash hook)"
conda activate OpenWind

cd "/Users/pdelac/Library/CloudStorage/GoogleDrive-patodelac@gmail.com/My Drive/Main/3.-INVESTIGACION/4.-DEVELOPMENT/2025-Traverso-analysis/traverso-analysis-v2"

# Lanzar la GUI y el script de captura en segundo plano
python unified_flute_gui_qt.py &
GUI_PID=$!

# Esperar a que la GUI se inicie
sleep 5

# Ejecutar script de captura usando el mismo proceso de Python
python -c "
import sys
sys.path.insert(0, '.')
from capture_gui_screenshots import take_screenshots
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

app = QApplication.instance()
if app:
    QTimer.singleShot(2000, take_screenshots)
" &

# Esperar a que termine la captura
wait

echo "Capturas completadas"
