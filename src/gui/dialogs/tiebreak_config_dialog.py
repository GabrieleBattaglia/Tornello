import wx
import builtins
from gui.accessibility import CustomAccessible
from gui.settings import apply_visual_settings
from utils import play_sound

_ = getattr(builtins, "_", lambda s: s)

class TiebreakConfigDialog(wx.Dialog):
    """
    Finestra di dialogo per la configurazione dinamica e personalizzata
    dei criteri di spareggio tecnico.
    """
    def __init__(self, parent, torneo):
        super().__init__(parent, title=_("Configura Regole di Spareggio"), size=(800, 600), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
        self.torneo = torneo
        
        # Carica le impostazioni visive globali di Tornello
        if parent and hasattr(parent, "settings") and parent.settings:
            self.settings = parent.settings
        else:
            from gui.settings import load_settings
            self.settings = load_settings()
            
        # Elenco dei criteri supportati da Tornello con nomi e descrizioni
        self.criteri_info = {
            "points": {
                "name": _("Punti Totali"),
                "desc": _("Punteggio complessivo accumulato nel torneo.")
            },
            "withdrawn": {
                "name": _("Ritirato"),
                "desc": _("Ordinamento che posiziona i giocatori ritirati dopo quelli attivi.")
            },
            "buchholz_cut1": {
                "name": _("Buchholz Cut-1"),
                "desc": _("Somma dei punti degli avversari escludendo quello con il punteggio più basso.")
            },
            "buchholz": {
                "name": _("Buchholz Totale"),
                "desc": _("Somma totale dei punti di tutti gli avversari incontrati.")
            },
            "aro": {
                "name": _("ARO (Average Rating of Opponents)"),
                "desc": _("Media Elo degli avversari effettivamente affrontati.")
            },
            "initial_elo": {
                "name": _("Elo Iniziale (Seed)"),
                "desc": _("Forza teorica iniziale (Seed di tabellone).")
            },
            "sonneborn_berger": {
                "name": _("Sonneborn-Berger"),
                "desc": _("Somma dei punti degli avversari sconfitti + metà punti degli avversari con cui si è pattato.")
            },
            "direct_encounter": {
                "name": _("Scontro Diretto"),
                "desc": _("Risultato dello scontro diretto tra i giocatori a pari punti (se si sono incontrati).")
            },
            "played_rounds_rep": {
                "name": _("Turni Giocati (REP)"),
                "desc": _("Numero di turni in cui il giocatore ha effettivamente giocato (escludendo assenze e forfeit).")
            },
            "number_of_wins": {
                "name": _("Maggior Numero di Vittorie"),
                "desc": _("Numero totale di vittorie conseguite nel torneo.")
            },
            "number_of_blacks": {
                "name": _("Incontri col Nero"),
                "desc": _("Maggiore numero di partite disputate con il colore Nero.")
            },
            "cumulative": {
                "name": _("Punteggio Progressivo"),
                "desc": _("Somma dei punteggi progressivi turno per turno (criterio cumulativo).")
            }
        }
        
        # Carica i criteri attivi
        default_order = ["points", "withdrawn", "buchholz_cut1", "buchholz", "aro", "initial_elo"]
        self.applied_keys = list(torneo.get("tiebreaks", default_order))
        self.applied_keys = [k for k in self.applied_keys if k in self.criteri_info]
        
        # Criteri disponibili (non ancora attivi)
        self.available_keys = [k for k in self.criteri_info.keys() if k not in self.applied_keys]
        
        panel = wx.Panel(self)
        main_vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Creiamo i controlli nel preciso ordine in cui vogliamo siano tabulati
        # Ordine di tabulazione desiderato:
        # 1. Lista disponibili
        # 2. Spiegazione regola (TextCtrl)
        # 3. Bottone Aggiungi
        # 4. Bottone Rimuovi
        # 5. Lista applicate
        # 6. Bottone Sposta Su
        # 7. Bottone Sposta Giù
        # 8. Bottone Conferma
        # 9. Bottone Annulla
        
        # 1. Lista disponibili
        self.lbl_available = wx.StaticText(panel, label=_("Regole disponibili"))
        self.list_available = wx.ListBox(panel, style=wx.LB_SINGLE)
        
        # 2. Spiegazione regola
        self.lbl_expl = wx.StaticText(panel, label=_("Spiegazione regola"))
        self.text_expl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(-1, 100))
        self.text_expl.SetName(_("Spiegazione regola"))
        self.text_expl.SetAccessible(CustomAccessible(self.text_expl, _("Spiegazione regola")))
        
        # 3. Bottone Aggiungi
        self.btn_add = wx.Button(panel, label="->", style=wx.BU_EXACTFIT)
        self.btn_add.SetName(_("Aggiungi regola selezionata"))
        self.btn_add.SetAccessible(CustomAccessible(self.btn_add, _("Aggiungi regola selezionata")))
        
        # 4. Bottone Rimuovi
        self.btn_remove = wx.Button(panel, label="<-", style=wx.BU_EXACTFIT)
        self.btn_remove.SetName(_("Rimuovi regola selezionata"))
        self.btn_remove.SetAccessible(CustomAccessible(self.btn_remove, _("Rimuovi regola selezionata")))
        
        # 5. Lista applicate
        self.lbl_applied = wx.StaticText(panel, label=_("Regole applicate"))
        self.list_applied = wx.ListBox(panel, style=wx.LB_SINGLE)
        
        # 6. Bottone Sposta Su
        self.btn_up = wx.Button(panel, label=_("Sposta Su"))
        self.btn_up.SetName(_("Sposta regola selezionata verso l'alto"))
        self.btn_up.SetAccessible(CustomAccessible(self.btn_up, _("Sposta regola selezionata verso l'alto")))
        
        # 7. Bottone Sposta Giù
        self.btn_down = wx.Button(panel, label=_("Sposta Giù"))
        self.btn_down.SetName(_("Sposta regola selezionata verso il basso"))
        self.btn_down.SetAccessible(CustomAccessible(self.btn_down, _("Sposta regola selezionata verso il basso")))
        
        # 8. Bottone Conferma
        self.btn_ok = wx.Button(panel, wx.ID_OK, _("Conferma"))
        self.btn_ok.SetName(_("Conferma"))
        self.btn_ok.SetAccessible(CustomAccessible(self.btn_ok, _("Conferma")))
        self.btn_ok.SetDefault()
        
        # 9. Bottone Annulla
        self.btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("Annulla"))
        self.btn_cancel.SetName(_("Annulla"))
        self.btn_cancel.SetAccessible(CustomAccessible(self.btn_cancel, _("Annulla")))
        
        # Disposizione nel sizer (le liste e i pulsanti di movimento)
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
        
        # Sizer laterale destro (Pulsanti Sposta Su e Giù)
        updown_vbox = wx.BoxSizer(wx.VERTICAL)
        updown_vbox.AddStretchSpacer()
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
        
        # Associazione eventi
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        
        self.list_available.Bind(wx.EVT_LISTBOX, self.on_select_available)
        self.list_available.Bind(wx.EVT_LISTBOX_DCLICK, self.on_add_double_click)
        self.list_available.Bind(wx.EVT_SET_FOCUS, self.on_focus_available)
        
        self.list_applied.Bind(wx.EVT_LISTBOX, self.on_select_applied)
        self.list_applied.Bind(wx.EVT_LISTBOX_DCLICK, self.on_remove_double_click)
        self.list_applied.Bind(wx.EVT_SET_FOCUS, self.on_focus_applied)

        
        self.btn_add.Bind(wx.EVT_BUTTON, self.on_add_button)
        self.btn_remove.Bind(wx.EVT_BUTTON, self.on_remove_button)
        self.btn_up.Bind(wx.EVT_BUTTON, self.on_up_button)
        self.btn_down.Bind(wx.EVT_BUTTON, self.on_down_button)
        
        self.btn_ok.Bind(wx.EVT_BUTTON, self.on_ok)
        self.btn_cancel.Bind(wx.EVT_BUTTON, self.on_cancel)
        
        self.populate_lists()
        
        # Applicazione temi e stili
        apply_visual_settings(self, self.settings)
        apply_visual_settings(panel, self.settings)
        apply_visual_settings(self.lbl_available, self.settings)
        apply_visual_settings(self.list_available, self.settings)
        apply_visual_settings(self.lbl_applied, self.settings)
        apply_visual_settings(self.list_applied, self.settings)
        apply_visual_settings(self.lbl_expl, self.settings)
        apply_visual_settings(self.text_expl, self.settings)
        apply_visual_settings(self.btn_add, self.settings)
        apply_visual_settings(self.btn_remove, self.settings)
        apply_visual_settings(self.btn_up, self.settings)
        apply_visual_settings(self.btn_down, self.settings)
        apply_visual_settings(self.btn_ok, self.settings)
        apply_visual_settings(self.btn_cancel, self.settings)
        
        self.Centre()
        
        # Sposta il focus sulla prima lista all'avvio
        wx.CallAfter(self.list_available.SetFocus)

    def populate_lists(self):
        """Popola le due listbox con i dati correnti."""
        self.list_available.Clear()
        for key in self.available_keys:
            name = self.criteri_info[key]["name"]
            self.list_available.Append(name)
            
        self.list_applied.Clear()
        for idx, key in enumerate(self.applied_keys, 1):
            name = self.criteri_info[key]["name"]
            self.list_applied.Append(f"{idx}. {name}")

    def update_explanation(self, key):
        """Aggiorna l'area di spiegazione e applica gli stili per garantire l'accessibilità visiva."""
        desc = self.criteri_info[key]["desc"]
        self.text_expl.SetValue(desc)
        apply_visual_settings(self.text_expl, self.settings)

    def on_select_available(self, event):
        idx = self.list_available.GetSelection()
        if idx != wx.NOT_FOUND:
            key = self.available_keys[idx]
            self.update_explanation(key)
            
    def on_select_applied(self, event):
        idx = self.list_applied.GetSelection()
        if idx != wx.NOT_FOUND:
            key = self.applied_keys[idx]
            self.update_explanation(key)

    def on_focus_available(self, event):
        """Quando la lista disponibili ottiene il focus, seleziona una voce ed aggiorna la descrizione."""
        if self.available_keys:
            idx = self.list_available.GetSelection()
            if idx == wx.NOT_FOUND:
                idx = 0
                self.list_available.SetSelection(idx)
            self.update_explanation(self.available_keys[idx])
        event.Skip()

    def on_focus_applied(self, event):
        """Quando la lista applicate ottiene il focus, seleziona una voce ed aggiorna la descrizione."""
        if self.applied_keys:
            idx = self.list_applied.GetSelection()
            if idx == wx.NOT_FOUND:
                idx = 0
                self.list_applied.SetSelection(idx)
            self.update_explanation(self.applied_keys[idx])
        event.Skip()

    def move_to_applied(self):
        """Sposta la regola selezionata tra quelle applicate (Aggiungi)."""
        idx = self.list_available.GetSelection()
        if idx != wx.NOT_FOUND:
            key = self.available_keys.pop(idx)
            self.applied_keys.append(key)
            # Suono originale accettazione/aggiunta 'successivo'
            play_sound("successivo", self.torneo)
            self.populate_lists()
            
            # Seleziona l'elemento appena aggiunto
            new_idx = len(self.applied_keys) - 1
            self.list_applied.SetSelection(new_idx)
            self.update_explanation(key)
            
            # Gestione del focus e della selezione sulla lista di sinistra
            if self.available_keys:
                sel_idx = min(idx, len(self.available_keys) - 1)
                self.list_available.SetSelection(sel_idx)
                new_key = self.available_keys[sel_idx]
                self.update_explanation(new_key)
            else:
                self.list_applied.SetFocus()
        else:
            play_sound("errore", self.torneo)
            
    def move_to_available(self):
        """Sposta la regola selezionata tra quelle disponibili (Rimuovi)."""
        idx = self.list_applied.GetSelection()
        if idx != wx.NOT_FOUND:
            key = self.applied_keys.pop(idx)
            self.available_keys.append(key)
            # Suono originale cancellazione/rimozione 'cancellato'
            play_sound("cancellato", self.torneo)
            self.populate_lists()
            
            # Seleziona l'elemento appena rimosso
            new_idx = len(self.available_keys) - 1
            self.list_available.SetSelection(new_idx)
            self.update_explanation(key)
            
            # Gestione del focus e della selezione sulla lista di destra
            if self.applied_keys:
                sel_idx = min(idx, len(self.applied_keys) - 1)
                self.list_applied.SetSelection(sel_idx)
                new_key = self.applied_keys[sel_idx]
                self.update_explanation(new_key)
            else:
                self.list_available.SetFocus()
        else:
            play_sound("errore", self.torneo)

    def on_add_double_click(self, event):
        self.move_to_applied()
        
    def on_remove_double_click(self, event):
        self.move_to_available()

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
            elif focused in [self.btn_ok, self.btn_cancel, self.btn_add, self.btn_remove, self.btn_up, self.btn_down]:
                event.Skip()
                return
            else:
                event.Skip()
        elif key_code == wx.WXK_DELETE or key_code == wx.WXK_NUMPAD_DELETE:
            if focused == self.list_applied:
                self.move_to_available()
                return  # Consuma l'evento
            event.Skip()
        else:
            event.Skip()


    def move_up(self):
        """Sposta in alto il criterio selezionato nella lista di destra (Sposta Su)."""
        idx = self.list_applied.GetSelection()
        if idx != wx.NOT_FOUND and idx > 0:
            self.applied_keys[idx], self.applied_keys[idx - 1] = self.applied_keys[idx - 1], self.applied_keys[idx]
            # Suono originale per lo spostamento verso l'alto
            play_sound("menu_triplicato_su_2", self.torneo)
            self.populate_lists()
            self.list_applied.SetSelection(idx - 1)
            self.update_explanation(self.applied_keys[idx - 1])
        else:
            play_sound("errore", self.torneo)

    def move_down(self):
        """Sposta in basso il criterio selezionato nella lista di destra (Sposta Giù)."""
        idx = self.list_applied.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.applied_keys) - 1:
            self.applied_keys[idx], self.applied_keys[idx + 1] = self.applied_keys[idx + 1], self.applied_keys[idx]
            # Suono originale per lo spostamento verso il basso
            play_sound("menu_triplicato_verso_il_basso_3", self.torneo)
            self.populate_lists()
            self.list_applied.SetSelection(idx + 1)
            self.update_explanation(self.applied_keys[idx + 1])
        else:
            play_sound("errore", self.torneo)

    def on_add_button(self, event):
        self.move_to_applied()
        
    def on_remove_button(self, event):
        self.move_to_available()
        
    def on_up_button(self, event):
        self.move_up()
        
    def on_down_button(self, event):
        self.move_down()

    def on_ok(self, event):
        self.torneo["tiebreaks"] = list(self.applied_keys)
        play_sound("salvato", self.torneo)
        self.EndModal(wx.ID_OK)

    def on_cancel(self, event):
        play_sound("cancellato", self.torneo)
        self.EndModal(wx.ID_CANCEL)
