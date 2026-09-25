"""I suoni della finestra dei risultati. Issue 51.

Fino alla 10.6.0 la finestra suonava la campanella, il preset notifica, in
tre momenti: all'apertura, a ogni arrivo del focus sui quattro pulsanti
Pianifica, Ritira, Annulla e Conferma, e premendo Pianifica, proprio mentre
la finestra di programmazione suonava il bip del giorno. Dalla 10.6.1 ci sono
due eventi suoi, uno per l'apertura e uno per i pulsanti, con due preset che
Tornello non usa per nient'altro: una regola del parco vuole un suono per
ogni evento. Dalla 10.6.2 l'annullamento della programmazione suona una
volta sola, e non piu' due. Dalla 10.10.0 anche il ripristino riuscito di
una copia di sicurezza ha il suo evento, con le stesse regole (issue 39), e
dalla 10.12.0 la finestra della composizione manuale del turno ne ha tre, per
la coppia aggiunta, la coppia con avvertimenti e la coppia tolta, piu' due
per Inverti colori, senza e con avvertimenti, e dalla 10.13.0 altri due per
Proposta automatica (issue 38).
Niente suona davvero: la collezione dei preset si legge come json, i
sorgenti come testo, e dove servono le finestre vere play_sound e' sostituita
da una finta che annota gli eventi.
"""

import json
import os
import re
from functools import cache
from types import SimpleNamespace

import pytest

RADICE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CARTELLA_SRC = os.path.join(RADICE, "src")
FINESTRA_DEI_RISULTATI = os.path.join(CARTELLA_SRC, "gui", "dialogs", "result_dialog.py")

# I due eventi nati con la 10.6.1, quello del ripristino, nato con la
# 10.10.0, e i sette della composizione manuale del turno, nati con la
# 10.12.0 e la 10.13.0.
EVENTI_NUOVI = (
    "apertura_risultati",
    "controllo_risultati",
    "ripristino",
    "coppia_aggiunta",
    "coppia_avvertimento",
    "coppia_tolta",
    "coppia_invertita",
    "coppia_invertita_avvertimento",
    "proposta_coppie",
    "proposta_coppie_avvertimento",
)

# Le chiamate con il nome scritto per intero, play_sound("...") oppure
# Acusticator.play("..."). Le f-string, come risultato_{val}, restano fuori:
# prima delle virgolette hanno la f.
CHIAMATA_LETTERALE = re.compile(r"""(?:play_sound|Acusticator\.play)\(\s*["']([^"']+)["']""")


def _leggi(percorso):
    with open(percorso, encoding="utf-8") as f:
        return f.read()


@cache
def chiamate_letterali():
    """Ogni nome passato per intero a un suono sotto src, con il file che lo
    chiama, come coppie (nome, file relativo)."""
    trovate = []
    for radice, _cartelle, files in os.walk(CARTELLA_SRC):
        for nome in files:
            if nome.endswith(".py"):
                percorso = os.path.join(radice, nome)
                relativo = os.path.relpath(percorso, CARTELLA_SRC)
                trovate += [(n, relativo) for n in CHIAMATA_LETTERALE.findall(_leggi(percorso))]
    return tuple(trovate)


@cache
def collezione():
    """La collezione dei preset di GBUtils, letta come json e senza suonare
    niente. Se GBUtils non c'e', le prove che la chiedono vengono saltate."""
    GBUtils = pytest.importorskip("GBUtils")
    percorso = os.path.join(os.path.dirname(os.path.abspath(GBUtils.__file__)), "Acu_Collection.json")
    return json.loads(_leggi(percorso))


def impronta(preset):
    """Cio' che si sente di un preset: score, forma d'onda e inviluppo. Nome e
    descrizione non contano, e due preset con la stessa impronta sono lo
    stesso suono."""
    return json.dumps([preset.get("score"), preset.get("kind", 1), preset.get("adsr")])


