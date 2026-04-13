import os
import subprocess
import traceback
from datetime import datetime
from config import *
from GBUtils import key


def handle_bbpairings_failure(torneo, round_number, error_message):
    """
    Gestisce i fallimenti di bbpPairings. Stampa un messaggio e chiede all'utente cosa fare.
    Restituisce una stringa che indica l'azione scelta dall'utente ('time_machine' o 'terminate').
    """
    print(
        _(
            "\n--- FALLIMENTO GENERAZIONE ABBINAMENTI AUTOMATICI (Turno {round_num}) ---"
        ).format(round_num=round_number)
    )
    print(error_message)
    print(_("Causa: bbpPairings.exe non è riuscito a generare gli abbinamenti."))
    print(
        _(
            "Azione richiesta: Verificare il file 'input_bbp.trf' nella sottocartella 'bbppairings' per possibili errori di formato."
        )
    )
    print(
        _(
            "Oppure, un risultato potrebbe essere stato inserito in modo errato nel turno precedente."
        )
    )

    while True:
        prompt = _(
            "\nCosa vuoi fare? (T)orna indietro con la Time Machine per correggere, (U)sci dal programma: "
        ).format(round_num=round_number)
        choice = key(prompt).strip().lower()
        if choice == "t":
            return "time_machine"
        elif choice == "u":
            return "terminate"
        else:
            print(_("Scelta non valida. Inserisci 't' o 'u'."))


