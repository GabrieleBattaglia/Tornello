import os
import traceback
from datetime import datetime

from config import DATE_FORMAT_ISO, DEFAULT_ELO
from stats import (
    compute_aro,
    compute_buchholz,
    compute_buchholz_cut1,
    compute_cumulative,
    compute_direct_encounter,
    compute_number_of_blacks,
    compute_number_of_wins,
    compute_played_rounds_rep,
    compute_sonneborn_berger,
    compute_tiebreak_value,
)
from tiebreak_criteria import (
    get_column_header,
    get_criterion_display_name,
    get_default_tiebreaks,
    migrate_old_tiebreaks,
    normalize_tiebreak_entry,
)
from utils import (
    _ensure_players_dict,
    format_date_locale,
    format_points,
    sanitize_filename,
)
from version import VERSIONE


def calcola_tempo_rimanente(end_date_str):
    from datetime import datetime, time

    try:
        end_dt = datetime.strptime(end_date_str, DATE_FORMAT_ISO)
        end_dt = datetime.combine(end_dt.date(), time(23, 59, 59))
        now = datetime.now()
        diff = end_dt - now
        return diff
    except Exception:
        return None


def get_current_round_report_text(torneo, round_num=None):
    """
    Restituisce lo stato del turno specificato (o corrente) come stringa.
    Mostra intestazione, partite da giocare (pianificate e non), e partite giocate.
    I giocatori ritirati sono raggruppati in fondo a ciascuna sezione.
    """
    import io
    from datetime import datetime

    from utils import format_date_locale

    if round_num is None:
        round_num = torneo.get("current_round")

    if round_num is None:
        return _("Numero turno non definito.")

    tournament_name_for_file = torneo.get("name", "Torneo_Senza_Nome")

    round_data = None
    for rnd in torneo.get("rounds", []):
        if rnd.get("round") == round_num:
            round_data = rnd
            break

    if "players_dict" not in torneo or len(torneo["players_dict"]) != len(
        torneo.get("players", [])
    ):
        torneo["players_dict"] = {p["id"]: p for p in torneo.get("players", [])}
    players_dict = torneo["players_dict"]

    round_dates_info = torneo.get("round_dates", [])
    current_round_period_info = next(
        (rd for rd in round_dates_info if rd.get("round") == round_num), None
    )
    start_date_turn_display = (
        format_date_locale(current_round_period_info.get("start_date"))
        if current_round_period_info
        else "N/D"
    )
    end_date_turn_display = (
        format_date_locale(current_round_period_info.get("end_date"))
        if current_round_period_info
        else "N/D"
    )
    time_left_str = ""
    if current_round_period_info and current_round_period_info.get("end_date"):
        end_date_str = current_round_period_info.get("end_date")
        diff = calcola_tempo_rimanente(end_date_str)
        if diff and diff.total_seconds() > 0:
            days = diff.days
            hours = diff.seconds // 3600
            time_left_str = _(
                " Mancano {days} giorni e {hours} ore al termine del periodo utile per questo turno."
            ).format(days=days, hours=hours)

    played_matches_active = []
    played_matches_withdrawn = []
    scheduled_pending_active = []
    scheduled_pending_withdrawn = []
    unscheduled_pending_active = []
    unscheduled_pending_withdrawn = []
    bye_player_display_line = None
    all_matches_in_round = []
    if round_data and "matches" in round_data:
        all_matches_in_round = sorted(
            round_data.get("matches", []), key=lambda m: m.get("id", 0)
        )

    if not all_matches_in_round and round_data is None:
        out = io.StringIO()
        out.write(_("Nome Torneo: {name} - ").format(name=tournament_name_for_file))
        out.write(_("Turno: {round_num}\n").format(round_num=round_num))
        out.write(
            _(" Periodo Turno: {start} - {end}\n").format(
                start=start_date_turn_display, end=end_date_turn_display
            )
        )
        if time_left_str:
            out.write(time_left_str + "\n")
        else:
            out.write("\n")
        out.write(_(" (Nessuna partita ancora definita o caricata per questo turno)\n"))
        return out.getvalue()

    for match in all_matches_in_round:
        wp_obj = players_dict.get(match.get("white_player_id"))
        bp_obj = players_dict.get(match.get("black_player_id"))

        if bp_obj is None and wp_obj is not None:
            bye_player_display_line = _(
                " {first_name} {last_name} ({elo}) ha il BYE"
            ).format(
                first_name=wp_obj.get("first_name", "?"),
                last_name=wp_obj.get("last_name", "?"),
                elo=int(wp_obj.get("initial_elo", 0)),
            )
            continue
        if bp_obj is None or wp_obj is None:
            continue

        wp_name = f"{wp_obj.get('first_name', _('Bianco?'))} {wp_obj.get('last_name', '')} ({int(wp_obj.get('initial_elo', 0))})"
        if wp_obj.get("withdrawn"):
            wp_name += " [RIT]"
        bp_name = f"{bp_obj.get('first_name', _('Nero?'))} {bp_obj.get('last_name', '')} ({int(bp_obj.get('initial_elo', 0))})"
        if bp_obj.get("withdrawn"):
            bp_name += " [RIT]"

        match_id_display = match.get("id", "?")
        is_withdrawn_match = wp_obj.get("withdrawn", False) or bp_obj.get(
            "withdrawn", False
        )

        if match.get("result") is not None:
            line = (
                f"  IDG:{match_id_display} {wp_name} - {bp_name}  {match.get('result')}"
            )
            (
                played_matches_withdrawn
                if is_withdrawn_match
                else played_matches_active
            ).append(line)
        else:
            if match.get("is_scheduled") and match.get("schedule_info"):
                schedule = match.get("schedule_info")
                try:
                    s_date = datetime.strptime(
                        schedule.get("date"), DATE_FORMAT_ISO
                    ).date()
                    s_time = datetime.strptime(schedule.get("time"), "%H:%M").time()
                    sortable_datetime = datetime.combine(s_date, s_time)
                    details_tuple = (
                        sortable_datetime,
                        match,
                        schedule,
                        wp_name,
                        bp_name,
                    )
                    (
                        scheduled_pending_withdrawn
                        if is_withdrawn_match
                        else scheduled_pending_active
                    ).append(details_tuple)
                except (ValueError, TypeError):
                    line = _(
                        " IDG:{match_id} {white_player} - {black_player} (Pianificazione Errata)"
                    ).format(
                        match_id=match_id_display,
                        white_player=wp_name,
                        black_player=bp_name,
                    )
                    (
                        unscheduled_pending_withdrawn
                        if is_withdrawn_match
                        else unscheduled_pending_active
                    ).append(line)
            else:
                line = f"   IDG:{match_id_display} {wp_name} - {bp_name}"
                (
                    unscheduled_pending_withdrawn
                    if is_withdrawn_match
                    else unscheduled_pending_active
                ).append(line)

    scheduled_pending_active.sort(key=lambda x: x[0])
    scheduled_pending_withdrawn.sort(key=lambda x: x[0])

    out = io.StringIO()
    out.write(_("Nome Torneo: {} - ").format(tournament_name_for_file))
    out.write(_("Turno: {}\n").format(round_num))
    # Dalla 10.12.0 il turno composto a mano dall'arbitro lo dice (issue 38).
    if round_data and round_data.get("manual_pairing"):
        out.write(_(" Abbinamenti composti a mano dall'arbitro\n"))
    out.write(
        _(" Periodo Turno: {} - {}\n").format(
            start_date_turn_display, end_date_turn_display
        )
    )
    if time_left_str:
        out.write(time_left_str + "\n")
    else:
        out.write("\n")

    current_printed_date_str = None
    if scheduled_pending_active:
        out.write(
            _(" Partite già pianificate, da giocare ({count}):\n").format(
                count=len(scheduled_pending_active)
            )
        )
        for dt_obj, match, schedule, wp_n, bp_n in scheduled_pending_active:
            match_date_iso = schedule.get("date")
            if match_date_iso != current_printed_date_str:
                out.write(f"  {format_date_locale(match_date_iso)}\n")
                current_printed_date_str = match_date_iso
            time_str = schedule.get("time", "HH:MM")
            out.write(
                _(
                    "   {time} IDG:{match_id}, {white} vs {black}, Canale: {channel}, Arbitro: {arbiter}\n"
                ).format(
                    time=time_str,
                    match_id=match.get("id", "?"),
                    white=wp_n,
                    black=bp_n,
                    channel=schedule.get("channel", _("N/D")),
                    arbiter=schedule.get("arbiter", _("N/D")),
                )
            )

    if unscheduled_pending_active:
        out.write(
            _("\n  Ancora non pianificate ({count}):\n").format(
                count=len(unscheduled_pending_active)
            )
        )
        for line in unscheduled_pending_active:
            out.write(f"   {line.strip()}\n")

    if scheduled_pending_withdrawn or unscheduled_pending_withdrawn:
        out.write(_("\n  -- Partite da giocare con giocatori ritirati --\n"))
        current_printed_date_withdrawn = None
        for dt_obj, match, schedule, wp_n, bp_n in scheduled_pending_withdrawn:
            match_date_iso = schedule.get("date")
            if match_date_iso != current_printed_date_withdrawn:
                out.write(f"   {format_date_locale(match_date_iso)}\n")
                current_printed_date_withdrawn = match_date_iso
            time_str = schedule.get("time", "HH:MM")
            out.write(
                _(
                    "    {time} IDG:{match_id}, {white} vs {black}, Canale: {channel}, Arbitro: {arbiter}\n"
                ).format(
                    time=time_str,
                    match_id=match.get("id", "?"),
                    white=wp_n,
                    black=bp_n,
                    channel=schedule.get("channel", _("N/D")),
                    arbiter=schedule.get("arbiter", _("N/D")),
                )
            )
        if unscheduled_pending_withdrawn:
            out.write(_("   Non pianificate (con ritirati):\n"))
            for line in unscheduled_pending_withdrawn:
                out.write(f"   {line.strip()}\n")

    out.write(
        _("\n  Partite già giocate o con risultato convalidato ({count}):\n").format(
            count=len(played_matches_active)
        )
    )
    if played_matches_active:
        for line in played_matches_active:
            out.write(f"{line}\n")
    else:
        out.write(_("  Ancora nessun risultato assegnato\n"))

    if played_matches_withdrawn:
        out.write(_("  -- Partite giocate con giocatori ritirati --\n"))
        for line in played_matches_withdrawn:
            out.write(f"{line}\n")

    if bye_player_display_line:
        out.write(f"\n{bye_player_display_line}\n")

    out.write(f"\n\nTornello ({VERSIONE})\n")
    return out.getvalue()


