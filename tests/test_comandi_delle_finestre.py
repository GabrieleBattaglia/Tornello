"""Tasti e voci che devono fare quello che promettono.

Dalla 10.8.4 INVIO nella finestra del risultato conferma solo se il pulsante
di conferma e' acceso: con un PGN non valido suona l'errore e la finestra
resta aperta. Lo fermano il gancio della tastiera, che arriva prima di
Windows, e on_key_down, per quando il tasto gli arriva lo stesso; sui
pulsanti e nel campo del PGN il tasto resta loro. Dalla 10.8.5 le voci del menu Visualizza, che prima non avevano
un gestore, fanno quello che fanno F5, F6 e F7, con lo stesso suono. Dalla
10.8.6 la riga che carica altri risultati FIDE non ha piu' i trattini che
NVDA leggeva, e si riconosce dalla posizione invece che dal testo. Dalla
10.13.8 eliminare un torneo manda i suoi file nel cestino, finto nelle prove.
Dalla 10.13.10 alla 10.13.14 l'albero non cambia il torneo aperto quando si
ricostruisce, e Apri Torneo, la finalizzazione, l'eliminazione, il menu
Torneo e Ctrl+L dicono il vero sul torneo aperto.
Nessuna finestra viene mostrata, niente suona: i suoni si annotano, e le
chiusure delle finestre modali pure.
"""

import os
from types import SimpleNamespace

import pytest

PGN_NON_VALIDO = "questo non e' un pgn"
PGN_VALIDO = '[Event "Prova"]\n\n1. e4 e5 2. Nf3 Nc6 1/2-1/2'


def _chiudi(dlg):
    """Ferma i timer della ricerca e distrugge la finestra, come nelle prove
    delle finestre adattabili."""
    import wx

    for valore in vars(dlg).values():
        if isinstance(valore, wx.Timer):
            valore.Stop()
    dlg.DestroyChildren()
    dlg.Destroy()


def _eventi_in_coda():
    """Esegue le chiamate lasciate a wx.CallAfter, come fa il ciclo degli
    eventi quando l'azione e' finita."""
    import wx

    wx.GetApp().ProcessPendingEvents()
    wx.YieldIfNeeded()


@pytest.fixture
def suoni(app_grafica, monkeypatch):
    """I suoni suonati, per nome, al posto di Acusticator."""
    import utils
    from gui.dialogs import fide_query_dialog, player_enrollment_dialog

    suonati = []

    def annota(nome, *a, **k):
        suonati.append(nome)
        return True

    monkeypatch.setattr(utils, "play_sound", annota)
    monkeypatch.setattr(utils, "bip_di_scelta", lambda *a, **k: None)
    for modulo in (fide_query_dialog, player_enrollment_dialog):
        monkeypatch.setattr(modulo, "play_sound", annota)
    return suonati


@pytest.fixture
def telaio(app_grafica):
    import wx

    from gui.settings import DEFAULT_SETTINGS

    cornice = wx.Frame(None)
    cornice.settings = dict(DEFAULT_SETTINGS)
    yield cornice
    cornice.Destroy()


def _invio(oggetto):
    """Un INVIO finto, con l'oggetto che lo riceve e l'annotazione dello
    Skip, cioe' del tasto lasciato passare al controllo."""
    import wx

    passati = []
    evento = SimpleNamespace(
        GetKeyCode=lambda: wx.WXK_RETURN,
        GetEventObject=lambda: oggetto,
        Skip=lambda: passati.append(True),
    )
    return evento, passati


class TestInvioNellaFinestraDelRisultato:
    def _finestra(self, telaio, suoni, **opzioni):
        from gui.dialogs.result_dialog import ResultDialog

        dlg = ResultDialog(telaio, "Bianchi Luca", "Russo Marco", "GIO001", "GIO002", 3, opzioni.pop("risultato", None), {}, telaio.settings, **opzioni)
        chiusure = []
        dlg.EndModal = chiusure.append
        suoni.clear()
        return dlg, chiusure

    def _scrivi_pgn(self, dlg, testo):
        dlg.txt_pgn.ChangeValue(testo)
        dlg.on_pgn_changed(None)

    def test_con_il_pgn_non_valido_invio_suona_l_errore_e_resta(self, telaio, suoni):
        dlg, chiusure = self._finestra(telaio, suoni)
        try:
            _valore, pulsante = dlg.radio_buttons[0]
            pulsante.SetValue(True)
            self._scrivi_pgn(dlg, PGN_NON_VALIDO)
            assert not dlg.btn_ok.IsEnabled()
            evento, passati = _invio(pulsante)
            dlg.on_key_down(evento)
            assert chiusure == []
            assert passati == []
            assert suoni == ["errore"]
        finally:
            _chiudi(dlg)

    def test_con_il_pgn_corretto_invio_conferma(self, telaio, suoni):
        import wx

        dlg, chiusure = self._finestra(telaio, suoni)
        try:
            _valore, pulsante = dlg.radio_buttons[2]
            pulsante.SetValue(True)
            self._scrivi_pgn(dlg, PGN_NON_VALIDO)
            self._scrivi_pgn(dlg, PGN_VALIDO)
            assert dlg.btn_ok.IsEnabled()
            dlg.on_key_down(_invio(pulsante)[0])
            assert chiusure == [wx.ID_OK]
            assert "errore" not in suoni
            chiusure.clear()
            # Anche cancellando il PGN sbagliato la conferma torna.
            self._scrivi_pgn(dlg, PGN_NON_VALIDO)
            self._scrivi_pgn(dlg, "")
            dlg.on_key_down(_invio(pulsante)[0])
            assert chiusure == [wx.ID_OK]
        finally:
            _chiudi(dlg)

    def test_anche_salva_pgn_non_salva_un_pgn_non_valido(self, telaio, suoni):
        """A turno completo il risultato e' fermo e la conferma si chiama
        Salva PGN: con il PGN sbagliato INVIO non salva nemmeno li'."""
        dlg, chiusure = self._finestra(telaio, suoni, risultato="1-0", disable_result_change=True)
        try:
            self._scrivi_pgn(dlg, PGN_NON_VALIDO)
            dlg.on_key_down(_invio(dlg.btn_ok)[0])
            assert chiusure == []
            assert suoni == ["errore"]
        finally:
            _chiudi(dlg)

    def _gancio(self, dlg, fuoco):
        """INVIO passato al gancio della tastiera con il focus indicato.
        Restituisce True se il tasto prosegue verso il controllo."""
        import wx

        dlg.FindFocus = lambda: fuoco
        passati = []
        dlg.on_char_hook(SimpleNamespace(GetKeyCode=lambda: wx.WXK_RETURN, Skip=lambda: passati.append(True)))
        return passati == [True]

    def test_il_gancio_ferma_invio_sulle_voci_e_lo_lascia_ai_pulsanti(self, telaio, suoni):
        """Con il PGN non valido il gancio ferma INVIO sulle voci del
        risultato e in ogni punto che non sia un pulsante o il campo del PGN,
        con il suono dell'errore; ai pulsanti lo lascia, perche' lo premano, e
        al campo, perche' vada a capo."""
        import wx

        dlg, chiusure = self._finestra(telaio, suoni)
        try:
            _valore, pulsante = dlg.radio_buttons[1]
            pulsante.SetValue(True)
            self._scrivi_pgn(dlg, PGN_NON_VALIDO)
            assert not self._gancio(dlg, pulsante)
            assert not self._gancio(dlg, dlg.pannello)
            assert suoni == ["errore", "errore"]
            suoni.clear()
            for controllo in (dlg.txt_pgn, dlg.btn_schedule, dlg.btn_withdraw, dlg.FindWindowById(wx.ID_CANCEL)):
                assert self._gancio(dlg, controllo)
            assert suoni == []
            self._scrivi_pgn(dlg, PGN_VALIDO)
            assert self._gancio(dlg, pulsante)
            assert suoni == []
            assert chiusure == []
        finally:
            _chiudi(dlg)

    def test_senza_risultato_il_gancio_ferma_invio_sulle_voci(self, telaio, suoni):
        """Dalla 10.13.51 (issue 63) il gancio ferma INVIO anche senza un
        risultato scelto, con il PGN valido o vuoto: sulle voci e in ogni
        punto che non sia un pulsante o il campo del PGN suona l'errore. Ai
        pulsanti il tasto resta, e Conferma Risultato lo ferma da se'."""
        import wx

        dlg, chiusure = self._finestra(telaio, suoni)
        try:
            pulsante = dlg.radio_buttons[0][1]
            assert dlg.get_selected_result() is None and dlg.btn_ok.IsEnabled()
            assert not self._gancio(dlg, pulsante)
            assert not self._gancio(dlg, dlg.pannello)
            self._scrivi_pgn(dlg, PGN_VALIDO)
            assert not self._gancio(dlg, pulsante)
            assert suoni == ["errore"] * 3
            suoni.clear()
            for controllo in (dlg.txt_pgn, dlg.btn_ok, dlg.btn_schedule, dlg.btn_withdraw, dlg.FindWindowById(wx.ID_CANCEL)):
                assert self._gancio(dlg, controllo)
            assert suoni == []
            # Scelta una voce, il tasto passa e conferma.
            pulsante.SetValue(True)
            assert self._gancio(dlg, pulsante)
            assert suoni == [] and chiusure == []
        finally:
            _chiudi(dlg)

    @staticmethod
    def _premi_conferma(dlg):
        """Conferma Risultato premuto: l'evento del pulsante, con
        l'annotazione dello Skip, cioe' della conferma lasciata proseguire
        verso la chiusura di wx."""
        import wx

        evento = wx.CommandEvent(wx.wxEVT_BUTTON, wx.ID_OK)
        evento.SetEventObject(dlg.btn_ok)
        passati = []
        evento.Skip = lambda *a: passati.append(True)
        dlg.on_conferma(evento)
        return passati == [True]

    def test_conferma_risultato_senza_risultato_suona_l_errore(self, telaio, suoni):
        """Dalla 10.13.51 Conferma Risultato, premuto senza un risultato
        scelto, fa sentire l'errore e non prosegue: fino alla 10.13.50 la
        finestra si chiudeva con il suono della conferma, e la partita
        restava senza risultato."""
        dlg, _chiusure = self._finestra(telaio, suoni)
        try:
            assert not self._premi_conferma(dlg)
            assert suoni == ["errore"]
            suoni.clear()
            dlg.radio_buttons[3][1].SetValue(True)
            assert self._premi_conferma(dlg)
            assert suoni == []
        finally:
            _chiudi(dlg)

    def test_salva_pgn_con_il_risultato_di_prima_prosegue(self, telaio, suoni):
        """A turno completo le voci sono spente, ma il risultato c'e':
        Salva PGN prosegue."""
        dlg, _chiusure = self._finestra(telaio, suoni, risultato="F-1", disable_result_change=True)
        try:
            assert self._premi_conferma(dlg)
            assert suoni == []
        finally:
            _chiudi(dlg)

    def test_nel_campo_del_pgn_invio_resta_al_campo(self, telaio, suoni):
        """Nel campo INVIO va a capo, anche con il PGN non valido."""
        dlg, chiusure = self._finestra(telaio, suoni)
        try:
            self._scrivi_pgn(dlg, PGN_NON_VALIDO)
            evento, passati = _invio(dlg.txt_pgn)
            dlg.on_key_down(evento)
            assert passati == [True]
            assert chiusure == []
            assert suoni == []
        finally:
            _chiudi(dlg)


class TestInvioTenutoGiu:
    """Dalla 10.13.43 un INVIO tenuto giu' vale una volta sola: il filtro
    dell'applicazione scarta il gancio dei tasti degli INVIO che Windows segna
    come ripetuti, prima di ogni finestra, e Windows non consegna il tasto a
    nessuno. Quelli che NVDA rimanda dai campi di testo arrivano come nuovi,
    e passano: e' il limite accettato. Il filtro si
    chiama qui direttamente: l'applicazione delle prove non e' Tornello."""

    @staticmethod
    def _filtra(app_grafica, codice, ripetuto, tipo=None):
        import wx

        from gui.app import TornelloApp

        class Tasto(wx.KeyEvent):
            def IsAutoRepeat(self):
                return ripetuto

        evento = Tasto(tipo or wx.wxEVT_CHAR_HOOK)
        evento.SetKeyCode(codice)
        return TornelloApp.FilterEvent(app_grafica, evento)

    @pytest.mark.parametrize("tasto", ["WXK_RETURN", "WXK_NUMPAD_ENTER"])
    def test_l_invio_ripetuto_si_scarta(self, app_grafica, tasto):
        import wx

        assert self._filtra(app_grafica, getattr(wx, tasto), True) == wx.App.Event_Processed

    @pytest.mark.parametrize("tasto", ["WXK_RETURN", "WXK_NUMPAD_ENTER"])
    def test_il_primo_invio_passa(self, app_grafica, tasto):
        import wx

        assert self._filtra(app_grafica, getattr(wx, tasto), False) == wx.App.Event_Skip

    @pytest.mark.parametrize("tasto", ["WXK_DOWN", "WXK_SPACE", "WXK_ESCAPE", "WXK_DELETE"])
    def test_gli_altri_tasti_ripetuti_passano(self, app_grafica, tasto):
        import wx

        assert self._filtra(app_grafica, getattr(wx, tasto), True) == wx.App.Event_Skip

    def test_passano_gli_altri_eventi(self, app_grafica):
        import wx

        assert self._filtra(app_grafica, wx.WXK_RETURN, True, wx.wxEVT_KEY_DOWN) == wx.App.Event_Skip


class TestFrecceInTondo:
    """Dalla 10.13.40 le frecce sulle voci del risultato e sui giorni della
    programmazione girano in tondo e scelgono la voce su cui arrivano. Dalla
    10.6.4 i pulsanti stanno nel loro riquadro, e wxMSW trattava le frecce
    come il tabulatore: dalla prima voce la freccia su finiva sul pulsante di
    conferma. Le frecce arrivano al riquadro come evento di navigazione, e
    qui l'evento si manda al riquadro come lo manda wx; il fuoco e' annotato,
    perche' la finestra non si mostra."""

    @staticmethod
    def _risultato(telaio):
        from gui.dialogs.result_dialog import ResultDialog

        dlg = ResultDialog(telaio, "Alberti Anna", "Longo Luca", "A1", "L1", 1, None, {}, telaio.settings)
        return dlg, [rb for _v, rb in dlg.radio_buttons]

    @staticmethod
    def _programmazione(telaio):
        from gui.dialogs.result_dialog import ScheduleDialog

        dlg = ScheduleDialog(telaio, {}, telaio.settings, {})
        return dlg, [rb for _d, rb in dlg.radio_buttons]

    @staticmethod
    def _freccia(pulsanti, da, avanti, monkeypatch, dal_tab=False, dal_pulsante=False):
        """La freccia premuta con il fuoco sulla voce da; restituisce le voci
        che hanno ricevuto il fuoco. L'evento nasce dal riquadro, come quello
        delle frecce, o con dal_pulsante dal pulsante, come quello che wxMSW
        manda quando si spegne il controllo con il fuoco."""
        import wx

        fuochi = []
        monkeypatch.setattr(wx.Window, "FindFocus", lambda: pulsanti[da])
        monkeypatch.setattr(wx.RadioButton, "SetFocus", lambda self: fuochi.append(pulsanti.index(self)))
        evento = wx.NavigationKeyEvent()
        evento.SetDirection(avanti)
        evento.SetFromTab(dal_tab)
        riquadro = pulsanti[da].GetParent()
        evento.SetEventObject(pulsanti[da] if dal_pulsante else riquadro)
        riquadro.ProcessEvent(evento)
        return fuochi

    @pytest.mark.parametrize("finestra", ["_risultato", "_programmazione"])
    def test_dalla_prima_la_freccia_su_va_all_ultima(self, telaio, suoni, monkeypatch, finestra):
        dlg, pulsanti = getattr(self, finestra)(telaio)
        try:
            assert self._freccia(pulsanti, 0, False, monkeypatch) == [len(pulsanti) - 1]
            assert [p.GetValue() for p in pulsanti] == [False] * (len(pulsanti) - 1) + [True]
        finally:
            _chiudi(dlg)

    @pytest.mark.parametrize("finestra", ["_risultato", "_programmazione"])
    def test_dall_ultima_la_freccia_giu_va_alla_prima(self, telaio, suoni, monkeypatch, finestra):
        dlg, pulsanti = getattr(self, finestra)(telaio)
        try:
            assert self._freccia(pulsanti, len(pulsanti) - 1, True, monkeypatch) == [0]
            assert [p.GetValue() for p in pulsanti] == [True] + [False] * (len(pulsanti) - 1)
        finally:
            _chiudi(dlg)

    def test_in_mezzo_la_freccia_sceglie_la_voce_accanto(self, telaio, suoni, monkeypatch):
        dlg, pulsanti = self._risultato(telaio)
        try:
            assert self._freccia(pulsanti, 2, True, monkeypatch) == [3]
            assert pulsanti[3].GetValue()
            assert self._freccia(pulsanti, 3, False, monkeypatch) == [2]
            assert pulsanti[2].GetValue() and not pulsanti[3].GetValue()
        finally:
            _chiudi(dlg)

    def test_il_tabulatore_non_sceglie_niente(self, telaio, suoni, monkeypatch):
        dlg, pulsanti = self._risultato(telaio)
        try:
            assert self._freccia(pulsanti, 0, False, monkeypatch, dal_tab=True) == []
            assert not any(p.GetValue() for p in pulsanti)
        finally:
            _chiudi(dlg)

    def test_l_evento_nato_dal_pulsante_non_sceglie_niente(self, telaio, suoni, monkeypatch):
        """Spegnendo il pulsante con il fuoco, wxMSW manda un evento in
        avanti, non da TAB, che nasce dal pulsante: non e' una freccia."""
        dlg, pulsanti = self._risultato(telaio)
        try:
            assert self._freccia(pulsanti, 2, True, monkeypatch, dal_pulsante=True) == []
            assert not any(p.GetValue() for p in pulsanti)
        finally:
            _chiudi(dlg)


@pytest.fixture
def principale(app_grafica, suoni, monkeypatch):
    """La finestra principale, mai mostrata, senza i controlli dell'avvio.
    Chiede i suoni annotati prima di nascere: nascendo suona l'avvio."""
    import gui.main_frame as mf
    from gui.settings import DEFAULT_SETTINGS

    for nome in ("_check_fide_db_on_startup", "_check_backup_on_startup", "_scan_and_load_initial_tournament", "_check_updates_async"):
        monkeypatch.setattr(mf.MainFrame, nome, lambda self: None)
    monkeypatch.setattr(mf.MainFrame, "Maximize", lambda self, *a: None)
    finestra = mf.MainFrame(None, "Tornello", dict(DEFAULT_SETTINGS))
    finestra._timer_pie_di_pagina.Stop()
    yield finestra
    finestra.Destroy()


class TestMenuVisualizza:
    """Le tre voci del menu e i tre tasti passano dagli stessi gestori. Il
    fuoco vero non si puo' spostare in una finestra mai mostrata: SetFocus e
    HasFocus dei tre controlli sono sostituiti da finti che annotano."""

    VOCI = (
        ("item_view_central", "F5", "spostamento_f5", "main_text"),
        ("item_view_tree", "F6", "spostamento_f6", "tree_ctrl"),
        ("item_view_status", "F7", "spostamento_f7", "status_text"),
    )

    def _annota_il_fuoco(self, principale, registro, pie_col_focus=False):
        for nome in ("main_text", "tree_ctrl", "status_text"):
            controllo = getattr(principale, nome)
            controllo.SetFocus = lambda nome=nome: registro.append(f"fuoco {nome}")
        principale.status_text.HasFocus = lambda: pie_col_focus
        principale.update_status_display = lambda *a: registro.append("ricalcolo")

    def _dal_menu(self, principale, voce):
        import wx

        evento = wx.CommandEvent(wx.wxEVT_MENU, getattr(principale, voce).GetId())
        evento.SetEventObject(principale)
        return principale.GetEventHandler().ProcessEvent(evento)

    def _dal_tasto(self, principale, tasto):
        import wx

        codice = {"F5": wx.WXK_F5, "F6": wx.WXK_F6, "F7": wx.WXK_F7}[tasto]
        principale.on_key_hook(SimpleNamespace(GetKeyCode=lambda: codice, Skip=lambda: None))

    @pytest.mark.parametrize(("voce", "tasto", "suono", "controllo"), VOCI)
    def test_la_voce_fa_quello_che_fa_il_tasto(self, principale, suoni, voce, tasto, suono, controllo):
        dal_menu, dal_tasto = [], []
        self._annota_il_fuoco(principale, dal_menu)
        suoni.clear()
        assert self._dal_menu(principale, voce)
        dal_menu[:0] = suoni
        self._annota_il_fuoco(principale, dal_tasto)
        suoni.clear()
        self._dal_tasto(principale, tasto)
        dal_tasto[:0] = suoni
        assert dal_menu == [suono, f"fuoco {controllo}"]
        assert dal_tasto == dal_menu

    def test_dal_pie_di_pagina_la_barra_di_stato_ricalcola(self, principale, suoni):
        """Con il focus gia' sul pie' di pagina SetFocus non genera l'arrivo
        del focus, e la voce ricalcola da se', come F7."""
        registro = []
        self._annota_il_fuoco(principale, registro, pie_col_focus=True)
        suoni.clear()
        assert self._dal_menu(principale, "item_view_status")
        assert suoni == ["spostamento_f7"]
        assert registro == ["ricalcolo", "fuoco status_text"]

    def test_le_voci_hanno_il_tasto_nell_etichetta(self, principale):
        for voce, tasto, _suono, _controllo in self.VOCI:
            assert getattr(principale, voce).GetItemLabel().endswith("\t" + tasto)

    def test_ogni_voce_ha_la_sua_lettera(self, principale):
        """Fino alla 10.13.4 Albero di Destra e Barra di Stato avevano tutte
        e due la B sottolineata, e la lettera non sceglieva nessuna delle
        due. Dalla 10.13.5 Barra di Stato ha la S."""
        etichette = [v.GetItemLabel() for v in principale.item_view_central.GetMenu().GetMenuItems()]
        lettere = [e[e.index("&") + 1].lower() for e in etichette]
        assert lettere == ["a", "b", "s"]
        assert etichette[2] == "Barra di &Stato\tF7"


class TestFileDiTorneoNonLeggibili:
    """La barra di stato dice quanti file di torneo non si leggono. Fino
    alla 10.13.5 anche un file solo era al plurale. Dalla 10.13.11 l'avviso
    arriva ad azione finita, con wx.CallAfter."""

    @pytest.mark.parametrize(
        ("quanti", "attesa"),
        [
            (1, "Attenzione: un file di torneo non leggibile, dettagli sotto."),
            (2, "Attenzione: 2 file di torneo non leggibili, dettagli sotto."),
        ],
    )
    def test_il_conteggio(self, principale, quanti, attesa):
        from config import user_data_path

        for numero in range(quanti):
            with open(user_data_path(f"Tornello - Rovinato{numero}.json"), "w", encoding="utf-8") as f:
                f.write("{rovinato")

        principale.populate_tree()
        _eventi_in_coda()

        assert principale.last_status_msg == attesa


def _risultati_fide(quanti):
    return [
        {
            "id_fide": 900000 + i,
            "last_name": f"Rossi{i:03d}",
            "first_name": "Mario",
            "elo_standard": 1500 + i,
            "elo_rapid": 1400,
            "birth_year": 1980,
            "federation": "ITA",
        }
        for i in range(quanti)
    ]


class TestRigaMostraAltri:
    ATTESA = "Mostra altri risultati (50 rimanenti su 150)"

    def test_consulta_fide(self, telaio, suoni, monkeypatch):
        from gui.dialogs import fide_query_dialog

        monkeypatch.setattr(fide_query_dialog, "search_players", lambda query, **k: _risultati_fide(150))
        dlg = fide_query_dialog.FideQueryDialog(telaio, {}, telaio.settings)
        try:
            dlg.search_input.ChangeValue("rossi")
            dlg._on_debounced_search(None)
            lista = dlg.list_results
            assert lista.GetCount() == 101
            assert lista.GetString(100) == self.ATTESA
            lista.SetSelection(100)
            dlg.on_item_selected(None)
            assert dlg.detail_text.GetValue() == ""
            dlg.on_import_player(None)
            assert lista.GetCount() == 150
            assert lista.GetSelection() == 100
            assert lista.GetString(100).startswith("Rossi100 ")
            assert len(dlg.results_map) == 150
        finally:
            _chiudi(dlg)

    def test_iscrizione(self, telaio, suoni, monkeypatch):
        from gui.dialogs import player_enrollment_dialog

        monkeypatch.setattr(player_enrollment_dialog, "search_players", lambda query, **k: _risultati_fide(150))
        dlg = player_enrollment_dialog.PlayerEnrollmentDialog(telaio, {}, [], telaio.settings)
        try:
            dlg.search_fide.ChangeValue("rossi")
            dlg.esegui_ricerca_fide()
            lista = dlg.list_fide_results
            assert lista.GetCount() == 101
            assert lista.GetString(100) == self.ATTESA
            lista.SetSelection(100)
            dlg.on_add_fide(None)
            assert lista.GetCount() == 150
            assert lista.GetSelection() == 100
            assert dlg.enrolled_players == []
            assert len(dlg.fide_results_map) == 150
        finally:
            _chiudi(dlg)

    def test_un_solo_risultato_che_resta_e_al_singolare(self, telaio, suoni, monkeypatch):
        """Con 101 risultati ne resta uno solo: fino alla 10.13.5 la riga
        diceva 1 rimanenti."""
        from gui.dialogs import fide_query_dialog, player_enrollment_dialog

        for modulo in (fide_query_dialog, player_enrollment_dialog):
            monkeypatch.setattr(modulo, "search_players", lambda query, **k: _risultati_fide(101))
        attesa = "Mostra altri risultati (1 rimanente su 101)"
        dlg = fide_query_dialog.FideQueryDialog(telaio, {}, telaio.settings)
        try:
            dlg.search_input.ChangeValue("rossi")
            dlg._on_debounced_search(None)
            assert dlg.list_results.GetString(100) == attesa
        finally:
            _chiudi(dlg)
        dlg = player_enrollment_dialog.PlayerEnrollmentDialog(telaio, {}, [], telaio.settings)
        try:
            dlg.search_fide.ChangeValue("rossi")
            dlg.esegui_ricerca_fide()
            assert dlg.list_fide_results.GetString(100) == attesa
        finally:
            _chiudi(dlg)

    def test_nessuna_riga_con_i_trattini_quando_i_risultati_bastano(self, telaio, suoni, monkeypatch):
        from gui.dialogs import fide_query_dialog

        monkeypatch.setattr(fide_query_dialog, "search_players", lambda query, **k: _risultati_fide(100))
        dlg = fide_query_dialog.FideQueryDialog(telaio, {}, telaio.settings)
        try:
            dlg.search_input.ChangeValue("rossi")
            dlg._on_debounced_search(None)
            voci = dlg.list_results.GetStrings()
            assert len(voci) == 100
            assert not any(voce.startswith(("-", "Mostra")) for voce in voci)
        finally:
            _chiudi(dlg)


