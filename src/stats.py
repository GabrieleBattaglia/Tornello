import math
from datetime import datetime

from config import DATE_FORMAT_ISO, DEFAULT_ELO, DEFAULT_K_FACTOR
from dateutil.relativedelta import relativedelta
from utils import format_points, get_player_by_id


def is_forfeit_result(result_str):
    """
    Vero se il risultato indica una partita non giocata: 1-F, F-1 o 0-0F.
    I punti assegnati per forfait valgono in classifica ma non concorrono
    al calcolo della variazione Elo e della performance.
    """
    return "F" in str(result_str or "").upper()


# Tabella FIDE che converte la percentuale di punteggio nella differenza di
# performance. Esisteva in due copie, e la seconda, dentro _get_dp_map, si
# fermava a 0.89: il criterio di spareggio TPR, e di conseguenza APRO,
# ricadeva sul valore di ripiego piu' o meno 800 per quasi tutti i
# giocatori. Una copia sola, usata da entrambe le funzioni.
DP_FIDE = {
    1.0: 800,
    0.99: 677,
    0.98: 589,
    0.97: 538,
    0.96: 501,
    0.95: 470,
    0.94: 444,
    0.93: 422,
    0.92: 401,
    0.91: 383,
    0.90: 366,
    0.89: 351,
    0.88: 336,
    0.87: 322,
    0.86: 309,
    0.85: 296,
    0.84: 284,
    0.83: 273,
    0.82: 262,
    0.81: 251,
    0.80: 240,
    0.79: 230,
    0.78: 220,
    0.77: 211,
    0.76: 202,
    0.75: 193,
    0.74: 184,
    0.73: 175,
    0.72: 166,
    0.71: 158,
    0.70: 149,
    0.69: 141,
    0.68: 133,
    0.67: 125,
    0.66: 117,
    0.65: 110,
    0.64: 102,
    0.63: 95,
    0.62: 87,
    0.61: 80,
    0.60: 72,
    0.59: 65,
    0.58: 57,
    0.57: 50,
    0.56: 43,
    0.55: 36,
    0.54: 29,
    0.53: 21,
    0.52: 14,
    0.51: 7,
    0.50: 0,
    0.49: -7,
    0.48: -14,
    0.47: -21,
    0.46: -29,
    0.45: -36,
    0.44: -43,
    0.43: -50,
    0.42: -57,
    0.41: -65,
    0.40: -72,
    0.39: -80,
    0.38: -87,
    0.37: -95,
    0.36: -102,
    0.35: -110,
    0.34: -117,
    0.33: -125,
    0.32: -133,
    0.31: -141,
    0.30: -149,
    0.29: -158,
    0.28: -166,
    0.27: -175,
    0.26: -184,
    0.25: -193,
    0.24: -202,
    0.23: -211,
    0.22: -220,
    0.21: -230,
    0.20: -240,
    0.19: -251,
    0.18: -262,
    0.17: -273,
    0.16: -284,
    0.15: -296,
    0.14: -309,
    0.13: -322,
    0.12: -336,
    0.11: -351,
    0.10: -366,
    0.09: -383,
    0.08: -401,
    0.07: -422,
    0.06: -444,
    0.05: -470,
    0.04: -501,
    0.03: -538,
    0.02: -589,
    0.01: -677,
    0.0: -800,
}


def get_k_factor(player_data_dict, tournament_start_date_str):
    """
    Determina il K-Factor FIDE. Ora dà priorità al valore ufficiale FIDE se presente nel DB,
    altrimenti lo calcola basandosi sulle regole.
    """
    # --- NUOVA LOGICA DI PRIORITÀ ---
    # Se abbiamo un K-Factor ufficiale dalla FIDE, usiamo quello e basta.
    fide_k = player_data_dict.get("fide_k_factor")
    if fide_k is not None and fide_k in [10, 20, 40]:  # I valori K validi
        return fide_k
    # --- FINE NUOVA LOGICA ---

    # Se non c'è un K-Factor FIDE, procedi con la logica di calcolo esistente...
    if not player_data_dict:
        return DEFAULT_K_FACTOR
    try:
        elo = float(player_data_dict.get("current_elo", DEFAULT_ELO))
    except (ValueError, TypeError):
        elo = DEFAULT_ELO

    games_played = player_data_dict.get("games_played", 0)
    is_experienced = player_data_dict.get("experienced", False)
    birth_date_str = player_data_dict.get("birth_date")
    age = None

    if birth_date_str and tournament_start_date_str:
        try:
            birth_dt = datetime.strptime(birth_date_str, DATE_FORMAT_ISO)
            current_dt = datetime.strptime(tournament_start_date_str, DATE_FORMAT_ISO)
            age = relativedelta(current_dt, birth_dt).years
        except (ValueError, TypeError):
            pass

    if games_played < 30 and not is_experienced:
        return 40
    if age is not None and age < 18 and elo < 2300:
        return 40
    if elo < 2400:
        return 20
    return 10


def calculate_expected_score(player_elo, opponent_elo):
    """Calcola il punteggio atteso di un giocatore contro un avversario."""
    try:
        p_elo = float(player_elo)
        o_elo = float(opponent_elo)
        # Limita la differenza Elo a +/- 400 come da specifiche FIDE
        diff = max(-400, min(400, o_elo - p_elo))
        return 1 / (1 + 10 ** (diff / 400))
    except (ValueError, TypeError):
        print(
            _(
                "Warning: Elo non valido ({player_elo} o {opponent_elo}) nel calcolo atteso."
            ).format(player_elo=player_elo, opponent_elo=opponent_elo)
        )
        return 0.5  # Ritorna 0.5 in caso di Elo non validi


