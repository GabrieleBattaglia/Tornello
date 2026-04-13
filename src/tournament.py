import os
import json
import traceback
from datetime import datetime, timedelta
from config import *
from utils import format_date_locale, sanitize_filename, create_backup
from engine import (
    handle_bbpairings_failure,
    genera_stringa_trf_per_bbpairings,
    run_bbpairings_engine,
    parse_bbpairings_couples_output,
)


def _ricalcola_stato_giocatore_da_storico(player_obj):
    """
    Azzera e ricalcola i punti e le statistiche di un giocatore
    basandosi sulla sua lista 'results_history'.
    Modifica direttamente l'oggetto giocatore passato.
    """
    # Azzera tutte le statistiche del torneo
    player_obj["points"] = 0.0
    player_obj["opponents"] = set()
    player_obj["white_games"] = 0
    player_obj["black_games"] = 0
    player_obj["last_color"] = None
    player_obj["consecutive_white"] = 0
    player_obj["consecutive_black"] = 0
    player_obj["received_bye_count"] = 0
    player_obj["received_bye_in_round"] = []
    # Ordina lo storico per assicurare un calcolo progressivo corretto
    history_sorted = sorted(
        player_obj.get("results_history", []), key=lambda x: x.get("round", 0)
    )
    for result in history_sorted:
        player_obj["points"] += result.get("score", 0.0)
        opponent = result.get("opponent_id")
        if opponent == "BYE_PLAYER_ID":
            player_obj["received_bye_count"] += 1
            player_obj["received_bye_in_round"].append(result.get("round"))
        elif opponent:
            player_obj["opponents"].add(opponent)

        color = result.get("color")
        if color == "white":
            player_obj["white_games"] += 1
            player_obj["last_color"] = "white"
            player_obj["consecutive_white"] += 1
            player_obj["consecutive_black"] = 0
        elif color == "black":
            player_obj["black_games"] += 1
            player_obj["last_color"] = "black"
            player_obj["consecutive_black"] += 1
            player_obj["consecutive_white"] = 0


