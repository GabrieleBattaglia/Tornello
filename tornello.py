# Entry point per Tornello v9
import atexit
import os
import sys
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)


def install_excepthook():
    def custom_excepthook(exctype, value, traceback_obj):
        import traceback
        from datetime import datetime

        err_msg = "".join(traceback.format_exception(exctype, value, traceback_obj))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"=== UNHANDLED EXCEPTION {timestamp} ===\n{err_msg}\n"

        # Il log va accanto all'applicazione: con un percorso relativo finiva
        # nella directory da cui il programma era stato avviato, mentre il
        # messaggio mostrato all'utente dice comunque di cercarlo in error.log.
        try:
            from config import user_data_path

            percorso_log = user_data_path("error.log")
        except Exception:
            percorso_log = "error.log"

        try:
            with open(percorso_log, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception:
            pass

        try:
            import wx

            if wx.GetApp():
                wx.MessageBox(
                    f"Si è verificato un errore imprevisto.\n\nDettagli:\n{value}\n\nI dettagli completi sono stati salvati in error.log.",
                    "Errore Imprevisto",
                    wx.ICON_ERROR | wx.OK,
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

from cli_adapter import CLIAdapter
from config import BBP_SUBDIR
from controller import TournamentController

from GBUtils import Donazione


def check_updates():
    try:
        from version import __version__ as current_ver

        from GBUtils import enter_escape, perform_update, update_checker

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
        elif latest_ver:
            print(_("Nessun aggiornamento disponibile: hai già l'ultima versione."))
        else:
            # update_checker restituisce una versione vuota anche quando la rete
            # non è raggiungibile: è un evento normale, non un errore del programma.
            print(
                _(
                    "Controllo aggiornamenti non riuscito, probabilmente manca la connessione. Il programma funziona ugualmente."
                )
            )
    except Exception as e_update:
        print(_("Controllo aggiornamenti fallito: {}").format(e_update))


def verifica_permessi_di_scrittura():
    """Tornello e' portabile e tiene i propri dati accanto a se stesso: il
    database dei giocatori, i tornei, l'archivio, i backup e i file di lavoro
    dell'abbinatore. Se quella cartella non e' scrivibile non c'e' ripiego che
    tenga, perche' anche la cartella di default e' quella. Meglio dirlo subito
    e con chiarezza, invece di far fallire una operazione alla volta.
    """
    from config import user_data_path
    from utils import cartella_scrivibile

    cartella = os.path.abspath(user_data_path(""))
    if cartella_scrivibile(cartella):
        return True

    messaggio = _(
        "Tornello non puo' scrivere nella propria cartella:\n{cartella}\n\n"
        "Il programma tiene accanto a se' il database dei giocatori, i tornei, "
        "l'archivio e le copie di sicurezza, quindi senza permesso di scrittura "
        "non puo' funzionare.\n\n"
        "Sposta la cartella di Tornello dove hai i permessi di scrittura, per "
        "esempio nei tuoi Documenti o sul Desktop, e riavvia il programma."
    ).format(cartella=cartella)
    print(messaggio)
    if "--cli" not in sys.argv:
        try:
            import wx

            app_avviso = wx.App(False)
            wx.MessageBox(
                messaggio, _("Cartella non scrivibile"), wx.OK | wx.ICON_ERROR
            )
            app_avviso.Destroy()
        except (ImportError, RuntimeError):
            # Senza interfaccia grafica resta il messaggio in console.
            pass
    return False


if __name__ == "__main__":
    if not verifica_permessi_di_scrittura():
        sys.exit(1)

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

    # Avvia controller con CLI adapter se --cli è presente, altrimenti avvia la GUI
    if "--cli" in sys.argv:
        check_updates()
        from config import lingua_rilevata

        atexit.register(lambda: Donazione(lang=lingua_rilevata))
        adapter = CLIAdapter()
        controller = TournamentController(adapter)
        controller.start()
    else:
        from gui import TornelloApp

        app = TornelloApp()
        app.MainLoop()
