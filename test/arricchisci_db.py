import json
import os
from datetime import datetime

PLAYER_DB_FILE = "tornello - giocatori_db.json" # Assicurati che sia il nome corretto
DATE_FORMAT_DB = "%Y-%m-%d" # Formato data che vogliamo nel DB JSON (consigliato)
DATE_FORMAT_TRF_DISPLAY = "%Y/%m/%d" # Formato FIDE TRF per la visualizzazione/guida input

def load_players_db_list():
    """Carica il database dei giocatori come lista di dizionari."""
    if os.path.exists(PLAYER_DB_FILE):
        try:
            with open(PLAYER_DB_FILE, "r", encoding='utf-8') as f:
                db_content = json.load(f)
                if isinstance(db_content, dict): 
                    return list(db_content.values())
                elif isinstance(db_content, list): 
                    return db_content
                else:
                    print(f"Formato DB sconosciuto in {PLAYER_DB_FILE}. Attesa lista di dizionari.")
                    return None
        except (json.JSONDecodeError, IOError) as e:
            print(f"Errore durante il caricamento del DB giocatori ({PLAYER_DB_FILE}): {e}")
            return None
    else:
        print(f"File DB giocatori '{PLAYER_DB_FILE}' non trovato.")
        return None

def save_players_db_list(players_list):
    """Salva la lista dei giocatori nel file JSON."""
    try:
        with open(PLAYER_DB_FILE, "w", encoding='utf-8') as f:
            json.dump(players_list, f, indent=4, ensure_ascii=False)
        print(f"Database giocatori salvato in '{PLAYER_DB_FILE}'.")
    except IOError as e:
        print(f"Errore durante il salvataggio del DB giocatori ({PLAYER_DB_FILE}): {e}")

def get_input_with_default(prompt_message, default_value=""):
    """Chiede un input all'utente, mostrando un valore di default."""
    # Assicura che default_value sia una stringa per il prompt
    default_display = str(default_value) if default_value is not None else ""
    if default_display:
        return input(f"{prompt_message} [{default_display}]: ").strip() or default_display
    else:
        return input(f"{prompt_message}: ").strip()

