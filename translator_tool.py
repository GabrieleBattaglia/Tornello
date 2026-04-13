import os
import re
import sys
import time

try:
    import polib
    from deep_translator import GoogleTranslator
except ImportError:
    print("Errore: Librerie mancanti. Installa con: pip install polib deep_translator")
    sys.exit(1)


def translate_po_file(po_file_path, target_lang):
    """
    Traduce tutte le stringhe non ancora tradotte in un file .po,
    preservando i segnaposto tipo {player} o {t}.
    """
    if not os.path.exists(po_file_path):
        print(f"Errore: File {po_file_path} non trovato.")
        return

    print(f"Caricamento file: {po_file_path}...")
    po = polib.pofile(po_file_path)
    translator = GoogleTranslator(source="it", target=target_lang)

    # Regex per trovare i segnaposto tipo {nome_variabile}
    placeholder_regex = re.compile(r"\{[^}]+\}")

    untranslated_entries = [e for e in po if not e.msgstr and e.msgid]
    total = len(untranslated_entries)

    if total == 0:
        print("Tutte le stringhe sono già tradotte.")
        return

    print(
        f"Trovate {total} stringhe da tradurre in '{target_lang}'. Inizio processo..."
    )

    count = 0
    for entry in untranslated_entries:
        original = entry.msgid

        # 1. Protezione segnaposto
        placeholders = placeholder_regex.findall(original)
        protected_text = original
        for i, ph in enumerate(placeholders):
            protected_text = protected_text.replace(ph, f"VAR{i}QQ")

        try:
            # 2. Traduzione
            translated_text = translator.translate(protected_text)

            if translated_text is None:
                print(f"\nAvviso: Traduzione vuota per '{original}'.")
                translated_text = ""

            # 3. Ripristino segnaposto
            for i, ph in enumerate(placeholders):
                translated_text = translated_text.replace(f"VAR{i}QQ", ph)

            entry.msgstr = translated_text
            count += 1

            if count % 10 == 0:
                print(f"Progresso: {count}/{total}...")
                # Piccolo delay per non farsi bannare dall'API gratuita
                time.sleep(0.5)

        except Exception as e:
            print(f"\nErrore durante la traduzione di '{original}': {e}")
            entry.msgstr = ""  # Previene crash di polib
            continue

    # Salvataggio
    po.save()
    print(f"\nLavoro completato! Tradotte {count} stringhe.")
    print(f"File salvato: {po_file_path}")
    print("Ricorda di compilare il file .mo usando: pybabel compile -d locales")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python translator_tool.py <percorso_file_po> <codice_lingua>")
        print(
            "Esempio: python translator_tool.py locales/pt/LC_MESSAGES/messages.po pt"
        )
    else:
        path = sys.argv[1]
        lang = sys.argv[2]
        translate_po_file(path, lang)
