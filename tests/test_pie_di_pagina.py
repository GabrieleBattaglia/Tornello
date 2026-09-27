"""Il pie' di pagina, la barra di stato che si raggiunge con F7. Issue 53 e 54.

Dalla 10.4.2 le percentuali del tempo, cioe' GT, TT, BK e FD, si calcolano in
secondi invece che a giorni interi; dalla 10.5.0 il pie' di pagina si
aggiorna da solo e le due righe di indicatori sono a larghezza fissa, due
blocchi da 40 caratteri per la barra braille, anche con gli acronimi
tradotti; dalla 10.6.0 il focus che arriva sulla barra dall'albero o
dall'area principale mostra nell'area la sezione del manuale sugli acronimi.
Le percentuali si provano con un orologio fisso; la regola di aggiornamento,
con il focus logico che resta sulla barra quando Tornello passa in secondo
piano, gira su un telaio finto, e poche prove usano un campo di testo vero,
in una finestra mai mostrata.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from stats import (
    RIGHE_DEL_PIE_DI_PAGINA,
    giorno_del_torneo,
    indicatori_pie_di_pagina,
    righe_pie_di_pagina,
    sigle_del_pie_di_pagina,
    tempo_del_turno,
)

# Un torneo di due giorni: dalla mezzanotte del 15 alla mezzanotte del 17.
BREVE = {"start_date": "2026-09-15", "end_date": "2026-09-16"}
# Le date di Autunneo2, con il primo turno dal 15 al 30 settembre.
AUTUNNEO = {
    "start_date": "2026-09-15",
    "end_date": "2026-12-21",
    "current_round": 1,
    "round_dates": [
        {"round": 1, "start_date": "2026-09-15", "end_date": "2026-09-30"},
        {"round": 2, "start_date": "2026-10-01", "end_date": "2026-10-16"},
    ],
}
MEZZOGIORNO = datetime(2026, 9, 25, 12, 0)


def _gt(torneo, adesso):
    return indicatori_pie_di_pagina(torneo, adesso)["gt"]


def _tt(torneo, adesso):
    return indicatori_pie_di_pagina(torneo, adesso)["tt"]


class TestTempoInSecondi:
    """GT e TT dalla mezzanotte del primo giorno alla mezzanotte dopo
    l'ultimo, secondo per secondo."""

    def test_alla_mezzanotte_del_primo_giorno_vale_zero(self):
        assert _gt(BREVE, datetime(2026, 9, 15, 0, 0)) == "0.0%"

    def test_a_mezzogiorno_del_primo_giorno_vale_un_quarto(self):
        assert _gt(BREVE, datetime(2026, 9, 15, 12, 0)) == "25.0%"

    def test_alla_mezzanotte_dopo_l_ultimo_giorno_vale_cento(self):
        assert _gt(BREVE, datetime(2026, 9, 17, 0, 0)) == "100.0%"
        assert _gt(BREVE, datetime(2026, 10, 1, 9, 30)) == "100.0%"

    def test_prima_dell_inizio_vale_zero(self):
        assert _gt(BREVE, datetime(2026, 9, 14, 18, 0)) == "0.0%"

    def test_a_torneo_concluso_vale_cento(self):
        concluso = dict(BREVE, concluded=True)
        assert _gt(concluso, datetime(2026, 9, 14, 18, 0)) == "100.0%"

    def test_date_illeggibili_o_assenti(self):
        assert _gt({"start_date": "15/09/2026", "end_date": "2026-09-16"}, MEZZOGIORNO) == "--"
        assert _gt({}, MEZZOGIORNO) == "--"
        assert giorno_del_torneo({}, MEZZOGIORNO) is None

    def test_i_valori_sono_secondi(self):
        trascorsi, totale = giorno_del_torneo(BREVE, datetime(2026, 9, 15, 6, 0))
        assert trascorsi == 6 * 3600
        assert totale == 2 * 86400

    def test_autunneo_a_mezzogiorno_del_25_settembre(self):
        # A giorni interi segnava 11,2 e 68,8 per cento tutto il giorno.
        assert _gt(AUTUNNEO, MEZZOGIORNO) == "10.7%"
        assert _tt(AUTUNNEO, MEZZOGIORNO) == "65.6%"

    def test_nello_stesso_giorno_il_valore_si_muove(self):
        mattina = _tt(AUTUNNEO, datetime(2026, 9, 25, 0, 30))
        sera = _tt(AUTUNNEO, datetime(2026, 9, 25, 23, 30))
        assert mattina == "62.6%"
        assert sera == "68.6%"

    def test_i_turni_del_calendario_si_toccano(self):
        # La fine del primo turno e' l'inizio del secondo: nessun buco.
        mezzanotte = datetime(2026, 10, 1, 0, 0)
        assert _tt(AUTUNNEO, mezzanotte) == "100.0%"
        secondo = dict(AUTUNNEO, current_round=2)
        assert _tt(secondo, mezzanotte) == "0.0%"
        assert _tt(secondo, mezzanotte + timedelta(hours=12)) == "3.1%"

    def test_turno_senza_date(self):
        senza = dict(AUTUNNEO, current_round=3)
        assert tempo_del_turno(senza, MEZZOGIORNO) is None
        assert _tt(senza, MEZZOGIORNO) == "--"


