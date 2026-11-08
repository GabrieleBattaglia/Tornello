"""CANC sulla voce di un turno, dalla 10.19.0: la Time Machine dall'albero
(decisione di Gabriele del 4 novembre 2026).

Sul turno corrente, l'ultimo abbinato, CANC fa quello che fa Ctrl+Z, con la
stessa domanda e lo stesso pulsante predefinito. Su un turno dei Completati
torna a quel turno, che ridiventa il turno corrente con i suoi risultati:
spariscono tutti i turni dopo, come con tanti Ctrl+Z quanti sono quei turni,
e se sono piu' di uno la domanda li conta e li nomina, con No predefinito.
Una copia di sicurezza sola, un salvataggio solo, alla fine, e nessuno stato
a meta': se il file del torneo non si scrive il torneo resta com'era. Su un
torneo concluso un messaggio dice perche' la Time Machine non lavora.
I tornei delle prove sono abbinati dal vero bbpPairings.exe, come in
test_e2e.py e test_turno_manuale.py: otto giocatori, cinque turni, un
ritiro dopo il turno 1 e un forfait con ritiro nel turno 3. Le prove girano
sulla finestra principale vera, mai mostrata, con le domande finte di
test_canc_nell_albero.py, che annotano titolo, testo e pulsante predefinito,
e i suoni annotati.
"""

import copy
import io
import json
import os
from contextlib import redirect_stdout
from types import SimpleNamespace

import pytest
import test_canc_nell_albero as canc
from test_canc_nell_albero import _canc, _dal_file, _domande, _voce

# Le due fixture della finestra principale, le stesse delle prove di CANC
# sulle partite.
principale = canc.principale
suoni = canc.suoni

PUNTI = {"1-0": (1.0, 0.0), "0-1": (0.0, 1.0), "1/2-1/2": (0.5, 0.5), "1-F": (1.0, 0.0)}

GIOCATORI = (
    ("ALF", "Alfieri", "Anna", 2000),
    ("BAR", "Barbieri", "Bruno", 1950),
    ("CAR", "Caruso", "Carla", 1900),
    ("DEL", "Delfini", "Dario", 1850),
    ("ESP", "Esposito", "Elena", 1800),
    ("FER", "Ferri", "Fabio", 1750),
    ("GAL", "Galli", "Giulia", 1700),
    ("LOM", "Lombardi", "Luca", 1650),
)

# Si ritira dopo il turno 1, che ha giocato: dopo la Time Machine resta
# ritirato, finche' resta il turno 1.
RITIRATO_PRESTO = "LOM"

ANNULLA_TURNO = "Sei sicuro di voler annullare l'ultimo turno del torneo Turni e tornare indietro? Questa azione è irreversibile."


def _risultato(turno, scacchiera):
    """Un risultato diverso per ogni scacchiera, sempre lo stesso."""
    return ("1-0", "0-1", "1/2-1/2")[(turno + scacchiera) % 3]


def _stato(torneo):
    """Quello che la Time Machine riporta com'era: i turni, il turno
    corrente, il numero della prossima partita e, per ogni giocatore, punti,
    storico e ritiro."""
    return {
        "rounds": json.loads(json.dumps(torneo["rounds"])),
        "current_round": torneo["current_round"],
        "next_match_id": torneo["next_match_id"],
        "players": {
            g["id"]: (g["points"], json.loads(json.dumps(g.get("results_history", []))), bool(g.get("withdrawn")))
            for g in torneo["players"]
        },
    }


