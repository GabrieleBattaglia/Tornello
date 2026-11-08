"""L'Elo nel file dei dettagli di un turno concluso, dalla 10.19.57
(decisione di Gabriele dell'8 novembre 2026).

Il file Tornello - nome - Turno N Dettagli.txt scrive l'Elo di partenza dei
giocatori intero, [1844], anche quando il torneo lo tiene con il punto zero,
1844.0. Cosi' lo tengono i tornei nati nella finestra, che lo prendono dal
database con get_initial_elo_for_tournament, e i tornei che la versione a
riga di comando salva, che passano da Player di models; un giocatore senza
Elo ha 1399.0, l'Elo che Tornello gli da'. Fino alla 10.19.56 l'Elo usciva
com'era nel torneo, [1844.0] nel Turno 3 di Autunneo2 e [1600.0] nel Turno 3
di Prova time machine, sul banco del collaudo, e la colonna si allargava di
due caratteri. Un Elo che manca resta ?, e uno con i decimali, che i file
del programma non hanno, resta com'e', perche' non si perda niente. Il
ripristino di una copia di sicurezza, che dalla 10.19.50 riscrive i file
dei dettagli che dicono altro, riscrive anche quelli scritti con il punto
zero.
Le prove della finestra girano sulla finestra principale vera, mai
mostrata, con i suoni annotati e la finestra del risultato finta di
test_scacchiere_nei_dettagli; quelle della console con il controller vero e
le risposte a copione. Tutto sta nella cartella temporanea della prova."""

import io
import os
from contextlib import redirect_stdout
from types import SimpleNamespace

import test_canc_sui_turni as turni
import test_console as console
import test_scacchiere_nei_dettagli as scacchiere
from test_canc_nell_albero import _voce_della_partita
from test_console import Copione, _adattatore, _controller, _torneo_al_primo_turno

principale = turni.principale
suoni = turni.suoni
muto = console.muto

INTESTAZIONE_DELLE_PARTITE = "\tSc | ID  | Bianco                       [Elo] (Pt) - Nero                         [Elo] (Pt) | Risultato\n"

# Le schede del database dei giocatori, come la finestra le iscrive: l'Elo
# di partenza viene da get_initial_elo_for_tournament, e Player di models lo
# tiene con il punto zero. Davanzo non ha Elo, e prende quello di Tornello.
SCHEDE = (
    {"id": "GAS", "first_name": "Claudio", "last_name": "Gasperoni", "current_elo": 1844},
    {"id": "DAV", "first_name": "Luca", "last_name": "Davanzo"},
    {"id": "PEZ", "first_name": "Erica", "last_name": "Pezzolato", "current_elo": 1616},
    {"id": "VIL", "first_name": "Gennaro", "last_name": "Vilone", "current_elo": 1499},
    {"id": "TOL", "first_name": "Filippa", "last_name": "Tolaro", "current_elo": 1515},
)
PUNTI_DOPO_IL_TURNO_1 = {"GAS": 1.0, "DAV": 0.0, "PEZ": 0.0, "VIL": 1.0, "TOL": 0.5}

# Il file del turno 1 del torneo delle schede, riga per riga, senza la riga
# in fondo con la versione.
RIGHE_DEL_TURNO_1 = [
    "Torneo: Elo intero\n",
    "Sito: Online, Data Inizio Torneo: Domenica 1 novembre 2026\n",
    "Dettaglio del turno 1 concluso\n",
    "\tPeriodo del Turno: Domenica 1 novembre 2026 - Sabato 7 novembre 2026\n",
    INTESTAZIONE_DELLE_PARTITE,
    "\t1  | 1   | Claudio Gasperoni        [1844] (1   ) - Luca Davanzo             [1399] (0   ) | 1-0\n",
    "\t2  | 2   | Erica Pezzolato          [1616] (0   ) - Gennaro Vilone           [1499] (1   ) | 0-1\n",
    "\tbye| 3   | Filippa Tolaro           [1515] (0.5 ) - BYE                             | BYE\n",
]
# Le stesse righe come le scriveva la 10.19.56: l'Elo con il punto zero.
RIGHE_DEL_TURNO_1_FINO_ALLA_10_19_56 = [
    *RIGHE_DEL_TURNO_1[:5],
    "\t1  | 1   | Claudio Gasperoni        [1844.0] (1   ) - Luca Davanzo             [1399.0] (0   ) | 1-0\n",
    "\t2  | 2   | Erica Pezzolato          [1616.0] (0   ) - Gennaro Vilone           [1499.0] (1   ) | 0-1\n",
    "\tbye| 3   | Filippa Tolaro           [1515.0] (0.5 ) - BYE                             | BYE\n",
]


