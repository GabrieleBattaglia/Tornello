"""La raccolta delle partite in PGN dopo il ripristino di una copia di
sicurezza di un torneo che la finestra non carica, dalla 10.19.58
(decisione di Gabriele dell'8 novembre 2026).

Con un altro torneo aperto, fuori e dentro la procedura guidata, dentro la
procedura senza un torneo aperto, e quando alla domanda Torneo non salvato
resta aperto il torneo di prima, la finestra non carica il torneo
ripristinato, e dalla 10.19.52 ne scrive soltanto il turno corrente e la
classifica. Dalla 10.19.58 anche la sua raccolta delle partite e' quella
che la finestra scriverebbe aprendolo e salvandolo, con le stesse funzioni:
la raccolta di prima, se ha partite che il torneo ripristinato non ha, va
nella cartella backup prima di essere sostituita, e va nel cestino se il
torneo ripristinato non ha partite in PGN; un torneo riaperto che teneva la
raccolta accanto al programma la ritrova, perche' la sua e' andata nel
cestino con la cartella d'archivio. Aprendolo e salvandolo non cambia piu'
niente. La raccolta del torneo aperto, nello stesso file, resta com'e', e
dalla correzione della 10.19.58 anche quella di un'altra edizione
archiviata con lo stesso nome, che mette in salvo il primo salvataggio del
torneo ripristinato, quando lo si apre.
Fino alla 10.19.57 la raccolta restava quella di prima del ripristino,
finche' il torneo non si apriva e si salvava.
Dalla 10.19.66 (decisione di Gabriele del 9 novembre 2026) i due messaggi
Raccolta delle partite non scritta dopo il ripristino, della raccolta che
non si scrive e della copia nella cartella backup che non riesce, finiscono
con una frase propria, con il nome del torneo ripristinato: la raccolta si
scrive quando si apre il torneo e lo si salva. Fino alla 10.19.65 finivano
con le frasi dei salvataggi, che promettono il prossimo salvataggio, ma il
prossimo salvataggio e' quello del torneo aperto, e non la scrive. Nei
salvataggi le frasi restano quelle di prima, parola per parola.
I tornei sono quelli delle prove della 10.19.52, in test_canc_sui_turni.py,
con il PGN a ogni partita giocata dei turni scelti. Le prove girano sulla
finestra principale vera, mai mostrata, con la finestra delle copie e le
finestre di messaggio finte, i suoni annotati e il cestino finto; tutto sta
nella cartella temporanea della prova."""

import copy
import json
import os
import sys

import pytest
import test_canc_sui_turni as turni

# Le due fixture della finestra principale, le stesse delle prove della
# 10.19.52 in test_canc_sui_turni.py.
principale = turni.principale
suoni = turni.suoni

SITUAZIONI = ["fuori, con Alfa aperta", "dentro, con Alfa aperta", "dentro, senza un torneo aperto", "No alla domanda Torneo non salvato"]


def _pgn(turno, partita):
    risultato = partita.get("result") or "*"
    return (
        f'[Event "Turni"]\n[Round "{turno}"]\n[White "{partita["white_player_id"]}"]\n[Black "{partita["black_player_id"]}"]\n'
        f'[Result "{risultato}"]\n\n1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 {risultato}'
    )


def _con_i_pgn(torneo, turni):
    """Il PGN a ogni partita giocata dei turni, con il risultato se c'e'."""
    for turno in torneo["rounds"]:
        if turno["round"] in turni:
            for partita in turno["matches"]:
                if partita.get("black_player_id"):
                    partita["pgn"] = _pgn(turno["round"], partita)
    return torneo


def _byte(percorso):
    with open(percorso, "rb") as f:
        return f.read()


def _copie_della_raccolta():
    """Le copie della raccolta nella cartella backup, con il loro contenuto."""
    from config import user_data_path

    return {
        nome: _byte(os.path.join(radice, nome))
        for radice, _cartelle, nomi in os.walk(user_data_path("backup"))
        for nome in nomi
        if "_pre_sostituzione_raccolta_" in nome
    }


def _raccolte_nel_cestino(cestino):
    return [p for p in cestino.ricevuti if p.endswith(".pgn")]


def _messaggi_della_finestra(monkeypatch, copie):
    """Le finestre di messaggio della finestra principale, finte: annotano
    titolo e testo nello stesso elenco della finestra delle copie, cosi'
    l'ordine si vede, e rispondono OK. Dalla 10.19.66 annotano anche, in
    copie.proprietari, il titolo, la finestra che le apre e lo stile."""
    import wx

    import gui.main_frame as mf

    copie.proprietari = []

    class Messaggio:
        def __init__(self, genitore, titolo, testo, style=wx.OK, **opzioni):
            self.domanda = bool(style & wx.YES_NO)
            copie.finestre.append((titolo, testo))
            copie.proprietari.append((titolo, genitore, style))

        def ShowModal(self):
            return wx.ID_YES if self.domanda else wx.ID_OK

        def Destroy(self):
            pass

    monkeypatch.setattr(mf, "AccessibleMsgDialog", Messaggio)


def _prepara_la_situazione(principale, monkeypatch, situazione):
    """Il torneo aperto e la procedura guidata della situazione. Con il No
    alla domanda Torneo non salvato, Alfa resta aperta senza il suo file, e
    la domanda risponde No, come in TestDopoIlRipristino."""
    import wx
    from test_comandi_delle_finestre import TestAlberoETorneoAttivo, _torneo_in_corso

    from config import user_data_path

    alfa = user_data_path("Tornello - Alfa.json")
    if situazione == "dentro, senza un torneo aperto":
        principale._nessun_torneo_aperto()
    else:
        with open(alfa, "w", encoding="utf-8") as f:
            json.dump(_torneo_in_corso("Alfa"), f)
        principale.load_tournament(alfa)
    if situazione.startswith("dentro"):
        TestAlberoETorneoAttivo._dal_menu(principale, wx.ID_NEW)
        assert principale.creation_mode
    if situazione.startswith("No"):
        os.remove(alfa)
        monkeypatch.setattr(principale, "_si_puo_lasciare_il_torneo", lambda: False)
    return alfa


