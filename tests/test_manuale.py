"""Il manuale, il ChangeLog e i crediti: i tre testi che il programma mostra
nell'area centrale con F1, F2 e F3. Issue 50.

Dalla 10.5.1 la sezione 6.2.1 del manuale spiega la finestra di
programmazione di una partita, e la vecchia 6.2.1, sul ritiro dall'albero,
diventa la 6.2.2; dalla 10.5.2 la 6.2 cita voci e pulsanti della finestra
del risultato come il programma li scrive; dalla 10.5.3 i tre testi non hanno
piu' righe di separatori, che lo screen reader leggeva come una fila di
simboli; dalla 10.12.0 la nuova 6.3.1 spiega la composizione manuale del
turno, e le sue citazioni si cercano nella sua finestra, in turno_manuale.py,
nella finestra principale e nei report (issue 38). Le prove leggono i file come testo e non importano i moduli di
Tornello: le etichette si cercano fra le stringhe dei sorgenti, lette con
ast, cosi' un'etichetta cambiata nel codice e non nel manuale non passa
inosservata. Dalla 10.18.1 (issue 59) le voci dell'albero e dei menu citate
in tutto il manuale si cercano fra le stringhe della finestra principale,
main_frame.py, e nessuna citazione nomina una voce sparita: fino alla
10.18.0 la 2.2, la 4.2, la 4.3 e il capitolo 8 citavano voci che l'albero
non ha.
"""

import ast
import os
import re
from functools import cache
from itertools import pairwise

import pytest

RADICE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CARTELLA_SRC = os.path.join(RADICE, "src")
TESTI_MOSTRATI = ("MANUALE.txt", "ChangeLog.txt", "CREDITS.txt")

# Un titolo e' una riga che comincia con il numero della sezione, "6. " per i
# capitoli e "6.2.1 " per le sezioni interne, con il testo tutto maiuscolo
# fuori dalle parentesi, come "2.1 L'AREA CENTRALE (Tasto F5)". Un capitolo
# deve anche avere una riga vuota prima, che lo distingue dagli elenchi
# numerati: "4. ARO (Average Rating of Opponents)" e' una voce della 4.3. Una
# sezione interna no: gli elenchi non usano mai il numero col punto, e cosi'
# un titolo attaccato al paragrafo di prima non sfugge ai controlli su ordine
# e doppioni. La riga vuota mancante la segnala errori_dei_titoli.
TITOLO = re.compile(r"^(\d+(?:\.\d+)*)(\.?) (\S.*)$")
SEGNAPOSTO = re.compile(r"\{[^{}]*\}")

# Le etichette della finestra di programmazione che la 6.2.1 cita, tutte
# scritte in result_dialog.py.
ETICHETTE_DELLA_PROGRAMMAZIONE = (
    "Pianifica Partita...",
    "Pianificazione Partita",
    "Seleziona Giorno",
    "Ora:",
    "Minuto:",
    "Sala / URL:",
    "Arbitro non necessario",
    "Non necessario",
    "Arbitro designato:",
    # Dalla 10.15.0 (issue 58).
    "Togli programmazione",
    "Annulla",
    "Conferma",
)

# I sorgenti dove il programma scrive i testi citati dalla 6.2 e dalla 6.2.1:
# le due finestre, l'albero e la barra di stato, il no scritto a mano.
SORGENTI_DELLE_CITAZIONI = (
    os.path.join("gui", "dialogs", "result_dialog.py"),
    os.path.join("gui", "main_frame.py"),
    "stats.py",
)

# Le citazioni che il programma non scrive cosi' come sono: la data la
# compone Babel, nella lingua scelta.
CITAZIONI_DI_ESEMPIO = ("Venerdì 25 settembre 2026",)

# Le cartelle dell'albero sparite con la 10.4.0, che la 6.1 non descrive piu'.
CARTELLE_SPARITE = ("Pianificate", "Non pianificate", "Concluse", "Partite", "Partite Concluse")

