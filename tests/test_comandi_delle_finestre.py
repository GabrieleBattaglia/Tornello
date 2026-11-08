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
import sys
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


def _descrizione_dell_errore(testo):
    """La descrizione del motivo che da' il sistema, dal testo intero che
    la console stampa per un OSError, come [WinError 5] Accesso negato:
    'a' -> 'b' per un file bloccato alla sostituzione, o [Errno 13]
    Permission denied: 'c' per uno bloccato all'apertura: dalla revisione
    della 10.19.19 i messaggi Torneo non salvato e Raccolta delle partite non
    scritta dicono soltanto quella, perche' il percorso del file lo dicono
    gia' (decisione di Gabriele del 5 novembre 2026). Il testo intero resta
    in console."""
    import re

    trovato = re.fullmatch(r"\[(?:WinError|Errno) \d+\] (.+?): '.*'", testo)
    assert trovato, testo
    return trovato.group(1)


def _apertura_non_riuscita(percorso, motivo):
    """Il titolo e il testo del messaggio Apertura non riuscita, per il file
    percorso che non si apre, con motivo, la descrizione: dalla 10.19.33
    (decisione di Gabriele del 7 novembre 2026) prende il posto del
    wx.MessageBox senza suono Errore nel caricamento del torneo, con il
    testo intero dell'errore."""
    return ("Apertura non riuscita", f"Il file {percorso} non si è potuto aprire: {motivo}.")


# I guasti del file di un torneo che l'albero ha gia' elencato, con la
# descrizione del motivo che dicono i messaggi Giocatore non rimosso e Torneo
# non eliminato: il file che manca e quello rovinato dalla 10.19.30; dalla
# 10.19.36 il file che e' una lista e quello con i turni che non sono una
# lista, che non hanno la forma di un torneo, come per l'albero.
GUASTI_DEL_FILE = [
    ("manca", "No such file or directory"),
    ("rovinato", "Expecting value: line 1 column 1 (char 0)"),
    ("lista", "non ha la forma di un torneo di Tornello"),
    ("senza_forma", "non ha la forma di un torneo di Tornello"),
]


def _guasta_il_file(percorso, guasto):
    """Il guasto di GUASTI_DEL_FILE sul file del torneo percorso."""
    import json

    if guasto == "manca":
        os.remove(percorso)
        return
    if guasto == "rovinato":
        testo = "non è un torneo"
    elif guasto == "lista":
        testo = json.dumps([1, 2, 3])
    else:
        with open(percorso, encoding="utf-8") as f:
            dati = json.load(f)
        dati["rounds"] = 5
        testo = json.dumps(dati)
    with open(percorso, "w", encoding="utf-8") as f:
        f.write(testo)


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

    def test_i_file_del_torneo_vanno_nel_cestino_e_gli_altri_restano(self, principale, suoni, monkeypatch, tmp_path, cestino_finto):
        from config import user_data_path

        nodo, file_torneo, esterna, finestre = self._prepara(principale, monkeypatch, tmp_path)
        suoni.clear()

        principale.delete_tournament_completely(nodo, file_torneo)

        attesi = [user_data_path(n) for n in self.DEL_TORNEO] + [str(esterna / "Tornello - Autunneo - Classifica.txt")]
        assert sorted(cestino_finto.ricevuti) == sorted(attesi)
        assert cestino_finto.ricevuti[0] == file_torneo
        assert cestino_finto.finestre == [principale.GetHandle()] * len(attesi)
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
    def test_i_file_rimasti_fuori_dal_cestino_si_nominano(self, principale, suoni, monkeypatch, tmp_path, cestino_finto, quanti):
        """Il torneo va nel cestino, ma un report, o due, no: restano dove
        sono, e il messaggio finale li nomina, uno per riga nella finestra,
        con il suono dell'errore invece di quello del successo pieno."""
        from config import user_data_path

        nodo, file_torneo, esterna, finestre = self._prepara(principale, monkeypatch, tmp_path)
        fuori = [str(esterna / "Tornello - Autunneo - Classifica.txt"), user_data_path("Tornello - Autunneo_sospeso.txt")][:quanti]
        cestino_finto.rifiuta.update(fuori)
        suoni.clear()

        principale.delete_tournament_completely(nodo, file_torneo)

        assert file_torneo in cestino_finto.ricevuti
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
    def test_un_torneo_in_archivio_non_porta_via_l_edizione_in_corso(self, principale, suoni, monkeypatch, tmp_path, cestino_finto, cartella):
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
        suoni.clear()

        principale.delete_tournament_completely(nodo, archiviato)

        assert cestino_finto.ricevuti == [archiviato, os.path.join(in_archivio, "Tornello - Sociale - Classifica.txt")]
        assert os.path.exists(in_corso)
        assert os.path.exists(report_in_corso)
        assert not (tmp_path / "chiavetta").exists()
        assert finestre[0][1].split("\n")[0] == "Vuoi mandare nel cestino di Windows il torneo concluso 'Sociale'?"
        assert suoni == ["cancellato"]

    @pytest.mark.parametrize(("nome", "file_del_programma"), [("Players db", "Tornello - Players_db.json"), ("Settings", "Tornello - Settings.json")])
    def test_i_file_del_programma_restano(self, principale, suoni, monkeypatch, cestino_finto, nome, file_del_programma):
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

        principale.delete_tournament_completely(nodo, archiviato)

        assert cestino_finto.ricevuti == [archiviato]
        assert os.path.exists(del_programma)

    @pytest.mark.parametrize(("inizio", "va_nel_cestino"), [("2026-09-01", True), ("2027-09-01", False)])
    def test_la_copia_conclusa_nella_cartella_esterna(self, principale, suoni, monkeypatch, tmp_path, cestino_finto, inizio, va_nel_cestino):
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

        principale.delete_tournament_completely(nodo, archiviato)

        attesi = [archiviato, report, nell_esterna] if va_nel_cestino else [archiviato, report]
        assert cestino_finto.ricevuti == attesi
        assert os.path.exists(nell_esterna) is not va_nel_cestino
        assert os.path.exists(copia)

    def test_gli_altri_json_con_il_nome_del_torneo_restano(self, principale, suoni, monkeypatch, cestino_finto):
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

        principale.delete_tournament_completely(nodo, aperto)

        assert cestino_finto.ricevuti == [aperto]
        assert os.path.exists(vero)
        assert os.path.exists(di_esplora_risorse)

    def test_una_cartella_scritta_con_altre_maiuscole_si_legge_una_volta(self, principale, suoni, monkeypatch, cestino_finto):
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
        cestino_finto.rifiuta.add(report)

        principale.delete_tournament_completely(nodo, file_torneo)

        assert cestino_finto.ricevuti == [file_torneo]
        assert len(cestino_finto.finestre) == 2
        assert os.path.exists(report)
        assert finestre[-1][1].split("\n") == [
            "Torneo 'Autunneo' mandato nel cestino di Windows.",
            "Un file correlato non è andato nel cestino, e resta dov'è:",
            report,
        ]

    def test_una_cartella_che_non_si_legge_si_nomina(self, principale, suoni, monkeypatch, tmp_path, cestino_finto):
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
        suoni.clear()

        principale.delete_tournament_completely(nodo, file_torneo)

        assert cestino_finto.ricevuti[0] == file_torneo
        assert len(cestino_finto.ricevuti) == 3
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

    def test_un_errore_a_meta_dice_che_il_torneo_e_gia_nel_cestino(self, principale, suoni, monkeypatch, tmp_path, cestino_finto):
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
        suoni.clear()

        principale.delete_tournament_completely(nodo, file_torneo)

        assert cestino_finto.ricevuti == [file_torneo]
        assert principale.active_filename is None
        assert principale.current_tournament is None
        testo = f"Errore durante l'eliminazione del torneo: guasto finto Il file del torneo {file_torneo} è già nel cestino di Windows, e da lì si può recuperare."
        assert finestre[-1] == ("Eliminazione non riuscita", testo)
        assert principale.last_status_msg == testo
        assert suoni == ["errore"]


