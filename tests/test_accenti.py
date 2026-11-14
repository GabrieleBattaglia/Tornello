"""Gli accenti veri nelle stringhe che Tornello traduce e mostra (10.19.15,
issue 70, decisione di Gabriele del 4 novembre 2026).

Fino alla 10.19.13 molte stringhe in _() scrivevano la vocale accentata come
vocale seguita dall'apostrofo, e', piu', perche', gia', c'e', che la barra
braille mostra come due caratteri e la sintesi vocale puo' leggere male. Le
prove leggono i sorgenti di src con ast, senza importarli, e cercano in ogni
stringa in _() una vocale seguita dall'apostrofo, o dall'accento grave della
tastiera, e poi da un carattere che non e' una lettera: quello e' un accento
mancato. Dalla revisione della 10.19.15 leggono anche i file .py della
radice che pybabel estrae secondo babel.cfg, come tornello.py e
percorsi.py: fino ad allora il messaggio della cartella non scrivibile di
tornello.py, che si traduce come gli altri, sfuggiva, con puo', se' e puo'. Le eccezioni vere sono poche. Un po' si scrive con l'apostrofo, come
i troncamenti da', di', fa', sta', va', mo' e be'. Una parola fra apici, come
'No', 'si' o 'Inizia torneo', finisce con l'apice che la chiude, e non con un
accento, anche con un'elisione dentro, come 'Coppa d'Inverno'. Dalla
revisione della 10.19.15 conta anche l'apostrofo tipografico, U+2019, che
arriva dai testi incollati, e gli apici tipografici di una citazione. Le
frasi di FRASI_AGGIORNAMENTO_GBUTILS, in aggiornamenti.py, devono restare
identiche, carattere per carattere, a quelle che GBUtils scrive, perche'
la traduzione si trova dal testo: lo controlla test_aggiornamento.py, e li'
l'apostrofo lo decide GBUtils.
Le elisioni, come l'albero o dell'arbitro, hanno l'apostrofo dopo una
consonante, o prima di una lettera, e non contano.
"""

import ast
import os
import re

RADICE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CARTELLA_SRC = os.path.join(RADICE, "src")
# La configurazione con cui pybabel estrae le stringhe per i cataloghi.
CONFIGURAZIONE_DI_BABEL = os.path.join(RADICE, "babel.cfg")
LETTERA = r"[\wÀ-ÿ]"
# Gli apostrofi: quello della tastiera, l'accento grave usato al suo posto, e
# quello tipografico, U+2019.
APOSTROFO = "['`\u2019]"
# Una parola che finisce con una vocale seguita da un apostrofo, e poi da un
# carattere che non e' una lettera.
PAROLA_SENZA_ACCENTO = re.compile(rf"{LETTERA}*[aeiouAEIOU]{APOSTROFO}(?!{LETTERA})")
# Una citazione fra apici: l'apice che la apre non segue una lettera, e
# quello che la chiude non e' seguito da una lettera; dentro, un apostrofo
# seguito da una lettera e' un'elisione, come in 'Coppa d'Inverno'. Lo
# stesso con gli apici tipografici, U+2018 e U+2019.
CITAZIONE = re.compile(
    rf"(?<!{LETTERA})'(?:[^'\n]|'(?={LETTERA}))*?[^\s']'(?!{LETTERA})"
    rf"|(?<!{LETTERA})\u2018(?:[^\u2018\u2019\n]|\u2019(?={LETTERA}))*?[^\s\u2019]\u2019(?!{LETTERA})"
)
# Le parole che si scrivono con l'apostrofo: un po' e i troncamenti degli
# imperativi, da', di', fa', sta' e va', e mo' e be'.
TRONCAMENTI = ("po'", "da'", "di'", "fa'", "sta'", "va'", "mo'", "be'")


def apostrofi_al_posto_degli_accenti(testo):
    """Le parole di testo con l'apostrofo al posto dell'accento, fuori dalle
    citazioni fra apici, tranne quelle di TRONCAMENTI, con qualunque
    apostrofo."""
    fuori = CITAZIONE.sub(" ", testo)
    return [p for p in PAROLA_SENZA_ACCENTO.findall(fuori) if re.sub(APOSTROFO, "'", p.lower()) not in TRONCAMENTI]


def file_della_radice_estratti():
    """I nomi dei file .py della radice che pybabel estrae: quelli che
    corrispondono a un modello delle sezioni python di babel.cfg, come
    [python: **.py], confrontato con pathmatch di Babel, la funzione che usa
    pybabel extract (revisione della 10.19.15, issue 70)."""
    from babel.util import pathmatch

    with open(CONFIGURAZIONE_DI_BABEL, encoding="utf-8") as f:
        modelli = re.findall(r"^\[python:\s*(.+?)\s*\]", f.read(), re.MULTILINE)
    return [
        nome
        for nome in sorted(os.listdir(RADICE))
        if nome.endswith(".py") and os.path.isfile(os.path.join(RADICE, nome)) and any(pathmatch(modello, nome) for modello in modelli)
    ]


def sorgenti_controllati():
    """I percorsi dei sorgenti di cui le prove leggono le stringhe: i file
    .py di src e, dalla revisione della 10.19.15, quelli della radice che
    pybabel estrae, come tornello.py."""
    percorsi = []
    for cartella, _sotto, files in os.walk(CARTELLA_SRC):
        percorsi += [os.path.join(cartella, nome) for nome in sorted(files) if nome.endswith(".py")]
    return percorsi + [os.path.join(RADICE, nome) for nome in file_della_radice_estratti()]