def calculate_elo_change(player, tournament_players_dict):
    """Calcola la variazione Elo per un giocatore basata sulle partite del torneo."""
    if not player or "initial_elo" not in player or "results_history" not in player:
        print(
            _(
                "Warning: Dati giocatore incompleti per calcolo Elo ({player_id})."
            ).format(player_id=player.get("id", _("ID Mancante")))
        )
        return 0

    # --- USA IL K-FACTOR SPECIFICO DEL GIOCATORE ---
    # Questo K viene determinato in finalize_tournament e salvato in p['k_factor']
    # Usiamo DEFAULT_K_FACTOR come fallback se non trovato (non dovrebbe succedere)
    k = player.get("k_factor")
    if k is None:
        k = DEFAULT_K_FACTOR
    # --- FINE MODIFICA K-FACTOR ---
    total_expected_score = 0.0
    actual_score = 0.0
    games_played_count = 0  # Rinomina variabile locale per chiarezza
    initial_elo = player["initial_elo"]
    try:
        initial_elo = float(initial_elo)
    except (ValueError, TypeError):
        print(
            _(
                "Warning: Elo iniziale non valido ({elo}) per giocatore {player_id}. Usato {default_elo}]."
            ).format(
                elo=initial_elo,
                player_id=player.get("id", _("ID Mancante")),
                default_elo=DEFAULT_ELO,
            )
        )
        initial_elo = DEFAULT_ELO

    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        score = result_entry.get("score")

        # Salta BYE e partite senza avversario o punteggio valido
        if opponent_id is None or opponent_id == "BYE_PLAYER_ID" or score is None:
            continue

        # Salta le partite non giocate (1-F, F-1, 0-0F): il punto assegnato per
        # forfait vale in classifica ma non concorre alla variazione Elo.
        if is_forfeit_result(result_entry.get("result")):
            continue

        opponent = tournament_players_dict.get(opponent_id)
        if not opponent or "initial_elo" not in opponent:
            print(
                _(
                    "Warning: Avversario {opponent_id} non trovato o Elo mancante per calcolo Elo."
                ).format(opponent_id=opponent_id)
            )
            continue

        try:
            opponent_elo = float(opponent["initial_elo"])
            score = float(score)
        except (ValueError, TypeError):
            print(
                _(
                    "Warning: Elo avversario ({}) o score ({}) non validi per partita contro {}."
                ).format(opponent.get("initial_elo"), score, opponent_id)
            )
            continue

        expected_score = calculate_expected_score(initial_elo, opponent_elo)
        total_expected_score += expected_score
        actual_score += score
        games_played_count += 1  # Conta solo partite valide per Elo

    if games_played_count == 0:
        return 0

    # Calcolo variazione Elo grezza usando il K specifico
    elo_change_raw = k * (actual_score - total_expected_score)

    # Arrotondamento FIDE standard
    if elo_change_raw > 0:
        return math.floor(elo_change_raw + 0.5)
    else:
        return math.ceil(elo_change_raw - 0.5)


def calculate_performance_rating(player, tournament_players_dict):
    """Calcola la Performance Rating di un giocatore."""
    if not player or "initial_elo" not in player or "results_history" not in player:
        # Ritorna l'Elo iniziale se non ci sono dati sufficienti
        return player.get("initial_elo", DEFAULT_ELO)
    opponent_elos = []
    total_score = 0.0
    games_played_for_perf = 0
    try:
        initial_elo = float(player["initial_elo"])
    except (ValueError, TypeError):
        initial_elo = DEFAULT_ELO  # Fallback se Elo iniziale non valido
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        score = result_entry.get("score")
        # Salta BYE e partite senza avversario o punteggio
        if opponent_id is None or opponent_id == "BYE_PLAYER_ID" or score is None:
            continue
        # Salta le partite non giocate (1-F, F-1, 0-0F): il punto assegnato per
        # forfait vale in classifica ma non concorre alla performance.
        if is_forfeit_result(result_entry.get("result")):
            continue
        opponent = tournament_players_dict.get(opponent_id)
        if not opponent or "initial_elo" not in opponent:
            print(
                _(
                    "Warning: Avversario {opponent_id} non trovato o Elo mancante per calcolo Performance."
                ).format(opponent_id=opponent_id)
            )
            continue
        try:
            opponent_elo = float(opponent["initial_elo"])
            total_score += float(score)
            opponent_elos.append(opponent_elo)
            games_played_for_perf += 1
        except (ValueError, TypeError):
            print(
                _(
                    "Warning: Dati non validi (Elo avversario {elo}) o score ({score}) per partita vs {opponent_id} nel calcolo performance."
                ).format(
                    elo=opponent.get("initial_elo"),
                    score=score,
                    opponent_id=opponent_id,
                )
            )
            continue
    if games_played_for_perf == 0:
        # Se non ci sono state partite valide, ritorna l'Elo iniziale
        return round(initial_elo)
    # Calcola media Elo avversari
    avg_opponent_elo = sum(opponent_elos) / games_played_for_perf
    # Calcola percentuale punteggio
    score_percentage = total_score / games_played_for_perf
    dp_map = DP_FIDE
    # Arrotonda la percentuale al centesimo più vicino per il lookup
    lookup_p = round(score_percentage, 2)
    # Gestisce casi limite
    lookup_p = max(lookup_p, 0.0)
    lookup_p = min(lookup_p, 1.0)
    # Ottieni dp dalla mappa, con fallback a +/- 800 per sicurezza
    dp = dp_map.get(lookup_p, 800 if lookup_p > 0.5 else -800)
    # Calcola performance
    performance = avg_opponent_elo + dp
    # Ritorna la performance arrotondata all'intero
    return round(performance)


