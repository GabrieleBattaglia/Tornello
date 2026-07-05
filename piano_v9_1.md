# Tornello v9.1.0 - Piano di Sviluppo
## Gestione Dinamica delle Regole di Spareggio FIDE/FSI

Questo documento descrive il piano di sviluppo per integrare in Tornello v9.1.0 la configurazione dinamica e personalizzata dei criteri di spareggio tecnico per la stesura delle classifiche, in conformità con il documento ufficiale delle regole federali ed internazionali.

---

### 1. Documentazione di Riferimento
* **File Ufficiale**: `Regole di spareggio - RTF30062024.pdf` (Regolamento Tecnico Federale della Federazione Scacchistica Italiana - FSI, entrato in vigore il 01-02-2025).
* **Articoli Chiave**:
  * **Art. 6.9.7 (Classifica ed ex-aequo)**: Stabilisce l'uso obbligatorio del sistema **Sonneborn-Berger** per tornei con abbinamenti predeterminati (girone all'italiana) e del sistema **Buchholz Cut-1** per i tornei a sistema svizzero, in mancanza di diversa esplicita regolamentazione.
  * **Art. 6.3.1.c (Patta a forfeit - HPB)**: Cita lo spareggio tecnico **REP** ("Turni in cui si è scelto di giocare") come primo criterio per la gestione dell'Half-Point-Bye.

---

### 2. Criteri di Spareggio da Implementare (`src/stats.py`)
Tornello v9.1 implementerà tutte le regole di spareggio previste dal regolamento ufficiale FIDE/FSI. Ciascuna regola sarà calcolata dinamicamente partendo dallo storico dei risultati dei giocatori:

| Codice Criterio | Nome Criterio | Descrizione / Formula | Stato Attuale |
| :--- | :--- | :--- | :--- |
| `points` | Punti Totali | Punteggio complessivo accumulato nel torneo. | Già Presente |
| `withdrawn` | Ritirato | Ordinamento che posiziona i giocatori ritirati dopo quelli attivi. | Già Presente |
| `buchholz_cut1` | Buchholz Cut-1 | Somma dei punti degli avversari escludendo quello con il punteggio più basso. | Già Presente |
| `buchholz` | Buchholz Totale | Somma totale dei punti di tutti gli avversari incontrati. | Già Presente |
| `aro` | ARO (Average Rating of Opponents) | Media Elo degli avversari effettivamente affrontati. | Già Presente |
| `initial_elo` | Elo Iniziale (Seed) | Forza teorica iniziale (Seed di tabellone). | Già Presente |
| `sonneborn_berger` | Sonneborn-Berger (SB) | Somma dei punti degli avversari sconfitti + metà punti degli avversari con cui si è pattato. | **Da implementare** |
| `direct_encounter` | Scontro Diretto | Risultato dello scontro diretto tra i giocatori a pari punti (se si sono incontrati). | **Da implementare** |
| `played_rounds_rep` | Turni Giocati (REP) | Numero di turni in cui il giocatore ha effettivamente giocato (escludendo assenze e forfeit). | **Da implementare** |
| `number_of_wins` | Maggior Numero di Vittorie | Numero totale di vittorie conseguite nel torneo. | **Da implementare** |
| `number_of_blacks` | Incontri col Nero | Maggior numero di partite disputate con il colore Nero. | **Da implementare** |
| `cumulative` | Punteggio Progressivo | Somma dei punteggi progressivi turno per turno (criterio cumulativo). | **Da implementare** |
Nota Bene: verifica che questo documento riporti fedelmente **tutte** le regole indicate nel documento di riferimento, anche al di fuori dei paragrafi specificati. Assicurarsi altresì che il documento non sia in contraddizione con questo piano, per quanto riguarda i metodi con cui calcolare le diverse tipologie di spareggio.
---

