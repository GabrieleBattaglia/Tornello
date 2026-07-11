"""
Registro centrale dei criteri di spareggio FIDE per tornei svizzeri individuali.
In conformità al FIDE Handbook 07 (Play-Off and Tie-Break Regulations)
efficaci dal 1° Marzo 2026.
"""

import builtins

_ = getattr(builtins, "_", lambda s: s)


# ---------------------------------------------------------------------------
# Definizione dei Modificatori (Articolo 14)
# ---------------------------------------------------------------------------
MODIFIERS = {
    "cut1": {
        "name": "Cut-1",
        "description": _(
            "Taglio del valore meno significativo: esclude dal calcolo il singolo "
            "contributo peggiore. È in assoluto il modificatore più utilizzato nei "
            "tornei. NOTA: se il giocatore ha forfeit nel suo storico, il taglio "
            "deve escludere prioritariamente il contributo più basso derivante da "
            "quei turni non giocati, a condizione che tale valore non sia inferiore "
            "al valore meno significativo assoluto dell'intero calcolo (Articolo 14, 16)."
        ),
    },
    "cut2": {
        "name": "Cut-2",
        "description": _(
            "Taglio dei due valori meno significativi: esclude dal calcolo i due "
            "contributi peggiori anziché uno solo."
        ),
    },
    "median1": {
        "name": "Median-1",
        "description": _(
            "Mediana 1: esclude contemporaneamente gli estremi, ovvero taglia sia "
            "il valore meno significativo (il peggiore) sia quello più significativo "
            "(il migliore)."
        ),
    },
    "median2": {
        "name": "Median-2",
        "description": _(
            "Mediana 2: estensione della mediana semplice; esclude i due valori "
            "meno significativi e i due valori più significativi dal calcolo."
        ),
    },
}


# ---------------------------------------------------------------------------
# Tabella di incrocio: quali modificatori sono associabili a quali criteri
# (Articolo 14, tabella ufficiale FIDE)
# ---------------------------------------------------------------------------
CRITERION_MODIFIERS = {
    "BH": ["cut1", "cut2", "median1", "median2"],  # Tutti e 4
    "FB": ["cut1"],  # Solo Cut-1
    "SB": ["cut1"],  # Solo Cut-1
    "ARO": ["cut1"],  # Solo Cut-1
    "PS": ["cut1"],  # Solo Cut-1
}