# Articolo 16 del regolamento FIDE sugli spareggi, in vigore dal 1 marzo 2026:
# trattamento dei turni non giocati negli spareggi che si basano sui risultati
# degli avversari, cioe' Buchholz, Sonneborn-Berger e le loro varianti.
# Fino alla versione 9.3.22 Tornello saltava del tutto quei turni, che e' la
# regola precedente al 2023 e produce classifiche non conformi.
BYE_ID = "BYE_PLAYER_ID"
# Le cinque categorie dell'articolo 16.2.
CAT_BYE_ABBINATORE = "bye_abbinatore"  # 16.2.1, bye assegnato dall'abbinatore
CAT_VITTORIA_FORFAIT = "vittoria_forfait"  # 16.2.2
CAT_BYE_RICHIESTO = "bye_richiesto"  # 16.2.3, seguito da almeno un turno giocato
CAT_SCONFITTA_FORFAIT = "sconfitta_forfait"  # 16.2.4
CAT_BYE_FINALE = "bye_finale"  # 16.2.5, seguito solo da turni non disponibili
# Turni non disponibili al gioco, i VUR dell'articolo 16.1.2.
CATEGORIE_VUR = frozenset({CAT_BYE_RICHIESTO, CAT_SCONFITTA_FORFAIT, CAT_BYE_FINALE})
CATEGORIE_FORFAIT = frozenset({CAT_VITTORIA_FORFAIT, CAT_SCONFITTA_FORFAIT})


def _players_dict(torneo):
    return torneo.get("players_dict") or {p["id"]: p for p in torneo.get("players", [])}


def _numero_float(valore, ripiego=0.0):
    try:
        return float(valore)
    except (ValueError, TypeError):
        return ripiego


def _turni_con_risultati(torneo):
    """Numeri dei turni in cui almeno una partita ha un risultato.
    Un turno appena generato non conta ancora per gli spareggi."""
    turni = set()
    for round_data in torneo.get("rounds", []):
        numero = round_data.get("round")
        if numero is None:
            continue
        for partita in round_data.get("matches", []):
            if partita.get("result"):
                turni.add(int(numero))
                break
    return sorted(turni)


def _ha_partita_in_attesa(torneo, player_id, numero_turno):
    """Vero se in quel turno il giocatore ha una partita ancora senza
    risultato: il turno e' in corso per lui, non un turno non giocato."""
    for round_data in torneo.get("rounds", []):
        if round_data.get("round") != numero_turno:
            continue
        for partita in round_data.get("matches", []):
            if player_id in (
                partita.get("white_player_id"),
                partita.get("black_player_id"),
            ):
                return not partita.get("result")
    return False


def categorie_turni_non_giocati(player_id, torneo, turni=None):
    """Classifica i turni non giocati dal giocatore secondo l'articolo 16.2.
    Restituisce un dizionario numero di turno, categoria."""
    giocatore = get_player_by_id(torneo, player_id)
    if not giocatore:
        return {}
    if turni is None:
        turni = _turni_con_risultati(torneo)
    ultimo_turno = int(torneo.get("total_rounds") or (turni[-1] if turni else 0))
    storico = {}
    for voce in giocatore.get("results_history", []):
        numero = voce.get("round")
        if numero is not None:
            storico[int(numero)] = voce

    categorie = {}
    for turno in turni:
        voce = storico.get(turno)
        if voce is None:
            # Nessuna traccia del turno: e' un bye a zero punti, che
            # l'articolo 16.1.1 equipara a un bye richiesto. E' il caso di
            # ogni turno successivo al ritiro di un giocatore.
            if _ha_partita_in_attesa(torneo, player_id, turno):
                continue
            categorie[turno] = CAT_BYE_RICHIESTO
            continue
        risultato = str(voce.get("result") or "").upper()
        if voce.get("opponent_id") == BYE_ID or risultato == "BYE":
            categorie[turno] = CAT_BYE_ABBINATORE
        elif "F" in risultato:
            punti = _numero_float(voce.get("score"))
            categorie[turno] = (
                CAT_VITTORIA_FORFAIT if punti > 0 else CAT_SCONFITTA_FORFAIT
            )

    # Un bye richiesto diventa della categoria 16.2.5 se e' nell'ultimo turno
    # del torneo o se dopo di esso ci sono soltanto altri turni non disponibili.
    for turno, categoria in list(categorie.items()):
        if categoria != CAT_BYE_RICHIESTO:
            continue
        successivi = [t for t in turni if t > turno]
        if (
            turno >= ultimo_turno
            or not successivi
            or all(categorie.get(t) in CATEGORIE_VUR for t in successivi)
        ):
            categorie[turno] = CAT_BYE_FINALE
    return categorie


def punteggio_aggiustato(player_id, torneo, turni=None):
    """Punteggio del giocatore come lo vedono gli spareggi dei suoi avversari,
    secondo l'articolo 16.3. Cambia solo per i turni della categoria 16.2.5,
    che vanno valutati come patte: e' il caso dei turni successivi a un ritiro."""
    giocatore = get_player_by_id(torneo, player_id)
    if not giocatore:
        return 0.0
    punteggio = _numero_float(giocatore.get("points"))
    categorie = categorie_turni_non_giocati(player_id, torneo, turni)
    for turno, categoria in categorie.items():
        if categoria != CAT_BYE_FINALE:
            continue
        voce_punti = 0.0
        for voce in giocatore.get("results_history", []):
            if voce.get("round") == turno:
                voce_punti = _numero_float(voce.get("score"))
                break
        punteggio += 0.5 - voce_punti
    return punteggio


