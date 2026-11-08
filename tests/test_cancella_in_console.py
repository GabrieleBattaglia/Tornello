"""La lista di cancella nella versione a riga di comando, dalla 10.19.55
(decisione di Gabriele dell'8 novembre 2026).

Fra i risultati del turno corrente, cancella elenca le partite giocate,
tranne il riposo, e chiede quale cancellare. Dalla 10.19.55 la lista le
numera con il numero della scacchiera, Sc. seguito dal numero e dall'IDG,
come l'elenco delle partite da registrare e l'albero della finestra, e la
domanda accetta soltanto quel numero, come l'elenco: un numero che non e'
quello di una scacchiera della lista si rifiuta con Scelta non valida, e
il file del torneo resta com'era. Fino alla 10.19.54 la lista numerava 1,
2, 3 secondo la posizione, accanto all'IDG, e la domanda accettava quel
numero o l'IDG: nel turno 4 di Turni, con i risultati alle scacchiere 2 e
3, la lista diceva 1. IDG:14 e 2. IDG:15, e scrivendo 2, il numero che
l'albero e l'elenco delle partite da registrare danno a Esposito contro
Barbieri, la conferma chiedeva di cancellare Delfini contro Caruso, la
Scacchiera 3.
Il torneo e' Turni di test_canc_sui_turni, abbinato dal vero bbpPairings,
con il turno 4 abbinato: Alfieri contro Ferri alla 1, Esposito contro
Barbieri alla 2, Delfini contro Caruso alla 3. La console e' quella vera,
con il controller e le risposte a copione di test_console, senza suoni.
Tutto sta nella cartella temporanea della prova."""

import io
import os
from contextlib import redirect_stdout

import pytest
import test_canc_sui_turni as turni
import test_console as console
from test_console import Copione, _adattatore

muto = console.muto

LISTA = [
    "",
    "Partite completate nel turno 4 (N. Scacchiera del Turno):",
    "  Sc. 2  (IDG:14) - Elena Esposito vs Bruno Barbieri | Risultato: 1-0",
    "  Sc. 3  (IDG:15) - Dario Delfini vs Carla Caruso | Risultato: 0-1",
]
DOMANDA = "Inserisci il numero della scacchiera della partita da cancellare (o vuoto per annullare): "


def _turni_al_turno_4():
    """Turni con il turno 4 abbinato e i risultati soltanto alle
    scacchiere 2 e 3, registrati come li registra la console."""
    from tournament import _apply_match_result_to_players

    torneo, _fotografie, _ritirato = turni._torneo_vero(abbinati=4)
    turno = torneo["rounds"][3]
    partite = {m["id"]: m for m in turno["matches"]}
    assert sorted(partite) == [13, 14, 15]
    with redirect_stdout(io.StringIO()):
        _apply_match_result_to_players(torneo, partite[14], "1-0", 1.0, 0.0)
        _apply_match_result_to_players(torneo, partite[15], "0-1", 0.0, 1.0)
    return torneo


def _console(monkeypatch, tasti, conferme):
    """La console vera sul torneo Turni, salvato nel suo file come lo salva
    il controller: i risultati, poi No a Vuoi continuare. Risponde il
    copione, il percorso, i byte del file prima e la cartella prima."""
    import config
    from controller import TournamentController
    from models import Tournament

    torneo = _turni_al_turno_4()
    copione = Copione(monkeypatch, tasti=tasti, conferme=conferme)
    guida = TournamentController(_adattatore(copione))
    guida.tournament = Tournament.from_dict({k: v for k, v in torneo.items() if k != "players_dict"})
    guida.active_filename = config.user_data_path("Tornello - Turni.json")
    guida._save_state()
    with open(guida.active_filename, "rb") as f:
        prima = f.read()
    cartella = sorted(os.listdir(config.user_data_path("")))

    guida._main_loop()

    assert copione.tasti == [] and copione.conferme == []
    return copione, guida.active_filename, prima, cartella


