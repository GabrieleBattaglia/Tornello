"""I numeri della classifica nel file del torneo, dalla 10.19.31 (decisione
di Gabriele del 7 novembre 2026).

Ogni salvataggio di un torneo in corso, o in preparazione, scrive nel file
i numeri della classifica del torneo che salva, gli stessi della classifica
del turno scritta subito dopo: Buchholz, Buchholz Cut-1, ARO, performance,
fattore K, variazione Elo, la posizione in display_rank e RIT in final_rank
per un ritirato. Fino alla 10.19.30 li ricalcolava soltanto la classifica,
scritta dopo il salvataggio, e nel file restavano quelli del salvataggio
prima: il 6 novembre 2026, in Autunneo2, il salvataggio del PGN di una
partita ha scritto i numeri del risultato inserito prima. In console, che
scrive la classifica su una copia del torneo, restavano quelli letti
all'apertura.
Le prove passano dalla finestra principale vera, mai mostrata, dalla
console guidata da un copione e da save_tournament. Un ricalcolo che non
riesce non ferma il salvataggio: il torneo si salva con i numeri di prima,
e la console lo dice. Un torneo concluso tiene i valori della
finalizzazione. Tutto sta nella cartella temporanea della prova, i suoni
sono muti e le finestre di messaggio finte."""

import copy
import json
import os
import re
from types import SimpleNamespace

import pytest

# I numeri della classifica che il file del torneo tiene per ogni giocatore.
CAMPI = ("points", "buchholz", "buchholz_cut1", "aro", "performance_rating", "k_factor", "elo_change", "display_rank", "final_rank")

# Sei giocatori, dal piu' forte, per identificativo, cognome, nome ed Elo.
GIOCATORI = (
    ("ALF", "Alfieri", "Aldo", 1800),
    ("BRU", "Bruni", "Bianca", 1700),
    ("CAR", "Caruso", "Carlo", 1600),
    ("DON", "Donati", "Diana", 1500),
    ("ESP", "Esposito", "Elio", 1450),
    ("FAB", "Fabbri", "Fabio", 1400),
)

# Le partite dei tre turni giocati, con il punteggio del Bianco. Al turno 3
# Alfieri contro Bruni e' ancora da giocare.
PARTITE = (
    (1, 1, "ALF", "DON", "1-0", 1.0),
    (2, 1, "BRU", "ESP", "1/2-1/2", 0.5),
    (3, 1, "CAR", "FAB", "0-1", 0.0),
    (4, 2, "ALF", "FAB", "1/2-1/2", 0.5),
    (5, 2, "BRU", "CAR", "1-0", 1.0),
    (6, 2, "DON", "ESP", "0-1", 0.0),
    (7, 3, "ALF", "BRU", None, None),
    (8, 3, "ESP", "FAB", "1/2-1/2", 0.5),
    (9, 3, "CAR", "DON", "1-0", 1.0),
)


def _torneo(nome="Spareggi"):
    """Il torneo al turno 3 di 5, con la partita fra Alfieri e Bruni da
    giocare, e con i numeri che la classifica gli ha dato: quelli che il
    salvataggio prima del risultato ha lasciato nel file."""
    from reports import get_standings_text

    giocatori = [
        {"id": codice, "last_name": cognome, "first_name": nome_proprio, "initial_elo": elo, "current_elo": elo, "points": 0.0, "withdrawn": False, "results_history": []}
        for codice, cognome, nome_proprio, elo in GIOCATORI
    ]
    per_id = {g["id"]: g for g in giocatori}
    turni = {}
    for numero, turno, bianco, nero, risultato, punti_del_bianco in PARTITE:
        turni.setdefault(turno, []).append({"id": numero, "round": turno, "white_player_id": bianco, "black_player_id": nero, "result": risultato})
        if risultato is None:
            continue
        per_id[bianco]["results_history"].append({"round": turno, "opponent_id": nero, "color": "white", "result": risultato, "score": punti_del_bianco})
        per_id[nero]["results_history"].append({"round": turno, "opponent_id": bianco, "color": "black", "result": risultato, "score": 1.0 - punti_del_bianco})
    for g in giocatori:
        g["points"] = sum(v["score"] for v in g["results_history"])
    torneo = {
        "name": nome,
        "tournament_id": nome.upper(),
        "start_date": "2026-11-01",
        "end_date": "2026-11-30",
        "total_rounds": 5,
        "current_round": 3,
        "next_match_id": len(PARTITE) + 1,
        "tournament_category": "standard",
        "players": giocatori,
        "rounds": [{"round": turno, "matches": partite} for turno, partite in sorted(turni.items())],
        "players_dict": per_id,
    }
    get_standings_text(torneo)
    return torneo


