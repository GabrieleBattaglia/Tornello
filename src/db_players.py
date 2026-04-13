import os
import json
import zipfile
import io
import requests
import threading
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime
from config import *
from utils import format_date_locale, enter_escape, format_rank_ordinal
from stats import get_k_factor

try:
    from unidecode import unidecode
except ImportError:

    def unidecode(x):
        return x


def _cerca_giocatore_nel_db_fide(search_term):
    """
    Cerca un giocatore nel DB FIDE locale per nome/cognome o ID FIDE.
    Restituisce una lista di record corrispondenti.
    Ricerca tokenizzata per non essere sensibile all'ordine delle parole.
    """
    if not os.path.exists(FIDE_DB_LOCAL_FILE):
        return []  # Se il file non esiste, non c'è nulla da cercare
    try:
        with open(FIDE_DB_LOCAL_FILE, "r", encoding="utf-8") as f:
            fide_db = json.load(f)
    except (IOError, json.JSONDecodeError):
        return []  # Errore di lettura, restituisce lista vuota

    matches = []
    search_terms = search_term.strip().lower().split()
    search_is_id = search_term.strip().isdigit()

    if search_is_id and search_term.strip() in fide_db:
        matches.append(fide_db[search_term.strip()])
        return matches

    for fide_id, player_data in fide_db.items():
        full_name = f"{player_data.get('first_name', '')} {player_data.get('last_name', '')}".lower()
        if all(term in full_name for term in search_terms):
            matches.append(player_data)

    return matches


