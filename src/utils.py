import datetime
import re
import os
import shutil
from babel.dates import format_date
from config import _, lingua_rilevata, DATE_FORMAT_ISO
from GBUtils import key

def create_backup(filepath, context="backup"):
    """
    Crea una copia di backup del file specificato nella cartella 'backup'.
    Aggiunge un timestamp e il contesto al nome del file per non sovrascrivere backup precedenti.
    """
    if not os.path.exists(filepath):
        return False
        
    backup_dir = "backup"
    if not os.path.exists(backup_dir):
        try:
            os.makedirs(backup_dir)
        except OSError:
            return False
            
    filename = os.path.basename(filepath)
    name, ext = os.path.splitext(filename)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{name}_{context}_{timestamp}{ext}"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        shutil.copy2(filepath, backup_path)
        return True
    except Exception:
        return False

def enter_escape(prompt=""):
    '''Ritorna vero su invio, falso su escape'''
    while True:
        k=key(prompt).strip()
        if k == "":
            return True
        elif k == "\x1b":
            return False
        print(_("Conferma con invio o annulla con escape"))

def format_rank_ordinal(rank):
    """Formatta il rank come numero ordinale italiano (es. 1°, 6°) o 'RIT'."""
    if rank == "RIT":
        return "RIT"
    try:
        # Prova a convertire in intero
        rank_int = int(rank)
        # Aggiunge il simbolo di grado per l'ordinale
        return f"{rank_int}°"
    except (ValueError, TypeError):
        # Se il rank non è 'RIT' e non è convertibile in intero, ritorna '?'
        return "?" # Fallback per rank non validi o non numerici

def format_date_locale(date_input):
    """Formatta una data (oggetto datetime o stringa ISO) nel formato locale esteso
       usando la libreria Babel per una gestione robusta della localizzazione."""
    if not date_input:
        return _("N/D")

    try:
        date_obj = date_input
        if not isinstance(date_input, datetime.datetime):
            # Converte la stringa ISO in un oggetto datetime, ma solo la parte della data
            date_obj = datetime.datetime.strptime(str(date_input), DATE_FORMAT_ISO).date()

        # Usa Babel per formattare la data in italiano in modo sicuro
        # 'full' corrisponde a un formato tipo "lunedì 23 giugno 2025"
        return format_date(date_obj, format='full', locale=lingua_rilevata).capitalize()
    except (ValueError, TypeError, IndexError):
        # Se qualcosa va storto, restituisce l'input originale
        return str(date_input)

def format_points(points):
    """Formatta i punti per la visualizzazione (intero se .0, altrimenti decimale)."""
    try:
        points = float(points)
        return str(int(points)) if points == int(points) else f"{points:.1f}"
    except (ValueError, TypeError):
        return str(points)

def sanitize_filename(name):
    """Rimuove/sostituisce caratteri problematici per i nomi dei file."""
    name = name.replace(' ', '_')
    name = re.sub(r'[^\w\-]+', '', name)
    if not name:
        name = "Torneo_Senza_Nome"
    return name