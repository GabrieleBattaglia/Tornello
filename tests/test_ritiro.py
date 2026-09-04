"""Prove sul ritiro a torneo iniziato e sul ritorno alla fase di iscrizione."""


class TestRitornoAllaPreparazione:
    """Quando il ritiro lascerebbe il torneo senza giocatori a sufficienza,
    il torneo torna alla fase in cui si iscrivono i giocatori invece di essere
    eliminato: e' il caso dell'arbitro che si accorge di aver sbagliato la
    creazione. Scelta concordata con Gabriele il 2026-09-04."""

    def _torneo(self):
        primo = {
            "id": "UNO001",
            "first_name": "Anna",
            "last_name": "Bianchi",
            "points": 1.5,
            "withdrawn": True,
            "final_rank": 2,
            "results_history": [
                {
                    "round": 1,
                    "opponent_id": "DUE001",
                    "color": "white",
                    "result": "1-0",
                    "score": 1.0,
                },
                {
                    "round": 2,
                    "opponent_id": "BYE_PLAYER_ID",
                    "color": None,
                    "result": "BYE",
                    "score": 0.5,
                },
            ],
        }
        secondo = {
            "id": "DUE001",
            "first_name": "Bruno",
            "last_name": "Neri",
            "points": 0.0,
            "withdrawn": False,
            "results_history": [
                {
                    "round": 1,
                    "opponent_id": "UNO001",
                    "color": "black",
                    "result": "1-0",
                    "score": 0.0,
                }
            ],
        }
        torneo = {
            "name": "Prova",
            "current_round": 2,
            "next_match_id": 4,
            "total_rounds": 3,
            "players": [primo, secondo],
            "rounds": [
                {
                    "round": 1,
                    "matches": [
                        {
                            "id": 1,
                            "round": 1,
                            "white_player_id": "UNO001",
                            "black_player_id": "DUE001",
                            "result": "1-0",
                        }
                    ],
                },
                {
                    "round": 2,
                    "matches": [
                        {
                            "id": 2,
                            "round": 2,
                            "white_player_id": "UNO001",
                            "black_player_id": None,
                            "result": "BYE",
                        }
                    ],
                },
            ],
        }
        torneo["players_dict"] = {p["id"]: p for p in torneo["players"]}
        return torneo, primo, secondo

    def test_i_turni_vengono_cancellati(self):
        from tournament import riporta_torneo_alla_preparazione

        torneo, _primo, _secondo = self._torneo()

        assert riporta_torneo_alla_preparazione(torneo) is True
        assert torneo["rounds"] == []
        assert torneo["current_round"] == 1
        assert torneo["next_match_id"] == 1

    def test_i_giocatori_tornano_allo_stato_iniziale(self):
        from tournament import riporta_torneo_alla_preparazione

        torneo, primo, secondo = self._torneo()

        riporta_torneo_alla_preparazione(torneo)

        for giocatore in (primo, secondo):
            assert giocatore["points"] == 0.0
            assert giocatore["results_history"] == []
            assert giocatore["withdrawn"] is False
            assert giocatore["received_bye_count"] == 0
            assert giocatore["received_bye_in_round"] == []
            assert giocatore["opponents"] == set()
            assert giocatore["final_rank"] is None

    def test_gli_iscritti_restano(self):
        """L'elenco degli iscritti e i dati generali non si toccano: e' la
        differenza fra riportare indietro il torneo ed eliminarlo."""
        from tournament import riporta_torneo_alla_preparazione

        torneo, _primo, _secondo = self._torneo()

        riporta_torneo_alla_preparazione(torneo)

        assert [p["id"] for p in torneo["players"]] == ["UNO001", "DUE001"]
        assert torneo["name"] == "Prova"
        assert torneo["total_rounds"] == 3

    def test_un_torneo_inesistente_non_fa_danni(self):
        from tournament import riporta_torneo_alla_preparazione

        assert riporta_torneo_alla_preparazione(None) is False
        assert riporta_torneo_alla_preparazione("non un torneo") is False
