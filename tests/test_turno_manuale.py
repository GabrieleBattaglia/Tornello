"""La composizione manuale del turno. Issue 38.

Quando bbpPairings risponde che non esiste un abbinamento valido, con il
codice di uscita 1, dalla 10.12.0 l'arbitro compone il turno a mano, e dalla
10.13.0 parte dalla proposta di Tornello. Qui si provano le funzioni senza wx
di turno_manuale.py (validazione, avvertimenti, colori, partite e proposta),
il contrassegno manual_pairing, il motore vero su un girone esaurito e dopo
un turno composto a mano, i metodi della finestra principale su un telaio
finto e la finestra della composizione, costruita e mai mostrata. I tornei
nascono in memoria; i file di lavoro del motore e le copie di sicurezza
finiscono nella cartella temporanea della prova, come vuole conftest.py.
"""

import copy
import io
import itertools
import json
import os
from contextlib import redirect_stdout
from types import SimpleNamespace

import pytest

W, B = "white", "black"
PUNTI = {"1-0": (1.0, 0.0), "0-1": (0.0, 1.0), "1/2-1/2": (0.5, 0.5), "1-F": (1.0, 0.0), "F-1": (0.0, 1.0), "0-0F": (0.0, 0.0)}


def _giocatore(pid, cognome, elo, nome="Test"):
    return {
        "id": pid,
        "first_name": nome,
        "last_name": cognome,
        "initial_elo": elo,
        "points": 0.0,
        "withdrawn": False,
        "results_history": [],
        "sex": "m",
        "federation": "ITA",
    }


def _torneo(giocatori, turni=5, bye=0.5, iniziale="white1"):
    torneo = {
        "name": "Prova manuale",
        "site": "Online",
        "federation_code": "ITA",
        "start_date": "2026-09-01",
        "end_date": "2026-09-30",
        "total_rounds": turni,
        "current_round": 1,
        "next_match_id": 1,
        "chief_arbiter": "A",
        "time_control": "Standard",
        "initial_board1_color_setting": iniziale,
        "bye_value": bye,
        "players": giocatori,
        "rounds": [],
    }
    torneo["players_dict"] = {g["id"]: g for g in giocatori}
    return torneo


def _gioca(torneo, turno, partite, bye=None, manuale=False):
    """Registra un turno intero con i suoi risultati, come fa la finestra:
    partite come (bianco, nero, risultato), bye l'id di chi riposa."""
    from tournament import _apply_match_result_to_players, registra_turno

    elenco = []
    for bianco, nero, _risultato in partite:
        elenco.append({"id": torneo["next_match_id"], "round": turno, "white_player_id": bianco, "black_player_id": nero, "result": None})
        torneo["next_match_id"] += 1
    if bye:
        elenco.append({"id": torneo["next_match_id"], "round": turno, "white_player_id": bye, "black_player_id": None, "result": "BYE"})
        torneo["next_match_id"] += 1
    registra_turno(torneo, elenco, turno, manuale=manuale)
    with redirect_stdout(io.StringIO()):
        for partita, (_b, _n, risultato) in zip(elenco, partite, strict=False):
            _apply_match_result_to_players(torneo, partita, risultato, *PUNTI[risultato])


def _con_colori(giocatore, colori, risultato="1/2-1/2"):
    """Uno storico di partite giocate con i colori dati, W o B, contro
    avversari che non sono nel torneo: mezzo punto a partita."""
    for turno, colore in enumerate(colori, 1):
        giocatore["results_history"].append({"round": turno, "opponent_id": f"X{turno}", "color": colore, "result": risultato, "score": PUNTI[risultato][0 if colore == W else 1]})
    return giocatore


def _torneo_saturo(turni=4):
    """Cinque iscritti; Epsilon riposa al turno 1 e poi si ritira, e i
    quattro rimasti si incontrano tutti fra loro nei turni 1, 2 e 3: al
    turno 4 non resta nessuna coppia nuova. E' il caso della issue."""
    giocatori = [
        _giocatore("A", "Alfa", 1800),
        _giocatore("B", "Beta", 1700),
        _giocatore("C", "Gamma", 1600),
        _giocatore("D", "Delta", 1500),
        _giocatore("E", "Epsilon", 1400),
    ]
    torneo = _torneo(giocatori, turni=turni)
    _gioca(torneo, 1, [("A", "B", "1-0"), ("C", "D", "1/2-1/2")], bye="E")
    torneo["players_dict"]["E"]["withdrawn"] = True
    _gioca(torneo, 2, [("D", "A", "0-1"), ("B", "C", "1-0")])
    _gioca(torneo, 3, [("A", "C", "1/2-1/2"), ("D", "B", "0-1")])
    return torneo


# Coppie valide per tutti gli attivi del torneo saturo, tutte gia' giocate.
TURNO_COMPLETO = [("B", "A"), ("C", "D")]


class TestValidazione:
    """Sono errori soltanto quelli che renderebbero il turno incoerente
    (decisione di Gabriele): tutto il resto e' un avvertimento."""

    def test_un_turno_completo_e_valido(self):
        from turno_manuale import valida_turno_manuale

        errori, avvertimenti = valida_turno_manuale(_torneo_saturo(), TURNO_COMPLETO)

        assert errori == []
        # Tutte e due le coppie si sono gia' incontrate: avvertimenti, non errori.
        assert len(avvertimenti) == 2
        assert all("gia' incontrati al turno" in a for a in avvertimenti)

    @pytest.mark.parametrize(
        ("coppie", "frammento"),
        [
            ([("B", "A")], "Gamma Test non ha ancora una coppia."),
            ([("B", "A"), ("C", "A"), ("D", None)], "Alfa Test compare in piu' di una coppia."),
            ([("B", "A"), ("C", "D"), ("E", None)], "Epsilon Test si e' ritirato"),
            ([("B", "A"), ("C", "Z9")], "Il giocatore Z9 non e' iscritto al torneo."),
            ([("B", "B"), ("A", "C"), ("D", None)], "Beta non puo' giocare contro se stesso."),
            ([("B", "A"), ("C", None), ("D", None)], "un numero pari, nessuno riposa: le coppie hanno 2 bye."),
        ],
    )
    def test_gli_errori_bloccanti(self, coppie, frammento):
        from turno_manuale import valida_turno_manuale

        errori, _avvertimenti = valida_turno_manuale(_torneo_saturo(), coppie)

        assert any(frammento in e for e in errori), errori

    def test_con_i_dispari_serve_un_bye_e_uno_solo(self):
        from turno_manuale import valida_turno_manuale

        torneo = _torneo_saturo()
        torneo["players_dict"]["E"]["withdrawn"] = False
        senza, _a = valida_turno_manuale(torneo, [("B", "A"), ("C", "D"), ("E", "E")])
        due, _a = valida_turno_manuale(torneo, [("B", "A"), ("C", None), ("D", None), ("E", None)])
        giusto, _a = valida_turno_manuale(torneo, [("B", "A"), ("C", "D"), ("E", None)])

        assert any("un numero dispari, uno solo riposa con il bye: le coppie ne hanno 0." in e for e in senza)
        assert any("le coppie ne hanno 3." in e for e in due)
        assert giusto == []


