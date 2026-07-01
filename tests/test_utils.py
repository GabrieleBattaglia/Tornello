import os
import shutil
import tempfile
import pytest
from utils import resolve_and_verify_save_path

def test_resolve_and_verify_save_path_empty():
    path, warning = resolve_and_verify_save_path("", default_fallback="temp_default")
    assert path == "temp_default"
    assert warning is None

def test_resolve_and_verify_save_path_valid():
    with tempfile.TemporaryDirectory() as tmpdir:
        path, warning = resolve_and_verify_save_path(tmpdir, default_fallback="temp_default")
        # should match the absolute path of tmpdir
        assert os.path.abspath(path) == os.path.abspath(tmpdir)
        assert warning is None

def test_resolve_and_verify_save_path_create_nonexistent():
    with tempfile.TemporaryDirectory() as tmpdir:
        target_path = os.path.join(tmpdir, "new_sub_dir")
        assert not os.path.exists(target_path)
        
        path, warning = resolve_and_verify_save_path(target_path, default_fallback="temp_default")
        assert os.path.exists(target_path)
        assert os.path.abspath(path) == os.path.abspath(target_path)
        assert warning is not None
        assert "creata" in warning.lower() or "created" in warning.lower()

def test_resolve_and_verify_save_path_invalid_drive():
    # K: is not present on this system
    invalid_path = "K:\\NonExistentDrive\\TornelloTestReports"
    
    path, warning = resolve_and_verify_save_path(invalid_path, default_fallback="temp_default")
    assert path == "temp_default"
    assert warning is not None
    assert "non è disponibile" in warning.lower() or "not available" in warning.lower()
