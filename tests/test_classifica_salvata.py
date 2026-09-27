"""La classifica di un torneo concluso mostra i valori salvati alla
finalizzazione: posizione, spareggi, performance e variazione Elo calcolati
allora, e non li ricalcola con le regole di oggi, perche' la classifica
pubblicata non deve cambiare a posteriori (decisione di Gabriele, 10.13.19).
Vale per la voce Classifica dell'albero, per Ctrl+L e per i report, che
passano tutti da reports.get_standings_text.

Un torneo finalizzato senza final_rank, come i tre archiviati del 2025 e
del 2026, ha come posizione il piazzamento scritto allora nello storico dei
giocatori; se lo storico non le ha tutte, le posizioni si ricavano dai
valori salvati, e una riga dice chi differisce dallo storico.

I tornei archiviati veri della cartella del programma, e il suo database
dei giocatori, si leggono e non si scrivono; gli altri stanno nella
cartella temporanea della prova. I suoni sono muti."""

import copy
import json
import os
import re
from types import SimpleNamespace

import pytest
from test_finalizzazione import (
    _cartella_archivio,
    _finalizza,
    _finalizza_in_console,
    _json_in_archivio,
    _leggi,
    _scrivi,
    prepara_il_banco,
)

RADICE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def banco(tmp_path, monkeypatch):
    """Il torneo finito di test_finalizzazione.py, da finalizzare."""
    return prepara_il_banco(tmp_path, monkeypatch)


def _archiviato_vero(nome_del_file):
    """Un torneo archiviato della cartella del programma, letto dal disco;
    la prova si salta se l'archivio non lo ha piu'."""
    for radice, _cartelle, files in os.walk(os.path.join(RADICE, "Closed Tournaments")):
        if nome_del_file in files:
            with open(os.path.join(radice, nome_del_file), encoding="utf-8") as f:
                return json.load(f)
    pytest.skip(f"Torneo archiviato non trovato: {nome_del_file}")
    return None


def _righe_dei_giocatori(testo):
    """Le righe della tabella, per cognome e nome come le scrive la
    classifica."""
    righe = {}
    for riga in testo.splitlines():
        trovato = re.match(r"^\s*(\d+|RIT)\s.{8}.{4}(.{27}) \[", riga)
        if trovato:
            righe[trovato.group(2).strip()] = riga
    return righe


def _posizione(riga):
    return riga.split()[0]


def _posizioni(testo):
    return {nome: _posizione(riga) for nome, riga in _righe_dei_giocatori(testo).items()}


def _database_vero():
    """Il database dei giocatori della cartella del programma, letto dal
    disco; la prova si salta se non c'e'."""
    percorso = os.path.join(RADICE, "Tornello - Players_db.json")
    if not os.path.exists(percorso):
        pytest.skip("Database dei giocatori non trovato")
    with open(percorso, encoding="utf-8") as f:
        dati = json.load(f)
    giocatori = dati.get("players", []) if isinstance(dati, dict) else dati
    return {g["id"]: g for g in giocatori}