def contributi_spareggio(player_id, torneo):
    """Contributi da usare per Buchholz, Sonneborn-Berger e varianti, uno per
    ogni turno, secondo gli articoli 16.3 e 16.4.
    Ogni contributo e' un dizionario con il turno, il punteggio dell'avversario
    reale o fittizio, i punti fatti dal giocatore in quel turno e l'indicazione
    se il turno era fra quelli non disponibili al gioco."""
    giocatore = get_player_by_id(torneo, player_id)
    if not giocatore:
        return []
    giocatori = _players_dict(torneo)
    turni = _turni_con_risultati(torneo)
    if not turni:
        return []
    categorie = categorie_turni_non_giocati(player_id, torneo, turni)
    punti_giocatore = _numero_float(giocatore.get("points"))
    # Articolo 16.4.2: il fittizio non puo' valere piu' di una patta per ogni
    # turno del torneo.
    tetto_patte = 0.5 * int(torneo.get("total_rounds") or len(turni))
    storico = {}
    for voce in giocatore.get("results_history", []):
        numero = voce.get("round")
        if numero is not None:
            storico[int(numero)] = voce

    contributi = []
    for turno in turni:
        voce = storico.get(turno)
        categoria = categorie.get(turno)
        punti_del_turno = _numero_float(voce.get("score")) if voce else 0.0
        if categoria is None:
            if not voce:
                continue
            avversario = giocatori.get(voce.get("opponent_id"))
            if not avversario:
                continue
            contributi.append(
                {
                    "turno": turno,
                    "punteggio": punteggio_aggiustato(
                        voce.get("opponent_id"), torneo, turni
                    ),
                    "punti": punti_del_turno,
                    "vur": False,
                    "elo": _numero_float(avversario.get("initial_elo"), DEFAULT_ELO),
                }
            )
            continue
        # Turno non giocato: l'articolo 16.4 lo valuta come una partita contro
        # un avversario fittizio che ha il punteggio del giocatore stesso.
        tetto = tetto_patte
        if categoria in CATEGORIE_FORFAIT and voce:
            avversario_previsto = voce.get("opponent_id")
            if avversario_previsto and avversario_previsto in giocatori:
                # Articolo 16.4.1: per i forfait il tetto e' il punteggio
                # aggiustato dell'avversario che era stato abbinato.
                tetto = punteggio_aggiustato(avversario_previsto, torneo, turni)
        contributi.append(
            {
                "turno": turno,
                "punteggio": min(punti_giocatore, tetto),
                "punti": punti_del_turno,
                "vur": categoria in CATEGORIE_VUR,
                "elo": None,
            }
        )
    return contributi


def _taglia_contributi(valori, quantita, vur):
    """Toglie i contributi meno significativi rispettando l'articolo 16.5:
    quando il giocatore ha turni non disponibili al gioco, il taglio deve
    colpire per primo il contributo piu' basso proveniente da quei turni."""
    elementi = list(zip(valori, vur, strict=False))
    for _ in range(quantita):
        if len(elementi) <= 1:
            break
        candidati = [e for e in elementi if e[1]]
        if candidati:
            da_togliere = min(candidati, key=lambda e: e[0])
        else:
            da_togliere = min(elementi, key=lambda e: e[0])
        elementi.remove(da_togliere)
    return elementi


def compute_buchholz(player_id, torneo):
    """Buchholz totale, articoli 8.1 e 16 del regolamento FIDE sugli spareggi.
    Somma i punteggi degli avversari; i turni non giocati dal giocatore
    contano come partite contro un avversario fittizio, e i turni non giocati
    degli avversari sono valutati secondo l'articolo 16.3."""
    contributi = contributi_spareggio(player_id, torneo)
    if not contributi:
        return 0.0
    return float(format_points(sum(c["punteggio"] for c in contributi)))


def compute_buchholz_cut1(player_id, torneo):
    """Buchholz Cut-1: toglie il contributo meno significativo, dando la
    precedenza a quello piu' basso fra i turni non disponibili al gioco,
    come vuole l'eccezione dell'articolo 16.5."""
    contributi = contributi_spareggio(player_id, torneo)
    if not contributi:
        return 0.0
    rimasti = _taglia_contributi(
        [c["punteggio"] for c in contributi], 1, [c["vur"] for c in contributi]
    )
    return float(format_points(sum(valore for valore, _vur in rimasti)))


def compute_aro(player_id, torneo):
    """Calcola l'Average Rating of Opponents (ARO) basato sull'Elo iniziale."""
    opponent_elos = []
    player = get_player_by_id(torneo, player_id)
    if not player:
        return None  # Non possiamo calcolare ARO
    players_dict = torneo.get(
        "players_dict", {p["id"]: p for p in torneo.get("players", [])}
    )
    opponent_ids_encountered = set()

    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        if (
            opponent_id
            and opponent_id != "BYE_PLAYER_ID"
            and opponent_id not in opponent_ids_encountered
        ):
            opponent = players_dict.get(opponent_id)
            if opponent and "initial_elo" in opponent:
                try:
                    opponent_elos.append(float(opponent["initial_elo"]))
                except (ValueError, TypeError):
                    print(
                        _(
                            "Warning: Elo iniziale non valido ({elo}) per avversario {opponent_id} in ARO di {player_id}."
                        ).format(
                            elo=opponent["initial_elo"],
                            opponent_id=opponent_id,
                            player_id=player_id,
                        )
                    )
                opponent_ids_encountered.add(opponent_id)
            # else: Giocatore non trovato o senza Elo iniziale, non includere in ARO

    if not opponent_elos:
        return None  # Nessun avversario valido trovato

    # Calcola la media e arrotonda all'intero
    aro = sum(opponent_elos) / len(opponent_elos)
    return round(aro)


def get_initial_elo_for_tournament(player_db_data: dict, category: str) -> float:
    """
    Risolve l'Elo iniziale di un giocatore per un torneo in base alla categoria.
    Gerarchia:
    - Blitz: elo_blitz -> current_elo -> elo_club -> DEFAULT_ELO (1399)
    - Rapid: elo_rapid -> current_elo -> elo_club -> DEFAULT_ELO (1399)
    - Standard: current_elo -> elo_club -> DEFAULT_ELO (1399)
    """
    category_lower = category.lower()

    # 1. Cerca elo specifico della cadenza
    elo = 0
    if category_lower == "blitz":
        elo = player_db_data.get("elo_blitz", 0) or player_db_data.get(
            "fide_elo_blitz", 0
        )
    elif category_lower == "rapid":
        elo = player_db_data.get("elo_rapid", 0) or player_db_data.get(
            "fide_elo_rapid", 0
        )

    # 2. Cerca Elo Standard (current_elo)
    if not elo:
        elo = player_db_data.get("current_elo", 0) or player_db_data.get("elo", 0)

    # 3. Cerca Elo Club
    if not elo:
        elo = player_db_data.get("elo_club", 0)

    # 4. Fallback al default
    if not elo:
        elo = DEFAULT_ELO

    return float(elo)