class TestEtaDeiFile:
    """BK e FD: l'eta' in secondi della copia piu' vecchia e del database
    FIDE, sulle soglie di 548 e 30 giorni."""

    def _valori(self, backup=None, fide=None):
        return indicatori_pie_di_pagina({}, MEZZOGIORNO, backup, fide)

    def test_backup_a_meta_soglia(self):
        assert self._valori(backup=MEZZOGIORNO - timedelta(days=274))["bk"] == "50.0%"

    def test_database_fide(self):
        assert self._valori(fide=MEZZOGIORNO - timedelta(days=15))["fd"] == "50.0%"
        assert self._valori(fide=MEZZOGIORNO - timedelta(days=45))["fd"] == "150.0%"

    def test_meno_di_un_giorno_si_vede(self):
        # A giorni interi sarebbe stato 0.0% fino al giorno dopo.
        assert self._valori(fide=MEZZOGIORNO - timedelta(hours=12))["fd"] == "1.7%"

    def test_file_assenti(self):
        valori = self._valori()
        assert valori["bk"] == "--"
        assert valori["fd"] == "--"

    def test_data_nel_futuro_vale_zero(self):
        assert self._valori(fide=MEZZOGIORNO + timedelta(minutes=5))["fd"] == "0.0%"


class TestRigheABlocchi:
    """Le due righe di indicatori: 8 indicatori da 10 caratteri, due blocchi
    da 40 per riga, con il secondo blocco dal carattere 41."""

    def _tutti(self, valore):
        return dict.fromkeys(
            [sigla for riga in RIGHE_DEL_PIE_DI_PAGINA for sigla in riga], valore
        )

    def test_ogni_indicatore_ha_il_suo_posto(self):
        # Un indicatore nuovo va messo in una riga, e ogni riga deve restare
        # fatta di blocchi interi da quattro.
        sigle = [sigla for riga in RIGHE_DEL_PIE_DI_PAGINA for sigla in riga]
        assert sorted(sigle) == sorted(indicatori_pie_di_pagina({}, MEZZOGIORNO))
        assert sorted(sigle) == sorted(sigle_del_pie_di_pagina())
        assert all(len(riga) % 4 == 0 for riga in RIGHE_DEL_PIE_DI_PAGINA)

    def test_acronimi_tradotti_restano_di_due_caratteri(self, monkeypatch):
        # Gli acronimi passano da _() uno per uno, a ogni chiamata: una
        # traduzione piu' lunga si taglia, una piu' corta si completa con uno
        # spazio, e le righe restano di 80 caratteri.
        import builtins

        traduzioni = {"GT": "GTX", "TT": "T", "PA": "DR"}
        monkeypatch.setattr(builtins, "_", lambda testo: traduzioni.get(testo, testo))
        prima, seconda = righe_pie_di_pagina(self._tutti("10.0%"))
        assert len(prima) == len(seconda) == 80
        assert prima[:30] == "GT  10.0% T   10.0% TC  10.0% "
        assert seconda[10:20] == "DR  10.0% "

    @pytest.mark.parametrize("valore",["--", "0.0%", "9.9%", "10.0%", "100.0%", "1234.5%"])
    def test_larghezza_fissa(self, valore):
        for riga in righe_pie_di_pagina(self._tutti(valore)):
            assert len(riga) == 80

    def test_acronimi_nelle_stesse_colonne(self):
        prima, seconda = righe_pie_di_pagina(self._tutti("--"))
        assert [prima[i : i + 2] for i in range(0, 80, 10)] == [
            "GT", "TT", "TC", "PG", "RT", "PR", "AR", "PN",
        ]
        assert [seconda[i : i + 2] for i in range(0, 80, 10)] == [
            "VB", "PA", "VN", "FB", "FN", "PB", "BK", "FD",
        ]
        # Il secondo blocco da 40 comincia con un acronimo.
        assert prima[40:42] == "RT"
        assert seconda[40:42] == "FN"

    def test_valori_allineati_a_destra(self):
        valori = self._tutti("--")
        valori.update(gt="10.7%", tt="65.6%", tc="100.0%", pg="0.0%")
        prima, _seconda = righe_pie_di_pagina(valori)
        assert prima[:40] == "GT  10.7% TT  65.6% TC 100.0% PG   0.0% "
        assert prima[40:50] == "RT     -- "

    def test_valore_troppo_lungo(self):
        valori = self._tutti("--")
        valori["fd"] = "1000.0%"
        _prima, seconda = righe_pie_di_pagina(valori)
        assert seconda[70:] == "FD  >999% "

    def test_con_i_valori_veri(self):
        # Un database FIDE di 400 giorni supera il 1000 per cento.
        valori = indicatori_pie_di_pagina(
            AUTUNNEO, MEZZOGIORNO, None, MEZZOGIORNO - timedelta(days=400)
        )
        prima, seconda = righe_pie_di_pagina(valori)
        assert prima.startswith("GT  10.7% TT  65.6% ")
        assert seconda.endswith("FD  >999% ")
        assert len(prima) == len(seconda) == 80