class TestTorneiArchiviatiVeri:
    """I tre tornei archiviati del 2025 e del 2026 sono stati finalizzati
    senza final_rank e senza final_tiebreaks. Con il database dei giocatori
    la posizione e' il piazzamento scritto allora nello storico; senza, la
    classifica la ricava dai punti e dagli spareggi salvati, e nei tre
    tornei le due strade danno le stesse posizioni, quelle della classifica
    che Tornello scrisse alla finalizzazione, nel file Classifica.txt
    archiviato. Per ASCId Primavera 1 quel file ha anche la classifica
    dell'arbitro, diversa per dieci giocatori, che indica come quella
    corretta: quale fosse la classifica ufficiale lo dira' Gabriele.
    Spareggi, performance e variazione Elo sono quelli salvati nel file del
    torneo; per cinque giocatori, Ionata e Tolaro in ASCId 52, Tolaro,
    Baratta e Parravano in Primavera 1, la variazione salvata non e' quella
    pubblicata e applicata allora al database, e la classifica mostra
    quella del file: anche questo lo decidera' Gabriele."""

    @pytest.mark.parametrize(
        "nome_del_file",
        [
            "Tornello - ASCId_Primavera_1.json",
            "Tornello - ASCId_52_Campionato_Italiano.json",
            "Tornello - Primavera_2.json",
        ],
    )
    def test_valori_salvati_e_torneo_intatto(self, nome_del_file):
        from reports import get_standings_text

        torneo = _archiviato_vero(nome_del_file)
        prima = copy.deepcopy(torneo)

        testo = get_standings_text(torneo)

        assert torneo == prima, "la classifica non deve toccare il torneo concluso"
        assert "CLASSIFICA FINALE" in testo
        assert (
            "Le posizioni di questo torneo concluso non erano salvate alla finalizzazione: sono ricavate dai punti e dagli spareggi salvati allora, nell'ordine dei criteri di spareggio."
            in testo
        )
        assert "non li ricalcola con le regole di oggi" not in testo
        righe = _righe_dei_giocatori(testo)
        for giocatore in torneo["players"]:
            riga = righe[f"{giocatore['last_name']}, {giocatore['first_name']}"[:27].strip()]
            if giocatore.get("withdrawn"):
                assert _posizione(riga) == "RIT"
                continue
            valori = riga.split("]")[1].split()
            assert valori[1:4] == [f"{giocatore['buchholz_cut1']:.1f}", f"{giocatore['buchholz']:.1f}", str(giocatore["aro"])]
            assert valori[-2:] == [str(giocatore["performance_rating"]), f"{giocatore['elo_change']:+d}"]

    @pytest.mark.parametrize(
        ("nome_del_file", "storico_completo"),
        [
            ("Tornello - ASCId_Primavera_1.json", True),
            # Del Monte Davide non e' nel database: la finalizzazione di
            # allora lo ha saltato, e le posizioni si ricavano dai valori
            # salvati, uguali allo storico di tutti gli altri.
            ("Tornello - ASCId_52_Campionato_Italiano.json", False),
            ("Tornello - Primavera_2.json", True),
        ],
    )
    def test_con_il_database_le_posizioni_dello_storico(self, nome_del_file, storico_completo):
        from reports import get_standings_text

        torneo = _archiviato_vero(nome_del_file)
        database = _database_vero()
        prima = (copy.deepcopy(torneo), copy.deepcopy(database))

        con_il_database = get_standings_text(torneo, players_db=database)
        dai_valori = get_standings_text(torneo, players_db={})

        assert (torneo, database) == prima, "la classifica non deve toccare il torneo e il database"
        dallo_storico = (
            "Le posizioni di questo torneo concluso non erano salvate nel suo file: sono il piazzamento che la finalizzazione ha scritto allora nello storico dei giocatori, nel database dei giocatori."
            in con_il_database
        )
        assert dallo_storico is storico_completo
        assert "diversa dal piazzamento" not in con_il_database + dai_valori
        assert _posizioni(con_il_database) == _posizioni(dai_valori)

    def test_primavera_1_come_la_classifica_scritta_da_tornello(self):
        """Di Bari ha l'ARO e la variazione Elo di allora, 1498 e +25, anche
        se oggi l'ARO non conta piu' il forfait (10.13.18) e la variazione
        lo escludeva gia'. Le posizioni sono quelle della classifica che
        Tornello scrisse alla finalizzazione, e dello storico dei giocatori:
        Nicolini terzo, Soppelsa quarto, Calzolari quindicesima.
        display_rank, salvato durante il torneo, diceva Soppelsa terzo e
        Calzolari ventunesima. La classifica dell'arbitro, nello stesso file
        archiviato, mette Calzolari sedicesima."""
        from reports import get_standings_text

        righe = _righe_dei_giocatori(get_standings_text(_archiviato_vero("Tornello - ASCId_Primavera_1.json")))

        di_bari = righe["Di Bari, Vincenzo"]
        assert _posizione(di_bari) == "14"
        assert " 1498 " in di_bari and di_bari.endswith(" +25")
        assert _posizione(righe["Nicolini, Francesco"]) == "3"
        assert _posizione(righe["Soppelsa, Maurizio"]) == "4"
        assert _posizione(righe["Calzolari, Valeria"]) == "15"


