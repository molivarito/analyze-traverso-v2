#!/usr/bin/env python3
"""
Script para mover la base de datos desde Google Drive a una ubicación local.

Este script:
1. Detecta si la base de datos está en Google Drive
2. Crea una nueva ubicación local (en ~/.flute_analysis/)
3. Mueve la base de datos si es posible, o crea una nueva
4. Actualiza la configuración para usar la nueva ubicación
"""

import sqlite3
import shutil
from pathlib import Path
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Ubicación actual (puede estar en Google Drive)
CURRENT_DB_PATH = Path(__file__).parent / "flute_analysis.db"

# Nueva ubicación local (fuera de Google Drive)
LOCAL_DB_DIR = Path.home() / ".flute_analysis"
LOCAL_DB_PATH = LOCAL_DB_DIR / "flute_analysis.db"


def is_in_google_drive(path: Path) -> bool:
    """Verifica si un path está en Google Drive."""
    return "GoogleDrive" in str(path.absolute())


def verify_database_integrity(db_path: Path) -> bool:
    """Intenta verificar la integridad de la base de datos."""
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        cursor = conn.cursor()
        cursor.execute('PRAGMA integrity_check')
        result = cursor.fetchone()
        conn.close()
        return result[0] == 'ok'
    except Exception as e:
        logger.warning(f"No se pudo verificar integridad: {e}")
        return False


def move_database():
    """Mueve la base de datos a una ubicación local."""
    logger.info("=" * 60)
    logger.info("SOLUCIÓN PARA BASE DE DATOS EN GOOGLE DRIVE")
    logger.info("=" * 60)
    
    # 1. Verificar ubicación actual
    logger.info(f"\n1. Ubicación actual: {CURRENT_DB_PATH}")
    logger.info(f"   Existe: {CURRENT_DB_PATH.exists()}")
    
    if CURRENT_DB_PATH.exists():
        logger.info(f"   Tamaño: {CURRENT_DB_PATH.stat().st_size / (1024*1024):.2f} MB")
        logger.info(f"   En Google Drive: {is_in_google_drive(CURRENT_DB_PATH)}")
    
    # 2. Crear directorio local
    logger.info(f"\n2. Creando directorio local: {LOCAL_DB_DIR}")
    LOCAL_DB_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("   ✓ Directorio creado")
    
    # 3. Intentar mover/copiar la base de datos
    if CURRENT_DB_PATH.exists() and not is_in_google_drive(CURRENT_DB_PATH):
        logger.info("\n3. La base de datos ya está fuera de Google Drive.")
        logger.info("   No se requiere mover.")
        return
    
    if CURRENT_DB_PATH.exists():
        logger.info("\n3. Intentando copiar base de datos desde Google Drive...")
        try:
            # Intentar copiar con timeout
            logger.info("   Copiando archivo (esto puede tardar si Google Drive está sincronizando)...")
            shutil.copy2(CURRENT_DB_PATH, LOCAL_DB_PATH)
            logger.info(f"   ✓ Base de datos copiada a: {LOCAL_DB_PATH}")
            
            # Verificar integridad de la copia
            if verify_database_integrity(LOCAL_DB_PATH):
                logger.info("   ✓ Integridad verificada: la base de datos NO está corrupta")
            else:
                logger.warning("   ⚠ La base de datos puede estar corrupta")
                
        except Exception as e:
            logger.error(f"   ✗ Error copiando base de datos: {e}")
            logger.info("   → Creando nueva base de datos vacía en ubicación local...")
            # Crear nueva base de datos vacía
            create_new_database()
    else:
        logger.info("\n3. Base de datos no existe. Creando nueva en ubicación local...")
        create_new_database()
    
    # 4. Crear archivo de configuración
    logger.info("\n4. Creando archivo de configuración...")
    config_file = Path(__file__).parent / "db_config.py"
    with open(config_file, 'w') as f:
        f.write(f'''"""
Configuración de ubicación de base de datos.

Este archivo se genera automáticamente por fix_database_location.py
Para cambiar la ubicación, edita DB_PATH abajo o ejecuta fix_database_location.py nuevamente.
"""

from pathlib import Path

# Ubicación de la base de datos (fuera de Google Drive)
DB_PATH = Path(r"{LOCAL_DB_PATH}")
''')
    logger.info(f"   ✓ Configuración guardada en: {config_file}")
    
    # 5. Actualizar db_schema.py para usar la nueva ubicación
    logger.info("\n5. Actualizando db_schema.py...")
    update_db_schema()
    
    logger.info("\n" + "=" * 60)
    logger.info("✓ COMPLETADO")
    logger.info("=" * 60)
    logger.info(f"\nLa base de datos ahora está en: {LOCAL_DB_PATH}")
    logger.info("\nPara usar esta ubicación, el código debe importar desde db_config:")
    logger.info("  from db_config import DB_PATH")
    logger.info("\nO puedes modificar db_schema.py directamente para usar:")
    logger.info(f"  DEFAULT_DB_PATH = Path(r\"{LOCAL_DB_PATH}\")")


def create_new_database():
    """Crea una nueva base de datos vacía."""
    try:
        from db_schema import create_database_schema
        create_database_schema(LOCAL_DB_PATH)
        logger.info(f"   ✓ Nueva base de datos creada en: {LOCAL_DB_PATH}")
    except Exception as e:
        logger.error(f"   ✗ Error creando nueva base de datos: {e}")
        raise


def update_db_schema():
    """Actualiza db_schema.py para usar la nueva ubicación si es posible."""
    db_schema_path = Path(__file__).parent / "db_schema.py"
    try:
        content = db_schema_path.read_text(encoding='utf-8')
        
        # Buscar la línea con DEFAULT_DB_PATH
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'DEFAULT_DB_PATH =' in line and 'Path(__file__)' in line:
                # Comentar la línea antigua y agregar nueva
                lines[i] = f"# DEFAULT_DB_PATH = Path(__file__).parent / \"flute_analysis.db\"  # Original (puede estar en Google Drive)"
                lines.insert(i + 1, f"# Usar ubicación local fuera de Google Drive:")
                lines.insert(i + 2, f"try:")
                lines.insert(i + 3, f"    from db_config import DB_PATH as DEFAULT_DB_PATH")
                lines.insert(i + 4, f"except ImportError:")
                lines.insert(i + 5, f"    # Fallback a ubicación original si no existe db_config")
                lines.insert(i + 6, f"    DEFAULT_DB_PATH = Path(__file__).parent / \"flute_analysis.db\"")
                break
        
        db_schema_path.write_text('\n'.join(lines), encoding='utf-8')
        logger.info("   ✓ db_schema.py actualizado para usar db_config.py")
    except Exception as e:
        logger.warning(f"   ⚠ No se pudo actualizar db_schema.py automáticamente: {e}")
        logger.info("   → Puedes actualizarlo manualmente para importar desde db_config")


if __name__ == "__main__":
    try:
        move_database()
    except KeyboardInterrupt:
        logger.info("\n\nOperación cancelada por el usuario.")
    except Exception as e:
        logger.error(f"\n\nError: {e}", exc_info=True)
        raise

