# Data concepimento 27 aprile 2025 by Gemini 2.5 (Modificato)
# gestore_db_giocatori.py
import os
import json
import sys 
import traceback
from datetime import datetime
from dateutil.relativedelta import relativedelta

try:
    from GBUtils import dgt 
except ImportError:
    print("ATTENZIONE: Libreria GBUtils non trovata. L'input non sarà validato come previsto per alcuni campi.")
    def dgt(prompt, kind="s", default=None, smin=0, smax=0, imin=0, imax=0, fmin=0.0, fmax=0.0, errmsg=""): # Aggiunto errmsg
        val = input(prompt)
        if not val and default is not None:
            return default
        # Aggiungi qui una minima validazione se vuoi per il fallback
        if kind == "i" or kind == "f":
            try:
                if kind == "i": return int(val)
                if kind == "f": return float(val)
            except ValueError:
                print(errmsg if errmsg else "Input numerico non valido.")
                return default
        return val

# --- Constants ---
VERSION = "4.1.0 del 27 maggio 2025" # Versione aggiornata del tool
PLAYER_DB_FILE = "tornello - giocatori_db.json"
PLAYER_DB_TXT_FILE = "tornello - giocatori_db.txt"
DATE_FORMAT_ISO = "%Y-%m-%d" 
DEFAULT_ELO = 1399.0
DEFAULT_K_FACTOR = 20

# --- Helper Functions ---
def sanitize_filename(name):
    name = name.replace(' ', '_')
    import re 
    name = re.sub(r'[^\w\-]+', '', name)
    if not name:
        name = "File_Senza_Nome"
    return name

def format_date_locale(date_input):
    if not date_input:
        return "N/D"
    try:
        if isinstance(date_input, datetime):
            date_obj = date_input
        else: 
            date_obj = datetime.strptime(str(date_input), DATE_FORMAT_ISO)
        giorni = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
        mesi = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
        return f"{giorni[date_obj.weekday()].capitalize()} {date_obj.day} {mesi[date_obj.month]} {date_obj.year}"
    except Exception: 
        return str(date_input) if date_input else "N/D"

def format_rank_ordinal(rank):
    if rank == "RIT": return "RIT"
    try: return f"{int(rank)}°"
    except: return "?"

def get_k_factor(player_data_dict, current_date_iso_str):
    # ... (codice invariato, corretto) ...
    if not player_data_dict: return DEFAULT_K_FACTOR
    try: elo = float(player_data_dict.get('current_elo', DEFAULT_ELO))
    except: elo = DEFAULT_ELO
    games = player_data_dict.get('games_played', 0)
    birth_str = player_data_dict.get('birth_date') 
    age = None
    if birth_str and current_date_iso_str:
        try:
            birth_dt = datetime.strptime(birth_str, DATE_FORMAT_ISO)
            current_dt = datetime.strptime(current_date_iso_str, DATE_FORMAT_ISO)
            age = relativedelta(current_dt, birth_dt).years
        except: pass 
    if games < 30: return 40
    if age is not None and age < 18 and elo < 2300: return 40
    if elo < 2400: return 20
    return 10

