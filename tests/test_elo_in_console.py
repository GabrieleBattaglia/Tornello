"""L'Elo intero nella versione a riga di comando, dalla 10.19.63 (decisione
di Gabriele del 9 novembre 2026).

La console tiene i giocatori in Player di models, che ha l'Elo di partenza
con il punto zero, 1844.0. Fino alla 10.19.62 lo scriveva cosi' in quattro
posti: l'elenco delle partite da registrare e la ricerca per nome fra i
risultati del turno corrente, per esempio Sc. 1  (IDG:1) - NomeG1 CognomeG1
[1800.0], la lista Riepilogo Giocatori Iscritti al Torneo, che esce alla
fine dell'iscrizione, per esempio 1. ID: G1 - NomeG1 CognomeG1 (Elo:
1800.0), e il file del torneo sospeso, Tornello - nome_sospeso.txt, dove i
giocatori iscritti nella sessione avevano l'Elo intero e quelli di una
sessione di prima il punto zero. Adesso l'Elo e' intero dappertutto, con
elo_da_scrivere di utils, la funzione dei file dei dettagli, come nella
finestra. Il file del torneo tiene l'Elo come prima.
Le prove guidano il controller vero con le risposte a copione, nella
cartella temporanea della prova; il motore degli abbinamenti e' quello
vero, il cestino e' finto."""

import json
import os

import pytest
import test_console as console
from test_console import ELO, Copione, _adattatore, _controller, _torneo_al_primo_turno

muto = console.muto

# Il database dei giocatori: Mario Rossi si iscrive nella sessione.
ROSSI = {"id": "ROSMA001", "first_name": "Mario", "last_name": "Rossi", "current_elo": 1844}


def _cartella():
    """I file della cartella del programma, per nome."""
    import config

    cartella = config.user_data_path("")
    return sorted(n for n in os.listdir(cartella) if os.path.isfile(os.path.join(cartella, n)))


def _sospeso_con_il_database():
    """Il torneo Console_Prova sospeso dalla console in una sessione di
    prima, con i quattro giocatori in Player di models, l'Elo con il punto
    zero, e il database dei giocatori con Mario Rossi."""
    import config
    from models import Player, Tournament
    from tournament import save_tournament

    torneo = Tournament.from_dict(
        {
            "name": "Console_Prova",
            "tournament_id": "CONSOLE_PROVA",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "total_rounds": 3,
            "players": [
                Player.from_dict({"id": pid, "first_name": "Nome" + pid, "last_name": "Cognome" + pid, "initial_elo": float(elo), "current_elo": float(elo)}).to_dict()
                for pid, elo in ELO.items()
            ],
        }
    ).to_dict()
    torneo["creation_suspended"] = True
    assert save_tournament(torneo)
    with open(config.PLAYER_DB_FILE, "w", encoding="utf-8") as f:
        json.dump({"schema_version": 2, "players": [ROSSI]}, f)
    percorso = config.user_data_path("Tornello - Console_Prova.json")
    with open(percorso, encoding="utf-8") as f:
        # Il caso c'e': il torneo sospeso tiene l'Elo con il punto zero.
        assert [p["initial_elo"] for p in json.load(f)["players"]] == [1800.0, 1700.0, 1600.0, 1500.0]
    return percorso


def _ripresa(monkeypatch, tmp_path, tasti, conferme=()):
    """La ripresa della creazione di Console_Prova, con le risposte date."""
    from controller import TournamentController

    monkeypatch.chdir(tmp_path)
    copione = Copione(monkeypatch, tasti=tasti, conferme=conferme)
    guida = TournamentController(_adattatore(copione))
    return copione, guida


