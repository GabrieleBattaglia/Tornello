"""Le finestre si adattano ai caratteri grandi e allo schermo. Issue 49.

Fino alla 10.6.2 ogni finestra aveva una misura fissa in pixel, oppure la
prendeva dal contenuto prima che il tema desse ai controlli il carattere dei
dialoghi, e nessuna scorreva: con i caratteri di Windows al 150 per cento, o
con quelli dei dialoghi grandi, campi e pulsanti finivano fuori dallo schermo.
Dalla 10.6.3 la misura la da' il contenuto, dentro l'area utile, e il
pannello scorre quando non ci sta; dalla 10.6.4 i controlli dei riquadri sono
figli del loro riquadro, e lo screen reader ne annuncia il nome.
Qui le finestre nascono con il carattere dei dialoghi a 36 punti e con uno
schermo simulato da 1280 per 688, quello di un monitor 1920 per 1080 con la
scala al 150 per cento: una finestra che torni a misura fissa, o un controllo
creato fuori dal suo riquadro, fa fallire la prova. Nessuna finestra viene
mostrata, niente suona, il thread che scarica il database FIDE e' sostituito
da uno finto e il database dei giocatori non si puo' scrivere.
I nomi dei controlli si leggono come li legge NVDA, da MSAA: SetName di wx
non ci arriva, e solo cosi' si vede un controllo rimasto senza nome.
"""

import ctypes
import datetime
import sys
from types import SimpleNamespace

import pytest

AREA = (0, 0, 1280, 688)
CORPO = 36

# I ruoli e gli stati di MSAA che le prove confrontano.
RUOLO_LISTA = 0x21
RUOLO_VOCE = 0x22
RUOLO_TESTO = 0x2A
RUOLO_BARRA = 0x30
STATO_SOLA_LETTURA = 0x40
STATO_FOCALIZZABILE = 0x100000

# La finestra del database dei giocatori riempie il suo albero con
# SetItemPyData, che wxPython da' per superata a favore di SetItemData: e' un
# lavoro a parte, e qui gli avvisi coprirebbero l'esito della suite con
# decine di righe uguali.
pytestmark = pytest.mark.filterwarnings("ignore:Call to deprecated item. Use SetItemData instead.")

FINESTRE = (
    "programmazione",
    "risultato",
    "consulta FIDE",
    "aggiornamento FIDE",
    "database giocatori",
    "sincronizzazione",
    "impostazioni",
    "messaggio",
    "donazione",
    "pulizia backup",
    "iscrizione",
    "spareggi",
    # Le due finestre dell'aggiornamento del programma, nate con la 10.7.0
    # (issue 37).
    "aggiornamento",
    "scaricamento aggiornamento",
)

# Le finestre con i riquadri, e quanti ne hanno almeno: senza, la prova sui
# genitori passerebbe anche senza controllare niente.
RIQUADRI = {"programmazione": 3, "risultato": 1, "iscrizione": 3, "impostazioni": 10}


def _muto(*a, **k):
    return True


def _vietato(*a, **k):
    raise AssertionError("una finestra ha provato a scrivere il database dei giocatori")


class _ThreadFinto:
    """Al posto di FideUpdateThread, che scaricherebbe il database FIDE."""

    def __init__(self, *a, **k):
        pass

    def start(self):
        pass


def _giocatori(quanti):
    return {
        f"GIO{i:03d}": {
            "id": f"GIO{i:03d}",
            "first_name": f"Nome{i} Secondonome",
            "last_name": f"Cognome{i} Cognomelungo",
            "current_elo": 1400 + i,
            "elo_rapid": 1300,
            "federation": "ITA",
            "fide_id_num_str": "0",
        }
        for i in range(quanti)
    }


def _torneo(giorni_alla_fine):
    oggi = datetime.date.today()
    return {
        "name": "Prova",
        "current_round": 1,
        "round_dates": [{"round": 1, "end_date": (oggi + datetime.timedelta(days=giorni_alla_fine)).isoformat()}],
        "players": [],
    }


