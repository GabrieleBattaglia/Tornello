"""Prove sulla finalizzazione di un torneo, nella finestra e in console, e
sull'archiviazione del suo file (issue 39, prima parte).

Tutto lavora nella cartella temporanea della prova: la deviazione del
conftest porta li' il database dei giocatori, l'archivio, le copie di
sicurezza e il file del torneo, e ogni prova lo controlla prima di
cominciare. I suoni sono sostituiti da una funzione muta."""

import copy
import json
import os
import types

import pytest

NOME = "Coppa_Prova"
INIZIO = "2026-07-01"
ELO_INIZIALI = {"G1": 1800, "G2": 1700, "G3": 1600, "G4": 1500}


def _voce(turno, avversario, colore, risultato, punti):
    return {
        "round": turno,
        "opponent_id": avversario,
        "color": colore,
        "result": risultato,
        "score": punti,
    }


def _torneo_finito():
    """Un torneo di quattro giocatori e un turno solo, gia' giocato: G1
    batte G2, G3 e G4 pattano. Abbastanza per avere variazioni Elo, partite
    e medaglie, senza passare dal motore degli abbinamenti."""
    from models import Player

    storici = {
        "G1": [_voce(1, "G2", "white", "1-0", 1.0)],
        "G2": [_voce(1, "G1", "black", "1-0", 0.0)],
        "G3": [_voce(1, "G4", "white", "1/2-1/2", 0.5)],
        "G4": [_voce(1, "G3", "black", "1/2-1/2", 0.5)],
    }
    giocatori = []
    for pid, elo in ELO_INIZIALI.items():
        giocatore = Player.from_dict(
            {
                "id": pid,
                "first_name": "Nome" + pid,
                "last_name": "Cognome" + pid,
                "initial_elo": float(elo),
                "current_elo": float(elo),
                "results_history": storici[pid],
            }
        ).to_dict()
        giocatore["points"] = sum(v["score"] for v in storici[pid])
        giocatore["opponents"] = [storici[pid][0]["opponent_id"]]
        giocatori.append(giocatore)
    return {
        "name": NOME,
        "tournament_id": "COPPA_PROVA",
        "site": "Imola",
        "start_date": INIZIO,
        "end_date": INIZIO,
        "total_rounds": 1,
        "current_round": 1,
        "bye_value": 1.0,
        "initial_board1_color_setting": "white1",
        "time_control": {"minutes": 90, "increment": 30, "pgn_value": "5400+30"},
        "tournament_category": "standard",
        "concluded": False,
        "players": giocatori,
        "rounds": [
            {
                "round": 1,
                "matches": [
                    {"id": 1, "round": 1, "white_player_id": "G1", "black_player_id": "G2", "result": "1-0", "is_scheduled": False},
                    {"id": 2, "round": 1, "white_player_id": "G3", "black_player_id": "G4", "result": "1/2-1/2", "is_scheduled": False},
                ],
            }
        ],
    }


@pytest.fixture
def banco(tmp_path, monkeypatch):
    """Database dei giocatori e file del torneo nella cartella temporanea,
    suoni muti. Restituisce i percorsi che servono alle prove."""
    return prepara_il_banco(tmp_path, monkeypatch)


def prepara_il_banco(tmp_path, monkeypatch):
    """Il lavoro della fixture banco, come funzione: la usano anche le prove
    della classifica dei tornei conclusi (test_classifica_salvata.py)."""
    import config
    import ui

    assert config.PLAYER_DB_FILE.startswith(str(tmp_path))
    assert ui.PLAYER_DB_FILE.startswith(str(tmp_path))
    assert ui.ARCHIVED_TOURNAMENTS_DIR.startswith(str(tmp_path))
    monkeypatch.setattr(ui, "play_sound", lambda *a, **k: None)

    giocatori_db = [
        {
            "id": pid,
            "first_name": "Nome" + pid,
            "last_name": "Cognome" + pid,
            "current_elo": float(elo),
            "initial_elo": float(elo),
            "games_played": 10,
            "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
            "tournaments_played": [],
        }
        for pid, elo in ELO_INIZIALI.items()
    ]
    with open(config.PLAYER_DB_FILE, "w", encoding="utf-8") as f:
        json.dump({"schema_version": 2, "players": giocatori_db}, f, indent=1)

    torneo = _torneo_finito()
    file_torneo = config.user_data_path(f"Tornello - {NOME}.json")
    _scrivi(file_torneo, torneo)
    return types.SimpleNamespace(
        db=config.PLAYER_DB_FILE,
        torneo=torneo,
        file_torneo=file_torneo,
        backup=config.user_data_path("backup"),
    )


def _scrivi(percorso, dati):
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump(dati, f, indent=1, ensure_ascii=False)


def _leggi(percorso):
    with open(percorso, encoding="utf-8") as f:
        return json.load(f)


def _giocatori_del_db(percorso):
    return {p["id"]: p for p in _leggi(percorso)["players"]}


def _cartella_archivio():
    from datetime import datetime

    import ui
    from utils import cartella_per_data

    mese = cartella_per_data(
        ui.ARCHIVED_TOURNAMENTS_DIR, datetime.strptime(INIZIO, "%Y-%m-%d"), crea=False
    )
    return os.path.join(mese, NOME)


def _copie(cartella_backup, contesto):
    trovate = []
    for radice, _cartelle, files in os.walk(cartella_backup):
        trovate += [os.path.join(radice, n) for n in files if f"_{contesto}_" in n]
    return sorted(trovate)


def _finalizza(banco, avvisi=None):
    """Finalizza come fa la finestra: database appena letto dal disco e il
    torneo come lo tiene in memoria."""
    from db_players import load_players_db
    from ui import finalize_tournament

    return finalize_tournament(
        copy.deepcopy(banco.torneo), load_players_db(), banco.file_torneo, avvisi
    )


def _finalizza_in_console(banco, messaggi=None):
    """Finalizza come fa la versione a riga di comando: il controller con il
    suo modello del torneo e il database che tiene aperto. messaggi, se
    c'e', riceve i messaggi e gli errori del controller."""
    import controller
    from db_players import load_players_db
    from models import Tournament

    if messaggi is None:
        messaggi = []
    interfaccia = types.SimpleNamespace(
        show_message=messaggi.append, show_error=messaggi.append
    )
    finto = types.SimpleNamespace(
        tournament=Tournament.from_dict(copy.deepcopy(banco.torneo)),
        players_db=load_players_db(),
        active_filename=banco.file_torneo,
        ui=interfaccia,
    )
    return controller.TournamentController._finalize_tournament(finto)


def _json_in_archivio(cartella=None):
    return os.path.join(cartella or _cartella_archivio(), f"Tornello - {NOME}.json")


def _nella_radice(cartella):
    """I file del torneo rimasti nella cartella del programma."""
    return sorted(n for n in os.listdir(cartella) if n.startswith(f"Tornello - {NOME}"))


def _leggi_byte(percorso):
    with open(percorso, "rb") as f:
        return f.read()


