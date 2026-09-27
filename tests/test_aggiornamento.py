"""L'aggiornamento del programma, nelle sue due facce. Issue 37.

Fino alla 10.6.5 la finestra proponeva l'aggiornamento con un AccessibleMsgDialog
che diceva le due versioni e taceva le note, lo scaricamento non si vedeva, e
la proposta si apriva insieme alle domande sul database FIDE e sui backup,
anche sopra di loro. La console decideva sulle sole due versioni. Dalla 10.7.0
la finestra ha le note e una finestra di avanzamento, dalla 10.8.0 la console
le impagina con manuale, dalla 10.8.1 la chiusura per aggiornamento salta
l'invito alla donazione (la prova sta in test_donazione.py) e dalla 10.8.2 la
proposta, i suoi esiti e le domande dell'avvio si aprono uno alla volta, a
finestra libera.
Niente rete e niente aggiornamenti veri: gestisci_aggiornamento e' sempre
sostituita da una finta. Niente finestra principale vera: i metodi di
MainFrame girano su telai finti. Le finestre dei due dialoghi nascono vere, ma
non vengono mai mostrate, e nessuna suona.
"""

import ast
import importlib.util
import inspect
import os
import sys
from types import SimpleNamespace

import pytest

RADICE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MB = 1024 * 1024


def _chiudi(dlg):
    """Distrugge un dialogo mai mostrato, controlli compresi, come le prove
    delle finestre adattabili."""
    dlg.DestroyChildren()
    dlg.Destroy()


def _righe(dlg):
    return dlg.campo_note.GetValue().split("\n")


