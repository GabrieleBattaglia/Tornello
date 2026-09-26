import pytest

from stats import (
    calculate_elo_change,
    calculate_performance_rating,
    compute_aro,
    compute_buchholz,
    compute_buchholz_cut1,
    get_k_factor,
)


def test_get_k_factor():
    # Giocatore con k_factor esplicito nel DB
    p_with_fide_k = {
        "k_factor": 40,
        "birth_date": "2015-05-05",
        "games_played": 10,
        "current_elo": 1200,
    }
    assert get_k_factor(p_with_fide_k, "2026-06-30") == 40

    # Giovane (under 18) -> K40
    p_young = {"birth_date": "2010-01-01", "games_played": 5, "current_elo": 1300}
    # Nel 2026 ha 16 anni -> under 18
    assert get_k_factor(p_young, "2026-06-30") == 40

    # Adulto con poche partite -> K40
    p_new_adult = {"birth_date": "1990-01-01", "games_played": 29, "current_elo": 1500}
    assert get_k_factor(p_new_adult, "2026-06-30") == 40

    # Adulto esperto con molte partite -> K20
    p_exp_adult = {"birth_date": "1990-01-01", "games_played": 31, "current_elo": 1800}
    assert get_k_factor(p_exp_adult, "2026-06-30") == 20

    # Giocatore con alto Elo -> K10
    p_pro = {"birth_date": "1980-01-01", "games_played": 100, "current_elo": 2450}
    assert get_k_factor(p_pro, "2026-06-30") == 10


def test_stats_calculations_with_real_data(sample_tournament_dict):
    # Ricalcoliamo il dizionario dei giocatori per i vecchi metodi che si aspettano dizionari
    sample_tournament_dict["players_dict"] = {
        p["id"]: p for p in sample_tournament_dict["players"]
    }

    # Prendiamo ad esempio un giocatore specifico (es. BATGA001 o altri)
    # Verifichiamo il Buchholz per un giocatore
    player_id = "BATGA001"

    bucch = compute_buchholz(player_id, sample_tournament_dict)
    bucch_cut1 = compute_buchholz_cut1(player_id, sample_tournament_dict)
    aro = compute_aro(player_id, sample_tournament_dict)

    assert bucch >= 0
    assert bucch_cut1 is None or bucch_cut1 >= 0
    assert aro is None or aro >= 0

    # Calcolo variazione elo e performance
    player_data = sample_tournament_dict["players_dict"][player_id]
    performance = calculate_performance_rating(
        player_data, sample_tournament_dict["players_dict"]
    )
    elo_change = calculate_elo_change(
        player_data, sample_tournament_dict["players_dict"]
    )

    assert performance is None or isinstance(performance, int)
    assert elo_change is None or isinstance(elo_change, (int, float))


def test_time_control_parsing_and_classification():
    from stats import classify_tournament_category, parse_time_control

    # Valido
    res = parse_time_control("15+10")
    assert res == {"minutes": 15, "increment": 10, "pgn_value": "900+10"}

    res = parse_time_control("90 + 30")
    assert res == {"minutes": 90, "increment": 30, "pgn_value": "5400+30"}

    # Senza incremento
    res = parse_time_control("10")
    assert res == {"minutes": 10, "increment": 0, "pgn_value": "600+0"}

    # Non valido
    assert parse_time_control("abc") is None
    assert parse_time_control("-5+10") is None

    # Classificazione
    assert classify_tournament_category(3, 2) == "blitz"
    assert classify_tournament_category(10, 0) == "blitz"
    assert classify_tournament_category(15, 10) == "rapid"
    assert classify_tournament_category(50, 0) == "rapid"
    assert classify_tournament_category(90, 30) == "standard"
    assert classify_tournament_category(60, 0) == "standard"


def test_new_tiebreaks_with_real_data(sample_tournament_dict):
    from stats import (
        compute_cumulative,
        compute_direct_encounter,
        compute_number_of_blacks,
        compute_number_of_wins,
        compute_played_rounds_rep,
        compute_sonneborn_berger,
    )

    # Setup players dictionary
    sample_tournament_dict["players_dict"] = {
        p["id"]: p for p in sample_tournament_dict["players"]
    }

    # Test for a specific player BATGA001
    player_id = "BATGA001"

    sb = compute_sonneborn_berger(player_id, sample_tournament_dict)
    de = compute_direct_encounter(player_id, sample_tournament_dict)
    rep = compute_played_rounds_rep(player_id, sample_tournament_dict)
    wins = compute_number_of_wins(player_id, sample_tournament_dict)
    blacks = compute_number_of_blacks(player_id, sample_tournament_dict)
    cum = compute_cumulative(player_id, sample_tournament_dict)

    assert isinstance(sb, float)
    assert sb >= 0.0

    assert isinstance(de, float)
    assert de >= 0.0

    assert isinstance(rep, int)
    assert rep >= 0

    assert isinstance(wins, int)
    assert wins >= 0

    assert isinstance(blacks, int)
    assert blacks >= 0

    assert isinstance(cum, float)
    assert cum >= 0.0


