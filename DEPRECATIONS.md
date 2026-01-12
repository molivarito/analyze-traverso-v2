# Deprecations and Legacy Code

This document tracks deprecated, legacy, and unclear-status code in the Traverso Analyzer project.

## Purpose

This file helps developers understand:
- Which code is actively maintained
- Which code is legacy but may still work
- Which code should be avoided for new development
- Migration paths for deprecated features

## GUI Applications Status

### 🟢 Active - Use These

#### `unified_flute_gui_qt.py` ⭐ **PRIMARY APPLICATION**
- **Status**: ✅ Active, primary GUI
- **Framework**: PyQt5
- **Description**: Comprehensive GUI with all features
- **Capabilities**:
  - Geometry visualization (2D and 3D)
  - Acoustic analysis
  - Database management
  - Engineering drawings
  - G-code generation
  - Sensitivity analysis integration
- **Use for**: All new development and primary user interface

#### `flute_experimenter.py`
- **Status**: ✅ Active, specialized tool
- **Framework**: PyQt5
- **Description**: Interactive geometry editor
- **Use for**: Experimental geometry modifications and real-time acoustic feedback

#### `flute_optimizer_gui.py`
- **Status**: ✅ Active, specialized tool
- **Framework**: PyQt5
- **Description**: Embouchure height optimization
- **Use for**: Tuning flutes by optimizing cork/chimney positions

#### `flute_geometry_editor_qt.py`
- **Status**: ✅ Active, specialized tool
- **Framework**: PyQt5
- **Description**: Detailed geometry editing
- **Use for**: Precise geometric modifications

### 🟡 Legacy/Unclear - Review Before Using

#### `gui.py`
- **Status**: ⚠️ **UNCLEAR** - Needs review
- **Framework**: Uncertain (possibly Tkinter or early PyQt)
- **Description**: Original GUI implementation
- **Lines**: 736 lines
- **Issues**:
  - Purpose unclear with `unified_flute_gui_qt.py` existing
  - May be superseded by newer GUIs
  - No clear documentation of differences
- **Recommendation**:
  - **DO NOT** use for new development
  - Document actual purpose or deprecate
  - If still needed, rename to clarify purpose (e.g., `gui_legacy.py` or `gui_simple.py`)

#### `gui_db.py`
- **Status**: ⚠️ **UNCLEAR** - Needs review
- **Framework**: Uncertain
- **Description**: Database-focused GUI variant (?)
- **Lines**: 722 lines
- **Issues**:
  - Purpose unclear - `unified_flute_gui_qt.py` has database functionality
  - May be an intermediate development version
  - Possible duplicate functionality
- **Recommendation**:
  - **DO NOT** use for new development
  - Document actual purpose or deprecate
  - Consider merging unique features into `unified_flute_gui_qt.py`

#### `unified_flute_gui.py`
- **Status**: ⚠️ **UNCLEAR** - Likely superseded
- **Framework**: Possibly Tkinter or early PyQt
- **Description**: Earlier unified GUI (before Qt version?)
- **Lines**: 865 lines
- **Issues**:
  - Appears to be superseded by `unified_flute_gui_qt.py`
  - May use different GUI framework
  - No clear use case vs Qt version
- **Recommendation**:
  - **DO NOT** use for new development
  - If Qt version has feature parity, deprecate this
  - Otherwise, document why both exist

#### `graphical_editor.py`
- **Status**: ⚠️ **UNCLEAR** - May overlap with other editors
- **Framework**: Uncertain
- **Description**: Graphical geometry editor
- **Lines**: 572 lines
- **Overlap with**: `flute_geometry_editor_qt.py`, `flute_experimenter.py`
- **Recommendation**:
  - Document differences from other editors
  - Consider consolidating if redundant

#### `perturbation_gui.py`
- **Status**: ⚠️ **UNCLEAR** - May be superseded by sensitivity_analysis_dialog.py
- **Framework**: Uncertain
- **Description**: Perturbation analysis interface
- **Lines**: 457 lines
- **Overlap with**: `sensitivity_analysis_dialog.py`
- **Recommendation**:
  - Review if `sensitivity_analysis_dialog.py` provides all functionality
  - Deprecate if redundant

## Backup Directories

### ❌ Should Not Be in Repository

