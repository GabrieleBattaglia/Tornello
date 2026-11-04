"""CANC sulle voci dell'albero della finestra principale. Issue 71.

Dalla 10.14.0 CANC su una partita giocata del turno corrente la riporta fra
quelle da giocare, come [cancella] della console, dopo una domanda con No
predefinito; il riposo, i turni gia' chiusi, i tornei conclusi e le partite
con un giocatore ritirato si rifiutano con un messaggio. CANC smista per
voce scelta: sul torneo e sul giocatore fa quello che faceva, sulle altre
voci suona l'errore senza parlare di tornei da eliminare. Dalla 10.19.0 la
voce del menu File si chiama Elimina o annulla la voce scelta, mostra Canc
come suo tasto e fa quello che fa CANC, dallo stesso gestore; sulle voci
dove CANC non lavora un messaggio di una riga dice dove lavora. CANC sui
turni, la Time Machine, ha le sue prove in test_canc_sui_turni.py.
Dalla 10.15.0 una programmazione si toglie con CANC sulla partita da giocare
programmata e con il pulsante Togli programmazione della finestra di
programmazione (issue 58).
Dalla 10.18.1 l'esempio pratico della Time Machine, nel capitolo 8 del
manuale, che corregge un risultato con CANC dopo Ctrl+Z, si segue passo per
passo anche qui (issue 59).
Le prove sulle funzioni di tournament.py girano senza finestre; le altre
sulla finestra principale vera, mai mostrata, con le domande finte che
annotano titolo, testo e pulsante predefinito, e i suoni annotati.
"""

import copy
import json
import os
import sys
from types import SimpleNamespace

import pytest

PGN_DELLA_PARTITA = '[Event "Prova"]\n[Result "0-1"]\n\n1. e4 e5 2. Nf3 Nc6 0-1'

GIOCATORI = (
    ("BIA", "Bianchi", "Luca"),
    ("VER", "Verdi", "Anna"),
    ("NER", "Neri", "Paolo"),
    ("RUS", "Russo", "Marco"),
    ("FER", "Ferrari", "Elena"),
)


def _voce_di_storico(turno, avversario, colore, risultato, punti):
    return {"round": turno, "opponent_id": avversario, "color": colore, "result": risultato, "score": punti}


def _torneo():
    """Cinque giocatori al turno 2 di 4. Il turno 1 e' chiuso; nel turno 2
    la scacchiera 1, Verdi contro Neri, e' giocata, con un PGN e la
    programmazione che aveva prima del risultato; la scacchiera 2 e' da
    giocare, programmata; alla 3 riposa Bianchi."""
    giocatori = [
        {"id": codice, "last_name": cognome, "first_name": nome, "initial_elo": 1500, "current_elo": 1500, "points": 0.0, "withdrawn": False, "results_history": []}
        for codice, cognome, nome in GIOCATORI
    ]
    per_id = {g["id"]: g for g in giocatori}
    storico = {
        "BIA": [_voce_di_storico(1, "VER", "white", "1-0", 1.0), _voce_di_storico(2, "BYE_PLAYER_ID", None, "BYE", 0.5)],
        "VER": [_voce_di_storico(1, "BIA", "black", "1-0", 0.0), _voce_di_storico(2, "NER", "white", "0-1", 0.0)],
        "NER": [_voce_di_storico(1, "RUS", "white", "1/2-1/2", 0.5), _voce_di_storico(2, "VER", "black", "0-1", 1.0)],
        "RUS": [_voce_di_storico(1, "NER", "black", "1/2-1/2", 0.5)],
        "FER": [_voce_di_storico(1, "BYE_PLAYER_ID", None, "BYE", 0.5)],
    }
    for codice, voci in storico.items():
        per_id[codice]["results_history"] = voci
        per_id[codice]["points"] = sum(v["score"] for v in voci)
    programmazione = {"date": "2026-11-05", "time": "17:30", "channel": "Sala A", "arbiter": "Gabry"}
    turno_1 = [
        {"id": 1, "round": 1, "white_player_id": "BIA", "black_player_id": "VER", "result": "1-0"},
        {"id": 2, "round": 1, "white_player_id": "NER", "black_player_id": "RUS", "result": "1/2-1/2"},
        {"id": 3, "round": 1, "white_player_id": "FER", "black_player_id": None, "result": "BYE"},
    ]
    turno_2 = [
        {
            "id": 4,
            "round": 2,
            "white_player_id": "VER",
            "black_player_id": "NER",
            "result": "0-1",
            "white_score": 0.0,
            "black_score": 1.0,
            "is_scheduled": False,
            "schedule_info": dict(programmazione),
            "pgn": PGN_DELLA_PARTITA,
        },
        {
            "id": 5,
            "round": 2,
            "white_player_id": "RUS",
            "black_player_id": "FER",
            "result": None,
            "is_scheduled": True,
            "schedule_info": {"date": "2026-11-06", "time": "18:00", "channel": "", "arbiter": ""},
        },
        {"id": 6, "round": 2, "white_player_id": "BIA", "black_player_id": None, "result": "BYE"},
    ]
    torneo = {
        "name": "Canc",
        "start_date": "2026-11-01",
        "end_date": "2026-11-30",
        "total_rounds": 4,
        "current_round": 2,
        "bye_value": 0.5,
        "next_match_id": 7,
        "players": giocatori,
        "rounds": [{"round": 1, "matches": turno_1}, {"round": 2, "matches": turno_2}],
    }
    torneo["players_dict"] = per_id
    return torneo


def _partita(torneo, id_partita):
    return next(m for r in torneo["rounds"] for m in r["matches"] if m["id"] == id_partita)


class TestCancellaRisultato:
    """La funzione che riporta la partita fra quelle da giocare."""

    def test_toglie_risultato_punteggi_e_storico_del_turno(self):
        from tournament import cancella_risultato

        torneo = _torneo()
        partita = _partita(torneo, 4)

        cancella_risultato(torneo, 2, partita)

        assert partita["result"] is None
        assert "white_score" not in partita and "black_score" not in partita
        giocatori = torneo["players_dict"]
        assert [v["round"] for v in giocatori["VER"]["results_history"]] == [1]
        assert [v["round"] for v in giocatori["NER"]["results_history"]] == [1]
        assert giocatori["NER"]["points"] == 0.5
        assert giocatori["VER"]["points"] == 0.0
        # Gli altri restano come erano, il riposo compreso.
        assert giocatori["BIA"]["points"] == 1.5
        assert _partita(torneo, 6)["result"] == "BYE"
        assert _partita(torneo, 1)["result"] == "1-0"

    def test_la_programmazione_torna_quella_di_prima(self):
        """Il risultato registrato spegne is_scheduled e tiene la data:
        cancellato il risultato la partita torna programmata, come la conta
        il pie' di pagina."""
        from tournament import cancella_risultato

        torneo = _torneo()
        partita = _partita(torneo, 4)

        cancella_risultato(torneo, 2, partita)

        assert partita["is_scheduled"] is True
        assert partita["schedule_info"]["date"] == "2026-11-05"

    def test_senza_programmazione_resta_da_programmare(self):
        from tournament import cancella_risultato

        torneo = _torneo()
        partita = _partita(torneo, 4)
        del partita["schedule_info"]

        cancella_risultato(torneo, 2, partita)

        assert partita["is_scheduled"] is False

    def test_il_pgn_resta_con_il_risultato_in_sospeso(self):
        import io

        import chess.pgn

        from tournament import cancella_risultato

        torneo = _torneo()
        partita = _partita(torneo, 4)

        cancella_risultato(torneo, 2, partita)

        letta = chess.pgn.read_game(io.StringIO(partita["pgn"]))
        assert letta.headers["Result"] == "*"
        assert [m.uci() for m in letta.mainline_moves()] == ["e2e4", "e7e5", "g1f3", "b8c6"]
        assert partita["pgn"].rstrip().endswith("*")

    def test_un_pgn_che_non_si_legge_resta_com_e(self):
        from tournament import pgn_senza_risultato

        assert pgn_senza_risultato("") == ""


