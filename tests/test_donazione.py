"""L'invito a offrire un caffe'. Issue 40, poi issue 69.

Fino alla 10.3.4 la finestra deviava sys.stdout su uno StringIO, chiamava
Donazione e rileggeva cio' che aveva stampato, il tutto dentro un except
Exception: pass che nascondeva qualunque guasto. Qui si prova che il testo
arriva dal valore restituito, con stampa=False. Dalla 10.17.0 (issue 69)
l'invito non compare piu' alla chiusura della finestra: lo mostra, sempre,
la voce Offrimi un caffe' del menu Aiuto, con probabilita=100; fino alla
10.16.1 lo mostrava la chiusura, una volta su cinque. Niente finestre vere:
Donazione e DonationDialog sono sostituite da finte, e i metodi di MainFrame
girano su un telaio finto o sulla finestra principale mai mostrata. Dalla
10.13.32 le prove dei tasti e dei pulsanti della finestra usano DonationDialog
vera, mai mostrata.
"""

import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def registro(monkeypatch):
    """Sostituisce DonationDialog con una finta che annota cio' che riceve."""
    import gui.dialogs.donation_dialog as modulo_dialogo

    registro = {"dialoghi": [], "mostrati": 0, "distrutti": 0}

    class DialogoFinto:
        def __init__(self, parent, titolo, messaggio, settings=None):
            registro["dialoghi"].append(
                {"parent": parent, "titolo": titolo, "messaggio": messaggio, "settings": settings}
            )

        def ShowModal(self):
            registro["mostrati"] += 1

        def Destroy(self):
            registro["distrutti"] += 1

    monkeypatch.setattr(modulo_dialogo, "DonationDialog", DialogoFinto)
    return registro


def _donazione_finta(monkeypatch, esito):
    """Sostituisce Donazione in GBUtils con una finta che annota gli argomenti
    e se durante la chiamata sys.stdout e' ancora quello di partenza. Se esito
    e' un'eccezione la solleva, altrimenti lo restituisce."""
    import GBUtils

    chiamate = []
    stdout_di_partenza = sys.stdout

    def finta(**argomenti):
        chiamate.append(
            {"argomenti": argomenti, "stdout_intatto": sys.stdout is stdout_di_partenza}
        )
        if isinstance(esito, Exception):
            raise esito
        return esito

    monkeypatch.setattr(GBUtils, "Donazione", finta)
    return chiamate


@pytest.fixture
def principale(app_grafica, monkeypatch):
    """La finestra principale, mai mostrata, senza i controlli dell'avvio e
    senza suoni."""
    import gui.main_frame as mf
    import utils
    from gui.settings import DEFAULT_SETTINGS

    monkeypatch.setattr(utils, "play_sound", lambda *a, **k: True)
    for nome in ("_check_fide_db_on_startup", "_check_backup_on_startup", "_scan_and_load_initial_tournament", "_check_updates_async"):
        monkeypatch.setattr(mf.MainFrame, nome, lambda self: None)
    monkeypatch.setattr(mf.MainFrame, "Maximize", lambda self, *a: None)
    finestra = mf.MainFrame(None, "Tornello", dict(DEFAULT_SETTINGS))
    finestra._timer_pie_di_pagina.Stop()
    yield finestra
    finestra.Destroy()


def _voci_del_menu_aiuto(principale):
    """Le etichette delle voci del menu Aiuto, con None per i separatori."""
    menu = principale.item_credits.GetMenu()
    return [None if v.IsSeparator() else v.GetItemLabel() for v in menu.GetMenuItems()]