# Le voci che il manuale citava fino alla 10.18.0 e che il programma non ha
# (issue 59): le cartelle della vecchia 2.2, la voce per aprire un torneo,
# che sta nel menu File come Apri Torneo..., quella degli spareggi della 4.3,
# che si chiama regole di spareggio, l'ultima voce della procedura guidata,
# che si chiama Iscrizione Giocatori, e il calcolo del turno nell'esempio
# della Time Machine, che si chiama calcola il turno successivo.
VOCI_SPARITE = (*CARTELLE_SPARITE, "Partecipanti", "Apri torneo", "Spareggi", "Avanti", "Genera Turno 3")

# Le parole con cui il manuale presenta una voce dell'albero o di un menu,
# seguite dalla voce fra virgolette, o da un elenco di voci: la voce
# "Classifica", i rami "Dati", "iscritti" e "turni".
VOCE_CITATA = re.compile(r'\b(?:voce|voci|ramo|rami)\s+("[^"]+"(?:(?:,\s*|\s+e\s+|\s+o\s+|\s+oppure\s+)"[^"]+")*)')

# Le citazioni della 2.2 e della 6.1 che il programma non scrive cosi' come
# sono. Le voci dei tornei le compone main_frame.py dal nome del torneo, dal
# mese della data di fine e dalla cartella, senza testo suo; gli indirizzi e
# i nomi li scrive l'arbitro nella programmazione, e le loro forme
# accorciate le calcola sala_e_arbitro_brevi di stats.py, provata in
# test_stats.py.
ESEMPI_DELLE_VOCI = (
    "Alfa (Ottobre 2026)",
    "Alfa (dalla cartella chiavetta)",
    "Alfa (Ottobre 2026, dalla cartella chiavetta)",
    "https://lichess.org/AbCdEfGh",
    "whatsapp https://call.whatsapp.com/voice/...",
    "whatsapp",
    "Giuseppe Ferraris",
    "Giuseppe Fer",
)


def leggi(nome):
    with open(os.path.join(RADICE, nome), encoding="utf-8") as f:
        return f.read().splitlines()


def titoli(righe):
    """I titoli numerati come (numero, testo, indice della riga), con il
    numero in forma di tupla: (6, 2, 1) per la 6.2.1."""
    trovati = []
    for i, riga in enumerate(righe):
        m = TITOLO.match(riga)
        if not m:
            continue
        numero, punto, testo = m.groups()
        parti = tuple(int(n) for n in numero.split("."))
        if (len(parti) == 1) != (punto == "."):
            continue
        if len(parti) == 1 and i > 0 and righe[i - 1].strip():
            continue
        fuori = re.sub(r"\([^)]*\)", "", testo)
        if fuori != fuori.upper() or not any(c.isalpha() for c in fuori):
            continue
        trovati.append((parti, testo, i))
    return trovati


def nome_del_numero(parti):
    return ".".join(str(n) for n in parti)


def errori_dei_titoli(righe):
    """I difetti dei titoli numerati, uno per frase: il primo che non e' il
    capitolo 1, i doppioni, i salti nell'ordine e i titoli senza la riga
    vuota prima."""
    elenco = titoli(righe)
    numeri = [parti for parti, _testo, _i in elenco]
    errori = []
    if not numeri or numeri[0] != (1,):
        errori.append("il primo titolo non e' il capitolo 1")
    visti = set()
    for parti in numeri:
        if parti in visti:
            errori.append(f"la {nome_del_numero(parti)} compare due volte")
        visti.add(parti)
    for prima, dopo in pairwise(numeri):
        if not successore_ammesso(prima, dopo):
            errori.append(f"dopo la {nome_del_numero(prima)} viene la {nome_del_numero(dopo)}")
    for parti, _testo, i in elenco:
        if i > 0 and righe[i - 1].strip():
            errori.append(f"la {nome_del_numero(parti)} non ha la riga vuota prima")
    return errori


def con_riga_aggiunta(righe, indice, riga):
    """Una copia delle righe con una riga in piu' al posto indicato."""
    return [*righe[:indice], riga, *righe[indice:]]


