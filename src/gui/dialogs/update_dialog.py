"""Le due finestre dell'aggiornamento di Tornello. Issue 37.

UpdateDialog propone la versione nuova con le sue note, UpdateProgressDialog
accompagna lo scaricamento. Fino alla 10.6.5 la proposta era un
AccessibleMsgDialog con Si' e No, che diceva le due versioni ma non le note
della release, e lo scaricamento non si vedeva da nessuna parte, se non in
una riga della barra di stato.
"""

import builtins

import wx
from GBwx import STILE_ADATTABILE, adatta_finestra, pannello_scorrevole

from gui.accessibility import NomeAccessibile
from gui.settings import apply_visual_settings

_ = getattr(builtins, "_", lambda s: s)

# Ogni quanti punti percentuali la finestra dello scaricamento riscrive il suo
# messaggio: come gestisci_aggiornamento di GBUtils nella versione da console,
# perche' cento annunci sarebbero un muro di parole per lo screen reader.
PASSO_DELL_AVANZAMENTO = 20

# I byte di un megabyte, per il messaggio dello scaricamento.
BYTE_PER_MB = 1024 * 1024

# Il totale e la parte scaricata di prova con cui la finestra dello
# scaricamento misura il suo messaggio piu' largo: il pacchetto di Tornello
# pesa un centinaio di megabyte, e tre cifre intere bastano.
MB_DI_PROVA = 999.9 * BYTE_PER_MB


def testo_delle_note(versione_attuale, versione_nuova, note):
    """Il contenuto del campo delle note: la prima riga dice le due versioni,
    quella di partenza e quella di arrivo, e le altre le note della release.
    La versione nuova arriva dal tag della release su GitHub, che ha una v
    davanti, v10.9.0, mentre quella del programma non l'ha: la v si toglie a
    tutte e due, perche' la riga le dica allo stesso modo.
    Le note arrivano da GitHub con i ritorni a capo di Windows e spesso con
    righe vuote in cima o in fondo: si tengono le righe come sono, con il solo
    a capo semplice, senza i bordi vuoti. Se mancano lo si dice, invece di
    lasciare il campo con la sola riga delle versioni.
    """
    righe = (note or "").strip().splitlines()
    corpo = "\n".join(righe) if righe else _("Nessuna nota per questa versione.")
    versioni = _("Versione attuale {attuale}, nuova {nuova}.").format(
        attuale=str(versione_attuale).lstrip("vV"), nuova=str(versione_nuova).lstrip("vV")
    )
    return f"{versioni}\n{corpo}"


def testo_dell_avanzamento(percento, preso, totale):
    """Il messaggio dello scaricamento, come 40%, 37,5 MB su 93,6 MB. I
    megabyte hanno un decimale e la virgola, come li scrive la versione da
    console e come NVDA li legge in italiano."""

    def mb(byte):
        return f"{byte / BYTE_PER_MB:.1f}".replace(".", ",")

    return _("{percento}%, {preso} MB su {totale} MB.").format(percento=percento, preso=mb(preso), totale=mb(totale))


def testo_finale():
    """Il messaggio di fine scaricamento, entro le quaranta celle della barra
    braille."""
    return _("Scaricato, preparo l'aggiornamento.")


class UpdateDialog(wx.Dialog):
    """Propone la versione nuova con le sue note e due pulsanti espliciti.

    Le note stanno in un campo di sola lettura, che riceve il fuoco
    all'apertura: la prima riga dice da quale versione si parte e a quale si
    arriva, e NVDA la legge subito, mentre un testo statico sopra il campo
    potrebbe non leggerlo da solo, come insegna AccessibleMsgDialog. Le righe
    si percorrono e si rileggono con le frecce.
    INVIO aggiorna, come la conferma della versione a riga di comando; ESC e
    la chiusura della finestra valgono Non adesso.
    Il modello e' la finestra di Dadillo e di Cartella, con la misura presa da
    GBwx come nelle altre finestre di Tornello dalla 10.6.3.
    """

    def __init__(self, parent, versione_attuale, versione_nuova, note, settings=None):
        super().__init__(parent, title=_("Aggiornamento Disponibile"), style=STILE_ADATTABILE)
        self.settings = settings
        panel = self.pannello = pannello_scorrevole(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.etichetta_note = wx.StaticText(panel, label=_("Novità di questa versione:"))
        vbox.Add(self.etichetta_note, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.campo_note = wx.TextCtrl(
            panel,
            value=testo_delle_note(versione_attuale, versione_nuova, note),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2,
        )
        vbox.Add(self.campo_note, 1, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_aggiorna = wx.Button(panel, wx.ID_YES, _("Aggiorna adesso"))
        self.btn_rimanda = wx.Button(panel, wx.ID_NO, _("Non adesso"))
        self.btn_aggiorna.SetDefault()
        btn_sizer.Add(self.btn_aggiorna, 0, wx.RIGHT, 10)
        btn_sizer.Add(self.btn_rimanda, 0)
        vbox.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 15)
        panel.SetSizer(vbox)

        # ESC, la X e Alt+F4 valgono Non adesso: wx li traduce in un evento
        # del pulsante con l'identificativo di ESC, mandato al dialogo e non
        # al pulsante, ed e' per questo che i due gestori stanno sul dialogo,
        # dove arrivano anche i clic veri. Il pulsante predefinito e'
        # Aggiorna adesso.
        self.SetAffirmativeId(wx.ID_YES)
        self.SetEscapeId(wx.ID_NO)
        self.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_YES), id=wx.ID_YES)
        self.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_NO), id=wx.ID_NO)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_tasto)

        if self.settings:
            for controllo in (self, panel, self.etichetta_note, self.campo_note, self.btn_aggiorna, self.btn_rimanda):
                apply_visual_settings(controllo, self.settings)

        adatta_finestra(self, self.pannello, (600, 450))
        self.campo_note.SetInsertionPoint(0)
        wx.CallAfter(lambda: self and self.campo_note.SetFocus())

    def _on_tasto(self, event):
        """INVIO nel campo delle note vale Aggiorna adesso. Un campo
        multilinea puo' tenere per se' il tasto invece di passarlo al
        pulsante predefinito, anche in sola lettura: qui lo si porta al
        pulsante in modo esplicito, senza dipendere da come wx lo tratta. Sui
        pulsanti INVIO resta loro, e su Non adesso rimanda. Ogni altro tasto
        prosegue, ESC compreso, che il dialogo traduce in Non adesso."""
        invio = event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
        if invio and not event.HasAnyModifiers() and wx.Window.FindFocus() is self.campo_note:
            self.EndModal(wx.ID_YES)
            return
        event.Skip()