def _nella_cartella_dei_report(torneo, nome_file):
    """Il percorso completo di un report del torneo: nella cartella scelta
    per il torneo, e senza una cartella scelta accanto al programma. Fino
    alla 10.3.2 in quel caso restava il solo nome del file, e il report
    finiva nella cartella da cui Tornello era stato avviato, dove la
    finalizzazione non lo trovava piu' per archiviarlo."""
    from utils import resolve_and_verify_save_path

    cartella, avviso = resolve_and_verify_save_path(torneo.get("custom_save_path"))
    if avviso:
        print(avviso)
    return os.path.join(cartella, nome_file)


def save_current_tournament_round_file(torneo):
    """
    Salva lo stato del turno corrente in un file TXT che viene sovrascritto.
    """
    current_round_num = torneo.get("current_round")
    if current_round_num is None:
        print(_("Salvataggio file turno corrente: Numero turno non definito."))
        return

    tournament_name_for_file = torneo.get("name", "Torneo_Senza_Nome")
    sanitized_name = sanitize_filename(tournament_name_for_file)
    filename = _("Tornello - {name} - Turno corrente.txt").format(name=sanitized_name)
    filename = _nella_cartella_dei_report(torneo, filename)

    try:
        text = get_current_round_report_text(torneo, current_round_num)
        with open(filename, "w", encoding="utf-8-sig") as f:
            f.write(text)
        print(
            _("File {filename} aggiornato con raggruppamento ritirati.").format(
                filename=filename
            )
        )
    except OSError as e:
        print(
            f"Errore durante la sovrascrittura del file stato turno corrente '{filename}': {e}"
        )
    except Exception as e_general:
        print(
            _(
                "Errore imprevisto in save_current_tournament_round_file: {error}"
            ).format(error=e_general)
        )
        traceback.print_exc()


def append_completed_round_to_history_file(torneo, completed_round_number):
    """
    Salva i dettagli di un turno concluso in un FILE SEPARATO per quel turno.
    Il file viene creato o sovrascritto.
    """
    tournament_name = torneo.get("name", "Torneo_Senza_Nome")
    sanitized_name = sanitize_filename(tournament_name)
    # NUOVO NOME FILE: specifico per il turno
    filename = _("Tornello - {name} - Turno {round_num} Dettagli.txt").format(
        name=sanitized_name, round_num=completed_round_number
    )
    filename = _nella_cartella_dei_report(torneo, filename)

    round_data = None
    for rnd in torneo.get("rounds", []):
        if rnd.get("round") == completed_round_number:
            round_data = rnd
            break

    if round_data is None or "matches" not in round_data:
        print(
            _(
                "Dati o partite del turno concluso {round_num} non trovati per il salvataggio."
            ).format(round_num=completed_round_number)
        )
        return

    # Assicura che il dizionario dei giocatori sia aggiornato
    _ensure_players_dict(torneo)
    players_dict = torneo["players_dict"]
    all_matches_in_round = round_data.get("matches", [])
    playable_matches = [
        m for m in all_matches_in_round if m.get("black_player_id") is not None
    ]
    bye_match = next(
        (m for m in all_matches_in_round if m.get("black_player_id") is None), None
    )

    def get_average_elo_for_sort(match, players_dict_local):
        w_id = match.get("white_player_id")
        b_id = match.get("black_player_id")
        w_elo_str = players_dict_local.get(w_id, {}).get("initial_elo", "0")
        b_elo_str = players_dict_local.get(b_id, {}).get("initial_elo", "0")
        try:
            w_elo = float(w_elo_str if w_elo_str is not None else 0.0)
            b_elo = float(b_elo_str if b_elo_str is not None else 0.0)
            if w_elo == 0.0 and b_elo == 0.0:
                return 0.0
            if w_elo == 0.0:
                return b_elo
            if b_elo == 0.0:
                return w_elo
            return (w_elo + b_elo) / 2.0
        except (ValueError, TypeError):
            return 0.0

    playable_matches.sort(
        key=lambda m: get_average_elo_for_sort(m, players_dict), reverse=True
    )

    try:
        # Apri in modalità "w" (scrittura) per creare/sovrascrivere il file specifico del turno
        with open(filename, "w", encoding="utf-8-sig") as f:
            # Scrivi sempre l'intestazione completa del torneo e del turno per questo file
            f.write(
                _("Torneo: {name}\n").format(
                    name=torneo.get("name", _("Nome Mancante"))
                )
            )
            f.write(
                _("Sito: {site}, Data Inizio Torneo: {start_date}\n").format(
                    site=torneo.get("site", "N/D"),
                    start_date=format_date_locale(torneo.get("start_date")),
                )
            )
            f.write(
                _("Dettaglio del turno {round_num} concluso\n").format(
                    round_num=completed_round_number
                )
            )
            if round_data.get("manual_pairing"):
                f.write(_("\tAbbinamenti composti a mano dall'arbitro\n"))
            round_dates_list = torneo.get("round_dates", [])
            current_round_dates = next(
                (
                    rd
                    for rd in round_dates_list
                    if rd.get("round") == completed_round_number
                ),
                None,
            )
            if current_round_dates:
                start_d_str = current_round_dates.get("start_date")
                end_d_str = current_round_dates.get("end_date")
                f.write(
                    _("\tPeriodo del Turno: {start} - {end}\n").format(
                        start=format_date_locale(start_d_str),
                        end=format_date_locale(end_d_str),
                    )
                )
            else:
                f.write(_("\tPeriodo del Turno: Date non trovate\n"))
            header_partite = _(
                "Sc | ID  | Bianco                       [Elo] (Pt) - Nero                         [Elo] (Pt) | Risultato"
            )
            f.write(f"\t{header_partite}\n")
            for board_num_idx, match in enumerate(playable_matches):
                board_num = board_num_idx + 1
                match_id = match.get("id", "?")
                white_p_id = match.get("white_player_id")
                black_p_id = match.get("black_player_id")
                result_str = match.get("result", _("ERRORE_RISULTATO_MANCANTE"))
                white_p = players_dict.get(white_p_id)
                black_p = players_dict.get(black_p_id)
                w_name = "? ?"
                w_elo = "?"
                w_pts = "?"
                if white_p:
                    w_name = f"{white_p.get('first_name', '?')} {white_p.get('last_name', '')}"
                    w_elo = white_p.get("initial_elo", "?")
                    # Recupera i punti che il giocatore aveva *alla fine di quel turno*
                    # Questo è più complesso, per ora usiamo i punti correnti come approssimazione o li omettiamo se troppo difficile.
                    # Per semplicità, usiamo i punti totali correnti dal dizionario principale.
                    w_pts = format_points(white_p.get("points", 0.0))
                b_name = "? ?"
                b_elo = "?"
                b_pts = "?"
                if black_p:
                    b_name = f"{black_p.get('first_name', '?')} {black_p.get('last_name', '')}"
                    b_elo = black_p.get("initial_elo", "?")
                    b_pts = format_points(black_p.get("points", 0.0))
                line = (
                    f"{board_num:<3}| "
                    f"{match_id:<4}| "
                    f"{w_name:<24} [{w_elo:>4}] ({w_pts:<4}) - "
                    f"{b_name:<24} [{b_elo:>4}] ({b_pts:<4}) | "
                    f"{result_str}"
                )
                f.write(f"\t{line}\n")
            if bye_match:
                match_id = bye_match.get("id", "?")
                white_p_id = bye_match.get("white_player_id")
                white_p = players_dict.get(white_p_id)
                if white_p:
                    w_name = f"{white_p.get('first_name', '?')} {white_p.get('last_name', '')}"
                    w_elo = white_p.get("initial_elo", "?")
                    w_pts = format_points(white_p.get("points", 0.0))
                    line = (
                        f"{_('bye'):<3}| "
                        f"{match_id:<4}| "
                        f"{w_name:<24} [{w_elo:>4}] ({w_pts:<4}) - {'BYE':<31} | BYE"
                    )
                    f.write(f"\t{line}\n")
                else:
                    line = _(
                        "{dashes:<3}| {match_id:<4}| Errore Giocatore Bye ID: {player_id:<10} | BYE"
                    ).format(dashes=_("bye"), match_id=match_id, player_id=white_p_id)
                    f.write(f"\t{line}\n")

            f.write(f"\n\nTornello ({VERSIONE})\n")
        print(
            _(
                "Dettaglio Turno Concluso {round_num} salvato nel file separato '{filename}'"
            ).format(round_num=completed_round_number, filename=filename)
        )
    except OSError as e:
        print(
            _(
                "Errore durante il salvataggio del file del turno '{filename}': {error}"
            ).format(filename=filename, error=e)
        )
    except Exception as general_e:
        print(
            _(
                "Errore inatteso durante il salvataggio del file del turno: {error}"
            ).format(error=general_e)
        )
        traceback.print_exc()


