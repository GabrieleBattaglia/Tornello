"""Riordina l'archivio dei tornei conclusi e le copie di sicurezza nella
struttura per anno e mese introdotta con la versione 9.7.0.

Serve una volta sola, per i file creati prima di quella versione: da allora
Tornello scrive gia' nelle sottocartelle giuste.

Cosa fa.
Archivio: ogni cartella di torneo che sta ancora nella radice di
"Closed Tournaments" viene spostata sotto l'anno e il mese di conclusione del
torneo, letti dal file JSON del torneo stesso; in mancanza di quello si guarda
il suffisso nel nome della cartella e, come ultima risorsa, la data di
modifica. Il nome della cartella di destinazione e' il solo nome del torneo,
senza il suffisso del mese, che ora sta nel percorso.
Backup: ogni file che sta ancora nella radice di "backup" viene spostato sotto
l'anno e il mese della copia, letti dal timestamp nel nome del file e, in
mancanza, dalla data di modifica.
Alla fine le cartelle rimaste vuote vengono tolte di mezzo.

Come si usa.
Senza argomenti fa una prova e stampa soltanto cosa farebbe, senza toccare
nulla. Con l'argomento --esegui sposta davvero i file.
Nessun file viene mai sovrascritto: se la destinazione esiste gia', lo
spostamento viene saltato e segnalato.

Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5 UltraCode)
"""

import json
import os
import re
import shutil
import sys
from datetime import datetime

RADICE_PROGETTO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(RADICE_PROGETTO, "src"))

import config  # noqa: F401  installa la funzione di traduzione
from config import ARCHIVED_TOURNAMENTS_DIR, user_data_path
from utils import (
    nome_cartella_mese,
    rimuovi_cartelle_vuote,
    sanitize_filename,
)

CARTELLA_BACKUP = user_data_path("backup")
TIMESTAMP_NEL_NOME = re.compile(r"(\d{8})_(\d{6})")
# I suffissi delle cartelle di archivio sono stati scritti in lingue diverse
# nel corso del tempo, quindi si riconoscono i mesi in italiano e in inglese.
MESI_PER_NOME = {
    "gennaio": 1,
    "january": 1,
    "febbraio": 2,
    "february": 2,
    "marzo": 3,
    "march": 3,
    "aprile": 4,
    "april": 4,
    "maggio": 5,
    "may": 5,
    "giugno": 6,
    "june": 6,
    "luglio": 7,
    "july": 7,
    "agosto": 8,
    "august": 8,
    "settembre": 9,
    "september": 9,
    "ottobre": 10,
    "october": 10,
    "novembre": 11,
    "november": 11,
    "dicembre": 12,
    "december": 12,
}


def e_una_cartella_di_anno(nome):
    return len(nome) == 4 and nome.isdigit()


def data_dal_nome_cartella(nome):
    """Legge l'anno e il mese dal suffisso storico, per esempio
    "Primavera_2 - June 2026"."""
    pezzi = nome.rsplit(" - ", 1)
    if len(pezzi) != 2:
        return None
    parole = pezzi[1].split()
    if len(parole) != 2:
        return None
    mese = MESI_PER_NOME.get(parole[0].strip().lower())
    if not mese or not parole[1].strip().isdigit():
        return None
    return datetime(int(parole[1]), mese, 1)


def nome_torneo_dalla_cartella(nome):
    """Toglie il suffisso del mese, che ora sta nel percorso."""
    data = data_dal_nome_cartella(nome)
    if data is None:
        return sanitize_filename(nome)
    return sanitize_filename(nome.rsplit(" - ", 1)[0])


def trova_json_del_torneo(cartella):
    for radice, _sottocartelle, files in os.walk(cartella):
        for nome in files:
            if nome.lower().endswith(".json") and nome.startswith("Tornello - "):
                return os.path.join(radice, nome)
    return None


def data_del_torneo(cartella):
    """Data di conclusione del torneo, cercata prima nel file del torneo, poi
    nel nome della cartella, infine nella data di modifica."""
    percorso_json = trova_json_del_torneo(cartella)
    if percorso_json:
        try:
            with open(percorso_json, "r", encoding="utf-8") as f:
                dati = json.load(f)
            fine = dati.get("end_date")
            if fine:
                return datetime.strptime(fine, "%Y-%m-%d"), "data di fine del torneo"
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    dal_nome = data_dal_nome_cartella(os.path.basename(cartella))
    if dal_nome:
        return dal_nome, "suffisso del nome della cartella"
    return datetime.fromtimestamp(os.path.getmtime(cartella)), "data di modifica"


def appiattisci_se_annidata(cartella):
    """Alcune cartelle di archivio contengono una sola sottocartella con lo
    stesso nome e nessun file: si prende quella interna, che e' dove stanno
    davvero i file del torneo."""
    try:
        contenuto = os.listdir(cartella)
    except OSError:
        return cartella
    if len(contenuto) != 1:
        return cartella
    interna = os.path.join(cartella, contenuto[0])
    if os.path.isdir(interna):
        return interna
    return cartella


