# Tornello Pro, by Gabriele Battaglia & Gemini 2.5
# Data concepimento: 28 marzo 2025

import os
import json
import sys
import math
from datetime import datetime, timedelta
import traceback # Per debug errori critici

# --- Constants ---
VERSIONE="2.0.5 di marzo 2025"
PLAYER_DB_FILE = "tornello - giocatori_db.json"
PLAYER_DB_TXT_FILE = "tornello - giocatori_db.txt"
TOURNAMENT_FILE = "Tornello - torneo.json"
DATE_FORMAT = "%Y-%m-%d" # formato date standard ISO
DEFAULT_K_FACTOR = 20 # Fattore K standard per il calcolo Elo (può variare)

# --- Database Giocatori Functions ---

def load_players_db():
	"""Carica il database dei giocatori dal file JSON."""
	if os.path.exists(PLAYER_DB_FILE):
		try:
			with open(PLAYER_DB_FILE, "r", encoding='utf-8') as f:
				# Usiamo un dizionario per accesso rapido tramite ID
				db_list = json.load(f)
				return {p['id']: p for p in db_list}
		except (json.JSONDecodeError, IOError) as e:
			print(f"Errore durante il caricamento del DB giocatori ({PLAYER_DB_FILE}): {e}")
			print("Verrà creato un nuovo DB vuoto se si aggiungono giocatori.")
			return {} # Restituisce un DB vuoto in caso di errore
	return {}

def save_players_db(players_db):
	"""Salva il database dei giocatori nel file JSON e genera il file TXT."""
	if not players_db: # Non salvare un DB vuoto se non c'era nulla da caricare e nulla è stato aggiunto
		# Questo previene la sovrascrittura accidentale di un file esistente ma illeggibile con un file vuoto
		# all'avvio del programma se il caricamento fallisce e non vengono aggiunti nuovi giocatori.
		# Se invece si aggiungono giocatori a un DB vuoto, verrà salvato correttamente.
		# Modifica: Salviamo anche se vuoto, per creare il file se non esiste
		# if not any(players_db.values()): # Controlla se è veramente vuoto
		#    print("Info: Il DB giocatori è vuoto, nessun salvataggio effettuato.")
		#    return
		pass # Procedi a salvare anche se vuoto

	try:
		# Salva JSON (convertendo di nuovo in lista per il formato standard JSON)
		with open(PLAYER_DB_FILE, "w", encoding='utf-8') as f:
			json.dump(list(players_db.values()), f, indent=4, ensure_ascii=False)

		# Salva TXT
		save_players_db_txt(players_db)

	except IOError as e:
		print(f"Errore durante il salvataggio del DB giocatori ({PLAYER_DB_FILE}): {e}")
	except Exception as e:
		 print(f"Errore imprevisto durante il salvataggio del DB: {e}")


