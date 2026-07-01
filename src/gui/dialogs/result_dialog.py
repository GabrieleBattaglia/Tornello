import wx
import builtins
from gui.settings import apply_visual_settings

_ = getattr(builtins, "_", lambda s: s)

class ResultDialog(wx.Dialog):
    """
    Finestra di dialogo modale per inserire o variare il risultato di una partita.
    Presenta opzioni radio verticali ampie e ben spaziate per l'accessibilità con screen reader.
    """
    def __init__(self, parent, white_name, black_name, board_num, current_result, settings):
        title = _("Risultato Scacchiera {num}").format(num=board_num)
        super().__init__(parent, title=title, size=(500, 450))
        
        self.settings = settings
        self.white_name = white_name
        self.black_name = black_name
        self.board_num = board_num
        self.current_result = current_result
        
        self._init_ui()
        self.apply_theme()
        self.Centre()

    def _init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # --- DETTAGLI PARTITA ---
        match_info = (
            f"Scacchiera {self.board_num}:\n"
            f"  {_('Bianco')}: {self.white_name}\n"
            f"  {_('Nero')}: {self.black_name}\n"
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
            sbs_options.Add(rb, 0, wx.ALL | wx.EXPAND, 8)
            self.radio_buttons.append((val, rb))
            first = False
            
        vbox.Add(sbs_options, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        
        # --- BOTTONI OK / ANNULLA ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("Annulla"))
        btn_ok = wx.Button(panel, wx.ID_OK, _("Conferma"))
        btn_ok.SetDefault()
        
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, 10)
        btn_sizer.Add(btn_ok, 0)
        
        vbox.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)
        
        panel.SetSizer(vbox)
        vbox.Fit(self)

    def apply_theme(self):
        apply_visual_settings(self.lbl_info, self.settings)
        for val, rb in self.radio_buttons:
            apply_visual_settings(rb, self.settings)

    def get_selected_result(self):
        """Restituisce la stringa del risultato selezionato (es. '1-0', '1/2-1/2', etc.)."""
        for val, rb in self.radio_buttons:
            if rb.GetValue():
                return val
        return None
