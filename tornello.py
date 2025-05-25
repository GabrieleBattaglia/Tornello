# Tornello by Gabriele Battaglia & Gemini 2.5
# Data concepimento: 28 marzo 2025
import os, json, sys, math, traceback, subprocess
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
# --- Constants ---
VERSIONE = "5.0.3 del 25 maggio 2025"
PLAYER_DB_FILE = "tornello - giocatori_db.json"
PLAYER_DB_TXT_FILE = "tornello - giocatori_db.txt"
TOURNAMENT_FILE = "Tornello - torneo.json"
DATE_FORMAT_ISO = "%Y-%m-%d"
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
        trf_lines.append(f"012 {str(dati_torneo.get('name', 'Torneo Default'))[:45]:<45}\n")
        trf_lines.append(f"022 {str(dati_torneo.get('site', 'Default Site'))[:45]:<45}\n")
        trf_lines.append(f"032 {str(dati_torneo.get('federation_code', 'ITA'))[:3]:<3}\n")
        trf_lines.append(f"042 {start_date_strf}\n")
        trf_lines.append(f"052 {end_date_strf}\n")
        trf_lines.append(f"062 {number_of_players_val:03d}\n")
        trf_lines.append(f"072 {number_of_players_val:03d}\n") 
        trf_lines.append("082 000\n") 
        trf_lines.append("092 Individual: Swiss-System\n")
        trf_lines.append(f"102 {str(dati_torneo.get('chief_arbiter', 'Default Arbiter'))[:45]:<45}\n")
        trf_lines.append("112 \n") 
        trf_lines.append(f"122 {str(dati_torneo.get('time_control', 'Standard'))[:45]:<45}\n")
        trf_lines.append(f"XXR {total_rounds_val:03d}\n")
        trf_lines.append("XXC white1\n") # Configura colore iniziale per il torneo

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
            elo = int(player_data.get('initial_elo', 1000)) 
            federazione_giocatore = str(player_data.get('federation', 'ITA')).upper()[:3]
            
            # Usa i campi specifici dal tuo player_data. Questi sono esempi.
            fide_id_from_playerdata = str(player_data.get('fide_id_num_str', '0')) 
            birth_date_from_playerdata = str(player_data.get('birth_short_str', '19000101')) 
            title_from_playerdata = str(player_data.get('title_str', '')).strip()

            # Scrittura campi anagrafici
            write_to_char_list_local(p_line_chars, 1, "001")
            write_to_char_list_local(p_line_chars, 5, f"{start_rank:>4}")
            write_to_char_list_local(p_line_chars, 10, player_data.get('sex', 'm')) 
            write_to_char_list_local(p_line_chars, 11, f"{title_from_playerdata:>3}"[:3])
            write_to_char_list_local(p_line_chars, 15, f"{nome_completo:<33}"[:33])
            write_to_char_list_local(p_line_chars, 49, f"{elo:<4}") 
            write_to_char_list_local(p_line_chars, 54, f"{federazione_giocatore:<3}"[:3])
            
            fide_id_core_digits = f"{fide_id_from_playerdata.zfill(6)}"[:6] 
            fide_id_final_field = f"   {fide_id_core_digits}  " 
            write_to_char_list_local(p_line_chars, 58, fide_id_final_field)

            write_to_char_list_local(p_line_chars, 70, f"{birth_date_from_playerdata:<10}"[:10])
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
                player_id = player.get('id', 'N/D') # Prendi ID per passarlo a get_k_factor (utile per debug lì)
                f.write(f"ID: {player_id}, ")
                f.write(f"{player.get('first_name', 'N/D')} {player.get('last_name', 'N/D')}, ")
                f.write(f"Elo: {player.get('current_elo', 'N/D')}\n")
                games_played_total = player.get('games_played', 0)
                f.write(f"\tPartite Valutate Totali: {games_played_total}, ")
                current_k_factor = get_k_factor(player, current_date_iso)
                f.write(f"K-Factor Stimato: {current_k_factor}, ")
                f.write(f"Data Iscrizione DB: {format_date_locale(player.get('registration_date'))}\n")
                birth_date_display = player.get('birth_date')
                f.write(f"\tData Nascita: {format_date_locale(birth_date_display) if birth_date_display else 'N/D'}\n") # Mostra anche data nascita
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
                         history_line = f"{rank_formatted}° su {t.get('total_players', '?')} in {t_name} - {start_date_formatted} - {end_date_formatted}"
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
    norm_last = last_name.strip().title() # Ora può contenere spazi, es "Di Bari"

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
        # Nota: .split() qui rimuove spazi interni dal cognome/nome PRIMA di prendere le iniziali.
        # Se vuoi iniziali da "Di Bari" come DB, questo va bene. Se volessi "DB", servirebbe logica diversa.
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
                # Indentazione corretta
                torneo_data = json.load(f)
                # Re-inizializza i set e campi necessari dopo il caricamento
                if 'players' in torneo_data:
                    for p in torneo_data['players']:
                        p['opponents'] = set(p.get('opponents', [])) # Ricrea il set
                        p.setdefault('white_games', 0)
                        p.setdefault('black_games', 0)
                        p.setdefault('last_color', None)
                        p.setdefault('received_bye', False)
                        p.setdefault('consecutive_white', 0)
                        p.setdefault('consecutive_black', 0)
                        p.setdefault('withdrawn', False)
                        p.setdefault('results_history', [])
                return torneo_data
        except (json.JSONDecodeError, IOError) as e:
            # Indentazione corretta
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

def create_match_from_color_result(color_result, torneo, round_number):
    """Crea un dizionario partita da un risultato valido ('W', W_ID, B_ID)."""
    if not color_result or color_result[0] != 'W':
        print(f"ERRORE create_match: Ricevuto risultato colore non valido: {color_result}")
        return None # Dovrebbe ricevere solo risultati validi
    white_id, black_id = color_result[1], color_result[2]
    match = {
        "id": torneo["next_match_id"],
        "round": round_number,
        "white_player_id": white_id,
        "black_player_id": black_id,
        "result": None
    }
    torneo["next_match_id"] += 1
    return match

