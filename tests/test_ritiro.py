"""Prove sul ritiro a torneo iniziato e sul ritorno alla fase di iscrizione."""

from types import SimpleNamespace

import pytest


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
    meta' torneo. Il minimo e' quello matematico, turni rimanenti piu' uno,
    senza margine: un ritiro e' un fatto e non una scelta dell'arbitro, e un
    margine avrebbe costretto a rifare tornei che potevano proseguire."""

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

        # Sette turni, siamo al secondo, restano cinque turni: fra sei
        # giocatori si possono giocare al massimo cinque turni, quindi ne
        # servono sei attivi dopo il ritiro e ne resterebbero cinque.
        si_puo, resterebbero, necessari, rimanenti = controlla_ritiro_possibile(
            self._torneo(7, 2, 6), "P0"
        )

        assert si_puo is False
        assert resterebbero == 5
        assert necessari == 6
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


class TestValutaRitiro:
    """Dalla 10.13.1 il controllo numerico sul ritiro e' un avviso con
    conferma, perche' se il motore non riesce ad abbinare un turno l'arbitro
    lo compone a mano (issue 38). Il bivio fra ritorno all'iscrizione ed
    eliminazione resta solo sotto i due giocatori attivi."""

    def _torneo(self, turni, turno_corrente, attivi):
        return {
            "total_rounds": turni,
            "current_round": turno_corrente,
            "players": [{"id": f"P{i}"} for i in range(attivi)],
        }

    def test_con_giocatori_a_sufficienza_e_libero(self):
        from tournament import valuta_ritiro

        assert valuta_ritiro(self._torneo(5, 3, 12), "P0")[0] == "libero"

    def test_con_pochi_giocatori_e_un_avviso(self):
        from tournament import valuta_ritiro

        # Il caso della issue: cinque giocatori su quattro turni, uno si
        # ritira dopo il primo. Fino alla 10.13.0 era un bivio anche con tre.
        assert valuta_ritiro(self._torneo(4, 1, 5), "P0") == ("libero", 4, 4, 3)
        assert valuta_ritiro(self._torneo(4, 1, 4), "P0") == ("avviso", 3, 4, 3)
        assert valuta_ritiro(self._torneo(7, 2, 3), "P0") == ("avviso", 2, 6, 5)

    def test_sotto_i_due_attivi_resta_il_bivio(self):
        from tournament import valuta_ritiro

        assert valuta_ritiro(self._torneo(5, 2, 2), "P0")[0] == "bivio"

    def test_all_ultimo_turno_basta_un_giocatore(self):
        from tournament import valuta_ritiro

        assert valuta_ritiro(self._torneo(5, 5, 2), "P0")[0] == "libero"
        assert valuta_ritiro(self._torneo(5, 5, 1), "P0")[0] == "bivio"


# Le tre strade da cui la finestra ritira un giocatore, su un telaio finto
# con i metodi veri di MainFrame: niente finestre, niente suoni.

AVVISO_COMUNE = "In quel caso Tornello ti proporra' di comporre il turno a mano."


class _Finestre:
    """Al posto di AccessibleMsgDialog: annota titolo, testo e pulsante
    predefinito di ogni domanda, e risponde come da copione."""

    def __init__(self, *risposte):
        self.risposte = list(risposte)
        self.aperte = []

    def __call__(self, parent, title, message, style=None, settings=None, no_predefinito=False):
        import wx

        registro = self

        class Finta:
            def ShowModal(self):
                registro.aperte.append((title, message, no_predefinito))
                return registro.risposte.pop(0) if registro.risposte else wx.ID_OK

            def Destroy(self):
                pass

        return Finta()


def _torneo_in_corso(attivi, turni):
    """Un torneo al turno 2: il turno 1 e' giocato, il turno 2 ha la prima
    coppia ancora da giocare e le altre con il risultato."""
    giocatori = [
        {"id": f"G{i}", "first_name": "Nome", "last_name": f"Cognome{i}", "initial_elo": 1500, "points": 0.0, "withdrawn": False, "results_history": []}
        for i in range(attivi)
    ]
    coppie = [(f"G{i}", f"G{i + 1}") for i in range(0, attivi - 1, 2)]
    turno_1 = [{"id": n + 1, "round": 1, "white_player_id": b, "black_player_id": w, "result": "1-0"} for n, (b, w) in enumerate(coppie)]
    turno_2 = [
        {"id": len(coppie) + n + 1, "round": 2, "white_player_id": w, "black_player_id": b, "result": None if n == 0 else "1/2-1/2"}
        for n, (b, w) in enumerate(coppie)
    ]
    for partita in turno_1:
        partita_giocatori = (partita["white_player_id"], partita["black_player_id"])
        for giocatore in giocatori:
            if giocatore["id"] in partita_giocatori:
                bianco = giocatore["id"] == partita_giocatori[0]
                giocatore["results_history"].append(
                    {"round": 1, "opponent_id": partita_giocatori[1] if bianco else partita_giocatori[0], "color": "white" if bianco else "black", "result": "1-0", "score": 1.0 if bianco else 0.0}
                )
    torneo = {
        "name": "Prova ritiro",
        "total_rounds": turni,
        "current_round": 2,
        "next_match_id": 2 * len(coppie) + 1,
        "players": giocatori,
        "rounds": [{"round": 1, "matches": turno_1}, {"round": 2, "matches": turno_2}],
    }
    torneo["players_dict"] = {g["id"]: g for g in giocatori}
    return torneo


def _telaio(torneo, monkeypatch, finestre, **altri):
    import gui.main_frame as mf
    import utils

    monkeypatch.setattr(mf, "AccessibleMsgDialog", finestre)
    monkeypatch.setattr(utils, "play_sound", lambda *a, **k: True)

    class Telaio:
        _proponi_ritiro_dal_torneo = mf.MainFrame._proponi_ritiro_dal_torneo
        _partita_del_turno_corrente = mf.MainFrame._partita_del_turno_corrente
        _conferma_ritiro = mf.MainFrame._conferma_ritiro
        _bivio_ha_cambiato_il_torneo = mf.MainFrame._bivio_ha_cambiato_il_torneo
        withdraw_player = mf.MainFrame.withdraw_player
        on_activate_match = mf.MainFrame.on_activate_match
        apply_match_result = mf.MainFrame.apply_match_result
        get_board_num = mf.MainFrame.get_board_num
        _e_il_torneo_aperto = mf.MainFrame._e_il_torneo_aperto

        def __init__(self):
            self.current_tournament = torneo
            self.active_filename = "prova_ritiro.json"
            self.settings = {}
            self.bivi = []

        def _save_state(self):
            pass

        def populate_tree(self):
            pass

        def show_players_list_verbose(self):
            pass

        def show_match_detail_verbose(self, *a, **k):
            pass

        def set_status(self, testo):
            pass

        def _dialogo_informativo(self, titolo, testo):
            raise AssertionError(testo)

        def _bivio_torneo_non_proseguibile(self, *argomenti):
            self.bivi.append(argomenti)

    for nome, valore in altri.items():
        setattr(Telaio, nome, valore)
    return Telaio()


def _ritirati(torneo):
    return [g["id"] for g in torneo["players"] if g.get("withdrawn")]


class TestLeTreStradeDelRitiro:
    """L'avviso e' lo stesso nel tasto CANC dell'albero, nel pulsante Ritira
    Giocatore della finestra del risultato e nella domanda dopo un forfait:
    fino alla 10.13.0 le ultime due saltavano il controllo."""

    def _canc(self, telaio, player_id):
        giocatore = telaio.current_tournament["players_dict"][player_id]
        telaio._proponi_ritiro_dal_torneo(None, giocatore, telaio.active_filename)

    def _dal_risultato(self, telaio, monkeypatch, player_id):
        import wx

        from gui.dialogs import result_dialog

        class Risultato:
            def __init__(self, *a, **k):
                self.selected_action = "withdraw"
                self.withdrawn_player_id = player_id

            def ShowModal(self):
                return wx.ID_OK

            def Destroy(self):
                pass

        monkeypatch.setattr(result_dialog, "ResultDialog", Risultato)
        telaio.on_activate_match(telaio.current_tournament["rounds"][1]["matches"][0])

    def _dopo_il_forfait(self, telaio):
        partita = telaio.current_tournament["rounds"][1]["matches"][0]
        partita["result"] = "1-F"
        telaio.apply_match_result(partita, "1-F")

    @pytest.mark.parametrize("risposta", ["si", "no"])
    @pytest.mark.parametrize("strada", ["canc", "risultato", "forfait"])
    def test_con_pochi_giocatori_l_avviso_con_il_no_predefinito(self, strada, risposta, monkeypatch):
        wx = pytest.importorskip("wx")
        torneo = _torneo_in_corso(attivi=4, turni=5)
        scelta = wx.ID_YES if risposta == "si" else wx.ID_NO
        # Dopo il forfait c'e' prima la domanda sul ritiro, a cui si risponde Si'.
        finestre = _Finestre(*([wx.ID_YES] if strada == "forfait" else []), scelta)
        telaio = _telaio(torneo, monkeypatch, finestre)
        # Il giocatore col nero della coppia ancora aperta: con il forfait
        # 1-F e' lui a non essersi presentato.
        chi = torneo["rounds"][1]["matches"][0]["black_player_id"]
        if strada == "canc":
            chi = "G2"
            self._canc(telaio, chi)
        elif strada == "risultato":
            self._dal_risultato(telaio, monkeypatch, chi)
        else:
            self._dopo_il_forfait(telaio)

        titolo, testo, no_predefinito = finestre.aperte[-1]
        assert titolo == "Ritiro con pochi giocatori"
        assert AVVISO_COMUNE in testo
        assert "Il pulsante predefinito e' No." in testo
        assert no_predefinito is True
        assert _ritirati(torneo) == ([chi] if risposta == "si" else [])
        assert telaio.bivi == []

    def test_il_canc_mette_la_domanda_e_l_avviso_in_una_finestra_sola(self, monkeypatch):
        wx = pytest.importorskip("wx")
        torneo = _torneo_in_corso(attivi=4, turni=5)
        finestre = _Finestre(wx.ID_YES)
        telaio = _telaio(torneo, monkeypatch, finestre)

        self._canc(telaio, "G2")

        assert len(finestre.aperte) == 1
        assert "Vuoi ritirarlo dal torneo?" in finestre.aperte[0][1]

    @pytest.mark.parametrize("strada", ["canc", "risultato", "forfait"])
    def test_con_giocatori_a_sufficienza_nessun_avviso(self, strada, monkeypatch):
        wx = pytest.importorskip("wx")
        torneo = _torneo_in_corso(attivi=8, turni=3)
        finestre = _Finestre(wx.ID_YES)
        telaio = _telaio(torneo, monkeypatch, finestre)
        chi = torneo["rounds"][1]["matches"][0]["black_player_id"]
        if strada == "canc":
            chi = "G2"
            self._canc(telaio, chi)
        elif strada == "risultato":
            self._dal_risultato(telaio, monkeypatch, chi)
        else:
            self._dopo_il_forfait(telaio)

        assert all(titolo != "Ritiro con pochi giocatori" for titolo, _t, _n in finestre.aperte)
        assert all(no is False for _t, _testo, no in finestre.aperte)
        assert _ritirati(torneo) == [chi]

    @pytest.mark.parametrize("strada", ["canc", "risultato", "forfait"])
    def test_sotto_i_due_attivi_il_bivio(self, strada, monkeypatch):
        wx = pytest.importorskip("wx")
        torneo = _torneo_in_corso(attivi=2, turni=5)
        finestre = _Finestre(wx.ID_YES)
        telaio = _telaio(torneo, monkeypatch, finestre)
        if strada == "canc":
            # Il canc vuole la partita del turno gia' giocata.
            torneo["rounds"][1]["matches"][0]["result"] = "1/2-1/2"
            self._canc(telaio, "G1")
        elif strada == "risultato":
            self._dal_risultato(telaio, monkeypatch, "G1")
        else:
            self._dopo_il_forfait(telaio)

        assert len(telaio.bivi) == 1
        assert _ritirati(torneo) == []

    def test_con_due_rimasti_l_avviso_dice_un_solo_avversario(self, monkeypatch):
        """Con due giocatori che restano l'avversario possibile e' uno solo,
        e il numero che servirebbe e' di giocatori attivi, non di avversari."""
        wx = pytest.importorskip("wx")
        torneo = _torneo_in_corso(attivi=4, turni=5)
        torneo["players_dict"]["G3"]["withdrawn"] = True
        finestre = _Finestre(wx.ID_NO)
        telaio = _telaio(torneo, monkeypatch, finestre)

        self._canc(telaio, "G2")

        titolo, testo, _no = finestre.aperte[-1]
        assert titolo == "Ritiro con pochi giocatori"
        assert "Fra 2 giocatori c'e' un solo avversario possibile a testa" in testo
        assert "servirebbero almeno 4 giocatori attivi" in testo
        assert "1 avversari" not in testo

    def test_con_piu_rimasti_l_avviso_resta_al_plurale(self, monkeypatch):
        wx = pytest.importorskip("wx")
        torneo = _torneo_in_corso(attivi=4, turni=5)
        finestre = _Finestre(wx.ID_NO)
        telaio = _telaio(torneo, monkeypatch, finestre)

        self._canc(telaio, "G2")

        testo = finestre.aperte[-1][1]
        assert "Fra 3 giocatori ci sono solo 2 avversari possibili a testa" in testo
        assert "servirebbero almeno 4 giocatori attivi" in testo


