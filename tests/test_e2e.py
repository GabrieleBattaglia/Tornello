import os
import json
import pytest
from models import Tournament, Player, Round, Match
from db_players import load_players_db
from tournament import save_tournament, _apply_match_result_to_players, ricalcola_punti_tutti_giocatori, generate_pairings_for_round
from ui import finalize_tournament

def test_e2e_tournament_flow(tmp_path, monkeypatch):
    # 1. Configura percorsi temporanei per evitare di sporcare i file reali
    db_file = tmp_path / "Tornello - Players_db.json"
    db_txt = tmp_path / "Tornello - Players_DB.txt"
    closed_dir = tmp_path / "Closed Tournaments"
    closed_dir.mkdir()
    
    # Crea un database giocatori locale con 4 giocatori di test
    initial_db = {
        "schema_version": 2,
        "players": [
            {
                "id": "GIOC001",
                "first_name": "Magnus",
                "last_name": "Carlsen",
                "current_elo": 2800.0,
                "initial_elo": 2800.0,
                "sex": "m",
                "federation": "NOR",
                "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
                "tournaments_played": []
            },
            {
                "id": "GIOC002",
                "first_name": "Hikaru",
                "last_name": "Nakamura",
                "current_elo": 2750.0,
                "initial_elo": 2750.0,
                "sex": "m",
                "federation": "USA",
                "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
                "tournaments_played": []
            },
            {
                "id": "GIOC003",
                "first_name": "Fabiano",
                "last_name": "Caruana",
                "current_elo": 2700.0,
                "initial_elo": 2700.0,
                "sex": "m",
                "federation": "USA",
                "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
                "tournaments_played": []
            },
            {
                "id": "GIOC004",
                "first_name": "Ding",
                "last_name": "Liren",
                "current_elo": 2650.0,
                "initial_elo": 2650.0,
                "sex": "m",
                "federation": "CHN",
                "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
                "tournaments_played": []
            }
        ]
    }
    with open(db_file, "w", encoding="utf-8") as f:
        json.dump(initial_db, f, indent=4)
        
    # Applica il monkeypatch
    import db_players
    import tournament
    import ui
    import config
    
    monkeypatch.setattr(db_players, "PLAYER_DB_FILE", str(db_file))
    monkeypatch.setattr(db_players, "PLAYER_DB_TXT_FILE", str(db_txt))
    monkeypatch.setattr(config, "PLAYER_DB_FILE", str(db_file))
    monkeypatch.setattr(config, "ARCHIVED_TOURNAMENTS_DIR", str(closed_dir))
    monkeypatch.setattr(ui, "PLAYER_DB_FILE", str(db_file))
    monkeypatch.setattr(ui, "ARCHIVED_TOURNAMENTS_DIR", str(closed_dir))
    
    # 2. Inizializza un nuovo torneo
    torneo_dict = {
        "name": "Super E2E Cup",
        "site": "Bologna",
        "start_date": "2026-07-01",
        "end_date": "2026-07-01",
        "total_rounds": 2,
        "current_round": 1,
        "bye_value": 1.0,
        "initial_board1_color_setting": "white1",
        "time_control": {
            "minutes": 90,
            "increment": 30,
            "pgn_value": "5400+30"
        },
        "tournament_category": "standard",
        "players": [Player.from_dict(p).to_dict() for p in initial_db["players"]],
        "rounds": []
    }
    torneo_dict["players_dict"] = {p["id"]: p for p in torneo_dict["players"]}
    
    # Salva il file del torneo (usando un helper per convertire i set)
    def save_helper(data, filepath):
        data_copy = data.copy()
        temp_p = []
        for p in data_copy.get("players", []):
            p_copy = p.copy()
            p_copy["opponents"] = list(p_copy.get("opponents", []))
            temp_p.append(p_copy)
        data_copy["players"] = temp_p
        if "players_dict" in data_copy:
            del data_copy["players_dict"]
        with open(filepath, "w", encoding="utf-8") as sf:
            json.dump(data_copy, sf, indent=4, ensure_ascii=False)

    tournament_filename = tmp_path / "Tornello - Super E2E Cup.json"
    torneo_dict["filename"] = str(tournament_filename)
    save_helper(torneo_dict, tournament_filename)
        
    # 3. Genera abbinamenti Turno 1
    matches = generate_pairings_for_round(torneo_dict)
    assert matches
    round1_obj = Round(round=1, matches=[Match.from_dict(m) for m in matches])
    torneo_dict["rounds"].append(round1_obj.to_dict())
    assert len(torneo_dict["rounds"]) == 1
    
    round1 = torneo_dict["rounds"][0]
    assert len(round1["matches"]) == 2
    
    # Registra i risultati per il Turno 1
    # Carlsen (GIOC001) v Caruana (GIOC003) -> 1-0
    # Nakamura (GIOC002) v Ding Liren (GIOC004) -> 1/2-1/2
    match1 = round1["matches"][0]
    match2 = round1["matches"][1]
    
    # Imposta risultati
    match1["result"] = "1-0"
    match2["result"] = "1/2-1/2"
    
    # Applica i risultati
    _apply_match_result_to_players(torneo_dict, match1, "1-0", 1.0, 0.0)
    _apply_match_result_to_players(torneo_dict, match2, "1/2-1/2", 0.5, 0.5)
    ricalcola_punti_tutti_giocatori(torneo_dict)
    
    # 4. Passa al Turno 2
    torneo_dict["current_round"] = 2
    matches2 = generate_pairings_for_round(torneo_dict)
    assert matches2
    round2_obj = Round(round=2, matches=[Match.from_dict(m) for m in matches2])
    torneo_dict["rounds"].append(round2_obj.to_dict())
    assert len(torneo_dict["rounds"]) == 2
    
    round2 = torneo_dict["rounds"][1]
    assert len(round2["matches"]) == 2
    
    # Board 1 del Turno 2
    match2_1 = round2["matches"][0]
    match2_2 = round2["matches"][1]
    
    match2_1["result"] = "1-0"
    match2_2["result"] = "0-1"
    
    _apply_match_result_to_players(torneo_dict, match2_1, "1-0", 1.0, 0.0)
    _apply_match_result_to_players(torneo_dict, match2_2, "0-1", 0.0, 1.0)
    ricalcola_punti_tutti_giocatori(torneo_dict)
    
    # Salva prima di finalizzare
    save_helper(torneo_dict, tournament_filename)
        
    # 5. Finalizza il torneo
    players_db = load_players_db()
    finalize_success = finalize_tournament(torneo_dict, players_db, str(tournament_filename))
    assert finalize_success is True
    
    # Verifica che il torneo sia stato archiviato nella cartella Closed Tournaments
    archived_files = os.listdir(closed_dir)
    assert len(archived_files) > 0
    
    # Carica il database dei giocatori aggiornato
    updated_db = load_players_db()
    # Verifica lo storico e le medaglie
    carlsen = updated_db["GIOC001"]
    assert len(carlsen.get("tournaments_played", [])) == 1
    assert carlsen["tournaments_played"][0]["tournament_name"] == "Super E2E Cup"
    assert carlsen["medals"]["bronze"] == 1
    
    nakamura = updated_db["GIOC002"]
    assert nakamura["medals"]["gold"] == 1
    
    caruana = updated_db["GIOC003"]
    assert caruana["medals"]["wood"] == 1
    
    ding = updated_db["GIOC004"]
    assert ding["medals"]["silver"] == 1