class TestEliminazioneDelTorneo:
    """Dalla 10.13.8 eliminare un torneo manda i suoi file nel cestino di
    Windows, con la finestra principale come proprietaria della domanda che
    Windows puo' fare, e non li cancella piu' per sempre con os.remove
    (decisione di Gabriele, avvertenza della issue 55). Il cestino e' finto;
    quello non disponibile e' la funzione vera del programma con
    cestino_disponibile che risponde di no, e lascia tutto dov'e'. I file di
    Autunneo2 restano: dalla 10.3.4 i file si riconoscono dal nome intero.
    La conferma elenca i file, cartella per cartella. Un altro json con il
    nome del torneo resta, tranne la copia dello stesso torneo concluso nella
    cartella di lavoro esterna; per un torneo in archivio la cartella di
    salvataggio conta solo se e' esterna, e una cartella che manca non si
    crea. Una cartella che non si legge, o un errore a meta', li dice il
    messaggio finale, con il suono dell'errore.
    Le finestre di messaggio sono finte, e annotano titolo e testo."""

    DEL_TORNEO = ("Tornello - Autunneo.json", "Tornello - Autunneo - Classifica.txt", "Tornello - Autunneo_sospeso.txt")
    DEGLI_ALTRI = ("Tornello - Autunneo2.json", "Tornello - Autunneo2 - Classifica.txt")
    NELLA_CARTELLA_ESTERNA = ("Tornello - Autunneo - Classifica.txt", "Tornello - Autunneo2 - Classifica.txt")

    @staticmethod
    def _json(percorso, **dati):
        """Un file di torneo, in preparazione se dati non dice altro."""
        import json

        os.makedirs(os.path.dirname(percorso), exist_ok=True)
        torneo = {"start_date": "2026-09-01", "end_date": "2026-10-15", "rounds": [], "players": []}
        torneo.update(dati)
        with open(percorso, "w", encoding="utf-8") as f:
            json.dump(torneo, f)

    @staticmethod
    def _report(percorso):
        os.makedirs(os.path.dirname(percorso), exist_ok=True)
        with open(percorso, "w", encoding="utf-8") as f:
            f.write("report")

    @staticmethod
    def _nodo(principale, percorso):
        """L'albero ricostruito e il nodo del torneo di quel file."""
        principale.populate_tree()
        nodo = principale._find_matching_item(principale.tree_root, {"action": "select_tournament", "filepath": percorso})
        assert nodo and nodo.IsOk()
        return nodo

    @staticmethod
    def _dialoghi_finti(monkeypatch):
        """Le finestre di messaggio annotate, con il Si' a ogni conferma."""
        import wx

        import gui.main_frame as mf

        finestre = []

        class DialogoFinto:
            def __init__(self, genitore, titolo, messaggio, style=wx.OK, **altro):
                finestre.append((titolo, messaggio))
                self.style = style

            def ShowModal(self):
                return wx.ID_YES if self.style & wx.YES_NO else wx.ID_OK

            def Destroy(self):
                pass

        monkeypatch.setattr(mf, "AccessibleMsgDialog", DialogoFinto)
        return finestre

    def _prepara(self, principale, monkeypatch, tmp_path):
        """I file dei due tornei nella cartella del programma e nella
        cartella di salvataggio di Autunneo, l'albero ricostruito e il nodo
        di Autunneo. Restituisce il nodo, il file del torneo, la cartella
        esterna e le finestre di messaggio annotate."""
        from config import user_data_path

        esterna = tmp_path / "esterna"
        esterna.mkdir()
        for nome in self.DEL_TORNEO + self.DEGLI_ALTRI:
            if nome.endswith(".json"):
                torneo = nome.removeprefix("Tornello - ").removesuffix(".json")
                cartella = {"custom_save_path": str(esterna)} if torneo == "Autunneo" else {}
                self._json(user_data_path(nome), name=torneo, **cartella)
            else:
                self._report(user_data_path(nome))
        for nome in self.NELLA_CARTELLA_ESTERNA:
            self._report(str(esterna / nome))
        file_torneo = user_data_path("Tornello - Autunneo.json")
        nodo = self._nodo(principale, file_torneo)
        return nodo, file_torneo, esterna, self._dialoghi_finti(monkeypatch)

    def _cestino_finto(self, monkeypatch, cartella, rifiuta=()):
        """Al posto di delete_file_to_trash: sposta i file in una cartella
        della prova e annota la finestra che li manda; i percorsi di rifiuta
        restano dove sono, come su un disco senza cestino."""
        import shutil

        import utils

        ricevuti, finestre = [], []

        def cestino(percorso, finestra=None):
            finestre.append(finestra)
            if percorso in rifiuta:
                return False
            cartella.mkdir(exist_ok=True)
            shutil.move(percorso, str(cartella / f"{len(ricevuti)}_{os.path.basename(percorso)}"))
            ricevuti.append(percorso)
            return True

        monkeypatch.setattr(utils, "delete_file_to_trash", cestino)
        return ricevuti, finestre

    def test_i_file_del_torneo_vanno_nel_cestino_e_gli_altri_restano(self, principale, suoni, monkeypatch, tmp_path):
        from config import user_data_path

        nodo, file_torneo, esterna, finestre = self._prepara(principale, monkeypatch, tmp_path)
        ricevuti, proprietarie = self._cestino_finto(monkeypatch, tmp_path / "cestino")
        suoni.clear()

        principale.delete_tournament_completely(nodo, file_torneo)

        attesi = [user_data_path(n) for n in self.DEL_TORNEO] + [str(esterna / "Tornello - Autunneo - Classifica.txt")]
        assert sorted(ricevuti) == sorted(attesi)
        assert ricevuti[0] == file_torneo
        assert proprietarie == [principale.GetHandle()] * len(attesi)
        assert not any(os.path.exists(p) for p in attesi)
        for nome in self.DEGLI_ALTRI:
            assert os.path.exists(user_data_path(nome)), nome
        assert (esterna / "Tornello - Autunneo2 - Classifica.txt").exists()
        assert principale._find_matching_item(principale.tree_root, {"action": "select_tournament", "filepath": file_torneo}) is None
        # La conferma dice il cestino ed elenca i file, un nome per riga
        # sotto la sua cartella; il messaggio finale conta i file correlati,
        # e nessuna finestra per i file rimasti fuori.
        assert len(finestre) == 1
        assert finestre[0][1].split("\n") == [
            "Vuoi mandare nel cestino di Windows il torneo in preparazione 'Autunneo'?",
            "Ci vanno 4 file, quello del torneo e quelli che portano il suo nome intero, e dal cestino si possono recuperare:",
            f"Nella cartella {os.path.dirname(file_torneo)}:",
            "Tornello - Autunneo.json",
            "Tornello - Autunneo - Classifica.txt",
            "Tornello - Autunneo_sospeso.txt",
            f"Nella cartella {esterna}:",
            "Tornello - Autunneo - Classifica.txt",
        ]
        assert principale.last_status_msg == "Torneo 'Autunneo' mandato nel cestino di Windows, con 3 file correlati."
        assert suoni == ["cancellato"]

    def test_con_il_cestino_non_disponibile_nessun_file_sparisce(self, principale, suoni, monkeypatch, tmp_path):
        """La funzione vera, su un disco senza cestino: il file del torneo non
        ci va, non si cancella per sempre, e nient'altro viene toccato."""
        import utils
        from config import user_data_path

        nodo, file_torneo, esterna, finestre = self._prepara(principale, monkeypatch, tmp_path)
        monkeypatch.setattr(utils, "cestino_disponibile", lambda percorso: False)
        suoni.clear()

        principale.delete_tournament_completely(nodo, file_torneo)

        for nome in self.DEL_TORNEO + self.DEGLI_ALTRI:
            assert os.path.exists(user_data_path(nome)), nome
        for nome in self.NELLA_CARTELLA_ESTERNA:
            assert (esterna / nome).exists(), nome
        assert principale._find_matching_item(principale.tree_root, {"action": "select_tournament", "filepath": file_torneo}) is not None
        titolo, testo = finestre[-1]
        assert titolo == "Eliminazione non riuscita"
        assert testo.startswith(f"Il file del torneo {file_torneo} non è andato nel cestino, e il torneo 'Autunneo' resta com'è")
        # Fra le cause anche il No alla domanda di Windows.
        assert "se hai risposto No alla domanda di Windows" in testo
        assert principale.last_status_msg == testo
        assert suoni == ["errore"]

    @pytest.mark.parametrize("quanti", [1, 2])
    def test_i_file_rimasti_fuori_dal_cestino_si_nominano(self, principale, suoni, monkeypatch, tmp_path, quanti):
        """Il torneo va nel cestino, ma un report, o due, no: restano dove
        sono, e il messaggio finale li nomina, uno per riga nella finestra,
        con il suono dell'errore invece di quello del successo pieno."""
        from config import user_data_path

        nodo, file_torneo, esterna, finestre = self._prepara(principale, monkeypatch, tmp_path)
        fuori = [str(esterna / "Tornello - Autunneo - Classifica.txt"), user_data_path("Tornello - Autunneo_sospeso.txt")][:quanti]
        ricevuti, _proprietarie = self._cestino_finto(monkeypatch, tmp_path / "cestino", rifiuta=fuori)
        suoni.clear()

        principale.delete_tournament_completely(nodo, file_torneo)

        assert file_torneo in ricevuti
        assert all(os.path.exists(p) for p in fuori)
        titolo, testo = finestre[-1]
        assert titolo == "File rimasti fuori dal cestino"
        righe = testo.split("\n")
        if quanti == 1:
            assert righe[:2] == [
                "Torneo 'Autunneo' mandato nel cestino di Windows, con 2 file correlati.",
                "Un file correlato non è andato nel cestino, e resta dov'è:",
            ]
        else:
            assert righe[:2] == [
                "Torneo 'Autunneo' mandato nel cestino di Windows, con un file correlato.",
                "2 file correlati non sono andati nel cestino, e restano dove sono:",
            ]
        assert sorted(righe[2:]) == sorted(fuori)
        assert all(p in principale.last_status_msg for p in fuori)
        assert suoni == ["errore"]

    @pytest.mark.parametrize("cartella", ["programma", "assente"])
    def test_un_torneo_in_archivio_non_porta_via_l_edizione_in_corso(self, principale, suoni, monkeypatch, tmp_path, cartella):
        """L'edizione 2025 di Sociale, conclusa e in archivio, con la cartella
        di salvataggio del programma, che la procedura guidata propone, o con
        una cartella che non c'e' piu', come una chiavetta non inserita: fino
        alla 10.13.7 nel secondo caso si ripiegava sulla cartella del
        programma. Nel cestino vanno il json archiviato e il suo report;
        l'edizione 2026 in corso accanto al programma resta, con il suo
        report, e la cartella che manca non nasce."""
        from config import ARCHIVED_TOURNAMENTS_DIR, user_data_path

        assente = tmp_path / "chiavetta" / "Sociale"
        salvataggio = user_data_path("") if cartella == "programma" else str(assente)
        in_archivio = os.path.join(ARCHIVED_TOURNAMENTS_DIR, "2025", "10 Ottobre", "Sociale")
        archiviato = os.path.join(in_archivio, "Tornello - Sociale.json")
        self._json(archiviato, name="Sociale", start_date="2025-09-01", end_date="2025-10-15", concluded=True, custom_save_path=salvataggio)
        self._report(os.path.join(in_archivio, "Tornello - Sociale - Classifica.txt"))
        in_corso = user_data_path("Tornello - Sociale.json")
        self._json(in_corso, name="Sociale", custom_save_path=user_data_path(""))
        report_in_corso = user_data_path("Tornello - Sociale - Classifica.txt")
        self._report(report_in_corso)
        nodo = self._nodo(principale, archiviato)
        finestre = self._dialoghi_finti(monkeypatch)
        ricevuti, _proprietarie = self._cestino_finto(monkeypatch, tmp_path / "cestino")
        suoni.clear()

        principale.delete_tournament_completely(nodo, archiviato)

        assert ricevuti == [archiviato, os.path.join(in_archivio, "Tornello - Sociale - Classifica.txt")]
        assert os.path.exists(in_corso)
        assert os.path.exists(report_in_corso)
        assert not (tmp_path / "chiavetta").exists()
        assert finestre[0][1].split("\n")[0] == "Vuoi mandare nel cestino di Windows il torneo concluso 'Sociale'?"
        assert suoni == ["cancellato"]

    @pytest.mark.parametrize(("nome", "file_del_programma"), [("Players db", "Tornello - Players_db.json"), ("Settings", "Tornello - Settings.json")])
    def test_i_file_del_programma_restano(self, principale, suoni, monkeypatch, tmp_path, nome, file_del_programma):
        """Un torneo concluso di nome Players db o Settings, con la cartella di
        salvataggio del programma: il database dei giocatori e le impostazioni
        portano il suo nome intero, e fino alla 10.13.7 andavano con lui."""
        from config import ARCHIVED_TOURNAMENTS_DIR, user_data_path

        in_archivio = os.path.join(ARCHIVED_TOURNAMENTS_DIR, "2025", "10 Ottobre", "X")
        archiviato = os.path.join(in_archivio, file_del_programma)
        self._json(archiviato, name=nome, concluded=True, custom_save_path=user_data_path(""))
        del_programma = user_data_path(file_del_programma)
        with open(del_programma, "w", encoding="utf-8") as f:
            f.write('{"players": []}')
        nodo = self._nodo(principale, archiviato)
        self._dialoghi_finti(monkeypatch)
        ricevuti, _proprietarie = self._cestino_finto(monkeypatch, tmp_path / "cestino")

        principale.delete_tournament_completely(nodo, archiviato)

        assert ricevuti == [archiviato]
        assert os.path.exists(del_programma)

    @pytest.mark.parametrize(("inizio", "va_nel_cestino"), [("2026-09-01", True), ("2027-09-01", False)])
    def test_la_copia_conclusa_nella_cartella_esterna(self, principale, suoni, monkeypatch, tmp_path, inizio, va_nel_cestino):
        """Un torneo in archivio con una cartella di lavoro esterna: la
        finalizzazione vi ha lasciato i report e la copia del torneo
        concluso, che vanno nel cestino con lui. Un json con lo stesso nome
        ma un'altra data di inizio e' un'altra edizione, e resta; la copia
        che Esplora risorse chiama "- Copia" resta sempre."""
        from config import ARCHIVED_TOURNAMENTS_DIR

        esterna = tmp_path / "esterna" / "Autunneo"
        in_archivio = os.path.join(ARCHIVED_TOURNAMENTS_DIR, "2026", "10 Ottobre", "Autunneo")
        archiviato = os.path.join(in_archivio, "Tornello - Autunneo.json")
        self._json(archiviato, name="Autunneo", concluded=True, custom_save_path=str(esterna))
        nell_esterna = str(esterna / "Tornello - Autunneo.json")
        self._json(nell_esterna, name="Autunneo", start_date=inizio, concluded=True, custom_save_path=str(esterna))
        copia = str(esterna / "Tornello - Autunneo - Copia.json")
        self._json(copia, name="Autunneo", concluded=True, custom_save_path=str(esterna))
        report = str(esterna / "Tornello - Autunneo - Classifica.txt")
        self._report(report)
        nodo = self._nodo(principale, archiviato)
        self._dialoghi_finti(monkeypatch)
        ricevuti, _proprietarie = self._cestino_finto(monkeypatch, tmp_path / "cestino")

        principale.delete_tournament_completely(nodo, archiviato)

        attesi = [archiviato, report, nell_esterna] if va_nel_cestino else [archiviato, report]
        assert ricevuti == attesi
        assert os.path.exists(nell_esterna) is not va_nel_cestino
        assert os.path.exists(copia)

    def test_gli_altri_json_con_il_nome_del_torneo_restano(self, principale, suoni, monkeypatch, tmp_path):
        """Un file aperto con un nome diverso da quello del torneo, Autunneo
        in Tornello - Autunneo_copia.json: il torneo vero con quel nome resta,
        e resta anche la copia che Esplora risorse chiama "- Copia"."""
        from config import user_data_path

        vero = user_data_path("Tornello - Autunneo.json")
        self._json(vero, name="Autunneo")
        di_esplora_risorse = user_data_path("Tornello - Autunneo - Copia.json")
        self._json(di_esplora_risorse, name="Autunneo")
        aperto = user_data_path("Tornello - Autunneo_copia.json")
        self._json(aperto, name="Autunneo")
        nodo = self._nodo(principale, aperto)
        self._dialoghi_finti(monkeypatch)
        ricevuti, _proprietarie = self._cestino_finto(monkeypatch, tmp_path / "cestino")

        principale.delete_tournament_completely(nodo, aperto)

        assert ricevuti == [aperto]
        assert os.path.exists(vero)
        assert os.path.exists(di_esplora_risorse)

    def test_una_cartella_scritta_con_altre_maiuscole_si_legge_una_volta(self, principale, suoni, monkeypatch, tmp_path):
        """La cartella di salvataggio e' quella del programma scritta in
        minuscolo: si legge una volta sola, e un report che il cestino
        rifiuta si prova una volta e si nomina una volta."""
        from config import user_data_path

        file_torneo = user_data_path("Tornello - Autunneo.json")
        self._json(file_torneo, name="Autunneo", custom_save_path=user_data_path("").lower())
        report = user_data_path("Tornello - Autunneo - Classifica.txt")
        self._report(report)
        nodo = self._nodo(principale, file_torneo)
        finestre = self._dialoghi_finti(monkeypatch)
        ricevuti, proprietarie = self._cestino_finto(monkeypatch, tmp_path / "cestino", rifiuta=(report,))

        principale.delete_tournament_completely(nodo, file_torneo)

        assert ricevuti == [file_torneo]
        assert len(proprietarie) == 2
        assert os.path.exists(report)
        assert finestre[-1][1].split("\n") == [
            "Torneo 'Autunneo' mandato nel cestino di Windows.",
            "Un file correlato non è andato nel cestino, e resta dov'è:",
            report,
        ]

    def test_una_cartella_che_non_si_legge_si_nomina(self, principale, suoni, monkeypatch, tmp_path):
        """La cartella di salvataggio non si legge, per esempio una cartella
        di rete sparita: il torneo va nel cestino con i file della cartella
        del programma, esce dall'albero e dalla memoria, e la conferma e il
        messaggio finale nominano la cartella, con il suono dell'errore."""
        nodo, file_torneo, esterna, finestre = self._prepara(principale, monkeypatch, tmp_path)
        principale.active_filename = file_torneo
        principale.current_tournament = {"name": "Autunneo"}
        vero = os.listdir

        def listdir(percorso="."):
            if os.path.normcase(os.path.abspath(percorso)) == os.path.normcase(str(esterna)):
                raise PermissionError(13, "Accesso negato", str(percorso))
            return vero(percorso)

        monkeypatch.setattr(os, "listdir", listdir)
        ricevuti, _proprietarie = self._cestino_finto(monkeypatch, tmp_path / "cestino")
        suoni.clear()

        principale.delete_tournament_completely(nodo, file_torneo)

        assert ricevuti[0] == file_torneo
        assert len(ricevuti) == 3
        for nome in self.NELLA_CARTELLA_ESTERNA:
            assert (esterna / nome).exists(), nome
        assert principale._find_matching_item(principale.tree_root, {"action": "select_tournament", "filepath": file_torneo}) is None
        assert principale.active_filename is None
        assert principale.current_tournament is None
        frase = "Una cartella non si è potuta leggere, e i file del torneo che contiene restano dove sono:"
        assert finestre[0][1].split("\n")[-2:] == [frase, str(esterna)]
        assert finestre[-1] == (
            "File rimasti fuori dal cestino",
            "\n".join(["Torneo 'Autunneo' mandato nel cestino di Windows, con 2 file correlati.", frase, str(esterna)]),
        )
        assert suoni == ["errore"]

    def test_un_errore_a_meta_dice_che_il_torneo_e_gia_nel_cestino(self, principale, suoni, monkeypatch, tmp_path):
        """Un errore dopo che il file del torneo e' andato nel cestino: il
        torneo e' gia' fuori dalla memoria, e non rinasce al primo
        salvataggio; il messaggio dice dov'e' il file, nella finestra
        accessibile e con il suono dell'errore."""
        nodo, file_torneo, _esterna, finestre = self._prepara(principale, monkeypatch, tmp_path)
        principale.active_filename = file_torneo
        principale.current_tournament = {"name": "Autunneo"}

        def guasto():
            raise RuntimeError("guasto finto")

        monkeypatch.setattr(principale, "show_intro_message", guasto)
        ricevuti, _proprietarie = self._cestino_finto(monkeypatch, tmp_path / "cestino")
        suoni.clear()

        principale.delete_tournament_completely(nodo, file_torneo)

        assert ricevuti == [file_torneo]
        assert principale.active_filename is None
        assert principale.current_tournament is None
        testo = f"Errore durante l'eliminazione del torneo: guasto finto Il file del torneo {file_torneo} è già nel cestino di Windows, e da lì si può recuperare."
        assert finestre[-1] == ("Eliminazione non riuscita", testo)
        assert principale.last_status_msg == testo
        assert suoni == ["errore"]


GIOCATORI_DEI_TORNEI = (
    ("BIA", "Bianchi", "Luca"),
    ("VER", "Verdi", "Anna"),
    ("NER", "Neri", "Paolo"),
    ("RUS", "Russo", "Marco"),
)


def _torneo_in_corso(nome, finito=False):
    """Un torneo al turno 1 con due partite. In corso ha tre turni e una
    partita da giocare; finito ha un turno solo con i due risultati, ed e'
    pronto per la finalizzazione."""
    giocatori = [
        {"id": codice, "last_name": cognome, "first_name": nome_proprio, "initial_elo": 1500, "current_elo": 1500, "points": 0.0, "results_history": []}
        for codice, cognome, nome_proprio in GIOCATORI_DEI_TORNEI
    ]
    partite = [
        {"id": 1, "white_player_id": "BIA", "black_player_id": "VER", "result": "1-0" if finito else None},
        {"id": 2, "white_player_id": "NER", "black_player_id": "RUS", "result": "1/2-1/2"},
    ]
    return {
        "name": nome,
        "start_date": "2026-09-01",
        "end_date": "2026-10-15",
        "total_rounds": 1 if finito else 3,
        "current_round": 1,
        "players": giocatori,
        "rounds": [{"round": 1, "matches": partite}],
    }


