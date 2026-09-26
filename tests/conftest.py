import hashlib
import importlib
import inspect
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


# La guardia delle finestre vere, dalla 10.13.22. Una prova non deve mai
# poter aprire una finestra sullo schermo di chi la lancia: il 26 settembre
# 2026 una finestra Errore, arrivata da un dialogo che la prova non aveva
# sostituito, e' rimasta dieci minuti sullo schermo di Gabriele, che non la
# vede e con NVDA se la ritrova davanti senza sapere da dove venga. Prima di
# ogni prova si sostituiscono percio' i metodi ShowModal scritti nel C++ di
# wx, quello di wx.Dialog e quelli delle sue sottoclassi che ne hanno uno
# proprio, le funzioni di wx che aprono da sole una finestra e aspettano la
# risposta, come wx.MessageBox, e il metodo Show delle finestre di primo
# livello e di quelle a comparsa. I dialoghi di Tornello ereditano il
# ShowModal di wx.Dialog, o di una sottoclasse di wx, e un ShowModal scritto
# in Python che chiama super() ci arriva lo stesso.
# Non basta: alcune finestre si mostrano da sole nel C++ appena create, senza
# passare dal Show di Python, come la barra di avanzamento di wx.ProgressDialog
# e l'avviso di wx.BusyInfo, e altri metodi aprono qualcosa sullo schermo
# senza essere un Show, come il menu contestuale di PopupMenu, che si ferma ad
# aspettare una scelta proprio come la finestra Errore di quella mattina. Le
# prime si sostituiscono con una classe che si ferma prima di creare
# qualunque cosa, i secondi come i ShowModal. Si fermano anche il browser e i
# programmi che Windows apre per un file.
# Una prova che vuole una risposta sostituisce il dialogo o il metodo con
# monkeypatch, come ha sempre fatto: la sua sostituzione viene dopo quella
# della guardia e la copre.
FUNZIONI_MODALI_DI_WX = (
    "MessageBox",
    "GetTextFromUser",
    "GetPasswordFromUser",
    "GetNumberFromUser",
    "GetSingleChoice",
    "FileSelector",
    "FileSelectorEx",
    "DirSelector",
    "LoadFileSelector",
    "SaveFileSelector",
    "GetColourFromUser",
    "GetFontFromUser",
)
FUNZIONI_MODALI_DI_WX_ADV = ("AboutBox", "GenericAboutBox", "ShowTip")
METODI_MODALI = ("ShowModal", "ShowWindowModal")
METODI_CHE_MOSTRANO = ("Show", "ShowWithoutActivating", "ShowWithEffect", "ShowFullScreen")
# Le classi che si mostrano da sole appena create, modulo per modulo.
CLASSI_CHE_SI_MOSTRANO_DA_SOLE = (
    ("wx", ("ProgressDialog", "GenericProgressDialog", "BusyInfo", "TipWindow")),
    ("wx.adv", ("SplashScreen",)),
)
# I metodi che aprono qualcosa sullo schermo senza passare da Show: menu
# contestuali, finestre a comparsa, tendine, procedure guidate, stampa,
# notifiche e icona nell'area di notifica. Valgono anche per le sottoclassi.
METODI_CHE_APRONO = (
    ("wx", "Window", ("PopupMenu", "GetPopupMenuSelectionFromUser")),
    ("wx", "PopupTransientWindow", ("Popup",)),
    ("wx", "ComboBox", ("Popup",)),
    ("wx", "ComboCtrl", ("Popup",)),
    ("wx", "PrintDialog", ("ShowModal",)),
    ("wx", "PageSetupDialog", ("ShowModal",)),
    ("wx", "Printer", ("Print", "PrintDialog", "Setup")),
    ("wx", "PrintPreview", ("Print",)),
    ("wx.adv", "Wizard", ("RunWizard",)),
    ("wx.adv", "NotificationMessage", ("Show",)),
    ("wx.adv", "RichToolTip", ("ShowFor",)),
    ("wx.adv", "TaskBarIcon", ("SetIcon", "ShowBalloon", "PopupMenu")),
    ("wx.html", "HtmlEasyPrinting", ("PageSetup", "PreviewFile", "PreviewText", "PrintFile", "PrintText")),
)
# Fuori da wx: il browser, e il programma che Windows associa a un file.
FUNZIONI_CHE_APRONO_ALTRI_PROGRAMMI = (
    ("webbrowser", ("open", "open_new", "open_new_tab")),
    ("os", ("startfile",)),
)


def _sottoclassi(classe):
    for figlia in classe.__subclasses__():
        yield figlia
        yield from _sottoclassi(figlia)


def _classi_con_metodo_nativo(radice, nome):
    """La radice e le sue sottoclassi, gia' definite, che hanno un metodo con
    quel nome scritto nel C++ di wx. Un metodo scritto in Python, per esempio
    la sostituzione di una prova, resta com'e'."""
    for classe in (radice, *_sottoclassi(radice)):
        metodo = classe.__dict__.get(nome)
        if metodo is not None and not inspect.isfunction(metodo):
            yield classe


