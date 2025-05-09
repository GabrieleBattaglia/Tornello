# Tornello by Gabriele Battaglia & Gemini 2.5
# Data concepimento: 28 marzo 2025
import os
import json
import sys
import math
import traceback
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
# --- Constants ---
VERSIONE = "4.0.0 del 9 maggio 2025"
PLAYER_DB_FILE = "tornello - giocatori_db.json"
PLAYER_DB_TXT_FILE = "tornello - giocatori_db.txt"
TOURNAMENT_FILE = "Tornello - torneo.json"
DATE_FORMAT_ISO = "%Y-%m-%d"
DEFAULT_ELO = 1399.0
DEFAULT_K_FACTOR = 20
# Costanti per regole colore FIDE
MAX_COLOR_DIFFERENCE = 2
MAX_CONSECUTIVE_SAME_COLOR = 2 # Un giocatore può giocare MAX 2 volte di fila con lo stesso colore

# --- Helper Functions --- (Incluse funzioni di calcolo tiebreak)

def get_k_factor(player_db_data, tournament_start_date_str):
    """
    Determina il K-Factor FIDE per un giocatore all'inizio del torneo.
    Basato su regole indicative (potrebbero variare leggermente nel tempo).
    Args:
        player_db_data (dict): Dati del giocatore dal DB principale (Elo/partite PRIMA del torneo).
        tournament_start_date_str (str): Data inizio torneo in formato YYYY-MM-DD.
    Returns:
        int: Il K-Factor appropriato (40, 20, o 10).
    """
    if not player_db_data:
        return DEFAULT_K_FACTOR # Fallback se dati non trovati

    try:
        # Usa l'Elo che il giocatore aveva PRIMA del torneo (dal DB)
        elo = float(player_db_data.get('current_elo', DEFAULT_ELO))
    except (ValueError, TypeError):
        elo = DEFAULT_ELO # Fallback se Elo non valido

    games_before_tournament = player_db_data.get('games_played', 0)
    birth_date_str = player_db_data.get('birth_date')

    # Calcola età all'inizio del torneo
    age = None
    if birth_date_str and tournament_start_date_str:
        try:
            birth_dt = datetime.strptime(birth_date_str, DATE_FORMAT_ISO)
            start_dt = datetime.strptime(tournament_start_date_str, DATE_FORMAT_ISO)
            # Calcola differenza in anni
            age = relativedelta(start_dt, birth_dt).years
            # print(f"DEBUG get_k_factor: Player {player_db_data.get('id')}, Birth: {birth_date_str}, Start: {tournament_start_date_str}, Age: {age}")
        except (ValueError, TypeError):
            # print(f"DEBUG get_k_factor: Errore calcolo età per {player_db_data.get('id')}")
            pass # Ignora date non valide

    # Applica regole K-Factor FIDE (controlla documentazione FIDE per regole più aggiornate)
    # Logica basata sulle regole comuni (es. 2023/2024)

    # 1. Giocatori con poche partite
    if games_before_tournament < 30:
        # print(f"DEBUG get_k_factor: Player {player_db_data.get('id')} -> K=40 (Games < 30)")
        return 40

    # 2. Giocatori Under 18 (se età calcolabile) con Elo < 2300
    if age is not None and age < 18 and elo < 2300:
        # print(f"DEBUG get_k_factor: Player {player_db_data.get('id')} -> K=40 (U18 Elo < 2300)")
        return 40

    # 3. Giocatori con Elo < 2400 (e >= 30 partite)
    if elo < 2400:
        # print(f"DEBUG get_k_factor: Player {player_db_data.get('id')} -> K=20 (Elo < 2400)")
        return 20

    # 4. Giocatori con Elo >= 2400 (e >= 30 partite)
    else:
        # print(f"DEBUG get_k_factor: Player {player_db_data.get('id')} -> K=10 (Elo >= 2400)")
        return 10

def format_rank_ordinal(rank):
    """Formatta il rank come numero ordinale italiano (es. 1°, 6°) o 'RIT'."""
    if rank == "RIT":
        return "RIT"
    try:
        # Prova a convertire in intero
        rank_int = int(rank)
        # Aggiunge il simbolo di grado per l'ordinale
        return f"{rank_int}°"
    except (ValueError, TypeError):
        # Se il rank non è 'RIT' e non è convertibile in intero, ritorna '?'
        return "?" # Fallback per rank non validi o non numerici

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
        # Indentazione corretta
        return str(date_input)

def format_points(points):
    """Formatta i punti per la visualizzazione (intero se .0, altrimenti decimale)."""
    try:
        points = float(points)
        return str(int(points)) if points == int(points) else f"{points:.1f}"
    except (ValueError, TypeError):
        # Indentazione corretta
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
                # Inizializza campi mancanti se necessario all'avvio
                for p in db_list:
                    medals_dict = p.setdefault('medals', {})
                    medals_dict.setdefault('gold', 0)
                    medals_dict.setdefault('silver', 0)
                    medals_dict.setdefault('bronze', 0)
                    medals_dict.setdefault('wood', 0)  # <-- Aggiunto controllo specifico per 'wood'
                    p.setdefault('tournaments_played', [])
                return {p['id']: p for p in db_list}
        except (json.JSONDecodeError, IOError) as e:
            # Indentazione corretta
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
        # Indentazione corretta
        print(f"Errore durante il salvataggio del DB giocatori ({PLAYER_DB_FILE}): {e}")
    except Exception as e:
        # Indentazione corretta
        print(f"Errore imprevisto durante il salvataggio del DB: {e}")

# Assicurati che la funzione get_k_factor sia definita prima di questa
# e che datetime sia importato (from datetime import datetime)

def save_players_db_txt(players_db):
    """Genera un file TXT leggibile con lo stato del database giocatori,
       includendo partite giocate totali e K-Factor attuale."""
    try:
        with open(PLAYER_DB_TXT_FILE, "w", encoding='utf-8-sig') as f: # Usiamo utf-8-sig
            now = datetime.now()
            current_date_iso = now.strftime(DATE_FORMAT_ISO) # Data corrente per calcolo K
            f.write(f"Report Database Giocatori Tornello - {format_date_locale(now.date())} {now.strftime('%H:%M:%S')}\n")
            f.write("=" * 40 + "\n\n")
            sorted_players = sorted(players_db.values(), key=lambda p: (p.get('last_name',''), p.get('first_name','')))
            if not sorted_players:
                f.write("Il database dei giocatori è vuoto.\n")
                return
            for player in sorted_players:
                player_id = player.get('id', 'N/D') # Prendi ID per passarlo a get_k_factor (utile per debug lì)
                f.write(f"ID: {player_id}, ")
                f.write(f"{player.get('first_name', 'N/D')} {player.get('last_name', 'N/D')}, ")
                f.write(f"Elo: {player.get('current_elo', 'N/D')}\n")
                games_played_total = player.get('games_played', 0)
                f.write(f"\tPartite Valutate Totali: {games_played_total}, ")
                current_k_factor = get_k_factor(player, current_date_iso)
                f.write(f"K-Factor Stimato: {current_k_factor}, ")
                f.write(f"Data Iscrizione DB: {format_date_locale(player.get('registration_date'))}\n")
                birth_date_display = player.get('birth_date')
                f.write(f"\tData Nascita: {format_date_locale(birth_date_display) if birth_date_display else 'N/D'}\n") # Mostra anche data nascita
                medals = player.get('medals', {'gold': 0, 'silver': 0, 'bronze': 0, 'wood': 0})
                f.write(f"\tMedagliere: Oro: {medals.get('gold',0)}, Argento: {medals.get('silver',0)}, Bronzo: {medals.get('bronze',0)}, Legno: {medals.get('wood',0)} in ")
                tournaments = player.get('tournaments_played', [])
                f.write(f"({len(tournaments)}) tornei:\n")
                if tournaments:
                    try:
                        tournaments_sorted = sorted(
                            tournaments,
                            key=lambda t: datetime.strptime(t.get('date_completed', '1900-01-01'), DATE_FORMAT_ISO),
                            reverse=True
                        )
                    except ValueError:
                        tournaments_sorted = tournaments # Mantieni ordine originale se date non valide
                    for t in tournaments_sorted: # Non serve più l'indice 'i' separato
                         rank_val = t.get('rank', '?')
                         t_name = t.get('tournament_name', 'Nome Torneo Mancante')
                         start_date_iso = t.get('date_started') # Prende la nuova data ISO di inizio
                         end_date_iso = t.get('date_completed') # Data di completamento
                         rank_formatted = format_rank_ordinal(rank_val) # Usa la nuova funzione helper
                         start_date_formatted = format_date_locale(start_date_iso)
                         end_date_formatted = format_date_locale(end_date_iso)
                         history_line = f"{rank_formatted}° in {t_name} - {start_date_formatted} - {end_date_formatted}"
                         f.write(f"\t{history_line}\n")
                else:
                    f.write("\tNessuno\n")
                f.write("\t" + "-" * 30 + "\n")
    except IOError as e:
        print(f"Errore durante il salvataggio del file TXT del DB giocatori ({PLAYER_DB_TXT_FILE}): {e}")
    except Exception as e:
        print(f"Errore imprevisto durante il salvataggio del TXT del DB: {e}")
        traceback.print_exc() # Stampa traceback per errori non gestiti
def add_or_update_player_in_db(players_db, first_name, last_name, elo):
    """
    Aggiunge un nuovo giocatore al DB principale o verifica se esiste già.
    Riceve nome e cognome GIA' SEPARATI. Ritorna l'ID del giocatore (nuovo o esistente).
    Include la logica di generazione ID internamente.
    """
    norm_first = first_name.strip().title()
    norm_last = last_name.strip().title() # Ora può contenere spazi, es "Di Bari"

    if not norm_first or not norm_last:
         print("Errore: Nome e Cognome non possono essere vuoti.")
         return None # Segnala errore

    # Cerca giocatore esistente nel DB principale per Nome e Cognome
    existing_id = None
    for pid, pdata in players_db.items():
        # Confronto case-insensitive per sicurezza
        if pdata.get('first_name', '').lower() == norm_first.lower() and \
           pdata.get('last_name', '').lower() == norm_last.lower():
            existing_id = pid
            break

    if existing_id:
        # Giocatore trovato nel DB principale
        print(f"Info: Giocatore {norm_first} {norm_last} (ID: {existing_id}) già presente nel DB.")
        # Non aggiorniamo l'ELO nel DB principale qui per mantenere il comportamento originale.
        # L'elo specifico per il torneo viene gestito in input_players.
        return existing_id # Ritorna l'ID esistente
    else:
        # Giocatore non trovato, creane uno nuovo nel DB principale
        print(f"Giocatore {norm_first} {norm_last} non trovato nel DB. Aggiungo...")

        # --- INIZIO Logica Generazione ID (presa dal tuo codice originale e adattata) ---
        # Nota: .split() qui rimuove spazi interni dal cognome/nome PRIMA di prendere le iniziali.
        # Se vuoi iniziali da "Di Bari" come DB, questo va bene. Se volessi "DB", servirebbe logica diversa.
        last_part_cleaned = ''.join(norm_last.split())
        first_part_cleaned = ''.join(norm_first.split())

        last_initials = last_part_cleaned[:3].upper()
        first_initials = first_part_cleaned[:2].upper()
        while len(last_initials) < 3: last_initials += 'X'
        while len(first_initials) < 2: first_initials += 'X'
        base_id = f"{last_initials}{first_initials}"

        # Gestione sicurezza se base_id diventa vuoto per input strani
        if not base_id: base_id = "XX00"

        count = 1
        new_id = f"{base_id}{count:03d}"
        max_attempts = 1000
        current_attempt = 0
        while new_id in players_db and current_attempt < max_attempts:
            count += 1
            new_id = f"{base_id}{count:03d}"
            current_attempt += 1

        if new_id in players_db: # Fallback se ancora in collisione
            print(f"ATTENZIONE: Impossibile generare ID univoco standard per {norm_first} {norm_last} dopo {max_attempts} tentativi.")
            fallback_suffix = hash(datetime.now()) % 10000 # Usa hash per il fallback
            new_id = f"{base_id}{fallback_suffix:04d}"
            if new_id in players_db:
                 print("ERRORE CRITICO: Fallback ID collision. Usare ID temporaneo.")
                 new_id = f"TEMP_{base_id}_{fallback_suffix}" # ID temporaneo di emergenza
        # --- FINE Logica Generazione ID ---

        # Crea nuovo record giocatore per il DB principale
        new_player = {
            "id": new_id,
            "first_name": norm_first,
            "last_name": norm_last, # Cognome completo
            # Memorizza l'elo fornito come ELO CORRENTE nel database principale
            "current_elo": elo,
            "registration_date": datetime.now().strftime(DATE_FORMAT_ISO),
            "birth_date": None,   # Valuta se chiederla nell'input manuale
            "games_played": 0,    # Default per nuovo giocatore
            "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0}, # Include wood
            "tournaments_played": [], # Lista vuota all'inizio
            # Aggiungi qui altri campi base che OGNI giocatore deve avere nel DB, inizializzati
            # es: "downfloat_count": 0, # Se questo è un attributo globale del giocatore
        }
        players_db[new_id] = new_player # Aggiunge il nuovo giocatore al dizionario in memoria
        print(f"Nuovo giocatore aggiunto al DB con ID {new_id}.")
        # Salva immediatamente il DB principale aggiornato su file
        save_players_db(players_db)
        return new_id # Ritorna il nuovo ID creato

def load_tournament():
    """Carica lo stato del torneo corrente dal file JSON."""
    if os.path.exists(TOURNAMENT_FILE):
        try:
            with open(TOURNAMENT_FILE, "r", encoding='utf-8') as f:
                # Indentazione corretta
                torneo_data = json.load(f)
                # Re-inizializza i set e campi necessari dopo il caricamento
                if 'players' in torneo_data:
                    for p in torneo_data['players']:
                        p['opponents'] = set(p.get('opponents', [])) # Ricrea il set
                        p.setdefault('white_games', 0)
                        p.setdefault('black_games', 0)
                        p.setdefault('last_color', None)
                        p.setdefault('received_bye', False)
                        p.setdefault('consecutive_white', 0)
                        p.setdefault('consecutive_black', 0)
                        p.setdefault('withdrawn', False)
                        p.setdefault('results_history', [])
                return torneo_data
        except (json.JSONDecodeError, IOError) as e:
            # Indentazione corretta
            print(f"Errore durante il caricamento del torneo ({TOURNAMENT_FILE}): {e}")
            return None
    return None

def save_tournament(torneo):
    """Salva lo stato corrente del torneo nel file JSON."""
    try:
        torneo_to_save = torneo.copy()
        # Prepara i dati per il salvataggio JSON
        if 'players' in torneo_to_save:
            # Indentazione corretta
            temp_players = []
            for p in torneo_to_save['players']:
                player_copy = p.copy()
                # Converti set in lista PRIMA di salvare
                player_copy['opponents'] = list(player_copy.get('opponents', set()))
                temp_players.append(player_copy)
            torneo_to_save['players'] = temp_players
        # Rimuovi il dizionario cache che non è serializzabile o necessario salvare
        if 'players_dict' in torneo_to_save:
            # Indentazione corretta
            del torneo_to_save['players_dict']
        with open(TOURNAMENT_FILE, "w", encoding='utf-8') as f:
            json.dump(torneo_to_save, f, indent=4, ensure_ascii=False)
    except IOError as e:
        # Indentazione corretta
        print(f"Errore durante il salvataggio del torneo ({TOURNAMENT_FILE}): {e}")
    except Exception as e:
        # Indentazione corretta
        print(f"Errore imprevisto durante il salvataggio del torneo: {e}")
        traceback.print_exc() # Stampa più dettagli in caso di errore non previsto

def get_player_by_id(torneo, player_id):
    """Restituisce i dati del giocatore nel torneo dato il suo ID, usando il dizionario interno."""
    # Ricrea il dizionario se non esiste o sembra obsoleto
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
        if total_rounds <= 0:
            # Indentazione corretta
            print("Errore: Numero di turni deve essere positivo.")
            return None
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
                # Avanza data solo se non è l'ultimo turno e non supera la data finale
                if i < total_rounds - 1:
                    # Indentazione corretta
                    next_day = current_date + timedelta(days=1)
                    if next_day <= end_date:
                        current_date = next_day
                    # Altrimenti, l'ultimo giorno viene riutilizzato
            return round_dates
        # Distribuzione più equa
        days_per_round_float = total_duration / total_rounds
        round_dates = []
        current_start_date = start_date
        accumulated_days = 0.0
        for i in range(total_rounds):
            round_num = i + 1
            accumulated_days += days_per_round_float
            # Determina l'offset del giorno di fine basato sull'accumulo arrotondato
            end_day_offset = round(accumulated_days)
            # L'offset del giorno di inizio è l'offset finale del turno precedente
            start_day_offset = round(accumulated_days - days_per_round_float) if i > 0 else 0
            # Calcola i giorni effettivi per questo turno
            current_round_days = end_day_offset - start_day_offset
            # Assicura almeno 1 giorno per turno
            if current_round_days <= 0: current_round_days = 1
            # Calcola la data di fine
            current_end_date = current_start_date + timedelta(days=current_round_days - 1)
            # Assicura che l'ultima data di fine sia quella del torneo
            if round_num == total_rounds:
                # Indentazione corretta
                current_end_date = end_date
            # Assicura che le date intermedie non superino la data finale del torneo
            elif current_end_date > end_date:
                # Indentazione corretta
                current_end_date = end_date
            round_dates.append({
                "round": round_num,
                "start_date": current_start_date.strftime(DATE_FORMAT_ISO),
                "end_date": current_end_date.strftime(DATE_FORMAT_ISO)
            })
            # Prepara la data di inizio per il prossimo turno
            next_start_candidate = current_end_date + timedelta(days=1)
            # Se non c'è più spazio, usa l'ultimo giorno disponibile
            if next_start_candidate > end_date and round_num < total_rounds:
                print(f"Avviso: Spazio insufficiente per i turni rimanenti. Il turno {round_num+1} inizierà il {format_date_locale(end_date)} (ultimo giorno).")
                current_start_date = end_date
            else:
                # Indentazione corretta
                current_start_date = next_start_candidate
        return round_dates
    except ValueError:
        # Indentazione corretta
        print(f"Formato data non valido ('{start_date_str}' o '{end_date_str}'). Usa YYYY-MM-DD.")
        return None
    except Exception as e:
        # Indentazione corretta
        print(f"Errore nel calcolo delle date: {e}")
        return None

