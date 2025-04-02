# Tornello by Gabriele Battaglia & Gemini 2.5
# Data concepimento: 28 marzo 2025
import os
import json
import sys
import math
import traceback
# Rimossa importazione locale, non più necessaria per le date manuali
from datetime import datetime, timedelta
# --- Constants ---
VERSIONE = "2.3 di aprile 2025"
PLAYER_DB_FILE = "tornello - giocatori_db.json"
PLAYER_DB_TXT_FILE = "tornello - giocatori_db.txt"
TOURNAMENT_FILE = "Tornello - torneo.json"
DATE_FORMAT_ISO = "%Y-%m-%d"
# DATE_FORMAT_LOCALE non più usato
DEFAULT_K_FACTOR = 20
# --- Helper Functions ---
def format_date_locale(date_input):
    """Formatta una data (oggetto datetime o stringa ISO) nel formato locale esteso
       (es. Lunedì 31 marzo 2025) usando mapping manuale per i nomi.
       Restituisce 'N/D' o la stringa originale in caso di errore o input nullo."""
    if not date_input:
        return "N/D"
    try:
        if isinstance(date_input, datetime):
            date_obj = date_input
        else:
            date_obj = datetime.strptime(str(date_input), DATE_FORMAT_ISO)
        giorni = [
            "lunedì", "martedì", "mercoledì", "giovedì",
            "venerdì", "sabato", "domenica"
        ]
        mesi = [
            "", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
            "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"
        ]
        giorno_settimana_num = date_obj.weekday()
        giorno_mese = date_obj.day
        mese_num = date_obj.month
        anno = date_obj.year
        nome_giorno = giorni[giorno_settimana_num].capitalize()
        nome_mese = mesi[mese_num]
        return f"{nome_giorno} {giorno_mese} {nome_mese} {anno}"
    except (ValueError, TypeError, IndexError):
        return str(date_input)
def format_points(points):
    """Formatta i punti per la visualizzazione (intero se .0, altrimenti decimale)."""
    try:
        points = float(points)
        return str(int(points)) if points == int(points) else f"{points:.1f}"
    except (ValueError, TypeError):
        return str(points)
def sanitize_filename(name):
    """Rimuove/sostituisce caratteri problematici per i nomi dei file."""
    name = name.replace(' ', '_')
    import re
    name = re.sub(r'[^\w\-]+', '', name)
    if not name:
        name = "Torneo_Senza_Nome"
    return name
# --- Database Giocatori Functions ---
def load_players_db():
    """Carica il database dei giocatori dal file JSON."""
    if os.path.exists(PLAYER_DB_FILE):
        try:
            with open(PLAYER_DB_FILE, "r", encoding='utf-8') as f:
                db_list = json.load(f)
                return {p['id']: p for p in db_list}
        except (json.JSONDecodeError, IOError) as e:
            print(f"Errore durante il caricamento del DB giocatori ({PLAYER_DB_FILE}): {e}")
            print("Verrà creato un nuovo DB vuoto se si aggiungono giocatori.")
            return {}
    return {}
def save_players_db(players_db):
    """Salva il database dei giocatori nel file JSON e genera il file TXT."""
    if not players_db:
        pass # Procedi a salvare anche se vuoto
    try:
        with open(PLAYER_DB_FILE, "w", encoding='utf-8') as f:
            json.dump(list(players_db.values()), f, indent=4, ensure_ascii=False)
        save_players_db_txt(players_db)
    except IOError as e:
        print(f"Errore durante il salvataggio del DB giocatori ({PLAYER_DB_FILE}): {e}")
    except Exception as e:
         print(f"Errore imprevisto durante il salvataggio del DB: {e}")
def save_players_db_txt(players_db):
    """Genera un file TXT leggibile con lo stato del database giocatori."""
    try:
        with open(PLAYER_DB_TXT_FILE, "w", encoding='utf-8-sig') as f: # Usiamo utf-8-sig
            now = datetime.now()
            f.write(f"Report Database Giocatori Tornello - {format_date_locale(now.date())} {now.strftime('%H:%M:%S')}\n")
            f.write("=" * 40 + "\n\n")
            sorted_players = sorted(players_db.values(), key=lambda p: (p.get('last_name',''), p.get('first_name','')))
            if not sorted_players:
                 f.write("Il database dei giocatori è vuoto.\n")
                 return
            for player in sorted_players:
                f.write(f"ID: {player.get('id', 'N/D')}\n")
                f.write(f"Nome: {player.get('first_name', 'N/D')} {player.get('last_name', 'N/D')}\n")
                f.write(f"Elo Attuale: {player.get('current_elo', 'N/D')}\n")
                f.write(f"Data Iscrizione DB: {format_date_locale(player.get('registration_date'))}\n")
                medals = player.get('medals', {'gold': 0, 'silver': 0, 'bronze': 0})
                f.write(f"Medagliere: Oro: {medals.get('gold',0)}, Argento: {medals.get('silver',0)}, Bronzo: {medals.get('bronze',0)}\n")
                tournaments = player.get('tournaments_played', [])
                f.write(f"Tornei Partecipati ({len(tournaments)}):\n")
                if tournaments:
                    for i, t in enumerate(tournaments, 1):
                        t_name = t.get('tournament_name', 'Nome Torneo Mancante')
                        rank = t.get('rank', '?')
                        total = t.get('total_players', '?')
                        f.write(f"  {i}. {t_name} (Pos: {rank}/{total})\n")
                else:
                    f.write("  Nessuno\n")
                f.write("-" * 30 + "\n")
    except IOError as e:
        print(f"Errore durante il salvataggio del file TXT del DB giocatori ({PLAYER_DB_TXT_FILE}): {e}")
    except Exception as e:
        print(f"Errore imprevisto durante il salvataggio del TXT del DB: {e}")
def add_or_update_player_in_db(players_db, first_name, last_name, elo):
    """Aggiunge un nuovo giocatore al DB o aggiorna l'Elo se esiste già."""
    norm_first = first_name.strip().title()
    norm_last = last_name.strip().title()
    existing_player = None
    for p_id, player_data in players_db.items():
        if player_data.get('first_name','').lower() == norm_first.lower() and \
           player_data.get('last_name','').lower() == norm_last.lower():
            existing_player = player_data
            break
    if existing_player:
        existing_id = existing_player.get('id', 'N/D')
        existing_elo = existing_player.get('current_elo', 'N/D')
        print(f"Giocatore {norm_first} {norm_last} trovato nel DB con ID {existing_id} e Elo {existing_elo}.")
        if existing_elo != elo:
             print(f"L'Elo fornito ({elo}) è diverso da quello nel DB ({existing_elo}). Verrà usato {elo} per questo torneo.")
        return existing_player['id']
    else:
        last_part_cleaned = ''.join(norm_last.split())
        first_part_cleaned = ''.join(norm_first.split())
        last_initials = last_part_cleaned[:3].upper()
        first_initials = first_part_cleaned[:2].upper()
        while len(last_initials) < 3: last_initials += 'X'
        while len(first_initials) < 2: first_initials += 'X'
        base_id = f"{last_initials}{first_initials}"
        count = 1
        new_id = f"{base_id}{count:03d}"
        max_attempts = 1000
        current_attempt = 0
        while new_id in players_db and current_attempt < max_attempts:
            count += 1
            new_id = f"{base_id}{count:03d}"
            current_attempt += 1
        if new_id in players_db:
            print(f"ATTENZIONE: Impossibile generare ID univoco per {norm_first} {norm_last} dopo {max_attempts} tentativi.")
            fallback_suffix = hash(datetime.now()) % 10000
            new_id = f"{base_id}{fallback_suffix:04d}"
            if new_id in players_db:
                 print("ERRORE CRITICO: Fallback ID collision. Usare ID temporaneo.")
                 new_id = f"TEMP_{base_id}_{fallback_suffix}"
        new_player = {
            "id": new_id,
            "first_name": norm_first,
            "last_name": norm_last,
            "current_elo": elo,
            "registration_date": datetime.now().strftime(DATE_FORMAT_ISO),
            "tournaments_played": [],
            "medals": {"gold": 0, "silver": 0, "bronze": 0}
        }
        players_db[new_id] = new_player
        print(f"Nuovo giocatore {norm_first} {norm_last} aggiunto al DB con ID {new_id}.")
        save_players_db(players_db)
        return new_id
