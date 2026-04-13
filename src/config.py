import os
import sys
from GBUtils import polipo


def resource_path(relative_path):
    """
    Restituisce il percorso assoluto a una risorsa, funzionante sia in sviluppo
    che per un eseguibile compilato con PyInstaller (anche con la cartella _internal).
    """
    try:
        # PyInstaller crea una cartella temporanea e ci salva il percorso in _MEIPASS
        # Questo è il percorso base per le risorse quando l'app è "congelata"
        base_path = sys._MEIPASS
    except Exception:
        # Se _MEIPASS non esiste, non siamo in un eseguibile PyInstaller
        # o siamo in una build onedir, il percorso base è la cartella dello script
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


lingua_rilevata, _ = polipo(source_language="it")
import builtins

builtins._ = _

# File e Directory Principali (relativi all'eseguibile)
PLAYER_DB_FILE = resource_path("Tornello - Players_db.json")
PLAYER_DB_TXT_FILE = resource_path("Tornello - Players_db.txt")
ARCHIVED_TOURNAMENTS_DIR = resource_path("Closed Tournaments")
FIDE_DB_LOCAL_FILE = resource_path("fide_ratings_local.json")

# Costanti per l'integrazione con bbpPairings
BBP_SUBDIR = resource_path("bbppairings")
BBP_EXE_NAME = "bbpPairings.exe"
BBP_EXE_PATH = os.path.join(BBP_SUBDIR, BBP_EXE_NAME)
BBP_INPUT_TRF = os.path.join(BBP_SUBDIR, "input_bbp.trf")
BBP_OUTPUT_COUPLES = os.path.join(BBP_SUBDIR, "output_coppie.txt")
BBP_OUTPUT_CHECKLIST = os.path.join(BBP_SUBDIR, "output_checklist.txt")

# Costanti non di percorso
DATE_FORMAT_ISO = "%Y-%m-%d"
DEFAULT_ELO = 1399.0
DEFAULT_K_FACTOR = 20
FIDE_XML_DOWNLOAD_URL = "http://ratings.fide.com/download/players_list_xml.zip"