def generate_pairings_for_round(torneo):
    """
    Genera gli abbinamenti per il turno corrente usando bbpPairings.exe.
    Include fallback a input manuale se bbpPairings fallisce.
    """
    round_number = torneo.get("current_round")
    if round_number is None:
        print("ERRORE: Numero turno corrente non definito nel torneo.")
        return None # O lista vuota
    
    print(f"\n--- Generazione Abbinamenti Turno {round_number} con bbpPairings ---")

    # Assicura che players_dict sia aggiornato e disponibile
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    
    players_for_pairing_objects = [
        p_obj.copy() for p_obj in torneo.get('players', []) 
        if not torneo['players_dict'][p_obj['id']].get("withdrawn", False)
    ]

    if not players_for_pairing_objects:
        print(f"Nessun giocatore attivo per il turno {round_number}.")
        return []

    # 1. Creare mappa ID Tornello -> StartRank (da 1 a N) e viceversa
    # L'ordinamento per StartRank è importante per bbpPairings
    # Usiamo un ordinamento di default (Elo decrescente, poi alfabetico) per assegnare gli StartRank
    # bbpPairings poi userà gli StartRank che gli passiamo nel file TRF.
    players_sorted_for_start_rank = sorted(
        players_for_pairing_objects, 
        key=lambda p: (-float(p.get('initial_elo', DEFAULT_ELO)), p.get('last_name','').lower(), p.get('first_name','').lower())
    )
    
    mappa_id_a_start_rank = {p['id']: i + 1 for i, p in enumerate(players_sorted_for_start_rank)}
    mappa_start_rank_a_id = {i + 1: p['id'] for i, p in enumerate(players_sorted_for_start_rank)}

    # 2. Generare la stringa TRF
    # Passiamo 'players_sorted_for_start_rank' perché l'ordine in cui i giocatori
    # appaiono nel TRF corrisponderà ai loro StartRank 1, 2, 3...
    trf_string = genera_stringa_trf_per_bbpairings(torneo, players_sorted_for_start_rank, mappa_id_a_start_rank)
    if not trf_string:
        print("ERRORE: Fallita generazione della stringa TRF per bbpPairings.")
        # Qui potresti implementare il fallback a pairing manuale se la generazione TRF fallisce
        # Per ora, ritorniamo None o una lista vuota per indicare fallimento.
        return handle_bbpairings_failure(torneo, round_number, "Fallimento generazione TRF")


    # 3. Eseguire bbpPairings.exe
    success, bbp_output_data, bbp_message = run_bbpairings_engine(trf_string)

    all_generated_matches = [] # Conterrà i dizionari partita finali

    if success:
        print("bbpPairings eseguito con successo.")
        # print(f"DEBUG bbp_output_data['coppie_raw']:\n{bbp_output_data['coppie_raw']}") # Debug
        
        # 4. Parsare l'output delle coppie
        parsed_pairing_list = parse_bbpairings_couples_output(bbp_output_data['coppie_raw'], mappa_start_rank_a_id)

        if parsed_pairing_list is None:
            print("ERRORE: Fallimento parsing output coppie di bbpPairings.")
            return handle_bbpairings_failure(torneo, round_number, f"Fallimento parsing output bbpPairings:\n{bbp_message}")
        
        # 5. Convertire in formato `all_matches` di tornello.py
        # e aggiornare lo stato dei giocatori
        
        # Controlla se il numero di giocatori da abbinare era dispari
        num_active_players_for_pairing = len(players_for_pairing_objects)
        player_with_bye_id = None

        if num_active_players_for_pairing % 2 != 0:
            # Identifica il giocatore con il BYE
            paired_ids_in_output = set()
            for match_info in parsed_pairing_list:
                if not match_info['is_bye']:
                    paired_ids_in_output.add(match_info['white_player_id'])
                    paired_ids_in_output.add(match_info['black_player_id'])
                else: # Se il bye è esplicito nell'output parsato
                    paired_ids_in_output.add(match_info['white_player_id'])


            active_player_ids = {p['id'] for p in players_for_pairing_objects}
            unpaired_ids = active_player_ids - paired_ids_in_output
            
            if len(unpaired_ids) == 1:
                player_with_bye_id = list(unpaired_ids)[0]
                # Verifica se il bye è già stato aggiunto da parse_bbpairings_couples_output
                bye_already_in_list = any(m['is_bye'] and m['white_player_id'] == player_with_bye_id for m in parsed_pairing_list)
                if not bye_already_in_list:
                     parsed_pairing_list.append({
                        'white_player_id': player_with_bye_id,
                        'black_player_id': None,
                        'result': "BYE",
                        'is_bye': True
                    })
                print(f"Info: Giocatore {player_with_bye_id} riceve il BYE (dedotto).")
            elif len(unpaired_ids) > 1:
                print(f"ERRORE: Imprevisto! {len(unpaired_ids)} giocatori spaiati con numero dispari di partecipanti.")
                return handle_bbpairings_failure(torneo, round_number, "Errore gestione bye")
            # Se len(unpaired_ids) == 0 ma ci aspettavamo un bye, parse_bbpairings_couples_output deve averlo già incluso.


        for i, match_info in enumerate(parsed_pairing_list):
            match_id = torneo.get("next_match_id", 1) + i
            current_match = {
                "id": match_id,
                "round": round_number,
                "white_player_id": match_info['white_player_id'],
                "black_player_id": match_info['black_player_id'], # Sarà None per il BYE
                "result": match_info.get('result'), # Sarà "BYE" o None
                # "original_p1_id": None, # Non più rilevante con bbpPairings
                # "original_p2_id": None,
            }
            all_generated_matches.append(current_match)

            # Aggiorna lo stato dei giocatori in torneo['players_dict']
            wp_id = current_match['white_player_id']
            bp_id = current_match['black_player_id']
            
            if wp_id and wp_id in torneo['players_dict']:
                player_w = torneo['players_dict'][wp_id]
                if not match_info.get('is_bye', False): # Partita normale
                    player_w['opponents'] = set(player_w.get('opponents', [])) # Assicura sia un set
                    player_w['opponents'].add(bp_id)
                    player_w['white_games'] = player_w.get('white_games', 0) + 1
                    player_w['last_color'] = 'white'
                    player_w['consecutive_white'] = player_w.get('consecutive_white', 0) + 1
                    player_w['consecutive_black'] = 0
                    # downfloat_count NON viene toccato qui, era per la logica interna
                else: # Gestione BYE per il giocatore
                    player_w['received_bye'] = True
                    player_w['points'] = float(player_w.get('points', 0.0)) + 1.0 # Assumiamo 1 punto per il bye
                    if "results_history" not in player_w: player_w["results_history"] = []
                    player_w["results_history"].append({
                        "round": round_number, "opponent_id": "BYE_PLAYER_ID", 
                        "color": None, "result": "BYE", "score": 1.0
                    })
            
            if bp_id and bp_id in torneo['players_dict']: # Se non è un BYE
                player_b = torneo['players_dict'][bp_id]
                player_b['opponents'] = set(player_b.get('opponents', [])) # Assicura sia un set
                player_b['opponents'].add(wp_id)
                player_b['black_games'] = player_b.get('black_games', 0) + 1
                player_b['last_color'] = 'black'
                player_b['consecutive_black'] = player_b.get('consecutive_black', 0) + 1
                player_b['consecutive_white'] = 0
        
        torneo["next_match_id"] = torneo.get("next_match_id", 1) + len(parsed_pairing_list)

    else: # bbpPairings.exe ha fallito
        returncode = bbp_output_data.get('returncode', -1) if bbp_output_data else -1
        # Se returncode è 1, significa "no valid pairing exists"
        if returncode == 1:
            print("ATTENZIONE: bbpPairings non ha trovato abbinamenti validi.")
            # Chiamiamo la funzione di fallback per l'input manuale
            return handle_bbpairings_failure(torneo, round_number, "bbpPairings: Nessun abbinamento valido trovato.", allow_manual_input=True)
        else:
            # Altri errori di bbpPairings
            print(f"ERRORE CRITICO da bbpPairings.exe: {bbp_message}")
            return handle_bbpairings_failure(torneo, round_number, f"Errore critico bbpPairings:\n{bbp_message}")

    # Sincronizzazione finale di torneo['players'] con players_dict (importante!)
    # Questa parte è cruciale e deve essere fatta con attenzione
    updated_players_list_for_torneo_struct = []
    # Manteniamo l'ordine originale dei giocatori se possibile, o usiamo l'ID per recuperare
    # Se players_sorted_for_start_rank contiene tutti i giocatori che erano in torneo['players']
    # possiamo usarlo come base per l'ordine, ma è più sicuro iterare gli ID originali.
    original_player_ids_order = [p['id'] for p in torneo.get('players', [])]
    
    for p_id_original in original_player_ids_order:
        if p_id_original in torneo['players_dict']: # Se il giocatore è ancora nel dizionario (non ritirato in modo strano)
            updated_players_list_for_torneo_struct.append(torneo['players_dict'][p_id_original])
        # else: il giocatore è stato rimosso, non dovrebbe accadere se gestiamo solo 'withdrawn'

    # Sostituisci solo se la nuova lista ha senso (es. stesso numero di giocatori non ritirati)
    # Questa logica di sincronizzazione va affinata per assicurare che 'torneo['players']'
    # rimanga la fonte di verità per l'ordine originale, ma con dati aggiornati.
    # Per ora, una semplice riscrittura basata su players_dict:
    torneo['players'] = list(torneo['players_dict'].values()) 
    # Sarebbe meglio:
    # new_player_list = []
    # for p_orig in torneo.get('players',[]): # Mantiene l'ordine originale
    #    if p_orig['id'] in torneo['players_dict']:
    #        new_player_list.append(torneo['players_dict'][p_orig['id']]) # Prende la versione aggiornata
    #    else: # Giocatore non più in dict (improbabile se non per bug)
    #        new_player_list.append(p_orig) # Mantiene il vecchio se non trovato
    # torneo['players'] = new_player_list

    print(f"--- Abbinamenti Turno {round_number} generati e stati aggiornati ---")
    return all_generated_matches