# --- Tournament Utility Functions ---
def load_tournament():
    """Carica lo stato del torneo corrente dal file JSON."""
    if os.path.exists(TOURNAMENT_FILE):
        try:
            with open(TOURNAMENT_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Errore durante il caricamento del torneo ({TOURNAMENT_FILE}): {e}")
            return None
    return None
def save_tournament(torneo):
    """Salva lo stato corrente del torneo nel file JSON."""
    try:
        temp_players = []
        if 'players' in torneo:
             for p in torneo['players']:
                  player_copy = p.copy()
                  # Converti set in lista PRIMA di salvare
                  player_copy['opponents'] = list(player_copy.get('opponents', []))
                  temp_players.append(player_copy)
        torneo_to_save = torneo.copy()
        torneo_to_save['players'] = temp_players
        if 'players_dict' in torneo_to_save:
             del torneo_to_save['players_dict']
        with open(TOURNAMENT_FILE, "w", encoding='utf-8') as f:
            json.dump(torneo_to_save, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Errore durante il salvataggio del torneo ({TOURNAMENT_FILE}): {e}")
    except Exception as e:
        print(f"Errore imprevisto durante il salvataggio del torneo: {e}")
        traceback.print_exc() # Stampa più dettagli in caso di errore non previsto
def get_player_by_id(torneo, player_id):
    """Restituisce i dati del giocatore nel torneo dato il suo ID, usando il dizionario interno."""
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    return torneo['players_dict'].get(player_id)
def calculate_dates(start_date_str, end_date_str, total_rounds):
    """Calcola le date di inizio e fine per ogni turno, distribuendo il tempo."""
    try:
        start_date = datetime.strptime(start_date_str, DATE_FORMAT_ISO)
        end_date = datetime.strptime(end_date_str, DATE_FORMAT_ISO)
        if end_date < start_date:
            print("Errore: la data di fine non può precedere la data di inizio.")
            return None
        total_duration = (end_date - start_date).days + 1
        if total_duration < total_rounds:
            print(f"Attenzione: La durata totale ({total_duration} giorni) è inferiore al numero di turni ({total_rounds}).")
            print("Assegnando 1 giorno per turno sequenzialmente.")
            round_dates = []
            current_date = start_date
            for i in range(total_rounds):
                round_dates.append({
                    "round": i + 1,
                    "start_date": current_date.strftime(DATE_FORMAT_ISO),
                    "end_date": current_date.strftime(DATE_FORMAT_ISO)
                })
                if current_date < end_date or i < total_rounds -1 :
                     current_date += timedelta(days=1)
            return round_dates
        days_per_round_float = total_duration / total_rounds
        round_dates = []
        current_start_date = start_date
        accumulated_days = 0.0
        for i in range(total_rounds):
            round_num = i + 1
            accumulated_days += days_per_round_float
            end_day_offset = round(accumulated_days)
            start_day_offset = round(accumulated_days - days_per_round_float)
            current_round_days = end_day_offset - start_day_offset
            if current_round_days <= 0: current_round_days = 1
            current_end_date = current_start_date + timedelta(days=current_round_days - 1)
            if round_num == total_rounds:
                 current_end_date = end_date
            elif current_end_date > end_date:
                 current_end_date = end_date
            round_dates.append({
                "round": round_num,
                "start_date": current_start_date.strftime(DATE_FORMAT_ISO),
                "end_date": current_end_date.strftime(DATE_FORMAT_ISO)
            })
            next_start_candidate = current_end_date + timedelta(days=1)
            if next_start_candidate > end_date and round_num < total_rounds:
                print(f"Avviso: Spazio insufficiente per i turni rimanenti. Il turno {round_num+1} inizierà il {format_date_locale(end_date)} (ultimo giorno).")
                current_start_date = end_date
            else:
                 current_start_date = next_start_candidate
        return round_dates
    except ValueError:
        print(f"Formato data non valido ('{start_date_str}' o '{end_date_str}'). Usa YYYY-MM-DD.")
        return None
    except Exception as e:
        print(f"Errore nel calcolo delle date: {e}")
        return None
# --- Elo Calculation Functions ---
def calculate_expected_score(player_elo, opponent_elo):
    """Calcola il punteggio atteso di un giocatore contro un avversario."""
    try:
        p_elo = float(player_elo)
        o_elo = float(opponent_elo)
        diff = max(-400, min(400, o_elo - p_elo))
        return 1 / (1 + 10**(diff / 400))
    except (ValueError, TypeError):
        print(f"Warning: Elo non valido ({player_elo} o {opponent_elo}) nel calcolo atteso.")
        return 0.5
def calculate_elo_change(player, tournament_players_dict, k_factor=DEFAULT_K_FACTOR):
    """Calcola la variazione Elo per un giocatore basata sulle partite del torneo."""
    if not player or 'initial_elo' not in player or 'results_history' not in player:
         print(f"Warning: Dati giocatore incompleti per calcolo Elo ({player.get('id','ID Mancante')}).")
         return 0
    total_expected_score = 0
    actual_score = 0
    games_played = 0
    initial_elo = player['initial_elo']
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        score = result_entry.get("score")
        if opponent_id is None or opponent_id == "BYE_PLAYER_ID" or score is None:
            continue
        opponent = tournament_players_dict.get(opponent_id)
        if not opponent or 'initial_elo' not in opponent:
            print(f"Warning: Avversario {opponent_id} non trovato o Elo iniziale mancante per calcolo Elo.")
            continue
        opponent_elo = opponent['initial_elo']
        expected_score = calculate_expected_score(initial_elo, opponent_elo)
        total_expected_score += expected_score
        actual_score += float(score)
        games_played += 1
    if games_played == 0:
        return 0
    elo_change = k_factor * (actual_score - total_expected_score)
    if elo_change > 0:
        return math.floor(elo_change + 0.5)
    else:
        return math.ceil(elo_change - 0.5)
def calculate_performance_rating(player, tournament_players_dict):
    """Calcola la Performance Rating di un giocatore."""
    if not player or 'initial_elo' not in player or 'results_history' not in player:
         return player.get('initial_elo', 1500)
    opponent_elos = []
    total_score = 0
    games_played_for_perf = 0
    initial_elo = player['initial_elo']
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        score = result_entry.get("score")
        if opponent_id is None or opponent_id == "BYE_PLAYER_ID" or score is None:
            continue
        opponent = tournament_players_dict.get(opponent_id)
        if not opponent or 'initial_elo' not in opponent:
             print(f"Warning: Avversario {opponent_id} non trovato o Elo mancante per calcolo Performance.")
             continue
        opponent_elos.append(opponent["initial_elo"])
        total_score += float(score)
        games_played_for_perf += 1
    if games_played_for_perf == 0:
        return initial_elo
    avg_opponent_elo = sum(opponent_elos) / games_played_for_perf
    score_percentage = total_score / games_played_for_perf
    dp_map = {
        1.0: 800, 0.99: 677, 0.98: 589, 0.97: 538, 0.96: 501, 0.95: 470,
        0.94: 444, 0.93: 422, 0.92: 401, 0.91: 383, 0.90: 366, 0.89: 351,
        0.88: 336, 0.87: 322, 0.86: 309, 0.85: 296, 0.84: 284, 0.83: 273,
        0.82: 262, 0.81: 251, 0.80: 240, 0.79: 230, 0.78: 220, 0.77: 211,
        0.76: 202, 0.75: 193, 0.74: 184, 0.73: 175, 0.72: 166, 0.71: 158,
        0.70: 149, 0.69: 141, 0.68: 133, 0.67: 125, 0.66: 117, 0.65: 110,
        0.64: 102, 0.63: 95, 0.62: 87, 0.61: 80, 0.60: 72, 0.59: 65,
        0.58: 57, 0.57: 50, 0.56: 43, 0.55: 36, 0.54: 29, 0.53: 21,
        0.52: 14, 0.51: 7, 0.50: 0,
    }
    lookup_p = round(score_percentage, 2)
    dp = 0
    if lookup_p < 0.0: lookup_p = 0.0
    if lookup_p > 1.0: lookup_p = 1.0
    if lookup_p < 0.50:
        complementary_p = round(1.0 - lookup_p, 2)
        dp = -dp_map.get(complementary_p, -800)
    elif lookup_p == 0.50:
         dp = 0
    else:
        dp = dp_map.get(lookup_p, 800)
    performance = avg_opponent_elo + dp
    return round(performance)
# --- Tie-breaking Functions ---
def compute_buchholz(player_id, torneo):
    """Calcola il punteggio Buchholz per un giocatore (somma punti avversari)."""
    buchholz_score = 0.0
    player = get_player_by_id(torneo, player_id)
    if not player: return 0.0
    players_dict = torneo.get('players_dict', {p['id']: p for p in torneo.get('players', [])})
    opponent_ids_encountered = set()
    for result_entry in player.get("results_history", []):
         opponent_id = result_entry.get("opponent_id")
         if opponent_id and opponent_id != "BYE_PLAYER_ID" and opponent_id not in opponent_ids_encountered:
             opponent = players_dict.get(opponent_id)
             if opponent:
                 buchholz_score += opponent.get("points", 0.0)
                 opponent_ids_encountered.add(opponent_id)
             else:
                 print(f"Warning: Avversario {opponent_id} non trovato nel dizionario per calcolo Buchholz di {player_id}.")
    return buchholz_score
# --- Pairing Logic ---
def assign_colors(player1, player2):
    """Assegna i colori basandosi sulla differenza B/N e alternanza."""
    w1 = player1.get("white_games", 0)
    b1 = player1.get("black_games", 0)
    d1 = w1 - b1
    last1 = player1.get("last_color", None)
    w2 = player2.get("white_games", 0)
    b2 = player2.get("black_games", 0)
    d2 = w2 - b2
    last2 = player2.get("last_color", None)
    if d1 < d2:
        return player1['id'], player2['id']
    elif d2 < d1:
        return player2['id'], player1['id']
    else:
        if last1 == "black" and last2 != "black":
            return player1['id'], player2['id']
        elif last2 == "black" and last1 != "black":
            return player2['id'], player1['id']
        elif last1 == "white" and last2 != "white":
            return player2['id'], player1['id']
        elif last2 == "white" and last1 != "white":
             return player1['id'], player2['id']
        else:
             p1_elo = player1.get('initial_elo', 0)
             p2_elo = player2.get('initial_elo', 0)
             if p1_elo > p2_elo:
                 if last1 == "white": return player2['id'], player1['id']
                 else: return player1['id'], player2['id']
             elif p2_elo > p1_elo:
                 if last2 == "white": return player1['id'], player2['id']
                 else: return player2['id'], player1['id']
             else:
                  print(f"Warning: Stessa diff. colore, stesso ultimo colore, stesso Elo ({p1_elo}) per {player1['id']} vs {player2['id']}. Assegnazione P1->Bianco.")
                  return player1['id'], player2['id']
def pairing(torneo):
    """Genera gli abbinamenti per il turno corrente."""
    round_number = torneo["current_round"]
    torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    players_dict = torneo['players_dict']
    players_for_pairing = []
    for p_orig in torneo.get('players', []):
        p_copy = p_orig.copy()
        # Lavora sempre con i SET internamente per il pairing
        p_copy['opponents'] = set(p_copy.get('opponents', []))
        players_for_pairing.append(p_copy)
    players_sorted = sorted(players_for_pairing, key=lambda x: (-x.get("points", 0.0), -x.get("initial_elo", 0)))
    paired_player_ids = set()
    matches = []
    bye_player_id = None
    active_players = [p for p in players_sorted if not p.get("withdrawn", False)]
    if len(active_players) % 2 != 0:
        eligible_for_bye = sorted(
            [p for p in active_players if not p.get("received_bye", False)],
            key=lambda x: (x.get("points", 0.0), x.get("initial_elo", 0))
        )
        bye_player_data = None
        if eligible_for_bye:
            bye_player_data = eligible_for_bye[0]
        else:
            print("Avviso: Tutti i giocatori attivi hanno già ricevuto il Bye. Riassegnazione al giocatore con punteggio/Elo più basso.")
            if active_players:
                 lowest_player = sorted(active_players, key=lambda x: (x.get("points", 0.0), x.get("initial_elo", 0)))[0]
                 bye_player_data = lowest_player
            else:
                 print("Errore: Nessun giocatore attivo per assegnare il Bye.")
        if bye_player_data:
             bye_player_id = bye_player_data['id']
             player_in_main_list = players_dict.get(bye_player_id)
             if player_in_main_list:
                  player_in_main_list["received_bye"] = True
                  # Assicurati che i punti siano float prima di aggiungere
                  player_in_main_list["points"] = float(player_in_main_list.get("points", 0.0)) + 1.0
                  if "results_history" not in player_in_main_list: player_in_main_list["results_history"] = []
                  player_in_main_list["results_history"].append({
                      "round": round_number, "opponent_id": "BYE_PLAYER_ID",
                      "color": None, "result": "BYE", "score": 1.0
                  })
             else:
                   print(f"ERRORE: Impossibile trovare il giocatore {bye_player_id} per aggiornare dati Bye.")
             bye_match = {
                 "id": torneo["next_match_id"], "round": round_number,
                 "white_player_id": bye_player_id, "black_player_id": None, "result": "BYE"
             }
             matches.append(bye_match)
             paired_player_ids.add(bye_player_id)
             torneo["next_match_id"] += 1
             print(f"Assegnato Bye a: {bye_player_data.get('first_name','')} {bye_player_data.get('last_name','')} (ID: {bye_player_id})")
    players_to_pair = [p for p in active_players if p['id'] not in paired_player_ids]
    score_groups = {}
    for p in players_to_pair:
        score = p.get("points", 0.0)
        if score not in score_groups: score_groups[score] = []
        score_groups[score].append(p)
    sorted_scores = sorted(score_groups.keys(), reverse=True)
    unpaired_list = []
    for score in sorted_scores:
        current_group_players = sorted(score_groups[score], key=lambda x: -x.get("initial_elo", 0))
        group_to_process = unpaired_list + current_group_players
        unpaired_list = []
        num_in_group = len(group_to_process)
        if num_in_group < 2:
             unpaired_list.extend(group_to_process)
             continue
        paired_in_this_group_cycle = set()
        temp_matches_this_group = []
        top_half_size = num_in_group // 2
        for i in range(top_half_size):
            player1 = group_to_process[i]
            if player1['id'] in paired_in_this_group_cycle: continue
            opponent_found = False
            preferred_opponent_index = i + top_half_size
            search_indices = [preferred_opponent_index] + \
                             list(range(preferred_opponent_index + 1, num_in_group)) + \
                             list(range(preferred_opponent_index - 1, top_half_size - 1, -1))
            for k in search_indices:
                 if k < top_half_size or k >= num_in_group: continue
                 player2 = group_to_process[k]
                 # Usa il SET per il controllo opponents
                 if player2['id'] not in paired_in_this_group_cycle and \
                    player2['id'] not in player1.get('opponents', set()):
                      white_id, black_id = assign_colors(player1, player2)
                      match = {
                          "id": torneo["next_match_id"], "round": round_number,
                          "white_player_id": white_id, "black_player_id": black_id, "result": None
                      }
                      temp_matches_this_group.append(match)
                      torneo["next_match_id"] += 1
                      paired_in_this_group_cycle.add(player1['id'])
                      paired_in_this_group_cycle.add(player2['id'])
                      opponent_found = True
                      break
        matches.extend(temp_matches_this_group)
        unpaired_list.extend([p for p in group_to_process if p['id'] not in paired_in_this_group_cycle])
    if unpaired_list:
        print("\nAVVISO: Impossibile appaiare tutti con Fold/Slide. Tentativo di Fallback Pairing.")
        for p in unpaired_list: print(f" - {p.get('first_name','')} {p.get('last_name','')} (ID: {p.get('id','')}, Punti: {p.get('points',0)})")
        unpaired_list.sort(key=lambda x: (-x.get("points", 0.0), -x.get("initial_elo", 0)))
        paired_in_fallback = set()
        for i in range(len(unpaired_list)):
            player1 = unpaired_list[i]
            if player1['id'] in paired_in_fallback: continue
            found_opponent_fallback = False
            for j in range(i + 1, len(unpaired_list)):
                player2 = unpaired_list[j]
                if player2['id'] in paired_in_fallback: continue
                # Usa il SET per il controllo opponents
                if player2['id'] not in player1.get('opponents', set()):
                    white_id, black_id = assign_colors(player1, player2)
                    match = {"id": torneo["next_match_id"], "round": round_number, "white_player_id": white_id, "black_player_id": black_id, "result": None}
                    matches.append(match)
                    torneo["next_match_id"] += 1
                    paired_in_fallback.add(player1['id'])
                    paired_in_fallback.add(player2['id'])
                    found_opponent_fallback = True
                    print(f" -> Fallback (No Repeat): Appaiati {player1['id']} vs {player2['id']}")
                    break
        remaining_after_fallback1 = [p for p in unpaired_list if p['id'] not in paired_in_fallback]
        if len(remaining_after_fallback1) % 2 != 0:
             print("ERRORE CRITICO FALLBACK: Numero dispari di giocatori rimasti dopo il primo fallback!")
        elif remaining_after_fallback1:
             print("\nAVVISO FORTE: Necessario forzare abbinamenti tra giocatori che hanno già giocato.")
             remaining_after_fallback1.sort(key=lambda x: (-x.get("points", 0.0), -x.get("initial_elo", 0)))
             for i in range(0, len(remaining_after_fallback1), 2):
                  if i + 1 >= len(remaining_after_fallback1): break
                  player1 = remaining_after_fallback1[i]
                  player2 = remaining_after_fallback1[i+1]
                  # Usa il SET per il controllo opponents
                  already_played_msg = " [RIPETUTO!]" if player2['id'] in player1.get('opponents', set()) else ""
                  white_id, black_id = assign_colors(player1, player2)
                  match = {"id": torneo["next_match_id"], "round": round_number, "white_player_id": white_id, "black_player_id": black_id, "result": None}
                  matches.append(match)
                  torneo["next_match_id"] += 1
                  paired_in_fallback.add(player1['id'])
                  paired_in_fallback.add(player2['id'])
                  print(f" -> Fallback FORZATO: Appaiati {player1['id']} vs {player2['id']}{already_played_msg}")
        final_paired_ids = {m.get('white_player_id') for m in matches if m.get('white_player_id')} | \
                           {m.get('black_player_id') for m in matches if m.get('black_player_id')}
        if bye_player_id: final_paired_ids.add(bye_player_id)
        final_unpaired_check = [p for p in active_players if p['id'] not in final_paired_ids]
        if final_unpaired_check:
             print("ERRORE CRITICO FINALE PAIRING: Giocatori ancora non appaiati dopo tutti i fallback:")
             for p in final_unpaired_check: print(f" - ID: {p['id']}")
    for match in matches:
         if match.get("result") == "BYE": continue
         white_player_id = match.get("white_player_id")
         black_player_id = match.get("black_player_id")
         if not white_player_id or not black_player_id: continue
         white_p = players_dict.get(white_player_id)
         black_p = players_dict.get(black_player_id)
         if not white_p or not black_p: continue
         # Assicura che siano SET prima di aggiungere (meglio essere sicuri)
         if not isinstance(white_p.get('opponents'), set): white_p['opponents'] = set(white_p.get('opponents', []))
         if not isinstance(black_p.get('opponents'), set): black_p['opponents'] = set(black_p.get('opponents', []))
         white_p["opponents"].add(black_player_id)
         black_p["opponents"].add(white_player_id)
         white_p["white_games"] = white_p.get("white_games", 0) + 1
         black_p["black_games"] = black_p.get("black_games", 0) + 1
         white_p["last_color"] = "white"
         black_p["last_color"] = "black"
    # Ritorna la lista delle partite create per il turno
    return matches
# --- Input and Output Functions ---
def input_players(players_db):
    """Gestisce l'input dei giocatori per un torneo."""
    players_in_tournament = []
    added_player_ids = set()
    print("\n--- Inserimento Giocatori ---")
    print("Puoi inserire 'Nome Cognome Elo' (es. Mario Rossi 1500) o un ID esistente (es. ROSMA001)")
    while True:
        data = input(f"Giocatore {len(players_in_tournament) + 1} (o vuoto per terminare): ").strip()
        if not data:
            if len(players_in_tournament) < 2:
                 print("Sono necessari almeno 2 giocatori.")
                 continue
            else:
                 break
        player_added_successfully = False
        player_id_to_add = None
        player_data_for_tournament = {}
        if data in players_db:
            potential_id = data
            if potential_id in added_player_ids:
                print(f"Errore: Giocatore ID {potential_id} già aggiunto.")
            else:
                db_player = players_db[potential_id]
                player_id_to_add = potential_id
                first_name = db_player.get('first_name', 'N/D')
                last_name = db_player.get('last_name', 'N/D')
                current_elo = db_player.get('current_elo', 1500)
                player_data_for_tournament = {
                    "id": player_id_to_add, "first_name": first_name, "last_name": last_name,
                    "initial_elo": current_elo, "points": 0.0, "results_history": [],
                    "opponents": set(), "white_games": 0, "black_games": 0,
                    "last_color": None, "received_bye": False, "buchholz": 0.0,
                    "performance_rating": None, "elo_change": None, "final_rank": None,
                    "withdrawn": False
                }
                print(f"Giocatore {first_name} {last_name} (ID: {player_id_to_add}, Elo: {current_elo}) aggiunto dal DB.")
                player_added_successfully = True
        else:
            try:
                parts = data.split()
                if len(parts) < 3:
                     raise ValueError("Formato non riconosciuto.")
                elo_str = parts[-1]
                elo = int(elo_str)
                name_parts = parts[:-1]
                if len(name_parts) == 0:
                     raise ValueError("Nome e Cognome mancanti.")
                elif len(name_parts) == 1:
                     first_name = name_parts[0].title()
                     last_name = name_parts[0].title()
                     print(f"Warning: Inserito solo un nome '{first_name}'. Usato anche come cognome.")
                else:
                     last_name = name_parts[-1].title()
                     first_name = " ".join(name_parts[:-1]).title()
                player_id_from_db = add_or_update_player_in_db(players_db, first_name, last_name, elo)
                if player_id_from_db in added_player_ids:
                     print(f"Errore: Giocatore {first_name} {last_name} (ID: {player_id_from_db}) già aggiunto.")
                else:
                    player_id_to_add = player_id_from_db
                    player_data_for_tournament = {
                        "id": player_id_to_add, "first_name": first_name, "last_name": last_name,
                        "initial_elo": elo, "points": 0.0, "results_history": [],
                        "opponents": set(), "white_games": 0, "black_games": 0,
                        "last_color": None, "received_bye": False, "buchholz": 0.0,
                        "performance_rating": None, "elo_change": None, "final_rank": None,
                        "withdrawn": False
                    }
                    player_added_successfully = True
            except ValueError as e:
                print(f"Input non valido: {e}. Riprova ('Nome Cognome Elo' o ID esistente).")
            except IndexError:
                 print("Formato input incompleto. Riprova.")
            except Exception as e:
                print(f"Errore imprevisto nell'inserimento giocatore: {e}")
        if player_added_successfully and player_id_to_add:
            players_in_tournament.append(player_data_for_tournament)
            added_player_ids.add(player_id_to_add)
    # Non convertire 'opponents' in lista qui, lo fa save_tournament
    return players_in_tournament
def update_match_result(torneo):
    """Chiede l'ID partita, aggiorna il risultato o gestisce 'cancella'.
       Restituisce True se un risultato è stato aggiornato o cancellato, False altrimenti."""
    current_round_num = torneo["current_round"]
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    players_dict = torneo['players_dict']
    current_round_data = None
    for r in torneo.get("rounds", []):
         if r.get("round") == current_round_num:
             current_round_data = r
             break
    if not current_round_data: # Sicurezza aggiuntiva
        print(f"ERRORE: Dati turno {current_round_num} non trovati per aggiornamento risultati.")
        return False
    while True: # Loop principale per chiedere ID o 'cancella'
        # Trova partite pendenti *ogni volta* nel loop per aggiornare il prompt
        pending_matches_this_round = []
        for m in current_round_data.get("matches", []):
             if m.get("result") is None and m.get("black_player_id") is not None:
                 pending_matches_this_round.append(m)
        if not pending_matches_this_round:
            # print("Info: Nessuna partita da registrare/cancellare per il turno corrente.") # Potrebbe essere logorroico
            return False # Nessuna azione possibile
        print("\nPartite del turno {} ancora da registrare:".format(current_round_num))
        pending_matches_this_round.sort(key=lambda m: m.get('id', 0))
        for m in pending_matches_this_round:
            white_p = players_dict.get(m.get('white_player_id'))
            black_p = players_dict.get(m.get('black_player_id'))
            if white_p and black_p:
                 w_name = f"{white_p.get('first_name','?')} {white_p.get('last_name','?')}"
                 w_elo = white_p.get('initial_elo','?')
                 b_name = f"{black_p.get('first_name','?')} {black_p.get('last_name','?')}"
                 b_elo = black_p.get('initial_elo','?')
                 print(f"  ID: {m.get('id','?')} - {w_name} [{w_elo}] vs {b_name} [{b_elo}]")
            else:
                 print(f"  ID: {m.get('id','?')} - Errore: Giocatore/i non trovato/i.")
        # Crea il prompt dinamico
        pending_ids = [str(m['id']) for m in pending_matches_this_round]
        prompt_ids_str = "-".join(pending_ids)
        prompt = f"Inserisci ID partita da aggiornare [{prompt_ids_str}], 'cancella' o lascia vuoto: "
        match_id_str = input(prompt).strip()
        if not match_id_str:
            return False # L'utente vuole uscire
        # --- Gestione Comando 'cancella' ---
        if match_id_str.lower() == 'cancella':
            completed_matches = []
            for m in current_round_data.get("matches", []):
                if m.get("result") is not None and m.get("result") != "BYE":
                    completed_matches.append(m)
            if not completed_matches:
                print("Nessuna partita completata in questo turno da poter cancellare.")
                continue # Torna al prompt principale
            print("\nPartite completate nel turno {} (possibile cancellare risultato):".format(current_round_num))
            completed_matches.sort(key=lambda m: m.get('id', 0))
            completed_ids = []
            for m in completed_matches:
                match_id = m.get('id','?')
                completed_ids.append(str(match_id))
                white_p = players_dict.get(m.get('white_player_id'))
                black_p = players_dict.get(m.get('black_player_id'))
                result = m.get('result','?')
                if white_p and black_p:
                    w_name = f"{white_p.get('first_name','?')} {white_p.get('last_name','?')}"
                    b_name = f"{black_p.get('first_name','?')} {black_p.get('last_name','?')}"
                    print(f"  ID: {match_id} - {w_name} vs {b_name} = {result}")
                else:
                    print(f"  ID: {match_id} - Errore giocatori = {result}")
            cancel_prompt = f"Inserisci ID partita da cancellare [{'-'.join(completed_ids)}] (o vuoto per annullare): "
            cancel_id_str = input(cancel_prompt).strip()
            if not cancel_id_str:
                continue # Torna al prompt principale
            try:
                cancel_id = int(cancel_id_str)
                match_to_cancel = None
                match_cancel_index = -1
                # Cerca l'ID tra le partite *completate* di questo turno
                for i, m in enumerate(current_round_data.get("matches", [])):
                    if m.get('id') == cancel_id and m.get("result") is not None and m.get("result") != "BYE":
                        match_to_cancel = m
                        match_cancel_index = i
                        break
                if match_to_cancel:
                    old_result = match_to_cancel['result']
                    white_p_id = match_to_cancel['white_player_id']
                    black_p_id = match_to_cancel['black_player_id']
                    white_p = players_dict.get(white_p_id)
                    black_p = players_dict.get(black_p_id)
                    if not white_p or not black_p:
                        print(f"ERRORE: Giocatori non trovati per la partita {cancel_id}, cancellazione annullata.")
                        continue
                    # Determina i punteggi da stornare
                    white_score_revert = 0.0
                    black_score_revert = 0.0
                    if old_result == "1-0": white_score_revert = 1.0
                    elif old_result == "0-1": black_score_revert = 1.0
                    elif old_result == "1/2-1/2": white_score_revert, black_score_revert = 0.5, 0.5
                    elif old_result == "0-0F": white_score_revert, black_score_revert = 0.0, 0.0 # Anche se 0, per coerenza
                    # Storna Punti
                    white_p["points"] = white_p.get("points", 0.0) - white_score_revert
                    black_p["points"] = black_p.get("points", 0.0) - black_score_revert
                    # Rimuovi da Storico Risultati (cerca l'entry specifica)
                    history_removed_w = False
                    if "results_history" in white_p:
                        for i in range(len(white_p["results_history"]) - 1, -1, -1): # Itera all'indietro
                            entry = white_p["results_history"][i]
                            if entry.get("round") == current_round_num and entry.get("opponent_id") == black_p_id:
                                del white_p["results_history"][i]
                                history_removed_w = True
                                break # Rimuovi solo la prima occorrenza trovata per questo round/oppo
                    history_removed_b = False
                    if "results_history" in black_p:
                        for i in range(len(black_p["results_history"]) - 1, -1, -1):
                            entry = black_p["results_history"][i]
                            if entry.get("round") == current_round_num and entry.get("opponent_id") == white_p_id:
                                del black_p["results_history"][i]
                                history_removed_b = True
                                break
                    # Azzera risultato nella partita
                    current_round_data["matches"][match_cancel_index]["result"] = None
                    print(f"Risultato ({old_result}) della partita ID {cancel_id} cancellato.")
                    if not history_removed_w: print(f"Warning: Voce storico non trovata per {white_p_id} vs {black_p_id}")
                    if not history_removed_b: print(f"Warning: Voce storico non trovata per {black_p_id} vs {white_p_id}")
                    # Salva subito il torneo dopo la cancellazione
                    save_tournament(torneo)
                    # Aggiorna dizionario interno dopo salvataggio
                    torneo['players_dict'] = {p['id']: p for p in torneo['players']}
                    return True # Indica che una modifica è stata fatta, forza il ricalcolo del prompt nel main loop
                else:
                    print(f"ID {cancel_id} non corrisponde a una partita completata cancellabile in questo turno.")
            except ValueError:
                print("ID non valido per la cancellazione. Inserisci un numero intero.")
            continue # Torna al prompt principale dopo l'operazione di cancellazione (o errore)
        # --- Fine Gestione 'cancella' ---
        # --- Gestione Inserimento Risultato Normale ---
        try:
            match_id_to_update = int(match_id_str)
            match_to_update = None
            match_index_in_round = -1
            # Cerca tra le partite PENDENTI
            for i, m in enumerate(current_round_data.get("matches", [])):
                if m.get('id') == match_id_to_update:
                     if m.get("result") is None and m.get("black_player_id") is not None:
                           match_to_update = m
                           match_index_in_round = i
                           break
                     elif m.get("result") == "BYE":
                           print(f"Info: La partita {match_id_to_update} è un BYE.")
                           break # ID trovato, ma è BYE
                     else:
                           print(f"Info: La partita {match_id_to_update} ha già un risultato ({m.get('result','?')}). Usa 'cancella' per modificarlo.")
                           break # ID trovato, ma già registrato
            if match_to_update:
                white_p = players_dict.get(match_to_update['white_player_id'])
                black_p = players_dict.get(match_to_update['black_player_id'])
                if not white_p or not black_p:
                     print(f"ERRORE: Giocatore non trovato per la partita {match_id_to_update}.")
                     continue # Richiedi ID
                print(f"Partita selezionata: {white_p['first_name']} {white_p['last_name']} vs {black_p['first_name']} {black_p['last_name']}")
                prompt_risultato = ("Risultato [bianco(1-0), nero(0-1), patta(1/2-1/2), bye(0-0F Annullata)]: ")
                result_input = input(prompt_risultato).strip().lower()
                new_result = None
                white_score = 0.0
                black_score = 0.0
                valid_input = True
                if result_input == 'bianco':
                    new_result = "1-0"
                    white_score = 1.0
                elif result_input == 'nero':
                    new_result = "0-1"
                    black_score = 1.0
                elif result_input == 'patta':
                    new_result = "1/2-1/2"
                    white_score = 0.5
                    black_score = 0.5
                elif result_input == 'bye':
                    new_result = "0-0F"
                    white_score = 0.0
                    black_score = 0.0
                    print("Partita marcata come non giocata/annullata (0-0).")
                else:
                    print("Input non valido. Usa 'bianco', 'nero', 'patta', 'bye'.")
                    valid_input = False
                if valid_input and new_result is not None:
                     # Assicurati che i punti siano float prima di aggiungere
                     white_p["points"] = float(white_p.get("points", 0.0)) + white_score
                     black_p["points"] = float(black_p.get("points", 0.0)) + black_score
                     if "results_history" not in white_p: white_p["results_history"] = []
                     if "results_history" not in black_p: black_p["results_history"] = []
                     white_p["results_history"].append({
                         "round": current_round_num, "opponent_id": black_p["id"],
                         "color": "white", "result": new_result, "score": white_score
                     })
                     black_p["results_history"].append({
                         "round": current_round_num, "opponent_id": white_p["id"],
                         "color": "black", "result": new_result, "score": black_score
                     })
                     current_round_data["matches"][match_index_in_round]["result"] = new_result
                     print("Risultato registrato.")
                     return True # Indica che un aggiornamento è stato fatto
            # Se match_to_update è None ma l'ID era valido (già registrato o BYE), il messaggio è stato stampato sopra
            elif match_index_in_round == -1 : # ID non trovato tra nessuna partita di questo turno
                 print("ID partita non valido per questo turno. Riprova.")
        except ValueError:
            print("ID non valido. Inserisci un numero intero o 'cancella'.")
def save_round_text(round_number, torneo):
    """Salva gli abbinamenti del turno in un file TXT."""
    tournament_name = torneo.get('name', 'Torneo_Senza_Nome')
    sanitized_name = sanitize_filename(tournament_name)
    filename = f"tornello - {sanitized_name} - turno{round_number}.txt"
    round_data = None
    for rnd in torneo.get("rounds", []):
        if rnd.get("round") == round_number:
            round_data = rnd
            break
    if round_data is None:
        print(f"Dati turno {round_number} non trovati per il salvataggio TXT.")
        return
    players_dict = torneo.get('players_dict', {p['id']: p for p in torneo.get('players', [])})
    try:
        with open(filename, "w", encoding='utf-8-sig') as f: # Usiamo utf-8-sig
            f.write(f"Torneo: {torneo.get('name', 'Nome Mancante')}\n")
            f.write(f"Turno: {round_number}\n")
            round_dates_list = torneo.get("round_dates", [])
            current_round_dates = next((rd for rd in round_dates_list if rd.get("round") == round_number), None)
            if current_round_dates:
                start_d_str = current_round_dates.get('start_date')
                end_d_str = current_round_dates.get('end_date')
                f.write(f"Periodo: {format_date_locale(start_d_str)} - {format_date_locale(end_d_str)}\n")
            f.write("-" * 60 + "\n")
            f.write("ID | Bianco                   [Elo] (Pt) - Nero                    [Elo] (Pt) | Risultato\n")
            f.write("-" * 60 + "\n")
            sorted_matches = sorted(round_data.get("matches", []), key=lambda m: m.get('id', 0))
            for match in sorted_matches:
                match_id = match.get('id', '?')
                white_p_id = match.get('white_player_id')
                black_p_id = match.get('black_player_id')
                result_str = match.get("result") if match.get("result") is not None else "Da programmare"
                white_p = players_dict.get(white_p_id)
                if not white_p:
                    line = f"{match_id:<2} | Errore Giocatore Bianco ID: {white_p_id} | {result_str}\n"
                    f.write(f"\t{line}")
                    continue
                w_name = f"{white_p.get('first_name','?')} {white_p.get('last_name','')}"
                w_elo = white_p.get('initial_elo','?')
                # Punti al momento della generazione del file (non sono storici)
                w_pts = format_points(white_p.get('points', 0.0))
                if black_p_id is None:
                    line = f"{match_id:<2} | {w_name:<24} [{w_elo:>4}] ({w_pts:<4}) - {'BYE':<31} | {result_str}\n"
                else:
                    black_p = players_dict.get(black_p_id)
                    if not black_p:
                        line = f"{match_id:<2} | {w_name:<24} [{w_elo:>4}] ({w_pts:<4}) - Errore Giocatore Nero ID: {black_p_id} | {result_str}\n"
                        f.write(f"\t{line}")
                        continue
                    b_name = f"{black_p.get('first_name','?')} {black_p.get('last_name','')}"
                    b_elo = black_p.get('initial_elo','?')
                    b_pts = format_points(black_p.get('points', 0.0))
                    line = (f"{match_id:<2} | "
                            f"{w_name:<24} [{w_elo:>4}] ({w_pts:<4}) - "
                            f"{b_name:<24} [{b_elo:>4}] ({b_pts:<4}) | "
                            f"{result_str}\n")
                f.write(f"\t{line}") # Aggiunto \t per indentare
        print(f"File abbinamenti {filename} salvato.")
    except IOError as e:
        print(f"Errore durante il salvataggio del file {filename}: {e}")
    except Exception as general_e:
         print(f"Errore inatteso durante save_round_text: {general_e}")
def save_standings_text(torneo, final=False):
    """Salva la classifica (parziale o finale) in un file TXT."""
    players = torneo.get("players", [])
    if not players:
         print("Warning: Nessun giocatore per generare classifica.")
         return
    torneo['players_dict'] = {p['id']: p for p in players}
    players_dict = torneo['players_dict']
    for p in players:
        p["buchholz"] = compute_buchholz(p["id"], torneo)
    if final:
        print("Calcolo Performance Rating e Variazione Elo per classifica finale...")
        for p in players:
             p["performance_rating"] = calculate_performance_rating(p, players_dict)
             p["elo_change"] = calculate_elo_change(p, players_dict, k_factor=torneo.get("k_factor", DEFAULT_K_FACTOR))
    def sort_key(player):
        points = player.get("points", 0.0)
        buchholz = player.get("buchholz", 0.0)
        performance = player.get("performance_rating", 0) if final else 0
        elo_initial = player.get("initial_elo", 0)
        return (-points, -buchholz, -performance, -elo_initial)
    try:
        players_sorted = sorted(players, key=sort_key)
    except Exception as e:
         print(f"Errore durante l'ordinamento dei giocatori: {e}")
         players_sorted = players
    if final:
        for i, p in enumerate(players_sorted):
            p["final_rank"] = i + 1
    tournament_name = torneo.get('name', 'Torneo_Senza_Nome')
    sanitized_name = sanitize_filename(tournament_name)
    file_suffix = "classifica_finale" if final else "classifica_parziale"
    filename = f"tornello - {sanitized_name} - {file_suffix}.txt"
    try:
        with open(filename, "w", encoding='utf-8-sig') as f: # Usiamo utf-8-sig
            f.write(f"Nome torneo: {torneo.get('name', 'N/D')}\n")
            if final:
                 f.write("CLASSIFICA FINALE\n")
            else:
                 completed_round = torneo.get("current_round", 1) - 1
                 f.write(f"Classifica Parziale - Dopo Turno {completed_round}\n")
            header = "Pos. Nome Cognome          [EloIni] Punti  Buchholz"
            if final:
                 header += "   Perf +/-Elo"
            f.write(header + "\n")
            f.write("=" * (len(header) + 2) + "\n")
            for i, player in enumerate(players_sorted, 1):
                rank = i if not final else player.get("final_rank", i)
                name_str = f"{player.get('first_name','?')} {player.get('last_name','')}"
                elo_str = f"[{player.get('initial_elo','?'):>4}]"
                pts_str = format_points(player.get('points', 0.0))
                buch_str = format_points(player.get('buchholz', 0.0))
                max_name_len = 21
                if len(name_str) > max_name_len:
                    name_str = name_str[:max_name_len-1] + "."
                line = f"{rank:<4} {name_str:<{max_name_len}} {elo_str:<8} {pts_str:<6} {buch_str:<8}"
                if final:
                     perf_str = str(player.get('performance_rating', 'N/A'))
                     elo_change_val = player.get('elo_change')
                     elo_change_str = f"{elo_change_val:+}" if elo_change_val is not None else "N/A"
                     line += f" {perf_str:<7} {elo_change_str:<6}"
                f.write(line + "\n")
        print(f"File classifica {filename} salvato.")
    except IOError as e:
        print(f"Errore durante il salvataggio del file classifica {filename}: {e}")
    except Exception as general_e:
         print(f"Errore inatteso durante save_standings_text: {general_e}")
         traceback.print_exc()
# --- Main Application Logic ---
def display_status(torneo):
    """Mostra lo stato attuale del torneo."""
    print("\n--- Stato Torneo ---")
    print(f"Nome: {torneo.get('name', 'N/D')}")
    start_d_str = torneo.get('start_date')
    end_d_str = torneo.get('end_date')
    print(f"Periodo: {format_date_locale(start_d_str)} - {format_date_locale(end_d_str)}")
    current_r = torneo.get('current_round', '?')
    total_r = torneo.get('total_rounds', '?')
    print(f"Turno Corrente: {current_r} / {total_r}")
    now = datetime.now()
    round_dates_list = torneo.get("round_dates", [])
    current_round_dates = next((rd for rd in round_dates_list if rd.get("round") == current_r), None)
    if current_round_dates:
        r_start_str = current_round_dates.get('start_date')
        r_end_str = current_round_dates.get('end_date')
        print(f"Periodo Turno {current_r}: {format_date_locale(r_start_str)} - {format_date_locale(r_end_str)}")
        try:
            round_end_dt = datetime.strptime(r_end_str, DATE_FORMAT_ISO).replace(hour=23, minute=59, second=59)
            days_left_round = (round_end_dt - now).days
            if now > round_end_dt:
                print(f"  -> Termine turno superato.")
            elif days_left_round == 0:
                print(f"  -> Ultimo giorno per completare il turno.")
            else:
                print(f"  -> Giorni rimanenti per il turno: {days_left_round}")
        except (ValueError, TypeError):
            print(f"  -> Date turno ('{format_date_locale(r_start_str)}', '{format_date_locale(r_end_str)}') non valide per calcolo giorni rimanenti.")
    try:
        tournament_end_dt = datetime.strptime(end_d_str, DATE_FORMAT_ISO).replace(hour=23, minute=59, second=59)
        days_left_tournament = (tournament_end_dt - now).days
        if now > tournament_end_dt:
            print(f"Termine torneo superato.")
        elif days_left_tournament == 0:
            print(f"Ultimo giorno del torneo.")
        else:
            print(f"Giorni rimanenti alla fine del torneo: {days_left_tournament}")
    except (ValueError, TypeError):
        print(f"Data fine torneo ('{format_date_locale(end_d_str)}') non valida per calcolo giorni rimanenti.")
    # Conta partite pendenti invece di listarle qui
    pending_match_count = 0
    found_current_round = False
    for r in torneo.get("rounds", []):
        if r.get("round") == current_r:
            found_current_round = True
            for m in r.get("matches", []):
                if m.get("result") is None and m.get("black_player_id") is not None:
                     pending_match_count += 1
            break
    if found_current_round:
        if pending_match_count > 0:
            print(f"\nPartite da giocare/registrare per il Turno {current_r}: {pending_match_count}")
            # La lista dettagliata verrà mostrata da update_match_result
        else:
             if current_r is not None and total_r is not None and current_r <= total_r:
                print(f"\nTutte le partite del Turno {current_r} sono state registrate.")
    elif current_r is not None and total_r is not None and current_r > total_r:
         print("\nIl torneo è concluso.")
    else:
         print("\nDati turno corrente non trovati.")
    print("--------------------\n")
def finalize_tournament(torneo, players_db):
     """Completa il torneo, calcola Elo/Performance, aggiorna DB giocatori."""
     print("\n--- Finalizzazione Torneo ---")
     players_dict = {p['id']: p for p in torneo.get('players', [])}
     torneo['players_dict'] = players_dict
     num_players = len(torneo.get('players', []))
     if num_players == 0:
          print("Nessun giocatore nel torneo, impossibile finalizzare.")
          return False
     print("Ricalcolo Buchholz, Performance Rating e Variazione Elo...") # Unificato print
     k_factor = torneo.get("k_factor", DEFAULT_K_FACTOR)
     for p in torneo.get('players',[]):
         p_id = p.get('id')
         if not p_id: continue
         if p.get("buchholz") is None: # Calcola solo se manca
              p["buchholz"] = compute_buchholz(p_id, torneo)
         p["performance_rating"] = calculate_performance_rating(p, players_dict)
         p["elo_change"] = calculate_elo_change(p, players_dict, k_factor)
     print("Definizione classifica finale...")
     def sort_key_final(player):
        points = player.get("points", 0.0)
        buchholz = player.get("buchholz", 0.0)
        performance = player.get("performance_rating", 0)
        elo_initial = player.get("initial_elo", 0)
        return (-points, -buchholz, -performance, -elo_initial)
     try:
        players_sorted = sorted(torneo.get('players',[]), key=sort_key_final)
        for i, p in enumerate(players_sorted):
            p["final_rank"] = i + 1
        torneo['players'] = players_sorted # Aggiorna lista torneo con i rank
     except Exception as e:
        print(f"Errore durante ordinamento finale: {e}")
     save_standings_text(torneo, final=True)
     print("Aggiornamento Database Giocatori...")
     db_updated = False
     for p in torneo.get('players',[]):
         player_id = p.get('id')
         final_rank = p.get('final_rank')
         elo_change = p.get('elo_change')
         if not player_id:
              print("Warning: Giocatore senza ID, impossibile aggiornare DB.")
              continue
         if player_id in players_db:
             db_player = players_db[player_id]
             if elo_change is not None:
                 old_elo = db_player.get('current_elo', '?')
                 # Assicura che l'elo attuale sia numerico per l'aggiornamento
                 current_db_elo = 1500
                 try:
                     current_db_elo = int(db_player.get('current_elo', 1500))
                 except (ValueError, TypeError):
                      print(f"Warning: Elo attuale non numerico per {player_id} nel DB. Reset a 1500.")
                 new_elo = current_db_elo + elo_change
                 db_player['current_elo'] = new_elo
                 print(f" - ID {player_id}: Elo aggiornato da {old_elo} a {new_elo} ({elo_change:+})")
             else:
                  print(f" - ID {player_id}: Variazione Elo non calcolata, Elo non aggiornato.")
             tournament_record = {
                 "tournament_name": torneo.get('name', 'N/D'),
                 "tournament_id": torneo.get('tournament_id', torneo.get('name', 'N/D')),
                 "rank": final_rank if final_rank is not None else 'N/A',
                 "total_players": num_players,
                 "date_completed": torneo.get('end_date', datetime.now().strftime(DATE_FORMAT_ISO))
             }
             if 'tournaments_played' not in db_player: db_player['tournaments_played'] = []
             if not any(t.get('tournament_id') == tournament_record['tournament_id'] for t in db_player['tournaments_played']):
                 db_player['tournaments_played'].append(tournament_record)
                 print(f" - ID {player_id}: Torneo '{tournament_record['tournament_name']}' aggiunto allo storico.")
             if final_rank is not None:
                 if 'medals' not in db_player: db_player['medals'] = {'gold': 0, 'silver': 0, 'bronze': 0}
                 updated_medal = False
                 if final_rank == 1:
                     db_player['medals']['gold'] = db_player['medals'].get('gold', 0) + 1
                     updated_medal = True
                 elif final_rank == 2:
                     db_player['medals']['silver'] = db_player['medals'].get('silver', 0) + 1
                     updated_medal = True
                 elif final_rank == 3:
                     db_player['medals']['bronze'] = db_player['medals'].get('bronze', 0) + 1
                     updated_medal = True
                 if updated_medal:
                      print(f" - ID {player_id}: Medagliere aggiornato (Rank: {final_rank}).")
             db_updated = True
         else:
             print(f"Attenzione: Giocatore ID {player_id} non trovato nel DB principale.")
     if db_updated:
          save_players_db(players_db)
          print("Database Giocatori aggiornato e salvato.")
     else:
          print("Nessun aggiornamento necessario per il Database Giocatori.")
     tournament_name = torneo.get('name', 'Torneo_Senza_Nome')
     sanitized_name = sanitize_filename(tournament_name)
     archive_name = f"tornello - {sanitized_name} - concluso.json"
     try:
          if os.path.exists(TOURNAMENT_FILE):
               os.rename(TOURNAMENT_FILE, archive_name)
               print(f"File torneo '{TOURNAMENT_FILE}' archiviato come '{archive_name}'")
          else:
               print(f"File torneo '{TOURNAMENT_FILE}' non trovato, impossibile archiviare.")
     except OSError as e:
          print(f"Errore durante l'archiviazione del file del torneo: {e}")
          print(f"Il file '{TOURNAMENT_FILE}' potrebbe essere rimasto.")
     return True
def main():
    players_db = load_players_db()
    torneo = load_tournament()
    launch_count = 1 # Default per nuovo torneo
    if torneo:
        # Incrementa contatore all'avvio se torneo esiste
        torneo['launch_count'] = torneo.get('launch_count', 0) + 1
        launch_count = torneo['launch_count']
    print(f"Benvenuti da Tornello {VERSIONE} - {launch_count}o lancio.\n\tGabriele Battaglia and Gemini 2.5.")
    if torneo is None:
        print(f"Nessun torneo in corso trovato ({TOURNAMENT_FILE}). Creazione nuovo torneo.")
        torneo = {}
        # Inizializza contatore per nuovo torneo
        torneo['launch_count'] = 1 # Parte da 1
        while True:
            name = input("Inserisci il nome del torneo: ").strip()
            if name:
                torneo["name"] = name
                break
            else:
                print("Il nome del torneo non può essere vuoto.")
        t_id_base = "".join(c for c in torneo['name'][:15] if c.isalnum() or c in ['_','-']).rstrip()
        torneo["tournament_id"] = f"{t_id_base}_{datetime.now().strftime('%Y%m%d%H%M')}"
        while True: # Loop per input data inizio
            try:
                oggi_str_iso = datetime.now().strftime(DATE_FORMAT_ISO)
                oggi_str_locale = format_date_locale(oggi_str_iso)
                start_date_str = input(f"Inserisci data inizio (YYYY-MM-DD) [Default: {oggi_str_locale}]: ").strip()
                if not start_date_str:
                    start_date_str = oggi_str_iso
                start_dt = datetime.strptime(start_date_str, DATE_FORMAT_ISO) # Valida
                torneo["start_date"] = start_date_str
                break # Esce dal loop data inizio
            except ValueError:
                print("Formato data non valido. Usa YYYY-MM-DD. Riprova.")
        while True: # Loop per input data fine
            try:
                start_date_default_locale = format_date_locale(torneo['start_date'])
                end_date_str = input(f"Inserisci data fine (YYYY-MM-DD) [Default: {start_date_default_locale}]: ").strip()
                if not end_date_str:
                    end_date_str = torneo['start_date']
                end_dt = datetime.strptime(end_date_str, DATE_FORMAT_ISO) # Valida
                start_dt = datetime.strptime(torneo["start_date"], DATE_FORMAT_ISO) # Rileggi per confronto
                if end_dt < start_dt:
                    print("Errore: La data di fine non può essere precedente alla data di inizio.")
                    continue # Richiedi data fine
                torneo["end_date"] = end_date_str
                break # Esce dal loop data fine
            except ValueError:
                print("Formato data non valido. Usa YYYY-MM-DD. Riprova.")
        while True: # Loop per numero turni
            try:
                rounds_str = input("Inserisci il numero totale dei turni: ").strip()
                total_rounds = int(rounds_str)
                if total_rounds > 0:
                    torneo["total_rounds"] = total_rounds
                    break # Esce dal loop turni
                else:
                    print("Il numero di turni deve essere positivo.")
            except ValueError:
                print("Inserisci un numero intero valido.")
        round_dates = calculate_dates(torneo["start_date"], torneo["end_date"], torneo["total_rounds"])
        if round_dates is None:
             print("Errore fatale nel calcolo delle date dei turni. Torneo annullato.")
             sys.exit(1)
        torneo["round_dates"] = round_dates
        torneo["players"] = input_players(players_db)
        if not torneo["players"] or len(torneo["players"]) < 2:
            print("Numero insufficiente di giocatori. Torneo annullato.")
            sys.exit(0)
        torneo["current_round"] = 1
        torneo["rounds"] = []
        torneo["next_match_id"] = 1
        torneo["k_factor"] = DEFAULT_K_FACTOR
        # Assicura che 'opponents' sia un SET per il primo pairing
        for p in torneo["players"]:
             p['opponents'] = set(p.get('opponents', []))
        print("\nGenerazione abbinamenti per il Turno 1...")
        matches_r1 = pairing(torneo)
        torneo["rounds"].append({"round": 1, "matches": matches_r1})
        torneo['players_dict'] = {p['id']: p for p in torneo['players']}
        save_tournament(torneo) # Salva torneo iniziale (con launch_count=1)
        save_round_text(1, torneo)
        save_standings_text(torneo, final=False)
        print("\nTorneo creato e Turno 1 generato.")
    else:
        print(f"Torneo '{torneo.get('name','N/D')}' in corso rilevato da {TOURNAMENT_FILE}.")
        if 'players' not in torneo: torneo['players'] = []
        # Assicura che 'opponents' sia un SET per operazioni interne
        for p in torneo["players"]:
            p['opponents'] = set(p.get('opponents', []))
        torneo['players_dict'] = {p['id']: p for p in torneo['players']}
    # --- Main Loop ---
    try:
        while torneo.get("current_round", 0) <= torneo.get("total_rounds", 0):
            current_round_num = torneo["current_round"]
            print(f"\n--- Gestione Turno {current_round_num} ---")
            display_status(torneo)
            round_completed = True
            pending_in_round = False
            round_data = None
            for r in torneo.get("rounds", []):
                 if r.get("round") == current_round_num:
                      round_data = r
                      for m in r.get("matches", []):
                           if m.get("result") is None and m.get("black_player_id") is not None:
                                round_completed = False
                                pending_in_round = True
                                break
                      break
            if round_data is None and current_round_num <= torneo.get("total_rounds",0):
                 print(f"ERRORE: Dati per il turno corrente {current_round_num} non trovati!")
                 break
            if not round_completed and pending_in_round:
                print("Inserisci i risultati delle partite o usa 'cancella':")
                # Chiama update_match_result finché restituisce True (azione eseguita)
                # o False (l'utente ha premuto invio per uscire)
                while update_match_result(torneo):
                    # Lo stato viene salvato all'interno di update_match_result dopo ogni modifica
                    # Ricarichiamo il dizionario per sicurezza, anche se dovrebbe essere aggiornato in-place
                    torneo['players_dict'] = {p['id']: p for p in torneo['players']}
                    # Controlla se ci sono ancora partite pendenti dopo l'aggiornamento/cancellazione
                    any_pending_left = False
                    # Bisogna rileggere round_data perché potrebbe essere cambiato (se 'cancella' ha funzionato)
                    current_round_data_check = None
                    for r_check in torneo.get("rounds", []):
                        if r_check.get("round") == current_round_num:
                            current_round_data_check = r_check
                            break
                    if current_round_data_check:
                        for m_check in current_round_data_check.get("matches", []):
                            if m_check.get("result") is None and m_check.get("black_player_id") is not None:
                                any_pending_left = True
                                break
                    if not any_pending_left:
                        print("\nTutte le partite del turno sono state registrate.")
                        break # Esce dal loop di update_match_result
                # Uscito dal loop di update_match_result (o perché finito o per invio vuoto)
                # Ricontrolla lo stato di completamento finale del turno
                final_round_check_completed = True
                final_round_data_check = None
                for r_check in torneo.get("rounds", []): # Rileggi i dati aggiornati
                    if r_check.get("round") == current_round_num:
                        final_round_data_check = r_check
                        break
                if final_round_data_check:
                    for m in final_round_data_check.get("matches", []):
                        if m.get("result") is None and m.get("black_player_id") is not None:
                            final_round_check_completed = False
                            break
                else:
                    # Se non ci sono dati del turno dopo l'update loop, qualcosa è andato storto
                    if current_round_num <= torneo.get("total_rounds", 0):
                        final_round_check_completed = False
            else:
                # Se il round era già completo all'inizio o non c'erano partite pendenti
                final_round_check_completed = True # Consideralo completo
            if final_round_check_completed:
                # Controlla se il turno attuale esiste effettivamente nei dati prima di dichiararlo completo
                if round_data or current_round_num > torneo.get("total_rounds", 0):
                     print(f"\nTurno {current_round_num} completato.")
                     save_round_text(current_round_num, torneo)
                     is_final_round = (current_round_num == torneo["total_rounds"])
                     save_standings_text(torneo, final=is_final_round)
                     if is_final_round:
                         if finalize_tournament(torneo, players_db):
                              print("\n--- Torneo Concluso e Finalizzato ---")
                         else:
                              print("\n--- Errore durante la Finalizzazione del Torneo ---")
                         break # Esce dal loop principale dei turni
                     else:
                         next_round_num = current_round_num + 1
                         print(f"\nGenerazione abbinamenti per il Turno {next_round_num}...")
                         # Assicura che 'opponents' sia un set prima del pairing
                         for p in torneo["players"]: p['opponents'] = set(p.get('opponents', []))
                         try:
                             # Aggiorna il numero del turno PRIMA di chiamare pairing
                             torneo["current_round"] = next_round_num
                             next_matches = pairing(torneo)
                             # Aggiungi il nuovo round con le sue partite
                             torneo["rounds"].append({"round": next_round_num, "matches": next_matches})
                             # Salva stato torneo e file del nuovo turno
                             save_tournament(torneo)
                             save_round_text(next_round_num, torneo)
                             print(f"Turno {next_round_num} generato e salvato.")
                         except Exception as e:
                             print(f"\nERRORE CRITICO durante la generazione del turno {next_round_num}: {e}")
                             print("Il torneo potrebbe essere in uno stato inconsistente.")
                             traceback.print_exc()
                             # Prova a salvare lo stato attuale prima di uscire
                             save_tournament(torneo)
                             break # Interrompi il torneo
                else:
                    # Caso strano: controllo completato ma dati round non trovati?
                    print(f"\nAttenzione: Turno {current_round_num} considerato completo ma dati round mancanti.")
                    break # Esce per sicurezza
            else:
                 print(f"\nIl Turno {current_round_num} non è ancora completo.")
                 print("Rilanciare il programma per continuare.")
                 # Salva lo stato attuale prima di uscire
                 save_tournament(torneo)
                 break
    except KeyboardInterrupt:
        print("\nOperazione interrotta dall'utente.")
        if torneo and 'players' in torneo:
             print("Salvataggio dello stato attuale del torneo...")
             save_tournament(torneo) # Salva lo stato con il contatore aggiornato
             print("Stato salvato. Uscita.")
        sys.exit(0)
    except Exception as e: # Cattura altri errori imprevisti nel loop principale
         print(f"\nERRORE CRITICO NON GESTITO nel flusso principale: {e}")
         print("Si consiglia di controllare i file JSON per eventuali corruzioni.")
         traceback.print_exc()
         if torneo: # Prova a salvare anche in caso di errore generico
              print("Tentativo di salvataggio dello stato attuale del torneo...")
              save_tournament(torneo)
              print("Stato (potenzialmente incompleto) salvato.")
         sys.exit(1)
    # Se il loop while termina normalmente (torneo finalizzato)
    print("\nProgramma terminato.")
if __name__ == "__main__":
    main() # Non serve più il blocco try/except qui, è dentro main()