import copy

from models import Tournament


def test_tournament_serialization_roundtrip(sample_tournament_dict):
    # Deserializza
    tournament = Tournament.from_dict(sample_tournament_dict)

    # Asserzioni sui dati base
    assert tournament.name == "ASCId Primavera 1"
    assert tournament.total_rounds == 5
    assert len(tournament.players) == 28
    assert len(tournament.rounds) == 5

    # Riserializza
    serialized_dict = tournament.to_dict()

    # Asserzioni sulla consistenza dei dati
    assert serialized_dict["name"] == sample_tournament_dict["name"]
    assert len(serialized_dict["players"]) == len(sample_tournament_dict["players"])
    assert len(serialized_dict["rounds"]) == len(sample_tournament_dict["rounds"])

    # Verifica che players_dict sia ricostruito correttamente
    assert len(tournament.players_dict) == 28
    assert tournament.players_dict["BATGA001"].first_name == "Gabriele"


def test_rollback_to_previous_round(sample_tournament_dict):
    import copy

    from tournament import rollback_to_previous_round

    t_dict = copy.deepcopy(sample_tournament_dict)

    initial_rounds_count = len(t_dict.get("rounds", []))
    assert initial_rounds_count == 5
    t_dict["current_round"] = 5

    # Rollback round 5
    success = rollback_to_previous_round(t_dict)
    assert success is True
    assert len(t_dict.get("rounds", [])) == 4
    assert t_dict["current_round"] == 4

    # Rollback round 4
    success = rollback_to_previous_round(t_dict)
    assert success is True
    assert len(t_dict.get("rounds", [])) == 3
    assert t_dict["current_round"] == 3

    # Rollback until empty
    for _ in range(3):
        rollback_to_previous_round(t_dict)

    assert len(t_dict.get("rounds", [])) == 0
    assert t_dict["current_round"] == 1


# Dalla 10.8.3 (issue 56): la console lavora sul modello e salva con
# Tournament.to_dict, che scrive solo le chiavi che conosce. Fino alla 10.8.2
# un torneo passato dalla console perdeva i criteri di spareggio, e i giocatori
# l'ARO. Le prove che seguono caricano un json intero nel modello, lo
# riscrivono e cercano le chiavi sparite, a ogni livello. Coprono le chiavi
# del torneo campione e quelle elencate in torneo_della_finestra, che e'
# scritto a mano: una chiave che la finestra comincia a scrivere va aggiunta
# li', altrimenti le prove restano verdi anche se il modello la perde. Il
# controllo di uguaglianza ferma da solo soltanto il caso opposto, un campo
# nuovo del modello che manchi nel torneo della finestra.

# Le chiavi del torneo che il modello lascia fuori apposta.
CHIAVI_ESCLUSE = {
    # La cache dei giocatori per identificativo: si ricostruisce a ogni
    # caricamento, e save_tournament la toglie prima di scrivere.
    "players_dict",
    # Il motivo dell'ultimo abbinamento fallito, che serve solo al messaggio
    # della sessione in corso (tournament.py, CHIAVE_ERRORE_ABBINAMENTO), e
    # dalla 10.12.0 il suo compagno, che dice se le coppie erano esaurite.
    "_errore_abbinamento",
    "_abbinamento_esaurito",
    # Il fattore K del torneo, scritto dalle versioni vecchie, come nel
    # torneo campione: oggi il K e' di ogni giocatore, e nessuno lo rilegge.
    "k_factor",
}


def chiavi_perse(prima, dopo, percorso=""):
    """I percorsi delle chiavi che ci sono in prima e mancano in dopo, a ogni
    livello: torneo, giocatori, storico, turni, partite, programmazioni e
    criteri di spareggio. Le liste si confrontano voce per voce."""
    perse = []
    if isinstance(prima, dict) and isinstance(dopo, dict):
        for chiave, valore in prima.items():
            dove = f"{percorso}.{chiave}" if percorso else chiave
            if chiave not in dopo:
                perse.append(dove)
            else:
                perse.extend(chiavi_perse(valore, dopo[chiave], dove))
    elif isinstance(prima, list) and isinstance(dopo, list):
        for indice, (voce, riscritta) in enumerate(zip(prima, dopo, strict=False)):
            perse.extend(chiavi_perse(voce, riscritta, f"{percorso}[{indice}]"))
    return perse


def senza_le_escluse(torneo):
    return {k: v for k, v in torneo.items() if k not in CHIAVI_ESCLUSE}