class TestLaListaDegliIscritti:
    """La lista Riepilogo Giocatori Iscritti al Torneo, alla fine
    dell'iscrizione ripresa: i quattro giocatori della sessione di prima e
    Mario Rossi, iscritto adesso dal database."""

    def test_l_elo_e_intero(self, monkeypatch, muto, tmp_path, capsys, cestino_finto):
        from tournament import load_tournament

        percorso = _sospeso_con_il_database()
        # INVIO carica Console_Prova; ROSMA001 iscrive Rossi; INVIO vuoto e c
        # chiudono l'iscrizione; f conferma la lista. Poi il bye suggerito e
        # la cartella proposta.
        copione, guida = _ripresa(monkeypatch, tmp_path, ["", "ROSMA001", "", "c", "f"], [True, True])

        guida._select_or_create_tournament()

        assert copione.tasti == [] and copione.conferme == []
        assert copione.domande[4] == "\nVuoi rimuovere un giocatore dalla lista? (Inserisci il numero, o 'f' per finire e confermare): "
        uscita = capsys.readouterr().out.splitlines()
        inizio = uscita.index("Riepilogo Giocatori Iscritti al Torneo")
        assert uscita[inizio : inizio + 8] == [
            "Riepilogo Giocatori Iscritti al Torneo",
            "Numero attuale di giocatori: 5",
            "  1. ID: G1 - NomeG1 CognomeG1 (Elo: 1800)",
            "  2. ID: G2 - NomeG2 CognomeG2 (Elo: 1700)",
            "  3. ID: G3 - NomeG3 CognomeG3 (Elo: 1600)",
            "  4. ID: G4 - NomeG4 CognomeG4 (Elo: 1500)",
            "  5. ID: ROSMA001 - Mario Rossi (Elo: 1844)",
            "Lista giocatori confermata.",
        ]
        assert not any(".0)" in r for r in uscita if "(Elo: " in r)
        # Il torneo nasce, e tiene l'Elo come prima: cambia soltanto come si
        # scrive.
        assert _cartella() == [
            "Tornello - Console_Prova - Classifica.txt",
            "Tornello - Console_Prova - Turno corrente.txt",
            "Tornello - Console_Prova.json",
            "Tornello - Players_db.json",
        ]
        salvato = load_tournament(percorso)
        assert [p["initial_elo"] for p in salvato["players"]] == [1800.0, 1700.0, 1600.0, 1500.0, 1844.0]
        assert [r["round"] for r in salvato["rounds"]] == [1]
        assert cestino_finto.tentativi == []


class TestIlFileDelTorneoSospeso:
    """Il file Tornello - Console_Prova_sospeso.txt, che la console scrive
    quando l'iscrizione ripresa si sospende di nuovo, con s: fino alla
    10.19.62 i quattro giocatori della sessione di prima avevano il punto
    zero, e Rossi, iscritto nella sessione, l'Elo intero."""

    def test_l_elo_e_intero_per_tutti(self, monkeypatch, muto, tmp_path, cestino_finto):
        import config
        from version import VERSIONE

        percorso = _sospeso_con_il_database()
        copione, guida = _ripresa(monkeypatch, tmp_path, ["", "ROSMA001", "", "s"])

        with pytest.raises(SystemExit) as uscita:
            guida._select_or_create_tournament()

        assert uscita.value.code == 0
        assert copione.tasti == []
        assert copione.domande[-1] == "Premi 'c' per concludere, 's' per sospendere, Esc per annullare: "
        assert _cartella() == ["Tornello - Console_Prova.json", "Tornello - Console_Prova_sospeso.txt", "Tornello - Players_db.json"]
        with open(config.user_data_path("Tornello - Console_Prova_sospeso.txt"), encoding="utf-8") as f:
            assert f.read() == "\n".join(
                [
                    "Riepilogo del torneo in preparazione: Console_Prova",
                    "Luogo: Online",
                    "Date: 2026-09-01 - 2026-09-30",
                    "Turni previsti: 3",
                    "Tempo di riflessione: Standard",
                    "",
                    "Giocatori inseriti: 5",
                    "01. CognomeG1 NomeG1 (ID: G1, Elo: 1800)",
                    "02. CognomeG2 NomeG2 (ID: G2, Elo: 1700)",
                    "03. CognomeG3 NomeG3 (ID: G3, Elo: 1600)",
                    "04. CognomeG4 NomeG4 (ID: G4, Elo: 1500)",
                    "05. Rossi Mario (ID: ROSMA001, Elo: 1844)",
                    "",
                    "",
                    f"Tornello ({VERSIONE})",
                    "",
                ]
            )
        # Il file del torneo tiene l'Elo come prima.
        with open(percorso, encoding="utf-8") as f:
            salvato = json.load(f)
        assert (salvato["creation_suspended"], [p["initial_elo"] for p in salvato["players"]]) == (True, [1800.0, 1700.0, 1600.0, 1500.0, 1844])
        assert cestino_finto.tentativi == []