# ---------------------------------------------------------------------------
# Catalogo dei 19 criteri di spareggio FIDE
# ---------------------------------------------------------------------------
CRITERIA = {
    "DE": {
        "name": _("Incontro Diretto"),
        "col_header": "DE",
        "description": _(
            "Valuta i risultati ottenuti esclusivamente negli scontri tra i "
            "partecipanti che si trovano in una situazione di parità. In un "
            "sistema svizzero, se i partecipanti in parità non si sono affrontati "
            "tutti, il criterio viene applicato se un giocatore risulterebbe primo "
            "nella classifica parziale indipendentemente dai risultati degli "
            "incontri mancanti; la medesima logica si applica per determinare le "
            "posizioni successive (Articolo 6.3)."
        ),
        "formula": _(
            "Somma dei punteggi ottenuti negli scontri tra i giocatori a pari "
            "merito. Nel caso in cui due partecipanti si siano incontrati più "
            "volte, si utilizza la media dei punteggi ottenuti in tali incontri "
            "(Articolo 6.1.2)."
        ),
    },
    "WIN": {
        "name": _("Numero di Vittorie"),
        "col_header": "WIN",
        "description": _(
            "Conteggia il numero totale di turni in cui il partecipante ha "
            "ottenuto il punteggio massimo previsto per la vittoria, includendo "
            "sia i punti ottenuti sulla scacchiera sia quelli assegnati senza "
            "giocare (forfait, bye)."
        ),
        "formula": _(
            "Numero complessivo di round in cui i punti ottenuti sono equivalenti "
            "a quelli previsti per una vittoria (Articolo 7.1)."
        ),
    },
    "WON": {
        "name": _("Partite Vinte alla Scacchiera"),
        "col_header": "WON",
        "description": _(
            "Considera esclusivamente il numero di vittorie ottenute effettivamente "
            "tramite lo svolgimento della partita sulla scacchiera."
        ),
        "formula": _(
            'Conteggio totale delle partite vinte "over the board" (Articolo 7.2).'
        ),
    },
    "BPG": {
        "name": _("Partite Giocate col Nero"),
        "col_header": "BPG",
        "description": _(
            "Valuta il numero di volte in cui a un partecipante è stato assegnato "
            "il colore nero nelle partite effettivamente disputate."
        ),
        "formula": _(
            "Numero totale di partite disputate fisicamente conducendo i pezzi neri "
            "(Articolo 7.3)."
        ),
    },
    "BWG": {
        "name": _("Partite Vinte col Nero"),
        "col_header": "BWG",
        "description": _(
            "Premia il numero di successi ottenuti sulla scacchiera quando il "
            "partecipante conduceva i pezzi neri."
        ),
        "formula": _(
            'Numero di partite vinte "over the board" giocando con il colore nero '
            "(Articolo 7.4)."
        ),
    },
    "PS": {
        "name": _("Punteggi Progressivi"),
        "col_header": "PS",
        "description": _(
            "Misura la tempestività del successo durante il torneo sommando il "
            "punteggio cumulativo del giocatore al termine di ogni turno."
        ),
        "formula": _(
            "Somma dei punteggi parziali ottenuti dal partecipante dopo ogni round. "
            'È prevista la variante "Cut-1" (PS-C1) che esclude il punteggio '
            "ottenuto dopo il primo turno (Articolo 7.5, 14.1.1)."
        ),
    },
    "REP": {
        "name": _("Round Scelti per il Gioco"),
        "col_header": "REP",
        "description": _(
            "Determina la partecipazione attiva del giocatore, escludendo le "
            "assenze o i punti ottenuti senza giocare per motivi tecnici o "
            "disciplinari."
        ),
        "formula": _(
            "Numero totale di round del torneo meno il numero di half-point-byes, "
            "zero-point-byes o sconfitte a forfait (Articolo 7.6)."
        ),
    },
    "STD": {
        "name": _("Punti Standard"),
        "col_header": "STD",
        "description": _(
            "Confronta sistematicamente il rendimento del partecipante rispetto a "
            "quello dell'avversario designato in ogni turno."
        ),
        "formula": _(
            "Somma dei round in cui si ottengono più punti dell'avversario (o più "
            "punti di un patto non giocato) più la metà dei round in cui si "
            "ottiene lo stesso punteggio dell'avversario (Articolo 7.7)."
        ),
    },
    "TPN": {
        "name": _("Numero di Sorteggio"),
        "col_header": "TPN",
        "description": _(
            "Utilizza l'ordinamento numerico assegnato ai fini degli accoppiamenti "
            "come criterio di classificazione finale."
        ),
        "formula": _(
            "Ordinamento basato sul numero di accoppiamento finale, applicato in "
            "ordine ascendente o discendente secondo il regolamento specifico "
            "(Articolo 7.8)."
        ),
    },
    "BH": {
        "name": _("Buchholz"),
        "col_header": "BH",
        "description": _(
            "Valuta la forza del percorso di un giocatore basandosi sul rendimento "
            "complessivo degli avversari incontrati."
        ),
        "formula": _(
            "Somma dei punteggi finali di tutti gli avversari affrontati. È "
            'prevista la variante principale "Cut-1" (BH-C1), che esclude il '
            "punteggio dell'avversario con il risultato più basso "
            "(Articolo 8.1, 14.1.1)."
        ),
    },
    "AOB": {
        "name": _("Media Buchholz Avversari"),
        "col_header": "AOB",
        "description": _(
            "Fornisce una valutazione basata sulla media dei punteggi Buchholz "
            "degli avversari con cui il giocatore ha disputato partite effettive."
        ),
        "formula": _(
            "Media aritmetica del punteggio Buchholz (o del Fore Buchholz) degli "
            "avversari affrontati sulla scacchiera (Articolo 8.2)."
        ),
    },
    "FB": {
        "name": _("Fore Buchholz"),
        "col_header": "FB",
        "description": _(
            "Variante preventiva del Buchholz che neutralizza l'impatto dell'ultimo "
            "turno calcolando i punteggi come se tutte le partite dell'ultimo round "
            "si fossero concluse in parità."
        ),
        "formula": _(
            "Punteggio Buchholz calcolato ipotizzando patte per tutti gli incontri "
            'accoppiati nell\'ultimo turno. È applicabile la variante "Cut-1" '
            "(Articolo 8.3, 5)."
        ),
    },
    "SB": {
        "name": _("Sonneborn-Berger"),
        "col_header": "SB",
        "description": _(
            "Premia i risultati positivi ottenuti contro avversari che hanno concluso "
            "il torneo con punteggi elevati."
        ),
        "formula": _(
            "Somma dei valori ottenuti moltiplicando il punteggio finale di ogni "
            "avversario per i punti ottenuti contro di esso. È prevista la variante "
            '"Cut-1" (SB-C1), che esclude il contributo associato all\'avversario '
            "con il punteggio più basso (Articolo 9.1, 14.1.1)."
        ),
    },
    "ARO": {
        "name": _("Media Rating Avversari"),
        "col_header": "ARO",
        "description": _(
            "Determina la difficoltà tecnica del torneo affrontato basandosi sulla "
            "forza media (rating) degli avversari. In presenza di giocatori senza "
            "rating, questi criteri devono essere esclusi dall'elenco degli "
            "spareggi, a meno che non siano pubblicate disposizioni specifiche "
            "prima dell'inizio (Articolo 10)."
        ),
        "formula": _(
            "Media dei rating degli avversari incontrati sulla scacchiera, "
            "arrotondata all'intero più vicino (con 0,5 arrotondato per eccesso). "
            'È prevista la variante "Cut-1" (ARO-C1), che esclude il rating '
            "dell'avversario più debole (Articolo 10.1, 14.1.1)."
        ),
    },
    "TPR": {
        "name": _("Rating di Performance"),
        "col_header": "TPR",
        "description": _(
            "Rappresenta il livello di forza espresso dal giocatore durante il "
            "torneo, basato sul punteggio percentuale e sul rating medio degli "
            "avversari."
        ),
        "formula": _(
            "Somma tra la Media del Rating degli Avversari (ARO) e la differenza "
            "di rating (RD) derivata dalla tabella di conversione FIDE applicata "
            "al punteggio frazionario (Articolo 10.2)."
        ),
    },
    "PTP": {
        "name": _("Performance Perfetta"),
        "col_header": "PTP",
        "description": _(
            "Identifica il rating più basso necessario affinché il punteggio "
            "atteso del giocatore sia pari o superiore a quello effettivamente "
            "realizzato, utilizzando l'intera scala di rating senza limiti di "
            "differenza."
        ),
        "formula": _(
            "Valore intero corrispondente al rating più basso calcolato tramite "
            "le probabilità di punteggio definite dalle normative FIDE, senza "
            "applicare il limite di ±400 punti (Articolo 10.3)."
        ),
    },
    "APRO": {
        "name": _("Media Performance Avversari"),
        "col_header": "APRO",
        "description": _(
            "Valuta la qualità dei risultati complessivi basandosi sulla media "
            "delle prestazioni tecniche (TPR) degli avversari incontrati sulla "
            "scacchiera."
        ),
        "formula": _(
            "Media aritmetica delle performance (TPR) degli avversari affrontati "
            "sulla scacchiera, arrotondata all'intero più vicino con 0,5 "
            "arrotondato per eccesso (Articolo 10.4)."
        ),
    },
    "APPO": {
        "name": _("Media Performance Perfetta Avversari"),
        "col_header": "APPO",
        "description": _(
            "Analizza il livello degli avversari basandosi sulla media dei loro "
            "valori di Performance Perfetta del Torneo (PTP)."
        ),
        "formula": _(
            "Media aritmetica dei valori PTP degli avversari affrontati sulla "
            "scacchiera, arrotondata all'intero più vicino con 0,5 arrotondato "
            "per eccesso (Articolo 10.5)."
        ),
    },
    "RTNG": {
        "name": _("Rating"),
        "col_header": "RTNG",
        "description": _(
            "Utilizza il rating personale del partecipante (iniziale o come da "
            "regolamento specifico) come elemento di ordinamento della classifica."
        ),
        "formula": _(
            "Ordinamento dei giocatori in base al proprio rating, solitamente "
            "dal più alto al più basso (Articolo 10.6)."
        ),
    },
}


