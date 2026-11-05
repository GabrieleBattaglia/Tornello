"""I tornei con lo stesso nome, senza wx (10.19.13, issue 66).

Il nome di un torneo, ripulito da sanitize_filename, da' il nome al suo
file, Tornello - <nome>.json, ai suoi report e alla raccolta delle partite in
PGN, <nome> - raccolta partite.pgn: due tornei con lo stesso nome ripulito,
senza badare alle maiuscole, come fa Windows, scrivono file con lo stesso
nome. Qui stanno i controlli che lo impediscono: con che cosa coincide il
nome di un torneo nuovo, o cambiato da Dati, nella cartella del programma
(coincidenza_del_nome), le edizioni con lo stesso nome nell'archivio
(edizioni_nell_archivio), e la raccolta delle partite di un altro torneo
trovata al posto di quella del torneo (raccolta_altrui_in_salvo e
aggiorna_la_raccolta_pgn). La finestra principale li usa con le sue finestre
di messaggio, la finalizzazione, nella finestra e in console, con le righe
che stampa.
Fino alla 10.19.10 stavano in gui/main_frame.py, dove la console non li
poteva usare, e guardavano soltanto il nome dei file. Un torneo rinominato
dal ramo Dati tiene pero' il file di prima: Beta, nel file Tornello -
Alfa.json, sfuggiva ai controlli, e un torneo nuovo chiamato Beta ne
avrebbe sostituito i report e la raccolta delle partite. Dalla 10.19.13
conta anche il nome scritto dentro il json, confrontato ripulito come quello
che da' il nome ai file (decisione di Gabriele del 4 novembre 2026)."""

import glob
import json
import os
import re
import time
from typing import NamedTuple

from config import ARCHIVED_TOURNAMENTS_DIR, user_data_path
from utils import sanitize_filename

# I nomi scritti nei json gia' letti, per percorso, con la firma del file,
# dimensione e data di modifica: la guardia della raccolta delle partite li
# chiede per tutto l'archivio a ogni salvataggio dopo un PGN nuovo. Misurato
# il 4 novembre 2026 su un archivio finto di 65 tornei, 11 MB in tutto,
# leggere tutti i json costava 70 millisecondi, il solo os.stat di ciascuno
# 12. Un file cambiato da meno di ETA_MINIMA_IN_MEMORIA_NS nanosecondi si
# rilegge ogni volta, come fa git con il suo indice: una seconda scrittura
# nello stesso istante, con la stessa dimensione, avrebbe la stessa firma.
# Un file che non si legge non si ricorda, perche' puo' essere bloccato per
# un momento, per esempio da Dropbox.
_NOMI_SCRITTI = {}
ETA_MINIMA_IN_MEMORIA_NS = 2 * 10**9

# Il risultato di una partita in PGN, nella riga Result dell'intestazione e
# in fondo alle mosse, che _senza_risultato mette in sospeso: CANC lo toglie
# con pgn_senza_risultato di tournament.py, e la stessa partita, con le
# stesse mosse, resta la stessa. In fondo alle mosse conta anche lo spazio
# prima: python-chess va a capo quando la riga supererebbe gli ottanta
# caratteri, e 1/2-1/2 ci arriva prima dell'asterisco.
_RISULTATO_NELL_INTESTAZIONE = re.compile(r'^\[Result "[^"\n]*"\]$', re.MULTILINE)
_RISULTATO_IN_FONDO = re.compile(r"(?:\s+|\A)(?:1-0|0-1|1/2-1/2|\*)\Z")


class Coincidenza(NamedTuple):
    """Con che cosa coincide il nome di un torneo nuovo, per
    coincidenza_del_nome. frase si mette nel messaggio dopo come; del_file e'
    vero quando coincide il nome del file, falso quando coincide soltanto il
    nome scritto dentro il json di un torneo con un file di nome diverso."""

    frase: str
    del_file: bool


class RaccoltaInSalvo(NamedTuple):
    """La risposta di raccolta_altrui_in_salvo. in_salvo e' vero se il
    torneo puo' scrivere la sua raccolta; testo e' il messaggio che dice
    dove e' andata quella dell'altro torneo, o perche' non si e' potuta
    mettere in salvo, oppure None se non c'era niente da dire.
    di_un_altra_edizione e' vero quando la raccolta al posto di quella del
    torneo e' di un'altra edizione archiviata, che adesso ne ha una copia
    nella sua cartella d'archivio: se resta dov'e', perche' il cestino non
    l'ha presa e il torneo non ha partite in PGN, non e' la raccolta rimasta
    del torneo, e la finalizzazione non lo dice, come la finestra (revisione
    della 10.19.13, decisione di Gabriele del 4 novembre 2026)."""

    in_salvo: bool
    testo: str | None = None
    di_un_altra_edizione: bool = False


class RaccoltaAggiornata(NamedTuple):
    """La risposta di aggiorna_la_raccolta_pgn. rimasta e' il percorso della
    raccolta di un torneo che non ha piu' partite in PGN, che doveva andare
    nel cestino e che il cestino non ha preso, oppure None; gia_detta e'
    vero quando era gia' fra le rimaste, e il cestino non si e' riprovato.
    non_scritta e' la frase che dice perche' la raccolta del torneo non e'
    stata scritta, oppure None; copia_non_riuscita e' vero quando e' perche'
    la raccolta rimasta non si e' potuta mettere nella cartella backup
    (revisione della 10.19.13). errore e' il motivo che da' il sistema
    quando la raccolta non si e' potuta scrivere, o leggere prima di
    sostituirla, oppure None: la finestra lo dice nel suo messaggio
    (decisione di Gabriele del 5 novembre 2026). Dalla revisione della
    10.19.19 e' soltanto la descrizione, strerror, per esempio Permission
    denied, perche' il messaggio dice gia' la cartella e il file; senza
    descrizione e' il testo intero, come prima. La frase in non_scritta,
    della finalizzazione, e la console tengono il testo intero."""

    rimasta: str | None = None
    gia_detta: bool = False
    non_scritta: str | None = None
    copia_non_riuscita: bool = False
    errore: str | None = None