class TestFinalizzazioneSalvaGliSpareggi:
    """Dalla 10.13.19 la finalizzazione salva nel giocatore il valore di
    ogni colonna di spareggio, final_tiebreaks, e la classifica del torneo
    concluso lo rilegge da li'."""

    def test_i_valori_restano_quelli_salvati(self, banco):
        from reports import get_standings_text

        assert _finalizza(banco) is True
        archiviato = _leggi(_json_in_archivio())
        for giocatore in archiviato["players"]:
            assert set(giocatore["final_tiebreaks"]) == {"BH-C1", "BH", "ARO", "RTNG"}
        # Valori salvati diversi da quelli che darebbe il calcolo di oggi:
        # la classifica deve mostrare questi.
        g1 = next(g for g in archiviato["players"] if g["id"] == "G1")
        g2 = next(g for g in archiviato["players"] if g["id"] == "G2")
        g1["final_tiebreaks"]["BH-C1"] = 9.5
        g1["final_tiebreaks"]["ARO"] = 1234
        g1["performance_rating"] = 2222
        g1["elo_change"] = 77
        g1["final_rank"], g2["final_rank"] = g2["final_rank"], g1["final_rank"]
        prima = copy.deepcopy(archiviato)

        righe = _righe_dei_giocatori(get_standings_text(archiviato))

        assert archiviato == prima
        riga_g1 = righe["CognomeG1, NomeG1"]
        assert _posizione(riga_g1) == str(g1["final_rank"])
        assert riga_g1.split("]")[1].split() == ["1.0", "9.5", f"{g1['final_tiebreaks']['BH']:.1f}", "1234", "1800", "2222", "+77"]

    def test_un_valore_non_salvato_si_legge_nd_e_lo_si_dice(self, banco):
        from reports import get_standings_text

        assert _finalizza(banco) is True
        archiviato = _leggi(_json_in_archivio())
        g3 = next(g for g in archiviato["players"] if g["id"] == "G3")
        del g3["final_tiebreaks"]
        g3["aro"] = None

        testo = get_standings_text(archiviato)

        riga_g3 = _righe_dei_giocatori(testo)["CognomeG3, NomeG3"]
        # BH-C1 e BH vengono dai campi che le finalizzazioni scrivevano gia',
        # l'ARO non c'e' piu', RTNG e' l'Elo di partenza.
        assert riga_g3.split("]")[1].split()[1:5] == [f"{g3['buchholz_cut1']:.1f}", f"{g3['buchholz']:.1f}", "n.d.", "1600"]
        assert (
            "I valori n.d. dei giocatori non ritirati non erano salvati alla finalizzazione di questo torneo: la classifica di un torneo concluso non li ricalcola con le regole di oggi."
            in testo
        )

    def test_senza_posizioni_e_senza_valori_si_calcola_e_lo_si_dice(self, banco):
        """Senza storico, senza posizioni e senza valori salvati le posizioni
        si calcolano con le regole di oggi, su una copia: sul torneo
        concluso il calcolo aggiungerebbe players_dict."""
        from reports import get_standings_text

        assert _finalizza(banco) is True
        archiviato = _leggi(_json_in_archivio())
        for giocatore in archiviato["players"]:
            giocatore["final_rank"] = None
        g4 = next(g for g in archiviato["players"] if g["id"] == "G4")
        del g4["final_tiebreaks"]
        g4["aro"] = None
        prima = copy.deepcopy(archiviato)

        testo = get_standings_text(archiviato, players_db={})

        assert archiviato == prima
        assert "Le posizioni di questo torneo concluso non erano salvate alla finalizzazione: sono calcolate con le regole di oggi." in testo
        assert _posizione(_righe_dei_giocatori(testo)["CognomeG1, NomeG1"]) == "1"

    def _senza_posizioni_e_con_i_valori_rovesciati(self, archiviato):
        """Toglie final_rank a tutti e da' al secondo dei due giocatori a
        pari punti, G3 e G4, un Buchholz Cut-1 salvato che, ricavando le
        posizioni dai valori, lo porterebbe davanti all'altro. Restituisce
        i due, quello dietro e quello davanti."""
        davanti, dietro = sorted((g for g in archiviato["players"] if g["points"] == 0.5), key=lambda g: g["final_rank"])
        assert davanti["final_rank"] < dietro["final_rank"]
        for giocatore in archiviato["players"]:
            giocatore["final_rank"] = None
        dietro["final_tiebreaks"]["BH-C1"] = 99.0
        return dietro, davanti

    def test_senza_posizioni_valgono_quelle_dello_storico(self, banco):
        from db_players import load_players_db
        from reports import get_standings_text

        assert _finalizza(banco) is True
        archiviato = _leggi(_json_in_archivio())
        storico = {g["id"]: g["final_rank"] for g in archiviato["players"]}
        self._senza_posizioni_e_con_i_valori_rovesciati(archiviato)
        prima = copy.deepcopy(archiviato)

        testo = get_standings_text(archiviato, players_db=load_players_db())

        assert archiviato == prima
        assert _posizioni(testo) == {f"Cognome{pid}, Nome{pid}": str(rank) for pid, rank in storico.items()}
        assert "sono il piazzamento che la finalizzazione ha scritto allora nello storico dei giocatori" in testo
        assert "ricavate dai punti" not in testo

    def test_con_lo_storico_incompleto_si_ricavano_e_si_dicono_le_differenze(self, banco):
        """Un giocatore che il database non ha, come quelli che le
        finalizzazioni fino alla 10.13.15 saltavano: le posizioni si
        ricavano dai valori salvati, e una riga dice chi e' in una posizione
        diversa da quella dello storico."""
        from db_players import load_players_db
        from reports import get_standings_text

        assert _finalizza(banco) is True
        archiviato = _leggi(_json_in_archivio())
        storico = {g["id"]: g["final_rank"] for g in archiviato["players"]}
        dietro, davanti = self._senza_posizioni_e_con_i_valori_rovesciati(archiviato)
        database = load_players_db()
        del database["G1"]

        testo = get_standings_text(archiviato, players_db=database)

        assert "ricavate dai punti e dagli spareggi salvati" in testo
        posizioni = _posizioni(testo)
        assert posizioni["CognomeG1, NomeG1"] == "1"
        assert posizioni[f"Cognome{dietro['id']}, Nome{dietro['id']}"] == str(storico[davanti["id"]])
        assert posizioni[f"Cognome{davanti['id']}, Nome{davanti['id']}"] == str(storico[dietro["id"]])
        elenco = ", ".join(
            [
                f"Cognome{dietro['id']} Nome{dietro['id']} {storico[davanti['id']]} invece di {storico[dietro['id']]}",
                f"Cognome{davanti['id']} Nome{davanti['id']} {storico[dietro['id']]} invece di {storico[davanti['id']]}",
            ]
        )
        assert (
            f"Per 2 giocatori la posizione è diversa dal piazzamento che la finalizzazione ha scritto allora nel loro storico, nel database dei giocatori: {elenco}."
            in testo
        )

    def test_il_report_di_un_torneo_concluso_resta_la_classifica_finale(self, banco):
        """Un salvataggio del torneo concluso scrive la classifica con
        final=False, come dopo ogni azione: resta quella finale, con i valori
        salvati, e il torneo non cambia."""
        from reports import get_standings_text

        assert _finalizza(banco) is True
        archiviato = _leggi(_json_in_archivio())
        prima = copy.deepcopy(archiviato)

        testo = get_standings_text(archiviato, final=False)

        assert "CLASSIFICA FINALE" in testo
        assert archiviato == prima


