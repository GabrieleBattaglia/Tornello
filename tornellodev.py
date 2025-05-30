# Data concepimento: 28 marzo 2025
import os, json, sys, math, traceback, subprocess, pprint
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
# --- Constants ---
VERSIONE = "5.9.3 del 29 maggio 2025 di Gabriele Battaglia &	Gemini 2.5 Pro\n\tusing BBP Pairings, a Swiss-system chess tournament engine created by Bierema Boyz Programming."
PLAYER_DB_FILE = "tornello - giocatori_db.json"
PLAYER_DB_TXT_FILE = "tornello - giocatori_db.txt"
TOURNAMENT_FILE = "Tornello - torneo.json"
DATE_FORMAT_ISO = "%Y-%m-%d"
DATE_FORMAT_DB = "%Y-%m-%d"
DEFAULT_ELO = 1399.0
DEFAULT_K_FACTOR = 20
# --- Constants for bbpPairings Integration ---
BBP_SUBDIR = "bbppairings"
BBP_EXE_NAME = "bbpPairings.exe" # Nome dell'eseguibile
BBP_EXE_PATH = os.path.join(BBP_SUBDIR, BBP_EXE_NAME)
BBP_INPUT_TRF = os.path.join(BBP_SUBDIR, "input_bbp.trf") # Nome file input per bbp
BBP_OUTPUT_COUPLES = os.path.join(BBP_SUBDIR, "output_coppie.txt")
BBP_OUTPUT_CHECKLIST = os.path.join(BBP_SUBDIR, "output_checklist.txt")

