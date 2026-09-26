import copy
import glob
import json
import os
import shutil
import traceback
from datetime import datetime

from GBUtils import dgt, key

from config import (
    ARCHIVED_TOURNAMENTS_DIR,
    DATE_FORMAT_ISO,
    DEFAULT_ELO,
    PLAYER_DB_FILE,
    user_data_path,
)
from db_players import (
    _cerca_giocatore_nel_db_fide,
    aggiungi_dal_fide,
    allinea_giocatori_con_database,
    crea_nuovo_giocatore_nel_db,
    database_non_letto,
    fattore_k_della_finalizzazione,
    messaggio_database_non_letto,
    save_players_db,
    scheda_dal_torneo,
    scheda_nel_database,
)

# Le due funzioni che riconoscono il torneo nello storico dei giocatori
# stanno in db_players dalla 10.10.0: le usa anche lo storno del ripristino,
# che deve trovare le stesse voci che la finalizzazione ha scritto.
from db_players import identita_del_torneo as _identita_del_torneo
from db_players import voce_di_questo_torneo as _voce_di_questo_torneo
from reports import save_standings_text, save_suspended_tournament_summary
from stats import (
    calculate_elo_change,
    calculate_performance_rating,
    campo_elo_della_cadenza,
    compute_aro,
    compute_buchholz,
    compute_buchholz_cut1,
    elo_a_cui_sommare_la_variazione,
    get_initial_elo_for_tournament,
    partite_valide_per_elo,
)
from tournament import (
    _apply_match_result_to_players,
    save_tournament,
    time_machine_torneo,
)
from utils import (
    copia_di_sicurezza,
    create_backup,
    enter_escape,
    file_del_torneo,
    format_date_locale,
    play_sound,
    sanitize_filename,
)

# Il confronto dei byte sta in utils dalla 10.10.0, condiviso con il
# ripristino delle copie di sicurezza e con le copie di chiusura.
from utils import stessi_byte as _stessi_byte


def _conferma_lista_giocatori_torneo(torneo, players_db):
    """
    Mostra i giocatori iscritti a un nuovo torneo e permette la rimozione.
    Restituisce True se la lista giocatori è valida per procedere, False se annullato o troppi pochi giocatori.
    Modifica direttamente torneo['players'] e torneo['players_dict'].
    """
    if not torneo or "players" not in torneo:
        print(_("Errore: Dati torneo o giocatori mancanti per la conferma."))
        return False

    print(_("Riepilogo Giocatori Iscritti al Torneo"))

    while True:
        if not torneo["players"]:
            print(_("Nessun giocatore attualmente iscritto al torneo."))
            if enter_escape(
                _("Vuoi tornare all'inserimento giocatori? (INVIO|ESCAPE)")
            ):
                # Questo richiederebbe di uscire da qui e rientrare in input_players,
                # o modificare input_players per essere richiamabile.
                # Per ora, diciamo che l'utente deve ricreare il torneo se svuota la lista.
                print(
                    _(
                        "Lista giocatori vuota. La creazione del torneo potrebbe fallire o necessitare di nuovi inserimenti."
                    )
                )
                return False  # Indica che la lista non è valida per procedere
            return False  # L'utente non vuole aggiungere, ma la lista è vuota.

        print(
            _("Numero attuale di giocatori: {count}").format(
                count=len(torneo["players"])
            )
        )
        for i, player_data in enumerate(torneo["players"]):
            # Assicurati che i dati per il display siano disponibili
            # Se i giocatori provengono da input_players, dovrebbero avere questi campi.
            player_id = player_data.get("id", "N/A")
            first_name = player_data.get("first_name", _("Nome?"))
            last_name = player_data.get("last_name", _("Cognome?"))
            elo = player_data.get(
                "initial_elo", "Elo?"
            )  # In un nuovo torneo, sarà initial_elo
            print(f"  {i + 1}. ID: {player_id} - {first_name} {last_name} (Elo: {elo})")
        choice = (
            input(
                _(
                    "\nVuoi rimuovere un giocatore dalla lista? (Inserisci il numero, o 'f' per finire e confermare): "
                )
            )
            .strip()
            .lower()
        )
        if choice == "f":
            min_players_for_tournament = (
                torneo.get("total_rounds", 1) + 1
            )  # Esempio di regola: NumTurni + 1
            if len(torneo["players"]) < min_players_for_tournament:
                print(
                    _(
                        "ERRORE CRITICO: Sono necessari almeno {min_players} giocatori per un torneo di {rounds} turni."
                    ).format(
                        min_players=min_players_for_tournament,
                        rounds=torneo.get("total_rounds"),
                    )
                )
                print(
                    _(
                        "Non puoi procedere finché non inserisci un numero sufficiente di giocatori, oppure modifichi i parametri del torneo."
                    )
                )
                return False

            # --- AGGIORNAMENTO SILENZIOSO DATI GIOCATORI ---
            # Allinea eventuali aggiornamenti del database (Elo, Titoli) prima di cristallizzare la lista
            category = torneo.get("tournament_category", "standard")
            aggiornati = allinea_giocatori_con_database(
                torneo["players"], players_db, category
            )

            if aggiornati > 0:
                print(
                    _(
                        "\nInfo: I dati (Elo/Titoli) di {count} giocatore/i sono stati automaticamente allineati all'ultimo aggiornamento del Database."
                    ).format(count=aggiornati)
                )
            # -----------------------------------------------

            print(_("Lista giocatori confermata."))
            return True  # Lista confermata e valida (o utente ha forzato con meno giocatori)
        if choice.isdigit():
            try:
                idx_to_remove = int(choice) - 1
                if 0 <= idx_to_remove < len(torneo["players"]):
                    player_to_remove = torneo["players"][idx_to_remove]
                    confirm_remove = enter_escape(
                        _(
                            "Rimuovere '{first_name} {last_name}'? (INVIO|ESCAPE): "
                        ).format(
                            first_name=player_to_remove.get("first_name"),
                            last_name=player_to_remove.get("last_name"),
                        )
                    )
                    if confirm_remove:
                        removed_player = torneo["players"].pop(idx_to_remove)
                        play_sound("rimozione_giocatore", torneo)
                        print(
                            _("Giocatore '{first_name} {last_name}' rimosso.").format(
                                first_name=removed_player.get("first_name"),
                                last_name=removed_player.get("last_name"),
                            )
                        )
                        # Aggiorna anche players_dict se necessario (o fallo alla fine una volta)
                        torneo["players_dict"] = {p["id"]: p for p in torneo["players"]}
                    else:
                        print(_("Rimozione annullata."))
                else:
                    print(_("Numero giocatore non valido."))
            except ValueError:
                print(_("Input non valido."))
        else:
            print(_("Comando non riconosciuto."))


def input_schedule_details(existing_details=None):
    from datetime import datetime

    from config import DATE_FORMAT_ISO

    details = {}
    is_modifying = existing_details is not None
    now = datetime.now()

    print(_("Dettagli Pianificazione Partita"))
    if is_modifying:
        print(_("Lasciare il campo vuoto per mantenere il valore attuale."))
    while True:
        prompt_date = _("Data partita (formati: GG, GG-MM, {iso_format})").format(
            iso_format=DATE_FORMAT_ISO
        )
        default_date_val_for_input = ""
        current_display = "N/D"
        if is_modifying and existing_details and existing_details.get("date"):
            default_date_val_for_input = existing_details["date"]
            current_display = format_date_locale(default_date_val_for_input)
        prompt_date += _(" [Attuale: {current}]: ").format(current=current_display)
        date_input_str = get_input_with_default(
            prompt_date, default_date_val_for_input
        ).strip()
        if not date_input_str and is_modifying:
            details["date"] = default_date_val_for_input
            break
        if not date_input_str and not is_modifying:
            print(_("La data è obbligatoria."))
            continue

        parsed_date_obj = None
        try:
            if "-" in date_input_str or "/" in date_input_str:
                parts = date_input_str.replace("/", "-").split("-")
                if len(parts) == 2:
                    day, month = int(parts[0]), int(parts[1])
                    parsed_date_obj = datetime(now.year, month, day)
                elif len(parts) == 3:
                    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                    if year < 100:
                        year += 2000
                    parsed_date_obj = datetime(year, month, day)
                else:
                    raise ValueError(_("Formato data non riconosciuto"))
            elif date_input_str.isdigit() and 1 <= len(date_input_str) <= 2:
                day = int(date_input_str)
                parsed_date_obj = datetime(now.year, now.month, day)
            else:
                from utils import parse_flexible_date

                parsed_date_obj = parse_flexible_date(date_input_str)

            details["date"] = parsed_date_obj.strftime(DATE_FORMAT_ISO)
            break
        except ValueError:
            print(
                _(
                    "Formato data '{input}' non valido o data inesistente. Usa GG, GG-MM, {iso_format} o AAAAMMGG."
                ).format(input=date_input_str, iso_format=DATE_FORMAT_ISO)
            )
        except TypeError:
            print(
                _("Input data '{input}' non interpretabile.").format(
                    input=date_input_str
                )
            )

    while True:
        prompt_time = _("Ora partita (formati: HH, HH:MM)")
        default_time_val_for_input = ""
        current_display_time = "N/O"
        if is_modifying and existing_details and existing_details.get("time"):
            default_time_val_for_input = existing_details["time"]
            current_display_time = default_time_val_for_input
        prompt_time += _(" [Attuale: {current}]: ").format(current=current_display_time)
        time_input_str = get_input_with_default(
            prompt_time, default_time_val_for_input
        ).strip()
        if not time_input_str and is_modifying:
            details["time"] = default_time_val_for_input
            break
        if not time_input_str and not is_modifying:
            print(_("L'ora è obbligatoria."))
            continue
        parsed_time_str = None
        try:
            if ":" in time_input_str:
                dt_obj = datetime.strptime(time_input_str, "%H:%M")
                parsed_time_str = dt_obj.strftime("%H:%M")
            elif (
                time_input_str.isdigit()
                and 0 <= int(time_input_str) <= 23
                and len(time_input_str) <= 2
            ):
                hour = int(time_input_str)
                parsed_time_str = f"{hour:02d}:00"
            else:
                raise ValueError(_("Formato ora non riconosciuto"))
            details["time"] = parsed_time_str
            break
        except ValueError:
            print(_("Formato ora non valido. Usa HH (es. 9) o HH:MM (es. 15:30)."))
    default_channel_val = (
        "" if not is_modifying else existing_details.get("channel", "")
    )
    details["channel"] = get_input_with_default(
        _("Canale/Link partita [Attuale: {current}]: ").format(
            current=default_channel_val
        ),
        default_channel_val,
    ).strip()
    default_arbiter_val = (
        "" if not is_modifying else existing_details.get("arbiter", "")
    )
    details["arbiter"] = get_input_with_default(
        _("Arbitro assegnato [Attuale: {current}]: ").format(
            current=default_arbiter_val
        ),
        default_arbiter_val,
    ).strip()
    if is_modifying:
        changed = False
        if details.get("date") != existing_details.get("date"):
            changed = True
        if details.get("time") != existing_details.get("time"):
            changed = True
        if details.get("channel", "") != existing_details.get("channel", ""):
            changed = True
        if details.get("arbiter", "") != existing_details.get("arbiter", ""):
            changed = True
        if not changed:
            print(
                _(
                    "Nessun dettaglio della pianificazione è stato effettivamente modificato."
                )
            )
    if not details.get("date") or not details.get("time"):
        print(
            _(
                "Data e ora sono obbligatori per la pianificazione. Operazione annullata."
            )
        )
        return None
    return details


