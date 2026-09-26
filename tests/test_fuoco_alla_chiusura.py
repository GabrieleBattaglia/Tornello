"""Il fuoco torna dov'era quando una finestra di dialogo si chiude, dalla
10.13.38.

Fino alla 10.13.37, chiusa una finestra di dialogo, il fuoco restava sulla
cornice della finestra principale, dove NVDA legge soltanto il titolo, e per
tornare a un controllo servivano F5, F6 o F7. Tutte le finestre di Tornello
tengono i controlli nel pannello di GBwx, e la causa stava li': alla
distruzione della finestra il fuoco passava dal controllo al pannello e dal
pannello al dialogo, e la finestra principale, riattivata con il fuoco sul
dialogo a meta' distruzione, credeva di averlo gia' e non lo rimetteva. Lo
corregge GBwx 1.0.1, per tutte le finestre costruite con pannello_scorrevole.
Qui le finestre sono vere, e si aprono davvero: la finestra principale di
Tornello e i dialoghi si mostrano sul desktop nascosto della suite (10.13.37),
dove il fuoco e l'attivazione funzionano come sullo schermo ma nessuno li
vede. Il segno finestre_vere dice alla guardia delle finestre di lasciarle
mostrare, e la guardia lo concede solo sul desktop nascosto. I tasti arrivano
come da tastiera: ESC e la barra spaziatrice passano prima dal gancio della
tastiera di wx, imitato con wxEVT_CHAR_HOOK, poi, se nessuno li prende, sono
messaggi WM_KEYDOWN e WM_KEYUP mandati al controllo, mai SendInput, che
andrebbe al desktop di chi lavora. Niente suona.
Due prove guardano i casi limite di GBwx 1.0.1: a finestra chiusa i suoi
controlli non ricevono eventi, e se il controllo di partenza e' stato spento
il fuoco va al primo controllo della finestra principale.
"""

import ctypes
import importlib
import os
import pkgutil
import sys
import time
from ctypes import wintypes

import pytest
from conftest import CARTELLA_SRC

pytestmark = [
    pytest.mark.finestre_vere,
    pytest.mark.skipif(sys.platform != "win32", reason="il desktop nascosto esiste solo in Windows"),
]

WM_KEYDOWN, WM_KEYUP = 0x100, 0x101
# Codice virtuale e codice di scansione dei due tasti delle prove.
TASTI = {"esc": (0x1B, 0x01), "spazio": (0x20, 0x39)}
# Oltre questo tempo una finestra che non si e' chiusa viene chiusa lo
# stesso, e la prova fallisce: meglio un fallimento che una suite ferma.
RETE_DI_SICUREZZA_MS = 8000
CHIUSA_DALLA_RETE = -1


def _user32():
    user32 = ctypes.WinDLL("user32")
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    return user32


def _premi(tasto, controllo):
    """Un tasto sul controllo, come dalla tastiera: prima il gancio della
    tastiera di wx, che per un tasto vero manda wxEVT_CHAR_HOOK alla finestra
    col fuoco e lo fa salire fino al dialogo; se nessuno lo prende, il tasto
    arriva al controllo con WM_KEYDOWN e WM_KEYUP. I messaggi mandati con
    PostMessage non passano dal gancio, che Windows chiama solo per l'input
    vero: per questo lo si imita."""
    import wx

    evento = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
    evento.SetKeyCode(wx.WXK_ESCAPE if tasto == "esc" else wx.WXK_SPACE)
    evento.SetEventObject(controllo)
    evento.SetId(controllo.GetId())
    if controllo.GetEventHandler().ProcessEvent(evento) and not evento.IsNextEventAllowed():
        return
    virtuale, scansione = TASTI[tasto]
    user32 = _user32()
    user32.PostMessageW(controllo.GetHandle(), WM_KEYDOWN, virtuale, 1 | scansione << 16)
    user32.PostMessageW(controllo.GetHandle(), WM_KEYUP, virtuale, 1 | scansione << 16 | 0xC0000000)


def _attendi(condizione, secondi=2.0):
    """Lascia lavorare il ciclo degli eventi finche' la condizione e' vera,
    o finche' scade il tempo; dice se e' diventata vera. Le finestre di
    primo livello si distruggono qui, fra gli eventi dell'attesa."""
    import wx

    fine = time.monotonic() + secondi
    while True:
        wx.GetApp().ProcessPendingEvents()
        wx.YieldIfNeeded()
        if condizione():
            return True
        if time.monotonic() > fine:
            return False
        time.sleep(0.01)


