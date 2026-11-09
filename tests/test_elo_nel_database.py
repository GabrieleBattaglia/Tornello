"""Gli Elo interi del database dei giocatori, dalla 10.19.64 (decisione di
Gabriele del 9 novembre 2026).

Il database tiene l'Elo standard, current_elo, intero, e l'Elo rapid,
l'Elo blitz e l'Elo club quasi sempre con il punto zero: il database vero
ha 54 schede su 55 con l'Elo rapid 0.0. Fino alla 10.19.63 la finestra
Gestione database, Ctrl+D, li scriveva cosi' in ogni voce dell'elenco, per
esempio (Std: 1837, Rap: 0.0 - ID: ...), mentre la finestra dell'iscrizione
scrive Rap: 0; e il file Tornello - Players_DB.txt aveva 108 righe con Elo
Rapid: 0.0 o Elo Blitz: 0.0. Adesso tutti e due li scrivono interi, con
elo_da_scrivere di utils, la funzione della console e dei file dei
dettagli: un Elo con i decimali, che i file del programma non hanno, resta
com'e'. Il database tiene gli Elo come prima.
Dalla 10.19.65 (decisione di Gabriele del 9 novembre 2026) un Elo null, che
un database scritto a mano puo' avere, si scrive ?, come nei file dei
dettagli: fino alla 10.19.64 la finestra e il file scrivevano None.
La finestra e' quella vera, aperta con il comando del menu della finestra
principale vera, mostrate tutte e due sul desktop nascosto delle prove; il
campo della modifica e' finto. Tutto sta nella cartella temporanea della
prova."""

import json
import sys

import pytest

# Le schede del database: Bianchi ha l'Elo rapid e l'Elo blitz, Rossi no, e
# Verdi ha l'Elo rapid con i decimali, che i file del programma non hanno.
SCHEDE = (
    {"id": "BIAAN001", "first_name": "Anna", "last_name": "Bianchi", "current_elo": 1600, "elo_rapid": 1650.0, "elo_blitz": 1580.0, "elo_club": 0.0},
    {"id": "ROSMA001", "first_name": "Mario", "last_name": "Rossi", "current_elo": 1500, "elo_rapid": 0.0, "elo_blitz": 0.0, "elo_club": 0.0},
    {"id": "VERLU001", "first_name": "Luca", "last_name": "Verdi", "current_elo": 1450, "elo_rapid": 1612.5, "elo_blitz": 0.0, "elo_club": 1400.0},
)
# Le schede con gli Elo null, come in un database scritto a mano: a Rossi
# mancano l'Elo rapid e l'Elo blitz, a Bianchi l'Elo rapid.
SCHEDE_CON_GLI_ELO_NULL = (
    {"id": "BIAAN001", "first_name": "Anna", "last_name": "Bianchi", "current_elo": 1600, "elo_rapid": None, "elo_blitz": 1580.0, "elo_club": 0.0},
    {"id": "ROSMA001", "first_name": "Mario", "last_name": "Rossi", "current_elo": 1500, "elo_rapid": None, "elo_blitz": None, "elo_club": 0.0},
)


def _scrivi_il_database(schede=SCHEDE):
    """Il database delle schede, nel file della cartella del programma; i
    suoi byte."""
    import config

    with open(config.PLAYER_DB_FILE, "w", encoding="utf-8") as f:
        json.dump({"schema_version": 2, "players": [dict(s) for s in schede]}, f, indent=1)
    with open(config.PLAYER_DB_FILE, "rb") as f:
        return f.read()


def _righe_dell_elo(percorso):
    """Le righe del file txt del database con i tre Elo, per giocatore."""
    with open(percorso, encoding="utf-8-sig") as f:
        righe = f.read().splitlines()
    esito = {}
    giocatore = None
    for riga in righe:
        if riga.startswith("ID: "):
            giocatore = riga
            esito[giocatore] = []
        elif riga.startswith("\tElo "):
            esito[giocatore].append(riga)
    return esito