def _ripristina(principale, monkeypatch, copia, cestino):
    """Dal menu File la finestra Copie di sicurezza, finta, che ripristina
    copia; restituisce il registro della finestra delle copie, le scatole di
    wx.MessageBox e le sonde del fuoco."""
    import wx
    from test_comandi_delle_finestre import TestAlberoETorneoAttivo

    copie = turni.TestIDettagliDopoIlRipristino._finestra_delle_copie(monkeypatch, copia, cestino)
    _messaggi_della_finestra(monkeypatch, copie)
    scatole = []
    monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
    registro = TestAlberoETorneoAttivo._sonde(principale)
    TestAlberoETorneoAttivo._dal_menu(principale, principale.item_backup_cleanup.GetId())
    return copie, scatole, registro


def _apri_e_salva(principale, monkeypatch, ripristinato):
    """L'arbitro apre il torneo ripristinato e lo salva."""
    if principale.creation_mode:
        principale._chiudi_la_procedura_guidata()
    monkeypatch.setattr(principale, "_si_puo_lasciare_il_torneo", lambda: True)
    principale.load_tournament(ripristinato)
    assert principale.current_tournament is not None
    principale._save_state()


def _resta_il_torneo_di_prima(principale, situazione, alfa):
    """Dopo il ripristino resta aperto il torneo di prima, Alfa, o nessuno,
    e la procedura guidata resta com'era."""
    assert principale.creation_mode is situazione.startswith("dentro")
    if situazione == "dentro, senza un torneo aperto":
        assert principale.current_tournament is None
    else:
        assert principale.current_tournament["name"] == "Alfa"
        assert os.path.normcase(principale.active_filename) == os.path.normcase(alfa)


def _la_scrive_il_salvataggio_del_ripristinato(principale, monkeypatch, ripristinato, raccolta, prima):
    """La frase propria della 10.19.66 dei messaggi della raccolta non
    scritta dopo il ripristino, Il torneo Turni e' salvato, e la raccolta si
    scrive quando apri il torneo e lo salvi, e' vera: il prossimo
    salvataggio della finestra, quello del torneo aperto, se c'e', non
    scrive la raccolta del torneo ripristinato, e nemmeno la sua apertura;
    la scrive il suo primo salvataggio, con le quattro partite del turno 1."""
    from reports import byte_della_raccolta_pgn

    if principale.current_tournament:
        principale._save_state()
    assert _byte(raccolta) == prima
    if principale.creation_mode:
        principale._chiudi_la_procedura_guidata()
    monkeypatch.setattr(principale, "_si_puo_lasciare_il_torneo", lambda: True)
    principale.load_tournament(ripristinato)
    assert principale._e_il_torneo_aperto(ripristinato)
    assert _byte(raccolta) == prima
    principale._save_state()
    with open(ripristinato, encoding="utf-8") as f:
        propria = byte_della_raccolta_pgn(json.load(f))
    assert propria.count(b"[Event ") == 4
    assert _byte(raccolta) == propria


def _torneo_in_corso_con_la_copia(principale, tmp_path, cartella, copia_con_pgn):
    """Turni con i turni da 1 a 3 completi, con il PGN a ogni partita, e la
    raccolta scritta dal salvataggio della finestra; la copia di sicurezza
    del turno 2 appena abbinato, con il PGN alle partite del turno 1, o del
    turno 1 appena abbinato, senza PGN. Con cartella lavoro, i due tornei
    tengono report e raccolta in una cartella di lavoro scelta."""
    from config import user_data_path
    from reports import file_della_raccolta_pgn

    lavoro = str(tmp_path / "lavoro")
    os.makedirs(lavoro)
    if copia_con_pgn:
        vecchio, _fotografie, _ritirato = turni._torneo_vero(abbinati=2, ultimo_completo=False)
        _con_i_pgn(vecchio, {1})
    else:
        vecchio, _fotografie, _ritirato = turni._torneo_vero(abbinati=1, ultimo_completo=False)
    vero, _fotografie, _ritirato = turni._torneo_vero(abbinati=3, ultimo_completo=True)
    _con_i_pgn(vero, {1, 2, 3})
    if cartella == "lavoro":
        vecchio["custom_save_path"] = vero["custom_save_path"] = lavoro
    copia = user_data_path(os.path.join("backup", "2026", "11 Novembre", "Tornello - Turni_turno_1_20261108_100000.json"))
    os.makedirs(os.path.dirname(copia), exist_ok=True)
    with open(copia, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in vecchio.items() if k != "players_dict"}, f, default=sorted)
    ripristinato = turni._apri(principale, copy.deepcopy(vero))
    principale._save_state()
    raccolta = file_della_raccolta_pgn(vero, ripristinato)
    assert os.path.dirname(raccolta) == (lavoro if cartella == "lavoro" else str(tmp_path))
    prima = _byte(raccolta)
    assert prima.count(b"[Event ") == 10
    return ripristinato, copia, raccolta, prima


