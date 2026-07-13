"""Test per il modulo fide_db (database FIDE SQLite con FTS5)."""

import os
import pytest
from fide_db import (
    _build_fts_query,
    _extract_first_term,
    _relevance_sort_key,
    _sanitize_fts_term,
    bulk_insert_players,
    cleanup_legacy_json,
    create_fide_db,
    fide_db_exists,
    get_player_by_fide_id,
    get_player_count,
    search_players,
    search_players_by_name,
)


# -- Fixtures ---------------------------------------------------------------


SAMPLE_PLAYERS = [
    {
        "fide_id": 1503014,
        "first_name": "Magnus",
        "last_name": "Carlsen",
        "federation": "NOR",
        "sex": "M",
        "title": "GM",
        "w_title": "",
        "o_title": "",
        "foa_title": "",
        "elo_standard": 2830,
        "games": 50,
        "k_factor": 10,
        "elo_rapid": 2830,
        "rapid_games": 20,
        "rapid_k": 10,
        "elo_blitz": 2886,
        "blitz_games": 30,
        "blitz_k": 10,
        "birth_year": 1990,
        "flag": None,
    },
    {
        "fide_id": 4100018,
        "first_name": "Fabiano",
        "last_name": "Caruana",
        "federation": "USA",
        "sex": "M",
        "title": "GM",
        "w_title": "",
        "o_title": "",
        "foa_title": "",
        "elo_standard": 2786,
        "games": 40,
        "k_factor": 10,
        "elo_rapid": 2750,
        "rapid_games": 15,
        "rapid_k": 10,
        "elo_blitz": 2770,
        "blitz_games": 25,
        "blitz_k": 10,
        "birth_year": 1992,
        "flag": None,
    },
    {
        "fide_id": 8603677,
        "first_name": "Ding",
        "last_name": "Liren",
        "federation": "CHN",
        "sex": "M",
        "title": "GM",
        "w_title": "",
        "o_title": "",
        "foa_title": "",
        "elo_standard": 2780,
        "games": 35,
        "k_factor": 10,
        "elo_rapid": 2730,
        "rapid_games": 10,
        "rapid_k": 20,
        "elo_blitz": 2788,
        "blitz_games": 18,
        "blitz_k": 10,
        "birth_year": 1992,
        "flag": None,
    },
    {
        "fide_id": 9999999,
        "first_name": "Mario",
        "last_name": "Rossi",
        "federation": "ITA",
        "sex": "M",
        "title": "",
        "w_title": "",
        "o_title": "",
        "foa_title": "",
        "elo_standard": 1800,
        "games": 10,
        "k_factor": 40,
        "elo_rapid": 1750,
        "rapid_games": 5,
        "rapid_k": 40,
        "elo_blitz": 1700,
        "blitz_games": 3,
        "blitz_k": 40,
        "birth_year": 1985,
        "flag": None,
    },
]


@pytest.fixture()
def fide_db_path(tmp_path, monkeypatch):
    """Crea un database FIDE temporaneo e patcha i percorsi."""
    import fide_db

    db_path = str(tmp_path / "fide_ratings.db")
    json_legacy_path = str(tmp_path / "fide_ratings_local.json")

    monkeypatch.setattr(fide_db, "FIDE_DB_LOCAL_FILE", db_path)
    monkeypatch.setattr(fide_db, "FIDE_DB_JSON_LEGACY", json_legacy_path)

    return db_path, json_legacy_path


@pytest.fixture()
def populated_fide_db(fide_db_path):
    """Crea un database FIDE temporaneo e lo popola con dati di test."""
    db_path, json_legacy_path = fide_db_path
    create_fide_db()
    bulk_insert_players(iter(SAMPLE_PLAYERS))
    return db_path, json_legacy_path


# -- Test: Stato del database -----------------------------------------------


class TestFideDbExists:
    def test_returns_false_when_no_file(self, fide_db_path):
        assert fide_db_exists() is False

    def test_returns_false_when_empty_db(self, fide_db_path):
        create_fide_db()
        assert fide_db_exists() is False

    def test_returns_true_when_populated(self, populated_fide_db):
        assert fide_db_exists() is True


