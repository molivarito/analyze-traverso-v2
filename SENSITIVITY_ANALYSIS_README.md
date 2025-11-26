# Análisis de Sensibilidad de Flautas Traverso

## Descripción General

El módulo de Análisis de Sensibilidad permite estudiar cómo la variación gradual de parámetros geométricos afecta la respuesta acústica de una flauta traverso. Esta funcionalidad es esencial para:

- **Optimización del diseño**: Identificar rangos óptimos para cada parámetro geométrico.
- **Estudio de tolerancias**: Comprender qué parámetros son más críticos y requieren mayor precisión en la fabricación.
- **Investigación histórica**: Analizar variaciones documentadas en instrumentos de diferentes períodos o constructores.
- **Desarrollo de prototipos**: Guiar modificaciones para mejorar características acústicas específicas.

## Acceso

**Menú**: `Análisis` > `Análisis de Sensibilidad...`

**Requisito**: Al menos una flauta debe estar cargada en la GUI.

## Parámetros Disponibles

Los parámetros están organizados por prioridad según su impacto en la respuesta acústica:

### Prioridad 1: Ángulo de Undercut de Agujeros

**Descripción**: Modifica el ángulo de conicidad de los agujeros laterales. El undercut es una técnica donde el agujero es más ancho en el interior que en el exterior, formando un cono.

**Rango típico**: 0° (cilindro) a 15° (undercut fuerte)

**Impacto acústico**:
- Afecta la afinación de notas específicas
- Modifica la respuesta en diferentes registros
- Influye en la "speaking quality" del instrumento

**Aplicación**: 
- Puede aplicarse a todos los agujeros simultáneamente
- Puede aplicarse a un agujero específico para correcciones finas

**Implementación técnica**: Los agujeros cónicos se representan en OpenWind mediante `[x_position, height, radius_top, radius_bottom, "linear"]`, donde:
- `radius_top`: Radio en la superficie externa
- `radius_bottom`: Radio en la superficie interna (mayor para undercut)
- `radius_bottom = radius_top + height * tan(angle)`

### Prioridad 2: Ángulo de Conicidad de Partes

**Descripción**: Modifica la pendiente del bore (tubo interior) de una parte específica (headjoint, left, right, foot).

**Rango típico**: ±50% de la pendiente actual

**Impacto acústico**:
- Afecta el balance entre registros
- Modifica la afinación general del instrumento
- Influye en la estabilidad de ciertas notas

**Aplicación**: Se aplica a una parte específica a la vez.

**Implementación técnica**: Se calcula la pendiente actual mediante regresión lineal y se genera un nuevo perfil manteniendo el diámetro en un punto de referencia (inicio de la parte).

### Prioridad 3: Posición del Corcho

**Descripción**: Modifica la posición del corcho (stopper) en el headjoint, lo que cambia la longitud acústica efectiva de la embocadura.

**Rango típico**: ±10 mm de la posición actual

**Impacto acústico**:
- Afecta fuertemente la afinación general
- Modifica el color tonal del instrumento
- Es uno de los ajustes más comunes en la práctica

**Implementación técnica**: Se modifica `_calculated_stopper_absolute_position_mm` en el headjoint y se recalcula `combined_measurements`.

### Prioridad 4: Diámetro de Agujeros Laterales

**Descripción**: Modifica el diámetro de los agujeros laterales (excluyendo la embocadura).

**Rango típico**: ±20% del diámetro actual o ±2 mm

**Impacto acústico**:
- Afecta la afinación de notas específicas
- Modifica la facilidad de emisión

### Prioridad 5: Diámetro de Embocadura

**Descripción**: Modifica el diámetro del agujero de embocadura.

**Rango típico**: ±2 mm del diámetro actual

**Impacto acústico**:
- Afecta el timbre general
- Modifica la respuesta y facilidad de emisión
- Influye en el volumen y proyección del sonido

### Prioridad 6: Posición de Agujeros Laterales

**Descripción**: Desplaza la posición de un agujero lateral específico a lo largo del tubo.

**Rango típico**: ±10 mm

**Impacto acústico**:
- Afecta la afinación de la nota correspondiente
- Menos crítico que el diámetro en la mayoría de casos

## Uso del Diálogo

### 1. Selección de Flauta Base

