"""Le copie di sicurezza lette, confrontate, ripristinate e sfoltite: la
logica senza wx di copie_di_sicurezza.py. Issue 39, seconda parte.

Tutto lavora nella cartella temporanea della prova: i percorsi arrivano alle
funzioni in un oggetto Percorsi, e le poche funzioni che li chiedono a config,
come la finalizzazione, trovano la deviazione del conftest. Il cestino e'
sempre uno finto, che sposta i file in una cartella della prova, e i suoni
sono muti.
"""

import copy
import json
import os
import shutil
import types
from datetime import datetime

import pytest
from test_finalizzazione import ELO_INIZIALI, ELO_RAPID, INIZIO, NOME, _torneo_finito

MESE = os.path.join("2026", "09 Settembre")


def _scrivi(percorso, dati):
    os.makedirs(os.path.dirname(str(percorso)), exist_ok=True)
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump(dati, f, indent=1, ensure_ascii=False)


def _leggi(percorso):
    with open(percorso, encoding="utf-8") as f:
        return json.load(f)


def _byte(percorso):
    with open(percorso, "rb") as f:
        return f.read()


def _copie(cartella, contesto):
    trovate = []
    for radice, _cartelle, files in os.walk(cartella):
        trovate += [os.path.join(radice, n) for n in files if f"_{contesto}_" in n]
    return sorted(trovate)


class CestinoFinto:
    """Al posto del cestino di Windows: sposta file e cartelle in una
    cartella della prova e annota che cosa ha ricevuto, e da quale finestra.
    rifiuta contiene i percorsi che non accetta, come un cestino che non si
    raggiunge."""

    def __init__(self, cartella):
        self.cartella = cartella
        self.ricevuti = []
        self.finestre = []
        self.rifiuta = set()

    def __call__(self, percorso, finestra=None):
        self.finestre.append(finestra)
        if os.path.abspath(percorso) in self.rifiuta:
            return False
        os.makedirs(self.cartella, exist_ok=True)
        destinazione = os.path.join(self.cartella, f"{len(self.ricevuti)}_{os.path.basename(percorso)}")
        shutil.move(percorso, destinazione)
        self.ricevuti.append(os.path.abspath(percorso))
        return True


def _giocatore(pid, cognome, **altro):
    return {"id": pid, "first_name": "Nome", "last_name": cognome, **altro}


def _torneo(nome="Coppa", turni=None, giocatori=None, **altro):
    """Un torneo scritto a mano, con i campi che servono ai confronti."""
    return {
        "name": nome,
        "tournament_id": nome.upper(),
        "start_date": "2026-09-01",
        "end_date": "2026-10-15",
        "total_rounds": 6,
        "current_round": len(turni or []) or 1,
        "players": giocatori if giocatori is not None else [_giocatore(f"G{i}", f"Cognome{i}") for i in range(1, 5)],
        "rounds": turni if turni is not None else [],
        **altro,
    }


def _partita(numero, turno, bianco, nero, risultato=None, **altro):
    return {"id": numero, "round": turno, "white_player_id": bianco, "black_player_id": nero, "result": risultato, **altro}


def _come_la_procedura_guidata(dati):
    """Il torneo come lo scrive il programma: la procedura guidata e la
    console passano da Tournament.to_dict, che aggiunge schema_version,
    come nel json di Autunneo2. I tornei scritti a mano non l'hanno, e con
    quelli soli le prove non vedevano che la copia di un torneo vero passava
    per il database dei giocatori."""
    from models import Tournament

    return Tournament.from_dict(dati).to_dict()


class TestNomi:
    def test_ogni_momento_si_riconosce(self):
        from copie_di_sicurezza import analizza_nome

        for contesto in (
            "creazione",
            "turno_12",
            "chiusura_torneo",
            "chiusura_db",
            "pre_finalize_torneo",
            "pre_finalize_db",
            "pre_rollback",
            "pre_timemachine",
            "pre_ritorno_preparazione",
            "pre_ripristino",
            "pre_archiviazione",
            "rifinalizzazione",
            "pre_turno_manuale",
        ):
            parti = analizza_nome(f"Tornello - Coppa_{contesto}_20260923_160512.json")
            assert parti["contesto"] == contesto
            assert parti["base"] == "Tornello - Coppa"
            assert parti["data"] == datetime(2026, 9, 23, 16, 5, 12)

    def test_i_trattini_bassi_del_nome_restano_al_nome(self):
        from copie_di_sicurezza import analizza_nome

        parti = analizza_nome("Tornello - Players_db_complex_pre_finalize_db_20260905_101112_2.json")

        assert parti["base"] == "Tornello - Players_db_complex"
        assert parti["contesto"] == "pre_finalize_db"
        assert parti["numero"] == 2
        assert parti["estensione"] == ".json"

    def test_un_report_e_un_momento_sconosciuto(self):
        from copie_di_sicurezza import analizza_nome

        report = analizza_nome("Tornello - Coppa - Classifica_rifinalizzazione_20260923_160512.txt")
        ignoto = analizza_nome("Tornello - Coppa_backup_20260923_160512.json")

        assert report["base"] == "Tornello - Coppa - Classifica"
        assert report["estensione"] == ".txt"
        assert ignoto["contesto"] is None
        assert ignoto["base"] == "Tornello - Coppa_backup"

    def test_i_file_estranei_e_le_date_impossibili(self):
        from copie_di_sicurezza import analizza_nome

        assert analizza_nome("Tornello - Coppa.json") is None
        assert analizza_nome("appunti.txt") is None
        assert analizza_nome("Tornello - Coppa_creazione_20261399_250000.json")["data"] is None

    def test_il_momento_a_parole(self):
        from copie_di_sicurezza import momento_in_parole

        assert momento_in_parole("pre_finalize_torneo") == "prima della finalizzazione"
        assert momento_in_parole("pre_finalize_db") == "prima della finalizzazione"
        assert momento_in_parole("turno_3") == "al turno 3 abbinato"
        assert momento_in_parole("chiusura_db") == "alla chiusura del programma"
        assert momento_in_parole("pre_ripristino") == "prima di un ripristino"
        assert momento_in_parole("pre_turno_manuale") == "prima di un turno composto a mano"
        assert momento_in_parole(None) == "momento sconosciuto"


class TestLettura:
    def test_un_torneo_vero(self, sample_tournament_dict, tmp_path):
        from copie_di_sicurezza import leggi_copia, riassunto_torneo

        percorso = tmp_path / "copia.json"
        _scrivi(percorso, sample_tournament_dict)

        tipo, dati, errore = leggi_copia(str(percorso))
        riassunto = riassunto_torneo(dati)

        assert (tipo, errore) == ("torneo", None)
        assert riassunto["nome"] == "ASCId Primavera 1"
        assert riassunto["turni_abbinati"] == riassunto["turni_previsti"] == 5
        assert riassunto["concluso"] is True
        assert riassunto["giocatori"] == len(sample_tournament_dict["players"])

    def test_i_numeri_di_un_torneo_in_corso(self):
        """Autunneo2 il 23 settembre: un turno di sei, dodici risultati su
        tredici. Qui in piccolo, con un bye che non conta fra le partite."""
        from copie_di_sicurezza import riassunto_torneo

        turno = {
            "round": 1,
            "matches": [
                _partita(1, 1, "G1", "G2", "1-0"),
                _partita(2, 1, "G3", "G4", None),
                _partita(3, 1, "G5", None, "BYE"),
            ],
        }
        giocatori = [_giocatore(f"G{i}", f"C{i}") for i in range(1, 6)]
        giocatori[4]["withdrawn"] = True
        riassunto = riassunto_torneo(_torneo(turni=[turno], giocatori=giocatori, concluded=None))

        assert riassunto["turni_abbinati"] == 1
        assert riassunto["turni_completi"] == 0
        assert (riassunto["risultati"], riassunto["partite"]) == (1, 2)
        assert (riassunto["giocatori"], riassunto["ritirati"]) == (5, 1)
        assert riassunto["concluso"] is False

    def test_le_copie_delle_prove_senza_identificativo(self):
        from copie_di_sicurezza import riassunto_torneo, tipo_del_contenuto

        vecchio = {"name": "Super E2E Cup", "players": [], "rounds": [], "concluded": None}

        assert tipo_del_contenuto(vecchio) == "torneo"
        assert riassunto_torneo(vecchio)["identificativo"] == ""

    def test_i_database_schema_2_e_schema_1(self, tmp_path):
        from copie_di_sicurezza import leggi_copia, riassunto_database

        voce = {"tournament_name": "Primavera", "tournament_id": "P", "date_started": "2026-05-01", "date_completed": "2026-06-15"}
        giocatori = [_giocatore("G1", "Rossi", tournaments_played=[voce]), _giocatore("G2", "Bianchi")]
        schema_2 = tmp_path / "db2.json"
        schema_1 = tmp_path / "db1.json"
        _scrivi(schema_2, {"schema_version": 2, "players": giocatori})
        _scrivi(schema_1, giocatori)

        for percorso, schema in ((schema_2, 2), (schema_1, 1)):
            tipo, dati, _errore = leggi_copia(str(percorso))
            riassunto = riassunto_database(dati)
            assert tipo == "database"
            assert riassunto["giocatori"] == 2
            assert riassunto["schema"] == schema
            assert riassunto["tornei"] == 1
            assert riassunto["ultimo_torneo"] == "Primavera"

    def test_un_torneo_scritto_dal_programma_e_un_torneo(self, tmp_path):
        """Tournament.to_dict scrive schema_version, come il database: il
        torneo si riconosce lo stesso, dai turni e dal nome, anche in
        preparazione, e la sua copia sta fra quelle del torneo."""
        from copie_di_sicurezza import (
            contenuto_breve,
            elenca_copie,
            iscritti_dei_tornei_attivi,
            raggruppa_per_origine,
            tipo_del_contenuto,
        )

        torneo = _come_la_procedura_guidata(_torneo_finito())
        in_preparazione = _come_la_procedura_guidata(dict(_torneo_finito(), rounds=[]))
        _metti(tmp_path, f"Tornello - {NOME}_turno_1_20260920_100000.json", torneo)
        _metti(tmp_path, f"Tornello - {NOME}_creazione_20260919_100000.json", in_preparazione)
        _scrivi(tmp_path / f"Tornello - {NOME}.json", torneo)

        assert "schema_version" in torneo
        assert tipo_del_contenuto(torneo) == "torneo"
        assert tipo_del_contenuto(in_preparazione) == "torneo"
        assert tipo_del_contenuto({"schema_version": 2, "players": []}) == "database"
        copie = elenca_copie(str(_cartella_backup(tmp_path)))
        assert [c.tipo for c in copie] == ["torneo", "torneo"]
        ((chiave, nome, elenco),) = raggruppa_per_origine(copie)
        assert (chiave, nome, len(elenco)) == (("torneo", NOME), NOME, 2)
        assert contenuto_breve(copie[1]) == "T1/1, 2/2 ris., 4 gioc."
        assert iscritti_dei_tornei_attivi(str(tmp_path)) == [(NOME, set(ELO_INIZIALI))]

    def test_json_rotto_e_report(self, tmp_path):
        from copie_di_sicurezza import leggi_copia

        rotto = tmp_path / "rotto.json"
        rotto.write_text("{rotto", encoding="utf-8")
        report = tmp_path / "classifica.txt"
        report.write_text("testo", encoding="utf-8")

        tipo, dati, errore = leggi_copia(str(rotto))
        assert (tipo, dati) == ("illeggibile", None)
        assert errore
        assert leggi_copia(str(report))[0] == "testo"


def _cartella_backup(tmp_path):
    return tmp_path / "backup"


