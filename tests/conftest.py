import hashlib
import importlib
import inspect
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

import pytest

# Aggiunge la cartella src al path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

RADICE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CARTELLA_SRC = os.path.join(RADICE, "src")


# Il desktop nascosto, dalla 10.13.37. La guardia delle finestre vere, piu'
# sotto, impedisce alle finestre di mostrarsi, ma non basta: Windows da' il
# primo piano anche a una finestra mai mostrata quando riceve il fuoco, per
# esempio con il SetFocus dell'albero in _ripristina_la_selezione o dentro
# una TextEntryDialog, perche' il processo di pytest e' partito dal terminale
# che aveva il primo piano. Il 26 settembre 2026 finestre invisibili delle
# prove hanno preso il primo piano sullo schermo di Gabriele, e NVDA gli
# leggeva i loro titoli. Percio', prima che wx crei qualunque finestra, il
# thread principale passa su un desktop di Windows tutto suo, che nessuno
# vede: le finestre nascono li', dove il fuoco, l'attivazione e il primo
# piano non toccano il desktop di chi lancia le prove, e gli agganci dello
# screen reader, che valgono per il desktop su cui sono stati messi, non le
# vedono. Se il passaggio non riesce, la suite non parte: meglio nessuna
# prova che finestre sul desktop vero. Fuori da Windows non serve.
# Il passaggio vale per il thread principale, l'unico su cui wx crea
# finestre: un thread nato dopo parte dal desktop del processo, quello di
# chi lancia le prove. Nelle esecuzioni del 26 settembre 2026, sorvegliate
# con un aggancio degli eventi di Windows sul desktop Default, l'unico a
# crearci qualcosa e' stato un thread della Shell, in una delle prove che
# allora mandavano file nel cestino di Windows: una finestra di soli
# messaggi di COM (OLEChannelWnd), che non si mostra, non si attiva e non
# riceve il fuoco. Dall'8 novembre 2026 nessuna prova manda piu' file nel
# cestino di Windows: la guardia del cestino, piu' sotto, fa cadere la prova
# che ci arriva, e alla Shell non arriva niente.
NOME_DEL_DESKTOP = f"tornello_prove_{os.getpid()}"
GENERIC_ALL = 0x10000000
# Il desktop di partenza, per nome, e la maniglia del desktop nascosto, che
# resta aperta finche' il processo vive: chiusa, il desktop sparirebbe sotto
# le finestre delle prove.
DESKTOP_DELLE_PROVE = {}


def user32_del_desktop():
    """user32 con le firme delle funzioni dei desktop. Una copia tutta sua,
    cosi' le firme non cambiano quelle che il resto del processo usa."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.CreateDesktopW.restype = wintypes.HANDLE
    user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    user32.SetThreadDesktop.restype = wintypes.BOOL
    user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
    user32.CloseDesktop.restype = wintypes.BOOL
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    user32.GetThreadDesktop.restype = wintypes.HANDLE
    user32.GetThreadDesktop.argtypes = [wintypes.DWORD]
    user32.GetUserObjectInformationW.restype = wintypes.BOOL
    user32.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    return user32


def _desktop_non_disponibile(azione, funzione, codice):
    import ctypes

    return (
        f"Le prove non partono: non si e' potuto {azione} ({funzione}, errore di Windows "
        f"{codice}: {ctypes.FormatError(codice).strip()}). Le finestre delle prove nascono "
        "su un desktop di Windows nascosto, creato apposta: senza, una finestra mai "
        "mostrata che riceve il fuoco prenderebbe il primo piano sullo schermo di chi "
        "lancia le prove, e lo screen reader ne leggerebbe il titolo. Il passaggio "
        "fallisce se questo thread ha gia' delle finestre, per esempio lanciando pytest "
        "dall'interno di un programma con le finestre."
    )


def passa_al_desktop_nascosto(user32=None, nome=None):
    """Crea il desktop nascosto e ci sposta il thread principale, che e'
    quello su cui wx crea le finestre. Torna la maniglia del desktop. Se non
    ci riesce solleva pytest.UsageError, che ferma la suite prima della prima
    prova con un messaggio chiaro. Windows rifiuta il passaggio a un thread
    che ha gia' finestre o agganci: va fatto prima di wx.App."""
    import ctypes

    user32 = user32 or user32_del_desktop()
    desktop = user32.CreateDesktopW(nome or NOME_DEL_DESKTOP, None, None, 0, GENERIC_ALL, None)
    if not desktop:
        raise pytest.UsageError(_desktop_non_disponibile("creare il desktop nascosto", "CreateDesktopW", ctypes.get_last_error()))
    if not user32.SetThreadDesktop(desktop):
        codice = ctypes.get_last_error()
        user32.CloseDesktop(desktop)
        raise pytest.UsageError(_desktop_non_disponibile("spostare le prove sul desktop nascosto", "SetThreadDesktop", codice))
    return desktop