class TestFinestraDellAggiornamento:
    """UpdateDialog: le due versioni in testa al campo, le note, i pulsanti."""

    def _crea(self, note="riga uno\r\nriga due\r\n"):
        from gui.dialogs.update_dialog import UpdateDialog

        return UpdateDialog(None, "10.6.5", "10.7.0", note, {})

    def test_esc_e_la_chiusura_valgono_non_adesso(self, app_grafica):
        import wx

        dlg = self._crea()
        try:
            assert dlg.GetEscapeId() == wx.ID_NO
            assert dlg.GetAffirmativeId() == wx.ID_YES
            assert dlg.btn_aggiorna.GetId() == wx.ID_YES
            assert dlg.btn_rimanda.GetId() == wx.ID_NO
        finally:
            _chiudi(dlg)

    def test_esc_e_invio_nel_giro_vero_di_wx(self, app_grafica, monkeypatch):
        """Il tasto mandato al dialogo come lo manda Windows, senza mostrare
        la finestra: ESC passa dal gestore di wx, che preme Non adesso, e
        INVIO nel campo da quello del dialogo. EndModal e' sostituito, perche'
        il dialogo non e' modale. La chiusura con la X e con Alt+F4, che wx
        traduce anch'essa in Non adesso, si vede solo a finestra modale: e'
        fra le prove a mano."""
        import wx

        dlg = self._crea()
        try:
            chiusure = []
            dlg.EndModal = chiusure.append
            monkeypatch.setattr(wx.Window, "FindFocus", lambda: dlg.campo_note)
            for codice, atteso in ((wx.WXK_ESCAPE, wx.ID_NO), (wx.WXK_RETURN, wx.ID_YES)):
                chiusure.clear()
                evento = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
                evento.SetKeyCode(codice)
                evento.SetEventObject(dlg.campo_note)
                dlg.ProcessEvent(evento)
                assert chiusure == [atteso]
        finally:
            _chiudi(dlg)

    def test_pulsanti_e_pulsante_predefinito(self, app_grafica):
        from gui.dialogs import update_dialog

        dlg = self._crea()
        try:
            assert dlg.btn_aggiorna.GetLabel() == update_dialog._("Aggiorna adesso")
            assert dlg.btn_rimanda.GetLabel() == update_dialog._("Non adesso")
            assert dlg.GetDefaultItem() is dlg.btn_aggiorna
        finally:
            _chiudi(dlg)

    def test_il_campo_e_multilinea_e_di_sola_lettura(self, app_grafica):
        dlg = self._crea()
        try:
            assert dlg.campo_note.IsMultiLine()
            assert not dlg.campo_note.IsEditable()
            # L'etichetta viene subito prima del campo, anche per il Tab.
            figli = list(dlg.pannello.GetChildren())
            assert figli.index(dlg.etichetta_note) + 1 == figli.index(dlg.campo_note)
        finally:
            _chiudi(dlg)

    def test_la_prima_riga_dice_le_due_versioni_in_ordine(self, app_grafica):
        dlg = self._crea()
        try:
            prima = _righe(dlg)[0]
            assert "10.6.5" in prima and "10.7.0" in prima
            assert prima.index("10.6.5") < prima.index("10.7.0")
            assert dlg.campo_note.GetInsertionPoint() == 0
        finally:
            _chiudi(dlg)

    def test_le_note_si_leggono_riga_per_riga(self, app_grafica):
        dlg = self._crea("\r\n## Novita'\r\n* riga uno\r\n\r\n* riga due\r\n\r\n")
        try:
            assert _righe(dlg)[1:] == ["## Novita'", "* riga uno", "", "* riga due"]
            assert "\r" not in dlg.campo_note.GetValue()
        finally:
            _chiudi(dlg)

    def test_la_v_del_tag_non_si_legge(self):
        """Il tag della release su GitHub e' v10.9.0, e update_checker lo
        passa cosi': la prima riga dice le due versioni allo stesso modo,
        senza v."""
        from gui.dialogs.update_dialog import testo_delle_note

        prima = testo_delle_note("10.8.2", "v10.9.0", "note").split("\n")[0]
        assert prima == "Versione attuale 10.8.2, nuova 10.9.0."
        assert testo_delle_note("V10.8.2", "10.9.0", None).split("\n")[0] == prima

    @pytest.mark.parametrize("note", [None, "", "  \r\n  \r\n"])
    def test_senza_note_lo_dice(self, app_grafica, note):
        from gui.dialogs import update_dialog

        dlg = self._crea(note)
        try:
            righe = _righe(dlg)
            assert len(righe) == 2
            assert righe[1] == update_dialog._("Nessuna nota per questa versione.")
        finally:
            _chiudi(dlg)

    def _tasto(self, dlg, codice, fuoco, monkeypatch):
        """Manda un tasto al gestore di INVIO con il fuoco dove si vuole, e
        dice con quale risposta si e' chiuso il dialogo e se il tasto e'
        proseguito."""
        import wx

        chiusure = []
        dlg.EndModal = chiusure.append
        monkeypatch.setattr(wx.Window, "FindFocus", lambda: fuoco)
        evento = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
        evento.SetKeyCode(codice)
        dlg._on_tasto(evento)
        return chiusure, evento.GetSkipped()

    def test_invio_nel_campo_aggiorna(self, app_grafica, monkeypatch):
        import wx

        dlg = self._crea()
        try:
            for codice in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                chiusure, proseguito = self._tasto(dlg, codice, dlg.campo_note, monkeypatch)
                assert chiusure == [wx.ID_YES]
                assert not proseguito
        finally:
            _chiudi(dlg)

    def test_invio_sui_pulsanti_e_esc_proseguono(self, app_grafica, monkeypatch):
        import wx

        dlg = self._crea()
        try:
            chiusure, proseguito = self._tasto(dlg, wx.WXK_RETURN, dlg.btn_rimanda, monkeypatch)
            assert chiusure == [] and proseguito
            chiusure, proseguito = self._tasto(dlg, wx.WXK_ESCAPE, dlg.campo_note, monkeypatch)
            assert chiusure == [] and proseguito
        finally:
            _chiudi(dlg)


