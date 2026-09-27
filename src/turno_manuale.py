"""La composizione manuale di un turno. Issue 38.

Quando bbpPairings risponde che non esiste un abbinamento valido, con il suo
codice di uscita 1, i giocatori rimasti hanno esaurito le coppie che il
sistema svizzero ammette: fra N giocatori ci sono N-1 avversari possibili, e
lo svizzero, che abbina per punteggio e non per completare il girone, puo'
saturare anche prima. Il regolamento FIDE (C.04.3, articolo 1.9.3) lascia
allora la decisione all'arbitro capo: dalla 10.12.0 l'arbitro compone il
turno a mano, nella finestra ManualPairingDialog, e dalla 10.13.0 parte dalla
proposta di Tornello.
Qui c'e' la logica, senza wx: i colori e le preferenze come li calcola
bbpPairings, gli avvertimenti su ogni coppia, la validazione del turno, la
proposta e le partite da registrare. La finestra chiama soltanto queste
funzioni, e nessuna di loro cambia il torneo, tranne
crea_partite_turno_manuale, che prende i numeri delle partite.
Gli avvertimenti non sono divieti: una coppia ripetuta, un secondo bye o un
colore sbilanciato si registrano, se l'arbitro lo decide. Bloccano soltanto
gli errori che renderebbero il turno incoerente, quelli di
valida_turno_manuale. Un incontro finito a tavolino non conta come gia'
giocato (C.04.2, articolo 3.5), e i colori contano solo le partite giocate
sulla scacchiera (C.04.2, articolo 3.4), come fa bbpPairings.
"""

from collections import namedtuple

from tournament import mappa_start_rank, ordina_per_start_rank

BYE_ID = "BYE_PLAYER_ID"
BIANCO = "white"
NERO = "black"
# I soli risultati che il TRF scrive come partite giocate: i forfait
# diventano + e -, e per bbpPairings non sono partite (gameWasPlayed).
RISULTATI_GIOCATI = ("1-0", "0-1", "1/2-1/2")
# Oltre questo numero di giocatori attivi la ricerca della proposta
# costerebbe troppo, e Tornello non ne fa (decisione di Gabriele).
MASSIMO_PER_LA_PROPOSTA = 16

# Un avvertimento su una coppia. tipo e' ripetuta, bye_vietato, squilibrio o
# tre_di_fila; giocatore e' l'id di chi lo riceve, None per la coppia intera;
# dettaglio sono i turni per ripetuta e bye_vietato, la differenza fra
# bianchi e neri per squilibrio, il colore per tre_di_fila.
Avvertimento = namedtuple("Avvertimento", "tipo giocatore dettaglio")


def _inverti(colore):
    if colore == BIANCO:
        return NERO
    if colore == NERO:
        return BIANCO
    return None


def _giocatore(torneo, player_id):
    for giocatore in torneo.get("players", []):
        if giocatore.get("id") == player_id:
            return giocatore
    return None


def _storico(giocatore):
    voci = [v for v in (giocatore or {}).get("results_history", []) or [] if isinstance(v, dict)]
    return sorted(voci, key=lambda v: v.get("round", 0) or 0)


def partita_giocata(voce):
    """Vero se la voce di storico e' una partita giocata sulla scacchiera:
    non un bye, non un forfait, e con il suo colore."""
    return (
        voce.get("opponent_id") not in (None, BYE_ID)
        and str(voce.get("result") or "").upper() in RISULTATI_GIOCATI
        and voce.get("color") in (BIANCO, NERO)
    )


def punti(giocatore):
    """I punti del giocatore, contati dal suo storico come fa il TRF."""
    return sum(float(v.get("score", 0.0) or 0.0) for v in (giocatore or {}).get("results_history", []) or [])


def nome_completo(giocatore):
    giocatore = giocatore or {}
    return f"{giocatore.get('last_name', '')} {giocatore.get('first_name', '')}".strip()


def nome_del_giocatore(torneo, player_id):
    """Cognome e nome del giocatore del torneo con questo id."""
    return nome_completo(_giocatore(torneo, player_id)) or str(player_id)


def _nome_breve(torneo, player_id):
    """Il cognome, e anche il nome se un altro iscritto ha lo stesso cognome:
    negli avvertimenti basta a capire di chi si parla."""
    giocatore = _giocatore(torneo, player_id) or {}
    cognome = giocatore.get("last_name", "")
    omonimi = sum(1 for p in torneo.get("players", []) if p.get("last_name", "").lower() == cognome.lower())
    return cognome if cognome and omonimi == 1 else nome_completo(giocatore) or str(player_id)


