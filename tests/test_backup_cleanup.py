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


def test_senza_cestino_il_file_resta(tmp_path, monkeypatch):
    """Su un disco senza cestino, per esempio una cartella di rete, il file
    resta dov'e' e la risposta e' falso: la Shell non viene nemmeno
    chiamata, e non puo' chiedere di cancellarlo per sempre."""
    import pytest

    import utils

    if sys.platform != "win32":
        pytest.skip("il cestino di Windows c'e' solo su Windows")
    percorso = tmp_path / "copia.json"
    percorso.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(utils, "cestino_disponibile", lambda p: False)

    assert utils.delete_file_to_trash(str(percorso)) is False
    assert percorso.read_text(encoding="utf-8") == "{}"


def test_il_disco_delle_prove_ha_il_cestino(tmp_path):
    """La domanda alla Shell, in sola lettura, sul disco della cartella
    temporanea, che il cestino ce l'ha."""
    import pytest

    import utils

    if sys.platform != "win32":
        pytest.skip("il cestino di Windows c'e' solo su Windows")
    assert utils.cestino_disponibile(str(tmp_path)) is True


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

    def _telaio(self, monkeypatch, risposta, impostazioni=None):
        import wx

        from gui import main_frame as mf

        registro = {"messaggio": None, "pulizia_aperta": False, "seleziona": None}

        class DialogoFinto:
            def __init__(self, parent, titolo, messaggio, style=None, settings=None):
                registro["messaggio"] = messaggio

            def ShowModal(self):
                return risposta

            def Destroy(self):
                pass

        monkeypatch.setattr(mf, "AccessibleMsgDialog", DialogoFinto)

        class TelaioFinto:
            def __init__(self):
                self.settings = {} if impostazioni is None else impostazioni

            def on_backup_cleanup(self, event, seleziona=None):
                registro["pulizia_aperta"] = True
                registro["seleziona"] = seleziona

        return TelaioFinto(), registro, wx

    def test_trova_i_backup_vecchi_nelle_sottocartelle(self, tmp_path, monkeypatch):
        import wx

        from gui import main_frame as mf

        self._prepara(tmp_path, monkeypatch)
        telaio, registro, _wx = self._telaio(monkeypatch, wx.ID_NO)

        mf.MainFrame._check_backup_on_startup(telaio)

        assert registro["messaggio"] is not None
        assert "1" in registro["messaggio"]

    def test_con_una_copia_sola_il_messaggio_e_al_singolare(self, tmp_path, monkeypatch):
        """Fino alla 10.13.27 diceva Sono stati individuati 1 file di backup
        piu' vecchi di 18 mesi."""
        import wx

        from gui import main_frame as mf

        self._prepara(tmp_path, monkeypatch)
        telaio, registro, _wx = self._telaio(monkeypatch, wx.ID_NO)

        mf.MainFrame._check_backup_on_startup(telaio)

        messaggio = registro["messaggio"]
        assert messaggio.startswith("È stato individuato un file di backup più vecchio di 18 mesi.\n")
        assert "La copia più vecchia di 18 mesi sarà già selezionata." in messaggio
        assert messaggio.endswith("e il file resta com'è.")
        assert "individuati" not in messaggio and "vecchi " not in messaggio

    def test_con_due_copie_il_messaggio_e_al_plurale(self, tmp_path, monkeypatch):
        import time

        import wx

        from gui import main_frame as mf

        antico = self._prepara(tmp_path, monkeypatch)
        secondo = antico.with_name("Tornello - Antico_chiusura_torneo.json")
        secondo.write_text("{}", encoding="utf-8")
        quando = time.time() - 900 * 86400
        os.utime(secondo, (quando, quando))
        telaio, registro, _wx = self._telaio(monkeypatch, wx.ID_NO)

        mf.MainFrame._check_backup_on_startup(telaio)

        messaggio = registro["messaggio"]
        assert messaggio.startswith("Sono stati individuati 2 file di backup più vecchi di 18 mesi.\n")
        assert "Le copie più vecchie di 18 mesi saranno già selezionate." in messaggio
        assert messaggio.endswith("e i file restano come sono.")

    def test_rispondendo_di_si_apre_la_finestra_di_pulizia(self, tmp_path, monkeypatch):
        """Dalla 10.9.0 la finestra e' quella delle copie di sicurezza, e le
        copie vecchie ci arrivano gia' selezionate: il pulsante Elimina
        consigliati non c'e' piu'."""
        import wx

        from gui import main_frame as mf

        antico = self._prepara(tmp_path, monkeypatch)
        telaio, registro, _wx = self._telaio(monkeypatch, wx.ID_YES)

        mf.MainFrame._check_backup_on_startup(telaio)

        assert registro["pulizia_aperta"] is True
        assert registro["seleziona"] == [str(antico)]

    def test_rispondendo_di_no_il_rinvio_va_nelle_impostazioni(
        self, tmp_path, monkeypatch
    ):
        """Fino alla 10.8.10 il No portava a oggi la data di modifica dei
        file vecchi, e le copie perdevano la loro eta'. Adesso i file restano
        come sono, e nelle impostazioni, salvate su disco, resta la data fino
        alla quale l'avviso non torna."""
        import time
        from datetime import datetime, timedelta

        import wx

        from gui import main_frame as mf
        from gui import settings as modulo_impostazioni

        antico = self._prepara(tmp_path, monkeypatch)
        assert modulo_impostazioni.SETTINGS_FILE.startswith(str(tmp_path))
        telaio, _registro, _wx = self._telaio(monkeypatch, wx.ID_NO)

        mf.MainFrame._check_backup_on_startup(telaio)

        eta_in_giorni = (time.time() - os.path.getmtime(str(antico))) / 86400
        assert eta_in_giorni > 899
        rinvio = datetime.strptime(telaio.settings[mf.RINVIO_AVVISO_BACKUP], "%Y-%m-%d")
        assert rinvio > datetime.now() + timedelta(days=540)
        with open(modulo_impostazioni.SETTINGS_FILE, encoding="utf-8") as f:
            salvate = f.read()
        assert telaio.settings[mf.RINVIO_AVVISO_BACKUP] in salvate

    def test_il_no_non_cambia_la_lingua_del_programma(self, tmp_path, monkeypatch):
        """Chi non ha mai salvato le Preferenze ha le impostazioni di
        fabbrica, con la lingua italiana, mentre selected_language.json ha la
        lingua del sistema, scritta da config al primo avvio. Salvare il
        rinvio con save_settings riportava all'italiano un programma inglese:
        sul disco va la sola chiave del rinvio."""
        import json

        import wx

        from gui import main_frame as mf
        from gui import settings as modulo_impostazioni

        self._prepara(tmp_path, monkeypatch)
        lingua = tmp_path / "selected_language.json"
        lingua.write_text(
            json.dumps({"language_code": "en", "available_languages": ["en", "it"]}),
            encoding="utf-8",
        )
        assert not os.path.exists(modulo_impostazioni.SETTINGS_FILE)
        telaio, _registro, _wx = self._telaio(
            monkeypatch, wx.ID_NO, modulo_impostazioni.load_settings()
        )
        assert telaio.settings["language"] == "it"

        mf.MainFrame._check_backup_on_startup(telaio)

        assert json.loads(lingua.read_text(encoding="utf-8"))["language_code"] == "en"
        with open(modulo_impostazioni.SETTINGS_FILE, encoding="utf-8") as f:
            salvate = json.load(f)
        assert salvate == {
            mf.RINVIO_AVVISO_BACKUP: telaio.settings[mf.RINVIO_AVVISO_BACKUP]
        }

    def test_le_preferenze_salvate_dopo_tengono_il_rinvio(self, tmp_path, monkeypatch, app_grafica):
        """Le Preferenze conoscono solo le chiavi che mostrano: salvandole,
        il rinvio spariva dal file, e l'avviso tornava al primo avvio. Dalla
        10.13.25 le Preferenze chiedono a wx dove sta il fuoco, e serve
        l'applicazione."""
        import json

        import wx

        from gui import main_frame as mf
        from gui import settings as modulo_impostazioni

        self._prepara(tmp_path, monkeypatch)
        telaio, _registro, _wx = self._telaio(
            monkeypatch, wx.ID_NO, modulo_impostazioni.load_settings()
        )
        mf.MainFrame._check_backup_on_startup(telaio)
        rinvio = telaio.settings[mf.RINVIO_AVVISO_BACKUP]

        scelte = dict(modulo_impostazioni.DEFAULT_SETTINGS, volume=80)

        class PreferenzeFinte:
            def __init__(self, parent, settings):
                pass

            def ShowModal(self):
                return wx.ID_OK

            def get_settings(self):
                return dict(scelte)

            def Destroy(self):
                pass

        monkeypatch.setattr(mf, "VisualSettingsDialog", PreferenzeFinte)
        telaio.apply_theme = lambda: None
        telaio.set_status = lambda testo: None

        mf.MainFrame.on_preferences(telaio, None)

        assert telaio.settings[mf.RINVIO_AVVISO_BACKUP] == rinvio
        assert telaio.settings["volume"] == 80
        with open(modulo_impostazioni.SETTINGS_FILE, encoding="utf-8") as f:
            salvate = json.load(f)
        assert salvate[mf.RINVIO_AVVISO_BACKUP] == rinvio
        assert salvate["volume"] == 80

    def test_un_file_di_impostazioni_illeggibile_non_si_riscrive(self, tmp_path):
        """Riscrivere un file che non si legge ne perderebbe il contenuto: il
        rinvio non si salva, e l'avviso torna al prossimo avvio."""
        from gui import settings as modulo_impostazioni

        assert modulo_impostazioni.SETTINGS_FILE.startswith(str(tmp_path))
        with open(modulo_impostazioni.SETTINGS_FILE, "w", encoding="utf-8") as f:
            f.write("{rovinato")

        assert modulo_impostazioni.salva_impostazione("chiave", "valore") is False

        with open(modulo_impostazioni.SETTINGS_FILE, encoding="utf-8") as f:
            assert f.read() == "{rovinato"

    def test_durante_il_rinvio_l_avviso_tace(self, tmp_path, monkeypatch):
        import wx

        from gui import main_frame as mf

        self._prepara(tmp_path, monkeypatch)
        telaio, registro, _wx = self._telaio(
            monkeypatch, wx.ID_NO, {mf.RINVIO_AVVISO_BACKUP: "2999-01-01"}
        )

        mf.MainFrame._check_backup_on_startup(telaio)

        assert registro["messaggio"] is None

    def test_un_rinvio_scaduto_o_illeggibile_non_ferma_l_avviso(
        self, tmp_path, monkeypatch
    ):
        import wx

        from gui import main_frame as mf

        self._prepara(tmp_path, monkeypatch)
        for rinvio in ("2020-01-01", "domani"):
            telaio, registro, _wx = self._telaio(
                monkeypatch, wx.ID_YES, {mf.RINVIO_AVVISO_BACKUP: rinvio}
            )

            mf.MainFrame._check_backup_on_startup(telaio)

            assert registro["messaggio"] is not None, rinvio

    def test_conta_la_data_nel_nome_non_quella_di_modifica(
        self, tmp_path, monkeypatch
    ):
        """Una copia fatta ieri di un file vecchio ha la data di modifica
        vecchia, perche' shutil.copy2 la conserva: non e' da pulire. Una
        copia nata tre anni fa lo e', anche se qualcuno ne ha cambiato la
        data di modifica."""
        import shutil
        import time
        from datetime import datetime, timedelta

        import wx

        from gui import main_frame as mf

        self._prepara(tmp_path, monkeypatch)
        shutil.rmtree(tmp_path / "backup" / "2023")
        recente = tmp_path / "backup" / "2026" / "09 Settembre"
        ieri = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d_%H%M%S")
        di_ieri = recente / f"Tornello - Players_db_chiusura_db_{ieri}.json"
        di_ieri.write_text("{}", encoding="utf-8")
        quando = time.time() - 900 * 86400
        os.utime(di_ieri, (quando, quando))
        telaio, registro, _wx = self._telaio(monkeypatch, wx.ID_NO)

        mf.MainFrame._check_backup_on_startup(telaio)

        assert registro["messaggio"] is None

        vecchia = tmp_path / "backup" / "2023" / "05 Maggio"
        vecchia.mkdir(parents=True)
        (vecchia / "Tornello - Antico_pre_rollback_20230510_090000.json").write_text(
            "{}", encoding="utf-8"
        )

        mf.MainFrame._check_backup_on_startup(telaio)

        assert registro["messaggio"] is not None

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


