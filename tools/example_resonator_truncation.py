"""
Script de ejemplo para demostrar el uso del análisis de resonador truncado.

Este script muestra cómo usar ResonatorTruncationAnalyzer para analizar
la respuesta acústica del resonador de una flauta sin agujeros.
"""

import logging
from pathlib import Path
from flute_data import FluteData
from resonator_truncation_analysis import ResonatorTruncationAnalyzer

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Ejemplo de uso del análisis de resonador truncado."""
    
    # Ejemplo: cargar una flauta desde un directorio
    # Ajusta esta ruta según tu estructura de datos
    flute_dir = Path("../data_json") / "Deppe"  # Cambiar según tu caso
    
    if not flute_dir.exists():
        logger.warning(f"Directorio de flauta no encontrado: {flute_dir}")
        logger.info("Por favor, ajusta la ruta 'flute_dir' en el script para apuntar a tus datos.")
        return
    
    try:
        # Cargar datos de la flauta (sin análisis acústico inicial para ahorrar tiempo)
        logger.info("Cargando datos de la flauta...")
        flute_data = FluteData(
            source=str(flute_dir),
            skip_acoustic_analysis=True  # No calcular análisis acústico completo
        )
        
        if flute_data.validation_errors:
            logger.error(f"Errores de validación: {flute_data.validation_errors}")
            return
        
        logger.info(f"Flauta cargada: {flute_data.flute_model}")
        
        # Crear analizador de resonador truncado
        logger.info("Creando analizador de resonador truncado...")
        analyzer = ResonatorTruncationAnalyzer(
            flute_data=flute_data,
            truncation_percentages=None,  # Usar valores por defecto (100%, 95%, ..., 20%)
            temperature=20.0,
            include_embouchure=True
        )
        
        # Ejecutar análisis
        logger.info("Ejecutando análisis...")
        results = analyzer.analyze()
        
        logger.info(f"Análisis completado. {len(results)} secciones analizadas.")
        
        # Mostrar resumen de resultados
        print("\n=== Resumen de Resultados ===")
        for percentage in sorted(results.keys(), reverse=True):
            result = results[percentage]
            f0 = result.get('f0')
            length_mm = result.get('length_mm', 0)
            if f0:
                print(f"{percentage:3.0f}% ({length_mm:6.2f}mm): f0 = {f0:6.1f} Hz")
        
        # Generar visualizaciones
        logger.info("Generando visualizaciones...")
        
        # Gráfico de frecuencias de resonancia
        fig1 = analyzer.plot_resonance_frequencies_vs_length()
        fig1.savefig("resonator_truncation_frequencies.png", dpi=150, bbox_inches='tight')
        logger.info("Gráfico guardado: resonator_truncation_frequencies.png")
        
        # Gráfico de inharmonicidad
        fig2 = analyzer.plot_inharmonicity_vs_length()
        fig2.savefig("resonator_truncation_inharmonicity.png", dpi=150, bbox_inches='tight')
        logger.info("Gráfico guardado: resonator_truncation_inharmonicity.png")
        
        # Gráfico de relaciones armónicas
        fig3 = analyzer.plot_harmonic_ratios_vs_length()
        fig3.savefig("resonator_truncation_harmonic_ratios.png", dpi=150, bbox_inches='tight')
        logger.info("Gráfico guardado: resonator_truncation_harmonic_ratios.png")
        
        # Curvas de impedancia superpuestas
        fig4 = analyzer.plot_impedance_curves_overlay()
        fig4.savefig("resonator_truncation_impedance_overlay.png", dpi=150, bbox_inches='tight')
        logger.info("Gráfico guardado: resonator_truncation_impedance_overlay.png")
        
        # Gráfico 3D
        fig5 = analyzer.plot_3d_frequency_length_amplitude()
        fig5.savefig("resonator_truncation_3d.png", dpi=150, bbox_inches='tight')
        logger.info("Gráfico guardado: resonator_truncation_3d.png")
        
        # Generar reporte PDF completo
        logger.info("Generando reporte PDF...")
        analyzer.generate_summary_report("resonator_truncation_report.pdf")
        logger.info("Reporte guardado: resonator_truncation_report.pdf")
        
        logger.info("¡Análisis completado exitosamente!")
        
    except Exception as e:
        logger.error(f"Error durante el análisis: {e}", exc_info=True)


if __name__ == "__main__":
    main()