# --- Elo Calculation Functions ---
def calculate_expected_score(player_elo, opponent_elo):
    """Calcola il punteggio atteso di un giocatore contro un avversario."""
    try:
        p_elo = float(player_elo)
        o_elo = float(opponent_elo)
        # Limita la differenza Elo a +/- 400 come da specifiche FIDE
        diff = max(-400, min(400, o_elo - p_elo))
        return 1 / (1 + 10**(diff / 400))
    except (ValueError, TypeError):
        # Indentazione corretta
        print(f"Warning: Elo non valido ({player_elo} o {opponent_elo}) nel calcolo atteso.")
        return 0.5 # Ritorna 0.5 in caso di Elo non validi

def calculate_elo_change(player, tournament_players_dict):
    """Calcola la variazione Elo per un giocatore basata sulle partite del torneo."""
    if not player or 'initial_elo' not in player or 'results_history' not in player:
        print(f"Warning: Dati giocatore incompleti per calcolo Elo ({player.get('id','ID Mancante')}).")
        return 0

    # --- USA IL K-FACTOR SPECIFICO DEL GIOCATORE ---
    # Questo K viene determinato in finalize_tournament e salvato in p['k_factor']
    # Usiamo DEFAULT_K_FACTOR come fallback se non trovato (non dovrebbe succedere)
    k = player.get('k_factor', DEFAULT_K_FACTOR)
    # --- FINE MODIFICA K-FACTOR ---
    total_expected_score = 0.0
    actual_score = 0.0
    games_played_count = 0 # Rinomina variabile locale per chiarezza
    initial_elo = player['initial_elo']
    try:
        initial_elo = float(initial_elo)
    except (ValueError, TypeError):
        print(f"Warning: Elo iniziale non valido ({initial_elo}) per giocatore {player.get('id','ID Mancante')}. Usato {DEFAULT_ELO}].")
        initial_elo = DEFAULT_ELO

    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        score = result_entry.get("score")

        # Salta BYE e partite senza avversario o punteggio valido
        if opponent_id is None or opponent_id == "BYE_PLAYER_ID" or score is None:
            continue

        # Salta partite marcate come 0-0F (Forfait/Non giocate) nel calcolo Elo
        # (il risultato è 0-0 ma non conta come partita giocata ai fini Elo)
        # NOTA: Potrebbe essere necessario marcare esplicitamente queste partite
        #       se la logica attuale non distingue "0-0F" da un pareggio 0.5-0.5
        #       Per ora, assumiamo che "score" sia None o 0.0 per forfait.
        #       Se usi "0-0F" come result string, potremmo aggiungere un check qui.
        # if result_entry.get("result") == "0-0F": continue # Opzionale

        opponent = tournament_players_dict.get(opponent_id)
        if not opponent or 'initial_elo' not in opponent:
            print(f"Warning: Avversario {opponent_id} non trovato o Elo mancante per calcolo Elo.")
            continue

        try:
            opponent_elo = float(opponent['initial_elo'])
            score = float(score)
        except (ValueError, TypeError):
            print(f"Warning: Elo avversario ({opponent.get('initial_elo')}) o score ({score}) non validi per partita contro {opponent_id}.")
            continue

        expected_score = calculate_expected_score(initial_elo, opponent_elo)
        total_expected_score += expected_score
        actual_score += score
        games_played_count += 1 # Conta solo partite valide per Elo

    if games_played_count == 0:
        return 0

    # Calcolo variazione Elo grezza usando il K specifico
    elo_change_raw = k * (actual_score - total_expected_score)

    # Arrotondamento FIDE standard
    if elo_change_raw > 0:
        return math.floor(elo_change_raw + 0.5)
    else:
        return math.ceil(elo_change_raw - 0.5)

def calculate_performance_rating(player, tournament_players_dict):
    """Calcola la Performance Rating di un giocatore."""
    if not player or 'initial_elo' not in player or 'results_history' not in player:
        # Indentazione corretta
        # Ritorna l'Elo iniziale se non ci sono dati sufficienti
        return player.get('initial_elo', DEFAULT_ELO)
    opponent_elos = []
    total_score = 0.0
    games_played_for_perf = 0
    try:
        initial_elo = float(player['initial_elo'])
    except (ValueError, TypeError):
        # Indentazione corretta
        initial_elo = DEFAULT_ELO # Fallback se Elo iniziale non valido
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        score = result_entry.get("score")
        # Salta BYE e partite senza avversario o punteggio
        if opponent_id is None or opponent_id == "BYE_PLAYER_ID" or score is None:
            continue
        opponent = tournament_players_dict.get(opponent_id)
        if not opponent or 'initial_elo' not in opponent:
            # Indentazione corretta
            print(f"Warning: Avversario {opponent_id} non trovato o Elo mancante per calcolo Performance.")
            continue
        try:
            # Indentazione corretta
            opponent_elo = float(opponent["initial_elo"])
            total_score += float(score)
            opponent_elos.append(opponent_elo)
            games_played_for_perf += 1
        except (ValueError, TypeError):
            # Indentazione corretta
            print(f"Warning: Dati non validi (Elo avversario {opponent.get('initial_elo')} o score {score}) per partita vs {opponent_id} nel calcolo performance.")
            continue
    if games_played_for_perf == 0:
        # Se non ci sono state partite valide, ritorna l'Elo iniziale
        return round(initial_elo)
    # Calcola media Elo avversari
    avg_opponent_elo = sum(opponent_elos) / games_played_for_perf
    # Calcola percentuale punteggio
    score_percentage = total_score / games_played_for_perf
    # Mappa FIDE p -> dp (differenza performance)
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
        # Per p < 0.50, usiamo la simmetria dp(p) = -dp(1-p)
        0.49: -7, 0.48: -14, 0.47: -21, 0.46: -29, 0.45: -36, 0.44: -43,
        0.43: -50, 0.42: -57, 0.41: -65, 0.40: -72, 0.39: -80, 0.38: -87,
        0.37: -95, 0.36: -102, 0.35: -110, 0.34: -117, 0.33: -125, 0.32: -133,
        0.31: -141, 0.30: -149, 0.29: -158, 0.28: -166, 0.27: -175, 0.26: -184,
        0.25: -193, 0.24: -202, 0.23: -211, 0.22: -220, 0.21: -230, 0.20: -240,
        0.19: -251, 0.18: -262, 0.17: -273, 0.16: -284, 0.15: -296, 0.14: -309,
        0.13: -322, 0.12: -336, 0.11: -351, 0.10: -366, 0.09: -383, 0.08: -401,
        0.07: -422, 0.06: -444, 0.05: -470, 0.04: -501, 0.03: -538, 0.02: -589,
        0.01: -677, 0.0: -800
    }
    # Arrotonda la percentuale al centesimo più vicino per il lookup
    lookup_p = round(score_percentage, 2)
    # Gestisce casi limite
    if lookup_p < 0.0: lookup_p = 0.0
    if lookup_p > 1.0: lookup_p = 1.0
    # Ottieni dp dalla mappa, con fallback a +/- 800 per sicurezza
    dp = dp_map.get(lookup_p, 800 if lookup_p > 0.5 else -800)
    # Calcola performance
    performance = avg_opponent_elo + dp
    # Ritorna la performance arrotondata all'intero
    return round(performance)

# --- Tie-breaking Functions ---
def compute_buchholz(player_id, torneo):
    """Calcola il punteggio Buchholz Totale per un giocatore (somma punti avversari)."""
    buchholz_score = 0.0
    player = get_player_by_id(torneo, player_id)
    if not player: return 0.0
    # Assicura che il dizionario dei giocatori sia aggiornato
    players_dict = torneo.get('players_dict', {p['id']: p for p in torneo.get('players', [])})
    # Usa lo storico risultati per trovare gli avversari reali
    opponent_ids_encountered = set() # Per evitare di contare due volte in caso di errori nello storico
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        # Ignora BYE e avversari non validi
        if opponent_id and opponent_id != "BYE_PLAYER_ID" and opponent_id not in opponent_ids_encountered:
            opponent = players_dict.get(opponent_id)
            if opponent:
                # Assicura che i punti siano float
                opponent_points = 0.0
                try:
                    # Indentazione corretta
                    opponent_points = float(opponent.get("points", 0.0))
                except (ValueError, TypeError):
                    # Indentazione corretta
                    print(f"Warning: Punti non validi ({opponent.get('points')}) per avversario {opponent_id} nel calcolo Buchholz di {player_id}.")
                buchholz_score += opponent_points
                opponent_ids_encountered.add(opponent_id)
            else:
                # Indentazione corretta
                # Questo warning è importante
                print(f"Warning: Avversario {opponent_id} (dallo storico di {player_id}) non trovato nel dizionario giocatori per calcolo Buchholz.")
    # Formatta il risultato Buchholz come gli altri punteggi
    return float(format_points(buchholz_score)) # Ritorna float ma formattato

def compute_buchholz_cut1(player_id, torneo):
    """Calcola il punteggio Buchholz Cut 1 (esclude il punteggio più basso)."""
    opponent_scores = []
    player = get_player_by_id(torneo, player_id)
    if not player: return 0.0
    players_dict = torneo.get('players_dict', {p['id']: p for p in torneo.get('players', [])})
    opponent_ids_encountered = set() # Evita doppio conteggio se storico errato

    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        if opponent_id and opponent_id != "BYE_PLAYER_ID" and opponent_id not in opponent_ids_encountered:
            opponent = players_dict.get(opponent_id)
            if opponent:
                try:
                    opponent_scores.append(float(opponent.get("points", 0.0)))
                except (ValueError, TypeError):
                    # Indentazione corretta
                    print(f"Warning: Punti non validi ({opponent.get('points')}) per avversario {opponent_id} in BuchholzCut1 di {player_id}.")
                opponent_ids_encountered.add(opponent_id)
            # else: Warning già dato da compute_buchholz se chiamato prima

    if not opponent_scores:
        return 0.0

    # Calcola Buchholz totale e sottrai il minimo
    total_score = sum(opponent_scores)
    min_score = min(opponent_scores) if opponent_scores else 0.0
    buchholz_cut1_score = total_score - min_score

    # Formatta come gli altri punti
    return float(format_points(buchholz_cut1_score))

def compute_aro(player_id, torneo):
    """Calcola l'Average Rating of Opponents (ARO) basato sull'Elo iniziale."""
    opponent_elos = []
    player = get_player_by_id(torneo, player_id)
    if not player: return None # Non possiamo calcolare ARO
    players_dict = torneo.get('players_dict', {p['id']: p for p in torneo.get('players', [])})
    opponent_ids_encountered = set()

    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        if opponent_id and opponent_id != "BYE_PLAYER_ID" and opponent_id not in opponent_ids_encountered:
            # Indentazione corretta
            opponent = players_dict.get(opponent_id)
            if opponent and 'initial_elo' in opponent:
                try:
                    # Indentazione corretta
                    opponent_elos.append(float(opponent['initial_elo']))
                except (ValueError, TypeError):
                    # Indentazione corretta
                    print(f"Warning: Elo iniziale non valido ({opponent['initial_elo']}) per avversario {opponent_id} in ARO di {player_id}.")
                opponent_ids_encountered.add(opponent_id)
            # else: Giocatore non trovato o senza Elo iniziale, non includere in ARO

    if not opponent_elos:
        return None # Nessun avversario valido trovato

    # Calcola la media e arrotonda all'intero
    aro = sum(opponent_elos) / len(opponent_elos)
    return round(aro)

# --- Pairing Logic ---

# Nuove funzioni helper per le regole colore FIDE
def get_color_preference_score(player):
    """Calcola la differenza B/N per la preferenza colore (FIDE C.04.3.a)."""
    return player.get("white_games", 0) - player.get("black_games", 0)

def check_absolute_color_constraints(player, color_to_assign):
    """Verifica se assegnare 'color_to_assign' a 'player' viola FIDE C.04.2.c/d."""
    if color_to_assign == 'white':
        # Controlla max differenza B/N (C.04.2.d)
        if (player.get("white_games", 0) + 1) - player.get("black_games", 0) > MAX_COLOR_DIFFERENCE:
            return False # Violerebbe la differenza massima
        # Controlla max consecutivi (C.04.2.c)
        if player.get("consecutive_white", 0) >= MAX_CONSECUTIVE_SAME_COLOR:
            return False # Violerebbe i consecutivi massimi
    elif color_to_assign == 'black':
        # Controlla max differenza B/N (C.04.2.d)
        if player.get("white_games", 0) - (player.get("black_games", 0) + 1) < -MAX_COLOR_DIFFERENCE:
            return False # Violerebbe la differenza massima
        # Controlla max consecutivi (C.04.2.c)
        if player.get("consecutive_black", 0) >= MAX_CONSECUTIVE_SAME_COLOR:
            return False # Violerebbe i consecutivi massimi
    return True # Nessuna violazione assoluta

def determine_color_assignment(player1, player2):
    """Determina l'assegnazione colori seguendo FIDE C.04.3 e verifica C.04.2.
       Restituisce:
       ('W', white_id, black_id) se assegnazione valida trovata.
       ('Error', reason) se impossibile assegnare colori senza violare regole.
    """
    p1_id = player1['id']
    p2_id = player2['id']
    d1 = get_color_preference_score(player1)
    d2 = get_color_preference_score(player2)
    last1 = player1.get("last_color", None)
    last2 = player2.get("last_color", None)
    p1_elo = player1.get('initial_elo', 0)
    p2_elo = player2.get('initial_elo', 0)
    # Priorità 1: Differenza B/N (C.04.3.a)
    # Chi ha la differenza minore ha più bisogno del bianco (o meno bisogno del nero)
    if d1 < d2: # P1 ha preferenza per il Bianco
        if check_absolute_color_constraints(player1, 'white') and check_absolute_color_constraints(player2, 'black'):
            return ('W', p1_id, p2_id)
        elif check_absolute_color_constraints(player1, 'black') and check_absolute_color_constraints(player2, 'white'):
            # Indentazione corretta
            print(f"Info Colore: {p1_id} aveva preferenza Bianco (d={d1}<{d2}), ma assegnato Nero per vincoli.")
            return ('W', p2_id, p1_id)
        else:
            return ('Error', f"Vincoli colore assoluti impediscono {p1_id}(d={d1}) vs {p2_id}(d={d2})")
    elif d2 < d1: # P2 ha preferenza per il Bianco
        if check_absolute_color_constraints(player2, 'white') and check_absolute_color_constraints(player1, 'black'):
            return ('W', p2_id, p1_id)
        elif check_absolute_color_constraints(player2, 'black') and check_absolute_color_constraints(player1, 'white'):
            # Indentazione corretta
            print(f"Info Colore: {p2_id} aveva preferenza Bianco (d={d2}<{d1}), ma assegnato Nero per vincoli.")
            return ('W', p1_id, p2_id)
        else:
            return ('Error', f"Vincoli colore assoluti impediscono {p1_id}(d={d1}) vs {p2_id}(d={d2})")
    else: # d1 == d2, si passa alla Priorità 2: Alternanza (C.04.3.b)
        p1_prefers_white_alt = (last1 == 'black')
        p2_prefers_white_alt = (last2 == 'black')
        if p1_prefers_white_alt and not p2_prefers_white_alt: # P1 ha giocato nero, P2 no -> P1 preferenza Bianco
            if check_absolute_color_constraints(player1, 'white') and check_absolute_color_constraints(player2, 'black'):
                return ('W', p1_id, p2_id)
            elif check_absolute_color_constraints(player1, 'black') and check_absolute_color_constraints(player2, 'white'):
                # Indentazione corretta
                print(f"Info Colore: {p1_id} aveva preferenza Bianco (alt), ma assegnato Nero per vincoli.")
                return ('W', p2_id, p1_id)
            else:
                # Indentazione corretta
                return ('Error', f"Vincoli colore assoluti impediscono {p1_id}(last={last1}) vs {p2_id}(last={last2})")
        elif p2_prefers_white_alt and not p1_prefers_white_alt: # P2 ha giocato nero, P1 no -> P2 preferenza Bianco
            if check_absolute_color_constraints(player2, 'white') and check_absolute_color_constraints(player1, 'black'):
                return ('W', p2_id, p1_id)
            elif check_absolute_color_constraints(player2, 'black') and check_absolute_color_constraints(player1, 'white'):
                # Indentazione corretta
                print(f"Info Colore: {p2_id} aveva preferenza Bianco (alt), ma assegnato Nero per vincoli.")
                return ('W', p1_id, p2_id)
            else:
                # Indentazione corretta
                return ('Error', f"Vincoli colore assoluti impediscono {p1_id}(last={last1}) vs {p2_id}(last={last2})")
        else: # Entrambi hanno giocato nero, o entrambi bianco/null -> Priorità 3: Rank/Rating (C.04.3.c)
            # Qui usiamo Elo come proxy per Rank. Il giocatore con Elo più alto ottiene la preferenza.
            higher_elo_player = player1 if p1_elo >= p2_elo else player2 # >= per dare priorità a P1 in caso di parità Elo
            lower_elo_player = player2 if p1_elo >= p2_elo else player1
            if check_absolute_color_constraints(higher_elo_player, 'white') and check_absolute_color_constraints(lower_elo_player, 'black'):
                # Indentazione corretta
                return ('W', higher_elo_player['id'], lower_elo_player['id'])
            elif check_absolute_color_constraints(higher_elo_player, 'black') and check_absolute_color_constraints(lower_elo_player, 'white'):
                # Indentazione corretta
                # Assegnazione inversa possibile
                print(f"Info Colore: {higher_elo_player['id']} (Elo alto) preferenza non assegnabile, colore invertito.")
                return ('W', lower_elo_player['id'], higher_elo_player['id'])
            else:
                # Indentazione corretta
                # Se nemmeno l'inversione è possibile, siamo bloccati
                return ('Error', f"Vincoli colore assoluti impediscono {p1_id}(Elo={p1_elo}) vs {p2_id}(Elo={p2_elo}) anche con rating")