def sincronizza_db_personale():
    """
    Carica il DB FIDE locale e il DB personale, li confronta, e propone
    aggiornamenti e associazioni di ID FIDE. Mostra un sommario e permette
    di applicare tutto in blocco o valutare singolarmente.
    """
    if not os.path.exists(FIDE_DB_LOCAL_FILE):
        print(
            _("ERRORE: Database FIDE locale '{}' non trovato.").format(
                FIDE_DB_LOCAL_FILE
            )
        )
        print(_("Esegui prima la funzione di aggiornamento del DB FIDE."))
        return
    print(
        _(
            "\n--- Avvio Sincronizzazione Database Personale con Database FIDE Locale ---"
        )
    )
    try:
        with open(FIDE_DB_LOCAL_FILE, "r", encoding="utf-8") as f:
            fide_db = json.load(f)
        print(_("Database FIDE locale caricato con {} giocatori.").format(len(fide_db)))
    except Exception as e:
        print(
            _("ERRORE critico durante la lettura di '{}': {}").format(
                FIDE_DB_LOCAL_FILE, e
            )
        )
        return
    players_db = load_players_db()
    if not players_db:
        print(
            _(
                "Il tuo database personale dei giocatori è vuoto. Nessuna sincronizzazione da effettuare."
            )
        )
        return

    print(_("Analisi dei giocatori nel tuo database personale..."))

    all_potential_changes = []
    stats = {
        "id_associations": 0,
        "elo_updates": 0,
        "birth_date_updates": 0,
        "title_updates": 0,
        "k_factor_updates": 0,
    }

    # FASE 1: Colleziona le modifiche in silenzio
    for player_id, local_player in players_db.items():
        fide_id_str = local_player.get("fide_id_num_str", "0")
        fide_record = None
        new_fide_id = None
        is_ambiguous = False
        matches = []

        if fide_id_str and fide_id_str != "0":
            fide_record = fide_db.get(fide_id_str)
        else:  # Cerca per nome/cognome
            p_first_name = local_player.get("first_name", "").lower()
            p_last_name = local_player.get("last_name", "").lower()

            if p_first_name and p_last_name:
                matches = [
                    f_p
                    for f_p in fide_db.values()
                    if f_p.get("first_name", "").lower() == p_first_name
                    and f_p.get("last_name", "").lower() == p_last_name
                ]

                if len(matches) == 1:
                    new_fide_id = str(matches[0]["id_fide"])
                    fide_record = matches[0]
                elif len(matches) > 1:
                    is_ambiguous = True

        updates = {}
        if fide_record:
            # Elo Standard
            fide_elo = fide_record.get("elo_standard", 0)
            if fide_elo > 0 and fide_elo != local_player.get("current_elo"):
                updates["current_elo"] = fide_elo
                stats["elo_updates"] += 1

            # Titolo FIDE
            fide_title = fide_record.get("title", "")
            if fide_title and not local_player.get("fide_title"):
                updates["fide_title"] = fide_title
                stats["title_updates"] += 1

            # K-Factor
            fide_k = fide_record.get("k_factor")
            if fide_k is not None and fide_k != local_player.get("fide_k_factor"):
                updates["fide_k_factor"] = fide_k
                stats["k_factor_updates"] += 1

            # Anno Nascita
            fide_birth_year = fide_record.get("birth_year")
            if fide_birth_year and not local_player.get("birth_date"):
                updates["birth_date"] = f"{fide_birth_year}-01-01"
                stats["birth_date_updates"] += 1

        if new_fide_id:
            stats["id_associations"] += 1

        if new_fide_id or updates or is_ambiguous:
            all_potential_changes.append(
                {
                    "player_id": player_id,
                    "current_data": local_player,
                    "new_fide_id": new_fide_id,
                    "updates": updates,
                    "is_ambiguous": is_ambiguous,
                    "matches": matches,
                }
            )

    # FASE 2: Riepilogo
    if not all_potential_changes:
        print(
            _(
                "\nAnalisi completata. Il tuo database personale è già perfettamente sincronizzato!"
            )
        )
        return

    print(_("\n--- Sommario Aggiornamenti Disponibili ---"))
    if stats["id_associations"] > 0:
        print(
            _(" - {num} nuovi ID FIDE da associare").format(
                num=stats["id_associations"]
            )
        )
    if stats["elo_updates"] > 0:
        print(_(" - {num} aggiornamenti Elo").format(num=stats["elo_updates"]))
    if stats["birth_date_updates"] > 0:
        print(
            _(" - {num} aggiornamenti anno di nascita").format(
                num=stats["birth_date_updates"]
            )
        )
    if stats["title_updates"] > 0:
        print(
            _(" - {num} aggiornamenti titoli FIDE").format(num=stats["title_updates"])
        )
    if stats["k_factor_updates"] > 0:
        print(
            _(" - {num} aggiornamenti K-Factor").format(num=stats["k_factor_updates"])
        )

    ambiguous_count = sum(1 for c in all_potential_changes if c["is_ambiguous"])
    if ambiguous_count > 0:
        print(
            _(
                " - {num} giocatori con omonimi multipli (richiedono risoluzione manuale)"
            ).format(num=ambiguous_count)
        )
    print("-" * 42)

    # Scelta Modalità (ESCAPE = Tutto, INVIO = Passo-passo)
    print(
        _(
            "Premi ESCAPE per applicare TUTTI gli aggiornamenti non ambigui in automatico."
        )
    )
    print(_("Premi INVIO per decidere per ciascun aggiornamento passo-passo."))

    step_by_step = enter_escape(
        _("Scegli la modalità (INVIO = passo-passo | ESCAPE = applica tutti): ")
    )

    changes_applied = False

    # FASE 3: Applicazione
    for change in all_potential_changes:
        player_id = change["player_id"]
        player = change["current_data"]
        new_fide_id = change["new_fide_id"]
        updates = change["updates"]
        is_ambiguous = change["is_ambiguous"]
        matches = change["matches"]

        if not step_by_step:
            # Modalità "Applica Tutti"
            if is_ambiguous:
                print(
                    _(
                        "\nGiocatore: {} {} (ID Locale: {}) ha {} omonimi nel DB FIDE. Risoluzione manuale richiesta."
                    ).format(
                        player.get("first_name"),
                        player.get("last_name"),
                        player.get("id"),
                        len(matches),
                    )
                )
                for i, match in enumerate(matches):
                    print(
                        _(
                            " {}. FIDE ID: {}, FED: {}, Elo: {}, Anno Nascita: {}"
                        ).format(
                            i + 1,
                            match["id_fide"],
                            match["federation"],
                            match["elo_standard"],
                            match.get("birth_year"),
                        )
                    )
                print(_("   0. Nessuno di questi"))
                choice = input(_("   Scelta (0-{}): ").format(len(matches))).strip()
                if choice.isdigit() and 1 <= int(choice) <= len(matches):
                    chosen_match = matches[int(choice) - 1]
                    new_fide_id = str(chosen_match["id_fide"])
                    fide_elo = chosen_match.get("elo_standard", 0)
                    if fide_elo > 0 and fide_elo != player.get("current_elo"):
                        updates["current_elo"] = fide_elo
                    fide_title = chosen_match.get("title", "")
                    if fide_title and not player.get("fide_title"):
                        updates["fide_title"] = fide_title
                    fide_k = chosen_match.get("k_factor")
                    if fide_k is not None and fide_k != player.get("fide_k_factor"):
                        updates["fide_k_factor"] = fide_k
                    fide_birth_year = chosen_match.get("birth_year")
                    if fide_birth_year and not player.get("birth_date"):
                        updates["birth_date"] = f"{fide_birth_year}-01-01"
                else:
                    print(_("   Saltato."))
                    continue

            # Applica in silenzio (salvo i log base)
            player_record_to_update = players_db[player_id]
            if new_fide_id:
                player_record_to_update["fide_id_num_str"] = new_fide_id
            if updates:
                player_record_to_update.update(updates)
            changes_applied = True

        else:
            # Modalità "Passo-passo"
            print(
                _("\n--- Modifiche per: {} {} (ID: {}) ---").format(
                    player.get("first_name"), player.get("last_name"), player.get("id")
                )
            )

            if is_ambiguous:
                print(_("Trovati {} omonimi nel DB FIDE.").format(len(matches)))
                for i, match in enumerate(matches):
                    print(
                        _(
                            " {}. FIDE ID: {}, FED: {}, Elo: {}, Anno Nascita: {}"
                        ).format(
                            i + 1,
                            match["id_fide"],
                            match["federation"],
                            match["elo_standard"],
                            match.get("birth_year"),
                        )
                    )
                print(_("   0. Nessuno di questi"))
                choice = input(_("   Scelta (0-{}): ").format(len(matches))).strip()
                if choice.isdigit() and 1 <= int(choice) <= len(matches):
                    chosen_match = matches[int(choice) - 1]
                    new_fide_id = str(chosen_match["id_fide"])
                    fide_elo = chosen_match.get("elo_standard", 0)
                    if fide_elo > 0 and fide_elo != player.get("current_elo"):
                        updates["current_elo"] = fide_elo
                    fide_title = chosen_match.get("title", "")
                    if fide_title and not player.get("fide_title"):
                        updates["fide_title"] = fide_title
                    fide_k = chosen_match.get("k_factor")
                    if fide_k is not None and fide_k != player.get("fide_k_factor"):
                        updates["fide_k_factor"] = fide_k
                    fide_birth_year = chosen_match.get("birth_year")
                    if fide_birth_year and not player.get("birth_date"):
                        updates["birth_date"] = f"{fide_birth_year}-01-01"
                else:
                    print(_("Saltato."))
                    continue

            if new_fide_id:
                print(_(" -> Associa nuovo ID FIDE: {}").format(new_fide_id))
            if updates:
                for key, value in updates.items():
                    print(
                        _(" -> Aggiorna {}: da '{}' a '{}'").format(
                            key.replace("_", " ").title(),
                            player.get(key, _("N/D")),
                            value,
                        )
                    )

            if new_fide_id or updates:
                if enter_escape(
                    _("Applicare queste modifiche? (INVIO per Sì | ESCAPE per No): ")
                ):
                    player_record_to_update = players_db[player_id]
                    if new_fide_id:
                        player_record_to_update["fide_id_num_str"] = new_fide_id
                    if updates:
                        player_record_to_update.update(updates)
                    changes_applied = True
                    print(_("Modifiche applicate."))
                else:
                    print(_("Modifiche saltate."))

    if changes_applied:
        save_players_db(players_db)
        print(_("\nSincronizzazione completata e database personale salvato!"))
    else:
        print(_("\nNessuna modifica è stata apportata al database personale."))


