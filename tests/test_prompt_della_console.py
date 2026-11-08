"""Le domande e i messaggi della versione a riga di comando con le date e i
due punti, dalla 10.19.56 (decisione di Gabriele dell'8 novembre 2026).

Il formato della data si dice a parole, AAAA-MM-GG, come nella finestra:
nelle domande della data di inizio e di fine di un torneo nuovo e nei loro
messaggi della data sbagliata, nella domanda e nel messaggio della data di
una partita da pianificare, nella domanda della data di nascita di un
giocatore nuovo. Le domande che finivano con due volte i due punti ne hanno
uno solo: Vuoi caricare, con un solo torneo nella cartella, le quattro della
pianificazione, il nome e il cognome di un giocatore nuovo. Fino alla
10.19.55, e gia' nella 10.0.0, domande e messaggi mostravano %Y-%m-%d, il
formato grezzo di strftime, e quelle domande finivano con ": : ", o con
":  []: ". Le date che si accettano e quelle che si rifiutano sono le
stesse di prima: le tabelle qui sotto sono quelle misurate sulla 10.19.55.
La console e' quella vera, con il controller e le risposte a copione di
test_console, senza suoni; il giorno di oggi e' fisso, domenica 8 novembre
2026. Tutto sta nella cartella temporanea della prova."""

import json
import os
from datetime import datetime

import pytest
import test_console as console
from test_console import Copione, _adattatore

muto = console.muto

DOMANDA_DI_CARICARE = "Vuoi caricare 'Corona'? (Premi INVIO per sì, o inserisci il nome di un NUOVO torneo da creare): "
DOMANDA_DI_INIZIO = "Inserisci data inizio (AAAA-MM-GG) [Default: Domenica 8 novembre 2026]: "
DOMANDA_DI_FINE = "Inserisci data fine (AAAA-MM-GG) [Default: Giovedì 7 gennaio 2027]: "
DATA_DI_INIZIO_SBAGLIATA = "Formato data non valido. Usa AAAA-MM-GG o AAAAMMGG."
DATA_DI_FINE_SBAGLIATA = "Formato data non valido. Usa AAAA-MM-GG."

# Le date di inizio, con la data che ne nasce, o None per quelle che si
# rifiutano. La vuota e' quella di oggi.
DATE_DI_INIZIO = {
    "": "2026-11-08",
    "2026-11-08": "2026-11-08",
    "20261108": "2026-11-08",
    "2026-1-5": "2026-01-05",
    " 2026-11-08 ": "2026-11-08",
    "99991231": "9999-12-31",
    "2026-02-30": None,
    "08/11/2026": None,
    "8-11-2026": None,
    "2026/11/08": None,
    "261108": None,
    "x": None,
    "2026-11-08x": None,
}
# Le date di fine, con l'inizio al 2026-11-08: vero per quelle che si
# accettano, altrimenti il messaggio del rifiuto.
DATE_DI_FINE = {
    "": True,
    "2026-12-31": True,
    "2026-12-5": True,
    "9999-12-31": True,
    "20261231": DATA_DI_FINE_SBAGLIATA,
    "2026-02-30": DATA_DI_FINE_SBAGLIATA,
    "31/12/2026": DATA_DI_FINE_SBAGLIATA,
    "2026/12/31": DATA_DI_FINE_SBAGLIATA,
    "x": DATA_DI_FINE_SBAGLIATA,
    "2026-11-01": "La data di fine non può essere precedente alla data di inizio.",
}


class Oggi(datetime):
    """Il datetime del controller, con oggi fisso."""

    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 8, 10, 30)


@pytest.fixture
def oggi_fisso(monkeypatch):
    import controller

    monkeypatch.setattr(controller, "datetime", Oggi)


def _contenuti():
    """I file della cartella del programma, con il loro contenuto."""
    import config

    cartella = config.user_data_path("")
    contenuti = {}
    for nome in sorted(os.listdir(cartella)):
        percorso = os.path.join(cartella, nome)
        if os.path.isfile(percorso):
            with open(percorso, "rb") as f:
                contenuti[nome] = f.read()
    return contenuti


def _leggi(percorso):
    with open(percorso, encoding="utf-8") as f:
        return json.load(f)


def _corona(**altro):
    """Corona, l'unico torneo della cartella del programma, al primo turno
    senza risultati."""
    import config

    torneo = console._torneo_al_primo_turno().to_dict()
    torneo["name"] = "Corona"
    torneo.update(altro)
    percorso = config.user_data_path("Tornello - Corona.json")
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump(torneo, f)
    return percorso