def select_downfloater(group_to_select_from, torneo):
    """
    Seleziona il giocatore che diventerà downfloater da un gruppo dispari.
    Criterio FIDE (più aderente):
    1. Priorità a NON far scendere chi ha già avuto il BYE in questo torneo.
    2. Priorità a NON far scendere chi è già sceso (downfloat_count > 0).
    3. Tra quelli con pari priorità (es. tutti senza bye e mai scesi),
       scegli quello con RANKING più basso (Elo più basso nel nostro caso)
       per farlo scendere.
    Restituisce il giocatore selezionato o None se il gruppo è vuoto.
    IMPORTANTE: Questa funzione SELEZIONA soltanto. L'incremento del
                downfloat_count avviene nella funzione chiamante (pair_score_group).
    """
    if not group_to_select_from:
        return None
    # Il gruppo arriva già ordinato per Elo DESC (dal più alto al più basso)
    # Noi vogliamo selezionare partendo dal fondo (Elo più basso)
    potential_floaters = list(group_to_select_from) # Lavora su copia
    # Ordina i candidati secondo i criteri FIDE per la *selezione* del downfloater
    # Chiave di sort: (ha_ricevuto_bye_TORNEO, downfloat_count, -initial_elo -> che diventa +initial_elo per sort ASC)
    # Si ordina in modo che chi DEVE scendere (bye=False, float=0, elo basso) venga prima
    def floater_priority_key(player):
        p_data = torneo['players_dict'].get(player['id']) # Recupera dati completi aggiornati
        if not p_data: return (True, 999, 0) # Errore, mettilo in fondo

        # Verifica se ha ricevuto il bye IN QUESTO TORNEO
        # La chiave 'received_bye' viene aggiornata direttamente nel player_dict
        has_received_bye_in_tournament = p_data.get('received_bye', False)
        downfloat_count = p_data.get('downfloat_count', 0)
        elo = p_data.get('initial_elo', 0)
        # Priorità per SCENDERE:
        # 1. Non ha avuto bye? (False viene prima di True)
        # 2. Non ha mai floattato? (0 viene prima di 1, 2...)
        # 3. Ha Elo basso? (Elo basso viene prima con sort ASC)
        return (has_received_bye_in_tournament, downfloat_count, elo)
    potential_floaters.sort(key=floater_priority_key) # Ordina per priorità a scendere
    if not potential_floaters: # Controllo sicurezza
         return None

    # Il giocatore da far scendere è il PRIMO in questa lista ordinata
    downfloater = potential_floaters[0]
    return downfloater

# --- Funzione per il tentativo di accoppiamento standard (Fold/Slide) ---
# Assicurati che determine_color_assignment e le altre funzioni helper siano definite prima

# --- Funzione per il tentativo di accoppiamento standard (Fold/Slide) ---
# Assicurati che determine_color_assignment e le altre funzioni helper siano definite prima

def attempt_fold_pairing(top_half, bottom_half, torneo, round_number):
    """
    [CON DEBUG] Tenta l'accoppiamento standard Top-vs-Bottom (Fold/Slide).
    Include logica per alternare i colori al primo turno.
    Restituisce: (lista_partite_riuscite, lista_spaiati_top, lista_spaiati_bottom)
    """
    print(f"\n[DEBUG PAIRING] === Inizio attempt_fold_pairing (Turno {round_number}) ===") # Header debug
    print(f"[DEBUG PAIRING] Giocatori Top Half (input): {[p['id'] for p in top_half]}")
    print(f"[DEBUG PAIRING] Giocatori Bottom Half (input): {[p['id'] for p in bottom_half]}")

    matches = []
    used_player_ids = set()

    # Ordina le metà (anche se già ordinate da pair_score_group, una sicurezza)
    # NOTA: Se pair_score_group ordina già correttamente, queste sort non dovrebbero cambiare l'ordine.
    top_half.sort(key=lambda x: -x.get("initial_elo", 0))
    bottom_half.sort(key=lambda x: -x.get("initial_elo", 0))
    print(f"[DEBUG PAIRING] Top Half IDs (dopo sort interna per Elo): {[p['id'] for p in top_half]}")
    print(f"[DEBUG PAIRING] Bottom Half IDs (dopo sort interna per Elo): {[p['id'] for p in bottom_half]}")

    # --- Esegui il matching greedy ---
    print("\n[DEBUG PAIRING] --- Inizio Ciclo Pairing Greedy ---")
    for i in range(len(top_half)):
        p1 = top_half[i]
        print(f"\n[DEBUG PAIRING] Processo p1 (Top index {i}): {p1['id']} [Elo:{p1.get('initial_elo')}]")

        if p1['id'] in used_player_ids:
            print(f"[DEBUG PAIRING] --> p1 {p1['id']} già accoppiato in questo step. Salto.")
            continue

        partner_found_for_p1 = False # Flag per vedere se troviamo partner in questo ciclo 'i'

        # Cerca un avversario valido nella bottom half
        for k in range(len(bottom_half)):
            p2 = bottom_half[k]
            print(f"[DEBUG PAIRING]   Valuto p2 (Bottom index {k}): {p2['id']} [Elo:{p2.get('initial_elo')}]")

            if p2['id'] in used_player_ids:
                print(f"[DEBUG PAIRING]   --> p2 {p2['id']} già accoppiato. Salto p2.")
                continue

            # Verifica se possono giocare (Turno 1: played_before sarà sempre False)
            played_before = p2['id'] in p1.get('opponents', set())
            print(f"[DEBUG PAIRING]   --> Giocato prima ({p1['id']} vs {p2['id']})? {played_before}")
            if not played_before:
                # Controlla assegnazione colori
                color_result = determine_color_assignment(p1, p2)
                print(f"[DEBUG PAIRING]   --> Esito check colori ({p1['id']} vs {p2['id']}): {color_result}")

                if color_result[0] == 'W':
                    # Accoppiamento Trovato!
                    white_id, black_id = color_result[1], color_result[2]
                    print(f"[DEBUG PAIRING]   +++ ACCOPPIAMENTO VALIDO TROVATO! Match ID: {torneo['next_match_id']}, W:{white_id}, B:{black_id} (Orig: Top={p1['id']}, Bottom={p2['id']}) +++")
                    match = {
                        "id": torneo["next_match_id"], "round": round_number,
                        "white_player_id": white_id, "black_player_id": black_id,
                        "result": None,
                        # Memorizza chi era Top/Bottom originale per l'alternanza (necessario)
                        "original_p1_id": p1['id'],
                        "original_p2_id": p2['id']
                    }
                    matches.append(match)
                    torneo["next_match_id"] += 1
                    used_player_ids.add(p1['id'])
                    used_player_ids.add(p2['id'])
                    print(f"[DEBUG PAIRING]   --> Aggiunti a used_player_ids: {p1['id']}, {p2['id']}")
                    print(f"[DEBUG PAIRING]   --> Interrompo ricerca partner per p1 {p1['id']} (trovato p2 {p2['id']}).")
                    partner_found_for_p1 = True # Segnala che abbiamo trovato partner
                    break # Trovato partner per p1, passa al prossimo p1 (ciclo 'i')
                else:
                     # Colori non validi o errore, continua a cercare p2
                     print(f"[DEBUG PAIRING]   --> Colori non assegnabili o errore: {color_result[1]}. Continuo ricerca p2.")
            # else: # Blocco non raggiungibile in T1
            #    print(f"[DEBUG PAIRING]   --> Già giocato. Continuo ricerca p2.")

        # Stampa se p1 è rimasto senza partner dopo aver ciclato su tutta bottom_half
        if not partner_found_for_p1 and p1['id'] not in used_player_ids:
             print(f"[DEBUG PAIRING] !!! NESSUN partner valido trovato per p1 {p1['id']} in bottom_half dopo ciclo 'k'. !!!")


    print("\n[DEBUG PAIRING] --- Fine Ciclo Pairing Greedy ---")
    print(f"[DEBUG PAIRING] Partite grezze create prima dell'alternanza: {len(matches)}")
    # Stampa le coppie grezze e i colori PRIMA dell'alternanza T1
    for m_debug in matches:
        print(f"[DEBUG PAIRING]   - Match ID {m_debug['id']}: W={m_debug['white_player_id']} vs B={m_debug['black_player_id']} (P1(Top): {m_debug['original_p1_id']}, P2(Bottom): {m_debug['original_p2_id']})")


    # --- Logica Alternanza Colori per Turno 1 ---
    if round_number == 1 and matches:
        print("\n[DEBUG PAIRING] --- Applico alternanza colori per Turno 1 ---")
        print("[DEBUG PAIRING] Ordino le partite per Elo del giocatore Top Half originale (decrescente)...")
        try:
             # Aggiungi gestione errori nel caso get() fallisca o elo non sia valido
             # Usiamo una funzione interna per chiarezza nel debug dell'ordinamento
             def get_sort_key_for_alternation(match_item):
                 p1_id_sort = match_item.get('original_p1_id')
                 player_data_sort = torneo['players_dict'].get(p1_id_sort, {})
                 elo_sort = player_data_sort.get('initial_elo', 0)
                 #print(f"DEBUG sort key for Match {match_item.get('id')}: P1={p1_id_sort}, Elo={elo_sort}") # Debug più fine se serve
                 # Assicura che ritorni un numero per l'ordinamento
                 try:
                     return float(elo_sort)
                 except (ValueError, TypeError):
                     return 0.0 # Metti in fondo se Elo non valido

             matches.sort(key=get_sort_key_for_alternation, reverse=True)
             print("[DEBUG PAIRING] Partite ordinate per alternanza:")
             for idx_sort, m_sort in enumerate(matches):
                  p1_elo_sort = torneo['players_dict'].get(m_sort['original_p1_id'], {}).get('initial_elo', 'N/A')
                  print(f"[DEBUG PAIRING]   {idx_sort}: Match ID {m_sort['id']} (P1(Top): {m_sort['original_p1_id']} [Elo:{p1_elo_sort}])")

        except Exception as e_sort:
             print(f"[DEBUG PAIRING] ERRORE durante l'ordinamento per alternanza colori: {e_sort}")
             # Procediamo comunque con l'ordine attuale, ma l'alternanza potrebbe essere errata

        print("[DEBUG PAIRING] Applico inversione colori su indici dispari (0-based)...")
        for idx, match in enumerate(matches):
            # Inverti i colori per le partite con indice dispari (scacchiera 2, 4, 6...)
            board_number_display = idx + 1 # Scacchiera (1-based)
            if idx % 2 != 0:
                w_id_orig = match['white_player_id']
                b_id_orig = match['black_player_id']
                match['white_player_id'] = b_id_orig
                match['black_player_id'] = w_id_orig
                print(f"[DEBUG PAIRING] --> Scacchiera {board_number_display} (Indice {idx}): Colori INVERTITI. Ora W:{b_id_orig}, B:{w_id_orig}")
            else:
                print(f"[DEBUG PAIRING] --> Scacchiera {board_number_display} (Indice {idx}): Colori NON invertiti. Rimane W:{match['white_player_id']}, B:{match['black_player_id']}")


    # Non rimuovere 'original_p1_id', 'original_p2_id' - potrebbero servire a chi chiama la funzione
    # per capire la logica o per debug futuro.

    # Identifica chi è rimasto spaiato
    unpaired_top = [p for p in top_half if p['id'] not in used_player_ids]
    unpaired_bottom = [p for p in bottom_half if p['id'] not in used_player_ids]
    print(f"\n[DEBUG PAIRING] === Fine attempt_fold_pairing ===")
    print(f"[DEBUG PAIRING] Partite finali generate in questo step: {len(matches)}")
    print(f"[DEBUG PAIRING] Spaiati Top: {[p['id'] for p in unpaired_top]}")
    print(f"[DEBUG PAIRING] Spaiati Bottom: {[p['id'] for p in unpaired_bottom]}")
    # print(f"[DEBUG PAIRING] IDs usati totali: {used_player_ids}") # Meno utile alla fine

    return matches, unpaired_top, unpaired_bottom
def check_pairing_validity(p1, p2, torneo_players_dict):
    """
    Verifica se p1 può essere accoppiato con p2.
    Controlla se hanno già giocato e se l'assegnazione colori è valida.
    Recupera i dati più aggiornati dei giocatori dal dizionario principale.
    Restituisce: (True/False, color_result)
    """
    # Recupera dati aggiornati (importante se stati modificati da altre operazioni)
    player1 = torneo_players_dict.get(p1.get('id'))
    player2 = torneo_players_dict.get(p2.get('id'))

    if not player1 or not player2:
        return False, None

    played_before = player2.get('id') in player1.get('opponents', set())
    if played_before:
        return False, None

    color_result = determine_color_assignment(player1, player2)
    if color_result[0] == 'W':
        return True, color_result
    else:
        # Stampa il motivo del fallimento colori solo se fallisce
        return False, None

def create_match_from_color_result(color_result, torneo, round_number):
    """Crea un dizionario partita da un risultato valido ('W', W_ID, B_ID)."""
    if not color_result or color_result[0] != 'W':
        print(f"ERRORE create_match: Ricevuto risultato colore non valido: {color_result}")
        return None # Dovrebbe ricevere solo risultati validi
    white_id, black_id = color_result[1], color_result[2]
    match = {
        "id": torneo["next_match_id"],
        "round": round_number,
        "white_player_id": white_id,
        "black_player_id": black_id,
        "result": None
    }
    torneo["next_match_id"] += 1
    return match

# ===============================================================================
# --- Fase 4: Funzione per Trasposizioni/Accoppiamenti Alternativi Avanzati ---
# ===============================================================================

def attempt_transpositions(unpaired_top, unpaired_bottom, matches_made_in_group, torneo, round_number):
    """
    Tenta di accoppiare i giocatori spaiati usando logiche di recupero FIDE-like avanzate.
    Ordine tentativi per la coppia spaiata (h0, l0):
    1. Diretto h0 vs l0
    2. Alternativo h0 vs l1 (se esiste l1)
    3. Alternativo h1 vs l0 (se esiste h1)
    4. Trasposizione Iterativa: Scambia partner tra (h0, l0) e CIASCUNA coppia (hp, lp)
       già formata nel fold pairing, finché non ne trova una valida.
    Se un tentativo riesce, si accoppia e si riavvia il ciclo while con i rimanenti.
    Se tutti falliscono per (h0, l0), il recupero per questo gruppo si interrompe.

    Restituisce: (lista_nuove_partite, lista_top_rimasti, lista_bottom_rimasti, id_partita_originale_da_rimuovere | None)
    """
    newly_made_matches = []
    current_unpaired_top = list(unpaired_top)
    current_unpaired_bottom = list(unpaired_bottom)
    current_unpaired_top.sort(key=lambda x: -x.get("initial_elo", 0))
    current_unpaired_bottom.sort(key=lambda x: -x.get("initial_elo", 0))

    players_dict = torneo['players_dict']
    match_id_to_remove = None # Diventa non-None solo se avviene una trasposizione T4

    # Loop finché ci sono giocatori spaiati in entrambe le metà
    while current_unpaired_top and current_unpaired_bottom:
        paired_this_cycle = False # Flag per vedere se abbiamo accoppiato h0 in questa iterazione

        h0 = current_unpaired_top[0]
        l0 = current_unpaired_bottom[0]
        # --- Tentativo 1: Accoppiamento Diretto (H0 vs L0) ---
        can_pair_1, color_res_1 = check_pairing_validity(h0, l0, players_dict)
        if can_pair_1:
            match = create_match_from_color_result(color_res_1, torneo, round_number)
            if match:
                newly_made_matches.append(match)
                current_unpaired_top.pop(0)
                current_unpaired_bottom.pop(0)
                paired_this_cycle = True
            # else: ERRORE gestito da create_match

        # --- Tentativo 2: Alternativo H0 vs L1 (se T1 fallito e L1 esiste) ---
        if not paired_this_cycle and len(current_unpaired_bottom) > 1:
            l1 = current_unpaired_bottom[1]
            can_pair_2, color_res_2 = check_pairing_validity(h0, l1, players_dict)
            if can_pair_2:
                match = create_match_from_color_result(color_res_2, torneo, round_number)
                if match:
                    newly_made_matches.append(match)
                    current_unpaired_top.pop(0)
                    current_unpaired_bottom.pop(1) # Rimuovi l1 (indice 1)
                    paired_this_cycle = True
                # else: ERRORE gestito da create_match

        # --- Tentativo 3: Alternativo H1 vs L0 (se T1,T2 falliti e H1 esiste) ---
        if not paired_this_cycle and len(current_unpaired_top) > 1:
            h1 = current_unpaired_top[1]
            can_pair_3, color_res_3 = check_pairing_validity(h1, l0, players_dict)
            if can_pair_3:
                match = create_match_from_color_result(color_res_3, torneo, round_number)
                if match:
                    newly_made_matches.append(match)
                    current_unpaired_top.pop(1) # Rimuovi h1 (indice 1)
                    current_unpaired_bottom.pop(0)
                    paired_this_cycle = True
                # else: ERRORE gestito da create_match

        # --- Tentativo 4: Trasposizione Iterativa (se T1,T2,T3 falliti e ci sono coppie con cui scambiare) ---
        if not paired_this_cycle and matches_made_in_group:
            # Itera sulle partite create nel fold pairing originale per trovare uno scambio valido
            for original_match_data in matches_made_in_group:
                hp_id = original_match_data.get('white_player_id') # ID Giocatore 1 della coppia esistente
                lp_id = original_match_data.get('black_player_id') # ID Giocatore 2 della coppia esistente
                hp = players_dict.get(hp_id)
                lp = players_dict.get(lp_id)

                if not hp or not lp:
                     print(f"WARN attempt_transpositions: Saltato controllo swap con match {original_match_data.get('id')} - dati giocatore mancanti ({hp_id}, {lp_id})") #DEBUG
                     continue # Salta questa coppia se i dati non sono recuperabili

                # Verifica se lo scambio è valido
                # Coppia Swap 1: h0 vs lp
                can_swap_1, color_res_swap_1 = check_pairing_validity(h0, lp, players_dict)
                # Coppia Swap 2: hp vs l0
                can_swap_2, color_res_swap_2 = check_pairing_validity(hp, l0, players_dict)

                # print(f"DEBUG attempt_transpositions T4 Swap Check with ({hp['id']} vs {lp['id']}): ({h0['id']} vs {lp['id']}) -> {can_swap_1}, ({hp['id']} vs {l0['id']}) -> {can_swap_2}") # DEBUG (Troppo verboso forse)
                if can_swap_1 and can_swap_2:
                    # TRASPOSIZIONE VALIDA TROVATA!
                    match_swap_1 = create_match_from_color_result(color_res_swap_1, torneo, round_number)
                    match_swap_2 = create_match_from_color_result(color_res_swap_2, torneo, round_number)

                    if match_swap_1 and match_swap_2:
                        newly_made_matches.extend([match_swap_1, match_swap_2])
                        current_unpaired_top.pop(0)
                        current_unpaired_bottom.pop(0)
                        match_id_to_remove = original_match_data['id'] # Segnala ID originale da rimuovere
                        paired_this_cycle = True # Abbiamo fatto progressi
                        # Ritorna subito dopo la prima trasposizione valida trovata
                        return newly_made_matches, current_unpaired_top, current_unpaired_bottom, match_id_to_remove
                    else:
                        print(f"ERRORE attempt_transpositions: T4 - Creazione match swap fallita?") #DEBUG
                        # Se la creazione fallisce qui, è un problema grave, ma continuiamo a cercare altre trasposizioni valide
                        # (anche se non dovrebbe accadere se check_pairing_validity è corretto)
                        paired_this_cycle = False # Non considerarlo un successo se il match non viene creato
                        break # Esci dal loop for delle trasposizioni per sicurezza? O continua? Continuiamo a cercare.

            # Se il loop 'for' finisce senza aver trovato (e ritornato) una trasposizione valida
            if not paired_this_cycle:
                 print(f"DEBUG attempt_transpositions: T4 - Nessuna trasposizione valida trovata iterando.") #DEBUG

        # --- Se nessun tentativo ha funzionato per h0 in questo ciclo ---
        if not paired_this_cycle:
            # Nessuna delle opzioni ha funzionato per H0 con L0 o L1, né H1 con L0, né trasposizioni.
            # Interrompiamo il recupero per questo gruppo; h0 e altri rimarranno spaiati.
            print(f"DEBUG attempt_transpositions: Nessuna soluzione trovata per H0={h0['id']} questo ciclo. Interrompo recupero.") # DEBUG
            break # Esce dal ciclo while principale di attempt_transpositions

        # Se paired_this_cycle è True (abbiamo accoppiato tramite T1, T2 o T3),
        # il ciclo while continua con le liste ridotte di giocatori spaiati.

    # Fine del ciclo while di recupero
    print(f"DEBUG attempt_transpositions: Fine recupero. Nuove partite: {len(newly_made_matches)}. Spaiati T: {len(current_unpaired_top)}, B: {len(current_unpaired_bottom)}") # DEBUG
    # Ritorna le partite create in questo tentativo e i giocatori rimasti spaiati
    # match_id_to_remove sarà None se non è avvenuta una trasposizione T4 che ha richiesto un ritorno immediato.
    return newly_made_matches, current_unpaired_top, current_unpaired_bottom, match_id_to_remove

