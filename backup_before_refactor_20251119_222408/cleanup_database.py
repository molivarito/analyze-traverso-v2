"""
Script para limpiar la base de datos eliminando datos innecesarios.
"""

import sqlite3
from pathlib import Path
from db_schema import DEFAULT_DB_PATH
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_pressure_flow_data(db_path: Path, backup: bool = True):
    """
    Elimina todos los datos de pressure_flow_data de la BD.
    
    Args:
        db_path: Ruta a la base de datos.
        backup: Si True, crea un backup antes de limpiar.
    """
    if backup:
        backup_path = db_path.with_suffix('.db.backup')
        logger.info(f"Creando backup en: {backup_path}")
        import shutil
        shutil.copy2(db_path, backup_path)
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Contar registros antes
        cursor.execute("SELECT COUNT(*) FROM impedance_results WHERE pressure_flow_data_json IS NOT NULL")
        count_before = cursor.fetchone()[0]
        logger.info(f"Registros con pressure_flow_data: {count_before}")
        
        # Calcular tamaño antes
        cursor.execute("""
            SELECT SUM(LENGTH(pressure_flow_data_json)) 
            FROM impedance_results 
            WHERE pressure_flow_data_json IS NOT NULL
        """)
        size_before_mb = (cursor.fetchone()[0] or 0) / (1024 * 1024)
        logger.info(f"Tamaño de pressure_flow_data: {size_before_mb:.2f} MB")
        
        # Eliminar pressure_flow_data
        cursor.execute("""
            UPDATE impedance_results 
            SET pressure_flow_data_json = NULL 
            WHERE pressure_flow_data_json IS NOT NULL
        """)
        
        conn.commit()
        logger.info(f"✓ Eliminados {count_before} registros de pressure_flow_data")
        logger.info(f"✓ Espacio liberado: ~{size_before_mb:.2f} MB")
        
        # Vacuum para recuperar espacio
        logger.info("Ejecutando VACUUM para optimizar BD...")
        cursor.execute("VACUUM")
        conn.commit()
        logger.info("✓ VACUUM completado")
        
    except Exception as e:
        logger.error(f"Error limpiando BD: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def get_database_size(db_path: Path) -> dict:
    """Obtiene estadísticas de tamaño de la BD."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    stats = {}
    
    # Tamaño total
    stats['total_size_mb'] = db_path.stat().st_size / (1024 * 1024)
    
    # Tamaño por tabla
    tables = [
        'flutes', 'flute_geometry', 'impedance_calculation_params',
        'bore_geometry', 'side_holes', 'impedance_results',
        'external_geometry', 'external_geometry_parameters'
    ]
    
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            
            # Para impedance_results, calcular tamaño de pressure_flow_data
            if table == 'impedance_results':
                cursor.execute("""
                    SELECT SUM(LENGTH(pressure_flow_data_json)) 
                    FROM impedance_results 
                    WHERE pressure_flow_data_json IS NOT NULL
                """)
                pf_size = (cursor.fetchone()[0] or 0) / (1024 * 1024)
                stats[f'{table}_pressure_flow_mb'] = pf_size
                
                # Tamaño total de la tabla
                cursor.execute("""
                    SELECT SUM(
                        LENGTH(frequencies_json) + 
                        LENGTH(impedance_real_json) + 
                        LENGTH(impedance_imag_json) +
                        COALESCE(LENGTH(antiresonance_freqs_json), 0) +
                        COALESCE(LENGTH(pressure_flow_data_json), 0)
                    )
                    FROM impedance_results
                """)
                total_size = (cursor.fetchone()[0] or 0) / (1024 * 1024)
                stats[f'{table}_total_mb'] = total_size
            
            stats[f'{table}_count'] = count
        except Exception as e:
            logger.debug(f"Error obteniendo stats de {table}: {e}")
    
    conn.close()
    return stats


def main():
    """Función principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Limpia la base de datos")
    parser.add_argument(
        '--db-path',
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Ruta a la base de datos"
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help="No crear backup antes de limpiar"
    )
    parser.add_argument(
        '--stats-only',
        action='store_true',
        help="Solo mostrar estadísticas, no limpiar"
    )
    
    args = parser.parse_args()
    
    if not args.db_path.exists():
        logger.error(f"Base de datos no existe: {args.db_path}")
        return
    
    # Mostrar estadísticas
    logger.info("=" * 60)
    logger.info("ESTADÍSTICAS DE BASE DE DATOS")
    logger.info("=" * 60)
    stats = get_database_size(args.db_path)
    
    logger.info(f"Tamaño total: {stats['total_size_mb']:.2f} MB ({stats['total_size_mb']/1024:.2f} GB)")
    
    if 'impedance_results_pressure_flow_mb' in stats:
        pf_size = stats['impedance_results_pressure_flow_mb']
        logger.info(f"Tamaño de pressure_flow_data: {pf_size:.2f} MB")
        if stats['total_size_mb'] > 0:
            logger.info(f"  (% del total: {pf_size/stats['total_size_mb']*100:.1f}%)")
    
    if 'impedance_results_total_mb' in stats:
        logger.info(f"Tamaño total de impedance_results: {stats['impedance_results_total_mb']:.2f} MB")
    
    logger.info(f"\nRegistros en BD:")
    for key, value in stats.items():
        if key.endswith('_count'):
            table_name = key.replace('_count', '')
            logger.info(f"  {table_name}: {value}")
    
    if args.stats_only:
        return
    
    # Confirmar limpieza
    print("\n" + "=" * 60)
    reply = input("¿Eliminar todos los datos de pressure_flow_data? (s/N): ")
    if reply.lower() != 's':
        logger.info("Operación cancelada")
        return
    
    # Limpiar
    cleanup_pressure_flow_data(args.db_path, backup=not args.no_backup)
    
    # Estadísticas después
    logger.info("\n" + "=" * 60)
    logger.info("ESTADÍSTICAS DESPUÉS DE LIMPIEZA")
    logger.info("=" * 60)
    stats_after = get_database_size(args.db_path)
    logger.info(f"Tamaño total: {stats_after['total_size_mb']:.2f} MB ({stats_after['total_size_mb']/1024:.2f} GB)")
    logger.info(f"Espacio liberado: {stats['total_size_mb'] - stats_after['total_size_mb']:.2f} MB")


if __name__ == "__main__":
    main()

