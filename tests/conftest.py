import json
import os
import sys

import pytest

# Aggiunge la cartella src al path
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)


@pytest.fixture
def sample_tournament_dict():
    """Carica un torneo reale salvato per i test."""
    # Il file viene cercato dentro l'archivio invece di puntare a una cartella
    # precisa: dalla versione 9.7.0 l'archivio e' ordinato per anno e mese, e
    # un percorso fisso si romperebbe a ogni riordino.
    archivio = os.path.join(os.path.dirname(__file__), "..", "Closed Tournaments")
    atteso = "Tornello - ASCId_Primavera_1.json"
    for radice, _cartelle, files in os.walk(archivio):
        if atteso in files:
            with open(os.path.join(radice, atteso), "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(f"Torneo di prova non trovato nell'archivio: {atteso}")