def giocatori_attivi(torneo):
    """I giocatori non ritirati, dal punteggio piu' alto, e a parita' di
    punti nell'ordine dello start rank: e' l'ordine delle liste della
    finestra e della proposta."""
    giocatori = torneo.get("players", [])
    ranghi = mappa_start_rank(giocatori)
    attivi = [p for p in giocatori if not p.get("withdrawn")]
    return sorted(attivi, key=lambda p: (-punti(p), ranghi[p["id"]]))


def giocatori_da_abbinare(torneo, coppie):
    """Gli id dei giocatori attivi che non stanno ancora in nessuna delle
    coppie, nell'ordine di giocatori_attivi: e' la lista Giocatori da
    abbinare della finestra."""
    in_coppia = {player_id for coppia in coppie for player_id in coppia if player_id is not None}
    return [p["id"] for p in giocatori_attivi(torneo) if p["id"] not in in_coppia]


def avversari_possibili(torneo, coppie, scelto):
    """Gli avversari che la lista Avversario offre al giocatore scelto: gli
    altri ancora da abbinare e, in fondo, None, cioe' il riposo, quando i
    giocatori attivi sono dispari e nessuna coppia ha ancora il bye."""
    avversari = [player_id for player_id in giocatori_da_abbinare(torneo, coppie) if player_id != scelto]
    dispari = len(giocatori_attivi(torneo)) % 2 == 1
    if dispari and not any(nero is None for _bianco, nero in coppie):
        avversari.append(None)
    return avversari


def colori_giocati(giocatore):
    """I colori delle sole partite giocate, dalla prima all'ultima."""
    return [v["color"] for v in _storico(giocatore) if partita_giocata(v)]


def _dati_colore(colori):
    """Preferenza, squilibrio e forza della preferenza, calcolati come
    Tournament::computePlayerData di bbpPairings (tournament.cpp)."""
    bianchi, neri = colori.count(BIANCO), colori.count(NERO)
    di_fila, ultimo = 0, None
    for colore in colori:
        di_fila = di_fila + 1 if colore == ultimo else 1
        ultimo = colore
    minore = NERO if bianchi > neri else BIANCO
    squilibrio = abs(bianchi - neri)
    if squilibrio > 1:
        preferenza = minore
    elif di_fila > 1:
        preferenza = _inverti(ultimo)
    elif squilibrio > 0:
        preferenza = minore
    elif di_fila:
        preferenza = _inverti(ultimo)
    else:
        preferenza = None
    assoluta = squilibrio > 1 or di_fila > 1
    return {
        "colori": colori,
        "preferenza": preferenza,
        "squilibrio": squilibrio,
        "assoluta": assoluta,
        "forte": not assoluta and squilibrio > 0,
    }


def preferenza_colore(giocatore):
    """Il colore che il giocatore dovrebbe avere e la forza della
    preferenza, come coppia: assoluta con due colori di differenza o con lo
    stesso colore nelle ultime due partite giocate, forte con un colore di
    differenza, lieve altrimenti, per alternare. (None, None) per chi non ha
    ancora giocato."""
    dati = _dati_colore(colori_giocati(giocatore))
    if dati["preferenza"] is None:
        return None, None
    forza = "assoluta" if dati["assoluta"] else "forte" if dati["forte"] else "lieve"
    return dati["preferenza"], forza


def _prima_differenza(colori_a, colori_b):
    """I colori dei due giocatori nella partita piu' recente in cui erano
    diversi, contando all'indietro le partite giocate di ciascuno, come
    findFirstColorDifference di bbpPairings (common.cpp)."""
    for colore_a, colore_b in zip(reversed(colori_a), reversed(colori_b), strict=False):
        if colore_a != colore_b:
            return colore_a, colore_b
    return None, None


