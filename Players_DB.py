# Data concepimento 27 aprile 2025 by Gemini 2.5 (Refactored per Tornello 8.8)
# gestore Players_DB.py
import os
import sys
from datetime import datetime

# --- Inizializzazione Ambiente e Moduli Tornello ---
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from GBUtils import polipo, dgt

    lingua_rilevata, _ = polipo(source_language="it")
    import builtins

    builtins._ = _
except ImportError:
    print("ATTENZIONE: Libreria GBUtils non trovata. Impossibile avviare il tool.")
    sys.exit(1)

from config import DATE_FORMAT_ISO, DEFAULT_ELO
from utils import format_date_locale, format_rank_ordinal, sanitize_filename
from ui import get_input_with_default
from db_players import load_players_db, save_players_db, crea_nuovo_giocatore_nel_db

VERSION = "4.4.0 (Modulo Tornello)"


# --- Helper specifici per lo script ---
def generate_player_id(first_name, last_name, players_db_dict):
    """Genera ID per il rinominamento, logica estratta dal vecchio script."""
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
                return None
            break
    if new_id in players_db_dict and current_attempt >= max_attempts:
        return None
    return new_id


def find_players_partial(search_term, players_db_dict):
    matches = []
    search_lower = search_term.strip().lower()
    if not search_lower:
        return matches

    search_terms = search_lower.split()

    for p_data_item in players_db_dict.values():
        searchable_string = f"{p_data_item.get('first_name', '')} {p_data_item.get('last_name', '')} {p_data_item.get('id', '')} {p_data_item.get('fide_title', '')} {p_data_item.get('fide_id_num_str', '')}".lower()
        if all(term in searchable_string for term in search_terms):
            matches.append(p_data_item)

    return matches


def display_player_details(player_data):
    print(_("\n--- Scheda Giocatore Dettagliata ---"))
    if not player_data:
        print(_("Dati giocatore non validi o non trovati."))
        return

    title_prefix = (
        f"{player_data.get('fide_title', '')} " if player_data.get("fide_title") else ""
    )
    print(f"{_('ID'):<30}: {player_data.get('id', 'N/D')}")
    print(
        f"{_('Nome Completo'):<30}: {title_prefix}{player_data.get('first_name', 'N/D')} {player_data.get('last_name', 'N/D')}"
    )
    print(
        f"{_('Titolo FIDE'):<30}: {player_data.get('fide_title', 'N/D') if player_data.get('fide_title') else _('Nessuno')}"
    )
    print(f"{_('Elo Corrente'):<30}: {player_data.get('current_elo', 'N/D')}")
    print(f"{_('Sesso'):<30}: {str(player_data.get('sex', 'N/D')).upper()}")
    print(
        f"{_('Federazione'):<30}: {str(player_data.get('federation', 'N/D')).upper()}"
    )
    print(f"{_('ID FIDE Numerico'):<30}: {player_data.get('fide_id_num_str', 'N/D')}")
    print(
        f"{_('Data Nascita'):<30}: {format_date_locale(player_data.get('birth_date'))}"
    )
    print(
        f"{_('Data Registrazione DB'):<30}: {format_date_locale(player_data.get('registration_date'))}"
    )
    print(
        f"{_('Partite Giocate (valutate)'):<30}: {player_data.get('games_played', 0)}"
    )

    experienced_val_str = _("Sì") if player_data.get("experienced", False) else _("No")
    print(f"{_('Esperienza Pregressa Signif.'):<30}: {experienced_val_str}")

    medals = player_data.get("medals", {})
    print(
        f"{_('Medagliere'):<30}: Oro: {medals.get('gold', 0)}, Argento: {medals.get('silver', 0)}, Bronzo: {medals.get('bronze', 0)}, Legno: {medals.get('wood', 0)}"
    )

    tournaments = player_data.get("tournaments_played", [])
    print(f"{_('Storico Tornei Giocati'):<30}: {len(tournaments)} registrati")
    if tournaments:
        try:
            tournaments_s_list = sorted(
                tournaments,
                key=lambda t_item: datetime.strptime(
                    t_item.get("date_completed", "1900-01-01"), DATE_FORMAT_ISO
                ),
                reverse=True,
            )
        except:
            tournaments_s_list = tournaments
        for i, t_rec_item in enumerate(tournaments_s_list):
            total_p_val = t_rec_item.get("total_players", "?")
            start_d = format_date_locale(t_rec_item.get("date_started"))
            end_d = format_date_locale(t_rec_item.get("date_completed"))
            print(
                f"  {i + 1}. {format_rank_ordinal(t_rec_item.get('rank', '?'))} su {total_p_val} in '{t_rec_item.get('tournament_name', 'N/D')}'"
            )
            print(
                f"     Date: {start_d} - {end_d} (ID Torneo: {t_rec_item.get('tournament_id', 'N/A')})"
            )
    print("-" * 40)


