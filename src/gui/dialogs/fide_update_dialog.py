import builtins
import threading

import wx
from db_players import aggiorna_db_fide_locale

from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog
from gui.settings import apply_visual_settings

_ = getattr(builtins, "_", lambda s: s)


class FideUpdateThread(threading.Thread):
    """
    Thread per eseguire lo scaricamento e la creazione del DB FIDE SQLite
    senza bloccare l'interfaccia grafica.
    """

    def __init__(self, progress_callback, completion_callback, interrompi):
        # Daemon: se il programma si chiude a meta' scaricamento, per esempio
        # per applicare un aggiornamento, non deve restare in vita ad aspettare
        # la fine di un lavoro che nessuno vedra' piu'.
        super().__init__(daemon=True)
        self.progress_callback = progress_callback
        self.completion_callback = completion_callback
        self.interrompi = interrompi
        self.success = False
        self.stats = {}

    def run(self):
        try:
            self.success = aggiorna_db_fide_locale(
                progress_callback=self.progress_callback,
                stats_output=self.stats,
                interrompi=self.interrompi,
            )
        except Exception as errore:
            # Anche un errore che sfugge del tutto deve arrivare all'utente
            # con il suo motivo, invece di sparire.
            self.success = False
            self.stats["error"] = str(errore)
        wx.CallAfter(self.completion_callback, self.success, self.stats)