class TestFinestraDelloScaricamento:
    """UpdateProgressDialog: un messaggio ogni venti per cento, il testo
    finale, e nessun modo di chiuderla."""

    @pytest.fixture
    def dialogo(self, app_grafica, monkeypatch):
        import wx

        from gui.dialogs.update_dialog import UpdateProgressDialog

        notifiche = []
        monkeypatch.setattr(wx.Accessible, "NotifyEvent", lambda *argomenti: notifiche.append(argomenti))
        dlg = UpdateProgressDialog(None, {})
        dlg.notifiche = notifiche
        yield dlg
        _chiudi(dlg)

    def test_il_messaggio_cambia_ogni_venti_per_cento(self, dialogo):
        from gui.dialogs import update_dialog

        iniziale = dialogo.status_label.GetLabel()
        assert iniziale == update_dialog._("Scarico l'aggiornamento.")
        visti = []
        for preso in (0, 1, 10, 19, 20, 21, 39, 40, 41, 60, 80, 99):
            dialogo.aggiorna(preso * MB, 100 * MB)
            assert dialogo.gauge.GetValue() == preso
            testo = dialogo.status_label.GetLabel()
            if not visti or visti[-1] != testo:
                visti.append(testo)
        assert visti == [
            iniziale,
            "20%, 20,0 MB su 100,0 MB.",
            "40%, 40,0 MB su 100,0 MB.",
            "60%, 60,0 MB su 100,0 MB.",
            "80%, 80,0 MB su 100,0 MB.",
        ]

    def test_un_passo_saltato_si_annuncia_con_la_percentuale_vera(self, dialogo):
        dialogo.aggiorna(47 * MB, 100 * MB)
        assert dialogo.status_label.GetLabel() == "47%, 47,0 MB su 100,0 MB."
        dialogo.aggiorna(55 * MB, 100 * MB)
        assert dialogo.status_label.GetLabel() == "47%, 47,0 MB su 100,0 MB."

    def test_a_scaricamento_finito_prepara_l_aggiornamento(self, dialogo):
        from gui.dialogs import update_dialog

        dialogo.aggiorna(90 * MB, 100 * MB)
        dialogo.aggiorna(100 * MB, 100 * MB)
        assert dialogo.gauge.GetValue() == 100
        assert dialogo.status_label.GetLabel() == update_dialog._("Scaricato, preparo l'aggiornamento.")

    @pytest.mark.parametrize("carattere", [12, 16, 24])
    def test_ogni_messaggio_sta_nella_finestra(self, app_grafica, monkeypatch, carattere):
        """Anche il messaggio finale, piu' lungo del primo, sta nell'area
        visibile, con il carattere dei dialoghi grande: nella 10.7.0 la
        finestra prendeva la misura dal primo messaggio. Lo schermo e' quello
        di serie, piu' largo della finestra."""
        import wx

        from gui.dialogs import update_dialog

        monkeypatch.setattr(wx.Accessible, "NotifyEvent", lambda *argomenti: None)
        dlg = update_dialog.UpdateProgressDialog(None, {"dialog_font_size": carattere})
        try:
            visibile = dlg.pannello.GetClientSize().width
            for preso, totale in ((0, 0), (40 * MB, int(93.6 * MB)), (999 * MB, 1000 * MB), (MB, MB)):
                dlg.aggiorna(preso, totale)
                # 15 pixel di bordo per parte, come nel sizer della finestra.
                assert dlg.status_label.GetBestSize().width + 30 <= visibile, dlg.status_label.GetLabel()
            assert dlg.status_label.GetLabel() == update_dialog.testo_finale()
            assert len(update_dialog.testo_finale()) <= 40
        finally:
            _chiudi(dlg)

    def test_senza_totale_nessuna_percentuale(self, dialogo):
        iniziale = dialogo.status_label.GetLabel()
        dialogo.aggiorna(5 * MB, 0)
        assert dialogo.status_label.GetLabel() == iniziale
        assert dialogo.notifiche == []

    def test_ogni_messaggio_diventa_il_nome_della_barra_e_si_notifica(self, dialogo):
        import wx

        dialogo.aggiorna(20 * MB, 100 * MB)
        dialogo.aggiorna(30 * MB, 100 * MB)
        dialogo.aggiorna(100 * MB, 100 * MB)
        assert dialogo._nome_della_barra.nome == dialogo.status_label.GetLabel()
        assert dialogo.notifiche == [
            (wx.ACC_EVENT_OBJECT_NAMECHANGE, dialogo.gauge, wx.OBJID_CLIENT, wx.ACC_SELF)
        ] * 2

    def test_non_si_chiude(self, dialogo):
        import wx

        assert dialogo.GetEscapeId() == wx.ID_NONE
        assert dialogo.Close() is False
        assert dialogo
        # Una chiusura che non si puo' rifiutare, per esempio quella del
        # sistema, passa.
        evento = wx.CloseEvent(wx.wxEVT_CLOSE_WINDOW)
        evento.SetCanVeto(False)
        dialogo._on_close(evento)
        assert evento.GetSkipped() and not evento.GetVeto()