def nome_del_desktop(maniglia, user32=None):
    """Il nome di un desktop, come lo dice Windows, o None."""
    import ctypes
    from ctypes import wintypes

    user32 = user32 or user32_del_desktop()
    testo = ctypes.create_unicode_buffer(256)
    necessari = wintypes.DWORD()
    if not user32.GetUserObjectInformationW(maniglia, 2, testo, ctypes.sizeof(testo), ctypes.byref(necessari)):
        return None
    return testo.value


def sul_desktop_nascosto():
    """Vero se il thread principale sta adesso sul desktop nascosto delle
    prove. Lo chiede la guardia delle finestre a una prova che vuole
    mostrarne di vere."""
    import ctypes

    if sys.platform != "win32" or "nascosto" not in DESKTOP_DELLE_PROVE:
        return False
    user32 = user32_del_desktop()
    attuale = user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
    return nome_del_desktop(attuale, user32) == NOME_DEL_DESKTOP


def pytest_configure(config):
    """Il passaggio al desktop nascosto, una volta per processo, prima che
    le prove importino i moduli e prima che la fixture app_grafica crei
    wx.App. Qui si dichiara anche il segno finestre_vere."""
    config.addinivalue_line(
        "markers",
        "finestre_vere: la prova mostra finestre vere e le apre con ShowModal; la guardia delle finestre lo permette solo sul desktop nascosto (dalla 10.13.38)",
    )
    if sys.platform != "win32" or DESKTOP_DELLE_PROVE:
        return
    import ctypes

    user32 = user32_del_desktop()
    partenza = user32.GetThreadDesktop(ctypes.windll.kernel32.GetCurrentThreadId())
    nome_di_partenza = nome_del_desktop(partenza, user32)
    DESKTOP_DELLE_PROVE["nascosto"] = passa_al_desktop_nascosto(user32)
    DESKTOP_DELLE_PROVE["partenza"] = nome_di_partenza


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

    # I file di lavoro del motore vanno in una cartella a parte, fuori da
    # quella della prova: diverse prove elencano cio' che trovano nella loro
    # cartella, e una sottocartella in piu' le farebbe fallire.
    motore = tmp_path_factory.mktemp("motore")
    devia_la_cartella_del_programma(monkeypatch, tmp_path, motore)
    # config e' sempre fra i moduli caricati: lo importa questa stessa
    # fixture, cosi' anche un modulo importato per la prima volta dentro una
    # prova si copia i valori gia' deviati.
    assert config.PLAYER_DB_FILE.startswith(str(tmp_path))


def devia_la_cartella_del_programma(monkeypatch, radice, motore=None):
    """La cartella del programma diventa radice, per tutti i moduli, con le
    costanti di dati calcolate all'importazione. Quelle del motore vanno in
    motore; senza, restano dove sono."""
    import percorsi

    veri = percorsi_veri()
    monkeypatch.setattr(percorsi, "cartella_applicazione", lambda: str(radice))
    deviati = {}
    for nome, vero in veri.items():
        if nome in COSTANTI_DEL_MOTORE:
            if motore is not None:
                deviati[nome] = str(motore / os.path.basename(vero))
        else:
            relativo = os.path.relpath(vero, RADICE)
            deviati[nome] = str(radice) if relativo == "." else str(radice / relativo)

    for modulo in moduli_di_tornello():
        for nome, nuovo in deviati.items():
            if isinstance(getattr(modulo, nome, None), str):
                monkeypatch.setattr(modulo, nome, nuovo)