def _chiave_del_percorso(percorso):
    """Il percorso nella forma in cui si confronta con un altro: assoluto e,
    su Windows, senza differenze di maiuscole e di barre. None e la stringa
    vuota restano come sono."""
    if not percorso:
        return percorso
    return os.path.normcase(os.path.abspath(percorso))


def _ha_la_forma_di_un_torneo(dati):
    """Vero se i dati letti da un file hanno la forma di un torneo di
    Tornello: un dizionario con il nome, gli iscritti e i turni. Il database
    dei giocatori, per esempio, ha gli iscritti ma non il nome."""
    return (
        isinstance(dati, dict)
        and isinstance(dati.get("name"), str)
        and isinstance(dati.get("players"), list)
        and isinstance(dati.get("rounds", []), list)
    )


def _file_del_torneo_nuovo(nome):
    """Il nome del file di un torneo nuovo chiamato nome, senza la cartella:
    Tornello - seguito dal nome ripulito da sanitize_filename, .json."""
    return f"Tornello - {sanitize_filename(nome)}.json"


def _leggi_json(percorso):
    """Il contenuto di un file JSON, oppure None se il file non si legge.
    Dalla 10.19.13 anche un json annidato oltre il limite di Python, che
    json.load rifiuta con RecursionError, conta come un file che non si
    legge, e non fa cadere i controlli sul nome."""
    try:
        with open(percorso, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError, RecursionError):
        return None


def _nome_ripulito(nome):
    """Il nome di un torneo nella forma in cui si confronta con un altro:
    ripulito da sanitize_filename, come nei nomi dei file, e in minuscolo."""
    return sanitize_filename(nome).lower()


def stesso_nome_di_file(percorso, nome):
    """Vero se il file percorso si chiama come quello di un torneo nuovo
    chiamato nome, senza badare alle maiuscole. Falso per un torneo trovato
    soltanto dal nome scritto nel suo json."""
    return os.path.basename(percorso).lower() == _file_del_torneo_nuovo(nome).lower()


def stesso_nome_scritto(dati, nome):
    """Vero se dati, i dati di un torneo letti dal suo json, hanno scritto
    il nome di un torneo nuovo chiamato nome, confrontato ripulito come in
    coincidenza_del_nome. Falso per dati None, cioe' per un file che non si
    legge o che non ha la forma di un torneo, e per un torneo che coincide
    soltanto per il nome del file, come Beta archiviata nel file Tornello -
    Alfa.json per il nome Alfa: il suo nome e' un altro, e i report e la
    raccolta delle partite non si chiamerebbero come i suoi (revisione della
    10.19.15, issue 66)."""
    return _ha_la_forma_di_un_torneo(dati) and _nome_ripulito(dati["name"]) == _nome_ripulito(nome)


def _nome_scritto(percorso):
    """Il nome scritto nel json percorso, ripulito da _nome_ripulito, e i
    dati letti: (nome, dati). Il nome e' None per un file che non si legge o
    che non ha la forma di un torneo; i dati sono None quando il nome viene
    da _NOMI_SCRITTI, senza leggere il file."""
    try:
        stato = os.stat(percorso)
    except OSError:
        return None, None
    chiave = _chiave_del_percorso(percorso)
    firma = (stato.st_size, stato.st_mtime_ns)
    in_memoria = _NOMI_SCRITTI.get(chiave)
    if in_memoria is not None and in_memoria[0] == firma:
        return in_memoria[1], None
    dati = _leggi_json(percorso)
    if dati is None:
        return None, None
    nome = _nome_ripulito(dati["name"]) if _ha_la_forma_di_un_torneo(dati) else None
    if time.time_ns() - stato.st_mtime_ns >= ETA_MINIMA_IN_MEMORIA_NS:
        _NOMI_SCRITTI[chiave] = (firma, nome)
    return nome, dati


def _con_lo_stesso_nome_scritto(percorso, ripulito):
    """I dati del torneo nel json percorso, se il nome scritto dentro,
    ripulito, e' ripulito; altrimenti None."""
    scritto, dati = _nome_scritto(percorso)
    if scritto != ripulito:
        return None
    if dati is None:
        dati = _leggi_json(percorso)
    if not _ha_la_forma_di_un_torneo(dati) or _nome_ripulito(dati["name"]) != ripulito:
        return None
    return dati


def _stato_nella_cartella(dati):
    """Lo stato di un torneo della cartella del programma, da dire nei
    messaggi: concluso, in corso o in preparazione."""
    if dati.get("concluded"):
        return _("concluso, nella cartella del programma")
    if dati.get("rounds"):
        return _("in corso nella cartella del programma")
    return _("in preparazione nella cartella del programma")


def _coincidenza_per_il_file(in_cartella, cercato):
    """La Coincidenza del file cercato, il nome in minuscolo del file di un
    torneo nuovo, con uno dei file in_cartella, oppure None."""
    for percorso in in_cartella:
        if os.path.basename(percorso).lower() != cercato:
            continue
        dati = _leggi_json(percorso)
        # Un file che non ha la forma di un torneo, o che non si legge, e' un
        # file del programma, e non si sovrascrive lo stesso.
        if not _ha_la_forma_di_un_torneo(dati):
            return Coincidenza(_("come un altro file del programma, che c'è già nella sua cartella"), True)
        return Coincidenza(
            _("come il file del torneo {torneo}, {stato}").format(torneo=dati["name"], stato=_stato_nella_cartella(dati)),
            True,
        )
    return None


