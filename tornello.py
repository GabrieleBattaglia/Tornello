# TORNELLO DEV
# Data concepimento: 28 marzo 2025
import os, json, sys, math, traceback, subprocess, glob, shutil, io, zipfile, threading, requests
import xml.etree.ElementTree as ET
from GBUtils import dgt, key, Donazione, polipo
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from babel.dates import format_date
# installazione percorsi relativi e i18n
def resource_path(relative_path):
    """
    Restituisce il percorso assoluto a una risorsa, funzionante sia in sviluppo
    che per un eseguibile compilato con PyInstaller (anche con la cartella _internal).
    """
    try:
        # PyInstaller crea una cartella temporanea e ci salva il percorso in _MEIPASS
        # Questo è il percorso base per le risorse quando l'app è "congelata"
        base_path = sys._MEIPASS
    except Exception:
        # Se _MEIPASS non esiste, non siamo in un eseguibile PyInstaller
        # o siamo in una build onedir, il percorso base è la cartella dello script
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

lingua_rilevata, _ = polipo(source_language="it")

# QCV Versione
VERSIONE = "8.6.8, 2025.07.29 by Gabriele Battaglia & Gemini 2.5 Pro\n\tusing BBP Pairings, a Swiss-system chess tournament engine created by Bierema Boyz Programming."

# QC File e Directory Principali (relativi all'eseguibile) ---
PLAYER_DB_FILE = resource_path("Tornello - Players_db.json")
PLAYER_DB_TXT_FILE = resource_path("Tornello - Players_db.txt")
ARCHIVED_TOURNAMENTS_DIR = resource_path("Closed Tournaments")
FIDE_DB_LOCAL_FILE = resource_path("fide_ratings_local.json")

# QC Costanti per l'integrazione con bbpPairings ---
BBP_SUBDIR = resource_path("bbppairings")
BBP_EXE_NAME = "bbpPairings.exe"
BBP_EXE_PATH = os.path.join(BBP_SUBDIR, BBP_EXE_NAME)
BBP_INPUT_TRF = os.path.join(BBP_SUBDIR, "input_bbp.trf")
BBP_OUTPUT_COUPLES = os.path.join(BBP_SUBDIR, "output_coppie.txt")
BBP_OUTPUT_CHECKLIST = os.path.join(BBP_SUBDIR, "output_checklist.txt")

# QC Costanti non di percorso ---
DATE_FORMAT_ISO = "%Y-%m-%d"
DEFAULT_ELO = 1399.0
DEFAULT_K_FACTOR = 20
FIDE_XML_DOWNLOAD_URL = "http://ratings.fide.com/download/players_list_xml.zip"

#QF

def enter_escape(prompt=""):
    '''Ritorna vero su invio, falso su escape'''
    while True:
        k=key(prompt).strip()
        if k == "":
            return True
        elif k == "\x1b":
            return False
        print(_("Conferma con invio o annulla con escape"))

def handle_bbpairings_failure(torneo, round_number, error_message):
    """
    Gestisce i fallimenti di bbpPairings. Stampa un messaggio e chiede all'utente cosa fare.
    Restituisce una stringa che indica l'azione scelta dall'utente ('time_machine' o 'terminate').
    """
    print(_("\n--- FALLIMENTO GENERAZIONE ABBINAMENTI AUTOMATICI (Turno {round_num}) ---").format(round_num=round_number))
    print(error_message)
    print(_("Causa: bbpPairings.exe non è riuscito a generare gli abbinamenti."))
    print(_("Azione richiesta: Verificare il file 'input_bbp.trf' nella sottocartella 'bbppairings' per possibili errori di formato."))
    print(_("Oppure, un risultato potrebbe essere stato inserito in modo errato nel turno precedente."))
    
    while True:
        prompt = _("\nCosa vuoi fare? (T)orna indietro con la Time Machine per correggere, (U)sci dal programma: ").format(round_num=round_number)
        choice = key(prompt).strip().lower()
        if choice == 't':
            return 'time_machine'
        elif choice == 'u':
            return 'terminate'
        else:
            print(_("Scelta non valida. Inserisci 't' o 'u'."))

def _cerca_giocatore_nel_db_fide(search_term):
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

    if search_is_id and search_term.strip() in fide_db:
        matches.append(fide_db[search_term.strip()])
        return matches

    for fide_id, player_data in fide_db.items():
        full_name = f"{player_data.get('first_name', '')} {player_data.get('last_name', '')}".lower()
        if search_lower in full_name:
            matches.append(player_data)

    return matches

def _ricalcola_stato_giocatore_da_storico(player_obj):
    """
    Azzera e ricalcola i punti e le statistiche di un giocatore
    basandosi sulla sua lista 'results_history'.
    Modifica direttamente l'oggetto giocatore passato.
    """
    # Azzera tutte le statistiche del torneo
    player_obj['points'] = 0.0
    player_obj['opponents'] = set()
    player_obj['white_games'] = 0
    player_obj['black_games'] = 0
    player_obj['last_color'] = None
    player_obj['consecutive_white'] = 0
    player_obj['consecutive_black'] = 0
    player_obj['received_bye_count'] = 0
    player_obj['received_bye_in_round'] = []
    # Ordina lo storico per assicurare un calcolo progressivo corretto
    history_sorted = sorted(player_obj.get("results_history", []), key=lambda x: x.get("round", 0))
    for result in history_sorted:
        player_obj['points'] += result.get('score', 0.0)
        opponent = result.get('opponent_id')
        if opponent == "BYE_PLAYER_ID":
            player_obj['received_bye_count'] += 1
            player_obj['received_bye_in_round'].append(result.get('round'))
        elif opponent:
            player_obj['opponents'].add(opponent)

        color = result.get('color')
        if color == 'white':
            player_obj['white_games'] += 1
            player_obj['last_color'] = 'white'
            player_obj['consecutive_white'] += 1
            player_obj['consecutive_black'] = 0
        elif color == 'black':
            player_obj['black_games'] += 1
            player_obj['last_color'] = 'black'
            player_obj['consecutive_black'] += 1
            player_obj['consecutive_white'] = 0

def time_machine_torneo(torneo):
    """
    Permette di riavvolgere il torneo a uno stato precedente, cancellando
    i risultati dei turni successivi a quello scelto.
    ORA CORREGGE ANCHE next_match_id e ricalcola i punti dei BYE.
    Restituisce True se il riavvolgimento è stato effettuato, False altrimenti.
    """
    current_round = torneo.get('current_round', 1)
    print(_("\n--- Time Machine ---"))
    print(_("Questa funzione ripristina lo stato del torneo a un turno precedente."))
    prompt_template_1 = _("Puoi tornare a un qualsiasi turno da 1 a {max_round}.")
    print(prompt_template_1.format(max_round=current_round))
    print(_("Tutti i risultati e gli abbinamenti successivi al turno scelto verranno cancellati."))
    try:
        prompt_template_2 = _("A quale turno vuoi tornare? (1-{max_round}, o vuoto per annullare): ")
        prompt_formatted = prompt_template_2.format(max_round=current_round)
        target_round_str = input(prompt_formatted).strip()
        if not target_round_str:
            print(_("Operazione annullata."))
            return False
        target_round = int(target_round_str)
        if not (1 <= target_round <= current_round):
            print(_("Numero di turno non valido."))
            return False
    except ValueError:
        print(_("Input non valido. Inserisci un numero."))
        return False
    print(_("\nATTENZIONE: Stai per eseguire un'operazione distruttiva."))
    prompt_template_3 = _("Verranno eliminati tutti i risultati e gli abbinamenti inseriti dal turno {target_round} in poi.")
    print(prompt_template_3.format(target_round=target_round))
    confirm = input(_("Sei assolutamente sicuro di voler procedere? (scrivi 'si' per confermare): ")).strip().lower()
    if confirm != 'si':
        print(_("Conferma non data. Operazione di riavvolgimento annullata."))
        return False
    prompt_template_4 = _("\nAvvio riavvolgimento al Turno {target_round}...")
    print(prompt_template_4.format(target_round=target_round))
    # Azzera lo stato futuro (rimuove i round >= target_round)
    torneo['rounds'] = [r for r in torneo.get('rounds', []) if r.get('round', 0) < target_round]
    for player in torneo.get('players', []):
        player['results_history'] = [res for res in player.get('results_history', []) if res.get('round', 0) < target_round]
        if player.get('withdrawn', False):
            player['withdrawn'] = False
        # Questa funzione azzererà i punti a 0 e li ricalcolerà dalla storia (ora ridotta)
        _ricalcola_stato_giocatore_da_storico(player)
    torneo['current_round'] = target_round

    # Ricalcola il prossimo ID partita
    max_id = 0
    for r in torneo.get('rounds', []):
        for m in r.get('matches', []):
            if m.get('id', 0) > max_id:
                max_id = m.get('id', 0)
    torneo['next_match_id'] = max_id + 1
    print(_("Contatore ID Partita ripristinato a: {}").format(torneo['next_match_id']))

    # <<< CORREZIONE 3: RIGENERAZIONE ABBINAMENTI PER IL TURNO DI DESTINAZIONE >>>
    print(_("Rigenerazione abbinamenti per il Turno {target_round}...").format(target_round=target_round))
    matches_new = generate_pairings_for_round(torneo)
    if matches_new is None:
        print("ERRORE CRITICO: fallita rigenerazione turno post time machine.")
        torneo['current_round'] = current_round 
        return False
    valore_bye_torneo = torneo.get('bye_value', 1.0) 
    for match in matches_new:
        if match.get("result") == "BYE":
            bye_player_id = match.get('white_player_id')
            player_obj = get_player_by_id(torneo, bye_player_id)
            if player_obj:
                player_obj['points'] = player_obj.get('points', 0.0) + valore_bye_torneo
                player_obj.setdefault("results_history", []).append({
                    "round": target_round, "opponent_id": "BYE_PLAYER_ID",
                    "color": None, "result": "BYE", "score": valore_bye_torneo
                })
                print(_("Ripristinato {score} punto/i per il BYE al Turno {round} per {name}.").format(score=valore_bye_torneo, round=target_round, name=player_obj.get('first_name')))
    
    # Aggiungiamo il nuovo set di abbinamenti alla lista dei round
    torneo.setdefault("rounds", []).append({"round": target_round, "matches": matches_new})
    
    # Ricostruisci il dizionario cache per coerenza
    torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    
    print(_("\nRiavvolgimento completato con successo!"))
    prompt_template_5 = _("Il torneo è ora al Turno {target_round}, pronto per l'inserimento dei risultati.")
    print(prompt_template_5.format(target_round=target_round))
    return True

def sincronizza_db_personale():
    """
    Carica il DB FIDE locale e il DB personale, li confronta, e propone
    aggiornamenti e associazioni di ID FIDE con un flusso di conferma completo e interattivo,
    rispettando le regole di precedenza per i dati locali.
    """
    if not os.path.exists(FIDE_DB_LOCAL_FILE):
        print(_("ERRORE: Database FIDE locale '{}' non trovato.").format(FIDE_DB_LOCAL_FILE))
        print(_("Esegui prima la funzione di aggiornamento del DB FIDE."))
        return
    print(_("\n--- Avvio Sincronizzazione Database Personale con Database FIDE Locale ---"))
    try:
        with open(FIDE_DB_LOCAL_FILE, "r", encoding='utf-8') as f:
            fide_db = json.load(f)
        print(_("Database FIDE locale caricato con {} giocatori.").format(len(fide_db)))
    except Exception as e:
        print(_("ERRORE critico durante la lettura di '{}': {}").format(FIDE_DB_LOCAL_FILE, e))
        return
    players_db = load_players_db()
    if not players_db:
        print(_("Il tuo database personale dei giocatori è vuoto. Nessuna sincronizzazione da effettuare."))
        return
    all_potential_changes = []
    
    print(_("Analisi dei giocatori nel tuo database personale..."))
    for player_id, local_player in players_db.items():
        fide_id_str = local_player.get('fide_id_num_str', '0')
        fide_record = None
        
        player_changes = {
            'player_id': player_id,
            'current_data': local_player,
            'new_fide_id': None,
            'updates': {}
        }
        
        # --- FASE 1: Trova una corrispondenza FIDE per il giocatore ---
        if fide_id_str and fide_id_str != '0':
            fide_record = fide_db.get(fide_id_str)
        else: # Se non c'è ID, cerca per nome/cognome per trovare una potenziale associazione
            p_first_name = local_player.get('first_name', '').lower()
            p_last_name = local_player.get('last_name', '').lower()
            
            if not p_first_name or not p_last_name: continue
            
            matches = [f_p for f_p in fide_db.values() if 
                       f_p.get('first_name', '').lower() == p_first_name and 
                       f_p.get('last_name', '').lower() == p_last_name]
            
            if len(matches) == 1:
                match = matches[0]
                print(_("\n-> Trovata una corrispondenza FIDE per il tuo giocatore '{} {}' (ID: {}):").format(local_player.get('first_name'), local_player.get('last_name'), player_id))
                print(_("   FIDE ID: {}, Nome: {}, {}, FED: {}, Elo: {}, Anno Nascita: {}").format(match['id_fide'], match['last_name'], match['first_name'], match['federation'], match['elo_standard'], match.get('birth_year')))
                if enter_escape(_("   Associare questo ID FIDE al tuo giocatore? (INVIO|ESCAPE)")):
                    player_changes['new_fide_id'] = str(match['id_fide'])
                    fide_record = match
            elif len(matches) > 1:
                print(_("\n-> Trovati {} omonimi nel DB FIDE per il tuo giocatore '{} {}' (ID: {}).").format(len(matches), local_player.get('first_name'), local_player.get('last_name'), player_id))
                print(_("   Seleziona l'ID FIDE corretto o 'n' per saltare:"))
                for i, match in enumerate(matches):
                    print(_(" {}. FIDE ID: {}, FED: {}, Elo: {}, Anno Nascita: {}").format(i + 1, match['id_fide'], match['federation'], match['elo_standard'], match.get('birth_year')))
                print(_("   n. Nessuno di questi"))
                choice = input(_(_("   Scelta: "))).strip().lower()
                if choice.isdigit() and 1 <= int(choice) <= len(matches):
                    chosen_match = matches[int(choice) - 1]
                    player_changes['new_fide_id'] = str(chosen_match['id_fide'])
                    fide_record = chosen_match
                else:
                    print(_("   Scelta non valida o saltata. Il giocatore non verrà associato."))
        # --- FASE 2: Se abbiamo un record FIDE (trovato tramite ID o tramite associazione), controlla gli aggiornamenti ---
        if fide_record:
            updates = {}
            # 1. Elo Standard: si aggiorna sempre se diverso
            fide_elo = fide_record.get('elo_standard', 0)
            if fide_elo > 0 and fide_elo != local_player.get('current_elo'):
                updates['current_elo'] = fide_elo
            
            # 2. Titolo FIDE: si aggiorna solo se il campo locale è vuoto
            fide_title = fide_record.get('title', '')
            if fide_title and not local_player.get('fide_title'):
                updates['fide_title'] = fide_title

            # 3. K-Factor: si aggiorna sempre, perché il dato FIDE è prioritario
            fide_k = fide_record.get('k_factor')
            if fide_k is not None and fide_k != local_player.get('fide_k_factor'):
                updates['fide_k_factor'] = fide_k

            # 4. Data di nascita: si aggiorna solo se il campo locale è vuoto e la FIDE fornisce l'anno
            fide_birth_year = fide_record.get('birth_year')
            if fide_birth_year and not local_player.get('birth_date'):
                updates['birth_date'] = f"{fide_birth_year}-01-01"

            player_changes['updates'] = updates
        
        if player_changes['new_fide_id'] or player_changes['updates']:
            all_potential_changes.append(player_changes)
    
    # --- FASE 3: Riepilogo e Conferma Finale Interattiva ---
    if not all_potential_changes:
        print(_("\nAnalisi completata. Il tuo database personale è già perfettamente sincronizzato!"))
        return
    print(_("\n--- Riepilogo Sincronizzazione: Trovate {} modifiche proposte ---").format(len(all_potential_changes)))
    for change in all_potential_changes[:3]:
        player = change['current_data']
        print(_(" - Giocatore: {} {} (ID Locale: {})").format(player.get('first_name'), player.get('last_name'), player.get('id')))
        if change['new_fide_id']:
            print(_("    -> Associazione nuovo ID FIDE: {}").format(change['new_fide_id']))
        if change['updates']:
            for key, value in change['updates'].items():
                print(_("    -> Aggiornamento {}: da '{}' a '{}'").format(key.replace('_',' ').title(), player.get(key), value))

    if len(all_potential_changes) > 3:
        if enter_escape(_("\nVuoi vedere l'elenco completo di tutte le modifiche proposte? (INVIO|ESCAPE)")) == 's':
            print(_("\n--- Elenco Completo Modifiche Proposte ---"))
            for change in all_potential_changes: # Mostra tutti
                 player = change['current_data']
                 print(_("  - Giocatore: {} {} (ID Locale: {})").format(player.get('first_name'), player.get('last_name'), player.get('id')))
                 if change['new_fide_id']:
                     print(_(" -> Associazione nuovo ID FIDE: {}").format(change['new_fide_id']))
                 if change['updates']:
                     for key, value in change['updates'].items():
                         print(_("     -> Aggiornamento {}: da '{}' a '{}'").format(key.replace('_',' ').title(), player.get(key, _('N/D')), value))
                 print("-" * 20)

    if enter_escape(_("\nVuoi applicare tutte le modifiche proposte al tuo database personale? (INVIO|ESCAPE)")):
        for change in all_potential_changes:
            player_record_to_update = players_db[change['player_id']]
            if change['new_fide_id']:
                player_record_to_update['fide_id_num_str'] = change['new_fide_id']
            if change['updates']:
                player_record_to_update.update(change['updates'])
            
        save_players_db(players_db)
        print(_("\nSincronizzazione completata e database personale salvato!"))
    else:
        print(_("\nOperazione annullata. Nessuna modifica è stata salvata."))

def aggiorna_db_fide_locale():
    """
    Scarica l'ultimo rating list FIDE (XML), estrae un set di dati arricchito
    e lo salva in un file JSON locale (fide_ratings_local.json).
    Restituisce True in caso di successo, False altrimenti.
    """
    try:
        print(_("Download del file ZIP FIDE da: {url}").format(url=FIDE_XML_DOWNLOAD_URL))
        print(_("L'operazione potrebbe richiedere alcuni minuti a seconda della connessione..."))
        zip_response = requests.get(FIDE_XML_DOWNLOAD_URL, timeout=120)
        zip_response.raise_for_status()

        print(_("Download completato. Apertura archivio ZIP in memoria..."))
        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
            xml_filename = next((name for name in zf.namelist() if name.lower().endswith('.xml')), None)
            
            if not xml_filename:
                print(_("ERRORE: Nessun file .xml trovato nell'archivio ZIP."))
                return False
            print(_("Estrazione ed elaborazione del file XML: {filename}...").format(filename=xml_filename))
            
            xml_content = zf.read(xml_filename)
            
            # --- INIZIO MODIFICA 1: FEEDBACK PER PARSING XML ---
            
            # Funzione che il thread eseguirà per stampare il feedback
            def print_feedback(stop_event, message):
                while not stop_event.wait(5): # Attende 5 secondi. Se non viene fermato, stampa.
                    print(message)

            stop_parsing_feedback = threading.Event()
            feedback_msg_parsing = _("  -> L'analisi del file XML è in corso, attendere...")
            parsing_thread = threading.Thread(target=print_feedback, args=(stop_parsing_feedback, feedback_msg_parsing))
            
            print(_("Analisi del file XML in corso (potrebbe richiedere più di un minuto)..."))
            parsing_thread.daemon = True # Permette al programma di uscire anche se il thread è attivo
            parsing_thread.start()
            
            try:
                # Parsing del file XML
                fide_players_db = {}
                root = ET.fromstring(xml_content)
            finally:
                # Ferma il thread di feedback, che abbia funzionato o meno
                stop_parsing_feedback.set()
                
            # --- FINE MODIFICA 1 ---
            
            player_count = 0
            for player_node in root.findall('player'):
                fide_id_node = player_node.find('fideid')
                
                if fide_id_node is not None and fide_id_node.text:
                    fide_id_str = fide_id_node.text.strip()
                    
                    # Estrai i dati usando i nomi dei tag XML
                    name = player_node.find('name').text
                    
                    # Per l'Elo, ora estraiamo tutte e 3 le cadenze + K-Factor e Flag
                    rating_std_node = player_node.find('rating')
                    rating_rap_node = player_node.find('rapid_rating')
                    rating_blz_node = player_node.find('blitz_rating')
                    k_factor_node = player_node.find('k')
                    flag_node = player_node.find('flag')

                    rating_std = int(rating_std_node.text) if rating_std_node is not None and rating_std_node.text else 0
                    
                    # Filtriamo i giocatori inattivi o senza rating standard, che sono meno rilevanti
                    if rating_std == 0 and (flag_node is not None and flag_node.text and 'i' in flag_node.text.lower()):
                        continue

                    last_name_fide, first_name_fide = name, ""
                    if ',' in name:
                        parts = name.split(',', 1)
                        last_name_fide = parts[0].strip()
                        first_name_fide = parts[1].strip()

                    fide_players_db[fide_id_str] = {
                        "id_fide": int(fide_id_str),
                        "first_name": first_name_fide,
                        "last_name": last_name_fide,
                        "federation": player_node.find('country').text,
                        "title": player_node.find('title').text or "",
                        "sex": player_node.find('sex').text or "",
                        # Rinomino 'elo' per chiarezza e aggiungo gli altri
                        "elo_standard": rating_std,
                        "elo_rapid": int(rating_rap_node.text) if rating_rap_node is not None and rating_rap_node.text else 0,
                        "elo_blitz": int(rating_blz_node.text) if rating_blz_node is not None and rating_blz_node.text else 0,
                        "k_factor": int(k_factor_node.text) if k_factor_node is not None and k_factor_node.text else None,
                        "flag": flag_node.text if flag_node is not None else None,
                        "birth_year": int(b.text) if (b := player_node.find('birthday')) is not None and b.text and b.text.isdigit() else None
                    }
                    player_count += 1
                    if player_count % 500000 == 0:
                        print(_("  ... elaborati {count} giocatori...").format(count=player_count))
            print(_("Elaborazione completata. Trovati e salvati {count} giocatori FIDE.").format(count=len(fide_players_db)))
            
            # --- INIZIO MODIFICA 2: FEEDBACK PER SCRITTURA JSON ---
            stop_json_feedback = threading.Event()
            feedback_msg_json = _("  -> La scrittura del file JSON è in corso, attendere...")
            json_thread = threading.Thread(target=print_feedback, args=(stop_json_feedback, feedback_msg_json))

            print(_("Salvataggio del database JSON locale (potrebbe richiedere tempo)..."))
            json_thread.daemon = True
            json_thread.start()
            try:
                with open(FIDE_DB_LOCAL_FILE, "w", encoding='utf-8') as f_out:
                    json.dump(fide_players_db, f_out, indent=1)
            finally:
                stop_json_feedback.set()
            
            # --- FINE MODIFICA 2 ---

            print(_("Database FIDE locale 'fide_ratings_local.json' salvato con successo."))
            return True # Restituisce True in caso di successo
    except requests.exceptions.Timeout:
        print(_("ERRORE: Timeout durante il download del file."))
        return False
    except requests.exceptions.RequestException as e_req:
        print(_("ERRORE di rete: {error}").format(error=e_req))
        return False
    except Exception as e_main:
        print(_("Si è verificato un errore imprevisto durante l'aggiornamento del DB FIDE: {error}").format(error=e_main))
        traceback.print_exc()
        return False