def _torneo_vero(abbinati=4, ultimo_completo=False):
    """Il torneo Turni, con i turni da 1 ad abbinati calcolati da
    bbpPairings. Ogni turno e' completo, con il file dei suoi dettagli, come
    lo scrive la finestra quando un turno si conclude, tranne l'ultimo,
    appena abbinato, se ultimo_completo e' falso. Dopo il turno 1 si ritira
    Lombardi; nel turno 3 il nero della scacchiera 1 non si presenta, perde
    1-F e si ritira. Restituisce il torneo, la fotografia di _stato a ogni
    turno completo, prima che il turno dopo fosse abbinato, e chi si e'
    ritirato nel turno 3."""
    from reports import append_completed_round_to_history_file
    from tournament import _apply_match_result_to_players, generate_pairings_for_round, motivo_ultimo_fallimento, registra_turno

    giocatori = [
        {
            "id": codice,
            "first_name": nome,
            "last_name": cognome,
            "initial_elo": elo,
            "current_elo": elo,
            "points": 0.0,
            "withdrawn": False,
            "results_history": [],
            "sex": "m",
            "federation": "ITA",
        }
        for codice, cognome, nome, elo in GIOCATORI
    ]
    torneo = {
        "name": "Turni",
        "site": "Online",
        "federation_code": "ITA",
        "start_date": "2026-11-01",
        "end_date": "2026-11-30",
        "total_rounds": 5,
        "current_round": 1,
        "next_match_id": 1,
        "chief_arbiter": "Gabry",
        "time_control": {"minutes": 60, "increment": 0},
        "initial_board1_color_setting": "white1",
        "bye_value": 0.5,
        "players": giocatori,
        "rounds": [],
    }
    torneo["players_dict"] = {g["id"]: g for g in giocatori}
    fotografie = {}
    ritirato_nel_turno_3 = None
    for numero in range(1, abbinati + 1):
        torneo["current_round"] = numero
        with redirect_stdout(io.StringIO()):
            partite = generate_pairings_for_round(torneo)
        assert partite is not None, motivo_ultimo_fallimento(torneo)
        turno = registra_turno(torneo, partite, numero)
        if numero == abbinati and not ultimo_completo:
            break
        for scacchiera, partita in enumerate(turno["matches"], 1):
            if partita.get("black_player_id") is None:
                continue
            risultato = _risultato(numero, scacchiera)
            if numero == 3 and scacchiera == 1:
                risultato = "1-F"
                ritirato_nel_turno_3 = partita["black_player_id"]
            with redirect_stdout(io.StringIO()):
                _apply_match_result_to_players(torneo, partita, risultato, *PUNTI[risultato])
        if numero == 1:
            torneo["players_dict"][RITIRATO_PRESTO]["withdrawn"] = True
        if numero == 3:
            torneo["players_dict"][ritirato_nel_turno_3]["withdrawn"] = True
        append_completed_round_to_history_file(torneo, numero)
        fotografie[numero] = _stato(torneo)
    return torneo, fotografie, ritirato_nel_turno_3


def _scrivi(torneo):
    from config import user_data_path

    percorso = user_data_path("Tornello - Turni.json")
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in torneo.items() if k != "players_dict"}, f, default=sorted)
    return percorso


def _apri(principale, torneo):
    percorso = _scrivi(torneo)
    principale.load_tournament(percorso)
    assert principale.current_tournament is not None
    return principale.active_filename


def _senza_i_valori_della_classifica(torneo, modello):
    """Il torneo con, per ogni giocatore, le sole chiavi del giocatore di
    modello. La classifica dei report, che la finestra scrive dopo ogni
    salvataggio, lascia nei giocatori in memoria i suoi valori, come il
    Buchholz e l'ARO, e il salvataggio dopo li porta nel file: dopo tre
    Ctrl+Z ci sono quelli del secondo, che CANC, con un salvataggio solo,
    non ha. La Time Machine non li tocca, e la classifica li ricalcola."""
    chiavi = {g["id"]: set(g) for g in modello["players"]}
    return dict(torneo, players=[{k: v for k, v in g.items() if k in chiavi[g["id"]]} for g in torneo["players"]])


def _archiviato(torneo):
    """Il torneo, concluso, scritto nell'archivio, in Closed Tournaments,
    2026, 11 Novembre, Turni: il percorso del suo file."""
    import config

    torneo["concluded"] = True
    cartella = os.path.join(config.ARCHIVED_TOURNAMENTS_DIR, "2026", "11 Novembre", "Turni")
    os.makedirs(cartella)
    archiviato = os.path.join(cartella, "Tornello - Turni.json")
    with open(archiviato, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in torneo.items() if k != "players_dict"}, f, default=sorted)
    return archiviato


def _byte(percorso):
    with open(percorso, "rb") as f:
        return f.read()


def _turno(principale, percorso, numero):
    return _voce(principale, action="show_round_report", filepath=percorso, round=numero)


def _dettagli(torneo, numero):
    from reports import file_dei_dettagli_del_turno

    return file_dei_dettagli_del_turno(torneo, numero)


def _cestino(principale, monkeypatch, rifiuta=()):
    """Il cestino finto della finestra: annota i file e li toglie, tranne
    quelli da rifiutare, che restano, come su un disco senza cestino."""
    ricevuti = []

    def nel_cestino(percorso):
        ricevuti.append(percorso)
        if percorso in rifiuta:
            return False
        os.remove(percorso)
        return True

    monkeypatch.setattr(principale, "_nel_cestino", nel_cestino)
    return ricevuti


def _copie(contesto):
    from config import user_data_path

    return [nome for _radice, _cartelle, nomi in os.walk(user_data_path("backup")) for nome in nomi if f"_{contesto}_" in nome]