def save_players_db_txt(players_db):
	"""Genera un file TXT leggibile con lo stato del database giocatori."""
	try:
		with open(PLAYER_DB_TXT_FILE, "w", encoding='utf-8') as f:
			f.write(f"Report Database Giocatori Tornello - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
			f.write("=" * 40 + "\n\n")

			# Ordina per ID o Nome/Cognome per consistenza
			sorted_players = sorted(players_db.values(), key=lambda p: (p.get('last_name',''), p.get('first_name','')))

			if not sorted_players:
				 f.write("Il database dei giocatori è vuoto.\n")
				 return # Esce se non ci sono giocatori

			for player in sorted_players:
				f.write(f"ID: {player.get('id', 'N/D')}\n")
				f.write(f"Nome: {player.get('first_name', 'N/D')} {player.get('last_name', 'N/D')}\n")
				f.write(f"Elo Attuale: {player.get('current_elo', 'N/D')}\n")
				f.write(f"Data Iscrizione DB: {player.get('registration_date', 'N/D')}\n")

				# Medagliere
				medals = player.get('medals', {'gold': 0, 'silver': 0, 'bronze': 0})
				f.write(f"Medagliere: Oro: {medals.get('gold',0)}, Argento: {medals.get('silver',0)}, Bronzo: {medals.get('bronze',0)}\n")

				# Tornei Partecipati
				tournaments = player.get('tournaments_played', [])
				f.write(f"Tornei Partecipati ({len(tournaments)}):\n")
				if tournaments:
					# Ordina i tornei se necessario (es. per data, ma manca la data qui)
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
	"""Aggiunge un nuovo giocatore al DB o aggiorna l'Elo se esiste già.
	   Gestisce nomi/cognomi con spazi nella generazione ID.
	   Restituisce l'ID del giocatore."""
	# Normalizza nomi per confronto
	norm_first = first_name.strip().title() # Usa title() per gestire meglio "Di Bari" -> "Di Bari"
	norm_last = last_name.strip().title()

	existing_player = None
	for p_id, player_data in players_db.items():
		# Confronto più robusto che ignora maiuscole/minuscole e spazi extra
		if player_data.get('first_name','').lower() == norm_first.lower() and \
		   player_data.get('last_name','').lower() == norm_last.lower():
			existing_player = player_data
			break

	if existing_player:
		existing_id = existing_player.get('id', 'N/D')
		existing_elo = existing_player.get('current_elo', 'N/D')
		print(f"Giocatore {norm_first} {norm_last} trovato nel DB con ID {existing_id} e Elo {existing_elo}.")
		# Manteniamo la logica precedente: usiamo l'Elo fornito per il torneo
		if existing_elo != elo:
			 print(f"L'Elo fornito ({elo}) è diverso da quello nel DB ({existing_elo}). Verrà usato {elo} per questo torneo.")
		# Non si aggiorna l'Elo nel DB qui, solo a fine torneo.
		return existing_player['id'] # Restituisce l'ID esistente
	else:
		# --- Gestione ID ---
		last_part_cleaned = ''.join(norm_last.split())
		first_part_cleaned = ''.join(norm_first.split())

		last_initials = last_part_cleaned[:3].upper()
		first_initials = first_part_cleaned[:2].upper()

		while len(last_initials) < 3: last_initials += 'X'
		while len(first_initials) < 2: first_initials += 'X'

		base_id = f"{last_initials}{first_initials}"

		count = 1
		new_id = f"{base_id}{count:03d}"
		# Controllo collisione più sicuro
		max_attempts = 1000 # Limite tentativi per evitare loop infinito
		current_attempt = 0
		while new_id in players_db and current_attempt < max_attempts:
			count += 1
			new_id = f"{base_id}{count:03d}"
			current_attempt += 1

		if new_id in players_db: # Se ancora in collisione dopo max_attempts
			print(f"ATTENZIONE: Impossibile generare ID univoco per {norm_first} {norm_last} dopo {max_attempts} tentativi.")
			# Fallback molto semplice (potrebbe ancora collidere ma è raro)
			fallback_suffix = hash(datetime.now()) % 10000
			new_id = f"{base_id}{fallback_suffix:04d}"
			if new_id in players_db:
				 print("ERRORE CRITICO: Fallback ID collision. Usare ID temporaneo.")
				 new_id = f"TEMP_{base_id}_{fallback_suffix}" # ID temporaneo chiaramente identificabile


		new_player = {
			"id": new_id,
			"first_name": norm_first,
			"last_name": norm_last,
			"current_elo": elo,
			"registration_date": datetime.now().strftime(DATE_FORMAT),
			"tournaments_played": [],
			"medals": {"gold": 0, "silver": 0, "bronze": 0}
		}
		players_db[new_id] = new_player
		print(f"Nuovo giocatore {norm_first} {norm_last} aggiunto al DB con ID {new_id}.")
		save_players_db(players_db) # Salva DB e TXT dopo aggiunta
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
		# Assicura che i set siano convertiti in liste prima di salvare
		temp_players = []
		if 'players' in torneo:
			 for p in torneo['players']:
				  player_copy = p.copy() # Lavora su una copia per non modificare l'originale in memoria
				  player_copy['opponents'] = list(player_copy.get('opponents', [])) # Converte set in lista
				  temp_players.append(player_copy)
		
		torneo_to_save = torneo.copy() # Crea una copia del dizionario torneo
		torneo_to_save['players'] = temp_players # Usa la lista giocatori con 'opponents' convertito
		# Rimuovi il dizionario temporaneo se esiste (non serializzabile)
		if 'players_dict' in torneo_to_save:
			 del torneo_to_save['players_dict'] 

		with open(TOURNAMENT_FILE, "w", encoding='utf-8') as f:
			json.dump(torneo_to_save, f, indent=4, ensure_ascii=False)
			
	except IOError as e:
		print(f"Errore durante il salvataggio del torneo ({TOURNAMENT_FILE}): {e}")
	except Exception as e:
		print(f"Errore imprevisto durante il salvataggio del torneo: {e}")


def format_points(points):
	"""Formatta i punti per la visualizzazione (intero se .0, altrimenti decimale)."""
	try:
		points = float(points) # Assicura sia un numero
		return str(int(points)) if points == int(points) else f"{points:.1f}" # Mostra sempre una cifra decimale se non intero
	except (ValueError, TypeError):
		return str(points) # Restituisci com'è se non è un numero valido


def get_player_by_id(torneo, player_id):
	"""Restituisce i dati del giocatore nel torneo dato il suo ID, usando il dizionario interno."""
	# Assicura che il dizionario sia presente e aggiornato
	if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
		torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
	return torneo['players_dict'].get(player_id)


def calculate_dates(start_date_str, end_date_str, total_rounds):
	"""Calcola le date di inizio e fine per ogni turno, distribuendo il tempo."""
	try:
		start_date = datetime.strptime(start_date_str, DATE_FORMAT)
		end_date = datetime.strptime(end_date_str, DATE_FORMAT)
		
		if end_date < start_date:
			 print("Errore: la data di fine non può precedere la data di inizio.")
			 return None
			 
		total_duration = (end_date - start_date).days + 1 # +1 per includere l'ultimo giorno

		if total_duration < total_rounds:
			print(f"Attenzione: La durata totale ({total_duration} giorni) è inferiore al numero di turni ({total_rounds}).")
			print("Assegnando 1 giorno per turno sequenzialmente.")
			round_dates = []
			current_date = start_date
			for i in range(total_rounds):
				round_dates.append({
					"round": i + 1,
					"start_date": current_date.strftime(DATE_FORMAT),
					"end_date": current_date.strftime(DATE_FORMAT)
				})
				# Avanza solo se non si supera la data di fine teorica (anche se breve)
				if current_date < end_date or i < total_rounds -1 : # Evita di andare oltre end_date se possibile
					 current_date += timedelta(days=1)
				# Se i turni sono troppi per i giorni, l'ultima data si ripeterà
			return round_dates

		# Distribuzione normale
		days_per_round_float = total_duration / total_rounds
		round_dates = []
		current_start_date = start_date
		accumulated_days = 0.0

		for i in range(total_rounds):
			round_num = i + 1
			accumulated_days += days_per_round_float
			# Arrotonda i giorni *cumulativi* e sottrai quelli precedenti per trovare i giorni *di questo* turno
			end_day_offset = round(accumulated_days)
			start_day_offset = round(accumulated_days - days_per_round_float) # Offset del giorno finale del turno precedente
			
			current_round_days = end_day_offset - start_day_offset
			if current_round_days <= 0: current_round_days = 1 # Assicura almeno 1 giorno

			current_end_date = current_start_date + timedelta(days=current_round_days - 1)

			# Assicura che l'ultima data non superi la data di fine torneo e che copra fino alla fine
			if round_num == total_rounds:
				 current_end_date = end_date
			# Controllo anti-superamento (anche se la logica arrotondata dovrebbe evitarlo)
			elif current_end_date > end_date:
				 current_end_date = end_date


			round_dates.append({
				"round": round_num,
				"start_date": current_start_date.strftime(DATE_FORMAT),
				"end_date": current_end_date.strftime(DATE_FORMAT)
			})
			
			# Prossimo inizio = giorno dopo la fine corrente
			next_start_candidate = current_end_date + timedelta(days=1)
			# Non iniziare un nuovo turno dopo la data di fine del torneo
			if next_start_candidate > end_date and round_num < total_rounds:
				print(f"Avviso: Spazio insufficiente per i turni rimanenti. Il turno {round_num+1} inizierà il {end_date.strftime(DATE_FORMAT)} (ultimo giorno).")
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
	# Gestisce Elo non validi (es. da BYE o errori)
	try:
		p_elo = float(player_elo)
		o_elo = float(opponent_elo)
		# Limita la differenza Elo massima a 400 punti ai fini del calcolo
		# (pratica comune per evitare variazioni estreme) - Opzionale
		diff = max(-400, min(400, o_elo - p_elo))
		return 1 / (1 + 10**(diff / 400))
	except (ValueError, TypeError):
		print(f"Warning: Elo non valido ({player_elo} o {opponent_elo}) nel calcolo atteso.")
		return 0.5 # Ritorna 0.5 (patta) in caso di Elo non valido? O solleva errore?


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
			continue # Salta Bye o voci incomplete

		opponent = tournament_players_dict.get(opponent_id)
		if not opponent or 'initial_elo' not in opponent:
			print(f"Warning: Avversario {opponent_id} non trovato o Elo iniziale mancante per calcolo Elo.")
			continue # Salta se l'avversario o il suo Elo non sono validi

		opponent_elo = opponent['initial_elo']

		# Calcola punteggio atteso per questa partita
		expected_score = calculate_expected_score(initial_elo, opponent_elo)
		total_expected_score += expected_score
		actual_score += float(score) # Assicura sia float
		games_played += 1

	if games_played == 0:
		return 0 # Nessuna variazione se non ha giocato partite valide per Elo

	# Applica K-factor (potrebbe variare in base a Elo/partite giocate - usiamo fisso per ora)
	# Arrotondamento standard: round al più vicino intero, .5 arrotonda all'intero pari (round half to even)
	# FIDE usa arrotondamento standard (round half up) di solito
	elo_change = k_factor * (actual_score - total_expected_score)
	# Applichiamo round standard (round half up)
	if elo_change > 0:
		return math.floor(elo_change + 0.5)
	else:
		return math.ceil(elo_change - 0.5)


def calculate_performance_rating(player, tournament_players_dict):
	"""Calcola la Performance Rating di un giocatore."""
	if not player or 'initial_elo' not in player or 'results_history' not in player:
		 return player.get('initial_elo', 1500) # Ritorna Elo iniziale o default se dati mancano

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
		return initial_elo # Performance uguale all'Elo iniziale se non ha giocato

	avg_opponent_elo = sum(opponent_elos) / games_played_for_perf
	score_percentage = total_score / games_played_for_perf

	# Tabella di conversione FIDE da p (percentuale) a dp (differenza Elo)
	# Fonte: FIDE Handbook B.02.10.1.1a (approssimata, interpolare sarebbe meglio)
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
		# Per p < 0.5, dp(p) = -dp(1-p)
	}

	# Arrotonda la percentuale al più vicino 0.01 per lookup
	lookup_p = round(score_percentage, 2)

	dp = 0 # Default a 0
	if lookup_p < 0.0: lookup_p = 0.0 # Limita inferiore
	if lookup_p > 1.0: lookup_p = 1.0 # Limita superiore

	if lookup_p < 0.50:
		# Trova il valore per 1-p e inverti il segno
		complementary_p = round(1.0 - lookup_p, 2)
		dp = -dp_map.get(complementary_p, -800) # Usa get con default negativo
	elif lookup_p == 0.50:
		 dp = 0
	else: # lookup_p > 0.50
		dp = dp_map.get(lookup_p, 800) # Usa get con default positivo

	# Potremmo interpolare per valori non esattamente in tabella, ma per ora usiamo il valore più vicino (implicito nel get)
	# o l'arrotondamento della percentuale stessa.

	performance = avg_opponent_elo + dp
	return round(performance)

# --- Tie-breaking Functions ---

def compute_buchholz(player_id, torneo):
	"""Calcola il punteggio Buchholz per un giocatore (somma punti avversari)."""
	buchholz_score = 0.0
	player = get_player_by_id(torneo, player_id)
	if not player: return 0.0

	# Usa il dizionario interno per efficienza
	players_dict = torneo.get('players_dict', {p['id']: p for p in torneo.get('players', [])})

	# Itera sugli avversari incontrati registrati nello storico del giocatore
	opponent_ids_encountered = set() # Evita di contare due volte in caso di errore dati
	for result_entry in player.get("results_history", []):
		 opponent_id = result_entry.get("opponent_id")
		 
		 if opponent_id and opponent_id != "BYE_PLAYER_ID" and opponent_id not in opponent_ids_encountered:
			 opponent = players_dict.get(opponent_id)
			 if opponent:
				 buchholz_score += opponent.get("points", 0.0) # Somma i punti CORRENTI dell'avversario
				 opponent_ids_encountered.add(opponent_id)
			 else:
				 print(f"Warning: Avversario {opponent_id} non trovato nel dizionario per calcolo Buchholz di {player_id}.")

	# Varianti comuni:
	# Buchholz Cut-1: Sottrai il punteggio dell'avversario con il punteggio più basso.
	# Buchholz Median (Cut-2): Sottrai il più alto e il più basso.
	# Buchholz Totale (quello implementato qui): Somma di tutti.

	return buchholz_score

# --- Pairing Logic (Simplified FIDE-like) ---

