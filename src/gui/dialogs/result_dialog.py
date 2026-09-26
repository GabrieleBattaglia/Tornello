import builtins
import datetime

import wx
from GBwx import STILE_ADATTABILE, adatta_finestra, pannello_scorrevole

from gui.settings import apply_visual_settings
from utils import format_date_locale

_ = getattr(builtins, "_", lambda s: s)

# Dalla 10.6.3 le finestre prendono la misura dal contenuto, dentro lo
# schermo, e scorrono se non ci stanno (issue 49): con i caratteri di Windows
# al 150 per cento, o con quelli dei dialoghi grandi, i pulsanti finivano
# fuori. Queste sono le misure che le due finestre avevano al 100 per cento,
# e restano come minimo. La programmazione cresce in altezza con i giorni
# proposti: il minimo e' quello dei quattro giorni che propone sempre.
MISURA_PROGRAMMAZIONE = (242, 435)
MISURA_RISULTATO = (457, 547)


class ScheduleDialog(wx.Dialog):
    """
    Finestra di dialogo modale per la pianificazione dettagliata di una partita.
    Permette di selezionare una data da una lista di radio button (da oggi a 3 giorni dopo la scadenza del turno),
    l'ora e i minuti con step da 5, l'indirizzo della sala o l'URL dell'incontro, e il nome dell'arbitro designato.
    """

    def __init__(self, parent, schedule_info, settings, tournament_data):
        super().__init__(
            parent,
            title=_("Pianificazione Partita"),
            style=STILE_ADATTABILE,
        )
        self.settings = settings
        self.schedule_info = schedule_info or {}
        self.tournament_data = tournament_data or {}
        self._init_ui()
        self.apply_theme()
        adatta_finestra(self, self.pannello, MISURA_PROGRAMMAZIONE)

    def _init_ui(self):
        panel = self.pannello = pannello_scorrevole(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # 1. Calcolo intervallo date (da oggi fino a scadenza turno + 3 giorni)
        from datetime import date

        today = date.today()

        current_round_num = self.tournament_data.get("current_round", 1)
        round_dates_info = self.tournament_data.get("round_dates", [])
        current_round_period_info = next(
            (rd for rd in round_dates_info if rd.get("round") == current_round_num),
            None,
        )

        end_date = None
        if current_round_period_info and current_round_period_info.get("end_date"):
            try:
                end_date = datetime.datetime.strptime(
                    current_round_period_info.get("end_date"), "%Y-%m-%d"
                ).date()
            except ValueError:
                pass

        if not end_date and self.tournament_data.get("end_date"):
            try:
                end_date = datetime.datetime.strptime(
                    self.tournament_data.get("end_date"), "%Y-%m-%d"
                ).date()
            except ValueError:
                pass

        if not end_date:
            end_date = today + datetime.timedelta(days=7)

        limit_date = end_date + datetime.timedelta(days=3)
        limit_date = max(limit_date, today + datetime.timedelta(days=3))
        limit_date = min(limit_date, today + datetime.timedelta(days=30))

        dates_list = []
        curr = today
        while curr <= limit_date:
            dates_list.append(curr)
            curr += datetime.timedelta(days=1)

        # Box di selezione giorno. Dalla 10.6.4 i controlli dei tre riquadri
        # sono figli del riquadro e non del pannello, come vuole wxPython: e'
        # da li' che lo screen reader ricava il nome del gruppo, e all'apertura
        # non compare piu' un avviso per controllo (issue 49). Ogni riquadro
        # nasce subito prima dei suoi controlli, quindi l'ordine del tasto Tab
        # resta quello di prima, e i pulsanti dei giorni restano un gruppo solo
        # perche' sono tutti figli dello stesso riquadro.
        sb_date = wx.StaticBox(panel, label=_("Seleziona Giorno"))
        sbs_date = wx.StaticBoxSizer(sb_date, wx.VERTICAL)

        self.radio_buttons = []
        first = True

        curr_date_str = self.schedule_info.get("date")
        curr_date = None
        if curr_date_str:
            try:
                curr_date = datetime.datetime.strptime(curr_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        for d in dates_list:
            style = wx.RB_GROUP if first else 0
            lbl = format_date_locale(d)
            rb = wx.RadioButton(sb_date, label=lbl, style=style)
            rb.Bind(wx.EVT_SET_FOCUS, self.on_rb_focus)

            if curr_date:
                rb.SetValue(d == curr_date)
            else:
                rb.SetValue(first)

            sbs_date.Add(rb, 0, wx.ALL | wx.EXPAND, 4)
            self.radio_buttons.append((d, rb))
            first = False

        vbox.Add(sbs_date, 0, wx.EXPAND | wx.ALL, 15)

        # 2. Selezione Ora e Minuti
        sb_time = wx.StaticBox(panel, label=_("Seleziona Ora"))
        sbs_time = wx.StaticBoxSizer(sb_time, wx.HORIZONTAL)

        lbl_hour = wx.StaticText(sb_time, label=_("Ora:"))
        self.choice_hour = wx.Choice(sb_time, choices=[f"{h:02d}" for h in range(24)])
        self.choice_hour.Bind(wx.EVT_SET_FOCUS, self.on_choice_focus)
        self.choice_hour.Bind(wx.EVT_CHOICE, self.on_choice_changed)

        lbl_min = wx.StaticText(sb_time, label=_("Minuto:"))
        self.choice_min = wx.Choice(
            sb_time, choices=[f"{m:02d}" for m in range(0, 60, 5)]
        )
        self.choice_min.Bind(wx.EVT_SET_FOCUS, self.on_choice_focus)
        self.choice_min.Bind(wx.EVT_CHOICE, self.on_choice_changed)

        curr_time_str = self.schedule_info.get("time", "15:00")
        c_hour, c_min = "15", "00"
        if ":" in curr_time_str:
            parts = curr_time_str.split(":")
            if len(parts) == 2:
                c_hour, c_min = parts[0], parts[1]
                try:
                    m_val = int(c_min)
                    m_val = 5 * round(m_val / 5)
                    if m_val >= 60:
                        m_val = 55
                    c_min = f"{m_val:02d}"
                except ValueError:
                    pass

        self.choice_hour.SetStringSelection(c_hour)
        self.choice_min.SetStringSelection(c_min)

        sbs_time.Add(lbl_hour, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        sbs_time.Add(self.choice_hour, 1, wx.RIGHT, 15)
        sbs_time.Add(lbl_min, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        sbs_time.Add(self.choice_min, 1)

        vbox.Add(sbs_time, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # 3. Campi Sala/URL e Arbitro
        sb_details = wx.StaticBox(panel, label=_("Dettagli Sede e Arbitro"))
        sbs_details = wx.StaticBoxSizer(sb_details, wx.VERTICAL)

        lbl_room = wx.StaticText(sb_details, label=_("Sala / URL:"))
        self.txt_room = wx.TextCtrl(sb_details)
        self.txt_room.SetValue(self.schedule_info.get("channel", ""))
        self.txt_room.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        # Dalla 10.2.0 chi programma dice se l'arbitro serve. La casella viene
        # prima del campo nell'ordine di tabulazione, ed e' creata prima della
        # sua etichetta, cosi' il campo tiene la propria; attiva, spegne il
        # campo. Le programmazioni vecchie con scritto Non necessario la
        # trovano gia' attiva.
        from stats import arbitro_non_necessario

        non_serve = arbitro_non_necessario(self.schedule_info)
        self.chk_no_arbiter = wx.CheckBox(sb_details, label=_("Arbitro non necessario"))
        self.chk_no_arbiter.SetValue(non_serve)
        self.chk_no_arbiter.Bind(wx.EVT_CHECKBOX, self.on_no_arbiter)
        self.chk_no_arbiter.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        lbl_arbiter = wx.StaticText(sb_details, label=_("Arbitro designato:"))
        self.txt_arbiter = wx.TextCtrl(sb_details)
        self.txt_arbiter.SetValue(
            "" if non_serve else self.schedule_info.get("arbiter", "")
        )
        self.txt_arbiter.Enable(not non_serve)
        self.txt_arbiter.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        sbs_details.Add(lbl_room, 0, wx.TOP | wx.BOTTOM, 2)
        sbs_details.Add(self.txt_room, 0, wx.EXPAND | wx.BOTTOM, 8)
        sbs_details.Add(self.chk_no_arbiter, 0, wx.BOTTOM, 8)
        sbs_details.Add(lbl_arbiter, 0, wx.TOP | wx.BOTTOM, 2)
        sbs_details.Add(self.txt_arbiter, 0, wx.EXPAND)

        vbox.Add(sbs_details, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # Pulsanti OK e Annulla
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("Annulla"))
        btn_ok = wx.Button(panel, wx.ID_OK, _("Conferma"))
        btn_ok.SetDefault()

        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, 10)
        btn_sizer.Add(btn_ok, 0)
        vbox.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        panel.SetSizer(vbox)

        # Associazione tasti
        panel.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.txt_room.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.chk_no_arbiter.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.txt_arbiter.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

    def on_no_arbiter(self, event):
        self.txt_arbiter.Enable(not self.chk_no_arbiter.GetValue())
        event.Skip()

    def apply_theme(self):
        apply_visual_settings(self, self.settings)

    # Issue 48, la campanella era troppo invadente. Dalla 10.3.0 le scelte
    # hanno un bip la cui altezza dice la posizione della voce, un semitono
    # per voce; dalla 10.3.1 i controlli hanno una sinusoide brevissima.

    def on_rb_focus(self, event):
        rb = event.GetEventObject()
        rb.SetValue(True)
        from utils import bip_di_scelta

        indice = next(
            (i for i, (_d, r) in enumerate(self.radio_buttons) if r is rb), 0
        )
        bip_di_scelta(indice, len(self.radio_buttons), self.tournament_data)
        event.Skip()

    def on_choice_focus(self, event):
        self._bip_della_scelta(event.GetEventObject())
        event.Skip()

    def on_choice_changed(self, event):
        self._bip_della_scelta(event.GetEventObject())
        event.Skip()

    def _bip_della_scelta(self, scelta):
        from utils import bip_di_scelta

        indice = scelta.GetSelection()
        if indice != wx.NOT_FOUND:
            bip_di_scelta(indice, scelta.GetCount(), self.tournament_data)

    def on_control_focus(self, event):
        from utils import play_sound

        play_sound("controllo_programmazione", self.tournament_data)
        event.Skip()

    # Gli esiti, conferma e annullamento, non li suona questa finestra ma
    # on_schedule della ResultDialog, che la apre: dalla 10.6.2 non c'e' piu'
    # un EndModal che suonava l'annullamento una seconda volta.

    def on_key_down(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_RETURN or key == wx.WXK_NUMPAD_ENTER:
            self.EndModal(wx.ID_OK)
        elif key == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()

    def get_schedule_info(self):
        selected_date = None
        for d, rb in self.radio_buttons:
            if rb.GetValue():
                selected_date = d.strftime("%Y-%m-%d")
                break
        if not selected_date:
            import datetime

            selected_date = datetime.date.today().strftime("%Y-%m-%d")

        selected_time = f"{self.choice_hour.GetStringSelection()}:{self.choice_min.GetStringSelection()}"
        non_serve = self.chk_no_arbiter.GetValue()
        # Con la casella attiva il campo porta la dicitura, cosi' resoconti,
        # albero e console, che leggono solo il campo, dicono Non necessario;
        # l'indicatore e' quello che conta per l'AR del pie' di pagina.
        return {
            "date": selected_date,
            "time": selected_time,
            "channel": self.txt_room.GetValue().strip(),
            "arbiter": _("Non necessario")
            if non_serve
            else self.txt_arbiter.GetValue().strip(),
            "arbiter_not_needed": non_serve,
        }


class ResultDialog(wx.Dialog):
    """
    Finestra di dialogo modale per inserire o variare il risultato di una partita.
    Presenta opzioni radio verticali ampie e ben spaziate personalizzate con i nomi dei giocatori.
    Navigando con Tab o Frecce, la selezione del risultato si attiva automaticamente.
    Invio conferma direttamente la scelta, Esc annulla tutto.
    """

    def __init__(
        self,
        parent,
        white_name,
        black_name,
        white_id,
        black_id,
        board_num,
        current_result,
        schedule_info,
        settings,
        pgn_text="",
        disable_result_change=False,
    ):
        title = _("Risultato Scacchiera {num}").format(num=board_num)
        super().__init__(
            parent,
            title=title,
            style=STILE_ADATTABILE,
        )

        self.settings = settings
        self.white_name = white_name
        self.black_name = black_name
        self.white_id = white_id
        self.black_id = black_id
        self.board_num = board_num
        self.current_result = current_result
        self.schedule_info = schedule_info or {}
        self.pgn_text = pgn_text or ""
        self.disable_result_change = disable_result_change

        self.selected_action = None  # None (risultato), "schedule", "withdraw"
        self.withdrawn_player_id = None

        self._init_ui()
        self.apply_theme()
        adatta_finestra(self, self.pannello, MISURA_RISULTATO)

        # Il suono dell'apertura, dalla 10.6.1 al posto della campanella
        # (issue 51). Se il focus arriva poi su un risultato, subito dopo si
        # sente anche il suo arpeggio.
        from utils import play_sound

        play_sound("apertura_risultati")

    def _init_ui(self):
        panel = self.pannello = pannello_scorrevole(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # --- DETTAGLI PARTITA ---
        sched_lbl = ""
        if self.schedule_info.get("date") and self.schedule_info.get("time"):
            d_formatted = format_date_locale(self.schedule_info["date"])
            sched_lbl = _("\nPianificata per: {date} alle {time}").format(
                date=d_formatted, time=self.schedule_info["time"]
            )
            if self.schedule_info.get("channel"):
                sched_lbl += _(" | Sala/URL: {}").format(self.schedule_info["channel"])
            if self.schedule_info.get("arbiter"):
                sched_lbl += _(" | Arbitro: {}").format(self.schedule_info["arbiter"])

        match_info = (
            _("Scacchiera {}:\n").format(self.board_num)
            + f"  {_('Bianco')}: {self.white_name}\n"
            f"  {_('Nero')}: {self.black_name}{sched_lbl}\n"
        )
        self.lbl_info = wx.StaticText(panel, label=match_info)
        vbox.Add(self.lbl_info, 0, wx.ALL | wx.EXPAND, 15)

        # --- OPZIONI RISULTATO (Nomi dei giocatori anziché generici) ---
        sb_options = wx.StaticBox(panel, label=_("Seleziona Risultato"))
        sbs_options = wx.StaticBoxSizer(sb_options, wx.VERTICAL)

        self.options = [
            ("1-0", _("1 - 0 (Vince {})").format(self.white_name)),
            ("0-1", _("0 - 1 (Vince {})").format(self.black_name)),
            ("1/2-1/2", _("1/2 - 1/2 (Patta)")),
            (
                "1-F",
                # "Forfait X / Assenza Y" non diceva a chi si riferisse cosa,
                # perche' forfait e assenza sono la stessa cosa detta in due modi.
                _("1 - F (vince {} a tavolino, non si e' presentato {})").format(
                    self.white_name, self.black_name
                ),
            ),
            (
                "F-1",
                _("F - 1 (vince {} a tavolino, non si e' presentato {})").format(
                    self.black_name, self.white_name
                ),
            ),
            ("0-0F", _("0 - 0F (non si e' presentato nessuno dei due)")),
        ]

        # Dalla 10.6.4 i pulsanti sono figli del riquadro, come vuole
        # wxPython, e lo screen reader ne ricava il nome del gruppo (issue
        # 49). Tutti e sei hanno lo stesso genitore, quindi restano un gruppo
        # solo, con un solo risultato scelto alla volta.
        self.radio_buttons = []
        first = True
        for val, desc in self.options:
            style = wx.RB_GROUP if first else 0
            rb = wx.RadioButton(sb_options, label=desc, style=style)
            rb.SetValue(val == self.current_result)
            sbs_options.Add(rb, 0, wx.ALL | wx.EXPAND, 6)

            # Associazione eventi per spostamento facilitato e suono
            rb.Bind(wx.EVT_SET_FOCUS, self.on_rb_focus)
            rb.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

            self.radio_buttons.append((val, rb))
            first = False

        vbox.Add(sbs_options, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        # --- CAMPO PGN ---
        self.lbl_pgn = wx.StaticText(
            panel, label=_("Incolla qui il pgn della partita (opzionale):")
        )
        self.txt_pgn = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE, size=self.FromDIP(wx.Size(-1, 100))
        )
        self.txt_pgn.SetValue(self.pgn_text)
        self.txt_pgn.Bind(wx.EVT_TEXT, self.on_pgn_changed)

        self.lbl_validation_error = wx.StaticText(panel, label="")
        self.lbl_validation_error.SetForegroundColour(wx.Colour(200, 0, 0))

        vbox.Add(self.lbl_pgn, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)
        vbox.Add(self.txt_pgn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        vbox.Add(self.lbl_validation_error, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # --- AZIONI DI PIANIFICAZIONE E RITIRO ---
        hbox_actions = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_schedule = wx.Button(panel, label=_("Pianifica Partita..."))
        self.btn_schedule.Bind(wx.EVT_BUTTON, self.on_schedule)
        self.btn_schedule.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        self.btn_withdraw = wx.Button(panel, label=_("Ritira Giocatore..."))
        self.btn_withdraw.Bind(wx.EVT_BUTTON, self.on_withdraw)
        self.btn_withdraw.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        hbox_actions.Add(self.btn_schedule, 1, wx.EXPAND | wx.RIGHT, 10)
        hbox_actions.Add(self.btn_withdraw, 1, wx.EXPAND)

        vbox.Add(hbox_actions, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        # --- BOTTONI OK / ANNULLA ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, _("Annulla"))
        btn_cancel.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        ok_label = (
            _("Salva PGN") if self.disable_result_change else _("Conferma Risultato")
        )
        self.btn_ok = wx.Button(panel, wx.ID_OK, ok_label)
        self.btn_ok.SetDefault()
        self.btn_ok.Bind(wx.EVT_SET_FOCUS, self.on_control_focus)

        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, 10)
        btn_sizer.Add(self.btn_ok, 0)

        vbox.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        if self.disable_result_change:
            for val, rb in self.radio_buttons:
                rb.Enable(False)
            self.btn_schedule.Enable(False)
            self.btn_withdraw.Enable(False)

        panel.SetSizer(vbox)

        # Bind generali keydown
        panel.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.btn_schedule.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.btn_withdraw.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.btn_ok.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        btn_cancel.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

    def on_char_hook(self, event):
        """INVIO con la conferma spenta, cioe' con un PGN non valido, fa
        suonare l'errore e lascia la finestra aperta, dalla 10.8.4. Il gancio
        arriva prima di ogni altro trattamento del tasto: senza, INVIO su una
        voce del risultato finiva a Windows, che con il pulsante predefinito
        spento lo scartava in silenzio, e on_key_down non lo vedeva. Sui
        pulsanti INVIO resta loro e li preme, come prima; nel campo del PGN va
        a capo."""
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and not self.btn_ok.IsEnabled():
            fuoco = self.FindFocus()
            if fuoco != self.txt_pgn and not isinstance(fuoco, wx.Button):
                from utils import play_sound

                play_sound("errore")
                return
        event.Skip()

    def apply_theme(self):
        apply_visual_settings(self.lbl_info, self.settings)
        for val, rb in self.radio_buttons:
            apply_visual_settings(rb, self.settings)
        apply_visual_settings(self.lbl_pgn, self.settings)
        apply_visual_settings(self.txt_pgn, self.settings)
        apply_visual_settings(self.lbl_validation_error, self.settings)
        apply_visual_settings(self.btn_schedule, self.settings)
        apply_visual_settings(self.btn_withdraw, self.settings)

    def get_selected_result(self):
        """Restituisce la stringa del risultato selezionato (es. '1-0', '1/2-1/2', etc.)."""
        for val, rb in self.radio_buttons:
            if rb.GetValue():
                return val
        return None

    def on_rb_focus(self, event):
        # Il solo passaggio del focus non sceglie piu' il risultato: con il
        # tabulatore si finiva per selezionare l'opzione su cui si atterrava, e
        # un Invio dato subito dopo la registrava. La scelta si fa con le
        # frecce, come in ogni gruppo di pulsanti di scelta, oppure con la
        # barra spaziatrice.
        rb = event.GetEventObject()
        for val, button in self.radio_buttons:
            if button == rb:
                from utils import play_sound

                play_sound(f"risultato_{val}")
                break
        event.Skip()

    # Issue 51, la campanella era troppo aggressiva anche qui. Dalla 10.6.1 i
    # quattro pulsanti, Pianifica, Ritira, Annulla e Conferma, hanno un suono
    # breve tutto loro, diverso da quello dell'apertura.

    def on_control_focus(self, event):
        from utils import play_sound

        play_sound("controllo_risultati")
        event.Skip()

    def on_key_down(self, event):
        key = event.GetKeyCode()
        if event.GetEventObject() == self.txt_pgn:
            event.Skip()
            return

        if key == wx.WXK_RETURN or key == wx.WXK_NUMPAD_ENTER:
            # Con la conferma spenta, cioe' con un PGN non valido, Invio non
            # registra niente: suona l'errore e la finestra resta aperta.
            # Fino alla 10.8.3 qui si confermava senza guardare il pulsante.
            # Di solito il tasto lo ferma prima on_char_hook; questo controllo
            # vale per quando arriva lo stesso. Dalla 10.8.4 decide il
            # pulsante, che on_pgn_changed accende e spegne.
            if not self.btn_ok.IsEnabled():
                from utils import play_sound

                play_sound("errore")
                return
            # Invio dentro il gruppo delle opzioni non conferma piu' da solo:
            # insieme alla selezione automatica sul focus bastavano un
            # tabulatore e un Invio per registrare un risultato non voluto.
            # Serve una scelta esplicita, con le frecce o con la barra.
            if any(button.GetValue() for _val, button in self.radio_buttons):
                self.EndModal(wx.ID_OK)
            else:
                event.Skip()
        elif key == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()

    def _esito_del_pgn(self, testo, colore=None):
        """Scrive sotto il campo l'esito della verifica del PGN.
        Dalla 10.6.3 il pannello scorre (issue 49): un messaggio piu' largo
        della finestra ne allarga il contenuto, e FitInside aggiorna lo
        scorrimento perche' lo si possa leggere per intero.
        """
        self.lbl_validation_error.SetLabel(testo)
        if colore is not None:
            self.lbl_validation_error.SetForegroundColour(colore)
        self.pannello.FitInside()

    def on_pgn_changed(self, event):
        val = self.txt_pgn.GetValue().strip()
        if not val:
            self._esito_del_pgn("")
            self.btn_ok.Enable(True)
            return

        import io

        import chess.pgn

        pgn_io = io.StringIO(val)
        try:
            game = chess.pgn.read_game(pgn_io)
            if game is None:
                self._esito_del_pgn(
                    _("Formato PGN non valido: nessun dato letto."),
                    wx.Colour(200, 0, 0),
                )
                self.btn_ok.Enable(False)
                return
            if game.errors:
                err_msg = str(game.errors[0])
                self._esito_del_pgn(
                    _("Formato PGN non valido: {err}").format(err=err_msg),
                    wx.Colour(200, 0, 0),
                )
                self.btn_ok.Enable(False)
                return

            has_moves = any(True for _ in game.mainline_moves())
            has_brackets = "[" in val and "]" in val
            if not has_moves and not has_brackets:
                self._esito_del_pgn(
                    _("Formato PGN non valido: testo non riconosciuto come PGN."),
                    wx.Colour(200, 0, 0),
                )
                self.btn_ok.Enable(False)
                return

            self._esito_del_pgn(_("Formato PGN valido."), wx.Colour(0, 150, 0))
            self.btn_ok.Enable(True)
        except Exception as e:
            self._esito_del_pgn(
                _("Errore validazione PGN: {err}").format(err=str(e)),
                wx.Colour(200, 0, 0),
            )
            self.btn_ok.Enable(False)

    def on_schedule(self, event):
        # Premendo Pianifica non suona niente: la finestra di programmazione,
        # appena riceve il focus, suona gia' il bip del giorno, e fino alla
        # 10.6.0 la campanella gli finiva sopra (issue 51). Gli esiti li suona
        # questo metodo: la partita pianificata o, dalla 10.6.2, l'annullamento,
        # che prima suonava anche la ScheduleDialog e si sentiva due volte.
        # Chiusa la programmazione, Windows riattiva questa finestra e rimette
        # il fuoco su btn_schedule: on_control_focus suona il tocco del
        # pulsante insieme all'esito. Lo stesso succede in on_withdraw, con il
        # fuoco su btn_withdraw. Il manuale lo dice nella 6.2.1 e nella 7.2.
        from utils import play_sound

        parent_frame = self.GetParent()
        t_data = getattr(parent_frame, "current_tournament", {})

        dlg = ScheduleDialog(self, self.schedule_info, self.settings, t_data)
        if dlg.ShowModal() == wx.ID_OK:
            self.schedule_info = dlg.get_schedule_info()
            self.selected_action = "schedule"
            play_sound("pianifica_crea")
            self.EndModal(wx.ID_OK)
        else:
            play_sound("cancellato")
        dlg.Destroy()

    def on_withdraw(self, event):
        choices = [
            f"{self.white_name} (ID: {self.white_id})",
            f"{self.black_name} (ID: {self.black_id})",
        ]
        dlg = wx.SingleChoiceDialog(
            self,
            _("Seleziona il giocatore da ritirare definitivamente dal torneo:"),
            _("Ritiro Giocatore"),
            choices,
        )
        if dlg.ShowModal() == wx.ID_OK:
            sel = dlg.GetSelection()
            self.withdrawn_player_id = self.white_id if sel == 0 else self.black_id
            self.selected_action = "withdraw"
            self.EndModal(wx.ID_OK)
        dlg.Destroy()

    def ShowModal(self):
        """Il suono dell'esito si sente quando la finestra si chiude, in
        qualunque modo, una volta sola: la conferma con Conferma Risultato o
        con INVIO, l'annullamento con Annulla, ESC o la chiusura della
        finestra. Fino alla 10.13.23 lo suonava un EndModal ridefinito qui,
        che pero' chiamava soltanto il codice Python di questa finestra: la
        chiusura normale di wx, cioe' il pulsante predefinito per INVIO, il
        gestore di ESC e i pulsanti Annulla e Conferma, passa dall'EndModal
        del C++, e la finestra si chiudeva in silenzio. ShowModal invece
        ritorna in ogni caso, con il pulsante della chiusura.
        Dopo una programmazione confermata o la scelta del giocatore da
        ritirare non si sente la conferma: la partita pianificata ha il suo
        suono, che suona on_schedule, e il ritiro prosegue con le sue domande.
        L'annullamento della programmazione lo suona on_schedule, e la
        finestra resta aperta."""
        esito = super().ShowModal()
        from utils import play_sound

        if esito == wx.ID_OK:
            if not self.selected_action:
                play_sound("conferma")
        else:
            play_sound("cancellato")
        return esito
