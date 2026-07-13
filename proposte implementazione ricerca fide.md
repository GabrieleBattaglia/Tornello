# Proposte di Ottimizzazione per la Ricerca nel Database FIDE

Questo documento descrive le strategie proposte per ottimizzare le prestazioni della ricerca all'interno del database locale FIDE (attualmente basato su un file JSON da ~677 MB contenente circa 1.8 milione di record), prevenendo rallentamenti ed evitare il freeze dell'interfaccia utente (GUI) su macchine meno performanti.

---

## 1. Passaggio da JSON a SQLite (Soluzione Raccomandata)
Attualmente, il file `fide_ratings_local.json` viene interamente caricato in RAM (occupando molta memoria a causa dell'overhead degli oggetti Python) e viene scansionato linearmente ad ogni ricerca ($O(N)$).

### Dettagli dell'implementazione:
* **Database Relazionale Locale**: Convertire il file JSON in un database SQLite (`fide_ratings.db`) durante il processo di aggiornamento del DB FIDE.
* **Indici di Ricerca**: Creare indici SQL sulle colonne maggiormente utilizzate per i filtri (`last_name`, `first_name`, `id_fide`), nazionalità.
* **Query Ottimizzate**: Eseguire query SQL mirate (es. `SELECT * FROM players WHERE last_name LIKE 'query%' LIMIT 100`) che restituiscono i risultati in pochissimi millisecondi.
* **SQLite FTS (Full Text Search)**: Sfruttare il modulo nativo di SQLite FTS5 per gestire in modo nativo e velocissimo ricerche complesse con più termini o operatori logici (es. `+`, `-`).

### Vantaggi:
* **Consumo di RAM quasi nullo**: La memoria dell'applicazione rimane ridotta in quanto i dati risiedono su disco e vengono estratti solo al bisogno.
* **Velocità Istantanea**: Tempo di risposta di pochi millisecondi anziché secondi.
* **Avvio Immediato**: Nessuna attesa all'apertura del dialogo per caricare il file JSON in memoria.

---

## 2. Implementazione del Debouncing (Antirimbalzo) nella GUI
Attualmente, ad ogni carattere digitato nel controllo di ricerca (`wx.EVT_TEXT`), viene avviato immediatamente il calcolo di confronto. Se l'utente digita velocemente un nome di 6 lettere, vengono eseguite 4 ricerche complete e pesanti in sequenza.

### Dettagli dell'implementazione:
* Introdurre un timer (es. `wx.Timer`) con un ritardo di 250-300 ms.
* Ad ogni digitazione il timer si riavvia.
* La funzione di ricerca viene effettivamente eseguita solo alla scadenza del timer (ovvero quando l'utente si ferma per un istante).

### Vantaggi:
* Riduzione drastica del numero di ricerche complessive.
* Minore carico sulla CPU durante la digitazione.

---

## 3. Pre-calcolo delle Chiavi di Ricerca (Search Keys)
Se si desidera mantenere l'approccio in-memory con JSON, la funzione `match_player_query` ricostruisce e normalizza in minuscolo la stringa di confronto per ogni singolo giocatore ad ogni tasto premuto.

### Dettagli dell'implementazione:
* Durante il caricamento iniziale del database JSON, pre-generare e salvare nel dizionario di ciascun giocatore un campo normalizzato (es. `p["search_key"] = f"{last_name} {first_name} {birth_year} {federation} {id_fide}".lower()`).
* Nel ciclo di ricerca, evitare chiamate multiple a `.get()` o a `.lower()` e confrontare la query direttamente con la stringa pre-compilata.

### Vantaggi:
* Velocizzazione del ciclo lineare in Python eliminando le operazioni di string formatting ed estrazione attributi su 1 milione di iterazioni.

---

## 4. Esecuzione della Ricerca in Background (Multi-threading)
Attualmente la ricerca avviene in modo sincrono nel thread principale che gestisce l'interfaccia utente (UI Thread), congelando la finestra fino al termine dell'elaborazione.

### Dettagli dell'implementazione:
* Spostare la scansione lineare dei giocatori in un thread secondario (utilizzando il modulo `threading` di Python o `wx.lib.delayedresult`).
* Se l'utente digita un nuovo carattere mentre una ricerca è ancora in esecuzione, il thread precedente viene terminato/ignorato per avviarne uno nuovo con i parametri aggiornati.

### Vantaggi:
* La GUI di Tornello rimane completamente fluida e reattiva, non dando mai la sensazione di "blocco", anche se i calcoli in background richiedono tempo per completarsi.
Selezionare la migliore e proporla all'utente specificando livello di complessità, eventuali compromessi da accettare, eventuali criticità.
Attendere la decisione dell'utente.