class TestFrasiDiGBUtils:
    """Le frasi di gestisci_aggiornamento entrano nei cataloghi attraverso la
    tupla di aggiornamenti.py: se GBUtils ne cambia una, la traduzione non si
    trova piu' e l'utente la sente in italiano."""

    def _frasi_della_tupla(self):
        with open(os.path.join(RADICE, "src", "aggiornamenti.py"), encoding="utf-8") as f:
            albero = ast.parse(f.read())
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.Assign) and any(getattr(t, "id", None) == "FRASI_AGGIORNAMENTO_GBUTILS" for t in nodo.targets):
                return [chiamata.args[0].value for chiamata in nodo.value.elts]
        raise AssertionError("FRASI_AGGIORNAMENTO_GBUTILS non trovata")

    def _frasi_di_gbutils(self):
        import textwrap

        import GBUtils

        albero = ast.parse(textwrap.dedent(inspect.getsource(GBUtils.gestisci_aggiornamento)))
        return {
            nodo.args[0].value
            for nodo in ast.walk(albero)
            if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", None) == "tr" and isinstance(nodo.args[0], ast.Constant)
        }

    def test_ogni_frase_della_tupla_e_scritta_in_gbutils(self):
        import GBUtils

        sorgente = inspect.getsource(GBUtils.gestisci_aggiornamento)
        frasi = self._frasi_della_tupla()
        assert len(frasi) == 13
        for frase in frasi:
            assert f'tr("{frase}")' in sorgente, frase

    def test_la_tupla_ha_tutte_le_frasi_di_gbutils(self):
        frasi = self._frasi_della_tupla()
        assert len(set(frasi)) == len(frasi)
        assert set(frasi) == self._frasi_di_gbutils()


class TestConsole:
    """tornello.py --cli: gestisci_aggiornamento senza avvisa, cosi' le note
    passano da manuale, con la conferma della console e la traduzione."""

    def test_aggiorna_da_console_passa_gli_argomenti_giusti(self, monkeypatch):
        import GBUtils

        import aggiornamenti
        from cli_adapter import CLIAdapter
        from version import __version__

        chiamate = []

        def finta(*argomenti, **opzioni):
            chiamate.append((argomenti, opzioni))
            return False

        monkeypatch.setattr(GBUtils, "gestisci_aggiornamento", finta)

        assert aggiornamenti.aggiorna_da_console() is False
        (argomenti, opzioni), = chiamate
        assert argomenti == ("tornello", __version__, aggiornamenti.API_RELEASE)
        assert aggiornamenti.API_RELEASE == "https://api.github.com/repos/GabrieleBattaglia/Tornello/releases/latest"
        assert set(opzioni) == {"chiedi", "traduci"}
        assert opzioni["traduci"] is aggiornamenti._
        assert opzioni["chiedi"].__func__ is CLIAdapter.confirm
        assert isinstance(opzioni["chiedi"].__self__, CLIAdapter)

    def test_restituisce_la_risposta_di_gbutils(self, monkeypatch):
        import GBUtils

        import aggiornamenti

        monkeypatch.setattr(GBUtils, "gestisci_aggiornamento", lambda *a, **k: True)
        assert aggiornamenti.aggiorna_da_console() is True

    @pytest.fixture
    def avvio(self, monkeypatch):
        """tornello.py caricato come modulo, senza eseguirne l'avvio. Il suo
        gestore delle eccezioni e il percorso dei moduli tornano com'erano."""
        monkeypatch.setattr(sys, "excepthook", sys.excepthook)
        monkeypatch.setattr(sys, "path", list(sys.path))
        specifica = importlib.util.spec_from_file_location("tornello_avvio", os.path.join(RADICE, "tornello.py"))
        modulo = importlib.util.module_from_spec(specifica)
        specifica.loader.exec_module(modulo)
        return modulo

    def test_check_updates_esce_solo_se_l_aggiornamento_e_pronto(self, monkeypatch, avvio):
        import aggiornamenti

        monkeypatch.setattr(aggiornamenti, "aggiorna_da_console", lambda: False)
        assert avvio.check_updates() is None
        monkeypatch.setattr(aggiornamenti, "aggiorna_da_console", lambda: True)
        with pytest.raises(SystemExit) as uscita:
            avvio.check_updates()
        assert uscita.value.code == 0

    def test_check_updates_con_un_guasto_prosegue(self, monkeypatch, avvio, capsys):
        import aggiornamenti

        def guasta():
            raise OSError("disco pieno")

        monkeypatch.setattr(aggiornamenti, "aggiorna_da_console", guasta)
        assert avvio.check_updates() is None
        assert "disco pieno" in capsys.readouterr().out

    def test_l_aggiornamento_viene_prima_dell_invito_alla_donazione(self):
        """Nel ramo --cli, check_updates va chiamata prima di atexit.register:
        chi esce per aggiornarsi non deve ricevere l'invito."""
        with open(os.path.join(RADICE, "tornello.py"), encoding="utf-8") as f:
            albero = ast.parse(f.read())
        ramo = next(
            nodo
            for nodo in ast.walk(albero)
            if isinstance(nodo, ast.If)
            and isinstance(nodo.test, ast.Compare)
            and getattr(nodo.test.left, "value", None) == "--cli"
            and isinstance(nodo.test.ops[0], ast.In)
        )

        def posizione(nome):
            return next(
                i
                for i, istruzione in enumerate(ramo.body)
                if any(isinstance(n, ast.Call) and ast.unparse(n.func) == nome for n in ast.walk(istruzione))
            )

        assert posizione("check_updates") < posizione("atexit.register")


