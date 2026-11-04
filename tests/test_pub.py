"""Le voci Entra al PUB e Chiedi aiuto al PUB del menu Aiuto. Issue 70, dalla
10.18.0.

Le due voci preparano una mail al PUB, il gruppo di supporto, con la
finestra_mail di GBwx; indirizzi, informazioni sul computer e composizione
della mail vengono da GBUtils, issue 57, e Tornello ci mette le parole,
in gui/pub.py, e le righe in piu': la versione di bbpPairings e la lingua
dell'interfaccia. Niente si apre davvero: la finestra della mail e' una finta
che annota cio' che riceve, oppure quella vera, mai mostrata, con ShowModal
che preme i pulsanti da se'; il programma di posta, os.startfile e gli
appunti sono sostituiti, e il guardiano di conftest fa fallire chi li
toccasse davvero. Dalla 10.19.10 le due voci hanno un suono: play_sound e'
una finta che annota gli eventi, e niente suona.
"""

import pytest

INFORMAZIONI = [
    ("windows", "Windows 11 Pro"),
    ("windows_versione", "25H2"),
    ("windows_build", "26300.7171"),
    ("architettura", "x64"),
    ("processore", "AMD Ryzen 9 7950X 16-Core Processor"),
    ("nuclei", 32),
    ("memoria_totale", "31,9 GB"),
    ("memoria_libera", "18,2 GB"),
    ("lingua", "it-IT"),
    ("screen_reader", "NVDA 2026.3.1"),
    ("schermo", "2560x1440"),
    ("scala", "150%"),
    ("python", "3.14.5 64 bit"),
    ("compilato", False),
]
BBP = "using BBP Pairings (v6.0.0), a Swiss-system chess tournament engine created by Bierema Boyz Programming."


@pytest.fixture
def suoni(monkeypatch):
    """play_sound sostituita da una finta che annota gli eventi: niente
    suona."""
    import utils

    registro = []
    monkeypatch.setattr(utils, "play_sound", lambda evento, *a, **k: registro.append(evento) or True)
    return registro


@pytest.fixture
def principale(app_grafica, suoni, monkeypatch):
    """La finestra principale, mai mostrata, senza i controlli dell'avvio e
    senza suoni: i suoi suoni li annota suoni, che riparte vuoto dopo la
    creazione della finestra."""
    import gui.main_frame as mf
    from gui.settings import DEFAULT_SETTINGS

    for nome in ("_check_fide_db_on_startup", "_check_backup_on_startup", "_scan_and_load_initial_tournament", "_check_updates_async"):
        monkeypatch.setattr(mf.MainFrame, nome, lambda self: None)
    monkeypatch.setattr(mf.MainFrame, "Maximize", lambda self, *a: None)
    finestra = mf.MainFrame(None, "Tornello", dict(DEFAULT_SETTINGS))
    finestra._timer_pie_di_pagina.Stop()
    suoni.clear()
    yield finestra
    finestra.Destroy()


@pytest.fixture
def finestre_della_mail(suoni, monkeypatch):
    """finestra_mail di GBwx sostituita da una finta che annota gli argomenti,
    e i suoni gia' suonati quando la finestra si apre, e risponde con l'esito
    di registro["esito"], vero se non detto."""
    import GBwx

    registro = {"chiamate": [], "esito": True}

    def finta(genitore, titolo, destinatario, oggetto, corpo, spiegazione, passi, pulsanti, senza_posta="", **opzioni):
        registro["chiamate"].append(
            {
                "genitore": genitore,
                "titolo": titolo,
                "destinatario": destinatario,
                "oggetto": oggetto,
                "corpo": corpo,
                "spiegazione": spiegazione,
                "passi": passi,
                "pulsanti": pulsanti,
                "senza_posta": senza_posta,
                "suoni_prima": list(suoni),
            }
        )
        return registro["esito"]

    monkeypatch.setattr(GBwx, "finestra_mail", finta)
    return registro


def _dal_menu(principale, voce):
    import wx

    evento = wx.CommandEvent(wx.wxEVT_MENU, voce.GetId())
    evento.SetEventObject(principale)
    assert principale.GetEventHandler().ProcessEvent(evento)


