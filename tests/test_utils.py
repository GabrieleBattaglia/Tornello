import os
import tempfile

from utils import resolve_and_verify_save_path


def test_resolve_and_verify_save_path_empty():
    path, warning = resolve_and_verify_save_path("", default_fallback="temp_default")
    assert path == "temp_default"
    assert warning is None


def test_resolve_and_verify_save_path_valid():
    with tempfile.TemporaryDirectory() as tmpdir:
        path, warning = resolve_and_verify_save_path(
            tmpdir, default_fallback="temp_default"
        )
        # should match the absolute path of tmpdir
        assert os.path.abspath(path) == os.path.abspath(tmpdir)
        assert warning is None


def test_resolve_and_verify_save_path_create_nonexistent():
    with tempfile.TemporaryDirectory() as tmpdir:
        target_path = os.path.join(tmpdir, "new_sub_dir")
        assert not os.path.exists(target_path)

        path, warning = resolve_and_verify_save_path(
            target_path, default_fallback="temp_default"
        )
        assert os.path.exists(target_path)
        assert os.path.abspath(path) == os.path.abspath(target_path)
        assert warning is not None
        assert "creata" in warning.lower() or "created" in warning.lower()


def test_resolve_and_verify_save_path_invalid_drive():
    # K: is not present on this system
    invalid_path = "K:\\NonExistentDrive\\TornelloTestReports"

    path, warning = resolve_and_verify_save_path(
        invalid_path, default_fallback="temp_default"
    )
    assert path == "temp_default"
    assert warning is not None
    assert "non è disponibile" in warning.lower() or "not available" in warning.lower()


def test_delete_active_tournament_logic():
    # Setup files in a temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # JSON file
        json_file = os.path.join(tmpdir, "Tornello - TestTournament.json")
        with open(json_file, "w", encoding="utf-8") as f:
            f.write('{"name": "TestTournament", "custom_save_path": "custom_dir"}')

        custom_dir = os.path.join(tmpdir, "custom_dir")
        os.makedirs(custom_dir)

        # Reports
        r1 = os.path.join(custom_dir, "Tornello - TestTournament - Classifica.txt")
        r2 = os.path.join(custom_dir, "Tornello - TestTournament - Turno corrente.txt")
        r3 = os.path.join(tmpdir, "Tornello - TestTournament - Calendario.ics")
        other_file = os.path.join(custom_dir, "Tornello - Other - Classifica.txt")

        for p in [r1, r2, r3, other_file]:
            with open(p, "w", encoding="utf-8") as f:
                f.write("content")

        # Now clean up using the same logic as delete_active_tournament
        import json

        with open(json_file, "r", encoding="utf-8") as f_in:
            data = json.load(f_in)

        t_name = data.get("name")
        assert t_name == "TestTournament"

        # remove json
        os.remove(json_file)

        # get paths to clean
        paths_to_clean = [os.path.dirname(json_file)]
        custom_path = data.get("custom_save_path")
        if custom_path:
            resolved_path = os.path.join(tmpdir, custom_path)
            paths_to_clean.append(resolved_path)

        paths_to_clean = list(set([os.path.abspath(p) for p in paths_to_clean if p]))

        from tournament import sanitize_filename

        sanitized_name = sanitize_filename(t_name)
        prefix_to_match = f"Tornello - {sanitized_name}"

        for folder in paths_to_clean:
            if os.path.exists(folder):
                for f_name in os.listdir(folder):
                    if f_name.startswith(prefix_to_match):
                        f_path = os.path.join(folder, f_name)
                        if os.path.isfile(f_path):
                            os.remove(f_path)

        # Assertions
        assert not os.path.exists(json_file)
        assert not os.path.exists(r1)
        assert not os.path.exists(r2)
        assert not os.path.exists(r3)
        assert os.path.exists(other_file)  # Should not be deleted!


class TestCartellaScrivibile:
    """Il controllo dei permessi che Tornello fa all'avvio. Non basta che la
    cartella esista: in Programmi c'e' ma non si puo' scrivere, ed e' li' che
    la prova sul campo si fermava con un codice di errore."""

    def test_una_cartella_normale_e_scrivibile(self, tmp_path):
        from utils import cartella_scrivibile

        assert cartella_scrivibile(str(tmp_path)) is True

    def test_una_cartella_inesistente_non_lo_e(self, tmp_path):
        from utils import cartella_scrivibile

        assert cartella_scrivibile(str(tmp_path / "assente")) is False

    def test_un_percorso_vuoto_non_lo_e(self):
        from utils import cartella_scrivibile

        assert cartella_scrivibile("") is False
        assert cartella_scrivibile(None) is False

    def test_non_lascia_il_file_di_prova(self, tmp_path):
        from utils import cartella_scrivibile

        cartella_scrivibile(str(tmp_path))

        assert list(tmp_path.iterdir()) == []