class TestLaFunzioneDiTournament:
    """torna_al_turno di tournament.py fa sul torneo quello che fanno tante
    chiamate di rollback_to_previous_round, senza copia, cestino e suono."""

    def test_come_tanti_rollback(self, monkeypatch):
        import utils
        from tournament import rollback_to_previous_round, torna_al_turno

        monkeypatch.setattr(utils, "play_sound", lambda *a, **k: True)
        torneo, _fotografie, _ritirato = _torneo_vero()
        uno, altro = copy.deepcopy(torneo), copy.deepcopy(torneo)

        assert torna_al_turno(uno, 1) == [4, 3, 2]
        for _volta in range(3):
            assert rollback_to_previous_round(altro, cestino=lambda percorso: True) is True

        assert uno == altro

    def test_senza_turni_dopo_non_cambia_niente(self):
        from tournament import torna_al_turno

        torneo, _fotografie, _ritirato = _torneo_vero()
        prima = copy.deepcopy(torneo)

        assert torna_al_turno(torneo, 4) == []
        assert torna_al_turno(torneo, 7) == []
        assert torneo == prima

    def test_a_zero_il_torneo_torna_in_preparazione(self):
        from tournament import torna_al_turno

        torneo, _fotografie, _ritirato = _torneo_vero(abbinati=2)

        assert torna_al_turno(torneo, 0) == [2, 1]
        assert torneo["rounds"] == []
        assert torneo["current_round"] == 1
        assert all(g["points"] == 0.0 and g["results_history"] == [] and not g["withdrawn"] for g in torneo["players"])


class TestSulTurnoCorrente:
    """Sul turno corrente CANC fa quello che fa Ctrl+Z."""

    def test_la_domanda_e_il_risultato_di_ctrl_z(self, principale, suoni, monkeypatch):
        import wx

        torneo, fotografie, _ritirato = _torneo_vero()
        percorso = _apri(principale, torneo)
        ricevuti = _cestino(principale, monkeypatch)
        domande = _domande(monkeypatch, wx.ID_YES)
        albero = principale.tree_ctrl
        voce = _turno(principale, percorso, 4)
        assert albero.GetItemText(voce) == "Turno corrente (4/5)"
        suoni.clear()

        _canc(principale, voce)

        assert [(d.titolo, d.testo, d.domanda, d.no_predefinito) for d in domande.aperte] == [("Annulla Turno", ANNULLA_TURNO, True, False)]
        assert _stato(_dal_file(percorso)) == fotografie[3]
        assert _stato(principale.current_tournament) == fotografie[3]
        assert suoni == ["time_machine"]
        assert principale.last_status_msg == "Time Machine attivata: tornati al turno precedente."
        # Il turno 4, appena abbinato, non aveva il file dei dettagli.
        assert ricevuti == []
        assert len(_copie("pre_rollback")) == 1
        assert _copie("pre_timemachine") == []
        # Il cursore sul turno 3, che torna corrente, fra i Completati.
        scelta = albero.GetSelection()
        assert albero.GetItemData(scelta)["action"] == "show_round_report"
        assert albero.GetItemData(scelta)["round"] == 3
        assert albero.GetItemText(scelta) == "Turno 3"
        assert albero.GetItemText(albero.GetItemParent(scelta)) == "Completati (3)"
        assert "Turno Corrente: 3 di 5" in principale.main_text.GetValue()

    def test_e_proprio_ctrl_z(self, principale, suoni, monkeypatch):
        """Lo stesso torneo, una volta con CANC sul turno corrente e una con
        Ctrl+Z: i due file sono identici."""
        import wx

        torneo, _fotografie, _ritirato = _torneo_vero()
        percorso = _apri(principale, copy.deepcopy(torneo))
        _cestino(principale, monkeypatch)
        _domande(monkeypatch, wx.ID_YES, wx.ID_YES)
        _canc(principale, _turno(principale, percorso, 4))
        con_canc = _dal_file(percorso)

        _apri(principale, copy.deepcopy(torneo))
        principale.on_rollback_round(None)

        assert _dal_file(percorso) == con_canc

    def test_con_no_non_cambia_niente(self, principale, suoni, monkeypatch):
        import wx

        torneo, _fotografie, _ritirato = _torneo_vero()
        percorso = _apri(principale, torneo)
        prima = _dal_file(percorso)
        ricevuti = _cestino(principale, monkeypatch)
        domande = _domande(monkeypatch, wx.ID_NO)
        suoni.clear()

        _canc(principale, _turno(principale, percorso, 4))

        assert len(domande.aperte) == 1
        assert _dal_file(percorso) == prima
        assert len(principale.current_tournament["rounds"]) == 4
        assert ricevuti == [] and suoni == []
        assert _copie("pre_rollback") == []

    def test_il_turno_corrente_completo_fra_i_completati(self, principale, suoni, monkeypatch):
        """Con tutti i risultati il turno 4 sta fra i Completati, sotto c'e'
        la voce calcola il turno successivo, ed e' ancora il turno corrente:
        CANC lo toglie, come Ctrl+Z, con il suo file dei dettagli."""
        import wx

        torneo, fotografie, _ritirato = _torneo_vero(ultimo_completo=True)
        percorso = _apri(principale, torneo)
        dettagli_4 = _dettagli(principale.current_tournament, 4)
        ricevuti = _cestino(principale, monkeypatch)
        domande = _domande(monkeypatch, wx.ID_YES)
        albero = principale.tree_ctrl
        voce = _turno(principale, percorso, 4)
        assert albero.GetItemText(albero.GetItemParent(voce)) == "Completati (4)"
        _voce(principale, action="generate_next_round_action", filepath=percorso)

        _canc(principale, voce)

        assert [d.titolo for d in domande.aperte] == ["Annulla Turno"]
        assert _stato(_dal_file(percorso)) == fotografie[3]
        assert ricevuti == [dettagli_4]
        assert albero.GetItemData(albero.GetSelection())["round"] == 3

    def test_il_turno_1_riporta_il_torneo_in_preparazione(self, principale, suoni, monkeypatch):
        """Il turno 1 corrente, tolto, lascia il torneo In Preparazione, con
        il cursore sulla voce calcola il turno 1, sotto turni."""
        import wx

        torneo, _fotografie, _ritirato = _torneo_vero(abbinati=1)
        percorso = _apri(principale, torneo)
        _cestino(principale, monkeypatch)
        _domande(monkeypatch, wx.ID_YES)
        albero = principale.tree_ctrl

        _canc(principale, _turno(principale, percorso, 1))

        assert _dal_file(percorso)["rounds"] == []
        scelta = albero.GetSelection()
        assert albero.GetItemData(scelta)["action"] == "start_tournament_matchmaking_action"
        assert albero.GetItemText(scelta) == "calcola il turno 1"
        assert albero.GetItemText(albero.GetItemParent(scelta)) == "turni (0)"
        torneo_voce = _voce(principale, action="select_tournament", filepath=percorso)
        assert albero.GetItemData(albero.GetItemParent(torneo_voce))["action"] == "category_prep"


