import wx
import builtins
from db_players import load_players_db, save_players_db, generate_player_id
from gui.settings import apply_visual_settings
from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog
from utils import play_sound

_ = getattr(builtins, "_", lambda s: s)


class PlayersDbDialog(wx.Dialog):
    """
    Finestra di dialogo per la gestione del Database Giocatori Locale.
    Usa un albero interattivo ed accessibile a destra e una lista con filtri a sinistra.
    """

    def __init__(self, parent, settings):
        title = _("Gestione Database Giocatori Locale")
        super().__init__(
            parent,
            title=title,
            size=(900, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.settings = settings
        self.players_db = load_players_db()
        self.selected_player_id = None

        self._init_ui()
        self.apply_theme()

        self.on_search_changed(None)
        self.Centre()

    def _init_ui(self):
        panel = wx.Panel(self)
        main_hbox = wx.BoxSizer(wx.HORIZONTAL)

        # --- COLONNA SINISTRA: RICERCA E LISTA ---
        left_vbox = wx.BoxSizer(wx.VERTICAL)

        left_vbox.Add(wx.StaticText(panel, label=_("Filtra Giocatori:")), 0, wx.ALL, 5)
        self.search_input = wx.TextCtrl(panel)
        self.search_input.Bind(wx.EVT_TEXT, self.on_search_changed)
        left_vbox.Add(self.search_input, 0, wx.EXPAND | wx.ALL, 5)

        self.list_players = wx.ListBox(panel, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.list_players.Bind(wx.EVT_LISTBOX, self.on_player_selected)
        left_vbox.Add(self.list_players, 1, wx.EXPAND | wx.ALL, 5)

        btn_add = wx.Button(panel, label=_("Aggiungi Nuovo Giocatore"))
        btn_add.Bind(wx.EVT_BUTTON, self.on_add_player)
        left_vbox.Add(btn_add, 0, wx.EXPAND | wx.ALL, 5)

        main_hbox.Add(left_vbox, 1, wx.EXPAND | wx.ALL, 5)

        # --- COLONNA DESTRA: ALBERO GESTIONE DATI ---
        right_vbox = wx.BoxSizer(wx.VERTICAL)
        right_vbox.Add(
            wx.StaticText(
                panel,
                label=_("Scheda ed Albero Dati (Invio = Modifica | Canc = Elimina):"),
            ),
            0,
            wx.ALL,
            5,
        )

        self.tree_ctrl = wx.TreeCtrl(panel, style=wx.TR_DEFAULT_STYLE | wx.TR_HIDE_ROOT)
        self.tree_ctrl.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self.on_tree_item_activated)
        self.tree_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_tree_key_down)
        right_vbox.Add(self.tree_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        btn_close = wx.Button(panel, wx.ID_CANCEL, _("Chiudi"))
        right_vbox.Add(btn_close, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        main_hbox.Add(right_vbox, 2, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(main_hbox)
        main_hbox.Fit(self)

    def apply_theme(self):
        apply_visual_settings(self.search_input, self.settings)
        apply_visual_settings(self.list_players, self.settings)
        apply_visual_settings(self.tree_ctrl, self.settings)

    def on_search_changed(self, event):
        query = self.search_input.GetValue().strip().lower()
        search_terms = query.split()

        self.list_players.Clear()
        self.players_map = []

        matching = []
        for p_id, p in self.players_db.items():
            full_name = f"{p.get('first_name', '')} {p.get('last_name', '')}".lower()
            if not search_terms or all(t in full_name for t in search_terms):
                matching.append((p_id, p))

        # Ordina per ELO decrescente
        matching_sorted = sorted(
            matching, key=lambda item: item[1].get("current_elo", 1399), reverse=True
        )

        for p_id, p in matching_sorted:
            name = f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
            elo_std = p.get("current_elo", 1399)
            elo_rap = p.get("elo_rapid", 0)
            label = f"{name} (Std: {elo_std}, Rap: {elo_rap} - ID: {p_id})"
            self.list_players.Append(label)
            self.players_map.append(p_id)

        if self.players_map:
            self.list_players.SetSelection(0)
            self.on_player_selected(None)
        else:
            self.tree_ctrl.DeleteAllItems()
            self.selected_player_id = None

    def on_player_selected(self, event):
        sel = self.list_players.GetSelection()
        if sel == wx.NOT_FOUND:
            self.tree_ctrl.DeleteAllItems()
            self.selected_player_id = None
            return

        self.selected_player_id = self.players_map[sel]
        self.populate_player_tree()

    def populate_player_tree(self):
        self.tree_ctrl.DeleteAllItems()
        if not self.selected_player_id:
            return

        p = self.players_db[self.selected_player_id]
        self.tree_root = self.tree_ctrl.AddRoot("Root")

        # Radice Visibile
        p_name = f"{p.get('last_name', '')} {p.get('first_name', '')}".strip() or _(
            "Senza Nome"
        )
        root_node = self.tree_ctrl.AppendItem(self.tree_root, p_name)
        self.tree_ctrl.SetItemPyData(root_node, {"type": "player_root"})

        # 1. Anagrafica
        node_bio = self.tree_ctrl.AppendItem(root_node, _("Anagrafica"))

        item_ln = self.tree_ctrl.AppendItem(
            node_bio, _("Cognome: {}").format(p.get("last_name", ""))
        )
        self.tree_ctrl.SetItemPyData(item_ln, {"type": "field", "key": "last_name"})

        item_fn = self.tree_ctrl.AppendItem(
            node_bio, _("Nome: {}").format(p.get("first_name", ""))
        )
        self.tree_ctrl.SetItemPyData(item_fn, {"type": "field", "key": "first_name"})

        raw_sex = p.get("sex") or p.get("gender") or "M"
        sex_display = "W" if str(raw_sex).strip().lower() in ("w", "f") else "M"
        item_gd = self.tree_ctrl.AppendItem(
            node_bio, _("Sesso: {}").format(sex_display)
        )
        self.tree_ctrl.SetItemPyData(item_gd, {"type": "field", "key": "sex"})

        item_bd = self.tree_ctrl.AppendItem(
            node_bio, _("Anno Nascita: {}").format(p.get("birth_date", _("N/D")))
        )
        self.tree_ctrl.SetItemPyData(item_bd, {"type": "field", "key": "birth_date"})

        item_fed = self.tree_ctrl.AppendItem(
            node_bio, _("Nazione (FED): {}").format(p.get("federation", "ITA"))
        )
        self.tree_ctrl.SetItemPyData(item_fed, {"type": "field", "key": "federation"})

        item_club = self.tree_ctrl.AppendItem(
            node_bio, _("Club/Società: {}").format(p.get("club", ""))
        )
        self.tree_ctrl.SetItemPyData(item_club, {"type": "field", "key": "club"})

        item_gp = self.tree_ctrl.AppendItem(
            node_bio, _("Partite Locali Giocate: {}").format(p.get("games_played", 0))
        )
        self.tree_ctrl.SetItemPyData(
            item_gp, {"type": "field", "key": "games_played", "is_int": True}
        )

        item_reg = self.tree_ctrl.AppendItem(
            node_bio, _("Data Registrazione: {}").format(p.get("registration_date", ""))
        )
        self.tree_ctrl.SetItemPyData(
            item_reg, {"type": "field", "key": "registration_date"}
        )

        # 2. ELO
        node_elo = self.tree_ctrl.AppendItem(root_node, _("ELO e Titoli"))

        elo_std_val = p.get("current_elo")
        elo_std = int(float(elo_std_val)) if elo_std_val is not None else 1399
        item_elo_std = self.tree_ctrl.AppendItem(
            node_elo, _("ELO Standard: {}").format(elo_std)
        )
        self.tree_ctrl.SetItemPyData(
            item_elo_std, {"type": "field", "key": "current_elo", "is_int": True}
        )

        elo_rap_val = p.get("elo_rapid")
        elo_rap = int(float(elo_rap_val)) if elo_rap_val is not None else 0
        item_elo_rap = self.tree_ctrl.AppendItem(
            node_elo, _("ELO Rapid: {}").format(elo_rap)
        )
        self.tree_ctrl.SetItemPyData(
            item_elo_rap, {"type": "field", "key": "elo_rapid", "is_int": True}
        )

        elo_blz_val = p.get("elo_blitz")
        elo_blz = int(float(elo_blz_val)) if elo_blz_val is not None else 0
        item_elo_blz = self.tree_ctrl.AppendItem(
            node_elo, _("ELO Blitz: {}").format(elo_blz)
        )
        self.tree_ctrl.SetItemPyData(
            item_elo_blz, {"type": "field", "key": "elo_blitz", "is_int": True}
        )

        item_title = self.tree_ctrl.AppendItem(
            node_elo, _("Titolo FIDE: {}").format(p.get("fide_title", ""))
        )
        self.tree_ctrl.SetItemPyData(item_title, {"type": "field", "key": "fide_title"})

        item_fid = self.tree_ctrl.AppendItem(
            node_elo, _("ID FIDE: {}").format(p.get("fide_id_num_str", ""))
        )
        self.tree_ctrl.SetItemPyData(
            item_fid, {"type": "field", "key": "fide_id_num_str"}
        )

        k_std = p.get("fide_k_factor")
        k_std_str = str(k_std) if k_std is not None else ""
        item_k_std = self.tree_ctrl.AppendItem(
            node_elo, _("FIDE Standard K: {}").format(k_std_str)
        )
        self.tree_ctrl.SetItemPyData(
            item_k_std, {"type": "field", "key": "fide_k_factor", "is_int": True}
        )

        g_std = p.get("fide_standard_games", 0)
        item_g_std = self.tree_ctrl.AppendItem(
            node_elo, _("Partite FIDE Standard: {}").format(g_std)
        )
        self.tree_ctrl.SetItemPyData(
            item_g_std, {"type": "field", "key": "fide_standard_games", "is_int": True}
        )

        k_rap = p.get("fide_rapid_k")
        k_rap_str = str(k_rap) if k_rap is not None else ""
        item_k_rap = self.tree_ctrl.AppendItem(
            node_elo, _("FIDE Rapid K: {}").format(k_rap_str)
        )
        self.tree_ctrl.SetItemPyData(
            item_k_rap, {"type": "field", "key": "fide_rapid_k", "is_int": True}
        )

        g_rap = p.get("fide_rapid_games", 0)
        item_g_rap = self.tree_ctrl.AppendItem(
            node_elo, _("Partite FIDE Rapid: {}").format(g_rap)
        )
        self.tree_ctrl.SetItemPyData(
            item_g_rap, {"type": "field", "key": "fide_rapid_games", "is_int": True}
        )

        k_blz = p.get("fide_blitz_k")
        k_blz_str = str(k_blz) if k_blz is not None else ""
        item_k_blz = self.tree_ctrl.AppendItem(
            node_elo, _("FIDE Blitz K: {}").format(k_blz_str)
        )
        self.tree_ctrl.SetItemPyData(
            item_k_blz, {"type": "field", "key": "fide_blitz_k", "is_int": True}
        )

        g_blz = p.get("fide_blitz_games", 0)
        item_g_blz = self.tree_ctrl.AppendItem(
            node_elo, _("Partite FIDE Blitz: {}").format(g_blz)
        )
        self.tree_ctrl.SetItemPyData(
            item_g_blz, {"type": "field", "key": "fide_blitz_games", "is_int": True}
        )

        item_w_title = self.tree_ctrl.AppendItem(
            node_elo, _("Titolo Femminile: {}").format(p.get("w_title", ""))
        )
        self.tree_ctrl.SetItemPyData(item_w_title, {"type": "field", "key": "w_title"})

        item_o_title = self.tree_ctrl.AppendItem(
            node_elo, _("Titolo Arbitro/Altro: {}").format(p.get("o_title", ""))
        )
        self.tree_ctrl.SetItemPyData(item_o_title, {"type": "field", "key": "o_title"})

        item_foa_title = self.tree_ctrl.AppendItem(
            node_elo, _("Titolo FOA: {}").format(p.get("foa_title", ""))
        )
        self.tree_ctrl.SetItemPyData(
            item_foa_title, {"type": "field", "key": "foa_title"}
        )

        item_flag = self.tree_ctrl.AppendItem(
            node_elo, _("Flag (Caratteristica): {}").format(p.get("flag", ""))
        )
        self.tree_ctrl.SetItemPyData(item_flag, {"type": "field", "key": "flag"})

        # 3. Storico Tornei
        node_hist = self.tree_ctrl.AppendItem(root_node, _("Storico Tornei"))
        history = p.get("tournaments_played", [])
        for idx, entry in enumerate(history):
            label = _("{}: Pos. {}/{} ({})").format(
                entry.get("tournament_name", _("Torneo")),
                entry.get("rank", _("N/D")),
                entry.get("total_players", _("N/D")),
                entry.get("date_completed", _("N/D")),
            )
            item_h = self.tree_ctrl.AppendItem(node_hist, label)
            self.tree_ctrl.SetItemPyData(
                item_h, {"type": "history_record", "index": idx}
            )

        # 4. Medagliere
        node_med = self.tree_ctrl.AppendItem(root_node, _("Medagliere"))
        medals = p.get("medals", {})

        item_g = self.tree_ctrl.AppendItem(
            node_med, _("Ori (Oro): {}").format(medals.get("gold", 0))
        )
        self.tree_ctrl.SetItemPyData(
            item_g, {"type": "field", "key_nested": ("medals", "gold"), "is_int": True}
        )

        item_s = self.tree_ctrl.AppendItem(
            node_med, _("Argenti (Argento): {}").format(medals.get("silver", 0))
        )
        self.tree_ctrl.SetItemPyData(
            item_s,
            {"type": "field", "key_nested": ("medals", "silver"), "is_int": True},
        )

        item_b = self.tree_ctrl.AppendItem(
            node_med, _("Bronzi (Bronzo): {}").format(medals.get("bronze", 0))
        )
        self.tree_ctrl.SetItemPyData(
            item_b,
            {"type": "field", "key_nested": ("medals", "bronze"), "is_int": True},
        )

        item_w = self.tree_ctrl.AppendItem(
            node_med, _("Legni (Medaglia di legno): {}").format(medals.get("wood", 0))
        )
        self.tree_ctrl.SetItemPyData(
            item_w, {"type": "field", "key_nested": ("medals", "wood"), "is_int": True}
        )

        self.tree_ctrl.Expand(root_node)

    def on_tree_item_activated(self, event):
        item = event.GetItem()
        data = self.tree_ctrl.GetItemPyData(item)
        if not data or data.get("type") != "field":
            return

        p = self.players_db[self.selected_player_id]
        if "key_nested" in data:
            parent_key, child_key = data["key_nested"]
            parent_dict = p.setdefault(parent_key, {})
            current_val = str(parent_dict.get(child_key, 0))
            key_name = child_key
        else:
            key_name = data["key"]
            current_val = str(p.get(key_name, ""))

        field_names = {
            "last_name": _("Cognome"),
            "first_name": _("Nome"),
            "sex": _("Sesso"),
            "gender": _("Sesso"),
            "birth_date": _("Anno Nascita"),
            "federation": _("Nazione (FED)"),
            "club": _("Club/Società"),
            "games_played": _("Partite Locali Giocate"),
            "registration_date": _("Data Registrazione"),
            "current_elo": _("ELO Standard"),
            "elo_rapid": _("ELO Rapid"),
            "elo_blitz": _("ELO Blitz"),
            "fide_title": _("Titolo FIDE"),
            "fide_id_num_str": _("ID FIDE"),
            "fide_k_factor": _("FIDE Standard K"),
            "fide_standard_games": _("Partite FIDE Standard"),
            "fide_rapid_k": _("FIDE Rapid K"),
            "fide_rapid_games": _("Partite FIDE Rapid"),
            "fide_blitz_k": _("FIDE Blitz K"),
            "fide_blitz_games": _("Partite FIDE Blitz"),
            "w_title": _("Titolo Femminile"),
            "o_title": _("Titolo Arbitro/Altro"),
            "foa_title": _("Titolo FOA"),
            "flag": _("Flag (Caratteristica)"),
            "gold": _("Ori (Oro)"),
            "silver": _("Argenti (Argento)"),
            "bronze": _("Bronzi (Bronzo)"),
            "wood": _("Legni (Medaglia di legno)"),
        }
        field_label = field_names.get(key_name, key_name)

        dlg = wx.TextEntryDialog(
            self,
            _("Modifica valore per '{field}':").format(field=field_label),
            _("Modifica Campo"),
            current_val,
        )
        if dlg.ShowModal() == wx.ID_OK:
            new_val = dlg.GetValue().strip()

            # Validazione e inserimento del valore
            if data.get("is_int"):
                if new_val.isdigit():
                    val = int(new_val)
                else:
                    play_sound("errore")
                    dlg_err = AccessibleMsgDialog(
                        self,
                        _("Errore"),
                        _("Inserisci un valore numerico valido."),
                        settings=self.settings,
                    )
                    dlg_err.ShowModal()
                    dlg_err.Destroy()
                    dlg.Destroy()
                    return
            else:
                val = new_val

            if "key_nested" in data:
                parent_key, child_key = data["key_nested"]
                p.setdefault(parent_key, {})[child_key] = val
            else:
                key = data["key"]
                if key == "sex":
                    val_clean = str(val).strip().lower()
                    if val_clean in ("w", "f", "femmina"):
                        p["sex"] = "w"
                        p["gender"] = "W"
                    else:
                        p["sex"] = "m"
                        p["gender"] = "M"
                else:
                    p[key] = val

            from db_players import save_players_db

            save_players_db(self.players_db)
            play_sound("timbratura")

            # Aggiorna il testo del nodo in-place per preservare il focus dell'albero
            if "key_nested" in data:
                parent_key, child_key = data["key_nested"]
                prefix_map = {
                    "gold": _("Ori (Oro): "),
                    "silver": _("Argenti (Argento): "),
                    "bronze": _("Bronzi (Bronzo): "),
                    "wood": _("Legni (Medaglia di legno): "),
                }
                prefix = prefix_map.get(child_key, "")
                val_updated = p.get(parent_key, {}).get(child_key, 0)
                self.tree_ctrl.SetItemText(item, f"{prefix}{val_updated}")
                # Impostiamo una chiave fittizia per evitare crash successivi
                key = parent_key
            else:
                key = data["key"]
                prefix_map = {
                    "last_name": _("Cognome: "),
                    "first_name": _("Nome: "),
                    "sex": _("Sesso: "),
                    "gender": _("Sesso: "),
                    "birth_date": _("Anno Nascita: "),
                    "federation": _("Nazione (FED): "),
                    "club": _("Club/Società: "),
                    "games_played": _("Partite Locali Giocate: "),
                    "registration_date": _("Data Registrazione: "),
                    "current_elo": _("ELO Standard: "),
                    "elo_rapid": _("ELO Rapid: "),
                    "elo_blitz": _("ELO Blitz: "),
                    "fide_title": _("Titolo FIDE: "),
                    "fide_id_num_str": _("ID FIDE: "),
                    "fide_k_factor": _("FIDE Standard K: "),
                    "fide_standard_games": _("Partite FIDE Standard: "),
                    "fide_rapid_k": _("FIDE Rapid K: "),
                    "fide_rapid_games": _("Partite FIDE Rapid: "),
                    "fide_blitz_k": _("FIDE Blitz K: "),
                    "fide_blitz_games": _("Partite FIDE Blitz: "),
                    "w_title": _("Titolo Femminile: "),
                    "o_title": _("Titolo Arbitro/Altro: "),
                    "foa_title": _("Titolo FOA: "),
                    "flag": _("Flag (Caratteristica): "),
                }
                prefix = prefix_map.get(key, "")
                disp_val = p.get(key, "")
                if key == "sex":
                    disp_val = "W" if p.get("sex") == "w" else "M"
                elif key in (
                    "current_elo",
                    "elo_rapid",
                    "elo_blitz",
                    "games_played",
                    "fide_standard_games",
                    "fide_rapid_games",
                    "fide_blitz_games",
                ):
                    try:
                        disp_val = int(float(disp_val))
                    except (ValueError, TypeError):
                        disp_val = 0
                elif key in ("fide_k_factor", "fide_rapid_k", "fide_blitz_k"):
                    if disp_val is not None:
                        try:
                            disp_val = int(float(disp_val))
                        except (ValueError, TypeError):
                            disp_val = ""
                    else:
                        disp_val = ""
                self.tree_ctrl.SetItemText(item, f"{prefix}{disp_val}")
            # Se sono cambiati dati identificativi o l'Elo, aggiorna la radice dell'albero e la listbox di sinistra
            if key in ["last_name", "first_name", "current_elo", "elo_rapid"]:
                if key in ["last_name", "first_name"]:
                    root_item = self.tree_ctrl.GetFirstChild(
                        self.tree_ctrl.GetRootItem()
                    )[0]
                    if root_item.IsOk():
                        p_name = f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
                        self.tree_ctrl.SetItemText(root_item, p_name)

                sel = self.list_players.GetSelection()
                if sel != wx.NOT_FOUND:
                    p_id = self.players_map[sel]
                    name_lbl = (
                        f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
                    )
                    elo_std = p.get("current_elo", 1399)
                    elo_rap = p.get("elo_rapid", 0)
                    self.list_players.SetString(
                        sel, f"{name_lbl} (Std: {elo_std}, Rap: {elo_rap} - ID: {p_id})"
                    )

        dlg.Destroy()

    def on_tree_key_down(self, event):
        key_code = event.GetKeyCode()
        item = self.tree_ctrl.GetSelection()
        if not item or not self.selected_player_id:
            event.Skip()
            return

        data = self.tree_ctrl.GetItemPyData(item)
        if key_code == wx.WXK_DELETE and data:
            dtype = data.get("type")
            p = self.players_db[self.selected_player_id]

            if dtype == "player_root":
                # Elimina l'intero giocatore
                self.delete_player(self.selected_player_id)
            elif dtype == "history_record":
                # Rimuovi record dallo storico
                idx = data["index"]
                msg = _("Sei sicuro di voler rimuovere questo record dallo storico?")
                dlg = AccessibleMsgDialog(
                    self,
                    _("Conferma Rimozione"),
                    msg,
                    style=wx.YES_NO,
                    settings=self.settings,
                )
                if dlg.ShowModal() == wx.ID_YES:
                    history = p.get("tournaments_played", [])
                    if 0 <= idx < len(history):
                        removed_entry = history.pop(idx)
                        rank = removed_entry.get("rank")
                        try:
                            rank_int = int(rank)
                        except (ValueError, TypeError):
                            rank_int = None
                        if rank_int in [1, 2, 3, 4]:
                            medals = p.setdefault(
                                "medals",
                                {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
                            )
                            medal_map = {1: "gold", 2: "silver", 3: "bronze", 4: "wood"}
                            medal_key = medal_map.get(rank_int)
                            if medal_key and medals.get(medal_key, 0) > 0:
                                medals[medal_key] -= 1
                    save_players_db(self.players_db)
                    self.populate_player_tree()
                dlg.Destroy()
            return

        event.Skip()

    def delete_player(self, player_id):
        p = self.players_db[player_id]
        name = f"{p.get('last_name')} {p.get('first_name')}"
        msg = _(
            "Sei sicuro di voler eliminare definitivamente il giocatore '{name}' dal database?"
        ).format(name=name)
        dlg = AccessibleMsgDialog(
            self,
            _("Conferma Eliminazione Giocatore"),
            msg,
            style=wx.YES_NO,
            settings=self.settings,
        )
        if dlg.ShowModal() == wx.ID_YES:
            del self.players_db[player_id]
            save_players_db(self.players_db)
            play_sound("tornello_rimozione_giocatore")
            self.on_search_changed(None)
        dlg.Destroy()

    def on_add_player(self, event):
        dlg_ln = wx.TextEntryDialog(self, _("Inserisci Cognome:"), _("Nuovo Giocatore"))
        if dlg_ln.ShowModal() != wx.ID_OK:
            dlg_ln.Destroy()
            return
        last_name = dlg_ln.GetValue().strip()
        dlg_ln.Destroy()

        dlg_fn = wx.TextEntryDialog(self, _("Inserisci Nome:"), _("Nuovo Giocatore"))
        if dlg_fn.ShowModal() != wx.ID_OK:
            dlg_fn.Destroy()
            return
        first_name = dlg_fn.GetValue().strip()
        dlg_fn.Destroy()

        if not last_name or not first_name:
            play_sound("errore")
            dlg_err = AccessibleMsgDialog(
                self,
                _("Errore"),
                _("Nome e Cognome sono obbligatori."),
                settings=self.settings,
            )
            dlg_err.ShowModal()
            dlg_err.Destroy()
            return

        new_id = generate_player_id(first_name, last_name, self.players_db)
        from datetime import datetime
        from config import DATE_FORMAT_ISO

        new_player = {
            "id": new_id,
            "first_name": first_name,
            "last_name": last_name,
            "current_elo": 1399,
            "registration_date": datetime.now().strftime(DATE_FORMAT_ISO),
            "birth_date": "1990-01-01",
            "sex": "m",
            "gender": "M",
            "federation": "ITA",
            "fide_title": "",
            "club": "",
            "games_played": 0,
            "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
            "tournaments_played": [],
            "fide_id_num_str": "",
            "results_history": [],
            "opponents": [],
        }

        self.players_db[new_id] = new_player
        save_players_db(self.players_db)
        play_sound("aggiunta_giocatore")

        self.search_input.SetValue("")  # Resetta ricerca per mostrare il nuovo
        self.on_search_changed(None)

        # Cerca ed evidenzia il nuovo giocatore aggiunto nella listbox
        for idx, p_id in enumerate(self.players_map):
            if p_id == new_id:
                self.list_players.SetSelection(idx)
                self.on_player_selected(None)
                break