class TestAvvertimenti:
    def _due(self):
        giocatori = [_giocatore("P", "Primo", 1600), _giocatore("S", "Secondo", 1500), _giocatore("T", "Terzo", 1400)]
        return _torneo(giocatori)

    def test_la_coppia_ripetuta_dice_il_turno(self):
        from turno_manuale import avvertimenti_coppia, descrivi_avvertimenti

        torneo = self._due()
        _gioca(torneo, 1, [("P", "S", "1-0")], bye="T")
        _gioca(torneo, 2, [("S", "T", "0-1")], bye="P")
        _gioca(torneo, 3, [("S", "P", "1/2-1/2")], bye="T")

        testi = descrivi_avvertimenti(torneo, avvertimenti_coppia(torneo, "P", "S"))

        assert "gia' incontrati ai turni 1, 3" in testi

    @pytest.mark.parametrize("risultato", ["1-F", "F-1", "0-0F"])
    def test_un_incontro_a_tavolino_non_e_una_ripetizione(self, risultato):
        """C.04.2, articolo 3.5: due giocatori che non hanno giocato possono
        ritrovarsi."""
        from turno_manuale import avvertimenti_coppia

        torneo = self._due()
        _gioca(torneo, 1, [("P", "S", risultato)], bye="T")

        assert [a.tipo for a in avvertimenti_coppia(torneo, "S", "P")] == []

    @pytest.mark.parametrize(
        ("risultato", "colore_di_t", "vietato"),
        [("1-F", W, True), ("F-1", B, True), ("F-1", W, False), ("1-F", B, False), ("0-0F", W, False), ("1-0", W, False)],
    )
    def test_il_bye_a_chi_ha_vinto_a_tavolino(self, risultato, colore_di_t, vietato):
        from turno_manuale import avvertimenti_coppia

        torneo = self._due()
        partita = ("T", "S", risultato) if colore_di_t == W else ("S", "T", risultato)
        _gioca(torneo, 1, [partita], bye="P")

        tipi = [a.tipo for a in avvertimenti_coppia(torneo, "T", None)]
        assert (tipi == ["bye_vietato"]) is vietato

    def test_il_secondo_bye_e_segnalato(self):
        from turno_manuale import avvertimenti_coppia, descrivi_avvertimenti

        torneo = self._due()
        _gioca(torneo, 1, [("P", "S", "1-0")], bye="T")

        testi = descrivi_avvertimenti(torneo, avvertimenti_coppia(torneo, "T", None))
        assert testi == ["Terzo ha gia' avuto un bye o una vittoria a tavolino, al turno 1"]

    def test_il_terzo_bianco_di_fila(self):
        from turno_manuale import avvertimenti_coppia, descrivi_avvertimenti

        torneo = self._due()
        _con_colori(torneo["players"][0], [B, W, W])

        testi = descrivi_avvertimenti(torneo, avvertimenti_coppia(torneo, "P", "S"))
        assert testi == ["Primo al terzo bianco di fila"]
        assert avvertimenti_coppia(torneo, "S", "P") == []

    def test_il_forfait_non_interrompe_la_serie(self):
        """I colori contano solo le partite giocate, come in bbpPairings."""
        from turno_manuale import avvertimenti_coppia

        torneo = self._due()
        primo = _con_colori(torneo["players"][0], [B, W, W])
        primo["results_history"].append({"round": 4, "opponent_id": "X3", "color": B, "result": "F-1", "score": 1.0})

        assert [a.tipo for a in avvertimenti_coppia(torneo, "P", "S")] == ["tre_di_fila"]

    def test_tre_colori_di_differenza(self):
        from turno_manuale import avvertimenti_coppia, descrivi_avvertimenti

        torneo = self._due()
        _con_colori(torneo["players"][1], [B, B, W, B])

        avvisi = avvertimenti_coppia(torneo, "P", "S")
        assert [a.tipo for a in avvisi] == ["squilibrio"]
        assert descrivi_avvertimenti(torneo, avvisi) == ["Secondo con 3 neri piu' dei bianchi"]


class TestColori:
    """Preferenze e colori come li calcola bbpPairings: tournament.cpp per le
    preferenze, common.cpp e dutch.cpp per il colore di una coppia."""

    @pytest.mark.parametrize(
        ("colori", "attesa"),
        [
            ([], (None, None)),
            # Un colore di differenza e' gia' una preferenza forte.
            ([W], (B, "forte")),
            ([W, B], (W, "lieve")),
            ([W, W], (B, "assoluta")),
            ([W, B, W], (B, "forte")),
            ([B, W, W], (B, "assoluta")),
            ([W, W, B, W], (B, "assoluta")),
            ([B, W, B, W], (B, "lieve")),
        ],
    )
    def test_preferenza_colore(self, colori, attesa):
        from turno_manuale import preferenza_colore

        assert preferenza_colore(_con_colori(_giocatore("X", "X", 1500), colori)) == attesa

    def test_i_forfait_non_contano_nei_colori(self):
        from turno_manuale import colori_giocati, preferenza_colore

        # Contando il forfait, i colori sarebbero bianco, nero, bianco, con
        # una preferenza forte per il nero.
        giocatore = _con_colori(_giocatore("X", "X", 1500), [W, B])
        giocatore["results_history"].append({"round": 3, "opponent_id": "Y", "color": W, "result": "1-F", "score": 1.0})
        giocatore["results_history"].append({"round": 4, "opponent_id": "BYE_PLAYER_ID", "color": None, "result": "BYE", "score": 0.5})

        assert colori_giocati(giocatore) == [W, B]
        assert preferenza_colore(giocatore) == (W, "lieve")

    @pytest.mark.parametrize(
        ("colori_a", "colori_b", "bianco"),
        [
            # Preferenze compatibili: ognuno ha la sua.
            ([B], [W], "A"),
            # Chi non ha preferenza lascia la sua all'altro.
            ([W], [], "B"),
            # Stessa preferenza assoluta: vince lo squilibrio piu' grande.
            ([B, B, W, B], [W, B, B], "A"),
            # Assoluta contro forte.
            ([W, W], [W, B, W], "B"),
            # Forte contro lieve.
            ([B, W, B], [W, B], "A"),
            # Due lievi uguali: si alterna rispetto all'ultima partita in cui
            # i colori erano diversi, contando all'indietro.
            ([W, B, B, W], [B, W, B, W], "A"),
        ],
    )
    def test_colore_dalle_preferenze(self, colori_a, colori_b, bianco):
        from turno_manuale import colore_suggerito

        torneo = _torneo([_con_colori(_giocatore("A", "Alfa", 1500), colori_a), _con_colori(_giocatore("B", "Beta", 1600), colori_b)])

        attesa = ("A", "B") if bianco == "A" else ("B", "A")
        assert colore_suggerito(torneo, "A", "B") == attesa
        assert colore_suggerito(torneo, "B", "A") == attesa

    @pytest.mark.parametrize(
        ("iniziale", "coppia", "bianco"),
        [
            # Il meglio piazzato con numero di abbinamento dispari ha il colore
            # iniziale; con numero pari quello opposto.
            ("white1", ("P1", "P3"), "P1"),
            ("black1", ("P1", "P3"), "P3"),
            ("white1", ("P2", "P3"), "P3"),
            ("black1", ("P2", "P4"), "P2"),
        ],
    )
    def test_senza_preferenze_decide_il_rango(self, iniziale, coppia, bianco):
        from turno_manuale import colore_suggerito

        giocatori = [_giocatore(f"P{i}", f"Cognome{i}", 2000 - i * 100) for i in range(1, 5)]
        torneo = _torneo(giocatori, iniziale=iniziale)

        assert colore_suggerito(torneo, *coppia)[0] == bianco

    def test_i_punti_vengono_prima_del_rango(self):
        """Il bye da' punti senza colori: P3 sale sopra P1 e, con il numero
        di abbinamento 3, dispari, prende il colore iniziale."""
        from turno_manuale import colore_suggerito

        giocatori = [_giocatore(f"P{i}", f"Cognome{i}", 2000 - i * 100) for i in range(1, 4)]
        giocatori[2]["results_history"].append({"round": 1, "opponent_id": "BYE_PLAYER_ID", "color": None, "result": "BYE", "score": 0.5})
        torneo = _torneo(giocatori)

        assert colore_suggerito(torneo, "P1", "P3") == ("P3", "P1")

    def test_stessa_preferenza_e_stessa_storia_decide_il_rango(self):
        from turno_manuale import colore_suggerito

        torneo = _torneo([_con_colori(_giocatore("A", "Alfa", 1600), [W]), _con_colori(_giocatore("B", "Beta", 1500), [W])])

        # A e' piu' in alto e tiene la sua preferenza, il nero.
        assert colore_suggerito(torneo, "A", "B") == ("B", "A")

    def test_la_differenza_di_colore_viene_prima_del_rango(self):
        """Stessa preferenza lieve e stessi punti: decide l'ultima partita in
        cui i due avevano colori diversi, anche se A e' piu' in alto e per
        rango terrebbe il suo nero."""
        from turno_manuale import colore_suggerito

        torneo = _torneo([_con_colori(_giocatore("A", "Alfa", 1700), [W, B, B, W]), _con_colori(_giocatore("B", "Beta", 1500), [B, W, B, W])])

        assert colore_suggerito(torneo, "A", "B") == ("A", "B")
        assert colore_suggerito(torneo, "B", "A") == ("A", "B")

    def test_il_bye_non_ha_colori(self):
        from turno_manuale import colore_suggerito

        assert colore_suggerito(_torneo([_giocatore("A", "Alfa", 1500)]), "A", None) == ("A", None)


