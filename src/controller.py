import os
import json
import glob
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from typing import List, Optional

from models import Tournament, Player, Match, Round, RoundDate, ResultEntry
from config import (
    FIDE_DB_LOCAL_FILE,
    FIDE_DB_JSON_LEGACY,
    PLAYER_DB_FILE,
    DATE_FORMAT_ISO,
    DEFAULT_K_FACTOR,
    DEFAULT_ELO,
)
from utils import (
    format_date_locale,
    sanitize_filename,
    create_backup,
    parse_flexible_date,
)
from db_players import (
    load_players_db,
    sincronizza_db_personale,
    aggiorna_db_fide_locale,
)
from engine import handle_bbpairings_failure
from tournament import (
    load_tournament,
    save_tournament,
    generate_pairings_for_round,
    time_machine_torneo,
)
from stats import (
    get_k_factor,
    compute_buchholz,
    compute_buchholz_cut1,
    compute_aro,
    calculate_performance_rating,
    calculate_elo_change,
    parse_time_control,
    classify_tournament_category,
    compute_tiebreak_value,
)
from tiebreak_criteria import (
    get_default_tiebreaks,
    migrate_old_tiebreaks,
)
from reports import (
    save_current_tournament_round_file,
    append_completed_round_to_history_file,
    save_standings_text,
)


class UIAdapter(ABC):
    @abstractmethod
    def show_message(self, message: str) -> None:
        pass

    @abstractmethod
    def show_error(self, message: str) -> None:
        pass

    @abstractmethod
    def confirm(self, prompt: str, default: bool = True) -> bool:
        pass

    @abstractmethod
    def input_text(self, prompt: str, default: str = "") -> str:
        pass

    @abstractmethod
    def input_int(
        self, prompt: str, min_val: Optional[int] = None, max_val: Optional[int] = None
    ) -> int:
        pass

    @abstractmethod
    def select_option(self, prompt: str, options: List[str]) -> int:
        pass

    @abstractmethod
    def input_players(
        self,
        players_db: dict,
        existing_players: List[Player],
        tournament: Tournament,
        tournament_filename: Optional[str],
    ) -> Optional[List[Player]]:
        pass

    @abstractmethod
    def confirm_player_list(self, tournament: Tournament, players_db: dict) -> bool:
        pass

    @abstractmethod
    def update_match_results(self, tournament: Tournament) -> bool:
        pass

    @abstractmethod
    def play_sound(
        self,
        sound_name: str,
        tournament: Optional[Tournament] = None,
        sync: bool = False,
    ) -> None:
        pass

    @abstractmethod
    def display_tournament_status(self, tournament: Tournament) -> None:
        pass


