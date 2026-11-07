"""La versione a riga di comando, guidata dal controller vero con un
adattatore a copione: niente tastiera, niente finestre, niente suoni.

Dalla 10.13.21 un risultato registrato in console arriva ai punti e allo
storico dei giocatori, e il turno successivo si abbina come dopo un turno
giocato: cli_adapter costruiva players_dict con dizionari nuovi, distinti da
quelli di players, e ui.update_match_result scriveva li'. Dalla 10.13.15
l'iscrizione dal database FIDE della console crea la scheda della finestra,
con tutti i dati FIDE, e non raddoppia una scheda che il database ha gia';
dalla 10.13.33 non la segna piu' esperta, e chi non ha un fattore K FIDE
valido ha K 40, come nella finestra. Tutto lavora nella cartella temporanea della prova; il motore
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
        # Dalla 10.13.33 la scheda e' quella della finestra, senza
        # experienced: fino alla 10.13.32 la console la segnava esperta.
        assert "experienced" not in scheda

    def test_senza_k_fide_valido_il_k_e_40_come_nella_finestra(self, monkeypatch):
        """RECORD_FIDE non ha rating standard e ha k_factor 0: il K che la
        colonna Elo Var. e la finalizzazione useranno per l'iscritto della
        console e' 40, come per quello della finestra, che passa da
        scheda_da_record_fide. Fino alla 10.13.32 era 20 (10.13.33)."""
        from db_players import fattore_k_della_finalizzazione, load_players_db, scheda_da_record_fide

        iscritti = self._iscrivi(monkeypatch, {}, "nicolini")

        database = load_players_db()
        dalla_finestra = scheda_da_record_fide(RECORD_FIDE, {})
        dalla_finestra.pop("registration_date")
        dalla_console = database["NICSA001"]
        assert {chiave: dalla_console.get(chiave) for chiave in dalla_finestra} == dalla_finestra
        assert "experienced" not in dalla_console
        assert fattore_k_della_finalizzazione(iscritti[0], database, "2026-09-26") == 40

    def test_una_scheda_con_lo_stesso_id_fide_non_si_raddoppia(self, monkeypatch):
        esistente = {"id": "NICSA004", "first_name": "Savino", "last_name": "Nicolini", "current_elo": 1500, "fide_id_num_str": "805165"}
        giocatori = {"NICSA004": esistente}

        iscritti = self._iscrivi(monkeypatch, giocatori, "805165")

        assert [p["id"] for p in iscritti] == ["NICSA004"]
        assert list(giocatori) == ["NICSA004"]


class TestRipresaDellaCreazioneSospesa:
    """Un torneo con l'iscrizione sospesa dalla console, con la S alla fine
    dell'inserimento, si riprende al lancio successivo: il controller lo
    riconosce, fa continuare l'iscrizione e completa la creazione fino al
    turno 1. Fino alla 10.13.48 il modello Tournament scartava la chiave
    creation_suspended, la ripresa non partiva mai e il torneo si apriva come
    se l'iscrizione fosse finita (issue 60); e se fosse partita, finita
    l'iscrizione avrebbe cominciato la creazione di un torneo nuovo."""

    def _sospeso(self):
        """Il json che la console scrive sospendendo: quattro iscritti, tre
        turni, nessun turno abbinato e il contrassegno della sospensione."""
        from models import Player, Tournament
        from tournament import save_tournament

        torneo = Tournament.from_dict(
            {
                "name": "Console_Prova",
                "tournament_id": "CONSOLE_PROVA",
                "start_date": "2026-09-01",
                "end_date": "2026-09-30",
                "total_rounds": 3,
                "players": [
                    Player.from_dict({"id": pid, "first_name": "Nome" + pid, "last_name": "Cognome" + pid, "initial_elo": float(elo), "current_elo": float(elo)}).to_dict()
                    for pid, elo in ELO.items()
                ],
            }
        ).to_dict()
        torneo["creation_suspended"] = True
        assert save_tournament(torneo)

    def test_la_ripresa_parte_e_arriva_al_turno_1(self, monkeypatch, muto, tmp_path):
        import config
        import ui
        from controller import TournamentController
        from tournament import load_tournament

        self._sospeso()
        percorso = config.user_data_path("Tornello - Console_Prova.json")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(ui, "_conferma_lista_giocatori_torneo", lambda torneo, db: True)
        # INVIO carica l'unico torneo; INVIO vuoto e C chiudono l'iscrizione
        # ripresa. Poi il bye suggerito e la cartella proposta.
        copione = Copione(monkeypatch, tasti=["", "", "c"], conferme=[True, True])
        adattatore = _adattatore(copione)
        guida = TournamentController(adattatore)

        guida._select_or_create_tournament()

        assert copione.tasti == [] and copione.conferme == []
        assert any("Ripresa inserimento giocatori" in m for m in adattatore.messaggi)
        assert guida.tournament.creation_suspended is False
        salvato = load_tournament(percorso)
        assert "creation_suspended" not in salvato
        assert sorted(p["id"] for p in salvato["players"]) == sorted(ELO)
        assert [r["round"] for r in salvato["rounds"]] == [1]
        abbinati = {pid for m in salvato["rounds"][0]["matches"] for pid in (m["white_player_id"], m["black_player_id"])}
        assert abbinati == set(ELO)

    def _avviato_con_il_contrassegno(self):
        """Il json di un torneo sospeso in console e poi avviato e giocato
        nella finestra, che lavora sul dizionario e fino alla revisione della
        10.13.49 non toglieva il contrassegno: il turno 1 giocato, il 2
        abbinato e creation_suspended ancora vero."""
        from tournament import save_tournament

        torneo = _torneo_al_primo_turno().to_dict()
        torneo["rounds"][0]["matches"][0]["result"] = "1-0"
        torneo["rounds"][0]["matches"][1]["result"] = "0-1"
        torneo["rounds"].append(
            {
                "round": 2,
                "matches": [
                    {"id": 3, "round": 2, "white_player_id": "G2", "black_player_id": "G1", "result": None},
                    {"id": 4, "round": 2, "white_player_id": "G3", "black_player_id": "G4", "result": None},
                ],
            }
        )
        torneo["current_round"] = 2
        torneo["next_match_id"] = 5
        torneo["creation_suspended"] = True
        assert save_tournament(torneo)

    def _controlla_i_turni_intatti(self, guida, adattatore, percorso):
        from tournament import load_tournament

        assert not any("Ripresa" in m for m in adattatore.messaggi)
        assert not any("creazione sospesa" in m for m in adattatore.messaggi)
        assert guida.tournament.creation_suspended is False
        assert [r.round for r in guida.tournament.rounds] == [1, 2]
        assert [m.result for m in guida.tournament.rounds[0].matches] == ["1-0", "0-1"]
        salvato = load_tournament(percorso)
        assert [r["round"] for r in salvato["rounds"]] == [1, 2]
        assert [m["result"] for m in salvato["rounds"][0]["matches"]] == ["1-0", "0-1"]

    def test_un_torneo_con_dei_turni_non_riprende_la_creazione(self, monkeypatch, muto, tmp_path):
        """Il contrassegno rimasto su un torneo che ha gia' dei turni non fa
        ripartire la creazione: fino alla revisione della 10.13.49 la console
        riprendeva l'iscrizione e, conclusa, azzerava i turni e abbinava di
        nuovo il turno 1, cancellando i risultati registrati."""
        import config
        from controller import TournamentController

        self._avviato_con_il_contrassegno()
        percorso = config.user_data_path("Tornello - Console_Prova.json")
        monkeypatch.chdir(tmp_path)
        # INVIO carica l'unico torneo, e nient'altro viene chiesto. Se la
        # ripresa partisse, l'iscrizione chiederebbe un tasto che non c'e'.
        copione = Copione(monkeypatch, tasti=[""])
        adattatore = _adattatore(copione)
        guida = TournamentController(adattatore)

        guida._select_or_create_tournament()

        assert copione.tasti == []
        self._controlla_i_turni_intatti(guida, adattatore, percorso)

    def test_fra_piu_tornei_quello_avviato_non_e_fra_i_sospesi(self, monkeypatch, muto, tmp_path):
        """Con piu' tornei nella cartella l'elenco dei tornei sospesi non
        nomina quello che ha gia' dei turni, e sceglierlo dall'elenco lo apre
        com'e'."""
        import glob
        import os

        import config
        from controller import TournamentController
        from models import Tournament
        from tournament import save_tournament

        self._avviato_con_il_contrassegno()
        altro = Tournament.from_dict(
            {"name": "Altro_Prova", "tournament_id": "ALTRO_PROVA", "start_date": "2026-10-01", "end_date": "2026-10-31", "total_rounds": 3}
        ).to_dict()
        assert save_tournament(altro)
        percorso = config.user_data_path("Tornello - Console_Prova.json")
        monkeypatch.chdir(tmp_path)
        nomi = [os.path.basename(f) for f in glob.glob("Tornello - *.json")]
        scelta = nomi.index("Tornello - Console_Prova.json") + 1
        copione = Copione(monkeypatch, tasti=[str(scelta)])
        adattatore = _adattatore(copione)
        guida = TournamentController(adattatore)

        guida._select_or_create_tournament()

        assert copione.tasti == []
        self._controlla_i_turni_intatti(guida, adattatore, percorso)

    def test_la_finestra_avviando_il_torneo_toglie_il_contrassegno(self):
        """La finestra registra il turno 1 con registra_turno, sul dizionario
        del torneo: il contrassegno della sospensione se ne va. Fino alla
        revisione della 10.13.49 restava nel json del torneo avviato."""
        from tournament import registra_turno

        torneo = _torneo_al_primo_turno().to_dict()
        partite = torneo["rounds"].pop()["matches"]
        torneo["current_round"] = 0
        torneo["creation_suspended"] = True

        registra_turno(torneo, partite, 1)

        assert "creation_suspended" not in torneo
        assert [r["round"] for r in torneo["rounds"]] == [1]


