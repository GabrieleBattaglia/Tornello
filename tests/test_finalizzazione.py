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

    def test_con_il_json_identico_l_archivio_resta_com_era(self, banco, tmp_path, monkeypatch):
        """Decisione di Gabriele, dalla 10.13.61 (issue 68): ripetendo la
        finalizzazione di un torneo gia' archiviato, l'archivio resta com'e'
        anche quando il json nuovo e' identico a quello archiviato, come
        quando e' diverso, e i report appena scritti vanno nella cartella
        backup con rifinalizzazione nel nome. Fino alla 10.13.60 la
        Classifica.txt dell'archivio veniva sostituita da quella nuova, con
        una copia pre_archiviazione: qui le due classifiche differiscono per
        la versione del programma che le firma, come dopo un aggiornamento
        fra le due finalizzazioni."""
        import reports

        assert _finalizza(banco) is True
        cartella = _cartella_archivio()
        archivio = {nome: _leggi_byte(os.path.join(cartella, nome)) for nome in os.listdir(cartella)}
        classifica = f"Tornello - {NOME} - Classifica.txt"
        assert sorted(archivio) == [classifica, f"Tornello - {NOME}.json"]
        database = _leggi_byte(banco.db)

        _scrivi(banco.file_torneo, banco.torneo)
        monkeypatch.setattr(reports, "VERSIONE", "versione successiva")
        avvisi = []
        assert _finalizza(banco, avvisi) is True

        assert {nome: _leggi_byte(os.path.join(cartella, nome)) for nome in os.listdir(cartella)} == archivio
        assert _leggi_byte(banco.db) == database
        assert _nella_radice(tmp_path) == []
        assert _copie(banco.backup, "pre_archiviazione") == []
        messi_da_parte = _copie(banco.backup, "rifinalizzazione")
        assert len(messi_da_parte) == 2
        json_nuovo = next(c for c in messi_da_parte if c.endswith(".json"))
        # Il json della seconda finalizzazione e' proprio identico.
        assert _leggi_byte(json_nuovo) == archivio[f"Tornello - {NOME}.json"]
        classifica_nuova = next(c for c in messi_da_parte if c.endswith(".txt"))
        with open(classifica_nuova, encoding="utf-8-sig") as f:
            assert "versione successiva" in f.read()
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

    def test_la_cartella_del_programma_scritta_in_minuscolo_non_e_esterna(
        self, banco, tmp_path
    ):
        """La cartella di lavoro e' quella del programma, ma il json la scrive
        in minuscolo. Fino alla 10.13.47 contava come esterna, e la classifica
        restava accanto al programma invece di andare in archivio (issue
        67)."""
        banco.torneo["custom_save_path"] = str(tmp_path).lower()
        _scrivi(banco.file_torneo, banco.torneo)

        assert _finalizza(banco) is True

        classifica = f"Tornello - {NOME} - Classifica.txt"
        assert os.path.exists(os.path.join(_cartella_archivio(), classifica))
        assert _nella_radice(tmp_path) == []


class TestCartelleConLeParentesiQuadre:
    """10.19.46 (decisione di Gabriele dell'8 novembre 2026). La cartella
    del programma, o la cartella di lavoro scelta, ha le parentesi quadre
    nel nome, come Tornello [prova]: la finalizzazione, dalla finestra e
    dalla console, trova i report del torneo, e li porta in archivio con il
    json. Fino alla 10.19.45, e gia' nella 10.0.0, glob leggeva le parentesi
    come un insieme di caratteri, e non trovava niente: i report restavano
    dov'erano, e in archivio andava soltanto il json."""

    DETTAGLI = f"Tornello - {NOME} - Turno 1 Dettagli.txt"
    CLASSIFICA = f"Tornello - {NOME} - Classifica.txt"

    @staticmethod
    def _finalizza_dalla(strada, banco):
        if strada == "finestra":
            return _finalizza(banco)
        return _finalizza_in_console(banco)

    @pytest.mark.parametrize("strada", ["finestra", "console"])
    def test_la_cartella_del_programma(self, programma_con_le_parentesi, tmp_path, monkeypatch, cestino_finto, strada):
        banco = prepara_il_banco(tmp_path, monkeypatch)
        assert banco.file_torneo.startswith(str(programma_con_le_parentesi))
        (programma_con_le_parentesi / self.DETTAGLI).write_text("dettagli", encoding="utf-8")

        assert self._finalizza_dalla(strada, banco) is True

        assert _nella_radice(programma_con_le_parentesi) == []
        assert sorted(os.listdir(_cartella_archivio())) == [self.CLASSIFICA, self.DETTAGLI, f"Tornello - {NOME}.json"]
        with open(os.path.join(_cartella_archivio(), self.DETTAGLI), encoding="utf-8") as f:
            assert f.read() == "dettagli"
        assert cestino_finto.ricevuti == []

    @pytest.mark.parametrize("strada", ["finestra", "console"])
    def test_la_cartella_di_lavoro_scelta(self, banco, tmp_path, cestino_finto, strada):
        """La cartella di lavoro esterna tiene i report, e l'archivio ne ha
        una copia."""
        esterna = tmp_path / "Lavoro [sociale]"
        esterna.mkdir()
        banco.torneo["custom_save_path"] = str(esterna)
        _scrivi(banco.file_torneo, banco.torneo)
        (esterna / self.DETTAGLI).write_text("dettagli", encoding="utf-8")

        assert self._finalizza_dalla(strada, banco) is True

        assert sorted(os.listdir(_cartella_archivio())) == [self.CLASSIFICA, self.DETTAGLI, f"Tornello - {NOME}.json"]
        assert sorted(os.listdir(esterna)) == [self.CLASSIFICA, self.DETTAGLI, f"Tornello - {NOME}.json"]
        with open(os.path.join(_cartella_archivio(), self.DETTAGLI), encoding="utf-8") as f:
            assert f.read() == "dettagli"
        assert _nella_radice(tmp_path) == []
        assert cestino_finto.ricevuti == []


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

    def test_un_ritirato_ha_l_elo_nella_voce(self, banco):
        """Dalla 10.19.5 (issue 73) un ritirato riceve la variazione delle
        partite giocate prima del ritiro, sull'Elo della cadenza, e la sua
        voce dello storico ha i campi dell'Elo, come quella degli altri: lo
        storno della riapertura li usa. G4, senza Elo rapid, patta con G3 da
        1600 partendo dal suo current_elo, 1500: D -100, PD 0,36, Delta R
        +0,14, per K 40 +5,6, cioe' +6, e l'Elo rapid gli nasce da 1500. Fino
        alla 10.19.0 restava senza variazione, con l'Elo rapid a zero e la
        voce senza i campi dell'Elo."""
        _con_la_cadenza(banco, "rapid")
        banco.torneo["players"][3]["withdrawn"] = True
        _scrivi(banco.file_torneo, banco.torneo)

        assert _finalizza(banco) is True

        g4 = _giocatori_del_db(banco.db)["G4"]
        voce = g4["tournaments_played"][-1]
        assert _variazioni_archiviate()["G4"] == 6
        assert (voce["elo_field"], voce["elo_before"], voce["elo_after"]) == ("elo_rapid", 0, 1506)
        assert g4["elo_rapid"] == 1506
        assert (g4["games_played"], g4["games_played_rapid"]) == (11, 1)
        assert voce["rank"] == "RIT"

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


class TestFattoreKDellaConsole:
    """Dalla 10.13.33 il fattore K passa da un punto solo,
    fattore_k_della_finalizzazione, anche nel primo calcolo del controller
    della console, che fino alla 10.13.32 dava 20 a chi il database non
    aveva, mentre la finalizzazione gli crea la scheda e, senza un K FIDE
    valido, gli da' 40. Un giocatore importato dal FIDE senza K valido, come
    G1 qui, ha 40."""

    def test_il_k_del_controller_e_quello_applicato(self, banco):
        import controller
        from db_players import load_players_db
        from models import Tournament

        dati = _leggi(banco.db)
        for scheda in dati["players"]:
            if scheda["id"] == "G1":
                scheda.update(fide_id_num_str="805165", fide_k_factor=0, games_played=0)
            elif scheda["id"] == "G2":
                scheda.update(experienced=True, games_played=80)
            elif scheda["id"] == "G4":
                scheda["fide_k_factor"] = 10
        dati["players"] = [g for g in dati["players"] if g["id"] != "G3"]
        _scrivi(banco.db, dati)
        messaggi = []
        finto = types.SimpleNamespace(
            tournament=Tournament.from_dict(copy.deepcopy(banco.torneo)),
            players_db=load_players_db(),
            active_filename=banco.file_torneo,
            ui=types.SimpleNamespace(show_message=messaggi.append, show_error=messaggi.append),
        )

        assert controller.TournamentController._finalize_tournament(finto) is True

        dal_controller = {p.id: p.k_factor for p in finto.tournament.players}
        applicati = {p["id"]: p["k_factor"] for p in _leggi(_json_in_archivio())["players"]}
        assert dal_controller == {"G1": 40, "G2": 20, "G3": 40, "G4": 10}
        assert dal_controller == applicati


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


