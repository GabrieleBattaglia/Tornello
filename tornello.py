# ruff: noqa: E402
# Entry point per Tornello v9
import os
import sys
import atexit
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

def install_excepthook():
    def custom_excepthook(exctype, value, traceback_obj):
        import traceback
        from datetime import datetime
        
        err_msg = "".join(traceback.format_exception(exctype, value, traceback_obj))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"=== UNHANDLED EXCEPTION {timestamp} ===\n{err_msg}\n"
        
        try:
            with open("error.log", "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception:
            pass
            
        try:
            import wx
            if wx.GetApp():
                wx.MessageBox(
                    f"Si è verificato un errore imprevisto.\n\nDettagli:\n{value}\n\nI dettagli completi sono stati salvati in error.log.",
                    "Errore Imprevisto",
                    wx.ICON_ERROR | wx.OK
                )
        except Exception:
            pass
            
        sys.__excepthook__(exctype, value, traceback_obj)
        
    sys.excepthook = custom_excepthook

install_excepthook()

# Aggiungi src a sys.path per lo sviluppo locale
try:
    sys._MEIPASS
except AttributeError:
    sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "src"))

from GBUtils import Donazione
from config import BBP_SUBDIR
from cli_adapter import CLIAdapter
from controller import TournamentController


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

    # Avvia controller con CLI adapter se --cli è presente, altrimenti avvia la GUI
    if "--cli" in sys.argv:
        atexit.register(Donazione)
        adapter = CLIAdapter()
        controller = TournamentController(adapter)
        controller.start()
    else:
        from gui import TornelloApp
        app = TornelloApp()
        app.MainLoop()
