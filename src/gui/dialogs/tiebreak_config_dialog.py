import wx
import builtins
from gui.accessibility import CustomAccessible
from gui.settings import apply_visual_settings
from utils import play_sound
from tiebreak_criteria import (
    CRITERIA,
    MODIFIERS,
    get_supported_modifiers,
    get_criterion_display_name,
    get_criterion_explanation,
    get_default_tiebreaks,
    migrate_old_tiebreaks,
    get_all_criteria_keys,
)

_ = getattr(builtins, "_", lambda s: s)


class TiebreakConfigDialog(wx.Dialog):
    """
    Finestra di dialogo per la configurazione dinamica e personalizzata
    dei criteri di spareggio tecnico conformi al regolamento FIDE.

    Ogni criterio applicato è memorizzato come dizionario:
        {"key": "BH", "modifiers": {"cut1": True}}
    La lista disponibile mostra sempre tutti i 19 criteri FIDE e permette
    l'aggiunta multipla dello stesso criterio con modificatori diversi.
    """

    def __init__(self, parent, torneo):
        super().__init__(
            parent,
            title=_("Configura Regole di Spareggio"),
            size=(800, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.torneo = torneo

        # Carica le impostazioni visive globali di Tornello
        if parent and hasattr(parent, "settings") and parent.settings:
            self.settings = parent.settings
        else:
            from gui.settings import load_settings

            self.settings = load_settings()

        # Lista completa delle chiavi disponibili (sempre tutti i 19 criteri)
        self.available_keys = get_all_criteria_keys()

        # Carica i criteri attivi con retrocompatibilità
        raw_tiebreaks = torneo.get("tiebreaks", None)
        if raw_tiebreaks is None:
            self.applied_entries = get_default_tiebreaks()
        elif raw_tiebreaks and isinstance(raw_tiebreaks[0], str):
            self.applied_entries = migrate_old_tiebreaks(raw_tiebreaks)
        else:
            self.applied_entries = [dict(e) for e in raw_tiebreaks]
            for entry in self.applied_entries:
                entry["modifiers"] = dict(entry.get("modifiers", {}))

        panel = wx.Panel(self)
        main_vbox = wx.BoxSizer(wx.VERTICAL)

        # Creiamo i controlli nel preciso ordine in cui vogliamo siano tabulati
        # Ordine di tabulazione desiderato:
        # 1. Lista disponibili
        # 2. Spiegazione regola (TextCtrl)
        # 3. Bottone Aggiungi
        # 4. Bottone Rimuovi
        # 5. Lista applicate
        # 6. Bottone Modificatori
        # 7. Bottone Sposta Su
        # 8. Bottone Sposta Giù
        # 9. Bottone Conferma
        # 10. Bottone Annulla

        # 1. Lista disponibili
        self.lbl_available = wx.StaticText(panel, label=_("Regole disponibili"))
        self.list_available = wx.ListBox(panel, style=wx.LB_SINGLE)

        # 2. Spiegazione regola
        self.lbl_expl = wx.StaticText(panel, label=_("Spiegazione regola"))
        self.text_expl = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(-1, 100)
        )
        self.text_expl.SetName(_("Spiegazione regola"))
        self.text_expl.SetAccessible(
            CustomAccessible(self.text_expl, _("Spiegazione regola"))
        )

        # 3. Bottone Aggiungi
        self.btn_add = wx.Button(panel, label="->", style=wx.BU_EXACTFIT)
        self.btn_add.SetName(_("Aggiungi regola selezionata"))
        self.btn_add.SetAccessible(
            CustomAccessible(self.btn_add, _("Aggiungi regola selezionata"))
        )

        # 4. Bottone Rimuovi
        self.btn_remove = wx.Button(panel, label="<-", style=wx.BU_EXACTFIT)
        self.btn_remove.SetName(_("Rimuovi regola selezionata"))
        self.btn_remove.SetAccessible(
            CustomAccessible(self.btn_remove, _("Rimuovi regola selezionata"))
        )

        # 5. Lista applicate
        self.lbl_applied = wx.StaticText(panel, label=_("Regole applicate"))
        self.list_applied = wx.ListBox(panel, style=wx.LB_SINGLE)

        # 6. Bottone Modificatori
        self.btn_modifiers = wx.Button(panel, label=_("Modificatori"))
        self.btn_modifiers.SetName(_("Modificatori della regola selezionata"))
        self.btn_modifiers.SetAccessible(
            CustomAccessible(
                self.btn_modifiers, _("Modificatori della regola selezionata")
            )
        )

        # 7. Bottone Sposta Su
        self.btn_up = wx.Button(panel, label=_("Sposta Su"))
        self.btn_up.SetName(_("Sposta regola selezionata verso l'alto"))
        self.btn_up.SetAccessible(
            CustomAccessible(self.btn_up, _("Sposta regola selezionata verso l'alto"))
        )

        # 8. Bottone Sposta Giù
        self.btn_down = wx.Button(panel, label=_("Sposta Giù"))
        self.btn_down.SetName(_("Sposta regola selezionata verso il basso"))
        self.btn_down.SetAccessible(
            CustomAccessible(
                self.btn_down, _("Sposta regola selezionata verso il basso")
            )
        )

        # 9. Bottone Conferma
        self.btn_ok = wx.Button(panel, wx.ID_OK, _("Conferma"))
        self.btn_ok.SetName(_("Conferma"))
        self.btn_ok.SetAccessible(CustomAccessible(self.btn_ok, _("Conferma")))
        self.btn_ok.SetDefault()

        # 10. Bottone Annulla
        self.btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("Annulla"))
        self.btn_cancel.SetName(_("Annulla"))
        self.btn_cancel.SetAccessible(CustomAccessible(self.btn_cancel, _("Annulla")))

        # --- Layout ---
        lists_hbox = wx.BoxSizer(wx.HORIZONTAL)

        # Sizer di sinistra (Regole disponibili)
        left_vbox = wx.BoxSizer(wx.VERTICAL)
        left_vbox.Add(self.lbl_available, 0, wx.BOTTOM, 5)
        left_vbox.Add(self.list_available, 1, wx.EXPAND)

        # Sizer centrale (Pulsanti -> e <-)
        mid_vbox = wx.BoxSizer(wx.VERTICAL)
        mid_vbox.AddStretchSpacer()
        mid_vbox.Add(self.btn_add, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)
        mid_vbox.Add(self.btn_remove, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 5)
        mid_vbox.AddStretchSpacer()

        # Sizer di destra (Regole applicate)
        right_vbox = wx.BoxSizer(wx.VERTICAL)
        right_vbox.Add(self.lbl_applied, 0, wx.BOTTOM, 5)
        right_vbox.Add(self.list_applied, 1, wx.EXPAND)

        # Sizer laterale destro (Pulsanti Modificatori, Sposta Su e Giù)
        updown_vbox = wx.BoxSizer(wx.VERTICAL)
        updown_vbox.AddStretchSpacer()
        updown_vbox.Add(self.btn_modifiers, 0, wx.ALL | wx.EXPAND, 5)
        updown_vbox.Add(self.btn_up, 0, wx.ALL | wx.EXPAND, 5)
        updown_vbox.Add(self.btn_down, 0, wx.ALL | wx.EXPAND, 5)
        updown_vbox.AddStretchSpacer()

        # Assembliamo la riga delle liste
        lists_hbox.Add(left_vbox, 1, wx.EXPAND | wx.RIGHT, 10)
        lists_hbox.Add(mid_vbox, 0, wx.EXPAND | wx.RIGHT, 10)
        lists_hbox.Add(right_vbox, 1, wx.EXPAND | wx.RIGHT, 10)
        lists_hbox.Add(updown_vbox, 0, wx.EXPAND)

        main_vbox.Add(lists_hbox, 1, wx.EXPAND | wx.ALL, 15)

        # Sezione spiegazione (visualizzata sotto la riga delle liste)
        expl_vbox = wx.BoxSizer(wx.VERTICAL)
        expl_vbox.Add(self.lbl_expl, 0, wx.BOTTOM, 5)
        expl_vbox.Add(self.text_expl, 1, wx.EXPAND)

        main_vbox.Add(expl_vbox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Pulsanti di azione finali
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.Add(self.btn_ok, 0, wx.RIGHT, 15)
        btn_sizer.Add(self.btn_cancel, 0)

        main_vbox.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 15)

        panel.SetSizer(main_vbox)

        # --- Associazione eventi ---
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

        self.list_available.Bind(wx.EVT_LISTBOX, self.on_select_available)
        self.list_available.Bind(wx.EVT_LISTBOX_DCLICK, self.on_add_double_click)
        self.list_available.Bind(wx.EVT_SET_FOCUS, self.on_focus_available)

        self.list_applied.Bind(wx.EVT_LISTBOX, self.on_select_applied)
        self.list_applied.Bind(wx.EVT_LISTBOX_DCLICK, self.on_remove_double_click)
        self.list_applied.Bind(wx.EVT_SET_FOCUS, self.on_focus_applied)
        self.list_applied.Bind(wx.EVT_CONTEXT_MENU, self.on_applied_context_menu)

        self.btn_add.Bind(wx.EVT_BUTTON, self.on_add_button)
        self.btn_remove.Bind(wx.EVT_BUTTON, self.on_remove_button)
        self.btn_modifiers.Bind(wx.EVT_BUTTON, self.on_show_modifiers)
        self.btn_up.Bind(wx.EVT_BUTTON, self.on_up_button)
        self.btn_down.Bind(wx.EVT_BUTTON, self.on_down_button)

        self.btn_ok.Bind(wx.EVT_BUTTON, self.on_ok)
        self.btn_cancel.Bind(wx.EVT_BUTTON, self.on_cancel)

        # Popola le liste
        self.populate_available()
        self.populate_applied()

        # Applicazione temi e stili a tutti i controlli
        for ctrl in [
            self,
            panel,
            self.lbl_available,
            self.list_available,
            self.lbl_applied,
            self.list_applied,
            self.lbl_expl,
            self.text_expl,
            self.btn_add,
            self.btn_remove,
            self.btn_modifiers,
            self.btn_up,
            self.btn_down,
            self.btn_ok,
            self.btn_cancel,
        ]:
            apply_visual_settings(ctrl, self.settings)

        self.Centre()

        # Sposta il focus sulla prima lista all'avvio
        wx.CallAfter(self.list_available.SetFocus)

    # ------------------------------------------------------------------
    # Popolamento delle liste
    # ------------------------------------------------------------------

    def populate_available(self):
        """Popola la lista disponibili con tutti i 19 criteri FIDE."""
        self.list_available.Clear()
        for key in self.available_keys:
            info = CRITERIA.get(key)
            name = info["name"] if info else key
            self.list_available.Append(name)

    def populate_applied(self):
        """Popola la lista applicata con numerazione e modificatori attivi."""
        prev_sel = self.list_applied.GetSelection()
        self.list_applied.Clear()
        for idx, entry in enumerate(self.applied_entries, 1):
            display = get_criterion_display_name(entry["key"], entry.get("modifiers"))
            self.list_applied.Append(f"{idx}. {display}")
        # Ripristina la selezione precedente se possibile
        if prev_sel != wx.NOT_FOUND and prev_sel < self.list_applied.GetCount():
            self.list_applied.SetSelection(prev_sel)

    # ------------------------------------------------------------------
    # Aggiornamento area di spiegazione
    # ------------------------------------------------------------------

    def update_explanation(self, key, modifiers=None):
        """Aggiorna l'area di spiegazione e applica gli stili per garantire l'accessibilità visiva."""
        text = get_criterion_explanation(key, modifiers)
        self.text_expl.SetValue(text)
        apply_visual_settings(self.text_expl, self.settings)

    # ------------------------------------------------------------------
    # Gestione selezione e focus
    # ------------------------------------------------------------------

    def on_select_available(self, event):
        idx = self.list_available.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.available_keys):
            key = self.available_keys[idx]
            self.update_explanation(key, modifiers=None)

    def on_select_applied(self, event):
        idx = self.list_applied.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.applied_entries):
            entry = self.applied_entries[idx]
            self.update_explanation(entry["key"], entry.get("modifiers"))

    def on_focus_available(self, event):
        """Quando la lista disponibili ottiene il focus, seleziona una voce ed aggiorna la descrizione."""
        if self.available_keys:
            idx = self.list_available.GetSelection()
            if idx == wx.NOT_FOUND:
                idx = 0
                self.list_available.SetSelection(idx)
            if idx < len(self.available_keys):
                self.update_explanation(self.available_keys[idx], modifiers=None)
        event.Skip()

    def on_focus_applied(self, event):
        """Quando la lista applicate ottiene il focus, seleziona una voce ed aggiorna la descrizione."""
        if self.applied_entries:
            idx = self.list_applied.GetSelection()
            if idx == wx.NOT_FOUND:
                idx = 0
                self.list_applied.SetSelection(idx)
            if idx < len(self.applied_entries):
                entry = self.applied_entries[idx]
                self.update_explanation(entry["key"], entry.get("modifiers"))
        event.Skip()

    # ------------------------------------------------------------------
    # Spostamento criteri fra le liste
    # ------------------------------------------------------------------

    def move_to_applied(self):
        """Aggiunge il criterio selezionato dalla lista disponibili a quella applicata.

        La lista disponibili non viene modificata: lo stesso criterio può
        essere aggiunto più volte con modificatori diversi.
        """
        idx = self.list_available.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.available_keys):
            key = self.available_keys[idx]
            new_entry = {"key": key, "modifiers": {}}
            self.applied_entries.append(new_entry)
            # Suono originale accettazione/aggiunta
            play_sound("successivo", self.torneo)
            self.populate_applied()

            # Seleziona l'elemento appena aggiunto nella lista applicata
            new_applied_idx = len(self.applied_entries) - 1
            self.list_applied.SetSelection(new_applied_idx)
            self.update_explanation(key, modifiers=None)
        else:
            play_sound("errore", self.torneo)

    def move_to_available(self):
        """Rimuove il criterio selezionato dalla lista applicata."""
        idx = self.list_applied.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.applied_entries):
            self.applied_entries.pop(idx)
            # Suono originale cancellazione/rimozione
            play_sound("cancellato", self.torneo)
            self.populate_applied()

            # Gestione del focus e della selezione sulla lista di destra
            if self.applied_entries:
                sel_idx = min(idx, len(self.applied_entries) - 1)
                self.list_applied.SetSelection(sel_idx)
                entry = self.applied_entries[sel_idx]
                self.update_explanation(entry["key"], entry.get("modifiers"))
            else:
                self.list_available.SetFocus()
        else:
            play_sound("errore", self.torneo)

    # ------------------------------------------------------------------
    # Gestione modificatori (context menu)
    # ------------------------------------------------------------------

    def on_show_modifiers(self, event=None):
        """Mostra il menu contestuale dei modificatori per il criterio applicato selezionato."""
        idx = self.list_applied.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self.applied_entries):
            play_sound("errore", self.torneo)
            return

        entry = self.applied_entries[idx]
        supported = get_supported_modifiers(entry["key"])
        if not supported:
            play_sound("errore", self.torneo)
            return

        menu = wx.Menu()
        modifiers_state = entry.get("modifiers", {})

        for mod_key in supported:
            mod_info = MODIFIERS.get(mod_key)
            if not mod_info:
                continue

            is_active = modifiers_state.get(mod_key, False)
            stato_label = _("attivo") if is_active else _("disattivo")
            label = f"{mod_info['name']} - {stato_label}"
            item = menu.Append(wx.ID_ANY, label, kind=wx.ITEM_CHECK)
            if is_active:
                menu.Check(item.GetId(), True)

            # Bind con closure per catturare mod_key
            self.Bind(
                wx.EVT_MENU,
                lambda evt, mk=mod_key: self.on_toggle_modifier(evt, mk),
                item,
            )

        self.PopupMenu(menu)
        menu.Destroy()

    def on_toggle_modifier(self, event, modifier_key):
        """Attiva/disattiva un modificatore sul criterio applicato selezionato."""
        idx = self.list_applied.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self.applied_entries):
            return

        entry = self.applied_entries[idx]
        modifiers = entry.setdefault("modifiers", {})

        # Toggle
        if modifiers.get(modifier_key, False):
            modifiers.pop(modifier_key, None)
        else:
            modifiers[modifier_key] = True

        # Aggiorna la visualizzazione
        self.populate_applied()
        self.list_applied.SetSelection(idx)
        self.update_explanation(entry["key"], entry.get("modifiers"))

    def on_applied_context_menu(self, event):
        """Gestisce il click destro sulla lista applicata per mostrare i modificatori."""
        self.on_show_modifiers()

    # ------------------------------------------------------------------
    # Riordino della lista applicata
    # ------------------------------------------------------------------

    def move_up(self):
        """Sposta in alto il criterio selezionato nella lista di destra (Sposta Su)."""
        idx = self.list_applied.GetSelection()
        if idx != wx.NOT_FOUND and idx > 0:
            self.applied_entries[idx], self.applied_entries[idx - 1] = (
                self.applied_entries[idx - 1],
                self.applied_entries[idx],
            )
            # Suono originale per lo spostamento verso l'alto
            play_sound("menu_triplicato_su_2", self.torneo)
            self.populate_applied()
            self.list_applied.SetSelection(idx - 1)
            entry = self.applied_entries[idx - 1]
            self.update_explanation(entry["key"], entry.get("modifiers"))
        else:
            play_sound("errore", self.torneo)

    def move_down(self):
        """Sposta in basso il criterio selezionato nella lista di destra (Sposta Giù)."""
        idx = self.list_applied.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.applied_entries) - 1:
            self.applied_entries[idx], self.applied_entries[idx + 1] = (
                self.applied_entries[idx + 1],
                self.applied_entries[idx],
            )
            # Suono originale per lo spostamento verso il basso
            play_sound("menu_triplicato_verso_il_basso_3", self.torneo)
            self.populate_applied()
            self.list_applied.SetSelection(idx + 1)
            entry = self.applied_entries[idx + 1]
            self.update_explanation(entry["key"], entry.get("modifiers"))
        else:
            play_sound("errore", self.torneo)

    # ------------------------------------------------------------------
    # Gestione eventi pulsanti
    # ------------------------------------------------------------------

    def on_add_double_click(self, event):
        self.move_to_applied()

    def on_remove_double_click(self, event):
        self.move_to_available()

    def on_add_button(self, event):
        self.move_to_applied()

    def on_remove_button(self, event):
        self.move_to_available()

    def on_up_button(self, event):
        self.move_up()

    def on_down_button(self, event):
        self.move_down()

    # ------------------------------------------------------------------
    # Gestione tastiera
    # ------------------------------------------------------------------

    def on_char_hook(self, event):
        key_code = event.GetKeyCode()
        focused = wx.Window.FindFocus()

        if key_code == wx.WXK_RETURN:
            if focused == self.list_available:
                self.move_to_applied()
                return  # Consuma l'evento senza propagarlo al bottone OK di default
            elif focused == self.list_applied:
                self.move_to_available()
                return  # Consuma l'evento
            elif focused in [
                self.btn_ok,
                self.btn_cancel,
                self.btn_add,
                self.btn_remove,
                self.btn_modifiers,
                self.btn_up,
                self.btn_down,
            ]:
                event.Skip()
                return
            else:
                event.Skip()
        elif key_code in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            if focused == self.list_applied:
                self.move_to_available()
                return  # Consuma l'evento
            event.Skip()
        elif key_code == wx.WXK_WINDOWS_MENU:
            if focused == self.list_applied:
                self.on_show_modifiers()
                return  # Consuma l'evento
            event.Skip()
        else:
            event.Skip()

    # ------------------------------------------------------------------
    # Conferma / Annulla
    # ------------------------------------------------------------------

    def on_ok(self, event):
        self.torneo["tiebreaks"] = [dict(entry) for entry in self.applied_entries]
        play_sound("salvato", self.torneo)
        self.EndModal(wx.ID_OK)

    def on_cancel(self, event):
        play_sound("cancellato", self.torneo)
        self.EndModal(wx.ID_CANCEL)