def assign_colors(player1, player2):
	"""Assegna i colori basandosi sulla differenza B/N e alternanza.
	   Restituisce (white_player_id, black_player_id)."""
	
	# Ottieni dati colore, gestendo valori mancanti (default a 0 o None)
	w1 = player1.get("white_games", 0)
	b1 = player1.get("black_games", 0)
	d1 = w1 - b1
	last1 = player1.get("last_color", None)

	w2 = player2.get("white_games", 0)
	b2 = player2.get("black_games", 0)
	d2 = w2 - b2
	last2 = player2.get("last_color", None)

	# Priorità 1: Differenza assoluta (chi ha giocato più Neri ha priorità per il Bianco)
	if d1 < d2: # player1 ha più "diritto" al bianco (d1 è più negativo o meno positivo di d2)
		return player1['id'], player2['id'] # P1 Bianco, P2 Nero
	elif d2 < d1: # player2 ha più "diritto" al bianco
		return player2['id'], player1['id'] # P2 Bianco, P1 Nero
	else: # d1 == d2, stessa differenza (es. entrambi 0, o entrambi +1)
		# Priorità 2: Alternanza rispetto all'ultimo turno giocato
		# Se P1 ha giocato Nero e P2 no (o viceversa), chi ha giocato Nero ottiene Bianco
		if last1 == "black" and last2 != "black":
			return player1['id'], player2['id']
		elif last2 == "black" and last1 != "black":
			return player2['id'], player1['id']
		# Se P1 ha giocato Bianco e P2 no (o viceversa), chi ha giocato Bianco ottiene Nero
		elif last1 == "white" and last2 != "white":
			return player2['id'], player1['id'] # P1 deve avere Nero, P2 Bianco
		elif last2 == "white" and last1 != "white":
			 return player1['id'], player2['id'] # P2 deve avere Nero, P1 Bianco
		else: # Stessa differenza, stesso ultimo colore (o primo turno)
			 # Priorità 3: Ranking (Elo iniziale come tiebreak)
			 # Il giocatore con Elo più alto ottiene il colore "preferito" teorico
			 # Se d=0, la preferenza è alternare (se last='w', preferenza='b')
			 # Se non c'è last_color (primo turno), Elo più alto Bianco? (Convenzione comune)
			 p1_elo = player1.get('initial_elo', 0)
			 p2_elo = player2.get('initial_elo', 0)

			 if p1_elo > p2_elo:
				 # P1 più alto. Se deve alternare (last='w' -> vuole 'b'), P2 prende Bianco. Altrimenti P1 Bianco.
				 if last1 == "white": return player2['id'], player1['id']
				 else: return player1['id'], player2['id']
			 elif p2_elo > p1_elo:
				 # P2 più alto. Se deve alternare (last='w' -> vuole 'b'), P1 prende Bianco. Altrimenti P2 Bianco.
				 if last2 == "white": return player1['id'], player2['id']
				 else: return player2['id'], player1['id']
			 else: # Elo uguali - raro, ma possibile. Assegnazione arbitraria o sorteggio.
				  # Arbitrario: P1 Bianco (basato sull'ordine di arrivo nella lista)
				  print(f"Warning: Stessa diff. colore, stesso ultimo colore, stesso Elo ({p1_elo}) per {player1['id']} vs {player2['id']}. Assegnazione P1->Bianco.")
				  return player1['id'], player2['id']


def pairing(torneo):
	"""Genera gli abbinamenti per il turno corrente usando sistema svizzero basato su score groups
	   con sistema Fold/Slide all'interno dei gruppi e fallback."""
	round_number = torneo["current_round"]
	torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
	players_dict = torneo['players_dict']

	players_for_pairing = []
	for p_orig in torneo.get('players', []):
		p_copy = p_orig.copy()
		p_copy['opponents'] = set(p_copy.get('opponents', [])) # Lavora con SET
		players_for_pairing.append(p_copy)

	players_sorted = sorted(players_for_pairing, key=lambda x: (-x.get("points", 0.0), -x.get("initial_elo", 0)))

	paired_player_ids = set()
	matches = []
	bye_player_id = None

	# 1. Gestione Bye (Logica Invariata - omessa per brevità, copia dal codice precedente)
	active_players = [p for p in players_sorted if not p.get("withdrawn", False)]
	if len(active_players) % 2 != 0:
		# ... (stessa logica di prima per assegnare il BYE) ...
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
				  player_in_main_list["points"] = player_in_main_list.get("points", 0.0) + 1.0
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
		# --- Fine Logica Bye ---


	# 2. Pairing Principale basato su Score Groups con Fold/Slide
	players_to_pair = [p for p in active_players if p['id'] not in paired_player_ids]
	score_groups = {}
	for p in players_to_pair:
		score = p.get("points", 0.0)
		if score not in score_groups: score_groups[score] = []
		score_groups[score].append(p)

	sorted_scores = sorted(score_groups.keys(), reverse=True)
	unpaired_list = [] # Giocatori non appaiati (floaters + rimasti dal fallback)

	for score in sorted_scores:
		current_group_players = sorted(score_groups[score], key=lambda x: -x.get("initial_elo", 0))
		# Processa floaters + giocatori del gruppo corrente
		group_to_process = unpaired_list + current_group_players
		unpaired_list = [] # Resetta floaters per questo ciclo
		
		num_in_group = len(group_to_process)
		if num_in_group < 2: # Non abbastanza giocatori da appaiare
			 unpaired_list.extend(group_to_process) # Diventano floaters per il prossimo gruppo
			 continue # Passa al prossimo score group

		# --- INIZIO LOGICA FOLD/SLIDE ---
		paired_in_this_group_cycle = set() # Chi è stato appaiato in questo specifico ciclo
		temp_matches_this_group = [] # Partite create in questo ciclo

		top_half_size = num_in_group // 2

		# Itera sulla metà superiore del gruppo
		for i in range(top_half_size):
			player1 = group_to_process[i]
			# Se player1 è già stato scelto come avversario da qualcuno sopra di lui, saltalo
			if player1['id'] in paired_in_this_group_cycle: continue

			opponent_found = False
			# Indice dell'avversario ideale nella metà inferiore
			preferred_opponent_index = i + top_half_size

			# Strategia di ricerca:
			# 1. Prova l'avversario ideale (preferred_opponent_index)
			# 2. Se non va bene (già appaiato o già giocato), cerca *sotto* l'ideale nella metà inferiore
			# 3. Se non va bene, cerca *sopra* l'ideale nella metà inferiore (fino all'inizio della metà inf)

			# Lista ordinata degli indici da provare nella metà inferiore
			search_indices = [preferred_opponent_index] + \
							 list(range(preferred_opponent_index + 1, num_in_group)) + \
							 list(range(preferred_opponent_index - 1, top_half_size - 1, -1))

			for k in search_indices:
				 # Assicurati che l'indice sia valido per la metà inferiore
				 if k < top_half_size or k >= num_in_group: continue

				 player2 = group_to_process[k]

				 # Controlla se player2 è disponibile E se non hanno già giocato
				 if player2['id'] not in paired_in_this_group_cycle and \
					player2['id'] not in player1.get('opponents', set()):

					  # Abbinamento valido trovato!
					  white_id, black_id = assign_colors(player1, player2)
					  match = {
						  "id": torneo["next_match_id"], "round": round_number,
						  "white_player_id": white_id, "black_player_id": black_id, "result": None
					  }
					  temp_matches_this_group.append(match)
					  torneo["next_match_id"] += 1
					  # Segna entrambi come appaiati in questo ciclo
					  paired_in_this_group_cycle.add(player1['id'])
					  paired_in_this_group_cycle.add(player2['id'])
					  opponent_found = True
					  break # Player1 ha trovato il suo avversario, passa al prossimo player1

			# Se player1 non ha trovato NESSUN avversario valido nella metà inferiore
			# (molto raro ma possibile con vincoli stretti), rimarrà non appaiato per ora.
			# Verrà aggiunto alla unpaired_list sotto.

		# --- FINE LOGICA FOLD/SLIDE ---

		# Aggiungi le partite create in questo ciclo alla lista principale
		matches.extend(temp_matches_this_group)

		# Determina chi è rimasto non appaiato da group_to_process e aggiungilo a unpaired_list
		# per essere processato nel prossimo score group o nel fallback finale.
		unpaired_list.extend([p for p in group_to_process if p['id'] not in paired_in_this_group_cycle])


	# 3. Fallback Pairing (Logica Invariata - omessa per brevità, copia dal codice precedente)
	#    Questa sezione gestisce 'unpaired_list' se contiene giocatori dopo aver processato tutti i gruppi.
	if unpaired_list:
		print("\nAVVISO: Impossibile appaiare tutti i giocatori con le regole standard (Fold/Slide).")
		print("Tentativo di Fallback Pairing per i seguenti giocatori:")
		# ... (stessa logica di fallback di prima: Tentativo 1 e Tentativo 2 Forzato) ...
		for p in unpaired_list: print(f" - {p.get('first_name','')} {p.get('last_name','')} (ID: {p.get('id','')}, Punti: {p.get('points',0)})")
		unpaired_list.sort(key=lambda x: (-x.get("points", 0.0), -x.get("initial_elo", 0)))
		paired_in_fallback = set()

		# Tentativo 1 Fallback: No Repeat
		for i in range(len(unpaired_list)):
			player1 = unpaired_list[i]
			if player1['id'] in paired_in_fallback: continue
			found_opponent_fallback = False
			for j in range(i + 1, len(unpaired_list)):
				player2 = unpaired_list[j]
				if player2['id'] in paired_in_fallback: continue
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
			# No action needed if not found here

		# Tentativo 2 Fallback: Forced Repeat
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
				  already_played_msg = " [RIPETUTO!]" if player2['id'] in player1.get('opponents', set()) else ""
				  white_id, black_id = assign_colors(player1, player2)
				  match = {"id": torneo["next_match_id"], "round": round_number, "white_player_id": white_id, "black_player_id": black_id, "result": None}
				  matches.append(match)
				  torneo["next_match_id"] += 1
				  paired_in_fallback.add(player1['id']) # Mark as paired
				  paired_in_fallback.add(player2['id'])
				  print(f" -> Fallback FORZATO: Appaiati {player1['id']} vs {player2['id']}{already_played_msg}")

		# Verifica Finale (Logica Invariata)
		final_paired_ids = {m.get('white_player_id') for m in matches if m.get('white_player_id')} | \
						   {m.get('black_player_id') for m in matches if m.get('black_player_id')}
		if bye_player_id: final_paired_ids.add(bye_player_id)
		
		final_unpaired_check = [p for p in active_players if p['id'] not in final_paired_ids]
		if final_unpaired_check:
			 print("ERRORE CRITICO FINALE PAIRING: Giocatori ancora non appaiati dopo tutti i fallback:")
			 for p in final_unpaired_check: print(f" - ID: {p['id']}")
		# --- Fine Logica Fallback ---


	# 4. Aggiornamento Statistiche Giocatori (Logica Invariata - omessa per brevità)
	#    Assicurati che aggiorni il 'players_dict' principale
	for match in matches:
		 if match.get("result") == "BYE": continue
		 white_player_id = match.get("white_player_id")
		 black_player_id = match.get("black_player_id")
		 if not white_player_id or not black_player_id: continue
		 white_p = players_dict.get(white_player_id)
		 black_p = players_dict.get(black_player_id)
		 if not white_p or not black_p: continue

		 # Lavora con SET nel dict principale
		 if not isinstance(white_p.get('opponents'), set): white_p['opponents'] = set(white_p.get('opponents', []))
		 if not isinstance(black_p.get('opponents'), set): black_p['opponents'] = set(black_p.get('opponents', []))

		 white_p["opponents"].add(black_player_id)
		 black_p["opponents"].add(white_player_id)
		 white_p["white_games"] = white_p.get("white_games", 0) + 1
		 black_p["black_games"] = black_p.get("black_games", 0) + 1
		 white_p["last_color"] = "white"
		 black_p["last_color"] = "black"
	# --- Fine Aggiornamento Statistiche ---

	# Ritorna le partite create
	return matches
