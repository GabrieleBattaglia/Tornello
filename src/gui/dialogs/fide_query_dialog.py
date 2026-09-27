import builtins

import wx
from GBwx import STILE_ADATTABILE, adatta_finestra, pannello_scorrevole

from fide_db import search_players
from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog
from gui.settings import apply_visual_settings
from utils import play_sound

_ = getattr(builtins, "_", lambda s: s)


class FideQueryDialog(wx.Dialog):
    """
    Finestra di dialogo per la consultazione del Database FIDE locale.
    Layout a doppia vista: ListBox per la scelta dei risultati a sinistra,
    e TextCtrl multi-riga dettagliato a destra per la consultazione dei dati completi.
    """

    def __init__(self, parent, players_db, settings):
        title = _("Consulta Database FIDE")
        super().__init__(
            parent,
            title=title,
            style=STILE_ADATTABILE,
        )

        self.settings = settings
        self.players_db = players_db

        self.all_fide_matches = []
        self.fide_displayed_count = 0

        self._search_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_debounced_search, self._search_timer)

        self._init_ui()
        self.apply_theme()
        # Dalla 10.6.3 la misura la da' il contenuto, dentro lo schermo, e
        # quella che la finestra aveva al 100 per cento resta come minimo
        # (issue 49). Lista e dettagli si riempiono dopo: la loro misura
        # minima resta quella di adesso, come col Fit di prima, altrimenti la
        # voce piu' lunga allargherebbe il contenuto e il pannello mostrerebbe
        # le barre invece di lasciar scorrere la lista.
        for controllo in (self.list_results, self.detail_text):
            controllo.SetMinSize(controllo.GetEffectiveMinSize())
        adatta_finestra(self, self.pannello, (823, 205))

        self.on_search_changed(None)

    def _init_ui(self):
        panel = self.pannello = pannello_scorrevole(self)
        vbox_main = wx.BoxSizer(wx.VERTICAL)

        # Filtro di Ricerca
        hbox_search = wx.BoxSizer(wx.HORIZONTAL)
        hbox_search.Add(
            wx.StaticText(panel, label=_("Cerca per Cognome/Nome o ID FIDE:")),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            10,
        )
        self.search_input = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.search_input.Bind(wx.EVT_TEXT, self.on_search_changed)
        hbox_search.Add(self.search_input, 1, wx.EXPAND)
        vbox_main.Add(hbox_search, 0, wx.EXPAND | wx.ALL, 10)

        # Area Risultati e Dettaglio (Splitter o HBox)
        hbox_views = wx.BoxSizer(wx.HORIZONTAL)

        # Sizer Sinistra: ListBox dei Risultati
        vbox_left = wx.BoxSizer(wx.VERTICAL)
        vbox_left.Add(
            wx.StaticText(panel, label=_("Giocatori Trovati:")), 0, wx.BOTTOM, 5
        )
        self.list_results = wx.ListBox(panel, style=wx.LB_SINGLE | wx.LB_NEEDED_SB)
        self.list_results.SetMinSize(self.FromDIP(wx.Size(300, -1)))
        self.list_results.Bind(wx.EVT_LISTBOX, self.on_item_selected)
        self.list_results.Bind(wx.EVT_LISTBOX_DCLICK, self.on_import_player)
        self.list_results.Bind(wx.EVT_CHAR_HOOK, self.on_list_key)
        vbox_left.Add(self.list_results, 1, wx.EXPAND)

        hbox_views.Add(vbox_left, 3, wx.EXPAND | wx.RIGHT, 10)

        # Sizer Destra: Dettagli Giocatore
        vbox_right = wx.BoxSizer(wx.VERTICAL)
        vbox_right.Add(
            wx.StaticText(panel, label=_("Dettagli Giocatore FIDE:")), 0, wx.BOTTOM, 5
        )
        self.detail_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        self.detail_text.SetMinSize(self.FromDIP(wx.Size(450, -1)))
        vbox_right.Add(self.detail_text, 1, wx.EXPAND)

        hbox_views.Add(vbox_right, 4, wx.EXPAND)

        vbox_main.Add(hbox_views, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Bottoni in fondo
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_import = wx.Button(panel, label=_("Importa nel DB Locale"))
        self.btn_import.Bind(wx.EVT_BUTTON, self.on_import_player)

        btn_close = wx.Button(panel, wx.ID_CANCEL, _("Chiudi"))

        btn_sizer.Add(self.btn_import, 0, wx.RIGHT, 10)
        btn_sizer.Add(btn_close, 0)
        vbox_main.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(vbox_main)

    def apply_theme(self):
        apply_visual_settings(self.search_input, self.settings)
        apply_visual_settings(self.list_results, self.settings)
        apply_visual_settings(self.detail_text, self.settings)

    def on_search_changed(self, event):
        self._search_timer.Stop()
        self._search_timer.Start(900, wx.TIMER_ONE_SHOT)

    def _on_debounced_search(self, event):
        query = self.search_input.GetValue().strip()
        self.list_results.Clear()
        self.results_map = []
        self.all_fide_matches = []
        self.fide_displayed_count = 0
        self.detail_text.Clear()

        if len(query) < 3:
            return

        play_sound("fide_attesa")
        self.all_fide_matches = search_players(query)
        self.load_more_results()
        play_sound("fide_pronto")

        if self.list_results.GetCount() > 0:
            self.list_results.SetSelection(0)
            self.on_item_selected(None)

    def _e_la_riga_mostra_altri(self, indice):
        """Vero per la riga che carica i risultati seguenti, l'ultima, che
        non ha un giocatore dietro. Dalla 10.8.6 la si riconosce dalla
        posizione: il testo non comincia piu' con i due trattini, che NVDA
        leggeva, e nelle altre lingue potrebbe cominciare in qualunque modo."""
        return indice >= len(self.results_map)

    def load_more_results(self):
        # Rimuovi l'eventuale precedente item "Mostra altri..."
        last_idx = self.list_results.GetCount() - 1
        if last_idx >= 0 and self._e_la_riga_mostra_altri(last_idx):
            self.list_results.Delete(last_idx)

        start = self.fide_displayed_count
        end = min(start + 100, len(self.all_fide_matches))

        for i in range(start, end):
            p = self.all_fide_matches[i]
            fide_id_str = str(p.get("id_fide"))
            name = f"{p.get('last_name', '')} {p.get('first_name', '')}".strip()
            elo_std = p.get("elo_standard", 0)
            elo_rap = p.get("elo_rapid", 0)
            label = _(
                "{name} (Std: {elo_std}, Rap: {elo_rap} - ID FIDE: {fide_id} - Anno: {anno} - FED: {fed})"
            ).format(
                name=name,
                elo_std=elo_std,
                elo_rap=elo_rap,
                fide_id=fide_id_str,
                anno=p.get("birth_year", _("N/D")),
                fed=p.get("federation", _("N/D")),
            )
            self.list_results.Append(label)
            self.results_map.append(p)

        self.fide_displayed_count = end

        # Se ci sono altri risultati, aggiungi la riga speciale
        if self.fide_displayed_count < len(self.all_fide_matches):
            total = len(self.all_fide_matches)
            rem = total - self.fide_displayed_count
            # Con un solo risultato che resta il singolare: fino alla
            # 10.13.5 la riga diceva 1 rimanenti.
            lbl = (
                _("Mostra altri risultati (1 rimanente su {total})").format(total=total)
                if rem == 1
                else _("Mostra altri risultati ({rem} rimanenti su {total})").format(
                    rem=rem, total=total
                )
            )
            self.list_results.Append(lbl)

    def on_item_selected(self, event):
        sel = self.list_results.GetSelection()
        if sel == wx.NOT_FOUND:
            self.detail_text.Clear()
            return

        # Ignora se è la riga speciale "Mostra altri..."
        if self._e_la_riga_mostra_altri(sel):
            self.detail_text.Clear()
            return

        p = self.results_map[sel]

        details = (
            _("Cognome: {}").format(p.get("last_name", ""))
            + "\n"
            + _("Nome: {}").format(p.get("first_name", ""))
            + "\n"
            + _("ID FIDE: {}").format(p.get("id_fide", _("N/D")))
            + "\n"
            + _("Nazione (FED): {}").format(p.get("federation", _("N/D")))
            + "\n"
            + _("Sesso (Sex): {}").format(p.get("sex", "M"))
            + "\n"
            + _("Anno Nascita: {}").format(p.get("birth_year", _("N/D")))
            + "\n"
            + _("Titolo FIDE: {}").format(p.get("title", _("Nessuno")))
            + "\n"
        )

        # Titoli secondari FIDE
        w_title = p.get("w_title", "")
        if w_title:
            details += _("Titolo Femminile: {}").format(w_title) + "\n"
        o_title = p.get("o_title", "")
        if o_title:
            details += _("Titolo Arbitro/Altro: {}").format(o_title) + "\n"
        foa_title = p.get("foa_title", "")
        if foa_title:
            details += _("Titolo FOA: {}").format(foa_title) + "\n"

        details += (
            _("Flag (Caratteristica): {}").format(p.get("flag", ""))
            + "\n"
            + _("ELO Standard: {}").format(p.get("elo_standard", 0))
            + " ("
            + _("Partite: {}").format(p.get("games", 0))
            + ", K: "
            + str(p.get("k_factor") if p.get("k_factor") is not None else _("N/D"))
            + ")\n"
            + _("ELO Rapid: {}").format(p.get("elo_rapid", 0))
            + " ("
            + _("Partite: {}").format(p.get("rapid_games", 0))
            + ", K: "
            + str(p.get("rapid_k") if p.get("rapid_k") is not None else _("N/D"))
            + ")\n"
            + _("ELO Blitz: {}").format(p.get("elo_blitz", 0))
            + " ("
            + _("Partite: {}").format(p.get("blitz_games", 0))
            + ", K: "
            + str(p.get("blitz_k") if p.get("blitz_k") is not None else _("N/D"))
            + ")\n"
        )
        self.detail_text.SetValue(details)
        apply_visual_settings(self.detail_text, self.settings)

    def on_import_player(self, event):
        sel = self.list_results.GetSelection()
        if sel == wx.NOT_FOUND:
            return

        # Gestisci il click su "Mostra altri..."
        if self._e_la_riga_mostra_altri(sel):
            self.load_more_results()
            new_sel = sel
            if new_sel < self.list_results.GetCount():
                self.list_results.SetSelection(new_sel)
                self.on_item_selected(None)
            return

        fide_player = self.results_map[sel]

        # Verifica se è già nel DB personale locale
        from db_players import aggiungi_dal_fide, scheda_con_lo_stesso_id_fide

        if scheda_con_lo_stesso_id_fide(self.players_db, fide_player.get("id_fide")):
            play_sound("errore")
            dlg = AccessibleMsgDialog(
                self,
                _("Info"),
                _("Questo giocatore è già presente nel tuo database personale."),
            )
            dlg.ShowModal()
            dlg.Destroy()
            return

        # La scheda la costruisce db_players, la stessa della finestra di
        # iscrizione e della console dalla 10.13.15. Se il database non si
        # salva, il giocatore non resta nemmeno in memoria, e lo si dice:
        # fino alla 10.13.14 la finestra lo dava per importato lo stesso.
        new_player, _creata = aggiungi_dal_fide(self.players_db, fide_player)
        if new_player is None:
            play_sound("errore")
            dlg = AccessibleMsgDialog(
                self,
                _("Errore"),
                _(
                    "Il database dei giocatori non si è potuto salvare: il giocatore non è stato importato. Il motivo più comune è un file tenuto bloccato da un altro programma, per esempio Dropbox o l'antivirus: riprova più tardi."
                ),
            )
            dlg.ShowModal()
            dlg.Destroy()
            return
        new_id = new_player["id"]

        msg = _(
            "Giocatore '{name}' importato con successo nel database locale con ID '{id}'."
        ).format(
            name=f"{new_player['last_name']} {new_player['first_name']}", id=new_id
        )
        play_sound("salvato")
        dlg = AccessibleMsgDialog(self, _("Importazione Completata"), msg)
        dlg.ShowModal()
        dlg.Destroy()

    def on_list_key(self, event):
        key_code = event.GetKeyCode()
        if key_code == wx.WXK_RETURN:
            self.on_import_player(None)
        else:
            event.Skip()
