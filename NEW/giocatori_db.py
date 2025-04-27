# Data concepimento 27 aprile 2025 by Gemini 2.5
import os
import json
import sys
from datetime import datetime

# --- Constants ---
# Assicurati che questo corrisponda ESATTAMENTE al file usato dal programma principale
PLAYER_DB_FILE = "tornello - giocatori_db.json"
DATE_FORMAT_ISO = "%Y-%m-%d"
DEFAULT_ELO = 1399 # Elo predefinito se non specificato

# --- Database Giocatori Functions ---

def load_players_db():
    """Carica il database dei giocatori dal file JSON.
       Restituisce un dizionario {id: player_data}.
       Crea i campi di default se mancano durante il caricamento o la creazione.
    """
    players_dict = {}
    if os.path.exists(PLAYER_DB_FILE):
        try:
            with open(PLAYER_DB_FILE, "r", encoding='utf-8') as f:
                db_list = json.load(f)
                for p in db_list:
                    # Assicura che tutti i campi necessari esistano
                    p.setdefault('current_elo', DEFAULT_ELO)
                    p.setdefault('registration_date', None)
                    p.setdefault('birth_date', None)
                    p.setdefault('games_played', 0)
                    p.setdefault('medals', {'gold': 0, 'silver': 0, 'bronze': 0})
                    p.setdefault('tournaments_played', [])
                    # Aggiungi altri campi di default se necessario per coerenza futura
                    # p.setdefault('downfloat_count', 0) # Esempio

                    if 'id' in p:
                       players_dict[p['id']] = p
                    else:
                        print(f"Attenzione: Record senza ID trovato e ignorato: {p}")
            print(f"Database '{PLAYER_DB_FILE}' caricato.")
        except (json.JSONDecodeError, IOError) as e:
            print(f"Errore durante il caricamento del DB giocatori ({PLAYER_DB_FILE}): {e}")
            print("Verrà usato un DB vuoto in memoria.")
            players_dict = {} # Resetta in caso di errore
        except Exception as e_generic:
             print(f"Errore imprevisto durante il caricamento: {e_generic}")
             players_dict = {}
    else:
        print(f"File database '{PLAYER_DB_FILE}' non trovato. Verrà creato se si aggiungono giocatori.")
    return players_dict

def save_players_db(players_db_dict):
    """Salva il database dei giocatori (dal dizionario) nel file JSON."""
    try:
        # Converte il dizionario in una lista di giocatori prima di salvare
        players_list = list(players_db_dict.values())
        with open(PLAYER_DB_FILE, "w", encoding='utf-8') as f:
            json.dump(players_list, f, indent=4, ensure_ascii=False)
        # print("Database giocatori salvato.") # Messaggio opzionale per conferma
    except IOError as e:
        print(f"ERRORE durante il salvataggio del DB giocatori ({PLAYER_DB_FILE}): {e}")
    except Exception as e_generic:
        print(f"ERRORE imprevisto durante il salvataggio del DB: {e_generic}")

def generate_player_id(first_name, last_name, players_db_dict):
    """Genera un ID univoco per un nuovo giocatore (LLLFFNNN)."""
    norm_first = first_name.strip().title()
    norm_last = last_name.strip().title()

    last_part_cleaned = ''.join(norm_last.split())
    first_part_cleaned = ''.join(norm_first.split())

    last_initials = last_part_cleaned[:3].upper()
    first_initials = first_part_cleaned[:2].upper()

    # Assicura lunghezza minima (come nel codice originale)
    while len(last_initials) < 3: last_initials += 'X'
    while len(first_initials) < 2: first_initials += 'X'

    base_id = f"{last_initials}{first_initials}"
    count = 1
    new_id = f"{base_id}{count:03d}"
    max_attempts = 1000 # Limite per evitare loop infiniti
    current_attempt = 0

    # Cerca ID univoco controllando le chiavi del dizionario
    while new_id in players_db_dict and current_attempt < max_attempts:
        count += 1
        new_id = f"{base_id}{count:03d}"
        current_attempt += 1

    if new_id in players_db_dict:
        # Se ancora in collisione dopo max tentativi (molto improbabile)
        print(f"ATTENZIONE: Impossibile generare ID univoco standard per {norm_first} {norm_last} dopo {max_attempts} tentativi.")
        # Usa un fallback (diverso dall'originale per semplicità qui, ma potresti copiarlo)
        timestamp_fallback = datetime.now().strftime('%S%f') # Secondi e microsecondi
        new_id = f"{base_id}ERR{timestamp_fallback[-3:]}"
        if new_id in players_db_dict: # Estrema improbabilità
             print("ERRORE CRITICO: Collisione anche con ID di fallback!")
             return None # Segnala fallimento generazione ID
    return new_id