def _ascid_al_turno(sample, turno):
    """Il torneo archiviato ASCId Primavera 1 com'era prima di abbinare il
    turno dato: storico, turni e ritiri tagliati."""
    torneo = copy.deepcopy(sample)
    torneo["rounds"] = [r for r in torneo["rounds"] if r["round"] < turno]
    for giocatore in torneo["players"]:
        ultimo = max([v["round"] for v in giocatore["results_history"]] or [0])
        giocatore["results_history"] = [v for v in giocatore["results_history"] if v["round"] < turno]
        if giocatore.get("withdrawn") and ultimo >= turno:
            giocatore["withdrawn"] = False
        giocatore["opponents"] = set(giocatore.get("opponents", []))
    torneo["current_round"] = max(turno - 1, 1)
    torneo["concluded"] = False
    torneo["next_match_id"] = 1 + max([m["id"] for r in torneo["rounds"] for m in r["matches"]] or [0])
    torneo["players_dict"] = {p["id"]: p for p in torneo["players"]}
    return torneo


class TestColoriComeIlMotore:
    @pytest.mark.parametrize("turno", [2, 3, 4, 5])
    def test_i_colori_suggeriti_sono_quelli_di_bbppairings(self, sample_tournament_dict, turno):
        """Sul torneo archiviato, con un ritirato e un forfait al turno 4,
        ogni coppia che il motore vero abbina riceve da colore_suggerito gli
        stessi colori, in qualunque ordine si passino i due giocatori."""
        from tournament import generate_pairings_for_round
        from turno_manuale import colore_suggerito

        torneo = _ascid_al_turno(sample_tournament_dict, turno)
        torneo["current_round"] = turno
        with redirect_stdout(io.StringIO()):
            partite = generate_pairings_for_round(torneo)

        assert partite
        coppie = [(m["white_player_id"], m["black_player_id"]) for m in partite if m["black_player_id"]]
        for bianco, nero in coppie:
            assert colore_suggerito(torneo, nero, bianco) == (bianco, nero)
            assert colore_suggerito(torneo, bianco, nero) == (bianco, nero)

    @pytest.mark.parametrize("iniziale", ["white1", "black1"])
    def test_il_numero_di_abbinamento_conta_i_ritirati_che_hanno_giocato(self, iniziale):
        """Senza partite giocate decide il numero di abbinamento, e
        bbpPairings conta anche chi si e' ritirato dopo aver giocato: qui P1,
        davanti a tutti. Al turno 1 P3 e P6 hanno vinto a tavolino, senza
        colori, e al turno 2 il motore li abbina fra loro."""
        from turno_manuale import colore_suggerito

        giocatori = [_giocatore(f"P{i}", f"Cognome{i}", 2100 - i * 100) for i in range(1, 7)]
        torneo = _torneo(giocatori, iniziale=iniziale)
        _gioca(torneo, 1, [("P1", "P2", "1-0"), ("P3", "P4", "1-F"), ("P5", "P6", "F-1")])
        torneo["players_dict"]["P1"]["withdrawn"] = True
        torneo["current_round"] = 2

        partite = _genera(torneo)

        coppie = [(m["white_player_id"], m["black_player_id"]) for m in partite if m["black_player_id"]]
        assert {"P3", "P6"} in [set(c) for c in coppie]
        for bianco, nero in coppie:
            assert colore_suggerito(torneo, nero, bianco) == (bianco, nero)
            assert colore_suggerito(torneo, bianco, nero) == (bianco, nero)