def handle_bbpairings_failure(torneo, round_number, error_message, allow_manual_input=False):
    """
    Gestisce i fallimenti di bbpPairings, opzionalmente attivando l'input manuale.
    """
    print(f"\n--- FALLIMENTO GENERAZIONE ABBINAMENTI AUTOMATICI (Turno {round_number}) ---")
    print(error_message)
    
    if allow_manual_input:
        print("Sarà necessario inserire gli abbinamenti e i colori manualmente.")
        # Qui dovresti implementare o chiamare la tua logica di input manuale.
        # Per ora, simulo che restituisca una lista vuota o None per indicare
        # che l'utente deve intervenire, e il flusso principale di tornello.py
        # potrebbe fermarsi o chiedere all'utente cosa fare.
        # Esempio: matches_manuali = richiedi_abbinamenti_manuali(torneo, round_number)
        # return matches_manuali
        print("Funzionalità di input manuale non ancora reimplementata in questo flusso.")
        print("Il torneo non può procedere automaticamente per questo turno.")
        return None # O una lista vuota per fermare il flusso di quel turno
    else:
        print("Il torneo non può procedere automaticamente per questo turno.")
        return None # O una lista vuota

def input_players(players_db):
    """
    Gestisce l'input dei giocatori per un torneo.
    1. Cerca per ID esatto nel DB.
    2. Se non è ID, cerca per Nome/Cognome parziale nel DB.
       - Se 1 match: aggiunge al torneo.
       - Se >1 match: mostra lista e richiede input più specifico.
    3. Se nessun match (né ID né ricerca), chiede Nome, Cognome, Elo separatamente.
       - Se Nome vuoto: torna al prompt iniziale.
       - Se Cognome o Elo vuoti/invalidi: usa default o segnala errore.
    4. Se input iniziale vuoto: termina inserimento (con check minimo giocatori).
    """
    players_in_tournament = []
    added_player_ids = set() # Tiene traccia degli ID già aggiunti a QUESTO torneo
    print("\n--- Inserimento Giocatori ---")
    print("Inserire ID esatto, oppure parte del Nome/Cognome per la ricerca.")
    print("Lasciare vuoto per terminare l'inserimento.")

    while True:
        current_num_players = len(players_in_tournament)
        data = input(f"\nGiocatore {current_num_players + 1} (ID o Ricerca Nome/Cognome, vuoto per terminare): ").strip()

        # --- Caso 4: Input Iniziale Vuoto -> Termina Inserimento ---
        if not data:
            min_players = 2 # Minimo per un torneo
            if current_num_players < min_players:
                print(f"\nAttenzione: Sono necessari almeno {min_players} giocatori per avviare il torneo.")
                continua = input("Ci sono meno di 2 giocatori. Continuare l'inserimento? (S/n): ").strip().lower()
                if continua == 'n':
                     print(f"\nInserimento terminato con {current_num_players} giocatori (insufficienti).")
                     # Ritorna la lista attuale, il chiamante deciderà se è valida
                     break
                else:
                     continue # Continua a chiedere giocatori (torna all'input data)
            else:
                # Numero sufficiente, termina
                print(f"\nInserimento terminato con {current_num_players} giocatori.")
                break # Esce dal ciclo while

        # Variabili per tenere traccia dello stato dell'iterazione
        player_id_to_add = None
        player_data_to_add = None # Conterrà i dati del giocatore trovato/creato

        # --- Tentativo 1: Check Esatto ID ---
        potential_id = data.upper()
        is_id_match = False
        if potential_id in players_db:
            print(f"Input riconosciuto come ID esatto: {potential_id}")
            is_id_match = True
            player_id_to_add = potential_id
            player_data_to_add = players_db[potential_id] # Dati presi direttamente dal DB

        # --- Tentativo 2: Ricerca Parziale (se non era ID) ---
        if not is_id_match:
            print(f"ID non trovato. Eseguo ricerca parziale per '{data}'...")
            search_lower = data.lower()
            matches = [] # Lista per contenere i DIZIONARI dei giocatori trovati
            for p_data_search in players_db.values():
                fname_lower = p_data_search.get('first_name', '').lower()
                lname_lower = p_data_search.get('last_name', '').lower()
                # Cerca la sotto-stringa nel nome O nel cognome
                if search_lower in fname_lower or search_lower in lname_lower:
                    matches.append(p_data_search)

            # --- Gestione Risultati Ricerca Parziale ---
            if len(matches) == 1:
                # Trovato risultato unico con ricerca parziale!
                player_data_to_add = matches[0]
                player_id_to_add = player_data_to_add['id']
                print(f"Trovato giocatore unico tramite ricerca: {player_data_to_add.get('first_name')} {player_data_to_add.get('last_name')} (ID: {player_id_to_add})")
                # Procedi all'aggiunta (verrà fatto dopo i tentativi)

            elif len(matches) > 1:
                # Trovati risultati multipli, mostra lista e richiedi input più specifico
                print(f"Trovati {len(matches)} giocatori contenenti '{data}'. Specifica usando l'ID esatto:")
                # Ordina i risultati per cognome, nome per una visualizzazione chiara
                matches.sort(key=lambda p: (p.get('last_name', '').lower(), p.get('first_name', '').lower()))
                for i, p_match in enumerate(matches, 1):
                    p_id = p_match.get('id', 'N/D')
                    p_fname = p_match.get('first_name', 'N/D')
                    p_lname = p_match.get('last_name', 'N/D')
                    p_elo = p_match.get('current_elo', 'N/D')
                    p_bdate = p_match.get('birth_date')
                    # Assumendo che format_date_locale sia definita correttamente altrove
                    try:
                         p_bdate_formatted = format_date_locale(p_bdate) if p_bdate else 'N/D'
                    except NameError: # Se format_date_locale non è definita in questo scope
                         p_bdate_formatted = p_bdate if p_bdate else 'N/D'

                    print(f"  {i}. ID: {p_id:<9} - {p_fname} {p_lname} (Elo DB: {p_elo}, Nato: {p_bdate_formatted})")
                # Non aggiungere nessuno ora, richiedi input più specifico nel prossimo ciclo
                continue # Salta il resto dell'iterazione corrente

            else: # len(matches) == 0 -> Nessun match (né ID né ricerca)
                # --- Tentativo 3: Input Manuale Separato ---
                print(f"Nessun giocatore trovato per '{data}'. Procedere con inserimento manuale:")
                first_name_manual = input("  Nome: ").strip()
                if not first_name_manual:
                     print("Inserimento manuale annullato (Nome vuoto).")
                     continue # Torna alla richiesta ID/Ricerca

                last_name_manual = input("  Cognome: ").strip()
                if not last_name_manual:
                     print("Errore: Cognome non può essere vuoto. Inserimento manuale annullato.")
                     continue # Torna alla richiesta ID/Ricerca

                elo_manual_input = input(f"  Elo (default {DEFAULT_ELO}): ").strip()
                elo_manual = DEFAULT_ELO
                if elo_manual_input:
                    try:
                        elo_manual = int(elo_manual_input)
                    except ValueError:
                        print(f"  Elo non valido '{elo_manual_input}'. Uso il default {DEFAULT_ELO}.")

                # Aggiungi/Aggiorna nel DB principale e ottieni l'ID
                # Assicurati che add_or_update_player_in_db riceva nomi separati
                player_id_from_db = add_or_update_player_in_db(players_db, first_name_manual, last_name_manual, elo_manual)

                if player_id_from_db is None:
                     print("Errore durante la gestione del giocatore nel DB. Riprova.")
                     continue # Torna alla richiesta ID/Ricerca
                else:
                     # Recupera i dati appena creati/trovati dal DB
                     player_data_to_add = players_db[player_id_from_db]
                     player_id_to_add = player_id_from_db
                     # L'Elo per il TORNEO sarà quello inserito manualmente ORA
                     initial_tournament_elo = elo_manual # Salva elo per dopo

        # --- Aggiunta Giocatore al Torneo (se trovato/creato e non duplicato) ---
        if player_id_to_add and player_data_to_add: # Se un ID e i dati sono stati determinati
             if player_id_to_add in added_player_ids:
                 print(f"Errore: Giocatore ID {player_id_to_add} ({player_data_to_add.get('first_name')} {player_data_to_add.get('last_name')}) è già stato aggiunto a questo torneo.")
             else:
                 # Prepara i dati finali specifici per il torneo
                 # Determina l'Elo iniziale corretto per il torneo
                 if is_id_match or len(matches) == 1: # Se aggiunto via ID o Ricerca Unica
                      try:
                           # Usa l'elo CORRENTE del DB
                           elo_torneo = int(player_data_to_add.get('current_elo', DEFAULT_ELO))
                      except (ValueError, TypeError):
                           print(f"Warning: Elo DB non valido per {player_id_to_add}. Uso {DEFAULT_ELO}.")
                           elo_torneo = DEFAULT_ELO
                 else: # Se aggiunto via Input Manuale (len(matches) == 0)
                      elo_torneo = initial_tournament_elo # Usa l'elo inserito manualmente

                 # Crea il dizionario per la lista players_in_tournament
                 player_data_for_tournament = {
                     "id": player_id_to_add,
                     "first_name": player_data_to_add.get('first_name', 'N/D'),
                     "last_name": player_data_to_add.get('last_name', 'N/D'),
                     "initial_elo": elo_torneo, # Elo all'inizio del torneo
                     "points": 0.0, "results_history": [], "opponents": set(),
                     "white_games": 0, "black_games": 0, "last_color": None,
                     "consecutive_white": 0, "consecutive_black": 0,
                     "received_bye": False, "buchholz": 0.0, "buchholz_cut1": None,
                     "performance_rating": None, "elo_change": None,
                     "k_factor": None, "games_this_tournament": 0,
                     "downfloat_count": 0,
                     "final_rank": None, "withdrawn": False
                 }
                 players_in_tournament.append(player_data_for_tournament)
                 added_player_ids.add(player_id_to_add)
                 print(f"-> Giocatore {player_data_for_tournament['first_name']} {player_data_for_tournament['last_name']} (Elo Torneo: {elo_torneo}) aggiunto al torneo.")
        # Se non è stato trovato/creato un ID valido (es. ricerca multipla o errore manuale),
        # non si entra in questo blocco e il ciclo while ricomincia chiedendo un nuovo input.
    return players_in_tournament

