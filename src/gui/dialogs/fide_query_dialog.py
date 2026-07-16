import wx
import builtins
from fide_db import search_players
from gui.settings import apply_visual_settings
from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog
from utils import play_sound

_ = getattr(builtins, "_", lambda s: s)


class FideQueryDialog(wx.Dialog):
    """
    Finestra di dialogo per la consultazione del Database FIDE locale.
    Layout a doppia vista: ListBox per la scelta dei risultati a sinistra,
    e TextCtrl multi-riga dettagliato a destra per la consultazione dei dati completi.
    """

    def __init__(self, parent, players_db, settings):
        title = _("Consulta Database FIDE")
        super().__init__(
            parent,
            title=title,
            size=(850, 550),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.settings = settings
        self.players_db = players_db

        self.all_fide_matches = []
        self.fide_displayed_count = 0

        self._search_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_debounced_search, self._search_timer)

        self._init_ui()
        self.apply_theme()

        self.on_search_changed(None)
        self.Centre()

    def _init_ui(self):
        panel = wx.Panel(self)
        vbox_main = wx.BoxSizer(wx.VERTICAL)

        # Filtro di Ricerca
        hbox_search = wx.BoxSizer(wx.HORIZONTAL)
        hbox_search.Add(
            wx.StaticText(panel, label=_("Cerca per Cognome/Nome o ID FIDE:")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self.search_input = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_input.Bind(wx.EVT_TEXT, self.on_search_changed)
        hbox_search.Add(self.search_input, 1, wx.EXPAND)
        vbox_main.Add(hbox_search, 0, wx.EXPAND | wx.ALL, 10)

        # Area Risultati e Dettaglio (Splitter o HBox)
        hbox_views = wx.BoxSizer(wx.HORIZONTAL)

        # Sizer Sinistra: ListBox dei Risultati
        vbox_left = wx.BoxSizer(wx.VERTICAL)
        vbox_left.Add(
            wx.StaticText(panel, label=_("Giocatori Trovati:")), 0, wx.BOTTOM, 5
        )
        self.list_results = wx.ListBox(panel, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.list_results.Bind(wx.EVT_LISTBOX, self.on_item_selected)
        self.list_results.Bind(wx.EVT_LISTBOX_DCLICK, self.on_import_player)
        self.list_results.Bind(wx.EVT_CHAR_HOOK, self.on_list_key)
        vbox_left.Add(self.list_results, 1, wx.EXPAND)

        hbox_views.Add(vbox_left, 1, wx.EXPAND | wx.RIGHT, 10)

        # Sizer Destra: Dettagli Giocatore
        vbox_right = wx.BoxSizer(wx.VERTICAL)
        vbox_right.Add(
            wx.StaticText(panel, label=_("Dettagli Giocatore FIDE:")), 0, wx.BOTTOM, 5
        )
        self.detail_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        vbox_right.Add(self.detail_text, 1, wx.EXPAND)

        hbox_views.Add(vbox_right, 1, wx.EXPAND)

        vbox_main.Add(hbox_views, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Bottoni in fondo
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_import = wx.Button(panel, label=_("Importa nel DB Locale"))
        self.btn_import.Bind(wx.EVT_BUTTON, self.on_import_player)

        btn_close = wx.Button(panel, wx.ID_CANCEL, _("Chiudi"))

        btn_sizer.Add(self.btn_import, 0, wx.RIGHT, 10)
        btn_sizer.Add(btn_close, 0)
        vbox_main.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(vbox_main)
        vbox_main.Fit(self)

    def apply_theme(self):
        apply_visual_settings(self.search_input, self.settings)
        apply_visual_settings(self.list_results, self.settings)
        apply_visual_settings(self.detail_text, self.settings)

    def on_search_changed(self, event):
        self._search_timer.Stop()
        self._search_timer.Start(900, wx.TIMER_ONE_SHOT)

    def _on_debounced_search(self, event):
        query = self.search_input.GetValue().strip()
        self.list_results.Clear()
        self.results_map = []
        self.all_fide_matches = []
        self.fide_displayed_count = 0
        self.detail_text.Clear()

        if len(query) < 3:
            return

        play_sound("fide_attesa")
        self.all_fide_matches = search_players(query)
        self.load_more_results()
        play_sound("fide_pronto")

        if self.list_results.GetCount() > 0:
            self.list_results.SetSelection(0)
            self.on_item_selected(None)

    def load_more_results(self):
        # Rimuovi l'eventuale precedente item "Mostra altri..."
        last_idx = self.list_results.GetCount() - 1
        if last_idx >= 0 and self.list_results.GetString(last_idx).startswith("--"):
            self.list_results.Delete(last_idx)

        start = self.fide_displayed_count
        end = min(start + 100, len(self.all_fide_matches))

        for i in range(start, end):
            p = self.all_fide_matches[i]
            fide_id_str = str(p.get("id_fide"))
            name = f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
            elo = p.get("elo_standard", 0)
            label = _(
                "{name} (ELO: {elo} - ID FIDE: {fide_id} - Anno: {anno} - FED: {fed})"
            ).format(
                name=name,
                elo=elo,
                fide_id=fide_id_str,
                anno=p.get("birth_year", _("N/D")),
                fed=p.get("federation", _("N/D")),
            )
            self.list_results.Append(label)
            self.results_map.append(p)

        self.fide_displayed_count = end

        # Se ci sono altri risultati, aggiungi la riga speciale
        if self.fide_displayed_count < len(self.all_fide_matches):
            total = len(self.all_fide_matches)
            rem = total - self.fide_displayed_count
            lbl = _("-- Mostra altri risultati ({rem} rimanenti su {total}) --").format(
                rem=rem, total=total
            )
            self.list_results.Append(lbl)

    def on_item_selected(self, event):
        sel = self.list_results.GetSelection()
        if sel == wx.NOT_FOUND:
            self.detail_text.Clear()
            return

        # Ignora se è la riga speciale "Mostra altri..."
        if self.list_results.GetString(sel).startswith("--"):
            self.detail_text.Clear()
            return

        p = self.results_map[sel]

        details = (
            _("Cognome: {}").format(p.get("last_name", ""))
            + "\n"
            + _("Nome: {}").format(p.get("first_name", ""))
            + "\n"
            + _("ID FIDE: {}").format(p.get("id_fide", _("N/D")))
            + "\n"
            + _("Nazione (FED): {}").format(p.get("federation", _("N/D")))
            + "\n"
            + _("Sesso (Sex): {}").format(p.get("sex", "M"))
            + "\n"
            + _("Anno Nascita: {}").format(p.get("birth_year", _("N/D")))
            + "\n"
            + _("Titolo FIDE: {}").format(p.get("title", _("Nessuno")))
            + "\n"
            + _("ELO Standard: {}").format(p.get("elo_standard", 0))
            + "\n"
            + _("Partite Standard: {}").format(p.get("games", 0))
            + "\n"
            + _("ELO Rapid: {}").format(p.get("elo_rapid", 0))
            + "\n"
            + _("Partite Rapid: {}").format(p.get("rapid_games", 0))
            + "\n"
            + _("ELO Blitz: {}").format(p.get("elo_blitz", 0))
            + "\n"
            + _("Partite Blitz: {}").format(p.get("blitz_games", 0))
            + "\n"
        )
        self.detail_text.SetValue(details)
        apply_visual_settings(self.detail_text, self.settings)

    def on_import_player(self, event):
        sel = self.list_results.GetSelection()
        if sel == wx.NOT_FOUND:
            return

        # Gestisci il click su "Mostra altri..."
        if self.list_results.GetString(sel).startswith("--"):
            self.load_more_results()
            new_sel = sel
            if new_sel < self.list_results.GetCount():
                self.list_results.SetSelection(new_sel)
                self.on_item_selected(None)
            return

        fide_player = self.results_map[sel]
        fide_id_str = str(fide_player.get("id_fide"))

        # Verifica se è già nel DB personale locale
        gia_presente = False
        for local_id, lp in self.players_db.items():
            if lp.get("fide_id_num_str") == fide_id_str:
                gia_presente = True
                break

        if gia_presente:
            play_sound("errore")
            dlg = AccessibleMsgDialog(
                self,
                _("Info"),
                _("Questo giocatore è già presente nel tuo database personale."),
            )
            dlg.ShowModal()
            dlg.Destroy()
            return

        # Genera ID locale per il giocatore
        from db_players import generate_player_id, save_players_db

        first_name = fide_player.get("first_name", "")
        last_name = fide_player.get("last_name", "")
        new_id = generate_player_id(first_name, last_name, self.players_db)

        from datetime import datetime
        from config import DATE_FORMAT_ISO

        fide_sex = fide_player.get("sex", "M")
        sex_val = "w" if str(fide_sex).strip().upper() in ("W", "F") else "m"
        gender_val = "W" if sex_val == "w" else "M"

        new_player = {
            "id": new_id,
            "first_name": first_name,
            "last_name": last_name,
            "current_elo": fide_player.get("elo_standard") or 1399,
            "registration_date": datetime.now().strftime(DATE_FORMAT_ISO),
            "birth_date": f"{fide_player.get('birth_year', 1980)}-01-01",
            "sex": sex_val,
            "gender": gender_val,
            "federation": fide_player.get("federation", "ITA"),
            "fide_title": fide_player.get("title", ""),
            "club": "",
            "games_played": 0,
            "medals": {"gold": 0, "silver": 0, "bronze": 0, "wood": 0},
            "tournaments_played": [],
            "fide_id_num_str": fide_id_str,
            "results_history": [],
            "opponents": [],
        }

        self.players_db[new_id] = new_player
        save_players_db(self.players_db)

        msg = _(
            "Giocatore '{name}' importato con successo nel database locale con ID '{id}'."
        ).format(
            name=f"{new_player['last_name']} {new_player['first_name']}", id=new_id
        )
        play_sound("salvato")
        dlg = AccessibleMsgDialog(self, _("Importazione Completata"), msg)
        dlg.ShowModal()
        dlg.Destroy()

    def on_list_key(self, event):
        key_code = event.GetKeyCode()
        if key_code == wx.WXK_RETURN:
            self.on_import_player(None)
        else:
            event.Skip()