def _coincidenza_per_il_nome_scritto(in_cartella, ripulito, saltati):
    """La Coincidenza di un torneo dei file in_cartella, tranne quelli il cui
    nome in minuscolo e' fra saltati, con il nome scritto nel json, ripulito,
    uguale a ripulito: i report e la raccolta delle partite avrebbero lo
    stesso nome. None se non ce n'e'."""
    for percorso in in_cartella:
        if os.path.basename(percorso).lower() in saltati:
            continue
        dati = _con_lo_stesso_nome_scritto(percorso, ripulito)
        if dati is None:
            continue
        return Coincidenza(
            _("come quelli del torneo {torneo}, {stato}, nel file {file}").format(
                torneo=dati["name"],
                stato=_stato_nella_cartella(dati),
                file=os.path.basename(percorso),
            ),
            False,
        )
    return None


def coincidenza_del_nome(nome, escluso=None, da_dati=False):
    """Con che cosa coincide un torneo nuovo chiamato nome, nella cartella
    del programma: una Coincidenza, oppure None se il nome e' libero.
    Il file di un torneo si chiama Tornello - <nome ripulito>.json, con il
    nome ripulito da sanitize_filename, e si confronta senza badare alle
    maiuscole, come fa Windows: con il database dei giocatori e le
    impostazioni, e con ogni altro file Tornello - *.json della cartella del
    programma, torneo o no. Dalla 10.19.13 coincide anche un torneo della
    cartella con un file di nome diverso e con lo stesso nome scritto nel
    suo json, ripulito allo stesso modo: e' un torneo rinominato dal ramo
    Dati, che tiene il file di prima, e i report e la raccolta delle partite
    dei due tornei avrebbero lo stesso nome. Un file che non si legge, o
    che non ha la forma di un torneo, non ha un nome scritto, e coincide
    soltanto con il suo nome di file. escluso e' il file del torneo
    aperto, che non coincide con se stesso quando cambia il nome o la data
    di inizio da Dati (10.19.7).
    da_dati dice che il nome viene dal ramo Dati, dove il file del torneo
    non cambia nome: un torneo con lo stesso nome scritto nel json conta
    allora prima del nome dei file, anche quando il suo file si chiama
    come quello di un torneo nuovo con quel nome, perche' il motivo vero e'
    che i report e la raccolta delle partite dei due tornei avrebbero lo
    stesso nome, e la Coincidenza ha del_file falso. Il nome che coincide
    soltanto con un file si rifiuta lo stesso, con del_file vero. I nomi
    rifiutati sono gli stessi, con o senza da_dati: cambia soltanto il
    motivo che il messaggio dice (10.19.15, issue 66, decisione di
    Gabriele del 4 novembre 2026).
    Nata con la 10.13.52 (issue 66): fino ad allora la procedura guidata non
    guardava, e un torneo chiamato come uno che c'era gia' ne sovrascriveva
    il file, con i turni e i risultati; uno chiamato Players_db o Settings
    prendeva il nome del database dei giocatori o delle impostazioni. I
    tornei dell'archivio non sono qui: un nome che coincide soltanto con
    loro e' quello di una nuova edizione, che si accetta dopo una domanda
    (edizioni_nell_archivio, decisione di Gabriele del 4 novembre 2026)."""
    from config import PLAYER_DB_FILE

    cercato = _file_del_torneo_nuovo(nome).lower()
    del_database = os.path.basename(PLAYER_DB_FILE).lower()
    delle_impostazioni = "tornello - settings.json"
    if cercato == del_database:
        return Coincidenza(_("come il database dei giocatori"), True)
    if cercato == delle_impostazioni:
        return Coincidenza(_("come il file delle impostazioni del programma"), True)

    in_cartella = [
        percorso
        for percorso in sorted(glob.glob(os.path.join(glob.escape(user_data_path("")), "Tornello - *.json")))
        if not (escluso and _chiave_del_percorso(percorso) == _chiave_del_percorso(escluso))
    ]
    ripulito = _nome_ripulito(nome)
    saltati = (del_database, delle_impostazioni)
    if da_dati:
        return _coincidenza_per_il_nome_scritto(in_cartella, ripulito, saltati) or _coincidenza_per_il_file(in_cartella, cercato)
    return _coincidenza_per_il_file(in_cartella, cercato) or _coincidenza_per_il_nome_scritto(in_cartella, ripulito, saltati)


def edizioni_nell_archivio(nome, escluso=None):
    """I tornei conclusi dell'archivio con lo stesso nome di un torneo nuovo
    chiamato nome: quelli il cui file coincide con il suo, confrontato come
    in coincidenza_del_nome, e dalla 10.19.13 quelli con un file di nome
    diverso e con lo stesso nome scritto nel json, come un'edizione
    rinominata dal ramo Dati prima di finalizzarla. Una lista di coppie (percorso, dati), in
    ordine di percorso, quindi di anno e di mese, con dati None per un file
    con il nome del suo che non si legge o che non ha la forma di un torneo;
    un file di nome diverso che non si legge non si conta, perche' il suo
    nome non si conosce. stesso_nome_di_file dice quale coincide per il nome
    del file. Un nome che coincide soltanto con loro e' quello di una nuova
    edizione, e la procedura guidata lo accetta dopo una domanda (10.13.52,
    issue 66, decisione di Gabriele del 4 novembre 2026): le edizioni si
    distinguono, nell'archivio e nello storico dei giocatori, dalla data di
    inizio. escluso e' il file del torneo aperto, che da Dati non e'
    un'edizione di se stesso quando sta nell'archivio (10.19.7)."""
    cercato = _file_del_torneo_nuovo(nome).lower()
    ripulito = _nome_ripulito(nome)
    trovate = []
    in_archivio = glob.glob(os.path.join(glob.escape(ARCHIVED_TOURNAMENTS_DIR), "**", "Tornello - *.json"), recursive=True)
    for percorso in sorted(in_archivio):
        if escluso and _chiave_del_percorso(percorso) == _chiave_del_percorso(escluso):
            continue
        if os.path.basename(percorso).lower() == cercato:
            dati = _leggi_json(percorso)
            trovate.append((percorso, dati if _ha_la_forma_di_un_torneo(dati) else None))
            continue
        dati = _con_lo_stesso_nome_scritto(percorso, ripulito)
        if dati is not None:
            trovate.append((percorso, dati))
    return trovate