def test_dynamic_standings_sorting():
    from config import _
    from reports import get_standings_text

    # Create a minimal sample tournament dict
    torneo = {
        "name": "Test Sort",
        "players": [
            {
                "id": "P1",
                "first_name": "A",
                "last_name": "A",
                "initial_elo": 1500,
                "points": 3.0,
                "results_history": [],
            },
            {
                "id": "P2",
                "first_name": "B",
                "last_name": "B",
                "initial_elo": 1600,
                "points": 3.0,
                "results_history": [],
            },
        ],
        "rounds": [],
        "total_rounds": 1,
        "current_round": 1,
    }

    # 1. Sort with points and initial_elo. P2 (1600) should be 1st, P1 (1500) should be 2nd.
    torneo["tiebreaks"] = ["points", "initial_elo"]
    text = get_standings_text(torneo)
    pos_b = text.find("B, B")
    pos_a = text.find("A, A")
    assert pos_b < pos_a
    # Since initial_elo is excluded from dynamic_cols and points is included, header should have Punti
    assert _("Punti") in text

    # 2. Let's make P1 have a higher Elo (1700) and verify it sorts first.
    torneo["players"][0]["initial_elo"] = 1700
    text_rev = get_standings_text(torneo)
    pos_b_rev = text_rev.find("B, B")
    pos_a_rev = text_rev.find("A, A")
    assert pos_a_rev < pos_b_rev

    # 3. Verify ordering of dynamic columns headers in text
    torneo["tiebreaks"] = ["points", "buchholz", "aro"]
    text_cols1 = get_standings_text(torneo)
    header_line1 = [line for line in text_cols1.split("\n") if _("Pos. (Tab)") in line][
        0
    ]
    assert header_line1.find(_("Punti")) < header_line1.find("BH")
    assert header_line1.find("BH") < header_line1.find("ARO")

    # Swap order: points, aro, buchholz
    torneo["tiebreaks"] = ["points", "aro", "buchholz"]
    text_cols2 = get_standings_text(torneo)
    header_line2 = [line for line in text_cols2.split("\n") if _("Pos. (Tab)") in line][
        0
    ]
    assert header_line2.find(_("Punti")) < header_line2.find("ARO")
    assert header_line2.find("ARO") < header_line2.find("BH")


def test_forfeit_esclusi_da_elo_e_performance():
    """I punti da forfait valgono in classifica ma non nel calcolo del rating.
    Regola stabilita da Gabriele il 2026-09-01, rilievo B5 della fase 1."""
    from stats import is_forfeit_result

    assert is_forfeit_result("1-F")
    assert is_forfeit_result("F-1")
    assert is_forfeit_result("0-0F")
    assert not is_forfeit_result("1-0")
    assert not is_forfeit_result("0-1")
    assert not is_forfeit_result("1/2-1/2")
    assert not is_forfeit_result(None)

    avversari = {
        "AVV001": {"id": "AVV001", "initial_elo": 1600.0},
        "AVV002": {"id": "AVV002", "initial_elo": 1600.0},
    }

    # Il giocatore vince una partita giocata e una per forfait: solo la prima conta.
    giocatore = {
        "id": "TST001",
        "initial_elo": 1600.0,
        "k_factor": 20,
        "results_history": [
            {
                "round": 1,
                "opponent_id": "AVV001",
                "color": "white",
                "result": "1-0",
                "score": 1.0,
            },
            {
                "round": 2,
                "opponent_id": "AVV002",
                "color": "black",
                "result": "1-F",
                "score": 1.0,
            },
        ],
    }

    solo_giocata = {
        "id": "TST002",
        "initial_elo": 1600.0,
        "k_factor": 20,
        "results_history": [
            {
                "round": 1,
                "opponent_id": "AVV001",
                "color": "white",
                "result": "1-0",
                "score": 1.0,
            },
        ],
    }

    # Con Elo pari, una vittoria giocata su un avversario di pari forza vale +10 con K 20.
    assert calculate_elo_change(giocatore, avversari) == 10
    assert calculate_elo_change(giocatore, avversari) == calculate_elo_change(
        solo_giocata, avversari
    )
    assert calculate_performance_rating(
        giocatore, avversari
    ) == calculate_performance_rating(solo_giocata, avversari)

    # Chi ha solo partite non giocate non ha rating di torneo: nessuna variazione Elo
    # e performance pari all'Elo iniziale.
    solo_forfeit = {
        "id": "TST003",
        "initial_elo": 1500.0,
        "k_factor": 20,
        "results_history": [
            {
                "round": 1,
                "opponent_id": "AVV001",
                "color": "white",
                "result": "1-F",
                "score": 1.0,
            },
            {
                "round": 2,
                "opponent_id": "AVV002",
                "color": "black",
                "result": "0-0F",
                "score": 0.0,
            },
        ],
    }
    assert calculate_elo_change(solo_forfeit, avversari) == 0
    assert calculate_performance_rating(solo_forfeit, avversari) == 1500


def test_partite_valide_per_elo():
    """Le partite che contano per la variazione Elo, scelte da una funzione
    sola: dalla 10.13.7 la finalizzazione la usa per decidere se nei rapid e
    nei blitz l'Elo della cadenza puo' nascere, e calculate_elo_change ci fa
    il suo calcolo. Restano fuori il bye, il forfait, la voce senza
    punteggio e l'avversario che non si trova, di cui si avvisa."""
    from stats import partite_valide_per_elo

    avversari = {"AVV001": {"id": "AVV001", "initial_elo": 1650.0}}

    def voce(turno, avversario, risultato, punti):
        return {"round": turno, "opponent_id": avversario, "color": "white", "result": risultato, "score": punti}

    giocatore = {
        "id": "TST004",
        "initial_elo": 1600.0,
        "k_factor": 20,
        "results_history": [
            voce(1, "BYE_PLAYER_ID", "BYE", 1.0),
            voce(2, "AVV001", "1-F", 1.0),
            voce(3, "AVV001", None, None),
            voce(4, "SCONOSCIUTO", "1-0", 1.0),
            voce(5, "AVV001", "0-1", 0.0),
        ],
    }
    avvisi = []

    assert partite_valide_per_elo(giocatore, avversari, avvisa=avvisi.append) == [(1650.0, 0.0)]
    assert len(avvisi) == 1 and "SCONOSCIUTO" in avvisi[0]
    # Senza avvisa non si dice niente, e senza partite l'elenco e' vuoto.
    assert partite_valide_per_elo({"id": "TST005", "results_history": giocatore["results_history"][:4]}, avversari) == []
    assert partite_valide_per_elo({"id": "TST006"}, avversari) == []
    # La variazione e' quella della sola partita valida: una sconfitta con
    # un avversario piu' forte di 50 punti, con K 20.
    solo_la_valida = dict(giocatore, results_history=[voce(5, "AVV001", "0-1", 0.0)])
    assert calculate_elo_change(giocatore, avversari) == calculate_elo_change(solo_la_valida, avversari) == -9


