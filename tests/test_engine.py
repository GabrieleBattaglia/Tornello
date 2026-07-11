from engine import parse_bbpairings_couples_output


def test_parse_bbpairings_couples_output():
    # Mappa start rank -> ID tornello
    mappa = {1: "GIOC001", 2: "GIOC002", 3: "GIOC003", 4: "GIOC004"}

    # Esempio di output bbpPairings: prima riga è il totale abbinamenti, poi coppie
    raw_output = """2
1 2
3 0
"""

    parsed = parse_bbpairings_couples_output(raw_output, mappa)

    assert parsed is not None
    assert len(parsed) == 2

    # Primo match (White 1 vs Black 2)
    assert parsed[0]["white_player_id"] == "GIOC001"
    assert parsed[0]["black_player_id"] == "GIOC002"
    assert parsed[0]["result"] is None
    assert parsed[0]["is_bye"] is False

    # Secondo match (BYE per 3)
    assert parsed[1]["white_player_id"] == "GIOC003"
    assert parsed[1]["black_player_id"] is None
    assert parsed[1]["result"] == "BYE"
    assert parsed[1]["is_bye"] is True


def test_genera_stringa_trf_per_bbpairings():
    from engine import genera_stringa_trf_per_bbpairings

    torneo = {
        "name": "Test Tournament",
        "site": "Test Site",
        "federation_code": "ITA",
        "start_date": "2026-06-30",
        "end_date": "2026-06-30",
        "total_rounds": 5,
        "current_round": 1,
        "chief_arbiter": "Test Arbiter",
        "time_control": {
            "raw": "15+10",
            "minutes": 15,
            "increment": 10,
            "pgn_value": "900+10",
        },
        "initial_board1_color_setting": "white1",
        "bye_value": 1.0,
        "players_dict": {"P1": {"id": "P1", "withdrawn": False}},
    }

    players = [
        {
            "id": "P1",
            "last_name": "Rossi",
            "first_name": "Mario",
            "initial_elo": 1800,
            "federation": "ITA",
            "fide_id_num_str": "12345",
            "birth_date": "1990-01-01",
            "sex": "m",
            "points": 0.0,
            "results_history": [],
        }
    ]

    mappa_id_a_rank = {"P1": 1}

    trf = genera_stringa_trf_per_bbpairings(torneo, players, mappa_id_a_rank)

    assert trf is not None
    assert "012 Test Tournament" in trf
    assert "192 FIDE_DUTCH" in trf
    assert "142 005" in trf
    assert "152 W" in trf
    assert "162  W 1.0    D 0.5    L 0.0    Z 0.0    P 1.0" in trf


def test_real_tournament_pairing(sample_tournament_dict):
    from engine import genera_stringa_trf_per_bbpairings, run_bbpairings_engine
    from tournament import _ensure_players_dict

    # Prepariamo i dati del torneo
    _ensure_players_dict(sample_tournament_dict)

    # Diciamo che vogliamo fare gli abbinamenti per il turno 2
    current_round = 2
    sample_tournament_dict["current_round"] = current_round

    # Ricalcola i punti dei giocatori per rispecchiare solo i turni precedenti a current_round
    for p in sample_tournament_dict["players"]:
        prev_points = 0.0
        for h in p.get("results_history", []):
            if h.get("round", 0) < current_round:
                prev_points += float(h.get("score", 0.0))
        p["points"] = prev_points

    # Prepariamo la lista dei giocatori
    players = sample_tournament_dict["players"]
    mappa_id_a_rank = {p["id"]: i + 1 for i, p in enumerate(players)}

    trf = genera_stringa_trf_per_bbpairings(
        sample_tournament_dict, players, mappa_id_a_rank
    )
    assert trf is not None

    # Eseguiamo il motore su questo TRF reale!
    success, bbp_output_data, bbp_message = run_bbpairings_engine(trf)
    assert success is True, f"bbpPairings failed: {bbp_message}"
    assert "coppie_raw" in bbp_output_data