def add_new_player(players_db_main_dict):
    print(_("\n--- Aggiunta Nuovo Giocatore ---"))
    first_name = get_input_with_default(_("Nome: ")).title()
    if not first_name:
        print(_("Nome richiesto."))
        return False
    last_name = get_input_with_default(_("Cognome: ")).title()
    if not last_name:
        print(_("Cognome richiesto."))
        return False

    elo_val = dgt(
        f"{_('Elo Corrente')} (default {int(DEFAULT_ELO)})",
        kind="i",
        imin=500,
        imax=4000,
        default=int(DEFAULT_ELO),
    )
    fide_title_new = get_input_with_default(
        _("Titolo FIDE (es. FM, o vuoto per nessuno):"), ""
    ).upper()[:3]

    sex_new = ""
    while True:
        sex_input = get_input_with_default(_("Sesso (m/w):"), "m").lower()
        if sex_input in ["m", "w"]:
            sex_new = sex_input
            break
        print(_("Input non valido. Usa 'm' o 'w'."))

    federation_new = (
        get_input_with_default(_("Federazione (3 lettere):"), "ITA").upper()[:3]
        or "ITA"
    )
    fide_id_num_new = get_input_with_default(
        _("ID FIDE Numerico (cifre, '0' se N/D):"), "0"
    )
    if not fide_id_num_new.isdigit():
        fide_id_num_new = "0"

    birth_date_str_new = None
    while True:
        bdate_input = get_input_with_default(
            _("Data di nascita ({date_format} o vuoto):").format(
                date_format=DATE_FORMAT_ISO
            ),
            "",
        )
        if not bdate_input:
            break
        try:
            datetime.strptime(bdate_input, DATE_FORMAT_ISO)
            birth_date_str_new = bdate_input
            break
        except ValueError:
            print(
                _("Formato data non valido. Usa {date_format}.").format(
                    date_format=DATE_FORMAT_ISO
                )
            )

    experienced_new_val = False
    while True:
        exp_input_str = get_input_with_default(
            _("Giocatore con esperienza pregressa significativa? (s/n):"), "n"
        ).lower()
        if exp_input_str == "s":
            experienced_new_val = True
            break
        elif exp_input_str == "n":
            experienced_new_val = False
            break
        print(_("Risposta non valida. Inserisci 's' o 'n'."))

    new_id = crea_nuovo_giocatore_nel_db(
        players_db_main_dict,
        first_name,
        last_name,
        float(elo_val),
        fide_title_new,
        sex_new,
        federation_new,
        fide_id_num_new,
        birth_date_str_new,
        experienced_new_val,
        silent=False,
    )
    if new_id:
        display_player_details(players_db_main_dict[new_id])
        return True
    return False