class TestMenuAiuto:
    """Le due voci vengono dopo Offrimi un caffe', dietro un separatore,
    ciascuna con la sua lettera: E per Entra al PUB, A per Chiedi aiuto, che
    non puo' avere la C di Changelog."""

    def test_le_voci_e_il_separatore(self, principale):
        menu = principale.item_credits.GetMenu()
        voci = [None if v.IsSeparator() else v.GetItemLabel() for v in menu.GetMenuItems()]
        assert voci == [
            "&Guida Accessibile\tF1",
            "&Changelog\tF2",
            "C&rediti\tF3",
            "&Offrimi un caffè...",
            None,
            "&Entra al PUB (gruppo di supporto)...",
            "Chiedi &aiuto al PUB...",
        ]
        lettere = [v[v.index("&") + 1].lower() for v in voci if v is not None]
        assert lettere == ["g", "c", "r", "o", "e", "a"]

    def test_entra_al_pub_dal_menu(self, principale, finestre_della_mail):
        from GBUtils import PUB_ISCRIZIONE

        from gui import pub

        _dal_menu(principale, principale.item_entra_al_pub)

        (chiamata,) = finestre_della_mail["chiamate"]
        assert chiamata["genitore"] is principale
        assert chiamata["destinatario"] == PUB_ISCRIZIONE
        assert chiamata["titolo"] == pub.mail_d_iscrizione()["titolo"]
        assert chiamata["pulsanti"] == pub.pulsanti()
        assert chiamata["senza_posta"] == pub.senza_posta()
        assert principale.last_status_msg == principale_testo("Entra al PUB: la mail d'iscrizione è pronta, spediscila tu.")

    def test_entra_al_pub_chiuso_prima(self, principale, finestre_della_mail):
        finestre_della_mail["esito"] = False

        _dal_menu(principale, principale.item_entra_al_pub)

        assert len(finestre_della_mail["chiamate"]) == 1
        assert principale.last_status_msg == principale_testo("Entra al PUB: finestra chiusa, nessuna mail preparata.")

    def test_chiedi_aiuto_dal_menu(self, principale, finestre_della_mail, monkeypatch):
        """La lingua e' quella in cui Tornello parla, e decide il punto
        decimale che informazioni_di_sistema usa per le memorie."""
        import GBUtils
        from GBUtils import PUB_GRUPPO

        import config
        from version import __version__

        separatori = []
        monkeypatch.setattr(GBUtils, "informazioni_di_sistema", lambda separatore=".": separatori.append(separatore) or INFORMAZIONI)
        monkeypatch.setattr(config, "lingua_rilevata", "en")

        _dal_menu(principale, principale.item_chiedi_aiuto_al_pub)

        (chiamata,) = finestre_della_mail["chiamate"]
        assert separatori == ["."]
        assert chiamata["destinatario"] == PUB_GRUPPO
        assert chiamata["oggetto"] == principale_testo("Chiedo per Tornello {versione}").format(versione=__version__)
        righe = chiamata["corpo"].splitlines()
        assert principale_testo("Lingua di Tornello: {lingua}").format(lingua="en") in righe
        assert principale_testo("Motore degli abbinamenti: BBP Pairings {versione}").format(versione="6.0.0") in righe
        # Dai sorgenti, non compilato.
        assert principale_testo("Programma: Tornello {versione}, dai sorgenti").format(versione=__version__) in righe
        assert principale.last_status_msg == principale_testo("Chiedi aiuto al PUB: la mail è pronta, scrivi la domanda e spediscila tu.")

    def test_chiedi_aiuto_in_italiano_usa_la_virgola_e_chiuso_prima(self, principale, finestre_della_mail, monkeypatch):
        import GBUtils

        import config

        separatori = []
        monkeypatch.setattr(GBUtils, "informazioni_di_sistema", lambda separatore=".": separatori.append(separatore) or INFORMAZIONI)
        monkeypatch.setattr(config, "lingua_rilevata", "it")
        finestre_della_mail["esito"] = False

        _dal_menu(principale, principale.item_chiedi_aiuto_al_pub)

        assert separatori == [","]
        assert principale.last_status_msg == principale_testo("Chiedi aiuto al PUB: finestra chiusa, nessuna mail preparata.")