def genera_stringa_trf_per_bbpairings(
    dati_torneo, lista_giocatori_attivi, mappa_id_a_start_rank
):
    """
    Genera la stringa di testo in formato TRF(bx) per bbpairings.
    Per il Round 1: righe giocatore SENZA blocchi dati partita (si affida a XXC white1).
    Per i Round > 1: righe giocatore CON storico risultati dei turni precedenti.
    """
    trf_lines = []
    try:
        valore_bye_torneo = dati_torneo.get("bye_value", 1.0)
        total_rounds_val = int(dati_torneo.get("total_rounds", 0))
        number_of_players_val = len(lista_giocatori_attivi)
        current_round_being_paired = int(dati_torneo.get("current_round", 1))
        start_date_strf = dati_torneo.get("start_date", "01/01/1900")
        end_date_strf = dati_torneo.get("end_date", "01/01/1900")
        if (
            "/" not in start_date_strf
            and len(start_date_strf) == 10
            and "-" in start_date_strf
        ):
            try:
                start_date_obj = datetime.strptime(start_date_strf, "%Y-%m-%d")
                start_date_strf = start_date_obj.strftime("%d/%m/%Y")
            except ValueError:
                start_date_strf = "01/01/1900"
        if (
            "/" not in end_date_strf
            and len(end_date_strf) == 10
            and "-" in end_date_strf
        ):
            try:
                end_date_obj = datetime.strptime(end_date_strf, "%Y-%m-%d")
                end_date_strf = end_date_obj.strftime("%d/%m/%Y")
            except ValueError:
                end_date_strf = "01/01/1900"
        # Intestazione (Header)
        trf_lines.append(
            f"012 {str(dati_torneo.get('name', _('Torneo Sconosciuto')))[:45]:<45}\n"
        )
        trf_lines.append(
            f"022 {str(dati_torneo.get('site', _('Luogo Sconosciuto')))[:45]:<45}\n"
        )  # Usa 'site'
        trf_lines.append(
            f"032 {str(dati_torneo.get('federation_code', 'ITA'))[:3]:<3}\n"
        )  # Usa 'federation_code'
        trf_lines.append(f"042 {start_date_strf}\n")  # Già usa 'start_date'
        trf_lines.append(f"052 {end_date_strf}\n")  # Già usa 'end_date'
        trf_lines.append(f"062 {number_of_players_val:03d}\n")  # Già calcolato
        trf_lines.append(f"072 {number_of_players_val:03d}\n")  # Già calcolato
        trf_lines.append("082 000\n")
        trf_lines.append(
            "092 Individual: Swiss-System\n"
        )  # Potrebbe diventare configurabile
        trf_lines.append(
            f"102 {str(dati_torneo.get('chief_arbiter', _('Arbitro Capo')))[:45]:<45}\n"
        )  # Usa 'chief_arbiter'
        deputy_str = str(dati_torneo.get("deputy_chief_arbiters", "")).strip()
        if not deputy_str:
            deputy_str = (
                " "  # TRF vuole almeno uno spazio se la riga 112 è presente ma vuota
            )
        trf_lines.append(f"112 {deputy_str[:45]:<45}\n")
        trf_lines.append(
            f"122 {str(dati_torneo.get('time_control', 'Standard'))[:45]:<45}\n"
        )  # Usa 'time_control'
        trf_lines.append(f"XXR {total_rounds_val:03d}\n")  # Già usa 'total_rounds'
        initial_color_setting = str(
            dati_torneo.get("initial_board1_color_setting", "white1")
        ).lower()
        trf_lines.append(f"XXC {initial_color_setting}\n")
        valore_bye_formattato = f"{valore_bye_torneo:.1f}"
        trf_lines.append(f"BBU {valore_bye_formattato:>4}\n")

        def write_to_char_list_local(target_list, start_col_1based, text_to_write):
            start_idx_0based = start_col_1based - 1
            source_chars = list(str(text_to_write))
            max_len_to_write = len(source_chars)
            # Evita di scrivere oltre la lunghezza della target_list se text_to_write è troppo lungo
            # per la posizione data, anche se p_line_chars è grande.
            if start_idx_0based + max_len_to_write > len(target_list):
                max_len_to_write = len(target_list) - start_idx_0based

            for i in range(max_len_to_write):
                if start_idx_0based + i < len(
                    target_list
                ):  # Doppio controllo per sicurezza
                    target_list[start_idx_0based + i] = source_chars[i]

        giocatori_ordinati_per_start_rank = sorted(
            lista_giocatori_attivi, key=lambda p: mappa_id_a_start_rank[p["id"]]
        )

        for player_data in giocatori_ordinati_per_start_rank:
            # Lunghezza base fino a col 89 (Rank) + spazio per molti turni di storico
            p_line_chars = [" "] * (
                89 + (total_rounds_val * 10) + 5
            )  # 89 + storico + buffer
            start_rank = mappa_id_a_start_rank[player_data["id"]]
            raw_last_name = player_data.get("last_name", _("Cognome"))
            raw_first_name = player_data.get("first_name", _("Nome"))
            nome_completo = f"{raw_last_name}, {raw_first_name}"
            elo = int(player_data.get("initial_elo", 1399))
            federazione_giocatore = str(player_data.get("federation", "ITA")).upper()[
                :3
            ]
            # Usa i campi specifici dal tuo player_data. Questi sono esempi.
            fide_id_from_playerdata = str(
                player_data.get("fide_id_num_str", "0")
            )  # Usa la chiave corretta
            birth_date_from_playerdata = str(
                player_data.get("birth_date", "1900-01-01")
            )  # Usa la chiave corretta
            title_from_playerdata = (
                str(player_data.get("fide_title", "")).strip().upper()
            )  # Usa la chiave corretta
            # Scrittura campi anagrafici
            write_to_char_list_local(p_line_chars, 1, "001")
            write_to_char_list_local(p_line_chars, 5, f"{start_rank:>4}")
            write_to_char_list_local(p_line_chars, 10, player_data.get("sex", "m"))
            write_to_char_list_local(
                p_line_chars, 11, f"{title_from_playerdata:>3}"[:3]
            )
            write_to_char_list_local(p_line_chars, 15, f"{nome_completo:<33}"[:33])
            write_to_char_list_local(p_line_chars, 49, f"{elo:<4}")
            write_to_char_list_local(
                p_line_chars, 54, f"{federazione_giocatore:<3}"[:3]
            )
            fide_id_core_num_fmt = f"{fide_id_from_playerdata:>9}"[
                :9
            ]  # Allinea a dx su 9 char
            fide_id_final_field = f"{fide_id_core_num_fmt}  "[
                :11
            ]  # Aggiungi 2 spazi, assicurati 11 char
            write_to_char_list_local(p_line_chars, 58, fide_id_final_field)
            birth_date_for_trf = "          "  # Default 10 spazi
            if birth_date_from_playerdata:  # Se non è None o stringa vuota
                try:
                    # Prova a convertire da YYYY-MM-DD a YYYY/MM/DD
                    dt_obj = datetime.strptime(
                        birth_date_from_playerdata, DATE_FORMAT_ISO
                    )  # DATE_FORMAT_DB è %Y-%m-%d
                    birth_date_for_trf = dt_obj.strftime(
                        "%Y/%m/%d"
                    )  # Formato TRF standard
                except ValueError:
                    # Se non è nel formato YYYY-MM-DD, usa il valore grezzo se è lungo 10, altrimenti placeholder
                    if len(str(birth_date_from_playerdata)) == 10:
                        birth_date_for_trf = str(birth_date_from_playerdata)
                    else:  # Fallback a stringa di spazi se il formato non è gestibile
                        birth_date_for_trf = "          "
            write_to_char_list_local(
                p_line_chars, 70, f"{birth_date_for_trf:<10}"[:10]
            )  # Assicura 10 caratteri
            punti_reali = float(player_data.get("points", 0.0))
            write_to_char_list_local(p_line_chars, 81, f"{punti_reali:4.1f}")
            write_to_char_list_local(
                p_line_chars, 86, f"{start_rank:>4}"
            )  # Campo Rank (col 86-89)
            colonna_inizio_blocco_partita = 92

            history_sorted = sorted(
                player_data.get("results_history", []), key=lambda x: x.get("round", 0)
            )
            if current_round_being_paired > 1:
                for res_entry in history_sorted:
                    round_of_this_entry = int(res_entry.get("round", 0))

                    if (
                        round_of_this_entry > 0
                        and round_of_this_entry < current_round_being_paired
                    ):
                        opp_id_tornello = res_entry.get("opponent_id")
                        player_color_this_game = str(res_entry.get("color", "")).lower()

                        color_char_trf = "-"
                        if player_color_this_game == "white":
                            color_char_trf = "w"
                        elif player_color_this_game == "black":
                            color_char_trf = "b"

                        tornello_result_str = str(res_entry.get("result", "")).upper()
                        float(res_entry.get("score", 0.0))
                        result_code_trf = "?"
                        opp_start_rank_str = "0000"
                        if (
                            opp_id_tornello == "BYE_PLAYER_ID"
                            or tornello_result_str == "BYE"
                        ):
                            color_char_trf = "-"
                            result_code_trf = "U"
                        elif opp_id_tornello:
                            opponent_start_rank = mappa_id_a_start_rank.get(
                                opp_id_tornello
                            )
                            if opponent_start_rank is None:
                                print(
                                    _(
                                        "AVVISO CRITICO: ID avversario storico {opponent_id} non trovato in mappa per giocatore {player_id} al turno {round_num}"
                                    ).format(
                                        opponent_id=opp_id_tornello,
                                        player_id=player_data["id"],
                                        round_num=round_of_this_entry,
                                    )
                                )
                                opp_start_rank_str = "XXXX"
                            else:
                                opp_start_rank_str = f"{opponent_start_rank:>4}"
                            is_white = player_color_this_game == "white"
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
                        else:
                            continue

                        if result_code_trf == "?":
                            continue

                        game_block = f"{opp_start_rank_str} {color_char_trf} {result_code_trf}  "[
                            :10
                        ]
                        write_to_char_list_local(
                            p_line_chars, colonna_inizio_blocco_partita, game_block
                        )
                        colonna_inizio_blocco_partita += 10

            # Per il Round 1: NON aggiungiamo il blocco "0000 w   " se XXC white1 è presente.
            # Le righe giocatore per il R1 finiranno dopo il campo Rank (col 89) o gli spazi successivi.
            # rstrip() si occuperà di rimuovere gli spazi finali inutilizzati da p_line_chars.
            # Se il giocatore è ritirato, aggiungi un risultato "Sconfitta a 0 punti" (Z)
            # per il turno corrente. Questo dice a bbpPairings di non abbinarlo.
            if dati_torneo["players_dict"][player_data["id"]].get("withdrawn", False):
                # L'avversario è 0000 (nessuno), il colore è '-' (non applicabile).
                game_block_forfeit = f"{'0000':>4} {'-':<1} {'Z':<1}   "[:10]
                # Scriviamo questo blocco nella prima colonna disponibile per lo storico
                write_to_char_list_local(
                    p_line_chars, colonna_inizio_blocco_partita, game_block_forfeit
                )
            final_line = "".join(p_line_chars).rstrip()
            trf_lines.append(final_line + "\n")
        return "".join(trf_lines)
    except Exception as e:
        print(
            _(
                "Errore catastrofico in genera_stringa_trf_per_bbpairings: {error}"
            ).format(error=e)
        )
        traceback.print_exc()
        return None


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
            print(
                _(
                    "Info: Creata sottocartella '{subdir}' per i file di bbpPairings."
                ).format(subdir=BBP_SUBDIR)
            )
        except OSError as e:
            return (
                False,
                None,
                _("Errore creazione sottocartella '{subdir}': {error}").format(
                    subdir=BBP_SUBDIR, error=e
                ),
            )
    try:
        with open(BBP_INPUT_TRF, "w", encoding="utf-8") as f:
            f.write(trf_content_string)
    except IOError as e:
        return (
            False,
            None,
            _("Errore scrittura file TRF di input '{filepath}': {error}").format(
                filepath=BBP_INPUT_TRF, error=e
            ),
        )
    command = [
        BBP_EXE_PATH,
        "--dutch",
        BBP_INPUT_TRF,
        "-p",
        BBP_OUTPUT_COUPLES,
        "-l",
        BBP_OUTPUT_CHECKLIST,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            error_message = _("bbpPairings.exe ha fallito con codice {}.\n").format(
                result.returncode
            )
            error_message += _("Stderr:\n{}\n").format(result.stderr)
            error_message += _("Stdout:\n{}").format(result.stdout)
            # Se codice è 1 (no pairing), lo gestiremo specificamente più avanti
            return (
                False,
                {
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
                error_message,
            )
        # Lettura file di output se successo
        coppie_content = ""
        if os.path.exists(BBP_OUTPUT_COUPLES):
            with open(BBP_OUTPUT_COUPLES, "r", encoding="utf-8") as f:
                coppie_content = f.read()
        else:
            return (
                False,
                None,
                _("File output coppie '{filepath}' non trovato.").format(
                    filepath=BBP_OUTPUT_COUPLES
                ),
            )

        checklist_content = ""
        if os.path.exists(BBP_OUTPUT_CHECKLIST):
            with open(BBP_OUTPUT_CHECKLIST, "r", encoding="utf-8") as f:
                checklist_content = f.read()
        # Non consideriamo un errore se il checklist non c'è, ma logghiamo

        return (
            True,
            {
                "coppie_raw": coppie_content,
                "checklist_raw": checklist_content,
                "stdout": result.stdout,
            },
            _("Esecuzione bbpPairings completata."),
        )

    except FileNotFoundError:
        return (
            False,
            None,
            _(
                "Errore: Eseguibile '{filepath}' non trovato. Assicurati sia nel percorso corretto."
            ).format(filepath=BBP_EXE_PATH),
        )
    except Exception as e:
        return (
            False,
            None,
            _(
                "Errore imprevisto durante esecuzione bbpPairings: {error}\n{traceback}"
            ).format(error=e, traceback=traceback.format_exc()),
        )


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
        return None  # O lista vuota, da decidere
    try:
        pair_lines = lines[1:]  # Le righe effettive degli abbinamenti
        for line_num, line in enumerate(pair_lines):
            parts = line.strip().split()
            if len(parts) != 2:
                print(
                    _(
                        "Warning: Riga abbinamento malformata: '{line}' (saltata)"
                    ).format(line=line)
                )
                continue

            try:
                start_rank1_str, start_rank2_str = parts[0], parts[1]
                start_rank1 = int(start_rank1_str)
                start_rank2 = int(start_rank2_str)  # Può essere 0 per il BYE
            except ValueError:
                print(
                    _(
                        "Warning: ID non numerici nella riga abbinamento: '{line}' (saltata)"
                    ).format(line=line)
                )
                continue

            player1_id_tornello = mappa_start_rank_a_id.get(start_rank1)

            if player1_id_tornello is None:
                print(
                    _(
                        "Warning: StartRank {rank} non trovato nella mappa giocatori (riga: '{line}')."
                    ).format(rank=start_rank1, line=line)
                )
                continue

            if start_rank2 == 0:  # È un BYE
                parsed_matches.append(
                    {
                        "white_player_id": player1_id_tornello,
                        "black_player_id": None,  # Nessun Nero per il BYE
                        "result": "BYE",  # Pre-impostiamo il risultato
                        "is_bye": True,
                    }
                )
            else:
                player2_id_tornello = mappa_start_rank_a_id.get(start_rank2)
                if player2_id_tornello is None:
                    print(
                        _(
                            "Warning: StartRank avversario {rank} non trovato nella mappa (riga: '{line}')."
                        ).format(rank=start_rank2, line=line)
                    )
                    continue
                # Assumiamo che il primo giocatore nella coppia (player1) abbia il Bianco
                parsed_matches.append(
                    {
                        "white_player_id": player1_id_tornello,
                        "black_player_id": player2_id_tornello,
                        "result": None,
                        "is_bye": False,
                    }
                )
        return parsed_matches
    except Exception as e:
        print(
            _(
                "Errore durante il parsing dell'output delle coppie: {error}\n{traceback}"
            ).format(error=e, traceback=traceback.format_exc())
        )
        return None
