from models import Tournament


def test_tournament_serialization_roundtrip(sample_tournament_dict):
    # Deserializza
    tournament = Tournament.from_dict(sample_tournament_dict)

    # Asserzioni sui dati base
    assert tournament.name == "ASCId Primavera 1"
    assert tournament.total_rounds == 5
    assert len(tournament.players) == 28
    assert len(tournament.rounds) == 5

    # Riserializza
    serialized_dict = tournament.to_dict()

    # Asserzioni sulla consistenza dei dati
    assert serialized_dict["name"] == sample_tournament_dict["name"]
    assert len(serialized_dict["players"]) == len(sample_tournament_dict["players"])
    assert len(serialized_dict["rounds"]) == len(sample_tournament_dict["rounds"])

    # Verifica che players_dict sia ricostruito correttamente
    assert len(tournament.players_dict) == 28
    assert tournament.players_dict["BATGA001"].first_name == "Gabriele"


def test_rollback_to_previous_round(sample_tournament_dict):
    from tournament import rollback_to_previous_round
    import copy

    t_dict = copy.deepcopy(sample_tournament_dict)

    initial_rounds_count = len(t_dict.get("rounds", []))
    assert initial_rounds_count == 5
    t_dict["current_round"] = 5

    # Rollback round 5
    success = rollback_to_previous_round(t_dict)
    assert success is True
    assert len(t_dict.get("rounds", [])) == 4
    assert t_dict["current_round"] == 4

    # Rollback round 4
    success = rollback_to_previous_round(t_dict)
    assert success is True
    assert len(t_dict.get("rounds", [])) == 3
    assert t_dict["current_round"] == 3

    # Rollback until empty
    for _ in range(3):
        rollback_to_previous_round(t_dict)

    assert len(t_dict.get("rounds", [])) == 0
    assert t_dict["current_round"] == 1
