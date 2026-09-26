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
        predefinito: serve alle conferme che sostituiscono dei file, come il
        ripristino di una copia di sicurezza (10.10.0), dove un INVIO di
        troppo non deve bastare. Senza, predefinito il Si'. ESC vale No in
        tutte le domande, con o senza no_predefinito, dalla 10.13.23."""
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
            else:
                btn_yes.SetDefault()
            self.pulsante_si, self.pulsante_no = btn_yes, btn_no
            self.pulsante_predefinito = btn_no if no_predefinito else btn_yes
            # ESC risponde No in tutte le domande, dalla 10.13.23: senza un
            # pulsante Annulla o OK wx non sapeva che cosa farne, e la domanda
            # restava aperta, per esempio Finalizza Torneo o Turni consigliati.
            # No non esegue mai l'azione proposta, ma non sempre lascia tutto
            # com'e': nella Pulizia Backup Consigliata rinvia il controllo di
            # 18 mesi, e nel torneo che non potrebbe proseguire porta alla
            # domanda sull'eliminazione. ESC fa lo stesso.
            self.SetEscapeId(wx.ID_NO)

            btn_yes.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_YES))
            btn_no.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_NO))

            btn_sizer.Add(btn_yes, 0, wx.RIGHT, 10)
            btn_sizer.Add(btn_no, 0)
        else:  # Default OK
            btn_ok = wx.Button(panel, wx.ID_OK, _("OK"))
            btn_ok.SetDefault()
            btn_ok.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_OK))
            btn_sizer.Add(btn_ok, 0)
            self.pulsante_predefinito = btn_ok
            # Con il solo OK, ESC chiude: wx lo faceva gia' da se', e qui lo
            # si dice in modo esplicito, come nelle domande.
            self.SetEscapeId(wx.ID_OK)

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

        self.Bind(wx.EVT_CHAR_HOOK, self._on_tasto)

        # Sposta il focus sul controllo di testo all'avvio per attivare la lettura automatica di NVDA
        wx.CallAfter(self.msg_text.SetFocus)

    def _on_tasto(self, event):
        """INVIO nel testo preme il pulsante predefinito, dalla 10.13.23: Si',
        No con no_predefinito, oppure OK. Il testo e' un campo multilinea,
        che si tiene il tasto anche in sola lettura, e fino alla 10.13.22 la
        finestra restava aperta. E' lo stesso rimedio della finestra
        dell'aggiornamento. Sui pulsanti INVIO resta loro e preme quello che
        ha il fuoco; ogni altro tasto prosegue: le frecce leggono il testo, ed
        ESC lo traduce wx nel pulsante di SetEscapeId.
        Un INVIO ripetuto, cioe' il tasto tenuto giu', non preme niente: chi
        apre la domanda con INVIO, per esempio dall'albero, e lo tiene un
        attimo di troppo, non deve rispondere Si' senza averla letta."""
        invio = event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
        if invio and not event.HasAnyModifiers() and not event.IsAutoRepeat() and wx.Window.FindFocus() is self.msg_text:
            self.EndModal(self.pulsante_predefinito.GetId())
            return
        event.Skip()