def _colore_neutro(a, b):
    """Il colore del primo giocatore quando le preferenze bastano a
    deciderlo, altrimenti None: choosePlayerNeutralColor di bbpPairings
    (common.cpp)."""
    pa, pb = a["preferenza"], b["preferenza"]
    if pa != pb or pa is None or pb is None:
        if pa is not None:
            return pa
        return _inverti(pb)
    if a["assoluta"] and (a["squilibrio"] > b["squilibrio"] or not b["assoluta"]):
        return pa
    if b["assoluta"] and (b["squilibrio"] > a["squilibrio"] or not a["assoluta"]):
        return _inverti(pb)
    if a["forte"] and not b["forte"]:
        return pa
    if b["forte"] and not a["forte"]:
        return _inverti(pb)
    colore_a, colore_b = _prima_differenza(a["colori"], b["colori"])
    if colore_a is not None and colore_b is not None:
        return colore_b
    return None


def _colore_iniziale(torneo):
    impostazione = str(torneo.get("initial_board1_color_setting", "white1")).lower()
    return BIANCO if "white" in impostazione else NERO


def _indici_di_abbinamento(torneo):
    """Il rankIndex di bbpPairings: la posizione, da zero, nell'ordine dello
    start rank, fra i giocatori che il motore considera: gli attivi, e i
    ritirati che hanno giocato almeno un turno."""
    considerati = [p for p in ordina_per_start_rank(torneo.get("players", [])) if not p.get("withdrawn") or p.get("results_history")]
    return {p["id"]: i for i, p in enumerate(considerati)}


def _colore_per_rango(torneo, a, b, posizione_a, posizione_b):
    """Il colore del primo giocatore quando le preferenze non decidono: il
    giocatore piu' in alto, per punti e poi per rango, ha la sua preferenza,
    e se nessuno ne ha, il colore iniziale se il suo numero di abbinamento e'
    dispari. E' choosePlayerColor del sistema olandese di bbpPairings
    (dutch.cpp), senza accelerazione."""
    punti_a, indice_a = posizione_a
    punti_b, indice_b = posizione_b
    b_piu_in_alto = (punti_a, indice_b) < (punti_b, indice_a)
    iniziale = _colore_iniziale(torneo)
    if a["preferenza"] is None:
        if b_piu_in_alto:
            return iniziale if indice_b % 2 else _inverti(iniziale)
        return _inverti(iniziale) if indice_a % 2 else iniziale
    return _inverti(b["preferenza"]) if b_piu_in_alto else a["preferenza"]


def colore_suggerito(torneo, id_a, id_b):
    """I colori che bbpPairings darebbe alla coppia, come coppia (bianco,
    nero). Con id_b None la coppia e' il bye di id_a, e resta (id_a, None)."""
    if id_b is None:
        return id_a, None
    giocatore_a, giocatore_b = _giocatore(torneo, id_a), _giocatore(torneo, id_b)
    a, b = _dati_colore(colori_giocati(giocatore_a)), _dati_colore(colori_giocati(giocatore_b))
    colore = _colore_neutro(a, b)
    if colore is None:
        indici = _indici_di_abbinamento(torneo)
        fuori = len(indici)
        colore = _colore_per_rango(
            torneo,
            a,
            b,
            (punti(giocatore_a), indici.get(id_a, fuori)),
            (punti(giocatore_b), indici.get(id_b, fuori)),
        )
    return (id_a, id_b) if colore == BIANCO else (id_b, id_a)


def _turni_contro(giocatore, avversario_id):
    return [v.get("round") for v in _storico(giocatore) if v.get("opponent_id") == avversario_id and partita_giocata(v)]


def _turni_senza_diritto_al_bye(giocatore):
    """I turni in cui il giocatore ha avuto il bye, o una vittoria a
    tavolino: 1-F col bianco, F-1 col nero. Chi li ha avuti non riceve un
    altro bye (C.04.1, regola 4, e criterio C2 del sistema olandese)."""
    turni = []
    for voce in _storico(giocatore):
        risultato = str(voce.get("result") or "").upper()
        bye = voce.get("opponent_id") == BYE_ID or risultato == "BYE"
        tavolino = (risultato == "1-F" and voce.get("color") == BIANCO) or (risultato == "F-1" and voce.get("color") == NERO)
        if bye or tavolino:
            turni.append(voce.get("round"))
    return turni


