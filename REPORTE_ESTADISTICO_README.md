# Reporte Estadístico de Base de Datos

## Descripción

Nueva funcionalidad que permite generar reportes estadísticos completos analizando todas las flautas almacenadas en la base de datos. El sistema extrae métricas geométricas clave y genera un PDF profesional con visualizaciones comparativas y estadísticas descriptivas.

## Cómo Usar

### Desde la GUI

1. **Abrir la aplicación**:
   ```bash
   python3 unified_flute_gui_qt.py
   ```

2. **Acceder al generador de reportes**:
   - Menú: `Base de Datos` → `Reportes` → `Reporte Estadístico Completo...`

3. **Configurar el reporte**:
   - **Filtro de Flautas**: Selecciona qué flautas incluir en el análisis
     - Por defecto, todas las flautas están seleccionadas
     - Usa el checkbox "Seleccionar todas" para marcar/desmarcar todas
   
   - **Métricas a Incluir**: Selecciona qué análisis realizar
     - ✓ Pendientes por Parte (conicidad de cada sección)
     - ✓ Tamaños de Agujeros (diámetros de todos los agujeros)
     - ✓ Largos Físicos por Parte (longitud de cada componente)
     - ✓ Diámetro de Embocadura (medición interna del cilindro)
     - ✓ Largo Acústico Total (longitud efectiva del resonador)
     - ☐ Análisis de Correlaciones (relaciones entre métricas)
   
   - **Opciones de Formato**:
     - Incluir tablas estadísticas (promedio, std, min, max, mediana)
     - Incluir resumen ejecutivo (tabla general de estadísticas)

4. **Generar el reporte**:
   - Click en "Generar Reporte"
   - Selecciona ubicación y nombre del archivo PDF
   - Espera mientras se procesan los datos (puede tardar unos segundos)
   - El PDF se generará automáticamente

5. **Ver el reporte**:
   - Opción de abrir el PDF automáticamente al finalizar
   - O navegar manualmente al archivo generado

## Métricas Incluidas

### 1. Pendientes por Parte
- **Descripción**: Analiza la conicidad de cada parte de la flauta (headjoint, left, right, foot)
- **Cálculo**: Regresión lineal sobre las mediciones de diámetro vs posición
- **Unidades**: mm/mm (cambio de diámetro por mm de longitud)
- **Visualizaciones**:
  - Box plot comparativo de todas las flautas
  - Histogramas de distribución por parte
  - Tabla de estadísticas (promedio, desviación, min, max, mediana)

### 2. Tamaños de Agujeros
- **Descripción**: Analiza los diámetros de todos los agujeros (incluida la embocadura)
- **Unidades**: mm
- **Visualizaciones**:
  - Box plot por posición de agujero
  - Histograma general de distribución
  - Tabla de estadísticas por agujero

### 3. Largos Físicos por Parte
- **Descripción**: Longitud física de cada componente de la flauta
- **Unidades**: mm
- **Visualizaciones**:
  - Box plot comparativo por parte
  - Histogramas superpuestos por parte
  - Tabla de estadísticas

### 4. Diámetro de Embocadura
- **Descripción**: Diámetro interno del cilindro de la embocadura
- **Nota**: Si la embocadura está deformada, se calcula el promedio
- **Unidades**: mm
- **Visualizaciones**:
  - Histograma de distribución
  - Box plot
  - Tabla de estadísticas (promedio, std, min, max, mediana, N)

### 5. Largo Acústico Total
- **Descripción**: Longitud efectiva del resonador (desde el corcho hasta el final)
- **Cálculo**: Diferencia entre la posición máxima y la posición del stopper
- **Unidades**: mm
- **Visualizaciones**:
  - Histograma de distribución
  - Box plot
  - Tabla de estadísticas

### 6. Análisis de Correlaciones (Opcional)
- **Descripción**: Relaciones entre diferentes métricas geométricas
- **Visualizaciones**:
  - Scatter plot: Largo Acústico vs Diámetro de Embocadura
  - Líneas de tendencia (regresión lineal)

## Estructura del PDF

El reporte PDF generado tiene la siguiente estructura:

1. **Portada**
   - Título del reporte
   - Fecha de generación
   - Número de flautas analizadas
   - Lista de métricas incluidas