class TestPartite:
    def test_forma_numeri_e_scacchiere(self):
        from models import Match
        from turno_manuale import crea_partite_turno_manuale

        torneo = _torneo_saturo()
        torneo["players_dict"]["E"]["withdrawn"] = False
        prima = torneo["next_match_id"]

        partite = crea_partite_turno_manuale(torneo, [("E", None), ("C", "D"), ("B", "A")], 4)

        # A ha 2,5 punti: la sua coppia va in prima scacchiera, il bye in fondo.
        assert [(p["white_player_id"], p["black_player_id"], p["result"]) for p in partite] == [("B", "A", None), ("C", "D", None), ("E", None, "BYE")]
        assert [p["id"] for p in partite] == [prima, prima + 1, prima + 2]
        assert torneo["next_match_id"] == prima + 3
        assert all(set(p) == {"id", "round", "white_player_id", "black_player_id", "result"} and p["round"] == 4 for p in partite)
        assert [Match.from_dict(p).to_dict()["id"] for p in partite] == [p["id"] for p in partite]

    def test_a_pari_punti_decide_la_somma_poi_lo_start_rank(self):
        from turno_manuale import ordina_coppie

        giocatori = [_giocatore(f"P{i}", f"Cognome{i}", 2000 - i * 100) for i in range(1, 7)]
        torneo = _torneo(giocatori)
        for pid, punti in (("P1", 1.0), ("P2", 1.0), ("P5", 1.0), ("P6", 0.5)):
            torneo["players_dict"][pid]["results_history"].append({"round": 1, "opponent_id": "X", "color": W, "result": "1-0", "score": punti})

        ordinate = ordina_coppie(torneo, [("P3", "P4"), ("P6", "P5"), ("P1", "P4"), ("P2", "P3")])

        assert ordinate == [("P6", "P5"), ("P1", "P4"), ("P2", "P3"), ("P3", "P4")]

    def test_conta_lo_start_rank_del_piu_alto_in_classifica(self):
        """A pari punteggio del primo e a pari somma conta lo start rank del
        giocatore piu' alto in classifica della coppia, cioe' di quello con
        piu' punti, come in sortResults di bbpPairings: non il migliore
        start rank dei due. P1 e' il primo dello start rank, ma nella sua
        coppia il piu' alto in classifica e' P5, che viene dopo P3."""
        from turno_manuale import ordina_coppie

        giocatori = [_giocatore(f"P{i}", f"Cognome{i}", 2000 - i * 100) for i in range(1, 9)]
        torneo = _torneo(giocatori)
        for pid, punti in (("P5", 2.0), ("P1", 1.5), ("P3", 2.0), ("P8", 1.5)):
            torneo["players_dict"][pid]["results_history"].append({"round": 1, "opponent_id": "X", "color": W, "result": "1-0", "score": punti})

        assert ordina_coppie(torneo, [("P5", "P1"), ("P3", "P8")]) == [("P3", "P8"), ("P5", "P1")]
        assert ordina_coppie(torneo, [("P1", "P5"), ("P8", "P3")]) == [("P8", "P3"), ("P1", "P5")]

    def test_a_pari_punti_nella_coppia_conta_il_migliore_start_rank(self):
        from turno_manuale import ordina_coppie

        giocatori = [_giocatore(f"P{i}", f"Cognome{i}", 2000 - i * 100) for i in range(1, 7)]
        torneo = _torneo(giocatori)

        assert ordina_coppie(torneo, [("P6", "P3"), ("P2", "P5")]) == [("P2", "P5"), ("P6", "P3")]


class TestTurnoRegistrato:
    def test_il_turno_manuale_ha_il_contrassegno(self):
        from tournament import registra_turno

        torneo = _torneo_saturo()
        turno = registra_turno(torneo, [{"id": 9, "round": 4, "white_player_id": "B", "black_player_id": "A", "result": None}], 4, manuale=True)

        assert turno["manual_pairing"] is True
        assert torneo["current_round"] == 4
        assert "manual_pairing" not in torneo["rounds"][0]

    def test_il_bye_assegnato_a_mano_da_punti_e_storico(self):
        from tournament import registra_turno
        from turno_manuale import crea_partite_turno_manuale

        torneo = _torneo_saturo()
        torneo["players_dict"]["E"]["withdrawn"] = False
        epsilon = torneo["players_dict"]["E"]
        punti_prima = epsilon["points"]

        registra_turno(torneo, crea_partite_turno_manuale(torneo, [("B", "A"), ("C", "D"), ("E", None)], 4), 4, manuale=True)

        assert epsilon["points"] == punti_prima + 0.5
        assert epsilon["results_history"][-1] == {"round": 4, "opponent_id": "BYE_PLAYER_ID", "color": None, "result": "BYE", "score": 0.5}

    def test_l_esito_del_fallimento_non_finisce_nel_json(self, tmp_path):
        from tournament import _abbinamento_fallito, abbinamento_esaurito, pulisci_esito_abbinamento, save_tournament

        torneo = _torneo_saturo()
        _abbinamento_fallito(torneo, "motivo", esaurito=True)
        assert abbinamento_esaurito(torneo)
        percorso = tmp_path / "Tornello - Prova manuale.json"

        assert save_tournament(torneo, filepath=str(percorso))

        dati = json.loads(percorso.read_text(encoding="utf-8"))
        assert "_errore_abbinamento" not in dati
        assert "_abbinamento_esaurito" not in dati
        # In memoria restano, finche' un turno non viene registrato.
        assert abbinamento_esaurito(torneo)
        pulisci_esito_abbinamento(torneo)
        assert not abbinamento_esaurito(torneo)


def _genera(torneo):
    from tournament import generate_pairings_for_round

    with redirect_stdout(io.StringIO()):
        return generate_pairings_for_round(torneo)


class TestMotoreVero:
    """Con il vero bbpPairings.exe, come test_e2e.py."""

    def test_il_girone_esaurito_restituisce_il_codice_1(self):
        from tournament import abbinamento_esaurito, motivo_ultimo_fallimento

        torneo = _torneo_saturo()
        torneo["current_round"] = 4

        assert _genera(torneo) is None
        assert abbinamento_esaurito(torneo)
        assert "nessun" in motivo_ultimo_fallimento(torneo) or "alcun" in motivo_ultimo_fallimento(torneo)

    def test_un_altro_errore_non_e_un_esaurimento(self, tmp_path, monkeypatch):
        import engine
        from tournament import abbinamento_esaurito

        monkeypatch.setattr(engine, "BBP_EXE_PATH", str(tmp_path / "assente.exe"))
        torneo = _torneo_saturo()
        torneo["current_round"] = 4

        assert _genera(torneo) is None
        assert not abbinamento_esaurito(torneo)

    def test_dopo_un_turno_manuale_ripetuto_il_motore_accetta_il_trf(self):
        """Il turno 4 composto a mano ripete due incontri; al turno 5 il
        motore puo' non trovare abbinamenti, ma non rifiuta il file."""
        from tournament import abbinamento_esaurito, motivo_ultimo_fallimento
        from turno_manuale import proposta_abbinamento

        torneo = _torneo_saturo(turni=5)
        proposta = proposta_abbinamento(torneo)
        assert proposta == [("B", "A"), ("C", "D")]
        _gioca(torneo, 4, [("B", "A", "0-1"), ("C", "D", "1/2-1/2")], manuale=True)
        torneo["current_round"] = 5

        esito = _genera(torneo)

        motivo = motivo_ultimo_fallimento(torneo) or ""
        assert esito is not None or abbinamento_esaurito(torneo), motivo
        assert "does not match" not in motivo and "contradicts" not in motivo

    def test_otto_giocatori_abbinati_davvero_dopo_il_turno_manuale(self):
        from tournament import registra_turno
        from turno_manuale import valida_turno_manuale

        torneo = _torneo([_giocatore(f"G{i}", f"Cognome{i}", 2100 - i * 50) for i in range(1, 9)])
        primo = _genera(torneo)
        registra_turno(torneo, primo, 1)
        with redirect_stdout(io.StringIO()):
            from tournament import _apply_match_result_to_players

            for partita in torneo["rounds"][0]["matches"]:
                _apply_match_result_to_players(torneo, partita, "1-0", 1.0, 0.0)
        coppie = [(m["white_player_id"], m["black_player_id"]) for m in torneo["rounds"][0]["matches"]]
        (x1, y1), (x2, y2), (x3, y3), (x4, y4) = coppie
        # Il turno 2 ripete la prima scacchiera, a colori invertiti.
        manuale = [(y1, x1), (x2, x3), (y2, x4), (y3, y4)]
        errori, avvertimenti = valida_turno_manuale(torneo, manuale)
        assert errori == []
        assert len(avvertimenti) == 1
        _gioca(torneo, 2, [(b, n, "1/2-1/2") for b, n in manuale], manuale=True)
        torneo["current_round"] = 3

        terzo = _genera(torneo)

        assert terzo is not None and len(terzo) == 4
        gia_giocate = {frozenset(c) for c in coppie + manuale}
        assert all(frozenset((m["white_player_id"], m["black_player_id"])) not in gia_giocate for m in terzo)


