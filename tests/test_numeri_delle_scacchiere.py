"""I numeri delle scacchiere da una funzione sola, dopo la 10.19.54
(decisione di Gabriele dell'8 novembre 2026).

numeri_delle_scacchiere di reports da' il numero della scacchiera di ogni
partita di un turno: le partite in ordine di identificativo, numerate da 1,
contando anche il riposo. La usavano l'albero della finestra e, dalla
10.19.54, il file dei dettagli del turno; gli altri posti che mostrano un
numero di scacchiera facevano lo stesso calcolo ognuno per conto suo, e
adesso la chiamano: get_board_num della finestra, per la finestra del
risultato, il dettaglio della partita e le domande di CANC e di Togli
programmazione, il ramo Partite PGN dell'albero, la raccolta delle partite
nell'area centrale, il cursore che dopo un risultato passa alla partita
successiva, il calendario ics e la console, nell'elenco delle partite da
registrare, nella ricerca per nome e nella scelta del numero. I numeri che
si vedono restano gli stessi.
Il turno 2 del torneo delle prove ha nel file le partite fuori ordine di
identificativo, e il riposo in mezzo: ogni posto deve dare i numeri scritti
qui, gli stessi di numeri_delle_scacchiere. Un mutante di
numeri_delle_scacchiere, che per esempio numera da 0 o al contrario, fa
cadere ogni prova: segno che ogni posto il numero lo prende da li'.
Le prove della finestra girano sulla finestra principale vera, mai
mostrata, con le domande finte di test_canc_nell_albero, che annotano
titolo e testo, e la finestra del risultato finta; quelle della console con
le risposte a copione di test_console. Tutto sta nella cartella temporanea
della prova."""

import json
from types import SimpleNamespace

import pytest
import test_canc_nell_albero as canc
import test_console as console
from test_canc_nell_albero import _canc, _domande
from test_console import Copione

# La finestra principale, mai mostrata, con i suoni annotati, come nelle
# prove di CANC; i suoni muti della console.
principale = canc.principale
suoni = canc.suoni
muto = console.muto

GIOCATORI = (
    ("ALF", "Alfieri", "Anna", 2000),
    ("BAR", "Barbieri", "Bruno", 1950),
    ("CAR", "Caruso", "Carla", 1900),
    ("DEL", "Delfini", "Dario", 1850),
    ("ESP", "Esposito", "Elena", 1800),
    ("FER", "Ferri", "Fabio", 1750),
    ("GAL", "Galli", "Giulia", 1700),
    ("LOM", "Lombardi", "Luca", 1650),
    ("MAR", "Marini", "Marta", 1600),
)

PGN = '[Event "Numeri"]\n[Result "{r}"]\n\n1. e4 e5 2. Nf3 Nc6 {r}'

# Il turno 2: scacchiera, identificativo, bianco, nero, risultato,
# programmazione e PGN. Nel file le partite stanno nell'ordine di
# ORDINE_NEL_FILE, e Marini riposa alla 3, fra le partite.
TURNO_2 = (
    (1, 6, "ALF", "BAR", "1-0", None, True),
    (2, 7, "CAR", "DEL", None, ("2026-11-12", "18:00"), False),
    (3, 8, "MAR", None, "BYE", None, False),
    (4, 9, "ESP", "FER", "0-1", None, True),
    (5, 10, "GAL", "LOM", None, ("2026-11-13", "20:30"), False),
)
ORDINE_NEL_FILE = (9, 6, 10, 8, 7)
TURNO_1 = (
    (1, 1, "ALF", "ESP", "1-0", None, False),
    (2, 2, "FER", "BAR", "0-1", None, False),
    (3, 3, "CAR", "GAL", "1-0", None, True),
    (4, 4, "LOM", "MAR", "1/2-1/2", None, False),
    (5, 5, "DEL", None, "BYE", None, False),
)
# I numeri che ogni posto deve dare, per identificativo.
NUMERI_2 = {6: 1, 7: 2, 8: 3, 9: 4, 10: 5}
NUMERI_1 = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
PUNTI = {"1-0": (1.0, 0.0), "0-1": (0.0, 1.0), "1/2-1/2": (0.5, 0.5), "BYE": (0.5, None)}