#### `backup_before_cleanup_20251126/`
- **Status**: ❌ **REMOVE FROM REPO**
- **Description**: Backup before cleanup on 2025-11-26
- **Contents**: 8 Python files (old versions)
- **Action Required**:
  - Keep locally if needed for reference
  - Remove from repository (use `.gitignore`)
  - History is preserved in Git, backups are redundant

#### `backup_before_refactor_20251119_222408/`
- **Status**: ❌ **REMOVE FROM REPO**
- **Description**: Backup before refactoring on 2025-11-19
- **Contents**: 16 Python files (old versions)
- **Action Required**:
  - Keep locally if needed for reference
  - Remove from repository (use `.gitignore`)
  - Use Git history to retrieve old versions if needed

**Note**: The `.gitignore` has been updated to prevent future backup directories from being committed.

## Migration Paths

### For GUI Development

**Current Practice** ✅:
```python
# Use this for all GUI development
from unified_flute_gui_qt import UnifiedFluteGUI_Qt
```

**Legacy Practice** ❌:
```python
# Avoid these unless you know why they exist
from gui import ...
from gui_db import ...
from unified_flute_gui import ...
```

### For Geometry Editing

**Primary Tool** ✅:
```python
# Interactive experimentation with real-time feedback
from flute_experimenter import ...
```

**Specialized Tool** ✅:
```python
# Detailed geometric editing
from flute_geometry_editor_qt import ...
```

**Unclear** ⚠️:
```python
# Review before using
from graphical_editor import ...
from perturbation_gui import ...
```

## Deprecated Patterns

### Avoid These Patterns

#### 1. Creating Backups in Repository
```bash
# ❌ Don't do this
cp important_file.py important_file_backup_20250112.py
git add important_file_backup_20250112.py

# ✅ Do this instead
git commit -m "Save current state before refactoring"
# Make changes
git commit -m "Complete refactoring"
# Old version is in Git history
```

#### 2. Multiple GUIs with Unclear Purpose
```python
# ❌ Don't create new GUIs without justification
# If unified_flute_gui_qt.py exists, extend it rather than creating gui_v2.py

# ✅ Do this instead
# 1. Extend unified_flute_gui_qt.py, or
# 2. Create specialized tool with clear, documented purpose
```

#### 3. Commented-Out Code
```python
# ❌ Don't leave large blocks of commented code
# import old_module  # Not used anymore
# def old_function():
#     # 50 lines of commented code
#     pass

# ✅ Do this instead
# Delete it - it's in Git history if you need it
```

## Action Items for Cleanup

### Priority 1: Immediate (No Breaking Changes)
- [x] Create `.gitignore` entries for backup directories
- [x] Document deprecation status (this file)
- [ ] Add deprecation warnings to unclear modules

### Priority 2: Investigation Required
- [ ] Test `gui.py` - determine if it's used, document or remove
- [ ] Test `gui_db.py` - determine if it's used, document or remove
- [ ] Test `unified_flute_gui.py` - compare with Qt version, deprecate if redundant
- [ ] Review `graphical_editor.py` vs other editors
- [ ] Review `perturbation_gui.py` vs `sensitivity_analysis_dialog.py`

### Priority 3: Cleanup (After Investigation)
- [ ] Remove or clearly document legacy GUIs
- [ ] Add deprecation warnings to files that will be removed
- [ ] Remove backup directories from repository (keep locally)
- [ ] Update README to clarify which tools to use

## Deprecation Warning Template

For files that will be deprecated but not immediately removed:

```python
"""
⚠️ DEPRECATION WARNING ⚠️

This module is deprecated and will be removed in a future version.

**Replacement**: Use `unified_flute_gui_qt.py` instead.

**Reason**: This module has been superseded by the Qt-based unified GUI.

**Timeline**: This module will be removed in version 3.0.0 (estimated Q2 2026).

**Migration**: See DEPRECATIONS.md for migration guide.

If you rely on this module, please contact the maintainers.
"""

import warnings

warnings.warn(
    "This module is deprecated. Use unified_flute_gui_qt instead.",
    DeprecationWarning,
    stacklevel=2
)

# ... rest of code
```

## Questions?

If you're unsure whether to use a particular module:

1. Check this file first
2. Check `ARCHITECTURE.md` for recommended modules
3. Ask in project discussions or issues
4. When in doubt, use `unified_flute_gui_qt.py` for GUI work

## Changelog

- **2026-01-12**: Initial deprecation documentation created
  - Identified unclear status GUIs
  - Documented backup directory issue
  - Established deprecation workflow

---

**Last Updated**: 2026-01-12