def _versione():
    """La riga in fondo al file, con la versione di Tornello."""
    from version import VERSIONE

    return f"\n\nTornello ({VERSIONE})\n"


def _leggi(percorso):
    with open(percorso, encoding="utf-8-sig") as f:
        return f.read()


def _torneo_dalla_finestra(cartella):
    """Il torneo Elo intero, con la cartella dei report cartella e i
    giocatori iscritti come li iscrive la finestra, e il turno 1 completo:
    Gasperoni batte Davanzo, Vilone batte Pezzolato, Tolaro riposa."""
    from models import Player
    from stats import get_initial_elo_for_tournament

    giocatori = []
    for scheda in SCHEDE:
        scheda = dict(scheda)
        scheda["initial_elo"] = get_initial_elo_for_tournament(scheda, "standard")
        giocatore = Player.from_dict(scheda).to_dict()
        giocatore["points"] = PUNTI_DOPO_IL_TURNO_1[giocatore["id"]]
        giocatori.append(giocatore)
    os.makedirs(cartella, exist_ok=True)
    return {
        "name": "Elo intero",
        "site": "Online",
        "start_date": "2026-11-01",
        "end_date": "2026-11-30",
        "custom_save_path": str(cartella),
        "total_rounds": 3,
        "current_round": 1,
        "players": giocatori,
        "round_dates": [{"round": 1, "start_date": "2026-11-01", "end_date": "2026-11-07"}],
        "rounds": [
            {
                "round": 1,
                "matches": [
                    {"id": 1, "round": 1, "white_player_id": "GAS", "black_player_id": "DAV", "result": "1-0"},
                    {"id": 2, "round": 1, "white_player_id": "PEZ", "black_player_id": "VIL", "result": "0-1"},
                    {"id": 3, "round": 1, "white_player_id": "TOL", "black_player_id": None, "result": "BYE"},
                ],
            }
        ],
    }


def test_il_file_scrive_l_elo_intero(tmp_path, cestino_finto):
    """Il turno concluso di un torneo con l'Elo come lo tiene la finestra,
    con il punto zero, anche per il giocatore senza Elo e per chi riposa:
    nel file l'Elo e' intero, riga per riga."""
    from reports import append_completed_round_to_history_file, file_dei_dettagli_del_turno

    cartella = tmp_path / "report"
    torneo = _torneo_dalla_finestra(cartella)
    # Il caso c'e': la finestra tiene l'Elo con il punto zero.
    assert [g["initial_elo"] for g in torneo["players"]] == [1844.0, 1399.0, 1616.0, 1499.0, 1515.0]
    assert all(isinstance(g["initial_elo"], float) for g in torneo["players"])

    with redirect_stdout(io.StringIO()) as uscita:
        append_completed_round_to_history_file(torneo, 1)

    percorso = file_dei_dettagli_del_turno(torneo, 1)
    assert uscita.getvalue().splitlines() == [f"Dettaglio Turno Concluso 1 salvato nel file separato '{percorso}'"]
    assert os.listdir(cartella) == ["Tornello - Elo_intero - Turno 1 Dettagli.txt"]
    assert _leggi(percorso) == "".join(RIGHE_DEL_TURNO_1) + _versione()
    assert cestino_finto.tentativi == []


def test_l_elo_che_manca_quello_con_i_decimali_e_quello_intero(tmp_path):
    """Un Elo che manca resta ?, come prima; uno con i decimali, che i file
    del programma non hanno, resta com'e', perche' non si perda niente; uno
    gia' intero, come lo tengono i tornei archiviati delle versioni
    vecchie, resta intero."""
    from reports import append_completed_round_to_history_file, file_dei_dettagli_del_turno

    torneo = _torneo_dalla_finestra(tmp_path / "report")
    giocatori = {g["id"]: g for g in torneo["players"]}
    del giocatori["GAS"]["initial_elo"]
    giocatori["DAV"]["initial_elo"] = 1844.5
    giocatori["PEZ"]["initial_elo"] = 1616
    giocatori["TOL"]["initial_elo"] = 1515

    with redirect_stdout(io.StringIO()):
        append_completed_round_to_history_file(torneo, 1)

    assert _leggi(file_dei_dettagli_del_turno(torneo, 1)) == "".join(
        [
            *RIGHE_DEL_TURNO_1[:5],
            "\t1  | 1   | Claudio Gasperoni        [   ?] (1   ) - Luca Davanzo             [1844.5] (0   ) | 1-0\n",
            "\t2  | 2   | Erica Pezzolato          [1616] (0   ) - Gennaro Vilone           [1499] (1   ) | 0-1\n",
            "\tbye| 3   | Filippa Tolaro           [1515] (0.5 ) - BYE                             | BYE\n",
        ]
    ) + _versione()