class TestIlBivioDallaFinestraDelRisultato:
    """Dalla 10.13.1 il bivio si raggiunge anche dal pulsante Ritira
    Giocatore e dalla domanda dopo un forfait, dentro la finestra del
    risultato. Se l'arbitro riporta il torneo all'iscrizione o lo elimina, la
    finestra del risultato non annuncia piu' niente e non mostra la partita,
    che non esiste piu': barra di stato, albero e area centrale restano
    quelli del bivio. Prima della correzione, con il torneo eliminato, la
    finestra si fermava con un errore imprevisto, e con il ritorno
    all'iscrizione la barra di stato diceva Risultato registrato. Il bivio e'
    quello vero; l'eliminazione e la copia di sicurezza sono finte."""

    FASE_DI_ISCRIZIONE = "Torneo riportato alla fase di iscrizione. I turni sono stati cancellati."

    def _risultato(self, monkeypatch, azione, chi=None):
        import wx

        from gui.dialogs import result_dialog

        class Risultato:
            def __init__(self, *a, **k):
                self.selected_action = azione
                self.withdrawn_player_id = chi
                self.txt_pgn = SimpleNamespace(GetValue=lambda: "")

            def ShowModal(self):
                return wx.ID_OK

            def get_selected_result(self):
                return "1-F"

            def Destroy(self):
                pass

        monkeypatch.setattr(result_dialog, "ResultDialog", Risultato)

    def _telaio(self, torneo, monkeypatch, finestre, elimina):
        import gui.main_frame as mf
        import utils

        registro = SimpleNamespace(stati=[], dettagli=[], alberi=[], copie=[])
        monkeypatch.setattr(utils, "create_backup", lambda *a, **k: registro.copie.append(a) or True)

        def set_status(self, testo):
            registro.stati.append(testo)

        def dettaglio(self, *a, **k):
            registro.dettagli.append(a)

        def albero(self):
            registro.alberi.append(True)

        def eliminazione(self, filepath):
            # Come delete_tournament_completely sul torneo aperto, se
            # l'arbitro conferma; altrimenti non succede niente.
            if elimina:
                self.current_tournament = None
                self.active_filename = None
                self.set_status("Torneo eliminato.")

        telaio = _telaio(
            torneo,
            monkeypatch,
            finestre,
            _bivio_torneo_non_proseguibile=mf.MainFrame._bivio_torneo_non_proseguibile,
            _proponi_eliminazione_torneo=eliminazione,
            set_status=set_status,
            show_match_detail_verbose=dettaglio,
            populate_tree=albero,
        )
        return telaio, registro

    def _apri_partita(self, telaio, monkeypatch, strada):
        """La partita ancora aperta del turno 2, fra G1 col bianco e G0 col
        nero: dalla finestra del risultato si ritira G1 con il pulsante,
        oppure si registra 1-F, e dopo il forfait si ritira G0."""
        partita = telaio.current_tournament["rounds"][1]["matches"][0]
        if strada == "risultato":
            self._risultato(monkeypatch, "withdraw", "G1")
        else:
            self._risultato(monkeypatch, None)
        telaio.on_activate_match(partita)

    @pytest.mark.parametrize("strada", ["risultato", "forfait"])
    def test_ritorno_all_iscrizione(self, strada, monkeypatch):
        wx = pytest.importorskip("wx")
        torneo = _torneo_in_corso(attivi=2, turni=5)
        # Dopo il forfait c'e' prima la domanda sul ritiro; poi al bivio Si'
        # riporta il torneo alla fase di iscrizione.
        finestre = _Finestre(*([wx.ID_YES] if strada == "forfait" else []), wx.ID_YES)
        telaio, registro = self._telaio(torneo, monkeypatch, finestre, elimina=False)

        self._apri_partita(telaio, monkeypatch, strada)

        assert finestre.aperte[-1][0] == "Il torneo non potrebbe proseguire"
        # Fra due attivi ne resterebbe uno: fino alla 10.13.5 la frase
        # diceva resterebbero 1 giocatori attivi.
        assert " resterebbe un solo giocatore attivo: con meno di due giocatori" in finestre.aperte[-1][1]
        assert "\n\nIl ritiro non viene registrato" in finestre.aperte[-1][1]
        assert torneo["rounds"] == []
        assert telaio.current_tournament is torneo
        assert registro.stati[-1] == self.FASE_DI_ISCRIZIONE
        assert not any(s.startswith("Risultato registrato") for s in registro.stati)
        assert telaio._tree_restore_target == {"action": "show_players", "filepath": "prova_ritiro.json"}
        assert registro.dettagli == []
        assert len(registro.alberi) == 1
        assert [c[1] for c in registro.copie] == ["pre_ritorno_preparazione"]

    @pytest.mark.parametrize("strada", ["risultato", "forfait"])
    def test_eliminazione(self, strada, monkeypatch):
        wx = pytest.importorskip("wx")
        torneo = _torneo_in_corso(attivi=2, turni=5)
        # Al bivio No, e l'eliminazione viene confermata.
        finestre = _Finestre(*([wx.ID_YES] if strada == "forfait" else []), wx.ID_NO)
        telaio, registro = self._telaio(torneo, monkeypatch, finestre, elimina=True)

        self._apri_partita(telaio, monkeypatch, strada)

        assert telaio.current_tournament is None
        assert registro.stati[-1] == "Torneo eliminato."
        assert registro.dettagli == []
        assert registro.alberi == []

    @pytest.mark.parametrize("strada", ["risultato", "forfait"])
    def test_rifiutate_entrambe_le_strade_la_finestra_prosegue(self, strada, monkeypatch):
        """Con No al bivio e nessuna eliminazione il torneo resta com'era, e
        la finestra del risultato fa quello che faceva: dopo il forfait il
        risultato e' registrato, e l'area centrale mostra la partita."""
        wx = pytest.importorskip("wx")
        torneo = _torneo_in_corso(attivi=2, turni=5)
        finestre = _Finestre(*([wx.ID_YES] if strada == "forfait" else []), wx.ID_NO)
        telaio, registro = self._telaio(torneo, monkeypatch, finestre, elimina=False)

        self._apri_partita(telaio, monkeypatch, strada)

        assert telaio.current_tournament is torneo
        assert len(torneo["rounds"]) == 2
        assert _ritirati(torneo) == []
        assert len(registro.dettagli) == 1
        assert len(registro.alberi) == 1
        if strada == "forfait":
            assert registro.stati[-1] == "Risultato registrato: 1-F."
            assert torneo["rounds"][1]["matches"][0]["result"] == "1-F"