Elige la flauta de referencia desde la cual se generarán las variantes. Se muestra información básica:
- Largo acústico
- Número total de agujeros

### 2. Configuración del Parámetro

**Parámetro**: Selecciona qué parámetro variar.

**Controles específicos** (según el parámetro):
- **Parte**: Para parámetros que se aplican a una parte específica (ej: conicidad).
- **Agujero**: Para parámetros que pueden aplicarse a un agujero específico o a todos (valor 0 = todos).

**Valor actual**: Muestra el valor de referencia del parámetro en la flauta base.

### 3. Rango de Variación

Define el rango de valores a explorar:

**Valor mínimo/máximo**: Límites del rango de variación.

**Modo de configuración** (elige uno):
- **Número de pasos**: Especifica cuántas variantes generar. El tamaño de paso se calcula automáticamente.
- **Tamaño de paso**: Especifica el incremento entre variantes. El número de variantes se calcula automáticamente.

**Ejemplo**: Para estudiar undercut de 0° a 15° en 16 pasos:
- Valor mínimo: 0.0
- Valor máximo: 15.0
- Número de pasos: 16
- Resultado: Variantes en 0°, 1°, 2°, ..., 15° (tamaño de paso = 1.0°)

### 4. Previsualización

Muestra los valores que se generarán y el número total de variantes. Para listas largas (>15), muestra las primeras 5 y últimas 5 con un indicador de valores omitidos.

### 5. Opciones de Cálculo

**Calcular análisis acústico**: Si está marcado, se ejecuta el análisis completo de impedancia para cada variante. **Recomendado para análisis serio**.

**Incluir datos de presión/flujo**: Guarda los datos de presión y flujo acústico. Útil para análisis detallados pero aumenta significativamente el tamaño de datos.

**Temperatura**: Temperatura del aire para los cálculos acústicos (default: 20°C).

**Diapasón (La)**: Frecuencia de referencia para La (default: 415 Hz). Afecta el cálculo de finger_frequencies.

### 6. Generación

**Botón "Generar y Cargar Variantes"**: Inicia el proceso. Se muestra:
- Diálogo de confirmación con resumen de la configuración
- Barra de progreso durante la generación
- Mensaje de éxito al finalizar

Las variantes se cargan automáticamente en la GUI y están disponibles para visualización en todas las pestañas.

## Nombres de Variantes

Las variantes generadas tienen nombres descriptivos que siguen el formato:

```
{nombre_base}_{param_abbr}_{target_info}_{valor}{unidad}_v{índice}
```

**Ejemplos**:
- `Wijne_undercut_5.0deg_v3` - Tercera variante con undercut de 5°
- `Bressan_taper_left_+15pct_v7` - Séptima variante con conicidad de "left" aumentada 15%
- `Hotteterre_cork_+2.5mm_v5` - Quinta variante con corcho desplazado +2.5 mm
- `Quantz_holeDiam_h3_7.2mm_v10` - Décima variante con agujero 3 de 7.2 mm

## Visualización y Análisis de Resultados

Una vez generadas, las variantes están disponibles en **todas** las pestañas de la GUI:

### Geometría (2D)

- **Perfil Combinado**: Compara los perfiles de todas las variantes superpuestas.
- **Partes Individuales**: Visualiza cada parte de cada variante.
- **Vista Sólido 2D** y **Corte Axial**: Muestra el espesor de pared y agujeros.

### Admitancia

- Compara la respuesta en frecuencia para cada nota.
- Visualiza presión y flujo acústico (si se calcularon).
- Muestra la geometría acústica con agujeros abiertos/cerrados por nota.

### Análisis Acústico

**Esta pestaña es especialmente útil para análisis de sensibilidad**:

- **Resumen (Dashboard)**: Compara métricas clave de todas las variantes en un gráfico radar.
- **Inharmonicidad**: Muestra cómo varía la inharmonicidad con el parámetro.
- **Frecuencias**: Compara frecuencias de resonancia vs temperamento para todas las variantes.
- **MOC (Modal Octave Compression)**: Identifica variantes con mejor balance entre octavas.
- **B_I & ESPE**: Muestra desviaciones de afinación.
- **Altura de Picos, Q-Factor**: Analiza la "speaking quality".
- **Características Tonales**: Ratios de armónicos y fase.
- **Estabilidad**: Estabilidad de pitch y cut-off frequency.

