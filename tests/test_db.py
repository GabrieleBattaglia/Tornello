import json
from db_players import load_players_db


def test_db_migration(tmp_path, monkeypatch):
    # Crea un file DB finto in formato v1 (lista)
    db_file = tmp_path / "Tornello - Players_db.json"
    v1_data = [
        {
            "id": "TEST001",
            "first_name": "Test",
            "last_name": "Player",
            "current_elo": 1500,
            "medals": {"gold": 1},
        }
    ]

    with open(db_file, "w", encoding="utf-8") as f:
        json.dump(v1_data, f)

    # Applica patch a PLAYER_DB_FILE e PLAYER_DB_TXT_FILE nel modulo db_players
    import db_players

    monkeypatch.setattr(db_players, "PLAYER_DB_FILE", str(db_file))
    monkeypatch.setattr(
        db_players, "PLAYER_DB_TXT_FILE", str(tmp_path / "Tornello - Players_DB.txt")
    )

    # Carica il DB, innescando la migrazione
    players = load_players_db()

    # Verifica che il giocatore sia stato caricato
    assert "TEST001" in players
    p = players["TEST001"]

    # Verifica che siano stati inseriti i campi di default v2
    assert p["elo_club"] == 0.0
    assert p["elo_rapid"] == 0.0
    assert p["fide_standard_games"] == 0
    assert p["medals"]["gold"] == 1
    assert p["medals"]["silver"] == 0  # Default v1

    # Leggi il file scritto per confermare che sia in formato v2
    with open(db_file, "r", encoding="utf-8") as f:
        saved_data = json.load(f)

    assert isinstance(saved_data, dict)
    assert saved_data["schema_version"] == 2
    assert len(saved_data["players"]) == 1
    assert saved_data["players"][0]["id"] == "TEST001"
