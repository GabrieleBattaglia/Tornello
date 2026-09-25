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
    alla 10.13.5 anche un file solo era al plurale."""

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
