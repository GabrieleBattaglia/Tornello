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
    
    # Determina il volume base dal torneo
    base_volume = 0.5
    if torneo and isinstance(torneo, dict):
        base_volume = torneo.get("base_volume", 0.5)

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

        custom_presets = {
            "tornello_avvio": {
                "descrizione": "Suono di benvenuto per Tornello (arpeggio ascendente solare)",
                "score": [
                    ["c5", 0.1, -0.8, 0.0],
                    ["e5", 0.1, -0.4, 0.0],
                    ["g5", 0.1, 0.0, 0.0],
                    ["c6", 0.2, 0.4, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.01]
            },
            "tornello_abbinamento": {
                "descrizione": "Arpeggio rapido per generazione abbinamenti Tornello",
                "score": [
                    ["e5", 0.08, -0.5, 0.0],
                    ["g5", 0.08, 0.0, 0.0],
                    ["c6", 0.15, 0.5, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.01]
            },
            "tornello_chiusura": {
                "descrizione": "Arpeggio discendente di chiusura per l'uscita da Tornello",
                "score": [
                    ["c6", 0.1, 0.4, 0.0],
                    ["g5", 0.1, 0.0, 0.0],
                    ["e5", 0.1, -0.4, 0.0],
                    ["c5", 0.2, -0.8, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.01]
            },
            "tornello_time_machine": {
                "descrizione": "Effetto rewind per Time Machine",
                "score": [
                    ["g4", 0.08, -0.5, 0.0],
                    ["e4", 0.08, -0.2, 0.0],
                    ["c4", 0.15, 0.2, 0.0],
                    ["g3", 0.25, 0.5, 0.0]
                ],
                "kind": 1,
                "adsr": [0.02, 0.0, 100.0, 0.05]
            },
            "tornello_conclusione_turno": {
                "descrizione": "Accordo di conclusione turno",
                "score": [
                    ["c5", 0.15, -0.3, 0.0],
                    ["e5", 0.15, 0.3, 0.0],
                    ["g5", 0.3, 0.0, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.02]
            },
            "tornello_conclusione_torneo": {
                "descrizione": "Fanfara trionfale per la conclusione del torneo",
                "score": [
                    ["c5", 0.1, -0.5, 0.0],
                    ["e5", 0.1, -0.2, 0.0],
                    ["g5", 0.1, 0.2, 0.0],
                    ["c6", 0.15, 0.5, 0.0],
                    ["e6", 0.15, 0.0, 0.0],
                    ["g6", 0.4, 0.0, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.05]
            },
            "tornello_aggiunta_giocatore": {
                "descrizione": "Suono per aggiunta giocatore (due note ascendenti rapide)",
                "score": [
                    ["c5", 0.08, -0.5, 0.0],
                    ["g5", 0.15, 0.5, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.02]
            },
            "tornello_ritiro_giocatore": {
                "descrizione": "Suono per ritiro giocatore (due note discendenti tristi)",
                "score": [
                    ["f4", 0.15, 0.0, 0.0],
                    ["c4", 0.3, 0.0, 0.0]
                ],
                "kind": 1,
                "adsr": [0.02, 0.0, 100.0, 0.05]
            },
            "tornello_rimozione_giocatore": {
                "descrizione": "Suono per rimozione giocatore dalla lista",
                "score": [
                    ["g4", 0.1, -0.2, 0.0],
                    ["d4", 0.2, 0.2, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.02]
            },
            "tornello_pianifica_crea": {
                "descrizione": "Pianificazione partita creata",
                "score": [
                    ["d5", 0.08, -0.3, 0.0],
                    ["f5", 0.08, 0.0, 0.0],
                    ["a5", 0.15, 0.3, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.02]
            },
            "tornello_pianifica_modifica": {
                "descrizione": "Pianificazione partita modificata",
                "score": [
                    ["f5", 0.08, -0.3, 0.0],
                    ["d5", 0.08, 0.0, 0.0],
                    ["f5", 0.15, 0.3, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.02]
            },
            "tornello_pianifica_rimuovi": {
                "descrizione": "Pianificazione partita rimossa",
                "score": [
                    ["a5", 0.08, 0.3, 0.0],
                    ["f5", 0.08, 0.0, 0.0],
                    ["d5", 0.15, -0.3, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.02]
            },
            "tornello_risultato_1_0": {
                "descrizione": "Risultato 1-0: Bianco vince (pan a sinistra, arpeggio brillante)",
                "score": [
                    ["c5", 0.08, -0.8, 0.0],
                    ["e5", 0.08, -0.8, 0.0],
                    ["g5", 0.15, -0.8, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.01]
            },
            "tornello_risultato_0_1": {
                "descrizione": "Risultato 0-1: Nero vince (pan a destra, arpeggio brillante)",
                "score": [
                    ["c5", 0.08, 0.8, 0.0],
                    ["e5", 0.08, 0.8, 0.0],
                    ["g5", 0.15, 0.8, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.01]
            },
            "tornello_risultato_patta": {
                "descrizione": "Risultato patta: accordo equilibrato centrato",
                "score": [
                    ["e5", 0.12, 0.0, 0.0],
                    ["a5", 0.25, 0.0, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.03]
            },
            "tornello_risultato_1_F": {
                "descrizione": "Risultato 1-F: forfait Nero (pan a sinistra, toni alterni)",
                "score": [
                    ["c5", 0.1, -0.8, 0.0],
                    ["c4", 0.2, -0.8, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.02]
            },
            "tornello_risultato_F_1": {
                "descrizione": "Risultato F-1: forfait Bianco (pan a destra, toni alterni)",
                "score": [
                    ["c5", 0.1, 0.8, 0.0],
                    ["c4", 0.2, 0.8, 0.0]
                ],
                "kind": 1,
                "adsr": [0.01, 0.0, 100.0, 0.02]
            },
            "tornello_risultato_0_0F": {
                "descrizione": "Risultato 0-0F: doppio forfait (toni discendenti cupi)",
                "score": [
                    ["c4", 0.12, 0.0, 0.0],
                    ["b3", 0.12, 0.0, 0.0],
                    ["bb3", 0.25, 0.0, 0.0]
                ],
                "kind": 1,
                "adsr": [0.02, 0.0, 100.0, 0.04]
            }
        }

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

