"""Le copie di sicurezza: leggerle, confrontarle con lo stato attuale,
ripristinarle e sfoltirle. Issue 39, seconda parte: 10.9.0, 10.10.0 e
10.11.0.

Le copie le fa utils.create_backup, nella cartella backup, sotto l'anno e il
mese in cui nascono, con un nome che dice il file d'origine, il momento e la
data con l'ora: "Tornello - Autunneo2_chiusura_torneo_20260923_160512.json".
Fino alla 10.8.12 il programma sapeva soltanto cancellarle. Qui sta tutto
cio' che serve alla finestra Copie di sicurezza, senza wx: la finestra lo
chiama, e le prove lo usano da sole.

Tre regole valgono per tutto il modulo.
Ogni funzione riceve i percorsi da chi la chiama, raccolti in Percorsi, e non
li prende dalle costanti di config: le prove li danno nella loro cartella
temporanea, e nessuna via dimenticata porta ai file veri. Solo
percorsi_del_programma li chiede a config, al momento della chiamata.
Le copie si leggono con json.load e basta: load_tournament e load_players_db
aggiungono campi e migrano, e una copia letta cosi' non sarebbe piu' lei.
Prima di scrivere sopra un file se ne fa una copia pre_ripristino, e se la
copia non riesce ci si ferma; si scrive in modo atomico e si rilegge, e
niente si cancella: cio' che se ne va finisce nel cestino di Windows.
"""

import contextlib
import copy
import datetime
import glob
import json
import os
import re
import shutil
from dataclasses import dataclass, field

from db_players import (
    identita_del_torneo,
    togli_torneo_dallo_storico,
    voce_di_questo_torneo,
)
from utils import (
    copia_di_sicurezza,
    data_della_copia,
    delete_file_to_trash,
    file_del_torneo,
    sanitize_filename,
    scrivi_json_atomico,
    stessi_byte,
)

# I momenti che create_backup scrive nel nome delle copie. turno_N ha il
# numero del turno appena abbinato.
CONTESTI_NOTI = (
    "creazione",
    r"turno_\d+",
    "chiusura_torneo",
    "chiusura_db",
    "pre_finalize_torneo",
    "pre_finalize_db",
    "pre_rollback",
    "pre_timemachine",
    "pre_ritorno_preparazione",
    "pre_ripristino",
    "pre_archiviazione",
    "rifinalizzazione",
)

# Il nome di una copia: il file d'origine, il momento, la data, l'ora, il
# suffisso delle copie nate nello stesso secondo e l'estensione. Il momento
# si cerca fra quelli noti e in fondo al nome, perche' i nomi dei tornei e dei
# database hanno anche loro i trattini bassi: Players_db_complex_pre_finalize_db.
NOME_DELLA_COPIA = re.compile(
    r"^(?P<base>.+)_(?P<contesto>"
    + "|".join(CONTESTI_NOTI)
    + r")_(?P<giorno>\d{8})_(?P<ora>\d{6})(?:_(?P<numero>\d+))?(?P<estensione>\.[^.]*)?$"
)
# Una copia con la data ma con un momento che questa versione non conosce.
NOME_CON_LA_DATA = re.compile(
    r"^(?P<base>.+)_(?P<giorno>\d{8})_(?P<ora>\d{6})(?:_(?P<numero>\d+))?(?P<estensione>\.[^.]*)?$"
)

# Le copie che la regola di conservazione non tocca mai: quelle della
# finalizzazione, che sono le sole a permettere di riaprire un torneo
# concluso, quelle che la finalizzazione mette da parte, di pre_archiviazione
# e di rifinalizzazione, e quelle fatte prima di un ripristino, che
# permettono di tornare indietro. Decisione di Gabriele del 25 settembre
# 2026. La finestra dice la regola con righe_della_regola, da qui.
CONTESTI_CONSERVATI = (
    "pre_finalize_torneo",
    "pre_finalize_db",
    "pre_archiviazione",
    "rifinalizzazione",
    "pre_ripristino",
)
# Quante copie tiene la regola per ogni origine.
COPIE_DA_TENERE = 10

# Quanti secondi possono separare la copia pre_finalize_db da quella del
# torneo nella stessa finalizzazione: nascono una dopo l'altra.
SECONDI_FRA_LE_COPIE_DELLA_FINALIZZAZIONE = 2

# Le righe di un elenco nel testo di un confronto, oltre le quali si dice
# soltanto quante ne restano.
RIGHE_PER_ELENCO = 15

NOME_DEL_DATABASE = "Tornello - Players_db.json"
PREFISSO = "Tornello - "


def analizza_nome(nome):
    """Le parti del nome di una copia, come dizionario con base, contesto,
    data, numero ed estensione; None se il nome non ha la data di una copia.
    Il contesto e' None per un momento che questa versione non conosce, e la
    data e' None se quella scritta nel nome e' impossibile."""
    trovato = NOME_DELLA_COPIA.match(nome)
    contesto = None
    if trovato:
        contesto = trovato.group("contesto")
    else:
        trovato = NOME_CON_LA_DATA.match(nome)
        if not trovato:
            return None
    try:
        data = datetime.datetime.strptime(
            trovato.group("giorno") + trovato.group("ora"), "%Y%m%d%H%M%S"
        )
    except ValueError:
        data = None
    return {
        "base": trovato.group("base"),
        "contesto": contesto,
        "data": data,
        "numero": int(trovato.group("numero") or 1),
        "estensione": trovato.group("estensione") or "",
    }


def momento_in_parole(contesto):
    """Il momento di una copia detto a parole, come lo mostra la finestra:
    pre_finalize_torneo diventa "prima della finalizzazione". I nomi dei file
    restano quelli di sempre (decisione di Gabriele)."""
    if not contesto:
        return _("momento sconosciuto")
    turno = re.fullmatch(r"turno_(\d+)", contesto)
    if turno:
        return _("al turno {numero} abbinato").format(numero=int(turno.group(1)))
    parole = {
        "creazione": _("alla nascita del torneo"),
        "chiusura_torneo": _("alla chiusura del programma"),
        "chiusura_db": _("alla chiusura del programma"),
        "pre_finalize_torneo": _("prima della finalizzazione"),
        "pre_finalize_db": _("prima della finalizzazione"),
        "pre_rollback": _("prima dell'annullamento del turno"),
        "pre_timemachine": _("prima della Time Machine"),
        "pre_ritorno_preparazione": _("prima del ritorno all'iscrizione"),
        "pre_ripristino": _("prima di un ripristino"),
        "pre_archiviazione": _("prima di una sostituzione in archivio"),
        "rifinalizzazione": _("da una finalizzazione ripetuta"),
    }
    return parole.get(contesto, contesto)


def calcola_eta(nascita, oggi):
    """L'eta' di una copia in mesi e giorni, come coppia di numeri; zero e
    zero per una data futura. Senza dateutil un mese vale trenta giorni.
    Nata come calculate_age nella finestra di pulizia dei backup, che la
    importa da qui."""
    if oggi < nascita:
        return 0, 0
    try:
        from dateutil.relativedelta import relativedelta
    except ImportError:
        giorni = (oggi - nascita).days
        return giorni // 30, giorni % 30
    differenza = relativedelta(oggi, nascita)
    return differenza.years * 12 + differenza.months, differenza.days


def tipo_del_contenuto(dati):
    """Che cosa contiene una copia letta: "torneo", "database" oppure
    "sconosciuto". Il torneo si riconosce per primo, dalla lista dei turni o
    dal nome: schema_version non dice niente, perche' ce l'hanno anche i
    tornei nati dalla procedura guidata o dalla console, che passano da
    Tournament.to_dict, come Autunneo2. Un database e' un dizionario con i
    giocatori, senza turni e senza nome, oppure la lista dei giocatori dello
    schema 1."""
    if isinstance(dati, list):
        return "database" if all(isinstance(g, dict) for g in dati) else "sconosciuto"
    if not isinstance(dati, dict) or not isinstance(dati.get("players"), list):
        return "sconosciuto"
    if isinstance(dati.get("rounds"), list) or dati.get("name"):
        return "torneo"
    if "rounds" in dati or "name" in dati:
        return "sconosciuto"
    return "database"


def leggi_copia(percorso):
    """Il contenuto di una copia, come (tipo, dati, errore). Il tipo e'
    quello di tipo_del_contenuto, oppure "testo" per un report, che non si
    legge, e "illeggibile" per un json rotto, con il motivo in errore."""
    if not percorso.lower().endswith(".json"):
        return "testo", None, None
    try:
        with open(percorso, encoding="utf-8") as f:
            dati = json.load(f)
    except (OSError, ValueError) as errore:
        return "illeggibile", None, str(errore)
    return tipo_del_contenuto(dati), dati, None


def _e_un_bye(partita):
    return partita.get("result") == "BYE" or not partita.get("black_player_id")


def _turni(dati):
    return [t for t in dati.get("rounds") or [] if isinstance(t, dict)]


def _giocatori_del_torneo(dati):
    return [g for g in dati.get("players") or [] if isinstance(g, dict)]


def giocatori_del_database(dati):
    """La lista dei giocatori di un database letto, schema 1 o 2."""
    elenco = dati if isinstance(dati, list) else (dati or {}).get("players") or []
    return [g for g in elenco if isinstance(g, dict)]


def riassunto_torneo(dati):
    """I numeri di un torneo letto da una copia. Sa stare senza i campi che
    le copie vecchie non hanno: quelle delle prove non hanno tournament_id e
    hanno concluded a None."""
    turni = _turni(dati)
    partite = [
        p
        for t in turni
        for p in t.get("matches") or []
        if isinstance(p, dict) and not _e_un_bye(p)
    ]
    completi = sum(
        1
        for t in turni
        if all(p.get("result") is not None for p in t.get("matches") or [] if isinstance(p, dict))
    )
    giocatori = _giocatori_del_torneo(dati)
    return {
        "nome": str(dati.get("name") or ""),
        "identificativo": str(dati.get("tournament_id") or ""),
        "inizio": dati.get("start_date"),
        "fine": dati.get("end_date"),
        "turni_previsti": dati.get("total_rounds"),
        "turni_abbinati": len(turni),
        "turni_completi": completi,
        "turno_corrente": dati.get("current_round"),
        "risultati": sum(1 for p in partite if p.get("result") is not None),
        "partite": len(partite),
        "giocatori": len(giocatori),
        "ritirati": sum(1 for g in giocatori if g.get("withdrawn")),
        "concluso": bool(dati.get("concluded")),
    }


