# Data concepimento 27 aprile 2025 by Gemini 2.5 (Modificato)
# Versione 3 - Adattato per tornello_new.py e GBUtils.dgt
import os
import json
import sys
import traceback # Per debug in save_players_db_txt
from datetime import datetime
from dateutil.relativedelta import relativedelta # Necessario per get_k_factor
from GBUtils import dgt
# --- Constants ---
PLAYER_DB_FILE = "tornello - giocatori_db.json"
PLAYER_DB_TXT_FILE = "tornello - giocatori_db.txt"
DATE_FORMAT_ISO = "%Y-%m-%d"
DEFAULT_ELO = 1399.0
DEFAULT_K_FACTOR = 20

# --- Helper Functions (copiate/adattate da tornello_new.py) ---
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
    except:
        return str(date_input)

def format_rank_ordinal(rank):
    if rank == "RIT": return "RIT"
    try: return f"{int(rank)}°"
    except: return "?"

def get_k_factor(player_db_data, current_date_iso_str): # Rinominato per chiarezza
    if not player_db_data: return DEFAULT_K_FACTOR
    try: elo = float(player_db_data.get('current_elo', DEFAULT_ELO))
    except: elo = DEFAULT_ELO
    games = player_db_data.get('games_played', 0)
    birth_str = player_db_data.get('birth_date')
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
    try:
        with open(PLAYER_DB_TXT_FILE, "w", encoding='utf-8-sig') as f:
            now = datetime.now()
            current_date_iso = now.strftime(DATE_FORMAT_ISO)
            f.write(f"Report Database Giocatori Tornello - {format_date_locale(now.date())} {now.strftime('%H:%M:%S')}\n")
            f.write("=" * 40 + "\n\n")
            players_list = list(players_db_dict.values())
            sorted_players = sorted(players_list, key=lambda p: (p.get('last_name','').lower(), p.get('first_name','').lower()))
            if not sorted_players:
                f.write("Il database dei giocatori è vuoto.\n")
                return
            for p in sorted_players:
                f.write(f"ID: {p.get('id', 'N/D')}, {p.get('first_name', 'N/D')} {p.get('last_name', 'N/D')}, Elo: {p.get('current_elo', 'N/D')}\n")
                f.write(f"\tPartite Valutate Totali: {p.get('games_played', 0)}, K-Factor Stimato: {get_k_factor(p, current_date_iso)}, Data Iscrizione DB: {format_date_locale(p.get('registration_date'))}\n")
                f.write(f"\tData Nascita: {format_date_locale(p.get('birth_date')) if p.get('birth_date') else 'N/D'}\n")
                medals = p.get('medals', {})
                f.write(f"\tMedagliere: Oro: {medals.get('gold',0)}, Argento: {medals.get('silver',0)}, Bronzo: {medals.get('bronze',0)}, Legno: {medals.get('wood',0)} in ")
                tournaments = p.get('tournaments_played', [])
                f.write(f"({len(tournaments)}) tornei:\n")
                if tournaments:
                    try:
                        tournaments_sorted = sorted(tournaments, key=lambda t: datetime.strptime(t.get('date_completed', '1900-01-01'), DATE_FORMAT_ISO), reverse=True)
                    except ValueError: tournaments_sorted = tournaments
                    for t in tournaments_sorted:
                         f.write(f"\t{format_rank_ordinal(t.get('rank', '?'))} in {t.get('tournament_name', 'N/M')} - {format_date_locale(t.get('date_started'))} - {format_date_locale(t.get('date_completed'))}\n")
                else: f.write("\tNessuno\n")
                f.write("\t" + "-" * 30 + "\n")
    except Exception as e:
        print(f"Errore salvataggio TXT DB: {e}")
        traceback.print_exc()

