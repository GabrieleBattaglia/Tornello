# TORNELLO DEV
# Data concepimento: 28 marzo 2025
import os
import json
import sys
import traceback
import glob

# Add src to sys.path for local development
try:
    sys._MEIPASS
except AttributeError:
    sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "src"))

from GBUtils import Donazione
import atexit
from datetime import datetime, timedelta

# installazione percorsi relativi e i18n
from config import *
from utils import enter_escape, format_date_locale, sanitize_filename, parse_flexible_date
from src.engine import handle_bbpairings_failure
from src.version import VERSIONE
from db_players import (
    load_players_db,
    sincronizza_db_personale,
    aggiorna_db_fide_locale,
)
from tournament import (
    time_machine_torneo,
    load_tournament,
    save_tournament,
    _ensure_players_dict,
    calculate_dates,
    generate_pairings_for_round,
)
from reports import (
    save_current_tournament_round_file,
    append_completed_round_to_history_file,
    save_standings_text,
    display_status,
)
from ui import (
    _conferma_lista_giocatori_torneo,
    input_players,
    update_match_result,
    finalize_tournament,
)

atexit.register(Donazione)

# QF


# --- Database Giocatori Functions ---


# --- Elo Calculation Functions ---


# --- Tie-breaking Functions ---


# --- Main Application Logic ---


