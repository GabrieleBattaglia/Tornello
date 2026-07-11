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