class TestIRisultatiDelTurno:
    """I risultati del turno corrente, dal controller: il turno 1 di
    Console_Prova, con la Scacchiera 1 pianificata e la 2 no. Nome trova le
    due partite, 1 sceglie la Scacchiera 1, 1-0 la registra, e INVIO vuoto
    chiude l'inserimento; poi no a Vuoi continuare."""

    def test_l_elenco_e_la_ricerca_per_nome(self, monkeypatch, muto, capsys, cestino_finto):
        from tournament import load_tournament

        torneo = _torneo_al_primo_turno()
        torneo.rounds[0].matches[0].is_scheduled = True
        torneo.rounds[0].matches[0].schedule_info = {"date": "2026-09-10", "time": "18:00"}
        # Il caso c'e': Player tiene l'Elo con il punto zero.
        assert [p.initial_elo for p in torneo.players] == [1800.0, 1700.0, 1600.0, 1500.0]
        copione = Copione(monkeypatch, tasti=["Nome", "1", "1-0", ""], conferme=[True, False])
        guida = _controller(_adattatore(copione), torneo)

        guida._main_loop()

        assert copione.tasti == [] and copione.conferme == []
        # INVIO vuoto, all'ultima domanda, chiude l'inserimento.
        assert copione.domande[-2].endswith("\nR|T|SC|nome|cognome [2]: ")
        uscita = capsys.readouterr().out.splitlines()
        inizio = uscita.index("Partite del turno 1 ancora da registrare (N. Scacchiera del Turno):")
        assert uscita[inizio : inizio + 8] == [
            "Partite del turno 1 ancora da registrare (N. Scacchiera del Turno):",
            "",
            "  Partite già pianificate, da giocare:",
            "    Sc. 1  (IDG:1) - NomeG1 CognomeG1     [1800] vs NomeG3 CognomeG3     [1600]",
            "      Pianificata per: Giovedì 10 settembre 2026 alle 18:00",
            "",
            "  Ancora non pianificate:",
            "    Sc. 2  (IDG:2) - NomeG4 CognomeG4     [1500] vs NomeG2 CognomeG2     [1700]",
        ]
        trovate = uscita.index("Trovate 2 partite pendenti per 'nome':")
        assert uscita[trovate + 1 : trovate + 3] == [
            "  Sc. 1  (IDG:1) - NomeG1 CognomeG1     [1800] vs NomeG3 CognomeG3     [1600]",
            "  Sc. 2  (IDG:2) - NomeG4 CognomeG4     [1500] vs NomeG2 CognomeG2     [1700]",
        ]
        # Dopo il risultato l'elenco ha la sola Scacchiera 2.
        assert [r for r in uscita[trovate + 3 :] if "(IDG:" in r] == ["    Sc. 2  (IDG:2) - NomeG4 CognomeG4     [1500] vs NomeG2 CognomeG2     [1700]"]
        assert not any(".0]" in r for r in uscita if "(IDG:" in r)
        salvato = load_tournament(guida.active_filename)
        assert {m["id"]: m["result"] for m in salvato["rounds"][0]["matches"]} == {1: "1-0", 2: None}
        assert [p["initial_elo"] for p in salvato["players"]] == [1800.0, 1700.0, 1600.0, 1500.0]
        assert cestino_finto.tentativi == []
