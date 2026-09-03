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


def test_save_players_db_txt_usa_i_nomi_di_campo_giusti(tmp_path, monkeypatch):
    """Il report leggibile deve mostrare i dati FIDE extra, non "N/D" per un
    nome di campo sbagliato. Prima della correzione i campi w_title,
    o_title, foa_title, flag, elo_rapid, elo_blitz e fide_standard_games
    venivano letti con un prefisso "fide_" che non esisteva nel record."""
    import db_players

    db_file = tmp_path / "Tornello - Players_db.json"
    txt_file = tmp_path / "Tornello - Players_DB.txt"
    monkeypatch.setattr(db_players, "PLAYER_DB_FILE", str(db_file))
    monkeypatch.setattr(db_players, "PLAYER_DB_TXT_FILE", str(txt_file))

    giocatore = {
        "id": "TEST001",
        "first_name": "Test",
        "last_name": "Player",
        "current_elo": 1500,
        "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
        "tournaments_played": [],
        "elo_rapid": 1550,
        "elo_blitz": 1480,
        "fide_standard_games": 42,
        "fide_rapid_games": 10,
        "fide_rapid_k": 20,
        "fide_blitz_games": 5,
        "fide_blitz_k": 20,
        "w_title": "WFM",
        "o_title": "AO",
        "foa_title": "AF",
        "flag": "I",
    }

    db_players.save_players_db_txt({"TEST001": giocatore})

    contenuto = txt_file.read_text(encoding="utf-8-sig")
    assert "Elo Rapid: 1550" in contenuto
    assert "Elo Blitz: 1480" in contenuto
    assert "Partite FIDE: 42" in contenuto
    assert "Titoli Extra: WFM, AO, AF" in contenuto
    assert "Flag: I" in contenuto
