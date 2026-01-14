# Análisis de Resonador Truncado

## Descripción

El análisis de resonador truncado permite estudiar la respuesta acústica del resonador de la flauta **sin considerar los agujeros**, truncando progresivamente la geometría desde el final para analizar cómo la longitud y conicidad afectan las frecuencias de resonancia.

## Fundamentación Acústica

Este análisis es válido y útil porque:

- **Aísla el efecto puro de la geometría del bore**: Sin la interferencia de los agujeros, podemos estudiar directamente cómo la conicidad y longitud del resonador afectan la respuesta acústica.
- **Muestra la relación longitud-frecuencia**: Al truncar progresivamente, observamos cómo cambian las frecuencias de resonancia con la longitud efectiva.
- **Comparable con estudios académicos**: Similar a estudios de "cutoff length" en acústica de instrumentos de viento.

## Uso Básico

### Ejemplo Simple

```python
from flute_data import FluteData
from resonator_truncation_analysis import ResonatorTruncationAnalyzer

# Cargar datos de la flauta
flute_data = FluteData(
    source="ruta/a/datos/flauta",
    skip_acoustic_analysis=True  # No necesitamos el análisis completo
)

# Crear analizador
analyzer = ResonatorTruncationAnalyzer(
    flute_data=flute_data,
    truncation_percentages=None,  # Usa valores por defecto: 100%, 95%, ..., 20%
    temperature=20.0,
    include_embouchure=True
)

# Ejecutar análisis
results = analyzer.analyze()

# Generar visualizaciones
fig1 = analyzer.plot_resonance_frequencies_vs_length()
fig1.savefig("frecuencias_vs_longitud.png")

fig2 = analyzer.plot_inharmonicity_vs_length()
fig2.savefig("inharmonicidad_vs_longitud.png")

# Generar reporte PDF completo
analyzer.generate_summary_report("reporte_resonador_truncado.pdf")
```

### Uso con FluteAnalyzer

```python
from analysis_module import FluteAnalyzer
from flute_data import FluteData

# Cargar flautas
flute_data_list = [FluteData("ruta/flauta1"), FluteData("ruta/flauta2")]

# Crear analizador unificado
analyzer = FluteAnalyzer(flute_data_list)

# Crear analizador de resonador truncado para la primera flauta
truncation_analyzer = analyzer.create_resonator_truncation_analyzer(
    flute_index=0,
    truncation_percentages=[100, 90, 80, 70, 60, 50],  # Porcentajes personalizados
    temperature=20.0
)

# Ejecutar análisis
results = truncation_analyzer.analyze()
```

## Parámetros Configurables

### ResonatorTruncationAnalyzer

- **`flute_data`**: Instancia de `FluteData` o `FluteDataDB` (requerido)
- **`truncation_percentages`**: Lista de porcentajes de longitud a analizar
  - Por defecto: `[100, 95, 90, 85, 80, 75, 70, 65, 60, 55, 50, 45, 40, 35, 30, 25, 20]`
  - Ejemplo personalizado: `[100, 90, 80, 70, 60, 50]`
- **`freq_range`**: Rango de frecuencias para análisis
  - Por defecto: `np.arange(100, 3000, 2.0)` (100-3000 Hz, paso 2 Hz)
- **`temperature`**: Temperatura en Celsius (por defecto: 20.0)
- **`min_length_mm`**: Longitud mínima en mm para considerar una sección válida (por defecto: 50.0)
- **`include_embouchure`**: Si `True`, incluye la embocadura en el análisis (por defecto: `True`)

## Métricas Calculadas

Para cada sección truncada, el análisis calcula:

1. **Frecuencias de antiresonancia**: f0, f1, f2, ... (primeros modos)
2. **Inharmonicidad**: Desviación del segundo armónico respecto a 2×f0 (en cents)
3. **Relaciones armónicas**: f1/f0, f2/f0, f2/f1
4. **Longitud efectiva**: Calculada desde f0 usando L_eff = c / (2 × f0)
5. **Q-factor**: Para cada modo de resonancia
6. **Curvas completas**: Impedancia y admitancia en todo el rango de frecuencias

