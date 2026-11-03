"""CANC sulle voci dell'albero della finestra principale. Issue 71.

Dalla 10.14.0 CANC su una partita giocata del turno corrente la riporta fra
quelle da giocare, come [cancella] della console, dopo una domanda con No
predefinito; il riposo, i turni gia' chiusi, i tornei conclusi e le partite
con un giocatore ritirato si rifiutano con un messaggio. CANC e'
l'acceleratore della voce Elimina Torneo Attivo del menu File, e il suo
gestore smista per voce scelta: sul torneo e sul giocatore fa quello che
faceva, sulle altre voci suona l'errore senza parlare di tornei da eliminare.
Le prove sulle funzioni di tournament.py girano senza finestre; le altre
sulla finestra principale vera, mai mostrata, con le domande finte che
annotano titolo, testo e pulsante predefinito, e i suoni annotati.
"""

import copy
import json
import os
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


def _canc(principale, voce):
    """La voce scelta nell'albero, poi CANC: il tasto arriva come comando
    della voce Elimina Torneo Attivo, di cui e' l'acceleratore."""
    import wx

    principale.tree_ctrl.SelectItem(voce)
    evento = wx.CommandEvent(wx.wxEVT_MENU, principale.item_delete_tournament.GetId())
    evento.SetEventObject(principale)
    assert principale.GetEventHandler().ProcessEvent(evento)


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
        # Il cursore resta sulla partita, adesso fra quelle da giocare.
        scelta = principale.tree_ctrl.GetSelection()
        assert principale.tree_ctrl.GetItemData(scelta)["match"]["id"] == 4
        genitore = principale.tree_ctrl.GetItemParent(scelta)
        while principale.tree_ctrl.GetItemData(genitore)["action"] != "category_da_giocare":
            genitore = principale.tree_ctrl.GetItemParent(genitore)
        assert principale.tree_ctrl.GetItemText(principale.tree_ctrl.GetItemParent(genitore)).startswith("Turno corrente")
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
        assert "Time Machine (Ctrl+Z)" in messaggio.testo
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
    """Il gestore della voce Elimina Torneo Attivo smista per voce scelta."""

    def test_sulle_altre_voci_solo_il_suono_dell_errore(self, principale, suoni, monkeypatch):
        """Fino alla 10.13.62 diceva di scegliere un torneo da eliminare."""
        percorso = _apri(principale)
        domande = _domande(monkeypatch)
        prima = _dal_file(percorso)
        voci = [
            _voce(principale, action="show_data", filepath=percorso),
            _voce(principale, action="show_round_report", filepath=percorso, round=2),
            _voce(principale, action="category_giocate", filepath=percorso, round=2),
            _voce(principale, action="show_standings", filepath=percorso),
            # La partita da giocare: nella 10.14.0 CANC non ha niente da
            # togliere.
            _voce_della_partita(principale, percorso, 2, 2, 5),
        ]
        for voce in voci:
            suoni.clear()
            _canc(principale, voce)
            assert suoni == ["errore"], principale.tree_ctrl.GetItemData(voce)
        assert domande.aperte == []
        assert _dal_file(percorso) == prima

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

    def test_la_voce_del_menu_tiene_il_suo_tasto(self, principale):
        assert principale.item_delete_tournament.GetItemLabel() == "E&limina Torneo Attivo...\tDelete"


def test_il_torneo_di_prova_e_coerente():
    """I punti del torneo di prova sono quelli del suo storico: le prove qui
    sopra ne misurano i cambiamenti."""
    from tournament import ricalcola_punti_tutti_giocatori

    torneo = _torneo()
    copia = copy.deepcopy(torneo)
    ricalcola_punti_tutti_giocatori(copia)
    assert {g["id"]: g["points"] for g in copia["players"]} == {g["id"]: g["points"] for g in torneo["players"]}
    assert os.path.basename(__file__).startswith("test_")