def _chiave_della_voce(voce):
    return (voce.get("tournament_id") or voce.get("tournament_name"), voce.get("date_started"))


def riassunto_database(dati):
    """I numeri di un database dei giocatori letto da una copia: giocatori,
    schema, tornei distinti negli storici e l'ultimo torneo registrato."""
    giocatori = giocatori_del_database(dati)
    tornei = {}
    for giocatore in giocatori:
        for voce in giocatore.get("tournaments_played") or []:
            if isinstance(voce, dict):
                tornei[_chiave_della_voce(voce)] = voce
    ultimo = max(tornei.values(), key=lambda v: str(v.get("date_completed") or ""), default=None)
    return {
        "giocatori": len(giocatori),
        "schema": dati.get("schema_version", 1) if isinstance(dati, dict) else 1,
        "tornei": len(tornei),
        "ultimo_torneo": (ultimo or {}).get("tournament_name"),
        "ultimo_torneo_data": (ultimo or {}).get("date_completed"),
    }


@dataclass
class Copia:
    """Una copia di sicurezza come la mostra la finestra: il file, il suo
    momento, il contenuto riassunto e l'origine, cioe' il torneo o il
    database da cui viene."""

    nome: str
    percorso: str
    dimensione: int
    data: datetime.datetime
    contesto: str | None
    numero: int
    base: str
    tipo: str
    riassunto: dict = field(default_factory=dict)
    errore: str | None = None
    chiave: tuple = ()
    origine: str = ""


def _origine(tipo, base, contesto, riassunto, nome_database):
    """La chiave con cui si raggruppano le copie della stessa origine e il
    nome da mostrare. Un torneo si riconosce dal nome letto nel contenuto,
    ripulito come nei nomi dei file, cosi' le sue copie e i suoi report
    stanno insieme; un database dal nome del file, e quello del programma si
    chiama Database dei giocatori."""
    senza = base[len(PREFISSO):] if base.startswith(PREFISSO) else base
    if tipo == "torneo" and riassunto.get("nome"):
        return ("torneo", sanitize_filename(riassunto["nome"])), riassunto["nome"]
    if tipo == "database" or contesto in ("chiusura_db", "pre_finalize_db"):
        if base.lower() == os.path.splitext(nome_database)[0].lower():
            return ("database", senza.lower()), _("Database dei giocatori")
        return ("database", senza.lower()), senza
    # Un report o un json che non si legge: il nome del torneo viene prima
    # di " - ", dove cominciano i suffissi dei report.
    torneo = senza.split(" - ")[0]
    return ("torneo", torneo), torneo


def descrivi_copia(percorso, nome_database=NOME_DEL_DATABASE):
    """La Copia di un file della cartella backup, con il contenuto letto."""
    nome = os.path.basename(percorso)
    parti = analizza_nome(nome) or {}
    tipo, dati, errore = leggi_copia(percorso)
    if tipo == "torneo":
        riassunto = riassunto_torneo(dati)
    elif tipo == "database":
        riassunto = riassunto_database(dati)
    else:
        riassunto = {}
    base = parti.get("base") or os.path.splitext(nome)[0]
    chiave, origine = _origine(tipo, base, parti.get("contesto"), riassunto, nome_database)
    try:
        dimensione = os.path.getsize(percorso)
    except OSError:
        dimensione = 0
    return Copia(
        nome=nome,
        percorso=percorso,
        dimensione=dimensione,
        data=parti.get("data") or data_della_copia(percorso),
        contesto=parti.get("contesto"),
        numero=parti.get("numero", 1),
        base=base,
        tipo=tipo,
        riassunto=riassunto,
        errore=errore,
        chiave=chiave,
        origine=origine,
    )


def elenca_copie(cartella_backup, nome_database=NOME_DEL_DATABASE):
    """Tutte le copie della cartella backup, scendendo nelle sottocartelle,
    dalla piu' vecchia alla piu' recente, con il contenuto letto. Le 194
    copie della macchina di Gabriele si leggono in qualche centesimo di
    secondo."""
    copie = []
    if not cartella_backup or not os.path.isdir(cartella_backup):
        return copie
    for cartella, _sottocartelle, files in os.walk(cartella_backup):
        for nome in files:
            percorso = os.path.join(cartella, nome)
            if os.path.isfile(percorso):
                copie.append(descrivi_copia(percorso, nome_database))
    copie.sort(key=lambda c: (c.data, c.numero, c.nome))
    return copie


def raggruppa_per_origine(copie):
    """Le origini delle copie, come lista di (chiave, nome, copie), in
    ordine di nome. Il nome di un torneo e' quello letto in una sua copia;
    se nessuna si legge, quello del file."""
    nomi, gruppi = {}, {}
    for c in copie:
        if c.tipo == "torneo" or c.chiave not in nomi:
            nomi[c.chiave] = c.origine
        gruppi.setdefault(c.chiave, []).append(c)
    return sorted(((k, nomi[k], elenco) for k, elenco in gruppi.items()), key=lambda g: g[1].lower())


def contenuto_breve(copia, con_origine=False):
    """Il contenuto di una copia in poche parole, per la lista: per un
    torneo "T1/6, 12/13 ris., 26 gioc.", per un database "54 gioc."."""
    r = copia.riassunto
    if copia.tipo == "torneo":
        if not r["turni_abbinati"]:
            testo = _("in preparazione, {giocatori} gioc.").format(giocatori=r["giocatori"])
        else:
            testo = _("T{abbinati}/{previsti}, {risultati}/{partite} ris., {giocatori} gioc.").format(
                abbinati=r["turni_abbinati"],
                previsti=r["turni_previsti"] if r["turni_previsti"] is not None else "?",
                risultati=r["risultati"],
                partite=r["partite"],
                giocatori=r["giocatori"],
            )
        if r["ritirati"]:
            testo += _(", {ritirati} rit.").format(ritirati=r["ritirati"])
        if r["concluso"]:
            testo += _(", concluso")
    elif copia.tipo == "database":
        testo = _("{giocatori} gioc.").format(giocatori=r["giocatori"])
    elif copia.tipo == "testo":
        testo = _("report di testo")
    elif copia.tipo == "illeggibile":
        testo = _("illeggibile")
    else:
        testo = _("contenuto sconosciuto")
    if con_origine:
        testo = f"{copia.origine}, {testo}"
    return testo


def _giorno(data):
    return data if data else _("non indicata")


def dettagli_della_copia(copia, oggi):
    """Le righe dei dettagli di una copia, in sola lettura nella finestra:
    corte, per la barra braille da quaranta celle."""
    mesi, giorni = calcola_eta(copia.data, oggi)
    righe = [
        _("Origine: {origine}").format(origine=copia.origine),
        _("Momento: {momento}").format(momento=momento_in_parole(copia.contesto)),
        _("Data: {data}").format(data=copia.data.strftime("%Y-%m-%d %H:%M:%S")),
        _("Età: {mesi} mesi, {giorni} giorni").format(mesi=mesi, giorni=giorni),
    ]
    r = copia.riassunto
    if copia.tipo == "torneo":
        if r["concluso"]:
            stato = _("concluso")
        elif r["turni_abbinati"]:
            stato = _("in corso")
        else:
            stato = _("in preparazione")
        righe.append(_("Torneo: {nome}").format(nome=r["nome"]))
        if r["identificativo"]:
            righe.append(_("Identificativo: {id}").format(id=r["identificativo"]))
        righe += [
            _("Inizio: {data}").format(data=_giorno(r["inizio"])),
            _("Fine: {data}").format(data=_giorno(r["fine"])),
            _("Stato: {stato}").format(stato=stato),
            _("Turni abbinati: {abbinati} su {previsti}").format(
                abbinati=r["turni_abbinati"],
                previsti=r["turni_previsti"] if r["turni_previsti"] is not None else "?",
            ),
            _("Turni completi: {completi}").format(completi=r["turni_completi"]),
            _("Turno corrente: {turno}").format(turno=r["turno_corrente"] if r["turno_corrente"] is not None else "?"),
            _("Risultati: {risultati} su {partite}").format(risultati=r["risultati"], partite=r["partite"]),
            _("Giocatori: {giocatori}").format(giocatori=r["giocatori"]),
            _("Ritirati: {ritirati}").format(ritirati=r["ritirati"]),
        ]
    elif copia.tipo == "database":
        righe += [
            _("Database dei giocatori"),
            _("Giocatori: {giocatori}").format(giocatori=r["giocatori"]),
            _("Schema: {schema}").format(schema=r["schema"]),
            _("Tornei negli storici: {tornei}").format(tornei=r["tornei"]),
        ]
        if r["ultimo_torneo"]:
            righe.append(_("Ultimo torneo registrato:"))
            righe.append(f"{r['ultimo_torneo']}, {_giorno(r['ultimo_torneo_data'])}")
    elif copia.tipo == "testo":
        righe.append(_("Un report di testo del torneo."))
    elif copia.tipo == "illeggibile":
        righe.append(_("Il file non si legge:"))
        righe.append(str(copia.errore))
    else:
        righe.append(_("Non è né un torneo né un database."))
    righe += [
        _("File:"),
        copia.nome,
        _("Dimensione: {kb} KB").format(kb=max(1, round(copia.dimensione / 1024))),
    ]
    return righe


def _nome_del_giocatore(giocatore, pid=""):
    nome = " ".join(p for p in (giocatore.get("last_name"), giocatore.get("first_name")) if p)
    return nome or str(giocatore.get("id") or pid or "?")