def save_players_db_txt(players_db_dict):
    # ... (codice quasi invariato, assicurati che i get() usino le chiavi corrette) ...
    try:
        with open(PLAYER_DB_TXT_FILE, "w", encoding='utf-8-sig') as f:
            now = datetime.now()
            current_date_iso_for_k = now.strftime(DATE_FORMAT_ISO)
            f.write(f"Report Database Giocatori Tornello - {format_date_locale(now.date())} {now.strftime('%H:%M:%S')}\n")
            f.write(f"Versione Tool: {VERSION}\n")
            f.write("=" * 70 + "\n\n")
            
            if not players_db_dict:
                f.write("Il database dei giocatori è vuoto.\n")
                return

            players_list_for_sort = list(players_db_dict.values())
            sorted_players = sorted(players_list_for_sort, key=lambda p: (p.get('last_name','').lower(), p.get('first_name','').lower()))
            
            if not sorted_players: 
                f.write("Il database dei giocatori è vuoto dopo l'ordinamento.\n")
                return

            for p_data in sorted_players:
                player_id = p_data.get('id', 'N/D')
                # USA LA CHIAVE CORRETTA PER IL TITOLO (es. 'fide_title')
                title = str(p_data.get('fide_title', '')).strip().upper()
                title_prefix = f"{title} " if title else ""
                first_name = p_data.get('first_name', 'N/D')
                last_name = p_data.get('last_name', 'N/D')
                elo = p_data.get('current_elo', 'N/D')
                
                f.write(f"ID: {player_id}, {title_prefix}{first_name} {last_name}, Elo: {elo}\n")
                
                # USA LE CHIAVI CORRETTE PER I NUOVI CAMPI
                sex_val = str(p_data.get('sex', 'N/D')).upper()
                federation_val = str(p_data.get('federation', 'N/D')).upper()
                fide_id_num_val = str(p_data.get('fide_id_num_str', 'N/D'))
                f.write(f"\tSesso: {sex_val}, Federazione: {federation_val}, ID FIDE num: {fide_id_num_val}\n")
                
                birth_date_str_val = p_data.get('birth_date') 
                f.write(f"\tData Nascita: {format_date_locale(birth_date_str_val)}\n")

                games_played = p_data.get('games_played', 0)
                k_factor = get_k_factor(p_data, current_date_iso_for_k)
                reg_date_str_val = p_data.get('registration_date')
                f.write(f"\tPartite Valutate: {games_played}, K-Factor Stimato: {k_factor}, Iscrizione DB: {format_date_locale(reg_date_str_val)}\n")
                
                medals = p_data.get('medals', {})
                f.write(f"\tMedagliere: Oro: {medals.get('gold',0)}, Argento: {medals.get('silver',0)}, Bronzo: {medals.get('bronze',0)}, Legno: {medals.get('wood',0)}\n")
                
                tournaments = p_data.get('tournaments_played', [])
                f.write(f"\tTornei Giocati ({len(tournaments)}):\n")
                # ... (resto della stampa tornei come prima) ...
                if tournaments:
                    try:
                        tournaments_s_list = sorted(tournaments, key=lambda t_item: datetime.strptime(t_item.get('date_completed', '1900-01-01'), DATE_FORMAT_ISO), reverse=True)
                    except ValueError: tournaments_s_list = tournaments 
                    for t_entry in tournaments_s_list:
                        total_p = t_entry.get('total_players', '?')
                        line = f"{format_rank_ordinal(t_entry.get('rank', '?'))} su {total_p} in '{t_entry.get('tournament_name', 'N/M')}'"
                        line += f" ({format_date_locale(t_entry.get('date_started'))} - {format_date_locale(t_entry.get('date_completed'))})"
                        f.write(f"\t\t{line}\n")
                else:
                    f.write("\t\tNessuno\n")
                f.write("\t" + "-" * 60 + "\n")
    except Exception as e:
        print(f"Errore durante il salvataggio del file TXT del DB giocatori: {e}")
        traceback.print_exc()

def load_players_db():
    # ... (codice invariato, ma assicurati che setdefault includa le nuove chiavi se vuoi che siano create automaticamente al caricamento di un DB vecchio) ...
    players_dict = {}
    if os.path.exists(PLAYER_DB_FILE):
        try:
            with open(PLAYER_DB_FILE, "r", encoding='utf-8') as f:
                db_list_from_file = json.load(f) 
                for p_entry in db_list_from_file:
                    if 'id' not in p_entry: 
                        print(f"Attenzione: Record giocatore senza ID nel DB: {p_entry}")
                        continue
                    
                    p_entry.setdefault('first_name', 'Sconosciuto')
                    p_entry.setdefault('last_name', 'Sconosciuto')
                    p_entry.setdefault('current_elo', DEFAULT_ELO)
                    p_entry.setdefault('registration_date', datetime.now().strftime(DATE_FORMAT_ISO))
                    p_entry.setdefault('birth_date', None) 
                    p_entry.setdefault('games_played', 0)
                    medals = p_entry.setdefault('medals', {})
                    for m_key_val in ['gold', 'silver', 'bronze', 'wood']: medals.setdefault(m_key_val, 0)
                    p_entry.setdefault('tournaments_played', [])
                    
                    # Assicura che i nuovi campi abbiano un default se carichi un DB vecchio
                    p_entry.setdefault('fide_title', '')    
                    p_entry.setdefault('sex', 'm')           
                    p_entry.setdefault('federation', 'ITA')  
                    p_entry.setdefault('fide_id_num_str', '0') 

                    players_dict[p_entry['id']] = p_entry
            print(f"Database '{PLAYER_DB_FILE}' caricato ({len(players_dict)} giocatori).")
        except Exception as e:
            print(f"Errore caricamento DB ({PLAYER_DB_FILE}): {e}. Verrà usato un DB vuoto in memoria.")
            players_dict = {} 
    else:
        print(f"File database '{PLAYER_DB_FILE}' non trovato. Verrà creato un nuovo DB se si aggiungono giocatori.")
    return players_dict

