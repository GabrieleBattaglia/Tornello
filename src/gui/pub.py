"""Le parole delle due voci del PUB, il gruppo di supporto, nel menu Aiuto:
la mail che iscrive e quella che chiede aiuto. Issue 70, dalla 10.18.0.

Richiesta di Gabriele del 21 ottobre 2026, per tutti i programmi del parco
che hanno una finestra. Gli indirizzi, le informazioni sul computer e la
composizione della mail vengono da GBUtils, issue GabrieleBattaglia/GBUtils#57,
e la finestra che la prepara da GBwx, finestra_mail: qui ci sono soltanto le
parole di Tornello, tradotte con _(), perche' GBUtils non ne ha di sue, e le
righe in piu' della mail d'aiuto, la versione di bbpPairings e la lingua
dell'interfaccia. Le parole seguono quelle di MeTeOra e di MESS, che le voci le
hanno gia'.
La finestra si apre sempre, anche quando il programma di posta c'e', perche'
il nuovo Outlook di Windows 11 e' spesso associato a mailto anche per chi non
lo usa; senza posta accompagna l'utente un passo alla volta, copiando negli
appunti un campo per volta. Tornello non spedisce mai niente: spedisce
l'utente, se vuole, dopo aver letto e corretto.
Il modulo non importa wx: le prove leggono le parole senza finestre.
"""

import builtins
import re

_ = getattr(builtins, "_", lambda s: s)


def pulsanti():
    """Le etichette dei pulsanti di finestra_mail, con le lettere di scelta
    rapida: Apri e Passo per passo con il programma di posta, OK nei passi,
    Chiudi, che nei passi diventa Annulla."""
    return {
        "apri": _("&Apri nel programma di posta"),
        "passi": _("&Passo per passo"),
        "ok": _("&OK"),
        "chiudi": _("&Chiudi"),
        "annulla": _("&Annulla"),
    }


def senza_posta():
    """La frase che precede il primo passo quando il programma di posta manca
    o non parte."""
    return _(
        "Non trovo un programma di posta, oppure non si è aperto: prepariamo la mail un pezzo alla volta, da incollare nella tua "
        "posta, per esempio nella webmail del browser."
    )


def etichette():
    """Le informazioni del computer nella mail d'aiuto, nell'ordine in cui
    compaiono, con le loro etichette. Se il programma e' compilato lo dice
    gia' la riga del programma, e la chiave compilato resta fuori."""
    return {
        "windows": _("Sistema operativo"),
        "windows_versione": _("Versione di Windows"),
        "windows_build": _("Build di Windows"),
        "architettura": _("Architettura"),
        "processore": _("Processore"),
        "nuclei": _("Nuclei logici"),
        "memoria_totale": _("Memoria"),
        "memoria_libera": _("Memoria libera"),
        "lingua": _("Lingua di sistema"),
        "screen_reader": _("Screen reader"),
        "schermo": _("Schermo"),
        "scala": _("Scala dello schermo"),
        "python": _("Python"),
    }


def parole():
    """Le parole dei valori vero e falso; None non ne ha, e una riga che non
    si e' potuta leggere resta fuori."""
    return {True: _("sì"), False: _("no")}


def separatore_decimale(lingua):
    """Il punto decimale delle memorie nella lingua dell'interfaccia: il punto
    in inglese, la virgola in italiano, spagnolo, francese e portoghese."""
    return "." if str(lingua or "").lower().startswith("en") else ","


def versione_di_bbppairings(informazioni):
    """La versione di bbpPairings, il motore degli abbinamenti, da
    __bbp_info__ di version.py, per esempio 6.0.0 da using BBP Pairings
    (v6.0.0). Se la frase cambia forma e la versione non si trova, torna la
    frase intera: meglio troppo che niente, per chi risponde."""
    trovata = re.search(r"BBP Pairings \(v?([^()\s]+)\)", informazioni or "")
    return trovata.group(1) if trovata else (informazioni or "").strip()


def _altra_strada():
    return _(
        "Se la mail non compare, torna qui e scegli Passo per passo: ti guido a scriverla nella tua posta, per esempio nella webmail "
        "del browser."
    )


def _iscriviti():
    return _("Se non sei ancora iscritto al PUB, puoi farlo con Entra al PUB, nel menu Aiuto.")