def edit_player_data(player_id_to_edit, players_db_dict_ref):
    if player_id_to_edit not in players_db_dict_ref:
        print(
            _("Errore: Giocatore con ID {id} non trovato.").format(id=player_id_to_edit)
        )
        return False, player_id_to_edit

    player_data_ref = players_db_dict_ref[player_id_to_edit]
    original_id = player_data_ref["id"]

    print(
        _("\n--- Modifica Giocatore ID: {id} ({first} {last}) ---").format(
            id=original_id,
            first=player_data_ref.get("first_name"),
            last=player_data_ref.get("last_name"),
        )
    )
    display_player_details(player_data_ref)
    print(_("--- Inserisci nuovi valori o premi Invio per mantenere i correnti ---"))

    original_first_name = player_data_ref.get("first_name", "")
    new_first_name = get_input_with_default(_("Nome"), original_first_name).title()
    original_last_name = player_data_ref.get("last_name", "")
    new_last_name = get_input_with_default(_("Cognome"), original_last_name).title()

    final_id_for_player = original_id

    if (new_first_name and new_first_name != original_first_name) or (
        new_last_name and new_last_name != original_last_name
    ):
        if new_first_name and new_last_name:
            print(_("Nome o cognome modificati."))
            if (
                get_input_with_default(
                    _(
                        "Vuoi tentare di rigenerare l'ID in base al nuovo nome/cognome? (s/N)"
                    ),
                    "n",
                ).lower()
                == "s"
            ):
                temp_player_data_for_id_gen = players_db_dict_ref.pop(original_id, None)
                candidate_new_id = generate_player_id(
                    new_first_name, new_last_name, players_db_dict_ref
                )

                if (
                    candidate_new_id
                    and candidate_new_id != original_id
                    and candidate_new_id not in players_db_dict_ref
                ):
                    final_id_for_player = candidate_new_id
                    temp_player_data_for_id_gen["id"] = final_id_for_player
                    players_db_dict_ref[final_id_for_player] = (
                        temp_player_data_for_id_gen
                    )
                    player_data_ref = players_db_dict_ref[final_id_for_player]
                    print(
                        _("ID giocatore aggiornato da '{old}' a '{new}'.").format(
                            old=original_id, new=final_id_for_player
                        )
                    )
                else:
                    print(
                        _(
                            "Errore o collisione nella generazione del nuovo ID. L'ID originale '{id}' verrà mantenuto."
                        ).format(id=original_id)
                    )
                    players_db_dict_ref[original_id] = temp_player_data_for_id_gen
        else:
            print(
                _(
                    "Nome e/o cognome non possono essere vuoti. Modifiche a nome/cognome annullate."
                )
            )
            new_first_name = original_first_name
            new_last_name = original_last_name

    player_data_ref["first_name"] = (
        new_first_name if new_first_name else original_first_name
    )
    player_data_ref["last_name"] = (
        new_last_name if new_last_name else original_last_name
    )

    try:
        current_elo_val = float(player_data_ref.get("current_elo", DEFAULT_ELO))
    except ValueError:
        current_elo_val = DEFAULT_ELO
    player_data_ref["current_elo"] = dgt(
        _("Elo Corrente (range 0-3500)"),
        kind="f",
        fmin=0.0,
        fmax=3500.0,
        default=current_elo_val,
    )

    player_data_ref["fide_title"] = get_input_with_default(
        _("Titolo FIDE (es. FM, '' per nessuno)"), player_data_ref.get("fide_title", "")
    ).upper()[:3]

    sex_default_edit = player_data_ref.get("sex", "m")
    while True:
        sex_input_val = get_input_with_default(
            _("Sesso (m/w)"), sex_default_edit
        ).lower()
        if sex_input_val in ["m", "w"]:
            player_data_ref["sex"] = sex_input_val
            break
        elif not sex_input_val and sex_default_edit:
            player_data_ref["sex"] = sex_default_edit
            break
        elif not sex_input_val and not sex_default_edit:
            player_data_ref["sex"] = "m"
            break
        print(_("Input non valido."))

    fed_default_edit = player_data_ref.get("federation", "ITA")
    player_data_ref["federation"] = (
        get_input_with_default(_("Federazione (3 lettere)"), fed_default_edit).upper()[
            :3
        ]
        or "ITA"
    )

    fide_id_default_edit = player_data_ref.get("fide_id_num_str", "0")
    new_fide_id_val = get_input_with_default(
        _("ID FIDE Numerico (cifre, '0' se N/D)"), fide_id_default_edit
    )
    if not new_fide_id_val.isdigit():
        new_fide_id_val = fide_id_default_edit
    player_data_ref["fide_id_num_str"] = new_fide_id_val or "0"

    birth_date_default_edit_str = player_data_ref.get("birth_date", "")
    while True:
        bdate_input_val = get_input_with_default(
            _("Data di nascita ({date_format} o vuoto per cancellare)").format(
                date_format=DATE_FORMAT_ISO
            ),
            birth_date_default_edit_str,
        )
        if not bdate_input_val:
            player_data_ref["birth_date"] = None
            break
        try:
            datetime.strptime(bdate_input_val, DATE_FORMAT_ISO)
            player_data_ref["birth_date"] = bdate_input_val
            break
        except ValueError:
            print(
                _("Formato data non valido. Usa {date_format}.").format(
                    date_format=DATE_FORMAT_ISO
                )
            )

    current_experienced_val = player_data_ref.get("experienced", False)
    experienced_default_str = "s" if current_experienced_val else "n"
    while True:
        exp_input_str_edit = get_input_with_default(
            _("Giocatore con esperienza pregressa significativa? (s/n)"),
            experienced_default_str,
        ).lower()
        if exp_input_str_edit == "s":
            player_data_ref["experienced"] = True
            break
        elif exp_input_str_edit == "n":
            player_data_ref["experienced"] = False
            break
        print(_("Risposta non valida. Inserisci 's' o 'n'."))

    print(_("\n--- Modifica Medagliere ---"))
    medals_data_ref = player_data_ref.setdefault(
        "medals", {"gold": 0, "silver": 0, "bronze": 0, "wood": 0}
    )
    for m_key in ["gold", "silver", "bronze", "wood"]:
        medals_data_ref[m_key] = dgt(
            f"{_('Medaglie di')} {m_key.capitalize()}",
            kind="i",
            imin=0,
            imax=999,
            default=medals_data_ref.get(m_key, 0),
        )

    print(_("\n--- Modifica Storico Tornei ---"))
    tournaments_data_ref = player_data_ref.setdefault("tournaments_played", [])

    while True:
        print(_("\nStorico Tornei Attuale:"))
        if not tournaments_data_ref:
            print(_("  Nessun torneo registrato nello storico."))
        else:
            try:
                sorted_tournaments_for_display = sorted(
                    tournaments_data_ref,
                    key=lambda t_item: datetime.strptime(
                        t_item.get("date_completed", "1900-01-01"), DATE_FORMAT_ISO
                    ),
                    reverse=True,
                )
            except ValueError:
                sorted_tournaments_for_display = tournaments_data_ref

            for i, t_disp in enumerate(sorted_tournaments_for_display):
                rank_disp = format_rank_ordinal(t_disp.get("rank", "?"))
                name_disp = t_disp.get("tournament_name", "Nome Torneo Mancante")
                players_disp = t_disp.get("total_players", "?")
                start_disp = format_date_locale(t_disp.get("date_started"))
                end_disp = format_date_locale(t_disp.get("date_completed"))
                tid_disp = t_disp.get("tournament_id", "N/A")
                print(f"  {i + 1}. {rank_disp} su {players_disp} in '{name_disp}'")
                print(
                    f"     {_('Date')}: {start_disp} - {end_disp} (ID Torneo: {tid_disp})"
                )

        print(_("\nOpzioni Storico Tornei:"))
        op_tourn = (
            get_input_with_default(
                _("  (A)ggiungi, (C)ancella, (F)ine gestione storico: "), "f"
            )
            .strip()
            .lower()
        )

        if op_tourn == "f":
            break
        elif op_tourn == "a":
            print(_("\n  --- Aggiunta nuovo torneo allo storico ---"))
            new_t_entry = {}
            new_t_entry["tournament_name"] = get_input_with_default(
                _("  Nome torneo: ")
            )
            if not new_t_entry["tournament_name"]:
                continue
            new_t_entry["tournament_id"] = get_input_with_default(
                _("  ID Torneo (default: generato in automatico): "),
                f"{sanitize_filename(new_t_entry['tournament_name'])}_{datetime.now().strftime('%Y%m')}",
            )
            new_t_entry["rank"] = get_input_with_default(
                _("  Posizione (es. 1, 2, o RIT): ")
            )
            try:
                new_t_entry["total_players"] = int(
                    get_input_with_default(_("  Numero totale partecipanti: "))
                )
            except ValueError:
                new_t_entry["total_players"] = 0

            for f_date in ["date_started", "date_completed"]:
                while True:
                    d_str = get_input_with_default(
                        _("  Data {field} ({format}): ").format(
                            field=f_date, format=DATE_FORMAT_ISO
                        )
                    )
                    if not d_str:
                        new_t_entry[f_date] = None
                        break
                    try:
                        datetime.strptime(d_str, DATE_FORMAT_ISO)
                        new_t_entry[f_date] = d_str
                        break
                    except ValueError:
                        print(_("  Formato data non valido."))
            tournaments_data_ref.append(new_t_entry)
            print(_("  Torneo aggiunto allo storico."))
        elif op_tourn == "c" and tournaments_data_ref:
            idx_str_c = get_input_with_default(_("  Numero torneo da cancellare: "))
            try:
                idx = int(idx_str_c) - 1
                if 0 <= idx < len(sorted_tournaments_for_display):
                    t_del = sorted_tournaments_for_display[idx]
                    tournaments_data_ref.remove(t_del)
                    print(_("  Torneo rimosso."))
            except (ValueError, IndexError):
                print(_("  Errore cancellazione."))

    print(_("\nGestione completata."))
    display_player_details(player_data_ref)
    return True, final_id_for_player