class TestAlberoETorneoAttivo:
    """L'albero e il torneo aperto, sulla finestra principale vera, mai
    mostrata. Ricostruendo l'albero con DeleteAllItems, il controllo di
    Windows sposta la selezione di voce in voce e manda un evento di
    selezione per ognuna: fino alla 10.13.9 ogni evento caricava il torneo di
    quella voce, e alla fine la selezione ripristinata riportava in memoria
    il torneo della voce di prima. Dalla 10.13.10 durante la ricostruzione
    non si carica niente, e il ripristino non apre un torneo diverso da
    quello aperto: Apri Torneo apre il torneo scelto, l'esito di un'azione
    resta nella barra di stato, e dopo una finalizzazione o un'eliminazione
    nessun torneo resta aperto di nascosto. Dalla 10.13.11 un file che non si
    legge si segnala una volta sola; dalla 10.13.12 il torneo aperto da
    un'altra cartella ha la sua voce nell'albero; dalla 10.13.13 il menu
    Torneo si accende appena il torneo si carica; dalla 10.13.14 Ctrl+L su un
    torneo concluso mostra la classifica finale. Il fuoco, i caricamenti e le
    voci attraversate dalla selezione si annotano.
    Anche il fuoco che arriva all'albero non apre un torneo da solo, il
    percorso scelto con Apri Torneo vale anche scritto con altre maiuscole,
    un file che non e' un torneo non si apre, un Apri Torneo non riuscito
    lascia aperto il torneo di prima, e la voce del torneo di un'altra
    cartella dice la cartella. Il fuoco sull'albero si simula mandando il
    solo messaggio WM_SETFOCUS al controllo, senza toccare il fuoco vero di
    Windows."""

    @staticmethod
    def _scrivi(percorso, torneo):
        import json

        os.makedirs(os.path.dirname(percorso), exist_ok=True)
        with open(percorso, "w", encoding="utf-8") as f:
            json.dump(torneo, f)

    def _prepara(self, *nomi, finiti=()):
        """I file dei tornei nella cartella del programma, per nome."""
        from config import user_data_path

        percorsi = {}
        for nome in nomi:
            percorsi[nome] = user_data_path(f"Tornello - {nome}.json")
            self._scrivi(percorsi[nome], _torneo_in_corso(nome, finito=nome in finiti))
        return percorsi

    @staticmethod
    def _sonde(principale):
        """Annota i tornei caricati, i file delle voci che la selezione
        attraversa e i controlli che chiedono il fuoco, che in una finestra
        mai mostrata non si sposta davvero."""
        import wx

        registro = SimpleNamespace(caricati=[], selezioni=[], fuoco=[])
        originale = principale.load_tournament

        def carica(percorso, rebuild_tree=True, **opzioni):
            registro.caricati.append(os.path.basename(percorso))
            return originale(percorso, rebuild_tree, **opzioni)

        def selezione(evento):
            voce = evento.GetItem()
            dati = (principale.tree_ctrl.GetItemData(voce) if voce.IsOk() else None) or {}
            registro.selezioni.append(dati.get("filepath"))
            evento.Skip()

        principale.load_tournament = carica
        principale.tree_ctrl.Bind(wx.EVT_TREE_SEL_CHANGED, selezione)
        for nome in ("main_text", "tree_ctrl", "status_text"):
            getattr(principale, nome).SetFocus = lambda nome=nome: registro.fuoco.append(nome)
        return registro

    @staticmethod
    def _voce(principale, **dati):
        voce = principale._find_matching_item(principale.tree_root, dati)
        assert voce and voce.IsOk(), dati
        return voce

    def _scegli_torneo(self, principale, percorso):
        """La voce del torneo scelta con le frecce."""
        principale.tree_ctrl.SelectItem(self._voce(principale, action="select_tournament", filepath=percorso))

    @staticmethod
    def _dati_della_selezione(principale):
        return principale.tree_ctrl.GetItemData(principale.tree_ctrl.GetSelection())

    @staticmethod
    def _dal_menu(principale, identificativo):
        import wx

        evento = wx.CommandEvent(wx.wxEVT_MENU, identificativo)
        evento.SetEventObject(principale)
        assert principale.GetEventHandler().ProcessEvent(evento)

    def _apri_con_ctrl_o(self, principale, monkeypatch, percorso):
        """Apri Torneo dal menu, con la finestra Apri finta che sceglie il
        file."""
        import wx

        class FinestraApri:
            def __init__(self, *argomenti, **opzioni):
                pass

            def ShowModal(self):
                return wx.ID_OK

            def GetPath(self):
                return percorso

            def Destroy(self):
                pass

        monkeypatch.setattr(wx, "FileDialog", FinestraApri)
        self._dal_menu(principale, wx.ID_OPEN)

    @staticmethod
    def _nessun_torneo_aperto(principale):
        assert principale.current_tournament is None
        assert principale.active_filename is None
        assert principale.GetTitle().endswith("[Nessun Torneo Caricato]")
        for voce in ("item_players", "item_round", "item_standings", "item_finalize"):
            assert not getattr(principale, voce).IsEnabled(), voce

    @staticmethod
    def _figlie(principale, genitore=None):
        """Le voci figlie, con etichetta e dati; senza genitore, quelle di
        primo livello."""
        albero = principale.tree_ctrl
        if genitore is None:
            genitore = principale.tree_root
        voci = []
        voce, cookie = albero.GetFirstChild(genitore)
        while voce.IsOk():
            voci.append((albero.GetItemText(voce), albero.GetItemData(voce)))
            voce, cookie = albero.GetNextChild(genitore, cookie)
        return voci

    def _voci_della_radice(self, principale):
        return self._figlie(principale)

    def _voci_dei_conclusi(self, principale):
        """Le etichette dei tornei nella categoria Tornei Conclusi."""
        categoria = self._voce(principale, action="category_closed")
        return [testo for testo, _dati in self._figlie(principale, categoria)]

    @staticmethod
    def _tutti_i_file(principale, genitore=None, trovati=None):
        """I file di tutte le voci dell'albero, in ogni ramo."""
        albero = principale.tree_ctrl
        if genitore is None:
            genitore = principale.tree_root
        trovati = [] if trovati is None else trovati
        voce, cookie = albero.GetFirstChild(genitore)
        while voce.IsOk():
            dati = albero.GetItemData(voce) or {}
            if dati.get("filepath"):
                trovati.append(os.path.normcase(dati["filepath"]))
            TestAlberoETorneoAttivo._tutti_i_file(principale, voce, trovati)
            voce, cookie = albero.GetNextChild(genitore, cookie)
        return trovati

    @staticmethod
    def _fuoco_all_albero(principale):
        """Il fuoco che arriva all'albero con F6, TAB o un clic: il solo
        messaggio WM_SETFOCUS, mandato al controllo della finestra mai
        mostrata, basta al controllo di Windows per scegliere da se' una voce
        quando non ne ha una."""
        import ctypes

        if os.name != "nt":
            pytest.skip("il messaggio WM_SETFOCUS e' di Windows")
        ctypes.windll.user32.SendMessageW(principale.tree_ctrl.GetHandle(), 0x0007, 0, 0)
        _eventi_in_coda()

    def test_ricostruire_l_albero_non_carica_nessun_torneo(self, principale, suoni):
        """Il cursore sul torneo aperto, un'azione che scrive il suo esito e
        ricostruisce l'albero: la selezione passa sulle voci degli altri
        tornei, ma nessuno si carica, il torneo aperto resta quello, con la
        sua voce scelta, e l'esito resta nella barra di stato."""
        percorsi = self._prepara("Alfa", "Beta", "Gamma", "Delta")
        registro = self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Beta"])
        assert registro.caricati == ["Tornello - Beta.json"]
        registro.caricati.clear()
        registro.selezioni.clear()
        esito = "Partita pianificata per il 1 ottobre 2026 alle 18:00."
        principale.set_status(esito)

        principale.populate_tree()

        assert set(registro.selezioni) - {percorsi["Beta"], None}
        assert registro.caricati == []
        assert principale.active_filename == percorsi["Beta"]
        assert principale.current_tournament["name"] == "Beta"
        assert principale.last_status_msg == esito
        assert self._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": percorsi["Beta"]}

    def test_apri_torneo_apre_il_torneo_scelto(self, principale, suoni, monkeypatch):
        """Con il cursore dell'albero su Beta, Ctrl+O su Alfa: si apre Alfa,
        una volta, e il cursore passa sulla sua voce. Fino alla 10.13.9
        restava aperto Beta, mentre la barra diceva caricato Alfa."""
        percorsi = self._prepara("Alfa", "Beta", "Gamma")
        registro = self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Beta"])
        registro.caricati.clear()

        self._apri_con_ctrl_o(principale, monkeypatch, percorsi["Alfa"])

        assert registro.caricati == ["Tornello - Alfa.json"]
        assert principale.active_filename == percorsi["Alfa"]
        assert principale.current_tournament["name"] == "Alfa"
        assert principale.GetTitle().endswith("[Alfa]")
        assert principale.last_status_msg == "Torneo 'Alfa' caricato con successo."
        assert self._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": percorsi["Alfa"]}
        assert principale.main_text.GetValue().startswith("Torneo: Alfa")

    def test_dopo_la_finalizzazione_nessun_torneo_resta_aperto(self, principale, suoni, monkeypatch):
        """Finalizzato Alfa, nessun torneo e' aperto, e il titolo e il menu
        lo dicono; il ripristino della copia di prima della finalizzazione
        riapre Alfa. Fino alla 10.13.9 restava aperto l'ultimo torneo
        dell'albero, e il ripristino non riapriva Alfa."""
        import ui
        from config import ARCHIVED_TOURNAMENTS_DIR

        percorsi = self._prepara("Alfa", "Beta", "Gamma", finiti=("Alfa",))
        registro = self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Alfa"])
        assert principale.item_finalize.IsEnabled()
        finestre = TestEliminazioneDelTorneo._dialoghi_finti(monkeypatch)
        messaggi = []
        monkeypatch.setattr("wx.MessageBox", lambda testo, *a, **k: messaggi.append(testo))
        archiviato = os.path.join(ARCHIVED_TOURNAMENTS_DIR, "2026", "10 Ottobre", "Alfa", "Tornello - Alfa.json")

        def finalizza(torneo, database, percorso, avvisi, raccolte_rimaste=None):
            torneo["concluded"] = True
            self._scrivi(archiviato, torneo)
            os.remove(percorso)
            return True

        monkeypatch.setattr(ui, "finalize_tournament", finalizza)
        registro.caricati.clear()

        self._dal_menu(principale, principale.item_finalize.GetId())

        # Dalla 10.13.43 il messaggio sta nella finestra accessibile.
        assert messaggi == []
        assert finestre[-1] == ("Successo", "Torneo finalizzato con successo! I dati dei giocatori sono stati aggiornati.")
        assert registro.caricati == []
        self._nessun_torneo_aperto(principale)
        assert principale.last_status_msg == "Torneo concluso e archiviato."
        assert self._dati_della_selezione(principale) == {"action": "start_new_tournament"}
        # L'area centrale torna alla schermata iniziale, come dicono dalla
        # 10.13.36 la sezione 9.3 del manuale e l'esempio del capitolo 9.
        assert principale.main_text.GetValue().startswith("Ciao! Benvenuto, sono Tornello")

        self._scrivi(percorsi["Alfa"], _torneo_in_corso("Alfa", finito=True))
        principale._save_state = lambda: registro.caricati.append("salvataggio")
        principale._dopo_il_ripristino(SimpleNamespace(riuscito=True, tipo="finalizzato", destinazione=percorsi["Alfa"]))

        assert registro.caricati == ["Tornello - Alfa.json", "salvataggio"]
        assert principale.active_filename == percorsi["Alfa"]
        assert principale.item_finalize.IsEnabled()

    def test_dopo_l_eliminazione_nessun_torneo_resta_aperto(self, principale, suoni, monkeypatch, tmp_path):
        """Eliminato Beta con il cursore sulla sua voce, la selezione passa a
        un altro torneo senza caricarlo: nessun torneo e' aperto, il titolo
        e il menu lo dicono, e l'albero ridisegnato non ha piu' Beta."""
        percorsi = self._prepara("Alfa", "Beta", "Gamma")
        registro = self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Beta"])
        TestEliminazioneDelTorneo._dialoghi_finti(monkeypatch)
        ricevuti, _proprietarie = TestEliminazioneDelTorneo()._cestino_finto(monkeypatch, tmp_path / "cestino")
        registro.caricati.clear()
        registro.selezioni.clear()

        principale.delete_tournament_completely(principale.tree_ctrl.GetSelection(), percorsi["Beta"])

        assert ricevuti == [percorsi["Beta"]]
        assert set(registro.selezioni) - {None}
        assert registro.caricati == []
        self._nessun_torneo_aperto(principale)
        assert principale.last_status_msg == "Torneo 'Beta' mandato nel cestino di Windows."
        assert [testo for testo, _dati in self._voci_della_radice(principale)] == ["Alfa", "Gamma", "Nuovo torneo"]

    def test_un_file_non_leggibile_si_segnala_una_volta(self, principale, suoni):
        """La riga nell'area centrale e l'avviso nella barra di stato
        arrivano quando il file si scopre, e non a ogni ricostruzione
        dell'albero, dove cancellavano l'esito dell'azione. Un altro file
        rovinato si segnala a sua volta, con l'avviso in coda all'esito
        dell'azione, e un file rimesso a posto che si rovina di nuovo si
        segnala di nuovo."""
        from config import user_data_path

        self._prepara("Alfa")
        rovinati = [user_data_path(f"Tornello - Rovinato{numero}.json") for numero in (1, 2)]
        with open(rovinati[0], "w", encoding="utf-8") as f:
            f.write("{rovinato")
        principale.populate_tree()
        _eventi_in_coda()
        assert principale.last_status_msg == "Attenzione: un file di torneo non leggibile, dettagli sotto."

        principale.set_status("Risultato registrato: 1-0.")
        principale.populate_tree()
        principale.populate_tree()
        _eventi_in_coda()

        assert principale.last_status_msg == "Risultato registrato: 1-0."
        assert principale.main_text.GetValue().count("Torneo non leggibile: Tornello - Rovinato1.json") == 1

        with open(rovinati[1], "w", encoding="utf-8") as f:
            f.write("{rovinato")
        principale.populate_tree()
        _eventi_in_coda()
        testo = principale.main_text.GetValue()
        assert principale.last_status_msg == "Risultato registrato: 1-0. Attenzione: un file di torneo non leggibile, dettagli sotto."
        assert testo.count("Torneo non leggibile: Tornello - Rovinato1.json") == 1
        assert testo.count("Torneo non leggibile: Tornello - Rovinato2.json") == 1

        self._scrivi(rovinati[0], _torneo_in_corso("Rimesso a posto"))
        principale.populate_tree()
        with open(rovinati[0], "w", encoding="utf-8") as f:
            f.write("{rovinato")
        principale.populate_tree()
        _eventi_in_coda()
        assert principale.main_text.GetValue().count("Torneo non leggibile: Tornello - Rovinato1.json") == 2

    def test_il_torneo_aperto_da_un_altra_cartella_sta_nell_albero(self, principale, suoni, monkeypatch, tmp_path):
        """Ctrl+O su un torneo fuori dalla cartella del programma, con il
        cursore su Alfa: il torneo ha la sua voce con i suoi rami, il cursore
        ci va, e le sue partite si scelgono e si aprono senza caricare
        nient'altro, anche dopo una ricostruzione dell'albero."""
        percorsi = self._prepara("Alfa")
        esterno = str(tmp_path / "esterna" / "Tornello - Esterno.json")
        self._scrivi(esterno, _torneo_in_corso("Esterno"))
        registro = self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Alfa"])

        self._apri_con_ctrl_o(principale, monkeypatch, esterno)

        assert principale.active_filename == esterno
        assert self._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": esterno}
        principale.populate_tree()
        partita = self._voce(principale, action="activate_match", filepath=esterno, round=1, board_num=1)
        registro.caricati.clear()
        aperte = []
        principale.on_activate_match = aperte.append
        principale.tree_ctrl.SelectItem(partita)
        principale.on_tree_item_activated(SimpleNamespace(GetItem=lambda: partita))

        assert registro.caricati == []
        assert principale.active_filename == esterno
        assert [partita_aperta["id"] for partita_aperta in aperte] == [1]

    def test_lo_stesso_file_scritto_con_altre_maiuscole_e_lo_stesso_torneo(self, principale, suoni, monkeypatch):
        """Ctrl+O su Alfa, con il percorso tutto in minuscolo, come puo'
        restituirlo la finestra Apri: Alfa ha una voce sola, il cursore ci
        va, e scegliere le sue partite non lo ricarica."""
        percorsi = self._prepara("Alfa", "Beta")
        registro = self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Beta"])

        self._apri_con_ctrl_o(principale, monkeypatch, percorsi["Alfa"].lower())

        voci_di_alfa = []
        voce, cookie = principale.tree_ctrl.GetFirstChild(principale.tree_root)
        while voce.IsOk():
            dati = principale.tree_ctrl.GetItemData(voce) or {}
            if dati.get("action") == "select_tournament" and os.path.normcase(dati["filepath"]) == os.path.normcase(percorsi["Alfa"]):
                voci_di_alfa.append(voce)
            voce, cookie = principale.tree_ctrl.GetNextChild(principale.tree_root, cookie)
        assert len(voci_di_alfa) == 1
        assert principale.tree_ctrl.GetSelection() == voci_di_alfa[0]
        registro.caricati.clear()

        principale.tree_ctrl.SelectItem(self._voce(principale, action="activate_match", filepath=percorsi["Alfa"], round=1, board_num=1))

        assert registro.caricati == []
        assert principale.current_tournament["name"] == "Alfa"

    def test_la_scelta_nell_albero_accende_il_menu_torneo(self, principale, suoni):
        """Scegliendo un torneo con le frecce, il menu Torneo segue il
        torneo scelto. Fino alla 10.13.12 restava spento fino alla
        ricostruzione successiva dell'albero, e Ctrl+L e Ctrl+F tacevano."""
        percorsi = self._prepara("Alfa", "Beta", finiti=("Beta",))
        registro = self._sonde(principale)
        principale.populate_tree()
        assert not principale.item_standings.IsEnabled()

        self._scegli_torneo(principale, percorsi["Beta"])

        assert registro.caricati == ["Tornello - Beta.json"]
        for voce in ("item_players", "item_round", "item_standings", "item_rollback", "item_finalize"):
            assert getattr(principale, voce).IsEnabled(), voce

        self._scegli_torneo(principale, percorsi["Alfa"])

        assert registro.caricati == ["Tornello - Beta.json", "Tornello - Alfa.json"]
        assert principale.item_standings.IsEnabled()
        assert not principale.item_finalize.IsEnabled()

    def test_ctrl_l_su_un_torneo_concluso_mostra_la_classifica_finale(self, principale, suoni, monkeypatch, sample_tournament_dict):
        """La stessa classifica della voce Classifica dell'albero. Fino alla
        10.13.13 Ctrl+L diceva Classifica Parziale - Dopo Turno 5."""
        from config import ARCHIVED_TOURNAMENTS_DIR

        assert sample_tournament_dict.get("concluded")
        percorso = os.path.join(ARCHIVED_TOURNAMENTS_DIR, "2025", "06 Giugno", "ASCId_Primavera_1", "Tornello - ASCId_Primavera_1.json")
        self._scrivi(percorso, sample_tournament_dict)
        registro = self._sonde(principale)
        self._apri_con_ctrl_o(principale, monkeypatch, percorso)

        self._dal_menu(principale, principale.item_standings.GetId())

        testo = principale.main_text.GetValue()
        assert "CLASSIFICA FINALE" in testo
        assert "Classifica Parziale" not in testo
        assert registro.fuoco[-1] == "main_text"
        principale.show_standings_verbose()
        assert principale.main_text.GetValue() == testo

    def test_la_classifica_di_un_torneo_concluso_ha_i_valori_salvati(self, principale, suoni, monkeypatch, sample_tournament_dict):
        """Dalla 10.13.19 Ctrl+L e la voce Classifica mostrano i valori
        salvati alla finalizzazione, e il torneo aperto non cambia: Di Bari
        ha l'ARO e la variazione Elo di allora, 1498 e +25, ed e'
        quattordicesimo come nella classifica che Tornello scrisse alla
        finalizzazione."""
        from config import ARCHIVED_TOURNAMENTS_DIR

        percorso = os.path.join(ARCHIVED_TOURNAMENTS_DIR, "2025", "06 Giugno", "ASCId_Primavera_1", "Tornello - ASCId_Primavera_1.json")
        self._scrivi(percorso, sample_tournament_dict)
        self._sonde(principale)
        self._apri_con_ctrl_o(principale, monkeypatch, percorso)

        def fotografia():
            campi = ("points", "display_rank", "final_rank", "buchholz", "buchholz_cut1", "aro", "performance_rating", "elo_change", "k_factor")
            return {p["id"]: tuple(p.get(c) for c in campi) for p in principale.current_tournament["players"]}

        prima = fotografia()
        self._dal_menu(principale, principale.item_standings.GetId())

        riga = next(r for r in principale.main_text.GetValue().splitlines() if "Di Bari, Vincenzo" in r)
        assert riga.split()[0] == "14"
        assert " 1498 " in riga and riga.rstrip().endswith("+25")
        assert fotografia() == prima

    def test_il_fuoco_sull_albero_non_apre_un_torneo_da_solo(self, principale, suoni, monkeypatch):
        """All'avvio con due tornei in corso nessun torneo e' aperto: il
        cursore sta su Nuovo torneo, e il fuoco che arriva all'albero non
        apre niente. Poi Ctrl+O su Gamma, e un ridisegno che non ritrova la
        voce di prima: il cursore va su Gamma, e il fuoco non apre Alfa.
        Fino alla 10.13.9 il controllo di Windows, trovando l'albero senza
        voce scelta, sceglieva la prima voce, e si apriva il suo torneo,
        anche al posto di quello aperto."""
        percorsi = self._prepara("Alfa", "Gamma")
        registro = self._sonde(principale)
        principale.populate_tree()

        assert self._dati_della_selezione(principale) == {"action": "start_new_tournament"}
        self._fuoco_all_albero(principale)
        assert registro.caricati == []
        assert principale.current_tournament is None

        self._apri_con_ctrl_o(principale, monkeypatch, percorsi["Gamma"])
        principale._tree_restore_target = {"action": "voce_che_non_c_e"}
        principale.populate_tree()
        registro.caricati.clear()
        esito = principale.last_status_msg

        self._fuoco_all_albero(principale)

        assert registro.caricati == []
        assert principale.active_filename == percorsi["Gamma"]
        assert self._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": percorsi["Gamma"]}
        assert principale.last_status_msg == esito

    def test_ctrl_o_con_il_percorso_scritto_in_un_altro_modo(self, principale, suoni, monkeypatch):
        """Ctrl+O su Alfa, in preparazione, con il percorso tutto in
        minuscolo: il torneo aperto prende il percorso nella forma
        dell'albero, e CANC su un iscritto lo toglie dal file e dalla
        memoria, anche dopo il salvataggio successivo. Poi Ctrl+O su Gamma,
        in corso, allo stesso modo: CANC su un giocatore propone il ritiro,
        senza dire Torneo non aperto."""
        import json

        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        torneo = _torneo_in_corso("Alfa")
        torneo["rounds"] = []
        self._scrivi(alfa, torneo)
        percorsi = self._prepara("Beta", "Gamma")
        registro = self._sonde(principale)
        principale.populate_tree()
        finestre = TestEliminazioneDelTorneo._dialoghi_finti(monkeypatch)

        self._apri_con_ctrl_o(principale, monkeypatch, alfa.lower())

        assert principale.active_filename == alfa
        iscritto = self._voce(principale, action="show_player_detail", filepath=alfa, player={"id": "BIA"})
        principale.tree_ctrl.SelectItem(iscritto)
        registro.caricati.clear()
        principale.delete_player_from_tournament(iscritto, principale.tree_ctrl.GetItemData(iscritto)["player"])
        principale._save_state()

        with open(alfa, encoding="utf-8") as f:
            su_disco = [p["id"] for p in json.load(f)["players"]]
        assert su_disco == ["VER", "NER", "RUS"]
        assert [p["id"] for p in principale.current_tournament["players"]] == su_disco
        assert registro.caricati == []

        self._apri_con_ctrl_o(principale, monkeypatch, percorsi["Gamma"].lower())
        chiesti = []
        principale._conferma_ritiro = lambda codice, percorso, domanda=None: chiesti.append(codice) and False
        giocatore = self._voce(principale, action="show_player_detail", filepath=percorsi["Gamma"], player={"id": "NER"})
        finestre.clear()

        principale.delete_player_from_tournament(giocatore, principale.tree_ctrl.GetItemData(giocatore)["player"])

        assert principale.active_filename == percorsi["Gamma"]
        assert "Torneo non aperto" not in [titolo for titolo, _testo in finestre]
        assert chiesti == ["NER"]

    def test_il_cursore_ritrova_la_voce_scritta_con_altre_maiuscole(self, principale, suoni):
        """Il bersaglio del cursore dopo un risultato o un turno nuovo si
        ritrova anche se scrive il file con altre maiuscole: l'albero non
        resta senza voce scelta, e non si carica niente."""
        percorsi = self._prepara("Alfa", "Beta")
        registro = self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Beta"])
        registro.caricati.clear()
        principale._tree_restore_target = {"action": "show_round_report", "filepath": percorsi["Beta"].lower(), "round": 1}

        principale.populate_tree()

        assert self._dati_della_selezione(principale) == {"action": "show_round_report", "filepath": percorsi["Beta"], "round": 1}
        assert registro.caricati == []

    @pytest.mark.parametrize("nome", ["Tornello - Players_db.json", "Tornello - Settings.json", "selected_language.json", "Tornello - Altro.json"])
    def test_ctrl_o_non_apre_come_torneo_un_file_che_non_lo_e(self, principale, suoni, monkeypatch, nome):
        """Il database dei giocatori, le impostazioni, la lingua scelta e un
        JSON senza la forma di un torneo: il suono dell'errore e un
        messaggio, il torneo aperto resta quello, il file resta com'era, e
        nell'albero non compare. Fino alla 10.13.11 il database si apriva
        come un torneo, con le persone come iscritti, e CANC su una di loro
        la toglieva dal database. I file del programma si riconoscono dal
        percorso, qui anche con dentro un nome e dei turni; gli altri dalla
        forma, e il database vero un nome non ce l'ha."""
        from config import user_data_path

        percorsi = self._prepara("Alfa")
        percorso = user_data_path(nome)
        contenuto = {"schema_version": 2, "players": [{"id": "ROSMA001", "first_name": "Mario", "last_name": "Rossi", "current_elo": 1800}]}
        if nome != "Tornello - Altro.json":
            contenuto.update(name="Mario", rounds=[])
        self._scrivi(percorso, contenuto)
        with open(percorso, "rb") as f:
            prima = f.read()
        registro = self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Alfa"])
        finestre = TestEliminazioneDelTorneo._dialoghi_finti(monkeypatch)
        suoni.clear()
        registro.caricati.clear()

        self._apri_con_ctrl_o(principale, monkeypatch, percorso)

        assert suoni == ["errore"]
        assert [titolo for titolo, _testo in finestre] == ["Non è un torneo"]
        assert nome in finestre[0][1]
        assert principale.active_filename == percorsi["Alfa"]
        assert principale.GetTitle().endswith("[Alfa]")
        assert principale.last_status_msg == "Il torneo non si è aperto: resta aperto 'Alfa'."
        assert os.path.normcase(percorso) not in self._tutti_i_file(principale)
        with open(percorso, "rb") as f:
            assert f.read() == prima

    def test_ctrl_o_che_non_riesce_lascia_aperto_il_torneo_di_prima(self, principale, suoni, monkeypatch, tmp_path):
        """Un file rovinato, scelto con Ctrl+O mentre e' aperto Alfa: un
        messaggio lo dice, Alfa resta aperto e la barra di stato lo dice.
        Se invece non si rilegge il file del torneo aperto, nessun torneo
        resta aperto: la versione in memoria, forse vecchia, il primo
        salvataggio la riscriverebbe sul file."""
        percorsi = self._prepara("Alfa")
        rotto = str(tmp_path / "altrove" / "Tornello - Rotto.json")
        os.makedirs(os.path.dirname(rotto))
        with open(rotto, "w", encoding="utf-8") as f:
            f.write("{rotto")
        self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Alfa"])
        messaggi = []
        monkeypatch.setattr("wx.MessageBox", lambda testo, *a, **k: messaggi.append(testo))

        self._apri_con_ctrl_o(principale, monkeypatch, rotto)

        assert len(messaggi) == 1
        assert messaggi[0].startswith("Errore nel caricamento del torneo:")
        assert principale.active_filename == percorsi["Alfa"]
        assert principale.GetTitle().endswith("[Alfa]")
        assert principale.last_status_msg == "Il torneo non si è aperto: resta aperto 'Alfa'."

        with open(percorsi["Alfa"], "w", encoding="utf-8") as f:
            f.write("{rovinato")
        self._apri_con_ctrl_o(principale, monkeypatch, percorsi["Alfa"])

        assert len(messaggi) == 2
        self._nessun_torneo_aperto(principale)
        assert principale.last_status_msg == "Il torneo non si è aperto: nessun torneo aperto."

    def test_il_torneo_di_un_altra_cartella_si_distingue_da_quello_con_lo_stesso_nome(self, principale, suoni, monkeypatch, tmp_path):
        """Alfa nella cartella del programma, e un altro Alfa su una
        chiavetta, aperto con Ctrl+O: la sua voce e la barra di stato dicono
        la cartella. Lo stesso per un torneo concluso: l'edizione in
        archivio e la sua copia nella cartella di lavoro esterna. Fino alla
        10.13.11 le due voci avevano la stessa etichetta."""
        from config import ARCHIVED_TOURNAMENTS_DIR

        self._prepara("Alfa", "Beta")
        chiavetta = str(tmp_path / "chiavetta" / "Tornello - Alfa.json")
        self._scrivi(chiavetta, _torneo_in_corso("Alfa"))
        concluso = _torneo_in_corso("Delta", finito=True)
        concluso["concluded"] = True
        self._scrivi(os.path.join(ARCHIVED_TOURNAMENTS_DIR, "2026", "10 Ottobre", "Delta", "Tornello - Delta.json"), concluso)
        lavoro = str(tmp_path / "Lavoro" / "Tornello - Delta.json")
        self._scrivi(lavoro, concluso)
        self._sonde(principale)
        principale.populate_tree()

        self._apri_con_ctrl_o(principale, monkeypatch, chiavetta)

        etichette = [testo for testo, _dati in self._voci_della_radice(principale)]
        assert etichette[:3] == ["Alfa", "Beta", "Alfa (dalla cartella chiavetta)"]
        assert principale.last_status_msg == "Torneo 'Alfa' caricato con successo, dalla cartella chiavetta."
        assert self._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": chiavetta}

        self._apri_con_ctrl_o(principale, monkeypatch, lavoro)

        assert self._voci_dei_conclusi(principale) == ["Delta (Ottobre 2026)", "Delta (Ottobre 2026, dalla cartella Lavoro)"]
        assert "Alfa (dalla cartella chiavetta)" not in [testo for testo, _dati in self._voci_della_radice(principale)]

    def test_un_file_rovinato_durante_un_azione_si_segnala_dopo_il_suo_esito(self, principale, suoni, monkeypatch):
        """Un file di torneo che si rovina a sessione avviata, scoperto dal
        ridisegno dell'albero dentro la finalizzazione: ad azione finita la
        barra di stato dice il suo esito e poi l'avviso, e l'area centrale
        ha la riga del file. Prima la finalizzazione riscriveva subito barra
        e area centrale, e la segnalazione spariva per tutta la sessione."""
        import ui
        from config import ARCHIVED_TOURNAMENTS_DIR, user_data_path

        percorsi = self._prepara("Alfa", "Beta", finiti=("Alfa",))
        self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Alfa"])
        TestEliminazioneDelTorneo._dialoghi_finti(monkeypatch)
        monkeypatch.setattr("wx.MessageBox", lambda *a, **k: None)
        archiviato = os.path.join(ARCHIVED_TOURNAMENTS_DIR, "2026", "10 Ottobre", "Alfa", "Tornello - Alfa.json")

        def finalizza(torneo, database, percorso, avvisi, raccolte_rimaste=None):
            torneo["concluded"] = True
            self._scrivi(archiviato, torneo)
            os.remove(percorso)
            return True

        monkeypatch.setattr(ui, "finalize_tournament", finalizza)
        with open(user_data_path("Tornello - Rovinato.json"), "w", encoding="utf-8") as f:
            f.write("{rovinato")

        self._dal_menu(principale, principale.item_finalize.GetId())
        _eventi_in_coda()

        assert principale.last_status_msg == "Torneo concluso e archiviato. Attenzione: un file di torneo non leggibile, dettagli sotto."
        assert principale.main_text.GetValue().count("Torneo non leggibile: Tornello - Rovinato.json") == 1

    def test_dopo_l_eliminazione_l_albero_non_ha_piu_le_voci_del_torneo(self, principale, suoni, monkeypatch, tmp_path):
        """Eliminato Beta, in preparazione e aperto: nell'albero non restano
        la categoria In Preparazione, ormai vuota, ne' la voce Avvio torneo,
        che con INVIO dava un errore; il cursore sta su una voce che c'e', e
        non si carica niente."""
        from config import user_data_path

        self._prepara("Alfa")
        beta = user_data_path("Tornello - Beta.json")
        torneo = _torneo_in_corso("Beta")
        torneo["rounds"] = []
        self._scrivi(beta, torneo)
        registro = self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, beta)
        principale.populate_tree()
        assert "Avvio torneo: Beta" in [testo for testo, _dati in self._voci_della_radice(principale)]
        TestEliminazioneDelTorneo._dialoghi_finti(monkeypatch)
        TestEliminazioneDelTorneo()._cestino_finto(monkeypatch, tmp_path / "cestino")
        registro.caricati.clear()

        principale.delete_tournament_completely(principale.tree_ctrl.GetSelection(), beta)

        assert [testo for testo, _dati in self._voci_della_radice(principale)] == ["Alfa", "Nuovo torneo"]
        assert os.path.normcase(beta) not in self._tutti_i_file(principale)
        assert principale.tree_ctrl.GetSelection().IsOk()
        assert registro.caricati == []
        self._nessun_torneo_aperto(principale)

    def test_invio_su_un_torneo_che_non_si_apre_non_fa_partire_l_azione(self, principale, suoni, monkeypatch):
        """INVIO su calcola il turno 1 di Beta, il cui file non c'e' piu':
        il messaggio d'errore, e il turno non parte. Fino alla 10.13.9
        l'avvio proseguiva, senza un torneo da avviare."""
        from config import user_data_path

        percorsi = self._prepara("Alfa")
        beta = user_data_path("Tornello - Beta.json")
        torneo = _torneo_in_corso("Beta")
        torneo["rounds"] = []
        self._scrivi(beta, torneo)
        self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Alfa"])
        voce = self._voce(principale, action="start_tournament_matchmaking_action", filepath=beta)
        os.remove(beta)
        messaggi, avviati = [], []
        monkeypatch.setattr("wx.MessageBox", lambda testo, *a, **k: messaggi.append(testo))
        principale.start_tournament_matchmaking = lambda *a, **k: avviati.append(principale.active_filename)

        principale.on_tree_item_activated(SimpleNamespace(GetItem=lambda: voce))

        assert len(messaggi) == 1
        assert avviati == []

    def test_finalizza_e_annulla_turno_nominano_il_torneo(self, principale, suoni, monkeypatch):
        """Le due domande prima di un'azione che non si torna indietro dicono
        su quale torneo si agisce; rispondendo No non cambia niente."""
        import wx

        import gui.main_frame as mf

        percorsi = self._prepara("Alfa", finiti=("Alfa",))
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Alfa"])
        domande = []

        class Rifiuto:
            def __init__(self, genitore, titolo, messaggio, style=wx.OK, **altro):
                domande.append(messaggio)

            def ShowModal(self):
                return wx.ID_NO

            def Destroy(self):
                pass

        monkeypatch.setattr(mf, "AccessibleMsgDialog", Rifiuto)

        self._dal_menu(principale, principale.item_finalize.GetId())
        self._dal_menu(principale, principale.item_rollback.GetId())

        assert domande[0].startswith("Sei sicuro di voler concludere definitivamente il torneo Alfa?")
        assert domande[1].startswith("Sei sicuro di voler annullare l'ultimo turno del torneo Alfa e tornare indietro?")
        assert len(principale.current_tournament["rounds"]) == 1
        assert not principale.current_tournament.get("concluded")

    @pytest.mark.parametrize("prende", (True, False))
    def test_la_time_machine_manda_nel_cestino_i_dettagli_del_turno_tolto(self, principale, suoni, monkeypatch, prende):
        """Dalla 10.13.60 (issue 68): annullato il turno 2, gia' concluso,
        il suo file dei dettagli va nel cestino, con la finestra principale
        come proprietaria della domanda di Windows, e quello del turno 1
        resta. Fino alla 10.13.59 restava anche quello del turno 2. Un file
        che il cestino non prende resta dov'e': lo dice un messaggio, con il
        suono dell'errore. Cestino e finestre di messaggio sono finti."""
        import wx

        import gui.main_frame as mf
        import utils
        from config import user_data_path

        torneo = _torneo_in_corso("Alfa", finito=True)
        torneo.update(total_rounds=3, current_round=2)
        torneo["rounds"].append({"round": 2, "matches": [
            {"id": 3, "white_player_id": "VER", "black_player_id": "NER", "result": "0-1"},
            {"id": 4, "white_player_id": "RUS", "black_player_id": "BIA", "result": "1-0"},
        ]})
        percorso = user_data_path("Tornello - Alfa.json")
        self._scrivi(percorso, torneo)
        dettagli = [user_data_path(f"Tornello - Alfa - Turno {numero} Dettagli.txt") for numero in (1, 2)]
        for file in dettagli:
            with open(file, "w", encoding="utf-8") as f:
                f.write("dettagli")
        principale.populate_tree()
        self._scegli_torneo(principale, percorso)
        assert len(principale.current_tournament["rounds"]) == 2
        ricevuti, finestre = [], []

        def cestino(file, finestra=None):
            ricevuti.append((file, finestra))
            if not prende:
                return False
            os.remove(file)
            return True

        class DialogoFinto:
            def __init__(self, genitore, titolo, messaggio, style=wx.OK, **altro):
                finestre.append((titolo, messaggio))
                self.style = style

            def ShowModal(self):
                return wx.ID_YES if self.style & wx.YES_NO else wx.ID_OK

            def Destroy(self):
                pass

        monkeypatch.setattr(utils, "delete_file_to_trash", cestino)
        monkeypatch.setattr(mf, "AccessibleMsgDialog", DialogoFinto)
        suoni.clear()

        self._dal_menu(principale, principale.item_rollback.GetId())

        assert len(principale.current_tournament["rounds"]) == 1
        assert ricevuti == [(dettagli[1], principale.GetHandle())]
        assert os.path.exists(dettagli[0])
        assert os.path.exists(dettagli[1]) is not prende
        if prende:
            assert len(finestre) == 1
            assert "errore" not in suoni
        else:
            assert finestre[1] == (
                "File rimasto fuori dal cestino",
                "Il file dei dettagli del turno tolto non è andato nel cestino, e resta dov'è, anche se il turno non c'è più:\n" + dettagli[1],
            )
            assert suoni[-1] == "errore"

    def test_con_il_database_che_non_si_legge_la_finalizzazione_non_parte(self, principale, suoni, monkeypatch):
        """Dalla 10.13.16: dopo il Si' alla domanda, il database bloccato
        ferma tutto con un messaggio, e database e torneo restano come
        sono. Letto vuoto, la finalizzazione avrebbe creato tutti gli
        iscritti, e il database sul disco avrebbe perso gli altri soci."""
        import config
        from test_db import _database_con_giocatori, lettura_bloccata

        percorsi = self._prepara("Alfa", finiti=("Alfa",))
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Alfa"])
        database_prima = _database_con_giocatori()
        with open(percorsi["Alfa"], "rb") as f:
            torneo_prima = f.read()
        finestre = TestDatabaseCheNonSiLeggeNelleFinestre._dialoghi_finti(monkeypatch)
        lettura_bloccata(monkeypatch, config.PLAYER_DB_FILE)
        suoni.clear()

        self._dal_menu(principale, principale.item_finalize.GetId())

        assert finestre[0][1].startswith("Sei sicuro di voler concludere definitivamente il torneo Alfa?")
        assert finestre[1][1].startswith("Il database dei giocatori, Tornello - Players_db.json, c'è ma non si è potuto leggere: ")
        assert len(finestre) == 2
        assert suoni == ["errore"]
        with open(config.PLAYER_DB_FILE, "rb") as f:
            assert f.read() == database_prima
        with open(percorsi["Alfa"], "rb") as f:
            assert f.read() == torneo_prima
        assert not principale.current_tournament.get("concluded")