class TestScacchiereComeIlMotore:
    """Le scacchiere del turno composto a mano seguono l'ordine in cui
    bbpPairings scrive le sue: le coppie del motore vero, rimesse in ordine
    da ordina_coppie, restano dove le ha messe il motore."""

    def test_conta_il_piu_alto_in_classifica_della_coppia(self):
        """Dieci giocatori, dopo il primo turno: al turno 2 il motore mette
        P4 contro P3 prima di P8 contro P1, perche' conta lo start rank del
        piu' alto in classifica della coppia, P3 con mezzo punto, e non
        quello di P1, che ha lo start rank migliore di tutti ma zero punti."""
        from turno_manuale import ordina_coppie

        torneo = _torneo([_giocatore(f"P{i}", f"Cognome{i}", 2000 - i * 50) for i in range(1, 11)])
        _gioca(torneo, 1, [("P1", "P6", "0-1"), ("P7", "P2", "0-1"), ("P3", "P8", "1/2-1/2"), ("P9", "P4", "1-0"), ("P5", "P10", "1-0")])
        torneo["current_round"] = 2

        coppie = [(m["white_player_id"], m["black_player_id"]) for m in _genera(torneo)]

        assert coppie.index(("P4", "P3")) < coppie.index(("P8", "P1"))
        assert ordina_coppie(torneo, coppie) == coppie
        assert ordina_coppie(torneo, coppie[::-1]) == coppie

    @pytest.mark.parametrize("turno", [2, 3, 4, 5])
    def test_sul_torneo_archiviato(self, sample_tournament_dict, turno):
        from turno_manuale import ordina_coppie

        torneo = _ascid_al_turno(sample_tournament_dict, turno)
        torneo["current_round"] = turno

        coppie = [(m["white_player_id"], m["black_player_id"]) for m in _genera(torneo)]

        assert ordina_coppie(torneo, coppie) == coppie
        assert ordina_coppie(torneo, coppie[::-1]) == coppie


def _tutti_gli_abbinamenti(nodi):
    if not nodi:
        yield []
        return
    primo, resto = nodi[0], nodi[1:]
    for i, altro in enumerate(resto):
        for seguito in _tutti_gli_abbinamenti(resto[:i] + resto[i + 1 :]):
            yield [(primo, altro), *seguito]


class TestProposta:
    def test_e_la_migliore_fra_tutte(self, sample_tournament_dict):
        """Con sette giocatori attivi del torneo archiviato al turno 4, il
        costo della proposta e' il minimo fra tutti i centocinque abbinamenti
        possibili, bye compreso, provati uno per uno."""
        from turno_manuale import colore_suggerito, costo_coppia, proposta_abbinamento

        torneo = _ascid_al_turno(sample_tournament_dict, 4)
        scelti = {p["id"] for p in torneo["players"][:7]}
        for giocatore in torneo["players"]:
            giocatore["withdrawn"] = giocatore["id"] not in scelti

        def costo(coppie):
            totale = (0, 0, 0, 0)
            for a, b in coppie:
                parziale = costo_coppia(torneo, *colore_suggerito(torneo, a, b))
                totale = tuple(x + y for x, y in zip(totale, parziale, strict=True))
            return totale

        attivi = sorted(scelti)
        migliore = min(costo(c) for c in _tutti_gli_abbinamenti([*attivi, None]))
        proposta = proposta_abbinamento(torneo)

        assert len(proposta) == 4
        assert sum(1 for _b, n in proposta if n is None) == 1
        assert costo(proposta) == migliore

    def test_riposa_chi_ha_meno_punti_e_non_ha_gia_riposato(self):
        from turno_manuale import proposta_abbinamento

        giocatori = [_giocatore(f"P{i}", f"Cognome{i}", 2000 - i * 100) for i in range(1, 6)]
        torneo = _torneo(giocatori)
        _gioca(torneo, 1, [("P1", "P3", "1-0"), ("P2", "P4", "1-0")], bye="P5")

        proposta = proposta_abbinamento(torneo)

        # P5 ha mezzo punto dal bye: riposa uno dei due a zero, P3 o P4.
        assert proposta[-1][1] is None
        assert proposta[-1][0] in ("P3", "P4")

    def test_oltre_sedici_attivi_nessuna_proposta(self):
        from turno_manuale import MASSIMO_PER_LA_PROPOSTA, proposta_abbinamento, righe_della_situazione

        torneo = _torneo([_giocatore(f"G{i}", f"C{i}", 2000 - i) for i in range(MASSIMO_PER_LA_PROPOSTA + 1)])

        assert proposta_abbinamento(torneo) is None
        assert "Proposta solo fino a 16 attivi" in righe_della_situazione(torneo, [], 1)

    def test_sedici_attivi_hanno_la_proposta(self, sample_tournament_dict):
        from turno_manuale import proposta_abbinamento, valida_turno_manuale

        torneo = _ascid_al_turno(sample_tournament_dict, 5)
        for posizione, giocatore in enumerate(torneo["players"]):
            giocatore["withdrawn"] = posizione >= 16

        proposta = proposta_abbinamento(torneo)

        assert len(proposta) == 8
        assert valida_turno_manuale(torneo, proposta)[0] == []