# --- Database Functions ---
def load_players_db():
    players_dict = {}
    if os.path.exists(PLAYER_DB_FILE):
        try:
            with open(PLAYER_DB_FILE, "r", encoding='utf-8') as f:
                db_list = json.load(f)
                for p in db_list:
                    if 'id' not in p: continue
                    p.setdefault('first_name', 'Sconosciuto')
                    p.setdefault('last_name', 'Sconosciuto')
                    p.setdefault('current_elo', DEFAULT_ELO)
                    p.setdefault('registration_date', datetime.now().strftime(DATE_FORMAT_ISO))
                    p.setdefault('birth_date', None)
                    p.setdefault('games_played', 0)
                    medals_dict = p.setdefault('medals', {})
                    for m_key in ['gold', 'silver', 'bronze', 'wood']: medals_dict.setdefault(m_key, 0)
                    p.setdefault('tournaments_played', [])
                    players_dict[p['id']] = p
            print(f"Database '{PLAYER_DB_FILE}' caricato ({len(players_dict)} giocatori).")
        except Exception as e:
            print(f"Errore caricamento DB ({PLAYER_DB_FILE}): {e}. DB vuoto in memoria.")
            players_dict = {}
    else:
        print(f"File database '{PLAYER_DB_FILE}' non trovato. Verrà creato.")
    return players_dict

def save_players_db(players_db_dict):
    try:
        with open(PLAYER_DB_FILE, "w", encoding='utf-8') as f:
            json.dump(list(players_db_dict.values()), f, indent=4, ensure_ascii=False)
        save_players_db_txt(players_db_dict)
    except Exception as e:
        print(f"ERRORE salvataggio DB ({PLAYER_DB_FILE}): {e}")

def generate_player_id(first_name, last_name, players_db_dict):
    norm_first = first_name.strip().title()
    norm_last = last_name.strip().title()
    if not norm_first or not norm_last: return None
    last_initials = ''.join(norm_last.split())[:3].upper().ljust(3, 'X')
    first_initials = ''.join(norm_first.split())[:2].upper().ljust(2, 'X')
    base_id = f"{last_initials}{first_initials}"
    if not base_id or base_id == "XXXXX": base_id = "PLYYR" # Fallback estremo
    count = 1
    new_id = f"{base_id}{count:03d}"
    while new_id in players_db_dict:
        count += 1
        new_id = f"{base_id}{count:03d}"
        if count > 999: # Limite teorico
            new_id = f"{base_id}{datetime.now().strftime('%S%f')[-4:]}" # Fallback con timestamp
            if new_id in players_db_dict: return None # Fallimento definitivo
            break
    return new_id

def find_players_partial(search_term, players_db_dict):
    matches = []
    search_lower = search_term.strip().lower()
    if not search_lower: return matches
    for p_data in players_db_dict.values():
        if search_lower in p_data.get('first_name', '').lower() or \
           search_lower in p_data.get('last_name', '').lower() or \
           search_lower == p_data.get('id','').lower(): # Aggiunta ricerca per ID
            matches.append(p_data)
    return matches

def display_player_details(player_data):
    print("\n--- Scheda Giocatore ---")
    if not player_data: print("Dati non validi."); return
    print(f"{'ID':<20}: {player_data.get('id', 'N/D')}")
    print(f"{'Nome':<20}: {player_data.get('first_name', 'N/D')}")
    print(f"{'Cognome':<20}: {player_data.get('last_name', 'N/D')}")
    print(f"{'Elo Corrente':<20}: {player_data.get('current_elo', 'N/D')}")
    print(f"{'Data Nascita':<20}: {format_date_locale(player_data.get('birth_date'))}")
    print(f"{'Data Registrazione':<20}: {format_date_locale(player_data.get('registration_date'))}")
    print(f"{'Partite Giocate':<20}: {player_data.get('games_played', 0)}")
    medals = player_data.get('medals', {})
    print(f"{'Medagliere':<20}: Oro: {medals.get('gold',0)}, Argento: {medals.get('silver',0)}, Bronzo: {medals.get('bronze',0)}, Legno: {medals.get('wood',0)}")
    tournaments = player_data.get('tournaments_played', [])
    print(f"{'Tornei Giocati':<20}: {len(tournaments)}")
    if tournaments:
        print("  Storico Tornei:")
        try:
            tournaments_sorted = sorted(tournaments, key=lambda t: datetime.strptime(t.get('date_completed', '1900-01-01'), DATE_FORMAT_ISO), reverse=True)
        except: tournaments_sorted = tournaments
        for i, t_rec in enumerate(tournaments_sorted):
            print(f"    {i+1}. {format_rank_ordinal(t_rec.get('rank', '?'))} in '{t_rec.get('tournament_name', 'N/D')}' ({format_date_locale(t_rec.get('date_started'))} - {format_date_locale(t_rec.get('date_completed'))})")
    print("------------------------")

