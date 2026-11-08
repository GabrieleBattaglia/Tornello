import os
import tempfile

from utils import resolve_and_verify_save_path


def test_resolve_and_verify_save_path_empty():
    path, warning = resolve_and_verify_save_path("", default_fallback="temp_default")
    assert path == "temp_default"
    assert warning is None


def test_resolve_and_verify_save_path_valid():
    with tempfile.TemporaryDirectory() as tmpdir:
        path, warning = resolve_and_verify_save_path(
            tmpdir, default_fallback="temp_default"
        )
        # should match the absolute path of tmpdir
        assert os.path.abspath(path) == os.path.abspath(tmpdir)
        assert warning is None


def test_resolve_and_verify_save_path_create_nonexistent():
    with tempfile.TemporaryDirectory() as tmpdir:
        target_path = os.path.join(tmpdir, "new_sub_dir")
        assert not os.path.exists(target_path)

        path, warning = resolve_and_verify_save_path(
            target_path, default_fallback="temp_default"
        )
        assert os.path.exists(target_path)
        assert os.path.abspath(path) == os.path.abspath(target_path)
        assert warning is not None
        assert "creata" in warning.lower() or "created" in warning.lower()


def _unita_che_non_esiste():
    """Una lettera di unita' che al momento della prova non c'e'. Fino al
    novembre 2026 la prova usava K:, che su una delle macchine di Gabriele
    esiste: si parte dalla Z e si scende, perche' le lettere alte sono le
    meno usate, e se ci sono tutte la prova non ha niente da verificare."""
    import string

    import pytest

    libere = [f"{lettera}:" for lettera in reversed(string.ascii_uppercase[3:]) if not os.path.exists(f"{lettera}:\\")]
    if not libere:
        pytest.skip("tutte le lettere di unita' dalla D alla Z sono in uso")
    return libere[0]


def test_resolve_and_verify_save_path_invalid_drive():
    # Un'unita' che non c'e', scelta al momento della prova.
    invalid_path = _unita_che_non_esiste() + "\\NonExistentDrive\\TornelloTestReports"

    path, warning = resolve_and_verify_save_path(
        invalid_path, default_fallback="temp_default"
    )
    assert path == "temp_default"
    assert warning is not None
    assert "non è disponibile" in warning.lower() or "not available" in warning.lower()


def test_delete_active_tournament_logic():
    # Setup files in a temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        # JSON file
        json_file = os.path.join(tmpdir, "Tornello - TestTournament.json")
        with open(json_file, "w", encoding="utf-8") as f:
            f.write('{"name": "TestTournament", "custom_save_path": "custom_dir"}')

        custom_dir = os.path.join(tmpdir, "custom_dir")
        os.makedirs(custom_dir)

        # Reports
        r1 = os.path.join(custom_dir, "Tornello - TestTournament - Classifica.txt")
        r2 = os.path.join(custom_dir, "Tornello - TestTournament - Turno corrente.txt")
        r3 = os.path.join(tmpdir, "Tornello - TestTournament - Calendario.ics")
        other_file = os.path.join(custom_dir, "Tornello - Other - Classifica.txt")

        for p in [r1, r2, r3, other_file]:
            with open(p, "w", encoding="utf-8") as f:
                f.write("content")

        # Now clean up using the same logic as delete_active_tournament
        import json

        with open(json_file, encoding="utf-8") as f_in:
            data = json.load(f_in)

        t_name = data.get("name")
        assert t_name == "TestTournament"

        # remove json
        os.remove(json_file)

        # get paths to clean
        paths_to_clean = [os.path.dirname(json_file)]
        custom_path = data.get("custom_save_path")
        if custom_path:
            resolved_path = os.path.join(tmpdir, custom_path)
            paths_to_clean.append(resolved_path)

        paths_to_clean = list(set([os.path.abspath(p) for p in paths_to_clean if p]))

        from tournament import sanitize_filename

        sanitized_name = sanitize_filename(t_name)
        prefix_to_match = f"Tornello - {sanitized_name}"

        for folder in paths_to_clean:
            if os.path.exists(folder):
                for f_name in os.listdir(folder):
                    if f_name.startswith(prefix_to_match):
                        f_path = os.path.join(folder, f_name)
                        if os.path.isfile(f_path):
                            os.remove(f_path)

        # Assertions
        assert not os.path.exists(json_file)
        assert not os.path.exists(r1)
        assert not os.path.exists(r2)
        assert not os.path.exists(r3)
        assert os.path.exists(other_file)  # Should not be deleted!


