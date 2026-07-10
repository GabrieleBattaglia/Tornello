# ruff: noqa: E402
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)


import wx
from gui.settings import load_settings
from gui.main_frame import MainFrame

class TornelloApp(wx.App):
    """Classe wx.App principale per Tornello v9."""
    def OnInit(self):
        # Carica le impostazioni globali (lingua, audio, font, colori)
        self.settings = load_settings()
        
        # Inizializza il Frame principale
        self.main_frame = MainFrame(None, title="Tornello", settings=self.settings)
        self.SetTopWindow(self.main_frame)
        self.main_frame.Show()
        return True
