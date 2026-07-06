import os
import traceback
from datetime import datetime
from config import DATE_FORMAT_ISO, DEFAULT_ELO
from utils import format_date_locale, format_points, sanitize_filename, _ensure_players_dict
from stats import (
    compute_buchholz,
    compute_buchholz_cut1,
    compute_aro,
    compute_sonneborn_berger,
    compute_direct_encounter,
    compute_played_rounds_rep,
    compute_number_of_wins,
    compute_number_of_blacks,
    compute_cumulative,
    compute_tiebreak_value,
)
from tiebreak_criteria import (
    get_column_header, get_criterion_display_name,
    migrate_old_tiebreaks, get_default_tiebreaks,
    normalize_tiebreak_entry,
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
        out.write(
            _("Nome Torneo: {name} - ").format(name=tournament_name_for_file)
        )
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
        out.write(
            _(" (Nessuna partita ancora definita o caricata per questo turno)\n")
        )
        return out.getvalue()

    for match in all_matches_in_round:
        wp_obj = players_dict.get(match.get("white_player_id"))
        bp_obj = players_dict.get(match.get("black_player_id"))

        if bp_obj is None and wp_obj is not None:
            bye_player_display_line = _(" {first_name} {last_name} ({elo}) ha il BYE").format(
                first_name=wp_obj.get("first_name", "?"),
                last_name=wp_obj.get("last_name", "?"),
                elo=int(wp_obj.get("initial_elo", 0)),
            )
            continue
        if bp_obj is None or wp_obj is None:
            continue

        wp_name = (
            f"{wp_obj.get('first_name', _('Bianco?'))} {wp_obj.get('last_name', '')} ({int(wp_obj.get('initial_elo', 0))})"
        )
        if wp_obj.get("withdrawn"):
            wp_name += " [RIT]"
        bp_name = (
            f"{bp_obj.get('first_name', _('Nero?'))} {bp_obj.get('last_name', '')} ({int(bp_obj.get('initial_elo', 0))})"
        )
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
    out.write(f"Nome Torneo: {tournament_name_for_file} - ")
    out.write(f"Turno: {round_num}\n")
    out.write(
        f" Periodo Turno: {start_date_turn_display} - {end_date_turn_display}\n"
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
                f"   {time_str} IDG:{match.get('id', '?')}, {wp_n} vs {bp_n}, Canale: {schedule.get('channel', 'N/D')}, Arbitro: {schedule.get('arbiter', 'N/D')}\n"
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
                f"    {time_str} IDG:{match.get('id', '?')}, {wp_n} vs {bp_n}, Canale: {schedule.get('channel', 'N/D')}, Arbitro: {schedule.get('arbiter', 'N/D')}\n"
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
    custom_path = torneo.get("custom_save_path")
    if custom_path:
        from utils import resolve_and_verify_save_path
        resolved_path, warning = resolve_and_verify_save_path(custom_path)
        if warning:
            print(warning)
        filename = os.path.join(resolved_path, filename)

    try:
        text = get_current_round_report_text(torneo, current_round_num)
        with open(filename, "w", encoding="utf-8-sig") as f:
            f.write(text)
        print(
            _("File {filename} aggiornato con raggruppamento ritirati.").format(
                filename=filename
            )
        )
    except IOError as e:
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
    custom_path = torneo.get("custom_save_path")
    if custom_path:
        from utils import resolve_and_verify_save_path
        resolved_path, warning = resolve_and_verify_save_path(custom_path)
        if warning:
            print(warning)
        filename = os.path.join(resolved_path, filename)

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
            f.write("=" * 80 + "\n")
            f.write(
                "\n"
                + "=" * 30
                + _(" DETTAGLIO TURNO {round_num} CONCLUSO ").format(
                    round_num=completed_round_number
                )
                + "=" * 26
                + "\n"
            )
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
            f.write("\t" + "-" * 76 + "\n")
            header_partite = _(
                "Sc | ID  | Bianco                       [Elo] (Pt) - Nero                         [Elo] (Pt) | Risultato"
            )
            f.write(f"\t{header_partite}\n")
            f.write("\t" + "-" * len(header_partite) + "\n")
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
                        f"{'---':<3}| "
                        f"{match_id:<4}| "
                        f"{w_name:<24} [{w_elo:>4}] ({w_pts:<4}) - {'BYE':<31} | BYE"
                    )
                    f.write(f"\t{line}\n")
                else:
                    line = _(
                        "{dashes:<3}| {match_id:<4}| Errore Giocatore Bye ID: {player_id:<10} | BYE"
                    ).format(dashes="---", match_id=match_id, player_id=white_p_id)
                    f.write(f"\t{line}\n")
            
            f.write(f"\n\nTornello ({VERSIONE})\n")
        print(
            _(
                "Dettaglio Turno Concluso {round_num} salvato nel file separato '{filename}'"
            ).format(round_num=completed_round_number, filename=filename)
        )
    except IOError as e:
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
            val = compute_tiebreak_value(p_id, torneo, entry["key"], entry.get("modifiers"))
            return float(val) if val is not None else 0.0
        # Fallback per chiavi legacy dirette
        if criterion == "buchholz_cut1":
            return compute_buchholz_cut1(p_id, torneo)
        elif criterion == "buchholz":
            return compute_buchholz(p_id, torneo)
        elif criterion == "aro":
            val = compute_aro(p_id, torneo)
            return val if val is not None else 0.0
        elif criterion == "initial_elo":
            elo_initial_raw = float(player_item.get("initial_elo", 0))
            return elo_initial_raw if elo_initial_raw > 0 else DEFAULT_ELO
        elif criterion == "sonneborn_berger":
            return compute_sonneborn_berger(p_id, torneo)
        elif criterion == "direct_encounter":
            return compute_direct_encounter(p_id, torneo)
        elif criterion == "played_rounds_rep":
            return compute_played_rounds_rep(p_id, torneo)
        elif criterion == "number_of_wins":
            return compute_number_of_wins(p_id, torneo)
        elif criterion == "number_of_blacks":
            return compute_number_of_blacks(p_id, torneo)
        elif criterion == "cumulative":
            return compute_cumulative(p_id, torneo)
        return 0.0
    
    # Nuovo formato: criterio come dizionario {"key": "BH", "modifiers": {...}}
    if isinstance(criterion, dict):
        key = criterion.get("key", "")
        modifiers = criterion.get("modifiers", {})
        val = compute_tiebreak_value(p_id, torneo, key, modifiers)
        return float(val) if val is not None else 0.0
    
    return 0.0


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
            val = " " * max(0, len(hdr) - 4) + "----"
            return hdr, val
        
        raw_val = compute_tiebreak_value(p_id, torneo, key, modifiers)
        if raw_val is None:
            val = " " * max(0, len(hdr) - 3) + "---"
        else:
            # Criteri che restituiscono interi
            int_criteria = {"WIN", "WON", "BPG", "BWG", "REP", "STD", "TPN",
                           "ARO", "TPR", "PTP", "APRO", "APPO", "RTNG", "AOB"}
            if key in int_criteria:
                width = max(len(hdr), 4)
                val = f"{int(raw_val):{width}d}"
            else:
                # Criteri float (BH, FB, SB, PS, DE)
                width = max(len(hdr), 5)
                val = f"{float(raw_val):{width}.1f}"
        return hdr, val
    
    # Retrocompatibilità: vecchio formato stringa
    if isinstance(criterion, str):
        if criterion == "points":
            hdr = _("Punti")
            val = f"{float(player.get('points', 0.0)):5.1f}"
        elif criterion == "buchholz_cut1":
            hdr = _("Bucch-1")
            val = f"{float(compute_buchholz_cut1(p_id, torneo)):7.2f}" if not is_rit else "   ----"
        elif criterion == "buchholz":
            hdr = _("Bucch")
            val = f"{float(compute_buchholz(p_id, torneo)):5.1f}" if not is_rit else " ----"
        elif criterion == "aro":
            hdr = _(" ARO")
            aro_val = compute_aro(p_id, torneo)
            val = f"{int(aro_val):4d}" if aro_val is not None and not is_rit else " ---"
        elif criterion == "sonneborn_berger":
            hdr = _("Sonn-B")
            sb_val = compute_sonneborn_berger(p_id, torneo)
            val = f"{float(sb_val):6.2f}" if not is_rit else "  ----"
        elif criterion == "direct_encounter":
            hdr = _("ScrDir")
            de_val = compute_direct_encounter(p_id, torneo)
            val = f"{float(de_val):6.1f}" if not is_rit else "  ----"
        elif criterion == "played_rounds_rep":
            hdr = _("REP")
            rep_val = compute_played_rounds_rep(p_id, torneo)
            val = f"{int(rep_val):3d}" if not is_rit else "  -"
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


def get_standings_text(torneo, final=False):
    """
    Genera la classifica (parziale o finale) del torneo come stringa.
    Mostra sempre gli spareggi, incluso ARO. Mostra Perf/Var Elo solo alla fine.
    Include la variazione rispetto alla posizione iniziale in tabellone (Seed).
    """
    import io
    from datetime import datetime
    from tournament import ricalcola_punti_tutti_giocatori
    from utils import format_date_locale
    
    ricalcola_punti_tutti_giocatori(torneo)
    players = torneo.get("players", [])
    if not players:
        return _("Attenzione: Nessun giocatore per generare la classifica.")

    if "players_dict" not in torneo or len(torneo["players_dict"]) != len(players):
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

    for p in players:
        p_id = p.get("id")
        if not p_id:
            continue
        p["buchholz"] = compute_buchholz(p_id, torneo)
        p["buchholz_cut1"] = compute_buchholz_cut1(p_id, torneo)
        p["aro"] = compute_aro(p_id, torneo)
        if p.get("withdrawn", False):
            p["final_rank"] = "RIT"

    def sort_key_standings(player_item):
        # Criteri impliciti sempre attivi: punti (decrescente) e stato attivo/ritirato
        try:
            pts = float(player_item.get("points", 0.0))
        except (ValueError, TypeError):
            pts = 0.0
        withdrawn_val = 1 if not player_item.get("withdrawn", False) else 0
        sort_tuple = [-pts, -withdrawn_val]
        
        # Criteri di spareggio configurati
        raw_tiebreaks = torneo.get("tiebreaks", None)
        if raw_tiebreaks is None:
            tiebreak_order = get_default_tiebreaks()
        elif raw_tiebreaks and isinstance(raw_tiebreaks[0], str):
            tiebreak_order = migrate_old_tiebreaks(raw_tiebreaks)
        else:
            tiebreak_order = raw_tiebreaks
        
        for criterion in tiebreak_order:
            val = get_criterion_value(player_item, criterion, torneo)
            # Aggiunge il valore invertito per l'ordinamento decrescente
            sort_tuple.append(-val)
        return tuple(sort_tuple)


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

    try:
        if is_initial_list:
            players_sorted = players_for_seeding
            for i, p_item in enumerate(players_sorted):
                p_item["display_rank"] = i + 1
        else:
            players_sorted = sorted(players, key=sort_key_standings)
            if not final or (
                players_sorted
                and "final_rank" not in players_sorted[0]
                and not players_sorted[0].get("withdrawn")
            ):
                current_display_rank = 0
                last_sort_key_tuple = None
                for i, p_item in enumerate(players_sorted):
                    if p_item.get("withdrawn", False):
                        p_item["display_rank"] = "RIT"
                        continue
                    current_sort_key_tuple = sort_key_standings(p_item)
                    if current_sort_key_tuple != last_sort_key_tuple:
                        current_display_rank = i + 1
                    p_item["display_rank"] = current_display_rank
                    last_sort_key_tuple = current_sort_key_tuple
            elif final:
                for i, p_item in enumerate(players_sorted):
                    if "final_rank" in p_item:
                        p_item["display_rank"] = p_item["final_rank"]
                    elif p_item.get("withdrawn", False):
                        p_item["display_rank"] = "RIT"
                    else:
                        p_item["display_rank"] = i + 1
    except Exception as e:
        print(f"Errore durante l'ordinamento dei giocatori per la classifica: {e}")
        traceback.print_exc()
        players_sorted = players

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
        out.write(
            _("Vice Arbitri: {arbiters}\n").format(arbiters=deputy_arbiters_str)
        )
    tc = torneo.get("time_control")
    cat = torneo.get("tournament_category")
    if not cat and isinstance(tc, dict):
        from stats import classify_tournament_category
        cat = classify_tournament_category(tc.get("minutes", 60), tc.get("increment", 0))
    if not cat:
        cat = "standard"
    cat_disp = cat.capitalize()

    tc_str = "N/D"
    if isinstance(tc, dict):
        tc_str = f"{tc.get('minutes', 0)} min + {tc.get('increment', 0)} sec ({cat_disp})"
    elif isinstance(tc, str):
        tc_str = f"{tc} ({cat_disp})"
    out.write(
        _("Controllo Tempo: {time_control}\n").format(
            time_control=tc_str
        )
    )
    out.write(_("Sistema di Abbinamento: Svizzero Olandese (via bbpPairings)\n"))
    
    # Lista ordinata per importanza dei criteri di spareggio attivi negli headers
    raw_tiebreaks = torneo.get("tiebreaks", None)
    if raw_tiebreaks is None:
        tiebreak_order_display = get_default_tiebreaks()
    elif raw_tiebreaks and isinstance(raw_tiebreaks[0], str):
        tiebreak_order_display = migrate_old_tiebreaks(raw_tiebreaks)
    else:
        tiebreak_order_display = raw_tiebreaks
    
    # Genera la stringa dei nomi dei criteri per il report
    criteri_display = []
    for entry in tiebreak_order_display:
        if isinstance(entry, dict):
            criteri_display.append(get_criterion_display_name(entry.get("key", ""), entry.get("modifiers")))
        elif isinstance(entry, str):
            # Retrocompatibilità vecchie chiavi stringa
            criteri_nomi_legacy = {
                "points": _("Punti"), "withdrawn": _("Ritirato"),
                "buchholz_cut1": _("Buchholz Cut-1"), "buchholz": _("Buchholz Totale"),
                "aro": _("ARO"), "initial_elo": _("Elo Iniziale"),
                "sonneborn_berger": _("Sonneborn-Berger"), "direct_encounter": _("Scontro Diretto"),
                "played_rounds_rep": _("REP (Turni Giocati)"), "number_of_wins": _("Vittorie"),
                "number_of_blacks": _("Neri"), "cumulative": _("Cumulativo"),
            }
            criteri_display.append(criteri_nomi_legacy.get(entry, entry))
    out.write(_("Criteri di Spareggio: {tiebreaks}\n").format(
        tiebreaks=", ".join(criteri_display)
    ))
    
    out.write(
        _("Data Report: {date} {time}\n").format(
            date=format_date_locale(datetime.now().date()),
            time=datetime.now().strftime("%H:%M:%S"),
        )
    )

    out.write("-" * 80 + "\n")
    out.write(f"{status_line}\n")
    out.write("-" * 80 + "\n")

    # --- HEADER TABELLA DINAMICO ---
    header_table = _("Pos. (Tab)   Titolo Nome Cognome               [EloIni] Punti")
    
    # Filtriamo i criteri che non hanno una colonna numerica separata
    dynamic_cols = []
    for crit in tiebreak_order_display:
        if isinstance(crit, dict):
            key = crit.get("key", "")
            if key not in ["points", "withdrawn", "initial_elo"]:
                dynamic_cols.append(crit)
        elif isinstance(crit, str):
            if crit not in ["points", "withdrawn", "initial_elo"]:
                dynamic_cols.append(crit)
    
    headers_list = []
    for crit in dynamic_cols:
        col_res = get_column_data(crit, {}, torneo)
        if col_res:
            headers_list.append(col_res[0])
            
    if headers_list:
        header_table += " " + " ".join(headers_list)
        
    if final:
        header_table += " " + _("Perf") + " " + _("Elo Var.")
        
    out.write(header_table + "\n")
    out.write("-" * len(header_table) + "\n")
 
    for player in players_sorted:
        rank_to_show = player.get("display_rank", "?")
 
        p_id = player.get("id")
        starting_rank = seeding_map.get(p_id, 0)
        delta_str = ""
        if isinstance(rank_to_show, (int, float)):
            delta = starting_rank - int(rank_to_show)
            delta_str = f"({delta:+})"
            rank_display_str = f"{int(rank_to_show):>3} {delta_str:<7}"
        else:
            rank_display_str = f"{str(rank_to_show):>3} {' ':<7}"
 
        fide_title = str(player.get("fide_title", "")).strip().upper()
        player_name_str = f"{player.get('last_name', 'N/D')}, {player.get('first_name', 'N/D')}"
 
        title_display_str = f"{fide_title:<3}"
        name_display_str = f"{player_name_str:<27.27}"
        elo_ini_str = f"[{int(player.get('initial_elo', DEFAULT_ELO)):4d}]"
 
        # Costruzione dinamica della riga dati
        pts_val = float(player.get("points", 0.0))
        line = f"{rank_display_str} {title_display_str} {name_display_str} {elo_ini_str} {pts_val:5.1f}"
        
        vals_list = []
        for crit in dynamic_cols:
            col_res = get_column_data(crit, player, torneo)
            if col_res:
                vals_list.append(col_res[1])
                
        if vals_list:
            line += " " + " ".join(vals_list)
 
        if final:
            if player.get("withdrawn", False):
                perf_str, elo_change_str = "----", " ---"
            else:
                perf_val = player.get("performance_rating")
                perf_str = (
                    f"{int(perf_val):4d}" if perf_val is not None else "----"
                )
                elo_change_val = player.get("elo_change")
                elo_change_str = (
                    f"{int(elo_change_val):+4d}"
                    if elo_change_val is not None
                    else " ---"
                )
            line += f" {perf_str} {elo_change_str}"
 
        if player.get("withdrawn", False):
            line = f"{line.ljust(90)} [RITIRATO]"
 
        out.write(line + "\n")

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
    custom_path = torneo.get("custom_save_path")
    if custom_path:
        from utils import resolve_and_verify_save_path
        resolved_path, warning = resolve_and_verify_save_path(custom_path)
        if warning:
            print(warning)
        filename = os.path.join(resolved_path, filename)

    try:
        text = get_standings_text(torneo, final)
        with open(filename, "w", encoding="utf-8-sig") as f:
            f.write(text)
        print(
            _("File classifica '{filename}' salvato/sovrascritto.").format(
                filename=filename
            )
        )
    except IOError as e:
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
    print(_("\n--- Stato Torneo ---"))
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
    print("--------------------\n")


def save_suspended_tournament_summary(torneo_obj, filename_base):
    """Genera un file di testo riepilogativo per un torneo con creazione sospesa."""
    try:
        report_filename = f"{filename_base}_sospeso.txt"
        with open(report_filename, "w", encoding="utf-8") as f:
            f.write(
                f"--- RIEPILOGO TORNEO IN PREPARAZIONE: {torneo_obj.get('name', 'Senza Nome')} ---\n\n"
            )
            f.write(f"Luogo: {torneo_obj.get('site', 'N/D')}\n")
            f.write(
                f"Date: {torneo_obj.get('start_date', 'N/D')} - {torneo_obj.get('end_date', 'N/D')}\n"
            )
            f.write(f"Turni previsti: {torneo_obj.get('total_rounds', 'N/D')}\n")
            f.write(
                f"Tempo di riflessione: {torneo_obj.get('time_control', 'N/D')}\n\n"
            )

            players = torneo_obj.get("players", [])
            f.write(f"--- GIOCATORI INSERITI ({len(players)}) ---\n")
            if not players:
                f.write("Nessun giocatore inserito finora.\n")
            else:
                for idx, p in enumerate(players, 1):
                    nome_cognome = (
                        f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
                    )
                    id_player = p.get("id", "")
                    elo = p.get("initial_elo", p.get("elo_standard", 0))
                    f.write(
                        f"{idx:02d}. {nome_cognome} (ID: {id_player}, Elo: {elo})\n"
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
    """
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
        game_duration = 180 # 3 ore di default
        
    from datetime import datetime, timedelta
    
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Tornello//Chess Tournament Calendar//IT",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH"
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
                w_name = f"{w_p.get('last_name', '')} {w_p.get('first_name', '')}".strip()
                b_name = f"{b_p.get('last_name', '')} {b_p.get('first_name', '')}".strip() if b_p else "BYE"
                
                try:
                    dt_start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                    dt_end = dt_start + timedelta(minutes=game_duration)
                except Exception:
                    continue
                    
                board_num = matches_sorted.index(m) + 1
                uid = f"Tornello_{t_id}_R{r_num}_M{m.get('id', 0)}@tornello"
                summary = f"Turno {r_num} - Scacchiera {board_num}: {w_name} vs {b_name}"
                
                arbiter = sched.get("arbiter") or torneo.get("chief_arbiter") or "N/D"
                channel = sched.get("channel") or "N/D"
                
                description = f"Torneo: {name}\\nTurno: {r_num}\\nScacchiera: {board_num}\\nArbitro: {arbiter}"
                
                lines.extend([
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTART:{dt_start.strftime('%Y%m%dT%H%M%S')}",
                    f"DTEND:{dt_end.strftime('%Y%m%dT%H%M%S')}",
                    f"SUMMARY:{summary}",
                    f"DESCRIPTION:{description}",
                    f"LOCATION:{channel}",
                    "END:VEVENT"
                ])
                
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