class TestCartellaScrivibile:
    """Il controllo dei permessi che Tornello fa all'avvio. Non basta che la
    cartella esista: in Programmi c'e' ma non si puo' scrivere, ed e' li' che
    la prova sul campo si fermava con un codice di errore."""

    def test_una_cartella_normale_e_scrivibile(self, tmp_path):
        from utils import cartella_scrivibile

        assert cartella_scrivibile(str(tmp_path)) is True

    def test_una_cartella_inesistente_non_lo_e(self, tmp_path):
        from utils import cartella_scrivibile

        assert cartella_scrivibile(str(tmp_path / "assente")) is False

    def test_un_percorso_vuoto_non_lo_e(self):
        from utils import cartella_scrivibile

        assert cartella_scrivibile("") is False
        assert cartella_scrivibile(None) is False

    def test_non_lascia_il_file_di_prova(self, tmp_path):
        from utils import cartella_scrivibile

        cartella_scrivibile(str(tmp_path))

        assert list(tmp_path.iterdir()) == []


class TestRitiratiNelRiavvolgimento:
    """Riavvolgendo un turno, il ritiro va annullato solo per chi era ancora in
    gioco in quel turno. Prima veniva azzerato per tutti: un giocatore ritirato
    al secondo turno tornava negli abbinamenti se l'arbitro riavvolgeva al
    settimo, e se ne accorgeva solo leggendo gli accoppiamenti. Rilievo B3."""

    def _giocatore(self, pid, turni):
        return {
            "id": pid,
            "first_name": pid,
            "last_name": pid,
            "points": float(len(turni)),
            "withdrawn": False,
            "results_history": [
                {
                    "round": turno,
                    "opponent_id": "ALTRO",
                    "color": "white",
                    "result": "1-0",
                    "score": 1.0,
                }
                for turno in turni
            ],
        }

    def _torneo(self, tmp_path, monkeypatch):
        import config

        monkeypatch.setattr(config, "user_data_path", lambda p: str(tmp_path / p))

        # Chi ha lasciato presto: ultima partita al turno 1, poi ritirato.
        presto = self._giocatore("PRESTO", [1])
        presto["withdrawn"] = True
        # Chi si ritira proprio nel turno che verra' annullato.
        adesso = self._giocatore("ADESSO", [1, 2, 3])
        adesso["withdrawn"] = True
        # Chi non si e' mai ritirato.
        attivo = self._giocatore("ATTIVO", [1, 2, 3])

        torneo = {
            "name": "Prova rollback",
            "current_round": 3,
            "total_rounds": 5,
            "players": [presto, adesso, attivo],
            "rounds": [
                {"round": numero, "matches": [{"id": numero, "round": numero}]}
                for numero in (1, 2, 3)
            ],
        }
        torneo["players_dict"] = {p["id"]: p for p in torneo["players"]}
        return torneo, presto, adesso, attivo

    def test_chi_si_era_ritirato_prima_resta_ritirato(self, tmp_path, monkeypatch):
        from tournament import rollback_to_previous_round

        torneo, presto, adesso, attivo = self._torneo(tmp_path, monkeypatch)

        assert rollback_to_previous_round(torneo) is True

        assert presto["withdrawn"] is True, "il ritiro del turno 1 non va annullato"
        assert adesso["withdrawn"] is False, (
            "chi giocava nel turno annullato torna in gioco"
        )
        assert attivo["withdrawn"] is False

    def test_l_ultimo_turno_nello_storico(self):
        from tournament import ultimo_turno_nello_storico

        assert ultimo_turno_nello_storico(self._giocatore("X", [1, 2, 7])) == 7
        assert ultimo_turno_nello_storico(self._giocatore("X", [])) == 0
        assert ultimo_turno_nello_storico(None) == 0