class _Registro(list):
    """Una lista che annota i passi di un telaio finto."""

    def passo(self, nome, valore=None):
        def registra(*argomenti, **opzioni):
            self.append((nome, *argomenti))
            return valore

        return registra


@pytest.fixture
def main_frame(app_grafica):
    from gui import main_frame

    return main_frame


class TestOrdineDellAvvio:
    """Parla per primo l'aggiornamento, poi il database FIDE e i backup."""

    def test_l_avvio_accoda_solo_i_tornei_e_l_aggiornamento(self):
        with open(os.path.join(RADICE, "src", "gui", "main_frame.py"), encoding="utf-8") as f:
            albero = ast.parse(f.read())
        classe = next(n for n in albero.body if isinstance(n, ast.ClassDef) and n.name == "MainFrame")
        costruttore = next(n for n in classe.body if isinstance(n, ast.FunctionDef) and n.name == "__init__")
        accodate = [
            ast.unparse(n.args[0])
            for n in ast.walk(costruttore)
            if isinstance(n, ast.Call) and ast.unparse(n.func) == "wx.CallAfter"
        ]
        assert accodate == ["self._scan_and_load_initial_tournament", "self._check_updates_async"]
        testo = ast.unparse(costruttore)
        assert "_check_fide_db_on_startup" not in testo
        assert "_check_backup_on_startup" not in testo

    def test_i_controlli_di_avvio_sono_in_fila(self, main_frame):
        registro = _Registro()
        telaio = SimpleNamespace(
            _check_fide_db_on_startup=registro.passo("fide"),
            _check_backup_on_startup=registro.passo("backup"),
        )
        main_frame.MainFrame._controlli_di_avvio(telaio)
        assert registro == [("fide",), ("backup",)]

    def test_un_guasto_della_domanda_fide_non_salta_i_backup(self, main_frame):
        """La domanda sui backup arriva, e il guasto prosegue verso la
        finestra dell'errore imprevisto."""
        registro = _Registro()

        def guasta():
            raise OSError("database FIDE illeggibile")

        telaio = SimpleNamespace(_check_fide_db_on_startup=guasta, _check_backup_on_startup=registro.passo("backup"))
        with pytest.raises(OSError, match="illeggibile"):
            main_frame.MainFrame._controlli_di_avvio(telaio)
        assert registro == [("backup",)]

    def test_senza_aggiornamento_arrivano_le_domande(self, main_frame):
        registro = _Registro()
        telaio = SimpleNamespace(
            _chiudi_avanzamento=registro.passo("chiudi avanzamento"),
            _quando_libera=registro.passo("quando libera"),
            _dopo_aggiornamento="dopo",
            Close=registro.passo("Close"),
            _chiusura_per_aggiornamento=False,
        )
        main_frame.MainFrame._fine_aggiornamento(telaio, False, [])
        assert registro == [("chiudi avanzamento",), ("quando libera", "dopo", [])]
        assert telaio._chiusura_per_aggiornamento is False

    def test_dopo_l_aggiornamento_gli_esiti_poi_le_domande(self, main_frame, monkeypatch):
        registro = _Registro()

        class MessaggioFinto:
            def __init__(self, parent, titolo, messaggio, **opzioni):
                registro.append(("messaggio", messaggio))

            def ShowModal(self):
                registro.append(("mostrato",))

            def Destroy(self):
                registro.append(("distrutto",))

        monkeypatch.setattr(main_frame, "AccessibleMsgDialog", MessaggioFinto)
        telaio = SimpleNamespace(_controlli_di_avvio=registro.passo("controlli"))
        main_frame.MainFrame._dopo_aggiornamento(telaio, ["uno.", "due."])
        assert registro == [("messaggio", "uno.\ndue."), ("mostrato",), ("distrutto",), ("controlli",)]

        registro.clear()
        main_frame.MainFrame._dopo_aggiornamento(telaio, [])
        assert registro == [("controlli",)]

    def test_un_guasto_del_messaggio_non_salta_le_domande(self, main_frame, monkeypatch):
        registro = _Registro()

        def guasto(*argomenti, **opzioni):
            raise RuntimeError("finestra non creata")

        monkeypatch.setattr(main_frame, "AccessibleMsgDialog", guasto)
        telaio = SimpleNamespace(_controlli_di_avvio=registro.passo("controlli"))
        with pytest.raises(RuntimeError, match="non creata"):
            main_frame.MainFrame._dopo_aggiornamento(telaio, ["Aggiornamento non riuscito."])
        assert registro == [("controlli",)]