def _metti(tmp_path, nome, dati=None, testo=None):
    """Una copia nella cartella backup della prova, sotto anno e mese."""
    percorso = _cartella_backup(tmp_path) / MESE / nome
    if testo is not None:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(testo, encoding="utf-8")
    else:
        _scrivi(percorso, dati)
    return percorso


class TestElenco:
    def test_origini_contenuto_e_ordine(self, tmp_path):
        import time

        from copie_di_sicurezza import contenuto_breve, elenca_copie, raggruppa_per_origine

        turno = {"round": 1, "matches": [_partita(1, 1, "G1", "G2", "1-0"), _partita(2, 1, "G3", "G4")]}
        _metti(tmp_path, "Tornello - Coppa_Prova_turno_1_20260920_100000.json", _torneo("Coppa Prova", [turno]))
        _metti(tmp_path, "Tornello - Coppa_Prova_creazione_20260919_090000.json", _torneo("Coppa Prova"))
        _metti(tmp_path, "Tornello - Coppa_Prova - Classifica_rifinalizzazione_20260921_120000.txt", testo="classifica")
        db = {"schema_version": 2, "players": [_giocatore("G1", "Rossi")]}
        vecchia = _metti(tmp_path, "Tornello - Players_db_chiusura_db_20260923_160512.json", db)
        _metti(tmp_path, "Tornello - Players_db_complex_pre_finalize_db_20260905_101112.json", db)
        # La data di modifica di una copia e' quella dell'originale: non conta.
        quando = time.time() - 400 * 86400
        os.utime(vecchia, (quando, quando))

        copie = elenca_copie(str(_cartella_backup(tmp_path)))
        gruppi = {nome: [c.nome for c in elenco] for _k, nome, elenco in raggruppa_per_origine(copie)}

        assert [c.data for c in copie] == sorted(c.data for c in copie)
        assert copie[-1].data == datetime(2026, 9, 23, 16, 5, 12)
        assert sorted(gruppi) == ["Coppa Prova", "Database dei giocatori", "Players_db_complex"]
        assert len(gruppi["Coppa Prova"]) == 3
        turno_1 = next(c for c in copie if c.contesto == "turno_1")
        assert contenuto_breve(turno_1) == "T1/6, 1/2 ris., 4 gioc."
        assert contenuto_breve(turno_1, con_origine=True).startswith("Coppa Prova, ")
        creazione = next(c for c in copie if c.contesto == "creazione")
        assert contenuto_breve(creazione) == "in preparazione, 4 gioc."
        assert contenuto_breve(copie[-1]) == "1 gioc."

    def test_i_dettagli_si_leggono_a_righe_corte(self, tmp_path):
        from copie_di_sicurezza import dettagli_della_copia, elenca_copie

        _metti(tmp_path, "Tornello - Coppa_chiusura_torneo_20260923_160512.json", _torneo("Coppa"))
        copia = elenca_copie(str(_cartella_backup(tmp_path)))[0]

        righe = dettagli_della_copia(copia, datetime(2026, 9, 25, 10, 0, 0))

        assert "Momento: alla chiusura del programma" in righe
        assert "Età: 0 mesi, 1 giorno" in righe
        assert "Stato: in preparazione" in righe
        assert "Turni abbinati: 0 su 6" in righe
        assert all(len(r) <= 40 for r in righe if r != copia.nome)

    def test_l_eta_con_una_sola_unita_e_al_singolare(self):
        """Fino alla 10.13.5 si leggeva 0 mesi, 1 giorni, nei dettagli e
        nella colonna dell'elenco."""
        from copie_di_sicurezza import eta_a_parole

        assert eta_a_parole(0, 1) == "0 mesi, 1 giorno"
        assert eta_a_parole(1, 0) == "1 mese, 0 giorni"
        assert eta_a_parole(1, 1) == "1 mese, 1 giorno"
        assert eta_a_parole(14, 22) == "14 mesi, 22 giorni"


class TestConfrontoTorneo:
    def _coppia(self):
        """Lo stato attuale ha due turni, un risultato, un PGN e una
        programmazione in piu' della copia, e un ritiro; la copia ha un
        risultato diverso e un iscritto che oggi non c'e'."""
        from copie_di_sicurezza import confronta_torneo

        attuale = _torneo(
            turni=[
                {"round": 1, "matches": [_partita(1, 1, "G1", "G2", "1-0", pgn="1. e4"), _partita(2, 1, "G3", "G4", "0-1")]},
                {"round": 2, "matches": [_partita(3, 2, "G2", "G3", "1/2-1/2", schedule_info={"date": "2026-09-20"})]},
            ]
        )
        attuale["players"][3]["withdrawn"] = True
        attuale["concluded"] = True
        copia = copy.deepcopy(attuale)
        copia["rounds"] = copia["rounds"][:1]
        copia["rounds"][0]["matches"][0]["result"] = None
        copia["rounds"][0]["matches"][0].pop("pgn")
        copia["rounds"][0]["matches"][1]["result"] = "1-0"
        copia["players"][3]["withdrawn"] = False
        copia["players"].append(_giocatore("G9", "Nuovo"))
        copia["concluded"] = False
        return confronta_torneo(copia, attuale)

    def test_cosa_si_perderebbe(self):
        esito = self._coppia()

        assert esito["turni_persi"] == [2]
        assert [k for k, _p in esito["risultati_persi"]] == [(1, 1), (2, 3)]
        assert [k for k, _a, _c in esito["risultati_diversi"]] == [(1, 2)]
        assert [k for k, _p in esito["pgn_persi"]] == [(1, 1)]
        assert [k for k, _p in esito["programmazioni_perse"]] == [(2, 3)]
        assert esito["iscritti_in_piu"] == ["G9"]
        assert esito["ritiri_annullati"] == ["G4"]
        assert esito["da_concluso_a_in_corso"] is True

    def test_il_testo_del_confronto(self):
        from copie_di_sicurezza import righe_del_confronto_torneo

        righe = righe_del_confronto_torneo(self._coppia())

        assert "Turni che si perderebbero: 2" in righe
        assert "Risultati che si perderebbero: 2" in righe
        assert "  T1, Cognome1-Cognome2: 1-0" in righe
        assert "  T1, Cognome3-Cognome4: 0-1 diventa 1-0" in righe
        assert "PGN che si perderebbero: 1" in righe
        assert "Programmazioni che si perderebbero: 1" in righe
        assert "Il torneo, oggi concluso, tornerebbe in corso." in righe

    def test_una_copia_uguale(self):
        from copie_di_sicurezza import confronta_torneo, righe_del_confronto_torneo

        torneo = _torneo()

        assert righe_del_confronto_torneo(confronta_torneo(torneo, copy.deepcopy(torneo))) == ["La copia è uguale allo stato attuale."]


class TestConfrontoDatabase:
    def test_giocatori_elo_storici_e_iscritti(self, tmp_path):
        from copie_di_sicurezza import confronta_database, iscritti_dei_tornei_attivi, righe_del_confronto_database

        voce = {"tournament_name": "Primavera", "tournament_id": "P", "date_started": "2026-05-01"}
        attuale = {
            "schema_version": 2,
            "players": [
                _giocatore("G1", "Rossi", current_elo=1845, tournaments_played=[voce]),
                _giocatore("G2", "Bianchi", current_elo=1500),
                _giocatore("G3", "Verdi", current_elo=1600),
            ],
        }
        copia = {
            "schema_version": 2,
            "players": [
                _giocatore("G1", "Rossi", current_elo=1829, tournaments_played=[]),
                _giocatore("G2", "Bianchi", current_elo=1499),
                _giocatore("G4", "Neri", current_elo=1700),
            ],
        }
        _scrivi(tmp_path / "Tornello - Coppa.json", _torneo("Coppa", giocatori=[_giocatore("G3", "Verdi")]))
        _scrivi(tmp_path / "Tornello - Chiusa.json", _torneo("Chiusa", giocatori=[_giocatore("G7", "X")], concluded=True))
        _scrivi(tmp_path / "Tornello - Players_db.json", attuale)

        tornei = iscritti_dei_tornei_attivi(str(tmp_path))
        esito = confronta_database(copia, attuale, tornei)
        righe = righe_del_confronto_database(esito)

        assert tornei == [("Coppa", {"G3"})]
        assert esito["sparirebbero"] == ["G3"]
        assert esito["tornerebbero"] == ["G4"]
        assert [(pid, oggi, nella_copia) for pid, _c, oggi, nella_copia in esito["elo"]] == [("G1", 1845, 1829), ("G2", 1500, 1499)]
        assert "  Rossi Nome, Elo 1845 a 1829 (-16)" in righe
        assert "Tornei che uscirebbero dagli storici: 1" in righe
        assert "  Primavera, 1 giocatore" in righe
        assert "  Coppa: Verdi Nome" in righe

    def test_un_giocatore_solo_e_al_singolare(self):
        """Partite, storici e medaglie contano i giocatori: fino alla 10.13.5
        anche uno solo era al plurale."""
        from copie_di_sicurezza import confronta_database, righe_del_confronto_database

        primavera = {"tournament_name": "Primavera", "tournament_id": "P", "date_started": "2026-05-01"}
        estate = {"tournament_name": "Estate", "tournament_id": "E", "date_started": "2026-07-01"}
        attuale = {
            "schema_version": 2,
            "players": [
                _giocatore("G1", "Rossi", games_played=11, medals={"gold": 1}, tournaments_played=[primavera, estate]),
                _giocatore("G2", "Bianchi", games_played=5, tournaments_played=[primavera]),
            ],
        }
        copia = {
            "schema_version": 2,
            "players": [
                _giocatore("G1", "Rossi", games_played=10, medals={"gold": 0}, tournaments_played=[]),
                _giocatore("G2", "Bianchi", games_played=5, tournaments_played=[]),
            ],
        }

        righe = righe_del_confronto_database(confronta_database(copia, attuale))

        assert "Partite giocate diverse: 1 giocatore" in righe
        assert "Medaglie diverse: 1 giocatore" in righe
        assert "  Estate, 1 giocatore" in righe
        assert "  Primavera, 2 giocatori" in righe

    def test_una_voce_sola_oltre_l_elenco_e_al_singolare(self):
        """Rilievo della revisione: con una voce in piu' di quelle che
        l'elenco mostra, fino alla 10.13.5 si leggeva e altre 1."""
        from copie_di_sicurezza import RIGHE_PER_ELENCO, _elenco

        titolo = "Voci: {numero}"
        assert _elenco(titolo, list(range(RIGHE_PER_ELENCO + 1)))[-1] == "  e un'altra"
        assert _elenco(titolo, list(range(RIGHE_PER_ELENCO + 2)))[-1] == "  e altre 2"
        assert _elenco(titolo, list(range(RIGHE_PER_ELENCO)))[-1] == f"  {RIGHE_PER_ELENCO - 1}"


def _giocatori_db(voci=None):
    return {
        pid: {
            "id": pid,
            "first_name": "Nome" + pid,
            "last_name": "Cognome" + pid,
            "current_elo": elo,
            "games_played": 10,
            "medals": {"gold": 1, "silver": 0, "bronze": 0, "wood": 0},
            "tournaments_played": list(voci or []),
        }
        for pid, elo in ELO_INIZIALI.items()
    }