# ---------------------------------------------------------------------------
# Mappatura retrocompatibilità: vecchie chiavi → nuovo formato
# ---------------------------------------------------------------------------
OLD_TO_NEW_MAPPING = {
    "points": None,  # Implicito, non è uno spareggio
    "withdrawn": None,  # Implicito
    "buchholz_cut1": {"key": "BH", "modifiers": {"cut1": True}},
    "buchholz": {"key": "BH", "modifiers": {}},
    "aro": {"key": "ARO", "modifiers": {}},
    "initial_elo": {"key": "RTNG", "modifiers": {}},
    "sonneborn_berger": {"key": "SB", "modifiers": {}},
    "direct_encounter": {"key": "DE", "modifiers": {}},
    "played_rounds_rep": {"key": "REP", "modifiers": {}},
    "number_of_wins": {"key": "WIN", "modifiers": {}},
    "number_of_blacks": {"key": "BPG", "modifiers": {}},
    "cumulative": {"key": "PS", "modifiers": {}},
}


# ---------------------------------------------------------------------------
# Funzioni di utilità
# ---------------------------------------------------------------------------


def get_supported_modifiers(criterion_key):
    """Restituisce la lista di chiavi modificatore supportate da un criterio."""
    return list(CRITERION_MODIFIERS.get(criterion_key, []))


def get_criterion_display_name(criterion_key, active_modifiers=None):
    """
    Restituisce il nome di visualizzazione del criterio con eventuali
    modificatori attivi indicati tra parentesi.
    Es: "Buchholz [Cut-1, Median-1]"
    """
    info = CRITERIA.get(criterion_key)
    if not info:
        return criterion_key

    name = info["name"]

    if active_modifiers:
        active_names = []
        for mod_key in CRITERION_MODIFIERS.get(criterion_key, []):
            if active_modifiers.get(mod_key, False):
                mod_info = MODIFIERS.get(mod_key)
                if mod_info:
                    active_names.append(mod_info["name"])
        if active_names:
            name += " [" + ", ".join(active_names) + "]"

    return name