class TestSelezioneMultipla:
    """La finestra di pulizia permette di prendere piu' file in un colpo solo:
    Ctrl+A, shift con le frecce, shift con Inizio e Fine. Prima si poteva
    eliminare soltanto la riga con il fuoco, e per svuotare un mese di backup
    servivano decine di conferme. Richiesta di Gabriele del 2026-09-05."""

    def _finestra(self, tmp_path, monkeypatch, app_grafica, quanti=6):
        import config

        monkeypatch.setattr(config, "user_data_path", lambda p: str(tmp_path / p))
        mese = tmp_path / "backup" / "2026" / "09 Settembre"
        mese.mkdir(parents=True)
        for numero in range(quanti):
            (mese / f"Tornello - Prova{numero}_pre_prova.json").write_text(
                "{}", encoding="utf-8"
            )

        import wx

        from gui.dialogs.backup_cleanup_dialog import BackupCleanupDialog

        telaio = wx.Frame(None)
        return BackupCleanupDialog(telaio, {}), telaio, app_grafica

    def _svuota_selezione(self, finestra):
        for indice in finestra.indici_selezionati():
            finestra.list_ctrl.Select(indice, False)

    class _Tasto:
        """Un evento da tastiera con il minimo che serve al gestore."""

        def __init__(self, codice, ctrl=False, shift=False):
            self.codice = codice
            self.ctrl = ctrl
            self.shift = shift
            self.saltato = False

        def GetKeyCode(self):
            return self.codice

        def ControlDown(self):
            return self.ctrl

        def ShiftDown(self):
            return self.shift

        def Skip(self):
            self.saltato = True

    def test_la_lista_non_e_a_selezione_singola(
        self, tmp_path, monkeypatch, app_grafica
    ):
        import wx

        finestra, telaio, _app = self._finestra(tmp_path, monkeypatch, app_grafica)
        try:
            stile = finestra.list_ctrl.GetWindowStyleFlag()
            assert not stile & wx.LC_SINGLE_SEL
        finally:
            finestra.Destroy()
            telaio.Destroy()

    def test_ctrl_a_prende_tutto(self, tmp_path, monkeypatch, app_grafica):
        finestra, telaio, _app = self._finestra(tmp_path, monkeypatch, app_grafica)
        try:
            finestra.on_list_key_down(self._Tasto(ord("A"), ctrl=True))

            assert len(finestra.indici_selezionati()) == 6
        finally:
            finestra.Destroy()
            telaio.Destroy()

    def test_shift_fine_estende_fino_in_fondo(self, tmp_path, monkeypatch, app_grafica):
        import wx

        finestra, telaio, _app = self._finestra(tmp_path, monkeypatch, app_grafica)
        try:
            self._svuota_selezione(finestra)
            finestra.list_ctrl.Focus(2)

            finestra.on_list_key_down(self._Tasto(wx.WXK_END, shift=True))

            assert finestra.indici_selezionati() == [2, 3, 4, 5]
        finally:
            finestra.Destroy()
            telaio.Destroy()

    def test_shift_inizio_estende_fino_in_cima(
        self, tmp_path, monkeypatch, app_grafica
    ):
        import wx

        finestra, telaio, _app = self._finestra(tmp_path, monkeypatch, app_grafica)
        try:
            self._svuota_selezione(finestra)
            finestra.list_ctrl.Focus(3)

            finestra.on_list_key_down(self._Tasto(wx.WXK_HOME, shift=True))

            assert finestra.indici_selezionati() == [0, 1, 2, 3]
        finally:
            finestra.Destroy()
            telaio.Destroy()

    def test_gli_altri_tasti_restano_alla_lista(
        self, tmp_path, monkeypatch, app_grafica
    ):
        """Le frecce con shift le gestisce gia' la lista da sola: il gestore
        non deve mangiarsele."""
        finestra, telaio, _app = self._finestra(tmp_path, monkeypatch, app_grafica)
        try:
            evento = self._Tasto(ord("Z"))

            finestra.on_list_key_down(evento)

            assert evento.saltato is True
        finally:
            finestra.Destroy()
            telaio.Destroy()

    def test_elimina_tutti_i_file_selezionati(self, tmp_path, monkeypatch, app_grafica):
        import os

        from gui.dialogs import backup_cleanup_dialog as modulo

        registro = {}

        class DialogoFinto:
            def __init__(self, parent, titolo, messaggio, style=None, settings=None):
                registro["messaggio"] = messaggio

            def ShowModal(self):
                import wx

                return wx.ID_YES

            def Destroy(self):
                pass

        monkeypatch.setattr(modulo, "AccessibleMsgDialog", DialogoFinto)
        finestra, telaio, _app = self._finestra(tmp_path, monkeypatch, app_grafica)
        try:
            self._svuota_selezione(finestra)
            for indice in (0, 1, 2):
                finestra.list_ctrl.Select(indice, True)

            finestra.on_delete_selected(None)

            assert "3" in registro["messaggio"]
            assert finestra.list_ctrl.GetItemCount() == 3
            rimasti = sum(
                len(files) for _r, _d, files in os.walk(str(tmp_path / "backup"))
            )
            assert rimasti == 3
            # Il fuoco non deve restare nel vuoto dopo la cancellazione.
            assert finestra.list_ctrl.GetFocusedItem() == 0
        finally:
            finestra.Destroy()
            telaio.Destroy()


