import os
import json
import wx
import builtins
from config import FIDE_DB_LOCAL_FILE
from gui.settings import apply_visual_settings

_ = getattr(builtins, "_", lambda s: s)

class PlayerEnrollmentDialog(wx.Dialog):
    """
    Finestra di dialogo modale per l'iscrizione dei giocatori al torneo.
    Fornisce ricerca in tempo reale sia nel DB personale locale che nel DB FIDE,
    con la possibilità di aggiungere o rimuovere partecipanti.
    """
    def __init__(self, parent, players_db, enrolled_players, settings):
        title = _("Iscrizione Giocatori")
        super().__init__(parent, title=title, size=(900, 650), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
        self.settings = settings
        self.players_db = players_db
        # Facciamo una copia dei giocatori iscritti per gestire l'annullamento
        self.enrolled_players = list(enrolled_players)
        
        # Carica il database FIDE locale in memoria per ricerche istantanee senza IO
        self.fide_db = {}
        if os.path.exists(FIDE_DB_LOCAL_FILE):
            try:
                with open(FIDE_DB_LOCAL_FILE, "r", encoding="utf-8") as f:
                    self.fide_db = json.load(f)
            except Exception:
                pass
                
        self._init_ui()
        self.apply_theme()
        
        # Inizializza le liste
        self.update_enrolled_list()
        self.on_search_local_changed(None)
        self.on_search_fide_changed(None)
        
        self.Centre()

    def _init_ui(self):
        panel = wx.Panel(self)
        main_hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        # --- COLONNA SINISTRA: RICERCA (Locali + FIDE) ---
        left_vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Sezione 1: DB Locale
        sb_local = wx.StaticBox(panel, label=_("Ricerca nel Database Personale Locale"))
        sbs_local = wx.StaticBoxSizer(sb_local, wx.VERTICAL)
        
        self.search_local = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_local.Bind(wx.EVT_TEXT, self.on_search_local_changed)
        sbs_local.Add(self.search_local, 0, wx.EXPAND | wx.ALL, 5)
        
        self.list_local_results = wx.ListBox(panel, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.list_local_results.Bind(wx.EVT_LISTBOX_DCLICK, self.on_add_local)
        self.list_local_results.Bind(wx.EVT_CHAR_HOOK, self.on_local_key)
        sbs_local.Add(self.list_local_results, 1, wx.EXPAND | wx.ALL, 5)
        
        left_vbox.Add(sbs_local, 1, wx.EXPAND | wx.ALL, 5)
        
        # Sezione 2: DB FIDE
        sb_fide = wx.StaticBox(panel, label=_("Ricerca nel Database FIDE (min. 3 caratteri)"))
        sbs_fide = wx.StaticBoxSizer(sb_fide, wx.VERTICAL)
        
        self.search_fide = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_fide.Bind(wx.EVT_TEXT, self.on_search_fide_changed)
        sbs_fide.Add(self.search_fide, 0, wx.EXPAND | wx.ALL, 5)
        
        self.list_fide_results = wx.ListBox(panel, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.list_fide_results.Bind(wx.EVT_LISTBOX_DCLICK, self.on_add_fide)
        self.list_fide_results.Bind(wx.EVT_CHAR_HOOK, self.on_fide_key)
        sbs_fide.Add(self.list_fide_results, 1, wx.EXPAND | wx.ALL, 5)
        
        left_vbox.Add(sbs_fide, 1, wx.EXPAND | wx.ALL, 5)
        
        main_hbox.Add(left_vbox, 1, wx.EXPAND)
        
        # --- COLONNA DESTRA: ISCRITTI ---
        right_vbox = wx.BoxSizer(wx.VERTICAL)
        
        sb_enrolled = wx.StaticBox(panel, label=_("Giocatori Iscritti al Torneo"))
        sbs_enrolled = wx.StaticBoxSizer(sb_enrolled, wx.VERTICAL)
        
        self.list_enrolled = wx.ListBox(panel, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.list_enrolled.Bind(wx.EVT_LISTBOX_DCLICK, self.on_remove_enrolled)
        self.list_enrolled.Bind(wx.EVT_CHAR_HOOK, self.on_enrolled_key)
        sbs_enrolled.Add(self.list_enrolled, 1, wx.EXPAND | wx.ALL, 5)
        
        # Bottoni OK/Annulla posizionati in fondo alla colonna destra
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("Annulla"))
        btn_ok = wx.Button(panel, wx.ID_OK, _("OK"))
        btn_ok.SetDefault()
        
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, 10)
        btn_sizer.Add(btn_ok, 0)
        sbs_enrolled.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.TOP | wx.BOTTOM, 5)
        
        right_vbox.Add(sbs_enrolled, 1, wx.EXPAND | wx.ALL, 5)
        
        main_hbox.Add(right_vbox, 1, wx.EXPAND)
        
        panel.SetSizer(main_hbox)
        main_hbox.Fit(self)

    def apply_theme(self):
        apply_visual_settings(self.search_local, self.settings)
        apply_visual_settings(self.list_local_results, self.settings)
        apply_visual_settings(self.search_fide, self.settings)
        apply_visual_settings(self.list_fide_results, self.settings)
        apply_visual_settings(self.list_enrolled, self.settings)

    def update_enrolled_list(self):
        """Aggiorna il contenuto della lista dei giocatori iscritti."""
        self.list_enrolled.Clear()
        self.enrolled_data_map = []
        
        for idx, p in enumerate(self.enrolled_players):
            name = f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
            elo = p.get("current_elo") or p.get("elo_standard") or 1399
            p_id = p.get("id") or p.get("fide_id_num_str") or "N/D"
            label = f"{name} (ELO: {elo} - ID: {p_id})"
            self.list_enrolled.Append(label)
            self.enrolled_data_map.append(p)

    def on_search_local_changed(self, event):
        """Filtra e aggiorna i risultati del DB locale."""
        query = self.search_local.GetValue().strip().lower()
        search_terms = query.split()
        
        self.list_local_results.Clear()
        self.local_results_map = []
        
        # Mappa per escludere omonimi già iscritti
        enrolled_ids = {p.get("id") for p in self.enrolled_players if p.get("id")}
        
        for p_id, p in self.players_db.items():
            if p_id in enrolled_ids:
                continue
                
            full_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".lower()
            if not search_terms or all(t in full_name for t in search_terms):
                name = f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
                elo = p.get("current_elo", 1399)
                label = f"{name} (ELO: {elo} - ID: {p_id})"
                self.list_local_results.Append(label)
                self.local_results_map.append(p)

    def on_search_fide_changed(self, event):
        """Filtra e aggiorna i risultati del DB FIDE."""
        query = self.search_fide.GetValue().strip().lower()
        self.list_fide_results.Clear()
        self.fide_results_map = []
        
        if len(query) < 3:
            return
            
        search_terms = query.split()
        search_is_id = query.isdigit()
        
        enrolled_fide_ids = {p.get("fide_id_num_str") for p in self.enrolled_players if p.get("fide_id_num_str")}
        
        # Ricerca per ID FIDE esatto
        if search_is_id and query in self.fide_db:
            p = self.fide_db[query]
            fide_id_str = str(p.get("id_fide"))
            if fide_id_str not in enrolled_fide_ids:
                name = f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
                elo = p.get("elo_standard", 0)
                label = f"{name} (ELO FIDE: {elo} - ID FIDE: {fide_id_str})"
                self.list_fide_results.Append(label)
                self.fide_results_map.append(p)
            return
            
        # Ricerca testuale
        count = 0
        for fide_id, p in self.fide_db.items():
            if fide_id in enrolled_fide_ids:
                continue
                
            full_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".lower()
            if all(t in full_name for t in search_terms):
                name = f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
                elo = p.get("elo_standard", 0)
                label = f"{name} (ELO FIDE: {elo} - ID FIDE: {fide_id})"
                self.list_fide_results.Append(label)
                self.fide_results_map.append(p)
                count += 1
                if count >= 100:  # Cap a 100 risultati per reattività
                    break

    def on_add_local(self, event):
        sel = self.list_local_results.GetSelection()
        if sel == wx.NOT_FOUND:
            return
            
        player_data = self.local_results_map[sel]
        self.enrolled_players.append(player_data)
        
        self.update_enrolled_list()
        self.on_search_local_changed(None)
        
        # Seleziona l'ultimo aggiunto per feedback acustico/visivo
        self.list_enrolled.SetSelection(self.list_enrolled.GetCount() - 1)

    def on_add_fide(self, event):
        sel = self.list_fide_results.GetSelection()
        if sel == wx.NOT_FOUND:
            return
            
        fide_player = self.fide_results_map[sel]
        
        # Mappa il giocatore FIDE nello schema giocatore di Tornello
        new_player = {
            "id": f"FIDE_{fide_player.get('id_fide')}",
            "first_name": fide_player.get("first_name", ""),
            "last_name": fide_player.get("last_name", ""),
            "current_elo": fide_player.get("elo_standard") or 1399,
            "fide_id_num_str": str(fide_player.get("id_fide")),
            "birth_date": f"{fide_player.get('birth_year', 1980)}-01-01",
            "gender": fide_player.get("sex", "M"),
            "federation": fide_player.get("federation", "ITA"),
            "fide_title": fide_player.get("title", "")
        }
        
        self.enrolled_players.append(new_player)
        self.update_enrolled_list()
        self.on_search_fide_changed(None)
        
        # Seleziona l'ultimo aggiunto
        self.list_enrolled.SetSelection(self.list_enrolled.GetCount() - 1)

    def on_remove_enrolled(self, event):
        sel = self.list_enrolled.GetSelection()
        if sel == wx.NOT_FOUND:
            return
            
        player_data = self.enrolled_data_map[sel]
        self.enrolled_players.remove(player_data)
        
        self.update_enrolled_list()
        self.on_search_local_changed(None)
        self.on_search_fide_changed(None)

    def on_local_key(self, event):
        key_code = event.GetKeyCode()
        if key_code == wx.WXK_RETURN:
            self.on_add_local(None)
        else:
            event.Skip()

    def on_fide_key(self, event):
        key_code = event.GetKeyCode()
        if key_code == wx.WXK_RETURN:
            self.on_add_fide(None)
        else:
            event.Skip()

    def on_enrolled_key(self, event):
        key_code = event.GetKeyCode()
        if key_code == wx.WXK_RETURN or key_code == wx.WXK_DELETE:
            self.on_remove_enrolled(None)
        else:
            event.Skip()

    def get_enrolled_players(self):
        return self.enrolled_players