def _numero_leggibile(valore):
    try:
        numero = float(valore)
    except (TypeError, ValueError):
        return str(valore)
    return str(int(numero)) if numero == int(numero) else f"{numero:.1f}"


def _elenco(titolo, voci):
    """Un titolo con il numero delle voci, e le voci una per riga, fino a
    RIGHE_PER_ELENCO; delle altre si dice quante sono."""
    if not voci:
        return []
    righe = [titolo.format(numero=len(voci))]
    righe += [f"  {v}" for v in voci[:RIGHE_PER_ELENCO]]
    if len(voci) > RIGHE_PER_ELENCO:
        righe.append(_("  e altre {numero}").format(numero=len(voci) - RIGHE_PER_ELENCO))
    return righe


def _partite(dati):
    return {
        (t.get("round"), p.get("id")): p
        for t in _turni(dati)
        for p in t.get("matches") or []
        if isinstance(p, dict)
    }


def _senza_cache(dati):
    return {k: v for k, v in dati.items() if k != "players_dict"}


def confronta_torneo(copia, attuale):
    """Che cosa cambierebbe rimettendo il torneo della copia al posto di
    quello attuale, partita per partita: turni e risultati che si
    perderebbero o cambierebbero, PGN e programmazioni perse, iscritti in
    piu' o in meno, ritiri annullati, e un torneo concluso che tornerebbe in
    corso. Le partite si riconoscono dal turno e dal loro numero."""
    pc, pa = _partite(copia), _partite(attuale)
    gc = {g.get("id"): g for g in _giocatori_del_torneo(copia)}
    ga = {g.get("id"): g for g in _giocatori_del_torneo(attuale)}
    nomi = {pid: _nome_del_giocatore(g, pid) for pid, g in {**gc, **ga}.items()}
    cognomi = {pid: str(g.get("last_name") or pid) for pid, g in {**gc, **ga}.items()}
    turni_copia = {t.get("round") for t in _turni(copia)}
    turni_attuali = {t.get("round") for t in _turni(attuale)}

    def ordinate(chiavi):
        return sorted(chiavi, key=lambda k: (k[0] or 0, k[1] or 0))

    esito = {
        "identico": _senza_cache(copia) == _senza_cache(attuale),
        "turni_persi": sorted(t for t in turni_attuali - turni_copia if t is not None),
        "turni_ritrovati": sorted(t for t in turni_copia - turni_attuali if t is not None),
        "risultati_persi": [],
        "risultati_diversi": [],
        "risultati_ritrovati": [],
        "pgn_persi": [],
        "pgn_diversi": [],
        "programmazioni_perse": [],
        "programmazioni_diverse": [],
        "nomi": nomi,
        "cognomi": cognomi,
    }
    for k in ordinate(pa.keys() | pc.keys()):
        a, c = pa.get(k) or {}, pc.get(k) or {}
        partita = a or c
        if _e_un_bye(partita):
            continue
        ra, rc = a.get("result"), c.get("result")
        if ra is not None and rc is None:
            esito["risultati_persi"].append((k, a))
        elif ra is not None and rc is not None and ra != rc:
            esito["risultati_diversi"].append((k, a, c))
        elif ra is None and rc is not None:
            esito["risultati_ritrovati"].append((k, c))
        if a.get("pgn") and not c.get("pgn"):
            esito["pgn_persi"].append((k, a))
        elif a.get("pgn") and c.get("pgn") and a["pgn"] != c["pgn"]:
            esito["pgn_diversi"].append((k, a))
        if a.get("schedule_info") and not c.get("schedule_info"):
            esito["programmazioni_perse"].append((k, a))
        elif a.get("schedule_info") and c.get("schedule_info") and a["schedule_info"] != c["schedule_info"]:
            esito["programmazioni_diverse"].append((k, a))
    comuni = ga.keys() & gc.keys()
    esito["iscritti_in_meno"] = sorted(ga.keys() - gc.keys(), key=lambda p: nomi[p])
    esito["iscritti_in_piu"] = sorted(gc.keys() - ga.keys(), key=lambda p: nomi[p])
    esito["ritiri_annullati"] = sorted(
        (p for p in comuni if ga[p].get("withdrawn") and not gc[p].get("withdrawn")), key=lambda p: nomi[p]
    )
    esito["ritiri_ritrovati"] = sorted(
        (p for p in comuni if gc[p].get("withdrawn") and not ga[p].get("withdrawn")), key=lambda p: nomi[p]
    )
    esito["da_concluso_a_in_corso"] = bool(attuale.get("concluded")) and not copia.get("concluded")
    return esito


def _la_partita(cognomi, chiave, partita):
    """Una partita detta in breve: "T1, Rossi-Bianchi"."""
    bianco, nero = partita.get("white_player_id"), partita.get("black_player_id")
    return _("T{turno}, {bianco}-{nero}").format(
        turno=chiave[0], bianco=cognomi.get(bianco, bianco), nero=cognomi.get(nero, nero)
    )


def righe_del_confronto_torneo(esito):
    """Il confronto di confronta_torneo in righe da leggere."""
    if esito["identico"]:
        return [_("La copia è uguale allo stato attuale.")]
    nomi, cognomi = esito["nomi"], esito["cognomi"]
    righe = []
    if esito["turni_persi"]:
        righe.append(_("Turni che si perderebbero: {turni}").format(turni=", ".join(str(t) for t in esito["turni_persi"])))
    if esito["turni_ritrovati"]:
        righe.append(_("Turni che tornerebbero: {turni}").format(turni=", ".join(str(t) for t in esito["turni_ritrovati"])))
    righe += _elenco(
        _("Risultati che si perderebbero: {numero}"),
        [f"{_la_partita(cognomi, k, p)}: {p.get('result')}" for k, p in esito["risultati_persi"]],
    )
    righe += _elenco(
        _("Risultati che cambierebbero: {numero}"),
        [
            _("{partita}: {oggi} diventa {copia}").format(partita=_la_partita(cognomi, k, a), oggi=a.get("result"), copia=c.get("result"))
            for k, a, c in esito["risultati_diversi"]
        ],
    )
    righe += _elenco(
        _("Risultati che tornerebbero: {numero}"),
        [f"{_la_partita(cognomi, k, p)}: {p.get('result')}" for k, p in esito["risultati_ritrovati"]],
    )
    righe += _elenco(_("PGN che si perderebbero: {numero}"), [_la_partita(cognomi, k, p) for k, p in esito["pgn_persi"]])
    righe += _elenco(_("PGN che cambierebbero: {numero}"), [_la_partita(cognomi, k, p) for k, p in esito["pgn_diversi"]])
    righe += _elenco(
        _("Programmazioni che si perderebbero: {numero}"), [_la_partita(cognomi, k, p) for k, p in esito["programmazioni_perse"]]
    )
    righe += _elenco(
        _("Programmazioni che cambierebbero: {numero}"), [_la_partita(cognomi, k, p) for k, p in esito["programmazioni_diverse"]]
    )
    righe += _elenco(_("Iscritti che sparirebbero: {numero}"), [nomi[p] for p in esito["iscritti_in_meno"]])
    righe += _elenco(_("Iscritti che tornerebbero: {numero}"), [nomi[p] for p in esito["iscritti_in_piu"]])
    righe += _elenco(_("Ritiri che si annullerebbero: {numero}"), [nomi[p] for p in esito["ritiri_annullati"]])
    righe += _elenco(_("Ritiri che tornerebbero: {numero}"), [nomi[p] for p in esito["ritiri_ritrovati"]])
    if esito["da_concluso_a_in_corso"]:
        righe.append(_("Il torneo, oggi concluso, tornerebbe in corso."))
    if not righe:
        righe.append(
            _("Turni, risultati, PGN, programmazioni, iscritti e ritiri restano gli stessi: cambiano solo altri dati del torneo.")
        )
    return righe


def tornei_attivi(radice, nome_database=NOME_DEL_DATABASE):
    """I tornei non conclusi della cartella del programma, letti."""
    tornei = []
    esclusi = {nome_database.lower(), "tornello - settings.json"}
    for percorso in sorted(glob.glob(os.path.join(glob.escape(radice), "Tornello - *.json"))):
        if os.path.basename(percorso).lower() in esclusi:
            continue
        tipo, dati, _errore = leggi_copia(percorso)
        if tipo == "torneo" and not dati.get("concluded"):
            tornei.append(dati)
    return tornei


def iscritti_dei_tornei_attivi(radice, nome_database=NOME_DEL_DATABASE, tornei=None):
    """I tornei non conclusi della cartella del programma, come lista di
    (nome del torneo, identificativi dei giocatori iscritti). Serve al
    confronto dei database: un iscritto che nella copia non c'e' perderebbe
    la sua scheda. tornei, se c'e', e' quello che tornei_attivi ha gia'
    letto."""
    if tornei is None:
        tornei = tornei_attivi(radice, nome_database)
    return [(str(dati.get("name") or ""), {g.get("id") for g in _giocatori_del_torneo(dati)}) for dati in tornei]


def giocatori_con_il_torneo(giocatori, dati):
    """I giocatori di un database, lista di schede, che hanno nello storico
    il torneo dati, riconosciuto come lo riconosce la finalizzazione: vuol
    dire che il torneo e' gia' stato finalizzato."""
    identificativo, inizio = identita_del_torneo(dati)
    nome = dati.get("name")
    return [
        g
        for g in giocatori
        if any(
            isinstance(v, dict) and voce_di_questo_torneo(v, identificativo, nome, inizio)
            for v in g.get("tournaments_played") or []
        )
    ]


