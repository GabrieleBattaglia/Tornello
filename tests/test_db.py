import json
import os

from db_players import load_players_db


def test_db_migration(tmp_path, monkeypatch):
    # Crea un file DB finto in formato v1 (lista)
    db_file = tmp_path / "Tornello - Players_db.json"
    v1_data = [
        {
            "id": "TEST001",
            "first_name": "Test",
            "last_name": "Player",
            "current_elo": 1500,
            "medals": {"gold": 1},
        }
    ]

    with open(db_file, "w", encoding="utf-8") as f:
        json.dump(v1_data, f)

    # Applica patch a PLAYER_DB_FILE e PLAYER_DB_TXT_FILE nel modulo db_players
    import db_players

    monkeypatch.setattr(db_players, "PLAYER_DB_FILE", str(db_file))
    monkeypatch.setattr(
        db_players, "PLAYER_DB_TXT_FILE", str(tmp_path / "Tornello - Players_DB.txt")
    )

    # Carica il DB, innescando la migrazione
    players = load_players_db()

    # Verifica che il giocatore sia stato caricato
    assert "TEST001" in players
    p = players["TEST001"]

    # Verifica che siano stati inseriti i campi di default v2
    assert p["elo_club"] == 0.0
    assert p["elo_rapid"] == 0.0
    assert p["fide_standard_games"] == 0
    assert p["medals"]["gold"] == 1
    assert p["medals"]["silver"] == 0  # Default v1

    # Leggi il file scritto per confermare che sia in formato v2
    with open(db_file, encoding="utf-8") as f:
        saved_data = json.load(f)

    assert isinstance(saved_data, dict)
    assert saved_data["schema_version"] == 2
    assert len(saved_data["players"]) == 1
    assert saved_data["players"][0]["id"] == "TEST001"


def test_save_players_db_txt_usa_i_nomi_di_campo_giusti(tmp_path, monkeypatch):
    """Il report leggibile deve mostrare i dati FIDE extra, non "N/D" per un
    nome di campo sbagliato. Prima della correzione i campi w_title,
    o_title, foa_title, flag, elo_rapid, elo_blitz e fide_standard_games
    venivano letti con un prefisso "fide_" che non esisteva nel record."""
    import db_players

    db_file = tmp_path / "Tornello - Players_db.json"
    txt_file = tmp_path / "Tornello - Players_DB.txt"
    monkeypatch.setattr(db_players, "PLAYER_DB_FILE", str(db_file))
    monkeypatch.setattr(db_players, "PLAYER_DB_TXT_FILE", str(txt_file))

    giocatore = {
        "id": "TEST001",
        "first_name": "Test",
        "last_name": "Player",
        "current_elo": 1500,
        "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
        "tournaments_played": [],
        "elo_rapid": 1550,
        "elo_blitz": 1480,
        "fide_standard_games": 42,
        "fide_rapid_games": 10,
        "fide_rapid_k": 20,
        "fide_blitz_games": 5,
        "fide_blitz_k": 20,
        "w_title": "WFM",
        "o_title": "AO",
        "foa_title": "AF",
        "flag": "I",
    }

    db_players.save_players_db_txt({"TEST001": giocatore})

    contenuto = txt_file.read_text(encoding="utf-8-sig")
    assert "Elo Rapid: 1550" in contenuto
    assert "Elo Blitz: 1480" in contenuto
    assert "Partite FIDE: 42" in contenuto
    assert "Titoli Extra: WFM, AO, AF" in contenuto
    assert "Flag: I" in contenuto


# Un giocatore come lo restituisce la ricerca nel database FIDE (fide_db).
RECORD_FIDE = {
    "id_fide": 805165,
    "first_name": "Savino",
    "last_name": "Nicolini",
    "federation": "ITA",
    "sex": "M",
    "title": "",
    "w_title": "",
    "o_title": "",
    "foa_title": "",
    "elo_standard": 0,
    "games": 0,
    "k_factor": 0,
    "elo_rapid": 1806,
    "rapid_games": 7,
    "rapid_k": 40,
    "elo_blitz": 0,
    "blitz_games": 0,
    "blitz_k": 0,
    "birth_year": 1960,
    "flag": None,
}