class TestSuUnTurnoCompletato:
    """Su un turno dei Completati CANC torna a quel turno."""

    def test_un_turno_solo_e_la_domanda_di_ctrl_z(self, principale, suoni, monkeypatch):
        """Il turno 3 viene subito prima del corrente: sparisce il solo turno
        4, e la domanda e' quella di Ctrl+Z, con Si' predefinito."""
        import wx

        torneo, fotografie, _ritirato = _torneo_vero()
        percorso = _apri(principale, torneo)
        _cestino(principale, monkeypatch)
        domande = _domande(monkeypatch, wx.ID_YES)
        albero = principale.tree_ctrl

        _canc(principale, _turno(principale, percorso, 3))

        assert [(d.titolo, d.testo, d.no_predefinito) for d in domande.aperte] == [("Annulla Turno", ANNULLA_TURNO, False)]
        assert _stato(_dal_file(percorso)) == fotografie[3]
        assert principale.last_status_msg == "Time Machine attivata: tornati al turno precedente."
        assert albero.GetItemData(albero.GetSelection())["round"] == 3

    def test_due_turni_con_la_domanda_che_li_nomina(self, principale, suoni, monkeypatch):
        """Il turno 2: spariscono il 3, con il suo file dei dettagli, e il 4.
        La domanda li nomina, dice chi torna in gioco, cioe' chi si e'
        ritirato nel turno 3 e non chi si e' ritirato dopo il turno 1, e ha
        No predefinito. Poi il torneo e' quello di quando il turno 2 si era
        appena concluso, con il cursore sul Turno 2, e bbpPairings abbina di
        nuovo il turno 3 come allora."""
        import wx

        torneo, fotografie, ritirato = _torneo_vero()
        percorso = _apri(principale, torneo)
        turno_3_di_allora = [(m["id"], m["white_player_id"], m["black_player_id"]) for m in principale.current_tournament["rounds"][2]["matches"]]
        dettagli = {numero: _dettagli(principale.current_tournament, numero) for numero in (1, 2, 3)}
        ricevuti = _cestino(principale, monkeypatch)
        domande = _domande(monkeypatch, wx.ID_YES)
        albero = principale.tree_ctrl
        nome = principale._nome_del_giocatore(ritirato)
        suoni.clear()

        _canc(principale, _turno(principale, percorso, 2))

        domanda = domande.aperte[0]
        assert (domanda.titolo, domanda.domanda, domanda.no_predefinito) == ("Torna al turno 2", True, True)
        assert domanda.testo == "\n\n".join(
            [
                "Vuoi tornare al turno 2 del torneo Turni? Spariscono 2 turni, il turno 3 e il turno 4, con i loro abbinamenti e i loro risultati, e il turno 2 torna il turno corrente, con i suoi risultati. Questa azione è irreversibile.",
                f"Torna in gioco {nome}, ritirato, che ha un risultato in uno dei turni che spariscono.",
                "Il pulsante predefinito è No.",
            ]
        )
        salvato = _dal_file(percorso)
        assert _stato(salvato) == fotografie[2]
        ritiri = {g["id"]: g["withdrawn"] for g in salvato["players"]}
        assert ritiri[ritirato] is False and ritiri[RITIRATO_PRESTO] is True
        assert suoni == ["time_machine"]
        assert principale.last_status_msg == "Time Machine attivata: tornati al turno 2, tolti 2 turni."
        assert ricevuti == [dettagli[3]]
        assert os.path.exists(dettagli[1]) and os.path.exists(dettagli[2])
        assert len(_copie("pre_timemachine")) == 1
        assert _copie("pre_rollback") == []
        scelta = albero.GetSelection()
        assert (albero.GetItemData(scelta)["round"], albero.GetItemText(scelta)) == (2, "Turno 2")
        assert albero.GetItemText(albero.GetItemParent(scelta)) == "Completati (2)"
        _voce(principale, action="generate_next_round_action", filepath=percorso)

        principale.generate_next_round()

        rifatto = principale.current_tournament["rounds"][2]
        assert [(m["id"], m["white_player_id"], m["black_player_id"]) for m in rifatto["matches"]] == turno_3_di_allora

    def test_tre_turni_come_tre_ctrl_z(self, principale, suoni, monkeypatch):
        """Il turno 1: spariscono il 2, il 3 e il 4, e il file e' identico a
        quello di tre Ctrl+Z di fila sullo stesso torneo."""
        import wx

        torneo, fotografie, _ritirato = _torneo_vero()
        percorso = _apri(principale, copy.deepcopy(torneo))
        ricevuti = _cestino(principale, monkeypatch)
        domande = _domande(monkeypatch, *[wx.ID_YES] * 4)

        _canc(principale, _turno(principale, percorso, 1))

        assert domande.aperte[0].titolo == "Torna al turno 1"
        assert "Spariscono 3 turni, dal turno 2 al turno 4, con i loro abbinamenti e i loro risultati" in domande.aperte[0].testo
        con_canc = _dal_file(percorso)
        assert _stato(con_canc) == fotografie[1]
        assert len(ricevuti) == 2
        assert principale.last_status_msg == "Time Machine attivata: tornati al turno 1, tolti 3 turni."

        from reports import append_completed_round_to_history_file

        _apri(principale, copy.deepcopy(torneo))
        # I file dei dettagli che CANC ha mandato nel cestino finto.
        for numero in (2, 3):
            append_completed_round_to_history_file(principale.current_tournament, numero)
        for _volta in range(3):
            principale.on_rollback_round(None)

        assert _senza_i_valori_della_classifica(_dal_file(percorso), con_canc) == con_canc
        assert len(ricevuti) == 4

    def test_con_no_non_cambia_niente(self, principale, suoni, monkeypatch):
        """Senza risposta Si' niente cambia, niente va nel cestino e non
        nasce nessuna copia: INVIO nel testo, con No predefinito, risponde
        No."""
        import wx

        torneo, _fotografie, _ritirato = _torneo_vero()
        percorso = _apri(principale, torneo)
        prima = _dal_file(percorso)
        in_memoria = copy.deepcopy(principale.current_tournament)
        ricevuti = _cestino(principale, monkeypatch)
        _domande(monkeypatch, wx.ID_NO)
        suoni.clear()

        _canc(principale, _turno(principale, percorso, 1))

        assert _dal_file(percorso) == prima
        assert principale.current_tournament == in_memoria
        assert ricevuti == [] and suoni == []
        assert _copie("pre_timemachine") == []

    def test_il_file_che_il_cestino_non_prende_resta_e_lo_si_dice(self, principale, suoni, monkeypatch):
        import wx

        torneo, fotografie, _ritirato = _torneo_vero()
        percorso = _apri(principale, torneo)
        dettagli = [_dettagli(principale.current_tournament, numero) for numero in (3, 2)]
        _cestino(principale, monkeypatch, rifiuta=dettagli)
        domande = _domande(monkeypatch, wx.ID_YES)

        _canc(principale, _turno(principale, percorso, 1))

        assert _stato(_dal_file(percorso)) == fotografie[1]
        messaggio = domande.aperte[1]
        assert messaggio.titolo == "File rimasti fuori dal cestino"
        assert messaggio.testo.splitlines() == [
            "I file dei dettagli dei turni tolti non sono andati nel cestino, e restano dove sono, anche se i turni non ci sono più:",
            *dettagli,
        ]
        assert suoni[-1] == "errore"


