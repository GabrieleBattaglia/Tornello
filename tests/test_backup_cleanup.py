import os
import sys
import tempfile
from datetime import datetime

# Add src folder to path just in case
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from gui.dialogs.backup_cleanup_dialog import calculate_age, delete_file_to_trash


def test_calculate_age():
    today = datetime(2026, 7, 9)

    # Test exactly 18 months ago
    mtime_18m = datetime(2025, 1, 9)
    months, days = calculate_age(mtime_18m, today)
    assert months == 18
    assert days == 0

    # Test 18 months and 15 days ago
    mtime_18m_15d = datetime(2024, 12, 25)
    months, days = calculate_age(mtime_18m_15d, today)
    assert months == 18
    assert days == 14 or days == 15  # depending on calendar details

    # Test future date
    future_date = datetime(2027, 7, 9)
    months, days = calculate_age(future_date, today)
    assert months == 0
    assert days == 0


def test_delete_file_to_trash():
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"test content")
        tmp_path = tmp.name

    assert os.path.exists(tmp_path)

    # Delete it using our helper
    success = delete_file_to_trash(tmp_path)
    assert success
    assert not os.path.exists(tmp_path)


class TestElencoDeiBackup:
    """La lettura dei file di backup, usata sia dalla pulizia automatica
    all'avvio sia dalla finestra di pulizia manuale. Dalla versione 9.7.0 i
    backup stanno nelle sottocartelle dell'anno e del mese, quindi la lettura
    deve scendere nell'albero: prima si fermava al primo livello e non avrebbe
    piu' trovato nulla."""

    def _crea(self, cartella, nome, giorni_fa=0):
        import time

        cartella.mkdir(parents=True, exist_ok=True)
        percorso = cartella / nome
        percorso.write_text("contenuto", encoding="utf-8")
        if giorni_fa:
            quando = time.time() - giorni_fa * 86400
            os.utime(percorso, (quando, quando))
        return percorso

    def test_trova_i_file_nelle_sottocartelle(self, tmp_path):
        from utils import elenca_file_di_backup

        self._crea(tmp_path / "2026" / "09 Settembre", "recente.json")
        self._crea(tmp_path / "2024" / "01 Gennaio", "vecchio.json")

        tutti, _vecchi = elenca_file_di_backup(str(tmp_path))

        assert sorted(f["name"] for f in tutti) == ["recente.json", "vecchio.json"]

    def test_separa_i_file_piu_vecchi_del_limite(self, tmp_path):
        from datetime import datetime, timedelta

        from utils import elenca_file_di_backup

        self._crea(tmp_path / "2026" / "09 Settembre", "recente.json")
        self._crea(tmp_path / "2024" / "01 Gennaio", "vecchio.json", giorni_fa=700)
        limite = datetime.now() - timedelta(days=548)

        tutti, vecchi = elenca_file_di_backup(str(tmp_path), limite)

        assert len(tutti) == 2
        assert [f["name"] for f in vecchi] == ["vecchio.json"]

    def test_ordina_dal_piu_vecchio_al_piu_recente(self, tmp_path):
        from utils import elenca_file_di_backup

        self._crea(tmp_path / "2026" / "09 Settembre", "recente.json")
        self._crea(tmp_path / "2025" / "05 Maggio", "meno_recente.json", giorni_fa=200)
        self._crea(tmp_path / "2024" / "01 Gennaio", "vecchio.json", giorni_fa=700)

        tutti, _vecchi = elenca_file_di_backup(str(tmp_path))

        assert [f["name"] for f in tutti] == [
            "vecchio.json",
            "meno_recente.json",
            "recente.json",
        ]

    def test_una_cartella_che_non_esiste_non_fa_danni(self, tmp_path):
        from utils import elenca_file_di_backup

        assert elenca_file_di_backup(str(tmp_path / "assente")) == ([], [])
        assert elenca_file_di_backup("") == ([], [])


class TestCartelleVuote:
    """Dopo le cancellazioni le cartelle dell'anno e del mese restano li' a
    vuoto. Richiesta di Gabriele del 2026-09-05: il sistema deve toglierle."""

    def test_toglie_mese_e_anno_rimasti_vuoti(self, tmp_path):
        from utils import rimuovi_cartelle_vuote

        (tmp_path / "2024" / "01 Gennaio").mkdir(parents=True)
        (tmp_path / "2024" / "02 Febbraio").mkdir(parents=True)

        rimosse = rimuovi_cartelle_vuote(str(tmp_path))

        assert rimosse == 3
        assert not (tmp_path / "2024").exists()
        assert tmp_path.exists()

    def test_non_tocca_le_cartelle_che_contengono_file(self, tmp_path):
        from utils import rimuovi_cartelle_vuote

        piena = tmp_path / "2026" / "09 Settembre"
        piena.mkdir(parents=True)
        (piena / "copia.json").write_text("{}", encoding="utf-8")
        (tmp_path / "2024" / "01 Gennaio").mkdir(parents=True)

        rimuovi_cartelle_vuote(str(tmp_path))

        assert piena.exists()
        assert (piena / "copia.json").exists()
        assert not (tmp_path / "2024").exists()

    def test_la_radice_resta_anche_se_vuota(self, tmp_path):
        from utils import rimuovi_cartelle_vuote

        assert rimuovi_cartelle_vuote(str(tmp_path)) == 0
        assert tmp_path.exists()

    def test_una_cartella_inesistente_non_fa_danni(self, tmp_path):
        from utils import rimuovi_cartelle_vuote

        assert rimuovi_cartelle_vuote(str(tmp_path / "assente")) == 0
        assert rimuovi_cartelle_vuote("") == 0