def time_machine_torneo(torneo):
    """
    Permette di riavvolgere il torneo a uno stato precedente, cancellando
    i risultati dei turni successivi a quello scelto.
    ORA CORREGGE ANCHE next_match_id e ricalcola i punti dei BYE.
    Restituisce True se il riavvolgimento è stato effettuato, False altrimenti.
    """
    current_round = torneo.get("current_round", 1)
    print(_("\n--- Time Machine ---"))
    print(_("Questa funzione ripristina lo stato del torneo a un turno precedente."))
    prompt_template_1 = _("Puoi tornare a un qualsiasi turno da 1 a {max_round}.")
    print(prompt_template_1.format(max_round=current_round))
    print(
        _(
            "Tutti i risultati e gli abbinamenti successivi al turno scelto verranno cancellati."
        )
    )
    try:
        prompt_template_2 = _(
            "A quale turno vuoi tornare? (1-{max_round}, o vuoto per annullare): "
        )
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
    prompt_template_3 = _(
        "Verranno eliminati tutti i risultati e gli abbinamenti inseriti dal turno {target_round} in poi."
    )
    print(prompt_template_3.format(target_round=target_round))
    confirm = (
        input(
            _(
                "Sei assolutamente sicuro di voler procedere? (scrivi 'si' per confermare): "
            )
        )
        .strip()
        .lower()
    )
    if confirm != "si":
        print(_("Conferma non data. Operazione di riavvolgimento annullata."))
        return False
    prompt_template_4 = _("\nAvvio riavvolgimento al Turno {target_round}...")
    print(prompt_template_4.format(target_round=target_round))

    # Crea un backup del file torneo corrente prima dell'operazione
    if "name" in torneo:
        current_filename = f"Tornello - {sanitize_filename(torneo['name'])}.json"
        if create_backup(current_filename, "pre_timemachine"):
            print(
                _("Backup di sicurezza creato: {filename}").format(
                    filename=current_filename
                )
            )
        else:
            print(
                _(
                    "ATTENZIONE: Impossibile creare il backup di sicurezza. Procedo ugualmente..."
                )
            )

    # Azzera lo stato futuro (rimuove i round >= target_round)
    torneo["rounds"] = [
        r for r in torneo.get("rounds", []) if r.get("round", 0) < target_round
    ]
    for player in torneo.get("players", []):
        player["results_history"] = [
            res
            for res in player.get("results_history", [])
            if res.get("round", 0) < target_round
        ]
        if player.get("withdrawn", False):
            player["withdrawn"] = False
        # Questa funzione azzererà i punti a 0 e li ricalcolerà dalla storia (ora ridotta)
        _ricalcola_stato_giocatore_da_storico(player)
    torneo["current_round"] = target_round

    # Ricalcola il prossimo ID partita
    max_id = 0
    for r in torneo.get("rounds", []):
        for m in r.get("matches", []):
            if m.get("id", 0) > max_id:
                max_id = m.get("id", 0)
    torneo["next_match_id"] = max_id + 1
    print(_("Contatore ID Partita ripristinato a: {}").format(torneo["next_match_id"]))

    # <<< CORREZIONE 3: RIGENERAZIONE ABBINAMENTI PER IL TURNO DI DESTINAZIONE >>>
    print(
        _("Rigenerazione abbinamenti per il Turno {target_round}...").format(
            target_round=target_round
        )
    )
    matches_new = generate_pairings_for_round(torneo)
    if matches_new is None:
        print("ERRORE CRITICO: fallita rigenerazione turno post time machine.")
        torneo["current_round"] = current_round
        return False
    valore_bye_torneo = torneo.get("bye_value", 1.0)
    for match in matches_new:
        if match.get("result") == "BYE":
            bye_player_id = match.get("white_player_id")
            player_obj = get_player_by_id(torneo, bye_player_id)
            if player_obj:
                player_obj["points"] = player_obj.get("points", 0.0) + valore_bye_torneo
                player_obj.setdefault("results_history", []).append(
                    {
                        "round": target_round,
                        "opponent_id": "BYE_PLAYER_ID",
                        "color": None,
                        "result": "BYE",
                        "score": valore_bye_torneo,
                    }
                )
                print(
                    _(
                        "Ripristinato {score} punto/i per il BYE al Turno {round} per {name}."
                    ).format(
                        score=valore_bye_torneo,
                        round=target_round,
                        name=player_obj.get("first_name"),
                    )
                )

    # Aggiungiamo il nuovo set di abbinamenti alla lista dei round
    torneo.setdefault("rounds", []).append(
        {"round": target_round, "matches": matches_new}
    )

    # Ricostruisci il dizionario cache per coerenza
    torneo["players_dict"] = {p["id"]: p for p in torneo.get("players", [])}

    print(_("\nRiavvolgimento completato con successo!"))
    prompt_template_5 = _(
        "Il torneo è ora al Turno {target_round}, pronto per l'inserimento dei risultati."
    )
    print(prompt_template_5.format(target_round=target_round))
    return True


def load_tournament(filename_to_load):
    """Carica lo stato del torneo corrente dal file JSON."""
    if os.path.exists(filename_to_load):
        try:
            with open(filename_to_load, "r", encoding="utf-8") as f:
                torneo_data = json.load(f)
                torneo_data.setdefault("name", _("Torneo Sconosciuto"))
                torneo_data.setdefault(
                    "start_date", datetime.now().strftime(DATE_FORMAT_ISO)
                )
                torneo_data.setdefault(
                    "end_date", datetime.now().strftime(DATE_FORMAT_ISO)
                )
                torneo_data.setdefault("total_rounds", 0)
                torneo_data.setdefault("current_round", 1)
                torneo_data.setdefault("next_match_id", 1)
                torneo_data.setdefault("rounds", [])
                torneo_data.setdefault("players", [])
                torneo_data.setdefault("launch_count", 0)
                torneo_data.setdefault("site", _("Luogo Sconosciuto"))
                torneo_data.setdefault(
                    "federation_code", "ITA"
                )  # Federazione del torneo
                torneo_data.setdefault("chief_arbiter", "N/D")
                torneo_data.setdefault("deputy_chief_arbiters", "")
                torneo_data.setdefault("time_control", "Standard")
                torneo_data.setdefault("bye_value", 1.0)
                if "players" in torneo_data:
                    for p in torneo_data["players"]:
                        p["opponents"] = set(p.get("opponents", []))
                        p.setdefault("white_games", 0)
                        p.setdefault("black_games", 0)
                        p.setdefault(
                            "received_bye_count", 0
                        )  # Esempio se avevi aggiunto questo
                        p.setdefault("received_bye_in_round", [])
                torneo_data["players_dict"] = {
                    p["id"]: p for p in torneo_data.get("players", [])
                }
                return torneo_data
        except (json.JSONDecodeError, IOError) as e:
            print(
                _(
                    "Errore durante il caricamento del torneo ({filename}): {error}"
                ).format(filename=filename_to_load, error=e)
            )
            return None
    return None