class TestPartiteGiocateSenzaForfait:
    """Dalla 10.13.53 (issue 65) le partite giocate del database crescono
    soltanto delle partite valide per l'Elo, in tutte le cadenze: i forfait,
    come i bye, non contano (articolo 5.1 del regolamento FIDE sul rating,
    B.02, e articolo 4.1 di quello rapid e blitz). Fino alla 10.13.52
    games_this_tournament escludeva soltanto i riposi, e G3, che vince a
    forfait, e G4, che perde a forfait, arrivavano a 11 partite come G1 e
    G2, che hanno giocato."""

    @pytest.mark.parametrize("categoria", ["standard", "rapid", "blitz"])
    def test_i_forfait_non_entrano_nelle_partite_giocate(self, banco, categoria):
        _g3_vince_a_forfait(banco.torneo)
        _con_la_cadenza(banco, categoria)

        assert _finalizza(banco) is True

        dopo = _giocatori_del_db(banco.db)
        assert {pid: dopo[pid]["games_played"] for pid in ELO_INIZIALI} == {"G1": 11, "G2": 11, "G3": 10, "G4": 10}
        archiviati = {p["id"]: p["games_this_tournament"] for p in _leggi(_json_in_archivio())["players"]}
        assert archiviati == {"G1": 1, "G2": 1, "G3": 0, "G4": 0}

    def test_la_console_fa_come_la_finestra(self, banco):
        """La console conta le partite come la finestra: il database viene
        uguale, e il suo primo calcolo dice le stesse partite."""
        import unittest.mock

        import controller

        _g3_vince_a_forfait(banco.torneo)
        _scrivi(banco.file_torneo, banco.torneo)
        contate = {}
        originale = controller.partite_giocate_nel_torneo

        def annota(giocatore, giocatori, categoria="standard"):
            contate[giocatore["id"]] = originale(giocatore, giocatori, categoria)
            return contate[giocatore["id"]]

        with unittest.mock.patch.object(controller, "partite_giocate_nel_torneo", annota):
            assert _finalizza_in_console(banco) is True

        assert contate == {"G1": 1, "G2": 1, "G3": 0, "G4": 0}
        dopo = _giocatori_del_db(banco.db)
        assert {pid: dopo[pid]["games_played"] for pid in ELO_INIZIALI} == {"G1": 11, "G2": 11, "G3": 10, "G4": 10}

    def test_il_k_conta_le_partite_senza_i_forfait(self, banco):
        """Con 29 partite e un forfait, G3 resta a 29 partite valide: il K
        del torneo dopo resta 40, mentre con una partita giocata scende a
        20. Fino alla 10.13.52 il forfait lo portava a 30, e a K 20."""
        from db_players import fattore_k_della_finalizzazione, load_players_db

        _g3_vince_a_forfait(banco.torneo)
        dati = _leggi(banco.db)
        for giocatore in dati["players"]:
            giocatore["games_played"] = 29
        _scrivi(banco.db, dati)

        assert _finalizza(banco) is True

        database = load_players_db()
        assert database["G3"]["games_played"] == 29
        assert database["G1"]["games_played"] == 30
        assert fattore_k_della_finalizzazione({"id": "G3"}, database, "2027-01-10") == 40
        assert fattore_k_della_finalizzazione({"id": "G1"}, database, "2027-01-10") == 20


class TestFattoreKDellaCadenzaAllaFinalizzazione:
    """Dalla 10.13.54 (issue 65) nei rapid e nei blitz il fattore K viene
    dai dati della cadenza, alla finalizzazione, nella console e nella
    colonna Elo Var. della classifica in corso, e le partite del torneo si
    contano anche a parte, nel campo della cadenza, che la voce dello
    storico ricorda come games_field. Fino alla 10.13.53 il K veniva dai
    dati standard, e le partite di una cadenza non si contavano."""

    @staticmethod
    def _schede(banco, **per_giocatore):
        dati = _leggi(banco.db)
        for scheda in dati["players"]:
            scheda.update(per_giocatore.get(scheda["id"], {}))
        _scrivi(banco.db, dati)

    @pytest.mark.parametrize(("categoria", "campo_k"), [("rapid", "fide_rapid_k"), ("blitz", "fide_blitz_k")])
    def test_il_k_e_quello_della_cadenza(self, banco, categoria, campo_k):
        """G1 ha il K FIDE standard 40 e quello della cadenza 20, G2 il
        contrario: vale quello della cadenza. G3, esperto con cento partite
        ma senza un K FIDE, ha l'Elo della cadenza e solo dieci partite di
        quella cadenza: e' esperto, e ha 20. G4 non ha l'Elo della cadenza,
        ed e' nuovo in quella lista: 40, anche da esperto."""
        _con_la_cadenza(banco, categoria)
        self._schede(
            banco,
            G1={"fide_k_factor": 40, campo_k: 20},
            G2={"fide_k_factor": 20, campo_k: 40},
            G3={"experienced": True, "games_played": 100, f"games_played_{categoria}": 10},
            G4={"experienced": True, "games_played": 100, "fide_k_factor": 20},
        )

        assert _finalizza(banco) is True

        k = {p["id"]: p["k_factor"] for p in _leggi(_json_in_archivio())["players"]}
        assert k == {"G1": 20, "G2": 40, "G3": 20, "G4": 40}

    def test_negli_standard_resta_il_k_standard(self, banco):
        _con_la_cadenza(banco, "standard")
        self._schede(banco, G1={"fide_k_factor": 40, "fide_rapid_k": 20}, G2={"fide_k_factor": 10, "fide_blitz_k": 40})

        assert _finalizza(banco) is True

        k = {p["id"]: p["k_factor"] for p in _leggi(_json_in_archivio())["players"]}
        assert (k["G1"], k["G2"]) == (40, 10)

    @pytest.mark.parametrize(("categoria", "campo", "altro"), [("rapid", "games_played_rapid", "games_played_blitz"), ("blitz", "games_played_blitz", "games_played_rapid")])
    def test_le_partite_si_contano_anche_nella_cadenza(self, banco, categoria, campo, altro):
        """Le partite giocate crescono come sempre, e quelle della cadenza
        con loro; un forfait non entra in nessuna delle due. G2 aveva gia'
        il campo, e la voce dello storico se ne ricorda il valore."""
        _g3_vince_a_forfait(banco.torneo)
        _con_la_cadenza(banco, categoria)
        self._schede(banco, G2={campo: 7})

        assert _finalizza(banco) is True

        dopo = _giocatori_del_db(banco.db)
        assert {pid: dopo[pid]["games_played"] for pid in ELO_INIZIALI} == {"G1": 11, "G2": 11, "G3": 10, "G4": 10}
        assert {pid: dopo[pid][campo] for pid in ELO_INIZIALI} == {"G1": 1, "G2": 8, "G3": 0, "G4": 0}
        assert all(altro not in dopo[pid] for pid in ELO_INIZIALI)
        voci = {pid: dopo[pid]["tournaments_played"][-1] for pid in ELO_INIZIALI}
        assert {pid: voci[pid]["games_field"] for pid in ELO_INIZIALI} == dict.fromkeys(ELO_INIZIALI, campo)
        assert voci["G2"]["games_before"] == 7
        assert "games_before" not in voci["G1"]

    def test_negli_standard_non_si_contano_a_parte(self, banco):
        _con_la_cadenza(banco, "standard")

        assert _finalizza(banco) is True

        dopo = _giocatori_del_db(banco.db)
        for pid in ELO_INIZIALI:
            assert dopo[pid]["games_played"] == 11, pid
            assert not {"games_played_rapid", "games_played_blitz"} & dopo[pid].keys(), pid
            assert "games_field" not in dopo[pid]["tournaments_played"][-1], pid

    def test_la_colonna_elo_var_usa_il_k_della_cadenza(self, banco):
        """La classifica in corso di un rapid dice la variazione con il K
        della cadenza, quello che la finalizzazione applica."""
        from reports import get_standings_text

        _con_la_cadenza(banco, "rapid")
        self._schede(banco, G1={"fide_k_factor": 40, "fide_rapid_k": 20}, G4={"fide_k_factor": 10})
        in_corso = copy.deepcopy(banco.torneo)

        get_standings_text(in_corso)

        colonna = {p["id"]: (p["k_factor"], p["elo_change"]) for p in in_corso["players"]}
        assert colonna["G1"][0] == 20
        assert colonna["G4"][0] == 40
        assert _finalizza(banco) is True
        archiviati = {p["id"]: (p["k_factor"], p["elo_change"]) for p in _leggi(_json_in_archivio())["players"]}
        assert colonna == archiviati

    def test_il_k_del_controller_della_console_e_quello_della_cadenza(self, banco):
        """Il primo calcolo della console, prima della finalizzazione
        comune, usa lo stesso K della cadenza."""
        import unittest.mock

        import controller

        _con_la_cadenza(banco, "blitz")
        self._schede(banco, G1={"fide_k_factor": 40, "fide_blitz_k": 10})
        chiesti = []
        originale = controller.fattore_k_della_finalizzazione

        def annota(giocatore, database, inizio, categoria="standard"):
            chiesti.append((giocatore["id"], categoria))
            return originale(giocatore, database, inizio, categoria)

        with unittest.mock.patch.object(controller, "fattore_k_della_finalizzazione", annota):
            assert _finalizza_in_console(banco) is True

        assert set(chiesti) == {(pid, "blitz") for pid in ELO_INIZIALI}
        assert {p["id"]: p["k_factor"] for p in _leggi(_json_in_archivio())["players"]}["G1"] == 10