def confronta_database(copia, attuale, tornei_attivi=()):
    """Che cosa cambierebbe rimettendo il database della copia al posto di
    quello attuale: giocatori che sparirebbero o tornerebbero, Elo che
    cambierebbero, dal salto piu' grande, partite, storici e medaglie, e gli
    iscritti ai tornei in corso che nella copia non esistono."""
    gc = {g.get("id"): g for g in giocatori_del_database(copia) if g.get("id")}
    ga = {g.get("id"): g for g in giocatori_del_database(attuale) if g.get("id")}
    nomi = {pid: _nome_del_giocatore(g, pid) for pid, g in {**gc, **ga}.items()}
    elo = []
    for pid in ga.keys() & gc.keys():
        for campo, nome_campo in (("current_elo", "Elo"), ("elo_rapid", "rapid"), ("elo_blitz", "blitz")):
            try:
                oggi, nella_copia = float(ga[pid].get(campo)), float(gc[pid].get(campo))
            except (TypeError, ValueError):
                continue
            if oggi != nella_copia:
                elo.append((pid, nome_campo, oggi, nella_copia))
    elo.sort(key=lambda e: (-abs(e[3] - e[2]), nomi[e[0]]))
    voci_c = {pid: {_chiave_della_voce(v): v for v in g.get("tournaments_played") or [] if isinstance(v, dict)} for pid, g in gc.items()}
    voci_a = {pid: {_chiave_della_voce(v): v for v in g.get("tournaments_played") or [] if isinstance(v, dict)} for pid, g in ga.items()}
    storici_persi, storici_ritrovati = {}, {}
    for pid in ga.keys() & gc.keys():
        for chiave, voce in voci_a[pid].items():
            if chiave not in voci_c[pid]:
                storici_persi.setdefault(voce.get("tournament_name") or str(chiave[0]), set()).add(pid)
        for chiave, voce in voci_c[pid].items():
            if chiave not in voci_a[pid]:
                storici_ritrovati.setdefault(voce.get("tournament_name") or str(chiave[0]), set()).add(pid)
    assenti = [
        (torneo, pid)
        for torneo, iscritti in tornei_attivi
        for pid in sorted(iscritti, key=str)
        if pid and pid not in gc
    ]
    return {
        "identico": copia == attuale,
        "nomi": nomi,
        "sparirebbero": sorted(ga.keys() - gc.keys(), key=lambda p: nomi[p]),
        "tornerebbero": sorted(gc.keys() - ga.keys(), key=lambda p: nomi[p]),
        "elo": elo,
        "partite": sorted(
            (p for p in ga.keys() & gc.keys() if ga[p].get("games_played") != gc[p].get("games_played")), key=lambda p: nomi[p]
        ),
        "medaglie": sorted(
            (p for p in ga.keys() & gc.keys() if ga[p].get("medals") != gc[p].get("medals")), key=lambda p: nomi[p]
        ),
        "storici_persi": storici_persi,
        "storici_ritrovati": storici_ritrovati,
        "assenti_dai_tornei": assenti,
    }


def righe_del_confronto_database(esito):
    """Il confronto di confronta_database in righe da leggere."""
    if esito["identico"]:
        return [_("La copia è uguale al database attuale.")]
    nomi = esito["nomi"]
    righe = []
    righe += _elenco(_("Giocatori che sparirebbero: {numero}"), [nomi[p] for p in esito["sparirebbero"]])
    righe += _elenco(_("Giocatori che tornerebbero: {numero}"), [nomi[p] for p in esito["tornerebbero"]])
    righe += _elenco(
        _("Elo che cambierebbero: {numero}"),
        [
            _("{nome}, {campo} {oggi} a {copia} ({differenza})").format(
                nome=nomi[pid],
                campo=campo,
                oggi=_numero_leggibile(oggi),
                copia=_numero_leggibile(nella_copia),
                differenza=("+" if nella_copia > oggi else "") + _numero_leggibile(nella_copia - oggi),
            )
            for pid, campo, oggi, nella_copia in esito["elo"]
        ],
    )
    if esito["partite"]:
        righe.append(_("Partite giocate diverse: {numero} giocatori").format(numero=len(esito["partite"])))
    righe += _elenco(
        _("Tornei che uscirebbero dagli storici: {numero}"),
        [_("{torneo}, {numero} giocatori").format(torneo=t, numero=len(p)) for t, p in sorted(esito["storici_persi"].items())],
    )
    righe += _elenco(
        _("Tornei che tornerebbero negli storici: {numero}"),
        [_("{torneo}, {numero} giocatori").format(torneo=t, numero=len(p)) for t, p in sorted(esito["storici_ritrovati"].items())],
    )
    if esito["medaglie"]:
        righe.append(_("Medaglie diverse: {numero} giocatori").format(numero=len(esito["medaglie"])))
    righe += _elenco(
        _("Iscritti ai tornei in corso che la copia non ha: {numero}"),
        [f"{torneo}: {nomi.get(pid, pid)}" for torneo, pid in esito["assenti_dai_tornei"]],
    )
    if not righe:
        righe.append(_("Giocatori, Elo, partite, storici e medaglie restano gli stessi: cambiano solo altri dati delle schede."))
    return righe


def _medaglia_a_parole(chiave):
    """Una medaglia del database detta a parole, per il testo dello storno."""
    return {"gold": _("oro"), "silver": _("argento"), "bronze": _("bronzo"), "wood": _("legno")}.get(chiave, chiave)


def storno_finalizzazione(giocatori, torneo_archiviato, giocatori_prima=None):
    """Toglie dal database gli effetti della finalizzazione di un torneo:
    Elo, partite giocate, voce dello storico e medaglia. Non scrive niente:
    lavora su una copia di giocatori, il dizionario delle schede per
    identificativo, e restituisce un dizionario con le schede stornate, i
    giocatori stornati, i conflitti e le segnalazioni.
    I valori da togliere vengono dal json archiviato, perche' sono quelli che
    il database ha davvero ricevuto (10.8.9). Se c'e' il database di prima,
    cioe' la copia pre_finalize_db, e l'Elo di oggi vale quello di prima piu'
    la variazione, come lo scrive la finalizzazione, si rimette il valore di
    prima; altrimenti si sottrae la variazione, e lo si segnala.
    Un giocatore che dopo questo torneo ne ha nello storico un altro e' un
    conflitto: l'Elo del torneo successivo e' calcolato su quello da togliere,
    e prima va riaperto quello (decisione di Gabriele)."""
    schede = copy.deepcopy(giocatori)
    identificativo, inizio = identita_del_torneo(torneo_archiviato)
    nome = torneo_archiviato.get("name")
    nel_torneo = {g.get("id"): g for g in _giocatori_del_torneo(torneo_archiviato)}
    prima = giocatori_prima or {}
    esito = {"giocatori": schede, "stornati": [], "conflitti": [], "segnalazioni": []}
    for pid, scheda in schede.items():
        storico = scheda.get("tournaments_played") or []
        indici = [
            i for i, v in enumerate(storico) if isinstance(v, dict) and voce_di_questo_torneo(v, identificativo, nome, inizio)
        ]
        if not indici:
            continue
        nome_giocatore = _nome_del_giocatore(scheda, pid)
        indice = indici[-1]
        successive = [v for v in storico[indice + 1:] if isinstance(v, dict)]
        if successive:
            esito["conflitti"].append((pid, nome_giocatore, successive))
            continue
        if len(indici) > 1:
            esito["segnalazioni"].append(
                _("{nome} ha {numero} voci di questo torneo nello storico: se ne toglie l'ultima.").format(
                    nome=nome_giocatore, numero=len(indici)
                )
            )
        voce = storico[indice]
        giocatore = nel_torneo.get(pid)
        stornato = {
            "id": pid,
            "nome": nome_giocatore,
            "elo_da": scheda.get("current_elo"),
            "elo_a": scheda.get("current_elo"),
            "partite_da": scheda.get("games_played", 0),
            "partite_a": scheda.get("games_played", 0),
            "sottratto": False,
            "da_copia": False,
            "medaglia": None,
        }
        if giocatore is None:
            esito["segnalazioni"].append(
                _("{nome} ha il torneo nello storico ma non è fra i suoi giocatori: si toglie solo la voce, Elo e partite restano.").format(
                    nome=nome_giocatore
                )
            )
        else:
            variazione = giocatore.get("elo_change")
            if variazione is not None:
                attuale = scheda.get("current_elo")
                di_prima = (prima.get(pid) or {}).get("current_elo")
                try:
                    coincide = di_prima is not None and int(di_prima) + variazione == attuale
                except (TypeError, ValueError):
                    coincide = False
                if coincide:
                    scheda["current_elo"] = di_prima
                    stornato["da_copia"] = True
                else:
                    try:
                        scheda["current_elo"] = attuale - variazione
                    except TypeError:
                        esito["segnalazioni"].append(
                            _("{nome}: l'Elo {elo} non è un numero e resta com'è.").format(nome=nome_giocatore, elo=attuale)
                        )
                    else:
                        stornato["sottratto"] = True
                        esito["segnalazioni"].append(
                            _("{nome}: l'Elo di prima si ricava togliendo la variazione del torneo, {variazione}.").format(
                                nome=nome_giocatore, variazione=_numero_leggibile(variazione)
                            )
                        )
            partite = giocatore.get("games_this_tournament") or 0
            try:
                scheda["games_played"] = max(0, int(scheda.get("games_played") or 0) - int(partite))
            except (TypeError, ValueError):
                esito["segnalazioni"].append(
                    _("{nome}: le partite giocate non sono un numero e restano come sono.").format(nome=nome_giocatore)
                )
        medaglie_prima = dict(scheda.get("medals") or {})
        togli_torneo_dallo_storico(scheda, indice)
        for chiave in ("gold", "silver", "bronze", "wood"):
            if (scheda.get("medals") or {}).get(chiave, 0) < medaglie_prima.get(chiave, 0):
                stornato["medaglia"] = chiave
        stornato["elo_a"] = scheda.get("current_elo")
        stornato["partite_a"] = scheda.get("games_played", 0)
        stornato["voce"] = voce
        esito["stornati"].append(stornato)
    esito["stornati"].sort(key=lambda s: s["nome"])
    return esito