def sezione(righe, numero):
    """Le righe della sezione, dal titolo escluso fino al titolo seguente,
    di qualunque livello."""
    elenco = titoli(righe)
    for posizione, (parti, _testo, i) in enumerate(elenco):
        if parti == numero:
            fine = elenco[posizione + 1][2] if posizione + 1 < len(elenco) else len(righe)
            return righe[i + 1 : fine]
    raise AssertionError(f"Nel manuale manca la sezione {numero}")


def capitolo(righe, numero):
    """Le righe del capitolo, sezioni interne comprese."""
    elenco = titoli(righe)
    inizio = next(i for parti, _testo, i in elenco if parti == (numero,))
    fine = next((i for parti, _testo, i in elenco if parti == (numero + 1,)), len(righe))
    return righe[inizio + 1 : fine]


def citazioni(righe):
    return [c for riga in righe for c in re.findall(r'"([^"]+)"', riga)]


def successore_ammesso(prima, dopo):
    """Dopo la 6.2 possono venire la 6.2.1, la 6.3 o il capitolo 7: il primo
    figlio, il fratello seguente o il seguente di un livello superiore."""
    if dopo == (*prima, 1):
        return True
    return any(dopo == (*prima[:k], prima[k] + 1) for k in range(len(prima)))


@cache
def stringhe_del_sorgente(relativo):
    """Le stringhe scritte nel sorgente, lette con ast senza importarlo."""
    with open(os.path.join(CARTELLA_SRC, relativo), encoding="utf-8") as f:
        albero = ast.parse(f.read())
    return frozenset(n.value for n in ast.walk(albero) if isinstance(n, ast.Constant) and isinstance(n.value, str))


@cache
def modelli_del_sorgente(relativo):
    """Le stringhe del sorgente come espressioni regolari, con ogni
    segnaposto di format, {} o {name}, al posto di un testo qualsiasi. Quelle
    senza lettere fuori dai segnaposto restano fuori: "{}" andrebbe bene per
    qualunque citazione."""
    modelli = []
    for s in stringhe_del_sorgente(relativo):
        if not any(c.isalpha() for c in SEGNAPOSTO.sub("", s)):
            continue
        pezzi = SEGNAPOSTO.split(s)
        modelli.append(re.compile(".+".join(re.escape(p) for p in pezzi), re.DOTALL))
    return modelli


def scritta_dal_programma(citazione):
    return any(m.fullmatch(citazione) for relativo in SORGENTI_DELLE_CITAZIONI for m in modelli_del_sorgente(relativo))


def voci_citate(righe):
    """Le voci che il manuale cita fra virgolette subito dopo voce, voci,
    ramo o rami, anche in un elenco: nel ramo "giocate", i rami "Dati",
    "iscritti" e "turni"."""
    return [c for riga in righe for elenco in VOCE_CITATA.findall(riga) for c in re.findall(r'"([^"]+)"', elenco)]


def _modello_della_fstring(nodo):
    """Una f-string come espressione regolare: il testo tradotto al posto di
    {_('turni')}, un testo qualsiasi al posto di ogni altro valore. None se
    non ha lettere sue, come f"{t_name}{label_suffix}", che andrebbe bene per
    qualunque citazione."""
    pezzi = []
    lettere = False
    for parte in nodo.values:
        if isinstance(parte, ast.Constant):
            testo = str(parte.value)
        elif (
            isinstance(parte.value, ast.Call)
            and getattr(parte.value.func, "id", None) == "_"
            and parte.value.args
            and isinstance(parte.value.args[0], ast.Constant)
        ):
            testo = str(parte.value.args[0].value)
        else:
            pezzi.append(".+")
            continue
        lettere = lettere or any(c.isalpha() for c in testo)
        pezzi.append(re.escape(testo))
    return re.compile("".join(pezzi), re.DOTALL) if lettere else None