class TestIscrizioneDallaRicercaFide:
    """Dalla 10.13.15 chi si iscrive dalla ricerca FIDE entra anche nel
    database dei giocatori, che si salva subito, e si iscrive con la scheda
    di li'. Fino alla 10.13.14 entrava nel torneo con un identificativo
    FIDE_ e senza scheda, e alla finalizzazione restava senza Elo, storico e
    medaglia, come due iscritti di Autunneo2."""

    def _finestra(self, telaio, monkeypatch, giocatori, risultati):
        from gui.dialogs import player_enrollment_dialog

        monkeypatch.setattr(player_enrollment_dialog, "search_players", lambda query, **k: list(risultati))
        dlg = player_enrollment_dialog.PlayerEnrollmentDialog(telaio, giocatori, [], telaio.settings)
        dlg.search_fide.ChangeValue("rossi")
        dlg.esegui_ricerca_fide()
        dlg.list_fide_results.SetSelection(0)
        return dlg

    def test_il_giocatore_entra_nel_database_e_si_iscrive_con_la_sua_scheda(self, telaio, suoni, monkeypatch):
        from db_players import load_players_db

        giocatori = {}
        dlg = self._finestra(telaio, monkeypatch, giocatori, _risultati_fide(1))
        try:
            dlg.on_add_fide(None)
            iscritti = dlg.get_enrolled_players()
            assert len(iscritti) == 1
            iscritto = iscritti[0]
            assert iscritto["id"] == "ROSMA001"
            assert not iscritto["id"].startswith("FIDE_")
            assert giocatori["ROSMA001"] is iscritto
            sul_disco = load_players_db()["ROSMA001"]
            assert sul_disco["fide_id_num_str"] == "900000"
            assert (sul_disco["current_elo"], sul_disco["elo_rapid"]) == (1500, 1400)
            assert "aggiunta_giocatore" in suoni
            # Iscritto, esce dai risultati FIDE e dalla lista locale.
            assert dlg.list_local_results.GetCount() == 0
        finally:
            _chiudi(dlg)

    def test_una_scheda_locale_con_lo_stesso_id_fide_si_iscrive_senza_doppioni(self, telaio, suoni, monkeypatch):
        esistente = {"id": "ROSMA009", "first_name": "Mario", "last_name": "Rossi000", "current_elo": 1600, "fide_id_num_str": "900000"}
        giocatori = {"ROSMA009": esistente}
        dlg = self._finestra(telaio, monkeypatch, giocatori, _risultati_fide(1))
        try:
            dlg.on_add_fide(None)
            assert dlg.get_enrolled_players() == [esistente]
            assert list(giocatori) == ["ROSMA009"]
        finally:
            _chiudi(dlg)

    def test_se_il_database_non_si_salva_non_si_iscrive(self, telaio, suoni, monkeypatch):
        import db_players
        from gui.dialogs import accessible_msg_dialog

        messaggi = []

        class Messaggio:
            def __init__(self, genitore, titolo, testo, **altro):
                messaggi.append(testo)

            def ShowModal(self):
                return 0

            def Destroy(self):
                pass

        monkeypatch.setattr(accessible_msg_dialog, "AccessibleMsgDialog", Messaggio)
        monkeypatch.setattr(db_players, "save_players_db", lambda giocatori: False)
        giocatori = {}
        dlg = self._finestra(telaio, monkeypatch, giocatori, _risultati_fide(1))
        try:
            suoni.clear()
            dlg.on_add_fide(None)
            assert dlg.get_enrolled_players() == []
            assert giocatori == {}
            assert suoni == ["errore"]
            assert messaggi[0].startswith("Il database dei giocatori non si è potuto salvare: Rossi000 Mario non è stato iscritto.")
        finally:
            _chiudi(dlg)

    def test_un_giocatore_gia_iscritto_lo_dice_un_messaggio(self, telaio, suoni, monkeypatch):
        """La ricerca FIDE esclude gli iscritti, ma una scheda con
        l'identificativo FIDE scritto come numero, come nei database vecchi,
        sfuggiva: aggiunta dalla ricerca FIDE, suonava l'errore e basta."""
        from gui.dialogs import accessible_msg_dialog, player_enrollment_dialog

        messaggi = []

        class Messaggio:
            def __init__(self, genitore, titolo, testo, **altro):
                messaggi.append(testo)

            def ShowModal(self):
                return 0

            def Destroy(self):
                pass

        monkeypatch.setattr(accessible_msg_dialog, "AccessibleMsgDialog", Messaggio)
        monkeypatch.setattr(player_enrollment_dialog, "search_players", lambda query, **k: _risultati_fide(1))
        esistente = {"id": "ROSMA009", "first_name": "Mario", "last_name": "Rossi000", "current_elo": 1600, "fide_id_num_str": 900000}
        dlg = player_enrollment_dialog.PlayerEnrollmentDialog(telaio, {"ROSMA009": esistente}, [esistente], telaio.settings)
        try:
            dlg.search_fide.ChangeValue("rossi")
            dlg.esegui_ricerca_fide()
            dlg.list_fide_results.SetSelection(0)
            suoni.clear()

            dlg.on_add_fide(None)

            assert dlg.get_enrolled_players() == [esistente]
            assert suoni == ["errore"]
            assert messaggi == ["Rossi000 Mario è già iscritto al torneo."]
        finally:
            _chiudi(dlg)

    def test_la_ricerca_esclude_gli_iscritti_con_la_regola_della_scheda(self, telaio, suoni, monkeypatch):
        """L'identificativo FIDE degli iscritti si confronta come lo scrive
        il database FIDE: un numero, degli spazi o uno zero non cambiano
        niente."""
        from gui.dialogs import player_enrollment_dialog

        esclusi = []

        def ricerca(query, exclude_fide_ids=None, **k):
            esclusi.append(exclude_fide_ids)
            return []

        monkeypatch.setattr(player_enrollment_dialog, "search_players", ricerca)
        iscritti = [
            {"id": "A", "fide_id_num_str": 900000},
            {"id": "B", "fide_id_num_str": " 900001 "},
            {"id": "C", "fide_id_num_str": "0"},
            {"id": "D", "fide_id_num_str": ""},
        ]
        dlg = player_enrollment_dialog.PlayerEnrollmentDialog(telaio, {}, iscritti, telaio.settings)
        try:
            dlg.search_fide.ChangeValue("rossi")
            dlg.esegui_ricerca_fide()

            assert esclusi[-1] == {"900000", "900001"}
        finally:
            _chiudi(dlg)


class TestDatabaseCheNonSiLeggeNelleFinestre:
    """Dalla 10.13.15 un database dei giocatori che c'e' ma non si legge,
    tenuto bloccato per un attimo da un altro programma o rovinato, non apre
    le finestre che lo modificano: l'iscrizione, la consultazione del
    database FIDE (Ctrl+K), la gestione del database locale e la
    sincronizzazione. Suona l'errore e un messaggio dice perche' e come
    rimediare. Fino alla 10.13.14 il database arrivava vuoto, e il primo
    salvataggio lo sostituiva con le sole schede aggiunte. La
    finalizzazione, dalla 10.13.16, e' nella classe dell'albero."""

    @staticmethod
    def _dialoghi_finti(monkeypatch):
        """Le finestre di messaggio della finestra principale annotate, per
        titolo e testo, con il Si' a ogni domanda."""
        import wx

        import gui.main_frame as mf

        finestre = []

        class DialogoFinto:
            def __init__(self, genitore, titolo, messaggio, style=wx.OK, **altro):
                finestre.append((titolo, messaggio))
                self.style = style

            def ShowModal(self):
                return wx.ID_YES if self.style & wx.YES_NO else wx.ID_OK

            def Destroy(self):
                pass

        monkeypatch.setattr(mf, "AccessibleMsgDialog", DialogoFinto)
        return finestre

    def test_le_finestre_del_database_non_si_aprono(self, principale, suoni, monkeypatch):
        import config
        import gui.dialogs as finestre_di_dialogo
        from gui.dialogs import fide_query_dialog, players_db_dialog, sync_database_dialog
        from test_db import _database_con_giocatori, lettura_bloccata

        aperte = []

        class FinestraFinta:
            def __init__(self, *a, **k):
                aperte.append(type(self).__name__)

            def ShowModal(self):
                return 0

            def Destroy(self):
                pass

        for modulo, nome in (
            (fide_query_dialog, "FideQueryDialog"),
            (players_db_dialog, "PlayersDbDialog"),
            (sync_database_dialog, "SyncDatabaseDialog"),
            (finestre_di_dialogo, "PlayerEnrollmentDialog"),
        ):
            monkeypatch.setattr(modulo, nome, type(nome, (FinestraFinta,), {}))
        database_prima = _database_con_giocatori()
        finestre = self._dialoghi_finti(monkeypatch)
        principale.current_tournament = {"name": "Alfa", "players": [], "rounds": []}
        lettura_bloccata(monkeypatch, config.PLAYER_DB_FILE, volte=5)
        suoni.clear()

        principale.on_fide_query(None)
        principale.on_local_db(None)
        principale.on_sync_db(None)
        principale.on_enroll_players(None)
        principale.on_wizard_next()

        assert aperte == []
        assert suoni == ["errore"] * 5
        assert len(finestre) == 5
        assert all(t.startswith("Il database dei giocatori, Tornello - Players_db.json, c'è ma non si è potuto leggere: ") for _titolo, t in finestre)
        with open(config.PLAYER_DB_FILE, "rb") as f:
            assert f.read() == database_prima

        # A blocco passato le finestre si aprono.
        principale.on_fide_query(None)
        principale.on_local_db(None)

        assert aperte == ["FideQueryDialog", "PlayersDbDialog"]


def _tasto_al_dialogo(dlg, codice, fuoco, monkeypatch):
    """Il tasto mandato al dialogo come lo manda Windows, con il gancio della
    tastiera, e il fuoco dove si vuole: ESC passa poi dal gestore di wx, che
    preme il pulsante di SetEscapeId."""
    import wx

    monkeypatch.setattr(wx.Window, "FindFocus", lambda: fuoco)
    evento = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
    evento.SetKeyCode(codice)
    evento.SetEventObject(fuoco)
    dlg.ProcessEvent(evento)
    return evento


class TestMessaggiEDomande:
    """Dalla 10.13.23 INVIO nel testo delle finestre di messaggio e di
    domanda preme il pulsante predefinito, ed ESC risponde No in tutte le
    domande, anche dove il predefinito e' il Si', come Finalizza Torneo o
    Turni consigliati, e chiude le finestre con il solo OK. Il testo e' un
    campo multilinea, che si teneva INVIO: la finestra restava aperta.
    EndModal e' annotato, perche' il dialogo non e' modale."""

    CASI = (
        # stile, no_predefinito, pulsante di INVIO, pulsante di ESC
        ("YES_NO", False, "ID_YES", "ID_NO"),
        ("YES_NO", True, "ID_NO", "ID_NO"),
        ("OK", False, "ID_OK", "ID_OK"),
    )

    @staticmethod
    def _crea(telaio, stile, no_predefinito=False):
        import wx

        from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog

        opzioni = {"no_predefinito": True} if no_predefinito else {}
        dlg = AccessibleMsgDialog(telaio, "Titolo", "Prima riga\nSeconda riga", style=getattr(wx, stile), settings=telaio.settings, **opzioni)
        chiusure = []
        dlg.EndModal = chiusure.append
        return dlg, chiusure

    @pytest.mark.parametrize(("stile", "no_predefinito", "invio", "esc"), CASI)
    def test_invio_nel_testo_ed_esc(self, telaio, monkeypatch, stile, no_predefinito, invio, esc):
        import wx

        dlg, chiusure = self._crea(telaio, stile, no_predefinito)
        try:
            assert dlg.GetDefaultItem().GetId() == getattr(wx, invio)
            for codice, atteso in ((wx.WXK_RETURN, invio), (wx.WXK_NUMPAD_ENTER, invio), (wx.WXK_ESCAPE, esc)):
                chiusure.clear()
                _tasto_al_dialogo(dlg, codice, dlg.msg_text, monkeypatch)
                assert chiusure == [getattr(wx, atteso)], codice
        finally:
            _chiudi(dlg)

    @pytest.mark.parametrize(("stile", "no_predefinito", "invio", "esc"), CASI)
    def test_invio_ripetuto_nel_testo_non_risponde(self, telaio, monkeypatch, stile, no_predefinito, invio, esc):
        # Chi apre la domanda con INVIO, per esempio dall'albero, e tiene il
        # tasto un attimo di troppo manda al testo degli INVIO ripetuti: non
        # devono rispondere Si' a una domanda non letta.
        import wx

        class TastoRipetuto(wx.KeyEvent):
            """wx non sa impostare la ripetizione su un evento costruito:
            la dice questa sottoclasse, che il gestore riceve com'e'."""

            def IsAutoRepeat(self):
                return True

        dlg, chiusure = self._crea(telaio, stile, no_predefinito)
        try:
            monkeypatch.setattr(wx.Window, "FindFocus", lambda: dlg.msg_text)
            for codice in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                evento = TastoRipetuto(wx.wxEVT_CHAR_HOOK)
                evento.SetKeyCode(codice)
                evento.SetEventObject(dlg.msg_text)
                dlg.ProcessEvent(evento)
            assert chiusure == []
            # Il primo INVIO, che non e' ripetuto, risponde come sempre.
            _tasto_al_dialogo(dlg, wx.WXK_RETURN, dlg.msg_text, monkeypatch)
            assert chiusure == [getattr(wx, invio)]
        finally:
            _chiudi(dlg)

    def test_le_frecce_leggono_il_testo_e_i_pulsanti_tengono_invio(self, telaio, monkeypatch):
        import wx

        dlg, chiusure = self._crea(telaio, "YES_NO")
        try:
            assert dlg.msg_text.IsMultiLine() and not dlg.msg_text.IsEditable()
            monkeypatch.setattr(wx.Window, "FindFocus", lambda: dlg.msg_text)
            for codice in (wx.WXK_DOWN, wx.WXK_UP, wx.WXK_HOME, wx.WXK_END):
                evento = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
                evento.SetKeyCode(codice)
                dlg._on_tasto(evento)
                assert evento.GetSkipped(), codice
            # Sul pulsante No INVIO resta al pulsante, che risponde No.
            monkeypatch.setattr(wx.Window, "FindFocus", lambda: dlg.pulsante_no)
            evento = wx.KeyEvent(wx.wxEVT_CHAR_HOOK)
            evento.SetKeyCode(wx.WXK_RETURN)
            dlg._on_tasto(evento)
            assert evento.GetSkipped()
            assert chiusure == []
        finally:
            _chiudi(dlg)


class TestImpostazioni:
    """Dalla 10.13.25 chiudendo le Impostazioni, con OK, Annulla o ESC, il
    fuoco torna sul controllo che lo aveva: restava sulla cornice. Dalla
    10.13.38 lo rimette GBwx alla distruzione della finestra, come per tutte
    le altre, e on_preferences non lo sposta piu' da se': la prova vera, con
    le finestre mostrate sul desktop nascosto, sta in
    test_fuoco_alla_chiusura.py. Dalla 10.13.26 annullando dopo aver mosso
    il volume il file torna al volume di prima."""

    @staticmethod
    def _preferenze_finte(monkeypatch, esito, registro):
        import gui.main_frame as mf

        class PreferenzeFinte:
            def __init__(self, genitore, impostazioni):
                self.impostazioni = dict(impostazioni)

            def ShowModal(self):
                registro.append("mostrata")
                return esito

            def get_settings(self):
                return self.impostazioni

            def rimetti_il_volume(self):
                registro.append("volume di prima")

            def Destroy(self):
                registro.append("distrutta")

        monkeypatch.setattr(mf, "VisualSettingsDialog", PreferenzeFinte)

    @pytest.mark.parametrize(
        ("esito", "atteso"),
        [
            ("ID_OK", ["mostrata", "distrutta"]),
            ("ID_CANCEL", ["mostrata", "volume di prima", "distrutta"]),
        ],
    )
    def test_si_chiude_senza_spostare_il_fuoco_da_se(self, principale, monkeypatch, esito, atteso):
        """Nessun SetFocus dopo Destroy: il fuoco lo rimette GBwx."""
        import wx

        registro = []
        self._preferenze_finte(monkeypatch, getattr(wx, esito), registro)
        for nome in ("main_text", "tree_ctrl", "status_text"):
            getattr(principale, nome).SetFocus = lambda nome=nome: registro.append(f"fuoco {nome}")
        monkeypatch.setattr(wx.Window, "FindFocus", lambda: principale.status_text)
        principale.on_preferences(None)
        assert registro == atteso

    @staticmethod
    def _finestra_vera(telaio, monkeypatch, volume):
        """Le impostazioni vere, con il file che dice volume e un'altra
        chiave da non perdere, e i suoni annotati."""
        import json

        import config
        from gui.dialogs import visual_settings_dialog

        suonati = []
        monkeypatch.setattr(visual_settings_dialog, "play_sound", lambda nome, *a, **k: suonati.append(nome))
        percorso = config.user_data_path("Tornello - Settings.json")
        with open(percorso, "w", encoding="utf-8") as f:
            json.dump({"volume": volume, "font_size": 18}, f)
        dlg = visual_settings_dialog.VisualSettingsDialog(telaio, dict(telaio.settings, volume=volume))
        return dlg, percorso, suonati

    @staticmethod
    def _nel_file(percorso):
        import json

        with open(percorso, encoding="utf-8") as f:
            return json.load(f)

    def test_annullando_il_volume_torna_quello_di_prima(self, telaio, monkeypatch):
        import utils

        dlg, percorso, suonati = self._finestra_vera(telaio, monkeypatch, 40)
        try:
            dlg.slider_vol.SetValue(90)
            dlg.on_volume_change(None)
            # Il suono di prova si sente al volume nuovo, scritto nel file.
            assert self._nel_file(percorso) == {"volume": 90, "font_size": 18}
            assert utils._volume_base() == 0.9
            assert suonati == ["prova_volume"]
            dlg.rimetti_il_volume()
            assert self._nel_file(percorso) == {"volume": 40, "font_size": 18}
            assert utils._volume_base() == 0.4
            assert suonati == ["prova_volume"]
        finally:
            _chiudi(dlg)
            # Il volume letto resta in memoria: le prove dopo non lo trovano.
            utils.invalida_volume_audio()

    def test_anche_dopo_reset_default(self, telaio, monkeypatch):
        dlg, percorso, _suonati = self._finestra_vera(telaio, monkeypatch, 75)
        try:
            dlg.on_reset(None)
            assert self._nel_file(percorso)["volume"] == 50
            dlg.rimetti_il_volume()
            assert self._nel_file(percorso) == {"volume": 75, "font_size": 18}
        finally:
            _chiudi(dlg)

    def test_senza_toccare_il_volume_annullare_non_scrive(self, telaio, monkeypatch):
        import os

        dlg, percorso, _suonati = self._finestra_vera(telaio, monkeypatch, 40)
        try:
            os.remove(percorso)
            dlg.rimetti_il_volume()
            assert not os.path.exists(percorso)
        finally:
            _chiudi(dlg)


class TestCalendarioIcs:
    """Dalla 10.13.27 le righe del calendario finiscono con CR LF, come vuole
    RFC 5545: dalla 9.0.0 finivano con CR CR LF, perche' il file si apriva
    con newline uguale a CR LF su un testo che li aveva gia'. Dalla stessa
    versione una sola partita dalla data illeggibile si dice al singolare."""

    @staticmethod
    def _file_scelto(monkeypatch, percorso):
        """La finestra di salvataggio finta, che sceglie il percorso."""
        import wx

        class SceltaFinta:
            def __init__(self, *argomenti, **opzioni):
                pass

            def ShowModal(self):
                return wx.ID_OK

            def GetPath(self):
                return str(percorso)

            def Destroy(self):
                pass

        monkeypatch.setattr(wx, "FileDialog", SceltaFinta)

    def test_le_righe_finiscono_con_cr_lf(self, principale, suoni, monkeypatch, tmp_path):
        percorso = tmp_path / "calendario.ics"
        self._file_scelto(monkeypatch, percorso)
        programmata = {"date": "2026-09-30", "time": "17:30", "channel": "Sala", "arbiter": "Gabry"}
        principale.current_tournament = {
            "name": "Prova",
            "tournament_id": "T1",
            "players": [
                {"id": "A1", "first_name": "Luca", "last_name": "Bianchi"},
                {"id": "B2", "first_name": "Marco", "last_name": "Russo"},
            ],
            "rounds": [{"round": 1, "matches": [{"id": 1, "white_player_id": "A1", "black_player_id": "B2", "is_scheduled": True, "schedule_info": programmata}]}],
        }
        principale.on_export_ics(None)

        dati = percorso.read_bytes()
        assert b"\r\r" not in dati
        righe = dati.split(b"\r\n")
        assert righe[0] == b"BEGIN:VCALENDAR"
        assert righe[-2:] == [b"END:VCALENDAR", b""]
        assert not any(b"\r" in riga or b"\n" in riga for riga in righe)
        assert b"SUMMARY:Turno 1 - Scacchiera 1: Bianchi Luca vs Russo Marco" in righe
        assert "conferma" in suoni

    @pytest.mark.parametrize(
        ("sbagliate", "atteso"),
        [
            (1, "Calendario esportato in 'calendario.ics', ma una partita pianificata non c'è entrata: la sua data non è leggibile."),
            (2, "Calendario esportato in 'calendario.ics', ma 2 partite pianificate non ci sono entrate: la loro data non è leggibile."),
        ],
    )
    def test_le_partite_dalla_data_illeggibile(self, principale, suoni, monkeypatch, tmp_path, sbagliate, atteso):
        # Fino alla correzione della 10.13.27 con una partita sola la barra
        # diceva 1 partite pianificate non ci sono entrate.
        percorso = tmp_path / "calendario.ics"
        self._file_scelto(monkeypatch, percorso)
        stati = []
        monkeypatch.setattr(principale, "set_status", stati.append)
        partite = [
            {"id": 1, "white_player_id": "A1", "black_player_id": "B2", "is_scheduled": True, "schedule_info": {"date": "2026-09-30", "time": "17:30"}}
        ]
        for numero in range(sbagliate):
            partite.append(
                {"id": 2 + numero, "white_player_id": "B2", "black_player_id": "A1", "is_scheduled": True, "schedule_info": {"date": "30 settembre", "time": "17:30"}}
            )
        principale.current_tournament = {
            "name": "Prova",
            "tournament_id": "T1",
            "players": [
                {"id": "A1", "first_name": "Luca", "last_name": "Bianchi"},
                {"id": "B2", "first_name": "Marco", "last_name": "Russo"},
            ],
            "rounds": [{"round": 1, "matches": partite}],
        }
        principale.on_export_ics(None)
        assert stati == [atteso]
        assert percorso.read_bytes().count(b"BEGIN:VEVENT") == 1

    def test_il_nome_proposto_e_un_file_del_torneo(self, principale, suoni, monkeypatch, tmp_path):
        # Fino alla 10.13.46 il nome proposto conteneva il nome del torneo
        # cosi' com'era, Tornello - Coppa d'Autunno 2026 - Calendario.ics, e
        # file_del_torneo non lo riconosceva: l'eliminazione del torneo lo
        # lasciava dov'era (issue 67).
        import wx

        from utils import file_del_torneo, sanitize_filename

        proposti = []

        class SceltaFinta:
            def __init__(self, *argomenti, **opzioni):
                proposti.append(opzioni.get("defaultFile"))

            def ShowModal(self):
                return wx.ID_OK

            def GetPath(self):
                return str(tmp_path / proposti[-1])

            def Destroy(self):
                pass

        monkeypatch.setattr(wx, "FileDialog", SceltaFinta)
        programmata = {"date": "2026-09-30", "time": "17:30"}
        principale.current_tournament = {
            "name": "Coppa d'Autunno 2026",
            "tournament_id": "T1",
            "players": [
                {"id": "A1", "first_name": "Luca", "last_name": "Bianchi"},
                {"id": "B2", "first_name": "Marco", "last_name": "Russo"},
            ],
            "rounds": [{"round": 1, "matches": [{"id": 1, "white_player_id": "A1", "black_player_id": "B2", "is_scheduled": True, "schedule_info": programmata}]}],
        }
        principale.on_export_ics(None)
        assert proposti == ["Tornello - Coppa_dAutunno_2026 - Calendario.ics"]
        assert file_del_torneo(proposti[0], sanitize_filename("Coppa d'Autunno 2026"))
        assert (tmp_path / proposti[0]).read_bytes().startswith(b"BEGIN:VCALENDAR\r\n")


class TestPuntiDelBye:
    """Dalla 10.13.28 il report del turno dice il bye da un punto al
    singolare: si leggeva BYE (1.0 punti)."""

    @pytest.mark.parametrize(("valore", "atteso"), [(1.0, "Bianchi Luca - BYE (1 punto)"), (0.5, "Bianchi Luca - BYE (0.5 punti)")])
    def test_i_punti_del_bye(self, principale, valore, atteso):
        principale.current_tournament = {
            "name": "Prova",
            "current_round": 1,
            "total_rounds": 5,
            "bye_value": valore,
            "players_dict": {"A1": {"id": "A1", "first_name": "Luca", "last_name": "Bianchi"}},
            "rounds": [{"round": 1, "matches": [{"id": 1, "white_player_id": "A1", "black_player_id": None, "result": "BYE"}]}],
        }
        principale.show_current_round_report()
        righe = [riga.strip() for riga in principale.main_text.GetValue().splitlines()]
        assert atteso in righe


def _lettera(etichetta):
    """La lettera di scelta rapida di una voce, quella dopo la &."""
    posizione = etichetta.find("&")
    return etichetta[posizione + 1].lower() if posizione >= 0 else None


class TestLettereDeiMenu:
    """Dalla 10.13.29 anche nel menu File ogni voce ha la sua lettera:
    Esporta partite pianificate, Elimina Torneo Attivo ed Esci avevano tutte
    e tre la E, e premendola non si sceglieva nessuna delle tre. La 10.13.5
    lo aveva fatto per il menu Visualizza."""

    def test_le_voci_del_menu_file(self, principale):
        etichette = [v.GetItemLabel() for v in principale.item_export_ics.GetMenu().GetMenuItems() if not v.IsSeparator()]
        assert [_lettera(e) for e in etichette] == ["n", "a", "p", "l", "c", "e"]
        assert principale.item_export_ics.GetItemLabel() == "Es&porta partite pianificate...\tCtrl+Shift+E"
        # Dalla 10.19.0 la voce che fa quello che fa CANC, con la L di prima.
        assert principale.item_canc.GetItemLabel() == "E&limina o annulla la voce scelta...\tCanc"

    def test_ogni_menu_ha_lettere_tutte_diverse(self, principale):
        barra = principale.GetMenuBar()
        titoli = [barra.GetMenuLabel(i) for i in range(barra.GetMenuCount())]
        assert len({_lettera(t) for t in titoli}) == len(titoli)
        for posizione, titolo in enumerate(titoli):
            voci = [v.GetItemLabel() for v in barra.GetMenu(posizione).GetMenuItems() if not v.IsSeparator()]
            lettere = [_lettera(v) for v in voci]
            assert None not in lettere, (titolo, voci)
            assert len(set(lettere)) == len(lettere), (titolo, voci)