def parse_time_control(time_control_str: str) -> dict | None:
    """
    Parsa una stringa di controllo del tempo (es. "15+10", "90+30", "3+2")
    e restituisce un dizionario strutturato con minuti, incremento e valore PGN,
    oppure None se non è valida.
    """
    import re

    time_control_str = time_control_str.strip()

    # Riconosce formati tipo "15+10", "90 + 30", "15" (senza incremento)
    match = re.match(r"^(\d+)(?:\s*\+\s*(\d+))?$", time_control_str)
    if not match:
        return None

    minutes = int(match.group(1))
    increment = int(match.group(2)) if match.group(2) else 0

    if minutes < 0 or increment < 0:
        return None

    # Conversione in secondi per il valore PGN
    seconds = minutes * 60
    pgn_value = f"{seconds}+{increment}"

    return {"minutes": minutes, "increment": increment, "pgn_value": pgn_value}


def classify_tournament_category(minutes: int, increment: int) -> str:
    """
    Classifica il torneo in base al tempo di riflessione calcolato su 60 mosse:
    Tempo Totale (in minuti) = minuti + incremento.
    - Blitz: Tempo Totale <= 10 minuti
    - Rapid: 10 < Tempo Totale < 60 minuti
    - Standard (Classical): Tempo Totale >= 60 minuti
    """
    total_time = minutes + increment
    if total_time <= 10:
        return "blitz"
    elif total_time < 60:
        return "rapid"
    else:
        return "standard"


def compute_sonneborn_berger(player_id, torneo):
    """Sonneborn-Berger, articoli 9.1 e 16: per ogni turno il punteggio
    dell'avversario, reale o fittizio, moltiplicato per i punti che il
    giocatore ha fatto in quel turno."""
    contributi = contributi_spareggio(player_id, torneo)
    if not contributi:
        return 0.0
    totale = sum(c["punteggio"] * c["punti"] for c in contributi)
    # Niente format_points qui: arrotonda a un decimale, mentre il
    # Sonneborn-Berger e' un prodotto che cade spesso sui quarti di punto e
    # serve intero per ordinare la classifica.
    return round(totale, 4)


def compute_direct_encounter(player_id, torneo):
    """Calcola il punteggio dello scontro diretto contro i giocatori a pari punti."""
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0.0

    try:
        player_points = float(player.get("points", 0.0))
    except (ValueError, TypeError):
        player_points = 0.0

    players = torneo.get("players", [])
    # Trova gli ID dei giocatori a pari punti (escluso se stesso)
    tied_player_ids = set()
    for p in players:
        if p.get("id") != player_id:
            try:
                p_pts = float(p.get("points", 0.0))
            except (ValueError, TypeError):
                p_pts = 0.0
            if p_pts == player_points:
                tied_player_ids.add(p.get("id"))

    if not tied_player_ids:
        return 0.0

    de_score = 0.0
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        if opponent_id in tied_player_ids:
            score = result_entry.get("score")
            if score is not None:
                try:
                    de_score += float(score)
                except (ValueError, TypeError):
                    pass
    return float(format_points(de_score))


def compute_played_rounds_rep(player_id, torneo):
    """Calcola i turni in cui il giocatore ha effettivamente giocato (REP)."""
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0

    played_count = 0
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        if not opponent_id or opponent_id == "BYE_PLAYER_ID":
            continue

        result_str = result_entry.get("result")
        if not result_str:
            continue

        result_upper = str(result_str).upper()
        if "F" in result_upper or "BYE" in result_upper:
            continue

        played_count += 1

    return played_count


def compute_number_of_wins(player_id, torneo):
    """Calcola il maggior numero di vittorie conseguite (incluse a tavolino/forfeit)."""
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0

    wins = 0
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        if opponent_id == "BYE_PLAYER_ID":
            continue

        score = result_entry.get("score")
        if score is not None:
            try:
                score_val = float(score)
            except (ValueError, TypeError):
                score_val = 0.0

            if score_val == 1.0:
                wins += 1
    return wins


def compute_number_of_blacks(player_id, torneo):
    """Calcola il maggior numero di partite effettivamente disputate con il Nero."""
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0

    blacks = 0
    for result_entry in player.get("results_history", []):
        if result_entry.get("color") == "black":
            opponent_id = result_entry.get("opponent_id")
            if not opponent_id or opponent_id == "BYE_PLAYER_ID":
                continue

            result_str = result_entry.get("result")
            if result_str:
                result_upper = str(result_str).upper()
                if "F" in result_upper or "BYE" in result_upper:
                    continue
            blacks += 1
    return blacks


def compute_cumulative(player_id, torneo):
    """Calcola la somma dei punteggi progressivi turno per turno (criterio cumulativo)."""
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0.0

    history_sorted = sorted(
        player.get("results_history", []), key=lambda x: x.get("round", 0)
    )

    cumulative_sum = 0.0
    running_total = 0.0
    for result in history_sorted:
        score = result.get("score")
        if score is not None:
            try:
                running_total += float(score)
            except (ValueError, TypeError):
                pass
        cumulative_sum += running_total

    return float(format_points(cumulative_sum))


# ---------------------------------------------------------------------------
# FIDE Tiebreak Criteria – Additional Compute Functions
# ---------------------------------------------------------------------------


