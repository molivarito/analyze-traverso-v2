"""
Script para poblar la base de datos de flautas de forma controlada.

Este script permite:
1. Poblar la BD con flautas específicas
2. Controlar qué flautas se procesan
3. Monitorear el progreso
4. Evitar que la BD crezca demasiado
5. Generar reporte detallado de estado de cada flauta
"""

import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging
from collections import defaultdict

from flute_data_db import FluteDataDB
from constants import FLUTE_PARTS_ORDER

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Directorio por defecto de datos JSON
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_JSON_DIR = SCRIPT_DIR.parent / "data_json"


def find_flute_directories(data_dir: Path) -> List[Path]:
    """
    Encuentra todos los directorios de flautas en el directorio de datos.
    
    Args:
        data_dir: Directorio raíz donde están las flautas.
    
    Returns:
        Lista de directorios de flautas.
    """
    flute_dirs = []
    if not data_dir.exists():
        logger.error(f"Directorio no existe: {data_dir}")
        return flute_dirs
    
    for item in data_dir.iterdir():
        if item.is_dir():
            # Verificar que tenga al menos un archivo JSON de parte
            has_json = any(f.name.endswith('.json') for f in item.iterdir())
            if has_json:
                flute_dirs.append(item)
    
    return sorted(flute_dirs)


def check_flute_files(flute_dir: Path) -> Dict[str, Any]:
    """
    Verifica qué archivos existen para una flauta.
    
    Args:
        flute_dir: Directorio de la flauta.
    
    Returns:
        Diccionario con información de archivos encontrados.
    """
    files_info = {
        'internal_files': {},
        'external_files': {},
        'missing_internal': [],
        'missing_external': []
    }
    
    for part in FLUTE_PARTS_ORDER:
        internal_file = flute_dir / f"{part}.json"
        external_file = flute_dir / f"{part}_external.json"
        
        if internal_file.exists():
            files_info['internal_files'][part] = str(internal_file)
        else:
            files_info['missing_internal'].append(part)
        
        if external_file.exists():
            files_info['external_files'][part] = str(external_file)
        else:
            files_info['missing_external'].append(part)
    
    return files_info


