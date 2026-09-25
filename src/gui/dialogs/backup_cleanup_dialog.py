"""La finestra Copie di sicurezza. Issue 39, seconda parte.

Fino alla 10.8.12 era la finestra Pulizia Backup: una lista di nomi di file
da mandare nel cestino. Dalla 10.9.0 legge il contenuto delle copie e dice
di ognuna il momento a parole, il contenuto in breve e l'eta'; dalla 10.10.0
ripristina un torneo o il database dei giocatori, dopo il confronto con lo
stato attuale; dalla 10.11.0 propone la regola di conservazione. Il lavoro
lo fa copie_di_sicurezza.py, che non usa wx: qui ci sono i controlli, le
conferme e i suoni.
Il modulo e la classe hanno tenuto il nome di prima: li usano il menu, la
domanda dell'avvio e le prove. delete_file_to_trash e calculate_age si
importano ancora da qui, anche se ora stanno in utils e in
copie_di_sicurezza.
"""

import builtins
import os
from datetime import datetime, timedelta

import wx
from GBwx import STILE_ADATTABILE, adatta_finestra, area_utile, pannello_scorrevole

from copie_di_sicurezza import calcola_eta as calculate_age
from copie_di_sicurezza import (
    contenuto_breve,
    copie_da_scartare,
    dettagli_della_copia,
    elenca_copie,
    leggi_copia,
    momento_in_parole,
    percorsi_del_programma,
    prepara_ripristino,
    raggruppa_per_origine,
    righe_della_conservazione,
    ripristina,
    stessa_edizione,
)
from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog
from gui.settings import apply_visual_settings
from utils import (
    delete_file_to_trash,
    dentro_la_cartella,
    play_sound,
    rimuovi_cartelle_vuote,
    sanitize_filename,
)

_ = getattr(builtins, "_", lambda s: s)


def _limite_dei_diciotto_mesi(oggi):
    """La data prima della quale una copia ha piu' di 18 mesi. Senza
    dateutil valgono 548 giorni."""
    try:
        from dateutil.relativedelta import relativedelta
    except ImportError:
        return oggi - timedelta(days=548)
    return oggi - relativedelta(months=18)