def get_criterion_value(player_item, criterion, torneo):
    """Calcola il valore di un criterio per l'ordinamento della classifica.

    Supporta sia il vecchio formato stringa sia il nuovo formato dizionario
    con chiavi FIDE e modificatori.
    """
    p_id = player_item.get("id")

    # Supporto retrocompatibilità: criterio come stringa (vecchio formato)
    if isinstance(criterion, str):
        if criterion == "points":
            try:
                return float(player_item.get("points", 0.0))
            except (ValueError, TypeError):
                return 0.0
        elif criterion == "withdrawn":
            return 1 if not player_item.get("withdrawn", False) else 0
        # Prova a normalizzare la vecchia chiave al nuovo formato
        entry = normalize_tiebreak_entry(criterion)
        if entry:
            val = compute_tiebreak_value(
                p_id, torneo, entry["key"], entry.get("modifiers")
            )
            return float(val) if val is not None else 0.0
        # Fallback per chiavi legacy dirette
        if criterion == "buchholz_cut1":
            return compute_buchholz_cut1(p_id, torneo)
        if criterion == "buchholz":
            return compute_buchholz(p_id, torneo)
        if criterion == "aro":
            val = compute_aro(p_id, torneo)
            return val if val is not None else 0.0
        if criterion == "initial_elo":
            elo_initial_raw = float(player_item.get("initial_elo", 0))
            return elo_initial_raw if elo_initial_raw > 0 else DEFAULT_ELO
        if criterion == "sonneborn_berger":
            return compute_sonneborn_berger(p_id, torneo)
        if criterion == "direct_encounter":
            return compute_direct_encounter(p_id, torneo)
        if criterion == "played_rounds_rep":
            return compute_played_rounds_rep(p_id, torneo)
        if criterion == "number_of_wins":
            return compute_number_of_wins(p_id, torneo)
        if criterion == "number_of_blacks":
            return compute_number_of_blacks(p_id, torneo)
        if criterion == "cumulative":
            return compute_cumulative(p_id, torneo)
        return 0.0

    # Nuovo formato: criterio come dizionario {"key": "BH", "modifiers": {...}}
    if isinstance(criterion, dict):
        key = criterion.get("key", "")
        modifiers = criterion.get("modifiers", {})
        val = compute_tiebreak_value(p_id, torneo, key, modifiers)
        return float(val) if val is not None else 0.0

    return 0.0


# I criteri di spareggio che danno un numero intero; gli altri, come BH, FB,
# SB, PS e DE, si scrivono con un decimale.
CRITERI_INTERI = frozenset(
    {"WIN", "WON", "BPG", "BWG", "REP", "STD", "TPN", "ARO", "TPR", "PTP", "APRO", "APPO", "RTNG", "AOB"}
)


def _valore_di_colonna(key, hdr, raw_val):
    """Il valore di una colonna di spareggio come lo scrive la classifica,
    largo quanto la sua intestazione; n.d. se il valore manca. Separato da
    get_column_data con la 10.13.19, per scrivere allo stesso modo i valori
    salvati alla finalizzazione."""
    if raw_val is None:
        return " " * max(0, len(hdr) - 4) + _("n.d.")
    if key in CRITERI_INTERI:
        return f"{int(raw_val):{max(len(hdr), 4)}d}"
    return f"{float(raw_val):{max(len(hdr), 5)}.1f}"


def criteri_di_spareggio(torneo):
    """I criteri di spareggio del torneo, nel formato a dizionari: quelli
    scelti dall'arbitro, i nomi del formato vecchio convertiti, o quelli
    predefiniti se il torneo non ne ha."""
    raw_tiebreaks = torneo.get("tiebreaks", None)
    if raw_tiebreaks is None:
        return get_default_tiebreaks()
    if raw_tiebreaks and isinstance(raw_tiebreaks[0], str):
        return migrate_old_tiebreaks(raw_tiebreaks)
    return raw_tiebreaks


def _ha_una_colonna(criterio):
    """Vero per i criteri che hanno una colonna loro nella classifica: punti,
    ritiro ed Elo iniziale ce l'hanno gia' nella parte fissa della riga."""
    chiave = criterio.get("key", "") if isinstance(criterio, dict) else criterio
    return chiave not in ("points", "withdrawn", "initial_elo")


def valori_degli_spareggi(player, torneo, criteri=None):
    """Il valore di ogni colonna di spareggio della classifica per un
    giocatore, per intestazione, per esempio {"BH-C1": 15.5, "ARO": 1648},
    calcolato come lo calcola la classifica. La finalizzazione lo salva nel
    giocatore, in final_tiebreaks, dalla 10.13.19: la classifica di un
    torneo concluso lo rilegge da li' invece di ricalcolarlo con le regole
    di oggi. I criteri del formato vecchio, a stringhe, non hanno un valore
    salvato."""
    if criteri is None:
        criteri = criteri_di_spareggio(torneo)
    valori = {}
    for criterio in criteri:
        if not isinstance(criterio, dict) or not _ha_una_colonna(criterio):
            continue
        chiave = criterio.get("key", "")
        modificatori = criterio.get("modifiers", {})
        valori[get_column_header(chiave, modificatori)] = compute_tiebreak_value(
            player.get("id"), torneo, chiave, modificatori
        )
    return valori