def mail_d_iscrizione():
    """Entra al PUB: le parole della mail che iscrive al gruppo. All'indirizzo
    dell'iscrizione Google non legge oggetto e testo, e risponde con una mail
    di conferma: nei passi basta l'indirizzo."""
    from GBUtils import PUB_ISCRIZIONE

    return {
        "titolo": _("Entra al PUB, il gruppo di supporto"),
        "destinatario": PUB_ISCRIZIONE,
        "oggetto": _("Iscrizione al PUB"),
        "corpo": _("Invia questo messaggio così com'è per iscriverti al PUB. Google ti scriverà per chiederti di confermare."),
        "spiegazione": "\n".join((
            _(
                "Il PUB è il gruppo di supporto dei programmi di Gabriele Battaglia, una lista di posta su Google Groups, dove si chiede "
                "aiuto, si segnalano i problemi e si propongono idee."
            ),
            # {programma} lo riempie finestra_mail con il nome del programma
            # di posta: non passa da format.
            _(
                "Il pulsante Apri nel programma di posta prepara in {programma} la mail che ti iscrive: spediscila così com'è, perché "
                "Tornello non spedisce niente da solo. Poi Google ti scriverà per chiederti di confermare l'iscrizione: segui le sue "
                "istruzioni."
            ),
            _altra_strada(),
        )),
        "passi": (
            (
                _(
                    "Passo 1 di 2. Scrivi una mail nuova nella tua posta, per esempio nella webmail del browser, e incolla nel campo A "
                    "l'indirizzo dell'iscrizione, che ho copiato negli appunti; poi torna qui e premi OK. L'indirizzo è questo:"
                ),
                PUB_ISCRIZIONE,
            ),
            (
                _(
                    "Passo 2 di 2. Oggetto e testo possono restare vuoti, perché Google non li legge: spedisci la mail così com'è. Google "
                    "ti scriverà per chiederti di confermare l'iscrizione: segui le sue istruzioni. OK chiude questa finestra."
                ),
                None,
            ),
        ),
    }


def mail_d_aiuto(versione, compilato, informazioni, lingua, bbp):
    """Chiedi aiuto al PUB: le parole della mail al gruppo. L'oggetto dice la
    versione; il testo ha una prima riga da sostituire con la domanda e sotto
    le informazioni, introdotte da una riga che parla a chi riceve la mail: il
    programma, con la versione e se gira compilato o dai sorgenti, il motore
    degli abbinamenti con la sua versione, da bbp, cioe' __bbp_info__ di
    version.py, la lingua dell'interfaccia, e il computer, da informazioni,
    le coppie di informazioni_di_sistema di GBUtils, con le etichette di
    etichette()."""
    from GBUtils import PUB_GRUPPO, righe_informazioni

    oggetto = _("Chiedo per Tornello {versione}").format(versione=versione)
    programma = (
        _("Programma: Tornello {versione}, pacchetto compilato") if compilato else _("Programma: Tornello {versione}, dai sorgenti")
    ).format(versione=versione)
    corpo = "\n".join((
        _("Scrivi qui la tua domanda, al posto di questa riga."),
        _("Informazioni su Tornello e sul computer di chi scrive:"),
        programma,
        _("Motore degli abbinamenti: BBP Pairings {versione}").format(versione=versione_di_bbppairings(bbp)),
        _("Lingua di Tornello: {lingua}").format(lingua=lingua),
        *righe_informazioni(etichette(), informazioni, parole()),
    ))
    return {
        "titolo": _("Chiedi aiuto al PUB"),
        "destinatario": PUB_GRUPPO,
        "oggetto": oggetto,
        "corpo": corpo,
        "spiegazione": "\n".join((
            # {programma} resta per finestra_mail, che ci mette il nome del
            # programma di posta.
            _(
                "Il pulsante Apri nel programma di posta prepara in {programma} una mail al PUB, il gruppo di supporto dei programmi "
                "di Gabriele Battaglia, con l'oggetto {oggetto}."
            ).format(programma="{programma}", oggetto=oggetto),
            _(
                "Scrivi la tua domanda al posto della prima riga del testo; sotto ci sono le informazioni su Tornello e sul tuo "
                "computer, utili a chi ti risponde, che puoi cancellare se preferisci."
            ),
            _("Poi spediscila tu: Tornello non spedisce niente da solo. {iscriviti}").format(iscriviti=_iscriviti()),
            _altra_strada(),
        )),
        "passi": (
            (
                _(
                    "Passo 1 di 4. Scrivi una mail nuova nella tua posta, per esempio nella webmail del browser, e incolla nel campo A "
                    "l'indirizzo del PUB, che ho copiato negli appunti; poi torna qui e premi OK. L'indirizzo è questo:"
                ),
                PUB_GRUPPO,
            ),
            (
                _("Passo 2 di 4. Incolla nel campo Oggetto quello che ho copiato negli appunti, poi torna qui e premi OK. L'oggetto è questo:"),
                oggetto,
            ),
            (
                _(
                    "Passo 3 di 4. Incolla nel testo della mail quello che ho copiato negli appunti, e scrivi la tua domanda al posto della "
                    "prima riga; le informazioni su Tornello e sul computer, sotto, puoi cancellarle se preferisci. Poi torna qui e premi "
                    "OK. Il testo è questo:"
                ),
                corpo,
            ),
            (_("Passo 4 di 4. Spedisci la mail. {iscriviti} OK chiude questa finestra.").format(iscriviti=_iscriviti()), None),
        ),
    }
