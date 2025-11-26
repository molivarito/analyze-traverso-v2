# Instrucciones para Completar y Compilar el Reporte LaTeX

## Archivos Creados

1. **`reporte_sistema_analisis_flautas.tex`**: Documento principal con estructura completa
2. **`reporte_secciones_completas.tex`**: Secciones expandidas con derivaciones matemáticas completas

## Estructura del Reporte

El reporte está diseñado para ser **multilingüe (Español y Francés)** con:
- Derivaciones matemáticas completas
- Espacios para capturas de pantalla
- Referencias académicas
- Casos de estudio

## Pasos para Completar el Reporte

### 1. Integrar Secciones Completas

Las secciones en `reporte_secciones_completas.tex` deben integrarse en el documento principal:

- **MOC**: Agregar después de la sección de Inharmonicidad
- **B_I**: Agregar después de MOC
- **ESPE**: Agregar después de B_I
- **Q-Factor**: Agregar después de ESPE
- **Frecuencias vs Temperamento**: Agregar después de Q-Factor
- **Altura de Picos**: Agregar después de Frecuencias vs Temperamento
- **Ratio Armónicos**: Agregar después de Altura de Picos
- **Coherencia de Fase**: Agregar después de Ratio Armónicos
- **Estabilidad de Pitch**: Agregar después de Coherencia de Fase
- **Cut-off Frequency**: Agregar después de Estabilidad de Pitch

### 2. Agregar Capturas de Pantalla

Crear un directorio `figuras/` y agregar las siguientes capturas:

#### Visualizaciones 2D:
- `perfil_fisico_acustico.png`: Comparación de perfil físico y acústico
- `perfil_combinado.png`: Perfil combinado con agujeros
- `vista_solido_2d.png`: Vista sólido 2D mostrando espesor de pared
- `corte_axial.png`: Corte axial del sólido

#### Visualizaciones 3D:
- `flauta_completa_3d.png`: Modelo 3D de flauta completa
- `partes_individuales_3d.png`: Partes individuales en 3D
- `comparacion_flautas_3d.png`: Comparación de múltiples flautas

#### Análisis Acústico:
- `admitancia_frecuencia.png`: Gráfico de admitancia en frecuencia
- `presion_flujo_espacial.png`: Presión y flujo espaciales
- `geometria_acustica.png`: Geometría acústica con agujeros y digitación
- `dashboard_resumen.png`: Dashboard de resumen con métricas
- `grafico_radar.png`: Gráfico radar comparativo
- `inharmonicidad.png`: Gráfico de inharmonicidad
- `moc.png`: Gráfico de MOC
- `bi_espe.png`: Gráfico de B_I y ESPE
- `frecuencias_resonancia.png`: Frecuencias de resonancia vs temperamento
- `altura_picos.png`: Altura de picos de admitancia
- `q_factor.png`: Q-Factor
- `caracteristicas_tonales.png`: Características tonales (ratios + fase)
- `estabilidad.png`: Estabilidad (pitch + cut-off)

#### Planos de Ingeniería:
- `plano_ingenieria_pagina1.png`: Primera página del plano
- `plano_ingenieria_pagina2.png`: Segunda página del plano

#### Editor de Geometría:
- `editor_geometria.png`: Interfaz del editor de geometría
- `comparacion_original_modificado.png`: Comparación acústica original vs modificado

#### G-code:
- `gcode_trayectorias.png`: Visualización de trayectorias G-code

### 3. Completar Casos de Estudio

En la Sección 6 (Casos de Estudio), agregar:

#### Caso 1: Análisis de Flauta Histórica
- Nombre de la flauta
- Datos históricos (constructor, fecha, etc.)
- Análisis completo con todas las métricas
- Capturas de pantalla específicas
- Interpretación de resultados

#### Caso 2: Comparación de Dos Flautas
- Comparación lado a lado
- Tabla comparativa de métricas
- Gráficos comparativos
- Análisis de diferencias

#### Caso 3: Optimización de Diseño
- Modificaciones realizadas
- Comparación antes/después
- Impacto en métricas acústicas

### 4. Completar Referencias Académicas

Agregar referencias en la sección de bibliografía:

```latex
\bibitem{helie2020}
Helie, T., \& Matignon, D. (2020).
\textit{OpenWind: A Python Library for Wind Instrument Modeling}.
INRIA Research Report RR-XXXX.

\bibitem{benade1990}
Benade, A. H. (1990).
\textit{Fundamentals of Musical Acoustics}.
Dover Publications, New York.

\bibitem{chaigne2013}
Chaigne, A., \& Kergomard, J. (2013).
\textit{Acoustics of Musical Instruments}.
Springer, New York.

\bibitem{webster1919}
Webster, A. G. (1919).
Acoustical impedance, and the theory of horns and of the phonograph.
\textit{Proceedings of the National Academy of Sciences}, 5(7), 275-282.

\bibitem{toff1996}
Toff, N. (1996).
\textit{The Flute Book: A Complete Guide for Students and Performers}.
Oxford University Press, Oxford.

\bibitem{quantz1752}
Quantz, J. J. (1752).
\textit{Versuch einer Anweisung die Flöte traversiere zu spielen}.
Berlin.

\bibitem{ricci2003}
Ricci, A. (2003).
\textit{The Baroque Flute Fingering Book}.
Ricci Publications.

\bibitem{flutehistory}
Powell, A. (2002).
\textit{The Flute}.
Yale University Press, New Haven.
```

