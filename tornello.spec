# -*- mode: python ; coding: utf-8 -*-

import os

# Definiamo i percorsi assoluti per le dipendenze
base_path = os.path.abspath(SPECPATH)
src_path = os.path.join(base_path, 'src')
gbutils_path = os.path.abspath(os.path.join(base_path, '..', 'GBUtils'))

# La collezione dei suoni condivisa va dentro il pacchetto: da quando
# play_sound si appoggia ad Acusticator e' li' che stanno tutti i preset,
# compresi i trentuno che prima Tornello si portava in audio_presets.py.
import os
from pathlib import Path

import GBUtils

COLLEZIONE_SUONI = os.path.join(os.path.dirname(GBUtils.__file__), 'Acu_Collection.json')

# Delle traduzioni al programma servono soltanto i cataloghi compilati: i .po
# sono il testo su cui si lavora e nel pacchetto pubblico non c'entrano, come
# dice il punto 4.6 del prontuario di rilascio. L'elenco si ricava da SPECPATH,
# cosi' non dipende dalla cartella da cui si lancia PyInstaller.
CATALOGHI = [
    (str(percorso), str(percorso.parent.relative_to(Path(SPECPATH))))
    for percorso in Path(SPECPATH, 'locales').rglob('*.mo')
]

a = Analysis(
    ['tornello.py'],
    pathex=[src_path, gbutils_path],
    binaries=[],
    datas=[
        ('bbppairings', 'bbppairings'),
        ('MANUALE.txt', '.'),
        ('ChangeLog.txt', '.'),
        ('CREDITS.txt', '.'),
        (COLLEZIONE_SUONI, '.'),  # Collezione condivisa di GBUtils (v9.3.16)
    ] + CATALOGHI,
    hiddenimports=['unidecode'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'doctest', 'pdb', 'PyQt5',
              'PyQt6', 'PySide2', 'PySide6', 'matplotlib', 'pandas'],
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