2. **Resumen Ejecutivo** (opcional)
   - Tabla con estadísticas generales
   - Vista rápida de todas las métricas principales

3. **Tabla Detallada de Métricas** (NUEVO)
   - Listado completo de todas las flautas con todas sus métricas
   - **Identificación automática de valores anómalos**:
     - 🟡 Celdas amarillas: Valores fuera del rango esperado (±2 desviaciones estándar)
     - 🔴 Celdas rosadas: Datos faltantes
   - Múltiples páginas si hay muchas flautas (25 flautas por página)
   - **Resumen de Anomalías**:
     - Página dedicada que lista todos los valores anómalos detectados
     - Muestra qué flauta, qué métrica, el valor, la media y cuántas desviaciones estándar se aleja
     - Facilita la identificación rápida de flautas con mediciones sospechosas

4. **Secciones por Métrica**
   - Cada métrica seleccionada tiene su propia sección
   - Gráficos comparativos (box plots, histogramas)
   - Tablas de estadísticas descriptivas
   - Interpretación visual de los datos

4. **Análisis de Correlaciones** (opcional)
   - Scatter plots mostrando relaciones entre variables
   - Líneas de tendencia y ecuaciones

## Ejemplos de Uso

### Caso 1: Análisis Completo de Todas las Flautas
- Seleccionar todas las flautas
- Marcar todas las métricas
- Incluir correlaciones
- Generar reporte completo
- **Resultado**: PDF con todas las visualizaciones, tabla detallada y análisis de anomalías

### Caso 2: Auditoría de Calidad de Datos
- Seleccionar todas las flautas
- Marcar todas las métricas
- Generar reporte
- **Revisar**:
  - Tabla detallada para ver valores anómalos (celdas amarillas)
  - Resumen de anomalías para identificar flautas problemáticas
  - Corregir errores en los JSON originales
- **Uso**: Control de calidad después de agregar nuevas flautas a la BD

### Caso 3: Comparación de un Subconjunto
- Seleccionar solo flautas de un periodo específico
- Analizar solo pendientes y diámetros
- Comparar características de diseño
- **Uso**: Estudios históricos o comparación de fabricantes

### Caso 4: Reporte Rápido de Embocaduras
- Seleccionar todas las flautas
- Marcar solo "Diámetro de Embocadura"
- Generar análisis específico
- **Uso**: Estudio enfocado en una característica específica

### Caso 5: Identificación de Flautas Únicas
- Generar reporte completo
- Revisar página de "Resumen de Anomalías"
- Identificar flautas con características extraordinarias
- **Uso**: Detectar instrumentos especiales o con diseños experimentales

## Interpretación de Resultados

### Pendientes
- **Positiva**: El diámetro aumenta hacia el extremo distal (cónica expandente)
- **Negativa**: El diámetro disminuye hacia el extremo distal (cónica contractante)
- **Cercana a cero**: Cilíndrica

### Box Plots
- **Caja**: Rango intercuartílico (50% central de los datos)
- **Línea central**: Mediana
- **Bigotes**: Rango de datos (excluyendo outliers)
- **Puntos**: Outliers (valores atípicos)

### Estadísticas
- **Promedio**: Valor medio de todas las flautas
- **Desv. Std**: Dispersión de los datos (cuánto varían)
- **Mínimo/Máximo**: Valores extremos
- **Mediana**: Valor central (menos sensible a outliers)

### Valores Anómalos (Outliers)

El sistema detecta automáticamente valores que se alejan significativamente del resto:

#### Criterio de Detección
- **±2 Desviaciones Estándar**: Un valor es considerado anómalo si está más de 2σ por encima o por debajo de la media
- Esto corresponde aproximadamente al 5% de los valores más extremos en una distribución normal

#### Interpretación
- **1-2σ**: Valor inusual pero posible
- **2-3σ**: Valor muy inusual, merece revisión
- **>3σ**: Valor extremadamente inusual, probable error de medición

#### Causas Posibles de Anomalías
1. **Errores de medición**: Typo al ingresar datos, error del instrumento
2. **Diseños únicos**: Flautas con características especiales intencionalmente diferentes
3. **Daños/deformaciones**: Instrumentos que han sufrido cambios físicos
4. **Errores de transcripción**: Confusión entre unidades (mm vs cm)
5. **Datos incompletos**: Mediciones parciales o estimaciones

