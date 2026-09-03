from engine import parse_bbpairings_couples_output


def test_parse_bbpairings_couples_output():
    # Mappa start rank -> ID tornello
    mappa = {1: "GIOC001", 2: "GIOC002", 3: "GIOC003", 4: "GIOC004"}

    # Esempio di output bbpPairings: prima riga è il totale abbinamenti, poi coppie
    raw_output = """2
1 2
3 0
"""

    parsed = parse_bbpairings_couples_output(raw_output, mappa)

    assert parsed is not None
    assert len(parsed) == 2

    # Primo match (White 1 vs Black 2)
    assert parsed[0]["white_player_id"] == "GIOC001"
    assert parsed[0]["black_player_id"] == "GIOC002"
    assert parsed[0]["result"] is None
    assert parsed[0]["is_bye"] is False

    # Secondo match (BYE per 3)
    assert parsed[1]["white_player_id"] == "GIOC003"
    assert parsed[1]["black_player_id"] is None
    assert parsed[1]["result"] == "BYE"
    assert parsed[1]["is_bye"] is True


def test_genera_stringa_trf_per_bbpairings():
    from engine import genera_stringa_trf_per_bbpairings

    torneo = {
        "name": "Test Tournament",
        "site": "Test Site",
        "federation_code": "ITA",
        "start_date": "2026-06-30",
        "end_date": "2026-06-30",
        "total_rounds": 5,
        "current_round": 1,
        "chief_arbiter": "Test Arbiter",
        "time_control": {
            "raw": "15+10",
            "minutes": 15,
            "increment": 10,
            "pgn_value": "900+10",
        },
        "initial_board1_color_setting": "white1",
        "bye_value": 1.0,
        "players_dict": {"P1": {"id": "P1", "withdrawn": False}},
    }

    players = [
        {
            "id": "P1",
            "last_name": "Rossi",
            "first_name": "Mario",
            "initial_elo": 1800,
            "federation": "ITA",
            "fide_id_num_str": "12345",
            "birth_date": "1990-01-01",
            "sex": "m",
            "points": 0.0,
            "results_history": [],
        }
    ]

    mappa_id_a_rank = {"P1": 1}

    trf = genera_stringa_trf_per_bbpairings(torneo, players, mappa_id_a_rank)

    assert trf is not None
    assert "012 Test Tournament" in trf
    assert "192 FIDE_DUTCH" in trf
    assert "142 005" in trf
    assert "152 W" in trf
    assert "162  W 1.0    D 0.5    L 0.0    Z 0.0    P 1.0" in trf


def test_real_tournament_pairing(sample_tournament_dict):
    from engine import genera_stringa_trf_per_bbpairings, run_bbpairings_engine
    from tournament import _ensure_players_dict

    # Prepariamo i dati del torneo
    _ensure_players_dict(sample_tournament_dict)

    # Diciamo che vogliamo fare gli abbinamenti per il turno 2
    current_round = 2
    sample_tournament_dict["current_round"] = current_round

    # Ricalcola i punti dei giocatori per rispecchiare solo i turni precedenti a current_round
    for p in sample_tournament_dict["players"]:
        prev_points = 0.0
        for h in p.get("results_history", []):
            if h.get("round", 0) < current_round:
                prev_points += float(h.get("score", 0.0))
        p["points"] = prev_points

    # Prepariamo la lista dei giocatori
    players = sample_tournament_dict["players"]
    mappa_id_a_rank = {p["id"]: i + 1 for i, p in enumerate(players)}

    trf = genera_stringa_trf_per_bbpairings(
        sample_tournament_dict, players, mappa_id_a_rank
    )
    assert trf is not None

    # Eseguiamo il motore su questo TRF reale!
    success, bbp_output_data, bbp_message = run_bbpairings_engine(trf)
    assert success is True, f"bbpPairings failed: {bbp_message}"
    assert "coppie_raw" in bbp_output_data


