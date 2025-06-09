# Data concepimento 27 aprile 2025 by Gemini 2.5 (Modificato)
# gestore Players_DB.py
import os
import json
import sys 
import traceback
from datetime import datetime
from dateutil.relativedelta import relativedelta # Assicurati che sia installato: pip install python-dateutil

try:
    # Se usi GBUtils, assicurati che dgt sia aggiornato per gestire 'b' (boolean) o usa get_input_with_default_gestore_db
    from GBUtils import dgt 
except ImportError:
    print("ATTENZIONE: Libreria GBUtils non trovata. L'input non sarà validato come previsto per alcuni campi.")
    # Fallback per dgt se GBUtils non è disponibile
    def dgt(prompt, kind="s", default=None, smin=0, smax=0, imin=0, imax=0, fmin=0.0, fmax=0.0, errmsg=""):
        val = input(prompt)
        if not val and default is not None:
            return default
        if kind == "i":
            try: return int(val)
            except ValueError: print(errmsg if errmsg else "Input numerico intero non valido."); return default
        if kind == "f":
            try: return float(val)
            except ValueError: print(errmsg if errmsg else "Input numerico float non valido."); return default
        # Per kind="b" (booleano), la gestione specifica è fatta in add/edit player
        return val

# --- Constants ---
VERSION = "4.3.0 del 3 giugno 2025" # Versione aggiornata del tool
PLAYER_DB_FILE = "Tornello - Players_DB.json" # Allineato a come sembra tu lo voglia
PLAYER_DB_TXT_FILE = "Tornello - Players_DB.txt"
DATE_FORMAT_ISO = "%Y-%m-%d" 
DEFAULT_ELO = 1399.0
DEFAULT_K_FACTOR = 20 # Usato come fallback

# --- Helper Functions ---
def sanitize_filename(name):
    name = name.replace(' ', '_')
    import re 
    name = re.sub(r'[^\w\-]+', '', name)
    if not name:
        name = "File_Senza_Nome" # Cambiato per coerenza con il nome del file
    return name

def format_date_locale(date_input):
    if not date_input: return "N/D"
    try:
        date_obj = datetime.strptime(str(date_input), DATE_FORMAT_ISO) if not isinstance(date_input, datetime) else date_input
        giorni = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
        mesi = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
        return f"{giorni[date_obj.weekday()].capitalize()} {date_obj.day} {mesi[date_obj.month]} {date_obj.year}"
    except Exception: return str(date_input) if date_input else "N/D"

def format_rank_ordinal(rank):
    if rank == "RIT": return "RIT"
    try: return f"{int(rank)}°"
    except: return "?"

def get_k_factor(player_data_dict, current_date_iso_str):
    """
    Determina il K-Factor FIDE per un giocatore.
    Aggiornato per includere la logica 'experienced' come in tornello.py.
    """
    if not player_data_dict: return DEFAULT_K_FACTOR
    try:
        elo = float(player_data_dict.get('current_elo', DEFAULT_ELO))
    except (ValueError, TypeError):
        elo = DEFAULT_ELO

    games_played = player_data_dict.get('games_played', 0)
    # NUOVO: Campo 'experienced'
    is_experienced = player_data_dict.get('experienced', False) # Default a False se non presente
    birth_date_str = player_data_dict.get('birth_date')
    age = None

    if birth_date_str and current_date_iso_str:
        try:
            birth_dt = datetime.strptime(birth_date_str, DATE_FORMAT_ISO)
            current_dt = datetime.strptime(current_date_iso_str, DATE_FORMAT_ISO)
            age = relativedelta(current_dt, birth_dt).years
        except (ValueError, TypeError):
            pass 
    
    # Logica K-Factor aggiornata (come da tornello.py)
    if games_played < 30 and not is_experienced: # Modificato qui
        return 40
    if age is not None and age < 18 and elo < 2300:
        return 40
    if elo < 2400:
        return 20
    return 10

