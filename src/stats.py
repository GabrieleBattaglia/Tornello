import math
import re
from collections import Counter
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta

from config import DATE_FORMAT_ISO, DEFAULT_ELO, DEFAULT_K_FACTOR
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


def campo_elo_della_cadenza(category) -> str:
    """Il campo della scheda del database che riceve la variazione Elo di un
    torneo alla finalizzazione: elo_blitz nei blitz, elo_rapid nei rapid,
    current_elo negli standard. E' il primo campo che
    get_initial_elo_for_tournament guarda per l'Elo di partenza, e una
    categoria mancante vale standard, come li'. Fino alla 10.13.3 la
    variazione andava sempre su current_elo, anche nei rapid e nei blitz;
    dalla 10.13.4 va sull'Elo della cadenza, per decisione di Gabriele come
    arbitro, nella finestra e nella console. La finalizzazione scrive il
    campo nella voce dello storico, elo_field, e lo storno della riapertura
    la toglie da li'."""
    categoria = str(category or "standard").lower()
    if categoria == "blitz":
        return "elo_blitz"
    if categoria == "rapid":
        return "elo_rapid"
    return "current_elo"


def elo_a_cui_sommare_la_variazione(player_db_data: dict, category) -> int:
    """L'Elo della scheda a cui la finalizzazione somma la variazione del
    torneo, per scriverla nel campo di campo_elo_della_cadenza.
    Negli standard e' current_elo, come e' sempre stato: DEFAULT_ELO se manca
    o non e' un numero. Nei rapid e nei blitz e' l'Elo della cadenza, e se il
    giocatore non lo ha, perche' manca o vale zero, si fa come per l'Elo di
    partenza del torneo, con get_initial_elo_for_tournament: l'Elo FIDE della
    cadenza, poi current_elo, poi l'Elo club, poi DEFAULT_ELO. Cosi' l'Elo
    della cadenza nasce dall'Elo con cui il giocatore ha cominciato il
    torneo, piu' la variazione, e current_elo resta com'e'."""
    try:
        if campo_elo_della_cadenza(category) == "current_elo":
            return int(player_db_data.get("current_elo", DEFAULT_ELO))
        return int(get_initial_elo_for_tournament(player_db_data, str(category)))
    except (ValueError, TypeError):
        return int(DEFAULT_ELO)


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
    if total_time < 60:
        return "rapid"
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
    if criterion_key == "WIN":
        return compute_wins_all(player_id, torneo)
    if criterion_key == "WON":
        return compute_wins_otb(player_id, torneo)
    if criterion_key == "BPG":
        return compute_number_of_blacks(player_id, torneo)
    if criterion_key == "BWG":
        return compute_black_wins(player_id, torneo)
    if criterion_key == "PS":
        return compute_progressive_scores(
            player_id, torneo, cut1=modifiers.get("cut1", False)
        )
    if criterion_key == "REP":
        return compute_played_rounds_rep(player_id, torneo)
    if criterion_key == "STD":
        return compute_standard_points(player_id, torneo)
    if criterion_key == "TPN":
        return compute_tournament_pairing_number(player_id, torneo)
    if criterion_key == "BH":
        return compute_buchholz_generic(
            player_id,
            torneo,
            cut1=modifiers.get("cut1", False),
            cut2=modifiers.get("cut2", False),
            median1=modifiers.get("median1", False),
            median2=modifiers.get("median2", False),
        )
    if criterion_key == "AOB":
        return compute_average_opponent_buchholz(player_id, torneo)
    if criterion_key == "FB":
        return compute_fore_buchholz(
            player_id, torneo, cut1=modifiers.get("cut1", False)
        )
    if criterion_key == "SB":
        return compute_sonneborn_berger_generic(
            player_id, torneo, cut1=modifiers.get("cut1", False)
        )
    if criterion_key == "ARO":
        return compute_aro_generic(player_id, torneo, cut1=modifiers.get("cut1", False))
    if criterion_key == "TPR":
        return compute_tpr(player_id, torneo)
    if criterion_key == "PTP":
        return compute_ptp(player_id, torneo)
    if criterion_key == "APRO":
        return compute_apro(player_id, torneo)
    if criterion_key == "APPO":
        return compute_appo(player_id, torneo)
    if criterion_key == "RTNG":
        return compute_rating_tiebreak(player_id, torneo)
    return 0.0


SECONDI_AL_GIORNO = 24 * 60 * 60