class TestRitiratiNelTRF:
    """Il turno non giocato di un ritirato va dichiarato a bbpPairings come Z,
    cioe' zero punti, non come U, che vale il punteggio del bye. Con U il
    totale dichiarato non torna con i risultati e il motore rifiuta il file
    con "The score for player N does not match the game results", bloccando
    la generazione del turno successivo. Riscontrato sul campo il 2026-09-03,
    rilievo E1 della fase 1."""

    def _torneo(self):
        return {
            "name": "Test",
            "site": "Online",
            "federation_code": "ITA",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "total_rounds": 5,
            "current_round": 3,
            "chief_arbiter": "Arbitro",
            "time_control": "Standard",
            "initial_board1_color_setting": "white1",
            "bye_value": 0.5,
        }

    def _giocatori(self):
        ritirato = {
            "id": "RIT001",
            "last_name": "Ritirato",
            "first_name": "Mario",
            "initial_elo": 1500,
            "points": 0.0,
            "withdrawn": True,
            "results_history": [
                {
                    "round": 1,
                    "opponent_id": "ATT001",
                    "color": "black",
                    "result": "F-1",
                    "score": 0.0,
                }
            ],
        }
        attivo = {
            "id": "ATT001",
            "last_name": "Attivo",
            "first_name": "Luigi",
            "initial_elo": 1600,
            "points": 1.0,
            "withdrawn": False,
            "results_history": [
                {
                    "round": 1,
                    "opponent_id": "RIT001",
                    "color": "white",
                    "result": "1-F",
                    "score": 1.0,
                }
            ],
        }
        return ritirato, attivo

    def test_il_turno_saltato_dal_ritirato_non_diventa_un_bye(self):
        from engine import genera_stringa_trf_per_bbpairings

        ritirato, attivo = self._giocatori()
        torneo = self._torneo()
        torneo["players_dict"] = {"RIT001": ritirato, "ATT001": attivo}
        mappa = {"RIT001": 1, "ATT001": 2}

        trf = genera_stringa_trf_per_bbpairings(torneo, [ritirato, attivo], mappa)

        assert trf is not None
        riga_ritirato = next(
            r for r in trf.splitlines() if r.startswith("001") and "Ritirato" in r
        )
        # Il turno 2, non giocato, sta nel blocco che parte dalla colonna 102.
        blocco_turno2 = riga_ritirato[101:111]
        assert "Z" in blocco_turno2, f"atteso Z nel turno 2, trovato: {blocco_turno2!r}"
        assert "U" not in riga_ritirato, (
            "il ritirato non deve avere bye assegnati: " + riga_ritirato
        )

    def test_il_punteggio_dichiarato_torna_con_i_risultati(self):
        from engine import genera_stringa_trf_per_bbpairings

        ritirato, attivo = self._giocatori()
        torneo = self._torneo()
        torneo["players_dict"] = {"RIT001": ritirato, "ATT001": attivo}
        mappa = {"RIT001": 1, "ATT001": 2}

        trf = genera_stringa_trf_per_bbpairings(torneo, [ritirato, attivo], mappa)
        riga_ritirato = next(
            r for r in trf.splitlines() if r.startswith("001") and "Ritirato" in r
        )
        # Colonne 81-84: il punteggio dichiarato, che bbpPairings confronta con
        # la somma dei risultati. Zero punti, sconfitta a forfait piu' turni Z.
        punteggio = float(riga_ritirato[80:84])
        assert punteggio == 0.0