@pytest.fixture
def ambiente(app_grafica, monkeypatch):
    """Schermo simulato, suoni muti, thread e scritture finti, e un telaio
    con le impostazioni: carattere dei dialoghi a 36 punti."""
    import GBwx
    import wx

    import utils
    from gui.dialogs import (
        backup_cleanup_dialog,
        fide_query_dialog,
        fide_update_dialog,
        player_enrollment_dialog,
        players_db_dialog,
        sync_database_dialog,
        tiebreak_config_dialog,
        visual_settings_dialog,
    )
    from gui.settings import DEFAULT_SETTINGS

    monkeypatch.setattr(GBwx, "area_utile", lambda finestra: wx.Rect(*AREA))
    monkeypatch.setattr(utils, "play_sound", _muto)
    monkeypatch.setattr(utils, "bip_di_scelta", _muto)
    for modulo in (backup_cleanup_dialog, fide_query_dialog, player_enrollment_dialog, players_db_dialog, sync_database_dialog, tiebreak_config_dialog, visual_settings_dialog):
        monkeypatch.setattr(modulo, "play_sound", _muto)
    monkeypatch.setattr(fide_update_dialog, "FideUpdateThread", _ThreadFinto)
    for modulo in (players_db_dialog, sync_database_dialog):
        monkeypatch.setattr(modulo, "load_players_db", lambda: _giocatori(30))
        monkeypatch.setattr(modulo, "save_players_db", _vietato)
    impostazioni = dict(DEFAULT_SETTINGS, dialog_font_size=CORPO)
    telaio = wx.Frame(None)
    telaio.settings = impostazioni
    yield SimpleNamespace(wx=wx, telaio=telaio, impostazioni=impostazioni)
    telaio.Destroy()


def _crea(nome, a):
    from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog
    from gui.dialogs.backup_cleanup_dialog import BackupCleanupDialog
    from gui.dialogs.donation_dialog import DonationDialog
    from gui.dialogs.fide_query_dialog import FideQueryDialog
    from gui.dialogs.fide_update_dialog import FideUpdateDialog
    from gui.dialogs.player_enrollment_dialog import PlayerEnrollmentDialog
    from gui.dialogs.players_db_dialog import PlayersDbDialog
    from gui.dialogs.result_dialog import ResultDialog, ScheduleDialog
    from gui.dialogs.sync_database_dialog import SyncDatabaseDialog
    from gui.dialogs.tiebreak_config_dialog import TiebreakConfigDialog
    from gui.dialogs.update_dialog import UpdateDialog, UpdateProgressDialog
    from gui.dialogs.visual_settings_dialog import VisualSettingsDialog

    t, s = a.telaio, a.impostazioni
    programmata = {"date": datetime.date.today().isoformat(), "time": "17:30", "channel": "https://meet.google.com/abc-defg-hij", "arbiter": "Gabry"}
    iscritti = list(_giocatori(8).values())
    costruttori = {
        # Trentuno giorni, il massimo che la finestra propone.
        "programmazione": lambda: ScheduleDialog(t, {}, s, _torneo(27)),
        "risultato": lambda: ResultDialog(t, "Bianchi Luca", "Russo Marco", "GIO001", "GIO002", 3, None, programmata, s),
        "consulta FIDE": lambda: FideQueryDialog(t, _giocatori(30), s),
        "aggiornamento FIDE": lambda: FideUpdateDialog(t, s),
        "database giocatori": lambda: PlayersDbDialog(t, s),
        "sincronizzazione": lambda: SyncDatabaseDialog(t, s),
        "impostazioni": lambda: VisualSettingsDialog(t, s),
        "messaggio": lambda: AccessibleMsgDialog(t, "Titolo", "Riga del messaggio\n" * 20, settings=s),
        "donazione": lambda: DonationDialog(t, "Titolo", "Riga del messaggio\n" * 20, s),
        "pulizia backup": lambda: BackupCleanupDialog(t, s),
        "iscrizione": lambda: PlayerEnrollmentDialog(t, _giocatori(30), iscritti, s),
        "spareggi": lambda: TiebreakConfigDialog(t, _torneo(5)),
        "aggiornamento": lambda: UpdateDialog(t, "10.6.5", "10.7.0", "* Riga delle note della release\n" * 40, s),
        "scaricamento aggiornamento": lambda: UpdateProgressDialog(t, s),
    }
    return costruttori[nome]()