def save_players_db_txt(players_db_dict):
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

            sorted_players = sorted(list(players_db_dict.values()), key=lambda p: (p.get('last_name','').lower(), p.get('first_name','').lower()))
            
            for p_data in sorted_players:
                title_prefix = f"{p_data.get('fide_title', '')} " if p_data.get('fide_title') else ""
                f.write(f"ID: {p_data.get('id', 'N/D')}, {title_prefix}{p_data.get('first_name', 'N/D')} {p_data.get('last_name', 'N/D')}, Elo: {p_data.get('current_elo', 'N/D')}\n")
                f.write(f"\tSesso: {str(p_data.get('sex', 'N/D')).upper()}, Federazione: {str(p_data.get('federation', 'N/D')).upper()}, ID FIDE num: {p_data.get('fide_id_num_str', 'N/D')}\n")
                f.write(f"\tData Nascita: {format_date_locale(p_data.get('birth_date'))}\n")
                
                # NUOVO: Visualizzazione 'experienced'
                experienced_str = "Sì" if p_data.get('experienced', False) else "No"
                f.write(f"\tEsperienza Pregressa Significativa: {experienced_str}\n")

                k_factor = get_k_factor(p_data, current_date_iso_for_k) # Ora usa 'experienced'
                f.write(f"\tPartite Valutate: {p_data.get('games_played', 0)}, K-Factor Stimato: {k_factor}, Iscrizione DB: {format_date_locale(p_data.get('registration_date'))}\n")
                
                medals = p_data.get('medals', {})
                f.write(f"\tMedagliere: Oro: {medals.get('gold',0)}, Argento: {medals.get('silver',0)}, Bronzo: {medals.get('bronze',0)}, Legno: {medals.get('wood',0)}\n")
                
                tournaments = p_data.get('tournaments_played', [])
                f.write(f"\tTornei Giocati ({len(tournaments)}):\n")
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
                    
                    p_entry.setdefault('fide_title', '')       
                    p_entry.setdefault('sex', 'm')             
                    p_entry.setdefault('federation', 'ITA')    
                    p_entry.setdefault('fide_id_num_str', '0') 
                    # NUOVO: setdefault per 'experienced'
                    p_entry.setdefault('experienced', False)   

                    players_dict[p_entry['id']] = p_entry
            print(f"Database '{PLAYER_DB_FILE}' caricato ({len(players_dict)} giocatori).")
        except Exception as e:
            print(f"Errore caricamento DB ({PLAYER_DB_FILE}): {e}. Verrà usato un DB vuoto in memoria.")
            players_dict = {} 
    else:
        print(f"File database '{PLAYER_DB_FILE}' non trovato. Verrà creato un nuovo DB se si aggiungono giocatori.")
    return players_dict

def save_players_db(players_db_dict_to_save):
    if not isinstance(players_db_dict_to_save, dict):
        print("ERRORE INTERNO: save_players_db si aspetta un dizionario.")
        return
    try:
        with open(PLAYER_DB_FILE, "w", encoding='utf-8') as f:
            # Allineo indent a 1 come sembra essere ora in tornello.py per il DB giocatori
            json.dump(list(players_db_dict_to_save.values()), f, indent=1, ensure_ascii=False) 
        print(f"Database giocatori JSON '{PLAYER_DB_FILE}' salvato.")
        save_players_db_txt(players_db_dict_to_save) 
    except Exception as e:
        print(f"ERRORE durante il salvataggio del DB giocatori ({PLAYER_DB_FILE}): {e}")
        traceback.print_exc()

def generate_player_id(first_name, last_name, players_db_dict):
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
            # Usa una parte più lunga del timestamp per maggiore unicità
            timestamp_suffix = datetime.now().strftime('%S%f') 
            new_id = f"{base_id}{timestamp_suffix[-4:]}" # Usa gli ultimi 4 per mantenere lunghezza
            if new_id in players_db_dict: return None # Fallimento se ancora collisione
            break 
    if new_id in players_db_dict and current_attempt >= max_attempts: 
        return None 
    return new_id     

def find_players_partial(search_term, players_db_dict):
    matches = []
    search_lower = search_term.strip().lower()
    if not search_lower: return matches
    for p_data_item in players_db_dict.values():
        # Aggiunta ricerca per ID giocatore nella ricerca parziale
        if search_lower in p_data_item.get('first_name', '').lower() or \
           search_lower in p_data_item.get('last_name', '').lower() or \
           search_lower == p_data_item.get('id','').lower() or \
           search_lower == p_data_item.get('fide_title','').lower() or \
           search_lower == p_data_item.get('fide_id_num_str',''):
            matches.append(p_data_item)
    return matches

def get_input_with_default_gestore_db(prompt_message, default_value=None):
    default_display = str(default_value) if default_value is not None else ""
    if default_display or isinstance(default_value, str) and default_value == "": 
        user_input = input(f"{prompt_message} [{default_display}]: ").strip()
        return user_input if user_input or (not user_input and default_value is None) else default_value
    else: 
        return input(f"{prompt_message}: ").strip()

