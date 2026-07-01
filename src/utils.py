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
    """Ritorna vero su invio, falso su escape"""
    while True:
        k = key(prompt).strip()
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
        return "?"  # Fallback per rank non validi o non numerici


def format_date_locale(date_input):
    """Formatta una data (oggetto datetime o stringa ISO) nel formato locale esteso
    usando la libreria Babel per una gestione robusta della localizzazione."""
    if not date_input:
        return _("N/D")

    try:
        date_obj = date_input
        if not isinstance(date_input, datetime.datetime):
            # Converte la stringa ISO in un oggetto datetime, ma solo la parte della data
            date_obj = datetime.datetime.strptime(
                str(date_input), DATE_FORMAT_ISO
            ).date()

        # Usa Babel per formattare la data in italiano in modo sicuro
        # 'full' corrisponde a un formato tipo "lunedì 23 giugno 2025"
        return format_date(date_obj, format="full", locale=lingua_rilevata).capitalize()
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
    name = name.replace(" ", "_")
    name = re.sub(r"[^\w\-]+", "", name)
    if not name:
        name = "Torneo_Senza_Nome"
    return name

def parse_flexible_date(date_input_str):
    """
    Tenta di parsare una data da vari formati, incluso ISO (YYYY-MM-DD)
    e compatto senza punteggiatura (YYYYMMDD).
    Restituisce un oggetto datetime se valido, solleva ValueError altrimenti.
    """
    from config import DATE_FORMAT_ISO
    from datetime import datetime
    
    date_str = date_input_str.strip()
    if not date_str:
        raise ValueError("Data vuota")
        
    # Tentativo ISO standard
    try:
        return datetime.strptime(date_str, DATE_FORMAT_ISO)
    except ValueError:
        pass
        
    # Tentativo AAAAMMGG compatto (lunghezza 8, solo numeri)
    if len(date_str) == 8 and date_str.isdigit():
        try:
            year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:])
            return datetime(year, month, day)
        except ValueError:
            pass
            
    raise ValueError(f"Formato data '{date_str}' non riconosciuto.")


