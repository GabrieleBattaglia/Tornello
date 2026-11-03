"""INVIO nella finestra del risultato senza un risultato scelto, dalla
10.13.51 (issue 63).

Fino alla 10.13.50, con nessuna voce del risultato scelta, INVIO arrivava
al pulsante predefinito Conferma Risultato, e Windows lo premeva: la
finestra si chiudeva con il suono della conferma senza registrare niente, e
un PGN appena incollato andava perso. La regola di on_key_down, che conferma
solo con un risultato scelto, non entrava mai in gioco. Adesso INVIO, e
Conferma Risultato premuto in qualunque modo, senza un risultato scelto
fanno sentire il suono dell'errore, e la finestra resta aperta, come con il
PGN non valido dalla 10.8.4.
Qui la finestra e' vera, e si apre davvero con ShowModal sul desktop
nascosto della suite (10.13.37), dove nessuno la vede. I tasti arrivano come
da tastiera: prima il gancio della tastiera di wx, imitato con
wxEVT_CHAR_HOOK, poi, se nessuno li prende, i messaggi WM_KEYDOWN e WM_KEYUP
mandati al controllo con il fuoco, mai SendInput. I suoni si annotano.
"""

import importlib
import os
import pkgutil
import sys

import pytest
from conftest import CARTELLA_SRC
from test_fuoco_alla_chiusura import CHIUSA_DALLA_RETE, _attendi, _quando_aperta, _rete_di_sicurezza, _user32

pytestmark = [
    pytest.mark.finestre_vere,
    pytest.mark.skipif(sys.platform != "win32", reason="il desktop nascosto esiste solo in Windows"),
]

WM_KEYDOWN, WM_KEYUP = 0x100, 0x101
# Codice virtuale e codice di scansione dei tasti delle prove.
TASTI = {"invio": (0x0D, 0x1C), "spazio": (0x20, 0x39)}
# Il codice con cui la prova chiude la finestra rimasta aperta dopo il tasto.
RIMASTA_APERTA = 7777


@pytest.fixture
def suoni(monkeypatch):
    """I suoni, annotati per nome, in utils e in ogni modulo delle finestre
    che se li e' importati."""
    import utils

    suonati = []

    def annota(nome, *_argomenti, **_opzioni):
        suonati.append(nome)
        return True

    for modulo in pkgutil.iter_modules([os.path.join(CARTELLA_SRC, "gui", "dialogs")]):
        importlib.import_module(f"gui.dialogs.{modulo.name}")
    for modulo in [utils] + [m for n, m in list(sys.modules.items()) if n.startswith("gui.")]:
        if hasattr(modulo, "play_sound"):
            monkeypatch.setattr(modulo, "play_sound", annota)
        if hasattr(modulo, "bip_di_scelta"):
            monkeypatch.setattr(modulo, "bip_di_scelta", lambda *a, **k: None)
    return suonati


@pytest.fixture
def genitore(app_grafica):
    """Una cornice vera, mostrata e attiva sul desktop nascosto."""
    import wx

    from gui.settings import DEFAULT_SETTINGS

    cornice = wx.Frame(None, title="Prova")
    cornice.settings = dict(DEFAULT_SETTINGS)
    cornice.Show()
    cornice.Raise()
    # Windows puo' rifiutare il primo piano per un attimo, per esempio
    # mentre un'altra suite lavora sul suo desktop nascosto: si riprova per
    # qualche secondo prima di darla per persa.
    user32 = _user32()
    for _tentativo in range(10):
        user32.SetForegroundWindow(cornice.GetHandle())
        if _attendi(lambda: wx.GetActiveWindow() is cornice, 0.5):
            break
    else:
        pytest.fail("la cornice non si e' attivata")
    yield cornice
    cornice.Destroy()
    _attendi(lambda: not cornice, 1.0)


def _premi(tasto, controllo):
    """Un tasto sul controllo, come dalla tastiera: prima il gancio della
    tastiera di wx, poi, se nessuno lo prende, WM_KEYDOWN e WM_KEYUP."""
    import wx

    evento = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
    evento.SetKeyCode(wx.WXK_RETURN if tasto == "invio" else wx.WXK_SPACE)
    evento.SetEventObject(controllo)
    evento.SetId(controllo.GetId())
    if controllo.GetEventHandler().ProcessEvent(evento) and not evento.IsNextEventAllowed():
        return
    virtuale, scansione = TASTI[tasto]
    user32 = _user32()
    user32.PostMessageW(controllo.GetHandle(), WM_KEYDOWN, virtuale, 1 | scansione << 16)
    user32.PostMessageW(controllo.GetHandle(), WM_KEYUP, virtuale, 1 | scansione << 16 | 0xC0000000)


def _apri_e_premi(dlg, tasto, dove, prima=None):
    """Apre la finestra con ShowModal; quando e' pronta chiama prima, se
    c'e', porta il fuoco sul controllo che dove sceglie e preme il tasto.
    Mezzo secondo dopo, se la finestra e' ancora aperta, la chiude con
    RIMASTA_APERTA. Restituisce il codice di chiusura."""
    import wx

    attese = []

    def chiudi_se_aperta(finestra):
        if finestra and finestra.IsModal():
            finestra.EndModal(RIMASTA_APERTA)

    def poi(finestra, _fuoco):
        if prima:
            prima(finestra)
        bersaglio = dove(finestra)
        bersaglio.SetFocus()

        def premi():
            assert wx.Window.FindFocus() is bersaglio
            _premi(tasto, bersaglio)
            attese.append(wx.CallLater(500, chiudi_se_aperta, finestra))

        attese.append(wx.CallLater(50, premi))

    _quando_aperta(type(dlg), poi)
    rete = _rete_di_sicurezza()
    try:
        return dlg.ShowModal()
    finally:
        rete.Stop()
        for attesa in attese:
            attesa.Stop()