def avvertimenti_coppia(torneo, bianco, nero=None):
    """Gli avvertimenti di una coppia con questi colori, o del bye di bianco
    se nero e' None:
    la coppia ha gia' giocato, con i turni: non conta un incontro finito a
    tavolino (C.04.2, articolo 3.5);
    il bye a chi ha gia' avuto un bye o una vittoria a tavolino;
    un giocatore arriverebbe a tre colori di differenza (C.04.1, regola 6);
    un giocatore avrebbe lo stesso colore per la terza volta di fila (C.04.1,
    regola 7)."""
    giocatore_bianco = _giocatore(torneo, bianco)
    if nero is None:
        turni = _turni_senza_diritto_al_bye(giocatore_bianco)
        return [Avvertimento("bye_vietato", bianco, turni)] if turni else []
    avvertimenti = []
    turni = _turni_contro(giocatore_bianco, nero)
    if turni:
        avvertimenti.append(Avvertimento("ripetuta", None, turni))
    for player_id, colore in ((bianco, BIANCO), (nero, NERO)):
        colori = [*colori_giocati(_giocatore(torneo, player_id)), colore]
        differenza = colori.count(BIANCO) - colori.count(NERO)
        if abs(differenza) > 2:
            avvertimenti.append(Avvertimento("squilibrio", player_id, differenza))
        if colori[-3:] == [colore] * 3:
            avvertimenti.append(Avvertimento("tre_di_fila", player_id, colore))
    return avvertimenti


def descrivi_avvertimento(torneo, avvertimento):
    """L'avvertimento detto a parole, breve, per le voci delle liste."""
    tipo, player_id, dettaglio = avvertimento
    if tipo == "ripetuta":
        if len(dettaglio) == 1:
            return _("gia' incontrati al turno {turno}").format(turno=dettaglio[0])
        return _("gia' incontrati ai turni {turni}").format(turni=", ".join(str(t) for t in dettaglio))
    nome = _nome_breve(torneo, player_id)
    if tipo == "bye_vietato":
        if len(dettaglio) == 1:
            return _("{nome} ha gia' avuto un bye o una vittoria a tavolino, al turno {turno}").format(nome=nome, turno=dettaglio[0])
        return _("{nome} ha gia' avuto un bye o una vittoria a tavolino, ai turni {turni}").format(nome=nome, turni=", ".join(str(t) for t in dettaglio))
    if tipo == "squilibrio":
        if dettaglio > 0:
            return _("{nome} con {numero} bianchi piu' dei neri").format(nome=nome, numero=dettaglio)
        return _("{nome} con {numero} neri piu' dei bianchi").format(nome=nome, numero=-dettaglio)
    if dettaglio == BIANCO:
        return _("{nome} al terzo bianco di fila").format(nome=nome)
    return _("{nome} al terzo nero di fila").format(nome=nome)


def descrivi_avvertimenti(torneo, avvertimenti):
    return [descrivi_avvertimento(torneo, a) for a in avvertimenti]


def testo_punti(valore):
    if valore == 1:
        return _("1 punto")
    return _("{punti} punti").format(punti=f"{valore:g}")


def _lettera(colore):
    return _("B") if colore == BIANCO else _("N")


def voce_giocatore(torneo, player_id):
    """La voce della lista Giocatori da abbinare: nome, punti, colori delle
    partite giocate e preferenza, per esempio Rossi Mario, 2 punti, colori
    B N B, preferenza N assoluta."""
    giocatore = _giocatore(torneo, player_id)
    colori = colori_giocati(giocatore)
    elenco = " ".join(_lettera(c) for c in colori) if colori else _("nessuno")
    testo = _("{nome}, {punti}, colori {colori}").format(nome=nome_completo(giocatore), punti=testo_punti(punti(giocatore)), colori=elenco)
    colore, forza = preferenza_colore(giocatore)
    if colore:
        forze = {"assoluta": _("assoluta"), "forte": _("forte"), "lieve": _("lieve")}
        testo += _(", preferenza {colore} {forza}").format(colore=_lettera(colore), forza=forze[forza])
    return testo


def voce_avversario(torneo, scelto, avversario):
    """La voce della lista Avversario per il giocatore scelto: nome, punti,
    chi avrebbe il bianco secondo i colori suggeriti, e gli avvertimenti di
    quella coppia. Con avversario None e' il riposo, cioe' il bye."""
    if avversario is None:
        testo = _("Riposo (bye)")
        avvertimenti = avvertimenti_coppia(torneo, scelto, None)
    else:
        bianco, nero = colore_suggerito(torneo, scelto, avversario)
        giocatore = _giocatore(torneo, avversario)
        testo = _("{nome}, {punti}, bianco a {bianco}").format(
            nome=nome_completo(giocatore), punti=testo_punti(punti(giocatore)), bianco=_nome_breve(torneo, bianco)
        )
        avvertimenti = avvertimenti_coppia(torneo, bianco, nero)
    return ", ".join([testo, *descrivi_avvertimenti(torneo, avvertimenti)])