# --- Fase 4: Funzione Pairing Within Halves (Logica Interna Raffinata) ---
def attempt_pair_within_halves(remaining_top, remaining_bottom, torneo, round_number):
    """
    Tenta di accoppiare i giocatori rimasti all'interno delle loro metà originali.
    Logica interna migliorata per cercare di minimizzare le differenze Elo tra gli
    accoppiamenti validi formati all'interno di ciascuna metà (cfr. FIDE C.04.5.b).
    Restituisce: (lista_partite_create_within_halves, lista_giocatori_ancora_spaiati)
    """
    print(f"DEBUG attempt_pair_within_halves: Inizio recupero finale (logica raffinata). Rimasti T:{len(remaining_top)}, B:{len(remaining_bottom)}") # DEBUG

    within_halves_matches = []
    final_unpaired_players = [] # Giocatori che non si riesce ad accoppiare nemmeno qui
    players_dict = torneo['players_dict']

    # --- Processa remaining_top ---
    current_unpaired_in_top = list(remaining_top)
    current_unpaired_in_top.sort(key=lambda x: -x.get("initial_elo", 0)) # Ordina Elo DESC

    processed_ids_top = set() # Tieni traccia di chi è stato processato (accoppiato o impossibile)

    print(f"DEBUG attempt_pair_within_halves: Processo Top Half ({len(current_unpaired_in_top)} giocatori)") #DEBUG
    # Usa un indice i per scorrere la lista mentre la modifichiamo (o meglio, usiamo un set di IDs)
    # Prendiamo il primo non ancora processato
    idx_p1 = 0
    while idx_p1 < len(current_unpaired_in_top):
        p1 = current_unpaired_in_top[idx_p1]
        if p1['id'] in processed_ids_top:
            idx_p1 += 1
            continue # Già processato (come parte di una coppia precedente)

        print(f"DEBUG attempt_pair_within_halves: Cerco partner Top per {p1['id']} ({p1.get('initial_elo',0)} Elo)") #DEBUG
        best_partner_p2 = None
        min_elo_diff = float('inf')
        best_partner_idx = -1
        best_color_res = None

        # Cerca il miglior partner VALIDO tra i rimanenti in Top
        for idx_p2 in range(idx_p1 + 1, len(current_unpaired_in_top)):
            p2 = current_unpaired_in_top[idx_p2]
            if p2['id'] in processed_ids_top:
                 continue # Già processato

            can_pair, color_res = check_pairing_validity(p1, p2, players_dict)
            if can_pair:
                # Calcola differenza Elo
                try:
                    elo_diff = abs(float(p1.get('initial_elo', 0)) - float(p2.get('initial_elo', 0)))
                    # Se è il primo valido o migliore del precedente, salvalo
                    if elo_diff < min_elo_diff:
                        min_elo_diff = elo_diff
                        best_partner_p2 = p2
                        best_partner_idx = idx_p2 # Salviamo indice per futura rimozione (sebbene useremo ID)
                        best_color_res = color_res
                except ValueError:
                    # Ignora questa coppia se Elo non è valido per il calcolo diff
                     print(f"WARN attempt_pair_within_halves: Elo non valido per calcolo diff tra {p1['id']} e {p2['id']}") #DEBUG
                     pass

        # Se abbiamo trovato un partner valido per p1
        if best_partner_p2:
            print(f"DEBUG attempt_pair_within_halves: Miglior partner Top trovato per {p1['id']} è {best_partner_p2['id']} (Diff Elo: {min_elo_diff})") #DEBUG
            match = create_match_from_color_result(best_color_res, torneo, round_number)
            if match:
                within_halves_matches.append(match)
                processed_ids_top.add(p1['id'])
                processed_ids_top.add(best_partner_p2['id'])
                print(f"DEBUG attempt_pair_within_halves: OK Top vs Top - Match ID {match['id']}") #DEBUG
            else:
                 print(f"ERRORE attempt_pair_within_halves: Fallita creazione match Top-Top valido?") #DEBUG
                 processed_ids_top.add(p1['id']) # Segna p1 come processato anche se fallisce la creazione match
        else:
            # Nessun partner valido trovato per p1 tra i rimanenti in Top
            print(f"DEBUG attempt_pair_within_halves: Nessun partner Top valido trovato per {p1['id']}. Diventa spaiato finale.") #DEBUG
            final_unpaired_players.append(p1)
            processed_ids_top.add(p1['id']) # Segna come processato

        idx_p1 += 1 # Passa al prossimo giocatore non ancora processato


    # --- Processa remaining_bottom (logica identica a Top) ---
    current_unpaired_in_bottom = list(remaining_bottom)
    current_unpaired_in_bottom.sort(key=lambda x: -x.get("initial_elo", 0))
    processed_ids_bottom = set()

    print(f"DEBUG attempt_pair_within_halves: Processo Bottom Half ({len(current_unpaired_in_bottom)} giocatori)") #DEBUG
    idx_p1 = 0
    while idx_p1 < len(current_unpaired_in_bottom):
        p1 = current_unpaired_in_bottom[idx_p1]
        if p1['id'] in processed_ids_bottom:
            idx_p1 += 1
            continue

        print(f"DEBUG attempt_pair_within_halves: Cerco partner Bottom per {p1['id']} ({p1.get('initial_elo',0)} Elo)") #DEBUG
        best_partner_p2 = None
        min_elo_diff = float('inf')
        best_partner_idx = -1
        best_color_res = None

        for idx_p2 in range(idx_p1 + 1, len(current_unpaired_in_bottom)):
            p2 = current_unpaired_in_bottom[idx_p2]
            if p2['id'] in processed_ids_bottom:
                 continue

            can_pair, color_res = check_pairing_validity(p1, p2, players_dict)
            if can_pair:
                try:
                    elo_diff = abs(float(p1.get('initial_elo', 0)) - float(p2.get('initial_elo', 0)))
                    if elo_diff < min_elo_diff:
                        min_elo_diff = elo_diff
                        best_partner_p2 = p2
                        best_partner_idx = idx_p2
                        best_color_res = color_res
                except ValueError:
                     pass

        if best_partner_p2:
            print(f"DEBUG attempt_pair_within_halves: Miglior partner Bottom trovato per {p1['id']} è {best_partner_p2['id']} (Diff Elo: {min_elo_diff})") #DEBUG
            match = create_match_from_color_result(best_color_res, torneo, round_number)
            if match:
                within_halves_matches.append(match)
                processed_ids_bottom.add(p1['id'])
                processed_ids_bottom.add(best_partner_p2['id'])
                print(f"DEBUG attempt_pair_within_halves: OK Bottom vs Bottom - Match ID {match['id']}") #DEBUG
            else:
                 print(f"ERRORE attempt_pair_within_halves: Fallita creazione match Bottom-Bottom valido?") #DEBUG
                 processed_ids_bottom.add(p1['id'])
        else:
            print(f"DEBUG attempt_pair_within_halves: Nessun partner Bottom valido trovato per {p1['id']}. Diventa spaiato finale.") #DEBUG
            final_unpaired_players.append(p1)
            processed_ids_bottom.add(p1['id'])

        idx_p1 += 1

    # Stampa finale e ritorno
    print(f"DEBUG attempt_pair_within_halves: Fine recupero finale. Partite create: {len(within_halves_matches)}. Spaiati finali: {len(final_unpaired_players)}") # DEBUG
    if final_unpaired_players:
         # Questo non dovrebbe accadere in un torneo normale se i vincoli non sono impossibili
         print(f"DEBUG attempt_pair_within_halves: ATTENZIONE CRITICA! Giocatori ancora spaiati dopo within-halves: {[p['id'] for p in final_unpaired_players]}") # DEBUG
    return within_halves_matches, final_unpaired_players