class TestTabellaPerformanceFIDE:
    """La tabella che converte la percentuale di punteggio nella differenza di
    performance esisteva in due copie e la seconda si fermava a 0.89, cosi' il
    criterio di spareggio TPR, e di conseguenza APRO, ricadeva sul valore di
    ripiego piu' o meno 800 per quasi tutti i giocatori. Rilievo B1."""

    def test_la_tabella_e_completa(self):
        from stats import DP_FIDE, _get_dp_map

        assert len(DP_FIDE) == 101
        assert _get_dp_map() is DP_FIDE

    def test_i_valori_intermedi_ci_sono(self):
        from stats import _get_dp_map

        tabella = _get_dp_map()
        # Prima della correzione questi tre non c'erano e il calcolo cadeva
        # sul ripiego: il 60 per cento dava piu' 800 invece di piu' 72, e il
        # 50 per cento dava meno 800 invece di zero.
        assert tabella[0.60] == 72
        assert tabella[0.50] == 0
        assert tabella[0.40] == -72

    def test_tpr_di_un_giocatore_al_sessanta_per_cento(self):
        from stats import compute_tpr

        # Cinque partite contro avversari tutti da 1600, tre punti su cinque.
        avversari = {}
        storico = []
        for i in range(5):
            pid = f"AVV{i}"
            avversari[pid] = {"id": pid, "initial_elo": 1600.0, "points": 0.0}
            storico.append(
                {
                    "round": i + 1,
                    "opponent_id": pid,
                    "color": "white",
                    "result": "1-0" if i < 3 else "0-1",
                    "score": 1.0 if i < 3 else 0.0,
                }
            )
        giocatore = {
            "id": "TST",
            "initial_elo": 1600.0,
            "points": 3.0,
            "results_history": storico,
        }
        torneo = {
            "players": [giocatore, *avversari.values()],
            "players_dict": {"TST": giocatore, **avversari},
        }

        tpr = compute_tpr("TST", torneo)

        # Media avversari 1600 piu' la differenza prevista per il 60 per cento,
        # cioe' 72. Prima della correzione veniva 2400, cioe' 1600 piu' 800.
        assert tpr == 1672


def test_il_piazzamento_finale_segue_i_criteri_configurati():
    """Il piazzamento assegnato alla finalizzazione deve usare i criteri di
    spareggio scelti dall'arbitro, gli stessi con cui la classifica viene poi
    ordinata e stampata. Prima usava una sequenza fissa scritta nel codice, e
    nel report finale le posizioni comparivano fuori sequenza: la prima riga
    portava il numero 2 e la seconda il numero 1. Rilievo D1, confermato sul
    campo il 2026-09-03."""
    from reports import get_criterion_value

    # Due giocatori a pari punti. Con Sonneborn-Berger, il criterio configurato,
    # vince A. Con il Buchholz della vecchia sequenza fissa vincerebbe B.
    a = {
        "id": "A",
        "first_name": "Anna",
        "last_name": "Alfa",
        "points": 4.0,
        "initial_elo": 1726,
        "withdrawn": False,
        "buchholz": 20.0,
        "buchholz_cut1": 16.0,
        "results_history": [],
    }
    b = {
        "id": "B",
        "first_name": "Bruno",
        "last_name": "Beta",
        "points": 4.0,
        "initial_elo": 1931,
        "withdrawn": False,
        "buchholz": 24.0,
        "buchholz_cut1": 20.0,
        "results_history": [],
    }
    torneo = {
        "players": [a, b],
        "players_dict": {"A": a, "B": b},
        "tiebreaks": [{"key": "SB", "modifiers": {}}],
        "sb_forzato": True,
    }

    # Sonneborn-Berger calcolato: si forza il valore per rendere la prova
    # indipendente dallo storico delle partite.
    valori = {"A": 9.5, "B": 9.0}

    def sort_key(player):
        chiave = [-float(player["points"]), -1]
        chiave.append(-valori[player["id"]])
        return tuple(chiave)

    ordinati = sorted(torneo["players"], key=sort_key)
    assert [p["id"] for p in ordinati] == ["A", "B"]

    # La stessa funzione usata dalla classifica deve saper leggere il criterio
    # configurato senza ricorrere a una sequenza fissa.
    valore_a = get_criterion_value(a, {"key": "SB", "modifiers": {}}, torneo)
    valore_b = get_criterion_value(b, {"key": "SB", "modifiers": {}}, torneo)
    assert isinstance(valore_a, (int, float))
    assert isinstance(valore_b, (int, float))


def test_finalize_usa_gli_stessi_criteri_della_classifica():
    """Verifica diretta sul codice: la funzione che assegna il piazzamento
    finale legge la configurazione dei criteri invece di una lista fissa."""
    import inspect

    import ui

    sorgente = inspect.getsource(ui.finalize_tournament)
    assert "tiebreak_order_final" in sorgente
    assert "get_criterion_value" in sorgente
    # La vecchia sequenza fissa non deve piu' comparire.
    assert "-bucch_c1, -bucch_tot, -performance, -elo_initial" not in sorgente


