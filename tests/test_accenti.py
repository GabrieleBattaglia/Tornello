"""Gli accenti veri nelle stringhe che Tornello traduce e mostra (10.19.15,
issue 70, decisione di Gabriele del 4 novembre 2026).

Fino alla 10.19.13 molte stringhe in _() scrivevano la vocale accentata come
vocale seguita dall'apostrofo, e', piu', perche', gia', c'e', che la barra
braille mostra come due caratteri e la sintesi vocale puo' leggere male. Le
prove leggono i sorgenti di src con ast, senza importarli, e cercano in ogni
stringa in _() una vocale seguita dall'apostrofo, o dall'accento grave della
tastiera, e poi da un carattere che non e' una lettera: quello e' un accento
mancato. Le eccezioni vere sono poche. Un po' si scrive con l'apostrofo. Una
parola fra apici, come 'No', 'si' o 'Inizia torneo', finisce con l'apice
che la chiude, e non con un accento. Le frasi di FRASI_AGGIORNAMENTO_GBUTILS,
in aggiornamenti.py, devono restare identiche, carattere per carattere, a
quelle che GBUtils scrive, perche' la traduzione si trova dal testo: lo
controlla test_aggiornamento.py, e li' l'apostrofo lo decide GBUtils.
Le elisioni, come l'albero o dell'arbitro, hanno l'apostrofo dopo una
consonante, o prima di una lettera, e non contano.
"""

import ast
import os
import re

RADICE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CARTELLA_SRC = os.path.join(RADICE, "src")
LETTERA = r"[\wÀ-ÿ]"
# Una parola che finisce con una vocale seguita dall'apostrofo, o
# dall'accento grave, e poi da un carattere che non e' una lettera.
PAROLA_SENZA_ACCENTO = re.compile(rf"{LETTERA}*[aeiouAEIOU]['`](?!{LETTERA})")
# Una citazione fra apici: l'apice che la apre non segue una lettera, e
# quello che la chiude non e' seguito da una lettera.
CITAZIONE = re.compile(rf"(?<!{LETTERA})'[^'\n]*?[^\s']'(?!{LETTERA})")


def apostrofi_al_posto_degli_accenti(testo):
    """Le parole di testo con l'apostrofo al posto dell'accento, fuori dalle
    citazioni fra apici, tranne po'."""
    fuori = CITAZIONE.sub(" ", testo)
    return [p for p in PAROLA_SENZA_ACCENTO.findall(fuori) if p.lower() not in ("po'", "po`")]


def stringhe_in_traduzione():
    """(file, riga, testo) per ogni stringa costante passata a _() nei
    sorgenti di src, tranne le frasi di FRASI_AGGIORNAMENTO_GBUTILS."""
    trovate = []
    for cartella, _sotto, files in os.walk(CARTELLA_SRC):
        for nome in sorted(files):
            if not nome.endswith(".py"):
                continue
            percorso = os.path.join(cartella, nome)
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
        """Fino alla 10.19.13 erano 45, in 9 file di src, 19 delle quali gia'
        nei cataloghi delle traduzioni."""
        stringhe = stringhe_in_traduzione()
        assert len(stringhe) > 500
        trovati = [
            f"{relativo}, riga {riga}: {', '.join(parole)} in {testo[:80]!r}"
            for relativo, riga, testo in stringhe
            if (parole := apostrofi_al_posto_degli_accenti(testo))
        ]
        assert trovati == []

    def test_le_frasi_di_gbutils_sono_le_sole_lasciate_fuori(self):
        """Le frasi saltate sono le quattordici della tupla, e fra loro
        quelle con l'apostrofo restano come le scrive GBUtils."""
        tutte = []
        with open(os.path.join(CARTELLA_SRC, "aggiornamenti.py"), encoding="utf-8") as f:
            albero = ast.parse(f.read())
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == "_" and nodo.args:
                tutte.append(nodo.args[0].value)
        controllate = [t for r, _riga, t in stringhe_in_traduzione() if r == os.path.join("src", "aggiornamenti.py")]
        saltate = [t for t in tutte if t not in controllate]
        assert len(saltate) == 14
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
        for giusto in (
            "Aspetta un po', poi riprova. Po' di tempo.",
            "Scegliendo 'No', questo controllo non si ripete.",
            "(scrivi 'si' per confermare)",
            "seleziona 'Inizia torneo' dall'albero a destra.",
            "Inserisci 't' o 'u'.",
            "Il torneo è già concluso, e non si cambia più: c'è la Time Machine.",
            "Un'altra unità, dell'arbitro, l'ha già avuto.",
        ):
            assert apostrofi_al_posto_degli_accenti(giusto) == [], giusto