def _scrivi(percorso, torneo):
    """Il file del torneo, come lo scrive un salvataggio: senza
    players_dict."""
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in torneo.items() if k != "players_dict"}, f, indent=1)


def _dal_file(percorso):
    with open(percorso, encoding="utf-8") as f:
        return json.load(f)


def _numeri(torneo):
    """I numeri della classifica di ogni giocatore, per identificativo."""
    return {g["id"]: {campo: g.get(campo) for campo in CAMPI} for g in torneo["players"]}


def _numeri_della_classifica(torneo):
    """I numeri che la classifica calcola per il torneo, su una sua copia:
    quelli che la classifica scritta dopo il salvataggio mostra."""
    from reports import get_standings_text

    copia = copy.deepcopy(torneo)
    get_standings_text(copia)
    return _numeri(copia)


def _righe_della_classifica(percorso):
    """Le righe dei giocatori nel file della classifica, per cognome: la
    posizione e le colonne dopo l'Elo iniziale, cioe' punti, BH-C1, BH, ARO,
    RTNG e, quando ci sono, Perf ed Elo Var."""
    with open(percorso, encoding="utf-8-sig") as f:
        testo = f.read()
    righe = {}
    for riga in testo.splitlines():
        trovato = re.match(r"^\s*(\d+|RIT)\s.{8}.{4}(.{27}) \[\s*\d+\]\s+(.*)$", riga)
        if trovato:
            cognome = trovato.group(2).split(",")[0].strip()
            righe[cognome] = (trovato.group(1), trovato.group(3).replace("[RITIRATO]", "").split())
    return righe


def _come_nella_classifica(giocatore, riga):
    """I numeri del giocatore come li scrive la sua riga della classifica,
    accanto a quelli del file: posizione e punti, e per chi non e' ritirato
    BH-C1, BH e ARO; Perf ed Elo Var. quando la classifica li mostra."""
    posizione, colonne = riga
    nel_file = {
        "display_rank": giocatore["display_rank"],
        "points": giocatore["points"],
    }
    scritti = {
        "display_rank": posizione if posizione == "RIT" else int(posizione),
        "points": float(colonne[0]),
    }
    if not giocatore.get("withdrawn"):
        nel_file.update(buchholz_cut1=giocatore["buchholz_cut1"], buchholz=giocatore["buchholz"], aro=giocatore["aro"])
        scritti.update(buchholz_cut1=float(colonne[1]), buchholz=float(colonne[2]), aro=int(colonne[3]))
    if len(colonne) > 5:
        nel_file["elo_change"] = giocatore["elo_change"]
        scritti["elo_change"] = int(colonne[6])
        if not giocatore.get("withdrawn"):
            nel_file["performance_rating"] = giocatore["performance_rating"]
            scritti["performance_rating"] = int(colonne[5])
    return nel_file, scritti


@pytest.fixture
def suoni(app_grafica, monkeypatch):
    import utils

    suonati = []
    monkeypatch.setattr(utils, "play_sound", lambda nome, *a, **k: suonati.append(nome) or True)
    monkeypatch.setattr(utils, "bip_di_scelta", lambda *a, **k: None)
    return suonati


