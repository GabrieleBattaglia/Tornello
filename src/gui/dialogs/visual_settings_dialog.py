import os
import wx
import builtins
from utils import play_sound
from gui.settings import apply_visual_settings
from config import resource_path
from version import __version__

_ = getattr(builtins, "_", lambda s: s)


class VisualSettingsDialog(wx.Dialog):
    """
    Finestra di dialogo per la gestione delle impostazioni Audio, Video e Lingua.
    Suddivisa in Tab (wx.Notebook) con anteprima in tempo reale e accessibilità garantita.
    """

    def __init__(self, parent, current_settings):
        title = _("Impostazioni (Audio/Video/Lingua)")
        super().__init__(parent, title=title, size=(550, 750))

        self.settings = current_settings.copy()

        # Valori di default
        self.default_rgb_text = [0, 100, 0]  # Verde brillante
        self.default_dialog_rgb_text = [0, 100, 0]
        self.default_rgb_back = [0, 0, 0]  # Nero
        self.default_dialog_rgb_back = [0, 0, 0]
        self.default_size = 12
        self.default_dialog_size = 12
        self.default_volume = 50
        self.default_lang = "it"

        # Scansione dinamica delle lingue disponibili
        self.lang_codes = ["it"]
        locales_dir = resource_path("locales")
        if os.path.exists(locales_dir):
            for item in os.listdir(locales_dir):
                item_path = os.path.join(locales_dir, item)
                if os.path.isdir(item_path):
                    mo_file = os.path.join(item_path, "LC_MESSAGES", "messages.mo")
                    if os.path.exists(mo_file):
                        self.lang_codes.append(item)

        self.LANG_NAMES = {
            "it": "Italiano",
            "en": "English",
            "es": "Español",
            "fr": "Français",
            "pt": "Português",
            "de": "Deutsch",
            "ru": "Русский",
            "zh": "中文",
        }

        self.lang_choices = [
            self.LANG_NAMES.get(code, code.upper()) for code in self.lang_codes
        ]

        self._init_ui()
        self._update_preview()
        self.Centre()

    def _init_ui(self):
        panel = wx.Panel(self)
        main_vbox = wx.BoxSizer(wx.VERTICAL)

        # --- ANTEPRIMA (Sempre visibile in alto) ---
        preview_label = _("Anteprima Visuale")
        sb_preview = wx.StaticBox(panel, label=preview_label)
        sb_sizer = wx.StaticBoxSizer(sb_preview, wx.VERTICAL)

        preview_val = (
            _("Tornello v{}").format(__version__)
            + "\n> "
            + _("Sistema pronto ed accessibile.")
        )
        self.preview_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(-1, 80)
        )
        self.preview_text.SetValue(preview_val)
        sb_sizer.Add(self.preview_text, 1, wx.EXPAND | wx.ALL, 5)
        main_vbox.Add(sb_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # --- NOTEBOOK PER I TABS ---
        self.notebook = wx.Notebook(panel)

        # 1. TAB: AUDIO E LINGUA
        tab_audio = wx.Panel(self.notebook)
        vbox_audio = wx.BoxSizer(wx.VERTICAL)

        sb_lang = wx.StaticBox(tab_audio, label=_("Lingua (Language)"))
        sbs_lang = wx.StaticBoxSizer(sb_lang, wx.VERTICAL)
        self.choice_lang = wx.Choice(tab_audio, choices=self.lang_choices)
        current_lang = self.settings.get("language", "it")
        if current_lang in self.lang_codes:
            self.choice_lang.SetSelection(self.lang_codes.index(current_lang))
        else:
            self.choice_lang.SetSelection(0)
        sbs_lang.Add(self.choice_lang, 0, wx.EXPAND | wx.ALL, 5)
        vbox_audio.Add(sbs_lang, 0, wx.EXPAND | wx.ALL, 10)

        sb_audio = wx.StaticBox(tab_audio, label=_("Audio"))
        sbs_audio = wx.StaticBoxSizer(sb_audio, wx.VERTICAL)
        hbox_vol = wx.BoxSizer(wx.HORIZONTAL)
        hbox_vol.Add(
            wx.StaticText(tab_audio, label=_("Volume Master (%):")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self.slider_vol = wx.Slider(
            tab_audio,
            value=self.settings.get("volume", 50),
            minValue=0,
            maxValue=100,
            style=wx.SL_HORIZONTAL | wx.SL_LABELS,
        )
        self.slider_vol.Bind(wx.EVT_SLIDER, self.on_volume_change)
        hbox_vol.Add(self.slider_vol, 1, wx.EXPAND)
        sbs_audio.Add(hbox_vol, 1, wx.EXPAND | wx.ALL, 5)
        vbox_audio.Add(sbs_audio, 0, wx.EXPAND | wx.ALL, 10)

        tab_audio.SetSizer(vbox_audio)
        self.notebook.AddPage(tab_audio, _("Audio e Lingua"))

        # 2. TAB: CARATTERI
        tab_font = wx.Panel(self.notebook)
        vbox_font = wx.BoxSizer(wx.VERTICAL)

        sb_font_main = wx.StaticBox(tab_font, label=_("Caratteri finestra principale"))
        sbs_font_main = wx.StaticBoxSizer(sb_font_main, wx.VERTICAL)
        hbox_fm = wx.BoxSizer(wx.HORIZONTAL)
        hbox_fm.Add(
            wx.StaticText(tab_font, label=_("Dimensione (pt):")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self.spin_size = wx.SpinCtrl(
            tab_font, min=8, max=72, initial=self.settings.get("font_size", 12)
        )
        self.spin_size.Bind(wx.EVT_SPINCTRL, self.on_change)
        self.spin_size.Bind(wx.EVT_TEXT, self.on_change)
        hbox_fm.Add(self.spin_size, 1, wx.EXPAND)
        sbs_font_main.Add(hbox_fm, 0, wx.EXPAND | wx.ALL, 5)
        vbox_font.Add(sbs_font_main, 0, wx.EXPAND | wx.ALL, 10)

        sb_font_dlg = wx.StaticBox(tab_font, label=_("Caratteri finestre di dialogo"))
        sbs_font_dlg = wx.StaticBoxSizer(sb_font_dlg, wx.VERTICAL)
        hbox_fd = wx.BoxSizer(wx.HORIZONTAL)
        hbox_fd.Add(
            wx.StaticText(tab_font, label=_("Dimensione (pt):")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self.spin_dialog_size = wx.SpinCtrl(
            tab_font, min=8, max=72, initial=self.settings.get("dialog_font_size", 12)
        )
        self.spin_dialog_size.Bind(wx.EVT_SPINCTRL, self.on_change)
        self.spin_dialog_size.Bind(wx.EVT_TEXT, self.on_change)
        hbox_fd.Add(self.spin_dialog_size, 1, wx.EXPAND)
        sbs_font_dlg.Add(hbox_fd, 0, wx.EXPAND | wx.ALL, 5)
        vbox_font.Add(sbs_font_dlg, 0, wx.EXPAND | wx.ALL, 10)

        tab_font.SetSizer(vbox_font)
        self.notebook.AddPage(tab_font, _("Caratteri"))

        red_label = _("Rosso (%):")
        green_label = _("Verde (%):")
        blue_label = _("Blu (%):")

        # 3. TAB: COLORI DI PRIMO PIANO
        tab_fg = wx.Panel(self.notebook)
        vbox_fg = wx.BoxSizer(wx.VERTICAL)

        sb_fg_main = wx.StaticBox(tab_fg, label=_("Colore testo finestra principale"))
        sbs_fg_main = wx.StaticBoxSizer(sb_fg_main, wx.VERTICAL)
        grid_fg_m = wx.FlexGridSizer(rows=3, cols=2, vgap=10, hgap=10)
        curr_text = self.settings.get("rgb_text", [0, 100, 0])

        grid_fg_m.Add(
            wx.StaticText(tab_fg, label=red_label), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.spin_tr = wx.SpinCtrl(tab_fg, min=0, max=100, initial=curr_text[0])
        self.spin_tr.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_fg_m.Add(self.spin_tr, 1, wx.EXPAND)

        grid_fg_m.Add(
            wx.StaticText(tab_fg, label=green_label), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.spin_tg = wx.SpinCtrl(tab_fg, min=0, max=100, initial=curr_text[1])
        self.spin_tg.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_fg_m.Add(self.spin_tg, 1, wx.EXPAND)

        grid_fg_m.Add(
            wx.StaticText(tab_fg, label=blue_label), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.spin_tb = wx.SpinCtrl(tab_fg, min=0, max=100, initial=curr_text[2])
        self.spin_tb.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_fg_m.Add(self.spin_tb, 1, wx.EXPAND)

        grid_fg_m.AddGrowableCol(1)
        sbs_fg_main.Add(grid_fg_m, 1, wx.EXPAND | wx.ALL, 5)
        vbox_fg.Add(sbs_fg_main, 0, wx.EXPAND | wx.ALL, 10)

        sb_fg_dlg = wx.StaticBox(tab_fg, label=_("Colore testo finestre di dialogo"))
        sbs_fg_dlg = wx.StaticBoxSizer(sb_fg_dlg, wx.VERTICAL)
        grid_fg_d = wx.FlexGridSizer(rows=3, cols=2, vgap=10, hgap=10)
        curr_dlg_text = self.settings.get("dialog_rgb_text", [0, 100, 0])

        grid_fg_d.Add(
            wx.StaticText(tab_fg, label=red_label), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.spin_dialog_tr = wx.SpinCtrl(
            tab_fg, min=0, max=100, initial=curr_dlg_text[0]
        )
        self.spin_dialog_tr.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_fg_d.Add(self.spin_dialog_tr, 1, wx.EXPAND)

        grid_fg_d.Add(
            wx.StaticText(tab_fg, label=green_label), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.spin_dialog_tg = wx.SpinCtrl(
            tab_fg, min=0, max=100, initial=curr_dlg_text[1]
        )
        self.spin_dialog_tg.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_fg_d.Add(self.spin_dialog_tg, 1, wx.EXPAND)

        grid_fg_d.Add(
            wx.StaticText(tab_fg, label=blue_label), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.spin_dialog_tb = wx.SpinCtrl(
            tab_fg, min=0, max=100, initial=curr_dlg_text[2]
        )
        self.spin_dialog_tb.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_fg_d.Add(self.spin_dialog_tb, 1, wx.EXPAND)

        grid_fg_d.AddGrowableCol(1)
        sbs_fg_dlg.Add(grid_fg_d, 1, wx.EXPAND | wx.ALL, 5)
        vbox_fg.Add(sbs_fg_dlg, 0, wx.EXPAND | wx.ALL, 10)

        tab_fg.SetSizer(vbox_fg)
        self.notebook.AddPage(tab_fg, _("Colori di primo piano"))

        # 4. TAB: COLORI DI SFONDO
        tab_bg = wx.Panel(self.notebook)
        vbox_bg = wx.BoxSizer(wx.VERTICAL)

        sb_bg_main = wx.StaticBox(tab_bg, label=_("Colore sfondo finestra principale"))
        sbs_bg_main = wx.StaticBoxSizer(sb_bg_main, wx.VERTICAL)
        grid_bg_m = wx.FlexGridSizer(rows=3, cols=2, vgap=10, hgap=10)
        curr_back = self.settings.get("rgb_back", [0, 0, 0])

        grid_bg_m.Add(
            wx.StaticText(tab_bg, label=red_label), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.spin_br = wx.SpinCtrl(tab_bg, min=0, max=100, initial=curr_back[0])
        self.spin_br.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_bg_m.Add(self.spin_br, 1, wx.EXPAND)

        grid_bg_m.Add(
            wx.StaticText(tab_bg, label=green_label), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.spin_bg = wx.SpinCtrl(tab_bg, min=0, max=100, initial=curr_back[1])
        self.spin_bg.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_bg_m.Add(self.spin_bg, 1, wx.EXPAND)

        grid_bg_m.Add(
            wx.StaticText(tab_bg, label=blue_label), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.spin_bb = wx.SpinCtrl(tab_bg, min=0, max=100, initial=curr_back[2])
        self.spin_bb.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_bg_m.Add(self.spin_bb, 1, wx.EXPAND)

        grid_bg_m.AddGrowableCol(1)
        sbs_bg_main.Add(grid_bg_m, 1, wx.EXPAND | wx.ALL, 5)
        vbox_bg.Add(sbs_bg_main, 0, wx.EXPAND | wx.ALL, 10)

        sb_bg_dlg = wx.StaticBox(tab_bg, label=_("Colore sfondo finestre di dialogo"))
        sbs_bg_dlg = wx.StaticBoxSizer(sb_bg_dlg, wx.VERTICAL)
        grid_bg_d = wx.FlexGridSizer(rows=3, cols=2, vgap=10, hgap=10)
        curr_dlg_back = self.settings.get("dialog_rgb_back", [0, 0, 0])

        grid_bg_d.Add(
            wx.StaticText(tab_bg, label=red_label), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.spin_dialog_br = wx.SpinCtrl(
            tab_bg, min=0, max=100, initial=curr_dlg_back[0]
        )
        self.spin_dialog_br.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_bg_d.Add(self.spin_dialog_br, 1, wx.EXPAND)

        grid_bg_d.Add(
            wx.StaticText(tab_bg, label=green_label), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.spin_dialog_bg = wx.SpinCtrl(
            tab_bg, min=0, max=100, initial=curr_dlg_back[1]
        )
        self.spin_dialog_bg.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_bg_d.Add(self.spin_dialog_bg, 1, wx.EXPAND)

        grid_bg_d.Add(
            wx.StaticText(tab_bg, label=blue_label), 0, wx.ALIGN_CENTER_VERTICAL
        )
        self.spin_dialog_bb = wx.SpinCtrl(
            tab_bg, min=0, max=100, initial=curr_dlg_back[2]
        )
        self.spin_dialog_bb.Bind(wx.EVT_SPINCTRL, self.on_change)
        grid_bg_d.Add(self.spin_dialog_bb, 1, wx.EXPAND)

        grid_bg_d.AddGrowableCol(1)
        sbs_bg_dlg.Add(grid_bg_d, 1, wx.EXPAND | wx.ALL, 5)
        vbox_bg.Add(sbs_bg_dlg, 0, wx.EXPAND | wx.ALL, 10)

        tab_bg.SetSizer(vbox_bg)
        self.notebook.AddPage(tab_bg, _("Colori di sfondo"))

        main_vbox.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

        # --- BOTTONI ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        btn_reset = wx.Button(panel, label=_("Reset Default"))
        btn_reset.Bind(wx.EVT_BUTTON, self.on_reset)
        btn_sizer.Add(btn_reset, 0, wx.RIGHT, 10)

        btn_sizer.AddStretchSpacer()

        btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("Annulla"))
        btn_ok = wx.Button(panel, wx.ID_OK, _("OK"))
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
        import json
        from config import user_data_path

        settings_path = user_data_path("Tornello - Settings.json")
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
        play_sound("notifica")

    def on_reset(self, event):
        self.spin_size.SetValue(self.default_size)
        self.spin_dialog_size.SetValue(self.default_dialog_size)
        self.slider_vol.SetValue(self.default_volume)
        if "it" in self.lang_codes:
            self.choice_lang.SetSelection(self.lang_codes.index("it"))
        else:
            self.choice_lang.SetSelection(0)

        self.spin_tr.SetValue(self.default_rgb_text[0])
        self.spin_tg.SetValue(self.default_rgb_text[1])
        self.spin_tb.SetValue(self.default_rgb_text[2])

        self.spin_dialog_tr.SetValue(self.default_dialog_rgb_text[0])
        self.spin_dialog_tg.SetValue(self.default_dialog_rgb_text[1])
        self.spin_dialog_tb.SetValue(self.default_dialog_rgb_text[2])

        self.spin_br.SetValue(self.default_rgb_back[0])
        self.spin_bg.SetValue(self.default_rgb_back[1])
        self.spin_bb.SetValue(self.default_rgb_back[2])

        self.spin_dialog_br.SetValue(self.default_dialog_rgb_back[0])
        self.spin_dialog_bg.SetValue(self.default_dialog_rgb_back[1])
        self.spin_dialog_bb.SetValue(self.default_dialog_rgb_back[2])

        self.on_volume_change(None)
        self._update_preview()

    def _get_current_values(self):
        size = self.spin_size.GetValue()
        dialog_size = self.spin_dialog_size.GetValue()
        vol = self.slider_vol.GetValue()

        tr = self.spin_tr.GetValue()
        tg = self.spin_tg.GetValue()
        tb = self.spin_tb.GetValue()

        dialog_tr = self.spin_dialog_tr.GetValue()
        dialog_tg = self.spin_dialog_tg.GetValue()
        dialog_tb = self.spin_dialog_tb.GetValue()

        br = self.spin_br.GetValue()
        bg = self.spin_bg.GetValue()
        bb = self.spin_bb.GetValue()

        dialog_br = self.spin_dialog_br.GetValue()
        dialog_bg = self.spin_dialog_bg.GetValue()
        dialog_bb = self.spin_dialog_bb.GetValue()

        return (
            size,
            dialog_size,
            vol,
            [tr, tg, tb],
            [dialog_tr, dialog_tg, dialog_tb],
            [br, bg, bb],
            [dialog_br, dialog_bg, dialog_bb],
        )

    def _update_preview(self):
        (
            size,
            dialog_size,
            vol,
            text_rgb,
            dialog_text_rgb,
            back_rgb,
            dialog_back_rgb,
        ) = self._get_current_values()

        temp_settings = {"font_size": size, "rgb_text": text_rgb, "rgb_back": back_rgb}
        apply_visual_settings(self.preview_text, temp_settings)

    def get_settings(self):
        (
            size,
            dialog_size,
            vol,
            text_rgb,
            dialog_text_rgb,
            back_rgb,
            dialog_back_rgb,
        ) = self._get_current_values()

        lang_idx = self.choice_lang.GetSelection()
        if lang_idx != wx.NOT_FOUND and lang_idx < len(self.lang_codes):
            lang_val = self.lang_codes[lang_idx]
        else:
            lang_val = "it"

        return {
            "font_size": size,
            "dialog_font_size": dialog_size,
            "volume": vol,
            "rgb_text": text_rgb,
            "dialog_rgb_text": dialog_text_rgb,
            "rgb_back": back_rgb,
            "dialog_rgb_back": dialog_back_rgb,
            "language": lang_val,
        }