class TestStorno:
    """storno_finalizzazione e' pura: riceve le schede e restituisce quelle
    stornate, senza scrivere niente."""

    def _archiviato(self):
        torneo = _torneo_finito()
        for giocatore, variazione in zip(torneo["players"], (16, -16, 2, -2), strict=True):
            giocatore["elo_change"] = variazione
            giocatore["games_this_tournament"] = 1
        torneo["concluded"] = True
        return torneo

    def _voce(self, rango=1):
        return {"tournament_name": NOME, "tournament_id": "COPPA_PROVA", "rank": rango, "total_players": 4, "date_started": INIZIO}

    def test_senza_il_database_di_prima_si_sottrae(self):
        from copie_di_sicurezza import storno_finalizzazione

        schede = _giocatori_db([self._voce()])
        schede["G1"]["current_elo"] = 1816
        prima = copy.deepcopy(schede)

        esito = storno_finalizzazione(schede, self._archiviato())

        assert schede == prima, "lo storno non deve toccare le schede ricevute"
        g1 = esito["giocatori"]["G1"]
        assert g1["current_elo"] == 1800
        assert g1["games_played"] == 9
        assert g1["tournaments_played"] == []
        assert g1["medals"]["gold"] == 0
        assert esito["conflitti"] == []
        assert any("togliendo la variazione" in s for s in esito["segnalazioni"])

    def test_con_il_database_di_prima_torna_il_valore_esatto(self):
        from copie_di_sicurezza import storno_finalizzazione

        di_prima = _giocatori_db()
        di_prima["G1"]["current_elo"] = 1800.7
        schede = _giocatori_db([self._voce()])
        schede["G1"]["current_elo"] = 1816

        esito = storno_finalizzazione(schede, self._archiviato(), di_prima)

        assert esito["giocatori"]["G1"]["current_elo"] == 1800.7
        stornato = next(s for s in esito["stornati"] if s["id"] == "G1")
        assert stornato["sottratto"] is False
        assert stornato["medaglia"] == "gold"

    def test_un_torneo_successivo_e_un_conflitto(self):
        from copie_di_sicurezza import storno_finalizzazione

        dopo = {"tournament_name": "Autunno", "tournament_id": "AUTUNNO", "rank": 2, "date_started": "2026-08-01"}
        schede = _giocatori_db([self._voce(), dopo])

        esito = storno_finalizzazione(schede, self._archiviato())

        assert sorted(pid for pid, _n, _v in esito["conflitti"]) == sorted(ELO_INIZIALI)
        assert esito["stornati"] == []

    def test_le_partite_non_vanno_sotto_zero(self):
        from copie_di_sicurezza import storno_finalizzazione

        schede = _giocatori_db([self._voce(rango=5)])
        schede["G2"]["games_played"] = 0

        esito = storno_finalizzazione(schede, self._archiviato())

        assert esito["giocatori"]["G2"]["games_played"] == 0
        assert esito["giocatori"]["G2"]["medals"]["gold"] == 1

    def _rapid(self):
        torneo = self._archiviato()
        torneo["tournament_category"] = "rapid"
        return torneo

    def _voce_con_l_elo(self, campo, prima, dopo):
        """La voce come la scrive la finalizzazione dalla 10.13.4: il campo
        dell'Elo che ha ricevuto la variazione, il valore di prima, se il
        campo c'era, e quello scritto. prima None vuol dire che il campo non
        c'era."""
        voce = self._voce()
        voce["elo_field"] = campo
        if prima is not None:
            voce["elo_before"] = prima
        voce["elo_after"] = dopo
        return voce

    def test_un_rapid_torna_all_elo_rapid_della_copia(self):
        """Dalla 10.13.4 la finalizzazione di un rapid scrive su elo_rapid, e
        lo storno toglie la variazione da li': current_elo non cambia. G4
        non aveva l'Elo rapid, e la finalizzazione glielo ha dato dal suo
        current_elo: torna a zero, e la copia lo conferma."""
        from copie_di_sicurezza import righe_dello_storno, storno_finalizzazione

        di_prima = _giocatori_db()
        schede = _giocatori_db()
        for pid, variazione in zip(ELO_INIZIALI, (16, -16, 2, -2), strict=True):
            di_prima[pid]["elo_rapid"] = 1650.0
            schede[pid]["elo_rapid"] = 1650 + variazione
            schede[pid]["tournaments_played"] = [self._voce_con_l_elo("elo_rapid", 1650.0, 1650 + variazione)]
        di_prima["G4"]["elo_rapid"] = 0.0
        schede["G4"]["elo_rapid"] = ELO_INIZIALI["G4"] - 2
        schede["G4"]["tournaments_played"] = [self._voce_con_l_elo("elo_rapid", 0.0, ELO_INIZIALI["G4"] - 2)]

        esito = storno_finalizzazione(schede, self._rapid(), di_prima)

        for pid in ELO_INIZIALI:
            assert esito["giocatori"][pid]["elo_rapid"] == di_prima[pid]["elo_rapid"], pid
            assert esito["giocatori"][pid]["current_elo"] == ELO_INIZIALI[pid], pid
        assert all(s["da_copia"] and s["campo"] == "elo_rapid" for s in esito["stornati"])
        assert esito["segnalazioni"] == []
        assert "CognomeG1 NomeG1: Elo rapid 1666 a 1650 (-16), partite 10 a 9, un oro in meno" in righe_dello_storno(esito)

    def test_senza_la_copia_l_elo_rapid_di_prima_viene_dallo_storico(self):
        """Senza la copia pre_finalize_db, per esempio riaprendo da una copia
        di un turno, il valore di prima viene dalla voce dello storico, ed e'
        esatto: G3 aveva l'Elo rapid a zero e ci torna, G4 non aveva il campo
        e il campo se ne va. Rilievo della revisione: la 10.13.4 in
        lavorazione sottraeva la variazione, e all'Elo rapid nato alla
        finalizzazione restava il current_elo di quel giorno. Nelle righe
        della conferma il campo che se ne va si dice a parole, non None."""
        from copie_di_sicurezza import righe_dello_storno, storno_finalizzazione

        schede = _giocatori_db()
        for pid, variazione in zip(("G1", "G2"), (16, -16), strict=True):
            schede[pid]["elo_rapid"] = 1650 + variazione
            schede[pid]["tournaments_played"] = [self._voce_con_l_elo("elo_rapid", 1650, 1650 + variazione)]
        schede["G3"]["elo_rapid"] = ELO_INIZIALI["G3"] + 2
        schede["G3"]["tournaments_played"] = [self._voce_con_l_elo("elo_rapid", 0.0, ELO_INIZIALI["G3"] + 2)]
        schede["G4"]["elo_rapid"] = ELO_INIZIALI["G4"] - 2
        schede["G4"]["tournaments_played"] = [self._voce_con_l_elo("elo_rapid", None, ELO_INIZIALI["G4"] - 2)]

        esito = storno_finalizzazione(schede, self._rapid())

        g = esito["giocatori"]
        assert (g["G1"]["elo_rapid"], g["G2"]["elo_rapid"], g["G3"]["elo_rapid"]) == (1650, 1650, 0.0)
        assert "elo_rapid" not in g["G4"]
        for pid in ELO_INIZIALI:
            assert g[pid]["current_elo"] == ELO_INIZIALI[pid], pid
        assert all(s["dallo_storico"] and not s["sottratto"] for s in esito["stornati"])
        assert esito["segnalazioni"] == []
        righe = righe_dello_storno(esito)
        assert "CognomeG4 NomeG4: Elo rapid 1498 a nessuno, partite 10 a 9, un oro in meno" in righe
        assert not any("None" in r for r in righe)

    def test_un_elo_rapid_cambiato_dopo_la_finalizzazione_si_sottrae(self):
        """Se l'Elo rapid non e' piu' quello scritto dalla finalizzazione, il
        valore di prima non vale piu': si toglie la variazione da quello di
        oggi, e lo si segnala."""
        from copie_di_sicurezza import storno_finalizzazione

        schede = _giocatori_db()
        for pid, variazione in zip(ELO_INIZIALI, (16, -16, 2, -2), strict=True):
            schede[pid]["elo_rapid"] = 1650 + variazione + 5
            schede[pid]["tournaments_played"] = [self._voce_con_l_elo("elo_rapid", 1650, 1650 + variazione)]

        esito = storno_finalizzazione(schede, self._rapid())

        for pid in ELO_INIZIALI:
            assert esito["giocatori"][pid]["elo_rapid"] == 1655, pid
            assert esito["giocatori"][pid]["current_elo"] == ELO_INIZIALI[pid], pid
        assert all(s["sottratto"] and s["campo"] == "elo_rapid" for s in esito["stornati"])
        assert sum("togliendo la variazione" in s for s in esito["segnalazioni"]) == 4

    def test_un_rapid_finalizzato_prima_della_10_13_4_torna_su_current_elo(self):
        """Fino alla 10.13.3 la variazione di un rapid andava su current_elo,
        e la voce dello storico non ha elo_field: lo storno la toglie da li',
        lasciando elo_rapid com'e', e la copia pre_finalize_db fa tornare il
        valore esatto. La segnalazione e' una sola per tutti i giocatori:
        nella 10.13.4 in lavorazione si ripeteva, uguale, per ciascuno."""
        from copie_di_sicurezza import righe_dello_storno, storno_finalizzazione

        di_prima = _giocatori_db()
        schede = _giocatori_db([self._voce()])
        for pid, variazione in zip(ELO_INIZIALI, (16, -16, 2, -2), strict=True):
            di_prima[pid]["elo_rapid"] = schede[pid]["elo_rapid"] = 1650
            schede[pid]["current_elo"] = ELO_INIZIALI[pid] + variazione

        esito = storno_finalizzazione(schede, self._rapid(), di_prima)

        for pid in ELO_INIZIALI:
            assert esito["giocatori"][pid]["current_elo"] == ELO_INIZIALI[pid], pid
            assert esito["giocatori"][pid]["elo_rapid"] == 1650, pid
        assert all(s["da_copia"] and s["campo"] == "current_elo" for s in esito["stornati"])
        assert esito["segnalazioni"] == [
            "La variazione di questo torneo è sull'Elo principale, dove la mettevano le finalizzazioni fatte prima della versione 10.13.4, e si toglie da lì: 4 giocatori."
        ]
        assert any(r.startswith("CognomeG1 NomeG1: Elo 1816 a 1800 (-16)") for r in righe_dello_storno(esito))

    def test_un_rapid_di_prima_della_10_13_4_senza_la_copia_si_sottrae_da_current_elo(self):
        """Rilievo bloccante della revisione: senza la copia pre_finalize_db,
        un rapid finalizzato fino alla 10.13.3 perdeva la variazione
        dall'Elo rapid, che non l'aveva mai ricevuta, e la teneva su
        current_elo. G4 senza Elo rapid finiva a -2, Elo di partenza del
        rapid successivo. La voce senza elo_field dice current_elo."""
        from copie_di_sicurezza import righe_dello_storno, storno_finalizzazione

        schede = _giocatori_db([self._voce()])
        for pid, variazione in zip(ELO_INIZIALI, (16, -16, 2, -2), strict=True):
            schede[pid]["elo_rapid"] = ELO_RAPID[pid]
            schede[pid]["current_elo"] = ELO_INIZIALI[pid] + variazione

        esito = storno_finalizzazione(schede, self._rapid())

        for pid in ELO_INIZIALI:
            assert esito["giocatori"][pid]["current_elo"] == ELO_INIZIALI[pid], pid
            assert esito["giocatori"][pid]["elo_rapid"] == ELO_RAPID[pid], pid
        assert all(s["sottratto"] and s["campo"] == "current_elo" for s in esito["stornati"])
        assert esito["segnalazioni"][-1].endswith("e si toglie da lì: 4 giocatori.")
        assert not any("Elo rapid" in r or "None" in r for r in righe_dello_storno(esito))

        # Con un giocatore solo, il singolare.
        solo = _giocatori_db()
        solo["G1"]["tournaments_played"] = [self._voce()]
        solo["G1"]["current_elo"] = 1816
        esito = storno_finalizzazione(solo, self._rapid())
        assert esito["giocatori"]["G1"]["current_elo"] == 1800
        assert esito["segnalazioni"][-1].endswith("e si toglie da lì: un giocatore.")

    def test_una_variazione_nulla_non_toglie_niente(self):
        """Un giocatore con variazione zero, per esempio con sole partite a
        forfait: non c'e' niente da togliere, e niente da segnalare. Nella
        10.13.4 in lavorazione, in un rapid di prima della 10.13.4, si
        leggeva l'Elo di prima si ricava togliendo la variazione del
        torneo, 0."""
        from copie_di_sicurezza import storno_finalizzazione

        torneo = self._rapid()
        for giocatore in torneo["players"]:
            if giocatore["id"] in ("G3", "G4"):
                giocatore["elo_change"] = 0
        di_prima = _giocatori_db()
        schede = _giocatori_db([self._voce()])
        for pid in ELO_INIZIALI:
            di_prima[pid]["elo_rapid"] = schede[pid]["elo_rapid"] = 0.0
        schede["G1"]["current_elo"] = 1816
        schede["G2"]["current_elo"] = 1684
        # Un aggiornamento FIDE dopo la finalizzazione: la copia non torna.
        schede["G3"]["current_elo"] = 1610

        for copia in (None, di_prima):
            esito = storno_finalizzazione(schede, torneo, copia)

            g = esito["giocatori"]
            assert (g["G3"]["current_elo"], g["G4"]["current_elo"]) == (1610, 1500)
            assert all(g[pid]["elo_rapid"] == 0.0 for pid in ELO_INIZIALI)
            nulli = [s for s in esito["stornati"] if s["id"] == "G3"]
            assert not nulli[0]["sottratto"] and not nulli[0]["da_copia"]
            assert not any(", 0." in s or "NomeG3" in s or "NomeG4" in s for s in esito["segnalazioni"])
            assert esito["segnalazioni"][-1].endswith("e si toglie da lì: 2 giocatori."), copia


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    """Database dei giocatori, gia' passato da load e save come fa il
    programma, e torneo finito, passato da Tournament.to_dict come quelli
    veri, nella cartella della prova; Percorsi della prova, cestino finto e
    suoni muti."""
    import config
    import ui
    from copie_di_sicurezza import Percorsi
    from db_players import load_players_db, save_players_db

    assert config.PLAYER_DB_FILE.startswith(str(tmp_path))
    assert ui.ARCHIVED_TOURNAMENTS_DIR.startswith(str(tmp_path))
    monkeypatch.setattr(ui, "play_sound", lambda *a, **k: None)
    giocatori = [
        {
            "id": pid,
            "first_name": "Nome" + pid,
            "last_name": "Cognome" + pid,
            "current_elo": float(elo),
            "initial_elo": float(elo),
            "games_played": 10,
        }
        for pid, elo in ELO_INIZIALI.items()
    ]
    _scrivi(config.PLAYER_DB_FILE, {"schema_version": 2, "players": giocatori})
    assert save_players_db(load_players_db())
    torneo = _come_la_procedura_guidata(_torneo_finito())
    assert "schema_version" in torneo
    file_torneo = str(tmp_path / f"Tornello - {NOME}.json")
    _scrivi(file_torneo, torneo)
    percorsi = Percorsi(
        radice=str(tmp_path),
        backup=str(tmp_path / "backup"),
        archivio=ui.ARCHIVED_TOURNAMENTS_DIR,
        database=config.PLAYER_DB_FILE,
        database_txt=str(tmp_path / "Tornello - Players_db.txt"),
    )
    return types.SimpleNamespace(
        torneo=torneo,
        file_torneo=file_torneo,
        percorsi=percorsi,
        cestino=CestinoFinto(str(tmp_path / "cestino")),
        tmp=tmp_path,
    )


