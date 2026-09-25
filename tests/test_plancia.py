"""Le partite da giocare nella plancia di comando, l'albero che si raggiunge
con F6. Issue 52.

Dalla 10.4.0 l'etichetta di una partita programmata dice anche sala e
arbitro, accorciati; i valori interi li mostra l'area centrale quando la
voce prende il fuoco. Niente finestre vere: i metodi di MainFrame girano su
un telaio finto, con un albero finto che annota le voci.
"""

from types import SimpleNamespace

import pytest

pytest.importorskip("wx")


class _AlberoFinto:
    """Il minimo di wx.TreeCtrl che serve alla plancia: ogni voce ricorda il
    genitore, l'etichetta e i dati."""

    def __init__(self):
        self.voci = []

    def AppendItem(self, genitore, etichetta):
        voce = SimpleNamespace(genitore=genitore, etichetta=etichetta, dati=None)
        voce.IsOk = lambda: True
        self.voci.append(voce)
        return voce

    def SetItemData(self, voce, dati):
        voce.dati = dati

    def SetItemText(self, voce, etichetta):
        voce.etichetta = etichetta

    def GetItemData(self, voce):
        return voce.dati

    def etichette(self):
        return [voce.etichetta for voce in self.voci]

    def voce_della_partita(self, id_partita):
        return next(
            voce
            for voce in self.voci
            if voce.dati
            and voce.dati.get("action") == "activate_match"
            and voce.dati["match"].get("id") == id_partita
        )


GIOCATORI = [
    {"id": "BIA", "last_name": "Bianchi", "first_name": "Luca"},
    {"id": "VER", "last_name": "Verdi", "first_name": "Anna"},
    {"id": "NER", "last_name": "Neri", "first_name": "Paolo"},
    {"id": "RUS", "last_name": "Russo", "first_name": "Marco"},
    {"id": "FER", "last_name": "Ferrari", "first_name": "Elena"},
    {"id": "ESP", "last_name": "Esposito", "first_name": "Carlo"},
    {"id": "COL", "last_name": "Colombo", "first_name": "Sara"},
    {"id": "GRE", "last_name": "Greco", "first_name": "Davide"},
]
CANALE_LUNGO = "whatsapp https://call.whatsapp.com/voice/AbC123xyz"


def _torneo():
    """Un turno con due partite programmate, una no e una gia' giocata. La
    scacchiera 1 si gioca un giorno dopo la 2: cosi' l'ordine per data e ora
    non coincide con quello per scacchiera."""
    partite = [
        {
            "id": 1,
            "white_player_id": "BIA",
            "black_player_id": "VER",
            "result": None,
            "is_scheduled": True,
            "schedule_info": {
                "date": "2026-09-27",
                "time": "17:30",
                "channel": CANALE_LUNGO,
                "arbiter": "Giuseppe Baratta",
            },
        },
        {
            "id": 2,
            "white_player_id": "NER",
            "black_player_id": "RUS",
            "result": None,
            "is_scheduled": True,
            "schedule_info": {
                "date": "2026-09-26",
                "time": "18:00",
                "channel": "",
                "arbiter": "Non necessario",
                "arbiter_not_needed": True,
            },
        },
        {
            "id": 3,
            "white_player_id": "FER",
            "black_player_id": "ESP",
            "result": None,
            "is_scheduled": False,
        },
        {
            "id": 4,
            "white_player_id": "COL",
            "black_player_id": "GRE",
            "result": "1-0",
        },
    ]
    return {
        "name": "Prova",
        "total_rounds": 5,
        "current_round": 1,
        "players": GIOCATORI,
        "players_dict": {g["id"]: g for g in GIOCATORI},
        "rounds": [{"round": 1, "matches": partite}],
    }