class TestMotivoPerTenereIlRisultato:
    def test_la_partita_giocata_del_turno_corrente_si_cancella(self):
        from tournament import motivo_per_tenere_il_risultato

        torneo = _torneo()
        assert motivo_per_tenere_il_risultato(torneo, 2, _partita(torneo, 4)) is None

    def test_il_turno_corrente_completo_vale_ancora(self):
        """Tutti i risultati e il turno seguente non ancora abbinato: il turno
        e' ancora quello corrente."""
        from tournament import motivo_per_tenere_il_risultato

        torneo = _torneo()
        _partita(torneo, 5)["result"] = "1-0"
        assert motivo_per_tenere_il_risultato(torneo, 2, _partita(torneo, 4)) is None

    def test_il_turno_chiuso(self):
        from tournament import motivo_per_tenere_il_risultato

        torneo = _torneo()
        assert motivo_per_tenere_il_risultato(torneo, 1, _partita(torneo, 1)) == "turno_chiuso"

    @pytest.mark.parametrize("nero", [None, "BYE_PLAYER_ID"])
    def test_il_riposo(self, nero):
        from tournament import motivo_per_tenere_il_risultato

        torneo = _torneo()
        riposo = _partita(torneo, 6)
        riposo["black_player_id"] = nero
        assert motivo_per_tenere_il_risultato(torneo, 2, riposo) == "riposo"

    def test_il_torneo_concluso(self):
        from tournament import motivo_per_tenere_il_risultato

        torneo = _torneo()
        torneo["concluded"] = True
        assert motivo_per_tenere_il_risultato(torneo, 2, _partita(torneo, 4)) == "torneo_concluso"

    @pytest.mark.parametrize("chi", ["VER", "NER"])
    def test_il_giocatore_ritirato(self, chi):
        from tournament import motivo_per_tenere_il_risultato

        torneo = _torneo()
        torneo["players_dict"][chi]["withdrawn"] = True
        assert motivo_per_tenere_il_risultato(torneo, 2, _partita(torneo, 4)) == "ritirato"

    def test_senza_risultato(self):
        from tournament import motivo_per_tenere_il_risultato

        torneo = _torneo()
        assert motivo_per_tenere_il_risultato(torneo, 2, _partita(torneo, 5)) == "senza_risultato"


# La finestra principale vera, mai mostrata.


class _Domande:
    """Al posto di AccessibleMsgDialog: annota titolo, testo e pulsante
    predefinito, e risponde come da copione; senza copione, Si' alle domande
    e OK ai messaggi."""

    def __init__(self, *risposte):
        self.risposte = list(risposte)
        self.aperte = []

    def __call__(self, parent, title, message, style=None, settings=None, no_predefinito=False):
        import wx

        registro = self
        domanda = bool(style and style & wx.YES_NO)

        class Finta:
            def ShowModal(self):
                registro.aperte.append(SimpleNamespace(titolo=title, testo=message, domanda=domanda, no_predefinito=no_predefinito))
                if registro.risposte:
                    return registro.risposte.pop(0)
                return wx.ID_YES if domanda else wx.ID_OK

            def Destroy(self):
                pass

        return Finta()


@pytest.fixture
def suoni(app_grafica, monkeypatch):
    import utils

    suonati = []
    monkeypatch.setattr(utils, "play_sound", lambda nome, *a, **k: suonati.append(nome) or True)
    monkeypatch.setattr(utils, "bip_di_scelta", lambda *a, **k: None)
    return suonati


@pytest.fixture
def principale(app_grafica, suoni, monkeypatch):
    """La finestra principale, mai mostrata, senza i controlli dell'avvio."""
    import gui.main_frame as mf
    from gui.settings import DEFAULT_SETTINGS

    for nome in ("_check_fide_db_on_startup", "_check_backup_on_startup", "_scan_and_load_initial_tournament", "_check_updates_async"):
        monkeypatch.setattr(mf.MainFrame, nome, lambda self: None)
    monkeypatch.setattr(mf.MainFrame, "Maximize", lambda self, *a: None)
    finestra = mf.MainFrame(None, "Tornello", dict(DEFAULT_SETTINGS))
    finestra._timer_pie_di_pagina.Stop()
    for nome in ("main_text", "tree_ctrl", "status_text"):
        getattr(finestra, nome).SetFocus = lambda: None
    yield finestra
    finestra.Destroy()


def _apri(principale, torneo=None):
    """Scrive il torneo nella cartella del programma e lo apre."""
    from config import user_data_path

    percorso = user_data_path("Tornello - Canc.json")
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in (torneo or _torneo()).items() if k != "players_dict"}, f)
    principale.load_tournament(percorso)
    assert principale.current_tournament is not None
    return principale.active_filename


def _dal_file(percorso):
    with open(percorso, encoding="utf-8") as f:
        return json.load(f)


def _voce(principale, **dati):
    voce = principale._find_matching_item(principale.tree_root, dati)
    assert voce and voce.IsOk(), dati
    return voce


def _voce_della_partita(principale, percorso, turno, scacchiera, id_partita):
    return _voce(principale, action="activate_match", filepath=percorso, round=turno, board_num=scacchiera, match={"id": id_partita})


def _comando(principale, voce, identificativo):
    import wx

    principale.tree_ctrl.SelectItem(voce)
    evento = wx.CommandEvent(wx.wxEVT_MENU, identificativo)
    evento.SetEventObject(principale)
    assert principale.GetEventHandler().ProcessEvent(evento)


def _canc(principale, voce):
    """La voce scelta nell'albero, poi CANC, o la voce Elimina o annulla la
    voce scelta del menu File: dalla 10.19.0 il tasto arriva dalla tabella
    degli acceleratori con l'identificativo della voce, ed e' lo stesso
    comando."""
    _comando(principale, voce, principale.item_canc.GetId())


def _domande(monkeypatch, *risposte):
    import gui.main_frame as mf

    domande = _Domande(*risposte)
    monkeypatch.setattr(mf, "AccessibleMsgDialog", domande)
    return domande


