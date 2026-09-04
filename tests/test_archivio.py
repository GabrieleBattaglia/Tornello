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
