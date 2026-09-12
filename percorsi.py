# Tornello, i percorsi: dove stanno i file, da sorgente e da eseguibile.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5, UltraCode).
# 12/09/2026: nasce con l'adozione di cartella_applicazione e percorso_risorsa
# di GBUtils, issue 20 e 31 della libreria. Prima le stesse due funzioni
# stavano in src/config.py, che risaliva di una cartella per arrivare qui:
# ogni progetto del parco software aveva la sua copia, e adesso la logica e'
# scritta una volta sola nella libreria condivisa.

"""I percorsi di Tornello.

Questo modulo sta nella radice del progetto, accanto a tornello.py, e non
dentro src: e' quella la cartella a cui i percorsi si riferiscono, cioe' dove
stanno i tornei, il database dei giocatori e le impostazioni, e una funzione
di GBUtils risponde la cartella del modulo che la chiama. Tenerlo qui rende
Tornello uguale agli altri progetti del parco software, che sono piatti e non
hanno questo problema.

Due regole, prese dal memorandum sui percorsi in docs. Cio' che il programma
scrive, cioe' tornei, archivio, database dei giocatori e impostazioni, sta
accanto al programma: accanto all'eseguibile quando e' compilato, accanto ai
sorgenti altrimenti. Cio' che il programma legge soltanto, cioe' i cataloghi
delle traduzioni e il motore di abbinamento bbpPairings, da compilato viaggia
dentro il pacchetto, nella cartella temporanea che PyInstaller apre
all'avvio, e li' va cercato per primo.
"""

import os

from GBUtils import cartella_applicazione
from GBUtils import percorso_risorsa as _percorso_risorsa


def resource_path(relative_path):
    """
    Restituisce il percorso assoluto a una risorsa (sola lettura), funzionante sia in sviluppo
    che per un eseguibile compilato con PyInstaller (anche con la cartella _internal).
    """
    return _percorso_risorsa(relative_path)


def user_data_path(relative_path):
    """
    Restituisce il percorso assoluto a un file di dati utente (scrittura), funzionante sia in sviluppo
    che per un eseguibile compilato con PyInstaller. I file vengono salvati nella cartella
    dell'eseguibile, garantendo la persistenza anche in configurazione onefile.
    La cartella si chiede a ogni chiamata e non una volta all'importazione:
    una costante congelerebbe il valore, mentre cosi' la risposta guarda ogni
    volta se il programma e' compilato, com'e' sempre stato.
    """
    return os.path.join(cartella_applicazione(), relative_path)
