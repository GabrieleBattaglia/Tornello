"""Il manuale, il ChangeLog e i crediti: i tre testi che il programma mostra
nell'area centrale con F1, F2 e F3. Issue 50.

Dalla 10.5.1 la sezione 6.2.1 del manuale spiega la finestra di
programmazione di una partita, e la vecchia 6.2.1, sul ritiro dall'albero,
diventa la 6.2.2; dalla 10.5.2 la 6.2 cita voci e pulsanti della finestra
del risultato come il programma li scrive; dalla 10.5.3 i tre testi non hanno
piu' righe di separatori, che lo screen reader leggeva come una fila di
simboli. Le prove leggono i file come testo e non importano i moduli di
Tornello: le etichette si cercano fra le stringhe dei sorgenti, lette con
ast, cosi' un'etichetta cambiata nel codice e non nel manuale non passa
inosservata.
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

    def test_il_capitolo_6_non_cita_le_cartelle_sparite(self):
        trovate = citazioni(capitolo(leggi("MANUALE.txt"), 6))
        assert trovate
        for cartella in CARTELLE_SPARITE:
            assert cartella not in trovate, cartella

    def test_la_prova_riconosce_una_citazione_sbagliata(self):
        """Le etichette di prima non passano: la prova le avrebbe fermate."""
        assert scritta_dal_programma("1 - 0 (Vince Bianchi Luca)")
        assert not scritta_dal_programma("1 - 0 Forfeit (1 - 0F)")
        assert not scritta_dal_programma("Tavolo 3: Bianchi - Neri")