def _secondi_trascorsi(inizio, fine, adesso, concluso):
    """Secondi trascorsi fra due date del calendario e secondi in tutto;
    None se le date mancano o non si leggono. Il tempo comincia alla
    mezzanotte della data d'inizio e finisce alla mezzanotte dopo la data di
    fine, cosi' l'ultimo giorno e' compreso e i turni del calendario si
    toccano senza buchi. Prima dell'inizio vale zero, dopo la fine o a cose
    concluse il totale.
    Fino alla 10.4.1 il conto era a giorni interi: la percentuale restava
    ferma per tutto il giorno e a mezzanotte saltava, di 6,25 punti in un
    turno di 16 giorni (issue 53). Le date sono dell'ora locale: il cambio
    dell'ora sposta il conto di un'ora, lo 0,04 per cento su 98 giorni.
    """
    try:
        dt_inizio = datetime.strptime(inizio, DATE_FORMAT_ISO)
        dt_fine = datetime.strptime(fine, DATE_FORMAT_ISO) + timedelta(days=1)
    except (TypeError, ValueError):
        return None
    totale = max((dt_fine - dt_inizio).total_seconds(), 1)
    if concluso:
        return totale, totale
    return min(max((adesso - dt_inizio).total_seconds(), 0), totale), totale


def giorno_del_torneo(torneo, adesso):
    """Il tempo trascorso del torneo e il tempo in tutto, in secondi, dalle
    date di inizio e di fine; None se le date mancano o non si leggono.
    Il conto arriva fino a questo momento. Fino alla 10.0.2 partiva dalla data
    d'inizio del turno in corso, e il pie' di pagina restava fermo per tutto
    il turno: Autunneo2, cominciato il 15 settembre, il 23 diceva ancora
    giorno 1 di 98 (issue 44). Dalla 10.4.2 si conta in secondi (issue 53).
    Prima dell'inizio vale zero, a torneo concluso il totale.
    """
    return _secondi_trascorsi(
        torneo.get("start_date"),
        torneo.get("end_date"),
        adesso,
        torneo.get("concluded", False),
    )


def tempo_del_turno(torneo, adesso):
    """Secondi trascorsi del turno in corso e secondi del turno, dalle date
    del calendario dei turni; None se il turno non ha date.
    """
    turno = next(
        (
            rd
            for rd in torneo.get("round_dates", [])
            if rd.get("round") == torneo.get("current_round")
        ),
        None,
    )
    if not turno:
        return None
    return _secondi_trascorsi(
        turno.get("start_date"),
        turno.get("end_date"),
        adesso,
        torneo.get("concluded", False),
    )


