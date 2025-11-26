# traverso_analysis
Analisis y comparación de traversos a partir de su geometría en archivos json

Las applicaciones actualmente:

### `gui.py`
- Carga una o varias flautas desde directorios de datos para un análisis comparativo.
- Maneja errores en los archivos JSON durante la carga, ofreciendo la opción de editarlos en el momento.
- **Gráficos de geometría:**
    - Perfil físico estimado (mostrando solapamientos de uniones).
    - Perfil acústico interno (concatenado, relativo al corcho).
    - Geometría de las 4 partes individuales en subplots.
- **Gráficos de análisis acústico comparativo:**
    - Admitancia por nota (con envolvente de presión y flujo).
    - Resumen de inharmonicidad (Pico 2 vs 2 * Pico 1).
    - Resumen de MOC (Modal Octave Compression).
    - Resumen de B_I / ESPE.

### `flute_experimenter.py`
- Carga una flauta y muestra un análisis simple: geometría, inharmonicidad, MOC y BI_ESPE.
- Permite **editar la geometría de forma gráfica e interactiva** (arrastrando puntos del perfil y agujeros).
- Muestra una comparación visual y acústica entre la flauta original y la modificada en tiempo real.
- Permite guardar la nueva geometría modificada en un nuevo directorio.
- Útil para estudiar el impacto de cambios geométricos específicos.

### `flute_optimizer_gui.py`
- Carga una flauta y optimiza la **altura de la chimenea de la embocadura** para cada nota.
- El objetivo de la optimización es alcanzar una afinación definida por el diapasón del La (ej. 415Hz) y la temperatura.
- **Muestra los resultados de la optimización:**
    - Alturas de chimenea optimizadas para cada nota.
    - Comparación de admitancias (inicial vs. optimizada).
    - Comparación de inharmonicidad (antes vs. después).
    - Geometría y envolventes de flujo/presión para la flauta optimizada.