# Le colonne di spareggio che le finalizzazioni fino alla 10.13.18 salvavano
# gia' nel giocatore, con il campo in cui stanno: Buchholz Cut-1, Buchholz e
# ARO, i tre criteri predefiniti che si calcolano dai risultati.
CAMPI_DELLE_VECCHIE_FINALIZZAZIONI = {
    "BH-C1": "buchholz_cut1",
    "BH": "buchholz",
    "ARO": "aro",
}


def _valore_salvato(player, criterio):
    """Il valore di una colonna di spareggio salvato alla finalizzazione,
    come (trovato, valore). Prima final_tiebreaks, dalla 10.13.19; poi, per
    i tornei finalizzati prima, i campi buchholz_cut1, buchholz e aro, che la
    finalizzazione scriveva gia'. L'Elo di partenza, RTNG, e' un dato del
    torneo e non un calcolo. Per ogni altra colonna di un torneo finalizzato
    prima della 10.13.19 il valore di allora non c'e'."""
    if not isinstance(criterio, dict):
        return False, None
    chiave = criterio.get("key", "")
    intestazione = get_column_header(chiave, criterio.get("modifiers", {}))
    salvati = player.get("final_tiebreaks")
    if isinstance(salvati, dict) and intestazione in salvati:
        return True, salvati[intestazione]
    if chiave == "RTNG":
        try:
            return True, round(float(player.get("initial_elo", 0)))
        except (ValueError, TypeError):
            return False, None
    campo = CAMPI_DELLE_VECCHIE_FINALIZZAZIONI.get(intestazione)
    if campo and player.get(campo) is not None:
        return True, player.get(campo)
    return False, None


def _intestazione_di_colonna(criterio, torneo):
    """L'intestazione della colonna di un criterio di spareggio."""
    if isinstance(criterio, dict):
        return get_column_header(criterio.get("key", ""), criterio.get("modifiers", {}))
    colonna = get_column_data(criterio, {}, torneo)
    return colonna[0] if colonna else None


def _posizione_salvata(player):
    """La posizione salvata alla finalizzazione, final_rank; RIT per un
    ritirato; None se non c'e'. display_rank non conta: e' l'ultima
    posizione mostrata durante il torneo, e nei tre tornei archiviati del 2025
    e del 2026, finalizzati senza final_rank, non coincide con il piazzamento
    che la finalizzazione ha scritto nello storico dei giocatori e nella
    classifica scritta da Tornello alla finalizzazione, nel file
    Classifica.txt archiviato, per 10, 11 e 14 giocatori. Per ASCId
    Primavera 1 quel file ha anche la classifica dell'arbitro, diversa per
    dieci giocatori."""
    if player.get("withdrawn", False):
        return "RIT"
    valore = player.get("final_rank")
    if isinstance(valore, int) and not isinstance(valore, bool) and valore > 0:
        return valore
    return None


def posizioni_dallo_storico(torneo, players_db):
    """Il piazzamento che la finalizzazione ha scritto nello storico dei
    giocatori del database per questo torneo, per identificativo del
    giocatore nel torneo: e' quello assegnato e premiato allora, con le
    medaglie. La voce si riconosce come la riconosce la finalizzazione; una
    voce scritta su una scheda trovata per identificativo FIDE vale per
    l'identificativo del torneo, id_nel_torneo (10.13.16). Contano soltanto
    le posizioni intere: RIT e N/A no.
    Nata con la 10.13.19, per i tornei conclusi che non hanno salvato
    final_rank: le finalizzazioni di allora ordinavano con criteri che oggi
    non sono piu' quelli, per esempio la performance al posto dell'ARO, e
    ricavare le posizioni dai valori salvati con i criteri di oggi potrebbe
    cambiare un piazzamento assegnato allora. Nei tre tornei archiviati del
    2025 e del 2026 le due strade danno le stesse posizioni; in ASCId 52
    lo storico non le ha tutte, perche' la finalizzazione di allora ha
    saltato un giocatore che il database non aveva."""
    from db_players import identita_del_torneo, voce_di_questo_torneo

    identificativo, inizio = identita_del_torneo(torneo)
    nome = torneo.get("name")
    posizioni = {}
    for chiave, scheda in (players_db or {}).items():
        if not isinstance(scheda, dict):
            continue
        for voce in scheda.get("tournaments_played") or []:
            if not isinstance(voce, dict) or not voce_di_questo_torneo(voce, identificativo, nome, inizio):
                continue
            rank = voce.get("rank")
            if isinstance(rank, int) and not isinstance(rank, bool) and rank > 0:
                posizioni[voce.get("id_nel_torneo") or scheda.get("id") or chiave] = rank
    return posizioni


def get_column_data(criterion, player, torneo):
    """Restituisce (header, valore_formattato) per una colonna della classifica.

    Supporta sia il vecchio formato stringa sia il nuovo formato dizionario.
    """
    p_id = player.get("id")
    is_rit = player.get("withdrawn", False)

    # Nuovo formato dizionario con chiavi FIDE
    if isinstance(criterion, dict):
        key = criterion.get("key", "")
        modifiers = criterion.get("modifiers", {})
        hdr = get_column_header(key, modifiers)

        if is_rit:
            return hdr, _valore_di_colonna(key, hdr, None)

        raw_val = compute_tiebreak_value(p_id, torneo, key, modifiers)
        return hdr, _valore_di_colonna(key, hdr, raw_val)

    # Retrocompatibilità: vecchio formato stringa
    if isinstance(criterion, str):
        if criterion == "points":
            hdr = _("Punti")
            val = f"{float(player.get('points', 0.0)):5.1f}"
        elif criterion == "buchholz_cut1":
            hdr = _("Bucch-1")
            val = (
                f"{float(compute_buchholz_cut1(p_id, torneo)):7.2f}"
                if not is_rit
                else "   " + _("n.d.")
            )
        elif criterion == "buchholz":
            hdr = _("Bucch")
            val = (
                f"{float(compute_buchholz(p_id, torneo)):5.1f}"
                if not is_rit
                else " " + _("n.d.")
            )
        elif criterion == "aro":
            hdr = _(" ARO")
            aro_val = compute_aro(p_id, torneo)
            val = (
                f"{int(aro_val):4d}"
                if aro_val is not None and not is_rit
                else _("n.d.")
            )
        elif criterion == "sonneborn_berger":
            hdr = _("Sonn-B")
            sb_val = compute_sonneborn_berger(p_id, torneo)
            val = f"{float(sb_val):6.2f}" if not is_rit else "  " + _("n.d.")
        elif criterion == "direct_encounter":
            hdr = _("ScrDir")
            de_val = compute_direct_encounter(p_id, torneo)
            val = f"{float(de_val):6.1f}" if not is_rit else "  " + _("n.d.")
        elif criterion == "played_rounds_rep":
            hdr = _("REP")
            rep_val = compute_played_rounds_rep(p_id, torneo)
            val = f"{int(rep_val):3d}" if not is_rit else _("nd.")
        elif criterion == "number_of_wins":
            hdr = _("Vitt")
            wins_val = compute_number_of_wins(p_id, torneo)
            val = f"{int(wins_val):4d}" if not is_rit else "   -"
        elif criterion == "number_of_blacks":
            hdr = _("Neri")
            blacks_val = compute_number_of_blacks(p_id, torneo)
            val = f"{int(blacks_val):4d}" if not is_rit else "   -"
        elif criterion == "cumulative":
            hdr = _("Cumul")
            cum_val = compute_cumulative(p_id, torneo)
            val = f"{float(cum_val):5.1f}" if not is_rit else "    -"
        else:
            return None
        return hdr, val

    return None


