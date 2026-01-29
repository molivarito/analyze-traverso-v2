"""
Script para migrar el esquema de la base de datos y agregar tablas de sensibilidad.

Este script actualiza la base de datos existente agregando las nuevas tablas
necesarias para el análisis de sensibilidad sin afectar los datos existentes.
"""
from db_schema import create_database_schema, DEFAULT_DB_PATH
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Migrando esquema de base de datos para agregar tablas de sensibilidad...")
    try:
        db_path = create_database_schema(DEFAULT_DB_PATH)
        logger.info(f"✓ Esquema migrado exitosamente: {db_path}")
        logger.info("✓ Tablas agregadas:")
        logger.info("  - sensitivity_analysis_runs")
        logger.info("  - sensitivity_variants")
        logger.info("✓ Índices creados para optimizar consultas")
    except Exception as e:
        logger.error(f"✗ Error durante la migración: {e}")
        raise