class BackupCleanupDialog(wx.Dialog):
    """La finestra Copie di sicurezza.

    Dall'alto: la scelta dell'origine, cioe' tutte le copie oppure quelle di
    un torneo o del database; la lista, dalla copia piu' vecchia alla piu'
    recente, con data e ora, momento, contenuto breve ed eta'; i dettagli
    della copia con il fuoco, in sola lettura, a righe corte per la barra
    braille; il riepilogo della cartella; i pulsanti Ripristina, Confronta
    con lo stato attuale, Elimina selezionati, Applica conservazione e
    Chiudi. La lista accetta la selezione multipla, come la pulizia di prima:
    Canc, Ctrl+A, shift con le frecce, con Inizio e con Fine.
    torneo_aperto e' il file del torneo aperto nella finestra principale, da
    cui si sceglie l'origine iniziale; seleziona, un elenco di copie da
    trovare gia' selezionate; dopo_il_ripristino, la funzione che la finestra
    principale passa per ricaricare subito il torneo ripristinato. percorsi,
    se c'e', prende il posto di quelli del programma.
    """

    def __init__(self, parent, settings, torneo_aperto=None, seleziona=None, dopo_il_ripristino=None, percorsi=None):
        super().__init__(parent, title=_("Copie di sicurezza"), style=STILE_ADATTABILE)
        self.settings = settings
        self.percorsi = percorsi or percorsi_del_programma()
        self.backup_dir = self.percorsi.backup
        self.torneo_aperto = torneo_aperto
        self.dopo_il_ripristino = dopo_il_ripristino
        self.copie = []
        self.visibili = []
        self.old_files_info = []
        self._chiavi_origine = [None]

        self._init_ui()
        self.apply_theme()
        self.populate_list(origine=self._origine_iniziale(seleziona), seleziona=seleziona)
        # La misura la da' il contenuto, dentro lo schermo, e 800 per 550
        # resta come minimo (issue 49). Si misura dopo il tema, che cambia i
        # caratteri, e dopo aver riempito la lista, che da' la larghezza alle
        # colonne. La lista ha una misura minima data per intero: quella che
        # calcolerebbe da se' comprende tutte le righe, e con molte copie la
        # finestra arriverebbe al fondo dello schermo.
        self._misura_la_lista()
        adatta_finestra(self, self.pannello, (800, 550))
        if self.list_ctrl.GetFocusedItem() >= 0:
            self.list_ctrl.EnsureVisible(self.list_ctrl.GetFocusedItem())
        destinazione = self.list_ctrl if self.list_ctrl.GetItemCount() else self.scelta_origine
        wx.CallAfter(lambda: self and destinazione.SetFocus())

    def _init_ui(self):
        panel = self.pannello = pannello_scorrevole(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Ogni controllo ha davanti la sua etichetta, e da li' lo screen
        # reader ne prende il nome; nessuno sta in un riquadro.
        self.lbl_origine = wx.StaticText(panel, label=_("&Origine delle copie:"))
        vbox.Add(self.lbl_origine, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        self.scelta_origine = wx.Choice(panel)
        self.scelta_origine.Bind(wx.EVT_CHOICE, self.on_origine)
        vbox.Add(self.scelta_origine, 0, wx.EXPAND | wx.ALL, 10)

        self.lbl_list = wx.StaticText(panel, label=_("E&lenco delle copie, dalla più vecchia alla più recente:"))
        vbox.Add(self.lbl_list, 0, wx.LEFT | wx.RIGHT, 10)
        # Senza LC_SINGLE_SEL la lista accetta la selezione multipla. Le
        # colonne prendono la larghezza dal loro testo ogni volta che la
        # lista si riempie, in _riempi_lista.
        self.list_ctrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_HRULES | wx.LC_VRULES)
        self._intestazioni = (_("Data e ora"), _("Momento"), _("Contenuto"), _("Età"))
        for colonna, intestazione in enumerate(self._intestazioni):
            self.list_ctrl.InsertColumn(colonna, intestazione)
        self.list_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_list_key_down)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.on_copia_col_fuoco)
        vbox.Add(self.list_ctrl, 2, wx.EXPAND | wx.ALL, 10)

        self.lbl_dettagli = wx.StaticText(panel, label=_("&Dettagli della copia:"))
        vbox.Add(self.lbl_dettagli, 0, wx.LEFT | wx.RIGHT, 10)
        self.dettagli = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        vbox.Add(self.dettagli, 1, wx.EXPAND | wx.ALL, 10)

        self.lbl_stats = wx.StaticText(panel, label=_("Riepilo&go della cartella backup:"))
        vbox.Add(self.lbl_stats, 0, wx.LEFT | wx.RIGHT, 10)
        self.stats_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        vbox.Add(self.stats_text, 0, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_ripristina = wx.Button(panel, label=_("&Ripristina"))
        self.btn_confronta = wx.Button(panel, label=_("&Confronta con lo stato attuale"))
        self.btn_delete_selected = wx.Button(panel, label=_("&Elimina selezionati"))
        self.btn_conservazione = wx.Button(panel, label=_("&Applica conservazione"))
        self.btn_close = wx.Button(panel, wx.ID_CANCEL, label=_("Chiudi"))
        self.btn_ripristina.Bind(wx.EVT_BUTTON, self.on_ripristina)
        self.btn_confronta.Bind(wx.EVT_BUTTON, self.on_confronta)
        self.btn_delete_selected.Bind(wx.EVT_BUTTON, self.on_delete_selected)
        self.btn_conservazione.Bind(wx.EVT_BUTTON, self.on_conservazione)
        self.btn_close.Bind(wx.EVT_BUTTON, self.on_close)
        for pulsante in self._pulsanti():
            btn_sizer.Add(pulsante, 0, wx.RIGHT, 5)
        vbox.Add(btn_sizer, 0, wx.ALL, 10)
        panel.SetSizer(vbox)

    def _pulsanti(self):
        return (self.btn_ripristina, self.btn_confronta, self.btn_delete_selected, self.btn_conservazione, self.btn_close)

    def apply_theme(self):
        """Applica le impostazioni visive del tema dell'applicazione."""
        controlli = (
            self,
            self.lbl_origine,
            self.scelta_origine,
            self.lbl_list,
            self.list_ctrl,
            self.lbl_dettagli,
            self.dettagli,
            self.lbl_stats,
            self.stats_text,
            *self._pulsanti(),
        )
        for controllo in controlli:
            apply_visual_settings(controllo, self.settings)
        # L'altezza dei due campi di testo si conta in righe del carattere
        # che il tema ha appena dato, non in pixel: con i caratteri grandi
        # le righe del riepilogo restano tutte visibili.
        for campo, righe in ((self.dettagli, 8), (self.stats_text, 5)):
            campo.SetMinSize(wx.Size(-1, campo.GetCharHeight() * righe))

    def _origine_iniziale(self, seleziona):
        """L'origine con cui la finestra si apre: tutte le copie se ce ne
        sono da trovare selezionate, altrimenti quelle del torneo aperto, se
        ne ha."""
        if seleziona or not self.torneo_aperto:
            return None
        tipo, dati, _errore = leggi_copia(self.torneo_aperto)
        if tipo == "torneo" and dati.get("name"):
            return ("torneo", sanitize_filename(dati["name"]))
        return None

    def load_backup_files(self):
        """Legge tutte le copie della cartella, con il loro contenuto, e
        raccoglie quelle nate piu' di 18 mesi fa. Le cartelle dell'anno e del
        mese rimaste vuote si tolgono prima."""
        rimuovi_cartelle_vuote(self.backup_dir)
        self.copie = elenca_copie(self.backup_dir, os.path.basename(self.percorsi.database))
        limite = _limite_dei_diciotto_mesi(datetime.now())
        self.old_files_info = [c for c in self.copie if c.data < limite]

    def _origine_scelta(self):
        indice = self.scelta_origine.GetSelection()
        if 0 <= indice < len(self._chiavi_origine):
            return self._chiavi_origine[indice]
        return None

    def populate_list(self, origine="attuale", seleziona=None):
        """Rilegge la cartella e riempie scelta dell'origine, lista e
        riepilogo. origine e' la chiave da mostrare; "attuale" tiene quella
        scelta. seleziona e' un elenco di percorsi da selezionare; senza, si
        seleziona la copia piu' recente."""
        if origine == "attuale":
            origine = self._origine_scelta()
        self.load_backup_files()
        gruppi = raggruppa_per_origine(self.copie)
        self._chiavi_origine = [None] + [chiave for chiave, _nome, _elenco in gruppi]
        voci = [_("Tutte ({numero})").format(numero=len(self.copie))]
        voci += [f"{nome} ({len(elenco)})" for _chiave, nome, elenco in gruppi]
        self.scelta_origine.Set(voci)
        indice = self._chiavi_origine.index(origine) if origine in self._chiavi_origine else 0
        self.scelta_origine.SetSelection(indice)
        self._riempi_lista(seleziona)

    def _testi_delle_righe(self, copie, con_origine):
        """I testi delle quattro colonne per ogni copia: data e ora, momento,
        contenuto breve, con il nome dell'origine se con_origine, ed eta'."""
        oggi = datetime.now()
        testi = []
        for copia in copie:
            mesi, giorni = calculate_age(copia.data, oggi)
            testi.append(
                (
                    copia.data.strftime("%Y-%m-%d %H:%M:%S"),
                    momento_in_parole(copia.contesto),
                    contenuto_breve(copia, con_origine=con_origine),
                    _("{m} mesi, {d} giorni").format(m=mesi, d=giorni),
                )
            )
        return testi

    def _larghezze_delle_colonne(self, testi):
        """La larghezza che serve a ogni colonna per mostrare per intero la
        sua intestazione e la sua voce piu' lunga, misurate con il carattere
        della lista, che il tema puo' aver ingrandito, piu' un margine di tre
        caratteri. Con le larghezze fisse di prima, pensate per il carattere
        piccolo, i caratteri al 150 per cento tagliavano i testi di tutte le
        colonne."""
        margine = self.list_ctrl.GetCharWidth() * 3
        return [
            max(self.list_ctrl.GetTextExtent(testo).width for testo in (intestazione, *(riga[colonna] for riga in testi)))
            + margine
            for colonna, intestazione in enumerate(self._intestazioni)
        ]

    def _misura_la_lista(self):
        """La misura minima della lista: larga quanto le colonne con tutte le
        copie, che e' la vista piu' larga perche' il contenuto comincia con
        l'origine, ma non oltre lo schermo; alta otto righe del suo
        carattere. Oltre, le colonne scorrono con la barra orizzontale della
        lista."""
        larghezze = self._larghezze_delle_colonne(self._testi_delle_righe(self.copie, True))
        larghezza = sum(larghezze) + wx.SystemSettings.GetMetric(wx.SYS_VSCROLL_X, self.list_ctrl) + self.list_ctrl.GetCharWidth() * 2
        massima = area_utile(self).width - self.FromDIP(80)
        self.list_ctrl.SetMinSize(wx.Size(max(1, min(larghezza, massima)), self.list_ctrl.GetCharHeight() * 8))

    def _riempi_lista(self, seleziona=None):
        origine = self._origine_scelta()
        self.visibili = [c for c in self.copie if origine is None or c.chiave == origine]
        testi = self._testi_delle_righe(self.visibili, origine is None)
        self.list_ctrl.DeleteAllItems()
        for indice, riga in enumerate(testi):
            self.list_ctrl.InsertItem(indice, riga[0])
            for colonna in (1, 2, 3):
                self.list_ctrl.SetItem(indice, colonna, riga[colonna])
        for colonna, larghezza in enumerate(self._larghezze_delle_colonne(testi)):
            self.list_ctrl.SetColumnWidth(colonna, larghezza)
        self._aggiorna_riepilogo()
        if not self.visibili:
            self.dettagli.SetValue(_("Nessuna copia di sicurezza."))
            return
        scelti = {os.path.normcase(os.path.abspath(p)) for p in seleziona or ()}
        indici = [i for i, c in enumerate(self.visibili) if os.path.normcase(os.path.abspath(c.percorso)) in scelti]
        if not indici:
            indici = [len(self.visibili) - 1]
        for indice in indici:
            self.list_ctrl.Select(indice, True)
        self.list_ctrl.Focus(indici[0])
        self.list_ctrl.EnsureVisible(indici[0])
        self._mostra_dettagli(indici[0])

    def _aggiorna_riepilogo(self):
        dimensione = sum(c.dimensione for c in self.copie) / (1024 * 1024)
        righe = [
            _("Copie nella cartella: {numero}").format(numero=len(self.copie)),
            _("Spazio occupato: {mb:.1f} MB").format(mb=dimensione),
            _("Nate più di 18 mesi fa: {numero}").format(numero=len(self.old_files_info)),
            _("Copie di questa origine: {numero}").format(numero=len(self.visibili)),
        ]
        self.stats_text.SetValue("\n".join(righe))

    def _mostra_dettagli(self, indice):
        if 0 <= indice < len(self.visibili):
            self.dettagli.SetValue("\n".join(dettagli_della_copia(self.visibili[indice], datetime.now())))
            self.dettagli.SetInsertionPoint(0)

    def on_origine(self, event):
        self._riempi_lista()

    def on_copia_col_fuoco(self, event):
        self._mostra_dettagli(event.GetIndex())
        event.Skip()

    def indici_selezionati(self):
        """Indici di tutte le righe selezionate, non solo della prima."""
        indici = []
        indice = self.list_ctrl.GetNextItem(-1, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
        while indice != -1:
            indici.append(indice)
            indice = self.list_ctrl.GetNextItem(indice, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED)
        return indici

    def seleziona_tutti(self):
        for indice in range(self.list_ctrl.GetItemCount()):
            self.list_ctrl.Select(indice, True)

    def estendi_selezione_al_bordo(self, verso_inizio):
        """Seleziona dalla riga con il fuoco fino alla prima o all'ultima,
        cioe' quello che fanno shift con Inizio e shift con Fine."""
        quante = self.list_ctrl.GetItemCount()
        if not quante:
            return
        partenza = self.list_ctrl.GetFocusedItem()
        if partenza == -1:
            partenza = 0
        arrivo = 0 if verso_inizio else quante - 1
        primo, ultimo = sorted((partenza, arrivo))
        for indice in range(primo, ultimo + 1):
            self.list_ctrl.Select(indice, True)
        self.list_ctrl.Focus(arrivo)
        self.list_ctrl.EnsureVisible(arrivo)

    def _riporta_il_fuoco(self, indice):
        """Dopo una cancellazione il fuoco non deve restare nel vuoto: si
        posa sulla riga che ha preso il posto di quella eliminata."""
        quante = self.list_ctrl.GetItemCount()
        if not quante:
            self.list_ctrl.SetFocus()
            return
        for vecchio in self.indici_selezionati():
            self.list_ctrl.Select(vecchio, False)
        destinazione = min(indice, quante - 1)
        self.list_ctrl.Select(destinazione, True)
        self.list_ctrl.Focus(destinazione)
        self.list_ctrl.EnsureVisible(destinazione)
        self._mostra_dettagli(destinazione)
        self.list_ctrl.SetFocus()

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

    def _copia_sola(self):
        """La copia selezionata, se ce n'e' una sola; altrimenti lo dice e
        risponde None."""
        indici = self.indici_selezionati()
        if len(indici) == 1 and indici[0] < len(self.visibili):
            return self.visibili[indici[0]]
        play_sound("errore")
        self._messaggio(_("Una copia sola"), _("Seleziona nell'elenco una copia sola, quella da ripristinare o da confrontare."))
        return None

    def _destinazione_per(self, copia):
        """Il file da sostituire con un torneo ripristinato: quello del
        torneo aperto, se e' la stessa edizione e non e' concluso, cosi' anche
        un torneo aperto da un'altra cartella torna al suo posto; altrimenti
        None, e il file e' quello della cartella del programma."""
        aperto = self.torneo_aperto
        if copia.tipo != "torneo" or not aperto or not os.path.isfile(aperto):
            return None
        if dentro_la_cartella(aperto, self.percorsi.archivio):
            return None
        tipo, dati, _errore = leggi_copia(aperto)
        _tipo, dati_copia, _errore = leggi_copia(copia.percorso)
        if tipo != "torneo" or dati.get("concluded") or not isinstance(dati_copia, dict):
            return None
        if dati.get("name") == dati_copia.get("name") and stessa_edizione(dati, dati_copia):
            return aperto
        return None

    def _nel_cestino(self, percorso):
        """Il cestino di Windows, con questa finestra come proprietaria della
        domanda che Windows fa prima di cancellare per sempre un file che il
        cestino non puo' prendere: cosi' la domanda prende il fuoco, invece
        di restare nascosta dietro la finestra delle copie."""
        return delete_file_to_trash(percorso, finestra=self.GetHandle())

    def on_confronta(self, event):
        copia = self._copia_sola()
        if copia is None:
            return
        piano = prepara_ripristino(copia.percorso, self.percorsi, self._destinazione_per(copia))
        testo = piano.rifiuto or "\n".join([*piano.avvertenze, _("File: {nome}").format(nome=copia.nome), *piano.righe])
        self._messaggio(_("Confronto con lo stato attuale"), testo)

    def on_ripristina(self, event):
        copia = self._copia_sola()
        if copia is None:
            return
        destinazione = self._destinazione_per(copia)
        piano = prepara_ripristino(copia.percorso, self.percorsi, destinazione)
        if piano.rifiuto:
            play_sound("errore")
            self._messaggio(_("Ripristino non possibile"), piano.rifiuto)
            return
        # Le avvertenze vengono prima di tutto, anche della domanda; il nome
        # del file dice sempre da dove viene la copia.
        domanda = [
            *piano.avvertenze,
            _("Ripristinare la copia {momento}, del {data}?").format(
                momento=momento_in_parole(copia.contesto), data=copia.data.strftime("%Y-%m-%d %H:%M:%S")
            ),
            _("File: {nome}").format(nome=copia.nome),
            *piano.righe,
            _("Confermi il ripristino? Il pulsante predefinito è No."),
        ]
        if not self._domanda(_("Conferma ripristino"), "\n".join(domanda)):
            return
        esito = ripristina(copia.percorso, self.percorsi, destinazione, cestino=self._nel_cestino)
        if esito.riuscito:
            play_sound("ripristino")
        else:
            play_sound("errore")
        # Prima di tutto la finestra principale: se il torneo ripristinato e'
        # quello aperto, la memoria va riallineata subito, o il primo
        # salvataggio riscriverebbe sul disco lo stato di prima.
        if self.dopo_il_ripristino:
            self.dopo_il_ripristino(esito)
        titolo = _("Ripristino riuscito") if esito.riuscito else _("Ripristino non riuscito")
        self._messaggio(titolo, "\n".join(esito.righe))
        self.populate_list(seleziona=[copia.percorso])
        self.list_ctrl.SetFocus()

    def on_delete_selected(self, event):
        """Manda nel cestino tutte le copie selezionate."""
        indici = self.indici_selezionati()
        if not indici:
            self._messaggio(_("Nessuna Selezione"), _("Nessun file selezionato. Seleziona un file dall'elenco per poterlo eliminare."))
            return
        scelte = [self.visibili[i] for i in indici if i < len(self.visibili)]
        if len(scelte) == 1:
            msg = _("Sei sicuro di voler spostare nel cestino il file di backup '{name}'?").format(name=scelte[0].nome)
        else:
            msg = _("Sei sicuro di voler spostare nel cestino i {count} file di backup selezionati?").format(count=len(scelte))
        dlg = AccessibleMsgDialog(self, _("Conferma Eliminazione"), msg, style=wx.YES_NO)
        conferma = dlg.ShowModal()
        dlg.Destroy()
        if conferma != wx.ID_YES:
            return
        non_riusciti = [c.nome for c in scelte if not self._nel_cestino(c.percorso)]
        play_sound("cancellato")
        self.populate_list()
        self._riporta_il_fuoco(indici[0])
        if non_riusciti:
            self._messaggio(_("Errore"), _("Alcuni file non sono stati eliminati:\n{files}").format(files=", ".join(non_riusciti)))

    def on_conservazione(self, event):
        """Mostra l'anteprima della regola di conservazione e, con un Si',
        manda nel cestino le copie in piu'. Mai da sola (decisione di
        Gabriele)."""
        scarto = copie_da_scartare(self.copie)
        righe = righe_della_conservazione(scarto)
        if not scarto:
            self._messaggio(_("Conservazione"), "\n".join(righe))
            return
        righe.append(_("Le mando nel cestino? Il pulsante predefinito è No."))
        if not self._domanda(_("Conservazione"), "\n".join(righe)):
            return
        non_riusciti = [c.nome for c in scarto if not self._nel_cestino(c.percorso)]
        play_sound("cancellato")
        self.populate_list()
        self.list_ctrl.SetFocus()
        if non_riusciti:
            self._messaggio(_("Errore"), _("Alcuni file non sono stati eliminati:\n{files}").format(files=", ".join(non_riusciti)))

    def on_close(self, event):
        """Chiude la finestra di dialogo."""
        play_sound("conferma")
        self.EndModal(wx.ID_CANCEL)

    def on_list_key_down(self, event):
        """Canc elimina la selezione; Ctrl+A prende tutto; shift con Inizio o
        Fine estende la selezione fino al bordo dell'elenco. Le frecce con
        shift le gestisce gia' la lista."""
        key_code = event.GetKeyCode()
        if key_code in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            self.on_delete_selected(None)
            return
        if event.ControlDown() and key_code in (ord("A"), ord("a")):
            self.seleziona_tutti()
            return
        if event.ShiftDown() and key_code in (wx.WXK_HOME, wx.WXK_END):
            self.estendi_selezione_al_bordo(key_code == wx.WXK_HOME)
            return
        event.Skip()