@cache
def modelli_della_finestra_principale():
    """Le voci dell'albero e dei menu che scrive main_frame.py, come
    espressioni regolari: le stringhe senza la & della lettera di scelta
    rapida e senza la scorciatoia dopo la tabulazione, cosi'
    "&Apri Torneo...\\tCtrl+O" vale "Apri Torneo...", con un testo qualsiasi
    al posto dei segnaposto di format, e le f-string con cui l'albero scrive
    i conteggi, come f"{_('turni')} ({len(rounds)})", che vale "turni (3)"."""
    with open(os.path.join(CARTELLA_SRC, "gui", "main_frame.py"), encoding="utf-8") as f:
        albero = ast.parse(f.read())
    modelli = []
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.JoinedStr):
            modello = _modello_della_fstring(nodo)
            if modello:
                modelli.append(modello)
        elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            stringa = nodo.value.split("\t")[0].replace("&", "")
            if any(c.isalpha() for c in SEGNAPOSTO.sub("", stringa)):
                modelli.append(re.compile(".+".join(re.escape(p) for p in SEGNAPOSTO.split(stringa)), re.DOTALL))
    return modelli


def scritta_dalla_finestra_principale(citazione):
    return any(m.fullmatch(citazione) for m in modelli_della_finestra_principale())


class TestTitoliDelManuale:
    def test_i_titoli_sono_unici_e_in_ordine(self):
        """Anche con la riga vuota prima, che tiene ogni titolo staccato dal
        paragrafo precedente."""
        assert errori_dei_titoli(leggi("MANUALE.txt")) == []

    def test_i_capitoli_e_le_sezioni_interne_si_riconoscono(self):
        """La lettura dei titoli non perde niente: ci sono tutti gli undici
        capitoli e la sezione piu' interna, la 2.3.1."""
        numeri = {parti for parti, _testo, _i in titoli(leggi("MANUALE.txt"))}
        assert {(n,) for n in range(1, 12)} <= numeri
        assert (2, 3, 1) in numeri

    def test_la_programmazione_sta_fra_la_6_2_e_la_6_3(self):
        elenco = {parti: testo for parti, testo, _i in titoli(leggi("MANUALE.txt"))}
        numeri = list(elenco)
        assert numeri.index((6, 2)) < numeri.index((6, 2, 1)) < numeri.index((6, 2, 2)) < numeri.index((6, 3))
        assert elenco[(6, 2, 1)] == "LA FINESTRA DI PROGRAMMAZIONE DI UNA PARTITA"
        assert elenco[(6, 2, 2)] == "RITIRARE UN GIOCATORE DALL'ALBERO"


class TestRegolaDeiTitoli:
    """Controprove su copie del manuale: un titolo messo male fa cadere la
    prova invece di sparire dal conto."""

    def test_un_doppione_attaccato_al_paragrafo_si_vede(self):
        righe = leggi("MANUALE.txt")
        inizio_6_2 = next(i for parti, _testo, i in titoli(righe) if parti == (6, 2))
        # Subito dopo l'ultima riga di testo della 6.1, prima della riga vuota.
        errori = errori_dei_titoli(con_riga_aggiunta(righe, inizio_6_2 - 1, "6.1 DOPPIONE"))
        assert "la 6.1 compare due volte" in errori
        assert "la 6.1 non ha la riga vuota prima" in errori

    def test_un_titolo_fuori_posto_in_coda_al_capitolo_si_vede(self):
        righe = leggi("MANUALE.txt")
        inizio_7 = next(i for parti, _testo, i in titoli(righe) if parti == (7,))
        errori = errori_dei_titoli(con_riga_aggiunta(righe, inizio_7 - 1, "6.9 TITOLO FUORI POSTO"))
        assert "dopo la 6.4 viene la 6.9" in errori
        assert "la 6.9 non ha la riga vuota prima" in errori

    def test_le_voci_di_un_elenco_non_sono_capitoli(self):
        righe = ["", "4. CAPITOLO", "3. Scontro Diretto", "4. ARO (Average Rating of Opponents)"]
        assert [parti for parti, _testo, _i in titoli(righe)] == [(4,)]