class TestEliminazioneDelTorneoSenzaFile:
    """Proposta 3 del nono giro. Il torneo nuovo della procedura guidata
    che non si e' salvato resta aperto dalla memoria, senza il suo file sul
    disco, come dalla 10.19.20. CANC sulla sua voce, che arriva come la voce
    Elimina o annulla la voce scelta del menu File, lo prende dalla memoria:
    la conferma, la stessa finestra accessibile dell'eliminazione, dice che
    il suo file non c'e' ancora, ed elenca soltanto i file che ci sono
    davvero, i report che il torneo ha gia' scritto nella sua cartella di
    salvataggio. Con Si' il torneo esce dalla memoria e dall'albero, l'area
    centrale torna alla schermata iniziale, il ricordo del messaggio Torneo
    non salvato si perde, i report vanno nel cestino e la barra di stato lo
    dice; con No niente cambia. Fino alla proposta la lettura del file, che
    non c'era, dava il messaggio Impossibile leggere il file del torneo, con
    il testo intero dell'errore in inglese e senza suono, e il torneo
    restava aperto. La scrittura del file del torneo, il cestino e le
    finestre di messaggio sono finti."""

    DOMANDA = "Vuoi eliminare il torneo in preparazione 'Nuovo Sociale'?"
    SI_PERDE = "Il suo file non c'è ancora: se lo elimini, il torneo e i suoi iscritti si perdono, e dal cestino non si possono recuperare."
    ELIMINATO = "Torneo 'Nuovo Sociale' eliminato: il suo file non c'era ancora."

    @staticmethod
    def _creato(principale, monkeypatch, tmp_path, cestino, risposte=()):
        """Il torneo nuovo Nuovo Sociale, con la cartella di salvataggio
        esterna, creato dalla procedura guidata con la scrittura del suo file
        negata: e' aperto senza il suo file, e i report li ha scritti lo
        stesso nella cartella esterna. Restituisce il file del torneo, la
        cartella esterna, i report, le finestre annotate, che alle domande
        rispondono con risposte e poi con Si', i messaggi di wx.MessageBox,
        le volte che l'area centrale torna alla schermata iniziale e i file
        ricevuti da cestino, il cestino finto della prova."""
        import wx

        from config import user_data_path

        esterna = tmp_path / "esterna"
        esterna.mkdir()
        scatole, iniziale = [], []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch, risposte)
        TestTorneoCheNonSiSalva._scrittura_negata(monkeypatch)
        principale.start_new_tournament_wizard()
        principale.creation_data["name"] = "Nuovo Sociale"
        principale.creation_data["save_path"] = str(esterna)
        principale.create_tournament_from_wizard(TestNomeDelTorneoNuovo._iscritti())
        percorso = user_data_path("Tornello - Nuovo_Sociale.json")
        assert not os.path.exists(percorso)
        assert principale._e_il_torneo_aperto(percorso)
        assert [f.titolo for f in finestre] == ["Torneo non salvato"]
        report = sorted(str(f) for f in esterna.iterdir())
        assert len(report) > 1
        monkeypatch.setattr(principale, "show_intro_message", lambda: iniziale.append(True))
        return SimpleNamespace(
            percorso=principale.active_filename,
            esterna=esterna,
            report=report,
            finestre=finestre,
            scatole=scatole,
            iniziale=iniziale,
            ricevuti=cestino.ricevuti,
        )

    @staticmethod
    def _canc(principale):
        """CANC sulla voce del torneo aperto: il tasto e' l'acceleratore della
        voce Elimina o annulla la voce scelta del menu File."""
        voce = principale._voce_del_torneo_aperto()
        assert voce is not None
        with principale._albero_senza_caricamenti():
            principale.tree_ctrl.SelectItem(voce)
        TestAlberoETorneoAttivo._dal_menu(principale, principale.item_canc.GetId())

    @staticmethod
    def _domande_fatte(creato):
        return [(f.titolo, f.testo) for f in creato.finestre if f.domanda]

    def test_con_si_il_torneo_esce_e_i_report_vanno_nel_cestino(self, principale, suoni, monkeypatch, tmp_path, cestino_finto):
        """La conferma elenca i report, sotto la cartella esterna, e con Si'
        il torneo esce dalla memoria e dall'albero, con la voce Avvio torneo
        e il ramo In Preparazione, che resta vuoto; i report vanno nel
        cestino, il file del torneo non nasce, e la barra di stato lo dice,
        con il suono della cancellazione."""
        creato = self._creato(principale, monkeypatch, tmp_path, cestino_finto)
        suoni.clear()

        self._canc(principale)

        conferma = [
            self.DOMANDA,
            self.SI_PERDE,
            f"Nel cestino di Windows vanno {len(creato.report)} file che portano il suo nome intero, e dal cestino si possono recuperare:",
            f"Nella cartella {creato.esterna}:",
            *[os.path.basename(r) for r in creato.report],
        ]
        assert self._domande_fatte(creato) == [("Conferma Eliminazione Torneo", "\n".join(conferma))]
        assert [f.titolo for f in creato.finestre] == ["Torneo non salvato", "Conferma Eliminazione Torneo"]
        assert creato.scatole == []
        assert principale.current_tournament is None
        assert principale.active_filename is None
        assert principale._tornei_non_salvati == set()
        assert creato.iniziale == [True]
        albero = TestAlberoETorneoAttivo
        assert os.path.normcase(creato.percorso) not in albero._tutti_i_file(principale)
        assert not [testo for testo, _dati in albero._figlie(principale) if "Nuovo Sociale" in testo or testo.startswith("In Preparazione")]
        assert sorted(creato.ricevuti) == creato.report
        assert not any(os.path.exists(r) for r in creato.report)
        assert not os.path.exists(creato.percorso)
        assert principale.last_status_msg == f"{self.ELIMINATO} {len(creato.report)} file correlati sono andati nel cestino di Windows."
        assert suoni == ["cancellato"]

    def test_senza_report_nel_cestino_non_va_niente(self, principale, suoni, monkeypatch, tmp_path, cestino_finto):
        """Tolti i report dalla cartella esterna, la conferma dice che nel
        cestino non va nessun file, e con Si' il torneo esce, senza niente
        nel cestino."""
        creato = self._creato(principale, monkeypatch, tmp_path, cestino_finto)
        for report in creato.report:
            os.remove(report)
        suoni.clear()

        self._canc(principale)

        conferma = [self.DOMANDA, self.SI_PERDE, "Nel cestino di Windows non va nessun file."]
        assert self._domande_fatte(creato) == [("Conferma Eliminazione Torneo", "\n".join(conferma))]
        assert creato.scatole == []
        assert principale.current_tournament is None
        assert creato.iniziale == [True]
        assert creato.ricevuti == []
        assert principale.last_status_msg == self.ELIMINATO
        assert suoni == ["cancellato"]

    def test_con_no_niente_cambia(self, principale, suoni, monkeypatch, tmp_path, cestino_finto):
        """Con No alla conferma il torneo nuovo resta aperto, con la sua voce
        nell'albero, e i report restano dove sono."""
        import wx

        creato = self._creato(principale, monkeypatch, tmp_path, cestino_finto, risposte=(wx.ID_NO,))
        stato = principale.last_status_msg
        suoni.clear()

        self._canc(principale)

        assert [titolo for titolo, _testo in self._domande_fatte(creato)] == ["Conferma Eliminazione Torneo"]
        assert creato.scatole == []
        assert principale._e_il_torneo_aperto(creato.percorso)
        assert principale._voce_del_torneo_aperto() is not None
        assert creato.iniziale == []
        assert creato.ricevuti == []
        assert all(os.path.exists(r) for r in creato.report)
        assert principale.last_status_msg == stato
        assert suoni == []

    def test_con_un_report_solo(self, principale, suoni, monkeypatch, tmp_path, cestino_finto):
        """Correzione della proposta 3, rilievo 8 della revisione. Con un
        report solo nella cartella esterna la conferma dice che nel cestino
        va un file, al singolare, e con Si' la barra di stato dice che un
        file correlato e' andato nel cestino."""
        creato = self._creato(principale, monkeypatch, tmp_path, cestino_finto)
        for report in creato.report[1:]:
            os.remove(report)
        suoni.clear()

        self._canc(principale)

        conferma = [
            self.DOMANDA,
            self.SI_PERDE,
            "Nel cestino di Windows va un file che porta il suo nome intero, e dal cestino si può recuperare:",
            f"Nella cartella {creato.esterna}:",
            os.path.basename(creato.report[0]),
        ]
        assert self._domande_fatte(creato) == [("Conferma Eliminazione Torneo", "\n".join(conferma))]
        assert principale.current_tournament is None
        assert creato.ricevuti == creato.report[:1]
        assert principale.last_status_msg == f"{self.ELIMINATO} Un file correlato è andato nel cestino di Windows."
        assert suoni == ["cancellato"]

    def test_un_errore_a_meta_non_dice_che_il_file_e_nel_cestino(self, principale, suoni, monkeypatch, tmp_path, cestino_finto):
        """Correzione della proposta 3, rilievo 8 della revisione. Dopo il
        Si' alla conferma un errore a meta', qui nella ricostruzione
        dell'albero, lo dice il messaggio Eliminazione non riuscita, con il
        suono dell'errore; non dice che il file del torneo e' gia' nel
        cestino, perche' il file non c'era."""
        creato = self._creato(principale, monkeypatch, tmp_path, cestino_finto)

        def guasto(*argomenti, **opzioni):
            raise RuntimeError("guasto finto")

        monkeypatch.setattr(principale, "populate_tree", guasto)
        suoni.clear()

        self._canc(principale)

        messaggi = [(f.titolo, f.testo) for f in creato.finestre if not f.domanda]
        assert messaggi[-1] == ("Eliminazione non riuscita", "Errore durante l'eliminazione del torneo: guasto finto")
        assert principale.last_status_msg == "Errore durante l'eliminazione del torneo: guasto finto"
        assert "errore" in suoni

    @pytest.mark.parametrize(("guasto", "motivo"), GUASTI_DEL_FILE)
    def test_canc_su_un_torneo_non_aperto_senza_file(self, principale, suoni, monkeypatch, cestino_finto, guasto, motivo):
        """Correzione della proposta 3, rilievo 7 della revisione. Alfa e'
        il torneo aperto, con un suo report nella cartella del programma;
        Gamma, che non e' aperta, ha la sua voce nell'albero, poi il suo
        file sparisce, o si rovina. CANC sulla voce di Gamma non prende i
        dati dalla memoria, che sono quelli di Alfa, e i file di Alfa
        restano dove sono: senza la guardia sul torneo aperto la conferma
        nominava Alfa, e con Si' il suo report andava nel cestino. Dalla
        10.19.30 si sente il suono dell'errore, ed esce, senza la conferma,
        il messaggio Torneo non eliminato, nella finestra accessibile, che
        nomina il torneo e il file, con la sola descrizione del motivo, e
        dice che il torneo e i suoi file restano com'erano: nel cestino non
        va niente, e la voce di Gamma resta nell'albero. Fino alla 10.19.29
        usciva un wx.MessageBox senza suono, Impossibile leggere il file del
        torneo, con il testo intero dell'errore. Dalla 10.19.36 lo stesso
        vale per un file che non ha la forma di un torneo, come una lista:
        fino alla 10.19.35 CANC si fermava con un errore che si vedeva
        soltanto in console. Nessun controllo chiede il fuoco."""
        import wx

        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        TestNomeDelTorneoNuovo._scrivi(alfa, _torneo_in_corso("Alfa"))
        principale.load_tournament(alfa)
        report = user_data_path("Tornello - Alfa - classifica.txt")
        with open(report, "w", encoding="utf-8") as f:
            f.write("classifica di Alfa")
        gamma = TestCancSuUnIscrittoDelTorneoAperto._gamma(principale, aperta=False)
        voce = principale._find_matching_item(principale.tree_root, {"action": "select_tournament", "filepath": gamma})
        assert voce and voce.IsOk()
        _guasta_il_file(gamma, guasto)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        with principale._albero_senza_caricamenti():
            principale.tree_ctrl.SelectItem(voce)
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, principale.item_canc.GetId())

        assert principale._e_il_torneo_aperto(alfa)
        assert registro.fuoco == []
        assert scatole == []
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (
                "Torneo non eliminato",
                f"Il torneo Gamma non si è potuto eliminare, perché il file {gamma} non si è potuto leggere: {motivo}. "
                "Il torneo e i suoi file restano com'erano, e nel cestino di Windows non va niente.",
                False,
            )
        ]
        assert suoni == ["errore"]
        assert cestino_finto.ricevuti == []
        assert os.path.exists(report)
        assert principale._find_matching_item(principale.tree_root, {"action": "select_tournament", "filepath": gamma}) is not None


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

    def test_dopo_l_eliminazione_nessun_torneo_resta_aperto(self, principale, suoni, monkeypatch, cestino_finto):
        """Eliminato Beta con il cursore sulla sua voce, la selezione passa a
        un altro torneo senza caricarlo: nessun torneo e' aperto, il titolo
        e il menu lo dicono, e l'albero ridisegnato non ha piu' Beta."""
        percorsi = self._prepara("Alfa", "Beta", "Gamma")
        registro = self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Beta"])
        TestEliminazioneDelTorneo._dialoghi_finti(monkeypatch)
        registro.caricati.clear()
        registro.selezioni.clear()

        principale.delete_tournament_completely(principale.tree_ctrl.GetSelection(), percorsi["Beta"])

        assert cestino_finto.ricevuti == [percorsi["Beta"]]
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
        salvataggio la riscriverebbe sul file. Dalla correzione della
        proposta 7 del nono giro e' di nuovo cosi' per il torneo salvato,
        che non ha modifiche soltanto in memoria. Dalla revisione della
        10.19.29 la prova guarda anche l'albero, che si ricostruisce senza
        la voce di Alfa, che non si legge: le voci di Alfa prese dalla
        memoria, con i suoi rami, non restano. Dalla 10.19.33 il messaggio
        e' Apertura non riuscita, nella finestra accessibile e con il suono
        dell'errore, con il file e il testo dell'errore di json: fino alla
        10.19.32 era un wx.MessageBox senza suono, Errore nel caricamento del
        torneo."""
        percorsi = self._prepara("Alfa")
        rotto = str(tmp_path / "altrove" / "Tornello - Rotto.json")
        os.makedirs(os.path.dirname(rotto))
        with open(rotto, "w", encoding="utf-8") as f:
            f.write("{rotto")
        registro = self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Alfa"])
        messaggi = []
        monkeypatch.setattr("wx.MessageBox", lambda testo, *a, **k: messaggi.append(testo))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        registro.fuoco.clear()
        suoni.clear()

        self._apri_con_ctrl_o(principale, monkeypatch, rotto)

        assert messaggi == []
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (*_apertura_non_riuscita(rotto, "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"), False)
        ]
        assert suoni == ["errore"]
        assert principale.active_filename == percorsi["Alfa"]
        assert principale.GetTitle().endswith("[Alfa]")
        assert principale.last_status_msg == "Il torneo non si è aperto: resta aperto 'Alfa'."
        assert self._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": percorsi["Alfa"]}
        assert registro.fuoco == []

        with open(percorsi["Alfa"], "w", encoding="utf-8") as f:
            f.write("{rovinato")
        finestre.clear()
        suoni.clear()
        self._apri_con_ctrl_o(principale, monkeypatch, percorsi["Alfa"])

        assert messaggi == []
        assert [(f.titolo, f.testo) for f in finestre] == [
            _apertura_non_riuscita(percorsi["Alfa"], "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)")
        ]
        assert suoni == ["errore"]
        self._nessun_torneo_aperto(principale)
        assert principale.last_status_msg == "Il torneo non si è aperto: nessun torneo aperto."
        assert self._tutti_i_file(principale) == []
        assert [(dati or {}).get("action") for _testo, dati in self._figlie(principale)] == ["start_new_tournament"]

    def test_un_json_troppo_annidato_e_un_file_che_non_si_legge(self, principale, suoni, monkeypatch):
        """Correzione della 10.19.29. Alfa e' aperto, e il suo file diventa
        un json annidato oltre il limite di Python, che json.load rifiuta
        con RecursionError; poi Alfa si riapre, come all'avvio o dall'albero.
        E' un file che non si legge, come in omonimi.py dalla 10.19.13: il
        messaggio Errore nel caricamento del torneo lo dice, nessun torneo
        resta aperto, e la barra di stato lo dice. Dalla 10.13.10 l'errore
        usciva dall'apertura, senza messaggio, e Alfa restava in memoria.
        Dalla 10.19.33 il messaggio e' Apertura non riuscita, con il suono
        dell'errore e il testo dell'errore, che dice quanta pila e' servita:
        fino alla 10.19.32 era un wx.MessageBox senza suono."""
        percorsi = self._prepara("Alfa")
        principale.load_tournament(percorsi["Alfa"])
        messaggi = []
        monkeypatch.setattr("wx.MessageBox", lambda testo, *a, **k: messaggi.append(testo))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        with open(percorsi["Alfa"], "w", encoding="utf-8") as f:
            f.write("[" * 200000 + "]" * 200000)
        suoni.clear()

        principale.load_tournament(percorsi["Alfa"])

        assert messaggi == []
        assert [f.titolo for f in finestre] == ["Apertura non riuscita"]
        inizio = f"Il file {percorsi['Alfa']} non si è potuto aprire: "
        assert finestre[0].testo.startswith(inizio)
        assert finestre[0].testo.endswith(" while decoding a JSON array from a unicode string.")
        assert "Errore" not in finestre[0].testo
        assert suoni == ["errore"]
        self._nessun_torneo_aperto(principale)
        assert principale.last_status_msg == "Il torneo non si è aperto: nessun torneo aperto."

    def test_ctrl_o_sul_file_del_torneo_salvato_cambiato_da_fuori(self, principale, suoni, monkeypatch):
        """Correzione della proposta 7 del nono giro. Alfa e' aperta e
        salvata, senza modifiche soltanto in memoria, e da fuori il suo file
        cambia, per esempio rimesso da git com'era ieri sera. Ctrl+O sullo
        stesso file lo rilegge, senza domande: la barra di stato dice
        caricato con successo, e il salvataggio dopo tiene la versione
        rimessa. Fino alla correzione il torneo non si rileggeva, e il
        salvataggio riscriveva sopra la versione vecchia della memoria."""
        import json

        percorsi = self._prepara("Alfa")
        principale.load_tournament(percorsi["Alfa"])
        alfa = principale.active_filename
        assert not principale._ha_modifiche_soltanto_in_memoria()
        with open(alfa, encoding="utf-8") as f:
            da_fuori = json.load(f)
        da_fuori["site"] = "Versione di ieri sera"
        with open(alfa, "w", encoding="utf-8") as f:
            json.dump(da_fuori, f)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)

        self._apri_con_ctrl_o(principale, monkeypatch, alfa)

        assert [f.titolo for f in finestre] == []
        assert principale._e_il_torneo_aperto(alfa)
        assert principale.current_tournament.get("site") == "Versione di ieri sera"
        assert principale.last_status_msg == "Torneo 'Alfa' caricato con successo."
        assert principale._voce_del_torneo_aperto() == principale.tree_ctrl.GetSelection()
        principale._save_state()
        assert TestNomeEDataDiInizioDaDati._nel_file(alfa).get("site") == "Versione di ieri sera"

    def test_ctrl_o_nella_procedura_guidata_sul_torneo_salvato(self, principale, suoni, monkeypatch):
        """Correzione della proposta 7 del nono giro, rilievo 3 della
        revisione. Alfa e' aperta e salvata, poi Ctrl+N apre la procedura
        guidata, e Ctrl+O sceglie il file di Alfa: Alfa si rilegge, come
        sulla base 98e4163, e l'area centrale la mostra. Fino alla correzione
        la barra di stato diceva che Alfa era gia' aperta, con l'area
        centrale vuota e la procedura sullo schermo. Dalla 10.19.34
        (decisione di Gabriele del 7 novembre 2026) la procedura si chiude:
        l'albero torna con i tornei e prende il fuoco, con il cursore sulla
        voce di Alfa, e l'area centrale mostra il suo turno corrente. Fino
        alla 10.19.33 la procedura restava sullo schermo, e il cursore non
        andava su nessuna voce."""
        import wx

        percorsi = self._prepara("Alfa")
        principale.load_tournament(percorsi["Alfa"])
        alfa = principale.active_filename
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        principale.start_new_tournament_wizard()
        assert principale.creation_mode
        registro = self._sonde(principale)
        suoni.clear()

        self._apri_con_ctrl_o(principale, monkeypatch, alfa)

        assert [f.titolo for f in finestre] == []
        assert scatole == []
        assert suoni == []
        assert principale._e_il_torneo_aperto(alfa)
        assert registro.caricati == ["Tornello - Alfa.json"]
        assert not principale.creation_mode
        assert [testo for testo, _dati in self._voci_della_radice(principale)] == ["Alfa", "Nuovo torneo"]
        assert self._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": alfa}
        assert registro.fuoco[-1:] == ["tree_ctrl"]
        assert principale.last_status_msg == "Torneo 'Alfa' caricato con successo."
        assert principale.main_text.GetValue().startswith("Torneo: Alfa\nTurno Corrente: 1 di 3")

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

    def test_la_cartella_del_programma_con_le_parentesi_quadre(self, principale, suoni, programma_con_le_parentesi):
        """10.19.46 (decisione di Gabriele dell'8 novembre 2026). La
        cartella del programma si chiama Tornello [prova], con le parentesi
        quadre: l'albero mostra Alfa, in corso, e Delta, concluso e
        archiviato, fra i Tornei Conclusi. Fino alla 10.19.45, e gia' nella
        10.0.0, glob leggeva le parentesi della cartella dell'archivio come
        un insieme di caratteri, e i Tornei Conclusi non c'erano; i tornei in
        corso li trova dalla 10.19.41."""
        from config import ARCHIVED_TOURNAMENTS_DIR, user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        self._scrivi(alfa, _torneo_in_corso("Alfa"))
        concluso = _torneo_in_corso("Delta", finito=True)
        concluso["concluded"] = True
        delta = os.path.join(ARCHIVED_TOURNAMENTS_DIR, "2026", "10 Ottobre", "Delta", "Tornello - Delta.json")
        self._scrivi(delta, concluso)
        assert "[prova]" in alfa and "[prova]" in delta
        suoni.clear()

        principale.populate_tree()

        assert [testo for testo, _dati in self._voci_della_radice(principale)] == ["Alfa", "Tornei Conclusi (1)", "Nuovo torneo"]
        assert self._voci_dei_conclusi(principale) == ["Delta (Ottobre 2026)"]
        assert set(self._tutti_i_file(principale)) == {os.path.normcase(alfa), os.path.normcase(delta)}
        assert suoni == []

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

    def test_dopo_l_eliminazione_l_albero_non_ha_piu_le_voci_del_torneo(self, principale, suoni, monkeypatch, cestino_finto):
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
        l'avvio proseguiva, senza un torneo da avviare. Dalla 10.19.33 il
        messaggio e' Apertura non riuscita, nella finestra accessibile, con
        il suono dell'errore, il file e la sola descrizione del motivo: fino
        alla 10.19.32 era un wx.MessageBox senza suono, Errore nel
        caricamento del torneo, con il testo intero dell'errore, che aveva il
        percorso con le barre doppie."""
        from config import user_data_path

        percorsi = self._prepara("Alfa")
        beta = user_data_path("Tornello - Beta.json")
        torneo = _torneo_in_corso("Beta")
        torneo["rounds"] = []
        self._scrivi(beta, torneo)
        registro = self._sonde(principale)
        principale.populate_tree()
        self._scegli_torneo(principale, percorsi["Alfa"])
        voce = self._voce(principale, action="start_tournament_matchmaking_action", filepath=beta)
        della_voce = principale.tree_ctrl.GetItemData(voce)["filepath"]
        os.remove(beta)
        messaggi, avviati = [], []
        monkeypatch.setattr("wx.MessageBox", lambda testo, *a, **k: messaggi.append(testo))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale.start_tournament_matchmaking = lambda *a, **k: avviati.append(principale.active_filename)
        registro.fuoco.clear()
        suoni.clear()

        principale.on_tree_item_activated(SimpleNamespace(GetItem=lambda: voce))

        assert messaggi == []
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [(*_apertura_non_riuscita(della_voce, "No such file or directory"), False)]
        assert suoni == ["errore"]
        assert avviati == []
        assert principale.current_tournament is None
        assert registro.fuoco == []

    CAMPI_DEL_RAMO_DATI = (
        ("name", "Nome Torneo"),
        ("site", "Luogo Torneo"),
        ("start_date", "Data Inizio"),
        ("end_date", "Data Fine"),
        ("time_control", "Tempo di riflessione"),
        ("chief_arbiter", "Arbitro Capo"),
        ("deputy_chief_arbiters", "Collaboratori / Vice Arbitri"),
        ("federation_code", "Codice Federazione"),
        ("color_board1", "Colore al giocatore più forte"),
        ("bye_value", "Valore del BYE"),
    )

    @pytest.mark.parametrize("campo, titolo", CAMPI_DEL_RAMO_DATI, ids=[c for c, _t in CAMPI_DEL_RAMO_DATI])
    def test_invio_su_un_campo_dei_dati_di_un_torneo_che_non_si_apre(self, principale, suoni, monkeypatch, campo, titolo):
        """10.19.18 (decisione di Gabriele del 5 novembre 2026). Alfa e'
        aperto, e Beta, in preparazione, ha la sua voce nell'albero, ma il suo
        file sparisce: il cursore arriva su un campo del suo ramo Dati, il
        messaggio d'errore lo dice, e nessun torneo resta aperto, con il
        cursore sulla voce. INVIO su quel campo riprova ad aprire Beta, come
        le altre voci dell'albero: esce di nuovo lo stesso messaggio, e il
        campo non si apre. Tornato il file, INVIO apre Beta, e il campo si
        apre con la sua finestra. Fino alla 10.19.17, e gia' nella 10.0.0,
        INVIO sui campi del ramo Dati leggeva il torneo aperto, None, e
        sollevava AttributeError: si vedeva la finestra Errore Imprevisto.
        Dalla 10.19.33 il messaggio e' Apertura non riuscita, nella finestra
        accessibile, con il suono dell'errore, il file e la sola descrizione
        del motivo, alle frecce e a INVIO: fino alla 10.19.32 era un
        wx.MessageBox senza suono, Errore nel caricamento del torneo."""
        import wx

        from config import user_data_path

        percorsi = self._prepara("Alfa")
        beta = user_data_path("Tornello - Beta.json")
        torneo = _torneo_in_corso("Beta")
        torneo.update(rounds=[], site="Bologna", chief_arbiter="Rossi Anna", federation_code="ITA", time_control={"minutes": 60, "increment": 0})
        self._scrivi(beta, torneo)
        principale.load_tournament(percorsi["Alfa"])
        voce = self._voce(principale, action="show_data", filepath=beta, field_active=campo)
        atteso = _apertura_non_riuscita(principale.tree_ctrl.GetItemData(voce)["filepath"], "No such file or directory")
        messaggi, aperti = [], []
        monkeypatch.setattr(wx, "MessageBox", lambda testo, *a, **k: messaggi.append(testo))

        class CampoFinto:
            def __init__(self, genitore, messaggio, titolo, *a, **k):
                aperti.append((titolo, principale.active_filename))

            def ShowModal(self):
                return wx.ID_CANCEL

            def SetSelection(self, *a):
                pass

            def Destroy(self):
                pass

        monkeypatch.setattr(wx, "TextEntryDialog", CampoFinto)
        monkeypatch.setattr(wx, "SingleChoiceDialog", CampoFinto)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        os.remove(beta)
        suoni.clear()
        principale.tree_ctrl.SelectItem(voce)
        _eventi_in_coda()
        assert principale.current_tournament is None
        assert principale.tree_ctrl.GetSelection() == voce
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [(*atteso, False)]
        assert suoni == ["errore"]
        suoni.clear()

        principale.on_tree_item_activated(SimpleNamespace(GetItem=lambda: voce))

        assert [(f.titolo, f.testo) for f in finestre] == [atteso] * 2
        assert messaggi == []
        assert aperti == []
        assert suoni == ["errore"]
        assert principale.current_tournament is None
        assert principale.tree_ctrl.GetSelection() == voce
        finestre.clear()

        self._scrivi(beta, torneo)
        principale.on_tree_item_activated(SimpleNamespace(GetItem=lambda: voce))

        assert messaggi == []
        assert principale._e_il_torneo_aperto(beta)
        assert aperti == [(titolo, principale.active_filename)]
        assert finestre == []

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
    def test_la_time_machine_manda_nel_cestino_i_dettagli_del_turno_tolto(self, principale, suoni, monkeypatch, cestino_finto, prende):
        """Dalla 10.13.60 (issue 68): annullato il turno 2, gia' concluso,
        il suo file dei dettagli va nel cestino, con la finestra principale
        come proprietaria della domanda di Windows, e quello del turno 1
        resta. Fino alla 10.13.59 restava anche quello del turno 2. Un file
        che il cestino non prende resta dov'e': lo dice un messaggio, con il
        suono dell'errore. Cestino e finestre di messaggio sono finti."""
        import wx

        import gui.main_frame as mf
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
        cestino_finto.prende = prende
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
        suoni.clear()

        self._dal_menu(principale, principale.item_rollback.GetId())

        assert len(principale.current_tournament["rounds"]) == 1
        assert cestino_finto.tentativi == [dettagli[1]]
        assert cestino_finto.finestre == [principale.GetHandle()]
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

    def test_la_raccolta_lasciata_da_un_edizione_archiviata_va_nella_sua_cartella(self, principale, suoni, monkeypatch, cestino_finto):
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
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()

        self._nuova_edizione(principale, monkeypatch, "2026-11-02", "2026-11-20")

        assert principale.active_filename == user_data_path("Tornello - Primavera_2.json")
        with open(os.path.join(os.path.dirname(archiviato), "Primavera_2 - raccolta partite.pgn"), "rb") as f:
            assert f.read() == contenuto
        assert cestino_finto.ricevuti == [os.path.abspath(lasciata)]
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
    def test_una_raccolta_di_nessuna_edizione_archiviata(self, principale, suoni, monkeypatch, cestino_finto, prende):
        """Una raccolta con il nome di quella del torneo nuovo, che nessuna
        edizione archiviata scriverebbe, per esempio di un torneo eliminato,
        va nel cestino, e il torneo nasce. Se il cestino non la prende si
        sente l'errore, un messaggio lo dice, la raccolta resta com'era e il
        torneo non nasce: la procedura guidata resta dov'e'."""
        from config import user_data_path

        lasciata = user_data_path("Gamma - raccolta partite.pgn")
        with open(lasciata, "wb") as f:
            f.write(b"partite di un torneo eliminato")
        cestino_finto.prende = prende
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()

        self._nuova_edizione(principale, monkeypatch, "2026-11-02", "2026-11-20", nome="Gamma")

        cartella = os.path.abspath(user_data_path(""))
        nuovo = user_data_path("Tornello - Gamma.json")
        if prende:
            assert cestino_finto.ricevuti == [os.path.abspath(lasciata)]
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
    def test_la_raccolta_si_mette_in_salvo_prima_dell_iscrizione(self, principale, suoni, monkeypatch, cestino_finto, prende):
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
        cestino_finto.prende = prende
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
            assert cestino_finto.ricevuti == [os.path.abspath(lasciata)]
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
    def test_la_raccolta_lasciata_va_nella_sua_cartella_d_archivio(self, principale, suoni, monkeypatch, tmp_path, cestino_finto, con_pgn):
        from config import user_data_path

        archiviato, lasciata, contenuto = self._archiviata_con_la_raccolta_lasciata()
        self._nata_in_console(principale, con_pgn)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()
        rimossi = self._rimozioni(monkeypatch)

        principale._save_state()

        with open(os.path.join(os.path.dirname(archiviato), "Primavera_2 - raccolta partite.pgn"), "rb") as f:
            assert f.read() == contenuto
        assert cestino_finto.ricevuti == [os.path.abspath(lasciata)]
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
        assert len(cestino_finto.ricevuti) == 1

    def test_se_non_si_mette_in_salvo_resta_e_la_raccolta_non_si_scrive(self, principale, suoni, monkeypatch, cestino_finto):
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
        cestino_finto.prende = False
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()
        principale.current_tournament["rounds"][0]["matches"][0]["result"] = "1-0"

        principale._save_state()

        with open(lasciata, "rb") as f:
            assert f.read() == contenuto
        assert not os.path.exists(os.path.join(os.path.dirname(archiviato), "Primavera_2 - raccolta partite.pgn"))
        assert cestino_finto.ricevuti == []
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

    def test_la_raccolta_del_torneo_stesso_si_sostituisce_senza_messaggi(self, principale, suoni, monkeypatch, cestino_finto):
        """Dopo un PGN nuovo la raccolta sul disco e' quella del torneo,
        scritta dal salvataggio di prima: si sostituisce, senza cestino e
        senza messaggi, anche con un'edizione archiviata con lo stesso nome.
        Una guardia: la mette in salvo soltanto la raccolta identica a
        quella di un'edizione archiviata."""
        from config import user_data_path

        self._archiviata_con_la_raccolta_lasciata()
        os.remove(user_data_path("Primavera_2 - raccolta partite.pgn"))
        self._nata_in_console(principale, con_pgn=True)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale._save_state()
        raccolta = user_data_path("Primavera_2 - raccolta partite.pgn")
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.PGN_NUOVO)

        principale.current_tournament["rounds"][0]["matches"][0]["pgn"] = PGN_VALIDO
        principale._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(PGN_VALIDO, self.PGN_NUOVO)
        assert cestino_finto.ricevuti == []
        assert finestre == []

    def test_l_edizione_stessa_nell_archivio_non_conta(self, principale, suoni, monkeypatch, cestino_finto):
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
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale.current_tournament["rounds"][0]["matches"][1]["pgn"] = self.PGN_NUOVO

        principale._save_state()

        with open(lasciata, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(PGN_VALIDO, self.PGN_NUOVO)
        assert cestino_finto.ricevuti == []
        assert finestre == []

    @pytest.mark.parametrize("con_pgn", [False, True], ids=["senza PGN", "con un PGN"])
    def test_se_il_cestino_non_la_prende_non_ci_riprova(self, principale, suoni, monkeypatch, cestino_finto, con_pgn):
        """Revisione della 10.19.13. La copia va nella cartella d'archivio
        della prima edizione, e il cestino non prende l'originale, per
        esempio su un disco senza cestino: il messaggio lo dice una volta, e
        fino alla chiusura i salvataggi non ci riprovano. Senza PGN la
        raccolta resta dov'e', e il messaggio lo dice; con un PGN il torneo
        la sostituisce con la sua. Quando il torneo senza PGN ne ha uno, la
        raccolta si scrive, senza altri messaggi e senza copie nella cartella
        backup. Fino ad allora ogni salvataggio riprovava il cestino, e
        ripeteva il messaggio, che diceva anche al torneo senza PGN che
        l'avrebbe sostituita, o cancellata."""
        from config import user_data_path

        archiviato, lasciata, contenuto = self._archiviata_con_la_raccolta_lasciata()
        self._nata_in_console(principale, con_pgn)
        cestino_finto.prende = False
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)

        for _volta in range(3):
            principale._save_state()

        with open(os.path.join(os.path.dirname(archiviato), "Primavera_2 - raccolta partite.pgn"), "rb") as f:
            assert f.read() == contenuto
        assert cestino_finto.tentativi == [os.path.abspath(lasciata)]
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
        assert len(cestino_finto.tentativi) == 1
        assert len(finestre) == 1
        # La raccolta dell'altra edizione non e' una raccolta rimasta del
        # torneo, nemmeno nella stessa sessione: la sua copia identica e' gia'
        # nella cartella d'archivio, e non va anche nella cartella backup.
        # Fino alla correzione della revisione della 10.19.13, senza PGN, ci
        # andava al primo PGN nuovo.
        assert TestRaccoltaSenzaPartiteNelCestino._copie_della_raccolta() == []


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
    def test_la_raccolta_di_un_altro_torneo_con_il_nome_nuovo(self, principale, suoni, monkeypatch, cestino_finto, prende):
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
        cestino_finto.prende = prende
        suoni.clear()

        self._campo(principale, monkeypatch, percorso, "name", "Beta")

        assert [f.titolo for f in finestre] == ["Raccolta delle partite di un altro torneo"]
        if prende:
            assert cestino_finto.ricevuti == [os.path.abspath(lasciata)]
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
    # Il seguito della stessa domanda quando tutte le edizioni trovate
    # coincidono soltanto per il nome del file: un torneo archiviato con quel
    # nome non c'e', e la frase sulla nuova edizione non c'e' piu' (revisione
    # della 10.19.15, decisione di Gabriele del 4 novembre 2026).
    SEGUITO_PER_IL_SOLO_FILE = "Vuoi dare lo stesso il nome {nome} a questo torneo? Il pulsante predefinito è No."

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
        resta; la procedura guidata tiene la sua. Dalla stessa revisione il
        seguito non parla di una nuova edizione di Alfa, che fra i tornei
        archiviati non c'e', e chiede soltanto se dare lo stesso il nome."""
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
                f"Beta, nella cartella {beta}, con il file Tornello - Alfa.json.\n" + self.SEGUITO_PER_IL_SOLO_FILE.format(nome="Alfa"),
                True,
                True,
            )
        ]
        assert procedura == [TestNomeDelTorneoNuovo._domanda_attesa("Alfa", "Tornello - Alfa.json", [("Beta", beta)])]

    def test_con_si_un_edizione_trovata_per_il_solo_file_da_soltanto_il_nome(self, principale, suoni, monkeypatch):
        """Revisione della 10.19.15. Con Si' alla domanda per Beta,
        archiviata nel file Tornello - Alfa.json, il torneo Gamma prende
        soltanto il nome Alfa: il suo file, il suo identificativo e la sua
        data di inizio restano i suoi, e Beta, nell'archivio, resta com'era."""
        import gui.main_frame as mf

        TestNomeDelTorneoNuovo._domande(monkeypatch)
        self._archiviata(("2026", "06 Giugno", "Beta"), "Tornello - Alfa.json", "Beta", "2026-06-01")
        beta = os.path.join(mf.ARCHIVED_TOURNAMENTS_DIR, "2026", "06 Giugno", "Beta", "Tornello - Alfa.json")
        with open(beta, "rb") as f:
            prima_di_beta = f.read()
        percorso = self._apri(principale, "Gamma", tournament_id="GAMMA")
        prima = self._nel_file(percorso)

        self._campo(principale, monkeypatch, percorso, "name", "Alfa")

        dopo = self._nel_file(percorso)
        assert principale.active_filename == percorso
        assert dopo["name"] == "Alfa"
        assert (dopo["tournament_id"], dopo["start_date"]) == ("GAMMA", prima["start_date"])
        assert principale.current_tournament["tournament_id"] == "GAMMA"
        with open(beta, "rb") as f:
            assert f.read() == prima_di_beta

    # La seconda frase del rifiuto da Dati per un'edizione trovata soltanto
    # per il nome del file, con la stessa data di inizio: dalla revisione
    # della 10.19.15 non spiega le edizioni con lo stesso nome, che qui non
    # lo sono (decisione di Gabriele del 4 novembre 2026).
    SPIEGAZIONE_DEL_RISERVATO = (
        "Con un'altra data di inizio il nome si può usare, dopo la domanda Nuova edizione di un torneo concluso. "
        "Cambia la data di inizio, oppure scegli un altro nome per il torneo."
    )

    def test_con_la_stessa_data_un_edizione_trovata_per_il_solo_file(self, principale, suoni, monkeypatch):
        """Revisione della 10.19.15. Con la data di inizio di Beta,
        archiviata nel file Tornello - Alfa.json, il nome Alfa da Dati si
        rifiuta come prima, ma il messaggio dice che e' riservato, con il
        nome, la cartella e il file di Beta, e non piu' che Beta ha lo stesso
        nome. La seconda frase dice che con un'altra data il nome si usa,
        dopo la domanda, e non piu' che con la stessa data la finalizzazione
        confonderebbe le edizioni: Beta e il torneo rinominato Alfa hanno
        identita', cartelle d'archivio e file diversi. La procedura guidata
        tiene il suo messaggio."""
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
                + self.SPIEGAZIONE_DEL_RISERVATO,
                False,
            )
        ]
        assert procedura == [
            f"Il nome Alfa non si può usare con la data di inizio {data}: il file del torneo si chiamerebbe Tornello - Alfa.json, come quello del torneo Beta, concluso e archiviato nella cartella {beta}, che ha la stessa data di inizio.\n"
            + self.SPIEGAZIONE_DELLA_DATA
        ]

    # La seconda frase dello stesso rifiuto quando il nome e' gia' quello del
    # torneo, e cambia la data di inizio: la domanda non viene, e il nome
    # resta (revisione della 10.19.15, decisione di Gabriele del 4 novembre
    # 2026).
    SPIEGAZIONE_DEL_NOME_CHE_RESTA = "Con un'altra data di inizio il nome resta. Cambia la data di inizio, oppure scegli un altro nome per il torneo."

    @pytest.mark.parametrize("nome_di_prima", ["Alfa", "Gamma"], ids=["il nome di sempre", "il nome dopo il Sì"])
    def test_la_data_di_un_edizione_trovata_per_il_solo_file_con_il_nome_gia_del_torneo(self, principale, suoni, monkeypatch, nome_di_prima):
        """Revisione della 10.19.15 (decisione di Gabriele del 4 novembre
        2026). Beta e' archiviata nel file Tornello - Alfa.json con la data
        di inizio 2026-06-01. Il torneo si chiama gia' Alfa: da sempre, o
        perche' Gamma ha preso il nome Alfa da Dati, con Si' alla domanda.
        Da Dati la data di inizio diventa quella di Beta: si rifiuta, con la
        stessa prima frase di quando cambia il nome, e la seconda dice che
        con un'altra data il nome resta, perche' la domanda Nuova edizione
        di un torneo concluso, per il nome che e' gia' del torneo, non
        viene. Con un'altra data la data cambia, senza domande. Fino ad
        allora il rifiuto prometteva la domanda, che non arrivava."""
        import wx

        from utils import format_date_locale

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch, [wx.ID_YES])
        beta = self._archiviata(("2026", "06 Giugno", "Beta"), "Tornello - Alfa.json", "Beta", "2026-06-01")
        percorso = self._apri(principale, nome_di_prima, tournament_id="NUOVO")
        if nome_di_prima == "Gamma":
            self._campo(principale, monkeypatch, percorso, "name", "Alfa")
            assert [f.titolo for f in finestre] == ["Nuova edizione di un torneo concluso"]
            assert principale.current_tournament["name"] == "Alfa"
        finestre.clear()
        prima = self._nel_file(percorso)
        suoni.clear()

        self._campo(principale, monkeypatch, percorso, "start_date", "2026-06-01")

        assert principale.current_tournament["start_date"] == "2026-11-02"
        assert self._nel_file(percorso) == prima
        assert suoni == ["apertura", "errore"]
        data = format_date_locale("2026-06-01")
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (
                "Nome del torneo già in uso",
                f"Il nome Alfa non si può usare con la data di inizio {data}: è riservato, perché il file di un torneo nuovo con questo nome si chiamerebbe come quello del torneo Beta, concluso e archiviato nella cartella {beta} con il file Tornello - Alfa.json, che ha la stessa data di inizio.\n"
                + self.SPIEGAZIONE_DEL_NOME_CHE_RESTA,
                False,
            )
        ]
        finestre.clear()

        self._campo(principale, monkeypatch, percorso, "start_date", "2026-07-01")

        assert principale.current_tournament["start_date"] == "2026-07-01"
        assert self._nel_file(percorso)["start_date"] == "2026-07-01"
        assert principale.current_tournament["name"] == "Alfa"
        assert finestre == []

    @pytest.mark.parametrize("prima", ["per il file", "per il nome"])
    def test_con_la_stessa_data_due_edizioni_una_per_il_nome_e_una_per_il_file(self, principale, suoni, monkeypatch, prima):
        """Revisione della 10.19.15 (decisione di Gabriele del 4 novembre
        2026). Con la stessa data di inizio ci sono Alfa, archiviata nel
        suo file con il nome Alfa, e Beta, archiviata nel file Tornello -
        Alfa.json: il nome Alfa da Dati si rifiuta, e il messaggio e' quello
        della prima delle due in ordine di percorso, con le sue frasi, vere
        anche con l'altra. Per Beta prima, il nome e' riservato, e con
        un'altra data si usa dopo la domanda, che c'e' davvero; per Alfa
        prima, le due edizioni con lo stesso nome e la stessa data. La
        procedura guidata tiene il suo messaggio, con il file."""
        from utils import format_date_locale

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        # L'ordine di percorso dipende dalla cartella dell'anno.
        anno_di_beta, anno_di_alfa = ("2025", "2026") if prima == "per il file" else ("2026", "2025")
        alfa = self._archiviata((anno_di_alfa, "06 Giugno", "Alfa"), "Tornello - Alfa.json", "Alfa", "2026-06-01")
        beta = self._archiviata((anno_di_beta, "06 Giugno", "Beta"), "Tornello - Alfa.json", "Beta", "2026-06-01")
        procedura = self._dalla_procedura_guidata(principale, monkeypatch, finestre, "Alfa", inizio="2026-06-01")
        percorso = self._apri(principale, "Gamma", start_date="2026-06-01")
        suoni.clear()

        self._campo(principale, monkeypatch, percorso, "name", "Alfa")

        assert principale.current_tournament["name"] == "Gamma"
        assert self._nel_file(percorso)["name"] == "Gamma"
        assert suoni == ["apertura", "errore"]
        data = format_date_locale("2026-06-01")
        if prima == "per il file":
            atteso = (
                f"Il nome Alfa non si può usare con la data di inizio {data}: è riservato, perché il file di un torneo nuovo con questo nome si chiamerebbe come quello del torneo Beta, concluso e archiviato nella cartella {beta} con il file Tornello - Alfa.json, che ha la stessa data di inizio.\n"
                + self.SPIEGAZIONE_DEL_RISERVATO
            )
            della_procedura = (
                f"Il nome Alfa non si può usare con la data di inizio {data}: il file del torneo si chiamerebbe Tornello - Alfa.json, come quello del torneo Beta, concluso e archiviato nella cartella {beta}, che ha la stessa data di inizio.\n"
                + self.SPIEGAZIONE_DELLA_DATA
            )
        else:
            atteso = (
                f"Il nome Alfa non si può usare con la data di inizio {data}: il torneo Alfa, concluso e archiviato nella cartella {alfa} con il file Tornello - Alfa.json, ha lo stesso nome e la stessa data di inizio, e i report e la raccolta delle partite si chiamerebbero come i suoi.\n"
                + self.SPIEGAZIONE_DELLA_DATA
            )
            della_procedura = (
                f"Il nome Alfa non si può usare con la data di inizio {data}: il file del torneo si chiamerebbe Tornello - Alfa.json, come quello del torneo Alfa, concluso e archiviato nella cartella {alfa}, che ha la stessa data di inizio.\n"
                + self.SPIEGAZIONE_DELLA_DATA
            )
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [("Nome del torneo già in uso", atteso, False)]
        assert procedura == [della_procedura]

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
        frase del nome riservato, al plurale, con il seguito che chiede
        soltanto se dare lo stesso il nome."""
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
            "Il nome Alfa è riservato, " + riservato + self.SEGUITO_PER_IL_SOLO_FILE.format(nome="Alfa"),
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

    @staticmethod
    def _voci_dell_albero(principale, genitore=None):
        """Tutte le voci dell'albero, in profondita', come coppie di voce e
        testo."""
        albero = principale.tree_ctrl
        if genitore is None:
            genitore = principale.tree_root
        voci = []
        voce, cookie = albero.GetFirstChild(genitore)
        while voce.IsOk():
            voci.append((voce, albero.GetItemText(voce)))
            voci += TestNomeEDataDiInizioDaDati._voci_dell_albero(principale, voce)
            voce, cookie = albero.GetNextChild(genitore, cookie)
        return voci

    @pytest.mark.parametrize("dove", ["in corso", "in preparazione", "da un'altra cartella"])
    def test_il_nome_nuovo_nel_titolo_e_nell_albero(self, principale, suoni, monkeypatch, tmp_path, dove):
        """10.19.16 (decisione di Gabriele del 5 novembre 2026). Il cursore
        sta sulla voce Nome torneo del ramo Dati di Alfa, e da li' il nome
        diventa Beta: il titolo della finestra e la voce del torneo
        nell'albero dicono subito Beta, e per un torneo in preparazione anche
        la voce Avvio torneo; la voce di un torneo aperto da un'altra
        cartella tiene la cartella fra parentesi. Il cursore resta sulla voce
        Nome torneo, e l'albero non si ricostruisce: DeleteAllItems non si
        chiama, le voci sono le stesse, e le altre dicono quello che
        dicevano. Fino alla 10.19.15, e gia' nella 10.0.0, il titolo diceva
        Alfa finche' il torneo non si riapriva, e la voce del torneo finche'
        l'albero non si ricostruiva."""
        if dove == "da un'altra cartella":
            # tmp_path e' la cartella del programma, nelle prove.
            altrove = tmp_path / "chiavetta"
            altrove.mkdir()
            percorso = str(altrove / "Tornello - Alfa.json")
            dati = _torneo_in_corso("Alfa")
            dati.update(start_date="2026-11-02", end_date="2026-11-20")
            TestNomeDelTorneoNuovo._scrivi(percorso, dati)
            principale.load_tournament(percorso)
            percorso = principale.active_filename
        else:
            percorso = self._apri(principale, "Alfa", **({"rounds": []} if dove == "in preparazione" else {}))
        albero = principale.tree_ctrl
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_data", "filepath": percorso, "field_active": "name"})
        with principale._albero_senza_caricamenti():
            albero.SelectItem(voce)
        del_torneo = principale._voce_del_torneo_aperto()
        prima = self._voci_dell_albero(principale)
        etichetta = albero.GetItemText(del_torneo)
        if dove == "da un'altra cartella":
            assert etichetta.startswith("Alfa (dalla cartella ")
        else:
            assert etichetta == "Alfa"
        assert ("Avvio torneo: Alfa" in [t for _v, t in prima]) == (dove == "in preparazione")
        assert principale.GetTitle().endswith(" - [Alfa]")
        cancellazioni = []
        vera = albero.DeleteAllItems
        monkeypatch.setattr(albero, "DeleteAllItems", lambda: (cancellazioni.append(True), vera())[1])

        self._campo(principale, monkeypatch, percorso, "name", "Beta")

        assert principale.current_tournament["name"] == "Beta"
        assert self._nel_file(percorso)["name"] == "Beta"
        assert principale.GetTitle().endswith(" - [Beta]")
        assert cancellazioni == []
        assert albero.GetSelection() == voce
        attesi = []
        for v, testo in prima:
            if v == voce:
                testo = "Nome torneo: Beta"
            elif v == del_torneo:
                testo = "Beta" + etichetta[len("Alfa") :]
            elif testo == "Avvio torneo: Alfa":
                testo = "Avvio torneo: Beta"
            attesi.append((v, testo))
        assert self._voci_dell_albero(principale) == attesi

    @pytest.mark.parametrize("ricostruito", [False, True], ids=["senza ricostruzione", "dopo una ricostruzione"])
    @pytest.mark.parametrize("scritto", ["", "   "], ids=["vuoto", "di soli spazi"])
    def test_un_nome_vuoto_non_si_accetta(self, principale, suoni, monkeypatch, capsys, scritto, ricostruito):
        """10.19.17 (decisione di Gabriele del 5 novembre 2026). Il cursore
        sta sulla voce Nome torneo del ramo Dati di Alfa, e da li' il nome
        diventa vuoto, o fatto di soli spazi, che la finestra del campo
        ripulisce: si sente il suono dell'errore, il messaggio Nome del
        torneo mancante dice che il nome resta quello di prima, e il nome, il
        file, il titolo della finestra e tutte le voci dell'albero restano
        come prima, con il cursore sulla voce Nome torneo; la console non
        dice niente. Poi il nome Gamma si accetta: il file, il titolo, la
        voce Nome torneo e la voce del torneo dicono Gamma, anche se prima
        l'albero si ricostruisce, come dopo un turno nuovo. Fino alla
        10.19.16, e gia' nella 10.0.0, il nome vuoto si accettava, e da quel
        momento ogni salvataggio non riusciva, con una riga in console. Nella
        prima stesura della 10.19.16, con il nome vuoto accettato e una
        ricostruzione dell'albero, la voce del torneo diventava GammaAlfa."""
        percorso = self._apri(principale, "Alfa")
        albero = principale.tree_ctrl
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_data", "filepath": percorso, "field_active": "name"})
        with principale._albero_senza_caricamenti():
            albero.SelectItem(voce)
        prima = self._voci_dell_albero(principale)
        titolo = principale.GetTitle()
        assert titolo.endswith(" - [Alfa]")
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()
        capsys.readouterr()

        self._campo(principale, monkeypatch, percorso, "name", scritto)

        assert principale.current_tournament["name"] == "Alfa"
        assert self._nel_file(percorso)["name"] == "Alfa"
        assert principale.GetTitle() == titolo
        assert self._voci_dell_albero(principale) == prima
        assert albero.GetSelection() == voce
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            ("Nome del torneo mancante", "Il nome del torneo non può essere vuoto: il nome resta quello di prima.", False)
        ]
        assert suoni == ["apertura", "errore"]
        assert capsys.readouterr().out == ""
        if ricostruito:
            principale.populate_tree()

        voce = self._campo(principale, monkeypatch, percorso, "name", "Gamma")

        assert self._nel_file(percorso)["name"] == "Gamma"
        assert principale.GetTitle().endswith(" - [Gamma]")
        assert albero.GetItemText(voce) == "Nome torneo: Gamma"
        assert albero.GetItemText(principale._voce_del_torneo_aperto()) == "Gamma"


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

    def test_la_guardia_riconosce_la_raccolta_dell_edizione_rinominata(self, principale, suoni, monkeypatch, cestino_finto):
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
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)

        principale._save_state()

        with open(os.path.join(os.path.dirname(archiviato), "Coppa_Prova - raccolta partite.pgn"), "rb") as f:
            assert f.read() == contenuto
        assert cestino_finto.ricevuti == [os.path.abspath(lasciata)]
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
    chiusura i salvataggi non ci riprovano, senza disturbare. Dalla revisione
    della 10.19.13 una raccolta rimasta, che il cestino non ha preso o che
    all'apertura del torneo ha partite che il torneo non ha, se ne ha ancora
    va nella cartella backup prima di essere sostituita. Il cestino e le
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

    def test_va_nel_cestino(self, principale, suoni, monkeypatch, tmp_path, cestino_finto):
        raccolta, contenuto = self._senza_piu_pgn(principale)
        rimossi = TestRaccoltaAlSalvataggioNellaFinestra._rimozioni(monkeypatch)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()

        principale._save_state()

        assert cestino_finto.tentativi == [os.path.abspath(raccolta)]
        assert not os.path.exists(raccolta)
        with open(tmp_path / "cestino" / f"0_{os.path.basename(raccolta)}", "rb") as f:
            assert f.read() == contenuto
        assert os.path.normcase(os.path.abspath(raccolta)) not in rimossi
        assert finestre == []
        assert "errore" not in suoni

    @staticmethod
    def _messaggio_della_raccolta_rimasta():
        """Il titolo e il testo del messaggio Raccolta delle partite rimasta
        per la raccolta di Primavera 2 nella cartella del programma."""
        from config import user_data_path

        cartella = os.path.abspath(user_data_path(""))
        return (
            "Raccolta delle partite rimasta",
            f"Il torneo Primavera 2 non ha più partite in PGN, e la sua raccolta delle partite Primavera_2 - raccolta partite.pgn, nella cartella {cartella}, doveva andare nel cestino di Windows, che non l'ha presa, per esempio perché quel disco non ha il cestino. Resta dov'è, con le partite di prima: Tornello non la cancella per sempre.\n"
            "Fino alla chiusura di Tornello i salvataggi non ci riprovano, e questo messaggio non si ripete. Quando il torneo ha di nuovo una partita in PGN, se la raccolta ha ancora partite che il torneo non ha, prima di sostituirla con la raccolta nuova Tornello la mette nella cartella backup, anche dopo una chiusura di Tornello. Se non ti serve più, spostala o cancellala tu.",
        )

    @staticmethod
    def _messaggio_della_copia_non_riuscita():
        """Il titolo e il testo del messaggio Raccolta delle partite non
        scritta per la raccolta di Primavera 2 nella cartella del programma.
        Dalla revisione della 10.19.13 dice che i salvataggi ci riprovano
        anche dopo una chiusura di Tornello, e la raccolta ha partite che il
        torneo non ha, non per forza le sue di prima, come quella di un altro
        torneo con lo stesso nome."""
        from config import user_data_path

        cartella = os.path.abspath(user_data_path(""))
        return (
            "Raccolta delle partite non scritta",
            f"La raccolta delle partite Primavera_2 - raccolta partite.pgn, nella cartella {cartella}, ha partite che il torneo Primavera 2 non ha: prima di sostituirla con la raccolta nuova Tornello doveva metterne una copia nella cartella backup, e la copia non è riuscita. Resta com'è, e la raccolta nuova non è stata scritta.\n"
            "I salvataggi ci riprovano, anche dopo una chiusura di Tornello, e fino alla chiusura questo messaggio non si ripete. Se la raccolta di prima non ti serve più, spostala o cancellala tu, e il prossimo salvataggio scriverà quella nuova.",
        )

    def test_se_il_cestino_non_la_prende_resta_e_lo_dice_una_volta(self, principale, suoni, monkeypatch, cestino_finto):
        """Resta com'era, con il suono dell'errore e un messaggio; il
        salvataggio dopo non riprova e non ripete il messaggio. Quando il
        torneo ha di nuovo il PGN la raccolta si scrive, e quando lo perde di
        nuovo si riprova, e il messaggio torna."""
        raccolta, contenuto = self._senza_piu_pgn(principale)
        cestino_finto.prende = False
        rimossi = TestRaccoltaAlSalvataggioNellaFinestra._rimozioni(monkeypatch)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()

        principale._save_state()
        principale._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == contenuto
        assert cestino_finto.tentativi == [os.path.abspath(raccolta)]
        assert rimossi == []
        assert suoni.count("errore") == 1
        messaggio = self._messaggio_della_raccolta_rimasta()
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio]

        principale.current_tournament["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
        principale._save_state()
        principale.current_tournament["rounds"][0]["matches"][1].pop("pgn")
        principale._save_state()

        assert len(cestino_finto.tentativi) == 2
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

    def test_la_raccolta_rimasta_va_nella_cartella_backup_prima_della_nuova(self, principale, suoni, monkeypatch, cestino_finto):
        """Revisione della 10.19.13. Il cestino non prende la raccolta del
        torneo senza piu' PGN, e resta. Al primo PGN nuovo, prima di
        scrivere la raccolta nuova, quella di prima va nella cartella
        backup, con una copia riletta, senza altri messaggi; i salvataggi
        dopo la sostituiscono come sempre, senza altre copie. Fino ad allora
        la raccolta nuova la sostituiva subito, e le partite di prima non
        c'erano piu' in nessun file."""
        raccolta, contenuto = self._senza_piu_pgn(principale)
        cestino_finto.prende = False
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

    @staticmethod
    def _senza_copie_delle_raccolte(monkeypatch):
        """Al posto di copia_di_sicurezza, una che non riesce per le raccolte
        delle partite, e fa le altre copie come sempre. Restituisce quella
        vera, da rimettere quando la copia deve riuscire."""
        import utils

        vera = utils.copia_di_sicurezza

        def senza_copie_delle_raccolte(percorso, *a, **k):
            if percorso.endswith(".pgn"):
                return None
            return vera(percorso, *a, **k)

        monkeypatch.setattr(utils, "copia_di_sicurezza", senza_copie_delle_raccolte)
        return vera

    def test_se_la_copia_non_riesce_la_raccolta_resta(self, principale, suoni, monkeypatch, cestino_finto):
        """La copia nella cartella backup della raccolta rimasta non riesce:
        la raccolta resta com'e', la nuova non si scrive, e un messaggio lo
        dice una volta, con il suono dell'errore. Quando la copia riesce, la
        raccolta nuova si scrive."""
        import utils

        raccolta, contenuto = self._senza_piu_pgn(principale)
        cestino_finto.prende = False
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale._save_state()
        vera = self._senza_copie_delle_raccolte(monkeypatch)
        principale.current_tournament["rounds"][0]["matches"][0]["pgn"] = self.ALTRO_PGN
        finestre.clear()
        suoni.clear()

        principale._save_state()
        principale._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == contenuto
        assert suoni.count("errore") == 1
        assert [(f.titolo, f.testo) for f in finestre] == [self._messaggio_della_copia_non_riuscita()]

        monkeypatch.setattr(utils, "copia_di_sicurezza", vera)
        principale._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN)
        assert len(self._copie_della_raccolta()) == 1

    @pytest.fixture
    def dopo_una_chiusura(self, principale):
        """Tornello che si chiude e si riapre: ogni chiamata da' una finestra
        principale nuova, con la memoria delle raccolte rimaste vuota, come
        all'avvio. I controlli dell'avvio li ha tolti la fixture principale,
        sulla classe della finestra; le finestre si distruggono alla fine."""
        import gui.main_frame as mf
        from gui.settings import DEFAULT_SETTINGS

        nuove = []

        def riapri():
            finestra = mf.MainFrame(None, "Tornello", dict(DEFAULT_SETTINGS))
            finestra._timer_pie_di_pagina.Stop()
            nuove.append(finestra)
            return finestra

        yield riapri
        for finestra in nuove:
            finestra.Destroy()

    def test_dopo_una_chiusura_la_raccolta_rimasta_va_nella_cartella_backup(self, principale, suoni, monkeypatch, dopo_una_chiusura, cestino_finto):
        """Revisione della 10.19.13 (decisione di Gabriele del 4 novembre
        2026). Il cestino non prende la raccolta di Primavera 2, che non ha
        piu' PGN, e il messaggio lo dice. Tornello si chiude e si riapre: la
        finestra nuova ha la memoria delle raccolte rimaste vuota, ma
        all'apertura del torneo, senza partite in PGN e con la sua raccolta
        nella cartella, la raccolta e' una raccolta rimasta. Al primo PGN
        nuovo va nella cartella backup, con una copia identica, prima che la
        raccolta nuova la sostituisca, senza altri messaggi; i salvataggi
        dopo la sostituiscono come sempre. Fino ad allora la copia la faceva
        soltanto una raccolta rimasta nella stessa sessione, e dopo una
        chiusura le partite di prima si perdevano."""
        raccolta, contenuto = self._senza_piu_pgn(principale)
        cestino_finto.prende = False
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale._save_state()
        assert [f.titolo for f in finestre] == ["Raccolta delle partite rimasta"]

        seconda = dopo_una_chiusura()
        seconda.load_tournament(principale.active_filename)
        seconda.current_tournament["rounds"][0]["matches"][0]["pgn"] = self.ALTRO_PGN
        seconda._save_state()

        copie = self._copie_della_raccolta()
        assert len(copie) == 1
        with open(copie[0], "rb") as f:
            assert f.read() == contenuto
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN)
        assert [f.titolo for f in finestre] == ["Raccolta delle partite rimasta"]

        seconda.current_tournament["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
        seconda._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN, PGN_VALIDO)
        assert len(self._copie_della_raccolta()) == 1

    def test_dopo_una_chiusura_un_torneo_con_pgn_non_fa_copie(self, principale, suoni, monkeypatch, dopo_una_chiusura):
        """Revisione della 10.19.13 (decisione di Gabriele del 4 novembre
        2026). Primavera 2 ha il PGN della seconda partita, e il salvataggio
        ne scrive la raccolta. Tornello si chiude e si riapre: all'apertura
        la raccolta e' quella che il torneo scriverebbe, e non e' una
        raccolta rimasta. Al primo PGN nuovo la raccolta nuova la sostituisce
        come sempre, senza copie nella cartella backup e senza messaggi.
        Nella prima stesura della revisione lo diceva la condizione sul PGN
        in raccolta_rimasta_all_apertura, e senza ogni torneo con partite in
        PGN, riaperto, faceva una copia; dalla regola piu' larga lo dice il
        confronto con la raccolta che il torneo scriverebbe."""
        from config import user_data_path

        dati = _torneo_in_corso("Primavera 2")
        dati["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
        percorso = user_data_path("Tornello - Primavera_2.json")
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        principale.load_tournament(percorso)
        principale._save_state()
        raccolta = user_data_path("Primavera_2 - raccolta partite.pgn")
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(PGN_VALIDO)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)

        seconda = dopo_una_chiusura()
        seconda.load_tournament(percorso)
        seconda.current_tournament["rounds"][0]["matches"][0]["pgn"] = self.ALTRO_PGN
        seconda._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN, PGN_VALIDO)
        assert self._copie_della_raccolta() == []
        assert finestre == []

    @pytest.mark.parametrize("prende", [False, True], ids=["il cestino non la prende", "il cestino la prende"])
    def test_dopo_una_chiusura_il_primo_salvataggio_senza_pgn_riprova_il_cestino(self, principale, suoni, monkeypatch, tmp_path, dopo_una_chiusura, cestino_finto, prende):
        """Revisione della 10.19.13. Dopo una chiusura di Tornello la raccolta
        rimasta ritrovata all'apertura non cambia quello che si vede senza
        PGN: il primo salvataggio riprova il cestino, come prima. Se il
        cestino non la prende, si sente l'errore e il messaggio Raccolta
        delle partite rimasta lo dice una volta, e il salvataggio dopo non
        riprova; se la prende, la raccolta va nel cestino, senza messaggi."""
        raccolta, contenuto = self._senza_piu_pgn(principale)
        cestino_finto.prende = False
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale._save_state()
        assert [(f.titolo, f.testo) for f in finestre] == [self._messaggio_della_raccolta_rimasta()]

        seconda = dopo_una_chiusura()
        seconda.load_tournament(principale.active_filename)
        cestino_finto.prende = prende
        cestino_finto.tentativi.clear()
        finestre.clear()
        suoni.clear()

        seconda._save_state()
        seconda._save_state()

        assert cestino_finto.tentativi == [os.path.abspath(raccolta)]
        if prende:
            assert not os.path.exists(raccolta)
            with open(tmp_path / "cestino" / f"0_{os.path.basename(raccolta)}", "rb") as f:
                assert f.read() == contenuto
            assert finestre == []
            assert "errore" not in suoni
        else:
            with open(raccolta, "rb") as f:
                assert f.read() == contenuto
            assert [(f.titolo, f.testo) for f in finestre] == [self._messaggio_della_raccolta_rimasta()]
            assert suoni.count("errore") == 1
        assert self._copie_della_raccolta() == []

    def test_dopo_una_chiusura_la_raccolta_di_un_altra_edizione_segue_la_guardia(self, principale, suoni, monkeypatch, dopo_una_chiusura, cestino_finto):
        """Revisione della 10.19.13. Al posto della raccolta della nuova
        edizione di Primavera 2, nata in console e senza partite in PGN, c'e'
        quella lasciata da Primavera 2 archiviata, identica a quella che il
        suo file scriverebbe: la guardia la copia nella cartella d'archivio
        di quell'edizione, il cestino non la prende, e il messaggio lo dice.
        Dopo una chiusura di Tornello, all'apertura non e' una raccolta
        rimasta della nuova edizione: al primo PGN nuovo la guardia la
        ritrova e lo dice, e la raccolta nuova la sostituisce senza copie
        nella cartella backup, come prima. La copia identica e' gia' nella
        cartella d'archivio."""
        from config import user_data_path

        T = TestRaccoltaAlSalvataggioNellaFinestra
        archiviato, lasciata, contenuto = T._archiviata_con_la_raccolta_lasciata()
        percorso = T._nata_in_console(principale)
        cestino_finto.prende = False
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale._save_state()
        assert [f.titolo for f in finestre] == ["Raccolta delle partite di un altro torneo"]

        seconda = dopo_una_chiusura()
        seconda.load_tournament(percorso)
        seconda.current_tournament["rounds"][0]["matches"][1]["pgn"] = T.PGN_NUOVO
        finestre.clear()
        seconda._save_state()

        cartella = os.path.abspath(user_data_path(""))
        archivio = os.path.join("Closed Tournaments", "2026", "06 Giugno", "Primavera_2")
        assert [(f.titolo, f.testo) for f in finestre] == [
            (
                "Raccolta delle partite di un altro torneo",
                f"Nella cartella {cartella} c'era la raccolta delle partite Primavera_2 - raccolta partite.pgn del torneo Primavera 2, concluso e archiviato nella cartella {archivio}: il torneo Primavera 2 l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
                f"Una copia identica, riletta, adesso è nella cartella d'archivio di quel torneo. Quella della cartella {cartella} non è andata nel cestino, e il torneo Primavera 2 la sostituirà con la sua raccolta.",
            )
        ]
        with open(os.path.join(os.path.dirname(archiviato), "Primavera_2 - raccolta partite.pgn"), "rb") as f:
            assert f.read() == contenuto
        with open(lasciata, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(T.PGN_NUOVO)
        assert self._copie_della_raccolta() == []

    @staticmethod
    def _ripristinato_con_un_altro_pgn(percorso):
        """Il file del torneo com'e' dopo un ripristino dalla finestra Copie
        di sicurezza: torna com'era in una copia, che alla prima partita ha
        il PGN di un'altra partita, ALTRO_PGN, e alla seconda nessuno."""
        import json

        with open(percorso, encoding="utf-8") as f:
            dati = json.load(f)
        dati["rounds"][0]["matches"][0]["pgn"] = TestRaccoltaSenzaPartiteNelCestino.ALTRO_PGN
        dati["rounds"][0]["matches"][1].pop("pgn", None)
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)

    @staticmethod
    def _il_ripristino(finestra, percorso, con_un_altro_torneo):
        """Il ripristino del file del torneo, con ALTRO_PGN, dalla finestra
        Copie di sicurezza della finestra principale finestra, e quello che
        la finestra fa subito dopo, con _dopo_il_ripristino: con nessun
        torneo aperto carica il torneo ripristinato e lo salva; con un altro
        torneo aperto, Estate, aperto prima, rilegge soltanto l'albero."""
        from config import user_data_path
        from copie_di_sicurezza import Esito

        if con_un_altro_torneo:
            altro = user_data_path("Tornello - Estate.json")
            TestNomeDelTorneoNuovo._scrivi(altro, _torneo_in_corso("Estate"))
            finestra.load_tournament(altro)
        TestRaccoltaSenzaPartiteNelCestino._ripristinato_con_un_altro_pgn(percorso)
        finestra._dopo_il_ripristino(Esito(True, tipo="torneo", destinazione=percorso))

    @pytest.mark.parametrize("con_un_altro_torneo", [False, True], ids=["nessun torneo aperto", "un altro torneo aperto"])
    def test_dopo_una_chiusura_il_ripristino_con_partite_in_pgn_fa_la_copia(self, principale, suoni, monkeypatch, dopo_una_chiusura, cestino_finto, con_un_altro_torneo):
        """Revisione della 10.19.13 (decisione di Gabriele del 4 novembre
        2026). Il cestino non prende la raccolta di Primavera 2, che non ha
        piu' PGN, e il messaggio lo dice. Tornello si chiude e si riapre, e
        dalla finestra Copie di sicurezza il torneo torna com'era in una
        copia, con il PGN di un'altra partita: con nessun torneo aperto la
        finestra lo carica e lo salva; con un altro torneo aperto rilegge
        soltanto l'albero, la raccolta resta com'era, e l'arbitro apre il
        torneo e lo salva dopo. All'apertura il torneo ha partite in PGN, ma
        la raccolta ha partite che il torneo non ha: e' una raccolta
        rimasta, e prima di essere sostituita va nella cartella backup, con
        una copia identica, senza altri messaggi; i salvataggi dopo non
        fanno altre copie. Fino ad allora era rimasta soltanto la raccolta di
        un torneo senza partite in PGN, e il primo salvataggio la sostituiva
        senza copia."""
        raccolta, contenuto = self._senza_piu_pgn(principale)
        cestino_finto.prende = False
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale._save_state()
        percorso = principale.active_filename
        assert [(f.titolo, f.testo) for f in finestre] == [self._messaggio_della_raccolta_rimasta()]

        seconda = dopo_una_chiusura()
        self._il_ripristino(seconda, percorso, con_un_altro_torneo)
        if con_un_altro_torneo:
            with open(raccolta, "rb") as f:
                assert f.read() == contenuto
            assert self._copie_della_raccolta() == []
            seconda.load_tournament(percorso)
            seconda._save_state()

        copie = self._copie_della_raccolta()
        assert len(copie) == 1
        with open(copie[0], "rb") as f:
            assert f.read() == contenuto
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN)
        assert [f.titolo for f in finestre] == ["Raccolta delle partite rimasta"]

        seconda._save_state()

        assert len(self._copie_della_raccolta()) == 1

    @pytest.mark.parametrize("strada", ["copia non riuscita dopo il ripristino", "ripristino con un altro torneo aperto"])
    def test_dopo_due_chiusure_la_raccolta_rimasta_va_ancora_nella_cartella_backup(self, principale, suoni, monkeypatch, dopo_una_chiusura, cestino_finto, strada):
        """Revisione della 10.19.13 (decisione di Gabriele del 4 novembre
        2026). Come sopra, ma la raccolta resta com'era anche dopo la
        seconda sessione: o perche' la copia nella cartella backup non
        riesce, e il messaggio Raccolta delle partite non scritta lo dice, o
        perche' il ripristino, con un altro torneo aperto, rilegge soltanto
        l'albero, e il torneo ripristinato non si apre. Dopo una seconda
        chiusura il torneo si apre e si salva: la raccolta ha ancora partite
        che il torneo non ha, e va nella cartella backup prima di essere
        sostituita, senza altri messaggi."""
        import utils

        raccolta, contenuto = self._senza_piu_pgn(principale)
        cestino_finto.prende = False
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale._save_state()
        percorso = principale.active_filename

        seconda = dopo_una_chiusura()
        if strada == "copia non riuscita dopo il ripristino":
            vera = self._senza_copie_delle_raccolte(monkeypatch)
            self._il_ripristino(seconda, percorso, con_un_altro_torneo=False)
            monkeypatch.setattr(utils, "copia_di_sicurezza", vera)
            attesi = [self._messaggio_della_raccolta_rimasta(), self._messaggio_della_copia_non_riuscita()]
        else:
            self._il_ripristino(seconda, percorso, con_un_altro_torneo=True)
            attesi = [self._messaggio_della_raccolta_rimasta()]
        with open(raccolta, "rb") as f:
            assert f.read() == contenuto
        assert self._copie_della_raccolta() == []
        assert [(f.titolo, f.testo) for f in finestre] == attesi

        terza = dopo_una_chiusura()
        terza.load_tournament(percorso)
        terza._save_state()

        copie = self._copie_della_raccolta()
        assert len(copie) == 1
        with open(copie[0], "rb") as f:
            assert f.read() == contenuto
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN)
        assert [(f.titolo, f.testo) for f in finestre] == attesi

    def test_dopo_una_chiusura_la_copia_non_riuscita_si_riprova(self, principale, suoni, monkeypatch, dopo_una_chiusura, cestino_finto):
        """Revisione della 10.19.13 (decisione di Gabriele del 4 novembre
        2026). Il cestino non prende la raccolta di Primavera 2, che non ha
        piu' PGN; poi la prima partita riceve un PGN nuovo, la copia della
        raccolta nella cartella backup non riesce, e il messaggio Raccolta
        delle partite non scritta dice che i salvataggi ci riprovano, anche
        dopo una chiusura di Tornello. Intanto il torneo si salva con il suo
        PGN nuovo. Dopo una chiusura il torneo ha partite in PGN, ma la
        raccolta ha partite che il torneo non ha: il primo salvataggio la
        mette nella cartella backup prima di sostituirla, senza altri
        messaggi. Fino ad allora la sostituiva senza copia e senza
        messaggi."""
        import utils

        raccolta, contenuto = self._senza_piu_pgn(principale)
        cestino_finto.prende = False
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale._save_state()
        vera = self._senza_copie_delle_raccolte(monkeypatch)
        principale.current_tournament["rounds"][0]["matches"][0]["pgn"] = self.ALTRO_PGN
        principale._save_state()
        with open(raccolta, "rb") as f:
            assert f.read() == contenuto
        attesi = [self._messaggio_della_raccolta_rimasta(), self._messaggio_della_copia_non_riuscita()]
        assert [(f.titolo, f.testo) for f in finestre] == attesi
        monkeypatch.setattr(utils, "copia_di_sicurezza", vera)

        seconda = dopo_una_chiusura()
        seconda.load_tournament(principale.active_filename)
        seconda._save_state()

        copie = self._copie_della_raccolta()
        assert len(copie) == 1
        with open(copie[0], "rb") as f:
            assert f.read() == contenuto
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN)
        assert [(f.titolo, f.testo) for f in finestre] == attesi

    def test_la_finalizzazione_in_console_dopo_una_copia_non_riuscita_fa_la_copia(self, principale, suoni, monkeypatch, cestino_finto):
        """Revisione della 10.19.13 (decisione di Gabriele del 4 novembre
        2026). Come sopra, ma dopo la chiusura il torneo si finalizza nella
        versione a riga di comando, che non ha raccolte rimaste da
        ricordare: _raccolta_del_torneo_scritta di ui.py usa la regola
        dell'apertura nella finestra, e la raccolta, che ha partite che il
        torneo non ha, va nella cartella backup prima di essere sostituita,
        senza avvisi. Fino ad allora la sostituiva senza copia."""
        import json

        import ui
        import utils

        raccolta, contenuto = self._senza_piu_pgn(principale)
        cestino_finto.prende = False
        TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale._save_state()
        vera = self._senza_copie_delle_raccolte(monkeypatch)
        principale.current_tournament["rounds"][0]["matches"][0]["pgn"] = self.ALTRO_PGN
        principale._save_state()
        monkeypatch.setattr(utils, "copia_di_sicurezza", vera)
        with open(principale.active_filename, encoding="utf-8") as f:
            torneo = json.load(f)
        avvisi = []

        assert ui._raccolta_del_torneo_scritta(torneo, principale.active_filename, avvisi.append) is True

        copie = self._copie_della_raccolta()
        assert len(copie) == 1
        with open(copie[0], "rb") as f:
            assert f.read() == contenuto
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN)
        assert avvisi == []

    @pytest.mark.parametrize("di_nuovo", [PGN_VALIDO, PGN_VALIDO.replace("1/2-1/2", "*")], ids=["lo stesso PGN", "senza il risultato"])
    def test_la_raccolta_rimasta_con_le_partite_che_il_torneo_ha_di_nuovo_non_fa_copie(self, principale, suoni, monkeypatch, cestino_finto, di_nuovo):
        """Revisione della 10.19.13 (decisione di Gabriele del 4 novembre
        2026). Il cestino non prende la raccolta di Primavera 2, che non ha
        piu' PGN, e resta. Poi la seconda partita riceve di nuovo il suo
        PGN, anche con il risultato in sospeso, come dopo CANC, e la prima
        uno nuovo: la raccolta non ha partite che il torneo non ha, e la
        raccolta nuova la sostituisce senza copie nella cartella backup,
        perche' non c'e' niente da perdere. Fino ad allora ogni raccolta
        rimasta diversa da quella nuova andava nella cartella backup."""
        raccolta, _contenuto = self._senza_piu_pgn(principale)
        cestino_finto.prende = False
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale._save_state()

        principale.current_tournament["rounds"][0]["matches"][0]["pgn"] = self.ALTRO_PGN
        principale.current_tournament["rounds"][0]["matches"][1]["pgn"] = di_nuovo
        principale._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN, di_nuovo)
        assert self._copie_della_raccolta() == []
        assert [f.titolo for f in finestre] == ["Raccolta delle partite rimasta"]

    # Il PGN di una partita come lo scrive la finestra del risultato, con
    # python-chess: pgn_senza_risultato, dopo CANC, ne cambia soltanto il
    # risultato. In PGN_A_CAPO l'ultima riga delle mosse ha 75 caratteri, e
    # python-chess va a capo prima di 1/2-1/2, ma non prima dell'asterisco.
    PGN_ESPORTATO = (
        '[Event "Primavera 2"]\n[Site "N/D"]\n[Date "2026.09.01"]\n[Round "1"]\n'
        '[White "Bianchi, Bruno"]\n[Black "Verdi, Vera"]\n[Result "1-0"]\n\n'
        "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 1-0"
    )
    PGN_A_CAPO = (
        '[Event "Primavera 2"]\n[Site "N/D"]\n[Date "2026.09.01"]\n[Round "1"]\n'
        '[White "Bianchi, Bruno"]\n[Black "Verdi, Vera"]\n[Result "1/2-1/2"]\n\n'
        "1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 Nf6 4. Ng1 Ng8 5. Nf3 Nf6 6. Ng1 Ng8 7. Nf3\n1/2-1/2"
    )

    @pytest.mark.parametrize(
        "fra_le_sessioni",
        ["niente", "una partita giocata in console", "una partita in meno nella raccolta", "il risultato tolto con CANC", "il risultato tolto con CANC, con un a capo in meno"],
    )
    def test_un_torneo_normale_riaperto_e_salvato_non_fa_copie(self, principale, suoni, monkeypatch, dopo_una_chiusura, fra_le_sessioni):
        """Revisione della 10.19.13 (decisione di Gabriele del 4 novembre
        2026). Primavera 2 ha due partite in PGN, e la finestra ne scrive la
        raccolta a ogni salvataggio, come per Autunneo2, aperto e salvato
        molte volte al giorno. Tornello si chiude e si riapre due volte, e
        ogni volta il torneo si apre e si salva, alla fine anche con un PGN
        nuovo: nessuna copia va nella cartella backup, e nessun messaggio.
        Fra la prima sessione e le altre il torneo puo' avere un risultato
        giocato nella versione a riga di comando, che non tocca i PGN e la
        raccolta non la scrive; la raccolta puo' avere una partita in meno
        del torneo, come dopo una raccolta che non si e' potuta scrivere; e
        la prima partita puo' avere il risultato tolto, che nel PGN diventa
        un asterisco, come dopo CANC, mentre la raccolta ha ancora 1-0: e'
        la stessa partita, anche quando con 1/2-1/2 l'ultima riga delle
        mosse andava a capo, e con l'asterisco non ci va piu'."""
        from config import user_data_path
        from tournament import pgn_senza_risultato

        prima = self.PGN_A_CAPO if "a capo" in fra_le_sessioni else self.PGN_ESPORTATO
        dati = _torneo_in_corso("Primavera 2")
        dati["rounds"][0]["matches"][0]["pgn"] = prima
        dati["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
        percorso = user_data_path("Tornello - Primavera_2.json")
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        principale.load_tournament(percorso)
        principale._save_state()
        principale._save_state()
        raccolta = user_data_path("Primavera_2 - raccolta partite.pgn")
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(prima, PGN_VALIDO)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        if fra_le_sessioni == "una partita giocata in console":
            dati["rounds"][0]["matches"][0]["result"] = "1-0"
            TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        elif fra_le_sessioni == "una partita in meno nella raccolta":
            with open(raccolta, "wb") as f:
                f.write(_raccolta_come_la_scrive_la_finestra(self.PGN_ESPORTATO))
        elif fra_le_sessioni.startswith("il risultato tolto con CANC"):
            senza = pgn_senza_risultato(prima)
            if prima == self.PGN_A_CAPO:
                assert senza == prima.replace('"1/2-1/2"', '"*"').replace("\n1/2-1/2", " *")
            else:
                assert senza == prima.replace('"1-0"', '"*"').replace(" 1-0", " *")
            dati["rounds"][0]["matches"][0]["pgn"] = senza
            TestNomeDelTorneoNuovo._scrivi(percorso, dati)

        for _sessione in range(2):
            finestra = dopo_una_chiusura()
            finestra.load_tournament(percorso)
            finestra._save_state()
            finestra._save_state()
        finestra.current_tournament["rounds"][0]["matches"][1]["pgn"] = self.ALTRO_PGN
        finestra._save_state()

        assert self._copie_della_raccolta() == []
        assert finestre == []
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(finestra.current_tournament["rounds"][0]["matches"][0]["pgn"], self.ALTRO_PGN)

    def test_dopo_una_chiusura_il_ripristino_che_cambia_la_seconda_partita_fa_la_copia(self, principale, suoni, monkeypatch, dopo_una_chiusura):
        """Correzione della revisione della 10.19.13. La raccolta di Primavera
        2 ha due partite, e quella che il torneo non ha piu' e' la seconda:
        dopo una chiusura di Tornello, dalla finestra Copie di sicurezza, con
        nessun torneo aperto, il torneo torna com'era in una copia, con la
        stessa prima partita e un'altra seconda. La raccolta e' rimasta, e
        prima di essere sostituita va nella cartella backup, con una copia
        identica, senza messaggi. Nelle altre prove la partita che il torneo
        non ha era la prima della raccolta, o l'unica, e un confronto che si
        fermasse alla prima partita coperta non se ne accorgeva."""
        import json

        from config import user_data_path
        from copie_di_sicurezza import Esito

        dati = _torneo_in_corso("Primavera 2")
        dati["rounds"][0]["matches"][0]["pgn"] = self.PGN_ESPORTATO
        dati["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
        percorso = user_data_path("Tornello - Primavera_2.json")
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        principale.load_tournament(percorso)
        principale._save_state()
        raccolta = user_data_path("Primavera_2 - raccolta partite.pgn")
        contenuto = _raccolta_come_la_scrive_la_finestra(self.PGN_ESPORTATO, PGN_VALIDO)
        with open(raccolta, "rb") as f:
            assert f.read() == contenuto
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)

        seconda = dopo_una_chiusura()
        with open(percorso, encoding="utf-8") as f:
            ripristinato = json.load(f)
        ripristinato["rounds"][0]["matches"][1]["pgn"] = self.ALTRO_PGN
        TestNomeDelTorneoNuovo._scrivi(percorso, ripristinato)
        seconda._dopo_il_ripristino(Esito(True, tipo="torneo", destinazione=percorso))

        copie = self._copie_della_raccolta()
        assert len(copie) == 1
        with open(copie[0], "rb") as f:
            assert f.read() == contenuto
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.PGN_ESPORTATO, self.ALTRO_PGN)
        assert finestre == []

    @pytest.mark.parametrize("sul_disco", ["non in UTF-8", "vuota"])
    def test_dopo_una_chiusura_la_raccolta_non_in_utf8_fa_la_copia_e_quella_vuota_no(self, principale, suoni, monkeypatch, dopo_una_chiusura, sul_disco):
        """Revisione della 10.19.13. Primavera 2 ha il PGN della seconda
        partita, e la finestra ne scrive la raccolta. Fra due sessioni al
        suo posto finisce una raccolta non in UTF-8, con Città scritto in
        cp1252, o una raccolta vuota. Dopo una chiusura il torneo si apre e
        si salva: la raccolta non in UTF-8 non si puo' confrontare, e
        potrebbe avere partite che il torneo non ha, quindi e' rimasta, e
        prima di essere sostituita va nella cartella backup; quella vuota non
        ha partite, e si sostituisce senza copie. Nessun messaggio."""
        from config import user_data_path

        dati = _torneo_in_corso("Primavera 2")
        dati["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
        percorso = user_data_path("Tornello - Primavera_2.json")
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        principale.load_tournament(percorso)
        principale._save_state()
        raccolta = user_data_path("Primavera_2 - raccolta partite.pgn")
        if sul_disco == "non in UTF-8":
            contenuto = _raccolta_come_la_scrive_la_finestra(PGN_VALIDO.replace("Prova", "Città"), self.ALTRO_PGN).decode("utf-8").encode("cp1252")
            with pytest.raises(UnicodeDecodeError):
                contenuto.decode("utf-8")
        else:
            contenuto = b""
        with open(raccolta, "wb") as f:
            f.write(contenuto)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)

        finestra = dopo_una_chiusura()
        finestra.load_tournament(percorso)
        finestra._save_state()

        letti = []
        for copia in self._copie_della_raccolta():
            with open(copia, "rb") as f:
                letti.append(f.read())
        assert letti == ([contenuto] if sul_disco == "non in UTF-8" else [])
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(PGN_VALIDO)
        assert finestre == []

    # La condivisione che un altro programma lascia, aprendo la raccolta
    # con CreateFileW: con FILE_SHARE_READ gli altri la leggono ma non la
    # scrivono, come con un visualizzatore di PGN; con FILE_SHARE_WRITE la
    # scrivono ma non la leggono; con zero non la leggono e non la scrivono.
    FILE_SHARE_READ = 0x1
    FILE_SHARE_WRITE = 0x2

    @staticmethod
    def _bloccata(percorso, condivisione):
        """Apre il file percorso come lo terrebbe aperto un altro programma,
        con un blocco vero di Windows, e restituisce la funzione che lo
        chiude."""
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.restype = ctypes.c_void_p
        kernel32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        generic_read, open_existing = 0x80000000, 3
        maniglia = kernel32.CreateFileW(percorso, generic_read, condivisione, None, open_existing, 0, None)
        assert maniglia not in (None, ctypes.c_void_p(-1).value), ctypes.get_last_error()
        return lambda: kernel32.CloseHandle(maniglia)

    @staticmethod
    def _messaggio_della_raccolta_non_scritta(errore, file="Primavera_2 - raccolta partite.pgn"):
        """Il titolo e il testo del messaggio Raccolta delle partite non
        scritta per la raccolta file, di Primavera 2 se non e' un'altra,
        nella cartella del programma, che un salvataggio non ha potuto
        scrivere, con errore, il motivo che da' il sistema (decisione di
        Gabriele del 5 novembre 2026)."""
        from config import user_data_path

        cartella = os.path.abspath(user_data_path(""))
        return (
            "Raccolta delle partite non scritta",
            f"La raccolta delle partite {file}, nella cartella {cartella}, non si è potuta scrivere: {errore}. "
            "Forse un altro programma la tiene aperta. Il torneo è salvato, e la raccolta si riscrive al prossimo salvataggio.",
        )

    RIGA_DELLA_CONSOLE = "Errore durante il salvataggio della raccolta PGN: "

    @classmethod
    def _errori_in_console(cls, capsys):
        """I motivi degli errori della raccolta che i salvataggi hanno
        stampato in console, una riga per salvataggio, come sempre."""
        righe = capsys.readouterr().out.splitlines()
        return [r[len(cls.RIGA_DELLA_CONSOLE) :] for r in righe if r.startswith(cls.RIGA_DELLA_CONSOLE)]

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_la_raccolta_che_non_si_riscrive_va_nella_cartella_backup_una_volta(self, principale, suoni, monkeypatch, capsys, dopo_una_chiusura):
        """Correzione della revisione della 10.19.13. Primavera 2 ha due
        partite in PGN, e la finestra ne scrive la raccolta. Fra due sessioni
        il torneo torna com'era in una copia, con un altro PGN alla prima
        partita, come dopo un ripristino: all'apertura la raccolta ha una
        partita che il torneo non ha, ed e' rimasta. Un visualizzatore di PGN
        la tiene aperta, e la lascia leggere ma non scrivere: il primo
        salvataggio la mette nella cartella backup e non la riscrive, e i due
        dopo non fanno altre copie. Tolto il blocco, il salvataggio scrive la
        raccolta nuova, con la copia di prima e basta. Fino alla correzione
        ogni salvataggio faceva un'altra copia identica, in silenzio.
        Dalla decisione di Gabriele del 5 novembre 2026 il primo salvataggio
        dice con un messaggio, e con il suono dell'errore, che la raccolta
        non si e' potuta scrivere, con il motivo che da' il sistema, e i due
        dopo non lo ripetono; la console stampa l'errore a ogni salvataggio,
        come prima. Fino ad allora c'era soltanto la riga in console."""
        import json

        from config import user_data_path

        dati = _torneo_in_corso("Primavera 2")
        dati["rounds"][0]["matches"][0]["pgn"] = self.PGN_ESPORTATO
        dati["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
        percorso = user_data_path("Tornello - Primavera_2.json")
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        principale.load_tournament(percorso)
        principale._save_state()
        raccolta = user_data_path("Primavera_2 - raccolta partite.pgn")
        contenuto = _raccolta_come_la_scrive_la_finestra(self.PGN_ESPORTATO, PGN_VALIDO)
        with open(raccolta, "rb") as f:
            assert f.read() == contenuto
        with open(percorso, encoding="utf-8") as f:
            ripristinato = json.load(f)
        ripristinato["rounds"][0]["matches"][0]["pgn"] = self.ALTRO_PGN
        TestNomeDelTorneoNuovo._scrivi(percorso, ripristinato)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()
        capsys.readouterr()

        sblocca = self._bloccata(raccolta, self.FILE_SHARE_READ)
        try:
            seconda = dopo_una_chiusura()
            seconda.load_tournament(percorso)
            for _volta in range(3):
                seconda._save_state()
            copie = self._copie_della_raccolta()
            with open(raccolta, "rb") as f:
                ancora = f.read()
        finally:
            sblocca()

        assert ancora == contenuto
        assert len(copie) == 1
        with open(copie[0], "rb") as f:
            assert f.read() == contenuto
        errori = self._errori_in_console(capsys)
        assert len(errori) == 3
        assert errori[0]
        messaggio = self._messaggio_della_raccolta_non_scritta(_descrizione_dell_errore(errori[0]))
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio]
        assert suoni.count("errore") == 1

        seconda._save_state()

        assert self._copie_della_raccolta() == copie
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN, PGN_VALIDO)
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio]
        assert self._errori_in_console(capsys) == []

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_la_raccolta_rimasta_che_non_si_legge_non_si_sostituisce(self, principale, suoni, monkeypatch, capsys, dopo_una_chiusura):
        """Correzione della revisione della 10.19.13. Come sopra, la raccolta
        ha una partita che il torneo, tornato com'era in una copia, non ha
        piu'. Dopo una chiusura di Tornello un altro programma la tiene
        aperta, e la lascia scrivere ma non leggere: all'apertura non si sa
        se abbia partite che il torneo non ha, e' rimasta, e i salvataggi non
        la sostituiscono, senza copie, perche' non si potrebbe mettere nella
        cartella backup. Tolto il blocco, il salvataggio la mette nella
        cartella backup e poi scrive la raccolta nuova. Se la raccolta che
        non si legge non fosse rimasta, il primo salvataggio la sostituirebbe
        senza copia, e la partita che il torneo non ha si perderebbe.
        Dalla decisione di Gabriele del 5 novembre 2026 il primo dei tre
        salvataggi dice con un messaggio, e con il suono dell'errore, che la
        raccolta non si e' potuta scrivere, con il motivo della lettura che
        non riesce, e gli altri due non lo ripetono. Il messaggio della copia
        non riuscita non c'e': la copia non si e' fatta perche' la raccolta
        non si legge."""
        import json

        from config import user_data_path

        dati = _torneo_in_corso("Primavera 2")
        dati["rounds"][0]["matches"][0]["pgn"] = self.PGN_ESPORTATO
        dati["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
        percorso = user_data_path("Tornello - Primavera_2.json")
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        principale.load_tournament(percorso)
        principale._save_state()
        raccolta = user_data_path("Primavera_2 - raccolta partite.pgn")
        contenuto = _raccolta_come_la_scrive_la_finestra(self.PGN_ESPORTATO, PGN_VALIDO)
        with open(raccolta, "rb") as f:
            assert f.read() == contenuto
        with open(percorso, encoding="utf-8") as f:
            ripristinato = json.load(f)
        ripristinato["rounds"][0]["matches"][0]["pgn"] = self.ALTRO_PGN
        TestNomeDelTorneoNuovo._scrivi(percorso, ripristinato)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()

        capsys.readouterr()
        sblocca = self._bloccata(raccolta, self.FILE_SHARE_WRITE)
        try:
            with pytest.raises(OSError):
                open(raccolta, "rb").close()
            seconda = dopo_una_chiusura()
            seconda.load_tournament(percorso)
            for _volta in range(3):
                seconda._save_state()
        finally:
            sblocca()

        with open(raccolta, "rb") as f:
            assert f.read() == contenuto
        assert self._copie_della_raccolta() == []
        errori = self._errori_in_console(capsys)
        assert len(errori) == 3
        assert errori[0]
        messaggio = self._messaggio_della_raccolta_non_scritta(_descrizione_dell_errore(errori[0]))
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio]
        assert suoni.count("errore") == 1

        seconda._save_state()

        copie = self._copie_della_raccolta()
        assert len(copie) == 1
        with open(copie[0], "rb") as f:
            assert f.read() == contenuto
        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.ALTRO_PGN, PGN_VALIDO)
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio]

    @staticmethod
    def _torneo_normale():
        """Primavera 2 con il PGN della prima partita, come un torneo aperto
        e salvato ogni giorno: la raccolta nella cartella e' quella che il
        torneo scrive. Restituisce il file del torneo, la raccolta e il suo
        contenuto."""
        from config import user_data_path

        dati = _torneo_in_corso("Primavera 2")
        dati["rounds"][0]["matches"][0]["pgn"] = TestRaccoltaSenzaPartiteNelCestino.PGN_ESPORTATO
        percorso = user_data_path("Tornello - Primavera_2.json")
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        raccolta = user_data_path("Primavera_2 - raccolta partite.pgn")
        contenuto = _raccolta_come_la_scrive_la_finestra(TestRaccoltaSenzaPartiteNelCestino.PGN_ESPORTATO)
        with open(raccolta, "wb") as f:
            f.write(contenuto)
        return percorso, raccolta, contenuto

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_la_raccolta_che_non_si_legge_non_ha_partite_in_piu(self, principale, suoni, monkeypatch, capsys, dopo_una_chiusura):
        """Correzione della revisione della 10.19.13. Primavera 2 e' un torneo
        normale, e la sua raccolta e' quella che il torneo scrive. Dopo una
        chiusura di Tornello un altro programma la tiene aperta, e non la
        lascia ne' leggere ne' scrivere: all'apertura e ai salvataggi, anche
        con un PGN nuovo, la raccolta resta com'era, e nessuna copia va nella
        cartella backup; l'errore si stampa. Tolto il blocco, il salvataggio
        scrive la raccolta nuova senza copie, perche' quella di prima ha
        soltanto partite del torneo. Fino alla correzione una raccolta che
        non si leggeva aveva partite che il torneo non ha, e il messaggio
        della copia non riuscita, con il suono dell'errore, lo diceva anche
        della raccolta del torneo.
        Dalla decisione di Gabriele del 5 novembre 2026 il primo dei tre
        salvataggi dice soltanto, con un messaggio e con il suono
        dell'errore, che la raccolta non si e' potuta scrivere, con il motivo
        che da' il sistema, e gli altri due non lo ripetono; il messaggio
        della copia non riuscita non c'e' mai."""
        percorso, raccolta, contenuto = self._torneo_normale()
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        capsys.readouterr()

        sblocca = self._bloccata(raccolta, 0)
        try:
            seconda = dopo_una_chiusura()
            seconda.load_tournament(percorso)
            suoni.clear()
            seconda._save_state()
            seconda.current_tournament["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
            seconda._save_state()
            seconda._save_state()
        finally:
            sblocca()

        with open(raccolta, "rb") as f:
            assert f.read() == contenuto
        assert self._copie_della_raccolta() == []
        errori = self._errori_in_console(capsys)
        assert len(errori) == 3
        assert errori[0]
        messaggio = self._messaggio_della_raccolta_non_scritta(_descrizione_dell_errore(errori[0]))
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio]
        assert suoni.count("errore") == 1

        seconda._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == _raccolta_come_la_scrive_la_finestra(self.PGN_ESPORTATO, PGN_VALIDO)
        assert self._copie_della_raccolta() == []
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio]

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_il_messaggio_della_raccolta_non_scritta_una_volta_fino_alla_chiusura(self, principale, suoni, monkeypatch, capsys, dopo_una_chiusura):
        """Decisione di Gabriele del 5 novembre 2026. Primavera 2 e' un
        torneo normale, aperto nella finestra. Un visualizzatore di PGN
        tiene aperta la sua raccolta, e la lascia leggere ma non scrivere: il
        salvataggio con un PGN nuovo non la scrive, e il messaggio lo dice,
        con il suono dell'errore e con il motivo che da' il sistema, lo
        stesso della riga in console. Tolto il blocco, il salvataggio la
        scrive. Bloccata di nuovo, i due salvataggi dopo, con un altro
        risultato nel PGN, non la scrivono, e il messaggio non torna: si dice
        una volta per quella raccolta, fino alla chiusura di Tornello. Dopo
        una chiusura il primo salvataggio che non la scrive lo dice di nuovo,
        una volta, e nessuna copia va nella cartella backup."""
        percorso, raccolta, contenuto = self._torneo_normale()
        principale.load_tournament(percorso)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()
        capsys.readouterr()

        sblocca = self._bloccata(raccolta, self.FILE_SHARE_READ)
        try:
            principale.current_tournament["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
            principale._save_state()
            with open(raccolta, "rb") as f:
                ancora = f.read()
        finally:
            sblocca()

        assert ancora == contenuto
        errori = self._errori_in_console(capsys)
        assert len(errori) == 1
        assert errori[0]
        messaggio = self._messaggio_della_raccolta_non_scritta(_descrizione_dell_errore(errori[0]))
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio]
        assert suoni.count("errore") == 1

        principale._save_state()
        scritta = _raccolta_come_la_scrive_la_finestra(self.PGN_ESPORTATO, PGN_VALIDO)
        with open(raccolta, "rb") as f:
            assert f.read() == scritta

        # Un altro risultato nel PGN della seconda partita: la raccolta da
        # riscrivere ha le stesse partite, e non e' una raccolta rimasta.
        sblocca = self._bloccata(raccolta, self.FILE_SHARE_READ)
        try:
            principale.current_tournament["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO.replace("1/2-1/2", "1-0")
            principale._save_state()
            principale._save_state()
            with open(raccolta, "rb") as f:
                ancora = f.read()
            assert len(self._errori_in_console(capsys)) == 2
            assert [(f.titolo, f.testo) for f in finestre] == [messaggio]
            assert suoni.count("errore") == 1

            seconda = dopo_una_chiusura()
            seconda.load_tournament(percorso)
            seconda._save_state()
            seconda._save_state()
        finally:
            sblocca()

        assert ancora == scritta
        assert len(self._errori_in_console(capsys)) == 2
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio] * 2
        assert suoni.count("errore") == 2
        assert self._copie_della_raccolta() == []

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    @pytest.mark.parametrize("dopo", ["un altro torneo", "il nome nuovo da Dati"])
    def test_il_messaggio_della_raccolta_non_scritta_una_volta_per_raccolta(self, principale, suoni, monkeypatch, capsys, dopo):
        """Decisione di Gabriele del 5 novembre 2026. Un visualizzatore di
        PGN tiene aperta la raccolta di Primavera 2, aperta nella finestra, e
        il salvataggio con un PGN nuovo non la scrive: il messaggio lo dice.
        Poi, nella stessa sessione, la finestra salva un'altra raccolta,
        quella di Estate 3, aperto dopo, oppure quella che Primavera 2 scrive
        con il nome Primavera 3, preso dal ramo Dati, con lo stesso file del
        torneo, e anche quella e' tenuta aperta: il messaggio esce di nuovo,
        con il nome di quella raccolta, perche' si dice una volta per
        raccolta, e non una volta per finestra o per file del torneo. Il
        salvataggio dopo, con la raccolta ancora bloccata, non lo ripete."""
        from config import user_data_path

        percorso, raccolta, _contenuto = self._torneo_normale()
        principale.load_tournament(percorso)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()
        capsys.readouterr()

        sblocca = self._bloccata(raccolta, self.FILE_SHARE_READ)
        try:
            principale.current_tournament["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
            principale._save_state()
        finally:
            sblocca()

        errori = self._errori_in_console(capsys)
        assert len(errori) == 1
        assert errori[0]
        primo = self._messaggio_della_raccolta_non_scritta(_descrizione_dell_errore(errori[0]))
        assert [(f.titolo, f.testo) for f in finestre] == [primo]

        if dopo == "un altro torneo":
            dati = _torneo_in_corso("Estate 3")
            dati["rounds"][0]["matches"][0]["pgn"] = self.PGN_ESPORTATO
            altro = user_data_path("Tornello - Estate_3.json")
            TestNomeDelTorneoNuovo._scrivi(altro, dati)
            file = "Estate_3 - raccolta partite.pgn"
            with open(user_data_path(file), "wb") as f:
                f.write(_raccolta_come_la_scrive_la_finestra(self.PGN_ESPORTATO))
            principale.load_tournament(altro)
            pgn = PGN_VALIDO
        else:
            TestNomeEDataDiInizioDaDati._campo(principale, monkeypatch, percorso, "name", "Primavera 3")
            file = "Primavera_3 - raccolta partite.pgn"
            pgn = PGN_VALIDO.replace("1/2-1/2", "1-0")
        seconda = user_data_path(file)
        assert os.path.isfile(seconda)
        assert [(f.titolo, f.testo) for f in finestre] == [primo]
        capsys.readouterr()

        sblocca = self._bloccata(seconda, self.FILE_SHARE_READ)
        try:
            principale.current_tournament["rounds"][0]["matches"][1]["pgn"] = pgn
            principale._save_state()
            principale._save_state()
        finally:
            sblocca()

        errori = self._errori_in_console(capsys)
        assert len(errori) == 2
        assert errori[0]
        assert [(f.titolo, f.testo) for f in finestre] == [primo, self._messaggio_della_raccolta_non_scritta(_descrizione_dell_errore(errori[0]), file)]
        assert suoni.count("errore") == 2

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_la_copia_non_riuscita_non_torna_dopo_la_raccolta_non_scritta(self, principale, suoni, monkeypatch, capsys, cestino_finto):
        """Correzione della revisione della 10.19.13. Il cestino non prende
        la raccolta di Primavera 2, che resta, e il torneo ha un PGN nuovo: la
        copia nella cartella backup non riesce, e il messaggio dice che fino
        alla chiusura non si ripete. Al salvataggio dopo un altro programma
        tiene la raccolta, e non la lascia leggere: il messaggio della
        raccolta non scritta lo dice. Tolto il blocco, la copia non riesce
        ancora, e i due salvataggi non ripetono nessun messaggio. Fino alla
        correzione il salvataggio che non scriveva la raccolta svuotava la
        memoria della copia non riuscita, e il suo messaggio tornava."""
        raccolta, contenuto = self._senza_piu_pgn(principale)
        cestino_finto.prende = False
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()
        principale._save_state()
        self._senza_copie_delle_raccolte(monkeypatch)
        principale.current_tournament["rounds"][0]["matches"][0]["pgn"] = self.ALTRO_PGN
        principale._save_state()
        capsys.readouterr()

        sblocca = self._bloccata(raccolta, self.FILE_SHARE_WRITE)
        try:
            principale._save_state()
        finally:
            sblocca()
        errori = self._errori_in_console(capsys)
        principale._save_state()
        principale._save_state()

        with open(raccolta, "rb") as f:
            assert f.read() == contenuto
        assert self._copie_della_raccolta() == []
        assert len(errori) == 1
        assert errori[0]
        assert [(f.titolo, f.testo) for f in finestre] == [
            self._messaggio_della_raccolta_rimasta(),
            self._messaggio_della_copia_non_riuscita(),
            self._messaggio_della_raccolta_non_scritta(_descrizione_dell_errore(errori[0])),
        ]
        assert suoni.count("errore") == 3

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_la_finalizzazione_in_console_con_la_raccolta_che_non_si_legge(self, suoni, capsys):
        """Correzione della revisione della 10.19.13. Lo stesso torneo
        normale si finalizza nella versione a riga di comando, mentre un
        altro programma tiene aperta la raccolta, senza lasciarla ne'
        leggere ne' scrivere: la raccolta resta com'era, nessuna copia va
        nella cartella backup, e l'avviso dice che non si e' potuta
        scrivere, con l'errore. Fino alla correzione diceva che la raccolta
        aveva partite che il torneo non ha, e che la copia nella cartella
        backup non era riuscita. Dalla proposta 6 del nono giro l'avviso
        dice dell'errore soltanto la descrizione, perche' nomina gia' il
        file e la cartella; il testo intero resta in console."""
        import json

        import ui

        percorso, raccolta, contenuto = self._torneo_normale()
        with open(percorso, encoding="utf-8") as f:
            torneo = json.load(f)
        avvisi = []
        capsys.readouterr()

        sblocca = self._bloccata(raccolta, 0)
        try:
            scritta = ui._raccolta_del_torneo_scritta(torneo, percorso, avvisi.append)
        finally:
            sblocca()

        assert scritta is False
        cartella = os.path.dirname(os.path.abspath(raccolta))
        della_raccolta = self._errori_in_console(capsys)
        assert len(della_raccolta) == 1
        assert len(avvisi) == 1
        assert avvisi[0].split("\n")[0] == (
            f"La raccolta delle partite Primavera_2 - raccolta partite.pgn del torneo Primavera 2 non si è potuta scrivere nella cartella {cartella}: "
            f"{_descrizione_dell_errore(della_raccolta[0])}"
        )
        assert avvisi[0].endswith(
            f"\nNon va in archivio con il torneo, e nella cartella {cartella} resta quella che c'era prima, che non ha le partite del torneo come sono alla fine: "
            "se non ti serve più, spostala o cancellala tu. Le partite del torneo restano nel suo file, in archivio."
        )
        assert self._copie_della_raccolta() == []
        with open(raccolta, "rb") as f:
            assert f.read() == contenuto


class TestTorneoCheNonSiSalva:
    """Dalla 10.19.19 (decisione di Gabriele del 5 novembre 2026) un
    salvataggio della finestra che non riesce a scrivere il file del torneo,
    per esempio perche' un altro programma lo tiene bloccato, lo dice con il
    suono dell'errore e il messaggio Torneo non salvato, con il motivo che
    da' il sistema: una volta, finche' un salvataggio di quel torneo non
    riesce di nuovo, o finche' il torneo non esce dalla memoria, quando si
    riapre dal suo file o nessun torneo resta aperto (correzione della
    revisione della 10.19.19). Mentre il torneo non si salva, il messaggio della
    raccolta non scritta, che direbbe che il torneo e' salvato, non esce.
    Fino alla 10.19.18, e gia' nella 10.0.0, lo diceva soltanto la riga in
    console, che resta com'era. I blocchi sono veri, con CreateFileW, come
    nelle prove della raccolta non scritta: il file del torneo si lascia
    leggere, ma non sostituire. Le finestre di messaggio sono finte."""

    RIGA_DELLA_CONSOLE = "Errore durante il salvataggio del torneo ({percorso}): "

    @classmethod
    def _errori_in_console(cls, capsys, percorso):
        """I motivi degli errori che i salvataggi hanno stampato in console,
        una riga per salvataggio, come sempre: quelli del file del torneo
        percorso e quelli della raccolta delle partite."""
        prefisso = cls.RIGA_DELLA_CONSOLE.format(percorso=percorso)
        della_raccolta = TestRaccoltaSenzaPartiteNelCestino.RIGA_DELLA_CONSOLE
        righe = capsys.readouterr().out.splitlines()
        return (
            [r[len(prefisso) :] for r in righe if r.startswith(prefisso)],
            [r[len(della_raccolta) :] for r in righe if r.startswith(della_raccolta)],
        )

    @staticmethod
    def _messaggio(percorso, errore, nome="Primavera 2"):
        """Il titolo e il testo del messaggio Torneo non salvato per il
        torneo nome, Primavera 2 se non e' un altro, nel file percorso, con
        errore, il motivo che da' il sistema."""
        return (
            "Torneo non salvato",
            f"Il torneo {nome} non si è potuto salvare nel file {percorso}: {errore}. "
            "Le ultime modifiche sono soltanto in memoria, e Tornello riprova a ogni salvataggio. Se un altro programma tiene aperto il file, chiudilo.",
        )

    @staticmethod
    def _aperto(principale, monkeypatch):
        """Primavera 2, un torneo normale con la sua raccolta, aperto nella
        finestra, con le finestre di messaggio annotate. Restituisce il file
        del torneo, la raccolta e le finestre."""
        percorso, raccolta, _contenuto = TestRaccoltaSenzaPartiteNelCestino._torneo_normale()
        principale.load_tournament(percorso)
        assert principale._e_il_torneo_aperto(percorso)
        return principale.active_filename, raccolta, TestNomeDelTorneoNuovo._domande(monkeypatch)

    @staticmethod
    def _salvataggi_bloccati(principale, *file, volte=3):
        """I salvataggi della finestra, volte di fila, con file tenuti aperti
        da un altro programma, che li lascia leggere ma non scrivere."""
        bloccati = [TestRaccoltaSenzaPartiteNelCestino._bloccata(f, TestRaccoltaSenzaPartiteNelCestino.FILE_SHARE_READ) for f in file]
        try:
            for _volta in range(volte):
                principale._save_state()
        finally:
            for sblocca in bloccati:
                sblocca()

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_il_messaggio_una_volta_finche_un_salvataggio_non_riesce(self, principale, suoni, monkeypatch, capsys):
        """Primavera 2 cambia luogo, e un altro programma tiene aperto il suo
        file: dei tre salvataggi soltanto il primo dice il messaggio, con il
        suono dell'errore e lo stesso motivo della riga in console, che c'e'
        a ogni salvataggio. Il file resta com'era, e il luogo nuovo resta in
        memoria. Tolto il blocco, il salvataggio scrive il luogo nuovo, senza
        messaggi: Tornello riprova davvero. Bloccato di nuovo, il messaggio
        torna, una volta in altri tre salvataggi."""
        percorso, _raccolta, finestre = self._aperto(principale, monkeypatch)
        with open(percorso, "rb") as f:
            prima = f.read()
        suoni.clear()
        capsys.readouterr()
        principale.current_tournament["site"] = "Roma"

        self._salvataggi_bloccati(principale, percorso)

        with open(percorso, "rb") as f:
            assert f.read() == prima
        assert principale.current_tournament["site"] == "Roma"
        errori, della_raccolta = self._errori_in_console(capsys, percorso)
        assert len(errori) == 3
        assert errori[0].startswith("[WinError ")
        assert repr(percorso) in errori[0]
        assert della_raccolta == []
        messaggio = self._messaggio(percorso, _descrizione_dell_errore(errori[0]))
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [(*messaggio, False)]
        assert "WinError" not in messaggio[1]
        assert repr(percorso) not in messaggio[1]
        assert suoni.count("errore") == 1

        principale._save_state()

        assert TestNomeEDataDiInizioDaDati._nel_file(percorso)["site"] == "Roma"
        assert self._errori_in_console(capsys, percorso) == ([], [])
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio]
        assert suoni.count("errore") == 1

        self._salvataggi_bloccati(principale, percorso)

        errori, _della_raccolta = self._errori_in_console(capsys, percorso)
        assert len(errori) == 3
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio, self._messaggio(percorso, _descrizione_dell_errore(errori[0]))]
        assert suoni.count("errore") == 2

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_la_raccolta_non_scritta_non_si_dice_mentre_il_torneo_non_si_salva(self, principale, suoni, monkeypatch, capsys):
        """Primavera 2 ha un PGN nuovo, e un altro programma tiene aperti il
        suo file e la sua raccolta: dei tre salvataggi il primo dice soltanto
        Torneo non salvato, e il messaggio della raccolta non scritta, che
        direbbe che il torneo e' salvato, non esce; la console stampa i due
        errori a ogni salvataggio, come prima. Tolto il blocco del file del
        torneo, il salvataggio lo scrive, e il messaggio della raccolta non
        scritta esce allora, una volta, perche' adesso e' vero. Fino alla
        10.19.18 il primo salvataggio diceva soltanto che la raccolta non si
        era scritta, e che il torneo era salvato."""
        percorso, raccolta, finestre = self._aperto(principale, monkeypatch)
        suoni.clear()
        capsys.readouterr()
        principale.current_tournament["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO

        self._salvataggi_bloccati(principale, percorso, raccolta)

        errori, della_raccolta = self._errori_in_console(capsys, percorso)
        assert len(errori) == 3
        assert len(della_raccolta) == 3
        messaggio = self._messaggio(percorso, _descrizione_dell_errore(errori[0]))
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio]
        assert suoni.count("errore") == 1

        self._salvataggi_bloccati(principale, raccolta, volte=2)

        errori, della_raccolta = self._errori_in_console(capsys, percorso)
        assert errori == []
        assert len(della_raccolta) == 2
        assert TestNomeEDataDiInizioDaDati._nel_file(percorso)["rounds"][0]["matches"][1]["pgn"] == PGN_VALIDO
        raccolta_non_scritta = TestRaccoltaSenzaPartiteNelCestino._messaggio_della_raccolta_non_scritta(_descrizione_dell_errore(della_raccolta[0]))
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio, raccolta_non_scritta]
        assert suoni.count("errore") == 2

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_dopo_una_time_machine_riuscita_il_messaggio_torna(self, principale, suoni, monkeypatch, capsys, cestino_finto):
        """Anche la Time Machine che scrive il file del torneo e' un
        salvataggio riuscito. Il file di Primavera 2 bloccato non si salva, e
        il messaggio esce; tolto il blocco, Ctrl+Z, con Si', riporta il torneo
        in preparazione e lo salva. Bloccato di nuovo, il primo salvataggio
        dice di nuovo il messaggio. Il cestino e' finto."""
        percorso, _raccolta, finestre = self._aperto(principale, monkeypatch)
        capsys.readouterr()

        self._salvataggi_bloccati(principale, percorso, volte=1)
        principale.on_rollback_round(None)

        assert TestNomeEDataDiInizioDaDati._nel_file(percorso)["rounds"] == []
        self._salvataggi_bloccati(principale, percorso, volte=2)

        errori, _della_raccolta = self._errori_in_console(capsys, percorso)
        assert len(errori) == 3
        non_salvato = [(f.titolo, f.testo) for f in finestre if f.titolo == "Torneo non salvato"]
        assert non_salvato == [self._messaggio(percorso, _descrizione_dell_errore(errori[0])), self._messaggio(percorso, _descrizione_dell_errore(errori[1]))]
        assert [f.titolo for f in finestre] == ["Torneo non salvato", "Annulla Turno", "Torneo non salvato"]

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_il_messaggio_si_dice_per_ogni_torneo(self, principale, suoni, monkeypatch, capsys):
        """Il messaggio si ricorda per il file del torneo: dopo quello di
        Primavera 2, che non si e' salvata, Estate 3 aperta nella stessa
        sessione, con il suo file bloccato, ha il suo, una volta."""
        from config import user_data_path

        primavera, _raccolta, finestre = self._aperto(principale, monkeypatch)
        estate = user_data_path("Tornello - Estate_3.json")
        TestNomeDelTorneoNuovo._scrivi(estate, _torneo_in_corso("Estate 3"))
        suoni.clear()
        capsys.readouterr()

        self._salvataggi_bloccati(principale, primavera, volte=2)
        errori_primavera, _della_raccolta = self._errori_in_console(capsys, primavera)
        principale.load_tournament(estate)
        assert principale._e_il_torneo_aperto(estate)
        estate = principale.active_filename
        self._salvataggi_bloccati(principale, estate, volte=2)
        errori_estate, _della_raccolta = self._errori_in_console(capsys, estate)

        assert len(errori_primavera) == 2
        assert len(errori_estate) == 2
        assert [(f.titolo, f.testo) for f in finestre] == [
            self._messaggio(primavera, _descrizione_dell_errore(errori_primavera[0])),
            self._messaggio(estate, _descrizione_dell_errore(errori_estate[0]), nome="Estate 3"),
        ]
        assert suoni.count("errore") == 2

    def test_un_file_con_il_nome_vuoto(self, principale, suoni, monkeypatch, capsys):
        """Un file di torneo scritto a mano con il nome vuoto, che dal ramo
        Dati dalla 10.19.17 non si puo' piu' dare, si apre, e i suoi
        salvataggi non riescono: save_tournament fa arrivare come motivo la
        frase che stampa in console, a ogni salvataggio come prima, e il
        messaggio la dice una volta."""
        from config import user_data_path

        percorso = user_data_path("Tornello - Senza_nome.json")
        TestNomeDelTorneoNuovo._scrivi(percorso, _torneo_in_corso(""))
        principale.load_tournament(percorso)
        assert principale._e_il_torneo_aperto(percorso)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()
        capsys.readouterr()

        principale._save_state()
        principale._save_state()

        frase = "Errore: Nome del torneo non presente. Impossibile salvare."
        assert capsys.readouterr().out.splitlines().count(frase) == 2
        assert [(f.titolo, f.testo) for f in finestre] == [self._messaggio(principale.active_filename, frase[:-1], nome="")]
        assert suoni.count("errore") == 1

    def test_il_motivo_di_un_errore_che_non_viene_dal_sistema(self, principale, suoni, monkeypatch, capsys):
        """Correzione della revisione della 10.19.19. Un errore che non viene
        dal sistema, come un insieme in un campo del torneo, che il JSON non
        sa scrivere: il messaggio dice lo stesso motivo della riga Errore
        imprevisto in console, e il file resta com'era. Fino alla revisione
        nessuna prova guardava il motivo di questo errore."""
        percorso, _raccolta, finestre = self._aperto(principale, monkeypatch)
        with open(percorso, "rb") as f:
            prima = f.read()
        suoni.clear()
        capsys.readouterr()
        principale.current_tournament["campo_strano"] = {1, 2}

        principale._save_state()

        prefisso = "Errore imprevisto durante il salvataggio del torneo: "
        motivi = [r[len(prefisso) :] for r in capsys.readouterr().out.splitlines() if r.startswith(prefisso)]
        assert len(motivi) == 1
        assert motivi[0]
        with open(percorso, "rb") as f:
            assert f.read() == prima
        assert [(f.titolo, f.testo) for f in finestre] == [self._messaggio(percorso, motivi[0])]
        assert suoni.count("errore") == 1

    def test_un_errore_del_sistema_senza_descrizione(self, principale, suoni, monkeypatch, capsys):
        """Revisione della 10.19.19. Un OSError senza descrizione, come
        quello che una libreria solleva con il solo messaggio: per Gabriele,
        senza strerror il motivo e' il testo intero, e il messaggio Torneo
        non salvato dice disco pieno, come la riga in console. La scrittura
        del file del torneo e' finta. Fino alla revisione del nono giro
        nessuna prova guardava questo ripiego, e senza il ripiego
        _save_state cadeva con TypeError."""
        import tournament

        percorso, _raccolta, finestre = self._aperto(principale, monkeypatch)
        suoni.clear()
        capsys.readouterr()

        def senza_descrizione(file, dati, indent=1):
            raise OSError("disco pieno")

        monkeypatch.setattr(tournament, "scrivi_json_atomico", senza_descrizione)
        principale._save_state()

        errori, _della_raccolta = self._errori_in_console(capsys, percorso)
        assert errori == ["disco pieno"]
        assert [(f.titolo, f.testo) for f in finestre] == [self._messaggio(percorso, "disco pieno")]
        assert suoni.count("errore") == 1

    def test_la_raccolta_con_un_errore_del_sistema_senza_descrizione(self, principale, suoni, monkeypatch, capsys):
        """Revisione della 10.19.13. La scrittura della raccolta delle
        partite di Primavera 2, che ha un PGN nuovo, solleva un OSError senza
        descrizione: il torneo si salva, e il messaggio Raccolta delle
        partite non scritta dice disco pieno, il testo intero, come la riga
        in console. Fino alla revisione del nono giro nessuna prova guardava
        questo ripiego, e senza il ripiego il messaggio non usciva."""
        import builtins

        import omonimi

        percorso, raccolta, finestre = self._aperto(principale, monkeypatch)
        suoni.clear()
        capsys.readouterr()
        vera = builtins.open

        def apri(file, mode="r", *argomenti, **opzioni):
            if "w" in mode and os.path.normcase(os.path.abspath(file)) == os.path.normcase(os.path.abspath(raccolta)):
                raise OSError("disco pieno")
            return vera(file, mode, *argomenti, **opzioni)

        monkeypatch.setattr(omonimi, "open", apri, raising=False)
        principale.current_tournament["rounds"][0]["matches"][1]["pgn"] = PGN_VALIDO
        principale._save_state()

        assert TestNomeEDataDiInizioDaDati._nel_file(percorso)["rounds"][0]["matches"][1]["pgn"] == PGN_VALIDO
        errori, della_raccolta = self._errori_in_console(capsys, percorso)
        assert errori == []
        assert della_raccolta == ["disco pieno"]
        assert [(f.titolo, f.testo) for f in finestre] == [TestRaccoltaSenzaPartiteNelCestino._messaggio_della_raccolta_non_scritta("disco pieno")]
        assert suoni.count("errore") == 1

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_il_messaggio_torna_quando_il_torneo_si_riapre(self, principale, suoni, monkeypatch, capsys):
        """Correzione della revisione della 10.19.19. Primavera 2 cambia luogo
        con il suo file bloccato, e il messaggio esce. Poi il cursore scende
        su Estate 3 e risale su Primavera 2, che si riapre dal suo file,
        ancora bloccato: il torneo letto dal file non ha modifiche soltanto in
        memoria, e quando il luogo cambia di nuovo il messaggio torna, una
        volta in due salvataggi. Fino alla revisione il ricordo del messaggio
        restava, e la finestra non diceva piu' niente."""
        from config import user_data_path

        primavera, _raccolta, finestre = self._aperto(principale, monkeypatch)
        estate = user_data_path("Tornello - Estate_3.json")
        TestNomeDelTorneoNuovo._scrivi(estate, _torneo_in_corso("Estate 3"))
        suoni.clear()
        capsys.readouterr()
        bloccata = TestRaccoltaSenzaPartiteNelCestino._bloccata(primavera, TestRaccoltaSenzaPartiteNelCestino.FILE_SHARE_READ)
        try:
            principale.current_tournament["site"] = "Roma"
            principale._save_state()
            principale.load_tournament(estate, rebuild_tree=False)
            principale.load_tournament(primavera, rebuild_tree=False)
            assert principale._e_il_torneo_aperto(primavera)
            principale.current_tournament["site"] = "Milano"
            principale._save_state()
            principale._save_state()
        finally:
            bloccata()

        errori, _della_raccolta = self._errori_in_console(capsys, primavera)
        assert len(errori) == 3
        assert [(f.titolo, f.testo) for f in finestre] == [self._messaggio(primavera, _descrizione_dell_errore(errori[0])), self._messaggio(primavera, _descrizione_dell_errore(errori[1]))]
        assert suoni.count("errore") == 2

    @staticmethod
    def _scrittura_negata(monkeypatch):
        """La scrittura del file del torneo che solleva PermissionError, come
        con la cartella del programma che non si puo' scrivere o con il disco
        pieno. Restituisce la scrittura vera, per rimetterla."""
        import tournament

        vera = tournament.scrivi_json_atomico

        def negata(percorso, dati, indent=1):
            raise PermissionError(13, "Accesso negato", percorso)

        monkeypatch.setattr(tournament, "scrivi_json_atomico", negata)
        return vera

    @staticmethod
    def _creato(principale, nome, luogo="Online"):
        """La procedura guidata, dall'inizio, con il nome nome, il luogo
        luogo e i quattro iscritti dei tornei delle prove, fino alla
        creazione del torneo."""
        principale.start_new_tournament_wizard()
        principale.creation_data["name"] = nome
        principale.creation_data["site"] = luogo
        principale.create_tournament_from_wizard(TestNomeDelTorneoNuovo._iscritti())

    @staticmethod
    def _aperto_dalla_memoria(principale, percorso, nome):
        """Il torneo nuovo nome, che non si e' salvato nel file percorso, e'
        quello aperto, con i quattro iscritti, il titolo e la barra di stato
        che lo dicono; la sua voce nell'albero viene dalla memoria, e dice
        soltanto il nome, perche' il suo file va nella cartella del
        programma: fino alla proposta 2 del nono giro diceva fra parentesi
        la cartella del suo file. Il cursore sta sulla voce
        calcola il turno 1, nel ramo turni del torneo, come dopo una
        creazione riuscita: fino alla correzione della revisione della
        10.19.20 qui, nel manuale e nel ChangeLog c'era scritto Avvio
        torneo, la voce con la stessa azione in fondo all'albero."""
        assert not os.path.exists(percorso)
        assert not principale.creation_mode
        assert principale._e_il_torneo_aperto(percorso)
        assert principale.current_tournament["name"] == nome
        assert [p["id"] for p in principale.current_tournament["players"]] == [g[0] for g in GIOCATORI_DEI_TORNEI]
        assert f"[{nome}]" in principale.GetTitle()
        assert principale.last_status_msg == "Torneo creato, ma non ancora salvato nel suo file."
        voce = principale._voce_del_torneo_aperto()
        assert voce is not None
        assert principale.tree_ctrl.GetItemText(voce) == nome
        scelta = principale.tree_ctrl.GetSelection()
        assert principale.tree_ctrl.GetItemData(scelta) == {
            "action": "start_tournament_matchmaking_action",
            "filepath": principale.active_filename,
        }
        assert principale.tree_ctrl.GetItemText(scelta) == "calcola il turno 1"
        assert principale.tree_ctrl.GetItemText(principale.tree_ctrl.GetItemParent(scelta)) == "turni (0)"

    def test_la_procedura_guidata_che_non_salva_lo_dice_ogni_volta(self, principale, suoni, monkeypatch):
        """Correzione della revisione della 10.19.19. Il torneo nuovo della
        procedura guidata non si salva, perche' il suo file non si scrive,
        come con la cartella del programma che non si puo' scrivere: il
        messaggio esce, e dalla 10.19.20 il torneo resta aperto. Il secondo
        tentativo, con lo stesso nome, lo dice di nuovo, una volta, e il
        torneo aperto e' il secondo. Fino alla revisione il ricordo del
        messaggio restava, e il secondo tentativo non lo diceva. Dalla
        10.19.21 il secondo tentativo comincia con la domanda di
        TestTorneoNonSalvatoDaLasciare, perche' il primo torneo nuovo ha le
        ultime modifiche soltanto in memoria, e con Si' parte; dalla proposta
        4 del nono giro la domanda dice che il suo file non c'e' ancora, e
        che lasciandolo si perdono il torneo e i suoi iscritti. La scrittura
        del file e le finestre di messaggio sono finte."""
        import wx

        from config import user_data_path

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        self._scrittura_negata(monkeypatch)
        suoni.clear()

        self._creato(principale, "Nuovo Sociale", "Bologna")
        self._creato(principale, "Nuovo Sociale", "Ferrara")

        percorso = user_data_path("Tornello - Nuovo_Sociale.json")
        messaggio = self._messaggio(percorso, "Accesso negato", nome="Nuovo Sociale")
        domanda = TestTorneoNonSalvatoDaLasciare._domanda_senza_file("Accesso negato", nome="Nuovo Sociale")
        assert [(f.titolo, f.testo) for f in finestre] == [messaggio, domanda, messaggio]
        assert suoni.count("errore") == 3
        assert scatole == []
        self._aperto_dalla_memoria(principale, percorso, "Nuovo Sociale")
        assert principale.current_tournament["site"] == "Ferrara"

    def test_il_torneo_nuovo_che_non_si_salva_resta_aperto(self, principale, suoni, monkeypatch, capsys):
        """10.19.20, decisione di Gabriele del 5 novembre 2026. Il primo
        salvataggio del torneo nuovo della procedura guidata non riesce,
        perche' la scrittura del suo file solleva PermissionError: esce il
        messaggio Torneo non salvato, e il torneo nuovo resta aperto, in
        memoria e nell'albero, senza il messaggio Errore nel caricamento del
        torneo, e la barra di stato dice che non e' ancora salvato. I
        salvataggi dopo riprovano davvero: con la scrittura vera il primo
        scrive il file con tutto il torneo e gli iscritti, senza messaggi, e
        fa la copia di sicurezza della creazione. Fino alla 10.19.19, e gia'
        nella 10.0.0, load_tournament rileggeva il file che non c'era, e il
        torneo nuovo usciva dalla memoria, mentre la barra diceva Torneo
        creato."""
        import json

        import wx

        import tournament
        from config import user_data_path

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        vera = self._scrittura_negata(monkeypatch)
        suoni.clear()

        self._creato(principale, "Nuovo Sociale", "Bologna")
        principale._save_state()

        percorso = user_data_path("Tornello - Nuovo_Sociale.json")
        assert [(f.titolo, f.testo) for f in finestre] == [self._messaggio(percorso, "Accesso negato", nome="Nuovo Sociale")]
        assert suoni.count("errore") == 1
        assert scatole == []
        self._aperto_dalla_memoria(principale, percorso, "Nuovo Sociale")
        capsys.readouterr()

        monkeypatch.setattr(tournament, "scrivi_json_atomico", vera)
        principale._save_state()

        nel_file = TestNomeEDataDiInizioDaDati._nel_file(percorso)
        attesi = {k: v for k, v in principale.current_tournament.items() if k != "players_dict"}
        assert nel_file == json.loads(json.dumps(attesi))
        assert nel_file["site"] == "Bologna"
        assert [p["id"] for p in nel_file["players"]] == [g[0] for g in GIOCATORI_DEI_TORNEI]
        assert self._errori_in_console(capsys, percorso) == ([], [])
        assert len(finestre) == 1
        assert suoni.count("errore") == 1
        copie = [f for _radice, _cartelle, file in os.walk(user_data_path("backup")) for f in file]
        assert [f for f in copie if f.startswith("Tornello - Nuovo_Sociale") and "creazione" in f]

    def test_il_torneo_nuovo_con_il_nome_troppo_lungo_resta_aperto(self, principale, suoni, monkeypatch, capsys):
        """10.19.20. Un salvataggio che non riesce davvero, senza finte: il
        nome del torneo e' cosi' lungo che il nome del suo file supera il
        limite di Windows, e il sistema lo rifiuta. Il messaggio Torneo non
        salvato dice la descrizione del motivo, la stessa della riga in
        console, e il torneo nuovo resta aperto, con i quattro iscritti; il
        salvataggio dopo non riesce di nuovo, senza un altro messaggio.
        Fino alla 10.19.19 il torneo nuovo usciva dalla memoria, con il
        messaggio Errore nel caricamento del torneo."""
        import wx

        from config import user_data_path

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        nome = "Coppa " + "x" * 245
        suoni.clear()
        capsys.readouterr()

        self._creato(principale, nome)
        principale._save_state()

        percorso = user_data_path(f"Tornello - Coppa_{'x' * 245}.json")
        errori, _della_raccolta = self._errori_in_console(capsys, percorso)
        assert len(errori) == 2
        assert [(f.titolo, f.testo) for f in finestre] == [self._messaggio(percorso, _descrizione_dell_errore(errori[0]), nome=nome)]
        assert suoni.count("errore") == 1
        assert scatole == []
        self._aperto_dalla_memoria(principale, percorso, nome)

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_dopo_canc_su_un_iscritto_il_messaggio_torna(self, principale, suoni, monkeypatch, capsys):
        """Correzione della revisione della 10.19.19. Gamma, in preparazione,
        cambia luogo con il suo file bloccato, e il messaggio esce. Tolto il
        blocco, CANC su un iscritto, con Si', scrive il file del torneo: e'
        un salvataggio riuscito, come quello della Time Machine, e dalla
        10.19.22 passa da _save_state, e scrive anche Roma. Bloccato di
        nuovo, quando il luogo cambia ancora il messaggio torna, una volta in
        due salvataggi. Fino alla revisione non tornava piu'."""
        from config import user_data_path

        percorso = user_data_path("Tornello - Gamma.json")
        dati = _torneo_in_corso("Gamma")
        dati["rounds"] = []
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        principale.load_tournament(percorso)
        assert principale._e_il_torneo_aperto(percorso)
        percorso = principale.active_filename
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()
        capsys.readouterr()

        principale.current_tournament["site"] = "Roma"
        self._salvataggi_bloccati(principale, percorso, volte=1)
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_player_detail", "filepath": percorso})
        principale.delete_player_from_tournament(voce, principale.tree_ctrl.GetItemData(voce)["player"])
        assert len(TestNomeEDataDiInizioDaDati._nel_file(percorso)["players"]) == 3
        assert TestNomeEDataDiInizioDaDati._nel_file(percorso).get("site") == "Roma"
        principale.current_tournament["site"] = "Milano"
        self._salvataggi_bloccati(principale, percorso, volte=2)

        errori, _della_raccolta = self._errori_in_console(capsys, percorso)
        assert len(errori) == 3
        assert [f.titolo for f in finestre] == ["Torneo non salvato", "Conferma Rimozione Giocatore", "Torneo non salvato"]
        non_salvato = [(f.titolo, f.testo) for f in finestre if f.titolo == "Torneo non salvato"]
        assert non_salvato == [self._messaggio(percorso, _descrizione_dell_errore(errori[0]), nome="Gamma"), self._messaggio(percorso, _descrizione_dell_errore(errori[1]), nome="Gamma")]
        assert suoni.count("errore") == 2