def get_input_with_default(prompt_message, default_value=None):
    default_display = str(default_value) if default_value is not None else ""
    if default_display or default_value is None:
        user_input = input(f"{prompt_message} [{default_display}]: ").strip()
        return user_input if user_input else default_value
    return input(f"{prompt_message}: ").strip()


def input_players(
    players_db, existing_players=None, torneo_obj=None, torneo_filename=None
):
    """
    Gestisce l'input dei giocatori per un torneo con una ricerca a 3 livelli.
    Permette di riprendere un inserimento interrotto.
    Restituisce la lista aggiornata dei giocatori (o None se l'utente sospende l'inserimento).
    """
    players_in_tournament = existing_players.copy() if existing_players else []
    added_player_ids_to_tournament = {p["id"] for p in players_in_tournament}

    print(_("Inserimento Giocatori per il Torneo"))
    print(_("Inserire ID locale, ID FIDE, o parte del Nome/Cognome."))
    print(
        _(
            "Il programma cercherà prima nel tuo DB personale, poi nel DB FIDE scaricato."
        )
    )
    while True:
        current_num_players = len(players_in_tournament)
        data_input = input(
            _("\nGiocatore {player_num} (o lascia vuoto per terminare): ").format(
                player_num=current_num_players + 1
            )
        ).strip()
        if not data_input:  # Logica per terminare o sospendere l'inserimento
            print(
                _(
                    "Vuoi (C)oncludere l'inserimento giocatori, (S)ospenderlo temporaneamente per riprenderlo in futuro, o (A)nnullare l'inserimento corrente?"
                )
            )
            scelta = key(
                _("Premi 'c' per concludere, 's' per sospendere, Esc per annullare: ")
            ).lower()
            if scelta == "c":
                return players_in_tournament
            if scelta == "s":
                if torneo_obj and torneo_filename:
                    print(
                        _("\nSospensione inserimento. Salvataggio stato del torneo...")
                    )
                    torneo_obj["players"] = players_in_tournament
                    torneo_obj["players_dict"] = {
                        p["id"]: p for p in players_in_tournament
                    }
                    # Aggiungiamo un flag esplicito per indicare che la creazione è sospesa
                    torneo_obj["creation_suspended"] = True
                    save_tournament(torneo_obj)
                    print(
                        _("Torneo sospeso salvato in: '{filename}'").format(
                            filename=torneo_filename
                        )
                    )

                    base_name = os.path.splitext(torneo_filename)[0]
                    save_suspended_tournament_summary(torneo_obj, base_name)

                    return None
                print(
                    _("Errore: impossibile sospendere il torneo in questo momento.")
                )
                continue
            return players_in_tournament  # Di default, se annulla/escape o altro, torna la lista attuale e decide la logica chiamante
        player_id_to_add = None
        player_data_from_db = None
        was_newly_created = False

        # --- LIVELLO 1: Ricerca nel DB Personale (`players_db`) ---
        potential_id_input = data_input.upper()
        if potential_id_input in players_db:
            if potential_id_input in added_player_ids_to_tournament:
                print(
                    _(
                        "Errore: Giocatore ID {player_id} ({first_name} {last_name}) è già nel torneo."
                    ).format(
                        player_id=potential_id_input,
                        first_name=players_db[potential_id_input].get("first_name"),
                        last_name=players_db[potential_id_input].get("last_name"),
                    )
                )
                continue
            player_id_to_add = potential_id_input
        else:
            search_terms = data_input.lower().split()
            matches_in_personal_db = [
                p
                for p in players_db.values()
                if all(
                    term
                    in f"{p.get('first_name', '')} {p.get('last_name', '')} {p.get('id', '')}".lower()
                    for term in search_terms
                )
            ]
            if matches_in_personal_db:
                print(
                    _(
                        "\nTrovati {count} giocatori nel tuo DB personale corrispondenti a '{term}':"
                    ).format(count=len(matches_in_personal_db), term=data_input)
                )
                for i, p in enumerate(matches_in_personal_db):
                    status = (
                        _(" (GIÀ NEL TORNEO)")
                        if p.get("id") in added_player_ids_to_tournament
                        else ""
                    )
                    print(
                        f"  {i + 1}. ID: {p.get('id')} - {p.get('first_name')} {p.get('last_name')}{status}"
                    )
                print(_("  0. Nessuno di questi, cerca nel DB FIDE"))

                choice = input(
                    _(
                        "Scegli un numero (o Invio per annullare e cercare un altro nome): "
                    )
                ).strip()
                if not choice:
                    continue
                if choice == "0":
                    player_id_to_add = None  # Will proceed to Level 2
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(matches_in_personal_db):
                        selected_p = matches_in_personal_db[idx]
                        if selected_p["id"] in added_player_ids_to_tournament:
                            print(
                                _("Errore: Il giocatore selezionato è già nel torneo.")
                            )
                            continue
                        player_id_to_add = selected_p["id"]
                    else:
                        print(_("Scelta non valida."))
                        continue
                else:
                    print(_("Input non valido."))
                    continue

        if player_id_to_add:
            # Trovato nel DB personale (o selezionato dall'utente)
            player_data_from_db = players_db[player_id_to_add]

        # --- LIVELLO 2: Ricerca nel DB FIDE Locale (se non trovato nel DB personale) ---
        if not player_id_to_add:
            print(
                _(
                    "Giocatore non trovato o non selezionato nel DB personale. Avvio ricerca nel DB FIDE..."
                )
            )
            fide_matches = _cerca_giocatore_nel_db_fide(data_input)

            selected_fide_record = None
            if len(fide_matches) == 1:
                match = fide_matches[0]
                print(_("\n-> Trovata 1 corrispondenza nel DB FIDE:"))
                print(
                    _(
                        "   Nome: {last_name}, {first_name} (ID FIDE: {fide_id}, FED: {fed}, Elo: {elo})"
                    ).format(
                        last_name=match["last_name"],
                        first_name=match["first_name"],
                        fide_id=match["id_fide"],
                        fed=match["federation"],
                        elo=match["elo_standard"],
                    )
                )
                if enter_escape(_("   È questo il giocatore corretto? (INVIO|ESCAPE)")):
                    selected_fide_record = match
            elif len(fide_matches) > 1:
                print(
                    _(
                        "\n-> Trovate {count} corrispondenze nel DB FIDE per '{term}'. Scegli quella corretta:"
                    ).format(count=len(fide_matches), term=data_input)
                )
                start_index = 0
                page_size = 15
                current_search_term = data_input
                while True:  # Loop per la paginazione
                    if start_index >= len(fide_matches):
                        print(
                            _(
                                "Non ci sono altri risultati da mostrare. Procedo con l'inserimento manuale."
                            )
                        )
                        selected_fide_record = None
                        break
                    # Mostra la pagina corrente di risultati
                    page_matches = fide_matches[start_index : start_index + page_size]
                    for i, match in enumerate(page_matches):
                        display_num = start_index + i + 1
                        print(
                            f"   {display_num}. ID FIDE: {match['id_fide']:<9} | {match['last_name']}, {match['first_name']:<25} | FED: {match['federation']:<3} | Elo: {match['elo_standard']:<4}"
                        )
                    print(_("   0. Nessuno di questi / Inserimento manuale"))
                    # Costruisce il prompt per l'utente
                    prompt_text = "\n"
                    has_more_pages = (start_index + page_size) < len(fide_matches)
                    if has_more_pages:
                        prompt_text += _(
                            "Scelta (Numero, 0 per manuale, Invio per successivi, +testo/-testo/testo per affinare): "
                        )
                    else:
                        prompt_text += _(
                            "Scelta (Numero o 0 per manuale, +testo/-testo/testo per affinare): "
                        )
                    choice_str = input(prompt_text).strip()
                    # Gestisce l'input dell'utente
                    if (
                        not choice_str and has_more_pages
                    ):  # L'utente preme Invio per la pagina successiva
                        start_index += page_size
                        print(_("Mostro i risultati successivi"))
                        continue
                    if not choice_str and not has_more_pages:
                        print(
                            _(
                                "Non ci sono altri risultati. Scegli un numero, 0 per manuale, oppure affina la ricerca."
                            )
                        )
                        continue
                    if choice_str.isdigit():
                        choice_num = int(choice_str)
                        if choice_num == 0:
                            selected_fide_record = None  # Attiva l'inserimento manuale
                            break
                        if 1 <= choice_num <= len(fide_matches):
                            selected_fide_record = fide_matches[choice_num - 1]
                            break
                        print(_("Scelta non valida. Riprova."))
                    else:
                        # Gestione affinamento ricerca
                        if choice_str.startswith("+"):
                            added_term = choice_str[1:].strip()
                            if added_term:
                                current_search_term = (
                                    f"{current_search_term} {added_term}"
                                )
                        elif choice_str.startswith("-"):
                            removed_term = choice_str[1:].strip().lower()
                            if removed_term:
                                terms = current_search_term.lower().split()
                                terms = [t for t in terms if t != removed_term]
                                current_search_term = " ".join(terms)
                        else:
                            current_search_term = choice_str

                        if not current_search_term.strip():
                            print(
                                _(
                                    "Il termine di ricerca non può essere vuoto. Inserisci un nuovo termine."
                                )
                            )
                            continue

                        print(
                            _("\n-> Nuova ricerca nel DB FIDE per '{term}'...").format(
                                term=current_search_term
                            )
                        )
                        fide_matches = _cerca_giocatore_nel_db_fide(current_search_term)
                        start_index = 0

                        if len(fide_matches) == 0:
                            print(
                                _(
                                    "Nessuna corrispondenza trovata con questi termini. Procedo con l'inserimento manuale."
                                )
                            )
                            selected_fide_record = None
                            break
                        if len(fide_matches) == 1:
                            match = fide_matches[0]
                            print(_("\n-> Trovata 1 corrispondenza nel DB FIDE:"))
                            print(
                                _(
                                    "   Nome: {last_name}, {first_name} (ID FIDE: {fide_id}, FED: {fed}, Elo: {elo})"
                                ).format(
                                    last_name=match["last_name"],
                                    first_name=match["first_name"],
                                    fide_id=match["id_fide"],
                                    fed=match["federation"],
                                    elo=match["elo_standard"],
                                )
                            )
                            if enter_escape(
                                _("   È questo il giocatore corretto? (INVIO|ESCAPE)")
                            ):
                                selected_fide_record = match
                                break
                            print(_("Procedo con l'inserimento manuale."))
                            selected_fide_record = None
                            break
                        print(
                            _("Trovate {count} corrispondenze.").format(
                                count=len(fide_matches)
                            )
                        )
                        continue

            # Se è stato selezionato un giocatore dal DB FIDE, crealo nel nostro DB personale
            if selected_fide_record:
                print(
                    _(
                        "Importazione di '{first_name} {last_name}' nel tuo DB personale..."
                    ).format(
                        first_name=selected_fide_record["first_name"],
                        last_name=selected_fide_record["last_name"],
                    )
                )
                # La scheda e' quella della finestra di iscrizione, con tutti
                # i dati FIDE, dalla 10.13.15: fino ad allora mancavano gli
                # Elo rapid e blitz e i fattori K, e senza Elo standard
                # current_elo restava a zero. Se il database locale ha gia'
                # una scheda con lo stesso identificativo FIDE, si usa quella
                # invece di crearne un doppione. experienced resta quello
                # della console: un giocatore con rating FIDE e' per
                # definizione esperto.
                scheda_fide, creata = aggiungi_dal_fide(
                    players_db, selected_fide_record, experienced=True
                )
                if scheda_fide is not None:
                    player_id_to_add = scheda_fide["id"]
                    player_data_from_db = scheda_fide
                    was_newly_created = creata
                else:
                    print(
                        _(
                            "Errore durante la creazione del giocatore importato. Si prega di riprovare."
                        )
                    )
                    continue

        # --- LIVELLO 3: Creazione Manuale (se non trovato da nessuna parte) ---
        if not player_id_to_add:
            print(
                _("Nessuna corrispondenza trovata. Procedi con l'inserimento manuale.")
            )
            first_name_new_db = (
                get_input_with_default(_("  Nome del nuovo giocatore: "))
                .strip()
                .title()
            )
            if not first_name_new_db:
                continue
            last_name_new_db = get_input_with_default(_("  Cognome: ")).strip().title()
            if not last_name_new_db:
                continue
            elo_new_db = dgt(
                f"  Elo (default {int(DEFAULT_ELO)})",
                kind="i",
                imin=500,
                imax=4000,
                default=int(DEFAULT_ELO),
            )
            fide_title_new_db = (
                get_input_with_default(_("  Titolo FIDE (es. FM, o vuoto)"), "")
                .strip()
                .upper()[:3]
            )
            sex_new_db = get_input_with_default(_("  Sesso (m/w)"), "m").strip().lower()
            fed_new_db = (
                get_input_with_default(_("  Federazione (3 lettere, es. ITA)"), "ITA")
                .strip()
                .upper()[:3]
                or "ITA"
            )
            fide_id_new_db = get_input_with_default(
                _("  ID FIDE Numerico ('0' se N/D)"), "0"
            ).strip()

            while True:
                bdate_input = get_input_with_default(
                    _("  Data Nascita ({date_format} o vuoto o AAAAMMGG)").format(
                        date_format=DATE_FORMAT_ISO
                    ),
                    "",
                )
                if bdate_input:
                    try:
                        from utils import parse_flexible_date

                        parsed_dt = parse_flexible_date(bdate_input)
                        birth_date_new_db = parsed_dt.strftime(DATE_FORMAT_ISO)
                        break
                    except ValueError:
                        print(_("Formato data non valido. Riprova."))
                else:
                    birth_date_new_db = None
                    break

            exp_new_db = enter_escape(
                _(" Esperienza pregressa significativa? (INVIO|ESCAPE)")
            )
            player_id_to_add = crea_nuovo_giocatore_nel_db(
                players_db,
                first_name_new_db,
                last_name_new_db,
                elo_new_db,
                fide_title_new_db,
                sex_new_db,
                fed_new_db,
                fide_id_new_db,
                birth_date_new_db,
                exp_new_db,
                silent=True,
            )
            if player_id_to_add:
                player_data_from_db = players_db.get(player_id_to_add)
                was_newly_created = True

        # --- Aggiunta finale del giocatore (selezionato o creato) al TORNEO ---
        if player_id_to_add and player_data_from_db:
            if player_id_to_add in added_player_ids_to_tournament:
                print(
                    _(
                        "Errore: Giocatore ID {player_id} ({player_name}) è già stato aggiunto a questo torneo."
                    ).format(
                        player_id=player_id_to_add,
                        player_name=player_data_from_db.get("first_name"),
                    )
                )
            else:
                category = torneo_obj.get("tournament_category", "standard")
                elo_per_torneo = int(
                    get_initial_elo_for_tournament(player_data_from_db, category)
                )
                player_instance = {
                    "id": player_id_to_add,
                    "first_name": player_data_from_db.get("first_name"),
                    "last_name": player_data_from_db.get("last_name"),
                    "initial_elo": elo_per_torneo,
                    # Copia tutti gli altri campi anagrafici dal DB personale
                    **{
                        k: v
                        for k, v in player_data_from_db.items()
                        if k not in ["id", "first_name", "last_name", "initial_elo"]
                    },
                    # Azzera i campi di stato del torneo
                    "points": 0.0,
                    "results_history": [],
                    "opponents": set(),
                    "white_games": 0,
                    "black_games": 0,
                    "last_color": None,
                    "consecutive_white": 0,
                    "consecutive_black": 0,
                    "received_bye_count": 0,
                    "received_bye_in_round": [],
                    "withdrawn": False,
                    "is_scheduled": False,
                }
                players_in_tournament.append(player_instance)
                added_player_ids_to_tournament.add(player_id_to_add)
                play_sound("aggiunta_giocatore", torneo_obj)

                if was_newly_created:
                    print(
                        _(
                            "-> Nuovo giocatore '{first_name} {last_name}' (ID: {player_id}) salvato nel DB e iscritto al torneo."
                        ).format(
                            first_name=player_instance["first_name"],
                            last_name=player_instance["last_name"],
                            player_id=player_id_to_add,
                        )
                    )
                else:
                    print(
                        _(
                            "-> Giocatore '{first_name} {last_name}' (ID: {player_id}) iscritto al torneo."
                        ).format(
                            first_name=player_instance["first_name"],
                            last_name=player_instance["last_name"],
                            player_id=player_id_to_add,
                        )
                    )
    return players_in_tournament


