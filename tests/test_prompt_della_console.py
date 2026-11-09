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
Dalla 10.19.59 il nome e il cognome di un giocatore nuovo non mostrano le
parentesi quadre vuote, e INVIO torna alla domanda Giocatore N invece di
fermare la console. Dalla 10.19.60 il valore che INVIO tiene si mostra una
volta sola, nelle quattro domande della pianificazione e in quella del
controllo del tempo, e il canale e l'arbitro senza un valore non dicono
[Attuale: ] vuoto; INVIO tiene gli stessi valori di prima.
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
GIOCATORE_1 = "\nGiocatore 1 (o lascia vuoto per terminare): "
PREMI_C_S_O_ESC = "Premi 'c' per concludere, 's' per sospendere, Esc per annullare: "
# Senza le parentesi quadre vuote dalla 10.19.59.
DOMANDA_DEL_NOME = "  Nome del nuovo giocatore: "
DOMANDA_DEL_COGNOME = "  Cognome: "
# Con il valore che INVIO tiene una volta sola dalla 10.19.60.
DOMANDA_DEL_TEMPO = "Controllo del Tempo (es. 15+10, 90+30, 3+2) [Default: 90+30]: "

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

    def test_le_domande_della_creazione_con_invio(self, monkeypatch, muto, oggi_fisso, cestino_finto):
        """Libero, poi INVIO a ogni domanda che ha un valore, tre turni,
        nessun giocatore e s. Ogni domanda mostra il valore che INVIO tiene
        una volta sola, con la parola Default; dalla 10.19.60 anche quella
        del controllo del tempo, che fino alla 10.19.59 diceva [Default:
        90+30] [90+30]: . INVIO tiene gli stessi valori di prima, e Libero
        nasce sospeso con quelli."""
        import config
        from controller import TournamentController

        copione = Copione(monkeypatch, tasti=["Libero", "", "", "3", "", "", "", "", "", "", "s"], conferme=[True])
        guida = TournamentController(_adattatore(copione))

        with pytest.raises(SystemExit) as uscita:
            guida._create_new_tournament()

        assert uscita.value.code == 0
        assert copione.tasti == [] and copione.conferme == []
        assert copione.domande == [
            "Inserisci il nome del nuovo torneo: ",
            DOMANDA_DI_INIZIO,
            DOMANDA_DI_FINE,
            "Inserisci il numero totale dei turni: ",
            "Luogo del torneo [Default: Luogo Sconosciuto]: ",
            "Federazione organizzante (codice 3 lettere) [Default: ITA]: ",
            "Arbitro Capo [Default: N/D]: ",
            "Vice Arbitri (separati da virgola) [Default: nessuno]: ",
            DOMANDA_DEL_TEMPO,
            "Bianco alla prima scacchiera del Turno 1?",
            GIOCATORE_1,
            PREMI_C_S_O_ESC,
        ]
        libero = _leggi(config.user_data_path("Tornello - Libero.json"))
        campi = ("start_date", "end_date", "total_rounds", "site", "federation_code", "chief_arbiter", "deputy_chief_arbiters", "time_control", "tournament_category")
        assert {c: libero[c] for c in campi} == {
            "start_date": "2026-11-08",
            "end_date": "2027-01-07",
            "total_rounds": 3,
            "site": "Luogo Sconosciuto",
            "federation_code": "ITA",
            "chief_arbiter": "N/D",
            "deputy_chief_arbiters": "",
            "time_control": {"minutes": 90, "increment": 30, "pgn_value": "5400+30"},
            "tournament_category": "standard",
        }
        assert cestino_finto.tentativi == []

    def test_il_controllo_del_tempo_scritto(self, monkeypatch, muto, oggi_fisso, cestino_finto):
        """Un controllo del tempo sbagliato, x, poi 15+10: la domanda torna,
        con il valore una volta sola, dopo il messaggio Formato non valido,
        e Libero nasce con 15+10."""
        import config
        from controller import TournamentController

        copione = Copione(monkeypatch, tasti=["Libero", "", "", "3", "", "", "", "", "x", "15+10", "", "s"], conferme=[True])
        adattatore = _adattatore(copione)

        with pytest.raises(SystemExit):
            TournamentController(adattatore)._create_new_tournament()

        assert copione.tasti == [] and copione.conferme == []
        assert [d for d in copione.domande if d.startswith("Controllo del Tempo")] == [DOMANDA_DEL_TEMPO, DOMANDA_DEL_TEMPO]
        assert adattatore.messaggi == ["Creazione Nuovo Torneo", "Formato non valido. Usa minuti+incremento o solo minuti."]
        libero = _leggi(config.user_data_path("Tornello - Libero.json"))
        assert libero["time_control"] == {"minutes": 15, "increment": 10, "pgn_value": "900+10"}
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
# Le domande della data e dell'ora di una partita ancora da pianificare.
DATA_DA_PIANIFICARE = "Data partita (formati: GG, GG-MM, AAAA-MM-GG) [Attuale: N/D]: "
ORA_DA_PIANIFICARE = "Ora partita (formati: HH, HH:MM) [Attuale: N/O]: "


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
        punti una volta sola, e la pianificazione si scrive nel file. Dalla
        10.19.60 il canale e l'arbitro, che non hanno ancora un valore, non
        dicono [Attuale: ] vuoto."""
        domande, percorso = self._risultati(monkeypatch, ["x", "2026-09-11", "25", "20:30", "Lichess", "Verdi"])
        uscita = capsys.readouterr().out

        assert domande[2:9] == [
            "Risultati: [1-0, 0-1, 1/2, 0-0F, 1-F, F-1, p per pianificare]: ",
            DATA_DA_PIANIFICARE,
            DATA_DA_PIANIFICARE,
            ORA_DA_PIANIFICARE,
            ORA_DA_PIANIFICARE,
            "Canale/Link partita: ",
            "Arbitro assegnato: ",
        ]
        righe = uscita.splitlines()
        assert "Formato data 'x' non valido o data inesistente. Usa GG, GG-MM, AAAA-MM-GG o AAAAMMGG." in righe
        assert "Formato ora non valido. Usa HH (es. 9) o HH:MM (es. 15:30)." in righe
        assert "Partita pianificata con successo." in righe
        assert "%Y" not in uscita
        partita = _leggi(percorso)["rounds"][0]["matches"][0]
        assert (partita["is_scheduled"], partita["schedule_info"]) == (True, {"date": "2026-09-11", "time": "20:30", "channel": "Lichess", "arbiter": "Verdi"})
        assert cestino_finto.tentativi == []

    def test_una_partita_da_pianificare_con_invio_al_canale_e_all_arbitro(self, monkeypatch, muto, cestino_finto, capsys):
        """La data e l'ora, poi INVIO al canale e all'arbitro: le due domande
        non dicono Attuale, dalla 10.19.60, e INVIO tiene il canale e
        l'arbitro vuoti, come fino alla 10.19.59."""
        domande, percorso = self._risultati(monkeypatch, ["2026-09-11", "20:30", "", ""])

        assert domande[2:7] == [
            "Risultati: [1-0, 0-1, 1/2, 0-0F, 1-F, F-1, p per pianificare]: ",
            DATA_DA_PIANIFICARE,
            ORA_DA_PIANIFICARE,
            "Canale/Link partita: ",
            "Arbitro assegnato: ",
        ]
        assert "Partita pianificata con successo." in capsys.readouterr().out.splitlines()
        partita = _leggi(percorso)["rounds"][0]["matches"][0]
        assert (partita["is_scheduled"], partita["schedule_info"]) == (True, {"date": "2026-09-11", "time": "20:30", "channel": "", "arbiter": ""})
        assert cestino_finto.tentativi == []

    def test_una_pianificazione_da_cambiare(self, monkeypatch, muto, cestino_finto, capsys):
        """La scacchiera 1 e' gia' pianificata: con m, e INVIO alle quattro
        domande, la pianificazione resta quella di prima. Ogni domanda
        mostra il valore che INVIO tiene una volta sola, dalla 10.19.60, con
        la parola Attuale, e la data nella forma a parole, con i due punti
        una volta sola. Fino alla 10.19.59 il valore era due volte, per
        esempio Canale/Link partita [Attuale: Lichess] [Lichess]: ."""
        import config

        torneo = console._torneo_al_primo_turno().to_dict()
        torneo["rounds"][0]["matches"][0].update(is_scheduled=True, schedule_info=dict(PIANIFICAZIONE))
        domande, percorso = self._risultati(monkeypatch, ["m", "", "", "", ""], rounds=torneo["rounds"])
        uscita = capsys.readouterr().out

        assert domande[3:8] == [
            "Questa partita è già pianificata. Vuoi (M)odificare o (R)imuovere la pianificazione? (Invio per annullare): ",
            "Data partita (formati: GG, GG-MM, AAAA-MM-GG) [Attuale: Giovedì 10 settembre 2026]: ",
            "Ora partita (formati: HH, HH:MM) [Attuale: 18:00]: ",
            "Canale/Link partita [Attuale: Lichess]: ",
            "Arbitro assegnato [Attuale: Verdi]: ",
        ]
        assert "Nessun dettaglio della pianificazione è stato effettivamente modificato." in uscita.splitlines()
        partita = _leggi(percorso)["rounds"][0]["matches"][0]
        assert (partita["is_scheduled"], partita["schedule_info"]) == (True, PIANIFICAZIONE)
        assert percorso == config.user_data_path("Tornello - Corona.json")
        assert cestino_finto.tentativi == []

    def test_una_pianificazione_senza_canale_e_arbitro_da_cambiare(self, monkeypatch, muto, cestino_finto, capsys):
        """La scacchiera 1 e' gia' pianificata senza canale e senza arbitro:
        con m e INVIO alle quattro domande la pianificazione resta quella di
        prima, e dalla 10.19.60 il canale e l'arbitro non dicono [Attuale: ]
        vuoto."""
        esistente = {"date": "2026-09-10", "time": "18:00", "channel": "", "arbiter": ""}
        torneo = console._torneo_al_primo_turno().to_dict()
        torneo["rounds"][0]["matches"][0].update(is_scheduled=True, schedule_info=dict(esistente))
        domande, percorso = self._risultati(monkeypatch, ["m", "", "", "", ""], rounds=torneo["rounds"])

        assert domande[4:8] == [
            "Data partita (formati: GG, GG-MM, AAAA-MM-GG) [Attuale: Giovedì 10 settembre 2026]: ",
            "Ora partita (formati: HH, HH:MM) [Attuale: 18:00]: ",
            "Canale/Link partita: ",
            "Arbitro assegnato: ",
        ]
        assert "Nessun dettaglio della pianificazione è stato effettivamente modificato." in capsys.readouterr().out.splitlines()
        partita = _leggi(percorso)["rounds"][0]["matches"][0]
        assert (partita["is_scheduled"], partita["schedule_info"]) == (True, esistente)
        assert cestino_finto.tentativi == []

    def test_una_pianificazione_cambiata(self, monkeypatch, muto, cestino_finto, capsys):
        """Con m e quattro valori nuovi la pianificazione diventa quella
        scritta: il valore mostrato una volta sola non cambia quello che si
        scrive al suo posto."""
        torneo = console._torneo_al_primo_turno().to_dict()
        torneo["rounds"][0]["matches"][0].update(is_scheduled=True, schedule_info=dict(PIANIFICAZIONE))
        domande, percorso = self._risultati(monkeypatch, ["m", "2026-09-12", "21", "Chess.com", "Bianchi"], rounds=torneo["rounds"])

        assert "Nessun dettaglio della pianificazione è stato effettivamente modificato." not in capsys.readouterr().out.splitlines()
        partita = _leggi(percorso)["rounds"][0]["matches"][0]
        assert (partita["is_scheduled"], partita["schedule_info"]) == (True, {"date": "2026-09-12", "time": "21:00", "channel": "Chess.com", "arbiter": "Bianchi"})
        assert cestino_finto.tentativi == []
        assert cestino_finto.tentativi == []