def edizione_con_l_identita(identita, escluso=None, saltati=()):
    """Il primo torneo concluso dell'archivio con l'identita' identita, cioe'
    con lo stesso identificativo e la stessa data di inizio, come le da'
    identita_del_torneo: una coppia (percorso, dati), oppure None. escluso
    e' il file del torneo aperto, saltati i percorsi da non guardare. Un
    json che non si legge, o che non ha la forma di un torneo, non conta.
    Lo storico dei giocatori riconosce un torneo dall'identita', e
    l'identificativo non cambia quando il torneo cambia nome da Dati: un
    torneo rinominato con la data di inizio di un'edizione archiviata con
    lo stesso identificativo sarebbe, alla finalizzazione, una
    finalizzazione ripetuta di quell'edizione, e i giocatori non ne
    riceverebbero niente. Nata con la revisione della 10.19.13 (issue 66,
    decisione di Gabriele del 4 novembre 2026): i controlli guardavano
    soltanto il nome, e il torneo rinominato sfuggiva."""
    from db_players import identita_del_torneo

    via = {_chiave_del_percorso(p) for p in saltati}
    if escluso:
        via.add(_chiave_del_percorso(escluso))
    in_archivio = glob.glob(os.path.join(glob.escape(ARCHIVED_TOURNAMENTS_DIR), "**", "Tornello - *.json"), recursive=True)
    for percorso in sorted(in_archivio):
        if _chiave_del_percorso(percorso) in via:
            continue
        dati = _leggi_json(percorso)
        if _ha_la_forma_di_un_torneo(dati) and identita_del_torneo(dati) == identita:
            return percorso, dati
    return None


def _cartella_nell_archivio(percorso):
    """La cartella d'archivio di un torneo concluso, da dire nei messaggi:
    il percorso da Closed Tournaments in giu', con l'anno e il mese, per
    esempio Closed Tournaments\\2026\\06 Giugno\\Primavera_2."""
    cartella = os.path.dirname(os.path.abspath(percorso))
    return os.path.relpath(cartella, os.path.dirname(os.path.abspath(ARCHIVED_TOURNAMENTS_DIR)))


def _contiene(percorso, contenuto):
    """Vero se il file percorso si legge e contiene esattamente contenuto."""
    try:
        with open(percorso, "rb") as f:
            return f.read() == contenuto
    except OSError:
        return False


def _senza_risultato(partita):
    """Il PGN partita con il risultato in sospeso, *, nella riga Result
    dell'intestazione e in fondo alle mosse, con uno spazio prima: due PGN
    della stessa partita che differiscono soltanto nel risultato, come prima
    e dopo CANC, diventano uguali (revisione della 10.19.13)."""
    partita = _RISULTATO_NELL_INTESTAZIONE.sub('[Result "*"]', partita)
    return _RISULTATO_IN_FONDO.sub(" *", partita)


def _partite_che_il_torneo_non_ha(torneo, percorso):
    """Vero se la raccolta delle partite percorso ha partite che il torneo
    non ha. La raccolta e' come la scrive byte_della_raccolta_pgn: il PGN di
    ogni partita, senza gli spazi ai due capi, uno dopo l'altro con una riga
    vuota in mezzo, in UTF-8 e con l'a capo del sistema. Anche il PGN di una
    partita ha una riga vuota, fra l'intestazione e le mosse, e dove finisce
    una partita lo dicono le partite del torneo: la raccolta si divide nei
    pezzi fra una riga vuota e l'altra, e se le partite del torneo, ognuna
    con i suoi pezzi, la coprono tutta, una dopo l'altra, in qualunque
    ordine, ogni partita della raccolta e' una partita del torneo. Il
    confronto e' sul testo, con _senza_risultato, e una partita che cambia
    soltanto nel risultato, come dopo CANC, e' la stessa; una che il torneo
    ha due volte nella raccolta non toglie niente. Una raccolta vuota non ha
    partite; una che non e' in UTF-8 ne ha, perche' non si puo' dire che non
    ne abbia. Nata con la revisione della 10.19.13 (issue 66, decisione di
    Gabriele del 4 novembre 2026).
    Un file che non si legge, per esempio perche' un altro programma lo
    tiene aperto senza lasciarlo leggere, solleva OSError: non si sa se abbia
    partite che il torneo non ha, e chi chiama lo dice com'e'. Fino alla
    correzione della stessa revisione ne aveva, e il messaggio della copia
    non riuscita diceva che aveva partite che il torneo non ha anche della
    raccolta identica di un torneo normale, bloccata da un altro programma."""
    with open(percorso, "rb") as f:
        dati = f.read()
    try:
        testo = dati.decode("utf-8")
    except UnicodeDecodeError:
        return True
    pezzi = testo.replace(os.linesep, "\n").strip().split("\n\n")
    if pezzi == [""]:
        return False
    # Le partite del torneo, senza il risultato, per numero di pezzi.
    partite = {}
    for turno in torneo.get("rounds", []):
        for partita in turno.get("matches", []):
            if partita.get("pgn"):
                pgn = partita["pgn"].strip()
                partite.setdefault(pgn.count("\n\n") + 1, set()).add(_senza_risultato(pgn))
    # I pezzi della raccolta fino a cui arrivano le partite del torneo, una
    # dopo l'altra dall'inizio.
    coperti = {0}
    for inizio in range(len(pezzi)):
        if inizio not in coperti:
            continue
        for quanti, testi in partite.items():
            fine = inizio + quanti
            if fine <= len(pezzi) and _senza_risultato("\n\n".join(pezzi[inizio:fine])) in testi:
                coperti.add(fine)
    return len(pezzi) not in coperti