class TestCancSullaPartitaGiocata:
    def test_si_riporta_la_partita_fra_quelle_da_giocare(self, principale, suoni, monkeypatch):
        import wx

        percorso = _apri(principale)
        domande = _domande(monkeypatch, wx.ID_YES)
        suoni.clear()

        _canc(principale, _voce_della_partita(principale, percorso, 2, 1, 4))

        assert len(domande.aperte) == 1
        domanda = domande.aperte[0]
        assert domanda.titolo == "Cancellazione del risultato"
        assert domanda.domanda and domanda.no_predefinito is True
        assert "Vuoi cancellare il risultato 0-1 della scacchiera 1 del turno 2, Verdi Anna contro Neri Paolo?" in domanda.testo
        assert "Torna fra le programmate, con la programmazione di prima" in domanda.testo
        assert "Il PGN resta con la partita" in domanda.testo
        assert domanda.testo.endswith("Il pulsante predefinito e' No.")
        partita = _partita(principale.current_tournament, 4)
        assert partita["result"] is None
        salvata = _partita(_dal_file(percorso), 4)
        assert salvata["result"] is None and salvata["is_scheduled"] is True
        neri = next(g for g in _dal_file(percorso)["players"] if g["id"] == "NER")
        assert neri["points"] == 0.5
        assert suoni[-1] == "cancellato"
        assert principale.last_status_msg == "Risultato cancellato: la scacchiera 1 del turno 2 torna fra le partite da giocare."
        # Il cursore resta sulla partita, adesso fra quelle da giocare: dalla
        # 10.16.0 fra le programmate, perche' lo era prima del risultato.
        scelta = principale.tree_ctrl.GetSelection()
        assert principale.tree_ctrl.GetItemData(scelta)["match"]["id"] == 4
        programmate = principale.tree_ctrl.GetItemParent(scelta)
        assert principale.tree_ctrl.GetItemData(programmate)["action"] == "category_programmate"
        da_giocare = principale.tree_ctrl.GetItemParent(programmate)
        assert principale.tree_ctrl.GetItemData(da_giocare)["action"] == "category_da_giocare"
        assert principale.tree_ctrl.GetItemText(principale.tree_ctrl.GetItemParent(da_giocare)).startswith("Turno corrente")
        # La voce del PGN dice che la partita e' da giocare, non None.
        assert "[da giocare]" in principale.tree_ctrl.GetItemText(_voce(principale, action="show_single_pgn", filepath=percorso, round=2, board_num=1, match={"id": 4}))

    def test_con_no_non_cambia_niente(self, principale, suoni, monkeypatch):
        import wx

        percorso = _apri(principale)
        prima = _dal_file(percorso)
        domande = _domande(monkeypatch, wx.ID_NO)
        suoni.clear()

        _canc(principale, _voce_della_partita(principale, percorso, 2, 1, 4))

        assert len(domande.aperte) == 1
        assert _partita(principale.current_tournament, 4)["result"] == "0-1"
        assert _dal_file(percorso) == prima
        assert "cancellato" not in suoni

    def test_nel_turno_corrente_completo(self, principale, suoni, monkeypatch):
        """Con tutti i risultati e il turno seguente non ancora abbinato il
        turno e' ancora quello corrente: sta fra i Completati, e dopo la
        cancellazione torna Turno corrente."""
        import wx

        torneo = _torneo()
        _partita(torneo, 5)["result"] = "1-0"
        percorso = _apri(principale, torneo)
        _voce(principale, action="generate_next_round_action", filepath=percorso)
        domande = _domande(monkeypatch, wx.ID_YES)

        _canc(principale, _voce_della_partita(principale, percorso, 2, 2, 5))

        assert domande.aperte[0].titolo == "Cancellazione del risultato"
        assert _partita(principale.current_tournament, 5)["result"] is None
        assert principale._find_matching_item(principale.tree_root, {"action": "generate_next_round_action", "filepath": percorso}) is None

    def test_dal_tasto_dell_albero_lo_stesso(self, principale, suoni, monkeypatch):
        """Se CANC arriva all'albero invece che al menu, fa lo stesso."""
        import wx

        percorso = _apri(principale)
        _domande(monkeypatch, wx.ID_YES)
        voce = _voce_della_partita(principale, percorso, 2, 1, 4)
        principale.tree_ctrl.SelectItem(voce)
        saltati = []

        principale.on_tree_key_down(SimpleNamespace(GetKeyCode=lambda: wx.WXK_DELETE, Skip=lambda: saltati.append(True)))

        assert _partita(principale.current_tournament, 4)["result"] is None
        assert saltati == []


class TestRisultatiCheRestano:
    """Il suono dell'errore e un messaggio che dice perche'; il torneo resta
    com'era."""

    def _rifiuto(self, principale, suoni, monkeypatch, torneo, turno, scacchiera, id_partita):
        percorso = _apri(principale, torneo)
        prima = _dal_file(percorso)
        domande = _domande(monkeypatch)
        suoni.clear()

        _canc(principale, _voce_della_partita(principale, percorso, turno, scacchiera, id_partita))

        assert suoni == ["errore"]
        assert len(domande.aperte) == 1
        assert not domande.aperte[0].domanda
        assert _dal_file(percorso) == prima
        return domande.aperte[0]

    def test_il_turno_chiuso(self, principale, suoni, monkeypatch):
        messaggio = self._rifiuto(principale, suoni, monkeypatch, _torneo(), 1, 1, 1)

        assert messaggio.titolo == "Turno chiuso"
        assert "dopo quel turno e' gia' stato abbinato il turno 2" in messaggio.testo
        # Dalla 10.19.0 il messaggio dice anche la strada di CANC sul turno.
        assert "CANC sulla voce Turno 1, fra i Completati, toglie in una volta sola tutti i turni che vengono dopo" in messaggio.testo
        assert "Ctrl+Z invece toglie l'ultimo turno abbinato, uno alla volta" in messaggio.testo
        assert _partita(principale.current_tournament, 1)["result"] == "1-0"

    def test_il_riposo(self, principale, suoni, monkeypatch):
        messaggio = self._rifiuto(principale, suoni, monkeypatch, _torneo(), 2, 3, 6)

        assert messaggio.titolo == "Riposo"
        assert "Il riposo di Bianchi Luca nel turno 2 non e' un risultato da cancellare" in messaggio.testo
        assert _partita(principale.current_tournament, 6)["result"] == "BYE"

    def test_il_giocatore_ritirato(self, principale, suoni, monkeypatch):
        """Per esempio dopo un forfait e il ritiro di chi non si e'
        presentato."""
        torneo = _torneo()
        partita = _partita(torneo, 4)
        partita["result"] = "1-F"
        torneo["players_dict"]["NER"]["withdrawn"] = True
        messaggio = self._rifiuto(principale, suoni, monkeypatch, torneo, 2, 1, 4)

        assert messaggio.titolo == "Giocatore ritirato"
        assert "Neri Paolo si e' ritirato dal torneo con questa partita" in messaggio.testo
        assert "aprendo la partita con INVIO" in messaggio.testo
        assert _partita(principale.current_tournament, 4)["result"] == "1-F"

    def test_i_due_giocatori_ritirati(self, principale, suoni, monkeypatch):
        torneo = _torneo()
        _partita(torneo, 4)["result"] = "0-0F"
        torneo["players_dict"]["NER"]["withdrawn"] = True
        torneo["players_dict"]["VER"]["withdrawn"] = True
        messaggio = self._rifiuto(principale, suoni, monkeypatch, torneo, 2, 1, 4)

        assert "Verdi Anna e Neri Paolo si sono ritirati dal torneo con questa partita" in messaggio.testo

    def test_il_torneo_concluso(self, principale, suoni, monkeypatch):
        torneo = _torneo()
        torneo["concluded"] = True
        messaggio = self._rifiuto(principale, suoni, monkeypatch, torneo, 2, 1, 4)

        assert messaggio.titolo == "Torneo concluso"
        assert "Copie di sicurezza" in messaggio.testo
