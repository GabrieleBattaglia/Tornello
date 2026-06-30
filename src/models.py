from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set

@dataclass
class ResultEntry:
    round: int
    opponent_id: str
    color: Optional[str]  # "white", "black", or None (for BYE)
    result: str           # "1-0", "0-1", "1/2-1/2", etc.
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round": self.round,
            "opponent_id": self.opponent_id,
            "color": self.color,
            "result": self.result,
            "score": self.score
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ResultEntry':
        return cls(
            round=d.get("round", 0),
            opponent_id=d.get("opponent_id", ""),
            color=d.get("color"),
            result=d.get("result", ""),
            score=float(d.get("score", 0.0))
        )

@dataclass
class Player:
    id: str
    first_name: str
    last_name: str
    initial_elo: float
    fide_title: str = ""
    sex: str = "m"
    federation: str = "ITA"
    fide_id_num_str: str = "0"
    birth_date: str = "1900-01-01"
    points: float = 0.0
    results_history: List[ResultEntry] = field(default_factory=list)
    opponents: Set[str] = field(default_factory=set)
    white_games: int = 0
    black_games: int = 0
    last_color: Optional[str] = None
    consecutive_white: int = 0
    consecutive_black: int = 0
    received_bye_count: int = 0
    received_bye_in_round: List[int] = field(default_factory=list)
    buchholz: float = 0.0
    buchholz_cut1: Optional[float] = None
    performance_rating: Optional[float] = None
    elo_change: Optional[float] = None
    k_factor: Optional[int] = None
    games_this_tournament: int = 0
    downfloat_count: int = 0
    final_rank: Optional[int] = None
    withdrawn: bool = False
    display_rank: Optional[int] = None
    
    # Issue #14: Fallback Elo and complete FIDE fields
    elo_club: Optional[float] = None
    elo_rapid: Optional[float] = None
    elo_blitz: Optional[float] = None
    fide_k_factor: Optional[int] = None
    fide_rapid_k: Optional[int] = None
    fide_blitz_k: Optional[int] = None
    fide_standard_games: int = 0
    fide_rapid_games: int = 0
    fide_blitz_games: int = 0
    w_title: str = ""
    o_title: str = ""
    foa_title: str = ""
    flag: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "initial_elo": self.initial_elo,
            "fide_title": self.fide_title,
            "sex": self.sex,
            "federation": self.federation,
            "fide_id_num_str": self.fide_id_num_str,
            "birth_date": self.birth_date,
            "points": self.points,
            "results_history": [r.to_dict() for r in self.results_history],
            "opponents": list(self.opponents),
            "white_games": self.white_games,
            "black_games": self.black_games,
            "last_color": self.last_color,
            "consecutive_white": self.consecutive_white,
            "consecutive_black": self.consecutive_black,
            "received_bye_count": self.received_bye_count,
            "received_bye_in_round": self.received_bye_in_round,
            "buchholz": self.buchholz,
            "buchholz_cut1": self.buchholz_cut1,
            "performance_rating": self.performance_rating,
            "elo_change": self.elo_change,
            "k_factor": self.k_factor,
            "games_this_tournament": self.games_this_tournament,
            "downfloat_count": self.downfloat_count,
            "final_rank": self.final_rank,
            "withdrawn": self.withdrawn,
            "display_rank": self.display_rank,
            "elo_club": self.elo_club,
            "elo_rapid": self.elo_rapid,
            "elo_blitz": self.elo_blitz,
            "fide_k_factor": self.fide_k_factor,
            "fide_rapid_k": self.fide_rapid_k,
            "fide_blitz_k": self.fide_blitz_k,
            "fide_standard_games": self.fide_standard_games,
            "fide_rapid_games": self.fide_rapid_games,
            "fide_blitz_games": self.fide_blitz_games,
            "w_title": self.w_title,
            "o_title": self.o_title,
            "foa_title": self.foa_title,
            "flag": self.flag
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Player':
        history_list = d.get("results_history", [])
        results_history = [ResultEntry.from_dict(h) for h in history_list]
        opponents = set(d.get("opponents", []))
        
        return cls(
            id=d.get("id", ""),
            first_name=d.get("first_name", ""),
            last_name=d.get("last_name", ""),
            initial_elo=float(d.get("initial_elo", 1399.0)),
            fide_title=d.get("fide_title", ""),
            sex=d.get("sex", "m"),
            federation=d.get("federation", "ITA"),
            fide_id_num_str=d.get("fide_id_num_str", "0"),
            birth_date=d.get("birth_date", "1900-01-01"),
            points=float(d.get("points", 0.0)),
            results_history=results_history,
            opponents=opponents,
            white_games=int(d.get("white_games", 0)),
            black_games=int(d.get("black_games", 0)),
            last_color=d.get("last_color"),
            consecutive_white=int(d.get("consecutive_white", 0)),
            consecutive_black=int(d.get("consecutive_black", 0)),
            received_bye_count=int(d.get("received_bye_count", 0)),
            received_bye_in_round=list(d.get("received_bye_in_round", [])),
            buchholz=float(d.get("buchholz", 0.0)),
            buchholz_cut1=d.get("buchholz_cut1"),
            performance_rating=d.get("performance_rating"),
            elo_change=d.get("elo_change"),
            k_factor=d.get("k_factor"),
            games_this_tournament=int(d.get("games_this_tournament", 0)),
            downfloat_count=int(d.get("downfloat_count", 0)),
            final_rank=d.get("final_rank"),
            withdrawn=bool(d.get("withdrawn", False)),
            display_rank=d.get("display_rank"),
            elo_club=d.get("elo_club"),
            elo_rapid=d.get("elo_rapid"),
            elo_blitz=d.get("elo_blitz"),
            fide_k_factor=d.get("fide_k_factor"),
            fide_rapid_k=d.get("fide_rapid_k"),
            fide_blitz_k=d.get("fide_blitz_k"),
            fide_standard_games=int(d.get("fide_standard_games", 0)),
            fide_rapid_games=int(d.get("fide_rapid_games", 0)),
            fide_blitz_games=int(d.get("fide_blitz_games", 0)),
            w_title=d.get("w_title", ""),
            o_title=d.get("o_title", ""),
            foa_title=d.get("foa_title", ""),
            flag=d.get("flag", "")
        )

