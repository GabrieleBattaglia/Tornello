"""Le scacchiere nel file dei dettagli di un turno concluso, dalla 10.19.54
(decisione di Gabriele dell'8 novembre 2026).

Il file Tornello - nome - Turno N Dettagli.txt numera le scacchiere come
l'albero della finestra, con la stessa funzione, numeri_delle_scacchiere di
reports: le partite in ordine di identificativo, che e' l'ordine in cui le
da' bbpPairings, quello dell'articolo 3.6 di C.04.2, con il riposo in fondo,
che nel file ha bye al posto del numero. Fino alla 10.19.53 le partite del
file erano in ordine di Elo medio, dal piu' alto: nel Turno 3 di Prova time
machine, sul banco del collaudo, la scacchiera 1 del file era la Scacchiera
2 dell'albero.
I tornei sono abbinati dal vero bbpPairings: Turni, il torneo di otto
giocatori di test_canc_sui_turni, e quello di quattro giocatori delle prove
della console. Le prove della finestra girano sulla finestra principale
vera, mai mostrata, con i suoni annotati e la finestra del risultato finta;
quelle della console con le risposte a copione. Tutto sta nella cartella
temporanea della prova."""

import io
import os
import re
from contextlib import redirect_stdout
from types import SimpleNamespace

import test_canc_sui_turni as turni
import test_console as console
from test_canc_nell_albero import _voce_della_partita
from test_console import Copione, _adattatore, _controller, _torneo_al_primo_turno

# Le fixture della finestra principale, come nelle prove di CANC sui turni,
# e i suoni muti della console.
principale = turni.principale
suoni = turni.suoni
muto = console.muto

# Il Turno 3 del torneo Turni come lo abbina bbpPairings, in ordine di
# identificativo: scacchiera, identificativo, bianco e nero; Caruso riposa.
# Per Elo medio l'ordine sarebbe 11, 9, 10: la scacchiera 1 del file era
# Barbieri contro Delfini, la Scacchiera 3 dell'albero.
TURNO_3 = (
    (1, 9, "Alfieri Anna", "Galli Giulia"),
    (2, 10, "Ferri Fabio", "Esposito Elena"),
    (3, 11, "Barbieri Bruno", "Delfini Dario"),
)
RIPOSO_3 = (4, 12, "Caruso Carla")

RIGA_DI_PARTITA = re.compile(r"\t(\S+)\s*\| (\d+)\s*\| (.+?)\s+\[[^]]*\] \([^)]*\) - (.+?)\s+(?:\[[^]]*\] \([^)]*\) )?\| (\S+)$")


def _righe_delle_partite(percorso):
    """Le righe delle partite del file dei dettagli, in ordine: scacchiera,
    come la scrive il file, identificativo, bianco, nero e risultato."""
    with open(percorso, encoding="utf-8-sig") as f:
        righe = f.read().splitlines()
    trovate = []
    for riga in righe:
        m = RIGA_DI_PARTITA.match(riga)
        if m:
            trovate.append((m.group(1), int(m.group(2)), m.group(3), m.group(4), m.group(5)))
    return trovate


def _voci_delle_partite(principale, percorso, numero):
    """Le voci delle partite del turno nell'albero, in qualunque ramo
    stiano, per identificativo."""
    albero = principale.tree_ctrl
    trovate = {}

    def visita(voce):
        figlio, cookie = albero.GetFirstChild(voce)
        while figlio.IsOk():
            dati = albero.GetItemData(figlio)
            if isinstance(dati, dict) and dati.get("action") == "activate_match" and dati.get("filepath") == percorso and dati.get("round") == numero:
                trovate[dati["match"]["id"]] = figlio
            visita(figlio)
            figlio, cookie = albero.GetNextChild(voce, cookie)

    visita(principale.tree_root)
    return trovate


def _elo_medio(torneo, partita):
    giocatori = {g["id"]: g for g in torneo["players"]}
    return (giocatori[partita["white_player_id"]]["initial_elo"] + giocatori[partita["black_player_id"]]["initial_elo"]) / 2


def _per_elo_medio(torneo, numero):
    """Gli identificativi delle partite del turno, senza il riposo, come li
    ordinava il file fino alla 10.19.53: per Elo medio, dal piu' alto."""
    turno = next(r for r in torneo["rounds"] if r["round"] == numero)
    partite = [m for m in turno["matches"] if m.get("black_player_id")]
    return [m["id"] for m in sorted(partite, key=lambda m: _elo_medio(torneo, m), reverse=True)]


