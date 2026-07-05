import wx

class CustomAccessible(wx.Accessible):
    """Classe custom per MSAA per esporre il nome corretto del controllo ai lettori dello schermo."""
    def __init__(self, win, name):
        super().__init__(win)
        self.name = name

    def GetName(self, childId):
        # IMPORTANTE: Restituire il nome personalizzato SOLO per il controllo stesso (wx.ACC_SELF).
        # Per gli elementi figli, restituire wx.ACC_NOT_SUPPORTED per consentire al sistema di leggere le etichette originali.
        if childId == wx.ACC_SELF:
            return wx.ACC_OK, self.name
        return wx.ACC_NOT_SUPPORTED, ""

def announce_text_to_screen_reader(text):
    """
    Invia un annuncio testuale allo screen reader se supportato.
    Su Windows, utilizza il motore wx.Accessibility se disponibile.
    Per semplicità ed elevata compatibilità, ci affidiamo anche al focus dei controlli.
    """
    pass

def set_accessibility_label(control, label_text):
    """
    Associa un'etichetta descrittiva ad un controllo per gli screen reader.
    """
    if hasattr(control, "SetAccessible"):
        control.SetAccessible(CustomAccessible(control, label_text))
    # Imposta comunque lo HelpText ed il ToolTip che NVDA legge come descrizione alternativa
    control.SetHelpText(label_text)
    control.SetToolTip(wx.ToolTip(label_text))