class TestSeparatori:
    @pytest.mark.parametrize("nome", TESTI_MOSTRATI)
    def test_nessuna_riga_di_separatori(self, nome):
        righe = leggi(nome)
        assert righe
        for numero, riga in enumerate(righe, 1):
            nuda = riga.strip()
            assert not (nuda and set(nuda) <= set("=-_")), f"{nome}, riga {numero}: {riga}"

    @pytest.mark.parametrize("nome", TESTI_MOSTRATI)
    def test_nessuna_fila_di_simboli_dentro_le_righe(self, nome):
        """Nemmeno le decorazioni attorno ai titoli, come i tre trattini per
        parte che il ChangeLog aveva nel suo."""
        for numero, riga in enumerate(leggi(nome), 1):
            assert not re.search(r"[=\-_]{3}", riga), f"{nome}, riga {numero}: {riga}"

    def test_nessun_separatore_nelle_stringhe_del_programma(self):
        """Dalla 10.13.30 anche le stringhe dei sorgenti: la spiegazione
        degli spareggi cominciava con una riga di segni uguale, costruita
        moltiplicando il segno per la lunghezza del nome del criterio, e NVDA
        la leggeva segno per segno. Si cercano le stringhe con una fila di
        tre segni e le stringhe di soli segni moltiplicate per un numero.
        Anche gli asterischi: la versione a riga di comando incorniciava gli
        errori con tre per parte."""
        segni = set("=-_~#*─═━")
        trovati = []
        for radice, _cartelle, files in os.walk(CARTELLA_SRC):
            for nome in files:
                if not nome.endswith(".py"):
                    continue
                percorso = os.path.join(radice, nome)
                relativo = os.path.relpath(percorso, CARTELLA_SRC)
                with open(percorso, encoding="utf-8") as f:
                    albero = ast.parse(f.read())
                for nodo in ast.walk(albero):
                    if isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Mult):
                        for lato in (nodo.left, nodo.right):
                            if isinstance(lato, ast.Constant) and isinstance(lato.value, str) and lato.value and set(lato.value) <= segni:
                                trovati.append(f"{relativo}, riga {nodo.lineno}: {lato.value!r} moltiplicato")
                    elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and re.search(r"([=\-_~#*─═━])\1\1", nodo.value):
                        trovati.append(f"{relativo}, riga {nodo.lineno}: {nodo.value[:60]!r}")
        assert trovati == []