class TestEventiNuovi:
    def test_i_due_eventi_esistono(self):
        from utils import EVENTI

        for evento in EVENTI_NUOVI:
            assert evento in EVENTI, f"manca l'evento {evento}"

    def test_i_preset_sono_diversi_fra_loro(self):
        from utils import EVENTI

        preset = [EVENTI[evento] for evento in EVENTI_NUOVI]
        assert len(set(preset)) == len(preset)

    def test_la_finestra_delle_copie_suona_il_ripristino(self):
        nomi = {n for n, file in chiamate_letterali() if file == os.path.join("gui", "dialogs", "backup_cleanup_dialog.py")}
        assert "ripristino" in nomi

    @pytest.mark.parametrize("evento", EVENTI_NUOVI)
    def test_nessun_altro_evento_usa_il_preset(self, evento):
        from utils import EVENTI

        preset = EVENTI[evento]
        altri = sorted(e for e, p in EVENTI.items() if p == preset and e != evento)
        assert altri == [], f"{preset} suona anche per {altri}"

    @pytest.mark.parametrize("evento", EVENTI_NUOVI)
    def test_nessuna_chiamata_diretta_usa_il_preset(self, evento):
        # Ogni nome si traduce come fa play_sound: se e' un evento vale il suo
        # preset, altrimenti e' gia' il nome di un preset.
        from utils import EVENTI

        preset = EVENTI[evento]
        estranee = sorted(
            f"{nome} in {file}"
            for nome, file in chiamate_letterali()
            if EVENTI.get(nome, nome) == preset and nome != evento
        )
        assert estranee == [], f"{preset} suona anche da {estranee}"

    @pytest.mark.parametrize("evento", EVENTI_NUOVI)
    def test_il_preset_esiste_nella_collezione(self, evento):
        from utils import EVENTI

        preset = collezione().get(EVENTI[evento])
        assert preset is not None, f"{EVENTI[evento]} non e' nella collezione"
        assert preset.get("score"), f"{EVENTI[evento]} non ha note"

    @pytest.mark.parametrize("evento", EVENTI_NUOVI)
    def test_nessun_altro_suono_di_tornello_e_identico(self, evento):
        # Un preset con un altro nome ma lo stesso suono non sarebbe originale.
        from utils import EVENTI

        dati = collezione()
        preset = EVENTI[evento]
        usati = set(EVENTI.values()) | {EVENTI.get(n, n) for n, _file in chiamate_letterali()}
        uguali = sorted(
            nome
            for nome in usati - {preset}
            if nome in dati and impronta(dati[nome]) == impronta(dati[preset])
        )
        assert uguali == [], f"{preset} suona come {uguali}"

    def test_le_chiamate_letterali_si_trovano(self):
        # La prova qui sopra vale solo se la ricerca trova davvero le chiamate:
        # fra quelle dirette c'e' per esempio apertura, in main_frame.
        nomi = {n for n, _file in chiamate_letterali()}
        assert {"apertura", "cancellato", "apertura_risultati", "controllo_risultati"} <= nomi
        assert not any(n.startswith("risultato_") for n in nomi)


class TestFinestraDeiRisultati:
    def test_la_campanella_non_suona_piu(self):
        testo = _leggi(FINESTRA_DEI_RISULTATI)
        assert not re.search(r"""play_sound\(\s*["']notifica["']""", testo)

    def test_la_finestra_usa_i_due_eventi(self):
        nomi = {n for n, file in chiamate_letterali() if file == os.path.relpath(FINESTRA_DEI_RISULTATI, CARTELLA_SRC)}
        assert {"apertura_risultati", "controllo_risultati"} <= nomi


@pytest.fixture
def suoni(monkeypatch):
    """Sostituisce play_sound e bip_di_scelta con due finte che annotano,
    e rende innocuo EndModal: le finestre di queste prove non sono mai
    mostrate, e wx rifiuterebbe di chiuderne una che non e' modale. Lo si
    sostituisce su wx.Dialog, cosi' un EndModal scritto in una delle due
    finestre resta quello vero e viene provato."""
    import wx

    import utils

    registro = []
    monkeypatch.setattr(utils, "play_sound", lambda evento, *a, **k: registro.append(evento))
    monkeypatch.setattr(utils, "bip_di_scelta", lambda *a, **k: registro.append("bip"))
    monkeypatch.setattr(wx.Dialog, "EndModal", lambda self, codice: registro.append(f"fine {codice}"))
    return registro


def _finestra_dei_risultati():
    from gui.dialogs.result_dialog import ResultDialog

    return ResultDialog(None, "Bianchi Luca", "Russo Marco", 1, 2, 3, None, {}, {})


def _tasto(codice):
    """Un evento di tastiera finto, quanto basta a on_key_down."""
    return SimpleNamespace(GetKeyCode=lambda: codice, Skip=lambda: None)


class TestSuoniDelleFinestre:
    def test_apertura_e_pulsanti(self, app_grafica, suoni):
        dialogo = _finestra_dei_risultati()
        try:
            assert suoni == ["apertura_risultati"]
            suoni.clear()
            dialogo.on_control_focus(SimpleNamespace(Skip=lambda: None))
            assert suoni == ["controllo_risultati"]
        finally:
            dialogo.Destroy()

    def test_pianifica_e_esc_suonano_solo_l_annullamento(self, app_grafica, suoni, monkeypatch):
        # ESC nella finestra di programmazione passa da on_key_down, come
        # quando la si usa davvero; fino alla 10.6.1 l'annullamento suonava
        # due volte, una in EndModal della ScheduleDialog e una in on_schedule.
        import wx

        from gui.dialogs import result_dialog

        def mostra_e_annulla(finestra):
            finestra.on_key_down(_tasto(wx.WXK_ESCAPE))
            return wx.ID_CANCEL

        monkeypatch.setattr(result_dialog.ScheduleDialog, "ShowModal", mostra_e_annulla)
        dialogo = _finestra_dei_risultati()
        try:
            suoni.clear()
            dialogo.on_schedule(None)
            assert [s for s in suoni if not s.startswith("fine")] == ["cancellato"]
            assert dialogo.selected_action is None
        finally:
            dialogo.Destroy()

    def test_pianifica_e_invio_suonano_solo_la_partita_pianificata(self, app_grafica, suoni, monkeypatch):
        import wx

        from gui.dialogs import result_dialog

        def mostra_e_conferma(finestra):
            finestra.on_key_down(_tasto(wx.WXK_RETURN))
            return wx.ID_OK

        monkeypatch.setattr(result_dialog.ScheduleDialog, "ShowModal", mostra_e_conferma)
        dialogo = _finestra_dei_risultati()
        try:
            suoni.clear()
            dialogo.on_schedule(None)
            assert [s for s in suoni if not s.startswith("fine")] == ["pianifica_crea"]
            assert dialogo.selected_action == "schedule"
        finally:
            dialogo.Destroy()