def aggiorna_db_fide_locale():
    """
    Scarica l'ultimo rating list FIDE (XML), estrae un set di dati arricchito
    e lo salva in un file JSON locale (fide_ratings_local.json).
    Restituisce True in caso di successo, False altrimenti.
    """
    try:
        print(
            _("Download del file ZIP FIDE da: {url}").format(url=FIDE_XML_DOWNLOAD_URL)
        )
        print(
            _(
                "L'operazione potrebbe richiedere alcuni minuti a seconda della connessione..."
            )
        )
        zip_response = requests.get(FIDE_XML_DOWNLOAD_URL, timeout=120)
        zip_response.raise_for_status()

        print(_("Download completato. Apertura archivio ZIP in memoria..."))
        with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
            xml_filename = next(
                (name for name in zf.namelist() if name.lower().endswith(".xml")), None
            )

            if not xml_filename:
                print(_("ERRORE: Nessun file .xml trovato nell'archivio ZIP."))
                return False
            print(
                _("Estrazione ed elaborazione del file XML: {filename}...").format(
                    filename=xml_filename
                )
            )

            xml_content = zf.read(xml_filename)

            # --- INIZIO MODIFICA 1: FEEDBACK PER PARSING XML ---

            # Funzione che il thread eseguirà per stampare il feedback
            def print_feedback(stop_event, message):
                while not stop_event.wait(
                    5
                ):  # Attende 5 secondi. Se non viene fermato, stampa.
                    print(message)

            stop_parsing_feedback = threading.Event()
            feedback_msg_parsing = _(
                "  -> L'analisi del file XML è in corso, attendere..."
            )
            parsing_thread = threading.Thread(
                target=print_feedback,
                args=(stop_parsing_feedback, feedback_msg_parsing),
            )

            print(
                _(
                    "Analisi del file XML in corso (potrebbe richiedere più di un minuto)..."
                )
            )
            parsing_thread.daemon = (
                True  # Permette al programma di uscire anche se il thread è attivo
            )
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
            for player_node in root.findall("player"):
                fide_id_node = player_node.find("fideid")

                if fide_id_node is not None and fide_id_node.text:
                    fide_id_str = fide_id_node.text.strip()

                    # Estrai i dati usando i nomi dei tag XML
                    name = player_node.find("name").text

                    # Per l'Elo, ora estraiamo tutte e 3 le cadenze + K-Factor e Flag
                    rating_std_node = player_node.find("rating")
                    rating_rap_node = player_node.find("rapid_rating")
                    rating_blz_node = player_node.find("blitz_rating")
                    k_factor_node = player_node.find("k")
                    flag_node = player_node.find("flag")

                    rating_std = (
                        int(rating_std_node.text)
                        if rating_std_node is not None and rating_std_node.text
                        else 0
                    )

                    # Filtriamo i giocatori inattivi o senza rating standard, che sono meno rilevanti
                    if rating_std == 0 and (
                        flag_node is not None
                        and flag_node.text
                        and "i" in flag_node.text.lower()
                    ):
                        continue

                    last_name_fide, first_name_fide = name, ""
                    if "," in name:
                        parts = name.split(",", 1)
                        last_name_fide = parts[0].strip()
                        first_name_fide = parts[1].strip()

                    fide_players_db[fide_id_str] = {
                        "id_fide": int(fide_id_str),
                        "first_name": first_name_fide,
                        "last_name": last_name_fide,
                        "federation": player_node.find("country").text,
                        "title": player_node.find("title").text or "",
                        "sex": player_node.find("sex").text or "",
                        # Rinomino 'elo' per chiarezza e aggiungo gli altri
                        "elo_standard": rating_std,
                        "elo_rapid": int(rating_rap_node.text)
                        if rating_rap_node is not None and rating_rap_node.text
                        else 0,
                        "elo_blitz": int(rating_blz_node.text)
                        if rating_blz_node is not None and rating_blz_node.text
                        else 0,
                        "k_factor": int(k_factor_node.text)
                        if k_factor_node is not None and k_factor_node.text
                        else None,
                        "flag": flag_node.text if flag_node is not None else None,
                        "birth_year": int(b.text)
                        if (b := player_node.find("birthday")) is not None
                        and b.text
                        and b.text.isdigit()
                        else None,
                    }
                    player_count += 1
                    if player_count % 500000 == 0:
                        print(
                            _("  ... elaborati {count} giocatori...").format(
                                count=player_count
                            )
                        )
            print(
                _(
                    "Elaborazione completata. Trovati e salvati {count} giocatori FIDE."
                ).format(count=len(fide_players_db))
            )

            # --- INIZIO MODIFICA 2: FEEDBACK PER SCRITTURA JSON ---
            stop_json_feedback = threading.Event()
            feedback_msg_json = _(
                "  -> La scrittura del file JSON è in corso, attendere..."
            )
            json_thread = threading.Thread(
                target=print_feedback, args=(stop_json_feedback, feedback_msg_json)
            )

            print(
                _("Salvataggio del database JSON locale (potrebbe richiedere tempo)...")
            )
            json_thread.daemon = True
            json_thread.start()
            try:
                with open(FIDE_DB_LOCAL_FILE, "w", encoding="utf-8") as f_out:
                    json.dump(fide_players_db, f_out, indent=1)
            finally:
                stop_json_feedback.set()

            # --- FINE MODIFICA 2 ---

            print(
                _(
                    "Database FIDE locale 'fide_ratings_local.json' salvato con successo."
                )
            )
            return True  # Restituisce True in caso di successo
    except requests.exceptions.Timeout:
        print(_("ERRORE: Timeout durante il download del file."))
        return False
    except requests.exceptions.RequestException as e_req:
        print(_("ERRORE di rete: {error}").format(error=e_req))
        return False
    except Exception as e_main:
        print(
            _(
                "Si è verificato un errore imprevisto durante l'aggiornamento del DB FIDE: {error}"
            ).format(error=e_main)
        )
        traceback.print_exc()
        return False