def get_standings_text(torneo, final=False, players_db=None):
    """
    Genera la classifica (parziale o finale) del torneo come stringa.
    Mostra sempre gli spareggi, incluso ARO. Mostra Perf/Var Elo solo alla fine.
    Include la variazione rispetto alla posizione iniziale in tabellone (Seed).
    Un torneo concluso mostra sempre la classifica finale con i valori
    salvati alla finalizzazione: posizione, spareggi, performance e
    variazione Elo calcolati allora, non ricalcolati con le regole di oggi,
    perche' la classifica pubblicata non deve cambiare a posteriori
    (decisione di Gabriele, 10.13.19). Il torneo concluso resta com'e': fino
    alla 10.13.18 la classifica riscriveva nei suoi giocatori i valori
    ricalcolati, e il primo salvataggio li avrebbe portati nel file. Un
    valore che il torneo non ha salvato si legge n.d., e una riga in fondo
    lo spiega. Se mancano delle posizioni, come nei tornei finalizzati fino
    alla 10.13.18, sono quelle scritte allora nello storico dei giocatori
    del database; se lo storico non le ha tutte, si ricavano dai punti e
    dagli spareggi salvati, e in mancanza anche di quelli si calcolano con
    le regole di oggi, su una copia del torneo. Una riga in fondo dice da
    dove vengono, e un'altra dice i giocatori per cui differiscono dallo
    storico.
    Durante il torneo la colonna Elo Var. e' la variazione che la
    finalizzazione applichera': stesso fattore K, calcolato sulla scheda del
    database dei giocatori, o su quella che la finalizzazione creera' per chi
    il database non ha (10.13.17); se il database non si legge, n.d., con una
    riga in fondo. players_db e' il database dei giocatori; senza, lo si
    legge dal disco.
    """
    import copy
    import io
    from datetime import datetime

    from utils import format_date_locale

    concluso = bool(torneo.get("concluded", False))
    if concluso:
        final = True
    else:
        from tournament import ricalcola_punti_tutti_giocatori

        ricalcola_punti_tutti_giocatori(torneo)
    players = torneo.get("players", [])
    if not players:
        return _("Attenzione: Nessun giocatore per generare la classifica.")

    if not concluso and (
        "players_dict" not in torneo or len(torneo["players_dict"]) != len(players)
    ):
        torneo["players_dict"] = {p["id"]: p for p in torneo.get("players", [])}

    # --- CALCOLO SEEDING (ORDINE DI PARTENZA) ---
    def get_effective_elo(p):
        elo = float(p.get("initial_elo", DEFAULT_ELO))
        return elo if elo > 0 else DEFAULT_ELO

    players_for_seeding = sorted(
        players,
        key=lambda p: (
            -get_effective_elo(p),
            p.get("last_name", "").lower(),
            p.get("first_name", "").lower(),
        ),
    )
    seeding_map = {p["id"]: i + 1 for i, p in enumerate(players_for_seeding)}
    # --------------------------------------------

    # Vero se il database dei giocatori, che serve alla colonna Elo Var. di
    # un torneo in corso, non si e' potuto leggere.
    database_illeggibile = False
    if not concluso:
        from db_players import database_non_letto, fattore_k_della_finalizzazione
        from stats import calculate_elo_change, calculate_performance_rating

        if players_db is None:
            from db_players import load_players_db

            players_db = load_players_db()
        # Senza le schede del database il K della finalizzazione non si
        # conosce: la colonna Elo Var. dice n.d., e una riga in fondo lo
        # spiega. Con il database letto vuoto direbbe per tutti la variazione
        # di un giocatore nuovo, con K 40.
        database_illeggibile = database_non_letto(players_db)
        for p in players:
            p_id = p.get("id")
            if not p_id:
                continue
            p["buchholz"] = compute_buchholz(p_id, torneo)
            p["buchholz_cut1"] = compute_buchholz_cut1(p_id, torneo)
            p["aro"] = compute_aro(p_id, torneo)
            if p.get("withdrawn", False):
                p["final_rank"] = "RIT"
                p["performance_rating"] = None
                p["elo_change"] = None
            else:
                # Il K e' quello della finalizzazione, ricalcolato ogni volta:
                # fino alla 10.13.16 veniva dal giocatore del torneo, che non
                # ha experienced, partite giocate e data di nascita del
                # database, e poi restava salvato nel torneo. Per chi non li
                # ha la regola dava 40 dove la finalizzazione dava 20.
                p["performance_rating"] = calculate_performance_rating(
                    p, torneo["players_dict"]
                )
                if database_illeggibile:
                    p["k_factor"] = None
                    p["elo_change"] = None
                else:
                    p["k_factor"] = fattore_k_della_finalizzazione(
                        p, players_db, torneo.get("start_date")
                    )
                    p["elo_change"] = calculate_elo_change(
                        p, torneo["players_dict"]
                    )

    tiebreak_order = criteri_di_spareggio(torneo)

    def sort_key_standings(player_item, torneo_del_calcolo=None):
        """La chiave di ordinamento con le regole di oggi. torneo_del_calcolo
        e' il torneo su cui calcolare gli spareggi, se non e' quello mostrato:
        per un torneo concluso e' una sua copia, che il calcolo puo' toccare."""
        if torneo_del_calcolo is None:
            torneo_del_calcolo = torneo
        # Criteri impliciti sempre attivi: punti (decrescente) e stato attivo/ritirato
        try:
            pts = float(player_item.get("points", 0.0))
        except (ValueError, TypeError):
            pts = 0.0
        withdrawn_val = 1 if not player_item.get("withdrawn", False) else 0
        sort_tuple = [-pts, -withdrawn_val]

        # Criteri di spareggio configurati
        for criterion in tiebreak_order:
            val = get_criterion_value(player_item, criterion, torneo_del_calcolo)
            # Aggiunge il valore invertito per l'ordinamento decrescente
            sort_tuple.append(-val)
        return tuple(sort_tuple)

    def posizioni_dall_ordine(ordinati, chiavi=None):
        """Le posizioni di una lista ordinata con sort_key_standings: a
        parita' di tutti i criteri la stessa posizione, RIT ai ritirati.
        chiavi, se c'e', ha le chiavi gia' calcolate, per identificativo."""
        risultato = {}
        posizione_corrente = 0
        ultima_chiave = None
        for i, p_item in enumerate(ordinati):
            if p_item.get("withdrawn", False):
                risultato[p_item.get("id")] = "RIT"
                continue
            chiave = chiavi[p_item.get("id")] if chiavi is not None else sort_key_standings(p_item)
            if chiave != ultima_chiave:
                posizione_corrente = i + 1
            risultato[p_item.get("id")] = posizione_corrente
            ultima_chiave = chiave
        return risultato

    # --- DETERMINAZIONE STATO E TITOLO REPORT ---
    current_round_in_state = torneo.get("current_round", 0)
    has_real_results = False
    for p in players:
        if any(
            res.get("result") not in [None, "BYE"]
            for res in p.get("results_history", [])
        ):
            has_real_results = True
            break

    show_ratings = final or has_real_results
    status_line = ""
    is_initial_list = False
    if final:
        status_line = _("CLASSIFICA FINALE")
    else:
        if not has_real_results and current_round_in_state <= 1:
            status_line = _("Elenco Iniziale Partecipanti (Prima del Turno 1)")
            is_initial_list = True
        else:
            all_matches_for_current_round_done = True
            if current_round_in_state > 0 and current_round_in_state <= torneo.get(
                "total_rounds", 0
            ):
                for r_data in torneo.get("rounds", []):
                    if r_data.get("round") == current_round_in_state:
                        for m in r_data.get("matches", []):
                            if (
                                m.get("result") is None
                                and m.get("black_player_id") is not None
                            ):
                                all_matches_for_current_round_done = False
                                break
                        break
                if all_matches_for_current_round_done:
                    status_line = _(
                        "Classifica Parziale - Dopo Turno {round_num}"
                    ).format(round_num=current_round_in_state)
                else:
                    status_line = _(
                        "Classifica Parziale - Durante Turno {round_num}"
                    ).format(round_num=current_round_in_state)

    # Le posizioni per identificativo. Durante il torneo si scrivono anche
    # nei giocatori, in display_rank, come sempre; per un torneo concluso
    # restano qui, e il torneo non cambia.
    posizioni = {}
    posizioni_calcolate_oggi = False
    posizioni_dai_valori_salvati = False
    posizioni_dallo_storico_usate = False
    # I giocatori la cui posizione ricavata o calcolata non e' il
    # piazzamento scritto nello storico, per la riga in fondo.
    diverse_dallo_storico = []

    def chiave_dai_valori_salvati(p_item):
        """Punti e colonne di spareggio salvati, nell'ordine dei criteri,
        per ordinare un torneo concluso senza final_rank; None se ne manca
        uno."""
        try:
            chiave = [-float(p_item.get("points", 0.0))]
        except (ValueError, TypeError):
            return None
        for criterio in tiebreak_order:
            if not _ha_una_colonna(criterio):
                continue
            trovato, valore = _valore_salvato(p_item, criterio)
            try:
                chiave.append(-float(valore))
            except (ValueError, TypeError):
                return None
            if not trovato:
                return None
        return tuple(chiave)

    try:
        if concluso:
            salvate = {p.get("id"): _posizione_salvata(p) for p in players}

            def ordine_salvato(p_item):
                try:
                    punti = float(p_item.get("points", 0.0))
                except (ValueError, TypeError):
                    punti = 0.0
                posizione = posizioni.get(p_item.get("id"))
                return (
                    -punti,
                    bool(p_item.get("withdrawn", False)),
                    posizione if isinstance(posizione, int) else float("inf"),
                    p_item.get("last_name", "").lower(),
                    p_item.get("first_name", "").lower(),
                )

            senza_posizione = any(valore is None for valore in salvate.values())
            dallo_storico = {}
            if senza_posizione:
                # Senza final_rank, come nei tornei finalizzati fino alla
                # 10.13.18 che non lo scrivevano, la posizione e' il
                # piazzamento scritto allora nello storico dei giocatori, lo
                # stesso delle medaglie.
                if players_db is None:
                    from db_players import load_players_db

                    players_db = load_players_db()
                dallo_storico = posizioni_dallo_storico(torneo, players_db)
            non_ritirati = [p.get("id") for p in players if not p.get("withdrawn", False)]
            if senza_posizione and non_ritirati and all(pid in dallo_storico for pid in non_ritirati):
                posizioni_dallo_storico_usate = True
                posizioni = {
                    p.get("id"): "RIT" if p.get("withdrawn", False) else dallo_storico[p.get("id")]
                    for p in players
                }
                players_sorted = sorted(players, key=ordine_salvato)
            elif senza_posizione and all(
                chiave_dai_valori_salvati(p) is not None
                for p in players
                if not p.get("withdrawn", False)
            ):
                # Se lo storico non le ha tutte, per esempio perche' la
                # finalizzazione di allora saltava chi il database non
                # aveva, le posizioni si ricavano dai punti e dagli spareggi
                # salvati, nell'ordine dei criteri di spareggio, e lo si dice.
                posizioni_dai_valori_salvati = True
                chiavi_salvate = {
                    p.get("id"): chiave_dai_valori_salvati(p)
                    for p in players
                    if not p.get("withdrawn", False)
                }

                def ordine_dei_valori(p_item):
                    ritirato = bool(p_item.get("withdrawn", False))
                    chiave = chiavi_salvate.get(p_item.get("id"))
                    if ritirato or chiave is None:
                        try:
                            punti = -float(p_item.get("points", 0.0))
                        except (ValueError, TypeError):
                            punti = 0.0
                        return (punti, 1)
                    return (chiave[0], 0, *chiave[1:])

                players_sorted = sorted(players, key=ordine_dei_valori)
                posizione_corrente = 0
                ultima_chiave = None
                for i, p_item in enumerate(players_sorted):
                    if p_item.get("withdrawn", False):
                        posizioni[p_item.get("id")] = "RIT"
                        continue
                    chiave = chiavi_salvate[p_item.get("id")]
                    if chiave != ultima_chiave:
                        posizione_corrente = i + 1
                    posizioni[p_item.get("id")] = posizione_corrente
                    ultima_chiave = chiave
            elif senza_posizione:
                # Senza la posizione salvata di qualcuno, e senza i valori
                # per ricavarla, le posizioni si calcolano tutte con le
                # regole di oggi, e lo si dice. Il calcolo lavora su una
                # copia: sul torneo concluso aggiungerebbe players_dict.
                posizioni_calcolate_oggi = True
                copia = copy.deepcopy(torneo)
                copia["players_dict"] = {g.get("id"): g for g in copia.get("players", [])}
                chiavi_di_oggi = {
                    g.get("id"): sort_key_standings(g, copia) for g in copia.get("players", [])
                }
                players_sorted = sorted(players, key=lambda g: chiavi_di_oggi[g.get("id")])
                posizioni = posizioni_dall_ordine(players_sorted, chiavi_di_oggi)
            else:
                posizioni = salvate
                players_sorted = sorted(players, key=ordine_salvato)
            if not posizioni_dallo_storico_usate:
                diverse_dallo_storico = [
                    (p, posizioni.get(p.get("id")), dallo_storico[p.get("id")])
                    for p in players_sorted
                    if p.get("id") in dallo_storico
                    and posizioni.get(p.get("id")) != dallo_storico[p.get("id")]
                ]
        elif is_initial_list:
            players_sorted = players_for_seeding
            for i, p_item in enumerate(players_sorted):
                p_item["display_rank"] = i + 1
        else:
            players_sorted = sorted(players, key=sort_key_standings)
            if not final or (
                players_sorted
                and players_sorted[0].get("final_rank") is None
                and not players_sorted[0].get("withdrawn")
            ):
                calcolate = posizioni_dall_ordine(players_sorted)
                for p_item in players_sorted:
                    p_item["display_rank"] = calcolate[p_item.get("id")]
            elif final:
                for i, p_item in enumerate(players_sorted):
                    if p_item.get("final_rank") is not None:
                        p_item["display_rank"] = p_item["final_rank"]
                    elif p_item.get("withdrawn", False):
                        p_item["display_rank"] = "RIT"
                    else:
                        p_item["display_rank"] = i + 1
    except Exception as e:
        print(f"Errore durante l'ordinamento dei giocatori per la classifica: {e}")
        traceback.print_exc()
        players_sorted = players
    if not concluso:
        posizioni = {p.get("id"): p.get("display_rank", "?") for p in players}

    out = io.StringIO()
    out.write(_("Nome Torneo: {name}\n").format(name=torneo.get("name", "N/D")))
    out.write(_("Luogo: {site}\n").format(site=torneo.get("site", "N/D")))
    out.write(
        _("Date: {start_date} - {end_date}\n").format(
            start_date=format_date_locale(torneo.get("start_date")),
            end_date=format_date_locale(torneo.get("end_date")),
        )
    )
    out.write(
        _("Federazione Organizzante: {fed}\n").format(
            fed=torneo.get("federation_code", "N/D")
        )
    )
    out.write(
        _("Arbitro Capo: {arbiter}\n").format(
            arbiter=torneo.get("chief_arbiter", "N/D")
        )
    )
    deputy_arbiters_str = torneo.get("deputy_chief_arbiters", "")
    if deputy_arbiters_str and deputy_arbiters_str.strip():
        out.write(_("Vice Arbitri: {arbiters}\n").format(arbiters=deputy_arbiters_str))
    tc = torneo.get("time_control")
    cat = torneo.get("tournament_category")
    if not cat and isinstance(tc, dict):
        from stats import classify_tournament_category

        cat = classify_tournament_category(
            tc.get("minutes", 60), tc.get("increment", 0)
        )
    if not cat:
        cat = "standard"
    cat_disp = cat.capitalize()

    tc_str = "N/D"
    if isinstance(tc, dict):
        tc_str = (
            f"{tc.get('minutes', 0)} min + {tc.get('increment', 0)} sec ({cat_disp})"
        )
    elif isinstance(tc, str):
        tc_str = f"{tc} ({cat_disp})"
    out.write(_("Controllo Tempo: {time_control}\n").format(time_control=tc_str))
    out.write(_("Sistema di Abbinamento: Svizzero Olandese (via bbpPairings)\n"))

    # Lista ordinata per importanza dei criteri di spareggio attivi negli headers
    tiebreak_order_display = tiebreak_order

    # Genera la stringa dei nomi dei criteri per il report
    criteri_display = []
    for entry in tiebreak_order_display:
        if isinstance(entry, dict):
            criteri_display.append(
                get_criterion_display_name(entry.get("key", ""), entry.get("modifiers"))
            )
        elif isinstance(entry, str):
            # Retrocompatibilità vecchie chiavi stringa
            criteri_nomi_legacy = {
                "points": _("Punti"),
                "withdrawn": _("Ritirato"),
                "buchholz_cut1": _("Buchholz Cut-1"),
                "buchholz": _("Buchholz Totale"),
                "aro": _("ARO"),
                "initial_elo": _("Elo Iniziale"),
                "sonneborn_berger": _("Sonneborn-Berger"),
                "direct_encounter": _("Scontro Diretto"),
                "played_rounds_rep": _("REP (Turni Giocati)"),
                "number_of_wins": _("Vittorie"),
                "number_of_blacks": _("Neri"),
                "cumulative": _("Cumulativo"),
            }
            criteri_display.append(criteri_nomi_legacy.get(entry, entry))
    out.write(
        _("Criteri di Spareggio: {tiebreaks}\n").format(
            tiebreaks=", ".join(criteri_display)
        )
    )

    out.write(
        _("Data Report: {date} {time}\n").format(
            date=format_date_locale(datetime.now().date()),
            time=datetime.now().strftime("%H:%M:%S"),
        )
    )

    out.write(f"{status_line}\n")

    # --- HEADER TABELLA DINAMICO ---
    header_table = _("Pos. (Tab)   Titolo Nome Cognome               [EloIni] Punti")

    # I criteri che hanno una colonna loro: punti, ritiro ed Elo iniziale
    # stanno gia' nella parte fissa della riga.
    dynamic_cols = [crit for crit in tiebreak_order_display if _ha_una_colonna(crit)]

    headers_list = []
    for crit in dynamic_cols:
        intestazione = _intestazione_di_colonna(crit, torneo)
        if intestazione:
            headers_list.append(intestazione)

    if headers_list:
        header_table += " " + " ".join(headers_list)

    if show_ratings:
        header_table += " " + _("Perf") + " " + _("Elo Var.")

    out.write(header_table + "\n")

    # I valori che un torneo concluso non ha salvato, per la riga in fondo.
    valori_mancanti = 0
    for player in players_sorted:
        p_id = player.get("id")
        rank_to_show = posizioni.get(p_id, "?")
        ritirato = player.get("withdrawn", False)

        starting_rank = seeding_map.get(p_id, 0)
        delta_str = ""
        if isinstance(rank_to_show, (int, float)):
            delta = starting_rank - int(rank_to_show)
            delta_str = f"({delta:+})"
            rank_display_str = f"{int(rank_to_show):>3} {delta_str:<7}"
        else:
            rank_display_str = f"{rank_to_show!s:>3} {' ':<7}"

        fide_title = str(player.get("fide_title", "")).strip().upper()
        player_name_str = (
            f"{player.get('last_name', 'N/D')}, {player.get('first_name', 'N/D')}"
        )

        title_display_str = f"{fide_title:<3}"
        name_display_str = f"{player_name_str:<27.27}"
        elo_ini_str = f"[{int(player.get('initial_elo', DEFAULT_ELO)):4d}]"

        # Costruzione dinamica della riga dati
        pts_val = float(player.get("points", 0.0))
        line = f"{rank_display_str} {title_display_str} {name_display_str} {elo_ini_str} {pts_val:5.1f}"

        vals_list = []
        for crit in dynamic_cols:
            if not concluso:
                col_res = get_column_data(crit, player, torneo)
                if col_res:
                    vals_list.append(col_res[1])
                continue
            # Torneo concluso: il valore salvato alla finalizzazione.
            intestazione = _intestazione_di_colonna(crit, torneo)
            if not intestazione:
                continue
            chiave = crit.get("key", "") if isinstance(crit, dict) else ""
            trovato, valore = (False, None) if ritirato else _valore_salvato(player, crit)
            if not trovato and not ritirato:
                valori_mancanti += 1
            vals_list.append(_valore_di_colonna(chiave, intestazione, valore))

        if vals_list:
            line += " " + " ".join(vals_list)

        if show_ratings:
            if ritirato:
                perf_str, elo_change_str = _("n.d."), _("n.d.")
            else:
                perf_val = player.get("performance_rating")
                perf_str = f"{int(perf_val):4d}" if perf_val is not None else _("n.d.")
                elo_change_val = player.get("elo_change")
                elo_change_str = (
                    f"{int(elo_change_val):+4d}"
                    if elo_change_val is not None
                    else _("n.d.")
                )
                if concluso:
                    valori_mancanti += (perf_val is None) + (elo_change_val is None)
            line += f" {perf_str} {elo_change_str}"

        if ritirato:
            line = f"{line.ljust(90)} [RITIRATO]"

        out.write(line + "\n")

    if posizioni_dallo_storico_usate:
        out.write(
            "\n"
            + _(
                "Le posizioni di questo torneo concluso non erano salvate nel suo file: sono il piazzamento che la finalizzazione ha scritto allora nello storico dei giocatori, nel database dei giocatori."
            )
            + "\n"
        )
    if posizioni_dai_valori_salvati:
        out.write(
            "\n"
            + _(
                "Le posizioni di questo torneo concluso non erano salvate alla finalizzazione: sono ricavate dai punti e dagli spareggi salvati allora, nell'ordine dei criteri di spareggio."
            )
            + "\n"
        )
    if posizioni_calcolate_oggi:
        out.write(
            "\n"
            + _(
                "Le posizioni di questo torneo concluso non erano salvate alla finalizzazione: sono calcolate con le regole di oggi."
            )
            + "\n"
        )
    if diverse_dallo_storico:
        elenco = ", ".join(
            _("{name} {rank} invece di {history_rank}").format(
                name=f"{p.get('last_name', '')} {p.get('first_name', '')}".strip(),
                rank=posizione,
                history_rank=nello_storico,
            )
            for p, posizione, nello_storico in diverse_dallo_storico
        )
        if len(diverse_dallo_storico) == 1:
            frase = _(
                "Per un giocatore la posizione è diversa dal piazzamento che la finalizzazione ha scritto allora nel suo storico, nel database dei giocatori: {players}."
            ).format(players=elenco)
        else:
            frase = _(
                "Per {count} giocatori la posizione è diversa dal piazzamento che la finalizzazione ha scritto allora nel loro storico, nel database dei giocatori: {players}."
            ).format(count=len(diverse_dallo_storico), players=elenco)
        out.write("\n" + frase + "\n")
    if valori_mancanti:
        out.write(
            "\n"
            + _(
                "I valori n.d. dei giocatori non ritirati non erano salvati alla finalizzazione di questo torneo: la classifica di un torneo concluso non li ricalcola con le regole di oggi."
            )
            + "\n"
        )
    if database_illeggibile and show_ratings:
        out.write(
            "\n"
            + _(
                "La colonna Elo Var. si legge n.d. perché il database dei giocatori non si è potuto leggere: senza le schede dei giocatori il fattore K della finalizzazione non si conosce."
            )
            + "\n"
        )

    out.write(f"\n\nTornello ({VERSIONE})\n")
    return out.getvalue()