class TestVoceOffrimiUnCaffe:
    """Dalla 10.17.0 la voce Offrimi un caffe' del menu Aiuto chiede il testo
    a Donazione, con probabilita=100 perche' compaia sempre, e lo mostra nella
    finestra dell'invito (issue 69), che dalla 10.19.10 si intitola come la
    voce, Offrimi un caffe': fino alla 10.19.7 era Offri un caffe'."""

    def test_passa_cento_stampa_falso_e_la_lingua_delle_impostazioni(
        self, monkeypatch, registro, capsys
    ):
        from gui import main_frame as mf

        chiamate = _donazione_finta(monkeypatch, "Offrimi un caffe'.")
        telaio = SimpleNamespace(settings={"language": "en"})

        mf.MainFrame.on_offrimi_un_caffe(telaio, None)

        assert chiamate == [
            {"argomenti": {"lang": "en", "probabilita": 100, "stampa": False}, "stdout_intatto": True}
        ]
        assert len(registro["dialoghi"]) == 1
        assert registro["dialoghi"][0]["messaggio"] == "Offrimi un caffe'."
        assert registro["dialoghi"][0]["titolo"] == mf._("Offrimi un caffè")
        assert registro["dialoghi"][0]["parent"] is telaio
        assert registro["dialoghi"][0]["settings"] == {"language": "en"}
        assert registro["mostrati"] == 1
        assert registro["distrutti"] == 1
        assert capsys.readouterr().out == ""

    def test_senza_impostazioni_la_lingua_e_none(self, monkeypatch, registro):
        from gui import main_frame as mf

        chiamate = _donazione_finta(monkeypatch, "Un caffe'?")

        mf.MainFrame.on_offrimi_un_caffe(SimpleNamespace(settings=None), None)

        assert chiamate[0]["argomenti"] == {"lang": None, "probabilita": 100, "stampa": False}
        assert registro["mostrati"] == 1

    def test_la_donazione_vera_compare_sempre_e_non_stampa(self, registro, capsys):
        """Con la Donazione vera di GBUtils e gli argomenti della voce,
        l'invito compare a ogni scelta, senza sorteggio, e non scrive niente
        su stdout. Fino alla 10.16.1, con il sorteggio di serie, compariva
        una volta su cinque: venti volte di fila sarebbe un caso su quasi cento
        mila miliardi."""
        from gui import main_frame as mf

        telaio = SimpleNamespace(settings={"language": "it"})
        for _volta in range(20):
            mf.MainFrame.on_offrimi_un_caffe(telaio, None)

        assert capsys.readouterr().out == ""
        assert registro["mostrati"] == 20
        assert all(d["messaggio"].startswith("Se questo software") for d in registro["dialoghi"])

    def test_la_voce_sta_nel_menu_aiuto_con_la_sua_lettera(self, principale):
        """La voce viene dopo Crediti, con la O, che nel menu Aiuto non ha
        nessun'altra voce."""
        voci = _voci_del_menu_aiuto(principale)
        assert voci[:4] == ["&Guida Accessibile\tF1", "&Changelog\tF2", "C&rediti\tF3", "&Offrimi un caffè..."]
        assert principale.item_caffe.GetItemLabel() == "&Offrimi un caffè..."
        lettere = [v[v.index("&") + 1].lower() for v in voci if v is not None]
        assert lettere[:4] == ["g", "c", "r", "o"]
        assert len(set(lettere)) == len(lettere)

    def test_scelta_dal_menu_apre_l_invito(self, principale, monkeypatch, registro):
        import wx

        chiamate = _donazione_finta(monkeypatch, "Un caffe'?")
        evento = wx.CommandEvent(wx.wxEVT_MENU, principale.item_caffe.GetId())
        evento.SetEventObject(principale)

        assert principale.GetEventHandler().ProcessEvent(evento)

        assert chiamate[0]["argomenti"]["probabilita"] == 100
        assert len(registro["dialoghi"]) == 1
        assert registro["dialoghi"][0]["parent"] is principale
        assert registro["mostrati"] == 1

    def test_il_titolo_della_finestra_e_il_nome_della_voce(self, principale, monkeypatch, registro):
        """Dalla 10.19.10 il titolo e' la voce del menu senza la & della
        lettera di scelta rapida e senza i puntini: fino alla 10.19.7 la
        finestra si chiamava Offri un caffe', e la voce Offrimi un caffe'."""
        import wx

        _donazione_finta(monkeypatch, "Un caffe'?")
        evento = wx.CommandEvent(wx.wxEVT_MENU, principale.item_caffe.GetId())
        evento.SetEventObject(principale)

        assert principale.GetEventHandler().ProcessEvent(evento)

        voce = principale.item_caffe.GetItemLabel().replace("&", "").removesuffix("...")
        assert registro["dialoghi"][0]["titolo"] == voce == "Offrimi un caffè"