class UpdateProgressDialog(wx.Dialog):
    """La finestra che accompagna lo scaricamento dell'aggiornamento.

    Non e' modale: chi la apre blocca il resto del programma con un
    wx.WindowDisabler, perche' la domanda che l'ha preceduta arriva da un
    thread che aspetta la risposta, e un ciclo modale annidato lo terrebbe
    fermo fino alla chiusura della finestra. Non si chiude ne' con ESC ne'
    con la X ne' con Alt+F4: lo scaricamento non si interrompe, e alla fine
    la distrugge chi l'ha aperta.
    Il fuoco sta sulla barra, che NVDA segue come fa con quella
    dell'aggiornamento FIDE, e ogni venti per cento il messaggio sopra la
    barra dice a che punto si e', con i megabyte scritti come nella versione
    da console, virgola compresa. Il messaggio e' anche il nome della barra,
    e a ogni cambio lo si notifica allo screen reader: NVDA legge il nome
    nuovo del controllo che ha il fuoco.
    La finestra e' larga quanto il messaggio piu' lungo che potra' mostrare,
    non quanto il primo: allargarla a meta' scaricamento la farebbe saltare
    sullo schermo, e lasciarla com'era taglierebbe il testo a chi vede.
    """

    def __init__(self, parent, settings=None):
        super().__init__(parent, title=_("Aggiornamento di Tornello"), style=STILE_ADATTABILE)
        self.settings = settings
        self._ultimo_passo = 0
        panel = self.pannello = pannello_scorrevole(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        testo = _("Scarico l'aggiornamento.")
        self.status_label = wx.StaticText(panel, label=testo)
        vbox.Add(self.status_label, 0, wx.ALL | wx.EXPAND, 15)
        self.gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        vbox.Add(self.gauge, 0, wx.ALL | wx.EXPAND, 15)
        panel.SetSizer(vbox)
        self._nome_della_barra = NomeAccessibile(self.gauge, testo)
        self.gauge.SetAccessible(self._nome_della_barra)

        if self.settings:
            for controllo in (self, panel, self.status_label, self.gauge):
                apply_visual_settings(controllo, self.settings)

        # I messaggi si misurano dopo aver dato il carattere, e prima di
        # adattare la finestra: la 10.7.0 la adattava al primo messaggio, e
        # quello finale, piu' lungo, finiva tagliato, con una barra di
        # scorrimento. Ciascuno passa per l'etichetta, che a finestra ancora
        # nascosta non annuncia niente, perche' la misura sia la sua e non
        # quella del solo testo, piu' stretta di un pixel; l'ultimo e' quello
        # iniziale.
        piu_largo = 0
        for possibile in (testo_finale(), testo_dell_avanzamento(100, MB_DI_PROVA, MB_DI_PROVA), testo):
            self.status_label.SetLabel(possibile)
            piu_largo = max(piu_largo, self.status_label.GetBestSize().width)
        self.status_label.SetMinSize(wx.Size(piu_largo, -1))
        adatta_finestra(self, self.pannello, (400, 160))
        self.SetEscapeId(wx.ID_NONE)
        self.EnableCloseButton(False)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        wx.CallAfter(lambda: self and self.gauge.SetFocus())

    def _on_close(self, event):
        """La X, Alt+F4 o una chiusura chiesta dal sistema: si resta aperti
        finche' si puo' dire di no."""
        if event.CanVeto():
            event.Veto()
        else:
            event.Skip()

    def _scrivi(self, testo):
        """Riscrive il messaggio e il nome della barra, e lo annuncia. Il
        pannello scorre dalla 10.6.3: FitInside aggiorna lo scorrimento se il
        testo nuovo e' piu' largo."""
        if self.status_label.GetLabel() == testo:
            return
        self.status_label.SetLabel(testo)
        self.pannello.FitInside()
        self._nome_della_barra.nome = testo
        wx.Accessible.NotifyEvent(wx.ACC_EVENT_OBJECT_NAMECHANGE, self.gauge, wx.OBJID_CLIENT, wx.ACC_SELF)

    def aggiorna(self, preso, totale):
        """I byte presi e il totale atteso, che vale zero quando il server
        non lo dichiara: allora la barra si muove avanti e indietro, senza
        percentuale. A scaricamento finito il messaggio dice che si prepara
        l'aggiornamento, perche' l'estrazione dell'archivio dura qualche
        secondo e non manda segnali."""
        if not totale:
            self.gauge.Pulse()
            return
        percento = max(0, min(100, int(preso * 100 / totale)))
        self.gauge.SetValue(percento)
        if preso >= totale:
            self._scrivi(testo_finale())
            return
        passo = percento - percento % PASSO_DELL_AVANZAMENTO
        if passo > self._ultimo_passo:
            self._ultimo_passo = passo
            self._scrivi(testo_dell_avanzamento(percento, preso, totale))