class TestIlFileDelDatabase:
    """Tornello - Players_DB.txt, scritto dal salvataggio del database nella
    cartella del programma, deviata nella cartella della prova."""

    def test_i_tre_elo_sono_interi(self):
        import os

        import config
        from db_players import load_players_db, save_players_db

        _scrivi_il_database()
        database = load_players_db()
        # Il caso c'e': il database tiene l'Elo rapid e l'Elo blitz con il
        # punto zero.
        assert database["ROSMA001"]["elo_rapid"] == 0.0 and isinstance(database["ROSMA001"]["elo_rapid"], float)
        assert config.PLAYER_DB_TXT_FILE.startswith(config.user_data_path(""))

        assert save_players_db(database)

        assert sorted(os.listdir(config.user_data_path(""))) == ["Tornello - Players_db.json", "Tornello - Players_db.txt"]
        assert _righe_dell_elo(config.PLAYER_DB_TXT_FILE) == {
            "ID: BIAAN001, Anna Bianchi": [
                "\tElo Standard: 1600 (Partite FIDE: 0)",
                "\tElo Rapid: 1650 (Partite FIDE: 0, K: None)",
                "\tElo Blitz: 1580 (Partite FIDE: 0, K: None)",
            ],
            "ID: ROSMA001, Mario Rossi": [
                "\tElo Standard: 1500 (Partite FIDE: 0)",
                "\tElo Rapid: 0 (Partite FIDE: 0, K: None)",
                "\tElo Blitz: 0 (Partite FIDE: 0, K: None)",
            ],
            "ID: VERLU001, Luca Verdi": [
                "\tElo Standard: 1450 (Partite FIDE: 0)",
                "\tElo Rapid: 1612.5 (Partite FIDE: 0, K: None)",
                "\tElo Blitz: 0 (Partite FIDE: 0, K: None)",
            ],
        }
        # Il database tiene gli Elo come prima.
        with open(config.PLAYER_DB_FILE, encoding="utf-8") as f:
            schede = {s["id"]: s for s in json.load(f)["players"]}
        assert [(schede[s["id"]]["elo_rapid"], schede[s["id"]]["elo_blitz"]) for s in SCHEDE] == [(1650.0, 1580.0), (0.0, 0.0), (1612.5, 0.0)]

    def test_un_elo_null_si_scrive_con_il_punto_interrogativo(self):
        """10.19.65: l'Elo standard, l'Elo rapid e l'Elo blitz null si
        scrivono ?; fino alla 10.19.64 None."""
        import config
        from db_players import load_players_db, save_players_db

        schede = (*SCHEDE_CON_GLI_ELO_NULL, {"id": "VERLU001", "first_name": "Luca", "last_name": "Verdi", "current_elo": None, "elo_rapid": 0.0, "elo_blitz": 0.0})
        _scrivi_il_database(schede)

        assert save_players_db(load_players_db())

        assert _righe_dell_elo(config.PLAYER_DB_TXT_FILE) == {
            "ID: BIAAN001, Anna Bianchi": [
                "\tElo Standard: 1600 (Partite FIDE: 0)",
                "\tElo Rapid: ? (Partite FIDE: 0, K: None)",
                "\tElo Blitz: 1580 (Partite FIDE: 0, K: None)",
            ],
            "ID: ROSMA001, Mario Rossi": [
                "\tElo Standard: 1500 (Partite FIDE: 0)",
                "\tElo Rapid: ? (Partite FIDE: 0, K: None)",
                "\tElo Blitz: ? (Partite FIDE: 0, K: None)",
            ],
            "ID: VERLU001, Luca Verdi": [
                "\tElo Standard: ? (Partite FIDE: 0)",
                "\tElo Rapid: 0 (Partite FIDE: 0, K: None)",
                "\tElo Blitz: 0 (Partite FIDE: 0, K: None)",
            ],
        }
        # Il database tiene gli Elo null com'erano.
        with open(config.PLAYER_DB_FILE, encoding="utf-8") as f:
            salvate = {s["id"]: s for s in json.load(f)["players"]}
        assert (salvate["ROSMA001"]["elo_rapid"], salvate["ROSMA001"]["elo_blitz"], salvate["VERLU001"]["current_elo"]) == (None, None, None)


