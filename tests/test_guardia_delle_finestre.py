"""La guardia delle finestre vere, dalla 10.13.22.

Il 26 settembre 2026 una prova ha aperto sullo schermo di Gabriele una
finestra Errore, rimasta li' dieci minuti, perche' un dialogo non era
sostituito. La guardia sta in conftest.py, fixture nessuna_finestra_vera:
queste prove verificano che sorvegli i ShowModal di wx e dei dialoghi di
Tornello, wx.MessageBox e il Show delle finestre di primo livello, le
finestre che si mostrano da sole appena create, come wx.ProgressDialog, i
menu contestuali e le altre finestre a comparsa, il browser e i programmi
che Windows apre per un file, che una chiamata faccia fallire la prova anche
quando qualcuno la ingoia, e che le prove restino libere di sostituire tutto
con monkeypatch.
Prima di chiamare davvero un metodo sorvegliato, ogni prova controlla che al
suo posto ci sia la guardia: se un giorno la guardia si rompesse, la prova
fallirebbe senza aprire niente.
"""

import contextlib
import importlib
import inspect
import os
import pkgutil
from types import SimpleNamespace

import pytest
from conftest import CARTELLA_SRC

# I dialoghi di wx che hanno un ShowModal tutto loro.
DIALOGHI_DI_WX = (
    "Dialog",
    "MessageDialog",
    "FileDialog",
    "DirDialog",
    "SingleChoiceDialog",
    "MultiChoiceDialog",
    "TextEntryDialog",
    "ColourDialog",
    "FontDialog",
)


def _sorvegliato(funzione):
    return getattr(funzione, "guardia_delle_finestre", False)


def _showmodal_che_arriva_a_wx(classe):
    """Il primo ShowModal non scritto in Python lungo la catena delle classi:
    e' quello che apre la finestra. Un ShowModal scritto in Python, come
    quello della finestra del risultato, chiama super() e ci arriva."""
    for antenata in classe.__mro__:
        metodo = antenata.__dict__.get("ShowModal")
        if metodo is None:
            continue
        if _sorvegliato(metodo) or not inspect.isfunction(metodo):
            return metodo
    return None


def _dialoghi_di_tornello(wx):
    """Tutte le classi di finestra di dialogo scritte sotto src/gui."""
    cartella = os.path.join(CARTELLA_SRC, "gui", "dialogs")
    for modulo in pkgutil.iter_modules([cartella]):
        importlib.import_module(f"gui.dialogs.{modulo.name}")
    importlib.import_module("gui.main_frame")
    visti = []
    da_visitare = list(wx.Dialog.__subclasses__())
    while da_visitare:
        classe = da_visitare.pop()
        da_visitare.extend(classe.__subclasses__())
        if classe.__module__.startswith("gui."):
            visti.append(classe)
    return visti


def _chiudi(finestra):
    """Distrugge subito i controlli e poi la finestra: la distruzione di una
    finestra di primo livello aspetta il ciclo degli eventi, e intanto il
    SetFocus che AccessibleMsgDialog rinvia con CallAfter potrebbe arrivare
    al testo di una finestra nascosta."""
    finestra.DestroyChildren()
    finestra.Destroy()


def _messaggio(telaio, stile=None):
    import wx

    from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog

    return AccessibleMsgDialog(telaio, "Titolo", "Testo", style=stile or wx.OK, settings={})