@pytest.fixture
def main_frame():
    """Il modulo della finestra principale, senza costruire finestre; se
    wxPython manca, le prove che lo chiedono vengono saltate."""
    pytest.importorskip("wx")
    from gui import main_frame as mf

    return mf


class _CampoFinto:
    """Il minimo di wx.TextCtrl che serve al pie' di pagina: annota le
    scritture e dice se ha il focus."""

    def __init__(self, focus=False):
        self.focus = focus
        self.scritture = []

    def ChangeValue(self, testo):
        self.scritture.append(testo)

    def HasFocus(self):
        return self.focus


class _EventoDelFocus:
    """Un evento di focus: annota Skip e dice da quale finestra arriva il
    focus, o verso quale va; None e' una finestra che wx non conosce."""

    def __init__(self, finestra, registro):
        self.finestra = finestra
        self.registro = registro

    def Skip(self):
        self.registro.append("skip")

    def GetWindow(self):
        return self.finestra


def _telaio_del_focus(mf, **attributi):
    """Un telaio finto con il ricalcolo protetto vero, il focus logico fuori
    dalla barra, nessun guasto registrato e gli attributi dati."""

    class Telaio(SimpleNamespace):
        _ricalcola_pie_di_pagina = mf.MainFrame._ricalcola_pie_di_pagina

    stato = {
        "_pie_di_pagina_col_focus": False,
        "_guasto_pie_di_pagina": False,
        # L'area principale e l'albero: dalla 10.6.0 il focus che arriva da
        # loro mostra anche gli acronimi del manuale.
        "main_text": object(),
        "tree_ctrl": object(),
        "_mostra_acronimi": lambda: None,
    }
    stato.update(attributi)
    return Telaio(**stato)


