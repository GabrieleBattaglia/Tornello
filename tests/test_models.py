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