def _principale_vera(monkeypatch):
    """La finestra principale vera, senza i controlli dell'avvio, che si
    mostra sul desktop nascosto."""
    import gui.main_frame as mf
    from gui.settings import DEFAULT_SETTINGS

    for nome in ("_check_fide_db_on_startup", "_check_backup_on_startup", "_scan_and_load_initial_tournament", "_check_updates_async"):
        monkeypatch.setattr(mf.MainFrame, nome, lambda self: None)
    monkeypatch.setattr(mf.MainFrame, "Maximize", lambda self, *a: None)
    finestra = mf.MainFrame(None, "Tornello", dict(DEFAULT_SETTINGS))
    finestra._timer_pie_di_pagina.Stop()
    return finestra


def _nella_gestione(monkeypatch, durante):
    """Ctrl+D, cioe' il comando Gestione Giocatori Locale del menu della
    finestra principale vera, mostrata e attiva sul desktop nascosto: la
    finestra Gestione Database Giocatori Locale vera si apre, modale, e
    mentre e' aperta durante riceve il dialogo; poi il dialogo si chiude.
    Restituisce i suoni del dialogo."""
    import wx
    from test_canc_nell_albero import _attiva
    from test_fuoco_alla_chiusura import _attendi

    from gui.dialogs import players_db_dialog
    from gui.dialogs.players_db_dialog import PlayersDbDialog

    suonati = []
    monkeypatch.setattr(players_db_dialog, "play_sound", lambda nome, *a, **k: suonati.append(nome) or True)

    def aperti():
        return [w for w in wx.GetTopLevelWindows() if isinstance(w, PlayersDbDialog) and w.IsModal()]

    def nella_finestra():
        try:
            durante(aperti()[0])
        finally:
            for dlg in aperti():
                dlg.EndModal(wx.ID_CANCEL)

    principale = _principale_vera(monkeypatch)
    try:
        _attiva(principale)
        rete = wx.CallLater(10000, lambda: [dlg.EndModal(wx.ID_CANCEL) for dlg in aperti()])
        wx.CallLater(300, nella_finestra)
        principale.ProcessCommand(principale.item_local_db.GetId())
        rete.Stop()
    finally:
        principale.Destroy()
        _attendi(lambda: not principale, 1.0)
    return suonati


def _quello_che_si_vede(dlg, suonati):
    """Titolo, voci dell'elenco, voce scelta, fuoco e suoni del dialogo
    aperto."""
    import wx
    from test_fuoco_alla_chiusura import _attendi

    return {
        "titolo": dlg.GetTitle(),
        "modale": dlg.IsModal() and dlg.IsShown(),
        "voci": [dlg.list_players.GetString(i) for i in range(dlg.list_players.GetCount())],
        "scelta": dlg.list_players.GetSelection(),
        "fuoco_sul_filtro": _attendi(lambda: wx.Window.FindFocus() is dlg.search_input),
        "suoni": list(suonati),
    }