@pytest.fixture
def finestre(monkeypatch):
    """Le finestre di messaggio della finestra principale, annotate con
    titolo e testo: le prove non ne aspettano nessuna."""
    import wx

    import gui.main_frame as mf

    annotate = []

    class DialogoFinto:
        def __init__(self, genitore, titolo, messaggio, *a, **k):
            annotate.append((titolo, messaggio))

        def ShowModal(self):
            return wx.ID_YES

        def Destroy(self):
            pass

    monkeypatch.setattr(mf, "AccessibleMsgDialog", DialogoFinto)
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: annotate.append(a))
    return annotate


@pytest.fixture
def principale(app_grafica, suoni, finestre, monkeypatch):
    """La finestra principale, mai mostrata, senza i controlli dell'avvio."""
    import gui.main_frame as mf
    from gui.settings import DEFAULT_SETTINGS

    for nome in ("_check_fide_db_on_startup", "_check_backup_on_startup", "_scan_and_load_initial_tournament", "_check_updates_async"):
        monkeypatch.setattr(mf.MainFrame, nome, lambda self: None)
    monkeypatch.setattr(mf.MainFrame, "Maximize", lambda self, *a: None)
    finestra = mf.MainFrame(None, "Tornello", dict(DEFAULT_SETTINGS))
    finestra._timer_pie_di_pagina.Stop()
    for nome in ("main_text", "tree_ctrl", "status_text"):
        getattr(finestra, nome).SetFocus = lambda: None
    yield finestra
    finestra.Destroy()


def _aperto(principale, torneo=None):
    """Il torneo scritto nella cartella del programma, con i numeri del
    salvataggio prima, e aperto nella finestra. Restituisce il file del
    torneo, il file della classifica e il torneo come era nel file."""
    from config import user_data_path

    torneo = torneo or _torneo()
    percorso = user_data_path(f"Tornello - {torneo['name']}.json")
    _scrivi(percorso, torneo)
    prima = _dal_file(percorso)
    principale.load_tournament(percorso)
    assert principale.current_tournament is not None
    classifica = user_data_path(f"Tornello - {torneo['name']} - Classifica.txt")
    return SimpleNamespace(percorso=percorso, classifica=classifica, prima=prima)


def _partita(principale, numero):
    for turno in principale.current_tournament["rounds"]:
        for partita in turno["matches"]:
            if partita["id"] == numero:
                return partita
    raise AssertionError(numero)


