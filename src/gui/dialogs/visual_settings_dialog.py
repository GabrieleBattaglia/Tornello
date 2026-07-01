import wx
import builtins
from utils import play_sound
from gui.settings import apply_visual_settings

_ = getattr(builtins, "_", lambda s: s)

class VisualSettingsDialog(wx.Dialog):
    """
    Finestra di dialogo per la gestione delle impostazioni Audio, Video e Lingua.
    Garantisce un'interfaccia accessibile e testabile con anteprima in tempo reale.
    """
    def __init__(self, parent, current_settings):
        title = _("Impostazioni (Audio/Video/Lingua)")
        super().__init__(parent, title=title, size=(550, 750))
        
        self.settings = current_settings.copy()
        
        # Valori di default
        self.default_rgb_text = [0, 100, 0]  # Verde brillante (monocromatico terminale)
        self.default_rgb_back = [0, 0, 0]    # Nero
        self.default_size = 12
        self.default_volume = 50
        self.default_lang = "it"
        
        self._init_ui()
        self._update_preview()
        self.Centre()

    def _init_ui(self):
        panel = wx.Panel(self)
        main_vbox = wx.BoxSizer(wx.VERTICAL)
        
        # --- ANTEPRIMA ---
        preview_label = _("Anteprima Visuale")
        sb_preview = wx.StaticBox(panel, label=preview_label)
        sbs_preview = wx.StaticBoxSizer(sb_preview, wx.VERTICAL)
        
        preview_val = "Tornello v9.0\n> " + _("Sistema pronto ed accessibile.")
        self.preview_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(-1, 80))
        self.preview_text.SetValue(preview_val)
        
        sbs_preview.Add(self.preview_text, 1, wx.EXPAND | wx.ALL, 5)
        main_vbox.Add(sbs_preview, 0, wx.EXPAND | wx.ALL, 10)
        
        # --- LINGUA ---
        lang_label = _("Lingua (Language)")
        sb_lang = wx.StaticBox(panel, label=lang_label)
        sbs_lang = wx.StaticBoxSizer(sb_lang, wx.VERTICAL)
        
        self.choice_lang = wx.Choice(panel, choices=["Italiano", "English"])
        current_lang = self.settings.get("language", "it")
        self.choice_lang.SetSelection(0 if current_lang == "it" else 1)
        
        sbs_lang.Add(self.choice_lang, 0, wx.EXPAND | wx.ALL, 5)
        main_vbox.Add(sbs_lang, 0, wx.EXPAND | wx.ALL, 10)
        
        # --- AUDIO ---
        audio_label = _("Audio")
        sb_audio = wx.StaticBox(panel, label=audio_label)
        sbs_audio = wx.StaticBoxSizer(sb_audio, wx.VERTICAL)
        
        hbox_vol = wx.BoxSizer(wx.HORIZONTAL)
        vol_text = _("Volume Master (%):")
        hbox_vol.Add(wx.StaticText(panel, label=vol_text), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        
        self.slider_vol = wx.Slider(panel, value=self.settings.get("volume", 50), minValue=0, maxValue=100, style=wx.SL_HORIZONTAL | wx.SL_LABELS)
        self.slider_vol.Bind(wx.EVT_SLIDER, self.on_volume_change)
        
        hbox_vol.Add(self.slider_vol, 1, wx.EXPAND)
        sbs_audio.Add(hbox_vol, 1, wx.EXPAND | wx.ALL, 5)
        main_vbox.Add(sbs_audio, 0, wx.EXPAND | wx.ALL, 10)
        
        # --- CONTROLLI VIDEO (Grid) ---
        controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Colonna 1: Testo
        text_ctrl_label = _("Testo")
        sb_text = wx.StaticBox(panel, label=text_ctrl_label)
        sbs_text = wx.StaticBoxSizer(sb_text, wx.VERTICAL)
        grid_text = wx.FlexGridSizer(rows=4, cols=2, vgap=10, hgap=10)
        
        size_label = _("Dimensione (pt):")
        grid_text.Add(wx.StaticText(panel, label=size_label), 0, wx.ALIGN_CENTER_VERTICAL)
        self.spin_size = wx.SpinCtrl(panel, min=8, max=72, initial=self.settings.get("font_size", 12))
        self.spin_size.Bind(wx.EVT_SPINCTRL, self.on_change)
        self.spin_size.Bind(wx.EVT_TEXT, self.on_change)
        grid_text.Add(self.spin_size, 0, wx.EXPAND)
        
        curr_text = self.settings.get("rgb_text", [0, 100, 0])
        
        red_label = _("Rosso (%):")
        green_label = _("Verde (%):")
        blue_label = _("Blu (%):")
        
        grid_text.Add(wx.StaticText(panel, label=red_label), 0, wx.ALIGN_CENTER_VERTICAL)
        self.spin_tr = wx.SpinCtrl(panel, min=0, max=100, initial=curr_text[0])
        self.spin_tr.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_text.Add(self.spin_tr, 0, wx.EXPAND)

        grid_text.Add(wx.StaticText(panel, label=green_label), 0, wx.ALIGN_CENTER_VERTICAL)
        self.spin_tg = wx.SpinCtrl(panel, min=0, max=100, initial=curr_text[1])
        self.spin_tg.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_text.Add(self.spin_tg, 0, wx.EXPAND)

        grid_text.Add(wx.StaticText(panel, label=blue_label), 0, wx.ALIGN_CENTER_VERTICAL)
        self.spin_tb = wx.SpinCtrl(panel, min=0, max=100, initial=curr_text[2])
        self.spin_tb.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_text.Add(self.spin_tb, 0, wx.EXPAND)
        
        sbs_text.Add(grid_text, 1, wx.EXPAND | wx.ALL, 5)
        controls_sizer.Add(sbs_text, 1, wx.EXPAND | wx.ALL, 5)
        
        # Colonna 2: Sfondo
        back_ctrl_label = _("Sfondo")
        sb_back = wx.StaticBox(panel, label=back_ctrl_label)
        sbs_back = wx.StaticBoxSizer(sb_back, wx.VERTICAL)
        grid_back = wx.FlexGridSizer(rows=4, cols=2, vgap=10, hgap=10)
        
        curr_back = self.settings.get("rgb_back", [0, 0, 0])
        
        grid_back.Add(wx.StaticText(panel, label=""), 0) 
        grid_back.Add(wx.StaticText(panel, label=""), 0)

        grid_back.Add(wx.StaticText(panel, label=red_label), 0, wx.ALIGN_CENTER_VERTICAL)
        self.spin_br = wx.SpinCtrl(panel, min=0, max=100, initial=curr_back[0])
        self.spin_br.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_back.Add(self.spin_br, 0, wx.EXPAND)

        grid_back.Add(wx.StaticText(panel, label=green_label), 0, wx.ALIGN_CENTER_VERTICAL)
        self.spin_bg = wx.SpinCtrl(panel, min=0, max=100, initial=curr_back[1])
        self.spin_bg.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_back.Add(self.spin_bg, 0, wx.EXPAND)

        grid_back.Add(wx.StaticText(panel, label=blue_label), 0, wx.ALIGN_CENTER_VERTICAL)
        self.spin_bb = wx.SpinCtrl(panel, min=0, max=100, initial=curr_back[2])
        self.spin_bb.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_back.Add(self.spin_bb, 0, wx.EXPAND)
        
        sbs_back.Add(grid_back, 1, wx.EXPAND | wx.ALL, 5)
        controls_sizer.Add(sbs_back, 1, wx.EXPAND | wx.ALL, 5)

        main_vbox.Add(controls_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        # --- BOTTONI ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        reset_text = _("Reset Default")
        btn_reset = wx.Button(panel, label=reset_text)
        btn_reset.Bind(wx.EVT_BUTTON, self.on_reset)
        btn_sizer.Add(btn_reset, 0, wx.RIGHT, 10)
        
        btn_sizer.AddStretchSpacer()
        
        cancel_text = _("Annulla")
        ok_text = _("OK")
        
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, cancel_text)
        btn_ok = wx.Button(panel, wx.ID_OK, ok_text)
        btn_ok.SetDefault()
        
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, 10)
        btn_sizer.Add(btn_ok, 0)
        
        main_vbox.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        panel.SetSizer(main_vbox)
        main_vbox.Fit(self)

    def on_change(self, event):
        self._update_preview()

    def on_volume_change(self, event):
        val = self.slider_vol.GetValue()
        # Salva temporaneamente il volume per play_sound
        import json
        import os
        settings_path = os.path.join(os.path.abspath("."), "Tornello - Settings.json")
        try:
            temp_settings = {}
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    temp_settings = json.load(f)
            temp_settings["volume"] = val
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(temp_settings, f, indent=4)
        except Exception:
            pass
        # Riproduci un suono di test
        play_sound("notifica")

    def on_reset(self, event):
        self.spin_size.SetValue(self.default_size)
        self.slider_vol.SetValue(self.default_volume)
        self.choice_lang.SetSelection(0) # Default Italiano
        
        self.spin_tr.SetValue(self.default_rgb_text[0])
        self.spin_tg.SetValue(self.default_rgb_text[1])
        self.spin_tb.SetValue(self.default_rgb_text[2])
        
        self.spin_br.SetValue(self.default_rgb_back[0])
        self.spin_bg.SetValue(self.default_rgb_back[1])
        self.spin_bb.SetValue(self.default_rgb_back[2])
        
        self.on_volume_change(None)
        self._update_preview()

    def _get_current_values(self):
        size = self.spin_size.GetValue()
        vol = self.slider_vol.GetValue()
        
        tr = self.spin_tr.GetValue()
        tg = self.spin_tg.GetValue()
        tb = self.spin_tb.GetValue()
        
        br = self.spin_br.GetValue()
        bg = self.spin_bg.GetValue()
        bb = self.spin_bb.GetValue()
        
        return size, vol, [tr, tg, tb], [br, bg, bb]

    def _update_preview(self):
        size, vol, text_rgb, back_rgb = self._get_current_values()
        
        temp_settings = {
            "font_size": size,
            "rgb_text": text_rgb,
            "rgb_back": back_rgb
        }
        apply_visual_settings(self.preview_text, temp_settings)

    def get_settings(self):
        size, vol, text_rgb, back_rgb = self._get_current_values()
        lang_idx = self.choice_lang.GetSelection()
        lang_val = "it" if lang_idx == 0 else "en"
        return {
            "font_size": size,
            "volume": vol,
            "rgb_text": text_rgb,
            "rgb_back": back_rgb,
            "language": lang_val
        }
