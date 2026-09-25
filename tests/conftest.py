import hashlib
import json
import os
import sys
import tempfile

import pytest

# Aggiunge la cartella src al path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

RADICE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CARTELLA_SRC = os.path.join(RADICE, "src")

# Le costanti di percorso che i moduli calcolano all'importazione, e che
# percio' non seguono la deviazione di cartella_applicazione. Ognuna viene
# riportata sotto la cartella temporanea della prova, in qualunque modulo di
# Tornello se la sia copiata con un from config import. Restano vere soltanto
# le risorse in sola lettura, cioe' le traduzioni, la cartella del motore e il
# suo eseguibile.
COSTANTI_DI_DATI = (
    "PLAYER_DB_FILE",
    "PLAYER_DB_TXT_FILE",
    "ARCHIVED_TOURNAMENTS_DIR",
    "FIDE_DB_LOCAL_FILE",
    "FIDE_DB_JSON_LEGACY",
    "BBP_INPUT_TRF",
    "BBP_OUTPUT_COUPLES",
    "BBP_OUTPUT_CHECKLIST",
    "SETTINGS_FILE",
    "project_root",
    "selected_lang_file",
)


def moduli_di_tornello():
    """I moduli caricati che vengono dalla cartella src del progetto."""
    for modulo in list(sys.modules.values()):
        file = getattr(modulo, "__file__", None)
        if file and os.path.abspath(file).startswith(CARTELLA_SRC + os.sep):
            yield modulo


def nella_radice_vera(percorso):
    """Vero se il percorso cade dentro la cartella vera del progetto."""
    assoluto = os.path.abspath(percorso)
    return assoluto == RADICE or assoluto.startswith(RADICE + os.sep)


COSTANTI_DEL_MOTORE = ("BBP_INPUT_TRF", "BBP_OUTPUT_COUPLES", "BBP_OUTPUT_CHECKLIST")
_percorsi_veri = {}


def percorsi_veri():
    """Il valore vero di ogni costante di dati, preso da config la prima
    volta, cioe' prima che una prova lo devii. Una volta deviato, il valore
    che un modulo si porta dietro non dice piu' niente: un modulo importato
    per la prima volta dentro una prova si copia la cartella temporanea di
    quella prova, e la tiene anche dopo. Per questo le costanti si riconoscono
    dal nome e non dal valore."""
    if not _percorsi_veri:
        import config

        for nome in COSTANTI_DI_DATI:
            if hasattr(config, nome):
                _percorsi_veri[nome] = os.path.abspath(getattr(config, nome))
        _percorsi_veri["SETTINGS_FILE"] = os.path.join(RADICE, "Tornello - Settings.json")
    return _percorsi_veri


@pytest.fixture(autouse=True)
def dati_in_cartella_temporanea(tmp_path, tmp_path_factory, monkeypatch):
    """Tutto cio' che il programma scrive finisce nella cartella temporanea
    della prova: tornei, archivio, database dei giocatori, impostazioni, copie
    di sicurezza, error.log e file di lavoro del motore di abbinamento.
    Fino alla 10.3.1 la deviazione valeva solo per la cartella backup, e il
    torneo in corso e il database veri restavano fuori dalla portata delle
    prove solo perche' ognuna di esse applicava le sue sostituzioni: le prove
    e2e scrivevano per un attimo due tornei nella radice, e quelle del motore
    riscrivevano i file che il programma usa quando abbina un turno.
    La radice dei dati la dice cartella_applicazione, chiesta da percorsi.py a
    ogni chiamata: sostituendo quel nome dentro percorsi, la deviazione vale
    per tutti i moduli, anche per quelli che hanno importato user_data_path in
    cima. Poi si riportano sotto la cartella temporanea le costanti calcolate
    all'importazione.
    """
    import config
    import percorsi

    veri = percorsi_veri()
    monkeypatch.setattr(percorsi, "cartella_applicazione", lambda: str(tmp_path))
    # I file di lavoro del motore vanno in una cartella a parte, fuori da
    # quella della prova: diverse prove elencano cio' che trovano nella loro
    # cartella, e una sottocartella in piu' le farebbe fallire.
    motore = tmp_path_factory.mktemp("motore")
    deviati = {}
    for nome, vero in veri.items():
        if nome in COSTANTI_DEL_MOTORE:
            deviati[nome] = str(motore / os.path.basename(vero))
        else:
            relativo = os.path.relpath(vero, RADICE)
            deviati[nome] = str(tmp_path) if relativo == "." else str(tmp_path / relativo)

    for modulo in moduli_di_tornello():
        for nome, nuovo in deviati.items():
            if isinstance(getattr(modulo, nome, None), str):
                monkeypatch.setattr(modulo, nome, nuovo)
    # config e' sempre fra i moduli caricati: lo importa questa stessa
    # fixture, cosi' anche un modulo importato per la prima volta dentro una
    # prova si copia i valori gia' deviati.
    assert config.PLAYER_DB_FILE.startswith(str(tmp_path))


