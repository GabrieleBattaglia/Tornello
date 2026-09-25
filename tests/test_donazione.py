"""L'invito alla donazione che la finestra mostra alla chiusura. Issue 40.

Fino alla 10.3.4 la finestra deviava sys.stdout su uno StringIO, chiamava
Donazione e rileggeva cio' che aveva stampato, il tutto dentro un except
Exception: pass che nascondeva qualunque guasto. Qui si prova che il testo
arriva dal valore restituito, con stampa=False, e che un guasto dell'invito
finisce nel log senza impedire la chiusura. Niente finestre vere: Donazione e
DonationDialog sono sostituite da finte, e i metodi di MainFrame girano su un
telaio finto.
"""

import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def registro(monkeypatch):
    """Sostituisce DonationDialog con una finta che annota cio' che riceve."""
    import gui.dialogs.donation_dialog as modulo_dialogo

    registro = {"dialoghi": [], "mostrati": 0, "distrutti": 0}

    class DialogoFinto:
        def __init__(self, parent, titolo, messaggio, settings=None):
            registro["dialoghi"].append(
                {"parent": parent, "titolo": titolo, "messaggio": messaggio, "settings": settings}
            )

        def ShowModal(self):
            registro["mostrati"] += 1

        def Destroy(self):
            registro["distrutti"] += 1

    monkeypatch.setattr(modulo_dialogo, "DonationDialog", DialogoFinto)
    return registro


def _donazione_finta(monkeypatch, esito):
    """Sostituisce Donazione in GBUtils con una finta che annota gli argomenti
    e se durante la chiamata sys.stdout e' ancora quello di partenza. Se esito
    e' un'eccezione la solleva, altrimenti lo restituisce."""
    import GBUtils

    chiamate = []
    stdout_di_partenza = sys.stdout

    def finta(**argomenti):
        chiamate.append(
            {"argomenti": argomenti, "stdout_intatto": sys.stdout is stdout_di_partenza}
        )
        if isinstance(esito, Exception):
            raise esito
        return esito

    monkeypatch.setattr(GBUtils, "Donazione", finta)
    return chiamate


class TestInvitoDonazione:
    """Il metodo che chiede il testo a Donazione e apre la finestra."""

    def test_passa_stampa_falso_e_la_lingua_delle_impostazioni(
        self, monkeypatch, registro, capsys
    ):
        from gui import main_frame as mf

        chiamate = _donazione_finta(monkeypatch, "Offrimi un caffe'.")
        telaio = SimpleNamespace(settings={"language": "en"})

        mf.MainFrame._invito_donazione(telaio)

        assert chiamate == [
            {"argomenti": {"lang": "en", "stampa": False}, "stdout_intatto": True}
        ]
        assert len(registro["dialoghi"]) == 1
        assert registro["dialoghi"][0]["messaggio"] == "Offrimi un caffe'."
        assert registro["dialoghi"][0]["parent"] is telaio
        assert registro["dialoghi"][0]["settings"] == {"language": "en"}
        assert registro["mostrati"] == 1
        assert registro["distrutti"] == 1
        assert capsys.readouterr().out == ""

    def test_senza_impostazioni_la_lingua_e_none(self, monkeypatch, registro):
        from gui import main_frame as mf

        chiamate = _donazione_finta(monkeypatch, None)

        mf.MainFrame._invito_donazione(SimpleNamespace(settings=None))

        assert chiamate[0]["argomenti"] == {"lang": None, "stampa": False}

    def test_con_none_non_si_apre_niente(self, monkeypatch, registro, capsys):
        from gui import main_frame as mf

        _donazione_finta(monkeypatch, None)

        mf.MainFrame._invito_donazione(SimpleNamespace(settings={"language": "it"}))

        assert registro["dialoghi"] == []
        assert registro["mostrati"] == 0
        assert capsys.readouterr().out == ""

    def test_la_donazione_vera_non_stampa_niente(self, monkeypatch, registro, capsys):
        """Con gli argomenti che passa la finestra, la Donazione vera di
        GBUtils non scrive su stdout e il suo testo arriva al dialogo. Il
        sorteggio si forza a cento per non dipendere dal caso."""
        import GBUtils

        from gui import main_frame as mf

        vera = GBUtils.Donazione
        monkeypatch.setattr(
            GBUtils, "Donazione", lambda **argomenti: vera(probabilita=100, **argomenti)
        )

        mf.MainFrame._invito_donazione(SimpleNamespace(settings={"language": "it"}))

        assert capsys.readouterr().out == ""
        assert len(registro["dialoghi"]) == 1
        assert registro["dialoghi"][0]["messaggio"].startswith("Se questo software")