def save_tournament(torneo):
    """Salva lo stato corrente del torneo nel file JSON."""
    tournament_name_for_file = None  # Inizializza a None
    dynamic_tournament_filename = None  # Inizializza a None
    try:
        tournament_name_for_file = torneo.get("name")
        if not tournament_name_for_file:
            print(_("Errore: Nome del torneo non presente. Impossibile salvare."))
            return  # O gestisci diversamente, es. nome file di default
        sanitized_name = sanitize_filename(tournament_name_for_file)
        dynamic_tournament_filename = f"Tornello - {sanitized_name}.json"
        torneo_to_save = torneo.copy()
        # Prepara i dati per il salvataggio JSON
        if "players" in torneo_to_save:
            temp_players = []
            for p in torneo_to_save["players"]:
                player_copy = p.copy()
                # Converti set in lista PRIMA di salvare
                player_copy["opponents"] = list(player_copy.get("opponents", set()))
                temp_players.append(player_copy)
            torneo_to_save["players"] = temp_players
        # Rimuovi il dizionario cache che non è serializzabile o necessario salvare
        if "players_dict" in torneo_to_save:
            del torneo_to_save["players_dict"]
        with open(dynamic_tournament_filename, "w", encoding="utf-8") as f:
            json.dump(torneo_to_save, f, indent=1, ensure_ascii=False)
    except IOError as e:
        print(
            _("Errore durante il salvataggio del torneo ({filename}): {error}").format(
                filename=dynamic_tournament_filename, error=e
            )
        )
    except Exception as e:
        print(_("Errore imprevisto durante il salvataggio del torneo: {}").format(e))
        traceback.print_exc()  # Stampa più dettagli in caso di errore non previsto


def _ensure_players_dict(torneo):
    """Assicura che il dizionario cache dei giocatori sia presente e aggiornato."""
    if "players_dict" not in torneo or len(torneo["players_dict"]) != len(
        torneo.get("players", [])
    ):
        torneo["players_dict"] = {p["id"]: p for p in torneo.get("players", [])}
    return torneo["players_dict"]