def genera_stringa_trf_per_bbpairings(dati_torneo, lista_giocatori_attivi, mappa_id_a_start_rank):
    """
    Genera la stringa di testo in formato TRF(bx) per bbpairings.
    Per il Round 1: righe giocatore SENZA blocchi dati partita (si affida a XXC white1).
    Per i Round > 1: righe giocatore CON storico risultati dei turni precedenti.
    """
    trf_lines = []
    try:
        total_rounds_val = int(dati_torneo.get('total_rounds', 0))
        number_of_players_val = len(lista_giocatori_attivi)
        current_round_being_paired = int(dati_torneo.get("current_round", 1))

        # Formattazione Date
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
        trf_lines.append(f"012 {str(dati_torneo.get('name', 'Torneo Sconosciuto'))[:45]:<45}\n")
        trf_lines.append(f"022 {str(dati_torneo.get('site', 'Luogo Sconosciuto'))[:45]:<45}\n") # Usa 'site'
        trf_lines.append(f"032 {str(dati_torneo.get('federation_code', 'ITA'))[:3]:<3}\n")    # Usa 'federation_code'
        trf_lines.append(f"042 {start_date_strf}\n") # Già usa 'start_date'
        trf_lines.append(f"052 {end_date_strf}\n")   # Già usa 'end_date'
        trf_lines.append(f"062 {number_of_players_val:03d}\n") # Già calcolato
        trf_lines.append(f"072 {number_of_players_val:03d}\n") # Già calcolato
        trf_lines.append("082 000\n") 
        trf_lines.append("092 Individual: Swiss-System\n") # Potrebbe diventare configurabile
        trf_lines.append(f"102 {str(dati_torneo.get('chief_arbiter', 'Arbitro Default'))[:45]:<45}\n") # Usa 'chief_arbiter'
        deputy_str = str(dati_torneo.get('deputy_chief_arbiters', '')).strip()
        if not deputy_str: deputy_str = " " # TRF vuole almeno uno spazio se la riga 112 è presente ma vuota
        trf_lines.append(f"112 {deputy_str[:45]:<45}\n") 
        trf_lines.append(f"122 {str(dati_torneo.get('time_control', 'Standard'))[:45]:<45}\n") # Usa 'time_control'
        trf_lines.append(f"XXR {total_rounds_val:03d}\n") # Già usa 'total_rounds'
        initial_color_setting = str(dati_torneo.get('initial_board1_color_setting', 'white1')).lower()
        trf_lines.append(f"XXC {initial_color_setting}\n")
        # Funzione helper definita una volta
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
            raw_last_name = player_data.get('last_name', 'Cognome')
            raw_first_name = player_data.get('first_name', 'Nome')
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
                    dt_obj = datetime.strptime(birth_date_from_playerdata, DATE_FORMAT_DB) # DATE_FORMAT_DB è %Y-%m-%d
                    birth_date_for_trf = dt_obj.strftime("%Y/%m/%d") # Formato TRF standard
                except ValueError:
                    # Se non è nel formato YYYY-MM-DD, usa il valore grezzo se è lungo 10, altrimenti placeholder
                    if len(str(birth_date_from_playerdata)) == 10:
                        birth_date_for_trf = str(birth_date_from_playerdata)
                    else: # Fallback a stringa di spazi se il formato non è gestibile
                        birth_date_for_trf = "          " 
            write_to_char_list_local(p_line_chars, 70, f"{birth_date_for_trf:<10}"[:10]) # Assicura 10 caratteri            
            write_to_char_list_local(p_line_chars, 81, f"{float(player_data.get('points', 0.0)):4.1f}")
            write_to_char_list_local(p_line_chars, 86, f"{start_rank:>4}") # Campo Rank (col 86-89)
            # --- Scrittura Storico Risultati ---
            # Inizia a scrivere i blocchi partita dalla colonna 92 (indice 91)
            # Le colonne 90 e 91 sono implicitamente spazi (dall'inizializzazione di p_line_chars)
            colonna_inizio_blocco_partita = 92 
            
            history_sorted = sorted(player_data.get("results_history", []), key=lambda x: x.get("round", 0))

            if current_round_being_paired > 1: # Scrivi lo storico solo se non è il primo turno
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
                            if player_score_this_game == 1.0: result_code_trf = "U"
                            elif player_score_this_game == 0.5: result_code_trf = "H" 
                            elif player_score_this_game == 0.0: result_code_trf = "Z" 
                            else: result_code_trf = "U" 
                        elif opp_id_tornello:
                            opponent_start_rank = mappa_id_a_start_rank.get(opp_id_tornello)
                            if opponent_start_rank is None:
                                print(f"AVVISO CRITICO: ID avv. storico {opp_id_tornello} non in mappa per {player_data['id']} R{round_of_this_entry}")
                                opp_start_rank_str = "XXXX" 
                            else:
                                opp_start_rank_str = f"{opponent_start_rank:>4}"
                            
                            if player_score_this_game == 1.0:
                                result_code_trf = "1" 
                                if tornello_result_str == "1-F": result_code_trf = "+" 
                            elif player_score_this_game == 0.5: result_code_trf = "="
                            elif player_score_this_game == 0.0:
                                result_code_trf = "0" 
                                if tornello_result_str == "F-1": result_code_trf = "-" 
                                elif tornello_result_str == "0-0F": result_code_trf = "-" 
                            else: result_code_trf = "?" 
                        else: continue 
                        
                        if result_code_trf == "?": continue

                        game_block = f"{opp_start_rank_str} {color_char_trf} {result_code_trf}  "[:10] 
                        write_to_char_list_local(p_line_chars, colonna_inizio_blocco_partita, game_block)
                        colonna_inizio_blocco_partita += 10
            
            # Per il Round 1: NON aggiungiamo il blocco "0000 w   " se XXC white1 è presente.
            # Le righe giocatore per il R1 finiranno dopo il campo Rank (col 89) o gli spazi successivi.
            # rstrip() si occuperà di rimuovere gli spazi finali inutilizzati da p_line_chars.

            final_line = "".join(p_line_chars).rstrip()
            trf_lines.append(final_line + "\n")
        
        return "".join(trf_lines)

    except Exception as e:
        print(f"Errore catastrofico in genera_stringa_trf_per_bbpairings: {e}")
        traceback.print_exc()
        return None

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
            print(f"Info: Creata sottocartella '{BBP_SUBDIR}' per i file di bbpPairings.")
        except OSError as e:
            return False, None, f"Errore creazione sottocartella '{BBP_SUBDIR}': {e}"

    try:
        with open(BBP_INPUT_TRF, "w", encoding="utf-8") as f:
            f.write(trf_content_string)
    except IOError as e:
        return False, None, f"Errore scrittura file TRF di input '{BBP_INPUT_TRF}': {e}"

    command = [
        BBP_EXE_PATH,
        "--dutch",
        BBP_INPUT_TRF,
        "-p", BBP_OUTPUT_COUPLES,
        "-l", BBP_OUTPUT_CHECKLIST
    ]

    try:
        # print(f"DEBUG: Eseguo comando: {' '.join(command)}") # Utile per debug
        result = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace')

        if result.returncode != 0:
            error_message = f"bbpPairings.exe ha fallito con codice {result.returncode}.\n"
            error_message += f"Stderr:\n{result.stderr}\n"
            error_message += f"Stdout:\n{result.stdout}"
            # Se codice è 1 (no pairing), lo gestiremo specificamente più avanti
            return False, {'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}, error_message

        # Lettura file di output se successo
        coppie_content = ""
        if os.path.exists(BBP_OUTPUT_COUPLES):
            with open(BBP_OUTPUT_COUPLES, "r", encoding="utf-8") as f:
                coppie_content = f.read()
        else:
            return False, None, f"File output coppie '{BBP_OUTPUT_COUPLES}' non trovato."
            
        checklist_content = ""
        if os.path.exists(BBP_OUTPUT_CHECKLIST):
            with open(BBP_OUTPUT_CHECKLIST, "r", encoding="utf-8") as f:
                checklist_content = f.read()
        # Non consideriamo un errore se il checklist non c'è, ma logghiamo

        return True, {'coppie_raw': coppie_content, 'checklist_raw': checklist_content, 'stdout': result.stdout}, "Esecuzione bbpPairings completata."

    except FileNotFoundError:
        return False, None, f"Errore: Eseguibile '{BBP_EXE_PATH}' non trovato. Assicurati sia nel percorso corretto."
    except Exception as e:
        return False, None, f"Errore imprevisto durante esecuzione bbpPairings: {e}\n{traceback.format_exc()}"

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
        print("Warning: File output coppie vuoto o illeggibile.")
        return None # O lista vuota, da decidere

    try:
        # La prima riga dovrebbe essere il numero di coppie, la saltiamo per ora
        # o la usiamo per validazione se necessario.
        # num_expected_pairs = int(lines[0])
        
        pair_lines = lines[1:] # Le righe effettive degli abbinamenti

        for line_num, line in enumerate(pair_lines):
            parts = line.strip().split()
            if len(parts) != 2:
                print(f"Warning: Riga abbinamento malformata: '{line}' (saltata)")
                continue
            
            try:
                start_rank1_str, start_rank2_str = parts[0], parts[1]
                start_rank1 = int(start_rank1_str)
                start_rank2 = int(start_rank2_str) # Può essere 0 per il BYE
            except ValueError:
                print(f"Warning: ID non numerici nella riga abbinamento: '{line}' (saltata)")
                continue

            player1_id_tornello = mappa_start_rank_a_id.get(start_rank1)
            
            if player1_id_tornello is None:
                print(f"Warning: StartRank {start_rank1} non trovato nella mappa giocatori (riga: '{line}').")
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
                    print(f"Warning: StartRank avversario {start_rank2} non trovato nella mappa (riga: '{line}').")
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
        print(f"Errore durante il parsing dell'output delle coppie: {e}\n{traceback.format_exc()}")
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
                f.write(f"\tSesso: {sesso}, Federazione Giocatore: {federazione_giocatore}, ID FIDE num: {fide_id_numerico}\n")
                games_played_total = player.get('games_played', 0)
                current_k_factor = get_k_factor(player, current_date_iso) # Assicurati che get_k_factor sia accessibile
                registration_date_display = format_date_locale(player.get('registration_date'))
                f.write(f"\tPartite Valutate Totali: {games_played_total}, K-Factor Stimato: {current_k_factor}, Data Iscrizione DB: {registration_date_display}\n")
                birth_date_val = player.get('birth_date') # Formato YYYY-MM-DD o None
                birth_date_display = format_date_locale(birth_date_val) if birth_date_val else 'N/D'
                f.write(f"\tData Nascita: {birth_date_display}\n") 
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
                         history_line = f"{rank_formatted} su {t.get('total_players', '?')} in {t_name} - {start_date_formatted} - {end_date_formatted}"
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
    norm_last = last_name.strip().title()
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
                torneo_data = json.load(f)
                
                # Inizializza campi standard del torneo se mancanti (per compatibilità)
                torneo_data.setdefault('name', 'Torneo Sconosciuto')
                torneo_data.setdefault('start_date', datetime.now().strftime(DATE_FORMAT_ISO))
                torneo_data.setdefault('end_date', datetime.now().strftime(DATE_FORMAT_ISO))
                torneo_data.setdefault('total_rounds', 0)
                torneo_data.setdefault('current_round', 1)
                torneo_data.setdefault('next_match_id', 1)
                torneo_data.setdefault('rounds', [])
                torneo_data.setdefault('players', [])
                torneo_data.setdefault('launch_count', 0)

                # --- INIZIO INIZIALIZZAZIONE NUOVI CAMPI HEADER ---
                torneo_data.setdefault('site', 'Luogo Sconosciuto')
                torneo_data.setdefault('federation_code', 'ITA') # Federazione del torneo
                torneo_data.setdefault('chief_arbiter', 'N/D')
                torneo_data.setdefault('deputy_chief_arbiters', '')
                torneo_data.setdefault('time_control', 'Standard')
                # Se avevi aggiunto campi per BBW, BBD, etc. per punteggi non standard:
                # torneo_data.setdefault('points_for_win', 1.0) 
                # torneo_data.setdefault('points_for_draw', 0.5)
                # --- FINE INIZIALIZZAZIONE NUOVI CAMPI HEADER ---

                # Re-inizializza i set e campi necessari dopo il caricamento per i giocatori
                if 'players' in torneo_data:
                    for p in torneo_data['players']:
                        p['opponents'] = set(p.get('opponents', [])) 
                        p.setdefault('white_games', 0)
                        p.setdefault('black_games', 0)
                        # ... (altri setdefault per i giocatori come già avevi) ...
                        p.setdefault('received_bye_count', 0) # Esempio se avevi aggiunto questo
                        p.setdefault('received_bye_in_round', [])


                # Ricostruisci players_dict
                torneo_data['players_dict'] = {p['id']: p for p in torneo_data.get('players', [])}
                return torneo_data
        except (json.JSONDecodeError, IOError) as e:
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

def generate_pairings_for_round(torneo):
    """
    Genera gli abbinamenti per il turno corrente usando bbpPairings.exe.
    Include gestione BYE e fallback a input manuale.
    """
    round_number = torneo.get("current_round")
    if round_number is None:
        print("ERRORE: Numero turno corrente non definito nel torneo.")
        return None 
    
    print(f"\n--- Generazione Abbinamenti Turno {round_number} con bbpPairings ---")

    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    
    # Filtra solo i giocatori attivi (non ritirati)
    # È cruciale che 'lista_giocatori_attivi' contenga solo chi deve essere abbinato.
    lista_giocatori_attivi = [
        p_obj.copy() for p_obj in torneo.get('players', []) 
        if not torneo['players_dict'][p_obj['id']].get("withdrawn", False)
    ]

    if not lista_giocatori_attivi:
        print(f"Nessun giocatore attivo per il turno {round_number}.")
        return []

    # 1. Creare mappa ID Tornello -> StartRank e viceversa
    # Ordinamento per StartRank: Elo decrescente, poi alfabetico
    players_sorted_for_start_rank = sorted(
        lista_giocatori_attivi, 
        key=lambda p: (-float(p.get('initial_elo', DEFAULT_ELO)), 
                       p.get('last_name','').lower(), 
                       p.get('first_name','').lower())
    )
    
    mappa_id_a_start_rank = {p['id']: i + 1 for i, p in enumerate(players_sorted_for_start_rank)}
    mappa_start_rank_a_id = {i + 1: p['id'] for i, p in enumerate(players_sorted_for_start_rank)}

    # 2. Generare la stringa TRF
    # 'players_sorted_for_start_rank' viene passato per mantenere l'ordine corretto nel TRF
    trf_string = genera_stringa_trf_per_bbpairings(torneo, players_sorted_for_start_rank, mappa_id_a_start_rank)
    if not trf_string:
        print("ERRORE: Fallita generazione della stringa TRF per bbpPairings.")
        return handle_bbpairings_failure(torneo, round_number, "Fallimento generazione stringa TRF.") 

    # 3. Eseguire bbpPairings.exe
    success, bbp_output_data, bbp_message = run_bbpairings_engine(trf_string)

    all_generated_matches = [] 

    if success:
        print("bbpPairings eseguito con successo.")
        
        # 4. Parsare l'output delle coppie
        parsed_pairing_list = parse_bbpairings_couples_output(bbp_output_data['coppie_raw'], mappa_start_rank_a_id)

        if parsed_pairing_list is None:
            print("ERRORE: Fallimento parsing output coppie di bbpPairings.")
            return handle_bbpairings_failure(torneo, round_number, f"Fallimento parsing output bbpPairings:\n{bbp_message}")
        
        # 5. Convertire in formato `all_matches` e aggiornare stato giocatori
        
        # La funzione parse_bbpairings_couples_output dovrebbe già marcare i BYE.
        # Non dovrebbe essere necessario dedurre il bye qui se il parsing lo fa.
        # Tuttavia, facciamo un controllo di coerenza se il numero di giocatori è dispari.
        num_active_players_for_pairing = len(lista_giocatori_attivi)
        bye_found_in_parsed_list = any(m.get('is_bye', False) for m in parsed_pairing_list)

        if num_active_players_for_pairing % 2 != 0:
            if not bye_found_in_parsed_list:
                # Questo scenario è improbabile se parse_bbpairings_couples_output gestisce "ID 0"
                print(f"ATTENZIONE: Numero giocatori dispari ({num_active_players_for_pairing}) ma nessun BYE esplicito trovato dal parsing. Verificare output bbpPairings.")
                # Potrebbe essere necessario un meccanismo di fallback più robusto qui per identificare il giocatore spaiato
                # confrontando `lista_giocatori_attivi` con quelli presenti in `parsed_pairing_list`.
                # Per ora, ci fidiamo che parse_bbpairings_couples_output lo gestisca.
            else:
                print("Info: BYE gestito correttamente dal parsing dell'output.")
        elif bye_found_in_parsed_list:
            # Numero pari di giocatori ma un BYE è stato parsato: anomalia.
            print(f"ATTENZIONE: Numero giocatori pari ({num_active_players_for_pairing}) ma un BYE è stato parsato. Controllare output.")
            return handle_bbpairings_failure(torneo, round_number, "Incoerenza BYE con numero giocatori pari.")


        for i, match_info in enumerate(parsed_pairing_list):
            match_id_counter = torneo.get("next_match_id", 1) # Leggi il contatore
            current_match = {
                "id": match_id_counter, # Usa il contatore
                "round": round_number,
                "white_player_id": match_info['white_player_id'],
                "black_player_id": match_info.get('black_player_id'), # Può essere None per BYE
                "result": match_info.get('result'), # Sarà "BYE" o None
            }
            all_generated_matches.append(current_match)
            torneo["next_match_id"] = match_id_counter + 1 # Incrementa per la prossima partita

            # Aggiorna lo stato dei giocatori in torneo['players_dict']
            wp_id = current_match['white_player_id']
            bp_id = current_match['black_player_id'] # Sarà None se BYE
            
            if wp_id and wp_id in torneo['players_dict']:
                player_w_dict_entry = torneo['players_dict'][wp_id] # Lavoriamo direttamente sul dizionario
                
                if match_info.get('is_bye', False): # Gestione specifica BYE
                    print(f"Info: Giocatore {wp_id} riceve il BYE per il turno {round_number}.")
                    player_w_dict_entry['received_bye_in_round'] = player_w_dict_entry.get('received_bye_in_round', [])
                    player_w_dict_entry['received_bye_in_round'].append(round_number) # Memorizza in quale turno ha avuto il bye
                    player_w_dict_entry['received_bye_count'] = player_w_dict_entry.get('received_bye_count', 0) + 1 # Conteggio bye totali
                    
                    player_w_dict_entry['points'] = float(player_w_dict_entry.get('points', 0.0)) + 1.0 # Assumiamo 1 punto per il bye
                    
                    if "results_history" not in player_w_dict_entry: player_w_dict_entry["results_history"] = []
                    player_w_dict_entry["results_history"].append({
                        "round": round_number, "opponent_id": "BYE_PLAYER_ID", 
                        "color": None, "result": "BYE", "score": 1.0 # Punteggio ottenuto in QUESTA "partita"
                    })
                    # Per un BYE, non si aggiornano statistiche colore o avversari diretti
                    # last_color potrebbe rimanere invariato o settato a None per il turno del bye
                    # player_w_dict_entry['last_color'] = None 
                    # consecutive_white/black non si resettano né incrementano con un bye

                else: # Partita normale
                    if bp_id is None: # Controllo di sicurezza, non dovrebbe accadere se is_bye è False
                        print(f"ERRORE: Partita normale per {wp_id} ma black_player_id è None.")
                        continue

                    player_w_dict_entry['opponents'] = set(player_w_dict_entry.get('opponents', [])) 
                    player_w_dict_entry['opponents'].add(bp_id)
                    player_w_dict_entry['white_games'] = player_w_dict_entry.get('white_games', 0) + 1
                    player_w_dict_entry['last_color'] = 'white'
                    player_w_dict_entry['consecutive_white'] = player_w_dict_entry.get('consecutive_white', 0) + 1
                    player_w_dict_entry['consecutive_black'] = 0
            
            if bp_id and bp_id in torneo['players_dict']: # Se non è un BYE (bp_id esiste)
                player_b_dict_entry = torneo['players_dict'][bp_id] # Lavoriamo direttamente sul dizionario
                player_b_dict_entry['opponents'] = set(player_b_dict_entry.get('opponents', [])) 
                player_b_dict_entry['opponents'].add(wp_id)
                player_b_dict_entry['black_games'] = player_b_dict_entry.get('black_games', 0) + 1
                player_b_dict_entry['last_color'] = 'black'
                player_b_dict_entry['consecutive_black'] = player_b_dict_entry.get('consecutive_black', 0) + 1
                player_b_dict_entry['consecutive_white'] = 0
        
        # La variabile globale next_match_id è già stata aggiornata nel loop
        # torneo["next_match_id"] = torneo.get("next_match_id", 1) + len(all_generated_matches) # Spostato nel loop

    else: # bbpPairings.exe ha fallito
        returncode = bbp_output_data.get('returncode', -1) if bbp_output_data else -1
        if returncode == 1:
            print("ATTENZIONE: bbpPairings non ha trovato abbinamenti validi.")
            return handle_bbpairings_failure(torneo, round_number, "bbpPairings: Nessun abbinamento valido trovato.")
        else:
            print(f"ERRORE CRITICO da bbpPairings.exe: {bbp_message}")
            return handle_bbpairings_failure(torneo, round_number, f"Errore critico bbpPairings:\n{bbp_message}")

    # Sincronizzazione finale di torneo['players'] con i dati aggiornati da torneo['players_dict']
    # È FONDAMENTALE che questa sincronizzazione avvenga correttamente.
    # L'approccio migliore è iterare la lista originale torneo['players'] e aggiornare
    # ogni dizionario giocatore con la sua versione corrispondente (e aggiornata) da torneo['players_dict'].
    temp_updated_players_list = []
    for p_original_in_list in torneo.get('players', []):
        player_id = p_original_in_list['id']
        if player_id in torneo['players_dict']:
            # Prendi la versione più aggiornata dal dizionario
            temp_updated_players_list.append(torneo['players_dict'][player_id])
        else:
            # Giocatore non più nel dizionario? Improbabile se non per errori gravi.
            # Manteniamo l'originale per non perdere dati, ma segnaliamo.
            print(f"AVVISO: Giocatore {player_id} non trovato in players_dict durante la sincronizzazione finale.")
            temp_updated_players_list.append(p_original_in_list) 
    torneo['players'] = temp_updated_players_list
    print(f"--- Abbinamenti Turno {round_number} generati e stati giocatori aggiornati ---")
    return all_generated_matches

def handle_bbpairings_failure(torneo, round_number, error_message):
    """
    Gestisce i fallimenti di bbpPairings. Stampa un messaggio e indica fallimento.
    """
    print(f"\n--- FALLIMENTO GENERAZIONE ABBINAMENTI AUTOMATICI (Turno {round_number}) ---")
    print(error_message)
    print("Causa: bbpPairings.exe non è riuscito a generare gli abbinamenti.")
    print("Azione richiesta: Verificare il file 'input_bbp.trf' nella sottocartella 'bbppairings' per possibili errori di formato.")
    print("Oppure, considerare di effettuare gli abbinamenti per questo turno manualmente (su carta).")
    print("Il torneo non può procedere automaticamente per questo turno.")
    return None

def get_input_with_default(prompt_message, default_value=None):
    default_display = str(default_value) if default_value is not None else ""
    if default_display or default_value is None: 
        user_input = input(f"{prompt_message} [{default_display}]: ").strip()
        return user_input if user_input else default_value 
    else: 
        return input(f"{prompt_message}: ").strip()

def input_players(players_db): # players_db è un dizionario {id: data}
    players_in_tournament = []
    added_player_ids = set()
    db_modified_in_this_session = False 

    print("\n--- Inserimento Giocatori ---")
    print("Inserire ID esatto, oppure parte del Nome/Cognome per la ricerca.")
    print("Lasciare vuoto per terminare l'inserimento.")

    while True: # Inizio loop principale per ogni giocatore da inserire/cercare
        current_num_players = len(players_in_tournament)
        data_input_utente = input(f"\nGiocatore {current_num_players + 1} (ID o Ricerca Nome/Cognome, vuoto per terminare): ").strip()

        if not data_input_utente:
            min_players = 2 
            if current_num_players < min_players:
                print(f"\nAttenzione: Sono necessari almeno {min_players} giocatori per avviare il torneo.")
                continua = input("Ci sono meno di 2 giocatori. Continuare l'inserimento? (S/n): ").strip().lower()
                if continua == 'n':
                    print(f"\nInserimento terminato con {current_num_players} giocatori (insufficienti).")
                    break 
                else:
                    continue 
            else:
                print(f"\nInserimento terminato con {current_num_players} giocatori.")
                break 
        
        # --- INIZIALIZZAZIONE CORRETTA ALL'INIZIO DI OGNI ITERAZIONE DEL LOOP ---
        player_id_to_add = None
        player_record_in_db = None # Fondamentale inizializzarlo a None qui!
        elo_for_this_tournament = DEFAULT_ELO
        was_new_player_scenario = False # Flag per tracciare se siamo nel percorso "nuovo giocatore"
        
        # Valori finali per il giocatore nel torneo corrente
        final_fide_title = ""
        final_sex = "m"
        final_federation = "ITA"
        final_fide_id_num = "0"
        final_birth_date = None 
        first_name_for_tournament = "N/D"
        last_name_for_tournament = "N/D"
        # --------------------------------------------------------------------

        potential_id = data_input_utente.upper()
        
        # 1. TENTATIVO DI MATCH ESATTO ID
        if potential_id in players_db:
            print(f"Input riconosciuto come ID esatto: {potential_id}")
            player_id_to_add = potential_id
            player_record_in_db = players_db[potential_id] # ASSEGNATO
        
        # 2. TENTATIVO DI RICERCA PARZIALE (se non era ID esatto)
        else: 
            search_lower = data_input_utente.lower()
            matches = [p_data for id_db, p_data in players_db.items() 
                       if search_lower in p_data.get('first_name', '').lower() or \
                          search_lower in p_data.get('last_name', '').lower()]

            if len(matches) == 1:
                player_record_in_db = matches[0] # ASSEGNATO
                player_id_to_add = player_record_in_db['id']
                f_name = player_record_in_db.get('first_name','')
                l_name = player_record_in_db.get('last_name','')
                print(f"Trovato tramite ricerca: {f_name} {l_name} (ID: {player_id_to_add})")
            
            elif len(matches) > 1:
                print(f"Trovati {len(matches)} giocatori contenenti '{data_input_utente}'. Specifica usando l'ID esatto:")
                matches.sort(key=lambda p_item: (p_item.get('last_name', '').lower(), p_item.get('first_name', '').lower()))
                for i, p_match_item in enumerate(matches, 1):
                    p_id_disp = p_match_item.get('id', 'N/D')
                    p_fname_disp = p_match_item.get('first_name', 'N/D')
                    p_lname_disp = p_match_item.get('last_name', 'N/D')
                    p_elo_disp = p_match_item.get('current_elo', 'N/D')
                    p_title_disp = p_match_item.get('fide_title', '') 
                    title_prefix_disp = f"{p_title_disp} " if p_title_disp else ""
                    p_bdate_val = p_match_item.get('birth_date')
                    p_bdate_disp = format_date_locale(p_bdate_val) if p_bdate_val else 'N/D' # Assicurati che format_date_locale sia definita
                    print(f"  {i}. ID: {p_id_disp:<9} - {title_prefix_disp}{p_fname_disp} {p_lname_disp} (Elo DB: {p_elo_disp}, Nato: {p_bdate_disp})")
                continue 
            
            # 3. NESSUN MATCH -> NUOVO GIOCATORE
            else: 
                was_new_player_scenario = True 
                print(f"Nessun giocatore trovato per '{data_input_utente}'. Inserimento nuovo giocatore:")
                first_name_manual = input("  Nome: ").strip()
                if not first_name_manual: print("Inserimento annullato."); continue 
                last_name_manual = input("  Cognome: ").strip()
                if not last_name_manual: print("Inserimento annullato."); continue 
                
                elo_manual_input_str = input(f"  Elo (default {DEFAULT_ELO}): ").strip()
                elo_for_this_tournament = DEFAULT_ELO
                if elo_manual_input_str:
                    try: elo_for_this_tournament = int(elo_manual_input_str)
                    except ValueError: print(f"    Elo non valido '{elo_manual_input_str}'. Uso {DEFAULT_ELO}.")
                
                final_fide_title = input(f"  Titolo FIDE per {first_name_manual} {last_name_manual} (es. FM, o lascia vuoto): ").strip().upper()[:3]
                while True:
                    sex_input_loop = input(f"  Sesso (m/w) [Default: m]: ").strip().lower() # Rinominata per evitare conflitto di scope
                    if sex_input_loop in ['m', 'w', '']: final_sex = sex_input_loop or 'm'; break
                    print("    Input non valido.")
                final_federation = input(f"  Federazione Giocatore (3 lettere, es. ITA) [Default: ITA]: ").strip().upper()[:3] or "ITA"
                final_fide_id_num_str_input = input(f"  ID FIDE Numerico (cifre, '0' se N/D) [Default: 0]: ").strip()
                final_fide_id_num = final_fide_id_num_str_input if final_fide_id_num_str_input.isdigit() else '0'
                if not final_fide_id_num_str_input : final_fide_id_num = '0'

                while True:
                    final_birth_date_str = input(f"  Data Nascita ({DATE_FORMAT_DB} es. 1990-01-20, o lascia vuoto): ").strip()
                    if not final_birth_date_str: final_birth_date = None; break
                    try: 
                        datetime.strptime(final_birth_date_str, DATE_FORMAT_DB)
                        final_birth_date = final_birth_date_str
                        break
                    except ValueError: print(f"    Formato data non valido. Usa {DATE_FORMAT_DB} o lascia vuoto.")
                
                player_id_to_add = add_or_update_player_in_db(players_db, first_name_manual, last_name_manual, elo_for_this_tournament)

                if player_id_to_add is None:
                    print("Errore durante creazione/aggiornamento del giocatore nel DB. Riprova.")
                    continue 
                
                player_record_in_db = players_db[player_id_to_add] # ASSEGNATO
                player_record_in_db['fide_title'] = final_fide_title
                player_record_in_db['sex'] = final_sex
                player_record_in_db['federation'] = final_federation
                player_record_in_db['fide_id_num_str'] = final_fide_id_num
                player_record_in_db['birth_date'] = final_birth_date 
                db_modified_in_this_session = True 
                
                first_name_for_tournament = first_name_manual
                last_name_for_tournament = last_name_manual
                print(f"Giocatore '{first_name_for_tournament} {last_name_for_tournament}' (ID: {player_id_to_add}) aggiunto al DB con dettagli.")

        # A questo punto, se player_record_in_db è stato assegnato (cioè non è None),
        # possiamo usarlo per popolare le variabili final_... se non era un nuovo giocatore.
        # Se era un nuovo giocatore, le variabili final_... sono già state popolate dall'input.
        if player_record_in_db and not was_new_player_scenario: 
            # Questo blocco ora si esegue solo se il giocatore è stato trovato nel DB
            # (ID esatto o ricerca singola), e NON è il percorso del nuovo giocatore.
            if not player_id_to_add : player_id_to_add = player_record_in_db['id'] # Assicura sia settato
            elo_for_this_tournament = int(player_record_in_db.get('current_elo', DEFAULT_ELO))
            
            # CORREZIONE: Usare player_record_in_db per leggere i valori
            final_fide_title = str(player_record_in_db.get('fide_title', '')).strip().upper()
            final_sex = str(player_record_in_db.get('sex', 'm')).lower()
            final_federation = str(player_record_in_db.get('federation', 'ITA')).upper()[:3]
            final_fide_id_num = str(player_record_in_db.get('fide_id_num_str', '0'))
            final_birth_date = player_record_in_db.get('birth_date') 
            first_name_for_tournament = player_record_in_db.get('first_name', 'N/D')
            last_name_for_tournament = player_record_in_db.get('last_name', 'N/D')

            # Assicurazioni finali sui default per i campi letti dal DB
            if not final_fide_title: final_fide_title = ""
            if not final_sex or final_sex not in ['m', 'w']: final_sex = "m"
            if not final_federation: final_federation = "ITA"
            if not final_fide_id_num.isdigit() : final_fide_id_num = "0"

        # --- Aggiunta Giocatore al Torneo ---
        if player_id_to_add: # Se un giocatore è stato identificato o creato con successo
            if player_id_to_add in added_player_ids:
                print(f"Errore: Giocatore ID {player_id_to_add} ({first_name_for_tournament} {last_name_for_tournament}) è già stato aggiunto a questo torneo.")
            else:
                player_data_for_tournament = {
                    "id": player_id_to_add,
                    "first_name": first_name_for_tournament,
                    "last_name": last_name_for_tournament,
                    "initial_elo": elo_for_this_tournament, 
                    
                    "fide_title": final_fide_title,
                    "sex": final_sex,
                    "federation": final_federation, 
                    "fide_id_num_str": final_fide_id_num, 
                    "birth_date": final_birth_date, 

                    "points": 0.0, "results_history": [], "opponents": set(),
                    "white_games": 0, "black_games": 0, "last_color": None,
                    "consecutive_white": 0, "consecutive_black": 0,
                    "received_bye_count": 0, 
                    "received_bye_in_round": [],
                    "buchholz": 0.0, "buchholz_cut1": None, 
                    "performance_rating": None, "elo_change": None,
                    "k_factor": None, "games_this_tournament": 0,
                    "downfloat_count": 0, 
                    "final_rank": None, "withdrawn": False
                }
                players_in_tournament.append(player_data_for_tournament)
                added_player_ids.add(player_id_to_add)
                title_display = f" ({final_fide_title})" if final_fide_title else ""
                print(f"-> Giocatore {first_name_for_tournament} {last_name_for_tournament}{title_display} (Elo Torneo: {elo_for_this_tournament}) aggiunto al torneo.")
    
    if db_modified_in_this_session:
        print("\nDatabase principale dei giocatori modificato (dettagli aggiunti a nuovi giocatori).")
        save_players_db(players_db) 
        print("Modifiche al database principale salvate.")
    return players_in_tournament

def update_match_result(torneo):
    """
    Chiede N.Scacchiera (relativo al turno) o Nome/Cognome per selezionare la partita, 
    aggiorna il risultato o gestisce 'cancella'.
    Restituisce True se almeno un risultato è stato aggiornato o cancellato 
    durante la sessione, False altrimenti.
    """
    any_changes_made_in_this_session = False
    current_round_num = torneo["current_round"]

    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    players_dict = torneo['players_dict']
    
    current_round_data = None
    round_index_in_torneo_rounds = -1
    for i, r_data_loop in enumerate(torneo.get("rounds", [])): # Rinominato r_data
        if r_data_loop.get("round") == current_round_num:
            current_round_data = r_data_loop
            round_index_in_torneo_rounds = i
            break
    
    if not current_round_data:
        print(f"ERRORE: Dati turno {current_round_num} non trovati per aggiornamento risultati.")
        return False

    while True: # Loop principale della sessione di input risultati
        # 1. Prepara la lista delle partite PENDENTI con il "Numero Scacchiera del Turno"
        pending_matches_info_list = [] # Lista di (num_scacchiera_turno, match_dict, nome_bianco, nome_nero)
        
        all_matches_in_this_round = current_round_data.get("matches", [])
        # Ordina tutte le partite del turno per ID globale per avere un ordine scacchiere consistente
        all_matches_this_round_sorted = sorted(all_matches_in_this_round, key=lambda m: m.get('id', 0))

        round_board_idx_counter = 0 # Contatore 0-based per le scacchiere del turno
        for match_obj in all_matches_this_round_sorted:
            round_board_idx_counter += 1 # Numero scacchiera 1-based per questo turno
            
            # Consideriamo questa partita per la visualizzazione e selezione solo se è pendente
            if match_obj.get("result") is None and match_obj.get("black_player_id") is not None:
                wp_obj = players_dict.get(match_obj.get('white_player_id'))
                bp_obj = players_dict.get(match_obj.get('black_player_id'))
                wp_name_disp = f"{wp_obj.get('first_name','N/A')} {wp_obj.get('last_name','')}" if wp_obj else "Giocatore Mancante"
                bp_name_disp = f"{bp_obj.get('first_name','N/A')} {bp_obj.get('last_name','')}" if bp_obj else "Giocatore Mancante"
                pending_matches_info_list.append(
                    (round_board_idx_counter, match_obj, wp_name_disp, bp_name_disp)
                )
        
        # Controlla se ci sono partite completate da poter cancellare (per l'opzione 'cancella')
        completed_matches_to_cancel = [
            m_c for m_c in all_matches_this_round_sorted # Usa la lista già ordinata
            if m_c.get("result") is not None and m_c.get("result") != "BYE"
        ]

        if not pending_matches_info_list and not completed_matches_to_cancel:
            if not any_changes_made_in_this_session: 
                 print(f"Info: Nessuna azione possibile per il turno {current_round_num} (nessuna partita pendente e nessuna da poter cancellare).")
            break 
            
        if pending_matches_info_list:
            print(f"\nPartite del turno {current_round_num} ancora da registrare (N. Scacchiera del Turno):")
            for displayed_board_num, match_dict_disp, w_name_disp, b_name_disp in pending_matches_info_list:
                wp_elo_disp = players_dict.get(match_dict_disp['white_player_id'], {}).get('initial_elo','?')
                bp_elo_disp = players_dict.get(match_dict_disp['black_player_id'], {}).get('initial_elo','?')
                print(f"  Sc. {displayed_board_num:<2} (IDG:{match_dict_disp.get('id')}) - {w_name_disp:<20} [{wp_elo_disp:>4}] vs {b_name_disp:<20} [{bp_elo_disp:>4}]")
        else:
            print(f"\nNessuna partita da registrare per il turno {current_round_num} (ma potresti voler cancellare un risultato).")
        pending_board_numbers_for_prompt_display = [str(match_info_tuple[0]) for match_info_tuple in pending_matches_info_list]
        board_numbers_str_for_prompt = "-".join(pending_board_numbers_for_prompt_display) if pending_board_numbers_for_prompt_display else "Nessuna"
        user_input_str = input(f"CS|nome|cognome|cancella: [{board_numbers_str_for_prompt}: ").strip()
        if not user_input_str: 
            break 

        selected_match_obj_for_processing = None 
        # selected_match_original_index_in_list = -1 # Lo troveremo dopo aver identificato selected_match_obj_for_processing

        if user_input_str.lower() == 'cancella':
            if not completed_matches_to_cancel:
                print("Nessuna partita completata in questo turno da poter cancellare.")
                continue
            print(f"\nPartite completate nel turno {current_round_num} (ID Globali):")
            completed_matches_to_cancel.sort(key=lambda m_sort: m_sort.get('id',0)) # Ordina per ID Globale
            for m_completed in completed_matches_to_cancel:
                wp_c = players_dict.get(m_completed.get('white_player_id'))
                bp_c = players_dict.get(m_completed.get('black_player_id'))
                wp_c_name = f"{wp_c.get('first_name','?')} {wp_c.get('last_name','?')}" if wp_c else "N/A"
                bp_c_name = f"{bp_c.get('first_name','?')} {bp_c.get('last_name','?')}" if bp_c else "N/A"
                print(f"  ID Glob: {m_completed.get('id','?'):<3} - {wp_c_name} vs {bp_c_name} = {m_completed.get('result','?')}")
            
            cancel_id_input = input("Inserisci ID Globale della partita da cui cancellare il risultato (o vuoto per annullare): ").strip()
            if not cancel_id_input: continue
            try:
                id_to_cancel = int(cancel_id_input)
                match_found_for_cancel = False
                for idx_match_original, match_in_round in enumerate(current_round_data["matches"]):
                    if match_in_round.get('id') == id_to_cancel and \
                       match_in_round.get("result") is not None and \
                       match_in_round.get("result") != "BYE":
                        
                        # --- Logica di cancellazione (come la tua versione precedente) ---
                        old_res = match_in_round['result']
                        wp_id_c = match_in_round['white_player_id']
                        bp_id_c = match_in_round['black_player_id']
                        wp_obj_c = players_dict.get(wp_id_c)
                        bp_obj_c = players_dict.get(bp_id_c)

                        if not wp_obj_c or not bp_obj_c:
                            print(f"ERRORE: Giocatori per partita ID {id_to_cancel} non trovati durante cancellazione.")
                            break # Esce dal for, il continue esterno riprenderà
                        
                        w_revert, b_revert = 0.0, 0.0
                        if old_res == "1-0": w_revert = 1.0
                        elif old_res == "0-1": b_revert = 1.0
                        elif old_res == "1/2-1/2": w_revert, b_revert = 0.5, 0.5
                        
                        wp_obj_c["points"] = float(wp_obj_c.get("points", 0.0)) - w_revert
                        bp_obj_c["points"] = float(bp_obj_c.get("points", 0.0)) - b_revert
                        
                        # Rimuovi da storico (logica semplificata, assicurati sia robusta)
                        wp_obj_c["results_history"] = [rh for rh in wp_obj_c.get("results_history",[]) if not (rh.get("round") == current_round_num and rh.get("opponent_id") == bp_id_c)]
                        bp_obj_c["results_history"] = [rh for rh in bp_obj_c.get("results_history",[]) if not (rh.get("round") == current_round_num and rh.get("opponent_id") == wp_id_c)]
                        
                        torneo["rounds"][round_index_in_torneo_rounds]["matches"][idx_match_original]["result"] = None
                        print(f"Risultato ({old_res}) della partita ID {id_to_cancel} cancellato.")
                        save_tournament(torneo)
                        # players_dict è già aggiornato per riferimento
                        any_changes_made_in_this_session = True
                        match_found_for_cancel = True
                        break 
                if not match_found_for_cancel:
                    print(f"ID {id_to_cancel} non corrisponde a una partita completata cancellabile.")
            except ValueError:
                print("ID non valido per la cancellazione.")
            continue # Torna al prompt principale del loop while True

        elif user_input_str.isdigit():
            try:
                board_num_choice = int(user_input_str)
                match_found_by_board = False
                for displayed_b_num, match_obj_dict, _, _ in pending_matches_info_list:
                    if displayed_b_num == board_num_choice:
                        selected_match_obj_for_processing = match_obj_dict
                        match_found_by_board = True
                        break
                if not match_found_by_board:
                    print(f"Numero Scacchiera (del turno) '{board_num_choice}' non valido o partita non pendente.")
                    continue
            except ValueError:
                print("Input numerico per Scacchiera non valido.")
                continue
        
        else: # Ricerca per Nome/Cognome
            search_term_lower = user_input_str.lower()
            candidate_matches_info = []
            for disp_b_num, match_o, wp_n, bp_n in pending_matches_info_list:
                if (search_term_lower in wp_n.lower()) or (search_term_lower in bp_n.lower()):
                    candidate_matches_info.append((disp_b_num, match_o, wp_n, bp_n))
            
            if not candidate_matches_info:
                print(f"Nessuna partita pendente trovata con giocatori che corrispondono a '{user_input_str}'.")
                continue
            elif len(candidate_matches_info) == 1:
                selected_match_obj_for_processing = candidate_matches_info[0][1]
                sel_board_disp, _, sel_w_disp, sel_b_disp = candidate_matches_info[0]
                print(f"Trovata partita unica (Sc. {sel_board_disp}): {sel_w_disp} vs {sel_b_disp}")
            else: 
                print(f"Trovate {len(candidate_matches_info)} partite pendenti per '{user_input_str}':")
                for disp_b_num_multi, match_d_multi, w_n_multi, b_n_multi in candidate_matches_info:
                    wp_elo_m_disp = players_dict.get(match_d_multi['white_player_id'], {}).get('initial_elo','?')
                    bp_elo_m_disp = players_dict.get(match_d_multi['black_player_id'], {}).get('initial_elo','?')
                    print(f"  Sc. {disp_b_num_multi:<2} (IDG:{match_d_multi.get('id')}) - {w_n_multi:<20} [{wp_elo_m_disp:>4}] vs {b_n_multi:<20} [{bp_elo_m_disp:>4}]")
                try:
                    specific_board_input = input("Inserisci il N.Scacchiera (del turno) desiderato dalla lista sopra: ").strip()
                    if not specific_board_input.isdigit():
                        print("Input non numerico per la scacchiera."); continue
                    specific_board_choice = int(specific_board_input)
                    for disp_b_num_cand, match_obj_cand, _, _ in candidate_matches_info:
                        if disp_b_num_cand == specific_board_choice:
                            selected_match_obj_for_processing = match_obj_cand
                            break
                    if not selected_match_obj_for_processing:
                        print(f"N.Scacchiera '{specific_board_choice}' non valido dalla lista filtrata."); continue
                except ValueError: print("Input Scacchiera non valido."); continue
        
        if selected_match_obj_for_processing:
            # Trova l'indice originale nella lista current_round_data["matches"]
            idx_in_original_list = -1
            for idx, m_orig_loop in enumerate(current_round_data["matches"]):
                if m_orig_loop['id'] == selected_match_obj_for_processing['id']:
                    idx_in_original_list = idx
                    break
            if idx_in_original_list == -1: 
                print(f"ERRORE INTERNO: Partita selezionata ID {selected_match_obj_for_processing['id']} non trovata."); continue

            wp_id_match = selected_match_obj_for_processing['white_player_id']
            bp_id_match = selected_match_obj_for_processing['black_player_id']
            wp_data_obj = players_dict.get(wp_id_match) 
            bp_data_obj = players_dict.get(bp_id_match) 

            if not wp_data_obj or not bp_data_obj:
                print(f"ERRORE CRITICO: Giocatori non trovati per partita ID {selected_match_obj_for_processing['id']}."); continue

            wp_name_match_disp = f"{wp_data_obj.get('first_name','?')} {wp_data_obj.get('last_name','?')}"
            bp_name_match_disp = f"{bp_data_obj.get('first_name','?')} {bp_data_obj.get('last_name','?')}"
            print(f"Partita selezionata per risultato: {wp_name_match_disp} vs {bp_name_match_disp} (ID Glob: {selected_match_obj_for_processing['id']})")
            
            result_input = input("Risultato [1-0, 0-1, 1/2, 0-0F, 1-F, F-1]: ").strip()
            parsed_result_str = None 
            parsed_w_score = 0.0
            parsed_b_score = 0.0
            valid_res_input = True

            if result_input == '1-0': parsed_result_str, parsed_w_score = "1-0", 1.0
            elif result_input == '0-1': parsed_result_str, parsed_b_score = "0-1", 1.0
            elif result_input == '1/2': parsed_result_str, parsed_w_score, parsed_b_score = "1/2-1/2", 0.5, 0.5
            elif result_input == '0-0F': parsed_result_str = "0-0F"; print("Doppio forfeit registrato (0-0F).") # Punti rimangono 0
            elif result_input == '1-F': parsed_result_str, parsed_w_score = "1-F", 1.0; print("Vittoria Bianco per Forfait avv. (1-F).")
            elif result_input == 'F-1': parsed_result_str, parsed_b_score = "F-1", 1.0; print("Vittoria Nero per Forfait Bianco (F-1).")
            else: valid_res_input = False
            
            if valid_res_input and parsed_result_str is not None:
                confirm_message_str = f"Risultato '{parsed_result_str}' non standard. Confermi comunque? (s/n): " # Fallback
                if parsed_result_str == "1-0":
                    confirm_message_str = f"Confermi che {wp_name_match_disp} vince contro {bp_name_match_disp}? (s/n): "
                elif parsed_result_str == "0-1":
                    confirm_message_str = f"Confermi che {bp_name_match_disp} vince contro {wp_name_match_disp}? (s/n): "
                elif parsed_result_str == "1/2-1/2":
                    confirm_message_str = f"Confermi che {wp_name_match_disp} e {bp_name_match_disp} pattano? (s/n): "
                elif parsed_result_str == "0-0F":
                    confirm_message_str = f"Confermi partita nulla/annullata (0-0F) tra {wp_name_match_disp} e {bp_name_match_disp}? (s/n): "
                elif parsed_result_str == "1-F": # Vittoria del Bianco per forfeit del Nero
                    confirm_message_str = f"Confermi vittoria a tavolino per {wp_name_match_disp} (forfait di {bp_name_match_disp})? (s/n): "
                elif parsed_result_str == "F-1": # Vittoria del Nero per forfeit del Bianco
                    confirm_message_str = f"Confermi vittoria a tavolino per {bp_name_match_disp} (forfait di {wp_name_match_disp})? (s/n): "           
                user_confirm_input = input(confirm_message_str).strip().lower()
                if user_confirm_input == 's':
                    wp_data_obj["points"] = float(wp_data_obj.get("points", 0.0)) + parsed_w_score
                    bp_data_obj["points"] = float(bp_data_obj.get("points", 0.0)) + parsed_b_score
                    if "results_history" not in wp_data_obj: wp_data_obj["results_history"] = []
                    if "results_history" not in bp_data_obj: bp_data_obj["results_history"] = []
                    wp_data_obj["results_history"].append({
                        "round": current_round_num, "opponent_id": bp_id_match, # Usa bp_id_match
                        "color": "white", "result": parsed_result_str, "score": parsed_w_score
                    })
                    bp_data_obj["results_history"].append({
                        "round": current_round_num, "opponent_id": wp_id_match, # Usa wp_id_match
                        "color": "black", "result": parsed_result_str, "score": parsed_b_score
                    })
                    torneo["rounds"][round_index_in_torneo_rounds]["matches"][idx_in_original_list]["result"] = parsed_result_str
                    
                    print("Risultato registrato.")
                    save_tournament(torneo) 
                    any_changes_made_in_this_session = True
                else:
                    print("Operazione annullata dall'utente.")
            elif not valid_res_input:
                print("Input risultato non valido.")
                
    return any_changes_made_in_this_session

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
            f.write("\tgiocate:\n")
            if played_matches:
                for p_match_str in played_matches:
                    f.write(f"\t\t{p_match_str}\n")
            else:
                f.write("\t\t(nessuna)\n")
            f.write("\tDa giocare:\n")
            if pending_matches:
                for pend_match_str in pending_matches:
                    f.write(f"\t\t{pend_match_str}\n")
            else:
                f.write("\t\t(nessuna)\n")
            if bye_player_info:
                f.write(f"\n\t\t{bye_player_info}\n")
        print(f"File stato turno corrente '{filename}' sovrascritto.")
    except IOError as e:
        print(f"Errore durante la sovrascrittura del file stato turno corrente '{filename}': {e}")


def append_completed_round_to_history_file(torneo, completed_round_number):
    """
    Salva i dettagli di un turno concluso in un FILE SEPARATO per quel turno.
    Il file viene creato o sovrascritto.
    """
    tournament_name = torneo.get('name', 'Torneo_Senza_Nome')
    sanitized_name = sanitize_filename(tournament_name)
    # NUOVO NOME FILE: specifico per il turno
    filename = f"tornello - {sanitized_name} - Turno {completed_round_number} Dettagli.txt" 

    round_data = None
    for rnd in torneo.get("rounds", []):
        if rnd.get("round") == completed_round_number:
            round_data = rnd
            break
    
    if round_data is None or "matches" not in round_data:
        print(f"Dati o partite del turno concluso {completed_round_number} non trovati per il salvataggio.")
        return

    # Assicura che il dizionario dei giocatori sia aggiornato
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
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
            f.write(f"Torneo: {torneo.get('name', 'Nome Mancante')}\n")
            f.write(f"Sito: {torneo.get('site', 'N/D')}, Data Inizio Torneo: {format_date_locale(torneo.get('start_date'))}\n") # Aggiunta Info
            f.write("=" * 80 + "\n")
            f.write("\n" + "="*30 + f" DETTAGLIO TURNO {completed_round_number} CONCLUSO " + "="*26 + "\n") # Modificato titolo leggermente
            
            round_dates_list = torneo.get("round_dates", [])
            current_round_dates = next((rd for rd in round_dates_list if rd.get("round") == completed_round_number), None)
            if current_round_dates:
                start_d_str = current_round_dates.get('start_date')
                end_d_str = current_round_dates.get('end_date')
                f.write(f"\tPeriodo del Turno: {format_date_locale(start_d_str)} - {format_date_locale(end_d_str)}\n")
            else:
                f.write("\tPeriodo del Turno: Date non trovate\n")
            
            f.write("\t"+"-" * 76 + "\n")
            header_partite = "Sc | ID  | Bianco                       [Elo] (Pt) - Nero                         [Elo] (Pt) | Risultato"
            f.write(f"\t{header_partite}\n")
            f.write(f"\t" + "-" * len(header_partite) + "\n")

            for board_num_idx, match in enumerate(playable_matches):
                board_num = board_num_idx + 1
                match_id = match.get('id', '?')
                white_p_id = match.get('white_player_id')
                black_p_id = match.get('black_player_id')
                result_str = match.get("result", "ERRORE_RISULTATO_MANCANTE")
                
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
                    line = f"{'---':<3}| {match_id:<4}| Errore Giocatore Bye ID: {white_p_id:<10} | BYE"
                    f.write(f"\t{line}\n")
            
        print(f"Dettaglio Turno Concluso {completed_round_number} salvato nel file separato '{filename}'")
    except IOError as e:
        print(f"Errore durante il salvataggio del file del turno '{filename}': {e}")
    except Exception as general_e:
        print(f"Errore inatteso durante il salvataggio del file del turno: {general_e}")
        traceback.print_exc()

def save_standings_text(torneo, final=False):
    """
    Salva/Sovrascrive la classifica (parziale o finale) in un unico file TXT.
    Include dettagli del torneo nell'header e Titolo FIDE per i giocatori.
    """
    players = torneo.get("players", [])
    if not players:
        print("Attenzione: Nessun giocatore per generare la classifica.")
        return
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(players):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}

    print("Calcolo/Aggiornamento Buchholz per classifica...")
    for p in players:
        p_id = p.get('id')
        if not p_id: continue
        if not p.get("withdrawn", False):
            # Assicurati che il dizionario 'torneo' completo sia passato a compute_buchholz
            p["buchholz"] = compute_buchholz(p_id, torneo) 
            if final and "buchholz_cut1" not in p: # Calcola B-1 solo se finale e non già fatto
                p["buchholz_cut1"] = compute_buchholz_cut1(p_id, torneo)
            elif not final:
                p["buchholz_cut1"] = None 
        else: # Giocatori ritirati
            p["buchholz"] = 0.0
            p["buchholz_cut1"] = None
            p["final_rank"] = "RIT" # Assicurati che il rank per i ritirati sia gestito

    # Ordinamento (la chiave di sort usa i campi esistenti in 'player')
    # Se 'final=True', i campi 'aro', 'performance_rating', 'elo_change', 'final_rank' 
    # dovrebbero essere già stati calcolati da finalize_tournament.
    def sort_key_standings(player_item):
        if player_item.get("withdrawn", False):
            # Metti i ritirati in fondo, ordinati per punteggio decrescente se vuoi, o un valore fisso
            return (0, -float(player_item.get("points", 0.0)), 0, 0, 0, 0) # (categoria_ritirati, -punti, ...)
        
        points_val = float(player_item.get("points", 0.0))
        # Per classifiche parziali, buchholz_cut1 potrebbe essere None
        bucch_c1_val = float(player_item.get("buchholz_cut1", 0.0) if player_item.get("buchholz_cut1") is not None else 0.0)
        bucch_tot_val = float(player_item.get("buchholz", 0.0))
        
        # Performance e Elo iniziale sono usati come ulteriori spareggi se presenti
        # (più rilevanti per la classifica finale)
        performance_val = int(player_item.get("performance_rating", 0) if player_item.get("performance_rating") is not None else 0)
        elo_initial_val = int(player_item.get("initial_elo", 0))
        
        # Priorità: Punti, BucchCut1 (se finale), BucchTot, Performance (se finale), Elo iniziale
        return (1, -points_val, -bucch_c1_val if final else 0, -bucch_tot_val, -performance_val if final else 0, -elo_initial_val)

    try:
        players_sorted = sorted(players, key=sort_key_standings, reverse=True) # reverse=True non serve se i criteri sono negativi
        players_sorted = sorted(players, key=sort_key_standings) 


        # Assegnazione del rango visualizzato (se non è una classifica finale già processata da finalize_tournament)
        # Se final=True, 'final_rank' dovrebbe già esistere su ogni 'player'.
        # Questa logica serve per le classifiche parziali o se 'final_rank' non è stato pre-calcolato.
        if not final or (players_sorted and "final_rank" not in players_sorted[0] and not players_sorted[0].get("withdrawn")):
            current_display_rank = 0
            last_sort_key_tuple = None
            for i, p_item in enumerate(players_sorted):
                if p_item.get("withdrawn", False):
                    p_item["display_rank"] = "RIT" # display_rank per i ritirati
                    continue
                
                current_sort_key_tuple = sort_key_standings(p_item)[1:] # Escludi il primo elemento (categoria ritirati/attivi)
                if current_sort_key_tuple != last_sort_key_tuple:
                    current_display_rank = i + 1
                p_item["display_rank"] = current_display_rank
                last_sort_key_tuple = current_sort_key_tuple
        elif final: # Per classifica finale, usa 'final_rank' se esiste, altrimenti calcola display_rank
            for i, p_item in enumerate(players_sorted):
                if "final_rank" in p_item:
                    p_item["display_rank"] = p_item["final_rank"]
                elif p_item.get("withdrawn", False):
                     p_item["display_rank"] = "RIT"
                else: # Fallback se final_rank manca inspiegabilmente
                    p_item["display_rank"] = i + 1


    except Exception as e:
        print(f"Errore durante l'ordinamento dei giocatori per la classifica: {e}")
        traceback.print_exc()
        players_sorted = players # Usa lista non ordinata in caso di errore grave di sort

    tournament_name_file = torneo.get('name', 'Torneo_Senza_Nome')
    sanitized_name_file = sanitize_filename(tournament_name_file)
    filename = f"tornello - {sanitized_name_file} - Classifica.txt" # Unico file, sovrascritto
    
    status_line = ""
    if final:
        status_line = "CLASSIFICA FINALE"
    else:
        current_round_in_state = torneo.get("current_round", 0)
        # Determina se ci sono risultati per capire se è prima del T1 o dopo un turno N
        has_any_results = any(p.get("results_history") for p in players)
        
        if not has_any_results and current_round_in_state == 1:
            status_line = f"Elenco Iniziale Partecipanti (Prima del Turno 1)"
        else:
            # Se siamo al turno N e ci sono risultati, la classifica è "dopo il turno N-1"
            # Se siamo al turno N e non ci sono risultati (es. prima di generare abb T1), è "prima del turno N"
            # Se il T1 è stato generato ma non ci sono risultati, current_round è 1.
            # La logica qui sotto cerca di mostrare lo stato corretto
            round_for_title = current_round_in_state
            all_matches_for_current_round_done = True
            if not final and current_round_in_state > 0 and current_round_in_state <= torneo.get("total_rounds",0):
                for r_data in torneo.get("rounds", []):
                    if r_data.get("round") == current_round_in_state:
                        for m in r_data.get("matches", []):
                            if m.get("result") is None and m.get("black_player_id") is not None: # Partita pendente non BYE
                                all_matches_for_current_round_done = False
                                break
                        break
                if all_matches_for_current_round_done and current_round_in_state > 0 :
                     status_line = f"Classifica Parziale - Dopo Turno {current_round_in_state}"
                elif current_round_in_state > 0 :
                     status_line = f"Classifica Parziale - Durante Turno {current_round_in_state}"
    try:
        with open(filename, "w", encoding='utf-8-sig') as f:
            f.write(f"Nome Torneo: {torneo.get('name', 'N/D')}\n")
            # --- INIZIO NUOVE INTESTAZIONI TORNEO ---
            f.write(f"Luogo: {torneo.get('site', 'N/D')}\n")
            f.write(f"Date: {format_date_locale(torneo.get('start_date'))} - {format_date_locale(torneo.get('end_date'))}\n")
            f.write(f"Federazione Organizzante: {torneo.get('federation_code', 'N/D')}\n")
            f.write(f"Arbitro Capo: {torneo.get('chief_arbiter', 'N/D')}\n")
            deputy_arbiters_str = torneo.get('deputy_chief_arbiters', '')
            if deputy_arbiters_str and deputy_arbiters_str.strip():
                f.write(f"Vice Arbitri: {deputy_arbiters_str}\n")
            f.write(f"Controllo Tempo: {torneo.get('time_control', 'N/D')}\n")
            f.write(f"Sistema di Abbinamento: Svizzero Olandese (via bbpPairings)\n") # Info aggiuntiva
            f.write(f"Data Report: {format_date_locale(datetime.now().date())} {datetime.now().strftime('%H:%M:%S')}\n")
            f.write("-" * 70 + "\n")
            # Header Tabella Giocatori
            # Adattiamo la larghezza per fare spazio al titolo
            header_table = "Pos. Titolo Nome Cognome                 [EloIni] Punti  Bucch-1 Bucch "
            if final:
                header_table += " ARO  Perf  Elo Var." # Elo Var. invece di +/-Elo per chiarezza
            f.write(header_table + "\n")
            f.write("-" * len(header_table) + "\n")
            for player in players_sorted:
                rank_to_show = player.get("display_rank", "?")
                if isinstance(rank_to_show, (int, float)): # rank numerico
                    rank_display_str = f"{int(rank_to_show):>3}."
                else: # Es. "RIT"
                    rank_display_str = f"{str(rank_to_show):>3} " # Spazio dopo per allineare con punto
                fide_title = str(player.get('fide_title', '')).strip().upper()
                # Nome Cognome, consideriamo una larghezza fissa per nome+cognome+virgola
                # Es. 30 caratteri per "Cognome, Nome"
                player_name_str = f"{player.get('last_name', 'N/D')}, {player.get('first_name', 'N/D')}"
                # Larghezza totale per Titolo + Nome Cognome. Esempio: 3 (titolo) + 1 (sp) + 30 (nome) = 34
                title_display_str = f"{fide_title:<3}" # Max 3 caratteri per titolo, allineato a sx
                name_display_str = f"{player_name_str:<27.27}" # Max 27 caratteri per Nome Cognome
                elo_ini_str = f"[{int(player.get('initial_elo', DEFAULT_ELO)):4d}]"
                points_str = f"{float(player.get('points', 0.0)):5.1f}" # 5.1f per es. "100.0" o "  1.5"
                
                bucch_c1_val = player.get('buchholz_cut1')
                bucch_c1_str = f"{float(bucch_c1_val):7.2f}" if bucch_c1_val is not None else "   ----"
                
                bucch_tot_str = f"{float(player.get('buchholz', 0.0)):6.2f}"

                line = (f"{rank_display_str} {title_display_str} {name_display_str} "
                        f"{elo_ini_str} {points_str} {bucch_c1_str} {bucch_tot_str}")

                if final:
                    if player.get("withdrawn", False):
                        aro_str, perf_str, elo_change_str = " ---", "----", " ---"
                    else:
                        aro_val = player.get('aro')
                        aro_str = f"{int(aro_val):4d}" if aro_val is not None else " ---"
                        
                        perf_val = player.get('performance_rating')
                        perf_str = f"{int(perf_val):4d}" if perf_val is not None else "----"
                        
                        elo_change_val = player.get('elo_change')
                        elo_change_str = f"{int(elo_change_val):+4d}" if elo_change_val is not None else " ---"
                    line += f" {aro_str} {perf_str} {elo_change_str}"
                f.write(line + "\n")
            print(f"File classifica '{filename}' salvato/sovrascritto.")
    except IOError as e:
        print(f"Errore durante il salvataggio del file classifica '{filename}': {e}")
    except Exception as general_e:
        print(f"Errore inatteso durante save_standings_text: {general_e}")
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
    print(f"\nBENVENUTI! Sono Tornello {VERSIONE}\n\tQuesta è la nostra {launch_count}a volta assieme.\n\tCopyright 2025, dedicato all'ASCId e al gruppo Scacchierando.")
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
        # --- INIZIO NUOVI INPUT PER HEADER TRF ---
        print("\nInserisci i dettagli aggiuntivi del torneo (lascia vuoto per usare default):")
        default_site = "Luogo Sconosciuto"
        torneo["site"] = input(f"  Luogo del torneo [Default: {default_site}]: ").strip() or default_site
        default_fed_code = "ITA"
        torneo["federation_code"] = input(f"  Federazione organizzante (codice 3 lettere) [Default: {default_fed_code}]: ").strip().upper() or default_fed_code
        if len(torneo["federation_code"]) > 3: torneo["federation_code"] = torneo["federation_code"][:3]
        default_chief_arbiter = "N/D"
        torneo["chief_arbiter"] = input(f"  Arbitro Capo [Default: {default_chief_arbiter}]: ").strip() or default_chief_arbiter
        default_deputy_arbiters = "" # Lasciare vuoto se nessuno
        torneo["deputy_chief_arbiters"] = input(f"  Vice Arbitri (separati da virgola se più di uno) [Default: nessuno]: ").strip() or default_deputy_arbiters
        default_time_control = "Standard"
        torneo["time_control"] = input(f"  Controllo del Tempo [Default: {default_time_control}]: ").strip() or default_time_control
        while True:
            board1_choice = input(f"  Bianco alla prima scacchiera del T1? (S/n) [Default: S]: ").strip().lower()
            if board1_choice == 's' or board1_choice == '':
                torneo['initial_board1_color_setting'] = "white1" # Valore usato nel TRF
                print("    -> Il Bianco inizierà sulla prima scacchiera del Turno 1.")
                break
            elif board1_choice == 'n':
                torneo['initial_board1_color_setting'] = "black1" # Valore usato nel TRF
                print("    -> Il Nero inizierà sulla prima scacchiera del Turno 1.")
                break
            else:
                print("    Risposta non valida. Inserisci 's' o 'n'.")
        # --- FINE NUOVI INPUT PER HEADER TRF ---
        # Calcola date turni
        round_dates = calculate_dates(torneo["start_date"], torneo["end_date"], torneo["total_rounds"])
        if round_dates is None:
            # Indentazione corretta
            print("Errore fatale nel calcolo delle date dei turni. Impossibile creare il torneo.")
            sys.exit(1)
        torneo["round_dates"] = round_dates
        # Input giocatori
        torneo["players"] = input_players(players_db)
        num_giocatori = len(torneo.get("players", []))
        num_turni_totali = torneo.get("total_rounds") # Assumiamo che sia stato impostato a un intero
        if num_giocatori < 2 or \
           (isinstance(num_turni_totali, int) and num_turni_totali > 0 and num_giocatori < (num_turni_totali + 1)):
            print("Numero insufficiente di giocatori validi inseriti per il numero di turni specificato. Torneo annullato.")
            sys.exit(0)
        # Inizializza stato torneo
        torneo["current_round"] = 1
        torneo["rounds"] = [] # Lista per contenere i dati di ogni turno (partite)
        torneo["next_match_id"] = 1
        torneo["k_factor"] = DEFAULT_K_FACTOR # Usa K default
        torneo["site"] = torneo.get("site", "Luogo Sconosciuto") # Chiedilo o usa default
        torneo["federation_code"] = torneo.get("federation_code", "ITA") # Federazione del torneo
        torneo["chief_arbiter"] = torneo.get("chief_arbiter", "Nome Arbitro Default")
        torneo["time_control"] = torneo.get("time_control", "Cadenza Standard")
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
            torneo["rounds"].append(round_entry)
        except Exception as e_append:
             print(f"ERRORE durante l'append di round data: {e_append}") # DEBUG
             traceback.print_exc()
             sys.exit(1) # Esci se l'append fallisce
        # Salva stato iniziale torneo e file T1
        save_tournament(torneo) # Ora salva con il round 1 dentro
        save_current_tournament_round_file(torneo)
        save_standings_text(torneo, final=False) # Salva classifica iniziale T0
        print("\nTorneo creato e Turno 1 generato.")
    else:
        print(f"Torneo '{torneo.get('name','N/D')}' in corso rilevato da {TOURNAMENT_FILE}.")
        if 'players' not in torneo: torneo['players'] = []
        for p in torneo["players"]:
            p['opponents'] = set(p.get('opponents', [])) # Ricostruisci set
            p.setdefault('consecutive_white', 0)
            p.setdefault('consecutive_black', 0)
        if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players', [])):
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
                if r.get("round") == current_round_num:
                    current_round_data = r
                    round_index = i
                    break
            if current_round_data is None:
                print(f"ERRORE CRITICO: Dati per il turno corrente {current_round_num} non trovati nella struttura del torneo!")
                break # Interrompi esecuzione
            # Verifica se il turno corrente è completo
            round_completed = True
            if "matches" in current_round_data:
                for m in current_round_data["matches"]:
                    if m.get("result") is None and m.get("black_player_id") is not None:
                        round_completed = False
                        break # Basta una partita pendente
            else:
                print(f"Warning: Nessuna partita trovata per il turno {current_round_num}.")
                round_completed = False # Considera incompleto
            # --- Flusso: Registra Risultati o Avanza Turno ---
            if not round_completed:
                modifications_made_this_session = update_match_result(torneo)
                print("\nSessione di inserimento/modifica risultati terminata.")
                print("Salvataggio file di report del turno corrente e classifica parziale...")
                save_current_tournament_round_file(torneo)
                save_standings_text(torneo, final=False)
                break
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
                        print(f"\nERRORE CRITICO durante la generazione del turno {next_round_num}: {e}")
                        print("Il torneo potrebbe essere in uno stato inconsistente.")
                        traceback.print_exc()
                        # Prova a salvare lo stato attuale
                        torneo["current_round"] = current_round_num # Ripristina per sicurezza
                        save_tournament(torneo)
                        break # Interrompi torneo
    except KeyboardInterrupt:
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