# --- Input and Output Functions ---
def sanitize_filename(name):
	"""Rimuove/sostituisce caratteri problematici per i nomi dei file."""
	# Sostituisci spazi con underscore
	name = name.replace(' ', '_')
	# Rimuovi caratteri non alfanumerici o non underscore/trattino (puoi personalizzare)
	# Questa è una versione semplice, potresti volerne una più restrittiva/permissiva
	import re
	name = re.sub(r'[^\w\-]+', '', name)
	# Evita nomi vuoti dopo la pulizia
	if not name:
		name = "Torneo_Senza_Nome"
	# Opzionale: tronca nomi molto lunghi
	# max_len = 40
	# if len(name) > max_len:
	#    name = name[:max_len]
	return name
def input_players(players_db):
	"""Gestisce l'input dei giocatori per un torneo, permettendo l'inserimento
	   tramite Nome/Cognome/Elo (che verifica/aggiunge al DB) o tramite ID
	   di un giocatore esistente nel DB."""

	players_in_tournament = []
	added_player_ids = set() # Tiene traccia degli ID già aggiunti a QUESTO torneo

	print("\n--- Inserimento Giocatori ---")
	print("Puoi inserire un giocatore con 'Nome Cognome Elo' (es. Mario Rossi 1500)")
	print("Oppure, se il giocatore è già nel DB, inserisci direttamente il suo ID (es. ROSMA001)")

	while True:
		data = input(f"Inserisci dati giocatore {len(players_in_tournament) + 1} (o lascia vuoto per terminare): ").strip()

		if not data:
			if len(players_in_tournament) < 2:
				 print("Sono necessari almeno 2 giocatori per un torneo.")
				 continue # Richiedi di nuovo
			else:
				 break # Termina inserimento

		player_added_successfully = False
		player_id_to_add = None
		player_data_for_tournament = {}

		# --- Tentativo 1: Il dato inserito è un ID esistente? ---
		# Controlla se l'input corrisponde esattamente a un ID nel DB
		if data in players_db:
			potential_id = data
			if potential_id in added_player_ids:
				print(f"Errore: Il giocatore con ID {potential_id} è già stato aggiunto a questo torneo.")
			else:
				# ID valido ed esiste nel DB, non ancora aggiunto al torneo
				db_player = players_db[potential_id]
				player_id_to_add = potential_id
				# Prendi i dati principali dal DB
				first_name = db_player.get('first_name', 'N/D')
				last_name = db_player.get('last_name', 'N/D')
				current_elo = db_player.get('current_elo', 1500) # Default Elo se manca

				player_data_for_tournament = {
					"id": player_id_to_add,
					"first_name": first_name,
					"last_name": last_name,
					"initial_elo": current_elo, # Usa Elo attuale del DB come Elo iniziale torneo
					"points": 0.0,
					"results_history": [],
					"opponents": set(), # Inizia come set
					"white_games": 0,
					"black_games": 0,
					"last_color": None,
					"received_bye": False,
					"buchholz": 0.0,
					"performance_rating": None,
					"elo_change": None,
					"final_rank": None,
					"withdrawn": False
				}
				print(f"Giocatore {first_name} {last_name} (ID: {player_id_to_add}, Elo: {current_elo}) aggiunto dal DB.")
				player_added_successfully = True

		# --- Tentativo 2: Il dato è Nome Cognome Elo? ---
		else:
			try:
				parts = data.split()
				if len(parts) < 3: # Servono almeno Nome, Cognome, Elo
					 # Riprova: forse l'ID era scritto male? O è davvero Nome/Elo?
					 raise ValueError("Formato non riconosciuto. Richiesto 'Nome Cognome Elo' o un ID valido.")

				elo_str = parts[-1]
				elo = int(elo_str) # Questo genera ValueError se non è un numero

				# Gestione Nome/Cognome più robusta
				name_parts = parts[:-1] # Tutto tranne l'ultimo elemento (Elo)
				if len(name_parts) == 0:
					 raise ValueError("Nome e Cognome mancanti.")
				elif len(name_parts) == 1:
					 # Solo un nome fornito - usalo come Nome e Cognome? O richiedi?
					 # Assumiamo sia solo il nome, chiedi cognome? Per ora, usiamo Nome=Cognome
					 first_name = name_parts[0].title()
					 last_name = name_parts[0].title() # O metti un placeholder?
					 print(f"Warning: Inserito solo un nome '{first_name}'. Usato anche come cognome.")
				else:
					 # Più parti per nome/cognome
					 # Convenzione: ultima parte è cognome, il resto è nome
					 last_name = name_parts[-1].title()
					 first_name = " ".join(name_parts[:-1]).title()

				# Verifica/Aggiungi al DB e ottieni ID
				player_id_from_db = add_or_update_player_in_db(players_db, first_name, last_name, elo)

				if player_id_from_db in added_player_ids:
					 print(f"Errore: Il giocatore {first_name} {last_name} (ID: {player_id_from_db}) è già stato aggiunto a questo torneo.")
				else:
					player_id_to_add = player_id_from_db
					# Crea dati per il torneo usando i dati *inseriti*
					player_data_for_tournament = {
						"id": player_id_to_add,
						"first_name": first_name,
						"last_name": last_name,
						"initial_elo": elo, # Usa Elo fornito come Elo iniziale torneo
						"points": 0.0,
						"results_history": [],
						"opponents": set(), # Inizia come set
						"white_games": 0,
						"black_games": 0,
						"last_color": None,
						"received_bye": False,
						"buchholz": 0.0,
						"performance_rating": None,
						"elo_change": None,
						"final_rank": None,
						"withdrawn": False
					}
					# Messaggio stampato da add_or_update_player_in_db se nuovo/trovato
					player_added_successfully = True

			except ValueError as e: # Cattura sia int(elo) che errori manuali
				print(f"Input non valido: {e}. Riprova con 'Nome Cognome Elo' o un ID giocatore esistente.")
			except IndexError: # Errore se parts[-1] non esiste (raro con check len(parts)<3)
				 print("Formato input incompleto. Riprova.")
			except Exception as e:
				print(f"Errore imprevisto nell'inserimento giocatore: {e}")

		# --- Aggiungi al torneo se successo ---
		if player_added_successfully and player_id_to_add:
			players_in_tournament.append(player_data_for_tournament)
			added_player_ids.add(player_id_to_add)

	# Converti 'opponents' set in lista prima di restituire (per JSON)
	for p in players_in_tournament:
		p['opponents'] = list(p['opponents'])

	return players_in_tournament