class TestIlTorneoInCorso:
    @pytest.mark.parametrize("copia_con_pgn", [True, False], ids=["copia del turno 2 con i PGN del turno 1", "copia del turno 1 senza PGN"])
    @pytest.mark.parametrize("cartella", ["programma", "lavoro"], ids=["raccolta nella cartella del programma", "raccolta in una cartella di lavoro"])
    @pytest.mark.parametrize("situazione", SITUAZIONI)
    def test_la_raccolta_del_torneo_ripristinato(self, principale, suoni, monkeypatch, cestino_finto, tmp_path, situazione, cartella, copia_con_pgn):
        from reports import byte_della_raccolta_pgn

        ripristinato, copia, raccolta, prima = _torneo_in_corso_con_la_copia(principale, tmp_path, cartella, copia_con_pgn)
        alfa = _prepara_la_situazione(principale, monkeypatch, situazione)
        procedura = situazione.startswith("dentro")
        assert _copie_della_raccolta() == {}
        suoni.clear()

        copie, scatole, registro = _ripristina(principale, monkeypatch, copia, cestino_finto)

        with open(ripristinato, encoding="utf-8") as f:
            dati = json.load(f)
        propria = byte_della_raccolta_pgn(dati)
        if copia_con_pgn:
            # La raccolta del torneo ripristinato, con le quattro partite del
            # turno 1, e quella di prima, con le dieci partite dei turni da 1
            # a 3, nella cartella backup, identica.
            assert propria.count(b"[Event ") == 4
            assert _byte(raccolta) == propria
            assert list(_copie_della_raccolta().values()) == [prima]
            assert _raccolte_nel_cestino(cestino_finto) == []
        else:
            # Il torneo ripristinato non ha partite in PGN: la raccolta di
            # prima va nel cestino, intera, senza copia.
            assert propria is None
            assert not os.path.exists(raccolta)
            assert _raccolte_nel_cestino(cestino_finto) == [os.path.abspath(raccolta)]
            (nel_cestino,) = [n for n in os.listdir(cestino_finto.cartella) if n.endswith(".pgn")]
            assert _byte(os.path.join(cestino_finto.cartella, nel_cestino)) == prima
            assert _copie_della_raccolta() == {}
        assert [titolo for titolo, _testo in copie.finestre] == ["Conferma ripristino", "Ripristino riuscito"]
        assert copie.suoni == ["ripristino"]
        assert suoni == []
        assert scatole == []
        assert registro.caricati == []
        assert registro.fuoco == ([] if procedura else ["tree_ctrl"])
        assert principale.creation_mode is procedura
        if situazione == "dentro, senza un torneo aperto":
            assert principale.current_tournament is None
        else:
            assert principale.current_tournament["name"] == "Alfa"
            assert os.path.normcase(principale.active_filename) == os.path.normcase(alfa)
        # Aprendo il torneo ripristinato e salvandolo non cambia niente.
        dopo = _byte(raccolta) if os.path.exists(raccolta) else None
        copie_dopo = _copie_della_raccolta()
        nel_cestino = list(cestino_finto.ricevuti)
        _apri_e_salva(principale, monkeypatch, ripristinato)
        assert (_byte(raccolta) if os.path.exists(raccolta) else None) == dopo
        assert _copie_della_raccolta() == copie_dopo
        assert _raccolte_nel_cestino(cestino_finto) == [p for p in nel_cestino if p.endswith(".pgn")]
        assert len(copie.finestre) == 2
        assert suoni == []

    def test_il_cestino_non_prende_la_raccolta(self, principale, suoni, monkeypatch, cestino_finto, tmp_path):
        """Fuori dalla procedura guidata, con Alfa aperta, la copia del turno
        1 senza PGN, e il cestino che non prende la raccolta, come un disco
        senza cestino: la raccolta resta dov'e', con le partite di prima, e
        dopo il suono del ripristino il messaggio Raccolta delle partite
        rimasta lo dice, con il suono dell'errore, come a un salvataggio,
        prima del messaggio Ripristino riuscito; aprendo e salvando il torneo
        ripristinato non si ripete."""
        ripristinato, copia, raccolta, prima = _torneo_in_corso_con_la_copia(principale, tmp_path, "programma", False)
        alfa = _prepara_la_situazione(principale, monkeypatch, SITUAZIONI[0])
        cestino_finto.rifiuta.add(raccolta)
        suoni.clear()

        copie, scatole, registro = _ripristina(principale, monkeypatch, copia, cestino_finto)

        assert _byte(raccolta) == prima
        assert os.path.abspath(raccolta) in cestino_finto.tentativi
        assert _raccolte_nel_cestino(cestino_finto) == []
        assert _copie_della_raccolta() == {}
        assert [titolo for titolo, _testo in copie.finestre] == ["Conferma ripristino", "Raccolta delle partite rimasta", "Ripristino riuscito"]
        assert copie.finestre[1][1] == (
            f"Il torneo Turni non ha più partite in PGN, e la sua raccolta delle partite Turni - raccolta partite.pgn, nella cartella {os.path.dirname(raccolta)}, "
            "doveva andare nel cestino di Windows, che non l'ha presa, per esempio perché quel disco non ha il cestino. Resta dov'è, con le partite di prima: "
            "Tornello non la cancella per sempre.\n"
            "Fino alla chiusura di Tornello i salvataggi non ci riprovano, e questo messaggio non si ripete. Quando il torneo ha di nuovo una partita in PGN, "
            "se la raccolta ha ancora partite che il torneo non ha, prima di sostituirla con la raccolta nuova Tornello la mette nella cartella backup, "
            "anche dopo una chiusura di Tornello. Se non ti serve più, spostala o cancellala tu."
        )
        assert copie.suoni == ["ripristino"]
        assert suoni == ["errore"]
        assert scatole == []
        assert registro.fuoco == ["tree_ctrl"]
        assert principale._e_il_torneo_aperto(alfa)

        _apri_e_salva(principale, monkeypatch, ripristinato)

        assert _byte(raccolta) == prima
        assert len(copie.finestre) == 3
        assert suoni == ["errore"]

    @pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")
    @pytest.mark.parametrize("situazione", SITUAZIONI)
    def test_la_raccolta_che_non_si_scrive(self, principale, suoni, monkeypatch, cestino_finto, tmp_path, capsys, situazione):
        """Correzione della 10.19.58, e 10.19.66. Con la copia del turno 2
        con i PGN del turno 1, e la raccolta del torneo ripristinato che un
        altro programma tiene aperta, e lascia leggere ma non scrivere, come
        un visualizzatore di PGN: la raccolta di prima va nella cartella
        backup, resta com'era, e dopo il suono del ripristino il messaggio
        Raccolta delle partite non scritta lo dice, con il motivo che da' il
        sistema e con il suono dell'errore, come a un salvataggio, prima del
        messaggio Ripristino riuscito. Dalla 10.19.66 il messaggio finisce
        con la sua frase, con il nome del torneo ripristinato, anche con Alfa
        aperta: Il torneo Turni e' salvato, e la raccolta si scrive quando
        apri il torneo e lo salvi. Fino alla 10.19.65 finiva con la frase dei
        salvataggi: Il torneo e' salvato, e la raccolta si riscrive al
        prossimo salvataggio. Tolto il blocco, la frase e' vera: il prossimo
        salvataggio della finestra, quello di Alfa, non la scrive, e
        nemmeno l'apertura del torneo ripristinato; la scrive il suo primo
        salvataggio, senza un'altra copia e senza altri messaggi."""
        import wx
        from test_comandi_delle_finestre import TestRaccoltaSenzaPartiteNelCestino, _descrizione_dell_errore

        ripristinato, copia, raccolta, prima = _torneo_in_corso_con_la_copia(principale, tmp_path, "programma", True)
        alfa = _prepara_la_situazione(principale, monkeypatch, situazione)
        procedura = situazione.startswith("dentro")
        suoni.clear()
        capsys.readouterr()

        sblocca = TestRaccoltaSenzaPartiteNelCestino._bloccata(raccolta, TestRaccoltaSenzaPartiteNelCestino.FILE_SHARE_READ)
        try:
            copie, scatole, registro = _ripristina(principale, monkeypatch, copia, cestino_finto)
            ancora = _byte(raccolta)
        finally:
            sblocca()

        assert ancora == prima
        assert list(_copie_della_raccolta().values()) == [prima]
        assert _raccolte_nel_cestino(cestino_finto) == []
        (errore,) = TestRaccoltaSenzaPartiteNelCestino._errori_in_console(capsys)
        assert [titolo for titolo, _testo in copie.finestre] == ["Conferma ripristino", "Raccolta delle partite non scritta", "Ripristino riuscito"]
        assert copie.finestre[1][1] == (
            f"La raccolta delle partite Turni - raccolta partite.pgn, nella cartella {os.path.dirname(raccolta)}, non si è potuta scrivere: "
            f"{_descrizione_dell_errore(errore)}. Forse un altro programma la tiene aperta. Il torneo Turni è salvato, e la raccolta si scrive quando apri il torneo e lo salvi."
        )
        assert copie.proprietari == [("Raccolta delle partite non scritta", principale, wx.OK)]
        assert copie.suoni == ["ripristino"]
        assert suoni == ["errore"]
        assert scatole == []
        assert registro.caricati == []
        assert registro.fuoco == ([] if procedura else ["tree_ctrl"])
        _resta_il_torneo_di_prima(principale, situazione, alfa)

        _la_scrive_il_salvataggio_del_ripristinato(principale, monkeypatch, ripristinato, raccolta, prima)

        assert list(_copie_della_raccolta().values()) == [prima]
        assert len(copie.finestre) == 3
        assert suoni == ["errore"]

    @pytest.mark.parametrize("situazione", SITUAZIONI)
    def test_la_copia_che_non_riesce(self, principale, suoni, monkeypatch, cestino_finto, tmp_path, situazione):
        """10.19.66. Con la copia del turno 2 con i PGN del turno 1, la
        raccolta di prima, con le dieci partite dei turni da 1 a 3, ha
        partite che il torneo ripristinato non ha, e la sua copia nella
        cartella backup non riesce: la raccolta resta com'era, e dopo il
        suono del ripristino il messaggio Raccolta delle partite non scritta
        lo dice, con il suono dell'errore, prima del messaggio Ripristino
        riuscito, e finisce con la sua frase, con il nome del torneo
        ripristinato, anche con Alfa aperta: Se la raccolta di prima non ti
        serve più, spostala o cancellala tu, e la raccolta nuova del torneo
        Turni si scrive quando apri il torneo e lo salvi. Fino alla 10.19.65
        finiva con la frase dei salvataggi: e il prossimo salvataggio
        scriverà quella nuova. Quando la copia riesce, la frase e' vera: il
        prossimo salvataggio della finestra, quello di Alfa, non la scrive,
        e nemmeno l'apertura del torneo ripristinato; la scrive il suo primo
        salvataggio, dopo la copia, senza altri messaggi. Dalla correzione
        della 10.19.66 anche la frase prima dice il torneo: I salvataggi del
        torneo Turni ci riprovano; nella prima stesura diceva I salvataggi ci
        riprovano, ma con Alfa aperta i salvataggi di Alfa non ci riprovano."""
        import wx
        from test_comandi_delle_finestre import TestRaccoltaSenzaPartiteNelCestino

        import utils

        ripristinato, copia, raccolta, prima = _torneo_in_corso_con_la_copia(principale, tmp_path, "programma", True)
        alfa = _prepara_la_situazione(principale, monkeypatch, situazione)
        procedura = situazione.startswith("dentro")
        vera = TestRaccoltaSenzaPartiteNelCestino._senza_copie_delle_raccolte(monkeypatch)
        suoni.clear()

        copie, scatole, registro = _ripristina(principale, monkeypatch, copia, cestino_finto)

        assert _byte(raccolta) == prima
        assert _copie_della_raccolta() == {}
        assert _raccolte_nel_cestino(cestino_finto) == []
        assert [titolo for titolo, _testo in copie.finestre] == ["Conferma ripristino", "Raccolta delle partite non scritta", "Ripristino riuscito"]
        assert copie.finestre[1][1] == (
            f"La raccolta delle partite Turni - raccolta partite.pgn, nella cartella {os.path.dirname(raccolta)}, ha partite che il torneo Turni non ha: "
            "prima di sostituirla con la raccolta nuova Tornello doveva metterne una copia nella cartella backup, e la copia non è riuscita. "
            "Resta com'è, e la raccolta nuova non è stata scritta.\n"
            "I salvataggi del torneo Turni ci riprovano, anche dopo una chiusura di Tornello, e fino alla chiusura questo messaggio non si ripete. "
            "Se la raccolta di prima non ti serve più, spostala o cancellala tu, e la raccolta nuova del torneo Turni si scrive quando apri il torneo e lo salvi."
        )
        assert copie.proprietari == [("Raccolta delle partite non scritta", principale, wx.OK)]
        assert copie.suoni == ["ripristino"]
        assert suoni == ["errore"]
        assert scatole == []
        assert registro.caricati == []
        assert registro.fuoco == ([] if procedura else ["tree_ctrl"])
        _resta_il_torneo_di_prima(principale, situazione, alfa)

        monkeypatch.setattr(utils, "copia_di_sicurezza", vera)
        _la_scrive_il_salvataggio_del_ripristinato(principale, monkeypatch, ripristinato, raccolta, prima)

        assert list(_copie_della_raccolta().values()) == [prima]
        assert len(copie.finestre) == 3
        assert suoni == ["errore"]

    @pytest.mark.parametrize(
        "caso",
        [
            pytest.param("scrittura", id="la raccolta che non si scrive", marks=pytest.mark.skipif(sys.platform != "win32", reason="il blocco di un altro programma e' quello di Windows")),
            pytest.param("copia", id="la copia che non riesce"),
        ],
    )
    @pytest.mark.parametrize("strada", ["ripristino del torneo aperto", "salvataggio"])
    def test_nei_salvataggi_le_frasi_restano(self, principale, suoni, monkeypatch, cestino_finto, tmp_path, capsys, strada, caso):
        """10.19.66. Nei salvataggi i due messaggi Raccolta delle partite
        non scritta restano parola per parola quelli di prima, con le frasi
        che promettono il prossimo salvataggio, che li' e' vero. Due strade:
        il ripristino della copia del turno 2 di Turni aperto, che la
        finestra carica e salva; e il salvataggio di Turni riaperto dal suo
        file, che e' tornato com'era nella copia del turno 2, come dopo un
        ripristino fatto con un altro torneo aperto. Con il suono
        dell'errore, senza wx.MessageBox, e la finestra principale apre il
        messaggio. Tolto il blocco, il prossimo salvataggio scrive la
        raccolta del torneo, con le quattro partite del turno 1."""
        import shutil
        from types import SimpleNamespace

        import wx
        from test_comandi_delle_finestre import TestRaccoltaSenzaPartiteNelCestino, _descrizione_dell_errore

        import utils
        from reports import byte_della_raccolta_pgn

        ripristinato, copia, raccolta, prima = _torneo_in_corso_con_la_copia(principale, tmp_path, "programma", True)
        assert principale._e_il_torneo_aperto(ripristinato)
        if caso == "copia":
            vera = TestRaccoltaSenzaPartiteNelCestino._senza_copie_delle_raccolte(monkeypatch)
        suoni.clear()
        capsys.readouterr()
        sblocca = TestRaccoltaSenzaPartiteNelCestino._bloccata(raccolta, TestRaccoltaSenzaPartiteNelCestino.FILE_SHARE_READ) if caso == "scrittura" else (lambda: None)
        try:
            if strada == "salvataggio":
                shutil.copyfile(copia, ripristinato)
                copie = SimpleNamespace(finestre=[])
                _messaggi_della_finestra(monkeypatch, copie)
                scatole = []
                monkeypatch.setattr(wx, "MessageBox", lambda *a, **k: scatole.append(a))
                principale.load_tournament(ripristinato)
                principale._save_state()
                titoli = ["Raccolta delle partite non scritta"]
            else:
                copie, scatole, registro = _ripristina(principale, monkeypatch, copia, cestino_finto)
                assert registro.caricati == ["Tornello - Turni.json"]
                assert copie.suoni == ["ripristino"]
                titoli = ["Conferma ripristino", "Raccolta delle partite non scritta", "Ripristino riuscito"]
        finally:
            sblocca()

        assert _byte(raccolta) == prima
        assert [titolo for titolo, _testo in copie.finestre] == titoli
        (testo,) = [testo for titolo, testo in copie.finestre if titolo == "Raccolta delle partite non scritta"]
        if caso == "scrittura":
            (errore,) = TestRaccoltaSenzaPartiteNelCestino._errori_in_console(capsys)
            assert testo == (
                f"La raccolta delle partite Turni - raccolta partite.pgn, nella cartella {os.path.dirname(raccolta)}, non si è potuta scrivere: "
                f"{_descrizione_dell_errore(errore)}. Forse un altro programma la tiene aperta. Il torneo è salvato, e la raccolta si riscrive al prossimo salvataggio."
            )
            assert list(_copie_della_raccolta().values()) == [prima]
        else:
            assert testo == (
                f"La raccolta delle partite Turni - raccolta partite.pgn, nella cartella {os.path.dirname(raccolta)}, ha partite che il torneo Turni non ha: "
                "prima di sostituirla con la raccolta nuova Tornello doveva metterne una copia nella cartella backup, e la copia non è riuscita. "
                "Resta com'è, e la raccolta nuova non è stata scritta.\n"
                "I salvataggi ci riprovano, anche dopo una chiusura di Tornello, e fino alla chiusura questo messaggio non si ripete. "
                "Se la raccolta di prima non ti serve più, spostala o cancellala tu, e il prossimo salvataggio scriverà quella nuova."
            )
            assert _copie_della_raccolta() == {}
            monkeypatch.setattr(utils, "copia_di_sicurezza", vera)
        assert copie.proprietari == [("Raccolta delle partite non scritta", principale, wx.OK)]
        assert suoni == ["errore"]
        assert scatole == []
        assert principale._e_il_torneo_aperto(ripristinato)

        principale._save_state()

        with open(ripristinato, encoding="utf-8") as f:
            propria = byte_della_raccolta_pgn(json.load(f))
        assert propria.count(b"[Event ") == 4
        assert _byte(raccolta) == propria
        assert list(_copie_della_raccolta().values()) == [prima]
        assert len(copie.finestre) == len(titoli)
        assert suoni == ["errore"]


