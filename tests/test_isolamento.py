"""Le prove non devono poter scrivere nei file veri del progetto.

La deviazione sta in conftest.py, fixture dati_in_cartella_temporanea. Queste
prove verificano che copra davvero tutti i moduli, compresi quelli che hanno
importato i percorsi in cima, e che un modulo nuovo con una costante di
percorso calcolata all'importazione non riapra il buco senza che nessuno se ne
accorga.
"""

import os

from conftest import RADICE, moduli_di_tornello, nella_radice_vera

# Le sole costanti che possono restare nella radice vera: risorse che il
# programma legge e non scrive.
RISORSE_IN_SOLA_LETTURA = {"locales_dir", "BBP_SUBDIR", "BBP_EXE_PATH"}


def test_user_data_path_va_nella_cartella_temporanea(tmp_path):
    import config
    import db_players
    import tournament
    import ui

    for modulo in (config, tournament, ui, db_players):
        assert modulo.user_data_path("x").startswith(str(tmp_path)), modulo.__name__


def test_le_costanti_di_percorso_vanno_nella_cartella_temporanea(tmp_path, tmp_path_factory):
    import config
    import controller
    import db_players
    import engine
    import fide_db
    import ui

    attese = [
        (config, "PLAYER_DB_FILE"),
        (db_players, "PLAYER_DB_FILE"),
        (ui, "PLAYER_DB_FILE"),
        (controller, "PLAYER_DB_FILE"),
        (config, "ARCHIVED_TOURNAMENTS_DIR"),
        (ui, "ARCHIVED_TOURNAMENTS_DIR"),
        (fide_db, "FIDE_DB_LOCAL_FILE"),
        (db_players, "FIDE_DB_LOCAL_FILE"),
    ]
    for modulo, nome in attese:
        valore = getattr(modulo, nome)
        assert valore.startswith(str(tmp_path)), f"{modulo.__name__}.{nome} = {valore}"
    # I file di lavoro del motore stanno in una cartella temporanea a parte.
    base = str(tmp_path_factory.getbasetemp())
    for nome in ("BBP_INPUT_TRF", "BBP_OUTPUT_COUPLES", "BBP_OUTPUT_CHECKLIST"):
        valore = getattr(engine, nome)
        assert valore.startswith(base), f"engine.{nome} = {valore}"
        assert not nella_radice_vera(valore), f"engine.{nome} = {valore}"


def test_nessun_modulo_tiene_un_percorso_vero_da_scrivere(tmp_path):
    """Scorre ogni stringa a livello di modulo che punta dentro la radice
    vera: deve essere una risorsa in sola lettura. Un modulo nuovo che si
    calcola un percorso di dati all'importazione fa fallire questa prova, e
    il rimedio e' aggiungere il nome a COSTANTI_DI_DATI in conftest.py."""
    import controller  # noqa: F401
    import engine  # noqa: F401
    import fide_db  # noqa: F401
    import reports  # noqa: F401
    import stats  # noqa: F401
    import ui  # noqa: F401

    trovate = []
    for modulo in moduli_di_tornello():
        for nome, valore in vars(modulo).items():
            if (
                not nome.startswith("__")
                and isinstance(valore, str)
                and os.path.isabs(valore)
                and nella_radice_vera(valore)
                and nome not in RISORSE_IN_SOLA_LETTURA
            ):
                trovate.append(f"{modulo.__name__}.{nome} = {valore}")
    assert trovate == []


def test_un_torneo_salvato_senza_percorso_resta_nella_cartella_temporanea(tmp_path):
    from tournament import save_tournament

    torneo = {"name": "Prova isolamento", "players": [], "rounds": []}
    save_tournament(torneo)
    nome_del_file = "Tornello - Prova_isolamento.json"
    assert (tmp_path / nome_del_file).exists()
    assert not os.path.exists(os.path.join(RADICE, nome_del_file))