class TestTestiDellaFinestra:
    def test_le_righe_della_situazione_stanno_nei_quaranta_caratteri(self):
        from turno_manuale import righe_della_situazione

        righe = righe_della_situazione(_torneo_saturo(), [("B", "A")], 4)

        assert righe[:4] == ["Turno 4 di 4, a mano", "Attivi 4, da abbinare 2", "Partite 1, bye 0 di 0", "Avvertimenti 1"]
        assert all(len(r) <= 40 for r in righe)

    def test_le_voci_delle_liste(self):
        from turno_manuale import voce_avversario, voce_coppia, voce_giocatore

        torneo = _torneo_saturo()

        assert voce_giocatore(torneo, "C") == "Gamma Test, 1 punto, colori B N N, preferenza B assoluta"
        assert voce_avversario(torneo, "A", "B") == "Beta Test, 2 punti, bianco a Beta, gia' incontrati al turno 1"
        assert voce_coppia(torneo, 2, "C", "D") == "Scacchiera 2: Gamma Test (B) contro Delta Test (N), gia' incontrati al turno 1"
        torneo["players_dict"]["E"]["withdrawn"] = False
        assert voce_avversario(torneo, "E", None) == "Riposo (bye), Epsilon ha gia' avuto un bye o una vittoria a tavolino, al turno 1"

    def test_giocatori_da_abbinare_e_avversari(self):
        """Le regole delle due liste stanno in turno_manuale, senza wx: chi
        e' ancora da abbinare, nell'ordine dei punti, e quali avversari
        restano al giocatore scelto, con il riposo in fondo solo quando gli
        attivi sono dispari e nessuno riposa ancora."""
        from turno_manuale import avversari_possibili, giocatori_da_abbinare

        torneo = _torneo_saturo()
        assert giocatori_da_abbinare(torneo, []) == ["A", "B", "C", "D"]
        assert giocatori_da_abbinare(torneo, [("B", "A")]) == ["C", "D"]
        assert avversari_possibili(torneo, [("B", "A")], "C") == ["D"]

        torneo["players_dict"]["E"]["withdrawn"] = False
        assert giocatori_da_abbinare(torneo, [("B", "A")]) == ["C", "D", "E"]
        assert avversari_possibili(torneo, [("B", "A")], "C") == ["D", "E", None]
        assert avversari_possibili(torneo, [("B", "A"), ("E", None)], "C") == ["D"]

    def test_il_riepilogo_conta_come_la_situazione(self):
        """Il campo Situazione e il riepilogo della conferma danno lo stesso
        numero di avvertimenti, contati uno per uno: la seconda scacchiera,
        gia' giocata e con due terzi colori di fila, ne ha tre."""
        from turno_manuale import righe_della_conferma, righe_della_situazione

        torneo = _torneo_saturo()
        coppie = [("B", "A"), ("D", "C")]

        situazione = righe_della_situazione(torneo, coppie, 4)
        conferma = righe_della_conferma(torneo, coppie, 4)

        assert situazione[3] == "Avvertimenti 4"
        assert conferma[:2] == ["Registrare il turno 4 composto a mano, con 2 partite?", "Avvertimenti: 4, su 2 scacchiere."]
        assert conferma[3] == "Scacchiera 2, Delta Test contro Gamma Test: gia' incontrati al turno 1, Delta al terzo bianco di fila, Gamma al terzo nero di fila."
        assert conferma[-1].endswith("Il pulsante predefinito e' No.")

    def test_il_riepilogo_al_singolare(self):
        """Con tre attivi la partita e' una sola; con un avvertimento solo
        la scacchiera e' una."""
        from turno_manuale import righe_della_conferma

        tre = _torneo([_giocatore(f"P{i}", f"Cognome{i}", 2000 - i * 100) for i in range(1, 4)])
        _gioca(tre, 1, [("P1", "P2", "1-0")], bye="P3")
        assert righe_della_conferma(tre, [("P3", "P1"), ("P2", None)], 2)[:2] == ["Registrare il turno 2 composto a mano, con una partita?", "Nessun avvertimento."]

        cinque = _torneo([_giocatore(f"P{i}", f"Cognome{i}", 2000 - i * 100) for i in range(1, 6)])
        _gioca(cinque, 1, [("P1", "P2", "1-0"), ("P3", "P4", "1-0")], bye="P5")
        conferma = righe_della_conferma(cinque, [("P2", "P1"), ("P3", "P5"), ("P4", None)], 2)
        assert conferma[:2] == ["Registrare il turno 2 composto a mano, con 2 partite?", "Avvertimenti: 1, su una scacchiera."]
        assert len(conferma) == 4


class TestReport:
    """Il turno composto a mano lo dicono il report del turno e il file dei
    Dettagli del turno concluso; i turni del motore no."""

    def test_il_report_del_turno(self):
        from reports import get_current_round_report_text

        torneo = _torneo_saturo()
        _gioca(torneo, 4, [("B", "A", "0-1"), ("C", "D", "1-0")], manuale=True)

        assert " Abbinamenti composti a mano dall'arbitro\n" in get_current_round_report_text(torneo, 4)
        assert "composti a mano" not in get_current_round_report_text(torneo, 3)

    def test_il_file_dei_dettagli(self, tmp_path):
        from reports import append_completed_round_to_history_file

        torneo = _torneo_saturo()
        torneo["custom_save_path"] = str(tmp_path)
        _gioca(torneo, 4, [("B", "A", "0-1"), ("C", "D", "1-0")], manuale=True)

        with redirect_stdout(io.StringIO()):
            append_completed_round_to_history_file(torneo, 4)
            append_completed_round_to_history_file(torneo, 3)

        manuale = (tmp_path / "Tornello - Prova_manuale - Turno 4 Dettagli.txt").read_text(encoding="utf-8-sig")
        del_motore = (tmp_path / "Tornello - Prova_manuale - Turno 3 Dettagli.txt").read_text(encoding="utf-8-sig")
        assert "\tAbbinamenti composti a mano dall'arbitro\n" in manuale
        assert "composti a mano" not in del_motore


def test_la_console_rimanda_alla_finestra(monkeypatch):
    """Dalla 10.13.3 la versione a riga di comando distingue l'esaurimento
    delle coppie dall'errore di formato, e rimanda alla finestra."""
    import engine

    wx = pytest.importorskip("wx")
    monkeypatch.setattr(wx, "GetApp", lambda: None)
    monkeypatch.setattr(engine, "key", lambda prompt: "u")

    uscita = io.StringIO()
    with redirect_stdout(uscita):
        assert engine.handle_bbpairings_failure({}, 4, "nessun abbinamento", esaurito=True) == "terminate"
    esaurito = uscita.getvalue()
    uscita = io.StringIO()
    with redirect_stdout(uscita):
        engine.handle_bbpairings_failure({}, 4, "file rifiutato")
    formato = uscita.getvalue()

    assert "senza l'opzione --cli" in esaurito and "errori di formato" not in esaurito
    assert "errori di formato" in formato and "--cli" not in formato


# I metodi della finestra principale, su un telaio finto: niente finestre,
# niente suoni, i salvataggi annotati.


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
                registro.aperte.append(SimpleNamespace(titolo=title, testo=message, no_predefinito=no_predefinito))
                return registro.risposte.pop(0) if registro.risposte else wx.ID_OK

            def Destroy(self):
                pass

        return Finta()


def _telaio(torneo, percorso, **altri):
    from gui.main_frame import MainFrame

    class Telaio:
        generate_next_round = MainFrame.generate_next_round
        start_tournament_matchmaking = MainFrame.start_tournament_matchmaking
        _registra_nuovo_turno = MainFrame._registra_nuovo_turno
        _registra_turno_manuale = MainFrame._registra_turno_manuale
        _proponi_abbinamento_manuale = MainFrame._proponi_abbinamento_manuale
        _dialogo_informativo = MainFrame._dialogo_informativo

        def __init__(self):
            self.current_tournament = torneo
            self.active_filename = str(percorso)
            self.settings = {}
            self.salvataggi = 0
            self.stato = None
            self.chiamate = []

        def _torneo_puo_partire(self, torneo):
            return True

        def _save_state(self):
            self.salvataggi += 1

        def populate_tree(self):
            pass

        def show_current_round_report(self):
            pass

        def set_status(self, testo):
            self.stato = testo

        def _avvisa_abbinamento_fallito(self, torneo):
            self.chiamate.append("avviso")

    for nome, valore in altri.items():
        setattr(Telaio, nome, valore)
    return Telaio()


