## traverso_analysis v2

Herramientas para **análisis, comparación y optimización de traversos** a partir de su geometría (JSON / base de datos), con integración de análisis acústico, estadísticas de base de datos y análisis de sensibilidad de parámetros geométricos.

El sistema combina:
- **Modelado geométrico detallado** (perfiles internos/externos, agujeros cilíndricos y cónicos, embocadura, uniones).
- **Cálculo acústico** (admitancias, inharmonicidad, MOC, B_I/ESPE, Q, etc.).
- **Exploración gráfica interactiva**.
- **Reportes automáticos en PDF** (estadísticos y de sensibilidad).

---

## Estructura general

- **`unified_flute_gui_qt.py`**: GUI principal unificada (entrada recomendada).
- **`flute_data.py` / `flute_data_db.py`**: núcleo de datos y acceso a la base de datos.
- **`analysis_module.py`**: cálculo y gráficos de métricas acústicas.
- **`flute_operations.py`**: generación de gráficos geométricos (perfiles, cortes, vistas 2D/3D).
- **`database_statistics.py`**: extracción de métricas de toda la base de datos y generación de reportes estadísticos.
- **`sensitivity_analysis.py` + `sensitivity_analysis_dialog.py`**: generación de variantes geométricas y análisis de sensibilidad con reporte en PDF.
- **`flute_geometry_editor_qt.py`**: editor interactivo de geometría con vista integrada en la GUI principal.
- Scripts auxiliares: `cleanup_database.py`, `migrate_json_to_db.py`, `optimize_flute_from_json.py`, etc.

Para detalles específicos de los reportes:
- Ver `REPORTE_ESTADISTICO_README.md` para el **reporte estadístico de base de datos**.
- Ver `SENSITIVITY_ANALYSIS_README.md` para el **análisis de sensibilidad**.

---

## Datos de entrada

El sistema puede trabajar con:

- **Archivos JSON** de geometría de flauta (formato “clásico”).
- **Base de datos SQLite** `flute_analysis.db` (no se versiona en Git).

### Geometría de agujeros (soporte para conos)

En los JSON/BD se admite:

- **Agujero cilíndrico**:

```json
"Holes diameter": [12.0, 10.5, 9.0]
```

- **Agujero cónico**:

```json
"Holes diameter": [12.0, [14.0, 18.0], 9.0]
```

- `12.0`  → cilindro, diámetro 12 mm.
- `[14.0, 18.0]` → cono con diámetro externo 14 mm, diámetro interno 18 mm (undercut).
- `9.0`   → cilindro, diámetro 9 mm.

El sistema calcula automáticamente el **espesor del muro** en la posición del agujero y genera el cono correspondiente (incluyendo compatibilidad con OpenWind).

---

## Aplicaciones principales

### `unified_flute_gui_qt.py` (entrada principal)

Interfaz unificada con pestañas para:

- **Gestión de flautas**:
  - Carga de flautas desde la base de datos.
  - Filtros por tipo/modelo, tamaño, afinación, etc.
  - Comparación simultánea de varias flautas.

- **Geometría**:
  - Perfil físico externo estimado (con solapamiento de uniones).
  - Perfil acústico interno concatenado (referido al corcho).
  - Perfiles de cada parte (cabeza, cuerpo, pie, etc.).
  - Agujeros cilíndricos y cónicos (incluida embocadura) en:
    - Corte axial 2D (perfiles + polígonos de agujeros).
    - Vista superior (círculos concéntricos para conos).
    - Vistas 2D adicionales y ensamblaje físico.

- **Análisis acústico**:
  - Admitancia (presión/flujo) por nota.
  - Inharmonicidad.
  - MOC (Modal Octave Compression).
  - B_I / ESPE.
  - Altura de picos y Q-factors.
  - Ratios armónicos, fase, estabilidad de pitch.
  - Frecuencias de resonancia, cut-off, etc.

- **Resumen**:
  - Tablas y gráficos resumen de métricas acústicas.

- **Reportes**:
  - Acceso al **reporte estadístico completo**.
  - Acceso al **reporte de análisis de sensibilidad**.

---

### `database_statistics.py` + menú de reportes

Permite generar un **Reporte Estadístico Completo** sobre todas (o un subconjunto) de las flautas en la base de datos:

- Selección de subconjunto de flautas (filtros).
- Elección de métricas geométricas y acústicas:
  - Longitudes de partes y total.
  - Número y posición de agujeros.
  - Diámetros de embocadura y agujeros.
  - Pendientes de secciones, longitudes acústicas efectivas, etc.
- Generación de un PDF con:
  - Box-plots, histogramas, dispersiones.
  - Tablas resumen (media, σ, min, max, mediana, N).
  - Detección automática de valores anómalos (±2σ) y página de resumen.

Configuración y uso detallados en `REPORTE_ESTADISTICO_README.md`.

---

### `sensitivity_analysis.py` + `sensitivity_analysis_dialog.py`

Módulo de **Análisis de Sensibilidad** sobre una flauta base:

- Parámetros que se pueden “sensibilizar” (variar sistemáticamente):
  - Ángulo de undercut de agujeros (con conversión automática de cilindros a conos).
  - Conicidad de partes (taper).
  - Posición del corcho.
  - Diámetros de agujeros y embocadura.
  - Posición de agujeros.