def _conferma_lista_giocatori_torneo(torneo, players_db):
    """
    Mostra i giocatori iscritti a un nuovo torneo e permette la rimozione.
    Restituisce True se la lista giocatori è valida per procedere, False se annullato o troppi pochi giocatori.
    Modifica direttamente torneo['players'] e torneo['players_dict'].
    """
    if not torneo or 'players' not in torneo:
        print(_("Errore: Dati torneo o giocatori mancanti per la conferma."))
        return False

    print(_("\n--- Riepilogo Giocatori Iscritti al Torneo ---"))
    
    while True:
        if not torneo['players']:
            print(_("Nessun giocatore attualmente iscritto al torneo."))
            if enter_escape(_("Vuoi tornare all'inserimento giocatori? (INVIO|ESCAPE)")):
                # Questo richiederebbe di uscire da qui e rientrare in input_players,
                # o modificare input_players per essere richiamabile.
                # Per ora, diciamo che l'utente deve ricreare il torneo se svuota la lista.
                print(_("Lista giocatori vuota. La creazione del torneo potrebbe fallire o necessitare di nuovi inserimenti."))
                return False # Indica che la lista non è valida per procedere
            else:
                return False # L'utente non vuole aggiungere, ma la lista è vuota.

        print(_("Numero attuale di giocatori: {count}").format(count=len(torneo['players'])))
        for i, player_data in enumerate(torneo['players']):
            # Assicurati che i dati per il display siano disponibili
            # Se i giocatori provengono da input_players, dovrebbero avere questi campi.
            player_id = player_data.get('id', 'N/A')
            first_name = player_data.get('first_name', _('Nome?'))
            last_name = player_data.get('last_name', _('Cognome?'))
            elo = player_data.get('initial_elo', 'Elo?') # In un nuovo torneo, sarà initial_elo
            print(f"  {i+1}. ID: {player_id} - {first_name} {last_name} (Elo: {elo})")
        choice = input(_("\nVuoi rimuovere un giocatore dalla lista? (Inserisci il numero, o 'f' per finire e confermare): ")).strip().lower()
        if choice == 'f':
            min_players_for_tournament = torneo.get("total_rounds", 1) + 1 # Esempio di regola: NumTurni + 1
            if len(torneo['players']) < min_players_for_tournament:
                 print(_("ATTENZIONE: Sono necessari almeno {min_players} giocatori per un torneo di {rounds} turni.").format(min_players=min_players_for_tournament, rounds=torneo.get('total_rounds')))
                 if enter_escape(_("Continuare comunque con meno giocatori? (INVIO|ESCAPE)")):
                     print(_("Conferma annullata. Puoi aggiungere altri giocatori o modificare i parametri del torneo."))
                     return False 
            print(_("Lista giocatori confermata."))
            return True # Lista confermata e valida (o utente ha forzato con meno giocatori)
        elif choice.isdigit():
            try:
                idx_to_remove = int(choice) - 1
                if 0 <= idx_to_remove < len(torneo['players']):
                    player_to_remove = torneo['players'][idx_to_remove]
                    confirm_remove = enter_escape(_("Rimuovere '{first_name} {last_name}'? (INVIO|ESCAPE): ").format(first_name=player_to_remove.get('first_name'), last_name=player_to_remove.get('last_name')))
                    if confirm_remove == True:
                        removed_player = torneo['players'].pop(idx_to_remove)
                        print(_("Giocatore '{first_name} {last_name}' rimosso.").format(first_name=removed_player.get('first_name'), last_name=removed_player.get('last_name')))
                        # Aggiorna anche players_dict se necessario (o fallo alla fine una volta)
                        torneo['players_dict'] = {p['id']: p for p in torneo['players']}
                    else:
                        print(_("Rimozione annullata."))
                else:
                    print(_("Numero giocatore non valido."))
            except ValueError:
                print(_("Input non valido."))
        else:
            print(_("Comando non riconosciuto."))

def gestisci_pianificazione_partite(torneo, current_round_data, players_dict):
    '''
    Gestisce l'inserimento, la modifica e la cancellazione della pianificazione 
    delle partite pendenti (senza risultato) per il turno corrente.
    Usa un ID Scacchiera del Turno (basato sull'ordine fisico) per la selezione.
    Restituisce True se sono state apportate modifiche, False altrimenti.
    '''
    any_changes_made_this_session = False
    current_round_num = current_round_data.get("round")

    # --- SOTTO-FUNZIONE PER INPUT DETTAGLI PIANIFICAZIONE (CON INPUT DATA/ORA SEMPLIFICATO) ---
    def _input_schedule_details(existing_details=None):
        details = {}
        is_modifying = existing_details is not None
        now = datetime.now()

        print(_("\n--- Dettagli Pianificazione Partita ---"))
        if is_modifying:
            print(_("Lasciare il campo vuoto per mantenere il valore attuale."))
        while True:
            prompt_date = _("Data partita (formati: GG, GG-MM, {iso_format})").format(iso_format=DATE_FORMAT_ISO)
            default_date_val_for_input = "" # Stringa vuota per get_input_with_default
            current_display = "N/D"
            if is_modifying and existing_details and existing_details.get('date'):
                default_date_val_for_input = existing_details['date']
                current_display = format_date_locale(default_date_val_for_input)
            prompt_date += _(" [Attuale: {current}]: ").format(current=current_display)
            date_input_str = get_input_with_default(prompt_date, default_date_val_for_input).strip()
            if not date_input_str and is_modifying: # Mantiene il vecchio valore se input vuoto in modifica
                details['date'] = default_date_val_for_input
                break
            if not date_input_str and not is_modifying:
                 print(_("La data è obbligatoria."))
                 continue
            
            parsed_date_obj = None
            try:
                if '-' in date_input_str or '/' in date_input_str: # Formato con separatori
                    parts = date_input_str.replace('/', '-').split('-')
                    if len(parts) == 2: # GG-MM
                        day, month = int(parts[0]), int(parts[1])
                        parsed_date_obj = datetime(now.year, month, day)
                    elif len(parts) == 3: # YYYY-MM-DD
                        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                        # Se l'anno è a due cifre, prova a interpretarlo (es. 25 -> 2025)
                        if year < 100: year += 2000 
                        parsed_date_obj = datetime(year, month, day)
                    else: raise ValueError(_("Formato data non riconosciuto"))
                elif date_input_str.isdigit() and 1 <= len(date_input_str) <= 2: # Solo Giorno (GG)
                    day = int(date_input_str)
                    parsed_date_obj = datetime(now.year, now.month, day)
                else: # Prova il formato ISO completo come ultima spiaggia
                    parsed_date_obj = datetime.strptime(date_input_str, DATE_FORMAT_ISO)
                
                details['date'] = parsed_date_obj.strftime(DATE_FORMAT_ISO)
                break
            except ValueError:
                print(_("Formato data '{input}' non valido o data inesistente. Usa GG, GG-MM, o {iso_format}.").format(input=date_input_str, iso_format=DATE_FORMAT_ISO))
            except TypeError: # In caso parsed_date_obj rimanga None per un path non gestito
                 print(_("Input data '{input}' non interpretabile.").format(input=date_input_str))


        while True:
            prompt_time = _("Ora partita (formati: HH, HH:MM)")
            default_time_val_for_input = ""
            current_display_time = "N/O"
            if is_modifying and existing_details and existing_details.get('time'):
                default_time_val_for_input = existing_details['time']
                current_display_time = default_time_val_for_input
            prompt_time += _(" [Attuale: {current}]: ").format(current=current_display_time)
            time_input_str = get_input_with_default(prompt_time, default_time_val_for_input).strip()
            if not time_input_str and is_modifying:
                details['time'] = default_time_val_for_input
                break
            if not time_input_str and not is_modifying:
                 print(_("L'ora è obbligatoria."))
                 continue
            parsed_time_str = None
            try:
                if ':' in time_input_str: # Formato HH:MM
                    dt_obj = datetime.strptime(time_input_str, "%H:%M")
                    parsed_time_str = dt_obj.strftime("%H:%M")
                elif time_input_str.isdigit() and 0 <= int(time_input_str) <= 23 and len(time_input_str) <=2 : # Solo Ora (HH)
                    hour = int(time_input_str)
                    parsed_time_str = f"{hour:02d}:00"
                else:
                    raise ValueError(_("Formato ora non riconosciuto"))
                details['time'] = parsed_time_str
                break
            except ValueError:
                print(_("Formato ora non valido. Usa HH (es. 9) o HH:MM (es. 15:30)."))
        # Canale e Arbitro (invariati)
        default_channel_val = "" if not is_modifying else existing_details.get('channel', "")
        details['channel'] = get_input_with_default(_("Canale/Link partita [Attuale: {current}]: ").format(current=default_channel_val), default_channel_val).strip()
        default_arbiter_val = "" if not is_modifying else existing_details.get('arbiter', "")
        details['arbiter'] = get_input_with_default(_("Arbitro assegnato [Attuale: {current}]: ").format(current=default_arbiter_val), default_arbiter_val).strip()
        if is_modifying: # Controlla se qualcosa è effettivamente cambiato
            changed = False
            if details.get('date') != existing_details.get('date'): changed = True
            if details.get('time') != existing_details.get('time'): changed = True
            if details.get('channel', "") != existing_details.get('channel', ""): changed = True
            if details.get('arbiter', "") != existing_details.get('arbiter', ""): changed = True
            if not changed:
                print(_("Nessun dettaglio della pianificazione è stato effettivamente modificato."))
        if not details.get('date') or not details.get('time'): # Campi obbligatori
             print(_("Data e ora sono obbligatori per la pianificazione. Operazione annullata."))
             return None
        return details
    while True:
        all_matches_in_round_sorted_by_id = sorted(
            current_round_data.get("matches", []), 
            key=lambda m: m.get('id', 0)
        )
        if not any(m.get("result") is None and m.get("black_player_id") is not None for m in all_matches_in_round_sorted_by_id):
            print(_("\nTutte le partite del Turno {round_num} sono state giocate o sono BYE.").format(round_num=current_round_num))
            print(_("Nessuna partita disponibile per la pianificazione/modifica."))
            break 
        display_lines_pending_scheduling = []
        display_lines_already_scheduled = []
        # Mappa: Numero Scacchiera del Turno VISUALIZZATO -> ID Globale Partita
        round_board_to_global_id_map = {} 
        # Mappa: Numero Scacchiera del Turno VISUALIZZATO -> Boolean (è pianificata?)
        round_board_is_scheduled_map = {}
        actual_board_number_counter = 0 # Contatore per il "Numero Scacchiera del Turno"
        # Costruisci le liste visualizzate e le mappe
        for match_obj in all_matches_in_round_sorted_by_id:
            # I BYE non hanno un numero di scacchiera selezionabile per la pianificazione
            if match_obj.get("black_player_id") is None: 
                continue 
            actual_board_number_counter += 1 # Incrementa per ogni partita giocabile (non BYE)
            # Consideriamo per la pianificazione solo le partite senza risultato
            if match_obj.get("result") is not None:
                continue 
            # A questo punto, la partita è giocabile e non ha risultato
            round_board_to_global_id_map[actual_board_number_counter] = match_obj['id']
            wp = players_dict.get(match_obj['white_player_id'])
            bp = players_dict.get(match_obj['black_player_id'])
            wp_name = f"{wp.get('first_name','?')} {wp.get('last_name','?')}" if wp else "N/A"
            bp_name = f"{bp.get('first_name','?')} {bp.get('last_name','?')}" if bp else "N/A"
            base_display_line = f"  Sc. {actual_board_number_counter}. (IDG: {match_obj['id']}) {wp_name} vs {bp_name}"
            if match_obj.get("is_scheduled", False) and match_obj.get("schedule_info"):
                round_board_is_scheduled_map[actual_board_number_counter] = True
                schedule = match_obj.get('schedule_info', {})
                date_str = format_date_locale(schedule.get('date')) if schedule.get('date') else "N/D"
                time_str = schedule.get('time', "N/O")
                channel_str = schedule.get('channel', "N/D")
                arbiter_str = schedule.get('arbiter', "N/D")
                display_lines_already_scheduled.append(base_display_line)
                display_lines_already_scheduled.append(_(" Pianificata per: {date} alle {time}").format(date=date_str, time=time_str))
                display_lines_already_scheduled.append(_(" Canale: {channel}, Arbitro: {arbiter}").format(channel=channel_str, arbiter=arbiter_str))
            else:
                round_board_is_scheduled_map[actual_board_number_counter] = False
                display_lines_pending_scheduling.append(base_display_line)
        
        print(_("\n--- Pianificazione Partite Turno {round_num} ---").format(round_num=current_round_num))
        print(_("(Vengono mostrati i Numeri Scacchiera reali del turno per le partite ancora da giocare)"))

        print(_("\nPartite da Pianificare (non hanno ancora una pianificazione):"))
        if display_lines_pending_scheduling:
            for line in display_lines_pending_scheduling: print(line)
        else:
            print(_("  Nessuna partita attualmente da pianificare (o sono tutte già pianificate)."))

        print(_("\nPartite Già Pianificate (in attesa di risultato):"))
        if display_lines_already_scheduled:
            for line in display_lines_already_scheduled: print(line)
        else:
            print(_("  Nessuna partita attualmente pianificata."))
        
        if not round_board_to_global_id_map:
            print(_("\nNessuna partita pendente disponibile per la gestione della pianificazione."))
            break
        action = key(_("\nOpzioni: (P)ianifica, (M)odifica/Rimuovi pianificazione, (ESCAPE) termina: ")).strip().lower()
        if action == '\x1b':
            break
        elif action == 'p' or action == 'm':
            prompt_msg = _("Inserisci il N. Scacchiera della partita")
            if action == 'p': prompt_msg += _(" da pianificare: ")
            else: prompt_msg += _(" la cui pianificazione vuoi modificare/rimuovere: ")
            selected_board_id_str = input(prompt_msg).strip()
            if not selected_board_id_str.isdigit():
                print(_("Input non valido. Inserisci un numero.")); continue
            
            selected_board_id = int(selected_board_id_str)
            
            if selected_board_id not in round_board_to_global_id_map:
                print(_("N#. Scacchiera non valido o non corrisponde a una partita gestibile.")); continue

            target_match_global_id = round_board_to_global_id_map[selected_board_id]
            is_currently_scheduled = round_board_is_scheduled_map.get(selected_board_id, False) # Default a False

            match_object_to_update = None
            original_match_idx = -1
            for m_idx, m_obj_loop in enumerate(current_round_data["matches"]):
                if m_obj_loop.get('id') == target_match_global_id:
                    match_object_to_update = current_round_data["matches"][m_idx]
                    original_match_idx = m_idx
                    break
            
            if not match_object_to_update:
                print(_("ERRORE INTERNO: Partita IDG {match_id} non trovata.").format(match_id=target_match_global_id))
                continue

            if action == 'p':
                if is_currently_scheduled:
                    print(_("Questa partita è già pianificata. Usa 'M' per modificarla.")); continue
                print(_("\nPianificazione per la partita Sc. {board_id} (IDG: {match_id})...").format(board_id=selected_board_id, match_id=target_match_global_id))
                new_schedule_data = _input_schedule_details() # existing_details è None
                if new_schedule_data:
                    match_object_to_update['schedule_info'] = new_schedule_data
                    match_object_to_update['is_scheduled'] = True
                    any_changes_made_this_session = True
                    print(_("Partita pianificata con successo."))
                else:
                    print(_("Pianificazione annullata."))
            elif action == 'm':
                if not is_currently_scheduled:
                    print(_("Questa partita non ha una pianificazione da modificare/rimuovere. Usa 'P'.")); continue
                wp_m = players_dict.get(match_object_to_update['white_player_id'])
                bp_m = players_dict.get(match_object_to_update['black_player_id'])
                wp_name_m = f"{wp_m.get('first_name','?')} {wp_m.get('last_name','?')}" if wp_m else "N/A"
                bp_name_m = f"{bp_m.get('first_name','?')} {bp_m.get('last_name','?')}" if bp_m else "N/A"
                print(_("\nGestione pianificazione per Sc. {board_id} (IDG: {match_id}): {white_player} vs {black_player}").format(board_id=selected_board_id, match_id=target_match_global_id, white_player=wp_name_m, black_player=bp_name_m))
                
                sub_action = key(_("Vuoi (M)odificare o (R)imuovere la pianificazione? (Invio per annullare): ")).strip().lower()
                if sub_action == 'm':
                    updated_schedule_data = _input_schedule_details(existing_details=match_object_to_update.get('schedule_info'))
                    if updated_schedule_data:
                        if updated_schedule_data != match_object_to_update.get('schedule_info'): # Controlla se c'è stato un cambiamento reale
                            match_object_to_update['schedule_info'] = updated_schedule_data
                            any_changes_made_this_session = True
                            print(_("Pianificazione modificata."))
                        # else: Nessuna modifica effettiva, non fare nulla
                    else: print(_("Modifica annullata."))
                elif sub_action == 'r':
                    if enter_escape(_("Confermi rimozione pianificazione? (INVIO|ESCAPE)")):
                        match_object_to_update['is_scheduled'] = False
                        if 'schedule_info' in match_object_to_update: del match_object_to_update['schedule_info']
                        any_changes_made_this_session = True
                        print(_("Pianificazione rimossa."))
                    else: print(_("Rimozione annullata."))
                elif not sub_action: print(_("Operazione annullata."))
                else: print(_("Azione non valida per modifica/rimozione."))
        else:
            print(_("Azione non riconosciuta. Riprova."))
    return any_changes_made_this_session