class FideUpdateDialog(wx.Dialog):
    """
    Finestra di dialogo per lo scaricamento e l'aggiornamento del DB FIDE locale.
    Mostra informazioni accessibili a NVDA sul progresso reale di scaricamento e analisi.
    """

    def __init__(self, parent, settings):
        title = _("Aggiornamento Database FIDE")
        super().__init__(
            parent, title=title, size=(500, 250), style=wx.DEFAULT_DIALOG_STYLE
        )

        self.settings = settings
        self.last_announced_percent = (
            -5
        )  # Annuncia ogni 5% per non saturare lo screen reader

        self.init_ui()
        self.apply_theme()
        self.Centre()

        # La finestra puo' sparire mentre il thread lavora: chiusa dalla X o
        # da Alt+F4, oppure distrutta perche' il programma si chiude per
        # applicare un aggiornamento accettato nel frattempo. Prima il thread
        # continuava a scrivere su una barra che non esisteva piu', e ogni
        # blocco ricevuto finiva nel log come RuntimeError sul Gauge. Ora la
        # chiusura alza questo evento, che ferma il lavoro al primo blocco
        # utile, e i callback controllano che la finestra esista ancora.
        self.interrompi = threading.Event()
        self.Bind(wx.EVT_CLOSE, self.on_close)

        # Avvio del thread in background
        self.thread = FideUpdateThread(
            self.on_progress, self.on_update_complete, self.interrompi
        )
        self.thread.start()

        # Impostiamo subito il focus sul Gauge per far sì che NVDA legga gli aggiornamenti di progresso
        wx.CallAfter(lambda: self and self.gauge.SetFocus())

    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Label di stato posizionata immediatamente prima del Gauge per accessibilità
        self.status_label = wx.StaticText(
            panel,
            label=_(
                "Connessione al server FIDE in corso...\n"
                "Avvio dello scaricamento del database FIDE Ratings."
            ),
        )
        vbox.Add(self.status_label, 0, wx.ALL | wx.EXPAND, 15)

        self.gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        vbox.Add(self.gauge, 0, wx.ALL | wx.EXPAND, 15)

        # Annulla resta attivo durante l'aggiornamento, e ferma davvero il
        # lavoro: prima era spento, e chi voleva interrompere non poteva farlo
        # se non chiudendo la finestra, con il thread che andava avanti lo
        # stesso. Vale anche per il tasto Esc, che in un dialogo equivale a
        # premere il pulsante Annulla.
        self.btn_close = wx.Button(panel, wx.ID_CANCEL, _("Annulla"))
        self.btn_close.Bind(wx.EVT_BUTTON, self.on_close)
        vbox.Add(self.btn_close, 0, wx.ALIGN_RIGHT | wx.ALL, 15)

        panel.SetSizer(vbox)
        vbox.Fit(self)

    def apply_theme(self):
        apply_visual_settings(self, self.settings)
        for child in self.GetChildren():
            apply_visual_settings(child, self.settings)

    def on_close(self, event=None):
        """Chiusura dalla X, da Alt+F4, da Esc o dal pulsante: ferma il lavoro.

        Il thread si accorge dell'evento al primo blocco utile e scarta il
        database temporaneo; la finestra non lo aspetta, perche' l'attesa
        potrebbe durare secondi e chi ha chiesto di chiudere vuole che
        succeda subito. Il suo callback di completamento trovera' la
        finestra gia' distrutta e non fara' nulla.
        """
        self.interrompi.set()
        if self.IsModal():
            self.EndModal(wx.ID_CANCEL)
        else:
            self.Destroy()

    def _viva(self):
        """Vero se la finestra esiste ancora e nessuno ha chiesto di fermarsi.

        In wxPython una finestra distrutta vale falso: e' il controllo che
        mancava, e senza il quale un aggiornamento arrivato dopo la
        distruzione finiva su un Gauge che non c'era piu'. Non basta da
        solo: la distruzione di una finestra principale e' rinviata al
        momento di riposo del ciclo eventi, e in quell'attimo la finestra
        vale ancora vero pur essendo condannata. IsBeingDeleted copre
        quell'attimo.
        """
        return bool(self) and not self.IsBeingDeleted() and not self.interrompi.is_set()

    def on_progress(self, phase, current, total):
        """Callback chiamata dal thread di background per notificare l'avanzamento."""
        wx.CallAfter(self.update_progress, phase, current, total)

    def update_progress(self, phase, current, total):
        if not self._viva() or total <= 0:
            return

        percent = int((current / total) * 100)
        percent = max(0, min(100, percent))
        self.gauge.SetValue(percent)

        # Formattazione accessibile a NVDA
        if phase == "download":
            title_text = _("Scaricamento Database FIDE...")
            if self.GetTitle() != title_text:
                self.SetTitle(title_text)

            current_mb = current / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            msg = _(
                "Scaricamento in corso: {percent}% ({current_mb:.1f} MB / {total_mb:.1f} MB)..."
            ).format(percent=percent, current_mb=current_mb, total_mb=total_mb)
            if self.status_label.GetLabel() != msg:
                self.status_label.SetLabel(msg)

        elif phase == "processing":
            title_text = _("Analisi del DB FIDE e creazione DB SQLite...")
            if self.GetTitle() != title_text:
                self.SetTitle(title_text)

            msg = _("Scrittura del database SQLite: {percent}%...").format(
                percent=percent
            )
            if self.status_label.GetLabel() != msg:
                self.status_label.SetLabel(msg)

        # Se la percentuale è cambiata di almeno il 5%, aggiorna l'annuncio accessibile
        if abs(percent - self.last_announced_percent) >= 5:
            self.last_announced_percent = percent
            # Aggiornando il nome o la descrizione accessibile, forziamo NVDA ad annunciare il valore
            self.gauge.SetName(f"{percent}%")

    def on_update_complete(self, success, stats):
        if not self._viva():
            # Finestra chiusa o distrutta prima della fine: il thread ha gia'
            # scartato il database temporaneo, e non c'e' nessuno a cui
            # riferire.
            return
        self.gauge.SetValue(100)
        self.btn_close.SetLabel(_("Chiudi"))

        if success:
            # Funzione di supporto per formattare la durata in mm:ss:dcm
            def format_duration(seconds):
                minutes = int(seconds // 60)
                remaining_secs = seconds % 60
                secs = int(remaining_secs)
                dcm = int((remaining_secs - secs) * 10)
                return f"{minutes:02d}:{secs:02d}:{dcm:d}"

            d_time = format_duration(stats.get("download_time", 0.0))
            p_time = format_duration(stats.get("processing_time", 0.0))
            saved_count = stats.get("saved_count", 0)

            old_c = stats.get("old_count", 0)
            new_c = stats.get("new_count", 0)

            success_msg = _(
                "Database FIDE locale aggiornato con successo!\n\n"
                "Tempo impiegato per il download: {d_time}\n"
                "Tempo per l'elaborazione del DB SQLite: {p_time}\n"
                "Totale giocatori salvati: {saved_count}"
            ).format(d_time=d_time, p_time=p_time, saved_count=saved_count)

            # Se c'era già un DB con dei record, mostriamo la differenza e la percentuale
            if old_c > 0:
                diff = new_c - old_c
                perc = (diff / old_c) * 100 if old_c > 0 else 0.0
                sign = "+" if diff >= 0 else ""
                success_msg += _(
                    "\n\nStatistiche di aggiornamento:\n"
                    "Prima {old_c} giocatori, ora {new_c} = {sign}{diff} ({sign}{perc:.2f}%)"
                ).format(old_c=old_c, new_c=new_c, sign=sign, diff=diff, perc=perc)

            self.status_label.SetLabel(
                _("Database FIDE locale aggiornato con successo!")
            )

            # Utilizza il dialogo personalizzato e accessibile per mostrare le statistiche
            dlg = AccessibleMsgDialog(
                self,
                _("Successo"),
                success_msg,
            )
            dlg.ShowModal()
            # Se il programma si chiude mentre il messaggio e' aperto, il
            # messaggio muore insieme a tutto il resto e ShowModal torna da
            # solo: distruggere di nuovo, o chiudere una finestra gia'
            # condannata, darebbe lo stesso errore che si vuole evitare.
            if dlg:
                dlg.Destroy()
            if self._viva() and self.IsModal():
                self.EndModal(wx.ID_OK)
        else:
            self.status_label.SetLabel(
                _("Errore durante l'aggiornamento del Database FIDE.")
            )
            # Il motivo vero viene da chi ha svolto il lavoro: prima veniva
            # sempre indicata la connessione, anche quando la causa era un'altra.
            motivo = (stats or {}).get("error")
            if motivo:
                messaggio = _(
                    "Aggiornamento del Database FIDE non riuscito.\n\nMotivo: {reason}\n\nIl database che avevi prima e' rimasto intatto e resta utilizzabile."
                ).format(reason=motivo)
            else:
                messaggio = _(
                    "Aggiornamento del Database FIDE non riuscito. Controlla la connessione ad internet.\n\nIl database che avevi prima e' rimasto intatto e resta utilizzabile."
                )
            dlg = AccessibleMsgDialog(
                self,
                _("Errore"),
                messaggio,
            )
            dlg.ShowModal()
            if dlg:
                dlg.Destroy()
            if self._viva() and self.IsModal():
                self.EndModal(wx.ID_CANCEL)