class TestDettagliDelTurnoToltoNelCestino:
    """Dalla 10.13.60 (issue 68) la Time Machine manda nel cestino di Windows
    il file Tornello - nome - Turno N Dettagli.txt del turno che toglie, se
    il turno era concluso e il file c'e'. Fino alla 10.13.59 il file restava
    nella cartella dei report, e descriveva un turno che non c'era piu'. Il
    turno che torna in corso tiene il suo, e gli altri file restano. Il
    cestino e' finto: annota i percorsi, e quelli da rifiutare restano dove
    sono, come su un disco senza cestino."""

    NOMI = ("Turno 2 Dettagli.txt", "Turno 3 Dettagli.txt", "Turno corrente.txt", "Classifica.txt")

    def _torneo(self, tmp_path, monkeypatch):
        """Tre turni conclusi, i report in una cartella scelta per il
        torneo, e i file dei report gia' scritti."""
        import config

        monkeypatch.setattr(config, "user_data_path", lambda p: str(tmp_path / p))
        cartella = tmp_path / "report"
        cartella.mkdir()
        torneo = {
            "name": "Coppa d'Autunno",
            "custom_save_path": str(cartella),
            "current_round": 3,
            "total_rounds": 5,
            "players": [TestRitiratiNelRiavvolgimento()._giocatore("ALFA", [1, 2, 3])],
            "rounds": [{"round": numero, "matches": [{"id": numero, "round": numero, "result": "1-0"}]} for numero in (1, 2, 3)],
        }
        torneo["players_dict"] = {p["id"]: p for p in torneo["players"]}
        for nome in self.NOMI:
            (cartella / f"Tornello - Coppa_dAutunno - {nome}").write_text("report", encoding="utf-8")
        return torneo, cartella

    def test_il_file_del_turno_tolto_va_nel_cestino(self, tmp_path, monkeypatch, cestino_finto):
        from tournament import rollback_to_previous_round

        torneo, cartella = self._torneo(tmp_path, monkeypatch)

        assert rollback_to_previous_round(torneo, cestino=cestino_finto) is True

        assert cestino_finto.tentativi == [str(cartella / "Tornello - Coppa_dAutunno - Turno 3 Dettagli.txt")]
        restano = sorted(p.name.removeprefix("Tornello - Coppa_dAutunno - ") for p in cartella.iterdir())
        assert restano == sorted(set(self.NOMI) - {"Turno 3 Dettagli.txt"})
        # Il secondo annullamento toglie il turno 2, con il suo file.
        assert rollback_to_previous_round(torneo, cestino=cestino_finto) is True
        assert cestino_finto.tentativi[1:] == [str(cartella / "Tornello - Coppa_dAutunno - Turno 2 Dettagli.txt")]

    def test_senza_il_file_il_cestino_non_si_chiama(self, tmp_path, monkeypatch, cestino_finto):
        """Il turno tolto di solito e' quello appena abbinato, ancora in
        corso, e il suo file non c'e'."""
        from tournament import rollback_to_previous_round

        torneo, cartella = self._torneo(tmp_path, monkeypatch)
        (cartella / "Tornello - Coppa_dAutunno - Turno 3 Dettagli.txt").unlink()

        assert rollback_to_previous_round(torneo, cestino=cestino_finto) is True

        assert cestino_finto.tentativi == []
        assert len(list(cartella.iterdir())) == len(self.NOMI) - 1

    def test_il_file_che_il_cestino_non_prende_resta(self, tmp_path, monkeypatch, capsys, cestino_finto):
        from tournament import rollback_to_previous_round

        torneo, cartella = self._torneo(tmp_path, monkeypatch)
        cestino_finto.prende = False

        assert rollback_to_previous_round(torneo, cestino=cestino_finto) is True

        dettagli = cartella / "Tornello - Coppa_dAutunno - Turno 3 Dettagli.txt"
        assert cestino_finto.tentativi == [str(dettagli)]
        assert dettagli.exists()
        assert len(torneo["rounds"]) == 2
        assert f"Il file {dettagli} del turno tolto non è andato nel cestino, e resta dov'è." in capsys.readouterr().out

    def test_senza_cestino_usa_quello_del_programma(self, tmp_path, monkeypatch, cestino_finto):
        from tournament import rollback_to_previous_round

        torneo, cartella = self._torneo(tmp_path, monkeypatch)

        assert rollback_to_previous_round(torneo) is True

        assert cestino_finto.tentativi == [str(cartella / "Tornello - Coppa_dAutunno - Turno 3 Dettagli.txt")]

    def test_il_nome_e_quello_che_scrive_la_conclusione_del_turno(self, tmp_path, monkeypatch):
        """Il file che la Time Machine cerca e' proprio quello che scrive
        append_completed_round_to_history_file: il nome si fa in un posto
        solo."""
        from reports import append_completed_round_to_history_file, file_dei_dettagli_del_turno

        torneo, cartella = self._torneo(tmp_path, monkeypatch)
        for nome in self.NOMI:
            (cartella / f"Tornello - Coppa_dAutunno - {nome}").unlink()
        torneo["players"] = []
        torneo["players_dict"] = {}

        append_completed_round_to_history_file(torneo, 3)

        assert [p.name for p in cartella.iterdir()] == ["Tornello - Coppa_dAutunno - Turno 3 Dettagli.txt"]
        assert file_dei_dettagli_del_turno(torneo, 3) == str(cartella / "Tornello - Coppa_dAutunno - Turno 3 Dettagli.txt")