def genera_stringa_trf_per_bbpairings(dati_torneo, lista_giocatori_attivi, mappa_id_a_start_rank):
    """
    Genera la stringa di testo in formato TRF(bx) per bbpairings.
    Per il Round 1: righe giocatore SENZA blocchi dati partita (si affida a XXC white1).
    Per i Round > 1: righe giocatore CON storico risultati dei turni precedenti.
    """
    trf_lines = []
    try:
        valore_bye_torneo = dati_torneo.get('bye_value', 1.0)
        total_rounds_val = int(dati_torneo.get('total_rounds', 0))
        number_of_players_val = len(lista_giocatori_attivi)
        current_round_being_paired = int(dati_torneo.get("current_round", 1))
        start_date_strf = dati_torneo.get('start_date', '01/01/1900') 
        end_date_strf = dati_torneo.get('end_date', '01/01/1900')   
        if '/' not in start_date_strf and len(start_date_strf) == 10 and '-' in start_date_strf:
            try:
                start_date_obj = datetime.strptime(start_date_strf, '%Y-%m-%d')
                start_date_strf = start_date_obj.strftime('%d/%m/%Y')
            except ValueError: start_date_strf = '01/01/1900' 
        if '/' not in end_date_strf and len(end_date_strf) == 10 and '-' in end_date_strf:
            try:
                end_date_obj = datetime.strptime(end_date_strf, '%Y-%m-%d')
                end_date_strf = end_date_obj.strftime('%d/%m/%Y')
            except ValueError: end_date_strf = '01/01/1900'
        # Intestazione (Header)
        trf_lines.append(f"012 {str(dati_torneo.get('name', _('Torneo Sconosciuto')))[:45]:<45}\n")
        trf_lines.append(f"022 {str(dati_torneo.get('site', _('Luogo Sconosciuto')))[:45]:<45}\n") # Usa 'site'
        trf_lines.append(f"032 {str(dati_torneo.get('federation_code', 'ITA'))[:3]:<3}\n")    # Usa 'federation_code'
        trf_lines.append(f"042 {start_date_strf}\n") # Già usa 'start_date'
        trf_lines.append(f"052 {end_date_strf}\n")   # Già usa 'end_date'
        trf_lines.append(f"062 {number_of_players_val:03d}\n") # Già calcolato
        trf_lines.append(f"072 {number_of_players_val:03d}\n") # Già calcolato
        trf_lines.append("082 000\n") 
        trf_lines.append("092 Individual: Swiss-System\n") # Potrebbe diventare configurabile
        trf_lines.append(f"102 {str(dati_torneo.get('chief_arbiter', _('Arbitro Capo')))[:45]:<45}\n") # Usa 'chief_arbiter'
        deputy_str = str(dati_torneo.get('deputy_chief_arbiters', '')).strip()
        if not deputy_str: deputy_str = " " # TRF vuole almeno uno spazio se la riga 112 è presente ma vuota
        trf_lines.append(f"112 {deputy_str[:45]:<45}\n") 
        trf_lines.append(f"122 {str(dati_torneo.get('time_control', 'Standard'))[:45]:<45}\n") # Usa 'time_control'
        trf_lines.append(f"XXR {total_rounds_val:03d}\n") # Già usa 'total_rounds'
        initial_color_setting = str(dati_torneo.get('initial_board1_color_setting', 'white1')).lower()
        trf_lines.append(f"XXC {initial_color_setting}\n")
        def write_to_char_list_local(target_list, start_col_1based, text_to_write):
            start_idx_0based = start_col_1based - 1
            source_chars = list(str(text_to_write))
            max_len_to_write = len(source_chars)
            # Evita di scrivere oltre la lunghezza della target_list se text_to_write è troppo lungo
            # per la posizione data, anche se p_line_chars è grande.
            if start_idx_0based + max_len_to_write > len(target_list):
                max_len_to_write = len(target_list) - start_idx_0based
            
            for i in range(max_len_to_write):
                if start_idx_0based + i < len(target_list): # Doppio controllo per sicurezza
                    target_list[start_idx_0based + i] = source_chars[i]
        
        giocatori_ordinati_per_start_rank = sorted(lista_giocatori_attivi, key=lambda p: mappa_id_a_start_rank[p['id']])

        for player_data in giocatori_ordinati_per_start_rank:
            # Lunghezza base fino a col 89 (Rank) + spazio per molti turni di storico
            p_line_chars = [' '] * (89 + (total_rounds_val * 10) + 5) # 89 + storico + buffer
            start_rank = mappa_id_a_start_rank[player_data['id']]
            raw_last_name = player_data.get('last_name', _('Cognome'))
            raw_first_name = player_data.get('first_name', _('Nome'))
            nome_completo = f"{raw_last_name}, {raw_first_name}"
            elo = int(player_data.get('initial_elo', 1399)) 
            federazione_giocatore = str(player_data.get('federation', 'ITA')).upper()[:3]
            # Usa i campi specifici dal tuo player_data. Questi sono esempi.
            fide_id_from_playerdata = str(player_data.get('fide_id_num_str', '0')) # Usa la chiave corretta
            birth_date_from_playerdata = str(player_data.get('birth_date', '1900-01-01')) # Usa la chiave corretta
            title_from_playerdata = str(player_data.get('fide_title', '')).strip().upper() # Usa la chiave corretta
            # Scrittura campi anagrafici
            write_to_char_list_local(p_line_chars, 1, "001")
            write_to_char_list_local(p_line_chars, 5, f"{start_rank:>4}")
            write_to_char_list_local(p_line_chars, 10, player_data.get('sex', 'm')) 
            write_to_char_list_local(p_line_chars, 11, f"{title_from_playerdata:>3}"[:3])
            write_to_char_list_local(p_line_chars, 15, f"{nome_completo:<33}"[:33])
            write_to_char_list_local(p_line_chars, 49, f"{elo:<4}") 
            write_to_char_list_local(p_line_chars, 54, f"{federazione_giocatore:<3}"[:3])
            fide_id_core_num_fmt = f"{fide_id_from_playerdata:>9}"[:9] # Allinea a dx su 9 char
            fide_id_final_field = f"{fide_id_core_num_fmt}  "[:11]    # Aggiungi 2 spazi, assicurati 11 char
            write_to_char_list_local(p_line_chars, 58, fide_id_final_field)
            birth_date_for_trf = "          " # Default 10 spazi
            if birth_date_from_playerdata: # Se non è None o stringa vuota
                try:
                    # Prova a convertire da YYYY-MM-DD a YYYY/MM/DD
                    dt_obj = datetime.strptime(birth_date_from_playerdata, DATE_FORMAT_ISO) # DATE_FORMAT_DB è %Y-%m-%d
                    birth_date_for_trf = dt_obj.strftime("%Y/%m/%d") # Formato TRF standard
                except ValueError:
                    # Se non è nel formato YYYY-MM-DD, usa il valore grezzo se è lungo 10, altrimenti placeholder
                    if len(str(birth_date_from_playerdata)) == 10:
                        birth_date_for_trf = str(birth_date_from_playerdata)
                    else: # Fallback a stringa di spazi se il formato non è gestibile
                        birth_date_for_trf = "          " 
            write_to_char_list_local(p_line_chars, 70, f"{birth_date_for_trf:<10}"[:10]) # Assicura 10 caratteri            
            punti_reali = float(player_data.get('points', 0.0))
            punti_per_trf = punti_reali  # Inizia con i punti reali
            # Se il valore del BYE nel torneo è diverso da 1.0 (es. 0.5),
            # dobbiamo correggere il punteggio da passare al motore.
            if valore_bye_torneo != 1.0:
                for res_entry in player_data.get("results_history", []):
                    # Se questo risultato è un BYE, aggiungiamo la differenza per "ingannare" il motore
                    if res_entry.get("opponent_id") == "BYE_PLAYER_ID":
                        punti_per_trf += (1.0 - valore_bye_torneo)
            # Scrivi il punteggio corretto per il motore
            write_to_char_list_local(p_line_chars, 81, f"{punti_per_trf:4.1f}")
            write_to_char_list_local(p_line_chars, 86, f"{start_rank:>4}") # Campo Rank (col 86-89)
            colonna_inizio_blocco_partita = 92 
            
            history_sorted = sorted(player_data.get("results_history", []), key=lambda x: x.get("round", 0))
            if current_round_being_paired > 1:
                for res_entry in history_sorted:
                    round_of_this_entry = int(res_entry.get("round", 0))
                    
                    if round_of_this_entry > 0 and round_of_this_entry < current_round_being_paired:
                        opp_id_tornello = res_entry.get("opponent_id")
                        player_color_this_game = str(res_entry.get("color", "")).lower()
                        
                        color_char_trf = "-" 
                        if player_color_this_game == "white": color_char_trf = "w"
                        elif player_color_this_game == "black": color_char_trf = "b"
                        
                        tornello_result_str = str(res_entry.get("result", "")).upper()
                        player_score_this_game = float(res_entry.get("score", 0.0)) 
                        result_code_trf = "?"
                        opp_start_rank_str = "0000"

                        if opp_id_tornello == "BYE_PLAYER_ID" or tornello_result_str == "BYE":
                            color_char_trf = "-"
                            if player_score_this_game > 0.0: result_code_trf = "U" 
                            else: result_code_trf = "Z" 
                        elif opp_id_tornello:
                            opponent_start_rank = mappa_id_a_start_rank.get(opp_id_tornello)
                            if opponent_start_rank is None:
                                print(_("AVVISO CRITICO: ID avversario storico {opponent_id} non trovato in mappa per giocatore {player_id} al turno {round_num}").format(opponent_id=opp_id_tornello, player_id=player_data['id'], round_num=round_of_this_entry))
                                opp_start_rank_str = "XXXX" 
                            else:
                                opp_start_rank_str = f"{opponent_start_rank:>4}"
                            is_white = (player_color_this_game == "white")
                            if tornello_result_str == "1-0":
                                result_code_trf = "1" if is_white else "0"
                            elif tornello_result_str == "0-1":
                                result_code_trf = "0" if is_white else "1"
                            elif tornello_result_str == "1/2-1/2":
                                result_code_trf = "="
                            elif tornello_result_str == "1-F":
                                result_code_trf = "+" if is_white else "-"
                            elif tornello_result_str == "F-1":
                                result_code_trf = "-" if is_white else "+"
                            elif tornello_result_str == "0-0F":
                                result_code_trf = "-"
                            else:
                                result_code_trf = "?"
                        else: continue 
                        
                        if result_code_trf == "?": continue

                        game_block = f"{opp_start_rank_str} {color_char_trf} {result_code_trf}  "[:10] 
                        write_to_char_list_local(p_line_chars, colonna_inizio_blocco_partita, game_block)
                        colonna_inizio_blocco_partita += 10
            
            # Per il Round 1: NON aggiungiamo il blocco "0000 w   " se XXC white1 è presente.
            # Le righe giocatore per il R1 finiranno dopo il campo Rank (col 89) o gli spazi successivi.
            # rstrip() si occuperà di rimuovere gli spazi finali inutilizzati da p_line_chars.
            # Se il giocatore è ritirato, aggiungi un risultato "Sconfitta a 0 punti" (Z)
            # per il turno corrente. Questo dice a bbpPairings di non abbinarlo.
            if dati_torneo['players_dict'][player_data['id']].get("withdrawn", False):
                # L'avversario è 0000 (nessuno), il colore è '-' (non applicabile).
                game_block_forfeit = f"{'0000':>4} {'-':<1} {'Z':<1}   "[:10]
                # Scriviamo questo blocco nella prima colonna disponibile per lo storico
                write_to_char_list_local(p_line_chars, colonna_inizio_blocco_partita, game_block_forfeit)
            final_line = "".join(p_line_chars).rstrip()
            trf_lines.append(final_line + "\n")
        return "".join(trf_lines)
    except Exception as e:
        print(_("Errore catastrofico in genera_stringa_trf_per_bbpairings: {error}").format(error=e))
        traceback.print_exc()
        return None

