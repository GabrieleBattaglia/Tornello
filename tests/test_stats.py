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

