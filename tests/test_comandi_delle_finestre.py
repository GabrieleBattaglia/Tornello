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
        TestEliminazioneDelTorneo._dialoghi_finti(monkeypatch)
        messaggi = []
        monkeypatch.setattr("wx.MessageBox", lambda testo, *a, **k: messaggi.append(testo))
        archiviato = os.path.join(ARCHIVED_TOURNAMENTS_DIR, "2026", "10 Ottobre", "Alfa", "Tornello - Alfa.json")

        def finalizza(torneo, database, percorso, avvisi):
            torneo["concluded"] = True
            self._scrivi(archiviato, torneo)
            os.remove(percorso)
            return True

        monkeypatch.setattr(ui, "finalize_tournament", finalizza)
        registro.caricati.clear()

        self._dal_menu(principale, principale.item_finalize.GetId())

        assert messaggi == ["Torneo finalizzato con successo! I dati dei giocatori sono stati aggiornati."]
        assert registro.caricati == []
        self._nessun_torneo_aperto(principale)
        assert principale.last_status_msg == "Torneo concluso e archiviato."
        assert self._dati_della_selezione(principale) == {"action": "start_new_tournament"}

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

        def finalizza(torneo, database, percorso, avvisi):
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
    10.13.26 annullando dopo aver mosso il volume il file torna al volume di
    prima."""

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
            ("ID_OK", ["mostrata", "distrutta", "fuoco"]),
            ("ID_CANCEL", ["mostrata", "volume di prima", "distrutta", "fuoco"]),
        ],
    )
    def test_il_fuoco_torna_dove_era(self, principale, monkeypatch, esito, atteso):
        import wx

        registro = []
        self._preferenze_finte(monkeypatch, getattr(wx, esito), registro)
        monkeypatch.setattr(wx.Window, "FindFocus", lambda: principale.status_text)
        principale.status_text.SetFocus = lambda: registro.append("fuoco")
        principale.on_preferences(None)
        assert registro == atteso

    def test_senza_un_controllo_col_fuoco_non_si_sposta_niente(self, principale, telaio, monkeypatch):
        import wx

        for fuoco in (None, principale, telaio):
            registro = []
            self._preferenze_finte(monkeypatch, wx.ID_CANCEL, registro)
            monkeypatch.setattr(wx.Window, "FindFocus", lambda fuoco=fuoco: fuoco)
            if fuoco is not None:
                fuoco.SetFocus = lambda registro=registro: registro.append("fuoco")
            principale.on_preferences(None)
            assert registro == ["mostrata", "volume di prima", "distrutta"]

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
            assert suonati == ["notifica"]
            dlg.rimetti_il_volume()
            assert self._nel_file(percorso) == {"volume": 40, "font_size": 18}
            assert utils._volume_base() == 0.4
            assert suonati == ["notifica"]
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
            (1, "Calendario esportato in 'calendario.ics', ma una partita pianificata non c'e' entrata: la sua data non e' leggibile."),
            (2, "Calendario esportato in 'calendario.ics', ma 2 partite pianificate non ci sono entrate: la loro data non e' leggibile."),
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
        assert principale.item_delete_tournament.GetItemLabel() == "E&limina Torneo Attivo...\tDelete"

    def test_ogni_menu_ha_lettere_tutte_diverse(self, principale):
        barra = principale.GetMenuBar()
        titoli = [barra.GetMenuLabel(i) for i in range(barra.GetMenuCount())]
        assert len({_lettera(t) for t in titoli}) == len(titoli)
        for posizione, titolo in enumerate(titoli):
            voci = [v.GetItemLabel() for v in barra.GetMenu(posizione).GetMenuItems() if not v.IsSeparator()]
            lettere = [_lettera(v) for v in voci]
            assert None not in lettere, (titolo, voci)
            assert len(set(lettere)) == len(lettere), (titolo, voci)