class TestVoceDelTorneoNuovoNonSalvato:
    """Proposta 2 del nono giro. La voce del torneo nuovo che non si e'
    salvato, presa dalla memoria, dice soltanto il nome del torneo: il suo
    file va nella cartella del programma, e la cartella fra parentesi non
    serve. Dopo il primo salvataggio riuscito la voce e' quella di ogni
    torneo sul disco, anche senza ricostruire l'albero. Fino alla proposta
    diceva per esempio Nuovo Sociale (dalla cartella Tornello), e dopo il
    primo salvataggio la parentesi restava finche' l'albero non si
    ricostruiva. Un torneo aperto da un'altra cartella dice sempre la sua
    cartella. La scrittura del file e le finestre di messaggio sono finte."""

    @staticmethod
    def _voci_con_il_nome(principale, nome):
        """I testi delle voci dei tornei che cominciano con nome, in tutto
        l'albero."""
        albero = principale.tree_ctrl
        trovate = []
        da_guardare = [principale.tree_root]
        while da_guardare:
            genitore = da_guardare.pop(0)
            voce, cookie = albero.GetFirstChild(genitore)
            while voce.IsOk():
                dati = albero.GetItemData(voce) or {}
                if dati.get("action") == "select_tournament" and albero.GetItemText(voce).startswith(nome):
                    trovate.append(albero.GetItemText(voce))
                da_guardare.append(voce)
                voce, cookie = albero.GetNextChild(genitore, cookie)
        return trovate

    def test_la_voce_dice_il_nome_prima_e_dopo_il_salvataggio(self, principale, suoni, monkeypatch, capsys):
        """Il primo salvataggio di Nuovo Sociale non riesce, e la sua voce
        dice Nuovo Sociale, senza parentesi. Con la scrittura vera il
        salvataggio dopo riesce, e la voce, che l'albero non ha rifatto, dice
        ancora Nuovo Sociale; lo stesso dopo la ricostruzione dell'albero, e
        dopo che il torneo si riapre dal suo file. In tutto l'albero c'e' una
        voce sola con quel nome."""
        import tournament
        from config import user_data_path

        TestNomeDelTorneoNuovo._domande(monkeypatch)
        vera = TestTorneoCheNonSiSalva._scrittura_negata(monkeypatch)
        TestTorneoCheNonSiSalva._creato(principale, "Nuovo Sociale", "Bologna")
        percorso = user_data_path("Tornello - Nuovo_Sociale.json")
        assert not os.path.exists(percorso)
        albero = principale.tree_ctrl
        voce = principale._voce_del_torneo_aperto()
        assert albero.GetItemText(voce) == "Nuovo Sociale"

        monkeypatch.setattr(tournament, "scrivi_json_atomico", vera)
        principale._save_state()

        assert os.path.exists(percorso)
        assert albero.GetItemText(voce) == "Nuovo Sociale"
        principale.populate_tree()
        assert albero.GetItemText(principale._voce_del_torneo_aperto()) == "Nuovo Sociale"
        assert self._voci_con_il_nome(principale, "Nuovo Sociale") == ["Nuovo Sociale"]
        principale.load_tournament(percorso)
        assert principale._e_il_torneo_aperto(percorso)
        assert albero.GetItemText(principale._voce_del_torneo_aperto()) == "Nuovo Sociale"
        assert self._voci_con_il_nome(principale, "Nuovo Sociale") == ["Nuovo Sociale"]

    def test_da_un_altra_cartella_la_parentesi_resta(self, principale, suoni, monkeypatch, tmp_path):
        """Alfa, aperto da una chiavetta, non e' piu' sul disco: la sua voce,
        presa dalla memoria, dice ancora la cartella fra parentesi, perche' il
        suo file non va nella cartella del programma. E' la regola di prima,
        che la proposta non cambia."""
        chiavetta = str(tmp_path / "chiavetta" / "Tornello - Alfa.json")
        TestNomeDelTorneoNuovo._scrivi(chiavetta, _torneo_in_corso("Alfa"))
        principale.load_tournament(chiavetta)
        assert principale._e_il_torneo_aperto(chiavetta)
        os.remove(chiavetta)

        principale.populate_tree()

        assert principale.tree_ctrl.GetItemText(principale._voce_del_torneo_aperto()) == "Alfa (dalla cartella chiavetta)"

    @pytest.mark.skipif(sys.platform != "win32", reason="i percorsi senza badare alle maiuscole sono quelli di Windows")
    def test_con_il_percorso_scritto_con_altre_maiuscole_la_parentesi_non_c_e(self, principale, suoni, monkeypatch, capsys):
        """Correzione della proposta 2, rilievo 9 della revisione. Il primo
        salvataggio di Nuovo Sociale non riesce, e il suo file, nella
        cartella del programma, e' scritto con la cartella in altre
        maiuscole, un'altra forma dello stesso file su Windows: la voce,
        presa dalla memoria, dice soltanto il nome, senza parentesi."""
        TestNomeDelTorneoNuovo._domande(monkeypatch)
        TestTorneoCheNonSiSalva._scrittura_negata(monkeypatch)
        TestTorneoCheNonSiSalva._creato(principale, "Nuovo Sociale", "Bologna")
        cartella, nome = os.path.split(principale.active_filename)
        principale.active_filename = os.path.join(cartella.swapcase(), nome)
        assert not os.path.exists(principale.active_filename)

        principale.populate_tree()

        assert principale.tree_ctrl.GetItemText(principale._voce_del_torneo_aperto()) == "Nuovo Sociale"

    def test_il_torneo_concluso_rimasto_nella_cartella_tiene_la_parentesi(self, principale, suoni, monkeypatch):
        """Correzione della proposta 2, rilievo 9 della revisione. Omega,
        concluso, ha il suo file nella cartella del programma, dove l'albero
        non elenca i tornei conclusi, ed e' aperto: la sua voce, presa dalla
        memoria, tiene la cartella fra parentesi, perche' il file c'e', come
        per ogni torneo aperto che l'albero non trova da se'."""
        import gui.main_frame as mf
        from config import user_data_path

        percorso = user_data_path("Tornello - Omega.json")
        concluso = _torneo_in_corso("Omega", finito=True)
        concluso["concluded"] = True
        TestNomeDelTorneoNuovo._scrivi(percorso, concluso)
        principale.load_tournament(percorso)
        assert principale._e_il_torneo_aperto(percorso)

        principale.populate_tree()

        cartella = mf._nome_della_cartella(percorso)
        assert principale.tree_ctrl.GetItemText(principale._voce_del_torneo_aperto()) == f"Omega (Ottobre 2026, dalla cartella {cartella})"


