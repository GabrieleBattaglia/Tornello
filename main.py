# Entry point per Tornello v9
import os
import sys
import atexit

# Aggiungi src a sys.path per lo sviluppo locale
try:
    sys._MEIPASS
except AttributeError:
    sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "src"))

from GBUtils import Donazione
from config import BBP_SUBDIR
from cli_adapter import CLIAdapter
from controller import TournamentController

atexit.register(Donazione)

def check_updates():
    try:
        from GBUtils import update_checker, perform_update, enter_escape
        from version import __version__ as current_ver

        print(_("Controllo aggiornamenti..."))
        repo_api = (
            "https://api.github.com/repos/GabrieleBattaglia/Tornello/releases/latest"
        )
        avail, latest_ver, dl_url, changelog = update_checker(current_ver, repo_api)
        if avail:
            if dl_url:
                print(_("\n*** AGGIORNAMENTO DISPONIBILE! ***"))
                print(
                    _("Versione corrente: {curr} | Nuova versione: {latest}").format(
                        curr=current_ver, latest=latest_ver
                    )
                )
                if enter_escape(
                    _(
                        "Vuoi scaricare e installare l'aggiornamento ora? (INVIO per Sì | ESCAPE per ignorare)"
                    )
                ):
                    print(
                        _(
                            "Scaricamento e installazione in corso. Il programma si chiuderà per l'aggiornamento..."
                        )
                    )
                    if perform_update(dl_url, "tornello"):
                        sys.exit(0)
                    else:
                        print(
                            _(
                                "Impossibile avviare l'aggiornamento automatico (la funzione è disponibile solo per la versione compilata)."
                            )
                        )
            else:
                print(_("\n*** AGGIORNAMENTO DISPONIBILE ***"))
                print(
                    _(
                        "E' disponibile la nuova versione {latest_ver}, ma i file di installazione non sono ancora pronti per il download."
                    ).format(latest_ver=latest_ver)
                )
                print(_("Riprova più tardi."))
    except Exception as e_update:
        print(_("Controllo aggiornamenti fallito: {}").format(e_update))


if __name__ == "__main__":
    if not os.path.exists(BBP_SUBDIR):
        try:
            os.makedirs(BBP_SUBDIR)
            print(
                _("Info: Creata sottocartella '{}' per i file di bbpPairings.").format(
                    BBP_SUBDIR
                )
            )
        except OSError as e:
            print(
                _("ATTENZIONE: Impossibile creare la sottocartella '{}': {}").format(
                    BBP_SUBDIR, e
                )
            )
            print(_("bbpPairings potrebbe non funzionare correttamente."))
            sys.exit(1)

    # Controlla aggiornamenti
    check_updates()

    # Avvia controller con CLI adapter
    adapter = CLIAdapter()
    controller = TournamentController(adapter)
    controller.start()