class TestDataDellaCopia:
    """L'eta' di una copia di sicurezza si legge dalla data che
    create_backup scrive nel nome. La data di modifica e' quella
    dell'originale, perche' shutil.copy2 la conserva: le copie di chiusura
    del database fatte il 23 settembre 2026 risultavano del 13 (issue 39)."""

    def _copia(self, cartella, nome, giorni_fa=0):
        import time

        cartella.mkdir(parents=True, exist_ok=True)
        percorso = cartella / nome
        percorso.write_text("{}", encoding="utf-8")
        if giorni_fa:
            quando = time.time() - giorni_fa * 86400
            os.utime(percorso, (quando, quando))
        return percorso

    def test_la_data_nel_nome_prevale_su_quella_di_modifica(self, tmp_path):
        from utils import data_della_copia

        copia = self._copia(
            tmp_path, "Tornello - Players_db_chiusura_db_20250101_120000.json"
        )

        assert data_della_copia(str(copia)) == datetime(2025, 1, 1, 12, 0, 0)

    def test_il_suffisso_delle_copie_nate_nello_stesso_secondo(self, tmp_path):
        from utils import data_della_copia

        copia = self._copia(
            tmp_path, "Tornello - Autunneo2_chiusura_torneo_20260923_160512_2.json"
        )

        assert data_della_copia(str(copia)) == datetime(2026, 9, 23, 16, 5, 12)

    def test_senza_data_nel_nome_si_ripiega_sulla_modifica(self, tmp_path):
        from utils import data_della_copia

        senza = self._copia(tmp_path, "Tornello - Vecchio.json", giorni_fa=100)
        impossibile = self._copia(
            tmp_path, "Tornello - Rotto_pre_rollback_20261399_250000.json", giorni_fa=100
        )

        for percorso in (senza, impossibile):
            attesa = datetime.fromtimestamp(os.path.getmtime(str(percorso)))
            assert data_della_copia(str(percorso)) == attesa

    def test_l_elenco_usa_la_data_del_nome(self, tmp_path):
        from datetime import timedelta

        from utils import elenca_file_di_backup

        mese = tmp_path / "2026" / "09 Settembre"
        oggi = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._copia(mese, f"Tornello - Players_db_chiusura_db_{oggi}.json", giorni_fa=900)
        self._copia(mese, "Tornello - Antico_pre_rollback_20200101_080000.json")
        limite = datetime.now() - timedelta(days=548)

        tutti, vecchi = elenca_file_di_backup(str(tmp_path), limite)

        assert [f["name"] for f in vecchi] == [
            "Tornello - Antico_pre_rollback_20200101_080000.json"
        ]
        assert tutti[0]["data"] == datetime(2020, 1, 1, 8, 0, 0)

    def test_l_indicatore_bk_usa_la_data_del_nome(self, tmp_path):
        from gui import main_frame as mf

        mese = tmp_path / "backup" / "2026" / "09 Settembre"
        self._copia(mese, "Tornello - Players_db_chiusura_db_20260923_101500.json", giorni_fa=400)

        assert mf.MainFrame._data_backup_piu_vecchio() == datetime(2026, 9, 23, 10, 15, 0)

    def test_la_finestra_mostra_la_data_della_copia(self, tmp_path, app_grafica):
        """Dalla 10.9.0 la data e ora e' la prima colonna della finestra
        Copie di sicurezza, e il momento, qui sconosciuto, la seconda."""
        import wx

        from gui.dialogs.backup_cleanup_dialog import BackupCleanupDialog

        mese = tmp_path / "backup" / "2025" / "01 Gennaio"
        self._copia(mese, "Tornello - Prova_pre_prova_20250101_120000.json")
        telaio = wx.Frame(None)
        finestra = BackupCleanupDialog(telaio, {})
        try:
            assert finestra.list_ctrl.GetItemText(0, 0) == "2025-01-01 12:00:00"
            assert finestra.list_ctrl.GetItemText(0, 1) == "momento sconosciuto"
        finally:
            finestra.Destroy()
            telaio.Destroy()


