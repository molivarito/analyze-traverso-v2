# Procedimiento para Poblar la Base de Datos

## Resumen

La base de datos SQLite almacena:
- Geometría de las flautas
- Parámetros de cálculo de impedancia
- Resultados de análisis acústico (cacheados)
- Geometría externa (medida o paramétrica)

## Paso 1: Resetear la Base de Datos (si es necesario)

Si la base de datos es muy grande o está corrupta, puedes resetearla:

```bash
python reset_database.py
```

Este script:
- Hace un backup automático de la BD actual (con timestamp)
- Borra la BD actual
- Crea una nueva BD vacía con el esquema correcto

**Nota:** Si la BD es > 100 MB, te pedirá confirmación escribiendo 'SI'.

## Paso 2: Poblar la Base de Datos

### Opción A: Poblar todas las flautas

```bash
python populate_database.py
```

### Opción B: Poblar flautas específicas

```bash
python populate_database.py --flutes "Deppe" "Grenser-Weemaels" "Bizey_Boudin"
```

### Opción C: Con parámetros personalizados

```bash
python populate_database.py \
    --flutes "Deppe" "Grenser-Weemaels" \
    --temperature 20.0 \
    --la-frequency 415.0 \
    --force-recalculate
```

### Parámetros disponibles:

- `--data-dir`: Directorio de datos JSON (default: `../data_json`)
- `--flutes`: Lista de nombres de flautas a procesar
- `--temperature`: Temperatura en Celsius (default: 20.0)
- `--la-frequency`: Frecuencia del La en Hz (default: 415.0)
- `--force-recalculate`: Fuerza recálculo incluso si existe en BD

## Paso 3: Poblar Gradualmente (Recomendado)

Para evitar que la BD crezca demasiado, es mejor poblar gradualmente:

### 1. Procesar flautas por grupos pequeños

```bash
# Grupo 1: Flautas principales
python populate_database.py --flutes "Deppe" "Grenser-Weemaels"

# Grupo 2: Otras flautas
python populate_database.py --flutes "Bizey_Boudin" "Stanesby"
```

### 2. Verificar tamaño de BD después de cada grupo

```bash
# Ver tamaño de BD
ls -lh flute_analysis.db
```

### 3. Monitorear el crecimiento

La BD debería crecer aproximadamente:
- ~1-5 MB por flauta (dependiendo de la cantidad de notas calculadas)
- Si crece mucho más, puede haber datos duplicados o problemas

## Paso 4: Usar la Base de Datos en la GUI

Una vez poblada, la GUI usará automáticamente la BD si:
- La BD existe y es < 1 GB
- Los cálculos están cacheados para los parámetros solicitados

Si la BD es > 1 GB, la GUI funcionará sin caché (calculando directamente desde JSON).

## Buenas Prácticas

1. **Poblar gradualmente**: No procesar todas las flautas de una vez
2. **Verificar tamaño**: Monitorear el tamaño de la BD regularmente
3. **Hacer backups**: El script de reset hace backups automáticos
4. **Usar parámetros consistentes**: Usar los mismos `temperature` y `la_frequency` para comparaciones
5. **Limpiar periódicamente**: Si la BD crece demasiado, considerar resetear y repoblar solo las flautas necesarias

## Solución de Problemas

### La BD es demasiado grande (> 1 GB)

1. Resetear la BD: `python reset_database.py`
2. Poblar solo las flautas que realmente necesitas
3. Considerar usar la aplicación sin caché (funciona bien)

### Error al poblar una flauta

- Verifica que los archivos JSON estén correctos
- Revisa los logs para ver errores específicos
- La flauta se puede usar sin estar en la BD

### La GUI no usa la BD

- Verifica que la BD existe y es < 1 GB
- Verifica que los parámetros de cálculo coincidan
- La GUI funcionará sin caché si la BD no está disponible

## Estructura de la Base de Datos

```
flute_analysis.db
├── flutes (información general)
├── flute_geometry (geometría de partes)
├── impedance_calculation_params (parámetros de cálculo)
├── impedance_results (resultados cacheados)
├── external_geometry (geometría externa medida)
└── external_geometry_parameters (parámetros de modelo paramétrico)
```

## Notas Importantes

- **La BD es un caché**: Los datos originales están en los archivos JSON
- **No es crítica**: La aplicación funciona perfectamente sin BD
- **Se puede regenerar**: Siempre puedes resetear y repoblar
- **Optimización futura**: Se puede implementar compresión o limpieza automática