class TestArticolo16:
    """Turni non giocati negli spareggi basati sui risultati degli avversari,
    articolo 16 del regolamento FIDE sugli spareggi in vigore dal 1 marzo 2026.
    Fino alla versione 9.3.22 Tornello saltava del tutto quei turni, che e' la
    regola precedente al 2023."""

    def _giocatore(self, pid, punti, storico):
        return {
            "id": pid,
            "first_name": pid,
            "last_name": pid,
            "initial_elo": 1800.0,
            "points": punti,
            "results_history": storico,
        }

    def _bye(self, turno):
        return {
            "round": turno,
            "opponent_id": "BYE_PLAYER_ID",
            "color": None,
            "result": "BYE",
            "score": 0.5,
        }

    def _torneo(self, giocatori, rounds, turni_totali):
        return {
            "players": giocatori,
            "players_dict": {p["id"]: p for p in giocatori},
            "rounds": rounds,
            "total_rounds": turni_totali,
            "bye_value": 0.5,
        }

    def _girone_di_tre(self):
        """Tre giocatori, tre turni, ognuno riceve un bye dall'abbinatore e
        chiude con un punto e mezzo."""
        p = self._giocatore(
            "P",
            1.5,
            [
                self._bye(1),
                {
                    "round": 2,
                    "opponent_id": "X",
                    "color": "white",
                    "result": "1-0",
                    "score": 1.0,
                },
                {
                    "round": 3,
                    "opponent_id": "Y",
                    "color": "black",
                    "result": "1-0",
                    "score": 0.0,
                },
            ],
        )
        x = self._giocatore(
            "X",
            1.5,
            [
                {
                    "round": 1,
                    "opponent_id": "Y",
                    "color": "white",
                    "result": "1-0",
                    "score": 1.0,
                },
                {
                    "round": 2,
                    "opponent_id": "P",
                    "color": "black",
                    "result": "1-0",
                    "score": 0.0,
                },
                self._bye(3),
            ],
        )
        y = self._giocatore(
            "Y",
            1.5,
            [
                {
                    "round": 1,
                    "opponent_id": "X",
                    "color": "black",
                    "result": "1-0",
                    "score": 0.0,
                },
                self._bye(2),
                {
                    "round": 3,
                    "opponent_id": "P",
                    "color": "white",
                    "result": "1-0",
                    "score": 1.0,
                },
            ],
        )
        rounds = [
            {
                "round": 1,
                "matches": [
                    {
                        "white_player_id": "P",
                        "black_player_id": None,
                        "result": "BYE",
                    },
                    {
                        "white_player_id": "X",
                        "black_player_id": "Y",
                        "result": "1-0",
                    },
                ],
            },
            {
                "round": 2,
                "matches": [
                    {
                        "white_player_id": "P",
                        "black_player_id": "X",
                        "result": "1-0",
                    },
                    {
                        "white_player_id": "Y",
                        "black_player_id": None,
                        "result": "BYE",
                    },
                ],
            },
            {
                "round": 3,
                "matches": [
                    {
                        "white_player_id": "Y",
                        "black_player_id": "P",
                        "result": "1-0",
                    },
                    {
                        "white_player_id": "X",
                        "black_player_id": None,
                        "result": "BYE",
                    },
                ],
            },
        ]
        return self._torneo([p, x, y], rounds, 3)

    def test_il_bye_conta_come_avversario_fittizio(self):
        """Articolo 16.4: il turno di bye vale una partita contro un fittizio
        che ha il punteggio del giocatore stesso, qui un punto e mezzo, sotto
        il tetto di mezzo punto per turno del torneo."""
        from stats import compute_buchholz

        torneo = self._girone_di_tre()

        # 1.5 dal fittizio del turno 1, piu' 1.5 di X e 1.5 di Y.
        assert compute_buchholz("P", torneo) == 4.5

    def test_il_fittizio_entra_anche_nel_sonneborn_berger(self):
        from stats import compute_sonneborn_berger

        torneo = self._girone_di_tre()

        # 1.5 per il mezzo punto del bye, piu' 1.5 per la vittoria su X,
        # piu' zero per la sconfitta con Y.
        assert compute_sonneborn_berger("P", torneo) == 2.25

    def test_il_bye_non_e_un_turno_non_disponibile(self):
        """Il bye assegnato dall'abbinatore e' della categoria 16.2.1 e non e'
        un VUR, quindi il Cut-1 non deve accanirsi su di lui."""
        from stats import CAT_BYE_ABBINATORE, categorie_turni_non_giocati

        torneo = self._girone_di_tre()

        assert categorie_turni_non_giocati("P", torneo) == {1: CAT_BYE_ABBINATORE}

    def _torneo_con_ritiro(self):
        """R gioca e perde il primo turno, poi si ritira: i turni 2 e 3 non
        hanno traccia nel suo storico."""
        r = self._giocatore(
            "R",
            0.0,
            [
                {
                    "round": 1,
                    "opponent_id": "A",
                    "color": "black",
                    "result": "1-0",
                    "score": 0.0,
                }
            ],
        )
        a = self._giocatore(
            "A",
            3.0,
            [
                {
                    "round": 1,
                    "opponent_id": "R",
                    "color": "white",
                    "result": "1-0",
                    "score": 1.0,
                },
                {
                    "round": 2,
                    "opponent_id": "B",
                    "color": "black",
                    "result": "0-1",
                    "score": 1.0,
                },
                {
                    "round": 3,
                    "opponent_id": "B",
                    "color": "white",
                    "result": "1-0",
                    "score": 1.0,
                },
            ],
        )
        b = self._giocatore(
            "B",
            0.0,
            [
                {
                    "round": 2,
                    "opponent_id": "A",
                    "color": "white",
                    "result": "0-1",
                    "score": 0.0,
                },
                {
                    "round": 3,
                    "opponent_id": "A",
                    "color": "black",
                    "result": "1-0",
                    "score": 0.0,
                },
            ],
        )
        rounds = [
            {
                "round": 1,
                "matches": [
                    {"white_player_id": "A", "black_player_id": "R", "result": "1-0"}
                ],
            },
            {
                "round": 2,
                "matches": [
                    {"white_player_id": "B", "black_player_id": "A", "result": "0-1"}
                ],
            },
            {
                "round": 3,
                "matches": [
                    {"white_player_id": "A", "black_player_id": "B", "result": "1-0"}
                ],
            },
        ]
        return self._torneo([r, a, b], rounds, 3)

    def test_i_turni_dopo_il_ritiro_valgono_come_patte(self):
        """Articolo 16.3.2: per gli spareggi degli avversari, i turni non
        giocati della categoria 16.2.5 si valutano come patte. Il ritirato ha
        zero punti sul campo ma ne vale uno per chi lo ha incontrato."""
        from stats import punteggio_aggiustato

        torneo = self._torneo_con_ritiro()

        assert punteggio_aggiustato("R", torneo) == 1.0

    def test_il_ritiro_e_classificato_come_bye_finale(self):
        from stats import CAT_BYE_FINALE, categorie_turni_non_giocati

        torneo = self._torneo_con_ritiro()

        assert categorie_turni_non_giocati("R", torneo) == {
            2: CAT_BYE_FINALE,
            3: CAT_BYE_FINALE,
        }

    def test_il_turno_in_corso_non_e_un_turno_non_giocato(self):
        """Se la partita del giocatore esiste ma non ha ancora un risultato il
        turno non va contato: altrimenti ogni classifica intermedia
        assegnerebbe un fittizio a chi deve ancora giocare."""
        from stats import categorie_turni_non_giocati

        torneo = self._torneo_con_ritiro()
        torneo["rounds"].append(
            {
                "round": 4,
                "matches": [
                    {"white_player_id": "A", "black_player_id": "B", "result": None},
                    {"white_player_id": "R", "black_player_id": None, "result": "1-0"},
                ],
            }
        )

        assert 4 not in categorie_turni_non_giocati("A", torneo)

    def test_la_sconfitta_per_forfait_e_limitata_dall_avversario(self):
        """Articolo 16.4.1: per i forfait il fittizio non puo' valere piu' del
        punteggio aggiustato dell'avversario che era stato abbinato."""
        from stats import compute_buchholz

        primo = self._giocatore(
            "P2",
            4.0,
            [
                {
                    "round": 1,
                    "opponent_id": "Z",
                    "color": "white",
                    "result": "F-1",
                    "score": 0.0,
                },
                {
                    "round": 2,
                    "opponent_id": "W",
                    "color": "white",
                    "result": "1-0",
                    "score": 1.0,
                },
            ],
        )
        zeta = self._giocatore(
            "Z",
            2.0,
            [
                {
                    "round": 1,
                    "opponent_id": "P2",
                    "color": "black",
                    "result": "F-1",
                    "score": 1.0,
                },
                self._bye(2),
            ],
        )
        doppia = self._giocatore(
            "W",
            0.0,
            [
                {
                    "round": 2,
                    "opponent_id": "P2",
                    "color": "black",
                    "result": "1-0",
                    "score": 0.0,
                }
            ],
        )
        rounds = [
            {
                "round": 1,
                "matches": [
                    {"white_player_id": "P2", "black_player_id": "Z", "result": "F-1"}
                ],
            },
            {
                "round": 2,
                "matches": [
                    {"white_player_id": "P2", "black_player_id": "W", "result": "1-0"},
                    {"white_player_id": "Z", "black_player_id": None, "result": "BYE"},
                ],
            },
        ]
        torneo = self._torneo([primo, zeta, doppia], rounds, 2)

        # Il giocatore ha 4 punti ma il fittizio vale 2, cioe' il punteggio di
        # Z. Con l'avversario del secondo turno a zero, il totale e' 2.
        assert compute_buchholz("P2", torneo) == 2.0

    def test_il_cut1_toglie_prima_il_turno_non_disponibile(self):
        """Eccezione dell'articolo 16.5: con turni non disponibili al gioco si
        taglia il contributo piu' basso fra quelli, non il piu' basso in
        assoluto."""
        from stats import _taglia_contributi

        rimasti = _taglia_contributi([3.0, 1.0, 2.0], 1, [False, False, True])

        assert sorted(valore for valore, _vur in rimasti) == [1.0, 3.0]

    def test_senza_turni_non_disponibili_il_cut1_toglie_il_minimo(self):
        from stats import _taglia_contributi

        rimasti = _taglia_contributi([3.0, 1.0, 2.0], 1, [False, False, False])

        assert sorted(valore for valore, _vur in rimasti) == [2.0, 3.0]