class TestCitazioniDelManuale:
    def test_le_etichette_della_programmazione_sono_quelle_del_codice(self):
        testo = "\n".join(sezione(leggi("MANUALE.txt"), (6, 2, 1)))
        stringhe = stringhe_del_sorgente(SORGENTI_DELLE_CITAZIONI[0])
        for etichetta in ETICHETTE_DELLA_PROGRAMMAZIONE:
            assert f'"{etichetta}"' in testo, etichetta
            assert etichetta in stringhe, etichetta

    @pytest.mark.parametrize("numero", [(6, 2), (6, 2, 1)])
    def test_ogni_citazione_e_scritta_dal_programma(self, numero):
        """Ogni testo fra virgolette della 6.2 e della 6.2.1 e' un'etichetta o
        un messaggio del programma, con i segnaposto riempiti: i nomi dei
        giocatori nelle voci del risultato, giorno e ora nella barra di stato."""
        trovate = citazioni(sezione(leggi("MANUALE.txt"), numero))
        assert trovate
        for citazione in trovate:
            if citazione in CITAZIONI_DI_ESEMPIO:
                continue
            assert scritta_dal_programma(citazione), citazione

    def test_il_manuale_non_cita_le_voci_sparite(self):
        """Fino alla 10.18.0 la prova guardava il solo capitolo 6, e le
        cartelle sparite con la 10.4.0; dalla 10.18.1 tutto il manuale, con
        le voci che la 2.2, la 4.2, la 4.3 e il capitolo 8 citavano senza
        che il programma le avesse (issue 59)."""
        trovate = citazioni(leggi("MANUALE.txt"))
        assert len(trovate) >= 100
        for voce in VOCI_SPARITE:
            assert voce not in trovate, voce
            assert not scritta_dalla_finestra_principale(voce), voce

    def test_ogni_voce_citata_e_scritta_dalla_finestra_principale(self):
        """In qualunque punto del manuale, una voce dell'albero o di un menu
        citata dopo voce, voci, ramo o rami e' una stringa di main_frame.py,
        con i segnaposto riempiti (issue 59)."""
        trovate = voci_citate(leggi("MANUALE.txt"))
        assert len(trovate) >= 20
        for citazione in trovate:
            assert scritta_dalla_finestra_principale(citazione), citazione

    def test_le_voci_della_2_2_sono_scritte_dalla_finestra_principale(self):
        """La 2.2 descrive l'albero: ogni sua citazione e' una voce, o la
        voce di un menu, che main_frame.py scrive, tranne gli esempi delle
        voci dei tornei. Fino alla 10.18.0 citava "Apri torneo" e le cartelle
        "Dati", "Partecipanti" e "Partite" (issue 59)."""
        trovate = citazioni(sezione(leggi("MANUALE.txt"), (2, 2)))
        assert len(trovate) >= 5
        for citazione in trovate:
            if citazione in ESEMPI_DELLE_VOCI:
                continue
            assert scritta_dalla_finestra_principale(citazione), citazione

    def test_le_citazioni_della_6_1_sono_scritte_dal_programma(self):
        """La 6.1 descrive i rami dei turni e le voci delle partite, cita il
        pulsante della finestra del risultato da cui si programma una
        partita, e le forme accorciate di sala e arbitro, che scrive
        stats.py."""
        trovate = citazioni(sezione(leggi("MANUALE.txt"), (6, 1)))
        assert len(trovate) >= 20
        for citazione in trovate:
            if citazione in ESEMPI_DELLE_VOCI:
                continue
            assert scritta_dalla_finestra_principale(citazione) or scritta_dal_programma(citazione), citazione

    def test_le_citazioni_del_capitolo_8_sono_scritte_dal_programma(self):
        """Il capitolo 8, sulla Time Machine, e il suo esempio pratico citano
        le voci dell'albero e del menu Torneo, le domande, i messaggi e la
        barra di stato della finestra principale, e le voci della finestra
        del risultato. Il nome del suono, time_machine, e' quello della
        tabella EVENTI di utils.py. Che l'esempio si segua davvero lo prova
        TestEsempioDellaTimeMachine in test_canc_nell_albero.py (issue 59)."""
        trovate = citazioni(capitolo(leggi("MANUALE.txt"), 8))
        assert len(trovate) >= 20
        assert "time_machine" in stringhe_del_sorgente("utils.py")
        for citazione in trovate:
            if citazione == "time_machine":
                continue
            assert scritta_dalla_finestra_principale(citazione) or scritta_dal_programma(citazione), citazione

    def test_la_prova_delle_voci_riconosce_quelle_che_non_ci_sono(self):
        """Controprova sulle frasi di prima della 10.18.1: le voci che non
        ci sono non passano, quelle vere si'."""
        assert voci_citate(['sotto il torneo, i rami "Dati", "Partecipanti" e "Partite", e la voce "Spareggi".']) == ["Dati", "Partecipanti", "Partite", "Spareggi"]
        for voce in ("Partecipanti", "Spareggi", "Avanti", "Apri torneo", "Time Machine", "Genera Turno 3"):
            assert not scritta_dalla_finestra_principale(voce), voce
        for voce in (
            "Dati",
            "regole di spareggio",
            "Iscrizione Giocatori",
            "Apri Torneo...",
            "Time Machine (Annulla Turno)",
            "turni (3)",
            "Tornei Conclusi (2)",
            "giocate (9/13, 69.2%)",
            "Turno corrente (2/5)",
            "Avvio torneo: Coppa",
        ):
            assert scritta_dalla_finestra_principale(voce), voce

    def test_le_citazioni_degli_aggiornamenti_sono_scritte_dal_programma(self):
        """La 11.5, sugli aggiornamenti del programma (issue 37), cita le due
        finestre, la barra di stato e le frasi della versione a riga di
        comando, che Tornello passa alla traduzione nella tupla delle frasi di
        GBUtils. Il prompt del paginatore lo compone manuale di GBUtils."""
        sorgenti = (os.path.join("gui", "dialogs", "update_dialog.py"), os.path.join("gui", "main_frame.py"), "aggiornamenti.py")
        trovate = citazioni(sezione(leggi("MANUALE.txt"), (11, 5)))
        assert len(trovate) >= 10
        for citazione in trovate:
            if citazione == "Novita' (1 / 3)":
                continue
            assert any(m.fullmatch(citazione) for relativo in sorgenti for m in modelli_del_sorgente(relativo)), citazione

    def test_la_riga_dei_risultati_fide_e_quella_del_codice(self):
        """La 5.3 cita la riga che carica altri risultati FIDE come la
        scrivono l'iscrizione e la consultazione del database FIDE. Fino alla
        10.8.5 citava un testo diverso da quello del codice, che aveva anche
        due trattini per parte, letti da NVDA."""
        sorgenti = (os.path.join("gui", "dialogs", "fide_query_dialog.py"), os.path.join("gui", "dialogs", "player_enrollment_dialog.py"))
        trovate = [c for c in citazioni(sezione(leggi("MANUALE.txt"), (5, 3))) if "Mostra altri" in c]
        assert trovate
        for citazione in trovate:
            assert not citazione.startswith("-"), citazione
            for relativo in sorgenti:
                assert any(m.fullmatch(citazione) for m in modelli_del_sorgente(relativo)), (relativo, citazione)

    def test_la_composizione_manuale_sta_fra_la_6_3_e_la_6_4(self):
        elenco = {parti: testo for parti, testo, _i in titoli(leggi("MANUALE.txt"))}
        numeri = list(elenco)
        assert numeri.index((6, 3)) < numeri.index((6, 3, 1)) < numeri.index((6, 4))
        assert elenco[(6, 3, 1)] == "LA COMPOSIZIONE MANUALE DI UN TURNO"

    def test_le_citazioni_della_composizione_manuale_sono_scritte_dal_programma(self):
        """La 6.3.1, sulla composizione manuale del turno (issue 38), cita la
        domanda, la finestra con le voci delle sue liste, gli avvertimenti,
        l'albero e i report. Nelle etichette la & della lettera di scelta
        rapida non si scrive, e le righe dei report si leggono senza gli spazi
        e gli a capo intorno."""
        sorgenti = (os.path.join("gui", "dialogs", "manual_pairing_dialog.py"), os.path.join("gui", "main_frame.py"), "turno_manuale.py", "reports.py")
        modelli = []
        for relativo in sorgenti:
            for stringa in stringhe_del_sorgente(relativo):
                stringa = stringa.replace("&", "").strip()
                if any(c.isalpha() for c in SEGNAPOSTO.sub("", stringa)):
                    modelli.append(re.compile(".+".join(re.escape(p) for p in SEGNAPOSTO.split(stringa)), re.DOTALL))
        trovate = citazioni(sezione(leggi("MANUALE.txt"), (6, 3, 1)))
        assert len(trovate) >= 20
        for citazione in trovate:
            assert any(m.fullmatch(citazione) for m in modelli), citazione
        assert not any(m.fullmatch("Scacchiera 1: Rossi Mario - Verdi Anna") for m in modelli)

    def test_la_prova_riconosce_una_citazione_sbagliata(self):
        """Le etichette di prima non passano: la prova le avrebbe fermate."""
        assert scritta_dal_programma("1 - 0 (Vince Bianchi Luca)")
        assert not scritta_dal_programma("1 - 0 Forfeit (1 - 0F)")
        assert not scritta_dal_programma("Tavolo 3: Bianchi - Neri")