def _finalizza(torneo, percorso):
    from db_players import load_players_db
    from ui import finalize_tournament

    return finalize_tournament(copy.deepcopy(torneo), load_players_db(), percorso, [])


def _cartella_d_archivio(ambiente):
    trovate = [
        radice
        for radice, _cartelle, files in os.walk(ambiente.percorsi.archivio)
        if f"Tornello - {NOME}.json" in files
    ]
    assert len(trovate) <= 1
    return trovate[0] if trovate else None


class TestRipristinoDiUnTorneoInCorso:
    def test_nasce_la_copia_di_prima_e_il_torneo_torna_com_era(self, ambiente):
        from copie_di_sicurezza import ripristina

        copia = _metti(ambiente.tmp, f"Tornello - {NOME}_turno_1_20260920_100000.json", ambiente.torneo)
        cambiato = copy.deepcopy(ambiente.torneo)
        cambiato["rounds"][0]["matches"][0]["result"] = "0-1"
        _scrivi(ambiente.file_torneo, cambiato)
        prima = _byte(ambiente.file_torneo)

        esito = ripristina(str(copia), ambiente.percorsi, cestino=ambiente.cestino)

        assert esito.riuscito, esito.righe
        assert _leggi(ambiente.file_torneo) == ambiente.torneo
        di_prima = _copie(ambiente.percorsi.backup, "pre_ripristino")
        assert di_prima == esito.copie
        assert _byte(di_prima[0]) == prima
        assert ambiente.cestino.ricevuti == []

    def test_la_copia_di_un_torneo_vero_non_tocca_il_database(self, ambiente):
        """La copia di un torneo scritto dal programma, con schema_version,
        torna al posto del torneo, e il database dei giocatori resta com'e'."""
        from copie_di_sicurezza import prepara_ripristino, ripristina

        copia = _metti(ambiente.tmp, f"Tornello - {NOME}_turno_1_20260920_100000.json", ambiente.torneo)
        database = _byte(ambiente.percorsi.database)

        piano = prepara_ripristino(str(copia), ambiente.percorsi)
        esito = ripristina(str(copia), ambiente.percorsi, cestino=ambiente.cestino)

        assert (piano.tipo, piano.destinazione, piano.rifiuto) == ("torneo", ambiente.file_torneo, None)
        assert esito.riuscito, esito.righe
        assert _byte(ambiente.percorsi.database) == database
        assert _leggi(ambiente.file_torneo) == ambiente.torneo

    def test_una_scrittura_fermata_prima_non_rimette_niente(self, ambiente, monkeypatch):
        """Il file bloccato ferma la scrittura prima della sostituzione: il
        file e' com'era, non si rimette, e l'esito non parla di danni."""
        import copie_di_sicurezza
        from copie_di_sicurezza import ripristina

        copia = _metti(ambiente.tmp, f"Tornello - {NOME}_turno_1_20260920_100000.json", ambiente.torneo)
        _scrivi(ambiente.file_torneo, dict(ambiente.torneo, current_round=9))
        prima = _byte(ambiente.file_torneo)

        def bloccato(*a, **k):
            raise PermissionError("file bloccato")

        def rimetti(*a, **k):
            raise AssertionError("un file intatto non si rimette")

        monkeypatch.setattr(copie_di_sicurezza, "scrivi_json_atomico", bloccato)
        monkeypatch.setattr(copie_di_sicurezza, "_rimetti_il_file", rimetti)

        esito = ripristina(str(copia), ambiente.percorsi, cestino=ambiente.cestino)

        assert not esito.riuscito
        assert _byte(ambiente.file_torneo) == prima
        assert "Nessun file è stato cambiato." in esito.righe
        assert not any("Nemmeno" in r for r in esito.righe)

    def test_se_la_copia_di_sicurezza_non_riesce_non_si_scrive_niente(self, ambiente, monkeypatch):
        import copie_di_sicurezza
        from copie_di_sicurezza import ripristina

        copia = _metti(ambiente.tmp, f"Tornello - {NOME}_turno_1_20260920_100000.json", ambiente.torneo)
        cambiato = dict(ambiente.torneo, current_round=9)
        _scrivi(ambiente.file_torneo, cambiato)
        prima = _byte(ambiente.file_torneo)
        monkeypatch.setattr(copie_di_sicurezza, "copia_di_sicurezza", lambda *a, **k: None)

        esito = ripristina(str(copia), ambiente.percorsi, cestino=ambiente.cestino)

        assert not esito.riuscito
        assert _byte(ambiente.file_torneo) == prima
        assert any("non è stato toccato niente" in r for r in esito.righe)

    def test_un_omonimo_con_un_altro_identificativo_si_rifiuta(self, ambiente):
        from copie_di_sicurezza import prepara_ripristino, ripristina

        altro = dict(ambiente.torneo, tournament_id="ALTRO")
        copia = _metti(ambiente.tmp, f"Tornello - {NOME}_turno_1_20260920_100000.json", altro)
        prima = _byte(ambiente.file_torneo)

        piano = prepara_ripristino(str(copia), ambiente.percorsi)
        esito = ripristina(str(copia), ambiente.percorsi, cestino=ambiente.cestino)

        assert "altro torneo con lo stesso nome" in piano.rifiuto
        assert not esito.riuscito
        assert _byte(ambiente.file_torneo) == prima
        assert _copie(ambiente.percorsi.backup, "pre_ripristino") == []

    def test_la_copia_di_un_torneo_concluso_non_si_rimette(self, ambiente):
        from copie_di_sicurezza import prepara_ripristino

        copia = _metti(ambiente.tmp, f"Tornello - {NOME}_rifinalizzazione_20260920_100000.json", dict(ambiente.torneo, concluded=True))

        assert "già concluso" in prepara_ripristino(str(copia), ambiente.percorsi).rifiuto

    def test_un_torneo_che_non_c_e_piu_torna_nella_cartella(self, ambiente):
        from copie_di_sicurezza import ripristina

        copia = _metti(ambiente.tmp, f"Tornello - {NOME}_turno_1_20260920_100000.json", ambiente.torneo)
        os.remove(ambiente.file_torneo)

        esito = ripristina(str(copia), ambiente.percorsi, cestino=ambiente.cestino)

        assert esito.riuscito
        assert esito.destinazione == ambiente.file_torneo
        assert _leggi(ambiente.file_torneo) == ambiente.torneo
        assert esito.copie == []

    def test_se_la_rilettura_non_torna_si_rimette_lo_stato_di_prima(self, ambiente, monkeypatch):
        import copie_di_sicurezza
        from copie_di_sicurezza import ripristina

        copia = _metti(ambiente.tmp, f"Tornello - {NOME}_turno_1_20260920_100000.json", ambiente.torneo)
        _scrivi(ambiente.file_torneo, dict(ambiente.torneo, current_round=9))
        prima = _byte(ambiente.file_torneo)

        def scrittura_sbagliata(percorso, dati, indent=1):
            with open(percorso, "w", encoding="utf-8") as f:
                json.dump({"rovinato": True}, f)

        monkeypatch.setattr(copie_di_sicurezza, "scrivi_json_atomico", scrittura_sbagliata)

        esito = ripristina(str(copia), ambiente.percorsi, cestino=ambiente.cestino)

        assert not esito.riuscito
        assert _byte(ambiente.file_torneo) == prima
        assert any("tornato com'era" in r for r in esito.righe)


def _rilettura_bloccata(monkeypatch, bersaglio):
    """Dopo la scrittura atomica di bersaglio, la prima rilettura lo trova
    bloccato, come fa a volte un antivirus: la scrittura e' riuscita, la
    verifica no. Si sostituisce soltanto l'open di copie_di_sicurezza, e le
    letture in binario, che confrontano i file con le loro copie, restano
    libere."""
    import builtins

    import copie_di_sicurezza

    bersaglio = os.path.abspath(bersaglio)
    stato = {"scritto": False}
    scrivi_vera, open_vero = copie_di_sicurezza.scrivi_json_atomico, builtins.open

    def scrivi(percorso, dati, indent=1):
        risultato = scrivi_vera(percorso, dati, indent)
        if os.path.abspath(percorso) == bersaglio:
            stato["scritto"] = True
        return risultato

    def apri(file, mode="r", *altri, **chiavi):
        if stato["scritto"] and "b" not in mode and os.path.abspath(str(file)) == bersaglio:
            stato["scritto"] = False
            raise PermissionError("file bloccato")
        return open_vero(file, mode, *altri, **chiavi)

    monkeypatch.setattr(copie_di_sicurezza, "scrivi_json_atomico", scrivi)
    monkeypatch.setattr(copie_di_sicurezza, "open", apri, raising=False)


