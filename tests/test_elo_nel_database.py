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


def _scrivi_il_database():
    """Il database delle schede, nel file della cartella del programma; i
    suoi byte."""
    import config

    with open(config.PLAYER_DB_FILE, "w", encoding="utf-8") as f:
        json.dump({"schema_version": 2, "players": [dict(s) for s in SCHEDE]}, f, indent=1)
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


@pytest.mark.finestre_vere
@pytest.mark.skipif(sys.platform != "win32", reason="il desktop nascosto esiste solo in Windows")
def test_la_finestra_gestione_database_scrive_gli_elo_interi(app_grafica, monkeypatch):
    """Ctrl+D, cioe' il comando Gestione Giocatori Locale del menu, apre la
    finestra vera, modale, sul desktop nascosto. Mentre e' aperta: il titolo,
    le voci dell'elenco, intere, in ordine di Elo standard, con la prima
    scelta, e il fuoco nel campo Filtra Giocatori; nessun suono. Poi INVIO
    sull'ELO Standard della scheda di Bianchi, nell'albero, con il campo
    della modifica finto che risponde 1620: la voce dell'elenco si riscrive,
    con l'Elo rapid intero, e si sente il suono del salvataggio. Nessun
    wx.MessageBox: la guardia delle finestre lo farebbe cadere."""
    import wx
    from test_canc_nell_albero import _attiva
    from test_fuoco_alla_chiusura import _attendi

    import config
    from gui.dialogs import players_db_dialog
    from gui.dialogs.players_db_dialog import PlayersDbDialog

    _scrivi_il_database()
    suonati = []
    monkeypatch.setattr(players_db_dialog, "play_sound", lambda nome, *a, **k: suonati.append(nome) or True)
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

    def nella_finestra():
        dlg = next((w for w in wx.GetTopLevelWindows() if isinstance(w, PlayersDbDialog)), None)
        try:
            visto["titolo"] = dlg.GetTitle()
            visto["modale"] = dlg.IsModal() and dlg.IsShown()
            visto["voci"] = [dlg.list_players.GetString(i) for i in range(dlg.list_players.GetCount())]
            visto["scelta"] = dlg.list_players.GetSelection()
            visto["fuoco_sul_filtro"] = _attendi(lambda: wx.Window.FindFocus() is dlg.search_input)
            visto["suoni_all_apertura"] = list(suonati)
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
        finally:
            if dlg is not None and dlg.IsModal():
                dlg.EndModal(wx.ID_CANCEL)

    principale = _principale_vera(monkeypatch)
    try:
        _attiva(principale)
        rete = wx.CallLater(10000, lambda: [w.EndModal(wx.ID_CANCEL) for w in wx.GetTopLevelWindows() if isinstance(w, PlayersDbDialog) and w.IsModal()])
        wx.CallLater(300, nella_finestra)
        principale.ProcessCommand(principale.item_local_db.GetId())
        rete.Stop()
    finally:
        principale.Destroy()
        _attendi(lambda: not principale, 1.0)

    assert visto["titolo"] == "Gestione Database Giocatori Locale"
    assert visto["modale"] is True
    assert visto["voci"] == [
        "Bianchi Anna (Std: 1600, Rap: 1650 - ID: BIAAN001)",
        "Rossi Mario (Std: 1500, Rap: 0 - ID: ROSMA001)",
        "Verdi Luca (Std: 1450, Rap: 1612.5 - ID: VERLU001)",
    ]
    assert visto["scelta"] == 0
    assert visto["fuoco_sul_filtro"] is True
    assert visto["suoni_all_apertura"] == []
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
