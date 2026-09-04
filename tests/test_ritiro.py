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

    def test_i_giocatori_rimasti_tornano_allo_stato_iniziale(self):
        from tournament import riporta_torneo_alla_preparazione

        torneo, _primo, secondo = self._torneo()

        riporta_torneo_alla_preparazione(torneo)

        assert secondo["points"] == 0.0
        assert secondo["results_history"] == []
        assert secondo["withdrawn"] is False
        assert secondo["received_bye_count"] == 0
        assert secondo["received_bye_in_round"] == []
        assert secondo["opponents"] == set()
        assert secondo["final_rank"] is None

    def test_i_ritirati_escono_dall_elenco_e_gli_altri_restano(self):
        """Chi si era ritirato non tornera' a giocare, quindi esce
        dall'elenco; gli altri restano iscritti, perche' l'arbitro vorra'
        ripartire da loro aggiungendone altri. Scelta di Gabriele del
        2026-09-05."""
        from tournament import riporta_torneo_alla_preparazione

        torneo, _primo, _secondo = self._torneo()

        riporta_torneo_alla_preparazione(torneo)

        assert [p["id"] for p in torneo["players"]] == ["DUE001"]
        assert list(torneo["players_dict"]) == ["DUE001"]
        assert torneo["name"] == "Prova"
        assert torneo["total_rounds"] == 3

    def test_un_torneo_inesistente_non_fa_danni(self):
        from tournament import riporta_torneo_alla_preparazione

        assert riporta_torneo_alla_preparazione(None) is False
        assert riporta_torneo_alla_preparazione("non un torneo") is False


class TestIscrittiETurni:
    """Il rapporto fra iscritti e turni va controllato prima di avviare il
    torneo. Fra N giocatori ci sono N-1 avversari possibili, quindi con meno di
    turni piu' uno iscritti l'abbinatore resta senza incontri nuovi: e' quello
    che e' successo sul campo con cinque giocatori su cinque turni."""

    def _torneo(self, turni, iscritti, ritirati=0):
        players = [{"id": f"P{i}"} for i in range(iscritti + ritirati)]
        for p in players[iscritti:]:
            p["withdrawn"] = True
        return {"total_rounds": turni, "players": players}

    def test_troppi_turni_per_gli_iscritti(self):
        from tournament import controlla_iscritti_e_turni

        si_puo, motivo, _avviso = controlla_iscritti_e_turni(self._torneo(5, 5))

        assert si_puo is False
        assert "6" in motivo

    def test_il_numero_giusto_di_iscritti_va_bene(self):
        from tournament import controlla_iscritti_e_turni

        si_puo, motivo, avviso = controlla_iscritti_e_turni(self._torneo(5, 8))

        assert si_puo is True
        assert motivo is None
        assert avviso is None

    def test_pochi_turni_sono_solo_un_avvertimento(self):
        from tournament import controlla_iscritti_e_turni

        si_puo, motivo, avviso = controlla_iscritti_e_turni(self._torneo(2, 16))

        assert si_puo is True
        assert motivo is None
        assert avviso is not None

    def test_i_ritirati_non_contano_fra_gli_iscritti(self):
        from tournament import controlla_iscritti_e_turni

        si_puo, _motivo, _avviso = controlla_iscritti_e_turni(
            self._torneo(5, 5, ritirati=3)
        )

        assert si_puo is False

    def test_servono_almeno_due_giocatori(self):
        from tournament import controlla_iscritti_e_turni

        si_puo, motivo, _avviso = controlla_iscritti_e_turni(self._torneo(1, 1))

        assert si_puo is False
        assert motivo


class TestRitiroPossibile:
    """Il ritiro non deve mai lasciare il torneo senza abbastanza giocatori per
    arrivare in fondo: e' la regola che impedisce all'abbinatore di fallire a
    meta' torneo. Al minimo teorico, cioe' turni rimanenti piu' uno, si somma
    un giocatore di margine, perche' il sistema svizzero abbina per punteggio e
    puo' esaurire le combinazioni prima del limite matematico."""

    def _torneo(self, turni, turno_corrente, attivi, ritirati=0):
        players = [{"id": f"P{i}"} for i in range(attivi + ritirati)]
        for p in players[attivi:]:
            p["withdrawn"] = True
        return {
            "total_rounds": turni,
            "current_round": turno_corrente,
            "players": players,
        }

    def test_con_pochi_giocatori_il_ritiro_e_impedito(self):
        from tournament import controlla_ritiro_possibile

        # Sette turni, siamo al secondo, restano cinque turni: servono sette
        # giocatori attivi dopo il ritiro e ne resterebbero cinque.
        si_puo, resterebbero, necessari, rimanenti = controlla_ritiro_possibile(
            self._torneo(7, 2, 6), "P0"
        )

        assert si_puo is False
        assert resterebbero == 5
        assert necessari == 7
        assert rimanenti == 5

    def test_con_giocatori_a_sufficienza_il_ritiro_passa(self):
        from tournament import controlla_ritiro_possibile

        si_puo, resterebbero, _necessari, _rimanenti = controlla_ritiro_possibile(
            self._torneo(5, 3, 12), "P0"
        )

        assert si_puo is True
        assert resterebbero == 11

    def test_all_ultimo_turno_il_ritiro_e_sempre_possibile(self):
        """Non ci sono piu' abbinamenti da fare, quindi nessun rischio."""
        from tournament import controlla_ritiro_possibile

        si_puo, _resterebbero, _necessari, rimanenti = controlla_ritiro_possibile(
            self._torneo(5, 5, 4), "P0"
        )

        assert si_puo is True
        assert rimanenti == 0

    def test_i_gia_ritirati_non_contano(self):
        from tournament import controlla_ritiro_possibile

        si_puo, resterebbero, _necessari, _rimanenti = controlla_ritiro_possibile(
            self._torneo(3, 1, 5, ritirati=4), "P0"
        )

        assert resterebbero == 4
        assert si_puo is True

    def test_un_torneo_inesistente_non_fa_danni(self):
        from tournament import controlla_ritiro_possibile

        assert controlla_ritiro_possibile(None, "P0") == (False, 0, 0, 0)