def update_match_result(torneo):
	"""Chiede l'ID partita e aggiorna il risultato. 
	   Restituisce True se un risultato è stato aggiornato, False altrimenti (es. Invio vuoto)."""
	current_round_num = torneo["current_round"]
	# Assicura che players_dict sia disponibile e aggiornato
	if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
		torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
	players_dict = torneo['players_dict']

	# Trova le partite del turno corrente senza risultato valido (None)
	pending_matches_this_round = []
	current_round_data = None
	for r in torneo.get("rounds", []):
		 if r.get("round") == current_round_num:
			 current_round_data = r
			 for m in r.get("matches", []):
				 # Considera pendente solo se il risultato è None e non è un Bye già registrato
				 if m.get("result") is None and m.get("black_player_id") is not None:
					 pending_matches_this_round.append(m)
			 break # Trovato il turno corrente

	if not pending_matches_this_round:
		# Questo non dovrebbe essere chiamato se non ci sono partite pendenti,
		# ma mettiamo un controllo per sicurezza.
		# print("Info: Nessuna partita da registrare per il turno corrente.")
		return False # Nessuna partita da aggiornare

	print("\nPartite del turno {} ancora da registrare:".format(current_round_num))
	# Ordina per ID per visualizzazione consistente
	pending_matches_this_round.sort(key=lambda m: m.get('id', 0))
	for m in pending_matches_this_round:
		white_p = players_dict.get(m.get('white_player_id'))
		black_p = players_dict.get(m.get('black_player_id'))
		# Stampa solo se entrambi i giocatori sono trovati (dovrebbe sempre esserlo)
		if white_p and black_p:
			 w_name = f"{white_p.get('first_name','?')} {white_p.get('last_name','?')}"
			 w_elo = white_p.get('initial_elo','?')
			 b_name = f"{black_p.get('first_name','?')} {black_p.get('last_name','?')}"
			 b_elo = black_p.get('initial_elo','?')
			 print(f"  ID: {m.get('id','?')} - {w_name} [{w_elo}] vs {b_name} [{b_elo}]")
		else:
			 print(f"  ID: {m.get('id','?')} - Errore: Giocatore/i non trovato/i.")


	while True: # Loop finché non viene inserito un ID valido o vuoto
		match_id_str = input("Inserisci l'ID della partita da aggiornare (lascia vuoto per tornare indietro): ").strip()
		if not match_id_str:
			return False # L'utente vuole uscire dall'aggiornamento per ora

		try:
			match_id_to_update = int(match_id_str)

			# Cerca la partita con quell'ID tra quelle pendenti di questo turno
			match_to_update = None
			match_index_in_round = -1
			original_match_data = None # Per rollback punti in caso di ri-registrazione (non implementato)

			for i, m in enumerate(current_round_data.get("matches", [])):
				# Cerca per ID E assicurati che non sia già registrata (o sia un Bye)
				if m.get('id') == match_id_to_update:
					 if m.get("result") is None and m.get("black_player_id") is not None:
						   match_to_update = m
						   match_index_in_round = i
						   # original_match_data = m.copy() # Salva stato precedente se necessario
						   break
					 elif m.get("result") == "BYE":
						   print(f"Info: La partita {match_id_to_update} è un BYE, non modificabile.")
						   # Continua il loop while per chiedere un altro ID
					 else: # Partita trovata ma risultato già presente
						   print(f"Info: La partita {match_id_to_update} ha già un risultato ({m.get('result','?')}).")
						   # TODO: Chiedere se sovrascrivere? Per ora non permettiamo.
						   # Continua il loop while
					 break # Esce dal for perché l'ID è stato trovato (registrato o bye)


			if match_to_update: # Trovata partita pendente con ID corrispondente
				white_p = players_dict.get(match_to_update['white_player_id'])
				black_p = players_dict.get(match_to_update['black_player_id'])
				if not white_p or not black_p:
					 print(f"ERRORE: Giocatore non trovato per la partita {match_id_to_update}.")
					 continue # Richiedi ID

				print(f"Partita selezionata: {white_p['first_name']} {white_p['last_name']} vs {black_p['first_name']} {black_p['last_name']}")

				result_input = input("Inserisci risultato [B=Bianco vince(1-0), N=Nero vince(0-1), = = Patta(1/2-1/2), ?=Non giocata(0-0)]: ").strip().upper() # Usa upper per B/N

				new_result = None
				white_score = 0.0
				black_score = 0.0
				valid_input = True

				if result_input == 'B':
					new_result = "1-0"
					white_score = 1.0
				elif result_input == 'N':
					new_result = "0-1"
					black_score = 1.0
				elif result_input == '=':
					new_result = "1/2-1/2" # Manteniamo formato frazione per chiarezza
					white_score = 0.5
					black_score = 0.5
				elif result_input == '?':
					new_result = "0-0F" # 'F' per Forfait/Non giocata, distinto da 0-0 (raro ma possibile)
					white_score = 0.0
					black_score = 0.0
					print("Partita marcata come non giocata (0-0).")
				else:
					print("Input non valido. Usa 'B', 'N', '=', '?'.")
					valid_input = False
					# Continua il loop while per richiedere l'ID

				if valid_input and new_result is not None:
					 # --- Aggiorna Punti e Storico ---
					 # Nota: Se si permette la sovrascrittura, bisognerebbe prima stornare i punti vecchi.
					 
					 white_p["points"] = white_p.get("points", 0.0) + white_score
					 black_p["points"] = black_p.get("points", 0.0) + black_score

					 # Aggiungi allo storico risultati (evita duplicati se si sovrascrive)
					 # Modo semplice: rimuovi vecchio risultato per questa coppia in questo turno, poi aggiungi nuovo
					 # (Omettemmo per semplicità, assumiamo non si sovrascrive)
					 if "results_history" not in white_p: white_p["results_history"] = []
					 if "results_history" not in black_p: black_p["results_history"] = []

					 white_p["results_history"].append({
						 "round": current_round_num,
						 "opponent_id": black_p["id"],
						 "color": "white",
						 "result": new_result,
						 "score": white_score
					 })
					 black_p["results_history"].append({
						 "round": current_round_num,
						 "opponent_id": white_p["id"],
						 "color": "black",
						 "result": new_result,
						 "score": black_score
					 })

					 # --- Aggiorna il risultato nella struttura dati del torneo ---
					 # Modifica direttamente la partita nella lista originale del round
					 current_round_data["matches"][match_index_in_round]["result"] = new_result

					 print("Risultato registrato.")
					 return True # Indica che un aggiornamento è stato fatto

			elif match_index_in_round == -1: # ID non trovato tra nessuna partita di questo turno
				 print("ID partita non valido o non appartenente a questo turno. Riprova.")
			# Altrimenti (ID trovato ma già registrato o BYE), il messaggio è già stato stampato sopra.

		except ValueError:
			print("ID non valido. Inserisci un numero intero.")
			# Continua il loop while per richiedere l'ID