def _descrivi(finestra):
    if finestra is None:
        return "nessun controllo"
    return f"{type(finestra).__name__} {finestra.GetName()!r} di {type(finestra.GetTopLevelParent()).__name__}"


def _aperta(classe):
    """La finestra di quella classe aperta adesso, la piu' recente."""
    import wx

    for finestra in reversed(wx.GetTopLevelWindows()):
        if isinstance(finestra, classe) and finestra.IsShown() and not finestra.IsBeingDeleted():
            return finestra
    return None


def _quando_aperta(classe, azione):
    """Aspetta che la finestra della classe sia aperta, con il fuoco dentro e
    dopo che le sue chiamate rinviate, come il SetFocus dell'apertura, sono
    passate; poi chiama azione con la finestra e il controllo col fuoco."""
    import wx

    stato = {"vista": None, "tentativi": 0}

    def passo():
        stato["tentativi"] += 1
        if stato["tentativi"] > RETE_DI_SICUREZZA_MS // 20:
            return
        finestra = _aperta(classe)
        fuoco = wx.Window.FindFocus()
        pronta = finestra is not None and fuoco is not None and fuoco.GetTopLevelParent() is finestra
        if not pronta:
            stato["vista"] = None
            wx.CallLater(20, passo)
            return
        if stato["vista"] is None:
            stato["vista"] = time.monotonic()
        if time.monotonic() - stato["vista"] < 0.1:
            wx.CallLater(20, passo)
            return
        azione(finestra, fuoco)

    wx.CallLater(20, passo)


def _chiudi_quando_aperta(classe, chiusura, pulsante, poi=None):
    """Quando la finestra della classe e' pronta, la chiude: ESC sul
    controllo col fuoco, oppure la barra spaziatrice sul pulsante, che prima
    riceve il fuoco, come con il Tab. poi, se c'e', si chiama dopo il tasto:
    serve alle finestre che fanno una domanda prima di chiudersi."""
    import wx

    def chiudi(finestra, fuoco):
        if chiusura == "esc":
            _premi("esc", fuoco)
        else:
            bersaglio = pulsante(finestra)
            bersaglio.SetFocus()
            wx.CallLater(20, _premi, "spazio", bersaglio)
        if poi:
            poi()

    _quando_aperta(classe, chiudi)


def _rete_di_sicurezza():
    """Chiude ogni finestra modale rimasta aperta, con un codice che fa
    fallire la prova."""
    import wx

    def chiudi_tutto():
        for finestra in wx.GetTopLevelWindows():
            if isinstance(finestra, wx.Dialog) and finestra.IsModal():
                finestra.EndModal(CHIUSA_DALLA_RETE)

    return wx.CallLater(RETE_DI_SICUREZZA_MS, chiudi_tutto)


def _zittisci(monkeypatch):
    """Nessun suono: play_sound e bip_di_scelta tacciono, in utils e in ogni
    modulo delle finestre che se li e' importati."""
    import utils

    def muto(*_argomenti, **_opzioni):
        return True

    for modulo in pkgutil.iter_modules([os.path.join(CARTELLA_SRC, "gui", "dialogs")]):
        importlib.import_module(f"gui.dialogs.{modulo.name}")
    importlib.import_module("gui.main_frame")
    for modulo in [utils] + [m for n, m in list(sys.modules.items()) if n.startswith("gui.")]:
        for nome in ("play_sound", "bip_di_scelta"):
            if hasattr(modulo, nome):
                monkeypatch.setattr(modulo, nome, muto)


@pytest.fixture
def principale(app_grafica, monkeypatch):
    """La finestra principale vera, mostrata e attiva sul desktop nascosto,
    senza i controlli dell'avvio e senza suoni."""
    import wx

    import gui.main_frame as mf
    from gui.settings import DEFAULT_SETTINGS

    _zittisci(monkeypatch)
    for nome in ("_check_fide_db_on_startup", "_check_backup_on_startup", "_scan_and_load_initial_tournament", "_check_updates_async"):
        monkeypatch.setattr(mf.MainFrame, nome, lambda self: None)
    monkeypatch.setattr(mf.MainFrame, "Maximize", lambda self, *a: None)
    finestra = mf.MainFrame(None, "Tornello", dict(DEFAULT_SETTINGS))
    finestra._timer_pie_di_pagina.Stop()
    finestra.Show()
    finestra.Raise()
    _user32().SetForegroundWindow(finestra.GetHandle())
    assert _attendi(lambda: wx.GetActiveWindow() is finestra), "la finestra principale non si e' attivata"
    yield finestra
    finestra.Destroy()
    _attendi(lambda: not finestra, 1.0)


