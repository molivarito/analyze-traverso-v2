#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para generar screenshots REALES desde la base de datos.
Usa las flautas Deppe y Freyer.
"""

import os
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from flute_data_db import FluteDataDB
from analysis_module import FluteAnalyzer
from flute_operations import FluteOperations

OUTPUT_DIR = "presentation_screenshots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

plt.style.use('seaborn-v0_8-darkgrid')

print(f"\n{'='*70}")
print("GENERANDO SCREENSHOTS REALES DESDE BASE DE DATOS")
print(f"{'='*70}\n")

# Cargar flautas desde BD
print("Cargando flautas desde base de datos...")
flute_deppe = FluteDataDB("Deppe")
flute_freyer = FluteDataDB("Freyer")

# Crear lista para analyzer (requiere lista)
flute_list = [flute_deppe]
analyzer = FluteAnalyzer(flute_list)

# Usar la primera flauta para los gráficos individuales
flute_data = flute_deppe
operations = FluteOperations(flute_data)

notes = flute_data.notes
print(f"Notas disponibles en Deppe: {len(notes)}")
display_notes = notes[:18] if len(notes) >= 18 else notes
print(f"Usando las primeras {len(display_notes)} notas para los gráficos\n")

# ==============================================================================
# 1. FRECUENCIAS DE RESONANCIA
# ==============================================================================
print("1. Generando gráfico de frecuencias de resonancia...")
try:
    fig, ax = plt.subplots(figsize=(10, 5))
    
    f0_vals, f1_vals, f2_vals, note_labels = [], [], [], []
    
    for note in display_notes:
        try:
            # Usar el analyzer para obtener métricas
            results = analyzer.analyze_single_note(note, flute_data.flute_model)
            if results and 'resonance_frequencies' in results:
                freqs = results['resonance_frequencies']
                if len(freqs) >= 3:
                    f0_vals.append(freqs[0])
                    f1_vals.append(freqs[1])
                    f2_vals.append(freqs[2])
                    note_labels.append(note)
        except Exception as e:
            print(f"   Error en nota {note}: {e}")
            continue
    
    x = np.arange(len(note_labels))
    ax.plot(x, f0_vals, 'o-', label='f₀', linewidth=2, markersize=5, color='#3498DB')
    ax.plot(x, f1_vals, 's-', label='f₁', linewidth=2, markersize=5, color='#E74C3C')
    ax.plot(x, f2_vals, '^-', label='f₂', linewidth=2, markersize=5, color='#2ECC71')
    
    ax.set_xlabel('Musical Note', fontsize=10)
    ax.set_ylabel('Frequency (Hz)', fontsize=10)
    ax.set_title('Resonance Frequencies - Deppe', fontsize=11, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(note_labels, rotation=45, ha='right', fontsize=8)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'real_resonance_frequencies.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("   ✓ real_resonance_frequencies.png")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

# ==============================================================================
# 2. INHARMONICIDAD
# ==============================================================================
print("2. Generando gráfico de inharmonicidad...")
try:
    fig, ax = plt.subplots(figsize=(10, 5))
    
    inharm_vals = []
    for note in note_labels:
        results = analyzer.analyze_single_note(note, flute_data.flute_model)
        inharm_vals.append(results.get('inharmonicity', 0) if results else 0)
    
    ax.plot(x, inharm_vals, 'o-', color='#E74C3C', linewidth=2, markersize=5)
    ax.axhline(y=0, color='k', linestyle='--', alpha=0.6, linewidth=1.5)
    ax.fill_between(x, -10, 10, alpha=0.1, color='green')
    
    ax.set_xlabel('Musical Note', fontsize=10)
    ax.set_ylabel('Inharmonicity (cents)', fontsize=10)
    ax.set_title('Inharmonicity - Deppe', fontsize=11, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(note_labels, rotation=45, ha='right', fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'real_inharmonicity.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("   ✓ real_inharmonicity.png")
except Exception as e:
    print(f"   ✗ Error: {e}")

# ==============================================================================
# 3. MOC
# ==============================================================================
print("3. Generando gráfico de MOC...")
try:
    fig, ax = plt.subplots(figsize=(10, 5))
    
    moc_vals = []
    for note in note_labels:
        results = analyzer.analyze_single_note(note, flute_data.flute_model)
        moc_vals.append(results.get('moc', 1.0) if results else 1.0)
    
    ax.plot(x, moc_vals, 'o-', color='#9B59B6', linewidth=2, markersize=5)
    ax.axhline(y=1.0, color='k', linestyle='--', alpha=0.6, linewidth=1.5)
    
    ax.set_xlabel('Musical Note', fontsize=10)
    ax.set_ylabel('MOC Value', fontsize=10)
    ax.set_title('Mouthpiece Octave Compensation - Deppe', fontsize=11, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(note_labels, rotation=45, ha='right', fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'real_moc.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("   ✓ real_moc.png")
except Exception as e:
    print(f"   ✗ Error: {e}")

# ==============================================================================
# 4. B_I y ESPE
# ==============================================================================
print("4. Generando gráfico de B_I y ESPE...")
try:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    
    bi_vals, espe_vals = [], []
    for note in note_labels:
        results = analyzer.analyze_single_note(note, flute_data.flute_model)
        if results:
            bi_vals.append(results.get('bi', 0))
            espe_vals.append(results.get('espe', 0))
        else:
            bi_vals.append(0)
            espe_vals.append(0)
    
    ax1.plot(x, bi_vals, 'o-', color='#F39C12', linewidth=2, markersize=5)
    ax1.axhline(y=0, color='k', linestyle='--', alpha=0.6)
    ax1.set_ylabel('B₁ (cents)', fontsize=10)
    ax1.set_title('First-Octave Pitch Adjustment (B₁) - Deppe', fontsize=11, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    
    ax2.plot(x, espe_vals, 's-', color='#16A085', linewidth=2, markersize=5)
    ax2.axhline(y=0, color='k', linestyle='--', alpha=0.6)
    ax2.set_xlabel('Musical Note', fontsize=10)
    ax2.set_ylabel('ESPE (cents)', fontsize=10)
    ax2.set_title('Embouchure Shift Pitch Effect (ESPE) - Deppe', fontsize=11, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(note_labels, rotation=45, ha='right', fontsize=8)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'real_bi_espe.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("   ✓ real_bi_espe.png")
except Exception as e:
    print(f"   ✗ Error: {e}")

# ==============================================================================
# 5. Q-FACTOR
# ==============================================================================
print("5. Generando gráfico de Q-factor...")
try:
    fig, ax = plt.subplots(figsize=(10, 5))
    
    q_vals = []
    for note in note_labels:
        results = analyzer.analyze_single_note(note, flute_data.flute_model)
        q_vals.append(results.get('q_factor', 0) if results else 0)
    
    ax.plot(x, q_vals, 'o-', color='#3498DB', linewidth=2, markersize=5)
    ax.set_xlabel('Musical Note', fontsize=10)
    ax.set_ylabel('Q-Factor', fontsize=10)
    ax.set_title('Quality Factor - Deppe', fontsize=11, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(note_labels, rotation=45, ha='right', fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'real_qfactor.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("   ✓ real_qfactor.png")
except Exception as e:
    print(f"   ✗ Error: {e}")

# ==============================================================================
# 6. HARMONIC RATIOS
# ==============================================================================
print("6. Generando gráfico de ratios armónicos...")
try:
    fig, ax = plt.subplots(figsize=(10, 5))
    
    ratio_f1_f0, ratio_f2_f0 = [], []
    for note in note_labels:
        results = analyzer.analyze_single_note(note, flute_data.flute_model)
        if results and 'resonance_frequencies' in results:
            freqs = results['resonance_frequencies']
            if len(freqs) >= 3:
                f0, f1, f2 = freqs[:3]
                ratio_f1_f0.append(f1 / f0 if f0 > 0 else 2.0)
                ratio_f2_f0.append(f2 / f0 if f0 > 0 else 3.0)
            else:
                ratio_f1_f0.append(2.0)
                ratio_f2_f0.append(3.0)
        else:
            ratio_f1_f0.append(2.0)
            ratio_f2_f0.append(3.0)
    
    ax.plot(x, ratio_f1_f0, 'o-', label='f₁/f₀', linewidth=2, markersize=5, color='#E74C3C')
    ax.plot(x, ratio_f2_f0, 's-', label='f₂/f₀', linewidth=2, markersize=5, color='#2ECC71')
    ax.axhline(y=2.0, color='red', linestyle='--', alpha=0.5, label='Ideal (2.0)')
    ax.axhline(y=3.0, color='green', linestyle='--', alpha=0.5, label='Ideal (3.0)')
    
    ax.set_xlabel('Musical Note', fontsize=10)
    ax.set_ylabel('Harmonic Ratio', fontsize=10)
    ax.set_title('Harmonic Ratios - Deppe', fontsize=11, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(note_labels, rotation=45, ha='right', fontsize=8)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_ylim([1.9, 3.1])
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'real_harmonic_ratios.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("   ✓ real_harmonic_ratios.png")
except Exception as e:
    print(f"   ✗ Error: {e}")

# ==============================================================================
# 7. PEAK HEIGHTS
# ==============================================================================
print("7. Generando gráfico de alturas de picos...")
try:
    fig, ax = plt.subplots(figsize=(10, 5))
    
    peak_f0, peak_f1, peak_f2 = [], [], []
    for note in note_labels:
        results = analyzer.analyze_single_note(note, flute_data.flute_model)
        if results and 'peak_heights' in results:
            peaks = results['peak_heights']
            peak_f0.append(peaks[0] if len(peaks) > 0 else 0)
            peak_f1.append(peaks[1] if len(peaks) > 1 else 0)
            peak_f2.append(peaks[2] if len(peaks) > 2 else 0)
        else:
            peak_f0.append(0)
            peak_f1.append(0)
            peak_f2.append(0)
    
    width = 0.25
    ax.bar(x - width, peak_f0, width, label='f₀', color='#3498DB', alpha=0.8)
    ax.bar(x, peak_f1, width, label='f₁', color='#E74C3C', alpha=0.8)
    ax.bar(x + width, peak_f2, width, label='f₂', color='#2ECC71', alpha=0.8)
    
    ax.set_xlabel('Musical Note', fontsize=10)
    ax.set_ylabel('Peak Height (dB)', fontsize=10)
    ax.set_title('Admittance Peak Heights - Deppe', fontsize=11, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(note_labels, rotation=45, ha='right', fontsize=8)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'real_peak_heights.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("   ✓ real_peak_heights.png")
except Exception as e:
    print(f"   ✗ Error: {e}")

# ==============================================================================
# 8. ADMITTANCE
# ==============================================================================
print("8. Generando espectro de admitancia...")
try:
    fig, ax = plt.subplots(figsize=(10, 5))
    
    test_note = note_labels[6] if len(note_labels) > 6 else note_labels[0]
    
    # Obtener impedancia desde el operations
    impedance_result = operations.calculate_impedance(test_note)
    
    if impedance_result and 'frequencies' in impedance_result:
        freqs = np.array(impedance_result['frequencies'])
        Z = np.array(impedance_result['impedance'])
        Y = 1.0 / (np.abs(Z) + 1e-10)
        
        ax.plot(freqs, Y, linewidth=1.5, color='#9B59B6')
        ax.set_xlabel('Frequency (Hz)', fontsize=10)
        ax.set_ylabel('|Admittance|', fontsize=10)
        ax.set_title(f'Admittance Spectrum - Deppe - {test_note}', fontsize=11, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_xlim([100, 3000])
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, 'real_admittance.png'), dpi=150, bbox_inches='tight')
        plt.close()
        print("   ✓ real_admittance.png")
    else:
        print("   ✗ No se pudo obtener datos de impedancia")
except Exception as e:
    print(f"   ✗ Error: {e}")

# ==============================================================================
# 9. MULTI-FLUTE COMPARISON (Deppe vs Freyer)
# ==============================================================================
print("9. Generando comparación multi-flauta (Deppe vs Freyer)...")
try:
    # Crear analyzer con ambas flautas
    flute_list_multi = [flute_deppe, flute_freyer]
    analyzer_multi = FluteAnalyzer(flute_list_multi)
    
    fig, ax = plt.subplots(figsize=(11, 5.5))
    
    flute_models = ["Deppe", "Freyer"]
    colors = ['#3498DB', '#E74C3C']
    markers = ['o', 's']
    
    # Encontrar notas comunes
    notes_deppe = set(flute_deppe.notes[:15])
    notes_freyer = set(flute_freyer.notes[:15])
    common_notes = sorted(list(notes_deppe & notes_freyer))[:15]
    
    for idx, (flute_model, flute, color, marker) in enumerate(zip(flute_models, flute_list_multi, colors, markers)):
        inharm_vals, note_labels_multi = [], []
        
        for note in common_notes:
            results = analyzer_multi.analyze_single_note(note, flute_model)
            if results:
                inharm_vals.append(results.get('inharmonicity', 0))
                note_labels_multi.append(note)
        
        x_multi = np.arange(len(note_labels_multi))
        ax.plot(x_multi, inharm_vals, marker=marker, linestyle='-', label=flute_model,
               linewidth=2, markersize=5, color=color, alpha=0.8)
    
    ax.axhline(y=0, color='k', linestyle='--', alpha=0.6)
    ax.fill_between(x_multi, -10, 10, alpha=0.1, color='gray')
    ax.set_xlabel('Musical Note', fontsize=10)
    ax.set_ylabel('Inharmonicity (cents)', fontsize=10)
    ax.set_title('Multi-Flute Comparison - Inharmonicity', fontsize=11, fontweight='bold')
    ax.set_xticks(x_multi)
    ax.set_xticklabels(note_labels_multi, rotation=45, ha='right', fontsize=8)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'real_multi_flute_comparison.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("   ✓ real_multi_flute_comparison.png")
except Exception as e:
    print(f"   ✗ Error: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'='*70}")
print("✓ GENERACIÓN DE SCREENSHOTS REALES COMPLETADA")
print(f"Directorio: {OUTPUT_DIR}/")
print(f"{'='*70}\n")