class TestScritturaAtomica:
    """Il database dei giocatori e i tornei vengono scritti prima in un file
    temporaneo e poi sostituiti in un colpo solo. Scrivendo direttamente sul
    file definitivo, un arresto a meta' operazione lasciava il vecchio
    contenuto troncato e il nuovo incompleto. Rilievo C1."""

    def test_scrive_il_contenuto(self, tmp_path):
        import json

        from utils import scrivi_json_atomico

        percorso = tmp_path / "dati.json"

        assert scrivi_json_atomico(str(percorso), {"a": 1, "b": [2, 3]}) is True
        with open(percorso, encoding="utf-8") as f:
            assert json.load(f) == {"a": 1, "b": [2, 3]}

    def test_non_lascia_file_temporanei(self, tmp_path):
        from utils import scrivi_json_atomico

        scrivi_json_atomico(str(tmp_path / "dati.json"), {"a": 1})

        assert [f.name for f in tmp_path.iterdir()] == ["dati.json"]

    def test_un_errore_non_distrugge_il_file_esistente(self, tmp_path):
        import json

        import pytest

        from utils import scrivi_json_atomico

        percorso = tmp_path / "dati.json"
        percorso.write_text('{"prezioso": true}', encoding="utf-8")

        # Un insieme non e' serializzabile: la scrittura fallisce a meta'.
        with pytest.raises(TypeError):
            scrivi_json_atomico(str(percorso), {"rotto": {1, 2, 3}})

        with open(percorso, encoding="utf-8") as f:
            assert json.load(f) == {"prezioso": True}
        assert [f.name for f in tmp_path.iterdir()] == ["dati.json"]

    def test_crea_la_cartella_se_manca(self, tmp_path):
        from utils import scrivi_json_atomico

        percorso = tmp_path / "nuova" / "dati.json"

        assert scrivi_json_atomico(str(percorso), {"a": 1}) is True
        assert percorso.exists()


class TestFileDelTorneo:
    """Eliminazione e finalizzazione riconoscono i file di un torneo dal nome
    intero, non dal solo inizio. Fino alla 10.3.3 il torneo Autunneo si
    portava via i file di Autunneo2, e un torneo chiamato P il database."""

    def test_riconosce_json_report_e_riepilogo_sospeso(self):
        from utils import file_del_torneo

        assert file_del_torneo("Tornello - Autunneo.json", "Autunneo")
        assert file_del_torneo("Tornello - Autunneo - Classifica.txt", "Autunneo")
        assert file_del_torneo("Tornello - Autunneo - Turno 3 Dettagli.txt", "Autunneo")
        assert file_del_torneo("Tornello - Autunneo - Standings.txt", "Autunneo")
        assert file_del_torneo("Tornello - Autunneo_sospeso.txt", "Autunneo")

    def test_non_prende_i_file_di_un_altro_torneo(self):
        from utils import file_del_torneo

        assert not file_del_torneo("Tornello - Autunneo2.json", "Autunneo")
        assert not file_del_torneo("Tornello - Autunneo2 - Classifica.txt", "Autunneo")
        assert not file_del_torneo("Tornello - Autunneo_bis - Classifica.txt", "Autunneo")
        assert not file_del_torneo("Tornello - Autunneo2_sospeso.txt", "Autunneo")

    def test_non_prende_database_e_impostazioni(self):
        from utils import file_del_torneo

        assert not file_del_torneo("Tornello - Players_db.json", "P")
        assert not file_del_torneo("Tornello - Players_db.json", "Players")
        assert not file_del_torneo("Tornello - Players_DB.txt", "Players")
        assert not file_del_torneo("Tornello - Settings.json", "S")