**Tip**: Para análisis de sensibilidad, enfócate en las pestañas que muestran **tendencias** cuando se ordenan las variantes por el valor del parámetro.

### Visualización 3D

Todas las variantes aparecen en el árbol de flautas. Útil para inspeccionar visualmente cambios geométricos grandes.

### Planos de Ingeniería y G-code

Puedes generar planos y G-code para cualquier variante seleccionándola en el combo correspondiente.

## Flujo de Trabajo Recomendado

### Análisis de Sensibilidad Básico

1. **Carga tu flauta** de interés en la GUI.
2. **Abre el diálogo** de Análisis de Sensibilidad (Menú `Análisis`).
3. **Selecciona el parámetro** que deseas estudiar (ej: Undercut de agujeros).
4. **Define un rango amplio** inicial (ej: 0° a 15° en 16 pasos).
5. **Activa "Calcular análisis acústico"** (desactiva "presión/flujo" para ahorrar espacio).
6. **Genera las variantes**.
7. **Analiza en "Análisis Acústico"**:
   - Ve al **Dashboard** para una vista general.
   - Revisa **Inharmonicidad** para ver tendencias.
   - Examina **Frecuencias** para identificar el rango óptimo.
8. **Identifica el rango prometedor** (ej: 5° a 10° parece mejor).
9. **Genera nuevas variantes** con un rango más fino en ese intervalo (ej: 5° a 10° en 11 pasos = cada 0.5°).
10. **Repite** hasta encontrar el valor óptimo.

### Optimización Multi-Parámetro

Para optimizar varios parámetros:

1. **Optimiza un parámetro** a la vez usando el flujo básico.
2. **Registra el valor óptimo** encontrado.
3. **Repite para el siguiente parámetro**, usando la flauta con el primer parámetro ya optimizado como base.
4. **Opcionalmente, itera**: Una vez optimizados todos, vuelve al primero para ver si el óptimo cambió.

**Nota**: Para optimización simultánea de múltiples parámetros, considera usar técnicas de diseño de experimentos (DoE) o algoritmos de optimización (futuras mejoras).

### Estudio de Tolerancias

1. **Genera variantes pequeñas** alrededor del valor nominal (ej: ±1 mm para posición de agujero).
2. **Calcula análisis acústico completo**.
3. **Compara métricas clave** (ej: desviación de afinación en cents).
4. **Determina tolerancias aceptables** basándote en cuánto pueden variar las métricas sin degradar la calidad.

## Exportación de Resultados

Actualmente, los resultados pueden exportarse mediante:

### Exportación Manual (Disponible)

- **Capturas de pantalla**: Usa las herramientas de tu sistema operativo para capturar gráficos.
- **Tablas**: Copia datos de la pestaña de análisis (si están visibles).

### Exportación Automática (Futuro)

- **CSV**: Tabla con todas las métricas por variante y nota.
- **PDF**: Reporte completo con gráficos de evolución de cada métrica vs parámetro.

**Nota**: Las funciones de exportación CSV/PDF están pendientes de implementación.

## Limitaciones y Consideraciones

### Memoria y Rendimiento

- Cada variante con análisis acústico completo ocupa ~5-50 MB en RAM (según el número de notas y si incluye presión/flujo).
- **Recomendación**: Para análisis con >50 variantes, considera:
  - Desactivar "Incluir datos de presión/flujo".
  - Cerrar otras aplicaciones para liberar RAM.
  - Analizar en lotes (ej: 2 análisis de 30 variantes cada uno).

### Tiempo de Cálculo

- **Sin análisis acústico**: ~1-5 segundos para 50 variantes (solo geometría).
- **Con análisis acústico**: ~30 segundos a 5 minutos para 50 variantes (depende del número de notas y la complejidad del instrumento).

### Validaciones

El sistema incluye validaciones básicas:
- Valor mínimo < Valor máximo
- Diámetros de agujeros no exceden el diámetro del bore
- Posiciones de agujeros dentro de la parte

**Sin embargo**, el sistema **no** valida si las modificaciones resultan en geometrías físicamente imposibles o musicalmente inútiles. Usa tu criterio y conocimiento del instrumento.

### Datos de Base