class TestChiusura:
    """on_close ferma il timer, fa le copie e suona, e la finestra si chiude.
    Dalla 10.17.0 non mostra piu' l'invito a offrire un caffe' (issue 69)."""

    def _telaio(self, monkeypatch):
        import utils

        passi = {"copie": [], "suoni": [], "skip": 0, "timer": []}
        monkeypatch.setattr(utils, "copie_di_chiusura", lambda nome: passi["copie"].append(nome))
        monkeypatch.setattr(
            utils, "play_sound", lambda nome, *resto, **opzioni: passi["suoni"].append(nome)
        )

        class TelaioFinto:
            def __init__(self):
                self.active_filename = "Tornello - Prova.json"
                self.current_tournament = None
                self.settings = {"language": "it"}
                # Dalla 10.5.0 on_close ferma per primo il timer del pie' di
                # pagina (issue 53).
                self._timer_pie_di_pagina = SimpleNamespace(
                    Stop=lambda: passi["timer"].append("stop")
                )

            def _si_puo_lasciare_il_torneo(self):
                # Dalla 10.19.21 la chiusura chiede prima se si puo'
                # lasciare il torneo aperto: qui non ce n'e' uno.
                return True

        class EventoFinto:
            def Skip(self):
                passi["skip"] += 1

            def CanVeto(self):
                return True

        return TelaioFinto(), EventoFinto(), passi

    def test_la_chiusura_non_mostra_l_invito(self, monkeypatch, registro):
        """Donazione non viene nemmeno chiamata, e nessuna finestra si apre:
        fino alla 10.16.1 l'invito compariva una chiusura su cinque."""
        from gui import main_frame as mf

        chiamate = _donazione_finta(monkeypatch, "Un caffe'?")
        telaio, evento, passi = self._telaio(monkeypatch)

        mf.MainFrame.on_close(telaio, evento)

        assert chiamate == []
        assert registro["dialoghi"] == []
        assert passi["timer"] == ["stop"]
        assert passi["copie"] == ["Tornello - Prova.json"]
        assert passi["suoni"] == ["chiusura"]
        assert passi["skip"] == 1

    def test_il_segnale_della_chiusura_per_aggiornamento_non_c_e_piu(self, principale):
        """Serviva soltanto a saltare l'invito nella chiusura che applica un
        aggiornamento (dalla 10.8.1, issue 37)."""
        assert not hasattr(principale, "_chiusura_per_aggiornamento")


class TestSuonoDellInvito:
    """La finestra Offrimi un caffe' suona all'apertura il preset donazione
    della collezione comune, lo stesso degli altri programmi del parco, con
    la firma di Tornello (issue 69)."""

    def test_la_finestra_suona_la_donazione(self, app_grafica, monkeypatch):
        import utils
        from gui.dialogs.donation_dialog import DonationDialog

        suonati = []
        monkeypatch.setattr(utils, "play_sound", lambda nome, *a, **k: suonati.append(nome))
        dlg = DonationDialog(None, "Offrimi un caffè", "Testo", {})
        try:
            assert suonati == ["donazione"]
        finally:
            dlg.DestroyChildren()
            dlg.Destroy()

    def test_il_preset_ha_la_firma_di_tornello(self):
        import json
        import os

        GBUtils = pytest.importorskip("GBUtils")
        percorso = os.path.join(os.path.dirname(os.path.abspath(GBUtils.__file__)), "Acu_Collection.json")
        with open(percorso, encoding="utf-8") as f:
            preset = json.load(f).get("donazione")
        assert preset is not None and preset.get("score")
        firme = preset["descrizione"].split("Usato da:")[-1]
        assert "tornello" in [nome.strip(" .") for nome in firme.split(",")]


