**Tornello: La Tecnologia al Servizio della Nostra Passione Scacchistica – Storia di un Compagno Digitale per i Tornei del Club**

Benvenuti, amici scacchisti!

Nel cuore pulsante di ogni circolo di scacchi, al di là della pura competizione sulla scacchiera, esiste un lavoro organizzativo fondamentale che permette alla nostra passione di prendere forma in tornei avvincenti e ben gestiti. Chiunque abbia partecipato all'organizzazione di un torneo, anche amatoriale, conosce le sfide: la compilazione degli elenchi dei partecipanti, la generazione degli abbinamenti turno dopo turno nel rispetto delle complesse regole FIDE, il calcolo meticoloso dei punteggi e degli spareggi, la tenuta dei registri. È un compito che richiede precisione, tempo e una buona dose di pazienza.

È proprio da queste esigenze pratiche, e dalla volontà di rendere la gestione dei nostri eventi di club più fluida ed efficiente, che nasce **Tornello**, un software gestionale per tornei di scacchi con sistema svizzero. Questo articolo vuole raccontarvi la sua storia, illustrarne le capacità e spiegare come può diventare un valido alleato per tutti noi. È un progetto nato dalla passione di uno di noi, Gabry (Gabriele Battaglia), e sviluppato con un pizzico di intelligenza artificiale collaborativa, con l'obiettivo di mettere la tecnologia al servizio del nostro amato gioco.

---

### **La Scintilla Iniziale: Perché Tornello? Le Sfide dell'Organizzazione Manuale**

L'idea di Tornello ha iniziato a prendere forma osservando le dinamiche dei tornei sociali. Spesso, l'entusiasmo per la competizione si scontra con la complessità della sua gestione. La preparazione manuale degli abbinamenti, specialmente con un numero crescente di partecipanti e turni, può diventare un collo di bottiglia, portando a ritardi e, talvolta, a inevitabili errori umani che possono incrinare lo spirito sportivo. Ricordare chi ha già giocato contro chi, bilanciare i colori, gestire i giocatori che arrivano in ritardo o si ritirano, calcolare i punteggi e gli spareggi come il Buchholz: sono tutte operazioni che, se fatte a mano o con strumenti generici non specifici per gli scacchi, assorbono energie preziose che potrebbero essere dedicate al gioco stesso o alla convivialità.

La visione dietro Tornello era quindi quella di creare uno strumento su misura per le esigenze del nostro club (e potenzialmente di altri circoli con necessità simili). Un software che potesse non solo automatizzare i compiti più ripetitivi e complessi, ma anche offrire una gestione flessibile e trasparente del torneo, dalla registrazione dei giocatori alla classifica finale, passando per la creazione di un archivio storico dei giocatori e delle loro performance. Si desiderava un compagno digitale che potesse alleggerire il carico organizzativo, permettendo agli arbitri e agli organizzatori di concentrarsi sugli aspetti più importanti: assicurare un ambiente di gioco sereno e corretto, e godersi lo spettacolo sulla scacchiera.

---

### **La Ricerca Algoritmica: Un Inizio Ambizioso e una Lezione Appresa**

Con questa visione in mente, il primo approccio allo sviluppo di Tornello fu ambizioso: tentare di implementare da zero un algoritmo interno per la gestione degli abbinamenti secondo il sistema svizzero. Questo sistema si basa su principi volti a far scontrare giocatori con punteggi simili, garantendo al contempo che nessuno incontri lo stesso avversario più di una volta e che ci sia un equo bilanciamento dei colori (Bianco/Nero) assegnati a ciascun giocatore.

Implementare queste regole, codificate dalla FIDE, è un compito tutt'altro che banale. Si tratta di considerare fasce di punteggio, gestire i cosiddetti "floaters" (giocatori spostati a fasce di punteggio inferiori o superiori per necessità di abbinamento), applicare criteri di priorità per l'assegnazione dei colori e gestire i BYE (turni di riposo). Ogni dettaglio ha un impatto diretto sulla correttezza e sull'equità del torneo.