def voce_coppia(torneo, scacchiera, bianco, nero):
    """La voce della lista Coppie composte, con i suoi avvertimenti."""
    if nero is None:
        testo = _("Scacchiera {numero}: {nome}, riposo (bye)").format(numero=scacchiera, nome=nome_completo(_giocatore(torneo, bianco)))
    else:
        testo = _("Scacchiera {numero}: {bianco} ({b}) contro {nero} ({n})").format(
            numero=scacchiera,
            bianco=nome_completo(_giocatore(torneo, bianco)),
            nero=nome_completo(_giocatore(torneo, nero)),
            b=_lettera(BIANCO),
            n=_lettera(NERO),
        )
    return ", ".join([testo, *descrivi_avvertimenti(torneo, avvertimenti_coppia(torneo, bianco, nero))])


def ordina_coppie(torneo, coppie):
    """Le coppie nell'ordine delle scacchiere, lo stesso di sortResults di
    bbpPairings (common.cpp): prima quella il cui giocatore piu' alto in
    classifica ha piu' punti, poi quella con la somma dei punti piu' alta,
    poi quella il cui giocatore piu' alto in classifica e' meglio piazzato
    nello start rank; il bye in fondo. Il piu' alto in classifica della
    coppia e' quello con piu' punti, e a parita' quello con lo start rank
    migliore: lo start rank dell'altro non conta, anche quando e' migliore."""
    giocatori = torneo.get("players", [])
    ranghi = mappa_start_rank(giocatori)
    fuori = len(ranghi) + 1
    punti_di = {p.get("id"): punti(p) for p in giocatori}

    def chiave(coppia):
        bianco, nero = coppia
        if nero is None:
            return (1, 0.0, 0.0, ranghi.get(bianco, fuori))
        pb, pn = punti_di.get(bianco, 0.0), punti_di.get(nero, 0.0)
        alto = min((bianco, nero), key=lambda i: (-punti_di.get(i, 0.0), ranghi.get(i, fuori)))
        return (0, -max(pb, pn), -(pb + pn), ranghi.get(alto, fuori))

    return sorted(coppie, key=chiave)


def valida_turno_manuale(torneo, coppie):
    """Controlla le coppie di un turno composto a mano, date come (bianco,
    nero), con nero None per il bye. Restituisce due elenchi di frasi, gli
    errori e gli avvertimenti. Sono errori, che impediscono di registrare il
    turno, soltanto: un giocatore attivo senza coppia o in piu' coppie, un
    ritirato o un id sconosciuto, un giocatore contro se stesso, un numero
    di bye diverso da quello necessario, cioe' uno con i giocatori attivi
    dispari e nessuno con i pari. Gli avvertimenti, uno per scacchiera, sono
    quelli di avvertimenti_coppia: il turno si registra lo stesso, se
    l'arbitro lo conferma."""
    errori = []
    attivi = [p["id"] for p in giocatori_attivi(torneo)]
    presenze = {}
    bye = 0
    for bianco, nero in coppie:
        if bianco is None:
            errori.append(_("Una coppia non ha il giocatore con il bianco."))
            continue
        if nero is None:
            bye += 1
        elif nero == bianco:
            errori.append(_("{nome} non puo' giocare contro se stesso.").format(nome=_nome_breve(torneo, bianco)))
        for player_id in [bianco] if nero in (None, bianco) else [bianco, nero]:
            giocatore = _giocatore(torneo, player_id)
            if giocatore is None:
                errori.append(_("Il giocatore {id} non e' iscritto al torneo.").format(id=player_id))
            elif giocatore.get("withdrawn"):
                errori.append(_("{nome} si e' ritirato dal torneo e non puo' essere abbinato.").format(nome=nome_completo(giocatore)))
            presenze[player_id] = presenze.get(player_id, 0) + 1
    for player_id in attivi:
        volte = presenze.get(player_id, 0)
        if volte == 0:
            errori.append(_("{nome} non ha ancora una coppia.").format(nome=nome_completo(_giocatore(torneo, player_id))))
        elif volte > 1:
            errori.append(_("{nome} compare in piu' di una coppia.").format(nome=nome_completo(_giocatore(torneo, player_id))))
    atteso = len(attivi) % 2
    if bye != atteso:
        if atteso:
            errori.append(_("Con {attivi} giocatori attivi, un numero dispari, uno solo riposa con il bye: le coppie ne hanno {bye}.").format(attivi=len(attivi), bye=bye))
        else:
            errori.append(_("Con {attivi} giocatori attivi, un numero pari, nessuno riposa: le coppie hanno {bye} bye.").format(attivi=len(attivi), bye=bye))
    avvertimenti = []
    for scacchiera, (bianco, nero) in enumerate(ordina_coppie(torneo, [c for c in coppie if c[0] is not None]), 1):
        if _giocatore(torneo, bianco) is None or (nero is not None and _giocatore(torneo, nero) is None):
            continue
        testi = descrivi_avvertimenti(torneo, avvertimenti_coppia(torneo, bianco, nero))
        if not testi:
            continue
        if nero is None:
            coppia = _("riposo di {nome}").format(nome=nome_completo(_giocatore(torneo, bianco)))
        else:
            coppia = _("{bianco} contro {nero}").format(bianco=nome_completo(_giocatore(torneo, bianco)), nero=nome_completo(_giocatore(torneo, nero)))
        avvertimenti.append(_("Scacchiera {numero}, {coppia}: {avvertimenti}.").format(numero=scacchiera, coppia=coppia, avvertimenti=", ".join(testi)))
    return errori, avvertimenti