def display_player_details(player_data):
    print("\n--- Scheda Giocatore Dettagliata ---")
    if not player_data: 
        print("Dati giocatore non validi o non trovati.")
        return
    
    title_prefix = f"{player_data.get('fide_title', '')} " if player_data.get('fide_title') else ""
    print(f"{'ID':<30}: {player_data.get('id', 'N/D')}")
    print(f"{'Nome Completo':<30}: {title_prefix}{player_data.get('first_name', 'N/D')} {player_data.get('last_name', 'N/D')}")
    print(f"{'Titolo FIDE':<30}: {player_data.get('fide_title', 'N/D') if player_data.get('fide_title') else 'Nessuno'}")
    print(f"{'Elo Corrente':<30}: {player_data.get('current_elo', 'N/D')}")
    print(f"{'Sesso':<30}: {str(player_data.get('sex', 'N/D')).upper()}")
    print(f"{'Federazione':<30}: {str(player_data.get('federation', 'N/D')).upper()}")
    print(f"{'ID FIDE Numerico':<30}: {player_data.get('fide_id_num_str', 'N/D')}")
    print(f"{'Data Nascita':<30}: {format_date_locale(player_data.get('birth_date'))}") 
    print(f"{'Data Registrazione DB':<30}: {format_date_locale(player_data.get('registration_date'))}")
    print(f"{'Partite Giocate (valutate)':<30}: {player_data.get('games_played', 0)}")
    # NUOVO: Visualizzazione 'experienced'
    experienced_val_str = "Sì" if player_data.get('experienced', False) else "No"
    print(f"{'Esperienza Pregressa Signif.':<30}: {experienced_val_str}")
    
    medals = player_data.get('medals', {})
    print(f"{'Medagliere':<30}: Oro: {medals.get('gold',0)}, Argento: {medals.get('silver',0)}, Bronzo: {medals.get('bronze',0)}, Legno: {medals.get('wood',0)}")
    
    tournaments = player_data.get('tournaments_played', [])
    print(f"{'Storico Tornei Giocati':<30}: {len(tournaments)} registrati")
    if tournaments:
        try:
            tournaments_s_list = sorted(tournaments, key=lambda t_item: datetime.strptime(t_item.get('date_completed', '1900-01-01'), DATE_FORMAT_ISO), reverse=True)
        except: tournaments_s_list = tournaments 
        for i, t_rec_item in enumerate(tournaments_s_list):
            total_p_val = t_rec_item.get('total_players', '?')
            start_d = format_date_locale(t_rec_item.get('date_started'))
            end_d = format_date_locale(t_rec_item.get('date_completed'))
            print(f"  {i+1}. {format_rank_ordinal(t_rec_item.get('rank', '?'))} su {total_p_val} in '{t_rec_item.get('tournament_name', 'N/D')}'")
            print(f"     Date: {start_d} - {end_d} (ID Torneo: {t_rec_item.get('tournament_id', 'N/A')})")
    print("-" * 40)

def add_new_player(players_db_dict_ref):
    print("\n--- Aggiunta Nuovo Giocatore ---")
    first_name = get_input_with_default_gestore_db("Nome: ").title()
    if not first_name: print("Nome richiesto."); return False
    last_name = get_input_with_default_gestore_db("Cognome: ").title()
    if not last_name: print("Cognome richiesto."); return False
    
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

    birth_date_str_new = None # Rinominata per chiarezza
    while True:
        bdate_input = get_input_with_default_gestore_db(f"Data di nascita ({DATE_FORMAT_ISO} o vuoto):", "")
        if not bdate_input: break
        try:
            datetime.strptime(bdate_input, DATE_FORMAT_ISO)
            birth_date_str_new = bdate_input
            break
        except ValueError: print(f"Formato data non valido. Usa {DATE_FORMAT_ISO}.")
    
    # NUOVO: Input per 'experienced'
    experienced_new_val = False
    while True:
        exp_input_str = get_input_with_default_gestore_db("Giocatore con esperienza pregressa significativa? (s/n):", "n").lower()
        if exp_input_str == 's': experienced_new_val = True; break
        elif exp_input_str == 'n': experienced_new_val = False; break
        print("Risposta non valida. Inserisci 's' o 'n'.")

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
        "fide_id_num_str": fide_id_num_new, "birth_date": birth_date_str_new,
        "experienced": experienced_new_val # NUOVO: Aggiunto al record
    }
    players_db_dict_ref[new_id] = new_player_record
    print(f"Giocatore '{new_player_record['first_name']} {new_player_record['last_name']}' aggiunto con ID {new_id}.")
    display_player_details(new_player_record)
    return True 