## Visualizaciones Disponibles

### 1. Frecuencias de Resonancia vs. Longitud
```python
fig = analyzer.plot_resonance_frequencies_vs_length(max_modes=5)
```
Muestra cómo cambian las frecuencias de los primeros modos al truncar la flauta.

### 2. Inharmonicidad vs. Longitud
```python
fig = analyzer.plot_inharmonicity_vs_length()
```
Muestra cómo la inharmonicidad varía con la longitud truncada.

### 3. Relaciones Armónicas vs. Longitud
```python
fig = analyzer.plot_harmonic_ratios_vs_length()
```
Muestra las relaciones f1/f0, f2/f0, f2/f1 y cómo se desvían de los valores armónicos ideales.

### 4. Curvas de Impedancia Superpuestas
```python
fig = analyzer.plot_impedance_curves_overlay(
    selected_percentages=[100, 80, 60, 40]  # Opcional
)
```
Superpone las curvas de admitancia para diferentes longitudes truncadas.

### 5. Mapa 3D: Frecuencia vs. Longitud vs. Amplitud
```python
fig = analyzer.plot_3d_frequency_length_amplitude()
```
Visualización 3D mostrando cómo la amplitud de admitancia varía con frecuencia y longitud.

## Estructura de Resultados

Los resultados se almacenan en `analyzer.results` como un diccionario:

```python
{
    100.0: {
        'percentage': 100.0,
        'length_mm': 600.0,
        'f0': 250.5,
        'f1': 501.2,
        'f2': 752.8,
        'antiresonance_frequencies': [250.5, 501.2, 752.8, ...],
        'inharmonicity_cents': 1.2,
        'harmonic_ratio_f1_f0': 2.0,
        'effective_length_mm': 680.5,
        'q_factors': [150.2, 120.5, ...],
        'frequencies': np.array([...]),
        'impedance': np.array([...]),
        'admittance': np.array([...]),
        'impedance_computation': <ImpedanceComputation object>,
        'truncated_geometry': [[x1, r1], [x2, r2], ...]
    },
    95.0: { ... },
    ...
}
```

## Interpretación de Resultados

### Frecuencias de Resonancia
- **f0**: Frecuencia fundamental del resonador truncado
- **Relación con longitud**: f0 debería aumentar al truncar (longitud menor → frecuencia mayor)
- **Desviación de armónicos**: f1/f0 debería ser ~2.0 para un tubo perfectamente cilíndrico

### Inharmonicidad
- **Valor positivo**: f1 > 2×f0 (compresión de octava)
- **Valor negativo**: f1 < 2×f0 (expansión de octava)
- **Cero**: Sistema perfectamente armónico

### Longitud Efectiva
- Comparar `effective_length_mm` con `length_mm` para ver el efecto de la conicidad
- Si son similares: bore aproximadamente cilíndrico
- Si difieren: conicidad significativa

## Consideraciones Técnicas

1. **Geometría truncada**: Se mantiene el corcho en x=0, el extremo truncado es abierto (radiación unflanged)
2. **Interpolación**: Si el truncamiento no coincide exactamente con un punto de medición, se interpola el radio
3. **Longitud mínima**: Secciones menores a `min_length_mm` pueden generar resultados inválidos
4. **Embocadura**: Si `include_embouchure=True`, se incluye en el análisis (recomendado)

## Ejemplo Completo

Ver `example_resonator_truncation.py` para un ejemplo completo de uso.

## Integración con el Sistema Existente

El análisis se integra con:
- `FluteData` / `FluteDataDB`: Para cargar datos de flautas
- `FluteAnalyzer`: Método helper `create_resonator_truncation_analyzer()`
- OpenWind: Usa `ImpedanceComputation` sin agujeros laterales

## Referencias

- Similar a estudios de "cutoff length" en acústica de instrumentos de viento
- Útil para entender el efecto de la conicidad en la respuesta acústica
- Permite aislar el efecto del resonador base sin interferencia de agujeros

