import os
import sys
from datetime import datetime
import wx
import builtins
from gui.settings import apply_visual_settings
from gui.dialogs.accessible_msg_dialog import AccessibleMsgDialog
from gui.accessibility import set_accessibility_label
from utils import play_sound

_ = getattr(builtins, "_", lambda s: s)


def calculate_age(mtime, today):
    """Calcola la differenza in mesi e giorni tra mtime e today."""
    if today < mtime:
        return 0, 0
    try:
        from dateutil.relativedelta import relativedelta

        delta = relativedelta(today, mtime)
        months = delta.years * 12 + delta.months
        days = delta.days
        return months, days
    except Exception:
        # Fallback in caso dateutil non sia disponibile
        diff_days = (today - mtime).days
        months = diff_days // 30
        days = diff_days % 30
        return months, days


def delete_file_to_trash(path):
    """Manda il file specificato nel Cestino di sistema se possibile, altrimenti lo elimina direttamente."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR),
                    ("fFlags", ctypes.c_ushort),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID),
                    ("lpszProgressTitle", wintypes.LPCWSTR),
                ]

            FO_DELETE = 3
            FOF_ALLOWUNDO = 0x0040
            FOF_NOCONFIRMATION = 0x0010
            FOF_NOERRORUI = 0x0400
            FOF_SILENT = 0x0004

            path_abs = os.path.abspath(path)
            # La Shell API richiede una stringa con doppio carattere nullo di terminazione
            path_double_null = path_abs + "\0\0"

            fileop = SHFILEOPSTRUCTW()
            fileop.hwnd = None
            fileop.wFunc = FO_DELETE
            fileop.pFrom = path_double_null
            fileop.pTo = None
            fileop.fFlags = (
                FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT
            )
            fileop.fAnyOperationsAborted = False
            fileop.hNameMappings = None
            fileop.lpszProgressTitle = None

            result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(fileop))
            if result == 0:
                return True
        except Exception:
            pass

    # Fallback su send2trash se installato
    try:
        from send2trash import send2trash

        send2trash(path)
        return True
    except Exception:
        pass

    # Fallback finale su eliminazione diretta
    try:
        os.remove(path)
        return True
    except Exception:
        return False


class BackupCleanupDialog(wx.Dialog):
    """
    Finestra di dialogo per la pulizia dei backup.
    Mostra statistiche sui file presenti, file consigliati per l'eliminazione
    (> 18 mesi) e un elenco navigabile ed ordinato cronologicamente.
    """

    def __init__(self, parent, settings):
        title = _("Pulizia Backup")
        super().__init__(
            parent,
            title=title,
            size=(800, 550),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )

        self.settings = settings
        self.backup_dir = "backup"
        self.files_info = []
        self.old_files_info = []

        # Assicura che la directory di backup esista
        if not os.path.exists(self.backup_dir):
            try:
                os.makedirs(self.backup_dir)
            except OSError:
                pass

        self._init_ui()
        self.apply_theme()
        self.populate_list()

        self.Centre()

        # Sposta il focus iniziale sul controllo di testo per consentire allo screen reader di leggerlo
        wx.CallAfter(self.stats_text.SetFocus)

    def _init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # 1. Area Statistiche (TextCtrl multilinee, in sola lettura ed accessibile)
        self.stats_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=(-1, 100)
        )
        self.stats_text.SetName(_("Statistiche backup"))
        vbox.Add(self.stats_text, 0, wx.EXPAND | wx.ALL, 10)

        # 2. Etichetta sibling prima della lista per NVDA
        self.lbl_list = wx.StaticText(
            panel, label=_("Elenco file di backup (dal più vecchio al più recente):")
        )
        vbox.Add(self.lbl_list, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # 3. Lista dei file di backup
        self.list_ctrl = wx.ListCtrl(
            panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_HRULES | wx.LC_VRULES
        )
        self.list_ctrl.SetName(_("Elenco file di backup"))
        set_accessibility_label(self.list_ctrl, _("Elenco file di backup"))

        self.list_ctrl.InsertColumn(0, _("Nome file"), width=320)
        self.list_ctrl.InsertColumn(1, _("Data di modifica"), width=180)
        self.list_ctrl.InsertColumn(2, _("Età"), width=220)

        self.list_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_list_key_down)
        vbox.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # 4. Pulsanti d'azione
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.btn_delete_selected = wx.Button(panel, label=_("Elimina questo file"))
        self.btn_delete_old = wx.Button(
            panel, label=_("Elimina consigliati (>18 mesi)")
        )
        self.btn_empty_folder = wx.Button(panel, label=_("Svuota cartella backup"))
        self.btn_close = wx.Button(panel, wx.ID_CANCEL, label=_("Chiudi"))

        self.btn_delete_selected.Bind(wx.EVT_BUTTON, self.on_delete_selected)
        self.btn_delete_old.Bind(wx.EVT_BUTTON, self.on_delete_old)
        self.btn_empty_folder.Bind(wx.EVT_BUTTON, self.on_empty_folder)
        self.btn_close.Bind(wx.EVT_BUTTON, self.on_close)

        btn_sizer.Add(self.btn_delete_selected, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(self.btn_delete_old, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(self.btn_empty_folder, 1, wx.EXPAND | wx.RIGHT, 5)
        btn_sizer.Add(self.btn_close, 1, wx.EXPAND)

        vbox.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        panel.SetSizer(vbox)

    def apply_theme(self):
        """Applica le impostazioni visive del tema dell'applicazione."""
        apply_visual_settings(self, self.settings)
        apply_visual_settings(self.stats_text, self.settings)
        apply_visual_settings(self.lbl_list, self.settings)
        apply_visual_settings(self.list_ctrl, self.settings)
        apply_visual_settings(self.btn_delete_selected, self.settings)
        apply_visual_settings(self.btn_delete_old, self.settings)
        apply_visual_settings(self.btn_empty_folder, self.settings)
        apply_visual_settings(self.btn_close, self.settings)

    def load_backup_files(self):
        """Scansiona i file nella directory di backup e rileva quelli più vecchi di 18 mesi."""
        self.files_info = []
        self.old_files_info = []
        today = datetime.now()

        try:
            from dateutil.relativedelta import relativedelta

            limit_date = today - relativedelta(months=18)
        except ImportError:
            limit_date = today - datetime.timedelta(days=548)

        if os.path.exists(self.backup_dir):
            try:
                for filename in os.listdir(self.backup_dir):
                    filepath = os.path.join(self.backup_dir, filename)
                    if os.path.isfile(filepath):
                        stat = os.stat(filepath)
                        size_bytes = stat.st_size
                        mtime = datetime.fromtimestamp(stat.st_mtime)

                        f_info = {
                            "name": filename,
                            "path": filepath,
                            "size": size_bytes,
                            "mtime": mtime,
                        }
                        self.files_info.append(f_info)
                        if mtime < limit_date:
                            self.old_files_info.append(f_info)
            except Exception:
                pass

        # Ordina dal più vecchio al più recente (ascendente)
        self.files_info.sort(key=lambda x: x["mtime"])

    def populate_list(self):
        """Ricarica la lista e aggiorna il testo delle statistiche."""
        self.list_ctrl.DeleteAllItems()
        self.load_backup_files()

        today = datetime.now()
        total_files = len(self.files_info)
        total_size_mb = sum(f["size"] for f in self.files_info) / (1024 * 1024)
        old_files_count = len(self.old_files_info)
        old_size_mb = sum(f["size"] for f in self.old_files_info) / (1024 * 1024)

        stats_msg = _(
            "Statistiche Cartella Backup:\n"
            "- Totale file presenti: {tot_files} (Dimensione totale: {tot_size:.2f} MB)\n"
            "- Consigliati per l'eliminazione (> 18 mesi): {old_files} (Dimensione: {old_size:.2f} MB)\n"
        ).format(
            tot_files=total_files,
            tot_size=total_size_mb,
            old_files=old_files_count,
            old_size=old_size_mb,
        )
        self.stats_text.SetValue(stats_msg)

        for idx, f in enumerate(self.files_info):
            self.list_ctrl.InsertItem(idx, f["name"])

            mtime_str = f["mtime"].strftime("%Y-%m-%d %H:%M:%S")
            self.list_ctrl.SetItem(idx, 1, mtime_str)

            months, days = calculate_age(f["mtime"], today)
            age_str = _("{m} mesi, {d} giorni").format(m=months, d=days)
            self.list_ctrl.SetItem(idx, 2, age_str)

        # Re-imposta la selezione sul primo elemento se presente
        if total_files > 0:
            self.list_ctrl.SetItemState(
                0,
                wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
                wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
            )

    def on_delete_selected(self, event):
        """Elimina il file attualmente selezionato nella lista."""
        selected_idx = self.list_ctrl.GetNextItem(
            -1, wx.LIST_NEXT_ALL, wx.LIST_STATE_SELECTED
        )
        if selected_idx == -1:
            msg = _(
                "Nessun file selezionato. Seleziona un file dall'elenco per poterlo eliminare."
            )
            dlg = AccessibleMsgDialog(self, _("Nessuna Selezione"), msg)
            dlg.ShowModal()
            dlg.Destroy()
            return

        file_info = self.files_info[selected_idx]
        msg = _(
            "Sei sicuro di voler spostare nel cestino il file di backup '{name}'?"
        ).format(name=file_info["name"])
        dlg = AccessibleMsgDialog(
            self, _("Conferma Eliminazione"), msg, style=wx.YES_NO
        )
        if dlg.ShowModal() == wx.ID_YES:
            dlg.Destroy()
            if delete_file_to_trash(file_info["path"]):
                play_sound("cancellato")
                self.populate_list()
            else:
                err_msg = _("Impossibile eliminare il file '{name}'.").format(
                    name=file_info["name"]
                )
                err_dlg = AccessibleMsgDialog(self, _("Errore"), err_msg)
                err_dlg.ShowModal()
                err_dlg.Destroy()
        else:
            dlg.Destroy()

    def on_delete_old(self, event):
        """Elimina tutti i file più vecchi di 18 mesi."""
        if not self.old_files_info:
            msg = _("Non ci sono file di backup più vecchi di 18 mesi da eliminare.")
            dlg = AccessibleMsgDialog(self, _("Nessun File Trovato"), msg)
            dlg.ShowModal()
            dlg.Destroy()
            return

        msg = _(
            "Sei sicuro di voler spostare nel cestino tutti i {count} file di backup più vecchi di 18 mesi?"
        ).format(count=len(self.old_files_info))
        dlg = AccessibleMsgDialog(
            self, _("Conferma Eliminazione Consigliata"), msg, style=wx.YES_NO
        )
        if dlg.ShowModal() == wx.ID_YES:
            dlg.Destroy()
            failed = []
            for f in self.old_files_info:
                if not delete_file_to_trash(f["path"]):
                    failed.append(f["name"])
            play_sound("cancellato")
            self.populate_list()
            if failed:
                err_msg = _("Alcuni file non sono stati eliminati:\n{files}").format(
                    files=", ".join(failed)
                )
                err_dlg = AccessibleMsgDialog(self, _("Errore Parziale"), err_msg)
                err_dlg.ShowModal()
                err_dlg.Destroy()
        else:
            dlg.Destroy()

    def on_empty_folder(self, event):
        """Elimina tutti i file presenti nella cartella di backup."""
        if not self.files_info:
            msg = _("La cartella di backup è già vuota.")
            dlg = AccessibleMsgDialog(self, _("Cartella Vuota"), msg)
            dlg.ShowModal()
            dlg.Destroy()
            return

        msg = _(
            "ATTENZIONE: Sei sicuro di voler spostare nel cestino TUTTI i file di backup contenuti nella cartella?"
        )
        dlg = AccessibleMsgDialog(
            self, _("Conferma Svuotamento Cartella"), msg, style=wx.YES_NO
        )
        if dlg.ShowModal() == wx.ID_YES:
            dlg.Destroy()
            failed = []
            for f in self.files_info:
                if not delete_file_to_trash(f["path"]):
                    failed.append(f["name"])
            play_sound("cancellato")
            self.populate_list()
            if failed:
                err_msg = _("Alcuni file non sono stati eliminati:\n{files}").format(
                    files=", ".join(failed)
                )
                err_dlg = AccessibleMsgDialog(self, _("Errore Parziale"), err_msg)
                err_dlg.ShowModal()
                err_dlg.Destroy()
        else:
            dlg.Destroy()

    def on_close(self, event):
        """Chiude la finestra di dialogo."""
        play_sound("conferma")
        self.EndModal(wx.ID_CANCEL)

    def on_list_key_down(self, event):
        """Intercetta il tasto Canc/Delete per eliminare il file selezionato."""
        key_code = event.GetKeyCode()
        if key_code in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            self.on_delete_selected(None)
        else:
            event.Skip()