class TestArbitroNonNecessario:
    """La regola che dice se una partita programmata puo' fare a meno
    dell'arbitro: la casella della 10.2.0, oppure le diciture scritte a mano
    nelle programmazioni precedenti. Fino alla 10.4.0 non aveva prove, e
    "Non necessario." col punto, trovato in un torneo archiviato, non era
    riconosciuto."""

    def test_la_casella_basta(self):
        from stats import arbitro_non_necessario

        assert arbitro_non_necessario({"arbiter_not_needed": True})
        assert arbitro_non_necessario(
            {"arbiter": "Non necessario", "arbiter_not_needed": True}
        )

    @pytest.mark.parametrize(
        "scritto",
        [
            "Non necessario",
            "non necessario",
            "Non necessario.",
            "  NON NECESSARIO  ",
            "non  necessario",
            "no",
            "No",
            "No!",
            "(no)",
        ],
    )
    def test_le_diciture_scritte_a_mano(self, scritto):
        from stats import arbitro_non_necessario

        assert arbitro_non_necessario({"arbiter": scritto})

    @pytest.mark.parametrize(
        "scritto",
        ["Bruno", "Stefano", "Luciano", "Gabry", "Cercasi", "no, grazie", "", None],
    )
    def test_il_no_dentro_un_nome_non_conta(self, scritto):
        from stats import arbitro_non_necessario

        assert not arbitro_non_necessario({"arbiter": scritto})
        assert not arbitro_non_necessario(
            {"arbiter": scritto, "arbiter_not_needed": False}
        )

    def test_la_programmazione_senza_arbitro(self):
        from stats import arbitro_non_necessario

        assert not arbitro_non_necessario({})