def destinazione(radice, data, nome_finale):
    return os.path.join(
        radice, f"{data.year:04d}", nome_cartella_mese(data.month), nome_finale
    )


def riordina_archivio(esegui):
    print("Archivio dei tornei conclusi:", ARCHIVED_TOURNAMENTS_DIR)
    if not os.path.isdir(ARCHIVED_TOURNAMENTS_DIR):
        print("   la cartella non esiste, niente da fare.")
        return 0, 0, 0
    spostate = saltate = vuote = 0
    for nome in sorted(os.listdir(ARCHIVED_TOURNAMENTS_DIR)):
        origine = os.path.join(ARCHIVED_TOURNAMENTS_DIR, nome)
        if not os.path.isdir(origine) or e_una_cartella_di_anno(nome):
            continue
        contenuto = trova_json_del_torneo(origine)
        if contenuto is None and not any(files for _r, _d, files in os.walk(origine)):
            print(f"   [vuota] {nome}: nessun file dentro, la tolgo")
            vuote += 1
            if esegui:
                try:
                    shutil.rmtree(origine)
                except OSError as errore:
                    print(f"      non rimossa: {errore}")
            continue
        data, fonte = data_del_torneo(origine)
        da_spostare = appiattisci_se_annidata(origine)
        nome_finale = nome_torneo_dalla_cartella(nome)
        arrivo = destinazione(ARCHIVED_TOURNAMENTS_DIR, data, nome_finale)
        relativo = os.path.relpath(arrivo, ARCHIVED_TOURNAMENTS_DIR)
        if os.path.exists(arrivo):
            print(f"   [saltata] {nome}: {relativo} esiste gia'")
            saltate += 1
            continue
        print(f"   {nome} -> {relativo}   ({fonte})")
        spostate += 1
        if esegui:
            os.makedirs(os.path.dirname(arrivo), exist_ok=True)
            shutil.move(da_spostare, arrivo)
            if da_spostare != origine and os.path.isdir(origine):
                try:
                    os.rmdir(origine)
                except OSError:
                    pass
    return spostate, saltate, vuote


def data_del_backup(percorso):
    trovato = TIMESTAMP_NEL_NOME.search(os.path.basename(percorso))
    if trovato:
        try:
            return (
                datetime.strptime(trovato.group(1), "%Y%m%d"),
                "timestamp nel nome",
            )
        except ValueError:
            pass
    return datetime.fromtimestamp(os.path.getmtime(percorso)), "data di modifica"


def riordina_backup(esegui):
    print("\nCopie di sicurezza:", CARTELLA_BACKUP)
    if not os.path.isdir(CARTELLA_BACKUP):
        print("   la cartella non esiste, niente da fare.")
        return 0, 0
    spostati = saltati = 0
    per_mese = {}
    for nome in sorted(os.listdir(CARTELLA_BACKUP)):
        origine = os.path.join(CARTELLA_BACKUP, nome)
        if not os.path.isfile(origine):
            continue
        data, fonte = data_del_backup(origine)
        cartella = os.path.join(
            CARTELLA_BACKUP, f"{data.year:04d}", nome_cartella_mese(data.month)
        )
        arrivo = os.path.join(cartella, nome)
        if os.path.exists(arrivo):
            print(f"   [saltato] {nome}: esiste gia' a destinazione")
            saltati += 1
            continue
        chiave = os.path.relpath(cartella, CARTELLA_BACKUP)
        per_mese[chiave] = per_mese.get(chiave, 0) + 1
        per_mese.setdefault("_fonte_" + chiave, fonte)
        spostati += 1
        if esegui:
            os.makedirs(cartella, exist_ok=True)
            shutil.move(origine, arrivo)
    for chiave in sorted(k for k in per_mese if not k.startswith("_fonte_")):
        print(f"   {per_mese[chiave]:4d} file -> {chiave}")
    return spostati, saltati


def main():
    esegui = "--esegui" in sys.argv
    if esegui:
        print("Riordino in corso: i file verranno spostati davvero.\n")
    else:
        print(
            "Prova senza toccare nulla. Per spostare davvero i file rilancia lo "
            "script con l'argomento --esegui.\n"
        )

    spostate, saltate, vuote = riordina_archivio(esegui)
    spostati, saltati = riordina_backup(esegui)

    if esegui:
        tolte = rimuovi_cartelle_vuote(ARCHIVED_TOURNAMENTS_DIR)
        tolte += rimuovi_cartelle_vuote(CARTELLA_BACKUP)
    else:
        tolte = 0

    print("\nRiepilogo")
    print(f"   tornei archiviati spostati: {spostate}")
    print(f"   tornei saltati perche' la destinazione esisteva: {saltate}")
    print(f"   cartelle di torneo vuote rimosse: {vuote}")
    print(f"   copie di sicurezza spostate: {spostati}")
    print(f"   copie saltate perche' la destinazione esisteva: {saltati}")
    print(f"   cartelle rimaste vuote e rimosse: {tolte}")
    if not esegui:
        print("\nNessun file e' stato toccato: questa era solo una prova.")


if __name__ == "__main__":
    main()
