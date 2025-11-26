"""
Script para migrar archivos JSON de flautas a la base de datos.

Este script:
1. Busca todos los directorios de flautas en el directorio de datos JSON
2. Carga cada flauta usando FluteDataDB
3. Calcula y guarda los análisis acústicos en la base de datos
4. Permite procesar todas las flautas o flautas específicas
"""

import argparse
from pathlib import Path
from typing import List, Optional
import logging
import sys

from flute_data_db import FluteDataDB
from db_schema import DEFAULT_DB_PATH

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s [%(name)s:%(funcName)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)


def find_flute_directories(data_dir: Path) -> List[Path]:
    """
    Encuentra todos los directorios de flautas en el directorio de datos.
    
    Args:
        data_dir: Directorio raíz donde buscar flautas.
    
    Returns:
        Lista de rutas a directorios de flautas.
    """
    flute_dirs = []
    
    if not data_dir.exists() or not data_dir.is_dir():
        logger.error(f"El directorio de datos no existe o no es un directorio: {data_dir}")
        return flute_dirs
    
    for item in data_dir.iterdir():
        if item.is_dir():
            # Verificar si contiene archivos JSON de partes de flauta
            has_json_files = any(
                (item / f"{part}.json").exists() 
                for part in ["headjoint", "left", "right", "foot"]
            )
            if has_json_files:
                flute_dirs.append(item)
    
    return sorted(flute_dirs)


def migrate_flute(
    flute_dir: Path,
    temperature: float = 20.0,
    la_frequency: float = 415.0,
    force_recalculate: bool = False
) -> bool:
    """
    Migra una flauta a la base de datos.
    
    Args:
        flute_dir: Directorio de la flauta.
        temperature: Temperatura en Celsius.
        la_frequency: Frecuencia del La (diapason) en Hz.
        force_recalculate: Si True, fuerza recálculo incluso si existe.
    
    Returns:
        True si la migración fue exitosa, False en caso contrario.
    """
    try:
        logger.info(f"Migrando flauta desde: {flute_dir}")
        
        # Cargar flauta usando FluteDataDB (esto automáticamente la guarda en BD)
        flute_data = FluteDataDB(
            source=str(flute_dir),
            temperature=temperature,
            la_frequency=la_frequency,
            skip_acoustic_analysis=False,
            force_recalculate=force_recalculate
        )
        
        if flute_data.validation_errors:
            logger.error(f"Errores de validación para {flute_dir.name}: {flute_data.validation_errors}")
            return False
        
        if not flute_data.acoustic_analysis:
            logger.warning(f"No se pudo calcular análisis acústico para {flute_dir.name}")
            return False
        
        logger.info(f"✓ Flauta '{flute_data.flute_model}' migrada exitosamente ({len(flute_data.acoustic_analysis)} notas)")
        return True
        
    except Exception as e:
        logger.error(f"Error migrando flauta {flute_dir.name}: {e}", exc_info=True)
        return False


def main():
    """Función principal del script de migración."""
    parser = argparse.ArgumentParser(
        description="Migra archivos JSON de flautas a la base de datos"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        help="Directorio raíz donde buscar flautas (por defecto: data_json relativo al script)"
    )
    parser.add_argument(
        "--flute",
        type=str,
        help="Nombre específico de flauta a migrar (opcional)"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=20.0,
        help="Temperatura en Celsius (por defecto: 20.0)"
    )
    parser.add_argument(
        "--la-frequency",
        type=float,
        default=415.0,
        help="Frecuencia del La (diapason) en Hz (por defecto: 415.0)"
    )
    parser.add_argument(
        "--force-recalculate",
        action="store_true",
        help="Fuerza recálculo incluso si ya existe en la base de datos"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        help="Ruta al archivo de base de datos (por defecto: flute_analysis.db en el directorio del script)"
    )
    
    args = parser.parse_args()
    
    # Determinar directorio de datos
    if args.data_dir:
        data_dir = Path(args.data_dir)
    else:
        script_dir = Path(__file__).parent
        data_dir = script_dir / "data_json"
        if not data_dir.exists():
            data_dir = script_dir.parent / "data_json"
    
    if not data_dir.exists():
        logger.error(f"El directorio de datos no existe: {data_dir}")
        sys.exit(1)
    
    logger.info(f"Buscando flautas en: {data_dir}")
    
    # Encontrar directorios de flautas
    if args.flute:
        # Buscar flauta específica
        flute_dir = data_dir / args.flute
        if not flute_dir.exists() or not flute_dir.is_dir():
            logger.error(f"No se encontró el directorio de la flauta: {flute_dir}")
            sys.exit(1)
        flute_dirs = [flute_dir]
    else:
        # Buscar todas las flautas
        flute_dirs = find_flute_directories(data_dir)
        if not flute_dirs:
            logger.warning(f"No se encontraron directorios de flautas en: {data_dir}")
            sys.exit(0)
    
    logger.info(f"Encontradas {len(flute_dirs)} flauta(s) para migrar")
    
    # Migrar cada flauta
    successful = 0
    failed = 0
    
    for flute_dir in flute_dirs:
        if migrate_flute(
            flute_dir,
            temperature=args.temperature,
            la_frequency=args.la_frequency,
            force_recalculate=args.force_recalculate
        ):
            successful += 1
        else:
            failed += 1
    
    # Resumen
    logger.info("=" * 60)
    logger.info(f"Migración completada:")
    logger.info(f"  ✓ Exitosas: {successful}")
    logger.info(f"  ✗ Fallidas: {failed}")
    logger.info(f"  Total: {len(flute_dirs)}")
    logger.info(f"Base de datos: {DEFAULT_DB_PATH}")
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

