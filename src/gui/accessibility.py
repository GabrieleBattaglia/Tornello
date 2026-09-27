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


class NomeAccessibile(wx.Accessible):
    """Il nome che lo screen reader legge per un controllo senza etichetta
    davanti. Windows lo ricava dal fratello che precede il controllo: dalla
    10.6.4 i controlli dei riquadri sono figli del loro StaticBox (issue 49),
    e il primo di ogni riquadro, se non ha un testo suo, restava senza nome,
    mentre prima lo prendeva dal riquadro. Si legge a ogni richiesta: chi
    cambia l'etichetta da cui viene aggiorna anche l'attributo nome.
    Per le voci di una lista, e per le altre parti del controllo, risponde
    ACC_NOT_IMPLEMENTED: wx lo chiede allora al controllo di Windows, e le
    voci tengono il loro testo. Con ACC_NOT_SUPPORTED, come fa CustomAccessible,
    wx le lascerebbe senza nome.
    Ruolo, stato e valore li chiede anch'esso all'oggetto standard di Windows
    per la classe della finestra: per campi, liste e caselle combinate e'
    quello di sempre, per un TextCtrl ricco no, e serve NomeAccessibileTesto."""

    def __init__(self, win, nome):
        super().__init__(win)
        self.nome = nome

    def GetName(self, childId):
        if childId != wx.ACC_SELF:
            return wx.ACC_NOT_IMPLEMENTED, ""
        return wx.ACC_OK, self.nome


class NomeAccessibileTesto(NomeAccessibile):
    """NomeAccessibile per un TextCtrl con TE_RICH o TE_RICH2. Senza oggetto
    di wx il controllo, un RICHEDIT50W, risponde con un oggetto suo: ruolo
    testo, sola lettura se non si modifica, e il testo come valore. Con un
    oggetto di wx, per cio' che questo non dice, Windows non ha un oggetto
    standard adatto e ne da' uno generico, con ruolo client, senza sola
    lettura e senza valore; qui si rimettono i tre dati del controllo."""

    def GetRole(self, childId):
        if childId != wx.ACC_SELF:
            return wx.ACC_NOT_IMPLEMENTED, 0
        return wx.ACC_OK, wx.ROLE_SYSTEM_TEXT

    def GetState(self, childId):
        if childId != wx.ACC_SELF:
            return wx.ACC_NOT_IMPLEMENTED, 0
        win = self.GetWindow()
        stato = wx.ACC_STATE_SYSTEM_FOCUSABLE
        if wx.Window.FindFocus() is win:
            stato |= wx.ACC_STATE_SYSTEM_FOCUSED
        if not win.IsEditable():
            stato |= wx.ACC_STATE_SYSTEM_READONLY
        if not win.IsShownOnScreen():
            stato |= wx.ACC_STATE_SYSTEM_INVISIBLE
        return wx.ACC_OK, stato

    def GetValue(self, childId):
        if childId != wx.ACC_SELF:
            return wx.ACC_NOT_IMPLEMENTED, ""
        return wx.ACC_OK, self.GetWindow().GetValue()


def announce_text_to_screen_reader(text):
    """
    Invia un annuncio testuale allo screen reader se supportato.
    Su Windows, utilizza il motore wx.Accessibility se disponibile.
    Per semplicità ed elevata compatibilità, ci affidiamo anche al focus dei controlli.
    """


def set_accessibility_label(control, label_text):
    """
    Associa un'etichetta descrittiva ad un controllo per gli screen reader.
    """
    if hasattr(control, "SetAccessible"):
        control.SetAccessible(CustomAccessible(control, label_text))
    # Imposta comunque lo HelpText ed il ToolTip che NVDA legge come descrizione alternativa
    control.SetHelpText(label_text)
    control.SetToolTip(wx.ToolTip(label_text))
