# Instrucciones para Capturar Screenshots de la Aplicación

## Preparación

1. Activar el entorno OpenWind:
   ```bash
   conda activate OpenWind
   ```

2. Lanzar la aplicación:
   ```bash
   cd "/Users/pdelac/Library/CloudStorage/GoogleDrive-patodelac@gmail.com/My Drive/Main/3.-INVESTIGACION/4.-DEVELOPMENT/2025-Traverso-analysis/traverso-analysis-v2"
   python unified_flute_gui_qt.py
   ```

## Screenshots Necesarios

### Screenshots de Análisis Acústico (Flauta: Deppe)

1. **Resonance Frequencies** (`real_resonance_frequencies.png`)
   - Cargar flauta: Deppe
   - Ir a tab "Análisis Acústico"
   - Sub-tab "Frecuencias" o similar
   - Capturar el gráfico de frecuencias de resonancia vs notas musicales

2. **Inharmonicity** (`real_inharmonicity.png`)
   - Tab "Análisis Acústico" > Sub-tab "Inharmonicidad"
   - Capturar el gráfico

3. **MOC** (`real_moc.png`)
   - Tab "Análisis Acústico" > Sub-tab "MOC"
   - Capturar el gráfico

4. **B_I y ESPE** (`real_bi_espe.png`)
   - Tab "Análisis Acústico" > Sub-tab "B_I & ESPE"
   - Capturar ambos gráficos (si están juntos) o capturar por separado

5. **Q-Factor** (`real_qfactor.png`)
   - Tab "Análisis Acústico" > Sub-tab "Q-Factor"
   - Capturar el gráfico

6. **Harmonic Ratios** (`real_harmonic_ratios.png`)
   - Tab "Análisis Acústico" > Sub-tab relacionado con ratios armónicos
   - Capturar gráfico mostrando f1/f0, f2/f0

7. **Peak Heights** (`real_peak_heights.png`)
   - Tab "Análisis Acústico" > Sub-tab de alturas de picos
   - Capturar gráfico de barras

8. **Admittance** (`real_admittance.png`)
   - Tab "Admitancia" o similar
   - Capturar espectro de admitancia para una nota

### Screenshot de Comparación Multi-Flauta

9. **Multi-Flute Comparison** (`real_multi_flute_comparison.png`)
   - Cargar flautas: Deppe y Freyer
   - Tab "Análisis Acústico" > Ver gráfico con múltiples flautas superp uestas
   - O tab "Resumen" / "Comparación"
   - Capturar gráfico mostrando ambas flautas

## Cómo Capturar

### Opción A: Usando screencapture de macOS

```bash
# Para capturar solo una ventana interactivamente:
screencapture -w -o presentation_screenshots/nombre_archivo.png

# Luego hacer clic en la ventana/gráfico que quieres capturar
```

### Opción B: Manualmente

1. Abrir la vista deseada en la aplicación
2. Presionar `Cmd + Shift + 4`, luego `Espacio`
3. Click en la ventana para capturar
4. Mover el archivo a `presentation_screenshots/` con el nombre correcto

## Lista de Archivos a Generar

- `real_resonance_frequencies.png`
- `real_inharmonicity.png`
- `real_moc.png`
- `real_bi_espe.png`
- `real_qfactor.png`
- `real_harmonic_ratios.png`
- `real_peak_heights.png`
- `real_admittance.png`
- `real_multi_flute_comparison.png`

## Actualizar LaTeX

Una vez capturados todos los screenshots, ejecutar:

```bash
python update_latex_with_real_screenshots.py
```

Este script reemplazará las referencias a los screenshots sintéticos por los reales.