class TestCicloCompleto:
    """Finalizza, ripristina la copia di prima della finalizzazione,
    rifinalizza: il database e l'archivio devono tornare quelli della prima
    finalizzazione, come se la riapertura non ci fosse mai stata."""

    def test_finalizza_riapri_e_rifinalizza(self, ambiente):
        from copie_di_sicurezza import prepara_ripristino, ripristina

        esterna = ambiente.tmp / "esterna"
        esterna.mkdir()
        ambiente.torneo["custom_save_path"] = str(esterna)
        _scrivi(ambiente.file_torneo, ambiente.torneo)
        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        database_finalizzato = _leggi(ambiente.percorsi.database)
        cartella = _cartella_d_archivio(ambiente)
        archiviato = _leggi(os.path.join(cartella, f"Tornello - {NOME}.json"))
        esterno = esterna / f"Tornello - {NOME}.json"
        assert esterno.exists()
        copia = _copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]
        database_di_prima = _leggi(_copie(ambiente.percorsi.backup, "pre_finalize_db")[0])

        piano = prepara_ripristino(copia, ambiente.percorsi)
        assert piano.tipo == "finalizzato"
        assert piano.rifiuto is None
        assert any("NomeG1" in r and "un oro in meno" in r for r in piano.righe)
        assert any(r.startswith("Gli Elo di prima vengono dalla copia Tornello - Players_db_pre_finalize_db_") for r in piano.righe)

        esito = ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino)

        assert esito.riuscito, esito.righe
        # Ogni copia dice di quale file e': il json archiviato e quello della
        # cartella esterna hanno lo stesso nome.
        for cosa in ("database dei giocatori", "torneo archiviato", "file della cartella esterna"):
            assert sum(r.startswith(f"  {cosa}: Tornello - ") for r in esito.righe) == 1, cosa
        assert not os.path.exists(cartella)
        assert not esterno.exists()
        assert sorted(ambiente.cestino.ricevuti) == sorted([os.path.abspath(cartella), os.path.abspath(esterno)])
        riaperto = _leggi(ambiente.file_torneo)
        assert riaperto == _leggi(copia)
        assert not riaperto.get("concluded")
        assert _leggi(ambiente.percorsi.database) == database_di_prima
        assert len(_copie(ambiente.percorsi.backup, "pre_ripristino")) == 3
        assert os.path.exists(ambiente.percorsi.database_txt)

        assert _finalizza(riaperto, ambiente.file_torneo) is True

        assert _leggi(ambiente.percorsi.database) == database_finalizzato
        assert _leggi(os.path.join(_cartella_d_archivio(ambiente), f"Tornello - {NOME}.json")) == archiviato

    def _rapid(self, ambiente):
        """Il database con gli Elo rapid, G4 senza, e il torneo della prova
        fatto rapid, con l'Elo di partenza che gli darebbe l'iscrizione.
        Restituisce il database come e' sul disco prima della
        finalizzazione."""
        from db_players import load_players_db, save_players_db
        from stats import get_initial_elo_for_tournament

        giocatori = load_players_db()
        for pid, elo in ELO_RAPID.items():
            giocatori[pid]["elo_rapid"] = elo
        assert save_players_db(giocatori)
        ambiente.torneo["tournament_category"] = "rapid"
        ambiente.torneo["time_control"] = {"minutes": 15, "increment": 10, "pgn_value": "900+10"}
        for giocatore in ambiente.torneo["players"]:
            giocatore["initial_elo"] = get_initial_elo_for_tournament(giocatori[giocatore["id"]], "rapid")
        _scrivi(ambiente.file_torneo, ambiente.torneo)
        return _leggi(ambiente.percorsi.database)

    def _copia_di_un_turno(self, ambiente):
        """Una copia del torneo con turno_1 nel nome, con il contenuto di
        quella di prima della finalizzazione: una copia di un turno non ha
        la compagna pre_finalize_db, e la riapertura non ha il database di
        prima."""
        from copie_di_sicurezza import database_di_prima

        copia = os.path.join(ambiente.percorsi.backup, f"Tornello - {NOME}_turno_1_20260701_120000.json")
        _scrivi(copia, _leggi(_copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]))
        assert database_di_prima(copia, ambiente.percorsi.backup) is None
        return copia

    def test_un_rapid_riaperto_rida_il_database_di_prima(self, ambiente):
        """Un torneo rapid: la finalizzazione cambia elo_rapid e lascia
        current_elo, e la riapertura dalla copia di prima della
        finalizzazione rimette il database identico a prima, anche l'Elo
        rapid di G4, che non lo aveva e lo ha avuto dal suo current_elo.
        Rifinalizzando si torna al database della prima finalizzazione."""
        from copie_di_sicurezza import prepara_ripristino, ripristina

        database_iniziale = self._rapid(ambiente)

        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        database_finalizzato = _leggi(ambiente.percorsi.database)
        iniziali = {g["id"]: g for g in database_iniziale["players"]}
        finalizzati = {g["id"]: g for g in database_finalizzato["players"]}
        for pid in ELO_INIZIALI:
            assert finalizzati[pid]["current_elo"] == iniziali[pid]["current_elo"], pid
        assert finalizzati["G1"]["elo_rapid"] > ELO_RAPID["G1"]
        assert finalizzati["G4"]["elo_rapid"] != 0

        copia = _copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]
        piano = prepara_ripristino(copia, ambiente.percorsi)
        assert piano.rifiuto is None
        assert any("NomeG1" in r and ": Elo rapid " in r for r in piano.righe)
        assert any(r.startswith("Gli Elo di prima vengono dalla copia Tornello - Players_db_pre_finalize_db_") for r in piano.righe)

        esito = ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino)

        assert esito.riuscito, esito.righe
        assert _leggi(ambiente.percorsi.database) == database_iniziale

        assert _finalizza(_leggi(ambiente.file_torneo), ambiente.file_torneo) is True
        assert _leggi(ambiente.percorsi.database) == database_finalizzato

    def test_un_rapid_riaperto_da_una_copia_di_un_turno_rida_il_database_di_prima(self, ambiente):
        """Senza la copia del database di prima gli Elo tornano dalla voce
        dello storico, esatti: anche l'Elo rapid di G4, nato alla
        finalizzazione, torna a zero. Rilievo della revisione: la 10.13.4 in
        lavorazione sottraeva la variazione, e gli lasciava il suo
        current_elo."""
        from copie_di_sicurezza import prepara_ripristino, ripristina

        database_iniziale = self._rapid(ambiente)
        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        copia = self._copia_di_un_turno(ambiente)

        piano = prepara_ripristino(copia, ambiente.percorsi)

        assert piano.rifiuto is None
        assert any(r.startswith("  CognomeG4 NomeG4: Elo rapid ") and " a 0 (" in r for r in piano.righe)
        assert not any("togliendo" in r or "Gli Elo di prima vengono" in r or "None" in r for r in piano.righe)
        assert ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino).riuscito
        assert _leggi(ambiente.percorsi.database) == database_iniziale

    def test_un_rapid_di_prima_della_10_13_4_riaperto_da_una_copia_di_un_turno(self, ambiente):
        """Rilievo bloccante della revisione. Un rapid finalizzato fino alla
        10.13.3 ha la variazione su current_elo, e le voci dello storico
        senza i campi dell'Elo; riaperto da una copia di un turno, che non
        ha il database di prima, la 10.13.4 in lavorazione toglieva la
        variazione da elo_rapid, dove non era mai stata, e lasciava
        current_elo com'era: sbagliati tutti e due, e l'Elo rapid di G4
        sotto zero. Adesso il database torna identico a prima."""
        from copie_di_sicurezza import prepara_ripristino, ripristina

        database_iniziale = self._rapid(ambiente)
        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        # Il database come lo lasciava la finalizzazione fino alla 10.13.3.
        archiviato = _leggi(os.path.join(_cartella_d_archivio(ambiente), f"Tornello - {NOME}.json"))
        variazioni = {g["id"]: g["elo_change"] for g in archiviato["players"]}
        iniziali = {g["id"]: g for g in database_iniziale["players"]}
        dati = _leggi(ambiente.percorsi.database)
        for giocatore in dati["players"]:
            pid = giocatore["id"]
            giocatore["current_elo"] = int(iniziali[pid]["current_elo"]) + variazioni[pid]
            giocatore["elo_rapid"] = iniziali[pid]["elo_rapid"]
            for chiave in ("elo_field", "elo_before", "elo_after"):
                giocatore["tournaments_played"][-1].pop(chiave)
        _scrivi(ambiente.percorsi.database, dati)
        assert all(variazioni.values())
        copia = self._copia_di_un_turno(ambiente)

        piano = prepara_ripristino(copia, ambiente.percorsi)

        assert piano.rifiuto is None
        assert any(r.startswith("  CognomeG1 NomeG1: Elo ") for r in piano.righe)
        assert not any("Elo rapid" in r or "None" in r for r in piano.righe)
        assert (
            "La variazione di questo torneo è sull'Elo principale, dove la mettevano le finalizzazioni fatte prima della versione 10.13.4, e si toglie da lì: 4 giocatori."
            in piano.righe
        )
        assert ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino).riuscito
        assert _leggi(ambiente.percorsi.database) == database_iniziale

    def test_un_giocatore_solo_da_stornare_e_al_singolare(self, ambiente):
        """Fino alla 10.13.5 la conferma diceva si toglie questo torneo, per
        1 giocatori."""
        from copie_di_sicurezza import prepara_ripristino

        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        dati = _leggi(ambiente.percorsi.database)
        for giocatore in dati["players"][1:]:
            giocatore["tournaments_played"] = []
        _scrivi(ambiente.percorsi.database, dati)
        copia = _copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]

        piano = prepara_ripristino(copia, ambiente.percorsi)

        assert piano.rifiuto is None
        assert "dal database dei giocatori si toglie questo torneo, per un giocatore:" in piano.righe

    def test_un_torneo_finalizzato_dopo_ferma_la_riapertura(self, ambiente):
        """Un secondo torneo con gli stessi giocatori, finalizzato dopo:
        riaprire il primo si rifiuta, dice quale riaprire prima e non
        scrive niente."""
        from copie_di_sicurezza import ripristina

        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        copia = _copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]
        secondo = _torneo_finito()
        secondo.update(name="Coppa Autunno", tournament_id="COPPA_AUTUNNO", start_date="2026-08-01", end_date="2026-08-01")
        file_secondo = str(ambiente.tmp / "Tornello - Coppa_Autunno.json")
        _scrivi(file_secondo, secondo)
        assert _finalizza(secondo, file_secondo) is True
        database = _byte(ambiente.percorsi.database)
        cartella = _cartella_d_archivio(ambiente)

        esito = ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino)

        assert not esito.riuscito
        assert "Coppa Autunno" in esito.righe[0]
        assert "Prima va riaperto" in esito.righe[0]
        assert _byte(ambiente.percorsi.database) == database
        assert os.path.isdir(cartella)
        assert not os.path.exists(ambiente.file_torneo)
        assert _copie(ambiente.percorsi.backup, "pre_ripristino") == []
        assert ambiente.cestino.ricevuti == []

    def test_se_l_archivio_non_va_nel_cestino_si_rimette_tutto(self, ambiente):
        from copie_di_sicurezza import ripristina

        esterna = ambiente.tmp / "esterna"
        esterna.mkdir()
        ambiente.torneo["custom_save_path"] = str(esterna)
        _scrivi(ambiente.file_torneo, ambiente.torneo)
        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        database = _byte(ambiente.percorsi.database)
        cartella = _cartella_d_archivio(ambiente)
        esterno = esterna / f"Tornello - {NOME}.json"
        contenuto_esterno = _byte(esterno)
        copia = _copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]
        ambiente.cestino.rifiuta.add(os.path.abspath(cartella))

        esito = ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino)

        assert not esito.riuscito
        assert _byte(ambiente.percorsi.database) == database
        assert os.path.isdir(cartella)
        assert _byte(esterno) == contenuto_esterno
        assert not os.path.exists(ambiente.file_torneo)
        testo = "\n".join(esito.righe)
        assert "Rimesso com'era: il database dei giocatori." in testo
        assert "Rimesso com'era: il file concluso della cartella esterna." in testo
        assert "Rimesso com'era: il file del torneo nella cartella del programma." in testo

    def test_se_il_database_non_si_scrive_il_torneo_se_ne_va(self, ambiente, monkeypatch):
        import copie_di_sicurezza
        from copie_di_sicurezza import ripristina

        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        database = _byte(ambiente.percorsi.database)
        cartella = _cartella_d_archivio(ambiente)
        copia = _copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]
        vera = copie_di_sicurezza.scrivi_json_atomico

        def scrittura(percorso, dati, indent=1):
            if os.path.abspath(percorso) == os.path.abspath(ambiente.percorsi.database):
                raise PermissionError("database bloccato")
            return vera(percorso, dati, indent)

        monkeypatch.setattr(copie_di_sicurezza, "scrivi_json_atomico", scrittura)

        esito = ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino)

        assert not esito.riuscito
        assert _byte(ambiente.percorsi.database) == database
        assert os.path.isdir(cartella)
        assert not os.path.exists(ambiente.file_torneo)
        assert ambiente.cestino.ricevuti == [os.path.abspath(ambiente.file_torneo)]

    def test_il_database_scritto_e_non_riletto_si_rimette(self, ambiente, monkeypatch):
        """La scrittura del database riesce, la rilettura no: il database e'
        cambiato, e va rimesso anche se il passo risulta non riuscito."""
        from copie_di_sicurezza import ripristina

        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        database = _byte(ambiente.percorsi.database)
        cartella = _cartella_d_archivio(ambiente)
        copia = _copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]
        _rilettura_bloccata(monkeypatch, ambiente.percorsi.database)

        esito = ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino)

        assert not esito.riuscito
        assert _byte(ambiente.percorsi.database) == database
        assert os.path.isdir(cartella)
        assert not os.path.exists(ambiente.file_torneo)
        testo = "\n".join(esito.righe)
        assert "Rimesso com'era: il database dei giocatori." in testo
        assert "Rimesso com'era: il file del torneo nella cartella del programma." in testo

    def test_il_torneo_scritto_e_non_riletto_se_ne_va(self, ambiente, monkeypatch):
        """Il primo passo: il torneo scritto nella cartella del programma e
        non riletto non resta li' come torneo in corso."""
        from copie_di_sicurezza import ripristina

        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        database = _byte(ambiente.percorsi.database)
        copia = _copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]
        _rilettura_bloccata(monkeypatch, ambiente.file_torneo)

        esito = ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino)

        assert not esito.riuscito
        assert not os.path.exists(ambiente.file_torneo)
        assert _byte(ambiente.percorsi.database) == database
        assert "Rimesso com'era: il file del torneo nella cartella del programma." in esito.righe
        assert "Nessun file è stato cambiato." not in esito.righe

    def test_il_cestino_che_prende_solo_il_json_archiviato(self, ambiente):
        """Il cestino prende il json archiviato e poi si ferma: il json torna
        nella cartella d'archivio dalla sua copia, e il torneo non sparisce
        dall'albero."""
        from copie_di_sicurezza import ripristina

        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        database = _byte(ambiente.percorsi.database)
        cartella = _cartella_d_archivio(ambiente)
        archiviato = os.path.join(cartella, f"Tornello - {NOME}.json")
        contenuto = _byte(archiviato)
        copia = _copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]
        fondo = ambiente.tmp / "cestino_a_meta"
        fondo.mkdir()

        def cestino(percorso, finestra=None):
            if os.path.abspath(percorso) == os.path.abspath(cartella):
                shutil.move(archiviato, fondo / "json")
                return False
            return ambiente.cestino(percorso)

        esito = ripristina(copia, ambiente.percorsi, cestino=cestino)

        assert not esito.riuscito
        assert _byte(archiviato) == contenuto
        assert _byte(ambiente.percorsi.database) == database
        assert not os.path.exists(ambiente.file_torneo)
        assert "Rimesso com'era: il file del torneo archiviato." in esito.righe

    def test_finalizzato_ma_fuori_dall_archivio_si_rifiuta(self, ambiente):
        """L'archiviazione non verificata lascia il json concluso nella
        cartella del programma, con il database gia' aggiornato. Rimessa come
        torneo in corso, la copia lascerebbe nel database i suoi effetti: il
        ripristino si rifiuta, dice perche' e come sistemare, e non scrive
        niente. Lo stesso senza il json concluso, per il solo database."""
        from copie_di_sicurezza import prepara_ripristino, ripristina

        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        cartella = _cartella_d_archivio(ambiente)
        shutil.copyfile(os.path.join(cartella, f"Tornello - {NOME}.json"), ambiente.file_torneo)
        shutil.rmtree(cartella)
        database, concluso = _byte(ambiente.percorsi.database), _byte(ambiente.file_torneo)
        copia = _copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]

        piano = prepara_ripristino(copia, ambiente.percorsi)
        esito = ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino)

        assert piano.tipo == "finalizzato"
        assert f"Il torneo {NOME} risulta già finalizzato:" in piano.rifiuto
        assert "il database dei giocatori lo ha nello storico di 4 giocatori" in piano.rifiuto
        assert f"il file Tornello - {NOME}.json lo contiene già concluso" in piano.rifiuto
        assert not esito.riuscito
        assert (_byte(ambiente.percorsi.database), _byte(ambiente.file_torneo)) == (database, concluso)
        assert _copie(ambiente.percorsi.backup, "pre_ripristino") == []

        os.remove(ambiente.file_torneo)
        piano = prepara_ripristino(copia, ambiente.percorsi)

        assert "il database dei giocatori lo ha nello storico di 4 giocatori" in piano.rifiuto
        assert "lo contiene già concluso" not in piano.rifiuto

        # Con il torneo nello storico di un giocatore solo, il singolare:
        # fino alla 10.13.5 si leggeva nello storico di 1 giocatori.
        dati = _leggi(ambiente.percorsi.database)
        for giocatore in dati["players"][1:]:
            giocatore["tournaments_played"] = []
        _scrivi(ambiente.percorsi.database, dati)
        piano = prepara_ripristino(copia, ambiente.percorsi)

        assert "il database dei giocatori lo ha nello storico di un giocatore;" in piano.rifiuto

    def test_un_torneo_aperto_da_un_file_con_un_altro_nome(self, ambiente):
        """Il json archiviato ha il nome del file da cui il torneo e' stato
        aperto: si trova dal contenuto, e il torneo si riapre."""
        from copie_di_sicurezza import prepara_ripristino, ripristina

        altro_file = str(ambiente.tmp / f"Tornello - {NOME}_bis.json")
        os.replace(ambiente.file_torneo, altro_file)
        assert _finalizza(ambiente.torneo, altro_file) is True
        copia = _copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]
        database_di_prima = _leggi(_copie(ambiente.percorsi.backup, "pre_finalize_db")[0])

        piano = prepara_ripristino(copia, ambiente.percorsi)
        esito = ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino)

        assert (piano.tipo, piano.rifiuto) == ("finalizzato", None)
        assert os.path.basename(piano.archiviato) == f"Tornello - {NOME}_bis.json"
        assert esito.riuscito, esito.righe
        assert _leggi(ambiente.file_torneo) == _leggi(copia)
        assert _leggi(ambiente.percorsi.database) == database_di_prima

    def test_se_la_copia_di_prima_non_torna_non_la_si_nomina(self, ambiente):
        """Dopo la finalizzazione gli Elo cambiano ancora, per esempio con un
        aggiornamento FIDE: la copia del database di prima non torna, e la
        conferma non dice che gli Elo vengono da li'."""
        from copie_di_sicurezza import prepara_ripristino

        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        dati = _leggi(ambiente.percorsi.database)
        for giocatore in dati["players"]:
            giocatore["current_elo"] += 5
        _scrivi(ambiente.percorsi.database, dati)
        copia = _copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]

        righe = prepara_ripristino(copia, ambiente.percorsi).righe

        assert not any(r.startswith("Gli Elo di prima vengono dalla copia") for r in righe)
        assert any(r.startswith("La copia Tornello - Players_db_pre_finalize_db_") and "non torna" in r for r in righe)

    def test_il_database_di_prima_della_riapertura_avverte(self, ambiente):
        """Rimettere il database di prima di una riapertura, che ha il torneo
        oggi in corso gia' finalizzato, e' possibile ma avverte per prima
        cosa; dopo, riaprire di nuovo il torneo si rifiuta, perche' il
        database lo ha e l'archivio no."""
        from copie_di_sicurezza import prepara_ripristino, ripristina

        assert _finalizza(ambiente.torneo, ambiente.file_torneo) is True
        copia = _copie(ambiente.percorsi.backup, "pre_finalize_torneo")[0]
        assert ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino).riuscito
        copia_del_database = next(c for c in _copie(ambiente.percorsi.backup, "pre_ripristino") if "Players_db" in c)

        piano = prepara_ripristino(copia_del_database, ambiente.percorsi)

        assert piano.rifiuto is None
        assert piano.avvertenze[0].startswith(f"Attenzione: nella copia il torneo {NOME}, che oggi è in corso, è già finalizzato.")
        assert ripristina(copia_del_database, ambiente.percorsi, cestino=ambiente.cestino).riuscito
        assert "risulta già finalizzato" in prepara_ripristino(copia, ambiente.percorsi).rifiuto