class TestNessunoStatoAMeta:
    def test_se_il_file_non_si_scrive_il_torneo_resta_com_era(self, principale, suoni, monkeypatch):
        """Il salvataggio non riesce, per esempio perche' un altro programma
        tiene bloccato il file: il torneo resta quello di prima, in memoria e
        sul disco, i file dei dettagli restano, e un messaggio lo dice."""
        import wx

        import tournament

        torneo, _fotografie, _ritirato = _torneo_vero()
        percorso = _apri(principale, torneo)
        prima = _dal_file(percorso)
        aperto = principale.current_tournament
        in_memoria = copy.deepcopy(aperto)
        ricevuti = _cestino(principale, monkeypatch)
        domande = _domande(monkeypatch, wx.ID_YES)
        monkeypatch.setattr(tournament, "save_tournament", lambda *a, **k: False)
        suoni.clear()

        _canc(principale, _turno(principale, percorso, 2))

        assert principale.current_tournament is aperto
        assert aperto == in_memoria
        assert _dal_file(percorso) == prima
        assert ricevuti == []
        assert suoni == ["errore"]
        messaggio = domande.aperte[1]
        assert messaggio.titolo == "Time Machine non riuscita"
        assert messaggio.testo.startswith(f"Il file del torneo {percorso} non si è potuto scrivere, e la Time Machine si è fermata: il torneo Turni resta com'era, con tutti i suoi turni.")
        assert principale.last_status_msg == messaggio.testo

    def test_lo_stesso_per_ctrl_z(self, principale, suoni, monkeypatch):
        """Fino alla 10.18.1 Ctrl+Z cambiava il torneo in memoria prima di
        salvarlo, e un salvataggio mancato non si sapeva."""
        import wx

        import tournament

        torneo, _fotografie, _ritirato = _torneo_vero()
        percorso = _apri(principale, torneo)
        prima = _dal_file(percorso)
        in_memoria = copy.deepcopy(principale.current_tournament)
        _cestino(principale, monkeypatch)
        domande = _domande(monkeypatch, wx.ID_YES)
        monkeypatch.setattr(tournament, "save_tournament", lambda *a, **k: False)

        principale.on_rollback_round(None)

        assert principale.current_tournament == in_memoria
        assert _dal_file(percorso) == prima
        assert [d.titolo for d in domande.aperte] == ["Annulla Turno", "Time Machine non riuscita"]


