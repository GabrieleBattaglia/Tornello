"""La guardia del cestino, dall'8 novembre 2026.

Fino ad allora tre prove mandavano file veri nel cestino di Windows, a ogni
corsa della suite, e nel cestino di Gabriele se ne erano accumulate
migliaia. La guardia sta in conftest.py, fixture nessun_cestino_vero, al
punto piu' in basso: la chiamata alla Shell di Windows, SHFileOperationW, e
send2trash. Queste prove verificano che una prova che ci arriva cada, con il
nome del file che voleva mandarci, anche quando qualcuno ingoia l'eccezione,
che il file resti dov'e', e che il cestino finto, la fixture cestino_finto,
continui a valere al posto di delete_file_to_trash.
Prima di chiamare davvero delete_file_to_trash, ogni prova controlla che al
posto della Shell ci sia la guardia: se un giorno la guardia si rompesse, la
prova fallirebbe senza mandare niente nel cestino.
"""

import contextlib
import re
import sys
import types
from types import SimpleNamespace

import pytest
from conftest import metti_la_guardia_del_cestino

solo_windows = pytest.mark.skipif(sys.platform != "win32", reason="il cestino di Windows c'e' solo su Windows")


def _sorvegliato(funzione):
    return getattr(funzione, "guardia_del_cestino", False)


def _shell():
    import ctypes

    return ctypes.windll.shell32.SHFileOperationW


def _copia(tmp_path):
    percorso = tmp_path / "Tornello - Prova_pre_prova.json"
    percorso.write_text("{}", encoding="utf-8")
    return percorso


@solo_windows
class TestLaGuardiaScatta:
    def test_la_shell_e_sorvegliata(self, nessun_cestino_vero):
        assert _sorvegliato(_shell())

    def test_una_prova_che_arriva_al_cestino_cade(self, nessun_cestino_vero, tmp_path):
        import utils

        percorso = _copia(tmp_path)
        assert _sorvegliato(_shell())
        with pytest.raises(pytest.fail.Exception, match="La prova ha raggiunto il cestino di Windows, con SHFileOperationW") as caduta:
            utils.delete_file_to_trash(str(percorso))
        assert f"voleva mandarci {percorso}." in str(caduta.value)
        assert percorso.read_text(encoding="utf-8") == "{}"
        assert len(nessun_cestino_vero.chiamate) == 1
        nessun_cestino_vero.chiamate.clear()

    def test_una_chiamata_ingoiata_fa_cadere_la_prova_alla_fine(self, nessun_cestino_vero, tmp_path):
        # Come fa wx con l'errore di un gestore di eventi: lo stampa e va
        # avanti. La prova non vede l'eccezione, ma la guardia l'ha annotata.
        import utils

        percorso = _copia(tmp_path)
        assert _sorvegliato(_shell())
        with contextlib.suppress(BaseException):
            utils.delete_file_to_trash(str(percorso))
        assert percorso.exists()
        with pytest.raises(pytest.fail.Exception, match=re.escape(str(percorso))):
            nessun_cestino_vero.verifica(SimpleNamespace(failed=False))
        with pytest.raises(pytest.fail.Exception):
            nessun_cestino_vero.verifica(None)
        # Se la prova e' gia' fallita per quella chiamata, non si ripete.
        nessun_cestino_vero.verifica(SimpleNamespace(failed=True))
        nessun_cestino_vero.chiamate.clear()


class TestSend2trash:
    def test_fuori_da_windows_si_ferma_send2trash(self, nessun_cestino_vero, monkeypatch, tmp_path):
        """Fuori da Windows delete_file_to_trash chiama send2trash, che qui
        non e' installato: al suo posto c'e' un modulo finto, e la guardia lo
        sorveglia come farebbe con quello vero."""
        import utils

        def vero(percorso):
            raise AssertionError(f"send2trash raggiunto senza la guardia: {percorso}")

        finto = types.ModuleType("send2trash")
        finto.send2trash = vero
        monkeypatch.setitem(sys.modules, "send2trash", finto)
        metti_la_guardia_del_cestino(monkeypatch, nessun_cestino_vero)
        assert _sorvegliato(finto.send2trash)
        percorso = _copia(tmp_path)
        with monkeypatch.context() as altrove:
            altrove.setattr(sys, "platform", "linux")
            with pytest.raises(pytest.fail.Exception, match="La prova ha raggiunto il cestino di Windows, con send2trash") as caduta:
                utils.delete_file_to_trash(str(percorso))
        assert f"voleva mandarci {percorso}." in str(caduta.value)
        assert percorso.read_text(encoding="utf-8") == "{}"
        nessun_cestino_vero.chiamate.clear()


class TestIlCestinoFinto:
    def test_vale_al_posto_di_delete_file_to_trash(self, cestino_finto, nessun_cestino_vero, tmp_path):
        """La guardia sta piu' in basso: il cestino finto, che prende il
        posto di delete_file_to_trash in ogni modulo che se l'e' importata,
        non la raggiunge."""
        import copie_di_sicurezza
        import utils
        from gui.dialogs import backup_cleanup_dialog

        assert utils.delete_file_to_trash is cestino_finto
        assert copie_di_sicurezza.delete_file_to_trash is cestino_finto
        assert backup_cleanup_dialog.delete_file_to_trash is cestino_finto
        percorso = _copia(tmp_path)

        assert utils.delete_file_to_trash(str(percorso), finestra=7) is True

        assert cestino_finto.ricevuti == [str(percorso)]
        assert cestino_finto.finestre == [7]
        assert not percorso.exists()
        assert (tmp_path / "cestino" / f"0_{percorso.name}").read_text(encoding="utf-8") == "{}"
        assert nessun_cestino_vero.chiamate == []
