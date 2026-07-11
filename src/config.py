import os
import sys
import builtins
from GBUtils import polipo


def resource_path(relative_path):
    """
    Restituisce il percorso assoluto a una risorsa (sola lettura), funzionante sia in sviluppo
    che per un eseguibile compilato con PyInstaller (anche con la cartella _internal).
    """
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        # In sviluppo, la radice del progetto è la cartella superiore a 'src'
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)


def user_data_path(relative_path):
    """
    Restituisce il percorso assoluto a un file di dati utente (scrittura), funzionante sia in sviluppo
    che per un eseguibile compilato con PyInstaller. I file vengono salvati nella cartella
    dell'eseguibile, garantendo la persistenza anche in configurazione onefile.
    """
    if getattr(sys, "frozen", False):
        base_path = os.path.dirname(sys.executable)
    else:
        # In sviluppo, la radice del progetto è la cartella superiore a 'src'
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)


locales_dir = resource_path("locales")
project_root = user_data_path("")

lingua_rilevata, _ = polipo(
    localedir=locales_dir, config_path=project_root, source_language="it"
)
builtins._ = _


# File e Directory Principali (relativi all'eseguibile/radice)
PLAYER_DB_FILE = user_data_path("Tornello - Players_db.json")
PLAYER_DB_TXT_FILE = user_data_path("Tornello - Players_db.txt")
ARCHIVED_TOURNAMENTS_DIR = user_data_path("Closed Tournaments")
FIDE_DB_LOCAL_FILE = user_data_path("fide_ratings_local.json")

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
