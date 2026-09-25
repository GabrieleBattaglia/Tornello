import datetime
import json
import os
import re
import shutil
import sys
import tempfile

from babel.dates import format_date
from GBUtils import enter_escape as enter_escape_condivisa

from config import DATE_FORMAT_ISO, _, lingua_rilevata


def scrivi_json_atomico(percorso, dati, indent=1):
    """Scrive un file JSON senza correre il rischio di lasciarlo a meta'.
    Il contenuto va prima in un file temporaneo nella stessa cartella, viene
    scaricato sul disco e solo allora prende il posto del file buono con una
    sostituzione, che il sistema operativo esegue in un colpo solo.
    Scrivendo direttamente sul file definitivo, un arresto del programma o della
    macchina a meta' operazione lascerebbe il vecchio contenuto gia' troncato e
    il nuovo incompleto: per il database dei giocatori, che contiene anagrafica,
    Elo, medaglie e storico, sarebbe una perdita non rimediabile.
    Le eccezioni vengono lasciate salire, perche' i chiamanti le gestiscono
    gia'; il file temporaneo non resta mai in giro.
    """
    cartella = os.path.dirname(os.path.abspath(percorso)) or "."
    os.makedirs(cartella, exist_ok=True)
    temporaneo = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=cartella,
            prefix=".tornello_",
            suffix=".tmp",
            delete=False,
        ) as f:
            temporaneo = f.name
            json.dump(dati, f, indent=indent, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporaneo, percorso)
        return True
    except Exception:
        if temporaneo and os.path.exists(temporaneo):
            try:
                os.remove(temporaneo)
            except OSError:
                pass
        raise


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


def create_backup(filepath, context="backup", cartella_backup=None):
    """
    Crea una copia di backup del file specificato nella cartella 'backup'
    accanto all'applicazione, dentro le sottocartelle dell'anno e del mese in
    cui la copia viene fatta.
    Aggiunge un timestamp e il contesto al nome del file per non sovrascrivere backup precedenti.
    Risponde vero se la copia e' nata; il lavoro lo fa copia_di_sicurezza,
    che dice anche dove.
    """
    return copia_di_sicurezza(filepath, context, cartella_backup) is not None


def copia_di_sicurezza(filepath, context="backup", cartella_backup=None):
    """La copia di create_backup, che restituisce il percorso della copia
    appena nata, oppure None se la copia non si e' potuta fare. Serve a chi
    deve rileggerla prima di togliere l'originale, come la finalizzazione
    ripetuta che mette da parte i suoi file (10.8.9).
    Due copie dello stesso file e dello stesso contesto nello stesso secondo
    avrebbero lo stesso nome: fino alla 10.8.10 la seconda cancellava la
    prima senza dire niente, per esempio le due copie pre_finalize_db che la
    console faceva di fila. Adesso la seconda prende il suffisso _2, la terza
    _3 e cosi' via, e nessuna copia viene mai sovrascritta.
    cartella_backup e' la radice delle copie; senza, quella accanto al
    programma. Dalla 10.10.0 la passa il ripristino (copie_di_sicurezza.py),
    che riceve tutti i suoi percorsi da chi lo chiama.
    """
    if not os.path.exists(filepath):
        return None

    # La cartella va accanto all'applicazione, non nella directory da cui e'
    # stata avviata: con un percorso relativo le copie di sicurezza fatte prima
    # di finalizzazione, Time Machine e rollback finivano dove capitava, e
    # l'utente che doveva recuperare un torneo non le trovava.
    if cartella_backup is None:
        from config import user_data_path

        cartella_backup = user_data_path("backup")

    adesso = datetime.datetime.now()
    backup_dir = cartella_per_data(cartella_backup, adesso)
    if not backup_dir:
        return None

    filename = os.path.basename(filepath)
    name, ext = os.path.splitext(filename)
    timestamp = adesso.strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{name}_{context}_{timestamp}{ext}"
    backup_path = os.path.join(backup_dir, backup_filename)
    numero = 2
    while os.path.exists(backup_path):
        backup_path = os.path.join(
            backup_dir, f"{name}_{context}_{timestamp}_{numero}{ext}"
        )
        numero += 1

    try:
        shutil.copy2(filepath, backup_path)
    except OSError:
        return None
    return backup_path


# La data scritta da create_backup in fondo al nome, prima dell'estensione,
# con il suffisso _2, _3 delle copie nate nello stesso secondo.
DATA_NEL_NOME_DELLA_COPIA = re.compile(r"_(\d{8})_(\d{6})(?:_\d+)?$")