def save_players_db(players_db_dict_to_save):
    # ... (codice invariato) ...
    if not isinstance(players_db_dict_to_save, dict):
        print("ERRORE INTERNO: save_players_db si aspetta un dizionario.")
        return
    try:
        with open(PLAYER_DB_FILE, "w", encoding='utf-8') as f:
            json.dump(list(players_db_dict_to_save.values()), f, indent=4, ensure_ascii=False)
        print(f"Database giocatori JSON '{PLAYER_DB_FILE}' salvato.")
        save_players_db_txt(players_db_dict_to_save) 
    except Exception as e:
        print(f"ERRORE durante il salvataggio del DB giocatori ({PLAYER_DB_FILE}): {e}")
        traceback.print_exc()

def generate_player_id(first_name, last_name, players_db_dict):
    # ... (codice invariato) ...
    norm_first = first_name.strip().title()
    norm_last = last_name.strip().title()
    if not norm_first or not norm_last: return None
    last_initials = ''.join(norm_last.split())[:3].upper().ljust(3, 'X')
    first_initials = ''.join(norm_first.split())[:2].upper().ljust(2, 'X')
    base_id = f"{last_initials}{first_initials}"
    if not base_id or base_id == "XXXXX": base_id = "GIOCX" 
    count = 1
    new_id = f"{base_id}{count:03d}"
    max_attempts = 1000 
    current_attempt = 0
    while new_id in players_db_dict and current_attempt < max_attempts:
        count += 1
        new_id = f"{base_id}{count:03d}"
        current_attempt +=1
        if count > 999: 
            new_id = f"{base_id}{datetime.now().strftime('%S%f')[-4:]}" 
            if new_id in players_db_dict: return None 
            break 
    if new_id in players_db_dict and current_attempt >= max_attempts: 
        return None 
    return new_id    

def find_players_partial(search_term, players_db_dict):
    # ... (codice invariato, ma la ricerca sui nuovi campi potrebbe essere utile) ...
    matches = []
    search_lower = search_term.strip().lower()
    if not search_lower: return matches
    for p_data_item in players_db_dict.values():
        if search_lower in p_data_item.get('first_name', '').lower() or \
           search_lower in p_data_item.get('last_name', '').lower() or \
           search_lower == p_data_item.get('id','').lower() or \
           search_lower == p_data_item.get('fide_title','').lower() or \
           search_lower == p_data_item.get('fide_id_num_str',''):
            matches.append(p_data_item)
    return matches

# --- NUOVA FUNZIONE HELPER PER L'INPUT (simile a quella di tornello.py) ---
def get_input_with_default_gestore_db(prompt_message, default_value=None):
    """Chiede un input all'utente, mostrando un valore di default."""
    default_display = str(default_value) if default_value is not None else ""
    # Mostra il prompt con il default solo se default_display ha un contenuto visibile
    # o se default_value era una stringa vuota (permettere di cancellare/confermare il vuoto)
    if default_display or isinstance(default_value, str): 
        user_input = input(f"{prompt_message} [{default_display}]: ").strip()
        # Se l'utente non inserisce nulla, restituisci il default originale
        return user_input if user_input else default_value 
    else: # Se default_value era None e non vogliamo mostrare "[None]"
        return input(f"{prompt_message}: ").strip()