def update_match_result(torneo):
    """
    Gestisce l'interfaccia utente per l'inserimento dei risultati,
    usando una funzione di supporto per l'applicazione dei dati.
    """
    any_changes_made_in_this_session = False
    while True:
        current_round_num = torneo["current_round"]
        if "players_dict" not in torneo or len(torneo["players_dict"]) != len(
            torneo.get("players", [])
        ):
            torneo["players_dict"] = {p["id"]: p for p in torneo.get("players", [])}
        players_dict = torneo["players_dict"]
        current_round_data = next(
            (
                r
                for r in torneo.get("rounds", [])
                if r.get("round") == current_round_num
            ),
            None,
        )
        if not current_round_data:
            print(
                _("ERRORE: Dati turno {round_num} non trovati.").format(
                    round_num=current_round_num
                )
            )
            return False
        pending_matches_info_list = []
        all_matches_in_this_round = current_round_data.get("matches", [])
        all_matches_this_round_sorted = sorted(
            all_matches_in_this_round, key=lambda m: m.get("id", 0)
        )
        round_board_idx_counter = 0
        for match_obj in all_matches_this_round_sorted:
            round_board_idx_counter += 1
            if (
                match_obj.get("result") is None
                and match_obj.get("black_player_id") is not None
            ):
                wp_obj = players_dict.get(match_obj.get("white_player_id"))
                bp_obj = players_dict.get(match_obj.get("black_player_id"))
                wp_name_disp = (
                    f"{wp_obj.get('first_name', 'N/A')} {wp_obj.get('last_name', '')}"
                    if wp_obj
                    else _("Giocatore Mancante")
                )
                bp_name_disp = (
                    f"{bp_obj.get('first_name', 'N/A')} {bp_obj.get('last_name', '')}"
                    if bp_obj
                    else _("Giocatore Mancante")
                )
                pending_matches_info_list.append(
                    (round_board_idx_counter, match_obj, wp_name_disp, bp_name_disp)
                )
        completed_matches_to_cancel = [
            m
            for m in all_matches_this_round_sorted
            if m.get("result") is not None and m.get("result") != "BYE"
        ]
        if not pending_matches_info_list and not completed_matches_to_cancel:
            if not any_changes_made_in_this_session:
                print(
                    _(
                        "Info: Nessuna azione possibile per il turno {round_num} (nessuna partita pendente e nessuna da poter cancellare)."
                    ).format(round_num=current_round_num)
                )
            break

        if pending_matches_info_list:
            planned = []
            unplanned = []
            for item in pending_matches_info_list:
                match_dict_disp = item[1]
                if match_dict_disp.get("is_scheduled", False) and match_dict_disp.get(
                    "schedule_info"
                ):
                    planned.append(item)
                else:
                    unplanned.append(item)

            def sort_planned(item):
                s = item[1].get("schedule_info", {})
                return (s.get("date", ""), s.get("time", ""))

            planned.sort(key=sort_planned)

            print(
                _(
                    "\nPartite del turno {round_num} ancora da registrare (N. Scacchiera del Turno):"
                ).format(round_num=current_round_num)
            )
            if planned:
                print(_("\n  Partite già pianificate, da giocare:"))
                for (
                    displayed_board_num,
                    match_dict_disp,
                    w_name_disp,
                    b_name_disp,
                ) in planned:
                    wp_elo_disp = players_dict.get(
                        match_dict_disp["white_player_id"], {}
                    ).get("initial_elo", "?")
                    bp_elo_disp = players_dict.get(
                        match_dict_disp["black_player_id"], {}
                    ).get("initial_elo", "?")
                    print(
                        _(
                            "    Sc. {board:<2} (IDG:{match_id}) - {white:<20} [{w_elo:>4}] vs {black:<20} [{b_elo:>4}]"
                        ).format(
                            board=displayed_board_num,
                            match_id=match_dict_disp.get("id"),
                            white=w_name_disp,
                            w_elo=wp_elo_disp,
                            black=b_name_disp,
                            b_elo=bp_elo_disp,
                        )
                    )
                    schedule = match_dict_disp.get("schedule_info", {})
                    date_str = (
                        format_date_locale(schedule.get("date"))
                        if schedule.get("date")
                        else "N/D"
                    )
                    time_str = schedule.get("time", "N/O")
                    channel_str = schedule.get("channel", "")
                    arbiter_str = schedule.get("arbiter", "")

                    plan_info = _("      Pianificata per: {date} alle {time}").format(
                        date=date_str, time=time_str
                    )
                    if channel_str:
                        plan_info += f", {channel_str}"
                    if arbiter_str:
                        plan_info += f", {arbiter_str}"

                    print(plan_info)

            if unplanned:
                print(_("\n  Ancora non pianificate:"))
                for (
                    displayed_board_num,
                    match_dict_disp,
                    w_name_disp,
                    b_name_disp,
                ) in unplanned:
                    wp_elo_disp = players_dict.get(
                        match_dict_disp["white_player_id"], {}
                    ).get("initial_elo", "?")
                    bp_elo_disp = players_dict.get(
                        match_dict_disp["black_player_id"], {}
                    ).get("initial_elo", "?")
                    print(
                        _(
                            "    Sc. {board:<2} (IDG:{match_id}) - {white:<20} [{w_elo:>4}] vs {black:<20} [{b_elo:>4}]"
                        ).format(
                            board=displayed_board_num,
                            match_id=match_dict_disp.get("id"),
                            white=w_name_disp,
                            w_elo=wp_elo_disp,
                            black=b_name_disp,
                            b_elo=bp_elo_disp,
                        )
                    )
        else:
            print(
                _(
                    "\nNessuna partita da registrare per il turno {round_num} (ma potresti voler cancellare un risultato)."
                ).format(round_num=current_round_num)
            )

        pending_board_numbers_for_prompt_display = [
            str(match_info_tuple[0]) for match_info_tuple in pending_matches_info_list
        ]
        board_numbers_str_for_prompt = (
            "-".join(pending_board_numbers_for_prompt_display)
            if pending_board_numbers_for_prompt_display
            else _("Nessuna")
        )
        prompt_lines = [
            _("Inserisci:"),
            _("\t[r] per ritirare un giocatore dal torneo;"),
            _("\t[t] Time Machine, per tornare all'inizio di un turno;"),
            _("\t[cancella] per eliminare un risultato inserito;"),
            _("\t[SC] il numero della scacchiera;"),
            _("\t[nom*|cog*] parte del nome o cognome di uno dei giocatori."),
        ]
        prompt_finale = "\n".join(prompt_lines) + _(
            "\nR|T|SC|nome|cognome [{boards}]: "
        ).format(boards=board_numbers_str_for_prompt)
        user_input_str = input(prompt_finale).strip().lower()

        if not user_input_str:
            break
        if user_input_str == "t":
            if time_machine_torneo(torneo):
                any_changes_made_in_this_session = True
                save_tournament(torneo)
                print(_("Stato del torneo ripristinato e salvato."))
            continue
        if user_input_str.lower() == "r":
            print(_("Ritiro Giocatore dal Torneo"))
            active_players_list = [
                p for p in torneo["players"] if not p.get("withdrawn", False)
            ]
            if not active_players_list:
                print(_("Nessun giocatore attivo da ritirare."))
                continue
            for i, p in enumerate(active_players_list):
                print(
                    f"  {i + 1}. {p.get('first_name')} {p.get('last_name')} (ID: {p.get('id')})"
                )
            player_to_withdraw_input = input(
                _(
                    "Inserisci il numero o l'ID del giocatore da ritirare (o vuoto per annullare): "
                )
            ).strip()
            if not player_to_withdraw_input:
                continue
            player_to_withdraw_obj = None
            if player_to_withdraw_input.isdigit() and (
                1 <= int(player_to_withdraw_input) <= len(active_players_list)
            ):
                player_to_withdraw_obj = active_players_list[
                    int(player_to_withdraw_input) - 1
                ]
            else:
                player_to_withdraw_obj = players_dict.get(
                    player_to_withdraw_input.upper()
                )
            if player_to_withdraw_obj and not player_to_withdraw_obj.get(
                "withdrawn", False
            ):
                player_name_withdraw = f"{player_to_withdraw_obj.get('first_name', '?')} {player_to_withdraw_obj.get('last_name', '?')}"
                confirm_prompt = _(
                    "Confermi il ritiro definitivo di {player_name}? (INVIO|ESCAPE)"
                ).format(player_name=player_name_withdraw)
                if enter_escape(confirm_prompt):
                    player_to_withdraw_obj["withdrawn"] = True
                    play_sound("ritiro_giocatore", torneo)
                    print(
                        _("Giocatore {player_name} marcato come ritirato.").format(
                            player_name=player_name_withdraw
                        )
                    )
                    any_changes_made_in_this_session = True
                    save_tournament(torneo)
                else:
                    print(_("Ritiro annullato."))
            else:
                print(_("Giocatore non trovato o già ritirato."))
            continue

        selected_match_obj_for_processing = None
        if user_input_str.lower() == "cancella":
            if not completed_matches_to_cancel:
                print(
                    _("Nessuna partita completata in questo turno da poter cancellare.")
                )
                continue
            print(
                _("\nPartite completate nel turno {round_num} (ID Globali):").format(
                    round_num=current_round_num
                )
            )
            for i, match in enumerate(completed_matches_to_cancel):
                wp_data = players_dict.get(match.get("white_player_id"))
                bp_data = players_dict.get(match.get("black_player_id"))
                w_name = (
                    f"{wp_data.get('first_name', '?')} {wp_data.get('last_name', '?')}"
                    if wp_data
                    else "?"
                )
                b_name = (
                    f"{bp_data.get('first_name', '?')} {bp_data.get('last_name', '?')}"
                    if bp_data
                    else "?"
                )
                print(
                    _(
                        "  {num}. IDG:{match_id} - {white} vs {black} | Risultato: {result}"
                    ).format(
                        num=i + 1,
                        match_id=match.get("id"),
                        white=w_name,
                        black=b_name,
                        result=match.get("result"),
                    )
                )

            cancel_choice = input(
                _(
                    "Inserisci il numero o l'ID Globale (IDG) della partita da cancellare (o vuoto per annullare): "
                )
            ).strip()
            if not cancel_choice:
                continue

            match_to_cancel = None
            if cancel_choice.isdigit():
                choice_num = int(cancel_choice)
                if 1 <= choice_num <= len(completed_matches_to_cancel):
                    match_to_cancel = completed_matches_to_cancel[choice_num - 1]
                else:
                    match_to_cancel = next(
                        (
                            m
                            for m in completed_matches_to_cancel
                            if m.get("id") == choice_num
                        ),
                        None,
                    )

            if not match_to_cancel:
                print(_("Scelta non valida."))
                continue

            wp_data_c = players_dict.get(match_to_cancel.get("white_player_id"))
            bp_data_c = players_dict.get(match_to_cancel.get("black_player_id"))

            w_name_c = (
                f"{wp_data_c.get('first_name', '?')} {wp_data_c.get('last_name', '?')}"
                if wp_data_c
                else "?"
            )
            b_name_c = (
                f"{bp_data_c.get('first_name', '?')} {bp_data_c.get('last_name', '?')}"
                if bp_data_c
                else "?"
            )

            if enter_escape(
                _(
                    "Confermi la CANCELLAZIONE del risultato per {w} vs {b}? (INVIO|ESCAPE): "
                ).format(w=w_name_c, b=b_name_c)
            ):
                # Reset partita
                match_to_cancel["result"] = None
                match_to_cancel.pop("white_score", None)
                match_to_cancel.pop("black_score", None)

                # Rimuovi da results_history
                if wp_data_c and "results_history" in wp_data_c:
                    wp_data_c["results_history"] = [
                        res
                        for res in wp_data_c["results_history"]
                        if res.get("round") != current_round_num
                    ]
                if bp_data_c and "results_history" in bp_data_c:
                    bp_data_c["results_history"] = [
                        res
                        for res in bp_data_c["results_history"]
                        if res.get("round") != current_round_num
                    ]

                from tournament import ricalcola_punti_tutti_giocatori

                ricalcola_punti_tutti_giocatori(torneo)
                any_changes_made_in_this_session = True
                save_tournament(torneo)
                play_sound("cancellato", torneo)
                print(_("Risultato cancellato e punteggi ricalcolati."))
            else:
                print(_("Cancellazione annullata."))
            continue
        if user_input_str.isdigit():
            try:
                board_num_choice = int(user_input_str)
                match_found_by_board = False
                for (
                    displayed_b_num,
                    match_obj_dict,
                    u1,
                    u2,
                ) in pending_matches_info_list:
                    if displayed_b_num == board_num_choice:
                        selected_match_obj_for_processing = match_obj_dict
                        match_found_by_board = True
                        break
                if not match_found_by_board:
                    print(
                        _(
                            "Numero Scacchiera (del turno) '{board_num_choice}' non valido o partita non pendente."
                        ).format(board_num_choice=board_num_choice)
                    )
                    continue
            except ValueError:
                print(_("Input numerico per Scacchiera non valido."))
                continue
        else:
            search_term_lower = user_input_str.lower()
            candidate_matches_info = []
            for disp_b_num, match_o, wp_n, bp_n in pending_matches_info_list:
                if (search_term_lower in wp_n.lower()) or (
                    search_term_lower in bp_n.lower()
                ):
                    candidate_matches_info.append((disp_b_num, match_o, wp_n, bp_n))
            if not candidate_matches_info:
                print(
                    _(
                        "Nessuna partita pendente trovata con giocatori che corrispondono a '{search_term}'."
                    ).format(search_term=user_input_str)
                )
                continue
            if len(candidate_matches_info) == 1:
                selected_match_obj_for_processing = candidate_matches_info[0][1]
                sel_board_disp, u1, sel_w_disp, sel_b_disp = candidate_matches_info[0]
                print(
                    _(
                        "Trovata partita unica (Sc. {board_num}): {white_player} vs {black_player}"
                    ).format(
                        board_num=sel_board_disp,
                        white_player=sel_w_disp,
                        black_player=sel_b_disp,
                    )
                )
            else:
                print(
                    _(
                        "Trovate {num_matches} partite pendenti per '{search_term}':"
                    ).format(
                        num_matches=len(candidate_matches_info),
                        search_term=user_input_str,
                    )
                )
                for (
                    disp_b_num_multi,
                    match_d_multi,
                    w_n_multi,
                    b_n_multi,
                ) in candidate_matches_info:
                    wp_elo_m_disp = players_dict.get(
                        match_d_multi["white_player_id"], {}
                    ).get("initial_elo", "?")
                    bp_elo_m_disp = players_dict.get(
                        match_d_multi["black_player_id"], {}
                    ).get("initial_elo", "?")
                    print(
                        _(
                            "  Sc. {board:<2} (IDG:{match_id}) - {white:<20} [{w_elo:>4}] vs {black:<20} [{b_elo:>4}]"
                        ).format(
                            board=disp_b_num_multi,
                            match_id=match_d_multi.get("id"),
                            white=w_n_multi,
                            w_elo=wp_elo_m_disp,
                            black=b_n_multi,
                            b_elo=bp_elo_m_disp,
                        )
                    )
                try:
                    specific_board_input = input(
                        _(
                            "Inserisci il N.Scacchiera (del turno) desiderato dalla lista sopra: "
                        )
                    ).strip()
                    if not specific_board_input.isdigit():
                        print(_("Input non numerico per la scacchiera."))
                        continue
                    specific_board_choice = int(specific_board_input)
                    for (
                        disp_b_num_cand,
                        match_obj_cand,
                        u1,
                        u2,
                    ) in candidate_matches_info:
                        if disp_b_num_cand == specific_board_choice:
                            selected_match_obj_for_processing = match_obj_cand
                            break
                    if not selected_match_obj_for_processing:
                        print(
                            _(
                                "N.Scacchiera '{board_choice}' non valido dalla lista filtrata."
                            ).format(board_choice=specific_board_choice)
                        )
                        continue
                except ValueError:
                    print(_("Input Scacchiera non valido."))
                    continue
        if selected_match_obj_for_processing:
            wp_data_obj = players_dict.get(
                selected_match_obj_for_processing["white_player_id"]
            )
            bp_data_obj = players_dict.get(
                selected_match_obj_for_processing["black_player_id"]
            )
            wp_name_match_disp = f"{wp_data_obj.get('first_name', '?')} {wp_data_obj.get('last_name', '?')}"
            bp_name_match_disp = f"{bp_data_obj.get('first_name', '?')} {bp_data_obj.get('last_name', '?')}"
            sel_msg = _(
                "Partita selezionata per risultato: {white} vs {black} (ID Glob: {match_id})"
            )
            print(
                sel_msg.format(
                    white=wp_name_match_disp,
                    black=bp_name_match_disp,
                    match_id=selected_match_obj_for_processing["id"],
                )
            )
            result_input = (
                input(
                    _("Risultati: [1-0, 0-1, 1/2, 0-0F, 1-F, F-1, p per pianificare]: ")
                )
                .strip()
                .upper()
            )

            if result_input == "P":
                is_currently_scheduled = selected_match_obj_for_processing.get(
                    "is_scheduled", False
                )
                if is_currently_scheduled:
                    sub_action = (
                        key(
                            _(
                                "Questa partita è già pianificata. Vuoi (M)odificare o (R)imuovere la pianificazione? (Invio per annullare): "
                            )
                        )
                        .strip()
                        .lower()
                    )
                    if sub_action == "m":
                        updated_schedule_data = input_schedule_details(
                            existing_details=selected_match_obj_for_processing.get(
                                "schedule_info"
                            )
                        )
                        if updated_schedule_data:
                            selected_match_obj_for_processing["schedule_info"] = (
                                updated_schedule_data
                            )
                            any_changes_made_in_this_session = True
                            save_tournament(torneo)
                            play_sound("pianifica_modifica", torneo)
                            print(_("Pianificazione modificata."))
                    elif sub_action == "r":
                        if enter_escape(
                            _("Confermi rimozione pianificazione? (INVIO|ESCAPE)")
                        ):
                            selected_match_obj_for_processing["is_scheduled"] = False
                            if "schedule_info" in selected_match_obj_for_processing:
                                del selected_match_obj_for_processing["schedule_info"]
                            any_changes_made_in_this_session = True
                            save_tournament(torneo)
                            play_sound("pianifica_rimuovi", torneo)
                            print(_("Pianificazione rimossa."))
                else:
                    new_schedule_data = input_schedule_details()
                    if new_schedule_data:
                        selected_match_obj_for_processing["schedule_info"] = (
                            new_schedule_data
                        )
                        selected_match_obj_for_processing["is_scheduled"] = True
                        any_changes_made_in_this_session = True
                        save_tournament(torneo)
                        play_sound("pianifica_crea", torneo)
                        print(_("Partita pianificata con successo."))
                continue

            result_map = {
                "1-0": ("1-0", 1.0, 0.0),
                "10": ("1-0", 1.0, 0.0),
                "0-1": ("0-1", 0.0, 1.0),
                "01": ("0-1", 0.0, 1.0),
                "1/2": ("1/2-1/2", 0.5, 0.5),
                "12": ("1/2-1/2", 0.5, 0.5),
                "7": ("1/2-1/2", 0.5, 0.5),
                "1-F": ("1-F", 1.0, 0.0),
                "1F": ("1-F", 1.0, 0.0),
                "F-1": ("F-1", 0.0, 1.0),
                "F1": ("F-1", 0.0, 1.0),
                "0-0F": ("0-0F", 0.0, 0.0),
                "00F": ("0-0F", 0.0, 0.0),
            }
            if result_input in result_map:
                res_str, w_score, b_score = result_map[result_input]
                confirm_message_str = _("Confermi risultato?")
                if res_str == "1-0":
                    confirm_message_str = _(
                        "Confermi che {winner} vince contro {loser}? (INVIO|ESCAPE): "
                    ).format(winner=wp_name_match_disp, loser=bp_name_match_disp)
                elif res_str == "0-1":
                    confirm_message_str = _(
                        "Confermi che {winner} vince contro {loser}? (INVIO|ESCAPE): "
                    ).format(winner=bp_name_match_disp, loser=wp_name_match_disp)
                elif res_str == "1/2-1/2":
                    confirm_message_str = _(
                        "Confermi che {player1} e {player2} pattano? (INVIO|ESCAPE): "
                    ).format(player1=wp_name_match_disp, player2=bp_name_match_disp)
                elif res_str == "1-F":
                    confirm_message_str = _(
                        "Confermi che {winner} vince per forfait contro {loser}? (INVIO|ESCAPE): "
                    ).format(winner=wp_name_match_disp, loser=bp_name_match_disp)
                elif res_str == "F-1":
                    confirm_message_str = _(
                        "Confermi che {winner} vince per forfait contro {loser}? (INVIO|ESCAPE): "
                    ).format(winner=bp_name_match_disp, loser=wp_name_match_disp)
                elif res_str == "0-0F":
                    confirm_message_str = _(
                        "Confermi doppio forfait tra {player1} e {player2}? (INVIO|ESCAPE): "
                    ).format(player1=wp_name_match_disp, player2=bp_name_match_disp)
                user_confirm_input = enter_escape(confirm_message_str)
                if user_confirm_input:
                    _apply_match_result_to_players(
                        torneo,
                        selected_match_obj_for_processing,
                        res_str,
                        w_score,
                        b_score,
                    )
                    any_changes_made_in_this_session = True
                    save_tournament(torneo)
                    play_sound(f"risultato_{res_str}", torneo)
                    if "F" in res_str:
                        forfeiting_players = []
                        if res_str == "1-F":
                            forfeiting_players.append(bp_data_obj)
                        elif res_str == "F-1":
                            forfeiting_players.append(wp_data_obj)
                        elif res_str == "0-0F":
                            forfeiting_players.extend([wp_data_obj, bp_data_obj])

                        for f_player_obj in forfeiting_players:
                            player_name_forfeit = f"{f_player_obj.get('first_name', '?')} {f_player_obj.get('last_name', '?')}"
                            withdraw_choice = enter_escape(
                                _(
                                    "Il giocatore {player_name} si ritira definitivamente dal torneo? (INVIO|ESCAPE)"
                                ).format(player_name=player_name_forfeit)
                            )
                            if withdraw_choice:
                                f_player_obj["withdrawn"] = True
                                play_sound("ritiro_giocatore", torneo)
                                print(
                                    _(
                                        "Giocatore {player_name} marcato come ritirato."
                                    ).format(player_name=player_name_forfeit)
                                )
                else:
                    print(_("Operazione annullata dall'utente."))
            else:
                play_sound("errore", torneo)
                print(_("Input risultato non valido."))
    return any_changes_made_in_this_session


