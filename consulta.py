# Consulta il DB FIDE
# Estratto e riadattato da Tornello DEV
# Data: 22 settembre 2025
# Modificato in base alla richiesta del 2 ottobre 2025

import os
import json
import sys
import traceback
import io
import zipfile
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# --- Impostazioni e Costanti ---

# Nome del file locale dove salveremo il database FIDE in formato JSON
FIDE_DB_LOCAL_FILE = "fide_ratings_local.json"

# L'URL ufficiale da cui scaricare la lista giocatori FIDE
FIDE_XML_DOWNLOAD_URL = "http://ratings.fide.com/download/players_list_xml.zip"


# --- Funzioni Principali ---

def aggiorna_db_fide_locale():
    """
    Scarica l'ultimo rating list FIDE (XML), estrae i dati più importanti
    e li salva in un file JSON locale (fide_ratings_local.json).
    Restituisce True in caso di successo, False altrimenti.
    """
    try:
        print(f"Download del file ZIP FIDE da: {FIDE_XML_DOWNLOAD_URL}")
        print("L'operazione potrebbe richiedere alcuni minuti a seconda della connessione...")
        
        # Esegue la richiesta per scaricare il file .zip
        zip_response = requests.get(FIDE_XML_DOWNLOAD_URL, timeout=120)
        zip_response.raise_for_status() # Lancia un errore se il download fallisce

        print("Download completato. Apertura archivio ZIP in memoria...")
        # Apre il file .zip direttamente in memoria, senza salvarlo su disco
        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
            # Trova il nome del file .xml all'interno dello .zip
            xml_filename = next((name for name in zf.namelist() if name.lower().endswith('.xml')), None)
            
            if not xml_filename:
                print("ERRORE: Nessun file .xml trovato nell'archivio ZIP.")
                return False
            
            print(f"Estrazione ed elaborazione del file XML: {xml_filename}...")
            
            # Legge il contenuto del file XML
            xml_content = zf.read(xml_filename)
            
            print("Analisi del file XML in corso (potrebbe richiedere più di un minuto)...")
            
            fide_players_db = {}
            # Inizia l'analisi (parsing) del file XML
            root = ET.fromstring(xml_content)
            
            player_count = 0
            # Itera su ogni "player" trovato nel file XML
            for player_node in root.findall('player'):
                fide_id_node = player_node.find('fideid')
                
                if fide_id_node is not None and fide_id_node.text:
                    fide_id_str = fide_id_node.text.strip()
                    
                    # Estrae i dati che ci interessano
                    name = player_node.find('name').text
                    rating_std_node = player_node.find('rating')
                    flag_node = player_node.find('flag')

                    rating_std = int(rating_std_node.text) if rating_std_node is not None and rating_std_node.text else 0
                    
                    # Filtriamo i giocatori inattivi o senza rating standard, che sono meno rilevanti
                    if rating_std == 0 and (flag_node is not None and flag_node.text and 'i' in flag_node.text.lower()):
                        continue

                    # Separa il cognome dal nome
                    last_name_fide, first_name_fide = name, ""
                    if ',' in name:
                        parts = name.split(',', 1)
                        last_name_fide = parts[0].strip()
                        first_name_fide = parts[1].strip()

                    # Costruisce il dizionario del giocatore
                    fide_players_db[fide_id_str] = {
                        "id_fide": int(fide_id_str),
                        "first_name": first_name_fide,
                        "last_name": last_name_fide,
                        "federation": player_node.find('country').text,
                        "title": player_node.find('title').text or "",
                        "sex": player_node.find('sex').text or "",
                        "elo_standard": rating_std,
                        "elo_rapid": int(r.text) if (r := player_node.find('rapid_rating')) is not None and r.text else 0,
                        "elo_blitz": int(b.text) if (b := player_node.find('blitz_rating')) is not None and b.text else 0,
                        "k_factor": int(k.text) if (k := player_node.find('k')) is not None and k.text else None,
                        "flag": flag_node.text if flag_node is not None else None,
                        "birth_year": int(by.text) if (by := player_node.find('birthday')) is not None and by.text and by.text.isdigit() else None
                    }
                    player_count += 1
                    # Fornisce un feedback ogni 500.000 giocatori elaborati
                    if player_count % 500000 == 0:
                        print(f"   ... elaborati {player_count} giocatori...")

            print(f"Elaborazione completata. Trovati e salvati {len(fide_players_db)} giocatori FIDE.")
            
            print("Salvataggio del database JSON locale (potrebbe richiedere tempo)...")
            # Salva il grande dizionario in un file JSON
            with open(FIDE_DB_LOCAL_FILE, "w", encoding='utf-8') as f_out:
                json.dump(fide_players_db, f_out, indent=1)
                
            print(f"Database FIDE locale '{FIDE_DB_LOCAL_FILE}' salvato con successo.")
            return True # Restituisce True per indicare successo

    except requests.exceptions.Timeout:
        print("ERRORE: Timeout durante il download del file.")
        return False
    except requests.exceptions.RequestException as e_req:
        print(f"ERRORE di rete: {e_req}")
        return False
    except Exception as e_main:
        print(f"Si è verificato un errore imprevisto durante l'aggiornamento del DB FIDE: {e_main}")
        traceback.print_exc()
        return False