class TestSmistamentoDelCanc:
    """CANC, e la voce Elimina o annulla la voce scelta del menu File, che
    dalla 10.19.0 e' lo stesso comando, smistano per voce scelta."""

    MESSAGGIO_DELLE_ALTRE_VOCI = "CANC lavora sulle voci di tornei, giocatori, turni, partite giocate e partite programmate."

    def test_sulle_altre_voci_l_errore_e_un_messaggio_di_una_riga(self, principale, suoni, monkeypatch):
        """Dalla 10.19.0 un messaggio di una riga dice su quali voci CANC
        lavora; dalla 10.14.0 alla 10.18.1 si sentiva soltanto l'errore, e
        fino alla 10.13.62 un messaggio diceva di scegliere un torneo da
        eliminare. Il torneo resta com'era."""
        percorso = _apri(principale)
        domande = _domande(monkeypatch)
        prima = _dal_file(percorso)
        voci = [
            _voce(principale, action="show_data", filepath=percorso),
            _voce(principale, action="show_data", filepath=percorso, field_active="site"),
            _voce(principale, action="show_players", filepath=percorso),
            _voce(principale, action="add_player_action", filepath=percorso),
            # Il ramo turni e il ramo Completati.
            _voce(principale, action="show_rounds", filepath=percorso),
            _voce(principale, action="category_giocate", filepath=percorso, round=2),
            _voce(principale, action="category_da_giocare", filepath=percorso, round=2),
            _voce(principale, action="category_programmate", filepath=percorso, round=2),
            _voce(principale, action="category_da_programmare", filepath=percorso, round=2),
            _voce(principale, action="show_standings", filepath=percorso),
            _voce(principale, action="show_tiebreaks", filepath=percorso),
            _voce(principale, action="show_pgn_matches_list", filepath=percorso),
            _voce(principale, action="show_single_pgn", filepath=percorso, round=2, board_num=1, match={"id": 4}),
            _voce(principale, action="start_new_tournament"),
        ]
        albero = principale.tree_ctrl
        assert albero.GetItemText(albero.GetItemParent(_voce(principale, action="show_round_report", filepath=percorso, round=1))).startswith("Completati")
        for voce in voci:
            suoni.clear()
            domande.aperte.clear()
            _canc(principale, voce)
            assert suoni == ["errore"], albero.GetItemData(voce)
            assert [(d.titolo, d.testo, d.domanda) for d in domande.aperte] == [("Elimina o annulla", self.MESSAGGIO_DELLE_ALTRE_VOCI, False)], albero.GetItemData(voce)
        assert "\n" not in self.MESSAGGIO_DELLE_ALTRE_VOCI
        assert _dal_file(percorso) == prima

    def test_senza_voce_scelta_lo_stesso_messaggio(self, principale, suoni, monkeypatch):
        domande = _domande(monkeypatch)
        suoni.clear()

        principale._canc_sulla_voce(None, None)

        assert suoni == ["errore"]
        assert [d.testo for d in domande.aperte] == [self.MESSAGGIO_DELLE_ALTRE_VOCI]

    def test_sul_calcolo_del_turno_successivo(self, principale, suoni, monkeypatch):
        torneo = _torneo()
        _partita(torneo, 5)["result"] = "1-0"
        percorso = _apri(principale, torneo)
        domande = _domande(monkeypatch)

        _canc(principale, _voce(principale, action="generate_next_round_action", filepath=percorso))

        assert suoni[-1] == "errore"
        assert [d.testo for d in domande.aperte] == [self.MESSAGGIO_DELLE_ALTRE_VOCI]
        assert len(principale.current_tournament["rounds"]) == 2

    def test_la_partita_da_giocare_non_programmata(self, principale, suoni, monkeypatch):
        """Dalla 10.19.0 il messaggio dice che non c'e' niente da togliere."""
        torneo = _torneo()
        da_giocare = _partita(torneo, 5)
        da_giocare["is_scheduled"] = False
        del da_giocare["schedule_info"]
        percorso = _apri(principale, torneo)
        domande = _domande(monkeypatch)
        prima = _dal_file(percorso)
        suoni.clear()

        _canc(principale, _voce_della_partita(principale, percorso, 2, 2, 5))

        assert suoni == ["errore"]
        assert [(d.titolo, d.testo, d.domanda) for d in domande.aperte] == [
            ("Elimina o annulla", "La partita e' da giocare e non e' programmata: CANC non ha niente da togliere.", False)
        ]
        assert _dal_file(percorso) == prima

    def test_la_partita_di_un_torneo_che_non_e_aperto(self, principale, suoni, monkeypatch):
        _apri(principale)
        domande = _domande(monkeypatch)
        suoni.clear()

        principale._canc_sulla_voce(None, {"action": "activate_match", "filepath": "Tornello - Altro.json", "round": 2, "match": {"id": 4}})

        assert suoni == ["errore"]
        assert [d.titolo for d in domande.aperte] == ["Torneo non aperto"]
        assert "La partita non e' del torneo aperto" in domande.aperte[0].testo

    def test_sul_torneo_lo_elimina_come_prima(self, principale, monkeypatch):
        percorso = _apri(principale)
        eliminati = []
        monkeypatch.setattr(principale, "delete_tournament_completely", lambda voce, filepath: eliminati.append(filepath))

        _canc(principale, _voce(principale, action="select_tournament", filepath=percorso))

        assert eliminati == [percorso]

    def test_sul_giocatore_come_prima(self, principale, monkeypatch):
        percorso = _apri(principale)
        tolti = []
        monkeypatch.setattr(principale, "delete_player_from_tournament", lambda voce, giocatore: tolti.append(giocatore["id"]))
        voce = _voce(principale, action="show_player_detail", filepath=percorso)

        _canc(principale, voce)

        assert tolti == [principale.tree_ctrl.GetItemData(voce)["player"]["id"]]

    def test_dal_menu_sulla_partita_giocata_come_canc(self, principale, suoni, monkeypatch):
        """Dalla revisione della 10.14.0 alla 10.18.1 la voce del menu,
        Elimina Torneo Attivo, su una partita giocata diceva di scegliere
        prima un torneo; dalla 10.19.0 fa quello che fa CANC, dallo stesso
        gestore, on_canc."""
        import wx

        percorso = _apri(principale)
        domande = _domande(monkeypatch, wx.ID_YES)
        voce = _voce_della_partita(principale, percorso, 2, 1, 4)
        principale.tree_ctrl.SelectItem(voce)
        evento = wx.CommandEvent(wx.wxEVT_MENU, principale.item_canc.GetId())
        evento.SetEventObject(principale.item_canc.GetMenu())

        assert principale.GetEventHandler().ProcessEvent(evento)

        assert [d.titolo for d in domande.aperte] == ["Cancellazione del risultato"]
        assert _partita(principale.current_tournament, 4)["result"] is None
        assert not hasattr(principale, "on_delete_active_tournament_menu")
        assert not hasattr(principale, "id_canc")


class TestLaVoceDelMenu:
    """Dalla 10.19.0 la voce del menu File si chiama Elimina o annulla la
    voce scelta, con la L, e mostra Canc, il nome scritto sul tasto, che
    NVDA legge con la voce. Fino alla 10.18.1 si chiamava Elimina Torneo
    Attivo e mostrava Delete."""

    def test_l_etichetta(self, principale):
        assert principale.item_canc.GetItemLabel() == "E&limina o annulla la voce scelta...\tCanc"
        assert principale.item_canc.GetItemLabelText() == "Elimina o annulla la voce scelta..."

    def test_windows_scrive_nel_menu_il_tasto_canc(self, principale):
        """Il testo della voce come lo ha il menu di Windows, che NVDA legge:
        dopo la tabulazione c'e' Canc. Con Delete, o Del, wx l'avrebbe
        riscritto come Delete."""
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32")
        user32.GetMenu.restype = wintypes.HMENU
        user32.GetMenu.argtypes = [wintypes.HWND]
        user32.GetSubMenu.restype = wintypes.HMENU
        user32.GetSubMenu.argtypes = [wintypes.HMENU, ctypes.c_int]
        user32.GetMenuStringW.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.LPWSTR, ctypes.c_int, wintypes.UINT]
        menu_file = principale.item_canc.GetMenu()
        posizione = next(i for i, v in enumerate(menu_file.GetMenuItems()) if v.GetId() == principale.item_canc.GetId())
        maniglia = user32.GetSubMenu(user32.GetMenu(principale.GetHandle()), 0)
        testo = ctypes.create_unicode_buffer(256)
        user32.GetMenuStringW(maniglia, posizione, testo, 256, 0x400)

        assert testo.value == "E&limina o annulla la voce scelta...\tCanc"

    def test_la_voce_non_ha_un_acceleratore_suo(self, principale):
        """wx non riconosce Canc come nome di un tasto: la voce non ha un
        acceleratore suo, e CANC lo da' la tabella della finestra
        principale, con l'identificativo della voce, come prova sul desktop
        nascosto test_il_tasto_canc_nell_albero_arriva_a_on_canc_con_la_voce_del_menu."""
        assert principale.item_canc.GetAccel() is None

    def test_la_finestra_principale_non_ha_campi_modificabili(self, principale):
        """L'acceleratore di CANC vale per tutta la finestra principale: non
        toglie il tasto a nessun campo dove avrebbe un lavoro suo, perche'
        i campi di testo della finestra, l'area centrale e la barra di stato,
        sono in sola lettura. Se ne nascesse uno modificabile, questa prova
        lo direbbe."""
        import wx

        def discendenti(finestra):
            for figlio in finestra.GetChildren():
                if not figlio.IsTopLevel():
                    yield figlio
                    yield from discendenti(figlio)

        testi = [w for w in discendenti(principale) if isinstance(w, wx.TextCtrl)]
        assert {w.GetName() for w in testi} == {"Vista principale", "Barra di stato"}
        assert not any(w.IsEditable() for w in testi)
        assert not [w for w in discendenti(principale) if isinstance(w, (wx.ComboBox, wx.SearchCtrl, wx.SpinCtrl, wx.ListCtrl, wx.ListBox))]

    def test_la_presentazione_dice_il_tasto(self, principale):
        principale.show_intro_message()

        assert " - Canc: nell'albero, elimina o annulla la voce scelta (torneo, giocatore, turno, partita giocata o programmata)" in principale.main_text.GetValue().splitlines()