class TestCopieMaiSovrascritte:
    """Due copie dello stesso file e dello stesso contesto nello stesso
    secondo avevano lo stesso nome, e la seconda cancellava la prima. Succedeva
    alle due pre_finalize_db della console. Dalla 10.8.11 la seconda prende il
    suffisso _2, la terza _3."""

    def test_la_stessa_copia_nello_stesso_secondo_prende_un_suffisso(
        self, tmp_path, monkeypatch
    ):
        import types
        from datetime import datetime as vera_datetime

        import utils

        class Fermo(vera_datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 9, 25, 10, 0, 0)

        monkeypatch.setattr(utils, "datetime", types.SimpleNamespace(datetime=Fermo))
        origine = tmp_path / "Tornello - Prova.json"
        for contenuto in ("uno", "due", "tre"):
            origine.write_text(contenuto, encoding="utf-8")
            assert utils.create_backup(str(origine), "pre_prova") is True

        cartella = utils.cartella_per_data(
            str(tmp_path / "backup"), Fermo.now(), crea=False
        )
        base = "Tornello - Prova_pre_prova_20260925_100000"
        attese = {
            f"{base}.json": "uno",
            f"{base}_2.json": "due",
            f"{base}_3.json": "tre",
        }
        assert sorted(os.listdir(cartella)) == sorted(attese)
        for nome, contenuto in attese.items():
            with open(os.path.join(cartella, nome), encoding="utf-8") as f:
                assert f.read() == contenuto
        assert utils.data_della_copia(os.path.join(cartella, f"{base}_3.json")) == Fermo.now()