class TestLeDateDelTorneoNuovo:
    def test_la_creazione_dalla_domanda_vuoi_caricare(self, monkeypatch, oggi_fisso, cestino_finto, tmp_path):
        """Corona e' l'unico torneo della cartella: alla domanda Vuoi
        caricare si scrive Libero, il nome del torneo nuovo. Poi una data di
        inizio sbagliata e quella giusta, una data di fine sbagliata e INVIO
        per quella proposta, tre turni, i dati con INVIO, nessun giocatore e
        s per sospendere. Le domande dicono AAAA-MM-GG, i due messaggi della
        data sbagliata anche, senza il suono dell'errore, e Libero nasce
        sospeso con le date scritte."""
        import config
        from controller import TournamentController

        suonati = console.TestIlFileCheNonETorneoInConsole._suoni(monkeypatch)
        _corona()
        prima = _contenuti()
        tasti = ["Libero", "2026-13-01", "2026-11-08", "2026-13-01", "", "3", "", "", "", "", "", "", "s"]
        copione = Copione(monkeypatch, tasti=tasti, conferme=[True])
        adattatore = _adattatore(copione)
        guida = TournamentController(adattatore)

        with pytest.raises(SystemExit) as uscita:
            guida._select_or_create_tournament()

        assert uscita.value.code == 0
        assert copione.tasti == [] and copione.conferme == []
        assert copione.domande[:6] == [
            DOMANDA_DI_CARICARE,
            DOMANDA_DI_INIZIO,
            DOMANDA_DI_INIZIO,
            DOMANDA_DI_FINE,
            DOMANDA_DI_FINE,
            "Inserisci il numero totale dei turni: ",
        ]
        assert adattatore.messaggi[:5] == [
            "\nTrovato un solo torneo esistente: 'Corona' (File: Tornello - Corona.json)",
            "Creazione Nuovo Torneo",
            "Nome suggerito per il nuovo torneo: 'Libero'",
            DATA_DI_INIZIO_SBAGLIATA,
            DATA_DI_FINE_SBAGLIATA,
        ]
        assert not any("%" in d for d in copione.domande)
        assert not any(d.rstrip().endswith(": :") or "::" in d for d in copione.domande)
        assert "errore" not in suonati
        dopo = _contenuti()
        nati = ["Tornello - Libero.json", "Tornello - Libero_sospeso.txt"]
        assert sorted(dopo) == sorted([*prima, *nati])
        assert {n: b for n, b in dopo.items() if n not in nati} == prima
        libero = _leggi(config.user_data_path("Tornello - Libero.json"))
        assert (libero["name"], libero["start_date"], libero["end_date"], libero["creation_suspended"]) == ("Libero", "2026-11-08", "2027-01-07", True)
        assert cestino_finto.tentativi == []

    def test_la_domanda_vuoi_caricare_con_invio(self, monkeypatch, muto, cestino_finto):
        """Con INVIO alla domanda Vuoi caricare, Corona si apre; la domanda
        finisce con i due punti una volta sola, e il file resta com'era."""
        from controller import TournamentController

        percorso = _corona()
        prima = _contenuti()
        copione = Copione(monkeypatch, tasti=[""])
        guida = TournamentController(_adattatore(copione))

        guida._select_or_create_tournament()

        assert copione.domande == [DOMANDA_DI_CARICARE]
        assert guida.active_filename == percorso and guida.tournament.name == "Corona"
        assert _contenuti() == prima
        assert cestino_finto.tentativi == []

    @pytest.mark.parametrize("scritta", list(DATE_DI_INIZIO))
    def test_le_date_di_inizio_che_si_accettano(self, monkeypatch, muto, oggi_fisso, scritta):
        """Ogni data di inizio si accetta o si rifiuta come nella 10.19.55;
        dopo un rifiuto la domanda torna, e il 1999-09-09 si accetta."""
        from controller import TournamentController

        copione = Copione(monkeypatch, tasti=[scritta, "1999-09-09"])
        adattatore = _adattatore(copione)

        data = TournamentController(adattatore)._data_di_inizio_chiesta()

        attesa = DATE_DI_INIZIO[scritta]
        if attesa is None:
            assert (data, copione.tasti, adattatore.messaggi) == ("1999-09-09", [], [DATA_DI_INIZIO_SBAGLIATA])
            assert copione.domande == [DOMANDA_DI_INIZIO, DOMANDA_DI_INIZIO]
        else:
            assert (data, copione.tasti, adattatore.messaggi) == (attesa, ["1999-09-09"], [])
            assert copione.domande == [DOMANDA_DI_INIZIO]

    @pytest.mark.parametrize("scritta", list(DATE_DI_FINE))
    def test_le_date_di_fine_che_si_accettano(self, monkeypatch, muto, oggi_fisso, scritta):
        """Ogni data di fine, con l'inizio al 2026-11-08, si accetta o si
        rifiuta come nella 10.19.55. La creazione si ferma alla domanda dei
        turni, che viene subito dopo la data di fine."""
        from controller import TournamentController

        class AiTurni(Exception):
            pass

        def ai_turni(*a, **k):
            raise AiTurni

        copione = Copione(monkeypatch, tasti=["Libero", "2026-11-08", scritta, "2027-01-01"])
        adattatore = _adattatore(copione)
        adattatore.input_int = ai_turni

        with pytest.raises(AiTurni):
            TournamentController(adattatore)._create_new_tournament()

        attesa = DATE_DI_FINE[scritta]
        fine = [d for d in copione.domande if d.startswith("Inserisci data fine")]
        if attesa is True:
            assert (fine, copione.tasti, adattatore.messaggi) == ([DOMANDA_DI_FINE], ["2027-01-01"], ["Creazione Nuovo Torneo"])
        else:
            assert (fine, copione.tasti, adattatore.messaggi) == ([DOMANDA_DI_FINE] * 2, [], ["Creazione Nuovo Torneo", attesa])


