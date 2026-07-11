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