# I file con la forma di un torneo, cioe' con il nome, gli iscritti e i turni,
# che l'apertura non apre, con il testo dell'errore che da': dalla correzione
# della 10.19.29 Apri Torneo lo sa prima della domanda Torneo non salvato.
FILE_CHE_NON_SI_APRONO = {
    "iscritto senza identificativo": ({"name": "Strano", "players": [{"first_name": "Mario"}], "rounds": []}, "'id'"),
    "iscritto scritto come testo": ({"name": "Strano", "players": ["Mario Rossi"], "rounds": []}, "string indices must be integers, not 'str'"),
    "turno scritto come numero": ({"name": "Strano", "players": [{"id": "A"}], "rounds": [1]}, "'int' object has no attribute 'get'"),
    "Bianco del turno corrente scritto come elenco": (
        {"name": "Strano", "players": [{"id": "A"}], "current_round": 1, "rounds": [{"round": 1, "matches": [{"white_player_id": ["A"], "black_player_id": None}]}]},
        "cannot use 'list' as a dict key (unhashable type: 'list')",
    ),
    "partita di un turno passato scritta come numero": (
        {"name": "Strano", "players": [{"id": "A"}], "current_round": 2, "rounds": [{"round": 1, "matches": [5]}, {"round": 2, "matches": []}]},
        "'int' object has no attribute 'get'",
    ),
}