def righe_dello_storno(storno):
    """I giocatori stornati, una riga ciascuno: Elo e partite da che cosa a
    che cosa, e la medaglia che se ne va."""
    righe = []
    for s in storno["stornati"]:
        riga = _("{nome}: Elo {da} a {a}").format(nome=s["nome"], da=_numero_leggibile(s["elo_da"]), a=_numero_leggibile(s["elo_a"]))
        try:
            differenza = float(s["elo_a"]) - float(s["elo_da"])
        except (TypeError, ValueError):
            differenza = 0
        if differenza:
            riga += f" ({'+' if differenza > 0 else ''}{_numero_leggibile(differenza)})"
        riga += _(", partite {da} a {a}").format(da=s["partite_da"], a=s["partite_a"])
        if s["medaglia"]:
            riga += _(", un {medaglia} in meno").format(medaglia=_medaglia_a_parole(s["medaglia"]))
        righe.append(riga)
    return righe


@dataclass
class Percorsi:
    """Dove stanno i file che il ripristino tocca: la cartella del programma,
    con i tornei in corso, la cartella backup, l'archivio dei tornei conclusi,
    il database dei giocatori e il suo riassunto in testo."""

    radice: str
    backup: str
    archivio: str
    database: str
    database_txt: str | None = None


def percorsi_del_programma():
    """I Percorsi veri del programma, chiesti a config al momento della
    chiamata. E' la sola funzione del modulo che li conosce."""
    import config

    return Percorsi(
        radice=config.user_data_path(""),
        backup=config.user_data_path("backup"),
        archivio=config.ARCHIVED_TOURNAMENTS_DIR,
        database=config.PLAYER_DB_FILE,
        database_txt=config.PLAYER_DB_TXT_FILE,
    )


@dataclass
class Piano:
    """Che cosa farebbe il ripristino di una copia. tipo e' "torneo" per un
    torneo in corso o in preparazione, "finalizzato" per un torneo concluso
    da riaprire, "database" per il database dei giocatori. rifiuto, se c'e',
    dice perche' il ripristino non si fa; righe sono il confronto con lo
    stato attuale e i passi, da mostrare nella conferma; avvertenze, le
    righe che la conferma mette per prime, prima ancora della domanda."""

    copia: str
    tipo: str = ""
    dati: object = None
    destinazione: str | None = None
    rifiuto: str | None = None
    righe: list = field(default_factory=list)
    avvertenze: list = field(default_factory=list)
    attuale: object = None
    archiviato: str | None = None
    cartella_archivio: str | None = None
    json_esterno: str | None = None
    database_nuovo: object = None


@dataclass
class Esito:
    """Com'e' andato un ripristino: le righe da leggere, le copie
    pre_ripristino nate, e cio' che e' andato nel cestino."""

    riuscito: bool
    righe: list = field(default_factory=list)
    tipo: str = ""
    destinazione: str | None = None
    copie: list = field(default_factory=list)
    tolti: list = field(default_factory=list)


def _problema_del_torneo(dati):
    """Il motivo per cui il contenuto di una copia non si puo' rimettere
    come torneo; None se va bene."""
    if not isinstance(dati.get("name"), str) or not dati["name"].strip():
        return _("La copia non ha il nome del torneo.")
    if not isinstance(dati.get("players"), list) or not isinstance(dati.get("rounds", []), list):
        return _("La copia non ha l'elenco dei giocatori o quello dei turni.")
    if any(not isinstance(g, dict) or not g.get("id") for g in dati["players"]):
        return _("Nella copia c'è un giocatore senza identificativo.")
    return None


def _problema_del_database(dati):
    """Il motivo per cui il contenuto di una copia non si puo' rimettere
    come database dei giocatori; None se va bene. Un database vuoto, o con
    una scheda senza identificativo, al primo salvataggio svuoterebbe
    l'archivio dei giocatori."""
    elenco = dati if isinstance(dati, list) else dati.get("players")
    if not isinstance(elenco, list) or not elenco:
        return _("La copia non contiene giocatori.")
    identificativi = [g.get("id") if isinstance(g, dict) else None for g in elenco]
    if not all(identificativi):
        return _("Nella copia c'è una scheda senza identificativo.")
    if len(set(identificativi)) != len(identificativi):
        return _("Nella copia ci sono due schede con lo stesso identificativo.")
    return None


def stessa_edizione(uno, altro):
    """Vero se i due tornei possono essere la stessa edizione: gli
    identificativi e le date di inizio, quando ci sono tutti e due, devono
    coincidere. La finestra ricava l'identificativo dal nome, e due edizioni
    con lo stesso nome hanno lo stesso: le distingue la data di inizio."""
    for campo in ("tournament_id", "start_date"):
        a, b = uno.get(campo), altro.get(campo)
        if a and b and a != b:
            return False
    return True


def _nome_del_file(dati):
    return f"{PREFISSO}{sanitize_filename(dati['name'])}.json"


def _file_da_mostrare(percorso, percorsi):
    """Un file detto nel testo di una conferma: se sta nella cartella del
    programma basta il nome, piu' corto da leggere sulla barra braille;
    altrimenti il percorso intero."""
    try:
        cartella = os.path.normcase(os.path.abspath(os.path.dirname(percorso)))
        if cartella == os.path.normcase(os.path.abspath(percorsi.radice)):
            return os.path.basename(percorso)
    except (TypeError, ValueError):
        pass
    return percorso


def _cerca_nell_archivio(archivio, dati):
    """I json dei tornei conclusi nell'archivio che sono la stessa edizione
    del torneo della copia. Si cercano prima con il nome di file che viene
    dal nome del torneo; se non ce n'e', fra tutti i json dell'archivio, dal
    contenuto: un torneo aperto con Apri Torneo da un file con un altro nome
    va in archivio con il nome di quel file."""
    nome_file = _nome_del_file(dati)

    def cerca(modello, nome_nel_contenuto):
        trovati = []
        for percorso in sorted(glob.glob(os.path.join(glob.escape(archivio), "**", modello), recursive=True)):
            tipo, archiviato, _errore = leggi_copia(percorso)
            if (
                tipo == "torneo"
                and archiviato.get("concluded")
                and stessa_edizione(dati, archiviato)
                and (not nome_nel_contenuto or archiviato.get("name") == dati.get("name"))
            ):
                trovati.append((percorso, archiviato))
        return trovati

    return cerca(glob.escape(nome_file), False) or cerca("*.json", True)


def ultima_copia_di(percorso, cartella_backup):
    """L'ultima copia di un file, di qualunque momento, cercata per nome
    nella cartella backup; None se non ce n'e'."""
    base, estensione = os.path.splitext(os.path.basename(percorso))
    migliore = None
    if not cartella_backup or not os.path.isdir(cartella_backup):
        return None
    for cartella, _sottocartelle, files in os.walk(cartella_backup):
        for nome in files:
            parti = analizza_nome(nome)
            if (
                parti
                and parti["data"]
                and parti["base"].lower() == base.lower()
                and parti["estensione"].lower() == estensione.lower()
            ):
                chiave = (parti["data"], parti["numero"])
                if migliore is None or chiave > migliore[0]:
                    migliore = (chiave, os.path.join(cartella, nome))
    return migliore[1] if migliore else None


def database_di_prima(percorso_copia, cartella_backup, nome_database=NOME_DEL_DATABASE):
    """La copia pre_finalize_db della stessa finalizzazione di una copia
    pre_finalize_torneo: le due nascono una dopo l'altra, nello stesso
    secondo o quasi. None se la copia non e' di prima di una finalizzazione,
    o se la sua compagna non c'e'."""
    parti = analizza_nome(os.path.basename(percorso_copia))
    if not parti or parti["contesto"] != "pre_finalize_torneo" or not parti["data"]:
        return None
    base = os.path.splitext(nome_database)[0].lower()
    candidate = []
    for cartella, _sottocartelle, files in os.walk(cartella_backup):
        for nome in files:
            altre = analizza_nome(nome)
            if altre and altre["contesto"] == "pre_finalize_db" and altre["data"] and altre["base"].lower() == base:
                distanza = abs((altre["data"] - parti["data"]).total_seconds())
                if distanza <= SECONDI_FRA_LE_COPIE_DELLA_FINALIZZAZIONE:
                    # Due finalizzazioni nello stesso secondo danno alle
                    # copie gli stessi suffissi: la seconda coppia ha _2.
                    diverso_suffisso = altre["numero"] != parti["numero"]
                    candidate.append((distanza, diverso_suffisso, os.path.join(cartella, nome)))
    return min(candidate)[2] if candidate else None


def _file_estranei(cartella, nome_sanitizzato, json_archiviato):
    """I file e le cartelle dentro la cartella d'archivio che non sono del
    torneo: se ce ne sono, la cartella non va nel cestino. Il json archiviato
    e' del torneo anche con un nome diverso, quello del file da cui il torneo
    e' stato aperto."""
    estranei = []
    for voce in os.scandir(cartella):
        if voce.name == json_archiviato:
            continue
        if voce.is_dir() or not file_del_torneo(voce.name, nome_sanitizzato):
            estranei.append(voce.name)
    return estranei


def _json_esterno(archiviato_dati, percorsi, nome_file):
    """Il json concluso che la finalizzazione ha lasciato nella cartella di
    lavoro esterna, se il torneo ne aveva una e il file c'e'. Non si passa da
    resolve_and_verify_save_path, che una cartella mancante la creerebbe."""
    esterna = archiviato_dati.get("custom_save_path")
    if not esterna:
        return None
    try:
        if os.path.normcase(os.path.abspath(esterna)) == os.path.normcase(os.path.abspath(percorsi.radice)):
            return None
    except (OSError, ValueError):
        return None
    percorso = os.path.join(esterna, nome_file)
    if not os.path.isfile(percorso):
        return None
    tipo, dati, _errore = leggi_copia(percorso)
    if tipo == "torneo" and dati.get("concluded") and stessa_edizione(archiviato_dati, dati):
        return percorso
    return None


