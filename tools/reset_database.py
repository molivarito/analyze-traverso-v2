"""
Script para resetear la base de datos de flautas.

Este script:
1. Hace un backup de la BD actual (si existe)
2. Borra la BD actual
3. Crea una nueva BD vacía con el esquema correcto
"""

import shutil
from pathlib import Path
from datetime import datetime
import logging

from db_schema import DEFAULT_DB_PATH, create_database_schema

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def reset_database(backup: bool = True) -> None:
    """
    Resetea la base de datos.
    
    Args:
        backup: Si True, hace un backup de la BD actual antes de borrarla.
    """
    db_path = Path(DEFAULT_DB_PATH)
    
    if not db_path.exists():
        logger.info("No existe base de datos, creando una nueva...")
        create_database_schema()
        logger.info("✓ Base de datos nueva creada")
        return
    
    # Obtener tamaño de la BD
    db_size_mb = db_path.stat().st_size / (1024 * 1024)
    logger.info(f"Base de datos actual: {db_path}")
    logger.info(f"Tamaño: {db_size_mb:.2f} MB ({db_size_mb/1024:.2f} GB)")
    
    if backup:
        # Crear backup con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"
        
        # Para archivos grandes (> 1 GB), renombrar es mucho más rápido que copiar
        if db_size_mb > 1024:
            logger.info(f"Archivo grande detectado, renombrando en lugar de copiar...")
            logger.info(f"Renombrando a: {backup_path}")
            db_path.rename(backup_path)
            logger.info(f"✓ Archivo renombrado: {backup_path}")
            logger.info(f"  Tamaño: {backup_path.stat().st_size / (1024 * 1024):.2f} MB")
            # No necesitamos borrar después, ya está renombrado
            logger.info("Creando nueva base de datos...")
            create_database_schema()
            logger.info("✓ Base de datos nueva creada")
            logger.info("\n" + "="*60)
            logger.info("Base de datos reseteada exitosamente")
            logger.info("="*60)
            return
        else:
            logger.info(f"Creando backup en: {backup_path}")
            shutil.copy2(db_path, backup_path)
            logger.info(f"✓ Backup creado: {backup_path}")
            logger.info(f"  Tamaño del backup: {backup_path.stat().st_size / (1024 * 1024):.2f} MB")
    
    # Borrar BD actual
    logger.info("Borrando base de datos actual...")
    db_path.unlink()
    logger.info("✓ Base de datos borrada")
    
    # Crear nueva BD
    logger.info("Creando nueva base de datos...")
    create_database_schema()
    logger.info("✓ Base de datos nueva creada")
    
    logger.info("\n" + "="*60)
    logger.info("Base de datos reseteada exitosamente")
    logger.info("="*60)


if __name__ == "__main__":
    import sys
    
    # Preguntar confirmación si la BD es grande
    db_path = Path(DEFAULT_DB_PATH)
    if db_path.exists():
        db_size_mb = db_path.stat().st_size / (1024 * 1024)
        if db_size_mb > 100:
            print(f"\n⚠️  ADVERTENCIA: La base de datos es grande ({db_size_mb/1024:.2f} GB)")
            print("¿Estás seguro de que quieres resetearla?")
            respuesta = input("Escribe 'SI' para confirmar: ")
            if respuesta != 'SI':
                print("Operación cancelada.")
                sys.exit(0)
    
    reset_database(backup=True)
    print("\n✓ Proceso completado. Puedes ahora poblar la BD gradualmente.")