def get_player_by_id(torneo, player_id):
    """Restituisce i dati del giocatore nel torneo dato il suo ID, usando il dizionario interno."""
    # Ricrea il dizionario se non esiste o sembra obsoleto
    _ensure_players_dict(torneo)
    return torneo["players_dict"].get(player_id)


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
            print(
                _(
                    "ERRORE: La durata totale del torneo ({duration} giorni) è inferiore al numero di turni previsti ({rounds})."
                ).format(duration=total_duration, rounds=total_rounds)
            )
            print(
                _(
                    "Impossibile programmare i turni senza sovrapposizioni. Ampliare la finestra temporale o ridurre i turni."
                )
            )
            return None
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
            start_day_offset = (
                round(accumulated_days - days_per_round_float) if i > 0 else 0
            )
            # Calcola i giorni effettivi per questo turno
            current_round_days = end_day_offset - start_day_offset
            # Assicura almeno 1 giorno per turno
            if current_round_days <= 0:
                current_round_days = 1
            # Calcola la data di fine
            current_end_date = current_start_date + timedelta(
                days=current_round_days - 1
            )
            # Assicura che l'ultima data di fine sia quella del torneo
            if round_num == total_rounds:
                current_end_date = end_date
            # Assicura che le date intermedie non superino la data finale del torneo
            elif current_end_date > end_date:
                current_end_date = end_date
            round_dates.append(
                {
                    "round": round_num,
                    "start_date": current_start_date.strftime(DATE_FORMAT_ISO),
                    "end_date": current_end_date.strftime(DATE_FORMAT_ISO),
                }
            )
            # Prepara la data di inizio per il prossimo turno
            next_start_candidate = current_end_date + timedelta(days=1)
            # Se non c'è più spazio, usa l'ultimo giorno disponibile
            if next_start_candidate > end_date and round_num < total_rounds:
                print(
                    _(
                        "Avviso: Spazio insufficiente per i turni rimanenti. Il turno {round_num} inizierà il {date} (ultimo giorno)."
                    ).format(round_num=round_num + 1, date=format_date_locale(end_date))
                )
                current_start_date = end_date
            else:
                current_start_date = next_start_candidate
        return round_dates
    except ValueError:
        print(
            _(
                "Formato data non valido ('{start_date}' o '{end_date}'). Usa {date_format}."
            ).format(
                start_date=start_date_str,
                end_date=end_date_str,
                date_format=DATE_FORMAT_ISO,
            )
        )
        return None
    except Exception as e:
        print(_("Errore nel calcolo delle date: {error}").format(error=e))
        return None


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
    print(
        _("\n--- Generazione Abbinamenti Turno {round_num} con bbpPairings ---").format(
            round_num=round_number
        )
    )
    for player in torneo.get("players", []):
        _ricalcola_stato_giocatore_da_storico(player)
    _ensure_players_dict(torneo)
    lista_giocatori_attivi = [p.copy() for p in torneo.get("players", [])]
    if not lista_giocatori_attivi:
        print(
            _("Nessun giocatore attivo per il turno {round_num}.").format(
                round_num=round_number
            )
        )
        return []

    # 1. Creare mappa ID Tornello -> StartRank e viceversa
    def get_effective_elo(p):
        elo = float(p.get("initial_elo", DEFAULT_ELO))
        return elo if elo > 0 else DEFAULT_ELO

    players_sorted_for_start_rank = sorted(
        lista_giocatori_attivi,
        key=lambda p: (
            -get_effective_elo(p),
            p.get("last_name", "").lower(),
            p.get("first_name", "").lower(),
        ),
    )

    mappa_id_a_start_rank = {
        p["id"]: i + 1 for i, p in enumerate(players_sorted_for_start_rank)
    }
    mappa_start_rank_a_id = {
        i + 1: p["id"] for i, p in enumerate(players_sorted_for_start_rank)
    }
    # 2. Generare la stringa TRF
    trf_string = genera_stringa_trf_per_bbpairings(
        torneo, players_sorted_for_start_rank, mappa_id_a_start_rank
    )
    if not trf_string:
        print(_("ERRORE: Fallita generazione della stringa TRF per bbpPairings."))
        return handle_bbpairings_failure(
            torneo, round_number, "Fallimento generazione stringa TRF."
        )
    # 3. Eseguire bbpPairings.exe
    success, bbp_output_data, bbp_message = run_bbpairings_engine(trf_string)
    all_generated_matches = []
    if success:
        print(_("bbpPairings eseguito con successo."))

        # 4. Parsare l'output delle coppie
        parsed_pairing_list = parse_bbpairings_couples_output(
            bbp_output_data["coppie_raw"], mappa_start_rank_a_id
        )
        if parsed_pairing_list is None:
            print(_("ERRORE: Fallimento parsing output coppie di bbpPairings."))
            return handle_bbpairings_failure(
                torneo,
                round_number,
                f"Fallimento parsing output bbpPairings:\n{bbp_message}",
            )
        # 5. Convertire in formato `all_matches`
        for i, match_info in enumerate(parsed_pairing_list):
            match_id_counter = torneo.get("next_match_id", 1)
            current_match = {
                "id": match_id_counter,
                "round": round_number,
                "white_player_id": match_info["white_player_id"],
                "black_player_id": match_info.get("black_player_id"),
                "result": match_info.get("result"),  # Sarà "BYE" o None
            }
            all_generated_matches.append(current_match)
            torneo["next_match_id"] = match_id_counter + 1
            # ---> IN QUESTA VERSIONE CORRETTA, NON C'È PIÙ ALCUN AGGIORNAMENTO DI STATO QUI <---
            # Le righe che aggiornavano punti, storico, avversari, colori, etc. sono state rimosse.
            # La funzione ora fa solo UNA cosa: genera gli abbinamenti.
    else:  # bbpPairings.exe ha fallito
        returncode = bbp_output_data.get("returncode", -1) if bbp_output_data else -1
        if returncode == 1:
            print(_("ATTENZIONE: bbpPairings non ha trovato abbinamenti validi."))
            return handle_bbpairings_failure(
                torneo, round_number, "bbpPairings: Nessun abbinamento valido trovato."
            )
        else:
            print(
                _("ERRORE CRITICO da bbpPairings.exe: {message}").format(
                    message=bbp_message
                )
            )
            return handle_bbpairings_failure(
                torneo, round_number, f"Errore critico bbpPairings:\n{bbp_message}"
            )
    print(_("--- Abbinamenti Turno {} generati. ---").format(round_number))
    return all_generated_matches