def update_match_result(torneo):
    """Chiede l'ID partita, aggiorna il risultato o gestisce 'cancella'.
       Include una richiesta di conferma prima di salvare il risultato.
       Restituisce True se un risultato è stato aggiornato o cancellato, False altrimenti."""
    current_round_num = torneo["current_round"]
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players',[])):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    players_dict = torneo['players_dict']
    
    current_round_data = None
    round_index = -1
    for i, r_data in enumerate(torneo.get("rounds", [])): # Rinomino r in r_data
        if r_data.get("round") == current_round_num:
            current_round_data = r_data
            round_index = i
            break
    
    if not current_round_data:
        print(f"ERRORE: Dati turno {current_round_num} non trovati per aggiornamento risultati.")
        return False

    while True: 
        pending_matches_this_round = []
        if "matches" in current_round_data:
            for m_pending in current_round_data["matches"]: # Rinomino m in m_pending
                if m_pending.get("result") is None and m_pending.get("black_player_id") is not None:
                    pending_matches_this_round.append(m_pending)
        
        if not pending_matches_this_round:
            # print("Info: Nessuna partita da registrare/cancellare per il turno corrente.") # Già rimosso
            return False 
        
        print(f"\nPartite del turno {current_round_num} ancora da registrare:")
        pending_matches_this_round.sort(key=lambda m_sort: m_sort.get('id', 0))
        for m_disp in pending_matches_this_round: # Rinomino m in m_disp
            white_p_obj = players_dict.get(m_disp.get('white_player_id')) # Rinomino white_p
            black_p_obj = players_dict.get(m_disp.get('black_player_id')) # Rinomino black_p
            if white_p_obj and black_p_obj:
                w_name_disp = f"{white_p_obj.get('first_name','?')} {white_p_obj.get('last_name','?')}"
                w_elo_disp = white_p_obj.get('initial_elo','?')
                b_name_disp = f"{black_p_obj.get('first_name','?')} {black_p_obj.get('last_name','?')}"
                b_elo_disp = black_p_obj.get('initial_elo','?')
                print(f"  ID: {m_disp.get('id','?'):<3} - {w_name_disp:<20} [{w_elo_disp:>4}] vs {b_name_disp:<20} [{b_elo_disp:>4}]")
            else:
                print(f"  ID: {m_disp.get('id','?'):<3} - Errore: Giocatore/i non trovato/i (W:{m_disp.get('white_player_id')}, B:{m_disp.get('black_player_id')}).")
        pending_ids_list = [str(m_id['id']) for m_id in pending_matches_this_round] # Rinomino pending_ids
        prompt_ids_str_val = "-".join(pending_ids_list) if pending_ids_list else "N/A" # Rinomino prompt_ids_str
        prompt_input_id = f"Inserisci ID partita da aggiornare, 'cancella' o lascia vuoto\n[{prompt_ids_str_val}]: "
        match_id_input_str = input(prompt_input_id).strip() # Rinomino match_id_str
        if not match_id_input_str:
            return False 
        if match_id_input_str.lower() == 'cancella':
            completed_matches_list = [] # Rinomino completed_matches
            if "matches" in current_round_data:
                for m_comp in current_round_data["matches"]: # Rinomino m in m_comp
                    if m_comp.get("result") is not None and m_comp.get("result") != "BYE":
                        completed_matches_list.append(m_comp)
            if not completed_matches_list:
                print("Nessuna partita completata in questo turno da poter cancellare.")
                continue
            print(f"\nPartite completate nel turno {current_round_num} (possibile cancellare risultato):")
            completed_matches_list.sort(key=lambda m_sort_comp: m_sort_comp.get('id', 0))
            completed_ids_list = [] # Rinomino completed_ids
            for m_disp_comp in completed_matches_list: # Rinomino m in m_disp_comp
                match_id_comp = m_disp_comp.get('id','?')
                completed_ids_list.append(str(match_id_comp))
                white_p_comp = players_dict.get(m_disp_comp.get('white_player_id'))
                black_p_comp = players_dict.get(m_disp_comp.get('black_player_id'))
                result_comp = m_disp_comp.get('result','?')
                if white_p_comp and black_p_comp:
                    w_name_comp = f"{white_p_comp.get('first_name','?')} {white_p_comp.get('last_name','?')}"
                    b_name_comp = f"{black_p_comp.get('first_name','?')} {black_p_comp.get('last_name','?')}"
                    print(f"  ID: {match_id_comp:<3} - {w_name_comp:<20} vs {b_name_comp:<20} = {result_comp}")
                else:
                    print(f"  ID: {match_id_comp:<3} - Errore giocatori = {result_comp} (W:{m_disp_comp.get('white_player_id')}, B:{m_disp_comp.get('black_player_id')})")
            cancel_prompt_ids_str = "-".join(completed_ids_list) if completed_ids_list else "N/A" # Rinomino cancel_prompt_ids
            cancel_prompt_msg = f"Inserisci ID partita da cancellare [{cancel_prompt_ids_str}] (o vuoto per annullare): " # Rinomino cancel_prompt
            cancel_id_input_str = input(cancel_prompt_msg).strip() # Rinomino cancel_id_str
            if not cancel_id_input_str:
                continue
            try:
                cancel_id_val = int(cancel_id_input_str) # Rinomino cancel_id
                match_to_cancel_obj = None # Rinomino match_to_cancel
                match_cancel_idx_val = -1 # Rinomino match_cancel_index
                if "matches" in current_round_data:
                    for i_cancel, m_cancel_search in enumerate(current_round_data["matches"]): # Rinomino i, m
                        if m_cancel_search.get('id') == cancel_id_val and m_cancel_search.get("result") is not None and m_cancel_search.get("result") != "BYE":
                            match_to_cancel_obj = m_cancel_search
                            match_cancel_idx_val = i_cancel
                            break
                if match_to_cancel_obj:
                    old_result_val = match_to_cancel_obj['result'] # Rinomino old_result
                    wp_id_cancel = match_to_cancel_obj['white_player_id'] # Rinomino white_p_id
                    bp_id_cancel = match_to_cancel_obj['black_player_id'] # Rinomino black_p_id
                    wp_cancel = players_dict.get(wp_id_cancel) # Rinomino white_p
                    bp_cancel = players_dict.get(bp_id_cancel) # Rinomino black_p
                    if not wp_cancel or not bp_cancel:
                        print(f"ERRORE: Giocatori non trovati per la partita {cancel_id_val} (W:{wp_id_cancel}, B:{bp_id_cancel}), cancellazione annullata.")
                        continue
                    w_score_revert = 0.0 # Rinomino white_score_revert
                    b_score_revert = 0.0 # Rinomino black_score_revert
                    if old_result_val == "1-0": w_score_revert = 1.0
                    elif old_result_val == "0-1": b_score_revert = 1.0
                    elif old_result_val == "1/2-1/2": w_score_revert, b_score_revert = 0.5, 0.5
                    wp_cancel["points"] = float(wp_cancel.get("points", 0.0)) - w_score_revert
                    bp_cancel["points"] = float(bp_cancel.get("points", 0.0)) - b_score_revert
                    hist_removed_w = False # Rinomino history_removed_w
                    if "results_history" in wp_cancel:
                        initial_len_w = len(wp_cancel["results_history"]) # Rinomino initial_len
                        wp_cancel["results_history"] = [
                            entry for entry in wp_cancel["results_history"]
                            if not (entry.get("round") == current_round_num and entry.get("opponent_id") == bp_id_cancel)
                        ]
                        hist_removed_w = (len(wp_cancel["results_history"]) < initial_len_w)
                    hist_removed_b = False # Rinomino history_removed_b
                    if "results_history" in bp_cancel:
                        initial_len_b = len(bp_cancel["results_history"]) # Rinomino initial_len
                        bp_cancel["results_history"] = [
                            entry for entry in bp_cancel["results_history"]
                            if not (entry.get("round") == current_round_num and entry.get("opponent_id") == wp_id_cancel)
                        ]
                        hist_removed_b = (len(bp_cancel["results_history"]) < initial_len_b)
                    torneo["rounds"][round_index]["matches"][match_cancel_idx_val]["result"] = None
                    print(f"Risultato ({old_result_val}) della partita ID {cancel_id_val} cancellato.")
                    if not hist_removed_w: print(f"Warning: Voce storico non trovata per {wp_id_cancel} vs {bp_id_cancel} durante cancellazione.")
                    if not hist_removed_b: print(f"Warning: Voce storico non trovata per {bp_id_cancel} vs {wp_id_cancel} durante cancellazione.")
                    save_tournament(torneo)
                    save_current_tournament_round_file(torneo)
                    torneo['players_dict'] = {p_upd['id']: p_upd for p_upd in torneo['players']} # Ricostruisci players_dict
                    return True 
                else:
                    print(f"ID {cancel_id_val} non corrisponde a una partita completata cancellabile in questo turno.")
            except ValueError:
                print("ID non valido per la cancellazione. Inserisci un numero intero.")
            continue 
        try:
            match_id_to_update_val = int(match_id_input_str) # Rinomino match_id_to_update
            match_to_update_obj = None # Rinomino match_to_update
            match_index_in_round_val = -1 # Rinomino match_index_in_round
            if "matches" in current_round_data:
                for i_search, m_search in enumerate(current_round_data["matches"]): # Rinomino i, m
                    if m_search.get('id') == match_id_to_update_val:
                        if m_search.get("result") is None and m_search.get("black_player_id") is not None:
                            match_to_update_obj = m_search
                            match_index_in_round_val = i_search
                            break
                        elif m_search.get("result") == "BYE":
                            print(f"Info: La partita {match_id_to_update_val} è un BYE, non registrabile.")
                            match_to_update_obj = None # Assicura che non si proceda
                            break 
                        else:
                            print(f"Info: La partita {match_id_to_update_val} ha già un risultato ({m_search.get('result','?')}). Usa 'cancella' per modificarlo.")
                            match_to_update_obj = None # Assicura che non si proceda
                            break 
            if match_to_update_obj:
                wp_id_upd = match_to_update_obj['white_player_id'] # Rinomino white_p_id
                bp_id_upd = match_to_update_obj['black_player_id'] # Rinomino black_p_id
                wp_upd = players_dict.get(wp_id_upd) # Rinomino white_p
                bp_upd = players_dict.get(bp_id_upd) # Rinomino black_p
                if not wp_upd or not bp_upd:
                    print(f"ERRORE CRITICO: Giocatore/i non trovato/i per la partita {match_id_to_update_val} (W:{wp_id_upd}, B:{bp_id_upd}). Impossibile registrare.")
                    continue 

                w_name_upd = f"{wp_upd.get('first_name','?')} {wp_upd.get('last_name','?')}" # Rinomino w_name
                b_name_upd = f"{bp_upd.get('first_name','?')} {bp_upd.get('last_name','?')}" # Rinomino b_name
                print(f"Partita selezionata: {w_name_upd} vs {b_name_upd}")
                
                prompt_result_input = "Risultato [1-0, 0-1, 1/2, 0-0F, 1-F, F-1]: " # Rinomino prompt_risultato
                result_input_str = input(prompt_result_input).strip() # Rinomino result_input

                parsed_new_result = None # Rinomino new_result
                parsed_white_score = 0.0 # Rinomino white_score
                parsed_black_score = 0.0 # Rinomino black_score
                is_valid_input_result = True # Rinomino valid_input

                if result_input_str == '1-0':
                    parsed_new_result = "1-0"
                    parsed_white_score = 1.0
                elif result_input_str == '0-1':
                    parsed_new_result = "0-1"
                    parsed_black_score = 1.0
                elif result_input_str == '1/2':
                    parsed_new_result = "1/2-1/2"
                    parsed_white_score = 0.5
                    parsed_black_score = 0.5
                elif result_input_str == '0-0F':
                    parsed_new_result = "0-0F"
                    print("Partita marcata come non giocata/annullata (0-0F).")
                elif result_input_str == '1-F':
                    parsed_new_result = "1-F"
                    parsed_white_score = 1.0
                    print("Partita registrata come vittoria del Bianco per Forfait (1-F).")
                elif result_input_str == 'F-1':
                    parsed_new_result = "F-1"
                    parsed_black_score = 1.0
                    print("Partita registrata come vittoria del Nero per Forfait (F-1).")
                else:
                    is_valid_input_result = False

                if is_valid_input_result and parsed_new_result is not None:
                    # --- INIZIO BLOCCO DI CONFERMA ---
                    confirm_message_str = "ERRORE INTERNO MESSAGGIO CONFERMA" 
                    if parsed_new_result == "1-0":
                        confirm_message_str = f"Confermi che {w_name_upd} vince contro {b_name_upd}? (s/n): "
                    elif parsed_new_result == "0-1":
                        confirm_message_str = f"Confermi che {b_name_upd} vince contro {w_name_upd}? (s/n): "
                    elif parsed_new_result == "1/2-1/2":
                        confirm_message_str = f"Confermi che {w_name_upd} e {b_name_upd} pattano? (s/n): "
                    elif parsed_new_result == "0-0F":
                        confirm_message_str = f"Confermi partita nulla/annullata (0-0F) tra {w_name_upd} e {b_name_upd}? (s/n): "
                    elif parsed_new_result == "1-F":
                        confirm_message_str = f"Confermi vittoria a tavolino per {w_name_upd} (forfait di {b_name_upd})? (s/n): "
                    elif parsed_new_result == "F-1":
                        confirm_message_str = f"Confermi vittoria a tavolino per {b_name_upd} (forfait di {w_name_upd})? (s/n): "
                    
                    user_confirmation = input(confirm_message_str).strip().lower()

                    if user_confirmation == 's':
                        # L'UTENTE HA CONFERMATO - Procedi con l'aggiornamento
                        wp_upd["points"] = float(wp_upd.get("points", 0.0)) + parsed_white_score
                        bp_upd["points"] = float(bp_upd.get("points", 0.0)) + parsed_black_score
                        
                        if "results_history" not in wp_upd: wp_upd["results_history"] = []
                        if "results_history" not in bp_upd: bp_upd["results_history"] = []
                        
                        wp_upd["results_history"].append({
                            "round": current_round_num, "opponent_id": bp_upd["id"],
                            "color": "white", "result": parsed_new_result, "score": parsed_white_score
                        })
                        bp_upd["results_history"].append({
                            "round": current_round_num, "opponent_id": wp_upd["id"],
                            "color": "black", "result": parsed_new_result, "score": parsed_black_score
                        })
                        
                        torneo["rounds"][round_index]["matches"][match_index_in_round_val]["result"] = parsed_new_result
                        print("Risultato registrato.")
                        
                        save_tournament(torneo)
                        save_current_tournament_round_file(torneo)
                        torneo['players_dict'] = {p_final_upd['id']: p_final_upd for p_final_upd in torneo['players']} # Ricostruisci
                        return True # Un risultato è stato effettivamente aggiornato
                    else:
                        print("Operazione annullata dall'utente. Nessun risultato registrato per questa partita.")
                        # Si tornerà al prompt ID partita nel prossimo ciclo del while esterno.
                
                elif not is_valid_input_result: # Se l'input iniziale del risultato non era valido
                    print("Input risultato non valido. Usa 1-0, 0-1, 1/2, 0-0F, 1-F, F-1.")
                # Se parsed_new_result è None o l'utente non ha confermato, si continua al prossimo ciclo while.

            elif match_index_in_round_val == -1 and match_id_input_str.lower() != 'cancella': 
                print("ID partita non valido per questo turno o risultato già presente. Riprova.")
        
        except ValueError:
            if match_id_input_str.lower() != 'cancella': # Evita doppio messaggio se era 'cancella' ma non un ID valido
                print("ID non valido. Inserisci un numero intero o 'cancella'.")
        # Il loop while True continua qui, mostrando di nuovo le partite pendenti

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
    Usa i dati già calcolati (come elo_change) presenti nel dizionario 'p'.
    """
    players = torneo.get("players", [])
    if not players:
        print("Warning: Nessun giocatore per generare classifica.")
        return
    # Assicura dizionario aggiornato (anche se dovrebbe esserlo da finalize)
    if 'players_dict' not in torneo or len(torneo['players_dict']) != len(players):
        torneo['players_dict'] = {p['id']: p for p in torneo.get('players', [])}
    # players_dict = torneo['players_dict'] # Non più strettamente necessario qui se i dati sono in players

    # --- CALCOLO SPAREGGI (BUCHHOLZ) E ORDINAMENTO ---
    # Buchholz va calcolato qui perché serve sempre, anche per l'ordinamento parziale
    print("Calcolo/Aggiornamento Buchholz per classifica...")
    for p in players:
        p_id = p.get('id')
        if not p_id: continue
        if not p.get("withdrawn", False):
            p["buchholz"] = compute_buchholz(p_id, torneo)
            # Calcola B-1 solo se finale E se non già presente (calcolato da finalize)
            if final and "buchholz_cut1" not in p:
                 p["buchholz_cut1"] = compute_buchholz_cut1(p_id, torneo)
            elif not final:
                 p["buchholz_cut1"] = None # Assicura sia None in parziale
        else:
            p["buchholz"] = 0.0
            p["buchholz_cut1"] = None

    # --- RIMOZIONE CALCOLI FINALI RIDONDANTI ---
    # Performance, Elo Change, ARO sono ora calcolati SOLO in finalize_tournament
    # e i risultati sono già presenti nei dizionari 'p' dentro la lista 'players'
    # quando questa funzione viene chiamata con final=True.
    # Non serve ricalcolarli qui.

    # --- ORDINAMENTO E ASSEGNAZIONE RANK (Logica invariata) ---
    # La chiave di sort userà i valori già presenti in 'p'
    def sort_key(player):
        # ... (stessa chiave di ordinamento di prima, usa i campi esistenti in player) ...
        if player.get("withdrawn", False):
            return (0, -float('inf'), -float('inf'), -float('inf'), -float('inf'))
        points = player.get("points", 0.0)
        # Usa i valori esistenti, gestendo None per parziali o errori
        bucch_c1 = player.get("buchholz_cut1", 0.0) if final and player.get("buchholz_cut1") is not None else 0.0
        bucch_tot = player.get("buchholz", 0.0)
        performance = player.get("performance_rating", 0) if final and player.get("performance_rating") is not None else -1
        elo_initial = player.get("initial_elo", 0)
        return (1, -points, -bucch_c1, -bucch_tot, -performance, -elo_initial)

    try:
        # Usa la lista 'players' che potrebbe essere già ordinata da finalize_tournament
        # Ma riordiniamo qui per sicurezza e per le classifiche parziali
        players_sorted = sorted(players, key=sort_key)
    except Exception as e:
        print(f"Errore durante l'ordinamento dei giocatori per la classifica: {e}")
        # Importa traceback se non già fatto globalmente
        # import traceback
        traceback.print_exc()
        players_sorted = players # Usa lista non ordinata in caso di errore

    # Assegna rank solo se finale E se non già presente (fatto da finalize)
    # Se chiamato per classifica parziale, assegna rank temporaneo per la stampa
    if final and players_sorted and "final_rank" not in players_sorted[0]:
        # Assegna rank finale se finalize non l'ha fatto (non dovrebbe succedere)
        print("WARN save_standings_text: Assegno final_rank qui, ma dovrebbe essere fatto da finalize_tournament.") # DEBUG
        current_rank = 0
        last_sort_key_values = None
        for i, p in enumerate(players_sorted):
             if not p.get("withdrawn", False):
                 current_sort_key_values = sort_key(p)[1:]
                 if current_sort_key_values != last_sort_key_values:
                     current_rank = i + 1
                 p["final_rank"] = current_rank
                 last_sort_key_values = current_sort_key_values
             else:
                 p["final_rank"] = "RIT"

    # --- NOME FILE E SCRITTURA (Logica nome file e titolo invariata) ---
    tournament_name = torneo.get('name', 'Torneo_Senza_Nome')
    sanitized_name = sanitize_filename(tournament_name)
    filename = f"tornello - {sanitized_name} - Classifica.txt"
    status_line = ""
    if final:
        status_line = "CLASSIFICA FINALE"
    else:
        # ... (logica per titolo classifica parziale invariata) ...
        has_any_results = any(entry for p in players for entry in p.get("results_history", []) if entry.get("result") is not None and entry.get("result") != "BYE")
        current_round_in_state = torneo.get("current_round", 0)
        if not has_any_results and current_round_in_state == 1:
            round_num_for_title = 0
            status_line = f"Classifica Iniziale (Prima del Turno 1)"
        else:
            round_num_for_title = current_round_in_state
            status_line = f"Classifica Parziale - Dopo Turno {round_num_for_title}"

    try:
        with open(filename, "w", encoding='utf-8-sig') as f:
            f.write(f"Nome torneo: {torneo.get('name', 'N/D')}\n")
            f.write(status_line + "\n")
            header = "Pos. Nome Cognome         [EloIni] Punti  Bucch-1 Bucch  "
            if final:
                header += " ARO  Perf  +/-Elo"
            f.write(header + "\n")
            f.write("-" * len(header) + "\n")

            # --- SCRITTURA DATI GIOCATORI (Usa i valori già presenti in 'p') ---
            for i, player in enumerate(players_sorted):
                 # Determina il rank da visualizzare
                rank_to_display = player.get("final_rank") if final and player.get("final_rank") is not None else (i + 1)
                rank_str = str(rank_to_display)

                name_str = f"{player.get('first_name','?')} {player.get('last_name','')}"
                elo_str = f"[{player.get('initial_elo','?'):>4}]"
                pts_str = format_points(player.get('points', 0.0))
                bucch_tot_str = format_points(player.get('buchholz', 0.0)) # Buchholz sempre calcolato
                bucch_c1_val = player.get('buchholz_cut1') # Può essere None
                bucch_c1_str = format_points(bucch_c1_val) if bucch_c1_val is not None else "---"

                max_name_len = 21
                if len(name_str) > max_name_len: name_str = name_str[:max_name_len-1] + "."

                line = f"{rank_str:<4} {name_str:<{max_name_len}} {elo_str:<8} {pts_str:<6} {bucch_c1_str:<7} {bucch_tot_str:<7}"

                if final:
                    # Recupera i valori CALCOLATI DA FINALIZE_TOURNAMENT
                    aro_val = player.get('aro')
                    perf_val = player.get('performance_rating')
                    elo_change_val = player.get('elo_change') # <<< USA QUESTO

                    if player.get("withdrawn", False):
                        aro_str, perf_str, elo_change_str = "---", "---", "---"
                    else:
                        aro_str = str(aro_val) if aro_val is not None else "N/A"
                        perf_str = str(perf_val) if perf_val is not None else "N/A"
                        elo_change_str = f"{elo_change_val:+}" if elo_change_val is not None else "N/A" # Format con segno +/-

                    line += f" {aro_str:<4} {perf_str:<6} {elo_change_str:<6}"
                f.write(line + "\n")

        print(f"File classifica {filename} salvato/sovrascritto.")
    # ... (except blocks invariati) ...
    except IOError as e:
        print(f"Errore durante il salvataggio del file classifica {filename}: {e}")
    except Exception as general_e:
        print(f"Errore inatteso durante save_standings_text: {general_e}")
        # import traceback # Assicurati sia importato globalmente
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
            print(f"DEBUG finalize: K-Factor per {player_id}: {p['k_factor']}") # DEBUG

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
        print(f"DEBUG finalize: Partite giocate da {player_id} nel torneo: {games_count}") # DEBUG


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
    print(f"\nBenvenuti da Tornello {VERSIONE} - {launch_count}o lancio.\n\tGabriele Battaglia and Gemini 2.5 Pro.") # Rimosso 2.5
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
        # Calcola date turni
        round_dates = calculate_dates(torneo["start_date"], torneo["end_date"], torneo["total_rounds"])
        if round_dates is None:
            # Indentazione corretta
            print("Errore fatale nel calcolo delle date dei turni. Impossibile creare il torneo.")
            sys.exit(1)
        torneo["round_dates"] = round_dates
        # Input giocatori
        torneo["players"] = input_players(players_db)
        if not torneo["players"] or len(torneo["players"]) < 2:
            print("Numero insufficiente di giocatori validi inseriti. Torneo annullato.")
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
            torneo["rounds"].append(round_entry) # <<< RIGA REINSERITA

            # --- DEBUG SUGGERITO PRIMA (ora utile per conferma) ---
            print(f"DEBUG main: Appended round data. torneo['rounds'] ora contiene:") # DEBUG
            # Importa pprint all'inizio del file se non l'hai già fatto
            import pprint
            pprint.pprint(torneo.get('rounds', 'ERRORE: CHIAVE rounds MANCANTE O NON LISTA'))
            # --- FINE DEBUG AGGIUNTO ---

        except Exception as e_append:
             print(f"ERRORE durante l'append di round data: {e_append}") # DEBUG
             # Importa traceback all'inizio del file se non l'hai già fatto
             import traceback
             traceback.print_exc()
             sys.exit(1) # Esci se l'append fallisce
        # --- FINE SEZIONE REINSERITA/MODIFICATA ---


        # Salva stato iniziale torneo e file T1
        save_tournament(torneo) # Ora salva con il round 1 dentro
        save_current_tournament_round_file(torneo)
        save_standings_text(torneo, final=False) # Salva classifica iniziale T0
        print("\nTorneo creato e Turno 1 generato.")
    else:
        # Torneo esistente caricato
        print(f"Torneo '{torneo.get('name','N/D')}' in corso rilevato da {TOURNAMENT_FILE}.")
        # Assicura che i set e il dizionario siano ricreati/validi dopo il caricamento
        if 'players' not in torneo: torneo['players'] = []
        for p in torneo["players"]:
            p['opponents'] = set(p.get('opponents', [])) # Ricostruisci set
            # Assicura presenza campi colore per compatibilità
            p.setdefault('consecutive_white', 0)
            p.setdefault('consecutive_black', 0)
        if 'players_dict' not in torneo or len(torneo['players_dict']) != len(torneo.get('players', [])):
            # Indentazione corretta
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
                # Indentazione corretta
                if r.get("round") == current_round_num:
                    current_round_data = r
                    round_index = i
                    break
            if current_round_data is None:
                # Indentazione corretta
                print(f"ERRORE CRITICO: Dati per il turno corrente {current_round_num} non trovati nella struttura del torneo!")
                break # Interrompi esecuzione
            # Verifica se il turno corrente è completo
            round_completed = True
            if "matches" in current_round_data:
                # Indentazione corretta
                for m in current_round_data["matches"]:
                    if m.get("result") is None and m.get("black_player_id") is not None:
                        # Indentazione corretta
                        round_completed = False
                        break # Basta una partita pendente
            else:
                # Indentazione corretta
                print(f"Warning: Nessuna partita trovata per il turno {current_round_num}.")
                round_completed = False # Considera incompleto

            # --- Flusso: Registra Risultati o Avanza Turno ---
            if not round_completed:
                print("\nIl turno non è completo. Registrare i risultati mancanti.")
                action_made = update_match_result(torneo)
                if not action_made:
                    # Indentazione corretta
                    print("\nNessun risultato inserito o cancellato in questa sessione.")
                    print("Salvataggio dello stato attuale del torneo...")
                    save_tournament(torneo)
                    print("Rilanciare il programma per continuare la registrazione o avanzare turno.")
                    break # Esce dal main loop
                else:
                    # Indentazione corretta
                    # Azione fatta, il loop while(True) continuerà, rivalutando lo stato
                    continue
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
                        # Indentazione corretta
                        print(f"\nERRORE CRITICO durante la generazione del turno {next_round_num}: {e}")
                        print("Il torneo potrebbe essere in uno stato inconsistente.")
                        traceback.print_exc()
                        # Prova a salvare lo stato attuale
                        torneo["current_round"] = current_round_num # Ripristina per sicurezza
                        save_tournament(torneo)
                        break # Interrompi torneo
    except KeyboardInterrupt:
        # Indentazione corretta
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