class TestNomeDelTorneoNuovo:
    """Dalla 10.13.52 (issue 66) la procedura guidata di un torneo nuovo non
    accetta un nome il cui file, Tornello - <nome ripulito>.json, coincide
    con il database dei giocatori, con le impostazioni, con un altro file
    Tornello - *.json della cartella del programma o con un torneo della
    cartella del programma, in corso, in preparazione o concluso, senza
    badare alle maiuscole. Un messaggio dice con che cosa coincide, e la
    procedura resta dov'e'. Fino alla 10.13.51 il torneo nuovo sovrascriveva
    il file che trovava. Un nome che coincide soltanto con un torneo
    dell'archivio e' quello di una nuova edizione: si accetta dopo una
    domanda, con No come pulsante predefinito, che per lo stesso nome non si
    ripete fino alla fine della procedura (decisione di Gabriele del 4
    novembre 2026), tranne quando l'edizione archiviata ha la stessa data di
    inizio. I messaggi sono annotati, e la finestra del nome e quella
    dell'iscrizione sono finte."""

    @staticmethod
    def _scrivi(percorso, dati):
        import json

        os.makedirs(os.path.dirname(percorso), exist_ok=True)
        with open(percorso, "w", encoding="utf-8") as f:
            json.dump(dati, f)

    def _torneo_nella_cartella(self, nome, **altro):
        from config import user_data_path

        percorso = user_data_path(f"Tornello - {nome}.json")
        self._scrivi(percorso, dict({"name": nome.replace("_", " "), "players": [], "rounds": []}, **altro))
        return percorso

    def _torneo_in_archivio(self, nome):
        import gui.main_frame as mf

        percorso = os.path.join(mf.ARCHIVED_TOURNAMENTS_DIR, "2026", "06 Giugno", nome, f"Tornello - {nome}.json")
        self._scrivi(percorso, dict(_torneo_in_corso(nome.replace("_", " ")), concluded=True))
        return percorso

    def test_il_database_dei_giocatori(self):
        from gui.main_frame import coincidenza_del_nome

        assert coincidenza_del_nome("Players db") == ("come il database dei giocatori", True)
        assert coincidenza_del_nome("PLAYERS_DB").frase == "come il database dei giocatori"

    def test_le_impostazioni(self):
        from gui.main_frame import coincidenza_del_nome

        assert coincidenza_del_nome("settings") == ("come il file delle impostazioni del programma", True)

    def test_un_altro_file_del_programma(self):
        """Un file Tornello - *.json che non e' un torneo, o che non si
        legge, non si sovrascrive lo stesso."""
        from config import user_data_path
        from gui.main_frame import coincidenza_del_nome

        self._scrivi(user_data_path("Tornello - Appunti.json"), {"voci": [1, 2]})
        with open(user_data_path("Tornello - Rovinato.json"), "w", encoding="utf-8") as f:
            f.write("{ non e' json")
        atteso = ("come un altro file del programma, che c'è già nella sua cartella", True)
        assert coincidenza_del_nome("Appunti") == atteso
        assert coincidenza_del_nome("rovinato") == atteso

    def test_un_torneo_in_preparazione(self):
        """Il nome si confronta ripulito, come lo ripulisce il file."""
        from gui.main_frame import coincidenza_del_nome

        self._torneo_nella_cartella("Coppa_dAutunno")
        assert coincidenza_del_nome("coppa d'autunno") == ("come il file del torneo Coppa dAutunno, in preparazione nella cartella del programma", True)

    def test_un_torneo_in_corso(self):
        from gui.main_frame import coincidenza_del_nome

        self._torneo_nella_cartella("Alfa", rounds=[{"round": 1, "matches": []}])
        assert coincidenza_del_nome("ALFA") == ("come il file del torneo Alfa, in corso nella cartella del programma", True)

    def test_un_torneo_concluso_nella_cartella(self):
        from gui.main_frame import coincidenza_del_nome

        self._torneo_nella_cartella("Gamma", rounds=[{"round": 1, "matches": []}], concluded=True)
        assert coincidenza_del_nome("Gamma") == ("come il file del torneo Gamma, concluso, nella cartella del programma", True)

    def test_un_torneo_in_archivio(self):
        """Un torneo dell'archivio non e' una coincidenza da rifiutare, ma
        un'edizione, che edizioni_nell_archivio trova con i suoi dati."""
        from gui.main_frame import coincidenza_del_nome, edizioni_nell_archivio

        percorso = self._torneo_in_archivio("Primavera_2")
        assert coincidenza_del_nome("primavera 2") is None
        edizioni = edizioni_nell_archivio("primavera 2")
        assert [(p, d["name"], d["start_date"]) for p, d in edizioni] == [(percorso, "Primavera 2", "2026-09-01")]

    def test_le_edizioni_in_ordine_d_anno_e_quella_che_non_si_legge(self):
        """Le edizioni vengono in ordine di cartella, cioe' d'anno e di mese;
        un file che non si legge e' un'edizione senza dati."""
        import gui.main_frame as mf

        seconda = self._torneo_in_archivio("Primavera_2")
        prima = os.path.join(mf.ARCHIVED_TOURNAMENTS_DIR, "2025", "06 Giugno", "Primavera_2", "Tornello - Primavera_2.json")
        os.makedirs(os.path.dirname(prima))
        with open(prima, "w", encoding="utf-8") as f:
            f.write("{ non e' json")
        assert [(p, d is None) for p, d in mf.edizioni_nell_archivio("Primavera 2")] == [(prima, True), (seconda, False)]

    def test_un_nome_libero(self):
        from gui.main_frame import coincidenza_del_nome, edizioni_nell_archivio

        self._torneo_nella_cartella("Alfa")
        self._torneo_in_archivio("Primavera_2")
        for nome in ("Alfa 2", "Primavera", "Players", "Settings 2026"):
            assert coincidenza_del_nome(nome) is None, nome
            assert edizioni_nell_archivio(nome) == [], nome

    @staticmethod
    def _nome_scritto(principale, monkeypatch, nome):
        """Il nome scritto nella finestra del nome della procedura guidata,
        e confermato con OK."""
        import wx

        class NomeFinto:
            def __init__(self, *a, **k):
                pass

            def ShowModal(self):
                return wx.ID_OK

            def GetValue(self):
                return nome

            def Destroy(self):
                pass

        monkeypatch.setattr(wx, "TextEntryDialog", NomeFinto)
        principale.on_wizard_field_activated(principale.tree_name, "name")

    def test_la_procedura_rifiuta_il_nome_e_resta(self, principale, suoni, monkeypatch):
        finestre = TestDatabaseCheNonSiLeggeNelleFinestre._dialoghi_finti(monkeypatch)
        self._torneo_nella_cartella("Alfa", rounds=[{"round": 1, "matches": []}])
        principale.start_new_tournament_wizard()
        self._nome_scritto(principale, monkeypatch, "Beta")
        assert principale.creation_data["name"] == "Beta"
        suoni.clear()

        self._nome_scritto(principale, monkeypatch, "alfa")

        assert principale.creation_mode
        assert principale.creation_data["name"] == "Beta"
        assert principale.tree_ctrl.GetItemText(principale.tree_name) == "Nome torneo *: Beta"
        assert suoni == ["apertura", "errore"]
        assert finestre == [
            (
                "Nome del torneo già in uso",
                "Il nome alfa non si può usare: il file del torneo si chiamerebbe Tornello - alfa.json, come il file del torneo Alfa, in corso nella cartella del programma.\n"
                "Nel nome del file gli spazi diventano trattini bassi, i simboli spariscono, e le maiuscole e le minuscole non fanno differenza. Scegli un altro nome per il torneo.",
            )
        ]

    def test_l_iscrizione_non_si_apre(self, principale, suoni, monkeypatch):
        """Un file nato dopo che il nome e' stato scritto ferma la procedura
        prima dell'iscrizione dei giocatori, che andrebbe persa."""
        import gui.dialogs as finestre_di_dialogo

        aperte = []
        monkeypatch.setattr(finestre_di_dialogo, "PlayerEnrollmentDialog", lambda *a, **k: aperte.append(True))
        finestre = TestDatabaseCheNonSiLeggeNelleFinestre._dialoghi_finti(monkeypatch)
        principale.start_new_tournament_wizard()
        self._nome_scritto(principale, monkeypatch, "Players DB")
        assert principale.creation_data["name"] == ""
        principale.creation_data["name"] = "Players DB"
        finestre.clear()

        principale.on_wizard_next()

        assert aperte == []
        assert [t for t, _m in finestre] == ["Nome del torneo già in uso"]
        assert "come il database dei giocatori" in finestre[0][1]
        assert principale.creation_mode

    def test_il_torneo_che_c_era_non_si_sovrascrive(self, principale, suoni, monkeypatch):
        """L'ultima guardia, in create_tournament_from_wizard: il file del
        torneo che c'era, in corso nella cartella del programma, resta
        com'e', e il torneo nuovo non nasce."""
        finestre = TestDatabaseCheNonSiLeggeNelleFinestre._dialoghi_finti(monkeypatch)
        percorso = self._torneo_nella_cartella("Primavera_2", rounds=[{"round": 1, "matches": []}])
        with open(percorso, "rb") as f:
            prima = f.read()
        principale.start_new_tournament_wizard()
        principale.creation_data["name"] = "Primavera 2"

        principale.create_tournament_from_wizard(self._iscritti())

        with open(percorso, "rb") as f:
            assert f.read() == prima
        assert principale.creation_mode
        assert principale.current_tournament is None
        assert [t for t, _m in finestre] == ["Nome del torneo già in uso"]

    @staticmethod
    def _iscritti():
        return [{"id": codice, "first_name": nome, "last_name": cognome, "current_elo": 1500} for codice, cognome, nome in GIOCATORI_DEI_TORNEI]

    @staticmethod
    def _domande(monkeypatch, risposte=()):
        """Le finestre di messaggio della finestra principale annotate, con
        titolo, testo, se sono domande e se il loro pulsante predefinito e'
        No. Alle domande rispondono, una dopo l'altra, le risposte, e finite
        quelle il Si'."""
        import wx

        import gui.main_frame as mf

        finestre = []
        in_coda = list(risposte)

        class DialogoFinto:
            def __init__(self, genitore, titolo, messaggio, style=wx.OK, settings=None, no_predefinito=False):
                self.domanda = bool(style & wx.YES_NO)
                finestre.append(SimpleNamespace(titolo=titolo, testo=messaggio, domanda=self.domanda, no_predefinito=no_predefinito))

            def ShowModal(self):
                if not self.domanda:
                    return wx.ID_OK
                return in_coda.pop(0) if in_coda else wx.ID_YES

            def Destroy(self):
                pass

        monkeypatch.setattr(mf, "AccessibleMsgDialog", DialogoFinto)
        return finestre

    @staticmethod
    def _domanda_attesa(scritto, file, edizioni):
        """Il testo della domanda sulla nuova edizione, con le edizioni
        archiviate come coppie di nome e cartella."""
        elenco = "; ".join(f"{torneo}, nella cartella {cartella}" for torneo, cartella in edizioni)
        quante = "un torneo concluso e archiviato" if len(edizioni) == 1 else f"{len(edizioni)} tornei conclusi e archiviati"
        return (
            f"Il file del torneo {scritto} si chiamerebbe {file}, come quello di {quante} fra i Tornei Conclusi: {elenco}.\n"
            "Se il torneo nuovo è una nuova edizione dello stesso torneo, il nome si può usare: le edizioni restano distinte, nell'archivio e nello storico dei giocatori, perché hanno date di inizio diverse.\n\n"
            f"Vuoi creare una nuova edizione con il nome {scritto}? Il pulsante predefinito è No."
        )

    def test_con_no_alla_domanda_il_nome_resta_quello_di_prima(self, principale, suoni, monkeypatch):
        """Un nome che coincide soltanto con un torneo dell'archivio: la
        domanda dice quale e dove, con No come pulsante predefinito, e con No
        il nome resta quello di prima, come dopo un rifiuto, ma senza il
        suono dell'errore."""
        import wx

        from gui.main_frame import NUOVA_EDIZIONE_CONFERMATA

        finestre = self._domande(monkeypatch, [wx.ID_NO])
        self._torneo_in_archivio("Primavera_2")
        principale.start_new_tournament_wizard()
        self._nome_scritto(principale, monkeypatch, "Beta")
        suoni.clear()

        self._nome_scritto(principale, monkeypatch, "primavera 2")

        assert principale.creation_data["name"] == "Beta"
        assert principale.tree_ctrl.GetItemText(principale.tree_name) == "Nome torneo *: Beta"
        assert NUOVA_EDIZIONE_CONFERMATA not in principale.creation_data
        assert suoni == ["apertura"]
        cartella = os.path.join("Closed Tournaments", "2026", "06 Giugno", "Primavera_2")
        assert [(f.titolo, f.testo, f.domanda, f.no_predefinito) for f in finestre] == [
            (
                "Nuova edizione di un torneo concluso",
                self._domanda_attesa("primavera 2", "Tornello - primavera_2.json", [("Primavera 2", cartella)]),
                True,
                True,
            )
        ]

    def test_con_si_il_nome_passa_e_la_domanda_non_si_ripete(self, principale, suoni, monkeypatch):
        """Con Si' il nome si accetta, e ne' l'iscrizione ne' la guardia
        finale chiedono di nuovo: il torneo nuovo nasce nella cartella del
        programma, e il torneo dell'archivio resta com'era."""
        import wx

        import gui.dialogs as finestre_di_dialogo
        from config import user_data_path

        class IscrizioneFinta:
            def __init__(self, *a, **k):
                aperte.append(True)

            def ShowModal(self):
                return wx.ID_CANCEL

            def Destroy(self):
                pass

        aperte = []
        monkeypatch.setattr(finestre_di_dialogo, "PlayerEnrollmentDialog", IscrizioneFinta)
        finestre = self._domande(monkeypatch)
        archiviato = self._torneo_in_archivio("Primavera_2")
        with open(archiviato, "rb") as f:
            prima = f.read()
        principale.start_new_tournament_wizard()
        suoni.clear()

        self._nome_scritto(principale, monkeypatch, "Primavera 2")

        assert principale.creation_data["name"] == "Primavera 2"
        assert principale.tree_ctrl.GetItemText(principale.tree_name) == "Nome torneo *: Primavera 2"
        assert suoni == ["apertura", "conferma"]
        assert [f.titolo for f in finestre] == ["Nuova edizione di un torneo concluso"]

        principale.on_wizard_next()
        principale.create_tournament_from_wizard(self._iscritti())

        assert aperte == [True]
        assert len(finestre) == 1
        nuovo = user_data_path("Tornello - Primavera_2.json")
        assert principale.active_filename == nuovo
        assert principale.current_tournament["name"] == "Primavera 2"
        with open(archiviato, "rb") as f:
            assert f.read() == prima

    def test_un_nome_cambiato_si_controlla_da_capo(self, principale, suoni, monkeypatch):
        """Lo stesso nome scritto di nuovo non richiede la domanda; un altro
        nome si', anche quando si torna a quello di prima."""
        finestre = self._domande(monkeypatch)
        self._torneo_in_archivio("Primavera_2")
        principale.start_new_tournament_wizard()

        for nome in ("Primavera 2", "Primavera 2", "Beta", "Primavera 2"):
            self._nome_scritto(principale, monkeypatch, nome)
            assert principale.creation_data["name"] == nome

        assert [f.titolo for f in finestre] == ["Nuova edizione di un torneo concluso"] * 2

    def test_piu_edizioni_nell_archivio(self, principale, suoni, monkeypatch):
        """Con due edizioni archiviate la domanda le dice tutte e due, in
        ordine d'anno."""
        import gui.main_frame as mf

        finestre = self._domande(monkeypatch)
        self._torneo_in_archivio("Primavera_2")
        prima = os.path.join(mf.ARCHIVED_TOURNAMENTS_DIR, "2025", "06 Giugno", "Primavera_2", "Tornello - Primavera_2.json")
        self._scrivi(prima, dict(_torneo_in_corso("Primavera 2"), start_date="2025-06-01", concluded=True))
        principale.start_new_tournament_wizard()

        self._nome_scritto(principale, monkeypatch, "Primavera 2")

        edizioni = [("Primavera 2", os.path.join("Closed Tournaments", anno, "06 Giugno", "Primavera_2")) for anno in ("2025", "2026")]
        assert [f.testo for f in finestre] == [self._domanda_attesa("Primavera 2", "Tornello - Primavera_2.json", edizioni)]

    def test_con_la_stessa_data_di_inizio_il_nome_non_passa(self, principale, suoni, monkeypatch):
        """Un'edizione archiviata con la data di inizio del torneo nuovo non
        si distinguerebbe da lui: il nome si rifiuta, senza domanda, anche
        dopo il Si' a una data diversa, quando la data cambia prima
        dell'iscrizione."""
        import gui.dialogs as finestre_di_dialogo
        from utils import format_date_locale

        aperte = []
        monkeypatch.setattr(finestre_di_dialogo, "PlayerEnrollmentDialog", lambda *a, **k: aperte.append(True))
        finestre = self._domande(monkeypatch)
        self._torneo_in_archivio("Primavera_2")
        principale.start_new_tournament_wizard()
        principale.creation_data["start_date"] = "2026-09-01"
        suoni.clear()

        self._nome_scritto(principale, monkeypatch, "Primavera 2")

        assert principale.creation_data["name"] == ""
        assert suoni == ["apertura", "errore"]
        cartella = os.path.join("Closed Tournaments", "2026", "06 Giugno", "Primavera_2")
        rifiuto = (
            "Nome del torneo già in uso",
            f"Il nome Primavera 2 non si può usare con la data di inizio {format_date_locale('2026-09-01')}: il file del torneo si chiamerebbe Tornello - Primavera_2.json, come quello del torneo Primavera 2, concluso e archiviato nella cartella {cartella}, che ha la stessa data di inizio.\n"
            "Le edizioni di un torneo con lo stesso nome si distinguono, nell'archivio e nello storico dei giocatori, dalla data di inizio: con la stessa data la finalizzazione le confonderebbe. Cambia la data di inizio, oppure scegli un altro nome per il torneo.",
            False,
        )
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [rifiuto]

        principale.creation_data["start_date"] = "2026-11-02"
        self._nome_scritto(principale, monkeypatch, "Primavera 2")
        assert principale.creation_data["name"] == "Primavera 2"
        principale.creation_data["start_date"] = "2026-09-01"
        finestre.clear()

        principale.on_wizard_next()

        assert aperte == []
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [rifiuto]

    def test_un_edizione_archiviata_dopo_il_nome_chiede_alla_guardia(self, principale, suoni, monkeypatch):
        """Il torneo dell'archivio arrivato dopo che il nome e' stato
        scritto: chiedono l'iscrizione e la guardia finale, e con No la
        procedura resta dov'e'; con Si' il torneo nasce."""
        import wx

        import gui.dialogs as finestre_di_dialogo
        from config import user_data_path

        aperte = []
        monkeypatch.setattr(finestre_di_dialogo, "PlayerEnrollmentDialog", lambda *a, **k: aperte.append(True))
        finestre = self._domande(monkeypatch, [wx.ID_NO, wx.ID_NO])
        principale.start_new_tournament_wizard()
        self._nome_scritto(principale, monkeypatch, "Primavera 2")
        assert finestre == []
        self._torneo_in_archivio("Primavera_2")

        principale.on_wizard_next()
        principale.create_tournament_from_wizard(self._iscritti())

        assert aperte == []
        assert not os.path.exists(user_data_path("Tornello - Primavera_2.json"))
        assert principale.creation_mode
        assert [f.titolo for f in finestre] == ["Nuova edizione di un torneo concluso"] * 2

        principale.create_tournament_from_wizard(self._iscritti())

        assert os.path.exists(user_data_path("Tornello - Primavera_2.json"))
        assert len(finestre) == 3

    @staticmethod
    def _gioca_il_turno(principale):
        """Il turno 1 del torneo aperto, giocato senza il motore: Bianchi
        batte Verdi, Neri e Russo pattano. Il torneo si salva."""
        torneo = principale.current_tournament
        giocatori = {p["id"]: p for p in torneo["players"]}
        partite = []
        for numero, (bianco, nero, risultato, punti) in enumerate((("BIA", "VER", "1-0", 1.0), ("NER", "RUS", "1/2-1/2", 0.5)), 1):
            partite.append({"id": numero, "round": 1, "white_player_id": bianco, "black_player_id": nero, "result": risultato, "is_scheduled": False})
            for io, avversario, colore, fatti in ((bianco, nero, "white", punti), (nero, bianco, "black", 1.0 - punti)):
                giocatori[io]["results_history"] = [{"round": 1, "opponent_id": avversario, "color": colore, "result": risultato, "score": fatti}]
                giocatori[io]["points"] = fatti
                giocatori[io]["opponents"] = [avversario]
        torneo["rounds"] = [{"round": 1, "matches": partite}]
        torneo["players_dict"] = giocatori
        principale._save_state()

    def test_la_nuova_edizione_si_finalizza_accanto_alla_prima(self, principale, suoni, monkeypatch):
        """La strada intera di una nuova edizione. La prima edizione di
        Primavera 2 nasce dalla procedura guidata, si gioca e si finalizza;
        la seconda nasce con lo stesso nome, dopo il Si' alla domanda, nel
        suo file della cartella del programma, e si finalizza anche lei.
        Tutte e due finiscono a ottobre 2026: la seconda va in archivio nella
        cartella con la sua data di inizio, la cartella della prima resta
        com'era, file per file, e lo storico di ogni giocatore ha le due
        edizioni, distinte dalla data di inizio."""
        import json
        from datetime import datetime

        import wx

        import ui
        from config import PLAYER_DB_FILE, user_data_path
        from utils import cartella_per_data

        messaggi = []
        monkeypatch.setattr(ui, "play_sound", lambda *a, **k: None)
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: messaggi.append(a))
        schede = [
            {"id": codice, "first_name": nome, "last_name": cognome, "current_elo": 1500.0, "initial_elo": 1500.0, "games_played": 10, "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0}, "tournaments_played": []}
            for codice, cognome, nome in GIOCATORI_DEI_TORNEI
        ]
        self._scrivi(PLAYER_DB_FILE, {"schema_version": 2, "players": schede})
        finestre = self._domande(monkeypatch)
        file_del_torneo = user_data_path("Tornello - Primavera_2.json")

        def edizione(inizio, fine):
            principale.start_new_tournament_wizard()
            principale.creation_data.update(start_date=inizio, end_date=fine, rounds=1)
            self._nome_scritto(principale, monkeypatch, "Primavera 2")
            assert principale.creation_data["name"] == "Primavera 2"
            principale.create_tournament_from_wizard(self._iscritti())
            assert principale.active_filename == file_del_torneo
            self._gioca_il_turno(principale)
            principale.on_finalize_tournament(None)
            assert principale.current_tournament is None
            assert not os.path.exists(file_del_torneo)

        def contenuto(cartella):
            letti = {}
            for nome in sorted(os.listdir(cartella)):
                with open(os.path.join(cartella, nome), "rb") as f:
                    letti[nome] = f.read()
            return letti

        mese = cartella_per_data(ui.ARCHIVED_TOURNAMENTS_DIR, datetime(2026, 10, 1), crea=False)
        cartella_prima = os.path.join(mese, "Primavera_2")
        edizione("2026-10-01", "2026-10-10")
        assert [f.titolo for f in finestre if f.domanda] == ["Finalizza Torneo"]
        prima = contenuto(cartella_prima)
        assert "Tornello - Primavera_2.json" in prima

        edizione("2026-10-15", "2026-10-25")

        assert [f.titolo for f in finestre if f.domanda] == ["Finalizza Torneo", "Nuova edizione di un torneo concluso", "Finalizza Torneo"]
        assert contenuto(cartella_prima) == prima
        cartella_seconda = f"{cartella_prima}_2026-10-15"
        with open(os.path.join(cartella_seconda, "Tornello - Primavera_2.json"), encoding="utf-8") as f:
            seconda = json.load(f)
        assert (seconda["start_date"], seconda["concluded"]) == ("2026-10-15", True)
        assert any(f.titolo == "Avvisi della finalizzazione" and cartella_seconda in f.testo for f in finestre)
        with open(PLAYER_DB_FILE, encoding="utf-8") as f:
            database = {p["id"]: p for p in json.load(f)["players"]}
        for codice, _cognome, _nome in GIOCATORI_DEI_TORNEI:
            assert [v["date_started"] for v in database[codice]["tournaments_played"]] == ["2026-10-01", "2026-10-15"], codice
            assert database[codice]["games_played"] == 12, codice
        assert messaggi == []
        nell_albero = TestAlberoETorneoAttivo._tutti_i_file(principale)
        for cartella in (cartella_prima, cartella_seconda):
            assert os.path.normcase(os.path.join(cartella, "Tornello - Primavera_2.json")) in nell_albero

    def test_con_un_nome_libero_il_torneo_nasce(self, principale, suoni, monkeypatch):
        """La strada di sempre: con il nome libero il torneo nasce, accanto a
        quello che c'era."""
        from config import user_data_path

        finestre = TestDatabaseCheNonSiLeggeNelleFinestre._dialoghi_finti(monkeypatch)
        self._torneo_nella_cartella("Alfa")
        principale.start_new_tournament_wizard()
        self._nome_scritto(principale, monkeypatch, "Alfa 2")
        assert principale.creation_data["name"] == "Alfa 2"
        iscritti = [{"id": codice, "first_name": nome, "last_name": cognome, "current_elo": 1500} for codice, cognome, nome in GIOCATORI_DEI_TORNEI]

        principale.create_tournament_from_wizard(iscritti)

        assert os.path.exists(user_data_path("Tornello - Alfa_2.json"))
        assert principale.current_tournament["name"] == "Alfa 2"
        assert finestre == []


def _raccolta_come_la_scrive_la_finestra(*pgn):
    """Il contenuto della raccolta delle partite con questi PGN, come lo
    scrive la finestra: separati da una riga vuota, con l'a capo in fondo,
    in UTF-8 e con l'a capo del sistema."""
    return ("\n\n".join(p.strip() for p in pgn) + "\n").replace("\n", os.linesep).encode("utf-8")


class TestRaccoltaDellePartiteDelleEdizioni:
    """Dalla 10.19.7 (issue 66, decisione di Gabriele del 4 novembre 2026)
    la finalizzazione porta in archivio la raccolta delle partite in PGN,
    con i report, e il primo salvataggio di un torneo nuovo non distrugge la
    raccolta di un altro torneo che trova al suo posto: quella di
    un'edizione archiviata va nella sua cartella d'archivio, con una copia
    riletta, e l'originale nel cestino; un'altra va nel cestino; se il
    cestino non la prende, il torneo non nasce. Fino alla 10.19.5 la
    raccolta restava nella cartella di salvataggio, e il primo salvataggio
    della nuova edizione la cancellava per sempre. Il cestino e le finestre
    di messaggio sono finti."""

    @staticmethod
    def _cestino(monkeypatch, cartella, prende=True):
        """Al posto di delete_file_to_trash: sposta i file in cartella e li
        annota; con prende falso li lascia dove sono, come un disco senza
        cestino."""
        import shutil

        import utils

        ricevuti = []

        def cestino(percorso, finestra=None):
            if not prende:
                return False
            os.makedirs(cartella, exist_ok=True)
            shutil.move(percorso, os.path.join(cartella, f"{len(ricevuti)}_{os.path.basename(percorso)}"))
            ricevuti.append(os.path.normcase(os.path.abspath(percorso)))
            return True

        monkeypatch.setattr(utils, "delete_file_to_trash", cestino)
        return ricevuti

    @staticmethod
    def _database_dei_giocatori():
        """Il database con le schede dei giocatori dei tornei delle prove."""
        from config import PLAYER_DB_FILE

        schede = [
            {"id": codice, "first_name": nome, "last_name": cognome, "current_elo": 1500.0, "initial_elo": 1500.0, "games_played": 10, "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0}, "tournaments_played": []}
            for codice, cognome, nome in GIOCATORI_DEI_TORNEI
        ]
        TestNomeDelTorneoNuovo._scrivi(PLAYER_DB_FILE, {"schema_version": 2, "players": schede})

    @staticmethod
    def _nuova_edizione(principale, monkeypatch, inizio, fine, nome="Primavera 2"):
        """Il torneo nome dalla procedura guidata, con un turno, le due date
        e gli iscritti dei tornei delle prove, fino alla sua nascita."""
        principale.start_new_tournament_wizard()
        principale.creation_data.update(start_date=inizio, end_date=fine, rounds=1)
        TestNomeDelTorneoNuovo._nome_scritto(principale, monkeypatch, nome)
        assert principale.creation_data["name"] == nome
        principale.create_tournament_from_wizard(TestNomeDelTorneoNuovo._iscritti())

    def test_la_finalizzazione_porta_la_raccolta_in_archivio(self, principale, suoni, monkeypatch):
        """La strada intera, sulla finestra principale vera, mai mostrata:
        Primavera 2 nasce dalla procedura guidata, una partita ha il PGN, il
        salvataggio scrive la raccolta nella cartella del programma, e
        on_finalize_tournament la porta nella cartella d'archivio. La nuova
        edizione con lo stesso nome nasce senza trovarla e senza messaggi
        sulla raccolta, e quella dell'archivio resta com'era."""
        from datetime import datetime

        import wx

        import ui
        from config import user_data_path
        from utils import cartella_per_data

        monkeypatch.setattr(ui, "play_sound", lambda *a, **k: None)
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: pytest.fail(f"MessageBox: {a}"))
        self._database_dei_giocatori()
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        raccolta = user_data_path("Primavera_2 - raccolta partite.pgn")

        self._nuova_edizione(principale, monkeypatch, "2026-10-01", "2026-10-10")
        TestNomeDelTorneoNuovo._gioca_il_turno(principale)
        principale.current_tournament["rounds"][0]["matches"][0]["pgn"] = PGN_VALIDO
        principale._save_state()
        contenuto = _raccolta_come_la_scrive_la_finestra(PGN_VALIDO)
        with open(raccolta, "rb") as f:
            assert f.read() == contenuto
        principale.on_finalize_tournament(None)

        assert principale.current_tournament is None
        mese = cartella_per_data(ui.ARCHIVED_TOURNAMENTS_DIR, datetime(2026, 10, 1), crea=False)
        in_archivio = os.path.join(mese, "Primavera_2", "Primavera_2 - raccolta partite.pgn")
        with open(in_archivio, "rb") as f:
            assert f.read() == contenuto
        assert not os.path.exists(raccolta)

        self._nuova_edizione(principale, monkeypatch, "2026-10-15", "2026-10-25")

        assert principale.active_filename == user_data_path("Tornello - Primavera_2.json")
        with open(in_archivio, "rb") as f:
            assert f.read() == contenuto
        assert [f.titolo for f in finestre if f.domanda] == ["Finalizza Torneo", "Nuova edizione di un torneo concluso"]
        assert not any(f.titolo == "Raccolta delle partite di un altro torneo" for f in finestre)

    def test_la_raccolta_lasciata_da_un_edizione_archiviata_va_nella_sua_cartella(self, principale, suoni, monkeypatch, tmp_path):
        """Primavera 2, archiviata prima della 10.19.7, ha lasciato la sua
        raccolta nella cartella del programma. La nuova edizione la trova,
        identica a quella che scriverebbe il file archiviato: va nella sua
        cartella d'archivio, con una copia riletta, l'originale va nel
        cestino, un messaggio lo dice, e il torneo nuovo nasce."""
        import gui.main_frame as mf
        from config import user_data_path

        archiviato = os.path.join(mf.ARCHIVED_TOURNAMENTS_DIR, "2026", "06 Giugno", "Primavera_2", "Tornello - Primavera_2.json")
        dati = dict(_torneo_in_corso("Primavera 2", finito=True), concluded=True)
        dati["rounds"][0]["matches"][0]["pgn"] = PGN_VALIDO
        TestNomeDelTorneoNuovo._scrivi(archiviato, dati)
        lasciata = user_data_path("Primavera_2 - raccolta partite.pgn")
        contenuto = _raccolta_come_la_scrive_la_finestra(PGN_VALIDO)
        with open(lasciata, "wb") as f:
            f.write(contenuto)
        ricevuti = self._cestino(monkeypatch, str(tmp_path / "cestino"))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()

        self._nuova_edizione(principale, monkeypatch, "2026-11-02", "2026-11-20")

        assert principale.active_filename == user_data_path("Tornello - Primavera_2.json")
        with open(os.path.join(os.path.dirname(archiviato), "Primavera_2 - raccolta partite.pgn"), "rb") as f:
            assert f.read() == contenuto
        assert ricevuti == [os.path.normcase(os.path.abspath(lasciata))]
        assert not os.path.exists(lasciata)
        assert "errore" not in suoni
        cartella = os.path.abspath(user_data_path(""))
        archivio = os.path.join("Closed Tournaments", "2026", "06 Giugno", "Primavera_2")
        assert [(f.titolo, f.testo) for f in finestre if not f.domanda] == [
            (
                "Raccolta delle partite di un altro torneo",
                f"Nella cartella {cartella} c'era la raccolta delle partite Primavera_2 - raccolta partite.pgn del torneo Primavera 2, concluso e archiviato nella cartella {archivio}: il torneo Primavera 2 l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
                f"Una copia identica, riletta, adesso è nella cartella d'archivio di quel torneo, e quella della cartella {cartella} è andata nel cestino di Windows.",
            )
        ]

    @pytest.mark.parametrize("prende", [True, False])
    def test_una_raccolta_di_nessuna_edizione_archiviata(self, principale, suoni, monkeypatch, tmp_path, prende):
        """Una raccolta con il nome di quella del torneo nuovo, che nessuna
        edizione archiviata scriverebbe, per esempio di un torneo eliminato,
        va nel cestino, e il torneo nasce. Se il cestino non la prende si
        sente l'errore, un messaggio lo dice, la raccolta resta com'era e il
        torneo non nasce: la procedura guidata resta dov'e'."""
        from config import user_data_path

        lasciata = user_data_path("Gamma - raccolta partite.pgn")
        with open(lasciata, "wb") as f:
            f.write(b"partite di un torneo eliminato")
        ricevuti = self._cestino(monkeypatch, str(tmp_path / "cestino"), prende)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()

        self._nuova_edizione(principale, monkeypatch, "2026-11-02", "2026-11-20", nome="Gamma")

        cartella = os.path.abspath(user_data_path(""))
        nuovo = user_data_path("Tornello - Gamma.json")
        if prende:
            assert ricevuti == [os.path.normcase(os.path.abspath(lasciata))]
            assert principale.active_filename == nuovo
            assert "errore" not in suoni
            assert [(f.titolo, f.testo) for f in finestre] == [
                (
                    "Raccolta delle partite di un altro torneo",
                    f"Nella cartella {cartella} c'era la raccolta delle partite Gamma - raccolta partite.pgn, che non è del torneo Gamma: il torneo l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
                    "È andata nel cestino di Windows, da dove si può recuperare.",
                )
            ]
        else:
            with open(lasciata, "rb") as f:
                assert f.read() == b"partite di un torneo eliminato"
            assert not os.path.exists(nuovo)
            assert principale.creation_mode
            assert principale.current_tournament is None
            assert principale.active_filename is None
            assert "errore" in suoni
            assert [(f.titolo, f.testo) for f in finestre] == [
                (
                    "Raccolta delle partite di un altro torneo",
                    f"Nella cartella {cartella} c'è la raccolta delle partite Gamma - raccolta partite.pgn, che non è del torneo Gamma: il torneo la sostituirebbe con la sua raccolta, o la cancellerebbe.\n"
                    "Non si è potuta mettere in salvo, né nella cartella d'archivio di un torneo concluso con lo stesso nome né nel cestino di Windows, per esempio perché quel disco non ha il cestino.\n"
                    "Il torneo non è stato creato: sposta quel file in un'altra cartella, poi riprova.",
                )
            ]


    @pytest.mark.parametrize("prende", [True, False])
    def test_la_raccolta_si_mette_in_salvo_prima_dell_iscrizione(self, principale, suoni, monkeypatch, tmp_path, prende):
        """La guardia sta anche prima dell'iscrizione dei giocatori, come
        quella del nome: la raccolta va nel cestino prima che la finestra di
        iscrizione si apra, e se il cestino non la prende la finestra non si
        apre, e l'iscrizione non va persa."""
        import wx

        import gui.dialogs as finestre_di_dialogo
        from config import user_data_path

        class IscrizioneFinta:
            def __init__(self, *a, **k):
                aperte.append(os.path.exists(lasciata))

            def ShowModal(self):
                return wx.ID_CANCEL

            def Destroy(self):
                pass

        aperte = []
        monkeypatch.setattr(finestre_di_dialogo, "PlayerEnrollmentDialog", IscrizioneFinta)
        lasciata = user_data_path("Gamma - raccolta partite.pgn")
        with open(lasciata, "wb") as f:
            f.write(b"partite di un torneo eliminato")
        ricevuti = self._cestino(monkeypatch, str(tmp_path / "cestino"), prende)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale.start_new_tournament_wizard()
        TestNomeDelTorneoNuovo._nome_scritto(principale, monkeypatch, "Gamma")
        suoni.clear()

        principale.on_wizard_next()

        assert principale.creation_mode
        assert [f.titolo for f in finestre] == ["Raccolta delle partite di un altro torneo"]
        if prende:
            # La finestra di iscrizione si apre con la raccolta gia' nel
            # cestino.
            assert aperte == [False]
            assert ricevuti == [os.path.normcase(os.path.abspath(lasciata))]
            assert suoni == ["conferma"]
        else:
            assert aperte == []
            with open(lasciata, "rb") as f:
                assert f.read() == b"partite di un torneo eliminato"
            assert suoni == ["errore"]


class TestRaccoltaAlSalvataggioNellaFinestra:
    """Correzione della revisione della 10.19.7 (issue 66): ogni salvataggio
    della finestra mette in salvo la raccolta di un'edizione archiviata che
    trova al posto di quella del torneo, prima di sostituirla o di
    cancellarla. Il caso e' quello di una nuova edizione nata in console,
    che non scrive la raccolta e non passa dalla procedura guidata: aperta
    nella finestra, il suo primo salvataggio cancellava per sempre con
    os.remove la raccolta lasciata da un'edizione archiviata prima della
    10.19.7, o la sostituiva con la sua. Ogni altra raccolta, come quella
    del torneo stesso dopo un PGN nuovo, si sostituisce come prima, senza
    messaggi. Il cestino e le finestre di messaggio sono finti."""

    PGN_NUOVO = '[Event "Nuova"]\n\n1. d4 d5 1/2-1/2'

    @staticmethod
    def _archiviata_con_la_raccolta_lasciata():
        """Primavera 2 archiviata, con un PGN, e la sua raccolta nella
        cartella del programma, come la lasciava la finalizzazione fino alla
        10.19.5. Restituisce il file archiviato, la raccolta e il suo
        contenuto."""
        import gui.main_frame as mf
        from config import user_data_path

        archiviato = os.path.join(mf.ARCHIVED_TOURNAMENTS_DIR, "2026", "06 Giugno", "Primavera_2", "Tornello - Primavera_2.json")
        dati = dict(_torneo_in_corso("Primavera 2", finito=True), concluded=True)
        dati["rounds"][0]["matches"][0]["pgn"] = PGN_VALIDO
        TestNomeDelTorneoNuovo._scrivi(archiviato, dati)
        lasciata = user_data_path("Primavera_2 - raccolta partite.pgn")
        contenuto = _raccolta_come_la_scrive_la_finestra(PGN_VALIDO)
        with open(lasciata, "wb") as f:
            f.write(contenuto)
        return archiviato, lasciata, contenuto

    @staticmethod
    def _nata_in_console(principale, con_pgn=False):
        """La nuova edizione di Primavera 2 come la scrive la console, con
        l'identificativo con l'ora, aperta nella finestra; con con_pgn la
        seconda partita ha un PGN, come dopo un Salva PGN nella finestra."""
        from config import user_data_path

        nuovo = _torneo_in_corso("Primavera 2")
        nuovo.update(tournament_id="Primavera_2_20261104120000", start_date="2026-11-02", end_date="2026-11-20")
        if con_pgn:
            nuovo["rounds"][0]["matches"][1]["pgn"] = TestRaccoltaAlSalvataggioNellaFinestra.PGN_NUOVO
        percorso = user_data_path("Tornello - Primavera_2.json")
        TestNomeDelTorneoNuovo._scrivi(percorso, nuovo)
        principale.load_tournament(percorso)
        assert principale.active_filename == percorso
        return percorso

    @staticmethod
    def _rimozioni(monkeypatch):
        """os.remove annotato: i file cancellati per sempre."""
        rimossi = []
        vero = os.remove

        def annota(percorso, *a, **k):
            rimossi.append(os.path.normcase(os.path.abspath(percorso)))
            return vero(percorso, *a, **k)

        monkeypatch.setattr(os, "remove", annota)
        return rimossi

    @pytest.mark.parametrize("con_pgn", [False, True], ids=["senza PGN", "con un PGN"])
    def test_la_raccolta_lasciata_va_nella_sua_cartella_d_archivio(self, principale, suoni, monkeypatch, tmp_path, con_pgn):
        from config import user_data_path

        archiviato, lasciata, contenuto = self._archiviata_con_la_raccolta_lasciata()
        self._nata_in_console(principale, con_pgn)
        ricevuti = TestRaccoltaDellePartiteDelleEdizioni._cestino(monkeypatch, str(tmp_path / "cestino"))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()
        rimossi = self._rimozioni(monkeypatch)

        principale._save_state()

        with open(os.path.join(os.path.dirname(archiviato), "Primavera_2 - raccolta partite.pgn"), "rb") as f:
            assert f.read() == contenuto
        assert ricevuti == [os.path.normcase(os.path.abspath(lasciata))]
        with open(tmp_path / "cestino" / "0_Primavera_2 - raccolta partite.pgn", "rb") as f:
            assert f.read() == contenuto
        assert os.path.normcase(os.path.abspath(lasciata)) not in rimossi
        if con_pgn:
            with open(lasciata, "rb") as f:
                assert f.read() == _raccolta_come_la_scrive_la_finestra(self.PGN_NUOVO)
        else:
            assert not os.path.exists(lasciata)
        assert "errore" not in suoni
        cartella = os.path.abspath(user_data_path(""))
        archivio = os.path.join("Closed Tournaments", "2026", "06 Giugno", "Primavera_2")
        assert [(f.titolo, f.testo) for f in finestre] == [
            (
                "Raccolta delle partite di un altro torneo",
                f"Nella cartella {cartella} c'era la raccolta delle partite Primavera_2 - raccolta partite.pgn del torneo Primavera 2, concluso e archiviato nella cartella {archivio}: il torneo Primavera 2 l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
                f"Una copia identica, riletta, adesso è nella cartella d'archivio di quel torneo, e quella della cartella {cartella} è andata nel cestino di Windows.",
            )
        ]

        # Il salvataggio dopo non trova piu' niente da mettere in salvo.
        finestre.clear()
        principale._save_state()
        assert finestre == []
        assert len(ricevuti) == 1

    def test_se_non_si_mette_in_salvo_resta_e_la_raccolta_non_si_scrive(self, principale, suoni, monkeypatch, tmp_path):
        """La copia nella cartella d'archivio non riesce e il cestino non la
        prende: si sente l'errore, un messaggio lo dice, la raccolta lasciata
        resta com'era, e quella del torneo non si scrive. Il file del torneo
        si salva lo stesso."""
        import json

        import ui
        from config import user_data_path

        archiviato, lasciata, contenuto = self._archiviata_con_la_raccolta_lasciata()
        percorso = self._nata_in_console(principale, con_pgn=True)
        monkeypatch.setattr(ui, "_copia_verificata", lambda *a, **k: False)
        ricevuti = TestRaccoltaDellePartiteDelleEdizioni._cestino(monkeypatch, str(tmp_path / "cestino"), prende=False)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()
        principale.current_tournament["rounds"][0]["matches"][0]["result"] = "1-0"

        principale._save_state()

        with open(lasciata, "rb") as f:
            assert f.read() == contenuto
        assert not os.path.exists(os.path.join(os.path.dirname(archiviato), "Primavera_2 - raccolta partite.pgn"))
        assert ricevuti == []
        with open(percorso, encoding="utf-8") as f:
            assert json.load(f)["rounds"][0]["matches"][0]["result"] == "1-0"
        assert "errore" in suoni
        cartella = os.path.abspath(user_data_path(""))
        assert [(f.titolo, f.testo) for f in finestre] == [
            (
                "Raccolta delle partite di un altro torneo",
                f"Nella cartella {cartella} c'è la raccolta delle partite Primavera_2 - raccolta partite.pgn, che non è del torneo Primavera 2: il torneo la sostituirebbe con la sua raccolta, o la cancellerebbe.\n"
                "Non si è potuta mettere in salvo, né nella cartella d'archivio di un torneo concluso con lo stesso nome né nel cestino di Windows, per esempio perché quel disco non ha il cestino.\n"
                "La raccolta delle partite del torneo non è stata scritta: sposta quel file in un'altra cartella, e la scriverà il prossimo salvataggio.",
            )
        ]

    def test_la_raccolta_del_torneo_stesso_si_sostituisce_senza_messaggi(self, principale, suoni, monkeypatch, tmp_path):
        """Dopo un PGN nuovo la raccolta sul disco e' quella del torneo,
        scritta dal salvataggio di prima: si sostituisce, senza cestino e
        senza messaggi, anche con un'edizione archiviata con lo stesso nome.
        Una guardia: la mette in salvo soltanto la raccolta identica a
        quella di un'edizione archiviata."""
        from config import user_data_path

        self._archiviata_con_la_raccolta_lasciata()
        os.remove(user_data_path("Primavera_2 - raccolta partite.pgn"))
        self._nata_in_console(principale, con_pgn=True)
        ricevuti = TestRaccoltaDellePartiteDelleEdizioni._cestino(monkeypatch, str(tmp_path / "cestino"))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale._save_state()
        raccolta = user_data_path("Primavera_2 - raccolta partite.pgn")
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.PGN_NUOVO)

        principale.current_tournament["rounds"][0]["matches"][0]["pgn"] = PGN_VALIDO
        principale._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(PGN_VALIDO, self.PGN_NUOVO)
        assert ricevuti == []
        assert finestre == []

    def test_l_edizione_stessa_nell_archivio_non_conta(self, principale, suoni, monkeypatch, tmp_path):
        """Il torneo concluso e archiviato, aperto da una sua copia fuori
        dall'archivio, come quella che resta nella cartella di lavoro
        esterna: la raccolta accanto e' identica a quella dell'archivio,
        perche' e' sua. Dopo un PGN nuovo si sostituisce, senza cestino e
        senza messaggi: un'edizione archiviata con la stessa identita' e' il
        torneo stesso."""
        import json

        from config import user_data_path

        archiviato, lasciata, _contenuto = self._archiviata_con_la_raccolta_lasciata()
        copia = user_data_path("Tornello - Primavera_2.json")
        with open(archiviato, encoding="utf-8") as f:
            TestNomeDelTorneoNuovo._scrivi(copia, json.load(f))
        principale.load_tournament(copia)
        ricevuti = TestRaccoltaDellePartiteDelleEdizioni._cestino(monkeypatch, str(tmp_path / "cestino"))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale.current_tournament["rounds"][0]["matches"][1]["pgn"] = self.PGN_NUOVO

        principale._save_state()

        with open(lasciata, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(PGN_VALIDO, self.PGN_NUOVO)
        assert ricevuti == []
        assert finestre == []

    @pytest.mark.parametrize("con_pgn", [False, True], ids=["senza PGN", "con un PGN"])
    def test_se_il_cestino_non_la_prende_non_ci_riprova(self, principale, suoni, monkeypatch, tmp_path, con_pgn):
        """Revisione della 10.19.13. La copia va nella cartella d'archivio
        della prima edizione, e il cestino non prende l'originale, per
        esempio su un disco senza cestino: il messaggio lo dice una volta, e
        fino alla chiusura i salvataggi non ci riprovano. Senza PGN la
        raccolta resta dov'e', e il messaggio lo dice; con un PGN il torneo
        la sostituisce con la sua. Quando il torneo senza PGN ne ha uno, la
        raccolta si scrive, senza altri messaggi. Fino ad allora ogni
        salvataggio riprovava il cestino, e ripeteva il messaggio, che
        diceva anche al torneo senza PGN che l'avrebbe sostituita, o
        cancellata."""
        from config import user_data_path

        archiviato, lasciata, contenuto = self._archiviata_con_la_raccolta_lasciata()
        self._nata_in_console(principale, con_pgn)
        tentativi = TestRaccoltaSenzaPartiteNelCestino._cestino(monkeypatch, str(tmp_path / "cestino"), prende=False)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)

        for _volta in range(3):
            principale._save_state()

        with open(os.path.join(os.path.dirname(archiviato), "Primavera_2 - raccolta partite.pgn"), "rb") as f:
            assert f.read() == contenuto
        assert tentativi == [os.path.normcase(os.path.abspath(lasciata))]
        cartella = os.path.abspath(user_data_path(""))
        archivio = os.path.join("Closed Tournaments", "2026", "06 Giugno", "Primavera_2")
        prima_riga = (
            f"Nella cartella {cartella} c'era la raccolta delle partite Primavera_2 - raccolta partite.pgn del torneo Primavera 2, concluso e archiviato nella cartella {archivio}: il torneo Primavera 2 l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
            "Una copia identica, riletta, adesso è nella cartella d'archivio di quel torneo. "
        )
        if con_pgn:
            seconda_riga = f"Quella della cartella {cartella} non è andata nel cestino, e il torneo Primavera 2 la sostituirà con la sua raccolta."
        else:
            seconda_riga = f"Quella della cartella {cartella} non è andata nel cestino, e resta dov'è: la copia nella cartella d'archivio basta, e se vuoi la puoi cancellare tu."
        assert [(f.titolo, f.testo) for f in finestre] == [("Raccolta delle partite di un altro torneo", prima_riga + seconda_riga)]
        with open(lasciata, "rb") as f:
            assert f.read() == (_raccolta_come_la_scrive_la_finestra(self.PGN_NUOVO) if con_pgn else contenuto)

        principale.current_tournament["rounds"][0]["matches"][1]["pgn"] = self.PGN_NUOVO
        principale._save_state()

        with open(lasciata, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.PGN_NUOVO)
        assert len(tentativi) == 1
        assert len(finestre) == 1