def _come_fino_alla_10_19_53(torneo, numero, percorso):
    """Riscrive il file dei dettagli del turno come lo scriveva la 10.19.53:
    le righe delle partite per Elo medio, dal piu' alto, numerate da 1 in
    quell'ordine, il riposo in fondo, e in fondo la riga della versione di
    allora. Restituisce i byte del file."""
    with open(percorso, encoding="utf-8-sig") as f:
        righe = f.read().split("\n")
    posti = [i for i, riga in enumerate(righe) if RIGA_DI_PARTITA.match(riga) and not riga.startswith("\tbye")]
    per_id = {int(RIGA_DI_PARTITA.match(righe[i]).group(2)): righe[i] for i in posti}
    for nuovo, (posto, ident) in enumerate(zip(posti, _per_elo_medio(torneo, numero), strict=True), 1):
        riga = per_id[ident]
        righe[posto] = "\t" + f"{nuovo:<3}| " + riga.split("| ", 1)[1]
    testo = "\n".join(righe)
    testo = re.sub(r"\n\nTornello \(.*\)\n\Z", "\n\nTornello (10.19.53)\n", testo, flags=re.S)
    with open(percorso, "w", encoding="utf-8-sig") as f:
        f.write(testo)
    with open(percorso, "rb") as f:
        return f.read()


def test_i_numeri_vengono_dagli_identificativi():
    """Le partite in ordine di identificativo, numerate da 1, con il
    riposo; l'ordine in cui il turno le tiene non conta."""
    from reports import numeri_delle_scacchiere

    turno = {
        "round": 2,
        "matches": [
            {"id": 7, "white_player_id": "C", "black_player_id": "D", "result": None},
            {"id": 8, "white_player_id": "E", "black_player_id": None, "result": "BYE"},
            {"id": 5, "white_player_id": "A", "black_player_id": "F", "result": "1-0"},
            {"id": 6, "white_player_id": "B", "black_player_id": "G", "result": None},
        ],
    }

    assert numeri_delle_scacchiere(turno) == {5: 1, 6: 2, 7: 3, 8: 4}
    assert numeri_delle_scacchiere({"round": 1, "matches": []}) == {}


def test_il_numero_del_file_e_quello_dell_albero_anche_col_riposo_in_mezzo(tmp_path):
    """Un turno che ha il riposo fra le partite, per identificativo: il
    numero della scacchiera, nel file come nell'albero, resta quello che da'
    numeri_delle_scacchiere, e il riposo, che nel file ha bye, sta in
    fondo. bbpPairings e la composizione a mano mettono il riposo in fondo:
    il turno qui e' scritto a mano."""
    from reports import append_completed_round_to_history_file, file_dei_dettagli_del_turno, numeri_delle_scacchiere

    giocatori = [
        {"id": codice, "first_name": codice, "last_name": "Prova", "initial_elo": elo, "points": 0.0, "results_history": []}
        for codice, elo in (("A", 1500), ("B", 1600), ("C", 1700), ("D", 1800), ("E", 1400))
    ]
    turno = {
        "round": 1,
        "matches": [
            {"id": 1, "round": 1, "white_player_id": "A", "black_player_id": "B", "result": "1-0"},
            {"id": 2, "round": 1, "white_player_id": "E", "black_player_id": None, "result": "BYE"},
            {"id": 3, "round": 1, "white_player_id": "C", "black_player_id": "D", "result": "0-1"},
        ],
    }
    torneo = {"name": "Riposo", "start_date": "2026-11-01", "custom_save_path": str(tmp_path), "players": giocatori, "rounds": [turno]}

    with redirect_stdout(io.StringIO()):
        append_completed_round_to_history_file(torneo, 1)

    assert numeri_delle_scacchiere(turno) == {1: 1, 2: 2, 3: 3}
    assert [(s, i) for s, i, *_resto in _righe_delle_partite(file_dei_dettagli_del_turno(torneo, 1))] == [("1", 1), ("3", 3), ("bye", 2)]