### 5. Completar Apéndices

#### Apéndice A: Formato de Archivos JSON

Incluir ejemplo completo de archivo JSON con todas las partes:

```json
{
  "headjoint": {
    "measurements": [...],
    "Holes position": [...],
    "Holes diameter": [...],
    ...
  },
  ...
}
```

#### Apéndice B: Instalación y Configuración

- Requisitos del sistema
- Instalación de dependencias (Python, OpenWind, PyQt5, etc.)
- Configuración inicial
- Solución de problemas comunes

#### Apéndice C: Guía de Uso

- Flujo de trabajo típico
- Ejemplos paso a paso
- Consejos y mejores prácticas

#### Apéndice D: Glosario

- Términos técnicos
- Términos musicales
- Símbolos matemáticos

## Compilación del Documento

### Requisitos

- LaTeX distribuition (TeX Live, MiKTeX, o MacTeX)
- Paquetes necesarios (instalados automáticamente en la mayoría de distribuciones)

### Compilación

```bash
# Primera compilación (genera TOC y referencias)
pdflatex reporte_sistema_analisis_flautas.tex

# Compilar referencias (si se usa BibTeX)
bibtex reporte_sistema_analisis_flautas

# Segunda compilación (actualiza referencias)
pdflatex reporte_sistema_analisis_flautas.tex

# Tercera compilación (asegura que todo esté actualizado)
pdflatex reporte_sistema_analisis_flautas.tex
```

O usar un script de compilación:

```bash
#!/bin/bash
pdflatex reporte_sistema_analisis_flautas.tex
bibtex reporte_sistema_analisis_flautas
pdflatex reporte_sistema_analisis_flautas.tex
pdflatex reporte_sistema_analisis_flautas.tex
```

### Compilación con Make

Crear un `Makefile`:

```makefile
MAIN = reporte_sistema_analisis_flautas
TEX = $(MAIN).tex
PDF = $(MAIN).pdf

all: $(PDF)

$(PDF): $(TEX)
	pdflatex $(TEX)
	bibtex $(MAIN)
	pdflatex $(TEX)
	pdflatex $(TEX)

clean:
	rm -f *.aux *.log *.out *.toc *.bbl *.blg *.bcf *.run.xml

.PHONY: all clean
```

## Estructura de Directorios Recomendada

```
proyecto/
├── reporte_sistema_analisis_flautas.tex
├── reporte_secciones_completas.tex
├── figuras/
│   ├── perfil_fisico_acustico.png
│   ├── perfil_combinado.png
│   ├── vista_solido_2d.png
│   ├── corte_axial.png
│   ├── flauta_completa_3d.png
│   ├── admitancia_frecuencia.png
│   ├── ...
│   └── [todas las capturas de pantalla]
├── casos_estudio/
│   ├── caso1_flauta_historica.tex
│   ├── caso2_comparacion.tex
│   └── caso3_optimizacion.tex
└── apendices/
    ├── formato_json.tex
    ├── instalacion.tex
    ├── guia_uso.tex
    └── glosario.tex
```

## Notas Importantes

1. **Idiomas**: El documento usa `\selectlanguage{spanish}` y `\selectlanguage{french}` para alternar entre idiomas. Asegúrate de que todas las secciones tengan ambas versiones.

2. **Figuras**: Todas las figuras deben estar en formato PNG o PDF de alta resolución (mínimo 300 DPI).

3. **Referencias Cruzadas**: Usar `\ref{}` y `\eqref{}` para referencias a figuras y ecuaciones.

4. **Ecuaciones**: Todas las ecuaciones importantes deben estar numeradas usando `\begin{equation}...\end{equation}`.

5. **Tablas**: Usar el entorno `table` con `booktabs` para tablas profesionales.

## Checklist Final

Antes de compilar el documento final:

- [ ] Todas las secciones de mediciones acústicas completadas
- [ ] Todas las derivaciones matemáticas incluidas
- [ ] Todas las capturas de pantalla agregadas
- [ ] Casos de estudio completados
- [ ] Referencias académicas completas
- [ ] Apéndices completados
- [ ] Glosario completo
- [ ] Revisión ortográfica en ambos idiomas
- [ ] Verificación de referencias cruzadas
- [ ] Verificación de numeración de ecuaciones y figuras

## Soporte

Si encuentras problemas al compilar:
1. Verificar que todos los paquetes estén instalados
2. Revisar los logs de compilación (.log)
3. Verificar rutas de figuras
4. Asegurar que todas las referencias estén definidas

