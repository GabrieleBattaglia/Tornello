import wx
import builtins
import datetime
from gui.settings import apply_visual_settings
from utils import format_date_locale

_ = getattr(builtins, "_", lambda s: s)


class ScheduleDialog(wx.Dialog):
    """
    Finestra di dialogo modale per la pianificazione dettagliata di una partita.
    Permette di selezionare una data da una lista di radio button (da oggi a 3 giorni dopo la scadenza del turno),
    l'ora e i minuti con step da 5, l'indirizzo della sala o l'URL dell'incontro, e il nome dell'arbitro designato.
    """

    def __init__(self, parent, schedule_info, settings, tournament_data):
        super().__init__(
            parent,
            title=_("Pianificazione Partita"),
            size=(500, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self.settings = settings
        self.schedule_info = schedule_info or {}
        self.tournament_data = tournament_data or {}
        self._init_ui()
        self.apply_theme()
        self.Centre()

    def _init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # 1. Calcolo intervallo date (da oggi fino a scadenza turno + 3 giorni)
        from datetime import date

        today = date.today()

        current_round_num = self.tournament_data.get("current_round", 1)
        round_dates_info = self.tournament_data.get("round_dates", [])
        current_round_period_info = next(
            (rd for rd in round_dates_info if rd.get("round") == current_round_num),
            None,
        )

        end_date = None
        if current_round_period_info and current_round_period_info.get("end_date"):
            try:
                end_date = datetime.datetime.strptime(
                    current_round_period_info.get("end_date"), "%Y-%m-%d"
                ).date()
            except ValueError:
                pass

        if not end_date and self.tournament_data.get("end_date"):
            try:
                end_date = datetime.datetime.strptime(
                    self.tournament_data.get("end_date"), "%Y-%m-%d"
                ).date()
            except ValueError:
                pass

        if not end_date:
            end_date = today + datetime.timedelta(days=7)

        limit_date = end_date + datetime.timedelta(days=3)
        if limit_date < today + datetime.timedelta(days=3):
            limit_date = today + datetime.timedelta(days=3)
        if limit_date > today + datetime.timedelta(days=30):
            limit_date = today + datetime.timedelta(days=30)

        dates_list = []
        curr = today
        while curr <= limit_date:
            dates_list.append(curr)
            curr += datetime.timedelta(days=1)

        # Box di selezione giorno
        sb_date = wx.StaticBox(panel, label=_("Seleziona Giorno"))
        sbs_date = wx.StaticBoxSizer(sb_date, wx.VERTICAL)

        self.radio_buttons = []
        first = True

        curr_date_str = self.schedule_info.get("date")
        curr_date = None
        if curr_date_str:
            try:
                curr_date = datetime.datetime.strptime(curr_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        for d in dates_list:
            style = wx.RB_GROUP if first else 0
            lbl = format_date_locale(d)
            rb = wx.RadioButton(panel, label=lbl, style=style)
            rb.Bind(wx.EVT_SET_FOCUS, self.on_rb_focus)

            if curr_date:
                rb.SetValue(d == curr_date)
            else:
                rb.SetValue(first)

            sbs_date.Add(rb, 0, wx.ALL | wx.EXPAND, 4)
            self.radio_buttons.append((d, rb))
            first = False

        vbox.Add(sbs_date, 0, wx.EXPAND | wx.ALL, 15)

        # 2. Selezione Ora e Minuti
        sb_time = wx.StaticBox(panel, label=_("Seleziona Ora"))
        sbs_time = wx.StaticBoxSizer(sb_time, wx.HORIZONTAL)

        lbl_hour = wx.StaticText(panel, label=_("Ora:"))
        self.choice_hour = wx.Choice(panel, choices=[f"{h:02d}" for h in range(24)])
        self.choice_hour.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        lbl_min = wx.StaticText(panel, label=_("Minuto:"))
        self.choice_min = wx.Choice(
            panel, choices=[f"{m:02d}" for m in range(0, 60, 5)]
        )
        self.choice_min.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        curr_time_str = self.schedule_info.get("time", "15:00")
        c_hour, c_min = "15", "00"
        if ":" in curr_time_str:
            parts = curr_time_str.split(":")
            if len(parts) == 2:
                c_hour, c_min = parts[0], parts[1]
                try:
                    m_val = int(c_min)
                    m_val = 5 * round(m_val / 5)
                    if m_val >= 60:
                        m_val = 55
                    c_min = f"{m_val:02d}"
                except ValueError:
                    pass

        self.choice_hour.SetStringSelection(c_hour)
        self.choice_min.SetStringSelection(c_min)

        sbs_time.Add(lbl_hour, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        sbs_time.Add(self.choice_hour, 1, wx.RIGHT, 15)
        sbs_time.Add(lbl_min, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        sbs_time.Add(self.choice_min, 1)

        vbox.Add(sbs_time, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # 3. Campi Sala/URL e Arbitro
        sb_details = wx.StaticBox(panel, label=_("Dettagli Sede e Arbitro"))
        sbs_details = wx.StaticBoxSizer(sb_details, wx.VERTICAL)

        lbl_room = wx.StaticText(panel, label=_("Sala / URL:"))
        self.txt_room = wx.TextCtrl(panel)
        self.txt_room.SetValue(self.schedule_info.get("channel", ""))
        self.txt_room.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        lbl_arbiter = wx.StaticText(panel, label=_("Arbitro designato:"))
        self.txt_arbiter = wx.TextCtrl(panel)
        self.txt_arbiter.SetValue(self.schedule_info.get("arbiter", ""))
        self.txt_arbiter.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        sbs_details.Add(lbl_room, 0, wx.TOP | wx.BOTTOM, 2)
        sbs_details.Add(self.txt_room, 0, wx.EXPAND | wx.BOTTOM, 8)
        sbs_details.Add(lbl_arbiter, 0, wx.TOP | wx.BOTTOM, 2)
        sbs_details.Add(self.txt_arbiter, 0, wx.EXPAND)

        vbox.Add(sbs_details, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Pulsanti OK e Annulla
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("Annulla"))
        btn_ok = wx.Button(panel, wx.ID_OK, _("Conferma"))
        btn_ok.SetDefault()

        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, 10)
        btn_sizer.Add(btn_ok, 0)
        vbox.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        panel.SetSizer(vbox)
        vbox.Fit(self)

        # Associazione tasti
        panel.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.txt_room.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.txt_arbiter.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

    def apply_theme(self):
        apply_visual_settings(self, self.settings)

    def on_rb_focus(self, event):
        rb = event.GetEventObject()
        rb.SetValue(True)
        from utils import play_sound

        play_sound("notifica")
        event.Skip()

    def on_control_focus(self, event):
        from utils import play_sound

        play_sound("notifica")
        event.Skip()

    def on_key_down(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_RETURN or key == wx.WXK_NUMPAD_ENTER:
            self.EndModal(wx.ID_OK)
        elif key == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()

    def EndModal(self, retCode):
        from utils import play_sound

        if retCode == wx.ID_OK:
            # Viene gestito in on_schedule di ResultDialog
            pass
        else:
            play_sound("cancellato")
        return super().EndModal(retCode)

    def get_schedule_info(self):
        selected_date = None
        for d, rb in self.radio_buttons:
            if rb.GetValue():
                selected_date = d.strftime("%Y-%m-%d")
                break
        if not selected_date:
            import datetime

            selected_date = datetime.date.today().strftime("%Y-%m-%d")

        selected_time = f"{self.choice_hour.GetStringSelection()}:{self.choice_min.GetStringSelection()}"
        return {
            "date": selected_date,
            "time": selected_time,
            "channel": self.txt_room.GetValue().strip(),
            "arbiter": self.txt_arbiter.GetValue().strip(),
        }


class ResultDialog(wx.Dialog):
    """
    Finestra di dialogo modale per inserire o variare il risultato di una partita.
    Presenta opzioni radio verticali ampie e ben spaziate personalizzate con i nomi dei giocatori.
    Navigando con Tab o Frecce, la selezione del risultato si attiva automaticamente.
    Invio conferma direttamente la scelta, Esc annulla tutto.
    """

    def __init__(
        self,
        parent,
        white_name,
        black_name,
        white_id,
        black_id,
        board_num,
        current_result,
        schedule_info,
        settings,
        pgn_text="",
        disable_result_change=False,
    ):
        title = _("Risultato Scacchiera {num}").format(num=board_num)
        super().__init__(
            parent,
            title=title,
            size=(550, 650),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.settings = settings
        self.white_name = white_name
        self.black_name = black_name
        self.white_id = white_id
        self.black_id = black_id
        self.board_num = board_num
        self.current_result = current_result
        self.schedule_info = schedule_info or {}
        self.pgn_text = pgn_text or ""
        self.disable_result_change = disable_result_change

        self.selected_action = None  # None (risultato), "schedule", "withdraw"
        self.withdrawn_player_id = None

        self._init_ui()
        self.apply_theme()
        self.Centre()

        # Audio feedback all'apertura del dialogo
        from utils import play_sound

        play_sound("notifica")

    def _init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # --- DETTAGLI PARTITA ---
        sched_lbl = ""
        if self.schedule_info.get("date") and self.schedule_info.get("time"):
            d_formatted = format_date_locale(self.schedule_info["date"])
            sched_lbl = _("\nPianificata per: {date} alle {time}").format(
                date=d_formatted, time=self.schedule_info["time"]
            )
            if self.schedule_info.get("channel"):
                sched_lbl += _(" | Sala/URL: {}").format(self.schedule_info["channel"])
            if self.schedule_info.get("arbiter"):
                sched_lbl += _(" | Arbitro: {}").format(self.schedule_info["arbiter"])

        match_info = (
            _("Scacchiera {}:\n").format(self.board_num)
            + f"  {_('Bianco')}: {self.white_name}\n"
            f"  {_('Nero')}: {self.black_name}{sched_lbl}\n"
        )
        self.lbl_info = wx.StaticText(panel, label=match_info)
        vbox.Add(self.lbl_info, 0, wx.ALL | wx.EXPAND, 15)

        # --- OPZIONI RISULTATO (Nomi dei giocatori anziché generici) ---
        sb_options = wx.StaticBox(panel, label=_("Seleziona Risultato"))
        sbs_options = wx.StaticBoxSizer(sb_options, wx.VERTICAL)

        self.options = [
            ("1-0", _("1 - 0 (Vince {})").format(self.white_name)),
            ("0-1", _("0 - 1 (Vince {})").format(self.black_name)),
            ("1/2-1/2", _("1/2 - 1/2 (Patta)")),
            (
                "1-F",
                _("1 - F (Forfait {} / Assenza {})").format(
                    self.white_name, self.black_name
                ),
            ),
            (
                "F-1",
                _("F - 1 (Forfait {} / Assenza {})").format(
                    self.black_name, self.white_name
                ),
            ),
            ("0-0F", _("0 - 0F (Assenza Doppia)")),
        ]

        self.radio_buttons = []
        first = True
        for val, desc in self.options:
            style = wx.RB_GROUP if first else 0
            rb = wx.RadioButton(panel, label=desc, style=style)
            rb.SetValue(val == self.current_result)
            sbs_options.Add(rb, 0, wx.ALL | wx.EXPAND, 6)

            # Associazione eventi per spostamento facilitato e suono
            rb.Bind(wx.EVT_SET_FOCUS, self.on_rb_focus)
            rb.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

            self.radio_buttons.append((val, rb))
            first = False

        vbox.Add(sbs_options, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        # --- CAMPO PGN ---
        self.lbl_pgn = wx.StaticText(
            panel, label=_("Incolla qui il pgn della partita (opzionale):")
        )
        self.txt_pgn = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 100))
        self.txt_pgn.SetValue(self.pgn_text)
        self.txt_pgn.Bind(wx.EVT_TEXT, self.on_pgn_changed)

        self.lbl_validation_error = wx.StaticText(panel, label="")
        self.lbl_validation_error.SetForegroundColour(wx.Colour(200, 0, 0))

        vbox.Add(self.lbl_pgn, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)
        vbox.Add(self.txt_pgn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        vbox.Add(self.lbl_validation_error, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # --- AZIONI DI PIANIFICAZIONE E RITIRO ---
        hbox_actions = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_schedule = wx.Button(panel, label=_("Pianifica Partita..."))
        self.btn_schedule.Bind(wx.EVT_BUTTON, self.on_schedule)
        self.btn_schedule.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        self.btn_withdraw = wx.Button(panel, label=_("Ritira Giocatore..."))
        self.btn_withdraw.Bind(wx.EVT_BUTTON, self.on_withdraw)
        self.btn_withdraw.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        hbox_actions.Add(self.btn_schedule, 1, wx.EXPAND | wx.RIGHT, 10)
        hbox_actions.Add(self.btn_withdraw, 1, wx.EXPAND)

        vbox.Add(hbox_actions, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # --- BOTTONI OK / ANNULLA ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("Annulla"))
        btn_cancel.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        ok_label = (
            _("Salva PGN") if self.disable_result_change else _("Conferma Risultato")
        )
        self.btn_ok = wx.Button(panel, wx.ID_OK, ok_label)
        self.btn_ok.SetDefault()
        self.btn_ok.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, 10)
        btn_sizer.Add(self.btn_ok, 0)

        vbox.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        if self.disable_result_change:
            for val, rb in self.radio_buttons:
                rb.Enable(False)
            self.btn_schedule.Enable(False)
            self.btn_withdraw.Enable(False)

        panel.SetSizer(vbox)
        vbox.Fit(self)

        # Bind generali keydown
        panel.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.btn_schedule.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.btn_withdraw.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.btn_ok.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        btn_cancel.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

    def apply_theme(self):
        apply_visual_settings(self.lbl_info, self.settings)
        for val, rb in self.radio_buttons:
            apply_visual_settings(rb, self.settings)
        apply_visual_settings(self.lbl_pgn, self.settings)
        apply_visual_settings(self.txt_pgn, self.settings)
        apply_visual_settings(self.lbl_validation_error, self.settings)
        apply_visual_settings(self.btn_schedule, self.settings)
        apply_visual_settings(self.btn_withdraw, self.settings)

    def get_selected_result(self):
        """Restituisce la stringa del risultato selezionato (es. '1-0', '1/2-1/2', etc.)."""
        for val, rb in self.radio_buttons:
            if rb.GetValue():
                return val
        return None

    def on_rb_focus(self, event):
        rb = event.GetEventObject()
        rb.SetValue(True)
        for val, button in self.radio_buttons:
            if button == rb:
                from utils import play_sound

                play_sound(f"risultato_{val}")
                break
        event.Skip()

    def on_control_focus(self, event):
        from utils import play_sound

        play_sound("notifica")
        event.Skip()

    def on_key_down(self, event):
        key = event.GetKeyCode()
        if event.GetEventObject() == self.txt_pgn:
            event.Skip()
            return

        if key == wx.WXK_RETURN or key == wx.WXK_NUMPAD_ENTER:
            self.EndModal(wx.ID_OK)
        elif key == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()

    def on_pgn_changed(self, event):
        val = self.txt_pgn.GetValue().strip()
        if not val:
            self.lbl_validation_error.SetLabel("")
            self.btn_ok.Enable(True)
            return

        import chess.pgn
        import io

        pgn_io = io.StringIO(val)
        try:
            game = chess.pgn.read_game(pgn_io)
            if game is None:
                self.lbl_validation_error.SetLabel(
                    _("Formato PGN non valido: nessun dato letto.")
                )
                self.lbl_validation_error.SetForegroundColour(wx.Colour(200, 0, 0))
                self.btn_ok.Enable(False)
                return
            if game.errors:
                err_msg = str(game.errors[0])
                self.lbl_validation_error.SetLabel(
                    _("Formato PGN non valido: {err}").format(err=err_msg)
                )
                self.lbl_validation_error.SetForegroundColour(wx.Colour(200, 0, 0))
                self.btn_ok.Enable(False)
                return

            has_moves = any(True for _ in game.mainline_moves())
            has_brackets = "[" in val and "]" in val
            if not has_moves and not has_brackets:
                self.lbl_validation_error.SetLabel(
                    _("Formato PGN non valido: testo non riconosciuto come PGN.")
                )
                self.lbl_validation_error.SetForegroundColour(wx.Colour(200, 0, 0))
                self.btn_ok.Enable(False)
                return

            self.lbl_validation_error.SetLabel(_("Formato PGN valido."))
            self.lbl_validation_error.SetForegroundColour(wx.Colour(0, 150, 0))
            self.btn_ok.Enable(True)
        except Exception as e:
            self.lbl_validation_error.SetLabel(
                _("Errore validazione PGN: {err}").format(err=str(e))
            )
            self.lbl_validation_error.SetForegroundColour(wx.Colour(200, 0, 0))
            self.btn_ok.Enable(False)

    def on_schedule(self, event):
        from utils import play_sound

        play_sound("notifica")

        parent_frame = self.GetParent()
        t_data = getattr(parent_frame, "current_tournament", {})

        dlg = ScheduleDialog(self, self.schedule_info, self.settings, t_data)
        if dlg.ShowModal() == wx.ID_OK:
            self.schedule_info = dlg.get_schedule_info()
            self.selected_action = "schedule"
            play_sound("pianifica_crea")
            self.EndModal(wx.ID_OK)
        else:
            play_sound("cancellato")
        dlg.Destroy()

    def on_withdraw(self, event):
        choices = [
            f"{self.white_name} (ID: {self.white_id})",
            f"{self.black_name} (ID: {self.black_id})",
        ]
        dlg = wx.SingleChoiceDialog(
            self,
            _("Seleziona il giocatore da ritirare definitivamente dal torneo:"),
            _("Ritiro Giocatore"),
            choices,
        )
        if dlg.ShowModal() == wx.ID_OK:
            sel = dlg.GetSelection()
            self.withdrawn_player_id = self.white_id if sel == 0 else self.black_id
            self.selected_action = "withdraw"
            self.EndModal(wx.ID_OK)
        dlg.Destroy()

    def EndModal(self, retCode):
        from utils import play_sound

        if retCode == wx.ID_OK:
            if not self.selected_action:
                play_sound("conferma")
        else:
            play_sound("cancellato")
        return super().EndModal(retCode)
