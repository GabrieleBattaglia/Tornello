import wx
import builtins
import webbrowser
from gui.settings import apply_visual_settings

_ = getattr(builtins, "_", lambda s: s)


class DonationDialog(wx.Dialog):
    """
    Dialogo accessibile personalizzato per mostrare il messaggio di donazione.
    Contiene un'area di testo navigabile, un pulsante per donare ed uno per chiudere.
    """

    def __init__(self, parent, title, message, settings=None):
        super().__init__(
            parent,
            title=title,
            size=(600, 450),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.settings = settings
        from utils import play_sound

        play_sound("donazione")
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Area Messaggio (Navigabile con screen reader)
        self.msg_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, value=message
        )

        vbox.Add(self.msg_text, 1, wx.EXPAND | wx.ALL, 10)

        # Bottoni
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        btn_donate = wx.Button(panel, wx.ID_YES, _("Dona con PayPal"))
        btn_close = wx.Button(panel, wx.ID_NO, _("Chiudi"))

        btn_donate.SetDefault()

        btn_donate.Bind(wx.EVT_BUTTON, self.on_donate)
        btn_close.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_NO))

        btn_sizer.Add(btn_donate, 0, wx.RIGHT, 10)
        btn_sizer.Add(btn_close, 0)

        vbox.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 15)
        panel.SetSizer(vbox)

        # Applica impostazioni visive di accessibilità
        if self.settings:
            apply_visual_settings(self, self.settings)
            apply_visual_settings(panel, self.settings)
            apply_visual_settings(self.msg_text, self.settings)
            apply_visual_settings(btn_donate, self.settings)
            apply_visual_settings(btn_close, self.settings)
        else:
            font = wx.Font(
                11, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
            )
            self.msg_text.SetFont(font)

        self.Centre()
        wx.CallAfter(self.msg_text.SetFocus)

    def on_donate(self, event):
        # Link personalizzato PayPal.Me dello sviluppatore.
        paypal_url = "https://paypal.me/GabrieleBattaglia780"
        try:
            webbrowser.open(paypal_url)
        except Exception:
            pass
        self.EndModal(wx.ID_YES)
