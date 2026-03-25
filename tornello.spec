# -*- mode: python ; coding: utf-8 -*-

import os

# Definiamo i percorsi assoluti per le dipendenze
base_path = os.path.abspath(SPECPATH)
src_path = os.path.join(base_path, 'src')
gbutils_path = os.path.abspath(os.path.join(base_path, '..', 'GBUtils'))

a = Analysis(
    ['tornello.py'],
    pathex=[src_path, gbutils_path],
    binaries=[],
    datas=[
        ('bbppairings', 'bbppairings'),
        ('locales', 'locales') # La cartella locales e tutto il suo contenuto per le traduzioni
    ],
    hiddenimports=['unidecode'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'doctest', 'pdb', 'PyQt5',
              'PyQt6', 'PySide2', 'PySide6', 'wx', 'matplotlib', 'pandas'],
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [], # Niente librerie qui per la modalità onedir (directory singola)
    exclude_binaries=True, # Importante per la modalità onedir: esclude i binari dall'exe
    name='tornello',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False, # Meglio False per la modalità onedir
    upx=True, # Usa UPX se installato per ridurre le dimensioni
    console=True, # App da console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Blocco COLLECT per creare la directory _internal
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='tornello',
)