def cartella_di_lavoro_esterna(custom_path):
    """
    Dice se la cartella di lavoro del torneo e' davvero un'altra cartella
    rispetto a quella dell'applicazione.
    Serve all'archiviazione: i file del torneo concluso restano al loro posto
    solo quando l'arbitro ha scelto una cartella esterna, altrimenti vanno
    spostati in archivio invece di essere lasciati accanto al programma.
    """
    if not custom_path:
        return False
    try:
        cartella_applicazione = os.path.abspath(user_data_path(""))
        return os.path.abspath(custom_path) != cartella_applicazione
    except (OSError, ValueError):
        # Percorso non risolvibile: meglio conservare gli originali che
        # rischiare di cancellarli.
        return True


def _stesso_file(primo, secondo):
    """Vero se i due percorsi portano allo stesso file sul disco."""
    try:
        return os.path.exists(secondo) and os.path.samefile(primo, secondo)
    except OSError:
        return False


def _copia_verificata(origine, destinazione, avvisa):
    """Copia un file del torneo concluso, il json o un report, in
    destinazione, in archivio o nella cartella di lavoro esterna, e rilegge
    la copia.
    Restituisce vero solo se alla fine la destinazione ha gli stessi byte
    dell'origine. Un file diverso che c'era gia' passa prima da una copia di
    sicurezza, e se quella non riesce resta com'e'. Fino alla 10.8.8 un file
    gia' presente non veniva sostituito e il json del torneo veniva cancellato
    lo stesso: una seconda finalizzazione lasciava in archivio il file della
    prima e perdeva quello giusto. avvisa riceve le frasi per l'utente.
    """
    nome = os.path.basename(destinazione)
    cartella = os.path.dirname(destinazione)
    if os.path.exists(destinazione):
        if _stessi_byte(origine, destinazione):
            return True
        if not create_backup(destinazione, "pre_archiviazione"):
            avvisa(
                _(
                    "Il file {name} in {path} non è stato sostituito: la copia di sicurezza del file che c'era non è riuscita."
                ).format(name=nome, path=cartella)
            )
            return False
        avvisa(
            _(
                "In {path} c'era già un file {name}: prima di sostituirlo ne è stata fatta una copia di sicurezza, nella cartella backup."
            ).format(name=nome, path=cartella)
        )
    try:
        shutil.copy2(origine, destinazione)
    except OSError as errore:
        avvisa(
            _("Copia di {name} in {path} non riuscita: {error}").format(
                name=nome, path=cartella, error=errore
            )
        )
        return False
    if not _stessi_byte(origine, destinazione):
        avvisa(
            _(
                "La copia di {name} in {path}, riletta, non è uguale all'originale."
            ).format(name=nome, path=cartella)
        )
        return False
    return True


