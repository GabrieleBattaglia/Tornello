import builtins
import glob
import json
import os
from contextlib import contextmanager

import wx
from GBwx import dentro_area_utile

from gui.dialogs import AccessibleMsgDialog, VisualSettingsDialog
from gui.settings import apply_visual_settings, salva_impostazione, save_settings
from version import __authors__, __date__, __version__

_ = getattr(builtins, "_", lambda s: s)


from config import ARCHIVED_TOURNAMENTS_DIR, user_data_path

# Ogni quanto il pie' di pagina ricalcola le sue percentuali quando non ha il
# focus. Il valore che si muove piu' in fretta, TT, con un decimale cambia
# ogni 23 minuti circa in un turno di 16 giorni: un minuto basta e avanza.
INTERVALLO_PIE_DI_PAGINA_MS = 60 * 1000

# La sezione del manuale che spiega gli acronimi del pie' di pagina, mostrata
# nell'area principale quando il focus arriva sulla barra (issue 54).
SEZIONE_DEGLI_ACRONIMI = "2.3.1"

# Ogni quanto riprovano la proposta di aggiornamento, i suoi esiti e le
# domande dell'avvio quando li trovano con un dialogo aperto (issue 37).
RIPROVA_A_FINESTRA_LIBERA_MS = 1000

# La chiave delle impostazioni con la data, nel formato AAAA-MM-GG, fino alla
# quale l'avviso di avvio sulle copie di sicurezza vecchie resta rinviato.
RINVIO_AVVISO_BACKUP = "backup_check_postponed_until"


def _cartella_predefinita_tornei():
    """La cartella dove proporre di salvare un torneo nuovo, cioe' quella del
    programma. Prima veniva proposta la directory di lavoro corrente, che
    coincide con quella del programma solo se lo si avvia da li'."""
    return os.path.abspath(user_data_path(""))


def _chiave_del_percorso(percorso):
    """Il percorso nella forma in cui si confronta con un altro: assoluto e,
    su Windows, senza differenze di maiuscole e di barre. None e la stringa
    vuota restano come sono."""
    if not percorso:
        return percorso
    return os.path.normcase(os.path.abspath(percorso))


def _nome_della_cartella(percorso):
    """Il nome della cartella che contiene il file, da dire a voce. La radice
    di un disco, che un nome non ce l'ha, si dice per intero."""
    cartella = os.path.dirname(os.path.abspath(percorso))
    return os.path.basename(cartella) or cartella


class FileNonTorneo(ValueError):
    """Un file JSON che non e' un torneo di Tornello, per esempio il database
    dei giocatori o le impostazioni. Il messaggio e' la frase da mostrare."""


def _ha_la_forma_di_un_torneo(dati):
    """Vero se i dati letti da un file hanno la forma di un torneo di
    Tornello: un dizionario con il nome, gli iscritti e i turni. Il database
    dei giocatori, per esempio, ha gli iscritti ma non il nome."""
    return (
        isinstance(dati, dict)
        and isinstance(dati.get("name"), str)
        and isinstance(dati.get("players"), list)
        and isinstance(dati.get("rounds", []), list)
    )


class CustomAccessible(wx.Accessible):
    """Classe custom per MSAA per esporre il nome corretto del controllo ai lettori dello schermo."""

    def __init__(self, win, name):
        super().__init__(win)
        self.name = name

    def GetName(self, childId):
        if childId == wx.ACC_SELF:
            return wx.ACC_OK, self.name
        return wx.ACC_NOT_SUPPORTED, ""