class TestRipristinoDelDatabase:
    def _copia(self, ambiente, dati):
        return str(_metti(ambiente.tmp, "Tornello - Players_db_chiusura_db_20260920_100000.json", dati))

    def test_il_database_torna_com_era(self, ambiente):
        from copie_di_sicurezza import prepara_ripristino, ripristina

        vecchio = _leggi(ambiente.percorsi.database)
        vecchio["players"][0]["current_elo"] = 1700.0
        copia = self._copia(ambiente, vecchio)
        prima = _byte(ambiente.percorsi.database)

        piano = prepara_ripristino(copia, ambiente.percorsi)
        esito = ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino)

        assert any("Elo 1800 a 1700 (-100)" in r for r in piano.righe)
        assert esito.riuscito
        assert _leggi(ambiente.percorsi.database) == vecchio
        assert _byte(esito.copie[0]) == prima
        with open(ambiente.percorsi.database_txt, encoding="utf-8-sig") as f:
            assert "1700" in f.read()

    def test_una_copia_vuota_o_senza_identificativi_si_rifiuta(self, ambiente):
        from copie_di_sicurezza import prepara_ripristino

        vuota = self._copia(ambiente, {"schema_version": 2, "players": []})
        assert "non contiene giocatori" in prepara_ripristino(vuota, ambiente.percorsi).rifiuto

        senza = _metti(ambiente.tmp, "Tornello - Players_db_chiusura_db_20260920_110000.json", {"schema_version": 2, "players": [{"last_name": "X"}]})
        assert "senza identificativo" in prepara_ripristino(str(senza), ambiente.percorsi).rifiuto

    def test_la_copia_di_un_altro_database_si_rifiuta(self, ambiente):
        """Le copie dei database delle prove, come Players_db_complex, non
        prendono il posto del database dei giocatori del programma."""
        from copie_di_sicurezza import prepara_ripristino, ripristina

        estraneo = {"schema_version": 2, "players": [_giocatore("ZZ", "Estraneo")]}
        copia = str(_metti(ambiente.tmp, "Tornello - Players_db_complex_pre_finalize_db_20260901_100000.json", estraneo))
        prima = _byte(ambiente.percorsi.database)

        piano = prepara_ripristino(copia, ambiente.percorsi)
        esito = ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino)

        assert "viene dal file Tornello - Players_db_complex.json" in piano.rifiuto
        assert not esito.riuscito
        assert _byte(ambiente.percorsi.database) == prima
        assert _copie(ambiente.percorsi.backup, "pre_ripristino") == []

    def test_se_sparisce_piu_della_meta_lo_dice_per_primo(self, ambiente):
        from copie_di_sicurezza import prepara_ripristino

        vecchio = _leggi(ambiente.percorsi.database)
        vecchio["players"] = vecchio["players"][:1]
        copia = self._copia(ambiente, vecchio)

        piano = prepara_ripristino(copia, ambiente.percorsi)

        assert piano.rifiuto is None
        assert piano.avvertenze[0].startswith("Attenzione: sparirebbero 3 dei 4 giocatori di oggi, più della metà.")
        assert piano.righe[0] == f"Il database dei giocatori tornerebbe com'era nella copia {os.path.basename(copia)}."

    def test_l_unico_giocatore_che_sparirebbe_e_al_singolare(self, ambiente):
        """Uno che sparisce e' piu' della meta' solo in un database di un
        giocatore: fino alla 10.13.5 si leggeva sparirebbero 1 dei 1
        giocatori."""
        from copie_di_sicurezza import prepara_ripristino

        oggi = _leggi(ambiente.percorsi.database)
        vecchio = copy.deepcopy(oggi)
        oggi["players"] = oggi["players"][:1]
        vecchio["players"] = vecchio["players"][1:]
        _scrivi(ambiente.percorsi.database, oggi)
        copia = self._copia(ambiente, vecchio)

        piano = prepara_ripristino(copia, ambiente.percorsi)

        assert piano.avvertenze[0] == "Attenzione: sparirebbe l'unico giocatore di oggi. Controlla che la copia sia quella giusta."

    def test_un_database_attuale_illeggibile_si_puo_sostituire(self, ambiente):
        from copie_di_sicurezza import ripristina

        buono = _leggi(ambiente.percorsi.database)
        copia = self._copia(ambiente, buono)
        with open(ambiente.percorsi.database, "w", encoding="utf-8") as f:
            f.write("{rovinato")

        esito = ripristina(copia, ambiente.percorsi, cestino=ambiente.cestino)

        assert esito.riuscito
        assert _leggi(ambiente.percorsi.database) == buono
        with open(esito.copie[0], encoding="utf-8") as f:
            assert f.read() == "{rovinato"