def _finestra_vera(monkeypatch, arrivati):
    """La finestra principale, che si mostra sul desktop nascosto, con
    on_canc che annota e non fa niente: il gestore si lega alla nascita
    della finestra, e va sostituito prima."""
    import gui.main_frame as mf
    from gui.settings import DEFAULT_SETTINGS

    for nome in ("_check_fide_db_on_startup", "_check_backup_on_startup", "_scan_and_load_initial_tournament", "_check_updates_async"):
        monkeypatch.setattr(mf.MainFrame, nome, lambda self: None)
    monkeypatch.setattr(mf.MainFrame, "Maximize", lambda self, *a: None)
    monkeypatch.setattr(mf.MainFrame, "on_canc", lambda self, evento: arrivati.append(evento.GetId()))
    finestra = mf.MainFrame(None, "Tornello", dict(DEFAULT_SETTINGS))
    finestra._timer_pie_di_pagina.Stop()
    return finestra


def _attiva(finestra):
    import wx
    from test_fuoco_alla_chiusura import _attendi, _user32

    finestra.Show()
    finestra.Raise()
    user32 = _user32()
    for _tentativo in range(10):
        user32.SetForegroundWindow(finestra.GetHandle())
        if _attendi(lambda: wx.GetActiveWindow() is finestra, 0.5):
            return user32
    pytest.fail("la finestra non si e' attivata")


def _premi_canc(user32, controllo):
    """CANC sul controllo, con WM_KEYDOWN e WM_KEYUP mandati con
    PostMessage, mai SendInput: VK_DELETE, con il codice di scansione 0x53
    e il bit del tasto esteso, come lo manda la tastiera. Il ciclo degli
    eventi gira finche' i due messaggi non sono passati."""
    import wx

    ciclo = wx.GUIEventLoop()

    def premi():
        dati = 1 | 0x53 << 16 | 1 << 24
        user32.PostMessageW(controllo.GetHandle(), 0x100, 0x2E, dati)
        user32.PostMessageW(controllo.GetHandle(), 0x101, 0x2E, dati | 0xC0000000)
        wx.CallLater(300, ciclo.Exit)

    wx.CallLater(50, premi)
    rete = wx.CallLater(5000, ciclo.Exit)
    ciclo.Run()
    rete.Stop()


@pytest.mark.finestre_vere
@pytest.mark.skipif(sys.platform != "win32", reason="il desktop nascosto esiste solo in Windows")
def test_il_tasto_canc_nell_albero_arriva_a_on_canc_con_la_voce_del_menu(app_grafica, suoni, monkeypatch):
    """CANC premuto davvero sull'albero, sulla finestra principale mostrata
    sul desktop nascosto: lo prende la tabella degli acceleratori della
    finestra, e arriva a on_canc con l'identificativo della voce Elimina o
    annulla la voce scelta, come la voce scelta dal menu. Dalla revisione
    della 10.14.0 alla 10.18.1 arrivava con un identificativo suo."""
    import wx
    from test_fuoco_alla_chiusura import _attendi

    arrivati = []
    finestra = _finestra_vera(monkeypatch, arrivati)
    try:
        percorso = _apri(finestra)
        voce = _voce(finestra, action="show_data", filepath=percorso)
        user32 = _attiva(finestra)
        finestra.tree_ctrl.SelectItem(voce)
        finestra.tree_ctrl.SetFocus()
        assert _attendi(lambda: wx.Window.FindFocus() is finestra.tree_ctrl)

        _premi_canc(user32, finestra.tree_ctrl)

        assert arrivati == [finestra.item_canc.GetId()]
    finally:
        finestra.Destroy()
        _attendi(lambda: not finestra, 1.0)


@pytest.mark.finestre_vere
@pytest.mark.skipif(sys.platform != "win32", reason="il desktop nascosto esiste solo in Windows")
def test_canc_in_un_campo_di_una_finestra_aperta_dalla_principale_cancella_il_carattere(app_grafica, suoni, monkeypatch):
    """Le finestre che la principale apre, come la finestra del risultato o
    quella di un dato del torneo, hanno i loro campi di testo: li' CANC
    cancella il carattere dopo il cursore, e non arriva a on_canc, perche'
    wx non guarda gli acceleratori della finestra che le ha aperte. La
    prova lo misura con un dialogo che non blocca, figlio della
    principale, mostrato sul desktop nascosto."""
    import wx
    from test_fuoco_alla_chiusura import _attendi

    arrivati = []
    finestra = _finestra_vera(monkeypatch, arrivati)
    dialogo = None
    try:
        dialogo = wx.Dialog(finestra, title="Prova")
        campo = wx.TextCtrl(dialogo, value="Coppa")
        campo.SetName("Nome")
        dialogo.Show()
        user32 = _attiva(dialogo)
        campo.SetFocus()
        campo.SetInsertionPoint(0)
        assert _attendi(lambda: wx.Window.FindFocus() is campo)

        _premi_canc(user32, campo)

        assert campo.GetValue() == "oppa"
        assert arrivati == []
    finally:
        if dialogo:
            dialogo.Destroy()
        finestra.Destroy()
        _attendi(lambda: not finestra, 1.0)