class TestCleanupLegacyJson:
    def test_removes_json_file(self, fide_db_path):
        _, json_path = fide_db_path
        with open(json_path, "w") as f:
            f.write("{}")
        assert os.path.exists(json_path)
        result = cleanup_legacy_json()
        assert result is True
        assert not os.path.exists(json_path)

    def test_returns_false_when_no_json(self, fide_db_path):
        result = cleanup_legacy_json()
        assert result is False


class TestGetPlayerCount:
    def test_empty_db(self, fide_db_path):
        assert get_player_count() == 0

    def test_populated_db(self, populated_fide_db):
        assert get_player_count() == len(SAMPLE_PLAYERS)


# -- Test: Creazione e popolazione -------------------------------------------


class TestCreateAndPopulate:
    def test_create_fide_db(self, fide_db_path):
        create_fide_db()
        db_path, _ = fide_db_path
        assert os.path.exists(db_path)

    def test_bulk_insert_returns_count(self, fide_db_path):
        create_fide_db()
        count = bulk_insert_players(iter(SAMPLE_PLAYERS))
        assert count == len(SAMPLE_PLAYERS)

    def test_bulk_insert_progress_callback(self, fide_db_path):
        create_fide_db()
        progress_counts = []
        # Creiamo abbastanza record per triggerare il callback (batch_size=5000)
        many_players = [
            {
                "fide_id": 10000 + i,
                "first_name": f"Test{i}",
                "last_name": f"Player{i}",
                "federation": "TST",
                "sex": "M",
                "title": "",
                "w_title": "",
                "o_title": "",
                "foa_title": "",
                "elo_standard": 1500,
                "games": 0,
                "k_factor": 40,
                "elo_rapid": 0,
                "rapid_games": 0,
                "rapid_k": None,
                "elo_blitz": 0,
                "blitz_games": 0,
                "blitz_k": None,
                "birth_year": 2000,
                "flag": None,
            }
            for i in range(5001)
        ]
        count = bulk_insert_players(
            iter(many_players), progress_callback=lambda c: progress_counts.append(c)
        )
        assert count == 5001
        assert len(progress_counts) >= 1  # Almeno un callback a 5000

    def test_recreate_db_drops_old_data(self, populated_fide_db):
        assert get_player_count() == len(SAMPLE_PLAYERS)
        create_fide_db()  # Ricrea il DB
        assert get_player_count() == 0


# -- Test: Ricerca per ID ---------------------------------------------------


class TestGetPlayerByFideId:
    def test_find_existing_player(self, populated_fide_db):
        player = get_player_by_fide_id(1503014)
        assert player is not None
        assert player["first_name"] == "Magnus"
        assert player["last_name"] == "Carlsen"
        assert player["federation"] == "NOR"
        assert player["elo_standard"] == 2830

    def test_find_by_string_id(self, populated_fide_db):
        player = get_player_by_fide_id("4100018")
        assert player is not None
        assert player["last_name"] == "Caruana"

    def test_not_found(self, populated_fide_db):
        player = get_player_by_fide_id(0)
        assert player is None

    def test_dict_format(self, populated_fide_db):
        """Verifica che il dizionario restituito abbia tutte le chiavi previste."""
        player = get_player_by_fide_id(1503014)
        expected_keys = {
            "id_fide",
            "first_name",
            "last_name",
            "federation",
            "sex",
            "title",
            "w_title",
            "o_title",
            "foa_title",
            "elo_standard",
            "games",
            "k_factor",
            "elo_rapid",
            "rapid_games",
            "rapid_k",
            "elo_blitz",
            "blitz_games",
            "blitz_k",
            "birth_year",
            "flag",
        }
        assert set(player.keys()) == expected_keys


# -- Test: Ricerca per nome -------------------------------------------------


class TestSearchPlayersByName:
    def test_exact_match(self, populated_fide_db):
        results = search_players_by_name("Magnus", "Carlsen")
        assert len(results) == 1
        assert results[0]["id_fide"] == 1503014

    def test_case_insensitive(self, populated_fide_db):
        results = search_players_by_name("magnus", "carlsen")
        assert len(results) == 1

    def test_no_match(self, populated_fide_db):
        results = search_players_by_name("Nonexistent", "Player")
        assert len(results) == 0