def _leggi_mappa_del_database(percorso):
    """Le schede di un database per identificativo, e il database letto;
    (None, None) se non si legge o non e' un database."""
    tipo, dati, _errore = leggi_copia(percorso) if percorso and os.path.exists(percorso) else (None, None, None)
    if tipo != "database":
        return None, None
    return {g.get("id"): g for g in giocatori_del_database(dati) if g.get("id")}, dati


def _con_giocatori(dati, schede):
    """Il database letto con le schede nuove al posto delle vecchie, nello
    stesso ordine e con gli stessi campi di contorno, come schema_version."""
    elenco = [schede.get(g.get("id"), g) for g in giocatori_del_database(dati)]
    if isinstance(dati, list):
        return elenco
    nuovo = dict(dati)
    nuovo["players"] = elenco
    return nuovo


def prepara_ripristino(percorso_copia, percorsi, destinazione=None):
    """Il Piano del ripristino di una copia: che cosa si farebbe, che cosa
    cambierebbe rispetto a oggi, o perche' non si fa. Non scrive niente.
    destinazione e' il file del torneo da sostituire; senza, quello con il
    nome del torneo nella cartella del programma."""
    tipo, dati, errore = leggi_copia(percorso_copia)
    piano = Piano(copia=percorso_copia, dati=dati)
    if tipo == "illeggibile":
        piano.rifiuto = _("La copia non si legge: {errore}").format(errore=errore)
    elif tipo == "database":
        _prepara_database(piano, percorsi)
    elif tipo == "torneo":
        _prepara_torneo(piano, percorsi, destinazione)
    else:
        piano.rifiuto = _("La copia non contiene né un torneo né il database dei giocatori: non si può ripristinare.")
    return piano


def _prepara_database(piano, percorsi):
    """Il piano del ripristino del database intero. La copia deve venire dal
    file del database del programma: nella cartella backup ci sono anche le
    copie dei database delle prove, come Players_db_complex, che al suo posto
    lascerebbero una scheda sola."""
    piano.tipo = "database"
    piano.destinazione = percorsi.database
    nome_copia = os.path.basename(piano.copia)
    parti = analizza_nome(nome_copia)
    origine = f"{parti['base']}{parti['estensione']}" if parti else nome_copia
    nome_database = os.path.basename(percorsi.database)
    if os.path.splitext(origine)[0].lower() != os.path.splitext(nome_database)[0].lower():
        piano.rifiuto = _(
            "La copia {copia} viene dal file {origine}, non dal database dei giocatori del programma, {database}: il ripristino non la mette al suo posto."
        ).format(copia=nome_copia, origine=origine, database=nome_database)
        return
    problema = _problema_del_database(piano.dati)
    if problema:
        piano.rifiuto = problema
        return
    righe = [_("Il database dei giocatori tornerebbe com'era nella copia {file}.").format(file=nome_copia)]
    attivi = tornei_attivi(percorsi.radice, nome_database)
    # Un torneo oggi in corso che nella copia e' gia' finalizzato: e' il caso
    # di chi rimette il database di prima di una riapertura. Il torneo
    # resterebbe in corso con il database che lo da' per finalizzato, e la
    # finalizzazione successiva lascerebbe i suoi giocatori come sono.
    for dati in attivi:
        if giocatori_con_il_torneo(giocatori_del_database(piano.dati), dati):
            piano.avvertenze.append(
                _(
                    "Attenzione: nella copia il torneo {nome}, che oggi è in corso, è già finalizzato. Dopo il ripristino il database e il torneo non sarebbero d'accordo. Per annullare la riapertura di un torneo non si ripristina il database: si finalizza di nuovo il torneo."
                ).format(nome=dati.get("name"))
            )
    if os.path.exists(percorsi.database):
        tipo, attuale, errore = leggi_copia(percorsi.database)
        if tipo == "database":
            piano.attuale = attuale
            esito = confronta_database(piano.dati, attuale, iscritti_dei_tornei_attivi(percorsi.radice, nome_database, attivi))
            righe += righe_del_confronto_database(esito)
            oggi = len(giocatori_del_database(attuale))
            if oggi and len(esito["sparirebbero"]) * 2 > oggi:
                piano.avvertenze.insert(
                    0,
                    _(
                        "Attenzione: sparirebbero {numero} dei {totale} giocatori di oggi, più della metà. Controlla che la copia sia quella giusta."
                    ).format(numero=len(esito["sparirebbero"]), totale=oggi),
                )
        else:
            righe.append(_("Il database attuale non si legge: {errore}").format(errore=errore or tipo))
        righe.append(_("Prima di scriverlo, il database attuale va in una copia di sicurezza con pre_ripristino nel nome."))
    else:
        righe.append(_("Oggi il database dei giocatori non c'è."))
    righe.append(
        _("Il ripristino del database intero serve solo per i disastri: per riaprire un torneo concluso si ripristina la sua copia di prima della finalizzazione, che toglie dal database soltanto quel torneo.")
    )
    piano.righe = righe


def _prepara_torneo(piano, percorsi, destinazione):
    dati = piano.dati
    problema = _problema_del_torneo(dati)
    if problema:
        piano.tipo = "torneo"
        piano.rifiuto = problema
        return
    nome = dati["name"]
    if dati.get("concluded"):
        piano.tipo = "torneo"
        piano.rifiuto = _(
            "La copia contiene il torneo {nome} già concluso. Per riaprirlo si ripristina una sua copia di prima della finalizzazione."
        ).format(nome=nome)
        return
    nome_file = _nome_del_file(dati)
    piano.destinazione = destinazione or os.path.join(percorsi.radice, nome_file)
    if os.path.exists(piano.destinazione):
        tipo, attuale, _errore = leggi_copia(piano.destinazione)
        if tipo == "torneo":
            if not stessa_edizione(dati, attuale):
                piano.tipo = "torneo"
                piano.rifiuto = _(
                    "Nel file {file} c'è un altro torneo con lo stesso nome, con un altro identificativo o un'altra data di inizio: il ripristino non lo sostituisce."
                ).format(file=piano.destinazione)
                return
            piano.attuale = attuale
        elif tipo != "illeggibile":
            piano.tipo = "torneo"
            piano.rifiuto = _("Il file {file} non contiene un torneo: il ripristino non lo sostituisce.").format(file=piano.destinazione)
            return
    archiviati = _cerca_nell_archivio(percorsi.archivio, dati)
    if len(archiviati) > 1:
        piano.tipo = "finalizzato"
        piano.rifiuto = _("Nell'archivio ci sono {numero} tornei conclusi che possono essere questo: {file}. Il ripristino non sceglie da solo.").format(
            numero=len(archiviati), file=", ".join(p for p, _d in archiviati)
        )
        return
    if archiviati:
        _prepara_finalizzato(piano, percorsi, archiviati[0])
        return
    fuori = _finalizzato_fuori_archivio(dati, piano.attuale, piano.destinazione, percorsi)
    if fuori:
        piano.tipo = "finalizzato"
        piano.rifiuto = "\n".join(fuori)
        return
    piano.tipo = "torneo"
    righe = []
    mostrato = _file_da_mostrare(piano.destinazione, percorsi)
    if piano.attuale is not None:
        righe.append(_("Il torneo {nome}, nel file {file}, tornerebbe com'era nella copia.").format(nome=nome, file=mostrato))
        righe += righe_del_confronto_torneo(confronta_torneo(dati, piano.attuale))
    elif os.path.exists(piano.destinazione):
        righe.append(_("Il file {file} oggi non si legge: al suo posto andrebbe il torneo della copia.").format(file=mostrato))
    else:
        righe.append(
            _("Il torneo {nome} non è fra quelli in corso: la copia lo rimetterebbe nella cartella del programma, nel file {file}.").format(
                nome=nome, file=nome_file
            )
        )
    if os.path.exists(piano.destinazione):
        righe.append(_("Prima di scriverlo, il file attuale va in una copia di sicurezza con pre_ripristino nel nome."))
    piano.righe = righe


def _finalizzato_fuori_archivio(dati, attuale, destinazione, percorsi):
    """Le righe del rifiuto per un torneo che risulta gia' finalizzato ma che
    l'archivio non ha: il database dei giocatori lo ha nello storico di
    qualcuno, o il file da sostituire, attuale, lo contiene gia' concluso.
    Succede se la finalizzazione non ha completato l'archiviazione (10.8.9),
    se la cartella d'archivio e' stata spostata o e' nel cestino, o se il
    database e' stato rimesso da una copia che il torneo lo aveva gia'.
    Rimessa come torneo in corso, la copia lascerebbe nel database gli
    effetti del torneo, e la finalizzazione successiva non scriverebbe i suoi
    giocatori: ci si ferma e si dice come sistemare. None se il torneo non
    risulta finalizzato."""
    motivi = []
    schede, _database = _leggi_mappa_del_database(percorsi.database)
    if schede:
        con = giocatori_con_il_torneo(list(schede.values()), dati)
        if con:
            motivi.append(
                _("  il database dei giocatori lo ha nello storico di {numero} giocatori;").format(numero=len(con))
            )
    if attuale is not None and attuale.get("concluded"):
        motivi.append(_("  il file {file} lo contiene già concluso;").format(file=_file_da_mostrare(destinazione, percorsi)))
    if not motivi:
        return None
    return [
        _("Il torneo {nome} risulta già finalizzato:").format(nome=dati["name"]),
        *motivi,
        _(
            "ma il suo file archiviato non si trova nella cartella {cartella}. Senza quello il ripristino non sa quali effetti togliere dal database, e il torneo tornerebbe in corso con il database che lo dà per finalizzato."
        ).format(cartella=percorsi.archivio),
        _(
            "Se la finalizzazione non ha completato l'archiviazione, completala come dice la finestra Avvisi della finalizzazione; se la cartella d'archivio è stata spostata o è nel cestino, rimettila al suo posto. Poi riprova."
        ),
    ]