def main_interactive_db_tool_loop(players_db_main_dict):
    print(
        _("\n--- Gestore Database Giocatori Tornello ---\n\tVersione: {vers}\n").format(
            vers=VERSION
        )
    )
    last_managed_player_id = None
    while True:
        print("\n" + "=" * 40)
        print(_("Giocatori nel database: {num}").format(num=len(players_db_main_dict)))
        prompt_msg_main = _(
            "Cerca giocatore (ID, nome/cognome), (L)ista tutti, (A)ggiungi nuovo, (S)alva e esci: "
        )
        if last_managed_player_id and last_managed_player_id in players_db_main_dict:
            prompt_msg_main = _(
                "Cerca (ID prec: {id}), (L)ista, (A)ggiungi, (S)alva e esci: "
            ).format(id=last_managed_player_id)

        search_input_main_val = (
            get_input_with_default(prompt_msg_main, "s").strip().lower()
        )
        if search_input_main_val == "s" or not search_input_main_val:
            break
        if search_input_main_val == "a":
            if add_new_player(players_db_main_dict):
                save_players_db(players_db_main_dict)
            continue
        if search_input_main_val == "l":
            if not players_db_main_dict:
                print(_("Database vuoto."))
            else:
                print(_("\n--- Lista Giocatori Completa ---"))
                sorted_for_display = sorted(
                    list(players_db_main_dict.values()),
                    key=lambda p_sort: (
                        p_sort.get("last_name", "").lower(),
                        p_sort.get("first_name", "").lower(),
                    ),
                )
                for p_list_item in sorted_for_display:
                    title_p_list = (
                        f"{p_list_item.get('fide_title', '')} "
                        if p_list_item.get("fide_title")
                        else ""
                    )
                    print(
                        f" ID: {p_list_item.get('id'):<10} | {title_p_list}{p_list_item.get('first_name', 'N/D')} {p_list_item.get('last_name', 'N/D')} | Elo: {p_list_item.get('current_elo', 'N/D')}"
                    )
            continue

        found_players_list_main = find_players_partial(
            search_input_main_val, players_db_main_dict
        )

        if not found_players_list_main:
            print(
                _("Nessun giocatore trovato per '{search}'.").format(
                    search=search_input_main_val
                )
            )
            if (
                get_input_with_default(
                    _("Vuoi aggiungere un nuovo giocatore? (S/n) "), "n"
                ).lower()
                == "s"
            ):
                if add_new_player(players_db_main_dict):
                    save_players_db(players_db_main_dict)
            continue
        elif len(found_players_list_main) == 1:
            player_to_manage_item = found_players_list_main[0]
            current_player_id_main_ops = player_to_manage_item["id"]
            while True:
                if current_player_id_main_ops in players_db_main_dict:
                    player_to_manage_item = players_db_main_dict[
                        current_player_id_main_ops
                    ]
                else:
                    break

                display_player_details(player_to_manage_item)
                action_main = get_input_with_default(
                    _("\nAzione: (M)odifica, (C)ancella, (S)eleziona altro/Fine"), "s"
                ).lower()

                if action_main == "s":
                    last_managed_player_id = current_player_id_main_ops
                    break
                elif action_main == "c":
                    if (
                        get_input_with_default(
                            _(
                                "Sicuro di cancellare {first} {last} (ID: {id})? (s/N)"
                            ).format(
                                first=player_to_manage_item.get("first_name"),
                                last=player_to_manage_item.get("last_name"),
                                id=current_player_id_main_ops,
                            ),
                            "n",
                        ).lower()
                        == "s"
                    ):
                        del players_db_main_dict[current_player_id_main_ops]
                        print(_("Giocatore cancellato."))
                        save_players_db(players_db_main_dict)
                        last_managed_player_id = None
                        break
                elif action_main == "m":
                    edit_successful, resulting_player_id = edit_player_data(
                        current_player_id_main_ops, players_db_main_dict
                    )
                    if edit_successful:
                        save_players_db(players_db_main_dict)
                        last_managed_player_id = resulting_player_id
                        current_player_id_main_ops = resulting_player_id
        else:
            print(
                _("\nTrovate {num} corrispondenze. Specifica meglio:").format(
                    num=len(found_players_list_main)
                )
            )
            found_players_list_main.sort(
                key=lambda p_item: (
                    p_item.get("last_name", "").lower(),
                    p_item.get("first_name", "").lower(),
                )
            )
            for i, p_match_item_disp in enumerate(found_players_list_main, 1):
                title_p_list_multi = (
                    f"{p_match_item_disp.get('fide_title', '')} "
                    if p_match_item_disp.get("fide_title")
                    else ""
                )
                print(
                    f"  {i}. ID: {p_match_item_disp.get('id', 'N/D'):<10} - {title_p_list_multi}{p_match_item_disp.get('first_name', 'N/D')} {p_match_item_disp.get('last_name', 'N/D')} (Elo: {p_match_item_disp.get('current_elo', 'N/D')})"
                )

    print(_("\nSalvataggio finale del database prima di uscire..."))
    save_players_db(players_db_main_dict)
    print(_("Uscita dal gestore database giocatori."))


if __name__ == "__main__":
    db = load_players_db()
    main_interactive_db_tool_loop(db)