def data_della_copia(percorso):
    """Il momento in cui e' nata una copia di sicurezza, letto dalla data che
    create_backup scrive nel nome del file, per esempio
    Tornello - Autunneo2_chiusura_torneo_20260923_160512.json.
    La data di modifica del file non dice quando e' nata la copia: shutil.copy2
    conserva quella dell'originale, e le copie di chiusura del database fatte
    il 23 settembre risultavano del 13, l'ultimo giorno in cui il database era
    cambiato. Fino alla 10.8.10 l'eta' delle copie si misurava cosi', e con
    lei il consiglio dei 18 mesi e l'indicatore BK del pie' di pagina.
    Solo per i file senza la data nel nome, o con una data impossibile, si
    ripiega sulla data di modifica. Nata come data_del_backup in
    riordina_archivio_e_backup.py, che ora la importa da qui.
    """
    base = os.path.splitext(os.path.basename(percorso))[0]
    trovata = DATA_NEL_NOME_DELLA_COPIA.search(base)
    if trovata:
        try:
            return datetime.datetime.strptime(
                trovata.group(1) + trovata.group(2), "%Y%m%d%H%M%S"
            )
        except ValueError:
            pass
    return datetime.datetime.fromtimestamp(os.path.getmtime(percorso))


def dentro_la_cartella(percorso, cartella):
    """Vero se il percorso sta dentro la cartella, a qualunque profondita'.
    Il confronto si fa sui percorsi assoluti e risolti, senza badare alle
    maiuscole come fa Windows."""
    if not percorso or not cartella:
        return False
    try:
        file_risolto = os.path.normcase(os.path.realpath(percorso))
        cartella_risolta = os.path.normcase(os.path.realpath(cartella))
        return (
            os.path.commonpath([file_risolto, cartella_risolta]) == cartella_risolta
            and file_risolto != cartella_risolta
        )
    except (OSError, ValueError):
        # Unita' diverse o percorso illeggibile: non sta dentro.
        return False


def stessi_byte(primo, secondo):
    """Vero se i due file si leggono e hanno esattamente lo stesso contenuto."""
    try:
        with open(primo, "rb") as f_primo, open(secondo, "rb") as f_secondo:
            return f_primo.read() == f_secondo.read()
    except OSError:
        return False


def copie_di_chiusura(percorso_torneo):
    """Le copie di sicurezza fatte alla chiusura del programma: il torneo
    aperto, se c'e', e l'archivio dei giocatori. Con quelle di ogni turno
    proteggono il lavoro di tutti i giorni (issue 45).
    Dalla 10.11.0 una copia identica, byte per byte, all'ultima copia dello
    stesso file non nasce: le tre copie di chiusura del database fatte il 23
    settembre 2026 erano uguali fra loro e al database, e ogni chiusura senza
    lavoro ne aggiungeva un'altra (issue 39).
    """
    from config import PLAYER_DB_FILE, user_data_path

    cartella = user_data_path("backup")
    if percorso_torneo:
        _copia_se_cambiato(percorso_torneo, "chiusura_torneo", cartella)
    _copia_se_cambiato(PLAYER_DB_FILE, "chiusura_db", cartella)


def _copia_se_cambiato(percorso, contesto, cartella_backup):
    """La copia di chiusura di un file, se il file e' diverso dalla sua
    ultima copia, di qualunque momento."""
    from copie_di_sicurezza import ultima_copia_di

    ultima = ultima_copia_di(percorso, cartella_backup)
    if ultima and stessi_byte(percorso, ultima):
        return
    create_backup(percorso, contesto, cartella_backup)


def cestino_disponibile(percorso):
    """Vero se il disco del percorso ha il cestino di Windows. Lo chiede alla
    Shell con SHQueryRecycleBinW sulla radice del disco: su una cartella di
    rete risponde con un errore. Fuori da Windows risponde vero, e decide
    send2trash."""
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        from ctypes import wintypes

        class SHQUERYRBINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("i64Size", ctypes.c_longlong),
                ("i64NumItems", ctypes.c_longlong),
            ]

        radice = os.path.splitdrive(os.path.abspath(percorso))[0] + "\\"
        informazioni = SHQUERYRBINFO()
        informazioni.cbSize = ctypes.sizeof(SHQUERYRBINFO)
        esito = ctypes.windll.shell32.SHQueryRecycleBinW(
            radice, ctypes.byref(informazioni)
        )
    except (OSError, AttributeError, ValueError, TypeError):
        return False
    return esito == 0