class TestSuoniDelPub:
    """Dalla 10.19.10 le due voci suonano appena le si sceglie, prima che si
    apra la finestra della mail, come in MeTeOra: Entra al PUB il campanello
    della porta del pub, mess_pub_entra, e Chiedi aiuto al PUB la domanda,
    mess_pub_aiuto, i preset di MESS e di MeTeOra, con la firma di Tornello
    dalla V242 di GBUtils. Fino alla 10.19.7 le voci non avevano un suono
    (decisione di Gabriele del 4 novembre 2026, issue 70)."""

    def test_entra_al_pub_suona_prima_della_finestra(self, principale, finestre_della_mail, suoni):
        _dal_menu(principale, principale.item_entra_al_pub)

        (chiamata,) = finestre_della_mail["chiamate"]
        assert chiamata["suoni_prima"] == ["pub_entra"]
        assert suoni == ["pub_entra"]

    def test_chiedi_aiuto_suona_prima_delle_informazioni_e_della_finestra(self, principale, finestre_della_mail, suoni, monkeypatch):
        """Il suono parte prima di leggere le informazioni sul computer, che
        possono chiedere un momento, come in MeTeOra."""
        import GBUtils

        letture = []
        monkeypatch.setattr(GBUtils, "informazioni_di_sistema", lambda separatore=".": letture.append(list(suoni)) or INFORMAZIONI)

        _dal_menu(principale, principale.item_chiedi_aiuto_al_pub)

        (chiamata,) = finestre_della_mail["chiamate"]
        assert letture == [["pub_aiuto"]]
        assert chiamata["suoni_prima"] == ["pub_aiuto"]
        assert suoni == ["pub_aiuto"]

    @pytest.mark.parametrize(("voce", "evento"), [("item_entra_al_pub", "pub_entra"), ("item_chiedi_aiuto_al_pub", "pub_aiuto")])
    def test_suona_una_volta_anche_con_la_finestra_chiusa_prima(self, principale, finestre_della_mail, suoni, monkeypatch, voce, evento):
        import GBUtils

        monkeypatch.setattr(GBUtils, "informazioni_di_sistema", lambda separatore=".": INFORMAZIONI)
        finestre_della_mail["esito"] = False

        _dal_menu(principale, getattr(principale, voce))

        assert suoni == [evento]

    def test_i_preset_sono_quelli_di_meteora(self):
        from utils import EVENTI

        assert EVENTI["pub_entra"] == "mess_pub_entra"
        assert EVENTI["pub_aiuto"] == "mess_pub_aiuto"

    @pytest.mark.parametrize("preset", ["mess_pub_entra", "mess_pub_aiuto"])
    def test_il_preset_ha_la_firma_di_tornello(self, preset):
        import json
        import os

        GBUtils = pytest.importorskip("GBUtils")
        percorso = os.path.join(os.path.dirname(os.path.abspath(GBUtils.__file__)), "Acu_Collection.json")
        with open(percorso, encoding="utf-8") as f:
            dati = json.load(f).get(preset)
        assert dati is not None and dati.get("score")
        firme = dati["descrizione"].split("Usato da:")[-1]
        assert "tornello" in [nome.strip(" .") for nome in firme.split(",")]


def principale_testo(testo):
    """Il testo come lo scrive la finestra, passato dalla sua traduzione."""
    from gui import main_frame

    return main_frame._(testo)