def edit_player_data(player_id_to_edit, players_db_dict_ref):
    if player_id_to_edit not in players_db_dict_ref:
        print(f"Errore: Giocatore con ID {player_id_to_edit} non trovato.")
        return False, player_id_to_edit 

    player_data_ref = players_db_dict_ref[player_id_to_edit] 
    original_id = player_data_ref['id'] 
    
    print(f"\n--- Modifica Giocatore ID: {original_id} ({player_data_ref.get('first_name')} {player_data_ref.get('last_name')}) ---")
    display_player_details(player_data_ref)
    print("--- Inserisci nuovi valori o premi Invio per mantenere i correnti ---")
    
    original_first_name = player_data_ref.get('first_name', '')
    new_first_name = get_input_with_default_gestore_db("Nome", original_first_name).title()
    original_last_name = player_data_ref.get('last_name', '')
    new_last_name = get_input_with_default_gestore_db("Cognome", original_last_name).title()

    id_changed_flag = False
    final_id_for_player = original_id

    # Logica rigenerazione ID (se nome/cognome cambiano)
    if (new_first_name and new_first_name != original_first_name) or \
       (new_last_name and new_last_name != original_last_name):
        if new_first_name and new_last_name: # Solo se entrambi sono ancora validi
            print("Nome o cognome modificati.")
            if get_input_with_default_gestore_db("Vuoi tentare di rigenerare l'ID in base al nuovo nome/cognome? (s/N)", "n").lower() == 's':
                temp_player_data_for_id_gen = players_db_dict_ref.pop(original_id, None) 
                if temp_player_data_for_id_gen is None: # Sicurezza
                     print("ERRORE INTERNO: Impossibile recuperare i dati del giocatore per la rigenerazione dell'ID."); return False, original_id

                candidate_new_id = generate_player_id(new_first_name, new_last_name, players_db_dict_ref) 
                
                if candidate_new_id and candidate_new_id != original_id:
                    if candidate_new_id in players_db_dict_ref: 
                        print(f"ATTENZIONE: Il nuovo ID generato '{candidate_new_id}' è già in uso. L'ID originale '{original_id}' verrà mantenuto.")
                        players_db_dict_ref[original_id] = temp_player_data_for_id_gen # Ripristina
                    else:
                        final_id_for_player = candidate_new_id
                        id_changed_flag = True
                        temp_player_data_for_id_gen['id'] = final_id_for_player # Aggiorna ID nel record
                        players_db_dict_ref[final_id_for_player] = temp_player_data_for_id_gen # Reinserisci con nuovo ID
                        player_data_ref = players_db_dict_ref[final_id_for_player] # Aggiorna riferimento
                        print(f"ID giocatore aggiornato da '{original_id}' a '{final_id_for_player}'.")
                elif not candidate_new_id :
                    print("Errore nella generazione del nuovo ID. L'ID originale '{original_id}' verrà mantenuto.")
                    players_db_dict_ref[original_id] = temp_player_data_for_id_gen # Ripristina
                else: # candidate_new_id == original_id
                    print("Il nuovo ID generato è identico all'originale. Nessuna modifica all'ID.")
                    players_db_dict_ref[original_id] = temp_player_data_for_id_gen # Ripristina
        else: # Nome o cognome diventati vuoti
            print("Nome e/o cognome non possono essere vuoti. Modifiche a nome/cognome annullate.")
            new_first_name = original_first_name 
            new_last_name = original_last_name
    
    player_data_ref['first_name'] = new_first_name if new_first_name else original_first_name
    player_data_ref['last_name'] = new_last_name if new_last_name else original_last_name
    
    # Modifica Elo con validazione di range tramite dgt (o la tua alternativa preferita)
    try:
        current_elo_val = float(player_data_ref.get('current_elo', DEFAULT_ELO))
    except ValueError:
        current_elo_val = DEFAULT_ELO
    player_data_ref['current_elo'] = dgt("Elo Corrente (range 0-3500)", kind="f", fmin=0.0, fmax=3500.0, default=current_elo_val)
    
    player_data_ref['fide_title'] = get_input_with_default_gestore_db("Titolo FIDE (es. FM, '' per nessuno)", player_data_ref.get('fide_title', '')).upper()[:3]
    
    sex_default_edit = player_data_ref.get('sex', 'm')
    while True:
        sex_input_val = get_input_with_default_gestore_db("Sesso (m/w)", sex_default_edit).lower()
        if sex_input_val in ['m', 'w']: player_data_ref['sex'] = sex_input_val; break
        elif not sex_input_val and sex_default_edit: player_data_ref['sex'] = sex_default_edit; break # Mantiene default se vuoto
        elif not sex_input_val and not sex_default_edit: player_data_ref['sex'] = 'm'; break # Default 'm' se era vuoto e cancellato
        print("Input non valido.")
            
    fed_default_edit = player_data_ref.get('federation', 'ITA')
    player_data_ref['federation'] = get_input_with_default_gestore_db("Federazione (3 lettere)", fed_default_edit).upper()[:3]
    if not player_data_ref['federation']: player_data_ref['federation'] = fed_default_edit 
    if not player_data_ref['federation']: player_data_ref['federation'] = 'ITA' 

    fide_id_default_edit = player_data_ref.get('fide_id_num_str', '0')
    new_fide_id_val = get_input_with_default_gestore_db("ID FIDE Numerico (cifre, '0' se N/D)", fide_id_default_edit)
    if not new_fide_id_val.isdigit(): new_fide_id_val = fide_id_default_edit # Ripristina se non numero
    if not new_fide_id_val: new_fide_id_val = '0' 
    player_data_ref['fide_id_num_str'] = new_fide_id_val

    birth_date_default_edit_str = player_data_ref.get('birth_date', "") # Passa stringa vuota se None per get_input
    while True:
        bdate_input_val = get_input_with_default_gestore_db(f"Data di nascita ({DATE_FORMAT_ISO} o vuoto per cancellare)", birth_date_default_edit_str)
        if not bdate_input_val: player_data_ref['birth_date'] = None; break
        try:
            datetime.strptime(bdate_input_val, DATE_FORMAT_ISO)
            player_data_ref['birth_date'] = bdate_input_val; break
        except ValueError: print(f"Formato data non valido. Usa {DATE_FORMAT_ISO}.")

    # NUOVO: Modifica 'experienced'
    current_experienced_val = player_data_ref.get('experienced', False)
    experienced_default_str = 's' if current_experienced_val else 'n'
    while True:
        exp_input_str_edit = get_input_with_default_gestore_db("Giocatore con esperienza pregressa significativa? (s/n)", experienced_default_str).lower()
        if exp_input_str_edit == 's': player_data_ref['experienced'] = True; break
        elif exp_input_str_edit == 'n': player_data_ref['experienced'] = False; break
        print("Risposta non valida. Inserisci 's' o 'n'.")

    print("\n--- Modifica Medagliere ---")
    medals_data_ref = player_data_ref.setdefault('medals', {'gold': 0, 'silver': 0, 'bronze': 0, 'wood': 0})
    for m_key_val_edit in ['gold', 'silver', 'bronze', 'wood']:
        medals_data_ref[m_key_val_edit] = dgt(f"Medaglie di {m_key_val_edit.capitalize()}", kind="i", imin=0, imax=999, default=medals_data_ref.get(m_key_val_edit, 0))
    # --- Modifica Storico Tornei ---
    print("\n--- Modifica Storico Tornei ---")
    tournaments_data_ref = player_data_ref.setdefault('tournaments_played', [])

    while True:
        print("\nStorico Tornei Attuale:")
        if not tournaments_data_ref:
            print("  Nessun torneo registrato nello storico.")
        else:
            # Ordina i tornei per data di completamento (più recente prima) per la visualizzazione
            try:
                sorted_tournaments_for_display = sorted(
                    tournaments_data_ref,
                    key=lambda t_item: datetime.strptime(t_item.get('date_completed', '1900-01-01'), DATE_FORMAT_ISO),
                    reverse=True
                )
            except ValueError: # In caso di date malformate, non ordinare
                sorted_tournaments_for_display = tournaments_data_ref

            for i, t_disp in enumerate(sorted_tournaments_for_display):
                rank_disp = format_rank_ordinal(t_disp.get('rank', '?'))
                name_disp = t_disp.get('tournament_name', 'Nome Torneo Mancante')
                players_disp = t_disp.get('total_players', '?')
                start_disp = format_date_locale(t_disp.get('date_started'))
                end_disp = format_date_locale(t_disp.get('date_completed'))
                tid_disp = t_disp.get('tournament_id', 'N/A')
                print(f"  {i+1}. {rank_disp} su {players_disp} in '{name_disp}'")
                print(f"     Date: {start_disp} - {end_disp} (ID Torneo: {tid_disp})")
        
        print("\nOpzioni Storico Tornei:")
        op_tourn = get_input_with_default_gestore_db("  (A)ggiungi, (M)odifica, (C)ancella, (F)ine gestione storico: ", "f").strip().lower()

        if op_tourn == 'f':
            break
        
        elif op_tourn == 'a':
            print("\n  --- Aggiunta nuovo torneo allo storico ---")
            new_t_entry = {}
            new_t_entry['tournament_name'] = get_input_with_default_gestore_db("  Nome torneo: ")
            if not new_t_entry['tournament_name']:
                print("  Nome torneo è obbligatorio. Aggiunta annullata."); continue
            
            new_t_entry['tournament_id'] = get_input_with_default_gestore_db(f"  ID Torneo (default: '{sanitize_filename(new_t_entry['tournament_name'])}_{datetime.now().strftime('%Y%m')}'): ", 
                                                                        f"{sanitize_filename(new_t_entry['tournament_name'])}_{datetime.now().strftime('%Y%m')}")
            
            new_t_entry['rank'] = get_input_with_default_gestore_db("  Posizione (es. 1, 2, o RIT): ")
            tp_str = get_input_with_default_gestore_db("  Numero totale partecipanti: ")
            try: new_t_entry['total_players'] = int(tp_str)
            except ValueError: new_t_entry['total_players'] = 0; print("  Numero partecipanti non valido, impostato a 0.")

            while True:
                ds_str = get_input_with_default_gestore_db(f"  Data inizio torneo ({DATE_FORMAT_ISO}): ")
                if not ds_str: new_t_entry['date_started'] = None; break # Permetti data vuota
                try: datetime.strptime(ds_str, DATE_FORMAT_ISO); new_t_entry['date_started'] = ds_str; break
                except ValueError: print(f"  Formato data non valido. Usa {DATE_FORMAT_ISO}.")
            
            while True:
                dc_str = get_input_with_default_gestore_db(f"  Data fine torneo ({DATE_FORMAT_ISO}): ")
                if not dc_str: new_t_entry['date_completed'] = None; break # Permetti data vuota
                try: 
                    dt_comp = datetime.strptime(dc_str, DATE_FORMAT_ISO)
                    if new_t_entry.get('date_started'):
                        dt_start = datetime.strptime(new_t_entry['date_started'], DATE_FORMAT_ISO)
                        if dt_comp < dt_start:
                            print("  La data di fine non può precedere la data di inizio.")
                            continue
                    new_t_entry['date_completed'] = dc_str; break
                except ValueError: print(f"  Formato data non valido. Usa {DATE_FORMAT_ISO}.")

            tournaments_data_ref.append(new_t_entry)
            print(f"  Torneo '{new_t_entry['tournament_name']}' aggiunto allo storico.")
            any_changes_made_this_session = True # Assumendo che questa variabile sia definita in edit_player_data

        elif op_tourn == 'm' and tournaments_data_ref:
            idx_str_m = get_input_with_default_gestore_db(f"  Numero torneo da modificare (1-{len(tournaments_data_ref)}): ")
            try:
                idx_to_edit = int(idx_str_m) - 1
                if 0 <= idx_to_edit < len(sorted_tournaments_for_display): # Usa la lista ordinata per l'indice
                    t_to_edit = sorted_tournaments_for_display[idx_to_edit] # Prendi l'oggetto corretto dalla lista ordinata
                    # Trova l'oggetto originale nella lista non ordinata per la modifica effettiva, se necessario
                    # Questo è importante se l'ordine in tournaments_data_ref è diverso e non vuoi basarti sull'indice di sorted_tournaments_for_display
                    # Per semplicità, se l'ID del torneo è affidabile e univoco, sarebbe meglio cercare per ID
                    # Se non c'è un ID univoco per voce di storico, modificare t_to_edit dovrebbe funzionare perché è un riferimento all'oggetto dizionario.
                    
                    print(f"\n  --- Modifica torneo storico: '{t_to_edit.get('tournament_name')}' ---")
                    print(f"  (Lasciare vuoto per mantenere il valore attuale: '{t_to_edit.get('tournament_name')}')")
                    t_to_edit['tournament_name'] = get_input_with_default_gestore_db("  Nuovo Nome torneo: ", t_to_edit.get('tournament_name'))
                    
                    print(f"  (Valore attuale ID Torneo: '{t_to_edit.get('tournament_id')}')")
                    t_to_edit['tournament_id'] = get_input_with_default_gestore_db("  Nuovo ID Torneo: ", t_to_edit.get('tournament_id'))
                    
                    print(f"  (Valore attuale Posizione: '{t_to_edit.get('rank')}')")
                    t_to_edit['rank'] = get_input_with_default_gestore_db("  Nuova Posizione: ", t_to_edit.get('rank'))
                    
                    print(f"  (Valore attuale Tot. Partecipanti: '{t_to_edit.get('total_players')}')")
                    tp_edit_str = get_input_with_default_gestore_db("  Nuovo Tot. Partecipanti: ", str(t_to_edit.get('total_players', '')))
                    try: t_to_edit['total_players'] = int(tp_edit_str) if tp_edit_str else t_to_edit.get('total_players')
                    except ValueError: print("  Numero partecipanti non valido, valore precedente mantenuto.")

                    # Modifica Data Inizio
                    current_ds_edit = t_to_edit.get('date_started', "")
                    while True:
                        ds_edit_str = get_input_with_default_gestore_db(f"  Nuova Data inizio ({DATE_FORMAT_ISO}, vuoto per cancellare)", current_ds_edit)
                        if not ds_edit_str: t_to_edit['date_started'] = None; break
                        try: datetime.strptime(ds_edit_str, DATE_FORMAT_ISO); t_to_edit['date_started'] = ds_edit_str; break
                        except ValueError: print(f"  Formato data non valido. Usa {DATE_FORMAT_ISO}.")
                    
                    # Modifica Data Fine
                    current_dc_edit = t_to_edit.get('date_completed', "")
                    while True:
                        dc_edit_str = get_input_with_default_gestore_db(f"  Nuova Data fine ({DATE_FORMAT_ISO}, vuoto per cancellare)", current_dc_edit)
                        if not dc_edit_str: t_to_edit['date_completed'] = None; break
                        try: 
                            dt_comp_edit = datetime.strptime(dc_edit_str, DATE_FORMAT_ISO)
                            if t_to_edit.get('date_started'):
                                dt_start_edit = datetime.strptime(t_to_edit['date_started'], DATE_FORMAT_ISO)
                                if dt_comp_edit < dt_start_edit:
                                    print("  La data di fine non può precedere la data di inizio.")
                                    continue
                            t_to_edit['date_completed'] = dc_edit_str; break
                        except ValueError: print(f"  Formato data non valido. Usa {DATE_FORMAT_ISO}.")
                    
                    print("  Torneo nello storico modificato.")
                    any_changes_made_this_session = True
                else:
                    print("  Numero torneo non valido.")
            except ValueError:
                print("  Input non numerico per la selezione del torneo.")

        elif op_tourn == 'c' and tournaments_data_ref:
            idx_str_c = get_input_with_default_gestore_db(f"  Numero torneo da cancellare (1-{len(tournaments_data_ref)}): ")
            try:
                idx_to_delete = int(idx_str_c) - 1
                if 0 <= idx_to_delete < len(sorted_tournaments_for_display): # Usa la lista ordinata per l'indice
                    tournament_to_delete_display_info = sorted_tournaments_for_display[idx_to_delete]
                    
                    # Trova l'elemento corrispondente nella lista originale (tournaments_data_ref) per la rimozione
                    # Questo è necessario perché l'indice di sorted_tournaments_for_display potrebbe non corrispondere
                    # all'indice in tournaments_data_ref se quest'ultima non era già ordinata allo stesso modo.
                    # La soluzione più sicura è cercare l'oggetto esatto o basarsi su un ID univoco se presente.
                    # Se gli oggetti sono dizionari, t_to_delete sarà un riferimento.
                    original_index_to_remove = -1
                    for i_orig, orig_t_obj in enumerate(tournaments_data_ref):
                        # Confronta alcuni campi chiave per identificare l'oggetto (o meglio un ID se ci fosse)
                        if orig_t_obj.get('tournament_name') == tournament_to_delete_display_info.get('tournament_name') and \
                           orig_t_obj.get('date_completed') == tournament_to_delete_display_info.get('date_completed') and \
                           orig_t_obj.get('tournament_id') == tournament_to_delete_display_info.get('tournament_id'): # ID è più robusto
                           original_index_to_remove = i_orig
                           break
                    
                    if original_index_to_remove != -1:
                        removed_t_name = tournaments_data_ref[original_index_to_remove].get('tournament_name', 'N/D')
                        if get_input_with_default_gestore_db(f"  Sicuro di cancellare il torneo '{removed_t_name}' dallo storico? (s/N)", "n").lower() == 's':
                            tournaments_data_ref.pop(original_index_to_remove)
                            print(f"  Torneo '{removed_t_name}' rimosso dallo storico.")
                            any_changes_made_this_session = True
                        else:
                            print("  Cancellazione annullata.")
                    else:
                        print("  Errore: Impossibile trovare il torneo selezionato nella lista originale per la cancellazione.")
                else:
                    print("  Numero torneo non valido.")
            except ValueError:
                print("  Input non numerico per la selezione del torneo.")
        
        elif op_tourn in ['m', 'c'] and not tournaments_data_ref:
             print("  Nessun torneo nello storico da modificare o cancellare.")
        elif op_tourn not in ['a', 'f']:
             print("  Operazione non valida per lo storico tornei.")

    print("\nGestione storico tornei completata.")
    display_player_details(player_data_ref) # Mostra i dati aggiornati
    return True, final_id_for_player # Assicurati che any_changes_made_this_session sia gestita correttamente per il ritorno

