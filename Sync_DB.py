import os
import sys

# Inizializzazione corretta dell'ambiente, come in Players_DB.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

try:
    from GBUtils import polipo
except ImportError:
    print("ATTENZIONE: Libreria GBUtils non trovata. Impossibile avviare il tool.")
    print(
        "Assicurati che la cartella GBUtils sia nel PYTHONPATH o nella stessa directory padre."
    )
    sys.exit(1)

# Configurazione multilingua
lingua_rilevata, _ = polipo(source_language="it")
import builtins

builtins._ = _

from config import *
from db_players import sincronizza_db_personale, aggiorna_db_fide_locale
from utils import enter_escape


def main():
    print(_("\n--- Sincronizzatore Database Tornello ---"))
    print(_("Questo tool confronta il tuo database giocatori personale"))
    print(_("con l'ultimo database FIDE scaricato e propone aggiornamenti.\n"))

    if not os.path.exists(FIDE_DB_LOCAL_FILE):
        print(
            _("Il database FIDE locale ({}) non è presente.").format(FIDE_DB_LOCAL_FILE)
        )
        if enter_escape(
            _(
                "Vuoi scaricarlo ora da FIDE.com? (Richiede alcuni minuti) (INVIO|ESCAPE)"
            )
        ):
            if not aggiorna_db_fide_locale():
                print(
                    _("Scaricamento annullato o fallito. Sincronizzazione impossibile.")
                )
                input(_("\nPremi Invio per uscire..."))
                sys.exit(1)
        else:
            print(_("Sincronizzazione impossibile senza il database FIDE."))
            input(_("\nPremi Invio per uscire..."))
            sys.exit(1)

    # Esegue la funzione importata direttamente dal core di Tornello
    sincronizza_db_personale()

    print(_("\nOperazioni completate."))
    input(_("Premi Invio per uscire dal tool di sincronizzazione..."))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(_("\nOperazione interrotta dall'utente."))
        sys.exit(0)
