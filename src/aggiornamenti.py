"""L'aggiornamento automatico di Tornello, comune alle sue due facce. Issue 37.

Il giro intero lo conduce gestisci_aggiornamento di GBUtils: controllo della
release, proposta con le note, scaricamento e avvio dello script che
sostituisce l'installazione. Qui restano i dati di Tornello, cioe' da dove
si legge la release e con che nome firmare file temporanei e log, e la
versione da console. Quella con le finestre sta in MainFrame, che le passa le
sue funzioni proponi e avanzamento.
Fino alla 10.6.5 le due facce chiamavano update_checker e perform_update
ciascuna per conto suo, con l'indirizzo della release scritto due volte, e
nessuna delle due mostrava le note della versione nuova, che update_checker
restituisce da sempre.
"""

from config import _

# L'ultima release pubblicata su GitHub, da cui arrivano versione, note e
# archivio da scaricare.
API_RELEASE = "https://api.github.com/repos/GabrieleBattaglia/Tornello/releases/latest"

# Il nome con cui gestisci_aggiornamento firma archivio, cartella temporanea,
# script e righe del log: lo stesso delle versioni fino alla 10.6.5, cosi'
# gli avanzi di un aggiornamento vecchio si riconoscono.
NOME_APP = "tornello"

# Le frasi che gestisci_aggiornamento di GBUtils dice durante l'aggiornamento
# e passa alla traduzione. Stanno qui soltanto perche' pybabel le estragga nei
# cataloghi: babel.cfg guarda i sorgenti di Tornello e non la libreria. Devono
# restare identiche, carattere per carattere, a quelle scritte in GBUtils,
# altrimenti la traduzione non viene trovata e l'utente sente l'italiano: lo
# controlla tests/test_aggiornamento.py. E' la stessa tupla di Orologic.
FRASI_AGGIORNAMENTO_GBUTILS = (
    _("Controllo aggiornamenti."),
    _("Hai gia' l'ultima versione,"),
    _("Controllo non riuscito, si prosegue."),
    _("Disponibile la versione"),
    _("ma il pacchetto non e' ancora pronto."),
    _("Tu hai la"),
    _("Novita' di questa versione:"),
    _("Novita'"),
    _("Vuoi aggiornare adesso?"),
    _("Aggiornamento rimandato."),
    _("Scarico l'aggiornamento."),
    _("Aggiornamento pronto, il programma si chiude per applicarlo."),
    _("Aggiornamento non riuscito, si prosegue con questa versione."),
)


def aggiorna_da_console():
    """L'aggiornamento della versione a riga di comando, tornello.py --cli.

    Senza avvisa gestisci_aggiornamento parla con print, e le note della
    release passano da manuale di GBUtils, che le impagina e si ferma a ogni
    pagina: e' la scelta di Gabriele del 4 settembre 2026, scritta nella
    issue. La domanda la fa la conferma della console, con INVIO per Si' ed
    ESCAPE per No e la guida tradotta, come ogni altra domanda di Tornello da
    riga di comando. Da sorgente non succede niente, perche' l'aggiornamento
    si applica soltanto al programma compilato.
    Restituisce vero quando il programma deve chiudersi perche' lo script che
    applica l'aggiornamento e' gia' partito e aspetta la sua uscita.
    """
    from GBUtils import gestisci_aggiornamento

    from cli_adapter import CLIAdapter
    from version import __version__

    return gestisci_aggiornamento(
        NOME_APP,
        __version__,
        API_RELEASE,
        chiedi=CLIAdapter().confirm,
        traduci=_,
    )