def save_round_text(round_number, torneo):
	"""Salva gli abbinamenti del turno in un file TXT con il formato richiesto."""
	tournament_name = torneo.get('name', 'Torneo_Senza_Nome') # Ottieni nome torneo
	sanitized_name = sanitize_filename(tournament_name)      # Pulisci nome
	filename = f"tornello - {sanitized_name} - turno{round_number}.txt"
	round_data = None
	for rnd in torneo.get("rounds", []):
		if rnd.get("round") == round_number:
			round_data = rnd
			break
	if round_data is None:
		print(f"Dati turno {round_number} non trovati per il salvataggio TXT.")
		return

	# Usa il dizionario interno per efficienza
	players_dict = torneo.get('players_dict', {p['id']: p for p in torneo.get('players', [])})

	try:
		with open(filename, "w", encoding='utf-8') as f:
			f.write(f"Torneo: {torneo.get('name', 'Nome Mancante')}\n")
			f.write(f"Turno: {round_number}\n")

			# Scrivi date turno
			round_dates_list = torneo.get("round_dates", [])
			current_round_dates = next((rd for rd in round_dates_list if rd.get("round") == round_number), None)
			if current_round_dates:
				start_d = current_round_dates.get('start_date','?')
				end_d = current_round_dates.get('end_date','?')
				f.write(f"Periodo: {start_d} - {end_d}\n")

			f.write("-" * 60 + "\n")
			# Intestazione più descrittiva
			f.write("ID | Bianco                   [Elo] (Pt) - Nero                    [Elo] (Pt) | Risultato\n")
			f.write("-" * 60 + "\n")

			# Ordina le partite per ID per consistenza
			sorted_matches = sorted(round_data.get("matches", []), key=lambda m: m.get('id', 0))

			for match in sorted_matches:
				match_id = match.get('id', '?')
				white_p_id = match.get('white_player_id')
				black_p_id = match.get('black_player_id')
				result_str = match.get("result") if match.get("result") is not None else "In corso"

				white_p = players_dict.get(white_p_id)

				if not white_p: # Giocatore bianco non trovato (errore dati)
					f.write(f"{match_id:<2} | Errore Giocatore Bianco ID: {white_p_id} | {result_str}\n")
					continue

				w_name = f"{white_p.get('first_name','?')} {white_p.get('last_name','')}"
				w_elo = white_p.get('initial_elo','?')
				w_pts = format_points(white_p.get('points', 0.0)) # Punti correnti

				if black_p_id is None: # Caso del Bye
					line = f"{match_id:<2} | {w_name:<24} [{w_elo:>4}] ({w_pts:<4}) - {'BYE':<31} | {result_str}\n"
				else:
					black_p = players_dict.get(black_p_id)
					if not black_p: # Giocatore nero non trovato
						f.write(f"{match_id:<2} | {w_name:<24} [{w_elo:>4}] ({w_pts:<4}) - Errore Giocatore Nero ID: {black_p_id} | {result_str}\n")
						continue

					b_name = f"{black_p.get('first_name','?')} {black_p.get('last_name','')}"
					b_elo = black_p.get('initial_elo','?')
					b_pts = format_points(black_p.get('points', 0.0)) # Punti correnti

					# Allinea i campi usando f-string formatting
					line = (f"{match_id:<2} | "
							f"{w_name:<24} [{w_elo:>4}] ({w_pts:<4}) - "
							f"{b_name:<24} [{b_elo:>4}] ({b_pts:<4}) | "
							f"{result_str}\n")
				f.write(line)
		print(f"File abbinamenti {filename} salvato.")
	except IOError as e:
		print(f"Errore durante il salvataggio del file {filename}: {e}")
	except Exception as general_e:
		 print(f"Errore inatteso durante save_round_text: {general_e}")


def save_standings_text(torneo, final=False):
	"""Salva la classifica (parziale o finale) in un file TXT con il formato richiesto."""
	players = torneo.get("players", [])
	if not players:
		 print("Warning: Nessun giocatore nel torneo per generare la classifica.")
		 return

	# Assicura che players_dict sia aggiornato
	torneo['players_dict'] = {p['id']: p for p in players}
	players_dict = torneo['players_dict']

	# Calcola Buchholz per tutti PRIMA dell'ordinamento
	for p in players:
		p["buchholz"] = compute_buchholz(p["id"], torneo)

	# Calcola Performance e Variazione Elo solo se finale
	if final:
		print("Calcolo Performance Rating e Variazione Elo per classifica finale...")
		for p in players:
			 # Usa il dizionario aggiornato per i calcoli
			 p["performance_rating"] = calculate_performance_rating(p, players_dict)
			 p["elo_change"] = calculate_elo_change(p, players_dict, k_factor=torneo.get("k_factor", DEFAULT_K_FACTOR)) # Usa K-factor del torneo se esiste

	# Ordina la classifica: Punti (desc), Buchholz (desc), Performance (desc, se finale), Elo iniziale (desc)
	def sort_key(player):
		points = player.get("points", 0.0)
		buchholz = player.get("buchholz", 0.0)
		# Se finale, usa performance; altrimenti usa 0 (non influenza sort)
		performance = player.get("performance_rating", 0) if final else 0
		elo_initial = player.get("initial_elo", 0)
		# Criteri: più alto è meglio, quindi usiamo negazione
		return (-points, -buchholz, -performance, -elo_initial)

	try:
		players_sorted = sorted(players, key=sort_key)
	except Exception as e:
		 print(f"Errore durante l'ordinamento dei giocatori: {e}")
		 players_sorted = players # Usa ordine non ordinato se sort fallisce

	# Assegna rank finale
	if final:
		for i, p in enumerate(players_sorted):
			p["final_rank"] = i + 1

	tournament_name = torneo.get('name', 'Torneo_Senza_Nome') # Ottieni nome torneo
	sanitized_name = sanitize_filename(tournament_name)      # Pulisci nome
	file_suffix = "classifica_finale" if final else "classifica_parziale"
	filename = f"tornello - {sanitized_name} - {file_suffix}.txt" # Nuovo nome file
	try:
		with open(filename, "w", encoding='utf-8') as f:
			f.write(f"Nome torneo: {torneo.get('name', 'N/D')}\n")
			if final:
				 f.write("CLASSIFICA FINALE\n")
			else:
				 # Turno precedente a quello corrente (es. dopo fine turno 1, siamo al turno 2, classifica è di fine 1)
				 completed_round = torneo.get("current_round", 1) - 1
				 f.write(f"Classifica Parziale - Dopo Turno {completed_round}\n")

			# Intestazione
			header = "Pos. Nome Cognome          [EloIni] Punti  Buchholz"
			if final:
				 header += "   Perf +/-Elo"
			f.write(header + "\n")
			f.write("=" * (len(header) + 2) + "\n") # Riga di separazione

			for i, player in enumerate(players_sorted, 1):
				rank = i if not final else player.get("final_rank", i) # Usa rank assegnato se finale
				name_str = f"{player.get('first_name','?')} {player.get('last_name','')}"
				elo_str = f"[{player.get('initial_elo','?'):>4}]" # Allinea a destra Elo
				pts_str = format_points(player.get('points', 0.0))
				buch_str = format_points(player.get('buchholz', 0.0))

				# Tronca nomi lunghi se necessario per allineamento
				max_name_len = 21
				if len(name_str) > max_name_len:
					name_str = name_str[:max_name_len-1] + "."

				line = f"{rank:<4} {name_str:<{max_name_len}} {elo_str:<8} {pts_str:<6} {buch_str:<8}" # Allineamenti

				if final:
					 perf_str = str(player.get('performance_rating', 'N/A'))
					 elo_change_val = player.get('elo_change') # Può essere None
					 # Formatta +/- Elo solo se non è None
					 elo_change_str = f"{elo_change_val:+}" if elo_change_val is not None else "N/A"
					 line += f" {perf_str:<7} {elo_change_str:<6}" # Allineamenti

				f.write(line + "\n")

		print(f"File classifica {filename} salvato.")
	except IOError as e:
		print(f"Errore durante il salvataggio del file classifica {filename}: {e}")
	except Exception as general_e:
		 print(f"Errore inatteso durante save_standings_text: {general_e}")
		 traceback.print_exc() # Stampa traceback per debug


# --- Main Application Logic ---

def display_status(torneo):
	"""Mostra lo stato attuale del torneo."""
	print("\n--- Stato Torneo ---")
	print(f"Nome: {torneo.get('name', 'N/D')}")
	start_d = torneo.get('start_date', '?')
	end_d = torneo.get('end_date', '?')
	print(f"Periodo: {start_d} - {end_d}")
	current_r = torneo.get('current_round', '?')
	total_r = torneo.get('total_rounds', '?')
	print(f"Turno Corrente: {current_r} / {total_r}")

	now = datetime.now()

	# Date turno corrente
	round_dates_list = torneo.get("round_dates", [])
	current_round_dates = next((rd for rd in round_dates_list if rd.get("round") == current_r), None)
	if current_round_dates:
		 r_start_str = current_round_dates.get('start_date','?')
		 r_end_str = current_round_dates.get('end_date','?')
		 print(f"Periodo Turno {current_r}: {r_start_str} - {r_end_str}")
		 try:
			 # Calcola fine giornata per confronto
			 round_end_dt = datetime.strptime(r_end_str, DATE_FORMAT).replace(hour=23, minute=59, second=59)
			 days_left_round = (round_end_dt - now).days
			 if now > round_end_dt: # Se siamo oltre la fine del giorno di fine turno
				 print(f"  -> Termine turno superato.")
			 elif days_left_round == 0:
				  print(f"  -> Ultimo giorno per completare il turno.")
			 else:
				 print(f"  -> Giorni rimanenti per il turno: {days_left_round}")
		 except (ValueError, TypeError):
			 print(f"  -> Date turno ('{r_start_str}', '{r_end_str}') non valide per calcolo giorni rimanenti.")

	# Giorni rimanenti torneo
	try:
		tournament_end_dt = datetime.strptime(end_d, DATE_FORMAT).replace(hour=23, minute=59, second=59)
		days_left_tournament = (tournament_end_dt - now).days
		if now > tournament_end_dt:
			print(f"Termine torneo superato.")
		elif days_left_tournament == 0:
			print(f"Ultimo giorno del torneo.")
		else:
			print(f"Giorni rimanenti alla fine del torneo: {days_left_tournament}")
	except (ValueError, TypeError):
		print(f"Data fine torneo ('{end_d}') non valida per calcolo giorni rimanenti.")

	# Partite Pendenti del turno corrente
	pending_matches_current_round = []
	# Usa dizionario giocatori per efficienza
	players_dict_status = torneo.get('players_dict', {p['id']: p for p in torneo.get('players', [])})
	
	found_current_round = False
	for r in torneo.get("rounds", []):
		if r.get("round") == current_r:
			found_current_round = True
			for m in r.get("matches", []):
				# Pendente se result è None E NON è un Bye (black_player_id esiste)
				if m.get("result") is None and m.get("black_player_id") is not None:
					 pending_matches_current_round.append(m)
			break # Trovato turno corrente

	if found_current_round and pending_matches_current_round:
		print(f"\nPartite da giocare/registrare per il Turno {current_r}:")
		# Ordina per ID
		pending_matches_current_round.sort(key=lambda m: m.get('id', 0))
		for m in pending_matches_current_round:
			white_p = players_dict_status.get(m.get('white_player_id'))
			black_p = players_dict_status.get(m.get('black_player_id'))
			if white_p and black_p:
				 w_name = f"{white_p.get('first_name','?')} {white_p.get('last_name','')}"
				 b_name = f"{black_p.get('first_name','?')} {black_p.get('last_name','')}"
				 print(f"  ID: {m.get('id','?')} - {w_name} vs {b_name}")
			else:
				  print(f"  ID: {m.get('id','?')} - Errore: Giocatore/i non trovato/i.")
	elif found_current_round:
		 # Controlla se siamo nell'ultimo turno o se il torneo è finito
		 if current_r is not None and total_r is not None and current_r <= total_r:
			print(f"\nTutte le partite del Turno {current_r} sono state registrate.")
	elif current_r is not None and total_r is not None and current_r > total_r:
		 print("\nIl torneo è concluso.") # Stato post-finalizzazione
	else:
		 print("\nDati turno corrente non trovati.")


	print("--------------------\n")