class TestNellaFinestra:
    """Il Turno 3 di Turni, abbinato e senza risultati: i tre risultati si
    registrano dalla finestra del risultato, aperta con INVIO sulla partita
    nell'albero, e l'ultimo conclude il turno, che scrive il file."""

    def _finestra_del_risultato(self, monkeypatch, risultati):
        """Al posto della finestra del risultato: annota come l'apre la
        finestra principale, sceglie il risultato della sua scacchiera e
        conferma."""
        import wx

        from gui.dialogs import result_dialog

        aperte = []

        class Risultato:
            def __init__(self, *a, **k):
                aperte.append(k)
                self.scacchiera = k["board_num"]
                self.selected_action = None
                self.txt_pgn = SimpleNamespace(GetValue=lambda: "")

            def ShowModal(self):
                return wx.ID_OK

            def get_selected_result(self):
                return risultati[self.scacchiera]

            def Destroy(self):
                pass

        monkeypatch.setattr(result_dialog, "ResultDialog", Risultato)
        return aperte

    def test_il_file_numera_le_scacchiere_come_l_albero(self, principale, suoni, monkeypatch, cestino_finto):
        torneo, _fotografie, _ritirato = turni._torneo_vero(abbinati=3)
        # Il caso c'e': per Elo medio l'ordine sarebbe un altro.
        assert _per_elo_medio(torneo, 3) == [11, 9, 10]
        percorso = turni._apri(principale, torneo)
        risultati = {9: "1-0", 10: "0-1", 11: "1/2-1/2"}
        aperte = self._finestra_del_risultato(monkeypatch, {s: risultati[i] for s, i, _b, _n in TURNO_3})
        albero = principale.tree_ctrl
        for scacchiera, ident, bianco, nero in TURNO_3:
            voce = _voce_della_partita(principale, percorso, 3, scacchiera, ident)
            assert albero.GetItemText(voce) == f"Scacchiera {scacchiera}: {bianco} vs {nero} (Non pianificata)"
            suoni.clear()
            with redirect_stdout(io.StringIO()):
                principale.on_tree_item_activated(SimpleNamespace(GetItem=lambda voce=voce: voce))

        # La finestra del risultato di ogni partita, Risultato Scacchiera
        # seguito dal numero, ha il numero della voce.
        partite = {m["id"]: m for m in principale.current_tournament["rounds"][2]["matches"]}
        assert [(k["board_num"], k["white_id"], k["black_id"]) for k in aperte] == [
            (s, partite[i]["white_player_id"], partite[i]["black_player_id"]) for s, i, _b, _n in TURNO_3
        ]
        # L'ultimo risultato conclude il turno: il suono della fine del
        # turno, e il cursore sul calcolo del turno successivo.
        assert "conclusione_turno" in suoni
        assert albero.GetItemText(albero.GetSelection()) == "calcola il turno successivo"
        # Nell'albero, fra le giocate, le partite con i loro numeri, e il
        # riposo dopo l'ultima scacchiera.
        for scacchiera, ident, bianco, nero in TURNO_3:
            voce = _voce_della_partita(principale, percorso, 3, scacchiera, ident)
            assert albero.GetItemText(voce) == f"Scacchiera {scacchiera}: {bianco} vs {nero} [{risultati[ident]}]"
        scacchiera, ident, chi_riposa = RIPOSO_3
        assert albero.GetItemText(_voce_della_partita(principale, percorso, 3, scacchiera, ident)) == f"Scacchiera {scacchiera}: {chi_riposa} - BYE [BYE]"
        # Nel file le stesse scacchiere, nello stesso ordine, con i nomi
        # scritti nome e cognome, e il riposo in fondo.
        dettagli = turni._dettagli(principale.current_tournament, 3)
        assert _righe_delle_partite(dettagli) == [
            *[(str(s), i, " ".join(reversed(b.split())), " ".join(reversed(n.split())), risultati[i]) for s, i, b, n in TURNO_3],
            ("bye", 12, "Carla Caruso", "BYE", "BYE"),
        ]
        # Lo stesso numero della voce dell'albero, e del dettaglio che
        # l'area centrale mostra quando la voce prende il cursore.
        voci = _voci_delle_partite(principale, percorso, 3)
        assert sorted(voci) == [9, 10, 11, 12]
        for scacchiera, ident, _bianco, _nero in (*TURNO_3, (*RIPOSO_3, None)):
            voce = voci[ident]
            assert albero.GetItemData(voce)["board_num"] == scacchiera
            assert albero.GetItemText(voce).startswith(f"Scacchiera {scacchiera}: ")
            albero.SelectItem(voce)
            assert principale.main_text.GetValue().splitlines()[:2] == ["DETTAGLIO PARTITA - TURNO 3", f"Scacchiera Numero: {scacchiera}"]