# La pianificazione che la partita della scacchiera 1 di Corona ha gia', per
# la prova del cambio.
PIANIFICAZIONE = {"date": "2026-09-10", "time": "18:00", "channel": "Lichess", "arbiter": "Verdi"}


class TestLaPianificazioneInConsole:
    @staticmethod
    def _risultati(monkeypatch, tasti, **altro):
        """Corona si apre con INVIO, e fra i risultati del turno 1 si
        pianifica la scacchiera 1; poi INVIO vuoto chiude i risultati, e No
        a Vuoi continuare. Restituisce le domande, l'uscita e il file."""
        from controller import TournamentController

        percorso = _corona(**altro)
        copione = Copione(monkeypatch, tasti=["", "1", "p", *tasti, ""], conferme=[False])
        guida = TournamentController(_adattatore(copione))
        guida._select_or_create_tournament()
        guida._main_loop()
        assert copione.tasti == [] and copione.conferme == []
        return copione.domande, percorso

    def test_una_partita_da_pianificare(self, monkeypatch, muto, cestino_finto, capsys):
        """Una data sbagliata, x, poi quella giusta; un'ora sbagliata, poi
        quella giusta; il canale e l'arbitro. La domanda della data e il suo
        messaggio dicono AAAA-MM-GG, le quattro domande finiscono con i due
        punti una volta sola, e la pianificazione si scrive nel file."""
        domande, percorso = self._risultati(monkeypatch, ["x", "2026-09-11", "25", "20:30", "Lichess", "Verdi"])
        uscita = capsys.readouterr().out

        data = "Data partita (formati: GG, GG-MM, AAAA-MM-GG) [Attuale: N/D]: "
        ora = "Ora partita (formati: HH, HH:MM) [Attuale: N/O]: "
        assert domande[2:9] == [
            "Risultati: [1-0, 0-1, 1/2, 0-0F, 1-F, F-1, p per pianificare]: ",
            data,
            data,
            ora,
            ora,
            "Canale/Link partita [Attuale: ]: ",
            "Arbitro assegnato [Attuale: ]: ",
        ]
        righe = uscita.splitlines()
        assert "Formato data 'x' non valido o data inesistente. Usa GG, GG-MM, AAAA-MM-GG o AAAAMMGG." in righe
        assert "Formato ora non valido. Usa HH (es. 9) o HH:MM (es. 15:30)." in righe
        assert "Partita pianificata con successo." in righe
        assert "%Y" not in uscita
        partita = _leggi(percorso)["rounds"][0]["matches"][0]
        assert (partita["is_scheduled"], partita["schedule_info"]) == (True, {"date": "2026-09-11", "time": "20:30", "channel": "Lichess", "arbiter": "Verdi"})
        assert cestino_finto.tentativi == []

    def test_una_pianificazione_da_cambiare(self, monkeypatch, muto, cestino_finto, capsys):
        """La scacchiera 1 e' gia' pianificata: con m, e INVIO alle quattro
        domande, la pianificazione resta quella di prima. Ogni domanda
        mostra il valore attuale e quello che INVIO tiene, con i due punti
        una volta sola."""
        import config

        torneo = console._torneo_al_primo_turno().to_dict()
        torneo["rounds"][0]["matches"][0].update(is_scheduled=True, schedule_info=dict(PIANIFICAZIONE))
        domande, percorso = self._risultati(monkeypatch, ["m", "", "", "", ""], rounds=torneo["rounds"])
        uscita = capsys.readouterr().out

        assert domande[3:8] == [
            "Questa partita è già pianificata. Vuoi (M)odificare o (R)imuovere la pianificazione? (Invio per annullare): ",
            "Data partita (formati: GG, GG-MM, AAAA-MM-GG) [Attuale: Giovedì 10 settembre 2026] [2026-09-10]: ",
            "Ora partita (formati: HH, HH:MM) [Attuale: 18:00] [18:00]: ",
            "Canale/Link partita [Attuale: Lichess] [Lichess]: ",
            "Arbitro assegnato [Attuale: Verdi] [Verdi]: ",
        ]
        assert "Nessun dettaglio della pianificazione è stato effettivamente modificato." in uscita.splitlines()
        partita = _leggi(percorso)["rounds"][0]["matches"][0]
        assert (partita["is_scheduled"], partita["schedule_info"]) == (True, PIANIFICAZIONE)
        assert percorso == config.user_data_path("Tornello - Corona.json")
        assert cestino_finto.tentativi == []