def _risultato(genitore):
    from gui.dialogs.result_dialog import ResultDialog

    dlg = ResultDialog(genitore, "Bianchi Luca", "Russo Marco", "GIO001", "GIO002", 3, None, {}, genitore.settings)
    # Un risultato scelto, come prima di Conferma Risultato.
    dlg.radio_buttons[0][1].SetValue(True)
    return dlg


def _programmazione(genitore):
    from test_finestre_adattabili import _torneo

    from gui.dialogs.result_dialog import ScheduleDialog

    return ScheduleDialog(genitore, {}, genitore.settings, _torneo(27))


def _iscrizione(genitore):
    from test_finestre_adattabili import _giocatori

    from gui.dialogs.player_enrollment_dialog import PlayerEnrollmentDialog

    return PlayerEnrollmentDialog(genitore, _giocatori(30), list(_giocatori(8).values()), genitore.settings)


def _copie(genitore):
    from gui.dialogs.backup_cleanup_dialog import BackupCleanupDialog

    return BackupCleanupDialog(genitore, genitore.settings)


def _composizione(genitore):
    from test_finestre_adattabili import _torneo_da_comporre

    from gui.dialogs.manual_pairing_dialog import ManualPairingDialog

    return ManualPairingDialog(genitore, _torneo_da_comporre(), 2, genitore.settings)


def _messaggio(genitore):
    from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog

    return AccessibleMsgDialog(genitore, "Messaggio", "Il testo del messaggio.", settings=genitore.settings)


def _domanda(genitore):
    import wx

    from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog

    return AccessibleMsgDialog(genitore, "Domanda", "Il testo della domanda?", style=wx.YES_NO, settings=genitore.settings)


def _per_id(identificativo):
    import wx

    return lambda finestra: finestra.FindWindowById(getattr(wx, identificativo), finestra)


# Le finestre del campione: come si creano, da quale controllo della
# finestra principale parte il fuoco, quale pulsante vale Annulla e quale
# OK, e i codici con cui ESC, Annulla e OK le chiudono. None dove il
# pulsante non c'e'.
FINESTRE = {
    "messaggio": (_messaggio, "status_text", None, _per_id("ID_OK"), ("ID_OK", None, "ID_OK")),
    "domanda": (_domanda, "tree_ctrl", lambda f: f.pulsante_no, lambda f: f.pulsante_si, ("ID_NO", "ID_NO", "ID_YES")),
    "risultato": (_risultato, "tree_ctrl", _per_id("ID_CANCEL"), lambda f: f.btn_ok, ("ID_CANCEL", "ID_CANCEL", "ID_OK")),
    "programmazione": (_programmazione, "status_text", _per_id("ID_CANCEL"), _per_id("ID_OK"), ("ID_CANCEL", "ID_CANCEL", "ID_OK")),
    "iscrizione": (_iscrizione, "tree_ctrl", _per_id("ID_CANCEL"), _per_id("ID_OK"), ("ID_CANCEL", "ID_CANCEL", "ID_OK")),
    "copie di sicurezza": (_copie, "main_text", lambda f: f.btn_close, None, ("ID_CANCEL", "ID_CANCEL", None)),
    "composizione manuale": (_composizione, "tree_ctrl", lambda f: f.btn_annulla, lambda f: f.btn_conferma, ("ID_CANCEL", "ID_CANCEL", "ID_OK")),
}
CHIUSURE = ("esc", "annulla", "ok")
CASI = [(nome, chiusura) for nome, voce in FINESTRE.items() for indice, chiusura in enumerate(CHIUSURE) if voce[4][indice]]


def _parti_da(principale, nome_del_controllo):
    import wx

    partenza = getattr(principale, nome_del_controllo)
    partenza.SetFocus()
    assert _attendi(lambda: wx.Window.FindFocus() is partenza), f"il fuoco non e' arrivato su {nome_del_controllo}"
    return partenza


