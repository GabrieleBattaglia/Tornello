import os
import json
import zipfile
import io
import requests
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime
from config import (
    FIDE_DB_LOCAL_FILE,
    PLAYER_DB_FILE,
    PLAYER_DB_TXT_FILE,
    DATE_FORMAT_ISO,
    FIDE_XML_DOWNLOAD_URL,
)
from fide_db import (
    create_fide_db,
    bulk_insert_players,
    cleanup_legacy_json,
    get_player_by_fide_id,
    search_players_by_name,
    fide_db_exists,
    get_player_count,
)
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
    Utilizza il database SQLite locale tramite il modulo fide_db.
    """
    if not fide_db_exists():
        return []

    search_term = search_term.strip()
    if not search_term:
        return []

    # Ricerca per ID FIDE esatto
    if search_term.isdigit():
        player = get_player_by_fide_id(search_term)
        return [player] if player else []

    # Ricerca testuale tramite FTS5
    from fide_db import search_players

    return search_players(search_term, limit=50)


def sincronizza_db_personale():
    """
    Carica il DB FIDE locale e il DB personale, li confronta, e propone
    aggiornamenti e associazioni di ID FIDE. Mostra un sommario e permette
    di applicare tutto in blocco o valutare singolarmente.
    """
    if not fide_db_exists():
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
    player_count = get_player_count()
    print(_("Database FIDE locale disponibile con {} giocatori.").format(player_count))
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
            fide_record = get_player_by_fide_id(fide_id_str)
        else:  # Cerca per nome/cognome
            p_first_name = local_player.get("first_name", "")
            p_last_name = local_player.get("last_name", "")

            if p_first_name and p_last_name:
                matches = search_players_by_name(p_first_name, p_last_name)

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

            # Nuovi campi FIDE
            fide_fields_to_sync = [
                ("elo_rapid", "elo_rapid"),
                ("elo_blitz", "elo_blitz"),
                ("games", "fide_standard_games"),
                ("rapid_games", "fide_rapid_games"),
                ("rapid_k", "fide_rapid_k"),
                ("blitz_games", "fide_blitz_games"),
                ("blitz_k", "fide_blitz_k"),
                ("w_title", "w_title"),
                ("o_title", "o_title"),
                ("foa_title", "foa_title"),
                ("flag", "flag"),
            ]
            for fide_key, local_key in fide_fields_to_sync:
                fide_val = fide_record.get(fide_key)
                if (
                    fide_val is not None
                    and fide_val != ""
                    and fide_val != local_player.get(local_key)
                ):
                    if "elo" in fide_key and fide_val == 0:
                        continue
                    updates[local_key] = fide_val
                    stats["other_updates"] = stats.get("other_updates", 0) + 1

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
    print(_("Premi ESCAPE per aggiornare in massa tutti i giocatori in automatico."))
    print(
        _(
            "Premi INVIO per confermare manualmente l'aggiornamento per ogni singolo giocatore."
        )
    )

    step_by_step = enter_escape(
        _(
            "Scegli la modalità (INVIO = Conferma singola | ESCAPE = Aggiorna in massa): "
        )
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

                    # Nuovi campi FIDE
                    fide_fields_to_sync = [
                        ("elo_rapid", "fide_elo_rapid"),
                        ("elo_blitz", "fide_elo_blitz"),
                        ("games", "fide_games"),
                        ("rapid_games", "fide_rapid_games"),
                        ("rapid_k", "fide_rapid_k"),
                        ("blitz_games", "fide_blitz_games"),
                        ("blitz_k", "fide_blitz_k"),
                        ("w_title", "fide_w_title"),
                        ("o_title", "fide_o_title"),
                        ("foa_title", "fide_foa_title"),
                        ("flag", "fide_flag"),
                    ]
                    for fide_key, local_key in fide_fields_to_sync:
                        fide_val = chosen_match.get(fide_key)
                        if (
                            fide_val is not None
                            and fide_val != ""
                            and fide_val != player.get(local_key)
                        ):
                            if "elo" in fide_key and fide_val == 0:
                                continue
                            updates[local_key] = fide_val
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

                    # Nuovi campi FIDE
                    fide_fields_to_sync = [
                        ("elo_rapid", "fide_elo_rapid"),
                        ("elo_blitz", "fide_elo_blitz"),
                        ("games", "fide_games"),
                        ("rapid_games", "fide_rapid_games"),
                        ("rapid_k", "fide_rapid_k"),
                        ("blitz_games", "fide_blitz_games"),
                        ("blitz_k", "fide_blitz_k"),
                        ("w_title", "fide_w_title"),
                        ("o_title", "fide_o_title"),
                        ("foa_title", "fide_foa_title"),
                        ("flag", "fide_flag"),
                    ]
                    for fide_key, local_key in fide_fields_to_sync:
                        fide_val = chosen_match.get(fide_key)
                        if (
                            fide_val is not None
                            and fide_val != ""
                            and fide_val != player.get(local_key)
                        ):
                            if "elo" in fide_key and fide_val == 0:
                                continue
                            updates[local_key] = fide_val
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


class ProgressFileObject:
    """Wrapper per file-like object che segnala il progresso della lettura al callback."""

    def __init__(self, fileobj, callback, total_size):
        self.fileobj = fileobj
        self.callback = callback
        self.total_size = total_size
        self.bytes_read = 0

    def read(self, size=-1):
        data = self.fileobj.read(size)
        self.bytes_read += len(data)
        if self.callback:
            try:
                self.callback("processing", self.bytes_read, self.total_size)
            except Exception:
                pass
        return data

    def readline(self, limit=-1):
        data = self.fileobj.readline(limit)
        self.bytes_read += len(data)
        if self.callback:
            try:
                self.callback("processing", self.bytes_read, self.total_size)
            except Exception:
                pass
        return data

    def close(self):
        self.fileobj.close()


def aggiorna_db_fide_locale(progress_callback=None, stats_output=None):
    """
    Scarica l'ultimo rating list FIDE (XML), lo elabora e salva i dati
    in un database SQLite locale (fide_ratings.db).
    Supporta un callback per notificare il progresso di scaricamento e analisi
    e un dizionario per salvare le statistiche dell'operazione.
    Restituisce True in caso di successo, False altrimenti.
    """
    import time
    from fide_db import (
        get_player_count,
    )

    old_count = get_player_count()
    start_download = time.time()

    try:
        print(
            _("Download del file ZIP FIDE da: {url}").format(url=FIDE_XML_DOWNLOAD_URL)
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        zip_response = requests.get(
            FIDE_XML_DOWNLOAD_URL, headers=headers, timeout=(30, 600), stream=True
        )
        zip_response.raise_for_status()

        total_length = zip_response.headers.get("content-length")
        chunks = []

        if total_length is None:
            # Nessun content-length disponibile, scarica normalmente
            chunks.append(zip_response.content)
        else:
            total_bytes = int(total_length)
            bytes_downloaded = 0
            # Usa chunk da 256KB per uno scaricamento efficiente
            for chunk in zip_response.iter_content(chunk_size=256 * 1024):
                if chunk:
                    chunks.append(chunk)
                    bytes_downloaded += len(chunk)
                    if progress_callback:
                        try:
                            progress_callback("download", bytes_downloaded, total_bytes)
                        except Exception:
                            pass

        download_duration = time.time() - start_download
        print(
            _(
                "Download completato in {duration:.2f}s. Apertura archivio ZIP in memoria..."
            ).format(duration=download_duration)
        )

        start_processing = time.time()
        zip_data = b"".join(chunks)

        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            xml_filename = next(
                (name for name in zf.namelist() if name.lower().endswith(".xml")), None
            )

            if not xml_filename:
                print(_("ERRORE: Nessun file .xml trovato nell'archivio ZIP."))
                return False

            xml_info = zf.getinfo(xml_filename)
            xml_size = xml_info.file_size

            print(
                _(
                    "Estrazione ed elaborazione del file XML: {filename} ({size_mb:.1f} MB)..."
                ).format(filename=xml_filename, size_mb=xml_size / (1024 * 1024))
            )

            # Crea il database SQLite vuoto
            create_fide_db()

            raw_xml_file = zf.open(xml_filename)
            progress_xml_file = ProgressFileObject(
                raw_xml_file, progress_callback, xml_size
            )

            # Generatore che produce record giocatori dal file XML
            def parse_xml_players():
                context = ET.iterparse(progress_xml_file, events=("end",))
                parse_count = 0

                for _event, elem in context:
                    if elem.tag == "player":
                        fide_id_node = elem.find("fideid")
                        if fide_id_node is not None and fide_id_node.text:
                            fide_id_str = fide_id_node.text.strip()
                            name = (
                                elem.find("name").text
                                if elem.find("name") is not None
                                and elem.find("name").text
                                else ""
                            )

                            last_name_fide, first_name_fide = name, ""
                            if "," in name:
                                parts = name.split(",", 1)
                                last_name_fide = parts[0].strip()
                                first_name_fide = parts[1].strip()

                            def get_text(tag, default=""):
                                node = elem.find(tag)
                                return (
                                    node.text
                                    if node is not None and node.text
                                    else default
                                )

                            def get_int(tag, default=0):
                                text = get_text(tag, "")
                                return (
                                    int(text) if text.lstrip("-").isdigit() else default
                                )

                            yield {
                                "fide_id": int(fide_id_str),
                                "first_name": first_name_fide,
                                "last_name": last_name_fide,
                                "federation": get_text("country"),
                                "sex": get_text("sex"),
                                "title": get_text("title"),
                                "w_title": get_text("w_title"),
                                "o_title": get_text("o_title"),
                                "foa_title": get_text("foa_title"),
                                "elo_standard": get_int("rating"),
                                "games": get_int("games"),
                                "k_factor": get_int("k", default=None),
                                "elo_rapid": get_int("rapid_rating"),
                                "rapid_games": get_int("rapid_games"),
                                "rapid_k": get_int("rapid_k", default=None),
                                "elo_blitz": get_int("blitz_rating"),
                                "blitz_games": get_int("blitz_games"),
                                "blitz_k": get_int("blitz_k", default=None),
                                "birth_year": get_int("birthday", default=None),
                                "flag": get_text("flag", default=None),
                            }
                            parse_count += 1
                            if parse_count % 5000 == 0:
                                time.sleep(0.001)

                        elem.clear()
                progress_xml_file.close()

            player_count = bulk_insert_players(
                parse_xml_players(), progress_callback=None
            )

            processing_duration = time.time() - start_processing
            new_count = get_player_count()

            if stats_output is not None:
                stats_output["old_count"] = old_count
                stats_output["new_count"] = new_count
                stats_output["saved_count"] = player_count
                stats_output["download_time"] = download_duration
                stats_output["processing_time"] = processing_duration

            print(
                _(
                    "Elaborazione completata. Trovati e salvati {count} giocatori FIDE."
                ).format(count=player_count)
            )

            # Elimina il vecchio file JSON se presente
            if cleanup_legacy_json():
                print(_("Vecchio file JSON FIDE rimosso."))

            print(_("Database FIDE locale 'fide_ratings.db' salvato con successo."))
            return True
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
    """Carica il database dei giocatori dal file JSON, eseguendo la migrazione se necessario."""
    if os.path.exists(PLAYER_DB_FILE):
        try:
            with open(PLAYER_DB_FILE, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            # Rileva schema
            schema_version = 1
            if isinstance(raw_data, dict):
                schema_version = raw_data.get("schema_version", 1)
                db_list = raw_data.get("players", [])
            else:
                db_list = raw_data

            # Esegui migrazione a schema_version 2 se necessario
            needs_save = False
            if schema_version < 2 or isinstance(raw_data, list):
                print(
                    _(
                        "\nInfo: Rilevato database giocatori in formato obsoleto. Avvio migrazione a schema v2..."
                    )
                )
                needs_save = True

            for p in db_list:
                # Campi base v1
                medals_dict = p.setdefault("medals", {})
                medals_dict.setdefault("gold", 0)
                medals_dict.setdefault("silver", 0)
                medals_dict.setdefault("bronze", 0)
                medals_dict.setdefault("wood", 0)
                p.setdefault("tournaments_played", [])
                p.setdefault("fide_k_factor", None)

                # Nuovi campi v2 (Issue #14)
                p.setdefault("elo_club", 0.0)
                p.setdefault("elo_rapid", 0.0)
                p.setdefault("elo_blitz", 0.0)
                p.setdefault("fide_rapid_k", None)
                p.setdefault("fide_blitz_k", None)
                p.setdefault("fide_standard_games", 0)
                p.setdefault("fide_rapid_games", 0)
                p.setdefault("fide_blitz_games", 0)
                p.setdefault("w_title", "")
                p.setdefault("o_title", "")
                p.setdefault("foa_title", "")
                p.setdefault("flag", "")

            players_map = {p["id"]: p for p in db_list}

            if needs_save:
                save_players_db(players_map)
                print(_("Migrazione completata con successo."))

            return players_map
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
        data_to_save = {"schema_version": 2, "players": list(players_db.values())}
        with open(PLAYER_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=1, ensure_ascii=False)
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
                    f"ID: {player_id_display}, {titolo_prefix}{first_name_display} {last_name_display}\n"
                )

                extra_titles = [
                    player.get(t)
                    for t in ["fide_w_title", "fide_o_title", "fide_foa_title"]
                    if player.get(t)
                ]
                extra_titles_str = (
                    f", Titoli Extra: {', '.join(extra_titles)}" if extra_titles else ""
                )

                f.write(
                    _(
                        "\tSesso: {sesso}, Federazione: {federazione}, ID FIDE: {fide_id}, Flag: {flag}{extra}\n"
                    ).format(
                        sesso=sesso,
                        federazione=federazione_giocatore,
                        fide_id=fide_id_numerico,
                        flag=player.get("fide_flag") or "N/D",
                        extra=extra_titles_str,
                    )
                )
                f.write(
                    f"\tElo Standard: {elo_display} (Partite FIDE: {player.get('fide_games', 'N/D')})\n"
                )
                f.write(
                    f"\tElo Rapid: {player.get('fide_elo_rapid', 'N/D')} (Partite FIDE: {player.get('fide_rapid_games', 'N/D')}, K: {player.get('fide_rapid_k', 'N/D')})\n"
                )
                f.write(
                    f"\tElo Blitz: {player.get('fide_elo_blitz', 'N/D')} (Partite FIDE: {player.get('fide_blitz_games', 'N/D')}, K: {player.get('fide_blitz_k', 'N/D')})\n"
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


def generate_player_id(first_name, last_name, players_db_dict):
    """Genera ID univoco per un giocatore, gestendo gli omonimi (es. BATGA001, BATGA002, ecc.)."""
    norm_first = first_name.strip().title()
    norm_last = last_name.strip().title()
    if not norm_first or not norm_last:
        return None
    last_initials = "".join(norm_last.split())[:3].upper().ljust(3, "X")
    first_initials = "".join(norm_first.split())[:2].upper().ljust(2, "X")
    base_id = f"{last_initials}{first_initials}"
    if not base_id or base_id == "XXXXX":
        base_id = "GIOCX"
    count = 1
    new_id = f"{base_id}{count:03d}"
    max_attempts = 1000
    current_attempt = 0
    while new_id in players_db_dict and current_attempt < max_attempts:
        count += 1
        new_id = f"{base_id}{count:03d}"
        current_attempt += 1
        if count > 999:
            timestamp_suffix = datetime.now().strftime("%S%f")
            new_id = f"{base_id}{timestamp_suffix[-4:]}"
            if new_id in players_db_dict:
                # Estrema rarità, usa un ID con timestamp esteso
                new_id = f"TEMP_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                if new_id in players_db_dict:
                    return None
            break
    if new_id in players_db_dict and current_attempt >= max_attempts:
        return None
    return new_id


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
    elo_club=0,
    elo_rapid=0,
    elo_blitz=0,
    fide_k_factor=None,
    fide_rapid_k=None,
    fide_blitz_k=None,
    fide_standard_games=0,
    fide_rapid_games=0,
    fide_blitz_games=0,
    w_title="",
    o_title="",
    foa_title="",
    flag="",
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

    new_player_id = generate_player_id(norm_first, norm_last, players_db)
    if not new_player_id:
        print(
            _(
                "ERRORE CRITICO: Impossibile generare ID univoco per {first_name} {last_name}."
            ).format(first_name=norm_first, last_name=norm_last)
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
        "elo_club": elo_club,
        "elo_rapid": elo_rapid,
        "elo_blitz": elo_blitz,
        "fide_k_factor": fide_k_factor,
        "fide_rapid_k": fide_rapid_k,
        "fide_blitz_k": fide_blitz_k,
        "fide_standard_games": fide_standard_games,
        "fide_rapid_games": fide_rapid_games,
        "fide_blitz_games": fide_blitz_games,
        "w_title": w_title,
        "o_title": o_title,
        "foa_title": foa_title,
        "flag": flag,
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


def allinea_giocatori_con_database(players_list, players_db, category="standard"):
    """
    Allinea gli initial_elo e i titoli dei giocatori in un torneo con
    l'ultimo stato presente nel database dei giocatori.
    Restituisce il numero di giocatori effettivamente aggiornati.
    """
    from stats import get_initial_elo_for_tournament

    aggiornati = 0
    for tp in players_list:
        # Supporta sia dict (v8) che oggetti Player (v9)
        p_id = tp.get("id") if isinstance(tp, dict) else tp.id
        if p_id in players_db:
            db_p = players_db[p_id]
            db_elo = get_initial_elo_for_tournament(db_p, category)
            if isinstance(tp, dict):
                if db_elo > 0 and db_elo != tp.get("initial_elo"):
                    tp["initial_elo"] = db_elo
                    if "elo" in tp:
                        tp["elo"] = db_elo
                    aggiornati += 1
                db_title = db_p.get("fide_title", "")
                if db_title and db_title != tp.get("fide_title", ""):
                    tp["fide_title"] = db_title
            else:
                if db_elo > 0 and db_elo != tp.initial_elo:
                    tp.initial_elo = db_elo
                    aggiornati += 1
                db_title = db_p.get("fide_title", "")
                if db_title and db_title != tp.fide_title:
                    tp.fide_title = db_title
    return aggiornati