class TestRitiratiNelRiavvolgimento:
    """Riavvolgendo un turno, il ritiro va annullato solo per chi era ancora in
    gioco in quel turno. Prima veniva azzerato per tutti: un giocatore ritirato
    al secondo turno tornava negli abbinamenti se l'arbitro riavvolgeva al
    settimo, e se ne accorgeva solo leggendo gli accoppiamenti. Rilievo B3."""

    def _giocatore(self, pid, turni):
        return {
            "id": pid,
            "first_name": pid,
            "last_name": pid,
            "points": float(len(turni)),
            "withdrawn": False,
            "results_history": [
                {
                    "round": turno,
                    "opponent_id": "ALTRO",
                    "color": "white",
                    "result": "1-0",
                    "score": 1.0,
                }
                for turno in turni
            ],
        }

    def _torneo(self, tmp_path, monkeypatch):
        import config

        monkeypatch.setattr(config, "user_data_path", lambda p: str(tmp_path / p))

        # Chi ha lasciato presto: ultima partita al turno 1, poi ritirato.
        presto = self._giocatore("PRESTO", [1])
        presto["withdrawn"] = True
        # Chi si ritira proprio nel turno che verra' annullato.
        adesso = self._giocatore("ADESSO", [1, 2, 3])
        adesso["withdrawn"] = True
        # Chi non si e' mai ritirato.
        attivo = self._giocatore("ATTIVO", [1, 2, 3])

        torneo = {
            "name": "Prova rollback",
            "current_round": 3,
            "total_rounds": 5,
            "players": [presto, adesso, attivo],
            "rounds": [
                {"round": numero, "matches": [{"id": numero, "round": numero}]}
                for numero in (1, 2, 3)
            ],
        }
        torneo["players_dict"] = {p["id"]: p for p in torneo["players"]}
        return torneo, presto, adesso, attivo

    def test_chi_si_era_ritirato_prima_resta_ritirato(self, tmp_path, monkeypatch):
        from tournament import rollback_to_previous_round

        torneo, presto, adesso, attivo = self._torneo(tmp_path, monkeypatch)

        assert rollback_to_previous_round(torneo) is True

        assert presto["withdrawn"] is True, "il ritiro del turno 1 non va annullato"
        assert adesso["withdrawn"] is False, (
            "chi giocava nel turno annullato torna in gioco"
        )
        assert attivo["withdrawn"] is False

    def test_l_ultimo_turno_nello_storico(self):
        from tournament import ultimo_turno_nello_storico

        assert ultimo_turno_nello_storico(self._giocatore("X", [1, 2, 7])) == 7
        assert ultimo_turno_nello_storico(self._giocatore("X", [])) == 0
        assert ultimo_turno_nello_storico(None) == 0


class TestScritturaAtomica:
    """Il database dei giocatori e i tornei vengono scritti prima in un file
    temporaneo e poi sostituiti in un colpo solo. Scrivendo direttamente sul
    file definitivo, un arresto a meta' operazione lasciava il vecchio
    contenuto troncato e il nuovo incompleto. Rilievo C1."""

    def test_scrive_il_contenuto(self, tmp_path):
        import json

        from utils import scrivi_json_atomico

        percorso = tmp_path / "dati.json"

        assert scrivi_json_atomico(str(percorso), {"a": 1, "b": [2, 3]}) is True
        with open(percorso, encoding="utf-8") as f:
            assert json.load(f) == {"a": 1, "b": [2, 3]}

    def test_non_lascia_file_temporanei(self, tmp_path):
        from utils import scrivi_json_atomico

        scrivi_json_atomico(str(tmp_path / "dati.json"), {"a": 1})

        assert [f.name for f in tmp_path.iterdir()] == ["dati.json"]

    def test_un_errore_non_distrugge_il_file_esistente(self, tmp_path):
        import json

        import pytest

        from utils import scrivi_json_atomico

        percorso = tmp_path / "dati.json"
        percorso.write_text('{"prezioso": true}', encoding="utf-8")

        # Un insieme non e' serializzabile: la scrittura fallisce a meta'.
        with pytest.raises(TypeError):
            scrivi_json_atomico(str(percorso), {"rotto": {1, 2, 3}})

        with open(percorso, encoding="utf-8") as f:
            assert json.load(f) == {"prezioso": True}
        assert [f.name for f in tmp_path.iterdir()] == ["dati.json"]

    def test_crea_la_cartella_se_manca(self, tmp_path):
        from utils import scrivi_json_atomico

        percorso = tmp_path / "nuova" / "dati.json"

        assert scrivi_json_atomico(str(percorso), {"a": 1}) is True
        assert percorso.exists()
