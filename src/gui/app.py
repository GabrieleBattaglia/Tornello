import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)


import wx

from gui.main_frame import MainFrame
from gui.settings import load_settings


class TornelloApp(wx.App):
    """Classe wx.App principale per Tornello v9."""

    def OnInit(self):
        # Carica le impostazioni globali (lingua, audio, font, colori)
        self.settings = load_settings()

        # Inizializza il Frame principale
        self.main_frame = MainFrame(None, title="Tornello", settings=self.settings)
        self.SetTopWindow(self.main_frame)
        self.main_frame.Show()
        self.main_frame.Raise()
        return True

    def FilterEvent(self, event):
        """Un INVIO tenuto giu' vale una volta sola, in tutto il programma,
        dalla 10.13.43. Il filtro vede ogni evento prima di finestre e
        controlli, e scarta gli INVIO ripetuti, cioe' quelli che Windows
        manda mentre il tasto resta premuto: scartato il gancio dei tasti,
        Windows non consegna il tasto a nessuno. Fino alla 10.13.42 l'albero
        riattivava la voce a ogni ripetizione, e le liste della composizione
        manuale aggiungevano una coppia dopo l'altra.
        Il limite: nei campi di testo NVDA si prende l'INVIO e ne rimanda
        ogni ripetizione con un rilascio e una pressione nuova
        (KeyboardInputGesture.send, per lo script caret_newLine), e qui
        arriva come un INVIO non ripetuto. Riconoscerlo dal tempo avrebbe
        fatto ignorare anche due INVIO voluti e ravvicinati: Gabriele ha
        scelto di lasciare cosi', il 27 settembre 2026."""
        if (
            event.GetEventType() == wx.wxEVT_CHAR_HOOK
            and event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
            and event.IsAutoRepeat()
        ):
            return self.Event_Processed
        return self.Event_Skip