def crea_partite_turno_manuale(torneo, coppie, turno):
    """Le partite del turno composto a mano, con la stessa forma di quelle
    che generate_pairings_for_round prende da bbpPairings: id, turno,
    giocatori, e risultato None, o BYE per chi riposa. Le scacchiere seguono
    ordina_coppie, e il bye va in fondo. I numeri delle partite si prendono
    da next_match_id, che avanza."""
    partite = []
    for bianco, nero in ordina_coppie(torneo, coppie):
        numero = torneo.get("next_match_id", 1)
        partite.append(
            {
                "id": numero,
                "round": turno,
                "white_player_id": bianco,
                "black_player_id": nero,
                "result": None if nero is not None else "BYE",
            }
        )
        torneo["next_match_id"] = numero + 1
    return partite


def costo_coppia(torneo, bianco, nero=None):
    """Il costo di una coppia per la proposta, come tupla da confrontare in
    quest'ordine: le ripetizioni, cioe' quante volte i due hanno gia' giocato;
    i bye vietati; le violazioni di colore, fra tre colori di differenza e
    terzo colore di fila; la differenza di punteggio in centesimi di punto,
    che per il bye e' il punteggio di chi riposa, perche' riposi chi ha meno
    punti."""
    avvertimenti = avvertimenti_coppia(torneo, bianco, nero)
    ripetizioni = sum(len(a.dettaglio) for a in avvertimenti if a.tipo == "ripetuta")
    bye_vietati = sum(1 for a in avvertimenti if a.tipo == "bye_vietato")
    colori = sum(1 for a in avvertimenti if a.tipo in ("squilibrio", "tre_di_fila"))
    punti_bianco = punti(_giocatore(torneo, bianco))
    differenza = punti_bianco if nero is None else abs(punti_bianco - punti(_giocatore(torneo, nero)))
    return (ripetizioni, bye_vietati, colori, round(differenza * 100))


