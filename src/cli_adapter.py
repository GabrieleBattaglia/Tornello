from typing import List, Optional

from controller import UIAdapter
from models import Tournament, Player, Round
from utils import enter_escape, play_sound
import ui

class CLIAdapter(UIAdapter):
    def show_message(self, message: str) -> None:
        print(message)

    def show_error(self, message: str) -> None:
        print(f"\n*** {message} ***")

    def confirm(self, prompt: str, default: bool = True) -> bool:
        if default:
            full_prompt = f"{prompt}" + _(" (INVIO per Sì | ESCAPE per No): ")
        else:
            full_prompt = f"{prompt}" + _(" (ESCAPE per No | INVIO per Sì): ")
        return enter_escape(full_prompt)

    def input_text(self, prompt: str, default: str = "") -> str:
        if default:
            val = input(f"{prompt} [{default}]: ").strip()
            return val if val else default
        return input(f"{prompt}: ").strip()

    def input_int(self, prompt: str, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
        while True:
            val_str = self.input_text(prompt)
            if not val_str:
                self.show_error(_("Il valore non può essere vuoto."))
                continue
            try:
                val = int(val_str)
                if min_val is not None and val < min_val:
                    self.show_error(_("Il valore deve essere almeno {min_val}.").format(min_val=min_val))
                    continue
                if max_val is not None and val > max_val:
                    self.show_error(_("Il valore non può superare {max_val}.").format(max_val=max_val))
                    continue
                return val
            except ValueError:
                self.show_error(_("Inserisci un numero intero valido."))

    def select_option(self, prompt: str, options: List[str]) -> int:
        for idx, option in enumerate(options):
            print(f" {idx + 1}. {option}")
        while True:
            choice_str = self.input_text(f"{prompt} (1-{len(options)})")
            if choice_str.isdigit():
                choice = int(choice_str)
                if 1 <= choice <= len(options):
                    return choice - 1
            self.show_error(_("Scelta non valida."))

    def input_date(self, prompt: str, default: str) -> str:
        return self.input_text(prompt, default)

    def input_players(self, players_db: dict, existing_players: List[Player], tournament: Tournament, tournament_filename: Optional[str]) -> Optional[List[Player]]:
        # Convert List[Player] to List[dict] for compatibility
        raw_existing = [p.to_dict() for p in existing_players]
        raw_torneo = tournament.to_dict()
        
        raw_res = ui.input_players(
            players_db=players_db,
            existing_players=raw_existing,
            torneo_obj=raw_torneo,
            torneo_filename=tournament_filename
        )
        if raw_res is None:
            return None
        return [Player.from_dict(p) for p in raw_res]

    def confirm_player_list(self, tournament: Tournament, players_db: dict) -> bool:
        torneo_dict = tournament.to_dict()
        # Ensure players_dict is populated in the dict for ui compatibility
        torneo_dict["players_dict"] = {p.id: p.to_dict() for p in tournament.players}
        
        res = ui._conferma_lista_giocatori_torneo(torneo_dict, players_db)
        if res:
            # Sync back players list
            tournament.players = [Player.from_dict(p) for p in torneo_dict["players"]]
            tournament.update_players_dict()
        return res

    def update_match_results(self, tournament: Tournament) -> bool:
        torneo_dict = tournament.to_dict()
        torneo_dict["players_dict"] = {p.id: p.to_dict() for p in tournament.players}
        
        res = ui.update_match_result(torneo_dict)
        if res:
            # Sync back round/match results and withdrawn players
            tournament.players = [Player.from_dict(p) for p in torneo_dict["players"]]
            tournament.rounds = [Round.from_dict(r) for r in torneo_dict.get("rounds", [])]
            tournament.current_round = torneo_dict.get("current_round", tournament.current_round)
            tournament.next_match_id = torneo_dict.get("next_match_id", tournament.next_match_id)
            tournament.update_players_dict()
        return res

    def play_sound(self, sound_name: str, tournament: Optional[Tournament] = None, sync: bool = False) -> None:
        torneo_dict = tournament.to_dict() if tournament else None
        play_sound(sound_name, torneo_dict, sync=sync)

    def display_tournament_status(self, tournament: Tournament) -> None:
        from reports import display_status
        display_status(tournament.to_dict())