Nonostante l'impegno profuso nello scrivere questo algoritmo interno, ci si rese presto conto dell'enorme complessità nel coprire ogni singolo caso limite e nel garantire una conformità impeccabile alle direttive FIDE. Il rischio di introdurre errori sottili, capaci di generare abbinamenti non ottimali o irregolari, era concreto. Si trattò di una sorta di "nobile fallimento": un tentativo coraggioso che portò alla consapevolezza che, per un compito così critico e standardizzato, affidarsi a una soluzione già validata e specializzata sarebbe stata la scelta più saggia e affidabile.

---

### **La Svolta: L'Integrazione di `bbpPairings v6`**

Presa coscienza delle difficoltà intrinseche, la ricerca si spostò verso motori di pairing esterni ed ufficiali. La scelta cadde su **`bbpPairings`**, sviluppato da Bierema Boyz Programming, un motore conforme alle regole FIDE per il sistema svizzero Olandese.

Con il rilascio di **Tornello v9.0**, il software è stato aggiornato per integrarsi nativamente con **bbpPairings v6.0.0** (conforme alle regole FIDE 2026 e al formato TRF-2026).
Ecco come funziona la collaborazione tra Tornello e il motore di pairing:
1. **Preparazione dei Dati:** Al momento di generare gli abbinamenti per un nuovo turno, Tornello raccoglie lo stato del torneo, lo storico dei colori, dei ritiri e dei risultati.
2. **Generazione del File TRF:** Tornello formatta le informazioni in un file standardizzato `input_bbp.trf` comprensivo delle estensioni FIDE `XXR` e `XXC`.
3. **Chiamata all'Engine:** Tornello invoca silenziosamente l'eseguibile di `bbpPairings`, passandogli il file TRF.
4. **Ricezione dei Risultati:** Il motore calcola gli abbinamenti corretti e produce i file di output che Tornello legge, interpreta ed applica immediatamente allo stato interno del torneo, riorganizzando la visualizzazione dei tavoli per l'utente.

---

### **L'Evoluzione Grafica ed Accessibile (Tornello v9)**

Inizialmente nato come applicazione testuale da riga di comando (CLI), Tornello ha subito una metamorfosi completa nella versione 9, trasformandosi in una **GUI (Interfaccia Grafica Utente) nativa in wxPython**.

Questa trasformazione non ha compromesso l'accessibilità, che è rimasta la priorità assoluta del progetto. L'intera interfaccia grafica è stata meticolosamente progettata e ottimizzata per essere **utilizzabile al 100% da utenti non vedenti o ipovedenti tramite screen reader (es. NVDA o JAWS)** e interamente navigabile da tastiera senza l'ausilio del mouse.

#### **Struttura della Finestra Principale**
La finestra principale è divisa in tre sezioni logiche, navigabili rapidamente tramite tasti funzione dedicati:
* **AREA CENTRALE (F5):** Un'area di testo monospaziata in sola lettura dove vengono visualizzati in modo chiaro i manuali, lo storico dei changelog, i dettagli dei turni, gli abbinamenti e le classifiche finali. Lo screen reader può leggerla comodamente riga per riga.
* **ALBERO DI DESTRA (F6):** Un controllo ad albero (`TreeCtrl`) dinamico che funge da pannello di controllo dell'applicazione. Consente di gestire l'intero ciclo di vita di un torneo (creazione, visualizzazione dei turni, delle partite e dei risultati) inserendo dati e attivando comandi premendo semplicemente **Invio** sul nodo corrispondente.
* **BARRA DI STATO INFERIORE (F7):** Riporta informazioni di contesto immediate, messaggi di errore o istruzioni d'aiuto per l'arbitro.

---

### **Funzionalità Chiave di Tornello v9**

1. **Creazione Guidata (Wizard):** L'albero di destra guida l'arbitro nella compilazione passo-passo dei dati del torneo: Nome, Luogo, Numero di Turni, Tempo di riflessione (con classificazione automatica in Standard, Rapid o Blitz), Cartella di salvataggio personalizzabile (con controlli di integrità e fallback automatico in caso di chiavette disconnesse), e preferenze di abbinamento (colore al primo tabellone, valore del BYE a 0.5 o 1.0).
2. **Iscrizione Giocatori e Ricerca Avanzata con Operatori:**
   La finestra di iscrizione consente di cercare i giocatori nel Database Locale del circolo o direttamente nel Database FIDE Ratings integrato (composto da oltre un milione di record), offrendo una ricerca fluida con operatori di precisione:
   * **Spazio (Default):** Ricerca non esclusiva (es. `rossi ita` cerca chi contiene sia `rossi` che `ita`).
   * **Prefisso `+` (Obbligatorio):** Il termine deve essere presente nel record (es. `+rossi +ita` esclude stranieri).
   * **Prefisso `-` (Escluso):** Il termine non deve comparire (es. `rossi -milano` esclude i record contenenti `milano`).
   * **Delimitatore `=` (Frase Esatta):** Cerca l'esatta combinazione dei termini (es. `=rossi=mario`).