@dataclass
class Match:
    id: int
    round: int
    white_player_id: str
    black_player_id: Optional[str]  # None if BYE
    result: Optional[str] = None    # "1-0", "0-1", "1/2-1/2", "1-F", "F-1", "0-0F", "BYE", or None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "round": self.round,
            "white_player_id": self.white_player_id,
            "black_player_id": self.black_player_id,
            "result": self.result
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Match':
        return cls(
            id=d.get("id", 0),
            round=d.get("round", 0),
            white_player_id=d.get("white_player_id", ""),
            black_player_id=d.get("black_player_id"),
            result=d.get("result")
        )

@dataclass
class RoundDate:
    round: int
    start_date: str
    end_date: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round": self.round,
            "start_date": self.start_date,
            "end_date": self.end_date
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'RoundDate':
        return cls(
            round=d.get("round", 0),
            start_date=d.get("start_date", ""),
            end_date=d.get("end_date", "")
        )

@dataclass
class Round:
    round: int
    matches: List[Match] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round": self.round,
            "matches": [m.to_dict() for m in self.matches]
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Round':
        matches_list = d.get("matches", [])
        matches = [Match.from_dict(m) for m in matches_list]
        return cls(
            round=d.get("round", 0),
            matches=matches
        )

@dataclass
class Tournament:
    name: str
    tournament_id: str
    start_date: str
    end_date: str
    total_rounds: int
    site: str = "Online"
    federation_code: str = "ITA"
    chief_arbiter: str = "N/D"
    deputy_chief_arbiters: str = ""
    time_control: Any = "Standard"  # Issue #12: string or dict
    initial_board1_color_setting: str = "white1"
    round_dates: List[RoundDate] = field(default_factory=list)
    players: List[Player] = field(default_factory=list)
    rounds: List[Round] = field(default_factory=list)
    next_match_id: int = 1
    bye_value: float = 1.0
    launch_count: int = 0
    schema_version: int = 1
    tournament_category: str = "standard"  # Issue #13

    # players_dict is a cache of player objects, not saved directly to file
    players_dict: Dict[str, Player] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        self.update_players_dict()

    def update_players_dict(self):
        self.players_dict = {p.id: p for p in self.players}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "launch_count": self.launch_count,
            "name": self.name,
            "tournament_id": self.tournament_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_rounds": self.total_rounds,
            "site": self.site,
            "federation_code": self.federation_code,
            "chief_arbiter": self.chief_arbiter,
            "deputy_chief_arbiters": self.deputy_chief_arbiters,
            "time_control": self.time_control,
            "initial_board1_color_setting": self.initial_board1_color_setting,
            "round_dates": [rd.to_dict() for rd in self.round_dates],
            "players": [p.to_dict() for p in self.players],
            "rounds": [r.to_dict() for r in self.rounds],
            "next_match_id": self.next_match_id,
            "bye_value": self.bye_value,
            "schema_version": self.schema_version,
            "tournament_category": self.tournament_category
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Tournament':
        rd_list = d.get("round_dates", [])
        round_dates = [RoundDate.from_dict(rd) for rd in rd_list]

        p_list = d.get("players", [])
        players = [Player.from_dict(p) for p in p_list]

        r_list = d.get("rounds", [])
        rounds = [Round.from_dict(r) for r in r_list]

        return cls(
            name=d.get("name", "Torneo Sconosciuto"),
            tournament_id=d.get("tournament_id", ""),
            start_date=d.get("start_date", ""),
            end_date=d.get("end_date", ""),
            total_rounds=int(d.get("total_rounds", 0)),
            site=d.get("site", "Online"),
            federation_code=d.get("federation_code", "ITA"),
            chief_arbiter=d.get("chief_arbiter", "N/D"),
            deputy_chief_arbiters=d.get("deputy_chief_arbiters", ""),
            time_control=d.get("time_control", "Standard"),
            initial_board1_color_setting=d.get("initial_board1_color_setting", "white1"),
            round_dates=round_dates,
            players=players,
            rounds=rounds,
            next_match_id=int(d.get("next_match_id", 1)),
            bye_value=float(d.get("bye_value", 1.0)),
            launch_count=int(d.get("launch_count", 0)),
            schema_version=int(d.get("schema_version", 1)),
            tournament_category=d.get("tournament_category", "standard")
        )