### 3. Logica di Ordinamento Dinamico Classifica (`src/reports.py`)
Attualmente la classifica ordina i giocatori tramite una tupla statica definita in `sort_key_standings(player_item)`.
* **Modifica prevista**: la chiave di ordinamento verrà costruita dinamicamente ciclando sulla lista ordinata dei criteri configurata nel torneo:
  ```python
  def sort_key_standings(player_item, torneo):
      # Costruisce la tupla di ordinamento basandosi sull'ordine di priorità
      # definito in torneo.get("tiebreaks", default_list)
      tiebreak_order = torneo.get("tiebreaks", ["points", "withdrawn", "buchholz_cut1", "buchholz", "aro", "initial_elo"])
      sort_tuple = []
      for criterion in tiebreak_order:
          val = get_criterion_value(player_item, criterion, torneo)
          # Aggiunge il valore invertito per l'ordinamento decrescente
          sort_tuple.append(-val)
      return tuple(sort_tuple)
  ```

---

### 4. Integrazione della GUI (`src/gui/main_frame.py`)
* **Nuovo Elemento nell'Albero**:
  All'interno del ramo **Torneo** verrà aggiunto il sotto-nodo **regole di spareggio** (accanto a turni, classifica, partite, ecc.).
  * Quando questa voce sarà focalizzata, come succede con gli altri controlli, l'area di testo principale riporterà le regole applicate ed il loro esatto ordine di priorità
  * Attivando questa voce (doppio clic o Invio), si aprirà una finestra di dialogo accessibile: `TiebreakConfigDialog`.
  * Anche le classifiche, sia quelle parziali che quella finale avranno negli headers assieme agli altri dati, la lista ordinata per importanza, dei criteri di spareggio attivi.

* **Struttura della Finestra `TiebreakConfigDialog`**:
  Per garantire massima usabilità e compatibilità con gli screen reader (accessibilità), la finestra di dialogo userà i controlli nativi wxWidgets configurati con font e colori conformi alle impostazioni visive globali di Tornello:
  1. **Lista Sinistra ("Regole disponibili")**: Mostra l'elenco dei criteri non ancora applicati.
  2. **ctrltext read_only ("Spiegazione regola")**: visualizza una spiegazione della regola selezionata nel prossimo controllo.
  3. **Lista Destra ("Regole applicate")**: Mostra l'elenco ordinato delle regole attive, ciascuna numerata rigorosamente a partire da 1 (es. `1. Punti`, `2. Buchholz Cut-1`, `3. ARO`).
  4. **Pulsanti di Movimento Laterale**:
     * Premendo **Invio** o facendo doppio clic su un elemento nelle *Regole disponibili*, questo si sposterà in fondo all'elenco delle *Regole applicate*.
     * Premendo **Invio** o facendo doppio clic su un elemento nelle *Regole applicate*, questo verrà rimosso e tornerà tra quelle *Disponibili*.
  5. **Pulsanti di Riordino (Verticali)**:
     * Pulsanti **Sposta Su** (Up) e **Sposta Giù** (Down) a fianco della lista destra per cambiare la priorità delle regole attive.
  6. **Pulsanti di Conferma**:
     * Pulsanti **Conferma** (OK) e **Annulla** (Cancel) in basso, posizionati in ordine di tabulazione standard.
  7. La lista di destra sarà popolata con le regole che tornello utilizza ora, numerate come detto per priorità, che faranno da scelta di default, se l'arbitro non desidera modificarle.
  8. Associare eventi audio originali a tutti i controlli ed i movimenti/operazioni presenti e compiuti in questa finestra, usando play_sound come in tutto il resto di Tornello
  9. Assicurarsi di aver seguito le regole di accessibilità indicate nelle istruzioni utente al modello, affinché gli screen readers siano in grado di leggere le caption dei controlli quando ricevono il focus di sistema.
  10. Laddove necessario, creare moduli .py nuovi per evitare appesantimento di quelli esistenti soprattutto laddove questi presentino già una cospicua quantità di righe di codice.