"""La versione a riga di comando, guidata dal controller vero con un
adattatore a copione: niente tastiera, niente finestre, niente suoni.

Dalla 10.13.21 un risultato registrato in console arriva ai punti e allo
storico dei giocatori, e il turno successivo si abbina come dopo un turno
giocato: cli_adapter costruiva players_dict con dizionari nuovi, distinti da
quelli di players, e ui.update_match_result scriveva li'. Dalla 10.13.15
l'iscrizione dal database FIDE della console crea la scheda della finestra,
con tutti i dati FIDE, segnata pero' come esperta, come faceva gia', e non
raddoppia una scheda che il database ha gia'. Tutto lavora nella cartella temporanea della prova; il motore
degli abbinamenti e' quello vero."""

import types

import pytest
from test_db import RECORD_FIDE

ELO = {"G1": 1800, "G2": 1700, "G3": 1600, "G4": 1500}


@pytest.fixture
def muto(monkeypatch):
    """I suoni di tutti i moduli che ne chiedono, muti."""
    import cli_adapter
    import controller
    import tournament
    import ui
    import utils

    for modulo in (utils, ui, cli_adapter, tournament, controller):
        if hasattr(modulo, "play_sound"):
            monkeypatch.setattr(modulo, "play_sound", lambda *a, **k: True)


class Copione:
    """Le risposte, nell'ordine, a input, a enter_escape e alle conferme del
    controller; ogni domanda senza risposta ferma la prova."""

    def __init__(self, monkeypatch, tasti=(), conferme=()):
        import ui

        self.tasti = list(tasti)
        self.conferme = list(conferme)
        self.domande = []
        monkeypatch.setattr("builtins.input", self.input)
        monkeypatch.setattr(ui, "enter_escape", self.conferma)
        monkeypatch.setattr(ui, "key", self.input)

    def input(self, domanda=""):
        self.domande.append(domanda)
        assert self.tasti, f"domanda senza risposta: {domanda}"
        return self.tasti.pop(0)

    def conferma(self, domanda="", *a, **k):
        self.domande.append(domanda)
        assert self.conferme, f"conferma senza risposta: {domanda}"
        return self.conferme.pop(0)


def _adattatore(copione):
    """L'adattatore vero della console, con le conferme del controller a
    copione e i messaggi annotati."""
    from cli_adapter import CLIAdapter

    class AdattatoreACopione(CLIAdapter):
        def __init__(self):
            self.messaggi = []

        def show_message(self, message):
            self.messaggi.append(message)

        def show_error(self, message):
            self.messaggi.append(message)

        def confirm(self, prompt, default=True):
            return copione.conferma(prompt)

        def display_tournament_status(self, tournament):
            pass

    return AdattatoreACopione()


def _torneo_al_primo_turno():
    """Quattro giocatori, tre turni, il primo abbinato e senza risultati."""
    from models import Player, Tournament

    giocatori = [
        Player.from_dict({"id": pid, "first_name": "Nome" + pid, "last_name": "Cognome" + pid, "initial_elo": float(elo), "current_elo": float(elo)}).to_dict()
        for pid, elo in ELO.items()
    ]
    return Tournament.from_dict(
        {
            "name": "Console_Prova",
            "tournament_id": "CONSOLE_PROVA",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "total_rounds": 3,
            "current_round": 1,
            "next_match_id": 3,
            "bye_value": 1.0,
            "players": giocatori,
            "rounds": [
                {
                    "round": 1,
                    "matches": [
                        {"id": 1, "round": 1, "white_player_id": "G1", "black_player_id": "G3", "result": None},
                        {"id": 2, "round": 1, "white_player_id": "G4", "black_player_id": "G2", "result": None},
                    ],
                }
            ],
        }
    )


def _controller(adattatore, torneo):
    import config
    from controller import TournamentController

    guida = TournamentController(adattatore)
    guida.tournament = torneo
    guida.active_filename = config.user_data_path("Tornello - Console_Prova.json")
    return guida