class TestConservazione:
    def test_restano_le_ultime_dieci_per_origine(self, tmp_path):
        from copie_di_sicurezza import copie_da_scartare, elenca_copie, righe_della_conservazione

        torneo = _torneo("Coppa")
        for giorno in range(1, 14):
            _metti(tmp_path, f"Tornello - Coppa_chiusura_torneo_202609{giorno:02d}_100000.json", torneo)
        for giorno in range(1, 4):
            _metti(tmp_path, f"Tornello - Coppa_pre_finalize_torneo_202608{giorno:02d}_100000.json", torneo)
            _metti(tmp_path, f"Tornello - Coppa_pre_ripristino_202608{giorno:02d}_100000.json", torneo)
        db = {"schema_version": 2, "players": [_giocatore("G1", "Rossi")]}
        for giorno in range(1, 12):
            _metti(tmp_path, f"Tornello - Players_db_chiusura_db_202609{giorno:02d}_100000.json", db)
        _metti(tmp_path, "Tornello - Coppa_senza_data.json", torneo)

        copie = elenca_copie(str(_cartella_backup(tmp_path)))
        scarto = copie_da_scartare(copie)
        righe = righe_della_conservazione(scarto)

        nomi = [c.nome for c in scarto]
        assert nomi == [
            "Tornello - Coppa_chiusura_torneo_20260901_100000.json",
            "Tornello - Players_db_chiusura_db_20260901_100000.json",
            "Tornello - Coppa_chiusura_torneo_20260902_100000.json",
            "Tornello - Coppa_chiusura_torneo_20260903_100000.json",
        ]
        assert "  Coppa: 3" in righe
        assert "  Database dei giocatori: 1" in righe
        assert "Andrebbero nel cestino 4 copie:" in righe
        # La regola si legge per intero, come la dice il manuale.
        for momento in (
            "prima della finalizzazione",
            "prima di una sostituzione in archivio",
            "da una finalizzazione ripetuta",
            "prima di un ripristino",
        ):
            assert f"  {momento};" in righe
        assert "e restano i file con un nome che Tornello non riconosce." in righe

    def test_niente_da_scartare(self, tmp_path):
        from copie_di_sicurezza import copie_da_scartare, righe_della_conservazione

        assert copie_da_scartare([]) == []
        assert righe_della_conservazione([])[0].startswith("Nessuna copia")

    def test_una_copia_sola_e_al_singolare(self):
        """Fino alla 10.13.5 si leggeva Andrebbero nel cestino 1 copie."""
        from copie_di_sicurezza import righe_della_conservazione

        righe = righe_della_conservazione([types.SimpleNamespace(origine="Coppa")])

        assert "Andrebbe nel cestino una copia:" in righe
        assert "  Coppa: 1" in righe
        assert not any(r.startswith("Andrebbero") for r in righe)

    def test_le_chiusure_identiche_non_si_ripetono(self, tmp_path):
        import config
        import utils

        torneo = tmp_path / "Tornello - Coppa.json"
        _scrivi(torneo, _torneo("Coppa"))
        _scrivi(config.PLAYER_DB_FILE, {"schema_version": 2, "players": [_giocatore("G1", "Rossi")]})
        cartella = str(_cartella_backup(tmp_path))

        utils.copie_di_chiusura(str(torneo))
        utils.copie_di_chiusura(str(torneo))
        assert len(_copie(cartella, "chiusura_torneo")) == 1
        assert len(_copie(cartella, "chiusura_db")) == 1

        _scrivi(torneo, _torneo("Coppa", current_round=2))
        utils.copie_di_chiusura(str(torneo))
        assert len(_copie(cartella, "chiusura_torneo")) == 2
        assert len(_copie(cartella, "chiusura_db")) == 1

    def test_l_ultima_copia_e_il_database_di_prima(self, tmp_path):
        from copie_di_sicurezza import database_di_prima, ultima_copia_di

        db = {"schema_version": 2, "players": []}
        _metti(tmp_path, "Tornello - Players_db_chiusura_db_20260920_100000.json", db)
        ultima = _metti(tmp_path, "Tornello - Players_db_pre_finalize_db_20260921_100000_2.json", db)
        _metti(tmp_path, "Tornello - Players_db_pre_finalize_db_20260921_100000.json", db)
        _metti(tmp_path, "Tornello - Players_db_complex_chiusura_db_20260925_100000.json", db)
        compagna = _metti(tmp_path, "Tornello - Coppa_pre_finalize_torneo_20260921_100001_2.json", _torneo())
        cartella = str(_cartella_backup(tmp_path))

        assert ultima_copia_di(str(tmp_path / "Tornello - Players_db.json"), cartella) == str(ultima)
        assert database_di_prima(str(compagna), cartella) == str(ultima)
        assert database_di_prima(str(ultima), cartella) is None


class DialogoFinto:
    """Al posto di AccessibleMsgDialog: annota titolo, testo, stile e No
    predefinito, e risponde con la prossima risposta della coda, o OK."""

    def __init__(self, registro, risposte):
        self.registro = registro
        self.risposte = risposte

    def __call__(self, parent, titolo, messaggio, style=None, settings=None, no_predefinito=False):
        self.registro.append(types.SimpleNamespace(titolo=titolo, testo=messaggio, style=style, no_predefinito=no_predefinito))
        return self

    def ShowModal(self):
        import wx

        return self.risposte.pop(0) if self.risposte else wx.ID_OK

    def Destroy(self):
        pass


@pytest.fixture
def finestra(ambiente, app_grafica, monkeypatch):
    """La finestra Copie di sicurezza sulla cartella della prova: tre copie
    del torneo, due del database, dialoghi e cestino finti, suoni muti. Il
    torneo aperto e' quello della prova."""
    import wx

    from gui.dialogs import backup_cleanup_dialog as modulo

    torneo = ambiente.torneo
    for giorno, turni in ((20, 0), (21, 1), (22, 1)):
        dati = copy.deepcopy(torneo)
        dati["rounds"] = dati["rounds"][:turni]
        contesto = "creazione" if not turni else f"turno_{turni}"
        _metti(ambiente.tmp, f"Tornello - {NOME}_{contesto}_202609{giorno}_100000.json", dati)
    database = _leggi(ambiente.percorsi.database)
    for giorno in (20, 23):
        _metti(ambiente.tmp, f"Tornello - Players_db_chiusura_db_202609{giorno}_180000.json", database)
    dialoghi, risposte, suoni, ripristini = [], [], [], []
    monkeypatch.setattr(modulo, "AccessibleMsgDialog", DialogoFinto(dialoghi, risposte))
    monkeypatch.setattr(modulo, "delete_file_to_trash", ambiente.cestino)
    monkeypatch.setattr(modulo, "play_sound", lambda evento, *a, **k: suoni.append(evento))
    telaio = wx.Frame(None)
    dlg = modulo.BackupCleanupDialog(
        telaio,
        {},
        torneo_aperto=ambiente.file_torneo,
        dopo_il_ripristino=ripristini.append,
        percorsi=ambiente.percorsi,
    )
    yield types.SimpleNamespace(
        dlg=dlg, dialoghi=dialoghi, risposte=risposte, suoni=suoni, ripristini=ripristini, wx=wx, ambiente=ambiente
    )
    dlg.Destroy()
    telaio.Destroy()


def _seleziona_solo(dlg, indice):
    for vecchio in dlg.indici_selezionati():
        dlg.list_ctrl.Select(vecchio, False)
    dlg.list_ctrl.Select(indice, True)
    dlg.list_ctrl.Focus(indice)