class TestTorneoNonSalvatoDaLasciare:
    """Dalla 10.19.21 (decisione di Gabriele del 5 novembre 2026) un torneo
    che ha le ultime modifiche soltanto in memoria, perche' il suo ultimo
    salvataggio non e' riuscito, prima di lasciarlo si riprova a salvare. Se
    si salva, si va avanti senza dire niente. Se no, con il suono
    dell'errore, la domanda Torneo non salvato chiede se lasciarlo lo
    stesso, con No predefinito: con Si' si va avanti, e le modifiche si
    perdono; con No si resta sul torneo, e niente cambia. Fino alla 10.19.20,
    e gia' nella 10.0.0, le modifiche si perdevano senza avviso. Il file del
    torneo lo tiene aperto un altro programma, con un blocco vero di
    CreateFileW che lo lascia leggere ma non sostituire; le finestre di
    messaggio, quella di Apri Torneo e le copie della chiusura sono finte."""

    @staticmethod
    def _domanda(errore, nome="Primavera 2"):
        """Il titolo e il testo della domanda per il torneo nome, Primavera 2
        se non e' un altro, con errore, la descrizione del motivo."""
        return (
            "Torneo non salvato",
            f"Il torneo {nome} non si è potuto salvare: {errore}. Se lo lasci, le ultime modifiche si perdono. Vuoi lasciarlo lo stesso? Il pulsante predefinito è No.",
        )

    @staticmethod
    def _domanda_senza_file(errore, nome):
        """Il titolo e il testo della domanda per il torneo nome che non ha
        ancora il suo file sul disco, come il torneo nuovo che non si e'
        salvato, con errore, la descrizione del motivo: dalla proposta 4 del
        nono giro dice che lasciandolo si perdono il torneo e i suoi
        iscritti, e non piu' le ultime modifiche."""
        return (
            "Torneo non salvato",
            f"Il torneo {nome} non si è potuto salvare: {errore}. Il suo file non c'è ancora: se lo lasci, il torneo e i suoi iscritti si perdono. Vuoi lasciarlo lo stesso? Il pulsante predefinito è No.",
        )

    @pytest.fixture
    def bloccata(self, principale, suoni, monkeypatch, capsys):
        """Primavera 2 aperta, con Estate 3 nella cartella e nell'albero, e il
        cursore sulla voce Luogo di Primavera 2. Il luogo diventa Roma, e il
        salvataggio non riesce, perche' un altro programma tiene bloccato il
        file: il messaggio Torneo non salvato esce. Restituisce i due file, il
        contenuto di quello di Primavera 2, la voce Luogo, la descrizione del
        motivo e la funzione che toglie il blocco, che alla fine si toglie da
        se'. Le finestre annotate le da' _finestre."""
        from config import user_data_path

        raccolte = TestRaccoltaSenzaPartiteNelCestino
        primavera, _raccolta, _contenuto = raccolte._torneo_normale()
        estate = user_data_path("Tornello - Estate_3.json")
        TestNomeDelTorneoNuovo._scrivi(estate, _torneo_in_corso("Estate 3"))
        principale.load_tournament(primavera)
        primavera = principale.active_filename
        estate = principale._percorso_come_nell_albero(estate)[0]
        with open(primavera, "rb") as f:
            prima = f.read()
        luogo = TestAlberoETorneoAttivo._voce(principale, action="show_data", filepath=primavera, field_active="site")
        with principale._albero_senza_caricamenti():
            principale.tree_ctrl.SelectItem(luogo)
        sblocchi = [raccolte._bloccata(primavera, raccolte.FILE_SHARE_READ)]

        def sblocca():
            while sblocchi:
                sblocchi.pop()()

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()
        capsys.readouterr()
        principale.current_tournament["site"] = "Roma"
        principale._save_state()
        errori, _della_raccolta = TestTorneoCheNonSiSalva._errori_in_console(capsys, primavera)
        assert len(errori) == 1
        descrizione = _descrizione_dell_errore(errori[0])
        assert [f.titolo for f in finestre] == ["Torneo non salvato"]
        yield SimpleNamespace(primavera=primavera, estate=estate, prima=prima, luogo=luogo, descrizione=descrizione, sblocca=sblocca)
        sblocca()

    @staticmethod
    def _finestre(monkeypatch, *risposte):
        """Da qui le finestre di messaggio annotate, con le risposte alle
        domande; finite quelle, Si'."""
        return TestNomeDelTorneoNuovo._domande(monkeypatch, risposte)

    @staticmethod
    def _domande_fatte(finestre):
        return [(f.titolo, f.testo, f.no_predefinito) for f in finestre if f.domanda]

    @staticmethod
    def _primavera_com_era(principale, bloccata):
        """Primavera 2 e' ancora il torneo aperto, con Roma in memoria, e il
        suo file e' com'era."""
        assert principale._e_il_torneo_aperto(bloccata.primavera)
        assert principale.current_tournament["site"] == "Roma"
        with open(bloccata.primavera, "rb") as f:
            assert f.read() == bloccata.prima

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_le_frecce_con_no_tornano_sulla_voce_di_prima(self, principale, suoni, monkeypatch, capsys, bloccata):
        """Il cursore scende con le frecce sulla voce di Estate 3: il
        salvataggio si riprova, non riesce, e la domanda esce una volta, con
        il suono dell'errore e la stessa descrizione del motivo. Con No
        Primavera 2 resta aperta, con Roma in memoria, e il cursore resta
        sulla voce Luogo, senza un'altra domanda e senza rileggere il torneo
        dal file. Dalla correzione della revisione della 10.19.21 la domanda
        arriva prima che la selezione cambi, e con No la selezione non passa
        mai su Estate 3: fino ad allora ci passava, e tornava sulla voce Luogo
        con wx.CallAfter. Tolto il blocco, il salvataggio dopo scrive Roma."""
        import wx

        finestre = self._finestre(monkeypatch, wx.ID_NO)
        registro = TestAlberoETorneoAttivo._sonde(principale)

        TestAlberoETorneoAttivo()._scegli_torneo(principale, bloccata.estate)
        _eventi_in_coda()

        assert self._domande_fatte(finestre) == [(*self._domanda(bloccata.descrizione), True)]
        assert [f.titolo for f in finestre] == ["Torneo non salvato"]
        assert suoni.count("errore") == 2
        assert registro.caricati == []
        assert registro.selezioni == []
        assert principale.tree_ctrl.GetSelection() == bloccata.luogo
        self._primavera_com_era(principale, bloccata)
        errori, _della_raccolta = TestTorneoCheNonSiSalva._errori_in_console(capsys, bloccata.primavera)
        assert len(errori) == 1

        bloccata.sblocca()
        principale._save_state()

        assert TestNomeEDataDiInizioDaDati._nel_file(bloccata.primavera)["site"] == "Roma"

    @pytest.mark.finestre_vere
    @pytest.mark.skipif(sys.platform != "win32", reason="il desktop nascosto e il blocco di un altro programma sono quelli di Windows")
    @pytest.mark.parametrize("risposta", ["no", "si"])
    def test_la_freccia_vera_e_gli_eventi_per_nvda(self, principale, suoni, monkeypatch, capsys, bloccata, risposta):
        """Correzione della revisione della 10.19.21. La finestra principale
        si mostra sul desktop nascosto, il cursore sta sulla voce accanto a
        quella di Estate 3, e la freccia arriva davvero all'albero, con
        PostMessage, come dalla tastiera. La domanda arriva prima che la
        selezione cambi. Con No il controllo di Windows non manda a NVDA ne'
        il fuoco ne' la selezione su nessuna voce, annotati con
        SetWinEventHook come li riceve uno screen reader, e il cursore resta
        dov'era: fino alla revisione la selezione passava su Estate 3, che
        riceveva fuoco e selezione, e tornava indietro, con la voce di
        partenza che riceveva il fuoco un'altra volta. Con Si' la domanda
        esce una volta sola, e il cursore passa su Estate 3, che si apre. La
        domanda e' finta, come nelle altre prove."""
        import ctypes
        from ctypes import wintypes

        import wx
        from test_canc_nell_albero import _attiva, _premi
        from test_fuoco_alla_chiusura import _attendi

        albero = principale.tree_ctrl
        estate = TestAlberoETorneoAttivo._voce(principale, action="select_tournament", filepath=bloccata.estate)
        partenza, tasto = albero.GetPrevVisible(estate), (0x28, 0x50)
        if not partenza.IsOk():
            partenza, tasto = albero.GetNextVisible(estate), (0x26, 0x48)
        assert albero.GetItemData(partenza).get("filepath") == bloccata.primavera
        user32 = _attiva(principale)
        with principale._albero_senza_caricamenti():
            albero.SelectItem(partenza)
        albero.SetFocus()
        assert _attendi(lambda: wx.Window.FindFocus() is albero)
        _attendi(lambda: False, 0.3)
        finestre = self._finestre(monkeypatch, wx.ID_NO if risposta == "no" else wx.ID_YES)
        eventi = []
        richiamo = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND, wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)(
            lambda gancio, evento, finestra, oggetto, figlio, thread, tempo: eventi.append((evento, finestra, figlio))
        )
        ganci = ctypes.WinDLL("user32")
        ganci.SetWinEventHook.restype = wintypes.HANDLE
        ganci.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, type(richiamo), wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
        ganci.UnhookWinEvent.argtypes = [wintypes.HANDLE]
        # EVENT_OBJECT_FOCUS e EVENT_OBJECT_SELECTION, del solo processo
        # delle prove, fuori contesto: arrivano fra gli eventi di wx.
        gancio = ganci.SetWinEventHook(0x8005, 0x8006, None, richiamo, os.getpid(), 0, 0)
        assert gancio
        try:
            _premi(user32, albero, *tasto)
            _attendi(lambda: False, 0.3)
        finally:
            ganci.UnhookWinEvent(gancio)

        sulle_voci = [e for e in eventi if e[1] == albero.GetHandle() and e[2] > 0]
        assert self._domande_fatte(finestre) == [(*self._domanda(bloccata.descrizione), True)]
        if risposta == "no":
            assert sulle_voci == []
            assert albero.GetSelection() == partenza
            self._primavera_com_era(principale, bloccata)
        else:
            assert sulle_voci
            assert albero.GetSelection() == estate
            assert principale._e_il_torneo_aperto(bloccata.estate)

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_le_frecce_con_si_lasciano_il_torneo(self, principale, suoni, monkeypatch, capsys, bloccata):
        """Con Si' alla domanda Estate 3 si apre, e Roma si perde: il file di
        Primavera 2 resta com'era, e riaperto non ha Roma."""
        import wx

        finestre = self._finestre(monkeypatch, wx.ID_YES)
        registro = TestAlberoETorneoAttivo._sonde(principale)

        TestAlberoETorneoAttivo()._scegli_torneo(principale, bloccata.estate)

        assert self._domande_fatte(finestre) == [(*self._domanda(bloccata.descrizione), True)]
        assert registro.caricati == ["Tornello - Estate_3.json"]
        assert principale._e_il_torneo_aperto(bloccata.estate)
        with open(bloccata.primavera, "rb") as f:
            assert f.read() == bloccata.prima
        bloccata.sblocca()
        principale.load_tournament(bloccata.primavera)
        assert principale.current_tournament.get("site") != "Roma"

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_tolto_il_blocco_si_salva_e_si_lascia_senza_domande(self, principale, suoni, monkeypatch, capsys, bloccata):
        """L'altro programma chiude il file prima che il cursore scenda su
        Estate 3: il salvataggio che si riprova riesce, Roma va nel file di
        Primavera 2, ed Estate 3 si apre, senza domande e senza messaggi."""
        finestre = self._finestre(monkeypatch)
        registro = TestAlberoETorneoAttivo._sonde(principale)
        bloccata.sblocca()

        TestAlberoETorneoAttivo()._scegli_torneo(principale, bloccata.estate)

        assert finestre == []
        assert suoni.count("errore") == 1
        assert TestNomeEDataDiInizioDaDati._nel_file(bloccata.primavera)["site"] == "Roma"
        assert registro.caricati == ["Tornello - Estate_3.json"]
        assert principale._e_il_torneo_aperto(bloccata.estate)

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_invio_su_un_altro_torneo_con_no_non_fa_niente(self, principale, suoni, monkeypatch, capsys, bloccata):
        """INVIO sulla voce Dati di Estate 3, che non e' il torneo aperto: la
        stessa domanda, e con No Primavera 2 resta aperta, e l'azione non
        parte."""
        import wx

        finestre = self._finestre(monkeypatch, wx.ID_NO)
        registro = TestAlberoETorneoAttivo._sonde(principale)
        dati = TestAlberoETorneoAttivo._voce(principale, action="show_data", filepath=bloccata.estate, field_active=None)

        principale.on_tree_item_activated(SimpleNamespace(GetItem=lambda: dati))

        assert self._domande_fatte(finestre) == [(*self._domanda(bloccata.descrizione), True)]
        assert registro.caricati == []
        self._primavera_com_era(principale, bloccata)

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    @pytest.mark.parametrize("risposta", ["no", "si", "senza veto"])
    def test_la_chiusura(self, principale, suoni, monkeypatch, capsys, bloccata, risposta):
        """La chiusura di Tornello. Con No la finestra resta aperta: la
        chiusura si ferma, senza le copie della chiusura e senza il suo
        suono, e Primavera 2 resta com'era. Con Si' la chiusura va avanti, e
        Roma si perde. Una chiusura che non si puo' fermare, come quella di
        Windows che si spegne, riprova il salvataggio senza domande, e va
        avanti."""
        import wx

        import utils

        finestre = self._finestre(monkeypatch, wx.ID_NO if risposta == "no" else wx.ID_YES)
        copie = []
        monkeypatch.setattr(utils, "copie_di_chiusura", lambda percorso: copie.append(percorso))
        evento = wx.CloseEvent(wx.wxEVT_CLOSE_WINDOW, principale.GetId())
        evento.SetCanVeto(risposta != "senza veto")

        principale.on_close(evento)

        errori, _della_raccolta = TestTorneoCheNonSiSalva._errori_in_console(capsys, bloccata.primavera)
        assert len(errori) == 1
        if risposta == "senza veto":
            assert finestre == []
        else:
            assert self._domande_fatte(finestre) == [(*self._domanda(bloccata.descrizione), True)]
        if risposta == "no":
            assert evento.GetVeto()
            assert copie == []
            assert "chiusura" not in suoni
        else:
            assert not evento.GetVeto()
            assert copie == [bloccata.primavera]
            assert "chiusura" in suoni
        self._primavera_com_era(principale, bloccata)

    @staticmethod
    def _finestra_apri(monkeypatch, finestre, percorso, esito=None):
        """La finestra Apri finta, che sceglie percorso, oppure, con esito
        wx.ID_CANCEL, si annulla. Restituisce l'elenco che annota, per ogni
        volta che si mostra, quante domande, fra le finestre annotate, erano
        gia' state fatte."""
        import wx

        esito = wx.ID_OK if esito is None else esito
        mostrate = []

        class FinestraApri:
            def __init__(self, *argomenti, **opzioni):
                pass

            def ShowModal(self):
                mostrate.append(len([f for f in finestre if f.domanda]))
                return esito

            def GetPath(self):
                return percorso

            def Destroy(self):
                pass

        monkeypatch.setattr(wx, "FileDialog", FinestraApri)
        return mostrate

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    @pytest.mark.parametrize("scritto", ["come nell'albero", "in minuscolo"])
    def test_apri_torneo_sul_torneo_aperto(self, principale, suoni, monkeypatch, capsys, bloccata, scritto):
        """Proposta 7 del nono giro. Apri Torneo, e nella finestra Apri lo
        stesso file di Primavera 2, anche scritto in minuscolo, come puo'
        restituirlo la finestra: nessuna domanda, nessun suono, e il torneo
        non si rilegge. Primavera 2 resta com'e' in memoria, con Roma, il
        cursore passa dalla voce Luogo a quella del torneo, e la barra di
        stato dice che il torneo e' gia' aperto. Tolto il blocco, il
        salvataggio dopo scrive Roma. Fino alla proposta la domanda arrivava
        prima della finestra Apri, e con Si' il torneo si rileggeva dal suo
        file: Roma si perdeva."""
        import wx

        finestre = self._finestre(monkeypatch)
        registro = TestAlberoETorneoAttivo._sonde(principale)
        scelto = bloccata.primavera.lower() if scritto == "in minuscolo" else bloccata.primavera
        assert os.path.exists(scelto)
        mostrate = self._finestra_apri(monkeypatch, finestre, scelto)
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_OPEN)

        assert mostrate == [0]
        assert finestre == []
        assert suoni == []
        assert registro.caricati == []
        self._primavera_com_era(principale, bloccata)
        assert principale.active_filename == bloccata.primavera
        assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": bloccata.primavera}
        assert principale.last_status_msg == "Il torneo 'Primavera 2' è già aperto, e resta com'è: Tornello non lo rilegge dal suo file."
        errori, _della_raccolta = TestTorneoCheNonSiSalva._errori_in_console(capsys, bloccata.primavera)
        assert errori == []

        bloccata.sblocca()
        principale._save_state()

        assert TestNomeEDataDiInizioDaDati._nel_file(bloccata.primavera)["site"] == "Roma"

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_apri_torneo_annullato(self, principale, suoni, monkeypatch, capsys, bloccata):
        """Proposta 7 del nono giro. Apri Torneo, e la finestra Apri si
        annulla: nessuna domanda, nessun suono, nessun salvataggio riprovato,
        e Primavera 2 resta com'era, con Roma in memoria e il cursore sulla
        voce Luogo. Fino alla proposta la domanda arrivava prima della
        finestra Apri, con il salvataggio riprovato e il suono dell'errore,
        anche se poi la finestra si annullava."""
        import wx

        finestre = self._finestre(monkeypatch)
        registro = TestAlberoETorneoAttivo._sonde(principale)
        mostrate = self._finestra_apri(monkeypatch, finestre, bloccata.estate, wx.ID_CANCEL)
        suoni.clear()
        barra = principale.last_status_msg

        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_OPEN)

        assert mostrate == [0]
        assert finestre == []
        assert suoni == []
        assert registro.caricati == []
        self._primavera_com_era(principale, bloccata)
        assert principale.tree_ctrl.GetSelection() == bloccata.luogo
        assert principale.last_status_msg == barra
        errori, _della_raccolta = TestTorneoCheNonSiSalva._errori_in_console(capsys, bloccata.primavera)
        assert errori == []

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    @pytest.mark.parametrize("contenuto", ["non torneo", "rovinato", "troppo annidato"])
    def test_apri_torneo_su_un_file_che_non_si_apre(self, principale, suoni, monkeypatch, capsys, bloccata, tmp_path, contenuto):
        """10.19.29. Apri Torneo, e nella finestra Apri un file che non e' un
        torneo, o che e' rovinato: Tornello lo legge prima della domanda
        Torneo non salvato, e il suo messaggio esce subito, Non e' un torneo
        con il suono dell'errore, o Errore nel caricamento del torneo, senza
        la domanda e senza riprovare il salvataggio. Primavera 2 resta
        aperta, com'e' in memoria, con Roma, il cursore resta sulla voce
        Luogo, e la barra di stato dice che il torneo non si e' aperto.
        Tolto il blocco, il salvataggio dopo scrive Roma. Fino alla 10.19.29
        la domanda usciva prima del messaggio, e con Si' Primavera 2 restava
        aperta lo stesso, con le modifiche che la domanda aveva detto perse.
        Dalla correzione della 10.19.29 vale anche per un json annidato oltre
        il limite di Python, che json.load rifiuta con RecursionError: fino ad
        allora Apri Torneo finiva senza messaggio, con l'errore in console.
        Dalla 10.19.33 il file rovinato e quello troppo annidato li dice il
        messaggio Apertura non riuscita, nella finestra accessibile e con il
        suono dell'errore, con il file e il testo dell'errore: fino alla
        10.19.32 era un wx.MessageBox senza suono, Errore nel caricamento del
        torneo."""
        import wx

        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda testo, *a, **k: scatole.append(testo))
        finestre = self._finestre(monkeypatch)
        registro = TestAlberoETorneoAttivo._sonde(principale)
        scelto = str(tmp_path / "altrove" / "Tornello - Altro.json")
        os.makedirs(os.path.dirname(scelto))
        with open(scelto, "w", encoding="utf-8") as f:
            f.write({"non torneo": '{"schema_version": 2, "players": []}', "rovinato": "{rotto", "troppo annidato": "[" * 200000 + "]" * 200000}[contenuto])
        mostrate = self._finestra_apri(monkeypatch, finestre, scelto)
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_OPEN)

        assert mostrate == [0]
        assert self._domande_fatte(finestre) == []
        if contenuto == "non torneo":
            assert [(f.titolo, f.testo) for f in finestre] == [("Non è un torneo", "Il file Tornello - Altro.json non è un torneo di Tornello, e non si apre.")]
            assert suoni == ["errore"]
            assert scatole == []
        elif contenuto == "rovinato":
            assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
                (*_apertura_non_riuscita(scelto, "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"), False)
            ]
            assert suoni == ["errore"]
            assert scatole == []
        else:
            assert [(f.titolo, f.domanda) for f in finestre] == [("Apertura non riuscita", False)]
            assert finestre[0].testo.startswith(f"Il file {scelto} non si è potuto aprire: ")
            assert finestre[0].testo.endswith(" while decoding a JSON array from a unicode string.")
            assert suoni == ["errore"]
            assert scatole == []
        assert registro.caricati == []
        self._primavera_com_era(principale, bloccata)
        assert principale.tree_ctrl.GetSelection() == bloccata.luogo
        assert principale.last_status_msg == "Il torneo non si è aperto: resta aperto 'Primavera 2'."
        errori, _della_raccolta = TestTorneoCheNonSiSalva._errori_in_console(capsys, bloccata.primavera)
        assert errori == []

        bloccata.sblocca()
        principale._save_state()

        assert TestNomeEDataDiInizioDaDati._nel_file(bloccata.primavera)["site"] == "Roma"

    @staticmethod
    def _scrivi_strano(tmp_path, dati):
        """Il file Tornello - Strano.json, con dati, in una cartella che
        l'albero non legge."""
        import json

        scelto = str(tmp_path / "altrove" / "Tornello - Strano.json")
        os.makedirs(os.path.dirname(scelto))
        with open(scelto, "w", encoding="utf-8") as f:
            json.dump(dati, f)
        return scelto

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    @pytest.mark.parametrize("forma", list(FILE_CHE_NON_SI_APRONO))
    def test_apri_torneo_su_un_file_con_la_forma_di_un_torneo_che_non_si_apre(self, principale, suoni, monkeypatch, capsys, bloccata, tmp_path, forma):
        """Correzione della 10.19.29. Apri Torneo, e nella finestra Apri un
        file con il nome, gli iscritti e i turni, ma con un iscritto senza il
        suo identificativo, o con un turno o una partita che non sono un
        dizionario: l'apertura non lo aprirebbe, e Tornello lo sa prima della
        domanda Torneo non salvato. Il messaggio Errore nel caricamento del
        torneo esce subito, con l'errore di sempre, senza la domanda e senza
        riprovare il salvataggio, e Primavera 2 resta aperta, com'e' in
        memoria, con Roma, con il cursore sulla voce Luogo. Tolto il blocco,
        il salvataggio dopo scrive Roma. Fino alla correzione la domanda
        usciva, e con Si' l'errore arrivava dopo e chiudeva Primavera 2:
        Roma non arrivava piu' nel file. Dalla 10.19.33 il messaggio e'
        Apertura non riuscita, nella finestra accessibile e con il suono
        dell'errore, con il file e lo stesso errore, per esempio 'id': fino
        alla 10.19.32 era un wx.MessageBox senza suono."""
        import wx

        dati, errore = FILE_CHE_NON_SI_APRONO[forma]
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda testo, *a, **k: scatole.append(testo))
        finestre = self._finestre(monkeypatch, wx.ID_YES)
        registro = TestAlberoETorneoAttivo._sonde(principale)
        scelto = self._scrivi_strano(tmp_path, dati)
        mostrate = self._finestra_apri(monkeypatch, finestre, scelto)
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_OPEN)

        assert mostrate == [0]
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [(*_apertura_non_riuscita(scelto, errore), False)]
        assert scatole == []
        assert suoni == ["errore"]
        assert registro.caricati == []
        self._primavera_com_era(principale, bloccata)
        assert principale.tree_ctrl.GetSelection() == bloccata.luogo
        assert principale.last_status_msg == "Il torneo non si è aperto: resta aperto 'Primavera 2'."
        errori, _della_raccolta = TestTorneoCheNonSiSalva._errori_in_console(capsys, bloccata.primavera)
        assert errori == []

        bloccata.sblocca()
        principale._save_state()

        assert TestNomeEDataDiInizioDaDati._nel_file(bloccata.primavera)["site"] == "Roma"

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_l_apertura_che_non_riesce_lascia_aperto_il_torneo_di_prima(self, principale, suoni, monkeypatch, capsys, bloccata, tmp_path):
        """Correzione della 10.19.29. load_tournament con
        tieni_il_precedente, come lo chiama Apri Torneo dopo la domanda, su
        un file con un iscritto senza il suo identificativo: il messaggio di
        sempre, e Primavera 2 resta aperta, com'e' in memoria, con Roma, con
        il titolo, l'area centrale e il cursore di prima. Tolto il blocco, il
        salvataggio dopo scrive Roma. Fino alla correzione l'errore arrivava
        con il torneo gia' al posto di Primavera 2, e nessun torneo restava
        aperto. Dalla 10.19.33 il messaggio di sempre e' Apertura non
        riuscita, con il suono dell'errore."""
        import wx

        dati, errore = FILE_CHE_NON_SI_APRONO["iscritto senza identificativo"]
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda testo, *a, **k: scatole.append(testo))
        finestre = self._finestre(monkeypatch)
        scelto = self._scrivi_strano(tmp_path, dati)
        titolo = principale.GetTitle()
        area = principale.main_text.GetValue()
        suoni.clear()

        principale.load_tournament(scelto, tieni_il_precedente=True)

        assert [(f.titolo, f.testo) for f in finestre] == [_apertura_non_riuscita(scelto, errore)]
        assert scatole == []
        assert suoni == ["errore"]
        self._primavera_com_era(principale, bloccata)
        assert principale.GetTitle() == titolo
        assert principale.main_text.GetValue() == area
        assert principale.tree_ctrl.GetSelection() == bloccata.luogo
        assert principale.last_status_msg == "Il torneo non si è aperto: resta aperto 'Primavera 2'."

        bloccata.sblocca()
        principale._save_state()

        assert TestNomeEDataDiInizioDaDati._nel_file(bloccata.primavera)["site"] == "Roma"

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_apri_torneo_nella_procedura_guidata_sul_torneo_aperto(self, principale, suoni, monkeypatch, capsys, bloccata):
        """10.19.29. Nuovo torneo dal menu File, con Si' alla domanda Torneo
        non salvato: la procedura guidata parte, e Primavera 2 resta in
        memoria, con Roma, finche' il torneo nuovo non nasce. Poi, dentro la
        procedura, Apri Torneo sul file di Primavera 2: nessuna domanda,
        nessun suono, e il torneo non si rilegge; la procedura si chiude,
        l'albero torna con i tornei e prende il fuoco, con il cursore sulla
        voce di Primavera 2, l'area centrale mostra il torneo, e la barra di
        stato dice che e' gia' aperto. Tolto il blocco, il salvataggio dopo
        scrive Roma. Fino alla 10.19.29 la procedura restava sullo schermo,
        e il cursore non andava sulla voce."""
        import wx

        finestre = self._finestre(monkeypatch, wx.ID_YES)
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        assert self._domande_fatte(finestre) == [(*self._domanda(bloccata.descrizione), True)]
        assert principale.creation_mode
        registro = TestAlberoETorneoAttivo._sonde(principale)
        mostrate = self._finestra_apri(monkeypatch, finestre, bloccata.primavera)
        suoni.clear()
        capsys.readouterr()

        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_OPEN)

        assert mostrate == [1]
        assert [f.titolo for f in finestre] == ["Torneo non salvato"]
        assert suoni == []
        assert registro.caricati == []
        assert not principale.creation_mode
        self._primavera_com_era(principale, bloccata)
        assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": bloccata.primavera}
        assert registro.fuoco[-1:] == ["tree_ctrl"]
        assert principale.main_text.GetValue().startswith("Torneo: Primavera 2")
        assert principale.last_status_msg == "Il torneo 'Primavera 2' è già aperto, e resta com'è: Tornello non lo rilegge dal suo file."
        errori, _della_raccolta = TestTorneoCheNonSiSalva._errori_in_console(capsys, bloccata.primavera)
        assert errori == []

        bloccata.sblocca()
        principale._save_state()

        assert TestNomeEDataDiInizioDaDati._nel_file(bloccata.primavera)["site"] == "Roma"

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    @pytest.mark.parametrize("risposta", ["no", "si"])
    def test_apri_torneo(self, principale, suoni, monkeypatch, capsys, bloccata, risposta):
        """Apri Torneo dal menu File, con Estate 3 scelto nella finestra
        Apri. Dalla proposta 7 del nono giro la finestra Apri si apre senza
        domande, e la domanda arriva dopo la scelta, prima di aprire Estate
        3. Con No Primavera 2 resta com'era; con Si' Estate 3 diventa il
        torneo aperto. Fino alla proposta la domanda arrivava prima della
        finestra Apri, e con No la finestra non si apriva. Dalla 10.19.29 il
        file di Estate 3 si legge prima della domanda, e dalla correzione
        della 10.19.29 con Si' si rilegge, perche' intanto puo' essere
        cambiato: fino ad allora si leggeva soltanto dopo la domanda, con
        Si', e dalla 10.19.29 alla correzione soltanto prima."""
        import wx

        finestre = self._finestre(monkeypatch, wx.ID_NO if risposta == "no" else wx.ID_YES)
        mostrate = self._finestra_apri(monkeypatch, finestre, bloccata.estate)
        letture = []
        leggi = principale._leggi_il_torneo

        def conta(percorso):
            if os.path.normcase(percorso) == os.path.normcase(bloccata.estate):
                letture.append(len(self._domande_fatte(finestre)))
            return leggi(percorso)

        principale._leggi_il_torneo = conta

        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_OPEN)

        assert mostrate == [0]
        assert letture == ([0] if risposta == "no" else [0, 1])
        assert self._domande_fatte(finestre) == [(*self._domanda(bloccata.descrizione), True)]
        if risposta == "no":
            self._primavera_com_era(principale, bloccata)
        else:
            assert principale._e_il_torneo_aperto(bloccata.estate)

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    @pytest.mark.parametrize("cambio", ["luogo nuovo", "sparito", "rovinato", "iscritto senza identificativo"])
    def test_apri_torneo_con_il_file_che_cambia_durante_la_domanda(self, principale, suoni, monkeypatch, capsys, bloccata, cambio):
        """Correzione della 10.19.29. Apri Torneo su Estate 3, e mentre la
        domanda Torneo non salvato aspetta la risposta il file di Estate 3
        cambia, per esempio rimesso da git o da un'altra macchina: con il
        luogo Napoli, sparito, rovinato o con un iscritto senza il suo
        identificativo. Con Si' il file si rilegge. Estate 3 si apre con
        Napoli, e il salvataggio dopo lo tiene; negli altri casi esce il
        messaggio Errore nel caricamento del torneo, e Primavera 2 resta
        aperta, com'e' in memoria, con Roma. Fino alla correzione Estate 3 si
        apriva dalla lettura di prima della domanda: senza luogo, e il primo
        salvataggio cancellava Napoli dal file; sparito, si apriva lo stesso,
        senza il suo file; rovinato, si apriva com'era. Dalla 10.19.33 il
        messaggio e' Apertura non riuscita, nella finestra accessibile e con
        il suono dell'errore, dopo quello della domanda, con il file e la
        sola descrizione del motivo: fino alla 10.19.32 era un wx.MessageBox
        senza suono, Errore nel caricamento del torneo."""
        import json

        import wx

        import gui.main_frame as mf

        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda testo, *a, **k: scatole.append(testo))
        finestre = self._finestre(monkeypatch, wx.ID_YES)
        Finto = mf.AccessibleMsgDialog
        estate = bloccata.estate

        def cambia():
            if cambio == "sparito":
                os.remove(estate)
                return
            with open(estate, encoding="utf-8") as f:
                dati = json.load(f)
            if cambio == "luogo nuovo":
                dati["site"] = "Napoli"
            elif cambio == "iscritto senza identificativo":
                del dati["players"][0]["id"]
            with open(estate, "w", encoding="utf-8") as f:
                if cambio == "rovinato":
                    f.write("{rotto")
                else:
                    json.dump(dati, f)

        class CambiaDuranteLaDomanda(Finto):
            def ShowModal(self):
                if self.domanda:
                    cambia()
                return super().ShowModal()

        monkeypatch.setattr(mf, "AccessibleMsgDialog", CambiaDuranteLaDomanda)
        self._finestra_apri(monkeypatch, finestre, estate)
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_OPEN)

        assert self._domande_fatte(finestre) == [(*self._domanda(bloccata.descrizione), True)]
        assert scatole == []
        if cambio == "luogo nuovo":
            assert principale._e_il_torneo_aperto(estate)
            assert principale.current_tournament["site"] == "Napoli"
            principale._save_state()
            assert TestNomeEDataDiInizioDaDati._nel_file(estate)["site"] == "Napoli"
            return
        motivo = {
            "sparito": "No such file or directory",
            "rovinato": "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)",
            "iscritto senza identificativo": "'id'",
        }[cambio]
        assert [(f.titolo, f.testo) for f in finestre] == [self._domanda(bloccata.descrizione), _apertura_non_riuscita(estate, motivo)]
        assert suoni == ["errore", "errore"]
        self._primavera_com_era(principale, bloccata)
        assert principale.last_status_msg == "Il torneo non si è aperto: resta aperto 'Primavera 2'."

        bloccata.sblocca()
        principale._save_state()

        assert TestNomeEDataDiInizioDaDati._nel_file(bloccata.primavera)["site"] == "Roma"

    @pytest.mark.parametrize("strada", ["apri", "chiusura"])
    def test_il_torneo_nuovo_senza_file_con_apri_torneo_e_la_chiusura(self, principale, suoni, monkeypatch, strada):
        """Proposta 4 del nono giro. Il torneo nuovo della procedura guidata
        che non si e' salvato resta aperto senza il suo file. Apri Torneo,
        con Estate 3 scelto nella finestra Apri, e la chiusura di Tornello
        riprovano il salvataggio, che non riesce: con il suono dell'errore e
        No predefinito, la domanda dice che il suo file non c'e' ancora, e
        che lasciandolo si perdono il torneo e i suoi iscritti. Con Si' ad
        Apri Torneo si apre Estate 3; con No alla chiusura la finestra resta
        aperta, senza le copie della chiusura, e il torneo nuovo resta
        aperto. Fino alla proposta la domanda diceva che si perdevano le
        ultime modifiche, mentre con Si' si perdeva tutto il torneo. La
        scrittura del file, le finestre di messaggio, quella di Apri Torneo e
        le copie della chiusura sono finte."""
        import wx

        import utils
        from config import user_data_path

        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: None)
        estate = user_data_path("Tornello - Estate_3.json")
        TestNomeDelTorneoNuovo._scrivi(estate, _torneo_in_corso("Estate 3"))
        finestre = self._finestre(monkeypatch, wx.ID_YES if strada == "apri" else wx.ID_NO)
        TestTorneoCheNonSiSalva._scrittura_negata(monkeypatch)
        TestTorneoCheNonSiSalva._creato(principale, "Nuovo Sociale")
        nuovo = principale.active_filename
        assert not os.path.exists(nuovo)
        suoni.clear()

        if strada == "apri":
            TestAlberoETorneoAttivo()._apri_con_ctrl_o(principale, monkeypatch, estate)
        else:
            copie = []
            monkeypatch.setattr(utils, "copie_di_chiusura", lambda percorso: copie.append(percorso))
            evento = wx.CloseEvent(wx.wxEVT_CLOSE_WINDOW, principale.GetId())
            evento.SetCanVeto(True)
            principale.on_close(evento)

        assert self._domande_fatte(finestre) == [(*self._domanda_senza_file("Accesso negato", nome="Nuovo Sociale"), True)]
        assert suoni.count("errore") == 1
        if strada == "apri":
            assert principale._e_il_torneo_aperto(estate)
        else:
            assert evento.GetVeto()
            assert copie == []
            assert principale._e_il_torneo_aperto(nuovo)

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    @pytest.mark.parametrize("risposta", ["no", "si"])
    def test_la_procedura_guidata(self, principale, suoni, monkeypatch, capsys, bloccata, risposta):
        """Nuovo torneo dal menu File. Con No la procedura guidata non parte,
        e l'albero resta com'era, con il cursore sulla voce Luogo; con Si'
        parte, con il suo suono."""
        import wx

        finestre = self._finestre(monkeypatch, wx.ID_NO if risposta == "no" else wx.ID_YES)

        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)

        assert self._domande_fatte(finestre) == [(*self._domanda(bloccata.descrizione), True)]
        if risposta == "no":
            assert not principale.creation_mode
            assert "nuovo_torneo" not in suoni
            assert principale.tree_ctrl.GetSelection() == bloccata.luogo
            self._primavera_com_era(principale, bloccata)
        else:
            assert principale.creation_mode
            assert "nuovo_torneo" in suoni

    @pytest.mark.parametrize("risposta", ["no", "si"])
    def test_il_ripristino_di_un_altro_torneo(self, principale, suoni, monkeypatch, risposta):
        """Il torneo nuovo della procedura guidata che non si e' salvato, e
        resta aperto senza il suo file, come dalla 10.19.20; poi dalla
        finestra Copie di sicurezza si ripristina un altro torneo, Estate 3,
        che di solito prende il suo posto. Il salvataggio si riprova, non
        riesce, e la domanda dice che il file del torneo nuovo non c'e'
        ancora, dalla proposta 4 del nono giro; con No il torneo nuovo resta
        aperto, mentre con Si' si apre
        Estate 3. Estate 3 entra nella cartella soltanto con il ripristino,
        e in tutti e due i casi l'albero ha la sua voce: con No perche'
        l'albero si ricostruisce, e fino alla revisione del nono giro nessuna
        prova lo guardava, perche' Estate 3 era gia' nell'albero prima. La
        scrittura del file e le finestre di messaggio sono finte."""
        import wx

        from config import user_data_path

        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: None)
        finestre = self._finestre(monkeypatch, wx.ID_NO if risposta == "no" else wx.ID_YES)
        TestTorneoCheNonSiSalva._scrittura_negata(monkeypatch)
        TestTorneoCheNonSiSalva._creato(principale, "Nuovo Sociale")
        estate = user_data_path("Tornello - Estate_3.json")
        TestNomeDelTorneoNuovo._scrivi(estate, _torneo_in_corso("Estate 3"))
        assert os.path.normcase(estate) not in TestAlberoETorneoAttivo._tutti_i_file(principale)

        principale._dopo_il_ripristino(SimpleNamespace(riuscito=True, tipo="torneo", destinazione=estate))

        assert self._domande_fatte(finestre) == [(*self._domanda_senza_file("Accesso negato", nome="Nuovo Sociale"), True)]
        if risposta == "no":
            assert principale._e_il_torneo_aperto(user_data_path("Tornello - Nuovo_Sociale.json"))
        else:
            assert principale._e_il_torneo_aperto(estate)
        assert os.path.normcase(principale._percorso_come_nell_albero(estate)[0]) in TestAlberoETorneoAttivo._tutti_i_file(principale)

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_il_ripristino_del_torneo_aperto_non_chiede(self, principale, suoni, monkeypatch, capsys, bloccata):
        """Il ripristino del torneo aperto stesso dalla finestra Copie di
        sicurezza non chiede niente e non salva prima, anche con le ultime
        modifiche soltanto in memoria: lo sostituisce apposta, e un
        salvataggio riscriverebbe sul disco lo stato di prima al posto della
        copia. Primavera 2 ha Roma soltanto in memoria; il blocco si toglie,
        e il ripristino scrive nel suo file la copia, con il luogo Firenze:
        dopo, nessuna domanda, e nel file e in memoria c'e' Firenze. Fino
        alla revisione del nono giro nessuna prova lo guardava, e senza la
        condizione sul torneo aperto stesso la copia si riscriveva in
        silenzio con Roma."""
        import json

        finestre = self._finestre(monkeypatch)
        bloccata.sblocca()
        copia = TestNomeEDataDiInizioDaDati._nel_file(bloccata.primavera)
        copia["site"] = "Firenze"
        with open(bloccata.primavera, "w", encoding="utf-8") as f:
            json.dump(copia, f, indent=1)

        principale._dopo_il_ripristino(SimpleNamespace(riuscito=True, tipo="torneo", destinazione=bloccata.primavera))

        assert self._domande_fatte(finestre) == []
        assert principale._e_il_torneo_aperto(bloccata.primavera)
        assert principale.current_tournament["site"] == "Firenze"
        assert TestNomeEDataDiInizioDaDati._nel_file(bloccata.primavera)["site"] == "Firenze"

    @pytest.mark.parametrize("strada", ["frecce", "invio"])
    def test_il_torneo_nuovo_lasciato_esce_dall_albero(self, principale, suoni, monkeypatch, strada):
        """Correzione della revisione della 10.19.20. Il torneo nuovo della
        procedura guidata che non si e' salvato resta aperto senza il suo
        file; poi il cursore va con le frecce sulla voce di Estate 3, o INVIO
        arriva sulla sua voce Dati, e con Si' alla domanda Estate 3 si apre;
        dalla proposta 4 del nono giro la domanda dice che il suo file non
        c'e' ancora, e che lasciandolo si perdono il torneo e i suoi iscritti.
        Il torneo nuovo non ha piu' niente da cui riaprirsi: la sua voce, con
        i suoi rami, e la voce Avvio torneo con il suo nome escono
        dall'albero, e il ramo In Preparazione esce, perche' resta vuoto, o,
        con Gamma in preparazione, conta un torneo in meno. Il cursore resta
        sulla stessa voce di Estate 3, senza che l'albero si ricostruisca, e
        senza messaggi. Fino alla revisione le voci restavano, e tornando
        sulla voce del torneo nuovo si vedeva il messaggio Errore nel
        caricamento del torneo, e nessun torneo restava aperto. La scrittura
        del file e le finestre di messaggio sono finte."""
        import wx

        from config import user_data_path

        estate = user_data_path("Tornello - Estate_3.json")
        TestNomeDelTorneoNuovo._scrivi(estate, _torneo_in_corso("Estate 3"))
        if strada == "invio":
            gamma = _torneo_in_corso("Gamma")
            gamma["rounds"] = []
            TestNomeDelTorneoNuovo._scrivi(user_data_path("Tornello - Gamma.json"), gamma)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        finestre = self._finestre(monkeypatch)
        TestTorneoCheNonSiSalva._scrittura_negata(monkeypatch)
        TestTorneoCheNonSiSalva._creato(principale, "Nuovo Sociale")
        nuovo = os.path.normcase(principale.active_filename)
        estate = principale._percorso_come_nell_albero(estate)[0]
        albero = TestAlberoETorneoAttivo
        prima = "In Preparazione (2)" if strada == "invio" else "In Preparazione (1)"
        assert prima in [testo for testo, _dati in albero._figlie(principale)]
        assert albero._tutti_i_file(principale).count(nuovo) > 1

        if strada == "frecce":
            voce = albero._voce(principale, action="select_tournament", filepath=estate)
            principale.tree_ctrl.SelectItem(voce)
        else:
            voce = albero._voce(principale, action="show_data", filepath=estate, field_active=None)
            with principale._albero_senza_caricamenti():
                principale.tree_ctrl.SelectItem(voce)
            principale.on_tree_item_activated(SimpleNamespace(GetItem=lambda: voce))
        _eventi_in_coda()

        assert self._domande_fatte(finestre) == [(*self._domanda_senza_file("Accesso negato", nome="Nuovo Sociale"), True)]
        assert principale._e_il_torneo_aperto(estate)
        assert nuovo not in albero._tutti_i_file(principale)
        preparazione = [testo for testo, _dati in albero._figlie(principale) if testo.startswith("In Preparazione")]
        assert preparazione == (["In Preparazione (1)"] if strada == "invio" else [])
        assert principale.tree_ctrl.GetSelection() == voce
        assert scatole == []