def _ritira_g4(banco):
    """G4 si ritira dopo il turno, con la sua partita giocata o a forfait."""
    banco.torneo["players"][3]["withdrawn"] = True
    _scrivi(banco.file_torneo, banco.torneo)


def _dati_archiviati():
    """K, partite e variazione di ogni giocatore del torneo archiviato."""
    return {p["id"]: (p["k_factor"], p["games_this_tournament"], p["elo_change"]) for p in _leggi(_json_in_archivio())["players"]}


class TestPartiteDeiRitirati:
    """Dalla 10.19.5 (issue 73) le partite che un ritirato ha giocato prima
    del ritiro si valutano: l'articolo 5.1 del regolamento FIDE sul rating
    (B.02), e il 4.1 di quello rapid e blitz, valutano ogni partita in cui i
    due giocatori hanno fatto almeno una mossa, e lasciano fuori soltanto
    quelle non giocate, per forfait o per qualunque altro motivo. Il
    ritirato riceve variazione, partite giocate e voce dello storico con i
    campi dell'Elo, nella finestra e nella console, e la colonna Elo Var.
    della classifica in corso dice la stessa variazione. Fino alla 10.19.0
    restava senza variazione e senza partite, mentre i suoi avversari
    avevano le partite giocate con lui.
    G4, 1500, patta con G3, 1600, e si ritira: D -100, PD 0,36, Delta R
    +0,14, per K 40 +5,6, cioe' +6. G3: PD 0,64, Delta R -0,14, -6."""

    def test_le_partite_giocate_si_valutano(self, banco):
        _ritira_g4(banco)

        assert _finalizza(banco) is True

        archiviati = _dati_archiviati()
        assert archiviati["G4"] == (40, 1, 6)
        assert archiviati["G3"] == (40, 1, -6)
        dopo = _giocatori_del_db(banco.db)
        assert (dopo["G4"]["current_elo"], dopo["G4"]["games_played"]) == (1506, 11)
        assert (dopo["G3"]["current_elo"], dopo["G3"]["games_played"]) == (1594, 11)
        voce = dopo["G4"]["tournaments_played"][-1]
        assert (voce["elo_field"], voce["elo_before"], voce["elo_after"], voce["rank"]) == ("current_elo", 1500, 1506, "RIT")
        assert dopo["G4"]["medals"] == {"gold": 0, "silver": 0, "bronze": 0, "wood": 0}

    def test_a_soli_forfait_niente_variazione_e_niente_partite(self, banco):
        """G4 perde a forfait con G3 e si ritira: la partita non giocata
        resta fuori, come per tutti, e G4 resta con l'Elo e le partite di
        prima."""
        _g3_vince_a_forfait(banco.torneo)
        _ritira_g4(banco)

        assert _finalizza(banco) is True

        assert _dati_archiviati()["G4"] == (40, 0, 0)
        dopo = _giocatori_del_db(banco.db)
        assert (dopo["G4"]["current_elo"], dopo["G4"]["games_played"]) == (1500, 10)

    @pytest.mark.parametrize(("categoria", "variazione"), [("standard", 6), ("rapid", 6), ("blitz", 4)])
    def test_la_console_fa_come_la_finestra(self, banco, categoria, variazione):
        """Lo stesso torneo con il ritirato, finalizzato dalla finestra e,
        rimesso tutto com'era, dalla console: il database viene uguale, e il
        primo calcolo del controller dice le stesse partite e la stessa
        variazione. Nel blitz G3 ha 1580: D -80, PD 0,39, +0,11 per 40,
        +4,4, cioe' +4."""
        import shutil

        import controller
        from db_players import load_players_db
        from models import Tournament

        prima = _con_la_cadenza(banco, categoria)
        _ritira_g4(banco)
        database_prima = _leggi_byte(banco.db)
        assert _finalizza(banco) is True
        dalla_finestra = _giocatori_del_db(banco.db)
        archiviati = _dati_archiviati()

        with open(banco.db, "wb") as f:
            f.write(database_prima)
        _scrivi(banco.file_torneo, banco.torneo)
        shutil.rmtree(_cartella_archivio())
        messaggi = []
        finto = types.SimpleNamespace(
            tournament=Tournament.from_dict(copy.deepcopy(banco.torneo)),
            players_db=load_players_db(),
            active_filename=banco.file_torneo,
            ui=types.SimpleNamespace(show_message=messaggi.append, show_error=messaggi.append),
        )
        assert controller.TournamentController._finalize_tournament(finto) is True

        assert _giocatori_del_db(banco.db) == dalla_finestra
        dal_controller = {p.id: (p.k_factor, p.games_this_tournament, p.elo_change) for p in finto.tournament.players}
        assert dal_controller == archiviati
        assert archiviati["G4"][1:] == (1, variazione)
        campo = {"rapid": "elo_rapid", "blitz": "elo_blitz"}.get(categoria, "current_elo")
        assert dalla_finestra["G4"][campo] == (prima["G4"][campo] or prima["G4"]["current_elo"]) + variazione

    def test_la_colonna_elo_var_della_classifica_in_corso(self, banco):
        """La classifica in corso dice per il ritirato la variazione che la
        finalizzazione applica, e non piu' n.d.; la performance resta n.d."""
        from reports import get_standings_text

        _ritira_g4(banco)
        in_corso = copy.deepcopy(banco.torneo)

        testo = get_standings_text(in_corso)

        colonna = {p["id"]: (p["k_factor"], p["elo_change"]) for p in in_corso["players"]}
        assert colonna["G4"] == (40, 6)
        riga = next(r for r in testo.splitlines() if "CognomeG4, NomeG4" in r)
        assert _("n.d.") + "   +6" in riga
        assert riga.endswith("[RITIRATO]")
        assert _finalizza(banco) is True
        archiviati = {pid: (k, variazione) for pid, (k, _partite, variazione) in _dati_archiviati().items()}
        assert colonna == archiviati

    def test_la_classifica_del_torneo_concluso_dice_la_variazione(self, banco):
        """Il torneo archiviato, riletto, mostra la variazione salvata del
        ritirato, senza la riga dei valori non salvati."""
        from reports import get_standings_text

        _ritira_g4(banco)
        assert _finalizza(banco) is True

        testo = get_standings_text(_leggi(_json_in_archivio()))

        riga = next(r for r in testo.splitlines() if "CognomeG4, NomeG4" in r)
        assert "   +6" in riga
        assert "I valori n.d. dei giocatori non ritirati" not in testo


def _con_gli_elo(banco, categoria, **per_giocatore):
    """Il torneo della cadenza scelta, come _con_la_cadenza, con i campi di
    per_giocatore nelle schede del database e l'Elo di partenza che
    l'iscrizione darebbe con quei campi."""
    from stats import get_initial_elo_for_tournament

    _con_la_cadenza(banco, categoria)
    dati = _leggi(banco.db)
    for scheda in dati["players"]:
        scheda.update(per_giocatore.get(scheda["id"], {}))
    _scrivi(banco.db, dati)
    schede = {g["id"]: g for g in dati["players"]}
    for giocatore in banco.torneo["players"]:
        giocatore["initial_elo"] = get_initial_elo_for_tournament(schede[giocatore["id"]], categoria)
    _scrivi(banco.file_torneo, banco.torneo)
    return copy.deepcopy(schede)