@pytest.fixture
def muto(monkeypatch):
    import utils

    suoni = []
    monkeypatch.setattr(utils, "play_sound", lambda evento, *a, **k: suoni.append(evento))
    return suoni


class TestFinestraPrincipale:
    def test_l_esaurimento_propone_la_composizione_manuale(self, tmp_path, muto):
        pytest.importorskip("wx")
        torneo = _torneo_saturo()
        telaio = _telaio(torneo, tmp_path / "t.json", _proponi_abbinamento_manuale=lambda self, numero: self.chiamate.append(("manuale", numero)))

        telaio.generate_next_round()

        assert telaio.chiamate == [("manuale", 4)]
        assert torneo["current_round"] == 3
        assert len(torneo["rounds"]) == 3

    def test_gli_altri_errori_restano_un_avviso(self, tmp_path, muto, monkeypatch):
        pytest.importorskip("wx")
        import engine

        monkeypatch.setattr(engine, "BBP_EXE_PATH", str(tmp_path / "assente.exe"))
        torneo = _torneo_saturo()
        telaio = _telaio(torneo, tmp_path / "t.json", _proponi_abbinamento_manuale=lambda self, numero: self.chiamate.append(("manuale", numero)))

        telaio.generate_next_round()

        assert telaio.chiamate == ["avviso"]

    def _su_disco(self, tmp_path, torneo):
        from tournament import save_tournament

        percorso = tmp_path / "Tornello - Prova manuale.json"
        assert save_tournament(torneo, filepath=str(percorso))
        return percorso

    def test_la_composizione_confermata_registra_il_turno(self, tmp_path, muto, monkeypatch):
        wx = pytest.importorskip("wx")
        import gui.main_frame as mf
        from gui.dialogs import manual_pairing_dialog
        from tournament import _abbinamento_fallito

        torneo = _torneo_saturo()
        torneo["current_round"] = 3
        percorso = self._su_disco(tmp_path, torneo)
        finestre = _Finestre(wx.ID_YES)
        monkeypatch.setattr(mf, "AccessibleMsgDialog", finestre)

        class Composizione:
            def __init__(self, parent, t, turno, settings):
                assert (t, turno) == (torneo, 4)
                self.coppie_confermate = [("C", "D"), ("B", "A")]

            def ShowModal(self):
                return wx.ID_OK

            def Destroy(self):
                pass

        monkeypatch.setattr(manual_pairing_dialog, "ManualPairingDialog", Composizione)
        telaio = _telaio(torneo, percorso)
        _abbinamento_fallito(torneo, "motivo", esaurito=True)

        telaio._proponi_abbinamento_manuale(4)

        assert finestre.aperte[0].titolo == "Nessun abbinamento valido"
        assert "C.04.3, articolo 1.9.3" in finestre.aperte[0].testo
        turno = torneo["rounds"][-1]
        assert turno["manual_pairing"] is True
        assert [(m["white_player_id"], m["black_player_id"]) for m in turno["matches"]] == [("B", "A"), ("C", "D")]
        assert torneo["current_round"] == 4
        assert "_errore_abbinamento" not in torneo and "_abbinamento_esaurito" not in torneo
        assert telaio.salvataggi == 1
        assert muto[-1] == "nuovo_turno"
        assert telaio.stato == "Registrati gli abbinamenti composti a mano del Turno 4."
        copie = [n for _r, _c, files in os.walk(tmp_path / "backup") for n in files]
        assert any("pre_turno_manuale" in n for n in copie), copie

    def test_rispondendo_no_non_cambia_niente(self, tmp_path, muto, monkeypatch):
        wx = pytest.importorskip("wx")
        import gui.main_frame as mf

        torneo = _torneo_saturo()
        torneo["current_round"] = 3
        prima = copy.deepcopy(torneo["rounds"])
        monkeypatch.setattr(mf, "AccessibleMsgDialog", _Finestre(wx.ID_NO))
        telaio = _telaio(torneo, tmp_path / "t.json")

        telaio._proponi_abbinamento_manuale(4)

        assert torneo["rounds"] == prima
        assert telaio.salvataggi == 0


class TestNonRegressione:
    """Il riordino di generate_next_round e start_tournament_matchmaking non
    cambia il turno che il motore genera: sul torneo archiviato ASCId
    Primavera 1, per ogni turno, il turno registrato dalla finestra e' quello
    che la ricetta di prima della 10.12.0 produceva, cioe'
    registra_bye_del_turno e poi Round(...).to_dict(). Il banco dello
    scratchpad, banco38_regressione.py, ha confrontato anche i sorgenti di
    prima e di dopo, con file identici."""

    @pytest.mark.parametrize("turno", [1, 2, 3, 4, 5])
    def test_il_turno_del_motore_resta_identico(self, sample_tournament_dict, turno, tmp_path, muto):
        pytest.importorskip("wx")
        from models import Match, Round
        from tournament import registra_bye_del_turno

        atteso = _ascid_al_turno(sample_tournament_dict, turno)
        atteso["current_round"] = turno
        partite = _genera(atteso)
        registra_bye_del_turno(atteso, partite, turno)
        atteso.setdefault("rounds", []).append(Round(round=turno, matches=[Match.from_dict(m) for m in partite]).to_dict())

        torneo = _ascid_al_turno(sample_tournament_dict, turno)
        telaio = _telaio(torneo, tmp_path / "t.json")
        with redirect_stdout(io.StringIO()):
            if turno == 1:
                telaio.start_tournament_matchmaking()
            else:
                telaio.generate_next_round()

        assert torneo["rounds"] == atteso["rounds"]
        assert "manual_pairing" not in torneo["rounds"][-1]
        assert torneo["next_match_id"] == atteso["next_match_id"]
        for giocatore in torneo["players"]:
            gemello = atteso["players_dict"][giocatore["id"]]
            assert giocatore["results_history"] == gemello["results_history"]
            assert giocatore["points"] == gemello["points"]
        assert telaio.salvataggi == 1
        assert muto == ["nuovo_turno"]


# La finestra, costruita e mai mostrata.


@pytest.fixture
def finestra(app_grafica, monkeypatch):
    import wx

    from gui.dialogs import manual_pairing_dialog

    suoni = []
    monkeypatch.setattr(manual_pairing_dialog, "play_sound", lambda evento, *a, **k: suoni.append(evento))
    domande = []
    aperte = []

    def crea(torneo, turno=4, risposta=True):
        dlg = manual_pairing_dialog.ManualPairingDialog(None, torneo, turno, {})
        dlg._domanda = lambda titolo, testo: domande.append((titolo, testo)) or risposta
        dlg._messaggio = lambda titolo, testo: domande.append((titolo, testo))
        dlg.EndModal = lambda codice: suoni.append(f"fine {codice}")
        aperte.append(dlg)
        return dlg

    yield SimpleNamespace(crea=crea, suoni=suoni, domande=domande, wx=wx)
    for dlg in aperte:
        dlg.Destroy()


def _tasto(codice):
    return SimpleNamespace(GetKeyCode=lambda: codice, Skip=lambda: None)