class TestChiusuraPerAggiornamento:
    def test_pronto_scrive_nella_barra_e_chiude_senza_finestre(self, main_frame):
        registro = _Registro()
        telaio = SimpleNamespace(
            _chiudi_avanzamento=registro.passo("chiudi avanzamento"),
            _quando_libera=registro.passo("quando libera"),
            set_status=registro.passo("stato"),
            Close=lambda: registro.append(("Close", telaio._chiusura_per_aggiornamento)),
            _chiusura_per_aggiornamento=False,
        )
        pronto = "Aggiornamento pronto, il programma si chiude per applicarlo."
        main_frame.MainFrame._fine_aggiornamento(telaio, True, [pronto])
        assert registro == [("chiudi avanzamento",), ("stato", pronto), ("Close", True)]

    def test_con_la_barra_di_stato_guasta_si_chiude_lo_stesso(self, main_frame, monkeypatch):
        """Lo script aspetta la chiusura una trentina di secondi: un guasto
        del pie' di pagina non la deve fermare, e finisce in error.log."""
        from gui import settings as modulo_settings

        registro, log = _Registro(), []
        monkeypatch.setattr(modulo_settings, "_registra", log.append)

        def guasta(testo):
            raise OSError("cartella dei backup illeggibile")

        telaio = SimpleNamespace(
            _chiudi_avanzamento=registro.passo("chiudi avanzamento"),
            _quando_libera=registro.passo("quando libera"),
            set_status=guasta,
            Close=lambda: registro.append(("Close", telaio._chiusura_per_aggiornamento)),
            _chiusura_per_aggiornamento=False,
        )
        main_frame.MainFrame._fine_aggiornamento(telaio, True, ["Aggiornamento pronto, il programma si chiude per applicarlo."])
        assert registro == [("chiudi avanzamento",), ("Close", True)]
        assert len(log) == 1 and "illeggibile" in log[0]

    def test_il_blocco_si_toglie_prima_di_chiudere_la_finestra(self, main_frame):
        registro = _Registro()

        class DialogoFinto:
            def Destroy(self):
                registro.append(("Destroy", telaio._disabilitatore))

        telaio = SimpleNamespace(_disabilitatore=object(), _dialogo_avanzamento=DialogoFinto())
        main_frame.MainFrame._chiudi_avanzamento(telaio)
        assert registro == [("Destroy", None)]
        assert telaio._dialogo_avanzamento is None
        # Senza finestra aperta non succede niente.
        main_frame.MainFrame._chiudi_avanzamento(telaio)
        assert len(registro) == 1


class TestFinestraLibera:
    def test_riconosce_un_dialogo_modale(self, main_frame, monkeypatch):
        import wx

        dlg = wx.Dialog(None)
        try:
            monkeypatch.setattr(wx, "GetTopLevelWindows", lambda: [dlg])
            telaio = SimpleNamespace(IsEnabled=lambda: True)
            assert main_frame.MainFrame._finestra_libera(telaio) is True
            dlg.IsModal = lambda: True
            assert main_frame.MainFrame._finestra_libera(telaio) is False
            # Una finestra di sistema non e' un wx.Dialog, ma disabilita la
            # finestra principale.
            dlg.IsModal = lambda: False
            telaio.IsEnabled = lambda: False
            assert main_frame.MainFrame._finestra_libera(telaio) is False
        finally:
            dlg.Destroy()

    def test_quando_libera_aspetta(self, main_frame, monkeypatch):
        import wx

        registro = _Registro()
        rinvii = []
        monkeypatch.setattr(wx, "CallLater", lambda *argomenti: rinvii.append(argomenti))
        libera = [False]

        class TelaioFinto:
            def IsBeingDeleted(self):
                return False

            def _finestra_libera(self):
                return libera[0]

            _quando_libera = main_frame.MainFrame._quando_libera

        telaio = TelaioFinto()
        funzione = registro.passo("funzione")
        telaio._quando_libera(funzione, "a", "b")
        assert registro == []
        assert rinvii == [(main_frame.RIPROVA_A_FINESTRA_LIBERA_MS, telaio._quando_libera, funzione, "a", "b")]
        libera[0] = True
        telaio._quando_libera(funzione, "a", "b")
        assert registro == [("funzione", "a", "b")]


