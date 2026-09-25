"""Prove sull'archiviazione dei tornei conclusi."""


class TestCartellaDiLavoro:
    """I file di un torneo concluso vanno spostati in archivio. Restano al loro
    posto solo se l'arbitro ha scelto una cartella esterna. Da quando la
    procedura guidata propone la cartella dell'applicazione, il vecchio
    controllo sul solo custom_save_path lasciava sempre i report accanto al
    programma: e' il difetto visto sul campo il 2026-09-04."""

    def test_nessuna_cartella_significa_spostare(self):
        from ui import cartella_di_lavoro_esterna

        assert cartella_di_lavoro_esterna("") is False
        assert cartella_di_lavoro_esterna(None) is False

    def test_la_cartella_dell_applicazione_non_e_esterna(self, monkeypatch):
        import ui

        monkeypatch.setattr(ui, "user_data_path", lambda _p: r"C:\Tornello")

        assert ui.cartella_di_lavoro_esterna(r"C:\Tornello") is False
        assert ui.cartella_di_lavoro_esterna(r"C:\Tornello\\") is False

    def test_una_cartella_diversa_e_esterna(self, monkeypatch):
        import ui

        monkeypatch.setattr(ui, "user_data_path", lambda _p: r"C:\Tornello")

        assert ui.cartella_di_lavoro_esterna(r"C:\Tornei\Circolo") is True


class TestReportAccantoAlProgramma:
    """Senza una cartella scelta per il torneo i report vanno accanto al
    programma, non nella cartella da cui e' stato avviato. Fino alla 10.3.2
    il nome restava relativo: lanciando le prove dalla radice del progetto, le
    classifiche dei tornei di prova finivano proprio li'."""

    def test_la_classifica_va_accanto_al_programma(
        self, tmp_path, monkeypatch, sample_tournament_dict
    ):
        from reports import save_standings_text

        altrove = tmp_path / "altrove"
        altrove.mkdir()
        monkeypatch.chdir(altrove)
        torneo = dict(sample_tournament_dict)
        torneo.pop("custom_save_path", None)

        save_standings_text(torneo)

        classifiche = [p.name for p in tmp_path.glob("*Classifica.txt")]
        assert len(classifiche) == 1
        assert list(altrove.iterdir()) == []

    def test_la_cartella_scelta_resta_quella(self, tmp_path):
        import os

        from reports import _nella_cartella_dei_report

        scelta = tmp_path / "circolo"
        percorso = _nella_cartella_dei_report({"custom_save_path": str(scelta)}, "x.txt")

        assert percorso == os.path.join(str(scelta), "x.txt")