class TestIlTorneoRiaperto:
    @pytest.mark.parametrize("situazione", SITUAZIONI)
    def test_la_raccolta_torna_accanto_al_programma(self, principale, suoni, monkeypatch, cestino_finto, tmp_path, situazione):
        """Coppa_Prova, con le due partite del turno 1 in PGN, teneva la
        raccolta accanto al programma, e la finalizzazione l'ha portata in
        archivio; la copia di prima della finalizzazione lo riapre, e la
        cartella d'archivio va nel cestino con la raccolta. Dopo il
        ripristino la raccolta e' di nuovo accanto al programma, con le due
        partite, come la scrive la finestra aprendo il torneo e salvandolo."""
        from test_finalizzazione import _cartella_archivio, _copie, _finalizza, prepara_il_banco
        from test_finalizzazione import _scrivi as scrivi_il_torneo

        from reports import byte_della_raccolta_pgn, file_della_raccolta_pgn

        banco = prepara_il_banco(tmp_path, monkeypatch)
        _con_i_pgn(banco.torneo, {1})
        scrivi_il_torneo(banco.file_torneo, banco.torneo)
        principale.load_tournament(banco.file_torneo)
        principale._save_state()
        raccolta = file_della_raccolta_pgn(banco.torneo, banco.file_torneo)
        assert os.path.dirname(raccolta) == str(tmp_path)
        assert _finalizza(banco) is True
        assert not os.path.exists(raccolta)
        assert os.path.isfile(os.path.join(_cartella_archivio(), os.path.basename(raccolta)))
        copia = _copie(banco.backup, "pre_finalize_torneo")[0]
        _prepara_la_situazione(principale, monkeypatch, situazione)
        procedura = situazione.startswith("dentro")
        suoni.clear()

        copie, scatole, registro = _ripristina(principale, monkeypatch, copia, cestino_finto)

        with open(banco.file_torneo, encoding="utf-8") as f:
            propria = byte_della_raccolta_pgn(json.load(f))
        assert propria.count(b"[Event ") == 2
        assert _byte(raccolta) == propria
        assert cestino_finto.ricevuti == [os.path.abspath(_cartella_archivio())]
        assert _copie_della_raccolta() == {}
        assert [titolo for titolo, _testo in copie.finestre] == ["Conferma ripristino", "Ripristino riuscito"]
        assert copie.suoni == ["ripristino"]
        assert suoni == []
        assert scatole == []
        assert registro.caricati == []
        assert registro.fuoco == ([] if procedura else ["tree_ctrl"])

        _apri_e_salva(principale, monkeypatch, banco.file_torneo)

        assert _byte(raccolta) == propria
        assert _copie_della_raccolta() == {}
        assert cestino_finto.ricevuti == [os.path.abspath(_cartella_archivio())]
        assert len(copie.finestre) == 2