def ricalcola_punti_tutti_giocatori(torneo):
    """
    Forza il ricalcolo dei punti per tutti i giocatori partendo da zero,
    basandosi unicamente sulla loro cronologia dei risultati.
    Questa è la fonte di verità per i punteggi.
    """
    if not torneo or "players" not in torneo:
        return  # Non fare nulla se il torneo non è valido

    for p in torneo.get("players", []):
        p["points"] = 0.0  # Azzera i punti
        for res in p.get("results_history", []):
            p["points"] += float(res.get("score", 0.0))


def _apply_match_result_to_players(torneo, match_obj, result_str, w_score, b_score):
    """
    Funzione di supporto che applica il risultato di una partita ai due giocatori
    e aggiorna tutte le strutture dati necessarie.
    """
    current_round_num = torneo.get("current_round")
    if not current_round_num:
        return

    wp_id = match_obj.get("white_player_id")
    bp_id = match_obj.get("black_player_id")

    # Lavoriamo direttamente sul dizionario cache per coerenza
    wp_data_obj = torneo["players_dict"].get(wp_id)
    bp_data_obj = torneo["players_dict"].get(bp_id)

    if not wp_data_obj or not bp_data_obj:
        print(
            f"ERRORE INTERNO: Impossibile trovare i giocatori {wp_id} o {bp_id} per applicare il risultato."
        )
        return

    # 1. Applica i punteggi
    wp_data_obj["points"] = float(wp_data_obj.get("points", 0.0)) + w_score
    # --- ECCO LA CORREZIONE FONDAMENTALE ---
    bp_data_obj["points"] = float(bp_data_obj.get("points", 0.0)) + b_score

    # 2. Aggiorna lo storico dei risultati
    wp_data_obj.setdefault("results_history", []).append(
        {
            "round": current_round_num,
            "opponent_id": bp_id,
            "color": "white",
            "result": result_str,
            "score": w_score,
        }
    )
    bp_data_obj.setdefault("results_history", []).append(
        {
            "round": current_round_num,
            "opponent_id": wp_id,
            "color": "black",
            "result": result_str,
            "score": b_score,
        }
    )

    # 3. Aggiorna l'oggetto 'match' originale nella lista dei round
    for r in torneo.get("rounds", []):
        if r.get("round") == current_round_num:
            for i, m in enumerate(r.get("matches", [])):
                if m.get("id") == match_obj.get("id"):
                    r["matches"][i]["result"] = result_str
                    # Rimuovi la pianificazione se c'era
                    if r["matches"][i].get("is_scheduled"):
                        r["matches"][i]["is_scheduled"] = False
                    break
            break
    print(_("\nRisultato registrato con successo."))