def _prepara_finalizzato(piano, percorsi, trovato):
    """Il piano per riaprire un torneo gia' finalizzato: lo storno dei suoi
    effetti dal database, la cartella d'archivio e il json concluso esterno
    nel cestino, il torneo della copia nella cartella del programma."""
    dati = piano.dati
    piano.tipo = "finalizzato"
    piano.archiviato, archiviato = trovato
    piano.cartella_archivio = os.path.dirname(piano.archiviato)
    nome = dati["name"]
    sanitizzato = sanitize_filename(nome)
    if os.path.normcase(os.path.abspath(piano.cartella_archivio)) == os.path.normcase(os.path.abspath(percorsi.archivio)):
        piano.rifiuto = _("Il torneo concluso sta direttamente nella cartella dell'archivio, {cartella}: il ripristino non la manda nel cestino.").format(
            cartella=piano.cartella_archivio
        )
        return
    estranei = _file_estranei(piano.cartella_archivio, sanitizzato, os.path.basename(piano.archiviato))
    if estranei:
        piano.rifiuto = _(
            "La cartella d'archivio {cartella} contiene anche file che non sono di questo torneo: {file}. Il ripristino non la manda nel cestino: sistemala a mano e riprova."
        ).format(cartella=piano.cartella_archivio, file=", ".join(sorted(estranei)))
        return
    schede, database = _leggi_mappa_del_database(percorsi.database)
    if schede is None:
        piano.rifiuto = _("Il database dei giocatori non si legge: senza, gli effetti del torneo non si possono togliere.")
        return
    di_prima = database_di_prima(piano.copia, percorsi.backup, os.path.basename(percorsi.database))
    schede_di_prima = _leggi_mappa_del_database(di_prima)[0] if di_prima else None
    storno = storno_finalizzazione(schede, archiviato, schede_di_prima)
    if storno["conflitti"]:
        successivi = {}
        for _pid, _nome, voci in storno["conflitti"]:
            for voce in voci:
                successivi[_chiave_della_voce(voce)] = voce
        elenco = sorted(successivi.values(), key=lambda v: str(v.get("date_completed") or ""), reverse=True)
        tornei = [f"{v.get('tournament_name')} ({_giorno(v.get('date_completed'))})" for v in elenco]
        giocatori = sorted(n for _pid, n, _voci in storno["conflitti"])
        piano.rifiuto = "\n".join(
            [
                _("Dopo {nome} è stato finalizzato un altro torneo con giocatori in comune, e i suoi Elo sono calcolati su quelli da togliere.").format(
                    nome=nome
                ),
                _("Prima va riaperto, partendo dall'ultimo: {tornei}.").format(tornei=", ".join(tornei)),
                _("Giocatori in comune: {giocatori}.").format(giocatori=", ".join(giocatori)),
            ]
        )
        return
    piano.database_nuovo = _con_giocatori(database, storno["giocatori"])
    # Nella cartella esterna il json concluso ha il nome di quello archiviato.
    piano.json_esterno = _json_esterno(archiviato, percorsi, os.path.basename(piano.archiviato))
    righe = [
        _("Il torneo {nome} è finalizzato e archiviato in {cartella}. Ripristinando la copia si riapre:").format(
            nome=nome, cartella=piano.cartella_archivio
        ),
        _("il torneo torna fra quelli in corso, nel file {file};").format(file=_file_da_mostrare(piano.destinazione, percorsi)),
        _("la cartella d'archivio va nel cestino;"),
    ]
    c_e = os.path.exists(piano.destinazione)
    if c_e:
        righe.append(_("il file del torneo che oggi c'è al suo posto viene sostituito;"))
    if piano.json_esterno:
        righe.append(_("il file concluso della cartella di lavoro esterna, {file}, va nel cestino;").format(file=piano.json_esterno))
    righe.append(
        _("dal database dei giocatori si toglie questo torneo, per {numero} giocatori:").format(numero=len(storno["stornati"]))
    )
    righe += [f"  {r}" for r in righe_dello_storno(storno)]
    righe += storno["segnalazioni"]
    # La copia del database di prima si nomina solo se almeno un Elo viene
    # davvero da li'; se non torna con nessuno, lo si dice.
    dalla_copia = sum(1 for s in storno["stornati"] if s["da_copia"])
    sottratti = sum(1 for s in storno["stornati"] if s["sottratto"])
    if di_prima and dalla_copia and sottratti:
        righe.append(
            _("Gli Elo di prima vengono dalla copia {file}, tranne quelli dei giocatori segnalati sopra.").format(
                file=os.path.basename(di_prima)
            )
        )
    elif di_prima and dalla_copia:
        righe.append(_("Gli Elo di prima vengono dalla copia {file}.").format(file=os.path.basename(di_prima)))
    elif di_prima and sottratti:
        righe.append(
            _("La copia {file}, del database di prima della finalizzazione, non torna con il database di oggi: gli Elo di prima si ricavano togliendo le variazioni.").format(
                file=os.path.basename(di_prima)
            )
        )
    righe.append(_("Il torneo della copia rispetto a quello archiviato:"))
    righe += [f"  {r}" for r in righe_del_confronto_torneo(confronta_torneo(dati, archiviato))]
    if piano.json_esterno and c_e:
        salvati = _("database, torneo archiviato, file della cartella esterna e file del torneo di oggi")
    elif piano.json_esterno:
        salvati = _("database, torneo archiviato e file della cartella esterna")
    elif c_e:
        salvati = _("database, torneo archiviato e file del torneo di oggi")
    else:
        salvati = _("database e torneo archiviato")
    righe.append(_("Prima di toccare qualcosa, {file} vanno in copie di sicurezza con pre_ripristino nel nome.").format(file=salvati))
    piano.righe = righe


def ripristina(percorso_copia, percorsi, destinazione=None, cestino=delete_file_to_trash):
    """Ripristina una copia: prepara di nuovo il piano, sui file come sono in
    questo momento, e lo esegue. cestino e' la funzione che manda nel cestino
    un file o una cartella e risponde se ci e' riuscita: le prove ne passano
    una finta. Restituisce un Esito."""
    piano = prepara_ripristino(percorso_copia, percorsi, destinazione)
    if piano.rifiuto:
        return Esito(False, [piano.rifiuto], tipo=piano.tipo, destinazione=piano.destinazione)
    if piano.tipo == "finalizzato":
        return _ripristina_finalizzato(piano, percorsi, cestino)
    return _ripristina_file(piano, percorsi, cestino)


def _metti_in_salvo(percorsi_da_copiare, cartella_backup, esito):
    """Le copie pre_ripristino dei file che il ripristino tocchera', rilette.
    Vero se sono nate tutte; al primo fallimento si ferma, e l'esito lo
    dice."""
    for percorso in percorsi_da_copiare:
        copia = copia_di_sicurezza(percorso, "pre_ripristino", cartella_backup)
        if not copia or not stessi_byte(percorso, copia):
            esito.righe.append(
                _("La copia di sicurezza di {file} non è riuscita: il ripristino si ferma, e non è stato toccato niente.").format(file=percorso)
            )
            return False
        esito.copie.append(copia)
    return True


def _scrivi_e_rileggi(percorso, dati):
    """Scrive dati in modo atomico e rilegge il file: vero solo se dentro
    c'e' esattamente cio' che si voleva."""
    try:
        scrivi_json_atomico(percorso, dati)
        with open(percorso, encoding="utf-8") as f:
            return json.load(f) == dati
    except (OSError, ValueError, TypeError):
        return False


def _rimetti_da_copia(copia, percorso):
    """Rimette un file com'era, dalla sua copia pre_ripristino, passando da
    un file temporaneo nella stessa cartella, che si ricrea se non c'e' piu':
    della cartella d'archivio il cestino puo' aver preso una parte. Vero se
    il file riletto e' uguale alla copia."""
    temporaneo = f"{percorso}.ripristino.tmp"
    try:
        os.makedirs(os.path.dirname(os.path.abspath(percorso)), exist_ok=True)
        shutil.copyfile(copia, temporaneo)
        os.replace(temporaneo, percorso)
    except OSError:
        if os.path.exists(temporaneo):
            with contextlib.suppress(OSError):
                os.remove(temporaneo)
        return False
    return stessi_byte(copia, percorso)


def _rimetti_il_file(copia, percorso, cestino):
    """Rimette com'era un file che il ripristino ha scritto: dalla sua copia
    pre_ripristino, oppure, se prima il file non c'era e copia e' None,
    mandando nel cestino quello nuovo. Vero se ci e' riuscito."""
    if copia:
        return _rimetti_da_copia(copia, percorso)
    return not os.path.exists(percorso) or (cestino(percorso) and not os.path.exists(percorso))


def _cambiato(percorso, copia):
    """Vero se un file non e' piu' com'era prima del ripristino: diverso
    dalla sua copia pre_ripristino, o sparito, oppure, se prima non c'era e
    copia e' None, comparso. Un file che non si rilegge conta come cambiato:
    meglio provare a rimetterlo che dirlo intatto senza saperlo."""
    if copia is None:
        return os.path.exists(percorso)
    return not stessi_byte(copia, percorso)


def _ripristina_file(piano, percorsi, cestino):
    """Il ripristino di un file solo: il torneo in corso o il database."""
    esito = Esito(False, tipo=piano.tipo, destinazione=piano.destinazione)
    c_era = os.path.exists(piano.destinazione)
    if c_era and not _metti_in_salvo([piano.destinazione], percorsi.backup, esito):
        return esito
    copia = esito.copie[0] if esito.copie else None
    if _scrivi_e_rileggi(piano.destinazione, piano.dati):
        esito.riuscito = True
        esito.righe.append(_("Ripristino riuscito: {file} è com'era nella copia.").format(file=_file_da_mostrare(piano.destinazione, percorsi)))
        if piano.tipo == "database" and percorsi.database_txt:
            from db_players import save_players_db_txt

            schede = {g.get("id"): g for g in giocatori_del_database(piano.dati)}
            save_players_db_txt(schede, percorsi.database_txt)
    else:
        esito.righe.append(_("La scrittura di {file} non è riuscita, o riletto non è uguale alla copia.").format(file=piano.destinazione))
        # Una scrittura che si ferma prima di sostituire il file, per
        # esempio perche' e' bloccato, lo lascia com'era: rimetterlo non
        # serve, e con il blocco ancora in corso non riuscirebbe, e l'esito
        # direbbe di un danno che non c'e'.
        if not _cambiato(piano.destinazione, copia):
            esito.righe.append(_("Nessun file è stato cambiato."))
        elif _rimetti_il_file(copia, piano.destinazione, cestino):
            esito.righe.append(_("Il file è tornato com'era prima del ripristino."))
        elif copia:
            esito.righe.append(_("Nemmeno lo stato di prima si è potuto rimettere: è nella copia {copia}.").format(copia=copia))
        else:
            esito.righe.append(_("Prima il file non c'era, e quello scritto dal ripristino non si è potuto mandare nel cestino."))
    if copia:
        esito.righe.append(_("Lo stato di prima è nella copia {copia}.").format(copia=os.path.basename(copia)))
    return esito