class TestFinalizzazioneRipetuta:
    """Una seconda finalizzazione dello stesso torneo, per esempio dopo aver
    rimesso in uso la copia di prima della finalizzazione, non deve toccare
    i giocatori che hanno gia' il torneo nello storico. Fino alla 10.8.7 la
    guardia copriva storico e medaglie, mentre Elo e partite giocate si
    sommavano di nuovo (issue 39)."""

    def test_elo_e_partite_non_raddoppiano(self, banco):
        assert _finalizza(banco) is True
        dopo_la_prima = _giocatori_del_db(banco.db)
        # La prova ha senso solo se la prima finalizzazione ha cambiato
        # qualcosa: G1 ha vinto, e il suo Elo e' salito.
        assert dopo_la_prima["G1"]["current_elo"] > ELO_INIZIALI["G1"]
        assert dopo_la_prima["G1"]["games_played"] == 11

        # Il torneo torna nella radice com'era prima della finalizzazione.
        _scrivi(banco.file_torneo, banco.torneo)
        avvisi = []
        assert _finalizza(banco, avvisi) is True
        dopo_la_seconda = _giocatori_del_db(banco.db)

        for pid in ELO_INIZIALI:
            prima, seconda = dopo_la_prima[pid], dopo_la_seconda[pid]
            assert seconda["current_elo"] == prima["current_elo"], pid
            assert seconda["games_played"] == prima["games_played"], pid
            assert seconda["medals"] == prima["medals"], pid
            assert len(seconda["tournaments_played"]) == 1, pid
        assert any("NomeG1 CognomeG1" in a and ": 4." in a for a in avvisi)

    def test_un_altra_edizione_con_lo_stesso_nome_conta(self, banco):
        """La finestra ricava l'identificativo dal nome: l'edizione
        dell'anno dopo ha lo stesso identificativo e un'altra data di
        inizio, e i suoi Elo si scrivono."""
        assert _finalizza(banco) is True
        dopo_la_prima = _giocatori_del_db(banco.db)

        banco.torneo["start_date"] = banco.torneo["end_date"] = "2027-07-01"
        _scrivi(banco.file_torneo, banco.torneo)
        avvisi = []
        assert _finalizza(banco, avvisi) is True
        dopo_la_seconda = _giocatori_del_db(banco.db)

        assert dopo_la_seconda["G1"]["games_played"] == 12
        assert dopo_la_seconda["G1"]["current_elo"] > dopo_la_prima["G1"]["current_elo"]
        assert len(dopo_la_seconda["G1"]["tournaments_played"]) == 2
        assert not any("storico" in a for a in avvisi)

    def test_una_voce_senza_identificativo_si_riconosce_dal_nome(self, banco):
        """La console, fino alla 10.8.7, scriveva nello storico
        l'identificativo vuoto dei tornei che non lo avevano. Con la sola
        ricerca per identificativo quella voce non si trovava, e una seconda
        finalizzazione sommava di nuovo Elo, partite, voce e medaglia."""
        dati = _leggi(banco.db)
        for giocatore in dati["players"]:
            giocatore["tournaments_played"] = [
                {
                    "tournament_name": NOME,
                    "tournament_id": "",
                    "rank": 1,
                    "total_players": 4,
                    "date_started": INIZIO,
                    "date_completed": INIZIO,
                }
            ]
        _scrivi(banco.db, dati)
        banco.torneo["tournament_id"] = ""
        _scrivi(banco.file_torneo, banco.torneo)
        prima = _leggi_byte(banco.db)
        avvisi = []

        assert _finalizza(banco, avvisi) is True

        assert _leggi_byte(banco.db) == prima
        assert any("NomeG1 CognomeG1" in a and ": 4." in a for a in avvisi)

    def test_l_archivio_tiene_i_valori_che_il_database_ha_ricevuto(
        self, banco, tmp_path
    ):
        """Con 29 partite la prima finalizzazione usa K 40 e porta i
        giocatori a 30; una seconda, sul torneo rimesso nella radice, ricalcola
        con K 20. Il database resta com'e', e il json in archivio deve restare
        quello della prima: i valori ricalcolati non li ha ricevuti nessuno.
        I file della seconda vanno nella cartella backup, non nella radice."""
        dati = _leggi(banco.db)
        for giocatore in dati["players"]:
            giocatore["games_played"] = 29
        _scrivi(banco.db, dati)
        assert _finalizza(banco) is True
        archiviato = _leggi_byte(_json_in_archivio())
        k_della_prima = {p["id"]: p["k_factor"] for p in _leggi(_json_in_archivio())["players"]}
        assert k_della_prima["G1"] == 40
        database_dopo_la_prima = _leggi_byte(banco.db)

        _scrivi(banco.file_torneo, banco.torneo)
        avvisi = []
        assert _finalizza(banco, avvisi) is True

        assert _leggi_byte(_json_in_archivio()) == archiviato
        assert _leggi_byte(banco.db) == database_dopo_la_prima
        assert _nella_radice(tmp_path) == []
        messi_da_parte = _copie(banco.backup, "rifinalizzazione")
        json_messi_da_parte = [c for c in messi_da_parte if c.endswith(".json")]
        assert len(json_messi_da_parte) == 1
        ricalcolato = {p["id"]: p for p in _leggi(json_messi_da_parte[0])["players"]}
        assert ricalcolato["G1"]["k_factor"] == 20
        assert any(c.endswith(".txt") for c in messi_da_parte)
        assert _copie(banco.backup, "pre_archiviazione") == []
        assert any("già finalizzato e archiviato" in a for a in avvisi)

    def test_un_giocatore_solo_senza_lo_storico_e_al_singolare(self, banco):
        """La finalizzazione ripetuta, con un K ricalcolato, trova un solo
        giocatore senza il torneo nello storico: lo aggiorna, e l'avviso lo
        dice al singolare. Fino alla 10.13.5 si leggeva per 1 giocatori, che
        non avevano il torneo nello storico."""
        dati = _leggi(banco.db)
        for giocatore in dati["players"]:
            giocatore["games_played"] = 29
        _scrivi(banco.db, dati)
        assert _finalizza(banco) is True
        dati = _leggi(banco.db)
        dati["players"][0]["tournaments_played"] = []
        _scrivi(banco.db, dati)

        _scrivi(banco.file_torneo, banco.torneo)
        avvisi = []
        assert _finalizza(banco, avvisi) is True

        assert (
            "Il database ha però ricevuto questa finalizzazione per un giocatore, che non aveva il torneo nello storico: per lui l'archivio non coincide con il database."
            in avvisi
        )
        assert not any("per 1 giocatori" in a for a in avvisi)