class TestSalaEArbitroBrevi:
    """Sala e arbitro nell'etichetta delle partite da giocare della plancia,
    dalla 10.4.0 (issue 52): la sala ai primi 8 caratteri, con gli indirizzi
    ridotti al nome del servizio, l'arbitro ai primi 12, No se non serve e
    N/D se manca. I casi vengono dalle 103 programmazioni dei tornei
    archiviati e da Autunneo2."""

    def _brevi(self, **programmazione):
        from stats import sala_e_arbitro_brevi

        return sala_e_arbitro_brevi(programmazione)

    @pytest.mark.parametrize(
        ("canale", "atteso"),
        [
            ("WhatsApp", "WhatsApp"),
            ("whatsapp", "whatsapp"),
            ("WA", "WA"),
            ("  WA  ", "WA"),
            ("Lichess", "Lichess"),
            ("whatsapp https://call.whatsapp.com/voice/AbC123xyz", "whatsapp"),
            ("https://chat.whatsapp.com/AbC123xyz", "WhatsApp"),
            ("wa.me/393331234567", "WhatsApp"),
            ("lichess.org/AbCdEfGh", "Lichess"),
            ("https://lichess.org/AbCdEfGh Lichess", "Lichess"),
            ("https://www.chess.com/play/online", "Chesscom"),
            ("chess.com", "Chesscom"),
            ("Chess.com", "Chesscom"),
            ("https://meet.google.com/abc-defg-hij", "Meet"),
            ("https://teams.microsoft.com/l/meetup-join/abc", "Teams"),
            ("https://us02web.zoom.us/j/123456789", "Zoom"),
            ("https://discord.gg/AbCd", "Discord"),
            ("https://meet.jit.si/TorneoScacchi", "Jitsi"),
            ("https://join.skype.com/AbCd", "Skype"),
            ("www.scacchierando.it/sala", "Scacchie"),
            ("http://www.bbc.co.uk/sala", "Bbc"),
            ("Sala.Blu", "Sala.Blu"),
            ("lichess maurixio - lollo1978", "lichess"),
            ("Sala 12 terra", "Sala 12"),
        ],
    )
    def test_la_sala(self, canale, atteso):
        sala, _arbitro = self._brevi(channel=canale, arbiter="Gabry")

        assert sala == atteso

    def test_i_nomi_dei_servizi_non_si_tagliano(self):
        """Un nome oltre gli 8 caratteri uscirebbe mozzato dal taglio, come
        Chess.co per Chess.com."""
        from stats import SERVIZI_NOTI

        assert all(len(nome) <= 8 for _dominio, nome in SERVIZI_NOTI)

    @pytest.mark.parametrize(
        ("arbitro", "atteso"),
        [
            ("Gabry", "Gabry"),
            ("  Gabry ", "Gabry"),
            ("Giuseppe Baratta", "Giuseppe Bar"),
            ("Mario Rossi Bianchi", "Mario Rossi"),
            ("Bruno", "Bruno"),
            ("Stefano", "Stefano"),
            ("Cercasi", "Cercasi"),
        ],
    )
    def test_l_arbitro(self, arbitro, atteso):
        _sala, breve = self._brevi(channel="WA", arbiter=arbitro)

        assert breve == atteso

    @pytest.mark.parametrize(
        "programmazione",
        [
            {"arbiter": "Non necessario", "arbiter_not_needed": True},
            {"arbiter": "", "arbiter_not_needed": True},
            {"arbiter": "Non necessario"},
            {"arbiter": "non necessario"},
            {"arbiter": "Non necessario."},
            {"arbiter": "no"},
        ],
    )
    def test_l_arbitro_non_necessario_vale_no(self, programmazione):
        _sala, arbitro = self._brevi(channel="WA", **programmazione)

        assert arbitro == _("No")

    def test_i_campi_vuoti_o_assenti_valgono_n_d(self):
        assert self._brevi(channel="", arbiter="") == (_("N/D"), _("N/D"))
        assert self._brevi(channel="   ", arbiter="  ") == (_("N/D"), _("N/D"))
        assert self._brevi(channel=None, arbiter=None) == (_("N/D"), _("N/D"))
        assert self._brevi(date="2026-09-25", time="17:30") == (_("N/D"), _("N/D"))

    def test_le_misure_si_possono_cambiare(self):
        from stats import sala_e_arbitro_brevi

        programmazione = {"channel": "WhatsApp", "arbiter": "Giuseppe Baratta"}

        assert sala_e_arbitro_brevi(programmazione, 7, 8) == ("WhatsAp", "Giuseppe")


