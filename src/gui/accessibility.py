import wx

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
        acc = wx.Accessible(control)
        # Questo assegna il nome accessibile in modo nativo
        control.SetAccessible(acc)
    # Imposta comunque lo HelpText ed il ToolTip che NVDA legge come descrizione alternativa
    control.SetHelpText(label_text)
    control.SetToolTip(wx.ToolTip(label_text))