def _metti_da_parte(percorso, avvisa):
    """Porta un file nella cartella backup, con rifinalizzazione nel nome, e
    lo toglie dal suo posto solo dopo aver riletto la copia. Serve ai file
    di una finalizzazione ripetuta che non entrano in archivio. Se la copia
    non torna il file resta dov'e', e avvisa lo dice."""
    copia = copia_di_sicurezza(percorso, "rifinalizzazione")
    if copia and _stessi_byte(percorso, copia):
        try:
            os.remove(percorso)
            return True
        except OSError as errore:
            avvisa(
                _("Il file {name} non si è potuto togliere da {path}: {error}").format(
                    name=os.path.basename(percorso),
                    path=os.path.dirname(percorso),
                    error=errore,
                )
            )
            return False
    avvisa(
        _(
            "Il file {name} resta in {path}: la sua copia nella cartella backup non è riuscita."
        ).format(name=os.path.basename(percorso), path=os.path.dirname(percorso))
    )
    return False


def _leggi_json_del_torneo(percorso):
    """Il contenuto di un json di torneo come dizionario, o None se il file
    non si legge o non contiene un dizionario."""
    try:
        with open(percorso, encoding="utf-8") as f:
            dati = json.load(f)
    except (OSError, ValueError):
        return None
    return dati if isinstance(dati, dict) else None


def _cartella_d_archivio(cartella_del_mese, nome_cartella, nome_json, identita):
    """La cartella d'archivio del torneo dentro quella del mese: la cartella
    con il suo nome, se non contiene il json di un altro torneo; altrimenti
    la stessa seguita dalla data di inizio, e poi da _2, _3.
    Due edizioni con lo stesso nome concluse nello stesso mese finivano nella
    stessa cartella, e il json della seconda prendeva il posto di quello
    della prima, che spariva dai tornei conclusi. Un json che non si legge
    conta come quello di un altro torneo: meglio una cartella in piu' che
    sostituire un file di cui non si sa niente."""

    def adatta(cartella):
        json_presente = os.path.join(cartella, nome_json)
        if not os.path.exists(json_presente):
            return True
        dati = _leggi_json_del_torneo(json_presente)
        return dati is not None and _identita_del_torneo(dati) == identita

    base = os.path.join(cartella_del_mese, nome_cartella)
    if adatta(base):
        return base
    inizio = identita[1]
    if inizio:
        base = f"{base}_{inizio}"
        if adatta(base):
            return base
    numero = 2
    while not adatta(f"{base}_{numero}"):
        numero += 1
    return f"{base}_{numero}"