def _nome(codice, al_contrario=True):
    """Il nome come lo scrive l'albero, cognome e nome, o come la console,
    nome e cognome."""
    _c, cognome, nome, _elo = next(g for g in GIOCATORI if g[0] == codice)
    return f"{cognome} {nome}" if al_contrario else f"{nome} {cognome}"


def _partite(numero, righe):
    partite = []
    for _scacchiera, ident, bianco, nero, risultato, programmazione, pgn in righe:
        partita = {"id": ident, "round": numero, "white_player_id": bianco, "black_player_id": nero, "result": risultato}
        if programmazione:
            giorno, ora = programmazione
            partita.update(is_scheduled=True, schedule_info={"date": giorno, "time": ora, "channel": "Sala A", "arbiter": "Gabry"})
        if pgn:
            partita["pgn"] = PGN.format(r=risultato)
        partite.append(partita)
    return partite


def _torneo():
    """Nove giocatori al turno 2 di 4: il turno 1 chiuso, il turno 2 con
    due partite giocate, due da giocare, programmate, e il riposo."""
    giocatori = [
        {"id": codice, "last_name": cognome, "first_name": nome, "initial_elo": elo, "current_elo": elo, "points": 0.0, "withdrawn": False, "results_history": []}
        for codice, cognome, nome, elo in GIOCATORI
    ]
    per_id = {g["id"]: g for g in giocatori}
    for numero, righe in ((1, TURNO_1), (2, TURNO_2)):
        for _scacchiera, _ident, bianco, nero, risultato, _programmazione, _pgn in righe:
            if risultato is None:
                continue
            punti_bianco, punti_nero = PUNTI[risultato]
            if nero is None:
                per_id[bianco]["results_history"].append({"round": numero, "opponent_id": "BYE_PLAYER_ID", "color": None, "result": "BYE", "score": punti_bianco})
                continue
            per_id[bianco]["results_history"].append({"round": numero, "opponent_id": nero, "color": "white", "result": risultato, "score": punti_bianco})
            per_id[nero]["results_history"].append({"round": numero, "opponent_id": bianco, "color": "black", "result": risultato, "score": punti_nero})
    for g in giocatori:
        g["points"] = sum(v["score"] for v in g["results_history"])
    turno_2 = {m["id"]: m for m in _partite(2, TURNO_2)}
    torneo = {
        "name": "Numeri",
        "start_date": "2026-11-01",
        "end_date": "2026-11-30",
        "total_rounds": 4,
        "current_round": 2,
        "bye_value": 0.5,
        "next_match_id": 11,
        "time_control": {"minutes": 60, "increment": 0},
        "players": giocatori,
        "rounds": [{"round": 1, "matches": _partite(1, TURNO_1)}, {"round": 2, "matches": [turno_2[i] for i in ORDINE_NEL_FILE]}],
    }
    torneo["players_dict"] = per_id
    return torneo


def _apri(principale):
    """Scrive il torneo nella cartella del programma e lo apre."""
    from config import user_data_path

    percorso = user_data_path("Tornello - Numeri.json")
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in _torneo().items() if k != "players_dict"}, f)
    principale.load_tournament(percorso)
    assert principale.current_tournament is not None
    return principale.active_filename


def _voci(principale, azione):
    """Le voci dell'albero con l'azione azione, nell'ordine dell'albero, come
    turno, identificativo, numero dei dati, etichetta e voce."""
    albero = principale.tree_ctrl
    trovate = []

    def visita(voce):
        figlio, cookie = albero.GetFirstChild(voce)
        while figlio.IsOk():
            dati = albero.GetItemData(figlio)
            if isinstance(dati, dict) and dati.get("action") == azione:
                trovate.append((dati.get("round"), dati["match"]["id"], dati.get("board_num"), albero.GetItemText(figlio), figlio))
            visita(figlio)
            figlio, cookie = albero.GetNextChild(voce, cookie)

    visita(principale.tree_root)
    return trovate


def _voce_della_partita(principale, turno, ident):
    return next(v for t, i, _n, _e, v in _voci(principale, "activate_match") if (t, i) == (turno, ident))