def finalize_tournament(torneo, players_db):
	 """Completa il torneo, calcola Elo/Performance, aggiorna DB giocatori."""
	 print("\n--- Finalizzazione Torneo ---")
	 
	 # Assicura dizionario giocatori aggiornato
	 players_dict = {p['id']: p for p in torneo.get('players', [])}
	 torneo['players_dict'] = players_dict
	 
	 num_players = len(torneo.get('players', []))
	 if num_players == 0:
		  print("Nessun giocatore nel torneo, impossibile finalizzare.")
		  return False # Indica fallimento

	 # 1. Calcola Performance e Variazione Elo per tutti (già fatto in save_standings finale)
	 #    Assicuriamoci sia fatto comunque.
	 print("Ricalcolo Performance Rating e Variazione Elo...")
	 k_factor = torneo.get("k_factor", DEFAULT_K_FACTOR)
	 for p in torneo.get('players',[]):
		 p_id = p.get('id')
		 if not p_id: continue
		 # Calcola Buchholz finale se non già fatto o None
		 if p.get("buchholz") is None:
			  p["buchholz"] = compute_buchholz(p_id, torneo)
		 # Calcola/Ricalcola performance ed Elo change
		 p["performance_rating"] = calculate_performance_rating(p, players_dict)
		 p["elo_change"] = calculate_elo_change(p, players_dict, k_factor)

	 # 2. Ordina per la classifica finale e assegna rank (già fatto in save_standings finale)
	 #    Rifacciamolo per sicurezza e per aggiornare p['final_rank']
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
		# Aggiorna la lista originale nel torneo con i rank assegnati
		torneo['players'] = players_sorted
	 except Exception as e:
		print(f"Errore durante ordinamento finale: {e}")
		# Non bloccare la finalizzazione, procedi senza rank aggiornati se fallisce

	 # 3. Salva classifica finale TXT (già fatto, ma lo rifacciamo per sicurezza con dati aggiornati)
	 save_standings_text(torneo, final=True)

	 # 4. Aggiorna DB Giocatori
	 print("Aggiornamento Database Giocatori...")
	 db_updated = False
	 for p in torneo.get('players',[]):
		 player_id = p.get('id')
		 final_rank = p.get('final_rank')
		 elo_change = p.get('elo_change')

		 if not player_id:
			  print("Warning: Giocatore senza ID trovato, impossibile aggiornare DB.")
			  continue
			  
		 if player_id in players_db:
			 db_player = players_db[player_id]
			 
			 # Aggiorna Elo
			 if elo_change is not None:
				 old_elo = db_player.get('current_elo', '?')
				 new_elo = db_player.get('current_elo', 1500) + elo_change # Usa 1500 se Elo DB manca
				 db_player['current_elo'] = new_elo
				 print(f" - ID {player_id}: Elo aggiornato da {old_elo} a {new_elo} ({elo_change:+})")
			 else:
				  print(f" - ID {player_id}: Variazione Elo non calcolata, Elo non aggiornato.")

			 # Aggiungi torneo alla lista (se non già presente per qualche motivo)
			 tournament_record = {
				 "tournament_name": torneo.get('name', 'N/D'),
				 "tournament_id": torneo.get('tournament_id', torneo.get('name', 'N/D')),
				 "rank": final_rank if final_rank is not None else 'N/A',
				 "total_players": num_players,
				 "date_completed": torneo.get('end_date', datetime.now().strftime(DATE_FORMAT)) # Data fine torneo
			 }
			 if 'tournaments_played' not in db_player: db_player['tournaments_played'] = []
			 # Evita di aggiungere lo stesso record più volte se finalize viene chiamato per errore più volte
			 if not any(t.get('tournament_id') == tournament_record['tournament_id'] for t in db_player['tournaments_played']):
				 db_player['tournaments_played'].append(tournament_record)
				 print(f" - ID {player_id}: Torneo '{tournament_record['tournament_name']}' aggiunto allo storico.")


			 # Aggiorna medagliere
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

			 db_updated = True # Segna che almeno un giocatore è stato processato per il salvataggio
		 else:
			 print(f"Attenzione: Giocatore con ID {player_id} (dal torneo) non trovato nel DB principale. Impossibile aggiornare storico/Elo.")

	 # 5. Salva il DB aggiornato (JSON e TXT) solo se ci sono state modifiche
	 if db_updated:
		  save_players_db(players_db)
		  print("Database Giocatori aggiornato e salvato.")
	 else:
		  print("Nessun aggiornamento necessario per il Database Giocatori.")

	 # 6. Rimuovere o archiviare il file del torneo?
	 tournament_name = torneo.get('name', 'Torneo_Senza_Nome') # Ottieni nome torneo
	 sanitized_name = sanitize_filename(tournament_name)      # Pulisci nome
	 # Definisci il nome del file archiviato
	 archive_name = f"tornello - {sanitized_name} - concluso.json" # Nuovo nome file archivio
	 try:
		  if os.path.exists(TOURNAMENT_FILE):
			   os.rename(TOURNAMENT_FILE, archive_name)
			   print(f"File torneo in corso '{TOURNAMENT_FILE}' archiviato come: '{archive_name}'")
		  else:
			   print(f"File torneo in corso '{TOURNAMENT_FILE}' non trovato, impossibile archiviare.")
	 except OSError as e:
		  print(f"Errore durante l'archiviazione del file del torneo: {e}")
		  print(f"Il file '{TOURNAMENT_FILE}' potrebbe essere rimasto.")
		  
	 return True # Finalizzazione completata (anche se con warning)