class TestGiocatoreDalDatabaseFide:
    """Dalla 10.13.15 chi si iscrive dalla ricerca FIDE entra anche nel
    database locale, e la scheda e' una sola per la finestra di iscrizione,
    la consultazione del database FIDE e la console."""

    def test_la_scheda_ha_tutti_i_dati_fide(self):
        from db_players import scheda_da_record_fide

        scheda = scheda_da_record_fide(RECORD_FIDE, {"NICSA001": {"id": "NICSA001"}})

        assert scheda["id"] == "NICSA002"
        assert scheda["fide_id_num_str"] == "805165"
        # Senza Elo standard la scheda parte da 1399, non da zero: la
        # finalizzazione di un torneo standard gli sommerebbe la variazione
        # a zero, come faceva la console fino alla 10.13.14.
        assert scheda["current_elo"] == 1399
        assert scheda["elo_rapid"] == 1806
        assert scheda["fide_rapid_k"] == 40
        assert scheda["fide_rapid_games"] == 7
        assert scheda["birth_date"] == "1960-01-01"
        assert (scheda["sex"], scheda["gender"]) == ("m", "M")
        assert scheda["flag"] == ""
        assert scheda["tournaments_played"] == []
        assert scheda["games_played"] == 0
        assert "experienced" not in scheda

    def test_si_aggiunge_e_si_salva(self, tmp_path):
        import config
        from db_players import aggiungi_dal_fide, load_players_db

        giocatori = {}
        scheda, creata = aggiungi_dal_fide(giocatori, RECORD_FIDE)

        assert creata is True
        assert giocatori[scheda["id"]] is scheda
        assert config.PLAYER_DB_FILE.startswith(str(tmp_path))
        assert load_players_db()[scheda["id"]]["fide_id_num_str"] == "805165"

    def test_una_scheda_con_lo_stesso_id_fide_non_si_raddoppia(self):
        from db_players import aggiungi_dal_fide

        esistente = {"id": "NICSA007", "first_name": "Savino", "last_name": "Nicolini", "fide_id_num_str": "805165"}
        giocatori = {"NICSA007": esistente}

        scheda, creata = aggiungi_dal_fide(giocatori, RECORD_FIDE)

        assert (scheda, creata) == (esistente, False)
        assert list(giocatori) == ["NICSA007"]

    def test_un_id_fide_vuoto_o_zero_non_trova_nessuno(self):
        from db_players import scheda_con_lo_stesso_id_fide

        giocatori = {"A": {"fide_id_num_str": "0"}, "B": {"fide_id_num_str": ""}}
        assert scheda_con_lo_stesso_id_fide(giocatori, "0") is None
        assert scheda_con_lo_stesso_id_fide(giocatori, "") is None
        assert scheda_con_lo_stesso_id_fide(giocatori, None) is None

    def test_se_il_database_non_si_salva_il_giocatore_non_nasce(self, monkeypatch):
        import db_players

        monkeypatch.setattr(db_players, "save_players_db", lambda giocatori: False)
        giocatori = {}

        assert db_players.aggiungi_dal_fide(giocatori, RECORD_FIDE) == (None, False)
        assert giocatori == {}

    def test_crea_nuovo_giocatore_senza_salvataggio_non_lo_crea(self, monkeypatch):
        """Fino alla 10.13.14 il giocatore restava in memoria e la console lo
        iscriveva, mentre il database sul disco non lo aveva."""
        import db_players

        monkeypatch.setattr(db_players, "save_players_db", lambda giocatori: False)
        giocatori = {}

        nuovo = db_players.crea_nuovo_giocatore_nel_db(
            giocatori, "Mario", "Rossi", 1500, "", "m", "ITA", "0", None, False, silent=True
        )

        assert nuovo is None
        assert giocatori == {}


class TestFattoreKDelGiocatoreDalFide:
    """Dalla 10.13.33 un giocatore importato dal database FIDE senza un
    fattore K FIDE valido, come RECORD_FIDE, senza rating standard e con
    k_factor 0, ha K 40, come un giocatore nuovo con meno di trenta partite
    (B.02, articolo 8.3.3), da qualunque strada venga. Fino alla 10.13.32 la
    console aggiungeva experienced alla scheda, e il suo K era 20."""

    def test_senza_k_fide_valido_il_k_e_40(self):
        from db_players import scheda_da_record_fide
        from stats import get_k_factor

        scheda = scheda_da_record_fide(RECORD_FIDE, {})

        assert get_k_factor(scheda, "2026-09-26") == 40

    def test_con_un_k_fide_valido_vale_quello(self):
        from db_players import scheda_da_record_fide
        from stats import get_k_factor

        scheda = scheda_da_record_fide(dict(RECORD_FIDE, k_factor=20, elo_standard=1850, games=120), {})

        assert get_k_factor(scheda, "2026-09-26") == 20

    def test_la_scheda_non_si_puo_cambiare_strada_facendo(self):
        """aggiungi_dal_fide non accetta piu' campi da aggiungere alla
        scheda, e le tre strade, la finestra di iscrizione, la consultazione
        del database FIDE e la console, la chiamano con il database e il
        record soltanto: la scheda, e con lei il K, e' una sola."""
        import ast
        import inspect

        from db_players import aggiungi_dal_fide

        cartella_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")

        assert list(inspect.signature(aggiungi_dal_fide).parameters) == ["players_db", "record"]
        chiamate = {}
        for relativo in (
            "ui.py",
            os.path.join("gui", "dialogs", "player_enrollment_dialog.py"),
            os.path.join("gui", "dialogs", "fide_query_dialog.py"),
        ):
            with open(os.path.join(cartella_src, relativo), encoding="utf-8") as f:
                albero = ast.parse(f.read())
            chiamate[relativo] = [
                (len(nodo.args), len(nodo.keywords))
                for nodo in ast.walk(albero)
                if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", None) == "aggiungi_dal_fide"
            ]
        assert chiamate == {relativo: [(2, 0)] for relativo in chiamate}