def _edizioni_della_raccolta(torneo, file_del_torneo, percorso):
    """Le edizioni archiviate di cui la raccolta delle partite percorso, al
    posto di quella del torneo con il file file_del_torneo, e' la raccolta:
    le coppie (percorso del json, dati) di edizioni_nell_archivio con lo
    stesso nome, in quell'ordine, la cui raccolta, come la scriverebbe il
    loro json, e' identica byte per byte a percorso, tranne un'edizione con
    l'identita' del torneo, che e' il torneo stesso. La usano la guardia,
    raccolta_altrui_in_salvo, e _da_mettere_in_salvo, all'apertura del
    torneo e prima di sostituire una raccolta rimasta, perche' riconoscano
    la stessa raccolta (revisione della 10.19.13)."""
    from db_players import identita_del_torneo
    from reports import byte_della_raccolta_pgn

    for json_archiviato, dati in edizioni_nell_archivio(torneo.get("name", ""), escluso=file_del_torneo):
        suo = byte_della_raccolta_pgn(dati) if dati else None
        if suo is None or not _contiene(percorso, suo):
            continue
        if torneo.get("start_date") and identita_del_torneo(dati) == identita_del_torneo(torneo):
            continue
        yield json_archiviato, dati


def raccolta_altrui_in_salvo(torneo, file_del_torneo, solo_archiviate=False, cestino=None, rimaste=None):
    """Se il torneo, con il file file_del_torneo, puo' scrivere la sua
    raccolta delle partite in PGN senza distruggere quella di un altro
    torneo: una RaccoltaInSalvo. Una raccolta che c'e' al suo posto, e che
    non e' identica a quella che il torneo scriverebbe, e' di un altro
    torneo, per esempio di un'edizione archiviata prima della 10.19.7,
    quando la raccolta restava nella cartella di salvataggio (issue 66). Se
    e' identica a quella di un'edizione archiviata con lo stesso nome, va
    nella sua cartella d'archivio, con una copia riletta, e l'originale nel
    cestino; altrimenti va nel cestino. Mai cancellata per sempre: dalla
    10.10.0 le cancellazioni vanno nel cestino (decisione di Gabriele). Il
    testo dice dov'e' andata. Se non va da nessuna parte, per esempio su un
    disco senza cestino, la risposta ha in_salvo falso, e il testo lo dice.
    Con solo_archiviate, come in ogni salvataggio della finestra e dalla
    10.19.13 alla finalizzazione, conta soltanto la raccolta identica a
    quella di un'edizione archiviata, di un'altra edizione: ogni altra
    raccolta resta al torneo, che la sostituisce, perche' dopo un PGN nuovo
    e' la sua di prima. Il file del torneo e un'edizione archiviata con la
    stessa identita' non contano: sono il torneo stesso, per esempio nella
    cartella di lavoro esterna dopo la finalizzazione.
    cestino e' la funzione che manda un percorso nel cestino e risponde vero
    se ci e' riuscita; senza, quella del programma. Fino alla 10.19.10 la
    guardia stava in MainFrame, e la finalizzazione in console non la
    faceva.
    La copia va nella cartella d'archivio dell'edizione con il nome della
    sua raccolta, quello che le da' il nome scritto nel suo json: fino alla
    revisione della 10.19.13 prendeva quello della raccolta del torneo, e con
    altre maiuscole, o per un'edizione rinominata da Dati e trovata per il
    nome del file, l'edizione non la riconosceva come sua, e il ripristino
    la vedeva come un file estraneo.
    rimaste e' l'insieme, come chiavi di percorso, delle raccolte che il
    cestino non ha preso, lo stesso di aggiorna_la_raccolta_pgn: la finestra
    passa il suo, che vale fino alla chiusura, la finalizzazione uno suo.
    Una raccolta rifiutata qui, che resta dov'e' perche' il torneo non ha
    partite in PGN e non la sostituisce, ci entra, e per una che c'e' gia'
    il cestino non si riprova e il messaggio non si ripete: fino alla
    revisione della
    10.19.13 ogni salvataggio della finestra riprovava, e ripeteva il
    messaggio e la domanda di Windows.
    Le edizioni di cui e' la raccolta le trova _edizioni_della_raccolta,
    come _da_mettere_in_salvo all'apertura del torneo e prima di sostituire
    una raccolta rimasta."""
    from reports import byte_della_raccolta_pgn, file_della_raccolta_pgn, nome_della_raccolta_pgn
    from ui import _copia_verificata
    from utils import delete_file_to_trash, stessi_byte

    cestino = cestino or delete_file_to_trash
    rimaste = set() if rimaste is None else rimaste
    percorso = file_della_raccolta_pgn(torneo, file_del_torneo)
    if not os.path.isfile(percorso):
        return RaccoltaInSalvo(True)
    proprio = byte_della_raccolta_pgn(torneo)
    if proprio is not None and _contiene(percorso, proprio):
        return RaccoltaInSalvo(True)
    cartella, nome_file = os.path.split(percorso)
    nome = torneo.get("name", "")
    trovata = False
    for json_archiviato, dati in _edizioni_della_raccolta(torneo, file_del_torneo, percorso):
        trovata = True
        destinazione = os.path.join(
            os.path.dirname(json_archiviato), nome_della_raccolta_pgn(sanitize_filename(dati["name"]))
        )
        # Una raccolta diversa gia' nella cartella d'archivio resta com'e':
        # quella trovata va nel cestino, piu' sotto.
        if os.path.exists(destinazione) and not stessi_byte(percorso, destinazione):
            break
        if not os.path.exists(destinazione) and not _copia_verificata(percorso, destinazione, lambda _frase: None):
            break
        chiave = _chiave_del_percorso(percorso)
        if chiave in rimaste:
            # Il cestino non l'ha gia' presa, e il messaggio e' gia' stato
            # detto: la copia in archivio c'e', e la raccolta resta.
            return RaccoltaInSalvo(True, di_un_altra_edizione=True)
        if cestino(percorso):
            testo = _(
                "Nella cartella {cartella} c'era la raccolta delle partite {file} del torneo {torneo}, concluso e archiviato nella cartella {archivio}: il torneo {nome} l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
                "Una copia identica, riletta, adesso è nella cartella d'archivio di quel torneo, e quella della cartella {cartella} è andata nel cestino di Windows."
            )
        elif proprio is not None:
            # Il torneo la sostituisce subito con la sua raccolta, e non
            # resta: non si ricorda.
            testo = _(
                "Nella cartella {cartella} c'era la raccolta delle partite {file} del torneo {torneo}, concluso e archiviato nella cartella {archivio}: il torneo {nome} l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
                "Una copia identica, riletta, adesso è nella cartella d'archivio di quel torneo. Quella della cartella {cartella} non è andata nel cestino, e il torneo {nome} la sostituirà con la sua raccolta."
            )
        else:
            # Il torneo non ha partite in PGN, e non scrive la sua raccolta:
            # quella trovata resta dov'e' (revisione della 10.19.13).
            rimaste.add(chiave)
            testo = _(
                "Nella cartella {cartella} c'era la raccolta delle partite {file} del torneo {torneo}, concluso e archiviato nella cartella {archivio}: il torneo {nome} l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
                "Una copia identica, riletta, adesso è nella cartella d'archivio di quel torneo. Quella della cartella {cartella} non è andata nel cestino, e resta dov'è: la copia nella cartella d'archivio basta, e se vuoi la puoi cancellare tu."
            )
        return RaccoltaInSalvo(
            True,
            testo.format(
                cartella=cartella,
                file=nome_file,
                torneo=dati.get("name", nome),
                archivio=_cartella_nell_archivio(json_archiviato),
                nome=nome,
            ),
            di_un_altra_edizione=True,
        )
    if solo_archiviate and not trovata:
        return RaccoltaInSalvo(True)
    if cestino(percorso):
        return RaccoltaInSalvo(
            True,
            _(
                "Nella cartella {cartella} c'era la raccolta delle partite {file}, che non è del torneo {nome}: il torneo l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
                "È andata nel cestino di Windows, da dove si può recuperare."
            ).format(cartella=cartella, file=nome_file, nome=nome),
        )
    return RaccoltaInSalvo(
        False,
        _(
            "Nella cartella {cartella} c'è la raccolta delle partite {file}, che non è del torneo {nome}: il torneo la sostituirebbe con la sua raccolta, o la cancellerebbe.\n"
            "Non si è potuta mettere in salvo, né nella cartella d'archivio di un torneo concluso con lo stesso nome né nel cestino di Windows, per esempio perché quel disco non ha il cestino."
        ).format(cartella=cartella, file=nome_file, nome=nome),
    )