class TestNellaFinestra:
    """La finestra salva il torneo con _save_state, e scrive poi la
    classifica: il file del torneo deve avere i numeri di quella classifica."""

    def test_il_risultato_porta_nel_file_i_numeri_della_classifica(self, principale, finestre):
        """Alfieri batte Bruni al turno 3. Nel file i due giocatori e i loro
        avversari dei turni prima, Donati e Fabbri per Alfieri, Esposito e
        Caruso per Bruni, hanno i numeri della classifica scritta dopo, e
        tutti i giocatori quelli che la classifica calcola dal file."""
        aperto = _aperto(principale)

        principale.apply_match_result(_partita(principale, 7), "1-0")

        salvato = _dal_file(aperto.percorso)
        assert _partita(SimpleNamespace(current_tournament=salvato), 7)["result"] == "1-0"
        nel_file = {g["last_name"]: g for g in salvato["players"]}
        righe = _righe_della_classifica(aperto.classifica)
        for cognome in ("Alfieri", "Bruni", "Donati", "Fabbri", "Esposito", "Caruso"):
            dal_file, dalla_classifica = _come_nella_classifica(nel_file[cognome], righe[cognome])
            assert dal_file == dalla_classifica, cognome
        assert _numeri(salvato) == _numeri_della_classifica(salvato)
        assert _numeri(salvato) == _numeri(principale.current_tournament)
        # Il risultato cambia i numeri di prima: Alfieri sale in testa, e il
        # Buchholz di Donati e di Fabbri, che lo hanno incontrato, cresce.
        prima = {g["last_name"]: g for g in aperto.prima["players"]}
        assert (prima["Alfieri"]["display_rank"], nel_file["Alfieri"]["display_rank"]) == (4, 1)
        for cognome in ("Donati", "Fabbri"):
            assert nel_file[cognome]["buchholz"] == prima[cognome]["buchholz"] + 1.0, cognome
        assert finestre == []

    def test_il_salvataggio_dopo_il_risultato_non_cambia_i_numeri(self, principale, finestre):
        """Il caso di Autunneo2 del 6 novembre 2026: dopo un risultato, il
        salvataggio del PGN di un'altra partita scriveva nel file i numeri
        di quel risultato, perche' il salvataggio del risultato aveva
        scritto quelli di prima. Adesso il Buchholz di Donati passa da 4.5 a
        5.5 gia' con il salvataggio del risultato, e il salvataggio del PGN
        non cambia niente."""
        aperto = _aperto(principale)
        donati_prima = next(g for g in aperto.prima["players"] if g["id"] == "DON")
        assert (donati_prima["buchholz"], donati_prima["display_rank"]) == (4.5, 6)

        principale.apply_match_result(_partita(principale, 7), "1-0")
        dopo_il_risultato = _dal_file(aperto.percorso)
        donati = next(g for g in dopo_il_risultato["players"] if g["id"] == "DON")
        assert (donati["buchholz"], donati["display_rank"]) == (5.5, 6)

        partita = _partita(principale, 8)
        partita["pgn"] = '[Event "Spareggi"]\n[Result "1/2-1/2"]\n\n1. e4 e5 1/2-1/2'
        principale.apply_match_result(partita, None, is_pgn_only=True)

        dopo_il_pgn = _dal_file(aperto.percorso)
        assert _partita(SimpleNamespace(current_tournament=dopo_il_pgn), 8)["pgn"]
        assert _numeri(dopo_il_pgn) == _numeri(dopo_il_risultato)
        assert finestre == []

    def test_il_ritirato_ha_nel_file_rit_e_la_performance_vuota(self, principale, finestre):
        """Caruso si ritira: nel file ha RIT in final_rank e in display_rank,
        come nella classifica, la performance None e la variazione Elo delle
        partite giocate prima del ritiro; gli altri hanno le posizioni della
        classifica scritta dopo."""
        aperto = _aperto(principale)
        caruso_prima = next(g for g in aperto.prima["players"] if g["id"] == "CAR")
        assert (caruso_prima.get("final_rank"), caruso_prima["display_rank"]) == (None, 5)

        principale.withdraw_player("CAR")

        salvato = _dal_file(aperto.percorso)
        caruso = next(g for g in salvato["players"] if g["id"] == "CAR")
        assert caruso["withdrawn"] is True
        assert (caruso.get("final_rank"), caruso["display_rank"], caruso["performance_rating"]) == ("RIT", "RIT", None)
        assert caruso["elo_change"] == -30
        righe = _righe_della_classifica(aperto.classifica)
        assert righe["Caruso"][0] == "RIT"
        for giocatore in salvato["players"]:
            dal_file, dalla_classifica = _come_nella_classifica(giocatore, righe[giocatore["last_name"]])
            assert dal_file == dalla_classifica, giocatore["last_name"]
        assert _numeri(salvato) == _numeri_della_classifica(salvato)
        assert finestre == []

    def test_il_torneo_in_preparazione_nasce_con_le_posizioni_di_partenza(self, principale, finestre, tmp_path):
        """La procedura guidata scrive il primo file del torneo: i quattro
        iscritti hanno le posizioni dell'elenco iniziale, dal piu' forte, il
        fattore K 40 di chi il database non ha e la variazione zero, come la
        classifica scritta dopo. Fino alla 10.19.30 avevano posizione, K e
        variazione None."""
        from config import user_data_path

        iscritti = [
            {"id": "VER", "first_name": "Anna", "last_name": "Verdi", "current_elo": 1500},
            {"id": "BIA", "first_name": "Luca", "last_name": "Bianchi", "current_elo": 1700},
            {"id": "RUS", "first_name": "Marco", "last_name": "Russo", "current_elo": 1400},
            {"id": "NER", "first_name": "Paolo", "last_name": "Neri", "current_elo": 1600},
        ]
        principale.start_new_tournament_wizard()
        principale.creation_data["name"] = "Spareggi Nuovo"
        principale.creation_data["save_path"] = str(tmp_path)

        principale.create_tournament_from_wizard(iscritti)

        salvato = _dal_file(user_data_path("Tornello - Spareggi_Nuovo.json"))
        assert salvato["rounds"] == []
        numeri = _numeri(salvato)
        assert {pid: numeri[pid]["display_rank"] for pid in numeri} == {"BIA": 1, "NER": 2, "VER": 3, "RUS": 4}
        assert {(n["k_factor"], n["elo_change"], n["buchholz"]) for n in numeri.values()} == {(40, 0, 0.0)}
        assert numeri == _numeri_della_classifica(salvato)
        righe = _righe_della_classifica(os.path.join(tmp_path, "Tornello - Spareggi_Nuovo - Classifica.txt"))
        assert {cognome: int(riga[0]) for cognome, riga in righe.items()} == {"Bianchi": 1, "Neri": 2, "Verdi": 3, "Russo": 4}
        assert finestre == []