def play_sound(event_name, torneo=None, sync=False):
    """
    Riproduce un effetto acustico per feedback utente.
    event_name può essere: 'avvio', 'chiusura', 'errore', 'conferma', 'cancellato',
    'salvato', 'nuovo_turno', 'aggiunta_giocatore', 'ritiro_giocatore',
    'rimozione_giocatore', 'conclusione_turno', 'conclusione_torneo', 'time_machine',
    'pianifica_crea', 'pianifica_modifica', 'pianifica_rimuovi',
    'risultato_1-0', 'risultato_0-1', 'risultato_1/2-1/2', 'risultato_1-F', 'risultato_F-1', 'risultato_0-0F',
    'notifica'.
    """
    import json
    import os
    import sys
    
    # Determina il volume base dal file di impostazioni globali o dal torneo
    base_volume = 0.5
    try:
        settings_path = os.path.join(os.path.abspath("."), "Tornello - Settings.json")
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as sf:
                s_data = json.load(sf)
                base_volume = s_data.get("volume", 50) / 100.0
    except Exception:
        pass

    if torneo and isinstance(torneo, dict):
        base_volume = torneo.get("base_volume", base_volume)

    # Mappatura eventi su preset
    event_presets = {
        "avvio": "tornello_avvio",
        "chiusura": "tornello_chiusura",
        "errore": "rifiutato",
        "conferma": "roger_cw_conferma",
        "cancellato": "cancellato",
        "salvato": "written_ok",
        "nuovo_turno": "tornello_abbinamento",
        "aggiunta_giocatore": "tornello_aggiunta_giocatore",
        "ritiro_giocatore": "tornello_ritiro_giocatore",
        "rimozione_giocatore": "tornello_rimozione_giocatore",
        "conclusione_turno": "tornello_conclusione_turno",
        "conclusione_torneo": "tornello_conclusione_torneo",
        "time_machine": "tornello_time_machine",
        "pianifica_crea": "tornello_pianifica_crea",
        "pianifica_modifica": "tornello_pianifica_modifica",
        "pianifica_rimuovi": "tornello_pianifica_rimuovi",
        "risultato_1-0": "tornello_risultato_1_0",
        "risultato_0-1": "tornello_risultato_0_1",
        "risultato_1/2-1/2": "tornello_risultato_patta",
        "risultato_1-F": "tornello_risultato_1_F",
        "risultato_F-1": "tornello_risultato_F_1",
        "risultato_0-0F": "tornello_risultato_0_0F",
        "notifica": "notifica"
    }

    preset_name = event_presets.get(event_name, event_name)

    try:
        import GBUtils
        from GBUtils import Acusticator
        
        gbutils_dir = os.path.dirname(GBUtils.__file__)
        db_path = os.path.join(gbutils_dir, "Acu_Collection.json")

        from audio_presets import custom_presets


        preset_data = None
        if os.path.exists(db_path):
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    collection = json.load(f)
                
                db_dirty = False
                for k, v in custom_presets.items():
                    if k not in collection:
                        collection[k] = v
                        db_dirty = True
                
                if db_dirty:
                    with open(db_path, "w", encoding="utf-8") as f:
                        json.dump(collection, f, indent=4, ensure_ascii=False)
                
                preset_data = collection.get(preset_name)
            except Exception as e:
                sys.stderr.write(f"Acusticator DB Error: {e}\n")

        if not preset_data:
            preset_data = custom_presets.get(preset_name)

        if not preset_data:
            return

        score_flat = []
        for q in preset_data.get('score', []):
            note, dur, pan, vol_delta = q
            vol = max(0.0, min(1.0, base_volume + vol_delta))
            score_flat.extend([note, dur, pan, vol])
        
        Acusticator(
            score_flat,
            kind=preset_data.get('kind', 1),
            adsr=preset_data.get('adsr', [0.005, 0.0, 100.0, 0.005]),
            sync=sync
        )
    except Exception as e:
        sys.stderr.write(f"Acusticator Play Error: {e}\n")


def _ensure_players_dict(torneo):
    """Assicura che il dizionario cache dei giocatori sia presente e aggiornato."""
    if "players_dict" not in torneo or len(torneo["players_dict"]) != len(
        torneo.get("players", [])
    ):
        torneo["players_dict"] = {p["id"]: p for p in torneo.get("players", [])}
    return torneo["players_dict"]


def get_player_by_id(torneo, player_id):
    """Restituisce i dati del giocatore nel torneo dato il suo ID, usando il dizionario interno."""
    _ensure_players_dict(torneo)
    return torneo["players_dict"].get(player_id)


def get_relevance_score(player, query_terms):
    last_name = player.get("last_name", "").lower()
    first_name = player.get("first_name", "").lower()
    first_term = query_terms[0] if query_terms else ""
    if last_name.startswith(first_term):
        return (1, last_name, first_name)
    elif first_name.startswith(first_term):
        return (2, last_name, first_name)
    else:
        return (3, last_name, first_name)