def stringhe_in_traduzione():
    """(file, riga, testo) per ogni stringa costante passata a _() nei
    sorgenti di sorgenti_controllati, tranne le frasi di
    FRASI_AGGIORNAMENTO_GBUTILS."""
    trovate = []
    for percorso in sorgenti_controllati():
        with open(percorso, encoding="utf-8") as f:
            albero = ast.parse(f.read())
        di_gbutils = set()
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.Assign) and any(getattr(t, "id", None) == "FRASI_AGGIORNAMENTO_GBUTILS" for t in nodo.targets):
                di_gbutils |= {id(n) for n in ast.walk(nodo.value)}
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == "_" and nodo.args:
                primo = nodo.args[0]
                if isinstance(primo, ast.Constant) and isinstance(primo.value, str) and id(primo) not in di_gbutils:
                    trovate.append((os.path.relpath(percorso, RADICE), primo.lineno, primo.value))
    return trovate


class TestAccentiVeri:
    def test_nessuna_stringa_in_traduzione_ha_l_apostrofo_al_posto_dell_accento(self):
        """Fino alla 10.19.13 erano 46, in 10 file, 9 di src e tornello.py,
        20 delle quali gia' nei cataloghi delle traduzioni."""
        stringhe = stringhe_in_traduzione()
        assert len(stringhe) > 500
        trovati = [
            f"{relativo}, riga {riga}: {', '.join(parole)} in {testo[:80]!r}"
            for relativo, riga, testo in stringhe
            if (parole := apostrofi_al_posto_degli_accenti(testo))
        ]
        assert trovati == []

    def test_si_leggono_anche_i_file_della_radice_che_pybabel_estrae(self):
        """Revisione della 10.19.15 (issue 70, decisione di Gabriele del 4
        novembre 2026): babel.cfg, con [python: **.py], fa estrarre a
        pybabel anche i file .py della radice, e la prova li legge come
        quelli di src, compreso percorsi.py, che oggi non ha stringhe da
        tradurre. Fino ad allora leggeva soltanto src, e il messaggio della
        cartella non scrivibile di tornello.py aveva ancora puo', se' e
        puo'."""
        letti = [os.path.relpath(p, RADICE) for p in sorgenti_controllati()]
        assert "tornello.py" in letti
        assert "percorsi.py" in letti
        assert os.path.join("src", "omonimi.py") in letti
        assert "Cartella non scrivibile" in [t for r, _riga, t in stringhe_in_traduzione() if r == "tornello.py"]

    def test_le_frasi_di_gbutils_sono_le_sole_lasciate_fuori(self):
        """Le frasi saltate sono le quindici della tupla, e fra loro
        quelle con l'apostrofo restano come le scrive GBUtils."""
        tutte = []
        with open(os.path.join(CARTELLA_SRC, "aggiornamenti.py"), encoding="utf-8") as f:
            albero = ast.parse(f.read())
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == "_" and nodo.args:
                tutte.append(nodo.args[0].value)
        controllate = [t for r, _riga, t in stringhe_in_traduzione() if r == os.path.join("src", "aggiornamenti.py")]
        saltate = [t for t in tutte if t not in controllate]
        assert len(saltate) == 15
        assert [t for t in saltate if apostrofi_al_posto_degli_accenti(t)] == [
            "Hai gia' l'ultima versione,",
            "ma il pacchetto non e' ancora pronto.",
            "Novita' di questa versione:",
            "Novita'",
        ]

    def test_la_prova_riconosce_gli_accenti_mancati_e_le_eccezioni(self):
        assert apostrofi_al_posto_degli_accenti("Il torneo e' concluso, e non si cambia piu'.") == ["e'", "piu'"]
        assert apostrofi_al_posto_degli_accenti("E' finito perche' c'e' un solo giocatore.") == ["E'", "perche'", "e'"]
        assert apostrofi_al_posto_degli_accenti("La cartella '{path}' non e' scrivibile.") == ["e'"]
        assert apostrofi_al_posto_degli_accenti("Non e` stato possibile.") == ["e`"]
        # Revisione della 10.19.15: l'apostrofo tipografico, U+2019, conta
        # come quello della tastiera.
        assert apostrofi_al_posto_degli_accenti("Il torneo e\u2019 concluso.") == ["e\u2019"]
        assert apostrofi_al_posto_degli_accenti("Non c\u2019e\u2019 piu\u2019 niente.") == ["e\u2019", "piu\u2019"]
        assert apostrofi_al_posto_degli_accenti("Il torneo 'Coppa d'Inverno' e' concluso.") == ["e'"]
        for giusto in (
            "Aspetta un po', poi riprova. Po' di tempo.",
            "Scegliendo 'No', questo controllo non si ripete.",
            "(scrivi 'si' per confermare)",
            "seleziona 'Inizia torneo' dall'albero a destra.",
            "Inserisci 't' o 'u'.",
            "Il torneo è già concluso, e non si cambia più: c'è la Time Machine.",
            "Un'altra unità, dell'arbitro, l'ha già avuto.",
            # Revisione della 10.19.15: i troncamenti, e le elisioni nelle
            # citazioni, anche con gli apici tipografici.
            "Da' un'occhiata al manuale.",
            "Fa' attenzione, e va' alla voce Dati.",
            "Di' a Tornello di aspettare, e sta' tranquillo.",
            "A mo' di esempio. Be', ci siamo.",
            "Aspetta un po\u2019, e da\u2019 un'occhiata.",
            "Il torneo 'Coppa d'Inverno' è già concluso.",
            "Il torneo \u2018Coppa d\u2019Inverno\u2019 è già concluso.",
        ):
            assert apostrofi_al_posto_degli_accenti(giusto) == [], giusto