def save_standings_text(torneo, final=False):
    """
    Salva/Sovrascrive la classifica (parziale o finale) in un unico file TXT.
    """
    players = torneo.get("players", [])
    if not players:
        print(_("Attenzione: Nessun giocatore per generare la classifica."))
        return

    tournament_name_file = torneo.get("name", "Torneo_Senza_Nome")
    sanitized_name_file = sanitize_filename(tournament_name_file)
    filename = _("Tornello - {name} - Classifica.txt").format(name=sanitized_name_file)
    filename = _nella_cartella_dei_report(torneo, filename)

    try:
        text = get_standings_text(torneo, final)
        with open(filename, "w", encoding="utf-8-sig") as f:
            f.write(text)
        print(
            _("File classifica '{filename}' salvato/sovrascritto.").format(
                filename=filename
            )
        )
    except OSError as e:
        print(
            _(
                "Errore durante il salvataggio del file classifica '{filename}': {error}"
            ).format(filename=filename, error=e)
        )
    except Exception as general_e:
        print(f"Errore inatteso durante save_standings_text: {general_e}")
        traceback.print_exc()


def display_status(torneo):
    """Mostra lo stato attuale del torneo."""
    print(_("Stato del torneo"))
    print(_("Nome: {name}").format(name=torneo.get("name", "N/D")))
    start_d_str = torneo.get("start_date")
    end_d_str = torneo.get("end_date")
    print(
        _("Periodo: {start} - {end}").format(
            start=format_date_locale(start_d_str), end=format_date_locale(end_d_str)
        )
    )
    current_r = torneo.get("current_round", "?")
    total_r = torneo.get("total_rounds", "?")
    print(
        _("Turno Corrente: {current} / {total}").format(
            current=current_r, total=total_r
        )
    )
    datetime.now()
    # Mostra date turno corrente
    round_dates_list = torneo.get("round_dates", [])
    current_round_dates = next(
        (rd for rd in round_dates_list if rd.get("round") == current_r), None
    )
    if current_round_dates:
        r_start_str = current_round_dates.get("start_date")
        r_end_str = current_round_dates.get("end_date")
        print(
            _("Periodo Turno {round_num}: {start} - {end}").format(
                round_num=current_r,
                start=format_date_locale(r_start_str),
                end=format_date_locale(r_end_str),
            )
        )
        try:
            # Calcola giorni rimanenti per il turno
            time_left_round = calcola_tempo_rimanente(r_end_str)
            if time_left_round:
                if time_left_round.total_seconds() < 0:
                    print(
                        _(" -> Termine turno superato da {days} giorni.").format(
                            days=abs(time_left_round.days)
                        )
                    )
                else:
                    days_left_round = time_left_round.days
                    if days_left_round == 0 and time_left_round.total_seconds() > 0:
                        print(_(" -> Ultimo giorno per completare il turno."))
                    elif days_left_round > 0:
                        print(
                            _(" -> Giorni rimanenti per il turno: {days}").format(
                                days=days_left_round
                            )
                        )
        except (ValueError, TypeError):
            # Ignora errore se le date non sono valide
            pass
    # Mostra giorni rimanenti alla fine del torneo
    try:
        time_left_tournament = calcola_tempo_rimanente(end_d_str)
        if time_left_tournament:
            if time_left_tournament.total_seconds() < 0:
                print(_("Termine torneo superato."))
            else:
                days_left_tournament = time_left_tournament.days
                if (
                    days_left_tournament == 0
                    and time_left_tournament.total_seconds() > 0
                ):
                    print("Ultimo giorno del torneo.")
                elif days_left_tournament > 0:
                    print(
                        _("Giorni rimanenti alla fine del torneo: {days}").format(
                            days=days_left_tournament
                        )
                    )
        else:
            raise ValueError()
    except (ValueError, TypeError):
        print(
            _(
                "Data fine torneo ('{date}') non valida per calcolo giorni rimanenti."
            ).format(date=format_date_locale(end_d_str))
        )
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
                        pending_match_count += 1
            break  # Trovato il round corrente, esci dal loop
    if found_current_round_data:
        if pending_match_count > 0:
            print(
                _(
                    "\nPartite da giocare/registrare per il Turno {round_num}: {count}"
                ).format(round_num=current_r, count=pending_match_count)
            )
            # La lista dettagliata verrà mostrata da update_match_result
        else:
            # Se il turno corrente è valido e non ci sono partite pendenti
            if current_r is not None and total_r is not None and current_r <= total_r:
                print(
                    _(
                        "\nTutte le partite del Turno {round_num} sono state registrate."
                    ).format(round_num=current_r)
                )
    # Caso: il torneo è finito (turno corrente > totale)
    elif current_r is not None and total_r is not None and current_r > total_r:
        print(_("\nIl torneo è concluso."))
    else:  # Caso: dati del turno corrente non trovati (potrebbe essere un errore)
        print(
            _("\nDati per il Turno {round_num} non trovati o turno non valido.").format(
                round_num=current_r
            )
        )


