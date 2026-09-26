import builtins
import webbrowser

import wx
from GBwx import STILE_ADATTABILE, adatta_finestra, pannello_scorrevole

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
            style=STILE_ADATTABILE,
        )

        self.settings = settings
        from utils import play_sound

        play_sound("donazione")
        panel = self.pannello = pannello_scorrevole(self)
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

        # Il pulsante predefinito e' Chiudi, dalla 10.13.32, non piu' Dona
        # con PayPal: INVIO nel testo, dove sta il fuoco all'apertura, preme
        # il predefinito, come nelle finestre di messaggio, ed ESC chiude.
        # Fino alla 10.13.31, dal testo, nessuno dei due chiudeva la
        # finestra. Il browser si apre soltanto con Dona con PayPal.
        btn_close.SetDefault()
        self.pulsante_predefinito = btn_close
        self.SetEscapeId(wx.ID_NO)

        btn_donate.Bind(wx.EVT_BUTTON, self.on_donate)
        btn_close.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_NO))
        self.Bind(wx.EVT_CHAR_HOOK, self._on_tasto)

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

        # Dalla 10.6.3 la misura la da' il contenuto, dentro lo schermo, e
        # 600 per 450 resta come minimo (issue 49).
        adatta_finestra(self, self.pannello, (600, 450))
        wx.CallAfter(self.msg_text.SetFocus)

    def _on_tasto(self, event):
        """INVIO nel testo, un campo multilinea che si tiene il tasto, preme
        Chiudi; sui pulsanti INVIO resta loro, e ogni altro tasto prosegue.
        Un INVIO ripetuto, con il tasto tenuto giu', non preme niente, come
        nelle finestre di messaggio."""
        invio = event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
        if invio and not event.HasAnyModifiers() and not event.IsAutoRepeat() and wx.Window.FindFocus() is self.msg_text:
            self.EndModal(self.pulsante_predefinito.GetId())
            return
        event.Skip()

    def on_donate(self, event):
        # Link personalizzato PayPal.Me dello sviluppatore.
        paypal_url = "https://paypal.me/GabrieleBattaglia780"
        try:
            webbrowser.open(paypal_url)
        except Exception:
            pass
        self.EndModal(wx.ID_YES)