class TestAperturaDentroBackup:
    """Apri torneo su una copia di sicurezza la rendeva il file attivo: ogni
    salvataggio la modificava, e riscriveva i report del torneo vero con lo
    stato vecchio. Dalla 10.8.12 Tornello la rifiuta e spiega perche'."""

    def test_riconosce_i_file_dentro_la_cartella(self, tmp_path):
        from utils import dentro_la_cartella

        backup = tmp_path / "backup"
        dentro = backup / "2026" / "09 Settembre" / "Tornello - X_chiusura_torneo_20260923_160512.json"
        dentro.parent.mkdir(parents=True)
        dentro.write_text("{}", encoding="utf-8")
        vicina = tmp_path / "backup2" / "Tornello - X.json"
        vicina.parent.mkdir()
        vicina.write_text("{}", encoding="utf-8")

        assert dentro_la_cartella(str(dentro), str(backup)) is True
        assert dentro_la_cartella(str(dentro).upper(), str(backup)) is True
        assert dentro_la_cartella(str(tmp_path / "Tornello - X.json"), str(backup)) is False
        assert dentro_la_cartella(str(vicina), str(backup)) is False
        assert dentro_la_cartella(str(backup), str(backup)) is False
        assert dentro_la_cartella("", str(backup)) is False

    def _apri(self, monkeypatch, scelto, risposta=None):
        import types

        import wx

        import utils
        from gui import main_frame as mf

        registro = {"messaggio": None, "caricato": None, "suoni": [], "finestra": None, "stile": None}
        if risposta is None:
            risposta = wx.ID_NO

        class SceltaFinta:
            def __init__(self, *args, **kwargs):
                pass

            def ShowModal(self):
                return wx.ID_OK

            def GetPath(self):
                return scelto

            def Destroy(self):
                pass

        class DialogoFinto:
            def __init__(self, parent, titolo, messaggio, style=None, settings=None):
                registro["messaggio"] = messaggio
                registro["stile"] = style

            def ShowModal(self):
                return risposta

            def Destroy(self):
                pass

        monkeypatch.setattr(mf.wx, "FileDialog", SceltaFinta)
        monkeypatch.setattr(mf, "AccessibleMsgDialog", DialogoFinto)
        monkeypatch.setattr(utils, "play_sound", lambda nome, *a, **k: registro["suoni"].append(nome))
        telaio = types.SimpleNamespace(
            settings={},
            load_tournament=lambda percorso, **opzioni: registro.update(caricato=percorso),
            on_backup_cleanup=lambda evento, seleziona=None: registro.update(finestra=seleziona),
            _e_il_torneo_aperto=lambda percorso: False,
        )
        mf.MainFrame.on_open_tournament(telaio, None)
        return registro

    def test_una_copia_di_sicurezza_non_si_apre(self, tmp_path, monkeypatch):
        copia = tmp_path / "backup" / "2026" / "09 Settembre" / "Tornello - X_chiusura_torneo_20260923_160512.json"
        copia.parent.mkdir(parents=True)
        copia.write_text("{}", encoding="utf-8")

        import wx

        registro = self._apri(monkeypatch, str(copia))

        assert registro["caricato"] is None
        assert copia.name in registro["messaggio"]
        assert registro["suoni"] == ["errore"]
        assert copia.read_text(encoding="utf-8") == "{}"
        assert registro["finestra"] is None
        # Una domanda con Si' e No, dove ESC vale No: dalla 10.13.23 lo fa
        # AccessibleMsgDialog in tutte le domande, e la prova sta in
        # test_comandi_delle_finestre.
        assert registro["stile"] == wx.YES_NO

    def test_col_si_si_apre_la_finestra_delle_copie(self, tmp_path, monkeypatch):
        """Dalla 10.10.0 il rifiuto propone la finestra delle copie di
        sicurezza, con la copia scelta gia' selezionata."""
        import wx

        copia = tmp_path / "backup" / "2026" / "09 Settembre" / "Tornello - X_chiusura_torneo_20260923_160512.json"
        copia.parent.mkdir(parents=True)
        copia.write_text("{}", encoding="utf-8")

        registro = self._apri(monkeypatch, str(copia), wx.ID_YES)

        assert registro["caricato"] is None
        assert registro["finestra"] == [str(copia)]
        assert "finestra delle copie di sicurezza" in registro["messaggio"]

    def test_un_torneo_fuori_dalla_cartella_si_apre(self, tmp_path, monkeypatch):
        torneo = tmp_path / "Tornello - X.json"
        torneo.write_text("{}", encoding="utf-8")

        registro = self._apri(monkeypatch, str(torneo))

        assert registro["caricato"] == str(torneo)
        assert registro["messaggio"] is None