def find_player_by_name(first_name, last_name, players_db_dict):
    """Cerca un giocatore per nome e cognome (case-insensitive).
       Restituisce i dati del giocatore (dict) se trovato, altrimenti None.
    """
    search_first_lower = first_name.strip().lower()
    search_last_lower = last_name.strip().lower()
    for player_data in players_db_dict.values():
        db_first_lower = player_data.get('first_name', '').lower()
        db_last_lower = player_data.get('last_name', '').lower()
        if db_first_lower == search_first_lower and db_last_lower == search_last_lower:
            return player_data # Ritorna l'intero dizionario del giocatore
    return None # Non trovato

def display_player_details(player_data):
    """Mostra i dettagli di un giocatore in modo leggibile."""
    print("\n--- Scheda Giocatore ---")
    if not player_data or not isinstance(player_data, dict):
        print("Dati giocatore non validi.")
        return

    # Elenca tutti i campi noti per completezza
    fields = [
        'id', 'first_name', 'last_name', 'current_elo',
        'birth_date', 'registration_date', 'games_played',
        'medals', 'tournaments_played'
        # Aggiungi altri campi se necessario
    ]

    for field in fields:
        value = player_data.get(field)
        display_value = ""

        if value is None:
            display_value = "N/D"
        elif field == 'medals' and isinstance(value, dict):
            # Formattazione specifica per il medagliere
            display_value = f"Oro: {value.get('gold', 0)}, Argento: {value.get('silver', 0)}, Bronzo: {value.get('bronze', 0)}"
        elif field == 'tournaments_played' and isinstance(value, list):
             # Mostra solo il numero di tornei per brevità
            display_value = f"{len(value)} tornei registrati"
            # Potresti espandere per mostrare i nomi se vuoi
            # if value:
            #    display_value += " (" + ", ".join([t.get('tournament_name', '?') for t in value[:3]]) + ('...' if len(value) > 3 else '') + ")"
            # else:
            #    display_value = "Nessun torneo registrato"
        elif field in ['birth_date', 'registration_date']:
             # Mostra le date nel formato ISO o N/D
            display_value = value if value else "N/D"
        else:
            display_value = str(value) # Converte altri valori in stringa

        # Stampa il campo e il valore formattato
        print(f"{field.replace('_', ' ').title():<20}: {display_value}")

    print("------------------------")