class TestRegolaDiAggiornamento:
    """Il pie' di pagina si riscrive solo quando il testo cambia; il timer
    lo lascia stare mentre ha il focus logico; l'arrivo del focus lo
    ricalcola, il ritorno da un'altra applicazione no."""

    def _telaio(self, mf, monkeypatch, torneo=None):
        stili = []
        monkeypatch.setattr(
            mf, "apply_visual_settings", lambda campo, *a, **k: stili.append(campo)
        )
        telaio = SimpleNamespace(
            last_status_msg="Pronto.",
            current_tournament=torneo,
            _testo_pie_di_pagina=None,
            status_text=_CampoFinto(),
            settings={},
            _data_backup_piu_vecchio=lambda: None,
            _data_database_fide=lambda: None,
        )
        return telaio, stili

    def test_testo_uguale_non_si_riscrive(self, main_frame, monkeypatch):
        # Un torneo senza date: GT e TT valgono -- a qualunque ora, cosi' il
        # testo non dipende dall'orologio vero.
        telaio, stili = self._telaio(main_frame, monkeypatch, torneo={"total_rounds": 5})
        main_frame.MainFrame.update_status_display(telaio)
        main_frame.MainFrame.update_status_display(telaio)
        assert len(telaio.status_text.scritture) == 1
        assert len(stili) == 1
        righe = telaio.status_text.scritture[0].split("\n")
        assert righe[0] == "Pronto."
        assert [len(r) for r in righe[1:]] == [80, 80]

    def test_un_messaggio_nuovo_si_scrive(self, main_frame, monkeypatch):
        telaio, stili = self._telaio(main_frame, monkeypatch)
        main_frame.MainFrame.update_status_display(telaio)
        main_frame.MainFrame.update_status_display(telaio, "Partita aggiornata.")
        assert telaio.status_text.scritture == ["Pronto.", "Partita aggiornata."]
        assert len(stili) == 2

    def test_il_timer_non_tocca_il_campo_col_focus(self, main_frame):
        chiamate = []
        telaio = _telaio_del_focus(
            main_frame,
            status_text=_CampoFinto(focus=True),
            FindFocus=lambda: None,
            _ricalcola_pie_di_pagina=lambda: chiamate.append(1),
        )
        main_frame.MainFrame._on_timer_pie_di_pagina(telaio, None)
        assert chiamate == []
        telaio.status_text.focus = False
        main_frame.MainFrame._on_timer_pie_di_pagina(telaio, None)
        assert chiamate == [1]

    def test_il_timer_rispetta_la_barra_lasciata_col_focus(self, main_frame):
        # Tornello in secondo piano: in wxMSW nessuna finestra ha il focus,
        # ma chi torna lo ritrova sulla barra, che non deve essere cambiata.
        # Lo stesso con la cornice, che il focus lo tiene solo di passaggio.
        chiamate = []
        telaio = _telaio_del_focus(
            main_frame,
            status_text=_CampoFinto(),
            FindFocus=lambda: None,
            _pie_di_pagina_col_focus=True,
            _ricalcola_pie_di_pagina=lambda: chiamate.append(1),
        )
        main_frame.MainFrame._on_timer_pie_di_pagina(telaio, None)
        telaio.FindFocus = lambda: telaio
        main_frame.MainFrame._on_timer_pie_di_pagina(telaio, None)
        assert chiamate == []
        assert telaio._pie_di_pagina_col_focus is True

    def test_il_timer_riconosce_il_focus_su_un_altra_finestra(self, main_frame):
        # Il focus logico e' rimasto sulla barra dopo una finestra di
        # sistema, ma il focus vero e' passato all'albero: il timer lo
        # rimette a posto e ricalcola.
        chiamate = []
        albero = object()
        telaio = _telaio_del_focus(
            main_frame,
            status_text=_CampoFinto(),
            FindFocus=lambda: albero,
            _pie_di_pagina_col_focus=True,
            _ricalcola_pie_di_pagina=lambda: chiamate.append(1),
        )
        main_frame.MainFrame._on_timer_pie_di_pagina(telaio, None)
        assert chiamate == [1]
        assert telaio._pie_di_pagina_col_focus is False

    def test_un_guasto_va_nel_log_una_volta_e_il_timer_continua(
        self, main_frame, monkeypatch
    ):
        # Senza la rete, la finestra dell'errore imprevisto tornerebbe ogni
        # minuto. Il guasto si scrive una volta, e di nuovo solo dopo un
        # ricalcolo riuscito; il timer non si ferma mai.
        from gui import settings as modulo_settings

        log, fermate = [], []
        monkeypatch.setattr(modulo_settings, "_registra", log.append)
        esiti = iter(
            [TypeError("dati a meta'"), TypeError("dati a meta'"), None, TypeError("di nuovo")]
        )

        def calcolo():
            esito = next(esiti)
            if esito is not None:
                raise esito

        telaio = _telaio_del_focus(
            main_frame,
            update_status_display=calcolo,
            _timer_pie_di_pagina=SimpleNamespace(Stop=lambda: fermate.append(1)),
        )
        for _volta in range(4):
            main_frame.MainFrame._ricalcola_pie_di_pagina(telaio)
        assert len(log) == 2
        assert "dati a meta'" in log[0]
        assert "di nuovo" in log[1]
        assert fermate == []

    def test_l_arrivo_del_focus_ricalcola(self, main_frame):
        # Dall'albero, con Tab o F7: prima Skip, perche' il controllo nativo
        # prenda il cursore, poi il calcolo, dentro il gestore e non in un
        # CallAfter.
        registro = []
        telaio = _telaio_del_focus(
            main_frame, _ricalcola_pie_di_pagina=lambda: registro.append("calcolo")
        )
        albero = object()
        main_frame.MainFrame._on_focus_pie_di_pagina(
            telaio, _EventoDelFocus(albero, registro)
        )
        assert registro == ["skip", "calcolo"]
        assert telaio._pie_di_pagina_col_focus is True

    def test_arrivo_dal_nulla_senza_focus_logico_ricalcola(self, main_frame):
        # Un clic sulla barra con Tornello in secondo piano, lasciato con il
        # focus sull'albero: e' un arrivo, non un ritorno.
        registro = []
        telaio = _telaio_del_focus(
            main_frame, _ricalcola_pie_di_pagina=lambda: registro.append("calcolo")
        )
        main_frame.MainFrame._on_focus_pie_di_pagina(
            telaio, _EventoDelFocus(None, registro)
        )
        assert registro == ["skip", "calcolo"]

    def test_il_ritorno_sulla_barra_non_la_riscrive(self, main_frame):
        # Alt+Tab e ritorno: il focus torna dal nulla, o dalla cornice che lo
        # tiene di passaggio, sulla barra che ce l'aveva gia'. Il cursore
        # resta dov'era; F7 rinfresca.
        registro = []
        telaio = _telaio_del_focus(
            main_frame,
            _pie_di_pagina_col_focus=True,
            _ricalcola_pie_di_pagina=lambda: registro.append("calcolo"),
        )
        main_frame.MainFrame._on_focus_pie_di_pagina(
            telaio, _EventoDelFocus(None, registro)
        )
        main_frame.MainFrame._on_focus_pie_di_pagina(
            telaio, _EventoDelFocus(telaio, registro)
        )
        assert registro == ["skip", "skip"]
        # Da un'altra finestra di Tornello invece e' un arrivo vero, anche se
        # il focus logico era rimasto appeso sulla barra.
        main_frame.MainFrame._on_focus_pie_di_pagina(
            telaio, _EventoDelFocus(object(), registro)
        )
        assert registro == ["skip", "skip", "skip", "calcolo"]

    def test_un_guasto_all_arrivo_del_focus_non_esce(self, main_frame, monkeypatch):
        # Senza la rete, la finestra dell'errore imprevisto riporterebbe il
        # focus sulla barra, e il guasto la riaprirebbe senza fine.
        from gui import settings as modulo_settings

        log, registro = [], []
        monkeypatch.setattr(modulo_settings, "_registra", log.append)

        def calcolo_rotto():
            raise TypeError("total_rounds non e' un numero")

        telaio = _telaio_del_focus(main_frame, update_status_display=calcolo_rotto)
        for _volta in range(3):
            telaio._pie_di_pagina_col_focus = False
            main_frame.MainFrame._on_focus_pie_di_pagina(
                telaio, _EventoDelFocus(object(), registro)
            )
        assert registro == ["skip"] * 3
        assert len(log) == 1
        assert "total_rounds" in log[0]

    def test_l_uscita_verso_tornello_libera_la_barra(self, main_frame):
        registro = []
        telaio = _telaio_del_focus(main_frame, _pie_di_pagina_col_focus=True)
        # Verso un'altra applicazione o una finestra di sistema, e verso la
        # cornice, il focus logico resta sulla barra.
        main_frame.MainFrame._on_uscita_pie_di_pagina(
            telaio, _EventoDelFocus(None, registro)
        )
        main_frame.MainFrame._on_uscita_pie_di_pagina(
            telaio, _EventoDelFocus(telaio, registro)
        )
        assert telaio._pie_di_pagina_col_focus is True
        # Verso l'albero o un dialogo di Tornello se ne va.
        main_frame.MainFrame._on_uscita_pie_di_pagina(
            telaio, _EventoDelFocus(object(), registro)
        )
        assert telaio._pie_di_pagina_col_focus is False
        assert registro == ["skip"] * 3

    def test_f7_ricalcola_una_volta_sola(self, main_frame, monkeypatch):
        # Da un altro controllo il calcolo lo fa l'arrivo del focus, e F7
        # non lo ripete. Sulla barra, dove SetFocus non genera l'evento, lo
        # fa F7.
        import wx

        import utils

        monkeypatch.setattr(utils, "play_sound", lambda *a, **k: None)
        registro = []

        class Campo(_CampoFinto):
            def SetFocus(self):
                registro.append("focus")

        telaio = SimpleNamespace(
            status_text=Campo(),
            update_status_display=lambda: registro.append("calcolo"),
        )
        # Dalla 10.8.5 F7 passa dal gestore della voce Barra di Stato del
        # menu Visualizza.
        telaio.on_view_status = lambda e: main_frame.MainFrame.on_view_status(telaio, e)
        evento = SimpleNamespace(GetKeyCode=lambda: wx.WXK_F7)
        main_frame.MainFrame.on_key_hook(telaio, evento)
        assert registro == ["focus"]
        registro.clear()
        telaio.status_text.focus = True
        main_frame.MainFrame.on_key_hook(telaio, evento)
        assert registro == ["calcolo", "focus"]

    def test_sul_campo_vero_il_cursore_resta_fermo(self, main_frame, app_grafica):
        # Un TextCtrl vero, come quello del pie' di pagina, in una finestra
        # mai mostrata: se il testo non cambia, il cursore resta dov'era.
        import wx

        cornice = wx.Frame(None)
        try:
            campo = wx.TextCtrl(
                cornice, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
            )
            telaio = SimpleNamespace(
                last_status_msg="Pronto.",
                current_tournament={"total_rounds": 5},
                _testo_pie_di_pagina=None,
                status_text=campo,
                settings={},
                _data_backup_piu_vecchio=lambda: None,
                _data_database_fide=lambda: None,
            )
            main_frame.MainFrame.update_status_display(telaio)
            righe = campo.GetValue().splitlines()
            assert righe[0] == "Pronto."
            assert [len(r) for r in righe[1:]] == [80, 80]
            campo.SetInsertionPoint(50)
            main_frame.MainFrame.update_status_display(telaio)
            assert campo.GetInsertionPoint() == 50
        finally:
            cornice.Destroy()

    def test_il_timer_si_ferma_alla_chiusura(self, main_frame, monkeypatch):
        # Lo Stop viene prima di tutto: le copie di chiusura qui falliscono
        # apposta, e il timer deve risultare fermo lo stesso.
        import utils

        registro = []

        def copie_rotte(_nome):
            raise RuntimeError("copie di chiusura")

        monkeypatch.setattr(utils, "copie_di_chiusura", copie_rotte)
        telaio = SimpleNamespace(
            _timer_pie_di_pagina=SimpleNamespace(Stop=lambda: registro.append("stop")),
            active_filename=None,
        )
        with pytest.raises(RuntimeError):
            main_frame.MainFrame.on_close(telaio, None)
        assert registro == ["stop"]