def _risultati(percorso):
    from tournament import load_tournament

    salvato = load_tournament(percorso)
    return {m["id"]: m["result"] for m in salvato["rounds"][3]["matches"]}, {g["id"]: g["points"] for g in salvato["players"]}


def _la_lista(uscita):
    inizio = uscita.index("Partite completate nel turno 4 (N. Scacchiera del Turno):")
    return uscita[inizio - 1 : inizio + 3]


@pytest.mark.parametrize(
    "numero,cancellata,giocatori",
    [("2", 14, "Elena Esposito vs Bruno Barbieri"), ("3", 15, "Dario Delfini vs Carla Caruso")],
)
def test_si_cancella_la_partita_della_scacchiera_scritta(monkeypatch, muto, capsys, cestino_finto, numero, cancellata, giocatori):
    """La lista dice le scacchiere 2 e 3 con il loro numero e l'IDG; il
    numero di una di loro chiede di cancellare quella partita, e INVIO la
    cancella: il risultato sparisce, i punti tornano quelli di prima, e
    l'altra partita resta com'era."""
    copione, percorso, _prima, _cartella = _console(monkeypatch, ["cancella", numero, ""], [True, False])

    uscita = capsys.readouterr().out.splitlines()
    assert _la_lista(uscita) == LISTA
    assert copione.domande[1] == DOMANDA
    assert copione.domande[2] == f"Confermi la CANCELLAZIONE del risultato per {giocatori}? (INVIO|ESCAPE): "
    assert "Risultato cancellato e punteggi ricalcolati." in uscita
    risultati, _punti = _risultati(percorso)
    attesi = {13: None, 14: "1-0", 15: "0-1"}
    attesi[cancellata] = None
    assert risultati == attesi
    assert cestino_finto.tentativi == []


@pytest.mark.parametrize("risposta", ["1", "4", "14", "15", "x"])
def test_un_numero_che_non_e_nella_lista_si_rifiuta(monkeypatch, muto, capsys, cestino_finto, risposta):
    """La Scacchiera 1, che non ha il risultato, una scacchiera che il
    turno non ha, gli IDG delle due partite della lista e una lettera: la
    console dice Scelta non valida, non chiede conferme e non cancella
    niente. Il file del torneo resta uguale byte per byte, e nella cartella
    non nasce niente."""
    import config

    copione, percorso, prima, cartella = _console(monkeypatch, ["cancella", risposta, ""], [False])

    uscita = capsys.readouterr().out.splitlines()
    assert _la_lista(uscita) == LISTA
    assert copione.domande[1] == DOMANDA
    assert uscita[uscita.index(LISTA[-1]) + 1] == "Scelta non valida."
    assert not any(d.startswith("Confermi la CANCELLAZIONE") for d in copione.domande)
    with open(percorso, "rb") as f:
        assert f.read() == prima
    assert sorted(os.listdir(config.user_data_path(""))) == cartella
    assert cestino_finto.tentativi == []


def test_come_l_elenco_delle_partite_da_registrare(monkeypatch, muto, capsys, cestino_finto):
    """L'elenco delle partite da registrare dice la Scacchiera 1 con lo
    stesso Sc. della lista, e anche lui accetta il numero della scacchiera
    e non l'IDG: 13, l'IDG della Scacchiera 1, si rifiuta."""
    copione, percorso, prima, _cartella = _console(monkeypatch, ["13", ""], [False])

    uscita = capsys.readouterr().out.splitlines()
    # L'elenco esce due volte: prima e dopo il rifiuto.
    assert [r.split(" - ", 1)[0] for r in uscita if r.startswith("    Sc. ")] == ["    Sc. 1  (IDG:13)"] * 2
    assert "Numero Scacchiera (del turno) '13' non valido o partita non pendente." in uscita
    with open(percorso, "rb") as f:
        assert f.read() == prima
    assert copione.domande[0].endswith("\nR|T|SC|nome|cognome [1]: ")