def _telaio(torneo):
    """Un telaio con i soli metodi della plancia che servono: albero e area
    centrale sono finti, e cio' che finisce nell'area centrale si annota."""
    from gui.main_frame import MainFrame

    class Telaio:
        add_round_subnodes = MainFrame.add_round_subnodes
        on_tree_selection_changed = MainFrame.on_tree_selection_changed
        show_match_detail_verbose = MainFrame.show_match_detail_verbose

        def __init__(self):
            self.tree_ctrl = _AlberoFinto()
            self.main_text = SimpleNamespace(Clear=self._svuota)
            self.current_tournament = torneo
            self.active_filename = "prova.json"
            self.creation_mode = False
            self.area_centrale = []

        def _svuota(self):
            self.area_centrale = []

        def append_log(self, testo):
            self.area_centrale.append(testo)

    telaio = Telaio()
    telaio.add_round_subnodes(
        "turni",
        torneo["rounds"][0],
        torneo,
        "prova.json",
        torneo["players_dict"],
        False,
    )
    return telaio


def _etichetta_programmata(scacchiera, bianco, nero, data, ora, sala, arbitro):
    from utils import format_date_locale

    return _(
        "Scacchiera {board}: {white} vs {black} (Pianificata: {date} {time}, sala {room}, arbitro {arbiter})"
    ).format(
        board=scacchiera,
        white=bianco,
        black=nero,
        date=format_date_locale(data),
        time=ora,
        room=sala,
        arbiter=arbitro,
    )


class TestEtichetteDaGiocare:
    def test_la_partita_programmata_dice_sala_e_arbitro(self):
        telaio = _telaio(_torneo())

        assert (
            _etichetta_programmata(
                1,
                "Bianchi Luca",
                "Verdi Anna",
                "2026-09-27",
                "17:30",
                "whatsapp",
                "Giuseppe Bar",
            )
            in telaio.tree_ctrl.etichette()
        )

    def test_arbitro_non_necessario_e_sala_vuota(self):
        telaio = _telaio(_torneo())

        assert (
            _etichetta_programmata(
                2,
                "Neri Paolo",
                "Russo Marco",
                "2026-09-26",
                "18:00",
                _("N/D"),
                _("No"),
            )
            in telaio.tree_ctrl.etichette()
        )

    def test_la_partita_non_programmata_resta_come_prima(self):
        telaio = _telaio(_torneo())

        attesa = _("Scacchiera {}: {} vs {} (Non pianificata)").format(
            3, "Ferrari Elena", "Esposito Carlo"
        )
        assert attesa in telaio.tree_ctrl.etichette()

    def test_l_ordine_resta_per_data_e_ora(self):
        """Prima le programmate, per giorno e ora anche contro l'ordine delle
        scacchiere, poi le altre."""
        telaio = _telaio(_torneo())

        da_giocare = [
            voce.dati["match"]["id"]
            for voce in telaio.tree_ctrl.voci
            if voce.dati
            and voce.dati.get("action") == "activate_match"
            and voce.dati["match"].get("result") is None
        ]
        assert da_giocare == [2, 1, 3]


class TestDettaglioNellAreaCentrale:
    """Spostandosi con le frecce su una partita da giocare, l'area centrale
    mostra sala o URL e arbitro per intero, qualunque cosa dica l'etichetta
    accorciata."""

    def _seleziona(self, telaio, id_partita):
        voce = telaio.tree_ctrl.voce_della_partita(id_partita)
        telaio.on_tree_selection_changed(SimpleNamespace(GetItem=lambda: voce))
        return "\n".join(telaio.area_centrale)

    def test_sala_e_arbitro_per_intero(self):
        telaio = _telaio(_torneo())

        testo = self._seleziona(telaio, 1)

        assert f"{_('Sala/URL')}: {CANALE_LUNGO}" in testo
        assert f"{_('Arbitro')}: Giuseppe Baratta" in testo

    def test_arbitro_non_necessario_e_sala_vuota(self):
        telaio = _telaio(_torneo())

        testo = self._seleziona(telaio, 2)

        assert f"{_('Sala/URL')}: {_('N/D')}" in testo
        assert f"{_('Arbitro')}: Non necessario" in testo