def cerca_giocatore_fide(search_term):
    """
    Cerca un giocatore nel DB FIDE locale per nome/cognome o ID FIDE.
    Restituisce una lista di record corrispondenti.
    """
    if not os.path.exists(FIDE_DB_LOCAL_FILE):
        return [] # Se il file non esiste, non c'è nulla da cercare
    try:
        with open(FIDE_DB_LOCAL_FILE, "r", encoding='utf-8') as f:
            fide_db = json.load(f)
    except (IOError, json.JSONDecodeError):
        return [] # Errore di lettura, restituisce lista vuota

    matches = []
    search_lower = search_term.strip().lower()
    search_is_id = search_term.strip().isdigit()

    # Se l'input è un numero e corrisponde a un ID FIDE, la ricerca è esatta e veloce
    if search_is_id and search_term.strip() in fide_db:
        matches.append(fide_db[search_term.strip()])
        return matches

    # Altrimenti, cerca il testo inserito nel nome completo di ogni giocatore
    for fide_id, player_data in fide_db.items():
        full_name = f"{player_data.get('first_name', '')} {player_data.get('last_name', '')}".lower()
        if search_lower in full_name:
            matches.append(player_data)

    return matches

# --- NUOVE FUNZIONI DI VISUALIZZAZIONE ---

def stampa_dettagli_giocatore(player):
    """
    Stampa i dati di un singolo giocatore in modo formattato e leggibile.
    Questa funzione centralizza la stampa dei dettagli.
    """
    print("-" * 30)
    for key, value in player.items():
        print(f"  {key.replace('_', ' ').capitalize():<15}: {value}")
    print("-" * 30)


