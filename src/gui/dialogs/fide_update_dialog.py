import wx
import builtins
import threading
from db_players import aggiorna_db_fide_locale
from gui.settings import apply_visual_settings

_ = getattr(builtins, "_", lambda s: s)


class FideUpdateThread(threading.Thread):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.success = False

    def run(self):
        try:
            self.success = aggiorna_db_fide_locale()
        except Exception:
            self.success = False
        wx.CallAfter(self.callback, self.success)


class FideUpdateDialog(wx.Dialog):
    """
    Finestra di dialogo per lo scaricamento e l'aggiornamento del DB FIDE locale.
    Visualizza un messaggio fisso di attesa e una barra di caricamento (Gauge) animata via Timer.
    L'operazione di rete e CPU-bound viene eseguita in un thread secondario per non bloccare la GUI.
    """

    def __init__(self, parent, settings):
        title = _("Aggiornamento Database FIDE")
        super().__init__(
            parent, title=title, size=(500, 250), style=wx.DEFAULT_DIALOG_STYLE
        )

        self.settings = settings
        self.init_ui()
        self.apply_theme()
        self.Centre()

    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Testo statico che indica l'avvio e la durata dell'operazione, evitando modifiche continue per NVDA
        self.status_label = wx.StaticText(
            panel,
            label=_(
                "Aggiornamento del Database FIDE locale in corso...\n"
                "L'operazione richiede solitamente 1-2 minuti di attesa.\n"
                "Attendere prego, la barra indica che l'elaborazione è attiva."
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

        # Timer per l'animazione costante della barra di progresso
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        self.timer.Start(100)  # Aggiorna la barra ogni 100ms

        # Avvio del thread in background
        self.thread = FideUpdateThread(self.on_update_complete)
        self.thread.start()

    def apply_theme(self):
        apply_visual_settings(self, self.settings)
        for child in self.GetChildren():
            apply_visual_settings(child, self.settings)

    def on_timer(self, event):
        self.gauge.Pulse()

    def on_update_complete(self, success):
        self.timer.Stop()
        self.gauge.SetValue(100)
        self.btn_close.SetLabel(_("Chiudi"))
        self.btn_close.Enable()

        if success:
            self.status_label.SetLabel(
                _("Database FIDE locale aggiornato con successo!")
            )
            wx.MessageBox(
                _("Database FIDE locale aggiornato con successo!"),
                _("Successo"),
                wx.ICON_INFORMATION,
            )
            self.EndModal(wx.ID_OK)
        else:
            self.status_label.SetLabel(
                _("Errore durante l'aggiornamento del Database FIDE.")
            )
            wx.MessageBox(
                _(
                    "Errore durante l'aggiornamento del Database FIDE. Controlla la connessione ad internet."
                ),
                _("Errore"),
                wx.ICON_ERROR,
            )
            self.EndModal(wx.ID_CANCEL)