class TestRisultatiInConsole:
    def test_punti_storico_e_turno_successivo(self, monkeypatch, muto):
        from tournament import load_tournament

        # Scacchiera 1: G1 batte G3; scacchiera 2: G4 e G2 pattano; INVIO
        # vuoto chiude l'inserimento. Poi si continua, si abbina il turno 2,
        # e alla sua richiesta dei risultati si esce.
        copione = Copione(monkeypatch, tasti=["1", "1-0", "2", "1/2", "", ""], conferme=[True, True, True, True, False])
        guida = _controller(_adattatore(copione), _torneo_al_primo_turno())

        guida._main_loop()

        salvato = load_tournament(guida.active_filename)
        giocatori = {p["id"]: p for p in salvato["players"]}
        assert {pid: p["points"] for pid, p in giocatori.items()} == {"G1": 1.0, "G2": 0.5, "G3": 0.0, "G4": 0.5}
        assert giocatori["G1"]["results_history"][0] == {"round": 1, "opponent_id": "G3", "color": "white", "result": "1-0", "score": 1.0}
        assert [v["result"] for v in giocatori["G2"]["results_history"]] == ["1/2-1/2"]
        assert len(salvato["rounds"]) == 2
        # Il turno 2 e' abbinato come dopo un turno giocato: nessuna coppia
        # si ripete, e G1, solo in testa, gioca con uno dei due a mezzo punto.
        coppie_1 = {frozenset(("G1", "G3")), frozenset(("G4", "G2"))}
        coppie_2 = {frozenset((m["white_player_id"], m["black_player_id"])) for m in salvato["rounds"][1]["matches"]}
        assert not coppie_1 & coppie_2
        avversario_di_g1 = next(iter(next(c for c in coppie_2 if "G1" in c) - {"G1"}))
        assert avversario_di_g1 in ("G2", "G4")

    def test_il_ritiro_dopo_un_forfait_arriva_al_torneo(self, monkeypatch, muto):
        """ui.update_match_result ritira il giocatore trovato in
        players_dict: con i dizionari copiati il ritiro si perdeva."""
        copione = Copione(monkeypatch, tasti=["1", "1-F", ""], conferme=[True, True])
        adattatore = _adattatore(copione)
        torneo = _torneo_al_primo_turno()

        assert adattatore.update_match_results(torneo) is True

        g3 = torneo.players_dict["G3"]
        assert g3.withdrawn is True
        assert g3.results_history[0].result == "1-F"
        assert torneo.players_dict["G1"].points == 1.0

    def test_la_conferma_della_lista_passa_a_ui_gli_stessi_dizionari(self, monkeypatch):
        """Anche confirm_player_list passa a ui un players_dict con gli
        stessi dizionari di players."""
        import ui

        adattatore = _adattatore(types.SimpleNamespace(conferma=lambda *a: True))
        torneo = _torneo_al_primo_turno()
        visti = {}

        def conferma_finta(torneo_dict, players_db):
            visti["stessi"] = all(torneo_dict["players_dict"][p["id"]] is p for p in torneo_dict["players"])
            return True

        monkeypatch.setattr(ui, "_conferma_lista_giocatori_torneo", conferma_finta)

        assert adattatore.confirm_player_list(torneo, {}) is True
        assert visti["stessi"] is True


class TestIscrizioneFideInConsole:
    def _iscrivi(self, monkeypatch, giocatori, testo):
        import ui

        monkeypatch.setattr(ui, "_cerca_giocatore_nel_db_fide", lambda termine: [dict(RECORD_FIDE)])
        monkeypatch.setattr(ui, "play_sound", lambda *a, **k: True)
        Copione(monkeypatch, tasti=[testo, "", "c"], conferme=[True])
        return ui.input_players(giocatori, torneo_obj={"tournament_category": "rapid"})

    def test_la_scheda_ha_tutti_i_dati_fide(self, monkeypatch):
        from db_players import load_players_db

        iscritti = self._iscrivi(monkeypatch, {}, "nicolini")

        assert [p["id"] for p in iscritti] == ["NICSA001"]
        assert iscritti[0]["initial_elo"] == 1806
        scheda = load_players_db()["NICSA001"]
        assert (scheda["elo_rapid"], scheda["fide_rapid_k"], scheda["current_elo"]) == (1806, 40, 1399)
        assert scheda["fide_id_num_str"] == "805165"
        # La console tiene il suo experienced.
        assert scheda["experienced"] is True

    def test_una_scheda_con_lo_stesso_id_fide_non_si_raddoppia(self, monkeypatch):
        esistente = {"id": "NICSA004", "first_name": "Savino", "last_name": "Nicolini", "current_elo": 1500, "fide_id_num_str": "805165"}
        giocatori = {"NICSA004": esistente}

        iscritti = self._iscrivi(monkeypatch, giocatori, "805165")

        assert [p["id"] for p in iscritti] == ["NICSA004"]
        assert list(giocatori) == ["NICSA004"]