class TestRegoleFideAllaFinalizzazione:
    """Dalla 10.19.5 (issue 73) la finalizzazione, nella finestra e nella
    console, e la colonna Elo Var. della classifica in corso passano la
    cadenza del torneo al calcolo della variazione: la soglia dei 400 punti
    dell'articolo 8.3.1 del B.02 vale negli standard soltanto sotto 2650, e
    nei rapid e nei blitz per tutti (articolo 7.3.1), dove una partita con
    600 punti di differenza e un giocatore sopra 2600 non si valuta. G1
    batte G2, G3 e G4 pattano; il K e' 40 per tutti, con dieci partite."""

    @pytest.mark.parametrize(("elo_di_g1", "elo_di_g2", "attese"), [(2650, 2150, (2, -3)), (2649, 2149, (3, -3))])
    def test_la_soglia_dei_400_negli_standard(self, banco, elo_di_g1, elo_di_g2, attese):
        """Con 500 punti di differenza un 2650 usa la differenza vera, PD
        0,96: +0,04 per 40, +1,6, cioe' +2; un 2649 la soglia, PD 0,92:
        +0,08 per 40, +3,2, cioe' +3. G2, sotto 2650, ha la soglia: -0,08
        per 40, -3. La formula di prima dava +4 e -4."""
        _con_gli_elo(banco, "standard", G1={"current_elo": elo_di_g1}, G2={"current_elo": elo_di_g2})

        assert _finalizza(banco) is True

        archiviati = _dati_archiviati()
        assert (archiviati["G1"][2], archiviati["G2"][2]) == attese
        dopo = _giocatori_del_db(banco.db)
        assert (dopo["G1"]["current_elo"], dopo["G2"]["current_elo"]) == (elo_di_g1 + attese[0], elo_di_g2 + attese[1])

    @pytest.mark.parametrize(("categoria", "campo"), [("rapid", "elo_rapid"), ("blitz", "elo_blitz")])
    def test_nei_rapid_e_nei_blitz_la_soglia_vale_per_tutti(self, banco, categoria, campo):
        """Lo stesso 2650 contro un 2150: 500 punti contano 400, +3 e -3."""
        _con_gli_elo(banco, categoria, G1={campo: 2650}, G2={campo: 2150})

        assert _finalizza(banco) is True

        archiviati = _dati_archiviati()
        assert (archiviati["G1"][2], archiviati["G2"][2]) == (3, -3)

    @pytest.mark.parametrize("dove", ["finestra", "console"])
    @pytest.mark.parametrize(("categoria", "campo"), [("rapid", "elo_rapid"), ("blitz", "elo_blitz")])
    def test_una_partita_con_600_punti_non_si_valuta(self, banco, categoria, campo, dove):
        """G1, 2700 nella cadenza, batte G2, 2000: 700 punti e un giocatore
        sopra 2600, la partita non si valuta. Tutti e due restano con la
        variazione zero, l'Elo della cadenza di prima e le partite di prima;
        G3, 1600 nella cadenza, e G4, che parte dal suo current_elo, 1500,
        hanno la loro patta, -6 e +6. La colonna Elo Var. della classifica in
        corso dice gli stessi valori."""
        from reports import get_standings_text

        prima = _con_gli_elo(banco, categoria, G1={campo: 2700}, G2={campo: 2000}, G3={campo: 1600})
        in_corso = copy.deepcopy(banco.torneo)
        get_standings_text(in_corso)

        assert (_finalizza(banco) if dove == "finestra" else _finalizza_in_console(banco)) is True

        archiviati = _dati_archiviati()
        assert {pid: valori[1:] for pid, valori in archiviati.items()} == {"G1": (0, 0), "G2": (0, 0), "G3": (1, -6), "G4": (1, 6)}
        assert {p["id"]: p["elo_change"] for p in in_corso["players"]} == {"G1": 0, "G2": 0, "G3": -6, "G4": 6}
        dopo = _giocatori_del_db(banco.db)
        for pid in ("G1", "G2"):
            assert dopo[pid][campo] == prima[pid][campo], pid
            assert (dopo[pid]["games_played"], dopo[pid][f"games_played_{categoria}"]) == (10, 0), pid
        assert (dopo["G3"]["games_played"], dopo["G4"]["games_played"]) == (11, 11)

    def test_negli_standard_la_stessa_partita_si_valuta(self, banco):
        """La stessa partita in uno standard: G1, da 2650 in su, usa la
        differenza vera, 700 punti, PD 0,99, +0,01 per 40, +0,4, cioe' 0;
        G2 la soglia, PD 0,08, -0,08 per 40, -3. Tutti e due hanno la
        partita."""
        _con_gli_elo(banco, "standard", G1={"current_elo": 2700}, G2={"current_elo": 2000})

        assert _finalizza(banco) is True

        archiviati = _dati_archiviati()
        assert (archiviati["G1"][1:], archiviati["G2"][1:]) == ((1, 0), (1, -3))
        dopo = _giocatori_del_db(banco.db)
        assert (dopo["G1"]["games_played"], dopo["G2"]["games_played"]) == (11, 11)


# Il PGN della prima partita del torneo della prova e il nome della sua
# raccolta delle partite, come li scrive la finestra.
PGN_DELLA_PROVA = '[Event "Coppa Prova"]\n\n1. e4 e5 2. Nf3 Nc6 1-0'
RACCOLTA = f"{NOME} - raccolta partite.pgn"


def _raccolta_di(*pgn):
    """Il contenuto della raccolta delle partite con questi PGN, come la
    scrivono la finestra e, dalla 10.19.13, la finalizzazione: separati da
    una riga vuota, con l'a capo in fondo, in UTF-8 e con l'a capo del
    sistema."""
    return ("\n\n".join(p.strip() for p in pgn) + "\n").replace("\n", os.linesep).encode("utf-8")


def _con_la_raccolta(banco, cartella=None):
    """Il torneo con il PGN della prima partita, salvato, e la sua raccolta
    nella cartella di lavoro, senza cartella quella del file del torneo,
    con l'a capo del sistema. Restituisce il percorso e il contenuto della
    raccolta."""
    banco.torneo["rounds"][0]["matches"][0]["pgn"] = PGN_DELLA_PROVA
    _scrivi(banco.file_torneo, banco.torneo)
    percorso = os.path.join(cartella or os.path.dirname(banco.file_torneo), RACCOLTA)
    contenuto = (PGN_DELLA_PROVA + "\n").replace("\n", os.linesep).encode("utf-8")
    with open(percorso, "wb") as f:
        f.write(contenuto)
    return percorso, contenuto


class TestRaccoltaDellePartiteInArchivio:
    """Dalla 10.19.7 (issue 66, decisione di Gabriele del 4 novembre 2026)
    la raccolta delle partite in PGN va in archivio con i report, nella
    finestra e in console, e segue la loro strada: spostata dalla cartella
    del programma, copiata dalla cartella di lavoro esterna, messa nella
    cartella backup da una finalizzazione ripetuta. Fino alla 10.19.5
    restava nella cartella di salvataggio, dove la nuova edizione con lo
    stesso nome la cancellava o la sostituiva."""

    @pytest.mark.parametrize("dove", ["finestra", "console"])
    def test_va_in_archivio_e_lascia_la_cartella(self, banco, dove):
        raccolta, contenuto = _con_la_raccolta(banco)

        assert (_finalizza(banco) if dove == "finestra" else _finalizza_in_console(banco)) is True

        assert _leggi_byte(os.path.join(_cartella_archivio(), RACCOLTA)) == contenuto
        assert not os.path.exists(raccolta)
        assert _copie(banco.backup, "pre_archiviazione") == []

    def test_dalla_cartella_esterna_si_copia_e_resta(self, banco, tmp_path):
        esterna = tmp_path / "esterna"
        esterna.mkdir()
        banco.torneo["custom_save_path"] = str(esterna)
        raccolta, contenuto = _con_la_raccolta(banco, str(esterna))

        assert _finalizza(banco) is True

        assert _leggi_byte(os.path.join(_cartella_archivio(), RACCOLTA)) == contenuto
        assert _leggi_byte(raccolta) == contenuto

    def test_nella_finalizzazione_ripetuta_va_nella_cartella_backup(self, banco):
        """L'archivio resta com'era, con la sua raccolta, e quella nuova va
        nella cartella backup con rifinalizzazione nel nome, come i report.
        Dalla 10.19.13 la finalizzazione scrive prima la raccolta del torneo,
        come l'ultimo salvataggio della finestra: quella che c'era, scritta
        dopo, si sostituisce, e nella cartella backup va quella con la
        partita in PGN in piu'."""
        raccolta, contenuto = _con_la_raccolta(banco)
        assert _finalizza(banco) is True
        in_archivio = os.path.join(_cartella_archivio(), RACCOLTA)
        assert _leggi_byte(in_archivio) == contenuto

        banco.torneo["rounds"][0]["matches"][1]["pgn"] = TestEdizioneRinominataDaDati.PGN_SECONDA
        _scrivi(banco.file_torneo, banco.torneo)
        with open(raccolta, "wb") as f:
            f.write(b"raccolta scritta dopo")
        avvisi = []
        assert _finalizza(banco, avvisi) is True

        assert any("già finalizzato e archiviato" in a for a in avvisi)
        assert _leggi_byte(in_archivio) == contenuto
        assert not os.path.exists(raccolta)
        messe_da_parte = [c for c in _copie(banco.backup, "rifinalizzazione") if c.endswith(".pgn")]
        assert [_leggi_byte(c) for c in messe_da_parte] == [_raccolta_di(PGN_DELLA_PROVA, TestEdizioneRinominataDaDati.PGN_SECONDA)]

    def test_quella_gia_nella_cartella_d_archivio_resta(self, banco):
        """Il torneo aperto da un file dell'archivio, senza una cartella di
        lavoro: la sua raccolta sta gia' nella cartella d'archivio, e non si
        sposta su se stessa, che vorrebbe dire cancellarla. Una guardia: con
        la 10.19.5 la raccolta non si spostava mai."""
        cartella = _cartella_archivio()
        os.makedirs(cartella)
        aperto = _json_in_archivio(cartella)
        os.remove(banco.file_torneo)
        banco.file_torneo = aperto
        raccolta, contenuto = _con_la_raccolta(banco)
        assert os.path.dirname(raccolta) == cartella

        assert _finalizza(banco) is True

        assert _leggi_byte(raccolta) == contenuto