# -- Test: Ricerca full-text (FTS5) ------------------------------------------


class TestSearchPlayers:
    def test_search_by_name(self, populated_fide_db):
        results = search_players("carlsen")
        assert len(results) >= 1
        assert any(p["last_name"] == "Carlsen" for p in results)

    def test_search_by_fide_id(self, populated_fide_db):
        results = search_players("1503014")
        assert len(results) == 1
        assert results[0]["last_name"] == "Carlsen"

    def test_search_multi_term(self, populated_fide_db):
        results = search_players("carlsen nor")
        assert len(results) >= 1
        assert results[0]["last_name"] == "Carlsen"

    def test_search_minimum_length(self, populated_fide_db):
        results = search_players("ca")
        assert len(results) == 0  # Sotto i 3 caratteri

    def test_search_empty(self, populated_fide_db):
        results = search_players("")
        assert len(results) == 0

    def test_search_exclude_ids(self, populated_fide_db):
        results = search_players("carlsen", exclude_fide_ids={"1503014"})
        assert all(p["id_fide"] != 1503014 for p in results)

    def test_search_exclude_id_for_id_lookup(self, populated_fide_db):
        results = search_players("1503014", exclude_fide_ids={"1503014"})
        assert len(results) == 0

    def test_search_by_federation(self, populated_fide_db):
        results = search_players("ITA")
        assert len(results) >= 1
        assert any(p["federation"] == "ITA" for p in results)

    def test_search_by_year(self, populated_fide_db):
        """Numeri sono trattati come ID FIDE, non come anno."""
        results = search_players("carlsen 1990")
        assert len(results) >= 1
        assert results[0]["birth_year"] == 1990

    def test_relevance_order_last_name_first(self, populated_fide_db):
        """Il cognome che inizia con il termine deve avere priorità."""
        results = search_players("car")
        if len(results) >= 2:
            # Carlsen e Caruana dovrebbero essere prima di altri
            assert results[0]["last_name"] in ("Carlsen", "Caruana")


# -- Test: Operatori di ricerca ---------------------------------------------


class TestSearchOperators:
    def test_exact_phrase(self, populated_fide_db):
        results = search_players("=Magnus Carlsen")
        assert len(results) >= 1
        assert results[0]["first_name"] == "Magnus"

    def test_exclude_operator(self, populated_fide_db):
        """Cerca 'car' escludendo 'NOR' → Caruana (USA) ma non Carlsen (NOR)."""
        results = search_players("car -NOR")
        carlsen_found = any(p["last_name"] == "Carlsen" for p in results)
        assert not carlsen_found
        caruana_found = any(p["last_name"] == "Caruana" for p in results)
        assert caruana_found

    def test_mandatory_operator(self, populated_fide_db):
        results = search_players("+carlsen")
        assert len(results) >= 1
        assert results[0]["last_name"] == "Carlsen"


# -- Test: Funzioni interne -------------------------------------------------


class TestBuildFtsQuery:
    def test_simple_term(self):
        assert _build_fts_query("carlsen") == "carlsen*"

    def test_multi_term(self):
        assert _build_fts_query("carlsen magnus") == "carlsen* AND magnus*"

    def test_mandatory_term(self):
        assert _build_fts_query("+carlsen") == "carlsen*"

    def test_exclude_term(self):
        result = _build_fts_query("carlsen -nor")
        assert "carlsen*" in result
        assert "NOT" in result
        assert "nor*" in result

    def test_exact_phrase(self):
        assert _build_fts_query("=Magnus Carlsen") == '"Magnus Carlsen"'

    def test_empty(self):
        assert _build_fts_query("") is None

    def test_only_exclusion(self):
        assert _build_fts_query("-carlsen") is None


class TestSanitizeFtsTerm:
    def test_removes_special_chars(self):
        assert _sanitize_fts_term('"test"') == "test"
        assert _sanitize_fts_term("test*") == "test"
        assert _sanitize_fts_term("(test)") == "test"

    def test_preserves_normal_text(self):
        assert _sanitize_fts_term("carlsen") == "carlsen"
        assert _sanitize_fts_term("1503014") == "1503014"