class TestIlGiocatoreNuovoInConsole:
    def test_nome_cognome_e_data_di_nascita(self, monkeypatch, muto, oggi_fisso, cestino_finto, capsys):
        """Nella creazione di Libero si iscrive Zeta, che non c'e' in nessuno
        dei due database: la console chiede il nome, Mario, il cognome,
        Rossi, poi gli altri dati con INVIO, una data di nascita sbagliata,
        x, e 19900501. Nome e cognome hanno i due punti una volta sola, e la
        data di nascita dice AAAA-MM-GG; Mario Rossi entra nel database dei
        giocatori, con la sua data di nascita, e nel torneo, che si sospende
        con s."""
        import config
        import ui
        from controller import TournamentController

        monkeypatch.setattr(ui, "_cerca_giocatore_nel_db_fide", lambda testo: [])
        elo = []

        def dgt(prompt="", **opzioni):
            elo.append(prompt)
            return opzioni.get("default")

        monkeypatch.setattr(ui, "dgt", dgt)
        tasti = ["Libero", "", "", "3", "", "", "", "", "", "Zeta", "Mario", "Rossi", "", "", "", "", "x", "19900501", "", "s"]
        # Si' al Bianco alla prima scacchiera, No all'esperienza pregressa.
        copione = Copione(monkeypatch, tasti=tasti, conferme=[True, False])
        guida = TournamentController(_adattatore(copione))

        with pytest.raises(SystemExit) as uscita:
            guida._create_new_tournament()
        stampato = capsys.readouterr().out

        assert uscita.value.code == 0
        assert copione.tasti == [] and copione.conferme == []
        iscrizione = copione.domande.index("\nGiocatore 1 (o lascia vuoto per terminare): ")
        assert copione.domande[iscrizione + 1 : iscrizione + 10] == [
            "  Nome del nuovo giocatore []: ",
            "  Cognome []: ",
            "  Titolo FIDE (es. FM, o vuoto): ",
            "  Sesso (m/w) [m]: ",
            "  Federazione (3 lettere, es. ITA) [ITA]: ",
            "  ID FIDE Numerico ('0' se N/D) [0]: ",
            "  Data Nascita (AAAA-MM-GG o vuoto o AAAAMMGG): ",
            "  Data Nascita (AAAA-MM-GG o vuoto o AAAAMMGG): ",
            " Esperienza pregressa significativa? (INVIO|ESCAPE)",
        ]
        assert elo == ["  Elo (default 1399)"]
        assert "Formato data non valido. Riprova." in stampato.splitlines()
        assert not any("%" in d or ":  [" in d for d in copione.domande)
        database = _leggi(config.PLAYER_DB_FILE)
        schede = database["players"] if isinstance(database, dict) else database
        assert [(s["first_name"], s["last_name"], s["birth_date"]) for s in schede] == [("Mario", "Rossi", "1990-05-01")]
        libero = _leggi(config.user_data_path("Tornello - Libero.json"))
        assert [(p["first_name"], p["last_name"]) for p in libero["players"]] == [("Mario", "Rossi")]
        assert cestino_finto.tentativi == []