class TestPosizioniAPariMerito:
    """Dalla 10.13.35 due giocatori pari nei punti e in tutti i criteri di
    spareggio hanno la stessa posizione finale, come nella classifica in
    corso: Tornello non sorteggia (C.07, articolo 4.2; decisione di
    Gabriele). Fino alla 10.13.34 la finalizzazione non faceva mai
    condividere una posizione: la chiave dell'ultimo confronto non si
    aggiornava, e non conteneva i punti."""

    def test_la_regola(self):
        from reports import posizioni_con_i_pari_merito

        elementi = [("a", 3.0), ("b", 2.0), ("c", 2.0), ("r", None), ("d", 1.0), ("e", 1.0), ("f", 0.0)]

        posizioni = posizioni_con_i_pari_merito(elementi, lambda e: e[1], lambda e: e[1] is None)

        assert posizioni == [1, 2, 2, None, 5, 5, 7]

    def test_una_lista_vuota_e_chi_e_da_solo(self):
        from reports import posizioni_con_i_pari_merito

        assert posizioni_con_i_pari_merito([], lambda e: e, lambda e: False) == []
        assert posizioni_con_i_pari_merito([None], lambda e: e, lambda e: False) == [1]

    @pytest.mark.parametrize("strada", ["finestra", "console"])
    def test_due_pari_su_tutto_condividono_la_posizione(self, banco, strada):
        """G3 e G4 pattano fra loro: mezzo punto ciascuno e lo stesso
        Buchholz, con e senza Cut-1, gli unici criteri del torneo. Hanno
        tutti e due la seconda posizione, nella classifica in corso, nel
        file del torneo archiviato, nella sua classifica e nel file della
        classifica, nello storico dei giocatori e nella medaglia; G2, ultimo,
        e' quarto."""
        from db_players import load_players_db
        from reports import get_standings_text

        banco.torneo["tiebreaks"] = [{"key": "BH", "modifiers": {"cut1": True}}, {"key": "BH", "modifiers": {}}]
        _scrivi(banco.file_torneo, banco.torneo)
        attese = {"CognomeG1, NomeG1": "1", "CognomeG3, NomeG3": "2", "CognomeG4, NomeG4": "2", "CognomeG2, NomeG2": "4"}
        assert _posizioni(get_standings_text(copy.deepcopy(banco.torneo))) == attese

        assert (_finalizza(banco) if strada == "finestra" else _finalizza_in_console(banco)) is True

        archiviato = _leggi(_json_in_archivio())
        assert {g["id"]: g["final_rank"] for g in archiviato["players"]} == {"G1": 1, "G3": 2, "G4": 2, "G2": 4}
        assert _posizioni(get_standings_text(archiviato)) == attese
        nome_del_file = next(n for n in os.listdir(_cartella_archivio()) if n.endswith("Classifica.txt"))
        with open(os.path.join(_cartella_archivio(), nome_del_file), encoding="utf-8-sig") as f:
            assert _posizioni(f.read()) == attese
        database = load_players_db()
        assert {pid: database[pid]["tournaments_played"][-1]["rank"] for pid in ("G1", "G2", "G3", "G4")} == {"G1": 1, "G2": 4, "G3": 2, "G4": 2}
        medaglie = {pid: {m for m, n in database[pid]["medals"].items() if n} for pid in ("G1", "G2", "G3", "G4")}
        assert medaglie == {"G1": {"gold"}, "G2": {"wood"}, "G3": {"silver"}, "G4": {"silver"}}

    def test_con_punti_diversi_la_posizione_non_si_condivide(self, banco):
        """Con il solo criterio delle vittorie col nero, che nel torneo del
        banco valgono zero per tutti, i quattro giocatori differiscono
        soltanto nei punti. Il primo calcolo del controller della console
        escludeva i punti dalla chiave, e fino alla 10.13.34 dava a tutti e
        quattro la prima posizione; adesso da' quella della finalizzazione,
        con G3 e G4 pari a mezzo punto."""
        import controller
        from db_players import load_players_db
        from models import Tournament

        banco.torneo["tiebreaks"] = [{"key": "BWG", "modifiers": {}}]
        _scrivi(banco.file_torneo, banco.torneo)
        messaggi = []
        finto = SimpleNamespace(
            tournament=Tournament.from_dict(copy.deepcopy(banco.torneo)),
            players_db=load_players_db(),
            active_filename=banco.file_torneo,
            ui=SimpleNamespace(show_message=messaggi.append, show_error=messaggi.append),
        )

        assert controller.TournamentController._finalize_tournament(finto) is True

        dal_controller = {p.id: p.final_rank for p in finto.tournament.players}
        archiviate = {g["id"]: g["final_rank"] for g in _leggi(_json_in_archivio())["players"]}
        assert dal_controller == {"G1": 1, "G3": 2, "G4": 2, "G2": 4}
        assert dal_controller == archiviate