class TestExtractFirstTerm:
    def test_simple(self):
        assert _extract_first_term("carlsen magnus") == "carlsen"

    def test_with_operator(self):
        assert _extract_first_term("+carlsen") == "carlsen"

    def test_exact_phrase(self):
        assert _extract_first_term("=Magnus Carlsen") == "magnus"


class TestRelevanceSortKey:
    def test_last_name_priority(self):
        player = {"last_name": "Carlsen", "first_name": "Magnus"}
        key = _relevance_sort_key(player, "car")
        assert key[0] == 1  # Priorità massima

    def test_first_name_priority(self):
        player = {"last_name": "Test", "first_name": "Carlo"}
        key = _relevance_sort_key(player, "car")
        assert key[0] == 2

    def test_no_match_priority(self):
        player = {"last_name": "Test", "first_name": "Player"}
        key = _relevance_sort_key(player, "car")
        assert key[0] == 3


class TestFideUpdateLocale:
    def test_aggiorna_db_fide_locale_success_and_stats(self, fide_db_path, monkeypatch):
        import io
        import zipfile
        import requests
        from db_players import aggiorna_db_fide_locale
        import db_players

        # 1. Crea uno ZIP mock in memoria contenente un XML FIDE minimale
        xml_content = """<?xml version="1.0" encoding="utf-8"?>
        <playerslist>
            <player>
                <fideid>1503014</fideid>
                <name>Carlsen, Magnus</name>
                <country>NOR</country>
                <sex>M</sex>
                <title>GM</title>
                <rating>2830</rating>
                <games>50</games>
                <k>10</k>
                <birthday>1990</birthday>
            </player>
            <player>
                <fideid>4100018</fideid>
                <name>Caruana, Fabiano</name>
                <country>USA</country>
                <sex>M</sex>
                <title>GM</title>
                <rating>2786</rating>
                <games>40</games>
                <k>10</k>
                <birthday>1992</birthday>
            </player>
        </playerslist>
        """
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("players_list_foa.xml", xml_content)
        zip_bytes = zip_buffer.getvalue()

        # Mock della risposta HTTP di requests
        class MockResponse:
            def __init__(self):
                self.content = zip_bytes
                self.status_code = 200
                self.headers = {"content-length": str(len(zip_bytes))}

            def raise_for_status(self):
                pass

            def iter_content(self, chunk_size=1024):
                # Restituisce i byte in blocchi
                pos = 0
                while pos < len(zip_bytes):
                    chunk = zip_bytes[pos : pos + chunk_size]
                    pos += chunk_size
                    yield chunk

        # Patch di requests.get e dei path del database in db_players
        monkeypatch.setattr(requests, "get", lambda *args, **kwargs: MockResponse())
        monkeypatch.setattr(db_players, "FIDE_DB_LOCAL_FILE", fide_db_path[0])

        # Callback per catturare il progresso
        progress_events = []

        def mock_callback(phase, current, total):
            progress_events.append((phase, current, total))

        # Dizionario per salvare le statistiche
        stats = {}

        # 2. Esegui la funzione
        success = aggiorna_db_fide_locale(
            progress_callback=mock_callback, stats_output=stats
        )

        # 3. Verifiche
        assert success is True
        assert stats["saved_count"] == 2
        assert stats["old_count"] == 0
        assert stats["new_count"] == 2
        assert "download_time" in stats
        assert "processing_time" in stats

        # Verifica che il callback sia stato invocato per entrambe le fasi
        phases = [evt[0] for evt in progress_events]
        assert "download" in phases
        assert "processing" in phases

        # Verifica che i dati siano stati scritti nel DB SQLite
        from fide_db import get_player_by_fide_id
        player = get_player_by_fide_id(1503014)
        assert player is not None
        assert player["last_name"] == "Carlsen"
        assert player["first_name"] == "Magnus"
        assert player["elo_standard"] == 2830
        assert player["birth_year"] == 1990