def main():
	print(f"Benvenuti in Tornello {VERSIONE} - Torneo di Scacchi")
	players_db = load_players_db()
	
	# Carica Torneo esistente, se c'è
	torneo = load_tournament()

	if torneo is None:
		print("Nessun torneo in corso trovato ({TOURNAMENT_FILE}). Creazione nuovo torneo.".format(TOURNAMENT_FILE=TOURNAMENT_FILE))
		torneo = {} # Inizia dizionario vuoto

		while True:
			 name = input("Inserisci il nome del torneo: ").strip()
			 if name:
				 torneo["name"] = name
				 break
			 else:
				 print("Il nome del torneo non può essere vuoto.")

		# Genera un ID univoco semplice per il torneo (basato su nome e data)
		t_id_base = "".join(c for c in torneo['name'][:15] if c.isalnum() or c in ['_','-']).rstrip()
		torneo["tournament_id"] = f"{t_id_base}_{datetime.now().strftime('%Y%m%d%H%M')}"

		# Input Date
		while True:
			try:
				start_date_str = input(f"Inserisci data inizio torneo (YYYY-MM-DD) [Default: oggi]: ").strip()
				if not start_date_str: start_date_str = datetime.now().strftime(DATE_FORMAT)
				start_dt = datetime.strptime(start_date_str, DATE_FORMAT) # Valida formato
				torneo["start_date"] = start_date_str
				break
			except ValueError:
				print("Formato data non valido. Riprova.")

		while True:
			try:
				end_date_str = input(f"Inserisci data fine torneo (YYYY-MM-DD) [Default: {torneo['start_date']}]: ").strip()
				if not end_date_str: end_date_str = torneo['start_date']
				end_dt = datetime.strptime(end_date_str, DATE_FORMAT)
				start_dt = datetime.strptime(torneo["start_date"], DATE_FORMAT) # Rileggi start_dt
				if end_dt < start_dt:
					print("La data di fine non può essere precedente alla data di inizio.")
				else:
					torneo["end_date"] = end_date_str
					break
			except ValueError:
				print("Formato data non valido. Riprova.")

		# Input Numero Turni
		while True:
			 try:
				 rounds_str = input("Inserisci il numero totale dei turni: ").strip()
				 total_rounds = int(rounds_str)
				 if total_rounds > 0:
					  torneo["total_rounds"] = total_rounds
					  break
				 else:
					  print("Il numero di turni deve essere positivo.")
			 except ValueError:
				 print("Inserisci un numero intero valido.")

		# Calcola date turni
		round_dates = calculate_dates(torneo["start_date"], torneo["end_date"], torneo["total_rounds"])
		if round_dates is None:
			 print("Errore fatale nel calcolo delle date dei turni. Il torneo non può essere creato.")
			 sys.exit(1)
		torneo["round_dates"] = round_dates

		# Input Giocatori (passa DB per controllo/aggiunta)
		torneo["players"] = input_players(players_db)
		if not torneo["players"] or len(torneo["players"]) < 2:
			print("Numero insufficiente di giocatori inseriti. Torneo annullato.")
			# Non salvare nulla e esci
			sys.exit(0)

		# Inizializza stato torneo
		torneo["current_round"] = 1
		torneo["rounds"] = [] # Lista di {"round": num, "matches": lista_partite}
		torneo["next_match_id"] = 1 # ID partita progressivo globale
		torneo["k_factor"] = DEFAULT_K_FACTOR # Fattore K di default (potrebbe essere chiesto)
		# 'players_dict' verrà creato/aggiornato quando serve

		# Prepara i giocatori (assicura struttura dati interna corretta)
		for p in torneo["players"]:
			p['opponents'] = set(p.get('opponents', [])) # Usa set internamente

		print("\nGenerazione abbinamenti per il Turno 1...")
		matches_r1 = pairing(torneo) # Modifica 'torneo' in-place (aggiunge a opponents, etc)
		torneo["rounds"].append({"round": 1, "matches": matches_r1})

		# Crea il dizionario per accesso rapido prima di salvare
		torneo['players_dict'] = {p['id']: p for p in torneo['players']}

		# Salva stato iniziale
		save_tournament(torneo)
		save_round_text(1, torneo)
		save_standings_text(torneo, final=False) # Salva classifica iniziale (Turno 0)

		print("\nTorneo creato e Turno 1 generato.")
		# Non esce, continua nel loop principale sotto

	else:
		print(f"Torneo '{torneo.get('name','N/D')}' in corso rilevato da {TOURNAMENT_FILE}.")
		# Assicura che i dati siano pronti per l'uso
		if 'players' not in torneo: torneo['players'] = []
		for p in torneo["players"]:
			p['opponents'] = set(p.get('opponents', [])) # Lavora con i set internamente
		torneo['players_dict'] = {p['id']: p for p in torneo['players']} # Rigenera dizionario

	# --- Main Loop ---
	try:
		while torneo.get("current_round", 0) <= torneo.get("total_rounds", 0):

			current_round_num = torneo["current_round"]
			print(f"\n--- Gestione Turno {current_round_num} ---")
			display_status(torneo) # Mostra stato attuale

			# Verifica se il turno corrente è già completato
			round_completed = True
			pending_in_round = False # Flag per vedere se ci sono partite da giocare
			round_data = None
			for r in torneo.get("rounds", []):
				 if r.get("round") == current_round_num:
					  round_data = r
					  for m in r.get("matches", []):
						   if m.get("result") is None and m.get("black_player_id") is not None:
								round_completed = False
								pending_in_round = True
								break # Trovata partita incompleta
					  break # Trovato round corrente

			if round_data is None and current_round_num <= torneo.get("total_rounds",0):
				 print(f"ERRORE: Dati per il turno corrente {current_round_num} non trovati!")
				 # Cosa fare? Provare a rigenerare? Uscire?
				 break # Esci dal loop principale

			if not round_completed and pending_in_round:
				print("Inserisci i risultati delle partite:")
				while pending_in_round: # Loop finché ci sono partite pendenti o l'utente esce
					updated = update_match_result(torneo) # Chiama la funzione di input

					if updated: # Se è stato inserito un risultato valido (True restituito)
						# Salva lo stato del torneo dopo ogni risultato inserito
						save_tournament(torneo)
						# Aggiorna dizionario interno dopo salvataggio (anche se save non lo tocca più)
						torneo['players_dict'] = {p['id']: p for p in torneo['players']}

						# Dopo un aggiornamento, riverifica subito se il turno è ora completo
						any_pending_left = False
						for m in round_data.get("matches", []):
							 if m.get("result") is None and m.get("black_player_id") is not None:
								  any_pending_left = True
								  break
						
						if not any_pending_left:
							print("\nTutte le partite del turno sono state registrate.")
							round_completed = True
							pending_in_round = False # Forza uscita dal loop input
							# break # Esce dal loop di inserimento risultati perché finito
						# Altrimenti (ci sono altre partite), il loop while continua chiedendo ID

					else: # Se update_match_result restituisce False (Invio a vuoto)
						print("Uscita dalla modalità inserimento risultati per questo turno.")
						pending_in_round = False # Forza uscita dal loop input
						# break # Esce SEMPRE dal loop di inserimento se l'utente preme Invio

			# Dopo il loop di input (o se era già completo)
			# Ricontrolla lo stato di completamento finale
			final_round_check_completed = True
			if round_data: # Se abbiamo i dati del turno
				 for m in round_data.get("matches", []):
					 if m.get("result") is None and m.get("black_player_id") is not None:
						 final_round_check_completed = False
						 break
			else: # Se non ci sono dati del turno (es. appena finito l'ultimo)
				 if current_round_num <= torneo.get("total_rounds",0):
					  final_round_check_completed = False # Non può essere completo se mancano i dati


			if final_round_check_completed:
				print(f"\nTurno {current_round_num} completato.")

				# Salva file TXT del turno (con risultati finali)
				save_round_text(current_round_num, torneo)

				# Salva classifica parziale/finale
				is_final_round = (current_round_num == torneo["total_rounds"])
				save_standings_text(torneo, final=is_final_round) # Passa flag 'final'

				if is_final_round:
					if finalize_tournament(torneo, players_db):
						 print("\n--- Torneo Concluso e Finalizzato ---")
					else:
						 print("\n--- Errore durante la Finalizzazione del Torneo ---")
					break # Esce dal loop principale dei turni
				else:
					# Prepara il prossimo turno
					next_round_num = current_round_num + 1
					print(f"\nGenerazione abbinamenti per il Turno {next_round_num}...")

					# Assicura che 'opponents' sia un set prima del pairing
					for p in torneo["players"]: p['opponents'] = set(p.get('opponents', []))

					try:
						next_matches = pairing(torneo) # Modifica 'torneo' in-place
						torneo["current_round"] = next_round_num # AVANZA IL TURNO QUI
						torneo["rounds"].append({"round": next_round_num, "matches": next_matches})

						# Salva stato torneo e file del nuovo turno
						save_tournament(torneo) # Salva con il nuovo turno e matches
						save_round_text(next_round_num, torneo) # Salva TXT del nuovo turno

						print(f"Turno {next_round_num} generato e salvato.")

					except Exception as e:
						print(f"\nERRORE CRITICO durante la generazione del turno {next_round_num}: {e}")
						print("Il torneo potrebbe essere in uno stato inconsistente.")
						traceback.print_exc()
						break # Interrompi il torneo


			else: # Turno non completato (l'utente è uscito dall'input o non ha iniziato)
				 print(f"\nIl Turno {current_round_num} non è ancora completo.")
				 print("Rilanciare il programma per continuare a inserire i risultati.")
				 break # Esce dal loop principale, richiede riavvio per continuare


	except KeyboardInterrupt:
		print("\nOperazione interrotta dall'utente.")
		# Considera di salvare lo stato attuale prima di uscire?
		if torneo and 'players' in torneo: # Salva solo se un torneo è caricato/in corso
			 print("Salvataggio dello stato attuale del torneo...")
			 save_tournament(torneo)
			 print("Stato salvato. Uscita.")
		sys.exit(0)
	# Gestione errore critico spostata fuori dal while principale


	print("\nProgramma terminato.")


if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		# Già gestito nel main loop, ma per sicurezza
		print("\nUscita forzata.")
		sys.exit(0)
	except Exception as e:
		 print(f"\nERRORE CRITICO NON GESTITO nel flusso principale: {e}")
		 print("Si consiglia di controllare i file JSON per eventuali corruzioni.")
		 traceback.print_exc()
		 sys.exit(1)