def torneo_della_finestra():
    """Un torneo come lo scrive oggi la finestra, con ogni chiave che la
    finestra mette nel json, i criteri di spareggio scelti, una partita
    programmata con il PGN, un bye e le due chiavi che il modello esclude.
    I valori sono gia' nella forma del modello, cosi' la riscrittura deve
    restituirli identici. L'elenco e' fermo alla 10.8.3: ogni chiave nuova
    della finestra, del torneo, dei giocatori o delle partite, va aggiunta
    qui. Dalla 10.12.0 il turno 2 e' composto a mano, con il suo
    contrassegno, e c'e' la seconda chiave dell'abbinamento fallito."""
    giocatrice = {
        "id": "BIANA001",
        "first_name": "Anna",
        "last_name": "Bianchi",
        "initial_elo": 1650.0,
        "fide_title": "WCM",
        "sex": "w",
        "gender": "W",
        "federation": "ITA",
        "fide_id_num_str": "123456",
        "birth_date": "1990-05-17",
        "points": 1.5,
        "results_history": [
            {"round": 1, "opponent_id": "ROSMA001", "color": "white", "result": "1-0", "score": 1.0},
            {"round": 2, "opponent_id": "BYE_PLAYER_ID", "color": None, "result": "BYE", "score": 0.5},
        ],
        "opponents": ["ROSMA001"],
        "white_games": 1,
        "black_games": 0,
        "last_color": "white",
        "consecutive_white": 1,
        "consecutive_black": 0,
        "received_bye_count": 1,
        "received_bye_in_round": [2],
        "buchholz": 0.5,
        "buchholz_cut1": 0.0,
        "aro": 1580.0,
        "performance_rating": 1980.0,
        "elo_change": 7.5,
        "k_factor": 20,
        "games_this_tournament": 1,
        "downfloat_count": 0,
        "final_rank": None,
        "withdrawn": False,
        "display_rank": 1,
        "elo_club": 1640.0,
        "elo_rapid": 1700.0,
        "elo_blitz": None,
        "fide_k_factor": 20,
        "fide_rapid_k": 20,
        "fide_blitz_k": None,
        "fide_standard_games": 42,
        "fide_rapid_games": 12,
        "fide_blitz_games": 0,
        "w_title": "WCM",
        "o_title": "",
        "foa_title": "",
        "flag": "",
        "current_elo": 1650.0,
    }
    avversario = dict(
        giocatrice,
        id="ROSMA001",
        first_name="Marco",
        last_name="Rossi",
        sex="m",
        gender="M",
        fide_title="",
        w_title="",
        points=0.0,
        results_history=[{"round": 1, "opponent_id": "BIANA001", "color": "black", "result": "1-0", "score": 0.0}],
        opponents=["BIANA001"],
        received_bye_count=0,
        received_bye_in_round=[],
        aro=1650.0,
    )
    return {
        "launch_count": 3,
        "name": "Prova della finestra",
        "tournament_id": "PROVA_DELLA_FINESTRA",
        "start_date": "2026-09-01",
        "end_date": "2026-12-31",
        "total_rounds": 5,
        "site": "Online",
        "federation_code": "ITA",
        "chief_arbiter": "Gabriele Battaglia",
        "deputy_chief_arbiters": "ClaudIA",
        "time_control": {"minutes": 60, "increment": 30},
        "initial_board1_color_setting": "black1",
        "round_dates": [
            {"round": 1, "start_date": "2026-09-01", "end_date": "2026-09-16"},
            {"round": 2, "start_date": "2026-09-17", "end_date": "2026-10-02"},
        ],
        "players": [giocatrice, avversario],
        "rounds": [
            {
                "round": 1,
                "matches": [
                    {
                        "id": 1,
                        "round": 1,
                        "white_player_id": "BIANA001",
                        "black_player_id": "ROSMA001",
                        "result": "1-0",
                        "is_scheduled": True,
                        "schedule_info": {
                            "date": "2026-09-10",
                            "time": "17:30",
                            "channel": "https://lichess.org/AbCdEfGh",
                            "arbiter": "Non necessario",
                            "arbiter_not_needed": True,
                        },
                        "pgn": '[Event "Prova"]\n\n1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7# 1-0',
                    },
                ],
            },
            {
                "round": 2,
                "matches": [
                    {"id": 2, "round": 2, "white_player_id": "BIANA001", "black_player_id": None, "result": "BYE", "is_scheduled": False},
                ],
                "manual_pairing": True,
            },
        ],
        "next_match_id": 3,
        "bye_value": 0.5,
        "schema_version": 1,
        "tournament_category": "rapid",
        "current_round": 2,
        "concluded": False,
        "custom_save_path": "D:\\Tornei",
        "save_path": "D:\\Tornei",
        "tiebreaks": [
            {"key": "DE", "modifiers": {}},
            {"key": "BH", "modifiers": {"cut1": True}},
            {"key": "ARO", "modifiers": {}},
        ],
        "_errore_abbinamento": "Nessun abbinamento possibile.",
        "_abbinamento_esaurito": True,
        "players_dict": {"BIANA001": giocatrice, "ROSMA001": avversario},
    }