def test_la_raccolta_del_torneo_aperto_resta(principale, suoni, monkeypatch, cestino_finto, tmp_path):
    """Il torneo aperto e' un'altra edizione di Turni, dell'anno prima,
    con la data di inizio del 2025, presa da un'altra cartella, e tiene
    report e raccolta nella stessa cartella di lavoro del torneo
    ripristinato: le due raccolte sono lo stesso file. Dopo il ripristino
    della copia del turno 1, senza PGN, nel file della cartella del
    programma, la raccolta resta quella del torneo aperto, con le sue tre
    partite del turno 2, senza copie e senza cestino; e resta tale al
    salvataggio del torneo aperto."""
    from config import user_data_path
    from reports import file_della_raccolta_pgn

    lavoro = str(tmp_path / "lavoro")
    os.makedirs(lavoro)
    vecchio, _fotografie, _ritirato = turni._torneo_vero(abbinati=1, ultimo_completo=False)
    vero, _fotografie, _ritirato = turni._torneo_vero(abbinati=3, ultimo_completo=True)
    vecchio["custom_save_path"] = vero["custom_save_path"] = lavoro
    copia = user_data_path(os.path.join("backup", "2026", "11 Novembre", "Tornello - Turni_turno_1_20261108_100000.json"))
    os.makedirs(os.path.dirname(copia), exist_ok=True)
    with open(copia, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in vecchio.items() if k != "players_dict"}, f, default=sorted)
    ripristinato = turni._scrivi(vero)
    altrove = tmp_path / "altrove"
    altrove.mkdir()
    aperto = str(altrove / "Tornello - Turni.json")
    suo = _con_i_pgn(copy.deepcopy(vero), {2})
    suo["start_date"], suo["end_date"] = "2025-11-01", "2025-11-30"
    with open(aperto, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in suo.items() if k != "players_dict"}, f, default=sorted)
    principale.load_tournament(aperto)
    principale._save_state()
    raccolta = file_della_raccolta_pgn(vero, ripristinato)
    assert raccolta == file_della_raccolta_pgn(suo, aperto)
    prima = _byte(raccolta)
    assert prima.count(b"[Event ") == 3
    suoni.clear()

    copie, scatole, registro = _ripristina(principale, monkeypatch, copia, cestino_finto)

    assert _byte(raccolta) == prima
    assert _raccolte_nel_cestino(cestino_finto) == []
    assert os.path.abspath(raccolta) not in cestino_finto.tentativi
    assert _copie_della_raccolta() == {}
    assert [titolo for titolo, _testo in copie.finestre] == ["Conferma ripristino", "Ripristino riuscito"]
    assert copie.suoni == ["ripristino"]
    assert suoni == []
    assert scatole == []
    assert registro.fuoco == ["tree_ctrl"]
    assert principale._e_il_torneo_aperto(aperto)
    with open(ripristinato, encoding="utf-8") as f:
        assert len(json.load(f)["rounds"]) == 1
    with open(aperto, encoding="utf-8") as f:
        assert json.load(f)["start_date"] == "2025-11-01"

    principale._save_state()

    assert _byte(raccolta) == prima
    assert len(copie.finestre) == 2