def _torna_su(partenza):
    import wx

    tornato = _attendi(lambda: wx.Window.FindFocus() is partenza)
    return tornato, _descrivi(wx.Window.FindFocus())


@pytest.mark.parametrize(("finestra", "chiusura"), CASI)
def test_il_fuoco_torna_sul_controllo_di_partenza(principale, finestra, chiusura):
    """La finestra si apre dalla principale con il fuoco su un suo
    controllo, si chiude con ESC, con Annulla o con OK, e il fuoco torna su
    quel controllo. OK della composizione manuale fa prima la domanda di
    conferma, a cui si risponde Si'."""
    import wx

    from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog

    crea, controllo, annulla, ok, codici = FINESTRE[finestra]
    atteso = getattr(wx, codici[CHIUSURE.index(chiusura)])
    partenza = _parti_da(principale, controllo)
    dlg = crea(principale)

    def rispondi_si():
        _chiudi_quando_aperta(AccessibleMsgDialog, "ok", lambda domanda: domanda.pulsante_si)

    poi = rispondi_si if finestra == "composizione manuale" and chiusura == "ok" else None
    _chiudi_quando_aperta(type(dlg), chiusura, annulla if chiusura == "annulla" else ok, poi)
    rete = _rete_di_sicurezza()
    try:
        codice = dlg.ShowModal()
    finally:
        rete.Stop()
    for valore in vars(dlg).values():
        if isinstance(valore, wx.Timer):
            valore.Stop()
    dlg.Destroy()
    assert codice == atteso
    tornato, dove = _torna_su(partenza)
    assert tornato, f"{finestra}, chiusa con {chiusura}: il fuoco e' su {dove}"


@pytest.mark.parametrize("chiusura", CHIUSURE)
def test_le_impostazioni_dal_menu(principale, chiusura, monkeypatch):
    """Le Impostazioni, aperte come dal menu Strumenti. Fino alla 10.13.37
    il fuoco lo rimetteva on_preferences, con un rimedio suo nato con la
    10.13.25: adesso lo rimette GBwx, come per tutte le altre finestre, e il
    risultato e' lo stesso."""
    import wx

    from gui.dialogs.visual_settings_dialog import VisualSettingsDialog

    codici = []
    originale = VisualSettingsDialog.ShowModal
    monkeypatch.setattr(VisualSettingsDialog, "ShowModal", lambda self: codici.append(originale(self)) or codici[-1])
    partenza = _parti_da(principale, "status_text")
    _chiudi_quando_aperta(VisualSettingsDialog, chiusura, _per_id("ID_CANCEL") if chiusura == "annulla" else _per_id("ID_OK"))
    rete = _rete_di_sicurezza()
    try:
        principale.on_preferences(None)
    finally:
        rete.Stop()
    assert codici == [wx.ID_OK if chiusura == "ok" else wx.ID_CANCEL]
    tornato, dove = _torna_su(partenza)
    assert tornato, f"impostazioni, chiuse con {chiusura}: il fuoco e' su {dove}"


def test_le_impostazioni_con_la_lingua_cambiata(principale, monkeypatch):
    """Con la lingua cambiata, OK nelle Impostazioni apre il messaggio
    Riavvio Richiesto: chiuso anche quello, il fuoco torna sul controllo di
    partenza."""
    import wx

    from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog
    from gui.dialogs.visual_settings_dialog import VisualSettingsDialog

    partenza = _parti_da(principale, "tree_ctrl")

    def cambia_la_lingua(finestra):
        """Il pulsante OK, dopo aver scelto un'altra lingua."""
        altra = next(i for i, codice in enumerate(finestra.lang_codes) if codice != principale.settings.get("language", "it"))
        finestra.choice_lang.SetSelection(altra)
        return finestra.FindWindowById(wx.ID_OK, finestra)

    def poi():
        _chiudi_quando_aperta(AccessibleMsgDialog, "ok", _per_id("ID_OK"))

    _chiudi_quando_aperta(VisualSettingsDialog, "ok", cambia_la_lingua, poi)
    rete = _rete_di_sicurezza()
    try:
        principale.on_preferences(None)
    finally:
        rete.Stop()
    assert principale.settings.get("language") != "it"
    tornato, dove = _torna_su(partenza)
    assert tornato, f"impostazioni con la lingua cambiata: il fuoco e' su {dove}"