# Un manuale in miniatura, con la sezione degli acronimi fra altre due.
MANUALE_IN_MINIATURA = "\n".join(
    [
        "2.3 LA BARRA DI STATO INFERIORE (Tasto F7)",
        "La barra.",
        "",
        "2.3.1 GLI ACRONIMI DEL PIÈ DI PAGINA",
        "- GT, giorno del torneo.",
        "- TT, tempo del turno.",
        "",
        "2.4 ACCESSIBILITÀ DEI DIALOGHI",
        "I dialoghi.",
    ]
)
SEZIONE_IN_MINIATURA = (
    "2.3.1 GLI ACRONIMI DEL PIÈ DI PAGINA\n- GT, giorno del torneo.\n- TT, tempo del turno."
)
UN_TORNEO = {"total_rounds": 5}


class _AreaFinta:
    """Il minimo dell'area principale che serve agli acronimi: il testo, e
    il registro di cancellazioni, scritture e spostamenti del focus."""

    def __init__(self, testo=""):
        self.testo = testo
        self.registro = []

    def GetValue(self):
        return self.testo

    def Clear(self):
        self.testo = ""
        self.registro.append("clear")

    def SetFocus(self):
        self.registro.append("focus")

    def scrivi(self, testo):
        """Come append_log: accoda, con il ritorno a capo finale."""
        self.testo += testo if testo.endswith("\n") else testo + "\n"
        self.registro.append("scrivi")