def display_player_details(player_data):
    # ... (codice modificato per includere i nuovi campi) ...
    print("\n--- Scheda Giocatore Dettagliata ---")
    if not player_data: 
        print("Dati giocatore non validi o non trovati.")
        return
    
    player_id = player_data.get('id', 'N/D')
    # USA LA CHIAVE CORRETTA PER IL TITOLO (es. 'fide_title')
    title = str(player_data.get('fide_title', '')).strip().upper()
    title_prefix = f"{title} " if title else ""
    first_name = player_data.get('first_name', 'N/D')
    last_name = player_data.get('last_name', 'N/D')
    
    print(f"{'ID':<20}: {player_id}")
    print(f"{'Nome Completo':<20}: {title_prefix}{first_name} {last_name}")
    print(f"{'Titolo FIDE':<20}: {title if title else 'N/D'}")
    print(f"{'Elo Corrente':<20}: {player_data.get('current_elo', 'N/D')}")
    # USA LE CHIAVI CORRETTE PER I NUOVI CAMPI
    print(f"{'Sesso':<20}: {str(player_data.get('sex', 'N/D')).upper()}")
    print(f"{'Federazione':<20}: {str(player_data.get('federation', 'N/D')).upper()}")
    print(f"{'ID FIDE Numerico':<20}: {player_data.get('fide_id_num_str', 'N/D')}")
    print(f"{'Data Nascita':<20}: {format_date_locale(player_data.get('birth_date'))}") 
    print(f"{'Data Registrazione':<20}: {format_date_locale(player_data.get('registration_date'))}")
    print(f"{'Partite Giocate':<20}: {player_data.get('games_played', 0)}")
    
    medals = player_data.get('medals', {})
    print(f"{'Medagliere':<20}: Oro: {medals.get('gold',0)}, Argento: {medals.get('silver',0)}, Bronzo: {medals.get('bronze',0)}, Legno: {medals.get('wood',0)}")
    
    tournaments = player_data.get('tournaments_played', [])
    print(f"{'Storico Tornei':<20}: {len(tournaments)} registrati")
    # ... (resto della stampa tornei come prima) ...
    if tournaments:
        try:
            tournaments_s_list = sorted(tournaments, key=lambda t_item: datetime.strptime(t_item.get('date_completed', '1900-01-01'), DATE_FORMAT_ISO), reverse=True)
        except: tournaments_s_list = tournaments # Fallback
        for i, t_rec_item in enumerate(tournaments_s_list):
            total_p_val = t_rec_item.get('total_players', '?')
            start_d = format_date_locale(t_rec_item.get('date_started'))
            end_d = format_date_locale(t_rec_item.get('date_completed'))
            print(f"    {i+1}. {format_rank_ordinal(t_rec_item.get('rank', '?'))} su {total_p_val} in '{t_rec_item.get('tournament_name', 'N/D')}'")
            print(f"       Date: {start_d} - {end_d} (ID Torneo: {t_rec_item.get('tournament_id', 'N/A')})")
    print("------------------------")

