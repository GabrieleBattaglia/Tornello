import os
import glob
import json
import wx
import builtins
from version import __version__, __date__
from gui.settings import apply_visual_settings, save_settings
from gui.dialogs import AccessibleMsgDialog, VisualSettingsDialog

_ = getattr(builtins, "_", lambda s: s)


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
        title_str = _(
            "Tornello - Versione {} - Data Rilascio {} - [Nessun Torneo Caricato]"
        ).format(__version__, __date__)
        super().__init__(parent, title=title_str, size=(1024, 768))

        self.settings = settings
        self.current_tournament = None
        self.active_filename = None
        self.creation_data = {}  # Contiene i dati transitori del nuovo torneo in fase di inserimento nell'albero
        self.creation_mode = (
            False  # True se stiamo compilando l'albero per il Nuovo Torneo
        )
        self.last_status_msg = _("Pronto.")

        self._init_ui()
        self._setup_shortcuts()
        self._check_fide_db_on_startup()
        self._check_backup_on_startup()
        self._scan_and_load_initial_tournament()
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
        self.splitter.SplitVertically(self.left_pane, self.right_pane, 700)
        self.splitter.SetMinimumPaneSize(150)

        main_layout.Add(self.splitter, 1, wx.EXPAND | wx.ALL, 5)

        # Barra di Stato personalizzata in basso (con etichetta adiacente precedente)
        self.lbl_status = wx.StaticText(self.top_panel, label=_("Barra di stato"))
        self.status_text = wx.TextCtrl(
            self.top_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
            size=(-1, 60),
        )
        self.status_text.SetName(_("Barra di stato"))
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

        file_menu = wx.Menu()
        file_menu.Append(wx.ID_NEW, _("&Nuovo Torneo...\tCtrl+N"))
        file_menu.Append(wx.ID_OPEN, _("&Apri Torneo...\tCtrl+O"))
        self.item_export_ics = file_menu.Append(
            wx.ID_ANY, _("&Esporta partite pianificate...\tCtrl+Shift+E")
        )
        self.item_delete_tournament = file_menu.Append(
            wx.ID_ANY, _("&Elimina Torneo Attivo...\tDelete")
        )
        self.item_backup_cleanup = file_menu.Append(wx.ID_ANY, _("&Pulisci backup..."))
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

        # Visualizza
        view_menu = wx.Menu()
        self.item_view_central = view_menu.Append(wx.ID_ANY, _("&Area Centrale\tF5"))
        self.item_view_tree = view_menu.Append(wx.ID_ANY, _("Al&bero di Destra\tF6"))
        self.item_view_status = view_menu.Append(wx.ID_ANY, _("&Barra di Stato\tF7"))
        self.menu_bar.Append(view_menu, _("&Visualizza"))

        # Strumenti
        tools_menu = wx.Menu()
        self.item_fide_query = tools_menu.Append(wx.ID_ANY, _("&Consulta FIDE\tCtrl+K"))
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

    def _setup_shortcuts(self):
        # Mappa i tasti funzione globali F1-F7
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_hook)

    def on_key_hook(self, event):
        key_code = event.GetKeyCode()
        if key_code == wx.WXK_F1:
            self.on_help(None)
        elif key_code == wx.WXK_F2:
            self.on_changelog(None)
        elif key_code == wx.WXK_F3:
            self.on_credits(None)
        elif key_code == wx.WXK_F5:
            self.main_text.SetFocus()
        elif key_code == wx.WXK_F6:
            self.tree_ctrl.SetFocus()
        elif key_code == wx.WXK_F7:
            self.status_text.SetFocus()
        else:
            event.Skip()

    def apply_theme(self):
        """Applica la combinazione di colori ed il font impostati in settings a tutti i controlli."""
        apply_visual_settings(self.main_text, self.settings)
        apply_visual_settings(self.tree_ctrl, self.settings)
        apply_visual_settings(self.status_text, self.settings)

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

    def set_status(self, text):
        """Aggiorna il contenuto della barra di stato personalizzata in basso."""
        self.update_status_display(text)

    def update_status_display(self, action_msg=None):
        """Calcola e visualizza le metriche avanzate di progresso e statistiche di gioco."""
        if action_msg is not None:
            self.last_status_msg = action_msg
        else:
            if not hasattr(self, "last_status_msg"):
                self.last_status_msg = _("Pronto.")

        lines = [self.last_status_msg]

        if self.current_tournament:
            # 1. Progress. Giorno x/y (zz.z%), turno x/y, risult.x/y (zz.z%), PGN x.
            t_start_str = self.current_tournament.get("start_date")
            t_end_str = self.current_tournament.get("end_date")

            y_days = 1
            x_day = 1
            day_pct = 100.0

            is_concluded = self.current_tournament.get("concluded", False)

            try:
                from datetime import datetime
                from config import DATE_FORMAT_ISO

                dt_start = datetime.strptime(t_start_str, DATE_FORMAT_ISO)
                dt_end = datetime.strptime(t_end_str, DATE_FORMAT_ISO)
                y_days = (dt_end - dt_start).days + 1
                if y_days <= 0:
                    y_days = 1

                if is_concluded:
                    x_day = y_days
                else:
                    curr_round = self.current_tournament.get("current_round", 1)
                    round_dates = self.current_tournament.get("round_dates", [])
                    curr_rd_data = next(
                        (rd for rd in round_dates if rd.get("round") == curr_round),
                        None,
                    )
                    curr_date_str = (
                        curr_rd_data.get("start_date") if curr_rd_data else None
                    )

                    if curr_date_str:
                        dt_curr = datetime.strptime(curr_date_str, DATE_FORMAT_ISO)
                        x_day = (dt_curr - dt_start).days + 1
                    else:
                        x_day = 1

                    if x_day < 1:
                        x_day = 1
                    if x_day > y_days:
                        x_day = y_days

                day_pct = (x_day / y_days) * 100.0
            except Exception:
                round_dates = self.current_tournament.get("round_dates", [])
                dates = sorted(
                    list(
                        set(
                            rd.get("start_date")
                            for rd in round_dates
                            if rd.get("start_date")
                        )
                    )
                )
                y_days = len(dates) if len(dates) > 0 else 1
                curr_round = self.current_tournament.get("current_round", 1)
                x_day = min(curr_round, y_days)
                day_pct = (x_day / y_days) * 100.0 if y_days > 0 else 100.0

            curr_round = self.current_tournament.get("current_round", 1)
            tot_rounds = self.current_tournament.get("total_rounds", 5)

            total_matches = 0
            played_matches = 0
            pgn_count = 0
            white_wins = 0
            draws = 0
            black_wins = 0

            for r in self.current_tournament.get("rounds", []):
                for m in r.get("matches", []):
                    total_matches += 1
                    if m.get("result") is not None:
                        played_matches += 1

                    if m.get("pgn"):
                        pgn_count += 1

                    b_id = m.get("black_player_id")
                    if b_id and b_id != "BYE_PLAYER_ID":
                        res = m.get("result")
                        if res in ["1-0", "1-F"]:
                            white_wins += 1
                        elif res == "1/2-1/2":
                            draws += 1
                        elif res in ["0-1", "F-1"]:
                            black_wins += 1

            res_pct = (
                (played_matches / total_matches * 100.0) if total_matches > 0 else 0.0
            )

            prog_line = _(
                "Progress. Giorno {}/{} ({:.1f}%), turno {}/{}, risult.{}/{} ({:.1f}%), PGN {}."
            ).format(
                x_day,
                y_days,
                day_pct,
                curr_round,
                tot_rounds,
                played_matches,
                total_matches,
                res_pct,
                pgn_count,
            )
            lines.append(prog_line)

            # 2. Vittorie: Bianco x, patte y, nero z.
            vit_line = _("Vittorie: Bianco {}, patte {}, nero {}.").format(
                white_wins, draws, black_wins
            )
            lines.append(vit_line)

        self.status_text.SetValue("\n".join(lines))

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

        intro = _(
            "Ciao! Benvenuto, sono Tornello v{} - Sviluppato da Gabriele Battaglia (IZ4APU) & Stella (AI)\n"
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
        ).format(__version__, age_str, __date__)
        self.append_log(intro)
        self.set_status(_("Pronto. Nessun torneo caricato."))

    def _check_fide_db_on_startup(self):
        """Verifica se il DB FIDE locale ha più di 30 giorni e propone l'aggiornamento."""
        from config import FIDE_DB_LOCAL_FILE, FIDE_DB_JSON_LEGACY
        from fide_db import fide_db_exists, cleanup_legacy_json

        # Fallback: se esiste il vecchio JSON ma non il nuovo SQLite, elimina il JSON
        if not fide_db_exists() and os.path.exists(FIDE_DB_JSON_LEGACY):
            cleanup_legacy_json()

        if os.path.exists(FIDE_DB_LOCAL_FILE):
            try:
                from datetime import datetime

                file_mod_timestamp = os.path.getmtime(FIDE_DB_LOCAL_FILE)
                file_age_days = (
                    datetime.now() - datetime.fromtimestamp(file_mod_timestamp)
                ).days
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
                        update_dlg.Destroy()
                    else:
                        dlg.Destroy()
            except Exception:
                pass
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
                update_dlg.Destroy()
            else:
                dlg.Destroy()

    def _check_backup_on_startup(self):
        """Scansiona la cartella backup/ alla ricerca di file più vecchi di 18 mesi."""
        backup_dir = "backup"
        if not os.path.exists(backup_dir):
            return

        from datetime import datetime

        try:
            from dateutil.relativedelta import relativedelta

            has_dateutil = True
        except ImportError:
            has_dateutil = False

        today = datetime.now()
        if has_dateutil:
            limit_date = today - relativedelta(months=18)
        else:
            limit_date = today - datetime.timedelta(days=548)  # ~18 mesi

        old_files = []
        try:
            for item in os.listdir(backup_dir):
                filepath = os.path.join(backup_dir, item)
                if os.path.isfile(filepath):
                    mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                    if mtime < limit_date:
                        old_files.append((filepath, mtime))
        except Exception:
            return

        if not old_files:
            return

        old_count = len(old_files)
        msg = _(
            "Sono stati individuati {count} file di backup più vecchi di 18 mesi.\n"
            "Si consiglia di effettuare una pulizia per liberare spazio su disco.\n\n"
            "Vuoi aprire la finestra di pulizia dei backup adesso?\n\n"
            "Nota: Scegliendo 'No', la data di modifica di questi file verrà aggiornata a oggi "
            "e non ti verrà riproposto questo controllo per altri 18 mesi."
        ).format(count=old_count)

        dlg = AccessibleMsgDialog(
            self, _("Pulizia Backup Consigliata"), msg, style=wx.YES_NO
        )
        res = dlg.ShowModal()
        dlg.Destroy()

        if res == wx.ID_YES:
            # Mostra la finestra di pulizia
            self.on_backup_cleanup(None)
        else:
            # Aggiorna mtime a oggi per non riproporlo
            for filepath, _discard in old_files:
                try:
                    os.utime(filepath, None)  # imposta mtime e atime a oggi/ora
                except Exception:
                    pass

    def _scan_and_load_initial_tournament(self):
        """Scansiona i file torneo in corso ed effettua il caricamento automatico se ce n'è solo uno."""
        from config import PLAYER_DB_FILE

        tournament_files = [
            f
            for f in glob.glob("Tornello - *.json")
            if "- concluso_" not in os.path.basename(f).lower()
            and os.path.basename(f) != os.path.basename(PLAYER_DB_FILE)
            and os.path.basename(f) != "Tornello - Settings.json"
        ]

        # Se c'è esattamente un solo torneo attivo, lo carichiamo all'avvio
        if len(tournament_files) == 1:
            filepath = tournament_files[0]
            self.load_tournament(filepath)
        else:
            self.populate_tree()

    def load_tournament(self, filepath, rebuild_tree=True):
        """Carica un torneo dal file JSON."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.current_tournament = data
            self.active_filename = filepath

            # Ricostruisce players_dict per l'interfaccia grafica
            self.current_tournament["players_dict"] = {
                p["id"]: p for p in self.current_tournament.get("players", [])
            }

            # Aggiorna titolo finestra
            # Aggiorna titolo finestra
            t_name = data.get("name", _("Torneo Sconosciuto"))
            title_str = _(
                "Tornello - Versione {version} - Data Rilascio {date} - [{name}]"
            ).format(version=__version__, date=__date__, name=t_name)
            self.SetTitle(title_str)

            # Carica il report del turno corrente nell'area centrale
            self.show_current_round_report()

            if rebuild_tree:
                self.populate_tree()
            self.set_status(
                _("Torneo '{name}' caricato con successo.").format(name=t_name)
            )
        except Exception as e:
            wx.MessageBox(
                _("Errore nel caricamento del torneo: {}").format(e),
                _("Errore"),
                wx.ICON_ERROR,
            )
            self.current_tournament = None
            self.active_filename = None
            if rebuild_tree:
                self.populate_tree()

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
        report += "-" * 40 + "\n"

        # Mostra abbinamenti se presenti
        rounds = self.current_tournament.get("rounds", [])
        active_round_data = next(
            (r for r in rounds if r.get("round") == curr_round), None
        )
        if active_round_data:
            report += _("Abbinamenti Turno {}:\n").format(curr_round)
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
                    report += _("  {} - BYE (1.0 punti)\n").format(w_name)
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
                for k in ["action", "filepath", "field_active", "round", "board_num"]:
                    if saved_data.get(k) != child_data.get(k):
                        match = False
                        break
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

    def populate_tree(self):
        """Costruisce e popola l'albero TreeCtrl destro con la struttura unificata di tutti i tornei."""
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

        self.tree_ctrl.DeleteAllItems()
        self.tree_root = self.tree_ctrl.AddRoot("Root")

        # Scansiona file
        from config import PLAYER_DB_FILE

        active_files = [
            f
            for f in glob.glob("Tornello - *.json")
            if "- concluso_" not in os.path.basename(f).lower()
            and os.path.basename(f) != os.path.basename(PLAYER_DB_FILE)
            and os.path.basename(f) != "Tornello - Settings.json"
        ]

        in_prep_files = []
        started_files = []
        for f in active_files:
            try:
                with open(f, "r", encoding="utf-8") as f_in:
                    data = json.load(f_in)
                if data.get("concluded"):
                    continue
                if len(data.get("rounds", [])) == 0:
                    in_prep_files.append((f, data))
                else:
                    started_files.append((f, data))
            except Exception:
                pass

        closed_files = glob.glob(
            os.path.join("Closed Tournaments", "**", "Tornello - *.json"),
            recursive=True,
        )
        concluded_files = []
        for f in closed_files:
            try:
                with open(f, "r", encoding="utf-8") as f_in:
                    data = json.load(f_in)
                concluded_files.append((f, data))
            except Exception:
                pass

        # 1. TORNEI IN CORSO (Attivi)
        for f, data in started_files:
            t_node = self.add_tournament_node(self.tree_root, f, data)
            if not expanded_actions:
                if self.active_filename and os.path.abspath(f) == os.path.abspath(
                    self.active_filename
                ):
                    self.tree_ctrl.Expand(t_node)
                    child, cookie = self.tree_ctrl.GetFirstChild(t_node)
                    while child.IsOk():
                        lbl = self.tree_ctrl.GetItemText(child)
                        if lbl.startswith(_("iscritti")) or lbl.startswith(_("turni")):
                            self.tree_ctrl.Expand(child)
                        child, cookie = self.tree_ctrl.GetNextChild(t_node, cookie)

        # 2. TORNEI IN PREPARAZIONE
        if in_prep_files:
            prep_parent = self.tree_ctrl.AppendItem(
                self.tree_root, f"{_('In Preparazione')} ({len(in_prep_files)})"
            )
            self.tree_ctrl.SetItemData(prep_parent, {"action": "category_prep"})
            for f, data in in_prep_files:
                t_node = self.add_tournament_node(prep_parent, f, data)
                if not expanded_actions:
                    if self.active_filename and os.path.abspath(f) == os.path.abspath(
                        self.active_filename
                    ):
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
                month_year = ""
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
                        month_year = f" ({month_name} {dt.year})"
                    except Exception:
                        pass
                label_suffix = month_year
                t_node = self.add_tournament_node(
                    closed_parent, f, data, label_suffix=label_suffix
                )
                if not expanded_actions:
                    if self.active_filename and os.path.abspath(f) == os.path.abspath(
                        self.active_filename
                    ):
                        self.tree_ctrl.Expand(t_node)
                        self.tree_ctrl.Expand(closed_parent)

        # 4. NUOVO TORNEO
        new_item = self.tree_ctrl.AppendItem(self.tree_root, _("Nuovo torneo"))
        self.tree_ctrl.SetItemData(new_item, {"action": "start_new_tournament"})

        if expanded_actions:
            self._restore_tree_expansion_state(self.tree_root, expanded_actions)

        if saved_data:
            target_item = self._find_matching_item(self.tree_root, saved_data)
            if target_item and target_item.IsOk():
                self.tree_ctrl.SelectItem(target_item)
                self.tree_ctrl.EnsureVisible(target_item)
                self.tree_ctrl.SetFocus()

        self.update_menu_states()
        self.update_status_display()

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
                    from utils import format_date_locale

                    f_date = format_date_locale(sched.get("date"))
                    match_label = _(
                        "Scacchiera {}: {} vs {} (Pianificata: {} {})"
                    ).format(board_num, w_name, b_name, f_date, sched.get("time"))
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
            "random": _("Casuale (scelto da Tornello)"),
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
                p_label += _(" [RIT]")
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
                node_act = self.tree_ctrl.AppendItem(turni_node, _("genera turno"))
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
            t_node, f"{_('partite')} ({total_pgn_matches})"
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
        if filepath:
            if not self.current_tournament or self.active_filename != filepath:
                self.load_tournament(filepath, rebuild_tree=False)

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
        info.append("=" * 50)
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
            "random": _("Casuale (scelto da Tornello)"),
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
        lines.append("=" * 50)
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

        lines.append("\n" + "=" * 50)
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
        info.append("=" * 50)

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
        info.append("=" * 50)
        info.append(_("Cognome: {last_name}").format(last_name=p.get("last_name", "")))
        info.append(_("Nome: {first_name}").format(first_name=p.get("first_name", "")))
        info.append(_("Elo Iniziale: {elo}").format(elo=int(p.get("initial_elo", 1399))))
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
            info.append("-" * 30)
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
        info.append("=" * 50)

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
        info.append("=" * 50)

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
        info.append("=" * 50)
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

        if filepath and (
            not self.current_tournament or self.active_filename != filepath
        ):
            self.load_tournament(filepath, rebuild_tree=False)

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
                    _("Nome torneo: {}").format(
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
                _("Casuale (scelto da Tornello)"),
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
                    self.tree_root, _("Avanti (Iscrizione Giocatori)")
                )
                self.tree_ctrl.SetItemData(next_item, {"action": "wizard_next"})
                if not (self.tree_ctrl.GetWindowStyleFlag() & wx.TR_HIDE_ROOT):
                    self.tree_ctrl.Expand(self.tree_root)

    def on_wizard_next(self):
        from db_players import load_players_db
        from utils import play_sound

        players_db = load_players_db()

        play_sound("conferma")

        # Apri il dialogo di iscrizione giocatori
        from gui.dialogs import PlayerEnrollmentDialog

        dlg = PlayerEnrollmentDialog(self, players_db, [], self.settings)
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
        from models import Tournament, Player, RoundDate
        from tournament import generate_pairings_for_round
        from utils import sanitize_filename

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
        self.active_filename = f"Tornello - {sanitized}.json"

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
        from stats import parse_time_control, classify_tournament_category

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

        msg = _(
            "Vuoi avviare il torneo generando subito gli abbinamenti per il Turno 1?\n\n"
            "Sì = Avvia il torneo generando il Turno 1\n"
            "No = Salva il torneo 'In preparazione' (potrai aggiungere altri giocatori ed avviarlo in seguito)"
        )
        dlg_start = AccessibleMsgDialog(self, _("Avvio Torneo"), msg, style=wx.YES_NO)
        start_now = dlg_start.ShowModal() == wx.ID_YES
        dlg_start.Destroy()

        if start_now:
            matches = generate_pairings_for_round(tournament.to_dict())
            if matches is None:
                wx.MessageBox(
                    _("Errore nella generazione degli abbinamenti con bbpPairings."),
                    _("Errore"),
                    wx.ICON_ERROR,
                )
                return
            from models import Round, Match

            round_obj = Round(round=1, matches=[Match.from_dict(m) for m in matches])
            tournament.rounds.append(round_obj)
            self.current_tournament = tournament.to_dict()
            self.current_tournament["players_dict"] = {
                p["id"]: p for p in self.current_tournament.get("players", [])
            }
            self._save_state()
            self.creation_mode = False
            self.load_tournament(self.active_filename)
            self.set_status(_("Torneo avviato. Generati abbinamenti per il Turno 1."))
        else:
            self.current_tournament = tournament.to_dict()
            self.current_tournament["players_dict"] = {
                p["id"]: p for p in self.current_tournament.get("players", [])
            }
            self._save_state()
            self.creation_mode = False
            self.load_tournament(self.active_filename)
            self.set_status(
                _(
                    "Torneo creato in preparazione. Puoi completare l'inserimento in seguito."
                )
            )

    def _save_state(self):
        if self.current_tournament:
            from tournament import save_tournament
            from reports import save_current_tournament_round_file, save_standings_text

            save_tournament(self.current_tournament, filepath=self.active_filename)
            save_current_tournament_round_file(self.current_tournament)
            save_standings_text(self.current_tournament, final=False)

            # Accumula ed esporta il file PGN del torneo
            if self.active_filename:
                import os
                from utils import sanitize_filename

                t_name = self.current_tournament.get("name", "Torneo_Senza_Nome")
                sanitized_name = sanitize_filename(t_name)
                pgn_filename = os.path.join(
                    os.path.dirname(self.active_filename),
                    f"{sanitized_name} - raccolta partite.pgn",
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
            elif action in ["select_tournament", "load_concluded"] and filepath:
                self.delete_tournament_completely(item, filepath)
                return

        event.Skip()

    def delete_player_from_tournament(self, item, player_data):
        if not self.current_tournament:
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

        p_name = f"{player_data.get('last_name', '')} {player_data.get('first_name', '')}".strip()
        msg = _("Sei sicuro di voler rimuovere il giocatore {name} dal torneo?").format(
            name=p_name
        )
        dlg = AccessibleMsgDialog(
            self, _("Conferma Rimozione Giocatore"), msg, style=wx.YES_NO
        )
        if dlg.ShowModal() == wx.ID_YES:
            try:
                players = self.current_tournament.get("players", [])
                to_remove = next(
                    (p for p in players if p.get("id") == player_data.get("id")), None
                )
                if to_remove:
                    players.remove(to_remove)
                    self.current_tournament["players_dict"] = {
                        p["id"]: p for p in players
                    }
                    self._save_state()
                    self.populate_tree()
                    from utils import play_sound

                    play_sound("rimozione_giocatore")
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
        dlg.Destroy()

    def load_concluded_tournament_report(self, filepath):
        """Visualizza i report e la classifica di un torneo concluso nell'area centrale."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            t_name = data.get("name", _("Torneo Concluso"))

            self.main_text.Clear()
            report = _("Torneo Concluso: {}\n").format(t_name)
            report += _("Data Inizio: {start} | Fine: {end}\n").format(
                start=data.get("start_date", _("N/D")),
                end=data.get("end_date", _("N/D")),
            )
            report += "-" * 50 + "\n\n"

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

    def delete_tournament_completely(self, item, filepath):
        """Rimuove fisicamente dal disco un torneo (attivo, concluso o in preparazione) e tutti i file correlati."""
        import json
        import os
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
            with open(filepath, "r", encoding="utf-8") as f_in:
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

        msg = _(
            "Sei sicuro di voler eliminare definitivamente il torneo {t_type} '{t_name}'?\nQuesta azione rimuoverà il file JSON centrale e TUTTI i report generati per questo torneo, sia nella cartella principale che nella cartella di salvataggio custom."
        ).format(t_type=t_type, t_name=t_name)
        dlg = AccessibleMsgDialog(
            self, _("Conferma Eliminazione Torneo"), msg, style=wx.YES_NO
        )
        if dlg.ShowModal() == wx.ID_YES:
            try:
                # 1. Rimuove il file JSON centrale
                if os.path.exists(filepath):
                    os.remove(filepath)

                # 2. Ottiene i percorsi di salvataggio per ripulire i file correlati
                paths_to_clean = [os.path.dirname(filepath)]
                custom_path = data.get("custom_save_path") or data.get("save_path")
                if custom_path:
                    from utils import resolve_and_verify_save_path

                    resolved_path, _discard = resolve_and_verify_save_path(custom_path)
                    if resolved_path and os.path.exists(resolved_path):
                        paths_to_clean.append(resolved_path)

                paths_to_clean = list(
                    set([os.path.abspath(p) for p in paths_to_clean if p])
                )

                # 3. Nome sanificato per trovare i file correlati
                from tournament import sanitize_filename

                sanitized_name = sanitize_filename(t_name)
                prefix_to_match = f"Tornello - {sanitized_name}"

                deleted_count = 0
                for folder in paths_to_clean:
                    if os.path.exists(folder):
                        for f_name in os.listdir(folder):
                            if f_name.startswith(prefix_to_match):
                                f_path = os.path.join(folder, f_name)
                                if os.path.isfile(f_path):
                                    try:
                                        os.remove(f_path)
                                        deleted_count += 1
                                    except Exception:
                                        pass

                # 4. Rimuove il nodo dall'albero
                self.tree_ctrl.Delete(item)

                # Se è stato cancellato il torneo attivo corrente, ripristina lo stato a vuoto
                if self.active_filename and os.path.abspath(
                    filepath
                ) == os.path.abspath(self.active_filename):
                    self.current_tournament = None
                    self.active_filename = None
                    self.show_intro_message()

                play_sound("cancellato", self.current_tournament)
                self.set_status(
                    _(
                        "Torneo '{t_name}' e i suoi {deleted_count} file correlati sono stati eliminati."
                    ).format(t_name=t_name, deleted_count=deleted_count)
                )
            except Exception as e:
                wx.MessageBox(
                    _("Errore durante l'eliminazione del torneo: {}").format(e),
                    _("Errore"),
                    wx.ICON_ERROR,
                )
        dlg.Destroy()

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
        if not data or data.get("action") not in [
            "select_tournament",
            "load_concluded",
        ]:
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
            "save_path": os.path.abspath("."),
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
            "random": _("Casuale (scelto da Tornello)"),
        }
        col_val = col_disp_map.get(col_raw, _("Bianco (scelto dall'arbitro)"))

        bye_val = str(self.creation_data["bye_value"])

        self.tree_name = self.tree_ctrl.AppendItem(
            self.tree_root, _("Nome torneo: {}").format(name_val)
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

        # Verifica se i campi obbligatori sono validati per mostrare "Avanti"
        if self.creation_data["name"] and self.creation_data["time_control"]:
            next_item = self.tree_ctrl.AppendItem(self.tree_root, _("Avanti"))
            self.tree_ctrl.SetItemData(next_item, {"action": "wizard_next"})

        if not (self.tree_ctrl.GetWindowStyleFlag() & wx.TR_HIDE_ROOT):
            self.tree_ctrl.Expand(self.tree_root)

        # Ripristina la selezione ed il focus sul campo modificato dopo 300 ms per lo screen reader
        if hasattr(self, "last_activated_field") and self.last_activated_field:
            target_item = self.find_tree_item_by_field(self.last_activated_field)
            if target_item:
                wx.CallLater(300, self._restore_tree_focus, target_item)

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
        dlg = VisualSettingsDialog(self, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            new_settings = dlg.get_settings()
            new_lang = new_settings.get("language", "it")
            self.settings = new_settings
            save_settings(self.settings)
            self.apply_theme()
            self.set_status("Impostazioni salvate ed applicate.")

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
        dlg.Destroy()

    def on_help(self, event):
        # Visualizza la guida accessibile caricandola da file
        self.main_text.Clear()
        guide_text = ""
        from config import resource_path

        guide_path = resource_path("MANUALE.txt")
        if os.path.exists(guide_path):
            try:
                with open(guide_path, "r", encoding="utf-8") as f:
                    guide_text = f.read()
            except Exception:
                pass

        if not guide_text:
            guide_text = _(
                "MANUALE GUIDA DI TORNELLO v9.3.0\n"
                "================================\n\n"
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
                with open(changelog_path, "r", encoding="utf-8") as f:
                    changelog_str = f.read()
            except Exception:
                pass

        if not changelog_str:
            changelog_str = _(
                "CHANGELOG DI TORNELLO\n"
                "=====================\n\n"
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
                with open(credits_path, "r", encoding="utf-8") as f:
                    credits_str = f.read()
            except Exception:
                pass

        if not credits_str:
            credits_str = _(
                "CREDITI DI TORNELLO\n"
                "===================\n\n"
                "Tornello è sviluppato da Gabriele Battaglia e Stella."
            )
        self.append_log(credits_str)
        self.main_text.SetFocus()

    def on_fide_query(self, event):
        from db_players import load_players_db

        players_db = load_players_db()
        from gui.dialogs.fide_query_dialog import FideQueryDialog

        dlg = FideQueryDialog(self, players_db, self.settings)
        dlg.ShowModal()
        dlg.Destroy()

    def on_backup_cleanup(self, event):
        from gui.dialogs.backup_cleanup_dialog import BackupCleanupDialog

        dlg = BackupCleanupDialog(self, self.settings)
        dlg.ShowModal()
        dlg.Destroy()

    def on_fide_update(self, event):
        from config import FIDE_DB_LOCAL_FILE, FIDE_DB_JSON_LEGACY
        from fide_db import cleanup_legacy_json
        from datetime import datetime
        import os

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
            update_dlg.ShowModal()
            update_dlg.Destroy()
        else:
            dlg.Destroy()

    def on_sync_db(self, event):
        from gui.dialogs.sync_database_dialog import SyncDatabaseDialog

        dlg = SyncDatabaseDialog(self, self.settings)
        dlg.ShowModal()
        dlg.Destroy()

    def on_local_db(self, event):
        from gui.dialogs.players_db_dialog import PlayersDbDialog

        dlg = PlayersDbDialog(self, self.settings)
        dlg.ShowModal()
        dlg.Destroy()

    def on_close(self, event):
        from utils import play_sound

        play_sound("chiusura", self.current_tournament, sync=True)

        try:
            import sys
            import io
            from GBUtils import Donazione

            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                current_lang = self.settings.get("language") if self.settings else None
                Donazione(lang=current_lang)
                donation_msg = sys.stdout.getvalue().strip()
            finally:
                sys.stdout = old_stdout

            if donation_msg:
                from gui.dialogs.donation_dialog import DonationDialog

                dlg = DonationDialog(
                    self, _("Offri un caffè"), donation_msg, self.settings
                )
                dlg.ShowModal()
                dlg.Destroy()
        except Exception:
            pass

        event.Skip()

    def on_new_tournament(self, event):
        self.start_new_tournament_wizard()

    def on_open_tournament(self, event):
        dlg = wx.FileDialog(
            self,
            _("Apri Torneo"),
            wildcard="JSON files (*.json)|*.json",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        if dlg.ShowModal() == wx.ID_OK:
            self.load_tournament(dlg.GetPath())
        dlg.Destroy()

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
        from db_players import load_players_db

        players_db = load_players_db()
        from gui.dialogs import PlayerEnrollmentDialog

        enrolled_raw = [p for p in self.current_tournament.get("players", [])]
        dlg = PlayerEnrollmentDialog(self, players_db, enrolled_raw, self.settings)
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
        from reports import get_standings_text

        self.main_text.Clear()
        standings_text = get_standings_text(self.current_tournament, final=False)
        self.append_log(standings_text)
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

        dlg = AccessibleMsgDialog(
            self,
            _("Annulla Turno"),
            _(
                "Sei sicuro di voler annullare l'ultimo turno e tornare indietro? Questa azione è irreversibile."
            ),
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

        dlg = AccessibleMsgDialog(
            self,
            _("Finalizza Torneo"),
            _(
                "Sei sicuro di voler concludere definitivamente il torneo? Verranno calcolati i piazzamenti finali, gli spareggi e aggiornati gli ELO nel database giocatori."
            ),
            style=wx.YES_NO,
        )
        if dlg.ShowModal() == wx.ID_YES:
            from db_players import load_players_db

            players_db = load_players_db()

            from ui import finalize_tournament

            success = finalize_tournament(
                self.current_tournament, players_db, self.active_filename
            )
            if success:
                wx.MessageBox(
                    _(
                        "Torneo finalizzato con successo! I dati dei giocatori sono stati aggiornati."
                    ),
                    _("Successo"),
                    wx.ICON_INFORMATION,
                )
                self.current_tournament = None
                self.active_filename = None
                self.populate_tree()
                self.show_intro_message()
                self.set_status(_("Torneo concluso e archiviato."))
        dlg.Destroy()

    def on_active_field_activated(self, item, field_active):
        from utils import format_date_locale

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
                    except ValueError:
                        wx.MessageBox(
                            _("Formato data non valido. Usa AAAA-MM-GG."),
                            _("Errore"),
                            wx.ICON_ERROR,
                        )
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
                    except ValueError:
                        wx.MessageBox(
                            _("Formato data non valido. Usa AAAA-MM-GG."),
                            _("Errore"),
                            wx.ICON_ERROR,
                        )
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
                from stats import parse_time_control, classify_tournament_category

                tc_parsed = parse_time_control(val)
                if tc_parsed:
                    old_tc = self.current_tournament.get("time_control", {})
                    if tc_parsed != old_tc:
                        self.current_tournament["time_control"] = tc_parsed
                        cat = classify_tournament_category(
                            tc_parsed.get("minutes", 60), tc_parsed.get("increment", 0)
                        )
                        self.current_tournament["tournament_category"] = cat
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
                else:
                    wx.MessageBox(
                        _("Formato non valido. Usa minuti+incremento o solo minuti."),
                        _("Errore"),
                        wx.ICON_ERROR,
                    )
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
            dlg.Destroy()
        elif field_active == "color_board1":
            choices = [
                _("Bianco (scelto dall'arbitro)"),
                _("Nero (scelto dall'arbitro)"),
                _("Casuale (scelto da Tornello)"),
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
                self.withdraw_player(dlg.withdrawn_player_id)
            else:
                res = dlg.get_selected_result()
                if res:
                    p_text = dlg.txt_pgn.GetValue().strip()
                    old_res = actual_match.get("result")
                    old_pgn = actual_match.get("pgn", "").strip()
                    if res != old_res or p_text != old_pgn:
                        if p_text:
                            import chess.pgn
                            import io

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
            self._save_state()
            from utils import play_sound

            play_sound("conferma")
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
                if dlg.ShowModal() == wx.ID_YES:
                    self.withdraw_player(forfeiting_id)
                dlg.Destroy()

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
        report = f"Scheda Giocatore: {p_name}\n"
        report += f"ID: {player.get('id')} | Sesso: {player.get('gender', 'M')} | Nazione: {player.get('federation', 'ITA')}\n"
        report += f"ELO Iniziale: {player.get('initial_elo', 1399)} | ELO Attuale: {player.get('current_elo', 1399)}\n"
        if player.get("withdrawn"):
            report += "Stato: RITIRATO DAL TORNEO\n"
        report += "-" * 50 + "\n\n"

        report += "Storico Partite nel Torneo:\n"
        history = player.get("results_history", [])
        for entry in history:
            opp_id = entry.get("opponent_id")
            opp_p = self.current_tournament.get("players_dict", {}).get(opp_id, {})
            opp_name = (
                f"{opp_p.get('last_name', '')} {opp_p.get('first_name', '')}".strip()
                if opp_id != "BYE_PLAYER_ID"
                else "BYE"
            )
            report += f"  Turno {entry.get('round')}: vs {opp_name} ({entry.get('color', 'N/D')}) -> Risultato: {entry.get('result')} (Punti: {entry.get('score')})\n"

        self.append_log(report)
        self.set_status(_("Visualizzazione scheda di {name}.").format(name=p_name))

    def start_tournament_matchmaking(self):
        from tournament import generate_pairings_for_round
        from utils import play_sound

        matches = generate_pairings_for_round(self.current_tournament)
        if matches is None:
            wx.MessageBox(
                _("Errore nella generazione degli abbinamenti."),
                _("Errore"),
                wx.ICON_ERROR,
            )
            return

        from models import Round, Match

        round_obj = Round(round=1, matches=[Match.from_dict(m) for m in matches])
        self.current_tournament.setdefault("rounds", []).append(round_obj.to_dict())
        self._save_state()

        play_sound("nuovo_turno", self.current_tournament)

        # Imposta il target per ripristinare il focus del cursore sul nuovo turno
        self._tree_restore_target = {
            "action": "show_round_report",
            "filepath": self.active_filename,
            "round": 1,
        }

        self.populate_tree()
        self.show_current_round_report()
        self.set_status(_("Torneo iniziato. Generati abbinamenti per il Turno 1."))

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
        filepath = self.active_filename

        from tournament import generate_pairings_for_round
        from utils import play_sound

        self.current_tournament["current_round"] = next_round_num

        next_matches = generate_pairings_for_round(self.current_tournament)
        if next_matches is None:
            self.current_tournament["current_round"] = curr_round
            wx.MessageBox(
                _("Errore durante la generazione degli abbinamenti."),
                _("Errore"),
                wx.ICON_ERROR,
            )
            return

        players_dict = self.current_tournament.get("players_dict", {})
        for p_id, p in players_dict.items():
            if p.get("withdrawn"):
                p.setdefault("results_history", []).append(
                    {
                        "round": next_round_num,
                        "opponent_id": "BYE_PLAYER_ID",
                        "color": None,
                        "result": "BYE",
                        "score": 0.0,
                    }
                )

        from models import Round, Match

        round_obj = Round(
            round=next_round_num, matches=[Match.from_dict(m) for m in next_matches]
        )
        self.current_tournament.setdefault("rounds", []).append(round_obj.to_dict())
        self._save_state()

        play_sound("nuovo_turno", self.current_tournament)

        # Imposta il target per ripristinare il focus del cursore sul nuovo turno
        self._tree_restore_target = {
            "action": "show_round_report",
            "filepath": filepath,
            "round": next_round_num,
        }

        self.populate_tree()
        self.show_current_round_report()
        self.set_status(
            _("Generati abbinamenti per il Turno {num}.").format(num=next_round_num)
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
                ics_content = generate_ics_content(self.current_tournament)
                with open(path, "w", encoding="utf-8", newline="\r\n") as f:
                    f.write(ics_content)
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