def main_interactive_db_tool_loop(players_db_main_dict):
    print(f"\n--- Gestore Database Giocatori Tornello (Tool Esterno) ---\n\tVersione: {VERSION}.\n")
    last_managed_player_id = None 
    while True:
        print("\n" + "="*40)
        print(f"Giocatori nel database: {len(players_db_main_dict)}")
        
        prompt_msg_main = "Cerca giocatore (ID, nome/cognome), (L)ista tutti, (A)ggiungi nuovo, (S)alva e esci: "
        if last_managed_player_id and last_managed_player_id in players_db_main_dict:
             prompt_msg_main = f"Cerca (ID prec: {last_managed_player_id}), (L)ista, (A)ggiungi, (S)alva e esci: "
        
        search_input_main_val = get_input_with_default_gestore_db(prompt_msg_main, "s").strip().lower()
        
        if search_input_main_val == 's' or not search_input_main_val : 
            break 
        if search_input_main_val == 'a': 
            if add_new_player(players_db_main_dict): 
                save_players_db(players_db_main_dict) 
            continue
        if search_input_main_val == 'l':
            if not players_db_main_dict: print("Database vuoto.")
            else:
                print("\n--- Lista Giocatori Completa ---")
                # Ordina per cognome, nome per la visualizzazione
                sorted_for_display = sorted(list(players_db_main_dict.values()), key=lambda p_sort: (p_sort.get('last_name','').lower(), p_sort.get('first_name','').lower()))
                for p_list_item in sorted_for_display:
                    title_p_list = f"{p_list_item.get('fide_title','')} " if p_list_item.get('fide_title') else ""
                    print(f" ID: {p_list_item.get('id'):<10} | {title_p_list}{p_list_item.get('first_name','N/D')} {p_list_item.get('last_name','N/D')} | Elo: {p_list_item.get('current_elo','N/D')}")
            continue


        found_players_list_main = find_players_partial(search_input_main_val, players_db_main_dict)

        if not found_players_list_main:
            print(f"Nessun giocatore trovato per '{search_input_main_val}'.")
            if get_input_with_default_gestore_db("Vuoi aggiungere un nuovo giocatore? (S/n) ", "n").lower() == 's':
                if add_new_player(players_db_main_dict): save_players_db(players_db_main_dict)
            continue

        elif len(found_players_list_main) == 1:
            player_to_manage_item = found_players_list_main[0]
            current_player_id_main_ops = player_to_manage_item['id'] 
            
            while True: 
                # Ricarica i dati del giocatore nel caso siano cambiati (es. ID)
                if current_player_id_main_ops in players_db_main_dict:
                    player_to_manage_item = players_db_main_dict[current_player_id_main_ops]
                else: # Giocatore non più esistente con quell'ID (es. ID cambiato e vecchio cancellato)
                    print(f"Giocatore con ID {current_player_id_main_ops} non più presente. Potrebbe essere stato modificato l'ID.")
                    last_managed_player_id = None # Resetta ID precedente
                    break # Torna al menu principale di ricerca


                display_player_details(player_to_manage_item) 
                
                action_main = get_input_with_default_gestore_db("\nAzione: (M)odifica, (C)ancella, (S)eleziona altro/Fine", "s").lower()

                if action_main == 's': last_managed_player_id = current_player_id_main_ops; break 
                elif action_main == 'c':
                    if get_input_with_default_gestore_db(f"Sicuro di cancellare {player_to_manage_item.get('first_name')} {player_to_manage_item.get('last_name')} (ID: {current_player_id_main_ops})? (s/N)", "n").lower() == 's':
                        try:
                            del players_db_main_dict[current_player_id_main_ops]
                            print("Giocatore cancellato.")
                            save_players_db(players_db_main_dict) 
                            last_managed_player_id = None 
                        except KeyError: print(f"ERRORE: Giocatore ID {current_player_id_main_ops} non trovato al momento della cancellazione.")
                        break 
                    else: print("Cancellazione annullata.")
                elif action_main == 'm':
                    edit_successful, resulting_player_id = edit_player_data(current_player_id_main_ops, players_db_main_dict)
                    if edit_successful:
                        save_players_db(players_db_main_dict) 
                        last_managed_player_id = resulting_player_id 
                        current_player_id_main_ops = resulting_player_id # Aggiorna l'ID per il loop azioni
                        # Non è necessario ricaricare player_to_manage_item qui perché edit_player_data
                        # aggiorna player_data_ref che è un riferimento allo stesso oggetto in players_db_main_dict,
                        # a meno che l'ID non sia cambiato, nel qual caso player_data_ref viene riassegnato.
                    # Il loop while(True) esterno a questo blocco azioni chiamerà di nuovo display_player_details
                    # con i dati potenzialmente aggiornati.
                else: print("Azione non riconosciuta.")
                
        else: # len(found_players_list_main) > 1
            print(f"\nTrovate {len(found_players_list_main)} corrispondenze per '{search_input_main_val}'. Specifica meglio (es. usando l'ID esatto):")
            found_players_list_main.sort(key=lambda p_item: (p_item.get('last_name','').lower(), p_item.get('first_name','').lower()))
            for i, p_match_item_disp in enumerate(found_players_list_main, 1):
                title_p_list_multi = f"{p_match_item_disp.get('fide_title','')} " if p_match_item_disp.get('fide_title') else ""
                print(f"  {i}. ID: {p_match_item_disp.get('id', 'N/D'):<10} - {title_p_list_multi}{p_match_item_disp.get('first_name', 'N/D')} {p_match_item_disp.get('last_name', 'N/D')} (Elo: {p_match_item_disp.get('current_elo', 'N/D')})")

    print("\nSalvataggio finale del database prima di uscire...")
    save_players_db(players_db_main_dict)
    print("Uscita dal gestore database giocatori.")

if __name__ == "__main__":
    db = load_players_db()
    main_interactive_db_tool_loop(db)