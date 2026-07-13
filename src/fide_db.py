"""
Modulo per la gestione del database FIDE locale in formato SQLite.

Fornisce funzionalità di creazione, popolazione, ricerca e consultazione
del database dei rating FIDE, utilizzando SQLite FTS5 per ricerche
full-text veloci. Sostituisce il precedente sistema basato su file JSON
da ~677 MB, riducendo il consumo di RAM a quasi zero e offrendo tempi
di risposta nell'ordine dei millisecondi.
"""

import os
import re
import sqlite3
import builtins

from config import FIDE_DB_LOCAL_FILE, FIDE_DB_JSON_LEGACY

_ = getattr(builtins, "_", lambda s: s)


# ---------------------------------------------------------------------------
# Connessione e conversione righe
# ---------------------------------------------------------------------------


def _get_connection():
    """Apre una connessione al database SQLite FIDE."""
    conn = sqlite3.connect(FIDE_DB_LOCAL_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_dict(row):
    """Converte una sqlite3.Row nel formato dizionario compatibile con il vecchio JSON."""
    return {
        "id_fide": row["fide_id"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "federation": row["federation"],
        "sex": row["sex"],
        "title": row["title"],
        "w_title": row["w_title"],
        "o_title": row["o_title"],
        "foa_title": row["foa_title"],
        "elo_standard": row["elo_standard"],
        "games": row["games"],
        "k_factor": row["k_factor"],
        "elo_rapid": row["elo_rapid"],
        "rapid_games": row["rapid_games"],
        "rapid_k": row["rapid_k"],
        "elo_blitz": row["elo_blitz"],
        "blitz_games": row["blitz_games"],
        "blitz_k": row["blitz_k"],
        "birth_year": row["birth_year"],
        "flag": row["flag"],
    }


# ---------------------------------------------------------------------------
# Stato del database
# ---------------------------------------------------------------------------


def fide_db_exists():
    """Verifica se il database SQLite FIDE esiste e contiene dati."""
    if not os.path.exists(FIDE_DB_LOCAL_FILE):
        return False
    try:
        conn = _get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM players")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def cleanup_legacy_json():
    """
    Rimuove il vecchio file JSON FIDE se presente.
    Restituisce True se il file è stato eliminato.
    """
    if os.path.exists(FIDE_DB_JSON_LEGACY):
        try:
            os.remove(FIDE_DB_JSON_LEGACY)
            return True
        except Exception:
            return False
    return False


def get_player_count():
    """Restituisce il numero totale di giocatori nel database FIDE."""
    try:
        conn = _get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM players")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Creazione e popolazione del database
# ---------------------------------------------------------------------------


def create_fide_db():
    """Crea un database FIDE SQLite vuoto, eliminando eventuali tabelle preesistenti."""
    conn = _get_connection()
    conn.execute("DROP TABLE IF EXISTS players_fts")
    conn.execute("DROP TABLE IF EXISTS players")
    conn.executescript(
        """
        CREATE TABLE players (
            fide_id     INTEGER PRIMARY KEY,
            first_name  TEXT NOT NULL DEFAULT '',
            last_name   TEXT NOT NULL DEFAULT '',
            federation  TEXT NOT NULL DEFAULT '',
            sex         TEXT NOT NULL DEFAULT '',
            title       TEXT NOT NULL DEFAULT '',
            w_title     TEXT NOT NULL DEFAULT '',
            o_title     TEXT NOT NULL DEFAULT '',
            foa_title   TEXT NOT NULL DEFAULT '',
            elo_standard INTEGER NOT NULL DEFAULT 0,
            games       INTEGER NOT NULL DEFAULT 0,
            k_factor    INTEGER,
            elo_rapid   INTEGER NOT NULL DEFAULT 0,
            rapid_games INTEGER NOT NULL DEFAULT 0,
            rapid_k     INTEGER,
            elo_blitz   INTEGER NOT NULL DEFAULT 0,
            blitz_games INTEGER NOT NULL DEFAULT 0,
            blitz_k     INTEGER,
            birth_year  INTEGER,
            flag        TEXT
        );

        CREATE INDEX idx_last_name  ON players(last_name  COLLATE NOCASE);
        CREATE INDEX idx_first_name ON players(first_name COLLATE NOCASE);
        CREATE INDEX idx_federation ON players(federation);

        CREATE VIRTUAL TABLE players_fts USING fts5(
            search_text,
            tokenize='unicode61 remove_diacritics 2'
        );
    """
    )
    conn.commit()
    conn.close()


def bulk_insert_players(players_iter, progress_callback=None):
    """
    Inserisce i giocatori dal generatore fornito nel database SQLite.

    Args:
        players_iter: iteratore che produce dizionari con le chiavi del record FIDE
                      (fide_id, first_name, last_name, federation, sex, title, ...).
        progress_callback: funzione opzionale chiamata ogni 5000 record con il
                           conteggio corrente come argomento.

    Returns:
        Numero totale di giocatori inseriti.
    """
    conn = _get_connection()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-64000")  # 64 MB di cache

    insert_sql = """
        INSERT OR REPLACE INTO players
        (fide_id, first_name, last_name, federation, sex, title,
         w_title, o_title, foa_title,
         elo_standard, games, k_factor,
         elo_rapid, rapid_games, rapid_k,
         elo_blitz, blitz_games, blitz_k,
         birth_year, flag)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    fts_sql = "INSERT INTO players_fts(rowid, search_text) VALUES (?, ?)"

    batch_size = 5000
    count = 0
    batch_p = []
    batch_f = []

    for p in players_iter:
        fide_id = p["fide_id"]
        first_name = p.get("first_name", "")
        last_name = p.get("last_name", "")
        federation = p.get("federation", "")
        birth_year = p.get("birth_year")

        batch_p.append(
            (
                fide_id,
                first_name,
                last_name,
                federation,
                p.get("sex", ""),
                p.get("title", ""),
                p.get("w_title", ""),
                p.get("o_title", ""),
                p.get("foa_title", ""),
                p.get("elo_standard", 0),
                p.get("games", 0),
                p.get("k_factor"),
                p.get("elo_rapid", 0),
                p.get("rapid_games", 0),
                p.get("rapid_k"),
                p.get("elo_blitz", 0),
                p.get("blitz_games", 0),
                p.get("blitz_k"),
                birth_year,
                p.get("flag"),
            )
        )

        search_text = (
            f"{first_name} {last_name} {birth_year or ''} {federation} {fide_id}"
        )
        batch_f.append((fide_id, search_text))

        count += 1
        if count % batch_size == 0:
            conn.executemany(insert_sql, batch_p)
            conn.executemany(fts_sql, batch_f)
            batch_p.clear()
            batch_f.clear()
            if progress_callback:
                progress_callback(count)

    # Inserisce gli ultimi record rimasti nel batch
    if batch_p:
        conn.executemany(insert_sql, batch_p)
        conn.executemany(fts_sql, batch_f)

    conn.commit()
    conn.execute("PRAGMA synchronous=FULL")
    conn.close()
    return count


# ---------------------------------------------------------------------------
# Ricerca giocatori
# ---------------------------------------------------------------------------


def get_player_by_fide_id(fide_id):
    """Restituisce i dati di un giocatore dato il suo ID FIDE, o None se non trovato."""
    try:
        conn = _get_connection()
        cursor = conn.execute(
            "SELECT * FROM players WHERE fide_id = ?", (int(fide_id),)
        )
        row = cursor.fetchone()
        conn.close()
        return _row_to_dict(row) if row else None
    except Exception:
        return None


def search_players_by_name(first_name, last_name):
    """
    Cerca giocatori per corrispondenza esatta di nome e cognome (case-insensitive).
    Utilizzato dalla sincronizzazione del database personale con il DB FIDE.
    """
    try:
        conn = _get_connection()
        cursor = conn.execute(
            "SELECT * FROM players "
            "WHERE first_name = ? COLLATE NOCASE AND last_name = ? COLLATE NOCASE",
            (first_name, last_name),
        )
        results = [_row_to_dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    except Exception:
        return []


def search_players(query, limit=None, exclude_fide_ids=None):
    """
    Cerca giocatori FIDE usando la stringa di ricerca con supporto operatori.

    Operatori supportati (compatibili con ``match_player_query`` in ``utils.py``):
      * termine semplice – tutti i termini devono essere presenti (AND implicito).
      * ``+termine`` – obbligatorio (equivalente al termine semplice).
      * ``-termine`` – escludi i risultati che contengono il termine.
      * ``=frase esatta`` – ricerca frase esatta.

    Args:
        query: stringa di ricerca.
        limit: numero massimo di risultati da restituire (None per nessun limite).
        exclude_fide_ids: set opzionale di ID FIDE (stringhe) da escludere.

    Returns:
        Lista di dizionari giocatore ordinati per rilevanza.
    """
    if not query or len(query.strip()) < 3:
        return []

    query = query.strip()

    # Ricerca per ID FIDE esatto (stringa numerica)
    if query.isdigit():
        player = get_player_by_fide_id(query)
        if player:
            fide_id_str = str(player["id_fide"])
            if exclude_fide_ids and fide_id_str in exclude_fide_ids:
                return []
            return [player]
        return []

    # Costruisci ed esegui query FTS5
    fts_query = _build_fts_query(query)
    results = []

    if fts_query:
        try:
            conn = _get_connection()
            sql = (
                "SELECT p.* FROM players p "
                "JOIN players_fts fts ON fts.rowid = p.fide_id "
                "WHERE players_fts MATCH ? "
                "ORDER BY fts.rank"
            )
            params = [fts_query]
            if limit is not None:
                sql += " LIMIT ?"
                fetch_limit = limit * 3 if exclude_fide_ids else limit
                params.append(fetch_limit)

            cursor = conn.execute(sql, params)
            for row in cursor:
                player = _row_to_dict(row)
                if exclude_fide_ids and str(player["id_fide"]) in exclude_fide_ids:
                    continue
                results.append(player)
                if limit is not None and len(results) >= limit:
                    break
            conn.close()
        except Exception:
            # Fallback a ricerca LIKE se FTS5 non funziona
            results = _search_like_fallback(query, limit, exclude_fide_ids)

    # Applica ordinamento per rilevanza (cognomi che iniziano col primo termine prima)
    if results:
        first_term = _extract_first_term(query)
        if first_term:
            results.sort(key=lambda p: _relevance_sort_key(p, first_term))

    return results


# ---------------------------------------------------------------------------
# Funzioni interne di supporto alla ricerca
# ---------------------------------------------------------------------------


def _sanitize_fts_term(term):
    """Rimuove i caratteri speciali della sintassi FTS5 da un termine di ricerca."""
    return re.sub(r'["\(\)\*\+\-\^\{\}\[\]:!&|]', "", term).strip()


def _build_fts_query(query):
    """
    Costruisce una query FTS5 dalla stringa di ricerca dell'utente.

    Traduce gli operatori di Tornello nel formato FTS5 di SQLite:
      termine    → ``termine*``  (prefix match)
      +termine   → ``termine*``  (prefix match obbligatorio, AND implicito)
      -termine   → ``NOT termine*``
      =frase     → ``"frase"``  (phrase match)
    """
    query = query.strip()

    # Ricerca frase esatta
    if query.startswith("="):
        phrase = _sanitize_fts_term(query[1:].strip())
        return f'"{phrase}"' if phrase else None

    parts = query.split()
    positive = []
    negative = []

    for part in parts:
        if part.startswith("-") and len(part) > 1:
            term = _sanitize_fts_term(part[1:])
            if term:
                negative.append(f"{term}*")
        elif part.startswith("+") and len(part) > 1:
            term = _sanitize_fts_term(part[1:])
            if term:
                positive.append(f"{term}*")
        else:
            term = _sanitize_fts_term(part)
            if term:
                positive.append(f"{term}*")

    if not positive:
        return None

    fts_query = " AND ".join(positive)

    if negative:
        neg_query = " OR ".join(negative)
        fts_query = f"({fts_query}) NOT ({neg_query})"

    return fts_query


def _extract_first_term(query):
    """Estrae il primo termine significativo dalla query per il calcolo della rilevanza."""
    query = query.strip()
    if query.startswith("="):
        parts = query[1:].strip().split()
        return parts[0].lower() if parts else ""
    for part in query.split():
        clean = part.lstrip("+-").lower()
        if clean:
            return clean
    return ""


def _relevance_sort_key(player, first_term):
    """
    Calcola la chiave di ordinamento per rilevanza.
    Privilegia cognomi che iniziano col primo termine, poi nomi, poi il resto.
    """
    last_name = (player.get("last_name") or "").lower()
    first_name = (player.get("first_name") or "").lower()

    if last_name.startswith(first_term):
        rel = 1
    elif first_name.startswith(first_term):
        rel = 2
    else:
        rel = 3

    return (rel, last_name, first_name)


def _search_like_fallback(query, limit, exclude_fide_ids=None):
    """Ricerca di fallback basata su LIKE quando FTS5 non è disponibile o fallisce."""
    terms = [
        _sanitize_fts_term(t.lstrip("+-"))
        for t in query.replace("=", " ").split()
        if _sanitize_fts_term(t.lstrip("+-"))
    ]

    if not terms:
        return []

    try:
        conn = _get_connection()
        where_parts = []
        params = []

        for term in terms:
            where_parts.append(
                "(first_name LIKE ? COLLATE NOCASE OR last_name LIKE ? COLLATE NOCASE "
                "OR federation LIKE ? COLLATE NOCASE OR CAST(fide_id AS TEXT) LIKE ? "
                "OR CAST(birth_year AS TEXT) LIKE ?)"
            )
            pattern = f"%{term}%"
            params.extend([pattern] * 5)

        sql = f"SELECT * FROM players WHERE {' AND '.join(where_parts)}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        cursor = conn.execute(sql, params)
        results = []
        for row in cursor:
            player = _row_to_dict(row)
            if exclude_fide_ids and str(player["id_fide"]) in exclude_fide_ids:
                continue
            results.append(player)
        conn.close()
        return results
    except Exception:
        return []
