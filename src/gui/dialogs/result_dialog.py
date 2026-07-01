import wx
import builtins
from gui.settings import apply_visual_settings
from utils import format_date_locale

_ = getattr(builtins, "_", lambda s: s)

class ResultDialog(wx.Dialog):
    """
    Finestra di dialogo modale per inserire o variare il risultato di una partita.
    Presenta opzioni radio verticali ampie e ben spaziate per l'accessibilità con screen reader,
    e pulsanti aggiuntivi per la pianificazione o il ritiro di un giocatore.
    """
    def __init__(self, parent, white_name, black_name, white_id, black_id, board_num, current_result, schedule_info, settings):
        title = _("Risultato Scacchiera {num}").format(num=board_num)
        super().__init__(parent, title=title, size=(550, 500), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
        self.settings = settings
        self.white_name = white_name
        self.black_name = black_name
        self.white_id = white_id
        self.black_id = black_id
        self.board_num = board_num
        self.current_result = current_result
        self.schedule_info = schedule_info or {}
        
        self.selected_action = None  # None (risultato), "schedule", "withdraw"
        self.withdrawn_player_id = None
        
        self._init_ui()
        self.apply_theme()
        self.Centre()

    def _init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # --- DETTAGLI PARTITA ---
        sched_lbl = ""
        if self.schedule_info.get("date") and self.schedule_info.get("time"):
            d_formatted = format_date_locale(self.schedule_info["date"])
            sched_lbl = _("\nPianificata per: {date} alle {time}").format(date=d_formatted, time=self.schedule_info["time"])
            
        match_info = (
            f"Scacchiera {self.board_num}:\n"
            f"  {_('Bianco')}: {self.white_name}\n"
            f"  {_('Nero')}: {self.black_name}{sched_lbl}\n"
        )
        self.lbl_info = wx.StaticText(panel, label=match_info)
        vbox.Add(self.lbl_info, 0, wx.ALL | wx.EXPAND, 15)
        
        # --- OPZIONI RISULTATO (RadioButtons) ---
        sb_options = wx.StaticBox(panel, label=_("Seleziona Risultato"))
        sbs_options = wx.StaticBoxSizer(sb_options, wx.VERTICAL)
        
        self.options = [
            ("1-0", f"1 - 0 ({_('Vince il Bianco')})"),
            ("0-1", f"0 - 1 ({_('Vince il Nero')})"),
            ("1/2-1/2", f"1/2 - 1/2 ({_('Patta')})"),
            ("1-F", f"1 - F ({_('Forfait Bianco / Assenza Nero')})"),
            ("F-1", f"F - 1 ({_('Forfait Nero / Assenza Bianco')})"),
            ("0-0F", f"0 - 0F ({_('Assenza Doppia')})")
        ]
        
        self.radio_buttons = []
        first = True
        for val, desc in self.options:
            style = wx.RB_GROUP if first else 0
            rb = wx.RadioButton(panel, label=desc, style=style)
            rb.SetValue(val == self.current_result)
            sbs_options.Add(rb, 0, wx.ALL | wx.EXPAND, 6)
            self.radio_buttons.append((val, rb))
            first = False
            
        vbox.Add(sbs_options, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        
        # --- AZIONI DI PIANIFICAZIONE E RITIRO ---
        hbox_actions = wx.BoxSizer(wx.HORIZONTAL)
        
        self.btn_schedule = wx.Button(panel, label=_("Pianifica Partita..."))
        self.btn_schedule.Bind(wx.EVT_BUTTON, self.on_schedule)
        
        self.btn_withdraw = wx.Button(panel, label=_("Ritira Giocatore..."))
        self.btn_withdraw.Bind(wx.EVT_BUTTON, self.on_withdraw)
        
        hbox_actions.Add(self.btn_schedule, 1, wx.EXPAND | wx.RIGHT, 10)
        hbox_actions.Add(self.btn_withdraw, 1, wx.EXPAND)
        
        vbox.Add(hbox_actions, 0, wx.EXPAND | wx.ALL, 15)
        
        # --- BOTTONI OK / ANNULLA ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("Annulla"))
        btn_ok = wx.Button(panel, wx.ID_OK, _("Conferma Risultato"))
        btn_ok.SetDefault()
        
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, 10)
        btn_sizer.Add(btn_ok, 0)
        
        vbox.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        
        panel.SetSizer(vbox)
        vbox.Fit(self)

    def apply_theme(self):
        apply_visual_settings(self.lbl_info, self.settings)
        for val, rb in self.radio_buttons:
            apply_visual_settings(rb, self.settings)
        apply_visual_settings(self.btn_schedule, self.settings)
        apply_visual_settings(self.btn_withdraw, self.settings)

    def get_selected_result(self):
        """Restituisce la stringa del risultato selezionato (es. '1-0', '1/2-1/2', etc.)."""
        for val, rb in self.radio_buttons:
            if rb.GetValue():
                return val
        return None

    def on_schedule(self, event):
        # Chiedi Data e Ora
        dlg_date = wx.TextEntryDialog(
            self,
            _("Inserisci la data della partita (AAAA-MM-GG):"),
            _("Pianificazione Partita"),
            self.schedule_info.get("date", "")
        )
        if dlg_date.ShowModal() != wx.ID_OK:
            dlg_date.Destroy()
            return
        date_val = dlg_date.GetValue().strip()
        dlg_date.Destroy()
        
        # Valida data
        from datetime import datetime
        try:
            datetime.strptime(date_val, "%Y-%m-%d")
        except ValueError:
            wx.MessageBox(_("Formato data non valido. Usa AAAA-MM-GG."), _("Errore"), wx.ICON_ERROR)
            return
            
        dlg_time = wx.TextEntryDialog(
            self,
            _("Inserisci l'ora della partita (HH:MM):"),
            _("Pianificazione Partita"),
            self.schedule_info.get("time", "15:00")
        )
        if dlg_time.ShowModal() != wx.ID_OK:
            dlg_time.Destroy()
            return
        time_val = dlg_time.GetValue().strip()
        dlg_time.Destroy()
        
        # Valida ora
        try:
            datetime.strptime(time_val, "%H:%M")
        except ValueError:
            wx.MessageBox(_("Formato ora non valido. Usa HH:MM."), _("Errore"), wx.ICON_ERROR)
            return
            
        self.schedule_info = {"date": date_val, "time": time_val}
        self.selected_action = "schedule"
        self.EndModal(wx.ID_OK)

    def on_withdraw(self, event):
        choices = [
            f"{self.white_name} (ID: {self.white_id})",
            f"{self.black_name} (ID: {self.black_id})"
        ]
        dlg = wx.SingleChoiceDialog(
            self,
            _("Seleziona il giocatore da ritirare definitivamente dal torneo:"),
            _("Ritiro Giocatore"),
            choices
        )
        if dlg.ShowModal() == wx.ID_OK:
            sel = dlg.GetSelection()
            self.withdrawn_player_id = self.white_id if sel == 0 else self.black_id
            self.selected_action = "withdraw"
            self.EndModal(wx.ID_OK)
        dlg.Destroy()
