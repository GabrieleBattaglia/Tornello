# Consulta il DB FIDE
# Estratto e riadattato da Tornello DEV
# Data: 22 settembre 2025
# Modificato in base alla richiesta del 2 ottobre 2025

import os
import sys
from datetime import datetime

# Add src to sys.path for local development
try:
    sys._MEIPASS
except AttributeError:
    sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), "src"))

from config import FIDE_DB_LOCAL_FILE
from db_players import aggiorna_db_fide_locale, _cerca_giocatore_nel_db_fide as cerca_giocatore_fide


# --- NUOVE FUNZIONI DI VISUALIZZAZIONE ---


def stampa_dettagli_giocatore(player):
    """
    Stampa i dati di un singolo giocatore in modo formattato e leggibile.
    Questa funzione centralizza la stampa dei dettagli.
    """
    print("-" * 30)
    for key, value in player.items():
        print(f"  {key.replace('_', ' ').capitalize():<15}: {value}")
    print("-" * 30)


def gestisci_risultati_con_pager(results):
    """
    Gestisce la visualizzazione di risultati multipli (da 4 a 100)
    con un sistema a pagine (pager).
    """
    start_index = 0
    num_results = len(results)

    while start_index < num_results:
        # Calcola l'indice di fine per la pagina corrente (massimo 10 risultati)
        end_index = min(start_index + 10, num_results)

        print(
            "\n--- Pagina "
            + str(start_index // 10 + 1)
            + f" di {(num_results + 9) // 10} ---"
        )

        # Stampa il riepilogo per i giocatori nella pagina corrente
        for i in range(start_index, end_index):
            player = results[i]
            progressivo = i + 1
            nome_completo = (
                f"{player.get('first_name', '')} {player.get('last_name', '')}"
            )
            # Usiamo .get(key, 'N/D') per evitare errori se un dato manca
            elo_std = player.get("elo_standard", "N/D")
            elo_rapid = player.get("elo_rapid", "N/D")
            anno = player.get("birth_year", "N/D")
            nazione = player.get("federation", "N/D")

            # Formattiamo la riga di riepilogo
            print(
                f"{progressivo:>3}. {nome_completo:<30} | Elo Std: {elo_std:<4} | Elo Rapid: {elo_rapid:<4} | Anno: {anno:<4} | Naz: {nazione}"
            )

        # Chiede all'utente cosa fare
        prompt = "\nInserisci il numero del giocatore per vederne i dettagli,\no premi Invio per la pagina successiva (q per tornare alla ricerca): "
        user_choice = input(prompt).strip()

        if not user_choice:  # L'utente ha premuto Invio
            start_index += 10
            if start_index >= num_results:
                print("Fine dei risultati.")
                break  # Esce dal ciclo del pager
        elif user_choice.lower() == "q":
            print("Torno alla ricerca...")
            break  # Esce dal ciclo del pager
        elif user_choice.isdigit():
            choice_index = int(user_choice)
            if 1 <= choice_index <= num_results:
                # L'utente ha scelto un giocatore valido, mostriamo i dettagli
                print(f"\n--- Dettagli per il giocatore #{choice_index} ---")
                stampa_dettagli_giocatore(
                    results[choice_index - 1]
                )  # -1 perché la lista parte da 0
                break  # Esce dal ciclo del pager dopo aver mostrato i dettagli
            else:
                print(f"ERRORE: Inserisci un numero tra 1 e {num_results}.")
        else:
            print("ERRORE: Input non valido.")


def main():
    """
    Funzione principale che orchestra il funzionamento dello script.
    """
    print("Welcome - FIDE Player Checker v1.0.1 (Data: 10 Maggio 2026) by Gabriele")
    print("--- FIDE Player Checker ---")
    print("Verifica stato database FIDE locale...")

    db_needs_update = False
    if not os.path.exists(FIDE_DB_LOCAL_FILE):
        print("\nIl database FIDE locale non è presente sul tuo computer.")
        db_needs_update = True
    else:
        try:
            # Controlla l'età del file
            file_mod_timestamp = os.path.getmtime(FIDE_DB_LOCAL_FILE)
            file_age = datetime.now() - datetime.fromtimestamp(file_mod_timestamp)
            file_age_days = file_age.days

            print(f"Info: Il tuo database FIDE locale ha {file_age_days} giorni.")
            if file_age_days >= 30:
                print("È più vecchio di 30 giorni e potrebbe essere obsoleto.")
                db_needs_update = True
        except Exception as e:
            print(f"Errore nel controllare la data del file DB FIDE locale: {e}")

    # Se il DB deve essere aggiornato, chiedi conferma all'utente
    if db_needs_update:
        user_choice = (
            input("Vuoi scaricare/aggiornare il database ora? (s/n): ").strip().lower()
        )
        if user_choice in ["s", "si", "y", "yes", ""]:
            aggiorna_db_fide_locale()
        else:
            if not os.path.exists(FIDE_DB_LOCAL_FILE):
                print("Impossibile procedere senza un database. Uscita.")
                sys.exit(0)

    print("\n--- Ricerca Giocatori ---")
    while True:
        search_term = input(
            "Inserisci parte del nome/cognome o ID FIDE (o lascia vuoto per uscire): "
        )
        if not search_term:
            break  # Esce dal ciclo se l'utente preme Invio

        results = cerca_giocatore_fide(search_term)
        num_results = len(results)

        # --- LOGICA DI VISUALIZZAZIONE MODIFICATA ---
        if num_results == 0:
            print(f"Nessun giocatore trovato per '{search_term}'.")

        elif num_results <= 3:
            print(f"\nTrovati {num_results} risultati per '{search_term}':")
            for player in results:
                stampa_dettagli_giocatore(player)  # Uso la nuova funzione

        elif num_results > 100:
            print(
                f"\nTrovati {num_results} risultati. Sono troppi per essere visualizzati."
            )
            print("Prova con una chiave di ricerca più specifica.")

        else:  # Da 4 a 100 risultati
            print(f"\nTrovati {num_results} risultati per '{search_term}'.")
            gestisci_risultati_con_pager(results)  # Uso la nuova funzione per il pager

    print("\nGrazie per aver usato FIDE Player Checker. A presto!")


# --- Esecuzione dello Script ---

if __name__ == "__main__":
    main()