class TestAssegnazioneBye:
    """Chi riceve il bye deve avere i punti previsti dal torneo. Rilievo G1,
    confermato sul campo: nell'interfaccia grafica restava a zero."""

    def _torneo(self):
        giocatore = {
            "id": "GIO001",
            "first_name": "Anna",
            "last_name": "Bianchi",
            "points": 0.0,
            "results_history": [],
        }
        return {
            "bye_value": 0.5,
            "players": [giocatore],
            "players_dict": {"GIO001": giocatore},
        }, giocatore

    def test_il_bye_assegna_i_punti_e_lo_storico(self):
        from tournament import registra_bye_del_turno

        torneo, giocatore = self._torneo()
        matches = [
            {"white_player_id": "GIO001", "black_player_id": None, "result": "BYE"}
        ]

        assegnati = registra_bye_del_turno(torneo, matches, 1)

        assert assegnati == ["GIO001"]
        assert giocatore["points"] == 0.5
        assert giocatore["received_bye_count"] == 1
        assert giocatore["received_bye_in_round"] == [1]
        voce = giocatore["results_history"][0]
        assert voce["round"] == 1
        assert voce["opponent_id"] == "BYE_PLAYER_ID"
        assert voce["score"] == 0.5

    def test_non_assegna_due_volte_lo_stesso_bye(self):
        from tournament import registra_bye_del_turno

        torneo, giocatore = self._torneo()
        matches = [
            {"white_player_id": "GIO001", "black_player_id": None, "result": "BYE"}
        ]

        registra_bye_del_turno(torneo, matches, 1)
        assegnati = registra_bye_del_turno(torneo, matches, 1)

        assert assegnati == []
        assert giocatore["points"] == 0.5
        assert len(giocatore["results_history"]) == 1

    def test_le_partite_normali_non_toccano_i_punti(self):
        from tournament import registra_bye_del_turno

        torneo, giocatore = self._torneo()
        matches = [
            {
                "white_player_id": "GIO001",
                "black_player_id": "ALT001",
                "result": None,
            }
        ]

        assert registra_bye_del_turno(torneo, matches, 1) == []
        assert giocatore["points"] == 0.0
        assert giocatore["results_history"] == []


class TestFallimentoAbbinamenti:
    """Quando bbpPairings non riesce ad abbinare, la funzione deve restituire
    None e lasciare leggibile il motivo. Prima restituiva una stringa nel
    percorso testuale e sollevava un'eccezione in quello grafico, mentre tutti
    i chiamanti verificano se il risultato e' None: il percorso di recupero
    non veniva mai raggiunto. Rilievo B2, confermato sul campo il 2026-09-03,
    dove l'utente ha visto il messaggio di errore imprevisto con error.log."""

    def _torneo_senza_motore(self, tmp_path, monkeypatch):
        import config
        import engine

        # Un eseguibile che non esiste: e' il modo piu' diretto di far fallire
        # il motore, ed e' esattamente la prova fatta sul campo.
        monkeypatch.setattr(engine, "BBP_EXE_PATH", str(tmp_path / "assente.exe"))
        monkeypatch.setattr(engine, "BBP_SUBDIR", str(tmp_path))
        monkeypatch.setattr(engine, "BBP_INPUT_TRF", str(tmp_path / "input.trf"))
        monkeypatch.setattr(config, "BBP_EXE_PATH", str(tmp_path / "assente.exe"))
        giocatori = [
            {
                "id": "P1",
                "last_name": "Uno",
                "first_name": "T",
                "initial_elo": 1500,
                "points": 0.0,
                "withdrawn": False,
                "results_history": [],
            },
            {
                "id": "P2",
                "last_name": "Due",
                "first_name": "T",
                "initial_elo": 1400,
                "points": 0.0,
                "withdrawn": False,
                "results_history": [],
            },
        ]
        return {
            "name": "Prova",
            "site": "Online",
            "federation_code": "ITA",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "total_rounds": 3,
            "current_round": 1,
            "chief_arbiter": "A",
            "time_control": "Standard",
            "initial_board1_color_setting": "white1",
            "bye_value": 0.5,
            "players": giocatori,
            "players_dict": {g["id"]: g for g in giocatori},
        }

    def test_restituisce_none_invece_di_una_stringa(self, tmp_path, monkeypatch):
        from tournament import generate_pairings_for_round

        torneo = self._torneo_senza_motore(tmp_path, monkeypatch)
        esito = generate_pairings_for_round(torneo)

        assert esito is None, f"atteso None, ottenuto {type(esito).__name__}: {esito!r}"

    def test_il_motivo_resta_leggibile(self, tmp_path, monkeypatch):
        from tournament import generate_pairings_for_round, motivo_ultimo_fallimento

        torneo = self._torneo_senza_motore(tmp_path, monkeypatch)
        generate_pairings_for_round(torneo)

        motivo = motivo_ultimo_fallimento(torneo)
        assert motivo, "il motivo del fallimento deve restare disponibile"
        assert isinstance(motivo, str)