class TestAcronimiAlFocus:
    """Issue 54: il focus che arriva sulla barra dall'albero o dall'area
    principale mostra nell'area la sezione 2.3.1 del manuale, che resta
    finche' un'altra azione non la riscrive."""

    def _telaio(self, area, torneo=UN_TORNEO, creazione=False, manuale=MANUALE_IN_MINIATURA):
        return SimpleNamespace(
            current_tournament=torneo,
            creation_mode=creazione,
            main_text=area,
            append_log=area.scrivi,
            _leggi_manuale=lambda: manuale,
        )

    def test_dall_albero_e_dall_area_si_mostrano(self, main_frame):
        # F7, Tab, Maiusc+Tab o un clic: prima il ricalcolo della barra, che
        # NVDA sta per leggere, poi l'area, che nessuno sta leggendo.
        registro = []
        telaio = _telaio_del_focus(
            main_frame,
            _ricalcola_pie_di_pagina=lambda: registro.append("calcolo"),
            _mostra_acronimi=lambda: registro.append("acronimi"),
        )
        main_frame.MainFrame._on_focus_pie_di_pagina(
            telaio, _EventoDelFocus(telaio.tree_ctrl, registro)
        )
        assert registro == ["skip", "calcolo", "acronimi"]
        registro.clear()
        telaio._pie_di_pagina_col_focus = False
        main_frame.MainFrame._on_focus_pie_di_pagina(
            telaio, _EventoDelFocus(telaio.main_text, registro)
        )
        assert registro == ["skip", "calcolo", "acronimi"]

    def test_da_un_dialogo_o_da_un_altra_applicazione_no(self, main_frame):
        # Il focus che torna da un dialogo chiuso, per esempio dopo Ctrl+P
        # lanciato dalla barra, o da un'altra applicazione: la sezione
        # cancellerebbe il report appena scritto.
        registro = []
        telaio = _telaio_del_focus(
            main_frame,
            _ricalcola_pie_di_pagina=lambda: registro.append("calcolo"),
            _mostra_acronimi=lambda: registro.append("acronimi"),
        )
        main_frame.MainFrame._on_focus_pie_di_pagina(
            telaio, _EventoDelFocus(object(), registro)
        )
        telaio._pie_di_pagina_col_focus = False
        main_frame.MainFrame._on_focus_pie_di_pagina(
            telaio, _EventoDelFocus(None, registro)
        )
        main_frame.MainFrame._on_focus_pie_di_pagina(
            telaio, _EventoDelFocus(None, registro)
        )
        main_frame.MainFrame._on_focus_pie_di_pagina(
            telaio, _EventoDelFocus(telaio, registro)
        )
        assert "acronimi" not in registro
        assert registro == ["skip", "calcolo", "skip", "calcolo", "skip", "skip"]

    def test_scrive_la_sezione_senza_spostare_il_focus(self, main_frame):
        area = _AreaFinta("Classifica dopo il turno 3\n")
        main_frame.MainFrame._mostra_acronimi(self._telaio(area))
        assert area.testo == SEZIONE_IN_MINIATURA + "\n"
        assert area.registro == ["clear", "scrivi"]

    def test_se_la_sezione_c_e_gia_non_la_riscrive(self, main_frame):
        # Con i ritorni a capo come puo' restituirli il RichEdit: chi la stava
        # leggendo ritrova il cursore dove l'aveva lasciato.
        area = _AreaFinta(SEZIONE_IN_MINIATURA.replace("\n", "\r\n") + "\r\n")
        main_frame.MainFrame._mostra_acronimi(self._telaio(area))
        assert area.registro == []

    def test_senza_torneo_nella_procedura_guidata_o_senza_manuale(self, main_frame):
        area = _AreaFinta("Benvenuto in Tornello\n")
        main_frame.MainFrame._mostra_acronimi(self._telaio(area, torneo=None))
        main_frame.MainFrame._mostra_acronimi(self._telaio(area, creazione=True))
        main_frame.MainFrame._mostra_acronimi(self._telaio(area, manuale=""))
        assert area.registro == []
        assert area.testo == "Benvenuto in Tornello\n"

    def test_il_timer_non_tocca_l_area(self, main_frame, monkeypatch):
        # Il ricalcolo di ogni minuto non conta come un'altra informazione:
        # la sezione resta. Il timer fa tutta la strada vera, fino a
        # update_status_display con un torneo aperto; un torneo senza date
        # rende il testo indipendente dall'orologio. Una scrittura sull'area
        # finirebbe nel suo registro; un metodo che l'area finta non ha
        # solleverebbe un errore, che il ricalcolo protetto manda nel log.
        # Per questo la barra deve risultare scritta e il log vuoto.
        from gui import settings as modulo_settings

        log = []
        monkeypatch.setattr(modulo_settings, "_registra", log.append)
        monkeypatch.setattr(main_frame, "apply_visual_settings", lambda *a, **k: None)
        area = _AreaFinta(SEZIONE_IN_MINIATURA + "\n")
        telaio = _telaio_del_focus(
            main_frame,
            status_text=_CampoFinto(),
            FindFocus=lambda: None,
            main_text=area,
            append_log=area.scrivi,
            current_tournament=UN_TORNEO,
            last_status_msg="Pronto.",
            _testo_pie_di_pagina=None,
            settings={},
            _data_backup_piu_vecchio=lambda: None,
            _data_database_fide=lambda: None,
        )
        telaio.update_status_display = lambda action_msg=None: (
            main_frame.MainFrame.update_status_display(telaio, action_msg)
        )
        main_frame.MainFrame._on_timer_pie_di_pagina(telaio, None)
        assert log == []
        assert telaio._guasto_pie_di_pagina is False
        assert len(telaio.status_text.scritture) == 1
        assert telaio.status_text.scritture[0].startswith("Pronto.\n")
        assert area.registro == []
        assert area.testo == SEZIONE_IN_MINIATURA + "\n"

    def test_sul_campo_vero(self, main_frame, app_grafica):
        # Un TextCtrl vero, come l'area principale, in una finestra mai
        # mostrata: la sezione prende il posto del report, e la seconda volta
        # il cursore resta dov'era.
        import wx

        cornice = wx.Frame(None)
        try:
            campo = wx.TextCtrl(
                cornice, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
            )
            campo.SetValue("Classifica dopo il turno 3")
            telaio = SimpleNamespace(
                current_tournament=UN_TORNEO,
                creation_mode=False,
                main_text=campo,
                _leggi_manuale=lambda: MANUALE_IN_MINIATURA,
            )
            telaio.append_log = lambda testo: main_frame.MainFrame.append_log(telaio, testo)
            main_frame.MainFrame._mostra_acronimi(telaio)
            assert campo.GetValue().splitlines() == SEZIONE_IN_MINIATURA.split("\n")
            campo.SetInsertionPoint(20)
            main_frame.MainFrame._mostra_acronimi(telaio)
            assert campo.GetInsertionPoint() == 20
        finally:
            cornice.Destroy()

    def test_la_provenienza_con_controlli_veri(self, main_frame, app_grafica):
        # Il confronto e' per identita': wx deve restituire da GetWindow lo
        # stesso oggetto Python dell'albero e dell'area, non un involucro
        # nuovo attorno allo stesso controllo.
        import wx

        cornice = wx.Frame(None)
        try:
            registro = []
            telaio = _telaio_del_focus(
                main_frame,
                main_text=wx.TextCtrl(cornice, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2),
                tree_ctrl=wx.TreeCtrl(cornice),
                _ricalcola_pie_di_pagina=lambda: registro.append("calcolo"),
                _mostra_acronimi=lambda: registro.append("acronimi"),
            )
            for provenienza in (telaio.tree_ctrl, telaio.main_text, wx.Button(cornice)):
                evento = wx.FocusEvent(wx.wxEVT_SET_FOCUS)
                evento.SetWindow(provenienza)
                telaio._pie_di_pagina_col_focus = False
                main_frame.MainFrame._on_focus_pie_di_pagina(telaio, evento)
            assert registro == ["calcolo", "acronimi", "calcolo", "acronimi", "calcolo"]
        finally:
            cornice.Destroy()

    def test_la_costante_trova_la_sezione_nel_manuale_vero(self, main_frame):
        # MANUALE.txt letto come lo legge F1, in sola lettura.
        from utils import sezione_del_manuale

        testo = main_frame.MainFrame._leggi_manuale()
        sezione = sezione_del_manuale(testo, main_frame.SEZIONE_DEGLI_ACRONIMI)
        assert sezione.startswith("2.3.1 GLI ACRONIMI DEL PIÈ DI PAGINA\n")

    def test_manuale_mancante(self, main_frame, monkeypatch, tmp_path):
        import config

        monkeypatch.setattr(config, "resource_path", lambda nome: str(tmp_path / nome))
        assert main_frame.MainFrame._leggi_manuale() == ""