def add_new_player(players_db_dict):
    print("\n--- Aggiunta Nuovo Giocatore ---")
    first_name = dgt("Nome: ", kind="s", smin=1, smax=50)
    if not first_name: return False
    last_name = dgt("Cognome: ", kind="s", smin=1, smax=50)
    if not last_name: return False
    
    elo_val = dgt("Elo Corrente (0-3500): ", kind="f", fmin=0, fmax=3500, default=DEFAULT_ELO)

    birth_date_str = None
    while True:
        bdate_input = dgt("Data di nascita (AAAA-MM-GG, o lascia vuoto): ", kind="s", smax=10, default="")
        if not bdate_input: break
        try:
            datetime.strptime(bdate_input, DATE_FORMAT_ISO)
            birth_date_str = bdate_input
            break
        except ValueError: print("Formato data non valido.")

    new_id = generate_player_id(first_name, last_name, players_db_dict)
    if new_id is None:
        print("ERRORE: Impossibile generare ID. Aggiunta annullata.")
        return False

    new_player = {
        "id": new_id, "first_name": first_name.title(), "last_name": last_name.title(),
        "current_elo": elo_val, "registration_date": datetime.now().strftime(DATE_FORMAT_ISO),
        "birth_date": birth_date_str, "games_played": 0,
        "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
        "tournaments_played": []
    }
    players_db_dict[new_id] = new_player
    print(f"Giocatore '{new_player['first_name']} {new_player['last_name']}' aggiunto con ID {new_id}.")
    display_player_details(new_player)
    return True