def get_column_header(criterion_key, active_modifiers=None):
    """
    Restituisce l'intestazione di colonna per le classifiche.
    Es: "BH", "BH-C1", "SB-C1", "ARO-C1", "PS-C1"
    """
    info = CRITERIA.get(criterion_key)
    if not info:
        return criterion_key

    header = info["col_header"]

    if active_modifiers:
        suffix_map = {
            "cut1": "C1",
            "cut2": "C2",
            "median1": "M1",
            "median2": "M2",
        }
        active_suffixes = []
        for mod_key in CRITERION_MODIFIERS.get(criterion_key, []):
            if active_modifiers.get(mod_key, False):
                s = suffix_map.get(mod_key)
                if s:
                    active_suffixes.append(s)
        if active_suffixes:
            header += "-" + "-".join(active_suffixes)

    return header


def get_criterion_explanation(criterion_key, active_modifiers=None):
    """
    Restituisce il testo completo di spiegazione per il criterio, inclusivo
    della formula di calcolo e dello stato dei modificatori.
    """
    info = CRITERIA.get(criterion_key)
    if not info:
        return _("Criterio non riconosciuto.")

    lines = []
    lines.append(info["name"])
    lines.append("=" * len(info["name"]))
    lines.append("")
    lines.append(_("Descrizione:"))
    lines.append(info["description"])
    lines.append("")
    lines.append(_("Formula di calcolo:"))
    lines.append(info["formula"])

    # Informazioni sui modificatori applicabili
    supported = get_supported_modifiers(criterion_key)
    if supported:
        lines.append("")
        lines.append(_("Modificatori applicabili:"))
        for mod_key in supported:
            mod = MODIFIERS.get(mod_key)
            if mod:
                if active_modifiers and active_modifiers.get(mod_key, False):
                    stato = _("ATTIVO")
                else:
                    stato = _("disattivo")
                lines.append(f"  • {mod['name']} ({stato}): {mod['description']}")
    else:
        lines.append("")
        lines.append(_("Questo criterio non supporta modificatori."))

    return "\n".join(lines)


def get_default_tiebreaks():
    """
    Restituisce la configurazione predefinita dei criteri di spareggio
    nel nuovo formato (lista di dizionari).
    Corrisponde all'attuale default di Tornello: BH-C1, BH, ARO, RTNG.
    """
    return [
        {"key": "BH", "modifiers": {"cut1": True}},
        {"key": "BH", "modifiers": {}},
        {"key": "ARO", "modifiers": {}},
        {"key": "RTNG", "modifiers": {}},
    ]


def migrate_old_tiebreaks(old_list):
    """
    Converte una lista di tiebreaks nel vecchio formato (lista di stringhe)
    al nuovo formato (lista di dizionari).
    Le voci non riconosciute o implicite (points, withdrawn) vengono scartate.
    """
    if not old_list:
        return get_default_tiebreaks()

    # Se è già nel nuovo formato (lista di dizionari), restituiscilo
    if old_list and isinstance(old_list[0], dict) and "key" in old_list[0]:
        return list(old_list)

    new_list = []
    for old_key in old_list:
        if old_key in OLD_TO_NEW_MAPPING:
            mapped = OLD_TO_NEW_MAPPING[old_key]
            if mapped is not None:
                # Deep copy per evitare mutazioni
                new_list.append(
                    {
                        "key": mapped["key"],
                        "modifiers": dict(mapped.get("modifiers", {})),
                    }
                )
        # Voci non mappate vengono ignorate silenziosamente

    return new_list if new_list else get_default_tiebreaks()


def get_all_criteria_keys():
    """Restituisce tutte le chiavi dei criteri nell'ordine del regolamento."""
    return list(CRITERIA.keys())


def normalize_tiebreak_entry(entry):
    """
    Normalizza una voce tiebreak assicurandosi che sia un dizionario valido.
    Gestisce sia il vecchio formato stringa sia il nuovo formato dizionario.
    """
    if isinstance(entry, str):
        mapped = OLD_TO_NEW_MAPPING.get(entry)
        if mapped:
            return {
                "key": mapped["key"],
                "modifiers": dict(mapped.get("modifiers", {})),
            }
        # Potrebbe essere già una chiave del nuovo formato
        if entry in CRITERIA:
            return {"key": entry, "modifiers": {}}
        return None
    elif isinstance(entry, dict) and "key" in entry:
        return {"key": entry["key"], "modifiers": dict(entry.get("modifiers", {}))}
    return None
