import os
import shutil
import glob
import traceback
from datetime import datetime
from config import *
from GBUtils import dgt, key
from utils import enter_escape, format_date_locale, format_points, sanitize_filename, create_backup
from db_players import _cerca_giocatore_nel_db_fide, crea_nuovo_giocatore_nel_db, save_players_db
from tournament import time_machine_torneo, save_tournament, _apply_match_result_to_players, _ensure_players_dict
from stats import get_k_factor, compute_buchholz, compute_buchholz_cut1, compute_aro, calculate_performance_rating, calculate_elo_change
from reports import save_standings_text

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

    # --- Creazione backup pre-finalizzazione ---
    print(_("Creazione backup di sicurezza prima dell'archiviazione..."))
    backup_db_ok = create_backup(PLAYER_DB_FILE, "pre_finalize_db")
    backup_torneo_ok = True
    if current_tournament_filename and os.path.exists(current_tournament_filename):
        backup_torneo_ok = create_backup(current_tournament_filename, "pre_finalize_torneo")
    
    if not backup_db_ok or not backup_torneo_ok:
        print(_("ATTENZIONE: Fallita la creazione di uno o più file di backup. Procedo ugualmente..."))
    else:
        print(_("Backup di sicurezza creati con successo."))

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