class TestFinestra:
    def test_origini_lista_e_dettagli(self, finestra):
        dlg = finestra.dlg

        voci = [dlg.scelta_origine.GetString(i) for i in range(dlg.scelta_origine.GetCount())]
        assert voci == ["Tutte (5)", "Coppa_Prova (3)", "Database dei giocatori (2)"]
        # Si apre sulle copie del torneo aperto, con la piu' recente selezionata.
        assert dlg.scelta_origine.GetSelection() == 1
        assert dlg.list_ctrl.GetItemCount() == 3
        assert dlg.indici_selezionati() == [2]
        assert dlg.list_ctrl.GetItemText(2, 0) == "2026-09-22 10:00:00"
        assert dlg.list_ctrl.GetItemText(2, 1) == "al turno 1 abbinato"
        assert dlg.list_ctrl.GetItemText(2, 2) == "T1/1, 2/2 ris., 4 gioc."
        assert dlg.list_ctrl.GetItemText(0, 1) == "alla nascita del torneo"
        assert "Momento: al turno 1 abbinato" in dlg.dettagli.GetValue()
        assert "Copie nella cartella: 5" in dlg.stats_text.GetValue()

        dlg.scelta_origine.SetSelection(0)
        dlg.on_origine(None)

        assert dlg.list_ctrl.GetItemCount() == 5
        assert dlg.list_ctrl.GetItemText(4, 2) == "Database dei giocatori, 4 gioc."

    def test_la_copia_scelta_arriva_selezionata(self, finestra, monkeypatch):
        from gui.dialogs.backup_cleanup_dialog import BackupCleanupDialog

        prima = _copie(finestra.ambiente.percorsi.backup, "creazione")[0]
        dlg = BackupCleanupDialog(
            finestra.dlg.GetParent(), {}, seleziona=[prima], percorsi=finestra.ambiente.percorsi
        )
        try:
            assert dlg.scelta_origine.GetSelection() == 0
            assert [dlg.visibili[i].percorso for i in dlg.indici_selezionati()] == [prima]
        finally:
            dlg.Destroy()

    def test_ripristino_con_conferma_e_no_predefinito(self, finestra):
        dlg, wx = finestra.dlg, finestra.wx
        cambiato = copy.deepcopy(finestra.ambiente.torneo)
        cambiato["rounds"][0]["matches"][0]["result"] = "0-1"
        _scrivi(finestra.ambiente.file_torneo, cambiato)
        _seleziona_solo(dlg, 2)
        finestra.risposte.append(wx.ID_YES)

        dlg.on_ripristina(None)

        conferma, esito = finestra.dialoghi
        assert conferma.style == wx.YES_NO
        assert conferma.no_predefinito is True
        assert "Risultati che cambierebbero: 1" in conferma.testo
        assert esito.titolo == "Ripristino riuscito"
        assert _leggi(finestra.ambiente.file_torneo) == finestra.ambiente.torneo
        assert finestra.suoni == ["ripristino"]
        assert [e.riuscito for e in finestra.ripristini] == [True]
        # La copia di prima del ripristino compare subito nella lista.
        assert dlg.list_ctrl.GetItemCount() == 4

    def test_col_no_non_cambia_niente(self, finestra):
        dlg, wx = finestra.dlg, finestra.wx
        prima = _byte(finestra.ambiente.file_torneo)
        _seleziona_solo(dlg, 0)
        finestra.risposte.append(wx.ID_NO)

        dlg.on_ripristina(None)

        assert len(finestra.dialoghi) == 1
        assert _byte(finestra.ambiente.file_torneo) == prima
        assert finestra.ripristini == []
        assert _copie(finestra.ambiente.percorsi.backup, "pre_ripristino") == []

    def test_confronto_senza_scrivere(self, finestra):
        dlg = finestra.dlg
        prima = _byte(finestra.ambiente.file_torneo)
        _seleziona_solo(dlg, 0)

        dlg.on_confronta(None)

        (confronto,) = finestra.dialoghi
        assert confronto.titolo == "Confronto con lo stato attuale"
        assert "Turni che si perderebbero: 1" in confronto.testo
        assert _byte(finestra.ambiente.file_torneo) == prima

    def test_con_due_copie_selezionate_non_si_ripristina(self, finestra):
        dlg = finestra.dlg
        dlg.seleziona_tutti()

        dlg.on_ripristina(None)

        assert [d.titolo for d in finestra.dialoghi] == ["Una copia sola"]
        assert finestra.suoni == ["errore"]

    def test_conservazione_con_anteprima(self, finestra):
        dlg, wx = finestra.dlg, finestra.wx
        database = _leggi(finestra.ambiente.percorsi.database)
        for giorno in range(1, 11):
            _metti(finestra.ambiente.tmp, f"Tornello - Players_db_chiusura_db_202608{giorno:02d}_180000.json", database)
        dlg.populate_list()
        finestra.risposte.append(wx.ID_YES)

        dlg.on_conservazione(None)

        (anteprima,) = finestra.dialoghi
        assert anteprima.no_predefinito is True
        assert "Andrebbero nel cestino 2 copie:" in anteprima.testo
        assert "  Database dei giocatori: 2" in anteprima.testo
        assert [os.path.basename(p) for p in finestra.ambiente.cestino.ricevuti] == [
            "Tornello - Players_db_chiusura_db_20260801_180000.json",
            "Tornello - Players_db_chiusura_db_20260802_180000.json",
        ]
        assert finestra.suoni == ["cancellato"]
        assert "Copie nella cartella: 13" in dlg.stats_text.GetValue()
        # Il cestino riceve la finestra: una domanda di Windows le appartiene.
        assert finestra.ambiente.cestino.finestre == [dlg.GetHandle()] * 2

    def test_le_colonne_mostrano_tutto_il_testo(self, finestra):
        """Nessuna colonna piu' stretta della sua intestazione o della sua
        voce piu' lunga, misurate con il carattere della lista, sia con le
        copie del torneo sia con tutte, dove il contenuto comincia con
        l'origine."""
        dlg = finestra.dlg

        def controlla():
            lista = dlg.list_ctrl
            for colonna in range(lista.GetColumnCount()):
                testi = [lista.GetColumn(colonna).GetText()]
                testi += [lista.GetItemText(riga, colonna) for riga in range(lista.GetItemCount())]
                piu_largo = max(lista.GetTextExtent(t).width for t in testi)
                assert lista.GetColumnWidth(colonna) > piu_largo, (colonna, testi)

        controlla()
        dlg.scelta_origine.SetSelection(0)
        dlg.on_origine(None)
        controlla()
        assert dlg.list_ctrl.GetMinSize().width > 0

    def test_le_avvertenze_vengono_prima_della_domanda(self, finestra):
        dlg, wx = finestra.dlg, finestra.wx
        database = _leggi(finestra.ambiente.percorsi.database)
        database["players"] = database["players"][:1]
        nome = "Tornello - Players_db_chiusura_db_20260924_180000.json"
        _metti(finestra.ambiente.tmp, nome, database)
        dlg.populate_list(origine=None, seleziona=[str(_cartella_backup(finestra.ambiente.tmp) / MESE / nome)])
        prima = _byte(finestra.ambiente.percorsi.database)
        finestra.risposte.append(wx.ID_NO)

        dlg.on_ripristina(None)

        (conferma,) = finestra.dialoghi
        righe = conferma.testo.split("\n")
        assert righe[0].startswith("Attenzione: sparirebbero 3 dei 4 giocatori di oggi")
        assert righe[1].startswith("Ripristinare la copia alla chiusura del programma")
        assert righe[2] == f"File: {nome}"
        assert _byte(finestra.ambiente.percorsi.database) == prima

    def test_i_controlli_hanno_il_nome_dell_etichetta(self, finestra):
        import sys

        if sys.platform != "win32":
            pytest.skip("MSAA c'e' solo su Windows")
        from test_finestre_adattabili import _msaa

        dlg = finestra.dlg
        for etichetta, controllo in (
            (dlg.lbl_origine, dlg.scelta_origine),
            (dlg.lbl_list, dlg.list_ctrl),
            (dlg.lbl_dettagli, dlg.dettagli),
            (dlg.lbl_stats, dlg.stats_text),
        ):
            nome = _msaa(controllo)[1][0][0]
            assert nome == etichetta.GetLabelText(), (nome, etichetta.GetLabelText())
        # Le voci della lista tengono il loro testo.
        assert _msaa(dlg.list_ctrl, 1)[1][1][0] == dlg.list_ctrl.GetItemText(0, 0)


class TestNoPredefinito:
    def test_il_no_predefinito_e_solo_su_richiesta(self, app_grafica):
        import wx

        from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog

        telaio = wx.Frame(None)
        prudente = AccessibleMsgDialog(telaio, "Titolo", "Testo", style=wx.YES_NO, settings={}, no_predefinito=True)
        solito = AccessibleMsgDialog(telaio, "Titolo", "Testo", style=wx.YES_NO, settings={})
        try:
            assert prudente.pulsante_no.GetId() == wx.ID_NO
            assert prudente.GetDefaultItem() is prudente.pulsante_no
            assert prudente.GetEscapeId() == wx.ID_NO
            assert solito.GetDefaultItem() is solito.pulsante_si
            assert solito.GetEscapeId() == wx.ID_ANY
        finally:
            prudente.Destroy()
            solito.Destroy()
            telaio.Destroy()


class TestDopoIlRipristino:
    """La finestra principale dopo un ripristino: il torneo aperto si
    ricarica subito, un altro torneo aperto resta dov'e'."""

    def _telaio(self, aperto, in_memoria=True):
        registro = []
        telaio = types.SimpleNamespace(
            active_filename=aperto,
            current_tournament={"name": "X"} if in_memoria else None,
            populate_tree=lambda: registro.append("albero"),
            _save_state=lambda: registro.append("salvato"),
        )

        def carica(percorso):
            registro.append(("caricato", percorso))
            telaio.active_filename = percorso

        telaio.load_tournament = carica
        return telaio, registro

    def test_il_torneo_aperto_si_ricarica(self, tmp_path):
        from copie_di_sicurezza import Esito
        from gui import main_frame as mf

        aperto = tmp_path / "Tornello - X.json"
        aperto.write_text("{}", encoding="utf-8")
        telaio, registro = self._telaio(str(aperto))

        mf.MainFrame._dopo_il_ripristino(telaio, Esito(True, tipo="torneo", destinazione=str(aperto)))

        assert registro == [("caricato", str(aperto)), "salvato"]

    def test_un_altro_torneo_aperto_resta(self, tmp_path):
        from copie_di_sicurezza import Esito
        from gui import main_frame as mf

        aperto = tmp_path / "Tornello - X.json"
        aperto.write_text("{}", encoding="utf-8")
        telaio, registro = self._telaio(str(aperto))

        mf.MainFrame._dopo_il_ripristino(telaio, Esito(True, tipo="torneo", destinazione=str(tmp_path / "Tornello - Y.json")))

        assert registro == ["albero"]

    def test_un_torneo_riaperto_senza_torneo_aperto_si_carica(self, tmp_path):
        from copie_di_sicurezza import Esito
        from gui import main_frame as mf

        telaio, registro = self._telaio(None, in_memoria=False)
        riaperto = str(tmp_path / "Tornello - Y.json")

        mf.MainFrame._dopo_il_ripristino(telaio, Esito(True, tipo="finalizzato", destinazione=riaperto))

        assert registro[0] == ("caricato", riaperto)

    def test_un_ripristino_non_riuscito_rilegge_solo_l_albero(self, tmp_path):
        from copie_di_sicurezza import Esito
        from gui import main_frame as mf

        telaio, registro = self._telaio(str(tmp_path / "Tornello - X.json"))

        mf.MainFrame._dopo_il_ripristino(telaio, Esito(False, tipo="torneo", destinazione=str(tmp_path / "Tornello - X.json")))

        assert registro == ["albero"]


class TestManuale:
    """La sezione 10.4 del manuale cita etichette e testi della finestra
    Copie di sicurezza: ognuno deve essere scritto dal programma, con i
    segnaposto al posto dei numeri e senza la e commerciale delle scorciatoie.
    Un'etichetta cambiata nel codice e non nel manuale non passa."""

    def test_le_citazioni_della_10_4_sono_scritte_dal_programma(self):
        import re

        from test_manuale import SEGNAPOSTO, citazioni, leggi, sezione, stringhe_del_sorgente

        sorgenti = (
            os.path.join("gui", "dialogs", "backup_cleanup_dialog.py"),
            os.path.join("gui", "dialogs", "accessible_msg_dialog.py"),
            "copie_di_sicurezza.py",
        )
        modelli = [
            re.compile(".+".join(re.escape(p) for p in SEGNAPOSTO.split(s.replace("&", ""))), re.DOTALL)
            for relativo in sorgenti
            for s in stringhe_del_sorgente(relativo)
            if any(c.isalpha() for c in SEGNAPOSTO.sub("", s))
        ]
        # Il nome di una copia e' un esempio: lo compone create_backup.
        esempi = ("Tornello - Autunneo2_chiusura_torneo_20260923_160512.json",)
        trovate = citazioni(sezione(leggi("MANUALE.txt"), (10, 4)))

        assert len(trovate) >= 10
        for citazione in trovate:
            if citazione in esempi:
                continue
            assert any(m.fullmatch(citazione) for m in modelli), citazione
