"""Tasti e voci che devono fare quello che promettono.

Dalla 10.8.4 INVIO nella finestra del risultato conferma solo se il pulsante
di conferma e' acceso: con un PGN non valido suona l'errore e la finestra
resta aperta. Lo fermano il gancio della tastiera, che arriva prima di
Windows, e on_key_down, per quando il tasto gli arriva lo stesso; sui
pulsanti e nel campo del PGN il tasto resta loro. Dalla 10.8.5 le voci del menu Visualizza, che prima non avevano
un gestore, fanno quello che fanno F5, F6 e F7, con lo stesso suono. Dalla
10.8.6 la riga che carica altri risultati FIDE non ha piu' i trattini che
NVDA leggeva, e si riconosce dalla posizione invece che dal testo.
Nessuna finestra viene mostrata, niente suona: i suoni si annotano, e le
chiusure delle finestre modali pure.
"""

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
