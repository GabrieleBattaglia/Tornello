import datetime
import os
import re
import shutil

from babel.dates import format_date
from config import DATE_FORMAT_ISO, _, lingua_rilevata

from GBUtils import key


def nome_cartella_mese(mese):
    """Nome della sottocartella di un mese, per esempio "09 Settembre".
    Il numero davanti serve a tenere i mesi in ordine quando il gestore file li
    ordina per nome, mentre la parola segue la lingua scelta nel programma."""
    nomi = (
        _("Gennaio"),
        _("Febbraio"),
        _("Marzo"),
        _("Aprile"),
        _("Maggio"),
        _("Giugno"),
        _("Luglio"),
        _("Agosto"),
        _("Settembre"),
        _("Ottobre"),
        _("Novembre"),
        _("Dicembre"),
    )
    try:
        numero = max(1, min(12, int(mese)))
    except (TypeError, ValueError):
        numero = 1
    return f"{numero:02d} {nomi[numero - 1]}"


def cartella_per_data(radice, data=None, crea=True):
    """Percorso della sottocartella anno e mese dentro una radice, per esempio
    backup, 2026, 09 Settembre. Le due sottocartelle nascono solo quando c'e'
    davvero qualcosa da metterci dentro.
    Restituisce None se la cartella non si e' potuta creare."""
    if data is None:
        data = datetime.datetime.now()
    percorso = os.path.join(radice, f"{data.year:04d}", nome_cartella_mese(data.month))
    if crea:
        try:
            os.makedirs(percorso, exist_ok=True)
        except OSError:
            return None
    return percorso


def create_backup(filepath, context="backup"):
    """
    Crea una copia di backup del file specificato nella cartella 'backup'
    accanto all'applicazione, dentro le sottocartelle dell'anno e del mese in
    cui la copia viene fatta.
    Aggiunge un timestamp e il contesto al nome del file per non sovrascrivere backup precedenti.
    """
    if not os.path.exists(filepath):
        return False

    # La cartella va accanto all'applicazione, non nella directory da cui e'
    # stata avviata: con un percorso relativo le copie di sicurezza fatte prima
    # di finalizzazione, Time Machine e rollback finivano dove capitava, e
    # l'utente che doveva recuperare un torneo non le trovava.
    from config import user_data_path

    adesso = datetime.datetime.now()
    backup_dir = cartella_per_data(user_data_path("backup"), adesso)
    if not backup_dir:
        return False

    filename = os.path.basename(filepath)
    name, ext = os.path.splitext(filename)
    timestamp = adesso.strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{name}_{context}_{timestamp}{ext}"
    backup_path = os.path.join(backup_dir, backup_filename)

    try:
        shutil.copy2(filepath, backup_path)
        return True
    except OSError:
        return False


def elenca_file_di_backup(cartella_backup, limite_data=None):
    """Elenca i file di backup, scendendo nelle sottocartelle dell'anno e del
    mese. Restituisce due liste: tutti i file, dal piu' vecchio al piu'
    recente, e quelli piu' vecchi della data limite, se indicata.
    Ogni file e' un dizionario con nome, percorso, dimensione e data di
    ultima modifica."""
    tutti = []
    vecchi = []
    if not cartella_backup or not os.path.isdir(cartella_backup):
        return tutti, vecchi

    try:
        for cartella, _sottocartelle, files in os.walk(cartella_backup):
            for nome in files:
                percorso = os.path.join(cartella, nome)
                if not os.path.isfile(percorso):
                    continue
                dati = os.stat(percorso)
                modifica = datetime.datetime.fromtimestamp(dati.st_mtime)
                informazioni = {
                    "name": nome,
                    "path": percorso,
                    "size": dati.st_size,
                    "mtime": modifica,
                }
                tutti.append(informazioni)
                if limite_data is not None and modifica < limite_data:
                    vecchi.append(informazioni)
    except OSError:
        return tutti, vecchi

    tutti.sort(key=lambda f: f["mtime"])
    vecchi.sort(key=lambda f: f["mtime"])
    return tutti, vecchi


def rimuovi_cartelle_vuote(radice):
    """Toglie di mezzo le sottocartelle rimaste vuote sotto una radice, senza
    mai toccare la radice stessa. Serve alla cartella dei backup: quando i file
    di un mese vengono cancellati, la cartella del mese e poi quella dell'anno
    resterebbero li' a vuoto.
    Restituisce quante cartelle sono state rimosse."""
    if not radice or not os.path.isdir(radice):
        return 0
    rimosse = 0
    radice_assoluta = os.path.abspath(radice)
    # dal basso verso l'alto, cosi' una cartella dell'anno che resta vuota dopo
    # la rimozione dei mesi viene tolta nello stesso passaggio.
    for cartella, _sottocartelle, _files in os.walk(radice, topdown=False):
        if os.path.abspath(cartella) == radice_assoluta:
            continue
        try:
            if not os.listdir(cartella):
                os.rmdir(cartella)
                rimosse += 1
        except OSError:
            continue
    return rimosse


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
    from datetime import datetime

    from config import DATE_FORMAT_ISO

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


