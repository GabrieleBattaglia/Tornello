import wx
import builtins
import threading
from db_players import aggiorna_db_fide_locale
from gui.settings import apply_visual_settings
from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog

_ = getattr(builtins, "_", lambda s: s)


class FideUpdateThread(threading.Thread):
    """
    Thread per eseguire lo scaricamento e la creazione del DB FIDE SQLite
    senza bloccare l'interfaccia grafica.
    """

    def __init__(self, progress_callback, completion_callback):
        super().__init__()
        self.progress_callback = progress_callback
        self.completion_callback = completion_callback
        self.success = False
        self.stats = {}

    def run(self):
        try:
            self.success = aggiorna_db_fide_locale(
                progress_callback=self.progress_callback, stats_output=self.stats
            )
        except Exception:
            self.success = False
            self.stats = {}
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

        # Avvio del thread in background
        self.thread = FideUpdateThread(self.on_progress, self.on_update_complete)
        self.thread.start()

        # Impostiamo subito il focus sul Gauge per far sì che NVDA legga gli aggiornamenti di progresso
        wx.CallAfter(self.gauge.SetFocus)

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

        self.btn_close = wx.Button(panel, wx.ID_CANCEL, _("Annulla"))
        self.btn_close.Disable()  # Disabilitato durante l'aggiornamento
        vbox.Add(self.btn_close, 0, wx.ALIGN_RIGHT | wx.ALL, 15)

        panel.SetSizer(vbox)
        vbox.Fit(self)

    def apply_theme(self):
        apply_visual_settings(self, self.settings)
        for child in self.GetChildren():
            apply_visual_settings(child, self.settings)

    def on_progress(self, phase, current, total):
        """Callback chiamata dal thread di background per notificare l'avanzamento."""
        wx.CallAfter(self.update_progress, phase, current, total)

    def update_progress(self, phase, current, total):
        if total <= 0:
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
        self.gauge.SetValue(100)
        self.btn_close.SetLabel(_("Chiudi"))
        self.btn_close.Enable()

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
            dlg.Destroy()
            self.EndModal(wx.ID_OK)
        else:
            self.status_label.SetLabel(
                _("Errore durante l'aggiornamento del Database FIDE.")
            )
            dlg = AccessibleMsgDialog(
                self,
                _("Errore"),
                _(
                    "Errore durante l'aggiornamento del Database FIDE. Controlla la connessione ad internet."
                ),
            )
            dlg.ShowModal()
            dlg.Destroy()
            self.EndModal(wx.ID_CANCEL)
