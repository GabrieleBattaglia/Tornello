from engine import parse_bbpairings_couples_output

def test_parse_bbpairings_couples_output():
    # Mappa start rank -> ID tornello
    mappa = {
        1: "GIOC001",
        2: "GIOC002",
        3: "GIOC003",
        4: "GIOC004"
    }

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