class TestIlGiocatoreNuovoInConsole:
    def test_nome_cognome_e_data_di_nascita(self, monkeypatch, muto, oggi_fisso, cestino_finto, capsys):
        """Nella creazione di Libero si iscrive Zeta, che non c'e' in nessuno
        dei due database: la console chiede il nome, Mario, il cognome,
        Rossi, poi gli altri dati con INVIO, una data di nascita sbagliata,
        x, e 19900501. Nome e cognome hanno i due punti una volta sola, e
        dalla 10.19.59 niente parentesi quadre vuote, e la data di nascita
        dice AAAA-MM-GG; Mario Rossi entra nel database dei giocatori, con la
        sua data di nascita, e nel torneo, che si sospende con s."""
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
        iscrizione = copione.domande.index(GIOCATORE_1)
        assert copione.domande[iscrizione + 1 : iscrizione + 10] == [
            DOMANDA_DEL_NOME,
            DOMANDA_DEL_COGNOME,
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
        assert not any("%" in d or ":  [" in d or "[]" in d for d in copione.domande)
        database = _leggi(config.PLAYER_DB_FILE)
        schede = database["players"] if isinstance(database, dict) else database
        assert [(s["first_name"], s["last_name"], s["birth_date"]) for s in schede] == [("Mario", "Rossi", "1990-05-01")]
        libero = _leggi(config.user_data_path("Tornello - Libero.json"))
        assert [(p["first_name"], p["last_name"]) for p in libero["players"]] == [("Mario", "Rossi")]
        assert cestino_finto.tentativi == []

    @pytest.mark.parametrize("vuoto", ["nome", "cognome"])
    def test_invio_vuoto_al_nome_o_al_cognome(self, monkeypatch, muto, oggi_fisso, cestino_finto, capsys, vuoto):
        """Dalla 10.19.59 (decisione di Gabriele dell'8 novembre 2026). Il
        database dei giocatori ha Anna Bianchi. Nella creazione di Libero si
        iscrive Zeta, che non c'e' in nessuno dei due database, e si preme
        INVIO alla domanda del nome, o a quella del cognome dopo Mario: la
        console torna alla domanda Giocatore 1, senza errori, e le due
        domande non hanno le parentesi quadre vuote. Poi INVIO e s: Libero
        nasce sospeso, senza iscritti, e il database dei giocatori, il json e
        il txt, resta uguale byte per byte. Fino alla 10.19.58 le domande
        dicevano Nome del nuovo giocatore []: e Cognome []: , e INVIO
        fermava la console con AttributeError, 'NoneType' object has no
        attribute 'strip'."""
        import config
        import db_players
        import ui
        from controller import TournamentController

        monkeypatch.setattr(ui, "_cerca_giocatore_nel_db_fide", lambda testo: [])
        database = {}
        db_players.crea_nuovo_giocatore_nel_db(database, "Anna", "Bianchi", 1500, "", "w", "ITA", "0", None, False, silent=True)
        assert db_players.save_players_db(database)
        prima = _contenuti()
        assert {os.path.basename(config.PLAYER_DB_FILE), os.path.basename(config.PLAYER_DB_TXT_FILE)} <= set(prima)
        risposte = [""] if vuoto == "nome" else ["Mario", ""]
        tasti = ["Libero", "", "", "3", "", "", "", "", "", "Zeta", *risposte, "", "s"]
        copione = Copione(monkeypatch, tasti=tasti, conferme=[True])
        guida = TournamentController(_adattatore(copione))

        with pytest.raises(SystemExit) as uscita:
            guida._create_new_tournament()
        stampato = capsys.readouterr().out.splitlines()

        assert uscita.value.code == 0
        assert copione.tasti == [] and copione.conferme == []
        iscrizione = copione.domande.index(GIOCATORE_1)
        chieste = [DOMANDA_DEL_NOME] if vuoto == "nome" else [DOMANDA_DEL_NOME, DOMANDA_DEL_COGNOME]
        assert copione.domande[iscrizione:] == [GIOCATORE_1, *chieste, GIOCATORE_1, PREMI_C_S_O_ESC]
        assert stampato.count("Nessuna corrispondenza trovata. Procedi con l'inserimento manuale.") == 1
        assert not any("Errore" in r or "Traceback" in r for r in stampato)
        dopo = _contenuti()
        nati = ["Tornello - Libero.json", "Tornello - Libero_sospeso.txt"]
        assert sorted(dopo) == sorted([*prima, *nati])
        assert {n: b for n, b in dopo.items() if n not in nati} == prima
        libero = _leggi(config.user_data_path("Tornello - Libero.json"))
        assert (libero["players"], libero["creation_suspended"]) == ([], True)
        assert cestino_finto.tentativi == []