class TestDopoIlRipristino:
    """Il ripristino di una copia di sicurezza allinea i file dei dettagli
    con allinea_i_dettagli_dei_turni, come dalla 10.19.50: il file scritto
    con il punto zero dice altro, e si riscrive, sovrascrivendo quello di
    prima, senza cestino; quello che cambia soltanto nella riga della
    versione resta com'e'."""

    def _scrivi(self, percorso, righe, versione):
        """Il file dei dettagli con le righe e la riga della versione
        versione in fondo, come lo scriveva quella versione; i suoi byte."""
        with open(percorso, "w", encoding="utf-8-sig") as f:
            f.write("".join(righe) + f"\n\nTornello ({versione})\n")
        with open(percorso, "rb") as f:
            return f.read()

    def test_il_file_col_punto_zero_si_riscrive(self, tmp_path, cestino_finto):
        from reports import allinea_i_dettagli_dei_turni, file_dei_dettagli_del_turno

        cartella = tmp_path / "report"
        torneo = _torneo_dalla_finestra(cartella)
        percorso = file_dei_dettagli_del_turno(torneo, 1)
        self._scrivi(percorso, RIGHE_DEL_TURNO_1_FINO_ALLA_10_19_56, "10.19.56")

        with redirect_stdout(io.StringIO()) as uscita:
            rimasti = allinea_i_dettagli_dei_turni(torneo, cestino_finto)

        assert rimasti == [] and cestino_finto.tentativi == []
        assert uscita.getvalue().splitlines() == [f"Dettaglio Turno Concluso 1 salvato nel file separato '{percorso}'"]
        assert os.listdir(cartella) == ["Tornello - Elo_intero - Turno 1 Dettagli.txt"]
        assert _leggi(percorso) == "".join(RIGHE_DEL_TURNO_1) + _versione()

    def test_il_file_con_l_elo_intero_resta(self, tmp_path, cestino_finto):
        from reports import allinea_i_dettagli_dei_turni, file_dei_dettagli_del_turno

        cartella = tmp_path / "report"
        torneo = _torneo_dalla_finestra(cartella)
        percorso = file_dei_dettagli_del_turno(torneo, 1)
        di_prima = self._scrivi(percorso, RIGHE_DEL_TURNO_1, "10.19.56")

        with redirect_stdout(io.StringIO()) as uscita:
            rimasti = allinea_i_dettagli_dei_turni(torneo, cestino_finto)

        assert rimasti == [] and cestino_finto.tentativi == []
        assert uscita.getvalue() == ""
        with open(percorso, "rb") as f:
            assert f.read() == di_prima


class TestNellaFinestra:
    """Il Turno 3 di Turni, il torneo di test_canc_sui_turni, con l'Elo con
    il punto zero, come lo tiene un torneo nato nella finestra: i tre
    risultati si registrano dalla finestra del risultato, aperta con INVIO
    sulla partita nell'albero, e l'ultimo conclude il turno, che scrive il
    file."""

    def test_la_conclusione_del_turno_scrive_l_elo_intero(self, principale, suoni, monkeypatch, cestino_finto):
        torneo, _fotografie, _ritirato = turni._torneo_vero(abbinati=3)
        for giocatore in torneo["players"]:
            giocatore["initial_elo"] = float(giocatore["initial_elo"])
        percorso = turni._apri(principale, torneo)
        # Il caso c'e': il torneo aperto tiene l'Elo con il punto zero.
        assert all(isinstance(g["initial_elo"], float) for g in principale.current_tournament["players"])
        risultati = {9: "1-0", 10: "0-1", 11: "1/2-1/2"}
        scacchiere.TestNellaFinestra._finestra_del_risultato(None, monkeypatch, {s: risultati[i] for s, i, _b, _n in scacchiere.TURNO_3})
        suoni.clear()
        for scacchiera, ident, _bianco, _nero in scacchiere.TURNO_3:
            voce = _voce_della_partita(principale, percorso, 3, scacchiera, ident)
            with redirect_stdout(io.StringIO()):
                principale.on_tree_item_activated(SimpleNamespace(GetItem=lambda voce=voce: voce))

        # L'ultimo risultato conclude il turno: il suono della fine del
        # turno, e il cursore sul calcolo del turno successivo.
        assert "conclusione_turno" in suoni
        albero = principale.tree_ctrl
        assert albero.GetItemText(albero.GetSelection()) == "calcola il turno successivo"
        assert _leggi(turni._dettagli(principale.current_tournament, 3)) == "".join(
            [
                "Torneo: Turni\n",
                "Sito: Online, Data Inizio Torneo: Domenica 1 novembre 2026\n",
                "Dettaglio del turno 3 concluso\n",
                "\tPeriodo del Turno: Date non trovate\n",
                INTESTAZIONE_DELLE_PARTITE,
                "\t1  | 9   | Anna Alfieri             [2000] (2.5 ) - Giulia Galli             [1700] (2   ) | 1-0\n",
                "\t2  | 10  | Fabio Ferri              [1750] (1   ) - Elena Esposito           [1800] (2   ) | 0-1\n",
                "\t3  | 11  | Bruno Barbieri           [1950] (1   ) - Dario Delfini            [1850] (1   ) | 1/2-1/2\n",
                "\tbye| 12  | Carla Caruso             [1900] (1   ) - BYE                             | BYE\n",
            ]
        ) + _versione()
        assert cestino_finto.tentativi == []