def edit_player_data(player_id, players_db_dict):
    if player_id not in players_db_dict:
        print(f"Errore: Giocatore con ID {player_id} non trovato.")
        return False, player_id # Ritorna False e l'ID originale

    player_data = players_db_dict[player_id]
    original_id = player_data['id']
    original_first_name = player_data.get('first_name')
    original_last_name = player_data.get('last_name')

    print(f"\n--- Modifica Giocatore ID: {original_id} ---")
    
    new_first_name = dgt("Nome: ", kind="s", smin=1, smax=50, default=original_first_name).title()
    new_last_name = dgt("Cognome: ", kind="s", smin=1, smax=50, default=original_last_name).title()

    id_changed = False
    new_id = original_id
    if new_first_name != original_first_name or new_last_name != original_last_name:
        print("Nome o cognome modificati. Tentativo di rigenerare l'ID...")
        candidate_new_id = generate_player_id(new_first_name, new_last_name, players_db_dict)
        if candidate_new_id and candidate_new_id != original_id:
            if candidate_new_id in players_db_dict:
                print(f"ATTENZIONE: Il nuovo ID generato '{candidate_new_id}' è già in uso da un altro giocatore. "
                      "Le modifiche a nome/cognome non cambieranno l'ID per evitare conflitti.")
            else:
                new_id = candidate_new_id
                id_changed = True
                print(f"ID giocatore aggiornato da '{original_id}' a '{new_id}'.")
        elif not candidate_new_id:
            print("Errore nella generazione del nuovo ID. L'ID originale verrà mantenuto.")
    
    player_data['first_name'] = new_first_name
    player_data['last_name'] = new_last_name
    
    player_data['current_elo'] = dgt("Elo Corrente (0-3500): ", kind="f", fmin=0, fmax=3500, default=player_data.get('current_elo', DEFAULT_ELO))
    
    while True:
        bdate_input = dgt("Data di nascita (AAAA-MM-GG, vuoto per non modificare/cancellare)", kind="s", smax=10, default=player_data.get('birth_date', ""))
        if not bdate_input:
            if player_data.get('birth_date') and dgt(f"Cancellare data nascita '{player_data.get('birth_date')}'? (s/N)", kind="s", smax=1, default="n").lower() == 's':
                player_data['birth_date'] = None
            break
        try:
            datetime.strptime(bdate_input, DATE_FORMAT_ISO)
            player_data['birth_date'] = bdate_input
            break
        except ValueError: print("Formato data non valido.")

    print("\n--- Modifica Medagliere ---")
    medals = player_data.setdefault('medals', {'gold': 0, 'silver': 0, 'bronze': 0, 'wood': 0})
    for m_key in ['gold', 'silver', 'bronze', 'wood']:
        medals[m_key] = dgt(f"Medaglie di {m_key.capitalize()}: ", kind="i", imin=0, imax=999, default=medals.get(m_key, 0))

    print("\n--- Modifica Storico Tornei ---")
    tournaments = player_data.setdefault('tournaments_played', [])
    while True:
        print("\nTornei registrati:")
        if not tournaments:
            print("  Nessun torneo registrato.")
        else:
            for i, t in enumerate(tournaments):
                print(f"  {i+1}. {format_rank_ordinal(t.get('rank'))} '{t.get('tournament_name')}' ({format_date_locale(t.get('date_started'))} - {format_date_locale(t.get('date_completed'))})")
        
        op = dgt("Operazione Tornei: (A)ggiungi, (M)odifica, (C)ancella, (F)ine: ", kind="s", smax=1, default="f").lower()
        if op == 'f': break

        if op == 'a':
            print("Aggiunta nuovo torneo:")
            t_name = dgt("Nome torneo: ", kind="s", smin=1, smax=100)
            if not t_name: continue
            t_rank_str = dgt("Posizione? (es. 1, 2, o RIT = ritirato): ", kind="s", smax=10)
            t_rank = t_rank_str # Mantiene RIT come stringa, altrimenti prova a convertire
            if t_rank_str.upper() != "RIT":
                try: t_rank = int(t_rank_str)
                except ValueError: t_rank = "?"
            
            t_ds = None
            while not t_ds:
                ds_str = dgt("Data inizio torneo (AAAA-MM-GG): ", kind="s", smax=10)
                try: datetime.strptime(ds_str, DATE_FORMAT_ISO); t_ds = ds_str; break
                except ValueError: print("Formato data non valido.")
            
            t_dc = None
            while not t_dc:
                dc_str = dgt("Data fine torneo (AAAA-MM-GG): ", kind="s", smax=10)
                try: 
                    dt_dc = datetime.strptime(dc_str, DATE_FORMAT_ISO)
                    if datetime.strptime(t_ds, DATE_FORMAT_ISO) > dt_dc:
                        print("Data fine non può essere prima della data inizio.")
                        continue
                    t_dc = dc_str; break
                except ValueError: print("Formato data non valido.")

            tournaments.append({"tournament_name": t_name, "rank": t_rank, "date_started": t_ds, "date_completed": t_dc})
            print("Torneo aggiunto.")

        elif op == 'm' and tournaments:
            idx_str = dgt(f"Numero torneo da modificare (1-{len(tournaments)}): ", kind="s", smax=2)
            try:
                idx = int(idx_str) - 1
                if 0 <= idx < len(tournaments):
                    t_edit = tournaments[idx]
                    print(f"Modifica torneo: {t_edit.get('tournament_name')}")
                    t_edit['tournament_name'] = dgt("Nome torneo", kind="s", smin=1, smax=100, default=t_edit.get('tournament_name'))
                    
                    rank_default = str(t_edit.get('rank', '?'))
                    t_rank_str = dgt("Rank (es. 1, 2, RIT)", kind="s", smax=10, default=rank_default)
                    t_edit['rank'] = t_rank_str
                    if t_rank_str.upper() != "RIT":
                        try: t_edit['rank'] = int(t_rank_str)
                        except ValueError: t_edit['rank'] = "?"

                    ds_default = t_edit.get('date_started','')
                    while True:
                        ds_str = dgt("Data inizio (AAAA-MM-GG): ", kind="s", smax=10, default=ds_default)
                        try: datetime.strptime(ds_str, DATE_FORMAT_ISO); t_edit['date_started'] = ds_str; break
                        except ValueError: print("Formato data non valido.")
                    
                    dc_default = t_edit.get('date_completed','')
                    while True:
                        dc_str = dgt("Data fine (AAAA-MM-GG): ", kind="s", smax=10, default=dc_default)
                        try: 
                            dt_dc = datetime.strptime(dc_str, DATE_FORMAT_ISO)
                            if datetime.strptime(t_edit['date_started'], DATE_FORMAT_ISO) > dt_dc:
                                print("Data fine non può essere prima della data inizio.")
                                continue
                            t_edit['date_completed'] = dc_str; break
                        except ValueError: print("Formato data non valido.")
                    print("Torneo modificato.")
                else: print("Numero torneo non valido.")
            except ValueError: print("Input non numerico.")

        elif op == 'c' and tournaments:
            idx_str = dgt(f"Numero torneo da cancellare (1-{len(tournaments)}): ", kind="s", smax=2)
            try:
                idx = int(idx_str) - 1
                if 0 <= idx < len(tournaments):
                    removed_t = tournaments.pop(idx)
                    print(f"Torneo '{removed_t.get('tournament_name')}' cancellato.")
                else: print("Numero torneo non valido.")
            except ValueError: print("Input non numerico.")

    if id_changed:
        print(f"Applicazione modifiche ID: da {original_id} a {new_id}")
        # Rimuovi il vecchio record e aggiungi/aggiorna con il nuovo ID
        # player_data ora contiene tutti i dati aggiornati, incluso il nuovo ID se generato
        player_data['id'] = new_id # Assicura che l'ID nel dizionario sia quello nuovo
        del players_db_dict[original_id]
        players_db_dict[new_id] = player_data
        
    print("\nDati giocatore aggiornati.")
    display_player_details(player_data)
    return True, new_id # Ritorna successo e il (potenzialmente nuovo) ID