def _scrivi_nel_fuoco(caratteri):
    """Scrive nella finestra che ha il fuoco per Windows, come dalla
    tastiera, con WM_CHAR, dopo averne selezionato tutto il testo. Per uno
    SpinCtrl la finestra col fuoco e' il suo campo di testo, non quella che
    wx chiama GetHandle."""
    user32 = _user32()
    user32.GetFocus.restype = wintypes.HWND
    campo = user32.GetFocus()
    user32.PostMessageW(campo, 0x00B1, 0, -1)
    for carattere in caratteri:
        user32.PostMessageW(campo, 0x0102, ord(carattere), 1)


def test_a_finestra_chiusa_i_controlli_non_ricevono_eventi(principale, monkeypatch):
    """Nelle Impostazioni si scrive 25 nella misura dei caratteri, senza
    confermarlo, e si chiude con ESC. Il fuoco che GBwx toglie alla
    distruzione della finestra non deve arrivare allo SpinCtrl come
    EVT_KILL_FOCUS: lo SpinCtrl confermerebbe il numero con un EVT_SPINCTRL,
    cioe' un on_change in piu' a finestra chiusa, come non succede con un
    dialogo senza pannello. In Tornello aggiornerebbe soltanto l'anteprima,
    ma un gestore che salva un campo quando perde il fuoco salverebbe dopo
    Annulla."""
    import wx

    from gui.dialogs.visual_settings_dialog import VisualSettingsDialog

    fase = {"chiusa": False}
    aperta, chiusa = [], []
    originale = VisualSettingsDialog.on_change

    def on_change(self, event):
        if fase["chiusa"]:
            chiusa.append(type(event).__name__)
            return None
        aperta.append(type(event).__name__)
        return originale(self, event)

    mostra = VisualSettingsDialog.ShowModal

    def show_modal(self):
        try:
            return mostra(self)
        finally:
            fase["chiusa"] = True

    monkeypatch.setattr(VisualSettingsDialog, "on_change", on_change)
    monkeypatch.setattr(VisualSettingsDialog, "ShowModal", show_modal)
    partenza = _parti_da(principale, "status_text")

    def scrivi_poi_esc(finestra, _fuoco):
        finestra.spin_size.SetFocus()
        wx.CallLater(60, _scrivi_nel_fuoco, "25")
        wx.CallLater(300, lambda: _premi("esc", wx.Window.FindFocus()))

    _quando_aperta(VisualSettingsDialog, scrivi_poi_esc)
    rete = _rete_di_sicurezza()
    try:
        principale.on_preferences(None)
    finally:
        rete.Stop()
    tornato, dove = _torna_su(partenza)
    assert aperta, "il numero scritto non e' arrivato allo SpinCtrl"
    assert chiusa == [], f"a finestra chiusa on_change e' stato chiamato da {chiusa}"
    assert tornato, f"impostazioni, chiuse con ESC dopo aver scritto: il fuoco e' su {dove}"


def test_con_la_partenza_spenta_il_fuoco_va_al_primo_controllo(principale):
    """Se il controllo da cui era partito il fuoco viene spento mentre la
    finestra e' aperta, alla chiusura Windows rifiuta il fuoco che wx gli
    rimette: GBwx lo da' allora al primo controllo della finestra principale
    che lo accetta, l'area centrale, invece di lasciarlo a nessuno, con i
    tasti che non arrivano a nessun controllo. Tornello oggi non spegne mai
    i controlli della finestra principale: la prova tiene fermo il
    comportamento per il giorno in cui succedesse."""
    import wx

    from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog

    partenza = _parti_da(principale, "tree_ctrl")
    dlg = _messaggio(principale)

    def spegni_poi_esc(_finestra, fuoco):
        partenza.Disable()
        _premi("esc", fuoco)

    _quando_aperta(AccessibleMsgDialog, spegni_poi_esc)
    rete = _rete_di_sicurezza()
    try:
        codice = dlg.ShowModal()
    finally:
        rete.Stop()
    for valore in vars(dlg).values():
        if isinstance(valore, wx.Timer):
            valore.Stop()
    dlg.Destroy()
    try:
        arrivato = _attendi(lambda: wx.Window.FindFocus() is principale.main_text)
        dove = _descrivi(wx.Window.FindFocus())
    finally:
        partenza.Enable()
    assert codice == wx.ID_OK
    assert arrivato, f"con la partenza spenta il fuoco e' su {dove}"