class TestNomeEDataDiInizioDaDati:
    """Dalla 10.19.7 (issue 66, decisione di Gabriele del 4 novembre 2026)
    il nome e la data di inizio cambiati dai campi di Dati passano dagli
    stessi controlli della procedura guidata: un file del programma o un
    torneo della cartella del programma si rifiutano, un torneo
    dell'archivio chiede, con No predefinito, e la data di inizio di
    un'edizione archiviata con lo stesso nome si rifiuta. Con un rifiuto o
    con No il campo resta com'era, e il file del torneo pure; il file del
    torneo aperto non conta. Fino alla 10.19.5 Dati non controllava niente.
    Le finestre del campo e dei messaggi sono finte."""

    @staticmethod
    def _apri(principale, nome, **altro):
        """Il torneo nome in corso nella cartella del programma, dal 2 al 20
        novembre 2026 se altro non dice altro, aperto nella finestra."""
        from config import user_data_path

        percorso = user_data_path(f"Tornello - {nome.replace(' ', '_')}.json")
        dati = _torneo_in_corso(nome)
        dati.update(start_date="2026-11-02", end_date="2026-11-20")
        dati.update(altro)
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        principale.load_tournament(percorso)
        assert principale.current_tournament["name"] == nome
        return percorso

    @staticmethod
    def _campo(principale, monkeypatch, percorso, campo, valore):
        """Il campo di Dati, con valore scritto nella sua finestra e
        confermato con OK. Restituisce la voce dell'albero."""
        import wx

        class CampoFinto:
            def __init__(self, *a, **k):
                pass

            def ShowModal(self):
                return wx.ID_OK

            def GetValue(self):
                return valore

            def Destroy(self):
                pass

        monkeypatch.setattr(wx, "TextEntryDialog", CampoFinto)
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_data", "filepath": percorso, "field_active": campo})
        assert voce and voce.IsOk(), campo
        principale.on_active_field_activated(voce, campo)
        return voce

    @staticmethod
    def _nel_file(percorso):
        import json

        with open(percorso, encoding="utf-8") as f:
            return json.load(f)

    SPIEGAZIONE_DEL_FILE = "Nel nome del file gli spazi diventano trattini bassi, i simboli spariscono, e le maiuscole e le minuscole non fanno differenza. Scegli un altro nome per il torneo."
    SPIEGAZIONE_DEI_NOMI = "Nei nomi dei file gli spazi diventano trattini bassi, i simboli spariscono, e le maiuscole e le minuscole non fanno differenza. Scegli un altro nome per il torneo."
    SPIEGAZIONE_DELLA_DATA = (
        "Le edizioni di un torneo con lo stesso nome si distinguono, nell'archivio e nello storico dei giocatori, dalla data di inizio: "
        "con la stessa data la finalizzazione le confonderebbe. Cambia la data di inizio, oppure scegli un altro nome per il torneo."
    )

    @staticmethod
    def _dalla_procedura_guidata(principale, monkeypatch, finestre, nome, inizio=None):
        """I testi dei messaggi della procedura guidata di un torneo nuovo
        chiamato nome, con la data di inizio inizio se c'e', tolti da
        finestre; poi la procedura si chiude con Indietro. Servono a vedere
        che la procedura tiene i suoi testi, con il file del torneo, mentre
        Dati dice i suoi (10.19.15)."""
        principale.start_new_tournament_wizard()
        if inizio:
            principale.creation_data["start_date"] = inizio
        TestNomeDelTorneoNuovo._nome_scritto(principale, monkeypatch, nome)
        principale.on_wizard_back()
        testi = [f.testo for f in finestre]
        finestre.clear()
        return testi

    def test_il_nome_di_un_torneo_della_cartella_non_si_accetta(self, principale, suoni, monkeypatch):
        """Dalla 10.19.15 il messaggio dice il motivo vero, i report e la
        raccolta delle partite con i nomi di quelli di Beta, e non come si
        chiamerebbe il file del torneo, che da Dati non cambia nome; la
        procedura guidata, dove il file nasce con il nome, dice il file come
        prima (decisione di Gabriele del 4 novembre 2026)."""
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        TestNomeDelTorneoNuovo()._torneo_nella_cartella("Beta", rounds=[{"round": 1, "matches": []}])
        procedura = self._dalla_procedura_guidata(principale, monkeypatch, finestre, "beta")
        percorso = self._apri(principale, "Alfa")
        with open(percorso, "rb") as f:
            prima = f.read()
        suoni.clear()

        voce = self._campo(principale, monkeypatch, percorso, "name", "beta")

        assert principale.current_tournament["name"] == "Alfa"
        assert principale.tree_ctrl.GetItemText(voce) == "Nome torneo: Alfa"
        with open(percorso, "rb") as f:
            assert f.read() == prima
        assert suoni == ["apertura", "errore"]
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (
                "Nome del torneo già in uso",
                "Il nome beta non si può usare: i report e la raccolta delle partite del torneo si chiamerebbero come quelli del torneo Beta, in corso nella cartella del programma, nel file Tornello - Beta.json.\n"
                + self.SPIEGAZIONE_DEI_NOMI,
                False,
            )
        ]
        assert procedura == [
            "Il nome beta non si può usare: il file del torneo si chiamerebbe Tornello - beta.json, come il file del torneo Beta, in corso nella cartella del programma.\n"
            + self.SPIEGAZIONE_DEL_FILE
        ]

    @pytest.mark.parametrize(
        ("nome", "file", "coincidenza"),
        [
            ("Players db", "Tornello - Players_db.json", "come il database dei giocatori"),
            ("settings", "Tornello - settings.json", "come il file delle impostazioni del programma"),
            ("Appunti", "Tornello - Appunti.json", "come un altro file del programma, che c'è già nella sua cartella"),
        ],
    )
    def test_il_nome_di_un_file_del_programma_e_riservato(self, principale, suoni, monkeypatch, nome, file, coincidenza):
        """Il nome di un file del programma da Dati non porterebbe via il
        file a nessuno, perche' il file del torneo non cambia nome, e i report
        non coinciderebbero con nessuno: si rifiuta lo stesso, e dalla 10.19.15
        il messaggio lo dice riservato, con il file che avrebbe un torneo
        nuovo con quel nome. La procedura guidata dice il file come prima."""
        from config import user_data_path

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        TestNomeDelTorneoNuovo._scrivi(user_data_path("Tornello - Appunti.json"), {"voci": [1, 2]})
        procedura = self._dalla_procedura_guidata(principale, monkeypatch, finestre, nome)
        percorso = self._apri(principale, "Alfa")
        suoni.clear()

        self._campo(principale, monkeypatch, percorso, "name", nome)

        assert principale.current_tournament["name"] == "Alfa"
        assert self._nel_file(percorso)["name"] == "Alfa"
        assert suoni == ["apertura", "errore"]
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (
                "Nome del torneo già in uso",
                f"Il nome {nome} non si può usare: è riservato, perché il file di un torneo nuovo con questo nome si chiamerebbe {file}, {coincidenza}.\n"
                + self.SPIEGAZIONE_DEL_FILE,
                False,
            )
        ]
        assert procedura == [f"Il nome {nome} non si può usare: il file del torneo si chiamerebbe {file}, {coincidenza}.\n" + self.SPIEGAZIONE_DEL_FILE]

    def test_da_dati_conta_prima_il_nome_scritto(self, principale, suoni, monkeypatch):
        """Gamma, rinominato da Dati, sta nel file Tornello - Beta.json, e
        Beta nel file Tornello - Delta.json. Da Dati il nome Beta si rifiuta
        per i report e la raccolta delle partite di Beta, il motivo vero, e
        non per il file di Gamma, con cui i report non coincidono; senza Beta
        resta il file di Gamma, e il nome e' riservato. La procedura guidata,
        dove il file Tornello - Beta.json si sovrascriverebbe, dice il file di
        Gamma, come prima (10.19.15)."""
        from config import user_data_path

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        TestNomeDelTorneoNuovo._scrivi(user_data_path("Tornello - Beta.json"), _torneo_in_corso("Gamma"))
        delta = user_data_path("Tornello - Delta.json")
        TestNomeDelTorneoNuovo._scrivi(delta, _torneo_in_corso("Beta"))
        procedura = self._dalla_procedura_guidata(principale, monkeypatch, finestre, "Beta")
        percorso = self._apri(principale, "Alfa")

        self._campo(principale, monkeypatch, percorso, "name", "Beta")
        os.remove(delta)
        self._campo(principale, monkeypatch, percorso, "name", "Beta")

        assert self._nel_file(percorso)["name"] == "Alfa"
        assert [f.testo for f in finestre] == [
            "Il nome Beta non si può usare: i report e la raccolta delle partite del torneo si chiamerebbero come quelli del torneo Beta, in corso nella cartella del programma, nel file Tornello - Delta.json.\n"
            + self.SPIEGAZIONE_DEI_NOMI,
            "Il nome Beta non si può usare: è riservato, perché il file di un torneo nuovo con questo nome si chiamerebbe Tornello - Beta.json, come il file del torneo Gamma, in corso nella cartella del programma.\n"
            + self.SPIEGAZIONE_DEL_FILE,
        ]
        assert procedura == [
            "Il nome Beta non si può usare: il file del torneo si chiamerebbe Tornello - Beta.json, come il file del torneo Gamma, in corso nella cartella del programma.\n"
            + self.SPIEGAZIONE_DEL_FILE
        ]

    def test_il_nome_di_un_torneo_dell_archivio_chiede(self, principale, suoni, monkeypatch):
        """La domanda della procedura guidata, con No predefinito: con No il
        nome resta, con Si' cambia e si salva, nel file di prima, che non
        cambia nome. Dalla 10.19.15 la premessa dice il motivo vero, i
        report e la raccolta delle partite con i nomi di quelli
        dell'edizione archiviata, e non come si chiamerebbe il file del
        torneo. Dalla revisione della 10.19.15 anche la fine della domanda ha
        parole sue, Vuoi che questo torneo diventi una nuova edizione, perche'
        da Dati il torneo c'e' gia'; la procedura guidata tiene la sua
        premessa con il file e la sua domanda, Vuoi creare una nuova
        edizione."""
        import wx

        from config import user_data_path

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch, [wx.ID_NO, wx.ID_NO])
        TestNomeDelTorneoNuovo()._torneo_in_archivio("Primavera_2")
        cartella = os.path.join("Closed Tournaments", "2026", "06 Giugno", "Primavera_2")
        procedura = self._dalla_procedura_guidata(principale, monkeypatch, finestre, "Primavera 2")
        percorso = self._apri(principale, "Alfa")
        suoni.clear()

        voce = self._campo(principale, monkeypatch, percorso, "name", "Primavera 2")

        assert principale.current_tournament["name"] == "Alfa"
        assert principale.tree_ctrl.GetItemText(voce) == "Nome torneo: Alfa"
        assert self._nel_file(percorso)["name"] == "Alfa"
        assert suoni == ["apertura"]
        assert procedura == [TestNomeDelTorneoNuovo._domanda_attesa("Primavera 2", "Tornello - Primavera_2.json", [("Primavera 2", cartella)])]
        assert [(f.titolo, f.testo, f.domanda, f.no_predefinito) for f in finestre] == [
            (
                "Nuova edizione di un torneo concluso",
                "Il torneo Primavera 2 avrebbe il nome di un torneo concluso e archiviato fra i Tornei Conclusi, e i report e la raccolta delle partite si chiamerebbero come i suoi: "
                f"Primavera 2, nella cartella {cartella}.\n" + self.SEGUITO_DELLA_DOMANDA.format(nome="Primavera 2"),
                True,
                True,
            )
        ]

        self._campo(principale, monkeypatch, percorso, "name", "Primavera 2")

        assert principale.current_tournament["name"] == "Primavera 2"
        assert principale.tree_ctrl.GetItemText(voce) == "Nome torneo: Primavera 2"
        assert self._nel_file(percorso)["name"] == "Primavera 2"
        assert not os.path.exists(user_data_path("Tornello - Primavera_2.json"))
        assert [f.titolo for f in finestre] == ["Nuova edizione di un torneo concluso"] * 2
        assert suoni[-1] == "conferma"

    def _rifiuto_della_data(self, cartella):
        """Il rifiuto della data di inizio di Primavera 2, archiviata nella
        cartella con la data di inizio 2026-09-01, come lo dice Dati dalla
        10.19.15: con il file dell'edizione archiviata, e senza dire come si
        chiamerebbe il file del torneo, che da Dati non cambia nome."""
        from utils import format_date_locale

        return (
            f"Il nome Primavera 2 non si può usare con la data di inizio {format_date_locale('2026-09-01')}: il torneo Primavera 2, concluso e archiviato nella cartella {cartella} con il file Tornello - Primavera_2.json, ha lo stesso nome e la stessa data di inizio, e i report e la raccolta delle partite si chiamerebbero come i suoi.\n"
            + self.SPIEGAZIONE_DELLA_DATA
        )

    def test_il_nome_con_la_data_di_un_edizione_archiviata_non_si_accetta(self, principale, suoni, monkeypatch):
        """Dalla 10.19.15 il rifiuto dice il torneo archiviato, con il suo
        file, e non come si chiamerebbe il file del torneo; la procedura
        guidata dice il file come prima."""
        from utils import format_date_locale

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        TestNomeDelTorneoNuovo()._torneo_in_archivio("Primavera_2")
        cartella = os.path.join("Closed Tournaments", "2026", "06 Giugno", "Primavera_2")
        procedura = self._dalla_procedura_guidata(principale, monkeypatch, finestre, "Primavera 2", inizio="2026-09-01")
        percorso = self._apri(principale, "Alfa", start_date="2026-09-01")
        suoni.clear()

        self._campo(principale, monkeypatch, percorso, "name", "Primavera 2")

        assert principale.current_tournament["name"] == "Alfa"
        assert self._nel_file(percorso)["name"] == "Alfa"
        assert suoni == ["apertura", "errore"]
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [("Nome del torneo già in uso", self._rifiuto_della_data(cartella), False)]
        assert procedura == [
            f"Il nome Primavera 2 non si può usare con la data di inizio {format_date_locale('2026-09-01')}: il file del torneo si chiamerebbe Tornello - Primavera_2.json, come quello del torneo Primavera 2, concluso e archiviato nella cartella {cartella}, che ha la stessa data di inizio.\n"
            + self.SPIEGAZIONE_DELLA_DATA
        ]

    def test_la_data_di_inizio_di_un_edizione_archiviata_non_si_accetta(self, principale, suoni, monkeypatch):
        """La nuova edizione di Primavera 2 prova a prendere da Dati la data
        di inizio di quella archiviata: si rifiuta, senza domanda, e il
        campo resta com'era; un'altra data passa, senza domanda."""
        from utils import format_date_locale

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        TestNomeDelTorneoNuovo()._torneo_in_archivio("Primavera_2")
        percorso = self._apri(principale, "Primavera 2")
        suoni.clear()

        voce = self._campo(principale, monkeypatch, percorso, "start_date", "2026-09-01")

        assert principale.current_tournament["start_date"] == "2026-11-02"
        assert self._nel_file(percorso)["start_date"] == "2026-11-02"
        assert principale.tree_ctrl.GetItemText(voce) == f"Data inizio: {format_date_locale('2026-11-02')}"
        assert suoni == ["apertura", "errore"]
        cartella = os.path.join("Closed Tournaments", "2026", "06 Giugno", "Primavera_2")
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [("Nome del torneo già in uso", self._rifiuto_della_data(cartella), False)]
        finestre.clear()

        self._campo(principale, monkeypatch, percorso, "start_date", "2026-11-03")

        assert principale.current_tournament["start_date"] == "2026-11-03"
        assert self._nel_file(percorso)["start_date"] == "2026-11-03"
        assert finestre == []
        assert suoni[-1] == "conferma"

    def test_il_torneo_aperto_non_coincide_con_se_stesso(self, principale, suoni, monkeypatch):
        """Il file del torneo aperto non conta: Alfa, rinominato Beta da
        Dati, torna Alfa nel suo file di sempre, e poi ALFA, e il torneo
        aperto dall'archivio prende lo stesso nome con le minuscole senza
        essere l'edizione archiviata di se stesso, con la sua stessa data di
        inizio. La domanda sulla nuova edizione non si fa per un nome che e'
        gia' quello del torneo."""
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        archiviato = TestNomeDelTorneoNuovo()._torneo_in_archivio("Primavera_2")
        percorso = self._apri(principale, "Alfa")

        for nome in ("Beta", "Alfa", "ALFA"):
            self._campo(principale, monkeypatch, percorso, "name", nome)
            assert self._nel_file(percorso)["name"] == nome
        self._campo(principale, monkeypatch, percorso, "start_date", "2026-11-05")

        assert self._nel_file(percorso)["start_date"] == "2026-11-05"
        assert finestre == []

        principale.load_tournament(archiviato)
        self._campo(principale, monkeypatch, archiviato, "name", "primavera 2")
        self._campo(principale, monkeypatch, archiviato, "start_date", "2026-09-02")

        dati = self._nel_file(archiviato)
        assert (dati["name"], dati["start_date"]) == ("primavera 2", "2026-09-02")
        assert finestre == []

    @pytest.mark.parametrize("prende", [True, False])
    def test_la_raccolta_di_un_altro_torneo_con_il_nome_nuovo(self, principale, suoni, monkeypatch, tmp_path, prende):
        """Il nome nuovo ha gia' la raccolta delle partite di un altro
        torneo: va nel cestino prima del salvataggio, e il nome cambia; se il
        cestino non la prende, si sente l'errore, la raccolta resta com'era
        e il nome anche."""
        from config import user_data_path

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        percorso = self._apri(principale, "Alfa")
        lasciata = user_data_path("Beta - raccolta partite.pgn")
        with open(lasciata, "wb") as f:
            f.write(b"partite di un altro torneo")
        ricevuti = TestRaccoltaDellePartiteDelleEdizioni._cestino(monkeypatch, str(tmp_path / "cestino"), prende)
        suoni.clear()

        self._campo(principale, monkeypatch, percorso, "name", "Beta")

        assert [f.titolo for f in finestre] == ["Raccolta delle partite di un altro torneo"]
        if prende:
            assert ricevuti == [os.path.normcase(os.path.abspath(lasciata))]
            assert self._nel_file(percorso)["name"] == "Beta"
            assert suoni == ["apertura", "conferma"]
        else:
            with open(lasciata, "rb") as f:
                assert f.read() == b"partite di un altro torneo"
            assert principale.current_tournament["name"] == "Alfa"
            assert self._nel_file(percorso)["name"] == "Alfa"
            assert suoni == ["apertura", "errore"]
            assert finestre[0].testo.endswith("\nIl nome del torneo resta quello di prima: sposta quel file in un'altra cartella, poi riprova.")

    def test_la_data_rifiutata_tiene_distinte_le_edizioni_alla_finalizzazione(self, principale, suoni, monkeypatch):
        """La strada intera: la prima edizione di Primavera 2 nasce, si gioca
        e si finalizza con on_finalize_tournament; la seconda nasce con
        un'altra data di inizio, e da Dati prova a prendere quella della
        prima, che si rifiuta. Finalizzata, la seconda ha la sua cartella
        d'archivio, e lo storico di ogni giocatore ha le due edizioni. Fino
        alla 10.19.5 la data passava, e la finalizzazione prendeva la seconda
        per una finalizzazione ripetuta della prima: i giocatori restavano
        senza Elo, partite e storico della seconda."""
        import json
        from datetime import datetime

        import wx

        import ui
        from config import PLAYER_DB_FILE
        from utils import cartella_per_data

        monkeypatch.setattr(ui, "play_sound", lambda *a, **k: None)
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: pytest.fail(f"MessageBox: {a}"))
        TestRaccoltaDellePartiteDelleEdizioni._database_dei_giocatori()
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        TestRaccoltaDellePartiteDelleEdizioni._nuova_edizione(principale, monkeypatch, "2026-10-01", "2026-10-10")
        TestNomeDelTorneoNuovo._gioca_il_turno(principale)
        principale.on_finalize_tournament(None)
        TestRaccoltaDellePartiteDelleEdizioni._nuova_edizione(principale, monkeypatch, "2026-10-15", "2026-10-25")
        TestNomeDelTorneoNuovo._gioca_il_turno(principale)
        finestre.clear()

        self._campo(principale, monkeypatch, principale.active_filename, "start_date", "2026-10-01")

        assert principale.current_tournament["start_date"] == "2026-10-15"
        assert [f.titolo for f in finestre] == ["Nome del torneo già in uso"]

        principale.on_finalize_tournament(None)

        assert principale.current_tournament is None
        with open(PLAYER_DB_FILE, encoding="utf-8") as f:
            database = {p["id"]: p for p in json.load(f)["players"]}
        for codice, _cognome, _nome in GIOCATORI_DEI_TORNEI:
            assert [v["date_started"] for v in database[codice]["tournaments_played"]] == ["2026-10-01", "2026-10-15"], codice
            assert database[codice]["games_played"] == 12, codice
        mese = cartella_per_data(ui.ARCHIVED_TOURNAMENTS_DIR, datetime(2026, 10, 1), crea=False)
        with open(os.path.join(mese, "Primavera_2_2026-10-15", "Tornello - Primavera_2.json"), encoding="utf-8") as f:
            assert json.load(f)["start_date"] == "2026-10-15"
        assert not any("già finalizzato e archiviato" in f.testo for f in finestre)

    RIFIUTO_DELL_IDENTITA = (
        "Nello storico dei giocatori un torneo si riconosce dall'identificativo e dalla data di inizio, e l'identificativo resta lo stesso quando il torneo cambia nome: "
        "con la stessa data la finalizzazione prenderebbe il torneo {nome} per quello archiviato, e i giocatori non ne riceverebbero né l'Elo né le partite. Scegli un'altra data di inizio."
    )

    def test_la_data_di_un_edizione_con_lo_stesso_identificativo_non_si_accetta(self, principale, suoni, monkeypatch):
        """Revisione della 10.19.13 (issue 66, decisione di Gabriele del 4
        novembre 2026). La prima edizione di Coppa, con l'identificativo
        COPPA, e' archiviata dal 1 giugno 2026. La seconda, nata Coppa nella
        procedura guidata, ha lo stesso identificativo e il file Tornello -
        Coppa.json, ed e' stata rinominata Beta da Dati: da Dati non prende
        la data di inizio della prima, perche' lo storico dei giocatori
        riconosce un torneo dall'identificativo e dalla data di inizio, e
        alla finalizzazione le due edizioni si confonderebbero. Un'altra
        data passa. Fino ad allora la data passava, perche' Beta non ha
        edizioni in archivio."""
        import gui.main_frame as mf
        from config import user_data_path
        from utils import format_date_locale

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        archiviata = os.path.join(mf.ARCHIVED_TOURNAMENTS_DIR, "2026", "06 Giugno", "Coppa", "Tornello - Coppa.json")
        prima = dict(_torneo_in_corso("Coppa", finito=True), concluded=True, tournament_id="COPPA", start_date="2026-06-01", end_date="2026-06-20")
        TestNomeDelTorneoNuovo._scrivi(archiviata, prima)
        percorso = user_data_path("Tornello - Coppa.json")
        TestNomeDelTorneoNuovo._scrivi(percorso, dict(_torneo_in_corso("Beta"), tournament_id="COPPA", start_date="2026-11-02", end_date="2026-11-20"))
        principale.load_tournament(percorso)
        suoni.clear()

        voce = self._campo(principale, monkeypatch, percorso, "start_date", "2026-06-01")

        assert principale.current_tournament["start_date"] == "2026-11-02"
        assert self._nel_file(percorso)["start_date"] == "2026-11-02"
        assert principale.tree_ctrl.GetItemText(voce) == f"Data inizio: {format_date_locale('2026-11-02')}"
        assert suoni == ["apertura", "errore"]
        cartella = os.path.join("Closed Tournaments", "2026", "06 Giugno", "Coppa")
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (
                "Data di inizio già in uso",
                f"La data di inizio {format_date_locale('2026-06-01')} non si può usare per il torneo Beta: il torneo Coppa, concluso e archiviato nella cartella {cartella} con il file Tornello - Coppa.json, ha lo stesso identificativo, COPPA, e la stessa data di inizio.\n"
                + self.RIFIUTO_DELL_IDENTITA.format(nome="Beta"),
                False,
            )
        ]
        finestre.clear()

        self._campo(principale, monkeypatch, percorso, "start_date", "2026-06-02")

        assert self._nel_file(percorso)["start_date"] == "2026-06-02"
        assert finestre == []

    def test_la_data_rifiutata_tiene_distinte_le_edizioni_rinominate(self, principale, suoni, monkeypatch):
        """La strada intera della revisione della 10.19.13: la prima
        edizione di Primavera 2 nasce, si gioca e si finalizza; la seconda
        nasce con un'altra data di inizio e l'identificativo PRIMAVERA_2, da
        Dati si rinomina Primavera Bis, e poi prova a prendere la data di
        inizio della prima, che si rifiuta. Finalizzata, ogni giocatore ha
        nello storico le due edizioni, con le partite di tutte e due. Fino
        ad allora la data passava, e alla finalizzazione i giocatori
        risultavano gia' registrati, senza Elo e partite della seconda."""
        import json

        import wx

        import ui
        from config import PLAYER_DB_FILE

        monkeypatch.setattr(ui, "play_sound", lambda *a, **k: None)
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: pytest.fail(f"MessageBox: {a}"))
        TestRaccoltaDellePartiteDelleEdizioni._database_dei_giocatori()
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        TestRaccoltaDellePartiteDelleEdizioni._nuova_edizione(principale, monkeypatch, "2026-10-01", "2026-10-10")
        TestNomeDelTorneoNuovo._gioca_il_turno(principale)
        principale.on_finalize_tournament(None)
        TestRaccoltaDellePartiteDelleEdizioni._nuova_edizione(principale, monkeypatch, "2026-10-15", "2026-10-25")
        TestNomeDelTorneoNuovo._gioca_il_turno(principale)
        assert principale.current_tournament["tournament_id"] == "PRIMAVERA_2"
        self._campo(principale, monkeypatch, principale.active_filename, "name", "Primavera Bis")
        finestre.clear()

        self._campo(principale, monkeypatch, principale.active_filename, "start_date", "2026-10-01")

        assert principale.current_tournament["name"] == "Primavera Bis"
        assert principale.current_tournament["start_date"] == "2026-10-15"
        assert [f.titolo for f in finestre] == ["Data di inizio già in uso"]

        principale.on_finalize_tournament(None)

        assert principale.current_tournament is None
        with open(PLAYER_DB_FILE, encoding="utf-8") as f:
            database = {p["id"]: p for p in json.load(f)["players"]}
        for codice, _cognome, _nome in GIOCATORI_DEI_TORNEI:
            voci = [(v.get("tournament_name"), v["date_started"]) for v in database[codice]["tournaments_played"]]
            assert voci == [("Primavera 2", "2026-10-01"), ("Primavera Bis", "2026-10-15")], codice
            assert database[codice]["games_played"] == 12, codice

    def test_due_edizioni_dell_archivio_al_plurale(self, principale, suoni, monkeypatch):
        """Revisione della 10.19.15: con due edizioni archiviate la premessa
        della domanda da Dati e' al plurale, con i report e la raccolta come
        i loro, e le elenca tutte e due, con la loro cartella."""
        import wx

        import gui.main_frame as mf

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch, [wx.ID_NO])
        for anno, inizio in (("2025", "2025-09-01"), ("2026", "2026-09-01")):
            archiviato = os.path.join(mf.ARCHIVED_TOURNAMENTS_DIR, anno, "09 Settembre", "Primavera_2", "Tornello - Primavera_2.json")
            TestNomeDelTorneoNuovo._scrivi(archiviato, dict(_torneo_in_corso("Primavera 2"), concluded=True, start_date=inizio))
        percorso = self._apri(principale, "Alfa")

        self._campo(principale, monkeypatch, percorso, "name", "Primavera 2")

        assert self._nel_file(percorso)["name"] == "Alfa"
        prima = os.path.join("Closed Tournaments", "2025", "09 Settembre", "Primavera_2")
        seconda = os.path.join("Closed Tournaments", "2026", "09 Settembre", "Primavera_2")
        assert [(f.titolo, f.testo, f.domanda, f.no_predefinito) for f in finestre] == [
            (
                "Nuova edizione di un torneo concluso",
                "Il torneo Primavera 2 avrebbe il nome di 2 tornei conclusi e archiviati fra i Tornei Conclusi, e i report e la raccolta delle partite si chiamerebbero come i loro: "
                f"Primavera 2, nella cartella {prima}; Primavera 2, nella cartella {seconda}.\n" + self.SEGUITO_DELLA_DOMANDA.format(nome="Primavera 2"),
                True,
                True,
            )
        ]

    # Il seguito della domanda sulla nuova edizione da Dati, dopo la
    # premessa. Dalla revisione della 10.19.15 ha parole sue: da Dati il
    # torneo c'e' gia', e diventa la nuova edizione, mentre la procedura
    # guidata ne crea una (decisione di Gabriele del 4 novembre 2026).
    SEGUITO_DELLA_DOMANDA = (
        "Se questo torneo è una nuova edizione dello stesso torneo, il nome si può usare: le edizioni restano distinte, nell'archivio e nello storico dei giocatori, perché hanno date di inizio diverse.\n\n"
        "Vuoi che questo torneo diventi una nuova edizione di {nome}? Il pulsante predefinito è No."
    )

    @staticmethod
    def _archiviata(cartella, file, nome, inizio=None):
        """Il torneo nome, concluso e archiviato con il file file nella
        cartella cartella, una tupla sotto Closed Tournaments, con la data
        di inizio inizio; senza nome, un file che non si legge. Restituisce
        la cartella come la dicono i messaggi."""
        import gui.main_frame as mf

        percorso = os.path.join(mf.ARCHIVED_TOURNAMENTS_DIR, *cartella, file)
        if nome:
            TestNomeDelTorneoNuovo._scrivi(percorso, dict(_torneo_in_corso(nome), concluded=True, start_date=inizio))
        else:
            os.makedirs(os.path.dirname(percorso), exist_ok=True)
            with open(percorso, "w", encoding="utf-8") as f:
                f.write("{ non e' json")
        return os.path.join("Closed Tournaments", *cartella)

    def test_un_edizione_trovata_per_il_solo_file_ha_il_nome_riservato(self, principale, suoni, monkeypatch):
        """Revisione della 10.19.15 (issue 66, decisione di Gabriele del 4
        novembre 2026). Beta, archiviata nel file Tornello - Alfa.json, come
        dopo un cambio di nome da Dati prima della finalizzazione, coincide
        con il nome Alfa soltanto per il file: da Dati la premessa della
        domanda dice che il nome e' riservato, e nomina Beta con la sua
        cartella e il suo file. Fino ad allora diceva che Beta aveva lo
        stesso nome, e che i report e la raccolta delle partite si sarebbero
        chiamati come i suoi. La domanda si fa lo stesso, e con No il nome
        resta; la procedura guidata tiene la sua."""
        import wx

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch, [wx.ID_NO, wx.ID_NO])
        beta = self._archiviata(("2026", "06 Giugno", "Beta"), "Tornello - Alfa.json", "Beta", "2026-06-01")
        procedura = self._dalla_procedura_guidata(principale, monkeypatch, finestre, "Alfa")
        percorso = self._apri(principale, "Gamma")
        suoni.clear()

        self._campo(principale, monkeypatch, percorso, "name", "Alfa")

        assert principale.current_tournament["name"] == "Gamma"
        assert self._nel_file(percorso)["name"] == "Gamma"
        assert suoni == ["apertura"]
        assert [(f.titolo, f.testo, f.domanda, f.no_predefinito) for f in finestre] == [
            (
                "Nuova edizione di un torneo concluso",
                "Il nome Alfa è riservato, perché il file di un torneo nuovo con questo nome si chiamerebbe come quello di un torneo concluso e archiviato fra i Tornei Conclusi: "
                f"Beta, nella cartella {beta}, con il file Tornello - Alfa.json.\n" + self.SEGUITO_DELLA_DOMANDA.format(nome="Alfa"),
                True,
                True,
            )
        ]
        assert procedura == [TestNomeDelTorneoNuovo._domanda_attesa("Alfa", "Tornello - Alfa.json", [("Beta", beta)])]

    def test_con_la_stessa_data_un_edizione_trovata_per_il_solo_file(self, principale, suoni, monkeypatch):
        """Revisione della 10.19.15. Con la data di inizio di Beta,
        archiviata nel file Tornello - Alfa.json, il nome Alfa da Dati si
        rifiuta come prima, ma il messaggio dice che e' riservato, con il
        nome, la cartella e il file di Beta, e non piu' che Beta ha lo stesso
        nome. La procedura guidata tiene il suo messaggio."""
        from utils import format_date_locale

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        beta = self._archiviata(("2026", "06 Giugno", "Beta"), "Tornello - Alfa.json", "Beta", "2026-06-01")
        procedura = self._dalla_procedura_guidata(principale, monkeypatch, finestre, "Alfa", inizio="2026-06-01")
        percorso = self._apri(principale, "Gamma", start_date="2026-06-01")
        suoni.clear()

        self._campo(principale, monkeypatch, percorso, "name", "Alfa")

        assert principale.current_tournament["name"] == "Gamma"
        assert self._nel_file(percorso)["name"] == "Gamma"
        assert suoni == ["apertura", "errore"]
        data = format_date_locale("2026-06-01")
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (
                "Nome del torneo già in uso",
                f"Il nome Alfa non si può usare con la data di inizio {data}: è riservato, perché il file di un torneo nuovo con questo nome si chiamerebbe come quello del torneo Beta, concluso e archiviato nella cartella {beta} con il file Tornello - Alfa.json, che ha la stessa data di inizio.\n"
                + self.SPIEGAZIONE_DELLA_DATA,
                False,
            )
        ]
        assert procedura == [
            f"Il nome Alfa non si può usare con la data di inizio {data}: il file del torneo si chiamerebbe Tornello - Alfa.json, come quello del torneo Beta, concluso e archiviato nella cartella {beta}, che ha la stessa data di inizio.\n"
            + self.SPIEGAZIONE_DELLA_DATA
        ]

    def test_due_edizioni_una_per_il_nome_e_una_per_il_file(self, principale, suoni, monkeypatch):
        """Revisione della 10.19.15. Alfa, archiviata nel 2025 nel suo file,
        ha il nome Alfa; Beta, archiviata nel 2026 nel file Tornello -
        Alfa.json, soltanto il file. Da Dati la premessa ha una frase per
        ciascuna, ognuna con la sua descrizione vera: Alfa con la sua
        cartella, Beta con la cartella e il file. La procedura guidata tiene
        la sua, con il file per tutte e due."""
        import wx

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch, [wx.ID_NO, wx.ID_NO])
        alfa = self._archiviata(("2025", "09 Settembre", "Alfa"), "Tornello - Alfa.json", "Alfa", "2025-09-01")
        beta = self._archiviata(("2026", "06 Giugno", "Beta"), "Tornello - Alfa.json", "Beta", "2026-06-01")
        procedura = self._dalla_procedura_guidata(principale, monkeypatch, finestre, "Alfa")
        percorso = self._apri(principale, "Gamma")

        self._campo(principale, monkeypatch, percorso, "name", "Alfa")

        assert self._nel_file(percorso)["name"] == "Gamma"
        assert [(f.titolo, f.testo, f.domanda, f.no_predefinito) for f in finestre] == [
            (
                "Nuova edizione di un torneo concluso",
                "Il torneo Alfa avrebbe il nome di un torneo concluso e archiviato fra i Tornei Conclusi, e i report e la raccolta delle partite si chiamerebbero come i suoi: "
                f"Alfa, nella cartella {alfa}. "
                "Il nome Alfa è anche riservato, perché il file di un torneo nuovo con questo nome si chiamerebbe come quello di un torneo concluso e archiviato fra i Tornei Conclusi: "
                f"Beta, nella cartella {beta}, con il file Tornello - Alfa.json.\n" + self.SEGUITO_DELLA_DOMANDA.format(nome="Alfa"),
                True,
                True,
            )
        ]
        assert procedura == [TestNomeDelTorneoNuovo._domanda_attesa("Alfa", "Tornello - Alfa.json", [("Alfa", alfa), ("Beta", beta)])]

    def test_edizioni_dei_due_tipi_al_plurale(self, principale, suoni, monkeypatch):
        """Revisione della 10.19.15. Due edizioni con il nome Alfa, una nel
        suo file e una nel file Tornello - Delta.json, e due soltanto con il
        file Tornello - Alfa.json, Beta e un file che non si legge: da Dati
        le due frasi della premessa sono al plurale, e il file che non si
        legge si nomina con il suo file, come nella procedura guidata, che
        tiene la sua premessa. Tolte le due con il nome Alfa, resta la sola
        frase del nome riservato, al plurale."""
        import wx

        import gui.main_frame as mf

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch, [wx.ID_NO] * 3)
        alfa = self._archiviata(("2025", "09 Settembre", "Alfa"), "Tornello - Alfa.json", "Alfa", "2025-09-01")
        delta = self._archiviata(("2026", "03 Marzo", "Alfa"), "Tornello - Delta.json", "Alfa", "2026-03-01")
        beta = self._archiviata(("2026", "06 Giugno", "Beta"), "Tornello - Alfa.json", "Beta", "2026-06-01")
        varie = self._archiviata(("2026", "07 Luglio", "Varie"), "Tornello - Alfa.json", None)
        procedura = self._dalla_procedura_guidata(principale, monkeypatch, finestre, "Alfa")
        percorso = self._apri(principale, "Gamma")

        self._campo(principale, monkeypatch, percorso, "name", "Alfa")
        for cartella, file in ((alfa, "Tornello - Alfa.json"), (delta, "Tornello - Delta.json")):
            os.remove(os.path.join(os.path.dirname(mf.ARCHIVED_TOURNAMENTS_DIR), cartella, file))
        self._campo(principale, monkeypatch, percorso, "name", "Alfa")

        assert self._nel_file(percorso)["name"] == "Gamma"
        riservato = (
            "perché il file di un torneo nuovo con questo nome si chiamerebbe come quello di 2 tornei conclusi e archiviati fra i Tornei Conclusi: "
            f"Beta, nella cartella {beta}, con il file Tornello - Alfa.json; Tornello - Alfa.json, nella cartella {varie}.\n"
        )
        assert [f.testo for f in finestre] == [
            "Il torneo Alfa avrebbe il nome di 2 tornei conclusi e archiviati fra i Tornei Conclusi, e i report e la raccolta delle partite si chiamerebbero come i loro: "
            f"Alfa, nella cartella {alfa}; Alfa, nella cartella {delta}, con il file Tornello - Delta.json. "
            "Il nome Alfa è anche riservato, " + riservato + self.SEGUITO_DELLA_DOMANDA.format(nome="Alfa"),
            "Il nome Alfa è riservato, " + riservato + self.SEGUITO_DELLA_DOMANDA.format(nome="Alfa"),
        ]
        assert procedura == [
            "Il torneo Alfa avrebbe il nome di 4 tornei conclusi e archiviati fra i Tornei Conclusi, e i report e la raccolta delle partite si chiamerebbero come i loro: "
            f"Alfa, nella cartella {alfa}; Alfa, nella cartella {delta}, con il file Tornello - Delta.json; Beta, nella cartella {beta}; Tornello - Alfa.json, nella cartella {varie}.\n"
            "Se il torneo nuovo è una nuova edizione dello stesso torneo, il nome si può usare: le edizioni restano distinte, nell'archivio e nello storico dei giocatori, perché hanno date di inizio diverse.\n\n"
            "Vuoi creare una nuova edizione con il nome Alfa? Il pulsante predefinito è No."
        ]

    @pytest.mark.parametrize("stessa_data", [False, True], ids=["un'altra data", "la stessa data"])
    @pytest.mark.parametrize("scritto", ["coppa prova", "Coppa_Prova"], ids=["altre maiuscole", "trattino basso"])
    def test_lo_stesso_nome_scritto_in_un_altro_modo_non_e_riservato(self, principale, suoni, monkeypatch, scritto, stessa_data):
        """Revisione della 10.19.15. Coppa Prova, archiviata nel file
        Tornello - Coppa_Prova.json, e il nome scritto da Dati con altre
        maiuscole, o con il trattino basso al posto dello spazio, sono lo
        stesso nome, confrontato ripulito come nei nomi dei file
        (stesso_nome_scritto di omonimi.py): i report e la raccolta delle
        partite si chiamerebbero davvero come i suoi. Con un'altra data di
        inizio lo dice la premessa della domanda, con la stessa data il
        rifiuto, e nessuno dei due dice che il nome e' riservato, che vale
        soltanto per un'edizione trovata per il solo nome del file."""
        import wx

        from utils import format_date_locale

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch, [wx.ID_NO])
        coppa = self._archiviata(("2026", "06 Giugno", "Coppa_Prova"), "Tornello - Coppa_Prova.json", "Coppa Prova", "2026-06-01")
        percorso = self._apri(principale, "Gamma", start_date="2026-06-01") if stessa_data else self._apri(principale, "Gamma")
        suoni.clear()

        self._campo(principale, monkeypatch, percorso, "name", scritto)

        assert principale.current_tournament["name"] == "Gamma"
        assert self._nel_file(percorso)["name"] == "Gamma"
        if stessa_data:
            assert suoni == ["apertura", "errore"]
            attese = [
                (
                    "Nome del torneo già in uso",
                    f"Il nome {scritto} non si può usare con la data di inizio {format_date_locale('2026-06-01')}: il torneo Coppa Prova, concluso e archiviato nella cartella {coppa} con il file Tornello - Coppa_Prova.json, ha lo stesso nome e la stessa data di inizio, e i report e la raccolta delle partite si chiamerebbero come i suoi.\n"
                    + self.SPIEGAZIONE_DELLA_DATA,
                    False,
                )
            ]
        else:
            assert suoni == ["apertura"]
            attese = [
                (
                    "Nuova edizione di un torneo concluso",
                    f"Il torneo {scritto} avrebbe il nome di un torneo concluso e archiviato fra i Tornei Conclusi, e i report e la raccolta delle partite si chiamerebbero come i suoi: "
                    f"Coppa Prova, nella cartella {coppa}.\n" + self.SEGUITO_DELLA_DOMANDA.format(nome=scritto),
                    True,
                )
            ]
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == attese