def main_enrich_db():
    players_list = load_players_db_list()

    if players_list is None:
        return

    print(f"\tTrovati {len(players_list)} giocatori nel database. Inizio arricchimento...\n")
    
    updated_players_list = []
    db_was_modified_overall = False # Traccia se sono state fatte modifiche (arricchimento o pulizia)

    for player_dict in players_list:
        player_id_display = player_dict.get('id', 'N/D')
        player_name_display = f"{player_dict.get('first_name', '')} {player_dict.get('last_name', '')}"
        print(f"--- Giocatore: {player_name_display} (ID: {player_id_display}) ---")
        
        current_player_data_changed_in_enrichment = False # Traccia modifiche per singolo giocatore in questa fase

        # 1. Titolo FIDE (fide_title)
        current_title = player_dict.get('fide_title', '')
        current_elo_for_prompt = player_dict.get('current_elo', 'N/A')
        new_title_input = get_input_with_default(f"  Titolo FIDE (Elo: {current_elo_for_prompt}, es. FM, WGM, vuoto se nessuno)", current_title).upper()
        new_title_processed = new_title_input[:3] 
        if player_dict.get('fide_title') != new_title_processed:
            player_dict['fide_title'] = new_title_processed
            current_player_data_changed_in_enrichment = True
        player_dict.setdefault('fide_title', '')

        # 2. Sesso (sex)
        current_sex = player_dict.get('sex', '')
        new_sex_input = ""
        while True:
            new_sex_input = get_input_with_default(f"  Sesso (m/w)", current_sex).lower()
            if new_sex_input in ['m', 'w', '']:
                break
            print("    Input non valido. Inserisci 'm' o 'w' o lascia vuoto per mantenere/cancellare.")
        final_sex = new_sex_input if new_sex_input else current_sex 
        if not final_sex: final_sex = 'm' 
        if player_dict.get('sex') != final_sex:
            player_dict['sex'] = final_sex
            current_player_data_changed_in_enrichment = True
        player_dict.setdefault('sex', 'm')

        # 3. Federazione Giocatore (federation)
        current_federation = player_dict.get('federation', 'ITA') 
        new_federation_input = get_input_with_default(f"  Federazione (codice 3 lettere, es. ITA)", current_federation).strip().upper() # Aggiunto strip()
        new_federation_processed = new_federation_input[:3] if new_federation_input else current_federation
        if not new_federation_processed: new_federation_processed = 'ITA'
        if player_dict.get('federation') != new_federation_processed:
            player_dict['federation'] = new_federation_processed
            current_player_data_changed_in_enrichment = True
        player_dict.setdefault('federation', 'ITA')

        # 4. FIDE ID Numerico (fide_id_num_str)
        current_fide_id_num = player_dict.get('fide_id_num_str', '0') 
        new_fide_id_num_input = get_input_with_default(f"  ID FIDE Numerico (cifre; '0' se N/D)", current_fide_id_num).strip() # Aggiunto strip()
        new_fide_id_processed = new_fide_id_num_input if new_fide_id_num_input else current_fide_id_num
        if not new_fide_id_processed.isdigit():
            print(f"    ID FIDE '{new_fide_id_processed}' non numerico, impostato a '0'.")
            new_fide_id_processed = '0'
        if player_dict.get('fide_id_num_str') != new_fide_id_processed:
            player_dict['fide_id_num_str'] = new_fide_id_processed
            current_player_data_changed_in_enrichment = True
        player_dict.setdefault('fide_id_num_str', '0')
            
        # 5. Data di Nascita (birth_date) - formato YYYY-MM-DD nel DB
        original_birth_date_from_db = player_dict.get('birth_date') 
        current_birth_date_for_ops = original_birth_date_from_db if original_birth_date_from_db is not None else ''
        default_for_prompt = current_birth_date_for_ops 

        if current_birth_date_for_ops and '/' in current_birth_date_for_ops and len(current_birth_date_for_ops) == 10:
            try:
                dt_obj = datetime.strptime(current_birth_date_for_ops, DATE_FORMAT_TRF_DISPLAY)
                converted_to_db_format = dt_obj.strftime(DATE_FORMAT_DB)
                print(f"    Data nascita '{current_birth_date_for_ops}' rilevata con '/', proposta come default: {converted_to_db_format}")
                default_for_prompt = converted_to_db_format
            except ValueError:
                print(f"    Formato data '{current_birth_date_for_ops}' con '/' non valido. Richiesto input manuale.")
                default_for_prompt = "" 

        new_birth_date_input = ""
        valid_date_entered = False
        while not valid_date_entered:
            new_birth_date_input = get_input_with_default(f"  Data Nascita ({DATE_FORMAT_DB})", default_for_prompt)
            if not new_birth_date_input: 
                final_birth_date_to_set = None if not default_for_prompt else default_for_prompt
                if player_dict.get('birth_date') != final_birth_date_to_set :
                     player_dict['birth_date'] = final_birth_date_to_set
                     current_player_data_changed_in_enrichment = True
                valid_date_entered = True
            else:
                try:
                    datetime.strptime(new_birth_date_input, DATE_FORMAT_DB) 
                    if player_dict.get('birth_date') != new_birth_date_input:
                        player_dict['birth_date'] = new_birth_date_input
                        current_player_data_changed_in_enrichment = True
                    valid_date_entered = True
                except ValueError:
                    print(f"    Formato data non valido. Usa {DATE_FORMAT_DB} o lascia vuoto.")
                    default_for_prompt = "" 

        if current_player_data_changed_in_enrichment:
            db_was_modified_overall = True # Segna che c'è stata almeno una modifica
            print("    Dati per questo giocatore aggiornati/arricchiti.")
        else:
            print("    Nessuna modifica ai dati di arricchimento per questo giocatore.")
        updated_players_list.append(player_dict)
        print("---") 
    # --- Fine Loop Arricchimento ---

    # --- INIZIO NUOVA SEZIONE: Pulizia Campi Obsoleti ---
    print("\nInizio pulizia campi obsoleti dal database...")
    obsolete_keys = [
        "white_games", "black_games", "last_color", 
        "consecutive_white", "consecutive_black", 
        "downfloat_count", 
        "opponents", # Se era un set/lista generico a livello di giocatore DB
        "received_bye" # Il vecchio campo booleano
        # Aggiungi qui altri campi specifici che sai essere obsoleti nel tuo DB
    ]
    
    cleaned_players_count = 0
    fields_removed_count = 0

    # Iteriamo su updated_players_list che contiene tutti i record (arricchiti o meno)
    for player_dict_to_clean in updated_players_list:
        player_had_obsolete_fields = False
        for key_to_remove in obsolete_keys:
            if key_to_remove in player_dict_to_clean:
                del player_dict_to_clean[key_to_remove]
                print(f"    Rimosso campo obsoleto '{key_to_remove}' da giocatore {player_dict_to_clean.get('id', 'N/D')}")
                fields_removed_count += 1
                player_had_obsolete_fields = True
        if player_had_obsolete_fields:
            cleaned_players_count +=1
            db_was_modified_overall = True # Segna che il DB è stato modificato anche dalla pulizia

    if fields_removed_count > 0:
        print(f"\nPulizia completata: {fields_removed_count} campi obsoleti rimossi da {cleaned_players_count} giocatori.")
    else:
        print("\nNessun campo obsoleto trovato da rimuovere.")
    # --- FINE NUOVA SEZIONE: Pulizia Campi Obsoleti ---

    if db_was_modified_overall: # Se ci sono state modifiche (arricchimento o pulizia)
        print("\nIl database dei giocatori è stato modificato.")
        conferma_salvataggio = input("Vuoi salvare le modifiche al file? (S/n): ").strip().lower()
        if conferma_salvataggio == 's' or conferma_salvataggio == '':
            save_players_db_list(updated_players_list) # Salva la lista che potrebbe essere stata modificata
        else:
            print("Modifiche NON salvate.")
    else:
        print("\nNessuna modifica apportata al database dei giocatori durante questa sessione.")

if __name__ == "__main__":
    # Ricorda di definire DATE_FORMAT_TRF_DISPLAY se non è già globale, 
    # o passala come argomento se preferisci non averla globale nello script.
    # Per questo script one-shot, va bene anche definirla qui se serve solo a main_enrich_db
    DATE_FORMAT_TRF_DISPLAY = "%Y/%m/%d" 
    main_enrich_db()