def _risultato(genitore, risultato=None, pgn=""):
    from gui.dialogs.result_dialog import ResultDialog

    return ResultDialog(genitore, "Bianchi Luca", "Russo Marco", "GIO001", "GIO002", 3, risultato, {}, genitore.settings, pgn_text=pgn)


def _prima_voce(finestra):
    return finestra.radio_buttons[0][1]


class TestInvioSenzaRisultato:
    def test_invio_su_una_voce_non_scelta_suona_l_errore_e_resta(self, genitore, suoni):
        """Il caso della issue 63: la finestra si apre senza risultato, il
        fuoco sta sulla prima voce, che non e' scelta, e si preme INVIO."""
        dlg = _risultato(genitore)
        try:
            codice = _apri_e_premi(dlg, "invio", _prima_voce, prima=lambda f: suoni.clear())
            assert codice == RIMASTA_APERTA, "INVIO ha chiuso la finestra"
            assert dlg.get_selected_result() is None
            assert suoni[0] == "errore"
            assert "conferma" not in suoni
        finally:
            dlg.Destroy()

    def test_il_pgn_incollato_resta_nel_campo(self, genitore, suoni):
        """Il PGN scritto prima di scegliere il risultato non va perso:
        la finestra resta aperta, con il testo nel campo."""
        pgn = '[Event "Prova"]\n\n1. e4 e5 1/2-1/2'
        dlg = _risultato(genitore, pgn=pgn)
        try:
            codice = _apri_e_premi(dlg, "invio", _prima_voce)
            assert codice == RIMASTA_APERTA
            assert dlg.txt_pgn.GetValue() == pgn
        finally:
            dlg.Destroy()

    def test_conferma_risultato_premuto_senza_risultato_resta(self, genitore, suoni):
        """Anche Conferma Risultato premuto con la barra spaziatrice, senza
        un risultato scelto, fa sentire l'errore e lascia la finestra
        aperta: chiudendosi direbbe confermato un risultato che non c'e'."""
        dlg = _risultato(genitore)
        try:
            codice = _apri_e_premi(dlg, "spazio", lambda f: f.btn_ok, prima=lambda f: suoni.clear())
            assert codice == RIMASTA_APERTA, "Conferma Risultato ha chiuso la finestra"
            assert "errore" in suoni
            assert "conferma" not in suoni
        finally:
            dlg.Destroy()

    def test_invio_su_conferma_risultato_senza_risultato_resta(self, genitore, suoni):
        dlg = _risultato(genitore)
        try:
            codice = _apri_e_premi(dlg, "invio", lambda f: f.btn_ok, prima=lambda f: suoni.clear())
            assert codice == RIMASTA_APERTA
            assert "errore" in suoni
        finally:
            dlg.Destroy()


class TestInvioConUnRisultato:
    def test_con_la_voce_scelta_invio_conferma(self, genitore, suoni):
        """Scelta una voce, INVIO conferma, come prima."""
        import wx

        def scegli(finestra):
            _prima_voce(finestra).SetValue(True)

        dlg = _risultato(genitore)
        try:
            codice = _apri_e_premi(dlg, "invio", _prima_voce, prima=scegli)
            assert codice == wx.ID_OK
            assert dlg.get_selected_result() == "1-0"
            assert "errore" not in suoni
            assert suoni[-1] == "conferma"
        finally:
            dlg.Destroy()

    def test_con_il_risultato_di_prima_invio_conferma(self, genitore, suoni):
        """La finestra aperta su una partita che ha gia' il risultato: INVIO
        lo conferma, anche con il fuoco su un'altra voce."""
        import wx

        dlg = _risultato(genitore, risultato="1/2-1/2")
        try:
            codice = _apri_e_premi(dlg, "invio", _prima_voce)
            assert codice == wx.ID_OK
            assert dlg.get_selected_result() == "1/2-1/2"
        finally:
            dlg.Destroy()

    def test_con_la_voce_scelta_conferma_risultato_conferma(self, genitore, suoni):
        import wx

        def scegli(finestra):
            finestra.radio_buttons[1][1].SetValue(True)

        dlg = _risultato(genitore)
        try:
            codice = _apri_e_premi(dlg, "spazio", lambda f: f.btn_ok, prima=scegli)
            assert codice == wx.ID_OK
            assert dlg.get_selected_result() == "0-1"
        finally:
            dlg.Destroy()

    def test_annulla_senza_risultato_chiude(self, genitore, suoni):
        """Annulla, senza un risultato scelto, chiude come sempre."""
        import wx

        dlg = _risultato(genitore)
        try:
            codice = _apri_e_premi(dlg, "spazio", lambda f: f.FindWindowById(wx.ID_CANCEL, f))
            assert codice == wx.ID_CANCEL
            assert codice != CHIUSA_DALLA_RETE
        finally:
            dlg.Destroy()