class TestAlberoDalTorneoInMemoria:
    """Proposta 1 del nono giro. L'albero prende sempre dalla memoria le
    voci del torneo aperto, anche quando il suo file c'e', e la
    ricostruzione non legge quel file: dopo una modifica che non si e'
    salvata, l'albero mostra quello su cui si lavora. Gli altri tornei si
    leggono dai loro file. Fino a questa proposta, e gia' nella 10.0.0, le
    voci del torneo aperto venivano dal file: dopo CANC su un iscritto con
    il file bloccato l'iscritto tolto restava nell'albero, e un secondo CANC
    sulla sua voce, con Si', non faceva niente, in silenzio. I blocchi sono
    veri, con CreateFileW; le finestre di messaggio sono finte."""

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_il_doppio_canc_con_il_file_bloccato(self, principale, suoni, monkeypatch, capsys):
        """Gamma e' aperta, in preparazione, e un altro programma tiene
        bloccato il suo file. CANC sul primo iscritto, con Si', lo toglie
        dalla memoria, e il messaggio Torneo non salvato lo dice. L'albero
        ricostruito ha tre iscritti, e la voce dell'iscritto tolto non c'e'
        piu': il secondo CANC su di lei non si puo' fare. Il file ha ancora
        i quattro iscritti."""
        canc = TestCancSuUnIscrittoDelTorneoAperto
        percorso = canc._gamma(principale)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        raccolte = TestRaccoltaSenzaPartiteNelCestino
        sblocca = raccolte._bloccata(percorso, raccolte.FILE_SHARE_READ)
        try:
            tolto = canc._canc_sul_primo_iscritto(principale, percorso)
            nel_file = TestNomeEDataDiInizioDaDati._nel_file(percorso)
        finally:
            sblocca()

        rimasti = [g[0] for g in GIOCATORI_DEI_TORNEI if g[0] != tolto]
        assert [f.titolo for f in finestre] == ["Conferma Rimozione Giocatore", "Torneo non salvato"]
        assert len(nel_file["players"]) == len(GIOCATORI_DEI_TORNEI)
        assert canc._iscritti_nell_albero(principale, percorso) == rimasti
        assert tolto not in canc._iscritti_nell_albero(principale, percorso)
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_players", "filepath": percorso})
        assert principale.tree_ctrl.GetItemText(voce) == f"iscritti ({len(rimasti)})"

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_il_luogo_non_salvato_si_vede_nell_albero(self, principale, suoni, monkeypatch, capsys):
        """Gamma cambia luogo, Roma, con il suo file bloccato, e il messaggio
        Torneo non salvato esce. L'albero ricostruito dice Roma nel ramo
        Dati, mentre il file ha ancora il luogo di prima."""
        percorso = TestCancSuUnIscrittoDelTorneoAperto._gamma(principale)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale.current_tournament["site"] = "Roma"
        TestTorneoCheNonSiSalva._salvataggi_bloccati(principale, percorso, volte=1)

        principale.populate_tree()

        assert [f.titolo for f in finestre] == ["Torneo non salvato"]
        assert TestNomeEDataDiInizioDaDati._nel_file(percorso).get("site") != "Roma"
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_data", "filepath": percorso, "field_active": "site"})
        assert voce and voce.IsOk()
        assert principale.tree_ctrl.GetItemText(voce) == "Luogo (Site): Roma"

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_il_luogo_non_salvato_con_il_percorso_scritto_in_minuscolo(self, principale, suoni, monkeypatch, capsys):
        """Correzione della proposta 1. Come la prova del luogo, con il file
        del torneo aperto scritto in minuscolo, un'altra forma dello stesso
        file su Windows: la ricostruzione riconosce lo stesso il torneo
        aperto, non legge il suo file, e dice Roma, in una voce sola."""
        from gui.main_frame import _chiave_del_percorso

        percorso = TestCancSuUnIscrittoDelTorneoAperto._gamma(principale)
        principale.active_filename = percorso.lower()
        assert principale.active_filename != percorso
        TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale.current_tournament["site"] = "Roma"
        TestTorneoCheNonSiSalva._salvataggi_bloccati(principale, percorso, volte=1)

        principale.populate_tree()

        assert TestNomeEDataDiInizioDaDati._nel_file(percorso).get("site") != "Roma"
        prep = principale._find_matching_item(principale.tree_root, {"action": "category_prep"})
        assert [t for t, _d in TestAlberoETorneoAttivo._figlie(principale, prep)] == ["Gamma"]
        voce = principale._voce_del_torneo_aperto()
        assert _chiave_del_percorso(principale.tree_ctrl.GetItemData(voce)["filepath"]) == _chiave_del_percorso(percorso)
        luogo = principale._find_matching_item(voce, {"action": "show_data", "filepath": percorso, "field_active": "site"})
        assert luogo and luogo.IsOk()
        assert principale.tree_ctrl.GetItemText(luogo) == "Luogo (Site): Roma"

    def test_il_torneo_concluso_aperto_dalla_memoria(self, principale, suoni, monkeypatch):
        """Correzione della proposta 1. Delta, concluso, sta nell'archivio
        ed e' aperto, con un luogo nuovo, Roma, che non si e' salvato. La
        ricostruzione prende dalla memoria anche il torneo concluso: il ramo
        Tornei Conclusi lo conta una volta, e la sua voce Luogo dice Roma."""
        import json

        from config import ARCHIVED_TOURNAMENTS_DIR

        percorso = os.path.join(ARCHIVED_TOURNAMENTS_DIR, "2026", "10 Ottobre", "Delta", "Tornello - Delta.json")
        concluso = _torneo_in_corso("Delta", finito=True)
        concluso["concluded"] = True
        TestNomeDelTorneoNuovo._scrivi(percorso, concluso)
        principale.load_tournament(percorso)
        assert principale._e_il_torneo_aperto(percorso)
        percorso = principale.active_filename
        principale.current_tournament["site"] = "Roma"

        principale.populate_tree()

        with open(percorso, encoding="utf-8") as f:
            assert json.load(f).get("site") != "Roma"
        voce = principale._voce_del_torneo_aperto()
        assert principale.tree_ctrl.GetItemText(voce).startswith("Delta")
        assert principale.tree_ctrl.GetItemText(principale.tree_ctrl.GetItemParent(voce)) == "Tornei Conclusi (1)"
        luogo = principale._find_matching_item(voce, {"action": "show_data", "filepath": percorso, "field_active": "site"})
        assert luogo and luogo.IsOk()
        assert principale.tree_ctrl.GetItemText(luogo) == "Luogo (Site): Roma"

    @staticmethod
    def _gamma_e_alfa(principale):
        """Alfa, in corso, e Gamma, aperta, in preparazione, nella cartella
        del programma. Restituisce i due file come li scrive l'albero."""
        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        TestNomeDelTorneoNuovo._scrivi(alfa, _torneo_in_corso("Alfa"))
        gamma = TestCancSuUnIscrittoDelTorneoAperto._gamma(principale)
        return gamma, principale._percorso_come_nell_albero(alfa)[0]

    @staticmethod
    def _etichette_dei_tornei(principale):
        """Le etichette delle voci di primo livello e di quelle del ramo In
        Preparazione, in ordine."""
        figlie = TestAlberoETorneoAttivo._figlie
        etichette = []
        for testo, dati in figlie(principale):
            etichette.append(testo)
            if (dati or {}).get("action") == "category_prep":
                voce = principale._find_matching_item(principale.tree_root, {"action": "category_prep"})
                etichette.append([t for t, _d in figlie(principale, voce)])
        return etichette

    @staticmethod
    def _lascia_gamma(principale, strada, alfa):
        """Da Gamma su Alfa, con le frecce sulla voce di Alfa o con INVIO
        sulla sua voce Dati, dove c'e' il cursore; poi le chiamate lasciate a
        wx.CallAfter."""
        import wx

        if strada == "frecce":
            TestAlberoETorneoAttivo()._scegli_torneo(principale, alfa)
        else:
            voce = TestAlberoETorneoAttivo._voce(principale, action="show_data", filepath=alfa)
            with principale._albero_senza_caricamenti():
                principale.tree_ctrl.SelectItem(voce)
            principale.on_tree_item_activated(wx.TreeEvent(wx.wxEVT_TREE_ITEM_ACTIVATED, principale.tree_ctrl, voce))
        _eventi_in_coda()
        assert principale._e_il_torneo_aperto(alfa)

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    @pytest.mark.parametrize("strada", ["frecce", "invio"])
    def test_il_torneo_lasciato_con_si_torna_com_e_nel_file(self, principale, suoni, monkeypatch, capsys, strada):
        """Correzione della proposta 1. Gamma e' aperta, con il file
        bloccato: CANC sul primo iscritto, con Si', lo toglie dalla memoria e
        dall'albero. Con le frecce o con INVIO su Alfa, e Si' alla domanda
        Torneo non salvato, la rimozione si perde: la voce di Gamma si rifa'
        dal file, con i quattro iscritti, nello stesso posto, mentre il
        cursore resta su Alfa. Tornando su Gamma, che si riapre dal file,
        l'albero dice ancora quattro iscritti, come la memoria. Fino alla
        correzione la voce mostrava tre iscritti, anche dopo la riapertura."""
        canc = TestCancSuUnIscrittoDelTorneoAperto
        gamma, alfa = self._gamma_e_alfa(principale)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        raccolte = TestRaccoltaSenzaPartiteNelCestino
        sblocca = raccolte._bloccata(gamma, raccolte.FILE_SHARE_READ)
        tutti = [g[0] for g in GIOCATORI_DEI_TORNEI]
        try:
            tolto = canc._canc_sul_primo_iscritto(principale, gamma)
            assert tolto not in canc._iscritti_nell_albero(principale, gamma)
            voci_prima = self._etichette_dei_tornei(principale)
            self._lascia_gamma(principale, strada, alfa)
            scelta = principale.tree_ctrl.GetItemData(principale.tree_ctrl.GetSelection())

            assert [f.titolo for f in finestre] == ["Conferma Rimozione Giocatore", "Torneo non salvato", "Torneo non salvato"]
            assert canc._iscritti_nell_albero(principale, gamma) == tutti
            voce = principale._find_matching_item(principale.tree_root, {"action": "show_players", "filepath": gamma})
            assert principale.tree_ctrl.GetItemText(voce) == f"iscritti ({len(tutti)})"
            assert self._etichette_dei_tornei(principale) == voci_prima
            assert scelta["filepath"] == alfa

            TestAlberoETorneoAttivo()._scegli_torneo(principale, gamma)
            _eventi_in_coda()
        finally:
            sblocca()
        assert principale._e_il_torneo_aperto(gamma)
        assert [p["id"] for p in principale.current_tournament["players"]] == tutti
        assert canc._iscritti_nell_albero(principale, gamma) == tutti

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_il_luogo_perso_non_resta_nella_voce_del_torneo_lasciato(self, principale, suoni, monkeypatch, capsys):
        """Correzione della proposta 1. Gamma ha il luogo Roma, che non si e'
        salvato, e il ramo Dati aperto. Con le frecce su Alfa, e Si' alla
        domanda, la voce Luogo di Gamma dice il luogo del file, e il ramo
        Dati resta aperto. Fino alla correzione diceva Roma, anche dopo che
        Gamma si riapriva dal suo file."""
        gamma, alfa = self._gamma_e_alfa(principale)
        TestNomeDelTorneoNuovo._domande(monkeypatch)
        principale.current_tournament["site"] = "Roma"
        raccolte = TestRaccoltaSenzaPartiteNelCestino
        sblocca = raccolte._bloccata(gamma, raccolte.FILE_SHARE_READ)
        try:
            principale._save_state()
            principale.populate_tree()
            dati = TestAlberoETorneoAttivo._voce(principale, action="show_data", filepath=gamma)
            principale.tree_ctrl.Expand(dati)
            luogo = TestAlberoETorneoAttivo._voce(principale, action="show_data", filepath=gamma, field_active="site")
            assert principale.tree_ctrl.GetItemText(luogo) == "Luogo (Site): Roma"
            self._lascia_gamma(principale, "frecce", alfa)
        finally:
            sblocca()

        nel_file = TestNomeEDataDiInizioDaDati._nel_file(gamma).get("site", "N/D")
        assert nel_file != "Roma"
        luogo = TestAlberoETorneoAttivo._voce(principale, action="show_data", filepath=gamma, field_active="site")
        assert principale.tree_ctrl.GetItemText(luogo) == f"Luogo (Site): {nel_file}"
        assert principale.tree_ctrl.IsExpanded(TestAlberoETorneoAttivo._voce(principale, action="show_data", filepath=gamma))

    def test_la_ricostruzione_non_legge_il_file_del_torneo_aperto(self, principale, suoni, monkeypatch):
        """Alfa, in corso, e Gamma, in preparazione, sono nella cartella del
        programma, e Gamma e' aperta. La ricostruzione dell'albero legge il
        file di Alfa e non quello di Gamma, che ha la sua voce, con il nome
        di sempre, nel ramo In Preparazione, che la conta, e la voce Avvio
        torneo."""
        import builtins

        import gui.main_frame as mf
        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        TestNomeDelTorneoNuovo._scrivi(alfa, _torneo_in_corso("Alfa"))
        percorso = TestCancSuUnIscrittoDelTorneoAperto._gamma(principale)
        letti = []

        def annota(file, *a, **k):
            letti.append(mf._chiave_del_percorso(file))
            return builtins.open(file, *a, **k)

        with monkeypatch.context() as m:
            m.setattr(mf, "open", annota, raising=False)
            principale.populate_tree()

        assert mf._chiave_del_percorso(alfa) in letti
        assert mf._chiave_del_percorso(percorso) not in letti
        voce = principale._voce_del_torneo_aperto()
        assert principale.tree_ctrl.GetItemText(voce) == "Gamma"
        assert principale.tree_ctrl.GetItemText(principale.tree_ctrl.GetItemParent(voce)) == "In Preparazione (1)"
        assert principale._find_matching_item(principale.tree_root, {"action": "start_tournament_matchmaking_action", "filepath": percorso}) is not None


class TestCancSuUnIscrittoDelTorneoAperto:
    """Dalla 10.19.22 (decisione di Gabriele del 5 novembre 2026) CANC su un
    iscritto del torneo aperto, in preparazione, con Si', lo toglie dalla
    memoria, da players e da players_dict, e salva il torneo con
    _save_state, come ogni altra modifica, con la scrittura atomica e senza
    players_dict nel file: le modifiche soltanto in memoria restano, e un
    file bloccato lo dice il messaggio Torneo non salvato. Fino alla
    10.19.21, e gia' nella 10.0.0, CANC rileggeva il file, lo riscriveva con
    json.dump e lo rimetteva in memoria: le modifiche si perdevano senza
    avviso, e con il file bloccato usciva Impossibile rimuovere il
    giocatore. Un iscritto di un torneo che non e' quello aperto si toglie
    dal suo file, scritto con save_tournament. I blocchi sono veri, con
    CreateFileW; le finestre di messaggio sono finte."""

    @staticmethod
    def _gamma(principale, aperta=True):
        """Gamma, in preparazione con i quattro iscritti dei tornei delle
        prove, nella cartella del programma, aperta se aperta e' vero, con
        l'albero che la mostra. Restituisce il suo file come lo scrive
        l'albero."""
        from config import user_data_path

        percorso = user_data_path("Tornello - Gamma.json")
        dati = _torneo_in_corso("Gamma")
        dati["rounds"] = []
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        if aperta:
            principale.load_tournament(percorso)
            assert principale._e_il_torneo_aperto(percorso)
        else:
            principale.populate_tree()
        return principale._percorso_come_nell_albero(percorso)[0]

    @staticmethod
    def _canc_sul_primo_iscritto(principale, percorso):
        """CANC sulla voce del primo iscritto di Gamma nell'albero.
        Restituisce il suo identificativo."""
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_player_detail", "filepath": percorso})
        assert voce and voce.IsOk()
        giocatore = principale.tree_ctrl.GetItemData(voce)["player"]
        principale.delete_player_from_tournament(voce, giocatore)
        return giocatore["id"]

    @staticmethod
    def _iscritti_nell_albero(principale, percorso, genitore=None):
        """Gli identificativi degli iscritti di Gamma nell'albero."""
        from gui.main_frame import _chiave_del_percorso

        albero = principale.tree_ctrl
        genitore = principale.tree_root if genitore is None else genitore
        trovati = []
        voce, cookie = albero.GetFirstChild(genitore)
        while voce.IsOk():
            dati = albero.GetItemData(voce) or {}
            if dati.get("action") == "show_player_detail" and _chiave_del_percorso(dati.get("filepath")) == _chiave_del_percorso(percorso):
                trovati.append(dati["player"]["id"])
            trovati += TestCancSuUnIscrittoDelTorneoAperto._iscritti_nell_albero(principale, percorso, voce)
            voce, cookie = albero.GetNextChild(genitore, cookie)
        return trovati

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_il_luogo_che_non_si_era_salvato_resta(self, principale, suoni, monkeypatch, capsys):
        """Gamma cambia luogo, Roma, con il suo file bloccato, e il messaggio
        Torneo non salvato esce. Tolto il blocco, CANC sul primo iscritto, con
        Si', lo toglie e salva: nel file ci sono Roma e tre iscritti, senza
        players_dict, e in memoria Roma resta, con tre iscritti anche in
        players_dict; l'albero ne mostra tre, e non esce un altro messaggio.
        Fino alla 10.19.21 CANC rileggeva il file, e Roma si perdeva."""
        percorso = self._gamma(principale)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        suoni.clear()
        principale.current_tournament["site"] = "Roma"
        TestTorneoCheNonSiSalva._salvataggi_bloccati(principale, percorso, volte=1)

        tolto = self._canc_sul_primo_iscritto(principale, percorso)

        rimasti = [g[0] for g in GIOCATORI_DEI_TORNEI if g[0] != tolto]
        nel_file = TestNomeEDataDiInizioDaDati._nel_file(percorso)
        assert nel_file.get("site") == "Roma"
        assert [p["id"] for p in nel_file["players"]] == rimasti
        assert "players_dict" not in nel_file
        assert principale.current_tournament["site"] == "Roma"
        assert [p["id"] for p in principale.current_tournament["players"]] == rimasti
        assert sorted(principale.current_tournament["players_dict"]) == sorted(rimasti)
        assert self._iscritti_nell_albero(principale, percorso) == rimasti
        assert [f.titolo for f in finestre] == ["Torneo non salvato", "Conferma Rimozione Giocatore"]
        assert suoni.count("errore") == 1
        assert "rimozione_giocatore" in suoni

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_con_il_file_bloccato_lo_dice_torneo_non_salvato(self, principale, suoni, monkeypatch, capsys):
        """Il file di Gamma e' bloccato, e CANC sul primo iscritto, con Si':
        l'iscritto esce dalla memoria, e il salvataggio che non riesce lo
        dice il messaggio Torneo non salvato, con la descrizione del motivo,
        e non Impossibile rimuovere il giocatore. Il file resta com'era;
        tolto il blocco, il salvataggio dopo scrive tre iscritti."""
        import wx

        percorso = self._gamma(principale)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        suoni.clear()
        capsys.readouterr()
        raccolte = TestRaccoltaSenzaPartiteNelCestino
        sblocca = raccolte._bloccata(percorso, raccolte.FILE_SHARE_READ)
        try:
            tolto = self._canc_sul_primo_iscritto(principale, percorso)
            nel_file = TestNomeEDataDiInizioDaDati._nel_file(percorso)
        finally:
            sblocca()

        rimasti = [g[0] for g in GIOCATORI_DEI_TORNEI if g[0] != tolto]
        errori, _della_raccolta = TestTorneoCheNonSiSalva._errori_in_console(capsys, percorso)
        assert len(errori) == 1
        assert scatole == []
        assert [(f.titolo, f.testo) for f in finestre] == [
            ("Conferma Rimozione Giocatore", finestre[0].testo),
            TestTorneoCheNonSiSalva._messaggio(percorso, _descrizione_dell_errore(errori[0]), nome="Gamma"),
        ]
        assert len(nel_file["players"]) == len(GIOCATORI_DEI_TORNEI)
        assert [p["id"] for p in principale.current_tournament["players"]] == rimasti
        assert sorted(principale.current_tournament["players_dict"]) == sorted(rimasti)

        principale._save_state()

        assert [p["id"] for p in TestNomeEDataDiInizioDaDati._nel_file(percorso)["players"]] == rimasti

    def test_l_iscritto_di_un_torneo_che_non_e_aperto(self, principale, suoni, monkeypatch):
        """Alfa, in corso, e' il torneo aperto, e CANC arriva sul primo
        iscritto di Gamma, che non e' aperta: Gamma si legge dal suo file, e
        con Si' l'iscritto si toglie dal file, scritto con save_tournament,
        senza players_dict, mentre Alfa resta aperta com'era. Fino alla
        10.19.21 json.dump scriveva anche players_dict."""
        import copy

        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        TestNomeDelTorneoNuovo._scrivi(alfa, _torneo_in_corso("Alfa"))
        principale.load_tournament(alfa)
        prima = copy.deepcopy(principale.current_tournament)
        percorso = self._gamma(principale, aperta=False)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)

        tolto = self._canc_sul_primo_iscritto(principale, percorso)

        nel_file = TestNomeEDataDiInizioDaDati._nel_file(percorso)
        assert [p["id"] for p in nel_file["players"]] == [g[0] for g in GIOCATORI_DEI_TORNEI if g[0] != tolto]
        assert "players_dict" not in nel_file
        assert [f.titolo for f in finestre] == ["Conferma Rimozione Giocatore"]
        assert principale._e_il_torneo_aperto(alfa)
        assert principale.current_tournament == prima

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_l_iscritto_di_un_torneo_che_non_e_aperto_con_il_file_bloccato(self, principale, suoni, monkeypatch, capsys):
        """Alfa e' il torneo aperto, e un altro programma tiene bloccato il
        file di Gamma, che non e' aperta: CANC sul primo iscritto di Gamma,
        con Si', non riesce a scriverne il file. Dalla proposta 5 del nono
        giro esce, con il suono dell'errore, il messaggio Giocatore non
        rimosso, nella finestra accessibile, che nomina il giocatore, il
        torneo e il file, con la descrizione del motivo che save_tournament
        da' dalla revisione della 10.19.19, e niente altro: il file di Gamma
        ha ancora i quattro iscritti, anche nell'albero, non si sente il
        suono della rimozione, e la barra di stato non la dice riuscita.
        Fino alla proposta usciva un wx.MessageBox senza suono, Impossibile
        rimuovere il giocatore, con la sola descrizione, senza il torneo e
        senza il file; fino alla revisione del nono giro nessuna prova
        guardava questo ramo."""
        import wx

        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        TestNomeDelTorneoNuovo._scrivi(alfa, _torneo_in_corso("Alfa"))
        principale.load_tournament(alfa)
        percorso = self._gamma(principale, aperta=False)
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_player_detail", "filepath": percorso})
        giocatore = principale.tree_ctrl.GetItemData(voce)["player"]
        nome_del_giocatore = f"{giocatore['last_name']} {giocatore['first_name']}"
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        suoni.clear()
        capsys.readouterr()
        barra = principale.last_status_msg
        raccolte = TestRaccoltaSenzaPartiteNelCestino
        sblocca = raccolte._bloccata(percorso, raccolte.FILE_SHARE_READ)
        try:
            self._canc_sul_primo_iscritto(principale, percorso)
        finally:
            sblocca()

        errori, _della_raccolta = TestTorneoCheNonSiSalva._errori_in_console(capsys, percorso)
        assert len(errori) == 1
        assert scatole == []
        assert [(f.titolo, f.testo) for f in finestre] == [
            ("Conferma Rimozione Giocatore", f"Sei sicuro di voler rimuovere il giocatore {nome_del_giocatore} dal torneo?"),
            (
                "Giocatore non rimosso",
                f"Il giocatore {nome_del_giocatore} non si è potuto rimuovere dal torneo Gamma, perché il file {percorso} non si è potuto salvare: "
                f"{_descrizione_dell_errore(errori[0])}. Il file del torneo e i suoi iscritti restano com'erano. "
                "Se un altro programma tiene aperto il file, chiudilo e riprova.",
            ),
        ]
        assert suoni == ["errore"]
        assert len(TestNomeEDataDiInizioDaDati._nel_file(percorso)["players"]) == len(GIOCATORI_DEI_TORNEI)
        assert len(self._iscritti_nell_albero(principale, percorso)) == len(GIOCATORI_DEI_TORNEI)
        assert principale.last_status_msg == barra
        assert principale._e_il_torneo_aperto(alfa)

    def _alfa_aperta_e_gamma(self, principale):
        """Alfa, in corso, aperta, e Gamma, in preparazione, non aperta, con
        l'albero che le mostra. Restituisce il file di Alfa, quello di Gamma
        come lo scrive l'albero, e il nome del primo iscritto di Gamma come
        lo dicono i messaggi."""
        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        TestNomeDelTorneoNuovo._scrivi(alfa, _torneo_in_corso("Alfa"))
        principale.load_tournament(alfa)
        percorso = self._gamma(principale, aperta=False)
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_player_detail", "filepath": percorso})
        giocatore = principale.tree_ctrl.GetItemData(voce)["player"]
        return alfa, percorso, f"{giocatore['last_name']} {giocatore['first_name']}"

    @pytest.mark.parametrize(("guasto", "motivo"), GUASTI_DEL_FILE)
    def test_l_iscritto_di_un_torneo_non_aperto_con_il_file_che_non_si_legge(self, principale, suoni, monkeypatch, guasto, motivo):
        """Alfa e' il torneo aperto, e Gamma, che non e' aperta, ha le sue
        voci nell'albero, poi il suo file sparisce, o si rovina. CANC sul
        primo iscritto di Gamma: dalla 10.19.30 si sente il suono
        dell'errore, ed esce subito, senza la domanda Conferma Rimozione
        Giocatore, il messaggio Giocatore non rimosso, nella finestra
        accessibile, che nomina il giocatore, il torneo e il file, con la
        sola descrizione del motivo, e dice che il torneo e i suoi iscritti
        restano com'erano. L'albero ha ancora i quattro iscritti di Gamma, e
        la barra di stato e Alfa restano com'erano. Fino alla 10.19.29 usciva
        un wx.MessageBox senza suono, Impossibile leggere il file del torneo,
        con il testo intero dell'errore. Dalla 10.19.36 lo stesso vale per un
        file che non ha la forma di un torneo, come una lista: fino alla
        10.19.35 CANC si fermava con un errore che si vedeva soltanto in
        console. Nessun controllo chiede il fuoco."""
        import wx

        alfa, percorso, nome_del_giocatore = self._alfa_aperta_e_gamma(principale)
        _guasta_il_file(percorso, guasto)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()
        barra = principale.last_status_msg

        self._canc_sul_primo_iscritto(principale, percorso)

        assert registro.fuoco == []
        assert scatole == []
        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (
                "Giocatore non rimosso",
                f"Il giocatore {nome_del_giocatore} non si è potuto rimuovere dal torneo Gamma, perché il file {percorso} non si è potuto leggere: "
                f"{motivo}. Il torneo e i suoi iscritti restano com'erano.",
                False,
            )
        ]
        assert suoni == ["errore"]
        assert len(self._iscritti_nell_albero(principale, percorso)) == len(GIOCATORI_DEI_TORNEI)
        assert principale.last_status_msg == barra
        assert principale._e_il_torneo_aperto(alfa)

    def test_l_iscritto_di_un_torneo_non_aperto_con_un_errore_imprevisto(self, principale, suoni, monkeypatch):
        """Alfa e' il torneo aperto, e CANC arriva sul primo iscritto di
        Gamma, che non e' aperta; con Si', un errore imprevisto, qui finto,
        nella scrittura del file di Gamma. Dalla 10.19.30 si sente il suono
        dell'errore, ed esce il messaggio Giocatore non rimosso, nella
        finestra accessibile, che nomina il giocatore, il torneo e il file,
        con la descrizione del motivo, e dice che il file e gli iscritti
        restano com'erano: il file di Gamma ne ha ancora quattro, come
        l'albero, non si sente il suono della rimozione, e la barra di stato
        resta com'era. Fino alla 10.19.29 usciva un wx.MessageBox senza
        suono, Impossibile rimuovere il giocatore, con il testo intero
        dell'errore."""
        import wx

        import tournament

        alfa, percorso, nome_del_giocatore = self._alfa_aperta_e_gamma(principale)

        def guasto(*argomenti, **opzioni):
            raise RuntimeError("guasto finto")

        monkeypatch.setattr(tournament, "save_tournament", guasto)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        suoni.clear()
        barra = principale.last_status_msg

        self._canc_sul_primo_iscritto(principale, percorso)

        assert scatole == []
        assert [(f.titolo, f.testo) for f in finestre] == [
            ("Conferma Rimozione Giocatore", f"Sei sicuro di voler rimuovere il giocatore {nome_del_giocatore} dal torneo?"),
            (
                "Giocatore non rimosso",
                f"Il giocatore {nome_del_giocatore} non si è potuto rimuovere dal torneo Gamma, nel file {percorso}, per un errore imprevisto: "
                "guasto finto. Il file del torneo e i suoi iscritti restano com'erano.",
            ),
        ]
        assert suoni == ["errore"]
        assert len(TestNomeEDataDiInizioDaDati._nel_file(percorso)["players"]) == len(GIOCATORI_DEI_TORNEI)
        assert len(self._iscritti_nell_albero(principale, percorso)) == len(GIOCATORI_DEI_TORNEI)
        assert principale.last_status_msg == barra
        assert principale._e_il_torneo_aperto(alfa)

    @pytest.mark.parametrize("aperta", [False, True])
    def test_un_errore_imprevisto_dopo_che_il_giocatore_e_uscito(self, principale, suoni, monkeypatch, aperta):
        """CANC sul primo iscritto di Gamma, aperta o no, con Si': il
        giocatore esce dal torneo, e il file di Gamma si scrive con tre
        iscritti, poi un errore imprevisto, qui finto, nel ridisegno
        dell'albero. Dalla 10.19.30 si sente il suono dell'errore, e non
        quello della rimozione, ed esce il messaggio Rimozione non conclusa,
        nella finestra accessibile, che dice che il giocatore e' uscito dal
        torneo, con la descrizione del motivo, e che l'albero potrebbe
        mostrarlo ancora. Fino alla 10.19.29 usciva un wx.MessageBox senza
        suono, Impossibile rimuovere il giocatore, anche se il giocatore
        era gia' uscito."""
        import wx

        if aperta:
            percorso = self._gamma(principale)
            voce = principale._find_matching_item(principale.tree_root, {"action": "show_player_detail", "filepath": percorso})
            giocatore = principale.tree_ctrl.GetItemData(voce)["player"]
            nome_del_giocatore = f"{giocatore['last_name']} {giocatore['first_name']}"
        else:
            _alfa, percorso, nome_del_giocatore = self._alfa_aperta_e_gamma(principale)

        def guasto(*argomenti, **opzioni):
            raise RuntimeError("guasto finto")

        monkeypatch.setattr(principale, "populate_tree", guasto)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        suoni.clear()

        tolto = self._canc_sul_primo_iscritto(principale, percorso)

        assert scatole == []
        assert [(f.titolo, f.testo) for f in finestre] == [
            ("Conferma Rimozione Giocatore", f"Sei sicuro di voler rimuovere il giocatore {nome_del_giocatore} dal torneo?"),
            (
                "Rimozione non conclusa",
                f"Il giocatore {nome_del_giocatore} è uscito dal torneo Gamma, ma poi un errore imprevisto ha interrotto l'operazione: "
                "guasto finto. L'albero potrebbe mostrarlo ancora fra gli iscritti.",
            ),
        ]
        assert suoni == ["errore"]
        rimasti = [g[0] for g in GIOCATORI_DEI_TORNEI if g[0] != tolto]
        assert [p["id"] for p in TestNomeEDataDiInizioDaDati._nel_file(percorso)["players"]] == rimasti
        if aperta:
            assert [p["id"] for p in principale.current_tournament["players"]] == rimasti