def raccolta_rimasta_all_apertura(torneo, file_del_torneo):
    """La chiave di percorso della raccolta delle partite del torneo, con
    il file file_del_torneo, se all'apertura del torneo e' una raccolta
    rimasta: al percorso dove il torneo la scriverebbe c'e' una raccolta che
    ha partite che il torneo non ha, con _da_mettere_in_salvo; altrimenti
    None. Non lo e' la raccolta di un'altra edizione archiviata, che la
    guardia, raccolta_altrui_in_salvo, riconosce con
    _edizioni_della_raccolta: segue la strada della guardia. Non lo e'
    nemmeno, e il confronto non si fa, la raccolta identica a quella che il
    torneo scriverebbe, come quella di un torneo aperto e salvato ogni
    giorno nella finestra, o giocato poi in console, che aggiunge soltanto
    partite senza PGN. La finestra la chiede a ogni apertura di un torneo,
    e la passa ad aggiorna_la_raccolta_pgn fra le ritrovate; la
    finalizzazione, nella finestra e in console, prima di scrivere la
    raccolta del torneo.
    Nata con la revisione della 10.19.13 (issue 66, decisione di Gabriele
    del 4 novembre 2026): la memoria delle raccolte rimaste nasce vuota a
    ogni avvio, e dopo una chiusura di Tornello il primo PGN nuovo
    sostituiva una raccolta rimasta senza metterla nella cartella backup, e
    le partite di prima si perdevano. La memoria si ricostruisce dal disco,
    senza campi nuovi nel file del torneo e senza file in piu'. Nella prima
    stesura della revisione era rimasta soltanto la raccolta di un torneo
    senza partite in PGN: un ripristino dalla finestra Copie di sicurezza, che ridava al
    torneo le partite in PGN di una copia, o una copia nella cartella backup
    non riuscita, con il torneo salvato con il suo PGN nuovo, lasciavano
    dopo una chiusura una raccolta con le partite di prima che il primo
    salvataggio sostituiva senza copia, e cosi' la finalizzazione in console
    (decisione di Gabriele del 4 novembre 2026).
    Una raccolta che non si legge, per esempio perche' un altro programma la
    tiene aperta, e' rimasta, perche' non si puo' dire che non abbia partite
    che il torneo non ha: aggiorna_la_raccolta_pgn non la sostituisce finche'
    non si legge, e lo dice come un errore di scrittura (correzione della
    stessa revisione)."""
    from reports import byte_della_raccolta_pgn, file_della_raccolta_pgn

    percorso = file_della_raccolta_pgn(torneo, file_del_torneo)
    if not os.path.isfile(percorso):
        return None
    proprio = byte_della_raccolta_pgn(torneo)
    if proprio is not None and _contiene(percorso, proprio):
        return None
    try:
        if not _da_mettere_in_salvo(torneo, file_del_torneo, percorso):
            return None
    except OSError:
        pass
    return _chiave_del_percorso(percorso)