class TestCartellaDellaCreazioneInConsole:
    """10.19.40 (decisione di Gabriele del 7 novembre 2026). Alla fine della
    creazione la console chiede dove salvare i report e la raccolta delle
    partite, come la procedura guidata della finestra con la sua Cartella
    Salvataggio, e dalla correzione della 10.19.40 la domanda lo dice:
    fino ad allora diceva i dati. La cartella
    scelta riceve i report e la raccolta delle partite, e il file del
    torneo resta nella cartella del programma, dove save_tournament lo
    scrive (manuale, sezione 4.1). Il messaggio Torneo creato e
    active_filename dicono quel file, e la domanda propone la cartella del
    programma. Fino alla 10.19.39, e gia' nella 10.0.0, con una cartella
    scelta active_filename e il messaggio dicevano un file nella cartella
    scelta, che non nasceva mai, la copia di sicurezza della chiusura non
    si faceva, e i report andavano nella cartella del programma; la domanda
    proponeva la cartella da cui Tornello era stato avviato. Tornello si
    avvia qui da un'altra cartella, lavoro."""

    REPORT = ("Tornello - Console_Prova - Classifica.txt", "Tornello - Console_Prova - Turno corrente.txt")

    @staticmethod
    def _suoni(monkeypatch):
        """I suoni chiesti da tutti i moduli, annotati per nome."""
        import cli_adapter
        import controller
        import tournament
        import ui
        import utils

        suoni = []
        for modulo in (utils, ui, cli_adapter, tournament, controller):
            if hasattr(modulo, "play_sound"):
                monkeypatch.setattr(modulo, "play_sound", lambda nome, *a, **k: suoni.append(nome) or True)
        return suoni

    @staticmethod
    def _creazione(monkeypatch, tmp_path, tasti, conferme):
        """Console_Prova, con i quattro iscritti e senza turni, arriva alla
        fine della creazione con le risposte date, avviata dalla cartella
        lavoro."""
        import config
        from controller import TournamentController

        lavoro = tmp_path / "lavoro"
        lavoro.mkdir()
        monkeypatch.chdir(lavoro)
        copione = Copione(monkeypatch, tasti=tasti, conferme=conferme)
        adattatore = _adattatore(copione)
        guida = TournamentController(adattatore)
        torneo = _torneo_al_primo_turno()
        torneo.rounds = []
        torneo.current_round = 0
        torneo.next_match_id = 1
        guida.tournament = torneo
        guida.active_filename = config.user_data_path("Tornello - Console_Prova.json")
        guida._completa_la_creazione()
        assert copione.tasti == [] and copione.conferme == []
        return types.SimpleNamespace(guida=guida, copione=copione, adattatore=adattatore, lavoro=lavoro)

    @staticmethod
    def _domande_attese(*altre):
        import os

        import config

        programma = os.path.abspath(config.user_data_path(""))
        return ["Accetti il valore suggerito? (No = usa 1.0)", f"Vuoi che i report e la raccolta delle partite vengano salvati in {programma}?", *altre]

    @staticmethod
    def _copie_di_chiusura():
        import glob
        import os

        import config

        return glob.glob(os.path.join(config.user_data_path("backup"), "**", "Tornello - Console_Prova_chiusura_torneo_*.json"), recursive=True)

    @pytest.mark.parametrize("scritta", ["per intero", "relativa"])
    def test_la_cartella_scelta_riceve_i_report(self, monkeypatch, muto, tmp_path, scritta):
        """No alla cartella proposta, e la cartella report, scritta per
        intero o relativa alla cartella da cui Tornello e' avviato: il file
        del torneo nasce nella cartella del programma, e il messaggio e
        active_filename dicono quello; il torneo ha la cartella scelta, per
        intero, per i report, che nascono li', e la cartella del programma
        non ne ha. All'uscita, dopo una modifica del torneo, la copia di
        sicurezza della chiusura si fa."""
        import os

        import config
        from tournament import load_tournament

        suoni = self._suoni(monkeypatch)
        scelta = tmp_path / "lavoro" / "report"
        creato = self._creazione(monkeypatch, tmp_path, [str(scelta) if scritta == "per intero" else "report"], [True, False])
        file_del_torneo = config.user_data_path("Tornello - Console_Prova.json")

        assert creato.copione.domande == self._domande_attese("Inserisci il percorso di salvataggio desiderato: ")
        assert creato.guida.active_filename == file_del_torneo
        assert os.path.isfile(file_del_torneo)
        assert creato.adattatore.messaggi[-1] == f"\nTorneo 'Console_Prova' creato e Turno 1 generato. File: '{file_del_torneo}'"
        assert (creato.guida.tournament.custom_save_path, creato.guida.tournament.save_path) == (str(scelta), str(scelta))
        salvato = load_tournament(file_del_torneo)
        assert (salvato["custom_save_path"], salvato["save_path"]) == (str(scelta), str(scelta))
        assert [r["round"] for r in salvato["rounds"]] == [1]
        assert tuple(sorted(os.listdir(scelta))) == self.REPORT
        assert not [n for n in os.listdir(config.user_data_path("")) if n.startswith("Tornello - Console_Prova - ")]
        assert os.listdir(creato.lavoro) == ["report"]
        assert suoni == ["nuovo_turno"]
        # Il torneo cambia dopo la copia della creazione, e all'uscita la
        # copia della chiusura nasce dal suo file.
        creato.guida.tournament.site = "Altrove"
        creato.guida._save_state()
        assert self._copie_di_chiusura() == []

        with pytest.raises(SystemExit):
            creato.guida._exit_program(0)

        copie = self._copie_di_chiusura()
        assert len(copie) == 1
        assert load_tournament(copie[0])["site"] == "Altrove"
        assert suoni == ["nuovo_turno", "chiusura"]

    def test_con_si_tutto_resta_nella_cartella_del_programma(self, monkeypatch, muto, tmp_path):
        """Si' alla cartella proposta, che e' quella del programma, e non
        quella da cui Tornello e' avviato: il file del torneo e i report
        nascono nella cartella del programma, il torneo non ha una cartella
        sua, come prima, e la cartella di avvio resta vuota."""
        import os

        import config
        from tournament import load_tournament

        suoni = self._suoni(monkeypatch)
        creato = self._creazione(monkeypatch, tmp_path, [], [True, True])
        file_del_torneo = config.user_data_path("Tornello - Console_Prova.json")

        assert creato.copione.domande == self._domande_attese()
        assert creato.guida.active_filename == file_del_torneo
        assert creato.adattatore.messaggi[-1] == f"\nTorneo 'Console_Prova' creato e Turno 1 generato. File: '{file_del_torneo}'"
        salvato = load_tournament(file_del_torneo)
        assert (salvato["custom_save_path"], salvato["save_path"]) == ("", "")
        nel_programma = os.listdir(config.user_data_path(""))
        assert tuple(sorted(n for n in nel_programma if n.startswith("Tornello - Console_Prova - "))) == self.REPORT
        assert os.listdir(creato.lavoro) == []
        assert suoni == ["nuovo_turno"]