class TestDoveLaTimeMachineNonLavora:
    def test_il_torneo_concluso_e_archiviato(self, principale, suoni, monkeypatch):
        """Sul turno di un torneo dei Tornei Conclusi, dove Ctrl+Z e' spento,
        CANC fa sentire l'errore e un messaggio dice perche' e come si
        riapre il torneo; il file resta com'era."""
        torneo, _fotografie, _ritirato = _torneo_vero(ultimo_completo=True)
        archiviato = _archiviato(torneo)
        principale.load_tournament(archiviato)
        percorso = principale.active_filename
        prima = _dal_file(percorso)
        domande = _domande(monkeypatch)
        albero = principale.tree_ctrl
        voce = _turno(principale, percorso, 2)
        conclusi = albero.GetItemParent(albero.GetItemParent(albero.GetItemParent(albero.GetItemParent(voce))))
        assert albero.GetItemData(conclusi)["action"] == "category_closed"
        suoni.clear()

        _canc(principale, voce)

        assert suoni == ["errore"]
        assert [(d.titolo, d.domanda) for d in domande.aperte] == [("Torneo concluso", False)]
        assert domande.aperte[0].testo.startswith("Il torneo Turni è concluso, e la Time Machine non toglie i turni di un torneo finalizzato.")
        assert "Copie di sicurezza" in domande.aperte[0].testo
        assert _dal_file(percorso) == prima
        assert principale.item_rollback.IsEnabled() is False

    def test_il_turno_di_un_torneo_che_non_e_aperto(self, principale, suoni, monkeypatch):
        torneo, _fotografie, _ritirato = _torneo_vero()
        percorso = _apri(principale, torneo)
        prima = _dal_file(percorso)
        domande = _domande(monkeypatch)
        suoni.clear()

        principale._canc_sulla_voce(None, {"action": "show_round_report", "filepath": "Tornello - Altro.json", "round": 2})

        assert suoni == ["errore"]
        assert [d.titolo for d in domande.aperte] == ["Torneo non aperto"]
        assert domande.aperte[0].testo.startswith("Il turno 2 non è del torneo aperto")
        assert _dal_file(percorso) == prima