def _da_mettere_in_salvo(torneo, file_del_torneo, percorso):
    """Vero se la raccolta delle partite percorso, al posto di quella del
    torneo con il file file_del_torneo, ha partite che il torneo non ha,
    con _partite_che_il_torneo_non_ha, e non e' la raccolta di un'altra
    edizione archiviata, che la guardia, raccolta_altrui_in_salvo,
    riconosce con _edizioni_della_raccolta, e le cui partite sono nel json
    di quell'edizione: la regola di Gabriele per una raccolta rimasta (4
    novembre 2026), la stessa all'apertura del torneo,
    raccolta_rimasta_all_apertura, e prima di sostituirla,
    aggiorna_la_raccolta_pgn. Un file che non si legge solleva OSError.
    Nata con la correzione della revisione della 10.19.13: fino ad allora la
    copia prima di sostituirla non guardava le altre edizioni, e nella
    stessa sessione la raccolta di un'altra edizione, gia' copiata nella sua
    cartella d'archivio e rimasta perche' il cestino non l'aveva presa,
    andava anche nella cartella backup al primo PGN nuovo."""
    if not _partite_che_il_torneo_non_ha(torneo, percorso):
        return False
    return next(_edizioni_della_raccolta(torneo, file_del_torneo, percorso), None) is None


def _gia_nella_cartella_backup(percorso):
    """Vero se l'ultima copia del file percorso nella cartella backup, di
    qualunque momento, e' identica byte per byte al file, come per le copie
    della chiusura del programma (copie_di_chiusura di utils.py): la
    raccolta e' gia' in salvo, e un'altra copia non serve. Nata con la
    correzione della revisione della 10.19.13: una raccolta rimasta che si
    legge ma non si riscrive, per esempio aperta in un visualizzatore di PGN
    che non lascia scrivere, resta fra le rimaste dopo la copia, e ogni
    salvataggio ne faceva un'altra copia identica, in silenzio, che con la
    regola delle ultime dieci copie poteva spingere fuori copie piu' vecchie
    e diverse della stessa raccolta."""
    from copie_di_sicurezza import ultima_copia_di
    from utils import stessi_byte

    ultima = ultima_copia_di(percorso, user_data_path("backup"))
    return bool(ultima) and stessi_byte(percorso, ultima)