class TestCosaSorveglia:
    def test_i_dialoghi_di_wx(self, app_grafica):
        import wx

        for nome in DIALOGHI_DI_WX:
            classe = getattr(wx, nome)
            assert _sorvegliato(classe.__dict__["ShowModal"]), f"wx.{nome}.ShowModal non e' sorvegliato"

    def test_le_funzioni_che_aprono_una_finestra(self, app_grafica):
        import wx
        import wx.adv

        for nome in ("MessageBox", "GetTextFromUser", "GetSingleChoice", "FileSelector", "DirSelector"):
            assert _sorvegliato(getattr(wx, nome)), f"wx.{nome} non e' sorvegliata"
        assert _sorvegliato(wx.adv.AboutBox)

    def test_il_show_delle_finestre(self, app_grafica):
        import wx

        assert _sorvegliato(wx.Window.__dict__["Show"])
        assert _sorvegliato(wx.Dialog.__dict__["Show"])
        assert _sorvegliato(wx.TopLevelWindow.__dict__["ShowWithoutActivating"])

    def test_le_finestre_che_si_mostrano_da_sole(self, app_grafica):
        # Il C++ di wx le mostra appena create, senza passare da Show: si
        # sostituisce la classe intera.
        import wx
        import wx.adv

        for classe in (wx.ProgressDialog, wx.GenericProgressDialog, wx.BusyInfo, wx.TipWindow, wx.adv.SplashScreen):
            assert _sorvegliato(classe), f"{classe.__name__} non e' sorvegliata"

    def test_i_metodi_che_aprono_qualcosa_senza_show(self, app_grafica):
        import wx
        import wx.adv

        for classe, nome in (
            (wx.Window, "PopupMenu"),
            (wx.Window, "GetPopupMenuSelectionFromUser"),
            (wx.TopLevelWindow, "ShowFullScreen"),
            (wx.PopupTransientWindow, "Popup"),
            (wx.ComboBox, "Popup"),
            (wx.PrintDialog, "ShowModal"),
            (wx.Printer, "Print"),
            (wx.adv.Wizard, "RunWizard"),
            (wx.adv.NotificationMessage, "Show"),
            (wx.adv.TaskBarIcon, "SetIcon"),
        ):
            assert _sorvegliato(classe.__dict__[nome]), f"{classe.__name__}.{nome} non e' sorvegliato"

    def test_il_browser_e_i_programmi_di_windows(self):
        import os
        import webbrowser

        for funzione in (webbrowser.open, webbrowser.open_new, webbrowser.open_new_tab, os.startfile):
            assert _sorvegliato(funzione), funzione.__name__

    def test_i_dialoghi_di_tornello(self, app_grafica):
        import wx

        dialoghi = _dialoghi_di_tornello(wx)
        nomi = {classe.__name__ for classe in dialoghi}
        # La ricerca li trova davvero: qualcuno dei piu' usati c'e'.
        assert {"AccessibleMsgDialog", "ResultDialog", "ScheduleDialog", "VisualSettingsDialog"} <= nomi
        for classe in dialoghi:
            assert _sorvegliato(_showmodal_che_arriva_a_wx(classe)), f"{classe.__name__} arriva a un ShowModal non sorvegliato"


