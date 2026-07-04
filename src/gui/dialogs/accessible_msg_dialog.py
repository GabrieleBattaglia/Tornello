import wx
import builtins
_ = getattr(builtins, "_", lambda s: s)

class AccessibleMsgDialog(wx.Dialog):
    """
    Dialogo accessibile personalizzato per Tornello.
    Usa una TextCtrl per il messaggio invece di una StaticText,
    permettendo la navigazione con le frecce (screen reader friendly).
    """
    def __init__(self, parent, title, message, style=wx.OK, settings=None):
        super().__init__(parent, title=title, size=(600, 450), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
        if settings is None:
            if parent and hasattr(parent, "settings") and parent.settings:
                settings = parent.settings
            else:
                from gui.settings import load_settings
                settings = load_settings()
        self.settings = settings
        
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Area Messaggio (Navigabile con screen reader)
        self.msg_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, value=message)
        
        vbox.Add(self.msg_text, 1, wx.EXPAND | wx.ALL, 10)
        
        # Bottoni
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Gestione del multilingua per i pulsanti standard
        if style & wx.YES_NO:
            btn_yes = wx.Button(panel, wx.ID_YES, _("Sì"))
            btn_no = wx.Button(panel, wx.ID_NO, _("No"))
            
            # Imposta default sul NO se richiesto o sul YES
            btn_yes.SetDefault()

            btn_yes.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_YES))
            btn_no.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_NO))

            btn_sizer.Add(btn_yes, 0, wx.RIGHT, 10)
            btn_sizer.Add(btn_no, 0)
        else: # Default OK
            btn_ok = wx.Button(panel, wx.ID_OK, _("OK"))
            btn_ok.SetDefault()
            btn_ok.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_OK))
            btn_sizer.Add(btn_ok, 0)

        vbox.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 15)

        panel.SetSizer(vbox)
        
        # Applica impostazioni visive di accessibilità
        from gui.settings import apply_visual_settings
        apply_visual_settings(self, self.settings)
        apply_visual_settings(panel, self.settings)
        apply_visual_settings(self.msg_text, self.settings)
        if style & wx.YES_NO:
            apply_visual_settings(btn_yes, self.settings)
            apply_visual_settings(btn_no, self.settings)
        else:
            apply_visual_settings(btn_ok, self.settings)
            
        self.Centre()

        # Sposta il focus sul controllo di testo all'avvio per attivare la lettura automatica di NVDA
        wx.CallAfter(self.msg_text.SetFocus)