def delete_file_to_trash(path, finestra=None):
    """Manda nel Cestino di Windows un file o una cartella, e risponde vero
    solo se dal suo posto e' sparito davvero.
    Fino alla 10.9.0 l'ultimo ripiego era os.remove, che cancella per sempre:
    dalla 10.10.0 le cancellazioni vanno sempre nel cestino (decisione di
    Gabriele). Su un disco senza cestino, per esempio una cartella di rete,
    il file resta dov'e' e la risposta e' falso, senza chiedere niente: la
    Shell, a cui non arriva nemmeno, chiederebbe se cancellarlo per sempre.
    Se il cestino c'e' ma non puo' prendere il file, per esempio perche' e'
    piu' grande del cestino o perche' il cestino di quel disco e' impostato
    per cancellare subito, la Shell riceve FOF_WANTNUKEWARNING e chiede prima
    di cancellare per sempre, invece di farlo in silenzio. finestra e'
    l'handle della finestra da cui parte la cancellazione: la domanda le
    appartiene, e prende il fuoco invece di restare nascosta dietro una
    finestra modale. Su Windows, dopo la Shell, non si ritenta con
    send2trash, che la stessa domanda non la farebbe.
    Nata in backup_cleanup_dialog.py, che la importa da qui, come
    copie_di_sicurezza.py (issue 39).
    """
    path_abs = os.path.abspath(path)
    if not os.path.exists(path_abs):
        return False
    if sys.platform == "win32":
        if not cestino_disponibile(path_abs):
            return False
        try:
            import ctypes
            from ctypes import wintypes

            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR),
                    ("fFlags", ctypes.c_ushort),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID),
                    ("lpszProgressTitle", wintypes.LPCWSTR),
                ]

            FO_DELETE = 3
            FOF_ALLOWUNDO = 0x0040
            FOF_NOCONFIRMATION = 0x0010
            FOF_NOERRORUI = 0x0400
            FOF_SILENT = 0x0004
            FOF_WANTNUKEWARNING = 0x4000

            fileop = SHFILEOPSTRUCTW()
            fileop.hwnd = finestra
            fileop.wFunc = FO_DELETE
            # La Shell vuole l'elenco dei percorsi chiuso da due caratteri nulli.
            fileop.pFrom = path_abs + "\0\0"
            fileop.pTo = None
            fileop.fFlags = (
                FOF_ALLOWUNDO
                | FOF_NOCONFIRMATION
                | FOF_NOERRORUI
                | FOF_SILENT
                | FOF_WANTNUKEWARNING
            )
            fileop.fAnyOperationsAborted = False
            fileop.hNameMappings = None
            fileop.lpszProgressTitle = None

            esito = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(fileop))
        except (OSError, AttributeError, ValueError, TypeError):
            return False
        return esito == 0 and not os.path.exists(path_abs)

    try:
        from send2trash import send2trash

        send2trash(path_abs)
    except (ImportError, OSError):
        return False
    return not os.path.exists(path_abs)


def elenca_file_di_backup(cartella_backup, limite_data=None):
    """Elenca i file di backup, scendendo nelle sottocartelle dell'anno e del
    mese. Restituisce due liste: tutti i file, dal piu' vecchio al piu'
    recente, e quelli piu' vecchi della data limite, se indicata.
    Ogni file e' un dizionario con nome, percorso, dimensione e data della
    copia, letta dal nome con data_della_copia. Fino alla 10.8.10 la chiave
    era mtime e conteneva la data di modifica, cioe' quella dell'originale."""
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
                nascita = data_della_copia(percorso)
                informazioni = {
                    "name": nome,
                    "path": percorso,
                    "size": dati.st_size,
                    "data": nascita,
                }
                tutti.append(informazioni)
                if limite_data is not None and nascita < limite_data:
                    vecchi.append(informazioni)
    except OSError:
        return tutti, vecchi

    tutti.sort(key=lambda f: f["data"])
    vecchi.sort(key=lambda f: f["data"])
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
    """Attende Invio o Escape, restituendo vero sul primo e falso sul secondo.
    La logica sta in GBUtils, come tutte le utilita' condivise: qui resta solo
    il passaggio del messaggio di guida nella lingua scelta, che la funzione
    condivisa non puo' tradurre da sola."""
    return enter_escape_condivisa(
        prompt, guida=_("Conferma con invio o annulla con escape")
    )


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


def file_del_torneo(nome_file, nome_sanitizzato):
    """Vero se nome_file, senza cartella, e' uno dei file del torneo il cui
    nome ripulito da sanitize_filename e' nome_sanitizzato: il json, un
    report, oppure il riepilogo della creazione sospesa.
    Non basta che il file cominci allo stesso modo, e fino alla 10.3.3 era
    proprio cosi': eliminare il torneo Autunneo cancellava anche i file di
    Autunneo2, uno chiamato P si portava via il database Players_db, e la
    finalizzazione spostava in archivio i file degli altri tornei con lo
    stesso inizio. Il nome deve finire dove cominciano i suffissi che Tornello
    aggiunge; il nome ripulito non contiene spazi, quindi " - " dopo di lui
    e' un confine sicuro anche per i report tradotti.
    """
    radice = f"Tornello - {nome_sanitizzato}"
    return (
        nome_file in (f"{radice}.json", f"{radice}_sospeso.txt")
        or nome_file.startswith(f"{radice} - ")
    )