def partite_previste(torneo):
    """Le partite di tutto il torneo: quelle dei turni gia' abbinati, bye
    compresi, piu' quelle dei turni ancora da abbinare, una ogni due
    giocatori in gara, arrotondando per eccesso per il bye.
    Fino alla 10.0.3 il pie' di pagina contava solo i turni abbinati, e la
    percentuale dei risultati diceva quanto era avanti il turno, non il
    torneo: 10 partite su 13, il 76,9 per cento, al primo turno di sei
    (issue 44).
    """
    abbinati = torneo.get("rounds", [])
    partite = sum(len(r.get("matches", [])) for r in abbinati)
    in_gara = sum(1 for p in torneo.get("players", []) if not p.get("withdrawn", False))
    mancanti = max(torneo.get("total_rounds", 5) - len(abbinati), 0)
    return partite + mancanti * ((in_gara + 1) // 2)


# Le soglie che fanno scattare le due manutenzioni, gli stessi valori degli
# avvisi all'avvio: 18 mesi per la pulizia dei backup, 30 giorni per
# l'aggiornamento del database FIDE.
SOGLIA_BACKUP_GIORNI = 548
SOGLIA_FIDE_GIORNI = 30
ESITI_SULLA_SCACCHIERA = ("1-0", "0-1", "1/2-1/2")


def _testo_nudo(testo):
    """Il testo in minuscolo, con gli spazi interni ridotti a uno e senza
    spazi ne' punteggiatura ai bordi: "  Non necessario. " diventa
    "non necessario"."""
    testo = " ".join(str(testo or "").split()).lower()
    return re.sub(r"^[\W_]+|[\W_]+$", "", testo)


def arbitro_non_necessario(programmazione):
    """Se chi ha programmato la partita ha detto che l'arbitro non serve.
    Dalla 10.2.0 lo dice la casella della finestra di programmazione; le
    programmazioni precedenti lo scrivevano a mano nel campo, come Non
    necessario o no, e valgono lo stesso. Il confronto e' sul campo intero:
    cercare "no" dentro il testo escluderebbe Bruno, Stefano o Luciano.
    Dalla 10.4.1 spazi e punteggiatura ai bordi non contano: in un torneo
    archiviato c'era "Non necessario." col punto, e la partita risultava
    avere un arbitro.
    """
    if programmazione.get("arbiter_not_needed"):
        return True
    return _testo_nudo(programmazione.get("arbiter")) in ("no", "non necessario")


# I servizi che capita di trovare nel campo Sala / URL, riconosciuti dal
# dominio: vale il dominio stesso o uno qualunque dei suoi sottodomini, come
# call.whatsapp.com o chat.whatsapp.com. Ogni nome sta negli 8 caratteri
# della sala: Chess.com, tagliato, diventerebbe Chess.co, che e' un altro
# dominio.
SERVIZI_NOTI = (
    ("whatsapp.com", "WhatsApp"),
    ("whatsapp.net", "WhatsApp"),
    ("wa.me", "WhatsApp"),
    ("lichess.org", "Lichess"),
    ("chess.com", "Chesscom"),
    ("meet.google.com", "Meet"),
    ("teams.microsoft.com", "Teams"),
    ("teams.live.com", "Teams"),
    ("zoom.us", "Zoom"),
    ("zoom.com", "Zoom"),
    ("discord.com", "Discord"),
    ("discord.gg", "Discord"),
    ("discordapp.com", "Discord"),
    ("jit.si", "Jitsi"),
    ("jitsi.org", "Jitsi"),
    ("skype.com", "Skype"),
)
# Un indirizzo comincia con http://, https:// o www., oppure e' un dominio
# scritto da solo, come lichess.org/abc. Nel secondo caso l'estensione deve
# essere fra queste: con una qualunque, anche Sala.Blu passerebbe per un
# indirizzo.
_ESTENSIONI = (
    "com", "org", "net", "it", "eu", "io", "me", "gg", "us", "si", "co",
    "uk", "ch", "de", "fr", "es", "pt", "app", "info", "tv", "ly", "live",
)
_INDIRIZZO = re.compile(
    r"(?:https?://|www\.)\S+"
    r"|(?<![\w@.-])[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:" + "|".join(_ESTENSIONI) + r")(?![\w-])(?:[/?#:]\S*)?",
    re.IGNORECASE,
)
# Le estensioni doppie, come co.uk: il nome sta un'etichetta piu' a sinistra.
_SECONDI_LIVELLI = ("co", "com", "org", "net", "gov", "edu", "ac")


def _nome_del_servizio(indirizzo):
    """La parte significativa di un indirizzo: il nome del servizio, se e'
    fra quelli noti, altrimenti il nome del dominio con l'iniziale
    maiuscola, per esempio Scacchierando per www.scacchierando.it/sala."""
    dominio = re.sub(r"^[a-z]+://", "", indirizzo, flags=re.IGNORECASE)
    dominio = re.split(r"[/?#]", dominio, maxsplit=1)[0].rsplit("@", 1)[-1]
    dominio = re.match(r"[a-z0-9.-]*", dominio.lower()).group()
    etichette = [e for e in dominio.split(".") if e]
    if etichette[:1] == ["www"]:
        etichette = etichette[1:]
    dominio = ".".join(etichette)
    for noto, nome in SERVIZI_NOTI:
        if dominio == noto or dominio.endswith("." + noto):
            return nome
    if len(etichette) >= 3 and etichette[-2] in _SECONDI_LIVELLI and len(etichette[-1]) == 2:
        nome = etichette[-3]
    elif len(etichette) >= 2:
        nome = etichette[-2]
    elif etichette:
        nome = etichette[0]
    else:
        return indirizzo
    return nome[:1].upper() + nome[1:]


def _chiave_di_parola(parola):
    """La parola in minuscolo e senza punteggiatura, per confrontarla."""
    return re.sub(r"[\W_]", "", parola).casefold()


def sala_breve(canale, cifre=8):
    """Il campo Sala / URL accorciato per l'etichetta della plancia.
    Ogni indirizzo diventa il nome del suo servizio, poi le parole
    consecutive uguali a meno di maiuscole e punteggiatura si fondono,
    tenendo la prima: "whatsapp https://call.whatsapp.com/voice/..." diventa
    "whatsapp". Infine il taglio, a 8 caratteri se non si chiede altro,
    senza spazi in coda. Il campo vuoto resta vuoto."""
    testo = _INDIRIZZO.sub(lambda m: _nome_del_servizio(m.group()), str(canale or ""))
    parole = []
    for parola in testo.split():
        chiave = _chiave_di_parola(parola)
        if parole and chiave and chiave == _chiave_di_parola(parole[-1]):
            continue
        parole.append(parola)
    return " ".join(parole)[:cifre].rstrip()


def sala_e_arbitro_brevi(programmazione, cifre_sala=8, cifre_arbitro=12):
    """Sala e arbitro di una partita programmata, accorciati per l'etichetta
    delle partite da giocare nella plancia (issue 52): la sala come dice
    sala_breve, l'arbitro ai primi 12 caratteri, oppure No se la partita non
    ne ha bisogno. Un campo vuoto o assente vale N/D. I valori interi restano
    nel dettaglio della partita, nell'area centrale."""
    sala = sala_breve(programmazione.get("channel"), cifre_sala)
    if arbitro_non_necessario(programmazione):
        arbitro = _("No")
    else:
        arbitro = " ".join(str(programmazione.get("arbiter") or "").split())
        arbitro = arbitro[:cifre_arbitro].rstrip()
    return sala or _("N/D"), arbitro or _("N/D")


def _percentuale(parte, totale):
    """Una percentuale con un decimale, oppure -- se non c'e' niente da contare."""
    return f"{parte / totale * 100:.1f}%" if totale else "--"


def _eta_in_percentuale(data, adesso, soglia_giorni):
    """L'eta' di un file, dalla data dell'ultima modifica, in percentuale
    sulla soglia in giorni; -- se il file non c'e'. Il conto e' in secondi,
    come quello di GT e TT. Un file con la data nel futuro, per esempio dopo
    che l'orologio e' stato rimesso indietro, ha eta' zero: fino alla 10.4.1
    dava una percentuale negativa."""
    if data is None:
        return "--"
    eta = max((adesso - data).total_seconds(), 0)
    return _percentuale(eta, soglia_giorni * SECONDI_AL_GIORNO)


def indicatori_pie_di_pagina(
    torneo, adesso, backup_piu_vecchio=None, aggiornamento_fide=None
):
    """Le percentuali del pie' di pagina, per acronimo, dalla 10.1.0.
    Ogni valore e' gia' scritto come xx.y%, oppure -- quando manca il dato o
    il totale e' zero. Gli acronimi sono spiegati nel manuale. Esiti, PGN e
    punteggio del bianco non contano i bye; PGN e punteggio del bianco non
    contano nemmeno i forfeit, che sulla scacchiera non si sono giocati.
    backup_piu_vecchio e aggiornamento_fide sono le date di modifica della
    copia di sicurezza piu' vecchia e del database FIDE, None se mancano.
    Dalla 10.4.2 tutto il conto del tempo sta qui, sullo stesso adesso: fino
    alla 10.4.1 BK e FD arrivavano gia' come eta' in giorni interi.
    """
    turni = torneo.get("rounds", [])
    partite = [m for r in turni for m in r.get("matches", [])]
    vere = [m for m in partite if m.get("black_player_id") != "BYE_PLAYER_ID"]
    decise = [m for m in vere if m.get("result")]
    sulla_scacchiera = [m for m in decise if m.get("result") in ESITI_SULLA_SCACCHIERA]
    in_attesa = [m for m in vere if not m.get("result")]
    programmate = [m for m in in_attesa if (m.get("schedule_info") or {}).get("date")]
    con_arbitro_da_dare = [
        m for m in programmate if not arbitro_non_necessario(m["schedule_info"])
    ]
    esiti = Counter(m.get("result") for m in decise)
    turno = next(
        (r for r in turni if r.get("round") == torneo.get("current_round")), None
    )
    partite_turno = turno.get("matches", []) if turno else []
    conclusi = sum(
        1
        for r in turni
        if r.get("matches") and all(m.get("result") for m in r["matches"])
    )
    giorni = giorno_del_torneo(torneo, adesso)
    tempo = tempo_del_turno(torneo, adesso)
    return {
        "gt": _percentuale(*giorni) if giorni else "--",
        "tt": _percentuale(*tempo) if tempo else "--",
        "tc": _percentuale(conclusi, torneo.get("total_rounds", 5)),
        "pg": _percentuale(
            sum(1 for m in partite if m.get("result")), partite_previste(torneo)
        ),
        "rt": _percentuale(
            sum(1 for m in partite_turno if m.get("result")), len(partite_turno)
        ),
        "pr": _percentuale(len(programmate), len(in_attesa)),
        "ar": _percentuale(
            sum(
                1
                for m in con_arbitro_da_dare
                if (m["schedule_info"].get("arbiter") or "").strip()
            ),
            len(con_arbitro_da_dare),
        ),
        "pn": _percentuale(
            sum(1 for m in sulla_scacchiera if m.get("pgn")), len(sulla_scacchiera)
        ),
        "vb": _percentuale(esiti["1-0"], len(decise)),
        "pa": _percentuale(esiti["1/2-1/2"], len(decise)),
        "vn": _percentuale(esiti["0-1"], len(decise)),
        "fb": _percentuale(esiti["1-F"], len(decise)),
        "fn": _percentuale(esiti["F-1"], len(decise)),
        "pb": _percentuale(
            esiti["1-0"] + esiti["1/2-1/2"] / 2, len(sulla_scacchiera)
        ),
        "bk": _eta_in_percentuale(backup_piu_vecchio, adesso, SOGLIA_BACKUP_GIORNI),
        "fd": _eta_in_percentuale(aggiornamento_fide, adesso, SOGLIA_FIDE_GIORNI),
    }


# Le due righe di indicatori del pie' di pagina, nell'ordine di lettura.
# Dalla 10.5.0 si aggiornano da sole e sono dati in tempo reale, quindi a
# larghezza fissa per la barra braille: ogni indicatore occupa 10 caratteri,
# cioe' acronimo in 2, spazio, valore allineato a destra in 6 caratteri e
# spazio. Quattro indicatori fanno un blocco da 40, il secondo blocco parte
# dal carattere 41, e un valore resta nelle stesse celle quando passa da 9.9%
# a 10.0% o arriva a 100.0%.
RIGHE_DEL_PIE_DI_PAGINA = (
    ("gt", "tt", "tc", "pg", "rt", "pr", "ar", "pn"),
    ("vb", "pa", "vn", "fb", "fn", "pb", "bk", "fd"),
)
LETTERE_DELLA_SIGLA = 2
CIFRE_DEL_VALORE = 6


def sigle_del_pie_di_pagina():
    """Gli acronimi del pie' di pagina nella lingua in uso, per chiave di
    indicatori_pie_di_pagina. Passano da _() come ogni testo mostrato, e si
    leggono a ogni chiamata; il manuale, solo in italiano, li spiega nella
    sezione 2.3.1. Fino alla 10.4.2 stavano dentro le due righe, tradotte
    intere: con la larghezza fissa della 10.5.0 si traducono uno per uno."""
    # Per chi traduce: ogni acronimo deve restare di due lettere. Le righe
    # sono impaginate a blocchi da 40 caratteri per la barra braille, e
    # righe_pie_di_pagina taglia o completa con uno spazio quello che non ci
    # sta.
    return {
        "gt": _("GT"),
        "tt": _("TT"),
        "tc": _("TC"),
        "pg": _("PG"),
        "rt": _("RT"),
        "pr": _("PR"),
        "ar": _("AR"),
        "pn": _("PN"),
        "vb": _("VB"),
        "pa": _("PA"),
        "vn": _("VN"),
        "fb": _("FB"),
        "fn": _("FN"),
        "pb": _("PB"),
        "bk": _("BK"),
        "fd": _("FD"),
    }


def _sigla_in_due(sigla):
    """L'acronimo in 2 caratteri esatti, cosi' l'indicatore resta di 10 con
    qualunque traduzione: una piu' lunga si taglia, una piu' corta si completa
    con uno spazio."""
    return sigla[:LETTERE_DELLA_SIGLA].ljust(LETTERE_DELLA_SIGLA)


def _valore_in_sei(valore):
    """Il valore di un indicatore in 6 caratteri al massimo. Li superano solo
    BK e FD, da 1000.0% in su, cioe' dopo 15 anni senza pulizia dei backup o
    dopo 300 giorni senza aggiornare il database FIDE: diventano >999%."""
    return valore if len(valore) <= CIFRE_DEL_VALORE else ">999%"


def righe_pie_di_pagina(valori):
    """Le due righe di indicatori del pie' di pagina, dai valori di
    indicatori_pie_di_pagina: 80 caratteri ciascuna, cioe' due blocchi da 40
    di quattro indicatori, per esempio "GT  10.7% TT  65.6% TC   0.0% ..."."""
    sigle = sigle_del_pie_di_pagina()
    return [
        "".join(
            f"{_sigla_in_due(sigle[chiave])} "
            f"{_valore_in_sei(valori[chiave]):>{CIFRE_DEL_VALORE}} "
            for chiave in riga
        )
        for riga in RIGHE_DEL_PIE_DI_PAGINA
    ]