# --- Main Loop ---
def main_loop(players_db):
    """Ciclo principale per l'interazione con l'utente."""
    while True:
        print("\n" + "="*40)
        print(f"Giocatori nel database: {len(players_db)}")
        print("Inserisci 'Nome Cognome [Elo]' per cercare/aggiungere.")
        user_input = input("Oppure lascia vuoto per uscire: ").strip()

        if not user_input:
            break # Esce dal ciclo principale

        # --- Parsing Input ---
        parts = user_input.split()
        first_name = ""
        last_name = ""
        elo = DEFAULT_ELO # Default
        valid_parse = False

        try:
            if len(parts) >= 2:
                # Prova a vedere se l'ultima parte è un Elo
                try:
                    elo = int(parts[-1])
                    name_parts = parts[:-1]
                    if len(name_parts) >= 2: # Almeno Nome e Cognome
                        last_name = name_parts[-1].title()
                        first_name = " ".join(name_parts[:-1]).title()
                        valid_parse = True
                    elif len(name_parts) == 1: # Forse solo Cognome?
                        last_name = name_parts[0].title()
                        first_name = last_name # Usa cognome come nome
                        print(f"Info: Interpretato come Cognome='{last_name}', Nome='{first_name}', Elo={elo}")
                        valid_parse = True
                except ValueError:
                    # Ultima parte non era Elo, assumi sia parte del cognome
                    last_name = parts[-1].title()
                    first_name = " ".join(parts[:-1]).title()
                    elo = DEFAULT_ELO # Usa default Elo
                    print(f"Info: Elo non specificato o non valido, usando {DEFAULT_ELO}.")
                    valid_parse = True
            elif len(parts) == 1:
                 print("Input non valido. Servono almeno Nome e Cognome.")
                 valid_parse = False # Richiede almeno due parti (nome, cognome)
            else: # len(parts) == 0 gestito all'inizio
                valid_parse = False

            if not valid_parse:
                continue # Richiedi input di nuovo

        except Exception as e:
            print(f"Errore durante l'analisi dell'input: {e}")
            continue # Richiedi input di nuovo

        # --- Cerca Giocatore ---
        existing_player_data = find_player_by_name(first_name, last_name, players_db)

        if existing_player_data:
            # --- Giocatore Trovato ---
            player_id = existing_player_data.get('id', 'ID_SCONOSCIUTO')
            print(f"\nGiocatore '{first_name} {last_name}' trovato nel database (ID: {player_id}).")
            display_player_details(existing_player_data)

            # Chiedi se cancellare
            confirm = input("Vuoi cancellare questo giocatore? (scrivi 'cancella' per confermare, altrimenti INVIO): ").strip()
            if confirm.lower() == 'cancella': # .lower() per essere più flessibili sulla conferma
                try:
                    # Rimuovi dal dizionario usando l'ID
                    del players_db[player_id]
                    print(f"Giocatore ID {player_id} cancellato.")
                    # Salva immediatamente le modifiche
                    save_players_db(players_db)
                except KeyError:
                     print(f"ERRORE: Impossibile cancellare giocatore ID {player_id} (non trovato nel dizionario - inconsistenza?).")
                except Exception as e_del:
                     print(f"ERRORE imprevisto durante la cancellazione: {e_del}")
            else:
                print("Cancellazione annullata.")
            # Il ciclo while continuerà chiedendo il prossimo input

        else:
            # --- Giocatore Non Trovato (Aggiunta) ---
            print(f"Giocatore '{first_name} {last_name}' non trovato. Procedo con l'aggiunta.")

            birth_date_str = None
            while True: # Loop per chiedere data nascita valida
                bdate_input = input("Inserisci data di nascita (AAAA-MM-GG) o lascia vuoto: ").strip()
                if not bdate_input:
                    birth_date_str = None
                    break
                else:
                    try:
                        # Valida il formato
                        datetime.strptime(bdate_input, DATE_FORMAT_ISO)
                        birth_date_str = bdate_input
                        break # Formato valido, esci dal loop data nascita
                    except ValueError:
                        print("Formato data non valido. Usa AAAA-MM-GG o lascia vuoto.")
                        # Continua a chiedere

            # Genera ID
            new_id = generate_player_id(first_name, last_name, players_db)

            if new_id is None:
                print("ERRORE CRITICO: Impossibile generare un ID univoco. Aggiunta annullata.")
                continue # Torna all'inizio del ciclo principale

            # Crea nuovo record giocatore
            new_player = {
                "id": new_id,
                "first_name": first_name,
                "last_name": last_name,
                "current_elo": elo, # Usa l'elo fornito o il default
                "registration_date": datetime.now().strftime(DATE_FORMAT_ISO),
                "birth_date": birth_date_str, # Può essere None
                "games_played": 0, # Inizializza i campi standard
                "medals": {"gold": 0, "silver": 0, "bronze": 0},
                "tournaments_played": []
                # Aggiungi altri campi di default se li hai nel DB principale
                # "downfloat_count": 0,
            }

            # Aggiungi al dizionario DB
            players_db[new_id] = new_player
            print(f"Nuovo giocatore '{first_name} {last_name}' aggiunto con ID {new_id}.")
            display_player_details(new_player) # Mostra la scheda appena creata

            # Salva immediatamente le modifiche
            save_players_db(players_db)
            # Il ciclo while continuerà

    print("\nSalvataggio finale del database...")
    save_players_db(players_db)
    print("Uscita dal gestore database giocatori.")


# --- Blocco di Esecuzione Principale ---
if __name__ == "__main__":
    print("--- Gestore Database Giocatori Tornello ---")
    db = load_players_db()
    main_loop(db)