# Il volume delle impostazioni si legge una volta sola e si tiene da parte:
# prima veniva riletto da disco a ogni singolo suono, e i suoni sono tanti.
_volume_impostazioni = None


def invalida_volume_audio():
    """Da chiamare quando l'utente cambia il volume nelle impostazioni."""
    global _volume_impostazioni
    _volume_impostazioni = None


def _volume_base():
    """Il volume scelto dall'utente, da 0 a 1. Mezzo se non risulta niente."""
    global _volume_impostazioni
    if _volume_impostazioni is not None:
        return _volume_impostazioni
    volume = 0.5
    try:
        import json

        from config import user_data_path

        percorso = user_data_path("Tornello - Settings.json")
        if os.path.exists(percorso):
            with open(percorso, encoding="utf-8") as f:
                volume = json.load(f).get("volume", 50) / 100.0
    except (OSError, ValueError, ImportError):
        pass
    _volume_impostazioni = max(0.0, min(1.0, volume))
    return _volume_impostazioni


# Quale suono della collezione va con quale evento del programma. E' l'unica
# cosa che riguarda Tornello: leggere la collezione e convertirne i volumi lo
# fa Acusticator, che e' anche il solo a sapere dove trovarla da eseguibile.
EVENTI = {
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
    "notifica": "notifica",
}


def play_sound(event_name, torneo=None, sync=False):
    """
    Riproduce un effetto acustico per feedback utente.
    event_name puo' essere una delle chiavi di EVENTI, oppure direttamente il
    nome di un preset della collezione condivisa, che viene cercato tale e
    quale: e' il caso di apertura, spostamento, lista e simili.
    Il volume viene da quello scelto nelle impostazioni, o da base_volume del
    torneo se il torneo ne ha uno suo. Restituisce True se il suono e' partito.
    """
    from GBUtils import Acusticator

    volume = _volume_base()
    if torneo and isinstance(torneo, dict):
        volume = torneo.get("base_volume", volume)
    return Acusticator.play(
        EVENTI.get(event_name, event_name), sync=sync, volume=volume
    )


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

    if (
        not mandatory_terms
        and not exact_phrases
        and optional_terms
        and matched_optionals == 0
    ):
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


def cartella_scrivibile(percorso):
    """Vero se nella cartella si possono davvero creare file. Non basta
    controllare che esista: in Programmi la cartella c'e' ma la scrittura e'
    negata, ed e' li' che Tornello si fermava con un codice di errore."""
    if not percorso or not os.path.isdir(percorso):
        return False
    prova = os.path.join(percorso, ".tornello_write_test")
    try:
        with open(prova, "w") as f:
            f.write("test")
        os.remove(prova)
        return True
    except OSError:
        return False


def resolve_and_verify_save_path(path, default_fallback=None):
    """
    Verifica se il percorso personalizzato è valido e accessibile.
    - Se l'unità (drive letter) non è disponibile: fallback alla cartella di default + avviso.
    - Se la cartella specificata non esiste: prova a crearla. Se fallisce, fallback + avviso.
    - Logga l'operazione su console/stdout.
    Restituisce una tupla (resolved_path, warning_message).
    """
    if default_fallback is None:
        # Il ripiego e' la cartella del programma, non quella da cui e' stato
        # avviato: sono due cose diverse ogni volta che lo si lancia da altrove.
        from config import user_data_path

        default_fallback = os.path.abspath(user_data_path(""))

    if not path:
        return default_fallback, None

    # Normalizza il percorso
    path = os.path.abspath(path)
    drive, tail = os.path.splitdrive(path)

    # 1. Verifica disponibilità dell'unità (drive letter)
    if drive:
        drive_root = drive + os.sep
        if not os.path.exists(drive_root):
            msg = _(
                "L'unità '{drive}' non è disponibile. Uso la cartella di default: '{fallback}'."
            ).format(drive=drive, fallback=default_fallback)
            print(f"LOG: {msg}")
            return default_fallback, msg

    # 2. Verifica/creazione della cartella
    if not os.path.exists(path):
        try:
            os.makedirs(path, exist_ok=True)
            # Log dell'operazione di creazione
            msg_log = _("Creata cartella di salvataggio inesistente: '{path}'").format(
                path=path
            )
            print(f"LOG: {msg_log}")
            msg_user = _("La cartella '{path}' non esisteva ed è stata creata.").format(
                path=path
            )
            return path, msg_user
        except Exception as e:
            msg = _(
                "Impossibile creare la cartella '{path}': {error}. Uso la cartella di default: '{fallback}'."
            ).format(path=path, error=e, fallback=default_fallback)
            print(f"LOG: {msg}")
            return default_fallback, msg

    # Verifica se la cartella esistente è scrivibile
    if not cartella_scrivibile(path):
        msg = _(
            "La cartella '{path}' non e' scrivibile. Uso la cartella di default: '{fallback}'."
        ).format(path=path, fallback=default_fallback)
        print(f"LOG: {msg}")
        return default_fallback, msg

    return path, None
