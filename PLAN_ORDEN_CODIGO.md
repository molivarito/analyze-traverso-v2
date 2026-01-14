## Plan de orden y revisión estática (v2)

**Objetivo general**  
Dejar el código del sistema de análisis de traversos **ordenado, legible y consistente**, sin modificar en absoluto la funcionalidad actual (misma lógica, mismos resultados numéricos, mismas rutas en la GUI).

En esta fase solo se permiten cambios de:
- Organización (reordenar funciones/métodos/clases dentro de un archivo).
- Nombres de variables internas y comentarios (sin tocar las interfaces públicas ni los nombres usados por otros módulos/Qt).
- Comentarios y docstrings.
- Limpieza de imports muertos y código claramente no utilizado.
- Pequeñas mejoras de estilo (espacios, saltos de línea, factorizar bloques repetidos **cuando es obvio** que no cambia el comportamiento).

No se permiten:
- Cambios en firmas de funciones/métodos **que se usen desde otros módulos o desde Qt**.
- Cambios en valores por defecto, rutas de archivos, nombres de señales/slots, claves de JSON, nombres de columnas en BD, etc.
- Modificaciones de algoritmos, fórmulas, orden de operaciones de cálculo o parámetros de análisis.

---

## 1. Núcleo de datos: `flute_data.py` y `flute_data_db.py`

**Objetivo**: Que sea claro cómo se representa la geometría, cómo se valida y cómo se conecta con la base de datos (incluyendo agujeros cónicos).

- **`flute_data.py`**
  - Añadir/normalizar docstrings en:
    - Clase principal de datos de flauta.
    - Métodos de carga desde JSON / BD.
    - Métodos relacionados con geometría de agujeros (cilíndricos y cónicos) y cálculo de espesor de muro.
  - Reordenar el archivo:
    - Constantes y tipos.
    - Clase de datos / helpers.
    - Funciones auxiliares (ej. interpolación de perfiles, utilidades de geometría).
  - Asegurar que los comentarios sobre formato mixto de agujeros (`número` vs `[diam_out, diam_in]`) estén concentrados en uno o dos lugares clave.
  - Limpiar imports no usados (sin tocar imports que puedan ser usados indirectamente).

- **`flute_data_db.py`**
  - Aclarar con comentarios:
    - Cuándo se usa `db_manager` y cuándo debe ser `None` (ej. variantes de sensibilidad que no se guardan).
    - Flujo de guardado: geometría, análisis acústico, metadatos.
  - Reorganizar métodos para que el flujo sea fácil de seguir:
    - Inicialización y helpers.
    - Guardado/carga de geometría.
    - Guardado/carga de análisis acústico.
  - Añadir docstrings breves donde falten (especialmente en métodos que interactúan con la BD).

---

## 2. Gráficos geométricos: `flute_operations.py`

**Objetivo**: Que las funciones de dibujo sean fáciles de leer y que el manejo de agujeros cónicos/cilíndricos esté claramente documentado.

- Agrupar y documentar las funciones principales:
  - Perfiles 2D (perfil acústico, perfil físico).
  - Cortes axiales 2D (`plot_axial_cut_2d`, `plot_individual_part_axial_cut_2d`).
  - Vista superior de agujeros y ensamblaje físico.
- En cada función clave:
  - Añadir docstring con:
    - Qué representa el gráfico.
    - Qué partes de la flauta se muestran.
    - Cómo se representan los agujeros cónicos (polígonos trapezoidales / círculos concéntricos).
  - Consolidar comentarios sobre `zorder` (por qué se eligen ciertos valores para que perfiles y agujeros no se tapen).
- Extraer, cuando tenga sentido **sin cambiar comportamiento**, pequeñas funciones “privadas” auxiliares de dibujo (ej. para convertir especificación de agujero en radios interno/externo), solo si la lógica ya está duplicada.

---

## 3. Análisis acústico: `analysis_module.py`

**Objetivo**: Que el rol de `FluteAnalyzer` y cada gráfico/métrica quede claramente identificado.

- Añadir docstring general a la clase `FluteAnalyzer`:
  - Qué tipo de objeto recibe (flauta + resultados de simulación).
  - Qué métricas produce.
  - Cómo se integra con la GUI y con los reportes PDF.
- Para cada método `plot_*`:
  - Añadir docstring conciso (qué métrica, qué ejes, qué unidades).
  - Garantizar que todos devuelven `plt.Figure` (ya está implementado, solo documentarlo).