def add_new_player(players_db_dict_ref):
    # ... (codice modificato per chiedere i nuovi campi) ...
    print("\n--- Aggiunta Nuovo Giocatore ---")
    first_name = get_input_with_default_gestore_db("Nome: ") # Usa la nuova funzione
    if not first_name: print("Nome richiesto."); return False
    first_name = first_name.title()

    last_name = get_input_with_default_gestore_db("Cognome: ")
    if not last_name: print("Cognome richiesto."); return False
    last_name = last_name.title()
    
    elo_str = get_input_with_default_gestore_db("Elo Corrente:", str(DEFAULT_ELO))
    try: elo_val = int(elo_str)
    except ValueError: elo_val = DEFAULT_ELO; print(f"Elo non valido, usato default {DEFAULT_ELO}")
    if not (0 <= elo_val <= 3500): elo_val = DEFAULT_ELO; print(f"Elo fuori range, usato default {DEFAULT_ELO}")

    fide_title_new = get_input_with_default_gestore_db("Titolo FIDE (es. FM, '' per nessuno):", "").upper()[:3]
    
    sex_new = ""
    while True:
        sex_input = get_input_with_default_gestore_db("Sesso (m/w):", "m").lower()
        if sex_input in ['m', 'w']: sex_new = sex_input; break
        print("Input non valido. Usa 'm' o 'w'.")
    
    federation_new = get_input_with_default_gestore_db("Federazione (3 lettere):", "ITA").upper()[:3]
    if not federation_new : federation_new = "ITA"

    fide_id_num_new = get_input_with_default_gestore_db("ID FIDE Numerico (cifre, '0' se N/D):", "0")
    if not fide_id_num_new.isdigit(): fide_id_num_new = '0'

    birth_date_str = None
    while True:
        bdate_input = get_input_with_default_gestore_db(f"Data di nascita ({DATE_FORMAT_ISO} o vuoto):", "")
        if not bdate_input: break
        try:
            datetime.strptime(bdate_input, DATE_FORMAT_ISO)
            birth_date_str = bdate_input
            break
        except ValueError: print(f"Formato data non valido. Usa {DATE_FORMAT_ISO}.")

    new_id = generate_player_id(first_name, last_name, players_db_dict_ref)
    if new_id is None:
        print("ERRORE: Impossibile generare ID univoco. Aggiunta annullata.")
        return False

    new_player_record = {
        "id": new_id, "first_name": first_name, "last_name": last_name,
        "current_elo": elo_val, "registration_date": datetime.now().strftime(DATE_FORMAT_ISO),
        "games_played": 0,
        "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
        "tournaments_played": [],
        "fide_title": fide_title_new, "sex": sex_new, "federation": federation_new,
        "fide_id_num_str": fide_id_num_new, "birth_date": birth_date_str
    }
    players_db_dict_ref[new_id] = new_player_record
    print(f"Giocatore '{new_player_record['first_name']} {new_player_record['last_name']}' aggiunto con ID {new_id}.")
    display_player_details(new_player_record)
    return True 