class TestFinestraDellaComposizione:
    def test_si_apre_con_la_proposta(self, finestra):
        dlg = finestra.crea(_torneo_saturo())

        assert dlg.coppie == [("B", "A"), ("C", "D")]
        assert dlg.lista_coppie.GetCount() == 2
        assert dlg.lista_coppie.GetString(0).startswith("Scacchiera 1: Beta Test (B) contro Alfa Test (N), gia' incontrati al turno 1")
        assert dlg.lista_liberi.GetCount() == 0
        assert dlg.btn_conferma.IsEnabled()
        assert dlg.situazione.GetValue().splitlines()[0] == "Turno 4 di 4, a mano"
        assert finestra.suoni == []

    def test_togli_scegli_aggiungi_e_inverti(self, finestra):
        wx = finestra.wx
        dlg = finestra.crea(_torneo_saturo())

        dlg.lista_coppie.SetSelection(0)
        dlg.on_tasto_coppie(_tasto(wx.WXK_DELETE))
        assert finestra.suoni == ["coppia_tolta"]
        assert dlg.coppie == [("C", "D")]
        assert not dlg.btn_conferma.IsEnabled()
        assert [dlg.lista_liberi.GetString(i).split(",")[0] for i in range(dlg.lista_liberi.GetCount())] == ["Alfa Test", "Beta Test"]

        # Scelto Alfa, l'avversario e' Beta, e il bianco suggerito va a Beta.
        dlg.lista_liberi.SetSelection(0)
        dlg.on_giocatore_scelto(SimpleNamespace(Skip=lambda: None))
        assert dlg.lista_avversari.GetCount() == 1
        assert "gia' incontrati al turno 1" in dlg.lista_avversari.GetString(0)
        assert dlg.scelta_bianco.GetStringSelection() == "Beta Test (suggerito)"

        dlg.on_tasto_avversari(_tasto(wx.WXK_RETURN))
        assert finestra.suoni[-1] == "coppia_avvertimento"
        assert dlg.coppie == [("B", "A"), ("C", "D")]
        assert dlg.btn_conferma.IsEnabled()

        dlg.lista_coppie.SetSelection(1)
        dlg.on_inverti(None)
        assert dlg.coppie[1] == ("D", "C")
        assert finestra.suoni[-1] == "coppia_invertita_avvertimento"

    def test_inversione_e_proposta_hanno_i_loro_suoni(self, finestra):
        """Inverti colori e Proposta automatica non suonano come l'aggiunta
        di una coppia: ciascuna ha due eventi suoi, senza e con avvertimenti."""
        giocatori = [_giocatore(f"P{i}", f"Cognome{i}", 2000 - i * 100) for i in range(1, 5)]
        dlg = finestra.crea(_torneo(giocatori), turno=1)

        dlg.lista_coppie.SetSelection(0)
        dlg.on_inverti(None)
        assert finestra.suoni == ["coppia_invertita"]
        dlg.on_proposta(None)
        assert finestra.suoni[-1] == "proposta_coppie"
        assert finestra.domande[-1][0] == "Proposta automatica"

        saturo = finestra.crea(_torneo_saturo())
        saturo.lista_coppie.SetSelection(0)
        saturo.on_togli(None)
        saturo.on_proposta(None)
        assert finestra.suoni[-1] == "proposta_coppie_avvertimento"
        assert saturo.coppie == [("B", "A"), ("C", "D")]

    def test_il_bianco_scelto_a_mano(self, finestra):
        dlg = finestra.crea(_torneo_saturo())
        dlg.lista_coppie.SetSelection(0)
        dlg.on_togli(None)
        dlg.lista_liberi.SetSelection(0)
        dlg.on_giocatore_scelto(SimpleNamespace(Skip=lambda: None))

        dlg.scelta_bianco.SetSelection(0)
        dlg.on_aggiungi(None)

        assert ("A", "B") in dlg.coppie

    def test_il_riposo_in_fondo_agli_avversari(self, finestra):
        giocatori = [_giocatore(f"P{i}", f"Cognome{i}", 2000 - i * 100) for i in range(1, 6)]
        dlg = finestra.crea(_torneo(giocatori), turno=1)
        bye = next(i for i, (_b, n) in enumerate(dlg.coppie) if n is None)

        dlg.lista_coppie.SetSelection(bye)
        dlg.on_togli(None)
        dlg.lista_liberi.SetSelection(0)
        dlg.on_giocatore_scelto(SimpleNamespace(Skip=lambda: None))

        assert dlg.lista_avversari.GetString(dlg.lista_avversari.GetCount() - 1) == "Riposo (bye)"
        dlg.lista_avversari.SetSelection(dlg.lista_avversari.GetCount() - 1)
        dlg.on_avversario_scelto(SimpleNamespace(Skip=lambda: None))
        assert not dlg.scelta_bianco.IsEnabled()
        dlg.on_aggiungi(None)
        assert finestra.suoni[-1] == "coppia_aggiunta"
        assert dlg.btn_conferma.IsEnabled()

    def test_la_conferma_mostra_il_riepilogo(self, finestra):
        dlg = finestra.crea(_torneo_saturo())

        dlg.on_conferma(None)

        titolo, testo = finestra.domande[-1]
        assert titolo == "Conferma del turno composto a mano"
        assert "Avvertimenti: 2, su 2 scacchiere." in testo
        assert dlg.situazione.GetValue().splitlines()[3] == "Avvertimenti 2"
        assert "Scacchiera 1, Beta Test contro Alfa Test: gia' incontrati al turno 1." in testo
        assert "Il pulsante predefinito e' No." in testo
        assert dlg.coppie_confermate == [("B", "A"), ("C", "D")]
        assert finestra.suoni[-1] == "fine 5100"

    def test_rispondendo_no_la_finestra_resta_aperta(self, finestra):
        dlg = finestra.crea(_torneo_saturo(), risposta=False)

        dlg.on_conferma(None)

        assert dlg.coppie_confermate is None
        assert not any(s.startswith("fine") for s in finestra.suoni)

    def test_oltre_sedici_attivi_si_compone_da_zero(self, finestra):
        dlg = finestra.crea(_torneo([_giocatore(f"G{i:02d}", f"C{i:02d}", 2000 - i) for i in range(17)]), turno=1)

        assert dlg.coppie == []
        assert dlg.lista_liberi.GetCount() == 17
        dlg.on_proposta(None)
        assert finestra.suoni == ["errore"]
        assert finestra.domande[-1][0] == "Proposta non disponibile"

    def test_annulla(self, finestra):
        dlg = finestra.crea(_torneo_saturo())

        dlg.on_annulla(None)

        assert finestra.suoni == ["cancellato", f"fine {finestra.wx.ID_CANCEL}"]
        assert dlg.coppie_confermate is None


def test_le_combinazioni_della_prova_esaustiva():
    """La prova della proposta conta davvero tutti gli abbinamenti: fra sei
    nodi sono quindici."""
    assert len(list(_tutti_gli_abbinamenti(list(range(6))))) == 15
    assert len({frozenset(frozenset(c) for c in a) for a in _tutti_gli_abbinamenti(list(range(6)))}) == 15
    assert list(itertools.islice(_tutti_gli_abbinamenti([]), 2)) == [[]]