class TestParoleDelPub:
    """Le parole di gui/pub.py, senza finestre."""

    def test_iscrizione(self):
        from GBUtils import PUB_ISCRIZIONE

        from gui import pub

        mail = pub.mail_d_iscrizione()
        assert mail["destinatario"] == PUB_ISCRIZIONE
        assert mail["oggetto"] and mail["corpo"]
        # Il nome del programma di posta lo mette finestra_mail.
        assert "{programma}" in mail["spiegazione"]
        assert "Tornello" in mail["spiegazione"]
        # Il primo passo copia l'indirizzo, l'ultimo non copia niente.
        assert mail["passi"][0][1] == PUB_ISCRIZIONE
        assert mail["passi"][-1][1] is None
        assert [p[0].split(".")[0] for p in mail["passi"]] == ["Passo 1 di 2", "Passo 2 di 2"]

    def test_aiuto(self):
        from GBUtils import PUB_GRUPPO

        from gui import pub

        mail = pub.mail_d_aiuto("10.18.0", True, INFORMAZIONI, "it", BBP)
        assert mail["destinatario"] == PUB_GRUPPO
        assert mail["oggetto"] == "Chiedo per Tornello 10.18.0"
        assert mail["corpo"].splitlines() == [
            "Scrivi qui la tua domanda, al posto di questa riga.",
            "Informazioni su Tornello e sul computer di chi scrive:",
            "Programma: Tornello 10.18.0, pacchetto compilato",
            "Motore degli abbinamenti: BBP Pairings 6.0.0",
            "Lingua di Tornello: it",
            "Sistema operativo: Windows 11 Pro",
            "Versione di Windows: 25H2",
            "Build di Windows: 26300.7171",
            "Architettura: x64",
            "Processore: AMD Ryzen 9 7950X 16-Core Processor",
            "Nuclei logici: 32",
            "Memoria: 31,9 GB",
            "Memoria libera: 18,2 GB",
            "Lingua di sistema: it-IT",
            "Screen reader: NVDA 2026.3.1",
            "Schermo: 2560x1440",
            "Scala dello schermo: 150%",
            "Python: 3.14.5 64 bit",
        ]
        assert "{programma}" in mail["spiegazione"]
        assert "Chiedo per Tornello 10.18.0" in mail["spiegazione"]
        assert [p[1] for p in mail["passi"]] == [PUB_GRUPPO, "Chiedo per Tornello 10.18.0", mail["corpo"], None]
        assert [p[0].split(".")[0] for p in mail["passi"]] == [f"Passo {n} di 4" for n in range(1, 5)]

    def test_le_informazioni_che_mancano_restano_fuori(self):
        """Un valore non letto, None, non ha la sua riga; uno screen reader
        che c'e' ma non si riconosce, vero, si dice si'."""
        from gui import pub

        informazioni = [("windows", None), ("screen_reader", True), ("nuclei", 1)]
        righe = pub.mail_d_aiuto("10.18.0", False, informazioni, "it", BBP)["corpo"].splitlines()
        assert righe[2] == "Programma: Tornello 10.18.0, dai sorgenti"
        assert righe[5:] == ["Nuclei logici: 1", "Screen reader: sì"]

    @pytest.mark.parametrize(
        ("informazioni", "attesa"),
        [
            (BBP, "6.0.0"),
            ("using BBP Pairings (6.1.2), un'altra frase.", "6.1.2"),
            ("bbpPairings, versione ignota", "bbpPairings, versione ignota"),
            ("", ""),
        ],
    )
    def test_la_versione_di_bbppairings(self, informazioni, attesa):
        from gui import pub

        assert pub.versione_di_bbppairings(informazioni) == attesa

    def test_la_versione_di_bbppairings_di_version_py(self):
        from gui import pub
        from version import __bbp_info__

        versione = pub.versione_di_bbppairings(__bbp_info__)
        assert versione and versione[0].isdigit()

    @pytest.mark.parametrize(("lingua", "separatore"), [("en", "."), ("en_US", "."), ("it", ","), ("es", ","), ("fr", ","), ("pt", ","), (None, ",")])
    def test_il_separatore_decimale(self, lingua, separatore):
        from gui import pub

        assert pub.separatore_decimale(lingua) == separatore

    def test_i_pulsanti_di_finestra_mail(self):
        """Le lettere sono diverse fra i pulsanti che si vedono insieme: Apri,
        Passo per passo e Chiudi nella spiegazione, OK e Annulla nei passi,
        dove Chiudi diventa Annulla e Apri sparisce."""
        from gui import pub

        etichette = pub.pulsanti()
        assert set(etichette) == {"apri", "passi", "ok", "chiudi", "annulla"}
        for insieme in (("apri", "passi", "chiudi"), ("ok", "annulla")):
            lettere = [etichette[chiave][etichette[chiave].index("&") + 1].lower() for chiave in insieme]
            assert len(set(lettere)) == len(lettere), insieme

    def test_l_indirizzo_mailto_resta_sotto_il_limite(self):
        """apri_mail rinuncia oltre i duemila caratteri, perche' certi programmi
        di posta tagliano l'indirizzo: con tutte le informazioni la mail
        d'aiuto ci deve stare, o si finirebbe sempre nei passi."""
        from GBUtils import indirizzo_mailto

        from gui import pub

        mail = pub.mail_d_aiuto("10.18.0", True, INFORMAZIONI, "it", BBP)
        assert len(indirizzo_mailto(mail["destinatario"], mail["oggetto"], mail["corpo"])) < 2000

    def test_nessun_separatore_grafico(self):
        from gui import pub

        testi = [pub.senza_posta(), *pub.pulsanti().values(), *pub.etichette().values()]
        for mail in (pub.mail_d_iscrizione(), pub.mail_d_aiuto("10.18.0", True, INFORMAZIONI, "it", BBP)):
            testi += [mail["titolo"], mail["oggetto"], mail["corpo"], mail["spiegazione"], *(p[0] for p in mail["passi"])]
        for testo in testi:
            for fila in ("===", "---", "___"):
                assert fila not in testo, testo


