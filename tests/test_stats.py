from stats import (
    get_k_factor,
    compute_buchholz,
    compute_buchholz_cut1,
    compute_aro,
    calculate_performance_rating,
    calculate_elo_change
)

def test_get_k_factor():
    # Giocatore con k_factor esplicito nel DB
    p_with_fide_k = {"k_factor": 40, "birth_date": "2015-05-05", "games_played": 10, "current_elo": 1200}
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
    sample_tournament_dict["players_dict"] = {p["id"]: p for p in sample_tournament_dict["players"]}
    
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
    performance = calculate_performance_rating(player_data, sample_tournament_dict["players_dict"])
    elo_change = calculate_elo_change(player_data, sample_tournament_dict["players_dict"])
    
    assert performance is None or isinstance(performance, int)
    assert elo_change is None or isinstance(elo_change, (int, float))


def test_time_control_parsing_and_classification():
    from stats import parse_time_control, classify_tournament_category
    
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
        compute_sonneborn_berger,
        compute_direct_encounter,
        compute_played_rounds_rep,
        compute_number_of_wins,
        compute_number_of_blacks,
        compute_cumulative
    )
    
    # Setup players dictionary
    sample_tournament_dict["players_dict"] = {p["id"]: p for p in sample_tournament_dict["players"]}
    
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
    from reports import get_standings_text
    
    # Create a minimal sample tournament dict
    torneo = {
        "name": "Test Sort",
        "players": [
            {"id": "P1", "first_name": "A", "last_name": "A", "initial_elo": 1500, "points": 3.0, "results_history": []},
            {"id": "P2", "first_name": "B", "last_name": "B", "initial_elo": 1600, "points": 3.0, "results_history": []},
        ],
        "rounds": [],
        "total_rounds": 1,
        "current_round": 1
    }
    
    # 1. Sort with points and initial_elo. P2 (1600) should be 1st, P1 (1500) should be 2nd.
    torneo["tiebreaks"] = ["points", "initial_elo"]
    text = get_standings_text(torneo)
    pos_b = text.find("B, B")
    pos_a = text.find("A, A")
    assert pos_b < pos_a
    # Since initial_elo is excluded from dynamic_cols and points is included, header should have Punti
    assert "Punti" in text
    
    # 2. Let's make P1 have a higher Elo (1700) and verify it sorts first.
    torneo["players"][0]["initial_elo"] = 1700
    text_rev = get_standings_text(torneo)
    pos_b_rev = text_rev.find("B, B")
    pos_a_rev = text_rev.find("A, A")
    assert pos_a_rev < pos_b_rev
    
    # 3. Verify ordering of dynamic columns headers in text
    torneo["tiebreaks"] = ["points", "buchholz", "aro"]
    text_cols1 = get_standings_text(torneo)
    header_line1 = [line for line in text_cols1.split("\n") if "Pos. (Tab)" in line][0]
    assert header_line1.find("Punti") < header_line1.find("BH")
    assert header_line1.find("BH") < header_line1.find("ARO")
    
    # Swap order: points, aro, buchholz
    torneo["tiebreaks"] = ["points", "aro", "buchholz"]
    text_cols2 = get_standings_text(torneo)
    header_line2 = [line for line in text_cols2.split("\n") if "Pos. (Tab)" in line][0]
    assert header_line2.find("Punti") < header_line2.find("ARO")
    assert header_line2.find("ARO") < header_line2.find("BH")