def proposta_abbinamento(torneo):
    """Le coppie da cui l'arbitro parte, con i colori suggeriti e
    nell'ordine delle scacchiere; None con piu' di MASSIMO_PER_LA_PROPOSTA
    giocatori attivi. E' la ricerca esaustiva dell'abbinamento dal costo piu'
    basso, sommando i costi di costo_coppia e confrontandoli nel loro ordine.
    Il primo giocatore rimasto si abbina a turno con ciascuno degli altri, e
    ogni gruppo di giocatori ancora da abbinare si risolve una volta sola:
    con 16 giocatori i gruppi sono 1596, contro i due milioni di abbinamenti
    possibili, e la proposta arriva in un centesimo di secondo. A parita' di
    costo vince il primo trovato, nell'ordine dei punti e dello start rank."""
    attivi = [p["id"] for p in giocatori_attivi(torneo)]
    if len(attivi) > MASSIMO_PER_LA_PROPOSTA:
        return None
    nodi = attivi + ([None] if len(attivi) % 2 else [])
    quanti = len(nodi)
    archi = {}
    for i in range(quanti):
        for j in range(i + 1, quanti):
            coppia = colore_suggerito(torneo, nodi[i], nodi[j])
            archi[i, j] = (costo_coppia(torneo, *coppia), coppia)
    risolti = {}

    def migliore(resto):
        if not resto:
            return (0, 0, 0, 0), ()
        if resto in risolti:
            return risolti[resto]
        primo = (resto & -resto).bit_length() - 1
        scelta = None
        for j in range(primo + 1, quanti):
            if not resto >> j & 1:
                continue
            costo, coppia = archi[primo, j]
            costo_resto, coppie_resto = migliore(resto & ~(1 << primo) & ~(1 << j))
            totale = tuple(x + y for x, y in zip(costo, costo_resto, strict=True))
            if scelta is None or totale < scelta[0]:
                scelta = (totale, (coppia, *coppie_resto))
        risolti[resto] = scelta
        return scelta

    _costo, coppie = migliore((1 << quanti) - 1)
    return ordina_coppie(torneo, list(coppie))


def numero_avvertimenti(torneo, coppie):
    """Quanti avvertimenti hanno le coppie, contati uno per uno: una coppia
    gia' giocata con un terzo bianco di fila ne ha due. E' il numero del
    campo Situazione e del riepilogo della conferma, che cosi' coincidono."""
    return sum(len(avvertimenti_coppia(torneo, bianco, nero)) for bianco, nero in coppie)


def righe_della_situazione(torneo, coppie, turno):
    """Le righe del campo Situazione, ognuna entro i 40 caratteri della barra
    braille: turno, attivi e giocatori ancora da abbinare, partite e bye,
    avvertimenti."""
    attivi = giocatori_attivi(torneo)
    da_abbinare = len(giocatori_da_abbinare(torneo, coppie))
    partite = sum(1 for _bianco, nero in coppie if nero is not None)
    bye = len(coppie) - partite
    righe = [
        _("Turno {turno} di {totale}, a mano").format(turno=turno, totale=torneo.get("total_rounds", turno)),
        _("Attivi {attivi}, da abbinare {resto}").format(attivi=len(attivi), resto=da_abbinare),
        _("Partite {partite}, bye {bye} di {atteso}").format(partite=partite, bye=bye, atteso=len(attivi) % 2),
        _("Avvertimenti {numero}").format(numero=numero_avvertimenti(torneo, coppie)),
    ]
    if len(attivi) > MASSIMO_PER_LA_PROPOSTA:
        righe.append(_("Proposta solo fino a {numero} attivi").format(numero=MASSIMO_PER_LA_PROPOSTA))
    return righe


def righe_della_conferma(torneo, coppie, turno):
    """Il riepilogo che Conferma turno mostra prima della domanda, per un
    turno senza errori: la domanda con il numero delle partite, poi quanti
    avvertimenti ci sono, contati come nel campo Situazione, e su quante
    scacchiere, poi gli avvertimenti scacchiera per scacchiera, e infine la
    copia di sicurezza e il pulsante predefinito."""
    _errori, per_scacchiera = valida_turno_manuale(torneo, coppie)
    partite = sum(1 for _bianco, nero in coppie if nero is not None)
    if partite == 1:
        righe = [_("Registrare il turno {turno} composto a mano, con una partita?").format(turno=turno)]
    else:
        righe = [_("Registrare il turno {turno} composto a mano, con {partite} partite?").format(turno=turno, partite=partite)]
    if not per_scacchiera:
        righe.append(_("Nessun avvertimento."))
    elif len(per_scacchiera) == 1:
        righe.append(_("Avvertimenti: {numero}, su una scacchiera.").format(numero=numero_avvertimenti(torneo, coppie)))
    else:
        righe.append(_("Avvertimenti: {numero}, su {scacchiere} scacchiere.").format(numero=numero_avvertimenti(torneo, coppie), scacchiere=len(per_scacchiera)))
    righe += per_scacchiera
    righe.append(_("Prima di registrare il turno Tornello fa una copia di sicurezza del torneo. Il pulsante predefinito e' No."))
    return righe
