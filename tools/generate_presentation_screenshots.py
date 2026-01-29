#!/usr/bin/env python
"""
Generate demonstration screenshots for the Beamer presentation.
Creates representative plots without needing openwind or PyQt5.
"""

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

OUTPUT_DIR = "presentation_screenshots"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Set style
plt.style.use('seaborn-v0_8-darkgrid')

def generate_resonance_frequencies():
    """Generate resonance frequencies plot."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    notes = ['D4', 'Eb4', 'E4', 'F4', 'F#4', 'G4', 'Ab4', 'A4', 'Bb4', 'B4',
             'C5', 'C#5', 'D5', 'Eb5', 'E5', 'F5', 'F#5', 'G5', 'Ab5', 'A5']
    x = np.arange(len(notes))
    
    # Generate realistic-looking data
    base_freq = 293.66  # D4
    f0 = base_freq * (2 ** (np.arange(len(notes)) / 12))
    f1 = f0 * 2 * (1 + 0.01 * np.random.randn(len(notes)))  # Slight deviation from perfect octave
    f2 = f0 * 3 * (1 + 0.02 * np.random.randn(len(notes)))
    
    ax.plot(x, f0, 'o-', label='f₀ (First mode)', linewidth=2.5, markersize=9, color='#3498DB')
    ax.plot(x, f1, 's-', label='f₁ (Second mode)', linewidth=2.5, markersize=9, color='#E74C3C')
    ax.plot(x, f2, '^-', label='f₂ (Third mode)', linewidth=2.5, markersize=9, color='#2ECC71')
    
    ax.set_xlabel('Musical Note', fontsize=14, fontweight='bold')
    ax.set_ylabel('Frequency (Hz)', fontsize=14, fontweight='bold')
    ax.set_title('Resonance Frequencies vs. Musical Notes', fontsize=16, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(notes, rotation=45, ha='right')
    ax.legend(fontsize=12, loc='upper left')
    ax.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'screenshot_resonance_frequencies.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Generated: screenshot_resonance_frequencies.png")


def generate_inharmonicity():
    """Generate inharmonicity plot."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    notes = ['D4', 'Eb4', 'E4', 'F4', 'F#4', 'G4', 'Ab4', 'A4', 'Bb4', 'B4',
             'C5', 'C#5', 'D5', 'Eb5', 'E5', 'F5', 'F#5', 'G5', 'Ab5', 'A5']
    x = np.arange(len(notes))
    
    # Realistic inharmonicity values (in cents)
    inharm = 5 * np.sin(x / 3) + 8 * np.random.randn(len(notes))
    
    ax.plot(x, inharm, 'o-', color='#E74C3C', linewidth=2.5, markersize=9)
    ax.axhline(y=0, color='k', linestyle='--', alpha=0.6, linewidth=2, label='Perfect tuning')
    ax.fill_between(x, -10, 10, alpha=0.1, color='green', label='±10 cents tolerance')
    
    ax.set_xlabel('Musical Note', fontsize=14, fontweight='bold')
    ax.set_ylabel('Inharmonicity (cents)', fontsize=14, fontweight='bold')
    ax.set_title('Inharmonicity Deviation from Equal Temperament', fontsize=16, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(notes, rotation=45, ha='right')
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'screenshot_inharmonicity.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Generated: screenshot_inharmonicity.png")


def generate_moc():
    """Generate MOC (Mouthpiece Octave Compensation) plot."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    notes = ['D4', 'Eb4', 'E4', 'F4', 'F#4', 'G4', 'Ab4', 'A4', 'Bb4', 'B4',
             'C5', 'C#5', 'D5', 'Eb5', 'E5', 'F5', 'F#5', 'G5']
    x = np.arange(len(notes))
    
    # MOC values typically range from 0.8 to 1.2
    moc = 1.0 + 0.15 * np.sin(x / 4) + 0.05 * np.random.randn(len(notes))
    
    ax.plot(x, moc, 'o-', color='#9B59B6', linewidth=2.5, markersize=9)
    ax.axhline(y=1.0, color='k', linestyle='--', alpha=0.6, linewidth=2, label='MOC = 1.0 (ideal)')
    ax.fill_between(x, 0.9, 1.1, alpha=0.1, color='blue', label='Typical range')
    
    ax.set_xlabel('Musical Note', fontsize=14, fontweight='bold')
    ax.set_ylabel('MOC Value', fontsize=14, fontweight='bold')
    ax.set_title('Mouthpiece Octave Compensation (MOC)', fontsize=16, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(notes, rotation=45, ha='right')
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_ylim([0.7, 1.3])
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'screenshot_moc.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Generated: screenshot_moc.png")


def generate_bi_espe():
    """Generate B_I and ESPE plot."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    notes = ['D4', 'Eb4', 'E4', 'F4', 'F#4', 'G4', 'Ab4', 'A4', 'Bb4', 'B4',
             'C5', 'C#5', 'D5', 'Eb5', 'E5', 'F5', 'F#5', 'G5']
    x = np.arange(len(notes))
    
    # B_I values (in cents)
    bi = 10 * np.sin(x / 3) + 5 + 3 * np.random.randn(len(notes))
    
    # ESPE values (in cents)
    espe = -8 * np.cos(x / 4) + 2 * np.random.randn(len(notes))
    
    # B_I plot
    ax1.plot(x, bi, 'o-', color='#F39C12', linewidth=2.5, markersize=9)
    ax1.axhline(y=0, color='k', linestyle='--', alpha=0.6, linewidth=2)
    ax1.set_ylabel('B₁ (cents)', fontsize=14, fontweight='bold')
    ax1.set_title('First-Octave Pitch Adjustment (B₁)', fontsize=16, fontweight='bold')
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.legend(['B₁', 'Zero reference'], fontsize=11)
    
    # ESPE plot
    ax2.plot(x, espe, 's-', color='#16A085', linewidth=2.5, markersize=9)
    ax2.axhline(y=0, color='k', linestyle='--', alpha=0.6, linewidth=2)
    ax2.set_xlabel('Musical Note', fontsize=14, fontweight='bold')
    ax2.set_ylabel('ESPE (cents)', fontsize=14, fontweight='bold')
    ax2.set_title('Embouchure Shift Pitch Effect (ESPE)', fontsize=16, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(notes, rotation=45, ha='right')
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.legend(['ESPE', 'Zero reference'], fontsize=11)
    
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'screenshot_bi_espe.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Generated: screenshot_bi_espe.png")


def generate_qfactor():
    """Generate Q-factor plot."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    notes = ['D4', 'Eb4', 'E4', 'F4', 'F#4', 'G4', 'Ab4', 'A4', 'Bb4', 'B4',
             'C5', 'C#5', 'D5', 'Eb5', 'E5', 'F5', 'F#5', 'G5', 'Ab5', 'A5']
    x = np.arange(len(notes))
    
    # Q-factor typically ranges from 10 to 50 for wind instruments
    q_factor = 25 + 10 * np.sin(x / 5) + 3 * np.random.randn(len(notes))
    q_factor = np.maximum(q_factor, 10)  # Ensure positive values
    
    ax.plot(x, q_factor, 'o-', color='#3498DB', linewidth=2.5, markersize=9)
    ax.axhline(y=25, color='gray', linestyle='--', alpha=0.5, linewidth=2, label='Average Q')
    
    ax.set_xlabel('Musical Note', fontsize=14, fontweight='bold')
    ax.set_ylabel('Q-Factor', fontsize=14, fontweight='bold')
    ax.set_title('Resonance Quality Factor (Q)', fontsize=16, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(notes, rotation=45, ha='right')
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_ylim([0, 50])
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'screenshot_qfactor.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Generated: screenshot_qfactor.png")


def generate_harmonic_ratios():
    """Generate harmonic ratios plot."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    notes = ['D4', 'Eb4', 'E4', 'F4', 'F#4', 'G4', 'Ab4', 'A4', 'Bb4', 'B4',
             'C5', 'C#5', 'D5', 'Eb5', 'E5', 'F5', 'F#5', 'G5', 'Ab5', 'A5']
    x = np.arange(len(notes))
    
    # Harmonic ratios (slight deviations from ideal)
    ratio_f1_f0 = 2.0 + 0.02 * np.sin(x / 4) + 0.01 * np.random.randn(len(notes))
    ratio_f2_f0 = 3.0 + 0.03 * np.cos(x / 5) + 0.015 * np.random.randn(len(notes))
    
    ax.plot(x, ratio_f1_f0, 'o-', label='f₁/f₀', linewidth=2.5, markersize=9, color='#E74C3C')
    ax.plot(x, ratio_f2_f0, 's-', label='f₂/f₀', linewidth=2.5, markersize=9, color='#2ECC71')
    ax.axhline(y=2.0, color='red', linestyle='--', alpha=0.5, linewidth=1.5, label='Ideal octave (2.0)')
    ax.axhline(y=3.0, color='green', linestyle='--', alpha=0.5, linewidth=1.5, label='Ideal twelfth (3.0)')
    
    ax.set_xlabel('Musical Note', fontsize=14, fontweight='bold')
    ax.set_ylabel('Harmonic Ratio', fontsize=14, fontweight='bold')
    ax.set_title('Harmonic Ratios (f₁/f₀ and f₂/f₀)', fontsize=16, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(notes, rotation=45, ha='right')
    ax.legend(fontsize=11, loc='upper left')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_ylim([1.9, 3.1])
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'screenshot_harmonic_ratios.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Generated: screenshot_harmonic_ratios.png")


def generate_peak_heights():
    """Generate admittance peak heights plot."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    notes = ['D4', 'Eb4', 'E4', 'F4', 'F#4', 'G4', 'Ab4', 'A4', 'Bb4', 'B4',
             'C5', 'C#5', 'D5', 'Eb5', 'E5', 'F5', 'F#5', 'G5', 'Ab5', 'A5']
    x = np.arange(len(notes))
    
    # Peak heights in dB (typically 40-80 dB)
    peak_f0 = 60 + 8 * np.sin(x / 6) + 2 * np.random.randn(len(notes))
    peak_f1 = 55 + 7 * np.sin(x / 5 + 1) + 2 * np.random.randn(len(notes))
    peak_f2 = 50 + 6 * np.sin(x / 4 + 2) + 2 * np.random.randn(len(notes))
    
    width = 0.25
    ax.bar(x - width, peak_f0, width, label='f₀ peak', color='#3498DB', alpha=0.8)
    ax.bar(x, peak_f1, width, label='f₁ peak', color='#E74C3C', alpha=0.8)
    ax.bar(x + width, peak_f2, width, label='f₂ peak', color='#2ECC71', alpha=0.8)
    
    ax.set_xlabel('Musical Note', fontsize=14, fontweight='bold')
    ax.set_ylabel('Admittance Peak Height (dB)', fontsize=14, fontweight='bold')
    ax.set_title('Admittance Peak Heights', fontsize=16, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(notes, rotation=45, ha='right')
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'screenshot_peak_heights.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Generated: screenshot_peak_heights.png")


def generate_admittance():
    """Generate admittance spectrum plot."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    freq = np.linspace(100, 3000, 1000)
    
    # Generate admittance peaks at resonance frequencies
    f0, f1, f2 = 294, 588, 882  # D4 and harmonics
    
    def lorentzian(f, f0, gamma, amplitude):
        return amplitude / (1 + ((f - f0) / gamma) ** 2)
    
    admittance = (lorentzian(freq, f0, 8, 1.0) +
                 lorentzian(freq, f1, 12, 0.7) +
                 lorentzian(freq, f2, 15, 0.5) +
                 0.05 * np.random.randn(len(freq)))
    
    ax.plot(freq, admittance, linewidth=2, color='#9B59B6')
    ax.axvline(x=f0, color='r', linestyle='--', alpha=0.5, label=f'f₀ = {f0} Hz')
    ax.axvline(x=f1, color='g', linestyle='--', alpha=0.5, label=f'f₁ = {f1} Hz')
    ax.axvline(x=f2, color='b', linestyle='--', alpha=0.5, label=f'f₂ = {f2} Hz')
    
    ax.set_xlabel('Frequency (Hz)', fontsize=14, fontweight='bold')
    ax.set_ylabel('|Admittance| (a.u.)', fontsize=14, fontweight='bold')
    ax.set_title('Acoustic Admittance Spectrum - Note D4', fontsize=16, fontweight='bold')
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_xlim([100, 3000])
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'screenshot_admittance.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Generated: screenshot_admittance.png")


def generate_multi_flute_comparison():
    """Generate multi-flute comparison plot."""
    fig, ax = plt.subplots(figsize=(14, 7))
    
    notes = ['D4', 'Eb4', 'E4', 'F4', 'F#4', 'G4', 'Ab4', 'A4', 'Bb4', 'B4',
             'C5', 'C#5', 'D5', 'Eb5', 'E5']
    x = np.arange(len(notes))
    
    flutes = ['Deppe', 'Bizey', 'Quantz']
    colors = ['#3498DB', '#E74C3C', '#2ECC71']
    markers = ['o', 's', '^']
    
    for idx, (flute, color, marker) in enumerate(zip(flutes, colors, markers)):
        inharm = 5 * np.sin(x / 3 + idx) + (idx - 1) * 3 + 2 * np.random.randn(len(notes))
        ax.plot(x, inharm, marker=marker, linestyle='-', label=flute, 
               linewidth=2.5, markersize=9, color=color, alpha=0.8)
    
    ax.axhline(y=0, color='k', linestyle='--', alpha=0.6, linewidth=2)
    ax.fill_between(x, -10, 10, alpha=0.1, color='gray', label='±10 cents tolerance')
    
    ax.set_xlabel('Musical Note', fontsize=14, fontweight='bold')
    ax.set_ylabel('Inharmonicity (cents)', fontsize=14, fontweight='bold')
    ax.set_title('Multi-Flute Comparison - Inharmonicity Analysis', fontsize=16, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(notes, rotation=45, ha='right')
    ax.legend(fontsize=12, loc='upper left')
    ax.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'screenshot_multi_flute_comparison.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print("✓ Generated: screenshot_multi_flute_comparison.png")


def main():
    """Generate all demonstration screenshots."""
    print("\n" + "=" * 70)
    print("GENERATING PRESENTATION SCREENSHOTS")
    print("=" * 70 + "\n")
    
    print("Creating acoustic analysis plots...")
    generate_resonance_frequencies()
    generate_inharmonicity()
    generate_moc()
    generate_bi_espe()
    generate_qfactor()
    generate_harmonic_ratios()
    generate_peak_heights()
    generate_admittance()
    
    print("\nCreating multi-flute comparison...")
    generate_multi_flute_comparison()
    
    print("\n" + "=" * 70)
    print(f"✓ All screenshots generated successfully in: {OUTPUT_DIR}/")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