class TestInConsole:
    """Il torneo di quattro giocatori della console, con l'Elo con il punto
    zero, come lo tiene Player di models: nel turno 1 vincono G3 e G4, nel
    turno 2 vince il bianco della scacchiera 1 e la 2 e' patta. La console
    conclude i due turni, e scrive i due file."""

    def test_la_console_scrive_l_elo_intero(self, monkeypatch, muto, capsys, cestino_finto):
        import config

        copione = Copione(
            monkeypatch,
            tasti=["1", "0-1", "2", "1-0", "", "1", "1-0", "2", "1/2", ""],
            conferme=[True, True, True, True, True, True, True, False],
        )
        torneo = _torneo_al_primo_turno()
        # Il caso c'e': Player tiene l'Elo con il punto zero.
        assert all(isinstance(g.initial_elo, float) for g in torneo.players)
        guida = _controller(_adattatore(copione), torneo)

        guida._main_loop()

        assert copione.tasti == [] and copione.conferme == []
        uscita = capsys.readouterr().out.splitlines()
        dettagli = {n: os.path.abspath(config.user_data_path(f"Tornello - Console_Prova - Turno {n} Dettagli.txt")) for n in (1, 2)}
        for n in (1, 2):
            assert f"Dettaglio Turno Concluso {n} salvato nel file separato '{dettagli[n]}'" in uscita
        cartella = os.path.dirname(dettagli[1])
        assert sorted(n for n in os.listdir(cartella) if n.endswith("Dettagli.txt")) == [os.path.basename(dettagli[n]) for n in (1, 2)]
        assert _leggi(dettagli[1]) == "".join(
            [
                "Torneo: Console_Prova\n",
                "Sito: Online, Data Inizio Torneo: Martedì 1 settembre 2026\n",
                "Dettaglio del turno 1 concluso\n",
                "\tPeriodo del Turno: Date non trovate\n",
                INTESTAZIONE_DELLE_PARTITE,
                "\t1  | 1   | NomeG1 CognomeG1         [1800] (0   ) - NomeG3 CognomeG3         [1600] (1   ) | 0-1\n",
                "\t2  | 2   | NomeG4 CognomeG4         [1500] (1   ) - NomeG2 CognomeG2         [1700] (0   ) | 1-0\n",
            ]
        ) + _versione()
        assert _leggi(dettagli[2]) == "".join(
            [
                "Torneo: Console_Prova\n",
                "Sito: Online, Data Inizio Torneo: Martedì 1 settembre 2026\n",
                "Dettaglio del turno 2 concluso\n",
                "\tPeriodo del Turno: Date non trovate\n",
                INTESTAZIONE_DELLE_PARTITE,
                "\t1  | 3   | NomeG3 CognomeG3         [1600] (2   ) - NomeG4 CognomeG4         [1500] (1   ) | 1-0\n",
                "\t2  | 4   | NomeG2 CognomeG2         [1700] (0.5 ) - NomeG1 CognomeG1         [1800] (0.5 ) | 1/2-1/2\n",
            ]
        ) + _versione()
        assert cestino_finto.tentativi == []