def _contenuto_della_cartella(cartella):
    """Nome e byte di ogni file della cartella."""
    return {n: _leggi_byte(os.path.join(cartella, n)) for n in sorted(os.listdir(cartella))}


class TestEdizioneRinominataDaDati:
    """Correzione della revisione della 10.19.7 (issue 66): un torneo
    rinominato da Dati con il nome di un'edizione archiviata tiene il file di
    prima, per esempio Tornello - Alfa.json. Concluso nello stesso mese di
    quell'edizione, entrava nella sua cartella d'archivio, che sembrava
    libera perche' non conteneva un json con lo stesso nome di file, e ne
    sostituiva la classifica e la raccolta delle partite. Adesso conta ogni
    json della cartella: il torneo prende la cartella con la data di inizio,
    come le altre edizioni dello stesso mese, e quella della prima resta
    com'era. Lo stesso quando il file con l'altro nome e' quello della prima
    edizione."""

    SECONDA = "2026-07-20"
    PGN_SECONDA = '[Event "Seconda"]\n\n1. d4 d5 1/2-1/2'

    def _seconda_edizione(self, file_della_seconda):
        """La seconda edizione, con il nome della prima, un'altra data di
        inizio nello stesso mese, il suo PGN e la sua raccolta nella cartella
        del programma. Restituisce il torneo e il contenuto della raccolta."""
        import config

        seconda = copy.deepcopy(_torneo_finito())
        seconda.update(tournament_id="ALFA", start_date=self.SECONDA, end_date="2026-07-21")
        seconda["rounds"][0]["matches"][0]["pgn"] = self.PGN_SECONDA
        _scrivi(config.user_data_path(file_della_seconda), seconda)
        contenuto = (self.PGN_SECONDA + "\n").replace("\n", os.linesep).encode("utf-8")
        with open(config.user_data_path(RACCOLTA), "wb") as f:
            f.write(contenuto)
        return seconda, contenuto

    @pytest.mark.parametrize("dove", ["finestra", "console"])
    @pytest.mark.parametrize(
        ("file_della_prima", "file_della_seconda"),
        [(f"Tornello - {NOME}.json", "Tornello - Alfa.json"), ("Tornello - Alfa.json", f"Tornello - {NOME}.json")],
        ids=["rinominata la seconda", "rinominata la prima"],
    )
    def test_ognuna_nella_sua_cartella(self, banco, dove, file_della_prima, file_della_seconda):
        import config

        # La prima edizione, con la sua raccolta, nel file file_della_prima.
        os.remove(banco.file_torneo)
        banco.file_torneo = config.user_data_path(file_della_prima)
        _raccolta, contenuto_prima = _con_la_raccolta(banco)
        assert _finalizza(banco) is True
        cartella = _cartella_archivio()
        prima = _contenuto_della_cartella(cartella)
        assert prima[RACCOLTA] == contenuto_prima
        assert file_della_prima in prima

        banco.torneo, contenuto_seconda = self._seconda_edizione(file_della_seconda)
        banco.file_torneo = config.user_data_path(file_della_seconda)
        avvisi = []
        if dove == "finestra":
            assert _finalizza(banco, avvisi) is True
        else:
            assert _finalizza_in_console(banco) is True

        assert _contenuto_della_cartella(cartella) == prima
        cartella_seconda = f"{cartella}_{self.SECONDA}"
        assert _leggi_byte(os.path.join(cartella_seconda, RACCOLTA)) == contenuto_seconda
        assert _leggi(os.path.join(cartella_seconda, file_della_seconda))["tournament_id"] == "ALFA"
        assert os.path.exists(os.path.join(cartella_seconda, f"Tornello - {NOME} - Classifica.txt"))
        assert _copie(banco.backup, "pre_archiviazione") == []
        if dove == "finestra":
            assert any(cartella_seconda in a for a in avvisi)

    def test_una_cartella_con_un_json_che_non_si_legge_non_si_usa(self, banco):
        """Un json rovinato con un altro nome, nella cartella con il nome del
        torneo, conta come quello di un altro torneo, come gia' quello con
        lo stesso nome."""
        cartella = _cartella_archivio()
        os.makedirs(cartella)
        rovinato = os.path.join(cartella, "Tornello - Alfa.json")
        with open(rovinato, "wb") as f:
            f.write(b"{non e' json")

        assert _finalizza(banco) is True

        assert _leggi_byte(rovinato) == b"{non e' json"
        assert os.listdir(cartella) == ["Tornello - Alfa.json"]
        assert _leggi(_json_in_archivio(f"{cartella}_{INIZIO}"))["concluded"] is True

    def test_un_file_al_posto_della_cartella_non_la_occupa(self, banco):
        """Un file con il nome della cartella del torneo, nella cartella del
        mese, non si puo' leggere come cartella: il torneo prende quella con
        la data di inizio. Prima la cartella sembrava libera, e la sua
        creazione non riusciva."""
        cartella = _cartella_archivio()
        os.makedirs(os.path.dirname(cartella))
        with open(cartella, "wb") as f:
            f.write(b"un file, non una cartella")

        assert _finalizza(banco) is True

        assert _leggi_byte(cartella) == b"un file, non una cartella"
        assert _leggi(_json_in_archivio(f"{cartella}_{INIZIO}"))["concluded"] is True


# La prima edizione di Coppa_Prova, archiviata a giugno 2026 da una versione
# fino alla 10.19.5, con il PGN della sua prima partita.
PGN_DELLA_PRIMA = '[Event "Prima"]\n\n1. c4 e5 0-1'


def _cestino_finto(monkeypatch, cartella, prende=True):
    """Al posto di delete_file_to_trash: annota ogni file che riceve, e lo
    sposta in cartella; con prende falso lo lascia dov'e', come un disco
    senza cestino."""
    import shutil

    import utils

    ricevuti = []

    def cestino(percorso, finestra=None):
        ricevuti.append(os.path.normcase(os.path.abspath(percorso)))
        if not prende:
            return False
        os.makedirs(cartella, exist_ok=True)
        shutil.move(percorso, os.path.join(cartella, f"{len(ricevuti)}_{os.path.basename(percorso)}"))
        return True

    monkeypatch.setattr(utils, "delete_file_to_trash", cestino)
    return ricevuti


def _prima_edizione_con_la_raccolta_lasciata(file_della_prima=f"Tornello - {NOME}.json"):
    """La prima edizione di Coppa_Prova, dal 1 al 2 giugno 2026, archiviata
    nel file file_della_prima, e la sua raccolta delle partite lasciata
    nella cartella del programma, come la lasciava la finalizzazione fino
    alla 10.19.5. Con Tornello - Alfa.json e' un'edizione rinominata dal ramo
    Dati prima di finalizzarla. Restituisce la sua cartella d'archivio e il
    contenuto della raccolta."""
    import config
    import ui

    prima = copy.deepcopy(_torneo_finito())
    prima.update(start_date="2026-06-01", end_date="2026-06-02", concluded=True)
    prima["rounds"][0]["matches"][0]["pgn"] = PGN_DELLA_PRIMA
    cartella = os.path.join(ui.ARCHIVED_TOURNAMENTS_DIR, "2026", "06 Giugno", NOME)
    os.makedirs(cartella)
    _scrivi(os.path.join(cartella, file_della_prima), prima)
    contenuto = _raccolta_di(PGN_DELLA_PRIMA)
    with open(config.user_data_path(RACCOLTA), "wb") as f:
        f.write(contenuto)
    return cartella, contenuto


