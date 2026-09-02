# Tornello, utilita': prepara l'archivio per la distribuzione.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5, modalita' auto).
# 02/09/2026: il lavoro e' passato a crea_archivio_release di GBUtils V93.

"""Comprime la cartella prodotta da PyInstaller in un solo archivio.

Tutto il mestiere sta in GBUtils, cosi' la regola sulle esclusioni e' una
sola per tutti i progetti. Qui restano soltanto i nomi di Tornello.

La versione precedente non escludeva niente: chi seguiva il prontuario e
provava l'eseguibile prima di comprimere si ritrovava nel pacchetto
pubblico i propri tornei, l'archivio giocatori e le impostazioni. Oltre
alle cartelle dei dati dell'utente, che la funzione salta da se', qui si
lasciano fuori i tornei chiusi, le copie di sicurezza, i file che
Tornello scrive accanto all'eseguibile e il database FIDE, che l'utente
si scarica da solo e pesa parecchio.
"""

import sys

from GBUtils import crea_archivio_release

FUORI = [
    "Closed Tournaments/",
    "backup/",
    "Tornello - *.json",
    "Tornello - *.txt",
    "selected_language.json",
    "fide_ratings.db",
]


def main():
    try:
        crea_archivio_release("Tornello", cartella_dist="dist/tornello", escludi=FUORI)
    except (FileNotFoundError, OSError) as e:
        print(f"Archivio non creato: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