class TestInConsole:
    """La console salva il torneo con _save_state del controller, che scrive
    la classifica su una copia del torneo: fino alla 10.19.30 nel file
    restavano i numeri letti all'apertura, o quelli di un torneo appena
    creato, senza posizione, K e variazione."""

    def test_i_risultati_portano_nel_file_i_numeri_della_classifica(self, monkeypatch):
        from test_console import Copione, _adattatore, _controller, _torneo_al_primo_turno

        import utils
        from config import user_data_path

        monkeypatch.setattr(utils, "play_sound", lambda *a, **k: True)
        # Scacchiera 1: G1 batte G3; scacchiera 2: G4 e G2 pattano; INVIO
        # vuoto chiude l'inserimento. Ogni risultato chiede conferma.
        copione = Copione(monkeypatch, tasti=["1", "1-0", "2", "1/2", ""], conferme=[True, True])
        adattatore = _adattatore(copione)
        guida = _controller(adattatore, _torneo_al_primo_turno())

        assert adattatore.update_match_results(guida.tournament) is True
        guida._save_state()

        salvato = _dal_file(guida.active_filename)
        numeri = _numeri(salvato)
        assert {pid: n["display_rank"] for pid, n in numeri.items()} == {"G1": 1, "G4": 2, "G2": 3, "G3": 4}
        assert numeri["G3"]["buchholz"] == 1.0
        assert all(n["k_factor"] == 40 and n["elo_change"] is not None for n in numeri.values())
        assert numeri == _numeri_della_classifica(salvato)
        righe = _righe_della_classifica(user_data_path("Tornello - Console_Prova - Classifica.txt"))
        for giocatore in salvato["players"]:
            dal_file, dalla_classifica = _come_nella_classifica(giocatore, righe[giocatore["last_name"]])
            assert dal_file == dalla_classifica, giocatore["last_name"]