def compute_buchholz_generic(
    player_id, torneo, cut1=False, cut2=False, median1=False, median2=False
):
    """Buchholz con i modificatori dell'articolo 14, cioe' Cut-1, Cut-2,
    Median-1 e Median-2, calcolato sui contributi dell'articolo 16.
    I tagli in basso seguono l'eccezione dell'articolo 16.5: quando il
    giocatore ha turni non disponibili al gioco si toglie prima il contributo
    piu' basso proveniente da quei turni."""
    contributi = contributi_spareggio(player_id, torneo)
    if not contributi:
        return 0.0

    valori = [c["punteggio"] for c in contributi]
    vur = [c["vur"] for c in contributi]

    if cut1:
        elementi = _taglia_contributi(valori, 1, vur)
    elif cut2:
        elementi = _taglia_contributi(valori, 2, vur)
    elif median1:
        elementi = _taglia_contributi(valori, 1, vur)
        if len(elementi) > 1:
            elementi.remove(max(elementi, key=lambda e: e[0]))
    elif median2:
        elementi = _taglia_contributi(valori, 2, vur)
        for _ in range(2):
            if len(elementi) > 1:
                elementi.remove(max(elementi, key=lambda e: e[0]))
    else:
        elementi = list(zip(valori, vur, strict=False))

    return float(format_points(sum(valore for valore, _vur in elementi)))


def compute_wins_all(player_id, torneo):
    """WIN: conta TUTTE le vittorie (score == 1.0), inclusi BYE e forfeit."""
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0

    wins = 0
    for result_entry in player.get("results_history", []):
        score = result_entry.get("score")
        if score is not None:
            try:
                if float(score) == 1.0:
                    wins += 1
            except (ValueError, TypeError):
                pass
    return wins


def compute_wins_otb(player_id, torneo):
    """WON: conta le vittorie 'over the board' (no BYE, no forfeit)."""
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0

    wins = 0
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        if not opponent_id or opponent_id == "BYE_PLAYER_ID":
            continue

        result_str = str(result_entry.get("result", "")).upper()
        if "F" in result_str or "BYE" in result_str:
            continue

        score = result_entry.get("score")
        if score is not None:
            try:
                if float(score) == 1.0:
                    wins += 1
            except (ValueError, TypeError):
                pass
    return wins


def compute_black_wins(player_id, torneo):
    """BWG: conta le vittorie OTB con il Nero (esclude forfeit)."""
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0

    wins = 0
    for result_entry in player.get("results_history", []):
        if result_entry.get("color") != "black":
            continue

        opponent_id = result_entry.get("opponent_id")
        if not opponent_id or opponent_id == "BYE_PLAYER_ID":
            continue

        result_str = str(result_entry.get("result", "")).upper()
        if "F" in result_str:
            continue

        score = result_entry.get("score")
        if score is not None:
            try:
                if float(score) == 1.0:
                    wins += 1
            except (ValueError, TypeError):
                pass
    return wins


def compute_progressive_scores(player_id, torneo, cut1=False):
    """PS: punteggio progressivo (cumulativo) con supporto Cut-1.

    Quando cut1=True, si sottrae il punteggio del primo turno dal running
    total prima di sommare (equivale a escludere il progressivo dopo il
    primo turno).
    """
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0.0

    history_sorted = sorted(
        player.get("results_history", []), key=lambda x: x.get("round", 0)
    )

    cumulative_sum = 0.0
    running_total = 0.0
    first_round_score = 0.0

    for i, result in enumerate(history_sorted):
        score = result.get("score")
        if score is not None:
            try:
                score_val = float(score)
                running_total += score_val
                if i == 0:
                    first_round_score = score_val
            except (ValueError, TypeError):
                pass
        cumulative_sum += running_total

    if cut1:
        # Sottrai il contributo del primo turno a tutti i turni successivi
        # Il progressivo del turno 1 = first_round_score
        # Ogni turno successivo include first_round_score nel running_total
        # Quindi sottraiamo first_round_score * len(history_sorted) dalla somma
        # e poi riaggiungiamo il progressivo del turno 1 originale
        # perché quello viene escluso interamente.
        # In pratica: escludiamo il contributo del R1 dal cumulativo.
        num_rounds = len(history_sorted)
        if num_rounds > 0:
            cumulative_sum -= first_round_score * num_rounds

    return float(format_points(cumulative_sum))


def compute_standard_points(player_id, torneo):
    """STD: punti standard basati sul confronto diretto turno per turno.

    Per ogni turno: se il giocatore ha ottenuto PIÙ dell'avversario -> +1,
    se UGUALE -> +0.5, se MENO o nessun avversario -> 0.
    """
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0.0

    std_score = 0.0
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        if not opponent_id or opponent_id == "BYE_PLAYER_ID":
            continue

        player_score = result_entry.get("score")
        if player_score is None:
            continue

        try:
            ps = float(player_score)
        except (ValueError, TypeError):
            continue

        # Cerchiamo il punteggio dell'avversario nello stesso turno
        opp_score = 1.0 - ps  # Complemento (W=1->L=0, D=0.5->D=0.5)

        if ps > opp_score:
            std_score += 1.0
        elif ps == opp_score:
            std_score += 0.5
        # else: 0

    return float(format_points(std_score))


def compute_tournament_pairing_number(player_id, torneo):
    """TPN: numero di abbinamento (seeding) del giocatore.

    Ordina tutti i giocatori per (-initial_elo, cognome, nome) e restituisce
    la posizione 1-based.
    """
    players = torneo.get("players", [])
    if not players:
        return 0

    def sort_key(p):
        try:
            elo = float(p.get("initial_elo", 0))
        except (ValueError, TypeError):
            elo = 0.0
        last = str(p.get("last_name", "")).lower()
        first = str(p.get("first_name", "")).lower()
        return (-elo, last, first)

    sorted_players = sorted(players, key=sort_key)

    for idx, p in enumerate(sorted_players, start=1):
        if p.get("id") == player_id:
            return idx

    return 0


def compute_average_opponent_buchholz(player_id, torneo):
    """AOB: media del Buchholz degli avversari giocati OTB.

    Per ogni avversario reale (no BYE, no forfeit), calcola il suo Buchholz
    e fa la media. Arrotondamento: 0.5 arrotonda per eccesso.
    """
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0

    opp_buchholz_values = []
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        if not opponent_id or opponent_id == "BYE_PLAYER_ID":
            continue

        result_str = str(result_entry.get("result", "")).upper()
        if "F" in result_str or "BYE" in result_str:
            continue

        # Calcola il Buchholz dell'avversario
        opp_bh = compute_buchholz(opponent_id, torneo)
        opp_buchholz_values.append(opp_bh)

    if not opp_buchholz_values:
        return 0

    avg = sum(opp_buchholz_values) / len(opp_buchholz_values)
    return math.floor(avg + 0.5)