def gestisci_risultati_con_pager(results):
    """
    Gestisce la visualizzazione di risultati multipli (da 4 a 100)
    con un sistema a pagine (pager).
    """
    start_index = 0
    num_results = len(results)

    while start_index < num_results:
        # Calcola l'indice di fine per la pagina corrente (massimo 10 risultati)
        end_index = min(start_index + 10, num_results)
        
        print("\n--- Pagina " + str(start_index // 10 + 1) + f" di { (num_results + 9) // 10 } ---")

        # Stampa il riepilogo per i giocatori nella pagina corrente
        for i in range(start_index, end_index):
            player = results[i]
            progressivo = i + 1
            nome_completo = f"{player.get('first_name', '')} {player.get('last_name', '')}"
            # Usiamo .get(key, 'N/D') per evitare errori se un dato manca
            elo_std = player.get('elo_standard', 'N/D')
            elo_rapid = player.get('elo_rapid', 'N/D')
            anno = player.get('birth_year', 'N/D')
            nazione = player.get('federation', 'N/D')
            
            # Formattiamo la riga di riepilogo
            print(f"{progressivo:>3}. {nome_completo:<30} | Elo Std: {elo_std:<4} | Elo Rapid: {elo_rapid:<4} | Anno: {anno:<4} | Naz: {nazione}")
        
        # Chiede all'utente cosa fare
        prompt = "\nInserisci il numero del giocatore per vederne i dettagli,\no premi Invio per la pagina successiva (q per tornare alla ricerca): "
        user_choice = input(prompt).strip()

        if not user_choice:  # L'utente ha premuto Invio
            start_index += 10
            if start_index >= num_results:
                print("Fine dei risultati.")
                break # Esce dal ciclo del pager
        elif user_choice.lower() == 'q':
             print("Torno alla ricerca...")
             break # Esce dal ciclo del pager
        elif user_choice.isdigit():
            choice_index = int(user_choice)
            if 1 <= choice_index <= num_results:
                # L'utente ha scelto un giocatore valido, mostriamo i dettagli
                print(f"\n--- Dettagli per il giocatore #{choice_index} ---")
                stampa_dettagli_giocatore(results[choice_index - 1]) # -1 perché la lista parte da 0
                break # Esce dal ciclo del pager dopo aver mostrato i dettagli
            else:
                print(f"ERRORE: Inserisci un numero tra 1 e {num_results}.")
        else:
            print("ERRORE: Input non valido.")


def main():
    """
    Funzione principale che orchestra il funzionamento dello script.
    """
    print("--- FIDE Player Checker ---")
    print("Verifica stato database FIDE locale...")
    
    db_needs_update = False
    if not os.path.exists(FIDE_DB_LOCAL_FILE):
        print("\nIl database FIDE locale non è presente sul tuo computer.")
        db_needs_update = True
    else:
        try:
            # Controlla l'età del file
            file_mod_timestamp = os.path.getmtime(FIDE_DB_LOCAL_FILE)
            file_age = datetime.now() - datetime.fromtimestamp(file_mod_timestamp)
            file_age_days = file_age.days
            
            print(f"Info: Il tuo database FIDE locale ha {file_age_days} giorni.")
            if file_age_days >= 30:
                print("È più vecchio di 30 giorni e potrebbe essere obsoleto.")
                db_needs_update = True
        except Exception as e:
            print(f"Errore nel controllare la data del file DB FIDE locale: {e}")

    # Se il DB deve essere aggiornato, chiedi conferma all'utente
    if db_needs_update:
        user_choice = input("Vuoi scaricare/aggiornare il database ora? (s/n): ").strip().lower()
        if user_choice in ['s', 'si', 'y', 'yes', '']:
            aggiorna_db_fide_locale()
        else:
            if not os.path.exists(FIDE_DB_LOCAL_FILE):
                print("Impossibile procedere senza un database. Uscita.")
                sys.exit(0)

    print("\n--- Ricerca Giocatori ---")
    while True:
        search_term = input("Inserisci parte del nome/cognome o ID FIDE (o lascia vuoto per uscire): ")
        if not search_term:
            break # Esce dal ciclo se l'utente preme Invio

        results = cerca_giocatore_fide(search_term)
        num_results = len(results)

        # --- LOGICA DI VISUALIZZAZIONE MODIFICATA ---
        if num_results == 0:
            print(f"Nessun giocatore trovato per '{search_term}'.")
        
        elif num_results <= 3:
            print(f"\nTrovati {num_results} risultati per '{search_term}':")
            for player in results:
                stampa_dettagli_giocatore(player) # Uso la nuova funzione
        
        elif num_results > 100:
            print(f"\nTrovati {num_results} risultati. Sono troppi per essere visualizzati.")
            print("Prova con una chiave di ricerca più specifica.")
        
        else: # Da 4 a 100 risultati
            print(f"\nTrovati {num_results} risultati per '{search_term}'.")
            gestisci_risultati_con_pager(results) # Uso la nuova funzione per il pager
    
    print("\nGrazie per aver usato FIDE Player Checker. A presto!")


# --- Esecuzione dello Script ---

if __name__ == "__main__":
    main()