class TestTogliProgrammazione:
    """Dalla 10.15.0 una programmazione si toglie dal pulsante Togli
    programmazione della finestra di programmazione e con CANC sulla partita
    programmata nell'albero, sempre dopo una domanda con No predefinito
    (issue 58). Fino alla 10.14.0 la toglieva soltanto la console."""

    def test_la_funzione_toglie_segno_e_dati(self):
        from tournament import togli_programmazione

        partita = _partita(_torneo(), 5)

        assert togli_programmazione(partita) is True
        assert partita["is_scheduled"] is False
        assert "schedule_info" not in partita
        assert togli_programmazione(partita) is False

    def test_il_pie_di_pagina_non_la_conta_piu(self):
        """Il pie' di pagina guarda la data: per questo schedule_info sparisce."""
        from datetime import datetime

        from stats import indicatori_pie_di_pagina
        from tournament import togli_programmazione

        torneo = _torneo()
        adesso = datetime(2026, 11, 3, 12)
        assert indicatori_pie_di_pagina(torneo, adesso, None, None)["pr"] == "100.0%"
        togli_programmazione(_partita(torneo, 5))
        assert indicatori_pie_di_pagina(torneo, adesso, None, None)["pr"] == "0.0%"

    def test_la_domanda(self):
        from gui.dialogs.result_dialog import domanda_togli_programmazione
        from utils import format_date_locale

        testo = domanda_togli_programmazione(2, "Russo Marco", "Ferrari Elena", {"date": "2026-11-06", "time": "18:00"})

        assert testo.startswith(f"Vuoi togliere la programmazione della scacchiera 2, Russo Marco contro Ferrari Elena, per {format_date_locale('2026-11-06')} alle 18:00?")
        assert testo.endswith("Il pulsante predefinito e' No.")

    @staticmethod
    def _programmazione(cornice, programmata):
        from gui.dialogs.result_dialog import ScheduleDialog

        dlg = ScheduleDialog(cornice, {"date": "2026-11-06", "time": "18:00"} if programmata else {}, cornice.settings, {}, programmata=programmata, scacchiera=2, bianco="Russo Marco", nero="Ferrari Elena")
        chiusure = []
        dlg.EndModal = chiusure.append
        return dlg, chiusure

    @pytest.fixture
    def cornice(self, app_grafica):
        import wx

        from gui.settings import DEFAULT_SETTINGS

        finestra = wx.Frame(None)
        finestra.settings = dict(DEFAULT_SETTINGS)
        yield finestra
        finestra.DestroyChildren()
        finestra.Destroy()

    @pytest.mark.parametrize("programmata", [True, False])
    def test_il_pulsante_e_acceso_solo_per_la_partita_programmata(self, cornice, suoni, programmata):
        import wx

        dlg, _chiusure = self._programmazione(cornice, programmata)
        try:
            assert dlg.btn_togli.GetLabel() == "Togli programmazione"
            assert dlg.btn_togli.IsEnabled() is programmata
            # Mai predefinito, e INVIO o ESC non lo premono.
            assert dlg.btn_togli.GetId() not in (dlg.GetAffirmativeId(), dlg.GetEscapeId(), wx.ID_OK, wx.ID_CANCEL)
        finally:
            dlg.Destroy()

    def test_nel_tab_viene_dopo_i_dettagli_e_prima_di_annulla(self, cornice, suoni):
        import wx

        dlg, _chiusure = self._programmazione(cornice, True)
        try:
            figli = list(dlg.pannello.GetChildren())
            dettagli = next(f for f in figli if isinstance(f, wx.StaticBox) and f.GetLabel() == "Dettagli Sede e Arbitro")
            annulla = next(f for f in figli if isinstance(f, wx.Button) and f.GetId() == wx.ID_CANCEL)
            assert figli.index(dettagli) < figli.index(dlg.btn_togli) < figli.index(annulla)
        finally:
            dlg.Destroy()

    @pytest.mark.parametrize(("risposta", "chiusa"), [("si", True), ("no", False)])
    def test_il_pulsante_chiede_prima(self, cornice, suoni, monkeypatch, risposta, chiusa):
        import wx

        from gui.dialogs import accessible_msg_dialog

        domande = _Domande(wx.ID_YES if risposta == "si" else wx.ID_NO)
        monkeypatch.setattr(accessible_msg_dialog, "AccessibleMsgDialog", domande)
        dlg, chiusure = self._programmazione(cornice, True)
        try:
            suoni.clear()
            dlg.on_togli(None)
        finally:
            dlg.Destroy()

        assert len(domande.aperte) == 1
        assert domande.aperte[0].titolo == "Togli programmazione"
        assert domande.aperte[0].no_predefinito is True
        assert "scacchiera 2, Russo Marco contro Ferrari Elena" in domande.aperte[0].testo
        assert chiusure == ([wx.ID_DELETE] if chiusa else [])
        assert suoni == []

    def test_la_finestra_del_risultato_passa_la_scelta(self, cornice, suoni, monkeypatch):
        """La programmazione chiusa con wx.ID_DELETE chiude anche la finestra
        del risultato, che la dice a chi l'ha aperta, senza suoni suoi."""
        import wx

        from gui.dialogs import result_dialog

        aperte = []

        class Programmazione:
            def __init__(self, *argomenti, **opzioni):
                aperte.append(opzioni)

            def ShowModal(self):
                return wx.ID_DELETE

            def Destroy(self):
                pass

        monkeypatch.setattr(result_dialog, "ScheduleDialog", Programmazione)
        dlg = result_dialog.ResultDialog(cornice, "Russo Marco", "Ferrari Elena", "RUS", "FER", 2, None, {"date": "2026-11-06", "time": "18:00"}, cornice.settings, programmata=True)
        chiusure = []
        dlg.EndModal = chiusure.append
        try:
            suoni.clear()
            dlg.on_schedule(None)
        finally:
            dlg.Destroy()

        assert aperte[0]["programmata"] is True
        assert (aperte[0]["scacchiera"], aperte[0]["bianco"], aperte[0]["nero"]) == (2, "Russo Marco", "Ferrari Elena")
        assert dlg.selected_action == "unschedule"
        assert chiusure == [wx.ID_OK]
        assert suoni == []

    def test_dalla_finestra_del_risultato(self, principale, suoni, monkeypatch):
        import wx

        from gui.dialogs import result_dialog

        percorso = _apri(principale)
        aperte = []

        class Risultato:
            def __init__(self, *argomenti, **opzioni):
                aperte.append(opzioni)
                self.selected_action = "unschedule"

            def ShowModal(self):
                return wx.ID_OK

            def Destroy(self):
                pass

        monkeypatch.setattr(result_dialog, "ResultDialog", Risultato)
        principale.tree_ctrl.SelectItem(_voce_della_partita(principale, percorso, 2, 2, 5))
        suoni.clear()

        principale.on_activate_match(_partita(principale.current_tournament, 5))

        assert aperte[0]["programmata"] is True
        salvata = _partita(_dal_file(percorso), 5)
        assert salvata["is_scheduled"] is False and "schedule_info" not in salvata
        assert suoni == ["pianifica_rimuovi"]
        assert principale.last_status_msg == "Programmazione tolta: la scacchiera 2 del turno 2 resta da giocare, senza giorno e ora."
        scelta = principale.tree_ctrl.GetSelection()
        assert principale.tree_ctrl.GetItemData(scelta)["match"]["id"] == 5
        assert principale.tree_ctrl.GetItemText(scelta).endswith("(Non pianificata)")
        # Dalla 10.16.0 la partita passa nel ramo da programmare.
        ramo = principale.tree_ctrl.GetItemParent(scelta)
        assert principale.tree_ctrl.GetItemData(ramo)["action"] == "category_da_programmare"
        assert principale.tree_ctrl.GetItemText(ramo) == "da programmare (1)"

    def test_la_partita_non_programmata_apre_il_pulsante_spento(self, principale, suoni, monkeypatch):
        import wx

        from gui.dialogs import result_dialog

        torneo = _torneo()
        da_giocare = _partita(torneo, 5)
        da_giocare["is_scheduled"] = False
        del da_giocare["schedule_info"]
        _apri(principale, torneo)
        aperte = []

        class Risultato:
            def __init__(self, *argomenti, **opzioni):
                aperte.append(opzioni)
                self.selected_action = None

            def ShowModal(self):
                return wx.ID_CANCEL

            def Destroy(self):
                pass

        monkeypatch.setattr(result_dialog, "ResultDialog", Risultato)
        principale.on_activate_match(_partita(principale.current_tournament, 5))

        assert aperte[0]["programmata"] is False

    @pytest.mark.parametrize(("risposta", "tolta"), [("si", True), ("no", False)])
    def test_con_canc_nell_albero(self, principale, suoni, monkeypatch, risposta, tolta):
        import wx

        percorso = _apri(principale)
        prima = _dal_file(percorso)
        domande = _domande(monkeypatch, wx.ID_YES if risposta == "si" else wx.ID_NO)
        suoni.clear()

        _canc(principale, _voce_della_partita(principale, percorso, 2, 2, 5))

        assert len(domande.aperte) == 1
        domanda = domande.aperte[0]
        assert domanda.titolo == "Togli programmazione"
        assert domanda.domanda and domanda.no_predefinito is True
        assert "scacchiera 2, Russo Marco contro Ferrari Elena" in domanda.testo
        partita = _partita(principale.current_tournament, 5)
        if tolta:
            assert partita["is_scheduled"] is False and "schedule_info" not in partita
            assert "schedule_info" not in _partita(_dal_file(percorso), 5)
            assert suoni == ["pianifica_rimuovi"]
            scelta = principale.tree_ctrl.GetSelection()
            assert principale.tree_ctrl.GetItemData(scelta)["match"]["id"] == 5
        else:
            assert partita["is_scheduled"] is True
            assert _dal_file(percorso) == prima
            assert suoni == []