def get_k_factor(player_data_dict, tournament_start_date_str):
    """
    Determina il K-Factor FIDE. Ora dà priorità al valore ufficiale FIDE se presente nel DB,
    altrimenti lo calcola basandosi sulle regole.
    """
    # --- NUOVA LOGICA DI PRIORITÀ ---
    # Se abbiamo un K-Factor ufficiale dalla FIDE, usiamo quello e basta.
    fide_k = player_data_dict.get('fide_k_factor')
    if fide_k is not None and fide_k in [10, 20, 40]: # I valori K validi
        return fide_k
    # --- FINE NUOVA LOGICA ---

    # Se non c'è un K-Factor FIDE, procedi con la logica di calcolo esistente...
    if not player_data_dict: return DEFAULT_K_FACTOR
    try:
        elo = float(player_data_dict.get('current_elo', DEFAULT_ELO))
    except (ValueError, TypeError):
        elo = DEFAULT_ELO

    games_played = player_data_dict.get('games_played', 0)
    is_experienced = player_data_dict.get('experienced', False)
    birth_date_str = player_data_dict.get('birth_date')
    age = None

    if birth_date_str and tournament_start_date_str:
        try:
            birth_dt = datetime.strptime(birth_date_str, DATE_FORMAT_ISO)
            current_dt = datetime.strptime(tournament_start_date_str, DATE_FORMAT_ISO)
            age = relativedelta(current_dt, birth_dt).years
        except (ValueError, TypeError):
            pass 

    if games_played < 30 and not is_experienced:
        return 40
    if age is not None and age < 18 and elo < 2300:
        return 40
    if elo < 2400:
        return 20
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
       usando la libreria Babel per una gestione robusta della localizzazione."""
    if not date_input:
        return _("N/D") 

    try:
        date_obj = date_input
        if not isinstance(date_input, datetime):
            # Converte la stringa ISO in un oggetto datetime, ma solo la parte della data
            date_obj = datetime.strptime(str(date_input), DATE_FORMAT_ISO).date()

        # Usa Babel per formattare la data in italiano in modo sicuro
        # 'full' corrisponde a un formato tipo "lunedì 23 giugno 2025"
        return format_date(date_obj, format='full', locale=lingua_rilevata).capitalize()
    except (ValueError, TypeError, IndexError):
        # Se qualcosa va storto, restituisce l'input originale
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

def run_bbpairings_engine(trf_content_string):
    """
    Esegue bbpPairings.exe con il TRF fornito e restituisce i risultati.

    Args:
        trf_content_string (str): Il contenuto completo del file TRF da passare a bbpPairings.

    Returns:
        tuple: (successo_bool, dati_output, messaggio_errore_o_dettagli)
               dati_output (dict): {'coppie': [(id_bianco, id_nero/None_per_bye)], 'checklist_raw': stringa_checklist}
               o None se fallisce.
               messaggio_errore_o_dettagli (str): Messaggio di errore o stdout/stderr.
    """
    # Assicurati che la sottocartella esista
    if not os.path.exists(BBP_SUBDIR):
        try:
            os.makedirs(BBP_SUBDIR)
            print(_("Info: Creata sottocartella '{subdir}' per i file di bbpPairings.").format(subdir=BBP_SUBDIR))
        except OSError as e:
            return False, None, _("Errore creazione sottocartella '{subdir}': {error}").format(subdir=BBP_SUBDIR, error=e)
    try:
        with open(BBP_INPUT_TRF, "w", encoding="utf-8") as f:
            f.write(trf_content_string)
    except IOError as e:
        return False, None, _("Errore scrittura file TRF di input '{filepath}': {error}").format(filepath=BBP_INPUT_TRF, error=e)
    command = [
        BBP_EXE_PATH,
        "--dutch",
        BBP_INPUT_TRF,
        "-p", BBP_OUTPUT_COUPLES,
        "-l", BBP_OUTPUT_CHECKLIST
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace')
        if result.returncode != 0:
            error_message = _("bbpPairings.exe ha fallito con codice {}.\n").format(result.returncode)
            error_message += _("Stderr:\n{}\n").format(result.stderr)
            error_message += _("Stdout:\n{}").format(result.stdout)
            # Se codice è 1 (no pairing), lo gestiremo specificamente più avanti
            return False, {'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}, error_message
        # Lettura file di output se successo
        coppie_content = ""
        if os.path.exists(BBP_OUTPUT_COUPLES):
            with open(BBP_OUTPUT_COUPLES, "r", encoding="utf-8") as f:
                coppie_content = f.read()
        else:
            return False, None, _("File output coppie '{filepath}' non trovato.").format(filepath=BBP_OUTPUT_COUPLES)
            
        checklist_content = ""
        if os.path.exists(BBP_OUTPUT_CHECKLIST):
            with open(BBP_OUTPUT_CHECKLIST, "r", encoding="utf-8") as f:
                checklist_content = f.read()
        # Non consideriamo un errore se il checklist non c'è, ma logghiamo

        return True, {'coppie_raw': coppie_content, 'checklist_raw': checklist_content, 'stdout': result.stdout}, _("Esecuzione bbpPairings completata.")

    except FileNotFoundError:
        return False, None, _("Errore: Eseguibile '{filepath}' non trovato. Assicurati sia nel percorso corretto.").format(filepath=BBP_EXE_PATH)
    except Exception as e:
        return False, None, _("Errore imprevisto durante esecuzione bbpPairings: {error}\n{traceback}").format(error=e, traceback=traceback.format_exc())

def parse_bbpairings_couples_output(coppie_raw_content, mappa_start_rank_a_id):
    """
    Estrae gli abbinamenti dal file di output 'coppie' di bbpPairings.
    Il primo ID in una coppia ha il Bianco. Un ID '0' come avversario indica un BYE.

    Args:
        coppie_raw_content (str): Contenuto testuale del file output coppie.
        mappa_start_rank_a_id (dict): Mappa {start_rank_progressivo: id_tornello}.

    Returns:
        list: Lista di dizionari partita, es:
              [{'white_player_id': ID1, 'black_player_id': ID2, 'result': None, 'is_bye': False},
               {'white_player_id': ID3, 'black_player_id': None, 'result': 'BYE', 'is_bye': True}, ...]
              o None in caso di errore.
    """
    parsed_matches = []
    lines = coppie_raw_content.strip().splitlines()

    if not lines:
        print(_("Warning: File output coppie vuoto o illeggibile."))
        return None # O lista vuota, da decidere
    try:
        pair_lines = lines[1:] # Le righe effettive degli abbinamenti
        for line_num, line in enumerate(pair_lines):
            parts = line.strip().split()
            if len(parts) != 2:
                print(_("Warning: Riga abbinamento malformata: '{line}' (saltata)").format(line=line))
                continue
            
            try:
                start_rank1_str, start_rank2_str = parts[0], parts[1]
                start_rank1 = int(start_rank1_str)
                start_rank2 = int(start_rank2_str) # Può essere 0 per il BYE
            except ValueError:
                print(_("Warning: ID non numerici nella riga abbinamento: '{line}' (saltata)").format(line=line))
                continue

            player1_id_tornello = mappa_start_rank_a_id.get(start_rank1)
            
            if player1_id_tornello is None:
                print(_("Warning: StartRank {rank} non trovato nella mappa giocatori (riga: '{line}').").format(rank=start_rank1, line=line))
                continue

            if start_rank2 == 0: # È un BYE
                parsed_matches.append({
                    'white_player_id': player1_id_tornello,
                    'black_player_id': None, # Nessun Nero per il BYE
                    'result': "BYE",         # Pre-impostiamo il risultato
                    'is_bye': True
                })
            else:
                player2_id_tornello = mappa_start_rank_a_id.get(start_rank2)
                if player2_id_tornello is None:
                    print(_("Warning: StartRank avversario {rank} non trovato nella mappa (riga: '{line}').").format(rank=start_rank2, line=line))
                    continue
                # Assumiamo che il primo giocatore nella coppia (player1) abbia il Bianco
                parsed_matches.append({
                    'white_player_id': player1_id_tornello,
                    'black_player_id': player2_id_tornello,
                    'result': None,
                    'is_bye': False
                })
        return parsed_matches
    except Exception as e:
        print(_("Errore durante il parsing dell'output delle coppie: {error}\n{traceback}").format(error=e, traceback=traceback.format_exc()))
        return None

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
                    p.setdefault('fide_k_factor', None)
                return {p['id']: p for p in db_list}
        except (json.JSONDecodeError, IOError) as e:
            print(_("Errore durante il caricamento del DB giocatori ({filename}): {error}").format(filename=PLAYER_DB_FILE, error=e))
            print(_("Verrà creato un nuovo DB vuoto se si aggiungono giocatori."))
            return {}
    return {}

def save_players_db(players_db):
    """Salva il database dei giocatori nel file JSON e genera il file TXT."""
    if not players_db:
        pass # Procedi a salvare anche se vuoto
    try:
        with open(PLAYER_DB_FILE, "w", encoding='utf-8') as f:
            json.dump(list(players_db.values()), f, indent=1, ensure_ascii=False)
        save_players_db_txt(players_db)
    except IOError as e:
        print(_("Errore durante il salvataggio del DB giocatori ({filename}): {error}").format(filename=PLAYER_DB_FILE, error=e))
    except Exception as e:
        print(_("Errore imprevisto durante il salvataggio del DB: {error}").format(error=e))

def save_players_db_txt(players_db):
    """Genera un file TXT leggibile con lo stato del database giocatori,
       includendo partite giocate totali e K-Factor attuale."""
    try:
        with open(PLAYER_DB_TXT_FILE, "w", encoding='utf-8-sig') as f: # Usiamo utf-8-sig
            now = datetime.now()
            current_date_iso = now.strftime(DATE_FORMAT_ISO) # Data corrente per calcolo K
            f.write(_("Report Database Giocatori Tornello - {date} {time}\n").format(date=format_date_locale(now.date()), time=now.strftime('%H:%M:%S')))
            f.write("=" * 40 + "\n\n")
            sorted_players = sorted(players_db.values(), key=lambda p: (p.get('last_name',''), p.get('first_name','')))
            if not sorted_players:
                f.write(_("Il database dei giocatori è vuoto.\n"))
                return
            for player in sorted_players:
                sesso = str(player.get('sex', 'N/D')).upper()
                federazione_giocatore = str(player.get('federation', 'N/D')).upper()
                fide_id_numerico = str(player.get('fide_id_num_str', 'N/D'))
                titolo_fide = str(player.get('fide_title', '')).strip().upper()
                titolo_prefix = f"{titolo_fide} " if titolo_fide else ""
                player_id_display = player.get('id', 'N/D')
                first_name_display = player.get('first_name', 'N/D')
                last_name_display = player.get('last_name', 'N/D')
                elo_display = player.get('current_elo', 'N/D')
                f.write(f"ID: {player_id_display}, {titolo_prefix}{first_name_display} {last_name_display}, Elo: {elo_display}\n")
                f.write(_("\tSesso: {sesso}, Federazione Giocatore: {federazione}, ID FIDE num: {fide_id}\n").format(sesso=sesso, federazione=federazione_giocatore, fide_id=fide_id_numerico))
                games_played_total = player.get('games_played', 0)
                current_k_factor = get_k_factor(player, current_date_iso) # Assicurati che get_k_factor sia accessibile
                registration_date_display = format_date_locale(player.get('registration_date'))
                f.write(_("\tPartite Valutate Totali: {games}, K-Factor Stimato: {k_factor}, Data Iscrizione DB: {reg_date}\n").format(games=games_played_total, k_factor=current_k_factor, reg_date=registration_date_display))
                birth_date_val = player.get('birth_date') # Formato YYYY-MM-DD o None
                birth_date_display = format_date_locale(birth_date_val) if birth_date_val else 'N/D'
                f.write(_("\tData Nascita: {birth_date}\n").format(birth_date=birth_date_display))
                medals = player.get('medals', {'gold': 0, 'silver': 0, 'bronze': 0, 'wood': 0})
                f.write(_("\tMedagliere: Oro: {gold}, Argento: {silver}, Bronzo: {bronze}, Legno: {wood} in ").format(gold=medals.get('gold',0), silver=medals.get('silver',0), bronze=medals.get('bronze',0), wood=medals.get('wood',0)))
                tournaments = player.get('tournaments_played', [])
                f.write(_("({count}) tornei:\n").format(count=len(tournaments)))
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
                         t_name = t.get('tournament_name', _('Nome Torneo Mancante'))
                         start_date_iso = t.get('date_started') # Prende la nuova data ISO di inizio
                         end_date_iso = t.get('date_completed') # Data di completamento
                         rank_formatted = format_rank_ordinal(rank_val) # Usa la nuova funzione helper
                         start_date_formatted = format_date_locale(start_date_iso)
                         end_date_formatted = format_date_locale(end_date_iso)
                         history_line = _("{rank} su {total} in {name} - {start} - {end}").format(rank=rank_formatted, total=t.get('total_players', '?'), name=t_name, start=start_date_formatted, end=end_date_formatted)
                         f.write(f"\t{history_line}\n")
                else:
                    f.write(_("\tNessuno\n"))
                f.write("\t" + "-" * 30 + "\n")
    except IOError as e:
        print(_("Errore durante il salvataggio del file TXT del DB giocatori ({filename}): {error}").format(filename=PLAYER_DB_TXT_FILE, error=e))
    except Exception as e:
        print(_("Errore imprevisto durante il salvataggio del TXT del DB: {}").format(e))
        traceback.print_exc() # Stampa traceback per errori non gestiti

def crea_nuovo_giocatore_nel_db(players_db, 
                                first_name, last_name, elo,
                                fide_title, sex, federation, 
                                fide_id_num_str, birth_date, experienced):
    """
    Crea SEMPRE un nuovo giocatore nel database principale (players_db),
    generando un ID univoco che gestisce gli omonimi.
    Salva il database principale aggiornato.
    Restituisce il nuovo ID del giocatore creato o None in caso di fallimento.
    """
    norm_first = first_name.strip().title()
    norm_last = last_name.strip().title()

    if not norm_first or not norm_last:
        print(_("Errore: Nome e Cognome non possono essere vuoti per la creazione del giocatore nel DB."))
        return None
    # Logica di Generazione ID (gestisce omonimi creando ID univoci come BATGA001, BATGA002, ecc.)
    last_part_cleaned = ''.join(norm_last.split())
    first_part_cleaned = ''.join(norm_first.split())
    last_initials = last_part_cleaned[:3].upper().ljust(3, 'X')
    first_initials = first_part_cleaned[:2].upper().ljust(2, 'X')
    base_id = f"{last_initials}{first_initials}"
    if not base_id or base_id == "XXXXX": # Fallback nel caso nome/cognome fossero invalidi (improbabile qui)
        base_id = "GIOCX" 
    count = 1
    new_player_id = f"{base_id}{count:03d}"
    max_attempts_id_gen = 1000 # Numero massimo di tentativi per trovare un ID univoco
    current_attempt_id_gen = 0
    while new_player_id in players_db and current_attempt_id_gen < max_attempts_id_gen:
        count += 1
        new_player_id = f"{base_id}{count:03d}"
        current_attempt_id_gen += 1
        if count > 999: # Se i 3 digit non bastano (molti omonimi)
            # Prova con un suffisso basato su timestamp per maggiore unicità
            timestamp_suffix = datetime.now().strftime('%S%f')[-4:] # Ultime 4 cifre da secondi+microsecondi
            candidate_id = f"{base_id}{timestamp_suffix}"
            if candidate_id not in players_db:
                new_player_id = candidate_id
                break 
            else: # Estrema rarità, usa un ID quasi certamente univoco
                new_player_id = f"TEMP_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                if new_player_id in players_db: # Praticamente impossibile, ma per completezza
                    print(_("ERRORE CRITICO: Fallimento catastrofico generazione ID per {} {}.").format(norm_first, norm_last))
                    return None 
                break 
    if new_player_id in players_db and current_attempt_id_gen >= max_attempts_id_gen:
        print(_("ERRORE CRITICO: Impossibile generare ID univoco per {first_name} {last_name} dopo {attempts} tentativi.").format(first_name=norm_first, last_name=norm_last, attempts=max_attempts_id_gen))
        return None

    print(_("Creazione nuovo giocatore nel DB principale: {} {} con il nuovo ID: {}").format(norm_first, norm_last, new_player_id))
    new_player_data_for_db = {
        "id": new_player_id,
        "first_name": norm_first,
        "last_name": norm_last,
        "current_elo": elo,
        "registration_date": datetime.now().strftime(DATE_FORMAT_ISO),
        "birth_date": birth_date, 
        "games_played": 0,
        "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
        "tournaments_played": [],
        "fide_title": fide_title,
        "sex": sex,
        "federation": federation,
        "fide_id_num_str": fide_id_num_str,
        "experienced": experienced
    }
    players_db[new_player_id] = new_player_data_for_db
    save_players_db(players_db) # Salva immediatamente il DB principale aggiornato
    print(_("Nuovo giocatore '{first_name} {last_name}' (ID: {player_id}) aggiunto al database principale.").format(first_name=norm_first, last_name=norm_last, player_id=new_player_id))
    return new_player_id

def load_tournament(filename_to_load):
    """Carica lo stato del torneo corrente dal file JSON."""
    if os.path.exists(filename_to_load):
        try:
            with open(filename_to_load, "r", encoding='utf-8') as f:
                torneo_data = json.load(f)
                torneo_data.setdefault('name', _('Torneo Sconosciuto'))
                torneo_data.setdefault('start_date', datetime.now().strftime(DATE_FORMAT_ISO))
                torneo_data.setdefault('end_date', datetime.now().strftime(DATE_FORMAT_ISO))
                torneo_data.setdefault('total_rounds', 0)
                torneo_data.setdefault('current_round', 1)
                torneo_data.setdefault('next_match_id', 1)
                torneo_data.setdefault('rounds', [])
                torneo_data.setdefault('players', [])
                torneo_data.setdefault('launch_count', 0)
                torneo_data.setdefault('site', _('Luogo Sconosciuto'))
                torneo_data.setdefault('federation_code', 'ITA') # Federazione del torneo
                torneo_data.setdefault('chief_arbiter', 'N/D')
                torneo_data.setdefault('deputy_chief_arbiters', '')
                torneo_data.setdefault('time_control', 'Standard')
                torneo_data.setdefault('bye_value', 1.0) 
                if 'players' in torneo_data:
                    for p in torneo_data['players']:
                        p['opponents'] = set(p.get('opponents', [])) 
                        p.setdefault('white_games', 0)
                        p.setdefault('black_games', 0)
                        p.setdefault('received_bye_count', 0) # Esempio se avevi aggiunto questo
                        p.setdefault('received_bye_in_round', [])
                torneo_data['players_dict'] = {p['id']: p for p in torneo_data.get('players', [])}
                return torneo_data
        except (json.JSONDecodeError, IOError) as e:
            print(_("Errore durante il caricamento del torneo ({filename}): {error}").format(filename=filename_to_load, error=e))
            return None
    return None

def save_tournament(torneo):
    """Salva lo stato corrente del torneo nel file JSON."""
    tournament_name_for_file = None  # Inizializza a None
    dynamic_tournament_filename = None # Inizializza a None
    try:
        tournament_name_for_file = torneo.get('name')
        if not tournament_name_for_file:
            print(_("Errore: Nome del torneo non presente. Impossibile salvare."))
            return # O gestisci diversamente, es. nome file di default
        sanitized_name = sanitize_filename(tournament_name_for_file)
        dynamic_tournament_filename = f"Tornello - {sanitized_name}.json"        
        torneo_to_save = torneo.copy()
        # Prepara i dati per il salvataggio JSON
        if 'players' in torneo_to_save:
            temp_players = []
            for p in torneo_to_save['players']:
                player_copy = p.copy()
                # Converti set in lista PRIMA di salvare
                player_copy['opponents'] = list(player_copy.get('opponents', set()))
                temp_players.append(player_copy)
            torneo_to_save['players'] = temp_players
        # Rimuovi il dizionario cache che non è serializzabile o necessario salvare
        if 'players_dict' in torneo_to_save:
            del torneo_to_save['players_dict']
        with open(dynamic_tournament_filename, "w", encoding='utf-8') as f:
            json.dump(torneo_to_save, f, indent=1, ensure_ascii=False)
    except IOError as e:
        print(_("Errore durante il salvataggio del torneo ({filename}): {error}").format(filename=dynamic_tournament_filename, error=e))
    except Exception as e:
        print(_("Errore imprevisto durante il salvataggio del torneo: {}").format(e))
        traceback.print_exc() # Stampa più dettagli in caso di errore non previsto

def _ensure_players_dict(torneo):
    """Assicura che il dizionario cache dei giocatori sia presente e aggiornato."""
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players', [])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    return torneo['players_dict']

def get_player_by_id(torneo, player_id):
    """Restituisce i dati del giocatore nel torneo dato il suo ID, usando il dizionario interno."""
    # Ricrea il dizionario se non esiste o sembra obsoleto
    _ensure_players_dict(torneo)
    return torneo['players_dict'].get(player_id)

def calculate_dates(start_date_str, end_date_str, total_rounds):
    """Calcola le date di inizio e fine per ogni turno, distribuendo il tempo."""
    try:
        start_date = datetime.strptime(start_date_str, DATE_FORMAT_ISO)
        end_date = datetime.strptime(end_date_str, DATE_FORMAT_ISO)
        if end_date < start_date:
            print(_("Errore: la data di fine non può precedere la data di inizio."))
            return None
        total_duration = (end_date - start_date).days + 1
        if total_rounds <= 0:
            print(_("Errore: Il numero dei turni deve essere positivo."))
            return None
        if total_duration < total_rounds:
            print(_("Attenzione: La durata totale ({duration} giorni) è inferiore al numero di turni ({rounds}).").format(duration=total_duration, rounds=total_rounds))
            print(_("Assegnando 1 giorno per turno sequenzialmente."))
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
                current_end_date = end_date
            # Assicura che le date intermedie non superino la data finale del torneo
            elif current_end_date > end_date:
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
                print(_("Avviso: Spazio insufficiente per i turni rimanenti. Il turno {round_num} inizierà il {date} (ultimo giorno).").format(round_num=round_num + 1, date=format_date_locale(end_date)))
                current_start_date = end_date
            else:
                current_start_date = next_start_candidate
        return round_dates
    except ValueError:
        print(_("Formato data non valido ('{start_date}' o '{end_date}'). Usa {date_format}.").format(start_date=start_date_str, end_date=end_date_str, date_format=DATE_FORMAT_ISO))
        return None
    except Exception as e:
        print(_("Errore nel calcolo delle date: {error}").format(error=e))
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
        print(_("Warning: Elo non valido ({player_elo} o {opponent_elo}) nel calcolo atteso.").format(player_elo=player_elo, opponent_elo=opponent_elo))
        return 0.5 # Ritorna 0.5 in caso di Elo non validi

def calculate_elo_change(player, tournament_players_dict):
    """Calcola la variazione Elo per un giocatore basata sulle partite del torneo."""
    if not player or 'initial_elo' not in player or 'results_history' not in player:
        print(_("Warning: Dati giocatore incompleti per calcolo Elo ({player_id}).").format(player_id=player.get('id', _('ID Mancante'))))
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
        print(_("Warning: Elo iniziale non valido ({elo}) per giocatore {player_id}. Usato {default_elo}].").format(elo=initial_elo, player_id=player.get('id', _('ID Mancante')), default_elo=DEFAULT_ELO))
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
            print(_("Warning: Avversario {opponent_id} non trovato o Elo mancante per calcolo Elo.").format(opponent_id=opponent_id))
            continue

        try:
            opponent_elo = float(opponent['initial_elo'])
            score = float(score)
        except (ValueError, TypeError):
            print(_("Warning: Elo avversario ({}) o score ({}) non validi per partita contro {}.").format(opponent.get('initial_elo'), score, opponent_id))
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
        # Ritorna l'Elo iniziale se non ci sono dati sufficienti
        return player.get('initial_elo', DEFAULT_ELO)
    opponent_elos = []
    total_score = 0.0
    games_played_for_perf = 0
    try:
        initial_elo = float(player['initial_elo'])
    except (ValueError, TypeError):
        initial_elo = DEFAULT_ELO # Fallback se Elo iniziale non valido
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        score = result_entry.get("score")
        # Salta BYE e partite senza avversario o punteggio
        if opponent_id is None or opponent_id == "BYE_PLAYER_ID" or score is None:
            continue
        opponent = tournament_players_dict.get(opponent_id)
        if not opponent or 'initial_elo' not in opponent:
            print(_("Warning: Avversario {opponent_id} non trovato o Elo mancante per calcolo Performance.").format(opponent_id=opponent_id))
            continue
        try:
            opponent_elo = float(opponent["initial_elo"])
            total_score += float(score)
            opponent_elos.append(opponent_elo)
            games_played_for_perf += 1
        except (ValueError, TypeError):
            print(_("Warning: Dati non validi (Elo avversario {elo}) o score ({score}) per partita vs {opponent_id} nel calcolo performance.").format(elo=opponent.get('initial_elo'), score=score, opponent_id=opponent_id))
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
                    opponent_points = float(opponent.get("points", 0.0))
                except (ValueError, TypeError):
                    print(_("Warning: Punti non validi ({points}) per avversario {opponent_id} nel calcolo Buchholz di {player_id}.").format(points=opponent.get('points'), opponent_id=opponent_id, player_id=player_id))
                buchholz_score += opponent_points
                opponent_ids_encountered.add(opponent_id)
            else:
                # Questo warning è importante
                print(_("Warning: Avversario {opponent_id} (dallo storico di {player_id}) non trovato nel dizionario giocatori per calcolo Buchholz.").format(opponent_id=opponent_id, player_id=player_id))
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
                    print(_("Warning: Punti non validi ({points}) per avversario {opponent_id} in BuchholzCut1 di {player_id}.").format(points=opponent.get('points'), opponent_id=opponent_id, player_id=player_id))
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
            opponent = players_dict.get(opponent_id)
            if opponent and 'initial_elo' in opponent:
                try:
                    opponent_elos.append(float(opponent['initial_elo']))
                except (ValueError, TypeError):
                    print(_("Warning: Elo iniziale non valido ({elo}) per avversario {opponent_id} in ARO di {player_id}.").format(elo=opponent['initial_elo'], opponent_id=opponent_id, player_id=player_id))
                opponent_ids_encountered.add(opponent_id)
            # else: Giocatore non trovato o senza Elo iniziale, non includere in ARO

    if not opponent_elos:
        return None # Nessun avversario valido trovato

    # Calcola la media e arrotonda all'intero
    aro = sum(opponent_elos) / len(opponent_elos)
    return round(aro)

def generate_pairings_for_round(torneo):
    """
    Genera gli abbinamenti per il turno corrente usando bbpPairings.exe.
    NON modifica più lo stato dei giocatori (punti/storico) per i BYE.
    Restituisce solo la lista delle partite generate.
    """
    round_number = torneo.get("current_round")
    if round_number is None:
        print(_("ERRORE: Numero turno corrente non definito nel torneo."))
        return None 
    print(_("\n--- Generazione Abbinamenti Turno {round_num} con bbpPairings ---").format(round_num=round_number))
    for player in torneo.get('players', []):
        _ricalcola_stato_giocatore_da_storico(player)
    _ensure_players_dict(torneo)
    lista_giocatori_attivi = [p.copy() for p in torneo.get('players', [])]
    if not lista_giocatori_attivi:
        print(_("Nessun giocatore attivo per il turno {round_num}.").format(round_num=round_number))
        return []
    # 1. Creare mappa ID Tornello -> StartRank e viceversa
    players_sorted_for_start_rank = sorted(
        lista_giocatori_attivi, 
        key=lambda p: (-float(p.get('initial_elo', DEFAULT_ELO)), 
                       p.get('last_name','').lower(), 
                       p.get('first_name','').lower())
    )
    
    mappa_id_a_start_rank = {p['id']: i + 1 for i, p in enumerate(players_sorted_for_start_rank)}
    mappa_start_rank_a_id = {i + 1: p['id'] for i, p in enumerate(players_sorted_for_start_rank)}
    # 2. Generare la stringa TRF
    trf_string = genera_stringa_trf_per_bbpairings(torneo, players_sorted_for_start_rank, mappa_id_a_start_rank)
    if not trf_string:
        print(_("ERRORE: Fallita generazione della stringa TRF per bbpPairings."))
        return handle_bbpairings_failure(torneo, round_number, "Fallimento generazione stringa TRF.") 
    # 3. Eseguire bbpPairings.exe
    success, bbp_output_data, bbp_message = run_bbpairings_engine(trf_string)
    all_generated_matches = [] 
    if success:
        print(_("bbpPairings eseguito con successo."))
        
        # 4. Parsare l'output delle coppie
        parsed_pairing_list = parse_bbpairings_couples_output(bbp_output_data['coppie_raw'], mappa_start_rank_a_id)
        if parsed_pairing_list is None:
            print(_("ERRORE: Fallimento parsing output coppie di bbpPairings."))
            return handle_bbpairings_failure(torneo, round_number, f"Fallimento parsing output bbpPairings:\n{bbp_message}")
        # 5. Convertire in formato `all_matches`
        for i, match_info in enumerate(parsed_pairing_list):
            match_id_counter = torneo.get("next_match_id", 1)
            current_match = {
                "id": match_id_counter,
                "round": round_number,
                "white_player_id": match_info['white_player_id'],
                "black_player_id": match_info.get('black_player_id'), 
                "result": match_info.get('result'), # Sarà "BYE" o None
            }
            all_generated_matches.append(current_match)
            torneo["next_match_id"] = match_id_counter + 1 
            # ---> IN QUESTA VERSIONE CORRETTA, NON C'È PIÙ ALCUN AGGIORNAMENTO DI STATO QUI <---
            # Le righe che aggiornavano punti, storico, avversari, colori, etc. sono state rimosse.
            # La funzione ora fa solo UNA cosa: genera gli abbinamenti.
    else: # bbpPairings.exe ha fallito
        returncode = bbp_output_data.get('returncode', -1) if bbp_output_data else -1
        if returncode == 1:
            print(_("ATTENZIONE: bbpPairings non ha trovato abbinamenti validi."))
            return handle_bbpairings_failure(torneo, round_number, "bbpPairings: Nessun abbinamento valido trovato.")
        else:
            print(_("ERRORE CRITICO da bbpPairings.exe: {message}").format(message=bbp_message))
            return handle_bbpairings_failure(torneo, round_number, f"Errore critico bbpPairings:\n{bbp_message}")
    print(_("--- Abbinamenti Turno {} generati. ---").format(round_number))
    return all_generated_matches

def handle_bbpairings_failure(torneo, round_number, error_message):
    """
    Gestisce i fallimenti di bbpPairings. Stampa un messaggio e indica fallimento.
    """
    print(_("\n--- FALLIMENTO GENERAZIONE ABBINAMENTI AUTOMATICI (Turno {round_num}) ---").format(round_num=round_number))
    print(error_message)
    print(_("Causa: bbpPairings.exe non è riuscito a generare gli abbinamenti."))
    print(_("Azione richiesta: Verificare il file 'input_bbp.trf' nella sottocartella 'bbppairings' per possibili errori di formato."))
    print(_("Oppure, considerare di effettuare gli abbinamenti per questo turno manualmente (su carta)."))
    print(_("Il torneo non può procedere automaticamente per questo turno."))
    return None

def get_input_with_default(prompt_message, default_value=None):
    default_display = str(default_value) if default_value is not None else ""
    if default_display or default_value is None: 
        user_input = input("{} [{}]: ".format(prompt_message, default_display)).strip()
        return user_input if user_input else default_value 
    else: 
        return input("{}: ".format(prompt_message)).strip()

def input_players(players_db):
    """
    Gestisce l'input dei giocatori per un torneo con una ricerca a 3 livelli:
    1. Cerca nel DB personale.
    2. Se non trovato, cerca nel DB FIDE locale.
    3. Se non trovato, procede con la creazione manuale.
    """
    players_in_tournament = []
    added_player_ids_to_tournament = set()

    print(_("\n--- Inserimento Giocatori per il Torneo ---"))
    print(_("Inserire ID locale, ID FIDE, o parte del Nome/Cognome."))
    print(_("Il programma cercherà prima nel tuo DB personale, poi nel DB FIDE scaricato."))
    while True:
        current_num_players = len(players_in_tournament)
        data_input = input(_("\nGiocatore {player_num} (o lascia vuoto per terminare): ").format(player_num=current_num_players + 1)).strip()
        if not data_input: # Logica per terminare l'inserimento
            if current_num_players < 2:
                if enter_escape(_("Ci sono meno di 2 giocatori. Continuare? (INVIO|ESCAPE)")): break
                else: continue
            else: break
        player_id_to_add = None
        player_data_from_db = None
        # --- LIVELLO 1: Ricerca nel DB Personale (`players_db`) ---
        potential_id_input = data_input.upper()
        if potential_id_input in players_db:
            player_id_to_add = potential_id_input
        else:
            matches_in_personal_db = [p for p in players_db.values() if data_input.lower() in f"{p.get('first_name','')} {p.get('last_name','')}".lower()]
            if len(matches_in_personal_db) == 1:
                player_id_to_add = matches_in_personal_db[0]['id']
            elif len(matches_in_personal_db) > 1:
                print(_("Trovati {count} giocatori nel tuo DB personale. Specifica usando l'ID locale:").format(count=len(matches_in_personal_db)))
                for i, p in enumerate(matches_in_personal_db): print(f"  {i+1}. ID: {p.get('id')} - {p.get('first_name')} {p.get('last_name')}")
                continue

        if player_id_to_add:
            print(_("Trovato giocatore nel DB personale: {} (ID: {})").format(players_db[player_id_to_add].get('first_name'), player_id_to_add))
            player_data_from_db = players_db[player_id_to_add]

        # --- LIVELLO 2: Ricerca nel DB FIDE Locale (se non trovato nel DB personale) ---
        if not player_id_to_add:
            print(_("Giocatore non trovato nel DB personale. Avvio ricerca nel DB FIDE..."))
            fide_matches = _cerca_giocatore_nel_db_fide(data_input)

            selected_fide_record = None
            if len(fide_matches) == 1:
                match = fide_matches[0]
                print(_("\n-> Trovata 1 corrispondenza nel DB FIDE:"))
                print(_("   Nome: {last_name}, {first_name} (ID FIDE: {fide_id}, FED: {fed}, Elo: {elo})").format(last_name=match['last_name'], first_name=match['first_name'], fide_id=match['id_fide'], fed=match['federation'], elo=match['elo_standard']))
                if enter_escape(_("   È questo il giocatore corretto? (INVIO|ESCAPE)")):
                    selected_fide_record = match
            elif len(fide_matches) > 1:
                print(_("\n-> Trovate {count} corrispondenze nel DB FIDE per '{term}'. Scegli quella corretta:").format(count=len(fide_matches), term=data_input))
                start_index = 0
                page_size = 15
                while True: # Loop per la paginazione
                    if start_index >= len(fide_matches):
                        print(_("Non ci sono altri risultati da mostrare. Procedo con l'inserimento manuale."))
                        selected_fide_record = None
                        break
                    # Mostra la pagina corrente di risultati
                    page_matches = fide_matches[start_index : start_index + page_size]
                    for i, match in enumerate(page_matches):
                        display_num = start_index + i + 1
                        print(f"   {display_num}. ID FIDE: {match['id_fide']:<9} | {match['last_name']}, {match['first_name']:<25} | FED: {match['federation']:<3} | Elo: {match['elo_standard']:<4}")
                    print(_("   0. Nessuno di questi / Inserimento manuale"))
                    # Costruisce il prompt per l'utente
                    prompt_text = "\n"
                    has_more_pages = (start_index + page_size) < len(fide_matches)
                    if has_more_pages:
                        prompt_text += _("Scelta (Numero, 0 per manuale, Invio per i prossimi {page_size}): ").format(page_size=page_size)
                    else:
                        prompt_text += _("Scelta (Numero o 0 per manuale): ")
                    choice_str = input(prompt_text).strip()
                    # Gestisce l'input dell'utente
                    if not choice_str and has_more_pages: # L'utente preme Invio per la pagina successiva
                        start_index += page_size
                        print(_("--- Mostro i risultati successivi ---"))
                        continue
                    elif choice_str.isdigit():
                        choice_num = int(choice_str)
                        if choice_num == 0:
                            selected_fide_record = None # Attiva l'inserimento manuale
                            break
                        elif 1 <= choice_num <= len(fide_matches):
                            selected_fide_record = fide_matches[choice_num - 1]
                            break
                        else:
                            print(_("Scelta non valida. Riprova."))
                    else:
                        print(_("Input non valido. Inserisci un numero o premi Invio."))

            # Se è stato selezionato un giocatore dal DB FIDE, crealo nel nostro DB personale
            if selected_fide_record:
                print(_("Importazione di '{first_name} {last_name}' nel tuo DB personale...").format(first_name=selected_fide_record['first_name'], last_name=selected_fide_record['last_name']))
                player_id_to_add = crea_nuovo_giocatore_nel_db(
                    players_db, 
                    first_name=selected_fide_record.get('first_name'), 
                    last_name=selected_fide_record.get('last_name'), 
                    elo=selected_fide_record.get('elo_standard'),
                    fide_title=selected_fide_record.get('title', ''),
                    sex=selected_fide_record.get('sex', 'M'),
                    federation=selected_fide_record.get('federation', ''),
                    fide_id_num_str=str(selected_fide_record.get('id_fide')),
                    birth_date=f"{selected_fide_record.get('birth_year')}-01-01" if selected_fide_record.get('birth_year') else None,
                    experienced=True # Un giocatore con rating FIDE è per definizione "experienced"
                )
                if player_id_to_add:
                    player_data_from_db = players_db[player_id_to_add]
                else:
                    print(_("Errore durante la creazione del giocatore importato. Si prega di riprovare."))
                    continue

        # --- LIVELLO 3: Creazione Manuale (se non trovato da nessuna parte) ---
        if not player_id_to_add:
            print(_("Nessuna corrispondenza trovata. Procedi con l'inserimento manuale."))
            # ... [La tua logica esistente per la raccolta manuale dei dati va qui] ...
            first_name_new_db = get_input_with_default(_("  Nome del nuovo giocatore: ")).strip().title()
            if not first_name_new_db: continue
            last_name_new_db = get_input_with_default(_("  Cognome: ")).strip().title()
            if not last_name_new_db: continue
            elo_new_db = dgt(f"  Elo (default {DEFAULT_ELO})", kind="f", fmin=500, fmax=4000, default=DEFAULT_ELO)
            fide_title_new_db = get_input_with_default(_("  Titolo FIDE (es. FM, o vuoto)"), "").strip().upper()[:3]
            sex_new_db = get_input_with_default(_("  Sesso (m/w)"), "m").strip().lower()
            fed_new_db = get_input_with_default(_("  Federazione (3 lettere, es. ITA)"), "ITA").strip().upper()[:3] or "ITA"
            fide_id_new_db = get_input_with_default(_("  ID FIDE Numerico ('0' se N/D)"), "0").strip()
            bdate_input = get_input_with_default(_(" Data Nascita ({date_format} o vuoto)").format(date_format=DATE_FORMAT_ISO), "")
            birth_date_new_db = bdate_input if bdate_input else None
            exp_new_db = enter_escape(_(" Esperienza pregressa significativa? (INVIO|ESCAPE)"))
            player_id_to_add = crea_nuovo_giocatore_nel_db(
                players_db, first_name_new_db, last_name_new_db, elo_new_db,
                fide_title_new_db, sex_new_db, fed_new_db, fide_id_new_db,
                birth_date_new_db, exp_new_db
            )
            if player_id_to_add:
                player_data_from_db = players_db.get(player_id_to_add)
        # --- Aggiunta finale del giocatore (selezionato o creato) al TORNEO ---
        if player_id_to_add and player_data_from_db:
            if player_id_to_add in added_player_ids_to_tournament:
                print(_("Errore: Giocatore ID {player_id} ({player_name}) è già stato aggiunto a questo torneo.").format(player_id=player_id_to_add, player_name=player_data_from_db.get('first_name')))
            else:
                elo_per_torneo = int(player_data_from_db.get('current_elo', DEFAULT_ELO))
                player_instance = {
                    "id": player_id_to_add,
                    "first_name": player_data_from_db.get('first_name'),
                    "last_name": player_data_from_db.get('last_name'),
                    "initial_elo": elo_per_torneo,
                    # Copia tutti gli altri campi anagrafici dal DB personale
                    **{k: v for k, v in player_data_from_db.items() if k not in ['id','first_name','last_name','initial_elo']},
                    # Azzera i campi di stato del torneo
                    "points": 0.0, "results_history": [], "opponents": set(),
                    "white_games": 0, "black_games": 0, "last_color": None,
                    "consecutive_white": 0, "consecutive_black": 0,
                    "received_bye_count": 0, "received_bye_in_round": [],
                    "withdrawn": False, "is_scheduled": False
                }
                players_in_tournament.append(player_instance)
                added_player_ids_to_tournament.add(player_id_to_add)
                print(_("-> Giocatore '{first_name} {last_name}' (ID DB: {player_id}) aggiunto al torneo.").format(first_name=player_instance['first_name'], last_name=player_instance['last_name'], player_id=player_id_to_add))
    return players_in_tournament

def ricalcola_punti_tutti_giocatori(torneo):
    """
    Forza il ricalcolo dei punti per tutti i giocatori partendo da zero,
    basandosi unicamente sulla loro cronologia dei risultati.
    Questa è la fonte di verità per i punteggi.
    """
    if not torneo or 'players' not in torneo:
        return # Non fare nulla se il torneo non è valido

    for p in torneo.get('players', []):
        p['points'] = 0.0 # Azzera i punti
        for res in p.get('results_history', []):
            p['points'] += float(res.get('score', 0.0))

def _apply_match_result_to_players(torneo, match_obj, result_str, w_score, b_score):
    """
    Funzione di supporto che applica il risultato di una partita ai due giocatori
    e aggiorna tutte le strutture dati necessarie.
    """
    current_round_num = torneo.get("current_round")
    if not current_round_num: return

    wp_id = match_obj.get('white_player_id')
    bp_id = match_obj.get('black_player_id')
    
    # Lavoriamo direttamente sul dizionario cache per coerenza
    wp_data_obj = torneo['players_dict'].get(wp_id)
    bp_data_obj = torneo['players_dict'].get(bp_id)

    if not wp_data_obj or not bp_data_obj:
        print(f"ERRORE INTERNO: Impossibile trovare i giocatori {wp_id} o {bp_id} per applicare il risultato.")
        return

    # 1. Applica i punteggi
    wp_data_obj["points"] = float(wp_data_obj.get("points", 0.0)) + w_score
    # --- ECCO LA CORREZIONE FONDAMENTALE ---
    bp_data_obj["points"] = float(bp_data_obj.get("points", 0.0)) + b_score

    # 2. Aggiorna lo storico dei risultati
    wp_data_obj.setdefault("results_history", []).append({
        "round": current_round_num, "opponent_id": bp_id,
        "color": "white", "result": result_str, "score": w_score
    })
    bp_data_obj.setdefault("results_history", []).append({
        "round": current_round_num, "opponent_id": wp_id,
        "color": "black", "result": result_str, "score": b_score
    })
    
    # 3. Aggiorna l'oggetto 'match' originale nella lista dei round
    for r in torneo.get("rounds", []):
        if r.get("round") == current_round_num:
            for i, m in enumerate(r.get("matches", [])):
                if m.get('id') == match_obj.get('id'):
                    r["matches"][i]["result"] = result_str
                    # Rimuovi la pianificazione se c'era
                    if r["matches"][i].get('is_scheduled'):
                        r["matches"][i]['is_scheduled'] = False
                    break
            break
    print(_("\nRisultato registrato con successo."))

def update_match_result(torneo):
    """
    Gestisce l'interfaccia utente per l'inserimento dei risultati,
    usando una funzione di supporto per l'applicazione dei dati.
    """
    any_changes_made_in_this_session = False
    while True:
        current_round_num = torneo["current_round"]
        if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
            torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
        players_dict = torneo['players_dict']
        current_round_data = next((r for r in torneo.get("rounds", []) if r.get("round") == current_round_num), None)
        if not current_round_data:
            print(_("ERRORE: Dati turno {round_num} non trovati.").format(round_num=current_round_num))
            return False
        pending_matches_info_list = []
        all_matches_in_this_round = current_round_data.get("matches", [])
        all_matches_this_round_sorted = sorted(all_matches_in_this_round, key=lambda m: m.get('id', 0))
        round_board_idx_counter = 0 
        for match_obj in all_matches_this_round_sorted:
            round_board_idx_counter += 1
            if match_obj.get("result") is None and match_obj.get("black_player_id") is not None:
                wp_obj = players_dict.get(match_obj.get('white_player_id'))
                bp_obj = players_dict.get(match_obj.get('black_player_id'))
                wp_name_disp = f"{wp_obj.get('first_name','N/A')} {wp_obj.get('last_name','')}" if wp_obj else _("Giocatore Mancante")
                bp_name_disp = f"{bp_obj.get('first_name','N/A')} {bp_obj.get('last_name','')}" if bp_obj else "Giocatore Mancante"
                pending_matches_info_list.append(
                    (round_board_idx_counter, match_obj, wp_name_disp, bp_name_disp)
                )
        completed_matches_to_cancel = [m for m in all_matches_this_round_sorted if m.get("result") is not None and m.get("result") != "BYE"]
        if not pending_matches_info_list and not completed_matches_to_cancel:
            if not any_changes_made_in_this_session:
                print(_("Info: Nessuna azione possibile per il turno {round_num} (nessuna partita pendente e nessuna da poter cancellare).").format(round_num=current_round_num))
            break

        if pending_matches_info_list:
            print(_("\nPartite del turno {round_num} ancora da registrare (N. Scacchiera del Turno):").format(round_num=current_round_num))
            for displayed_board_num, match_dict_disp, w_name_disp, b_name_disp in pending_matches_info_list:
                wp_elo_disp = players_dict.get(match_dict_disp['white_player_id'], {}).get('initial_elo','?')
                bp_elo_disp = players_dict.get(match_dict_disp['black_player_id'], {}).get('initial_elo','?')
                print(f"  Sc. {displayed_board_num:<2} (IDG:{match_dict_disp.get('id')}) - {w_name_disp:<20} [{wp_elo_disp:>4}] vs {b_name_disp:<20} [{bp_elo_disp:>4}]")
        else:
            print(_("\nNessuna partita da registrare per il turno {round_num} (ma potresti voler cancellare un risultato).").format(round_num=current_round_num))

        pending_board_numbers_for_prompt_display = [str(match_info_tuple[0]) for match_info_tuple in pending_matches_info_list]
        board_numbers_str_for_prompt = "-".join(pending_board_numbers_for_prompt_display) if pending_board_numbers_for_prompt_display else _("Nessuna")
        prompt_lines = [
            _("Inserisci:"),
            _("\t[p] --- per entrare in modalità programmazione partite;"),
            _("\t[r] --- per ritirare un giocatore dal torneo;"),
            _("\t[t] --- Time Machine, per tornare all'inizio di un turno;"),
            _("\t[cancella] --- per eliminare un risultato inserito;"),
            _("\t[SC] --- il numero della scacchiera;"),
            _("\t[nom*|cog*] --- parte del nome o cognome di uno dei giocatori.")]
        prompt_finale = "\n".join(prompt_lines) + _("\nP|R|T|SC|nome|cognome [{boards}]: ").format(boards=board_numbers_str_for_prompt)
        user_input_str = input(prompt_finale).strip().lower()

        if not user_input_str: 
            break 
        elif user_input_str == 't':
            if time_machine_torneo(torneo):
                any_changes_made_in_this_session = True
                save_tournament(torneo)
                print(_("Stato del torneo ripristinato e salvato."))
            continue 
        elif user_input_str.lower() == 'r':
            print(_("\n--- Ritiro Giocatore dal Torneo ---"))
            active_players_list = [p for p in torneo['players'] if not p.get('withdrawn', False)]
            if not active_players_list:
                print(_("Nessun giocatore attivo da ritirare."))
                continue
            for i, p in enumerate(active_players_list):
                print(f"  {i+1}. {p.get('first_name')} {p.get('last_name')} (ID: {p.get('id')})")
            player_to_withdraw_input = input(_("Inserisci il numero o l'ID del giocatore da ritirare (o vuoto per annullare): ")).strip()
            if not player_to_withdraw_input: continue
            player_to_withdraw_obj = None
            if player_to_withdraw_input.isdigit() and (1 <= int(player_to_withdraw_input) <= len(active_players_list)):
                player_to_withdraw_obj = active_players_list[int(player_to_withdraw_input) - 1]
            else:
                player_to_withdraw_obj = players_dict.get(player_to_withdraw_input.upper())
            if player_to_withdraw_obj and not player_to_withdraw_obj.get('withdrawn', False):
                player_name_withdraw = f"{player_to_withdraw_obj.get('first_name','?')} {player_to_withdraw_obj.get('last_name','?')}"
                confirm_prompt = _("Confermi il ritiro definitivo di {player_name}? (INVIO|ESCAPE)").format(player_name=player_name_withdraw)
                if enter_escape(confirm_prompt):
                    player_to_withdraw_obj['withdrawn'] = True
                    print(_("Giocatore {player_name} marcato come ritirato.").format(player_name=player_name_withdraw))
                    any_changes_made_in_this_session = True
                    save_tournament(torneo)
                else:
                    print(_("Ritiro annullato."))
            else:
                print(_("Giocatore non trovato o già ritirato."))
            continue
        elif user_input_str.lower() == 'p':
            print(_("\n--- Accesso al Modulo Pianificazione Partite ---"))
            if gestisci_pianificazione_partite(torneo, current_round_data, players_dict):
                any_changes_made_in_this_session = True
            continue 

        selected_match_obj_for_processing = None
        if user_input_str.lower() == 'cancella':
            if not completed_matches_to_cancel:
                print(_("Nessuna partita completata in questo turno da poter cancellare."))
                continue
            print(_("\nPartite completate nel turno {round_num} (ID Globali):").format(round_num=current_round_num))
            # ... (la logica di cancellazione, che era già corretta, va qui)
            continue
        elif user_input_str.isdigit():
            try:
                board_num_choice = int(user_input_str)
                match_found_by_board = False
                for displayed_b_num, match_obj_dict, u1, u2 in pending_matches_info_list:
                    if displayed_b_num == board_num_choice:
                        selected_match_obj_for_processing = match_obj_dict
                        match_found_by_board = True
                        break
                if not match_found_by_board:
                    print(_("Numero Scacchiera (del turno) '{board_num_choice}' non valido o partita non pendente.").format(board_num_choice=board_num_choice))
                    continue
            except ValueError:
                print(_("Input numerico per Scacchiera non valido."))
                continue
        else:
            search_term_lower = user_input_str.lower()
            candidate_matches_info = []
            for disp_b_num, match_o, wp_n, bp_n in pending_matches_info_list:
                if (search_term_lower in wp_n.lower()) or (search_term_lower in bp_n.lower()):
                    candidate_matches_info.append((disp_b_num, match_o, wp_n, bp_n))
            if not candidate_matches_info:
                print(_("Nessuna partita pendente trovata con giocatori che corrispondono a '{search_term}'.").format(search_term=user_input_str))
                continue
            elif len(candidate_matches_info) == 1:
                selected_match_obj_for_processing = candidate_matches_info[0][1]
                sel_board_disp, u1, sel_w_disp, sel_b_disp = candidate_matches_info[0]
                print(_("Trovata partita unica (Sc. {board_num}): {white_player} vs {black_player}").format(board_num=sel_board_disp, white_player=sel_w_disp, black_player=sel_b_disp))
            else: 
                print(_("Trovate {num_matches} partite pendenti per '{search_term}':").format(num_matches=len(candidate_matches_info), search_term=user_input_str))
                for disp_b_num_multi, match_d_multi, w_n_multi, b_n_multi in candidate_matches_info:
                    wp_elo_m_disp = players_dict.get(match_d_multi['white_player_id'], {}).get('initial_elo','?')
                    bp_elo_m_disp = players_dict.get(match_d_multi['black_player_id'], {}).get('initial_elo','?')
                    print(f"  Sc. {disp_b_num_multi:<2} (IDG:{match_d_multi.get('id')}) - {w_n_multi:<20} [{wp_elo_m_disp:>4}] vs {b_n_multi:<20} [{bp_elo_m_disp:>4}]")
                try:
                    specific_board_input = input(_("Inserisci il N.Scacchiera (del turno) desiderato dalla lista sopra: ")).strip()
                    if not specific_board_input.isdigit():
                        print(_("Input non numerico per la scacchiera.")); continue
                    specific_board_choice = int(specific_board_input)
                    for disp_b_num_cand, match_obj_cand, u1, u2 in candidate_matches_info:
                        if disp_b_num_cand == specific_board_choice:
                            selected_match_obj_for_processing = match_obj_cand
                            break
                    if not selected_match_obj_for_processing:
                        print(_("N.Scacchiera '{board_choice}' non valido dalla lista filtrata.").format(board_choice=specific_board_choice))
                        continue
                except ValueError: print(_("Input Scacchiera non valido.")); continue
        if selected_match_obj_for_processing:
            wp_data_obj = players_dict.get(selected_match_obj_for_processing['white_player_id'])
            bp_data_obj = players_dict.get(selected_match_obj_for_processing['black_player_id'])
            wp_name_match_disp = f"{wp_data_obj.get('first_name','?')} {wp_data_obj.get('last_name','?')}"
            bp_name_match_disp = f"{bp_data_obj.get('first_name','?')} {bp_data_obj.get('last_name','?')}"
            sel_msg = _("Partita selezionata per risultato: {white} vs {black} (ID Glob: {match_id})")
            print(sel_msg.format(white=wp_name_match_disp, black=bp_name_match_disp, match_id=selected_match_obj_for_processing['id']))
            result_input = dgt(_("Risultati: [1-0, 0-1, 1/2, 0-0F, 1-F, F-1]: "),kind="s",smin=3,smax=4)
            result_map = {
                "1-0": ("1-0", 1.0, 0.0), "0-1": ("0-1", 0.0, 1.0),
                "1/2": ("1/2-1/2", 0.5, 0.5), "1-F": ("1-F", 1.0, 0.0),
                "F-1": ("F-1", 0.0, 1.0), "0-0F": ("0-0F", 0.0, 0.0)
            }
            if result_input in result_map:
                res_str, w_score, b_score = result_map[result_input]
                confirm_message_str = _("Confermi risultato?")
                if res_str == "1-0":
                    confirm_message_str = _("Confermi che {winner} vince contro {loser}? (INVIO|ESCAPE): ").format(winner=wp_name_match_disp, loser=bp_name_match_disp)
                elif res_str == "0-1":
                    confirm_message_str = _("Confermi che {winner} vince contro {loser}? (INVIO|ESCAPE): ").format(winner=bp_name_match_disp, loser=wp_name_match_disp)
                elif res_str == "1/2-1/2":
                     confirm_message_str = _("Confermi che {player1} e {player2} pattano? (INVIO|ESCAPE): ").format(player1=wp_name_match_disp, player2=bp_name_match_disp)
                user_confirm_input = enter_escape(confirm_message_str)
                if user_confirm_input == True:
                    _apply_match_result_to_players(torneo, selected_match_obj_for_processing, res_str, w_score, b_score)
                    any_changes_made_in_this_session = True
                    save_tournament(torneo)
                    if "F" in res_str:
                        forfeiting_player_id = bp_data_obj['id'] if res_str == "1-F" else wp_data_obj['id']
                        forfeiting_player_obj = players_dict.get(forfeiting_player_id)
                        player_name_forfeit = f"{forfeiting_player_obj.get('first_name','?')} {forfeiting_player_obj.get('last_name','?')}"
                        withdraw_choice = enter_escape(_("Il giocatore {player_name} si ritira definitivamente dal torneo? (INVIO|ESCAPE)").format(player_name=player_name_forfeit))
                        if withdraw_choice == True:
                            forfeiting_player_obj['withdrawn'] = True
                            print(_("Giocatore {player_name} marcato come ritirato.").format(player_name=player_name_forfeit))
                else:
                    print(_("Operazione annullata dall'utente."))
            else:
                print(_("Input risultato non valido."))
    return any_changes_made_in_this_session

def save_current_tournament_round_file(torneo):
    """
    Salva lo stato del turno corrente in un file TXT che viene sovrascritto.
    Mostra intestazione, partite da giocare (pianificate e non), e partite giocate.
    I giocatori ritirati sono raggruppati in fondo a ciascuna sezione.
    Utilizza 1 spazio per livello di indentazione.
    """
    tournament_name_for_file = torneo.get('name', 'Torneo_Senza_Nome')
    sanitized_name = sanitize_filename(tournament_name_for_file)
    current_round_num = torneo.get("current_round")

    if current_round_num is None:
        print(_("Salvataggio file turno corrente: Numero turno non definito."))
        return
    filename = _("Tornello - {name} - Turno corrente.txt").format(name=sanitized_name)
    round_data = None
    for rnd in torneo.get("rounds", []):
        if rnd.get("round") == current_round_num:
            round_data = rnd
            break
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players', [])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    players_dict = torneo['players_dict']
    round_dates_info = torneo.get("round_dates", [])
    current_round_period_info = next((rd for rd in round_dates_info if rd.get("round") == current_round_num), None)
    start_date_turn_display = format_date_locale(current_round_period_info.get('start_date')) if current_round_period_info else "N/D"
    end_date_turn_display = format_date_locale(current_round_period_info.get('end_date')) if current_round_period_info else "N/D"
    # --- INIZIO MODIFICHE: Smistamento partite in liste separate per attivi e ritirati ---
    played_matches_active = []
    played_matches_withdrawn = []
    scheduled_pending_active = []
    scheduled_pending_withdrawn = []
    unscheduled_pending_active = []
    unscheduled_pending_withdrawn = []
    bye_player_display_line = None
    all_matches_in_round = []
    if round_data and "matches" in round_data:
        all_matches_in_round = sorted(round_data.get("matches", []), key=lambda m: m.get('id', 0))
    # Gestione caso turno vuoto (invariata)
    if not all_matches_in_round and round_data is None:
        try:
            with open(filename, "w", encoding='utf-8-sig') as f:
                f.write(_("Nome Torneo: {name} - ").format(name=tournament_name_for_file))
                f.write(_("Turno: {round_num}\n").format(round_num=current_round_num))
                f.write(_(" Periodo Turno: {start} - {end}\n\n").format(start=start_date_turn_display, end=end_date_turn_display))
                f.write(_(" (Nessuna partita ancora definita o caricata per questo turno)\n"))
            print(_("File stato turno corrente '{filename}' aggiornato (turno non ancora popolato o vuoto).").format(filename=filename))
        except IOError as e:
            print(_("Errore scrittura file stato turno corrente '{filename}': {error}").format(filename=filename, error=e))
        return

    # Ciclo di smistamento modificato
    for match in all_matches_in_round:
        wp_obj = players_dict.get(match.get('white_player_id'))
        bp_obj = players_dict.get(match.get('black_player_id'))
        
        if bp_obj is None and wp_obj is not None: # È un BYE
            bye_player_display_line = _(" {first_name} {last_name} ha il BYE").format(first_name=wp_obj.get('first_name', '?'), last_name=wp_obj.get('last_name', '?'))
            continue
        if bp_obj is None or wp_obj is None: # Partita corrotta o invalida
            continue
            
        # Aggiungi il flag [RIT] ai nomi dei giocatori ritirati
        wp_name = f"{wp_obj.get('first_name',_('Bianco?'))} {wp_obj.get('last_name','')}"
        if wp_obj.get('withdrawn'): wp_name += " [RIT]"
        bp_name = f"{bp_obj.get('first_name',_('Nero?'))} {bp_obj.get('last_name','')}"
        if bp_obj.get('withdrawn'): bp_name += " [RIT]"
        
        match_id_display = match.get('id', '?')
        is_withdrawn_match = wp_obj.get('withdrawn', False) or bp_obj.get('withdrawn', False)

        if match.get("result") is not None:
            line = f"  IDG:{match_id_display} {wp_name} - {bp_name}  {match.get('result')}"
            (played_matches_withdrawn if is_withdrawn_match else played_matches_active).append(line)
        else:
            if match.get("is_scheduled") and match.get("schedule_info"):
                schedule = match.get("schedule_info")
                try:
                    s_date = datetime.strptime(schedule.get("date"), DATE_FORMAT_ISO).date()
                    s_time = datetime.strptime(schedule.get("time"), "%H:%M").time()
                    sortable_datetime = datetime.combine(s_date, s_time)
                    details_tuple = (sortable_datetime, match, schedule, wp_name, bp_name)
                    (scheduled_pending_withdrawn if is_withdrawn_match else scheduled_pending_active).append(details_tuple)
                except (ValueError, TypeError) as e_dt:
                    line = _(" IDG:{match_id} {white_player} - {black_player} (Pianificazione Errata)").format(match_id=match_id_display, white_player=wp_name, black_player=bp_name)
                    (unscheduled_pending_withdrawn if is_withdrawn_match else unscheduled_pending_active).append(line)
            else:
                line = f"   IDG:{match_id_display} {wp_name} - {bp_name}"
                (unscheduled_pending_withdrawn if is_withdrawn_match else unscheduled_pending_active).append(line)

    # Ordina entrambe le liste di partite pianificate
    scheduled_pending_active.sort(key=lambda x: x[0])
    scheduled_pending_withdrawn.sort(key=lambda x: x[0])

    # Scrittura su file con la nuova logica di raggruppamento
    try:
        with open(filename, "w", encoding='utf-8-sig') as f:
            # Intestazione (Livello 0)
            f.write(f"Nome Torneo: {tournament_name_for_file} - ")
            f.write(f"Turno: {current_round_num}\n")
            f.write(f" Periodo Turno: {start_date_turn_display} - {end_date_turn_display}\n\n")
            
            # Sezione Partite da giocare (Titolo Livello 1)
            f.write(" Partite da giocare\n")
            
            # --- Partite Pianificate ---
            current_printed_date_str = None
            if not scheduled_pending_active:
                f.write(_("  (Nessuna partita con giocatori attivi è attualmente pianificata con data/ora)\n"))
            else:
                for dt_obj, match, schedule, wp_n, bp_n in scheduled_pending_active:
                    match_date_iso = schedule.get('date')
                    if match_date_iso != current_printed_date_str:
                        f.write(f"  {format_date_locale(match_date_iso)}\n")
                        current_printed_date_str = match_date_iso
                    time_str = schedule.get('time', 'HH:MM')
                    f.write(f"   {time_str} IDG:{match.get('id', '?')}, {wp_n} vs {bp_n}, Canale: {schedule.get('channel', 'N/D')}, Arbitro: {schedule.get('arbiter', 'N/D')}\n")
            # --- Partite Non Pianificate ---
            f.write(_("  Non pianificate (giocatori attivi):\n"))
            if unscheduled_pending_active:
                for line in unscheduled_pending_active: f.write(f"{line}\n")
            else:
                f.write(_("   (nessuna)\n"))
            # --- Sezione Ritirati (se presente) ---
            if scheduled_pending_withdrawn or unscheduled_pending_withdrawn:
                f.write(_("\n  -- Partite da giocare con giocatori ritirati --\n"))
                current_printed_date_withdrawn = None
                for dt_obj, match, schedule, wp_n, bp_n in scheduled_pending_withdrawn:
                    match_date_iso = schedule.get('date')
                    if match_date_iso != current_printed_date_withdrawn:
                        f.write(f"   {format_date_locale(match_date_iso)}\n")
                        current_printed_date_withdrawn = match_date_iso
                    time_str = schedule.get('time', 'HH:MM')
                    f.write(f"    {time_str} IDG:{match.get('id', '?')}, {wp_n} vs {bp_n}, Canale: {schedule.get('channel', 'N/D')}, Arbitro: {schedule.get('arbiter', 'N/D')}\n")
                if unscheduled_pending_withdrawn:
                    f.write(_("   Non pianificate (con ritirati):\n"))
                    for line in unscheduled_pending_withdrawn: f.write(f"   {line.strip()}\n") # Rimuovi e ri-applica indentazione per coerenza
            if bye_player_display_line:
                f.write(f"\n{bye_player_display_line}\n")
            # Sezione Partite Giocate (Titolo Livello 1)
            f.write(_(" Partite giocate\n"))
            if played_matches_active:
                for line in played_matches_active: f.write(f"{line}\n")
            else:
                 f.write(_("  (nessuna partita ancora giocata da giocatori attivi)\n"))
            if played_matches_withdrawn:
                f.write(_("  -- Partite giocate con giocatori ritirati --\n"))
                for line in played_matches_withdrawn: f.write(f"{line}\n")
        print(_("File {filename} aggiornato con raggruppamento ritirati.").format(filename=filename))
    except IOError as e:
        print(f"Errore durante la sovrascrittura del file stato turno corrente '{filename}': {e}")
    except Exception as e_general:
        print(_("Errore imprevisto in save_current_tournament_round_file: {error}").format(error=e_general))
        traceback.print_exc()

def append_completed_round_to_history_file(torneo, completed_round_number):
    """
    Salva i dettagli di un turno concluso in un FILE SEPARATO per quel turno.
    Il file viene creato o sovrascritto.
    """
    tournament_name = torneo.get('name', 'Torneo_Senza_Nome')
    sanitized_name = sanitize_filename(tournament_name)
    # NUOVO NOME FILE: specifico per il turno
    filename = _("Tornello - {name} - Turno {round_num} Dettagli.txt").format(name=sanitized_name, round_num=completed_round_number)

    round_data = None
    for rnd in torneo.get("rounds", []):
        if rnd.get("round") == completed_round_number:
            round_data = rnd
            break
    
    if round_data is None or "matches" not in round_data:
        print(_("Dati o partite del turno concluso {round_num} non trovati per il salvataggio.").format(round_num=completed_round_number))
        return

    # Assicura che il dizionario dei giocatori sia aggiornato
    _ensure_players_dict(torneo)
    players_dict = torneo['players_dict']
    all_matches_in_round = round_data.get("matches", [])
    playable_matches = [m for m in all_matches_in_round if m.get("black_player_id") is not None]
    bye_match = next((m for m in all_matches_in_round if m.get("black_player_id") is None), None)

    def get_average_elo_for_sort(match, players_dict_local):
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
        # Apri in modalità "w" (scrittura) per creare/sovrascrivere il file specifico del turno
        with open(filename, "w", encoding='utf-8-sig') as f:
            # Scrivi sempre l'intestazione completa del torneo e del turno per questo file
            f.write(_("Torneo: {name}\n").format(name=torneo.get('name', _('Nome Mancante'))))
            f.write(_("Sito: {site}, Data Inizio Torneo: {start_date}\n").format(site=torneo.get('site', 'N/D'), start_date=format_date_locale(torneo.get('start_date'))))
            f.write("=" * 80 + "\n")
            f.write("\n" + "="*30 + _(" DETTAGLIO TURNO {round_num} CONCLUSO ").format(round_num=completed_round_number) + "="*26 + "\n")
            round_dates_list = torneo.get("round_dates", [])
            current_round_dates = next((rd for rd in round_dates_list if rd.get("round") == completed_round_number), None)
            if current_round_dates:
                start_d_str = current_round_dates.get('start_date')
                end_d_str = current_round_dates.get('end_date')
                f.write(_("\tPeriodo del Turno: {start} - {end}\n").format(start=format_date_locale(start_d_str), end=format_date_locale(end_d_str)))
            else:
                f.write(_("\tPeriodo del Turno: Date non trovate\n"))
            f.write("\t"+"-" * 76 + "\n")
            header_partite = _("Sc | ID  | Bianco                       [Elo] (Pt) - Nero                         [Elo] (Pt) | Risultato")
            f.write(f"\t{header_partite}\n")
            f.write(f"\t" + "-" * len(header_partite) + "\n")
            for board_num_idx, match in enumerate(playable_matches):
                board_num = board_num_idx + 1
                match_id = match.get('id', '?')
                white_p_id = match.get('white_player_id')
                black_p_id = match.get('black_player_id')
                result_str = match.get("result", _("ERRORE_RISULTATO_MANCANTE"))
                white_p = players_dict.get(white_p_id)
                black_p = players_dict.get(black_p_id)
                w_name = "? ?"
                w_elo = "?"
                w_pts = "?"
                if white_p:
                    w_name = f"{white_p.get('first_name','?')} {white_p.get('last_name','')}"
                    w_elo = white_p.get('initial_elo','?')
                    # Recupera i punti che il giocatore aveva *alla fine di quel turno*
                    # Questo è più complesso, per ora usiamo i punti correnti come approssimazione o li omettiamo se troppo difficile.
                    # Per semplicità, usiamo i punti totali correnti dal dizionario principale.
                    w_pts = format_points(white_p.get('points', 0.0))
                b_name = "? ?"
                b_elo = "?"
                b_pts = "?"
                if black_p:
                    b_name = f"{black_p.get('first_name','?')} {black_p.get('last_name','')}"
                    b_elo = black_p.get('initial_elo','?')
                    b_pts = format_points(black_p.get('points', 0.0))
                line = (f"{board_num:<3}| "
                        f"{match_id:<4}| "
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
                    line = _("{dashes:<3}| {match_id:<4}| Errore Giocatore Bye ID: {player_id:<10} | BYE").format(dashes='---', match_id=match_id, player_id=white_p_id)
                    f.write(f"\t{line}\n")
        print(_("Dettaglio Turno Concluso {round_num} salvato nel file separato '{filename}'").format(round_num=completed_round_number, filename=filename))
    except IOError as e:
        print(_("Errore durante il salvataggio del file del turno '{filename}': {error}").format(filename=filename, error=e))
    except Exception as general_e:
        print(_("Errore inatteso durante il salvataggio del file del turno: {error}").format(error=general_e))
        traceback.print_exc()

def save_standings_text(torneo, final=False):
    """
    Salva/Sovrascrive la classifica (parziale o finale) in un unico file TXT.
    Mostra sempre gli spareggi, incluso ARO. Mostra Perf/Var Elo solo alla fine.
    """
    ricalcola_punti_tutti_giocatori(torneo)
    players = torneo.get("players", [])
    if not players:
        print(_("Attenzione: Nessun giocatore per generare la classifica."))
        return
    
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(players):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    
    print(_("Calcolo/Aggiornamento spareggi per classifica..."))
    for p in players:
        p_id = p.get('id')
        if not p_id: continue
        p["buchholz"] = compute_buchholz(p_id, torneo)
        p["buchholz_cut1"] = compute_buchholz_cut1(p_id, torneo)
        p["aro"] = compute_aro(p_id, torneo)
        if p.get("withdrawn", False):
            p["final_rank"] = "RIT"

    def sort_key_standings(player_item):
        points_val = float(player_item.get("points", -999))
        status_val = 1 if not player_item.get("withdrawn", False) else 0
        bucch_c1_val = float(player_item.get("buchholz_cut1", -1.0) if player_item.get("buchholz_cut1") is not None else -1.0)
        bucch_tot_val = float(player_item.get("buchholz", 0.0))
        aro_val = float(player_item.get("aro", 0.0) if player_item.get("aro") is not None else 0.0)
        elo_initial_val = int(player_item.get("initial_elo", 0))
        return (-points_val, -status_val, -bucch_c1_val, -bucch_tot_val, -aro_val, -elo_initial_val)

    try:
        players_sorted = sorted(players, key=sort_key_standings)
        if not final or (players_sorted and "final_rank" not in players_sorted[0] and not players_sorted[0].get("withdrawn")):
            current_display_rank = 0
            last_sort_key_tuple = None
            for i, p_item in enumerate(players_sorted):
                if p_item.get("withdrawn", False):
                    p_item["display_rank"] = "RIT"
                    continue
                current_sort_key_tuple = sort_key_standings(p_item)
                if current_sort_key_tuple != last_sort_key_tuple:
                    current_display_rank = i + 1
                p_item["display_rank"] = current_display_rank
                last_sort_key_tuple = current_sort_key_tuple
        elif final:
            for i, p_item in enumerate(players_sorted):
                if "final_rank" in p_item:
                    p_item["display_rank"] = p_item["final_rank"]
                elif p_item.get("withdrawn", False):
                    p_item["display_rank"] = "RIT"
                else:
                    p_item["display_rank"] = i + 1
    except Exception as e:
        print(f"Errore durante l'ordinamento dei giocatori per la classifica: {e}")
        traceback.print_exc()
        players_sorted = players

    tournament_name_file = torneo.get('name', 'Torneo_Senza_Nome')
    sanitized_name_file = sanitize_filename(tournament_name_file)
    filename = _("Tornello - {name} - Classifica.txt").format(name=sanitized_name_file)
    # ... (il resto della logica per il titolo del file rimane uguale) ...
    status_line = ""
    if final:
        status_line = _("CLASSIFICA FINALE")
    else:
        current_round_in_state = torneo.get("current_round", 0)
        has_any_results = any(p.get("results_history") for p in players)
        if not has_any_results and current_round_in_state == 1:
            status_line = _("Elenco Iniziale Partecipanti (Prima del Turno 1)")
        else:
            round_for_title = current_round_in_state
            all_matches_for_current_round_done = True
            if not final and current_round_in_state > 0 and current_round_in_state <= torneo.get("total_rounds",0):
                for r_data in torneo.get("rounds", []):
                    if r_data.get("round") == current_round_in_state:
                        for m in r_data.get("matches", []):
                            if m.get("result") is None and m.get("black_player_id") is not None:
                                all_matches_for_current_round_done = False
                                break
                        break
                if all_matches_for_current_round_done and current_round_in_state > 0 :
                        status_line = _("Classifica Parziale - Dopo Turno {round_num}").format(round_num=current_round_in_state)
                elif current_round_in_state > 0 :
                        status_line = _("Classifica Parziale - Durante Turno {round_num}").format(round_num=current_round_in_state)
    
    try:
        with open(filename, "w", encoding='utf-8-sig') as f:
            # ... (la scrittura dell'header del file rimane la stessa) ...
            f.write(_("Nome Torneo: {name}\n").format(name=torneo.get('name', 'N/D')))
            f.write(_("Luogo: {site}\n").format(site=torneo.get('site', 'N/D')))
            f.write(_("Date: {start_date} - {end_date}\n").format(start_date=format_date_locale(torneo.get('start_date')), end_date=format_date_locale(torneo.get('end_date'))))
            f.write(_("Federazione Organizzante: {fed}\n").format(fed=torneo.get('federation_code', 'N/D')))
            f.write(_("Arbitro Capo: {arbiter}\n").format(arbiter=torneo.get('chief_arbiter', 'N/D')))
            deputy_arbiters_str = torneo.get('deputy_chief_arbiters', '')
            if deputy_arbiters_str and deputy_arbiters_str.strip():
                f.write(_("Vice Arbitri: {arbiters}\n").format(arbiters=deputy_arbiters_str))
            f.write(_("Controllo Tempo: {time_control}\n").format(time_control=torneo.get('time_control', 'N/D')))
            f.write(_("Sistema di Abbinamento: Svizzero Olandese (via bbpPairings)\n"))
            f.write(_("Data Report: {date} {time}\n").format(date=format_date_locale(datetime.now().date()), time=datetime.now().strftime('%H:%M:%S')))
            f.write("-" * 70 + "\n")
            f.write(f"{status_line}\n") # Aggiunto lo status calcolato
            f.write("-" * 70 + "\n")

            # --- MODIFICA HEADER TABELLA ---
            header_table = _("Pos. Titolo Nome Cognome               [EloIni] Punti  Bucch-1  Bucch    ARO ")
            if final:
                header_table += " Perf  Elo Var."
            f.write(header_table + "\n")
            f.write("-" * len(header_table) + "\n")
            
            for player in players_sorted:
                rank_to_show = player.get("display_rank", "?")
                rank_display_str = f"{int(rank_to_show):>3}." if isinstance(rank_to_show, (int, float)) else f"{str(rank_to_show):>3} "
                
                fide_title = str(player.get('fide_title', '')).strip().upper()
                player_name_str = f"{player.get('last_name', 'N/D')}, {player.get('first_name', 'N/D')}"
                
                title_display_str = f"{fide_title:<3}"
                name_display_str = f"{player_name_str:<27.27}"
                elo_ini_str = f"[{int(player.get('initial_elo', DEFAULT_ELO)):4d}]"
                points_str = f"{float(player.get('points', 0.0)):5.1f}"
                
                bucch_c1_val = player.get('buchholz_cut1')
                bucch_c1_str = f"{float(bucch_c1_val):7.2f}" if bucch_c1_val is not None and not player.get("withdrawn") else "   ----"
                
                bucch_tot_val = player.get('buchholz')
                bucch_tot_str = f"{float(bucch_tot_val):6.2f}" if bucch_tot_val is not None and not player.get("withdrawn") else "  ----"

                aro_val = player.get('aro')
                aro_str = f"{int(aro_val):4d}" if aro_val is not None and not player.get("withdrawn") else " ---"
                
                # --- MODIFICA RIGA DATI ---
                line = (f"{rank_display_str} {title_display_str} {name_display_str} "
                        f"{elo_ini_str} {points_str} {bucch_c1_str} {bucch_tot_str} {aro_str}")

                if final:
                    if player.get("withdrawn", False):
                        perf_str, elo_change_str = "----", " ---"
                    else:
                        perf_val = player.get('performance_rating')
                        perf_str = f"{int(perf_val):4d}" if perf_val is not None else "----"
                        elo_change_val = player.get('elo_change')
                        elo_change_str = f"{int(elo_change_val):+4d}" if elo_change_val is not None else " ---"
                    line += f" {perf_str} {elo_change_str}"
                
                if player.get("withdrawn", False):
                    line = f"{line.ljust(90)} [RITIRATO]"
                
                f.write(line + "\n")
            
            print(_("File classifica '{filename}' salvato/sovrascritto.").format(filename=filename))
    except IOError as e:
        print(_("Errore durante il salvataggio del file classifica '{filename}': {error}").format(filename=filename, error=e))
    except Exception as general_e:
        print(f"Errore inatteso durante save_standings_text: {general_e}")
        traceback.print_exc()

# --- Main Application Logic ---
def display_status(torneo):
    """Mostra lo stato attuale del torneo."""
    print(_("\n--- Stato Torneo ---"))
    print(_("Nome: {name}").format(name=torneo.get('name', 'N/D')))
    start_d_str = torneo.get('start_date')
    end_d_str = torneo.get('end_date')
    print(_("Periodo: {start} - {end}").format(start=format_date_locale(start_d_str), end=format_date_locale(end_d_str)))
    current_r = torneo.get('current_round', '?')
    total_r = torneo.get('total_rounds', '?')
    print(_("Turno Corrente: {current} / {total}").format(current=current_r, total=total_r))
    now = datetime.now()
    # Mostra date turno corrente
    round_dates_list = torneo.get("round_dates", [])
    current_round_dates = next((rd for rd in round_dates_list if rd.get("round") == current_r), None)
    if current_round_dates:
        r_start_str = current_round_dates.get('start_date')
        r_end_str = current_round_dates.get('end_date')
        print(_("Periodo Turno {round_num}: {start} - {end}").format(round_num=current_r, start=format_date_locale(r_start_str), end=format_date_locale(r_end_str)))
        try:
            # Calcola giorni rimanenti per il turno
            round_end_dt = datetime.strptime(r_end_str, DATE_FORMAT_ISO).replace(hour=23, minute=59, second=59)
            time_left_round = round_end_dt - now
            if time_left_round.total_seconds() < 0:
                print(_(" -> Termine turno superato da {days} giorni.").format(days=abs(time_left_round.days)))
            else:
                days_left_round = time_left_round.days
                if days_left_round == 0 and time_left_round.total_seconds() > 0:
                    print(_(" -> Ultimo giorno per completare il turno."))
                elif days_left_round > 0:
                    print(_(" -> Giorni rimanenti per il turno: {days}").format(days=days_left_round))
        except (ValueError, TypeError):
            # Ignora errore se le date non sono valide
            pass
    # Mostra giorni rimanenti alla fine del torneo
    try:
        tournament_end_dt = datetime.strptime(end_d_str, DATE_FORMAT_ISO).replace(hour=23, minute=59, second=59)
        time_left_tournament = tournament_end_dt - now
        if time_left_tournament.total_seconds() < 0:
            print(_("Termine torneo superato."))
        else:
            days_left_tournament = time_left_tournament.days
            if days_left_tournament == 0 and time_left_tournament.total_seconds() > 0:
                print(f"Ultimo giorno del torneo.")
            elif days_left_tournament > 0:
                print(_("Giorni rimanenti alla fine del torneo: {days}").format(days=days_left_tournament))
    except (ValueError, TypeError):
        print(_("Data fine torneo ('{date}') non valida per calcolo giorni rimanenti.").format(date=format_date_locale(end_d_str)))
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
                        pending_match_count += 1
            break # Trovato il round corrente, esci dal loop
    if found_current_round_data:
        if pending_match_count > 0:
            print(_("\nPartite da giocare/registrare per il Turno {round_num}: {count}").format(round_num=current_r, count=pending_match_count))
            # La lista dettagliata verrà mostrata da update_match_result
        else:
            # Se il turno corrente è valido e non ci sono partite pendenti
            if current_r is not None and total_r is not None and current_r <= total_r:
               print(_("\nTutte le partite del Turno {round_num} sono state registrate.").format(round_num=current_r))
    # Caso: il torneo è finito (turno corrente > totale)
    elif current_r is not None and total_r is not None and current_r > total_r:
        print(_("\nIl torneo è concluso."))
    else: # Caso: dati del turno corrente non trovati (potrebbe essere un errore)
        print(_("\nDati per il Turno {round_num} non trovati o turno non valido.").format(round_num=current_r))
    print("--------------------\n")

def finalize_tournament(torneo, players_db, current_tournament_filename):
    """
    Completa il torneo: calcola Elo/Performance/Spareggi, aggiorna DB giocatori,
    e archivia tutti i file del torneo in una sottocartella dedicata.
    Restituisce True se la finalizzazione (inclusa l'archiviazione) ha avuto successo, False altrimenti.
    """
    tournament_name_original = torneo.get('name')
    if not tournament_name_original:
        print(_("ERRORE CRITICO: Nome del torneo non presente nell'oggetto torneo. Impossibile finalizzare."))
        return False
    print(_("\n--- Finalizzazione Torneo: {name} ---").format(name=tournament_name_original))
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players', [])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    num_players = len(torneo.get('players', []))
    if num_players == 0:
        print(_("Nessun giocatore nel torneo, impossibile finalizzare."))
        return False
    # --- Fase 1: Determina K-Factor e conta partite giocate nel torneo ---
    print(_("Accesso al DB e calcolo K-Factor e partite giocate..."))
    tournament_start_date = torneo.get('start_date')
    for p in torneo.get('players', []):
        player_id = p.get('id')
        if not player_id or p.get("withdrawn", False):
            p['k_factor'] = None 
            p['games_this_tournament'] = 0
            continue
        player_db_data = players_db.get(player_id)
        if not player_db_data:
            # print(f"WARN finalize: Dati DB non trovati per {player_id}, K-Factor userà default.") # Meno verboso
            p['k_factor'] = DEFAULT_K_FACTOR
        else:
            p['k_factor'] = get_k_factor(player_db_data, tournament_start_date)
        games_count = 0
        for result_entry in p.get("results_history", []):
            if result_entry.get("opponent_id") and \
               result_entry.get("opponent_id") != "BYE_PLAYER_ID" and \
               result_entry.get("score") is not None:
                # Considera anche di escludere i forfeit "0-0F" se necessario
                # if result_entry.get("result") != "0-0F":
                games_count += 1
        p['games_this_tournament'] = games_count
    # --- Fase 2: Calcola Spareggi, Performance, Elo Change ---
    print(_("Ricalcolo finale Buchholz, ARO, Performance Rating, Variazione Elo..."))
    players_dict_for_calculations = torneo['players_dict'] # Usiamo il dizionario per coerenza
    for p in torneo.get('players', []):
        p_id = p.get('id')
        if not p_id or p.get("withdrawn", False):
            p["buchholz"] = 0.0
            p["buchholz_cut1"] = None # O 0.0 se preferisci non avere None
            p["aro"] = None
            p["performance_rating"] = None
            p["elo_change"] = None
            continue

        p["buchholz"] = compute_buchholz(p_id, torneo)
        p["buchholz_cut1"] = compute_buchholz_cut1(p_id, torneo)
        p["aro"] = compute_aro(p_id, torneo)
        p["performance_rating"] = calculate_performance_rating(p, players_dict_for_calculations)
        p["elo_change"] = calculate_elo_change(p, players_dict_for_calculations) # Usa K da p['k_factor']

    # --- Fase 3: Ordinamento Finale e Assegnazione Rank ---
    print(_("Ordinamento classifica finale..."))
    def sort_key_final(player):
        points = float(player.get("points", -999))
        status_val = 1 if not player.get("withdrawn", False) else 0 # 1 per attivo, 0 per ritirato
        bucch_c1 = float(player.get("buchholz_cut1", -1.0) if player.get("buchholz_cut1") is not None else -1.0)
        bucch_tot = float(player.get("buchholz", 0.0))
        performance = int(player.get("performance_rating", -1) if player.get("performance_rating") is not None else -1)
        elo_initial = int(player.get("initial_elo", 0))
        # Ordina per: Punti (desc), Stato (attivi prima), Spareggi (desc)
        return (-points, -status_val, -bucch_c1, -bucch_tot, -performance, -elo_initial)
    try:
        players_sorted = sorted(torneo.get('players', []), key=sort_key_final)
        current_visual_rank = 0
        last_sort_key_tuple_for_rank = None
        for i, p_item in enumerate(players_sorted):
            if p_item.get("withdrawn", False):
                p_item["final_rank"] = "RIT"
                continue
            
            # Genera la tupla di spareggio per il confronto, escludendo l'indicatore attivo/ritirato
            current_sort_key_tuple_for_rank = sort_key_final(p_item)[1:] 
            
            if current_sort_key_tuple_for_rank != last_sort_key_tuple_for_rank:
                current_visual_rank = i + 1
            p_item["final_rank"] = current_visual_rank
            last_sort_key_tuple_for_rank = current_sort_key_tuple_for_rank
        torneo['players'] = players_sorted 
    except Exception as e_sort:
        print(_("Errore durante l'ordinamento dei giocatori per la classifica: {error}").format(error=e))
        traceback.print_exc()
        # Non interrompere la finalizzazione, ma la classifica potrebbe non essere ordinata.

    # --- Fase 4: Salva Classifica Finale TXT (nella directory corrente, prima dell'archiviazione) ---
    print(_("Salvataggio classifica finale su file di testo..."))
    save_standings_text(torneo, final=True)

    # --- Fase 5: Aggiornamento Database Giocatori ---
    print(_("Aggiornamento Database Giocatori (Elo, partite, storico tornei)..."))
    db_updated_count = 0
    for p_final_data in torneo.get('players', []):
        player_id = p_final_data.get('id')
        if not player_id: continue

        if player_id in players_db:
            db_player_record = players_db[player_id]
            elo_change_from_tournament = p_final_data.get('elo_change')
            games_played_in_tournament = p_final_data.get('games_this_tournament', 0)

            if elo_change_from_tournament is not None:
                try:
                    current_elo_in_db = int(db_player_record.get('current_elo', DEFAULT_ELO))
                    db_player_record['current_elo'] = current_elo_in_db + elo_change_from_tournament
                except (ValueError, TypeError): # Fallback se current_elo non è valido
                    db_player_record['current_elo'] = int(DEFAULT_ELO) + elo_change_from_tournament
            
            db_player_record['games_played'] = db_player_record.get('games_played', 0) + games_played_in_tournament
            
            tournament_history_entry = {
                "tournament_name": tournament_name_original,
                "tournament_id": torneo.get('tournament_id', tournament_name_original), # Usa ID torneo se disponibile
                "rank": p_final_data.get('final_rank', 'N/A'),
                "total_players": num_players,
                "date_started": torneo.get('start_date'),
                "date_completed": torneo.get('end_date', datetime.now().strftime(DATE_FORMAT_ISO))
            }
            if 'tournaments_played' not in db_player_record: db_player_record['tournaments_played'] = []
            
            # Evita di aggiungere lo stesso record di torneo più volte
            if not any(t.get('tournament_id') == tournament_history_entry['tournament_id'] for t in db_player_record['tournaments_played']):
                db_player_record['tournaments_played'].append(tournament_history_entry)
                
                player_final_rank = p_final_data.get('final_rank')
                if isinstance(player_final_rank, int) and player_final_rank in [1, 2, 3, 4]:
                    if 'medals' not in db_player_record: 
                        db_player_record['medals'] = {'gold': 0, 'silver': 0, 'bronze': 0, 'wood': 0}
                    # Assicura tutte le chiavi medaglia per sicurezza
                    for medal_key_init in ['gold', 'silver', 'bronze', 'wood']:
                        db_player_record['medals'].setdefault(medal_key_init, 0)
                    
                    medal_map = {1: 'gold', 2: 'silver', 3: 'bronze', 4: 'wood'}
                    medal_type_to_add = medal_map.get(player_final_rank)
                    if medal_type_to_add:
                        db_player_record['medals'][medal_type_to_add] += 1
            db_updated_count +=1
    
    if db_updated_count > 0:
        save_players_db(players_db) # Salva sia JSON che TXT del DB giocatori
        print(_("Database Giocatori aggiornato per {count} giocatori e salvato.").format(count=db_updated_count))
    else:
        print(_("Nessun aggiornamento necessario per il Database Giocatori."))
    # --- Fase 6: Archiviazione File Torneo ---
    print(_("Archiviazione del torneo '{name}'...").format(name=tournament_name_original))
    sanitized_tournament_name = sanitize_filename(tournament_name_original)
    end_date_str = torneo.get('end_date')
    archive_folder_suffix = datetime.now().strftime("%Y-%m-%d") # Fallback per suffisso cartella
    if end_date_str:
        try:
            end_date_obj = datetime.strptime(end_date_str, DATE_FORMAT_ISO)
            archive_folder_suffix = end_date_obj.strftime("%B %Y").capitalize()
        except ValueError:
            print(_(" Warning: Formato data di fine ('{date_str}') non valido. Uso data corrente per suffisso cartella archivio.").format(date_str=end_date_str))
    tournament_archive_subdir_name = f"{sanitized_tournament_name} - {archive_folder_suffix}"
    full_archive_path = os.path.join(ARCHIVED_TOURNAMENTS_DIR, tournament_archive_subdir_name)
    try:
        os.makedirs(full_archive_path, exist_ok=True)
    except OSError as e:
        print(_("ERRORE: Creazione cartella di archivio '{path}' fallita: {error}").format(path=full_archive_path, error=e))
        print(_("I file del torneo non saranno archiviati ma il resto della finalizzazione è completo."))
        return False # L'archiviazione è una parte importante della finalizzazione

    files_to_move = []
    # 1. File JSON principale del torneo
    if current_tournament_filename and os.path.exists(current_tournament_filename):
        files_to_move.append(current_tournament_filename)
    else:
        # Tentativo di ricostruire il nome del file JSON se non passato o non esistente, basato sul nome del torneo
        # Questo è un fallback, current_tournament_filename dovrebbe essere corretto.
        guessed_json_filename = f"Tornello - {sanitized_tournament_name}.json" # Assicurati che "Tornello - " sia il tuo prefisso
        if os.path.exists(guessed_json_filename) and guessed_json_filename not in files_to_move:
             files_to_move.append(guessed_json_filename)
        else:
             print(_(" Warning: File JSON principale del torneo ('{current_filename}' o '{guessed_filename}') non trovato per l'archiviazione.").format(current_filename=current_tournament_filename, guessed_filename=guessed_json_filename))


    # 2. Altri file di testo (.txt) associati al torneo
    # Il pattern usa il nome sanificato per trovare i file correlati.
    # Assicurati che il prefisso "Tornello - " sia corretto e usato consistentemente.
    file_pattern_prefix = f"Tornello - {sanitized_tournament_name}"
    
    for file_in_dir in glob.glob(f"{file_pattern_prefix}*.*"): # Prende tutti i file che iniziano così
        if os.path.isfile(file_in_dir): # Assicurati sia un file
             # Evita di aggiungere nuovamente il file JSON principale se già presente
            if file_in_dir not in files_to_move:
                files_to_move.append(file_in_dir)

    if not files_to_move:
        print(_("  Warning: Nessun file specifico del torneo trovato da archiviare."))
    moved_files_count = 0
    for filepath_to_move in files_to_move:
        try:
            filename_only = os.path.basename(filepath_to_move)
            destination_path = os.path.join(full_archive_path, filename_only)
            # Gestione della sovrascrittura (anche se improbabile per una nuova cartella di archivio)
            if os.path.exists(destination_path):
                print(_(" Warning: File '{filename}' esiste già in '{path}'. Non verrà sovrascritto.").format(filename=filename_only, path=full_archive_path))
                continue # Salta lo spostamento di questo file
            shutil.move(filepath_to_move, destination_path)
            moved_files_count += 1
        except Exception as e_move:
            print(f"  Errore durante lo spostamento di '{os.path.basename(filepath_to_move)}': {e_move}")
    if moved_files_count > 0:
        print(_("Spostati {count} file del torneo in: '{path}'").format(count=moved_files_count, path=full_archive_path))
    else:
        print(_("Nessun file del torneo è stato spostato nella cartella di archivio."))
    print(_("Torneo '{name}' finalizzato e archiviato.").format(name=tournament_name_original))
    return True

if __name__ == "__main__":
    if not os.path.exists(BBP_SUBDIR):
        try:
            os.makedirs(BBP_SUBDIR)
            print(_("Info: Creata sottocartella '{}' per i file di bbpPairings.").format(BBP_SUBDIR))
        except OSError as e:
            print(_("ATTENZIONE: Impossibile creare la sottocartella '{}': {}").format(BBP_SUBDIR, e))
            print(_("bbpPairings potrebbe non funzionare correttamente."))
            sys.exit(1)
    players_db = load_players_db()
    torneo = None
    active_tournament_filename = None
    deve_creare_nuovo_torneo = False
    nome_nuovo_torneo_suggerito = None
    print(_("\nBENVENUTI! Sono Tornello {}").format(VERSIONE))
    print(_("\nVerifica stato database FIDE locale..."))
    db_fide_esiste = os.path.exists(FIDE_DB_LOCAL_FILE)
    db_fide_appena_aggiornato = False 
    if not db_fide_esiste:
        print(_("\nIl database FIDE locale non è presente sul tuo computer."))
        # Se non esiste, proponiamo sempre di scaricarlo
        if enter_escape(_("Vuoi scaricarlo ora? (L'operazione potrebbe richiedere alcuni minuti) (INVIO|ESCAPE)")):
            if aggiorna_db_fide_locale():
                db_fide_appena_aggiornato = True
                print(_("Database FIDE locale aggiornato con successo."))
    else: # Il file esiste, quindi controlliamo solo la sua età
        try:
            file_mod_timestamp = os.path.getmtime(FIDE_DB_LOCAL_FILE)
            file_age_days = (datetime.now() - datetime.fromtimestamp(file_mod_timestamp)).days
            print(_("Info: Il tuo database FIDE locale ha {} giorni.").format(file_age_days))
            if file_age_days >= 32:
                print(_("Essendo trascorsi più di 32 giorni dall'ultimo download, potrebbe essere stato rilasciato un aggiornamento"))
                if enter_escape(_("Si consiglia di aggiornarlo. Vuoi scaricare la versione più recente? (INVIO|ESCAPE)")):
                    if aggiorna_db_fide_locale():
                        db_fide_appena_aggiornato = True
        except Exception as e:
            print(_("Errore nel controllare la data del file DB FIDE locale: {}").format(e))
    # --- SINCRONIZZAZIONE DB PERSONALE ---
    # Chiedi di sincronizzare solo se il DB FIDE esiste (o perché c'era già o perché è stato appena scaricato)
    if os.path.exists(FIDE_DB_LOCAL_FILE):
        # La condizione chiave è qui: chiedi se abbiamo appena aggiornato OPPURE se il file è vecchio
        file_age_days = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(FIDE_DB_LOCAL_FILE))).days
        if db_fide_appena_aggiornato or file_age_days >= 32:
            prompt_sync = _("\nDatabase FIDE aggiornato. Vuoi sincronizzare ora il tuo DB personale?") if db_fide_appena_aggiornato else _("\nVuoi sincronizzare il tuo DB personale con i dati FIDE locali?")
            if enter_escape(f"{prompt_sync} (INVIO|ESCAPE)"):
                sincronizza_db_personale()
    # 1. Scansione dei file torneo esistenti
    tournament_files_pattern = "Tornello - *.json" 
    potential_tournament_files = [
        f for f in glob.glob(tournament_files_pattern) 
        if "- concluso_" not in os.path.basename(f).lower() and # Aggiunto .lower() per sicurezza
            os.path.basename(f) != os.path.basename(PLAYER_DB_FILE) # <-- CORREZIONE
    ]
    if not potential_tournament_files:
        print(_("Nessun torneo esistente trovato."))
        deve_creare_nuovo_torneo = True
    elif len(potential_tournament_files) == 1:
        single_found_filepath = potential_tournament_files[0]
        single_tournament_name_guess = _("Torneo Sconosciuto")
        try:
            with open(single_found_filepath, "r", encoding='utf-8') as f_temp:
                data_temp = json.load(f_temp)
            single_tournament_name_guess = data_temp.get("name", os.path.basename(single_found_filepath).replace("Tornello - ", "").replace(".json",""))
        except Exception as e:
            # Se non riesci a leggere il nome dal JSON, usa una parte del nome del file
            print(_("Info: impossibile leggere i dettagli da '{filename}' ({error}). Uso il nome del file.").format(filename=os.path.basename(single_found_filepath), error=e))
            base_name = os.path.basename(single_found_filepath)
            if base_name.startswith("Tornello - ") and base_name.endswith(".json"):
                single_tournament_name_guess = base_name[len("Tornello - "):-len(".json")]
            else:
                single_tournament_name_guess = base_name
        print(_("\nTrovato un solo torneo esistente: '{name}' (File: {filename})").format(name=single_tournament_name_guess, filename=os.path.basename(single_found_filepath)))
        while True: # Loop per la scelta dell'utente
            user_input_choice = input(_("Vuoi caricare '{name}'? (S/Invio per sì, oppure inserisci il nome di un NUOVO torneo da creare): ").format(name=single_tournament_name_guess)).strip()
            if not user_input_choice or user_input_choice.lower() == 's':
                # L'utente vuole caricare il torneo trovato (ha premuto Invio o 's')
                active_tournament_filename = single_found_filepath
                print(_("Caricamento di '{name}'...").format(name=single_tournament_name_guess))
                torneo = load_tournament(active_tournament_filename)
                if not torneo:
                    # Il caricamento è fallito
                    print(_("Errore fatale nel caricamento del torneo '{filename}'.").format(filename=active_tournament_filename))
                    # Chiediamo se vuole creare un nuovo torneo o uscire
                    create_new_instead_choice = enter_escape("Vuoi creare un nuovo torneo? (INVIO per sì|ESCAPE per uscire): ")
                    if create_new_instead_choice:
                        deve_creare_nuovo_torneo = True
                        active_tournament_filename = None # Resetta perché il caricamento è fallito
                    else:
                        print(_("Uscita dal programma."))
                        sys.exit(0) # Esce se il caricamento fallisce e non vuole creare
                # Se torneo è stato caricato con successo (o se si è scelto di creare dopo fallimento), esci da questo loop
                break 
            else:
                # L'utente ha inserito un nome, quindi vuole creare un nuovo torneo.
                # La stringa inserita (user_input_choice) è il nome del nuovo torneo.
                print(_("Ok, procederemo con la creazione di un nuovo torneo chiamato: '{name}'.").format(name=user_input_choice))
                deve_creare_nuovo_torneo = True
                nome_nuovo_torneo_suggerito = user_input_choice
                break
    else: # Più di un torneo trovato
        print(_("\n--- Tornei Esistenti Trovati ---"))
        tournament_options = []
        for idx, filepath in enumerate(potential_tournament_files):
            try:
                # Carichiamo temporaneamente per estrarre i metadati
                with open(filepath, "r", encoding='utf-8') as f_temp:
                    data_temp = json.load(f_temp)
                
                t_name = data_temp.get("name", _("Nome Sconosciuto"))
                t_start = data_temp.get("start_date")
                t_end = data_temp.get("end_date")
                
                start_display = format_date_locale(t_start) if t_start else "N/D"
                end_display = format_date_locale(t_end) if t_end else "N/D"
                
                tournament_options.append({
                    "id_lista": idx + 1,
                    "filepath": filepath,
                    "name": t_name,
                    "start_date_display": start_display,
                    "end_date_display": end_display
                })
                print(_(" {num}. {name} (dal {start_date} al {end_date}) - File: {filename}").format(num=idx + 1, name=t_name, start_date=start_display, end_date=end_display, filename=os.path.basename(filepath)))
            except Exception as e:
                print(_(" Errore durante la lettura dei metadati da {filename}: {error} (file saltato)").format(filename=os.path.basename(filepath), error=e))

        if not tournament_options: # Se tutti i file hanno dato errore in lettura metadati
            print(_("Nessun torneo valido trovato nonostante la presenza di file. Si procederà con la creazione."))
            deve_creare_nuovo_torneo = True
        else:
            print(_(" {num}. Crea un nuovo torneo").format(num=len(tournament_options) + 1))
            while True:
                choice_str = input(_("Scegli un torneo da caricare (1-{max_num}) o '{new_num}' per crearne uno nuovo: ").format(max_num=len(tournament_options), new_num=len(tournament_options) + 1)).strip()
                if choice_str.isdigit():
                    choice_num = int(choice_str)
                    if 1 <= choice_num <= len(tournament_options):
                        chosen_option = next(opt for opt in tournament_options if opt["id_lista"] == choice_num)
                        active_tournament_filename = chosen_option["filepath"]
                        print(_("Caricamento di '{name}'...").format(name=chosen_option['name']))
                        torneo = load_tournament(active_tournament_filename)
                        if not torneo:
                            print(_("Errore nel caricamento del torneo {filename}. Riprova o crea un nuovo torneo.").format(filename=active_tournament_filename))
                            # L'utente tornerà al prompt di scelta
                            active_tournament_filename = None # Resetta
                        else:
                            break # Torneo scelto e caricato
                    elif choice_num == len(tournament_options) + 1:
                        deve_creare_nuovo_torneo = True
                        break
                    else:
                        print(_("Scelta non valida."))
                else:
                    print(_("Inserisci un numero."))
    # 2. Creazione nuovo torneo (se necessario)
    if deve_creare_nuovo_torneo or torneo is None:
        if not deve_creare_nuovo_torneo and torneo is None : # Se il caricamento è fallito ma non era stato scelto di creare
            print(_("Nessun torneo caricato. Si procede con la creazione di un nuovo torneo."))
        torneo = {} 
        print(_("\n--- Creazione Nuovo Torneo ---"))
        active_tournament_filename = None # Verrà impostato quando il nome sarà definito
        new_tournament_name_final = ""    # Nome che verrà effettivamente usato per il torneo
        # Fase 1: Prova a usare il nome suggerito, se esiste
        if nome_nuovo_torneo_suggerito:
            print(_("Nome suggerito per il nuovo torneo: '{name}'").format(name=nome_nuovo_torneo_suggerito))
            current_potential_name = nome_nuovo_torneo_suggerito
            sanitized_check_name = sanitize_filename(current_potential_name)
            # Assicurati che il prefisso "Tornello - " sia quello corretto per il tuo stile di nomenclatura
            prospective_filename_check = f"Tornello - {sanitized_check_name}.json" 
            if os.path.exists(prospective_filename_check):
                overwrite_choice = enter_escape(_("ATTENZIONE: Un file torneo '{filename}' con questo nome esiste già. Sovrascriverlo? (INVIO|ESCAPE): ").format(filename=prospective_filename_check))
                if overwrite_choice == True:
                    new_tournament_name_final = current_potential_name # Accetta il nome suggerito
                    active_tournament_filename = prospective_filename_check
                else:
                    print(_("Sovrascrittura annullata. Verrà richiesto un nuovo nome."))
                    nome_nuovo_torneo_suggerito = None # Il suggerimento non è più valido
                    # new_tournament_name_final rimane "" (o None), quindi si passerà alla richiesta manuale
            else: # Il file per il nome suggerito non esiste, quindi va bene
                new_tournament_name_final = current_potential_name
                active_tournament_filename = prospective_filename_check
        
        # Fase 2: Se un nome non è stato finalizzato dal suggerimento (o non c'era suggerimento), chiedilo
        if not new_tournament_name_final:
            while True: # Loop solo per la richiesta del nome se necessario
                input_corrente_nome_torneo = input(_("Inserisci il nome del nuovo torneo: ")).strip()
                if input_corrente_nome_torneo:
                    sanitized_name_new = sanitize_filename(input_corrente_nome_torneo)
                    prospective_filename = f"Tornello - {sanitized_name_new}.json" # Usa il tuo stile
                    if os.path.exists(prospective_filename):
                        overwrite = enter_escape(_("ATTENZIONE: Un file torneo '{filename}' con questo nome esiste già. Sovrascriverlo? (INVIO|ESCAPE): ").format(filename=prospective_filename_check))
                        if overwrite != True:
                            print(_("Operazione annullata. Scegli un nome diverso per il torneo."))
                            continue # Torna a chiedere il nome (all'inizio di QUESTO while True)
                    new_tournament_name_final = input_corrente_nome_torneo
                    active_tournament_filename = prospective_filename
                    break # Esce dal loop di richiesta nome, nome definito!
                else:
                    print(_("Il nome del torneo non può essere vuoto. Riprova."))
        if not new_tournament_name_final or not active_tournament_filename:
            print(_("Nome del torneo non definito correttamente. Creazione annullata."))
            sys.exit(1) 
        torneo["name"] = new_tournament_name_final
        while True: 
            try:
                oggi_str_iso = datetime.now().strftime(DATE_FORMAT_ISO)
                oggi_str_locale = format_date_locale(oggi_str_iso)
                start_date_str = input(_("Inserisci data inizio ({date_format}) [Default: {default_date}]: ").format(date_format=DATE_FORMAT_ISO, default_date=oggi_str_locale)).strip()
                if not start_date_str: start_date_str = oggi_str_iso
                start_dt = datetime.strptime(start_date_str, DATE_FORMAT_ISO)
                torneo["start_date"] = start_date_str
                break 
            except ValueError: print(_("Formato data non valido. Usa {date_format}. Riprova.").format(date_format=DATE_FORMAT_ISO))
        while True:
            try:
                start_date_dt = datetime.strptime(torneo["start_date"], DATE_FORMAT_ISO)
                future_date_dt = start_date_dt + timedelta(days=60)
                default_end_date_iso = future_date_dt.strftime(DATE_FORMAT_ISO)
                default_end_date_locale = format_date_locale(future_date_dt)
                end_date_str = input(_("Inserisci data fine ({date_format}) [Default: {default_date}]: ").format(date_format=DATE_FORMAT_ISO, default_date=default_end_date_locale)).strip()
                if not end_date_str: end_date_str = default_end_date_iso
                end_dt = datetime.strptime(end_date_str, DATE_FORMAT_ISO)
                if end_dt < start_date_dt:
                    print(_("Errore: La data di fine non può essere precedente alla data di inizio."))
                    continue
                torneo["end_date"] = end_date_str
                break
            except ValueError: print(f"Formato data non valido. Usa {DATE_FORMAT_ISO}. Riprova.")
            except OverflowError: print(_("Errore: La data calcolata risulta troppo lontana nel futuro.")); continue
        while True: 
            try:
                rounds_str = input(_("Inserisci il numero totale dei turni: ")).strip()
                total_rounds = int(rounds_str)
                if total_rounds > 0: torneo["total_rounds"] = total_rounds; break
                else: print(_("Il numero di turni deve essere positivo."))
            except ValueError: print(_("Inserisci un numero intero valido."))
        print(_("\nInserisci i dettagli aggiuntivi del torneo (lascia vuoto per usare default):"))
        torneo["site"] = input(_(" Luogo del torneo [Default: {default_site}]: ").format(default_site=_("Luogo Sconosciuto"))).strip() or _("Luogo Sconosciuto")
        fed_code = input(_("  Federazione organizzante (codice 3 lettere) [Default: ITA]: ")).strip().upper() or "ITA"
        torneo["federation_code"] = fed_code[:3]
        torneo["chief_arbiter"] = input(_(" Arbitro Capo [Default: {default_arbiter}]: ").format(default_arbiter=_("N/D"))).strip() or _("N/D")
        torneo["deputy_chief_arbiters"] = input(_(" Vice Arbitri (separati da virgola) [Default: {default_deputy}]: ").format(default_deputy=_("nessuno"))).strip() or ""
        torneo["time_control"] = input(_(" Controllo del Tempo [Default: {default_tc}]: ").format(default_tc=_("Standard"))).strip() or _("Standard")
        while True:
            b1_choice = enter_escape(_(" Bianco alla prima scacchiera del Turno 1? (INVIO|ESCAPE): "))
            if b1_choice: torneo['initial_board1_color_setting'] = "white1"; break
            else: torneo['initial_board1_color_setting'] = "black1"; break
        round_dates = calculate_dates(torneo["start_date"], torneo["end_date"], torneo["total_rounds"])
        if round_dates is None:
            print(_("Errore fatale nel calcolo delle date dei turni. Creazione torneo annullata.")); sys.exit(1)
        torneo["round_dates"] = round_dates
        torneo["tournament_id"] = f"{sanitize_filename(torneo['name'])}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        torneo["players"] = input_players(players_db)
        if not _conferma_lista_giocatori_torneo(torneo, players_db):
            print(_("Creazione torneo annullata a causa di problemi con la lista giocatori."))
            sys.exit(0) 
        torneo['players_dict'] = {p['id']: p for p in torneo['players']}
        num_giocatori = len(torneo.get("players", []))
        num_turni_totali = torneo.get("total_rounds",0)
        if num_giocatori > (num_turni_totali * 2):
            valore_bye_calcolato = 0.5
        else:
            valore_bye_calcolato = 1.0
        valore_suggerito = valore_bye_calcolato
        valore_alternativo = 1.0 if valore_suggerito == 0.5 else 0.5
        print("-" * 30)
        print(_("Calcolo Valore del BYE secondo la regola FIDE"))
        print(_("Il valore suggerito è: {val}").format(val=valore_suggerito))
        print("-" * 30)
        prompt_conferma = _("Accetti il valore suggerito? (INVIO = Sì / ESCAPE = No, per usare {alt_val})").format(alt_val=valore_alternativo)
        if enter_escape(prompt_conferma):
            valore_bye_confermato = valore_suggerito
        else:
            valore_bye_confermato = valore_alternativo
        torneo['bye_value'] = float(valore_bye_confermato)
        print(_("Valore del BYE impostato a: {val}").format(val=torneo['bye_value']))
        min_req_players = num_turni_totali + 1 if isinstance(num_turni_totali, int) and num_turni_totali > 0 else 2
        if num_giocatori < min_req_players : # Ricontrolla dopo _conferma
             print(_("Numero insufficiente di giocatori ({num_players}) per {num_rounds} turni dopo la conferma. Torneo annullato.").format(num_players=num_giocatori, num_rounds=num_turni_totali));
             sys.exit(0)
        torneo["current_round"] = 1
        torneo["rounds"] = []
        torneo["next_match_id"] = 1
        torneo["launch_count"] = 1
        torneo['players_dict'] = {p['id']: p for p in torneo['players']}

        print(_("\nGenerazione abbinamenti per il Turno 1..."))
        matches_r1 = generate_pairings_for_round(torneo)
        if matches_r1 is None:
            print(_("ERRORE CRITICO: Fallimento generazione abbinamenti Turno 1. Torneo non avviato.")); sys.exit(1)
        print(_("Registrazione risultati automatici per il Turno 1 (BYE)..."))
        valore_bye_torneo = torneo.get('bye_value', 1.0) 
        for match in matches_r1:
            if match.get("result") == "BYE":
                bye_player_id = match.get('white_player_id')
                if bye_player_id and bye_player_id in torneo['players_dict']:
                    player_obj = torneo['players_dict'][bye_player_id]
                    player_obj['points'] = valore_bye_torneo
                    player_obj.setdefault("results_history", []).append({
                        "round": 1, "opponent_id": "BYE_PLAYER_ID",
                        "color": None, "result": "BYE", "score": valore_bye_torneo
                    })
                    print(_(" > Giocatore {name} (ID: {id}) ha ricevuto un BYE. Punti e storico aggiornati.").format(name=player_obj.get('first_name'), id=bye_player_id))
        torneo["rounds"].append({"round": 1, "matches": matches_r1})
        save_tournament(torneo) # Salva sul nuovo active_tournament_filename
        save_current_tournament_round_file(torneo)
        save_standings_text(torneo, final=False)
        print(_("\nTorneo '{name}' creato e Turno 1 generato. File: '{filename}'").format(name=torneo.get('name'), filename=active_tournament_filename))
    # 3. Se nessun torneo è attivo a questo punto, esci.
    if not torneo or not active_tournament_filename:
        print(_("\nNessun torneo attivo. Uscita dal programma."))
        sys.exit(0)
    # 4. Aggiorna launch_count se il torneo è stato caricato (non creato ora)
    if not deve_creare_nuovo_torneo: # Implica che è stato caricato
        torneo['launch_count'] = torneo.get('launch_count', 0) + 1
        # Assicura che players_dict sia inizializzato (load_tournament dovrebbe già farlo)
        _ensure_players_dict(torneo)
    # Messaggio di benvenuto specifico per il torneo
    print(_("\n--- Torneo Attivo: {name} ---").format(name=torneo.get('name', 'N/D')))
    print(f"File: {active_tournament_filename}")
    print(_("Sessione numero {count} per questo torneo.").format(count=torneo.get('launch_count',1)))
    print(_("Copyright 2025, dedicato all'ASCId e al gruppo Scacchierando."))
    try:
        while True:
            current_round_num = torneo.get("current_round")
            total_rounds_num = torneo.get("total_rounds")
            if current_round_num is None or total_rounds_num is None or current_round_num > total_rounds_num:
                # ... (condizione di uscita se il torneo è finito)
                if torneo: # Se il torneo è "finito" ma esiste ancora l'oggetto
                     print(_("\nIl torneo '{name}' si è concluso o in uno stato non valido.").format(name=torneo.get('name')))
                else: # Se è stato finalizzato e impostato a None
                     print(_("\nNessun torneo attivo o torneo concluso."))
                break 

            print(_("\n--- Gestione Turno {round_num} ---").format(round_num=current_round_num))
            display_status(torneo)
            
            current_round_data = None
            for r_data_loop in torneo.get("rounds", []):
                if r_data_loop.get("round") == current_round_num:
                    current_round_data = r_data_loop; break
            
            if current_round_data is None:
                print(_("ERRORE CRITICO: Dati turno {round_num} non trovati!").format(round_num=current_round_num))
                break
            round_completed = all(
                m.get("result") is not None or m.get("black_player_id") is None 
                for m in current_round_data.get("matches", [])
            ) if current_round_data.get("matches") else False # Considera non completo se non ci sono partite

            if not round_completed:
                modifications_made = update_match_result(torneo) # Passa l'oggetto torneo aggiornabile
                # update_match_result ora chiama gestisci_pianificazione_partite che usa il current_round_data da torneo
                print(_("\nSessione di inserimento/modifica risultati (o pianificazione) terminata."))
                if modifications_made: # Se update_match_result o gestisci_pianificazione hanno fatto modifiche
                    print(_("Salvataggio modifiche al torneo..."))
                    save_tournament(torneo) # Salva sul file corretto
                
                save_current_tournament_round_file(torneo)
                save_standings_text(torneo, final=False)
                exit_choice = enter_escape(_("Vuoi continuare? (INVIO|ESCAPE)): "))
                if exit_choice == False:
                    print(_("Salvataggio finale prima dell'uscita..."))
                    save_tournament(torneo)
                    break # Esce dal while True (main loop)
            else:
                print(_("\nTurno {round_num} completato.").format(round_num=current_round_num))
                append_completed_round_to_history_file(torneo, current_round_num)
                save_standings_text(torneo, final=False)

                if current_round_num == total_rounds_num:
                    print(_("\nUltimo turno completato. Avvio finalizzazione torneo..."))
                    if finalize_tournament(torneo, players_db, active_tournament_filename):
                        print(_("\n--- Torneo Concluso e Finalizzato Correttamente ---"))
                        torneo = None 
                        active_tournament_filename = None
                    else:
                        print(_("\n--- ERRORE durante la Finalizzazione del Torneo ---"))
                        if torneo and active_tournament_filename: save_tournament(torneo)
                    break 
                else: # Prepara e genera il prossimo turno
                    next_round_num = current_round_num + 1
                    print(_("\nVuoi procedere e generare gli abbinamenti per il Turno {round_num}? (INVIO|ESCAPE): ").format(round_num=next_round_num))
                    procede_next_round = enter_escape()
                    if procede_next_round:
                        # 1. Aggiorna il numero del turno
                        torneo["current_round"] = next_round_num
                        print(_("Generazione abbinamenti per il Turno {round_num}...").format(round_num=next_round_num))
                        # 2. Genera gli abbinamenti
                        next_matches = generate_pairings_for_round(torneo)
                        if next_matches is None:
                            user_action = handle_bbpairings_failure(torneo, next_round_num, "Errore durante la generazione.")
                            if user_action == 'time_machine':
                                print(_("Accesso alla Time Machine..."))
                                # Ripristiniamo il turno corrente a quello precedente, così la TM parte da uno stato noto
                                torneo["current_round"] = current_round_num
                                if time_machine_torneo(torneo):
                                    any_changes_made_in_this_session = True
                                    save_tournament(torneo)
                                    print(_("Stato del torneo ripristinato e salvato. Riavvio del ciclo principale."))
                                else:
                                    print(_("Time Machine annullata o fallita. Uscita per sicurezza."))
                                    save_tournament(torneo)
                                    break # Esce dal ciclo principale
                                # Non uscire dal ciclo, ricomincerà dal turno ripristinato
                                continue 
                            elif user_action == 'terminate':
                                print(_("Uscita dal programma come richiesto."))
                                torneo["current_round"] = current_round_num # Ripristina per coerenza
                                save_tournament(torneo)
                                break # Esce dal ciclo principale
                        # 3. Gestisci il BYE appena generato (se presente)
                        print(_("Registrazione risultati automatici per il Turno {round_num} (BYE)...").format(round_num=next_round_num))
                        valore_bye_torneo = torneo.get('bye_value', 1.0) 
                        for match in next_matches:
                            if match.get("result") == "BYE":
                                bye_player_id = match.get('white_player_id')
                                _ensure_players_dict(torneo) # Assicura che la cache giocatori sia pronta
                                if bye_player_id and bye_player_id in torneo['players_dict']:
                                    player_obj = torneo['players_dict'][bye_player_id]
                                    player_obj['points'] = player_obj.get('points', 0.0) + valore_bye_torneo
                                    player_obj.setdefault("results_history", []).append({
                                        "round": next_round_num,
                                        "opponent_id": "BYE_PLAYER_ID",
                                        "color": None, "result": "BYE", "score": valore_bye_torneo
                                    })
                                    # Aggiorna anche le altre statistiche relative al BYE
                                    player_obj['received_bye_count'] = player_obj.get('received_bye_count', 0) + 1
                                    player_obj.setdefault('received_bye_in_round', []).append(next_round_num)
                                    print(_(" > Giocatore {name} (ID: {id}) ha ricevuto un BYE. Punti e storico aggiornati.").format(name=player_obj.get('first_name'), id=bye_player_id))
                        torneo["rounds"].append({"round": next_round_num, "matches": next_matches})
                        # 5. Salva tutto
                        save_tournament(torneo)
                        save_current_tournament_round_file(torneo)
                        print(_("Turno {round_num} generato e salvato.").format(round_num=next_round_num))
                    else:
                        print(_("Generazione prossimo turno annullata. Salvataggio stato attuale."))
                        save_tournament(torneo)
                        break # Esce dal main loop
    except KeyboardInterrupt:
        print(_("\nOperazione interrotta dall'utente."))
        if torneo and active_tournament_filename:
            print(f"Salvataggio stato attuale del torneo in '{active_tournament_filename}'...")
            save_tournament(torneo)
            if torneo.get("current_round") <= torneo.get("total_rounds",0):
                save_current_tournament_round_file(torneo)
        print(_("Stato salvato. Uscita."))
        sys.exit(0)
    except Exception as e_main_loop:
        print(_("\nERRORE CRITICO NON GESTITO nel flusso principale: {error}").format(error=e_main_loop))
        traceback.print_exc()
        if torneo and active_tournament_filename:
            print(f"Tentativo salvataggio stato torneo in '{active_tournament_filename}'...")
            save_tournament(torneo)
        sys.exit(1)
    if torneo is None and active_tournament_filename is None:
        print(_("\nProgramma Tornello terminato."))
        Donazione()
    elif torneo and active_tournament_filename:
         print(_("\nProgramma Tornello terminato. Ultimo stato per '{name}' in '{filename}'.").format(name=torneo.get('name', 'N/D'), filename=active_tournament_filename))
         Donazione()
    else: # Caso anomalo
         print(_("\nProgramma Tornello terminato con uno stato incerto del torneo."))