class TestProposta:
    """Il ponte fra il thread del controllo e la finestra. Qui CallAfter e
    CallLater eseguono subito, nello stesso thread."""

    @pytest.fixture
    def ponte(self, main_frame, monkeypatch):
        import wx

        registro = _Registro()
        monkeypatch.setattr(wx, "CallAfter", lambda funzione, *a: funzione(*a))

        def rinvia(ms, funzione, *a):
            registro.append(("rinvio", ms))
            funzione(*a)

        monkeypatch.setattr(wx, "CallLater", rinvia)
        stato = SimpleNamespace(libera=[True], risposta=True, vivo=True)

        class TelaioFinto:
            def __bool__(self):
                return stato.vivo

            def IsBeingDeleted(self):
                return False

            def _finestra_libera(self):
                esito = stato.libera.pop(0) if len(stato.libera) > 1 else stato.libera[0]
                registro.append(("libera?", esito))
                return esito

            def _chiedi_aggiornamento(self, *argomenti):
                registro.append(("chiedi", *argomenti))
                return stato.risposta

            def _apri_avanzamento(self):
                registro.append(("avanzamento",))

        return SimpleNamespace(telaio=TelaioFinto(), registro=registro, stato=stato, mf=main_frame)

    def test_si_apre_l_avanzamento_e_poi_risponde(self, ponte):
        esito = ponte.mf.MainFrame._proponi_aggiornamento(ponte.telaio, "10.6.5", "10.7.0", "note")
        assert esito is True
        assert ponte.registro == [("libera?", True), ("chiedi", "10.6.5", "10.7.0", "note"), ("avanzamento",)]

    def test_non_adesso(self, ponte):
        ponte.stato.risposta = False
        assert ponte.mf.MainFrame._proponi_aggiornamento(ponte.telaio, "10.6.5", "10.7.0", None) is False
        assert ("avanzamento",) not in ponte.registro

    def test_con_un_dialogo_aperto_aspetta(self, ponte):
        ponte.stato.libera = [False, False, True]
        assert ponte.mf.MainFrame._proponi_aggiornamento(ponte.telaio, "10.6.5", "10.7.0", "") is True
        riprova = ponte.mf.RIPROVA_A_FINESTRA_LIBERA_MS
        assert ponte.registro[:5] == [("libera?", False), ("rinvio", riprova), ("libera?", False), ("rinvio", riprova), ("libera?", True)]
        assert ponte.registro[5][0] == "chiedi"

    def test_a_finestra_chiusa_risponde_di_no(self, ponte):
        ponte.stato.vivo = False
        assert ponte.mf.MainFrame._proponi_aggiornamento(ponte.telaio, "10.6.5", "10.7.0", "") is False
        assert ponte.registro == []