class TestRaccoltaDiUnAltraEdizioneAllaFinalizzazione:
    """Dalla 10.19.13 (issue 66, decisione di Gabriele del 4 novembre 2026)
    la finalizzazione, nella finestra e in console, scrive prima la raccolta
    delle partite del torneo, come l'ultimo salvataggio della finestra, e
    porta in archivio soltanto quella. La raccolta identica a quella di
    un'altra edizione archiviata con lo stesso nome, anche rinominata dal
    ramo Dati, va nella cartella d'archivio di quell'edizione, con una copia
    riletta, e l'originale nel cestino. Fino alla 10.19.10 la finalizzazione
    portava nel suo archivio la raccolta che trovava al suo percorso,
    qualunque fosse, e la console, che la raccolta non la scrive, ne portava
    una vecchia, o nessuna. Il cestino e' finto."""

    @pytest.mark.parametrize("dove", ["finestra", "console"])
    @pytest.mark.parametrize("file_della_prima", [f"Tornello - {NOME}.json", "Tornello - Alfa.json"], ids=["stesso file", "rinominata da Dati"])
    def test_va_nella_cartella_della_sua_edizione(self, banco, monkeypatch, tmp_path, capsys, dove, file_della_prima):
        """La nuova edizione, senza partite in PGN, nata e finalizzata in
        console, trova la raccolta della prima: va nella cartella d'archivio
        della prima, l'originale nel cestino, e l'archivio della nuova
        edizione resta senza raccolta. Una riga lo dice."""
        import config

        cartella_prima, contenuto = _prima_edizione_con_la_raccolta_lasciata(file_della_prima)
        lasciata = config.user_data_path(RACCOLTA)
        ricevuti = _cestino_finto(monkeypatch, str(tmp_path / "cestino"))
        avvisi = []

        assert (_finalizza(banco, avvisi) if dove == "finestra" else _finalizza_in_console(banco)) is True

        assert _leggi_byte(os.path.join(cartella_prima, RACCOLTA)) == contenuto
        assert ricevuti == [os.path.normcase(os.path.abspath(lasciata))]
        assert _leggi_byte(tmp_path / "cestino" / f"1_{RACCOLTA}") == contenuto
        assert not os.path.exists(lasciata)
        assert RACCOLTA not in os.listdir(_cartella_archivio())
        archivio = os.path.join("Closed Tournaments", "2026", "06 Giugno", NOME)
        frase = (
            f"Nella cartella {os.path.dirname(lasciata)} c'era la raccolta delle partite {RACCOLTA} del torneo {NOME}, concluso e archiviato nella cartella {archivio}: il torneo {NOME} l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
            f"Una copia identica, riletta, adesso è nella cartella d'archivio di quel torneo, e quella della cartella {os.path.dirname(lasciata)} è andata nel cestino di Windows."
        )
        if dove == "finestra":
            assert frase in avvisi
        else:
            assert frase in capsys.readouterr().out

    @pytest.mark.parametrize("dove", ["finestra", "console"])
    def test_il_torneo_con_le_sue_partite_porta_in_archivio_la_sua(self, banco, monkeypatch, tmp_path, dove):
        """La nuova edizione ha la sua partita in PGN: la raccolta della prima
        va nella sua cartella, e nell'archivio della nuova c'e' la sua."""
        import config

        cartella_prima, contenuto = _prima_edizione_con_la_raccolta_lasciata()
        _cestino_finto(monkeypatch, str(tmp_path / "cestino"))
        banco.torneo["rounds"][0]["matches"][0]["pgn"] = PGN_DELLA_PROVA
        _scrivi(banco.file_torneo, banco.torneo)

        assert (_finalizza(banco) if dove == "finestra" else _finalizza_in_console(banco)) is True

        assert _leggi_byte(os.path.join(cartella_prima, RACCOLTA)) == contenuto
        assert _leggi_byte(os.path.join(_cartella_archivio(), RACCOLTA)) == _raccolta_di(PGN_DELLA_PROVA)
        assert not os.path.exists(config.user_data_path(RACCOLTA))

    @pytest.mark.parametrize("dove", ["finestra", "console"])
    @pytest.mark.parametrize("di_prima", [False, True], ids=["senza raccolta", "con la raccolta di prima"])
    def test_in_archivio_la_raccolta_del_torneo_com_e_alla_fine(self, banco, dove, di_prima):
        """Le due partite del torneo hanno il PGN, e la raccolta sul disco
        non c'e', come per un torneo giocato in console, o ha soltanto la
        prima. In archivio va la raccolta con tutte e due, come dalla
        finestra, che la scrive a ogni salvataggio."""
        import config

        banco.torneo["rounds"][0]["matches"][0]["pgn"] = PGN_DELLA_PROVA
        banco.torneo["rounds"][0]["matches"][1]["pgn"] = TestEdizioneRinominataDaDati.PGN_SECONDA
        _scrivi(banco.file_torneo, banco.torneo)
        raccolta = config.user_data_path(RACCOLTA)
        if di_prima:
            with open(raccolta, "wb") as f:
                f.write(_raccolta_di(PGN_DELLA_PROVA))

        assert (_finalizza(banco) if dove == "finestra" else _finalizza_in_console(banco)) is True

        attesa = _raccolta_di(PGN_DELLA_PROVA, TestEdizioneRinominataDaDati.PGN_SECONDA)
        assert _leggi_byte(os.path.join(_cartella_archivio(), RACCOLTA)) == attesa
        assert not os.path.exists(raccolta)

    def test_se_non_si_mette_in_salvo_resta_e_non_va_in_archivio(self, banco, monkeypatch, tmp_path):
        """La cartella della prima edizione ha gia' una raccolta diversa, e
        il cestino non prende quella lasciata: resta dov'era, non va
        nell'archivio della nuova edizione, e un avviso lo dice. La
        finalizzazione va in fondo lo stesso."""
        import config

        cartella_prima, contenuto = _prima_edizione_con_la_raccolta_lasciata()
        diversa = os.path.join(cartella_prima, RACCOLTA)
        with open(diversa, "wb") as f:
            f.write(b"un'altra raccolta")
        lasciata = config.user_data_path(RACCOLTA)
        ricevuti = _cestino_finto(monkeypatch, str(tmp_path / "cestino"), prende=False)
        avvisi = []

        assert _finalizza(banco, avvisi) is True

        assert _leggi_byte(lasciata) == contenuto
        assert _leggi_byte(diversa) == b"un'altra raccolta"
        assert ricevuti == [os.path.normcase(os.path.abspath(lasciata))]
        assert RACCOLTA not in os.listdir(_cartella_archivio())
        cartella = os.path.dirname(lasciata)
        assert (
            f"Nella cartella {cartella} c'è la raccolta delle partite {RACCOLTA}, che non è del torneo {NOME}: il torneo la sostituirebbe con la sua raccolta, o la cancellerebbe.\n"
            "Non si è potuta mettere in salvo, né nella cartella d'archivio di un torneo concluso con lo stesso nome né nel cestino di Windows, per esempio perché quel disco non ha il cestino.\n"
            f"La raccolta delle partite del torneo {NOME} non è stata scritta e non va in archivio, e quella che c'è resta dov'è: spostala tu in un'altra cartella. Le partite del torneo restano nel suo file, in archivio."
        ) in avvisi

    @pytest.mark.parametrize("prende", [True, False])
    def test_senza_partite_in_pgn_la_raccolta_va_nel_cestino(self, banco, monkeypatch, tmp_path, prende):
        """Il torneo non ha piu' partite in PGN, per esempio dopo una Time
        Machine, e la sua raccolta di prima e' ancora nella cartella del
        programma: va nel cestino, e non in archivio. Se il cestino non la
        prende resta dov'e', mai cancellata per sempre, e un avviso lo dice.
        Fino alla 10.19.10 andava in archivio."""
        import config

        raccolta = config.user_data_path(RACCOLTA)
        with open(raccolta, "wb") as f:
            f.write(_raccolta_di(PGN_DELLA_PROVA))
        ricevuti = _cestino_finto(monkeypatch, str(tmp_path / "cestino"), prende)
        avvisi = []

        assert _finalizza(banco, avvisi) is True

        assert ricevuti == [os.path.normcase(os.path.abspath(raccolta))]
        assert RACCOLTA not in os.listdir(_cartella_archivio())
        detto = [a for a in avvisi if RACCOLTA in a]
        if prende:
            assert not os.path.exists(raccolta)
            assert detto == []
        else:
            assert _leggi_byte(raccolta) == _raccolta_di(PGN_DELLA_PROVA)
            assert detto == [
                f"Il torneo {NOME} non ha più partite in PGN, e la sua raccolta delle partite {RACCOLTA}, nella cartella {os.path.dirname(raccolta)}, doveva andare nel cestino di Windows, che non l'ha presa, per esempio perché quel disco non ha il cestino. Resta dov'è, con le partite di prima: Tornello non la cancella per sempre. Non va in archivio con il torneo."
            ]

    @pytest.mark.parametrize("dove", ["finestra", "console", "finestra, gia' detta"])
    def test_la_raccolta_dell_altra_edizione_che_resta_la_dice_un_avviso_solo(self, banco, monkeypatch, tmp_path, capsys, dove):
        """Revisione della 10.19.13 (issue 66, decisione di Gabriele del 4
        novembre 2026). La nuova edizione, senza partite in PGN, trova la
        raccolta della prima, e il cestino non la prende, come su un disco
        senza cestino: la copia va nella cartella d'archivio della prima, la
        raccolta resta dov'e', e lo dice soltanto l'avviso della guardia.
        Fino ad allora lo seguiva quello della raccolta rimasta, che la
        chiamava raccolta del torneo e diceva che il torneo non aveva piu'
        partite in PGN; la finestra non lo diceva gia' piu'. Se la finestra
        ha gia' detto la guardia, e passa la raccolta fra le sue rimaste, la
        finalizzazione non dice niente, e non riprova il cestino."""
        import config
        from db_players import load_players_db
        from omonimi import _chiave_del_percorso
        from ui import finalize_tournament

        cartella_prima, contenuto = _prima_edizione_con_la_raccolta_lasciata()
        lasciata = config.user_data_path(RACCOLTA)
        ricevuti = _cestino_finto(monkeypatch, str(tmp_path / "cestino"), prende=False)
        avvisi = []

        if dove == "console":
            assert _finalizza_in_console(banco) is True
            detti = [capsys.readouterr().out]
        else:
            rimaste = {_chiave_del_percorso(lasciata)} if dove != "finestra" else None
            assert finalize_tournament(copy.deepcopy(banco.torneo), load_players_db(), banco.file_torneo, avvisi, rimaste) is True
            detti = [a for a in avvisi if RACCOLTA in a]

        assert _leggi_byte(lasciata) == contenuto
        assert _leggi_byte(os.path.join(cartella_prima, RACCOLTA)) == contenuto
        assert RACCOLTA not in os.listdir(_cartella_archivio())
        if dove == "finestra, gia' detta":
            assert ricevuti == []
            assert detti == []
            return
        assert ricevuti == [os.path.normcase(os.path.abspath(lasciata))]
        cartella = os.path.dirname(lasciata)
        archivio = os.path.join("Closed Tournaments", "2026", "06 Giugno", NOME)
        frase = (
            f"Nella cartella {cartella} c'era la raccolta delle partite {RACCOLTA} del torneo {NOME}, concluso e archiviato nella cartella {archivio}: il torneo {NOME} l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
            f"Una copia identica, riletta, adesso è nella cartella d'archivio di quel torneo. Quella della cartella {cartella} non è andata nel cestino, e resta dov'è: la copia nella cartella d'archivio basta, e se vuoi la puoi cancellare tu."
        )
        if dove == "finestra":
            assert detti == [frase]
        else:
            assert detti[0].count(frase) == 1
            assert "non ha più partite in PGN" not in detti[0]

    def test_la_raccolta_rimasta_del_torneo_gia_detta_dalla_finestra_ha_il_suo_avviso(self, banco, monkeypatch, tmp_path):
        """Revisione della 10.19.13 (issue 66). Il torneo non ha piu'
        partite in PGN, e la finestra passa fra le sue rimaste la raccolta
        del torneo stesso, che il suo cestino non ha preso. Non e' la
        raccolta di un'altra edizione: la finalizzazione non riprova il
        cestino, la raccolta resta dov'e' e non va in archivio, e l'avviso
        della raccolta rimasta lo dice ancora. Soltanto per la raccolta di
        un'altra edizione, che la guardia ha riconosciuto, basta l'avviso
        della guardia: la finestra, che la raccolta rimasta l'ha gia' detta,
        non la ripete, ma la finalizzazione dice anche che non va in
        archivio."""
        import config
        from db_players import load_players_db
        from omonimi import _chiave_del_percorso
        from ui import finalize_tournament

        raccolta = config.user_data_path(RACCOLTA)
        contenuto = _raccolta_di(PGN_DELLA_PROVA)
        with open(raccolta, "wb") as f:
            f.write(contenuto)
        ricevuti = _cestino_finto(monkeypatch, str(tmp_path / "cestino"), prende=False)
        avvisi = []
        rimaste = {_chiave_del_percorso(raccolta)}

        assert finalize_tournament(copy.deepcopy(banco.torneo), load_players_db(), banco.file_torneo, avvisi, rimaste) is True

        assert ricevuti == []
        assert _leggi_byte(raccolta) == contenuto
        assert RACCOLTA not in os.listdir(_cartella_archivio())
        assert [a for a in avvisi if RACCOLTA in a] == [
            f"Il torneo {NOME} non ha più partite in PGN, e la sua raccolta delle partite {RACCOLTA}, nella cartella {os.path.dirname(raccolta)}, doveva andare nel cestino di Windows, che non l'ha presa, per esempio perché quel disco non ha il cestino. Resta dov'è, con le partite di prima: Tornello non la cancella per sempre. Non va in archivio con il torneo."
        ]

    def test_con_il_nome_della_raccolta_della_sua_edizione(self, banco, monkeypatch, tmp_path):
        """Revisione della 10.19.13. La nuova edizione si chiama coppa_prova,
        la prima Coppa_Prova: la raccolta della prima va nella sua cartella
        d'archivio con il nome che le da' la prima, e per il ripristino della
        prima non e' un file estraneo. Fino ad allora prendeva il nome della
        raccolta della nuova edizione, con le minuscole."""
        from copie_di_sicurezza import _file_estranei

        cartella_prima, contenuto = _prima_edizione_con_la_raccolta_lasciata()
        _cestino_finto(monkeypatch, str(tmp_path / "cestino"))
        banco.torneo["name"] = NOME.lower()
        _scrivi(banco.file_torneo, banco.torneo)

        assert _finalizza_in_console(banco) is True

        assert sorted(os.listdir(cartella_prima)) == [RACCOLTA, f"Tornello - {NOME}.json"]
        assert _leggi_byte(os.path.join(cartella_prima, RACCOLTA)) == contenuto
        assert _file_estranei(cartella_prima, NOME, f"Tornello - {NOME}.json") == []

    def test_con_il_nome_dell_edizione_rinominata(self, banco, monkeypatch, tmp_path):
        """La prima edizione, nata Coppa_Prova e rinominata Beta da Dati, e'
        archiviata nel file Tornello - Coppa_Prova.json, e nella cartella del
        programma e' rimasta la sua raccolta con il nome di prima. La nuova
        Coppa_Prova la riconosce per il nome del file, e la raccolta va nella
        cartella di Beta come Beta - raccolta partite.pgn, il nome che Beta
        le da'. Fino alla revisione della 10.19.13 ci andava con il nome
        Coppa_Prova, e per il ripristino di Beta era un file estraneo."""
        import config
        import ui
        from copie_di_sicurezza import _file_estranei

        prima = copy.deepcopy(_torneo_finito())
        prima.update(name="Beta", start_date="2026-06-01", end_date="2026-06-02", concluded=True)
        prima["rounds"][0]["matches"][0]["pgn"] = PGN_DELLA_PRIMA
        cartella_prima = os.path.join(ui.ARCHIVED_TOURNAMENTS_DIR, "2026", "06 Giugno", "Beta")
        os.makedirs(cartella_prima)
        _scrivi(os.path.join(cartella_prima, f"Tornello - {NOME}.json"), prima)
        contenuto = _raccolta_di(PGN_DELLA_PRIMA)
        with open(config.user_data_path(RACCOLTA), "wb") as f:
            f.write(contenuto)
        _cestino_finto(monkeypatch, str(tmp_path / "cestino"))

        assert _finalizza_in_console(banco) is True

        assert sorted(os.listdir(cartella_prima)) == ["Beta - raccolta partite.pgn", f"Tornello - {NOME}.json"]
        assert _leggi_byte(os.path.join(cartella_prima, "Beta - raccolta partite.pgn")) == contenuto
        assert _file_estranei(cartella_prima, "Beta", f"Tornello - {NOME}.json") == []