class TestLaGuardiaScatta:
    def test_showmodal_di_un_dialogo_di_tornello(self, app_grafica, nessuna_finestra_vera):
        import wx

        assert _sorvegliato(wx.Dialog.__dict__["ShowModal"])
        dialogo = _messaggio(None)
        try:
            with pytest.raises(pytest.fail.Exception, match="ShowModal di AccessibleMsgDialog"):
                dialogo.ShowModal()
        finally:
            _chiudi(dialogo)
        assert len(nessuna_finestra_vera.chiamate) == 1
        nessuna_finestra_vera.chiamate.clear()

    def test_showmodal_di_un_dialogo_di_wx(self, app_grafica, nessuna_finestra_vera):
        import wx

        assert _sorvegliato(wx.MessageDialog.__dict__["ShowModal"])
        dialogo = wx.MessageDialog(None, "Testo", "Titolo")
        try:
            with pytest.raises(pytest.fail.Exception, match=r"MessageDialog\.ShowModal"):
                dialogo.ShowModal()
        finally:
            _chiudi(dialogo)
        nessuna_finestra_vera.chiamate.clear()

    def test_messagebox(self, app_grafica, nessuna_finestra_vera):
        import wx

        assert _sorvegliato(wx.MessageBox)
        with pytest.raises(pytest.fail.Exception, match=r"wx\.MessageBox"):
            wx.MessageBox("Testo", "Errore", wx.OK | wx.ICON_ERROR)
        nessuna_finestra_vera.chiamate.clear()

    def test_showmodal_scritto_in_python_che_chiama_super(self, app_grafica, nessuna_finestra_vera):
        import wx

        class Dialogo(wx.Dialog):
            def ShowModal(self):
                return super().ShowModal()

        assert _sorvegliato(wx.Dialog.__dict__["ShowModal"])
        dialogo = Dialogo(None, title="Prova")
        try:
            with pytest.raises(pytest.fail.Exception):
                dialogo.ShowModal()
        finally:
            _chiudi(dialogo)
        nessuna_finestra_vera.chiamate.clear()

    def test_show_di_una_finestra_di_primo_livello(self, app_grafica, nessuna_finestra_vera):
        import wx

        assert _sorvegliato(wx.Window.__dict__["Show"])
        telaio = wx.Frame(None, title="Prova")
        try:
            with pytest.raises(pytest.fail.Exception, match="Show di Frame"):
                telaio.Show()
            assert not telaio.IsShown()
            # Nasconderla, o mostrare un controllo dentro la finestra che
            # resta invisibile, non apre niente e resta permesso.
            telaio.Show(False)
            pannello = wx.Panel(telaio)
            pannello.Show(False)
            assert pannello.Show(True)
        finally:
            _chiudi(telaio)
        assert len(nessuna_finestra_vera.chiamate) == 1
        nessuna_finestra_vera.chiamate.clear()

    @pytest.mark.parametrize(
        ("modulo", "nome", "argomenti"),
        [
            ("wx", "ProgressDialog", ("Titolo", "Testo")),
            ("wx", "GenericProgressDialog", ("Titolo", "Testo")),
            ("wx", "BusyInfo", ("Attendere",)),
            ("wx", "TipWindow", (None, "Testo")),
            ("wx.adv", "SplashScreen", (None, 0, 0, None)),
        ],
    )
    def test_una_finestra_che_si_mostra_da_sola(self, app_grafica, nessuna_finestra_vera, modulo, nome, argomenti):
        # Si ferma alla creazione, prima che il C++ la mostri: fino alla
        # correzione della 10.13.22 wx.ProgressDialog si mostrava senza che
        # la guardia se ne accorgesse.
        classe = getattr(importlib.import_module(modulo), nome)
        assert _sorvegliato(classe)
        with pytest.raises(pytest.fail.Exception, match=rf"{modulo}\.{nome} vero"):
            classe(*argomenti)
        assert len(nessuna_finestra_vera.chiamate) == 1
        nessuna_finestra_vera.chiamate.clear()

    def test_la_barra_di_avanzamento_della_sincronizzazione(self, app_grafica, nessuna_finestra_vera, monkeypatch):
        # Il caso vero: Sincronizza tutto apre una wx.ProgressDialog.
        from gui.dialogs import sync_database_dialog

        suoni = []
        monkeypatch.setattr(sync_database_dialog, "play_sound", lambda nome, *a, **k: suoni.append(nome))
        assert _sorvegliato(sync_database_dialog.wx.ProgressDialog)
        dialogo = sync_database_dialog.SyncDatabaseDialog(None, {})
        try:
            with pytest.raises(pytest.fail.Exception, match=r"wx\.ProgressDialog vero"):
                dialogo.on_bulk_sync(None)
        finally:
            _chiudi(dialogo)
        assert suoni == ["fide_attesa"]
        nessuna_finestra_vera.chiamate.clear()

    def test_il_menu_contestuale(self, app_grafica, nessuna_finestra_vera):
        import wx

        assert _sorvegliato(wx.Window.__dict__["PopupMenu"])
        assert _sorvegliato(wx.Window.__dict__["GetPopupMenuSelectionFromUser"])
        telaio = wx.Frame(None, title="Prova")
        menu = wx.Menu()
        menu.Append(wx.ID_ANY, "Voce")
        try:
            with pytest.raises(pytest.fail.Exception, match="PopupMenu di Frame"):
                telaio.PopupMenu(menu)
            with pytest.raises(pytest.fail.Exception, match="GetPopupMenuSelectionFromUser di Frame"):
                telaio.GetPopupMenuSelectionFromUser(menu)
        finally:
            menu.Destroy()
            _chiudi(telaio)
        assert len(nessuna_finestra_vera.chiamate) == 2
        nessuna_finestra_vera.chiamate.clear()

    def test_il_menu_dei_modificatori_degli_spareggi(self, app_grafica, nessuna_finestra_vera, monkeypatch):
        # Il caso vero: il pulsante Modificatori, o il tasto Applicazioni,
        # apre un menu contestuale che aspetta una scelta.
        import wx

        from gui.dialogs import tiebreak_config_dialog
        from tiebreak_criteria import get_supported_modifiers

        suoni = []
        monkeypatch.setattr(tiebreak_config_dialog, "play_sound", lambda nome, *a, **k: suoni.append(nome))
        assert _sorvegliato(wx.Window.__dict__["PopupMenu"])
        telaio = wx.Frame(None, title="Prova")
        telaio.settings = {}
        dialogo = tiebreak_config_dialog.TiebreakConfigDialog(telaio, {"name": "Prova", "players": []})
        try:
            voce = next(i for i, e in enumerate(dialogo.applied_entries) if get_supported_modifiers(e["key"]))
            dialogo.list_applied.SetSelection(voce)
            with pytest.raises(pytest.fail.Exception, match="PopupMenu di TiebreakConfigDialog"):
                dialogo.on_show_modifiers()
        finally:
            _chiudi(dialogo)
            _chiudi(telaio)
        assert suoni == []
        nessuna_finestra_vera.chiamate.clear()

    def test_schermo_intero_e_finestre_a_comparsa(self, app_grafica, nessuna_finestra_vera):
        import wx

        assert _sorvegliato(wx.TopLevelWindow.__dict__["ShowFullScreen"])
        assert _sorvegliato(wx.Window.__dict__["Show"])
        assert _sorvegliato(wx.PopupTransientWindow.__dict__["Popup"])
        telaio = wx.Frame(None, title="Prova")
        try:
            with pytest.raises(pytest.fail.Exception, match="ShowFullScreen di Frame"):
                telaio.ShowFullScreen(True)
            # Uscire dallo schermo intero non mostra niente.
            telaio.ShowFullScreen(False)
            # Una finestra a comparsa non e' di primo livello, e il suo Show
            # non si puo' controllare prima di chiamarlo: la si mette fuori
            # dallo schermo, cosi' che nemmeno una guardia rotta la mostri.
            comparsa = wx.PopupWindow(telaio)
            comparsa.SetPosition(wx.Point(-32000, -32000))
            with pytest.raises(pytest.fail.Exception, match="Show di PopupWindow"):
                comparsa.Show()
            assert not comparsa.IsShown()
            transitoria = wx.PopupTransientWindow(telaio)
            with pytest.raises(pytest.fail.Exception, match="Popup di PopupTransientWindow"):
                transitoria.Popup()
        finally:
            _chiudi(telaio)
        assert len(nessuna_finestra_vera.chiamate) == 3
        nessuna_finestra_vera.chiamate.clear()

    def test_procedura_guidata_e_notifica(self, app_grafica, nessuna_finestra_vera):
        import wx.adv

        assert _sorvegliato(wx.adv.Wizard.__dict__["RunWizard"])
        assert _sorvegliato(wx.adv.NotificationMessage.__dict__["Show"])
        procedura = wx.adv.Wizard(None, title="Prova")
        pagina = wx.adv.WizardPageSimple(procedura)
        try:
            with pytest.raises(pytest.fail.Exception, match="RunWizard di Wizard"):
                procedura.RunWizard(pagina)
        finally:
            _chiudi(procedura)
        notifica = wx.adv.NotificationMessage("Titolo", "Testo")
        with pytest.raises(pytest.fail.Exception, match="Show di NotificationMessage"):
            notifica.Show()
        assert len(nessuna_finestra_vera.chiamate) == 2
        nessuna_finestra_vera.chiamate.clear()

    def test_il_browser_e_i_programmi_di_windows(self, nessuna_finestra_vera, tmp_path):
        import os
        import webbrowser

        assert _sorvegliato(webbrowser.open)
        with pytest.raises(pytest.fail.Exception, match=r"webbrowser\.open vero"):
            webbrowser.open("https://example.invalid")
        # Un file che non c'e': se la guardia mancasse, non si aprirebbe
        # niente lo stesso.
        assert _sorvegliato(os.startfile)
        with pytest.raises(pytest.fail.Exception, match=r"os\.startfile vero"):
            os.startfile(str(tmp_path / "non_esiste.txt"))  # noqa: S606 - e' la guardia a rispondere
        assert len(nessuna_finestra_vera.chiamate) == 2
        nessuna_finestra_vera.chiamate.clear()

    def test_una_chiamata_ingoiata_fa_fallire_la_prova_alla_fine(self, app_grafica, nessuna_finestra_vera):
        # Come fa wx con l'errore di un gestore di eventi: lo stampa e va
        # avanti. La prova non vede l'eccezione, ma la guardia l'ha annotata.
        import wx

        assert _sorvegliato(wx.MessageBox)
        with contextlib.suppress(BaseException):
            wx.MessageBox("Testo")
        assert nessuna_finestra_vera.chiamate
        with pytest.raises(pytest.fail.Exception, match=r"wx\.MessageBox"):
            nessuna_finestra_vera.verifica(SimpleNamespace(failed=False))
        with pytest.raises(pytest.fail.Exception):
            nessuna_finestra_vera.verifica(None)
        # Se la prova e' gia' fallita per quella chiamata, non si ripete.
        nessuna_finestra_vera.verifica(SimpleNamespace(failed=True))
        nessuna_finestra_vera.chiamate.clear()