def _attiva(principale, voce):
    principale.on_tree_item_activated(SimpleNamespace(GetItem=lambda: voce))


def _finestra_del_risultato(monkeypatch, risposta, risultato=None):
    """Al posto della finestra del risultato: annota come l'apre la
    finestra principale e risponde risposta, con il risultato risultato."""
    from gui.dialogs import result_dialog

    aperte = []

    class Risultato:
        def __init__(self, *a, **k):
            aperte.append(k)
            self.selected_action = None
            self.txt_pgn = SimpleNamespace(GetValue=lambda: "")

        def ShowModal(self):
            return risposta

        def get_selected_result(self):
            return risultato

        def Destroy(self):
            pass

    monkeypatch.setattr(result_dialog, "ResultDialog", Risultato)
    return aperte


@pytest.fixture
def senza_messagebox(monkeypatch):
    """Nessun wx.MessageBox deve uscire."""
    import wx

    usciti = []
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: usciti.append(a))
    yield
    assert usciti == []


def test_la_funzione_numera_per_identificativo_con_il_riposo():
    """I numeri attesi sono quelli di numeri_delle_scacchiere, e il file
    tiene le partite in un altro ordine."""
    from reports import numeri_delle_scacchiere

    torneo = _torneo()
    assert [m["id"] for m in torneo["rounds"][1]["matches"]] == [9, 6, 10, 8, 7]
    assert numeri_delle_scacchiere(torneo["rounds"][1]) == NUMERI_2
    assert numeri_delle_scacchiere(torneo["rounds"][0]) == NUMERI_1