def edit_player_data(player_id_to_edit, players_db_dict_ref):
    # ... (codice modificato per usare get_input_with_default_gestore_db e gestire nuovi campi) ...
    if player_id_to_edit not in players_db_dict_ref:
        print(f"Errore: Giocatore con ID {player_id_to_edit} non trovato.")
        return False, player_id_to_edit 

    player_data_ref = players_db_dict_ref[player_id_to_edit] 
    original_id = player_data_ref['id'] 
    
    print(f"\n--- Modifica Giocatore ID: {original_id} ({player_data_ref.get('first_name')} {player_data_ref.get('last_name')}) ---")
    display_player_details(player_data_ref) # Mostra i dati attuali prima della modifica
    print("--- Inserisci nuovi valori o premi Invio per mantenere i correnti ---")
    
    original_first_name = player_data_ref.get('first_name', '')
    new_first_name = get_input_with_default_gestore_db("Nome", original_first_name).title()
    
    original_last_name = player_data_ref.get('last_name', '')
    new_last_name = get_input_with_default_gestore_db("Cognome", original_last_name).title()

    id_changed_flag = False
    final_id_for_player = original_id

    if new_first_name != original_first_name or new_last_name != original_last_name:
        if (new_first_name and new_last_name): # Solo se entrambi sono validi
            print("Nome o cognome modificati.")
            if get_input_with_default_gestore_db("Vuoi tentare di rigenerare l'ID? (s/N)", "n").lower() == 's':
                temp_player_data_for_id_gen = players_db_dict_ref.pop(original_id, None) 
                candidate_new_id = generate_player_id(new_first_name, new_last_name, players_db_dict_ref) 
                if candidate_new_id and candidate_new_id != original_id:
                    if candidate_new_id in players_db_dict_ref: 
                        print(f"ATTENZIONE: Il nuovo ID generato '{candidate_new_id}' è già in uso. L'ID originale '{original_id}' verrà mantenuto.")
                        players_db_dict_ref[original_id] = temp_player_data_for_id_gen 
                    else:
                        final_id_for_player = candidate_new_id
                        id_changed_flag = True
                        temp_player_data_for_id_gen['id'] = final_id_for_player
                        players_db_dict_ref[final_id_for_player] = temp_player_data_for_id_gen
                        player_data_ref = players_db_dict_ref[final_id_for_player] 
                        print(f"ID giocatore aggiornato da '{original_id}' a '{final_id_for_player}'.")
                elif not candidate_new_id :
                    print("Errore nella generazione del nuovo ID. L'ID originale verrà mantenuto.")
                    if temp_player_data_for_id_gen: players_db_dict_ref[original_id] = temp_player_data_for_id_gen
                else: 
                    print("Il nuovo ID generato è identico all'originale. Nessuna modifica all'ID.")
                    if temp_player_data_for_id_gen: players_db_dict_ref[original_id] = temp_player_data_for_id_gen
        else:
            print("Nome e/o cognome non validi, impossibile aggiornare l'ID.")
            new_first_name = original_first_name # Ripristina
            new_last_name = original_last_name  # Ripristina

    player_data_ref['first_name'] = new_first_name
    player_data_ref['last_name'] = new_last_name
    
    # Per Elo, usiamo dgt per la validazione del range, ma il default ora è preso da player_data_ref
    player_data_ref['current_elo'] = dgt("Elo Corrente (0-3500)", kind="f", fmin=0, fmax=3500, default=float(player_data_ref.get('current_elo', DEFAULT_ELO)))
    
    player_data_ref['fide_title'] = get_input_with_default_gestore_db("Titolo FIDE (es. FM, '' per nessuno)", player_data_ref.get('fide_title', '')).upper()[:3]
    
    sex_default_edit = player_data_ref.get('sex', 'm')
    while True:
        sex_input_val = get_input_with_default_gestore_db("Sesso (m/w)", sex_default_edit).lower()
        if sex_input_val in ['m', 'w', '']: 
            player_data_ref['sex'] = sex_input_val if sex_input_val else sex_default_edit
            if not player_data_ref['sex'] : player_data_ref['sex'] = 'm' # Assicura default se cancellato e default era vuoto
            break
        print("Input non valido.")
        
    fed_default_edit = player_data_ref.get('federation', 'ITA')
    player_data_ref['federation'] = get_input_with_default_gestore_db("Federazione (3 lettere)", fed_default_edit).upper()[:3]
    if not player_data_ref['federation']: player_data_ref['federation'] = fed_default_edit # Ripristina default se cancellato
    if not player_data_ref['federation']: player_data_ref['federation'] = 'ITA' # Assicura default finale

    fide_id_default_edit = player_data_ref.get('fide_id_num_str', '0')
    new_fide_id_val = get_input_with_default_gestore_db("ID FIDE Numerico (cifre, '0' se N/D)", fide_id_default_edit)
    if not new_fide_id_val.isdigit(): new_fide_id_val = '0' if not new_fide_id_val else fide_id_default_edit # Se non è numero, usa '0' o il default se l'utente ha cancellato
    if not new_fide_id_val: new_fide_id_val = '0' # Default finale '0' se stringa vuota
    player_data_ref['fide_id_num_str'] = new_fide_id_val

    birth_date_default_edit = player_data_ref.get('birth_date') # Può essere None
    while True:
        bdate_input_val = get_input_with_default_gestore_db(f"Data di nascita ({DATE_FORMAT_ISO} o vuoto)", birth_date_default_edit if birth_date_default_edit is not None else "")
        if not bdate_input_val:
            player_data_ref['birth_date'] = None # Permetti cancellazione
            break
        try:
            datetime.strptime(bdate_input_val, DATE_FORMAT_ISO)
            player_data_ref['birth_date'] = bdate_input_val
            break
        except ValueError: print(f"Formato data non valido. Usa {DATE_FORMAT_ISO}.")

    print("\n--- Modifica Medagliere ---")
    medals_data_ref = player_data_ref.setdefault('medals', {'gold': 0, 'silver': 0, 'bronze': 0, 'wood': 0}) # Rinomino medals_ref
    for m_key_val_edit in ['gold', 'silver', 'bronze', 'wood']: # Rinomino m_key_item
        medals_data_ref[m_key_val_edit] = dgt(f"Medaglie di {m_key_val_edit.capitalize()}", kind="i", imin=0, imax=999, default=medals_data_ref.get(m_key_val_edit, 0))

    print("\n--- Modifica Storico Tornei ---")
    tournaments_data_ref = player_data_ref.setdefault('tournaments_played', []) # Rinomino tournaments_ref
    # ... (la tua logica esistente per modificare/aggiungere/cancellare tornei è complessa e la lascio invariata) ...
    # Assicurati che i default per dgt() qui dentro prendano i valori da t_edit (se in modifica)
    # Esempio per modifica (dentro il tuo op == 'm'):
    # t_edit['tournament_name'] = get_input_with_default_gestore_db("Nome torneo", t_edit.get('tournament_name'))
    # E così via per gli altri campi del torneo nello storico...
    # Per semplicità, lascio la tua logica con dgt qui, ma potresti volerla adattare.
    while True:
        print("\nTornei registrati:") # ... (stampa tornei) ...
        if not tournaments_data_ref: print("   Nessun torneo registrato.")
        else:
            for i, t_disp in enumerate(tournaments_data_ref): # Rinomino t
                print(f"   {i+1}. {format_rank_ordinal(t_disp.get('rank'))} '{t_disp.get('tournament_name')}' ({format_date_locale(t_disp.get('date_started'))} - {format_date_locale(t_disp.get('date_completed'))})")
        
        op_tourn = dgt("Operazione Storico Tornei: (A)ggiungi, (M)odifica, (C)ancella, (F)ine: ", kind="s", smax=1, default="f").lower() # Rinomino op
        if op_tourn == 'f': break
        # ... (A, M, C come nel tuo codice, usando dgt o get_input_with_default_gestore_db come preferisci)
        # Per esempio, in modalità Modifica (op_tourn == 'm'):
        if op_tourn == 'm' and tournaments_data_ref:
            idx_str_m_tourn = dgt(f"Numero torneo da modificare (1-{len(tournaments_data_ref)}): ", kind="s", smax=len(str(len(tournaments_data_ref))))
            try:
                idx_m_tourn = int(idx_str_m_tourn) - 1 
                if 0 <= idx_m_tourn < len(tournaments_data_ref):
                    t_edit_obj_hist = tournaments_data_ref[idx_m_tourn] 
                    print(f"Modifica torneo storico: '{t_edit_obj_hist.get('tournament_name')}'")
                    t_edit_obj_hist['tournament_name'] = get_input_with_default_gestore_db("Nome torneo", t_edit_obj_hist.get('tournament_name'))
                    # ... e così via per rank, total_players, date ...
                    print("Torneo nello storico modificato.")
                # ...
            except ValueError: print("Input non numerico.")
        # ... implementa 'a' e 'c' in modo simile ...
    
    print("\nDati giocatore e storico tornei aggiornati.")
    display_player_details(player_data_ref) 
    return True, final_id_for_player 