def _torneo_con_ultimo_turno_pari(torneo):
    """Copia del torneo in cui tutte le partite dell'ultimo turno sono patte.
    Serve al Fore-Buchholz, che e' un Buchholz calcolato su quello scenario:
    costruire il torneo virtuale e riusare il calcolo dell'articolo 16 evita
    di avere una seconda implementazione degli spareggi da tenere allineata."""
    ultimo_turno = torneo.get("current_round", 1)
    giocatori = []
    for originale in torneo.get("players", []):
        copia = dict(originale)
        storico = []
        differenza = 0.0
        for voce in originale.get("results_history", []):
            voce_copia = dict(voce)
            if voce_copia.get("round") == ultimo_turno and voce_copia.get(
                "opponent_id"
            ) not in (None, BYE_ID):
                vecchi_punti = _numero_float(voce_copia.get("score"))
                voce_copia["score"] = 0.5
                voce_copia["result"] = "1/2-1/2"
                differenza += 0.5 - vecchi_punti
            storico.append(voce_copia)
        copia["results_history"] = storico
        copia["points"] = _numero_float(originale.get("points")) + differenza
        giocatori.append(copia)

    virtuale = dict(torneo)
    virtuale["players"] = giocatori
    virtuale["players_dict"] = {p["id"]: p for p in giocatori}
    rounds = []
    for round_data in torneo.get("rounds", []):
        copia_round = dict(round_data)
        if copia_round.get("round") == ultimo_turno:
            partite = []
            for partita in copia_round.get("matches", []):
                copia_partita = dict(partita)
                if copia_partita.get("result") and copia_partita.get("result") != "BYE":
                    copia_partita["result"] = "1/2-1/2"
                partite.append(copia_partita)
            copia_round["matches"] = partite
        rounds.append(copia_round)
    virtuale["rounds"] = rounds
    return virtuale


def compute_fore_buchholz(player_id, torneo, cut1=False):
    """FB, Fore-Buchholz: il Buchholz che si otterrebbe se tutte le partite
    dell'ultimo turno finissero in parita'. E' una variante del Buchholz,
    quindi segue le stesse regole dell'articolo 16 sui turni non giocati."""
    return compute_buchholz_generic(
        player_id, _torneo_con_ultimo_turno_pari(torneo), cut1=cut1
    )


def compute_sonneborn_berger_generic(player_id, torneo, cut1=False):
    """Sonneborn-Berger con il modificatore Cut-1, calcolato sui contributi
    dell'articolo 16. Il taglio segue l'eccezione dell'articolo 16.5: fra il
    contributo piu' basso proveniente da un turno non disponibile e il
    contributo piu' basso in assoluto si toglie il maggiore dei due, che e'
    sempre il primo quando esistono turni non disponibili."""
    contributi = contributi_spareggio(player_id, torneo)
    if not contributi:
        return 0.0

    valori = [c["punteggio"] * c["punti"] for c in contributi]
    vur = [c["vur"] for c in contributi]
    elementi = (
        _taglia_contributi(valori, 1, vur)
        if cut1
        else list(zip(valori, vur, strict=False))
    )
    return round(sum(valore for valore, _vur in elementi), 4)


def compute_aro_generic(player_id, torneo, cut1=False):
    """ARO con supporto modificatore Cut-1.

    Raccoglie gli Elo iniziali degli avversari. Se cut1, rimuove il più basso
    prima di calcolare la media. Arrotondamento: 0.5 per eccesso.
    """
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0

    players_dict = torneo.get(
        "players_dict", {p["id"]: p for p in torneo.get("players", [])}
    )

    opponent_elos = []
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        if not opponent_id or opponent_id == "BYE_PLAYER_ID":
            continue

        opponent = players_dict.get(opponent_id)
        if opponent and "initial_elo" in opponent:
            try:
                opponent_elos.append(float(opponent["initial_elo"]))
            except (ValueError, TypeError):
                pass

    if not opponent_elos:
        return 0

    if cut1 and len(opponent_elos) > 1:
        opponent_elos.remove(min(opponent_elos))

    avg = sum(opponent_elos) / len(opponent_elos)
    return math.floor(avg + 0.5)


def _get_dp_map():
    """La tabella FIDE della differenza di performance, una sola copia."""
    return DP_FIDE


def compute_tpr(player_id, torneo):
    """TPR: Tournament Performance Rating = ARO + dp(score_percentage).

    Stessa logica di calculate_performance_rating ma esposta come funzione
    di spareggio con la firma standard (player_id, torneo).
    """
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0

    players_dict = torneo.get(
        "players_dict", {p["id"]: p for p in torneo.get("players", [])}
    )

    try:
        initial_elo = float(player.get("initial_elo", DEFAULT_ELO))
    except (ValueError, TypeError):
        initial_elo = DEFAULT_ELO

    opponent_elos = []
    total_score = 0.0
    games_played = 0

    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        score = result_entry.get("score")
        if not opponent_id or opponent_id == "BYE_PLAYER_ID" or score is None:
            continue

        opponent = players_dict.get(opponent_id)
        if not opponent or "initial_elo" not in opponent:
            continue

        try:
            opp_elo = float(opponent["initial_elo"])
            total_score += float(score)
            opponent_elos.append(opp_elo)
            games_played += 1
        except (ValueError, TypeError):
            continue

    if games_played == 0:
        return round(initial_elo)

    avg_opponent_elo = sum(opponent_elos) / games_played
    score_percentage = total_score / games_played

    dp_map = _get_dp_map()
    lookup_p = round(score_percentage, 2)
    lookup_p = max(0.0, min(1.0, lookup_p))
    dp = dp_map.get(lookup_p, 800 if lookup_p > 0.5 else -800)

    return round(avg_opponent_elo + dp)