# La sentinella. Qualunque cosa sfugga alla deviazione qui sopra, oggi o con
# un modulo scritto domani, la suite non deve poter cambiare i file veri senza
# che qualcuno se ne accorga. Si prende l'impronta dei file della radice, dei
# tornei archiviati, dei file di lavoro del motore e delle copie di sicurezza
# prima della prima prova, e la si confronta dopo l'ultima. I file molto grandi,
# come il database FIDE, si riconoscono da misura e data invece che
# dall'impronta, che costerebbe secondi a ogni esecuzione.
SOGLIA_IMPRONTA = 20 * 1024 * 1024
CARTELLE_SORVEGLIATE = ("Closed Tournaments", "bbppairings", "backup")


def _file_sorvegliati():
    for voce in os.scandir(RADICE):
        if voce.is_file():
            yield voce.path
    for cartella in CARTELLE_SORVEGLIATE:
        for radice, _cartelle, files in os.walk(os.path.join(RADICE, cartella)):
            for nome in files:
                yield os.path.join(radice, nome)


def _fotografia():
    """Per ogni file sorvegliato l'impronta, e per i piccoli anche il
    contenuto, cosi' da poterlo mettere in salvo se la suite lo cambia."""
    impronte, contenuti = {}, {}
    for percorso in _file_sorvegliati():
        relativo = os.path.relpath(percorso, RADICE)
        stato = os.stat(percorso)
        if stato.st_size > SOGLIA_IMPRONTA:
            impronte[relativo] = (stato.st_size, stato.st_mtime_ns)
            continue
        with open(percorso, "rb") as f:
            dati = f.read()
        impronte[relativo] = hashlib.sha256(dati).hexdigest()
        contenuti[relativo] = dati
    return impronte, contenuti


@pytest.fixture(scope="session", autouse=True)
def sentinella_dei_file_veri():
    """Fa fallire la suite se una prova ha cambiato, creato o tolto un file
    vero del progetto. Non rimette niente a posto da sola: se Tornello e'
    aperto mentre la suite gira e salva il torneo, quel cambiamento e' buono,
    e una sentinella che ripristinasse lo cancellerebbe. Mette invece in salvo
    le versioni di prima in una cartella temporanea e ne dice il nome; in ogni
    caso i json dei tornei e il database stanno anche su GitHub."""
    prima, contenuti = _fotografia()
    yield
    dopo, _ = _fotografia()
    cambiati = sorted(n for n in prima.keys() & dopo.keys() if prima[n] != dopo[n])
    comparsi = sorted(dopo.keys() - prima.keys())
    spariti = sorted(prima.keys() - dopo.keys())
    if not (cambiati or comparsi or spariti):
        return
    salvataggio = tempfile.mkdtemp(prefix="tornello_sentinella_")
    for nome in cambiati + spariti:
        if nome in contenuti:
            destinazione = os.path.join(salvataggio, nome)
            os.makedirs(os.path.dirname(destinazione), exist_ok=True)
            with open(destinazione, "wb") as f:
                f.write(contenuti[nome])
    righe = ["La suite ha toccato file veri del progetto."]
    righe += [f"Cambiato: {n}" for n in cambiati]
    righe += [f"Comparso: {n}" for n in comparsi]
    righe += [f"Sparito: {n}" for n in spariti]
    righe.append(f"Le versioni di prima sono in {salvataggio}")
    pytest.fail("\n".join(righe))


@pytest.fixture
def sample_tournament_dict():
    """Carica un torneo reale salvato per i test."""
    # Il file viene cercato dentro l'archivio invece di puntare a una cartella
    # precisa: dalla versione 9.7.0 l'archivio e' ordinato per anno e mese, e
    # un percorso fisso si romperebbe a ogni riordino.
    archivio = os.path.join(RADICE, "Closed Tournaments")
    atteso = "Tornello - ASCId_Primavera_1.json"
    for radice, _cartelle, files in os.walk(archivio):
        if atteso in files:
            with open(os.path.join(radice, atteso), encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(f"Torneo di prova non trovato nell'archivio: {atteso}")


@pytest.fixture(scope="session")
def app_grafica():
    """Applicazione wx condivisa da tutte le prove che costruiscono finestre.
    Crearne una per prova fa cadere l'interprete: wx ne ammette una sola per
    processo. Se l'interfaccia grafica non e' disponibile, le prove che la
    chiedono vengono saltate."""
    try:
        import wx
    except ImportError as errore:  # pragma: no cover
        pytest.skip(f"wxPython non disponibile: {errore}")

    applicazione = wx.App(False)
    yield applicazione
    applicazione.Destroy()