@pytest.fixture
def programma_con_le_parentesi(tmp_path, monkeypatch):
    """La cartella del programma con le parentesi quadre nel nome, Tornello
    [prova], dentro la cartella temporanea della prova: ci vanno i tornei,
    l'archivio, il database dei giocatori e le copie di sicurezza, come con
    dati_in_cartella_temporanea. Serve alle prove delle ricerche con glob,
    che dalla 10.19.41 e dalla 10.19.46 passano da glob.escape: senza, glob
    legge le parentesi come un insieme di caratteri. Restituisce la
    cartella."""
    import config

    radice = tmp_path / "Tornello [prova]"
    radice.mkdir()
    devia_la_cartella_del_programma(monkeypatch, radice)
    assert config.user_data_path("").startswith(str(radice))
    assert config.ARCHIVED_TOURNAMENTS_DIR.startswith(str(radice))
    return radice


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
# Dalla 10.13.38 una prova segnata finestre_vere puo' mostrare davvero le
# sue finestre e aprire i dialoghi con ShowModal, per esempio per vedere
# dove va il fuoco quando si chiudono: la guardia la lascia fare, ma solo
# sul desktop nascosto, dove nessuno le vede. Tutto il resto resta fermo.
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


class Guardia:
    """Cio' che le guardie hanno in comune: annotano ogni chiamata a cio' che
    una prova non deve raggiungere, e la chiamata fa fallire la prova subito,
    con un'eccezione che il codice di Tornello non puo' ingoiare, perche' non
    deriva da Exception; se la fa comunque sparire qualcun altro, per esempio
    wx, che stampa l'errore di un gestore di eventi e prosegue, la prova
    fallisce alla fine."""

    def __init__(self):
        self.chiamate = []

    def ferma(self, messaggio):
        self.chiamate.append(messaggio)
        pytest.fail(messaggio, pytrace=True)

    def verifica(self, esito_della_prova):
        """A prova finita: se c'e' stata una chiamata vietata e la prova non
        e' gia' fallita per questo, fallisce adesso."""
        if self.chiamate and not (esito_della_prova is not None and esito_della_prova.failed):
            pytest.fail("\n".join(self.chiamate), pytrace=False)


class GuardiaDelleFinestre(Guardia):
    """Sostituisce cio' che aprirebbe una finestra vera e annota ogni
    chiamata, che fa fallire la prova."""

    def vieta(self, descrizione):
        self.ferma(
            f"La prova ha chiamato {descrizione} vero, che aprirebbe una finestra "
            "sullo schermo. Va sostituito con monkeypatch prima di arrivarci, per "
            "esempio con una classe finta che risponde, come fanno le altre prove."
        )

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


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """Annota sulla prova l'esito di ogni fase: alle guardie serve sapere se
    la prova e' gia' fallita per una finestra vera o per il cestino."""
    rapporto = yield
    setattr(item, f"esito_{rapporto.when}", rapporto)
    return rapporto


@pytest.fixture(autouse=True)
def nessuna_finestra_vera(request, monkeypatch):
    """La guardia delle finestre vere, su ogni prova. Senza wxPython non c'e'
    niente da sorvegliare. Con il segno finestre_vere, e soltanto sul
    desktop nascosto, Show e ShowModal restano quelli di wx."""
    try:
        import wx
        import wx.adv
        import wx.html
    except ImportError:  # pragma: no cover
        yield None
        return

    finestre_vere = request.node.get_closest_marker("finestre_vere") is not None
    if finestre_vere and not sul_desktop_nascosto():
        pytest.fail("La prova vuole mostrare finestre vere, e la guardia lo permette solo sul desktop nascosto delle prove.", pytrace=False)
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
    for nome in METODI_MODALI if not finestre_vere else ():
        for classe in list(_classi_con_metodo_nativo(wx.Dialog, nome)):
            monkeypatch.setattr(classe, nome, guardia.metodo_modale(classe, nome))
    for nome in METODI_CHE_MOSTRANO if not finestre_vere else ():
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