class TestDopoLaFinalizzazione:
    """Dalla 10.13.36 la sezione 9.3 e l'esempio pratico del capitolo 9
    dicono che cosa mostra davvero la finestra dopo la finalizzazione:
    l'area centrale torna alla schermata iniziale, e la classifica finale
    compare dalla voce Classifica del torneo, fra i Tornei Conclusi. Fino
    alla 10.13.35 dicevano che l'area centrale mostrava la classifica
    finale, mentre on_finalize_tournament chiama show_intro_message; il
    comportamento della finestra lo controlla test_comandi_delle_finestre."""

    def _esempio(self, righe):
        testo = "\n".join(capitolo(righe, 9))
        return testo[testo.index("ESEMPIO PRATICO: Chiusura del torneo") :]

    def test_la_9_3_e_l_esempio_dicono_la_schermata_iniziale(self):
        righe = leggi("MANUALE.txt")
        sezione_9_3 = "\n".join(sezione(righe, (9, 3)))
        esempio = self._esempio(righe)

        for testo in (sezione_9_3, esempio):
            assert "torna alla schermata iniziale" in testo
            assert "voce Classifica" in testo
            assert "Tornei Conclusi" in testo
        assert "viene stampata in formato testuale leggibile nell'Area Centrale" not in sezione_9_3
        assert "appare la classifica finale" not in esempio

    def test_l_esempio_cita_la_voce_dell_albero_come_la_scrive_il_programma(self):
        esempio = self._esempio(leggi("MANUALE.txt"))

        assert citazioni([esempio]) == ["Finalizza il torneo", "Torneo Sociale di Primavera"]
        assert "Finalizza il torneo" in stringhe_del_sorgente(os.path.join("gui", "main_frame.py"))

    def test_l_apertura_del_capitolo_distingue_l_albero_dal_menu(self):
        """L'apertura del capitolo 9 chiama la voce che compare nell'albero
        con il suo nome, Finalizza il torneo, come l'esempio pratico, e la
        voce del menu Torneo con il suo, Finalizza Torneo. Fino alla 10.13.35
        diceva che compariva la voce Finalizza Torneo, il nome della voce
        del menu, che non compare: c'e' sempre."""
        testo = "\n".join(capitolo(leggi("MANUALE.txt"), 9))
        apertura = testo[: testo.index("9.1 LE FORMULE DI SPAREGGIO APPLICATE")]
        stringhe = stringhe_del_sorgente(os.path.join("gui", "main_frame.py"))

        assert "compare nell'albero" in apertura
        assert citazioni([apertura]) == ["Finalizza il torneo", "Finalizza Torneo"]
        assert 'compare la voce "Finalizza Torneo"' not in apertura
        assert "Finalizza il torneo" in stringhe
        assert "&Finalizza Torneo\tCtrl+F" in stringhe


class TestSpareggiDellaSezione91:
    """La sezione 9.1 cita gli articoli del C.07 con il loro ambito: il TPR
    sulle partite giocate per l'articolo 10.2, il 15.2 soltanto per i tornei
    a turni prestabiliti, gli estremi del PTP dell'articolo 10.3 (10.13.34),
    e la clausola del regolamento del torneo che l'articolo 4.2 chiede per
    i pari che non si sorteggiano (10.13.35)."""

    def test_tpr_ptp_e_pari_merito(self):
        testo = "\n".join(sezione(leggi("MANUALE.txt"), (9, 1)))

        assert "articoli 10.2 e 15.2" not in testo
        assert "l'articolo 15.2 prescrive per i tornei a turni prestabiliti" in testo
        assert "800 punti meno del rating dell'avversario più debole" in testo
        assert "736 punti più di quello dell'avversario più forte" in testo
        assert "ha PTP 2336" in testo
        assert "l'articolo 2.1" not in testo
        assert "il bando o il regolamento del torneo deve quindi dire" in testo