class TestLeProveSostituisconoLiberamente:
    def test_showmodal_e_messagebox_sostituiti(self, app_grafica, nessuna_finestra_vera, monkeypatch):
        import wx

        monkeypatch.setattr(wx.Dialog, "ShowModal", lambda self: wx.ID_YES)
        monkeypatch.setattr("wx.MessageBox", lambda *a, **k: wx.OK)
        dialogo = _messaggio(None, wx.YES_NO)
        try:
            assert dialogo.ShowModal() == wx.ID_YES
        finally:
            _chiudi(dialogo)
        assert wx.MessageBox("Testo") == wx.OK
        assert nessuna_finestra_vera.chiamate == []

    def test_barra_di_avanzamento_menu_e_browser_sostituiti(self, app_grafica, nessuna_finestra_vera, monkeypatch):
        import webbrowser

        import wx

        class AvanzamentoFinto:
            def __init__(self, *a, **k):
                self.passi = []

            def Update(self, *argomenti):
                self.passi.append(argomenti)
                return True, False

        monkeypatch.setattr(wx, "ProgressDialog", AvanzamentoFinto)
        monkeypatch.setattr(wx.Window, "PopupMenu", lambda finestra, menu, *a: True)
        aperti = []
        monkeypatch.setattr(webbrowser, "open", aperti.append)
        avanzamento = wx.ProgressDialog("Titolo", "Testo")
        assert avanzamento.Update(1, "Passo") == (True, False)
        telaio = wx.Frame(None, title="Prova")
        menu = wx.Menu()
        try:
            assert telaio.PopupMenu(menu) is True
        finally:
            menu.Destroy()
            _chiudi(telaio)
        webbrowser.open("https://example.invalid")
        assert aperti == ["https://example.invalid"]
        assert nessuna_finestra_vera.chiamate == []

    def test_la_classe_di_un_dialogo_sostituita(self, app_grafica, nessuna_finestra_vera, monkeypatch):
        import wx

        from gui.dialogs import result_dialog

        monkeypatch.setattr(result_dialog.ScheduleDialog, "ShowModal", lambda self: wx.ID_CANCEL)
        dialogo = result_dialog.ScheduleDialog(None, {}, {}, {})
        try:
            assert dialogo.ShowModal() == wx.ID_CANCEL
        finally:
            _chiudi(dialogo)
        assert nessuna_finestra_vera.chiamate == []