class TestBarraDopoIndietro:
    """10.19.32 (decisione di Gabriele del 7 novembre 2026). Nuovo torneo
    dal menu File con un torneo aperto, e poi INVIO sulla voce Indietro
    della procedura guidata: il torneo resta aperto, e la barra di stato lo
    nomina, Pronto. Torneo aperto:, con il suo nome, anche quando ha le
    ultime modifiche soltanto in memoria. Senza un torneo aperto dice
    Pronto. Nessun torneo caricato., come prima. Fino alla 10.19.31 diceva
    sempre cosi', anche con il torneo aperto, e il titolo della finestra lo
    nominava. Le finestre di messaggio sono finte."""

    bloccata = TestTorneoNonSalvatoDaLasciare.bloccata

    @staticmethod
    def _indietro(principale):
        """INVIO sulla voce Indietro della procedura guidata."""
        voce = TestAlberoETorneoAttivo._voce(principale, action="wizard_back")
        principale.on_tree_item_activated(SimpleNamespace(GetItem=lambda: voce))
        _eventi_in_coda()

    @staticmethod
    def _prima_riga_della_barra(principale):
        return principale.status_text.GetValue().replace("\r", "\n").split("\n")[0]

    def test_con_il_torneo_salvato(self, principale, suoni, monkeypatch):
        """Alfa e' aperta e salvata: dopo Indietro Alfa resta aperta, con
        il titolo e il cursore sulla sua voce, e la barra di stato dice
        Pronto. Torneo aperto: Alfa., senza suoni e senza messaggi."""
        import wx

        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        percorsi = TestAlberoETorneoAttivo()._prepara("Alfa")
        principale.load_tournament(percorsi["Alfa"])
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        assert principale.creation_mode
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        self._indietro(principale)

        assert not principale.creation_mode
        assert principale._e_il_torneo_aperto(percorsi["Alfa"])
        assert principale.GetTitle().endswith("[Alfa]")
        assert principale.last_status_msg == "Pronto. Torneo aperto: Alfa."
        assert self._prima_riga_della_barra(principale) == "Pronto. Torneo aperto: Alfa."
        assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": principale.active_filename}
        assert registro.caricati == []
        # Il fuoco resta sull'albero, dove era arrivato INVIO: nessuno lo
        # sposta.
        assert registro.fuoco == []
        assert suoni == []
        assert finestre == []
        assert scatole == []

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    def test_con_il_torneo_che_ha_le_modifiche_soltanto_in_memoria(self, principale, suoni, monkeypatch, capsys, bloccata):
        """Primavera 2 ha Roma soltanto in memoria: Nuovo torneo, Si' alla
        domanda Torneo non salvato, e Indietro. Primavera 2 resta aperta,
        con Roma, e la barra di stato dice Pronto. Torneo aperto: Primavera
        2., senza altre domande, suoni o messaggi."""
        import wx

        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch, [wx.ID_YES])
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        assert [f.titolo for f in finestre] == ["Torneo non salvato"]
        assert principale.creation_mode
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        self._indietro(principale)

        assert not principale.creation_mode
        TestTorneoNonSalvatoDaLasciare._primavera_com_era(principale, bloccata)
        assert principale.GetTitle().endswith("[Primavera 2]")
        assert principale.last_status_msg == "Pronto. Torneo aperto: Primavera 2."
        assert self._prima_riga_della_barra(principale) == "Pronto. Torneo aperto: Primavera 2."
        assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": bloccata.primavera}
        assert registro.caricati == []
        # Il fuoco resta sull'albero, dove era arrivato INVIO: nessuno lo
        # sposta.
        assert registro.fuoco == []
        assert suoni == []
        assert [f.titolo for f in finestre] == ["Torneo non salvato"]
        assert scatole == []

    def test_senza_torneo_aperto(self, principale, suoni, monkeypatch):
        """Senza un torneo aperto la barra di stato dice, come prima,
        Pronto. Nessun torneo caricato., e il cursore va su Nuovo torneo."""
        import wx

        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        TestAlberoETorneoAttivo()._prepara("Alfa", "Beta")
        principale.populate_tree()
        assert principale.current_tournament is None
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        suoni.clear()

        self._indietro(principale)

        assert principale.current_tournament is None
        assert principale.last_status_msg == "Pronto. Nessun torneo caricato."
        assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "start_new_tournament"}
        assert suoni == []
        assert scatole == []

    def test_l_avviso_di_un_file_che_non_si_legge_non_tiene_la_frase(self, principale, suoni, monkeypatch):
        """Mentre la procedura guidata e' aperta, un file di torneo della
        cartella del programma si rovina: Indietro ridisegna l'albero, che lo
        scopre, e la barra di stato dice soltanto l'avviso, senza la frase
        Pronto. Torneo aperto: Alfa. davanti, come prima senza la frase
        Pronto. Nessun torneo caricato.: la frase di riposo non e' un esito
        da conservare."""
        import wx

        from config import user_data_path

        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: None)
        percorsi = TestAlberoETorneoAttivo()._prepara("Alfa")
        principale.load_tournament(percorsi["Alfa"])
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        with open(user_data_path("Tornello - Rotto.json"), "w", encoding="utf-8") as f:
            f.write("{rotto")

        self._indietro(principale)

        assert principale._e_il_torneo_aperto(percorsi["Alfa"])
        assert principale.last_status_msg == "Attenzione: un file di torneo non leggibile, dettagli sotto."


class TestAreaCentraleDopoIndietro:
    """10.19.45 (decisione di Gabriele del 7 novembre 2026). Nuovo torneo
    dal menu File, e poi INVIO sulla voce Indietro della procedura guidata:
    con un torneo aperto l'area centrale mostra il suo turno corrente, come
    dopo Apri Torneo dentro la procedura dalla 10.19.34; senza un torneo
    aperto mostra il benvenuto, come prima. Fino alla 10.19.44, e gia' nella
    10.0.0, mostrava sempre il benvenuto, anche con il torneo aperto, che
    la barra di stato nominava dalla 10.19.32. La barra, il cursore e il
    fuoco restano quelli della 10.19.32. Le finestre di messaggio sono
    finte."""

    BENVENUTO = "Ciao! Benvenuto, sono Tornello"

    def test_con_un_torneo_aperto(self, principale, suoni, monkeypatch):
        """Alfa e' aperta e salvata, al turno 1: dopo Indietro l'area
        centrale mostra il turno corrente di Alfa, lo stesso testo di prima
        di Nuovo torneo, senza il benvenuto, e la barra di stato dice Pronto.
        Torneo aperto: Alfa., senza suoni, senza messaggi e senza spostare il
        fuoco."""
        import wx

        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        percorsi = TestAlberoETorneoAttivo()._prepara("Alfa")
        principale.load_tournament(percorsi["Alfa"])
        turno_corrente = principale.main_text.GetValue()
        assert turno_corrente.startswith("Torneo: Alfa\nTurno Corrente: 1 di 3\nAbbinamenti Turno 1:\n")
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        assert principale.creation_mode
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        TestBarraDopoIndietro._indietro(principale)

        assert not principale.creation_mode
        assert principale.main_text.GetValue() == turno_corrente
        assert self.BENVENUTO not in principale.main_text.GetValue()
        assert principale.last_status_msg == "Pronto. Torneo aperto: Alfa."
        assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": principale.active_filename}
        assert registro.caricati == []
        assert registro.fuoco == []
        assert suoni == []
        assert finestre == []
        assert scatole == []

    def test_senza_torneo_aperto(self, principale, suoni, monkeypatch):
        """Senza un torneo aperto l'area centrale mostra il benvenuto, come
        prima, e la barra di stato dice Pronto. Nessun torneo caricato."""
        import wx

        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        TestAlberoETorneoAttivo()._prepara("Alfa")
        principale.populate_tree()
        assert principale.current_tournament is None
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        suoni.clear()

        TestBarraDopoIndietro._indietro(principale)

        assert principale.current_tournament is None
        assert principale.main_text.GetValue().startswith(self.BENVENUTO)
        assert principale.last_status_msg == "Pronto. Nessun torneo caricato."
        assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "start_new_tournament"}
        assert suoni == []
        assert scatole == []

    AIUTO_DI_INDIETRO = (
        "Indietro\n\nSeleziona questa voce per annullare la creazione del torneo e tornare al torneo aperto, o, "
        "senza un torneo aperto, alla schermata iniziale.\n"
    )

    def test_l_aiuto_della_voce_indietro(self, principale, suoni, monkeypatch):
        """Correzione della 10.19.45 (decisione di Gabriele dell'8 novembre
        2026). Alfa e' aperta, e dopo Nuovo torneo il cursore arriva sulla
        voce Indietro: l'area centrale mostra il suo aiuto, che dice dove si
        torna, al torneo aperto o, senza un torneo aperto, alla schermata
        iniziale. Fino alla 10.19.44, e gia' nella 10.0.0, diceva di tornare
        alla schermata iniziale anche con il torneo aperto. Nessun suono,
        nessun messaggio, nessun caricamento, e il fuoco non si sposta."""
        import wx

        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        percorsi = TestAlberoETorneoAttivo()._prepara("Alfa")
        principale.load_tournament(percorsi["Alfa"])
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        assert principale.creation_mode
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()
        voce = TestAlberoETorneoAttivo._voce(principale, action="wizard_back")

        principale.on_tree_selection_changed(SimpleNamespace(GetItem=lambda: voce))

        assert principale.main_text.GetValue() == self.AIUTO_DI_INDIETRO
        assert principale.creation_mode
        assert principale._e_il_torneo_aperto(percorsi["Alfa"])
        assert registro.caricati == []
        assert registro.fuoco == []
        assert suoni == []
        assert finestre == []
        assert scatole == []


class TestApriTorneoNellaProceduraGuidata:
    """10.19.34 (decisione di Gabriele del 7 novembre 2026). Ogni Apri
    Torneo riuscito dentro la procedura guidata di un torneo nuovo la
    chiude: l'albero torna con i tornei e prende il fuoco, con il cursore
    sulla voce del torneo aperto, e l'area centrale mostra il suo turno
    corrente, come dopo un caricamento. Fino alla 10.19.33 lo faceva
    soltanto Apri Torneo sul file del torneo aperto con le modifiche
    soltanto in memoria (10.19.29): con un altro torneo il torneo si apriva,
    ma la procedura restava sullo schermo, e il cursore non andava su
    nessuna voce. Un Apri Torneo che non riesce, o annullato, lascia la
    procedura com'e'. Le finestre di messaggio e quella di Apri Torneo sono
    finte."""

    bloccata = TestTorneoNonSalvatoDaLasciare.bloccata

    @staticmethod
    def _nella_procedura(principale, monkeypatch, *risposte):
        """Beta, salvata, nella cartella del programma accanto ad Alfa, che
        e' aperta e salvata; poi Nuovo torneo dal menu File. Restituisce i
        percorsi, le finestre di messaggio annotate, i wx.MessageBox e il
        registro delle sonde."""
        import wx

        percorsi = TestAlberoETorneoAttivo()._prepara("Alfa", "Beta")
        principale.load_tournament(percorsi["Alfa"])
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch, risposte)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        assert principale.creation_mode
        registro = TestAlberoETorneoAttivo._sonde(principale)
        return percorsi, finestre, scatole, registro

    @staticmethod
    def _procedura_com_era(principale):
        """La procedura guidata e' ancora sullo schermo, con la voce
        Indietro in cima."""
        assert principale.creation_mode
        assert [testo for testo, _dati in TestAlberoETorneoAttivo._figlie(principale)][:2] == ["Indietro", "Nome torneo *: Non impostato"]

    @staticmethod
    def _procedura_chiusa_sul_torneo(principale, registro, percorso, nome):
        """La procedura si e' chiusa: l'albero ha i tornei, il cursore e'
        sulla voce del torneo nome, nel file percorso, l'albero ha preso il
        fuoco e l'area centrale mostra il turno corrente."""
        assert not principale.creation_mode
        assert principale._e_il_torneo_aperto(percorso)
        assert principale.current_tournament["name"] == nome
        assert "Nuovo torneo" in [testo for testo, _dati in TestAlberoETorneoAttivo._figlie(principale)]
        assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": principale.active_filename}
        assert registro.fuoco[-1:] == ["tree_ctrl"]
        assert principale.main_text.GetValue().startswith(f"Torneo: {nome}\nTurno Corrente: ")

    def test_su_un_altro_torneo(self, principale, suoni, monkeypatch):
        """Alfa aperta e salvata, Nuovo torneo, poi Apri Torneo sul file di
        Beta: Beta si apre, una volta, senza domande e senza suoni, e la
        procedura si chiude sulla voce di Beta. La barra di stato dice che
        Beta e' caricata."""
        percorsi, finestre, scatole, registro = self._nella_procedura(principale, monkeypatch)
        suoni.clear()

        TestAlberoETorneoAttivo()._apri_con_ctrl_o(principale, monkeypatch, percorsi["Beta"])

        self._procedura_chiusa_sul_torneo(principale, registro, percorsi["Beta"], "Beta")
        assert registro.caricati == ["Tornello - Beta.json"]
        assert principale.GetTitle().endswith("[Beta]")
        assert principale.last_status_msg == "Torneo 'Beta' caricato con successo."
        assert finestre == []
        assert scatole == []
        assert suoni == []

    def test_su_un_torneo_di_un_altra_cartella(self, principale, suoni, monkeypatch, tmp_path):
        """Apri Torneo, dentro la procedura, su un torneo di una chiavetta:
        la procedura si chiude sulla sua voce, che dice la cartella fra
        parentesi."""
        _percorsi, finestre, scatole, registro = self._nella_procedura(principale, monkeypatch)
        chiavetta = str(tmp_path / "chiavetta" / "Tornello - Gamma.json")
        TestAlberoETorneoAttivo._scrivi(chiavetta, _torneo_in_corso("Gamma"))
        suoni.clear()

        TestAlberoETorneoAttivo()._apri_con_ctrl_o(principale, monkeypatch, chiavetta)

        self._procedura_chiusa_sul_torneo(principale, registro, chiavetta, "Gamma")
        assert "Gamma (dalla cartella chiavetta)" in [testo for testo, _dati in TestAlberoETorneoAttivo._figlie(principale)]
        assert principale.last_status_msg == "Torneo 'Gamma' caricato con successo, dalla cartella chiavetta."
        assert finestre == []
        assert scatole == []
        assert suoni == []

    def test_su_un_file_che_non_si_apre(self, principale, suoni, monkeypatch, tmp_path):
        """Apri Torneo, dentro la procedura, su un file rovinato: il
        messaggio Apertura non riuscita, con il suono dell'errore, e la
        procedura resta com'era, con Alfa aperta."""
        _percorsi, finestre, scatole, registro = self._nella_procedura(principale, monkeypatch)
        rotto = str(tmp_path / "altrove" / "Tornello - Rotto.json")
        os.makedirs(os.path.dirname(rotto))
        with open(rotto, "w", encoding="utf-8") as f:
            f.write("{rotto")
        suoni.clear()

        TestAlberoETorneoAttivo()._apri_con_ctrl_o(principale, monkeypatch, rotto)

        self._procedura_com_era(principale)
        assert principale.current_tournament["name"] == "Alfa"
        assert [(f.titolo, f.testo) for f in finestre] == [
            _apertura_non_riuscita(rotto, "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)")
        ]
        assert scatole == []
        assert suoni == ["errore"]
        assert registro.fuoco == []
        assert principale.last_status_msg == "Il torneo non si è aperto: resta aperto 'Alfa'."

    def test_annullato(self, principale, suoni, monkeypatch):
        """Apri Torneo, dentro la procedura, con la finestra Apri annullata:
        niente cambia, e la procedura resta com'era."""
        import wx

        _percorsi, finestre, scatole, registro = self._nella_procedura(principale, monkeypatch)

        class FinestraAnnullata:
            def __init__(self, *argomenti, **opzioni):
                pass

            def ShowModal(self):
                return wx.ID_CANCEL

            def GetPath(self):
                return ""

            def Destroy(self):
                pass

        monkeypatch.setattr(wx, "FileDialog", FinestraAnnullata)
        barra = principale.last_status_msg
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_OPEN)

        self._procedura_com_era(principale)
        assert principale.current_tournament["name"] == "Alfa"
        assert registro.caricati == []
        assert registro.fuoco == []
        assert principale.last_status_msg == barra
        assert finestre == []
        assert scatole == []
        assert suoni == []

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    @pytest.mark.parametrize("risposta", ["si", "no"])
    def test_su_un_altro_torneo_con_le_modifiche_soltanto_in_memoria(self, principale, suoni, monkeypatch, capsys, bloccata, risposta):
        """Primavera 2 ha Roma soltanto in memoria: Nuovo torneo, con Si'
        alla domanda Torneo non salvato, e poi Apri Torneo sul file di Estate
        3. La domanda esce di nuovo, come fuori dalla procedura: con Si'
        Estate 3 si apre, e la procedura si chiude sulla sua voce; con No
        Primavera 2 resta aperta, con Roma, e la procedura resta com'era."""
        import wx

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch, [wx.ID_YES, wx.ID_YES if risposta == "si" else wx.ID_NO])
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        assert principale.creation_mode
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        TestAlberoETorneoAttivo()._apri_con_ctrl_o(principale, monkeypatch, bloccata.estate)

        domanda = TestTorneoNonSalvatoDaLasciare._domanda(bloccata.descrizione)
        assert [(f.titolo, f.testo) for f in finestre] == [domanda, domanda]
        assert suoni == ["errore"]
        assert scatole == []
        if risposta == "si":
            self._procedura_chiusa_sul_torneo(principale, registro, bloccata.estate, "Estate 3")
            assert registro.caricati == ["Tornello - Estate_3.json"]
            assert principale.last_status_msg == "Torneo 'Estate 3' caricato con successo."
        else:
            self._procedura_com_era(principale)
            TestTorneoNonSalvatoDaLasciare._primavera_com_era(principale, bloccata)
            assert registro.caricati == []
            assert registro.fuoco == []

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    @pytest.mark.parametrize("cambio", ["sparito", "rovinato"])
    def test_su_un_altro_torneo_che_si_guasta_durante_la_domanda(self, principale, suoni, monkeypatch, capsys, bloccata, cambio):
        """Correzione della 10.19.34. Primavera 2 ha Roma soltanto in
        memoria: Nuovo torneo, con Si' alla domanda Torneo non salvato, e poi
        Apri Torneo sul file di Estate 3, che prima della domanda si legge e
        si apre. La domanda esce di nuovo, e mentre aspetta la risposta il
        file di Estate 3 sparisce, o si rovina: con Si' il file si rilegge, e
        non si apre. Esce il messaggio Apertura non riuscita, con il suono
        dell'errore dopo quello della domanda, Primavera 2 resta aperta, con
        Roma, e la procedura resta com'era, come per ogni Apri Torneo che non
        riesce. Fino alla correzione nessuna prova guardava questo caso: una
        chiusura della procedura anche dopo un Apri Torneo che non riesce
        passava tutte le prove della 10.19.34."""
        import wx

        import gui.main_frame as mf

        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch, [wx.ID_YES, wx.ID_YES])
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        assert principale.creation_mode
        registro = TestAlberoETorneoAttivo._sonde(principale)
        Finto = mf.AccessibleMsgDialog
        estate = bloccata.estate

        class GuastaDuranteLaDomanda(Finto):
            def ShowModal(self):
                if self.domanda:
                    if cambio == "sparito":
                        os.remove(estate)
                    else:
                        with open(estate, "w", encoding="utf-8") as f:
                            f.write("{rotto")
                return super().ShowModal()

        monkeypatch.setattr(mf, "AccessibleMsgDialog", GuastaDuranteLaDomanda)
        suoni.clear()

        TestAlberoETorneoAttivo()._apri_con_ctrl_o(principale, monkeypatch, estate)

        motivo = {
            "sparito": "No such file or directory",
            "rovinato": "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)",
        }[cambio]
        domanda = TestTorneoNonSalvatoDaLasciare._domanda(bloccata.descrizione)
        assert [(f.titolo, f.testo) for f in finestre] == [domanda, domanda, _apertura_non_riuscita(estate, motivo)]
        assert suoni == ["errore", "errore"]
        assert scatole == []
        self._procedura_com_era(principale)
        TestTorneoNonSalvatoDaLasciare._primavera_com_era(principale, bloccata)
        assert registro.caricati == ["Tornello - Estate_3.json"]
        assert registro.fuoco == []
        assert principale.last_status_msg == "Il torneo non si è aperto: resta aperto 'Primavera 2'."


