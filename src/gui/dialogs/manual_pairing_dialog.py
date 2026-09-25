"""La finestra della composizione manuale del turno. Issue 38.

Si apre soltanto quando bbpPairings risponde che non esiste un abbinamento
valido, e l'arbitro accetta di comporre il turno a mano. Parte dalla
proposta di Tornello, se i giocatori attivi non sono piu' di 16, e l'arbitro
la cambia: sceglie un giocatore, poi l'avversario, o il riposo, e il colore,
e aggiunge la coppia; toglie una coppia con CANC e ne inverte i colori. Le
regole stanno tutte in turno_manuale.py, che non usa wx: qui ci sono i
controlli, i suoni e le conferme. La finestra non cambia il torneo: alla
conferma lascia le coppie in coppie_confermate, e le registra la finestra
principale.
"""

import builtins

import wx
from GBwx import STILE_ADATTABILE, adatta_finestra, pannello_scorrevole

from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog
from gui.settings import apply_visual_settings
from turno_manuale import (
    MASSIMO_PER_LA_PROPOSTA,
    avversari_possibili,
    avvertimenti_coppia,
    colore_suggerito,
    giocatori_da_abbinare,
    nome_del_giocatore,
    ordina_coppie,
    proposta_abbinamento,
    righe_della_conferma,
    righe_della_situazione,
    valida_turno_manuale,
    voce_avversario,
    voce_coppia,
    voce_giocatore,
)
from utils import play_sound

_ = getattr(builtins, "_", lambda s: s)

TASTI_INVIO = (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)
TASTI_CANC = (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE)