def test_la_raccolta_di_un_altra_edizione_aperta_da_un_altra_cartella_resta(principale, suoni, monkeypatch, cestino_finto, tmp_path):
    """Correzione della 10.19.58. Il torneo aperto e' un'altra edizione di
    Turni, del 2025, con le partite del turno 2 in PGN, presa da un'altra
    cartella e senza una cartella di lavoro: la sua raccolta sta accanto al
    suo file, e non e' quella del torneo ripristinato, che sta accanto al
    programma. Dopo il ripristino della copia del turno 1, senza PGN, la
    raccolta del torneo ripristinato va nel cestino, intera, come con Alfa
    aperta, e quella dell'altra edizione resta byte per byte, anche al
    salvataggio del torneo aperto: il ripristino scrive la raccolta del file
    ripristinato, non di quello aperto, e lascia stare soltanto la raccolta
    che e' lo stesso file di quella del torneo aperto, non quella di un
    torneo con lo stesso nome."""
    from config import user_data_path
    from reports import file_della_raccolta_pgn

    assert user_data_path("").startswith(str(tmp_path))
    ripristinato, copia, raccolta, prima = _torneo_in_corso_con_la_copia(principale, tmp_path, "programma", False)
    with open(ripristinato, encoding="utf-8") as f:
        vero = json.load(f)
    altrove = tmp_path / "altrove"
    altrove.mkdir()
    aperto = str(altrove / "Tornello - Turni.json")
    suo = copy.deepcopy(vero)
    for turno in suo["rounds"]:
        for partita in turno["matches"]:
            partita.pop("pgn", None)
    _con_i_pgn(suo, {2})
    suo["start_date"], suo["end_date"] = "2025-11-01", "2025-11-30"
    with open(aperto, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in suo.items() if k != "players_dict"}, f, default=sorted)
    principale.load_tournament(aperto)
    assert principale._e_il_torneo_aperto(aperto)
    principale._save_state()
    raccolta_aperta = file_della_raccolta_pgn(suo, aperto)
    assert os.path.dirname(raccolta_aperta) == str(altrove)
    sua = _byte(raccolta_aperta)
    assert sua.count(b"[Event ") == 3
    assert _byte(raccolta) == prima
    suoni.clear()

    copie, scatole, registro = _ripristina(principale, monkeypatch, copia, cestino_finto)

    assert _byte(raccolta_aperta) == sua
    assert os.path.abspath(raccolta_aperta) not in cestino_finto.tentativi
    assert not os.path.exists(raccolta)
    assert _raccolte_nel_cestino(cestino_finto) == [os.path.abspath(raccolta)]
    (nel_cestino,) = [n for n in os.listdir(cestino_finto.cartella) if n.endswith(".pgn")]
    assert _byte(os.path.join(cestino_finto.cartella, nel_cestino)) == prima
    assert _copie_della_raccolta() == {}
    assert [titolo for titolo, _testo in copie.finestre] == ["Conferma ripristino", "Ripristino riuscito"]
    assert copie.suoni == ["ripristino"]
    assert suoni == []
    assert scatole == []
    assert registro.fuoco == ["tree_ctrl"]
    assert principale._e_il_torneo_aperto(aperto)
    with open(aperto, encoding="utf-8") as f:
        assert json.load(f)["start_date"] == "2025-11-01"

    principale._save_state()

    assert _byte(raccolta_aperta) == sua
    assert not os.path.exists(raccolta)
    assert len(copie.finestre) == 2
    assert suoni == []