class TestCicloCompletoDeiBackup:
    """La prova che tiene insieme i pezzi: si crea una copia di sicurezza, la
    si ritrova nella sottocartella del mese, la si cancella e la cartella
    rimasta vuota sparisce."""

    def test_dalla_copia_alla_pulizia(self, tmp_path, monkeypatch):
        import config
        import utils
        from gui.dialogs.backup_cleanup_dialog import delete_file_to_trash
        from utils import (
            cartella_per_data,
            create_backup,
            elenca_file_di_backup,
            rimuovi_cartelle_vuote,
        )

        monkeypatch.setattr(config, "user_data_path", lambda p: str(tmp_path / p))
        origine = tmp_path / "Tornello - Prova.json"
        origine.write_text("{}", encoding="utf-8")

        assert create_backup(str(origine), "pre_prova") is True

        cartella_backup = str(tmp_path / "backup")
        attesa = cartella_per_data(cartella_backup, crea=False)
        assert os.path.isdir(attesa), "la copia deve stare sotto anno e mese"

        tutti, _vecchi = elenca_file_di_backup(cartella_backup)
        assert len(tutti) == 1
        assert "pre_prova" in tutti[0]["name"]

        assert delete_file_to_trash(tutti[0]["path"]) is True
        assert rimuovi_cartelle_vuote(cartella_backup) == 2
        assert not os.path.isdir(attesa)
        assert os.path.isdir(cartella_backup)
        assert utils.elenca_file_di_backup(cartella_backup) == ([], [])


class TestRilevatoreAutomatico:
    """Il controllo che parte all'avvio e segnala i backup piu' vecchi di
    diciotto mesi. Va provato davvero, perche' con i backup finiti nelle
    sottocartelle dell'anno e del mese una lettura ferma al primo livello non
    troverebbe piu' nulla e il controllo sarebbe diventato muto."""

    def _prepara(self, tmp_path, monkeypatch):
        import time

        import config
        from gui import main_frame as mf

        monkeypatch.setattr(config, "user_data_path", lambda p: str(tmp_path / p))
        monkeypatch.setattr(mf, "user_data_path", lambda p: str(tmp_path / p))

        vecchia = tmp_path / "backup" / "2023" / "05 Maggio"
        vecchia.mkdir(parents=True)
        antico = vecchia / "Tornello - Antico_pre_prova.json"
        antico.write_text("{}", encoding="utf-8")
        quando = time.time() - 900 * 86400
        os.utime(antico, (quando, quando))

        recente = tmp_path / "backup" / "2026" / "09 Settembre"
        recente.mkdir(parents=True)
        (recente / "Tornello - Nuovo.json").write_text("{}", encoding="utf-8")

        # Una cartella rimasta vuota, come ne restano dopo le cancellazioni.
        (tmp_path / "backup" / "2022" / "03 Marzo").mkdir(parents=True)
        return antico

    def _telaio(self, monkeypatch, risposta):
        import wx
        from gui import main_frame as mf

        registro = {"messaggio": None, "pulizia_aperta": False}

        class DialogoFinto:
            def __init__(self, parent, titolo, messaggio, style=None, settings=None):
                registro["messaggio"] = messaggio

            def ShowModal(self):
                return risposta

            def Destroy(self):
                pass

        monkeypatch.setattr(mf, "AccessibleMsgDialog", DialogoFinto)

        class TelaioFinto:
            settings = {}

            def on_backup_cleanup(self, event):
                registro["pulizia_aperta"] = True

        return TelaioFinto(), registro, wx

    def test_trova_i_backup_vecchi_nelle_sottocartelle(self, tmp_path, monkeypatch):
        import wx
        from gui import main_frame as mf

        self._prepara(tmp_path, monkeypatch)
        telaio, registro, _wx = self._telaio(monkeypatch, wx.ID_NO)

        mf.MainFrame._check_backup_on_startup(telaio)

        assert registro["messaggio"] is not None
        assert "1" in registro["messaggio"]

    def test_rispondendo_di_si_apre_la_finestra_di_pulizia(self, tmp_path, monkeypatch):
        import wx
        from gui import main_frame as mf

        self._prepara(tmp_path, monkeypatch)
        telaio, registro, _wx = self._telaio(monkeypatch, wx.ID_YES)

        mf.MainFrame._check_backup_on_startup(telaio)

        assert registro["pulizia_aperta"] is True

    def test_rispondendo_di_no_le_date_vengono_aggiornate(self, tmp_path, monkeypatch):
        import time

        import wx
        from gui import main_frame as mf

        antico = self._prepara(tmp_path, monkeypatch)
        telaio, _registro, _wx = self._telaio(monkeypatch, wx.ID_NO)

        mf.MainFrame._check_backup_on_startup(telaio)

        eta_in_giorni = (time.time() - os.path.getmtime(str(antico))) / 86400
        assert eta_in_giorni < 1

    def test_le_cartelle_vuote_spariscono(self, tmp_path, monkeypatch):
        import wx
        from gui import main_frame as mf

        self._prepara(tmp_path, monkeypatch)
        telaio, _registro, _wx = self._telaio(monkeypatch, wx.ID_NO)

        mf.MainFrame._check_backup_on_startup(telaio)

        assert not (tmp_path / "backup" / "2022").exists()
        assert (tmp_path / "backup" / "2026" / "09 Settembre").exists()

    def test_senza_file_vecchi_non_dice_nulla(self, tmp_path, monkeypatch):
        import shutil

        import wx
        from gui import main_frame as mf

        self._prepara(tmp_path, monkeypatch)
        shutil.rmtree(tmp_path / "backup" / "2023")
        telaio, registro, _wx = self._telaio(monkeypatch, wx.ID_NO)

        mf.MainFrame._check_backup_on_startup(telaio)

        assert registro["messaggio"] is None