def analyze_flute_status(flute_data: FluteDataDB, files_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analiza el estado completo de una flauta.
    
    Args:
        flute_data: Objeto FluteDataDB de la flauta.
        files_info: Información de archivos encontrados.
    
    Returns:
        Diccionario con análisis completo de la flauta.
    """
    status = {
        'flute_name': flute_data.flute_model,
        'flute_id': getattr(flute_data, '_flute_db_id', None),
        'has_errors': bool(flute_data.validation_errors),
        'has_warnings': bool(flute_data.validation_warnings),
        'errors': flute_data.validation_errors or [],
        'warnings': flute_data.validation_warnings or [],
        'notes_calculated': len(flute_data.acoustic_analysis) if flute_data.acoustic_analysis else 0,
        'parts_status': {},
        'external_geometry_status': {},
        'missing_parts': [],
        'data_consistency': []
    }
    
    # Analizar estado de cada parte
    for part in FLUTE_PARTS_ORDER:
        part_status = {
            'has_internal': part in files_info['internal_files'],
            'has_external_file': part in files_info['external_files'],
            'has_external_geometry': False,
            'external_source': None,
            'has_data': part in flute_data.data
        }
        
        # Verificar geometría externa
        if hasattr(flute_data, 'external_geometry') and flute_data.external_geometry:
            if part in flute_data.external_geometry:
                part_status['has_external_geometry'] = True
                # Intentar determinar la fuente (medida vs paramétrica)
                if part_status['has_external_file']:
                    part_status['external_source'] = 'measured'
                else:
                    part_status['external_source'] = 'parametric'
        
        status['parts_status'][part] = part_status
        
        # Verificar si falta la parte
        if not part_status['has_data']:
            status['missing_parts'].append(part)
    
    # Verificar inconsistencias
    # 1. Partes sin datos internos
    for part in status['missing_parts']:
        status['data_consistency'].append(f"Parte '{part}' no tiene datos internos")
    
    # 2. Partes sin geometría externa
    for part, part_status in status['parts_status'].items():
        if part_status['has_data'] and not part_status['has_external_geometry']:
            status['data_consistency'].append(
                f"Parte '{part}' tiene datos pero no tiene geometría externa (ni medida ni paramétrica)"
            )
    
    # 3. Archivos externos sin usar (si hay geometría paramétrica)
    for part in files_info['external_files']:
        part_status = status['parts_status'].get(part, {})
        if part_status.get('external_source') == 'parametric':
            status['data_consistency'].append(
                f"Parte '{part}' tiene archivo externo pero se está usando geometría paramétrica"
            )
    
    return status


def populate_flute(
    flute_dir: Path,
    temperature: float = 20.0,
    la_frequency: float = 415.0,
    force_recalculate: bool = False,
    generate_report: bool = True
) -> tuple[bool, Optional[Dict[str, Any]]]:
    """
    Pobla la base de datos con una flauta específica.
    
    Args:
        flute_dir: Directorio de la flauta.
        temperature: Temperatura en Celsius.
        la_frequency: Frecuencia del La (diapason) en Hz.
        force_recalculate: Si True, fuerza recálculo incluso si existe en BD.
        generate_report: Si True, genera reporte detallado.
    
    Returns:
        Tupla (success, report_dict) donde success es True si se procesó exitosamente,
        y report_dict contiene el análisis detallado si generate_report es True.
    """
    report = None
    
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"Procesando: {flute_dir.name}")
        logger.info(f"{'='*60}")
        
        # Verificar archivos antes de cargar
        files_info = check_flute_files(flute_dir)
        
        # Crear FluteDataDB (esto calculará y guardará en BD automáticamente)
        flute_data = FluteDataDB(
            str(flute_dir),
            temperature=temperature,
            la_frequency=la_frequency,
            force_recalculate=force_recalculate
        )
        
        success = not bool(flute_data.validation_errors)
        
        if generate_report:
            report = analyze_flute_status(flute_data, files_info)
            report['success'] = success
            report['files_info'] = files_info
        
        if flute_data.validation_errors:
            logger.error(f"Errores de validación en {flute_dir.name}:")
            for error in flute_data.validation_errors:
                logger.error(f"  - {error.get('message', 'Error desconocido')}")
            return False, report
        
        if flute_data.validation_warnings:
            logger.warning(f"Advertencias en {flute_dir.name}:")
            for warning in flute_data.validation_warnings:
                logger.warning(f"  - {warning.get('message', 'Advertencia desconocida')}")
        
        logger.info(f"✓ {flute_dir.name} procesada exitosamente")
        logger.info(f"  - Notas calculadas: {len(flute_data.acoustic_analysis) if flute_data.acoustic_analysis else 0}")
        
        return True, report
        
    except Exception as e:
        logger.error(f"Error procesando {flute_dir.name}: {e}", exc_info=True)
        if generate_report:
            report = {
                'flute_name': flute_dir.name,
                'success': False,
                'error': str(e),
                'files_info': check_flute_files(flute_dir)
            }
        return False, report


def generate_detailed_report(
    reports: List[Dict[str, Any]],
    output_file: Optional[Path] = None
) -> str:
    """
    Genera un reporte detallado en texto.
    
    Args:
        reports: Lista de reportes de flautas.
        output_file: Archivo donde guardar el reporte (opcional).
    
    Returns:
        String con el reporte completo.
    """
    lines = []
    lines.append("=" * 80)
    lines.append("REPORTE DETALLADO DE FLAUTAS EN BASE DE DATOS")
    lines.append("=" * 80)
    lines.append("")
    
    # Resumen general
    total = len(reports)
    successful = sum(1 for r in reports if r.get('success', False))
    failed = total - successful
    
    lines.append("RESUMEN GENERAL")
    lines.append("-" * 80)
    lines.append(f"Total de flautas procesadas: {total}")
    lines.append(f"  ✓ Exitosas: {successful}")
    lines.append(f"  ✗ Fallidas: {failed}")
    lines.append("")
    
    # Estadísticas
    flutes_with_errors = sum(1 for r in reports if r.get('has_errors', False))
    flutes_with_warnings = sum(1 for r in reports if r.get('has_warnings', False))
    flutes_missing_external = sum(
        1 for r in reports 
        if r.get('external_geometry_status') and 
        any(not status.get('has_external_geometry', False) 
            for status in r.get('parts_status', {}).values())
    )
    
    lines.append("ESTADÍSTICAS")
    lines.append("-" * 80)
    lines.append(f"Flautas con errores: {flutes_with_errors}")
    lines.append(f"Flautas con advertencias: {flutes_with_warnings}")
    lines.append(f"Flautas con geometría externa faltante: {flutes_missing_external}")
    lines.append("")
    
    # Detalle por flauta
    lines.append("=" * 80)
    lines.append("DETALLE POR FLAUTA")
    lines.append("=" * 80)
    lines.append("")
    
    for i, report in enumerate(reports, 1):
        flute_name = report.get('flute_name', 'Desconocida')
        success = report.get('success', False)
        flute_id = report.get('flute_id')
        
        lines.append(f"\n[{i}/{total}] {flute_name}")
        lines.append("-" * 80)
        
        # Estado general
        status_icon = "✓" if success else "✗"
        lines.append(f"Estado: {status_icon} {'Cargada exitosamente' if success else 'Error al cargar'}")
        if flute_id:
            lines.append(f"ID en BD: {flute_id}")
        
        # Errores
        if report.get('has_errors'):
            lines.append("\n❌ ERRORES:")
            for error in report.get('errors', []):
                error_msg = error.get('message', 'Error desconocido')
                error_part = error.get('part', '')
                if error_part:
                    lines.append(f"  • {error_part}: {error_msg}")
                else:
                    lines.append(f"  • {error_msg}")
        
        # Advertencias
        if report.get('has_warnings'):
            lines.append("\n⚠️  ADVERTENCIAS:")
            for warning in report.get('warnings', []):
                warning_msg = warning.get('message', 'Advertencia desconocida')
                warning_part = warning.get('part', '')
                if warning_part:
                    lines.append(f"  • {warning_part}: {warning_msg}")
                else:
                    lines.append(f"  • {warning_msg}")
        
        # Notas calculadas
        notes_count = report.get('notes_calculated', 0)
        lines.append(f"\n📊 Notas calculadas: {notes_count}")
        
        # Estado de partes
        parts_status = report.get('parts_status', {})
        if parts_status:
            lines.append("\n📦 ESTADO DE PARTES:")
            for part, status in parts_status.items():
                part_lines = [f"  {part}:"]
                
                # Archivos
                if status.get('has_internal'):
                    part_lines.append("    ✓ Archivo interno")
                else:
                    part_lines.append("    ✗ Archivo interno faltante")
                
                if status.get('has_external_file'):
                    part_lines.append("    ✓ Archivo externo (medido)")
                else:
                    part_lines.append("    ✗ Archivo externo faltante")
                
                # Geometría externa
                if status.get('has_external_geometry'):
                    source = status.get('external_source', 'unknown')
                    if source == 'measured':
                        part_lines.append("    ✓ Geometría externa: MEDIDA")
                    elif source == 'parametric':
                        part_lines.append("    ⚠ Geometría externa: PARAMÉTRICA (generada)")
                    else:
                        part_lines.append("    ✓ Geometría externa: disponible")
                else:
                    part_lines.append("    ✗ Geometría externa: NO DISPONIBLE")
                
                lines.append(" ".join(part_lines))
        
        # Partes faltantes
        missing_parts = report.get('missing_parts', [])
        if missing_parts:
            lines.append(f"\n⚠️  Partes faltantes: {', '.join(missing_parts)}")
        
        # Inconsistencias
        inconsistencies = report.get('data_consistency', [])
        if inconsistencies:
            lines.append("\n⚠️  INCONSISTENCIAS EN DATOS:")
            for inc in inconsistencies:
                lines.append(f"  • {inc}")
        
        # Archivos encontrados
        files_info = report.get('files_info', {})
        if files_info:
            missing_int = files_info.get('missing_internal', [])
            missing_ext = files_info.get('missing_external', [])
            if missing_int or missing_ext:
                lines.append("\n📁 ARCHIVOS FALTANTES:")
                if missing_int:
                    lines.append(f"  • Internos: {', '.join(missing_int)}")
                if missing_ext:
                    lines.append(f"  • Externos: {', '.join(missing_ext)}")
        
        lines.append("")
    
    # Resumen de problemas comunes
    lines.append("=" * 80)
    lines.append("RESUMEN DE PROBLEMAS COMUNES")
    lines.append("=" * 80)
    lines.append("")
    
    # Flautas sin geometría externa medida
    flutes_no_external = [
        r['flute_name'] for r in reports
        if r.get('success') and 
        all(not status.get('has_external_file', False) 
            for status in r.get('parts_status', {}).values())
    ]
    if flutes_no_external:
        lines.append(f"Flautas sin archivos externos medidos ({len(flutes_no_external)}):")
        for name in flutes_no_external[:10]:  # Mostrar máximo 10
            lines.append(f"  • {name}")
        if len(flutes_no_external) > 10:
            lines.append(f"  ... y {len(flutes_no_external) - 10} más")
        lines.append("")
    
    # Flautas con geometría paramétrica
    flutes_parametric = [
        r['flute_name'] for r in reports
        if r.get('success') and 
        any(status.get('external_source') == 'parametric' 
            for status in r.get('parts_status', {}).values())
    ]
    if flutes_parametric:
        lines.append(f"Flautas usando geometría paramétrica ({len(flutes_parametric)}):")
        for name in flutes_parametric[:10]:
            lines.append(f"  • {name}")
        if len(flutes_parametric) > 10:
            lines.append(f"  ... y {len(flutes_parametric) - 10} más")
        lines.append("")
    
    report_text = "\n".join(lines)
    
    # Guardar en archivo si se especificó
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        logger.info(f"\nReporte guardado en: {output_file}")
    
    return report_text


def populate_database(
    data_dir: Optional[Path] = None,
    flute_names: Optional[List[str]] = None,
    temperature: float = 20.0,
    la_frequency: float = 415.0,
    force_recalculate: bool = False,
    generate_report: bool = True,
    report_file: Optional[Path] = None
) -> None:
    """
    Pobla la base de datos con flautas.
    
    Args:
        data_dir: Directorio de datos JSON. Si es None, usa el por defecto.
        flute_names: Lista de nombres de flautas a procesar. Si es None, procesa todas.
        temperature: Temperatura en Celsius.
        la_frequency: Frecuencia del La (diapason) en Hz.
        force_recalculate: Si True, fuerza recálculo incluso si existe en BD.
        generate_report: Si True, genera reporte detallado.
        report_file: Archivo donde guardar el reporte (opcional).
    """
    if data_dir is None:
        data_dir = DEFAULT_DATA_JSON_DIR
    
    data_dir = Path(data_dir)
    if not data_dir.exists():
        logger.error(f"Directorio no existe: {data_dir}")
        return
    
    logger.info(f"Buscando flautas en: {data_dir}")
    
    # Encontrar directorios de flautas
    all_flute_dirs = find_flute_directories(data_dir)
    
    if not all_flute_dirs:
        logger.warning("No se encontraron flautas")
        return
    
    logger.info(f"Encontradas {len(all_flute_dirs)} flautas")
    
    # Filtrar por nombres si se especificaron
    if flute_names:
        flute_dirs = [d for d in all_flute_dirs if d.name in flute_names]
        if len(flute_dirs) < len(flute_names):
            not_found = set(flute_names) - {d.name for d in flute_dirs}
            logger.warning(f"Flautas no encontradas: {not_found}")
    else:
        flute_dirs = all_flute_dirs
    
    if not flute_dirs:
        logger.warning("No hay flautas para procesar")
        return
    
    logger.info(f"\nProcesando {len(flute_dirs)} flauta(s)...")
    logger.info(f"Parámetros: temp={temperature}°C, la={la_frequency}Hz")
    
    # Procesar cada flauta
    successful = 0
    failed = 0
    reports = []
    
    for i, flute_dir in enumerate(flute_dirs, 1):
        logger.info(f"\n[{i}/{len(flute_dirs)}] {flute_dir.name}")
        
        success, report = populate_flute(
            flute_dir, 
            temperature, 
            la_frequency, 
            force_recalculate,
            generate_report=generate_report
        )
        
        if success:
            successful += 1
        else:
            failed += 1
        
        if report:
            reports.append(report)
    
    # Resumen básico
    logger.info("\n" + "="*60)
    logger.info("RESUMEN")
    logger.info("="*60)
    logger.info(f"Exitosas: {successful}")
    logger.info(f"Fallidas: {failed}")
    logger.info(f"Total: {len(flute_dirs)}")
    
    # Verificar tamaño de BD
    from db_schema import DEFAULT_DB_PATH
    db_path = Path(DEFAULT_DB_PATH)
    if db_path.exists():
        db_size_mb = db_path.stat().st_size / (1024 * 1024)
        logger.info(f"\nTamaño de BD: {db_size_mb:.2f} MB ({db_size_mb/1024:.2f} GB)")
    
    # Generar reporte detallado
    if generate_report and reports:
        logger.info("\n" + "="*60)
        logger.info("GENERANDO REPORTE DETALLADO...")
        logger.info("="*60)
        
        report_text = generate_detailed_report(reports, report_file)
        
        # Mostrar resumen del reporte en consola
        print("\n" + "="*80)
        print("REPORTE DETALLADO")
        print("="*80)
        print(report_text[:2000])  # Mostrar primeros 2000 caracteres
        if len(report_text) > 2000:
            print("\n... (reporte completo guardado en archivo)")


def main():
    """Función principal con interfaz de línea de comandos."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Pobla la base de datos de flautas de forma controlada"
    )
    parser.add_argument(
        '--data-dir',
        type=Path,
        default=DEFAULT_DATA_JSON_DIR,
        help=f"Directorio de datos JSON (default: {DEFAULT_DATA_JSON_DIR})"
    )
    parser.add_argument(
        '--flutes',
        nargs='+',
        help="Nombres específicos de flautas a procesar (opcional)"
    )
    parser.add_argument(
        '--temperature',
        type=float,
        default=20.0,
        help="Temperatura en Celsius (default: 20.0)"
    )
    parser.add_argument(
        '--la-frequency',
        type=float,
        default=415.0,
        help="Frecuencia del La en Hz (default: 415.0)"
    )
    parser.add_argument(
        '--force-recalculate',
        action='store_true',
        help="Fuerza recálculo incluso si existe en BD"
    )
    parser.add_argument(
        '--no-report',
        action='store_true',
        help="No genera reporte detallado"
    )
    parser.add_argument(
        '--report-file',
        type=Path,
        help="Archivo donde guardar el reporte detallado (default: reporte_flautas.txt)"
    )
    
    args = parser.parse_args()
    
    # Determinar archivo de reporte
    report_file = args.report_file
    if report_file is None and not args.no_report:
        report_file = Path("reporte_flautas.txt")
    
    populate_database(
        data_dir=args.data_dir,
        flute_names=args.flutes,
        temperature=args.temperature,
        la_frequency=args.la_frequency,
        force_recalculate=args.force_recalculate,
        generate_report=not args.no_report,
        report_file=report_file
    )


if __name__ == "__main__":
    main()