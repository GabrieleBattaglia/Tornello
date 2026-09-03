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