class TournamentController:
    def __init__(self, ui_adapter: UIAdapter):
        self.ui = ui_adapter
        self.players_db = load_players_db()
        self.tournament: Optional[Tournament] = None
        self.active_filename: Optional[str] = None

    def start(self) -> None:
        self.ui.show_message(_("\nBENVENUTI! Sono Tornello V9"))
        self.ui.play_sound("avvio")

        self._check_fide_db()
        self._select_or_create_tournament()

        if self.tournament:
            self._main_loop()

    def _check_fide_db(self) -> None:
        self.ui.show_message(_("\nVerifica stato database FIDE locale..."))

        # Fallback: se esiste il vecchio JSON ma non il nuovo SQLite, elimina il JSON
        from fide_db import fide_db_exists, cleanup_legacy_json

        if not fide_db_exists() and os.path.exists(FIDE_DB_JSON_LEGACY):
            cleanup_legacy_json()
            self.ui.show_message(
                _(
                    "Vecchio database FIDE JSON rimosso. È necessario riscaricare il database."
                )
            )

        db_fide_esiste = os.path.exists(FIDE_DB_LOCAL_FILE)
        db_fide_appena_aggiornato = False

        if not db_fide_esiste:
            self.ui.show_message(
                _("\nIl database FIDE locale non è presente sul tuo computer.")
            )
            if self.ui.confirm(
                _(
                    "Vuoi scaricarlo ora? (L'operazione potrebbe richiedere alcuni minuti)"
                )
            ):
                if aggiorna_db_fide_locale():
                    db_fide_appena_aggiornato = True
                    self.ui.show_message(
                        _("Database FIDE locale aggiornato con successo.")
                    )
        else:
            try:
                file_mod_timestamp = os.path.getmtime(FIDE_DB_LOCAL_FILE)
                file_age_days = (
                    datetime.now() - datetime.fromtimestamp(file_mod_timestamp)
                ).days
                self.ui.show_message(
                    _("Info: Il tuo database FIDE locale ha {} giorni.").format(
                        file_age_days
                    )
                )
                if file_age_days >= 32:
                    self.ui.show_message(
                        _(
                            "Essendo trascorsi più di 32 giorni dall'ultimo download, potrebbe essere stato rilasciato un aggiornamento."
                        )
                    )
                    if self.ui.confirm(
                        _(
                            "Si consiglia di aggiornarlo. Vuoi scaricare la versione più recente?"
                        )
                    ):
                        if aggiorna_db_fide_locale():
                            db_fide_appena_aggiornato = True
            except Exception as e:
                self.ui.show_error(
                    _(
                        "Errore nel controllare la data del file DB FIDE locale: {}"
                    ).format(e)
                )

        if os.path.exists(FIDE_DB_LOCAL_FILE):
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
                if self.ui.confirm(prompt_sync):
                    sincronizza_db_personale()

    def _select_or_create_tournament(self) -> None:
        tournament_files_pattern = "Tornello - *.json"
        potential_tournament_files = [
            f
            for f in glob.glob(tournament_files_pattern)
            if "- concluso_" not in os.path.basename(f).lower()
            and os.path.basename(f) != os.path.basename(PLAYER_DB_FILE)
            and os.path.basename(f) != "Tornello - Settings.json"
        ]

        deve_creare_nuovo_torneo = False
        nome_nuovo_torneo_suggerito = None

        if not potential_tournament_files:
            self.ui.show_message(_("Nessun torneo esistente trovato."))
            if self.ui.confirm(_("Vuoi creare un nuovo torneo?")):
                deve_creare_nuovo_torneo = True
            else:
                self.ui.show_message(_("Uscita dal programma."))
                self._exit_program(0)
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
                self.ui.show_message(
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

            self.ui.show_message(
                _(
                    "\nTrovato un solo torneo esistente: '{name}' (File: {filename})"
                ).format(
                    name=single_tournament_name_guess,
                    filename=os.path.basename(single_found_filepath),
                )
            )

            choice_str = self.ui.input_text(
                _(
                    "Vuoi caricare '{name}'? (Premi INVIO per sì, o inserisci il nome di un NUOVO torneo da creare): "
                ).format(name=single_tournament_name_guess)
            ).strip()

            if not choice_str:
                self.active_filename = single_found_filepath
                self.ui.show_message(
                    _("Caricamento di '{name}'...").format(
                        name=single_tournament_name_guess
                    )
                )
                torneo_dict = load_tournament(self.active_filename)
                if torneo_dict:
                    self.tournament = Tournament.from_dict(torneo_dict)
                else:
                    self.ui.show_error(
                        _(
                            "Errore fatale nel caricamento del torneo '{filename}'."
                        ).format(filename=self.active_filename)
                    )
                    if self.ui.confirm(_("Vuoi creare un nuovo torneo?")):
                        deve_creare_nuovo_torneo = True
                    else:
                        self._exit_program(0)
            else:
                deve_creare_nuovo_torneo = True
                nome_nuovo_torneo_suggerito = choice_str
        else:
            self.ui.show_message(_("\n--- Tornei Esistenti Trovati ---"))
            tournament_options = []
            for idx, filepath in enumerate(potential_tournament_files):
                try:
                    with open(filepath, "r", encoding="utf-8") as f_temp:
                        data_temp = json.load(f_temp)
                    t_name = data_temp.get("name", _("Nome Sconosciuto"))
                    t_start = data_temp.get("start_date")
                    t_end = data_temp.get("end_date")
                    start_display = format_date_locale(t_start) if t_start else "N/D"
                    end_display = format_date_locale(t_end) if t_end else "N/D"
                    tournament_options.append(
                        {"id_lista": idx + 1, "filepath": filepath, "name": t_name}
                    )
                    self.ui.show_message(
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
                    self.ui.show_error(
                        _(
                            " Errore durante la lettura dei metadati da {filename}: {error} (file saltato)"
                        ).format(filename=os.path.basename(filepath), error=e)
                    )

            if not tournament_options:
                self.ui.show_message(
                    _(
                        "Nessun torneo valido trovato nonostante la presenza di file. Si procederà con la creazione."
                    )
                )
                deve_creare_nuovo_torneo = True
            else:
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
                    self.ui.show_message(
                        _("\n*** TROVATI TORNEI CON CREAZIONE SOSPESA ***")
                    )
                    for st in suspended_tournaments:
                        self.ui.show_message(
                            _(" - '{name}' (File: {filename})").format(
                                name=st["name"],
                                filename=os.path.basename(st["filepath"]),
                            )
                        )

                    if len(suspended_tournaments) == 1:
                        if self.ui.confirm(
                            _("Vuoi riprendere la creazione di '{name}'?").format(
                                name=suspended_tournaments[0]["name"]
                            )
                        ):
                            self.active_filename = suspended_tournaments[0]["filepath"]
                            torneo_dict = load_tournament(self.active_filename)
                            self.tournament = Tournament.from_dict(torneo_dict)
                            deve_creare_nuovo_torneo = False
                            self.ui.show_message(
                                _("Ripresa creazione torneo '{name}'...").format(
                                    name=self.tournament.name
                                )
                            )
                    else:
                        self.ui.show_message(
                            _(
                                "Ci sono più tornei in stato sospeso. Selezionali dal menu per riprenderli."
                            )
                        )

                if not self.tournament:
                    options_list = [opt["name"] for opt in tournament_options] + [
                        _("Crea un nuovo torneo")
                    ]
                    idx_choice = self.ui.select_option(
                        _("Scegli un torneo da caricare o creane uno nuovo"),
                        options_list,
                    )
                    if idx_choice < len(tournament_options):
                        chosen = tournament_options[idx_choice]
                        self.active_filename = chosen["filepath"]
                        self.ui.show_message(
                            _("Caricamento di '{name}'...").format(name=chosen["name"])
                        )
                        torneo_dict = load_tournament(self.active_filename)
                        if torneo_dict:
                            self.tournament = Tournament.from_dict(torneo_dict)
                        else:
                            self.ui.show_error(
                                _("Errore nel caricamento del torneo. Riprova.")
                            )
                            self._exit_program(1)
                    else:
                        deve_creare_nuovo_torneo = True

        # Gestione ripresa torneo sospeso
        if (
            self.tournament
            and self.tournament.schema_version == 1
            and getattr(self.tournament, "creation_suspended", False)
        ):
            self._resume_suspended_creation()
            deve_creare_nuovo_torneo = True  # Procedi alla generazione del turno 1

        if deve_creare_nuovo_torneo or self.tournament is None:
            self._create_new_tournament(nome_nuovo_torneo_suggerito)

    def _resume_suspended_creation(self) -> None:
        self.ui.show_message(
            _("\nRipresa inserimento giocatori per '{name}'...").format(
                name=self.tournament.name
            )
        )
        res = self.ui.input_players(
            self.players_db,
            self.tournament.players,
            self.tournament,
            self.active_filename,
        )
        if res is None:
            self._exit_program(0)
        self.tournament.players = res
        self.tournament.update_players_dict()

        if not self.ui.confirm_player_list(self.tournament, self.players_db):
            self.ui.show_message(
                _(
                    "Creazione torneo annullata a causa di problemi con la lista giocatori."
                )
            )
            self._exit_program(0)

        # Rimuovi il flag di sospensione
        # Per le dataclasses possiamo usare setattr o semplicemente rimuovere/azzerare
        # Nel dizionario salvato era creation_suspended. Nella dataclass non lo salviamo più o lo resettiamo
        if hasattr(self.tournament, "creation_suspended"):
            delattr(self.tournament, "creation_suspended")

    def _create_new_tournament(self, suggested_name: Optional[str] = None) -> None:
        self.ui.show_message(_("\n--- Creazione Nuovo Torneo ---"))
        new_name = ""

        if suggested_name:
            self.ui.show_message(
                _("Nome suggerito per il nuovo torneo: '{name}'").format(
                    name=suggested_name
                )
            )
            sanitized = sanitize_filename(suggested_name)
            prospective = f"Tornello - {sanitized}.json"
            if os.path.exists(prospective):
                if self.ui.confirm(
                    _(
                        "Un file torneo '{filename}' con questo nome esiste già. Sovrascriverlo?"
                    ).format(filename=prospective)
                ):
                    new_name = suggested_name
                    self.active_filename = prospective
            else:
                new_name = suggested_name
                self.active_filename = prospective

        while not new_name:
            input_name = self.ui.input_text(
                _("Inserisci il nome del nuovo torneo")
            ).strip()
            if not input_name:
                self.ui.show_message(_("Il nome del torneo non può essere vuoto."))
                continue
            sanitized = sanitize_filename(input_name)
            prospective = f"Tornello - {sanitized}.json"
            if os.path.exists(prospective):
                if not self.ui.confirm(
                    _(
                        "Un file torneo '{filename}' con questo nome esiste già. Sovrascriverlo?"
                    ).format(filename=prospective)
                ):
                    continue
            new_name = input_name
            self.active_filename = prospective

        # Date inizio
        start_date = ""
        while not start_date:
            oggi_str_iso = datetime.now().strftime(DATE_FORMAT_ISO)
            oggi_str_locale = format_date_locale(oggi_str_iso)
            inp_date = self.ui.input_text(
                _(
                    "Inserisci data inizio ({date_format}) [Default: {default_date}]"
                ).format(date_format=DATE_FORMAT_ISO, default_date=oggi_str_locale)
            ).strip()
            if not inp_date:
                inp_date = oggi_str_iso
            try:
                dt = parse_flexible_date(inp_date)
                start_date = dt.strftime(DATE_FORMAT_ISO)
            except ValueError:
                self.ui.show_error(
                    _("Formato data non valido. Usa {date_format} o AAAAMMGG.").format(
                        date_format=DATE_FORMAT_ISO
                    )
                )

        # Date fine
        end_date = ""
        while not end_date:
            start_dt = datetime.strptime(start_date, DATE_FORMAT_ISO)
            future_dt = start_dt + timedelta(days=60)
            default_end_iso = future_dt.strftime(DATE_FORMAT_ISO)
            default_end_locale = format_date_locale(future_dt)
            inp_date = self.ui.input_text(
                _(
                    "Inserisci data fine ({date_format}) [Default: {default_date}]"
                ).format(date_format=DATE_FORMAT_ISO, default_date=default_end_locale)
            ).strip()
            if not inp_date:
                inp_date = default_end_iso
            try:
                end_dt = datetime.strptime(inp_date, DATE_FORMAT_ISO)
                if end_dt < start_dt:
                    self.ui.show_error(
                        _(
                            "La data di fine non può essere precedente alla data di inizio."
                        )
                    )
                    continue
                end_date = inp_date
            except ValueError:
                self.ui.show_error(
                    _("Formato data non valido. Usa {date_format}.").format(
                        date_format=DATE_FORMAT_ISO
                    )
                )
            except OverflowError:
                self.ui.show_error(
                    _("La data calcolata risulta troppo lontana nel futuro.")
                )

        # Turni
        total_rounds = self.ui.input_int(
            _("Inserisci il numero totale dei turni"), min_val=1
        )

        # Dettagli aggiuntivi
        site = self.ui.input_text(
            _("Luogo del torneo [Default: Luogo Sconosciuto]")
        ).strip() or _("Luogo Sconosciuto")
        fed_code = (
            self.ui.input_text(
                _("Federazione organizzante (codice 3 lettere) [Default: ITA]")
            )
            .strip()
            .upper()
            or "ITA"
        )
        fed_code = fed_code[:3]
        chief_arbiter = (
            self.ui.input_text(_("Arbitro Capo [Default: N/D]")).strip() or "N/D"
        )
        deputy_chief_arbiters = (
            self.ui.input_text(
                _("Vice Arbitri (separati da virgola) [Default: nessuno]")
            ).strip()
            or ""
        )
        # Controllo del tempo
        time_control_parsed = None
        while not time_control_parsed:
            time_control_entered = self.ui.input_text(
                _("Controllo del Tempo (es. 15+10, 90+30, 3+2) [Default: 90+30]"),
                default="90+30",
            ).strip()
            time_control_parsed = parse_time_control(time_control_entered)
            if not time_control_parsed:
                self.ui.show_error(
                    _("Formato non valido. Usa minuti+incremento o solo minuti.")
                )

        tournament_category = classify_tournament_category(
            time_control_parsed["minutes"], time_control_parsed["increment"]
        )

        initial_board1_color_setting = "white1"
        if not self.ui.confirm(_("Bianco alla prima scacchiera del Turno 1?")):
            initial_board1_color_setting = "black1"

        from tournament import calculate_dates

        round_dates_raw = calculate_dates(start_date, end_date, total_rounds)
        if round_dates_raw is None:
            self.ui.show_error(
                _(
                    "Errore fatale nel calcolo delle date dei turni. Creazione torneo annullata."
                )
            )
            self._exit_program(1)

        round_dates = [RoundDate.from_dict(rd) for rd in round_dates_raw]
        tournament_id = (
            f"{sanitize_filename(new_name)}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )

        self.tournament = Tournament(
            name=new_name,
            tournament_id=tournament_id,
            start_date=start_date,
            end_date=end_date,
            total_rounds=total_rounds,
            site=site,
            federation_code=fed_code,
            chief_arbiter=chief_arbiter,
            deputy_chief_arbiters=deputy_chief_arbiters,
            time_control=time_control_parsed,
            initial_board1_color_setting=initial_board1_color_setting,
            round_dates=round_dates,
            players=[],
            rounds=[],
            next_match_id=1,
            bye_value=0.5,
            launch_count=1,
            tournament_category=tournament_category,
        )

        # Inserimento giocatori
        existing_players = []
        while True:
            res = self.ui.input_players(
                self.players_db, existing_players, self.tournament, self.active_filename
            )
            if res is None:
                # Sospeso
                self._exit_program(0)
            self.tournament.players = res
            self.tournament.update_players_dict()

            if self.ui.confirm_player_list(self.tournament, self.players_db):
                break
            else:
                self.ui.show_message(
                    _("\nReindirizzamento all'inserimento giocatori...")
                )
                existing_players = self.tournament.players

        valore_bye_suggerito = 0.5
        valore_alternativo = 1.0

        self.ui.show_message("-" * 30)
        self.ui.show_message(_("Calcolo Valore del BYE secondo la regola FIDE"))
        self.ui.show_message(
            _("Il valore suggerito è: {val}").format(val=valore_bye_suggerito)
        )
        self.ui.show_message("-" * 30)
        if self.ui.confirm(
            _("Accetti il valore suggerito? (No = usa {alt_val})").format(
                alt_val=valore_alternativo
            )
        ):
            self.tournament.bye_value = valore_bye_suggerito
        else:
            self.tournament.bye_value = valore_alternativo

        self.ui.show_message(
            _("Valore del BYE impostato a: {val}").format(val=self.tournament.bye_value)
        )

        min_req = self.tournament.total_rounds + 1
        if len(self.tournament.players) < min_req:
            self.ui.show_error(
                _(
                    "Numero insufficiente di giocatori ({num_players}) per {num_rounds} turni. Torneo annullato."
                ).format(
                    num_players=len(self.tournament.players),
                    num_rounds=self.tournament.total_rounds,
                )
            )
            self._exit_program(0)

        self.tournament.current_round = 1
        self.tournament.rounds = []
        self.tournament.next_match_id = 1

        self.ui.show_message(_("\nGenerazione abbinamenti per il Turno 1..."))
        # Per la generazione passiamo il dizionario temporaneo del torneo per compatibilità con il vecchio motore
        # In seguito lo modificheremo in Fase 4 per accettare direttamente il modello dati.
        torneo_dict = self.tournament.to_dict()
        matches_r1_raw = generate_pairings_for_round(torneo_dict)
        if matches_r1_raw is None:
            self.ui.show_error(
                _(
                    "ERRORE CRITICO: Fallimento generazione abbinamenti Turno 1. Torneo non avviato."
                )
            )
            self._exit_program(1)

        matches_r1 = [Match.from_dict(m) for m in matches_r1_raw]
        self.ui.play_sound("nuovo_turno", self.tournament)
        self.ui.show_message(
            _("Registrazione risultati automatici per il Turno 1 (BYE)...")
        )

        for m in matches_r1:
            if m.result == "BYE":
                bye_player = self.tournament.players_dict.get(m.white_player_id)
                if bye_player:
                    bye_player.points = self.tournament.bye_value
                    bye_player.results_history.append(
                        ResultEntry(
                            round=1,
                            opponent_id="BYE_PLAYER_ID",
                            color=None,
                            result="BYE",
                            score=self.tournament.bye_value,
                        )
                    )
                    # Aggiorna contatori
                    bye_player.received_bye_count += 1
                    bye_player.received_bye_in_round.append(1)
                    self.ui.show_message(
                        _(
                            " > Giocatore {name} (ID: {id}) ha ricevuto un BYE. Punti e storico aggiornati."
                        ).format(name=bye_player.first_name, id=bye_player.id)
                    )

        self.tournament.rounds.append(Round(round=1, matches=matches_r1))

        # Percorso di salvataggio
        default_path = os.path.abspath(".")
        if not self.ui.confirm(
            _("Vuoi che i dati vengano salvati in {}?").format(default_path)
        ):
            while True:
                custom_path = self.ui.input_text(
                    _("Inserisci il percorso di salvataggio desiderato")
                ).strip()
                if not custom_path:
                    self.ui.show_message(_("Il percorso non può essere vuoto."))
                    continue
                try:
                    if not os.path.exists(custom_path):
                        os.makedirs(custom_path, exist_ok=True)
                    test_file = os.path.join(custom_path, ".tornello_test")
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    # Aggiorniamo la destinazione
                    sanitized_name = sanitize_filename(self.tournament.name)
                    self.active_filename = os.path.join(
                        custom_path, f"Tornello - {sanitized_name}.json"
                    )
                    # Rimuoviamo il vecchio se presente
                    break
                except Exception as e:
                    self.ui.show_error(
                        _("Percorso non valido o non scrivibile: {}").format(e)
                    )

        self._save_state()
        self.ui.show_message(
            _("\nTorneo '{name}' creato e Turno 1 generato. File: '{filename}'").format(
                name=self.tournament.name, filename=self.active_filename
            )
        )

    def _save_state(self) -> None:
        if self.tournament and self.active_filename:
            dict_to_save = self.tournament.to_dict()
            save_tournament(dict_to_save)
            save_current_tournament_round_file(dict_to_save)
            save_standings_text(dict_to_save, final=False)

    def _main_loop(self) -> None:
        self.ui.show_message(
            _("\n--- Torneo Attivo: {name} ---").format(name=self.tournament.name)
        )
        self.ui.show_message(
            _("Copyright 2026, dedicato all'ASCId e al gruppo Scacchierando.")
        )

        try:
            while True:
                curr_round = self.tournament.current_round
                tot_rounds = self.tournament.total_rounds

                if curr_round > tot_rounds:
                    self.ui.show_message(
                        _("\nIl torneo '{name}' si è concluso.").format(
                            name=self.tournament.name
                        )
                    )
                    break

                self.ui.show_message(
                    _("\n--- Gestione Turno {round_num} ---").format(
                        round_num=curr_round
                    )
                )
                self.ui.display_tournament_status(self.tournament)

                round_data = next(
                    (r for r in self.tournament.rounds if r.round == curr_round), None
                )
                if not round_data:
                    self.ui.show_error(
                        _("ERRORE CRITICO: Dati turno {round_num} non trovati!").format(
                            round_num=curr_round
                        )
                    )
                    break

                round_completed = (
                    all(
                        m.result is not None or m.black_player_id is None
                        for m in round_data.matches
                    )
                    if round_data.matches
                    else False
                )

                if not round_completed:
                    modifications = self.ui.update_match_results(self.tournament)
                    self.ui.show_message(
                        _("\nSessione di inserimento/modifica risultati terminata.")
                    )
                    if modifications:
                        self.ui.show_message(_("Salvataggio modifiche al torneo..."))
                        self._save_state()

                    if not self.ui.confirm(_("Vuoi continuare?")):
                        self.ui.show_message(
                            _("Salvataggio finale prima dell'uscita...")
                        )
                        self._save_state()
                        break
                else:
                    self.ui.show_message(
                        _("\nTurno {round_num} completato.").format(
                            round_num=curr_round
                        )
                    )
                    self.ui.play_sound("conclusione_turno", self.tournament)

                    dict_for_reports = self.tournament.to_dict()
                    append_completed_round_to_history_file(dict_for_reports, curr_round)
                    save_standings_text(dict_for_reports, final=False)

                    if curr_round == tot_rounds:
                        self.ui.show_message(
                            _(
                                "\nUltimo turno completato. Avvio finalizzazione torneo..."
                            )
                        )
                        if self._finalize_tournament():
                            self.ui.show_message(
                                _(
                                    "\n--- Torneo Concluso e Finalizzato Correttamente ---"
                                )
                            )
                            self.tournament = None
                            self.active_filename = None
                        else:
                            self.ui.show_error(
                                _(
                                    "\n--- ERRORE durante la Finalizzazione del Torneo ---"
                                )
                            )
                            self._save_state()
                        break
                    else:
                        next_round = curr_round + 1
                        if self.ui.confirm(
                            _(
                                "\nVuoi procedere e generare gli abbinamenti per il Turno {round_num}?"
                            ).format(round_num=next_round)
                        ):
                            self.tournament.current_round = next_round
                            self.ui.show_message(
                                _(
                                    "Generazione abbinamenti per il Turno {round_num}..."
                                ).format(round_num=next_round)
                            )

                            torneo_dict = self.tournament.to_dict()
                            next_matches_raw = generate_pairings_for_round(torneo_dict)

                            if next_matches_raw is None:
                                user_action = handle_bbpairings_failure(
                                    torneo_dict,
                                    next_round,
                                    "Errore durante la generazione.",
                                )
                                if user_action == "time_machine":
                                    self.tournament.current_round = curr_round
                                    torneo_dict = self.tournament.to_dict()
                                    if time_machine_torneo(torneo_dict):
                                        self.tournament = Tournament.from_dict(
                                            torneo_dict
                                        )
                                        self._save_state()
                                    else:
                                        self.ui.show_message(
                                            _(
                                                "Time Machine annullata o fallita. Uscita per sicurezza."
                                            )
                                        )
                                        break
                                    continue
                                elif user_action == "terminate":
                                    self.tournament.current_round = curr_round
                                    self._save_state()
                                    break

                            next_matches = [
                                Match.from_dict(m) for m in next_matches_raw
                            ]
                            self.ui.play_sound("nuovo_turno", self.tournament)
                            self.ui.show_message(
                                _(
                                    "Registrazione risultati automatici per il Turno {round_num} (BYE)..."
                                ).format(round_num=next_round)
                            )

                            for m in next_matches:
                                if m.result == "BYE":
                                    bye_player = self.tournament.players_dict.get(
                                        m.white_player_id
                                    )
                                    if bye_player:
                                        bye_player.points += self.tournament.bye_value
                                        bye_player.results_history.append(
                                            ResultEntry(
                                                round=next_round,
                                                opponent_id="BYE_PLAYER_ID",
                                                color=None,
                                                result="BYE",
                                                score=self.tournament.bye_value,
                                            )
                                        )
                                        bye_player.received_bye_count += 1
                                        bye_player.received_bye_in_round.append(
                                            next_round
                                        )
                                        self.ui.show_message(
                                            _(
                                                " > Giocatore {name} (ID: {id}) ha ricevuto un BYE. Punti e storico aggiornati."
                                            ).format(
                                                name=bye_player.first_name,
                                                id=bye_player.id,
                                            )
                                        )

                            self.tournament.rounds.append(
                                Round(round=next_round, matches=next_matches)
                            )
                            self._save_state()
                            self.ui.show_message(
                                _("Turno {round_num} generato e salvato.").format(
                                    round_num=next_round
                                )
                            )
                        else:
                            self.ui.show_message(
                                _(
                                    "Generazione prossimo turno annullata. Salvataggio stato attuale."
                                )
                            )
                            self._save_state()
                            break

        except KeyboardInterrupt:
            self.ui.show_message(_("\nOperazione interrotta dall'utente."))
            if self.tournament:
                self._save_state()
            self._exit_program(0)
        except Exception as e:
            self.ui.show_error(
                _("\nERRORE CRITICO NON GESTITO nel flusso principale: {error}").format(
                    error=e
                )
            )
            import traceback

            traceback.print_exc()
            if self.tournament:
                self._save_state()
            self._exit_program(1)

    def _finalize_tournament(self) -> bool:
        if not self.tournament:
            return False

        # Creazione backup
        self.ui.show_message(
            _("Creazione backup di sicurezza prima dell'archiviazione...")
        )
        backup_db_ok = create_backup(PLAYER_DB_FILE, "pre_finalize_db")
        backup_torneo_ok = True
        if self.active_filename and os.path.exists(self.active_filename):
            backup_torneo_ok = create_backup(
                self.active_filename, "pre_finalize_torneo"
            )

        if not backup_db_ok or not backup_torneo_ok:
            self.ui.show_message(
                _(
                    "ATTENZIONE: Fallita la creazione di uno o più file di backup. Procedo ugualmente..."
                )
            )

        self.tournament.update_players_dict()
        if not self.tournament.players:
            self.ui.show_error(
                _("Nessun giocatore nel torneo, impossibile finalizzare.")
            )
            return False

        # Fase 1: Determina K-Factor e conta partite
        self.ui.show_message(_("Accesso al DB e calcolo K-Factor e partite giocate..."))
        for p in self.tournament.players:
            if p.withdrawn:
                p.k_factor = None
                p.games_this_tournament = 0
                continue
            player_db_data = self.players_db.get(p.id)
            if not player_db_data:
                p.k_factor = DEFAULT_K_FACTOR
            else:
                p.k_factor = get_k_factor(player_db_data, self.tournament.start_date)

            games_count = 0
            for r in p.results_history:
                if (
                    r.opponent_id
                    and r.opponent_id != "BYE_PLAYER_ID"
                    and r.score is not None
                ):
                    games_count += 1
            p.games_this_tournament = games_count

        # Fase 2: Calcola spareggi
        self.ui.show_message(
            _("Ricalcolo finale Buchholz, ARO, Performance Rating, Variazione Elo...")
        )
        # Riconvertiamo a dizionario temporaneamente per le vecchie librerie pure di calcolo
        torneo_dict = self.tournament.to_dict()
        torneo_dict["players_dict"] = {
            p.id: p.to_dict() for p in self.tournament.players
        }

        for p in self.tournament.players:
            if p.withdrawn:
                p.buchholz = 0.0
                p.buchholz_cut1 = None
                p.aro = None
                p.performance_rating = None
                p.elo_change = None
                continue

            p.buchholz = compute_buchholz(p.id, torneo_dict)
            p.buchholz_cut1 = compute_buchholz_cut1(p.id, torneo_dict)
            p.aro = compute_aro(p.id, torneo_dict)
            p.performance_rating = calculate_performance_rating(
                p.to_dict(), torneo_dict["players_dict"]
            )
            p.elo_change = calculate_elo_change(
                p.to_dict(), torneo_dict["players_dict"]
            )

        # Fase 3: Ordinamento dinamico basato sui criteri di spareggio configurati
        self.ui.show_message(_("Ordinamento classifica finale..."))

        # Leggi i criteri di spareggio dal torneo con retrocompatibilità
        raw_tiebreaks = torneo_dict.get("tiebreaks", None)
        if raw_tiebreaks is None:
            tiebreak_entries = get_default_tiebreaks()
        elif raw_tiebreaks and isinstance(raw_tiebreaks[0], str):
            tiebreak_entries = migrate_old_tiebreaks(raw_tiebreaks)
        else:
            tiebreak_entries = raw_tiebreaks

        def sort_key_final(player: Player):
            points = float(player.points)
            status_val = 0 if player.withdrawn else 1
            sort_tuple = [-points, -status_val]

            # Applica dinamicamente ogni criterio di spareggio configurato
            for entry in tiebreak_entries:
                if isinstance(entry, dict):
                    key = entry.get("key", "")
                    modifiers = entry.get("modifiers", {})
                else:
                    key = str(entry)
                    modifiers = {}
                val = compute_tiebreak_value(player.id, torneo_dict, key, modifiers)
                sort_tuple.append(-(float(val) if val is not None else 0.0))

            return tuple(sort_tuple)

        players_sorted = sorted(self.tournament.players, key=sort_key_final)
        current_visual_rank = 0
        last_sort_key = None
        for i, p_item in enumerate(players_sorted):
            if p_item.withdrawn:
                p_item.final_rank = None  # o 'RIT'
                continue
            curr_sort_key = sort_key_final(p_item)[1:]
            if curr_sort_key != last_sort_key:
                current_visual_rank = i + 1
            p_item.final_rank = current_visual_rank
            last_sort_key = curr_sort_key

        self.tournament.players = players_sorted
        self.tournament.update_players_dict()

        # Update players database
        # ... logic to save to players_db
        from db_players import save_players_db

        # finalizza database
        for p in self.tournament.players:
            if p.withdrawn or p.final_rank is None:
                continue
            if p.id in self.players_db:
                local_p = self.players_db[p.id]
                category_lower = self.tournament.tournament_category.lower()
                change = p.elo_change if p.elo_change is not None else 0.0

                if category_lower == "blitz":
                    old_elo = local_p.get("elo_blitz", DEFAULT_ELO) or DEFAULT_ELO
                    local_p["elo_blitz"] = max(100.0, old_elo + change)
                elif category_lower == "rapid":
                    old_elo = local_p.get("elo_rapid", DEFAULT_ELO) or DEFAULT_ELO
                    local_p["elo_rapid"] = max(100.0, old_elo + change)
                else:
                    old_elo = local_p.get("current_elo", DEFAULT_ELO) or DEFAULT_ELO
                    local_p["current_elo"] = max(100.0, old_elo + change)

                local_p["games_played"] = (
                    local_p.get("games_played", 0) + p.games_this_tournament
                )
        save_players_db(self.players_db)

        # Archiviazione
        # Richiama la finalizzazione/archiviazione dei report
        # Per compatibilità, creiamo una versione temporanea dict e richiamiamo ui.finalize_tournament
        # o lo facciamo direttamente noi. La finalizzazione sposta i file.
        # Facciamolo tramite ui per non duplicare i percorsi di spostamento
        from ui import finalize_tournament

        return finalize_tournament(
            self.tournament.to_dict(), self.players_db, self.active_filename
        )

    def _exit_program(self, code: int = 0) -> None:
        self.ui.play_sound("chiusura", self.tournament, sync=True)
        import sys

        sys.exit(code)