class TestArchiviazione:
    """Il file del torneo concluso va in archivio, e quello attivo si toglie
    solo dopo aver riletto la copia. Fino alla 10.8.8 un file gia' presente
    in archivio restava com'era, e il json attivo veniva cancellato lo
    stesso (issue 39)."""

    def _prepara_archivio(self, banco, **segni):
        """In archivio, dove andra' il torneo, un json della stessa edizione
        con un contenuto diverso: i segni passati come argomenti."""
        cartella = _cartella_archivio()
        os.makedirs(cartella, exist_ok=True)
        gia_presente = _json_in_archivio(cartella)
        _scrivi(gia_presente, dict(banco.torneo, **segni))
        return gia_presente

    def test_il_file_che_c_era_passa_da_una_copia_e_poi_si_sostituisce(self, banco):
        gia_presente = self._prepara_archivio(banco, vecchio=True)
        avvisi = []

        assert _finalizza(banco, avvisi) is True

        archiviato = _leggi(gia_presente)
        assert archiviato["name"] == NOME
        assert archiviato["concluded"] is True
        assert "vecchio" not in archiviato
        assert not os.path.exists(banco.file_torneo)
        copie = _copie(banco.backup, "pre_archiviazione")
        assert len(copie) == 1
        assert _leggi(copie[0])["vecchio"] is True
        assert any("copia di sicurezza" in a for a in avvisi)

    def test_senza_la_copia_di_sicurezza_non_si_sostituisce_niente(
        self, banco, monkeypatch
    ):
        """E la finalizzazione risponde di no: il torneo e' concluso e il
        database aggiornato, ma l'archivio non ha il json. Fino alla 10.8.8
        la finestra lo annunciava archiviato."""
        import ui

        vera = ui.create_backup

        def create_backup_finta(percorso, contesto="backup"):
            if contesto == "pre_archiviazione":
                return False
            return vera(percorso, contesto)

        monkeypatch.setattr(ui, "create_backup", create_backup_finta)
        gia_presente = self._prepara_archivio(banco, vecchio=True)
        avvisi = []

        assert _finalizza(banco, avvisi) is False

        assert _leggi(gia_presente)["vecchio"] is True
        assert os.path.exists(banco.file_torneo)
        assert _leggi(banco.file_torneo)["concluded"] is True
        assert any("non è stato sostituito" in a for a in avvisi)
        assert any(
            banco.file_torneo in a and _cartella_archivio() in a for a in avvisi
        )

    def test_se_la_copia_riletta_non_torna_il_torneo_resta(self, banco, monkeypatch):
        import shutil

        import ui

        def copia_guasta(origine, destinazione):
            with open(origine, "rb") as f:
                dati = f.read()
            with open(destinazione, "wb") as f:
                f.write(dati[: len(dati) // 2])

        monkeypatch.setattr(
            ui, "shutil", types.SimpleNamespace(copy2=copia_guasta, move=shutil.move)
        )
        avvisi = []

        assert _finalizza(banco, avvisi) is False

        assert os.path.exists(banco.file_torneo)
        assert _leggi(banco.file_torneo)["concluded"] is True
        assert any("riletta" in a for a in avvisi)
        assert any(banco.file_torneo in a for a in avvisi)

    def test_i_report_gia_presenti_passano_da_una_copia_e_si_sostituiscono(
        self, banco, tmp_path
    ):
        """Fino alla 10.8.8 un report gia' presente in archivio non si
        sostituiva, e quello nuovo restava per sempre nella radice."""
        cartella = _cartella_archivio()
        self._prepara_archivio(banco, vecchio=True)
        classifica = f"Tornello - {NOME} - Classifica.txt"
        with open(os.path.join(cartella, classifica), "w", encoding="utf-8") as f:
            f.write("classifica vecchia")

        assert _finalizza(banco) is True

        with open(os.path.join(cartella, classifica), encoding="utf-8-sig") as f:
            assert "classifica vecchia" not in f.read()
        assert _nella_radice(tmp_path) == []
        copie = [os.path.basename(c) for c in _copie(banco.backup, "pre_archiviazione")]
        assert sum(c.endswith(".txt") for c in copie) == 1
        assert sum(c.endswith(".json") for c in copie) == 1

    def test_un_altra_edizione_nello_stesso_mese_ha_la_sua_cartella(
        self, banco, tmp_path
    ):
        """Due edizioni con lo stesso nome concluse nello stesso mese: il json
        della seconda prendeva il posto di quello della prima, che spariva dai
        tornei conclusi."""
        assert _finalizza(banco) is True
        prima_edizione = _leggi_byte(_json_in_archivio())

        seconda = "2026-07-15"
        banco.torneo["start_date"] = banco.torneo["end_date"] = seconda
        _scrivi(banco.file_torneo, banco.torneo)
        avvisi = []
        assert _finalizza(banco, avvisi) is True

        assert _leggi_byte(_json_in_archivio()) == prima_edizione
        cartella_seconda = f"{_cartella_archivio()}_{seconda}"
        assert _leggi(_json_in_archivio(cartella_seconda))["start_date"] == seconda
        assert os.path.exists(
            os.path.join(cartella_seconda, f"Tornello - {NOME} - Classifica.txt")
        )
        assert _nella_radice(tmp_path) == []
        assert _copie(banco.backup, "pre_archiviazione") == []
        assert len(_giocatori_del_db(banco.db)["G1"]["tournaments_played"]) == 2
        assert any(cartella_seconda in a for a in avvisi)

    def test_con_la_copia_giusta_il_torneo_attivo_se_ne_va(self, banco):
        avvisi = []

        assert _finalizza(banco, avvisi) is True

        archiviato = os.path.join(_cartella_archivio(), f"Tornello - {NOME}.json")
        assert _leggi(archiviato)["concluded"] is True
        assert not os.path.exists(banco.file_torneo)
        assert _copie(banco.backup, "pre_archiviazione") == []
        assert avvisi == []

    def test_il_file_aperto_dall_archivio_non_sparisce(self, banco, tmp_path):
        """Il file aperto e' gia' quello dell'archivio: la conclusione si
        scrive li', e il file resta, perche' e' lui la copia da tenere."""
        cartella = _cartella_archivio()
        os.makedirs(cartella)
        aperto = _json_in_archivio(cartella)
        _scrivi(aperto, banco.torneo)
        os.remove(banco.file_torneo)
        banco.file_torneo = aperto

        assert _finalizza(banco) is True

        assert _leggi(aperto)["concluded"] is True
        assert [n for n in _nella_radice(tmp_path) if n.endswith(".json")] == []


class TestCartellaDiLavoroEsterna:
    """La cartella di lavoro scelta dall'arbitro, fuori da quella del
    programma, come quella in Dropbox di Autunneo2: i report restano li' e
    ricevono anche una copia del torneo concluso."""

    def _esterna(self, banco, tmp_path):
        esterna = tmp_path / "esterna"
        esterna.mkdir()
        banco.torneo["custom_save_path"] = str(esterna)
        return esterna

    def test_il_json_della_cartella_esterna_passa_da_una_copia_sola(
        self, banco, tmp_path
    ):
        """Il json nella radice e un json diverso gia' nella cartella esterna.
        Fino alla 10.8.8 il glob dei report prendeva anche quel json, e ne
        nascevano due copie pre_archiviazione e un avviso su un file che in
        archivio non c'era."""
        esterna = self._esterna(banco, tmp_path)
        _scrivi(banco.file_torneo, banco.torneo)
        nella_esterna = esterna / f"Tornello - {NOME}.json"
        nella_esterna.write_text('{"altro": 1}', encoding="utf-8")
        avvisi = []

        assert _finalizza(banco, avvisi) is True

        archiviato = _leggi_byte(_json_in_archivio())
        assert _leggi(_json_in_archivio())["concluded"] is True
        assert _leggi_byte(str(nella_esterna)) == archiviato
        assert not os.path.exists(banco.file_torneo)
        copie = _copie(banco.backup, "pre_archiviazione")
        assert len(copie) == 1
        assert _leggi(copie[0]) == {"altro": 1}
        assert len(avvisi) == 1
        assert str(esterna) in avvisi[0]
        classifica = f"Tornello - {NOME} - Classifica.txt"
        assert (esterna / classifica).exists()
        assert os.path.exists(os.path.join(_cartella_archivio(), classifica))

    def test_un_torneo_aperto_dalla_cartella_esterna_si_conclude_li(
        self, banco, tmp_path
    ):
        """Il torneo aperto con Apri torneo dalla cartella esterna. Fino alla
        10.8.8 la conclusione si salvava nella radice: in archivio andava il
        file aperto, ancora da concludere, e nella radice nasceva un json
        concluso che l'albero non mostrava."""
        esterna = self._esterna(banco, tmp_path)
        os.remove(banco.file_torneo)
        aperto = str(esterna / f"Tornello - {NOME}.json")
        _scrivi(aperto, banco.torneo)
        banco.file_torneo = aperto

        assert _finalizza(banco) is True

        archiviato = _leggi(_json_in_archivio())
        assert archiviato["concluded"] is True
        assert all(p["final_rank"] is not None for p in archiviato["players"])
        assert _leggi_byte(aperto) == _leggi_byte(_json_in_archivio())
        assert [n for n in _nella_radice(tmp_path) if n.endswith(".json")] == []


class TestScrittureNonRiuscite:
    """save_players_db e save_tournament stampavano l'errore e basta, e la
    finalizzazione andava avanti: il json attivo spariva e la finestra diceva
    i giocatori aggiornati. Dalla 10.8.9 ci si ferma, e tutto resta com'era
    prima della finalizzazione."""

    def _guasta(self, monkeypatch, modulo):
        def scrittura_bloccata(*argomenti, **opzioni):
            raise PermissionError("file tenuto bloccato da un altro programma")

        monkeypatch.setattr(modulo, "scrivi_json_atomico", scrittura_bloccata)

    def test_se_il_database_non_si_salva_il_torneo_torna_da_concludere(
        self, banco, monkeypatch
    ):
        import db_players
        from db_players import load_players_db
        from ui import finalize_tournament

        database_prima = _leggi_byte(banco.db)
        giocatori = load_players_db()
        schede_prima = copy.deepcopy(giocatori)
        torneo = copy.deepcopy(banco.torneo)
        self._guasta(monkeypatch, db_players)
        avvisi = []

        esito = finalize_tournament(torneo, giocatori, banco.file_torneo, avvisi)

        assert esito is False
        assert _leggi_byte(banco.db) == database_prima
        assert giocatori == schede_prima
        assert torneo["concluded"] is False
        assert _leggi(banco.file_torneo)["concluded"] is False
        assert not os.path.exists(_json_in_archivio())
        assert any("database dei giocatori non si è potuto salvare" in a for a in avvisi)

    def test_se_il_torneo_non_si_salva_ci_si_ferma_prima_del_database(
        self, banco, monkeypatch
    ):
        import tournament
        from db_players import load_players_db
        from ui import finalize_tournament

        database_prima = _leggi_byte(banco.db)
        torneo_prima = _leggi_byte(banco.file_torneo)
        torneo = copy.deepcopy(banco.torneo)
        self._guasta(monkeypatch, tournament)
        avvisi = []

        esito = finalize_tournament(torneo, load_players_db(), banco.file_torneo, avvisi)

        assert esito is False
        assert _leggi_byte(banco.db) == database_prima
        assert _leggi_byte(banco.file_torneo) == torneo_prima
        assert torneo["concluded"] is False
        assert not os.path.exists(_json_in_archivio())
        assert any(banco.file_torneo in a for a in avvisi)


class TestMessaggioFinale:
    """Il testo che chiude la finalizzazione nella finestra. Con degli
    avvisi il messaggio di successo, che diceva i giocatori aggiornati anche
    quando nessuno lo era, lascia il posto alla finestra degli avvisi."""

    def test_senza_avvisi_basta_il_successo(self):
        from gui.main_frame import MainFrame

        assert MainFrame._esito_della_finalizzazione(True, []) is None

    def test_riuscita_con_avvisi(self):
        from gui.main_frame import MainFrame

        titolo, testo = MainFrame._esito_della_finalizzazione(True, ["primo", "secondo"])

        assert titolo == "Avvisi della finalizzazione"
        righe = testo.split("\n")
        assert righe[0].startswith("Il torneo è concluso e archiviato")
        assert righe[1:] == ["primo", "secondo"]

    def test_non_riuscita(self):
        from gui.main_frame import MainFrame

        _titolo, testo = MainFrame._esito_della_finalizzazione(False, ["motivo"])

        assert testo.startswith("La finalizzazione non è andata fino in fondo")
        assert testo.endswith("motivo")


class TestFinalizzazioneInConsole:
    """La console calcolava e scriveva Elo e partite per conto suo, poi
    chiamava la finalizzazione comune, che li scriveva di nuovo: ogni
    giocatore riceveva la variazione due volte, e la seconda copia
    pre_finalize_db nasceva con gli Elo gia' cambiati. Dalla 10.8.10 il
    database lo tocca solo la finalizzazione comune, una volta."""

    def test_elo_applicato_una_volta_e_copia_del_database_pulita(self, banco):
        with open(banco.db, "rb") as f:
            database_prima = f.read()

        assert _finalizza_in_console(banco) is True

        archiviato = _leggi(
            os.path.join(_cartella_archivio(), f"Tornello - {NOME}.json")
        )
        variazioni = {p["id"]: p for p in archiviato["players"]}
        dopo = _giocatori_del_db(banco.db)
        for pid, elo in ELO_INIZIALI.items():
            attesa = elo + variazioni[pid]["elo_change"]
            assert dopo[pid]["current_elo"] == pytest.approx(attesa), pid
            assert dopo[pid]["games_played"] == 11, pid

        copie_db = _copie(banco.backup, "pre_finalize_db")
        assert len(copie_db) == 1
        with open(copie_db[0], "rb") as f:
            assert f.read() == database_prima
        assert len(_copie(banco.backup, "pre_finalize_torneo")) == 1


# Gli Elo delle cadenze nel database della prova. G4 non ne ha nessuno: nei
# rapid e nei blitz parte dal suo current_elo, come nel calcolo dell'Elo di
# partenza.
ELO_RAPID = {"G1": 1700, "G2": 1650, "G3": 1600, "G4": 0}
ELO_BLITZ = {"G1": 1750, "G2": 1600, "G3": 1580, "G4": 0}
CADENZE = {
    "standard": {"minutes": 90, "increment": 30, "pgn_value": "5400+30"},
    "rapid": {"minutes": 15, "increment": 10, "pgn_value": "900+10"},
    "blitz": {"minutes": 3, "increment": 2, "pgn_value": "180+2"},
}


def _con_la_cadenza(banco, categoria):
    """Il database con gli Elo rapid e blitz, e il torneo della cadenza
    scelta, con l'Elo di partenza che gli darebbe l'iscrizione. Restituisce
    le schede del database come sono prima della finalizzazione."""
    from stats import get_initial_elo_for_tournament

    dati = _leggi(banco.db)
    for giocatore in dati["players"]:
        giocatore["elo_rapid"] = ELO_RAPID[giocatore["id"]]
        giocatore["elo_blitz"] = ELO_BLITZ[giocatore["id"]]
    _scrivi(banco.db, dati)
    schede = {g["id"]: g for g in dati["players"]}
    banco.torneo["tournament_category"] = categoria
    banco.torneo["time_control"] = CADENZE[categoria]
    for giocatore in banco.torneo["players"]:
        giocatore["initial_elo"] = get_initial_elo_for_tournament(
            schede[giocatore["id"]], categoria
        )
    _scrivi(banco.file_torneo, banco.torneo)
    return copy.deepcopy(schede)


def _variazioni_archiviate():
    return {p["id"]: p["elo_change"] for p in _leggi(_json_in_archivio())["players"]}


def _g3_vince_a_forfait(torneo):
    """G3 e G4 non giocano, e G3 vince a forfait: nessuno dei due ha una
    partita valida per l'Elo, e la loro variazione e' zero. G1 e G2 giocano
    come prima."""
    for giocatore in torneo["players"]:
        if giocatore["id"] == "G3":
            giocatore["results_history"] = [_voce(1, "G4", "white", "1-F", 1.0)]
            giocatore["points"] = 1.0
        elif giocatore["id"] == "G4":
            giocatore["results_history"] = [_voce(1, "G3", "black", "1-F", 0.0)]
            giocatore["points"] = 0.0
    for partita in torneo["rounds"][0]["matches"]:
        if partita["white_player_id"] == "G3":
            partita["result"] = "1-F"
    return torneo


class TestEloDellaCadenza:
    """Dalla 10.13.4 la variazione Elo dei tornei rapid e blitz va sull'Elo
    della cadenza, lo stesso da cui viene l'Elo di partenza, e non piu' su
    current_elo; negli standard resta su current_elo. Decisione di Gabriele
    come arbitro: la 10.8.10 aveva lasciato current_elo in via provvisoria."""

    @pytest.mark.parametrize(
        ("categoria", "campo", "altro"),
        [("rapid", "elo_rapid", "elo_blitz"), ("blitz", "elo_blitz", "elo_rapid")],
    )
    def test_cambia_solo_l_elo_della_cadenza(self, banco, categoria, campo, altro):
        prima = _con_la_cadenza(banco, categoria)

        assert _finalizza(banco) is True

        variazioni = _variazioni_archiviate()
        dopo = _giocatori_del_db(banco.db)
        # La prova ha senso solo con variazioni vere, anche per G4.
        assert variazioni["G1"] > 0 and variazioni["G4"] != 0
        for pid in ELO_INIZIALI:
            base = prima[pid][campo] or prima[pid]["current_elo"]
            assert dopo[pid][campo] == base + variazioni[pid], pid
            assert dopo[pid]["current_elo"] == prima[pid]["current_elo"], pid
            assert dopo[pid][altro] == prima[pid][altro], pid
            assert dopo[pid]["games_played"] == 11, pid
        # G4 non aveva l'Elo della cadenza: nasce dal suo current_elo, da
        # cui e' partito nel torneo, piu' la variazione.
        assert dopo["G4"][campo] == ELO_INIZIALI["G4"] + variazioni["G4"]
        # La voce dello storico dice il campo, il valore di prima e quello
        # scritto, per lo storno della riapertura.
        for pid in ELO_INIZIALI:
            voce = dopo[pid]["tournaments_played"][-1]
            assert voce["elo_field"] == campo, pid
            assert voce["elo_before"] == prima[pid][campo], pid
            assert voce["elo_after"] == dopo[pid][campo], pid

    def test_negli_standard_resta_current_elo(self, banco):
        prima = _con_la_cadenza(banco, "standard")

        assert _finalizza(banco) is True

        variazioni = _variazioni_archiviate()
        dopo = _giocatori_del_db(banco.db)
        assert variazioni["G1"] > 0
        for pid in ELO_INIZIALI:
            attesa = prima[pid]["current_elo"] + variazioni[pid]
            assert dopo[pid]["current_elo"] == attesa, pid
            assert dopo[pid]["elo_rapid"] == prima[pid]["elo_rapid"], pid
            assert dopo[pid]["elo_blitz"] == prima[pid]["elo_blitz"], pid
            voce = dopo[pid]["tournaments_played"][-1]
            assert (voce["elo_field"], voce["elo_before"], voce["elo_after"]) == (
                "current_elo",
                prima[pid]["current_elo"],
                attesa,
            ), pid

    def test_un_ritirato_non_ha_l_elo_nella_voce(self, banco):
        """Un ritirato non ha variazione, e la sua voce dello storico non ha
        i campi dell'Elo: lo storno non ne tocca nessuno."""
        _con_la_cadenza(banco, "rapid")
        banco.torneo["players"][3]["withdrawn"] = True
        _scrivi(banco.file_torneo, banco.torneo)

        assert _finalizza(banco) is True

        voce = _giocatori_del_db(banco.db)["G4"]["tournaments_played"][-1]
        assert not {"elo_field", "elo_before", "elo_after"} & voce.keys()
        assert _giocatori_del_db(banco.db)["G4"]["elo_rapid"] == 0

    @pytest.mark.parametrize("categoria", ["rapid", "blitz", "standard"])
    def test_la_console_fa_come_la_finestra(self, banco, categoria):
        """Lo stesso torneo finalizzato dalla finestra e, rimesso tutto
        com'era, dalla console: il database deve venire uguale."""
        import shutil

        prima = _con_la_cadenza(banco, categoria)
        database_prima = _leggi_byte(banco.db)
        assert _finalizza(banco) is True
        dalla_finestra = _giocatori_del_db(banco.db)

        with open(banco.db, "wb") as f:
            f.write(database_prima)
        _scrivi(banco.file_torneo, banco.torneo)
        shutil.rmtree(_cartella_archivio())
        assert _finalizza_in_console(banco) is True

        assert _giocatori_del_db(banco.db) == dalla_finestra
        campo = {"rapid": "elo_rapid", "blitz": "elo_blitz"}.get(categoria, "current_elo")
        assert dalla_finestra["G1"][campo] > prima["G1"][campo]

    def test_una_seconda_finalizzazione_non_raddoppia_l_elo_rapid(self, banco):
        """La guardia della 10.8.8 vale anche per l'Elo della cadenza."""
        _con_la_cadenza(banco, "rapid")
        assert _finalizza(banco) is True
        dopo_la_prima = _leggi_byte(banco.db)

        _scrivi(banco.file_torneo, banco.torneo)
        assert _finalizza(banco, []) is True

        assert _leggi_byte(banco.db) == dopo_la_prima


class TestEloDellaCadenzaSenzaPartiteValide:
    """Dalla 10.13.7, decisione di Gabriele come arbitro: nei rapid e nei
    blitz l'Elo della cadenza nasce solo con almeno una partita valida per
    l'Elo. Chi non lo ha, e nel torneo ha solo forfait, bye o nessuna
    partita, resta senza, e la sua voce dello storico non registra
    variazione. Nella 10.13.4 gli nasceva uguale all'Elo di partenza. Chi lo
    ha gia' lo tiene com'e', con la variazione zero."""

    @pytest.mark.parametrize(
        ("categoria", "campo"), [("rapid", "elo_rapid"), ("blitz", "elo_blitz")]
    )
    def test_a_soli_forfait_l_elo_della_cadenza_non_nasce(self, banco, categoria, campo):
        _g3_vince_a_forfait(banco.torneo)
        prima = _con_la_cadenza(banco, categoria)
        # Nel database di prova G4 ha l'Elo della cadenza a zero, G3 no.
        assert prima["G4"][campo] == 0 and prima["G3"][campo] > 0

        assert _finalizza(banco) is True

        variazioni = _variazioni_archiviate()
        dopo = _giocatori_del_db(banco.db)
        assert variazioni["G3"] == variazioni["G4"] == 0
        assert dopo["G4"][campo] == 0
        assert dopo["G4"]["current_elo"] == prima["G4"]["current_elo"]
        voce = dopo["G4"]["tournaments_played"][-1]
        assert not {"elo_field", "elo_before", "elo_after"} & voce.keys()
        # La voce dello storico c'e', senza i campi dell'Elo.
        assert voce["tournament_id"] == "COPPA_PROVA"
        # G3 aveva l'Elo della cadenza, e lo tiene uguale.
        assert dopo["G3"][campo] == prima["G3"][campo]
        voce = dopo["G3"]["tournaments_played"][-1]
        assert (voce["elo_field"], voce["elo_before"], voce["elo_after"]) == (campo, prima["G3"][campo], prima["G3"][campo])
        # G1 e G2 hanno giocato: la variazione va sull'Elo della cadenza.
        for pid in ("G1", "G2"):
            assert dopo[pid][campo] == prima[pid][campo] + variazioni[pid], pid

    def test_con_l_elo_della_cadenza_mancante_il_campo_non_nasce(self, banco):
        """Una scheda senza il campo, in memoria, resta senza: il database
        di prova passa da load_players_db, che lo metterebbe a zero, e
        questa prova gli toglie il campo dopo."""
        from db_players import load_players_db
        from ui import finalize_tournament

        _g3_vince_a_forfait(banco.torneo)
        _con_la_cadenza(banco, "rapid")
        giocatori = load_players_db()
        del giocatori["G4"]["elo_rapid"]

        assert finalize_tournament(copy.deepcopy(banco.torneo), giocatori, banco.file_torneo, []) is True

        dopo = _giocatori_del_db(banco.db)
        assert "elo_rapid" not in dopo["G4"]
        assert "elo_field" not in dopo["G4"]["tournaments_played"][-1]

    def test_con_l_elo_rapid_gia_presente_resta_invariato(self, banco):
        """Lo stesso G4, a soli forfait, con l'Elo rapid che ha gia': resta
        quello, e la voce dello storico lo dice prima e dopo."""
        _g3_vince_a_forfait(banco.torneo)
        _con_la_cadenza(banco, "rapid")
        dati = _leggi(banco.db)
        for giocatore in dati["players"]:
            if giocatore["id"] == "G4":
                giocatore["elo_rapid"] = 1450
        _scrivi(banco.db, dati)

        assert _finalizza(banco) is True

        g4 = _giocatori_del_db(banco.db)["G4"]
        assert g4["elo_rapid"] == 1450
        assert g4["current_elo"] == ELO_INIZIALI["G4"]
        voce = g4["tournaments_played"][-1]
        assert (voce["elo_field"], voce["elo_before"], voce["elo_after"]) == ("elo_rapid", 1450, 1450)

    def test_con_una_partita_valida_l_elo_della_cadenza_nasce(self, banco):
        """G4 senza Elo rapid che gioca, come nella 10.13.4: l'Elo rapid
        nasce dall'Elo di partenza piu' la variazione."""
        _con_la_cadenza(banco, "rapid")

        assert _finalizza(banco) is True

        g4 = _giocatori_del_db(banco.db)["G4"]
        assert g4["elo_rapid"] == ELO_INIZIALI["G4"] + _variazioni_archiviate()["G4"]
        assert g4["tournaments_played"][-1]["elo_field"] == "elo_rapid"

    def test_la_console_fa_come_la_finestra(self, banco):
        """Il torneo con i forfait, finalizzato dalla finestra e, rimesso
        tutto com'era, dalla console: il database deve venire uguale."""
        import shutil

        _g3_vince_a_forfait(banco.torneo)
        _con_la_cadenza(banco, "rapid")
        database_prima = _leggi_byte(banco.db)
        assert _finalizza(banco) is True
        dalla_finestra = _giocatori_del_db(banco.db)

        with open(banco.db, "wb") as f:
            f.write(database_prima)
        _scrivi(banco.file_torneo, banco.torneo)
        shutil.rmtree(_cartella_archivio())
        assert _finalizza_in_console(banco) is True

        assert _giocatori_del_db(banco.db) == dalla_finestra
        assert dalla_finestra["G4"]["elo_rapid"] == 0


def _togli_dal_database(banco, *identificativi):
    dati = _leggi(banco.db)
    dati["players"] = [g for g in dati["players"] if g["id"] not in identificativi]
    _scrivi(banco.db, dati)


class TestIscrittiCheIlDatabaseNonHa:
    """Dalla 10.13.16 la finalizzazione crea nel database dei giocatori chi
    non c'e', con i dati che il torneo ha gia', gli applica tutto come agli
    altri e lo scrive negli avvisi (decisione di Gabriele). Fino alla 10.13.15
    lo saltava in silenzio: niente Elo, storico e medaglia, come e' successo
    a due iscritti di Autunneo2 venuti dalla ricerca FIDE."""

    def test_nascono_e_ricevono_tutto_come_gli_altri(self, banco):
        _togli_dal_database(banco, "G3", "G4")
        avvisi = []

        assert _finalizza(banco, avvisi) is True

        database = _giocatori_del_db(banco.db)
        archiviati = {p["id"]: p for p in _leggi(_json_in_archivio())["players"]}
        medaglie = {1: "gold", 2: "silver", 3: "bronze", 4: "wood"}
        for pid in ("G3", "G4"):
            scheda = database[pid]
            giocatore = archiviati[pid]
            assert (scheda["first_name"], scheda["last_name"]) == ("Nome" + pid, "Cognome" + pid)
            assert scheda["current_elo"] == pytest.approx(ELO_INIZIALI[pid] + giocatore["elo_change"])
            assert giocatore["elo_change"] != 0
            assert scheda["games_played"] == 1
            voce = scheda["tournaments_played"][-1]
            assert voce["created_by_finalization"] is True
            assert voce["rank"] == giocatore["final_rank"]
            assert voce["elo_field"] == "current_elo"
            assert scheda["medals"][medaglie[giocatore["final_rank"]]] == 1
        assert "created_by_finalization" not in database["G1"]["tournaments_played"][-1]
        # I nomi nell'ordine della classifica finale.
        nomi = ", ".join(f"Nome{pid} Cognome{pid}" for pid in archiviati if pid in ("G3", "G4"))
        assert avvisi == [
            f"2 giocatori non erano nel database dei giocatori: {nomi}. La finalizzazione li ha creati con i dati che avevano nel torneo, e ha dato loro Elo, partite giocate, storico e medaglie come agli altri."
        ]

    def test_uno_solo_e_al_singolare_anche_in_console(self, banco, capsys):
        """La console scrive gli avvisi sullo schermo, con print."""
        _togli_dal_database(banco, "G2")
        capsys.readouterr()

        assert _finalizza_in_console(banco) is True

        uscita = capsys.readouterr().out
        assert (
            "Un giocatore non era nel database dei giocatori: NomeG2 CognomeG2. La finalizzazione lo ha creato con i dati che aveva nel torneo, e gli ha dato Elo, partite giocate, storico e medaglia come agli altri."
            in uscita
        )
        assert "giocatori non erano nel database" not in uscita
        database = _giocatori_del_db(banco.db)
        assert database["G2"]["tournaments_played"][-1]["created_by_finalization"] is True
        assert database["G2"]["games_played"] == 1

    def test_l_avviso_al_singolare(self, banco):
        _togli_dal_database(banco, "G2")
        avvisi = []

        assert _finalizza(banco, avvisi) is True

        assert avvisi == [
            "Un giocatore non era nel database dei giocatori: NomeG2 CognomeG2. La finalizzazione lo ha creato con i dati che aveva nel torneo, e gli ha dato Elo, partite giocate, storico e medaglia come agli altri."
        ]

    def test_se_il_database_non_si_salva_non_restano_in_memoria(self, banco, monkeypatch):
        """La console tiene il database aperto: una scheda creata e rimasta
        in memoria farebbe passare il giocatore per registrato alla
        finalizzazione successiva."""
        import ui
        from db_players import load_players_db

        _togli_dal_database(banco, "G3")
        giocatori = load_players_db()
        monkeypatch.setattr(ui, "save_players_db", lambda giocatori: False)

        esito = ui.finalize_tournament(copy.deepcopy(banco.torneo), giocatori, banco.file_torneo, [])

        assert esito is False
        assert "G3" not in giocatori
        assert giocatori["G1"]["tournaments_played"] == []


class TestColonnaEloVarDellaClassificaInCorso:
    """Dalla 10.13.17 la colonna Elo Var. della classifica in corso e' la
    variazione che la finalizzazione applichera': il fattore K viene dalla
    scheda del database, o da quella che la finalizzazione creera' per chi
    manca. Fino alla 10.13.16 veniva dal giocatore del torneo, che non ha
    experienced, partite giocate e data di nascita: 40 dove la
    finalizzazione dava 20, e la colonna diceva il doppio."""

    def test_la_colonna_e_quella_che_la_finalizzazione_applica(self, banco):
        from reports import get_standings_text

        dati = _leggi(banco.db)
        for scheda in dati["players"]:
            if scheda["id"] == "G1":
                scheda["experienced"] = True
                scheda["games_played"] = 80
            elif scheda["id"] == "G4":
                scheda["fide_k_factor"] = 10
        dati["players"] = [g for g in dati["players"] if g["id"] != "G3"]
        _scrivi(banco.db, dati)
        in_corso = copy.deepcopy(banco.torneo)

        testo = get_standings_text(in_corso)

        colonna = {p["id"]: (p["k_factor"], p["elo_change"]) for p in in_corso["players"]}
        assert colonna["G1"][0] == 20
        assert colonna["G4"][0] == 10
        assert f"{colonna['G1'][1]:+4d}" in next(r for r in testo.splitlines() if "CognomeG1, NomeG1" in r)
        assert _finalizza(banco) is True
        archiviati = {p["id"]: (p["k_factor"], p["elo_change"]) for p in _leggi(_json_in_archivio())["players"]}
        assert colonna == archiviati

    def test_il_k_salvato_nel_torneo_non_conta_piu(self, banco):
        """Il K del giocatore del torneo restava salvato nel file, e la
        classifica non lo ricalcolava piu': in Autunneo2 vale 40 per tutti."""
        from reports import get_standings_text

        dati = _leggi(banco.db)
        for scheda in dati["players"]:
            scheda["experienced"] = True
        _scrivi(banco.db, dati)
        in_corso = copy.deepcopy(banco.torneo)
        for giocatore in in_corso["players"]:
            giocatore["k_factor"] = 40

        get_standings_text(in_corso)

        assert {p["k_factor"] for p in in_corso["players"]} == {20}


def _con_altri_soci(banco, numero=30):
    """Il database del banco con numero schede in piu', di soci che il
    torneo non ha: un database illeggibile li farebbe sparire."""
    dati = _leggi(banco.db)
    dati["players"] += [
        {
            "id": f"SOCIO{i:02d}",
            "first_name": f"Nome{i}",
            "last_name": "Socio",
            "current_elo": 1500.0,
            "games_played": 40,
            "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
            "tournaments_played": [{"tournament_name": "Vecchio", "rank": 3}],
        }
        for i in range(numero)
    ]
    _scrivi(banco.db, dati)


class TestDatabaseCheNonSiLegge:
    """Dalla 10.13.16 la finalizzazione crea nel database chi non trova: con
    un database che c'e' ma non si legge, letto vuoto, avrebbe creato tutti
    gli iscritti e scritto un database con loro soli, e gli altri soci, con
    storici, medaglie ed Elo, sarebbero spariti. Adesso il database non letto
    arriva come DatabaseNonLetto, la finalizzazione non parte e niente
    cambia; la console lo rilegge prima di rinunciare."""

    def _niente_e_cambiato(self, banco, database_prima, torneo_prima, esito, torneo):
        assert esito is False
        assert _leggi_byte(banco.db) == database_prima
        assert _leggi_byte(banco.file_torneo) == torneo_prima
        assert torneo.get("concluded") is False
        assert not os.path.exists(_json_in_archivio())
        assert _copie(banco.backup, "pre_finalize_db") == []

    def test_con_la_lettura_bloccata_non_parte(self, banco, monkeypatch):
        from db_players import load_players_db
        from test_db import lettura_bloccata
        from ui import finalize_tournament

        _con_altri_soci(banco)
        database_prima = _leggi_byte(banco.db)
        torneo_prima = _leggi_byte(banco.file_torneo)
        lettura_bloccata(monkeypatch, banco.db)
        torneo = copy.deepcopy(banco.torneo)
        avvisi = []

        esito = finalize_tournament(torneo, load_players_db(), banco.file_torneo, avvisi)

        self._niente_e_cambiato(banco, database_prima, torneo_prima, esito, torneo)
        assert len(avvisi) == 2
        assert avvisi[0].startswith("Il database dei giocatori, Tornello - Players_db.json, c'è ma non si è potuto leggere: ")
        assert avvisi[0].endswith(
            "Per non perdere i giocatori che contiene, Tornello non lo modifica. Se un altro programma lo tiene bloccato, per esempio Dropbox o l'antivirus, riprova più tardi; se il file è rovinato, ripristinalo dalla finestra Copie di sicurezza del menu File."
        )
        assert avvisi[1] == (
            "La finalizzazione non parte: il torneo resta da concludere, e il database dei giocatori e l'archivio restano come sono."
        )

    def test_con_il_json_rovinato_non_parte(self, banco):
        from db_players import load_players_db
        from ui import finalize_tournament

        _con_altri_soci(banco)
        intero = _leggi_byte(banco.db)
        with open(banco.db, "wb") as f:
            f.write(intero[: len(intero) // 2])
        database_prima = _leggi_byte(banco.db)
        torneo_prima = _leggi_byte(banco.file_torneo)
        torneo = copy.deepcopy(banco.torneo)

        esito = finalize_tournament(torneo, load_players_db(), banco.file_torneo, [])

        self._niente_e_cambiato(banco, database_prima, torneo_prima, esito, torneo)

    def test_in_console_si_rilegge_e_a_blocco_passato_si_finalizza(self, banco, monkeypatch):
        """Il controller legge il database all'avvio: se allora era
        bloccato, la finalizzazione lo rilegge, e a blocco passato va."""
        from test_db import lettura_bloccata

        _con_altri_soci(banco)
        lettura_bloccata(monkeypatch, banco.db)

        assert _finalizza_in_console(banco) is True

        database = _giocatori_del_db(banco.db)
        assert len(database) == 34
        assert database["G1"]["tournaments_played"][-1]["tournament_name"] == NOME

    def test_in_console_se_ancora_non_si_legge_non_parte(self, banco, monkeypatch):
        from test_db import lettura_bloccata

        _con_altri_soci(banco)
        database_prima = _leggi_byte(banco.db)
        torneo_prima = _leggi_byte(banco.file_torneo)
        lettura_bloccata(monkeypatch, banco.db, volte=2)
        messaggi = []

        assert _finalizza_in_console(banco, messaggi) is False

        assert _leggi_byte(banco.db) == database_prima
        assert _leggi_byte(banco.file_torneo) == torneo_prima
        assert not os.path.exists(_json_in_archivio())
        assert messaggi[0].startswith("Il database dei giocatori, Tornello - Players_db.json, c'è ma non si è potuto leggere: ")
        assert messaggi[1].startswith("La finalizzazione non parte: il torneo resta da concludere")

    def test_la_colonna_elo_var_dice_nd(self, banco, monkeypatch):
        """Durante il torneo la classifica rilegge il database a ogni
        salvataggio: letto vuoto, la colonna direbbe per tutti la variazione
        di un giocatore nuovo, con K 40."""
        from reports import get_standings_text
        from test_db import lettura_bloccata

        lettura_bloccata(monkeypatch, banco.db)
        in_corso = copy.deepcopy(banco.torneo)

        testo = get_standings_text(in_corso)

        assert {p["elo_change"] for p in in_corso["players"]} == {None}
        assert next(r for r in testo.splitlines() if "CognomeG1, NomeG1" in r).rstrip().endswith(" n.d.")
        assert (
            "La colonna Elo Var. si legge n.d. perché il database dei giocatori non si è potuto leggere: senza le schede dei giocatori il fattore K della finalizzazione non si conosce."
            in testo
        )
        # Con il database letto la riga non c'e'.
        assert "La colonna Elo Var. si legge n.d." not in get_standings_text(copy.deepcopy(banco.torneo))


def _rinomina_nel_torneo(torneo, vecchio, nuovo):
    """Cambia l'identificativo di un giocatore in tutto il torneo."""
    for giocatore in torneo["players"]:
        if giocatore["id"] == vecchio:
            giocatore["id"] = nuovo
        for voce in giocatore.get("results_history", []):
            if voce.get("opponent_id") == vecchio:
                voce["opponent_id"] = nuovo
        giocatore["opponents"] = [nuovo if o == vecchio else o for o in giocatore.get("opponents", [])]
    for turno in torneo["rounds"]:
        for partita in turno["matches"]:
            for lato in ("white_player_id", "black_player_id"):
                if partita.get(lato) == vecchio:
                    partita[lato] = nuovo


def iscritto_fide_con_la_scheda_altrove(banco):
    """G3 e' nel torneo come FIDE_12345, come i due iscritti di Autunneo2
    venuti dalla ricerca FIDE, e nel database come G3, con lo stesso
    identificativo FIDE, esperto e con 200 partite, cioe' con K 20: la
    scheda che Ctrl+K o l'iscrizione FIDE a un altro torneo avrebbero
    creato nel frattempo. La usano anche le prove della riapertura."""
    _rinomina_nel_torneo(banco.torneo, "G3", "FIDE_12345")
    for giocatore in banco.torneo["players"]:
        if giocatore["id"] == "FIDE_12345":
            giocatore["fide_id_num_str"] = "12345"
    _scrivi(banco.file_torneo, banco.torneo)
    dati = _leggi(banco.db)
    for scheda in dati["players"]:
        if scheda["id"] == "G3":
            scheda.update(fide_id_num_str="12345", experienced=True, games_played=200)
    _scrivi(banco.db, dati)


class TestIscrittoTrovatoPerIdentificativoFide:
    """Dalla 10.13.16 la finalizzazione cerca la scheda di un iscritto anche
    per identificativo FIDE: un iscritto FIDE_<id> che il database ha sotto
    un altro identificativo riceve Elo, partite, storico e medaglia su
    quella scheda, senza doppioni, e gli Avvisi lo dicono; la colonna Elo
    Var. usa il K di quella scheda."""

    def test_niente_doppione_e_tutto_va_alla_scheda_vera(self, banco):
        from db_players import load_players_db
        from reports import get_standings_text

        iscritto_fide_con_la_scheda_altrove(banco)
        in_corso = copy.deepcopy(banco.torneo)
        get_standings_text(in_corso, players_db=load_players_db())
        colonna = {p["id"]: (p["k_factor"], p["elo_change"]) for p in in_corso["players"]}
        assert colonna["FIDE_12345"] == (20, -3)
        avvisi = []

        assert _finalizza(banco, avvisi) is True

        database = _giocatori_del_db(banco.db)
        assert [pid for pid, s in database.items() if str(s.get("fide_id_num_str")) == "12345"] == ["G3"]
        assert "FIDE_12345" not in database
        g3 = database["G3"]
        voce = g3["tournaments_played"][-1]
        assert voce["id_nel_torneo"] == "FIDE_12345"
        assert "created_by_finalization" not in voce
        assert g3["current_elo"] == pytest.approx(ELO_INIZIALI["G3"] - 3)
        assert g3["games_played"] == 201
        archiviati = {p["id"]: (p["k_factor"], p["elo_change"]) for p in _leggi(_json_in_archivio())["players"]}
        assert archiviati == colonna
        assert "id_nel_torneo" not in database["G1"]["tournaments_played"][-1]
        assert avvisi == [
            "NomeG3 CognomeG3 è nel torneo con l'identificativo FIDE_12345, che il database dei giocatori non ha, e nel database con l'identificativo G3, con lo stesso identificativo FIDE: Elo, partite giocate, storico e medaglia sono andati alla scheda G3, senza crearne un doppione."
        ]