class TestRipristinoNellaProceduraGuidata:
    """10.19.43 (decisione di Gabriele del 7 novembre 2026). Dentro la
    procedura guidata di un torneo nuovo, il ripristino di una copia del
    torneo aperto dalla finestra Copie di sicurezza, aperta dal menu File o
    da Apri Torneo su una copia, chiude la procedura, come Apri Torneo dalla
    10.19.34, e il torneo ripristinato si carica, come fuori dalla
    procedura. Con la copia di un altro torneo la procedura resta com'e'.
    Fino alla 10.19.42, e gia' dalla 10.10.0, la procedura restava, e in
    memoria restava il torneo di prima: dopo Indietro il primo salvataggio
    lo riscriveva sul disco al posto della copia, senza avviso. La finestra
    Copie di sicurezza non si mostra: al posto di aspettare, seleziona la
    copia e preme Ripristina, con Si' alla conferma, poi si chiude. Le
    finestre di messaggio sono finte, e il cestino pure."""

    @staticmethod
    def _copia(nome, luogo):
        """Una copia di sicurezza del torneo nome, al turno 1, con il luogo
        luogo, nella cartella backup."""
        from config import user_data_path

        copia = user_data_path(os.path.join("backup", "2026", "11 Novembre", f"Tornello - {nome}_turno_1_20261107_100000.json"))
        TestNomeDelTorneoNuovo._scrivi(copia, dict(_torneo_in_corso(nome), site=luogo))
        return copia

    @staticmethod
    def _finestra_delle_copie(monkeypatch, copia, tmp_path):
        """La finestra Copie di sicurezza finta descritta sopra. Restituisce
        le sue finestre di messaggio, con titolo e testo, i suoi suoni e il
        cestino."""
        import wx
        from conftest import CestinoFinto

        from gui.dialogs import backup_cleanup_dialog as bcd

        registro = SimpleNamespace(finestre=[], suoni=[], cestino=CestinoFinto(str(tmp_path / "cestino")))

        class Messaggio:
            def __init__(self, genitore, titolo, messaggio, style=wx.OK, **opzioni):
                self.domanda = bool(style & wx.YES_NO)
                registro.finestre.append(titolo)

            def ShowModal(self):
                return wx.ID_YES if self.domanda else wx.ID_OK

            def Destroy(self):
                pass

        def mostra(finestra):
            indice = [os.path.normcase(c.percorso) for c in finestra.visibili].index(os.path.normcase(copia))
            for vecchio in finestra.indici_selezionati():
                finestra.list_ctrl.Select(vecchio, False)
            finestra.list_ctrl.Select(indice, True)
            finestra.on_ripristina(None)
            return wx.ID_CANCEL

        monkeypatch.setattr(bcd, "AccessibleMsgDialog", Messaggio)
        monkeypatch.setattr(bcd, "play_sound", lambda nome, *a, **k: registro.suoni.append(nome))
        monkeypatch.setattr(bcd, "delete_file_to_trash", registro.cestino)
        monkeypatch.setattr(bcd.BackupCleanupDialog, "ShowModal", mostra)
        return registro

    @staticmethod
    def _ripristina(principale, monkeypatch, strada, copia):
        """La finestra Copie di sicurezza dal menu File, o da Apri Torneo
        sulla copia, con Si' alla domanda Copia di sicurezza."""
        if strada == "menu":
            TestAlberoETorneoAttivo._dal_menu(principale, principale.item_backup_cleanup.GetId())
        else:
            TestAlberoETorneoAttivo()._apri_con_ctrl_o(principale, monkeypatch, copia)

    @staticmethod
    def _domande_di_apri_torneo(strada, copia):
        """Le finestre di messaggio della finestra principale: Apri Torneo
        su una copia fa la domanda Copia di sicurezza, con il suono
        dell'errore."""
        if strada == "menu":
            return [], []
        testo = (
            f"Il file {os.path.basename(copia)} è una copia di sicurezza: sta nella cartella backup, e Tornello non lo apre come torneo.\n"
            "Aperto così, verrebbe modificato a ogni salvataggio, e classifica, turni e raccolta delle partite del torneo verrebbero riscritti con lo stato vecchio della copia.\n"
            "Vuoi aprire la finestra delle copie di sicurezza, con questa copia già selezionata? Da lì puoi leggerla, confrontarla con lo stato attuale e ripristinarla."
        )
        return [("Copia di sicurezza", testo)], ["errore"]

    @staticmethod
    def _procedura_chiusa_sul_torneo(principale, registro, percorso, nome):
        """La procedura si e' chiusa: l'albero ha i tornei, il cursore e'
        sulla voce del torneo nome, nel file percorso, e l'albero ha chiesto
        il fuoco. L'area centrale mostra i dati del torneo, perche' alla
        chiusura della finestra Copie di sicurezza l'albero si rilegge, e
        rimette il cursore sulla sua voce, come dopo lo stesso ripristino
        fuori dalla procedura. Il fuoco si chiede perche' la finestra delle
        copie e' finta, e non spegne la finestra principale: con quella vera,
        modale, dalla 10.19.49 l'albero non lo chiede, e lo guarda
        TestNessunFuocoConLeCopieAperte in test_fuoco_alla_chiusura.py."""
        assert not principale.creation_mode
        assert principale._e_il_torneo_aperto(percorso)
        assert principale.current_tournament["name"] == nome
        assert "Nuovo torneo" in [testo for testo, _dati in TestAlberoETorneoAttivo._figlie(principale)]
        assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": principale.active_filename}
        assert registro.fuoco == ["tree_ctrl"]
        assert principale.main_text.GetValue().startswith(f"INFORMAZIONI DETTAGLIATE DEL TORNEO\nNome Torneo: {nome}\n")

    @pytest.mark.parametrize("strada", ["menu", "apri"], ids=["dal menu File", "da Apri Torneo su una copia"])
    def test_la_copia_del_torneo_aperto(self, principale, suoni, monkeypatch, tmp_path, strada):
        """Alfa e' aperta e salvata, con il luogo Roma; Nuovo torneo dal menu
        File, e poi il ripristino della copia di Alfa con il luogo Firenze.
        La procedura si chiude sulla voce di Alfa, con il fuoco all'albero e
        i dati di Alfa nell'area centrale, e Alfa si carica dal suo file,
        con Firenze, una volta; il salvataggio dopo tiene Firenze. Escono
        soltanto la conferma e l'esito del ripristino, e, da Apri Torneo, la
        domanda Copia di sicurezza."""
        import wx

        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        TestNomeDelTorneoNuovo._scrivi(alfa, dict(_torneo_in_corso("Alfa"), site="Roma"))
        principale.load_tournament(alfa)
        copia = self._copia("Alfa", "Firenze")
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        assert principale.creation_mode
        copie = self._finestra_delle_copie(monkeypatch, copia, tmp_path)
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        self._ripristina(principale, monkeypatch, strada, copia)

        self._procedura_chiusa_sul_torneo(principale, registro, alfa, "Alfa")
        assert registro.caricati == ["Tornello - Alfa.json"]
        assert principale.current_tournament["site"] == "Firenze"
        assert TestNomeEDataDiInizioDaDati._nel_file(alfa)["site"] == "Firenze"
        assert principale.GetTitle().endswith("[Alfa]")
        assert principale.last_status_msg == "Torneo 'Alfa' caricato con successo."
        domande, suoni_di_apri = self._domande_di_apri_torneo(strada, copia)
        assert [(f.titolo, f.testo) for f in finestre] == domande
        assert suoni == suoni_di_apri
        assert copie.finestre == ["Conferma ripristino", "Ripristino riuscito"]
        assert copie.suoni == ["ripristino"]
        assert scatole == []
        principale._save_state()
        assert TestNomeEDataDiInizioDaDati._nel_file(alfa)["site"] == "Firenze"

    @pytest.mark.parametrize("strada", ["menu", "apri"], ids=["dal menu File", "da Apri Torneo su una copia"])
    def test_la_copia_di_un_altro_torneo(self, principale, suoni, monkeypatch, tmp_path, strada):
        """Alfa e' aperta, con il luogo Roma; Nuovo torneo, e poi il
        ripristino della copia di Beta, che non e' aperta, con il luogo
        Firenze, nel file di Beta. La procedura resta com'era, con Alfa
        aperta e Roma, senza caricamenti e senza spostare il fuoco, come
        prima della 10.19.43."""
        import wx

        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        beta = user_data_path("Tornello - Beta.json")
        TestNomeDelTorneoNuovo._scrivi(alfa, dict(_torneo_in_corso("Alfa"), site="Roma"))
        TestNomeDelTorneoNuovo._scrivi(beta, dict(_torneo_in_corso("Beta"), site="Napoli"))
        principale.load_tournament(alfa)
        copia = self._copia("Beta", "Firenze")
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        copie = self._finestra_delle_copie(monkeypatch, copia, tmp_path)
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        self._ripristina(principale, monkeypatch, strada, copia)

        TestApriTorneoNellaProceduraGuidata._procedura_com_era(principale)
        assert principale._e_il_torneo_aperto(alfa)
        assert principale.current_tournament["site"] == "Roma"
        assert TestNomeEDataDiInizioDaDati._nel_file(beta)["site"] == "Firenze"
        assert registro.caricati == []
        assert registro.fuoco == []
        domande, suoni_di_apri = self._domande_di_apri_torneo(strada, copia)
        assert [(f.titolo, f.testo) for f in finestre] == domande
        assert suoni == suoni_di_apri
        assert copie.finestre == ["Conferma ripristino", "Ripristino riuscito"]
        assert scatole == []

    def test_senza_torneo_aperto(self, principale, suoni, monkeypatch, tmp_path):
        """Nessun torneo e' aperto: Nuovo torneo, e poi, dal menu File, il
        ripristino della copia di Beta, nel file di Beta. La copia e' di un
        torneo che non e' aperto, e la procedura resta com'era, senza
        caricare Beta e senza spostare il fuoco; fuori dalla procedura Beta
        si caricherebbe."""
        import wx

        from config import user_data_path

        beta = user_data_path("Tornello - Beta.json")
        TestNomeDelTorneoNuovo._scrivi(beta, dict(_torneo_in_corso("Beta"), site="Napoli"))
        principale.populate_tree()
        assert principale.current_tournament is None
        copia = self._copia("Beta", "Firenze")
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        copie = self._finestra_delle_copie(monkeypatch, copia, tmp_path)
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        self._ripristina(principale, monkeypatch, "menu", copia)

        TestApriTorneoNellaProceduraGuidata._procedura_com_era(principale)
        assert principale.current_tournament is None
        assert TestNomeEDataDiInizioDaDati._nel_file(beta)["site"] == "Firenze"
        assert registro.caricati == []
        assert registro.fuoco == []
        assert finestre == []
        assert suoni == []
        assert copie.finestre == ["Conferma ripristino", "Ripristino riuscito"]
        assert scatole == []

    def test_il_torneo_ripristinato_che_non_si_apre(self, principale, suoni, monkeypatch, tmp_path):
        """Alfa e' aperta; Nuovo torneo, e poi, dal menu File, il ripristino
        della copia di Alfa, che subito dopo non si legge, per esempio
        perche' un altro programma ha preso il file. Come fuori dalla
        procedura, il messaggio Apertura non riuscita, con il suono
        dell'errore, e nessun torneo resta aperto; la procedura resta
        com'era, come dopo un Apri Torneo che non riesce."""
        import wx

        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        TestNomeDelTorneoNuovo._scrivi(alfa, dict(_torneo_in_corso("Alfa"), site="Roma"))
        principale.load_tournament(alfa)
        copia = self._copia("Alfa", "Firenze")
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        copie = self._finestra_delle_copie(monkeypatch, copia, tmp_path)
        registro = TestAlberoETorneoAttivo._sonde(principale)

        def illeggibile(percorso):
            raise PermissionError(13, "Permission denied", percorso)

        monkeypatch.setattr(principale, "_leggi_il_torneo", illeggibile)
        suoni.clear()

        self._ripristina(principale, monkeypatch, "menu", copia)

        TestApriTorneoNellaProceduraGuidata._procedura_com_era(principale)
        assert principale.current_tournament is None
        assert registro.caricati == ["Tornello - Alfa.json"]
        assert registro.fuoco == []
        assert [(f.titolo, f.testo) for f in finestre] == [_apertura_non_riuscita(alfa, "Permission denied")]
        assert suoni == ["errore"]
        assert principale.last_status_msg == "Il torneo non si è aperto: nessun torneo aperto."
        assert copie.finestre == ["Conferma ripristino", "Ripristino riuscito"]
        assert scatole == []

    def test_il_torneo_concluso_aperto_si_riapre(self, principale, suoni, monkeypatch, tmp_path):
        """Coppa_Prova e' finalizzata, e aperta dal suo file archiviato;
        Nuovo torneo, e poi, dal menu File, il ripristino della sua copia di
        prima della finalizzazione, che la riapre nella cartella del
        programma e manda nel cestino la cartella d'archivio, con il file
        aperto. La procedura si chiude sulla voce di Coppa_Prova, riaperta e
        caricata dal file nuovo; l'albero non ha piu' i Tornei Conclusi, e il
        salvataggio dopo non rimette il file archiviato. Fino alla 10.19.42
        in memoria restava il torneo concluso, con il file nel cestino:
        l'albero lo mostrava ancora fra i Tornei Conclusi, e il primo
        salvataggio lo riscriveva in archivio."""
        import wx
        from test_finalizzazione import NOME, _cartella_archivio, _copie, _finalizza, prepara_il_banco

        banco = prepara_il_banco(tmp_path, monkeypatch)
        assert _finalizza(banco) is True
        archiviato = os.path.join(_cartella_archivio(), f"Tornello - {NOME}.json")
        principale.load_tournament(archiviato)
        assert principale.current_tournament.get("concluded")
        copia = _copie(banco.backup, "pre_finalize_torneo")[0]
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        assert principale.creation_mode
        copie = self._finestra_delle_copie(monkeypatch, copia, tmp_path)
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        self._ripristina(principale, monkeypatch, "menu", copia)

        assert copie.cestino.ricevuti == [os.path.abspath(_cartella_archivio())]
        self._procedura_chiusa_sul_torneo(principale, registro, banco.file_torneo, NOME)
        assert registro.caricati == [os.path.basename(banco.file_torneo)]
        assert not principale.current_tournament.get("concluded")
        assert not any(testo.startswith("Tornei Conclusi") for testo, _dati in TestAlberoETorneoAttivo._figlie(principale))
        assert finestre == []
        assert suoni == []
        assert copie.finestre == ["Conferma ripristino", "Ripristino riuscito"]
        assert scatole == []
        principale._save_state()
        assert not os.path.exists(archiviato)
        assert not TestNomeEDataDiInizioDaDati._nel_file(banco.file_torneo).get("concluded")

    def test_il_torneo_concluso_aperto_dalla_cartella_esterna_si_riapre(self, principale, suoni, monkeypatch, tmp_path):
        """Coppa_Prova ha una cartella di lavoro esterna, dove la
        finalizzazione lascia una copia del json concluso, ed e' aperta da
        quel file; Nuovo torneo, e poi, dal menu File, il ripristino della
        sua copia di prima della finalizzazione, che la riapre nella
        cartella del programma e manda nel cestino il file aperto, da solo,
        e poi la cartella d'archivio, che non lo contiene. Come con il file
        archiviato, la procedura si chiude sulla voce di Coppa_Prova,
        riaperta e caricata dal file nuovo, e il salvataggio dopo non rimette
        il file concluso nella cartella esterna. Senza il confronto con i
        file tolti uno per uno, la procedura restava aperta, con in memoria
        il torneo concluso del file finito nel cestino."""
        import wx
        from test_finalizzazione import NOME, _cartella_archivio, _copie, _finalizza, _scrivi, prepara_il_banco

        banco = prepara_il_banco(tmp_path, monkeypatch)
        esterna = tmp_path / "esterna"
        esterna.mkdir()
        banco.torneo["custom_save_path"] = str(esterna)
        _scrivi(banco.file_torneo, banco.torneo)
        assert _finalizza(banco) is True
        aperto = str(esterna / f"Tornello - {NOME}.json")
        principale.load_tournament(aperto)
        assert principale._e_il_torneo_aperto(aperto)
        assert principale.current_tournament.get("concluded")
        copia = _copie(banco.backup, "pre_finalize_torneo")[0]
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        assert principale.creation_mode
        copie = self._finestra_delle_copie(monkeypatch, copia, tmp_path)
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        self._ripristina(principale, monkeypatch, "menu", copia)

        assert copie.cestino.ricevuti == [os.path.abspath(aperto), os.path.abspath(_cartella_archivio())]
        self._procedura_chiusa_sul_torneo(principale, registro, banco.file_torneo, NOME)
        assert registro.caricati == [os.path.basename(banco.file_torneo)]
        assert not principale.current_tournament.get("concluded")
        assert not any(testo.startswith("Tornei Conclusi") for testo, _dati in TestAlberoETorneoAttivo._figlie(principale))
        assert finestre == []
        assert suoni == []
        assert copie.finestre == ["Conferma ripristino", "Ripristino riuscito"]
        assert scatole == []
        principale._save_state()
        assert not os.path.exists(aperto)
        assert not TestNomeEDataDiInizioDaDati._nel_file(banco.file_torneo).get("concluded")


class TestCancSuUnaVoceCheNonCePiu:
    """10.19.35 (decisione di Gabriele del 7 novembre 2026). CANC sulla voce
    di un iscritto che nel torneo non c'e' piu', perche' il file del torneo
    e' cambiato dopo che l'albero lo aveva letto: si sente il suono
    dell'errore, l'albero si ridisegna, e il messaggio Giocatore non rimosso
    lo dice, senza la domanda prima. Fino alla 10.19.34 usciva la domanda
    Conferma Rimozione Giocatore, e dopo il Si' non succedeva niente, senza
    suono e senza messaggio. Dalla 10.19.37 lo stesso per l'iscritto di un
    torneo iniziato, con il messaggio Giocatore non ritirato, dove CANC
    usciva in silenzio, e il messaggio Giocatore gia' ritirato ha il suono
    dell'errore. Dalla 10.19.38 lo stesso per una partita, con il messaggio
    Partita non cambiata, dove si sentiva soltanto il suono dell'errore.
    Dalla 10.19.44 lo stesso per un turno, con il messaggio Turno non
    trovato, dove usciva Torneo non aperto. Le finestre di messaggio sono
    finte, e il fuoco si annota."""

    @staticmethod
    def _gamma_cambiata(principale):
        """Alfa, in corso, aperta, e Gamma, in preparazione, nell'albero; poi
        il file di Gamma perde il primo iscritto, Bianchi Luca, come dopo un
        cambio fatto da un altro programma. Restituisce il file di Alfa e
        quello di Gamma come li scrive l'albero, la voce di Bianchi, che
        l'albero mostra ancora, e il contenuto del file di Gamma."""
        alfa, gamma, _nome = TestCancSuUnIscrittoDelTorneoAperto()._alfa_aperta_e_gamma(principale)
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_player_detail", "filepath": gamma})
        assert principale.tree_ctrl.GetItemData(voce)["player"]["id"] == "BIA"
        dati = TestNomeEDataDiInizioDaDati._nel_file(gamma)
        dati["players"] = dati["players"][1:]
        TestNomeDelTorneoNuovo._scrivi(gamma, dati)
        with open(gamma, "rb") as f:
            contenuto = f.read()
        return principale._percorso_come_nell_albero(alfa)[0], gamma, voce, contenuto

    @staticmethod
    def _iscritto_non_rimosso(gamma):
        return (
            "Giocatore non rimosso",
            "Il giocatore Bianchi Luca non si è potuto rimuovere dal torneo Gamma, perché non è più fra i suoi iscritti: "
            f"forse il file {gamma} è cambiato dopo che l'albero lo aveva letto. "
            "Il torneo e i suoi iscritti restano com'erano, e l'albero adesso li mostra aggiornati.",
            False,
        )

    def test_l_iscritto_di_un_torneo_che_non_e_aperto(self, principale, suoni, monkeypatch):
        """Il cursore e' sulla voce di Bianchi, che il file di Gamma non ha
        piu', e Gamma non e' aperta: CANC dal menu. Il messaggio, il suono
        dell'errore e basta; il file di Gamma resta com'era, l'albero mostra
        i suoi tre iscritti, e il cursore, che non resta su un torneo
        chiuso, va sulla voce di Alfa, con il fuoco all'albero. Alfa resta
        aperta, e la barra di stato non cambia."""
        import wx

        alfa, gamma, voce, contenuto = self._gamma_cambiata(principale)
        with principale._albero_senza_caricamenti():
            principale.tree_ctrl.SelectItem(voce)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        registro = TestAlberoETorneoAttivo._sonde(principale)
        barra = principale.last_status_msg
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, principale.item_canc.GetId())

        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [self._iscritto_non_rimosso(gamma)]
        assert scatole == []
        assert suoni == ["errore"]
        with open(gamma, "rb") as f:
            assert f.read() == contenuto
        assert TestCancSuUnIscrittoDelTorneoAperto._iscritti_nell_albero(principale, gamma) == ["VER", "NER", "RUS"]
        assert principale._e_il_torneo_aperto(alfa)
        assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": alfa}
        assert registro.fuoco == ["tree_ctrl"]
        assert registro.caricati == []
        assert principale.last_status_msg == barra

    def test_l_iscritto_del_torneo_aperto_con_le_frecce(self, principale, suoni, monkeypatch):
        """Le frecce sulla voce di Bianchi aprono Gamma dal suo file, che
        non lo ha piu', senza ridisegnare l'albero: CANC dal menu. Il
        messaggio, il suono dell'errore e basta; Gamma resta aperta con i
        suoi tre iscritti, in memoria e nel file, l'albero ne mostra tre, e
        il cursore va sulla voce iscritti di Gamma, con il fuoco
        all'albero."""
        import wx

        _alfa, gamma, voce, contenuto = self._gamma_cambiata(principale)
        principale.tree_ctrl.SelectItem(voce)
        assert principale._e_il_torneo_aperto(gamma)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        registro = TestAlberoETorneoAttivo._sonde(principale)
        barra = principale.last_status_msg
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, principale.item_canc.GetId())

        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [self._iscritto_non_rimosso(gamma)]
        assert scatole == []
        assert suoni == ["errore"]
        with open(gamma, "rb") as f:
            assert f.read() == contenuto
        assert [p["id"] for p in principale.current_tournament["players"]] == ["VER", "NER", "RUS"]
        assert sorted(principale.current_tournament["players_dict"]) == ["NER", "RUS", "VER"]
        assert TestCancSuUnIscrittoDelTorneoAperto._iscritti_nell_albero(principale, gamma) == ["VER", "NER", "RUS"]
        assert principale._e_il_torneo_aperto(gamma)
        assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "show_players", "filepath": gamma}
        assert registro.fuoco == ["tree_ctrl"]
        assert registro.caricati == []
        assert principale.last_status_msg == barra

    def test_l_iscritto_di_un_torneo_con_gli_iscritti_scritti_male(self, principale, suoni, monkeypatch):
        """Correzione della 10.19.35. Alfa e' aperta, e Gamma, in
        preparazione e non aperta, ha le sue voci nell'albero; poi nel file
        di Gamma gli iscritti diventano una lista di numeri. Il cursore e'
        sulla voce di Bianchi: CANC dal menu. Si sente il suono dell'errore,
        ed esce subito, senza la domanda Conferma Rimozione Giocatore, il
        messaggio Giocatore non rimosso dell'errore imprevisto, che nomina il
        giocatore, il torneo e il file, con la descrizione del motivo. Il
        file di Gamma resta com'era, l'albero ha ancora i suoi quattro
        iscritti, e Alfa e la barra di stato restano com'erano. Nella
        10.19.35, prima della correzione, la ricerca dell'iscritto, uscita
        dal try e messa prima della domanda, fermava CANC con un errore che
        si vedeva soltanto in console; fino alla 10.19.34 uscivano la domanda
        e, dopo il Si', lo stesso messaggio."""
        import wx

        alfa, gamma, nome_del_giocatore = TestCancSuUnIscrittoDelTorneoAperto()._alfa_aperta_e_gamma(principale)
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_player_detail", "filepath": gamma})
        dati = TestNomeEDataDiInizioDaDati._nel_file(gamma)
        dati["players"] = [1, 2, 3, 4]
        TestNomeDelTorneoNuovo._scrivi(gamma, dati)
        with open(gamma, "rb") as f:
            contenuto = f.read()
        with principale._albero_senza_caricamenti():
            principale.tree_ctrl.SelectItem(voce)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        registro = TestAlberoETorneoAttivo._sonde(principale)
        barra = principale.last_status_msg
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, principale.item_canc.GetId())

        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (
                "Giocatore non rimosso",
                f"Il giocatore {nome_del_giocatore} non si è potuto rimuovere dal torneo Gamma, nel file {gamma}, per un errore imprevisto: "
                "'int' object has no attribute 'get'. Il file del torneo e i suoi iscritti restano com'erano.",
                False,
            )
        ]
        assert scatole == []
        assert suoni == ["errore"]
        with open(gamma, "rb") as f:
            assert f.read() == contenuto
        assert len(TestCancSuUnIscrittoDelTorneoAperto._iscritti_nell_albero(principale, gamma)) == len(GIOCATORI_DEI_TORNEI)
        assert principale._e_il_torneo_aperto(alfa)
        assert registro.fuoco == []
        assert registro.caricati == []
        assert principale.last_status_msg == barra

    @staticmethod
    def _gamma_iniziata_e_cambiata(principale):
        """Alfa e Gamma, in corso, nell'albero, con Alfa aperta; poi nel file
        di Gamma Russo Marco cambia identificativo, da RUS a ROS, negli
        iscritti e nelle partite, come dopo un cambio fatto da un altro
        programma. Restituisce il file di Gamma come lo scrive l'albero, la
        voce di Russo, che l'albero mostra ancora con RUS, e il contenuto del
        file di Gamma."""
        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        TestNomeDelTorneoNuovo._scrivi(alfa, _torneo_in_corso("Alfa"))
        TestNomeDelTorneoNuovo._scrivi(user_data_path("Tornello - Gamma.json"), _torneo_in_corso("Gamma"))
        principale.load_tournament(alfa)
        gamma = principale._percorso_come_nell_albero(user_data_path("Tornello - Gamma.json"))[0]
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_player_detail", "filepath": gamma, "player": {"id": "RUS"}})
        assert voce and voce.IsOk()
        with open(gamma, encoding="utf-8") as f:
            testo = f.read()
        with open(gamma, "w", encoding="utf-8") as f:
            f.write(testo.replace('"RUS"', '"ROS"'))
        with open(gamma, "rb") as f:
            contenuto = f.read()
        return gamma, voce, contenuto

    def test_l_iscritto_che_non_c_e_piu_in_un_torneo_iniziato(self, principale, suoni, monkeypatch):
        """10.19.37. Le frecce sulla voce di Russo aprono Gamma dal suo file,
        dove Russo ha un altro identificativo, senza ridisegnare l'albero:
        CANC dal menu, che a torneo iniziato propone il ritiro. Il suono
        dell'errore, l'albero ridisegnato, con il cursore sulla voce
        iscritti di Gamma e il fuoco all'albero, e il messaggio Giocatore
        non ritirato; nessun giocatore si ritira, e il file di Gamma resta
        com'era. Fino alla 10.19.36 CANC usciva in silenzio."""
        import wx

        gamma, voce, contenuto = self._gamma_iniziata_e_cambiata(principale)
        principale.tree_ctrl.SelectItem(voce)
        assert principale._e_il_torneo_aperto(gamma)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        registro = TestAlberoETorneoAttivo._sonde(principale)
        barra = principale.last_status_msg
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, principale.item_canc.GetId())

        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (
                "Giocatore non ritirato",
                "Il giocatore Russo Marco non si è potuto ritirare dal torneo Gamma, perché non è più fra i suoi iscritti: "
                f"forse il file {gamma} è cambiato dopo che l'albero lo aveva letto. "
                "Il torneo e i suoi iscritti restano com'erano, e l'albero adesso li mostra aggiornati.",
                False,
            )
        ]
        assert scatole == []
        assert suoni == ["errore"]
        with open(gamma, "rb") as f:
            assert f.read() == contenuto
        assert not any(g.get("withdrawn") for g in principale.current_tournament["players"])
        assert TestCancSuUnIscrittoDelTorneoAperto._iscritti_nell_albero(principale, gamma) == ["BIA", "VER", "NER", "ROS"]
        assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "show_players", "filepath": gamma}
        assert registro.fuoco == ["tree_ctrl"]
        assert registro.caricati == []
        assert principale.last_status_msg == barra

    def test_il_giocatore_gia_ritirato(self, principale, suoni, monkeypatch):
        """10.19.37. Alfa, in corso, aperta, con Russo Marco ritirato: CANC
        sulla sua voce dal menu. Il messaggio Giocatore gia' ritirato, con il
        suono dell'errore, e nient'altro: fino alla 10.19.36 il messaggio
        usciva senza suono."""
        import wx

        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        dati = _torneo_in_corso("Alfa")
        dati["players"][3]["withdrawn"] = True
        TestNomeDelTorneoNuovo._scrivi(alfa, dati)
        principale.load_tournament(alfa)
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_player_detail", "filepath": principale.active_filename, "player": {"id": "RUS"}})
        assert voce and voce.IsOk()
        principale.tree_ctrl.SelectItem(voce)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        registro = TestAlberoETorneoAttivo._sonde(principale)
        barra = principale.last_status_msg
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, principale.item_canc.GetId())

        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            ("Giocatore già ritirato", "Russo Marco risulta già ritirato dal torneo.", False)
        ]
        assert scatole == []
        assert suoni == ["errore"]
        assert registro.fuoco == []
        assert principale.last_status_msg == barra

    @pytest.mark.parametrize("cambio", ["partita", "turno"])
    def test_la_partita_che_non_c_e_piu(self, principale, suoni, monkeypatch, cambio):
        """10.19.38. Alfa e Gamma, in corso, nell'albero, con Alfa aperta;
        poi nel file di Gamma la partita della scacchiera 2 del turno 1
        cambia identificativo, o il turno 1 sparisce e Gamma torna in
        preparazione, come dopo un cambio fatto da un altro programma. Le
        frecce sulla voce della partita aprono Gamma dal suo file, senza
        ridisegnare l'albero, e CANC dal menu: il suono dell'errore, l'albero
        ridisegnato e il messaggio Partita non cambiata; il file di Gamma
        resta com'era. Il cursore va sulla voce del turno, con il fuoco
        all'albero, o, se il turno non c'e' piu', sulla voce di Gamma. Fino
        alla 10.19.37 si sentiva soltanto il suono dell'errore."""
        import wx

        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        TestNomeDelTorneoNuovo._scrivi(alfa, _torneo_in_corso("Alfa"))
        TestNomeDelTorneoNuovo._scrivi(user_data_path("Tornello - Gamma.json"), _torneo_in_corso("Gamma"))
        principale.load_tournament(alfa)
        gamma = principale._percorso_come_nell_albero(user_data_path("Tornello - Gamma.json"))[0]
        voce = principale._find_matching_item(
            principale.tree_root, {"action": "activate_match", "filepath": gamma, "round": 1, "board_num": 2, "match": {"id": 2}}
        )
        assert voce and voce.IsOk()
        dati = TestNomeEDataDiInizioDaDati._nel_file(gamma)
        if cambio == "partita":
            dati["rounds"][0]["matches"][1]["id"] = 7
        else:
            dati["rounds"] = []
        TestNomeDelTorneoNuovo._scrivi(gamma, dati)
        with open(gamma, "rb") as f:
            contenuto = f.read()
        principale.tree_ctrl.SelectItem(voce)
        assert principale._e_il_torneo_aperto(gamma)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        registro = TestAlberoETorneoAttivo._sonde(principale)
        barra = principale.last_status_msg
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, principale.item_canc.GetId())

        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (
                "Partita non cambiata",
                f"La partita della scacchiera 2 del turno 1 non è più nel torneo Gamma: forse il file {gamma} è cambiato dopo che l'albero lo aveva letto. "
                "Il torneo resta com'era, e l'albero adesso mostra le sue partite aggiornate.",
                False,
            )
        ]
        assert scatole == []
        assert suoni == ["errore"]
        with open(gamma, "rb") as f:
            assert f.read() == contenuto
        assert principale._e_il_torneo_aperto(gamma)
        assert registro.caricati == []
        assert principale.last_status_msg == barra
        if cambio == "partita":
            assert principale.current_tournament["rounds"][0]["matches"][1] == dati["rounds"][0]["matches"][1]
            assert principale._find_matching_item(
                principale.tree_root, {"action": "activate_match", "filepath": gamma, "round": 1, "board_num": 2, "match": {"id": 7}}
            )
            assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "show_round_report", "filepath": gamma, "round": 1}
            assert registro.fuoco == ["tree_ctrl"]
        else:
            assert principale.current_tournament["rounds"] == []
            assert principale._find_matching_item(principale.tree_root, {"action": "show_round_report", "filepath": gamma, "round": 1}) is None
            assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": gamma}
            assert registro.fuoco == []

    @staticmethod
    def _gamma_con_due_turni_e_poi_uno(principale):
        """Alfa, aperta, e Gamma, in corso con due turni, nell'albero; poi il
        file di Gamma perde il turno 2, come dopo una Time Machine fatta da
        un'altra macchina. Restituisce il file di Alfa e quello di Gamma
        come li scrive l'albero, la voce del turno 2, che l'albero mostra
        ancora, e il contenuto del file di Gamma."""
        from config import user_data_path

        alfa = user_data_path("Tornello - Alfa.json")
        TestNomeDelTorneoNuovo._scrivi(alfa, _torneo_in_corso("Alfa"))
        dati = _torneo_in_corso("Gamma")
        dati["rounds"].append(
            {
                "round": 2,
                "matches": [
                    {"id": 3, "white_player_id": "VER", "black_player_id": "NER", "result": None},
                    {"id": 4, "white_player_id": "RUS", "black_player_id": "BIA", "result": None},
                ],
            }
        )
        dati["current_round"] = 2
        TestNomeDelTorneoNuovo._scrivi(user_data_path("Tornello - Gamma.json"), dati)
        principale.load_tournament(alfa)
        gamma = principale._percorso_come_nell_albero(user_data_path("Tornello - Gamma.json"))[0]
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_round_report", "filepath": gamma, "round": 2})
        assert voce and voce.IsOk()
        dati["rounds"] = dati["rounds"][:1]
        dati["current_round"] = 1
        TestNomeDelTorneoNuovo._scrivi(gamma, dati)
        with open(gamma, "rb") as f:
            contenuto = f.read()
        return principale._percorso_come_nell_albero(alfa)[0], gamma, voce, contenuto

    def test_il_turno_che_non_c_e_piu(self, principale, suoni, monkeypatch):
        """10.19.44 (decisione di Gabriele del 7 novembre 2026). Le frecce
        sulla voce del turno 2 di Gamma aprono Gamma dal suo file, che il
        turno 2 non lo ha piu', senza ridisegnare l'albero: CANC dal menu.
        Il suono dell'errore, l'albero ridisegnato, senza la voce del turno
        2, con il cursore sulla voce di Gamma e il fuoco all'albero, e il
        messaggio Turno non trovato; Gamma resta aperta con il suo turno 1,
        il file resta com'era, e la barra di stato non cambia. Fino alla
        10.19.43, e gia' dalla 10.19.0, usciva il messaggio Torneo non
        aperto, che diceva di spostarsi sul torneo, l'albero non si
        ridisegnava, e ogni CANC lo ripeteva."""
        import wx

        _alfa, gamma, voce, contenuto = self._gamma_con_due_turni_e_poi_uno(principale)
        principale.tree_ctrl.SelectItem(voce)
        assert principale._e_il_torneo_aperto(gamma)
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        registro = TestAlberoETorneoAttivo._sonde(principale)
        barra = principale.last_status_msg
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, principale.item_canc.GetId())

        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (
                "Turno non trovato",
                f"Il turno 2 non è più nel torneo Gamma: forse il file {gamma} è cambiato dopo che l'albero lo aveva letto. "
                "Il torneo resta com'era, e l'albero adesso mostra i suoi turni aggiornati.",
                False,
            )
        ]
        assert scatole == []
        assert suoni == ["errore"]
        with open(gamma, "rb") as f:
            assert f.read() == contenuto
        assert principale._e_il_torneo_aperto(gamma)
        assert [r["round"] for r in principale.current_tournament["rounds"]] == [1]
        assert principale._find_matching_item(principale.tree_root, {"action": "show_round_report", "filepath": gamma, "round": 2}) is None
        assert principale._find_matching_item(principale.tree_root, {"action": "show_round_report", "filepath": gamma, "round": 1})
        assert TestAlberoETorneoAttivo._dati_della_selezione(principale) == {"action": "select_tournament", "filepath": gamma}
        assert registro.fuoco == ["tree_ctrl"]
        assert registro.caricati == []
        assert principale.last_status_msg == barra

    def test_il_turno_di_un_altro_torneo(self, principale, suoni, monkeypatch):
        """Il turno 2 di Gamma, che non e' aperta, con Alfa aperta: CANC
        sulla sua voce, senza sceglierla, perche' scelta aprirebbe Gamma. Il
        messaggio Torneo non aperto di prima, con il suono dell'errore, e
        l'albero non si ridisegna: il cursore resta dov'era, e il fuoco
        pure."""
        import wx

        alfa, gamma, voce, _contenuto = self._gamma_con_due_turni_e_poi_uno(principale)
        selezione = principale.tree_ctrl.GetSelection()
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        principale._canc_sulla_voce(voce, principale.tree_ctrl.GetItemData(voce))

        assert [(f.titolo, f.testo, f.domanda) for f in finestre] == [
            (
                "Torneo non aperto",
                "Il turno 2 non è del torneo aperto: spostati prima sul suo torneo, nell'albero, poi ripeti l'operazione.",
                False,
            )
        ]
        assert scatole == []
        assert suoni == ["errore"]
        assert principale._e_il_torneo_aperto(alfa)
        assert principale._find_matching_item(principale.tree_root, {"action": "show_round_report", "filepath": gamma, "round": 2})
        assert principale.tree_ctrl.GetSelection() == selezione
        assert registro.fuoco == []
        assert registro.caricati == []


class TestBarraDopoIlNomeNuovo:
    """10.19.39 (decisione di Gabriele del 7 novembre 2026). Il nome del
    torneo aperto cambia dalla voce Nome torneo del ramo Dati, per esempio
    da Prova stessa data a Corona: la barra di stato lo dice, Nome del
    torneo cambiato in 'Corona'., come gia' il titolo della finestra e
    l'albero. Fino alla 10.19.38, e gia' nella 10.0.0, teneva il messaggio
    di prima, per esempio Torneo 'Prova stessa data' caricato con successo.
    Un nome che non cambia, o che non si accetta, lascia la barra com'era.
    Le finestre del campo e dei messaggi sono finte."""

    BARRA = "Nome del torneo cambiato in 'Corona'."

    @staticmethod
    def _prima_riga_della_barra(principale):
        return principale.status_text.GetValue().replace("\r", "\n").split("\n")[0]

    @staticmethod
    def _apri(principale, tmp_path, dove):
        """Prova stessa data, in corso, in preparazione o in corso da
        un'altra cartella, aperta nella finestra; restituisce il suo file e
        il messaggio che l'apertura ha scritto nella barra."""
        nome = "Prova stessa data"
        if dove != "da un'altra cartella":
            percorso = TestNomeEDataDiInizioDaDati._apri(principale, nome, **({"rounds": []} if dove == "in preparazione" else {}))
            return percorso, f"Torneo '{nome}' caricato con successo."
        # tmp_path e' la cartella del programma, nelle prove.
        altrove = tmp_path / "chiavetta"
        altrove.mkdir()
        percorso = str(altrove / "Tornello - Prova_stessa_data.json")
        dati = _torneo_in_corso(nome)
        dati.update(start_date="2026-11-02", end_date="2026-11-20")
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        principale.load_tournament(percorso)
        return principale.active_filename, f"Torneo '{nome}' caricato con successo, dalla cartella chiavetta."

    @pytest.mark.parametrize("dove", ["in corso", "in preparazione", "da un'altra cartella"])
    def test_la_barra_dice_il_nome_nuovo(self, principale, suoni, monkeypatch, tmp_path, dove):
        """Il cursore sta sulla voce Nome torneo, e il nome diventa Corona:
        il nome cambia in memoria e nel file, e la barra di stato dice il
        nome nuovo, con i suoni di sempre, senza messaggi; il cursore resta
        sulla voce Nome torneo, e nessuno sposta il fuoco."""
        import wx

        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        percorso, aperto = self._apri(principale, tmp_path, dove)
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_data", "filepath": percorso, "field_active": "name"})
        with principale._albero_senza_caricamenti():
            principale.tree_ctrl.SelectItem(voce)
        assert principale.last_status_msg == aperto
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        TestNomeEDataDiInizioDaDati._campo(principale, monkeypatch, percorso, "name", "Corona")

        assert principale.current_tournament["name"] == "Corona"
        assert TestNomeEDataDiInizioDaDati._nel_file(percorso)["name"] == "Corona"
        assert principale.GetTitle().endswith(" - [Corona]")
        assert principale.last_status_msg == self.BARRA
        assert self._prima_riga_della_barra(principale) == self.BARRA
        assert suoni == ["apertura", "conferma"]
        assert finestre == []
        assert scatole == []
        assert principale.tree_ctrl.GetSelection() == voce
        assert registro.caricati == []
        assert registro.fuoco == []

    def test_con_le_frecce_e_invio_su_un_altro_torneo(self, principale, suoni, monkeypatch):
        """Alfa e' aperta. Le frecce portano il cursore sulla voce Nome
        torneo di Prova stessa data, che si apre e lo dice nella barra, e
        INVIO cambia il nome in Corona: la barra dice il nome nuovo."""
        import wx

        from config import user_data_path

        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        TestNomeEDataDiInizioDaDati._apri(principale, "Alfa")
        percorso = user_data_path("Tornello - Prova_stessa_data.json")
        dati = _torneo_in_corso("Prova stessa data")
        dati.update(start_date="2026-11-02", end_date="2026-11-20")
        TestNomeDelTorneoNuovo._scrivi(percorso, dati)
        principale.populate_tree()
        voce = principale._find_matching_item(principale.tree_root, {"action": "show_data", "filepath": percorso, "field_active": "name"})
        principale.tree_ctrl.SelectItem(voce)
        _eventi_in_coda()
        assert principale._e_il_torneo_aperto(percorso)
        assert principale.last_status_msg == "Torneo 'Prova stessa data' caricato con successo."
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        class CampoFinto:
            def __init__(self, *a, **k):
                pass

            def ShowModal(self):
                return wx.ID_OK

            def GetValue(self):
                return "Corona"

            def Destroy(self):
                pass

        monkeypatch.setattr(wx, "TextEntryDialog", CampoFinto)
        principale.on_tree_item_activated(SimpleNamespace(GetItem=lambda: voce))
        _eventi_in_coda()

        assert principale.current_tournament["name"] == "Corona"
        assert TestNomeEDataDiInizioDaDati._nel_file(percorso)["name"] == "Corona"
        assert principale.last_status_msg == self.BARRA
        assert self._prima_riga_della_barra(principale) == self.BARRA
        assert suoni == ["apertura", "conferma"]
        assert finestre == []
        assert scatole == []
        assert principale.tree_ctrl.GetSelection() == voce
        assert registro.caricati == []
        assert registro.fuoco == []

    @pytest.mark.parametrize("scritto", ["Prova stessa data", "", "Alfa"], ids=["lo stesso nome", "vuoto", "di un altro torneo"])
    def test_il_nome_che_non_cambia_lascia_la_barra(self, principale, suoni, monkeypatch, scritto):
        """Lo stesso nome non cambia niente, e un nome vuoto, o quello di
        un altro torneo della cartella, non si accetta: il nome resta
        quello di prima, e la barra dice ancora il messaggio dell'apertura,
        come prima della 10.19.39."""
        import wx

        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        finestre = TestNomeDelTorneoNuovo._domande(monkeypatch)
        TestNomeDelTorneoNuovo()._torneo_nella_cartella("Alfa")
        percorso = TestNomeEDataDiInizioDaDati._apri(principale, "Prova stessa data")
        aperto = "Torneo 'Prova stessa data' caricato con successo."
        assert principale.last_status_msg == aperto
        suoni.clear()

        TestNomeEDataDiInizioDaDati._campo(principale, monkeypatch, percorso, "name", scritto)

        assert principale.current_tournament["name"] == "Prova stessa data"
        assert TestNomeEDataDiInizioDaDati._nel_file(percorso)["name"] == "Prova stessa data"
        assert principale.last_status_msg == aperto
        assert self._prima_riga_della_barra(principale) == aperto
        assert scatole == []
        if scritto == "Prova stessa data":
            assert finestre == []
            assert suoni == ["apertura", "conferma"]
        else:
            assert [f.titolo for f in finestre] == ["Nome del torneo mancante" if scritto == "" else "Nome del torneo già in uso"]
            assert suoni == ["apertura", "errore"]