# Il cestino finto e la guardia del cestino, dall'8 novembre 2026. Fino ad
# allora tre prove mandavano file veri nel cestino di Windows, a ogni corsa
# della suite: test_delete_file_to_trash un file temporaneo,
# test_dalla_copia_alla_pulizia e test_elimina_tutti_i_file_selezionati le
# copie di sicurezza che avevano appena creato. Nel cestino di Gabriele se ne
# erano accumulate migliaia. Una prova che manda file nel cestino usa il
# cestino finto, la fixture cestino_finto, che prende il posto di
# delete_file_to_trash; una prova di delete_file_to_trash in se' sostituisce
# la chiamata di Windows con il metodo shell di CestinoFinto, e guarda che
# cosa le arriva. Il cestino che non prende, o che rifiuta certi percorsi, e'
# lo stesso cestino finto, con prende e rifiuta: una prova non se ne scrive
# uno suo. La guardia sta al punto piu' in basso, la chiamata alla
# Shell di Windows, SHFileOperationW, e send2trash, che fuori da Windows ne
# fa le veci: cosi' una prova che sostituisce delete_file_to_trash, o che
# risponde da se' a cestino_disponibile, continua a fare quello che fa, e si
# ferma soltanto una chiamata che arriverebbe davvero al cestino. La prova
# cade, e il file resta dov'e'.


class CestinoFinto:
    """Al posto del cestino di Windows: sposta file e cartelle in una
    cartella della prova e annota che cosa ha ricevuto, e da quale finestra.
    tentativi annota ogni percorso che gli arriva, prima di decidere se lo
    prende; ricevuti soltanto quelli che ha preso. rifiuta contiene i
    percorsi che non accetta, e con prende falso non ne accetta nessuno,
    come un cestino che non si raggiunge, per esempio su un disco senza
    cestino: il file resta dov'e', e la risposta e' falso. Si chiama come
    delete_file_to_trash; il metodo shell prende invece il posto della
    chiamata di Windows, nelle prove di delete_file_to_trash in se'. Fino
    all'8 novembre 2026 stava in test_copie_di_sicurezza.py; dallo stesso
    giorno prende anche il posto dei cestini finti che alcune prove si
    scrivevano da se', ognuno con la sua variante: il cestino che non
    prende, i percorsi rifiutati e i tentativi annotati prima del rifiuto
    sono diventati prende, rifiuta e tentativi."""

    def __init__(self, cartella):
        self.cartella = cartella
        self.prende = True
        self.tentativi = []
        self.ricevuti = []
        self.finestre = []
        self.richieste = []
        self.rifiuta = set()

    def __call__(self, percorso, finestra=None):
        self.finestre.append(finestra)
        if not self._accetta(percorso):
            return False
        self._sposta(percorso)
        return True

    def shell(self, richiesta):
        """Al posto di ctypes.windll.shell32.SHFileOperationW: annota che
        cosa le arriva, cioe' la finestra, l'operazione, l'elenco dei percorsi
        fino ai due caratteri nulli che lo chiudono, la destinazione e le
        opzioni, e sposta il file come un cestino. Risponde 0, come la Shell
        quando riesce; con un percorso di rifiuta, o con prende falso, il file
        resta dov'e', e la risposta e' un codice d'errore."""
        import ctypes

        struttura = richiesta._obj
        percorso = struttura.pFrom
        inizio = ctypes.c_void_p.from_buffer(struttura, type(struttura).pFrom.offset).value
        self.richieste.append(
            SimpleNamespace(
                finestra=struttura.hwnd,
                operazione=struttura.wFunc,
                elenco=ctypes.wstring_at(inizio, len(percorso) + 2),
                destinazione=struttura.pTo,
                opzioni=struttura.fFlags,
            )
        )
        if not self._accetta(percorso):
            return 2
        self._sposta(percorso)
        return 0

    def _accetta(self, percorso):
        """Annota il tentativo, e dice se il cestino prende il percorso."""
        percorso = os.path.abspath(percorso)
        self.tentativi.append(percorso)
        return self.prende and percorso not in {os.path.abspath(p) for p in self.rifiuta}

    def _sposta(self, percorso):
        os.makedirs(self.cartella, exist_ok=True)
        destinazione = os.path.join(self.cartella, f"{len(self.ricevuti)}_{os.path.basename(percorso)}")
        shutil.move(percorso, destinazione)
        self.ricevuti.append(os.path.abspath(percorso))