def _ripristina_finalizzato(piano, percorsi, cestino):
    """Riapre un torneo finalizzato. I passi, nell'ordine: copie
    pre_ripristino di database, torneo archiviato, json esterno e file di
    destinazione, se c'e'; torneo nella cartella del programma; database
    stornato; json esterno nel cestino; cartella d'archivio nel cestino. I
    passi da cestino vengono per ultimi perche' sono i piu' difficili da
    rimettere. Se un passo non riesce, quelli gia' tentati si rimettono dalle
    copie, e l'esito dice quali."""
    esito = Esito(False, tipo=piano.tipo, destinazione=piano.destinazione)
    da_salvare = [percorsi.database, piano.archiviato]
    if piano.json_esterno:
        da_salvare.append(piano.json_esterno)
    if os.path.exists(piano.destinazione):
        da_salvare.append(piano.destinazione)
    if not _metti_in_salvo(da_salvare, percorsi.backup, esito):
        return esito
    copia_del = dict(zip(da_salvare, esito.copie, strict=True))
    # Un passo entra fra i tentati prima di cominciare. Una scrittura
    # riuscita con la rilettura bloccata, per esempio dall'antivirus, o un
    # cestino che prende soltanto una parte della cartella, lasciano il file
    # cambiato anche se il passo risulta non riuscito: chi rimette guarda i
    # file, non la risposta del passo.
    tentati = []

    def fallito(frase):
        esito.righe.append(frase)
        esito.righe += _rimetti(tentati, copia_del, piano, percorsi, cestino)
        return esito

    tentati.append("torneo")
    if not _scrivi_e_rileggi(piano.destinazione, piano.dati):
        return fallito(_("La scrittura del torneo in {file} non è riuscita.").format(file=piano.destinazione))
    tentati.append("database")
    if not _scrivi_e_rileggi(percorsi.database, piano.database_nuovo):
        return fallito(_("La scrittura del database dei giocatori non è riuscita."))
    if piano.json_esterno:
        tentati.append("esterno")
        if not cestino(piano.json_esterno) or os.path.exists(piano.json_esterno):
            return fallito(_("Il file {file} non è andato nel cestino.").format(file=piano.json_esterno))
        esito.tolti.append(piano.json_esterno)
    tentati.append("archivio")
    if not cestino(piano.cartella_archivio) or os.path.exists(piano.cartella_archivio):
        return fallito(
            _("La cartella d'archivio {cartella} non è andata nel cestino, o non tutta: controlla nel cestino se c'è una parte dei suoi file.").format(
                cartella=piano.cartella_archivio
            )
        )
    esito.tolti.append(piano.cartella_archivio)
    _togli_cartelle_vuote_sopra(piano.cartella_archivio, percorsi.archivio)
    if percorsi.database_txt:
        from db_players import save_players_db_txt

        save_players_db_txt(
            {g.get("id"): g for g in giocatori_del_database(piano.database_nuovo)}, percorsi.database_txt
        )
    esito.riuscito = True
    esito.righe.append(
        _("Il torneo {nome} è riaperto: è fra quelli in corso, nel file {file}.").format(
            nome=piano.dati["name"], file=_file_da_mostrare(piano.destinazione, percorsi)
        )
    )
    esito.righe.append(_("La cartella d'archivio è nel cestino."))
    if piano.json_esterno:
        esito.righe.append(_("Il file concluso della cartella esterna è nel cestino."))
    esito.righe.append(_("Il database dei giocatori non ha più questo torneo."))
    esito.righe.append(_("Copie di sicurezza di prima del ripristino:"))
    esito.righe += _righe_delle_copie(copia_del, piano, percorsi)
    return esito


def _righe_delle_copie(copia_del, piano, percorsi):
    """Le copie pre_ripristino di una riapertura, una per riga, ciascuna con
    il file di cui e' la copia: il json archiviato e quello della cartella
    esterna hanno lo stesso nome, e le loro copie anche."""
    di_che_cosa = {
        percorsi.database: _("database dei giocatori"),
        piano.archiviato: _("torneo archiviato"),
        piano.json_esterno: _("file della cartella esterna"),
        piano.destinazione: _("file del torneo nella cartella del programma"),
    }
    return [
        _("  {cosa}: {copia}").format(cosa=di_che_cosa.get(percorso, percorso), copia=os.path.basename(copia))
        for percorso, copia in copia_del.items()
    ]


def _rimetti(tentati, copia_del, piano, percorsi, cestino):
    """Rimette com'erano i file dei passi tentati di un ripristino non
    riuscito, dall'ultimo al primo, e restituisce le righe che dicono com'e'
    andata. Si rimette solo un file che non e' piu' com'era. Della cartella
    d'archivio si rimette il json del torneo, dalla sua copia, ricreando la
    cartella se serve: senza, il torneo non sarebbe ne' fra quelli in corso
    ne' fra i conclusi. Il resto della cartella, se il cestino ne ha preso
    una parte, si recupera da li'."""
    righe = []
    cambiati = 0
    for passo in reversed(tentati):
        if passo == "archivio":
            percorso, cosa = piano.archiviato, _("il file del torneo archiviato")
        elif passo == "esterno":
            percorso, cosa = piano.json_esterno, _("il file concluso della cartella esterna")
        elif passo == "database":
            percorso, cosa = percorsi.database, _("il database dei giocatori")
        else:
            percorso, cosa = piano.destinazione, _("il file del torneo nella cartella del programma")
        copia = copia_del.get(percorso)
        if not _cambiato(percorso, copia):
            continue
        cambiati += 1
        if _rimetti_il_file(copia, percorso, cestino):
            righe.append(_("Rimesso com'era: {cosa}.").format(cosa=cosa))
        else:
            righe.append(_("Non si è potuto rimettere com'era: {cosa}. Lo stato di prima è nelle copie pre_ripristino.").format(cosa=cosa))
    if not cambiati:
        righe.append(_("Nessun file è stato cambiato."))
    righe.append(_("Copie di sicurezza di prima del ripristino:"))
    righe += _righe_delle_copie(copia_del, piano, percorsi)
    return righe


def _togli_cartelle_vuote_sopra(cartella, radice):
    """Toglie le cartelle del mese e dell'anno rimaste vuote sopra una
    cartella tolta, senza mai toccare la radice dell'archivio."""
    radice = os.path.normcase(os.path.abspath(radice))
    sopra = os.path.dirname(os.path.abspath(cartella))
    while os.path.normcase(sopra) != radice and os.path.normcase(sopra).startswith(radice):
        try:
            if os.listdir(sopra):
                return
            os.rmdir(sopra)
        except OSError:
            return
        sopra = os.path.dirname(sopra)


def copie_da_scartare(copie, quante=COPIE_DA_TENERE):
    """Le copie che la regola di conservazione manderebbe nel cestino: per
    ogni origine restano le ultime quante; quelle dei momenti di
    CONTESTI_CONSERVATI restano tutte, come le copie con un nome che questa
    versione non riconosce. Non tocca niente: la finestra mostra l'anteprima
    e aspetta il pulsante (decisione di Gabriele)."""
    gruppi = {}
    for c in copie:
        if c.contesto and c.contesto not in CONTESTI_CONSERVATI:
            gruppi.setdefault(c.chiave, []).append(c)
    scarto = []
    for gruppo in gruppi.values():
        gruppo.sort(key=lambda c: (c.data, c.numero, c.nome))
        scarto += gruppo[: max(0, len(gruppo) - quante)]
    scarto.sort(key=lambda c: (c.data, c.numero, c.nome))
    return scarto


def righe_della_regola(quante=COPIE_DA_TENERE):
    """La regola di conservazione per intero, a righe corte per la barra
    braille. I momenti delle copie che restano tutte vengono da
    CONTESTI_CONSERVATI, detti come li dice la finestra: la regola scritta e
    quella applicata non possono andare ciascuna per la sua strada."""
    momenti = []
    for contesto in CONTESTI_CONSERVATI:
        parole = momento_in_parole(contesto)
        if parole not in momenti:
            momenti.append(parole)
    return [
        _("Per ogni origine restano le ultime {quante} copie.").format(quante=quante),
        _("Restano tutte le copie fatte:"),
        *[f"  {parole};" for parole in momenti],
        _("e restano i file con un nome che Tornello non riconosce."),
    ]


def righe_della_conservazione(scarto, quante=COPIE_DA_TENERE):
    """L'anteprima della regola di conservazione: la regola, e quante copie
    andrebbero nel cestino, origine per origine."""
    if not scarto:
        return [_("Nessuna copia da mandare nel cestino."), *righe_della_regola(quante)]
    per_origine = {}
    for c in scarto:
        per_origine[c.origine] = per_origine.get(c.origine, 0) + 1
    righe = [
        *righe_della_regola(quante),
        _("Andrebbero nel cestino {numero} copie:").format(numero=len(scarto)),
    ]
    righe += [f"  {origine}: {numero}" for origine, numero in sorted(per_origine.items(), key=lambda v: v[0].lower())]
    return righe