class TestFinestraDellInvito:
    """Dalla 10.13.32 il pulsante predefinito della finestra Offrimi un caffe'
    e' Chiudi, e non piu' Dona con PayPal. INVIO nel testo preme Chiudi, come
    nelle finestre di messaggio, ed ESC chiude: fino alla 10.13.31, dal testo,
    nessuno dei due chiudeva la finestra. Il browser si apre soltanto con Dona
    con PayPal. La finestra vera, mai mostrata, con il suono e il browser
    sostituiti; EndModal e' annotato, perche' non e' modale."""

    @pytest.fixture
    def invito(self, app_grafica, monkeypatch):
        import webbrowser

        import utils
        from gui.dialogs.donation_dialog import DonationDialog

        aperti = []
        monkeypatch.setattr(utils, "play_sound", lambda *a, **k: None)
        monkeypatch.setattr(webbrowser, "open", aperti.append)
        dlg = DonationDialog(None, "Offrimi un caffè", "Prima riga\nSeconda riga", {})
        dlg.chiusure = []
        dlg.aperti = aperti
        dlg.EndModal = dlg.chiusure.append
        yield dlg
        dlg.DestroyChildren()
        dlg.Destroy()

    def _tasto(self, dlg, codice, fuoco, monkeypatch):
        import wx

        monkeypatch.setattr(wx.Window, "FindFocus", lambda: fuoco)
        evento = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
        evento.SetKeyCode(codice)
        evento.SetEventObject(fuoco)
        dlg.ProcessEvent(evento)

    def test_il_predefinito_e_chiudi(self, invito):
        import wx

        from gui.dialogs import donation_dialog

        assert invito.GetDefaultItem().GetId() == wx.ID_NO
        assert invito.GetDefaultItem().GetLabel() == donation_dialog._("Chiudi")
        assert invito.GetEscapeId() == wx.ID_NO

    def test_invio_nel_testo_ed_esc_chiudono_senza_browser(self, invito, monkeypatch):
        import wx

        for codice in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER, wx.WXK_ESCAPE):
            invito.chiusure.clear()
            self._tasto(invito, codice, invito.msg_text, monkeypatch)
            assert invito.chiusure == [wx.ID_NO], codice
        assert invito.aperti == []

    def test_invio_ripetuto_non_chiude(self, invito, monkeypatch):
        # Il tasto tenuto giu' manda INVIO ripetuti: non premono Chiudi, e
        # la finestra resta aperta. Il primo INVIO, non ripetuto, la chiude.
        import wx

        class TastoRipetuto(wx.KeyEvent):
            """wx non sa impostare la ripetizione su un evento costruito:
            la dice questa sottoclasse, che il gestore riceve com'e'."""

            def IsAutoRepeat(self):
                return True

        monkeypatch.setattr(wx.Window, "FindFocus", lambda: invito.msg_text)
        for codice in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            evento = TastoRipetuto(wx.wxEVT_CHAR_HOOK)
            evento.SetKeyCode(codice)
            evento.SetEventObject(invito.msg_text)
            invito.ProcessEvent(evento)
        assert invito.chiusure == []
        self._tasto(invito, wx.WXK_RETURN, invito.msg_text, monkeypatch)
        assert invito.chiusure == [wx.ID_NO]
        assert invito.aperti == []

    def test_dona_con_paypal_apre_il_browser_solo_se_premuto(self, invito):
        import wx

        pulsante = invito.FindWindowById(wx.ID_YES, invito)
        evento = wx.CommandEvent(wx.wxEVT_BUTTON, wx.ID_YES)
        evento.SetEventObject(pulsante)
        pulsante.GetEventHandler().ProcessEvent(evento)
        assert invito.aperti == ["https://paypal.me/GabrieleBattaglia780"]
        assert invito.chiusure == [wx.ID_YES]