def pair_score_group(group_players, downfloaters_in, torneo, round_number):
    """
    Gestisce l'accoppiamento per un singolo gruppo di punteggio, inclusi i downfloaters.
    Chiama i vari tentativi di pairing (fold, trasposizioni semplici, within-halves).
    Incrementa downfloat_count per il giocatore selezionato.
    Restituisce: (lista_partite_generate_per_il_gruppo, lista_downfloaters_per_il_prossimo_gruppo)
    """
    print(f"\nDEBUG pair_score_group: Processo gruppo con {len(group_players)} giocatori + {len(downfloaters_in)} downfloaters.") # DEBUG
    combined_group = downfloaters_in + group_players
    combined_group.sort(key=lambda x: (-x.get("initial_elo", 0), x.get("last_name", "").lower(), x.get("first_name", "").lower()))
    print(f"DEBUG pair_score_group: Gruppo combinato ordinato: {[p['id'] for p in combined_group]}") # DEBUG
    matches_in_this_step = [] # Lista temporanea per le partite create in questo gruppo
    current_downfloaters = [] # Questi saranno i downfloaters *finali* di questo gruppo
    players_to_pair_in_group = list(combined_group) # Lavora su una copia

    # Gestisci numero dispari: seleziona downfloater E INCREMENTA COUNT
    if len(players_to_pair_in_group) % 2 != 0:
        # Passa il torneo per accedere ai dati aggiornati (bye, float count) necessari alla selezione FIDE-like
        floater = select_downfloater(players_to_pair_in_group, torneo)
        if floater:
            floater_id = floater.get('id')
            if floater_id: # Assicurati che l'ID esista
                # Rimuovi dalla lista da accoppiare
                players_to_pair_in_group = [p for p in players_to_pair_in_group if p.get('id') != floater_id]
                # Aggiungi ai downfloaters finali che verranno restituiti
                current_downfloaters.append(floater)

                # --- INCREMENTA DOWNFLOAT COUNT nel dizionario principale ---
                # Usa il dizionario aggiornato del torneo per modificare lo stato persistente
                floater_data_main = torneo['players_dict'].get(floater_id)
                if floater_data_main:
                     current_count = floater_data_main.get('downfloat_count', 0)
                     # Aggiorna il contatore nel dizionario principale
                     floater_data_main['downfloat_count'] = current_count + 1
                     print(f"DEBUG pair_score_group: Incrementato downfloat_count per {floater_id} a {current_count + 1}") #DEBUG
                else:
                     # Questo sarebbe un errore grave di consistenza dati
                     print(f"ERRORE CRITICO pair_score_group: Impossibile trovare i dati principali di {floater_id} per aggiornare downfloat_count!") #DEBUG
                # --- FINE INCREMENTO ---

                print(f"DEBUG pair_score_group: Gruppo reso pari. Downfloater selezionato: {floater_id}") # DEBUG
            else:
                print("DEBUG pair_score_group: ERRORE - Giocatore selezionato come downfloater non ha un ID?") #DEBUG
        else:
             print("DEBUG pair_score_group: ERRORE - select_downfloater ha restituito None?") # DEBUG

    # Se rimangono meno di 2 giocatori, vanno ai downfloaters finali
    if len(players_to_pair_in_group) < 2:
        print(f"DEBUG pair_score_group: Meno di 2 giocatori rimasti ({len(players_to_pair_in_group)}), diventano downfloaters finali: {[p['id'] for p in players_to_pair_in_group]}") # DEBUG
        # Aggiunge questi ai downfloaters già determinati (quello per numero dispari)
        current_downfloaters.extend(players_to_pair_in_group)
        # Restituisce lista vuota di partite e tutti i downfloaters accumulati
        return [], current_downfloaters

    # Dividi in metà (ora il numero è pari)
    group_size = len(players_to_pair_in_group)
    top_half = players_to_pair_in_group[:group_size // 2]
    bottom_half = players_to_pair_in_group[group_size // 2:]
    print(f"DEBUG pair_score_group: Top Half ({len(top_half)}): {[p['id'] for p in top_half]}") # DEBUG
    print(f"DEBUG pair_score_group: Bottom Half ({len(bottom_half)}): {[p['id'] for p in bottom_half]}") # DEBUG

    # --- Tentativo 1: Fold Pairing ---
    matches_fold, unpaired_top, unpaired_bottom = attempt_fold_pairing(top_half, bottom_half, torneo, round_number)
    # Aggiungi SUBITO le partite trovate nel fold alla lista temporanea di questo gruppo
    matches_in_this_step.extend(matches_fold)

    # --- Tentativo 2: Trasposizioni/Accoppiamenti Alternativi ---
    remaining_top_after_rec = list(unpaired_top)  # Inizializza con gli spaiati dal fold
    remaining_bottom_after_rec = list(unpaired_bottom)
    match_id_to_remove_from_fold = None # ID da rimuovere se swap avviene

    # Esegui solo se ci sono giocatori rimasti spaiati dal primo tentativo
    if unpaired_top or unpaired_bottom:
        print(f"DEBUG pair_score_group: Giocatori rimasti dopo Fold - T:{len(unpaired_top)}, B:{len(unpaired_bottom)}. Chiamo attempt_transpositions...") #DEBUG

        # Passa le partite già fatte nel fold (matches_fold), gli spaiati e il torneo
        new_matches_rec, remaining_top_after_rec, remaining_bottom_after_rec, match_id_to_remove_from_fold = attempt_transpositions(
            unpaired_top,
            unpaired_bottom,
            matches_fold, # Passa SOLO le partite create nel fold pairing di questo step
            torneo,
            round_number
        )

        # Se la trasposizione ha avuto successo e richiede la rimozione di una partita originale:
        if match_id_to_remove_from_fold is not None:
             print(f"DEBUG pair_score_group: Rimuovo match originale ID {match_id_to_remove_from_fold} (causa trasposizione).") #DEBUG
             # Rimuovi la partita originale dalla lista TEMPORANEA di questo gruppo
             matches_in_this_step = [m for m in matches_in_this_step if m.get('id') != match_id_to_remove_from_fold]

        # Aggiungi le nuove partite create dal recupero (se ce ne sono)
        if new_matches_rec:
             print(f"DEBUG pair_score_group: Aggiungo {len(new_matches_rec)} partite da recupero (transposizioni/alternativi).") #DEBUG
             matches_in_this_step.extend(new_matches_rec)
    # else: Fold pairing ha accoppiato tutti
    # --- Tentativo 3: Pairing Within Halves (ULTIMA ISTANZA) ---
    # Chiama questo SE E SOLO SE rimangono giocatori spaiati DOPO il tentativo di trasposizione/recupero
    if remaining_top_after_rec or remaining_bottom_after_rec:
        print(f"DEBUG pair_score_group: Giocatori rimasti dopo Recupero - T:{len(remaining_top_after_rec)}, B:{len(remaining_bottom_after_rec)}. Chiamo attempt_pair_within_halves...") #DEBUG

        # Passa i giocatori rimasti dalla fase precedente
        within_halves_matches, final_unpaired = attempt_pair_within_halves(remaining_top_after_rec,remaining_bottom_after_rec,torneo,round_number)

        if within_halves_matches:
             print(f"DEBUG pair_score_group: Aggiungo {len(within_halves_matches)} partite da within-halves.") #DEBUG
             matches_in_this_step.extend(within_halves_matches)

        # I giocatori ancora spaiati DOPO QUESTO ULTIMO TENTATIVO diventano downfloaters finali
        if final_unpaired:
             print(f"DEBUG pair_score_group: Giocatori rimasti ANCHE dopo within-halves. Diventano Downfloaters finali: {[p['id'] for p in final_unpaired]}") # DEBUG
             # Aggiungi ai downfloaters già selezionati (quello per numero dispari)
             current_downfloaters.extend(final_unpaired)
    # else: Non c'erano giocatori rimasti dopo il recupero (transposizioni/alternativi)

    # Ritorna le partite totali create per questo gruppo e i downfloaters finali accumulati
    print(f"DEBUG pair_score_group: Fine processo gruppo. Partite totali create: {len(matches_in_this_step)}. Downfloaters finali generati: {[p['id'] for p in current_downfloaters]}") # DEBUG
    return matches_in_this_step, current_downfloaters

# --- Funzione Principale Orchestratrice (sostituisce la vecchia 'pairing') ---
def generate_pairings_for_round(torneo):
    """
    Genera gli abbinamenti per il turno corrente usando la logica modulare FIDE.
    """
    round_number = torneo.get("current_round")
    if round_number is None:
        print("ERRORE: Numero turno corrente non definito nel torneo.")
        return None
    print(f"\nDEBUG: --- INIZIO GENERAZIONE PAIRING TURNO {round_number} ---") # DEBUG

    # Assicura che il dizionario giocatori sia aggiornato e accessibile
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
       torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    players_dict = torneo['players_dict']

    # 1. Prepara lista giocatori attivi
    players_for_pairing = []
    for p_orig in torneo.get('players', []):
        if not p_orig.get("withdrawn", False):
            p_copy = p_orig.copy()
            # Assicura campi necessari (anche se già fatto altrove, è una sicurezza)
            p_copy['opponents'] = set(p_copy.get('opponents', []))
            p_copy.setdefault('points', 0.0)
            p_copy.setdefault('initial_elo', DEFAULT_ELO) # Fallback
            p_copy.setdefault('received_bye', False)
            p_copy.setdefault('white_games', 0)
            p_copy.setdefault('black_games', 0)
            p_copy.setdefault('last_color', None)
            p_copy.setdefault('consecutive_white', 0)
            p_copy.setdefault('consecutive_black', 0)
            # TODO: Aggiungere campo 'downfloat_count' se necessario per regole FIDE più avanzate
            players_for_pairing.append(p_copy)

    if len(players_for_pairing) < 2:
        print("DEBUG: Numero insufficiente di giocatori attivi (<2) per generare accoppiamenti.") # DEBUG
        return [] # Nessuna partita possibile

    # Ordina globalmente per assegnazione Bye
    players_sorted_for_bye = sorted(players_for_pairing, key=lambda x: (x.get("points", 0.0), x.get("initial_elo", 0))) # Punti ASC, Elo ASC

    all_matches = []
    paired_player_ids = set()
    bye_player_id = None

    # 2. Gestione Bye
    active_players_count = len(players_for_pairing)
    if active_players_count % 2 != 0:
        # Trova eleggibili (non hanno ricevuto bye)
        eligible_for_bye = [p for p in players_sorted_for_bye if not p.get("received_bye", False)]

        bye_player_data = None
        if eligible_for_bye:
            # Chi ha punteggio più basso tra gli eleggibili (già ordinati per Punti ASC, Elo ASC)
            bye_player_data = eligible_for_bye[0]
        else:
            # Tutti hanno già ricevuto il bye, lo prende il giocatore con punteggio/elo più basso in assoluto
            print("DEBUG: Tutti i giocatori attivi hanno già ricevuto il Bye. Riassegnazione.") # DEBUG
            if players_sorted_for_bye:
                bye_player_data = players_sorted_for_bye[0]

        if bye_player_data:
            bye_player_id = bye_player_data['id']
            paired_player_ids.add(bye_player_id) # Aggiungi ai già 'accoppiati' (col bye)

            # Crea la 'partita' bye
            bye_match = {
                "id": torneo["next_match_id"], "round": round_number,
                "white_player_id": bye_player_id, "black_player_id": None, "result": "BYE"
            }
            all_matches.append(bye_match)
            torneo["next_match_id"] += 1
            print(f"DEBUG: Assegnato Bye a: {bye_player_data.get('first_name','')} {bye_player_data.get('last_name','')} (ID: {bye_player_id})") # DEBUG

            # IMPORTANTE: Aggiorna SUBITO i dati del giocatore che ha ricevuto il bye nel dizionario principale!
            player_in_main_list = players_dict.get(bye_player_id)
            if player_in_main_list:
                player_in_main_list["received_bye"] = True
                # Assicura che i punti siano float prima di aggiungere
                player_in_main_list["points"] = float(player_in_main_list.get("points", 0.0)) + 1.0
                if "results_history" not in player_in_main_list: player_in_main_list["results_history"] = []
                # Aggiungi voce allo storico (ma il risultato si registra automaticamente)
                player_in_main_list["results_history"].append({
                    "round": round_number, "opponent_id": "BYE_PLAYER_ID",
                    "color": None, "result": "BYE", "score": 1.0
                })
            else:
                 print(f"ERRORE CRITICO: Impossibile trovare giocatore {bye_player_id} per aggiornare dati Bye.")
                 # Potrebbe essere necessario interrompere qui o gestire l'errore
                 return None # Segnala fallimento grave
        else:
            print("ERRORE: Impossibile assegnare il Bye nonostante numero dispari di giocatori.")
            return None # Fallimento

    # 3. Prepara giocatori per accoppiamento effettivo
    players_to_pair = [p for p in players_for_pairing if p['id'] not in paired_player_ids]

    if not players_to_pair and not all_matches: # Nessuno da accoppiare e nessun bye
         print("DEBUG: Nessun giocatore da accoppiare e nessun bye assegnato.") #DEBUG
         return []
    elif not players_to_pair and all_matches: # Caso possibile: 1 giocatore, riceve bye
        print("DEBUG: Un solo giocatore attivo, ha ricevuto il bye. Nessun'altra partita.") #DEBUG
        # Non aggiorniamo colori/avversari qui, solo il bye è stato gestito
        return all_matches # Ritorna solo la partita BYE

    if len(players_to_pair) % 2 != 0:
        print(f"ERRORE CRITICO: Numero dispari di giocatori ({len(players_to_pair)}) rimasti DOPO assegnazione bye. Qualcosa non va.")
        return None # Fallimento logico

    # 4. Raggruppa per punteggio
    score_groups = {}
    for p in players_to_pair:
        score = p.get("points", 0.0)
        # Usa una chiave che gestisca float e None/stringhe in modo sicuro
        score_key = float(score) if isinstance(score, (int, float)) else -float('inf')
        if score_key not in score_groups: score_groups[score_key] = []
        score_groups[score_key].append(p)
    print(f"DEBUG: Gruppi di punteggio creati: { {s: [p['id'] for p in g] for s, g in score_groups.items()} }") # DEBUG

    # Ordina i gruppi di punteggio dal più alto al più basso
    sorted_scores = sorted(score_groups.keys(), reverse=True)

    # 5. Itera sui gruppi e accoppia
    downfloaters_from_previous = []
    # all_matches già contiene il bye se presente

    for score in sorted_scores:
        print(f"\nDEBUG: Processo score group {score}...") #DEBUG
        group_player_list = score_groups[score]

        # Chiamata alla funzione che gestisce il singolo gruppo
        matches_this_group, downfloaters_to_next = pair_score_group(
            group_player_list,
            downfloaters_from_previous,
            torneo, # Passa l'oggetto torneo per accesso a dati/ID
            round_number
        )

        if matches_this_group is None: # Se pair_score_group segnala un errore interno grave
             print(f"ERRORE CRITICO durante l'accoppiamento del gruppo {score}.")
             return None # Interrompi tutto

        all_matches.extend(matches_this_group)
        downfloaters_from_previous = downfloaters_to_next # Prepara per il prossimo gruppo

    # 6. Verifica Finale
    if downfloaters_from_previous:
        print("\n--- ERRORE CRITICO DI ACCOPPIAMENTO FINALE ---") # DEBUG
        print("Impossibile accoppiare i seguenti giocatori (rimasti come downfloaters finali):") # DEBUG
        downfloaters_from_previous.sort(key=lambda x: (-x.get("points", 0.0), -x.get("initial_elo", 0)))
        for p in downfloaters_from_previous:
            opponents_str = ", ".join(list(p.get('opponents', set())))
            color_diff = p.get("white_games", 0) - p.get("black_games", 0)
            last_c = p.get("last_color", "N/A")
            cons_w = p.get("consecutive_white", 0)
            cons_b = p.get("consecutive_black", 0)
            print(f"  - ID: {p['id']} Pts: {p.get('points', 0.0)} Elo: {p.get('initial_elo', 0)} | Opp: [{opponents_str}] | ColDiff: {color_diff} Last: {last_c} ConsW: {cons_w} ConsB: {cons_b}") # DEBUG
        print("L'algoritmo (anche con recupero base) non è riuscito a risolvere.")
        print("Potrebbe essere necessaria logica di trasposizione più avanzata o pairing within-halves.")
        return None # Fallimento generazione turno

    # 7. Successo: Aggiorna dati giocatori nella struttura principale del torneo
    print(f"\nDEBUG: Accoppiamento Turno {round_number} completato con successo. {len(all_matches)} partite totali (incluso bye se presente).") #DEBUG
    print("DEBUG: Aggiornamento dati post-accoppiamento (avversari, colori)...") #DEBUG
    for match in all_matches:
        # Salta il BYE, già gestito
        if match.get("result") == "BYE" or match.get("black_player_id") is None:
             continue

        white_player_id = match.get("white_player_id")
        black_player_id = match.get("black_player_id")

        white_p = players_dict.get(white_player_id)
        black_p = players_dict.get(black_player_id)

        if not white_p or not black_p:
            print(f"ERRORE: Giocatore non trovato nel dizionario principale per aggiornare dati partita ID {match.get('id')}")
            continue

        # Aggiorna lista avversari (assicurati che siano set)
        if not isinstance(white_p.get('opponents'), set): white_p['opponents'] = set(white_p.get('opponents', []))
        if not isinstance(black_p.get('opponents'), set): black_p['opponents'] = set(black_p.get('opponents', []))
        white_p["opponents"].add(black_player_id)
        black_p["opponents"].add(white_player_id)

        # Aggiorna statistiche colore
        white_p["white_games"] = white_p.get("white_games", 0) + 1
        black_p["black_games"] = black_p.get("black_games", 0) + 1
        white_p["last_color"] = "white"
        black_p["last_color"] = "black"
        # Aggiorna colori consecutivi
        white_p["consecutive_white"] = white_p.get("consecutive_white", 0) + 1
        white_p["consecutive_black"] = 0
        black_p["consecutive_black"] = black_p.get("consecutive_black", 0) + 1
        black_p["consecutive_white"] = 0
        # Stampa DEBUG colori aggiornati
        # print(f"DEBUG PostPair Update W: {white_p['id']} - W:{white_p['white_games']}, B:{white_p['black_games']}, Last:{white_p['last_color']}, CW:{white_p['consecutive_white']}, CB:{white_p['consecutive_black']}") #DEBUG
        # print(f"DEBUG PostPair Update B: {black_p['id']} - W:{black_p['white_games']}, B:{black_p['black_games']}, Last:{black_p['last_color']}, CW:{black_p['consecutive_white']}, CB:{black_p['consecutive_black']}") #DEBUG


    print(f"DEBUG: --- FINE GENERAZIONE PAIRING TURNO {round_number} ---") # DEBUG
    return all_matches

# ==============================================================================
# --- FINE NUOVA LOGICA DI PAIRING MODULARE (Fase 1) ---
# ==============================================================================

def input_players(players_db):
    """
    Gestisce l'input dei giocatori per un torneo.
    1. Cerca per ID esatto nel DB.
    2. Se non è ID, cerca per Nome/Cognome parziale nel DB.
       - Se 1 match: aggiunge al torneo.
       - Se >1 match: mostra lista e richiede input più specifico.
    3. Se nessun match (né ID né ricerca), chiede Nome, Cognome, Elo separatamente.
       - Se Nome vuoto: torna al prompt iniziale.
       - Se Cognome o Elo vuoti/invalidi: usa default o segnala errore.
    4. Se input iniziale vuoto: termina inserimento (con check minimo giocatori).
    """
    players_in_tournament = []
    added_player_ids = set() # Tiene traccia degli ID già aggiunti a QUESTO torneo
    print("\n--- Inserimento Giocatori ---")
    print("Inserire ID esatto, oppure parte del Nome/Cognome per la ricerca.")
    print("Lasciare vuoto per terminare l'inserimento.")

    while True:
        current_num_players = len(players_in_tournament)
        data = input(f"\nGiocatore {current_num_players + 1} (ID o Ricerca Nome/Cognome, vuoto per terminare): ").strip()

        # --- Caso 4: Input Iniziale Vuoto -> Termina Inserimento ---
        if not data:
            min_players = 2 # Minimo per un torneo
            if current_num_players < min_players:
                print(f"\nAttenzione: Sono necessari almeno {min_players} giocatori per avviare il torneo.")
                continua = input("Ci sono meno di 2 giocatori. Continuare l'inserimento? (S/n): ").strip().lower()
                if continua == 'n':
                     print(f"\nInserimento terminato con {current_num_players} giocatori (insufficienti).")
                     # Ritorna la lista attuale, il chiamante deciderà se è valida
                     break
                else:
                     continue # Continua a chiedere giocatori (torna all'input data)
            else:
                # Numero sufficiente, termina
                print(f"\nInserimento terminato con {current_num_players} giocatori.")
                break # Esce dal ciclo while

        # Variabili per tenere traccia dello stato dell'iterazione
        player_id_to_add = None
        player_data_to_add = None # Conterrà i dati del giocatore trovato/creato

        # --- Tentativo 1: Check Esatto ID ---
        potential_id = data.upper()
        is_id_match = False
        if potential_id in players_db:
            print(f"Input riconosciuto come ID esatto: {potential_id}")
            is_id_match = True
            player_id_to_add = potential_id
            player_data_to_add = players_db[potential_id] # Dati presi direttamente dal DB

        # --- Tentativo 2: Ricerca Parziale (se non era ID) ---
        if not is_id_match:
            print(f"ID non trovato. Eseguo ricerca parziale per '{data}'...")
            search_lower = data.lower()
            matches = [] # Lista per contenere i DIZIONARI dei giocatori trovati
            for p_data_search in players_db.values():
                fname_lower = p_data_search.get('first_name', '').lower()
                lname_lower = p_data_search.get('last_name', '').lower()
                # Cerca la sotto-stringa nel nome O nel cognome
                if search_lower in fname_lower or search_lower in lname_lower:
                    matches.append(p_data_search)

            # --- Gestione Risultati Ricerca Parziale ---
            if len(matches) == 1:
                # Trovato risultato unico con ricerca parziale!
                player_data_to_add = matches[0]
                player_id_to_add = player_data_to_add['id']
                print(f"Trovato giocatore unico tramite ricerca: {player_data_to_add.get('first_name')} {player_data_to_add.get('last_name')} (ID: {player_id_to_add})")
                # Procedi all'aggiunta (verrà fatto dopo i tentativi)

            elif len(matches) > 1:
                # Trovati risultati multipli, mostra lista e richiedi input più specifico
                print(f"Trovati {len(matches)} giocatori contenenti '{data}'. Specifica usando l'ID esatto:")
                # Ordina i risultati per cognome, nome per una visualizzazione chiara
                matches.sort(key=lambda p: (p.get('last_name', '').lower(), p.get('first_name', '').lower()))
                for i, p_match in enumerate(matches, 1):
                    p_id = p_match.get('id', 'N/D')
                    p_fname = p_match.get('first_name', 'N/D')
                    p_lname = p_match.get('last_name', 'N/D')
                    p_elo = p_match.get('current_elo', 'N/D')
                    p_bdate = p_match.get('birth_date')
                    # Assumendo che format_date_locale sia definita correttamente altrove
                    try:
                         p_bdate_formatted = format_date_locale(p_bdate) if p_bdate else 'N/D'
                    except NameError: # Se format_date_locale non è definita in questo scope
                         p_bdate_formatted = p_bdate if p_bdate else 'N/D'

                    print(f"  {i}. ID: {p_id:<9} - {p_fname} {p_lname} (Elo DB: {p_elo}, Nato: {p_bdate_formatted})")
                # Non aggiungere nessuno ora, richiedi input più specifico nel prossimo ciclo
                continue # Salta il resto dell'iterazione corrente

            else: # len(matches) == 0 -> Nessun match (né ID né ricerca)
                # --- Tentativo 3: Input Manuale Separato ---
                print(f"Nessun giocatore trovato per '{data}'. Procedere con inserimento manuale:")
                first_name_manual = input("  Nome: ").strip()
                if not first_name_manual:
                     print("Inserimento manuale annullato (Nome vuoto).")
                     continue # Torna alla richiesta ID/Ricerca

                last_name_manual = input("  Cognome: ").strip()
                if not last_name_manual:
                     print("Errore: Cognome non può essere vuoto. Inserimento manuale annullato.")
                     continue # Torna alla richiesta ID/Ricerca

                elo_manual_input = input(f"  Elo (default {DEFAULT_ELO}): ").strip()
                elo_manual = DEFAULT_ELO
                if elo_manual_input:
                    try:
                        elo_manual = int(elo_manual_input)
                    except ValueError:
                        print(f"  Elo non valido '{elo_manual_input}'. Uso il default {DEFAULT_ELO}.")

                # Aggiungi/Aggiorna nel DB principale e ottieni l'ID
                # Assicurati che add_or_update_player_in_db riceva nomi separati
                player_id_from_db = add_or_update_player_in_db(players_db, first_name_manual, last_name_manual, elo_manual)

                if player_id_from_db is None:
                     print("Errore durante la gestione del giocatore nel DB. Riprova.")
                     continue # Torna alla richiesta ID/Ricerca
                else:
                     # Recupera i dati appena creati/trovati dal DB
                     player_data_to_add = players_db[player_id_from_db]
                     player_id_to_add = player_id_from_db
                     # L'Elo per il TORNEO sarà quello inserito manualmente ORA
                     initial_tournament_elo = elo_manual # Salva elo per dopo

        # --- Aggiunta Giocatore al Torneo (se trovato/creato e non duplicato) ---
        if player_id_to_add and player_data_to_add: # Se un ID e i dati sono stati determinati
             if player_id_to_add in added_player_ids:
                 print(f"Errore: Giocatore ID {player_id_to_add} ({player_data_to_add.get('first_name')} {player_data_to_add.get('last_name')}) è già stato aggiunto a questo torneo.")
             else:
                 # Prepara i dati finali specifici per il torneo
                 # Determina l'Elo iniziale corretto per il torneo
                 if is_id_match or len(matches) == 1: # Se aggiunto via ID o Ricerca Unica
                      try:
                           # Usa l'elo CORRENTE del DB
                           elo_torneo = int(player_data_to_add.get('current_elo', DEFAULT_ELO))
                      except (ValueError, TypeError):
                           print(f"Warning: Elo DB non valido per {player_id_to_add}. Uso {DEFAULT_ELO}.")
                           elo_torneo = DEFAULT_ELO
                 else: # Se aggiunto via Input Manuale (len(matches) == 0)
                      elo_torneo = initial_tournament_elo # Usa l'elo inserito manualmente

                 # Crea il dizionario per la lista players_in_tournament
                 player_data_for_tournament = {
                     "id": player_id_to_add,
                     "first_name": player_data_to_add.get('first_name', 'N/D'),
                     "last_name": player_data_to_add.get('last_name', 'N/D'),
                     "initial_elo": elo_torneo, # Elo all'inizio del torneo
                     "points": 0.0, "results_history": [], "opponents": set(),
                     "white_games": 0, "black_games": 0, "last_color": None,
                     "consecutive_white": 0, "consecutive_black": 0,
                     "received_bye": False, "buchholz": 0.0, "buchholz_cut1": None,
                     "performance_rating": None, "elo_change": None,
                     "k_factor": None, "games_this_tournament": 0,
                     "downfloat_count": 0,
                     "final_rank": None, "withdrawn": False
                 }
                 players_in_tournament.append(player_data_for_tournament)
                 added_player_ids.add(player_id_to_add)
                 print(f"-> Giocatore {player_data_for_tournament['first_name']} {player_data_for_tournament['last_name']} (Elo Torneo: {elo_torneo}) aggiunto al torneo.")
        # Se non è stato trovato/creato un ID valido (es. ricerca multipla o errore manuale),
        # non si entra in questo blocco e il ciclo while ricomincia chiedendo un nuovo input.
    return players_in_tournament

def update_match_result(torneo):
    """Chiede l'ID partita, aggiorna il risultato o gestisce 'cancella'.
       Restituisce True se un risultato è stato aggiornato o cancellato, False altrimenti."""
    current_round_num = torneo["current_round"]
    # Assicura che il dizionario sia aggiornato
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    players_dict = torneo['players_dict']
    # Trova i dati del turno corrente
    current_round_data = None
    round_index = -1
    for i, r in enumerate(torneo.get("rounds", [])):
        # Indentazione corretta
        if r.get("round") == current_round_num:
            current_round_data = r
            round_index = i
            break
    if not current_round_data:
        print(f"ERRORE: Dati turno {current_round_num} non trovati per aggiornamento risultati.")
        return False
    while True: # Loop principale per chiedere ID o 'cancella'
        # Trova partite pendenti *ogni volta* nel loop per aggiornare il prompt
        pending_matches_this_round = []
        if "matches" in current_round_data:
            for m in current_round_data["matches"]:
                # Considera pendente se non ha risultato E non è un BYE
                if m.get("result") is None and m.get("black_player_id") is not None:
                    pending_matches_this_round.append(m)
        if not pending_matches_this_round:
            # print("Info: Nessuna partita da registrare/cancellare per il turno corrente.") # Rimosso per brevità
            return False # Nessuna azione possibile, esce dal loop di update
        print("\nPartite del turno {} ancora da registrare:".format(current_round_num))
        pending_matches_this_round.sort(key=lambda m: m.get('id', 0)) # Ordina per ID partita
        for m in pending_matches_this_round:
            white_p = players_dict.get(m.get('white_player_id'))
            black_p = players_dict.get(m.get('black_player_id'))
            if white_p and black_p:
                # Indentazione corretta
                w_name = f"{white_p.get('first_name','?')} {white_p.get('last_name','?')}"
                w_elo = white_p.get('initial_elo','?')
                b_name = f"{black_p.get('first_name','?')} {black_p.get('last_name','?')}"
                b_elo = black_p.get('initial_elo','?')
                print(f"  ID: {m.get('id','?'):<3} - {w_name:<20} [{w_elo:>4}] vs {b_name:<20} [{b_elo:>4}]")
            else:
                # Indentazione corretta
                # Messaggio di errore se i giocatori non sono trovati
                print(f"  ID: {m.get('id','?'):<3} - Errore: Giocatore/i non trovato/i (W:{m.get('white_player_id')}, B:{m.get('black_player_id')}).")
        # Crea il prompt dinamico con gli ID pendenti
        pending_ids = [str(m['id']) for m in pending_matches_this_round]
        prompt_ids_str = "-".join(pending_ids) if pending_ids else "N/A"
        prompt = f"Inserisci ID partita da aggiornare [{prompt_ids_str}], 'cancella' o lascia vuoto: "
        match_id_str = input(prompt).strip()
        if not match_id_str:
            return False # L'utente vuole uscire dall'aggiornamento risultati per ora
        # --- Gestione Comando 'cancella' ---
        if match_id_str.lower() == 'cancella':
            completed_matches = []
            if "matches" in current_round_data:
                for m in current_round_data["matches"]:
                    # Può cancellare solo partite giocate (non BYE, non pendenti)
                    if m.get("result") is not None and m.get("result") != "BYE":
                        completed_matches.append(m)
            if not completed_matches:
                print("Nessuna partita completata in questo turno da poter cancellare.")
                continue # Torna al prompt principale ID/cancella
            print("\nPartite completate nel turno {} (possibile cancellare risultato):".format(current_round_num))
            completed_matches.sort(key=lambda m: m.get('id', 0)) # Ordina per ID
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
                    print(f"  ID: {match_id:<3} - {w_name:<20} vs {b_name:<20} = {result}")
                else:
                    print(f"  ID: {match_id:<3} - Errore giocatori = {result} (W:{m.get('white_player_id')}, B:{m.get('black_player_id')})")
            cancel_prompt_ids = "-".join(completed_ids) if completed_ids else "N/A"
            cancel_prompt = f"Inserisci ID partita da cancellare [{cancel_prompt_ids}] (o vuoto per annullare): "
            cancel_id_str = input(cancel_prompt).strip()
            if not cancel_id_str:
                continue # Torna al prompt principale ID/cancella
            try:
                cancel_id = int(cancel_id_str)
                match_to_cancel = None
                match_cancel_index = -1
                # Cerca l'ID tra le partite *di questo turno* (memorizzate in current_round_data)
                if "matches" in current_round_data:
                    for i, m in enumerate(current_round_data["matches"]):
                        # Indentazione corretta
                        # Deve avere l'ID giusto ED essere una partita completata (non BYE)
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
                        print(f"ERRORE: Giocatori non trovati per la partita {cancel_id} (W:{white_p_id}, B:{black_p_id}), cancellazione annullata.")
                        continue
                    # Determina i punteggi da stornare
                    white_score_revert = 0.0
                    black_score_revert = 0.0
                    if old_result == "1-0": white_score_revert = 1.0
                    elif old_result == "0-1": black_score_revert = 1.0
                    elif old_result == "1/2-1/2": white_score_revert, black_score_revert = 0.5, 0.5
                    # Non serve stornare per "0-0F" perché i punti erano già 0
                    # Storna Punti (assicurati siano float)
                    white_p["points"] = float(white_p.get("points", 0.0)) - white_score_revert
                    black_p["points"] = float(black_p.get("points", 0.0)) - black_score_revert
                    # Rimuovi da Storico Risultati (cerca l'entry specifica di questo round/avversario)
                    history_removed_w = False
                    if "results_history" in white_p:
                        initial_len = len(white_p["results_history"])
                        white_p["results_history"] = [
                            entry for entry in white_p["results_history"]
                            if not (entry.get("round") == current_round_num and entry.get("opponent_id") == black_p_id)
                        ]
                        history_removed_w = (len(white_p["results_history"]) < initial_len)
                    history_removed_b = False
                    if "results_history" in black_p:
                        initial_len = len(black_p["results_history"])
                        black_p["results_history"] = [
                            entry for entry in black_p["results_history"]
                            if not (entry.get("round") == current_round_num and entry.get("opponent_id") == white_p_id)
                        ]
                        history_removed_b = (len(black_p["results_history"]) < initial_len)
                    # Azzera risultato nella partita all'interno della struttura `torneo`
                    torneo["rounds"][round_index]["matches"][match_cancel_index]["result"] = None
                    print(f"Risultato ({old_result}) della partita ID {cancel_id} cancellato.")
                    if not history_removed_w: print(f"Warning: Voce storico non trovata per {white_p_id} vs {black_p_id} durante cancellazione.")
                    if not history_removed_b: print(f"Warning: Voce storico non trovata per {black_p_id} vs {white_p_id} durante cancellazione.")
                    # Salva subito il torneo dopo la cancellazione
                    save_tournament(torneo)
                    # Ricarica il dizionario interno per riflettere le modifiche
                    save_current_tournament_round_file(torneo)
                    torneo['players_dict'] = {p['id']: p for p in torneo['players']}
                    return True # Indica che una modifica è stata fatta, forza ricalcolo prompt nel main loop
                else:
                    print(f"ID {cancel_id} non corrisponde a una partita completata cancellabile in questo turno.")
            except ValueError:
                # Indentazione corretta
                print("ID non valido per la cancellazione. Inserisci un numero intero.")
            continue # Torna al prompt principale dopo l'operazione di cancellazione (o errore)
        # --- Fine Gestione 'cancella' ---
        # --- Gestione Inserimento Risultato Normale ---
        try:
            match_id_to_update = int(match_id_str)
            match_to_update = None
            match_index_in_round = -1
            # Cerca tra le partite del turno corrente (in current_round_data)
            if "matches" in current_round_data:
                # Indentazione corretta
                for i, m in enumerate(current_round_data["matches"]):
                    if m.get('id') == match_id_to_update:
                        # Indentazione corretta
                        if m.get("result") is None and m.get("black_player_id") is not None:
                            # Indentazione corretta
                            # Trovata partita pendente corrispondente
                            match_to_update = m
                            match_index_in_round = i
                            break
                        elif m.get("result") == "BYE":
                            # Indentazione corretta
                            print(f"Info: La partita {match_id_to_update} è un BYE, non registrabile.")
                            # Non impostare match_to_update, così non chiede risultato
                            break # Esce dal for, tornerà al prompt ID/cancella
                        else:
                            # Indentazione corretta
                            # Trovata, ma ha già un risultato
                            print(f"Info: La partita {match_id_to_update} ha già un risultato ({m.get('result','?')}). Usa 'cancella' per modificarlo.")
                            # Non impostare match_to_update
                            break # Esce dal for
            # Se abbiamo trovato una partita pendente da aggiornare
            if match_to_update:
                white_p_id = match_to_update['white_player_id']
                black_p_id = match_to_update['black_player_id']
                white_p = players_dict.get(white_p_id)
                black_p = players_dict.get(black_p_id)
                if not white_p or not black_p:
                    # Indentazione corretta
                    print(f"ERRORE CRITICO: Giocatore/i non trovato/i per la partita {match_id_to_update} (W:{white_p_id}, B:{black_p_id}). Impossibile registrare.")
                    # Potrebbe indicare corruzione dati, meglio non procedere con questa partita
                    continue # Richiedi un altro ID
                w_name = f"{white_p.get('first_name','?')} {white_p.get('last_name','?')}"
                b_name = f"{black_p.get('first_name','?')} {black_p.get('last_name','?')}"
                print(f"Partita selezionata: {w_name} vs {b_name}")
                # Chiedi risultato con opzioni chiare
                prompt_risultato = "Risultato [1-0, 0-1, 1/2, 0-0F, 1-F, F-1]: "
                result_input = input(prompt_risultato).strip()
                new_result = None
                white_score = 0.0
                black_score = 0.0
                valid_input = True
                if result_input == '1-0':
                    new_result = "1-0"
                    white_score = 1.0
                elif result_input == '0-1':
                    new_result = "0-1"
                    black_score = 1.0
                elif result_input == '1/2':
                    new_result = "1/2-1/2"
                    white_score = 0.5
                    black_score = 0.5
                elif result_input == '0-0F':
                    new_result = "0-0F" # Forfait/Non giocata - entrambi 0 punti
                    white_score = 0.0
                    black_score = 0.0
                    print("Partita marcata come non giocata/annullata (0-0F).")
                elif result_input == '1-F':
                    new_result = "1-F"  # Stringa per vittoria Bianco per Forfait
                    white_score = 1.0
                    black_score = 0.0
                    print("Partita registrata come vittoria del Bianco per Forfait (1-F).")
                elif result_input == 'F-1':
                    new_result = "F-1"  # Stringa per vittoria Nero per Forfait
                    white_score = 0.0
                    black_score = 1.0
                    print("Partita registrata come vittoria del Nero per Forfait (F-1).")                
                else:
                    print("Input non valido. Usa 1-0, 0-1, 1/2, 0-0F, 1-F, F-1.")
                    valid_input = False
                if valid_input and new_result is not None:
                    # Indentazione corretta
                    # Aggiorna punti (assicurati siano float)
                    white_p["points"] = float(white_p.get("points", 0.0)) + white_score
                    black_p["points"] = float(black_p.get("points", 0.0)) + black_score
                    # Aggiorna storico risultati
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
                    # Aggiorna risultato nella struttura del torneo
                    torneo["rounds"][round_index]["matches"][match_index_in_round]["result"] = new_result
                    print("Risultato registrato.")
                    # Salva lo stato dopo la registrazione
                    save_tournament(torneo)
                    save_current_tournament_round_file(torneo)
                    # Aggiorna il dizionario interno
                    torneo['players_dict'] = {p['id']: p for p in torneo['players']}
                    return True # Indica che un aggiornamento è stato fatto
            # Se match_to_update è None ma l'ID era valido (già registrato o BYE),
            # il messaggio è stato stampato sopra e il loop continua chiedendo ID.
            elif match_index_in_round == -1 and match_id_str.lower() != 'cancella': # ID numerico ma non trovato nel turno
                # Indentazione corretta
                print("ID partita non valido per questo turno. Riprova.")
        except ValueError:
            # Indentazione corretta
            # Se l'input non era 'cancella' e non era un numero intero
            if match_id_str.lower() != 'cancella':
                print("ID non valido. Inserisci un numero intero o 'cancella'.")

def save_current_tournament_round_file(torneo):
    """
    Salva lo stato del turno corrente in un file TXT che viene sovrascritto.
    Mostra partite giocate e da giocare.
    """
    tournament_name = torneo.get('name', 'Torneo_Senza_Nome')
    sanitized_name = sanitize_filename(tournament_name)
    current_round_num = torneo.get("current_round")
    if current_round_num is None:
        print("Salvataggio file turno corrente: Numero turno non definito.")
        return
    filename = f"tornello - {sanitized_name} - turno corrente.txt"
    # Trova i dati del turno corrente
    round_data = None
    for rnd in torneo.get("rounds", []):
        if rnd.get("round") == current_round_num:
            round_data = rnd
            break
    if round_data is None or "matches" not in round_data:
        # Potrebbe essere che il turno non sia ancora stato generato (es. all'inizio)
        # o che ci sia un problema. Se non ci sono dati, non scriviamo nulla o un file vuoto.
        try:
            with open(filename, "w", encoding='utf-8-sig') as f:
                f.write(f"Turno {current_round_num}\n")
                f.write("(Nessuna partita ancora definita per questo turno)\n")
            print(f"File stato turno corrente '{filename}' aggiornato (turno non ancora popolato).")
        except IOError as e:
            print(f"Errore durante la scrittura del file stato turno corrente '{filename}': {e}")        
        return

    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    players_dict = torneo['players_dict']
    all_matches_in_round = round_data.get("matches", [])
    played_matches = []
    pending_matches = []
    bye_player_info = None
    for match in sorted(all_matches_in_round, key=lambda m: m.get('id', 0)): # Ordina per ID partita
        if match.get("black_player_id") is None: # È un BYE
            bye_p = players_dict.get(match.get('white_player_id'))
            if bye_p:
                bye_player_info = f"{bye_p.get('first_name','?')} {bye_p.get('last_name','?')} ha il BYE"
            continue
        white_p = players_dict.get(match.get('white_player_id'))
        black_p = players_dict.get(match.get('black_player_id'))
        w_name = f"{white_p.get('first_name','?')} {white_p.get('last_name','?')}" if white_p else "Giocatore Bianco Sconosciuto"
        b_name = f"{black_p.get('first_name','?')} {black_p.get('last_name','?')}" if black_p else "Giocatore Nero Sconosciuto"
        match_id = match.get('id', '?')
        match_line = f"{match_id} {w_name} - {b_name}"
        if match.get("result") is not None:
            played_matches.append(f"{match_line} {match.get('result')}")
        else:
            pending_matches.append(match_line)

    try:
        with open(filename, "w", encoding='utf-8-sig') as f: # Modalità "w" per sovrascrivere
            f.write(f"Turno {current_round_num}\n")

            f.write("giocate\n")
            if played_matches:
                for p_match_str in played_matches:
                    f.write(f" {p_match_str}\n")
            else:
                f.write(" (nessuna)\n")

            f.write("da giocare\n")
            if pending_matches:
                for pend_match_str in pending_matches:
                    f.write(f" {pend_match_str}\n")
            else:
                f.write(" (nessuna)\n")

            if bye_player_info:
                f.write(f"\n {bye_player_info}\n")

        print(f"File stato turno corrente '{filename}' sovrascritto.")
    except IOError as e:
        print(f"Errore durante la sovrascrittura del file stato turno corrente '{filename}': {e}")


def append_completed_round_to_history_file(torneo, completed_round_number):
    """
    Accoda i dettagli di un turno concluso al file storico dei turni.
    Il formato è simile alla vecchia funzione save_round_text.
    """
    tournament_name = torneo.get('name', 'Torneo_Senza_Nome')
    sanitized_name = sanitize_filename(tournament_name)
    filename = f"tornello - {sanitized_name} - turni conclusi.txt"

    round_data = None
    for rnd in torneo.get("rounds", []):
        if rnd.get("round") == completed_round_number:
            round_data = rnd
            break

    if round_data is None or "matches" not in round_data:
        print(f"Dati o partite del turno concluso {completed_round_number} non trovati per il salvataggio storico.")
        return
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    players_dict = torneo['players_dict']

    all_matches_in_round = round_data.get("matches", [])
    # Ordina le partite per ID per consistenza (o per scacchiera se si vuole mantenere la logica originale)
    # Per semplicità, qui ordiniamo per ID. La vecchia logica ordinava per Elo medio per scacchiera.
    # Manteniamo l'ordinamento per Elo medio per scacchiera per coerenza con l'output precedente.
    
    playable_matches = [m for m in all_matches_in_round if m.get("black_player_id") is not None]
    bye_match = next((m for m in all_matches_in_round if m.get("black_player_id") is None), None)
    def get_average_elo_for_sort(match, players_dict_local): # Rinominata per evitare conflitti
        w_id = match.get('white_player_id')
        b_id = match.get('black_player_id')
        w_elo_str = players_dict_local.get(w_id, {}).get('initial_elo', '0')
        b_elo_str = players_dict_local.get(b_id, {}).get('initial_elo', '0')
        try:
            w_elo = float(w_elo_str if w_elo_str is not None else 0.0)
            b_elo = float(b_elo_str if b_elo_str is not None else 0.0)
            if w_elo == 0.0 and b_elo == 0.0: return 0.0
            if w_elo == 0.0: return b_elo
            if b_elo == 0.0: return w_elo
            return (w_elo + b_elo) / 2.0
        except (ValueError, TypeError): return 0.0

    playable_matches.sort(key=lambda m: get_average_elo_for_sort(m, players_dict), reverse=True)

    try:
        with open(filename, "a", encoding='utf-8-sig') as f: # Modalità "a" per append
            f.seek(0, os.SEEK_END)
            if f.tell() > 0:
                 f.write("\n" + "="*30 + f" TURNO {completed_round_number} CONCLUSO " + "="*30 + "\n")
            else:
                 f.write(f"Torneo: {torneo.get('name', 'Nome Mancante')}\n")
                 f.write("=" * 80 + "\n")
                 f.write("\n" + "="*30 + f" TURNO {completed_round_number} CONCLUSO " + "="*30 + "\n") # Anche per il primo turno nel file
            round_dates_list = torneo.get("round_dates", [])
            current_round_dates = next((rd for rd in round_dates_list if rd.get("round") == completed_round_number), None)
            if current_round_dates:
                start_d_str = current_round_dates.get('start_date')
                end_d_str = current_round_dates.get('end_date')
                f.write(f"\tPeriodo: {format_date_locale(start_d_str)} - {format_date_locale(end_d_str)}\n")
            else:
                f.write("\tPeriodo: Date non trovate\n")
            f.write("\t"+"-" * 76 + "\n")
            header_partite = "Sc | ID  | Bianco                   [Elo] (Pt) - Nero                     [Elo] (Pt) | Risultato"
            f.write(f"\t{header_partite}\n")
            f.write(f"\t" + "-" * len(header_partite) + "\n")

            for board_num_idx, match in enumerate(playable_matches):
                board_num = board_num_idx + 1
                match_id = match.get('id', '?')
                white_p_id = match.get('white_player_id')
                black_p_id = match.get('black_player_id')
                result_str = match.get("result", "ERRORE_RISULTATO_MANCANTE") # Dovrebbe sempre esserci per un turno concluso

                white_p = players_dict.get(white_p_id)
                black_p = players_dict.get(black_p_id)

                # Gestisci casi in cui i giocatori potrebbero mancare (non dovrebbe succedere)
                w_name = "? ?"
                w_elo = "?"
                w_pts = "?"
                if white_p:
                    w_name = f"{white_p.get('first_name','?')} {white_p.get('last_name','')}"
                    w_elo = white_p.get('initial_elo','?')
                    w_pts = format_points(white_p.get('points', 0.0))

                b_name = "? ?"
                b_elo = "?"
                b_pts = "?"
                if black_p:
                    b_name = f"{black_p.get('first_name','?')} {black_p.get('last_name','')}"
                    b_elo = black_p.get('initial_elo','?')
                    b_pts = format_points(black_p.get('points', 0.0))
                line = (f"{board_num:<3}| " # Colonna Scacchiera
                        f"{match_id:<4}| " # Colonna ID (un po' più stretta)
                        f"{w_name:<24} [{w_elo:>4}] ({w_pts:<4}) - "
                        f"{b_name:<24} [{b_elo:>4}] ({b_pts:<4}) | "
                        f"{result_str}")
            f.write(f"\t{line}\n")
            if bye_match:
                match_id = bye_match.get('id', '?')
                white_p_id = bye_match.get('white_player_id')
                white_p = players_dict.get(white_p_id)
                if white_p:
                     w_name = f"{white_p.get('first_name','?')} {white_p.get('last_name','')}"
                     w_elo = white_p.get('initial_elo','?')
                     w_pts = format_points(white_p.get('points', 0.0))
                     line = (f"{'---':<3}| "
                             f"{match_id:<4}| "
                             f"{w_name:<24} [{w_elo:>4}] ({w_pts:<4}) - {'BYE':<31} | BYE")
                     f.write(f"\t{line}\n")
                else:
                     line = f"{'---':<3}| {match_id:<4}| Errore Giocatore Bye ID: {white_p_id:<10} | BYE"
                     f.write(f"\t{line}\n")
        print(f"Dati Turno Concluso {completed_round_number} aggiunti al file storico '{filename}'")
    except IOError as e:
        print(f"Errore durante l'aggiornamento del file storico turni '{filename}': {e}")
    except Exception as general_e:
        print(f"Errore inatteso durante append_completed_round_to_history_file: {general_e}")
        traceback.print_exc()

def save_standings_text(torneo, final=False):
    """
    Salva/Sovrascrive la classifica (parziale o finale) in un unico file TXT.
    Usa i dati già calcolati (come elo_change) presenti nel dizionario 'p'.
    """
    players = torneo.get("players", [])
    if not players:
        print("Warning: Nessun giocatore per generare classifica.")
        return
    # Assicura dizionario aggiornato (anche se dovrebbe esserlo da finalize)
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(players):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    # players_dict = torneo['players_dict'] # Non più strettamente necessario qui se i dati sono in players

    # --- CALCOLO SPAREGGI (BUCHHOLZ) E ORDINAMENTO ---
    # Buchholz va calcolato qui perché serve sempre, anche per l'ordinamento parziale
    print("Calcolo/Aggiornamento Buchholz per classifica...")
    for p in players:
        p_id = p.get('id')
        if not p_id: continue
        if not p.get("withdrawn", False):
            p["buchholz"] = compute_buchholz(p_id, torneo)
            # Calcola B-1 solo se finale E se non già presente (calcolato da finalize)
            if final and "buchholz_cut1" not in p:
                 p["buchholz_cut1"] = compute_buchholz_cut1(p_id, torneo)
            elif not final:
                 p["buchholz_cut1"] = None # Assicura sia None in parziale
        else:
            p["buchholz"] = 0.0
            p["buchholz_cut1"] = None

    # --- RIMOZIONE CALCOLI FINALI RIDONDANTI ---
    # Performance, Elo Change, ARO sono ora calcolati SOLO in finalize_tournament
    # e i risultati sono già presenti nei dizionari 'p' dentro la lista 'players'
    # quando questa funzione viene chiamata con final=True.
    # Non serve ricalcolarli qui.

    # --- ORDINAMENTO E ASSEGNAZIONE RANK (Logica invariata) ---
    # La chiave di sort userà i valori già presenti in 'p'
    def sort_key(player):
        # ... (stessa chiave di ordinamento di prima, usa i campi esistenti in player) ...
        if player.get("withdrawn", False):
            return (0, -float('inf'), -float('inf'), -float('inf'), -float('inf'))
        points = player.get("points", 0.0)
        # Usa i valori esistenti, gestendo None per parziali o errori
        bucch_c1 = player.get("buchholz_cut1", 0.0) if final and player.get("buchholz_cut1") is not None else 0.0
        bucch_tot = player.get("buchholz", 0.0)
        performance = player.get("performance_rating", 0) if final and player.get("performance_rating") is not None else -1
        elo_initial = player.get("initial_elo", 0)
        return (1, -points, -bucch_c1, -bucch_tot, -performance, -elo_initial)

    try:
        # Usa la lista 'players' che potrebbe essere già ordinata da finalize_tournament
        # Ma riordiniamo qui per sicurezza e per le classifiche parziali
        players_sorted = sorted(players, key=sort_key)
    except Exception as e:
        print(f"Errore durante l'ordinamento dei giocatori per la classifica: {e}")
        # Importa traceback se non già fatto globalmente
        # import traceback
        traceback.print_exc()
        players_sorted = players # Usa lista non ordinata in caso di errore

    # Assegna rank solo se finale E se non già presente (fatto da finalize)
    # Se chiamato per classifica parziale, assegna rank temporaneo per la stampa
    if final and players_sorted and "final_rank" not in players_sorted[0]:
        # Assegna rank finale se finalize non l'ha fatto (non dovrebbe succedere)
        print("WARN save_standings_text: Assegno final_rank qui, ma dovrebbe essere fatto da finalize_tournament.") # DEBUG
        current_rank = 0
        last_sort_key_values = None
        for i, p in enumerate(players_sorted):
             if not p.get("withdrawn", False):
                 current_sort_key_values = sort_key(p)[1:]
                 if current_sort_key_values != last_sort_key_values:
                     current_rank = i + 1
                 p["final_rank"] = current_rank
                 last_sort_key_values = current_sort_key_values
             else:
                 p["final_rank"] = "RIT"

    # --- NOME FILE E SCRITTURA (Logica nome file e titolo invariata) ---
    tournament_name = torneo.get('name', 'Torneo_Senza_Nome')
    sanitized_name = sanitize_filename(tournament_name)
    filename = f"tornello - {sanitized_name} - Classifica.txt"
    status_line = ""
    if final:
        status_line = "CLASSIFICA FINALE"
    else:
        # ... (logica per titolo classifica parziale invariata) ...
        has_any_results = any(entry for p in players for entry in p.get("results_history", []) if entry.get("result") is not None and entry.get("result") != "BYE")
        current_round_in_state = torneo.get("current_round", 0)
        if not has_any_results and current_round_in_state == 1:
            round_num_for_title = 0
            status_line = f"Classifica Iniziale (Prima del Turno 1)"
        else:
            round_num_for_title = current_round_in_state
            status_line = f"Classifica Parziale - Dopo Turno {round_num_for_title}"

    try:
        with open(filename, "w", encoding='utf-8-sig') as f:
            f.write(f"Nome torneo: {torneo.get('name', 'N/D')}\n")
            f.write(status_line + "\n")
            header = "Pos. Nome Cognome         [EloIni] Punti  Bucch-1 Bucch  "
            if final:
                header += " ARO  Perf  +/-Elo"
            f.write(header + "\n")
            f.write("-" * len(header) + "\n")

            # --- SCRITTURA DATI GIOCATORI (Usa i valori già presenti in 'p') ---
            for i, player in enumerate(players_sorted):
                 # Determina il rank da visualizzare
                rank_to_display = player.get("final_rank") if final and player.get("final_rank") is not None else (i + 1)
                rank_str = str(rank_to_display)

                name_str = f"{player.get('first_name','?')} {player.get('last_name','')}"
                elo_str = f"[{player.get('initial_elo','?'):>4}]"
                pts_str = format_points(player.get('points', 0.0))
                bucch_tot_str = format_points(player.get('buchholz', 0.0)) # Buchholz sempre calcolato
                bucch_c1_val = player.get('buchholz_cut1') # Può essere None
                bucch_c1_str = format_points(bucch_c1_val) if bucch_c1_val is not None else "---"

                max_name_len = 21
                if len(name_str) > max_name_len: name_str = name_str[:max_name_len-1] + "."

                line = f"{rank_str:<4} {name_str:<{max_name_len}} {elo_str:<8} {pts_str:<6} {bucch_c1_str:<7} {bucch_tot_str:<7}"

                if final:
                    # Recupera i valori CALCOLATI DA FINALIZE_TOURNAMENT
                    aro_val = player.get('aro')
                    perf_val = player.get('performance_rating')
                    elo_change_val = player.get('elo_change') # <<< USA QUESTO

                    if player.get("withdrawn", False):
                        aro_str, perf_str, elo_change_str = "---", "---", "---"
                    else:
                        aro_str = str(aro_val) if aro_val is not None else "N/A"
                        perf_str = str(perf_val) if perf_val is not None else "N/A"
                        elo_change_str = f"{elo_change_val:+}" if elo_change_val is not None else "N/A" # Format con segno +/-

                    line += f" {aro_str:<4} {perf_str:<6} {elo_change_str:<6}"
                f.write(line + "\n")

        print(f"File classifica {filename} salvato/sovrascritto.")
    # ... (except blocks invariati) ...
    except IOError as e:
        print(f"Errore durante il salvataggio del file classifica {filename}: {e}")
    except Exception as general_e:
        print(f"Errore inatteso durante save_standings_text: {general_e}")
        # import traceback # Assicurati sia importato globalmente
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
    # Mostra date turno corrente
    round_dates_list = torneo.get("round_dates", [])
    current_round_dates = next((rd for rd in round_dates_list if rd.get("round") == current_r), None)
    if current_round_dates:
        r_start_str = current_round_dates.get('start_date')
        r_end_str = current_round_dates.get('end_date')
        print(f"Periodo Turno {current_r}: {format_date_locale(r_start_str)} - {format_date_locale(r_end_str)}")
        try:
            # Calcola giorni rimanenti per il turno
            round_end_dt = datetime.strptime(r_end_str, DATE_FORMAT_ISO).replace(hour=23, minute=59, second=59)
            time_left_round = round_end_dt - now
            if time_left_round.total_seconds() < 0:
                print(f"  -> Termine turno superato da {abs(time_left_round.days)} giorni.")
            else:
                days_left_round = time_left_round.days
                if days_left_round == 0 and time_left_round.total_seconds() > 0:
                    # Indentazione corretta
                    print(f"  -> Ultimo giorno per completare il turno.")
                elif days_left_round > 0:
                    # Indentazione corretta
                    print(f"  -> Giorni rimanenti per il turno: {days_left_round}")
        except (ValueError, TypeError):
            # Indentazione corretta
            # Ignora errore se le date non sono valide
            pass
    # Mostra giorni rimanenti alla fine del torneo
    try:
        tournament_end_dt = datetime.strptime(end_d_str, DATE_FORMAT_ISO).replace(hour=23, minute=59, second=59)
        time_left_tournament = tournament_end_dt - now
        if time_left_tournament.total_seconds() < 0:
            print(f"Termine torneo superato.")
        else:
            days_left_tournament = time_left_tournament.days
            if days_left_tournament == 0 and time_left_tournament.total_seconds() > 0:
                # Indentazione corretta
                print(f"Ultimo giorno del torneo.")
            elif days_left_tournament > 0:
                # Indentazione corretta
                print(f"Giorni rimanenti alla fine del torneo: {days_left_tournament}")
    except (ValueError, TypeError):
        # Indentazione corretta
        print(f"Data fine torneo ('{format_date_locale(end_d_str)}') non valida per calcolo giorni rimanenti.")
    # Conta partite pendenti nel turno corrente
    pending_match_count = 0
    found_current_round_data = False
    for r in torneo.get("rounds", []):
        if r.get("round") == current_r:
            found_current_round_data = True
            if "matches" in r:
                for m in r["matches"]:
                    # Pendente se non ha risultato e non è un BYE
                    if m.get("result") is None and m.get("black_player_id") is not None:
                        # Indentazione corretta
                        pending_match_count += 1
            break # Trovato il round corrente, esci dal loop
    if found_current_round_data:
        if pending_match_count > 0:
            print(f"\nPartite da giocare/registrare per il Turno {current_r}: {pending_match_count}")
            # La lista dettagliata verrà mostrata da update_match_result
        else:
            # Indentazione corretta
            # Se il turno corrente è valido e non ci sono partite pendenti
            if current_r is not None and total_r is not None and current_r <= total_r:
               print(f"\nTutte le partite del Turno {current_r} sono state registrate.")
    # Caso: il torneo è finito (turno corrente > totale)
    elif current_r is not None and total_r is not None and current_r > total_r:
        # Indentazione corretta
        print("\nIl torneo è concluso.")
    else: # Caso: dati del turno corrente non trovati (potrebbe essere un errore)
        # Indentazione corretta
        print(f"\nDati per il Turno {current_r} non trovati o turno non valido.")
    print("--------------------\n")

def finalize_tournament(torneo, players_db):
    """Completa il torneo, calcola Elo/Performance/Spareggi, aggiorna DB giocatori."""
    print("\n--- Finalizzazione Torneo ---")
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players', [])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    players_dict = torneo['players_dict']
    num_players = len(torneo.get('players', []))
    if num_players == 0:
        print("Nessun giocatore nel torneo, impossibile finalizzare.")
        return False

    tournament_start_date = torneo.get('start_date') # Necessario per get_k_factor

    # --- Fase 1: Determina K-Factor e conta partite giocate nel torneo ---
    print("Determinazione K-Factor e conteggio partite giocate...")
    for p in torneo.get('players',[]):
        player_id = p.get('id')
        if not player_id or p.get("withdrawn", False):
             p['k_factor'] = None # K non applicabile a ritirati
             p['games_this_tournament'] = 0
             continue

        # Recupera dati dal DB principale (Elo/partite PRIMA del torneo)
        player_db_data = players_db.get(player_id)
        if not player_db_data:
            print(f"WARN finalize: Dati DB non trovati per {player_id}, K-Factor userà default.")
            p['k_factor'] = DEFAULT_K_FACTOR
        else:
            # Calcola e memorizza il K-Factor per questo giocatore nel torneo
            p['k_factor'] = get_k_factor(player_db_data, tournament_start_date)
            print(f"DEBUG finalize: K-Factor per {player_id}: {p['k_factor']}") # DEBUG

        # Conta partite giocate in questo torneo (valide per Elo)
        games_count = 0
        for result_entry in p.get("results_history", []):
            opponent_id = result_entry.get("opponent_id")
            score = result_entry.get("score")
            # Conta solo partite reali con punteggio valido (esclude BYE, esclude 0-0F se gestito)
            if opponent_id and opponent_id != "BYE_PLAYER_ID" and score is not None:
                # Aggiungere qui check per result != "0-0F" se necessario
                games_count += 1
        p['games_this_tournament'] = games_count
        print(f"DEBUG finalize: Partite giocate da {player_id} nel torneo: {games_count}") # DEBUG


    # --- Fase 2: Calcola Spareggi, Performance, Elo Change (usando K specifico) ---
    print("Ricalcolo finale Buchholz, ARO, Performance Rating, Variazione Elo...")
    # Il K-Factor ora è dentro p['k_factor'] per ogni giocatore
    for p in torneo.get('players',[]):
        p_id = p.get('id')
        if not p_id or p.get("withdrawn", False):
             # Dati nulli/default per ritirati
             p["buchholz"] = 0.0
             p["buchholz_cut1"] = None
             p["aro"] = None
             p["performance_rating"] = None
             p["elo_change"] = None
             p["final_rank"] = "RIT"
             continue # Passa al prossimo giocatore

        # Calcola spareggi e performance
        p["buchholz"] = compute_buchholz(p_id, torneo)
        p["buchholz_cut1"] = compute_buchholz_cut1(p_id, torneo)
        p["aro"] = compute_aro(p_id, torneo)
        p["performance_rating"] = calculate_performance_rating(p, players_dict)

        # Calcola variazione Elo (la funzione ora usa p['k_factor'] internamente)
        p["elo_change"] = calculate_elo_change(p, players_dict)


    # --- Fase 3: Ordinamento Finale e Assegnazione Rank ---
    print("Ordinamento classifica finale...")
    # La funzione sort_key rimane invariata (usa i campi calcolati sopra)
    def sort_key_final(player):
         # ... (logica sort_key invariata) ...
        if player.get("withdrawn", False):
            return (0, -float('inf'), -float('inf'), -float('inf'), -float('inf'))
        points = player.get("points", 0.0)
        bucch_c1 = player.get("buchholz_cut1", 0.0) if player.get("buchholz_cut1") is not None else 0.0
        bucch_tot = player.get("buchholz", 0.0)
        performance = player.get("performance_rating", 0) if player.get("performance_rating") is not None else -1
        elo_initial = player.get("initial_elo", 0)
        return (1, -points, -bucch_c1, -bucch_tot, -performance, -elo_initial)

    try:
        players_sorted = sorted(torneo.get('players',[]), key=sort_key_final)
        current_rank = 0
        last_sort_key_values = None
        for i, p in enumerate(players_sorted):
            if not p.get("withdrawn", False):
                # ... (assegnazione rank invariata) ...
                current_sort_key_values = sort_key_final(p)[1:]
                if current_sort_key_values != last_sort_key_values:
                    current_rank = i + 1
                p["final_rank"] = current_rank
                last_sort_key_values = current_sort_key_values
            # else: rank RIT già assegnato
        torneo['players'] = players_sorted # Aggiorna lista nel torneo con rank e dati finali
    except Exception as e:
        print(f"Errore durante ordinamento finale: {e}")
        traceback.print_exc()

    # --- Fase 4: Salva Classifica Finale TXT ---
    save_standings_text(torneo, final=True) # Ora conterrà +/- Elo corretto per K

    # --- Fase 5: Aggiornamento Database Giocatori (Elo e Partite Giocate) ---
    print("Aggiornamento Database Giocatori (Elo e Partite Giocate)...")
    db_updated = False
    for p_final in torneo.get('players',[]): # Usa la lista ordinata e con dati finali
        player_id = p_final.get('id')
        final_rank = p_final.get('final_rank')
        elo_change = p_final.get('elo_change') # Variazione calcolata con K corretto
        games_in_tournament = p_final.get('games_this_tournament', 0) # Partite giocate nel torneo
        if not player_id: continue
        if player_id in players_db:
            db_player = players_db[player_id] # Accedi al record del DB
            # Aggiorna Elo
            if elo_change is not None:
                old_elo_db = db_player.get('current_elo', 'N/D')
                try:
                    current_db_elo_val = int(db_player.get('current_elo', DEFAULT_ELO))
                except (ValueError, TypeError):
                    print(f"Warning: Elo DB ('{old_elo_db}') non numerico per {player_id}. Reset a {DEFAULT_ELO}.")
                    current_db_elo_val = DEFAULT_ELO
                new_elo = current_db_elo_val + elo_change
                db_player['current_elo'] = new_elo # Aggiorna Elo nel DB
                print(f" - ID {player_id}: Elo DB aggiornato da {old_elo_db} a {new_elo} ({elo_change:+})")
            else:
                 # Questo accade per i ritirati o se il calcolo fallisce
                 print(f" - ID {player_id}: Variazione Elo non applicabile, Elo DB non aggiornato.")
            # Aggiorna Partite Giocate
            old_games_played = db_player.get('games_played', 0)
            new_games_played = old_games_played + games_in_tournament
            db_player['games_played'] = new_games_played
            print(f" - ID {player_id}: Partite DB aggiornate da {old_games_played} a {new_games_played} (+{games_in_tournament})")
            tournament_record = {
                 "tournament_name": torneo.get('name', 'N/D'),
                 "tournament_id": torneo.get('tournament_id', torneo.get('name', 'N/D')),
                 "rank": final_rank if final_rank is not None else 'N/A',
                 "total_players": num_players,
                 "date_started": torneo.get('start_date'), # <<<=== NUOVA RIGA AGGIUNTA
                 "date_completed": torneo.get('end_date', datetime.now().strftime(DATE_FORMAT_ISO))
             }
            if 'tournaments_played' not in db_player: db_player['tournaments_played'] = []
            if not any(t.get('tournament_id') == tournament_record['tournament_id'] for t in db_player['tournaments_played']):
                 db_player['tournaments_played'].append(tournament_record)
                 print(f" - ID {player_id}: Torneo '{tournament_record['tournament_name']}' aggiunto allo storico DB.")
                 if isinstance(final_rank, int) and final_rank in [1, 2, 3, 4]:
                    # Assicura che il dizionario medals esista e abbia tutte le chiavi
                    if 'medals' not in db_player:
                        db_player['medals'] = {'gold': 0, 'silver': 0, 'bronze': 0, 'wood': 0}
                    else:
                        # Assicura comunque la presenza di tutte le chiavi per sicurezza
                        db_player['medals'].setdefault('gold', 0)
                        db_player['medals'].setdefault('silver', 0)
                        db_player['medals'].setdefault('bronze', 0)
                        db_player['medals'].setdefault('wood', 0) # Assicura wood

                    medal_key = None
                    if final_rank == 1: medal_key = 'gold'
                    elif final_rank == 2: medal_key = 'silver'
                    elif final_rank == 3: medal_key = 'bronze'
                    elif final_rank == 4: medal_key = 'wood' # <-- Gestisce 4° posto

                    # Incrementa usando .get() per sicurezza
                    if medal_key:
                        db_player['medals'][medal_key] = db_player['medals'].get(medal_key, 0) + 1
                        print(f" - ID {player_id}: Medagliere DB aggiornato (+1 {medal_key}).")
            db_updated = True
        else:
            print(f"Attenzione: Giocatore ID {player_id} non trovato nel DB principale.")

    # Salva DB se aggiornato
    if db_updated:
        save_players_db(players_db) # Salva il file JSON e TXT del DB
        print("Database Giocatori aggiornato e salvato.")
    else:
        print("Nessun aggiornamento effettuato sul Database Giocatori.")

    # --- Fase 6: Archivia File Torneo (logica invariata) ---
    # ... (codice archiviazione come prima) ...
    tournament_name = torneo.get('name', 'Torneo_Senza_Nome')
    sanitized_name = sanitize_filename(tournament_name)
    timestamp_archive = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_name = f"tornello - {sanitized_name} - concluso_{timestamp_archive}.json"
    try:
        if os.path.exists(TOURNAMENT_FILE):
            os.rename(TOURNAMENT_FILE, archive_name)
            print(f"File torneo '{TOURNAMENT_FILE}' archiviato come '{archive_name}'")
        else:
            print(f"File torneo '{TOURNAMENT_FILE}' non trovato, impossibile archiviare.")
    except OSError as e:
        print(f"Errore durante l'archiviazione del file del torneo: {e}")
        return False
    return True

def main():
    players_db = load_players_db()
    torneo = load_tournament()
    launch_count = 1 # Default per nuovo torneo
    if torneo:
        # Incrementa contatore all'avvio se torneo esiste
        torneo['launch_count'] = torneo.get('launch_count', 0) + 1
        launch_count = torneo['launch_count']
        # Ricostruisci il dizionario cache all'avvio
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    print(f"\nBenvenuti da Tornello {VERSIONE} - {launch_count}o lancio.\n\tGabriele Battaglia and Gemini 2.5 Pro.") # Rimosso 2.5
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
        # Crea un ID torneo più robusto
        t_id_base = sanitize_filename(torneo['name'])[:20] # Usa nome sanificato
        torneo["tournament_id"] = f"{t_id_base}_{datetime.now().strftime('%Y%m%d%H%M%S')}" # Aggiungi secondi per unicità
        while True: # Loop per input data inizio
            try:
                oggi_str_iso = datetime.now().strftime(DATE_FORMAT_ISO)
                oggi_str_locale = format_date_locale(oggi_str_iso)
                start_date_str = input(f"Inserisci data inizio (YYYY-MM-DD) [Default: {oggi_str_locale}]: ").strip()
                if not start_date_str:
                    start_date_str = oggi_str_iso
                # Valida formato data
                start_dt = datetime.strptime(start_date_str, DATE_FORMAT_ISO)
                torneo["start_date"] = start_date_str
                break # Esce dal loop data inizio
            except ValueError:
                # Indentazione corretta
                print("Formato data non valido. Usa YYYY-MM-DD. Riprova.")
        while True:
            try:
                # Ottieni la data di inizio già inserita
                start_date_dt = datetime.strptime(torneo["start_date"], DATE_FORMAT_ISO)
                # --- NUOVA LOGICA DEFAULT +60 GIORNI ---
                # Calcola la data 60 giorni dopo l'inizio
                future_date_dt = start_date_dt + timedelta(days=60)
                # Formatta la data futura per il default e per il prompt
                default_end_date_iso = future_date_dt.strftime(DATE_FORMAT_ISO)
                default_end_date_locale = format_date_locale(future_date_dt) # Usa la nostra funzione per il formato leggibile
                # --- FINE NUOVA LOGICA DEFAULT ---

                # Chiedi input usando la nuova data di default nel prompt
                end_date_str = input(f"Inserisci data fine (YYYY-MM-DD) [Default: {default_end_date_locale}]: ").strip()
                # Se l'utente non inserisce nulla, usa la data calcolata (+60gg)
                if not end_date_str:
                    end_date_str = default_end_date_iso # Usa la data futura come default

                # Valida formato e ordine date (come prima)
                end_dt = datetime.strptime(end_date_str, DATE_FORMAT_ISO)
                if end_dt < start_date_dt:
                    print("Errore: La data di fine non può essere precedente alla data di inizio.")
                    continue # Richiedi data fine

                # Se tutto ok, salva ed esci dal loop
                torneo["end_date"] = end_date_str
                break
            except ValueError:
                print("Formato data non valido. Usa YYYY-MM-DD. Riprova.")
            except OverflowError:
                 print("Errore: La data calcolata (+60 giorni) risulta troppo lontana nel futuro.")
                 # In questo caso (molto raro), potremmo tornare al default precedente o chiedere di nuovo
                 # Per semplicità ora stampiamo solo l'errore e continuiamo a chiedere
                 continue
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
        # Calcola date turni
        round_dates = calculate_dates(torneo["start_date"], torneo["end_date"], torneo["total_rounds"])
        if round_dates is None:
            # Indentazione corretta
            print("Errore fatale nel calcolo delle date dei turni. Impossibile creare il torneo.")
            sys.exit(1)
        torneo["round_dates"] = round_dates
        # Input giocatori
        torneo["players"] = input_players(players_db)
        if not torneo["players"] or len(torneo["players"]) < 2:
            print("Numero insufficiente di giocatori validi inseriti. Torneo annullato.")
            sys.exit(0)
        # Inizializza stato torneo
        torneo["current_round"] = 1
        torneo["rounds"] = [] # Lista per contenere i dati di ogni turno (partite)
        torneo["next_match_id"] = 1
        torneo["k_factor"] = DEFAULT_K_FACTOR # Usa K default
        # Crea il dizionario cache iniziale
        torneo['players_dict'] = {p['id']: p for p in torneo['players']}
        print("\nGenerazione abbinamenti per il Turno 1...")
        matches_r1 = generate_pairings_for_round(torneo)

        # --- CONTROLLO ERRORE E RIGA APPEND MANCANTE REINSERITA ---
        if matches_r1 is None:
            # La nuova funzione restituisce None in caso di fallimento critico
            print("ERRORE CRITICO: Fallimento generazione accoppiamenti per il Turno 1.")
            print("Controllare i dati dei giocatori e le regole FIDE implementate. Torneo non avviato.")
            sys.exit(1)

        # Aggiungi il primo turno alla lista dei turni
        round_entry = {"round": 1, "matches": matches_r1}
        try:
            # Assicurati che torneo['rounds'] sia una lista (dovrebbe esserlo, ma è una sicurezza)
            if not isinstance(torneo.get('rounds'), list):
                 print("DEBUG main: torneo['rounds'] non era una lista! Inizializzo.") # DEBUG
                 torneo['rounds'] = []
            torneo["rounds"].append(round_entry) # <<< RIGA REINSERITA

            # --- DEBUG SUGGERITO PRIMA (ora utile per conferma) ---
            print(f"DEBUG main: Appended round data. torneo['rounds'] ora contiene:") # DEBUG
            # Importa pprint all'inizio del file se non l'hai già fatto
            import pprint
            pprint.pprint(torneo.get('rounds', 'ERRORE: CHIAVE rounds MANCANTE O NON LISTA'))
            # --- FINE DEBUG AGGIUNTO ---

        except Exception as e_append:
             print(f"ERRORE durante l'append di round data: {e_append}") # DEBUG
             # Importa traceback all'inizio del file se non l'hai già fatto
             import traceback
             traceback.print_exc()
             sys.exit(1) # Esci se l'append fallisce
        # --- FINE SEZIONE REINSERITA/MODIFICATA ---


        # Salva stato iniziale torneo e file T1
        save_tournament(torneo) # Ora salva con il round 1 dentro
        save_current_tournament_round_file(torneo)
        save_standings_text(torneo, final=False) # Salva classifica iniziale T0
        print("\nTorneo creato e Turno 1 generato.")
    else:
        # Torneo esistente caricato
        print(f"Torneo '{torneo.get('name','N/D')}' in corso rilevato da {TOURNAMENT_FILE}.")
        # Assicura che i set e il dizionario siano ricreati/validi dopo il caricamento
        if 'players' not in torneo: torneo['players'] = []
        for p in torneo["players"]:
            p['opponents'] = set(p.get('opponents', [])) # Ricostruisci set
            # Assicura presenza campi colore per compatibilità
            p.setdefault('consecutive_white', 0)
            p.setdefault('consecutive_black', 0)
        if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players', [])):
            # Indentazione corretta
            torneo['players_dict'] = {p['id']: p for p in torneo['players']}
    # --- Main Loop ---
    try:
        while True: # Loop gestito da break interni
            current_round_num = torneo.get("current_round")
            total_rounds_num = torneo.get("total_rounds")
            # Condizione di uscita principale: torneo concluso
            if current_round_num is None or total_rounds_num is None or current_round_num > total_rounds_num:
                print("\nStato torneo indica conclusione o errore nel numero turno.")
                break # Esce dal main loop
            print(f"\n--- Gestione Turno {current_round_num} ---")
            display_status(torneo)
            # Trova i dati del turno corrente
            current_round_data = None
            round_index = -1
            for i, r in enumerate(torneo.get("rounds", [])):
                # Indentazione corretta
                if r.get("round") == current_round_num:
                    current_round_data = r
                    round_index = i
                    break
            if current_round_data is None:
                # Indentazione corretta
                print(f"ERRORE CRITICO: Dati per il turno corrente {current_round_num} non trovati nella struttura del torneo!")
                break # Interrompi esecuzione
            # Verifica se il turno corrente è completo
            round_completed = True
            if "matches" in current_round_data:
                # Indentazione corretta
                for m in current_round_data["matches"]:
                    if m.get("result") is None and m.get("black_player_id") is not None:
                        # Indentazione corretta
                        round_completed = False
                        break # Basta una partita pendente
            else:
                # Indentazione corretta
                print(f"Warning: Nessuna partita trovata per il turno {current_round_num}.")
                round_completed = False # Considera incompleto

            # --- Flusso: Registra Risultati o Avanza Turno ---
            if not round_completed:
                print("\nIl turno non è completo. Registrare i risultati mancanti.")
                action_made = update_match_result(torneo)
                if not action_made:
                    # Indentazione corretta
                    print("\nNessun risultato inserito o cancellato in questa sessione.")
                    print("Salvataggio dello stato attuale del torneo...")
                    save_tournament(torneo)
                    print("Rilanciare il programma per continuare la registrazione o avanzare turno.")
                    break # Esce dal main loop
                else:
                    # Indentazione corretta
                    # Azione fatta, il loop while(True) continuerà, rivalutando lo stato
                    continue
            else:
                # Il turno è completo
                print(f"\nTurno {current_round_num} completato.")
                append_completed_round_to_history_file(torneo, current_round_num) # Nuovo salvataggio per turni conclusi
                save_standings_text(torneo, final=False) # Salva classifica parziale dopo T N
                # Verifica se era l'ultimo turno
                if current_round_num == total_rounds_num:
                    print("\nUltimo turno completato. Avvio finalizzazione torneo...")
                    if finalize_tournament(torneo, players_db):
                        # Indentazione corretta
                        print("\n--- Torneo Concluso e Finalizzato Correttamente ---")
                        torneo = None # Resetta stato locale
                    else:
                        # Indentazione corretta
                        print("\n--- ERRORE durante la Finalizzazione del Torneo ---")
                        if torneo: save_tournament(torneo)
                    break # Esce dal main loop
                else:
                    # Prepara e genera il prossimo turno
                    next_round_num = current_round_num + 1
                    print(f"\nGenerazione abbinamenti per il Turno {next_round_num}...")
                    # Aggiorna il numero del turno PRIMA di chiamare pairing
                    torneo["current_round"] = next_round_num
                    try:
                        # Chiama la funzione di pairing
                        next_matches = generate_pairings_for_round(torneo)
                        if next_matches is None:
                            # Indentazione corretta
                            # Pairing fallito! Errore già stampato.
                            print(f"Impossibile generare il turno {next_round_num}. Il torneo non può proseguire.")
                            # Ripristina numero turno e salva
                            torneo["current_round"] = current_round_num
                            save_tournament(torneo)
                            break # Interrompi torneo
                        # Aggiungi il nuovo round alla lista 'rounds'
                        torneo["rounds"].append({"round": next_round_num, "matches": next_matches})
                        # Salva stato torneo e file del nuovo turno
                        save_tournament(torneo)
                        save_current_tournament_round_file(torneo)
                        print(f"Turno {next_round_num} generato e salvato.")
                        # Il loop while(True) continuerà con il nuovo turno
                    except Exception as e:
                        # Indentazione corretta
                        print(f"\nERRORE CRITICO durante la generazione del turno {next_round_num}: {e}")
                        print("Il torneo potrebbe essere in uno stato inconsistente.")
                        traceback.print_exc()
                        # Prova a salvare lo stato attuale
                        torneo["current_round"] = current_round_num # Ripristina per sicurezza
                        save_tournament(torneo)
                        break # Interrompi torneo
    except KeyboardInterrupt:
        # Indentazione corretta
        print("\nOperazione interrotta dall'utente.")
        if torneo: # Salva stato se un torneo era in corso
            print("Salvataggio dello stato attuale del torneo...")
            save_tournament(torneo)
            if torneo.get("current_round") is not None and torneo.get("total_rounds") is not None and torneo.get("current_round") <= torneo.get("total_rounds"):
                save_current_tournament_round_file(torneo) # Salva anche lo stato del turno corrente
            print("Stato salvato. Uscita.")
        sys.exit(0)
    except Exception as e: # Cattura altri errori imprevisti nel loop principale
        # Indentazione corretta
        print(f"\nERRORE CRITICO NON GESTITO nel flusso principale: {e}")
        print("Si consiglia di controllare i file JSON per eventuali corruzioni.")
        traceback.print_exc()
        if torneo: # Prova a salvare anche in caso di errore generico
            print("Tentativo di salvataggio dello stato attuale del torneo...")
            save_tournament(torneo)
            if torneo.get("current_round") is not None and torneo.get("total_rounds") is not None and torneo.get("current_round") <= torneo.get("total_rounds"):
                save_current_tournament_round_file(torneo) # Salva anche lo stato del turno corrente
            print("Stato (potenzialmente incompleto) salvato.")
        sys.exit(1)
    # Se il loop while termina normalmente o via break controllato
    print("\nProgramma Tornello terminato.")

if __name__ == "__main__":
    main()
