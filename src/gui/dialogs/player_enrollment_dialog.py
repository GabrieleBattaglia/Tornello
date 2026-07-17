import wx
import builtins
from fide_db import search_players
from gui.settings import apply_visual_settings
from utils import match_player_query, play_sound

_ = getattr(builtins, "_", lambda s: s)


class PlayerEnrollmentDialog(wx.Dialog):
    """
    Finestra di dialogo modale per l'iscrizione dei giocatori al torneo.
    Fornisce ricerca in tempo reale sia nel DB personale locale che nel DB FIDE,
    con la possibilità di aggiungere o rimuovere partecipanti.
    """

    def __init__(
        self, parent, players_db, enrolled_players, settings, category="standard"
    ):
        title = _("Iscrizione Giocatori")
        super().__init__(
            parent,
            title=title,
            size=(900, 650),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.settings = settings
        self.players_db = players_db
        self.category = category
        # Facciamo una copia dei giocatori iscritti per gestire l'annullamento
        self.enrolled_players = list(enrolled_players)

        self.all_fide_matches = []
        self.fide_displayed_count = 0

        self._fide_search_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_debounced_fide_search, self._fide_search_timer)

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
        self.sb_local = wx.StaticBox(
            panel, label=_("Ricerca nel Database Personale Locale")
        )
        sbs_local = wx.StaticBoxSizer(self.sb_local, wx.VERTICAL)

        self.search_local = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_local.SetName(_("Filtra per nome o cognome nel database locale"))
        self.search_local.Bind(wx.EVT_TEXT, self.on_search_local_changed)
        sbs_local.Add(self.search_local, 0, wx.EXPAND | wx.ALL, 5)

        self.lbl_local_status = wx.StaticText(panel, label=_("Giocatori trovati: 0"))
        self.lbl_local_status.SetName(_("Stato ricerca locale"))
        sbs_local.Add(
            self.lbl_local_status, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5
        )

        self.list_local_results = wx.ListBox(
            panel, style=wx.LB_SINGLE | wx.LB_NEEDED_SB
        )
        self.list_local_results.SetName(_("Risultati Ricerca Locale"))
        self.list_local_results.Bind(wx.EVT_LISTBOX_DCLICK, self.on_add_local)
        self.list_local_results.Bind(wx.EVT_CHAR_HOOK, self.on_local_key)
        sbs_local.Add(self.list_local_results, 1, wx.EXPAND | wx.ALL, 5)

        left_vbox.Add(sbs_local, 1, wx.EXPAND | wx.ALL, 5)

        # Sezione 2: DB FIDE
        self.sb_fide = wx.StaticBox(
            panel, label=_("Ricerca nel Database FIDE (min. 3 caratteri)")
        )
        sbs_fide = wx.StaticBoxSizer(self.sb_fide, wx.VERTICAL)

        self.search_fide = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_fide.SetName(
            _("Filtra per nome o cognome nel database FIDE (minimo 3 caratteri)")
        )
        self.search_fide.Bind(wx.EVT_TEXT, self.on_search_fide_changed)
        sbs_fide.Add(self.search_fide, 0, wx.EXPAND | wx.ALL, 5)

        self.lbl_fide_status = wx.StaticText(
            panel, label=_("Digita almeno 3 caratteri per cercare.")
        )
        self.lbl_fide_status.SetName(_("Stato ricerca FIDE"))
        sbs_fide.Add(
            self.lbl_fide_status, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5
        )

        self.list_fide_results = wx.ListBox(panel, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.list_fide_results.SetName(_("Risultati Ricerca FIDE"))
        self.list_fide_results.Bind(wx.EVT_LISTBOX_DCLICK, self.on_add_fide)
        self.list_fide_results.Bind(wx.EVT_CHAR_HOOK, self.on_fide_key)
        sbs_fide.Add(self.list_fide_results, 1, wx.EXPAND | wx.ALL, 5)

        left_vbox.Add(sbs_fide, 1, wx.EXPAND | wx.ALL, 5)

        # Pulsanti colonna sinistra: Iscrivi + Nuovo Giocatore
        btn_left_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_enroll = wx.Button(panel, label=_("&Iscrivi"))
        self.btn_enroll.SetName(_("Iscrivi il giocatore selezionato"))
        self.btn_enroll.Bind(wx.EVT_BUTTON, self.on_enroll_clicked)
        btn_left_sizer.Add(self.btn_enroll, 1, wx.EXPAND | wx.RIGHT, 5)

        self.btn_new_player = wx.Button(
            panel, label=_("Nuovo Giocatore Da Zero (Principiante)")
        )
        self.btn_new_player.Bind(wx.EVT_BUTTON, self.on_create_new_player)
        btn_left_sizer.Add(self.btn_new_player, 2, wx.EXPAND)

        left_vbox.Add(btn_left_sizer, 0, wx.EXPAND | wx.ALL, 5)

        main_hbox.Add(left_vbox, 1, wx.EXPAND)

        # --- COLONNA DESTRA: ISCRITTI ---
        right_vbox = wx.BoxSizer(wx.VERTICAL)

        self.sb_enrolled = wx.StaticBox(panel, label=_("Giocatori Iscritti al Torneo"))
        sbs_enrolled = wx.StaticBoxSizer(self.sb_enrolled, wx.VERTICAL)

        self.list_enrolled = wx.ListBox(panel, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.list_enrolled.Bind(wx.EVT_LISTBOX_DCLICK, self.on_remove_enrolled)
        self.list_enrolled.Bind(wx.EVT_CHAR_HOOK, self.on_enrolled_key)
        sbs_enrolled.Add(self.list_enrolled, 1, wx.EXPAND | wx.ALL, 5)

        # Bottoni OK/Annulla posizionati in fondo alla colonna destra
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("Annulla"))
        btn_ok = wx.Button(panel, wx.ID_OK, _("OK"))
        btn_ok.SetDefault()
        btn_ok.Bind(wx.EVT_BUTTON, self.on_ok_clicked)

        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, 10)
        btn_sizer.Add(btn_ok, 0)
        sbs_enrolled.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.TOP | wx.BOTTOM, 5)

        right_vbox.Add(sbs_enrolled, 1, wx.EXPAND | wx.ALL, 5)

        main_hbox.Add(right_vbox, 1, wx.EXPAND)

        panel.SetSizer(main_hbox)

        # Sizer principale per il Dialog stesso (self) per garantire elasticità al ridimensionamento
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)

        self.SetMinSize((850, 600))
        self.Layout()

    def apply_theme(self):
        apply_visual_settings(self.search_local, self.settings)
        apply_visual_settings(self.lbl_local_status, self.settings)
        apply_visual_settings(self.list_local_results, self.settings)
        apply_visual_settings(self.search_fide, self.settings)
        apply_visual_settings(self.lbl_fide_status, self.settings)
        apply_visual_settings(self.list_fide_results, self.settings)
        apply_visual_settings(self.list_enrolled, self.settings)
        apply_visual_settings(self.btn_enroll, self.settings)
        apply_visual_settings(self.btn_new_player, self.settings)

    def update_enrolled_list(self):
        """Aggiorna il contenuto della lista dei giocatori iscritti, ordinati per ELO decrescente."""
        from stats import get_initial_elo_for_tournament

        # Ordina per ELO decrescente (in base alla cadenza del torneo), poi per cognome, poi per nome
        self.enrolled_players.sort(
            key=lambda x: (
                -get_initial_elo_for_tournament(x, self.category),
                x.get("last_name", "").lower(),
                x.get("first_name", "").lower(),
            )
        )

        self.list_enrolled.Clear()
        self.enrolled_data_map = []

        for idx, p in enumerate(self.enrolled_players):
            last_name = p.get("last_name", "")
            first_name = p.get("first_name", "")
            elo = int(get_initial_elo_for_tournament(p, self.category))
            fed = p.get("federation") or "ITA"
            label = f"{idx + 1}. {last_name} {first_name} ({fed}) {elo}"
            self.list_enrolled.Append(label)
            self.enrolled_data_map.append(p)

        total_enrolled = len(self.enrolled_players)
        self.sb_enrolled.SetLabel(
            _("Giocatori Iscritti al Torneo ({total})").format(total=total_enrolled)
        )

    def on_search_local_changed(self, event):
        """Filtra e aggiorna i risultati del DB locale in ordine di ELO decrescente."""
        query = self.search_local.GetValue().strip().lower()

        self.list_local_results.Clear()
        self.local_results_map = []

        # Mappa per escludere omonimi già iscritti
        enrolled_ids = {p.get("id") for p in self.enrolled_players if p.get("id")}

        matching_with_scores = []
        for p_id, p in self.players_db.items():
            if p_id in enrolled_ids:
                continue

            if not query:
                # Se la query è vuota, ordiniamo solo alfabeticamente
                score = (
                    0,
                    0,
                    p.get("last_name", "").lower(),
                    p.get("first_name", "").lower(),
                )
                matching_with_scores.append((score, p))
            else:
                score = match_player_query(p, query)
                if score is not None:
                    matching_with_scores.append((score, p))

        # Ordina per rilevanza query, poi per ELO decrescente
        matching_with_scores.sort(
            key=lambda x: (
                x[0][0],  # -matched_count
                -(x[1].get("current_elo") or x[1].get("elo_standard") or 1399),
                x[0][2],  # last_name
                x[0][3],  # first_name
            )
        )

        matching_sorted = [p for score, p in matching_with_scores]

        for p in matching_sorted:
            p_id = p.get("id")
            name = f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
            elo_std = p.get("current_elo") or p.get("elo_standard") or 1399
            elo_rap = p.get("elo_rapid") or 0
            label = _("{name} (Std: {elo_std}, Rap: {elo_rap} - ID: {id})").format(
                name=name, elo_std=elo_std, elo_rap=elo_rap, id=p_id
            )
            self.list_local_results.Append(label)
            self.local_results_map.append(p)

        total_found = len(matching_sorted)
        self.lbl_local_status.SetLabel(
            _("Giocatori trovati: {total}").format(total=total_found)
        )

    def on_search_fide_changed(self, event):
        """Filtra e aggiorna i risultati del DB FIDE."""
        self._fide_search_timer.Stop()
        self._fide_search_timer.Start(900, wx.TIMER_ONE_SHOT)

    def _on_debounced_fide_search(self, event):
        self.esegui_ricerca_fide()

    def esegui_ricerca_fide(self, target_sel=None):
        query = self.search_fide.GetValue().strip()
        self.list_fide_results.Clear()
        self.fide_results_map = []
        self.all_fide_matches = []
        self.fide_displayed_count = 0

        if len(query) < 3:
            self.lbl_fide_status.SetLabel(_("Digita almeno 3 caratteri per cercare."))
            return

        play_sound("fide_attesa")

        enrolled_fide_ids = {
            p.get("fide_id_num_str")
            for p in self.enrolled_players
            if p.get("fide_id_num_str")
        }

        self.all_fide_matches = search_players(
            query, exclude_fide_ids=enrolled_fide_ids
        )

        self.load_more_fide_results()

        total_found = len(self.all_fide_matches)
        self.lbl_fide_status.SetLabel(
            _("Giocatori trovati: {total}").format(total=total_found)
        )

        # Ripristina la selezione se indicata o seleziona il primo elemento
        new_count = self.list_fide_results.GetCount()
        if new_count > 0:
            if target_sel is not None:
                new_sel = min(target_sel, new_count - 1)
                self.list_fide_results.SetSelection(new_sel)
                self.list_fide_results.SetFocus()  # Sposta il focus solo all'aggiunta/rimozione
            else:
                self.list_fide_results.SetSelection(0)
        else:
            if target_sel is not None:
                self.search_fide.SetFocus()

        play_sound("fide_pronto")

    def load_more_fide_results(self):
        # Rimuovi l'eventuale precedente item "Mostra altri..."
        last_idx = self.list_fide_results.GetCount() - 1
        if last_idx >= 0 and self.list_fide_results.GetString(last_idx).startswith(
            "--"
        ):
            self.list_fide_results.Delete(last_idx)

        start = self.fide_displayed_count
        end = min(start + 100, len(self.all_fide_matches))

        for i in range(start, end):
            p = self.all_fide_matches[i]
            fide_id_str = str(p.get("id_fide"))
            name = f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
            elo_std = p.get("elo_standard", 0)
            elo_rap = p.get("elo_rapid", 0)
            label = _(
                "{name} (Std: {elo_std}, Rap: {elo_rap} - ID FIDE: {fide_id} - Anno: {anno} - FED: {fed})"
            ).format(
                name=name,
                elo_std=elo_std,
                elo_rap=elo_rap,
                fide_id=fide_id_str,
                anno=p.get("birth_year", _("N/D")),
                fed=p.get("federation", _("N/D")),
            )
            self.list_fide_results.Append(label)
            self.fide_results_map.append(p)

        self.fide_displayed_count = end

        # Se ci sono altri risultati, aggiungi la riga speciale
        if self.fide_displayed_count < len(self.all_fide_matches):
            total = len(self.all_fide_matches)
            rem = total - self.fide_displayed_count
            lbl = _("-- Mostra altri risultati ({rem} rimanenti su {total}) --").format(
                rem=rem, total=total
            )
            self.list_fide_results.Append(lbl)

    def on_add_local(self, event):
        sel = self.list_local_results.GetSelection()
        if sel == wx.NOT_FOUND:
            return

        player_data = self.local_results_map[sel]
        self.enrolled_players.append(player_data)

        self.update_enrolled_list()
        self.on_search_local_changed(None)

        # Riproduci suono di aggiunta
        play_sound("aggiunta_giocatore")

        # Trova l'indice del giocatore appena aggiunto nella lista iscritti (perché è stata riordinata)
        new_idx = 0
        for i, p in enumerate(self.enrolled_players):
            if p.get("id") == player_data.get("id"):
                new_idx = i
                break

        self.list_enrolled.SetSelection(new_idx)

        # Ripristina la selezione e il focus sulla lista locale (o sul campo di ricerca se vuota)
        new_count = self.list_local_results.GetCount()
        if new_count > 0:
            new_sel = min(sel, new_count - 1)
            self.list_local_results.SetSelection(new_sel)
            self.list_local_results.SetFocus()
        else:
            self.search_local.SetFocus()

    def on_add_fide(self, event):
        sel = self.list_fide_results.GetSelection()
        if sel == wx.NOT_FOUND:
            return

        # Controlla se è la riga speciale "Mostra altri..."
        if self.list_fide_results.GetString(sel).startswith("--"):
            self.load_more_fide_results()
            new_sel = sel
            if new_sel < self.list_fide_results.GetCount():
                self.list_fide_results.SetSelection(new_sel)
            return

        fide_player = self.fide_results_map[sel]

        # Mappa il giocatore FIDE nello schema giocatore di Tornello
        raw_sex = fide_player.get("sex", "M")
        sex_val = "w" if str(raw_sex).strip().lower() in ("w", "f") else "m"
        gender_val = sex_val.upper()

        new_player = {
            "id": f"FIDE_{fide_player.get('id_fide')}",
            "first_name": fide_player.get("first_name", ""),
            "last_name": fide_player.get("last_name", ""),
            "current_elo": fide_player.get("elo_standard") or 1399,
            "elo_rapid": fide_player.get("elo_rapid", 0),
            "elo_blitz": fide_player.get("elo_blitz", 0),
            "fide_k_factor": fide_player.get("k_factor"),
            "fide_rapid_k": fide_player.get("rapid_k"),
            "fide_blitz_k": fide_player.get("blitz_k"),
            "fide_standard_games": fide_player.get("games", 0),
            "fide_rapid_games": fide_player.get("rapid_games", 0),
            "fide_blitz_games": fide_player.get("blitz_games", 0),
            "w_title": fide_player.get("w_title", ""),
            "o_title": fide_player.get("o_title", ""),
            "foa_title": fide_player.get("foa_title", ""),
            "flag": fide_player.get("flag", ""),
            "fide_id_num_str": str(fide_player.get("id_fide")),
            "birth_date": f"{fide_player.get('birth_year', 1980)}-01-01",
            "sex": sex_val,
            "gender": gender_val,
            "federation": fide_player.get("federation", "ITA"),
            "fide_title": fide_player.get("title", ""),
        }

        self.enrolled_players.append(new_player)
        self.update_enrolled_list()

        # Esegui la ricerca immediata senza passare per il debounce
        # e ripristina la selezione desiderata
        self.esegui_ricerca_fide(target_sel=sel)

        # Riproduci suono di aggiunta
        play_sound("aggiunta_giocatore")

        # Trova l'indice del giocatore appena aggiunto nella lista iscritti
        new_idx = 0
        for i, p in enumerate(self.enrolled_players):
            if p.get("fide_id_num_str") == new_player.get("fide_id_num_str"):
                new_idx = i
                break

        self.list_enrolled.SetSelection(new_idx)

    def on_remove_enrolled(self, event):
        sel = self.list_enrolled.GetSelection()
        if sel == wx.NOT_FOUND:
            return

        player_data = self.enrolled_data_map[sel]
        self.enrolled_players.remove(player_data)

        play_sound("rimozione_giocatore")

        self.update_enrolled_list()
        self.on_search_local_changed(None)

        # Aggiorna subito la ricerca FIDE
        self.esegui_ricerca_fide()

        # Focus sulla lista iscritti se ci sono ancora elementi, altrimenti torna alla ricerca locale
        if self.list_enrolled.GetCount() > 0:
            new_sel = min(sel, self.list_enrolled.GetCount() - 1)
            self.list_enrolled.SetSelection(new_sel)
            self.list_enrolled.SetFocus()
        else:
            self.search_local.SetFocus()

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

    def on_ok_clicked(self, event):
        play_sound("conferma")
        event.Skip()

    def on_enroll_clicked(self, event):
        focused_win = wx.Window.FindFocus()
        local_sel = self.list_local_results.GetSelection()
        fide_sel = self.list_fide_results.GetSelection()

        # Se una lista ha il focus ed ha una selezione valida, usiamo quella
        if focused_win == self.list_local_results and local_sel != wx.NOT_FOUND:
            self.on_add_local(None)
            return
        elif focused_win == self.list_fide_results and fide_sel != wx.NOT_FOUND:
            self.on_add_fide(None)
            return

        # Altrimenti proviamo ad aggiungere da chi ha una selezione
        if local_sel != wx.NOT_FOUND:
            self.on_add_local(None)
        elif fide_sel != wx.NOT_FOUND:
            self.on_add_fide(None)
        else:
            from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog

            dlg = AccessibleMsgDialog(
                self,
                _("Nessuna Selezione"),
                _("Seleziona prima un giocatore dalla ricerca locale o FIDE."),
                settings=self.settings,
            )
            dlg.ShowModal()
            dlg.Destroy()

    def get_enrolled_players(self):
        return self.enrolled_players

    def on_create_new_player(self, event):
        dlg_ln = wx.TextEntryDialog(
            self, _("Inserisci Cognome del nuovo giocatore:"), _("Crea Nuovo Giocatore")
        )
        if dlg_ln.ShowModal() != wx.ID_OK:
            dlg_ln.Destroy()
            return
        last_name = dlg_ln.GetValue().strip()
        dlg_ln.Destroy()

        dlg_fn = wx.TextEntryDialog(
            self, _("Inserisci Nome del nuovo giocatore:"), _("Crea Nuovo Giocatore")
        )
        if dlg_fn.ShowModal() != wx.ID_OK:
            dlg_fn.Destroy()
            return
        first_name = dlg_fn.GetValue().strip()
        dlg_fn.Destroy()

        if not last_name or not first_name:
            from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog

            dlg = AccessibleMsgDialog(
                self,
                _("Errore"),
                _("Nome e Cognome sono obbligatori."),
                settings=self.settings,
            )
            dlg.ShowModal()
            dlg.Destroy()
            return

        # Genera ID e crea nel DB locale
        from db_players import generate_player_id, save_players_db

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

        # Salva nel DB giocatori
        self.players_db[new_id] = new_player
        save_players_db(self.players_db)

        # Iscrivi automaticamente al torneo corrente
        self.enrolled_players.append(new_player)
        self.update_enrolled_list()

        # Ripristina/pulisce ricerche
        self.on_search_local_changed(None)

        # Seleziona l'ultimo aggiunto nella lista iscritti per feedback
        self.list_enrolled.SetSelection(self.list_enrolled.GetCount() - 1)