class TestNellaFinestra:
    def test_get_board_num(self, principale, suoni):
        """get_board_num, che serve alla finestra del risultato, al
        dettaglio e alle domande di CANC e di Togli programmazione: per ogni
        partita il numero della funzione, e 1 per una partita che il turno
        non ha, come prima."""
        _apri(principale)
        for turno, attesi in ((1, NUMERI_1), (2, NUMERI_2)):
            partite = principale.current_tournament["rounds"][turno - 1]["matches"]
            assert {m["id"]: principale.get_board_num(m, turno) for m in partite} == attesi
        assert principale.get_board_num({"id": 99}, 2) == 1
        assert principale.get_board_num({"id": 6}, 7) == 1

    def test_i_rami_dei_turni(self, principale, suoni):
        """Le voci delle partite nei rami dei turni, che numeravano gia' con
        la funzione: il riferimento degli altri posti."""
        _apri(principale)
        voci = {(t, i): (n, e) for t, i, n, e, _v in _voci(principale, "activate_match")}
        assert {i: n for (t, i), (n, _e) in voci.items() if t == 2} == NUMERI_2
        assert {i: n for (t, i), (n, _e) in voci.items() if t == 1} == NUMERI_1
        assert voci[(2, 8)][1] == "Scacchiera 3: Marini Marta - BYE [BYE]"
        assert voci[(2, 9)][1] == "Scacchiera 4: Esposito Elena vs Ferri Fabio [0-1]"
        assert voci[(2, 10)][1].startswith("Scacchiera 5: Galli Giulia vs Lombardi Luca (Pianificata: ")

    def test_il_dettaglio_della_partita(self, principale, suoni):
        """Il dettaglio della partita nell'area centrale, chiesto senza il
        numero, come dopo la finestra del risultato: il numero lo cerca
        get_board_num."""
        _apri(principale)
        for turno, attesi in ((1, NUMERI_1), (2, NUMERI_2)):
            for m in principale.current_tournament["rounds"][turno - 1]["matches"]:
                principale.show_match_detail_verbose(m, turno)
                assert principale.main_text.GetValue().splitlines()[:2] == [f"DETTAGLIO PARTITA - TURNO {turno}", f"Scacchiera Numero: {attesi[m['id']]}"]

    def test_la_finestra_del_risultato(self, principale, suoni, monkeypatch, senza_messagebox):
        """INVIO sulle partite del turno 2, giocate e da giocare: la finestra
        del risultato, Risultato Scacchiera seguito dal numero, riceve il
        numero della funzione. Con Annulla niente cambia, e l'area centrale
        mostra il dettaglio con lo stesso numero."""
        import wx

        _apri(principale)
        aperte = _finestra_del_risultato(monkeypatch, wx.ID_CANCEL)
        for ident in (6, 7, 9, 10):
            _attiva(principale, _voce_della_partita(principale, 2, ident))
        assert [(k["board_num"], k["white_id"], k["black_id"]) for k in aperte] == [(1, "ALF", "BAR"), (2, "CAR", "DEL"), (4, "ESP", "FER"), (5, "GAL", "LOM")]

    def test_il_cursore_dopo_il_risultato(self, principale, suoni, monkeypatch, senza_messagebox):
        """Il risultato della Scacchiera 2 dalla finestra del risultato: il
        cursore dell'albero passa alla partita da giocare dopo, la
        Scacchiera 5, che si ritrova con il suo numero, e l'area centrale
        mostra il dettaglio della Scacchiera 2."""
        import wx

        _apri(principale)
        _domande(monkeypatch)
        _finestra_del_risultato(monkeypatch, wx.ID_OK, "1-0")
        _attiva(principale, _voce_della_partita(principale, 2, 7))

        albero = principale.tree_ctrl
        scelta = albero.GetSelection()
        assert albero.GetItemText(scelta).startswith("Scacchiera 5: Galli Giulia vs Lombardi Luca (Pianificata: ")
        assert albero.GetItemData(scelta)["board_num"] == 5
        assert principale.main_text.GetValue().splitlines()[:2] == ["DETTAGLIO PARTITA - TURNO 2", "Scacchiera Numero: 2"]

    def test_le_domande_di_canc(self, principale, suoni, monkeypatch, senza_messagebox):
        """CANC sulla Scacchiera 4, giocata, e sulla Scacchiera 5, da
        giocare e programmata: le domande Cancellazione del risultato e
        Togli programmazione nominano la scacchiera con il numero della
        funzione. Con No il file del torneo resta com'era."""
        import wx

        percorso = _apri(principale)
        with open(percorso, "rb") as f:
            prima = f.read()
        domande = _domande(monkeypatch, wx.ID_NO, wx.ID_NO)
        _canc(principale, _voce_della_partita(principale, 2, 9))
        _canc(principale, _voce_della_partita(principale, 2, 10))

        assert [d.titolo for d in domande.aperte] == ["Cancellazione del risultato", "Togli programmazione"]
        assert domande.aperte[0].testo.startswith("Vuoi cancellare il risultato 0-1 della scacchiera 4 del turno 2, Esposito Elena contro Ferri Fabio?")
        assert domande.aperte[1].testo.startswith("Vuoi togliere la programmazione della scacchiera 5, Galli Giulia contro Lombardi Luca, per ")
        with open(percorso, "rb") as f:
            assert f.read() == prima

    def test_il_ramo_partite_pgn(self, principale, suoni):
        """Le voci del ramo Partite PGN, turno per turno, con il numero della
        funzione nell'etichetta e nei dati."""
        _apri(principale)
        voci = [(t, i, n, e) for t, i, n, e, _v in _voci(principale, "show_single_pgn")]
        assert voci == [
            (1, 3, 3, "Scacchiera 3: Caruso Carla vs Galli Giulia [1-0]"),
            (2, 6, 1, "Scacchiera 1: Alfieri Anna vs Barbieri Bruno [1-0]"),
            (2, 9, 4, "Scacchiera 4: Esposito Elena vs Ferri Fabio [0-1]"),
        ]

    def test_la_raccolta_nell_area_centrale(self, principale, suoni):
        """La raccolta delle partite PGN nell'area centrale, di tutto il
        torneo e del turno 2: le partite nell'ordine del file, con il
        numero della funzione."""
        _apri(principale)
        principale.show_pgn_matches_list_verbose()
        assert principale.main_text.GetValue().splitlines() == [
            "RACCOLTA PARTITE PGN",
            "  Turno 1 Scacchiera 3: Caruso Carla vs Galli Giulia [1-0]",
            "  Turno 2 Scacchiera 4: Esposito Elena vs Ferri Fabio [0-1]",
            "  Turno 2 Scacchiera 1: Alfieri Anna vs Barbieri Bruno [1-0]",
        ]
        principale.show_pgn_matches_list_verbose(2)
        assert principale.main_text.GetValue().splitlines() == [
            "RACCOLTA PARTITE PGN - TURNO 2",
            "  Turno 2 Scacchiera 4: Esposito Elena vs Ferri Fabio [0-1]",
            "  Turno 2 Scacchiera 1: Alfieri Anna vs Barbieri Bruno [1-0]",
        ]