class TestSulGiocatoreDiUnTorneoConcluso:
    """Dalla 10.19.0 CANC sul giocatore di un torneo concluso fa sentire
    l'errore, e il messaggio Torneo concluso dice perche' e come si riapre
    il torneo, come sui suoi turni. Fino alla 10.18.1 proponeva il ritiro, e
    con Si' cambiava il file archiviato e scriveva i report nella cartella
    di salvataggio."""

    TESTO = "Il torneo Turni è concluso, e i suoi giocatori non si tolgono e non si ritirano più. Un torneo finalizzato si riapre dalla finestra Copie di sicurezza del menu File, ripristinando la sua copia di prima della finalizzazione."

    @pytest.mark.parametrize("aperto", [True, False], ids=["aperto", "non aperto"])
    def test_nessun_ritiro_e_nessun_file_toccato(self, principale, suoni, monkeypatch, aperto):
        """Il torneo archiviato aperto, come nella revisione, oppure un altro
        torneo aperto: allora CANC arriva sulla voce senza sceglierla, perche'
        scelta aprirebbe il suo torneo, come in
        test_il_turno_di_un_torneo_che_non_e_aperto."""
        import wx

        from config import user_data_path

        torneo, _fotografie, _ritirato = _torneo_vero(ultimo_completo=True)
        archiviato = _archiviato(torneo)
        if aperto:
            principale.load_tournament(archiviato)
        else:
            canc._apri(principale)
            principale.populate_tree()
        prima = _byte(archiviato)
        cartelle = (user_data_path(""), os.path.dirname(archiviato))
        file_di_prima = [sorted(os.listdir(cartella)) for cartella in cartelle]
        domande = _domande(monkeypatch, wx.ID_YES, wx.ID_YES)
        albero = principale.tree_ctrl
        voce = _voce(principale, action="show_player_detail", filepath=archiviato)
        assert albero.GetItemData(voce)["player"]["id"] == "ALF"
        suoni.clear()

        if aperto:
            _canc(principale, voce)
        else:
            principale._canc_sulla_voce(voce, albero.GetItemData(voce))

        assert principale._e_il_torneo_aperto(archiviato) is aperto
        assert suoni == ["errore"]
        assert [(d.titolo, d.testo, d.domanda) for d in domande.aperte] == [("Torneo concluso", self.TESTO, False)]
        assert _byte(archiviato) == prima
        assert [sorted(os.listdir(cartella)) for cartella in cartelle] == file_di_prima


def test_la_domanda_con_piu_ritiri_annullati_li_elenca_uno_per_riga(principale):
    """Quando tornano in gioco piu' giocatori la domanda li elenca, un nome
    per riga, sotto una frase che dice perche'."""
    torneo, _fotografie, _ritirato = _torneo_vero()
    _apri(principale, torneo)
    nuovo = copy.deepcopy(principale.current_tournament)
    for codice in ("ALF", "BAR"):
        principale.current_tournament["players_dict"][codice]["withdrawn"] = True
        nuovo["players_dict"][codice]["withdrawn"] = False

    testo = principale._domanda_del_ritorno(nuovo, [4, 3, 2], 1)

    assert "\n\nTornano in gioco i giocatori ritirati che hanno un risultato in uno dei turni che spariscono:\nAlfieri Anna\nBarbieri Bruno\n\n" in testo


@pytest.mark.parametrize("abbinati", [2, 3, 4])
def test_il_torneo_di_prova_e_abbinato_dal_motore(abbinati):
    """bbpPairings abbina tutti i turni, con il bye a chi tocca e senza chi
    si e' ritirato."""
    torneo, fotografie, ritirato = _torneo_vero(abbinati=abbinati)

    assert [r["round"] for r in torneo["rounds"]] == list(range(1, abbinati + 1))
    assert sorted(fotografie) == list(range(1, abbinati))
    for turno in torneo["rounds"][1:]:
        in_gioco = {chi for m in turno["matches"] for chi in (m["white_player_id"], m["black_player_id"]) if chi}
        assert RITIRATO_PRESTO not in in_gioco
    if abbinati == 4:
        assert ritirato not in {chi for m in torneo["rounds"][3]["matches"] for chi in (m["white_player_id"], m["black_player_id"])}