class TestChiusura:
    """on_close fa le copie, suona e invita, e la finestra si chiude comunque."""

    def _telaio(self, monkeypatch, log_vero=False):
        """Con log_vero il guasto va in error.log attraverso il _registra vero,
        altrimenti finisce nella lista passi["log"]."""
        import utils
        from gui import main_frame as mf
        from gui import settings as modulo_settings

        passi = {"copie": [], "suoni": [], "log": [], "skip": 0}
        monkeypatch.setattr(utils, "copie_di_chiusura", lambda nome: passi["copie"].append(nome))
        monkeypatch.setattr(
            utils, "play_sound", lambda nome, *resto, **opzioni: passi["suoni"].append(nome)
        )
        if not log_vero:
            monkeypatch.setattr(modulo_settings, "_registra", passi["log"].append)

        class TelaioFinto:
            _invito_donazione = mf.MainFrame._invito_donazione

            def __init__(self):
                self.active_filename = "Tornello - Prova.json"
                self.current_tournament = None
                self.settings = {"language": "it"}

        class EventoFinto:
            def Skip(self):
                passi["skip"] += 1

        return TelaioFinto(), EventoFinto(), passi

    def test_un_guasto_di_donazione_non_impedisce_la_chiusura(
        self, monkeypatch, registro
    ):
        from gui import main_frame as mf

        _donazione_finta(monkeypatch, RuntimeError("sorteggio rotto"))
        telaio, evento, passi = self._telaio(monkeypatch)

        mf.MainFrame.on_close(telaio, evento)

        assert passi["skip"] == 1
        assert len(passi["log"]) == 1
        assert "Invito alla donazione non mostrato" in passi["log"][0]
        assert "sorteggio rotto" in passi["log"][0]
        assert registro["dialoghi"] == []

    def test_il_guasto_arriva_in_error_log_con_il_traceback(
        self, monkeypatch, registro, tmp_path
    ):
        """Qui _registra e' quello vero, e error.log sta nella cartella della
        prova grazie a dati_in_cartella_temporanea. Il traceback lo scrive
        format_exc, che lo trova solo se _registra viene chiamata dentro
        l'except: chiamata dopo, scriverebbe NoneType: None."""
        from gui import main_frame as mf

        _donazione_finta(monkeypatch, RuntimeError("sorteggio rotto"))
        telaio, evento, passi = self._telaio(monkeypatch, log_vero=True)

        mf.MainFrame.on_close(telaio, evento)

        testo = (tmp_path / "error.log").read_text(encoding="utf-8")
        assert "Invito alla donazione non mostrato: sorteggio rotto" in testo
        assert "RuntimeError: sorteggio rotto" in testo
        assert "NoneType: None" not in testo
        assert passi["skip"] == 1

    def test_chiusura_normale_copie_suono_invito(self, monkeypatch, registro):
        from gui import main_frame as mf

        chiamate = _donazione_finta(monkeypatch, "Un caffe'?")
        telaio, evento, passi = self._telaio(monkeypatch)

        mf.MainFrame.on_close(telaio, evento)

        assert passi["copie"] == ["Tornello - Prova.json"]
        assert passi["suoni"] == ["chiusura"]
        assert chiamate[0]["argomenti"] == {"lang": "it", "stampa": False}
        assert registro["mostrati"] == 1
        assert passi["log"] == []
        assert passi["skip"] == 1