def test_il_calendario_ics():
    """Il calendario ics delle partite programmate: nel titolo e nella
    descrizione di ogni evento il numero della funzione."""
    from reports import generate_ics_content

    contenuto, saltate = generate_ics_content(_torneo())

    assert saltate == []
    righe = contenuto.split("\r\n")
    assert [r for r in righe if r.startswith("SUMMARY:")] == [
        "SUMMARY:Turno 2 - Scacchiera 5: Galli Giulia vs Lombardi Luca",
        "SUMMARY:Turno 2 - Scacchiera 2: Caruso Carla vs Delfini Dario",
    ]
    assert [r.split("\\n")[2] for r in righe if r.startswith("DESCRIPTION:")] == ["Scacchiera: 5", "Scacchiera: 2"]


class TestInConsole:
    """La richiesta dei risultati del turno corrente nella versione a riga
    di comando, ui.update_match_result, con le risposte a copione."""

    def _richiesta(self, monkeypatch, tasti, conferme):
        import config
        import ui

        torneo = _torneo()
        percorso = config.user_data_path("Tornello - Numeri.json")
        copione = Copione(monkeypatch, tasti=tasti, conferme=conferme)
        ui.update_match_result(torneo, percorso)
        assert copione.tasti == [] and copione.conferme == []
        risultati = {m["id"]: m["result"] for m in torneo["rounds"][1]["matches"]}
        return copione, risultati

    def test_l_elenco_e_il_numero(self, monkeypatch, muto, capsys):
        """L'elenco delle partite da registrare dice Sc. con il numero della
        funzione, la domanda li elenca, e 5 sceglie la Scacchiera 5."""
        copione, risultati = self._richiesta(monkeypatch, ["5", "1-0", ""], [True])

        uscita = capsys.readouterr().out.splitlines()
        assert [r.split(" - ", 1)[0] for r in uscita if r.startswith("    Sc. ")] == ["    Sc. 2  (IDG:7)", "    Sc. 5  (IDG:10)", "    Sc. 2  (IDG:7)"]
        assert copione.domande[0].endswith("\nR|T|SC|nome|cognome [2-5]: ")
        assert "Partita selezionata per risultato: Giulia Galli vs Luca Lombardi (ID Glob: 10)" in uscita
        assert copione.domande[-1].endswith("\nR|T|SC|nome|cognome [2]: ")
        assert risultati == {9: "0-1", 6: "1-0", 10: "1-0", 8: "BYE", 7: None}

    def test_la_ricerca_per_nome(self, monkeypatch, muto, capsys):
        """La ricerca per nome con una partita sola: la console dice il suo
        numero."""
        _copione, risultati = self._richiesta(monkeypatch, ["lomb", "1/2", ""], [True])

        uscita = capsys.readouterr().out.splitlines()
        assert "Trovata partita unica (Sc. 5): Giulia Galli vs Luca Lombardi" in uscita
        assert risultati[10] == "1/2-1/2" and risultati[7] is None

    def test_la_scelta_fra_le_partite_trovate(self, monkeypatch, muto, capsys):
        """Con due partite trovate per nome la console le elenca con i loro
        numeri, e 5 sceglie la Scacchiera 5."""
        copione, risultati = self._richiesta(monkeypatch, ["ar", "5", "1-0", ""], [True])

        uscita = capsys.readouterr().out.splitlines()
        inizio = uscita.index("Trovate 2 partite pendenti per 'ar':")
        assert [r.split(" - ", 1)[0] for r in uscita[inizio + 1 : inizio + 3]] == ["  Sc. 2  (IDG:7)", "  Sc. 5  (IDG:10)"]
        assert copione.domande[1] == "Inserisci il N.Scacchiera (del turno) desiderato dalla lista sopra: "
        assert risultati[10] == "1-0" and risultati[7] is None