class TestIDettagliDopoIlRipristino:
    """10.19.50 (decisione di Gabriele dell'8 novembre 2026). La prova 5 del
    collaudo: Ctrl+Z sul torneo con i turni da 1 a 3 completi manda nel
    cestino il file dei dettagli del turno 3, e il file del turno 2 dice un
    altro risultato; poi, dal menu File, la finestra Copie di sicurezza e il
    ripristino della copia di prima della Time Machine, fuori dalla procedura
    guidata, dentro, dopo Nuovo torneo, e con un altro torneo aperto. Dopo il
    ripristino, nella cartella dei report, i file dei tre turni sono quelli
    scritti alla conclusione dei turni. Fino alla 10.19.49 il file del turno
    3 restava nel cestino, e quello del turno 2 diceva il risultato di prima.
    La finestra delle copie non si mostra: seleziona la copia e preme
    Ripristina, con Si' alla conferma; le finestre di messaggio e il cestino
    sono finti."""

    @staticmethod
    def _dettagli():
        from config import user_data_path

        cartella = user_data_path("")
        dettagli = {}
        for nome in sorted(os.listdir(cartella)):
            if nome.endswith(" Dettagli.txt"):
                with open(os.path.join(cartella, nome), "rb") as f:
                    dettagli[nome] = f.read()
        return dettagli

    @staticmethod
    def _finestra_delle_copie(monkeypatch, copia, cestino):
        """La finestra Copie di sicurezza finta: seleziona la copia, anche
        fra tutte se l'origine scelta non la mostra, e preme Ripristina.
        Restituisce le sue finestre di messaggio, con titolo e testo, e i
        suoi suoni."""
        import wx

        from gui.dialogs import backup_cleanup_dialog as bcd

        registro = SimpleNamespace(finestre=[], suoni=[])

        class Messaggio:
            def __init__(self, genitore, titolo, testo, style=wx.OK, **opzioni):
                self.domanda = bool(style & wx.YES_NO)
                registro.finestre.append((titolo, testo))

            def ShowModal(self):
                return wx.ID_YES if self.domanda else wx.ID_OK

            def Destroy(self):
                pass

        def mostra(finestra):
            if os.path.normcase(copia) not in [os.path.normcase(c.percorso) for c in finestra.visibili]:
                finestra.populate_list(origine=None)
            indice = [os.path.normcase(c.percorso) for c in finestra.visibili].index(os.path.normcase(copia))
            for vecchio in finestra.indici_selezionati():
                finestra.list_ctrl.Select(vecchio, False)
            finestra.list_ctrl.Select(indice, True)
            finestra.on_ripristina(None)
            return wx.ID_CANCEL

        monkeypatch.setattr(bcd, "AccessibleMsgDialog", Messaggio)
        monkeypatch.setattr(bcd, "play_sound", lambda nome, *a, **k: registro.suoni.append(nome))
        monkeypatch.setattr(bcd, "delete_file_to_trash", cestino)
        monkeypatch.setattr(bcd.BackupCleanupDialog, "ShowModal", mostra)
        return registro

    @pytest.mark.parametrize("caso", ["fuori", "dentro", "altro"], ids=["fuori dalla procedura guidata", "dentro la procedura guidata", "con un altro torneo aperto"])
    def test_la_prova_5_del_collaudo(self, principale, suoni, monkeypatch, cestino_finto, caso):
        import re

        import wx
        from test_comandi_delle_finestre import TestAlberoETorneoAttivo, _torneo_in_corso

        from config import user_data_path

        torneo, _fotografie, _ritirato = _torneo_vero(abbinati=3, ultimo_completo=True)
        allora = self._dettagli()
        assert len(allora) == 3
        percorso = _apri(principale, copy.deepcopy(torneo))
        domande = _domande(monkeypatch, wx.ID_YES)
        principale.on_rollback_round(None)
        assert [d.titolo for d in domande.aperte] == ["Annulla Turno"]
        turno_3 = _dettagli(principale.current_tournament, 3)
        assert cestino_finto.ricevuti == [os.path.abspath(turno_3)]
        turno_2 = _dettagli(principale.current_tournament, 2)
        with open(turno_2, "rb") as f:
            righe = f.read().split(b"\r\n")
        prima = next(i for i, r in enumerate(righe) if r.startswith(b"\t1  |"))
        risultato = righe[prima].rsplit(b"| ", 1)[1]
        righe[prima] = righe[prima][: -len(risultato)] + (b"0-1" if risultato != b"0-1" else b"1-0")
        with open(turno_2, "wb") as f:
            f.write(b"\r\n".join(righe))
        (copia,) = [os.path.join(r, n) for r, _c, nomi in os.walk(user_data_path("backup")) for n in nomi if "_pre_rollback_" in n]
        alfa = user_data_path("Tornello - Alfa.json")
        if caso == "altro":
            with open(alfa, "w", encoding="utf-8") as f:
                json.dump(_torneo_in_corso("Alfa"), f)
            principale.load_tournament(alfa)
        if caso == "dentro":
            TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
            assert principale.creation_mode
        copie = self._finestra_delle_copie(monkeypatch, copia, cestino_finto)
        scatole = []
        monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
        registro = TestAlberoETorneoAttivo._sonde(principale)
        suoni.clear()

        TestAlberoETorneoAttivo._dal_menu(principale, principale.item_backup_cleanup.GetId())

        assert self._dettagli() == allora
        assert cestino_finto.ricevuti == [os.path.abspath(turno_3)]
        assert [titolo for titolo, _testo in copie.finestre] == ["Conferma ripristino", "Ripristino riuscito"]
        assert re.fullmatch(
            r"Ripristino riuscito: Tornello - Turni\.json è com'era nella copia\.\nLo stato di prima è nella copia Tornello - Turni_pre_ripristino_\d{8}_\d{6}\.json\.",
            copie.finestre[1][1],
        ), copie.finestre[1][1]
        assert copie.suoni == ["ripristino"]
        assert scatole == []
        assert [d.titolo for d in domande.aperte] == ["Annulla Turno"]
        assert suoni == []
        assert registro.fuoco == ["tree_ctrl"]
        assert not principale.creation_mode
        assert len(_dal_file(percorso)["rounds"]) == 3
        aperto = alfa if caso == "altro" else percorso
        assert principale._e_il_torneo_aperto(aperto)
        assert principale.tree_ctrl.GetItemData(principale.tree_ctrl.GetSelection())["filepath"] == principale.active_filename