3. **Paginazione Intelligente e Focus Vocale:** I risultati FIDE sono paginati a blocchi di 100 per mantenere elevate le prestazioni dello screen reader. All'aggiunta di un giocatore, il sistema esegue un salto di focus automatico sulla lista degli iscritti (ordinati per ELO decrescente con numerazione), leggendo istantaneamente la conferma vocale.
4. **Sistema di Feedback Sonori Spazializzati (Acusticator):**
   Tornello v9 integra il modulo `Acusticator` di `GBUtils` per riprodurre feedback sonori per ogni evento. I suoni sono mappati nel file globale `Acu_Collection.json` e riprodotti calcolando il volume finale come delta rispetto al volume di sistema dell'app:
   * *Avvio applicazione* (`tornello_avvio`) e *chiusura sincrona* (`tornello_chiusura`).
   * *Aggiunta, ritiro e rimozione giocatore*.
   * *Pianificazione, modifica ed eliminazione partita*.
   * *Suoni spazializzati per i risultati*: arpeggio a sinistra per la vittoria del Bianco (`1-0`), arpeggio a destra per la vittoria del Nero (`0-1`), accordo bilanciato al centro per la patta (`1/2-1/2`), toni alternati per i forfait (`1-F`, `F-1`, `0-0F`).
   * *Fine turno* (`conclusione_turno`) e *conclusione torneo* (`conclusione_torneo`).
   * *Rollback del turno* (`time_machine`).
5. **Gestione Database Giocatori Locale (Ctrl+D):** Un pannello completo per esplorare, modificare i dati (anagrafica, nazione ed ELO Club personalizzato come fallback) o rimuovere i giocatori del circolo.
6. **Sincronizzazione DB FIDE (Ctrl+Y):** Consente di importare l'anagrafica e aggiornare gli Elo storici in blocco o in modalità passo-passo con risoluzione delle omonimie.

---

### **Scorciatoie da Tastiera Globali**

Tornello può essere controllato interamente con le seguenti scorciatoie:
* **F1:** Visualizza la Guida / Manuale d'Uso.
* **F2:** Visualizza il ChangeLog completo delle versioni.
* **F3:** Visualizza i Crediti e i Ringraziamenti.
* **F5 / F6 / F7:** Spostamento rapido del focus tra Area Centrale, Albero e Barra di Stato.
* **Ctrl+N:** Nuovo Torneo (Wizard).
* **Ctrl+O:** Apri Torneo (dialogo di selezione file JSON).
* **Ctrl+S:** Salva Torneo (salvataggio manuale istantaneo dello stato).
* **Ctrl+I:** Iscrizione Giocatori (attivo prima dell'inizio del turno 1).
* **Ctrl+G:** Visualizza Elenco Giocatori Iscritti nell'Area Centrale.
* **Ctrl+U:** Visualizza gli Abbinamenti del Turno Corrente.
* **Ctrl+L:** Visualizza la Classifica Corrente.
* **Ctrl+Z:** Time Machine (annulla l'ultimo turno generato e torna indietro).
* **Ctrl+F:** Finalizza Torneo (calcola spareggi Buchholz/ARO, aggiorna anagrafiche ELO locali ed archivia il torneo).
* **Ctrl+D:** Gestione Database Locale dei Giocatori.
* **Ctrl+K:** Cerca / Consulta Database FIDE Ratings.
* **Ctrl+Y:** Sincronizzazione Database locale con il tracciato FIDE.

---

### **Conclusione**

Tornello v9 rappresenta un significativo traguardo nella gestione dei tornei di scacchi di club, fondendo il rigore algoritmico del motore bbpPairings v6 ad una veste grafica moderna, un ricco design acustico immersivo ed un'accessibilità assoluta per tutti gli arbitri e organizzatori.
 Buon torneo a tutti!