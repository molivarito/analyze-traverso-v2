#!/usr/bin/env python
"""
Script para actualizar el LaTeX reemplazando screenshots sintéticos por reales.
"""

import re

TEX_FILE = "presentation_software_features.tex"

# Mapeo de nombres sintéticos a nombres reales
replacements = {
    "screenshot_resonance_frequencies.png": "real_resonance_frequencies.png",
    "screenshot_inharmonicity.png": "real_inharmonicity.png",
    "screenshot_moc.png": "real_moc.png",
    "screenshot_bi_espe.png": "real_bi_espe.png",
    "screenshot_qfactor.png": "real_qfactor.png",
    "screenshot_harmonic_ratios.png": "real_harmonic_ratios.png",
    "screenshot_peak_heights.png": "real_peak_heights.png",
    "screenshot_admittance.png": "real_admittance.png",
    "screenshot_multi_flute_comparison.png": "real_multi_flute_comparison.png"
}

def update_latex():
    """Actualiza el archivo LaTeX con los nombres de screenshots reales."""
    
    print(f"Leyendo {TEX_FILE}...")
    with open(TEX_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Realizar reemplazos
    for old_name, new_name in replacements.items():
        if old_name in content:
            content = content.replace(old_name, new_name)
            print(f"  Reemplazado: {old_name} -> {new_name}")
    
    if content != original_content:
        # Guardar backup
        backup_file = TEX_FILE + ".backup"
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(original_content)
        print(f"\nBackup guardado en: {backup_file}")
        
        # Guardar archivo actualizado
        with open(TEX_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Archivo actualizado: {TEX_FILE}")
        
        # Recompilar
        print("\nRecompilando presentación...")
        import subprocess
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", TEX_FILE],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("✓ PDF recompilado exitosamente")
        else:
            print("✗ Error al recompilar PDF")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
    else:
        print("\nNo se encontraron cambios necesarios")

if __name__ == "__main__":
    update_latex()
