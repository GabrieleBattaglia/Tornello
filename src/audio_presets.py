# Preset audio di fallback per Tornello v9
# Utilizzati come rimpiazzo se non presenti nel file di configurazione globale Acu_Collection.json

custom_presets = {
    "tornello_avvio": {
        "descrizione": "Suono di benvenuto per Tornello (arpeggio ascendente solare)",
        "score": [
            ["c5", 0.1, -0.8, 0.0],
            ["e5", 0.1, -0.4, 0.0],
            ["g5", 0.1, 0.0, 0.0],
            ["c6", 0.2, 0.4, 0.0],
        ],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.01],
    },
    "tornello_abbinamento": {
        "descrizione": "Arpeggio rapido per generazione abbinamenti Tornello",
        "score": [
            ["e5", 0.08, -0.5, 0.0],
            ["g5", 0.08, 0.0, 0.0],
            ["c6", 0.15, 0.5, 0.0],
        ],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.01],
    },
    "tornello_chiusura": {
        "descrizione": "Arpeggio discendente di chiusura per l'uscita da Tornello",
        "score": [
            ["c6", 0.1, 0.4, 0.0],
            ["g5", 0.1, 0.0, 0.0],
            ["e5", 0.1, -0.4, 0.0],
            ["c5", 0.2, -0.8, 0.0],
        ],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.01],
    },
    "tornello_time_machine": {
        "descrizione": "Effetto rewind per Time Machine",
        "score": [
            ["g4", 0.08, -0.5, 0.0],
            ["e4", 0.08, -0.2, 0.0],
            ["c4", 0.15, 0.2, 0.0],
            ["g3", 0.25, 0.5, 0.0],
        ],
        "kind": 1,
        "adsr": [0.02, 0.0, 100.0, 0.05],
    },
    "tornello_conclusione_turno": {
        "descrizione": "Accordo di conclusione turno",
        "score": [
            ["c5", 0.15, -0.3, 0.0],
            ["e5", 0.15, 0.3, 0.0],
            ["g5", 0.3, 0.0, 0.0],
        ],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.02],
    },
    "tornello_conclusione_torneo": {
        "descrizione": "Fanfara trionfale per la conclusione del torneo",
        "score": [
            ["c5", 0.1, -0.5, 0.0],
            ["e5", 0.1, -0.2, 0.0],
            ["g5", 0.1, 0.2, 0.0],
            ["c6", 0.15, 0.5, 0.0],
            ["e6", 0.15, 0.0, 0.0],
            ["g6", 0.4, 0.0, 0.0],
        ],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.05],
    },
    "tornello_aggiunta_giocatore": {
        "descrizione": "Suono per aggiunta giocatore (due note ascendenti rapide)",
        "score": [["c5", 0.08, -0.5, 0.0], ["g5", 0.15, 0.5, 0.0]],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.02],
    },
    "tornello_ritiro_giocatore": {
        "descrizione": "Suono per ritiro giocatore (due note discendenti tristi)",
        "score": [["f4", 0.15, 0.0, 0.0], ["c4", 0.3, 0.0, 0.0]],
        "kind": 1,
        "adsr": [0.02, 0.0, 100.0, 0.05],
    },
    "tornello_rimozione_giocatore": {
        "descrizione": "Suono per rimozione giocatore dalla lista",
        "score": [["g4", 0.1, -0.2, 0.0], ["d4", 0.2, 0.2, 0.0]],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.02],
    },
    "tornello_pianifica_crea": {
        "descrizione": "Pianificazione partita creata",
        "score": [
            ["d5", 0.08, -0.3, 0.0],
            ["f5", 0.08, 0.0, 0.0],
            ["a5", 0.15, 0.3, 0.0],
        ],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.02],
    },
    "tornello_pianifica_modifica": {
        "descrizione": "Pianificazione partita modificata",
        "score": [
            ["f5", 0.08, -0.3, 0.0],
            ["d5", 0.08, 0.0, 0.0],
            ["f5", 0.15, 0.3, 0.0],
        ],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.02],
    },
    "tornello_pianifica_rimuovi": {
        "descrizione": "Pianificazione partita rimossa",
        "score": [
            ["a5", 0.08, 0.3, 0.0],
            ["f5", 0.08, 0.0, 0.0],
            ["d5", 0.15, -0.3, 0.0],
        ],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.02],
    },
    "tornello_risultato_1_0": {
        "descrizione": "Risultato 1-0: Bianco vince (pan a sinistra, arpeggio brillante)",
        "score": [
            ["c5", 0.08, -0.8, 0.0],
            ["e5", 0.08, -0.8, 0.0],
            ["g5", 0.15, -0.8, 0.0],
        ],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.01],
    },
    "tornello_risultato_0_1": {
        "descrizione": "Risultato 0-1: Nero vince (pan a destra, arpeggio brillante)",
        "score": [
            ["c5", 0.08, 0.8, 0.0],
            ["e5", 0.08, 0.8, 0.0],
            ["g5", 0.15, 0.8, 0.0],
        ],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.01],
    },
    "tornello_risultato_patta": {
        "descrizione": "Risultato patta: accordo equilibrato centrato",
        "score": [["e5", 0.12, 0.0, 0.0], ["a5", 0.25, 0.0, 0.0]],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.03],
    },
    "tornello_risultato_1_F": {
        "descrizione": "Risultato 1-F: forfait Nero (pan a sinistra, toni alterni)",
        "score": [["c5", 0.1, -0.8, 0.0], ["c4", 0.2, -0.8, 0.0]],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.02],
    },
    "tornello_risultato_F_1": {
        "descrizione": "Risultato F-1: forfait Bianco (pan a destra, toni alterni)",
        "score": [["c5", 0.1, 0.8, 0.0], ["c4", 0.2, 0.8, 0.0]],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.02],
    },
    "tornello_risultato_0_0F": {
        "descrizione": "Risultato 0-0F: doppio forfait (toni discendenti cupi)",
        "score": [
            ["c4", 0.12, 0.0, 0.0],
            ["b3", 0.12, 0.0, 0.0],
            ["bb3", 0.25, 0.0, 0.0],
        ],
        "kind": 1,
        "adsr": [0.02, 0.0, 100.0, 0.04],
    },
    "fide_attesa": {
        "descrizione": "Segnale acustico basso di attesa per ricerca FIDE",
        "score": [["g3", 0.08, 0.0, -0.1]],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.02],
    },
    "fide_pronto": {
        "descrizione": "Segnale acustico acuto di fine ricerca FIDE",
        "score": [["g6", 0.08, 0.0, 0.0]],
        "kind": 1,
        "adsr": [0.01, 0.0, 100.0, 0.01],
    },
}