def aggiorna_la_raccolta_pgn(torneo, file_del_torneo, cestino=None, rimaste=None, ritrovate=None):
    """Scrive la raccolta delle partite in PGN del torneo, con il contenuto
    di byte_della_raccolta_pgn, al percorso di file_della_raccolta_pgn: lo
    fa ogni salvataggio della finestra, dopo raccolta_altrui_in_salvo, e
    dalla 10.19.13 la finalizzazione, nella finestra e in console, perche'
    l'archivio abbia la raccolta del torneo com'e' alla fine (issue 66). La
    console la raccolta non la scrive mai, e fino alla 10.19.10 la sua
    finalizzazione portava in archivio quella che trovava, o nessuna.
    Risponde con una RaccoltaAggiornata.
    Se il torneo non ha piu' partite in PGN, per esempio dopo una Time
    Machine, la raccolta che c'e' va nel cestino con cestino, la funzione
    che manda un percorso nel cestino e risponde vero se ci e' riuscita, e
    senza, quella del programma: fino alla 10.19.10 si cancellava per sempre
    con os.remove (decisione di Gabriele del 4 novembre 2026). Se il cestino
    non la prende resta dov'e', mai cancellata per sempre, entra in rimaste,
    e la risposta ha il suo percorso, da dire con raccolta_rimasta.
    rimaste e' l'insieme, come chiavi di percorso, delle raccolte che il
    cestino non ha preso, lo stesso di raccolta_altrui_in_salvo: per una che
    c'e' gia' il cestino non si riprova, e la risposta ha gia_detta vero.
    Dalla revisione della 10.19.13 una raccolta rimasta, prima di essere
    sostituita dalla raccolta nuova, va nella cartella backup, con una copia
    riletta: fino ad allora le partite di prima si perdevano al primo PGN
    nuovo, mentre il messaggio prometteva che Tornello non le cancellava.
    La copia si fa se la raccolta ha ancora partite che il torneo non ha, e
    non e' quella di un'altra edizione archiviata, con _da_mettere_in_salvo,
    la stessa regola dell'apertura (decisione di Gabriele del 4 novembre
    2026): se il torneo le ha di nuovo tutte, anche con un altro risultato,
    non c'e' niente da perdere, e le partite di un'altra edizione sono nel
    suo json, e la guardia ne ha gia' messo la raccolta nella sua cartella
    d'archivio. Non si fa nemmeno quando l'ultima copia della raccolta nella
    cartella backup le e' identica, con _gia_nella_cartella_backup: una
    raccolta che si legge ma non si riscrive resta fra le rimaste, e fino
    alla correzione della stessa revisione ogni salvataggio ne faceva
    un'altra copia identica.
    Se la copia non riesce, la raccolta resta com'e', e la risposta ha
    copia_non_riuscita vero e la frase in non_scritta. Un errore di
    scrittura si stampa, come sempre, la raccolta di prima resta com'era, e
    dalla stessa revisione la frase sta in non_scritta, perche' la
    finalizzazione lo dica: fino ad allora l'archivio restava senza raccolta
    senza nessun avviso. Una raccolta rimasta che non si legge, per esempio
    perche' un altro programma la tiene aperta, non si sostituisce, perche'
    puo' avere partite che il torneo non ha, e la risposta lo dice come un
    errore di scrittura, con l'errore della lettura: fino alla correzione
    della stessa revisione la copia non riusciva, e la frase diceva che la
    raccolta aveva partite che il torneo non ha anche quando era quella del
    torneo. In tutti e due i casi la risposta ha in errore il motivo che da'
    il sistema, che la finestra dice nel suo messaggio: fino alla decisione
    di Gabriele del 5 novembre 2026 nella finestra c'era soltanto la riga
    in console.
    ritrovate e' l'insieme, come chiavi di percorso, delle raccolte rimaste
    ritrovate sul disco all'apertura del loro torneo, dopo una chiusura di
    Tornello, o alla finalizzazione, con raccolta_rimasta_all_apertura: per
    una di loro il salvataggio senza partite in PGN riprova il cestino, come
    per ogni raccolta, e se il cestino non la prende diventa una delle
    rimaste; quando il torneo ha partite in PGN, prima di essere sostituita
    va nella cartella backup, come le rimaste (revisione della 10.19.13,
    decisione di Gabriele del 4 novembre 2026). Fino ad allora la memoria
    delle rimaste nasceva vuota a ogni avvio, e il primo PGN nuovo dopo una
    chiusura sostituiva la raccolta senza copia."""
    from reports import byte_della_raccolta_pgn, file_della_raccolta_pgn
    from utils import copia_di_sicurezza, delete_file_to_trash, stessi_byte

    cestino = cestino or delete_file_to_trash
    rimaste = set() if rimaste is None else rimaste
    ritrovate = set() if ritrovate is None else ritrovate
    percorso = file_della_raccolta_pgn(torneo, file_del_torneo)
    chiave = _chiave_del_percorso(percorso)
    cartella, file = os.path.split(percorso)
    contenuto = byte_della_raccolta_pgn(torneo)
    if contenuto is not None:
        if chiave in ritrovate:
            ritrovate.discard(chiave)
            rimaste.add(chiave)
        try:
            # Una raccolta rimasta che non si legge solleva OSError da
            # _da_mettere_in_salvo, e non si sostituisce: la frase e' quella
            # della scrittura che non riesce.
            if (
                chiave in rimaste
                and os.path.isfile(percorso)
                and not _contiene(percorso, contenuto)
                and _da_mettere_in_salvo(torneo, file_del_torneo, percorso)
                and not _gia_nella_cartella_backup(percorso)
            ):
                copia = copia_di_sicurezza(percorso, "pre_sostituzione_raccolta")
                if not copia or not stessi_byte(percorso, copia):
                    return RaccoltaAggiornata(
                        non_scritta=_(
                            "La raccolta delle partite {file}, nella cartella {cartella}, ha partite che il torneo {nome} non ha: prima di sostituirla con la raccolta nuova Tornello doveva metterne una copia nella cartella backup, e la copia non è riuscita. Resta com'è, e la raccolta nuova non è stata scritta."
                        ).format(file=file, cartella=cartella, nome=torneo.get("name", "")),
                        copia_non_riuscita=True,
                    )
            with open(percorso, "wb") as f:
                f.write(contenuto)
        except OSError as e:
            print(f"Errore durante il salvataggio della raccolta PGN: {e}")
            return RaccoltaAggiornata(
                non_scritta=_("La raccolta delle partite {file} del torneo {nome} non si è potuta scrivere nella cartella {cartella}: {errore}").format(
                    file=file, nome=torneo.get("name", ""), cartella=cartella, errore=e
                ),
                errore=e.strerror or str(e),
            )
        rimaste.discard(chiave)
        return RaccoltaAggiornata()
    if not os.path.isfile(percorso):
        rimaste.discard(chiave)
        ritrovate.discard(chiave)
        return RaccoltaAggiornata()
    if chiave in rimaste:
        return RaccoltaAggiornata(rimasta=percorso, gia_detta=True)
    ritrovate.discard(chiave)
    if cestino(percorso):
        return RaccoltaAggiornata()
    rimaste.add(chiave)
    return RaccoltaAggiornata(rimasta=percorso)


def raccolta_rimasta(percorso, nome):
    """La frase per la raccolta delle partite percorso del torneo nome, che
    doveva andare nel cestino perche' il torneo non ha piu' partite in PGN,
    e che il cestino non ha preso (aggiorna_la_raccolta_pgn)."""
    cartella, file = os.path.split(percorso)
    return _(
        "Il torneo {nome} non ha più partite in PGN, e la sua raccolta delle partite {file}, nella cartella {cartella}, doveva andare nel cestino di Windows, che non l'ha presa, per esempio perché quel disco non ha il cestino. Resta dov'è, con le partite di prima: Tornello non la cancella per sempre."
    ).format(nome=nome, file=file, cartella=cartella)