def save_suspended_tournament_summary(torneo_obj, filename_base):
    """Genera un file di testo riepilogativo per un torneo con creazione sospesa."""
    try:
        report_filename = f"{filename_base}_sospeso.txt"
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(
                _("Riepilogo del torneo in preparazione: {}\n").format(
                    torneo_obj.get("name", _("Senza Nome"))
                )
            )
            f.write(_("Luogo: {}\n").format(torneo_obj.get("site", _("N/D"))))
            f.write(
                _("Date: {} - {}\n").format(
                    torneo_obj.get("start_date", _("N/D")),
                    torneo_obj.get("end_date", _("N/D")),
                )
            )
            f.write(
                _("Turni previsti: {}\n").format(
                    torneo_obj.get("total_rounds", _("N/D"))
                )
            )
            f.write(
                _("Tempo di riflessione: {}\n\n").format(
                    torneo_obj.get("time_control", _("N/D"))
                )
            )

            players = torneo_obj.get("players", [])
            f.write(_("Giocatori inseriti: {}\n").format(len(players)))
            if not players:
                f.write(_("Nessun giocatore inserito finora.\n"))
            else:
                for idx, p in enumerate(players, 1):
                    nome_cognome = (
                        f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
                    )
                    id_player = p.get("id", "")
                    elo = p.get("initial_elo", p.get("elo_standard", 0))
                    f.write(
                        _("{idx:02d}. {name} (ID: {id}, Elo: {elo})\n").format(
                            idx=idx, name=nome_cognome, id=id_player, elo=elo
                        )
                    )
            f.write(f"\n\nTornello ({VERSIONE})\n")
        print(
            _("Riepilogo promemoria salvato in: '{report}'").format(
                report=report_filename
            )
        )
    except Exception as e:
        print(_("Errore nel salvataggio del riepilogo sospeso: {e}").format(e=e))