# Un titolo del manuale comincia con il numero della sezione: "3. " per un
# capitolo, "2.3.1 " per una sezione interna.
_TITOLO_DEL_MANUALE = re.compile(r"^(\d+(?:\.\d+)*)(\.?) (\S.*)$")


def _numero_del_titolo(righe, i):
    """Il numero della riga i, come "2.3.1" o "3", se e' un titolo del
    manuale; altrimenti None. Il testo di un titolo e' tutto maiuscolo fuori
    dalle parentesi, come "2.3 LA BARRA DI STATO INFERIORE (Tasto F7)". Un
    capitolo ha il punto dopo il numero e la riga vuota prima, che lo
    distingue dalle voci degli elenchi numerati come "4. ARO (Average Rating
    of Opponents)"; una sezione interna no, perche' gli elenchi non usano mai
    il numero col punto in mezzo. E' la stessa regola che tests/test_manuale.py
    controlla su tutto il manuale."""
    m = _TITOLO_DEL_MANUALE.match(righe[i])
    if not m:
        return None
    numero, punto, testo = m.groups()
    capitolo = "." not in numero
    if capitolo != (punto == "."):
        return None
    if capitolo and i > 0 and righe[i - 1].strip():
        return None
    fuori = re.sub(r"\([^)]*\)", "", testo)
    if fuori != fuori.upper() or not any(c.isalpha() for c in fuori):
        return None
    return numero


def sezione_del_manuale(testo, numero):
    """La sezione del manuale con il numero dato, per esempio "2.3.1": dal
    suo titolo compreso fino al titolo seguente escluso, di qualunque livello,
    senza le righe vuote in coda. La sezione di un capitolo si ferma quindi
    alla sua prima sezione interna. None se nel testo non c'e'.
    Dalla 10.5.3 il manuale non ha piu' righe di separatori: la fine la segna
    soltanto il titolo seguente. Issue 54."""
    righe = testo.splitlines()
    titoli = [i for i in range(len(righe)) if _numero_del_titolo(righe, i)]
    for posizione, inizio in enumerate(titoli):
        if _numero_del_titolo(righe, inizio) != numero:
            continue
        fine = titoli[posizione + 1] if posizione + 1 < len(titoli) else len(righe)
        sezione = righe[inizio:fine]
        while sezione and not sezione[-1].strip():
            sezione.pop()
        return "\n".join(sezione)
    return None


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
    # Dalla 10.3.1 i controlli della finestra di programmazione hanno una
    # sinusoide di 45 ms al posto della campanella, troppo invadente (issue 48).
    "controllo_programmazione": "meditimer_giro",
    # Dalla 10.6.1 anche la finestra dei risultati lascia la campanella, troppo
    # aggressiva: un suono all'apertura e uno diverso sui quattro pulsanti
    # Pianifica, Ritira, Annulla e Conferma. Due preset che in Tornello non
    # suonano per nient'altro, scelti in prova: quelli definitivi li decide
    # l'ascolto di Gabriele (issue 51).
    "apertura_risultati": "meditimer_tempo_trascorso",
    "controllo_risultati": "gabryscola_gioca_carta",
    # Dalla 10.10.0 un ripristino riuscito dalla finestra Copie di
    # sicurezza: tre tic veloci che salgono, un preset che Tornello non usa
    # per nient'altro. Provvisorio fino all'ascolto di Gabriele (issue 39).
    "ripristino": "meditimer_banco_salvato",
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


def bip_di_scelta(indice, quante, torneo=None):
    """Un bip sinusoidale breve, tanto piu' acuto quanto piu' avanti e' la
    voce scelta in un elenco: ventiquattro altezze per le ventiquattro ore,
    dodici per i minuti, una per ogni giorno. Serve alle scelte della finestra
    di programmazione, dalla 10.3.0 (issue 48): la posizione si sente prima
    che la dica lo screen reader. Un semitono per voce a partire dal do
    centrale, piu' stretti se le voci superano le tre ottave.
    """
    from GBUtils import Acusticator

    volume = _volume_base()
    if torneo and isinstance(torneo, dict):
        volume = torneo.get("base_volume", volume)
    passo = min(1.0, 36 / max(quante - 1, 1))
    frequenza = 261.63 * 2 ** (indice * passo / 12)
    Acusticator([frequenza, 0.04, 0, volume], kind=1, adsr=[10, 0, 100, 30])


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
    if first_name.startswith(first_term):
        return (2, last_name, first_name)
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