class TestSchedaDalTorneo:
    """La scheda che la finalizzazione crea, dalla 10.13.16, per un iscritto
    che il database non ha: con i dati che il torneo ha gia' di lui."""

    def test_i_dati_del_giocatore_del_torneo(self):
        from db_players import scheda_dal_torneo

        giocatore = {
            "id": "FIDE_552017923",
            "first_name": "Augusto",
            "last_name": "Di Folca",
            "initial_elo": 1399.0,
            "current_elo": 1399.0,
            "elo_rapid": 1806,
            "elo_blitz": 0,
            "elo_club": None,
            "fide_k_factor": 0,
            "fide_rapid_k": 40,
            "fide_id_num_str": "552017923",
            "birth_date": "1970-01-01",
            "sex": "m",
            "federation": "ITA",
            "flag": None,
            "points": 2.0,
            "results_history": [{"round": 1}],
        }

        scheda = scheda_dal_torneo(giocatore)

        assert scheda["id"] == "FIDE_552017923"
        assert (scheda["first_name"], scheda["last_name"]) == ("Augusto", "Di Folca")
        assert (scheda["current_elo"], scheda["elo_rapid"], scheda["elo_club"]) == (1399.0, 1806, 0)
        assert (scheda["fide_k_factor"], scheda["fide_rapid_k"]) == (0, 40)
        assert scheda["birth_date"] == "1970-01-01"
        assert scheda["fide_id_num_str"] == "552017923"
        assert scheda["flag"] == ""
        assert (scheda["games_played"], scheda["tournaments_played"]) == (0, [])
        assert scheda["medals"] == {"gold": 0, "silver": 0, "bronze": 0, "wood": 0}
        for chiave in ("points", "results_history", "initial_elo"):
            assert chiave not in scheda

    def test_la_data_di_ripiego_del_torneo_non_e_una_data(self):
        """models.Player scrive 1900-01-01 quando la data non la conosce."""
        from db_players import scheda_dal_torneo

        scheda = scheda_dal_torneo({"id": "X", "birth_date": "1900-01-01", "fide_id_num_str": "0"})
        assert scheda["birth_date"] is None
        assert scheda["fide_id_num_str"] == ""


def lettura_bloccata(monkeypatch, percorso, volte=1):
    """Le prime aperture in lettura del database dei giocatori rispondono
    PermissionError, come un file tenuto per un attimo da Dropbox o
    dall'antivirus; le altre aprono il file vero. La usano anche le prove
    della finalizzazione e delle finestre."""
    import builtins
    import os

    import db_players

    vero_open = builtins.open
    rimaste = {"volte": volte}

    def finto_open(file, mode="r", *a, **k):
        if rimaste["volte"] and "r" in mode and os.path.abspath(str(file)) == os.path.abspath(percorso):
            rimaste["volte"] -= 1
            raise PermissionError(13, "Il file è in uso da un altro processo", str(file))
        return vero_open(file, mode, *a, **k)

    monkeypatch.setattr(db_players, "open", finto_open, raising=False)


def _database_con_giocatori(numero=30):
    """Un database dei giocatori sul disco, nella cartella della prova, con
    numero schede; restituisce i suoi byte."""
    import config

    giocatori = [
        {"id": f"SOCIO{i:02d}", "first_name": f"Nome{i}", "last_name": "Socio", "current_elo": 1500.0, "games_played": 40, "tournaments_played": []}
        for i in range(numero)
    ]
    with open(config.PLAYER_DB_FILE, "w", encoding="utf-8") as f:
        json.dump({"schema_version": 2, "players": giocatori}, f)
    with open(config.PLAYER_DB_FILE, "rb") as f:
        return f.read()


def _byte_del_database():
    import config

    with open(config.PLAYER_DB_FILE, "rb") as f:
        return f.read()


