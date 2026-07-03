import os
import json
from models import Player, Round, Match, ResultEntry
from db_players import load_players_db
from tournament import _apply_match_result_to_players, ricalcola_punti_tutti_giocatori, generate_pairings_for_round
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


def test_e2e_complex_tournament_flow_bye_withdrawals(tmp_path, monkeypatch):
    # 1. Configura percorsi temporanei per evitare di sporcare i file reali
    db_file = tmp_path / "Tornello - Players_db_complex.json"
    db_txt = tmp_path / "Tornello - Players_DB_complex.txt"
    closed_dir = tmp_path / "Closed Tournaments Complex"
    closed_dir.mkdir()
    
    # Crea 29 giocatori nel DB locale con Elo decrescenti
    players_db_list = []
    for i in range(1, 30):
        players_db_list.append({
            "id": f"GIOC{i:03d}",
            "first_name": f"Player{i}",
            "last_name": f"Test{i}",
            "current_elo": float(2000 - i * 10),
            "initial_elo": float(2000 - i * 10),
            "sex": "m" if i % 2 == 0 else "w",
            "federation": "ITA",
            "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
            "tournaments_played": []
        })
        
    initial_db = {
        "schema_version": 2,
        "players": players_db_list
    }
    with open(db_file, "w", encoding="utf-8") as f:
        json.dump(initial_db, f, indent=4)
        
    # Applica il monkeypatch
    import db_players
    import ui
    import config
    
    monkeypatch.setattr(db_players, "PLAYER_DB_FILE", str(db_file))
    monkeypatch.setattr(db_players, "PLAYER_DB_TXT_FILE", str(db_txt))
    monkeypatch.setattr(config, "PLAYER_DB_FILE", str(db_file))
    monkeypatch.setattr(config, "ARCHIVED_TOURNAMENTS_DIR", str(closed_dir))
    monkeypatch.setattr(ui, "PLAYER_DB_FILE", str(db_file))
    monkeypatch.setattr(ui, "ARCHIVED_TOURNAMENTS_DIR", str(closed_dir))
    
    # 2. Inizializza un nuovo torneo con 29 giocatori e 7 turni
    torneo_dict = {
        "name": "Complex E2E Cup",
        "site": "Imola",
        "start_date": "2026-07-01",
        "end_date": "2026-07-01",
        "total_rounds": 7,
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
    
    # Helper per salvare su disco
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

    tournament_filename = tmp_path / "Tornello - Complex E2E Cup.json"
    torneo_dict["filename"] = str(tournament_filename)
    save_helper(torneo_dict, tournament_filename)
    
    def get_scores(res_str):
        if res_str in ("1-0", "1-F"):
            return 1.0, 0.0
        elif res_str in ("0-1", "F-1"):
            return 0.0, 1.0
        elif res_str == "1/2-1/2":
            return 0.5, 0.5
        return 0.0, 0.0

    # 3. Esegui il torneo turno per turno (1-7)
    for round_num in range(1, 8):
        torneo_dict["current_round"] = round_num
        
        # Genera gli abbinamenti
        matches = generate_pairings_for_round(torneo_dict)
        assert matches is not None
        
        # Calcola numero di giocatori attivi
        active_count = sum(1 for p in torneo_dict["players"] if not p.get("withdrawn"))
        
        # Se dispari, deve esserci un BYE
        has_bye = any(m.get("black_player_id") is None for m in matches)
        if active_count % 2 == 1:
            assert has_bye is True
        else:
            assert has_bye is False
            
        # Registra i risultati delle partite
        for idx, match in enumerate(matches):
            if match.get("black_player_id") is None:
                # Partita di BYE: il motore assegna automaticamente il risultato "BYE"
                match["result"] = "BYE"
                # Il punteggio del BYE viene applicato automaticamente
                # nel controller/main_frame, ma qui lo simuliamo per il test:
                bye_player = torneo_dict["players_dict"].get(match["white_player_id"])
                if bye_player:
                    bye_player.setdefault("results_history", []).append(ResultEntry(
                        round=round_num, opponent_id="BYE_PLAYER_ID", color=None, result="BYE", score=1.0
                    ).to_dict())
            else:
                # Partita standard
                if round_num == 3 and idx == 0:
                    # Vittoria per forfait (forfeit win per il Bianco) al turno 3 board 1
                    res = "1-F"
                elif round_num == 4 and idx == 1:
                    # Sconfitta per forfait (forfeit win per il Nero) al turno 4 board 2
                    res = "F-1"
                else:
                    # Risultato normale alternato
                    res = "1-0" if idx % 2 == 0 else "0-1"
                
                match["result"] = res
                w_score, b_score = get_scores(res)
                _apply_match_result_to_players(torneo_dict, match, res, w_score, b_score)
                
        # Salva il round
        round_obj = Round(round=round_num, matches=[Match.from_dict(m) for m in matches])
        torneo_dict["rounds"].append(round_obj.to_dict())
        
        # Ricalcola i punteggi
        ricalcola_punti_tutti_giocatori(torneo_dict)
        
        # Applicazione ritiri
        if round_num == 4:
            # Ritiro definitivo del giocatore GIOC010 al turno 4
            torneo_dict["players_dict"]["GIOC010"]["withdrawn"] = True
        elif round_num == 5:
            # Ritiro definitivo del giocatore GIOC011 al turno 5
            torneo_dict["players_dict"]["GIOC011"]["withdrawn"] = True
            
        save_helper(torneo_dict, tournament_filename)
        
    # 4. Finalizza il torneo
    players_db = load_players_db()
    finalize_success = finalize_tournament(torneo_dict, players_db, str(tournament_filename))
    assert finalize_success is True
    
    # 5. Verifica archiviazione e storico
    archived_files = os.listdir(closed_dir)
    assert len(archived_files) > 0
    
    # Verifica che i dati storici sul DB siano stati scritti correttamente
    updated_db = load_players_db()
    p1 = updated_db["GIOC001"]
    assert len(p1.get("tournaments_played", [])) == 1
    assert p1["tournaments_played"][0]["tournament_name"] == "Complex E2E Cup"