class GuardiaDelleFinestre:
    """Sostituisce cio' che aprirebbe una finestra vera e annota ogni
    chiamata. La chiamata fa fallire la prova subito, con un'eccezione che il
    codice di Tornello non puo' ingoiare, perche' non deriva da Exception; se
    la fa comunque sparire qualcun altro, per esempio wx, che stampa l'errore
    di un gestore di eventi e prosegue, la prova fallisce alla fine."""

    def __init__(self):
        self.chiamate = []

    def vieta(self, descrizione):
        messaggio = (
            f"La prova ha chiamato {descrizione} vero, che aprirebbe una finestra "
            "sullo schermo. Va sostituito con monkeypatch prima di arrivarci, per "
            "esempio con una classe finta che risponde, come fanno le altre prove."
        )
        self.chiamate.append(messaggio)
        pytest.fail(messaggio, pytrace=True)

    def funzione(self, descrizione):
        def vietata(*_argomenti, **_opzioni):
            self.vieta(descrizione)

        vietata.guardia_delle_finestre = True
        return vietata

    def classe_vietata(self, descrizione):
        """Al posto di una classe che si mostra da sola appena creata: la
        creazione si ferma prima di arrivare al C++. Resta una classe, cosi'
        isinstance non si rompe, e una sottoclasse si ferma anche lei."""
        guardia = self

        class Vietata:
            guardia_delle_finestre = True

            def __new__(cls, *_argomenti, **_opzioni):
                guardia.vieta(descrizione)

        Vietata.__name__ = Vietata.__qualname__ = descrizione.rsplit(".", 1)[-1]
        return Vietata

    def metodo_modale(self, classe, nome):
        def vietato(finestra, *_argomenti, **_opzioni):
            self.vieta(f"{classe.__name__}.{nome} di {type(finestra).__name__}")

        vietato.guardia_delle_finestre = True
        return vietato

    def metodo_che_mostra(self, wx, classe, nome):
        """Show e i suoi fratelli valgono per tutte le finestre, anche per i
        controlli dentro una finestra mai mostrata, che restano invisibili:
        si ferma solo una finestra di primo livello, o una finestra a
        comparsa, che si mostrerebbe. In Show e ShowFullScreen il primo
        argomento dice se mostrare o nascondere."""
        originale = getattr(classe, nome)

        def mostra(finestra, *argomenti, **opzioni):
            mostrare = argomenti[0] if argomenti and nome in ("Show", "ShowFullScreen") else opzioni.get("show", True)
            if mostrare and isinstance(finestra, (wx.TopLevelWindow, wx.PopupWindow)):
                self.vieta(f"{nome} di {type(finestra).__name__}")
            return originale(finestra, *argomenti, **opzioni)

        mostra.guardia_delle_finestre = True
        return mostra

    def verifica(self, esito_della_prova):
        """A prova finita: se una finestra vera e' stata chiesta e la prova
        non e' gia' fallita per questo, fallisce adesso."""
        if self.chiamate and not (esito_della_prova is not None and esito_della_prova.failed):
            pytest.fail("\n".join(self.chiamate), pytrace=False)


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """Annota sulla prova l'esito di ogni fase: alla guardia serve sapere se
    la prova e' gia' fallita per una finestra vera."""
    rapporto = yield
    setattr(item, f"esito_{rapporto.when}", rapporto)
    return rapporto


@pytest.fixture(autouse=True)
def nessuna_finestra_vera(request, monkeypatch):
    """La guardia delle finestre vere, su ogni prova. Senza wxPython non c'e'
    niente da sorvegliare."""
    try:
        import wx
        import wx.adv
        import wx.html
    except ImportError:  # pragma: no cover
        yield None
        return

    guardia = GuardiaDelleFinestre()
    moduli = {"wx": wx, "wx.adv": wx.adv, "wx.html": wx.html}
    for nome in FUNZIONI_MODALI_DI_WX:
        if hasattr(wx, nome):
            monkeypatch.setattr(wx, nome, guardia.funzione(f"wx.{nome}"))
    for nome in FUNZIONI_MODALI_DI_WX_ADV:
        if hasattr(wx.adv, nome):
            monkeypatch.setattr(wx.adv, nome, guardia.funzione(f"wx.adv.{nome}"))
    for nome_modulo, nomi in FUNZIONI_CHE_APRONO_ALTRI_PROGRAMMI:
        modulo = importlib.import_module(nome_modulo)
        for nome in nomi:
            if hasattr(modulo, nome):
                monkeypatch.setattr(modulo, nome, guardia.funzione(f"{nome_modulo}.{nome}"))
    for nome in METODI_MODALI:
        for classe in list(_classi_con_metodo_nativo(wx.Dialog, nome)):
            monkeypatch.setattr(classe, nome, guardia.metodo_modale(classe, nome))
    for nome in METODI_CHE_MOSTRANO:
        for classe in list(_classi_con_metodo_nativo(wx.Window, nome)):
            monkeypatch.setattr(classe, nome, guardia.metodo_che_mostra(wx, classe, nome))
    for nome_modulo, nome_classe, nomi in METODI_CHE_APRONO:
        radice = getattr(moduli[nome_modulo], nome_classe, None)
        for nome in nomi if radice is not None else ():
            for classe in list(_classi_con_metodo_nativo(radice, nome)):
                monkeypatch.setattr(classe, nome, guardia.metodo_modale(classe, nome))
    for nome_modulo, nomi in CLASSI_CHE_SI_MOSTRANO_DA_SOLE:
        for nome in nomi:
            if hasattr(moduli[nome_modulo], nome):
                monkeypatch.setattr(moduli[nome_modulo], nome, guardia.classe_vietata(f"{nome_modulo}.{nome}"))
    yield guardia
    guardia.verifica(getattr(request.node, "esito_call", None))


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