class TestRamiDelleDaGiocareNellAlberoVero:
    """Dalla 10.16.0 le partite da giocare stanno nei rami programmate e da
    programmare: il cursore segue la partita che cambia ramo, e i rami
    aperti restano aperti quando l'albero si ridisegna."""

    def test_la_partita_programmata_passa_fra_le_programmate_con_il_cursore(self, principale, suoni, monkeypatch):
        import wx

        from gui.dialogs import result_dialog

        torneo = _torneo()
        da_giocare = _partita(torneo, 5)
        da_giocare["is_scheduled"] = False
        del da_giocare["schedule_info"]
        percorso = _apri(principale, torneo)
        voce = _voce_della_partita(principale, percorso, 2, 2, 5)
        assert principale.tree_ctrl.GetItemData(principale.tree_ctrl.GetItemParent(voce))["action"] == "category_da_programmare"
        programmazione = {"date": "2026-11-06", "time": "18:00", "channel": "", "arbiter": "", "arbiter_not_needed": False}

        class Risultato:
            def __init__(self, *argomenti, **opzioni):
                self.selected_action = "schedule"
                self.schedule_info = programmazione

            def ShowModal(self):
                return wx.ID_OK

            def Destroy(self):
                pass

        monkeypatch.setattr(result_dialog, "ResultDialog", Risultato)
        principale.tree_ctrl.SelectItem(voce)

        principale.on_activate_match(_partita(principale.current_tournament, 5))

        scelta = principale.tree_ctrl.GetSelection()
        assert principale.tree_ctrl.GetItemData(scelta)["match"]["id"] == 5
        ramo = principale.tree_ctrl.GetItemParent(scelta)
        assert principale.tree_ctrl.GetItemData(ramo)["action"] == "category_programmate"
        assert principale.tree_ctrl.GetItemText(ramo) == "programmate (1)"
        vuoto = _voce(principale, action="category_da_programmare", filepath=percorso, round=2)
        assert principale.tree_ctrl.GetItemText(vuoto) == "da programmare (0)"

    def test_i_rami_aperti_restano_aperti(self, principale):
        percorso = _apri(principale)
        for azione in ("category_da_giocare", "category_programmate"):
            principale.tree_ctrl.Expand(_voce(principale, action=azione, filepath=percorso, round=2))

        principale.populate_tree()

        assert principale.tree_ctrl.IsExpanded(_voce(principale, action="category_programmate", filepath=percorso, round=2))
        assert not principale.tree_ctrl.IsExpanded(_voce(principale, action="category_da_programmare", filepath=percorso, round=2))


def _torneo_della_time_machine(turni=3):
    """Il torneo dell'esempio pratico del capitolo 8 del manuale, di cinque
    turni: il turno 3 appena abbinato, senza risultati, e al turno 2 la
    scacchiera 1, Bianchi contro Russo, vinta dal bianco, che era invece
    patta. Con turni=1 resta il solo turno 1, senza risultati."""
    giocatori = [
        {"id": codice, "last_name": cognome, "first_name": nome, "initial_elo": 1500, "current_elo": 1500, "points": 0.0, "withdrawn": False, "results_history": []}
        for codice, cognome, nome in GIOCATORI[:4]
    ]
    per_id = {g["id"]: g for g in giocatori}
    partite = [
        (1, "BIA", "VER", "1-0", 1.0, 0.0),
        (1, "NER", "RUS", "1/2-1/2", 0.5, 0.5),
        (2, "BIA", "RUS", "1-0", 1.0, 0.0),
        (2, "NER", "VER", "1-0", 1.0, 0.0),
        (3, "BIA", "NER", None, None, None),
        (3, "RUS", "VER", None, None, None),
    ]
    if turni == 1:
        partite = [(1, bianco, nero, None, None, None) for _t, bianco, nero, *_resto in partite[:2]]
    turni_del_torneo = {}
    for id_partita, (turno, bianco, nero, risultato, punti_bianco, punti_nero) in enumerate(partite, 1):
        turni_del_torneo.setdefault(turno, []).append(
            {"id": id_partita, "round": turno, "white_player_id": bianco, "black_player_id": nero, "result": risultato}
        )
        if risultato is not None:
            per_id[bianco]["results_history"].append(_voce_di_storico(turno, nero, "white", risultato, punti_bianco))
            per_id[nero]["results_history"].append(_voce_di_storico(turno, bianco, "black", risultato, punti_nero))
    for giocatore in giocatori:
        giocatore["points"] = sum(v["score"] for v in giocatore["results_history"])
    torneo = {
        "name": "Canc",
        "start_date": "2026-11-01",
        "end_date": "2026-11-30",
        "total_rounds": 5,
        "current_round": turni,
        "bye_value": 0.5,
        "next_match_id": len(partite) + 1,
        "players": giocatori,
        "rounds": [{"round": numero, "matches": incontri} for numero, incontri in sorted(turni_del_torneo.items())],
    }
    torneo["players_dict"] = per_id
    return torneo