def generate_ics_content(torneo):
    """
    Genera il contenuto di un file iCalendar (.ics) con tutte le partite
    pianificate del torneo.

    Risponde con il contenuto e con l'elenco delle partite che non sono
    entrate, come coppie di turno e identificativo: una scacchiera che manca
    dal calendario va detta a chi esporta, non lasciata sparire.
    """
    partite_saltate = []
    rounds = torneo.get("rounds", [])
    name = torneo.get("name", "Torneo")
    t_id = torneo.get("tournament_id", "TEST")

    tc = torneo.get("time_control", {})
    if isinstance(tc, dict):
        minutes = tc.get("minutes", 60)
        inc = tc.get("increment", 0)
        # Supponiamo 60 mosse di durata media per calcolare la fine stimata
        game_duration = int(minutes * 2 + (inc * 60) / 60)
    else:
        game_duration = 180  # 3 ore di default

    from datetime import datetime, timedelta

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Tornello//Chess Tournament Calendar//IT",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    players_dict = torneo.get("players_dict", {})
    if not players_dict:
        players_dict = {p["id"]: p for p in torneo.get("players", [])}

    for r in rounds:
        r_num = r.get("round", 1)
        matches = r.get("matches", [])
        matches_sorted = sorted(matches, key=lambda x: x.get("id", 0))
        for m in matches:
            if m.get("is_scheduled") and m.get("schedule_info"):
                sched = m["schedule_info"]
                date_str = sched.get("date")
                time_str = sched.get("time")
                if not date_str or not time_str:
                    continue

                w_id = m.get("white_player_id")
                b_id = m.get("black_player_id")
                w_p = players_dict.get(w_id, {})
                b_p = players_dict.get(b_id, {}) if b_id else None
                w_name = (
                    f"{w_p.get('last_name', '')} {w_p.get('first_name', '')}".strip()
                )
                b_name = (
                    f"{b_p.get('last_name', '')} {b_p.get('first_name', '')}".strip()
                    if b_p
                    else "BYE"
                )

                try:
                    dt_start = datetime.strptime(
                        f"{date_str} {time_str}", "%Y-%m-%d %H:%M"
                    )
                    dt_end = dt_start + timedelta(minutes=game_duration)
                except ValueError:
                    # Le partite senza data sono gia' state scartate sopra: qui
                    # arriva solo chi la data ce l'ha ma scritta male.
                    partite_saltate.append((r_num, m.get("id")))
                    continue

                board_num = matches_sorted.index(m) + 1
                uid = f"Tornello_{t_id}_R{r_num}_M{m.get('id', 0)}@tornello"
                summary = (
                    f"Turno {r_num} - Scacchiera {board_num}: {w_name} vs {b_name}"
                )

                arbiter = sched.get("arbiter") or torneo.get("chief_arbiter") or "N/D"
                channel = sched.get("channel") or "N/D"

                description = f"Torneo: {name}\\nTurno: {r_num}\\nScacchiera: {board_num}\\nArbitro: {arbiter}"

                lines.extend(
                    [
                        "BEGIN:VEVENT",
                        f"UID:{uid}",
                        f"DTSTART:{dt_start.strftime('%Y%m%dT%H%M%S')}",
                        f"DTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}",
                        f"SUMMARY:{summary}",
                        f"DESCRIPTION:{description}",
                        f"LOCATION:{channel}",
                        "END:VEVENT",
                    ]
                )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n", partite_saltate