def finalize_tournament(torneo, players_db, current_tournament_filename, avvisi=None):
    """
    Completa il torneo: calcola Elo/Performance/Spareggi, aggiorna DB giocatori,
    e archivia tutti i file del torneo in una sottocartella dedicata.
    Restituisce True se la finalizzazione (inclusa l'archiviazione) ha avuto successo, False altrimenti.
    Dalla 10.8.9 e' False anche quando il database e' aggiornato ma il json
    del torneo non ha raggiunto l'archivio: prima la finestra annunciava il
    torneo concluso e archiviato, e il file restava nella radice, nascosto
    dall'albero perche' concluso.
    avvisi, se c'e', e' una lista che riceve le frasi da mostrare all'utente,
    le stesse che vengono stampate: la finestra non vede la console, e senza
    di loro non saprebbe dei giocatori lasciati come erano o del file del
    torneo rimasto al suo posto.
    """
    if avvisi is None:
        avvisi = []

    def avvisa(frase):
        print(frase)
        avvisi.append(frase)

    tournament_name_original = torneo.get("name")
    if not tournament_name_original:
        avvisa(
            _(
                "ERRORE CRITICO: Nome del torneo non presente nell'oggetto torneo. Impossibile finalizzare."
            )
        )
        return False
    # Un database dei giocatori che c'e' ma non si e' potuto leggere arriva
    # vuoto: tutti gli iscritti risulterebbero mancanti, la fase 5 li
    # creerebbe e il salvataggio lascerebbe sul disco un database con i soli
    # iscritti del torneo. La finalizzazione non parte, e niente cambia: il
    # torneo resta da concludere (10.13.16).
    if database_non_letto(players_db):
        avvisa(messaggio_database_non_letto(players_db))
        avvisa(
            _(
                "La finalizzazione non parte: il torneo resta da concludere, e il database dei giocatori e l'archivio restano come sono."
            )
        )
        return False
    print(_("Finalizzazione Torneo: {name}").format(name=tournament_name_original))
    sanitized_tournament_name = sanitize_filename(tournament_name_original)
    # Il torneo concluso si salva nel file da cui e' stato aperto. Fino alla
    # 10.8.8 si salvava sempre nella radice: con un torneo aperto da un'altra
    # cartella, in archivio andava il file aperto, ancora da concludere, e
    # nella radice nasceva un json concluso che l'albero non mostrava, sopra
    # un eventuale torneo con lo stesso nome.
    percorso_del_torneo = current_tournament_filename or user_data_path(
        f"Tornello - {sanitized_tournament_name}.json"
    )

    # --- Creazione backup pre-finalizzazione ---
    print(_("Creazione backup di sicurezza prima dell'archiviazione..."))
    backup_db_ok = create_backup(PLAYER_DB_FILE, "pre_finalize_db")
    backup_torneo_ok = True
    if current_tournament_filename and os.path.exists(current_tournament_filename):
        backup_torneo_ok = create_backup(
            current_tournament_filename, "pre_finalize_torneo"
        )

    if not backup_db_ok or not backup_torneo_ok:
        avvisa(
            _(
                "ATTENZIONE: Fallita la creazione di uno o più file di backup. Procedo ugualmente..."
            )
        )
    else:
        print(_("Backup di sicurezza creati con successo."))

    if "players_dict" not in torneo or len(torneo["players_dict"]) != len(
        torneo.get("players", [])
    ):
        torneo["players_dict"] = {p["id"]: p for p in torneo.get("players", [])}
    num_players = len(torneo.get("players", []))
    if num_players == 0:
        avvisa(_("Nessun giocatore nel torneo, impossibile finalizzare."))
        return False
    # --- Fase 1: Determina K-Factor e conta partite giocate nel torneo ---
    print(_("Accesso al DB e calcolo K-Factor e partite giocate..."))
    tournament_start_date = torneo.get("start_date")
    for p in torneo.get("players", []):
        player_id = p.get("id")
        if not player_id or p.get("withdrawn", False):
            p["k_factor"] = None
            p["games_this_tournament"] = 0
            continue
        # Il K viene dalla scheda del database, oppure, per chi il database
        # non ha, dalla scheda che la fase 5 creera' per lui con i dati del
        # torneo (10.13.16). Fino alla 10.13.15 per lui valeva il K di
        # ripiego, 20, e la fase 5 lo saltava. La classifica in corso passa
        # dalla stessa funzione, cosi' la sua colonna Elo Var. e' quella che
        # la finalizzazione applica (10.13.17).
        p["k_factor"] = fattore_k_della_finalizzazione(
            p, players_db, tournament_start_date
        )
        games_count = 0
        for result_entry in p.get("results_history", []):
            if (
                result_entry.get("opponent_id")
                and result_entry.get("opponent_id") != "BYE_PLAYER_ID"
                and result_entry.get("score") is not None
            ):
                # Considera anche di escludere i forfeit "0-0F" se necessario
                # if result_entry.get("result") != "0-0F":
                games_count += 1
        p["games_this_tournament"] = games_count
    # --- Fase 2: Calcola Spareggi, Performance, Elo Change ---
    print(_("Ricalcolo finale Buchholz, ARO, Performance Rating, Variazione Elo..."))
    players_dict_for_calculations = torneo[
        "players_dict"
    ]  # Usiamo il dizionario per coerenza
    for p in torneo.get("players", []):
        p_id = p.get("id")
        if not p_id or p.get("withdrawn", False):
            p["buchholz"] = 0.0
            p["buchholz_cut1"] = None  # O 0.0 se preferisci non avere None
            p["aro"] = None
            p["performance_rating"] = None
            p["elo_change"] = None
            continue

        p["buchholz"] = compute_buchholz(p_id, torneo)
        p["buchholz_cut1"] = compute_buchholz_cut1(p_id, torneo)
        p["aro"] = compute_aro(p_id, torneo)
        p["performance_rating"] = calculate_performance_rating(
            p, players_dict_for_calculations
        )
        p["elo_change"] = calculate_elo_change(
            p, players_dict_for_calculations
        )  # Usa K da p['k_factor']

    # --- Fase 3: Ordinamento Finale e Assegnazione Rank ---
    print(_("Ordinamento classifica finale..."))

    # I criteri di spareggio configurati dall'arbitro, gli stessi che usa la
    # classifica mostrata durante il torneo. Prima qui c'era una sequenza fissa
    # scritta nel codice, Buchholz Cut-1, Buchholz, performance ed Elo, che
    # ignorava la configurazione: il piazzamento assegnato non corrispondeva
    # all'ordine con cui la classifica veniva poi stampata, e nel report finale
    # le posizioni comparivano fuori sequenza. Rilievo D1.
    from reports import get_criterion_value
    from tiebreak_criteria import get_default_tiebreaks, migrate_old_tiebreaks

    raw_tiebreaks = torneo.get("tiebreaks", None)
    if raw_tiebreaks is None:
        tiebreak_order_final = get_default_tiebreaks()
    elif raw_tiebreaks and isinstance(raw_tiebreaks[0], str):
        tiebreak_order_final = migrate_old_tiebreaks(raw_tiebreaks)
    else:
        tiebreak_order_final = raw_tiebreaks

    def sort_key_final(player):
        try:
            points = float(player.get("points", 0.0))
        except (ValueError, TypeError):
            points = 0.0
        status_val = (
            1 if not player.get("withdrawn", False) else 0
        )  # 1 per attivo, 0 per ritirato
        chiave = [-points, -status_val]
        for criterio in tiebreak_order_final:
            chiave.append(-get_criterion_value(player, criterio, torneo))
        return tuple(chiave)

    # Resta None se l'ordinamento si ferma prima del salvataggio.
    torneo_salvato = None
    try:
        players_sorted = sorted(torneo.get("players", []), key=sort_key_final)
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
        # I valori delle colonne di spareggio, come li mostra la classifica,
        # restano salvati nel giocatore: la classifica di un torneo concluso
        # li rilegge da qui invece di ricalcolarli con le regole di oggi
        # (decisione di Gabriele, 10.13.19). Fino alla 10.13.18 restavano
        # soltanto Buchholz, Buchholz Cut-1 e ARO.
        from reports import valori_degli_spareggi

        for p_item in players_sorted:
            if p_item.get("withdrawn", False):
                p_item.pop("final_tiebreaks", None)
            else:
                p_item["final_tiebreaks"] = valori_degli_spareggi(
                    p_item, torneo, tiebreak_order_final
                )
        torneo["players"] = players_sorted
        # Segna il torneo come concluso e salva lo stato su file prima di archiviarlo
        torneo["concluded"] = True
        torneo_salvato = save_tournament(torneo, filepath=percorso_del_torneo)
    except Exception as e_sort:
        print(
            _(
                "Errore durante l'ordinamento dei giocatori per la classifica: {error}"
            ).format(error=e_sort)
        )
        traceback.print_exc()
        # Non interrompere la finalizzazione, ma la classifica potrebbe non essere ordinata.

    # Senza il file salvato ci si ferma prima di toccare il database e
    # l'archivio. Fino alla 10.8.8 si andava avanti: in archivio finiva il
    # file di prima, ancora da concludere, "verificato" contro se stesso, e
    # il json attivo veniva tolto. Il torneo in memoria torna da concludere,
    # cosi' la finestra permette di riprovare.
    if torneo_salvato is False:
        torneo["concluded"] = False
        avvisa(
            _(
                "Il file del torneo non si è potuto salvare in {path}: la finalizzazione si ferma qui, e il database dei giocatori e l'archivio restano come erano. Il motivo più comune è un file tenuto bloccato da un altro programma, per esempio Dropbox o l'antivirus: riprova la finalizzazione più tardi."
            ).format(path=percorso_del_torneo)
        )
        return False

    # --- Fase 4: Salva Classifica Finale TXT (nella directory corrente, prima dell'archiviazione) ---
    print(_("Salvataggio classifica finale su file di testo..."))
    save_standings_text(torneo, final=True)

    # --- Fase 5: Aggiornamento Database Giocatori ---
    print(_("Aggiornamento Database Giocatori (Elo, partite, storico tornei)..."))
    db_updated_count = 0
    # Il torneo si riconosce nello storico dall'identificativo e dalla data di
    # inizio. L'identificativo da solo non basta: la finestra lo ricava dal
    # nome, e due edizioni con lo stesso nome avrebbero lo stesso. Un
    # identificativo vuoto, come nei file che non lo hanno mai avuto, lascia
    # il posto al nome, e _voce_di_questo_torneo riconosce anche le voci
    # scritte senza identificativo.
    id_nello_storico, inizio_nello_storico = _identita_del_torneo(torneo)
    gia_registrati = []
    # Le schede come erano prima di questa finalizzazione, per rimetterle in
    # memoria se il database non si salva: la console tiene il suo database
    # aperto, e alla finalizzazione successiva le voci di storico rimaste in
    # memoria farebbero passare i giocatori per gia' aggiornati.
    schede_di_prima = {}
    # La cadenza del torneo, letta come la legge l'Elo di partenza, e il
    # campo dell'Elo che riceve la variazione (decisione di Gabriele come
    # arbitro, 10.13.4).
    categoria = torneo.get("tournament_category", "standard")
    campo_elo = campo_elo_della_cadenza(categoria)
    # I giocatori che il database non aveva, creati da questa finalizzazione,
    # e i loro nomi per gli avvisi.
    creati = []
    nomi_creati = []
    # Gli iscritti trovati nel database con lo stesso identificativo FIDE ma
    # con un altro identificativo, per gli avvisi.
    trovati_per_fide = []
    for p_final_data in torneo.get("players", []):
        player_id = p_final_data.get("id")
        if not player_id:
            continue
        nome_completo = " ".join(
            parte
            for parte in (
                p_final_data.get("first_name", ""),
                p_final_data.get("last_name", ""),
            )
            if parte
        )

        # La scheda del giocatore: quella con il suo identificativo, oppure
        # quella con il suo identificativo FIDE, che la finalizzazione usa
        # invece di crearne un doppione. Succede agli iscritti FIDE_<id> che
        # la finestra metteva nel torneo senza scheda fino alla 10.13.14, se
        # nel frattempo sono entrati nel database con Ctrl+K o con
        # l'iscrizione FIDE a un altro torneo. La voce dello storico si
        # ricorda allora l'identificativo del torneo, id_nel_torneo, per la
        # riapertura (10.13.16).
        scheda_trovata = scheda_nel_database(p_final_data, players_db)
        # Chi il database non ha nasce qui, con i dati che il torneo ha gia'
        # di lui, e riceve Elo, partite, storico e medaglia come gli altri
        # (decisione di Gabriele, 10.13.16). Fino alla 10.13.15 veniva
        # saltato in silenzio, com'e' successo a due iscritti di Autunneo2
        # venuti dalla ricerca FIDE. La sua voce dello storico lo ricorda,
        # con created_by_finalization, e la riapertura del torneo dalle
        # copie di sicurezza lo toglie di nuovo dal database.
        creato = scheda_trovata is None
        if creato:
            db_id = player_id
            players_db[db_id] = scheda_dal_torneo(p_final_data)
            creati.append(db_id)
            nomi_creati.append(nome_completo or player_id)
        elif player_id in players_db:
            db_id = player_id
        else:
            db_id = next(
                chiave
                for chiave, scheda in players_db.items()
                if scheda is scheda_trovata
            )

        if db_id in players_db:
            db_player_record = players_db[db_id]
            scheda_di_prima = copy.deepcopy(db_player_record)
            if "tournaments_played" not in db_player_record:
                db_player_record["tournaments_played"] = []
            # Se il torneo e' gia' nello storico, questa finalizzazione ha
            # gia' scritto tutto del giocatore, e lui resta com'e'. Fino alla
            # 10.8.7 la guardia valeva solo per storico e medaglie: una
            # seconda finalizzazione, per esempio di un torneo rimesso in uso
            # da una copia di sicurezza, sommava di nuovo Elo e partite.
            if any(
                _voce_di_questo_torneo(
                    t, id_nello_storico, tournament_name_original, inizio_nello_storico
                )
                for t in db_player_record["tournaments_played"]
            ):
                gia_registrati.append(nome_completo or player_id)
                continue
            # Chi e' appena nato non ha una scheda di prima: se il database
            # non si salva, esce dalla memoria (vedi sotto).
            if not creato:
                schede_di_prima[db_id] = scheda_di_prima
            if db_id != player_id:
                trovati_per_fide.append((nome_completo or player_id, player_id, db_id))
            elo_change_from_tournament = p_final_data.get("elo_change")
            games_played_in_tournament = p_final_data.get("games_this_tournament", 0)

            # La variazione va sull'Elo della cadenza del torneo, quello da
            # cui viene l'Elo di partenza: current_elo negli standard,
            # elo_rapid nei rapid, elo_blitz nei blitz. Fino alla 10.13.3
            # andava sempre su current_elo; la base, per chi non ha l'Elo
            # della cadenza, e' in elo_a_cui_sommare_la_variazione.
            # La voce dello storico si ricorda il campo, il valore di prima,
            # se il campo c'era, e quello scritto: lo storno della riapertura
            # (copie_di_sicurezza) toglie la variazione dallo stesso campo e
            # rimette il valore di prima anche senza la copia pre_finalize_db.
            # Una voce senza elo_field e' di una finalizzazione fino alla
            # 10.13.3, che la variazione la metteva su current_elo, oppure di
            # un giocatore senza variazione: un ritirato, o chi resta senza
            # l'Elo della cadenza, qui sotto.
            elo_nello_storico = {}
            # Nei rapid e nei blitz l'Elo della cadenza nasce solo con almeno
            # una partita valida per l'Elo, scelta come la sceglie il calcolo
            # della variazione: non un bye, non un forfait (decisione di
            # Gabriele come arbitro, 10.13.7). Chi non lo ha, perche' manca o
            # vale zero, e nel torneo non ha nessuna partita cosi', ha la
            # variazione zero e non lo riceve: il campo resta com'era, e la
            # sua voce dello storico non registra variazione. Nella 10.13.4
            # l'Elo della cadenza gli nasceva uguale all'Elo di partenza.
            resta_senza_elo_della_cadenza = (
                campo_elo != "current_elo"
                and not db_player_record.get(campo_elo)
                and not partite_valide_per_elo(p_final_data, torneo["players_dict"])
            )
            if elo_change_from_tournament is not None and not resta_senza_elo_della_cadenza:
                elo_nello_storico["elo_field"] = campo_elo
                if campo_elo in db_player_record:
                    elo_nello_storico["elo_before"] = db_player_record[campo_elo]
                db_player_record[campo_elo] = (
                    elo_a_cui_sommare_la_variazione(db_player_record, categoria)
                    + elo_change_from_tournament
                )
                elo_nello_storico["elo_after"] = db_player_record[campo_elo]

            db_player_record["games_played"] = (
                db_player_record.get("games_played", 0) + games_played_in_tournament
            )

            tournament_history_entry = {
                "tournament_name": tournament_name_original,
                "tournament_id": id_nello_storico,
                "rank": p_final_data.get("final_rank", "N/A"),
                "total_players": num_players,
                "date_started": inizio_nello_storico,
                "date_completed": torneo.get(
                    "end_date", datetime.now().strftime(DATE_FORMAT_ISO)
                ),
                **elo_nello_storico,
            }
            if creato:
                tournament_history_entry["created_by_finalization"] = True
            if db_id != player_id:
                tournament_history_entry["id_nel_torneo"] = player_id
            db_player_record["tournaments_played"].append(tournament_history_entry)

            player_final_rank = p_final_data.get("final_rank")
            if isinstance(player_final_rank, int) and player_final_rank in [
                1,
                2,
                3,
                4,
            ]:
                if "medals" not in db_player_record:
                    db_player_record["medals"] = {
                        "gold": 0,
                        "silver": 0,
                        "bronze": 0,
                        "wood": 0,
                    }
                # Assicura tutte le chiavi medaglia per sicurezza
                for medal_key_init in ["gold", "silver", "bronze", "wood"]:
                    db_player_record["medals"].setdefault(medal_key_init, 0)

                medal_map = {1: "gold", 2: "silver", 3: "bronze", 4: "wood"}
                medal_type_to_add = medal_map.get(player_final_rank)
                if medal_type_to_add:
                    db_player_record["medals"][medal_type_to_add] += 1
            db_updated_count += 1

    if gia_registrati:
        avvisa(
            _(
                "Giocatori che avevano già questo torneo nello storico: {count}. Elo, partite giocate, storico e medaglie restano come erano per: {names}."
            ).format(count=len(gia_registrati), names=", ".join(gia_registrati))
        )
    if db_updated_count > 0:
        # Salva sia JSON che TXT del DB giocatori. Se il JSON non si scrive ci
        # si ferma: fino alla 10.8.8 la finalizzazione andava avanti, toglieva
        # il json attivo e diceva i giocatori aggiornati, mentre il database
        # sul disco era quello di prima. Adesso tutto torna com'era prima
        # della finalizzazione, schede in memoria e torneo da concludere, e
        # si puo' riprovare.
        if not save_players_db(players_db):
            players_db.update(schede_di_prima)
            for player_id in creati:
                players_db.pop(player_id, None)
            torneo["concluded"] = False
            avvisa(
                _(
                    "Il database dei giocatori non si è potuto salvare: Elo, partite giocate, storico e medaglie restano come erano, il torneo torna da concludere e non viene archiviato. Il motivo più comune è un file tenuto bloccato da un altro programma, per esempio Dropbox o l'antivirus: riprova la finalizzazione più tardi."
                )
            )
            if not save_tournament(torneo, filepath=percorso_del_torneo):
                avvisa(
                    _(
                        "Anche il file del torneo, in {path}, non si è potuto riportare allo stato di prima: sul disco risulta concluso, anche se il database non ha ricevuto niente."
                    ).format(path=percorso_del_torneo)
                )
            return False
        print(
            _("Database Giocatori aggiornato per {count} giocatori e salvato.").format(
                count=db_updated_count
            )
        )
        # Chi e' nato nel database lo dicono gli avvisi, dopo il salvataggio
        # riuscito (10.13.16).
        if len(creati) == 1:
            avvisa(
                _(
                    "Un giocatore non era nel database dei giocatori: {names}. La finalizzazione lo ha creato con i dati che aveva nel torneo, e gli ha dato Elo, partite giocate, storico e medaglia come agli altri."
                ).format(names=nomi_creati[0])
            )
        elif creati:
            avvisa(
                _(
                    "{count} giocatori non erano nel database dei giocatori: {names}. La finalizzazione li ha creati con i dati che avevano nel torneo, e ha dato loro Elo, partite giocate, storico e medaglie come agli altri."
                ).format(count=len(creati), names=", ".join(nomi_creati))
            )
        # Chi e' andato su una scheda trovata per identificativo FIDE lo
        # dicono gli avvisi, uno per giocatore (10.13.16).
        for nome, id_nel_torneo, id_nel_database in trovati_per_fide:
            avvisa(
                _(
                    "{name} è nel torneo con l'identificativo {tournament_id}, che il database dei giocatori non ha, e nel database con l'identificativo {db_id}, con lo stesso identificativo FIDE: Elo, partite giocate, storico e medaglia sono andati alla scheda {db_id}, senza crearne un doppione."
                ).format(name=nome, tournament_id=id_nel_torneo, db_id=id_nel_database)
            )
    else:
        print(_("Nessun aggiornamento necessario per il Database Giocatori."))
    # --- Fase 6: Archiviazione File Torneo ---
    print(
        _("Archiviazione del torneo '{name}'...").format(name=tournament_name_original)
    )
    # L'archivio e' ordinato per anno e per mese di conclusione del torneo, e
    # le due sottocartelle nascono solo quando c'e' un torneo da metterci.
    end_date_str = torneo.get("end_date")
    data_archivio = datetime.now()
    if end_date_str:
        try:
            data_archivio = datetime.strptime(end_date_str, DATE_FORMAT_ISO)
        except ValueError:
            print(
                _(
                    " Warning: Formato data di fine ('{date_str}') non valido. Uso data corrente per la cartella archivio."
                ).format(date_str=end_date_str)
            )
    from utils import cartella_per_data

    cartella_del_mese = cartella_per_data(ARCHIVED_TOURNAMENTS_DIR, data_archivio)
    if not cartella_del_mese:
        cartella_del_mese = ARCHIVED_TOURNAMENTS_DIR

    custom_path = torneo.get("custom_save_path")
    if custom_path:
        from utils import resolve_and_verify_save_path

        custom_path, warning = resolve_and_verify_save_path(custom_path)
        if warning:
            print(warning)

    # I file restano al loro posto soltanto quando la cartella di lavoro e' una
    # cartella esterna scelta dall'arbitro. Da quando la procedura guidata
    # propone la cartella dell'applicazione, custom_save_path e' sempre
    # valorizzato: senza questo confronto i report del torneo concluso
    # restavano accanto al programma invece di finire in archivio.
    conserva_originali = cartella_di_lavoro_esterna(custom_path)

    # 1. Trova il file JSON principale del torneo (locale)
    local_json_filename = user_data_path(f"Tornello - {sanitized_tournament_name}.json")
    if current_tournament_filename and os.path.exists(current_tournament_filename):
        local_json_path = current_tournament_filename
    elif os.path.exists(local_json_filename):
        local_json_path = local_json_filename
    else:
        local_json_path = None
        print(
            _(
                " Warning: File JSON principale del torneo ('{current_filename}') non trovato per l'archiviazione."
            ).format(current_filename=current_tournament_filename)
        )
    nome_json_del_torneo = f"Tornello - {sanitized_tournament_name}.json"
    json_filename_only = (
        os.path.basename(local_json_path) if local_json_path else nome_json_del_torneo
    )

    # La cartella del torneo in archivio. Un'altra edizione con lo stesso nome
    # conclusa nello stesso mese ha gia' la sua: questa ne prende una con la
    # data di inizio nel nome, invece di sostituirle il json.
    full_archive_path = _cartella_d_archivio(
        cartella_del_mese,
        sanitized_tournament_name,
        json_filename_only,
        (id_nello_storico, inizio_nello_storico),
    )
    try:
        os.makedirs(full_archive_path, exist_ok=True)
    except OSError as e:
        avvisa(
            _(
                "ERRORE: Creazione cartella di archivio '{path}' fallita: {error}"
            ).format(path=full_archive_path, error=e)
        )
        avvisa(
            _(
                "I file del torneo non saranno archiviati ma il resto della finalizzazione è completo."
            )
        )
        return False  # L'archiviazione è una parte importante della finalizzazione
    if os.path.basename(full_archive_path) != sanitized_tournament_name:
        avvisa(
            _(
                "Nell'archivio di questo mese c'è già un altro torneo con il nome {name}: questo va nella cartella {path}."
            ).format(name=tournament_name_original, path=full_archive_path)
        )

    destination_json = os.path.join(full_archive_path, json_filename_only)
    json_gia_in_archivio = os.path.exists(destination_json)
    # Il file aperto puo' essere gia' quello dell'archivio, o quello della
    # cartella di lavoro esterna: allora non va tolto, perche' e' lui la copia
    # da tenere, e da quando la conclusione si salva nel file aperto contiene
    # davvero il torneo concluso.
    gia_al_suo_posto = bool(local_json_path) and _stesso_file(
        local_json_path, destination_json
    )
    custom_json_dest = (
        os.path.join(custom_path, json_filename_only) if conserva_originali else None
    )
    copia_di_lavoro = bool(local_json_path and custom_json_dest) and _stesso_file(
        local_json_path, custom_json_dest
    )

    # 2. Trova gli altri file di testo (.txt) associati al torneo (nella cartella custom o in locale)
    report_files = []
    if custom_path:
        file_pattern_prefix = os.path.join(
            custom_path, f"Tornello - {sanitized_tournament_name}"
        )
    else:
        file_pattern_prefix = user_data_path(f"Tornello - {sanitized_tournament_name}")

    for file_in_dir in glob.glob(f"{file_pattern_prefix}*.*"):
        # Il glob prende tutto cio' che comincia con il nome del torneo,
        # quindi anche i file di Autunneo2 finalizzando Autunneo: si tengono
        # solo quelli che portano il nome per intero. Il json del torneo non
        # e' un report: quello della cartella esterna lo tratta il ramo del
        # json, e preso anche qui passava due volte dalla copia di sicurezza,
        # con un avviso su un file che in archivio non c'era.
        nome_del_file = os.path.basename(file_in_dir)
        if (
            os.path.isfile(file_in_dir)
            and nome_del_file != nome_json_del_torneo
            and file_del_torneo(nome_del_file, sanitized_tournament_name)
        ):
            # Escludiamo il file JSON del torneo attivo da questa lista per gestirlo separatamente
            if not local_json_path or os.path.abspath(file_in_dir) != os.path.abspath(
                local_json_path
            ):
                report_files.append(file_in_dir)

    # Una finalizzazione ripetuta di un torneo gia' archiviato: l'archivio ha
    # il json della stessa edizione, e almeno un giocatore aveva gia' la voce
    # nello storico, quindi non ha ricevuto niente. Il json in archivio
    # contiene i valori che il database ha ricevuto la prima volta, e resta
    # com'e': quello nuovo li ricalcola sul database gia' aggiornato, per
    # esempio con un K diverso, e se sostituisse l'archivio lo storno dei
    # valori applicati non avrebbe piu' da dove prenderli. I file nuovi vanno
    # nella cartella backup, cosi' non restano nella radice.
    if (
        gia_registrati
        and local_json_path
        and json_gia_in_archivio
        and not gia_al_suo_posto
        and not _stessi_byte(local_json_path, destination_json)
    ):
        avvisa(
            _(
                "Il torneo {name} era già finalizzato e archiviato in {path}, con i valori che il database dei giocatori ha ricevuto allora: l'archivio resta com'era, e questa finalizzazione non lo sostituisce. Se il torneo aveva risultati diversi, il database e l'archivio non li hanno ricevuti. I file che ha prodotto nella cartella del programma sono stati messi nella cartella backup, con rifinalizzazione nel nome; quelli della cartella di lavoro esterna, se ne hai scelta una, restano dove sono."
            ).format(name=tournament_name_original, path=full_archive_path)
        )
        da_mettere_da_parte = [] if copia_di_lavoro else [local_json_path]
        if not conserva_originali:
            da_mettere_da_parte += report_files
        for percorso in da_mettere_da_parte:
            _metti_da_parte(percorso, avvisa)
        if db_updated_count == 1:
            avvisa(
                _(
                    "Il database ha però ricevuto questa finalizzazione per un giocatore, che non aveva il torneo nello storico: per lui l'archivio non coincide con il database."
                )
            )
        elif db_updated_count > 1:
            avvisa(
                _(
                    "Il database ha però ricevuto questa finalizzazione per {count} giocatori, che non avevano il torneo nello storico: per loro l'archivio non coincide con il database."
                ).format(count=db_updated_count)
            )
        print(
            _("Torneo '{name}' finalizzato e archiviato.").format(
                name=tournament_name_original
            )
        )
        play_sound("conclusione_torneo", torneo)
        return True

    moved_files_count = 0
    # Processa e copia/sposta i report di testo. Passano dalla stessa copia
    # riletta del json: fino alla 10.8.8 un report gia' presente in archivio
    # non veniva sostituito, e senza cartella esterna quello nuovo restava
    # per sempre nella radice, mentre l'archivio mescolava il json nuovo con
    # i report vecchi.
    for filepath in report_files:
        try:
            filename_only = os.path.basename(filepath)
            destination_path = os.path.join(full_archive_path, filename_only)
            if _copia_verificata(filepath, destination_path, avvisa):
                moved_files_count += 1
                if not conserva_originali:
                    # Sposta: l'originale se ne va solo dopo la copia riletta.
                    os.remove(filepath)
        except Exception as e_move:
            print(
                f"  Errore durante lo spostamento di '{os.path.basename(filepath)}': {e_move}"
            )

    # Processa e archivia il file JSON locale
    archiviato = True
    if local_json_path:
        try:
            archiviato = gia_al_suo_posto or _copia_verificata(
                local_json_path, destination_json, avvisa
            )
            if archiviato and not gia_al_suo_posto:
                moved_files_count += 1

            # Se l'utente ha una cartella personalizzata, salva una copia del JSON concluso anche lì
            if conserva_originali and not copia_di_lavoro:
                _copia_verificata(local_json_path, custom_json_dest, avvisa)

            # Il file JSON attivo si toglie solo quando la copia in archivio
            # e' stata riletta ed e' uguale: fino alla 10.8.8 si cancellava
            # comunque, anche quando in archivio non era stato copiato niente.
            # La copia nella cartella esterna non conta: se non riesce, lo
            # dicono i suoi avvisi.
            if archiviato and not (gia_al_suo_posto or copia_di_lavoro):
                os.remove(local_json_path)
            elif not archiviato:
                avvisa(
                    _(
                        "Il file del torneo resta in {path}: la sua copia in archivio non è verificata, e senza quella il file non si toglie. Il torneo è concluso e il database dei giocatori lo contiene già, ma l'archiviazione non è completa: risolto il problema, per completarla sposta a mano quel file nella cartella {folder}."
                    ).format(path=local_json_path, folder=full_archive_path)
                )
        except Exception as e_json:
            archiviato = False
            avvisa(
                _("Errore durante l'archiviazione del file JSON '{name}': {error}").format(
                    name=os.path.basename(local_json_path), error=e_json
                )
            )

    # Senza una finalizzazione gia' archiviata con cui confrontarsi, i valori
    # di chi aveva gia' il torneo nello storico sono ricalcolati sul database
    # che li contiene gia', e possono non essere quelli che ha ricevuto.
    if gia_registrati and not json_gia_in_archivio:
        avvisa(
            _(
                "Per i giocatori che avevano già questo torneo nello storico, le variazioni Elo scritte nel file archiviato sono ricalcolate adesso, e possono non coincidere con quelle che il database ha ricevuto la prima volta."
            )
        )

    if moved_files_count > 0:
        print(
            _("Spostati/Archiviati {count} file del torneo in: '{path}'").format(
                count=moved_files_count, path=full_archive_path
            )
        )
    else:
        print(_("Nessun file del torneo è stato spostato nella cartella di archivio."))
    # Un torneo il cui json non ha raggiunto l'archivio non e' archiviato, e
    # la finestra non deve dirlo: fino alla 10.8.8 si rispondeva vero lo
    # stesso.
    if not archiviato:
        return False
    print(
        _("Torneo '{name}' finalizzato e archiviato.").format(
            name=tournament_name_original
        )
    )
    play_sound("conclusione_torneo", torneo)
    return True