def _chiudi(dlg):
    """Ferma i timer della ricerca, che il dialogo avvia nascendo, e lo
    distrugge: un timer che scattasse dopo troverebbe la finestra sparita.
    I controlli si distruggono subito, mentre la finestra aspetterebbe un
    ciclo degli eventi che nelle prove non gira: il Notebook delle
    impostazioni, rimasto in vita fino all'uscita, faceva scrivere a wx un
    errore di UnregisterClass alla chiusura della suite."""
    import wx

    for valore in vars(dlg).values():
        if isinstance(valore, wx.Timer):
            valore.Stop()
    dlg.DestroyChildren()
    dlg.Destroy()


def _contenuto_coperto(pannello):
    contenuto = pannello.GetSizer().GetMinSize()
    virtuale = pannello.GetVirtualSize()
    return virtuale.width >= contenuto.width and virtuale.height >= contenuto.height


@pytest.mark.parametrize("nome", FINESTRE)
def test_la_finestra_sta_nello_schermo_e_il_contenuto_si_raggiunge(nome, ambiente):
    wx = ambiente.wx
    dlg = _crea(nome, ambiente)
    try:
        assert wx.Rect(*AREA).Contains(dlg.GetRect()), f"{nome}: {tuple(dlg.GetRect())} esce dallo schermo"
        stile = dlg.GetWindowStyle()
        assert stile & wx.RESIZE_BORDER and stile & wx.MAXIMIZE_BOX
        assert isinstance(dlg.pannello, wx.ScrolledWindow)
        assert _contenuto_coperto(dlg.pannello)
        # Rimpicciolita a mano, la finestra deve lasciar scorrere fino in fondo.
        dlg.SetSize(300, 200)
        dlg.Layout()
        assert _contenuto_coperto(dlg.pannello)
    finally:
        _chiudi(dlg)


def _controlli_fuori_dal_riquadro(finestra):
    """Visita ogni sizer della finestra e delle sue figlie. Dentro uno
    StaticBoxSizer ogni controllo deve avere per genitore il suo riquadro.
    Torna i riquadri visti e i controlli fuori posto."""
    import wx

    riquadri, fuori = [], []

    def nel_sizer(sizer, riquadro):
        if isinstance(sizer, wx.StaticBoxSizer):
            riquadro = sizer.GetStaticBox()
            riquadri.append(riquadro.GetLabel())
        for voce in sizer.GetChildren():
            if voce.IsWindow():
                controllo = voce.GetWindow()
                if riquadro is not None and controllo.GetParent() is not riquadro:
                    fuori.append(f"{type(controllo).__name__} {controllo.GetLabel()!r} in {riquadro.GetLabel()!r}")
            elif voce.IsSizer():
                nel_sizer(voce.GetSizer(), riquadro)

    def visita(finestra):
        if finestra.GetSizer():
            nel_sizer(finestra.GetSizer(), None)
        for figlia in finestra.GetChildren():
            visita(figlia)

    visita(finestra)
    return riquadri, fuori


@pytest.mark.parametrize("nome", FINESTRE)
def test_i_controlli_dei_riquadri_sono_figli_del_riquadro(nome, ambiente):
    dlg = _crea(nome, ambiente)
    try:
        riquadri, fuori = _controlli_fuori_dal_riquadro(dlg)
        assert fuori == []
        assert len(riquadri) >= RIQUADRI.get(nome, 0)
    finally:
        _chiudi(dlg)