def compute_ptp(player_id, torneo):
    """PTP: Perfect Tournament Performance.

    Trova il più basso intero R tale che il punteggio atteso (calcolato con
    la formula di probabilità FIDE SENZA cap ±400) >= punteggio reale.
    Ricerca binaria nell'intervallo 0-4000.

    E = sum(1 / (1 + 10^((Ri - R) / 400))) per ogni Elo avversario Ri.
    """
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0

    players_dict = torneo.get(
        "players_dict", {p["id"]: p for p in torneo.get("players", [])}
    )

    opponent_elos = []
    total_score = 0.0

    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        score = result_entry.get("score")
        if not opponent_id or opponent_id == "BYE_PLAYER_ID" or score is None:
            continue

        opponent = players_dict.get(opponent_id)
        if not opponent or "initial_elo" not in opponent:
            continue

        try:
            opp_elo = float(opponent["initial_elo"])
            total_score += float(score)
            opponent_elos.append(opp_elo)
        except (ValueError, TypeError):
            continue

    if not opponent_elos:
        try:
            return round(float(player.get("initial_elo", DEFAULT_ELO)))
        except (ValueError, TypeError):
            return DEFAULT_ELO

    def expected_score_for_rating(r):
        """Punteggio atteso senza cap ±400."""
        return sum(1.0 / (1.0 + 10.0 ** ((ri - r) / 400.0)) for ri in opponent_elos)

    # Ricerca binaria: trova il più basso R dove E(R) >= actual_score
    lo, hi = 0, 4000
    while lo < hi:
        mid = (lo + hi) // 2
        if expected_score_for_rating(mid) >= total_score:
            hi = mid
        else:
            lo = mid + 1

    return lo


def compute_apro(player_id, torneo):
    """APRO: media del TPR di tutti gli avversari giocati OTB.

    Arrotondamento: 0.5 per eccesso (math.floor(value + 0.5)).
    """
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0

    opp_tpr_values = []
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        if not opponent_id or opponent_id == "BYE_PLAYER_ID":
            continue

        result_str = str(result_entry.get("result", "")).upper()
        if "F" in result_str or "BYE" in result_str:
            continue

        opp_tpr = compute_tpr(opponent_id, torneo)
        opp_tpr_values.append(opp_tpr)

    if not opp_tpr_values:
        return 0

    avg = sum(opp_tpr_values) / len(opp_tpr_values)
    return math.floor(avg + 0.5)


def compute_appo(player_id, torneo):
    """APPO: media del PTP di tutti gli avversari giocati OTB.

    Arrotondamento: 0.5 per eccesso (math.floor(value + 0.5)).
    """
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0

    opp_ptp_values = []
    for result_entry in player.get("results_history", []):
        opponent_id = result_entry.get("opponent_id")
        if not opponent_id or opponent_id == "BYE_PLAYER_ID":
            continue

        result_str = str(result_entry.get("result", "")).upper()
        if "F" in result_str or "BYE" in result_str:
            continue

        opp_ptp = compute_ptp(opponent_id, torneo)
        opp_ptp_values.append(opp_ptp)

    if not opp_ptp_values:
        return 0

    avg = sum(opp_ptp_values) / len(opp_ptp_values)
    return math.floor(avg + 0.5)


def compute_rating_tiebreak(player_id, torneo):
    """RTNG: restituisce l'Elo iniziale del giocatore come criterio di spareggio."""
    player = get_player_by_id(torneo, player_id)
    if not player:
        return 0

    try:
        return round(float(player.get("initial_elo", 0)))
    except (ValueError, TypeError):
        return 0


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def compute_tiebreak_value(player_id, torneo, criterion_key, modifiers=None):
    """Dispatcher: calcola il valore di un criterio di spareggio con modificatori."""
    if modifiers is None:
        modifiers = {}

    if criterion_key == "DE":
        return compute_direct_encounter(player_id, torneo)
    elif criterion_key == "WIN":
        return compute_wins_all(player_id, torneo)
    elif criterion_key == "WON":
        return compute_wins_otb(player_id, torneo)
    elif criterion_key == "BPG":
        return compute_number_of_blacks(player_id, torneo)
    elif criterion_key == "BWG":
        return compute_black_wins(player_id, torneo)
    elif criterion_key == "PS":
        return compute_progressive_scores(
            player_id, torneo, cut1=modifiers.get("cut1", False)
        )
    elif criterion_key == "REP":
        return compute_played_rounds_rep(player_id, torneo)
    elif criterion_key == "STD":
        return compute_standard_points(player_id, torneo)
    elif criterion_key == "TPN":
        return compute_tournament_pairing_number(player_id, torneo)
    elif criterion_key == "BH":
        return compute_buchholz_generic(
            player_id,
            torneo,
            cut1=modifiers.get("cut1", False),
            cut2=modifiers.get("cut2", False),
            median1=modifiers.get("median1", False),
            median2=modifiers.get("median2", False),
        )
    elif criterion_key == "AOB":
        return compute_average_opponent_buchholz(player_id, torneo)
    elif criterion_key == "FB":
        return compute_fore_buchholz(
            player_id, torneo, cut1=modifiers.get("cut1", False)
        )
    elif criterion_key == "SB":
        return compute_sonneborn_berger_generic(
            player_id, torneo, cut1=modifiers.get("cut1", False)
        )
    elif criterion_key == "ARO":
        return compute_aro_generic(player_id, torneo, cut1=modifiers.get("cut1", False))
    elif criterion_key == "TPR":
        return compute_tpr(player_id, torneo)
    elif criterion_key == "PTP":
        return compute_ptp(player_id, torneo)
    elif criterion_key == "APRO":
        return compute_apro(player_id, torneo)
    elif criterion_key == "APPO":
        return compute_appo(player_id, torneo)
    elif criterion_key == "RTNG":
        return compute_rating_tiebreak(player_id, torneo)
    return 0.0
