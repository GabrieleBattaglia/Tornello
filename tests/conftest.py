import os
import sys
import json
import pytest

# Aggiunge la cartella src al path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)


@pytest.fixture
def sample_tournament_dict():
    """Carica un torneo reale salvato per i test."""
    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "Closed Tournaments",
        "ASCId_Primavera_1 - Giugno 2025",
        "Tornello - ASCId_Primavera_1.json",
    )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