class TestLaRaccoltaDiUnAltraEdizione:
    @pytest.mark.parametrize("copia_con_pgn", [True, False], ids=["copia del turno 2 con i PGN del turno 1", "copia del turno 1 senza PGN"])
    @pytest.mark.parametrize("situazione", SITUAZIONI)
    def test_la_raccolta_dell_edizione_archiviata_resta(self, principale, suoni, monkeypatch, cestino_finto, tmp_path, situazione, copia_con_pgn):
        """Correzione della 10.19.58 (decisione di Gabriele dell'8 novembre
        2026: mai toccare la raccolta di un'altra edizione con lo stesso
        nome). Turni del 2026, nato in console, non ha mai scritto la sua
        raccolta, e tiene i report in una cartella di lavoro. L'edizione del
        2025, conclusa e archiviata, con le partite del turno 2 in PGN, ha
        lasciato la sua raccolta in quella cartella, al posto di quella di
        Turni del 2026, e una copia identica nella sua cartella d'archivio.
        Dopo il ripristino di una copia di Turni del 2026, che la finestra
        non carica, la raccolta dell'edizione del 2025 resta com'e', senza
        cestino, senza copie e senza messaggi. Nella prima stesura della
        10.19.58 la guardia la mandava subito nel cestino, con il messaggio
        Raccolta delle partite di un altro torneo. La mette in salvo, come
        prima del ripristino, il primo salvataggio di Turni del 2026 aperto
        nella finestra: nel cestino, con la copia nella cartella d'archivio
        che c'e' gia', e con quel messaggio."""
        import config
        from reports import byte_della_raccolta_pgn, file_della_raccolta_pgn

        assert config.user_data_path("").startswith(str(tmp_path))
        assert config.ARCHIVED_TOURNAMENTS_DIR.startswith(str(tmp_path))
        lavoro = str(tmp_path / "lavoro")
        os.makedirs(lavoro)
        if copia_con_pgn:
            vecchio, _fotografie, _ritirato = turni._torneo_vero(abbinati=2, ultimo_completo=False)
            _con_i_pgn(vecchio, {1})
        else:
            vecchio, _fotografie, _ritirato = turni._torneo_vero(abbinati=1, ultimo_completo=False)
        vero, _fotografie, _ritirato = turni._torneo_vero(abbinati=3, ultimo_completo=True)
        vecchio["custom_save_path"] = vero["custom_save_path"] = lavoro
        ripristinato = turni._scrivi(vero)
        copia = config.user_data_path(os.path.join("backup", "2026", "11 Novembre", "Tornello - Turni_turno_1_20261108_100000.json"))
        os.makedirs(os.path.dirname(copia), exist_ok=True)
        with open(copia, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in vecchio.items() if k != "players_dict"}, f, default=sorted)
        edizione = _con_i_pgn(copy.deepcopy(vero), {2})
        edizione["start_date"], edizione["end_date"] = "2025-11-01", "2025-11-30"
        edizione["concluded"] = True
        archivio = os.path.join(config.ARCHIVED_TOURNAMENTS_DIR, "2025", "11 Novembre", "Turni")
        os.makedirs(archivio)
        with open(os.path.join(archivio, "Tornello - Turni.json"), "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in edizione.items() if k != "players_dict"}, f, default=sorted)
        sua = byte_della_raccolta_pgn(edizione)
        assert sua.count(b"[Event ") == 3
        raccolta = file_della_raccolta_pgn(vero, ripristinato)
        assert os.path.dirname(raccolta) == lavoro
        in_archivio = os.path.join(archivio, os.path.basename(raccolta))
        for percorso in (raccolta, in_archivio):
            with open(percorso, "wb") as f:
                f.write(sua)
        _prepara_la_situazione(principale, monkeypatch, situazione)
        procedura = situazione.startswith("dentro")
        suoni.clear()

        copie, scatole, registro = _ripristina(principale, monkeypatch, copia, cestino_finto)

        with open(ripristinato, encoding="utf-8") as f:
            dati = json.load(f)
        assert len(dati["rounds"]) == (2 if copia_con_pgn else 1)
        propria = byte_della_raccolta_pgn(dati)
        assert _byte(raccolta) == sua
        assert _byte(in_archivio) == sua
        assert os.path.abspath(raccolta) not in cestino_finto.tentativi
        assert _raccolte_nel_cestino(cestino_finto) == []
        assert _copie_della_raccolta() == {}
        assert [titolo for titolo, _testo in copie.finestre] == ["Conferma ripristino", "Ripristino riuscito"]
        assert copie.suoni == ["ripristino"]
        assert suoni == []
        assert scatole == []
        assert registro.caricati == []
        assert registro.fuoco == ([] if procedura else ["tree_ctrl"])
        assert principale.creation_mode is procedura

        _apri_e_salva(principale, monkeypatch, ripristinato)

        assert _byte(in_archivio) == sua
        assert _raccolte_nel_cestino(cestino_finto) == [os.path.abspath(raccolta)]
        (nel_cestino,) = [n for n in os.listdir(cestino_finto.cartella) if n.endswith(".pgn")]
        assert _byte(os.path.join(cestino_finto.cartella, nel_cestino)) == sua
        if copia_con_pgn:
            assert propria.count(b"[Event ") == 4
            assert _byte(raccolta) == propria
        else:
            assert propria is None
            assert not os.path.exists(raccolta)
        assert _copie_della_raccolta() == {}
        assert [titolo for titolo, _testo in copie.finestre] == [
            "Conferma ripristino",
            "Ripristino riuscito",
            "Raccolta delle partite di un altro torneo",
        ]
        assert copie.finestre[2][1] == (
            f"Nella cartella {lavoro} c'era la raccolta delle partite Turni - raccolta partite.pgn del torneo Turni, "
            f"concluso e archiviato nella cartella {os.path.join('Closed Tournaments', '2025', '11 Novembre', 'Turni')}: "
            "il torneo Turni l'avrebbe sostituita con la sua raccolta, o cancellata.\n"
            "Una copia identica, riletta, adesso è nella cartella d'archivio di quel torneo, "
            f"e quella della cartella {lavoro} è andata nel cestino di Windows."
        )
        assert suoni == []
