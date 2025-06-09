# Salva questo come imposta_esperienza_giocatori.py
# nella stessa cartella di tornello - giocatori_db.json

import json
import os

PLAYER_DB_FILE = "tornello - giocatori_db.json" 

def load_players_db_list_for_tool():
    """Carica il database dei giocatori come lista di dizionari."""
    if os.path.exists(PLAYER_DB_FILE):
        try:
            with open(PLAYER_DB_FILE, "r", encoding='utf-8') as f:
                db_content = json.load(f)
                # Gestisce sia il caso in cui il DB sia una lista, sia un dizionario di giocatori
                if isinstance(db_content, dict):
                    return list(db_content.values()) 
                elif isinstance(db_content, list):
                    return db_content
                else:
                    print(f"ERRORE: Formato DB sconosciuto in {PLAYER_DB_FILE}. Attesa lista o dizionario.")
                    return None
        except (json.JSONDecodeError, IOError) as e:
            print(f"Errore durante il caricamento del DB giocatori ({PLAYER_DB_FILE}): {e}")
            return None
    else:
        print(f"File DB giocatori '{PLAYER_DB_FILE}' non trovato.")
        return None

def save_players_db_list_for_tool(players_list_to_save):
    """Salva la lista dei giocatori nel file JSON."""
    try:
        with open(PLAYER_DB_FILE, "w", encoding='utf-8') as f:
            json.dump(players_list_to_save, f, indent=4, ensure_ascii=False)
        print(f"Database giocatori aggiornato e salvato in '{PLAYER_DB_FILE}'.")
    except IOError as e:
        print(f"Errore durante il salvataggio del DB giocatori ({PLAYER_DB_FILE}): {e}")

def main_set_player_experience():
    players_list = load_players_db_list_for_tool()

    if players_list is None:
        print("Operazione annullata.")
        return

    if not players_list:
        print("Il database dei giocatori è vuoto. Nulla da aggiornare.")
        return

    print(f"\Trovati {len(players_list)} giocatori. Verrà chiesto di impostare il campo 'experienced'.")
    print("Rispondi 's' se il giocatore ha esperienza pregressa significativa, 'n' altrimenti.")
    
    modifications_count = 0

    for player_record in players_list: # player_record è un dizionario
        player_name = f"{player_record.get('first_name', 'Sconosciuto')} {player_record.get('last_name', 'Sconosciuto')}"
        player_id = player_record.get('id', 'N/D')
        
        current_experience_value = player_record.get('experienced') # Potrebbe essere True, False, o None (se la chiave non esiste)
        
        prompt_default_display = ""
        if current_experience_value is True:
            prompt_default_display = " (Attuale: Sì)"
        elif current_experience_value is False:
            prompt_default_display = " (Attuale: No)"
        # Se current_experience_value è None, nessun "Attuale" verrà mostrato.

        new_experience_bool = None
        while True:
            user_input = input(f"Giocatore: {player_name} (ID: {player_id}). Ha esperienza?{prompt_default_display} (s/n): ").strip().lower()
            if user_input == 's':
                new_experience_bool = True
                break
            elif user_input == 'n':
                new_experience_bool = False
                break
            # Se l'input è vuoto e c'era un valore precedente, potremmo decidere di mantenerlo.
            # Ma per un tool one-shot "semplicissimo", forzare 's' o 'n' è più diretto.
            # Se vuoi che l'invio vuoto mantenga il valore esistente (se c'è) o imposti un default, 
            # la logica del prompt andrebbe leggermente cambiata.
            # Per ora, richiede una risposta 's' o 'n'.
            print("    Risposta non valida. Prego inserire 's' o 'n'.")
        
        # Aggiorna il record e conta se c'è stata una modifica o se il campo è stato aggiunto
        if player_record.get('experienced') != new_experience_bool:
            player_record['experienced'] = new_experience_bool
            modifications_count += 1
            print(f"    -> 'experienced' per {player_name} impostato a: {new_experience_bool}")
        else:
            # Anche se il valore è lo stesso, assicuriamoci che la chiave esista
            if 'experienced' not in player_record:
                 player_record['experienced'] = new_experience_bool # Aggiunge la chiave se mancava
                 if new_experience_bool is not None: # Conta come modifica se la chiave viene aggiunta
                    modifications_count +=1 
            print(f"    -> 'experienced' per {player_name} non modificato (valore attuale: {player_record.get('experienced')}).")

    if modifications_count > 0:
        print(f"\nSono stati aggiornati/impostati i campi 'experienced' per {modifications_count} giocatori.")
        confirm_save = input("Vuoi salvare le modifiche al database? (S/n): ").strip().lower()
        if confirm_save == 's' or confirm_save == '':
            save_players_db_list_for_tool(players_list)
        else:
            print("Modifiche non salvate.")
    else:
        print("\nNessuna modifica apportata al campo 'experienced' dei giocatori (o i valori erano già impostati).")

if __name__ == "__main__":
    main_set_player_experience()