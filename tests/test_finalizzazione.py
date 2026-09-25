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


def _finalizza_in_console(banco):
    """Finalizza come fa la versione a riga di comando: il controller con il
    suo modello del torneo e il database che tiene aperto."""
    import controller
    from db_players import load_players_db
    from models import Tournament

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