- Revisar imports y constantes:
  - Limpiar lo que ya no se use.
  - Añadir comentarios donde haya parámetros “mágicos” (ej. rangos de frecuencia, escalas, etc.).

---

## 4. Análisis de sensibilidad: `sensitivity_analysis.py` y `sensitivity_analysis_dialog.py`

**Objetivo**: Que el flujo “configurar variación → generar variantes → calcular → generar reporte” sea claro y trazable.

- **`sensitivity_analysis.py`**
  - Documentar:
    - Enums / dataclasses de configuración de variación.
    - `FluteVariantGenerator` y `SensitivityAnalyzer` (qué hace cada uno).
    - `SensitivityReportGenerator`:
      - Estructura general del PDF (portada, resumen, gráficos de evolución, tablas, gráficos geométricos y acústicos).
      - Qué métricas se incluyen y cómo se leen de las variantes.
  - Comentarios claros en:
    - `_apply_hole_undercut()` y `_convert_hole_to_cone()` (asunciones geométricas, fórmula del undercut).
    - Lógica para NO guardar variantes en la BD (uso de `db_manager=None`).

- **`sensitivity_analysis_dialog.py`**
  - Añadir docstrings breves en la clase principal y en los métodos que:
    - Recogen parámetros de la UI.
    - Lanzan el análisis en `QThread`.
    - Manejan la señal de finalización y el estado del diálogo (barra de progreso, botones, exportación a PDF).
  - Aclarar con comentarios dónde se emite la señal `variants_ready` y quién la usa en la GUI principal.

---

## 5. GUI principal: `unified_flute_gui_qt.py`

**Objetivo**: Que la estructura de la GUI (pestañas, menús, acciones) sea navegable y que las rutas de interacción estén documentadas.

- Al inicio del archivo:
  - Breve comentario/resumen de las principales secciones de la GUI.
- Reorganizar la clase principal (sin cambiar nombres de métodos conectados a señales):
  - Inicialización y construcción de la GUI.
  - Gestión de base de datos y carga de flautas.
  - Pestañas de geometría.
  - Pestañas de análisis acústico.
  - Menú de reportes estadísticos.
  - Menú de análisis de sensibilidad.
- Añadir comentarios en:
  - `_open_sensitivity_analysis_dialog()` y manejadores relacionados (cómo se conectan con el análisis de sensibilidad y carga de variantes).
  - `_open_geometry_editor()` y `_on_editor_flute_loaded_for_analysis()` (flujo editor → GUI principal).
- Limpiar métodos claramente obsoletos/comentados, **solo si se tiene 100% certeza** de que no se usan (si hay duda, dejar y solo marcar con comentario).

---

## 6. Editor de geometría: `flute_geometry_editor_qt.py`

**Objetivo**: Que quede claro cómo se sincroniza la tabla de agujeros con la representación interna (incluyendo conos) y cómo se integra con la GUI principal.

- Documentar:
  - Formato interno de agujeros (cilíndricos vs cónicos) y cómo se mapean a las columnas de la tabla (“Diámetro” / “Diámetro interno”).
  - Flujo de:
    - `_update_holes_table()` (llenar tabla desde datos).
    - `_on_holes_table_changed()` (reflejar los cambios en el modelo).
    - `_update_edit_plot()` (cómo se dibujan los agujeros cónicos como elipses concéntricas).
  - Método `_load_in_main_gui()` y la señal `flute_loaded_for_analysis` (contrato con la GUI principal).
- Reorganizar secciones del archivo:
  - Inicialización / UI.
  - Sincronización tabla ↔ datos.
  - Gráficos del editor.
  - Integración con GUI principal.

---

## 7. Reglas de validación final

Al terminar cada bloque de cambios:

- Ejecutar la GUI principal (`unified_flute_gui_qt.py`) y comprobar:
  - Que abre sin errores.
  - Que las pestañas y menús relevantes siguen funcionando.
  - Que los flujos clave (carga de flauta, análisis acústico, editor, análisis de sensibilidad, reportes) siguen produciendo los mismos resultados que antes.
- Hacer commits pequeños y descriptivos, por ejemplo:
  - `refactor: documentar manejo de agujeros cónicos en flute_data`
  - `chore: ordenar funciones de dibujo en flute_operations`
  - `docs: aclarar flujo de análisis de sensibilidad`

Este plan sirve como “contrato” de que la refactorización es **puramente estática/estructural** y no debe alterar la funcionalidad del sistema.