#### Qué Hacer con los Valores Anómalos
1. **Verificar los datos originales**: Revisar el JSON de la flauta
2. **Confirmar las mediciones**: Si es posible, re-medir el instrumento
3. **Documentar**: Si el valor es correcto, documentar por qué es diferente
4. **Corregir**: Si es un error, corregir en el JSON y repoblar la base de datos
5. **Analizar**: Investigar si hay patrones en las anomalías (ej: todas de un mismo fabricante)

## Archivos Involucrados

### Nuevos Archivos
- `database_statistics.py`: Módulo principal de extracción y generación
  - `DatabaseStatisticsExtractor`: Extrae métricas de la BD
  - `StatisticsReportGenerator`: Genera el PDF con visualizaciones

### Archivos Modificados
- `unified_flute_gui_qt.py`: 
  - Nueva clase `DatabaseStatisticsDialog`
  - Método `_open_statistics_report_dialog()`
  - Acción de menú agregada

- `flute_db_manager.py`:
  - Método `get_all_flutes_for_statistics()`
  - Método `get_flute_geometry_for_statistics()`

## Requisitos

El sistema utiliza las bibliotecas ya disponibles:
- `numpy`: Para cálculos estadísticos y regresión lineal
- `matplotlib`: Para generación de gráficos
- `sqlite3`: Para acceso a la base de datos
- `PyQt5`: Para la interfaz gráfica

No se requieren dependencias adicionales.

## Notas Técnicas

### Extracción de Datos
1. Se consulta la base de datos para obtener la lista de flautas
2. Para cada flauta:
   - Se obtiene la geometría de cada parte (JSON almacenado)
   - Se reconstruyen las mediciones combinadas
   - Se calculan métricas geométricas específicas
   - Se detectan y manejan datos faltantes

### Cálculo de Pendientes
- Se usa `np.polyfit()` con grado 1 (regresión lineal)
- Solo se consideran partes con ≥2 puntos de medición
- El ángulo del cono se calcula como: `arctan(pendiente/2)`

### Diámetro de Embocadura
- Se extrae del primer agujero del headjoint
- Si hay múltiples mediciones, se promedian
- Detecta embocaduras deformadas automáticamente

### Largo Acústico
- Se reconstruyen las `combined_measurements` desde las partes
- Se considera el ensamblaje con mortise/tenon
- Se normaliza respecto a la posición del stopper

### Rendimiento
- Procesamiento optimizado para bases de datos grandes
- Uso eficiente de memoria
- Generación progresiva del PDF (página por página)

## Solución de Problemas

### Error: "No se pudieron extraer métricas"
- Verificar que las flautas seleccionadas tienen datos completos
- Revisar los logs para errores específicos
- Intentar con un subconjunto más pequeño

### Error: "No hay datos de geometría"
- Asegurar que las flautas están correctamente guardadas en la BD
- Verificar que los JSON tienen campos `measurements`
- Repoblar la base de datos si es necesario

### PDF vacío o incompleto
- Verificar que al menos una métrica está seleccionada
- Comprobar que hay suficientes flautas para análisis estadístico
- Revisar permisos de escritura en el directorio de destino

### Proceso muy lento
- Reducir el número de flautas analizadas
- Desmarcar "Análisis de Correlaciones" si no es necesario
- Verificar que la base de datos no está corrupta

## Futuras Mejoras Potenciales

1. **Exportar datos a CSV**: Para análisis externos
2. **Comparación entre grupos**: Análisis por fabricante, periodo, etc.
3. **Más correlaciones**: Análisis multivariado completo
4. **Gráficos interactivos**: Visualizaciones con zoom y tooltips
5. **Templates personalizables**: Diferentes formatos de reporte
6. **Análisis temporal**: Evolución de diseños a través del tiempo

## Contacto y Soporte

Para preguntas o problemas:
- Revisar los logs en `flute_analysis.log`
- Consultar la documentación de OpenWind
- Verificar que la base de datos está actualizada

---

**Versión**: 1.0  
**Fecha**: 2024-11-20  
**Autor**: Sistema de Análisis de Flautas Traverso

