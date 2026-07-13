import wx
import builtins
from db_players import load_players_db, save_players_db
from fide_db import (
    fide_db_exists,
    get_player_by_fide_id,
    search_players_by_name,
)
from gui.settings import apply_visual_settings
from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog

_ = getattr(builtins, "_", lambda s: s)


class SyncDatabaseDialog(wx.Dialog):
    """
    Dialogo di sincronizzazione per confrontare e aggiornare il database personale
    dei giocatori con il database FIDE locale.
    Supporta l'aggiornamento massivo e la risoluzione passo-passo.
    """

    def __init__(self, parent, settings):
        title = _("Sincronizzazione Database Personale con FIDE")
        super().__init__(
            parent,
            title=title,
            size=(750, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.settings = settings
        self.players_db = load_players_db()
        self.fide_db_available = fide_db_exists()

        self.changes = []
        self.stats = {"id_associations": 0, "elo_updates": 0, "other_updates": 0}

        self._collect_changes()
        self._init_ui()
        self.apply_theme()
        self.Centre()

    def _collect_changes(self):
        """Confronta il DB locale e FIDE raccogliendo le discrepanze."""
        if not self.players_db or not self.fide_db_available:
            return

        for player_id, local_player in self.players_db.items():
            fide_id_str = local_player.get("fide_id_num_str", "0")
            fide_record = None
            new_fide_id = None
            is_ambiguous = False
            matches = []

            if fide_id_str and fide_id_str != "0":
                fide_record = get_player_by_fide_id(fide_id_str)
            else:
                # Cerca per nome e cognome
                p_first = local_player.get("first_name", "")
                p_last = local_player.get("last_name", "")

                if p_first and p_last:
                    matches = search_players_by_name(p_first, p_last)
                    if len(matches) == 1:
                        new_fide_id = str(matches[0]["id_fide"])
                        fide_record = matches[0]
                    elif len(matches) > 1:
                        is_ambiguous = True

            updates = {}
            if fide_record:
                # Standard ELO
                fide_elo = fide_record.get("elo_standard", 0)
                if fide_elo > 0 and fide_elo != local_player.get("current_elo"):
                    updates["current_elo"] = fide_elo
                    self.stats["elo_updates"] += 1

                # Titolo FIDE
                fide_title = fide_record.get("title", "")
                if fide_title and not local_player.get("fide_title"):
                    updates["fide_title"] = fide_title
                    self.stats["other_updates"] += 1

                # Anno Nascita
                fide_birth = fide_record.get("birth_year")
                if fide_birth and not local_player.get("birth_date"):
                    updates["birth_date"] = f"{fide_birth}-01-01"
                    self.stats["other_updates"] += 1

            if new_fide_id:
                self.stats["id_associations"] += 1

            if new_fide_id or updates or is_ambiguous:
                self.changes.append(
                    {
                        "player_id": player_id,
                        "local_player": local_player,
                        "new_fide_id": new_fide_id,
                        "updates": updates,
                        "is_ambiguous": is_ambiguous,
                        "matches": matches,
                    }
                )

    def _init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Titolo / Stato
        lbl_title = wx.StaticText(panel, label=_("Sincronizzazione Database Giocatori"))
        font_title = wx.Font(
            14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD
        )
        lbl_title.SetFont(font_title)
        vbox.Add(lbl_title, 0, wx.ALL, 15)

        # Testo di Riepilogo
        summary_text = ""
        if not self.changes:
            summary_text = _(
                "Il tuo database personale è già perfettamente sincronizzato con il DB FIDE locale!"
            )
        else:
            summary_text = (
                _("Trovate modifiche disponibili per {num} giocatori:\n").format(
                    num=len(self.changes)
                )
                + f" - {self.stats['id_associations']} "
                + _("nuovi ID FIDE da associare\n")
                + f" - {self.stats['elo_updates']} "
                + _("aggiornamenti di punteggio Elo\n")
                + f" - {self.stats['other_updates']} "
                + _("aggiornamenti di dati anagrafici/titoli\n\n")
                + _(
                    "Scegli se aggiornare tutto in massa (gli omonimi multipli andranno risolti singolarmente)\n"
                    "oppure valutare ogni singolo giocatore passo-passo."
                )
            )

        self.txt_summary = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(-1, 200)
        )
        self.txt_summary.SetValue(summary_text)
        vbox.Add(self.txt_summary, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        # Bottoni
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        if self.changes:
            self.btn_bulk = wx.Button(panel, label=_("Aggiorna Tutto (In Massa)"))
            self.btn_bulk.Bind(wx.EVT_BUTTON, self.on_bulk_sync)

            self.btn_step = wx.Button(panel, label=_("Valuta Singolarmente"))
            self.btn_step.Bind(wx.EVT_BUTTON, self.on_step_sync)

            btn_sizer.Add(self.btn_bulk, 0, wx.RIGHT, 10)
            btn_sizer.Add(self.btn_step, 0, wx.RIGHT, 10)

        btn_close = wx.Button(panel, wx.ID_CANCEL, _("Chiudi"))
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(btn_close, 0)

        vbox.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 15)

        panel.SetSizer(vbox)
        vbox.Fit(self)

    def apply_theme(self):
        apply_visual_settings(self.txt_summary, self.settings)

    def on_bulk_sync(self, event):
        """Applica tutte le modifiche non ambigue in blocco."""
        dlg_prog = wx.ProgressDialog(
            _("Sincronizzazione in corso"),
            _("Elaborazione dati..."),
            maximum=len(self.changes),
            parent=self,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_ELAPSED_TIME,
        )

        applied_count = 0
        ambiguous_list = []

        for idx, change in enumerate(self.changes):
            dlg_prog.Update(
                idx,
                _("Aggiornamento {name}...").format(
                    name=f"{change['local_player'].get('last_name')} {change['local_player'].get('first_name')}"
                ),
            )

            if change["is_ambiguous"]:
                ambiguous_list.append(change)
                continue

            p_id = change["player_id"]
            player = self.players_db[p_id]

            # Applica associazione ID
            if change["new_fide_id"]:
                player["fide_id_num_str"] = change["new_fide_id"]

            # Applica modifiche campi
            for k, v in change["updates"].items():
                player[k] = v

            applied_count += 1

        dlg_prog.Destroy()
        save_players_db(self.players_db)

        # Se ci sono omonimi ambigui, li risolviamo subito uno ad uno
        if ambiguous_list:
            msg = _(
                "Aggiornati {num} giocatori. Ci sono {amb} omonimi con ID ambiguo da risolvere."
            ).format(num=applied_count, amb=len(ambiguous_list))
            wx.MessageBox(msg, _("Risoluzione Omonimi"), wx.ICON_INFORMATION)
            self._resolve_ambiguous_changes(ambiguous_list)
        else:
            msg = _(
                "Sincronizzazione massiva completata con successo! Aggiornati {num} giocatori."
            ).format(num=applied_count)
            dlg_res = AccessibleMsgDialog(self, _("Sincronizzazione Completata"), msg)
            dlg_res.ShowModal()
            dlg_res.Destroy()
            self.EndModal(wx.ID_OK)

    def _resolve_ambiguous_changes(self, ambiguous_list):
        """Risolve omonimi multipli uno ad uno presentando una lista di opzioni."""
        for change in ambiguous_list:
            player = change["local_player"]
            matches = change["matches"]

            choices = []
            for m in matches:
                choices.append(
                    _(
                        "FIDE ID: {fide_id} | FED: {fed} | ELO: {elo} | Anno: {anno}"
                    ).format(
                        fide_id=m["id_fide"],
                        fed=m["federation"],
                        elo=m["elo_standard"],
                        anno=m.get("birth_year", _("N/D")),
                    )
                )

            dlg = wx.SingleChoiceDialog(
                self,
                _("Seleziona il record FIDE corretto per {name}:").format(
                    name=f"{player.get('last_name')} {player.get('first_name')}"
                ),
                _("Risoluzione Omonimia"),
                choices,
            )

            if dlg.ShowModal() == wx.ID_OK:
                sel = dlg.GetSelection()
                selected_match = matches[sel]
                p_id = change["player_id"]
                local_p = self.players_db[p_id]

                # Associa ID e aggiorna
                local_p["fide_id_num_str"] = str(selected_match["id_fide"])
                if selected_match.get("elo_standard", 0) > 0:
                    local_p["current_elo"] = selected_match["elo_standard"]
                if selected_match.get("birth_year"):
                    local_p["birth_date"] = f"{selected_match['birth_year']}-01-01"
                if selected_match.get("title"):
                    local_p["fide_title"] = selected_match["title"]

            dlg.Destroy()

        save_players_db(self.players_db)
        wx.MessageBox(
            _("Tutti gli omonimi sono stati risolti e salvati."),
            _("Sincronizzazione Completata"),
            wx.ICON_INFORMATION,
        )
        self.EndModal(wx.ID_OK)

    def on_step_sync(self, event):
        """Avvia la valutazione passo-passo dei cambiamenti."""
        applied_count = 0
        skipped_count = 0

        for change in self.changes:
            player = change["local_player"]
            name = (
                f"{player.get('last_name', '')} {player.get('first_name', '')}".strip()
            )
            p_id = change["player_id"]
            local_p = self.players_db[p_id]

            if change["is_ambiguous"]:
                # Caso di omonimia multipla: presentiamo le opzioni
                matches = change["matches"]
                choices = []
                for m in matches:
                    choices.append(
                        _(
                            "FIDE ID: {fide_id} | FED: {fed} | ELO: {elo} | Anno: {anno}"
                        ).format(
                            fide_id=m["id_fide"],
                            fed=m["federation"],
                            elo=m["elo_standard"],
                            anno=m.get("birth_year", _("N/D")),
                        )
                    )

                dlg = wx.SingleChoiceDialog(
                    self,
                    _(
                        "Seleziona il record FIDE corretto per {name} (Omonimia multipla):"
                    ).format(name=name),
                    _("Risoluzione Omonimia"),
                    choices,
                )

                if dlg.ShowModal() == wx.ID_OK:
                    sel = dlg.GetSelection()
                    selected_match = matches[sel]

                    # Associa ID e aggiorna
                    local_p["fide_id_num_str"] = str(selected_match["id_fide"])
                    if selected_match.get("elo_standard", 0) > 0:
                        local_p["current_elo"] = selected_match["elo_standard"]
                    if selected_match.get("birth_year"):
                        local_p["birth_date"] = f"{selected_match['birth_year']}-01-01"
                    if selected_match.get("title"):
                        local_p["fide_title"] = selected_match["title"]
                    # Altri campi FIDE
                    for k_fide, k_local in [
                        ("elo_rapid", "elo_rapid"),
                        ("elo_blitz", "elo_blitz"),
                    ]:
                        val_f = selected_match.get(k_fide)
                        if val_f:
                            local_p[k_local] = val_f

                    applied_count += 1
                else:
                    skipped_count += 1
                dlg.Destroy()

            else:
                # Caso non ambiguo: presentiamo le modifiche proposte per conferma
                summary = []
                if change["new_fide_id"]:
                    summary.append(
                        _(" - Associazione ID FIDE: {id_val}").format(
                            id_val=change["new_fide_id"]
                        )
                    )

                field_names = {
                    "current_elo": _("ELO Standard"),
                    "fide_title": _("Titolo FIDE"),
                    "birth_date": _("Data di nascita"),
                    "fide_k_factor": _("K-Factor"),
                    "elo_rapid": _("ELO Rapid"),
                    "elo_blitz": _("ELO Blitz"),
                }

                for k, v in change["updates"].items():
                    old_val = local_p.get(k, "N/D")
                    f_name = field_names.get(k, k)
                    summary.append(f" - {f_name}: {old_val} -> {v}")

                summary_str = "\n".join(summary)
                msg = _(
                    "Vuoi applicare le seguenti modifiche per {name}?\n\n{summary}"
                ).format(name=name, summary=summary_str)

                dlg = AccessibleMsgDialog(
                    self, _("Conferma Aggiornamento"), msg, style=wx.YES_NO
                )
                if dlg.ShowModal() == wx.ID_YES:
                    # Applica associazione ID
                    if change["new_fide_id"]:
                        local_p["fide_id_num_str"] = change["new_fide_id"]
                    # Applica modifiche campi
                    for k, v in change["updates"].items():
                        local_p[k] = v
                    applied_count += 1
                else:
                    skipped_count += 1
                dlg.Destroy()

        if applied_count > 0:
            save_players_db(self.players_db)

        msg_fin = _(
            "Sincronizzazione completata.\nApplicati: {app} | Saltati: {skp}"
        ).format(app=applied_count, skp=skipped_count)
        wx.MessageBox(msg_fin, _("Sincronizzazione Terminata"), wx.ICON_INFORMATION)
        self.EndModal(wx.ID_OK)