class TestFinestraVeraDellaMail:
    """La finestra_mail vera di GBwx con le parole di Tornello, mai mostrata:
    ShowModal preme da se' i pulsanti, come farebbe l'utente. Il programma di
    posta, os.startfile e gli appunti sono sostituiti."""

    @pytest.fixture
    def finestra(self, app_grafica, monkeypatch):
        import os

        import GBUtils
        import GBwx

        registro = {"appunti": [], "aperti": [], "posta": None, "testi": []}
        monkeypatch.setattr(GBUtils, "programma_di_posta", lambda: registro["posta"])
        monkeypatch.setattr(GBwx, "_negli_appunti", lambda testo: registro["appunti"].append(testo) or True)
        monkeypatch.setattr(GBwx._FinestraMail, "Maximize", lambda self, *a: None)
        # apri_mail apre la bozza con os.startfile: qui la si annota soltanto.
        monkeypatch.setattr(os, "startfile", registro["aperti"].append)
        return registro

    def _con_pulsanti(self, monkeypatch, registro, premi):
        """ShowModal annota il testo della finestra e chiama premi, che fa
        quello che farebbe l'utente."""
        import GBwx
        import wx

        def show_modal(dialogo):
            registro["testi"].append(dialogo.testo.GetValue())
            premi(dialogo)
            return wx.ID_OK

        monkeypatch.setattr(GBwx._FinestraMail, "ShowModal", show_modal)

    def test_senza_posta_i_passi_copiano_indirizzo_oggetto_e_testo(self, finestra, monkeypatch):
        from GBUtils import PUB_GRUPPO
        from GBwx import finestra_mail

        from gui import pub

        def premi(dialogo):
            while dialogo.passo is not None and dialogo.passo < len(dialogo.passi) and not dialogo.riuscita:
                dialogo._avanti()

        self._con_pulsanti(monkeypatch, finestra, premi)
        mail = pub.mail_d_aiuto("10.18.0", True, INFORMAZIONI, "it", BBP)
        riuscita = finestra_mail(None, mail["titolo"], mail["destinatario"], mail["oggetto"], mail["corpo"], mail["spiegazione"],
                                 mail["passi"], pub.pulsanti(), pub.senza_posta())

        assert riuscita is True
        assert finestra["appunti"] == [PUB_GRUPPO, "Chiedo per Tornello 10.18.0", mail["corpo"]]
        assert finestra["aperti"] == []
        # Il primo passo arriva con la frase della posta che manca.
        assert finestra["testi"][0].startswith(pub.senza_posta())

    def test_con_la_posta_apri_prepara_la_bozza(self, finestra, monkeypatch):
        from GBUtils import PUB_ISCRIZIONE
        from GBwx import finestra_mail

        from gui import pub

        finestra["posta"] = "Thunderbird"
        self._con_pulsanti(monkeypatch, finestra, lambda dialogo: dialogo._apri())
        mail = pub.mail_d_iscrizione()
        riuscita = finestra_mail(None, mail["titolo"], mail["destinatario"], mail["oggetto"], mail["corpo"], mail["spiegazione"],
                                 mail["passi"], pub.pulsanti(), pub.senza_posta())

        assert riuscita is True
        (indirizzo,) = finestra["aperti"]
        assert indirizzo.startswith("mailto:" + PUB_ISCRIZIONE + "?subject=")
        assert finestra["appunti"] == []
        # La spiegazione dice il nome del programma di posta al posto del segnaposto.
        assert "Thunderbird" in finestra["testi"][0]
        assert "{programma}" not in finestra["testi"][0]