# --- Main Loop ---
def main_interactive_loop(players_db):
    print("\n" + "="*40 + "\n--- Gestore Database Giocatori Tornello ---")
    active_player_id = None # Per mantenere l'ID corrente in caso di modifica ID

    while True:
        print("\n" + "="*40)
        print(f"Giocatori nel database: {len(players_db)}")
        search_prompt = "ID, nome, cognome o vuoto: "
        if active_player_id and active_player_id in players_db: # Se un giocatore è stato appena modificato con cambio ID
             search_prompt = f"Cerca giocatore (ID, nome/cognome) [ID prec: {active_player_id}] o vuoto per uscire"
        
        search_input = dgt(search_prompt, kind="s", smax=100, default="").strip()
        active_player_id = None # Resetta l'ID attivo dopo ogni ricerca

        if not search_input: break 

        found_players = find_players_partial(search_input, players_db)

        if not found_players:
            print(f"Nessun giocatore trovato per '{search_input}'.")
            if dgt("Vuoi aggiungere un nuovo giocatore? (S/n) ", kind="s", smax=1, default="s").lower() == 's':
                if add_new_player(players_db): save_players_db(players_db)
            continue

        elif len(found_players) == 1:
            player_to_manage = found_players[0]
            current_player_id_for_ops = player_to_manage['id'] # ID prima di eventuali modifiche
            display_player_details(player_to_manage)
            
            action = dgt("Azione: (O)k, (C)ancella, (E)dita", kind="s", smax=1, default="o").lower()

            if action == 'o': continue
            elif action == 'c':
                if dgt(f"Sicuro di cancellare {player_to_manage.get('first_name')} {player_to_manage.get('last_name')} (ID: {current_player_id_for_ops})? (s/N): ", kind="s", smax=1, default="n").lower() == 's':
                    try:
                        del players_db[current_player_id_for_ops]
                        print("Giocatore cancellato.")
                        save_players_db(players_db)
                    except KeyError: print(f"ERRORE: Giocatore ID {current_player_id_for_ops} non trovato.")
                else: print("Cancellazione annullata.")
            elif action == 'e':
                success, resulting_id = edit_player_data(current_player_id_for_ops, players_db)
                if success:
                    active_player_id = resulting_id # Salva l'ID risultante per il prossimo prompt
                    save_players_db(players_db)
            else: print("Azione non riconosciuta.")
            
        else: # len(found_players) > 1
            print(f"\nTrovate {len(found_players)} corrispondenze per '{search_input}'. Specifica meglio (es. usando l'ID):")
            found_players.sort(key=lambda p: (p.get('last_name','').lower(), p.get('first_name','').lower()))
            for i, p_match in enumerate(found_players, 1):
                print(f"  {i}. ID: {p_match.get('id', 'N/D'):<9} - {p_match.get('first_name', 'N/D')} {p_match.get('last_name', 'N/D')} (Elo: {p_match.get('current_elo', 'N/D')})")
            
    print("\nSalvataggio finale del database...")
    save_players_db(players_db)
    print("Uscita dal gestore database giocatori.")

if __name__ == "__main__":
    db = load_players_db()
    main_interactive_loop(db)