- Para cada valor del parámetro:
  - Se genera una **variante geométrica** (sin guardar en la base de datos, solo en memoria).
  - Se calcula el análisis acústico correspondiente.

El sistema incluye un `SensitivityReportGenerator` que produce un **PDF de análisis de sensibilidad** con:

- Evolución de métricas acústicas vs. parámetro:
  - Inharmonicidad, MOC, B_I/ESPE.
  - Frecuencias de resonancia, alturas de pico, Q.
  - Otras métricas derivadas del `FluteAnalyzer`.
- Tablas comparativas de todas las variantes.
- Estadísticos resumen por métrica (media, σ, min, max, mediana, N).
- **Gráficos acústicos individuales** para notas seleccionadas (las mismas vistas que en la GUI).
- **Gráficos geométricos** por variante:
  - Perfil acústico, corte axial, vista sólida 2D/ensamblaje.
  - Vistas superiores de agujeros (incluyendo posición y tamaño de cada agujero, con conos dibujados como círculos concéntricos).
  - Títulos y layouts ajustados para evitar solapamientos en PDF.

Los flautas variantes **no se guardan en la base de datos** (se trabaja con `FluteDataDB` sin `db_manager` para evitar ruido en la BD).

---

### `flute_geometry_editor_qt.py`

Editor gráfico de geometría, integrado con la GUI principal:

- Visualización interactiva de:
  - Perfiles internos y externos.
  - Agujeros (cilíndricos y cónicos), incluyendo embocadura.
- Edición mediante tabla:
  - Columna de “Diámetro” y “Diámetro interno” para permitir formato mixto:
    - Solo diámetro externo → agujero cilíndrico.
    - Diámetro externo + diámetro interno → agujero cónico `[diam_out, diam_in]`.
- Gráficos del editor:
  - Agujeros cónicos representados como elipses concéntricas en corte 2D.
- Botón para **cargar la geometría modificada en la GUI principal** y recalcular el análisis acústico.

---

### Scripts históricos / utilidades

Se mantienen algunos scripts de la versión anterior por compatibilidad:

- **`gui.py`**:
  - Carga una o varias flautas desde directorios de datos (JSON) para análisis comparativo rápido.
  - Maneja errores de JSON (ofrece editar al vuelo).
  - Gráficos de:
    - Perfil físico estimado (solapamiento de uniones).
    - Perfil acústico interno concatenado.
    - Geometría de las 4 partes en subplots.
    - Admitancias por nota y métricas acústicas globales (inharmonicidad, MOC, B_I/ESPE).

- **`flute_experimenter.py`**:
  - Carga una flauta individual.
  - Muestra geometría + inharmonicidad + MOC + B_I/ESPE.
  - Editor gráfico interactivo (arrastrar puntos del perfil y agujeros).
  - Comparación visual y acústica entre flauta original y modificada.
  - Guardado de una nueva geometría modificada.

- **`flute_optimizer_gui.py`**:
  - Carga una flauta y optimiza la **altura de la chimenea de embocadura** por nota.
  - Objetivo: afinación para un diapasón y temperatura definidos (ej. A=415 Hz).
  - Resultados:
    - Alturas de chimenea optimizadas.
    - Comparación de admitancias (antes / después).
    - Comparación de inharmonicidad.
    - Geometría y envolventes de flujo/presión para la flauta optimizada.

---

## Instalación y entorno

1. Crear entorno (ejemplo con `conda`):

```bash
conda create -n OpenWind python=3.11
conda activate OpenWind
```

2. Instalar dependencias:

- El proyecto asume instalación de:
  - `numpy`, `scipy`, `matplotlib`.
  - `pyqt5` (para las GUIs).
  - Cualquier otra dependencia específica documentada en los scripts o en archivos de requisitos (si se añaden).

(Se recomienda crear un `requirements.txt` o `environment.yml` si aún no existe).

3. Ejecutar la GUI principal:

```bash
python unified_flute_gui_qt.py
```

---

## Notas sobre versiones y backups

- Este repositorio corresponde a la **versión v2**, con:
  - Soporte completo para **agujeros cónicos** (incluida embocadura).
  - Integración del **análisis de sensibilidad** con reporte en PDF.
  - Módulo de **estadísticas de base de datos** y reporte estadístico completo.
- Se han mantenido directorios de backup:
  - `backup_before_refactor_20251119_222408/`
  - `backup_before_cleanup_20251126/`
  para poder rastrear fácilmente la evolución del código.

La base de datos local (`flute_analysis.db` y copias) **no se versiona en GitHub** y se debe gestionar de forma local.

---

## Próximos pasos / ideas

- Completar y mantener documentación de usuario (PDF LaTeX en `Report/`).
- Añadir ejemplos de JSON y flautas de referencia.
- Incluir tests de regresión para métricas acústicas y formatos de agujeros.
- Documentar flujos de trabajo típicos:
  - Cargar flauta → editar geometría → analizar → comparar → optimizar.
  - Trabajar a nivel de base de datos (estadísticas).
  - Realizar estudios de sensibilidad de parámetros clave.