class ManualPairingDialog(wx.Dialog):
    """La finestra Composizione manuale del turno.

    I controlli, nell'ordine del tasto TAB: la Situazione, in sola lettura e
    a righe corte per la barra braille; la lista dei Giocatori da abbinare;
    la lista Avversario, che segue il giocatore scelto e porta in ogni voce
    gli avvertimenti della coppia, con il Riposo (bye) in fondo quando
    serve; la scelta Bianco a, gia' sul colore suggerito; il pulsante
    Aggiungi coppia, che risponde anche a INVIO sull'avversario; la lista
    delle Coppie composte, dove CANC toglie la coppia; i pulsanti Togli
    coppia, Inverti colori, Proposta automatica, Conferma turno, acceso solo
    a coppie complete, e Annulla, che risponde anche a ESC.
    torneo e' il dizionario del torneo, che la finestra legge soltanto;
    turno e' il numero del turno da comporre.
    """

    def __init__(self, parent, torneo, turno, settings):
        super().__init__(parent, title=_("Composizione manuale del turno {turno}").format(turno=turno), style=STILE_ADATTABILE)
        self.settings = settings
        self.torneo = torneo
        self.turno = turno
        self.coppie = []
        self.coppie_confermate = None
        self._liberi = []
        self._avversari = []
        self._candidati_bianco = []

        self._init_ui()
        self.apply_theme()
        # La misura la da' il contenuto, dentro lo schermo, e 700 per 600
        # resta come minimo (issue 49). Le liste hanno una misura data in
        # caratteri: cosi' le voci lunghe, con gli avvertimenti, non allargano
        # la finestra oltre lo schermo, e le liste scorrono di lato.
        adatta_finestra(self, self.pannello, (700, 600))
        self.coppie = list(proposta_abbinamento(torneo) or [])
        self._aggiorna()
        wx.CallAfter(lambda: self and self.situazione.SetFocus())

    def _init_ui(self):
        panel = self.pannello = pannello_scorrevole(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Ogni controllo ha davanti la sua etichetta, e da li' lo screen
        # reader ne prende il nome; nessuno sta in un riquadro.
        self.lbl_situazione = wx.StaticText(panel, label=_("&Situazione:"))
        vbox.Add(self.lbl_situazione, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.situazione = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        vbox.Add(self.situazione, 0, wx.EXPAND | wx.ALL, 10)

        self.lbl_liberi = wx.StaticText(panel, label=_("&Giocatori da abbinare:"))
        vbox.Add(self.lbl_liberi, 0, wx.LEFT | wx.RIGHT, 10)
        self.lista_liberi = wx.ListBox(panel, style=wx.LB_SINGLE | wx.HSCROLL)
        self.lista_liberi.Bind(wx.EVT_LISTBOX, self.on_giocatore_scelto)
        self.lista_liberi.Bind(wx.EVT_CHAR_HOOK, self.on_tasto_liberi)
        vbox.Add(self.lista_liberi, 1, wx.EXPAND | wx.ALL, 10)

        self.lbl_avversari = wx.StaticText(panel, label=_("A&vversario:"))
        vbox.Add(self.lbl_avversari, 0, wx.LEFT | wx.RIGHT, 10)
        self.lista_avversari = wx.ListBox(panel, style=wx.LB_SINGLE | wx.HSCROLL)
        self.lista_avversari.Bind(wx.EVT_LISTBOX, self.on_avversario_scelto)
        self.lista_avversari.Bind(wx.EVT_CHAR_HOOK, self.on_tasto_avversari)
        vbox.Add(self.lista_avversari, 1, wx.EXPAND | wx.ALL, 10)

        riga_bianco = wx.BoxSizer(wx.HORIZONTAL)
        self.lbl_bianco = wx.StaticText(panel, label=_("&Bianco a:"))
        riga_bianco.Add(self.lbl_bianco, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self.scelta_bianco = wx.Choice(panel)
        riga_bianco.Add(self.scelta_bianco, 1, wx.EXPAND | wx.RIGHT, 10)
        self.btn_aggiungi = wx.Button(panel, label=_("&Aggiungi coppia"))
        self.btn_aggiungi.Bind(wx.EVT_BUTTON, self.on_aggiungi)
        riga_bianco.Add(self.btn_aggiungi, 0)
        vbox.Add(riga_bianco, 0, wx.EXPAND | wx.ALL, 10)

        self.lbl_coppie = wx.StaticText(panel, label=_("Coppie &composte:"))
        vbox.Add(self.lbl_coppie, 0, wx.LEFT | wx.RIGHT, 10)
        self.lista_coppie = wx.ListBox(panel, style=wx.LB_SINGLE | wx.HSCROLL)
        self.lista_coppie.Bind(wx.EVT_LISTBOX, self.on_coppia_scelta)
        self.lista_coppie.Bind(wx.EVT_CHAR_HOOK, self.on_tasto_coppie)
        vbox.Add(self.lista_coppie, 1, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_togli = wx.Button(panel, label=_("&Togli coppia"))
        self.btn_inverti = wx.Button(panel, label=_("&Inverti colori"))
        self.btn_proposta = wx.Button(panel, label=_("&Proposta automatica"))
        self.btn_conferma = wx.Button(panel, label=_("C&onferma turno"))
        self.btn_annulla = wx.Button(panel, wx.ID_CANCEL, label=_("Annulla"))
        self.btn_togli.Bind(wx.EVT_BUTTON, self.on_togli)
        self.btn_inverti.Bind(wx.EVT_BUTTON, self.on_inverti)
        self.btn_proposta.Bind(wx.EVT_BUTTON, self.on_proposta)
        self.btn_conferma.Bind(wx.EVT_BUTTON, self.on_conferma)
        self.btn_annulla.Bind(wx.EVT_BUTTON, self.on_annulla)
        for pulsante in self._pulsanti():
            btn_sizer.Add(pulsante, 0, wx.RIGHT, 5)
        vbox.Add(btn_sizer, 0, wx.ALL, 10)
        panel.SetSizer(vbox)

    def _pulsanti(self):
        return (self.btn_togli, self.btn_inverti, self.btn_proposta, self.btn_conferma, self.btn_annulla)

    def apply_theme(self):
        """Colori e caratteri del tema, poi le misure in righe e caratteri del
        carattere appena dato, mai in pixel."""
        controlli = (
            self,
            self.lbl_situazione,
            self.situazione,
            self.lbl_liberi,
            self.lista_liberi,
            self.lbl_avversari,
            self.lista_avversari,
            self.lbl_bianco,
            self.scelta_bianco,
            self.btn_aggiungi,
            self.lbl_coppie,
            self.lista_coppie,
            *self._pulsanti(),
        )
        for controllo in controlli:
            apply_visual_settings(controllo, self.settings)
        self.situazione.SetMinSize(wx.Size(self.situazione.GetCharWidth() * 42, self.situazione.GetCharHeight() * 6))
        for lista, righe in ((self.lista_liberi, 5), (self.lista_avversari, 5), (self.lista_coppie, 6)):
            lista.SetMinSize(wx.Size(lista.GetCharWidth() * 50, lista.GetCharHeight() * righe))
        self.scelta_bianco.SetMinSize(wx.Size(self.scelta_bianco.GetCharWidth() * 30, -1))

    # Lo stato: le coppie composte fin qui, e le liste che ne derivano, con
    # le regole di turno_manuale: chi e' ancora da abbinare e quali
    # avversari, riposo compreso, restano al giocatore scelto.

    @staticmethod
    def _seleziona(lista, indice):
        quante = lista.GetCount()
        if quante:
            lista.SetSelection(min(max(indice, 0), quante - 1))

    def _aggiorna(self, indice_libero=0, indice_coppia=0):
        """Riempie liste, scelta e situazione dalle coppie composte, e
        accende i pulsanti che servono. Le coppie restano nell'ordine delle
        scacchiere, che e' anche quello della lista."""
        self._liberi = giocatori_da_abbinare(self.torneo, self.coppie)
        self.lista_liberi.Set([voce_giocatore(self.torneo, player_id) for player_id in self._liberi])
        self._seleziona(self.lista_liberi, indice_libero)
        self.coppie = ordina_coppie(self.torneo, self.coppie)
        self.lista_coppie.Set([voce_coppia(self.torneo, numero, bianco, nero) for numero, (bianco, nero) in enumerate(self.coppie, 1)])
        self._seleziona(self.lista_coppie, indice_coppia)
        self._aggiorna_avversari()
        self.situazione.SetValue("\n".join(righe_della_situazione(self.torneo, self.coppie, self.turno)))
        self.situazione.SetInsertionPoint(0)
        errori, _avvertimenti = valida_turno_manuale(self.torneo, self.coppie)
        self.btn_conferma.Enable(not errori)
        self.btn_togli.Enable(bool(self.coppie))
        self._aggiorna_inverti()

    def _aggiorna_avversari(self):
        """La lista Avversario per il giocatore scelto: gli altri ancora da
        abbinare, e il riposo se i giocatori attivi sono dispari e nessuno ha
        ancora il bye."""
        indice = self.lista_liberi.GetSelection()
        if indice == wx.NOT_FOUND or indice >= len(self._liberi):
            self._avversari = []
        else:
            self._avversari = avversari_possibili(self.torneo, self.coppie, self._liberi[indice])
        voci = [voce_avversario(self.torneo, self._liberi[indice], avversario) for avversario in self._avversari]
        self.lista_avversari.Set(voci)
        self._seleziona(self.lista_avversari, 0)
        self._aggiorna_bianco()

    def _scelta_corrente(self):
        """Il giocatore scelto e il suo avversario, None per il riposo, o
        None se manca uno dei due."""
        indice = self.lista_liberi.GetSelection()
        indice_avversario = self.lista_avversari.GetSelection()
        if wx.NOT_FOUND in (indice, indice_avversario) or indice >= len(self._liberi) or indice_avversario >= len(self._avversari):
            return None
        return self._liberi[indice], self._avversari[indice_avversario]

    def _aggiorna_bianco(self):
        """La scelta Bianco a, con i due giocatori della coppia e il colore
        suggerito gia' scelto; spenta per il riposo o senza scelta."""
        scelta = self._scelta_corrente()
        self.btn_aggiungi.Enable(scelta is not None)
        if scelta is None or scelta[1] is None:
            self._candidati_bianco = []
            self.scelta_bianco.Set([])
            self.scelta_bianco.Enable(False)
            return
        scelto, avversario = scelta
        suggerito, _nero = colore_suggerito(self.torneo, scelto, avversario)
        self._candidati_bianco = [scelto, avversario]
        nomi = []
        for player_id in self._candidati_bianco:
            nome = nome_del_giocatore(self.torneo, player_id)
            if player_id == suggerito:
                nome = _("{nome} (suggerito)").format(nome=nome)
            nomi.append(nome)
        self.scelta_bianco.Set(nomi)
        self.scelta_bianco.SetSelection(self._candidati_bianco.index(suggerito))
        self.scelta_bianco.Enable(True)

    def _aggiorna_inverti(self):
        indice = self.lista_coppie.GetSelection()
        con_colori = indice != wx.NOT_FOUND and indice < len(self.coppie) and self.coppie[indice][1] is not None
        self.btn_inverti.Enable(con_colori)

    def _suona_coppie(self, coppie, senza, con):
        """Il suono di una o piu' coppie appena composte: l'evento con se
        almeno una ha avvertimenti, altrimenti l'evento senza. Aggiunta,
        inversione dei colori e proposta hanno ciascuna i suoi due eventi:
        una regola del parco vuole un suono diverso per ogni evento."""
        con_avvertimenti = any(avvertimenti_coppia(self.torneo, bianco, nero) for bianco, nero in coppie)
        play_sound(con if con_avvertimenti else senza)

    def _messaggio(self, titolo, testo):
        dlg = AccessibleMsgDialog(self, titolo, testo, settings=self.settings)
        dlg.ShowModal()
        dlg.Destroy()

    def _domanda(self, titolo, testo):
        """Una conferma con il No predefinito: vero solo per un Si' esplicito."""
        dlg = AccessibleMsgDialog(self, titolo, testo, style=wx.YES_NO, settings=self.settings, no_predefinito=True)
        risposta = dlg.ShowModal()
        dlg.Destroy()
        return risposta == wx.ID_YES

    # Gli eventi.

    def on_giocatore_scelto(self, event):
        self._aggiorna_avversari()
        event.Skip()

    def on_avversario_scelto(self, event):
        self._aggiorna_bianco()
        event.Skip()

    def on_coppia_scelta(self, event):
        self._aggiorna_inverti()
        event.Skip()

    def on_tasto_liberi(self, event):
        """INVIO sul giocatore scelto porta alla lista Avversario."""
        if event.GetKeyCode() in TASTI_INVIO and self._avversari:
            self.lista_avversari.SetFocus()
            return
        event.Skip()

    def on_tasto_avversari(self, event):
        """INVIO sull'avversario aggiunge la coppia."""
        if event.GetKeyCode() in TASTI_INVIO:
            self.on_aggiungi(None)
            return
        event.Skip()

    def on_tasto_coppie(self, event):
        """CANC toglie la coppia."""
        if event.GetKeyCode() in TASTI_CANC:
            self.on_togli(None)
            return
        event.Skip()

    def on_aggiungi(self, event):
        """Aggiunge la coppia del giocatore scelto con l'avversario, con il
        bianco a chi dice la scelta Bianco a. Il fuoco torna sulla lista dei
        giocatori da abbinare, o, quando sono finiti, sulla conferma."""
        scelta = self._scelta_corrente()
        if scelta is None:
            play_sound("errore")
            return
        scelto, avversario = scelta
        if avversario is None:
            coppia = (scelto, None)
        else:
            indice = self.scelta_bianco.GetSelection()
            bianco = self._candidati_bianco[indice] if indice != wx.NOT_FOUND else colore_suggerito(self.torneo, scelto, avversario)[0]
            coppia = (bianco, avversario if bianco == scelto else scelto)
        indice_libero = self.lista_liberi.GetSelection()
        self.coppie.append(coppia)
        self._suona_coppie([coppia], "coppia_aggiunta", "coppia_avvertimento")
        self._aggiorna(indice_libero=indice_libero, indice_coppia=ordina_coppie(self.torneo, self.coppie).index(coppia))
        if self._liberi:
            self.lista_liberi.SetFocus()
        elif self.btn_conferma.IsEnabled():
            self.btn_conferma.SetFocus()
        else:
            self.lista_coppie.SetFocus()

    def on_togli(self, event):
        """Toglie la coppia scelta: i suoi giocatori tornano da abbinare."""
        indice = self.lista_coppie.GetSelection()
        if indice == wx.NOT_FOUND or indice >= len(self.coppie):
            play_sound("errore")
            return
        del self.coppie[indice]
        play_sound("coppia_tolta")
        self._aggiorna(indice_coppia=indice)
        if self.coppie:
            self.lista_coppie.SetFocus()
        else:
            self.lista_liberi.SetFocus()

    def on_inverti(self, event):
        """Scambia i colori della coppia scelta; il riposo non ne ha."""
        indice = self.lista_coppie.GetSelection()
        if indice == wx.NOT_FOUND or indice >= len(self.coppie) or self.coppie[indice][1] is None:
            play_sound("errore")
            return
        bianco, nero = self.coppie[indice]
        self.coppie[indice] = (nero, bianco)
        self._suona_coppie([self.coppie[indice]], "coppia_invertita", "coppia_invertita_avvertimento")
        self._aggiorna(indice_coppia=indice)
        self.lista_coppie.SetFocus()

    def on_proposta(self, event):
        """Rimette le coppie della proposta di Tornello, dopo una conferma se
        ce ne sono altre gia' composte."""
        proposta = proposta_abbinamento(self.torneo)
        if proposta is None:
            play_sound("errore")
            self._messaggio(
                _("Proposta non disponibile"),
                _("Con piu' di {numero} giocatori attivi Tornello non propone le coppie: componile a mano, giocatore per giocatore.").format(numero=MASSIMO_PER_LA_PROPOSTA),
            )
            return
        if self.coppie and self.coppie != proposta:
            testo = _("Le coppie composte fin qui lasciano il posto a quelle proposte da Tornello. Continuare? Il pulsante predefinito e' No.")
            if not self._domanda(_("Proposta automatica"), testo):
                return
        self.coppie = list(proposta)
        self._suona_coppie(self.coppie, "proposta_coppie", "proposta_coppie_avvertimento")
        self._aggiorna()
        self.lista_coppie.SetFocus()

    def on_conferma(self, event):
        """Controlla il turno, mostra il riepilogo degli avvertimenti e, con
        un Si', chiude la finestra lasciando le coppie in
        coppie_confermate."""
        errori, _avvertimenti = valida_turno_manuale(self.torneo, self.coppie)
        if errori:
            play_sound("errore")
            self._messaggio(_("Turno incompleto"), "\n".join(errori))
            return
        righe = righe_della_conferma(self.torneo, self.coppie, self.turno)
        if not self._domanda(_("Conferma del turno composto a mano"), "\n".join(righe)):
            return
        self.coppie_confermate = list(self.coppie)
        self.EndModal(wx.ID_OK)

    def on_annulla(self, event):
        """Chiude senza registrare niente: il torneo resta com'era."""
        play_sound("cancellato")
        self.EndModal(wx.ID_CANCEL)