class TestEsempioDellaTimeMachine:
    """L'esempio pratico del capitolo 8 del manuale, seguito passo per passo
    sulla finestra principale vera, mai mostrata, dalla 10.18.1 (issue 59):
    dopo Ctrl+Z il turno 2 torna il turno corrente, sta fra i Completati con
    tutti i risultati, e la sua finestra del risultato non li cambia; CANC
    sulla partita sbagliata, con Si' scelto al posto del No predefinito, la
    riporta fra quelle da giocare, nel Turno corrente; INVIO sulla partita
    apre la finestra che adesso accetta il risultato, e la patta riporta il
    cursore sul calcolo del turno successivo. Fino alla 10.13.62 l'esempio
    diceva di cambiare il risultato dalla finestra, che non lo permette."""

    def _finestra_del_risultato(self, monkeypatch, risultato=None):
        """Al posto della finestra del risultato: annota come l'apre la
        finestra principale; con risultato, lo sceglie e conferma, senza
        annulla."""
        import wx

        from gui.dialogs import result_dialog

        aperte = []

        class Risultato:
            def __init__(self, *a, **k):
                aperte.append(k)
                self.selected_action = None
                self.txt_pgn = SimpleNamespace(GetValue=lambda: "")

            def ShowModal(self):
                return wx.ID_OK if risultato else wx.ID_CANCEL

            def get_selected_result(self):
                return risultato

            def Destroy(self):
                pass

        monkeypatch.setattr(result_dialog, "ResultDialog", Risultato)
        return aperte

    def test_si_segue_passo_per_passo(self, principale, suoni, monkeypatch):
        import wx

        percorso = _apri(principale, _torneo_della_time_machine())
        monkeypatch.setattr(principale, "_nel_cestino", lambda percorso: True)
        domande = _domande(monkeypatch, wx.ID_YES, wx.ID_YES)
        albero = principale.tree_ctrl
        suoni.clear()

        # Passi 1 e 2: Ctrl+Z, e la domanda che nomina il torneo, con Si'
        # come pulsante predefinito.
        principale.on_rollback_round(None)

        domanda = domande.aperte[0]
        assert domanda.titolo == "Annulla Turno"
        assert domanda.testo == "Sei sicuro di voler annullare l'ultimo turno del torneo Canc e tornare indietro? Questa azione è irreversibile."
        assert domanda.domanda and domanda.no_predefinito is False
        # Passo 3: il suono, la barra di stato, il turno 2 corrente e fra i
        # Completati, il calcolo del turno successivo, la finestra del
        # risultato che non lo cambia.
        assert "time_machine" in suoni
        assert principale.last_status_msg == "Time Machine attivata: tornati al turno precedente."
        assert principale.current_tournament["current_round"] == 2
        assert [r["round"] for r in principale.current_tournament["rounds"]] == [1, 2]
        turno_2 = _voce(principale, action="show_round_report", filepath=percorso, round=2)
        assert albero.GetItemText(turno_2) == "Turno 2"
        assert albero.GetItemText(albero.GetItemParent(turno_2)) == "Completati (2)"
        _voce(principale, action="generate_next_round_action", filepath=percorso)
        aperte = self._finestra_del_risultato(monkeypatch)
        principale.on_activate_match(_partita(principale.current_tournament, 3))
        assert aperte[-1]["disable_result_change"] is True
        # Il file dei dettagli del turno 2, come l'aveva scritto la sua
        # conclusione: la sezione 8.1 dice che resta, e che Tornello lo
        # riscrive quando il turno torna completo, come la 6.2. Fino alla
        # revisione della 10.13.60 la 8.1 diceva quando un risultato cambia.
        from reports import append_completed_round_to_history_file, file_dei_dettagli_del_turno

        append_completed_round_to_history_file(principale.current_tournament, 2)
        dettagli = file_dei_dettagli_del_turno(principale.current_tournament, 2)
        with open(dettagli, encoding="utf-8-sig") as f:
            dettagli_di_prima = f.read()
        assert "1-0" in dettagli_di_prima and "1/2-1/2" not in dettagli_di_prima

        # Passi 4 e 5: CANC sulla partita, nel ramo giocate del Turno 2, e Si'
        # al posto del No predefinito.
        voce = _voce_della_partita(principale, percorso, 2, 1, 3)
        assert albero.GetItemText(voce) == "Scacchiera 1: Bianchi Luca vs Russo Marco [1-0]"
        assert albero.GetItemData(albero.GetItemParent(voce))["action"] == "category_giocate"
        _canc(principale, voce)

        domanda = domande.aperte[1]
        assert domanda.titolo == "Cancellazione del risultato"
        assert domanda.no_predefinito is True
        # Passo 6: il suono, la barra di stato, il Turno corrente subito
        # sotto turni, la partita fra quelle da programmare, con il cursore.
        assert suoni[-1] == "cancellato"
        assert principale.last_status_msg == "Risultato cancellato: la scacchiera 1 del turno 2 torna fra le partite da giocare."
        scelta = albero.GetSelection()
        assert albero.GetItemData(scelta)["match"]["id"] == 3
        da_programmare = albero.GetItemParent(scelta)
        assert albero.GetItemData(da_programmare)["action"] == "category_da_programmare"
        da_giocare = albero.GetItemParent(da_programmare)
        assert albero.GetItemData(da_giocare)["action"] == "category_da_giocare"
        turno_corrente = albero.GetItemParent(da_giocare)
        assert albero.GetItemText(turno_corrente) == "Turno corrente (2/5)"
        assert albero.GetItemText(albero.GetItemParent(turno_corrente)) == "turni (2)"
        # Il risultato e' cambiato, ma il turno non e' completo: il file dei
        # dettagli resta com'era.
        with open(dettagli, encoding="utf-8-sig") as f:
            assert f.read() == dettagli_di_prima

        # Passo 7: INVIO sulla partita, dall'albero, e la patta.
        aperte = self._finestra_del_risultato(monkeypatch, "1/2-1/2")
        principale.on_tree_item_activated(SimpleNamespace(GetItem=lambda: scelta))

        assert aperte[-1]["disable_result_change"] is False
        assert _partita(principale.current_tournament, 3)["result"] == "1/2-1/2"
        punti = {g["id"]: g["points"] for g in _dal_file(percorso)["players"]}
        assert punti["BIA"] == 1.5 and punti["RUS"] == 1.0
        # Passo 8: il suono della fine del turno, il turno fra i Completati,
        # il cursore sul calcolo del turno successivo.
        assert "conclusione_turno" in suoni
        with open(dettagli, encoding="utf-8-sig") as f:
            assert "1/2-1/2" in f.read()
        assert albero.GetItemText(albero.GetItemParent(_voce(principale, action="show_round_report", filepath=percorso, round=2))) == "Completati (2)"
        assert albero.GetItemData(albero.GetSelection())["action"] == "generate_next_round_action"
        assert albero.GetItemText(albero.GetSelection()) == "calcola il turno successivo"

    def test_tolto_il_turno_1_il_torneo_torna_in_preparazione(self, principale, suoni, monkeypatch):
        """La sezione 8.1: togliendo anche il turno 1 il torneo torna fra
        quelli In Preparazione, e l'iscrizione si apre di nuovo."""
        import wx

        import gui.dialogs

        percorso = _apri(principale, _torneo_della_time_machine(turni=1))
        monkeypatch.setattr(principale, "_nel_cestino", lambda percorso: True)
        _domande(monkeypatch, wx.ID_YES)

        principale.on_rollback_round(None)

        assert principale.current_tournament["rounds"] == []
        torneo = _voce(principale, action="select_tournament", filepath=percorso)
        assert principale.tree_ctrl.GetItemData(principale.tree_ctrl.GetItemParent(torneo))["action"] == "category_prep"
        # Sotto turni la voce calcola il turno 1, e in fondo all'albero la
        # voce Avvio torneo, con la stessa azione.
        assert principale.tree_ctrl.GetItemText(_voce(principale, action="start_tournament_matchmaking_action", filepath=percorso)) == "calcola il turno 1"
        ultima = principale.tree_ctrl.GetLastChild(principale.tree_root)
        assert principale.tree_ctrl.GetItemData(ultima)["action"] == "start_tournament_matchmaking_action"
        assert principale.tree_ctrl.GetItemText(ultima) == "Avvio torneo: Canc"
        iscrizioni = []

        class Iscrizione:
            def __init__(self, *a, **k):
                iscrizioni.append(a)

            def ShowModal(self):
                return wx.ID_CANCEL

            def Destroy(self):
                pass

        monkeypatch.setattr(gui.dialogs, "PlayerEnrollmentDialog", Iscrizione)
        monkeypatch.setattr(principale, "_database_dei_giocatori", lambda: {"players": []})

        principale.on_enroll_players(None)

        assert len(iscrizioni) == 1


def test_il_torneo_di_prova_e_coerente():
    """I punti del torneo di prova sono quelli del suo storico: le prove qui
    sopra ne misurano i cambiamenti."""
    from tournament import ricalcola_punti_tutti_giocatori

    torneo = _torneo()
    copia = copy.deepcopy(torneo)
    ricalcola_punti_tutti_giocatori(copia)
    assert {g["id"]: g["points"] for g in copia["players"]} == {g["id"]: g["points"] for g in torneo["players"]}
    assert os.path.basename(__file__).startswith("test_")