def load_players_db():
    """Carica il database dei giocatori dal file JSON."""
    if os.path.exists(PLAYER_DB_FILE):
        try:
            with open(PLAYER_DB_FILE, "r", encoding="utf-8") as f:
                db_list = json.load(f)
                # Inizializza campi mancanti se necessario all'avvio
                for p in db_list:
                    medals_dict = p.setdefault("medals", {})
                    medals_dict.setdefault("gold", 0)
                    medals_dict.setdefault("silver", 0)
                    medals_dict.setdefault("bronze", 0)
                    medals_dict.setdefault(
                        "wood", 0
                    )  # <-- Aggiunto controllo specifico per 'wood'
                    p.setdefault("tournaments_played", [])
                    p.setdefault("fide_k_factor", None)
                return {p["id"]: p for p in db_list}
        except (json.JSONDecodeError, IOError) as e:
            print(
                _(
                    "Errore durante il caricamento del DB giocatori ({filename}): {error}"
                ).format(filename=PLAYER_DB_FILE, error=e)
            )
            print(_("Verrà creato un nuovo DB vuoto se si aggiungono giocatori."))
            return {}
    return {}


def save_players_db(players_db):
    """Salva il database dei giocatori nel file JSON e genera il file TXT."""
    if not players_db:
        pass  # Procedi a salvare anche se vuoto
    try:
        with open(PLAYER_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(list(players_db.values()), f, indent=1, ensure_ascii=False)
        save_players_db_txt(players_db)
    except IOError as e:
        print(
            _(
                "Errore durante il salvataggio del DB giocatori ({filename}): {error}"
            ).format(filename=PLAYER_DB_FILE, error=e)
        )
    except Exception as e:
        print(
            _("Errore imprevisto durante il salvataggio del DB: {error}").format(
                error=e
            )
        )


def save_players_db_txt(players_db):
    """Genera un file TXT leggibile con lo stato del database giocatori,
    includendo partite giocate totali e K-Factor attuale."""
    try:
        with open(
            PLAYER_DB_TXT_FILE, "w", encoding="utf-8-sig"
        ) as f:  # Usiamo utf-8-sig
            now = datetime.now()
            current_date_iso = now.strftime(
                DATE_FORMAT_ISO
            )  # Data corrente per calcolo K
            f.write(
                _("Report Database Giocatori Tornello - {date} {time}\n").format(
                    date=format_date_locale(now.date()), time=now.strftime("%H:%M:%S")
                )
            )
            f.write("=" * 40 + "\n\n")
            sorted_players = sorted(
                players_db.values(),
                key=lambda p: (p.get("last_name", ""), p.get("first_name", "")),
            )
            if not sorted_players:
                f.write(_("Il database dei giocatori è vuoto.\n"))
                return
            for player in sorted_players:
                sesso = str(player.get("sex", "N/D")).upper()
                federazione_giocatore = str(player.get("federation", "N/D")).upper()
                fide_id_numerico = str(player.get("fide_id_num_str", "N/D"))
                titolo_fide = str(player.get("fide_title", "")).strip().upper()
                titolo_prefix = f"{titolo_fide} " if titolo_fide else ""
                player_id_display = player.get("id", "N/D")
                first_name_display = player.get("first_name", "N/D")
                last_name_display = player.get("last_name", "N/D")
                elo_display = player.get("current_elo", "N/D")
                f.write(
                    f"ID: {player_id_display}, {titolo_prefix}{first_name_display} {last_name_display}, Elo: {elo_display}\n"
                )
                f.write(
                    _(
                        "\tSesso: {sesso}, Federazione Giocatore: {federazione}, ID FIDE num: {fide_id}\n"
                    ).format(
                        sesso=sesso,
                        federazione=federazione_giocatore,
                        fide_id=fide_id_numerico,
                    )
                )
                games_played_total = player.get("games_played", 0)
                current_k_factor = get_k_factor(
                    player, current_date_iso
                )  # Assicurati che get_k_factor sia accessibile
                registration_date_display = format_date_locale(
                    player.get("registration_date")
                )
                f.write(
                    _(
                        "\tPartite Valutate Totali: {games}, K-Factor Stimato: {k_factor}, Data Iscrizione DB: {reg_date}\n"
                    ).format(
                        games=games_played_total,
                        k_factor=current_k_factor,
                        reg_date=registration_date_display,
                    )
                )
                birth_date_val = player.get("birth_date")  # Formato YYYY-MM-DD o None
                birth_date_display = (
                    format_date_locale(birth_date_val) if birth_date_val else "N/D"
                )
                f.write(
                    _("\tData Nascita: {birth_date}\n").format(
                        birth_date=birth_date_display
                    )
                )
                medals = player.get(
                    "medals", {"gold": 0, "silver": 0, "bronze": 0, "wood": 0}
                )
                f.write(
                    _(
                        "\tMedagliere: Oro: {gold}, Argento: {silver}, Bronzo: {bronze}, Legno: {wood} in "
                    ).format(
                        gold=medals.get("gold", 0),
                        silver=medals.get("silver", 0),
                        bronze=medals.get("bronze", 0),
                        wood=medals.get("wood", 0),
                    )
                )
                tournaments = player.get("tournaments_played", [])
                f.write(_("({count}) tornei:\n").format(count=len(tournaments)))
                if tournaments:
                    try:
                        tournaments_sorted = sorted(
                            tournaments,
                            key=lambda t: datetime.strptime(
                                t.get("date_completed", "1900-01-01"), DATE_FORMAT_ISO
                            ),
                            reverse=True,
                        )
                    except ValueError:
                        tournaments_sorted = (
                            tournaments  # Mantieni ordine originale se date non valide
                        )
                    for t in tournaments_sorted:  # Non serve più l'indice 'i' separato
                        rank_val = t.get("rank", "?")
                        t_name = t.get("tournament_name", _("Nome Torneo Mancante"))
                        start_date_iso = t.get(
                            "date_started"
                        )  # Prende la nuova data ISO di inizio
                        end_date_iso = t.get("date_completed")  # Data di completamento
                        rank_formatted = format_rank_ordinal(
                            rank_val
                        )  # Usa la nuova funzione helper
                        start_date_formatted = format_date_locale(start_date_iso)
                        end_date_formatted = format_date_locale(end_date_iso)
                        history_line = _(
                            "{rank} su {total} in {name} - {start} - {end}"
                        ).format(
                            rank=rank_formatted,
                            total=t.get("total_players", "?"),
                            name=t_name,
                            start=start_date_formatted,
                            end=end_date_formatted,
                        )
                        f.write(f"\t{history_line}\n")
                else:
                    f.write(_("\tNessuno\n"))
                f.write("\t" + "-" * 30 + "\n")
    except IOError as e:
        print(
            _(
                "Errore durante il salvataggio del file TXT del DB giocatori ({filename}): {error}"
            ).format(filename=PLAYER_DB_TXT_FILE, error=e)
        )
    except Exception as e:
        print(
            _("Errore imprevisto durante il salvataggio del TXT del DB: {}").format(e)
        )
        traceback.print_exc()  # Stampa traceback per errori non gestiti


def crea_nuovo_giocatore_nel_db(
    players_db,
    first_name,
    last_name,
    elo,
    fide_title,
    sex,
    federation,
    fide_id_num_str,
    birth_date,
    experienced,
    silent=False,
):
    """
    Crea SEMPRE un nuovo giocatore nel database principale (players_db),
    generando un ID univoco che gestisce gli omonimi.
    Salva il database principale aggiornato.
    Restituisce il nuovo ID del giocatore creato o None in caso di fallimento.
    """
    norm_first = first_name.strip().title()
    norm_last = last_name.strip().title()

    if not norm_first or not norm_last:
        print(
            _(
                "Errore: Nome e Cognome non possono essere vuoti per la creazione del giocatore nel DB."
            )
        )
        return None
    # Logica di Generazione ID (gestisce omonimi creando ID univoci come BATGA001, BATGA002, ecc.)
    last_part_cleaned = "".join(norm_last.split())
    first_part_cleaned = "".join(norm_first.split())
    last_initials = last_part_cleaned[:3].upper().ljust(3, "X")
    first_initials = first_part_cleaned[:2].upper().ljust(2, "X")
    base_id = f"{last_initials}{first_initials}"
    if (
        not base_id or base_id == "XXXXX"
    ):  # Fallback nel caso nome/cognome fossero invalidi (improbabile qui)
        base_id = "GIOCX"
    count = 1
    new_player_id = f"{base_id}{count:03d}"
    max_attempts_id_gen = 1000  # Numero massimo di tentativi per trovare un ID univoco
    current_attempt_id_gen = 0
    while new_player_id in players_db and current_attempt_id_gen < max_attempts_id_gen:
        count += 1
        new_player_id = f"{base_id}{count:03d}"
        current_attempt_id_gen += 1
        if count > 999:  # Se i 3 digit non bastano (molti omonimi)
            # Prova con un suffisso basato su timestamp per maggiore unicità
            timestamp_suffix = datetime.now().strftime("%S%f")[
                -4:
            ]  # Ultime 4 cifre da secondi+microsecondi
            candidate_id = f"{base_id}{timestamp_suffix}"
            if candidate_id not in players_db:
                new_player_id = candidate_id
                break
            else:  # Estrema rarità, usa un ID quasi certamente univoco
                new_player_id = f"TEMP_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                if (
                    new_player_id in players_db
                ):  # Praticamente impossibile, ma per completezza
                    print(
                        _(
                            "ERRORE CRITICO: Fallimento catastrofico generazione ID per {} {}."
                        ).format(norm_first, norm_last)
                    )
                    return None
                break
    if new_player_id in players_db and current_attempt_id_gen >= max_attempts_id_gen:
        print(
            _(
                "ERRORE CRITICO: Impossibile generare ID univoco per {first_name} {last_name} dopo {attempts} tentativi."
            ).format(
                first_name=norm_first, last_name=norm_last, attempts=max_attempts_id_gen
            )
        )
        return None

    if not silent:
        print(
            _(
                "Creazione nuovo giocatore nel DB principale: {} {} con il nuovo ID: {}"
            ).format(norm_first, norm_last, new_player_id)
        )
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
        "experienced": experienced,
    }
    players_db[new_player_id] = new_player_data_for_db
    save_players_db(players_db)  # Salva immediatamente il DB principale aggiornato
    if not silent:
        print(
            _(
                "Nuovo giocatore '{first_name} {last_name}' (ID: {player_id}) aggiunto al database principale."
            ).format(
                first_name=norm_first, last_name=norm_last, player_id=new_player_id
            )
        )
    return new_player_id
