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
            f"Tornello v9.0 - Gestione Tornei di Scacchi Accessibile\n"
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
        closed_item = self.tree_ctrl.AppendItem(self.tree_root, "📁 Tornei Conclusi")
        closed_files = glob.glob(os.path.join("Closed Tournaments", "Tornello - *.json"))
        for f in closed_files:
            try:
                with open(f, "r", encoding="utf-8") as f_in:
                    data = json.load(f_in)
                t_name = data.get("name", os.path.basename(f))
                label = f"{t_name} (Concluso)"
                item = self.tree_ctrl.AppendItem(closed_item, label)
                self.tree_ctrl.SetItemPyData(item, {"action": "load_concluded", "filepath": f})
            except Exception:
                pass
                
        # 3. Nuovo Torneo
        new_item = self.tree_ctrl.AppendItem(self.tree_root, "⭐ Nuovo torneo")
        self.tree_ctrl.SetItemPyData(new_item, {"action": "start_new_tournament"})

    def populate_tree_with_tournament(self):
        t_name = self.current_tournament.get("name", "Torneo")
        root_item = self.tree_ctrl.AppendItem(self.tree_root, t_name)
        
        # Dati
        dati_item = self.tree_ctrl.AppendItem(root_item, "📁 Dati")
        self.tree_ctrl.SetItemPyData(dati_item, {"action": "show_data"})
        
        # Partecipanti
        part_item = self.tree_ctrl.AppendItem(root_item, "📁 Partecipanti")
        self.tree_ctrl.SetItemPyData(part_item, {"action": "show_players"})
        
        # Partite
        partite_item = self.tree_ctrl.AppendItem(root_item, "📁 Partite")
        self.tree_ctrl.SetItemPyData(partite_item, {"action": "show_matches"})
        
        # Inizia torneo (se applicabile)
        is_started = len(self.current_tournament.get("rounds", [])) > 0
        if not is_started:
            start_item = self.tree_ctrl.AppendItem(root_item, "🏁 Inizia torneo")
            self.tree_ctrl.SetItemPyData(start_item, {"action": "start_tournament_matchmaking"})
            
        self.tree_ctrl.Expand(root_item)

    def on_tree_item_activated(self, event):
        item = event.GetItem()
        data = self.tree_ctrl.GetItemPyData(item)
        if not data:
            return
            
        field = data.get("field")
        if field:
            self.on_wizard_field_activated(field)
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

    def on_wizard_field_activated(self, field):
        if field == "name":
            dlg = wx.TextEntryDialog(self, _("Inserisci il nome del torneo:"), _("Nome Torneo"), self.creation_data["name"])
            if dlg.ShowModal() == wx.ID_OK:
                self.creation_data["name"] = dlg.GetValue().strip()
            dlg.Destroy()
        elif field == "site":
            dlg = wx.TextEntryDialog(self, _("Inserisci il luogo (Site):"), _("Luogo Torneo"), self.creation_data["site"])
            if dlg.ShowModal() == wx.ID_OK:
                self.creation_data["site"] = dlg.GetValue().strip()
            dlg.Destroy()
        elif field == "rounds":
            dlg = wx.TextEntryDialog(self, _("Inserisci il numero di turni:"), _("Numero Turni"), str(self.creation_data["rounds"]))
            if dlg.ShowModal() == wx.ID_OK:
                val = dlg.GetValue().strip()
                if val.isdigit():
                    self.creation_data["rounds"] = int(val)
                else:
                    wx.MessageBox(_("Inserisci un numero intero valido."), _("Errore"), wx.ICON_ERROR)
            dlg.Destroy()
        elif field == "time_control":
            dlg = wx.TextEntryDialog(self, _("Inserisci il tempo di riflessione (es. 15+10 o 90+30):"), _("Tempo di riflessione"), self.creation_data["time_control"])
            if dlg.ShowModal() == wx.ID_OK:
                self.creation_data["time_control"] = dlg.GetValue().strip()
            dlg.Destroy()
        elif field == "save_path":
            dlg = wx.DirDialog(self, _("Seleziona la cartella di salvataggio per i report:"), self.creation_data["save_path"])
            if dlg.ShowModal() == wx.ID_OK:
                self.creation_data["save_path"] = dlg.GetPath()
            dlg.Destroy()
            
        self.populate_new_tournament_wizard_tree()

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

    def create_tournament_from_wizard(self, enrolled):
        from models import Tournament, Player
        from tournament import generate_pairings_for_round
        from utils import sanitize_filename
        
        players = []
        for p in enrolled:
            players.append(Player.from_dict(p))
            
        from datetime import datetime
        from config import DATE_FORMAT_ISO
        oggi = datetime.now().strftime(DATE_FORMAT_ISO)
        
        save_dir = self.creation_data["save_path"]
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                wx.MessageBox(f"Impossibile creare la cartella di salvataggio: {e}", "Errore", wx.ICON_ERROR)
                return
                
        sanitized = sanitize_filename(self.creation_data["name"])
        self.active_filename = f"Tornello - {sanitized}.json"
        
        t_dict = {
            "name": self.creation_data["name"],
            "tournament_id": sanitized.upper(),
            "site": self.creation_data["site"] or "N/D",
            "start_date": oggi,
            "end_date": oggi,
            "total_rounds": self.creation_data["rounds"],
            "current_round": 1,
            "time_control": self.creation_data["time_control"],
            "players": [p.to_dict() for p in players],
            "rounds": [],
            "custom_save_path": save_dir,
            "save_path": save_dir
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
        self.creation_mode = True
        self.creation_data = {
            "name": "",
            "site": "",
            "rounds": 5,
            "time_control": "15+10",
            "save_path": os.path.abspath("."),
            "arbiter": "",
            "deputies": "",
            "color_board1": "white1"
        }
        self.populate_new_tournament_wizard_tree()

    def populate_new_tournament_wizard_tree(self):
        self.tree_ctrl.DeleteAllItems()
        self.tree_root = self.tree_ctrl.AddRoot("Nuovo Torneo")
        
        name_val = self.creation_data["name"] or "Non impostato"
        site_val = self.creation_data["site"] or "Non impostato"
        rounds_val = str(self.creation_data["rounds"])
        tc_val = self.creation_data["time_control"] or "Non impostato"
        path_val = self.creation_data["save_path"]
        
        self.tree_name = self.tree_ctrl.AppendItem(self.tree_root, f"Nome torneo: {name_val}")
        self.tree_ctrl.SetItemPyData(self.tree_name, {"field": "name"})
        
        self.tree_site = self.tree_ctrl.AppendItem(self.tree_root, f"Luogo (Site): {site_val}")
        self.tree_ctrl.SetItemPyData(self.tree_site, {"field": "site"})
        
        self.tree_rounds = self.tree_ctrl.AppendItem(self.tree_root, f"Numero turni: {rounds_val}")
        self.tree_ctrl.SetItemPyData(self.tree_rounds, {"field": "rounds"})
        
        self.tree_tc = self.tree_ctrl.AppendItem(self.tree_root, f"Tempo riflessione: {tc_val}")
        self.tree_ctrl.SetItemPyData(self.tree_tc, {"field": "time_control"})
        
        self.tree_path = self.tree_ctrl.AppendItem(self.tree_root, f"Cartella di salvataggio: {path_val}")
        self.tree_ctrl.SetItemPyData(self.tree_path, {"field": "save_path"})
        
        # Verifica se i campi obbligatori sono validati per mostrare "Avanti"
        if self.creation_data["name"] and self.creation_data["time_control"]:
            next_item = self.tree_ctrl.AppendItem(self.tree_root, "👉 Avanti")
            self.tree_ctrl.SetItemPyData(next_item, {"action": "wizard_next"})
            
        self.tree_ctrl.Expand(self.tree_root)

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
            "MANUALE GUIDA DI TORNELLO v9.0\n"
            "==============================\n\n"
            "Tornello è strutturato in modo da permettere ad un utente non vedente di muoversi\n"
            "agilmente tra le funzioni principali tramite tasti di scelta rapida ed acceleratori.\n\n"
            "NAVIGAZIONE DI BASE:\n"
            " - Premere F5 per andare all'Area Centrale per leggere i report.\n"
            " - Premere F6 per posizionarsi sull'Albero di Destra e scorrere i tornei e i dettagli.\n"
            " - Premere F7 per focalizzare la barra di stato inferiore.\n"
            " - Usare le scorciatoie Alt + Lettera per accedere al Menu Principale in alto.\n"
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