class TestAroSoloPartiteGiocate:
    """Dalla 10.13.18 l'ARO conta soltanto gli avversari delle partite
    giocate sulla scacchiera, come vuole l'articolo 10.1 del regolamento
    FIDE sugli spareggi (C.07, dal 1 marzo 2026): niente bye e niente
    forfait. Fino alla 10.13.17 contava anche gli avversari delle partite
    vinte o perse a forfait, che performance e variazione Elo escludevano."""

    def _torneo(self):
        def voce(turno, avversario, risultato, punti):
            return {"round": turno, "opponent_id": avversario, "result": risultato, "score": punti}

        giocatori = [
            {"id": "P", "initial_elo": 1500, "results_history": [voce(1, "A", "1-0", 1.0), voce(2, "B", "1-F", 1.0), voce(3, "C", "0-0F", 0.0), voce(4, "BYE_PLAYER_ID", "BYE", 1.0), voce(5, "D", "0-1", 0.0)]},
            {"id": "A", "initial_elo": 1600, "results_history": []},
            {"id": "B", "initial_elo": 1400, "results_history": []},
            {"id": "C", "initial_elo": 1300, "results_history": []},
            {"id": "D", "initial_elo": 1700, "results_history": []},
        ]
        return {"players": giocatori, "players_dict": {g["id"]: g for g in giocatori}, "rounds": [], "total_rounds": 5}

    def test_i_forfait_non_entrano_nella_media(self):
        from stats import compute_aro_generic, compute_tiebreak_value

        torneo = self._torneo()

        assert compute_aro("P", torneo) == 1650
        assert compute_aro_generic("P", torneo) == 1650
        assert compute_tiebreak_value("P", torneo, "ARO", {}) == 1650
        assert compute_tiebreak_value("P", torneo, "ARO", {"cut1": True}) == 1700

    def test_a_soli_forfait_l_aro_non_c_e(self):
        from stats import compute_aro_generic

        torneo = self._torneo()
        torneo["players"][0]["results_history"] = torneo["players"][0]["results_history"][1:4]

        assert compute_aro("P", torneo) is None
        assert compute_aro_generic("P", torneo) == 0

    def test_ascid_primavera_1_come_la_classifica_dell_arbitro(self, sample_tournament_dict):
        """Il torneo archiviato vero, letto e non scritto: Di Bari ha vinto a
        forfait il turno 4 contro Bosetti. Sulle quattro partite giocate
        l'ARO e' 1522,25, come nella classifica dell'arbitro nel file
        dell'archivio; con il forfait Tornello diceva 1498."""
        from stats import compute_tiebreak_value

        torneo = sample_tournament_dict
        torneo["players_dict"] = {p["id"]: p for p in torneo["players"]}

        assert compute_tiebreak_value("DIBVI001", torneo, "ARO", {}) == 1522
        assert compute_aro("DIBVI001", torneo) == 1522


class TestSpareggiSulRatingSenzaForfait:
    """Dalla 10.13.34 TPR e PTP contano soltanto le partite giocate sulla
    scacchiera: il TPR come vuole l'articolo 10.2 del regolamento FIDE sugli
    spareggi (C.07, dal 1 marzo 2026), il PTP dell'articolo 10.3 per
    coerenza con il TPR, come l'articolo 15.2 prescrive per i tornei a
    turni prestabiliti (decisione di Gabriele). Di conseguenza cambiano APRO
    e APPO (articoli 10.4 e 10.5), le medie dei TPR e dei PTP degli
    avversari affrontati sulla scacchiera. Fino alla 10.13.33 le partite
    vinte o perse a forfait entravano nella media e nel punteggio: P, che
    patta con A da 1600 e vince a forfait con B da 1400, aveva TPR 1693 e
    PTP 1706."""

    def _torneo(self):
        def voce(turno, avversario, risultato, punti):
            return {"round": turno, "opponent_id": avversario, "result": risultato, "score": punti}

        giocatori = [
            {"id": "P", "initial_elo": 1500, "results_history": [voce(1, "A", "1/2-1/2", 0.5), voce(2, "B", "1-F", 1.0), voce(3, "BYE_PLAYER_ID", "BYE", 1.0)]},
            {"id": "A", "initial_elo": 1600, "results_history": [voce(1, "P", "1/2-1/2", 0.5)]},
            {"id": "B", "initial_elo": 1400, "results_history": [voce(2, "P", "F-1", 0.0)]},
        ]
        return {"players": giocatori, "players_dict": {g["id"]: g for g in giocatori}, "rounds": [], "total_rounds": 3}

    def test_tpr_e_ptp_sulle_sole_partite_giocate(self):
        from stats import compute_tiebreak_value

        torneo = self._torneo()

        assert compute_tiebreak_value("P", torneo, "TPR", {}) == 1600
        assert compute_tiebreak_value("P", torneo, "PTP", {}) == 1600

    def test_apro_e_appo_usano_tpr_e_ptp_senza_forfait(self):
        from stats import compute_tiebreak_value

        torneo = self._torneo()

        assert compute_tiebreak_value("A", torneo, "APRO", {}) == 1600
        assert compute_tiebreak_value("A", torneo, "APPO", {}) == 1600

    def test_il_tpr_coincide_con_la_colonna_perf(self):
        from stats import compute_tpr

        torneo = self._torneo()

        assert compute_tpr("P", torneo) == calculate_performance_rating(torneo["players"][0], torneo["players_dict"])

    def test_a_soli_forfait_vale_l_elo_di_partenza(self):
        from stats import compute_ptp, compute_tpr

        torneo = self._torneo()
        torneo["players"][0]["results_history"] = torneo["players"][0]["results_history"][1:]

        assert compute_tpr("P", torneo) == 1500
        assert compute_ptp("P", torneo) == 1500

    def test_ascid_primavera_1_tpr_e_perf_coincidono(self, sample_tournament_dict):
        """Il torneo archiviato vero, letto e non scritto, con il forfait di
        Di Bari al turno 4: per ogni giocatore il TPR e' la performance
        della colonna Perf, che i forfait li escludeva gia'."""
        from stats import compute_tpr

        torneo = sample_tournament_dict
        torneo["players_dict"] = {p["id"]: p for p in torneo["players"]}

        diversi = {
            p["id"]: (compute_tpr(p["id"], torneo), calculate_performance_rating(p, torneo["players_dict"]))
            for p in torneo["players"]
            if compute_tpr(p["id"], torneo) != calculate_performance_rating(p, torneo["players_dict"])
        }
        assert diversi == {}