class TestSaveTournament:
    """save_tournament, la strada di tutti i salvataggi: finestra, console,
    Time Machine e rimozione di un iscritto da un torneo che non e' aperto."""

    @pytest.mark.parametrize("arrivo", [1, 0])
    def test_la_time_machine_scrive_i_numeri_del_turno_a_cui_torna(self, tmp_path, arrivo):
        """La Time Machine salva una copia del torneo con i turni dopo
        quello di arrivo tolti: il file ha i numeri di quel turno, o, in
        preparazione, le posizioni di partenza, e non quelli del turno 3."""
        from tournament import save_tournament, torna_al_turno

        torneo = _torneo()
        torna_al_turno(torneo, arrivo)
        percorso = str(tmp_path / "Tornello - Spareggi.json")

        assert save_tournament(torneo, filepath=percorso)

        salvato = _dal_file(percorso)
        assert len(salvato["rounds"]) == arrivo
        assert _numeri(salvato) == _numeri_della_classifica(salvato)
        attese = {"ALF": 1, "BRU": 2, "CAR": 3, "DON": 4, "ESP": 5, "FAB": 6} if arrivo == 0 else {"FAB": 1, "ALF": 2, "ESP": 3, "BRU": 4, "DON": 5, "CAR": 6}
        assert {g["id"]: g["display_rank"] for g in salvato["players"]} == attese

    def test_un_ricalcolo_che_non_riesce_non_ferma_il_salvataggio(self, tmp_path, monkeypatch, capsys):
        """Se il calcolo solleva un errore, il torneo si salva lo stesso,
        con il risultato nuovo e con i numeri di prima, tutti, anche quelli
        che il calcolo aveva gia' cambiato, nel file e in memoria, e la
        console lo dice."""
        import reports
        from tournament import _apply_match_result_to_players, save_tournament

        torneo = _torneo()
        partita = torneo["rounds"][2]["matches"][0]
        _apply_match_result_to_players(torneo, partita, "1-0", 1.0, 0.0)
        prima = _numeri(torneo)
        players_dict = torneo["players_dict"]
        calcolati = []
        vera = reports.aggiorna_i_numeri_in_corso

        def calcola_e_annota(t, *a, **k):
            vera(t, *a, **k)
            calcolati.append(_numeri(t))

        def guasto(*a, **k):
            raise RuntimeError("guasto di prova")

        monkeypatch.setattr(reports, "aggiorna_i_numeri_in_corso", calcola_e_annota)
        monkeypatch.setattr(reports, "ordina_la_classifica_in_corso", guasto)
        percorso = str(tmp_path / "Tornello - Spareggi.json")
        capsys.readouterr()

        assert save_tournament(torneo, filepath=percorso)

        salvato = _dal_file(percorso)
        assert salvato["rounds"][2]["matches"][0]["result"] == "1-0"
        assert calcolati and calcolati[0] != prima
        assert _numeri(salvato) == prima
        assert _numeri(torneo) == prima
        assert torneo["players_dict"] is players_dict
        assert (
            "Avviso: i numeri della classifica del torneo Spareggi non si sono potuti ricalcolare prima del salvataggio, e il file li salva come erano: guasto di prova"
            in capsys.readouterr().out
        )

    def test_un_torneo_concluso_tiene_i_numeri_della_finalizzazione(self, tmp_path):
        """Il torneo concluso non si ricalcola: i numeri sono quelli che la
        finalizzazione ha calcolato e salvato. E' il comportamento di prima,
        che il ricalcolo non deve toccare."""
        from tournament import save_tournament

        torneo = _torneo()
        torneo["concluded"] = True
        for posizione, giocatore in enumerate(torneo["players"], start=1):
            giocatore.update(final_rank=posizione, display_rank=posizione, buchholz=10.0 + posizione, elo_change=posizione)
        prima = _numeri(torneo)
        percorso = str(tmp_path / "Tornello - Spareggi.json")

        assert save_tournament(torneo, filepath=percorso)

        assert _numeri(_dal_file(percorso)) == prima
        assert _numeri(torneo) == prima

    def test_il_file_ha_le_stesse_chiavi_di_prima(self, tmp_path):
        """Nessun campo nuovo e nessun campo tolto: il file resta leggibile
        dalle versioni di prima."""
        from tournament import save_tournament

        torneo = _torneo()
        chiavi_del_torneo = set(torneo) - {"players_dict"}
        chiavi_dei_giocatori = [set(g) | {"opponents"} for g in torneo["players"]]
        percorso = str(tmp_path / "Tornello - Spareggi.json")

        assert save_tournament(torneo, filepath=percorso)

        salvato = _dal_file(percorso)
        assert set(salvato) == chiavi_del_torneo
        assert [set(g) for g in salvato["players"]] == chiavi_dei_giocatori