class TestPartiteDellaCadenzaNelDatabase:
    """Dalla 10.13.54 (issue 65) la finestra Gestione Database Giocatori
    Locale mostra, sotto le Partite Locali Giocate, le partite dei tornei
    rapid e blitz, da cui il fattore K di quella cadenza conta le trenta
    partite, e le lascia modificare come le altre. Una scheda senza il
    campo, come quelle di prima, ne mostra zero."""

    def test_le_due_voci_dell_anagrafica(self, telaio, suoni):
        from db_players import save_players_db
        from gui.dialogs.players_db_dialog import PlayersDbDialog

        scheda = {"id": "ROSMA001", "first_name": "Mario", "last_name": "Rossi", "current_elo": 1500, "games_played": 20, "games_played_rapid": 12}
        assert save_players_db({"ROSMA001": scheda})
        dlg = PlayersDbDialog(telaio, telaio.settings)
        try:
            dlg.selected_player_id = "ROSMA001"
            dlg.populate_player_tree()
            albero = dlg.tree_ctrl
            voci = {}

            def visita(voce):
                figlio, segno = albero.GetFirstChild(voce)
                while figlio.IsOk():
                    voci[albero.GetItemText(figlio)] = albero.GetItemData(figlio)
                    visita(figlio)
                    figlio, segno = albero.GetNextChild(voce, segno)

            visita(albero.GetRootItem())
            testi = list(voci)
            posizione = testi.index("Partite Locali Giocate: 20")
            assert testi[posizione + 1 : posizione + 3] == ["Partite Locali Rapid: 12", "Partite Locali Blitz: 0"]
            assert voci["Partite Locali Rapid: 12"] == {"type": "field", "key": "games_played_rapid", "is_int": True}
            assert voci["Partite Locali Blitz: 0"] == {"type": "field", "key": "games_played_blitz", "is_int": True}
        finally:
            _chiudi(dlg)