Las variantes se generan **en memoria** y **no** se guardan automáticamente en la base de datos para evitar saturarla. Para guardar una variante prometedora:

1. Usa el **Editor de Geometría** para recrearla manualmente.
2. Guárdala con un nombre nuevo.
3. Cárgala normalmente en la GUI.

## Casos de Uso Documentados

### Caso 1: Optimización de Undercut para Inharmonicidad

**Objetivo**: Encontrar el ángulo de undercut que minimiza la inharmonicidad promedio.

**Configuración**:
- Flauta base: Wijne
- Parámetro: Undercut de todos los agujeros
- Rango: 0° a 15° en 16 pasos
- Cálculo acústico: Sí (sin presión/flujo)

**Resultado esperado**: Gráfico de inharmonicidad promedio vs undercut, identificando un mínimo alrededor de 5-8°.

### Caso 2: Estudio de Conicidad del Headjoint

**Objetivo**: Analizar cómo la conicidad del headjoint afecta el balance entre registros.

**Configuración**:
- Flauta base: Bressan
- Parámetro: Conicidad de headjoint
- Rango: -30% a +30% en 13 pasos
- Cálculo acústico: Sí (con presión/flujo para visualización detallada)

**Resultado esperado**: Gráficos de MOC y B_I/ESPE mostrando cómo el balance entre octavas mejora o empeora.

### Caso 3: Ajuste Fino de Afinación con Posición del Corcho

**Objetivo**: Afinar el instrumento ajustando el corcho.

**Configuración**:
- Flauta base: Hotteterre
- Parámetro: Posición del corcho
- Rango: -5 mm a +5 mm en 21 pasos (cada 0.5 mm)
- Cálculo acústico: Sí

**Resultado esperado**: Gráfico de frecuencias vs temperamento mostrando cómo todas las notas suben o bajan, identificando la posición óptima para un diapasón dado.

## Preguntas Frecuentes

**Q: ¿Puedo variar múltiples parámetros simultáneamente?**
A: Actualmente no. El sistema varía un parámetro a la vez. Para análisis multi-paramétrico, ejecuta análisis secuenciales.

**Q: ¿Las variantes se guardan en la base de datos?**
A: No, las variantes son temporales (solo en RAM). Para guardar una variante, usa el Editor de Geometría para recrearla y guardarla manualmente.

**Q: ¿Puedo exportar las variantes como archivos JSON?**
A: Actualmente no hay una función directa, pero cada variante en memoria tiene su estructura JSON completa que puede ser accedida mediante el Editor de Geometría.

**Q: ¿Por qué el análisis es lento?**
A: El cálculo de impedancia acústica con OpenWind es computacionalmente costoso. Para 50 variantes con 7 notas cada una, se realizan 350 cálculos de impedancia. Considera usar menos notas o menos variantes para análisis preliminares.

**Q: ¿Cómo sé qué parámetro estudiar primero?**
A: Sigue el orden de prioridades recomendado. Generalmente:
1. **Undercut** tiene gran impacto en afinación de notas individuales.
2. **Conicidad** afecta el balance general.
3. **Posición del corcho** ajusta la afinación global.

**Q: ¿Qué hago si el programa se queda sin memoria?**
A: Reduce el número de variantes, desactiva "presión/flujo", o cierra otras aplicaciones. Para estudios grandes, considera dividir en múltiples análisis más pequeños.

**Q: ¿Los nombres de variantes se pueden personalizar?**
A: Actualmente no. Los nombres se generan automáticamente para ser descriptivos y únicos.

## Futuras Mejoras

- [ ] Variación de múltiples parámetros simultáneos (grid search)
- [ ] Exportación automática a CSV/PDF
- [ ] Optimización automática (algoritmos genéticos, gradient descent)
- [ ] Gráficos de superficie 3D (parámetro1 vs parámetro2 vs métrica)
- [ ] Animaciones de evolución de respuesta acústica
- [ ] Guardado/carga de configuraciones de análisis
- [ ] Guardado selectivo de variantes prometedoras en DB
- [ ] Comparación con flautas históricas documentadas

## Soporte y Contribuciones

Para reportar bugs, solicitar funcionalidades o contribuir:
- Consulta el repositorio principal del proyecto
- Contacta al desarrollador/investigador principal

---

**Última actualización**: 2025-11-20
**Versión**: 1.0