class TestGiroNelThread:
    """_run_update_check con gestisci_aggiornamento finta: gli argomenti, gli
    esiti raccolti e la fine sempre sul thread della finestra."""

    @pytest.fixture
    def giro(self, main_frame, monkeypatch):
        import GBUtils
        import wx

        from gui import settings as modulo_settings

        accodate, chiamate, log = [], [], []
        monkeypatch.setattr(wx, "CallAfter", lambda funzione, *a: accodate.append((funzione, *a)))
        monkeypatch.setattr(modulo_settings, "_registra", log.append)
        telaio = SimpleNamespace(
            _proponi_aggiornamento=lambda *a: True,
            _avanzamento_aggiornamento=lambda *a: None,
            _fine_aggiornamento=lambda *a: None,
        )

        def imposta(esito):
            def finta(*argomenti, **opzioni):
                chiamate.append((argomenti, opzioni))
                if isinstance(esito, Exception):
                    raise esito
                opzioni["avvisa"]("Aggiornamento non riuscito, si prosegue con questa versione.")
                return esito

            monkeypatch.setattr(GBUtils, "gestisci_aggiornamento", finta)

        return SimpleNamespace(telaio=telaio, accodate=accodate, chiamate=chiamate, log=log, imposta=imposta, mf=main_frame)

    def test_passa_proposta_avanzamento_e_traduzione(self, giro):
        import aggiornamenti
        from version import __version__

        giro.imposta(False)
        giro.mf.MainFrame._run_update_check(giro.telaio)
        (argomenti, opzioni), = giro.chiamate
        assert argomenti == ("tornello", __version__, aggiornamenti.API_RELEASE)
        assert set(opzioni) == {"proponi", "avvisa", "avanzamento", "traduci"}
        assert opzioni["proponi"] is giro.telaio._proponi_aggiornamento
        assert opzioni["avanzamento"] is giro.telaio._avanzamento_aggiornamento
        assert opzioni["traduci"] is giro.mf._
        assert giro.accodate == [
            (giro.telaio._fine_aggiornamento, False, ["Aggiornamento non riuscito, si prosegue con questa versione."])
        ]

    def test_un_guasto_va_nel_log_e_le_domande_arrivano(self, giro):
        giro.imposta(RuntimeError("rete a meta'"))
        giro.mf.MainFrame._run_update_check(giro.telaio)
        assert giro.accodate == [(giro.telaio._fine_aggiornamento, False, [])]
        assert len(giro.log) == 1 and "rete a meta'" in giro.log[0]

    def test_l_avanzamento_passa_alla_finestra(self, main_frame, monkeypatch):
        import wx

        accodate = []
        monkeypatch.setattr(wx, "CallAfter", lambda funzione, *a: accodate.append((funzione, *a)))
        telaio = SimpleNamespace(_mostra_avanzamento="mostra")
        main_frame.MainFrame._avanzamento_aggiornamento(telaio, 5, 10)
        assert accodate == [("mostra", 5, 10)]

        registro = _Registro()
        telaio = SimpleNamespace(_dialogo_avanzamento=SimpleNamespace(aggiorna=registro.passo("aggiorna")))
        main_frame.MainFrame._mostra_avanzamento(telaio, 5, 10)
        assert registro == [("aggiorna", 5, 10)]
        telaio._dialogo_avanzamento = None
        main_frame.MainFrame._mostra_avanzamento(telaio, 6, 10)
        assert len(registro) == 1

    def test_l_avanzamento_blocca_le_altre_finestre(self, main_frame, monkeypatch):
        import wx

        from gui.dialogs import update_dialog

        registro = _Registro()

        class AvanzamentoFinto:
            def __init__(self, parent, settings):
                registro.append(("crea", parent, settings))

            def Show(self):
                registro.append(("Show",))

        class DisabilitatoreFinto:
            def __init__(self, salvo):
                registro.append(("blocca", salvo))

        monkeypatch.setattr(update_dialog, "UpdateProgressDialog", AvanzamentoFinto)
        monkeypatch.setattr(wx, "WindowDisabler", DisabilitatoreFinto)
        telaio = SimpleNamespace(settings={"language": "it"}, _dialogo_avanzamento=None, _disabilitatore=None)
        main_frame.MainFrame._apri_avanzamento(telaio)
        dialogo = telaio._dialogo_avanzamento
        assert registro == [("crea", telaio, {"language": "it"}), ("Show",), ("blocca", dialogo)]
        assert isinstance(telaio._disabilitatore, DisabilitatoreFinto)

    def test_la_domanda_usa_la_finestra_con_le_note(self, main_frame, monkeypatch):
        import wx

        from gui.dialogs import update_dialog

        registro = _Registro()
        risposte = [wx.ID_YES, wx.ID_NO]

        class FinestraFinta:
            def __init__(self, *argomenti):
                registro.append(("crea", *argomenti))

            def ShowModal(self):
                return risposte.pop(0)

            def Destroy(self):
                registro.append(("Destroy",))

        monkeypatch.setattr(update_dialog, "UpdateDialog", FinestraFinta)
        telaio = SimpleNamespace(settings={})
        assert main_frame.MainFrame._chiedi_aggiornamento(telaio, "10.6.5", "10.7.0", "note") is True
        assert registro == [("crea", telaio, "10.6.5", "10.7.0", "note", {}), ("Destroy",)]
        assert main_frame.MainFrame._chiedi_aggiornamento(telaio, "10.6.5", "10.7.0", "note") is False