def match_player_query(player, query):
    """
    Effettua una ricerca flessibile basata su operatori (+ per obbligatorio, - per escluso, = per frase esatta).
    Cerca su Cognome, Nome, Anno di Nascita, Federazione e ID FIDE.
    Ritorna None se non corrisponde, o una tupla (score, rel_score, last_name, first_name) per l'ordinamento.
    """
    first_name = player.get("first_name", "") or ""
    last_name = player.get("last_name", "") or ""
    
    # Estrae l'anno di nascita (da birth_year o birth_date)
    birth_yr = player.get("birth_year")
    if not birth_yr and player.get("birth_date"):
        birth_yr = player["birth_date"][:4]
    birth = str(birth_yr or "")
    
    fed = player.get("federation", "") or ""
    fide_id = str(player.get("id_fide") or player.get("fide_id_num_str") or "")
    
    search_text = f"{first_name} {last_name} {birth} {fed} {fide_id}".lower()
    
    exact_phrases = []
    forbidden_terms = []
    mandatory_terms = []
    optional_terms = []
    
    temp_query = query.strip()
    if temp_query.startswith("="):
        phrase = temp_query.replace("=", " ").strip().lower()
        if phrase:
            exact_phrases.append(phrase)
    else:
        parts = temp_query.split()
        for part in parts:
            if part.startswith("+"):
                term = part[1:].strip().lower()
                if term:
                    mandatory_terms.append(term)
            elif part.startswith("-"):
                term = part[1:].strip().lower()
                if term:
                    forbidden_terms.append(term)
            else:
                term = part.strip().lower()
                if term:
                    optional_terms.append(term)
                    
    # Verifiche
    for term in forbidden_terms:
        if term in search_text:
            return None
            
    for phrase in exact_phrases:
        if phrase not in search_text:
            return None
            
    for term in mandatory_terms:
        if term not in search_text:
            return None
            
    matched_optionals = 0
    for term in optional_terms:
        if term in search_text:
            matched_optionals += 1
            
    if not mandatory_terms and not exact_phrases and optional_terms and matched_optionals == 0:
        return None
        
    total_matched = len(mandatory_terms) + matched_optionals + len(exact_phrases)
    
    # Primo termine per calcolo rilevanza starts-with
    first_query_term = ""
    if query.strip().startswith("="):
        parts_seq = query.replace("=", " ").strip().split()
        if parts_seq:
            first_query_term = parts_seq[0].lower()
    else:
        for part in query.split():
            clean = part.lstrip("+-").lower()
            if clean:
                first_query_term = clean
                break
                
    rel_score = 3
    last_name_l = last_name.lower()
    first_name_l = first_name.lower()
    if first_query_term:
        if last_name_l.startswith(first_query_term):
            rel_score = 1
        elif first_name_l.startswith(first_query_term):
            rel_score = 2
            
    return (-total_matched, rel_score, last_name_l, first_name_l)


def resolve_and_verify_save_path(path, default_fallback="."):
    """
    Verifica se il percorso personalizzato è valido e accessibile.
    - Se l'unità (drive letter) non è disponibile: fallback alla cartella di default + avviso.
    - Se la cartella specificata non esiste: prova a crearla. Se fallisce, fallback + avviso.
    - Logga l'operazione su console/stdout.
    Restituisce una tupla (resolved_path, warning_message).
    """
    if not path:
        return default_fallback, None

    # Normalizza il percorso
    path = os.path.abspath(path)
    drive, tail = os.path.splitdrive(path)
    
    # 1. Verifica disponibilità dell'unità (drive letter)
    if drive:
        drive_root = drive + os.sep
        if not os.path.exists(drive_root):
            msg = _("L'unità '{drive}' non è disponibile. Uso la cartella di default: '{fallback}'.").format(
                drive=drive, fallback=default_fallback
            )
            print(f"LOG: {msg}")
            return default_fallback, msg

    # 2. Verifica/creazione della cartella
    if not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
            # Log dell'operazione di creazione
            msg_log = _("Creata cartella di salvataggio inesistente: '{path}'").format(path=path)
            print(f"LOG: {msg_log}")
            msg_user = _("La cartella '{path}' non esisteva ed è stata creata.").format(path=path)
            return path, msg_user
        except Exception as e:
            msg = _("Impossibile creare la cartella '{path}': {error}. Uso la cartella di default: '{fallback}'.").format(
                path=path, error=e, fallback=default_fallback
            )
            print(f"LOG: {msg}")
            return default_fallback, msg

    # Verifica se la cartella esistente è scrivibile
    try:
        test_file = os.path.join(path, ".tornello_write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
    except Exception as e:
        msg = _("La cartella '{path}' non è scrivibile: {error}. Uso la cartella di default: '{fallback}'.").format(
            path=path, error=e, fallback=default_fallback
        )
        print(f"LOG: {msg}")
        return default_fallback, msg

    return path, None