class MainFrame(wx.Frame):
    """
    Finestra principale (MainFrame) di Tornello v9.0.
    Implementa la barra dei menu, l'area centrale dei report, l'albero di navigazione
    a destra e la barra di stato personalizzata per NVDA in basso.
    """

    def __init__(self, parent, title, settings):
        # Titolo iniziale dell'app
        title_str = f"Tornello - {_('Versione {} - Data Rilascio {} - [Nessun Torneo Caricato]').format(__version__, __date__)}"
        super().__init__(parent, title=title_str)
        # Dalla 10.6.3 la finestra ripristinata, quella che torna con
        # Win+freccia giu', sta dentro lo schermo (issue 49): i 768 pixel di
        # prima, con la scala dello schermo al 150 per cento, erano piu' dei
        # 688 disponibili, e il pie' di pagina finiva sotto il bordo. Le
        # misure sono in pixel al 100 per cento, anche il minimo.
        dentro_area_utile(self, (1024, 768))
        self.SetMinSize(self.FromDIP(wx.Size(480, 360)))

        self.settings = settings
        self.current_tournament = None
        self.active_filename = None
        self.creation_data = {}  # Contiene i dati transitori del nuovo torneo in fase di inserimento nell'albero
        self.creation_mode = (
            False  # True se stiamo compilando l'albero per il Nuovo Torneo
        )
        self.last_status_msg = _("Pronto.")
        # L'ultimo testo scritto nel pie' di pagina, per non riscriverlo se
        # non cambia (vedi update_status_display).
        self._testo_pie_di_pagina = None
        # Vero quando il focus logico e' sul pie' di pagina: ce l'ha, oppure
        # ce l'aveva quando Tornello e' passato in secondo piano o si e'
        # aperta una finestra di sistema (vedi _on_focus_pie_di_pagina).
        self._pie_di_pagina_col_focus = False
        # Vero dopo un guasto del ricalcolo automatico gia' scritto in
        # error.log, perche' non si ripeta a ogni minuto.
        self._guasto_pie_di_pagina = False
        # L'aggiornamento del programma (issue 37): la finestra che accompagna
        # lo scaricamento, il blocco delle altre finestre finche' dura, e il
        # segnale che la chiusura serve ad applicarlo, per la quale on_close
        # salta l'invito alla donazione.
        self._dialogo_avanzamento = None
        self._disabilitatore = None
        self._chiusura_per_aggiornamento = False
        # Vero mentre l'albero si svuota e si ricostruisce: gli eventi di
        # selezione che il controllo di Windows manda in quel momento non
        # caricano tornei (vedi _albero_senza_caricamenti).
        self._albero_in_ricostruzione = False
        # I file di torneo non leggibili gia' segnalati, perche' la riga
        # nell'area centrale e l'avviso nella barra non si ripetano a ogni
        # ricostruzione dell'albero.
        self._illeggibili_segnalati = set()

        self._init_ui()
        self._setup_shortcuts()
        # Dalla 10.5.0 il pie' di pagina si aggiorna da solo ogni minuto,
        # finche' non ha il focus (issue 53): il timer gira sul thread
        # principale, solo quando il ciclo degli eventi e' libero, e legge
        # soltanto.
        self._timer_pie_di_pagina = wx.Timer(self)
        self.Bind(
            wx.EVT_TIMER, self._on_timer_pie_di_pagina, self._timer_pie_di_pagina
        )
        self._timer_pie_di_pagina.Start(INTERVALLO_PIE_DI_PAGINA_MS)
        # Dalla 10.8.2 le domande sul database FIDE e sui backup non partono
        # da qui ma da _controlli_di_avvio, quando l'aggiornamento del
        # programma ha finito di parlare: prima si aprivano tutte insieme, e
        # la proposta di aggiornamento compariva sopra la finestra FIDE.
        wx.CallAfter(self._scan_and_load_initial_tournament)
        wx.CallAfter(self._check_updates_async)
        self.Maximize(True)

        # Gestione chiusura per riprodurre il suono
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Suono di avvio applicazione
        from utils import play_sound

        play_sound("avvio")

    def _init_ui(self):
        # Pannello principale di contenimento
        self.top_panel = wx.Panel(self)
        main_layout = wx.BoxSizer(wx.VERTICAL)

        # Splitter per dividere l'area centrale e l'albero a destra
        self.splitter = wx.SplitterWindow(
            self.top_panel, style=wx.SP_3D | wx.SP_LIVE_UPDATE
        )

        # Area Sinistra Pane (Panel + Sizer con etichetta adiacente precedente)
        self.left_pane = wx.Panel(self.splitter)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        self.lbl_main = wx.StaticText(self.left_pane, label=_("Vista principale"))
        self.main_text = wx.TextCtrl(
            self.left_pane, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        self.main_text.SetName(_("Vista principale"))
        left_sizer.Add(self.lbl_main, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 2)
        left_sizer.Add(self.main_text, 1, wx.EXPAND)
        self.left_pane.SetSizer(left_sizer)

        # Area Destra Pane (Panel + Sizer con etichetta adiacente precedente)
        self.right_pane = wx.Panel(self.splitter)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        self.lbl_tree = wx.StaticText(self.right_pane, label=_("Centro comandi"))
        self.tree_ctrl = wx.TreeCtrl(
            self.right_pane, style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT
        )
        self.tree_ctrl.SetName(_("Centro comandi"))
        self.tree_ctrl.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_tree_selection_changed)
        self.tree_ctrl.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.on_tree_item_activated)
        self.tree_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_tree_key_down)
        right_sizer.Add(self.lbl_tree, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 2)
        right_sizer.Add(self.tree_ctrl, 1, wx.EXPAND)
        self.right_pane.SetSizer(right_sizer)

        # Configurazione splitter
        self.splitter.SplitVertically(
            self.left_pane, self.right_pane, self.FromDIP(700)
        )
        self.splitter.SetMinimumPaneSize(self.FromDIP(150))

        main_layout.Add(self.splitter, 1, wx.EXPAND | wx.ALL, 5)

        # Barra di Stato personalizzata in basso (con etichetta adiacente precedente)
        self.lbl_status = wx.StaticText(self.top_panel, label=_("Barra di stato"))
        # L'altezza la decide apply_theme, dal carattere. Dalla 10.8.7 il
        # testo non va mai a capo: ogni riga di indicatori, da 80 caratteri,
        # resta una riga, e i due blocchi da 40 restano intatti anche con un
        # carattere grande o la finestra stretta. Chi vede scorre di lato con
        # la barra orizzontale; lo screen reader legge la riga intera.
        self.status_text = wx.TextCtrl(
            self.top_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.TE_DONTWRAP,
        )
        self.status_text.SetName(_("Barra di stato"))
        self.status_text.Bind(wx.EVT_SET_FOCUS, self._on_focus_pie_di_pagina)
        self.status_text.Bind(wx.EVT_KILL_FOCUS, self._on_uscita_pie_di_pagina)
        main_layout.Add(self.lbl_status, 0, wx.LEFT | wx.RIGHT, 5)
        main_layout.Add(
            self.status_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5
        )

        self.top_panel.SetSizer(main_layout)

        # Barra dei Menu
        self._init_menubar()

        # Applica i colori e font salvati
        self.apply_theme()

        # Messaggio introduttivo iniziale
        self.show_intro_message()

    def _init_menubar(self):
        self.menu_bar = wx.MenuBar()

        # Ogni voce ha la sua lettera: fino alla 10.13.28 Esporta, Elimina ed
        # Esci avevano tutte e tre la E, e la lettera non ne sceglieva
        # nessuna.
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_NEW, _("&Nuovo Torneo...\tCtrl+N"))
        file_menu.Append(wx.ID_OPEN, _("&Apri Torneo...\tCtrl+O"))
        self.item_export_ics = file_menu.Append(
            wx.ID_ANY, _("Es&porta partite pianificate...\tCtrl+Shift+E")
        )
        self.item_delete_tournament = file_menu.Append(
            wx.ID_ANY, _("E&limina Torneo Attivo...\tDelete")
        )
        # Dalla 10.9.0 la finestra di pulizia e' la finestra Copie di
        # sicurezza, che legge, confronta e ripristina le copie (issue 39).
        self.item_backup_cleanup = file_menu.Append(wx.ID_ANY, _("&Copie di sicurezza..."))
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, _("&Esci\tCtrl+Q"))
        self.menu_bar.Append(file_menu, _("&File"))

        # Torneo
        torneo_menu = wx.Menu()
        self.item_enroll = torneo_menu.Append(
            wx.ID_ANY, _("&Iscrizione Giocatori...\tCtrl+I")
        )
        self.item_players = torneo_menu.Append(
            wx.ID_ANY, _("Visualizza &Giocatori\tCtrl+G")
        )
        self.item_round = torneo_menu.Append(
            wx.ID_ANY, _("&Abbinamenti / Turno Corrente\tCtrl+U")
        )
        self.item_standings = torneo_menu.Append(
            wx.ID_ANY, _("&Classifica Corrente\tCtrl+L")
        )
        self.item_rollback = torneo_menu.Append(
            wx.ID_ANY, _("&Time Machine (Annulla Turno)\tCtrl+Z")
        )
        self.item_finalize = torneo_menu.Append(
            wx.ID_ANY, _("&Finalizza Torneo\tCtrl+F")
        )
        self.menu_bar.Append(torneo_menu, _("&Torneo"))

        # Database
        db_menu = wx.Menu()
        self.item_local_db = db_menu.Append(
            wx.ID_ANY, _("&Gestione Giocatori Locale\tCtrl+D")
        )
        self.item_sync_db = db_menu.Append(
            wx.ID_ANY, _("&Sincronizza DB Locale con FIDE\tCtrl+Y")
        )
        self.menu_bar.Append(db_menu, _("&Database"))

        # Visualizza. Ogni voce ha la sua lettera: fino alla 10.13.4 Albero
        # di Destra e Barra di Stato avevano tutte e due la B.
        view_menu = wx.Menu()
        self.item_view_central = view_menu.Append(wx.ID_ANY, _("&Area Centrale\tF5"))
        self.item_view_tree = view_menu.Append(wx.ID_ANY, _("Al&bero di Destra\tF6"))
        self.item_view_status = view_menu.Append(wx.ID_ANY, _("Barra di &Stato\tF7"))
        self.menu_bar.Append(view_menu, _("&Visualizza"))

        # Strumenti
        tools_menu = wx.Menu()
        self.item_fide_query = tools_menu.Append(
            wx.ID_ANY, _("&Consulta Database FIDE\tCtrl+K")
        )
        self.item_fide_update = tools_menu.Append(
            wx.ID_ANY, _("&Verifica Aggiornamenti FIDE")
        )
        tools_menu.Append(
            wx.ID_PREFERENCES, _("&Impostazioni (Audio/Video/Lingua)...\tCtrl+P")
        )
        self.menu_bar.Append(tools_menu, _("&Strumenti"))

        # Aiuto
        help_menu = wx.Menu()
        help_menu.Append(wx.ID_HELP, _("&Guida Accessibile\tF1"))
        self.item_changelog = help_menu.Append(wx.ID_ANY, _("&Changelog\tF2"))
        self.item_credits = help_menu.Append(wx.ID_ABOUT, _("C&rediti\tF3"))
        self.menu_bar.Append(help_menu, _("&Aiuto"))

        self.SetMenuBar(self.menu_bar)

        # Menu Bindings
        self.Bind(wx.EVT_MENU, self.on_exit, id=wx.ID_EXIT)
        self.Bind(wx.EVT_MENU, self.on_preferences, id=wx.ID_PREFERENCES)
        self.Bind(wx.EVT_MENU, self.on_help, id=wx.ID_HELP)
        self.Bind(wx.EVT_MENU, self.on_fide_query, self.item_fide_query)
        self.Bind(wx.EVT_MENU, self.on_fide_update, self.item_fide_update)
        self.Bind(wx.EVT_MENU, self.on_local_db, self.item_local_db)
        self.Bind(wx.EVT_MENU, self.on_sync_db, self.item_sync_db)
        self.Bind(wx.EVT_MENU, self.on_changelog, self.item_changelog)
        self.Bind(wx.EVT_MENU, self.on_credits, self.item_credits)
        self.Bind(wx.EVT_MENU, self.on_new_tournament, id=wx.ID_NEW)
        self.Bind(wx.EVT_MENU, self.on_open_tournament, id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, self.on_export_ics, self.item_export_ics)
        self.Bind(
            wx.EVT_MENU,
            self.on_delete_active_tournament_menu,
            self.item_delete_tournament,
        )
        self.Bind(wx.EVT_MENU, self.on_backup_cleanup, self.item_backup_cleanup)
        self.Bind(wx.EVT_MENU, self.on_enroll_players, self.item_enroll)
        self.Bind(wx.EVT_MENU, self.on_view_players, self.item_players)
        self.Bind(wx.EVT_MENU, self.on_view_current_round, self.item_round)
        self.Bind(wx.EVT_MENU, self.on_view_standings, self.item_standings)
        self.Bind(wx.EVT_MENU, self.on_rollback_round, self.item_rollback)
        self.Bind(wx.EVT_MENU, self.on_finalize_tournament, self.item_finalize)
        self.Bind(wx.EVT_MENU, self.on_view_central, self.item_view_central)
        self.Bind(wx.EVT_MENU, self.on_view_tree, self.item_view_tree)
        self.Bind(wx.EVT_MENU, self.on_view_status, self.item_view_status)

    def _setup_shortcuts(self):
        # Mappa i tasti funzione globali F1-F7
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_hook)

    def on_key_hook(self, event):
        key_code = event.GetKeyCode()
        from utils import play_sound

        if key_code == wx.WXK_F1:
            play_sound("apertura")
            self.on_help(None)
        elif key_code == wx.WXK_F2:
            play_sound("lista")
            self.on_changelog(None)
        elif key_code == wx.WXK_F3:
            play_sound("melodia_del_campanello_1")
            self.on_credits(None)
        elif key_code == wx.WXK_F5:
            self.on_view_central(None)
        elif key_code == wx.WXK_F6:
            self.on_view_tree(None)
        elif key_code == wx.WXK_F7:
            self.on_view_status(None)
        else:
            event.Skip()

    # F5, F6 e F7 e le tre voci del menu Visualizza passano dagli stessi
    # gestori, con lo stesso suono e lo stesso effetto. Fino alla 10.8.4 le
    # voci del menu non avevano gestore, e scelte dal menu non facevano
    # niente. Il menu non sposta il focus: quando la voce arriva, il focus e'
    # ancora dove l'utente l'aveva lasciato, e l'arrivo sul pie' di pagina
    # segue la strada di F7, ricalcolo e sezione degli acronimi compresi.

    def on_view_central(self, event):
        from utils import play_sound

        play_sound("spostamento_f5")
        self.main_text.SetFocus()

    def on_view_tree(self, event):
        from utils import play_sound

        play_sound("spostamento_f6")
        self.tree_ctrl.SetFocus()

    def on_view_status(self, event):
        from utils import play_sound

        play_sound("spostamento_f7")
        # Se il focus e' gia' sul pie' di pagina SetFocus non genera
        # EVT_SET_FOCUS, e il ricalcolo va fatto qui, prima. Negli altri
        # casi lo fa _on_focus_pie_di_pagina, e rifarlo qui costerebbe un
        # secondo giro nella cartella dei backup prima che NVDA legga.
        if self.status_text.HasFocus():
            self.update_status_display()
        self.status_text.SetFocus()

    def apply_theme(self):
        """Applica la combinazione di colori ed il font impostati in settings a tutti i controlli."""
        apply_visual_settings(self.main_text, self.settings)
        apply_visual_settings(self.tree_ctrl, self.settings)
        apply_visual_settings(self.status_text, self.settings, force_dialog=True)

        # Applica il tema anche ai sotto-pannelli e alle etichette adiacenti
        if hasattr(self, "left_pane") and self.left_pane:
            apply_visual_settings(self.left_pane, self.settings)
        if hasattr(self, "right_pane") and self.right_pane:
            apply_visual_settings(self.right_pane, self.settings)
        if hasattr(self, "lbl_main") and self.lbl_main:
            apply_visual_settings(self.lbl_main, self.settings)
        if hasattr(self, "lbl_tree") and self.lbl_tree:
            apply_visual_settings(self.lbl_tree, self.settings)
        if hasattr(self, "lbl_status") and self.lbl_status:
            apply_visual_settings(self.lbl_status, self.settings)

        # Il pie' di pagina e' alto tre righe del suo carattere, piu' il bordo
        # e mezza riga di margine. Fino alla 10.6.2 era alto 60 pixel fissi, e
        # con i caratteri dei dialoghi sopra i 12 punti la terza riga spariva;
        # dalla 10.6.3 segue il carattere, anche quando cambia dalle
        # preferenze, che passano di qui (issue 49).
        # Dalla 10.8.7 sotto le righe c'e' la barra di scorrimento
        # orizzontale, che sta fuori dall'area del testo: si conta anche
        # quando, nel momento della misura, non e' ancora comparsa. Il
        # RichEdit la mostra sempre, spenta quando non serve, e allora la
        # differenza fra le due misure la comprende gia'.
        riga = self.status_text.GetCharHeight()
        fuori = self.status_text.GetSize().height - self.status_text.GetClientSize().height
        barra = wx.SystemSettings.GetMetric(wx.SYS_HSCROLL_Y, self.status_text)
        fuori = max(fuori, self.status_text.GetWindowBorderSize().height + barra)
        self.status_text.SetMinSize(wx.Size(-1, riga * 3 + riga // 2 + fuori))
        self.top_panel.Layout()

    def set_status(self, text):
        """Aggiorna il contenuto della barra di stato personalizzata in basso."""
        self.update_status_display(text)

    def update_status_display(self, action_msg=None):
        """Calcola e visualizza le metriche avanzate di progresso e statistiche di gioco.
        Oltre che dopo ogni azione, dalla 10.5.0 la chiamano il timer di un
        minuto, l'arrivo del focus sul pie' di pagina e F7 (issue 53)."""
        if action_msg is not None:
            self.last_status_msg = action_msg
        else:
            if not hasattr(self, "last_status_msg"):
                self.last_status_msg = _("Pronto.")

        lines = [self.last_status_msg]

        if self.current_tournament:
            # Dalla 10.1.0 il pie' di pagina e' fatto di sole percentuali, per
            # acronimo, spiegate nel manuale: i numeri assoluti stanno nella
            # plancia, qui serve la fotografia dello stato del torneo.
            # Dalla 10.5.0 le due righe sono a larghezza fissa, due blocchi
            # da 40 caratteri ciascuna, per la barra braille.
            from datetime import datetime

            from stats import indicatori_pie_di_pagina, righe_pie_di_pagina

            valori = indicatori_pie_di_pagina(
                self.current_tournament,
                datetime.now(),
                self._data_backup_piu_vecchio(),
                self._data_database_fide(),
            )
            lines.extend(righe_pie_di_pagina(valori))

        # Dalla 10.5.0 il testo si riscrive solo se cambia (issue 53). Anche
        # quando cambia, in wxMSW la scrittura riporta il cursore all'inizio
        # e lo stile si applica selezionando tutto il testo: su un campo con
        # il focus la barra braille salterebbe alla prima riga e NVDA potrebbe
        # annunciare la selezione. Il confronto e' con l'ultimo testo scritto
        # e non con GetValue, che nel RichEdit puo' restituire i ritorni a
        # capo in un'altra forma; ChangeValue non genera EVT_TEXT.
        testo = "\n".join(lines)
        if testo == self._testo_pie_di_pagina:
            return
        self._testo_pie_di_pagina = testo
        self.status_text.ChangeValue(testo)
        apply_visual_settings(self.status_text, self.settings, force_dialog=True)

    def _on_timer_pie_di_pagina(self, event):
        """Ricalcola il pie' di pagina ogni minuto, ma non mentre ha il focus
        logico: sotto il cursore di chi legge non deve cambiare niente. I
        valori si rinfrescano comunque all'arrivo del focus e con F7.
        HasFocus da solo non basta: in wxMSW, con Tornello in secondo piano,
        nessuna finestra ha il focus, e il timer riscriverebbe la barra
        lasciata con il cursore sulla terza riga. Al ritorno la scrittura
        avrebbe riportato il cursore all'inizio, e la barra braille
        ripartirebbe dal messaggio di stato."""
        if self.status_text.HasFocus():
            return
        finestra = self.FindFocus()
        if finestra is not None and finestra is not self:
            # Il focus e' su un'altra finestra di Tornello, quindi non sulla
            # barra, anche se ci e' arrivato passando da una finestra di
            # sistema, senza lasciare traccia in _on_uscita_pie_di_pagina.
            self._pie_di_pagina_col_focus = False
        elif self._pie_di_pagina_col_focus:
            # Tornello e' in secondo piano, o sopra c'e' una finestra di
            # sistema, e il focus tornera' sulla barra: resta com'e'.
            return
        self._ricalcola_pie_di_pagina()

    def _ricalcola_pie_di_pagina(self):
        """Il ricalcolo che nessuno ha chiesto con un'azione, cioe' quello del
        timer e dell'arrivo del focus. Un guasto qui non apre la finestra
        dell'errore imprevisto: dal timer tornerebbe ogni minuto, e dal focus
        senza fine, perche' chiudendola il focus torna sulla barra e il
        ricalcolo si guasta di nuovo. Il guasto va in error.log, con il
        traceback, una volta sola finche' un ricalcolo non riesce; il timer
        continua a girare, cosi' l'aggiornamento riprende da se' appena i dati
        tornano leggibili. Le azioni e F7 premuto sulla barra seguono la
        strada di sempre."""
        try:
            self.update_status_display()
        except Exception as errore:  # noqa: BLE001
            if not self._guasto_pie_di_pagina:
                self._guasto_pie_di_pagina = True
                from gui.settings import _registra

                _registra(f"Aggiornamento automatico del pie' di pagina non riuscito: {errore}")
        else:
            self._guasto_pie_di_pagina = False

    def _on_focus_pie_di_pagina(self, event):
        """Ricalcola il pie' di pagina quando il focus ci arriva, da F7, da
        Tab o dal mouse, prima che lo screen reader lo legga. Il ricalcolo e'
        sincrono: NVDA interroga il controllo solo dopo che il gestore ha
        restituito il thread, e trova gia' i valori nuovi. event.Skip() serve
        perche' il controllo nativo prenda il cursore.
        Non ricalcola quando il focus torna sulla barra che ce l'aveva gia',
        cioe' al ritorno da un'altra applicazione o dopo una finestra di
        sistema: allora il focus non arriva da un'altra finestra di Tornello,
        ma dal nulla o, di passaggio, dalla cornice, e la barra si ritrova
        com'era, con il cursore dove era rimasto. F7 la rinfresca, e
        un'azione fatta nel frattempo l'ha gia' riscritta.
        Dalla 10.6.0, se il focus arriva dall'albero o dall'area principale,
        cioe' con F7, Tab, Maiusc+Tab o un clic, l'area principale mostra la
        sezione del manuale sugli acronimi (issue 54). Non quando torna da un
        dialogo chiuso o da un'altra applicazione: cancellerebbe il report
        appena scritto dall'azione lanciata dalla barra."""
        event.Skip()
        provenienza = event.GetWindow()
        ritorno = self._pie_di_pagina_col_focus and (
            provenienza is None or provenienza is self
        )
        self._pie_di_pagina_col_focus = True
        if not ritorno:
            self._ricalcola_pie_di_pagina()
        if provenienza is self.main_text or provenienza is self.tree_ctrl:
            self._mostra_acronimi()

    def _mostra_acronimi(self):
        """Scrive nell'area principale la sezione del manuale che spiega gli
        acronimi del pie' di pagina, da leggere con F5. La sezione resta
        finche' un'altra azione non riscrive l'area: l'albero, F1, un report o
        un messaggio; il timer del pie' di pagina non la tocca mai.
        Non fa niente senza un torneo aperto, perche' senza percentuali non
        c'e' niente da spiegare, ne' durante la procedura guidata, dove l'area
        spiega il campo dell'albero. Se l'area mostra gia' la sezione non la
        riscrive, cosi' il cursore resta dove l'aveva lasciato chi la stava
        leggendo. Non sposta il focus: NVDA non legge i cambi di un controllo
        che non ce l'ha, e la sostituzione e' silenziosa."""
        if not self.current_tournament or self.creation_mode:
            return
        from utils import sezione_del_manuale

        sezione = sezione_del_manuale(self._leggi_manuale(), SEZIONE_DEGLI_ACRONIMI)
        if not sezione:
            return
        # Il RichEdit puo' restituire i ritorni a capo in un'altra forma, e
        # append_log aggiunge quello finale.
        attuale = self.main_text.GetValue().replace("\r\n", "\n").replace("\r", "\n")
        if attuale.rstrip() == sezione.rstrip():
            return
        self.main_text.Clear()
        self.append_log(sezione)

    def _on_uscita_pie_di_pagina(self, event):
        """Il focus lascia il pie' di pagina. Se va su un'altra finestra di
        Tornello, dialoghi compresi, il focus logico se ne va con lui. Se va in
        un'altra applicazione o in una finestra di sistema, come quella per
        aprire i file, wx non la conosce e GetWindow vale None; se va sulla
        cornice, ci passa soltanto. In quei casi il focus logico resta sulla
        barra, dove tornera'."""
        event.Skip()
        destinazione = event.GetWindow()
        if destinazione is not None and destinazione is not self:
            self._pie_di_pagina_col_focus = False

    @staticmethod
    def _data_backup_piu_vecchio():
        """Data del backup piu' vecchio; None se non ce ne sono.
        Fino alla 10.4.1 restituiva l'eta' in giorni interi: dalla 10.4.2 il
        conto lo fa indicatori_pie_di_pagina, in secondi. Dalla 10.8.11 e' la
        data in cui la copia e' nata, letta dal nome del file, e non piu'
        quella di modifica, che la copia eredita dall'originale."""
        from config import user_data_path
        from utils import elenca_file_di_backup

        tutti, _vecchi = elenca_file_di_backup(user_data_path("backup"))
        if not tutti:
            return None
        return min(f["data"] for f in tutti)

    @staticmethod
    def _data_database_fide():
        """Data di modifica del database FIDE locale; None se non c'e'."""
        from datetime import datetime

        from config import FIDE_DB_LOCAL_FILE

        try:
            return datetime.fromtimestamp(os.path.getmtime(FIDE_DB_LOCAL_FILE))
        except OSError:
            return None

    def append_log(self, text):
        """Aggiunge testo all'area centrale posizionando il cursore all'inizio del blocco inserito."""
        if not text.endswith("\n"):
            text += "\n"
        insertion_point = self.main_text.GetLastPosition()
        self.main_text.AppendText(text)
        self.main_text.SetInsertionPoint(insertion_point)
        self.main_text.ShowPosition(insertion_point)

    def show_intro_message(self):
        self.main_text.Clear()

        from datetime import datetime

        birth_date = datetime(2025, 6, 10, 0, 34)
        now = datetime.now()

        try:
            from dateutil.relativedelta import relativedelta

            delta = relativedelta(now, birth_date)
            y, m, d, h, mi = (
                delta.years,
                delta.months,
                delta.days,
                delta.hours,
                delta.minutes,
            )
        except Exception:
            diff = now - birth_date
            y = diff.days // 365
            rem_days = diff.days % 365
            m = rem_days // 30
            d = rem_days % 30
            h = diff.seconds // 3600
            mi = (diff.seconds % 3600) // 60

        age_parts = []
        if y > 0:
            age_parts.append(
                _("{} anno").format(y) if y == 1 else _("{} anni").format(y)
            )
        if m > 0:
            age_parts.append(
                _("{} mese").format(m) if m == 1 else _("{} mesi").format(m)
            )
        if d > 0:
            age_parts.append(
                _("{} giorno").format(d) if d == 1 else _("{} giorni").format(d)
            )
        if h > 0:
            age_parts.append(_("{} ora").format(h) if h == 1 else _("{} ore").format(h))
        if mi > 0 or not age_parts:
            age_parts.append(
                _("{} minuto").format(mi) if mi == 1 else _("{} minuti").format(mi)
            )

        age_str = ", ".join(age_parts)

        from utils import format_date_locale

        intro = _(
            "Ciao! Benvenuto, sono Tornello v{} - Sviluppato da {}\n"
            "  sono nato il 10/06/2025 alle 00:34 e oggi ho {} e sarò felicissimo di aiutarti\n"
            "  a gestire i tuoi tornei con sistema svizzero/olandese.\n\n"
            "La data del mio ultimo rilascio è {}\n\n"
            "Sono progettato con orgoglio per essere completamente utilizzabile con screen reader (NVDA/JAWS).\n"
            "Premi tab, shift+tab o f5, f6 e f7 per esplorare le mie 3 sezioni principali\n"
            "  ma soprattutto presta attenzione a f6, il centro magico dei comandi, si fa quasi tutto da lì, è la tua plancia, capitano!\n\n"
            "Ed ora un po di tasti rapidi:\n"
            " - F1: Guida / Manuale completo\n"
            " - F2: Visualizza il ChangeLog completo\n"
            " - F3: Visualizza i Crediti e Ringraziamenti\n"
            " - F5: Sposta il focus sulla grande area centrale dei report\n"
            " - F6: Sposta il focus sull'albero di navigazione dei tornei\n"
            " - F7: Sposta il focus sulla barra di stato inferiore\n"
            " - Ctrl+N: Nuovo Torneo (Wizard)\n"
            " - Ctrl+O: Apri Torneo esistente\n"
            " - Ctrl+Shift+E: Esporta le partite pianificate in formato calendario (.ics)\n"
            " - Ctrl+S: Salva lo stato del torneo corrente\n"
            " - Ctrl+I: Finestra di iscrizione e registrazione giocatori\n"
            " - Ctrl+G: Mostra l'elenco dei giocatori iscritti\n"
            " - Ctrl+U: Mostra gli abbinamenti / turno corrente\n"
            " - Ctrl+L: Mostra la classifica del torneo corrente\n"
            " - Ctrl+Z: Time Machine (annulla l'ultimo turno generato)\n"
            " - Ctrl+F: Finalizza il torneo (calcola spareggi, aggiorna database ed archivia)\n"
            " - Ctrl+D: Gestione del Database locale dei giocatori\n"
            " - Ctrl+K: Cerca / consulta direttamente il Database FIDE Ratings\n"
            " - Ctrl+Y: Sincronizzazione del Database locale con il tracciato FIDE\n"
        ).format(
            __version__,
            __authors__,
            age_str,
            format_date_locale(__date__.replace(".", "-")),
        )
        self.append_log(intro)
        self.set_status(_("Pronto. Nessun torneo caricato."))

    def _check_fide_db_on_startup(self):
        """Verifica se il DB FIDE locale ha più di 30 giorni e propone l'aggiornamento."""
        if not self.settings.get("check_fide_at_startup", True):
            return

        from config import FIDE_DB_JSON_LEGACY, FIDE_DB_LOCAL_FILE
        from fide_db import cleanup_legacy_json, fide_db_exists

        # Fallback: se esiste il vecchio JSON ma non il nuovo SQLite, elimina il JSON
        if not fide_db_exists() and os.path.exists(FIDE_DB_JSON_LEGACY):
            cleanup_legacy_json()

        if os.path.exists(FIDE_DB_LOCAL_FILE):
            from datetime import datetime

            # Nel try ci sta soltanto la lettura della data del file, che e'
            # l'unica cosa che puo' fallire per un errore di sistema: prima
            # copriva anche le finestre qui sotto, e se una di quelle si
            # rompeva chi aveva appena risposto di si' non vedeva aprirsi
            # niente e non sapeva perche'. Il ramo else, poche righe piu'
            # giu', le stesse finestre le apre senza rete.
            try:
                file_mod_timestamp = os.path.getmtime(FIDE_DB_LOCAL_FILE)
                file_age_days = (
                    datetime.now() - datetime.fromtimestamp(file_mod_timestamp)
                ).days
            except OSError:
                # Senza la data del file non si puo' decidere niente: si tace e
                # si lascia perdere il controllo, che e' facoltativo.
                return
            if file_age_days >= 30:
                msg = _(
                    "Il database FIDE locale è stato aggiornato {days} giorni fa.\n"
                    "Si consiglia di verificare e scaricare l'aggiornamento più recente.\n"
                    "Vuoi procedere con il controllo e lo scaricamento ora?"
                ).format(days=file_age_days)
                dlg = AccessibleMsgDialog(
                    self, _("Aggiornamento Database FIDE"), msg, style=wx.YES_NO
                )
                if dlg.ShowModal() == wx.ID_YES:
                    dlg.Destroy()
                    from gui.dialogs.fide_update_dialog import FideUpdateDialog

                    update_dlg = FideUpdateDialog(self, self.settings)
                    update_dlg.ShowModal()
                    # Se nel frattempo la finestra e' stata distrutta, per
                    # esempio perche' il programma si chiude, non c'e' piu'
                    # niente da distruggere.
                    if update_dlg:
                        update_dlg.Destroy()
                else:
                    dlg.Destroy()
        else:
            # Nessun DB FIDE trovato: proponi il download
            msg = _(
                "Il database FIDE locale non è presente.\n"
                "È necessario scaricarlo per poter cercare giocatori "
                "nel database FIDE internazionale.\n\n"
                "Vuoi scaricarlo ora?"
            )
            dlg = AccessibleMsgDialog(
                self, _("Database FIDE Mancante"), msg, style=wx.YES_NO
            )
            if dlg.ShowModal() == wx.ID_YES:
                dlg.Destroy()
                from gui.dialogs.fide_update_dialog import FideUpdateDialog

                update_dlg = FideUpdateDialog(self, self.settings)
                update_dlg.ShowModal()
                if update_dlg:
                    update_dlg.Destroy()
            else:
                dlg.Destroy()

    def _controlli_di_avvio(self):
        """Le domande dell'avvio sul database FIDE e sui backup, una dopo
        l'altra. Le chiama la fine del controllo aggiornamenti, dalla 10.8.2:
        prima partivano insieme a lui, ciascuna con il suo CallAfter, e il
        ciclo modale della prima faceva aprire le altre sopra di lei. Da
        sorgente il controllo aggiornamenti finisce subito, e la domanda FIDE
        arriva come prima.
        Un guasto della domanda FIDE non fa saltare quella sui backup, come
        quando partivano separate: la domanda sui backup arriva lo stesso, e
        il guasto va poi alla finestra dell'errore imprevisto."""
        try:
            self._check_fide_db_on_startup()
        finally:
            self._check_backup_on_startup()

    def _finestra_libera(self):
        """Vero se nessun dialogo modale e' aperto. Un dialogo modale di wx,
        o una finestra di sistema come quella di scelta di un file, disabilita
        la finestra principale; i dialoghi di wx si riconoscono anche da
        IsModal."""
        if not self.IsEnabled():
            return False
        return not any(
            isinstance(finestra, wx.Dialog) and finestra.IsModal()
            for finestra in wx.GetTopLevelWindows()
        )

    def _quando_libera(self, funzione, *argomenti):
        """Chiama funzione subito se la finestra e' libera, altrimenti
        riprova ogni secondo finche' non lo diventa: cosi' un messaggio o una
        domanda non si aprono mai sopra un dialogo che l'utente sta usando.
        Se nel frattempo la finestra principale si chiude, lascia perdere."""
        if not self or self.IsBeingDeleted():
            return
        if self._finestra_libera():
            funzione(*argomenti)
        else:
            wx.CallLater(RIPROVA_A_FINESTRA_LIBERA_MS, self._quando_libera, funzione, *argomenti)

    def _check_updates_async(self):
        """Avvia il controllo aggiornamenti in un thread asincrono per non bloccare l'avvio della GUI."""
        import threading

        t = threading.Thread(target=self._run_update_check, daemon=True)
        t.start()

    def _run_update_check(self):
        """Nel thread: il giro intero dell'aggiornamento, condotto da
        gestisci_aggiornamento di GBUtils (issue 37). Tace finche' non c'e'
        una versione nuova, e da sorgente non fa niente. La proposta con le
        note la fa _proponi_aggiornamento, lo scaricamento lo segue
        _avanzamento_aggiornamento, e gli esiti, pochi e tutti utili, si
        raccolgono per mostrarli alla fine, sul thread della finestra.
        Fino alla 10.6.5 il controllo chiamava update_checker, ignorava le
        note e ingoiava qualunque errore con un except: pass."""
        avvisi = []
        try:
            from GBUtils import gestisci_aggiornamento

            from aggiornamenti import API_RELEASE, NOME_APP

            pronto = gestisci_aggiornamento(
                NOME_APP,
                __version__,
                API_RELEASE,
                proponi=self._proponi_aggiornamento,
                avvisa=avvisi.append,
                avanzamento=self._avanzamento_aggiornamento,
                traduci=_,
            )
        except Exception as errore:  # noqa: BLE001 - il thread non ha nessuno a cui passare un guasto
            # Senza aggiornamento il programma prosegue, e le domande
            # dell'avvio devono arrivare lo stesso: il guasto va in error.log.
            from gui.settings import _registra

            _registra(f"Controllo aggiornamenti non riuscito: {errore}")
            pronto = False
        wx.CallAfter(self._fine_aggiornamento, pronto, avvisi)

    def _proponi_aggiornamento(self, versione_attuale, versione_nuova, note):
        """La risposta dell'utente, che gestisci_aggiornamento aspetta.

        Arriva dal thread del controllo, ma la finestra vive su quello
        principale: la domanda si porta li' con CallAfter e il thread resta
        fermo finche' non si sa la risposta, perche' e' lei a dire se
        scaricare. La finestra si apre soltanto quando nessun dialogo modale
        e' aperto, altrimenti si riprova dopo un secondo senza rispondere.
        Col si' si apre la finestra dello scaricamento prima di rispondere,
        cosi' il resto del programma e' gia' bloccato quando lo scaricamento
        comincia. E' il ponte di Dadillo e di Cartella.
        """
        import threading

        risposta = []
        risposto = threading.Event()

        def nella_finestra():
            if not self or self.IsBeingDeleted():
                # La finestra principale non c'e' piu': si risponde di no.
                risposto.set()
                return
            if not self._finestra_libera():
                wx.CallLater(RIPROVA_A_FINESTRA_LIBERA_MS, nella_finestra)
                return
            try:
                if self._chiedi_aggiornamento(versione_attuale, versione_nuova, note):
                    self._apri_avanzamento()
                    risposta.append(True)
            finally:
                risposto.set()

        wx.CallAfter(nella_finestra)
        risposto.wait()
        return bool(risposta)

    def _chiedi_aggiornamento(self, versione_attuale, versione_nuova, note):
        """La finestra con le due versioni e le note: vero per Aggiorna
        adesso, falso per Non adesso, ESC o la chiusura della finestra."""
        from gui.dialogs.update_dialog import UpdateDialog

        dlg = UpdateDialog(self, versione_attuale, versione_nuova, note, self.settings)
        scelta = dlg.ShowModal()
        dlg.Destroy()
        return scelta == wx.ID_YES

    def _apri_avanzamento(self):
        """Apre la finestra dello scaricamento e blocca tutte le altre. Il
        blocco e' un wx.WindowDisabler e non un ShowModal: il ciclo modale
        annidato non tornerebbe finche' la finestra resta aperta, e il thread
        del controllo aspetterebbe la risposta per tutto quel tempo, senza
        mai scaricare. Durante lo scaricamento non si puo' cominciare niente,
        per esempio l'inserimento di un risultato, che la chiusura per
        l'aggiornamento interromperebbe a meta'."""
        from gui.dialogs.update_dialog import UpdateProgressDialog

        dialogo = UpdateProgressDialog(self, self.settings)
        dialogo.Show()
        self._dialogo_avanzamento = dialogo
        self._disabilitatore = wx.WindowDisabler(dialogo)

    def _avanzamento_aggiornamento(self, preso, totale):
        """Nel thread dello scaricamento: i byte presi e il totale, a ogni
        punto percentuale, passano alla finestra sul thread principale."""
        wx.CallAfter(self._mostra_avanzamento, preso, totale)

    def _mostra_avanzamento(self, preso, totale):
        if self and self._dialogo_avanzamento:
            self._dialogo_avanzamento.aggiorna(preso, totale)

    def _chiudi_avanzamento(self):
        """Toglie il blocco e poi chiude la finestra dello scaricamento. In
        quest'ordine: chiusa per prima, con il resto ancora disabilitato,
        Windows darebbe il fuoco a un'altra applicazione."""
        self._disabilitatore = None
        if self._dialogo_avanzamento:
            self._dialogo_avanzamento.Destroy()
        self._dialogo_avanzamento = None

    def _fine_aggiornamento(self, pronto, avvisi):
        """Sul thread della finestra, quando gestisci_aggiornamento ha finito.

        Se l'aggiornamento e' pronto lo script che lo applica e' gia' partito
        e aspetta la chiusura del programma soltanto una trentina di secondi:
        l'esito va nella barra di stato e non in una finestra modale, che
        aspetterebbe chi la chiude, e il programma si chiude da solo, con le
        copie di chiusura di sempre ma senza l'invito alla donazione.
        Altrimenti si mostrano gli esiti raccolti, se ce ne sono, per esempio
        lo scaricamento non riuscito, e poi arrivano le domande dell'avvio.
        """
        if not self:
            return
        self._chiudi_avanzamento()
        if pronto:
            # La chiusura non dipende dal messaggio: scriverlo ricalcola il
            # pie' di pagina, che legge la cartella dei backup e la data del
            # database FIDE, e un guasto li' lascerebbe il programma aperto,
            # con la finestra dell'errore imprevisto e lo script che dopo
            # trenta secondi rinuncia all'aggiornamento. Il guasto va in
            # error.log, come quelli del ricalcolo automatico.
            self._chiusura_per_aggiornamento = True
            if avvisi:
                try:
                    self.set_status(avvisi[-1])
                except Exception as errore:  # noqa: BLE001 - la chiusura che applica l'aggiornamento viene prima del messaggio
                    from gui.settings import _registra

                    _registra(f"Esito dell'aggiornamento non scritto nella barra di stato: {errore}")
            self.Close()
            return
        self._quando_libera(self._dopo_aggiornamento, list(avvisi))

    def _dopo_aggiornamento(self, avvisi):
        """Gli esiti dell'aggiornamento non applicato, se ce ne sono, e poi le
        domande dell'avvio, che arrivano anche se il messaggio degli esiti si
        guasta: il guasto va poi alla finestra dell'errore imprevisto."""
        try:
            if avvisi:
                dlg = AccessibleMsgDialog(self, _("Aggiornamento di Tornello"), "\n".join(avvisi))
                dlg.ShowModal()
                dlg.Destroy()
        finally:
            self._controlli_di_avvio()

    def _check_backup_on_startup(self):
        """Scansiona la cartella dei backup alla ricerca di file più vecchi di 18 mesi."""
        backup_dir = user_data_path("backup")
        if not os.path.exists(backup_dir):
            return

        from datetime import datetime, timedelta

        from config import DATE_FORMAT_ISO

        try:
            from dateutil.relativedelta import relativedelta

            has_dateutil = True
        except ImportError:
            has_dateutil = False

        today = datetime.now()
        # Fino alla 10.8.10 il ripiego senza dateutil era datetime.timedelta,
        # che sulla classe datetime non esiste, e il controllo si fermava.
        diciotto_mesi = relativedelta(months=18) if has_dateutil else timedelta(days=548)
        limit_date = today - diciotto_mesi

        # Stessa lettura della finestra di pulizia, e come li' si tolgono
        # prima le cartelle dell'anno e del mese rimaste vuote.
        from utils import elenca_file_di_backup, rimuovi_cartelle_vuote

        rimuovi_cartelle_vuote(backup_dir)

        # Il No di un avvio precedente rinvia l'avviso di 18 mesi. Fino alla
        # 10.8.10 il rinvio si otteneva portando a oggi la data di modifica
        # dei file vecchi: le copie cambiavano data, e la loro eta' non si
        # poteva piu' ricostruire. Adesso la data sta nelle impostazioni e i
        # file restano come sono; una data illeggibile non rinvia niente.
        impostazioni = self.settings
        rinvio = impostazioni.get(RINVIO_AVVISO_BACKUP) if impostazioni else None
        if rinvio:
            try:
                if today.date() < datetime.strptime(rinvio, DATE_FORMAT_ISO).date():
                    return
            except (TypeError, ValueError):
                pass

        _tutti, vecchi = elenca_file_di_backup(backup_dir, limit_date)
        if not vecchi:
            return

        old_count = len(vecchi)
        # Con un file solo il messaggio va al singolare: fino alla 10.13.27
        # diceva Sono stati individuati 1 file di backup piu' vecchi.
        if old_count == 1:
            msg = _(
                "È stato individuato un file di backup più vecchio di 18 mesi.\n"
                "Si consiglia di effettuare una pulizia per liberare spazio su disco.\n\n"
                "Vuoi aprire la finestra delle copie di sicurezza adesso? La copia più vecchia di 18 mesi sarà già selezionata.\n\n"
                "Nota: Scegliendo 'No', questo controllo non ti verrà riproposto per altri 18 mesi, "
                "e il file resta com'è."
            )
        else:
            msg = _(
                "Sono stati individuati {count} file di backup più vecchi di 18 mesi.\n"
                "Si consiglia di effettuare una pulizia per liberare spazio su disco.\n\n"
                "Vuoi aprire la finestra delle copie di sicurezza adesso? Le copie più vecchie di 18 mesi saranno già selezionate.\n\n"
                "Nota: Scegliendo 'No', questo controllo non ti verrà riproposto per altri 18 mesi, "
                "e i file restano come sono."
            ).format(count=old_count)

        dlg = AccessibleMsgDialog(
            self, _("Pulizia Backup Consigliata"), msg, style=wx.YES_NO
        )
        res = dlg.ShowModal()
        dlg.Destroy()

        if res == wx.ID_YES:
            # La finestra delle copie, con le copie vecchie gia' selezionate:
            # dalla 10.9.0 non c'e' piu' il pulsante Elimina consigliati, e
            # basta premere Elimina selezionati.
            self.on_backup_cleanup(None, seleziona=[f["path"] for f in vecchi])
        elif impostazioni is not None:
            impostazioni[RINVIO_AVVISO_BACKUP] = (today + diciotto_mesi).strftime(
                DATE_FORMAT_ISO
            )
            # Sul disco va la sola chiave del rinvio. save_settings riscrive
            # anche selected_language.json con la lingua delle impostazioni:
            # a chi non ha mai salvato le Preferenze avrebbe rimesso
            # l'italiano dei valori di fabbrica al posto della lingua del
            # sistema. salva_impostazione scrive gia' in error.log il motivo
            # di un salvataggio mancato: in quel caso l'avviso torna al
            # prossimo avvio, che e' il male minore.
            salva_impostazione(
                RINVIO_AVVISO_BACKUP, impostazioni[RINVIO_AVVISO_BACKUP]
            )

    def _scan_and_load_initial_tournament(self):
        """Scansiona i file torneo in corso ed effettua il caricamento automatico se ce n'è solo uno."""
        tournament_files = self._file_dei_tornei()[0]

        # Se c'è esattamente un solo torneo attivo, lo carichiamo all'avvio
        if len(tournament_files) == 1:
            filepath = tournament_files[0]
            self.load_tournament(filepath)
        else:
            self.populate_tree()

    def load_tournament(self, filepath, rebuild_tree=True, tieni_il_precedente=False):
        """Carica un torneo dal file JSON. Se il file non si legge, o non e'
        un torneo, lo dicono un messaggio e la barra di stato. Con
        tieni_il_precedente, che passa Apri Torneo, il torneo aperto prima
        resta aperto, se e' un altro file (vedi _torneo_non_aperto)."""
        try:
            data = self._leggi_il_torneo(filepath)
        except (OSError, ValueError) as errore:
            # ValueError comprende il JSON rovinato, il testo che non e'
            # UTF-8 e FileNonTorneo.
            self._torneo_non_aperto(filepath, errore, rebuild_tree, tieni_il_precedente)
            return
        try:
            self.current_tournament = data
            # Il percorso si tiene nella forma in cui lo scrive l'albero:
            # Apri Torneo puo' restituire lo stesso file con altre maiuscole,
            # e i confronti esatti fra percorsi, come i bersagli del cursore
            # dopo un risultato, non lo riconoscerebbero.
            self.active_filename, elencato = self._percorso_come_nell_albero(filepath)

            # Ricostruisce players_dict per l'interfaccia grafica
            self.current_tournament["players_dict"] = {
                p["id"]: p for p in self.current_tournament.get("players", [])
            }

            t_name = data.get("name", _("Torneo Sconosciuto"))
            self._aggiorna_titolo()
            # Il menu Torneo segue il torneo appena caricato, qualunque strada
            # lo abbia caricato. Fino alla 10.13.12 lo accendeva solo la
            # ricostruzione dell'albero: scegliendo un torneo con le frecce
            # le voci restavano spente, e Ctrl+L e Ctrl+F tacevano.
            self.update_menu_states()

            # Carica il report del turno corrente nell'area centrale
            self.show_current_round_report()

            if rebuild_tree:
                self.populate_tree()
            if elencato:
                esito = _("Torneo '{name}' caricato con successo.").format(name=t_name)
            else:
                # Un file preso fuori dalla cartella del programma e
                # dall'archivio puo' avere lo stesso nome di un torneo
                # dell'albero: la cartella li distingue.
                esito = _(
                    "Torneo '{name}' caricato con successo, dalla cartella {cartella}."
                ).format(name=t_name, cartella=_nome_della_cartella(filepath))
            self.set_status(esito)
        except Exception as errore:
            self._torneo_non_aperto(filepath, errore, rebuild_tree, False)

    def _leggi_il_torneo(self, filepath):
        """I dati del torneo scritto nel file. Un file del programma, come il
        database dei giocatori, le impostazioni o la lingua scelta, e un JSON
        senza la forma di un torneo sollevano FileNonTorneo: fino alla
        10.13.11 Apri Torneo li apriva come tornei, e con il database dei
        giocatori CANC su una persona la toglieva dal database, con il suo
        Elo e il suo storico."""
        from config import PLAYER_DB_FILE
        from gui.settings import SETTINGS_FILE

        nome = os.path.basename(filepath)
        del_programma = {
            _chiave_del_percorso(f)
            for f in (
                PLAYER_DB_FILE,
                SETTINGS_FILE,
                user_data_path("selected_language.json"),
            )
        }
        if _chiave_del_percorso(filepath) in del_programma:
            raise FileNonTorneo(
                _(
                    "Il file {name} è un file del programma, non un torneo, e Tornello non lo apre come torneo."
                ).format(name=nome)
            )
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
        if not _ha_la_forma_di_un_torneo(data):
            raise FileNonTorneo(
                _("Il file {name} non è un torneo di Tornello, e non si apre.").format(
                    name=nome
                )
            )
        return data

    def _torneo_non_aperto(self, filepath, errore, rebuild_tree, tieni_il_precedente):
        """Dice perche' il file non si e' aperto, e lascia il torneo aperto
        in uno stato vero. Con tieni_il_precedente resta aperto il torneo di
        prima, se c'e' ed e' un altro file, e la barra di stato lo dice: fino
        alla 10.13.9 lo riapriva per caso il ridisegno dell'albero, e la
        barra diceva caricato con successo. Altrimenti nessun torneo resta
        aperto: un torneo che non si rilegge non resta in memoria in una
        versione vecchia, che il primo salvataggio riscriverebbe sul file."""
        from utils import play_sound

        if isinstance(errore, FileNonTorneo):
            play_sound("errore")
            self._dialogo_informativo(_("Non è un torneo"), str(errore))
        else:
            wx.MessageBox(
                _("Errore nel caricamento del torneo: {}").format(errore),
                _("Errore"),
                wx.ICON_ERROR,
            )
        if (
            tieni_il_precedente
            and self.current_tournament
            and not self._e_il_torneo_aperto(filepath)
        ):
            self.set_status(
                _("Il torneo non si è aperto: resta aperto '{name}'.").format(
                    name=self.current_tournament.get("name", _("Torneo Sconosciuto"))
                )
            )
            return
        self._nessun_torneo_aperto()
        if rebuild_tree:
            self.populate_tree()
        self.set_status(_("Il torneo non si è aperto: nessun torneo aperto."))

    def _file_dei_tornei(self):
        """I file che l'albero legge da se': i tornei della cartella del
        programma, senza il database dei giocatori e le impostazioni, e
        quelli dell'archivio dei tornei conclusi. Due elenchi, in quest'ordine."""
        from config import PLAYER_DB_FILE

        in_cartella = [
            f
            for f in glob.glob(user_data_path("Tornello - *.json"))
            if "- concluso_" not in os.path.basename(f).lower()
            and os.path.basename(f) != os.path.basename(PLAYER_DB_FILE)
            and os.path.basename(f) != "Tornello - Settings.json"
        ]
        in_archivio = glob.glob(
            os.path.join(ARCHIVED_TOURNAMENTS_DIR, "**", "Tornello - *.json"),
            recursive=True,
        )
        return in_cartella, in_archivio

    def _percorso_come_nell_albero(self, filepath):
        """Il percorso del file nella forma in cui lo scrive l'albero, e se
        l'albero lo trova da se'. Un file fuori dalla cartella del programma
        e dall'archivio resta com'e', reso assoluto."""
        chiave = _chiave_del_percorso(filepath)
        in_cartella, in_archivio = self._file_dei_tornei()
        for f in in_cartella + in_archivio:
            if _chiave_del_percorso(f) == chiave:
                return f, True
        return os.path.abspath(filepath), False

    def _aggiorna_titolo(self):
        """Il titolo della finestra dice il torneo aperto, oppure che non ce
        n'e' nessuno."""
        if self.current_tournament:
            t_name = self.current_tournament.get("name", _("Torneo Sconosciuto"))
            titolo = _("Versione {version} - Data Rilascio {date} - [{name}]").format(
                version=__version__, date=__date__, name=t_name
            )
        else:
            titolo = _(
                "Versione {} - Data Rilascio {} - [Nessun Torneo Caricato]"
            ).format(__version__, __date__)
        self.SetTitle(f"Tornello - {titolo}")

    def _nessun_torneo_aperto(self):
        """Toglie dalla memoria il torneo aperto, e il titolo e il menu
        Torneo lo dicono subito. Fino alla 10.13.9, dopo una finalizzazione,
        il titolo restava sul torneo appena chiuso."""
        self.current_tournament = None
        self.active_filename = None
        self._aggiorna_titolo()
        self.update_menu_states()

    def _e_il_torneo_aperto(self, filepath):
        """Vero se filepath e' il file del torneo aperto, anche scritto con
        altre maiuscole o in un'altra forma."""
        if not (filepath and self.current_tournament and self.active_filename):
            return False
        return _chiave_del_percorso(filepath) == _chiave_del_percorso(
            self.active_filename
        )

    @contextmanager
    def _albero_senza_caricamenti(self):
        """Il blocco in cui l'albero si svuota o perde una voce. Cancellando
        la voce selezionata il controllo di Windows sposta la selezione su
        un'altra voce, e manda un evento di selezione per ognuna: fino alla
        10.13.9 on_tree_selection_changed caricava il torneo di ciascuna,
        cosi' a ogni ricostruzione dell'albero passavano in memoria tutti i
        tornei, e alla fine ne restava aperto uno che nessuno aveva scelto."""
        prima = self._albero_in_ricostruzione
        self._albero_in_ricostruzione = True
        try:
            yield
        finally:
            self._albero_in_ricostruzione = prima

    def show_current_round_report(self):
        """Visualizza l'abbinamento del turno corrente o lo stato del torneo concluso."""
        if not self.current_tournament:
            return

        self.main_text.Clear()
        t_name = self.current_tournament.get("name", _("Torneo Sconosciuto"))
        curr_round = self.current_tournament.get("current_round", 1)
        tot_rounds = self.current_tournament.get("total_rounds", 5)

        report = _("Torneo: {name}\nTurno Corrente: {curr} di {total}\n").format(
            name=t_name, curr=curr_round, total=tot_rounds
        )

        # Mostra abbinamenti se presenti
        rounds = self.current_tournament.get("rounds", [])
        active_round_data = next(
            (r for r in rounds if r.get("round") == curr_round), None
        )
        if active_round_data:
            report += _("Abbinamenti Turno {}:\n").format(curr_round)
            if active_round_data.get("manual_pairing"):
                report += _("Abbinamenti composti a mano dall'arbitro.\n")
            matches = active_round_data.get("matches", [])
            for m in matches:
                w_id = m.get("white_player_id")
                b_id = m.get("black_player_id")
                res = m.get("result")
                # Recupera nomi
                players_dict = self.current_tournament.get("players_dict", {})
                w_player = players_dict.get(w_id, {})
                b_player = players_dict.get(b_id, {}) if b_id else None

                w_name = f"{w_player.get('last_name', '')} {w_player.get('first_name', '')}".strip()
                if b_player:
                    b_name = f"{b_player.get('last_name', '')} {b_player.get('first_name', '')}".strip()
                    res_str = f" [{res}] " if res else " - "
                    report += _("  {white} vs {black}{result}\n").format(
                        white=w_name, black=b_name, result=res_str
                    )
                else:
                    # I punti con il singolare per il bye da un punto, come
                    # nella composizione manuale: fino alla 10.13.27 si leggeva
                    # BYE (1.0 punti).
                    from turno_manuale import testo_punti

                    report += _("  {name} - BYE ({punti})\n").format(
                        name=w_name, punti=testo_punti(self.current_tournament.get("bye_value", 0.5))
                    )
        else:
            report += _("Nessun abbinamento generato per questo turno.\n")
            if not rounds:
                report += _(
                    "\nIl torneo è in fase di preparazione.\n"
                    "Puoi iscrivere altri giocatori premendo Ctrl+I (o dal menù Torneo -> Iscrizioni).\n"
                    "Quando sei pronto ad iniziare il torneo, seleziona 'Inizia torneo' dall'albero a destra.\n"
                )

        self.append_log(report)

    def _get_tree_expansion_state(self, parent_node, expanded_actions):
        if not parent_node.IsOk():
            return
        child, cookie = self.tree_ctrl.GetFirstChild(parent_node)
        while child.IsOk():
            if self.tree_ctrl.IsExpanded(child):
                data = self.tree_ctrl.GetItemData(child)
                if data and isinstance(data, dict) and "action" in data:
                    key = (data.get("action"), data.get("filepath"), data.get("round"))
                    expanded_actions.add(key)
            self._get_tree_expansion_state(child, expanded_actions)
            child, cookie = self.tree_ctrl.GetNextChild(parent_node, cookie)

    def _restore_tree_expansion_state(self, parent_node, expanded_actions):
        if not parent_node.IsOk():
            return
        child, cookie = self.tree_ctrl.GetFirstChild(parent_node)
        while child.IsOk():
            data = self.tree_ctrl.GetItemData(child)
            if data and isinstance(data, dict) and "action" in data:
                key = (data.get("action"), data.get("filepath"), data.get("round"))
                if key in expanded_actions:
                    self.tree_ctrl.Expand(child)
            self._restore_tree_expansion_state(child, expanded_actions)
            child, cookie = self.tree_ctrl.GetNextChild(parent_node, cookie)

    def _find_matching_item(self, parent_node, saved_data):
        if not parent_node.IsOk():
            return None

        child, cookie = self.tree_ctrl.GetFirstChild(parent_node)
        while child.IsOk():
            child_data = self.tree_ctrl.GetItemData(child)
            if (
                child_data
                and isinstance(child_data, dict)
                and isinstance(saved_data, dict)
            ):
                match = True
                for k in ["action", "field_active", "round", "board_num"]:
                    if saved_data.get(k) != child_data.get(k):
                        match = False
                        break
                # Il file si riconosce anche scritto con altre maiuscole: i
                # bersagli del cursore scritti con il percorso del torneo
                # aperto altrimenti non si trovavano, e l'albero restava
                # senza voce scelta.
                if match and _chiave_del_percorso(
                    saved_data.get("filepath")
                ) != _chiave_del_percorso(child_data.get("filepath")):
                    match = False
                if match:
                    if "player" in saved_data and "player" in child_data:
                        if saved_data["player"].get("id") != child_data["player"].get(
                            "id"
                        ):
                            match = False
                    elif "match" in saved_data and "match" in child_data:
                        if saved_data["match"].get("id") != child_data["match"].get(
                            "id"
                        ):
                            match = False

                if match:
                    return child

            res = self._find_matching_item(child, saved_data)
            if res:
                return res

            child, cookie = self.tree_ctrl.GetNextChild(parent_node, cookie)
        return None

    def populate_tree(self, prendi_il_fuoco=True):
        """Costruisce e popola l'albero TreeCtrl destro con la struttura unificata di tutti i tornei.
        Rimessa la voce di prima, l'albero prende il fuoco: dopo un'azione
        fatta dall'albero il cursore resta li'. Con prendi_il_fuoco falso
        l'albero non tocca il fuoco: serve dopo una finestra che si puo'
        aprire anche dalla barra di stato o dall'area centrale, come le copie
        di sicurezza, perche' il fuoco torni dove GBwx lo rimette quando la
        finestra se ne va davvero, cioe' dopo, fra gli eventi successivi."""
        if self.creation_mode:
            return

        expanded_actions = set()
        saved_data = None

        # Gestione override target per il focus
        if hasattr(self, "_tree_restore_target") and self._tree_restore_target:
            saved_data = self._tree_restore_target
            self._tree_restore_target = None
        else:
            try:
                selected_item = self.tree_ctrl.GetSelection()
                if selected_item.IsOk():
                    saved_data = self.tree_ctrl.GetItemData(selected_item)
            except Exception:
                pass

        try:
            if self.tree_root and self.tree_root.IsOk():
                self._get_tree_expansion_state(self.tree_root, expanded_actions)
        except Exception:
            pass

        with self._albero_senza_caricamenti():
            if not prendi_il_fuoco:
                # DeleteAllItems portava il fuoco sull'albero anche senza il
                # SetFocus di _ripristina_la_selezione: cancellata la voce
                # col cursore, il controllo di Windows sposta il cursore
                # sulla voce dopo, e wxMSW, a ogni cambio di selezione che
                # non viene dalle sue funzioni come SelectItem o Unselect,
                # da' il fuoco all'albero (wxTreeCtrl::MSWOnNotify,
                # TVN_SELCHANGING, in src/msw/treectrl.cpp). Misurato sul
                # desktop nascosto con wxPython 4.3.1. Unselect toglie il
                # cursore senza quel SetFocus, e con l'albero senza voce
                # scelta la cancellazione non sposta niente. La voce da
                # rimettere e' gia' in saved_data.
                self.tree_ctrl.Unselect()
            file_illeggibili = self._ricostruisci_albero(expanded_actions)

        if saved_data:
            target_item = self._find_matching_item(self.tree_root, saved_data)
            if target_item and target_item.IsOk():
                self._ripristina_la_selezione(target_item, prendi_il_fuoco)
        if not self.tree_ctrl.GetSelection().IsOk():
            self._cursore_senza_caricare()

        self.update_menu_states()
        self.update_status_display()
        self._segnala_i_file_non_leggibili(file_illeggibili)

    def _cursore_senza_caricare(self):
        """Mette il cursore sulla voce del torneo aperto o, senza torneo
        aperto, sulla voce Nuovo torneo, senza caricare niente. Un albero
        senza voce scelta, per esempio all'avvio o quando la voce di prima
        non c'e' piu', la sceglie da se' quando riceve il fuoco, con F6, TAB
        o un clic: il controllo di Windows prende la prima voce e manda
        l'evento di selezione, e fino alla 10.13.9 si apriva il primo torneo
        dell'elenco, anche al posto di quello aperto. Nuovo torneo non apre
        niente, e un torneo si apre spostandosi con le frecce sulla sua
        voce, come sempre: il cursore fermo sulla voce di un torneo chiuso
        lo farebbe credere aperto."""
        voce = self._voce_del_torneo_aperto()
        if voce is None:
            voce = self._find_matching_item(
                self.tree_root, {"action": "start_new_tournament"}
            )
        if voce and voce.IsOk():
            with self._albero_senza_caricamenti():
                self.tree_ctrl.SelectItem(voce)

    def _ripristina_la_selezione(self, voce, prendi_il_fuoco=True):
        """Rimette il cursore sulla voce che aveva prima della ricostruzione.
        Una voce di un altro torneo non si sceglie come farebbero le frecce,
        perche' caricherebbe quel torneo al posto di quello aperto: fino alla
        10.13.9 Apri Torneo, con il cursore su un altro torneo, lasciava
        aperto quello, mentre la barra diceva caricato il torneo scelto. Con
        un torneo aperto il cursore va sulla sua voce; senza, per esempio
        dopo l'eliminazione del torneo aperto, resta dov'era, senza caricare
        niente. Poi l'albero prende il fuoco, se prendi_il_fuoco e' vero:
        vedi populate_tree."""
        dati = self.tree_ctrl.GetItemData(voce)
        percorso = dati.get("filepath") if isinstance(dati, dict) else None
        if percorso and not self._e_il_torneo_aperto(percorso):
            voce = self._voce_del_torneo_aperto() or voce
            with self._albero_senza_caricamenti():
                self.tree_ctrl.SelectItem(voce)
        else:
            self.tree_ctrl.SelectItem(voce)
        self.tree_ctrl.EnsureVisible(voce)
        if prendi_il_fuoco:
            self.tree_ctrl.SetFocus()

    def _voce_del_torneo_aperto(self):
        """La voce del torneo aperto nell'albero, None se non c'e' un torneo
        aperto. Le voci dei tornei stanno al primo livello e nelle due
        categorie In Preparazione e Tornei Conclusi."""
        if not self.current_tournament:
            return None
        da_guardare = [self.tree_root]
        while da_guardare:
            genitore = da_guardare.pop(0)
            voce, cookie = self.tree_ctrl.GetFirstChild(genitore)
            while voce.IsOk():
                dati = self.tree_ctrl.GetItemData(voce)
                azione = dati.get("action") if isinstance(dati, dict) else None
                if azione == "select_tournament" and self._e_il_torneo_aperto(
                    dati.get("filepath")
                ):
                    return voce
                if azione in ("category_prep", "category_closed"):
                    da_guardare.append(voce)
                voce, cookie = self.tree_ctrl.GetNextChild(genitore, cookie)
        return None

    def _segnala_i_file_non_leggibili(self, file_illeggibili):
        """Dice nella barra di stato, e con una riga per file nell'area
        centrale, i file di torneo che non si leggono, quando si scoprono.
        Fino alla 10.13.10 lo ripeteva a ogni ricostruzione dell'albero: la
        riga si accodava di nuovo all'area centrale, e l'avviso prendeva il
        posto dell'esito dell'azione appena fatta. Un file rimesso a posto
        esce dall'elenco, e se si rovina di nuovo si segnala di nuovo.
        La segnalazione arriva ad azione finita, con wx.CallAfter: molte azioni,
        dopo aver ridisegnato l'albero, riscrivono l'area centrale e la barra
        di stato, e l'avrebbero cancellata prima che qualcuno la leggesse."""
        chiavi = {_chiave_del_percorso(f): (f, e) for f, e in file_illeggibili}
        nuovi = [
            valore
            for chiave, valore in chiavi.items()
            if chiave not in self._illeggibili_segnalati
        ]
        self._illeggibili_segnalati = set(chiavi)
        if nuovi:
            wx.CallAfter(self._mostra_i_file_non_leggibili, nuovi)

    def _mostra_i_file_non_leggibili(self, nuovi):
        """L'avviso in coda all'esito dell'azione nella barra di stato, e una
        riga per file in fondo all'area centrale."""
        if not self:
            return
        # Con un file solo la frase va al singolare: fino alla 10.13.5
        # diceva 1 file di torneo non leggibili.
        avviso = (
            _("Attenzione: un file di torneo non leggibile, dettagli sotto.")
            if len(nuovi) == 1
            else _(
                "Attenzione: {n} file di torneo non leggibili, dettagli sotto."
            ).format(n=len(nuovi))
        )
        # Il messaggio di riposo non e' un esito da conservare.
        esito = getattr(self, "last_status_msg", "")
        if esito and esito not in (_("Pronto."), _("Pronto. Nessun torneo caricato.")):
            avviso = f"{esito} {avviso}"
        self.set_status(avviso)
        for percorso, errore in nuovi:
            self.append_log(
                _("Torneo non leggibile: {nome}. Motivo: {motivo}").format(
                    nome=os.path.basename(percorso), motivo=errore
                )
            )

    def _ricostruisci_albero(self, expanded_actions):
        """Svuota l'albero e lo riempie con i tornei in corso, in preparazione
        e conclusi. Il torneo aperto ha sempre la sua voce, anche se il suo
        file sta fuori dalla cartella del programma e dall'archivio.
        Restituisce i file di torneo che non si leggono, come coppie di
        percorso ed errore. populate_tree la chiama dentro
        _albero_senza_caricamenti."""
        self.tree_ctrl.DeleteAllItems()
        self.tree_root = self.tree_ctrl.AddRoot("Root")

        # Scansiona file
        active_files, closed_files = self._file_dei_tornei()

        in_prep_files = []
        started_files = []
        # Un file di torneo che non si apre, perche' un altro programma lo
        # tiene bloccato o perche' un salvataggio e' finito male, sparirebbe
        # dall'albero senza una parola: chi lo cerca penserebbe di averlo
        # perso, mentre sul disco c'e' ancora. I file si raccolgono qui, e
        # _segnala_i_file_non_leggibili li dice una volta sola.
        file_illeggibili = []

        def leggi(f):
            with open(f, encoding="utf-8") as f_in:
                data = json.load(f_in)
            # Un JSON che non e' un torneo non ha una voce: scelta, non si
            # aprirebbe, perche' load_tournament lo rifiuta.
            if not _ha_la_forma_di_un_torneo(data):
                raise FileNonTorneo(_("non ha la forma di un torneo di Tornello"))
            return data

        for f in active_files:
            try:
                data = leggi(f)
                if data.get("concluded"):
                    continue
                if len(data.get("rounds", [])) == 0:
                    in_prep_files.append((f, data))
                else:
                    started_files.append((f, data))
            except Exception as errore:
                file_illeggibili.append((f, errore))

        concluded_files = []
        for f in closed_files:
            try:
                concluded_files.append((f, leggi(f)))
            except Exception as errore:
                file_illeggibili.append((f, errore))

        # Il torneo aperto ha sempre la sua voce, con i suoi rami, anche
        # quando Apri Torneo lo ha preso da una cartella che l'albero non
        # legge: fino alla 10.13.11 non compariva, e le sue partite non si
        # potevano aprire. I dati sono quelli in memoria, e il ramo e' quello
        # del suo stato. La sua voce dice fra parentesi la cartella da cui
        # e' stato aperto: un torneo con lo stesso nome, come la copia su una
        # chiavetta o l'edizione archiviata, altrimenti avrebbe nell'albero
        # una voce identica, e con NVDA non si distinguerebbero.
        dalla_memoria = None
        if self.current_tournament and self.active_filename:
            elencati = {
                _chiave_del_percorso(f)
                for f, _data in started_files + in_prep_files + concluded_files
            }
            if _chiave_del_percorso(self.active_filename) not in elencati:
                dalla_memoria = _chiave_del_percorso(self.active_filename)
                aperto = (self.active_filename, self.current_tournament)
                if self.current_tournament.get("concluded"):
                    concluded_files.append(aperto)
                elif self.current_tournament.get("rounds"):
                    started_files.append(aperto)
                else:
                    in_prep_files.append(aperto)

        def tra_parentesi(f, *parti):
            """Il seguito dell'etichetta di un torneo: le parti fra parentesi,
            con la cartella in coda per la voce aggiunta dalla memoria."""
            parti = [p for p in parti if p]
            if dalla_memoria and _chiave_del_percorso(f) == dalla_memoria:
                parti.append(
                    _("dalla cartella {cartella}").format(
                        cartella=_nome_della_cartella(f)
                    )
                )
            return f" ({', '.join(parti)})" if parti else ""

        # 1. TORNEI IN CORSO (Attivi)
        for f, data in started_files:
            t_node = self.add_tournament_node(
                self.tree_root, f, data, label_suffix=tra_parentesi(f)
            )
            if not expanded_actions:
                if self._e_il_torneo_aperto(f):
                    # Si apre il torneo, cosi' i suoi rami si vedono, ma i rami
                    # partono chiusi: e' l'utente a decidere cosa espandere, e
                    # per il resto della sessione l'albero ricorda come li ha
                    # lasciati. Fino alla 10.0.0 si aprivano iscritti e turni
                    # (issue 46).
                    self.tree_ctrl.Expand(t_node)

        # 2. TORNEI IN PREPARAZIONE
        if in_prep_files:
            prep_parent = self.tree_ctrl.AppendItem(
                self.tree_root, f"{_('In Preparazione')} ({len(in_prep_files)})"
            )
            self.tree_ctrl.SetItemData(prep_parent, {"action": "category_prep"})
            for f, data in in_prep_files:
                t_node = self.add_tournament_node(
                    prep_parent, f, data, label_suffix=tra_parentesi(f)
                )
                if not expanded_actions:
                    if self._e_il_torneo_aperto(f):
                        self.tree_ctrl.Expand(t_node)
                        self.tree_ctrl.Expand(prep_parent)

        # 3. TORNEI CONCLUSI
        if concluded_files:
            closed_parent = self.tree_ctrl.AppendItem(
                self.tree_root, f"{_('Tornei Conclusi')} ({len(concluded_files)})"
            )
            self.tree_ctrl.SetItemData(closed_parent, {"action": "category_closed"})
            for f, data in concluded_files:
                end_date_str = data.get("end_date")
                month_year = None
                if end_date_str:
                    try:
                        from datetime import datetime

                        dt = datetime.strptime(end_date_str, "%Y-%m-%d")
                        mesi = [
                            _("gennaio"),
                            _("febbraio"),
                            _("marzo"),
                            _("aprile"),
                            _("maggio"),
                            _("giugno"),
                            _("luglio"),
                            _("agosto"),
                            _("settembre"),
                            _("ottobre"),
                            _("novembre"),
                            _("dicembre"),
                        ]
                        month_name = mesi[dt.month - 1].capitalize()
                        month_year = f"{month_name} {dt.year}"
                    except Exception:
                        pass
                label_suffix = tra_parentesi(f, month_year)
                t_node = self.add_tournament_node(
                    closed_parent, f, data, label_suffix=label_suffix
                )
                if not expanded_actions:
                    if self._e_il_torneo_aperto(f):
                        self.tree_ctrl.Expand(t_node)
                        self.tree_ctrl.Expand(closed_parent)

        # 4. NUOVO TORNEO
        new_item = self.tree_ctrl.AppendItem(self.tree_root, _("Nuovo torneo"))
        self.tree_ctrl.SetItemData(new_item, {"action": "start_new_tournament"})

        # 5. AVVIO DEL TORNEO APERTO, se non e' ancora iniziato. E' la voce che
        #    ha preso il posto della domanda che compariva a fine creazione.
        if (
            self.current_tournament
            and self.active_filename
            and not self.current_tournament.get("rounds")
            and not self.current_tournament.get("concluded")
        ):
            avvio_item = self.tree_ctrl.AppendItem(
                self.tree_root,
                _("Avvio torneo: {name}").format(
                    name=self.current_tournament.get("name", "")
                ),
            )
            self.tree_ctrl.SetItemData(
                avvio_item,
                {
                    "action": "start_tournament_matchmaking_action",
                    "filepath": self.active_filename,
                },
            )

        if expanded_actions:
            self._restore_tree_expansion_state(self.tree_root, expanded_actions)
        return file_illeggibili

    def add_round_subnodes(
        self, parent_node, r, data, filepath, players_dict, is_concluded
    ):
        r_num = r.get("round")
        tot_rounds = data.get("total_rounds", 5)

        is_current = (
            r_num == data.get("current_round", 1)
            and len(data.get("rounds", [])) == r_num
        )
        r_label = _("Turno {}").format(r_num)
        if is_current and not is_concluded:
            all_done = True
            for m in r.get("matches", []):
                if m.get("result") is None and m.get("black_player_id") is not None:
                    all_done = False
                    break
            if not all_done:
                r_label = _("Turno corrente ({}/{})").format(r_num, tot_rounds)
        # Dalla 10.12.0 un turno composto a mano dall'arbitro si riconosce
        # dal nome (issue 38).
        if r.get("manual_pairing"):
            r_label = _("{turno}, abbinamenti manuali").format(turno=r_label)

        r_node = self.tree_ctrl.AppendItem(parent_node, r_label)
        self.tree_ctrl.SetItemData(
            r_node,
            {"action": "show_round_report", "filepath": filepath, "round": r_num},
        )

        giocate_parent = self.tree_ctrl.AppendItem(r_node, _("giocate"))
        self.tree_ctrl.SetItemData(
            giocate_parent,
            {"action": "category_giocate", "filepath": filepath, "round": r_num},
        )

        matches_played = []
        matches_to_play = []
        for m in r.get("matches", []):
            if m.get("result") is not None or m.get("black_player_id") is None:
                matches_played.append(m)
            else:
                matches_to_play.append(m)

        # Calcola numero e percentuale per le giocate
        played_count = len(matches_played)
        total_count = len(r.get("matches", []))
        pct = (played_count / total_count * 100.0) if total_count > 0 else 0.0
        giocate_label = f"{_('giocate')} ({played_count}/{total_count}, {pct:.1f}%)"
        self.tree_ctrl.SetItemText(giocate_parent, giocate_label)

        round_matches_sorted = sorted(
            r.get("matches", []), key=lambda x: x.get("id", 0)
        )
        match_id_to_board = {
            m.get("id"): idx for idx, m in enumerate(round_matches_sorted, 1)
        }

        matches_played.sort(key=lambda x: match_id_to_board.get(x.get("id"), 0))

        from datetime import datetime

        from config import DATE_FORMAT_ISO

        def get_match_sort_key(m_item):
            board_num = match_id_to_board.get(m_item.get("id"), 0)
            if m_item.get("is_scheduled") and m_item.get("schedule_info"):
                sched = m_item["schedule_info"]
                try:
                    dt = datetime.strptime(
                        f"{sched.get('date')} {sched.get('time')}",
                        f"{DATE_FORMAT_ISO} %H:%M",
                    )
                    return (0, dt, board_num)
                except Exception:
                    pass
            return (1, datetime.max, board_num)

        matches_to_play.sort(key=get_match_sort_key)

        for m in matches_played:
            w_id = m.get("white_player_id")
            b_id = m.get("black_player_id")
            res = m.get("result")
            w_p = players_dict.get(w_id, {})
            b_p = players_dict.get(b_id, {}) if b_id else None
            w_name = f"{w_p.get('last_name', '')} {w_p.get('first_name', '')}".strip()
            board_num = match_id_to_board.get(m.get("id"), 1)
            if b_p:
                b_name = (
                    f"{b_p.get('last_name', '')} {b_p.get('first_name', '')}".strip()
                )
                match_label = _("Scacchiera {}: {} vs {}").format(
                    board_num, w_name, b_name
                )
            else:
                match_label = _("Scacchiera {}: {} - BYE").format(board_num, w_name)
            if res is not None:
                match_label += f" [{res}]"
            m_node = self.tree_ctrl.AppendItem(giocate_parent, match_label)
            self.tree_ctrl.SetItemData(
                m_node,
                {
                    "action": "activate_match",
                    "filepath": filepath,
                    "match": m,
                    "round": r_num,
                    "board_num": board_num,
                },
            )

        if matches_to_play:
            da_giocare_parent = self.tree_ctrl.AppendItem(
                r_node, f"{_('da giocare')} ({len(matches_to_play)})"
            )
            self.tree_ctrl.SetItemData(
                da_giocare_parent,
                {"action": "category_da_giocare", "filepath": filepath, "round": r_num},
            )
            for m in matches_to_play:
                w_id = m.get("white_player_id")
                b_id = m.get("black_player_id")
                w_p = players_dict.get(w_id, {})
                b_p = players_dict.get(b_id, {})
                w_name = (
                    f"{w_p.get('last_name', '')} {w_p.get('first_name', '')}".strip()
                )
                b_name = (
                    f"{b_p.get('last_name', '')} {b_p.get('first_name', '')}".strip()
                )
                board_num = match_id_to_board.get(m.get("id"), 1)

                if m.get("is_scheduled") and m.get("schedule_info"):
                    sched = m["schedule_info"]
                    from stats import sala_e_arbitro_brevi
                    from utils import format_date_locale

                    # Dalla 10.4.0 anche sala e arbitro, accorciati perche'
                    # l'etichetta resti leggibile: i valori interi li mostra
                    # il dettaglio della partita nell'area centrale, appena
                    # la voce prende il fuoco (issue 52).
                    sala, arbitro = sala_e_arbitro_brevi(sched)
                    match_label = _(
                        "Scacchiera {board}: {white} vs {black} (Pianificata: {date} {time}, sala {room}, arbitro {arbiter})"
                    ).format(
                        board=board_num,
                        white=w_name,
                        black=b_name,
                        date=format_date_locale(sched.get("date")),
                        time=sched.get("time"),
                        room=sala,
                        arbiter=arbitro,
                    )
                else:
                    match_label = _("Scacchiera {}: {} vs {} (Non pianificata)").format(
                        board_num, w_name, b_name
                    )
                m_node = self.tree_ctrl.AppendItem(da_giocare_parent, match_label)
                self.tree_ctrl.SetItemData(
                    m_node,
                    {
                        "action": "activate_match",
                        "filepath": filepath,
                        "match": m,
                        "round": r_num,
                        "board_num": board_num,
                    },
                )

    def add_tournament_node(self, parent, filepath, data, label_suffix=""):
        t_name = data.get("name", os.path.basename(filepath))
        t_node = self.tree_ctrl.AppendItem(parent, f"{t_name}{label_suffix}")
        self.tree_ctrl.SetItemData(
            t_node, {"action": "select_tournament", "filepath": filepath}
        )

        dati_node = self.tree_ctrl.AppendItem(t_node, _("Dati"))
        self.tree_ctrl.SetItemData(
            dati_node, {"action": "show_data", "filepath": filepath}
        )

        from utils import format_date_locale

        name_item = self.tree_ctrl.AppendItem(
            dati_node, _("Nome torneo: {}").format(data.get("name"))
        )
        self.tree_ctrl.SetItemData(
            name_item,
            {"action": "show_data", "filepath": filepath, "field_active": "name"},
        )

        site_item = self.tree_ctrl.AppendItem(
            dati_node, _("Luogo (Site): {}").format(data.get("site", _("N/D")))
        )
        self.tree_ctrl.SetItemData(
            site_item,
            {"action": "show_data", "filepath": filepath, "field_active": "site"},
        )

        start_item = self.tree_ctrl.AppendItem(
            dati_node,
            _("Data inizio: {}").format(format_date_locale(data.get("start_date"))),
        )
        self.tree_ctrl.SetItemData(
            start_item,
            {"action": "show_data", "filepath": filepath, "field_active": "start_date"},
        )

        end_item = self.tree_ctrl.AppendItem(
            dati_node,
            _("Data fine: {}").format(format_date_locale(data.get("end_date"))),
        )
        self.tree_ctrl.SetItemData(
            end_item,
            {"action": "show_data", "filepath": filepath, "field_active": "end_date"},
        )

        tc = data.get("time_control", "Standard")
        cat = data.get("tournament_category")
        if not cat and isinstance(tc, dict):
            from stats import classify_tournament_category

            cat = classify_tournament_category(
                tc.get("minutes", 60), tc.get("increment", 0)
            )
        if not cat:
            cat = "standard"

        cat_map = {"standard": _("Standard"), "rapid": _("Rapid"), "blitz": _("Blitz")}
        cat_disp = cat_map.get(cat.lower(), cat.capitalize())

        if isinstance(tc, dict):
            tc_disp = _("{} min + {} sec ({})").format(
                tc.get("minutes", 60), tc.get("increment", 0), cat_disp
            )
        else:
            tc_disp = f"{tc} ({cat_disp})"
        tc_item = self.tree_ctrl.AppendItem(
            dati_node, _("Tempo riflessione: {}").format(tc_disp)
        )
        self.tree_ctrl.SetItemData(
            tc_item,
            {
                "action": "show_data",
                "filepath": filepath,
                "field_active": "time_control",
            },
        )

        arb_item = self.tree_ctrl.AppendItem(
            dati_node, _("Arbitro Capo: {}").format(data.get("chief_arbiter", _("N/D")))
        )
        self.tree_ctrl.SetItemData(
            arb_item,
            {
                "action": "show_data",
                "filepath": filepath,
                "field_active": "chief_arbiter",
            },
        )

        dep_item = self.tree_ctrl.AppendItem(
            dati_node,
            _("Collaboratori: {}").format(
                data.get("deputy_chief_arbiters", "") or _("Nessuno")
            ),
        )
        self.tree_ctrl.SetItemData(
            dep_item,
            {
                "action": "show_data",
                "filepath": filepath,
                "field_active": "deputy_chief_arbiters",
            },
        )

        fed_item = self.tree_ctrl.AppendItem(
            dati_node,
            _("Codice Federazione: {}").format(data.get("federation_code", "ITA")),
        )
        self.tree_ctrl.SetItemData(
            fed_item,
            {
                "action": "show_data",
                "filepath": filepath,
                "field_active": "federation_code",
            },
        )

        col_raw = data.get("initial_board1_color_setting", "white1")
        col_disp_map = {
            "white1": _("Bianco (scelto dall'arbitro)"),
            "black1": _("Nero (scelto dall'arbitro)"),
            "random": _("Casuale (scelto da {app})").format(app="Tornello"),
        }
        col_val = col_disp_map.get(col_raw, _("Bianco (scelto dall'arbitro)"))
        col_item = self.tree_ctrl.AppendItem(
            dati_node, _("Colore al giocatore più forte: {}").format(col_val)
        )
        self.tree_ctrl.SetItemData(
            col_item,
            {
                "action": "show_data",
                "filepath": filepath,
                "field_active": "color_board1",
            },
        )

        bye_item = self.tree_ctrl.AppendItem(
            dati_node, _("Valore del BYE: {}").format(data.get("bye_value", 0.5))
        )
        self.tree_ctrl.SetItemData(
            bye_item,
            {"action": "show_data", "filepath": filepath, "field_active": "bye_value"},
        )
        players = data.get("players", [])
        iscritti_node = self.tree_ctrl.AppendItem(
            t_node, f"{_('iscritti')} ({len(players)})"
        )
        self.tree_ctrl.SetItemData(
            iscritti_node, {"action": "show_players", "filepath": filepath}
        )

        for p in players:
            p_label = _("{last} {first} (Elo: {elo}, Naz: {fed})").format(
                last=p.get("last_name", ""),
                first=p.get("first_name", ""),
                elo=int(p.get("initial_elo", 1399)),
                fed=p.get("federation", "ITA"),
            )
            if p.get("withdrawn"):
                # Parola intera e non la sigla: allo screen reader "RIT" non
                # dice nulla, ed e' l'unico modo per sapere dall'albero che il
                # giocatore ha lasciato il torneo.
                p_label += _(", ritirato")
            p_node = self.tree_ctrl.AppendItem(iscritti_node, p_label)
            self.tree_ctrl.SetItemData(
                p_node,
                {"action": "show_player_detail", "filepath": filepath, "player": p},
            )

        add_p_node = self.tree_ctrl.AppendItem(iscritti_node, _("aggiungi giocatore"))
        self.tree_ctrl.SetItemData(
            add_p_node, {"action": "add_player_action", "filepath": filepath}
        )

        rounds = data.get("rounds", [])
        turni_node = self.tree_ctrl.AppendItem(t_node, f"{_('turni')} ({len(rounds)})")
        self.tree_ctrl.SetItemData(
            turni_node, {"action": "show_rounds", "filepath": filepath}
        )

        players_dict = {p["id"]: p for p in players}
        is_concluded = data.get("concluded", False)

        if len(rounds) > 0:
            completed_rounds = []
            pending_round = None
            for r in rounds:
                all_done = True
                for m in r.get("matches", []):
                    if m.get("result") is None and m.get("black_player_id") is not None:
                        all_done = False
                        break
                if all_done:
                    completed_rounds.append(r)
                else:
                    pending_round = r

            if completed_rounds:
                completati_parent = self.tree_ctrl.AppendItem(
                    turni_node, f"{_('Completati')} ({len(completed_rounds)})"
                )
                self.tree_ctrl.SetItemData(
                    completati_parent, {"action": "show_rounds", "filepath": filepath}
                )
                for r in completed_rounds:
                    self.add_round_subnodes(
                        completati_parent, r, data, filepath, players_dict, is_concluded
                    )

            if pending_round:
                self.add_round_subnodes(
                    turni_node,
                    pending_round,
                    data,
                    filepath,
                    players_dict,
                    is_concluded,
                )
            elif not is_concluded:
                tot_rounds = data.get("total_rounds", 5)
                last_r_num = len(rounds)
                if last_r_num < tot_rounds:
                    action_node = self.tree_ctrl.AppendItem(
                        turni_node, _("calcola il turno successivo")
                    )
                    self.tree_ctrl.SetItemData(
                        action_node,
                        {"action": "generate_next_round_action", "filepath": filepath},
                    )
                elif last_r_num == tot_rounds:
                    action_node = self.tree_ctrl.AppendItem(
                        turni_node, _("Finalizza il torneo")
                    )
                    self.tree_ctrl.SetItemData(
                        action_node,
                        {"action": "finalize_tournament_action", "filepath": filepath},
                    )
        else:
            if not is_concluded:
                node_act = self.tree_ctrl.AppendItem(
                    turni_node, _("calcola il turno 1")
                )
                self.tree_ctrl.SetItemData(
                    node_act,
                    {
                        "action": "start_tournament_matchmaking_action",
                        "filepath": filepath,
                    },
                )

        # Sotto-nodo: Classifica
        classifica_node = self.tree_ctrl.AppendItem(t_node, _("Classifica"))
        self.tree_ctrl.SetItemData(
            classifica_node, {"action": "show_standings", "filepath": filepath}
        )

        # Sotto-nodo: regole di spareggio
        tiebreaks_node = self.tree_ctrl.AppendItem(t_node, _("regole di spareggio"))
        self.tree_ctrl.SetItemData(
            tiebreaks_node, {"action": "show_tiebreaks", "filepath": filepath}
        )

        # Sotto-nodo: partite
        total_pgn_matches = sum(
            1 for r in rounds for m in r.get("matches", []) if m.get("pgn")
        )
        partite_pgn_node = self.tree_ctrl.AppendItem(
            t_node, _("Partite PGN") + f" ({total_pgn_matches})"
        )
        self.tree_ctrl.SetItemData(
            partite_pgn_node, {"action": "show_pgn_matches_list", "filepath": filepath}
        )
        for r in rounds:
            r_num = r.get("round")
            round_matches_sorted = sorted(
                r.get("matches", []), key=lambda x: x.get("id", 0)
            )

            # Check if there is any match in this round with PGN
            has_pgn_in_round = any(m.get("pgn") for m in round_matches_sorted)
            if not has_pgn_in_round:
                continue

            pgn_count_in_round = sum(1 for m in round_matches_sorted if m.get("pgn"))
            r_pgn_node = self.tree_ctrl.AppendItem(
                partite_pgn_node, f"T{r_num} ({pgn_count_in_round})"
            )
            self.tree_ctrl.SetItemData(
                r_pgn_node,
                {
                    "action": "show_pgn_matches_list",
                    "filepath": filepath,
                    "round": r_num,
                },
            )

            match_id_to_board = {
                m.get("id"): idx for idx, m in enumerate(round_matches_sorted, 1)
            }
            for m in round_matches_sorted:
                if m.get("pgn"):
                    w_id = m.get("white_player_id")
                    b_id = m.get("black_player_id")
                    res = m.get("result")
                    w_p = players_dict.get(w_id, {})
                    b_p = players_dict.get(b_id, {}) if b_id else None
                    w_name = f"{w_p.get('last_name', '')} {w_p.get('first_name', '')}".strip()
                    board_num = match_id_to_board.get(m.get("id"), 1)
                    if b_p:
                        b_name = f"{b_p.get('last_name', '')} {b_p.get('first_name', '')}".strip()
                        label = _("Scacchiera {}: {} vs {} [{}]").format(
                            board_num, w_name, b_name, res
                        )
                    else:
                        label = _("Scacchiera {}: {} - BYE [{}]").format(
                            board_num, w_name, res
                        )
                    m_node = self.tree_ctrl.AppendItem(r_pgn_node, label)
                    self.tree_ctrl.SetItemData(
                        m_node,
                        {
                            "action": "show_single_pgn",
                            "filepath": filepath,
                            "match": m,
                            "round": r_num,
                            "board_num": board_num,
                        },
                    )

        return t_node

    def on_tree_selection_changed(self, event):
        if not self or not getattr(self, "tree_ctrl", None) or not self.tree_ctrl:
            return
        # Le selezioni che il controllo fa da se' mentre l'albero si svuota
        # non sono scelte di chi usa il programma.
        if getattr(self, "_albero_in_ricostruzione", False):
            return
        try:
            item = event.GetItem()
            if not item or not item.IsOk():
                return
        except Exception:
            return

        try:
            data = self.tree_ctrl.GetItemData(item)
        except Exception:
            return

        if not data or not isinstance(data, dict):
            return

        if self.creation_mode:
            field = data.get("field")
            action = data.get("action")
            self.main_text.Clear()
            if field == "name":
                self.append_log(
                    _(
                        "Nome Torneo\n\nSeleziona questa voce (premi Invio o doppio clic) per impostare il nome del torneo. Questo campo è obbligatorio."
                    )
                )
            elif field == "site":
                self.append_log(
                    _(
                        "Luogo (Site)\n\nSeleziona questa voce per impostare il luogo del torneo (es. città o 'Online')."
                    )
                )
            elif field == "start_date":
                self.append_log(
                    _(
                        "Data inizio\n\nSeleziona questa voce per impostare la data di inizio del torneo."
                    )
                )
            elif field == "end_date":
                self.append_log(
                    _(
                        "Data fine\n\nSeleziona questa voce per impostare la data di conclusione del torneo."
                    )
                )
            elif field == "rounds":
                self.append_log(
                    _(
                        "Numero turni\n\nSeleziona questa voce per definire il numero totale di turni previsti."
                    )
                )
            elif field == "time_control":
                self.append_log(
                    _(
                        "Tempo riflessione\n\nSeleziona questa voce per impostare la cadenza di gioco (es. '60+0' o '15+10'). Questo campo è obbligatorio."
                    )
                )
            elif field == "save_path":
                self.append_log(
                    _(
                        "Cartella di salvataggio\n\nSeleziona questa voce per modificare la directory in cui verrà salvato il file del torneo."
                    )
                )
            elif field == "chief_arbiter":
                self.append_log(
                    _(
                        "Arbitro Capo\n\nSeleziona questa voce per indicare il nome dell'Arbitro Capo."
                    )
                )
            elif field == "deputy_chief_arbiters":
                self.append_log(
                    _(
                        "Collaboratori / Vice Arbitri\n\nSeleziona questa voce per elencare eventuali collaboratori o vice arbitri."
                    )
                )
            elif field == "federation_code":
                self.append_log(
                    _(
                        "Codice Federazione\n\nSeleziona questa voce per impostare il codice federazione (es. ITA)."
                    )
                )
            elif field == "color_board1":
                self.append_log(
                    _(
                        "Colore al giocatore più forte\n\nSeleziona questa voce per definire se il primo giocatore in tabellone avrà il Bianco, il Nero, o se verrà scelto a caso al turno 1."
                    )
                )
            elif field == "bye_value":
                self.append_log(
                    _(
                        "Valore del BYE\n\nSeleziona questa voce per definire il punteggio del BYE per i giocatori senza avversario (default 0.5)."
                    )
                )
            elif action == "wizard_next":
                self.append_log(
                    _(
                        "Procedi\n\nSeleziona questa voce per concludere la configurazione dei parametri e passare all'iscrizione dei giocatori."
                    )
                )
            elif action == "wizard_back":
                self.append_log(
                    _(
                        "Indietro\n\nSeleziona questa voce per annullare la creazione del torneo e tornare alla schermata iniziale."
                    )
                )
            return

        filepath = data.get("filepath")
        if filepath and not self._e_il_torneo_aperto(filepath):
            self.load_tournament(filepath, rebuild_tree=False)
            # Un file che non si e' aperto l'ha gia' detto il messaggio, e
            # quello che segue non vale per un altro torneo.
            if not self._e_il_torneo_aperto(filepath):
                return

        action = data.get("action")
        if action == "select_tournament":
            self.show_tournament_data_verbose()
        elif action == "show_data":
            self.show_tournament_data_verbose(data.get("field_active"))
        elif action == "show_players":
            self.show_players_list_verbose()
        elif action == "show_player_detail":
            self.show_player_detail_verbose(data.get("player"))
        elif action == "show_rounds":
            self.show_rounds_report_verbose()
        elif action == "show_round_report":
            self.show_single_round_report_verbose(data.get("round"))
        elif action == "activate_match":
            self.show_match_detail_verbose(
                data.get("match"), data.get("round"), data.get("board_num")
            )
        elif action == "show_pgn_matches_list":
            self.show_pgn_matches_list_verbose(data.get("round"))
        elif action == "show_single_pgn":
            self.show_single_pgn_text(data.get("match"))
        elif action == "show_standings":
            self.show_standings_verbose()
        elif action == "show_tiebreaks":
            self.show_tiebreaks_verbose()
        elif action == "category_prep":
            self.main_text.Clear()
            self.append_log(
                _(
                    "Tornei In Preparazione\n\nIn questa sezione trovi i tornei creati ma non ancora avviati (ossia per cui non sono ancora stati generati gli abbinamenti del primo turno)."
                )
            )
        elif action == "category_closed":
            self.main_text.Clear()
            self.append_log(
                _(
                    "Tornei Conclusi\n\nIn questa sezione sono archiviati i tornei per cui è stata completata l'elaborazione dei turni e che sono stati finalizzati."
                )
            )
        elif action == "category_giocate":
            self.main_text.Clear()
            round_num = data.get("round")
            self.append_log(
                _(
                    "Partite Giocate - Turno {num}\n\nQuesta sezione elenca le partite del turno {num} che sono già state disputate o che hanno un risultato registrato."
                ).format(num=round_num)
            )
        elif action == "category_da_giocare":
            self.main_text.Clear()
            round_num = data.get("round")
            self.append_log(
                _(
                    "Partite Da Giocare - Turno {num}\n\nQuesta sezione elenca le partite ancora da disputare nel turno {num}.\n\nSelezionando una partita e premendo Invio (o facendo doppio clic) potrai registrarne il risultato o pianificarne data e ora."
                ).format(num=round_num)
            )
        elif action == "add_player_action":
            self.main_text.Clear()
            self.append_log(
                _(
                    "Aggiungi Giocatore\n\nFai doppio clic o premi Invio su questa voce per aprire la finestra di iscrizione e inserimento di nuovi giocatori al torneo."
                )
            )
        elif action == "start_tournament_matchmaking_action":
            self.main_text.Clear()
            self.append_log(
                _(
                    "Genera Turno\n\nFai doppio clic o premi Invio su questa voce per avviare il torneo generando gli abbinamenti del Turno 1."
                )
            )
        elif action == "generate_next_round_action":
            self.main_text.Clear()
            self.append_log(
                _(
                    "Genera Turno\n\nFai doppio clic o premi Invio su questa voce per generare gli abbinamenti del turno successivo."
                )
            )
        elif action == "finalize_tournament_action":
            self.main_text.Clear()
            self.append_log(
                _(
                    "Finalizza Torneo\n\nFai doppio clic o premi Invio su questa voce per concludere il torneo e salvarlo tra i tornei conclusi."
                )
            )

    def show_tournament_data_verbose(self, highlight_field=None):
        if not self.current_tournament:
            return
        t = self.current_tournament
        self.main_text.Clear()

        info = []
        info.append(_("INFORMAZIONI DETTAGLIATE DEL TORNEO"))
        info.append(_("Nome Torneo: {name}").format(name=t.get("name", "N/D")))
        info.append(_("Luogo: {site}").format(site=t.get("site", "N/D")))
        info.append(
            _("Data Inizio: {start_date}").format(start_date=t.get("start_date", "N/D"))
        )
        info.append(
            _("Data Fine: {end_date}").format(end_date=t.get("end_date", "N/D"))
        )

        tc = t.get("time_control", {})
        cat = t.get("tournament_category")
        if not cat and isinstance(tc, dict):
            from stats import classify_tournament_category

            cat = classify_tournament_category(
                tc.get("minutes", 60), tc.get("increment", 0)
            )
        if not cat:
            cat = "standard"
        cat_disp = cat.capitalize()
        if isinstance(tc, dict):
            tc_str = f"{tc.get('minutes', 60)} min + {tc.get('increment', 0)} sec ({cat_disp})"
        else:
            tc_str = f"{tc} ({cat_disp})"
        info.append(_("Tempo di Riflessione: {tc}").format(tc=tc_str))
        info.append(
            _("Arbitro Capo: {arbiter}").format(arbiter=t.get("chief_arbiter", "N/D"))
        )
        info.append(
            _("Collaboratori / Vice Arbitri: {arbiters}").format(
                arbiters=t.get("deputy_chief_arbiters") or _("Nessuno")
            )
        )
        info.append(
            _("Codice Federazione: {fed}").format(fed=t.get("federation_code", "ITA"))
        )

        col_raw = t.get("initial_board1_color_setting", "white1")
        col_disp_map = {
            "white1": _("Bianco (scelto dall'arbitro)"),
            "black1": _("Nero (scelto dall'arbitro)"),
            "random": _("Casuale (scelto da {app})").format(app="Tornello"),
        }
        info.append(
            _(
                "Colore assegnato al giocatore più forte in scacchiera 1: {color}"
            ).format(color=col_disp_map.get(col_raw, _("Bianco (scelto dall'arbitro)")))
        )
        info.append(_("Valore del BYE: {val}").format(val=t.get("bye_value", 0.5)))
        info.append(
            _("Categoria Elo Torneo: {cat}").format(
                cat=t.get("tournament_category", "Standard")
            )
        )
        info.append(
            _("Numero totale di turni: {rounds}").format(
                rounds=t.get("total_rounds", 5)
            )
        )
        info.append(
            _("Turno corrente: {round}").format(round=t.get("current_round", 1))
        )
        info.append(
            _("Giocatori iscritti: {count}").format(count=len(t.get("players", [])))
        )
        self.append_log("\n".join(info))

    def show_tiebreaks_verbose(self):
        if not self.current_tournament:
            return
        self.main_text.Clear()

        from tiebreak_criteria import (
            get_criterion_display_name,
            get_default_tiebreaks,
            migrate_old_tiebreaks,
        )

        # Ottieni la priorità dei tiebreaks con retrocompatibilità
        raw_tiebreaks = self.current_tournament.get("tiebreaks", None)
        if raw_tiebreaks is None:
            tiebreak_entries = get_default_tiebreaks()
        elif raw_tiebreaks and isinstance(raw_tiebreaks[0], str):
            tiebreak_entries = migrate_old_tiebreaks(raw_tiebreaks)
        else:
            tiebreak_entries = raw_tiebreaks

        lines = []
        lines.append(_("REGOLE DI SPAREGGIO CONFIGURATE"))
        lines.append(_("Ordine di priorità dei criteri di spareggio attivi:\n"))

        for idx, entry in enumerate(tiebreak_entries, 1):
            if isinstance(entry, dict):
                nome = get_criterion_display_name(
                    entry.get("key", ""), entry.get("modifiers")
                )
            else:
                # Retrocompatibilità vecchio formato stringa
                criteri_nomi = {
                    "points": _("Punti Totali"),
                    "withdrawn": _("Ritirato"),
                    "buchholz_cut1": _("Buchholz Cut-1"),
                    "buchholz": _("Buchholz Totale"),
                    "aro": _("ARO (Average Rating of Opponents)"),
                    "initial_elo": _("Elo Iniziale (Seed)"),
                    "sonneborn_berger": _("Sonneborn-Berger"),
                    "direct_encounter": _("Scontro Diretto"),
                    "played_rounds_rep": _("Turni Giocati (REP)"),
                    "number_of_wins": _("Maggior Numero di Vittorie"),
                    "number_of_blacks": _("Incontri col Nero"),
                    "cumulative": _("Punteggio Progressivo"),
                }
                nome = criteri_nomi.get(entry, entry)
            lines.append(f"  {idx}. {nome}")

        lines.append(
            _(
                "Fai doppio clic o premi Invio su questa voce per modificare le regole di spareggio."
            )
        )

        self.append_log("\n".join(lines))
        self.main_text.SetInsertionPoint(0)
        self.main_text.ShowPosition(0)

    def on_configure_tiebreaks(self):
        from gui.dialogs import TiebreakConfigDialog
        from utils import play_sound

        play_sound("apertura", self.current_tournament)
        dlg = TiebreakConfigDialog(self, self.current_tournament)
        if dlg.ShowModal() == wx.ID_OK:
            self._save_state()
            self.show_tiebreaks_verbose()
        dlg.Destroy()

    def show_players_list_verbose(self):
        if not self.current_tournament:
            return
        t = self.current_tournament
        self.main_text.Clear()

        info = []
        info.append(
            _("GIOCATORI ISCRITTI ({count})").format(count=len(t.get("players", [])))
        )

        for idx, p in enumerate(t.get("players", [])):
            withdrawn_str = f" [{_('RITIRATO')}]" if p.get("withdrawn") else ""
            info.append(
                _("{num}. {last} {first} (Elo: {elo}, Naz: {fed}){withdrawn}").format(
                    num=idx + 1,
                    last=p.get("last_name", ""),
                    first=p.get("first_name", ""),
                    elo=int(p.get("initial_elo", 1399)),
                    fed=p.get("federation", "ITA"),
                    withdrawn=withdrawn_str,
                )
            )

        self.append_log("\n".join(info))

    def show_player_detail_verbose(self, p):
        if not p or not self.current_tournament:
            return
        self.main_text.Clear()

        info = []
        info.append(_("SCHEDA DETTAGLIATA GIOCATORE"))
        info.append(_("Cognome: {last_name}").format(last_name=p.get("last_name", "")))
        info.append(_("Nome: {first_name}").format(first_name=p.get("first_name", "")))
        info.append(
            _("Elo Iniziale: {elo}").format(elo=int(p.get("initial_elo", 1399)))
        )
        info.append(_("ID Interno: {id}").format(id=p.get("id", "")))
        info.append(
            _("Fide ID: {fide}").format(fide=p.get("fide_id_num_str") or _("N/D"))
        )
        info.append(_("Sesso: {gender}").format(gender=p.get("gender", "M")))
        info.append(_("Federazione: {fed}").format(fed=p.get("federation", "ITA")))
        info.append(
            _("Anno di nascita: {year}").format(year=p.get("birth_year") or _("N/D"))
        )
        info.append(
            _("Titolo FIDE: {title}").format(title=p.get("fide_title") or _("Nessuno"))
        )
        info.append(_("Punti correnti: {pts}").format(pts=p.get("points", 0.0)))

        status_str = (
            _("Ritirato dal torneo") if p.get("withdrawn") else _("Attivo nel torneo")
        )
        info.append(_("Stato: {status}").format(status=status_str))

        history = p.get("results_history", [])
        if history:
            info.append("\n" + _("Storico Turni e Risultati:"))
            for h in history:
                r_num = h.get("round")
                opp_id = h.get("opponent_id")
                res = h.get("result")
                color = h.get("color", "")

                color_str = (
                    _("Bianco")
                    if color == "white"
                    else _("Nero")
                    if color == "black"
                    else ""
                )

                opp_name = "BYE"
                if opp_id:
                    players_dict = self.current_tournament.get("players_dict", {})
                    opp_p = players_dict.get(opp_id)
                    if opp_p:
                        opp_name = f"{opp_p.get('last_name')} {opp_p.get('first_name')}"

                res_str = f"[{res}]" if res is not None else _("Non disputata")
                info.append(
                    _(
                        "  Turno {}: Colore: {color} vs {opponent} -> Risultato: {result}"
                    ).format(r_num, color=color_str, opponent=opp_name, result=res_str)
                )

        self.append_log("\n".join(info))

    def show_rounds_report_verbose(self):
        if not self.current_tournament:
            return
        t = self.current_tournament
        self.main_text.Clear()

        info = []
        info.append(_("REPORT TURNI DEL TORNEO"))

        rounds = t.get("rounds", [])
        if not rounds:
            info.append(_("Nessun turno disputato o generato."))
        else:
            for r in rounds:
                r_num = r.get("round")
                matches = r.get("matches", [])
                concluded = sum(1 for m in matches if m.get("result") is not None)
                info.append(
                    _("Turno {num}: {m_count} partite ({c_count} concluse)").format(
                        num=r_num, m_count=len(matches), c_count=concluded
                    )
                )

        self.append_log("\n".join(info))

    def show_single_round_report_verbose(self, round_num):
        if not self.current_tournament:
            return
        from reports import get_current_round_report_text

        self.main_text.Clear()
        text = get_current_round_report_text(self.current_tournament, round_num)
        self.append_log(text)

    def show_single_pgn_text(self, match):
        if not self.current_tournament or not match:
            return
        self.main_text.Clear()
        pgn_text = match.get("pgn", "")
        if pgn_text:
            self.append_log(pgn_text)
        else:
            self.append_log(_("Nessun PGN disponibile per questa partita."))

    def show_pgn_matches_list_verbose(self, round_num=None):
        if not self.current_tournament:
            return
        self.main_text.Clear()
        info = []
        if round_num is not None:
            info.append(_("RACCOLTA PARTITE PGN - TURNO {num}").format(num=round_num))
        else:
            info.append(_("RACCOLTA PARTITE PGN"))

        has_pgn = False
        for r in self.current_tournament.get("rounds", []):
            r_num = r.get("round")
            if round_num is not None and r_num != round_num:
                continue
            round_matches_sorted = sorted(
                r.get("matches", []), key=lambda x: x.get("id", 0)
            )
            match_id_to_board = {
                m.get("id"): idx for idx, m in enumerate(round_matches_sorted, 1)
            }

            for m in r.get("matches", []):
                if m.get("pgn"):
                    has_pgn = True
                    w_id = m.get("white_player_id")
                    b_id = m.get("black_player_id")
                    res = m.get("result")
                    players_dict = self.current_tournament.get("players_dict", {})
                    w_p = players_dict.get(w_id, {})
                    b_p = players_dict.get(b_id, {}) if b_id else None
                    w_name = f"{w_p.get('last_name', '')} {w_p.get('first_name', '')}".strip()
                    board_num = match_id_to_board.get(m.get("id"), 1)
                    if b_p:
                        b_name = f"{b_p.get('last_name', '')} {b_p.get('first_name', '')}".strip()
                        info.append(
                            _("  Turno {} Scacchiera {}: {} vs {} [{}]").format(
                                r_num, board_num, w_name, b_name, res
                            )
                        )
                    else:
                        info.append(
                            _("  Turno {} Scacchiera {}: {} - BYE [{}]").format(
                                r_num, board_num, w_name, res
                            )
                        )

        if not has_pgn:
            if round_num is not None:
                info.append(
                    _("Nessuna partita ha ancora un PGN inserito in questo turno.")
                )
            else:
                info.append(_("Nessuna partita ha ancora un PGN inserito."))

        self.append_log("\n".join(info))

    def get_board_num(self, match, round_num):
        if not self.current_tournament or not match:
            return 1
        rounds = self.current_tournament.get("rounds", [])
        r_data = next((r for r in rounds if r.get("round") == round_num), None)
        if not r_data:
            return 1
        round_matches = sorted(r_data.get("matches", []), key=lambda x: x.get("id", 0))
        for idx, m in enumerate(round_matches, 1):
            if m.get("id") == match.get("id"):
                return idx
        return 1

    def show_match_detail_verbose(self, m, round_num, board_num=None):
        if not m or not self.current_tournament:
            return
        if board_num is None:
            board_num = self.get_board_num(m, round_num)
        self.main_text.Clear()

        info = []
        info.append(_("DETTAGLIO PARTITA - TURNO {num}").format(num=round_num))
        info.append(_("Scacchiera Numero: {board}").format(board=board_num))

        players_dict = self.current_tournament.get("players_dict", {})
        w_id = m.get("white_player_id")
        b_id = m.get("black_player_id")
        res = m.get("result")

        w_p = players_dict.get(w_id, {})
        w_name = f"{w_p.get('last_name', '')} {w_p.get('first_name', '')}".strip()
        info.append(
            _("Bianco (White): {name} (Elo: {elo}, Naz: {fed})").format(
                name=w_name,
                elo=int(w_p.get("initial_elo", 1399)),
                fed=w_p.get("federation", "ITA"),
            )
        )

        if b_id:
            b_p = players_dict.get(b_id, {})
            b_name = f"{b_p.get('last_name', '')} {b_p.get('first_name', '')}".strip()
            info.append(
                _("Nero (Black): {name} (Elo: {elo}, Naz: {fed})").format(
                    name=b_name,
                    elo=int(b_p.get("initial_elo", 1399)),
                    fed=b_p.get("federation", "ITA"),
                )
            )
        else:
            info.append(_("Nero: BYE"))

        res_disp = res if res else _("Non ancora disputata")
        info.append(_("Risultato Registrato: {res}").format(res=res_disp))

        if m.get("is_scheduled") and m.get("schedule_info"):
            sched = m["schedule_info"]
            info.append(_("Pianificazione Partita:"))
            from utils import format_date_locale

            info.append(f"  {_('Data')}: {format_date_locale(sched.get('date'))}")
            info.append(f"  {_('Ora')}: {sched.get('time')}")
            info.append(f"  {_('Sala/URL')}: {sched.get('channel') or _('N/D')}")
            info.append(f"  {_('Arbitro')}: {sched.get('arbiter') or _('N/D')}")

        if m.get("pgn"):
            info.append("")
            info.append(_("Mosse della partita (PGN):"))
            info.append(m.get("pgn"))

        self.append_log("\n".join(info))

    def update_menu_states(self):
        """Abilita o disabilita le voci di menù del torneo in base allo stato corrente."""
        if not self.current_tournament:
            self.item_enroll.Enable(False)
            self.item_players.Enable(False)
            self.item_round.Enable(False)
            self.item_standings.Enable(False)
            self.item_rollback.Enable(False)
            self.item_finalize.Enable(False)
            self.item_export_ics.Enable(False)
            return

        self.item_players.Enable(True)
        self.item_standings.Enable(True)

        rounds = self.current_tournament.get("rounds", [])
        is_started = len(rounds) > 0

        is_concluded = (
            self.current_tournament.get("concluded", False)
            if self.current_tournament
            else False
        )

        # Gestione abilitazione esportazione ICS
        has_scheduled = False
        for r in rounds:
            for m in r.get("matches", []):
                if m.get("is_scheduled") and m.get("schedule_info"):
                    sched = m["schedule_info"]
                    if sched.get("date") and sched.get("time"):
                        has_scheduled = True
                        break
            if has_scheduled:
                break
        self.item_export_ics.Enable(has_scheduled)

        # Iscrizione abilitata solo se non iniziato e non concluso
        self.item_enroll.Enable(not is_started and not is_concluded)

        # Turno corrente abilitato solo se iniziato
        self.item_round.Enable(is_started)

        # Rollback abilitato solo se iniziato e non concluso
        self.item_rollback.Enable(is_started and not is_concluded)

        # Finalizzazione abilitata solo se:
        # non è concluso, siamo all'ultimo turno, e tutte le partite dell'ultimo turno hanno un risultato.
        can_finalize = False
        if is_started and not is_concluded:
            curr_round = self.current_tournament.get("current_round", 1)
            tot_rounds = self.current_tournament.get("total_rounds", 5)
            if curr_round == tot_rounds:
                r_data = next((r for r in rounds if r.get("round") == curr_round), None)
                if r_data:
                    all_done = True
                    for m in r_data.get("matches", []):
                        if (
                            m.get("result") is None
                            and m.get("black_player_id") is not None
                        ):
                            all_done = False
                            break
                    if all_done:
                        can_finalize = True

        self.item_finalize.Enable(can_finalize)

    def show_standings_verbose(self):
        if not self.current_tournament:
            return
        from reports import get_standings_text

        self.main_text.Clear()

        is_concluded = (
            self.current_tournament.get("concluded", False)
            if self.current_tournament
            else False
        )

        text = get_standings_text(self.current_tournament, final=is_concluded)
        self.append_log(text)

    def on_tree_item_activated(self, event):
        item = event.GetItem()
        data = self.tree_ctrl.GetItemData(item)
        if not data:
            return

        field = data.get("field")
        if field:
            self.on_wizard_field_activated(item, field)
            return

        field_active = data.get("field_active")
        if field_active:
            self.on_active_field_activated(item, field_active)
            return

        action = data.get("action")
        filepath = data.get("filepath")

        if filepath and not self._e_il_torneo_aperto(filepath):
            self.load_tournament(filepath, rebuild_tree=False)
            # Se il torneo della voce non si e' aperto, per esempio perche'
            # il suo file non c'e' piu', l'azione non parte: fino alla
            # 10.13.9 Avvio torneo proseguiva dopo il messaggio d'errore,
            # senza un torneo da avviare.
            if not self._e_il_torneo_aperto(filepath):
                return

        if action == "add_player_action":
            self.on_enroll_players(None)
        elif action == "start_tournament_matchmaking_action":
            self.start_tournament_matchmaking()
        elif action == "generate_next_round_action":
            self.generate_next_round()
        elif action == "finalize_tournament_action":
            self.on_finalize_tournament(None)
        elif action == "activate_match":
            self.on_activate_match(data.get("match"))
        elif action == "show_tiebreaks":
            self.on_configure_tiebreaks()
        elif action == "start_new_tournament":
            self.start_new_tournament_wizard()
        elif action == "wizard_next":
            self.on_wizard_next()
        elif action == "wizard_back":
            self.on_wizard_back()

    def on_wizard_field_activated(self, item, field):
        from utils import format_date_locale, play_sound

        play_sound("apertura")

        if field == "name":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci il nome del torneo:"),
                _("Nome Torneo"),
                self.creation_data["name"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                play_sound("conferma")
                self.creation_data["name"] = dlg.GetValue().strip()
                self.tree_ctrl.SetItemText(
                    item,
                    _("Nome torneo *: {}").format(
                        self.creation_data["name"] or _("Non impostato")
                    ),
                )
            dlg.Destroy()
        elif field == "site":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci il luogo (Site):"),
                _("Luogo Torneo"),
                self.creation_data["site"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                play_sound("conferma")
                self.creation_data["site"] = dlg.GetValue().strip()
                self.tree_ctrl.SetItemText(
                    item,
                    _("Luogo (Site): {}").format(
                        self.creation_data["site"] or _("Non impostato")
                    ),
                )
            dlg.Destroy()
        elif field == "rounds":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci il numero di turni:"),
                _("Numero Turni"),
                str(self.creation_data["rounds"]),
            )
            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                if val.isdigit():
                    play_sound("conferma")
                    self.creation_data["rounds"] = int(val)
                    self.tree_ctrl.SetItemText(
                        item, _("Numero turni: {}").format(self.creation_data["rounds"])
                    )
                else:
                    wx.MessageBox(
                        _("Inserisci un numero intero valido."),
                        _("Errore"),
                        wx.ICON_ERROR,
                    )
            dlg.Destroy()
        elif field == "time_control":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci il tempo di riflessione (es. 15+10 o 90+30 o 60+0):"),
                _("Tempo di riflessione"),
                self.creation_data["time_control"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                play_sound("conferma")
                self.creation_data["time_control"] = dlg.GetValue().strip()
                self.tree_ctrl.SetItemText(
                    item,
                    _("Tempo riflessione: {}").format(
                        self.creation_data["time_control"] or _("Non impostato")
                    ),
                )
            dlg.Destroy()
        elif field == "save_path":
            dlg = wx.DirDialog(
                self,
                _("Seleziona la cartella di salvataggio per i report:"),
                self.creation_data["save_path"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                play_sound("conferma")
                self.creation_data["save_path"] = dlg.GetPath()
                self.tree_ctrl.SetItemText(
                    item,
                    _("Cartella di salvataggio: {}").format(
                        self.creation_data["save_path"]
                    ),
                )
            dlg.Destroy()
        elif field == "start_date":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci la data di inizio (AAAA-MM-GG):"),
                _("Data Inizio"),
                self.creation_data["start_date"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                try:
                    from datetime import datetime

                    datetime.strptime(val, "%Y-%m-%d")
                    play_sound("conferma")
                    self.creation_data["start_date"] = val
                    self.tree_ctrl.SetItemText(
                        item, _("Data inizio: {}").format(format_date_locale(val))
                    )
                except ValueError:
                    wx.MessageBox(
                        _("Formato data non valido. Usa AAAA-MM-GG."),
                        _("Errore"),
                        wx.ICON_ERROR,
                    )
            dlg.Destroy()
        elif field == "end_date":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci la data di fine (AAAA-MM-GG):"),
                _("Data Fine"),
                self.creation_data["end_date"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                try:
                    from datetime import datetime

                    datetime.strptime(val, "%Y-%m-%d")
                    play_sound("conferma")
                    self.creation_data["end_date"] = val
                    self.tree_ctrl.SetItemText(
                        item, _("Data fine: {}").format(format_date_locale(val))
                    )
                except ValueError:
                    wx.MessageBox(
                        _("Formato data non valido. Usa AAAA-MM-GG."),
                        _("Errore"),
                        wx.ICON_ERROR,
                    )
            dlg.Destroy()
        elif field == "chief_arbiter":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci il nome dell'Arbitro Capo:"),
                _("Arbitro Capo"),
                self.creation_data["chief_arbiter"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                play_sound("conferma")
                self.creation_data["chief_arbiter"] = dlg.GetValue().strip()
                self.tree_ctrl.SetItemText(
                    item,
                    _("Arbitro Capo: {}").format(
                        self.creation_data["chief_arbiter"] or _("Non impostato")
                    ),
                )
            dlg.Destroy()
        elif field == "deputy_chief_arbiters":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci i collaboratori / vice arbitri (separati da virgola):"),
                _("Collaboratori / Vice Arbitri"),
                self.creation_data["deputy_chief_arbiters"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                play_sound("conferma")
                self.creation_data["deputy_chief_arbiters"] = dlg.GetValue().strip()
                self.tree_ctrl.SetItemText(
                    item,
                    _("Collaboratori / Vice Arbitri: {}").format(
                        self.creation_data["deputy_chief_arbiters"]
                        or _("Non impostate")
                    ),
                )
            dlg.Destroy()
        elif field == "federation_code":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci il codice della federazione ospitante (es. ITA, FRA):"),
                _("Codice Federazione"),
                self.creation_data["federation_code"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                play_sound("conferma")
                self.creation_data["federation_code"] = dlg.GetValue().strip().upper()
                self.tree_ctrl.SetItemText(
                    item,
                    _("Codice Federazione: {}").format(
                        self.creation_data["federation_code"]
                    ),
                )
            dlg.Destroy()
        elif field == "color_board1":
            choices = [
                _("Bianco (scelto dall'arbitro)"),
                _("Nero (scelto dall'arbitro)"),
                _("Casuale (scelto da {app})").format(app="Tornello"),
            ]
            dlg = wx.SingleChoiceDialog(
                self,
                _(
                    "Seleziona il colore per il giocatore più forte (scacchiera 1, turno 1):"
                ),
                _("Colore al giocatore più forte"),
                choices,
            )
            curr_raw = self.creation_data["color_board1"]
            curr_idx = 0
            if curr_raw == "black1":
                curr_idx = 1
            elif curr_raw == "random":
                curr_idx = 2
            dlg.SetSelection(curr_idx)
            if dlg.ShowModal() == wx.ID_OK:
                play_sound("conferma")
                sel = dlg.GetSelection()
                val_raw = "white1"
                if sel == 1:
                    val_raw = "black1"
                elif sel == 2:
                    val_raw = "random"
                self.creation_data["color_board1"] = val_raw
                col_disp = choices[sel]
                self.tree_ctrl.SetItemText(
                    item, _("Colore al giocatore più forte: {}").format(col_disp)
                )
            dlg.Destroy()
        elif field == "bye_value":
            choices = ["0.0", "0.5", "1.0"]
            dlg = wx.SingleChoiceDialog(
                self,
                _("Seleziona il valore del BYE secondo la regola FIDE:"),
                _("Valore del BYE"),
                choices,
            )
            curr_str = str(self.creation_data["bye_value"])
            if curr_str in choices:
                dlg.SetSelection(choices.index(curr_str))
            if dlg.ShowModal() == wx.ID_OK:
                play_sound("conferma")
                self.creation_data["bye_value"] = float(dlg.GetStringSelection())
                self.tree_ctrl.SetItemText(
                    item,
                    _("Valore del BYE: {}").format(self.creation_data["bye_value"]),
                )
            dlg.Destroy()

        # Controlla se dobbiamo aggiungere il bottone "Avanti"
        if self.creation_data["name"] and self.creation_data["time_control"]:
            has_next = False
            child, cookie = self.tree_ctrl.GetFirstChild(self.tree_root)
            while child.IsOk():
                if self.tree_ctrl.GetItemData(child).get("action") == "wizard_next":
                    has_next = True
                    break
                child, cookie = self.tree_ctrl.GetNextChild(self.tree_root, cookie)

            if not has_next:
                next_item = self.tree_ctrl.AppendItem(
                    self.tree_root, _("Iscrizione Giocatori")
                )
                self.tree_ctrl.SetItemData(next_item, {"action": "wizard_next"})
                if not (self.tree_ctrl.GetWindowStyleFlag() & wx.TR_HIDE_ROOT):
                    self.tree_ctrl.Expand(self.tree_root)

    def on_wizard_next(self):
        from utils import play_sound

        # Un database che non si legge non apre la finestra di iscrizione:
        # un giocatore aggiunto dalla ricerca FIDE o da zero non si potrebbe
        # salvare (10.13.15).
        players_db = self._database_dei_giocatori()
        if players_db is None:
            return

        play_sound("conferma")

        # Calcola la categoria del torneo in base al tempo di riflessione inserito
        from gui.dialogs import PlayerEnrollmentDialog
        from stats import classify_tournament_category, parse_time_control

        tc_parsed = parse_time_control(
            self.creation_data.get("time_control", "60+0")
        ) or {
            "minutes": 60,
            "increment": 0,
        }
        category = classify_tournament_category(
            tc_parsed.get("minutes", 60), tc_parsed.get("increment", 0)
        )
        self.creation_data["tournament_category"] = category

        dlg = PlayerEnrollmentDialog(
            self, players_db, [], self.settings, category=category
        )
        if dlg.ShowModal() == wx.ID_OK:
            enrolled = dlg.get_enrolled_players()
            if len(enrolled) < 2:
                wx.MessageBox(
                    _("Sono necessari almeno 2 giocatori per avviare un torneo."),
                    _("Errore"),
                    wx.ICON_ERROR,
                )
                dlg.Destroy()
                return

            self.create_tournament_from_wizard(enrolled)
        dlg.Destroy()

    def on_wizard_back(self):
        self.creation_mode = False
        self.creation_data = {}
        self.populate_tree()
        self.show_intro_message()

    def create_tournament_from_wizard(self, enrolled):
        from models import Player, RoundDate, Tournament
        from stats import get_initial_elo_for_tournament
        from utils import sanitize_filename

        category = self.creation_data.get("tournament_category", "standard")
        for p in enrolled:
            p["initial_elo"] = get_initial_elo_for_tournament(p, category)

        players = []
        for p in enrolled:
            players.append(Player.from_dict(p))

        save_dir = self.creation_data["save_path"]
        from utils import resolve_and_verify_save_path

        resolved_save_dir, warning = resolve_and_verify_save_path(save_dir)
        if warning:
            wx.MessageBox(warning, _("Avviso Percorso"), wx.OK | wx.ICON_WARNING)
        save_dir = resolved_save_dir

        sanitized = sanitize_filename(self.creation_data["name"])
        self.active_filename = user_data_path(f"Tornello - {sanitized}.json")

        from tournament import calculate_dates

        round_dates_raw = (
            calculate_dates(
                self.creation_data["start_date"],
                self.creation_data["end_date"],
                self.creation_data["rounds"],
            )
            or []
        )

        # Classificazione categoria Elo
        from stats import classify_tournament_category, parse_time_control

        tc_parsed = parse_time_control(self.creation_data["time_control"]) or {
            "minutes": 60,
            "increment": 0,
        }
        tournament_category = classify_tournament_category(
            tc_parsed.get("minutes", 60), tc_parsed.get("increment", 0)
        )

        color_setting = self.creation_data["color_board1"]
        if color_setting == "random":
            import random

            color_setting = random.choice(["white1", "black1"])

        t_dict = {
            "name": self.creation_data["name"],
            "tournament_id": sanitized.upper(),
            "site": self.creation_data["site"] or "N/D",
            "start_date": self.creation_data["start_date"],
            "end_date": self.creation_data["end_date"],
            "total_rounds": self.creation_data["rounds"],
            "current_round": 1,
            "time_control": tc_parsed,
            "chief_arbiter": self.creation_data["chief_arbiter"] or "N/D",
            "deputy_chief_arbiters": self.creation_data["deputy_chief_arbiters"] or "",
            "federation_code": self.creation_data["federation_code"] or "ITA",
            "initial_board1_color_setting": color_setting,
            "round_dates": [
                rd.to_dict() for rd in [RoundDate.from_dict(x) for x in round_dates_raw]
            ],
            "players": [p.to_dict() for p in players],
            "rounds": [],
            "custom_save_path": save_dir,
            "save_path": save_dir,
            "bye_value": self.creation_data["bye_value"],
            "tournament_category": tournament_category,
        }

        tournament = Tournament.from_dict(t_dict)
        tournament.update_players_dict()

        # Il torneo nasce sempre in preparazione. L'avvio e' una voce
        # dell'albero, "calcola il turno 1" sotto i turni oppure la voce in
        # fondo al centro comandi: piu' chiaro di una domanda che compariva una
        # volta sola e che, se rispondevi di no, spariva.
        self.current_tournament = tournament.to_dict()
        self.current_tournament["players_dict"] = {
            p["id"]: p for p in self.current_tournament.get("players", [])
        }
        self._save_state()
        self.creation_mode = False
        self._tree_restore_target = {
            "action": "start_tournament_matchmaking_action",
            "filepath": self.active_filename,
        }
        self.load_tournament(self.active_filename)
        self.set_status(
            _(
                "Torneo creato. Quando gli iscritti sono al completo, avvialo con la voce calcola il turno 1."
            )
        )

    def _save_state(self):
        if self.current_tournament:
            from reports import save_current_tournament_round_file, save_standings_text
            from tournament import save_tournament

            save_tournament(self.current_tournament, filepath=self.active_filename)
            save_current_tournament_round_file(self.current_tournament)
            save_standings_text(self.current_tournament, final=False)

            # Accumula ed esporta il file PGN del torneo
            if self.active_filename:
                import os

                from utils import resolve_and_verify_save_path, sanitize_filename

                t_name = self.current_tournament.get("name", "Torneo_Senza_Nome")
                sanitized_name = sanitize_filename(t_name)
                # La raccolta partite e' un file che appartiene al torneo, non
                # al programma: va nella cartella di lavoro scelta dall'arbitro,
                # come i report di testo.
                cartella_pgn = self.current_tournament.get("custom_save_path")
                if cartella_pgn:
                    cartella_pgn, _avviso = resolve_and_verify_save_path(cartella_pgn)
                else:
                    cartella_pgn = os.path.dirname(self.active_filename)
                pgn_filename = os.path.join(
                    cartella_pgn,
                    _("{name} - raccolta partite.pgn").format(name=sanitized_name),
                )
                all_pgns = []
                for r in self.current_tournament.get("rounds", []):
                    for m in r.get("matches", []):
                        if m.get("pgn"):
                            all_pgns.append(m["pgn"].strip())
                if all_pgns:
                    try:
                        with open(pgn_filename, "w", encoding="utf-8") as f:
                            f.write("\n\n".join(all_pgns) + "\n")
                    except Exception as e:
                        print(f"Errore durante il salvataggio della raccolta PGN: {e}")
                else:
                    if os.path.exists(pgn_filename):
                        try:
                            os.remove(pgn_filename)
                        except Exception:
                            pass

    def on_tree_key_down(self, event):
        if not self or not getattr(self, "tree_ctrl", None) or not self.tree_ctrl:
            return
        try:
            key_code = event.GetKeyCode()
            item = self.tree_ctrl.GetSelection()
            if not item or not item.IsOk():
                event.Skip()
                return
            data = self.tree_ctrl.GetItemData(item)
        except Exception:
            event.Skip()
            return

        if key_code == wx.WXK_DELETE and item and data:
            action = data.get("action")
            filepath = data.get("filepath")
            if action == "show_player_detail":
                player_data = data.get("player")
                self.delete_player_from_tournament(item, player_data)
                return
            if action in ["select_tournament", "load_concluded"] and filepath:
                self.delete_tournament_completely(item, filepath)
                return

        event.Skip()

    def delete_player_from_tournament(self, item, player_data):
        node_data = self.tree_ctrl.GetItemData(item)
        if not node_data:
            return
        filepath = node_data.get("filepath")
        if not filepath:
            return

        import json

        from utils import play_sound

        try:
            with open(filepath, encoding="utf-8") as f_in:
                t_data = json.load(f_in)
        except Exception as e:
            wx.MessageBox(
                _("Impossibile leggere il file del torneo: {}").format(e),
                _("Errore"),
                wx.ICON_ERROR,
            )
            return

        if len(t_data.get("rounds", [])) > 0:
            self._proponi_ritiro_dal_torneo(item, player_data, filepath)
            return

        p_name = f"{player_data.get('last_name', '')} {player_data.get('first_name', '')}".strip()
        msg = _("Sei sicuro di voler rimuovere il giocatore {name} dal torneo?").format(
            name=p_name
        )
        dlg = AccessibleMsgDialog(
            self, _("Conferma Rimozione Giocatore"), msg, style=wx.YES_NO
        )
        if dlg.ShowModal() == wx.ID_YES:
            try:
                players = t_data.get("players", [])
                to_remove = next(
                    (p for p in players if p.get("id") == player_data.get("id")), None
                )
                if to_remove:
                    players.remove(to_remove)
                    t_data["players_dict"] = {p["id"]: p for p in players}

                    with open(filepath, "w", encoding="utf-8") as f_out:
                        json.dump(t_data, f_out, indent=4)

                    if self._e_il_torneo_aperto(filepath):
                        self.current_tournament = t_data

                    self._tree_restore_target = {
                        "action": "show_players",
                        "filepath": filepath,
                    }
                    self.populate_tree()
                    play_sound("rimozione_giocatore")

                    if self._e_il_torneo_aperto(filepath):
                        self.show_players_list_verbose()

                    self.set_status(
                        _("Giocatore '{name}' rimosso con successo.").format(
                            name=p_name
                        )
                    )
            except Exception as e:
                wx.MessageBox(
                    _("Impossibile rimuovere il giocatore: {}").format(e),
                    _("Errore"),
                    wx.ICON_ERROR,
                )
        else:
            parent_item = self.tree_ctrl.GetItemParent(item)
            if parent_item and parent_item.IsOk():
                self.tree_ctrl.SelectItem(parent_item)
                self.tree_ctrl.SetFocus()
        dlg.Destroy()

    def _partita_del_turno_corrente(self, player_id):
        """Dice cosa fa il giocatore nel turno in corso: 'assente' se non ha
        partita, 'giocata' se il risultato c'e' gia', 'da_giocare' altrimenti."""
        rounds = self.current_tournament.get("rounds", [])
        if not rounds:
            return "assente"
        ultimo = rounds[-1]
        for partita in ultimo.get("matches", []):
            if player_id in (
                partita.get("white_player_id"),
                partita.get("black_player_id"),
            ):
                return "giocata" if partita.get("result") else "da_giocare"
        return "assente"

    def _proponi_ritiro_dal_torneo(self, item, player_data, filepath):
        """A torneo iniziato l'iscrizione non si puo' piu' togliere, perche'
        lascerebbe abbinamenti e risultati riferiti a un giocatore che non
        esiste piu'. Al suo posto si offre il ritiro, che e' l'operazione che
        l'arbitro sta cercando davvero."""
        from utils import play_sound

        p_name = f"{player_data.get('last_name', '')} {player_data.get('first_name', '')}".strip()
        if not self._e_il_torneo_aperto(filepath):
            play_sound("errore")
            self._dialogo_informativo(
                _("Torneo non aperto"),
                _(
                    "Il torneo e' gia' iniziato, quindi l'iscrizione di {name} non si puo' piu' togliere: al suo posto si puo' ritirare il giocatore. Apri prima il torneo, poi ripeti l'operazione."
                ).format(name=p_name),
            )
            return

        giocatore = self.current_tournament.get("players_dict", {}).get(
            player_data.get("id")
        )
        if not giocatore:
            return

        if giocatore.get("withdrawn"):
            self._dialogo_informativo(
                _("Giocatore gia' ritirato"),
                _("{name} risulta gia' ritirato dal torneo.").format(name=p_name),
            )
            return

        turno_corrente = self.current_tournament.get("current_round", 1)
        stato = self._partita_del_turno_corrente(giocatore.get("id"))
        if stato == "da_giocare":
            play_sound("errore")
            self._dialogo_informativo(
                _("Partita ancora aperta"),
                _(
                    "{name} ha una partita senza risultato nel turno {round}. Registra prima quel risultato, indicando il forfait se non si e' presentato: subito dopo il programma ti proporra' il ritiro."
                ).format(name=p_name, round=turno_corrente),
            )
            return

        if stato == "giocata":
            messaggio = _(
                "Il torneo e' iniziato, quindi l'iscrizione di {name} non si puo' piu' togliere: i risultati gia' registrati resterebbero senza giocatore.\n\nVuoi ritirarlo dal torneo? La partita che ha gia' giocato nel turno {round} resta valida e il ritiro vale dal turno successivo."
            ).format(name=p_name, round=turno_corrente)
        else:
            messaggio = _(
                "Il torneo e' iniziato, quindi l'iscrizione di {name} non si puo' piu' togliere: i risultati gia' registrati resterebbero senza giocatore.\n\nVuoi ritirarlo dal torneo? Non verra' piu' abbinato nei turni successivi."
            ).format(name=p_name)

        if not self._conferma_ritiro(giocatore.get("id"), filepath, domanda=messaggio):
            return

        self.withdraw_player(giocatore.get("id"))
        self._tree_restore_target = {"action": "show_players", "filepath": filepath}
        self.populate_tree()
        self.show_players_list_verbose()

    def _conferma_ritiro(self, player_id, filepath, domanda=None):
        """Il controllo sul ritiro, uguale nelle tre strade da cui si ritira un
        giocatore: il tasto CANC nell'albero, il pulsante Ritira Giocatore
        della finestra del risultato e la domanda dopo un forfait. Fino alla
        10.13.0 lo facevano solo il tasto CANC, e le altre due lo saltavano.
        Risponde vero se il ritiro va registrato.
        Quando i giocatori attivi non bastano per i turni che restano, dalla
        10.13.1 il ritiro non e' piu' impedito: un avviso, con No come
        pulsante predefinito, dice che il motore potrebbe non riuscire ad
        abbinare un turno, e che in quel caso il turno si compone a mano
        (issue 38). Il bivio fra ritorno all'iscrizione ed eliminazione resta
        solo quando i giocatori attivi scenderebbero sotto due, e risponde
        falso: la finestra del risultato controlla poi con
        _bivio_ha_cambiato_il_torneo se il torneo e' cambiato sotto di lei.
        domanda e' la domanda di conferma della strada, se ne ha una: senza
        avviso si pone da sola, con l'avviso ne diventa l'inizio."""
        from tournament import valuta_ritiro

        giocatore = self.current_tournament.get("players_dict", {}).get(player_id, {})
        nome = f"{giocatore.get('last_name', '')} {giocatore.get('first_name', '')}".strip()
        esito, resterebbero, necessari, turni_rimanenti = valuta_ritiro(
            self.current_tournament, player_id
        )
        if esito == "bivio":
            self._bivio_torneo_non_proseguibile(
                filepath, nome, resterebbero, necessari, turni_rimanenti
            )
            return False
        if esito == "avviso":
            from utils import play_sound

            play_sound("errore")
            # Con l'avviso restano almeno due giocatori e due turni: fra due
            # giocatori l'avversario possibile e' uno solo, e la frase va al
            # singolare. Il numero che servirebbe e' di giocatori, non di
            # avversari, e la frase lo dice.
            if resterebbero - 1 == 1:
                avviso = _(
                    "Ritirando {name} resterebbero {resterebbero} giocatori attivi per i {turni} turni che mancano. Fra {resterebbero} giocatori c'e' un solo avversario possibile a testa, e per giocare tutti i turni che mancano senza incontri ripetuti servirebbero almeno {necessari} giocatori attivi: il motore di abbinamento potrebbe non riuscire ad abbinare uno dei prossimi turni. In quel caso Tornello ti proporra' di comporre il turno a mano."
                )
            else:
                avviso = _(
                    "Ritirando {name} resterebbero {resterebbero} giocatori attivi per i {turni} turni che mancano. Fra {resterebbero} giocatori ci sono solo {avversari} avversari possibili a testa, e per giocare tutti i turni che mancano senza incontri ripetuti servirebbero almeno {necessari} giocatori attivi: il motore di abbinamento potrebbe non riuscire ad abbinare uno dei prossimi turni. In quel caso Tornello ti proporra' di comporre il turno a mano."
                )
            avviso = avviso.format(
                name=nome,
                resterebbero=resterebbero,
                avversari=max(resterebbero - 1, 0),
                turni=turni_rimanenti,
                necessari=necessari,
            )
            testo = "\n\n".join(
                [
                    *([domanda] if domanda else []),
                    avviso,
                    _("Vuoi ritirarlo comunque? Il pulsante predefinito e' No."),
                ]
            )
            dlg = AccessibleMsgDialog(
                self,
                _("Ritiro con pochi giocatori"),
                testo,
                style=wx.YES_NO,
                settings=self.settings,
                no_predefinito=True,
            )
            conferma = dlg.ShowModal()
            dlg.Destroy()
            return conferma == wx.ID_YES
        if domanda:
            dlg = AccessibleMsgDialog(
                self,
                _("Ritiro dal torneo"),
                domanda,
                style=wx.YES_NO,
                settings=self.settings,
            )
            conferma = dlg.ShowModal()
            dlg.Destroy()
            return conferma == wx.ID_YES
        return True

    def _bivio_torneo_non_proseguibile(
        self, filepath, nome_giocatore, resterebbero, necessari, turni_rimanenti
    ):
        """Il ritiro lascerebbe il torneo con meno di due giocatori attivi, e
        nessun turno si potrebbe piu' abbinare, nemmeno a mano. Il ritiro non
        viene registrato e restano due strade: riportare il torneo alla fase di
        iscrizione, che conserva tutto e permette di rifarlo, oppure eliminarlo.
        Fino alla 10.13.0 il bivio arrivava gia' quando i giocatori non
        bastavano per i turni rimanenti: dalla 10.13.1 quello e' un avviso di
        _conferma_ritiro."""
        from tournament import riporta_torneo_alla_preparazione
        from utils import create_backup, play_sound

        play_sound("errore")
        # Con un giocatore solo che resterebbe, la prima frase va al
        # singolare: fino alla 10.13.5 diceva resterebbero 1 giocatori.
        if resterebbero == 1:
            premessa = _(
                "Ritirando {name} resterebbe un solo giocatore attivo: con meno di due giocatori non si abbina piu' nessun turno, nemmeno a mano."
            ).format(name=nome_giocatore)
        else:
            premessa = _(
                "Ritirando {name} resterebbero {resterebbero} giocatori attivi: con meno di due giocatori non si abbina piu' nessun turno, nemmeno a mano."
            ).format(name=nome_giocatore, resterebbero=resterebbero)
        messaggio = premessa + "\n\n" + _(
            "Il ritiro non viene registrato, perche' il torneo si fermerebbe a meta' senza possibilita' di rimediare. Restano due strade: riportare il torneo alla fase di iscrizione, dove i turni giocati vengono cancellati, i giocatori gia' ritirati tolti dall'elenco e tutto torna modificabile, oppure eliminare il torneo.\n\n"
            "Vuoi riportare il torneo alla fase di iscrizione? Prima dell'operazione viene creata una copia di sicurezza."
        )
        dlg = AccessibleMsgDialog(
            self,
            _("Il torneo non potrebbe proseguire"),
            messaggio,
            style=wx.YES_NO,
            settings=self.settings,
        )
        conferma = dlg.ShowModal()
        dlg.Destroy()

        if conferma != wx.ID_YES:
            self._proponi_eliminazione_torneo(filepath)
            return

        create_backup(filepath, "pre_ritorno_preparazione")
        if not riporta_torneo_alla_preparazione(self.current_tournament):
            play_sound("errore")
            self._dialogo_informativo(
                _("Operazione non riuscita"),
                _(
                    "Non e' stato possibile riportare il torneo alla fase di iscrizione."
                ),
            )
            return

        self._save_state()
        self._tree_restore_target = {"action": "show_players", "filepath": filepath}
        self.populate_tree()
        self.show_players_list_verbose()
        self.set_status(
            _(
                "Torneo riportato alla fase di iscrizione. I turni sono stati cancellati."
            )
        )

    def _bivio_ha_cambiato_il_torneo(self, torneo, turno):
        """Vero se il bivio di _conferma_ritiro, raggiunto dalla finestra del
        risultato, ha riportato il torneo alla fase di iscrizione, e il turno
        della partita non c'e' piu', oppure lo ha eliminato, e il torneo
        aperto non e' piu' quello. Dalla 10.13.1 il bivio si raggiunge anche
        dal pulsante Ritira Giocatore e dalla domanda dopo un forfait: in quel
        caso on_activate_match esce subito, e barra di stato, albero e area
        centrale restano come li ha lasciati il bivio. Se l'arbitro ha
        rifiutato entrambe le strade il torneo e' quello di prima, e la
        finestra del risultato prosegue come sempre."""
        if self.current_tournament is not torneo:
            return True
        return turno is not None and not any(r is turno for r in torneo.get("rounds", []))

    def _proponi_eliminazione_torneo(self, filepath):
        """Seconda strada del bivio: eliminare il torneo. Si riusa la stessa
        funzione dell'albero, che chiede conferma elencando i file e li manda
        nel cestino."""
        dlg = AccessibleMsgDialog(
            self,
            _("Eliminare il torneo"),
            _(
                "Vuoi allora mandare nel cestino di Windows il torneo e tutti i suoi file? Se rispondi di no non viene fatto nulla, e il torneo resta come si trova ora."
            ),
            style=wx.YES_NO,
            settings=self.settings,
        )
        conferma = dlg.ShowModal()
        dlg.Destroy()
        if conferma != wx.ID_YES:
            return

        nodo = self._find_matching_item(
            self.tree_root, {"action": "select_tournament", "filepath": filepath}
        )
        if nodo and nodo.IsOk():
            self.delete_tournament_completely(nodo, filepath)
            return

        self._dialogo_informativo(
            _("Eliminazione dall'albero"),
            _(
                "Per eliminare il torneo posizionati sul suo nome nell'albero e premi il tasto Canc."
            ),
        )

    def _torneo_puo_partire(self, torneo):
        """Controlla il rapporto fra iscritti e turni prima di generare il
        primo turno. Il divieto ferma l'avvio, l'avvertimento chiede solo
        conferma. Serve a non far partire tornei che l'abbinatore non potrebbe
        portare a termine: era il caso dei cinque giocatori su cinque turni."""
        from tournament import controlla_iscritti_e_turni
        from utils import play_sound

        si_puo, motivo, avvertimento = controlla_iscritti_e_turni(torneo)
        if not si_puo:
            play_sound("errore")
            self._dialogo_informativo(_("Torneo non avviabile"), motivo)
            return False
        if avvertimento:
            dlg = AccessibleMsgDialog(
                self,
                _("Turni consigliati"),
                avvertimento + _("\n\nVuoi avviare comunque il torneo?"),
                style=wx.YES_NO,
                settings=self.settings,
            )
            conferma = dlg.ShowModal()
            dlg.Destroy()
            if conferma != wx.ID_YES:
                return False
        return True

    def _dialogo_informativo(self, titolo, messaggio):
        dlg = AccessibleMsgDialog(self, titolo, messaggio, settings=self.settings)
        dlg.ShowModal()
        dlg.Destroy()

    def load_concluded_tournament_report(self, filepath):
        """Visualizza i report e la classifica di un torneo concluso nell'area centrale."""
        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
            t_name = data.get("name", _("Torneo Concluso"))

            self.main_text.Clear()
            report = _("Torneo Concluso: {}\n").format(t_name)
            report += _("Data Inizio: {start} | Fine: {end}\n").format(
                start=data.get("start_date", _("N/D")),
                end=data.get("end_date", _("N/D")),
            )

            # Aggiungi classifica finale se presente nel json
            report += _("Classifica Finale:\n")
            players = data.get("players", [])
            players_sorted = sorted(
                players, key=lambda p: p.get("points", 0.0), reverse=True
            )
            for idx, p in enumerate(players_sorted):
                p_name = f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
                report += _(" {rank:>2}. {name:<30} Punti: {pts:.1f}\n").format(
                    rank=idx + 1, name=p_name, pts=p.get("points", 0.0)
                )

            self.append_log(report)
            self.set_status(
                _("Visualizzazione report torneo concluso '{name}'.").format(
                    name=t_name
                )
            )
        except Exception as e:
            wx.MessageBox(
                _("Impossibile leggere il report: {}").format(e),
                _("Errore"),
                wx.ICON_ERROR,
            )

    def _nel_cestino(self, percorso):
        """Il cestino di Windows, con la finestra principale come proprietaria
        della domanda che Windows fa prima di cancellare per sempre un file
        che il cestino non puo' prendere, come nella finestra Copie di
        sicurezza: cosi' la domanda prende il fuoco, invece di restare
        nascosta. Su un disco senza cestino il file resta dov'e', e la
        risposta e' falso."""
        from utils import delete_file_to_trash

        return delete_file_to_trash(percorso, finestra=self.GetHandle())

    def _file_correlati_del_torneo(self, filepath, data, t_name):
        """I file che vanno nel cestino insieme al file del torneo, e le
        cartelle che non si sono potute leggere: li elenca la conferma, e li
        manda nel cestino delete_tournament_completely.
        Sono i file che portano il nome intero del torneo, riconosciuti con
        file_del_torneo come dalla 10.3.4, nella cartella del file del torneo
        e nella sua cartella di salvataggio. Dalla 10.13.8 un json ci va solo
        se e' la copia dello stesso torneo nell'altra cartella, cioe' quella
        del torneo concluso nella cartella di lavoro esterna: stesso nome di
        file, stesso nome del torneo e stessa edizione. Ogni altro json e' un
        altro torneo, o un file del programma: l'edizione in corso accanto a
        quella conclusa, la copia che Esplora risorse chiama "- Copia", il
        torneo vero accanto a un file aperto con un altro nome, il database
        dei giocatori e le impostazioni per un torneo di nome Players db o
        Settings. Fino alla 10.13.7 sparivano insieme al torneo.
        La cartella di salvataggio si prende com'e', senza
        resolve_and_verify_save_path, che la crea se manca e ripiega sulla
        cartella del programma se manca la sua unita'. Per un torneo in
        archivio conta solo se e' una cartella esterna, come per la
        finalizzazione: altrimenti i suoi report sono gia' in archivio, e
        quelli con lo stesso nome accanto al programma sono di un'altra
        edizione. Una cartella scritta con maiuscole diverse si legge una
        volta sola."""
        from copie_di_sicurezza import stessa_edizione
        from tournament import sanitize_filename
        from ui import cartella_di_lavoro_esterna
        from utils import file_del_torneo

        def chiave(percorso):
            return os.path.normcase(os.path.abspath(percorso))

        cartella_del_file = os.path.dirname(os.path.abspath(filepath))
        cartelle = [cartella_del_file]
        custom_path = data.get("custom_save_path") or data.get("save_path")
        in_archivio = chiave(filepath).startswith(
            chiave(ARCHIVED_TOURNAMENTS_DIR) + os.sep
        )
        if (
            custom_path
            and os.path.isdir(custom_path)
            and (not in_archivio or cartella_di_lavoro_esterna(custom_path))
        ):
            cartelle.append(os.path.abspath(custom_path))

        sanitized_name = sanitize_filename(t_name)
        nome_del_json = f"Tornello - {sanitized_name}.json"
        correlati, illeggibili, lette = [], [], set()
        for cartella in cartelle:
            if chiave(cartella) in lette:
                continue
            lette.add(chiave(cartella))
            try:
                nomi = sorted(os.listdir(cartella))
            except OSError:
                illeggibili.append(cartella)
                continue
            for f_name in nomi:
                f_path = os.path.join(cartella, f_name)
                if not file_del_torneo(f_name, sanitized_name) or not os.path.isfile(
                    f_path
                ):
                    continue
                if f_name.lower().endswith(".json"):
                    if chiave(cartella) == chiave(cartella_del_file):
                        continue
                    if f_name != nome_del_json:
                        continue
                    try:
                        with open(f_path, encoding="utf-8") as f_in:
                            altro = json.load(f_in)
                    except (OSError, ValueError):
                        continue
                    if not (
                        isinstance(altro, dict)
                        and altro.get("name") == t_name
                        and stessa_edizione(data, altro)
                    ):
                        continue
                correlati.append(f_path)
        return correlati, illeggibili

    @staticmethod
    def _righe_per_cartella(percorsi):
        """I percorsi raggruppati per cartella: una riga con la cartella e
        una per ogni file, perche' sulla barra braille il nome di un file si
        legge meglio senza la cartella davanti."""
        gruppi = {}
        for percorso in percorsi:
            cartella = os.path.dirname(percorso)
            gruppi.setdefault(os.path.normcase(cartella), (cartella, []))[1].append(
                os.path.basename(percorso)
            )
        righe = []
        for cartella, nomi in gruppi.values():
            righe.append(_("Nella cartella {cartella}:").format(cartella=cartella))
            righe.extend(nomi)
        return righe

    def delete_tournament_completely(self, item, filepath):
        """Manda nel cestino di Windows un torneo (attivo, concluso o in
        preparazione) e i suoi file correlati, quelli di
        _file_correlati_del_torneo, che la conferma elenca cartella per
        cartella. Fino alla 10.13.7 li cancellava per sempre con os.remove, e
        si recuperavano solo da GitHub; dalla 10.13.8 passano da _nel_cestino,
        e un file che il cestino non prende resta dov'e', senza ripiegare su
        os.remove (decisione di Gabriele, avvertenza della issue 55). Il file
        del torneo va per primo: se non va nel cestino non si tocca
        nient'altro, e il torneo resta intero; se ci va, il torneo esce subito
        dall'albero e dalla memoria, e un file correlato rimasto fuori, o una
        cartella che non si legge, li nomina il messaggio finale, con il suono
        dell'errore. Un errore a meta' dice anche che il file del torneo e'
        gia' nel cestino."""
        from utils import play_sound

        t_label = self.tree_ctrl.GetItemText(item)

        # Determina la categoria del torneo per un messaggio di conferma dettagliato
        parent = self.tree_ctrl.GetItemParent(item)
        parent_data = self.tree_ctrl.GetItemData(parent) if parent else None

        is_closed = "closed tournaments" in filepath.lower() or (
            parent_data and parent_data.get("action") == "category_closed"
        )
        is_prep = parent_data and parent_data.get("action") == "category_prep"

        if is_closed:
            t_type = _("concluso")
        elif is_prep:
            t_type = _("in preparazione")
        else:
            t_type = _("attivo")

        try:
            with open(filepath, encoding="utf-8") as f_in:
                data = json.load(f_in)
        except Exception as e:
            wx.MessageBox(
                _("Impossibile leggere il file del torneo: {}").format(e),
                _("Errore"),
                wx.ICON_ERROR,
            )
            return

        t_name = data.get("name", t_label)
        if not t_name:
            t_name = t_label

        correlati, illeggibili = self._file_correlati_del_torneo(
            filepath, data, t_name
        )
        if len(illeggibili) == 1:
            frase_illeggibili = _(
                "Una cartella non si è potuta leggere, e i file del torneo che contiene restano dove sono:"
            )
        else:
            frase_illeggibili = _(
                "{count} cartelle non si sono potute leggere, e i file del torneo che contengono restano dove sono:"
            ).format(count=len(illeggibili))

        # La conferma elenca i file che vanno nel cestino, un nome per riga
        # sotto la sua cartella, da leggere con le frecce.
        righe = [
            _("Vuoi mandare nel cestino di Windows il torneo {t_type} '{t_name}'?").format(
                t_type=t_type, t_name=t_name
            )
        ]
        if correlati:
            righe.append(
                _(
                    "Ci vanno {count} file, quello del torneo e quelli che portano il suo nome intero, e dal cestino si possono recuperare:"
                ).format(count=len(correlati) + 1)
            )
        else:
            righe.append(
                _("Ci va il file del torneo, e dal cestino si può recuperare:")
            )
        righe.extend(
            self._righe_per_cartella([os.path.abspath(filepath), *correlati])
        )
        if illeggibili:
            righe.append(frase_illeggibili)
            righe.extend(illeggibili)
        dlg = AccessibleMsgDialog(
            self, _("Conferma Eliminazione Torneo"), "\n".join(righe), style=wx.YES_NO
        )
        conferma = dlg.ShowModal()
        dlg.Destroy()
        if conferma != wx.ID_YES:
            return
        torneo_nel_cestino = False
        try:
            # 1. Il file JSON del torneo, per primo. Se il cestino non lo
            # prende, per esempio su un disco senza cestino, il torneo resta
            # com'e', report compresi, e non si cancella niente per sempre.
            if os.path.exists(filepath) and not self._nel_cestino(filepath):
                play_sound("errore", self.current_tournament)
                err_msg = _(
                    "Il file del torneo {path} non è andato nel cestino, e il torneo '{t_name}' resta com'è, con tutti i suoi file. Succede su un disco senza cestino, per esempio una cartella di rete, con un file tenuto bloccato da un altro programma, oppure se hai risposto No alla domanda di Windows di cancellarlo per sempre."
                ).format(t_name=t_name, path=filepath)
                self.set_status(err_msg)
                print(err_msg)
                self._dialogo_informativo(_("Eliminazione non riuscita"), err_msg)
                return
            torneo_nel_cestino = True

            # 2. Il torneo non c'e' piu': esce subito dall'albero e, se era
            # quello aperto, dalla memoria, prima dei file correlati. Cosi' un
            # errore che arrivasse dopo non lo lascerebbe aperto, a rinascere
            # nella cartella del programma al primo salvataggio. Il cursore
            # passa da solo a un'altra voce, che non carica il suo torneo:
            # fino alla 10.13.9 al posto di quello eliminato se ne apriva un
            # altro, senza avviso.
            with self._albero_senza_caricamenti():
                self.tree_ctrl.Delete(item)
            if self._e_il_torneo_aperto(filepath):
                self._nessun_torneo_aperto()
                self.show_intro_message()
            # L'albero si ridisegna, con il cursore sulla voce dove l'ha
            # portato la cancellazione, senza caricare niente: fino alla
            # 10.13.9 restavano la voce Avvio torneo del torneo eliminato,
            # che con INVIO dava un errore, e il conteggio vecchio della sua
            # categoria.
            self.populate_tree()

            # 3. I file correlati vanno nel cestino uno per uno: quelli che non
            # ci vanno restano dove sono, e il messaggio finale li nomina.
            deleted_count = 0
            non_andati = []
            for f_path in correlati:
                if not os.path.isfile(f_path):
                    continue
                if self._nel_cestino(f_path):
                    deleted_count += 1
                else:
                    non_andati.append(f_path)

            if deleted_count == 0:
                info_msg = _(
                    "Torneo '{t_name}' mandato nel cestino di Windows."
                ).format(t_name=t_name)
            elif deleted_count == 1:
                info_msg = _(
                    "Torneo '{t_name}' mandato nel cestino di Windows, con un file correlato."
                ).format(t_name=t_name)
            else:
                info_msg = _(
                    "Torneo '{t_name}' mandato nel cestino di Windows, con {deleted_count} file correlati."
                ).format(t_name=t_name, deleted_count=deleted_count)
            righe_finali = [info_msg]
            stato = [info_msg]
            if non_andati:
                if len(non_andati) == 1:
                    frase = _(
                        "Un file correlato non è andato nel cestino, e resta dov'è:"
                    )
                else:
                    frase = _(
                        "{count} file correlati non sono andati nel cestino, e restano dove sono:"
                    ).format(count=len(non_andati))
                righe_finali += [frase, *non_andati]
                stato.append(f"{frase} {', '.join(non_andati)}")
            if illeggibili:
                righe_finali += [frase_illeggibili, *illeggibili]
                stato.append(f"{frase_illeggibili} {', '.join(illeggibili)}")
            if len(righe_finali) == 1:
                play_sound("cancellato", self.current_tournament)
                self.set_status(info_msg)
                print(info_msg)
                return
            # Qualcosa e' rimasto fuori: il suono dell'errore, e non quello del
            # successo pieno, poi una finestra con un percorso per riga.
            play_sound("errore", self.current_tournament)
            self.set_status(" ".join(stato))
            testo = "\n".join(righe_finali)
            print(testo)
            self._dialogo_informativo(_("File rimasti fuori dal cestino"), testo)
        except Exception as e:
            play_sound("errore", self.current_tournament)
            err_msg = _("Errore durante l'eliminazione del torneo: {}").format(e)
            if torneo_nel_cestino:
                err_msg += " " + _(
                    "Il file del torneo {path} è già nel cestino di Windows, e da lì si può recuperare."
                ).format(path=filepath)
            self.set_status(err_msg)
            print(err_msg)
            self._dialogo_informativo(_("Eliminazione non riuscita"), err_msg)

    def on_delete_active_tournament_menu(self, event):
        item = self.tree_ctrl.GetSelection()
        if not item or not item.IsOk():
            from utils import play_sound

            play_sound("errore", self.current_tournament)
            wx.MessageBox(
                _(
                    "Seleziona prima un torneo attivo dall'albero per poterlo eliminare."
                ),
                _("Avviso"),
                wx.ICON_WARNING,
            )
            return

        data = self.tree_ctrl.GetItemData(item)
        if not data:
            from utils import play_sound

            play_sound("errore", self.current_tournament)
            wx.MessageBox(
                _(
                    "Seleziona prima un torneo attivo dall'albero per poterlo eliminare."
                ),
                _("Avviso"),
                wx.ICON_WARNING,
            )
            return

        action = data.get("action")
        if action == "show_player_detail":
            player_data = data.get("player")
            self.delete_player_from_tournament(item, player_data)
            return
        if action in ["select_tournament", "load_concluded"]:
            filepath = data.get("filepath")
            if not filepath:
                from utils import play_sound

                play_sound("errore", self.current_tournament)
                wx.MessageBox(
                    _(
                        "Seleziona prima un torneo attivo dall'albero per poterlo eliminare."
                    ),
                    _("Avviso"),
                    wx.ICON_WARNING,
                )
                return
            self.delete_tournament_completely(item, filepath)
            return
        from utils import play_sound

        play_sound("errore", self.current_tournament)
        wx.MessageBox(
            _(
                "Seleziona prima un torneo attivo dall'albero per poterlo eliminare."
            ),
            _("Avviso"),
            wx.ICON_WARNING,
        )
        return

    def start_new_tournament_wizard(self):
        """Inizia il flusso guidato di inserimento dati nell'albero per il Nuovo Torneo."""
        from datetime import datetime, timedelta

        from config import DATE_FORMAT_ISO
        from utils import play_sound

        oggi_dt = datetime.now()
        oggi_str = oggi_dt.strftime(DATE_FORMAT_ISO)
        future_dt = oggi_dt + timedelta(days=60)
        future_str = future_dt.strftime(DATE_FORMAT_ISO)

        self.creation_mode = True
        self.last_activated_field = None
        self.creation_data = {
            "name": "",
            "site": "Online",
            "start_date": oggi_str,
            "end_date": future_str,
            "rounds": 5,
            "time_control": "60+0",
            # La cartella del programma, non quella da cui e' stato avviato:
            # con os.path.abspath(".") un torneo creato lanciando Tornello da
            # un'altra cartella finiva li', lontano da tutti gli altri.
            "save_path": _cartella_predefinita_tornei(),
            "chief_arbiter": "N/D",
            "deputy_chief_arbiters": "",
            "federation_code": "ITA",
            "color_board1": "white1",
            "bye_value": 0.5,
        }
        play_sound("notifica")
        self.populate_new_tournament_wizard_tree()

    def populate_new_tournament_wizard_tree(self):
        self.tree_ctrl.DeleteAllItems()
        self.tree_root = self.tree_ctrl.AddRoot(_("Nuovo Torneo"))

        # Voce Indietro per annullare
        back_item = self.tree_ctrl.AppendItem(self.tree_root, _("Indietro"))
        self.tree_ctrl.SetItemData(back_item, {"action": "wizard_back"})

        name_val = self.creation_data["name"] or _("Non impostato")
        site_val = self.creation_data["site"] or _("Non impostato")

        from utils import format_date_locale

        start_val = format_date_locale(self.creation_data["start_date"])
        end_val = format_date_locale(self.creation_data["end_date"])

        rounds_val = str(self.creation_data["rounds"])
        tc_val = self.creation_data["time_control"] or _("Non impostato")
        path_val = self.creation_data["save_path"]
        arb_val = self.creation_data["chief_arbiter"] or _("Non impostato")
        dep_val = self.creation_data["deputy_chief_arbiters"] or _("Non impostate")
        fed_val = self.creation_data["federation_code"] or "ITA"

        col_raw = self.creation_data["color_board1"]
        col_disp_map = {
            "white1": _("Bianco (scelto dall'arbitro)"),
            "black1": _("Nero (scelto dall'arbitro)"),
            "random": _("Casuale (scelto da {app})").format(app="Tornello"),
        }
        col_val = col_disp_map.get(col_raw, _("Bianco (scelto dall'arbitro)"))

        bye_val = str(self.creation_data["bye_value"])

        self.tree_name = self.tree_ctrl.AppendItem(
            self.tree_root, _("Nome torneo *: {}").format(name_val)
        )
        self.tree_ctrl.SetItemData(self.tree_name, {"field": "name"})

        self.tree_site = self.tree_ctrl.AppendItem(
            self.tree_root, _("Luogo (Site): {}").format(site_val)
        )
        self.tree_ctrl.SetItemData(self.tree_site, {"field": "site"})

        self.tree_start = self.tree_ctrl.AppendItem(
            self.tree_root, _("Data inizio: {}").format(start_val)
        )
        self.tree_ctrl.SetItemData(self.tree_start, {"field": "start_date"})

        self.tree_end = self.tree_ctrl.AppendItem(
            self.tree_root, _("Data fine: {}").format(end_val)
        )
        self.tree_ctrl.SetItemData(self.tree_end, {"field": "end_date"})

        self.tree_rounds = self.tree_ctrl.AppendItem(
            self.tree_root, _("Numero turni: {}").format(rounds_val)
        )
        self.tree_ctrl.SetItemData(self.tree_rounds, {"field": "rounds"})

        self.tree_tc = self.tree_ctrl.AppendItem(
            self.tree_root, _("Tempo riflessione: {}").format(tc_val)
        )
        self.tree_ctrl.SetItemData(self.tree_tc, {"field": "time_control"})

        self.tree_path = self.tree_ctrl.AppendItem(
            self.tree_root, _("Cartella di salvataggio: {}").format(path_val)
        )
        self.tree_ctrl.SetItemData(self.tree_path, {"field": "save_path"})

        self.tree_arb = self.tree_ctrl.AppendItem(
            self.tree_root, _("Arbitro Capo: {}").format(arb_val)
        )
        self.tree_ctrl.SetItemData(self.tree_arb, {"field": "chief_arbiter"})

        self.tree_dep = self.tree_ctrl.AppendItem(
            self.tree_root, _("Collaboratori / Vice Arbitri: {}").format(dep_val)
        )
        self.tree_ctrl.SetItemData(self.tree_dep, {"field": "deputy_chief_arbiters"})

        self.tree_fed = self.tree_ctrl.AppendItem(
            self.tree_root, _("Codice Federazione: {}").format(fed_val)
        )
        self.tree_ctrl.SetItemData(self.tree_fed, {"field": "federation_code"})

        self.tree_col = self.tree_ctrl.AppendItem(
            self.tree_root, _("Colore al giocatore più forte: {}").format(col_val)
        )
        self.tree_ctrl.SetItemData(self.tree_col, {"field": "color_board1"})

        self.tree_bye = self.tree_ctrl.AppendItem(
            self.tree_root, _("Valore del BYE: {}").format(bye_val)
        )
        self.tree_ctrl.SetItemData(self.tree_bye, {"field": "bye_value"})

        # Verifica se i campi obbligatori sono validati per mostrare "Iscrizione Giocatori"
        if self.creation_data["name"] and self.creation_data["time_control"]:
            next_item = self.tree_ctrl.AppendItem(
                self.tree_root, _("Iscrizione Giocatori")
            )
            self.tree_ctrl.SetItemData(next_item, {"action": "wizard_next"})

        if not (self.tree_ctrl.GetWindowStyleFlag() & wx.TR_HIDE_ROOT):
            self.tree_ctrl.Expand(self.tree_root)

        # Ripristina la selezione ed il focus sul campo modificato dopo 300 ms per lo screen reader
        if hasattr(self, "last_activated_field") and self.last_activated_field:
            target_item = self.find_tree_item_by_field(self.last_activated_field)
            if target_item:
                wx.CallLater(300, self._restore_tree_focus, target_item)
        else:
            if hasattr(self, "tree_name") and self.tree_name:
                wx.CallLater(300, self._restore_tree_focus, self.tree_name)

    def find_tree_item_by_field(self, field_name):
        field_map = {
            "name": getattr(self, "tree_name", None),
            "site": getattr(self, "tree_site", None),
            "start_date": getattr(self, "tree_start", None),
            "end_date": getattr(self, "tree_end", None),
            "rounds": getattr(self, "tree_rounds", None),
            "time_control": getattr(self, "tree_tc", None),
            "save_path": getattr(self, "tree_path", None),
            "chief_arbiter": getattr(self, "tree_arb", None),
            "deputy_chief_arbiters": getattr(self, "tree_dep", None),
            "federation_code": getattr(self, "tree_fed", None),
            "color_board1": getattr(self, "tree_col", None),
            "bye_value": getattr(self, "tree_bye", None),
        }
        return field_map.get(field_name)

    def _restore_tree_focus(self, item):
        if item and item.IsOk():
            self.tree_ctrl.SetFocus()
            self.tree_ctrl.SelectItem(item)
            self.tree_ctrl.EnsureVisible(item)

    def on_exit(self, event):
        self.Close()

    def on_preferences(self, event):
        old_lang = self.settings.get("language", "it")
        # Il fuoco torna dove era prima delle impostazioni, in qualunque modo
        # si chiudano: dalla 10.13.38 lo rimette GBwx 1.0.1 alla distruzione
        # della finestra, come per tutte le altre. Dalla 10.13.25 alla
        # 10.13.37 lo rimetteva un rimedio qui, pensato per questa finestra
        # sola, mentre il fuoco restava sulla cornice, dove NVDA legge
        # soltanto il titolo, dopo ogni finestra costruita con GBwx.
        dlg = VisualSettingsDialog(self, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            new_settings = dlg.get_settings()
            new_lang = new_settings.get("language", "it")
            # Le Preferenze conoscono solo le chiavi che mostrano: le altre,
            # come il rinvio dell'avviso sulle copie di sicurezza vecchie,
            # restano quelle di prima invece di sparire dal file.
            self.settings = {**self.settings, **new_settings}
            salvate = save_settings(self.settings)
            self.apply_theme()
            if salvate:
                self.set_status(_("Impostazioni salvate ed applicate."))
            else:
                self.set_status(
                    _("Impostazioni applicate adesso, ma non salvate su disco: al prossimo avvio torneranno le precedenti. Dettagli in error.log.")
                )

            if old_lang != new_lang:
                msg = _(
                    "La lingua è stata cambiata. Riavvia l'applicazione affinché le modifiche abbiano effetto."
                )
                dlg_msg = AccessibleMsgDialog(
                    self,
                    _("Riavvio Richiesto"),
                    msg,
                    style=wx.OK,
                    settings=self.settings,
                )
                dlg_msg.ShowModal()
                dlg_msg.Destroy()
        else:
            # Il cursore del volume scrive il file a ogni scatto, per il
            # suono di prova: annullando si rimette il volume di prima
            # (10.13.26).
            dlg.rimetti_il_volume()
        dlg.Destroy()

    @staticmethod
    def _leggi_manuale():
        """Il testo di MANUALE.txt, o una stringa vuota se manca o non si
        legge. Lo usano F1, che lo mostra intero, e l'arrivo del focus sul pie'
        di pagina, che ne mostra la sezione degli acronimi."""
        from config import resource_path

        try:
            with open(resource_path("MANUALE.txt"), encoding="utf-8") as f:
                return f.read()
        except (OSError, ValueError):
            return ""

    def on_help(self, event):
        # Visualizza la guida accessibile caricandola da file
        self.main_text.Clear()
        guide_text = self._leggi_manuale()
        if not guide_text:
            guide_text = _(
                "Manuale guida di Tornello\n"
                "File MANUALE.txt non trovato. Consultare la guida online o ripristinare il file."
            )
        self.append_log(guide_text)
        self.main_text.SetFocus()

    def on_changelog(self, event):
        self.main_text.Clear()
        changelog_str = ""
        from config import resource_path

        changelog_path = resource_path("ChangeLog.txt")
        if os.path.exists(changelog_path):
            try:
                with open(changelog_path, encoding="utf-8") as f:
                    changelog_str = f.read()
            except Exception:
                pass

        if not changelog_str:
            changelog_str = _(
                "Changelog di Tornello\n"
                "File ChangeLog.txt non trovato. Consultare la guida online o ripristinare il file."
            )
        self.append_log(changelog_str)
        self.main_text.SetFocus()

    def on_credits(self, event):
        self.main_text.Clear()
        credits_str = ""
        from config import resource_path

        credits_path = resource_path("CREDITS.txt")
        if os.path.exists(credits_path):
            try:
                with open(credits_path, encoding="utf-8") as f:
                    credits_str = f.read()
            except Exception:
                pass

        if not credits_str:
            credits_str = _(
                "CREDITI DI TORNELLO\n\nTornello è sviluppato da {}."
            ).format(__authors__)
        self.append_log(credits_str)
        self.main_text.SetFocus()

    def on_fide_query(self, event):
        players_db = self._database_dei_giocatori()
        if players_db is None:
            return
        from gui.dialogs.fide_query_dialog import FideQueryDialog

        dlg = FideQueryDialog(self, players_db, self.settings)
        dlg.ShowModal()
        dlg.Destroy()

    def on_backup_cleanup(self, event, seleziona=None):
        """La finestra Copie di sicurezza, dal menu File, dalla domanda
        dell'avvio e da Apri Torneo su una copia. seleziona e' l'elenco delle
        copie da trovare gia' selezionate. Alla chiusura l'albero si rilegge:
        un ripristino o una cancellazione possono averlo cambiato, ma senza
        toccare il fuoco: GBwx lo rimette, quando la finestra se ne va
        davvero, sul controllo che lo aveva alla sua apertura, l'albero, la
        barra di stato o l'area centrale. Fino alla 10.13.38 la rilettura lo
        portava sempre sull'albero, prima ancora che la finestra se ne
        andasse."""
        from gui.dialogs.backup_cleanup_dialog import BackupCleanupDialog

        dlg = BackupCleanupDialog(
            self,
            self.settings,
            torneo_aperto=self.active_filename,
            seleziona=seleziona,
            dopo_il_ripristino=self._dopo_il_ripristino,
        )
        dlg.ShowModal()
        dlg.Destroy()
        self.populate_tree(prendi_il_fuoco=False)
        self.update_status_display()

    def _dopo_il_ripristino(self, esito):
        """Riallinea la finestra a un ripristino riuscito, subito, mentre la
        finestra delle copie e' ancora aperta. Se il torneo ripristinato e'
        quello aperto, o il file aperto se n'e' andato nel cestino con
        l'archivio, o non c'e' un torneo aperto, il torneo ripristinato si
        carica: tenuto in memoria quello di prima, il primo salvataggio lo
        riscriverebbe sul disco al posto della copia. Poi _save_state
        rigenera classifica, turno e raccolta delle partite. Con un altro
        torneo aperto basta rileggere l'albero, e durante la creazione di un
        torneo nuovo nemmeno quello: la procedura guidata resta com'e'."""
        if getattr(self, "creation_mode", False):
            return
        if not esito.riuscito or esito.tipo not in ("torneo", "finalizzato") or not esito.destinazione:
            self.populate_tree()
            return
        aperto = self.active_filename
        stesso = bool(aperto) and os.path.normcase(os.path.abspath(aperto)) == os.path.normcase(
            os.path.abspath(esito.destinazione)
        )
        if stesso or not self.current_tournament or not (aperto and os.path.exists(aperto)):
            self.load_tournament(esito.destinazione)
            if self.current_tournament:
                self._save_state()
            return
        self.populate_tree()

    def on_fide_update(self, event):
        import os
        from datetime import datetime

        from config import FIDE_DB_JSON_LEGACY, FIDE_DB_LOCAL_FILE
        from fide_db import cleanup_legacy_json

        # Fallback: elimina vecchio JSON se presente
        if os.path.exists(FIDE_DB_JSON_LEGACY):
            cleanup_legacy_json()

        msg = ""
        if os.path.exists(FIDE_DB_LOCAL_FILE):
            file_mod_timestamp = os.path.getmtime(FIDE_DB_LOCAL_FILE)
            file_age_days = (
                datetime.now() - datetime.fromtimestamp(file_mod_timestamp)
            ).days
            msg = _(
                "Il database FIDE locale corrente è stato aggiornato {days} giorni fa.\n\n"
            ).format(days=file_age_days)
        else:
            msg = _("Nessun database FIDE locale trovato.\n\n")

        msg += _(
            "Desideri collegarti a ratings.fide.com e scaricare l'ultimo aggiornamento?"
        )

        dlg = AccessibleMsgDialog(
            self, _("Verifica Aggiornamenti FIDE"), msg, style=wx.YES_NO
        )
        if dlg.ShowModal() == wx.ID_YES:
            dlg.Destroy()
            from gui.dialogs.fide_update_dialog import FideUpdateDialog

            update_dlg = FideUpdateDialog(self, self.settings)
            esito = update_dlg.ShowModal()
            update_dlg.Destroy()

            # La versione testuale propone la sincronizzazione subito dopo un
            # aggiornamento riuscito; qui mancava del tutto. FideUpdateDialog
            # chiude con wx.ID_OK solo quando l'aggiornamento e' andato a buon
            # fine, vedi il suo on_update_complete.
            if esito == wx.ID_OK:
                dlg_prop = AccessibleMsgDialog(
                    self,
                    _("Sincronizzazione Database"),
                    _(
                        "Database FIDE aggiornato. Vuoi sincronizzare ora il tuo database personale dei giocatori con i nuovi dati?"
                    ),
                    style=wx.YES_NO,
                )
                if dlg_prop.ShowModal() == wx.ID_YES:
                    dlg_prop.Destroy()
                    self.on_sync_db(None)
                else:
                    dlg_prop.Destroy()
        else:
            dlg.Destroy()

    def on_sync_db(self, event):
        from gui.dialogs.sync_database_dialog import SyncDatabaseDialog

        # La finestra legge e salva il database da se': se non si legge, non
        # si apre (10.13.15).
        if self._database_dei_giocatori() is None:
            return
        dlg = SyncDatabaseDialog(self, self.settings)
        dlg.ShowModal()
        dlg.Destroy()

    def on_local_db(self, event):
        from gui.dialogs.players_db_dialog import PlayersDbDialog

        # La finestra legge e salva il database da se': se non si legge, non
        # si apre (10.13.15).
        if self._database_dei_giocatori() is None:
            return
        dlg = PlayersDbDialog(self, self.settings)
        dlg.ShowModal()
        dlg.Destroy()

    def on_close(self, event):
        # Il timer del pie' di pagina si ferma per primo: l'invito alla
        # donazione, con la sua finestra modale, fa girare il ciclo degli
        # eventi, e un timer ancora acceso dopo la chiusura scatterebbe su
        # controlli ormai distrutti.
        self._timer_pie_di_pagina.Stop()
        from utils import copie_di_chiusura, play_sound

        copie_di_chiusura(self.active_filename)

        # sync=True aspetterebbe senza limite che l'audio segnali la fine:
        # se lo stream smette di rispondere, per esempio subito dopo un
        # carico pesante come l'importazione FIDE, l'applicazione resta
        # bloccata in chiusura e va terminata a forza. Un tempo massimo
        # tiene comunque l'attesa breve, senza lasciare la chiusura in balia
        # dell'audio.
        play_sound("chiusura", self.current_tournament, sync=1.5)

        # Dalla 10.8.1 la chiusura che applica un aggiornamento salta
        # l'invito: lo script che sostituisce il programma aspetta la sua
        # uscita una trentina di secondi soltanto, e chi leggeva l'invito con
        # calma si ritrovava con l'aggiornamento non applicato.
        if not self._chiusura_per_aggiornamento:
            try:
                self._invito_donazione()
            except Exception as errore:  # noqa: BLE001
                # Largo di proposito: un'eccezione che uscisse da on_close
                # salterebbe event.Skip() e la finestra non si chiuderebbe piu',
                # per colpa di un invito che non serve a niente del lavoro fatto.
                # Ma non tace piu' come l'except: pass di prima: il guasto finisce
                # in error.log, con il suo traceback.
                from gui.settings import _registra

                _registra(f"Invito alla donazione non mostrato: {errore}")

        event.Skip()

    def _invito_donazione(self):
        """L'invito a offrire un caffe', nella lingua delle impostazioni.

        Donazione, dalla V2.1.0 di GBUtils, restituisce il messaggio, o None se
        il sorteggio non passa, e con stampa=False non stampa niente. Fino alla
        10.3.4 la stampa si catturava deviando sys.stdout su uno StringIO, un
        aggiramento nato quando Donazione sapeva soltanto stampare.
        """
        from GBUtils import Donazione

        lingua = self.settings.get("language") if self.settings else None
        testo = Donazione(lang=lingua, stampa=False)
        if testo is None:
            return
        from gui.dialogs.donation_dialog import DonationDialog

        dlg = DonationDialog(self, _("Offri un caffè"), testo, self.settings)
        dlg.ShowModal()
        dlg.Destroy()

    def on_new_tournament(self, event):
        self.start_new_tournament_wizard()

    def on_open_tournament(self, event):
        dlg = wx.FileDialog(
            self,
            _("Apri Torneo"),
            wildcard="JSON files (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        scelto = dlg.GetPath() if dlg.ShowModal() == wx.ID_OK else None
        dlg.Destroy()
        if not scelto:
            return
        # Una copia di sicurezza aperta come torneo diventava il file attivo:
        # ogni salvataggio la modificava sul posto, e rigenerava classifica,
        # turni e raccolta delle partite del torneo vero con lo stato vecchio
        # della copia. Fino alla 10.8.11 Tornello la apriva senza dire niente.
        from utils import dentro_la_cartella, play_sound

        if dentro_la_cartella(scelto, user_data_path("backup")):
            play_sound("errore")
            # Dalla 10.9.0 le copie si usano dalla finestra delle copie di
            # sicurezza, e la domanda la propone con la copia gia'
            # selezionata. Si' e' il predefinito: aprire la finestra non
            # cambia niente. ESC vale No, come in tutte le domande dalla
            # 10.13.23.
            dlg_rifiuto = AccessibleMsgDialog(
                self,
                _("Copia di sicurezza"),
                _(
                    "Il file {name} è una copia di sicurezza: sta nella cartella backup, e Tornello non lo apre come torneo.\n"
                    "Aperto così, verrebbe modificato a ogni salvataggio, e classifica, turni e raccolta delle partite del torneo verrebbero riscritti con lo stato vecchio della copia.\n"
                    "Vuoi aprire la finestra delle copie di sicurezza, con questa copia già selezionata? Da lì puoi leggerla, confrontarla con lo stato attuale e ripristinarla."
                ).format(name=os.path.basename(scelto)),
                style=wx.YES_NO,
                settings=self.settings,
            )
            risposta = dlg_rifiuto.ShowModal()
            dlg_rifiuto.Destroy()
            if risposta == wx.ID_YES:
                self.on_backup_cleanup(None, seleziona=[scelto])
            return
        # Se il file scelto non si apre, o non e' un torneo, resta aperto il
        # torneo di prima.
        self.load_tournament(scelto, tieni_il_precedente=True)
        # Il cursore dell'albero passa sulla voce del torneo aperto, anche
        # se stava su una voce che non e' di un torneo, come Nuovo torneo;
        # senza caricare di nuovo e senza cambiare l'area centrale.
        if self._e_il_torneo_aperto(scelto):
            voce = self._voce_del_torneo_aperto()
            if voce and voce.IsOk():
                with self._albero_senza_caricamenti():
                    self.tree_ctrl.SelectItem(voce)

    def on_enroll_players(self, event):
        if not self.current_tournament:
            wx.MessageBox(_("Nessun torneo attivo."), _("Errore"), wx.ICON_ERROR)
            return
        if len(self.current_tournament.get("rounds", [])) > 0:
            wx.MessageBox(
                _(
                    "Impossibile modificare l'iscrizione dei giocatori: il torneo è già iniziato."
                ),
                _("Errore"),
                wx.ICON_ERROR,
            )
            return
        players_db = self._database_dei_giocatori()
        if players_db is None:
            return
        from gui.dialogs import PlayerEnrollmentDialog

        enrolled_raw = [p for p in self.current_tournament.get("players", [])]
        category = self.current_tournament.get("tournament_category", "standard")
        dlg = PlayerEnrollmentDialog(
            self, players_db, enrolled_raw, self.settings, category=category
        )
        if dlg.ShowModal() == wx.ID_OK:
            enrolled = dlg.get_enrolled_players()
            if len(enrolled) < 2:
                wx.MessageBox(
                    _("Sono necessari almeno 2 giocatori per il torneo."),
                    _("Errore"),
                    wx.ICON_ERROR,
                )
                dlg.Destroy()
                return

            from stats import get_initial_elo_for_tournament

            category = self.current_tournament.get("tournament_category", "standard")
            for p in enrolled:
                p["initial_elo"] = get_initial_elo_for_tournament(p, category)

            from models import Player

            self.current_tournament["players"] = [
                Player.from_dict(p).to_dict() for p in enrolled
            ]
            self.current_tournament["players_dict"] = {
                p["id"]: p for p in self.current_tournament["players"]
            }
            self._save_state()
            self.populate_tree()
            self.show_current_round_report()
        dlg.Destroy()

    def on_view_players(self, event):
        if not self.current_tournament:
            wx.MessageBox(_("Nessun torneo attivo."), _("Errore"), wx.ICON_ERROR)
            return
        self.main_text.Clear()
        report = _("Elenco Giocatori Iscritti:\n\n")
        for i, p in enumerate(self.current_tournament.get("players", []), 1):
            elo_str = (
                f"({int(p.get('current_elo', 0))})" if p.get("current_elo") else ""
            )
            report += f"{i:2d}. {p.get('first_name', '')} {p.get('last_name', '')} {elo_str}\n"
        self.append_log(report)
        self.main_text.SetFocus()

    def on_view_current_round(self, event):
        if not self.current_tournament:
            wx.MessageBox(_("Nessun torneo attivo."), _("Errore"), wx.ICON_ERROR)
            return
        self.show_current_round_report()
        self.main_text.SetFocus()

    def on_view_standings(self, event):
        if not self.current_tournament:
            wx.MessageBox(_("Nessun torneo attivo."), _("Errore"), wx.ICON_ERROR)
            return
        # La stessa classifica della voce dell'albero: per un torneo concluso
        # e' quella finale. Fino alla 10.13.13 Ctrl+L la dava sempre parziale,
        # Dopo Turno N, e senza le posizioni finali.
        self.show_standings_verbose()
        self.main_text.SetFocus()

    def on_rollback_round(self, event):
        if not self.current_tournament:
            wx.MessageBox(_("Nessun torneo attivo."), _("Errore"), wx.ICON_ERROR)
            return
        rounds = self.current_tournament.get("rounds", [])
        if not rounds:
            wx.MessageBox(
                _("Impossibile annullare il turno: nessun turno giocato."),
                _("Errore"),
                wx.ICON_ERROR,
            )
            return

        # La domanda nomina il torneo: il menu Torneo vale per il torneo
        # appena scelto nell'albero, e l'ultima parola prima di un'azione
        # irreversibile deve dire su quale torneo si agisce.
        dlg = AccessibleMsgDialog(
            self,
            _("Annulla Turno"),
            _(
                "Sei sicuro di voler annullare l'ultimo turno del torneo {name} e tornare indietro? Questa azione è irreversibile."
            ).format(name=self.current_tournament.get("name", _("Torneo Sconosciuto"))),
            style=wx.YES_NO,
        )
        if dlg.ShowModal() == wx.ID_YES:
            from tournament import rollback_to_previous_round

            if rollback_to_previous_round(self.current_tournament):
                self._save_state()
                self.populate_tree()
                self.show_current_round_report()
                self.set_status(
                    _("Time Machine attivata: tornati al turno precedente.")
                )
        dlg.Destroy()

    def _database_dei_giocatori(self):
        """Il database dei giocatori letto dal disco, oppure None, dopo il
        suono d'errore e un messaggio, se il file c'e' ma non si legge,
        perche' un altro programma lo tiene bloccato o perche' e' rovinato.
        Chi lo chiede lo modificherebbe e lo salverebbe: il salvataggio non
        riuscirebbe, ed e' meglio dirlo prima. Fino alla 10.13.14 il database
        illeggibile arrivava vuoto, e il primo salvataggio lo sostituiva sul
        disco con le sole schede aggiunte: nell'iscrizione e nelle finestre
        del database dalla 10.13.15, nella finalizzazione dalla 10.13.16."""
        from db_players import (
            database_non_letto,
            load_players_db,
            messaggio_database_non_letto,
        )
        from utils import play_sound

        players_db = load_players_db()
        if not database_non_letto(players_db):
            return players_db
        play_sound("errore")
        dlg = AccessibleMsgDialog(
            self,
            _("Errore"),
            messaggio_database_non_letto(players_db),
            settings=self.settings,
        )
        dlg.ShowModal()
        dlg.Destroy()
        return None

    @staticmethod
    def _esito_della_finalizzazione(riuscita, avvisi):
        """Titolo e testo della finestra che chiude la finalizzazione, oppure
        None quando basta il messaggio di successo, cioe' quando la
        finalizzazione e' riuscita e non ha niente da segnalare.
        Con degli avvisi il messaggio di successo non compare: diceva i
        giocatori aggiornati anche quando nessuno lo era, e arrivava a NVDA
        prima degli avvisi che lo smentivano. La prima riga dice com'e' andata,
        le altre sono gli avvisi."""
        if riuscita and not avvisi:
            return None
        if riuscita:
            apertura = _(
                "Il torneo è concluso e archiviato, ma non tutto è andato come al solito: leggi gli avvisi qui sotto."
            )
        else:
            apertura = _(
                "La finalizzazione non è andata fino in fondo: gli avvisi qui sotto dicono che cosa è stato fatto e che cosa no."
            )
        return _("Avvisi della finalizzazione"), "\n".join([apertura, *avvisi])

    def on_finalize_tournament(self, event):
        if not self.current_tournament:
            wx.MessageBox(_("Nessun torneo attivo."), _("Errore"), wx.ICON_ERROR)
            return

        is_concluded = (
            self.current_tournament.get("concluded", False)
            if self.current_tournament
            else False
        )

        if is_concluded:
            wx.MessageBox(
                _("Il torneo è già concluso e finalizzato."), _("Errore"), wx.ICON_ERROR
            )
            return

        rounds = self.current_tournament.get("rounds", [])
        if not rounds:
            wx.MessageBox(
                _("Il torneo non è ancora iniziato."), _("Errore"), wx.ICON_ERROR
            )
            return

        curr_round_num = self.current_tournament.get("current_round", 1)
        total_rounds = self.current_tournament.get("total_rounds", 0)

        if curr_round_num < total_rounds:
            wx.MessageBox(
                _(
                    "Impossibile finalizzare il torneo prima di aver completato tutti i turni previsti."
                ),
                _("Errore"),
                wx.ICON_ERROR,
            )
            return

        last_round = rounds[-1]
        for m in last_round.get("matches", []):
            if m.get("result") is None:
                wx.MessageBox(
                    _(
                        "Impossibile finalizzare il torneo: ci sono ancora partite senza risultato nell'ultimo turno."
                    ),
                    _("Errore"),
                    wx.ICON_ERROR,
                )
                return

        # La domanda nomina il torneo, come quella di Annulla Turno: il
        # database dei giocatori cambia per sempre.
        dlg = AccessibleMsgDialog(
            self,
            _("Finalizza Torneo"),
            _(
                "Sei sicuro di voler concludere definitivamente il torneo {name}? Verranno calcolati i piazzamenti finali, gli spareggi e aggiornati gli ELO nel database giocatori."
            ).format(name=self.current_tournament.get("name", _("Torneo Sconosciuto"))),
            style=wx.YES_NO,
        )
        if dlg.ShowModal() == wx.ID_YES:
            # Con il database che non si legge la finalizzazione non parte:
            # creerebbe nel database tutti gli iscritti, e il file sul disco
            # perderebbe tutti gli altri giocatori (10.13.16).
            players_db = self._database_dei_giocatori()
            if players_db is None:
                dlg.Destroy()
                return

            from ui import finalize_tournament

            # Gli avvisi che la finalizzazione stampa in console, qui
            # altrimenti invisibili: giocatori che avevano gia' il torneo
            # nello storico, copie di sicurezza non riuscite, file del torneo
            # rimasto al suo posto perche' la copia in archivio non torna.
            avvisi = []
            success = finalize_tournament(
                self.current_tournament, players_db, self.active_filename, avvisi
            )
            esito = self._esito_della_finalizzazione(success, avvisi)
            if esito is None:
                wx.MessageBox(
                    _(
                        "Torneo finalizzato con successo! I dati dei giocatori sono stati aggiornati."
                    ),
                    _("Successo"),
                    wx.ICON_INFORMATION,
                )
            else:
                titolo, testo = esito
                dlg_avvisi = AccessibleMsgDialog(
                    self, titolo, testo, settings=self.settings
                )
                dlg_avvisi.ShowModal()
                dlg_avvisi.Destroy()
            if success:
                # Nessun torneo resta aperto: fino alla 10.13.9 la
                # ricostruzione dell'albero ne apriva un altro senza avviso.
                self._nessun_torneo_aperto()
                # Dopo la finestra di conferma il focus resterebbe nel vuoto:
                # lo si riporta nell'albero, sulla voce che serve subito dopo
                # aver chiuso un torneo.
                self._tree_restore_target = {"action": "start_new_tournament"}
                self.populate_tree()
                self.show_intro_message()
                self.set_status(_("Torneo concluso e archiviato."))
        dlg.Destroy()

    def on_active_field_activated(self, item, field_active):
        from utils import format_date_locale, play_sound

        is_started = len(self.current_tournament.get("rounds", [])) > 0
        if is_started and field_active in ["time_control", "color_board1", "bye_value"]:
            play_sound("errore")
            dlg_err = AccessibleMsgDialog(
                self,
                _("Errore"),
                _("Non è possibile modificare questo parametro a torneo iniziato."),
                settings=self.settings,
            )
            dlg_err.ShowModal()
            dlg_err.Destroy()
            return

        play_sound("apertura")

        if field_active == "name":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci il nome del torneo:"),
                _("Nome Torneo"),
                self.current_tournament["name"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                new_val = dlg.GetValue().strip()
                if new_val != self.current_tournament.get("name"):
                    self.current_tournament["name"] = new_val
                    self.tree_ctrl.SetItemText(
                        item, _("Nome torneo: {}").format(new_val)
                    )
                    self._save_state()
                play_sound("conferma")
            dlg.Destroy()
        elif field_active == "site":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci il luogo (Site):"),
                _("Luogo Torneo"),
                self.current_tournament["site"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                new_val = dlg.GetValue().strip()
                if new_val != self.current_tournament.get("site"):
                    self.current_tournament["site"] = new_val
                    self.tree_ctrl.SetItemText(
                        item, _("Luogo (Site): {}").format(new_val)
                    )
                    self._save_state()
                play_sound("conferma")
            dlg.Destroy()
        elif field_active == "start_date":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci la data di inizio (AAAA-MM-GG):"),
                _("Data Inizio"),
                self.current_tournament["start_date"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                if val != self.current_tournament.get("start_date"):
                    try:
                        from datetime import datetime

                        datetime.strptime(val, "%Y-%m-%d")
                        self.current_tournament["start_date"] = val
                        self.tree_ctrl.SetItemText(
                            item, _("Data inizio: {}").format(format_date_locale(val))
                        )
                        self._save_state()
                        play_sound("conferma")
                    except ValueError:
                        play_sound("errore")
                        dlg_err = AccessibleMsgDialog(
                            self,
                            _("Errore"),
                            _("Formato data non valido. Usa AAAA-MM-GG."),
                            settings=self.settings,
                        )
                        dlg_err.ShowModal()
                        dlg_err.Destroy()
            dlg.Destroy()
        elif field_active == "end_date":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci la data di fine (AAAA-MM-GG):"),
                _("Data Fine"),
                self.current_tournament["end_date"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                if val != self.current_tournament.get("end_date"):
                    try:
                        from datetime import datetime

                        datetime.strptime(val, "%Y-%m-%d")
                        self.current_tournament["end_date"] = val
                        self.tree_ctrl.SetItemText(
                            item, _("Data fine: {}").format(format_date_locale(val))
                        )
                        self._save_state()
                        play_sound("conferma")
                    except ValueError:
                        play_sound("errore")
                        dlg_err = AccessibleMsgDialog(
                            self,
                            _("Errore"),
                            _("Formato data non valido. Usa AAAA-MM-GG."),
                            settings=self.settings,
                        )
                        dlg_err.ShowModal()
                        dlg_err.Destroy()
            dlg.Destroy()
        elif field_active == "time_control":
            tc = self.current_tournament.get("time_control", {})
            tc_val = (
                tc
                if isinstance(tc, str)
                else f"{tc.get('minutes', 60)}+{tc.get('increment', 0)}"
            )
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci il tempo di riflessione (es. 15+10 o 90+30 o 60+0):"),
                _("Tempo di riflessione"),
                tc_val,
            )
            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                from stats import (
                    classify_tournament_category,
                    get_initial_elo_for_tournament,
                    parse_time_control,
                )

                tc_parsed = parse_time_control(val)
                if tc_parsed:
                    old_tc = self.current_tournament.get("time_control", {})
                    if tc_parsed != old_tc:
                        self.current_tournament["time_control"] = tc_parsed
                        cat = classify_tournament_category(
                            tc_parsed.get("minutes", 60), tc_parsed.get("increment", 0)
                        )
                        self.current_tournament["tournament_category"] = cat

                        # Ricalcola l'Elo di partenza per tutti i giocatori iscritti se il torneo non è iniziato
                        if not self.current_tournament.get("rounds"):
                            for p in self.current_tournament.get("players", []):
                                p["initial_elo"] = get_initial_elo_for_tournament(
                                    p, cat
                                )
                        cat_map = {
                            "standard": _("Standard"),
                            "rapid": _("Rapid"),
                            "blitz": _("Blitz"),
                        }
                        cat_disp = cat_map.get(cat.lower(), cat.capitalize())
                        tc_disp = _("{} min + {} sec ({})").format(
                            tc_parsed.get("minutes", 60),
                            tc_parsed.get("increment", 0),
                            cat_disp,
                        )
                        self.tree_ctrl.SetItemText(
                            item, _("Tempo riflessione: {}").format(tc_disp)
                        )
                        self._save_state()
                    play_sound("conferma")
                else:
                    play_sound("errore")
                    dlg_err = AccessibleMsgDialog(
                        self,
                        _("Errore"),
                        _("Formato non valido. Usa minuti+incremento o solo minuti."),
                        settings=self.settings,
                    )
                    dlg_err.ShowModal()
                    dlg_err.Destroy()
            dlg.Destroy()
        elif field_active == "chief_arbiter":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci il nome dell'Arbitro Capo:"),
                _("Arbitro Capo"),
                self.current_tournament["chief_arbiter"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                new_val = dlg.GetValue().strip()
                if new_val != self.current_tournament.get("chief_arbiter"):
                    self.current_tournament["chief_arbiter"] = new_val
                    self.tree_ctrl.SetItemText(
                        item, _("Arbitro Capo: {}").format(new_val)
                    )
                    self._save_state()
                play_sound("conferma")
            dlg.Destroy()
        elif field_active == "deputy_chief_arbiters":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci i collaboratori / vice arbitri (separati da virgola):"),
                _("Collaboratori / Vice Arbitri"),
                self.current_tournament.get("deputy_chief_arbiters", ""),
            )
            if dlg.ShowModal() == wx.ID_OK:
                new_val = dlg.GetValue().strip()
                if new_val != self.current_tournament.get("deputy_chief_arbiters"):
                    self.current_tournament["deputy_chief_arbiters"] = new_val
                    self.tree_ctrl.SetItemText(
                        item, _("Collaboratori: {}").format(new_val or _("Nessuno"))
                    )
                    self._save_state()
                play_sound("conferma")
            dlg.Destroy()
        elif field_active == "federation_code":
            dlg = wx.TextEntryDialog(
                self,
                _("Inserisci il codice della federazione ospitante (es. ITA, FRA):"),
                _("Codice Federazione"),
                self.current_tournament["federation_code"],
            )
            if dlg.ShowModal() == wx.ID_OK:
                new_val = dlg.GetValue().strip().upper()
                if new_val != self.current_tournament.get("federation_code"):
                    self.current_tournament["federation_code"] = new_val
                    self.tree_ctrl.SetItemText(
                        item, _("Codice Federazione: {}").format(new_val)
                    )
                    self._save_state()
                play_sound("conferma")
            dlg.Destroy()
        elif field_active == "color_board1":
            choices = [
                _("Bianco (scelto dall'arbitro)"),
                _("Nero (scelto dall'arbitro)"),
                _("Casuale (scelto da {app})").format(app="Tornello"),
            ]
            dlg = wx.SingleChoiceDialog(
                self,
                _(
                    "Seleziona il colore per il giocatore più forte (scacchiera 1, turno 1):"
                ),
                _("Colore al giocatore più forte"),
                choices,
            )
            curr_raw = self.current_tournament.get(
                "initial_board1_color_setting", "white1"
            )
            curr_idx = 0
            if curr_raw == "black1":
                curr_idx = 1
            elif curr_raw == "random":
                curr_idx = 2
            dlg.SetSelection(curr_idx)
            if dlg.ShowModal() == wx.ID_OK:
                sel = dlg.GetSelection()
                val_raw = "white1"
                if sel == 1:
                    val_raw = "black1"
                elif sel == 2:
                    val_raw = "random"
                if val_raw != self.current_tournament.get(
                    "initial_board1_color_setting"
                ):
                    self.current_tournament["initial_board1_color_setting"] = val_raw
                    col_disp = choices[sel]
                    self.tree_ctrl.SetItemText(
                        item, _("Colore al giocatore più forte: {}").format(col_disp)
                    )
                    self._save_state()
                play_sound("conferma")
            dlg.Destroy()
        elif field_active == "bye_value":
            choices = ["0.0", "0.5", "1.0"]
            dlg = wx.SingleChoiceDialog(
                self,
                _("Seleziona il valore del BYE secondo la regola FIDE:"),
                _("Valore del BYE"),
                choices,
            )
            curr_str = str(self.current_tournament.get("bye_value", 1.0))
            if curr_str in choices:
                dlg.SetSelection(choices.index(curr_str))
            if dlg.ShowModal() == wx.ID_OK:
                new_val = float(dlg.GetStringSelection())
                if new_val != float(self.current_tournament.get("bye_value", 0.5)):
                    self.current_tournament["bye_value"] = new_val
                    self.tree_ctrl.SetItemText(
                        item, _("Valore del BYE: {}").format(new_val)
                    )
                    self._save_state()
                play_sound("conferma")
            dlg.Destroy()

    def on_activate_match(self, match):
        if not self.current_tournament or not match:
            return

        # Find the actual match in the currently loaded tournament to avoid referencing stale objects
        match_id = match.get("id")
        round_num = match.get("round", 1)
        actual_match = None
        for r in self.current_tournament.get("rounds", []):
            if r.get("round") == round_num:
                for m in r.get("matches", []):
                    if m.get("id") == match_id:
                        actual_match = m
                        break
                break
        if not actual_match:
            actual_match = match

        w_id = actual_match.get("white_player_id")
        b_id = actual_match.get("black_player_id")
        if not b_id or b_id == "BYE_PLAYER_ID":
            wx.MessageBox(
                _("La partita con BYE non richiede inserimento risultati."),
                _("Info"),
                wx.ICON_INFORMATION,
            )
            return

        players_dict = self.current_tournament.get("players_dict", {})
        w_p = players_dict.get(w_id, {})
        b_p = players_dict.get(b_id, {})

        w_name = f"{w_p.get('last_name', '')} {w_p.get('first_name', '')}".strip()
        b_name = f"{b_p.get('last_name', '')} {b_p.get('first_name', '')}".strip()

        board_num = self.get_board_num(actual_match, actual_match.get("round", 1))

        pgn_text = actual_match.get("pgn", "")

        # Determinazione se il turno è concluso o il torneo è closed/concluded
        torneo = self.current_tournament
        is_tournament_concluded = self.current_tournament.get("concluded", False)
        is_round_concluded = False
        round_obj = next(
            (
                r
                for r in self.current_tournament.get("rounds", [])
                if r.get("round") == round_num
            ),
            None,
        )
        if round_obj:
            all_done = True
            for m in round_obj.get("matches", []):
                if (
                    m.get("result") is None
                    and m.get("black_player_id") is not None
                    and m.get("black_player_id") != "BYE_PLAYER_ID"
                ):
                    all_done = False
                    break
            if all_done:
                is_round_concluded = True

        disable_result_change = is_tournament_concluded or is_round_concluded

        from gui.dialogs.result_dialog import ResultDialog

        dlg = ResultDialog(
            self,
            white_name=w_name,
            black_name=b_name,
            white_id=w_id,
            black_id=b_id,
            board_num=board_num,
            current_result=actual_match.get("result"),
            schedule_info=actual_match.get("schedule_info"),
            settings=self.settings,
            pgn_text=pgn_text,
            disable_result_change=disable_result_change,
        )

        if dlg.ShowModal() == wx.ID_OK:
            from utils import format_date_locale

            if dlg.selected_action == "schedule":
                old_sched = actual_match.get("schedule_info", {})
                if (
                    not actual_match.get("is_scheduled")
                    or old_sched != dlg.schedule_info
                ):
                    actual_match["is_scheduled"] = True
                    actual_match["schedule_info"] = dlg.schedule_info
                    self._save_state()
                    self.set_status(
                        _("Partita pianificata per il {date} alle {time}.").format(
                            date=format_date_locale(dlg.schedule_info["date"]),
                            time=dlg.schedule_info["time"],
                        )
                    )
                else:
                    self.set_status(_("Nessuna modifica alla pianificazione."))
            elif dlg.selected_action == "withdraw":
                # Dalla 10.13.1 anche questa strada passa dal controllo sul
                # ritiro, con l'avviso quando i giocatori non bastano.
                if self._conferma_ritiro(dlg.withdrawn_player_id, self.active_filename):
                    self.withdraw_player(dlg.withdrawn_player_id)
                elif self._bivio_ha_cambiato_il_torneo(torneo, round_obj):
                    dlg.Destroy()
                    return
            else:
                res = dlg.get_selected_result()
                if res:
                    p_text = dlg.txt_pgn.GetValue().strip()
                    old_res = actual_match.get("result")
                    old_pgn = actual_match.get("pgn", "").strip()
                    if res != old_res or p_text != old_pgn:
                        if p_text:
                            import io

                            import chess.pgn

                            pgn_io = io.StringIO(p_text)
                            try:
                                game = chess.pgn.read_game(pgn_io)
                                if game:
                                    game.headers["Event"] = self.current_tournament.get(
                                        "name", "Torneo"
                                    )
                                    game.headers["Site"] = self.current_tournament.get(
                                        "site", "N/D"
                                    )

                                    # Date
                                    r_num = actual_match.get("round", 1)
                                    date_val = "????.??.??"
                                    round_dates_info = self.current_tournament.get(
                                        "round_dates", []
                                    )
                                    current_round_period_info = next(
                                        (
                                            rd
                                            for rd in round_dates_info
                                            if rd.get("round") == r_num
                                        ),
                                        None,
                                    )
                                    raw_date = None
                                    if (
                                        current_round_period_info
                                        and current_round_period_info.get("start_date")
                                    ):
                                        raw_date = current_round_period_info.get(
                                            "start_date"
                                        )
                                    elif self.current_tournament.get("start_date"):
                                        raw_date = self.current_tournament.get(
                                            "start_date"
                                        )
                                    if raw_date:
                                        date_val = raw_date.replace("-", ".")
                                    game.headers["Date"] = date_val
                                    game.headers["Round"] = str(r_num)

                                    # Players
                                    w_name_pgn = f"{w_p.get('last_name', '')}, {w_p.get('first_name', '')}".strip(
                                        ", "
                                    )
                                    b_name_pgn = f"{b_p.get('last_name', '')}, {b_p.get('first_name', '')}".strip(
                                        ", "
                                    )
                                    game.headers["White"] = w_name_pgn
                                    game.headers["Black"] = b_name_pgn

                                    # Result
                                    res_map = {
                                        "1-0": "1-0",
                                        "1-F": "1-0",
                                        "0-1": "0-1",
                                        "F-1": "0-1",
                                        "1/2-1/2": "1/2-1/2",
                                    }
                                    game.headers["Result"] = res_map.get(res, "*")

                                    # Elos
                                    game.headers["WhiteElo"] = str(
                                        int(w_p.get("initial_elo", 1399))
                                    )
                                    game.headers["BlackElo"] = str(
                                        int(b_p.get("initial_elo", 1399))
                                    )

                                    exporter = chess.pgn.StringExporter(
                                        headers=True, comments=True, variations=True
                                    )
                                    p_text = game.accept(exporter)
                            except Exception as e:
                                print(
                                    _("Errore durante l'elaborazione PGN: {}").format(e)
                                )

                        if p_text:
                            actual_match["pgn"] = p_text
                        else:
                            actual_match.pop("pgn", None)

                        self.apply_match_result(
                            actual_match, res, is_pgn_only=disable_result_change
                        )
                        # Dopo un forfait la domanda sul ritiro puo' arrivare
                        # al bivio, che riporta il torneo all'iscrizione o lo
                        # elimina: allora il risultato non va annunciato.
                        if self._bivio_ha_cambiato_il_torneo(torneo, round_obj):
                            dlg.Destroy()
                            return
                        if disable_result_change:
                            self.set_status(_("Partita aggiornata con PGN."))
                        else:
                            self.set_status(
                                _("Risultato registrato: {res}.").format(res=res)
                            )

                            # Ricalcola la posizione ottimale per il focus
                            if round_obj:
                                round_matches = round_obj.get("matches", [])
                                round_matches_sorted = sorted(
                                    round_matches, key=lambda x: x.get("id", 0)
                                )
                                remaining_unplayed = [
                                    m
                                    for m in round_matches_sorted
                                    if m.get("result") is None
                                    and m.get("black_player_id") is not None
                                ]

                                if remaining_unplayed:
                                    next_match = next(
                                        (
                                            m
                                            for m in remaining_unplayed
                                            if m.get("id", 0)
                                            > actual_match.get("id", 0)
                                        ),
                                        remaining_unplayed[0],
                                    )
                                    board_num_next = (
                                        round_matches_sorted.index(next_match) + 1
                                    )
                                    self._tree_restore_target = {
                                        "action": "activate_match",
                                        "filepath": self.active_filename,
                                        "match": next_match,
                                        "round": round_num,
                                        "board_num": board_num_next,
                                    }
                                else:
                                    # Turno completato
                                    tot_rounds = self.current_tournament.get(
                                        "total_rounds", 5
                                    )
                                    last_r_num = len(
                                        self.current_tournament.get("rounds", [])
                                    )
                                    if round_num == last_r_num:
                                        if round_num < tot_rounds:
                                            self._tree_restore_target = {
                                                "action": "generate_next_round_action",
                                                "filepath": self.active_filename,
                                            }
                                        else:
                                            self._tree_restore_target = {
                                                "action": "finalize_tournament_action",
                                                "filepath": self.active_filename,
                                            }
                                    else:
                                        self._tree_restore_target = {
                                            "action": "show_round_report",
                                            "filepath": self.active_filename,
                                            "round": round_num,
                                        }
                    else:
                        self.set_status(_("Nessuna modifica apportata alla partita."))

            # Rebuild tree and refresh display
            self.populate_tree()
            self.show_match_detail_verbose(actual_match, round_num, board_num)

        dlg.Destroy()

    def apply_match_result(self, match, result_str, is_pgn_only=False):
        if is_pgn_only:
            # Il suono della conferma lo da' la finestra del risultato, che
            # e' la sola a chiamare questo ramo con Salva PGN, quando si
            # chiude: suonarlo anche qui lo faceva sentire due volte.
            self._save_state()
            return

        result_map = {
            "1-0": (1.0, 0.0),
            "0-1": (0.0, 1.0),
            "1/2-1/2": (0.5, 0.5),
            "1-F": (1.0, 0.0),
            "F-1": (0.0, 1.0),
            "0-0F": (0.0, 0.0),
        }
        w_score, b_score = result_map.get(result_str, (0.0, 0.0))

        curr_round = match.get("round", self.current_tournament.get("current_round", 1))
        wp_id = match.get("white_player_id")
        bp_id = match.get("black_player_id")

        players_dict = self.current_tournament.get("players_dict", {})
        wp = players_dict.get(wp_id)
        bp = players_dict.get(bp_id)

        if wp:
            wp["results_history"] = [
                h for h in wp.get("results_history", []) if h.get("round") != curr_round
            ]
        if bp:
            bp["results_history"] = [
                h for h in bp.get("results_history", []) if h.get("round") != curr_round
            ]

        from tournament import (
            _apply_match_result_to_players,
            ricalcola_punti_tutti_giocatori,
        )

        _apply_match_result_to_players(
            self.current_tournament, match, result_str, w_score, b_score
        )
        ricalcola_punti_tutti_giocatori(self.current_tournament)

        # Salva lo stato dopo aver applicato il risultato
        self._save_state()

        # Gestione suoni e completamento del turno
        curr_round_num = self.current_tournament.get("current_round", 1)
        round_data = next(
            (
                r
                for r in self.current_tournament.get("rounds", [])
                if r.get("round") == curr_round_num
            ),
            None,
        )
        if round_data and all(
            m.get("result") is not None for m in round_data.get("matches", [])
        ):
            # Turno concluso: salva il report dettagliato del turno e riproduci il suono conclusivo del turno
            from reports import append_completed_round_to_history_file

            append_completed_round_to_history_file(
                self.current_tournament, curr_round_num
            )
            from utils import play_sound

            play_sound("conclusione_turno", self.current_tournament)
        else:
            # Riproduci il suono specifico del risultato
            from utils import play_sound

            play_sound(f"risultato_{result_str}", self.current_tournament)

        if "F" in result_str:
            forfeiting_name = (
                f"{bp['first_name']} {bp['last_name']}"
                if result_str == "1-F"
                else (
                    f"{wp['first_name']} {wp['last_name']}"
                    if result_str == "F-1"
                    else None
                )
            )
            forfeiting_id = (
                bp_id
                if result_str == "1-F"
                else (wp_id if result_str == "F-1" else None)
            )

            if forfeiting_name:
                msg = _(
                    "Il giocatore {name} si ritira definitivamente dal torneo?"
                ).format(name=forfeiting_name)
                dlg = AccessibleMsgDialog(
                    self, _("Ritiro dopo Forfait"), msg, style=wx.YES_NO
                )
                risposta = dlg.ShowModal()
                dlg.Destroy()
                # Dalla 10.13.1 anche il ritiro dopo un forfait passa dal
                # controllo sul ritiro, con l'avviso quando i giocatori non
                # bastano.
                if risposta == wx.ID_YES and self._conferma_ritiro(
                    forfeiting_id, self.active_filename
                ):
                    self.withdraw_player(forfeiting_id)

    def withdraw_player(self, player_id):
        players_dict = self.current_tournament.get("players_dict", {})
        player = players_dict.get(player_id)
        if player:
            player["withdrawn"] = True
            self._save_state()
            p_name = f"{player.get('last_name')} {player.get('first_name')}"
            self.set_status(
                _("Giocatore '{name}' ritirato con successo.").format(name=p_name)
            )
            from utils import play_sound

            play_sound("ritiro_giocatore", self.current_tournament)

    def show_player_detail(self, player):
        self.main_text.Clear()
        p_name = f"{player.get('last_name', '')} {player.get('first_name', '')}".strip()
        report = _("Scheda Giocatore: {name}\n").format(name=p_name)
        report += _("ID: {id} | Sesso: {sex} | Nazione: {fed}\n").format(
            id=player.get("id"),
            sex=player.get("gender", "M"),
            fed=player.get("federation", "ITA"),
        )
        report += _("ELO Iniziale: {init} | ELO Attuale: {curr}\n").format(
            init=int(player.get("initial_elo", 1399)),
            curr=int(player.get("current_elo", 1399)),
        )
        if player.get("withdrawn"):
            report += _("Stato: RITIRATO DAL TORNEO\n")

        report += _("Storico Partite nel Torneo:\n")
        history = player.get("results_history", [])
        for entry in history:
            opp_id = entry.get("opponent_id")
            opp_p = self.current_tournament.get("players_dict", {}).get(opp_id, {})
            opp_name = (
                f"{opp_p.get('last_name', '')} {opp_p.get('first_name', '')}".strip()
                if opp_id != "BYE_PLAYER_ID"
                else "BYE"
            )
            # Localizziamo anche BYE se necessario, ma opp_name "BYE" va bene, convertiamo l'opp_name a _("BYE")
            if opp_name == "BYE":
                opp_name = _("BYE")

            report += _(
                "  Turno {round}: vs {opp} ({color}) -> Risultato: {res} (Punti: {score})\n"
            ).format(
                round=entry.get("round"),
                opp=opp_name,
                color=entry.get("color", "N/D"),
                res=entry.get("result"),
                score=entry.get("score"),
            )

        self.append_log(report)
        self.set_status(_("Visualizzazione scheda di {name}.").format(name=p_name))

    def start_tournament_matchmaking(self):
        from tournament import abbinamento_esaurito, generate_pairings_for_round

        if not self._torneo_puo_partire(self.current_tournament):
            return

        matches = generate_pairings_for_round(self.current_tournament)
        if matches is None:
            if abbinamento_esaurito(self.current_tournament):
                self._proponi_abbinamento_manuale(1)
            else:
                self._avvisa_abbinamento_fallito(self.current_tournament)
            return

        self._registra_nuovo_turno(
            matches, 1, _("Torneo iniziato. Generati abbinamenti per il Turno 1.")
        )

    def _registra_nuovo_turno(self, matches, numero, stato, manuale=False):
        """Registra il turno appena abbinato, salva e mostra il turno nuovo.
        Fino alla 10.11.0 le stesse righe stavano due volte, all'avvio del
        torneo e in generate_next_round; dalla 10.12.0 servono anche al turno
        composto a mano (issue 38), e il lavoro sui dati lo fa registra_turno,
        senza wx: il turno del motore resta registrato come prima. stato e' la
        frase della barra di stato."""
        from tournament import registra_turno
        from utils import play_sound

        # Il giocatore senza avversario prende i punti previsti dal torneo:
        # prima li assegnava solo il percorso testuale. Al giocatore ritirato
        # non va scritta alcuna voce di storico per i turni che non gioca.
        # Prima gliene veniva messa una di BYE con zero punti: nel file TRF
        # diventava il codice U, cioe' bye assegnato, che per bbpPairings vale
        # il punteggio del bye e non zero. Il totale dichiarato non tornava
        # piu' con i risultati e il motore rifiutava il file con "The score
        # for player N does not match the game results", bloccando la
        # generazione del turno successivo. Ci pensa gia' engine.py, che per i
        # ritirati riempie con il codice Z i turni non giocati.
        registra_turno(self.current_tournament, matches, numero, manuale=manuale)
        self._save_state()

        play_sound("nuovo_turno", self.current_tournament)

        # Imposta il target per ripristinare il focus del cursore sul nuovo turno
        self._tree_restore_target = {
            "action": "show_round_report",
            "filepath": self.active_filename,
            "round": numero,
        }

        self.populate_tree()
        self.show_current_round_report()
        self.set_status(stato)

    def _proponi_abbinamento_manuale(self, numero):
        """bbpPairings ha risposto che nessun abbinamento del turno rispetta i
        criteri assoluti: con i giocatori rimasti le coppie ammesse sono
        esaurite. Il regolamento lascia la decisione all'arbitro capo
        (C.04.3, articolo 1.9.3), e dalla 10.12.0 Tornello propone di comporre
        il turno a mano (issue 38). Per gli altri errori resta l'avviso di
        _avvisa_abbinamento_fallito."""
        from utils import play_sound

        play_sound("errore", self.current_tournament)
        messaggio = _(
            "bbpPairings non ha trovato nessun abbinamento del turno {turno} che rispetti i criteri assoluti del sistema svizzero: con i giocatori rimasti, ogni combinazione ripeterebbe un incontro gia' giocato, darebbe un secondo bye a chi l'ha gia' avuto o farebbe incontrare due giocatori che devono avere lo stesso colore.\n\n"
            "In questo caso il regolamento FIDE (C.04.3, articolo 1.9.3) lascia la decisione all'arbitro capo. Puoi comporre a mano gli abbinamenti del turno {turno}: con non piu' di 16 giocatori attivi Tornello propone le coppie da cui partire, e segnala sempre gli incontri ripetuti, i bye e i colori fuori regola, che restano avvertimenti e non divieti. Prima di registrare il turno viene creata una copia di sicurezza, e nell'albero il turno si chiamera' Turno {turno}, abbinamenti manuali.\n\n"
            "Vuoi comporre a mano il turno {turno}? Se rispondi No il torneo resta com'e'."
        ).format(turno=numero)
        dlg = AccessibleMsgDialog(
            self,
            _("Nessun abbinamento valido"),
            messaggio,
            style=wx.YES_NO,
            settings=self.settings,
        )
        risposta = dlg.ShowModal()
        dlg.Destroy()
        if risposta != wx.ID_YES:
            self.set_status(
                _("Turno {turno} non abbinato: il torneo resta com'era.").format(
                    turno=numero
                )
            )
            return

        from gui.dialogs.manual_pairing_dialog import ManualPairingDialog

        dlg = ManualPairingDialog(self, self.current_tournament, numero, self.settings)
        esito = dlg.ShowModal()
        coppie = dlg.coppie_confermate
        dlg.Destroy()
        if esito != wx.ID_OK or not coppie:
            self.set_status(
                _(
                    "Composizione manuale annullata: il turno {turno} non e' stato registrato."
                ).format(turno=numero)
            )
            return
        self._registra_turno_manuale(coppie, numero)

    def _registra_turno_manuale(self, coppie, numero):
        """Registra le coppie confermate nella finestra di composizione. Prima
        fa la copia di sicurezza pre_turno_manuale; se non riesce, chiede se
        registrare lo stesso, con il No predefinito."""
        from turno_manuale import crea_partite_turno_manuale, valida_turno_manuale
        from utils import create_backup, play_sound

        errori, _avvertimenti = valida_turno_manuale(self.current_tournament, coppie)
        if errori:
            play_sound("errore", self.current_tournament)
            self._dialogo_informativo(_("Turno non registrato"), "\n".join(errori))
            return
        if not create_backup(self.active_filename, "pre_turno_manuale"):
            dlg = AccessibleMsgDialog(
                self,
                _("Copia di sicurezza non riuscita"),
                _(
                    "Non e' stato possibile creare la copia di sicurezza del torneo prima del turno composto a mano. Registrare lo stesso il turno {turno}? Il pulsante predefinito e' No."
                ).format(turno=numero),
                style=wx.YES_NO,
                settings=self.settings,
                no_predefinito=True,
            )
            risposta = dlg.ShowModal()
            dlg.Destroy()
            if risposta != wx.ID_YES:
                return
        partite = crea_partite_turno_manuale(self.current_tournament, coppie, numero)
        self._registra_nuovo_turno(
            partite,
            numero,
            _("Registrati gli abbinamenti composti a mano del Turno {num}.").format(
                num=numero
            ),
            manuale=True,
        )

    def _avvisa_abbinamento_fallito(self, torneo):
        """
        Spiega all'utente perche' gli abbinamenti non sono stati generati.

        Prima il fallimento arrivava come eccezione al gestore globale e
        l'utente vedeva il messaggio di errore imprevisto con il rimando a
        error.log, senza alcuna indicazione utile.
        """
        from tournament import motivo_ultimo_fallimento

        motivo = motivo_ultimo_fallimento(torneo)
        messaggio = _("Non e' stato possibile generare gli abbinamenti del turno.")
        if motivo:
            messaggio += _("\n\nMotivo: {reason}").format(reason=motivo)
        messaggio += _(
            "\n\nIl torneo non e' stato modificato. Se il problema dipende da un "
            "risultato inserito per errore nei turni precedenti, puoi correggerlo "
            "e riprovare, oppure tornare indietro con la Time Machine."
        )
        from utils import play_sound

        play_sound("errore", torneo)
        dlg = AccessibleMsgDialog(
            self, _("Abbinamenti non generati"), messaggio, settings=self.settings
        )
        dlg.ShowModal()
        dlg.Destroy()

    def generate_next_round(self):
        """Genera gli abbinamenti per il turno successivo se il turno corrente è concluso."""
        if not self.current_tournament:
            return

        rounds = self.current_tournament.get("rounds", [])
        curr_round = self.current_tournament.get("current_round", 1)
        tot_rounds = self.current_tournament.get("total_rounds", 5)

        if curr_round >= tot_rounds:
            wx.MessageBox(
                _("Il torneo ha già raggiunto il numero massimo di turni previsto."),
                _("Errore"),
                wx.ICON_ERROR,
            )
            return

        r_curr = next((r for r in rounds if r.get("round") == curr_round), None)
        if r_curr:
            for m in r_curr.get("matches", []):
                if m.get("result") is None and m.get("black_player_id") is not None:
                    wx.MessageBox(
                        _(
                            "Impossibile generare il turno successivo: ci sono ancora partite senza risultato nel turno corrente."
                        ),
                        _("Errore"),
                        wx.ICON_ERROR,
                    )
                    return

        next_round_num = curr_round + 1

        from tournament import abbinamento_esaurito, generate_pairings_for_round

        self.current_tournament["current_round"] = next_round_num

        next_matches = generate_pairings_for_round(self.current_tournament)
        if next_matches is None:
            self.current_tournament["current_round"] = curr_round
            # Dalla 10.12.0 l'esaurimento delle coppie ha la sua strada, la
            # composizione manuale; gli altri errori restano un avviso.
            if abbinamento_esaurito(self.current_tournament):
                self._proponi_abbinamento_manuale(next_round_num)
            else:
                self._avvisa_abbinamento_fallito(self.current_tournament)
            return

        self._registra_nuovo_turno(
            next_matches,
            next_round_num,
            _("Generati abbinamenti per il Turno {num}.").format(num=next_round_num),
        )

    def on_export_ics(self, event):
        if not self.current_tournament:
            return

        # Controlla se ci sono partite pianificate
        has_scheduled = False
        for r in self.current_tournament.get("rounds", []):
            for m in r.get("matches", []):
                if m.get("is_scheduled") and m.get("schedule_info"):
                    sched = m["schedule_info"]
                    if sched.get("date") and sched.get("time"):
                        has_scheduled = True
                        break
            if has_scheduled:
                break

        if not has_scheduled:
            wx.MessageBox(
                _("Non ci sono partite pianificate in questo torneo."),
                _("Esporta Calendario"),
                wx.OK | wx.ICON_INFORMATION,
            )
            return

        default_filename = f"Tornello - {self.current_tournament.get('name', 'Torneo')} - Calendario.ics"
        dlg = wx.FileDialog(
            self,
            _("Salva file iCalendar (.ics)"),
            wildcard="iCalendar files (*.ics)|*.ics",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            defaultFile=default_filename,
        )

        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            from reports import generate_ics_content

            try:
                ics_content, partite_saltate = generate_ics_content(
                    self.current_tournament
                )
                # Le righe finiscono gia' con CR LF, come vuole RFC 5545:
                # newline="" le scrive come sono. Fino alla 10.13.26 il file
                # si apriva con newline="\r\n", che aggiungeva un secondo CR a
                # ogni riga.
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(ics_content)
                # Con una partita sola la frase va al singolare: fino alla
                # 10.13.27 diceva 1 partite pianificate non ci sono entrate.
                if len(partite_saltate) == 1:
                    self.set_status(
                        _("Calendario esportato in '{path}', ma una partita pianificata non c'e' entrata: la sua data non e' leggibile.").format(
                            path=os.path.basename(path)
                        )
                    )
                elif partite_saltate:
                    self.set_status(
                        _("Calendario esportato in '{path}', ma {n} partite pianificate non ci sono entrate: la loro data non e' leggibile.").format(
                            path=os.path.basename(path), n=len(partite_saltate)
                        )
                    )
                else:
                    self.set_status(
                        _("Calendario esportato con successo in '{path}'.").format(
                            path=os.path.basename(path)
                        )
                    )
                from utils import play_sound

                play_sound("conferma")
            except Exception as e:
                wx.MessageBox(
                    _("Errore durante l'esportazione: {e}").format(e=e),
                    _("Errore"),
                    wx.ICON_ERROR,
                )
        dlg.Destroy()

    def find_active_tree_item_by_action(self, action):
        action_map = {
            "show_data": getattr(self, "node_dati", None),
            "show_players": getattr(self, "node_partecipanti", None),
            "show_matches": getattr(self, "node_partite", None),
            "show_matches_unscheduled": getattr(self, "node_non_pianificate", None),
            "show_matches_scheduled": getattr(self, "node_pianificate", None),
            "show_matches_concluded": getattr(self, "node_concluse", None),
        }
        return action_map.get(action)