def _msaa(finestra, figli=0):
    """Numero dei figli, e nome, ruolo e stato MSAA del controllo (figlio 0)
    e dei suoi primi figli, chiesti a oleacc come fa NVDA. Solo ctypes, per
    non dipendere da pywin32; funziona anche a finestra nascosta."""
    from ctypes import wintypes

    class Guid(ctypes.Structure):
        _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD), ("d", ctypes.c_ubyte * 8)]

    class Variant(ctypes.Structure):
        _fields_ = [("vt", ctypes.c_ushort), ("r1", ctypes.c_ushort), ("r2", ctypes.c_ushort), ("r3", ctypes.c_ushort), ("val", ctypes.c_longlong), ("resto", ctypes.c_longlong)]

    iid = Guid()
    ctypes.oledll.ole32.CLSIDFromString("{618736E0-3C3D-11CF-810C-00AA00389B71}", ctypes.byref(iid))
    # Posizioni nella tabella di IAccessible, dopo IUnknown e IDispatch.
    conta = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_long))
    testo = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, Variant, ctypes.POINTER(ctypes.c_void_p))
    variante = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, Variant, ctypes.POINTER(Variant))
    rilascia = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
    libera = ctypes.windll.oleaut32.SysFreeString
    libera.argtypes = [ctypes.c_void_p]
    ctypes.oledll.ole32.CoInitialize(None)
    acc = ctypes.c_void_p()
    try:
        ctypes.oledll.oleacc.AccessibleObjectFromWindow(wintypes.HWND(finestra.GetHandle()), ctypes.c_long(-4), ctypes.byref(iid), ctypes.byref(acc))
        tabella = ctypes.cast(acc, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        quanti = ctypes.c_long()
        conta(tabella[8])(acc, ctypes.byref(quanti))
        voci = []
        for figlio in range(figli + 1):
            chi = Variant(vt=3, val=figlio)
            nome = ctypes.c_void_p()
            testo(tabella[10])(acc, chi, ctypes.byref(nome))
            letto = ctypes.wstring_at(nome.value) if nome.value else ""
            libera(nome)
            ruolo, stato = Variant(), Variant()
            variante(tabella[13])(acc, chi, ctypes.byref(ruolo))
            variante(tabella[14])(acc, chi, ctypes.byref(stato))
            voci.append((letto, ruolo.val & 0xFFFFFFFF, stato.val & 0xFFFFFFFF))
        return quanti.value, voci
    finally:
        if acc.value:
            rilascia(ctypes.cast(acc, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[2])(acc)
        ctypes.windll.ole32.CoUninitialize()


def _senza_etichetta(finestra):
    """I controlli dei riquadri che ricevono il focus e non hanno ne' un testo
    proprio, come pulsanti e caselle, ne' uno StaticText subito prima.
    Windows da' loro il nome del fratello che li precede: dalla 10.6.4 il
    primo di un riquadro non ne ha, e prima era il riquadro stesso."""
    import wx

    trovati = []

    def visita(w):
        if isinstance(w, wx.StaticBox):
            precedente = None
            for figlio in w.GetChildren():
                con_testo = isinstance(figlio, (wx.Button, wx.CheckBox, wx.RadioButton))
                if figlio.AcceptsFocus() and not con_testo and not isinstance(precedente, wx.StaticText):
                    trovati.append(figlio)
                precedente = figlio
        for figlio in w.GetChildren():
            visita(figlio)

    visita(finestra)
    return trovati


# Quanti controlli senza etichetta ha almeno ogni finestra con i riquadri:
# senza, la prova sui nomi passerebbe anche senza controllare niente.
SENZA_ETICHETTA = {"iscrizione": 3, "impostazioni": 2}
solo_windows = pytest.mark.skipif(sys.platform != "win32", reason="MSAA c'e' solo su Windows")


@solo_windows
@pytest.mark.parametrize("nome", FINESTRE)
def test_i_controlli_senza_etichetta_hanno_un_nome_per_lo_screen_reader(nome, ambiente):
    """Nella 10.6.4 com'era nel primo commit, i due campi di ricerca e la
    lista degli iscritti, l'anteprima e la lingua delle impostazioni
    arrivavano a NVDA senza nome."""
    dlg = _crea(nome, ambiente)
    try:
        controlli = _senza_etichetta(dlg)
        assert len(controlli) >= SENZA_ETICHETTA.get(nome, 0)
        for controllo in controlli:
            letto = _msaa(controllo)[1][0][0]
            assert letto, f"{nome}: {type(controllo).__name__} senza nome per lo screen reader"
    finally:
        _chiudi(dlg)


@solo_windows
def test_la_lista_degli_iscritti_ha_il_nome_del_riquadro_e_le_voci_il_loro(ambiente):
    """Le voci tengono il loro testo solo se l'oggetto accessibile, per i
    figli, lascia rispondere Windows: con ACC_NOT_SUPPORTED, come fa
    CustomAccessible, sarebbero arrivate a NVDA tutte senza nome."""
    dlg = _crea("iscrizione", ambiente)
    try:
        lista = dlg.list_enrolled
        quanti, voci = _msaa(lista, 3)
        assert quanti == lista.GetCount() == 8
        assert voci[0][:2] == (dlg.sb_enrolled.GetLabel(), RUOLO_LISTA)
        for posizione, voce in enumerate(voci[1:]):
            assert voce[:2] == (lista.GetString(posizione), RUOLO_VOCE)
        # Il nome segue il numero degli iscritti, come l'etichetta del riquadro.
        dlg.enrolled_players.pop()
        dlg.update_enrolled_list()
        assert "(7)" in dlg.sb_enrolled.GetLabel()
        assert _msaa(lista)[1][0][0] == dlg.sb_enrolled.GetLabel()
    finally:
        _chiudi(dlg)


@solo_windows
def test_l_anteprima_resta_un_testo_in_sola_lettura(ambiente):
    """L'anteprima e' un RICHEDIT50W: con un oggetto accessibile di wx che
    dia solo il nome, Windows la presentava come client, senza sola lettura."""
    dlg = _crea("impostazioni", ambiente)
    try:
        anteprima = dlg.preview_text
        nome, ruolo, stato = _msaa(anteprima)[1][0]
        assert (nome, ruolo) == (anteprima.GetParent().GetLabel(), RUOLO_TESTO)
        assert stato & STATO_SOLA_LETTURA and stato & STATO_FOCALIZZABILE
    finally:
        _chiudi(dlg)


@solo_windows
def test_le_note_dell_aggiornamento_hanno_il_nome_dell_etichetta(ambiente):
    """Il campo delle note, un RICHEDIT50W senza oggetto accessibile di wx,
    prende il nome dall'etichetta che lo precede e resta un testo in sola
    lettura (issue 37)."""
    dlg = _crea("aggiornamento", ambiente)
    try:
        nome, ruolo, stato = _msaa(dlg.campo_note)[1][0]
        assert (nome, ruolo) == (dlg.etichetta_note.GetLabel(), RUOLO_TESTO)
        assert stato & STATO_SOLA_LETTURA and stato & STATO_FOCALIZZABILE
    finally:
        _chiudi(dlg)


@solo_windows
def test_la_barra_dello_scaricamento_si_chiama_come_il_messaggio(ambiente, monkeypatch):
    """Il nome MSAA della barra segue il messaggio, e la barra resta una
    barra di avanzamento per NVDA (issue 37). La notifica allo screen reader
    e' sostituita da una finta."""
    wx = ambiente.wx
    monkeypatch.setattr(wx.Accessible, "NotifyEvent", lambda *argomenti: None)
    dlg = _crea("scaricamento aggiornamento", ambiente)
    try:
        assert _msaa(dlg.gauge)[1][0][:2] == (dlg.status_label.GetLabel(), RUOLO_BARRA)
        dlg.aggiorna(40, 100)
        assert _msaa(dlg.gauge)[1][0][:2] == (dlg.status_label.GetLabel(), RUOLO_BARRA)
        assert dlg.status_label.GetLabel().startswith("40%")
    finally:
        _chiudi(dlg)


def test_i_risultati_restano_un_gruppo_solo(ambiente):
    dlg = _crea("risultato", ambiente)
    try:
        for valore, pulsante in dlg.radio_buttons:
            pulsante.SetValue(True)
            assert dlg.get_selected_result() == valore
            assert [p for _v, p in dlg.radio_buttons if p.GetValue()] == [pulsante]
    finally:
        _chiudi(dlg)


def test_i_giorni_restano_un_gruppo_solo(ambiente):
    dlg = _crea("programmazione", ambiente)
    try:
        assert len(dlg.radio_buttons) == 31
        for giorno, pulsante in dlg.radio_buttons:
            pulsante.SetValue(True)
            assert dlg.get_schedule_info()["date"] == giorno.isoformat()
            assert [p for _g, p in dlg.radio_buttons if p.GetValue()] == [pulsante]
        dlg.chk_no_arbiter.SetValue(True)
        dlg.on_no_arbiter(ambiente.wx.CommandEvent())
        info = dlg.get_schedule_info()
        assert info["arbiter_not_needed"] is True
        assert not dlg.txt_arbiter.IsEnabled()
    finally:
        _chiudi(dlg)


def test_l_esito_del_pgn_si_legge_anche_se_e_lungo(ambiente):
    dlg = _crea("risultato", ambiente)
    try:
        prima = dlg.pannello.GetSizer().GetMinSize().width
        dlg._esito_del_pgn("Formato PGN non valido: " + "mossa illegale " * 30, ambiente.wx.Colour(200, 0, 0))
        assert dlg.pannello.GetSizer().GetMinSize().width > prima
        assert _contenuto_coperto(dlg.pannello)
    finally:
        _chiudi(dlg)


def test_finestra_principale_dentro_lo_schermo_e_pie_di_pagina_di_tre_righe(ambiente, monkeypatch):
    """La finestra principale non scorre: ripristinata sta dentro lo schermo,
    e il pie' di pagina mostra le sue tre righe intere anche a 36 punti.
    Maximize e' sostituita da una finta che annota la misura del momento,
    cioe' quella che torna con Win+freccia giu'. Dalla 10.8.7 il pie' di
    pagina non va a capo: le righe da 80 caratteri restano tre anche quando
    non ci stanno in larghezza, e l'altezza comprende la barra di
    scorrimento orizzontale, che non copre la terza riga."""
    wx = ambiente.wx
    import gui.main_frame as mf

    for nome in ("_check_fide_db_on_startup", "_check_backup_on_startup", "_scan_and_load_initial_tournament", "_check_updates_async"):
        monkeypatch.setattr(mf.MainFrame, nome, lambda self: None)
    ripristinata = []
    monkeypatch.setattr(mf.MainFrame, "Maximize", lambda self, *a: ripristinata.append(self.GetRect()))
    principale = mf.MainFrame(None, "Tornello", dict(ambiente.impostazioni))
    try:
        principale._timer_pie_di_pagina.Stop()
        assert ripristinata and wx.Rect(*AREA).Contains(ripristinata[0])
        testo = principale.status_text
        assert testo.GetWindowStyleFlag() & wx.TE_DONTWRAP
        barra = wx.SystemSettings.GetMetric(wx.SYS_HSCROLL_Y, testo)
        assert testo.GetSize().height - testo.GetClientSize().height >= barra
        riga = testo.GetCharHeight()
        assert testo.GetMinSize().height >= riga * 3 + riga // 2 + barra
        # Due righe da 80 caratteri, come quelle degli indicatori: a 36 punti
        # non ci stanno nei 1280 pixel dello schermo simulato.
        testo.SetValue("Pronto.\n" + "GT  10.7% " * 8 + "\n" + "VB  50.0% " * 8)
        assert testo.GetNumberOfLines() == 3
        righe = [testo.PositionToCoords(testo.XYToPosition(0, r)).y for r in range(3)]
        passo = righe[1] - righe[0]
        assert passo > 0
        assert righe[2] + passo <= testo.GetClientSize().height
        testo.SetSize(wx.Size(testo.GetSize().width // 4, testo.GetSize().height))
        assert testo.GetNumberOfLines() == 3
    finally:
        principale.Destroy()
