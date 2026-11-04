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
    mettere in salvo, oppure None se non c'era niente da dire."""

    in_salvo: bool
    testo: str | None = None


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


def coincidenza_del_nome(nome, escluso=None):
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
    ripulito = _nome_ripulito(nome)
    for percorso in in_cartella:
        if os.path.basename(percorso).lower() in (del_database, delle_impostazioni):
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


def raccolta_altrui_in_salvo(torneo, file_del_torneo, solo_archiviate=False, cestino=None):
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
    faceva."""
    from db_players import identita_del_torneo
    from reports import byte_della_raccolta_pgn, file_della_raccolta_pgn
    from ui import _copia_verificata
    from utils import delete_file_to_trash, stessi_byte

    cestino = cestino or delete_file_to_trash
    percorso = file_della_raccolta_pgn(torneo, file_del_torneo)
    if not os.path.isfile(percorso):
        return RaccoltaInSalvo(True)
    proprio = byte_della_raccolta_pgn(torneo)
    if proprio is not None and _contiene(percorso, proprio):
        return RaccoltaInSalvo(True)
    cartella, nome_file = os.path.split(percorso)
    nome = torneo.get("name", "")
    trovata = False
    for json_archiviato, dati in edizioni_nell_archivio(nome, escluso=file_del_torneo):
        suo = byte_della_raccolta_pgn(dati) if dati else None
        if suo is None or not _contiene(percorso, suo):
            continue
        if torneo.get("start_date") and identita_del_torneo(dati) == identita_del_torneo(torneo):
            continue
        trovata = True
        destinazione = os.path.join(os.path.dirname(json_archiviato), nome_file)
        # Una raccolta diversa gia' nella cartella d'archivio resta com'e':
        # quella trovata va nel cestino, piu' sotto.
        if os.path.exists(destinazione) and not stessi_byte(percorso, destinazione):
            break
        if not os.path.exists(destinazione) and not _copia_verificata(percorso, destinazione, lambda _frase: None):
            break
        if cestino(percorso):
            testo = _(
                "Nella cartella {cartella} c'era la raccolta delle partite {file} del torneo {torneo}, concluso e archiviato nella cartella {archivio}: il torneo {nome} l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
                "Una copia identica, riletta, adesso è nella cartella d'archivio di quel torneo, e quella della cartella {cartella} è andata nel cestino di Windows."
            )
        else:
            testo = _(
                "Nella cartella {cartella} c'era la raccolta delle partite {file} del torneo {torneo}, concluso e archiviato nella cartella {archivio}: il torneo {nome} l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
                "Una copia identica, riletta, adesso è nella cartella d'archivio di quel torneo. Quella della cartella {cartella} non è andata nel cestino, e il torneo {nome} la sostituirà con la sua raccolta, o la cancellerà."
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


def aggiorna_la_raccolta_pgn(torneo, file_del_torneo, cestino=None):
    """Scrive la raccolta delle partite in PGN del torneo, con il contenuto
    di byte_della_raccolta_pgn, al percorso di file_della_raccolta_pgn: lo
    fa ogni salvataggio della finestra, dopo raccolta_altrui_in_salvo, e
    dalla 10.19.13 la finalizzazione, nella finestra e in console, perche'
    l'archivio abbia la raccolta del torneo com'e' alla fine (issue 66). La
    console la raccolta non la scrive mai, e fino alla 10.19.10 la sua
    finalizzazione portava in archivio quella che trovava, o nessuna.
    Se il torneo non ha piu' partite in PGN, per esempio dopo una Time
    Machine, la raccolta che c'e' va nel cestino con cestino, la funzione
    che manda un percorso nel cestino e risponde vero se ci e' riuscita, e
    senza, quella del programma: fino alla 10.19.10 si cancellava per sempre
    con os.remove (decisione di Gabriele del 4 novembre 2026). Se il cestino
    non la prende resta dov'e', mai cancellata per sempre, e la risposta e'
    il suo percorso, da dire con raccolta_rimasta; altrimenti None. Un
    errore di scrittura si stampa, come sempre, e la raccolta di prima resta
    com'era."""
    from reports import byte_della_raccolta_pgn, file_della_raccolta_pgn
    from utils import delete_file_to_trash

    cestino = cestino or delete_file_to_trash
    percorso = file_della_raccolta_pgn(torneo, file_del_torneo)
    contenuto = byte_della_raccolta_pgn(torneo)
    if contenuto is not None:
        try:
            with open(percorso, "wb") as f:
                f.write(contenuto)
        except OSError as e:
            print(f"Errore durante il salvataggio della raccolta PGN: {e}")
        return None
    if os.path.isfile(percorso) and not cestino(percorso):
        return percorso
    return None


def raccolta_rimasta(percorso, nome):
    """La frase per la raccolta delle partite percorso del torneo nome, che
    doveva andare nel cestino perche' il torneo non ha piu' partite in PGN,
    e che il cestino non ha preso (aggiorna_la_raccolta_pgn)."""
    cartella, file = os.path.split(percorso)
    return _(
        "Il torneo {nome} non ha più partite in PGN, e la sua raccolta delle partite {file}, nella cartella {cartella}, doveva andare nel cestino di Windows, che non l'ha presa, per esempio perché quel disco non ha il cestino. Resta dov'è, con le partite di prima: Tornello non la cancella per sempre."
    ).format(nome=nome, file=file, cartella=cartella)