class TestRaccoltaRimastaAllaFinalizzazione:
    """Revisione della 10.19.13 (issue 66). La finestra passa alla
    finalizzazione le raccolte che il suo cestino non ha preso: una rimasta,
    se ha ancora partite che il torneo non ha, prima di essere sostituita
    dalla raccolta del torneo va nella cartella backup, come nei salvataggi
    della finestra. Una raccolta che non si puo'
    scrivere, per esempio tenuta aperta da un altro programma, lo dice un
    avviso: fino ad allora l'archivio restava senza raccolta, e l'errore
    andava soltanto sulla console, che la finestra non mostra."""

    @pytest.mark.parametrize("riesce", [True, False], ids=["copia riuscita", "copia non riuscita"])
    def test_la_raccolta_rimasta_va_nella_cartella_backup(self, banco, monkeypatch, riesce):
        import config
        import utils
        from db_players import load_players_db
        from omonimi import _chiave_del_percorso
        from ui import finalize_tournament

        raccolta = config.user_data_path(RACCOLTA)
        rimasta = _raccolta_di(PGN_DELLA_PRIMA)
        with open(raccolta, "wb") as f:
            f.write(rimasta)
        banco.torneo["rounds"][0]["matches"][0]["pgn"] = PGN_DELLA_PROVA
        _scrivi(banco.file_torneo, banco.torneo)
        if not riesce:
            vera = utils.copia_di_sicurezza
            monkeypatch.setattr(utils, "copia_di_sicurezza", lambda p, *a, **k: None if p.endswith(".pgn") else vera(p, *a, **k))
        avvisi = []

        esito = finalize_tournament(copy.deepcopy(banco.torneo), load_players_db(), banco.file_torneo, avvisi, {_chiave_del_percorso(raccolta)})

        assert esito is True
        copie = _copie(banco.backup, "pre_sostituzione_raccolta")
        detti = [a for a in avvisi if RACCOLTA in a]
        if riesce:
            assert [_leggi_byte(c) for c in copie] == [rimasta]
            assert _leggi_byte(os.path.join(_cartella_archivio(), RACCOLTA)) == _raccolta_di(PGN_DELLA_PROVA)
            assert not os.path.exists(raccolta)
            assert detti == []
        else:
            cartella = os.path.dirname(raccolta)
            assert copie == []
            assert _leggi_byte(raccolta) == rimasta
            assert RACCOLTA not in os.listdir(_cartella_archivio())
            assert detti == [
                f"La raccolta delle partite {RACCOLTA}, nella cartella {cartella}, ha partite che il torneo {NOME} non ha: prima di sostituirla con la raccolta nuova Tornello doveva metterne una copia nella cartella backup, e la copia non è riuscita. Resta com'è, e la raccolta nuova non è stata scritta.\n"
                f"Non va in archivio con il torneo, e nella cartella {cartella} resta quella che c'era prima, che non ha le partite del torneo come sono alla fine: se non ti serve più, spostala o cancellala tu. Le partite del torneo restano nel suo file, in archivio."
            ]

    @pytest.mark.parametrize(
        ("di_prima", "con_la_copia"),
        [((PGN_DELLA_PRIMA, PGN_DELLA_PROVA), True), ((PGN_DELLA_PROVA, PGN_DELLA_PRIMA), True), ((PGN_DELLA_PROVA,), False)],
        ids=["con una partita che il torneo non ha", "con la partita che il torneo non ha dopo una sua", "con le sole partite del torneo"],
    )
    def test_dalla_console_la_raccolta_con_partite_che_il_torneo_non_ha_va_nella_cartella_backup(self, banco, di_prima, con_la_copia):
        """Revisione della 10.19.13 (decisione di Gabriele del 4 novembre
        2026). La finalizzazione nella versione a riga di comando non ha
        raccolte rimaste da ricordare, e usa la regola dell'apertura nella
        finestra: la raccolta al posto di quella del torneo, che ha una
        partita che il torneo non ha, va nella cartella backup prima di
        essere sostituita, e in archivio va quella del torneo. Una raccolta
        con le sole partite del torneo, qui la prima, come quella di un
        torneo che ha poi una partita in PGN in piu', si sostituisce senza
        copie. Fino ad allora la console la sostituiva sempre senza copia."""
        import config

        raccolta = config.user_data_path(RACCOLTA)
        vecchia = _raccolta_di(*di_prima)
        with open(raccolta, "wb") as f:
            f.write(vecchia)
        banco.torneo["rounds"][0]["matches"][0]["pgn"] = PGN_DELLA_PROVA
        banco.torneo["rounds"][0]["matches"][1]["pgn"] = TestEdizioneRinominataDaDati.PGN_SECONDA
        _scrivi(banco.file_torneo, banco.torneo)

        assert _finalizza_in_console(banco) is True

        copie = _copie(banco.backup, "pre_sostituzione_raccolta")
        assert [_leggi_byte(c) for c in copie] == ([vecchia] if con_la_copia else [])
        attesa =_raccolta_di(PGN_DELLA_PROVA, TestEdizioneRinominataDaDati.PGN_SECONDA)
        assert _leggi_byte(os.path.join(_cartella_archivio(), RACCOLTA)) == attesa
        assert not os.path.exists(raccolta)

    @pytest.mark.parametrize("dove", ["finestra", "console"])
    def test_la_raccolta_che_non_si_scrive_lo_dice_un_avviso(self, banco, capsys, dove):
        """La raccolta vecchia, in sola lettura come un file tenuto aperto da
        un altro programma, non si riscrive: la finalizzazione va in fondo,
        la raccolta non va in archivio, e un avviso dice che non e' stata
        scritta e dove resta quella vecchia. Dalla proposta 6 del nono giro
        l'avviso dice del motivo soltanto la descrizione, come Permission
        denied, perche' nomina gia' il file e la cartella; la console tiene
        il testo intero, con il numero dell'errore e il percorso."""
        import re
        import stat

        import config

        banco.torneo["rounds"][0]["matches"][0]["pgn"] = PGN_DELLA_PROVA
        _scrivi(banco.file_torneo, banco.torneo)
        raccolta = config.user_data_path(RACCOLTA)
        with open(raccolta, "wb") as f:
            f.write(b"raccolta vecchia")
        os.chmod(raccolta, stat.S_IREAD)
        avvisi = []
        try:
            assert (_finalizza(banco, avvisi) if dove == "finestra" else _finalizza_in_console(banco)) is True
            nell_archivio = os.listdir(_cartella_archivio())
            vecchia = _leggi_byte(raccolta)
        finally:
            os.chmod(raccolta, stat.S_IREAD | stat.S_IWRITE)

        assert RACCOLTA not in nell_archivio
        assert vecchia == b"raccolta vecchia"
        cartella = os.path.dirname(raccolta)
        inizio = f"La raccolta delle partite {RACCOLTA} del torneo {NOME} non si è potuta scrivere nella cartella {cartella}: "
        fine = (
            f"\nNon va in archivio con il torneo, e nella cartella {cartella} resta quella che c'era prima, che non ha le partite del torneo come sono alla fine: "
            "se non ti serve più, spostala o cancellala tu. Le partite del torneo restano nel suo file, in archivio."
        )
        uscita = capsys.readouterr().out
        righe = [r for r in uscita.splitlines() if r.startswith("Errore durante il salvataggio della raccolta PGN: ")]
        assert len(righe) == 1
        trovato = re.fullmatch(r"Errore durante il salvataggio della raccolta PGN: \[(?:WinError|Errno) \d+\] (.+?): '.*'", righe[0])
        assert trovato, righe[0]
        avviso = inizio + trovato.group(1) + fine
        if dove == "finestra":
            assert [a for a in avvisi if RACCOLTA in a] == [avviso]
        else:
            assert uscita.count(avviso) == 1

    @pytest.mark.parametrize("dove", ["finestra", "console"])
    def test_l_errore_senza_descrizione_lo_dice_intero(self, banco, capsys, monkeypatch, dove):
        """Proposta 6 del nono giro. La scrittura della raccolta solleva un
        OSError senza descrizione, come disco pieno: l'avviso della
        finalizzazione dice il testo intero, disco pieno, come la console,
        perche' non c'e' una descrizione da dire al suo posto. Senza il
        ripiego direbbe None."""
        import builtins

        import config
        import omonimi

        banco.torneo["rounds"][0]["matches"][0]["pgn"] = PGN_DELLA_PROVA
        _scrivi(banco.file_torneo, banco.torneo)
        raccolta = config.user_data_path(RACCOLTA)
        vera = builtins.open

        def apri(file, mode="r", *argomenti, **opzioni):
            if "w" in mode and os.path.basename(str(file)) == RACCOLTA:
                raise OSError("disco pieno")
            return vera(file, mode, *argomenti, **opzioni)

        monkeypatch.setattr(omonimi, "open", apri, raising=False)
        avvisi = []

        assert (_finalizza(banco, avvisi) if dove == "finestra" else _finalizza_in_console(banco)) is True

        assert RACCOLTA not in os.listdir(_cartella_archivio())
        cartella = os.path.dirname(raccolta)
        avviso = (
            f"La raccolta delle partite {RACCOLTA} del torneo {NOME} non si è potuta scrivere nella cartella {cartella}: disco pieno"
            "\nNon va in archivio con il torneo. Le partite del torneo restano nel suo file, in archivio."
        )
        uscita = capsys.readouterr().out
        assert "Errore durante il salvataggio della raccolta PGN: disco pieno" in uscita.splitlines()
        if dove == "finestra":
            assert [a for a in avvisi if RACCOLTA in a] == [avviso]
        else:
            assert uscita.count(avviso) == 1