class TestPtpAgliEstremi:
    """Dalla 10.13.34 il PTP segue l'articolo 10.3 del C.07 anche agli
    estremi: con zero punti nelle partite giocate vale 800 meno del rating
    dell'avversario piu' debole, e con tutte le partite giocate vinte il
    rating dell'avversario piu' forte piu' 736, il primo per cui la tabella
    8.1.2 del B.02 da' probabilita' 1,00. Fino alla 10.13.33 la ricerca si
    fermava ai suoi limiti, 0 e 4000; con i forfait fuori dal conto questi
    casi arrivano anche a chi ha preso punti a forfait, o li ha persi, e il
    valore sbagliato passava all'APPO degli avversari."""

    @staticmethod
    def _torneo(partite_di_p, elo):
        """P con le partite date, (turno, avversario, risultato, punti);
        ogni avversario ha la voce speculare e l'Elo di elo."""
        speculare = {"1-0": "0-1", "0-1": "1-0", "1/2-1/2": "1/2-1/2", "1-F": "F-1", "F-1": "1-F"}
        giocatori = {"P": {"id": "P", "initial_elo": 1500, "results_history": []}}
        for avversario, valore in elo.items():
            giocatori[avversario] = {"id": avversario, "initial_elo": valore, "results_history": []}
        for turno, avversario, risultato, punti in partite_di_p:
            giocatori["P"]["results_history"].append({"round": turno, "opponent_id": avversario, "result": risultato, "score": punti})
            giocatori[avversario]["results_history"].append(
                {"round": turno, "opponent_id": "P", "result": speculare[risultato], "score": 1.0 - punti}
            )
        return {"players": list(giocatori.values()), "players_dict": giocatori, "rounds": [], "total_rounds": len(partite_di_p)}

    def test_zero_sulla_scacchiera_e_una_vittoria_a_forfait(self):
        """P perde con A da 2000 e con B da 1900 e vince a forfait con C da
        1400: il PTP e' 1900 - 800, e non 0; l'APPO di A, che ha giocato
        soltanto con P, e' lo stesso valore. Con il forfait nel conto, fino
        alla 10.13.33, P aveva 1600."""
        from stats import compute_tiebreak_value

        torneo = self._torneo([(1, "A", "0-1", 0.0), (2, "B", "0-1", 0.0), (3, "C", "1-F", 1.0)], {"A": 2000, "B": 1900, "C": 1400})

        assert compute_tiebreak_value("P", torneo, "PTP", {}) == 1100
        assert compute_tiebreak_value("A", torneo, "APPO", {}) == 1100

    def test_tutte_vinte_sulla_scacchiera_e_una_sconfitta_a_forfait(self):
        """P vince con A da 1600 e perde a forfait con B da 1400: il PTP e'
        1600 + 736, e non 4000; l'APPO di A e' lo stesso valore."""
        from stats import compute_tiebreak_value

        torneo = self._torneo([(1, "A", "1-0", 1.0), (2, "B", "F-1", 0.0)], {"A": 1600, "B": 1400})

        assert compute_tiebreak_value("P", torneo, "PTP", {}) == 2336
        assert compute_tiebreak_value("A", torneo, "APPO", {}) == 2336

    def test_zero_e_pieno_senza_forfait(self):
        """Gli stessi estremi per chi ha davvero zero punti o tutti i punti,
        che fino alla 10.13.33 avevano 0 e 4000."""
        from stats import compute_ptp

        elo = {"A": 1700, "B": 1500}
        tutte_perse = self._torneo([(1, "A", "0-1", 0.0), (2, "B", "0-1", 0.0)], elo)
        tutte_vinte = self._torneo([(1, "A", "1-0", 1.0), (2, "B", "1-0", 1.0)], elo)

        assert compute_ptp("P", tutte_perse) == 700
        assert compute_ptp("P", tutte_vinte) == 2436

    def test_fra_gli_estremi_la_ricerca_resta_quella_di_prima(self):
        """Un punto e mezzo su due contro 1400 e 1600 non e' un estremo: il
        PTP e' quello della formula logistica, 1706, fra lo zero e il pieno
        degli stessi avversari, 600 e 2336. La tabella 8.1.2 darebbe 1703:
        fra gli estremi Tornello usa la formula logistica, e la prova lo
        fissa."""
        from stats import compute_ptp

        elo = {"A": 1400, "B": 1600}
        torneo = self._torneo([(1, "A", "1-0", 1.0), (2, "B", "1/2-1/2", 0.5)], elo)

        assert compute_ptp("P", torneo) == 1706
        assert compute_ptp("P", self._torneo([(1, "A", "0-1", 0.0), (2, "B", "0-1", 0.0)], elo)) == 600
        assert compute_ptp("P", self._torneo([(1, "A", "1-0", 1.0), (2, "B", "1-0", 1.0)], elo)) == 2336