class TestDatabaseCheNonSiLegge:
    """Dalla 10.13.15 e dalla 10.13.16 un database dei giocatori che c'e' ma non si legge,
    bloccato per un attimo o rovinato, arriva come DatabaseNonLetto: vuoto
    come prima, ma save_players_db rifiuta di scriverlo. Fino ad allora era
    un dizionario vuoto qualunque, e il primo salvataggio sostituiva sul
    disco il database del circolo con le sole schede aggiunte: con la
    finalizzazione della 10.13.16 i soli iscritti del torneo, con
    l'iscrizione FIDE della 10.13.15 il solo giocatore iscritto."""

    def test_il_file_che_non_c_e_e_un_database_vuoto_che_si_salva(self):
        from db_players import database_non_letto, save_players_db

        giocatori = load_players_db()

        assert giocatori == {} and not database_non_letto(giocatori)
        giocatori["X"] = {"id": "X"}
        assert save_players_db(giocatori) is True

    def test_la_lettura_bloccata_da_un_database_che_non_si_scrive(self, monkeypatch, capsys):
        import config
        from db_players import database_non_letto, save_players_db

        prima = _database_con_giocatori()
        lettura_bloccata(monkeypatch, config.PLAYER_DB_FILE)

        giocatori = load_players_db()

        assert giocatori == {} and database_non_letto(giocatori)
        assert "in uso da un altro processo" in giocatori.errore
        giocatori["NUOVO"] = {"id": "NUOVO"}
        capsys.readouterr()
        assert save_players_db(giocatori) is False
        assert _byte_del_database() == prima
        assert capsys.readouterr().out.startswith(
            "Il database dei giocatori, Tornello - Players_db.json, c'è ma non si è potuto leggere: "
        )
        # Il blocco e' passato: la lettura successiva trova tutti.
        assert len(load_players_db()) == 30

    def test_il_json_rovinato_da_un_database_che_non_si_scrive(self):
        import config
        from db_players import database_non_letto, save_players_db

        intero = _database_con_giocatori()
        with open(config.PLAYER_DB_FILE, "wb") as f:
            f.write(intero[: len(intero) // 2])

        giocatori = load_players_db()

        assert database_non_letto(giocatori)
        giocatori["X"] = {"id": "X"}
        assert save_players_db(giocatori) is False
        assert _byte_del_database() == intero[: len(intero) // 2]

    def test_l_iscrizione_fide_non_riscrive_il_database(self, monkeypatch):
        import config
        from db_players import aggiungi_dal_fide

        prima = _database_con_giocatori()
        lettura_bloccata(monkeypatch, config.PLAYER_DB_FILE)
        giocatori = load_players_db()

        assert aggiungi_dal_fide(giocatori, RECORD_FIDE) == (None, False)
        assert giocatori == {}
        assert _byte_del_database() == prima

    def test_nuovo_giocatore_non_riscrive_il_database(self, monkeypatch):
        import config
        from db_players import crea_nuovo_giocatore_nel_db

        prima = _database_con_giocatori()
        lettura_bloccata(monkeypatch, config.PLAYER_DB_FILE)
        giocatori = load_players_db()

        nuovo = crea_nuovo_giocatore_nel_db(giocatori, "Mario", "Rossi", 1500, "", "m", "ITA", "0", None, False, silent=True)

        assert nuovo is None
        assert giocatori == {}
        assert _byte_del_database() == prima


class TestSchedaNelDatabase:
    """Dalla 10.13.16 la finalizzazione cerca la scheda di un iscritto per
    identificativo e, se non la trova, per identificativo FIDE: un iscritto
    FIDE_<id> che nel frattempo e' entrato nel database con un altro
    identificativo non diventa un doppione."""

    def test_prima_l_identificativo_poi_l_identificativo_fide(self):
        from db_players import scheda_nel_database, scheda_per_la_finalizzazione

        vera = {"id": "NICSA001", "fide_id_num_str": "805165", "experienced": True, "games_played": 200}
        omonima = {"id": "FIDE_805165", "fide_id_num_str": "1"}
        giocatori = {"NICSA001": vera}

        assert scheda_nel_database({"id": "FIDE_805165", "fide_id_num_str": "805165"}, giocatori) is vera
        assert scheda_nel_database({"id": "FIDE_805165", "fide_id_num_str": 805165}, giocatori) is vera
        assert scheda_nel_database({"id": "ALTRO", "fide_id_num_str": "0"}, giocatori) is None
        giocatori["FIDE_805165"] = omonima
        assert scheda_nel_database({"id": "FIDE_805165", "fide_id_num_str": "805165"}, giocatori) is omonima
        assert scheda_per_la_finalizzazione({"id": "NUOVO", "first_name": "A", "fide_id_num_str": ""}, giocatori)["id"] == "NUOVO"
