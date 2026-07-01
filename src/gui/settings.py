import os
import json
import wx
import config

SETTINGS_FILE = config.resource_path("Tornello - Settings.json")

DEFAULT_SETTINGS = {
    "font_size": 12,
    "volume": 50,
    "rgb_text": [0, 100, 0],   # Percentaggi (0-100)
    "rgb_back": [0, 0, 0],     # Percentaggi (0-100)
    "language": "it"
}

def load_settings():
    """Carica le impostazioni globali dal file JSON."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                settings = DEFAULT_SETTINGS.copy()
                settings.update(loaded)
                return settings
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    """Salva le impostazioni globali su file JSON."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4)
    except Exception:
        pass

def pct_to_byte(pct):
    """Converte un valore percentuale (0-100) in byte (0-255)."""
    val = int((pct / 100) * 255)
    return max(0, min(255, val))

def apply_visual_settings(control, settings):
    """Applica font, colore di testo e colore di sfondo a un controllo wxPython per l'accessibilità."""
    fs = settings.get("font_size", 12)
    rgb_text = settings.get("rgb_text", [0, 100, 0])
    rgb_back = settings.get("rgb_back", [0, 0, 0])
    
    fg_col = wx.Colour(pct_to_byte(rgb_text[0]), pct_to_byte(rgb_text[1]), pct_to_byte(rgb_text[2]))
    bg_col = wx.Colour(pct_to_byte(rgb_back[0]), pct_to_byte(rgb_back[1]), pct_to_byte(rgb_back[2]))
    
    font = wx.Font(fs, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
    
    control.SetFont(font)
    control.SetForegroundColour(fg_col)
    control.SetBackgroundColour(bg_col)
    
    if isinstance(control, wx.TextCtrl):
        attr = wx.TextAttr(fg_col, bg_col, font)
        control.SetDefaultStyle(attr)
        # Se c'è del testo, riapplica lo stile su tutta la lunghezza
        if control.GetValue():
            control.SetStyle(0, control.GetLastPosition(), attr)
        
    control.Refresh()
    control.Update()