# La pianificazione che la partita della scacchiera 1 ha gia', e quella che
# si scrive, per TestIlFileDelTorneoInConsole.
PIANIFICAZIONE_DI_PRIMA = {"date": "2026-09-10", "time": "18:00", "channel": "", "arbiter": ""}
PIANIFICAZIONE_NUOVA = {"date": "2026-09-11", "time": "20:30", "channel": "Lichess", "arbiter": "Verdi"}


class TestIlFileDelTorneoInConsole:
    """10.19.41 (decisione di Gabriele del 7 novembre 2026). La console
    cerca i tornei nella cartella del programma, come l'albero della
    finestra, da qualunque cartella sia avviata, e tiene il file del torneo
    con il percorso intero; il torneo aperto si salva sempre nel suo file,
    come nella finestra: i salvataggi del controller, quelli di
    ui.update_match_result, la sospensione dell'iscrizione e la copia di
    sicurezza della Time Machine. Fino alla 10.19.40, e gia' nella 10.0.0,
    la console cercava i tornei nella cartella di avvio, e li salvava nel
    file che nasce dal nome, nella cartella del programma: avviata da
    un'altra cartella con una copia del torneo, apriva la copia e la
    scriveva sopra il torneo vero; un torneo rinominato dal ramo Dati della
    finestra, che tiene il file di prima, finiva in un file nuovo, e quello
    aperto restava com'era, anche con la creazione sospesa, che all'avvio
    dopo tornava e riscriveva il turno 1 del torneo gia' avviato."""

    @staticmethod
    def _scrivi(percorso, torneo):
        import json

        with open(percorso, "w", encoding="utf-8") as f:
            json.dump(torneo, f)

    @staticmethod
    def _leggi(percorso):
        import json

        with open(percorso, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _tornei():
        """I file dei tornei nella cartella del programma, per nome."""
        import os

        import config

        return sorted(
            n
            for n in os.listdir(config.user_data_path(""))
            if n.startswith("Tornello - ") and n.endswith(".json") and n not in ("Tornello - Players_db.json", "Tornello - Settings.json")
        )

    @staticmethod
    def _copie(nome):
        import glob
        import os

        import config

        return glob.glob(os.path.join(config.user_data_path("backup"), "**", nome), recursive=True)

    def _rinominato(self, **altro):
        """Il torneo Corona nel file Tornello - Prova_stessa_data.json, come
        lo lascia un cambio del nome dal ramo Dati della finestra."""
        import config

        torneo = _torneo_al_primo_turno().to_dict()
        torneo["name"] = "Corona"
        torneo.update(altro)
        percorso = config.user_data_path("Tornello - Prova_stessa_data.json")
        self._scrivi(percorso, torneo)
        return percorso

    def test_avviata_da_un_altra_cartella_apre_e_salva_il_torneo_del_programma(self, monkeypatch, muto, tmp_path):
        """Nella cartella del programma Console_Prova ha il risultato della
        prima partita; nella cartella di avvio, lavoro, c'e' una sua copia
        vecchia, senza risultati. INVIO apre il torneo della cartella del
        programma, con il percorso intero, e il salvataggio lo scrive li':
        la copia resta com'era."""
        import os

        import config
        from controller import TournamentController

        vero = _torneo_al_primo_turno().to_dict()
        vero["rounds"][0]["matches"][0]["result"] = "1-0"
        file_vero = config.user_data_path("Tornello - Console_Prova.json")
        self._scrivi(file_vero, vero)
        lavoro = tmp_path / "lavoro"
        lavoro.mkdir()
        copia = lavoro / "Tornello - Console_Prova.json"
        self._scrivi(copia, _torneo_al_primo_turno().to_dict())
        prima = copia.read_bytes()
        monkeypatch.chdir(lavoro)
        copione = Copione(monkeypatch, tasti=[""])
        adattatore = _adattatore(copione)
        guida = TournamentController(adattatore)

        guida._select_or_create_tournament()

        assert copione.tasti == []
        assert adattatore.messaggi == [
            "\nTrovato un solo torneo esistente: 'Console_Prova' (File: Tornello - Console_Prova.json)",
            "Caricamento di 'Console_Prova'...",
        ]
        assert guida.active_filename == file_vero
        assert guida.tournament.rounds[0].matches[0].result == "1-0"
        guida.tournament.site = "Altrove"
        guida._save_state()
        salvato = self._leggi(file_vero)
        assert (salvato["site"], salvato["rounds"][0]["matches"][0]["result"]) == ("Altrove", "1-0")
        assert copia.read_bytes() == prima
        assert os.listdir(lavoro) == ["Tornello - Console_Prova.json"]

    def test_la_cartella_del_programma_con_le_parentesi_quadre(self, monkeypatch, muto, tmp_path):
        """La cartella del programma si chiama Tornello [prova], con le
        parentesi quadre, e la console e' avviata da li'. INVIO apre il suo
        torneo, con il percorso intero, e lo stesso elenco lo legge l'albero
        della finestra. Nella prima stesura della 10.19.41 glob leggeva le
        parentesi come un insieme di caratteri: la console diceva Nessun
        torneo esistente trovato, e chiedeva se crearne uno, mentre fino
        alla 10.19.40, avviata dalla cartella del programma, il torneo lo
        trovava; l'albero non lo trovava gia' prima."""
        import percorsi

        from controller import TournamentController
        from tournament import tornei_nella_cartella_del_programma

        programma = tmp_path / "Tornello [prova]"
        programma.mkdir()
        monkeypatch.setattr(percorsi, "cartella_applicazione", lambda: str(programma))
        file_del_torneo = str(programma / "Tornello - Console_Prova.json")
        self._scrivi(file_del_torneo, _torneo_al_primo_turno().to_dict())
        monkeypatch.chdir(programma)
        copione = Copione(monkeypatch, tasti=[""])
        adattatore = _adattatore(copione)
        guida = TournamentController(adattatore)

        guida._select_or_create_tournament()

        assert tornei_nella_cartella_del_programma() == [file_del_torneo]
        assert copione.tasti == []
        assert adattatore.messaggi == [
            "\nTrovato un solo torneo esistente: 'Console_Prova' (File: Tornello - Console_Prova.json)",
            "Caricamento di 'Console_Prova'...",
        ]
        assert guida.active_filename == file_del_torneo
        assert guida.tournament.name == "Console_Prova"

    @pytest.mark.parametrize("strada", ["risultato", "time machine", "abbinamento non riuscito"])
    def test_un_torneo_rinominato_resta_nel_suo_file(self, monkeypatch, muto, tmp_path, capsys, strada):
        """Corona, rinominato dalla finestra, si apre dalla console e si
        gioca: un risultato registrato, una Time Machine chiesta con t fra i
        risultati, o la Time Machine dopo un abbinamento non riuscito. Ogni
        salvataggio scrive nel file aperto, la copia di sicurezza della
        Time Machine si fa da li', e un file con il nome nuovo non nasce.
        Il cestino e' finto: la Time Machine dopo l'abbinamento non riuscito
        toglie il turno 1, concluso, e il suo file dei dettagli, che la
        conclusione del turno ha appena scritto, va nel cestino. Nella prima
        stesura della 10.19.41 quel file finiva nel cestino vero di Windows,
        a ogni corsa delle prove."""
        import os

        from test_copie_di_sicurezza import CestinoFinto

        import config
        import controller
        import utils
        from controller import TournamentController

        cestino = CestinoFinto(str(tmp_path / "cestino"))
        monkeypatch.setattr(utils, "delete_file_to_trash", cestino)
        if strada == "abbinamento non riuscito":
            torneo = _torneo_al_primo_turno().to_dict()
            for partita, risultato in zip(torneo["rounds"][0]["matches"], ("1-0", "0-1"), strict=True):
                partita["result"] = risultato
            aperto = self._rinominato(rounds=torneo["rounds"])
            monkeypatch.setattr(controller, "generate_pairings_for_round", lambda *a, **k: None)
            monkeypatch.setattr(controller, "handle_bbpairings_failure", lambda *a, **k: "time_machine")
            # INVIO apre il torneo; Si' all'abbinamento del turno 2, che non
            # riesce; la Time Machine al turno 1, si; poi INVIO vuoto fra i
            # risultati e No a continuare.
            tasti, conferme = ["", "1", "si", ""], [True, False]
        else:
            aperto = self._rinominato()
            if strada == "risultato":
                # INVIO apre il torneo; 1-0 sulla scacchiera 1, confermato;
                # INVIO vuoto e No a continuare.
                tasti, conferme = ["", "1", "1-0", ""], [True, False]
            else:
                # INVIO apre il torneo; t, il turno 1, si; INVIO vuoto e No a
                # continuare.
                tasti, conferme = ["", "t", "1", "si", ""], [False]
        monkeypatch.chdir(tmp_path)
        copione = Copione(monkeypatch, tasti=tasti, conferme=conferme)
        guida = TournamentController(_adattatore(copione))

        guida._select_or_create_tournament()
        guida._main_loop()

        assert copione.tasti == [] and copione.conferme == []
        assert guida.active_filename == aperto
        assert self._tornei() == ["Tornello - Prova_stessa_data.json"]
        salvato = self._leggi(aperto)
        assert salvato["name"] == "Corona"
        stampato = capsys.readouterr().out
        if strada == "risultato":
            assert [m["result"] for m in salvato["rounds"][0]["matches"]] == ["1-0", None]
        else:
            assert [m["result"] for m in salvato["rounds"][0]["matches"]] == [None, None]
            assert len(self._copie("Tornello - Prova_stessa_data_pre_timemachine_*.json")) == 1
            assert f"Backup di sicurezza creato: {aperto}" in stampato.splitlines()
            assert "Impossibile creare il backup" not in stampato
        dettagli = [os.path.abspath(config.user_data_path("Tornello - Corona - Turno 1 Dettagli.txt"))]
        assert cestino.ricevuti == (dettagli if strada == "abbinamento non riuscito" else [])

    @pytest.mark.parametrize(
        "azione", ["ritiro", "cancellazione", "pianificazione creata", "pianificazione modificata", "pianificazione rimossa"]
    )
    def test_le_altre_azioni_fra_i_risultati_salvano_nel_file_aperto(self, monkeypatch, muto, tmp_path, azione):
        """Corona, rinominato dalla finestra, si apre dalla console, e fra i
        risultati si ritira il primo giocatore, si cancella il risultato
        della scacchiera 1, o la si pianifica, se ne cambia la
        pianificazione o la si toglie. Il salvataggio di
        ui.update_match_result scrive il cambio nel file aperto, prima di
        quello del controller, e un file con il nome nuovo non nasce. Le
        cinque azioni salvano ciascuna per conto suo: senza il file aperto,
        quel salvataggio andava nel file che nasce dal nome, Tornello -
        Corona.json, come fino alla 10.19.40."""
        import ui
        from controller import TournamentController

        torneo = _torneo_al_primo_turno().to_dict()
        partita = torneo["rounds"][0]["matches"][0]
        if azione == "cancellazione":
            partita["result"] = "1-0"
        elif azione != "pianificazione creata":
            partita.update(is_scheduled=True, schedule_info=dict(PIANIFICAZIONE_DI_PRIMA))
        aperto = self._rinominato(rounds=torneo["rounds"])
        chieste = []

        def dettagli(existing_details=None):
            chieste.append(existing_details)
            return dict(PIANIFICAZIONE_NUOVA)

        monkeypatch.setattr(ui, "input_schedule_details", dettagli)
        # INVIO apre il torneo; poi l'azione, con la sua conferma se la
        # chiede; INVIO vuoto chiude i risultati, e No a continuare.
        tasti, conferme = {
            "ritiro": (["", "r", "1", ""], [True, False]),
            "cancellazione": (["", "cancella", "1", ""], [True, False]),
            "pianificazione creata": (["", "1", "p", ""], [False]),
            "pianificazione modificata": (["", "1", "p", "m", ""], [False]),
            "pianificazione rimossa": (["", "1", "p", "r", ""], [True, False]),
        }[azione]
        monkeypatch.chdir(tmp_path)
        copione = Copione(monkeypatch, tasti=tasti, conferme=conferme)
        guida = TournamentController(_adattatore(copione))
        guida._select_or_create_tournament()
        # Il file aperto com'e' quando il controller salva la prima volta,
        # cioe' come lo ha lasciato ui.update_match_result.
        prima_del_controller = []
        salva = guida._save_state

        def save_state(*a, **k):
            if not prima_del_controller:
                prima_del_controller.append(self._leggi(aperto))
            return salva(*a, **k)

        monkeypatch.setattr(guida, "_save_state", save_state)

        guida._main_loop()

        assert copione.tasti == [] and copione.conferme == []
        assert guida.active_filename == aperto
        assert self._tornei() == ["Tornello - Prova_stessa_data.json"]
        for salvato in (prima_del_controller[0], self._leggi(aperto)):
            assert salvato["name"] == "Corona"
            scacchiera_1 = salvato["rounds"][0]["matches"][0]
            if azione == "ritiro":
                assert [p["id"] for p in salvato["players"] if p.get("withdrawn")] == ["G1"]
            elif azione == "cancellazione":
                assert scacchiera_1["result"] is None
            elif azione == "pianificazione rimossa":
                assert scacchiera_1["is_scheduled"] is False and "schedule_info" not in scacchiera_1
            else:
                assert (scacchiera_1["is_scheduled"], scacchiera_1["schedule_info"]) == (True, PIANIFICAZIONE_NUOVA)
        attese = {"pianificazione creata": [None], "pianificazione modificata": [PIANIFICAZIONE_DI_PRIMA]}
        assert chieste == attese.get(azione, [])

    def test_la_ripresa_di_un_torneo_rinominato_resta_nel_suo_file(self, monkeypatch, muto, tmp_path):
        """Corona, in preparazione, rinominato dalla finestra, riprende la
        creazione in console: il turno 1 va nel file aperto, che il messaggio
        Torneo creato nomina con il percorso intero, e la sospensione se ne
        va. All'avvio dopo la console apre il torneo com'e', senza
        riprendere la creazione."""
        import ui
        from controller import TournamentController

        aperto = self._rinominato(rounds=[], current_round=0, creation_suspended=True)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(ui, "_conferma_lista_giocatori_torneo", lambda torneo, db: True)
        # INVIO apre il torneo; INVIO vuoto e c chiudono l'iscrizione
        # ripresa; poi il bye suggerito e la cartella proposta.
        copione = Copione(monkeypatch, tasti=["", "", "c"], conferme=[True, True])
        adattatore = _adattatore(copione)
        guida = TournamentController(adattatore)

        guida._select_or_create_tournament()

        assert copione.tasti == [] and copione.conferme == []
        assert any("Ripresa inserimento giocatori per 'Corona'" in m for m in adattatore.messaggi)
        assert guida.active_filename == aperto
        assert adattatore.messaggi[-1] == f"\nTorneo 'Corona' creato e Turno 1 generato. File: '{aperto}'"
        assert self._tornei() == ["Tornello - Prova_stessa_data.json"]
        salvato = self._leggi(aperto)
        assert "creation_suspended" not in salvato
        assert [r["round"] for r in salvato["rounds"]] == [1]
        prima = self._leggi(aperto)

        copione = Copione(monkeypatch, tasti=[""])
        adattatore = _adattatore(copione)
        guida = TournamentController(adattatore)
        guida._select_or_create_tournament()

        assert copione.domande == ["Vuoi caricare 'Corona'? (Premi INVIO per sì, o inserisci il nome di un NUOVO torneo da creare): : "]
        assert not any("Ripresa" in m or "sospesa" in m for m in adattatore.messaggi)
        assert [r.round for r in guida.tournament.rounds] == [1]
        assert self._leggi(aperto) == prima

    def test_la_sospensione_di_un_torneo_rinominato_resta_nel_suo_file(self, monkeypatch, muto, tmp_path, capsys):
        """Corona, in preparazione, rinominato dalla finestra, riprende la
        creazione in console e si sospende di nuovo con s: il torneo resta
        nel suo file, sospeso, e il messaggio lo nomina con il percorso
        intero."""
        from controller import TournamentController

        aperto = self._rinominato(rounds=[], current_round=0, creation_suspended=True, site="Prima")
        monkeypatch.chdir(tmp_path)
        # INVIO apre il torneo; INVIO vuoto e s sospendono l'iscrizione.
        copione = Copione(monkeypatch, tasti=["", "", "s"])
        guida = TournamentController(_adattatore(copione))

        with pytest.raises(SystemExit):
            guida._select_or_create_tournament()

        assert copione.tasti == []
        assert f"Torneo sospeso salvato in: '{aperto}'" in capsys.readouterr().out.splitlines()
        assert self._tornei() == ["Tornello - Prova_stessa_data.json"]
        salvato = self._leggi(aperto)
        assert (salvato["name"], salvato["creation_suspended"], salvato["rounds"]) == ("Corona", True, [])
        assert sorted(p["id"] for p in salvato["players"]) == sorted(ELO)


# I contenuti dei file che la console non apre, per TestIlFileCheNonSiApreInConsole.
FILE_CHE_NON_SI_APRONO = {
    "rovinato": b"{rotto",
    "non UTF-8": '{"name": "Città"}'.encode("latin-1"),
    "troppo annidato": b'{"name": "Rotto", "x": ' + b"[" * 200000 + b"]" * 200000 + b"}",
    # Una cartella con il nome del file di un torneo: aprirla da' l'errore
    # del sistema, PermissionError, di cui va soltanto la descrizione,
    # Permission denied, senza il numero e il percorso.
    "una cartella": None,
}


class TestIlFileCheNonSiApreInConsole:
    """10.19.42 (decisione di Gabriele del 7 novembre 2026). Un file di
    torneo che la console non apre, all'avvio, lo dice un messaggio, con il
    file e del motivo la sola descrizione, come Apertura non riuscita nella
    finestra: "Il file C:\\...\\Tornello - Rotto.json non si è potuto aprire:
    ..." Poi la console continua come per gli altri file che non si aprono:
    con il torneo che era l'unico, Errore fatale e la domanda Vuoi creare un
    nuovo torneo; con il torneo scelto dall'elenco, Errore nel caricamento
    del torneo e l'uscita; con la ripresa di una creazione sospesa, l'elenco
    dei tornei, come dopo un No. Fino alla 10.19.41, e gia' nella 10.0.0, un
    file che non e' UTF-8, o un json annidato oltre il limite di Python,
    fermava la console con un errore, e la ripresa si fermava anche con un
    file sparito mentre la domanda aspettava; per un json rovinato
    load_tournament stampava il testo intero dell'errore."""

    @staticmethod
    def _motivo(percorso):
        """Del motivo per cui il file non si apre la sola descrizione, come
        la da' Python aprendolo con json; per il json troppo annidato None,
        perche' il testo dice quanta memoria ha usato, e cambia."""
        import json

        try:
            with open(percorso, encoding="utf-8") as f:
                json.load(f)
        except RecursionError:
            return None
        except (OSError, ValueError) as errore:
            return (getattr(errore, "strerror", None) or str(errore)).rstrip(".")
        raise AssertionError("il file si apre")

    @staticmethod
    def _controlla_il_messaggio(messaggio, percorso, motivo):
        if motivo is None:
            assert messaggio.startswith(f"Il file {percorso} non si è potuto aprire: Stack overflow")
            assert messaggio.endswith(" while decoding a JSON array from a unicode string.")
        else:
            assert messaggio == f"Il file {percorso} non si è potuto aprire: {motivo}."

    @pytest.mark.parametrize("contenuto", list(FILE_CHE_NON_SI_APRONO))
    def test_l_unico_torneo_che_non_si_apre(self, monkeypatch, muto, tmp_path, capsys, contenuto):
        """L'unico torneo della cartella del programma non si apre: dopo
        INVIO il messaggio, poi Errore fatale e la domanda Vuoi creare un
        nuovo torneo; con No la console esce. Il file resta com'era."""
        import os

        import config
        from controller import TournamentController

        percorso = config.user_data_path("Tornello - Rotto.json")
        if FILE_CHE_NON_SI_APRONO[contenuto] is None:
            os.mkdir(percorso)
        else:
            with open(percorso, "wb") as f:
                f.write(FILE_CHE_NON_SI_APRONO[contenuto])
        motivo = self._motivo(percorso)
        monkeypatch.chdir(tmp_path)
        copione = Copione(monkeypatch, tasti=[""], conferme=[False])
        adattatore = _adattatore(copione)
        guida = TournamentController(adattatore)

        with pytest.raises(SystemExit) as uscita:
            guida._select_or_create_tournament()

        assert uscita.value.code == 0
        assert copione.tasti == [] and copione.conferme == []
        assert copione.domande[-1] == "Vuoi creare un nuovo torneo?"
        assert adattatore.messaggi[1:3] == ["\nTrovato un solo torneo esistente: 'Rotto' (File: Tornello - Rotto.json)", "Caricamento di 'Rotto'..."]
        self._controlla_il_messaggio(adattatore.messaggi[3], percorso, motivo)
        assert adattatore.messaggi[4:] == [f"Errore fatale nel caricamento del torneo '{percorso}'."]
        assert guida.tournament is None
        if FILE_CHE_NON_SI_APRONO[contenuto] is None:
            assert motivo == "Permission denied"
            assert os.listdir(percorso) == []
        else:
            with open(percorso, "rb") as f:
                assert f.read() == FILE_CHE_NON_SI_APRONO[contenuto]
        assert "Errore durante il caricamento del torneo" not in capsys.readouterr().out

    @pytest.mark.parametrize("cambio", ["sparito", "non UTF-8"])
    def test_la_ripresa_con_il_file_che_non_si_apre_piu(self, monkeypatch, muto, tmp_path, cambio):
        """Console_Prova, in preparazione, e Altro, avviato: mentre la
        domanda Vuoi riprendere la creazione aspetta, il file di
        Console_Prova sparisce, o diventa un file che non e' UTF-8. Dopo il
        Si' il messaggio, e poi l'elenco dei tornei, da cui si apre Altro."""
        import json
        import os

        import config
        from controller import TournamentController

        sospeso = _torneo_al_primo_turno().to_dict()
        sospeso.update(rounds=[], current_round=0, creation_suspended=True)
        percorso = config.user_data_path("Tornello - Console_Prova.json")
        with open(percorso, "w", encoding="utf-8") as f:
            json.dump(sospeso, f)
        altro = _torneo_al_primo_turno().to_dict()
        altro["name"] = "Altro"
        file_altro = config.user_data_path("Tornello - Altro.json")
        with open(file_altro, "w", encoding="utf-8") as f:
            json.dump(altro, f)
        monkeypatch.chdir(tmp_path)
        # Altro, scelto con il suo numero nell'elenco, nell'ordine della
        # cartella.
        import glob

        nomi = [os.path.basename(f) for f in glob.glob(config.user_data_path("Tornello - *.json"))]
        copione = Copione(monkeypatch, tasti=[str(nomi.index("Tornello - Altro.json") + 1)])
        adattatore = _adattatore(copione)

        def conferma(prompt, default=True):
            copione.domande.append(prompt)
            if cambio == "sparito":
                os.remove(percorso)
            else:
                with open(percorso, "wb") as f:
                    f.write(FILE_CHE_NON_SI_APRONO["non UTF-8"])
            return True

        adattatore.confirm = conferma
        guida = TournamentController(adattatore)

        guida._select_or_create_tournament()

        assert copione.tasti == []
        assert copione.domande == ["Vuoi riprendere la creazione di 'Console_Prova'?", "Scegli un torneo da caricare o creane uno nuovo (1-3): "]
        motivo = "No such file or directory" if cambio == "sparito" else self._motivo(percorso)
        indice = adattatore.messaggi.index(" - 'Console_Prova' (File: Tornello - Console_Prova.json)")
        assert adattatore.messaggi[indice + 1 :] == [f"Il file {percorso} non si è potuto aprire: {motivo}.", "Caricamento di 'Altro'..."]
        assert (guida.tournament.name, guida.active_filename) == ("Altro", file_altro)
        assert not any("Ripresa" in m for m in adattatore.messaggi)

    def test_il_torneo_scelto_che_non_si_apre_piu(self, monkeypatch, muto, tmp_path):
        """Alfa e Beta nella cartella del programma: mentre l'elenco aspetta
        la scelta, il file di Beta diventa un file che non e' UTF-8. Scelto
        Beta, il messaggio, poi Errore nel caricamento del torneo, e la
        console esce."""
        import json

        import config
        from controller import TournamentController

        percorsi = {}
        for nome in ("Alfa", "Beta"):
            torneo = _torneo_al_primo_turno().to_dict()
            torneo["name"] = nome
            percorsi[nome] = config.user_data_path(f"Tornello - {nome}.json")
            with open(percorsi[nome], "w", encoding="utf-8") as f:
                json.dump(torneo, f)
        monkeypatch.chdir(tmp_path)
        copione = Copione(monkeypatch, tasti=["2"])
        adattatore = _adattatore(copione)
        scelta = copione.input

        def input_che_rovina_beta(domanda=""):
            with open(percorsi["Beta"], "wb") as f:
                f.write(FILE_CHE_NON_SI_APRONO["non UTF-8"])
            return scelta(domanda)

        monkeypatch.setattr("builtins.input", input_che_rovina_beta)
        guida = TournamentController(adattatore)

        with pytest.raises(SystemExit) as uscita:
            guida._select_or_create_tournament()

        assert uscita.value.code == 1
        assert copione.tasti == []
        motivo = self._motivo(percorsi["Beta"])
        assert adattatore.messaggi[-3:] == ["Caricamento di 'Beta'...", f"Il file {percorsi['Beta']} non si è potuto aprire: {motivo}.", "Errore nel caricamento del torneo. Riprova."]
        assert guida.tournament is None