@pytest.mark.finestre_vere
@pytest.mark.skipif(sys.platform != "win32", reason="il desktop nascosto esiste solo in Windows")
def test_la_finestra_gestione_database_scrive_gli_elo_interi(app_grafica, monkeypatch):
    """Ctrl+D apre la finestra vera, modale, sul desktop nascosto. Mentre e'
    aperta: il titolo, le voci dell'elenco, intere, in ordine di Elo
    standard, con la prima scelta, e il fuoco nel campo Filtra Giocatori;
    nessun suono. Poi INVIO sull'ELO Standard della scheda di Bianchi,
    nell'albero, con il campo della modifica finto che risponde 1620: la
    voce dell'elenco si riscrive, con l'Elo rapid intero, e si sente il
    suono del salvataggio. Nessun wx.MessageBox: la guardia delle finestre
    lo farebbe cadere."""
    import wx

    import config
    from gui.dialogs import players_db_dialog

    _scrivi_il_database()
    campi = []

    class CampoFinto:
        def __init__(self, genitore, messaggio, titolo, valore):
            campi.append((titolo, messaggio, valore))

        def ShowModal(self):
            return wx.ID_OK

        def GetValue(self):
            return "1620"

        def Destroy(self):
            pass

    visto = {}
    suonati = []

    def durante(dlg):
        visto.update(_quello_che_si_vede(dlg, suonati))
        albero = dlg.tree_ctrl
        voci = {}

        def visita(voce):
            figlio, segno = albero.GetFirstChild(voce)
            while figlio.IsOk():
                voci[albero.GetItemText(figlio)] = figlio
                visita(figlio)
                figlio, segno = albero.GetNextChild(voce, segno)

        visita(albero.GetRootItem())
        voce = voci["ELO Standard: 1600"]
        albero.SelectItem(voce)
        monkeypatch.setattr(players_db_dialog.wx, "TextEntryDialog", CampoFinto)
        dlg.on_tree_item_activated(type("Evento", (), {"GetItem": lambda self: voce})())
        visto["voce_dopo_la_modifica"] = dlg.list_players.GetString(0)
        visto["albero_dopo_la_modifica"] = albero.GetItemText(voce)

    suonati.extend(_nella_gestione(monkeypatch, durante))

    assert visto["titolo"] == "Gestione Database Giocatori Locale"
    assert visto["modale"] is True
    assert visto["voci"] == [
        "Bianchi Anna (Std: 1600, Rap: 1650 - ID: BIAAN001)",
        "Rossi Mario (Std: 1500, Rap: 0 - ID: ROSMA001)",
        "Verdi Luca (Std: 1450, Rap: 1612.5 - ID: VERLU001)",
    ]
    assert visto["scelta"] == 0
    assert visto["fuoco_sul_filtro"] is True
    assert visto["suoni"] == []
    assert campi == [("Modifica Campo", "Modifica valore per 'ELO Standard':", "1600")]
    assert visto["voce_dopo_la_modifica"] == "Bianchi Anna (Std: 1620, Rap: 1650 - ID: BIAAN001)"
    assert visto["albero_dopo_la_modifica"] == "ELO Standard: 1620"
    assert suonati == ["timbratura"]
    # Il database ha l'Elo standard nuovo, e tiene gli altri come prima; il
    # suo file txt, riscritto dal salvataggio, li ha interi.
    with open(config.PLAYER_DB_FILE, encoding="utf-8") as f:
        bianchi = next(s for s in json.load(f)["players"] if s["id"] == "BIAAN001")
    assert (bianchi["current_elo"], bianchi["elo_rapid"], bianchi["elo_blitz"]) == (1620, 1650.0, 1580.0)
    assert _righe_dell_elo(config.PLAYER_DB_TXT_FILE)["ID: BIAAN001, Anna Bianchi"] == [
        "\tElo Standard: 1620 (Partite FIDE: 0)",
        "\tElo Rapid: 1650 (Partite FIDE: 0, K: None)",
        "\tElo Blitz: 1580 (Partite FIDE: 0, K: None)",
    ]


@pytest.mark.finestre_vere
@pytest.mark.skipif(sys.platform != "win32", reason="il desktop nascosto esiste solo in Windows")
@pytest.mark.parametrize(
    ("schede", "attese"),
    [
        (SCHEDE_CON_GLI_ELO_NULL, ["Bianchi Anna (Std: 1600, Rap: ? - ID: BIAAN001)", "Rossi Mario (Std: 1500, Rap: ? - ID: ROSMA001)"]),
        (({"id": "ROSMA001", "first_name": "Mario", "last_name": "Rossi", "current_elo": None, "elo_rapid": None},), ["Rossi Mario (Std: ?, Rap: ? - ID: ROSMA001)"]),
    ],
    ids=["l'Elo rapid null", "l'Elo standard null del solo giocatore"],
)
def test_la_finestra_gestione_database_con_gli_elo_null(app_grafica, monkeypatch, schede, attese):
    """10.19.65: nella finestra vera, sul desktop nascosto, un Elo null si
    scrive ?; fino alla 10.19.64 None. Il database resta com'era."""
    import config

    prima = _scrivi_il_database(schede)
    visto = {}
    suonati = []

    def durante(dlg):
        visto.update(_quello_che_si_vede(dlg, suonati))

    suonati.extend(_nella_gestione(monkeypatch, durante))

    assert visto["titolo"] == "Gestione Database Giocatori Locale"
    assert visto["modale"] is True
    assert visto["voci"] == attese
    assert visto["scelta"] == 0
    assert visto["fuoco_sul_filtro"] is True
    assert visto["suoni"] == [] and suonati == []
    with open(config.PLAYER_DB_FILE, "rb") as f:
        assert f.read() == prima