if __name__ == "__main__":
    if not os.path.exists(BBP_SUBDIR):
        try:
            os.makedirs(BBP_SUBDIR)
            print(
                _("Info: Creata sottocartella '{}' per i file di bbpPairings.").format(
                    BBP_SUBDIR
                )
            )
        except OSError as e:
            print(
                _("ATTENZIONE: Impossibile creare la sottocartella '{}': {}").format(
                    BBP_SUBDIR, e
                )
            )
            print(_("bbpPairings potrebbe non funzionare correttamente."))
            sys.exit(1)
    players_db = load_players_db()
    torneo = None
    active_tournament_filename = None
    deve_creare_nuovo_torneo = False
    nome_nuovo_torneo_suggerito = None
    print(_("\nBENVENUTI! Sono Tornello {}").format(VERSIONE))

    # --- CONTROLLO AGGIORNAMENTI AUTOMATICI ---
    try:
        from GBUtils import update_checker, perform_update
        from version import __version__ as current_ver

        print(_("Controllo aggiornamenti..."))
        repo_api = (
            "https://api.github.com/repos/GabrieleBattaglia/Tornello/releases/latest"
        )
        avail, latest_ver, dl_url, changelog = update_checker(current_ver, repo_api)
        if avail:
            if dl_url:
                print(_("\n*** AGGIORNAMENTO DISPONIBILE! ***"))
                print(
                    _("Versione corrente: {curr} | Nuova versione: {latest}").format(
                        curr=current_ver, latest=latest_ver
                    )
                )
                if enter_escape(
                    _(
                        "Vuoi scaricare e installare l'aggiornamento ora? (INVIO per Sì | ESCAPE per ignorare)"
                    )
                ):
                    print(
                        _(
                            "Scaricamento e installazione in corso. Il programma si chiuderà per l'aggiornamento..."
                        )
                    )
                    if perform_update(dl_url, "tornello"):
                        sys.exit(0)
                    else:
                        print(
                            _(
                                "Impossibile avviare l'aggiornamento automatico (la funzione è disponibile solo per la versione compilata)."
                            )
                        )
            else:
                print(_("\n*** AGGIORNAMENTO DISPONIBILE ***"))
                print(
                    _(
                        "E' disponibile la nuova versione {latest_ver}, ma i file di installazione non sono ancora pronti per il download."
                    ).format(latest_ver=latest_ver)
                )
                print(_("Riprova più tardi."))
    except Exception as e_update:
        print(_("Controllo aggiornamenti fallito: {}").format(e_update))

    print(_("\nVerifica stato database FIDE locale..."))
    db_fide_esiste = os.path.exists(FIDE_DB_LOCAL_FILE)
    db_fide_appena_aggiornato = False
    if not db_fide_esiste:
        print(_("\nIl database FIDE locale non è presente sul tuo computer."))
        # Se non esiste, proponiamo sempre di scaricarlo
        if enter_escape(
            _(
                "Vuoi scaricarlo ora? (L'operazione potrebbe richiedere alcuni minuti) (INVIO|ESCAPE)"
            )
        ):
            if aggiorna_db_fide_locale():
                db_fide_appena_aggiornato = True
                print(_("Database FIDE locale aggiornato con successo."))
    else:  # Il file esiste, quindi controlliamo solo la sua età
        try:
            file_mod_timestamp = os.path.getmtime(FIDE_DB_LOCAL_FILE)
            file_age_days = (
                datetime.now() - datetime.fromtimestamp(file_mod_timestamp)
            ).days
            print(
                _("Info: Il tuo database FIDE locale ha {} giorni.").format(
                    file_age_days
                )
            )
            if file_age_days >= 32:
                print(
                    _(
                        "Essendo trascorsi più di 32 giorni dall'ultimo download, potrebbe essere stato rilasciato un aggiornamento"
                    )
                )
                if enter_escape(
                    _(
                        "Si consiglia di aggiornarlo. Vuoi scaricare la versione più recente? (INVIO|ESCAPE)"
                    )
                ):
                    if aggiorna_db_fide_locale():
                        db_fide_appena_aggiornato = True
        except Exception as e:
            print(
                _("Errore nel controllare la data del file DB FIDE locale: {}").format(
                    e
                )
            )
    # --- SINCRONIZZAZIONE DB PERSONALE ---
    # Chiedi di sincronizzare solo se il DB FIDE esiste (o perché c'era già o perché è stato appena scaricato)
    if os.path.exists(FIDE_DB_LOCAL_FILE):
        # La condizione chiave è qui: chiedi se abbiamo appena aggiornato OPPURE se il file è vecchio
        file_age_days = (
            datetime.now()
            - datetime.fromtimestamp(os.path.getmtime(FIDE_DB_LOCAL_FILE))
        ).days
        if db_fide_appena_aggiornato or file_age_days >= 32:
            prompt_sync = (
                _(
                    "\nDatabase FIDE aggiornato. Vuoi sincronizzare ora il tuo DB personale?"
                )
                if db_fide_appena_aggiornato
                else _(
                    "\nVuoi sincronizzare il tuo DB personale con i dati FIDE locali?"
                )
            )
            if enter_escape(f"{prompt_sync} (INVIO|ESCAPE)"):
                sincronizza_db_personale()
    # 1. Scansione dei file torneo esistenti
    tournament_files_pattern = "Tornello - *.json"
    potential_tournament_files = [
        f
        for f in glob.glob(tournament_files_pattern)
        if "- concluso_"
        not in os.path.basename(f).lower()  # Aggiunto .lower() per sicurezza
        and os.path.basename(f) != os.path.basename(PLAYER_DB_FILE)  # <-- CORREZIONE
    ]
    if not potential_tournament_files:
        print(_("Nessun torneo esistente trovato."))
        if enter_escape(
            _("Premi INVIO per creare un nuovo torneo, ESCAPE per uscire.")
        ):
            deve_creare_nuovo_torneo = True
        else:
            print(_("Uscita dal programma."))
            sys.exit(0)
    elif len(potential_tournament_files) == 1:
        single_found_filepath = potential_tournament_files[0]
        single_tournament_name_guess = _("Torneo Sconosciuto")
        try:
            with open(single_found_filepath, "r", encoding="utf-8") as f_temp:
                data_temp = json.load(f_temp)
            single_tournament_name_guess = data_temp.get(
                "name",
                os.path.basename(single_found_filepath)
                .replace("Tornello - ", "")
                .replace(".json", ""),
            )
        except Exception as e:
            # Se non riesci a leggere il nome dal JSON, usa una parte del nome del file
            print(
                _(
                    "Info: impossibile leggere i dettagli da '{filename}' ({error}). Uso il nome del file."
                ).format(filename=os.path.basename(single_found_filepath), error=e)
            )
            base_name = os.path.basename(single_found_filepath)
            if base_name.startswith("Tornello - ") and base_name.endswith(".json"):
                single_tournament_name_guess = base_name[
                    len("Tornello - ") : -len(".json")
                ]
            else:
                single_tournament_name_guess = base_name
        print(
            _("\nTrovato un solo torneo esistente: '{name}' (File: {filename})").format(
                name=single_tournament_name_guess,
                filename=os.path.basename(single_found_filepath),
            )
        )
        while True:  # Loop per la scelta dell'utente
            user_input_choice = input(
                _(
                    "Vuoi caricare '{name}'? (S/Invio per sì, oppure inserisci il nome di un NUOVO torneo da creare): "
                ).format(name=single_tournament_name_guess)
            ).strip()
            if not user_input_choice or user_input_choice.lower() == "s":
                # L'utente vuole caricare il torneo trovato (ha premuto Invio o 's')
                active_tournament_filename = single_found_filepath
                print(
                    _("Caricamento di '{name}'...").format(
                        name=single_tournament_name_guess
                    )
                )
                torneo = load_tournament(active_tournament_filename)
                if not torneo:
                    # Il caricamento è fallito
                    print(
                        _(
                            "Errore fatale nel caricamento del torneo '{filename}'."
                        ).format(filename=active_tournament_filename)
                    )
                    # Chiediamo se vuole creare un nuovo torneo o uscire
                    create_new_instead_choice = enter_escape(
                        "Vuoi creare un nuovo torneo? (INVIO per sì|ESCAPE per uscire): "
                    )
                    if create_new_instead_choice:
                        deve_creare_nuovo_torneo = True
                        active_tournament_filename = (
                            None  # Resetta perché il caricamento è fallito
                        )
                    else:
                        print(_("Uscita dal programma."))
                        sys.exit(
                            0
                        )  # Esce se il caricamento fallisce e non vuole creare
                # Se torneo è stato caricato con successo (o se si è scelto di creare dopo fallimento), esci da questo loop
                break
            else:
                # L'utente ha inserito un nome, quindi vuole creare un nuovo torneo.
                # La stringa inserita (user_input_choice) è il nome del nuovo torneo.
                print(
                    _(
                        "Ok, procederemo con la creazione di un nuovo torneo chiamato: '{name}'."
                    ).format(name=user_input_choice)
                )
                deve_creare_nuovo_torneo = True
                nome_nuovo_torneo_suggerito = user_input_choice
                break
    else:  # Più di un torneo trovato
        print(_("\n--- Tornei Esistenti Trovati ---"))
        tournament_options = []
        for idx, filepath in enumerate(potential_tournament_files):
            try:
                # Carichiamo temporaneamente per estrarre i metadati
                with open(filepath, "r", encoding="utf-8") as f_temp:
                    data_temp = json.load(f_temp)

                t_name = data_temp.get("name", _("Nome Sconosciuto"))
                t_start = data_temp.get("start_date")
                t_end = data_temp.get("end_date")

                start_display = format_date_locale(t_start) if t_start else "N/D"
                end_display = format_date_locale(t_end) if t_end else "N/D"

                tournament_options.append(
                    {
                        "id_lista": idx + 1,
                        "filepath": filepath,
                        "name": t_name,
                        "start_date_display": start_display,
                        "end_date_display": end_display,
                    }
                )
                print(
                    _(
                        " {num}. {name} (dal {start_date} al {end_date}) - File: {filename}"
                    ).format(
                        num=idx + 1,
                        name=t_name,
                        start_date=start_display,
                        end_date=end_display,
                        filename=os.path.basename(filepath),
                    )
                )
            except Exception as e:
                print(
                    _(
                        " Errore durante la lettura dei metadati da {filename}: {error} (file saltato)"
                    ).format(filename=os.path.basename(filepath), error=e)
                )

        if (
            not tournament_options
        ):  # Se tutti i file hanno dato errore in lettura metadati
            print(
                _(
                    "Nessun torneo valido trovato nonostante la presenza di file. Si procederà con la creazione."
                )
            )
            deve_creare_nuovo_torneo = True
        else:
            # --- Controllo Tornei Sospesi ---
            suspended_tournaments = []
            for opt in tournament_options:
                try:
                    with open(opt["filepath"], "r", encoding="utf-8") as f_temp:
                        data_temp = json.load(f_temp)
                    if data_temp.get("creation_suspended", False):
                        suspended_tournaments.append(opt)
                except Exception:
                    pass

            if suspended_tournaments:
                print(_("\n*** TROVATI TORNEI CON CREAZIONE SOSPESA ***"))
                for st in suspended_tournaments:
                    print(
                        _(" - '{name}' (File: {filename})").format(
                            name=st["name"], filename=os.path.basename(st["filepath"])
                        )
                    )

                if len(suspended_tournaments) == 1:
                    resume_choice = enter_escape(
                        _(
                            "Vuoi riprendere la creazione di '{name}'? (INVIO|ESCAPE): "
                        ).format(name=suspended_tournaments[0]["name"])
                    )
                    if resume_choice:
                        active_tournament_filename = suspended_tournaments[0][
                            "filepath"
                        ]
                        torneo = load_tournament(active_tournament_filename)
                        deve_creare_nuovo_torneo = False
                        print(
                            _("Ripresa creazione torneo '{name}'...").format(
                                name=torneo["name"]
                            )
                        )
                else:
                    # Gestione di multipli tornei sospesi (opzionale, per ora lasciamo la scelta generale)
                    print(
                        _(
                            "Ci sono più tornei in stato sospeso. Selezionali dal menu per riprenderli."
                        )
                    )

            print(
                _("\n {num}. Crea un nuovo torneo").format(
                    num=len(tournament_options) + 1
                )
            )
            while True:
                choice_str = input(
                    _(
                        "Scegli un torneo da caricare (1-{max_num}) o '{new_num}' per crearne uno nuovo: "
                    ).format(
                        max_num=len(tournament_options),
                        new_num=len(tournament_options) + 1,
                    )
                ).strip()
                if choice_str.isdigit():
                    choice_num = int(choice_str)
                    if 1 <= choice_num <= len(tournament_options):
                        chosen_option = next(
                            opt
                            for opt in tournament_options
                            if opt["id_lista"] == choice_num
                        )
                        active_tournament_filename = chosen_option["filepath"]
                        print(
                            _("Caricamento di '{name}'...").format(
                                name=chosen_option["name"]
                            )
                        )
                        torneo = load_tournament(active_tournament_filename)
                        if not torneo:
                            print(
                                _(
                                    "Errore nel caricamento del torneo {filename}. Riprova o crea un nuovo torneo."
                                ).format(filename=active_tournament_filename)
                            )
                            # L'utente tornerà al prompt di scelta
                            active_tournament_filename = None  # Resetta
                        else:
                            break  # Torneo scelto e caricato
                    elif choice_num == len(tournament_options) + 1:
                        deve_creare_nuovo_torneo = True
                        break
                    else:
                        print(_("Scelta non valida."))
                else:
                    print(_("Inserisci un numero."))

    torneo_in_ripresa = False
    torneo_in_ripresa = False
    # Se abbiamo caricato un torneo che era in stato sospeso, saltiamo la fase 2 di "nuova creazione"
    # e andiamo direttamente al completamento dell'inserimento giocatori
    if torneo and torneo.get("creation_suspended", False):
        print(
            _("\nRipresa inserimento giocatori per '{name}'...").format(
                name=torneo["name"]
            )
        )
        existing_players_list = torneo.get("players", [])
        risultato_input = input_players(
            players_db,
            existing_players=existing_players_list,
            torneo_obj=torneo,
            torneo_filename=active_tournament_filename,
        )

        if risultato_input is None:
            # Sospeso di nuovo
            sys.exit(0)

        torneo["players"] = risultato_input

        # Una volta confermata e conclusa la lista, togliamo il flag di sospensione
        if not _conferma_lista_giocatori_torneo(torneo, players_db):
            print(
                _(
                    "Creazione torneo annullata a causa di problemi con la lista giocatori."
                )
            )
            sys.exit(0)

        torneo.pop("creation_suspended", None)
        torneo["players_dict"] = {p["id"]: p for p in torneo["players"]}
        deve_creare_nuovo_torneo = True  # Forza la logica successiva (generazione turni, bye, ecc) a credere che stiamo finendo la creazione
        torneo_in_ripresa = True
        torneo_in_ripresa = True

    # 2. Creazione nuovo torneo (se necessario)
    if deve_creare_nuovo_torneo or (torneo is None and not active_tournament_filename):
        if (
            not deve_creare_nuovo_torneo and torneo is None
        ):  # Se il caricamento è fallito ma non era stato scelto di creare
            print(
                _(
                    "Nessun torneo caricato. Si procede con la creazione di un nuovo torneo."
                )
            )

        if not torneo_in_ripresa:
            if not torneo_in_ripresa:
                # Se non stiamo riprendendo un torneo sospeso, inizializziamo da zero
                if not torneo or not torneo.get("name"):
                    torneo = {}
                    print(_("\n--- Creazione Nuovo Torneo ---"))
                    active_tournament_filename = (
                        None  # Verrà impostato quando il nome sarà definito
                    )
                    new_tournament_name_final = (
                        ""  # Nome che verrà effettivamente usato per il torneo
                    )
                else:
                    new_tournament_name_final = torneo.get("name")

                # Fase 1: Prova a usare il nome suggerito, se esiste
                if nome_nuovo_torneo_suggerito and not new_tournament_name_final:
                    print(
                        _("Nome suggerito per il nuovo torneo: '{name}'").format(
                            name=nome_nuovo_torneo_suggerito
                        )
                    )
                    current_potential_name = nome_nuovo_torneo_suggerito
                    sanitized_check_name = sanitize_filename(current_potential_name)
                    # Assicurati che il prefisso "Tornello - " sia quello corretto per il tuo stile di nomenclatura
                    prospective_filename_check = (
                        f"Tornello - {sanitized_check_name}.json"
                    )
                    if os.path.exists(prospective_filename_check):
                        overwrite_choice = enter_escape(
                            _(
                                "ATTENZIONE: Un file torneo '{filename}' con questo nome esiste già. Sovrascriverlo? (INVIO|ESCAPE): "
                            ).format(filename=prospective_filename_check)
                        )
                        if overwrite_choice:
                            new_tournament_name_final = (
                                current_potential_name  # Accetta il nome suggerito
                            )
                            active_tournament_filename = prospective_filename_check
                        else:
                            print(
                                _(
                                    "Sovrascrittura annullata. Verrà richiesto un nuovo nome."
                                )
                            )
                            nome_nuovo_torneo_suggerito = (
                                None  # Il suggerimento non è più valido
                            )
                            # new_tournament_name_final rimane "" (o None), quindi si passerà alla richiesta manuale
                    else:  # Il file per il nome suggerito non esiste, quindi va bene
                        new_tournament_name_final = current_potential_name
                        active_tournament_filename = prospective_filename_check

                # Fase 2: Se un nome non è stato finalizzato dal suggerimento (o non c'era suggerimento), chiedilo
                if not new_tournament_name_final:
                    while True:  # Loop solo per la richiesta del nome se necessario
                        input_corrente_nome_torneo = input(
                            _("Inserisci il nome del nuovo torneo: ")
                        ).strip()
                        if input_corrente_nome_torneo:
                            sanitized_name_new = sanitize_filename(
                                input_corrente_nome_torneo
                            )
                            prospective_filename = f"Tornello - {sanitized_name_new}.json"  # Usa il tuo stile
                            if os.path.exists(prospective_filename):
                                overwrite = enter_escape(
                                    _(
                                        "ATTENZIONE: Un file torneo '{filename}' con questo nome esiste già. Sovrascriverlo? (INVIO|ESCAPE): "
                                    ).format(filename=prospective_filename_check)
                                )
                                if not overwrite:
                                    print(
                                        _(
                                            "Operazione annullata. Scegli un nome diverso per il torneo."
                                        )
                                    )
                                    continue  # Torna a chiedere il nome (all'inizio di QUESTO while True)
                            new_tournament_name_final = input_corrente_nome_torneo
                            active_tournament_filename = prospective_filename
                            break  # Esce dal loop di richiesta nome, nome definito!
                        else:
                            print(
                                _("Il nome del torneo non può essere vuoto. Riprova.")
                            )
                if not new_tournament_name_final or not active_tournament_filename:
                    print(
                        _(
                            "Nome del torneo non definito correttamente. Creazione annullata."
                        )
                    )
                    sys.exit(1)
                torneo["name"] = new_tournament_name_final
                while True:
                    try:
                        oggi_str_iso = datetime.now().strftime(DATE_FORMAT_ISO)
                        oggi_str_locale = format_date_locale(oggi_str_iso)
                        start_date_str = input(
                            _(
                                "Inserisci data inizio ({date_format}) [Default: {default_date}]: "
                            ).format(
                                date_format=DATE_FORMAT_ISO,
                                default_date=oggi_str_locale,
                            )
                        ).strip()
                        if not start_date_str:
                            start_date_str = oggi_str_iso
                        start_dt = parse_flexible_date(start_date_str)
                        torneo["start_date"] = start_dt.strftime(DATE_FORMAT_ISO)
                        break
                    except ValueError:
                        print(
                            _(
                                "Formato data non valido. Usa {date_format} o AAAAMMGG. Riprova."
                            ).format(date_format=DATE_FORMAT_ISO)
                        )
                while True:
                    try:
                        start_date_dt = datetime.strptime(
                            torneo["start_date"], DATE_FORMAT_ISO
                        )
                        future_date_dt = start_date_dt + timedelta(days=60)
                        default_end_date_iso = future_date_dt.strftime(DATE_FORMAT_ISO)
                        default_end_date_locale = format_date_locale(future_date_dt)
                        end_date_str = input(
                            _(
                                "Inserisci data fine ({date_format}) [Default: {default_date}]: "
                            ).format(
                                date_format=DATE_FORMAT_ISO,
                                default_date=default_end_date_locale,
                            )
                        ).strip()
                        if not end_date_str:
                            end_date_str = default_end_date_iso
                        end_dt = datetime.strptime(end_date_str, DATE_FORMAT_ISO)
                        if end_dt < start_date_dt:
                            print(
                                _(
                                    "Errore: La data di fine non può essere precedente alla data di inizio."
                                )
                            )
                            continue
                        torneo["end_date"] = end_date_str
                        break
                    except ValueError:
                        print(
                            f"Formato data non valido. Usa {DATE_FORMAT_ISO}. Riprova."
                        )
                    except OverflowError:
                        print(
                            _(
                                "Errore: La data calcolata risulta troppo lontana nel futuro."
                            )
                        )
                        continue
                while True:
                    try:
                        rounds_str = input(
                            _("Inserisci il numero totale dei turni: ")
                        ).strip()
                        total_rounds = int(rounds_str)
                        if total_rounds > 0:
                            torneo["total_rounds"] = total_rounds
                            break
                        else:
                            print(_("Il numero di turni deve essere positivo."))
                    except ValueError:
                        print(_("Inserisci un numero intero valido."))
                print(
                    _(
                        "\nInserisci i dettagli aggiuntivi del torneo (lascia vuoto per usare default):"
                    )
                )
                torneo["site"] = input(
                    _(" Luogo del torneo [Default: {default_site}]: ").format(
                        default_site=_("Luogo Sconosciuto")
                    )
                ).strip() or _("Luogo Sconosciuto")
                fed_code = (
                    input(
                        _(
                            "  Federazione organizzante (codice 3 lettere) [Default: ITA]: "
                        )
                    )
                    .strip()
                    .upper()
                    or "ITA"
                )
                torneo["federation_code"] = fed_code[:3]
                torneo["chief_arbiter"] = input(
                    _(" Arbitro Capo [Default: {default_arbiter}]: ").format(
                        default_arbiter=_("N/D")
                    )
                ).strip() or _("N/D")
                torneo["deputy_chief_arbiters"] = (
                    input(
                        _(
                            " Vice Arbitri (separati da virgola) [Default: {default_deputy}]: "
                        ).format(default_deputy=_("nessuno"))
                    ).strip()
                    or ""
                )
                torneo["time_control"] = input(
                    _(" Controllo del Tempo [Default: {default_tc}]: ").format(
                        default_tc=_("Standard")
                    )
                ).strip() or _("Standard")
                while True:
                    b1_choice = enter_escape(
                        _(" Bianco alla prima scacchiera del Turno 1? (INVIO|ESCAPE): ")
                    )
                    if b1_choice:
                        torneo["initial_board1_color_setting"] = "white1"
                        break
                    else:
                        torneo["initial_board1_color_setting"] = "black1"
                        break
                round_dates = calculate_dates(
                    torneo["start_date"], torneo["end_date"], torneo["total_rounds"]
                )
                if round_dates is None:
                    print(
                        _(
                            "Errore fatale nel calcolo delle date dei turni. Creazione torneo annullata."
                        )
                    )
                    sys.exit(1)
                torneo["round_dates"] = round_dates
                torneo["tournament_id"] = (
                    f"{sanitize_filename(torneo['name'])}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                )
                existing_players = []
                while True:
                    risultato_input = input_players(
                        players_db,
                        existing_players=existing_players,
                        torneo_obj=torneo,
                        torneo_filename=active_tournament_filename,
                    )
                    if risultato_input is None:
                        # Utente ha sospeso la creazione
                        sys.exit(0)
                    torneo["players"] = risultato_input
                    if _conferma_lista_giocatori_torneo(torneo, players_db):
                        break
                    else:
                        print(_("\nReindirizzamento all'inserimento giocatori..."))
                        existing_players = torneo["players"]
                torneo["players_dict"] = {p["id"]: p for p in torneo["players"]}
        num_giocatori = len(torneo.get("players", []))
        num_turni_totali = torneo.get("total_rounds", 0)
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
        prompt_conferma = _(
            "Accetti il valore suggerito? (INVIO = Sì / ESCAPE = No, per usare {alt_val})"
        ).format(alt_val=valore_alternativo)
        if enter_escape(prompt_conferma):
            valore_bye_confermato = valore_suggerito
        else:
            valore_bye_confermato = valore_alternativo
        torneo["bye_value"] = float(valore_bye_confermato)
        print(_("Valore del BYE impostato a: {val}").format(val=torneo["bye_value"]))
        min_req_players = (
            num_turni_totali + 1
            if isinstance(num_turni_totali, int) and num_turni_totali > 0
            else 2
        )
        if num_giocatori < min_req_players:  # Ricontrolla dopo _conferma
            print(
                _(
                    "Numero insufficiente di giocatori ({num_players}) per {num_rounds} turni dopo la conferma. Torneo annullato."
                ).format(num_players=num_giocatori, num_rounds=num_turni_totali)
            )
            sys.exit(0)
        torneo["current_round"] = 1
        torneo["rounds"] = []
        torneo["next_match_id"] = 1
        torneo["launch_count"] = 1
        torneo["players_dict"] = {p["id"]: p for p in torneo["players"]}

        print(_("\nGenerazione abbinamenti per il Turno 1..."))
        matches_r1 = generate_pairings_for_round(torneo)
        if matches_r1 is None:
            print(
                _(
                    "ERRORE CRITICO: Fallimento generazione abbinamenti Turno 1. Torneo non avviato."
                )
            )
            sys.exit(1)
        print(_("Registrazione risultati automatici per il Turno 1 (BYE)..."))
        valore_bye_torneo = torneo.get("bye_value", 1.0)
        for match in matches_r1:
            if match.get("result") == "BYE":
                bye_player_id = match.get("white_player_id")
                if bye_player_id and bye_player_id in torneo["players_dict"]:
                    player_obj = torneo["players_dict"][bye_player_id]
                    player_obj["points"] = valore_bye_torneo
                    player_obj.setdefault("results_history", []).append(
                        {
                            "round": 1,
                            "opponent_id": "BYE_PLAYER_ID",
                            "color": None,
                            "result": "BYE",
                            "score": valore_bye_torneo,
                        }
                    )
                    print(
                        _(
                            " > Giocatore {name} (ID: {id}) ha ricevuto un BYE. Punti e storico aggiornati."
                        ).format(name=player_obj.get("first_name"), id=bye_player_id)
                    )
        torneo["rounds"].append({"round": 1, "matches": matches_r1})
        save_tournament(torneo)  # Salva sul nuovo active_tournament_filename
        save_current_tournament_round_file(torneo)
        save_standings_text(torneo, final=False)
        print(
            _("\nTorneo '{name}' creato e Turno 1 generato. File: '{filename}'").format(
                name=torneo.get("name"), filename=active_tournament_filename
            )
        )
    # 3. Se nessun torneo è attivo a questo punto, esci.
    if not torneo or not active_tournament_filename:
        print(_("\nNessun torneo attivo. Uscita dal programma."))
        sys.exit(0)
    # 4. Aggiorna launch_count se il torneo è stato caricato (non creato ora)
    if not deve_creare_nuovo_torneo:  # Implica che è stato caricato
        torneo["launch_count"] = torneo.get("launch_count", 0) + 1
        # Assicura che players_dict sia inizializzato (load_tournament dovrebbe già farlo)
        _ensure_players_dict(torneo)
    # Messaggio di benvenuto specifico per il torneo
    print(_("\n--- Torneo Attivo: {name} ---").format(name=torneo.get("name", "N/D")))
    print(f"File: {active_tournament_filename}")
    print(
        _("Sessione numero {count} per questo torneo.").format(
            count=torneo.get("launch_count", 1)
        )
    )
    print(_("Copyright 2025, dedicato all'ASCId e al gruppo Scacchierando."))
    try:
        while True:
            current_round_num = torneo.get("current_round")
            total_rounds_num = torneo.get("total_rounds")
            if (
                current_round_num is None
                or total_rounds_num is None
                or current_round_num > total_rounds_num
            ):
                # ... (condizione di uscita se il torneo è finito)
                if torneo:  # Se il torneo è "finito" ma esiste ancora l'oggetto
                    print(
                        _(
                            "\nIl torneo '{name}' si è concluso o in uno stato non valido."
                        ).format(name=torneo.get("name"))
                    )
                else:  # Se è stato finalizzato e impostato a None
                    print(_("\nNessun torneo attivo o torneo concluso."))
                break

            print(
                _("\n--- Gestione Turno {round_num} ---").format(
                    round_num=current_round_num
                )
            )
            display_status(torneo)

            current_round_data = None
            for r_data_loop in torneo.get("rounds", []):
                if r_data_loop.get("round") == current_round_num:
                    current_round_data = r_data_loop
                    break

            if current_round_data is None:
                print(
                    _("ERRORE CRITICO: Dati turno {round_num} non trovati!").format(
                        round_num=current_round_num
                    )
                )
                break
            round_completed = (
                all(
                    m.get("result") is not None or m.get("black_player_id") is None
                    for m in current_round_data.get("matches", [])
                )
                if current_round_data.get("matches")
                else False
            )  # Considera non completo se non ci sono partite

            if not round_completed:
                modifications_made = update_match_result(
                    torneo
                )  # Passa l'oggetto torneo aggiornabile
                # update_match_result ora chiama gestisci_pianificazione_partite che usa il current_round_data da torneo
                print(
                    _(
                        "\nSessione di inserimento/modifica risultati (o pianificazione) terminata."
                    )
                )
                if modifications_made:  # Se update_match_result o gestisci_pianificazione hanno fatto modifiche
                    print(_("Salvataggio modifiche al torneo..."))
                    save_tournament(torneo)  # Salva sul file corretto

                save_current_tournament_round_file(torneo)
                save_standings_text(torneo, final=False)
                exit_choice = enter_escape(_("Vuoi continuare? (INVIO|ESCAPE)): "))
                if not exit_choice:
                    print(_("Salvataggio finale prima dell'uscita..."))
                    save_tournament(torneo)
                    break  # Esce dal while True (main loop)
            else:
                print(
                    _("\nTurno {round_num} completato.").format(
                        round_num=current_round_num
                    )
                )
                append_completed_round_to_history_file(torneo, current_round_num)
                save_standings_text(torneo, final=False)

                if current_round_num == total_rounds_num:
                    print(
                        _("\nUltimo turno completato. Avvio finalizzazione torneo...")
                    )
                    if finalize_tournament(
                        torneo, players_db, active_tournament_filename
                    ):
                        print(
                            _("\n--- Torneo Concluso e Finalizzato Correttamente ---")
                        )
                        torneo = None
                        active_tournament_filename = None
                    else:
                        print(
                            _("\n--- ERRORE durante la Finalizzazione del Torneo ---")
                        )
                        if torneo and active_tournament_filename:
                            save_tournament(torneo)
                    break
                else:  # Prepara e genera il prossimo turno
                    next_round_num = current_round_num + 1
                    print(
                        _(
                            "\nVuoi procedere e generare gli abbinamenti per il Turno {round_num}? (INVIO|ESCAPE): "
                        ).format(round_num=next_round_num)
                    )
                    procede_next_round = enter_escape()
                    if procede_next_round:
                        # 1. Aggiorna il numero del turno
                        torneo["current_round"] = next_round_num
                        print(
                            _(
                                "Generazione abbinamenti per il Turno {round_num}..."
                            ).format(round_num=next_round_num)
                        )
                        # 2. Genera gli abbinamenti
                        next_matches = generate_pairings_for_round(torneo)
                        if next_matches is None:
                            user_action = handle_bbpairings_failure(
                                torneo, next_round_num, "Errore durante la generazione."
                            )
                            if user_action == "time_machine":
                                print(_("Accesso alla Time Machine..."))
                                # Ripristiniamo il turno corrente a quello precedente, così la TM parte da uno stato noto
                                torneo["current_round"] = current_round_num
                                if time_machine_torneo(torneo):
                                    any_changes_made_in_this_session = True
                                    save_tournament(torneo)
                                    print(
                                        _(
                                            "Stato del torneo ripristinato e salvato. Riavvio del ciclo principale."
                                        )
                                    )
                                else:
                                    print(
                                        _(
                                            "Time Machine annullata o fallita. Uscita per sicurezza."
                                        )
                                    )
                                    save_tournament(torneo)
                                    break  # Esce dal ciclo principale
                                # Non uscire dal ciclo, ricomincerà dal turno ripristinato
                                continue
                            elif user_action == "terminate":
                                print(_("Uscita dal programma come richiesto."))
                                torneo["current_round"] = (
                                    current_round_num  # Ripristina per coerenza
                                )
                                save_tournament(torneo)
                                break  # Esce dal ciclo principale
                        # 3. Gestisci il BYE appena generato (se presente)
                        print(
                            _(
                                "Registrazione risultati automatici per il Turno {round_num} (BYE)..."
                            ).format(round_num=next_round_num)
                        )
                        valore_bye_torneo = torneo.get("bye_value", 1.0)
                        for match in next_matches:
                            if match.get("result") == "BYE":
                                bye_player_id = match.get("white_player_id")
                                _ensure_players_dict(
                                    torneo
                                )  # Assicura che la cache giocatori sia pronta
                                if (
                                    bye_player_id
                                    and bye_player_id in torneo["players_dict"]
                                ):
                                    player_obj = torneo["players_dict"][bye_player_id]
                                    player_obj["points"] = (
                                        player_obj.get("points", 0.0)
                                        + valore_bye_torneo
                                    )
                                    player_obj.setdefault("results_history", []).append(
                                        {
                                            "round": next_round_num,
                                            "opponent_id": "BYE_PLAYER_ID",
                                            "color": None,
                                            "result": "BYE",
                                            "score": valore_bye_torneo,
                                        }
                                    )
                                    # Aggiorna anche le altre statistiche relative al BYE
                                    player_obj["received_bye_count"] = (
                                        player_obj.get("received_bye_count", 0) + 1
                                    )
                                    player_obj.setdefault(
                                        "received_bye_in_round", []
                                    ).append(next_round_num)
                                    print(
                                        _(
                                            " > Giocatore {name} (ID: {id}) ha ricevuto un BYE. Punti e storico aggiornati."
                                        ).format(
                                            name=player_obj.get("first_name"),
                                            id=bye_player_id,
                                        )
                                    )
                        torneo["rounds"].append(
                            {"round": next_round_num, "matches": next_matches}
                        )
                        # 5. Salva tutto
                        save_tournament(torneo)
                        save_current_tournament_round_file(torneo)
                        print(
                            _("Turno {round_num} generato e salvato.").format(
                                round_num=next_round_num
                            )
                        )
                    else:
                        print(
                            _(
                                "Generazione prossimo turno annullata. Salvataggio stato attuale."
                            )
                        )
                        save_tournament(torneo)
                        break  # Esce dal main loop
    except KeyboardInterrupt:
        print(_("\nOperazione interrotta dall'utente."))
        if torneo and active_tournament_filename:
            print(
                f"Salvataggio stato attuale del torneo in '{active_tournament_filename}'..."
            )
            save_tournament(torneo)
            if torneo.get("current_round") <= torneo.get("total_rounds", 0):
                save_current_tournament_round_file(torneo)
        print(_("Stato salvato. Uscita."))
        sys.exit(0)
    except Exception as e_main_loop:
        print(
            _("\nERRORE CRITICO NON GESTITO nel flusso principale: {error}").format(
                error=e_main_loop
            )
        )
        traceback.print_exc()
        if torneo and active_tournament_filename:
            print(
                f"Tentativo salvataggio stato torneo in '{active_tournament_filename}'..."
            )
            save_tournament(torneo)
        sys.exit(1)
    if torneo is None and active_tournament_filename is None:
        print(_("\nProgramma Tornello terminato."))
    elif torneo and active_tournament_filename:
        print(
            _(
                "\nProgramma Tornello terminato. Ultimo stato per '{name}' in '{filename}'."
            ).format(
                name=torneo.get("name", "N/D"), filename=active_tournament_filename
            )
        )
    else:  # Caso anomalo
        print(_("\nProgramma Tornello terminato con uno stato incerto del torneo."))
