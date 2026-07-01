import os
import glob
import json
import wx
import builtins
from version import __version__, __date__, __authors__
from gui.settings import apply_visual_settings, save_settings
from gui.dialogs import AccessibleMsgDialog, VisualSettingsDialog

_ = getattr(builtins, "_", lambda s: s)

class MainFrame(wx.Frame):
    """
    Finestra principale (MainFrame) di Tornello v9.0.
    Implementa la barra dei menu, l'area centrale dei report, l'albero di navigazione
    a destra e la barra di stato personalizzata per NVDA in basso.
    """
    def __init__(self, parent, title, settings):
        # Titolo iniziale dell'app
        title_str = f"Tornello - Versione {__version__} - Data Rilascio {__date__} - [Nessun Torneo Caricato]"
        super().__init__(parent, title=title_str, size=(1024, 768))
        
        self.settings = settings
        self.current_tournament = None
        self.active_filename = None
        self.creation_data = {}  # Contiene i dati transitori del nuovo torneo in fase di inserimento nell'albero
        self.creation_mode = False  # True se stiamo compilando l'albero per il Nuovo Torneo
        
        self._init_ui()
        self._setup_shortcuts()
        self._check_fide_db_on_startup()
        self._scan_and_load_initial_tournament()
        self.Centre()

    def _init_ui(self):
        # Pannello principale di contenimento
        self.top_panel = wx.Panel(self)
        main_layout = wx.BoxSizer(wx.VERTICAL)
        
        # Splitter per dividere l'area centrale e l'albero a destra
        self.splitter = wx.SplitterWindow(self.top_panel, style=wx.SP_3D | wx.SP_LIVE_UPDATE)
        
        # Area Sinistra: Grande controllo di testo multi-riga per i report
        self.main_text = wx.TextCtrl(self.splitter, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        
        # Area Destra: Albero di navigazione
        self.tree_ctrl = wx.TreeCtrl(self.splitter, style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT)
        self.tree_ctrl.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.on_tree_item_activated)
        self.tree_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_tree_key_down)
        
        # Configurazione splitter
        self.splitter.SplitVertically(self.main_text, self.tree_ctrl, 700)
        self.splitter.SetMinimumPaneSize(150)
        
        main_layout.Add(self.splitter, 1, wx.EXPAND | wx.ALL, 5)
        
        # Barra di Stato personalizzata in basso (TextCtrl accessibile a 3 righe)
        self.status_text = wx.TextCtrl(self.top_panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(-1, 60))
        main_layout.Add(self.status_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        self.top_panel.SetSizer(main_layout)
        
        # Barra dei Menu
        self._init_menubar()
        
        # Applica i colori e font salvati
        self.apply_theme()
        
        # Messaggio introduttivo iniziale
        self.show_intro_message()

    def _init_menubar(self):
        self.menu_bar = wx.MenuBar()
        
        # File
        file_menu = wx.Menu()
        file_menu.Append(wx.ID_NEW, _("&Nuovo Torneo...\tCtrl+N") if "_" in globals() else "&Nuovo Torneo...\tCtrl+N")
        file_menu.Append(wx.ID_OPEN, _("&Apri Torneo...\tCtrl+O") if "_" in globals() else "&Apri Torneo...\tCtrl+O")
        file_menu.Append(wx.ID_SAVE, _("&Salva Torneo\tCtrl+S") if "_" in globals() else "&Salva Torneo\tCtrl+S")
        file_menu.AppendSeparator()
        file_menu.Append(wx.ID_EXIT, _("&Esci\tCtrl+Q") if "_" in globals() else "&Esci\tCtrl+Q")
        self.menu_bar.Append(file_menu, _("&File") if "_" in globals() else "&File")
        
        # Torneo
        torneo_menu = wx.Menu()
        self.item_enroll = torneo_menu.Append(wx.ID_ANY, _("&Iscrizione Giocatori...\tCtrl+I") if "_" in globals() else "&Iscrizione Giocatori...\tCtrl+I")
        self.item_players = torneo_menu.Append(wx.ID_ANY, _("Visualizza &Giocatori\tCtrl+G") if "_" in globals() else "Visualizza &Giocatori\tCtrl+G")
        self.item_round = torneo_menu.Append(wx.ID_ANY, _("&Abbinamenti / Turno Corrente\tCtrl+U") if "_" in globals() else "&Abbinamenti / Turno Corrente\tCtrl+U")
        self.item_standings = torneo_menu.Append(wx.ID_ANY, _("&Classifica Corrente\tCtrl+L") if "_" in globals() else "&Classifica Corrente\tCtrl+L")
        self.item_rollback = torneo_menu.Append(wx.ID_ANY, _("&Time Machine (Annulla Turno)\tCtrl+Z") if "_" in globals() else "&Time Machine (Annulla Turno)\tCtrl+Z")
        self.item_finalize = torneo_menu.Append(wx.ID_ANY, _("&Finalizza Torneo\tCtrl+F") if "_" in globals() else "&Finalizza Torneo\tCtrl+F")
        self.menu_bar.Append(torneo_menu, _("&Torneo") if "_" in globals() else "&Torneo")
        
        # Database
        db_menu = wx.Menu()
        self.item_local_db = db_menu.Append(wx.ID_ANY, _("&Gestione Giocatori Locale\tCtrl+D"))
        self.item_sync_db = db_menu.Append(wx.ID_ANY, _("&Sincronizza DB Locale con FIDE\tCtrl+Y"))
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
        self.item_fide_update = tools_menu.Append(wx.ID_ANY, _("&Verifica Aggiornamenti FIDE"))
        tools_menu.Append(wx.ID_PREFERENCES, _("&Impostazioni (Audio/Video/Lingua)...\tCtrl+P"))
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
        self.Bind(wx.EVT_MENU, self.on_local_db, self.item_local_db)
        self.Bind(wx.EVT_MENU, self.on_sync_db, self.item_sync_db)
        self.Bind(wx.EVT_MENU, self.on_changelog, self.item_changelog)
        self.Bind(wx.EVT_MENU, self.on_credits, self.item_credits)

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

    def set_status(self, text):
        """Aggiorna il contenuto della barra di stato personalizzata in basso."""
        self.status_text.SetValue(text)

    def append_log(self, text):
        """Aggiunge testo all'area centrale posizionando il cursore all'inizio del blocco inserito."""
        if not text.endswith("\n"):
            text += "\n"
        insertion_point = self.main_text.GetLastPosition()
        self.main_text.AppendText(text)
        self.main_text.SetInsertionPoint(insertion_point)
        self.main_text.ShowPosition(insertion_point)
        self.main_text.SetFocus()

    def show_intro_message(self):
        self.main_text.Clear()
        intro = (
            f"Tornello v{__version__} - Gestione Tornei di Scacchi Accessibile\n"
            f"Sviluppato da {__authors__} (Rilascio: {__date__})\n\n"
            f"Tornello è progettato per essere utilizzabile al 100% con screen reader (NVDA/JAWS).\n"
            f"Premere il tasto TAB (o F6) per spostarsi sull'albero a destra e selezionare o creare un torneo.\n\n"
            f"Tasti rapidi globali:\n"
            f" - F1: Guida / Manuale\n"
            f" - F2: Changelog del software\n"
            f" - F3: Informazioni e Crediti\n"
            f" - F5: Sposta il focus sulla grande area centrale dei report\n"
            f" - F6: Sposta il focus sull'albero di navigazione dei tornei\n"
            f" - F7: Sposta il focus sulla barra di stato inferiore\n"
        )
        self.append_log(intro)
        self.set_status("Pronto. Nessun torneo caricato.")

    def _check_fide_db_on_startup(self):
        """Verifica se il DB FIDE locale ha più di 30 giorni e propone l'aggiornamento."""
        from config import FIDE_DB_LOCAL_FILE
        if os.path.exists(FIDE_DB_LOCAL_FILE):
            try:
                from datetime import datetime
                file_mod_timestamp = os.path.getmtime(FIDE_DB_LOCAL_FILE)
                file_age_days = (datetime.now() - datetime.fromtimestamp(file_mod_timestamp)).days
                if file_age_days >= 30:
                    msg = (
                        f"Il database FIDE locale è stato aggiornato {file_age_days} giorni fa.\n"
                        f"Si consiglia di verificare e scaricare l'aggiornamento più recente.\n"
                        f"Vuoi procedere con il controllo e lo scaricamento ora?"
                    )
                    dlg = AccessibleMsgDialog(self, "Aggiornamento Database FIDE", msg, style=wx.YES_NO)
                    if dlg.ShowModal() == wx.ID_YES:
                        # Avvia aggiornamento (implementeremo poi l'UpdateFideDatabaseDialog)
                        self.set_status("Verifica aggiornamenti database FIDE avviata...")
                    dlg.Destroy()
            except Exception:
                pass

    def _scan_and_load_initial_tournament(self):
        """Scansiona i file torneo in corso ed effettua il caricamento automatico se ce n'è solo uno."""
        from config import PLAYER_DB_FILE
        tournament_files = [
            f for f in glob.glob("Tornello - *.json")
            if "- concluso_" not in os.path.basename(f).lower()
            and os.path.basename(f) != os.path.basename(PLAYER_DB_FILE)
        ]
        
        # Se c'è esattamente un solo torneo attivo, lo carichiamo all'avvio
        if len(tournament_files) == 1:
            filepath = tournament_files[0]
            self.load_tournament(filepath)
        else:
            self.populate_tree()

    def load_tournament(self, filepath):
        """Carica un torneo dal file JSON."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.current_tournament = data
            self.active_filename = filepath
            
            # Aggiorna titolo finestra
            t_name = data.get("name", "Torneo Sconosciuto")
            title_str = f"Tornello - Versione {__version__} - Data Rilascio {__date__} - [{t_name}]"
            self.SetTitle(title_str)
            
            # Carica il report del turno corrente nell'area centrale
            self.show_current_round_report()
            
            # Rigenera l'albero con i dati del torneo caricato
            self.populate_tree()
            self.set_status(f"Torneo '{t_name}' caricato con successo.")
        except Exception as e:
            wx.MessageBox(f"Errore nel caricamento del torneo: {e}", "Errore", wx.ICON_ERROR)
            self.current_tournament = None
            self.active_filename = None
            self.populate_tree()

    def show_current_round_report(self):
        """Visualizza l'abbinamento del turno corrente o lo stato del torneo concluso."""
        if not self.current_tournament:
            return
        
        self.main_text.Clear()
        t_name = self.current_tournament.get("name", "Torneo Sconosciuto")
        curr_round = self.current_tournament.get("current_round", 1)
        tot_rounds = self.current_tournament.get("total_rounds", 5)
        
        report = f"Torneo: {t_name}\nTurno Corrente: {curr_round} di {tot_rounds}\n"
        report += "-" * 40 + "\n"
        
        # Mostra abbinamenti se presenti
        rounds = self.current_tournament.get("rounds", [])
        active_round_data = next((r for r in rounds if r.get("round") == curr_round), None)
        if active_round_data:
            report += f"Abbinamenti Turno {curr_round}:\n"
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
                    report += f"  {w_name} vs {b_name}{res_str}\n"
                else:
                    report += f"  {w_name} - BYE (1.0 punti)\n"
        else:
            report += "Nessun abbinamento generato per questo turno.\n"
            
        self.append_log(report)

    def populate_tree(self):
        """Costruisce e popola l'albero TreeCtrl destro a seconda dello stato dell'app."""
        self.tree_ctrl.DeleteAllItems()
        self.tree_root = self.tree_ctrl.AddRoot("Root")
        
        if not self.current_tournament:
            # Caso A: Nessun torneo caricato
            self.populate_tree_no_tournament()
        else:
            # Caso B: Torneo caricato
            self.populate_tree_with_tournament()

    def populate_tree_no_tournament(self):
        # 1. Tornei attivi
        from config import PLAYER_DB_FILE
        active_files = [
            f for f in glob.glob("Tornello - *.json")
            if "- concluso_" not in os.path.basename(f).lower()
            and os.path.basename(f) != os.path.basename(PLAYER_DB_FILE)
        ]
        
        for f in active_files:
            try:
                with open(f, "r", encoding="utf-8") as f_in:
                    data = json.load(f_in)
                t_name = data.get("name", os.path.basename(f))
                curr_r = data.get("current_round", 1)
                tot_r = data.get("total_rounds", 5)
                label = f"{t_name} (Turno {curr_r}/{tot_r})"
                item = self.tree_ctrl.AppendItem(self.tree_root, label)
                self.tree_ctrl.SetItemPyData(item, {"action": "load_tournament", "filepath": f})
            except Exception:
                pass
                
        # 2. Cartella Tornei Conclusi
        closed_files = glob.glob(os.path.join("Closed Tournaments", "**", "Tornello - *.json"), recursive=True)
        closed_item = self.tree_ctrl.AppendItem(self.tree_root, f"Tornei Conclusi ({len(closed_files)})")
        for f in closed_files:
            try:
                with open(f, "r", encoding="utf-8") as f_in:
                    data = json.load(f_in)
                t_name = data.get("name", os.path.basename(f))
                
                # Formatta mese e anno di conclusione
                end_date_str = data.get("end_date")
                month_year = ""
                if end_date_str:
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(end_date_str, "%Y-%m-%d")
                        mesi = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", 
                                "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
                        month_name = mesi[dt.month - 1].capitalize()
                        month_year = f" ({month_name} {dt.year})"
                    except Exception:
                        pass
                        
                label = f"{t_name}{month_year}"
                item = self.tree_ctrl.AppendItem(closed_item, label)
                self.tree_ctrl.SetItemPyData(item, {"action": "load_concluded", "filepath": f})
            except Exception:
                pass
                
        # 3. Nuovo Torneo
        new_item = self.tree_ctrl.AppendItem(self.tree_root, "Nuovo torneo")
        self.tree_ctrl.SetItemPyData(new_item, {"action": "start_new_tournament"})

    def populate_tree_with_tournament(self):
        t_name = self.current_tournament.get("name", "Torneo")
        root_item = self.tree_ctrl.AppendItem(self.tree_root, t_name)
        
        # Dati
        dati_item = self.tree_ctrl.AppendItem(root_item, "Dati")
        self.tree_ctrl.SetItemPyData(dati_item, {"action": "show_data"})
        self.node_dati = dati_item
        
        # Sotto-nodi per i parametri del torneo attivo
        from utils import format_date_locale
        name_item = self.tree_ctrl.AppendItem(dati_item, f"Nome torneo: {self.current_tournament.get('name')}")
        self.tree_ctrl.SetItemPyData(name_item, {"field_active": "name"})
        
        site_item = self.tree_ctrl.AppendItem(dati_item, f"Luogo (Site): {self.current_tournament.get('site')}")
        self.tree_ctrl.SetItemPyData(site_item, {"field_active": "site"})

        start_item = self.tree_ctrl.AppendItem(dati_item, f"Data inizio: {format_date_locale(self.current_tournament.get('start_date'))}")
        self.tree_ctrl.SetItemPyData(start_item, {"field_active": "start_date"})

        end_item = self.tree_ctrl.AppendItem(dati_item, f"Data fine: {format_date_locale(self.current_tournament.get('end_date'))}")
        self.tree_ctrl.SetItemPyData(end_item, {"field_active": "end_date"})

        tc = self.current_tournament.get("time_control", "Standard")
        tc_disp = tc if isinstance(tc, str) else f"{tc.get('minutes', 60)}+{tc.get('increment', 0)}"
        tc_item = self.tree_ctrl.AppendItem(dati_item, f"Tempo riflessione: {tc_disp}")
        self.tree_ctrl.SetItemPyData(tc_item, {"field_active": "time_control"})

        arb_item = self.tree_ctrl.AppendItem(dati_item, f"Arbitro Capo: {self.current_tournament.get('chief_arbiter', 'N/D')}")
        self.tree_ctrl.SetItemPyData(arb_item, {"field_active": "chief_arbiter"})

        dep_item = self.tree_ctrl.AppendItem(dati_item, f"Collaboratori: {self.current_tournament.get('deputy_chief_arbiters', '') or 'Nessuno'}")
        self.tree_ctrl.SetItemPyData(dep_item, {"field_active": "deputy_chief_arbiters"})

        fed_item = self.tree_ctrl.AppendItem(dati_item, f"Codice Federazione: {self.current_tournament.get('federation_code', 'ITA')}")
        self.tree_ctrl.SetItemPyData(fed_item, {"field_active": "federation_code"})

        col_raw = self.current_tournament.get("initial_board1_color_setting", "white1")
        col_disp_map = {
            "white1": "Bianco",
            "black1": "Nero",
            "random": "Casuale"
        }
        col_val = col_disp_map.get(col_raw, "Bianco")
        col_item = self.tree_ctrl.AppendItem(dati_item, f"Colore al giocatore più forte: {col_val}")
        self.tree_ctrl.SetItemPyData(col_item, {"field_active": "color_board1"})

        bye_item = self.tree_ctrl.AppendItem(dati_item, f"Valore del BYE: {self.current_tournament.get('bye_value', 1.0)}")
        self.tree_ctrl.SetItemPyData(bye_item, {"field_active": "bye_value"})
        
        # Partecipanti
        num_players = len(self.current_tournament.get("players", []))
        part_item = self.tree_ctrl.AppendItem(root_item, f"Partecipanti ({num_players})")
        self.tree_ctrl.SetItemPyData(part_item, {"action": "show_players"})
        self.node_partecipanti = part_item
        
        for p in self.current_tournament.get("players", []):
            p_lbl = f"{p.get('last_name', '')} {p.get('first_name', '')} (Elo: {p.get('initial_elo', 1399)})"
            if p.get("withdrawn"):
                p_lbl += " [RIT]"
            p_node = self.tree_ctrl.AppendItem(part_item, p_lbl)
            self.tree_ctrl.SetItemPyData(p_node, {"action": "show_player_detail", "player": p})
        
        # Partite
        curr_round = self.current_tournament.get("current_round", 1)
        rounds = self.current_tournament.get("rounds", [])
        round_data = next((r for r in rounds if r.get("round") == curr_round), None)
        matches = round_data.get("matches", []) if round_data else []
        
        num_concluded = sum(1 for m in matches if m.get("result") is not None)
        num_scheduled = sum(1 for m in matches if m.get("result") is None and m.get("is_scheduled") and m.get("schedule_info"))
        num_unscheduled = len(matches) - num_concluded - num_scheduled
        
        partite_item = self.tree_ctrl.AppendItem(root_item, f"Partite ({len(matches)})")
        self.tree_ctrl.SetItemPyData(partite_item, {"action": "show_matches"})
        self.node_partite = partite_item
        
        unsched_item = self.tree_ctrl.AppendItem(partite_item, f"Non pianificate ({num_unscheduled})")
        self.tree_ctrl.SetItemPyData(unsched_item, {"action": "show_matches_unscheduled"})
        self.node_non_pianificate = unsched_item
        
        sched_item = self.tree_ctrl.AppendItem(partite_item, f"Pianificate ({num_scheduled})")
        self.tree_ctrl.SetItemPyData(sched_item, {"action": "show_matches_scheduled"})
        self.node_pianificate = sched_item
        
        conc_item = self.tree_ctrl.AppendItem(partite_item, f"Concluse ({num_concluded})")
        self.tree_ctrl.SetItemPyData(conc_item, {"action": "show_matches_concluded"})
        self.node_concluse = conc_item
        
        # Popola accoppiamenti
        players_dict = self.current_tournament.get("players_dict", {})
        for m in matches:
            w_id = m.get("white_player_id")
            b_id = m.get("black_player_id")
            res = m.get("result")
            w_p = players_dict.get(w_id, {})
            b_p = players_dict.get(b_id, {}) if b_id else None
            
            w_name = f"{w_p.get('last_name', '')} {w_p.get('first_name', '')}".strip()
            if b_p:
                b_name = f"{b_p.get('last_name', '')} {b_p.get('first_name', '')}".strip()
                match_label = f"Scacchiera {m.get('board')}: {w_name} vs {b_name}"
            else:
                match_label = f"Scacchiera {m.get('board')}: {w_name} - BYE"
                
            if res is not None:
                lbl = f"{match_label} [{res}]"
                m_node = self.tree_ctrl.AppendItem(conc_item, lbl)
            elif m.get("is_scheduled") and m.get("schedule_info"):
                info = m["schedule_info"]
                lbl = f"{match_label} ({info.get('date')} {info.get('time')})"
                m_node = self.tree_ctrl.AppendItem(sched_item, lbl)
            else:
                m_node = self.tree_ctrl.AppendItem(unsched_item, match_label)
                
            self.tree_ctrl.SetItemPyData(m_node, {"action": "activate_match", "match": m})
        
        # Inizia torneo (se applicabile)
        is_started = len(rounds) > 0
        if not is_started:
            start_item = self.tree_ctrl.AppendItem(root_item, "Inizia torneo")
            self.tree_ctrl.SetItemPyData(start_item, {"action": "start_tournament_matchmaking"})
            
        self.tree_ctrl.Expand(root_item)

    def on_tree_item_activated(self, event):
        item = event.GetItem()
        data = self.tree_ctrl.GetItemPyData(item)
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
        if action == "load_tournament":
            self.load_tournament(data["filepath"])
        elif action == "load_concluded":
            self.load_concluded_tournament_report(data["filepath"])
        elif action == "start_new_tournament":
            self.start_new_tournament_wizard()
        elif action == "wizard_next":
            self.on_wizard_next()
        elif action == "wizard_back":
            self.on_wizard_back()
        elif action == "activate_match":
            self.on_activate_match(data["match"])
        elif action == "show_player_detail":
            self.show_player_detail(data["player"])
        elif action == "start_tournament_matchmaking":
            self.start_tournament_matchmaking()

    def on_wizard_field_activated(self, item, field):
        from utils import format_date_locale
        
        if field == "name":
            dlg = wx.TextEntryDialog(self, _("Inserisci il nome del torneo:"), _("Nome Torneo"), self.creation_data["name"])
            if dlg.ShowModal() == wx.ID_OK:
                self.creation_data["name"] = dlg.GetValue().strip()
                self.tree_ctrl.SetItemText(item, f"Nome torneo: {self.creation_data['name'] or 'Non impostato'}")
            dlg.Destroy()
        elif field == "site":
            dlg = wx.TextEntryDialog(self, _("Inserisci il luogo (Site):"), _("Luogo Torneo"), self.creation_data["site"])
            if dlg.ShowModal() == wx.ID_OK:
                self.creation_data["site"] = dlg.GetValue().strip()
                self.tree_ctrl.SetItemText(item, f"Luogo (Site): {self.creation_data['site'] or 'Non impostato'}")
            dlg.Destroy()
        elif field == "rounds":
            dlg = wx.TextEntryDialog(self, _("Inserisci il numero di turni:"), _("Numero Turni"), str(self.creation_data["rounds"]))
            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                if val.isdigit():
                    self.creation_data["rounds"] = int(val)
                    self.tree_ctrl.SetItemText(item, f"Numero turni: {self.creation_data['rounds']}")
                else:
                    wx.MessageBox(_("Inserisci un numero intero valido."), _("Errore"), wx.ICON_ERROR)
            dlg.Destroy()
        elif field == "time_control":
            dlg = wx.TextEntryDialog(self, _("Inserisci il tempo di riflessione (es. 15+10 o 90+30 o 60+0):"), _("Tempo di riflessione"), self.creation_data["time_control"])
            if dlg.ShowModal() == wx.ID_OK:
                self.creation_data["time_control"] = dlg.GetValue().strip()
                self.tree_ctrl.SetItemText(item, f"Tempo riflessione: {self.creation_data['time_control'] or 'Non impostato'}")
            dlg.Destroy()
        elif field == "save_path":
            dlg = wx.DirDialog(self, _("Seleziona la cartella di salvataggio per i report:"), self.creation_data["save_path"])
            if dlg.ShowModal() == wx.ID_OK:
                self.creation_data["save_path"] = dlg.GetPath()
                self.tree_ctrl.SetItemText(item, f"Cartella di salvataggio: {self.creation_data['save_path']}")
            dlg.Destroy()
        elif field == "start_date":
            dlg = wx.TextEntryDialog(self, _("Inserisci la data di inizio (AAAA-MM-GG):"), _("Data Inizio"), self.creation_data["start_date"])
            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                try:
                    from datetime import datetime
                    datetime.strptime(val, "%Y-%m-%d")
                    self.creation_data["start_date"] = val
                    self.tree_ctrl.SetItemText(item, f"Data inizio: {format_date_locale(val)}")
                except ValueError:
                    wx.MessageBox(_("Formato data non valido. Usa AAAA-MM-GG."), _("Errore"), wx.ICON_ERROR)
            dlg.Destroy()
        elif field == "end_date":
            dlg = wx.TextEntryDialog(self, _("Inserisci la data di fine (AAAA-MM-GG):"), _("Data Fine"), self.creation_data["end_date"])
            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                try:
                    from datetime import datetime
                    datetime.strptime(val, "%Y-%m-%d")
                    self.creation_data["end_date"] = val
                    self.tree_ctrl.SetItemText(item, f"Data fine: {format_date_locale(val)}")
                except ValueError:
                    wx.MessageBox(_("Formato data non valido. Usa AAAA-MM-GG."), _("Errore"), wx.ICON_ERROR)
            dlg.Destroy()
        elif field == "chief_arbiter":
            dlg = wx.TextEntryDialog(self, _("Inserisci il nome dell'Arbitro Capo:"), _("Arbitro Capo"), self.creation_data["chief_arbiter"])
            if dlg.ShowModal() == wx.ID_OK:
                self.creation_data["chief_arbiter"] = dlg.GetValue().strip()
                self.tree_ctrl.SetItemText(item, f"Arbitro Capo: {self.creation_data['chief_arbiter'] or 'Non impostato'}")
            dlg.Destroy()
        elif field == "deputy_chief_arbiters":
            dlg = wx.TextEntryDialog(self, _("Inserisci i collaboratori / vice arbitri (separati da virgola):"), _("Collaboratori / Vice Arbitri"), self.creation_data["deputy_chief_arbiters"])
            if dlg.ShowModal() == wx.ID_OK:
                self.creation_data["deputy_chief_arbiters"] = dlg.GetValue().strip()
                self.tree_ctrl.SetItemText(item, f"Collaboratori / Vice Arbitri: {self.creation_data['deputy_chief_arbiters'] or 'Non impostate'}")
            dlg.Destroy()
        elif field == "federation_code":
            dlg = wx.TextEntryDialog(self, _("Inserisci il codice della federazione ospitante (es. ITA, FRA):"), _("Codice Federazione"), self.creation_data["federation_code"])
            if dlg.ShowModal() == wx.ID_OK:
                self.creation_data["federation_code"] = dlg.GetValue().strip().upper()
                self.tree_ctrl.SetItemText(item, f"Codice Federazione: {self.creation_data['federation_code']}")
            dlg.Destroy()
        elif field == "color_board1":
            choices = ["Bianco", "Nero", "Casuale"]
            dlg = wx.SingleChoiceDialog(self, _("Seleziona il colore per il giocatore più forte (scacchiera 1, turno 1):"), _("Colore al giocatore più forte"), choices)
            curr_raw = self.creation_data["color_board1"]
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
                self.creation_data["color_board1"] = val_raw
                col_disp = choices[sel]
                self.tree_ctrl.SetItemText(item, f"Colore al giocatore più forte: {col_disp}")
            dlg.Destroy()
        elif field == "bye_value":
            choices = ["0.0", "0.5", "1.0"]
            dlg = wx.SingleChoiceDialog(self, _("Seleziona il valore del BYE secondo la regola FIDE:"), _("Valore del BYE"), choices)
            curr_str = str(self.creation_data["bye_value"])
            if curr_str in choices:
                dlg.SetSelection(choices.index(curr_str))
            if dlg.ShowModal() == wx.ID_OK:
                self.creation_data["bye_value"] = float(dlg.GetStringSelection())
                self.tree_ctrl.SetItemText(item, f"Valore del BYE: {self.creation_data['bye_value']}")
            dlg.Destroy()
            
        # Controlla se dobbiamo aggiungere il bottone "Avanti"
        if self.creation_data["name"] and self.creation_data["time_control"]:
            has_next = False
            child, cookie = self.tree_ctrl.GetFirstChild(self.tree_root)
            while child.IsOk():
                cdata = self.tree_ctrl.GetItemPyData(child)
                if cdata and cdata.get("action") == "wizard_next":
                    has_next = True
                    break
                child, cookie = self.tree_ctrl.GetNextChild(self.tree_root, cookie)
            if not has_next:
                next_item = self.tree_ctrl.AppendItem(self.tree_root, "Avanti")
                self.tree_ctrl.SetItemPyData(next_item, {"action": "wizard_next"})

    def on_wizard_next(self):
        from db_players import load_players_db
        players_db = load_players_db()
        
        # Apri il dialogo di iscrizione giocatori
        from gui.dialogs import PlayerEnrollmentDialog
        dlg = PlayerEnrollmentDialog(self, players_db, [], self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            enrolled = dlg.get_enrolled_players()
            if len(enrolled) < 2:
                wx.MessageBox(_("Sono necessari almeno 2 giocatori per avviare un torneo."), _("Errore"), wx.ICON_ERROR)
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
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                wx.MessageBox(f"Impossibile creare la cartella di salvataggio: {e}", "Errore", wx.ICON_ERROR)
                return
                
        sanitized = sanitize_filename(self.creation_data["name"])
        self.active_filename = f"Tornello - {sanitized}.json"
        
        from tournament import calculate_dates
        round_dates_raw = calculate_dates(self.creation_data["start_date"], self.creation_data["end_date"], self.creation_data["rounds"]) or []
        
        # Classificazione categoria Elo
        from utils import parse_time_control, classify_tournament_category
        tc_parsed = parse_time_control(self.creation_data["time_control"]) or {"minutes": 60, "increment": 0}
        tournament_category = classify_tournament_category(tc_parsed.get("minutes", 60), tc_parsed.get("increment", 0))
        
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
            "round_dates": [rd.to_dict() for rd in [RoundDate.from_dict(x) for x in round_dates_raw]],
            "players": [p.to_dict() for p in players],
            "rounds": [],
            "custom_save_path": save_dir,
            "save_path": save_dir,
            "bye_value": self.creation_data["bye_value"],
            "tournament_category": tournament_category
        }
        
        tournament = Tournament.from_dict(t_dict)
        tournament.update_players_dict()
        
        # Genera accoppiamenti per il Turno 1
        matches = generate_pairings_for_round(tournament.to_dict())
        if matches is None:
            wx.MessageBox(_("Errore nella generazione degli abbinamenti con bbpPairings."), _("Errore"), wx.ICON_ERROR)
            return
            
        from models import Round, Match
        round_obj = Round(round=1, matches=[Match.from_dict(m) for m in matches])
        tournament.rounds.append(round_obj)
        
        self.current_tournament = tournament.to_dict()
        
        # Salva stato
        self._save_state()
        
        self.creation_mode = False
        self.load_tournament(self.active_filename)

    def _save_state(self):
        if self.current_tournament:
            from tournament import save_tournament
            from reports import save_current_tournament_round_file, save_standings_text
            save_tournament(self.current_tournament)
            save_current_tournament_round_file(self.current_tournament)
            save_standings_text(self.current_tournament, final=False)

    def on_tree_key_down(self, event):
        key_code = event.GetKeyCode()
        item = self.tree_ctrl.GetSelection()
        
        if key_code == wx.WXK_DELETE and item:
            data = self.tree_ctrl.GetItemPyData(item)
            if data and data.get("action") == "load_concluded":
                # Elimina torneo concluso
                self.delete_concluded_tournament(item, data["filepath"])
                return
                
        event.Skip()

    def load_concluded_tournament_report(self, filepath):
        """Visualizza i report e la classifica di un torneo concluso nell'area centrale."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            t_name = data.get("name", "Torneo Concluso")
            
            self.main_text.Clear()
            report = f"Torneo Concluso: {t_name}\n"
            report += f"Data Inizio: {data.get('start_date', 'N/D')} | Fine: {data.get('end_date', 'N/D')}\n"
            report += "-" * 50 + "\n\n"
            
            # Aggiungi classifica finale se presente nel json
            report += "Classifica Finale:\n"
            players = data.get("players", [])
            players_sorted = sorted(players, key=lambda p: p.get("points", 0.0), reverse=True)
            for idx, p in enumerate(players_sorted):
                p_name = f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
                report += f" {idx+1:>2}. {p_name:<30} Punti: {p.get('points', 0.0):.1f}\n"
                
            self.append_log(report)
            self.set_status(f"Visualizzazione report torneo concluso '{t_name}'.")
        except Exception as e:
            wx.MessageBox(f"Impossibile leggere il report: {e}", "Errore", wx.ICON_ERROR)

    def delete_concluded_tournament(self, item, filepath):
        """Rimuove fisicamente dal disco un torneo concluso dopo conferma."""
        t_label = self.tree_ctrl.GetItemText(item)
        msg = f"Sei sicuro di voler eliminare definitivamente il torneo concluso '{t_label}'?\nQuesta azione rimuoverà il file dal disco in modo permanente."
        dlg = AccessibleMsgDialog(self, "Conferma Eliminazione Torneo", msg, style=wx.YES_NO)
        if dlg.ShowModal() == wx.ID_YES:
            try:
                os.remove(filepath)
                self.tree_ctrl.Delete(item)
                self.show_intro_message()
                self.set_status(f"Torneo '{t_label}' eliminato con successo.")
            except Exception as e:
                wx.MessageBox(f"Impossibile eliminare il file: {e}", "Errore", wx.ICON_ERROR)
        dlg.Destroy()

    def start_new_tournament_wizard(self):
        """Inizia il flusso guidato di inserimento dati nell'albero per il Nuovo Torneo."""
        from datetime import datetime, timedelta
        from config import DATE_FORMAT_ISO
        
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
            "bye_value": 1.0
        }
        self.populate_new_tournament_wizard_tree()

    def populate_new_tournament_wizard_tree(self):
        self.tree_ctrl.DeleteAllItems()
        self.tree_root = self.tree_ctrl.AddRoot("Nuovo Torneo")
        
        # Voce Indietro per annullare
        back_item = self.tree_ctrl.AppendItem(self.tree_root, "Indietro")
        self.tree_ctrl.SetItemPyData(back_item, {"action": "wizard_back"})
        
        name_val = self.creation_data["name"] or "Non impostato"
        site_val = self.creation_data["site"] or "Non impostato"
        
        from utils import format_date_locale
        start_val = format_date_locale(self.creation_data["start_date"])
        end_val = format_date_locale(self.creation_data["end_date"])
        
        rounds_val = str(self.creation_data["rounds"])
        tc_val = self.creation_data["time_control"] or "Non impostato"
        path_val = self.creation_data["save_path"]
        arb_val = self.creation_data["chief_arbiter"] or "Non impostato"
        dep_val = self.creation_data["deputy_chief_arbiters"] or "Non impostate"
        fed_val = self.creation_data["federation_code"] or "ITA"
        
        col_raw = self.creation_data["color_board1"]
        col_disp_map = {
            "white1": "Bianco",
            "black1": "Nero",
            "random": "Casuale"
        }
        col_val = col_disp_map.get(col_raw, "Bianco")
        
        bye_val = str(self.creation_data["bye_value"])
        
        self.tree_name = self.tree_ctrl.AppendItem(self.tree_root, f"Nome torneo: {name_val}")
        self.tree_ctrl.SetItemPyData(self.tree_name, {"field": "name"})
        
        self.tree_site = self.tree_ctrl.AppendItem(self.tree_root, f"Luogo (Site): {site_val}")
        self.tree_ctrl.SetItemPyData(self.tree_site, {"field": "site"})

        self.tree_start = self.tree_ctrl.AppendItem(self.tree_root, f"Data inizio: {start_val}")
        self.tree_ctrl.SetItemPyData(self.tree_start, {"field": "start_date"})

        self.tree_end = self.tree_ctrl.AppendItem(self.tree_root, f"Data fine: {end_val}")
        self.tree_ctrl.SetItemPyData(self.tree_end, {"field": "end_date"})
        
        self.tree_rounds = self.tree_ctrl.AppendItem(self.tree_root, f"Numero turni: {rounds_val}")
        self.tree_ctrl.SetItemPyData(self.tree_rounds, {"field": "rounds"})
        
        self.tree_tc = self.tree_ctrl.AppendItem(self.tree_root, f"Tempo riflessione: {tc_val}")
        self.tree_ctrl.SetItemPyData(self.tree_tc, {"field": "time_control"})
        
        self.tree_path = self.tree_ctrl.AppendItem(self.tree_root, f"Cartella di salvataggio: {path_val}")
        self.tree_ctrl.SetItemPyData(self.tree_path, {"field": "save_path"})

        self.tree_arb = self.tree_ctrl.AppendItem(self.tree_root, f"Arbitro Capo: {arb_val}")
        self.tree_ctrl.SetItemPyData(self.tree_arb, {"field": "chief_arbiter"})

        self.tree_dep = self.tree_ctrl.AppendItem(self.tree_root, f"Collaboratori / Vice Arbitri: {dep_val}")
        self.tree_ctrl.SetItemPyData(self.tree_dep, {"field": "deputy_chief_arbiters"})

        self.tree_fed = self.tree_ctrl.AppendItem(self.tree_root, f"Codice Federazione: {fed_val}")
        self.tree_ctrl.SetItemPyData(self.tree_fed, {"field": "federation_code"})

        self.tree_col = self.tree_ctrl.AppendItem(self.tree_root, f"Colore al giocatore più forte: {col_val}")
        self.tree_ctrl.SetItemPyData(self.tree_col, {"field": "color_board1"})

        self.tree_bye = self.tree_ctrl.AppendItem(self.tree_root, f"Valore del BYE: {bye_val}")
        self.tree_ctrl.SetItemPyData(self.tree_bye, {"field": "bye_value"})
        
        # Verifica se i campi obbligatori sono validati per mostrare "Avanti"
        if self.creation_data["name"] and self.creation_data["time_control"]:
            next_item = self.tree_ctrl.AppendItem(self.tree_root, "Avanti")
            self.tree_ctrl.SetItemPyData(next_item, {"action": "wizard_next"})
            
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
        dlg = VisualSettingsDialog(self, self.settings)
        if dlg.ShowModal() == wx.ID_OK:
            self.settings = dlg.get_settings()
            save_settings(self.settings)
            self.apply_theme()
            self.set_status("Impostazioni salvate ed applicate.")
        dlg.Destroy()

    def on_help(self, event):
        # Visualizza la guida accessibile
        self.main_text.Clear()
        guide_text = (
            "MANUALE GUIDA DI TORNELLO v9.0.2\n"
            "================================\n\n"
            "Tornello è strutturato in modo da permettere ad un utente non vedente di muoversi\n"
            "agilmente tra le funzioni principali tramite tasti di scelta rapida ed acceleratori.\n\n"
            "NAVIGAZIONE DI BASE:\n"
            " - Premere F5 per andare all'Area Centrale per leggere i report.\n"
            " - Premere F6 per posizionarsi sull'Albero di Destra e scorrere i tornei e i dettagli.\n"
            " - Premere F7 per focalizzare la barra di stato inferiore.\n"
            " - Usare le scorciatoie Alt + Lettera per accedere al Menu Principale in alto.\n\n"
            "RICERCA E OPERATORI NEI DATABASE (LOCALE E FIDE):\n"
            "Nelle finestre di iscrizione giocatori o consultazione FIDE, puoi inserire termini semplici\n"
            "o combinare i seguenti operatori per affinare la ricerca:\n"
            " - Spazio: I termini sono cercati in modo non esclusivo per default. Se cerchi 'simona ita',\n"
            "   Tornello troverà le giocatrici che contengono 'simona' e 'ita', ordinando prima chi le ha entrambe.\n"
            " - Operatore '+' (Obbligatorio): Il termine preceduto da '+' deve essere presente nel record.\n"
            "   Esempio: '+simona +ita' trova solo giocatrici di nome Simona della federazione italiana.\n"
            " - Operatore '-' (Escluso): Il termine preceduto da '-' non deve essere presente nel record.\n"
            "   Esempio: 'simona -ita' trova tutte le giocatrici di nome Simona che NON appartengono all'Italia.\n"
            " - Operatore '=' (Frase Esatta): Cerca la sequenza esatta dei termini separati da '='.\n"
            "   Esempio: '=gerasole=marco' trova solo i record che contengono esattamente la sequenza 'gerasole marco'.\n\n"
            "ESEMPIO COMPLESSO COMBINATO:\n"
            " Query: 'simona +ita -milano 1985'\n"
            " Spiegazione:\n"
            "  1. La giocatrice deve obbligatoriamente appartenere alla federazione italiana (+ita).\n"
            "  2. La giocatrice non deve contenere la parola 'milano' nel record (-milano).\n"
            "  3. Vengono cercate le giocatrici di nome 'simona' (termine opzionale di ricerca principale).\n"
            "  4. Se una delle Simona trovate è nata nel '1985' (termine opzionale), verrà visualizzata in cima alla lista\n"
            "     rispetto a chi è nata in altri anni, poiché soddisfa un termine opzionale in più.\n"
        )
        self.append_log(guide_text)

    def on_changelog(self, event):
        self.main_text.Clear()
        changelog = (
            "CHANGELOG TORNELLO v9.0\n"
            "=======================\n\n"
            " - Passaggio completo all'interfaccia grafica accessibile wxPython.\n"
            " - Integrazione nativa con bbpPairings v6.0.0 (motore abbinamenti FIDE 2026).\n"
            " - Formato TRF-2026 supportato nativamente.\n"
            " - Gestione avanzata del database locale giocatori direttamente tramite albero.\n"
            " - Sincronizzazione con file FIDE con modalità passo-passo o in blocco.\n"
        )
        self.append_log(changelog)

    def on_credits(self, event):
        self.main_text.Clear()
        credits_str = (
            "CREDITI DI TORNELLO\n"
            "===================\n\n"
            "Tornello è sviluppato da Gabriele Battaglia e Stella.\n"
            "Dedicato all'Associazione Scacchisti Italiani Ciechi e Ipovedenti (ASCId)\n"
            "e al gruppo di Scacchierando.\n\n"
            "Utilizza il motore di abbinamento svizzero bbpPairings di Bierema Boyz Programming.\n"
        )
        self.append_log(credits_str)

    def on_fide_query(self, event):
        from db_players import load_players_db
        players_db = load_players_db()
        from gui.dialogs.fide_query_dialog import FideQueryDialog
        dlg = FideQueryDialog(self, players_db, self.settings)
        dlg.ShowModal()
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

    def on_active_field_activated(self, item, field_active):
        from utils import format_date_locale
        
        if field_active == "name":
            dlg = wx.TextEntryDialog(self, _("Inserisci il nome del torneo:"), _("Nome Torneo"), self.current_tournament["name"])
            if dlg.ShowModal() == wx.ID_OK:
                new_val = dlg.GetValue().strip()
                self.current_tournament["name"] = new_val
                self.tree_ctrl.SetItemText(item, f"Nome torneo: {new_val}")
                self._save_state()
            dlg.Destroy()
        elif field_active == "site":
            dlg = wx.TextEntryDialog(self, _("Inserisci il luogo (Site):"), _("Luogo Torneo"), self.current_tournament["site"])
            if dlg.ShowModal() == wx.ID_OK:
                new_val = dlg.GetValue().strip()
                self.current_tournament["site"] = new_val
                self.tree_ctrl.SetItemText(item, f"Luogo (Site): {new_val}")
                self._save_state()
            dlg.Destroy()
        elif field_active == "start_date":
            dlg = wx.TextEntryDialog(self, _("Inserisci la data di inizio (AAAA-MM-GG):"), _("Data Inizio"), self.current_tournament["start_date"])
            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                try:
                    from datetime import datetime
                    datetime.strptime(val, "%Y-%m-%d")
                    self.current_tournament["start_date"] = val
                    self.tree_ctrl.SetItemText(item, f"Data inizio: {format_date_locale(val)}")
                    self._save_state()
                except ValueError:
                    wx.MessageBox(_("Formato data non valido. Usa AAAA-MM-GG."), _("Errore"), wx.ICON_ERROR)
            dlg.Destroy()
        elif field_active == "end_date":
            dlg = wx.TextEntryDialog(self, _("Inserisci la data di fine (AAAA-MM-GG):"), _("Data Fine"), self.current_tournament["end_date"])
            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                try:
                    from datetime import datetime
                    datetime.strptime(val, "%Y-%m-%d")
                    self.current_tournament["end_date"] = val
                    self.tree_ctrl.SetItemText(item, f"Data fine: {format_date_locale(val)}")
                    self._save_state()
                except ValueError:
                    wx.MessageBox(_("Formato data non valido. Usa AAAA-MM-GG."), _("Errore"), wx.ICON_ERROR)
            dlg.Destroy()
        elif field_active == "time_control":
            tc = self.current_tournament.get("time_control", {})
            tc_val = tc if isinstance(tc, str) else f"{tc.get('minutes', 60)}+{tc.get('increment', 0)}"
            dlg = wx.TextEntryDialog(self, _("Inserisci il tempo di riflessione (es. 15+10 o 90+30 o 60+0):"), _("Tempo di riflessione"), tc_val)
            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                from utils import parse_time_control, classify_tournament_category
                tc_parsed = parse_time_control(val)
                if tc_parsed:
                    self.current_tournament["time_control"] = tc_parsed
                    self.current_tournament["tournament_category"] = classify_tournament_category(tc_parsed.get("minutes", 60), tc_parsed.get("increment", 0))
                    self.tree_ctrl.SetItemText(item, f"Tempo riflessione: {val}")
                    self._save_state()
                else:
                    wx.MessageBox(_("Formato non valido. Usa minuti+incremento o solo minuti."), _("Errore"), wx.ICON_ERROR)
            dlg.Destroy()
        elif field_active == "chief_arbiter":
            dlg = wx.TextEntryDialog(self, _("Inserisci il nome dell'Arbitro Capo:"), _("Arbitro Capo"), self.current_tournament["chief_arbiter"])
            if dlg.ShowModal() == wx.ID_OK:
                new_val = dlg.GetValue().strip()
                self.current_tournament["chief_arbiter"] = new_val
                self.tree_ctrl.SetItemText(item, f"Arbitro Capo: {new_val}")
                self._save_state()
            dlg.Destroy()
        elif field_active == "deputy_chief_arbiters":
            dlg = wx.TextEntryDialog(self, _("Inserisci i collaboratori / vice arbitri (separati da virgola):"), _("Collaboratori / Vice Arbitri"), self.current_tournament.get("deputy_chief_arbiters", ""))
            if dlg.ShowModal() == wx.ID_OK:
                new_val = dlg.GetValue().strip()
                self.current_tournament["deputy_chief_arbiters"] = new_val
                self.tree_ctrl.SetItemText(item, f"Collaboratori: {new_val or 'Nessuno'}")
                self._save_state()
            dlg.Destroy()
        elif field_active == "federation_code":
            dlg = wx.TextEntryDialog(self, _("Inserisci il codice della federazione ospitante (es. ITA, FRA):"), _("Codice Federazione"), self.current_tournament["federation_code"])
            if dlg.ShowModal() == wx.ID_OK:
                new_val = dlg.GetValue().strip().upper()
                self.current_tournament["federation_code"] = new_val
                self.tree_ctrl.SetItemText(item, f"Codice Federazione: {new_val}")
                self._save_state()
            dlg.Destroy()
        elif field_active == "color_board1":
            choices = ["Bianco", "Nero", "Casuale"]
            dlg = wx.SingleChoiceDialog(self, _("Seleziona il colore per il giocatore più forte (scacchiera 1, turno 1):"), _("Colore al giocatore più forte"), choices)
            curr_raw = self.current_tournament.get("initial_board1_color_setting", "white1")
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
                self.current_tournament["initial_board1_color_setting"] = val_raw
                col_disp = choices[sel]
                self.tree_ctrl.SetItemText(item, f"Colore al giocatore più forte: {col_disp}")
                self._save_state()
            dlg.Destroy()
        elif field_active == "bye_value":
            choices = ["0.0", "0.5", "1.0"]
            dlg = wx.SingleChoiceDialog(self, _("Seleziona il valore del BYE secondo la regola FIDE:"), _("Valore del BYE"), choices)
            curr_str = str(self.current_tournament.get("bye_value", 1.0))
            if curr_str in choices:
                dlg.SetSelection(choices.index(curr_str))
            if dlg.ShowModal() == wx.ID_OK:
                new_val = float(dlg.GetStringSelection())
                self.current_tournament["bye_value"] = new_val
                self.tree_ctrl.SetItemText(item, f"Valore del BYE: {new_val}")
                self._save_state()
            dlg.Destroy()

    def on_activate_match(self, match):
        w_id = match.get("white_player_id")
        b_id = match.get("black_player_id")
        if not b_id or b_id == "BYE_PLAYER_ID":
            wx.MessageBox(_("La partita con BYE non richiede inserimento risultati."), _("Info"), wx.ICON_INFORMATION)
            return
            
        players_dict = self.current_tournament.get("players_dict", {})
        w_p = players_dict.get(w_id, {})
        b_p = players_dict.get(b_id, {})
        
        w_name = f"{w_p.get('last_name', '')} {w_p.get('first_name', '')}".strip()
        b_name = f"{b_p.get('last_name', '')} {b_p.get('first_name', '')}".strip()
        
        from gui.dialogs.result_dialog import ResultDialog
        dlg = ResultDialog(
            self,
            white_name=w_name,
            black_name=b_name,
            white_id=w_id,
            black_id=b_id,
            board_num=match.get("board", 1),
            current_result=match.get("result"),
            schedule_info=match.get("schedule_info"),
            settings=self.settings
        )
        
        if dlg.ShowModal() == wx.ID_OK:
            from utils import format_date_locale
            if dlg.selected_action == "schedule":
                match["is_scheduled"] = True
                match["schedule_info"] = dlg.schedule_info
                self._save_state()
                self.set_status(_("Partita pianificata per il {date} alle {time}.").format(
                    date=format_date_locale(dlg.schedule_info["date"]),
                    time=dlg.schedule_info["time"]
                ))
            elif dlg.selected_action == "withdraw":
                self.withdraw_player(dlg.withdrawn_player_id)
            else:
                res = dlg.get_selected_result()
                if res:
                    self.apply_match_result(match, res)
                    self.set_status(_("Risultato registrato: {res}.").format(res=res))
            
            # Rebuild tree with focus restoration on the "Partite" category
            self.last_activated_action = "show_matches"
            self.populate_tree()
            
        dlg.Destroy()

    def apply_match_result(self, match, result_str):
        result_map = {
            "1-0": (1.0, 0.0),
            "0-1": (0.0, 1.0),
            "1/2-1/2": (0.5, 0.5),
            "1-F": (1.0, 0.0),
            "F-1": (0.0, 1.0),
            "0-0F": (0.0, 0.0),
        }
        w_score, b_score = result_map.get(result_str, (0.0, 0.0))
        
        curr_round = self.current_tournament.get("current_round", 1)
        wp_id = match.get("white_player_id")
        bp_id = match.get("black_player_id")
        
        players_dict = self.current_tournament.get("players_dict", {})
        wp = players_dict.get(wp_id)
        bp = players_dict.get(bp_id)
        
        if wp:
            wp["results_history"] = [h for h in wp.get("results_history", []) if h.get("round") != curr_round]
        if bp:
            bp["results_history"] = [h for h in bp.get("results_history", []) if h.get("round") != curr_round]
            
        from tournament import _apply_match_result_to_players, ricalcola_punti_tutti_giocatori
        _apply_match_result_to_players(self.current_tournament, match, result_str, w_score, b_score)
        ricalcola_punti_tutti_giocatori(self.current_tournament)
        
        if "F" in result_str:
            forfeiting_name = f"{bp['first_name']} {bp['last_name']}" if result_str == "1-F" else (f"{wp['first_name']} {wp['last_name']}" if result_str == "F-1" else None)
            forfeiting_id = bp_id if result_str == "1-F" else (wp_id if result_str == "F-1" else None)
            
            if forfeiting_name:
                msg = _("Il giocatore {name} si ritira definitivamente dal torneo?").format(name=forfeiting_name)
                dlg = AccessibleMsgDialog(self, _("Ritiro dopo Forfait"), msg, style=wx.YES_NO)
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
            self.set_status(_("Giocatore '{name}' ritirato con successo.").format(name=p_name))

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
            opp_name = f"{opp_p.get('last_name', '')} {opp_p.get('first_name', '')}".strip() if opp_id != "BYE_PLAYER_ID" else "BYE"
            report += f"  Turno {entry.get('round')}: vs {opp_name} ({entry.get('color', 'N/D')}) -> Risultato: {entry.get('result')} (Punti: {entry.get('score')})\n"
            
        self.append_log(report)
        self.set_status(_("Visualizzazione scheda di {name}.").format(name=p_name))

    def start_tournament_matchmaking(self):
        from tournament import generate_pairings_for_round
        matches = generate_pairings_for_round(self.current_tournament)
        if matches is None:
            wx.MessageBox(_("Errore nella generazione degli abbinamenti."), _("Errore"), wx.ICON_ERROR)
            return
            
        from models import Round, Match
        round_obj = Round(round=1, matches=[Match.from_dict(m) for m in matches])
        self.current_tournament.setdefault("rounds", []).append(round_obj.to_dict())
        self._save_state()
        
        self.populate_tree()
        self.set_status(_("Torneo iniziato. Generati abbinamenti per il Turno 1."))

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