class TestNomeScrittoNelJson:
    """Dalla 10.19.13 (issue 66, decisione di Gabriele del 4 novembre 2026)
    coincidenza_del_nome ed edizioni_nell_archivio, e con loro la procedura
    guidata, il nome e la data di inizio da Dati e la guardia della raccolta
    delle partite, riconoscono un torneo anche dal nome scritto nel suo json,
    nella cartella del programma e nell'archivio, ripulito come quello che da'
    il nome ai report e alla raccolta. Un torneo rinominato dal ramo Dati
    tiene il file di prima, e fino alla 10.19.10 sfuggiva: si guardava
    soltanto il nome dei file. Le finestre del nome e dei messaggi e il
    cestino sono finti."""

    RIFIUTO_DI_BETA = (
        "Nome del torneo già in uso",
        "Il nome Beta non si può usare: i report e la raccolta delle partite del torneo si chiamerebbero come quelli del torneo Beta, in corso nella cartella del programma, nel file Tornello - Alfa.json.\n"
        "Nei nomi dei file gli spazi diventano trattini bassi, i simboli spariscono, e le maiuscole e le minuscole non fanno differenza. Scegli un altro nome per il torneo.",
    )

    @staticmethod
    def _beta_nel_file_di_alfa():
        """Beta, in corso nella cartella del programma nel file Tornello -
        Alfa.json, come dopo un cambio di nome dal ramo Dati."""
        from config import user_data_path

        percorso = user_data_path("Tornello - Alfa.json")
        TestNomeDelTorneoNuovo._scrivi(percorso, dict(_torneo_in_corso("Beta"), start_date="2026-11-02", end_date="2026-11-20"))
        return percorso

    @staticmethod
    def _coppa_nel_file_di_alfa(con_pgn=False):
        """Coppa_Prova, concluso e archiviato nel file Tornello - Alfa.json,
        con la data di inizio 2026-09-01; con con_pgn la prima partita ha il
        PGN."""
        import gui.main_frame as mf

        percorso = os.path.join(mf.ARCHIVED_TOURNAMENTS_DIR, "2026", "06 Giugno", "Coppa_Prova", "Tornello - Alfa.json")
        dati = dict(_torneo_in_corso("Coppa_Prova", finito=True), concluded=True)
        if con_pgn:
            dati["rounds"][0]["matches"][0]["pgn"] = PGN_VALIDO
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        return percorso

    def test_la_coincidenza_nella_cartella_del_programma(self):
        """Beta coincide per il nome scritto, Alfa per il file, come prima;
        il file del torneo aperto non coincide con se stesso."""
        from gui.main_frame import coincidenza_del_nome

        percorso = self._beta_nel_file_di_alfa()

        assert coincidenza_del_nome("beta") == ("come quelli del torneo Beta, in corso nella cartella del programma, nel file Tornello - Alfa.json", False)
        assert coincidenza_del_nome("Alfa") == ("come il file del torneo Beta, in corso nella cartella del programma", True)
        assert coincidenza_del_nome("beta", escluso=percorso) is None
        assert coincidenza_del_nome("Gamma") is None

    def test_un_json_che_non_si_legge_non_ferma_niente(self):
        """Un json rovinato, uno annidato oltre il limite di Python e uno che
        non e' un torneo, con un nome scritto o senza, non coincidono per il
        nome scritto e non fanno cadere niente; per il nome del file restano
        un altro file del programma, come prima. Fino alla 10.19.10 il json
        annidato faceva cadere il controllo con RecursionError."""
        import gui.main_frame as mf
        from config import user_data_path

        profondo = "[" * 100000 + "]" * 100000
        in_archivio = os.path.join(mf.ARCHIVED_TOURNAMENTS_DIR, "2026", "06 Giugno", "Varie")
        os.makedirs(in_archivio)
        for cartella in (user_data_path(""), in_archivio):
            with open(os.path.join(cartella, "Tornello - Rovinato.json"), "w", encoding="utf-8") as f:
                f.write("{ non e' json")
            with open(os.path.join(cartella, "Tornello - Profondo.json"), "w", encoding="utf-8") as f:
                f.write(profondo)
            TestNomeDelTorneoNuovo._scrivi(os.path.join(cartella, "Tornello - Appunti.json"), {"name": "Beta", "voci": []})

        assert mf.coincidenza_del_nome("Beta") is None
        assert mf.edizioni_nell_archivio("Beta") == []
        assert mf.coincidenza_del_nome("profondo") == ("come un altro file del programma, che c'è già nella sua cartella", True)
        assert [(os.path.basename(p), d) for p, d in mf.edizioni_nell_archivio("Profondo")] == [("Tornello - Profondo.json", None)]

    def test_le_edizioni_nell_archivio(self):
        """L'edizione archiviata nel file di Alfa e' un'edizione di Coppa
        Prova, per il nome scritto, e di Alfa, per il file; il file del
        torneo aperto non conta."""
        from gui.main_frame import edizioni_nell_archivio, stesso_nome_di_file

        percorso = self._coppa_nel_file_di_alfa()

        assert [(p, d["name"]) for p, d in edizioni_nell_archivio("coppa prova")] == [(percorso, "Coppa_Prova")]
        assert [(p, d["name"]) for p, d in edizioni_nell_archivio("ALFA")] == [(percorso, "Coppa_Prova")]
        assert edizioni_nell_archivio("Coppa Prova", escluso=percorso) == []
        assert (stesso_nome_di_file(percorso, "alfa"), stesso_nome_di_file(percorso, "Coppa Prova")) == (True, False)

    def test_la_procedura_guidata_non_accetta_beta(self, principale, suoni, monkeypatch):
        """Il nome si rifiuta con il motivo vero, e anche l'ultima guardia
        prima di scrivere il file non crea il torneo."""
        from config import user_data_path

        finestre = TestDatabaseCheNonSiLeggeNelleFinestre._dialoghi_finti(monkeypatch)
        self._beta_nel_file_di_alfa()
        principale.start_new_tournament_wizard()
        suoni.clear()

        TestNomeDelTorneoNuovo._nome_scritto(principale, monkeypatch, "Beta")

        assert principale.creation_data["name"] == ""
        assert suoni == ["apertura", "errore"]
        assert finestre == [self.RIFIUTO_DI_BETA]

        principale.creation_data["name"] = "Beta"
        principale.create_tournament_from_wizard(TestNomeDelTorneoNuovo._iscritti())

        assert not os.path.exists(user_data_path("Tornello - Beta.json"))
        assert principale.current_tournament is None
        assert finestre == [self.RIFIUTO_DI_BETA] * 2

    def test_da_dati_un_altro_torneo_non_prende_il_nome_beta(self, principale, suoni, monkeypatch):
        """Gamma non prende da Dati il nome Beta, e resta com'era; Beta, nel
        file di Alfa, non coincide con se stesso, e cambia le maiuscole del
        nome e la data di inizio senza messaggi."""
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        alfa = self._beta_nel_file_di_alfa()
        percorso = TestNomeEDataDiInizioDaDati._apri(principale, "Gamma")
        suoni.clear()

        voce = TestNomeEDataDiInizioDaDati._campo(principale, monkeypatch, percorso, "name", "Beta")

        assert principale.current_tournament["name"] == "Gamma"
        assert principale.tree_ctrl.GetItemText(voce) == "Nome torneo: Gamma"
        assert TestNomeEDataDiInizioDaDati._nel_file(percorso)["name"] == "Gamma"
        assert suoni == ["apertura", "errore"]
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [(*self.RIFIUTO_DI_BETA, False)]

        finestre.clear()
        principale.load_tournament(alfa)
        TestNomeEDataDiInizioDaDati._campo(principale, monkeypatch, alfa, "name", "BETA")
        TestNomeEDataDiInizioDaDati._campo(principale, monkeypatch, alfa, "start_date", "2026-11-03")

        dati = TestNomeEDataDiInizioDaDati._nel_file(alfa)
        assert (dati["name"], dati["start_date"]) == ("BETA", "2026-11-03")
        assert finestre == []

    def test_l_edizione_rinominata_nell_archivio(self, principale, suoni, monkeypatch):
        """Coppa Prova con la data di inizio dell'edizione archiviata nel
        file di Alfa si rifiuta, con il motivo vero; con un'altra data viene
        la domanda sulla nuova edizione, che dice anche il file, e con No il
        nome resta quello di prima."""
        import wx

        from utils import format_date_locale

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch, [wx.ID_NO])
        self._coppa_nel_file_di_alfa()
        principale.start_new_tournament_wizard()
        principale.creation_data["start_date"] = "2026-09-01"
        suoni.clear()

        TestNomeDelTorneoNuovo._nome_scritto(principale, monkeypatch, "Coppa Prova")

        assert principale.creation_data["name"] == ""
        assert suoni == ["apertura", "errore"]
        cartella = os.path.join("Closed Tournaments", "2026", "06 Giugno", "Coppa_Prova")
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (
                "Nome del torneo già in uso",
                f"Il nome Coppa Prova non si può usare con la data di inizio {format_date_locale('2026-09-01')}: il torneo Coppa_Prova, concluso e archiviato nella cartella {cartella} con il file Tornello - Alfa.json, ha lo stesso nome e la stessa data di inizio, e i report e la raccolta delle partite si chiamerebbero come i suoi.\n"
                "Le edizioni di un torneo con lo stesso nome si distinguono, nell'archivio e nello storico dei giocatori, dalla data di inizio: con la stessa data la finalizzazione le confonderebbe. Cambia la data di inizio, oppure scegli un altro nome per il torneo.",
                False,
            )
        ]

        finestre.clear()
        principale.creation_data["start_date"] = "2026-11-02"
        TestNomeDelTorneoNuovo._nome_scritto(principale, monkeypatch, "Coppa Prova")

        assert principale.creation_data["name"] == ""
        assert [(f.titolo, f.testo, f.domanda, f.no_predefinito) for f in finestre] == [
            (
                "Nuova edizione di un torneo concluso",
                f"Il torneo Coppa Prova avrebbe il nome di un torneo concluso e archiviato fra i Tornei Conclusi, e i report e la raccolta delle partite si chiamerebbero come i suoi: Coppa_Prova, nella cartella {cartella}, con il file Tornello - Alfa.json.\n"
                "Se il torneo nuovo è una nuova edizione dello stesso torneo, il nome si può usare: le edizioni restano distinte, nell'archivio e nello storico dei giocatori, perché hanno date di inizio diverse.\n\n"
                "Vuoi creare una nuova edizione con il nome Coppa Prova? Il pulsante predefinito è No.",
                True,
                True,
            )
        ]

    def test_la_guardia_riconosce_la_raccolta_dell_edizione_rinominata(self, principale, suoni, monkeypatch, tmp_path):
        """L'edizione archiviata nel file di Alfa, prima della 10.19.7, ha
        lasciato la sua raccolta nella cartella del programma; la nuova Coppa
        Prova, nata in console, la trova al primo salvataggio nella finestra:
        va nella cartella d'archivio dell'edizione rinominata, con una copia
        riletta, e l'originale nel cestino. Fino alla 10.19.10 la guardia non
        la riconosceva, e il salvataggio la cancellava per sempre."""
        from config import user_data_path

        archiviato = self._coppa_nel_file_di_alfa(con_pgn=True)
        lasciata = user_data_path("Coppa_Prova - raccolta partite.pgn")
        contenuto = _raccolta_come_la_scrive_la_finestra(PGN_VALIDO)
        with open(lasciata, "wb") as f:
            f.write(contenuto)
        nuovo = dict(_torneo_in_corso("Coppa_Prova"), tournament_id="Coppa_Prova_20261104120000", start_date="2026-11-02", end_date="2026-11-20")
        percorso = user_data_path("Tornello - Coppa_Prova.json")
        TestNomeDelTorneoNuovo._scrivi(percorso, nuovo)
        principale.load_tournament(percorso)
        ricevuti = TestRaccoltaDellePartiteDelleEdizioni._cestino(monkeypatch, str(tmp_path / "cestino"))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)

        principale._save_state()

        with open(os.path.join(os.path.dirname(archiviato), "Coppa_Prova - raccolta partite.pgn"), "rb") as f:
            assert f.read() == contenuto
        assert ricevuti == [os.path.normcase(os.path.abspath(lasciata))]
        assert not os.path.exists(lasciata)
        assert [f.titolo for f in finestre] == ["Raccolta delle partite di un altro torneo"]
        assert os.path.join("Closed Tournaments", "2026", "06 Giugno", "Coppa_Prova") in finestre[0].testo

    def test_i_nomi_scritti_si_ricordano_per_i_file_vecchi(self, monkeypatch):
        """La guardia della raccolta legge tutto l'archivio a ogni
        salvataggio dopo un PGN nuovo: il nome scritto in un file vecchio si
        ricorda per percorso, dimensione e data di modifica, e il file non si
        rilegge finche' non cambia. Un file cambiato da poco si rilegge
        sempre, perche' una seconda scrittura nello stesso istante avrebbe la
        stessa data. I dati di un'edizione trovata si leggono sempre."""
        import time

        import omonimi

        monkeypatch.setattr(omonimi, "_NOMI_SCRITTI", {})
        letti = []
        vero = omonimi._leggi_json

        def annota(percorso):
            letti.append(os.path.basename(percorso))
            return vero(percorso)

        monkeypatch.setattr(omonimi, "_leggi_json", annota)
        percorso = self._coppa_nel_file_di_alfa()

        for _volta in range(2):
            assert omonimi.edizioni_nell_archivio("Beta") == []
        assert letti == ["Tornello - Alfa.json"] * 2

        vecchio = time.time() - 3600
        os.utime(percorso, (vecchio, vecchio))
        letti.clear()
        for _volta in range(3):
            assert omonimi.edizioni_nell_archivio("Beta") == []
        assert letti == ["Tornello - Alfa.json"]

        letti.clear()
        assert [p for p, _d in omonimi.edizioni_nell_archivio("Coppa Prova")] == [percorso]
        assert letti == ["Tornello - Alfa.json"]

        TestNomeDelTorneoNuovo._scrivi(percorso, dict(_torneo_in_corso("Coppa_Prova_2", finito=True), concluded=True))
        os.utime(percorso, (vecchio, vecchio))
        letti.clear()
        assert omonimi.edizioni_nell_archivio("Coppa Prova") == []
        assert [p for p, _d in omonimi.edizioni_nell_archivio("Coppa Prova 2")] == [percorso]
        assert letti == ["Tornello - Alfa.json"] * 2

    def test_la_firma_conta_anche_la_data_di_modifica(self, monkeypatch):
        """Il json archiviato riscritto con un nome della stessa lunghezza
        ha la stessa dimensione e un'altra data di modifica: la firma, che
        ha tutte e due, lo fa rileggere, e il nome nuovo si riconosce."""
        import time

        import omonimi

        monkeypatch.setattr(omonimi, "_NOMI_SCRITTI", {})
        percorso = self._coppa_nel_file_di_alfa()
        vecchio = time.time() - 3600
        os.utime(percorso, (vecchio, vecchio))
        assert [p for p, _d in omonimi.edizioni_nell_archivio("Coppa Prova")] == [percorso]
        dimensione = os.path.getsize(percorso)

        TestNomeDelTorneoNuovo._scrivi(percorso, dict(_torneo_in_corso("Coppa_Provo", finito=True), concluded=True))
        os.utime(percorso, (vecchio + 60, vecchio + 60))

        assert os.path.getsize(percorso) == dimensione
        assert omonimi.edizioni_nell_archivio("Coppa Prova") == []
        assert [p for p, _d in omonimi.edizioni_nell_archivio("Coppa Provo")] == [percorso]

    def test_un_file_che_non_si_legge_non_si_ricorda(self, monkeypatch):
        """Un json vecchio che per un momento non si legge, per esempio
        bloccato da Dropbox, non si ricorda senza nome: alla lettura dopo,
        con la stessa firma, il suo nome si riconosce."""
        import time

        import omonimi

        monkeypatch.setattr(omonimi, "_NOMI_SCRITTI", {})
        percorso = self._coppa_nel_file_di_alfa()
        vecchio = time.time() - 3600
        os.utime(percorso, (vecchio, vecchio))
        vero = omonimi._leggi_json
        letti = []

        def bloccato_la_prima_volta(p):
            letti.append(p)
            return None if len(letti) == 1 else vero(p)

        monkeypatch.setattr(omonimi, "_leggi_json", bloccato_la_prima_volta)

        assert omonimi.edizioni_nell_archivio("Coppa Prova") == []
        assert [p for p, _d in omonimi.edizioni_nell_archivio("Coppa Prova")] == [percorso]


class TestRaccoltaSenzaPartiteNelCestino:
    """Dalla 10.19.13 (decisione di Gabriele del 4 novembre 2026) la raccolta
    delle partite di un torneo che non ha piu' partite in PGN, per esempio
    dopo una Time Machine, va nel cestino di Windows al salvataggio della
    finestra, come gli altri file dell'utente: fino alla 10.19.10
    _salva_i_report la cancellava per sempre con os.remove. Se il cestino non
    la prende resta dov'e', un messaggio lo dice una volta, e fino alla
    chiusura i salvataggi non ci riprovano, senza disturbare. Il cestino e le
    finestre di messaggio sono finti."""

    @staticmethod
    def _senza_piu_pgn(principale):
        """Primavera 2 in corso, con il PGN della seconda partita, aperta e
        salvata nella finestra, che ne scrive la raccolta; poi la partita
        perde il PGN, come dopo una Time Machine. Restituisce la raccolta e
        il suo contenuto."""
        from config import user_data_path

        dati = _torneo_in_corso("Primavera 2")
        dati["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
        percorso = user_data_path("Tornello - Primavera_2.json")
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        principale.load_tournament(percorso)
        principale._save_state()
        raccolta = user_data_path("Primavera_2 - raccolta partite.pgn")
        with open(raccolta, "rb") as f:
            contenuto = f.read()
        assert contenuto == _raccolta_come_la_scrive_la_finestra(PGN_VALIDO)
        principale.current_tournament["rounds"][0]["matches"][1].pop("pgn")
        return raccolta, contenuto

    @staticmethod
    def _cestino(monkeypatch, cartella, prende=True):
        """Al posto di delete_file_to_trash: annota ogni tentativo, e con
        prende sposta il file in cartella; senza lo lascia dov'e', come un
        disco senza cestino."""
        import shutil

        import utils

        tentativi = []

        def cestino(percorso, finestra=None):
            tentativi.append(os.path.normcase(os.path.abspath(percorso)))
            if not prende:
                return False
            os.makedirs(cartella, exist_ok=True)
            shutil.move(percorso, os.path.join(cartella, os.path.basename(percorso)))
            return True

        monkeypatch.setattr(utils, "delete_file_to_trash", cestino)
        return tentativi

    def test_va_nel_cestino(self, principale, suoni, monkeypatch, tmp_path):
        raccolta, contenuto = self._senza_piu_pgn(principale)
        tentativi = self._cestino(monkeypatch, str(tmp_path / "cestino"))
        rimossi = TestRaccoltaAlSalvataggioNellaFinestra._rimozioni(monkeypatch)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()

        principale._save_state()

        assert tentativi == [os.path.normcase(os.path.abspath(raccolta))]
        assert not os.path.exists(raccolta)
        with open(tmp_path / "cestino" / os.path.basename(raccolta), "rb") as f:
            assert f.read() == contenuto
        assert os.path.normcase(os.path.abspath(raccolta)) not in rimossi
        assert finestre == []
        assert "errore" not in suoni

    def test_se_il_cestino_non_la_prende_resta_e_lo_dice_una_volta(self, principale, suoni, monkeypatch, tmp_path):
        """Resta com'era, con il suono dell'errore e un messaggio; il
        salvataggio dopo non riprova e non ripete il messaggio. Quando il
        torneo ha di nuovo il PGN la raccolta si scrive, e quando lo perde di
        nuovo si riprova, e il messaggio torna."""
        from config import user_data_path

        raccolta, contenuto = self._senza_piu_pgn(principale)
        tentativi = self._cestino(monkeypatch, str(tmp_path / "cestino"), prende=False)
        rimossi = TestRaccoltaAlSalvataggioNellaFinestra._rimozioni(monkeypatch)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()

        principale._save_state()
        principale._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == contenuto
        assert tentativi == [os.path.normcase(os.path.abspath(raccolta))]
        assert rimossi == []
        assert suoni.count("errore") == 1
        cartella = os.path.abspath(user_data_path(""))
        messaggio = (
            "Raccolta delle partite rimasta",
            f"Il torneo Primavera 2 non ha più partite in PGN, e la sua raccolta delle partite Primavera_2 - raccolta partite.pgn, nella cartella {cartella}, doveva andare nel cestino di Windows, che non l'ha presa, per esempio perché quel disco non ha il cestino. Resta dov'è, con le partite di prima: Tornello non la cancella per sempre.\n"
            "Fino alla chiusura di Tornello i salvataggi non ci riprovano, e questo messaggio non si ripete. Se nel frattempo il torneo ha di nuovo una partita in PGN, prima di scrivere la raccolta nuova Tornello mette questa nella cartella backup. Se non ti serve più, spostala o cancellala tu.",
        )
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio]

        principale.current_tournament["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
        principale._save_state()
        principale.current_tournament["rounds"][0]["matches"][1].pop("pgn")
        principale._save_state()

        assert len(tentativi) == 2
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio] * 2

    ALTRO_PGN = '[Event "Turno nuovo"]\n\n1. d4 d5 2. c4 e6 0-1'

    @staticmethod
    def _copie_della_raccolta():
        """Le copie della raccolta di Primavera 2 nella cartella backup, fatte
        prima di sostituire una raccolta rimasta."""
        from config import user_data_path

        trovate = []
        for radice, _cartelle, files in os.walk(user_data_path("backup")):
            trovate += [os.path.join(radice, n) for n in files if n.startswith("Primavera_2 - raccolta partite_pre_sostituzione_raccolta_")]
        return sorted(trovate)

    def test_la_raccolta_rimasta_va_nella_cartella_backup_prima_della_nuova(self, principale, suoni, monkeypatch, tmp_path):
        """Revisione della 10.19.13. Il cestino non prende la raccolta del
        torneo senza piu' PGN, e resta. Al primo PGN nuovo, prima di
        scrivere la raccolta nuova, quella di prima va nella cartella
        backup, con una copia riletta, senza altri messaggi; i salvataggi
        dopo la sostituiscono come sempre, senza altre copie. Fino ad allora
        la raccolta nuova la sostituiva subito, e le partite di prima non
        c'erano piu' in nessun file."""
        raccolta, contenuto = self._senza_piu_pgn(principale)
        self._cestino(monkeypatch, str(tmp_path / "cestino"), prende=False)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale._save_state()
        assert [f.titolo for f in finestre] == ["Raccolta delle partite rimasta"]

        principale.current_tournament["rounds"][0]["matches"][0]["pgn"] = self.ALTRO_PGN
        principale._save_state()

        copie = self._copie_della_raccolta()
        assert len(copie) == 1
        with open(copie[0], "rb") as f:
            assert f.read() == contenuto
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN)
        assert [f.titolo for f in finestre] == ["Raccolta delle partite rimasta"]

        principale.current_tournament["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
        principale._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN, PGN_VALIDO)
        assert len(self._copie_della_raccolta()) == 1

    def test_se_la_copia_non_riesce_la_raccolta_resta(self, principale, suoni, monkeypatch, tmp_path):
        """La copia nella cartella backup della raccolta rimasta non riesce:
        la raccolta resta com'e', la nuova non si scrive, e un messaggio lo
        dice una volta, con il suono dell'errore. Quando la copia riesce, la
        raccolta nuova si scrive."""
        import utils
        from config import user_data_path

        raccolta, contenuto = self._senza_piu_pgn(principale)
        self._cestino(monkeypatch, str(tmp_path / "cestino"), prende=False)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale._save_state()
        vera = utils.copia_di_sicurezza

        def senza_copie_delle_raccolte(percorso, *a, **k):
            if percorso.endswith(".pgn"):
                return None
            return vera(percorso, *a, **k)

        monkeypatch.setattr(utils, "copia_di_sicurezza", senza_copie_delle_raccolte)
        principale.current_tournament["rounds"][0]["matches"][0]["pgn"] = self.ALTRO_PGN
        finestre.clear()
        suoni.clear()

        principale._save_state()
        principale._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == contenuto
        assert suoni.count("errore") == 1
        cartella = os.path.abspath(user_data_path(""))
        assert [(f.titolo, f.testo) for f in finestre] == [
            (
                "Raccolta delle partite non scritta",
                f"La raccolta delle partite Primavera_2 - raccolta partite.pgn, nella cartella {cartella}, ha ancora le partite di prima, che il torneo Primavera 2 non ha più: prima di sostituirla con la raccolta nuova Tornello doveva metterne una copia nella cartella backup, e la copia non è riuscita. Resta com'è, e la raccolta nuova non è stata scritta.\n"
                "I salvataggi ci riprovano, e fino alla chiusura di Tornello questo messaggio non si ripete. Se la raccolta di prima non ti serve più, spostala o cancellala tu, e il prossimo salvataggio scriverà quella nuova.",
            )
        ]

        monkeypatch.setattr(utils, "copia_di_sicurezza", vera)
        principale._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN)
        assert len(self._copie_della_raccolta()) == 1