# Un manuale in miniatura, con i titoli scritti come nel manuale vero e le
# righe che ai titoli somigliano senza esserlo: le voci degli elenchi
# numerati, anche tutte maiuscole fuori dalle parentesi, e un numero col
# punto in mezzo seguito da testo minuscolo.
MANUALE_DI_PROVA = "\n".join(
    [
        "1. PRIMO CAPITOLO",
        "Introduzione.",
        "",
        "1.1 LA PRIMA SEZIONE (Tasto F5)",
        "Testo della prima sezione.",
        "",
        "1.1.1 UNA SOTTOSEZIONE",
        "I criteri:",
        "1. Scontro Diretto",
        "4. ARO (Average Rating of Opponents)",
        "0.5 punti al bye, come dice il regolamento.",
        "- GT, giorno del torneo.",
        "",
        "",
        "1.2 LA SECONDA SEZIONE",
        "Testo della seconda.",
        "",
        "2. SECONDO CAPITOLO",
        "Fine.",
        "",
    ]
)


class TestSezioneDelManuale:
    """La sezione del manuale che il pie' di pagina mostra nell'area
    principale: dal suo titolo al titolo seguente, di qualunque livello.
    Issue 54."""

    def test_arriva_fino_al_titolo_seguente(self):
        from utils import sezione_del_manuale

        assert sezione_del_manuale(MANUALE_DI_PROVA, "1.1.1") == "\n".join(
            [
                "1.1.1 UNA SOTTOSEZIONE",
                "I criteri:",
                "1. Scontro Diretto",
                "4. ARO (Average Rating of Opponents)",
                "0.5 punti al bye, come dice il regolamento.",
                "- GT, giorno del torneo.",
            ]
        )

    def test_si_ferma_alla_sottosezione_e_al_capitolo(self):
        from utils import sezione_del_manuale

        assert sezione_del_manuale(MANUALE_DI_PROVA, "1.1") == (
            "1.1 LA PRIMA SEZIONE (Tasto F5)\nTesto della prima sezione."
        )
        assert sezione_del_manuale(MANUALE_DI_PROVA, "1.2") == (
            "1.2 LA SECONDA SEZIONE\nTesto della seconda."
        )
        assert sezione_del_manuale(MANUALE_DI_PROVA, "1") == "1. PRIMO CAPITOLO\nIntroduzione."
        assert sezione_del_manuale(MANUALE_DI_PROVA, "2") == "2. SECONDO CAPITOLO\nFine."

    def test_i_ritorni_a_capo_di_windows(self):
        from utils import sezione_del_manuale

        testo = MANUALE_DI_PROVA.replace("\n", "\r\n")
        assert sezione_del_manuale(testo, "1.2") == "1.2 LA SECONDA SEZIONE\nTesto della seconda."

    def test_sezione_che_non_c_e(self):
        from utils import sezione_del_manuale

        assert sezione_del_manuale(MANUALE_DI_PROVA, "1.3") is None
        assert sezione_del_manuale(MANUALE_DI_PROVA, "0.5") is None
        assert sezione_del_manuale(MANUALE_DI_PROVA, "4") is None
        assert sezione_del_manuale("", "2.3.1") is None

    def test_gli_acronimi_nel_manuale_vero(self):
        """La 2.3.1 di MANUALE.txt, letto in sola lettura: comincia dal suo
        titolo, spiega ogni sigla del pie' di pagina e finisce prima della
        2.4."""
        import re

        from stats import RIGHE_DEL_PIE_DI_PAGINA
        from utils import sezione_del_manuale

        radice = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        with open(os.path.join(radice, "MANUALE.txt"), encoding="utf-8") as f:
            sezione = sezione_del_manuale(f.read(), "2.3.1")

        assert sezione.startswith("2.3.1 GLI ACRONIMI DEL PIÈ DI PAGINA\n")
        sigle = [chiave.upper() for riga in RIGHE_DEL_PIE_DI_PAGINA for chiave in riga]
        assert len(sigle) == 16
        for sigla in sigle:
            assert re.search(rf"\b{sigla}\b", sezione), sigla
        assert "2.4 " not in sezione
        assert "2.3 LA BARRA" not in sezione