def test_il_torneo_campione_non_perde_chiavi(sample_tournament_dict):
    """Un torneo vero dell'archivio, scritto da una versione vecchia, passa
    dal modello senza perdere niente, ARO dei giocatori compreso."""
    riscritto = Tournament.from_dict(sample_tournament_dict).to_dict()
    assert chiavi_perse(senza_le_escluse(sample_tournament_dict), riscritto) == []
    assert all("aro" in giocatore for giocatore in riscritto["players"])


def test_il_torneo_della_finestra_torna_identico():
    """Le chiavi del torneo della finestra tornano con il loro valore, e il
    modello non ne aggiunge: una chiave nuova del modello che manchi qui fa
    fallire la prova, perche' il torneo della finestra resti completo. Una
    chiave nuova della finestra, invece, la prova la vede soltanto dopo che
    e' stata aggiunta a torneo_della_finestra."""
    torneo = torneo_della_finestra()
    riscritto = Tournament.from_dict(torneo).to_dict()
    assert chiavi_perse(senza_le_escluse(torneo), riscritto) == []
    assert riscritto == senza_le_escluse(torneo)


def test_le_chiavi_escluse_restano_fuori():
    riscritto = Tournament.from_dict(torneo_della_finestra()).to_dict()
    assert CHIAVI_ESCLUSE.isdisjoint(riscritto)


def test_i_criteri_di_spareggio_passano_dalla_console():
    """I criteri arrivano ai dizionari che la console passa a classifica,
    finalizzazione e salvataggio, anche nel formato vecchio a nomi, e una
    modifica al dizionario non tocca il torneo in memoria."""
    torneo = torneo_della_finestra()
    modello = Tournament.from_dict(torneo)
    assert modello.to_dict()["tiebreaks"] == torneo["tiebreaks"]
    modello.to_dict()["tiebreaks"][1]["modifiers"]["cut1"] = False
    assert modello.tiebreaks[1]["modifiers"] == {"cut1": True}
    vecchi = dict(torneo, tiebreaks=["buchholz_cut1", "buchholz", "aro"])
    assert Tournament.from_dict(vecchi).to_dict()["tiebreaks"] == ["buchholz_cut1", "buchholz", "aro"]


def test_un_torneo_senza_criteri_resta_senza_la_chiave():
    """Un json che non li ha mai scelti non se li vede scrivere: la chiave
    assente vale i criteri predefiniti, oggi e con le versioni di prima."""
    torneo = torneo_della_finestra()
    del torneo["tiebreaks"]
    modello = Tournament.from_dict(torneo)
    assert modello.tiebreaks is None
    assert "tiebreaks" not in modello.to_dict()


def test_la_prova_riconosce_una_chiave_persa():
    """Controprova: una chiave sparita, anche in fondo a una partita, si vede.
    La riscrittura si fa su una copia, perche' Match tiene il dizionario della
    programmazione cosi' com'e', e toglierne una chiave lo toglierebbe anche
    all'originale."""
    torneo = senza_le_escluse(torneo_della_finestra())
    riscritto = Tournament.from_dict(copy.deepcopy(torneo)).to_dict()
    del riscritto["tiebreaks"]
    del riscritto["rounds"][0]["matches"][0]["schedule_info"]["arbiter_not_needed"]
    assert chiavi_perse(torneo, riscritto) == ["rounds[0].matches[0].schedule_info.arbiter_not_needed", "tiebreaks"]


def test_il_turno_composto_a_mano_si_riconosce():
    """Il contrassegno manual_pairing della 10.12.0 (issue 38): nel json
    compare solo quando e' vero, e un turno che non lo ha vale falso, cosi' i
    file di prima si leggono come sempre e i turni del motore restano scritti
    come prima."""
    from models import Round

    manuale = {"round": 4, "matches": [], "manual_pairing": True}
    del_motore = {"round": 3, "matches": []}

    assert Round.from_dict(manuale).manual_pairing is True
    assert Round.from_dict(manuale).to_dict() == manuale
    assert Round.from_dict(del_motore).manual_pairing is False
    assert Round.from_dict(del_motore).to_dict() == del_motore
    assert "manual_pairing" not in Round(round=1).to_dict()
