import builtins

import wx
from GBwx import STILE_ADATTABILE, adatta_finestra, pannello_scorrevole

_ = getattr(builtins, "_", lambda s: s)


class AccessibleMsgDialog(wx.Dialog):
    """
    Dialogo accessibile personalizzato per Tornello.
    Usa una TextCtrl per il messaggio invece di una StaticText,
    permettendo la navigazione con le frecce (screen reader friendly).
    """

    def __init__(self, parent, title, message, style=wx.OK, settings=None, no_predefinito=False):
        """no_predefinito, con style=wx.YES_NO, fa del No il pulsante
        predefinito e di ESC un No esplicito: serve alle conferme che
        sostituiscono dei file, come il ripristino di una copia di sicurezza
        (10.10.0), dove un INVIO di troppo non deve bastare. Senza, tutto
        resta come prima: predefinito il Si'."""
        super().__init__(
            parent,
            title=title,
            style=STILE_ADATTABILE,
        )

        if settings is None:
            if parent and hasattr(parent, "settings") and parent.settings:
                settings = parent.settings
            else:
                from gui.settings import load_settings

                settings = load_settings()
        self.settings = settings

        panel = self.pannello = pannello_scorrevole(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Area Messaggio (Navigabile con screen reader)
        self.msg_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, value=message
        )

        vbox.Add(self.msg_text, 1, wx.EXPAND | wx.ALL, 10)

        # Bottoni
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Gestione del multilingua per i pulsanti standard
        if style & wx.YES_NO:
            btn_yes = wx.Button(panel, wx.ID_YES, _("Sì"))
            btn_no = wx.Button(panel, wx.ID_NO, _("No"))

            # Imposta default sul NO se richiesto o sul YES
            if no_predefinito:
                btn_no.SetDefault()
                self.SetEscapeId(wx.ID_NO)
            else:
                btn_yes.SetDefault()
            self.pulsante_si, self.pulsante_no = btn_yes, btn_no

            btn_yes.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_YES))
            btn_no.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_NO))

            btn_sizer.Add(btn_yes, 0, wx.RIGHT, 10)
            btn_sizer.Add(btn_no, 0)
        else:  # Default OK
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

        # Dalla 10.6.3 la misura la da' il contenuto, dentro lo schermo, e
        # 600 per 450 resta come minimo (issue 49).
        adatta_finestra(self, self.pannello, (600, 450))

        # Sposta il focus sul controllo di testo all'avvio per attivare la lettura automatica di NVDA
        wx.CallAfter(self.msg_text.SetFocus)