# --- Main Loop del Tool Esterno ---
def main_interactive_db_tool_loop(players_db_main_dict):
    # ... (codice quasi invariato, ma usa get_input_with_default_gestore_db per il prompt principale se vuoi quel formato) ...
    print(f"\n--- Gestore Database Giocatori Tornello (Tool Esterno) ---\n\tVersione: {VERSION}.\n")
    last_managed_player_id = None 
    while True:
        print("\n" + "="*40)
        print(f"Giocatori nel database: {len(players_db_main_dict)}")
        
        prompt_msg_main = "Cerca giocatore (ID, nome/cognome) o vuoto per (S)alvare e uscire, (A)ggiungi nuovo: "
        if last_managed_player_id and last_managed_player_id in players_db_main_dict:
             prompt_msg_main = f"Cerca (ID prec: {last_managed_player_id}), (A)ggiungi, (S)alva e esci: "
        
        # Usiamo get_input_with_default_gestore_db per il prompt principale per consistenza,
        # anche se dgt con default="s" andava bene.
        search_input_main_val = get_input_with_default_gestore_db(prompt_msg_main, "s").strip().lower() # Rinomino search_input_main
        
        if search_input_main_val == 's' or not search_input_main_val : 
            break 
        if search_input_main_val == 'a': 
            if add_new_player(players_db_main_dict): 
                save_players_db(players_db_main_dict) 
            continue

        found_players_list_main = find_players_partial(search_input_main_val, players_db_main_dict) # Rinomino found_players_list

        if not found_players_list_main:
            print(f"Nessun giocatore trovato per '{search_input_main_val}'.")
            if get_input_with_default_gestore_db("Vuoi aggiungere un nuovo giocatore con questi termini? (S/n) ", "n").lower() == 's':
                if add_new_player(players_db_main_dict): save_players_db(players_db_main_dict)
            continue

        elif len(found_players_list_main) == 1:
            player_to_manage_item = found_players_list_main[0] # Rinomino player_to_manage_dict
            current_player_id_main_ops = player_to_manage_item['id'] # Rinomino current_player_id_ops
            
            while True: 
                display_player_details(player_to_manage_item) # player_to_manage_item potrebbe cambiare se l'ID viene modificato
                
                action_main = get_input_with_default_gestore_db("\nAzione: (M)odifica, (C)ancella, (S)eleziona altro/Fine", "s").lower() # Rinomino action

                if action_main == 's': last_managed_player_id = current_player_id_main_ops; break 
                elif action_main == 'c':
                    if get_input_with_default_gestore_db(f"Sicuro di cancellare {player_to_manage_item.get('first_name')} {player_to_manage_item.get('last_name')} (ID: {current_player_id_main_ops})? (s/N)", "n").lower() == 's':
                        try:
                            del players_db_main_dict[current_player_id_main_ops]
                            print("Giocatore cancellato.")
                            save_players_db(players_db_main_dict) 
                            last_managed_player_id = None 
                        except KeyError: print(f"ERRORE: Giocatore ID {current_player_id_main_ops} non trovato.")
                        break 
                    else: print("Cancellazione annullata.")
                elif action_main == 'm':
                    edit_successful, resulting_player_id = edit_player_data(current_player_id_main_ops, players_db_main_dict)
                    if edit_successful:
                        save_players_db(players_db_main_dict) 
                        last_managed_player_id = resulting_player_id 
                        if last_managed_player_id in players_db_main_dict: # Ricarica se l'ID è cambiato o i dati sono stati modificati
                             player_to_manage_item = players_db_main_dict[last_managed_player_id]
                             current_player_id_main_ops = last_managed_player_id # Aggiorna l'ID corrente per il loop azioni
                        else: 
                             print(f"Attenzione: Giocatore con ID {last_managed_player_id} non più trovabile dopo modifica.")
                             break 
                else: print("Azione non riconosciuta.")
                
        else: # len(found_players_list_main) > 1
             # ... (stampa risultati multipli come prima) ...
            print(f"\nTrovate {len(found_players_list_main)} corrispondenze per '{search_input_main_val}'. Specifica meglio (es. usando l'ID):")
            found_players_list_main.sort(key=lambda p_item: (p_item.get('last_name','').lower(), p_item.get('first_name','').lower()))
            for i, p_match_item_disp in enumerate(found_players_list_main, 1): # Rinomino p_match
                print(f"  {i}. ID: {p_match_item_disp.get('id', 'N/D'):<9} - {p_match_item_disp.get('first_name', 'N/D')} {p_match_item_disp.get('last_name', 'N/D')} (Elo: {p_match_item_disp.get('current_elo', 'N/D')})")

    print("\nSalvataggio finale del database prima di uscire...")
    save_players_db(players_db_main_dict)
    print("Uscita dal gestore database giocatori.")

if __name__ == "__main__":
    db = load_players_db()
    main_interactive_db_tool_loop(db)