@pytest.fixture
def cestino_finto(tmp_path, monkeypatch):
    """Il cestino finto, per le prove che mandano file nel cestino: prende il
    posto di delete_file_to_trash in utils e in ogni modulo di Tornello che
    se l'e' importata, e sposta i file nella cartella cestino della prova.
    Restituisce il CestinoFinto, con i tentativi, i file ricevuti e le
    finestre da cui sono partiti; la prova sceglie con prende e rifiuta il
    cestino che non prende, o che rifiuta certi percorsi. ripristina di
    copie_di_sicurezza lo riceve come argomento cestino, come fa la finestra
    Copie di sicurezza: il suo valore predefinito e' il cestino vero, e la
    guardia fermerebbe la prova."""
    # copie_di_sicurezza si importa prima della sostituzione: importato dopo,
    # il valore predefinito di ripristina resterebbe il cestino finto anche
    # nelle prove che vengono dopo.
    importlib.import_module("copie_di_sicurezza")
    import utils

    vero = utils.delete_file_to_trash
    cestino = CestinoFinto(str(tmp_path / "cestino"))
    for modulo in list(moduli_di_tornello()):
        if getattr(modulo, "delete_file_to_trash", None) is vero:
            monkeypatch.setattr(modulo, "delete_file_to_trash", cestino)
    yield cestino
    # Un modulo importato per la prima volta durante la prova si e' copiato
    # il cestino finto: torna quello vero, come negli altri.
    for modulo in list(moduli_di_tornello()):
        if getattr(modulo, "delete_file_to_trash", None) is cestino:
            modulo.delete_file_to_trash = vero


class GuardiaDelCestino(Guardia):
    """Al posto del cestino vero: la chiamata alla Shell di Windows, e
    send2trash. Il file resta dov'e', e la prova cade."""

    def vieta(self, via, percorso):
        self.ferma(
            f"La prova ha raggiunto il cestino di Windows, con {via}, e voleva "
            f"mandarci {percorso}. Va sostituito prima di arrivarci: una prova che "
            "manda file nel cestino usa la fixture cestino_finto, al posto di "
            "delete_file_to_trash; una prova di delete_file_to_trash in se' "
            "sostituisce la chiamata di Windows con il metodo shell di "
            "CestinoFinto, come test_delete_file_to_trash."
        )

    def shell(self):
        def shfileoperation(richiesta, *_argomenti):
            struttura = getattr(richiesta, "_obj", richiesta)
            self.vieta("SHFileOperationW", getattr(struttura, "pFrom", richiesta))

        shfileoperation.guardia_del_cestino = True
        return shfileoperation

    def send2trash(self):
        def send2trash(percorso, *_argomenti, **_opzioni):
            self.vieta("send2trash", percorso)

        send2trash.guardia_del_cestino = True
        return send2trash


def metti_la_guardia_del_cestino(monkeypatch, guardia):
    """La guardia al posto della chiamata alla Shell di Windows, e di
    send2trash, se c'e'."""
    if sys.platform == "win32":
        import ctypes

        monkeypatch.setattr(ctypes.windll.shell32, "SHFileOperationW", guardia.shell())
    try:
        import send2trash
    except ImportError:
        return
    monkeypatch.setattr(send2trash, "send2trash", guardia.send2trash())


@pytest.fixture(autouse=True)
def nessun_cestino_vero(request, monkeypatch):
    """La guardia del cestino, su ogni prova."""
    guardia = GuardiaDelCestino()
    metti_la_guardia_del_cestino(monkeypatch, guardia)
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