class TestInConsole:
    """Il torneo di quattro giocatori della console: nel turno 1 vincono G3
    e G4, e bbpPairings mette alla scacchiera 1 del turno 2 G3 e G4, a un
    punto, e alla 2 G1 e G2, a zero, che hanno l'Elo medio piu' alto. I
    risultati del turno 2 lo concludono, e la console scrive il file."""

    def test_il_file_numera_le_scacchiere_come_la_console(self, monkeypatch, muto, capsys):
        import config
        from tournament import load_tournament

        # Turno 1: G3 batte G1, G4 batte G2; INVIO vuoto, si continua, e si
        # abbina il turno 2. Turno 2: 1-0 alla scacchiera 1, patta alla 2;
        # INVIO vuoto, si continua, il turno 2 si conclude, e il turno 3 non
        # si abbina.
        copione = Copione(
            monkeypatch,
            tasti=["1", "0-1", "2", "1-0", "", "1", "1-0", "2", "1/2", ""],
            conferme=[True, True, True, True, True, True, True, False],
        )
        guida = _controller(_adattatore(copione), _torneo_al_primo_turno())

        guida._main_loop()

        assert copione.tasti == [] and copione.conferme == []
        salvato = load_tournament(guida.active_filename)
        turno_2 = sorted(salvato["rounds"][1]["matches"], key=lambda m: m["id"])
        assert [{m["white_player_id"], m["black_player_id"]} for m in turno_2] == [{"G3", "G4"}, {"G1", "G2"}]
        assert [m["id"] for m in turno_2] == [3, 4]
        assert _per_elo_medio(salvato, 2) == [4, 3]
        nomi = {p["id"]: f"{p['first_name']} {p['last_name']}" for p in salvato["players"]}
        uscita = capsys.readouterr().out.splitlines()
        # La console mostra le partite da registrare con i numeri
        # dell'albero.
        inizio = uscita.index("Partite del turno 2 ancora da registrare (N. Scacchiera del Turno):")
        assert [r.split(" - ", 1)[0] for r in uscita[inizio + 3 : inizio + 5]] == ["    Sc. 1  (IDG:3)", "    Sc. 2  (IDG:4)"]
        dettagli = os.path.abspath(config.user_data_path("Tornello - Console_Prova - Turno 2 Dettagli.txt"))
        assert f"Dettaglio Turno Concluso 2 salvato nel file separato '{dettagli}'" in uscita
        assert _righe_delle_partite(dettagli) == [
            ("1", 3, nomi[turno_2[0]["white_player_id"]], nomi[turno_2[0]["black_player_id"]], "1-0"),
            ("2", 4, nomi[turno_2[1]["white_player_id"]], nomi[turno_2[1]["black_player_id"]], "1/2-1/2"),
        ]
        # Il turno 1 aveva lo stesso ordine anche per Elo medio.
        primo = os.path.abspath(config.user_data_path("Tornello - Console_Prova - Turno 1 Dettagli.txt"))
        assert [(s, i) for s, i, *_resto in _righe_delle_partite(primo)] == [("1", 1), ("2", 2)]


class TestDopoIlRipristino:
    """I file scritti fino alla 10.19.53 restano come sono finche' il turno
    non si conclude di nuovo, o finche' un ripristino non li allinea con
    allinea_i_dettagli_dei_turni, come dalla 10.19.50: quello di un turno in
    cui l'ordine per Elo medio era un altro dice altro, e si riscrive, con
    le scacchiere dell'albero; quello di un turno in cui l'ordine era lo
    stesso resta com'e', anche con la riga della versione di allora."""

    def test_il_file_con_l_ordine_di_prima_si_riscrive(self, cestino_finto):
        from reports import allinea_i_dettagli_dei_turni

        torneo, _fotografie, _ritirato = turni._torneo_vero(abbinati=4, ultimo_completo=True)
        di_prima = {}
        for numero in (1, 2, 3, 4):
            di_prima[numero] = _come_fino_alla_10_19_53(torneo, numero, turni._dettagli(torneo, numero))
        # Nei turni 2 e 3 l'ordine per Elo medio e' un altro; nell'1 e nel 4
        # e' lo stesso.
        assert [r["round"] for r in torneo["rounds"] if _per_elo_medio(torneo, r["round"]) != sorted(_per_elo_medio(torneo, r["round"]))] == [2, 3]

        with redirect_stdout(io.StringIO()) as uscita:
            rimasti = allinea_i_dettagli_dei_turni(torneo, cestino_finto)

        assert rimasti == [] and cestino_finto.tentativi == []
        for numero in (1, 4):
            with open(turni._dettagli(torneo, numero), "rb") as f:
                assert f.read() == di_prima[numero]
        for numero in (2, 3):
            percorso = turni._dettagli(torneo, numero)
            with open(percorso, "rb") as f:
                assert f.read() != di_prima[numero]
            turno = next(r for r in torneo["rounds"] if r["round"] == numero)
            in_ordine = sorted(m["id"] for m in turno["matches"] if m.get("black_player_id"))
            assert [(s, i) for s, i, *_resto in _righe_delle_partite(percorso) if s != "bye"] == [(str(n), i) for n, i in enumerate(in_ordine, 1)]
        assert [r for r in uscita.getvalue().splitlines() if r.startswith("Dettaglio Turno Concluso")] == [
            f"Dettaglio Turno Concluso {n} salvato nel file separato '{turni._dettagli(torneo, n)}'" for n in (3, 2)
        ]
        assert [(s, i) for s, i, *_resto in _righe_delle_partite(turni._dettagli(torneo, 3))] == [("1", 9), ("2", 10), ("3", 11), ("bye", 12)]
