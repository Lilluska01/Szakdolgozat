import logging
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from services.user_service import UserService
from services.access_service import AccessService
from services.session_service import SessionService
from nfc.reader import NFCReader

log = logging.getLogger(__name__)

class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Egyetemi NFC jelenlétkezelő')
        self.root.geometry('1050x680')
        self.root.minsize(820, 520)
        self.user_service = UserService()
        self.access_service = AccessService()
        self.session_service = SessionService()
        self.reader = NFCReader()
        self.admin_panel = None
        self._closing = False
        self._refresh_timer = None
        self._reader_events = queue.Queue()
        self._reader_message = 'NFC olvasó csatlakoztatása…'
        self._build_widgets()
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.after(50, self._drain_reader_events)
        self.reader_thread = threading.Thread(target=self.reader.start, args=(self._on_card, self._reader_error, self._reader_ready), daemon=True, name='nfc-reader')
        self.reader_thread.start()
        self.refresh_lists()

    def _build_widgets(self):
        header = ttk.Frame(self.root, padding=14)
        header.pack(fill='x')
        ttk.Label(header, text='Jelenléti áttekintő', font=('Segoe UI', 19, 'bold')).pack(side='left')
        self.status_label = ttk.Label(header, text='Olvasó csatlakoztatása…')
        self.status_label.pack(side='right')
        body = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        body.pack(fill='both', expand=True, padx=12, pady=8)
        left = ttk.Frame(body, padding=8); right = ttk.Frame(body, padding=8)
        body.add(left, weight=1); body.add(right, weight=1)
        ttk.Label(left, text='Éppen bent').pack(anchor='w')
        self.inside_table = ttk.Treeview(left, columns=('name', 'neptun', 'last_seen'), show='headings')
        for key, title, width in [('name','Név',190), ('neptun','Neptun',90), ('last_seen','Utolsó esemény',150)]:
            self.inside_table.heading(key, text=title); self.inside_table.column(key, width=width, anchor='w')
        self.inside_table.pack(fill='both', expand=True, pady=8)
        ttk.Label(right, text='Legutóbbi események').pack(anchor='w')
        self.log_table = ttk.Treeview(right, columns=('name','card','action','timestamp'), show='headings')
        for key, title, width in [('name','Név',150),('card','Kártya',130),('action','Művelet',85),('timestamp','Időpont',150)]:
            self.log_table.heading(key, text=title); self.log_table.column(key,width=width,anchor='w')
        self.log_table.pack(fill='both', expand=True, pady=8)
        footer = ttk.Frame(self.root, padding=10); footer.pack(fill='x')
        ttk.Button(footer, text='Felhasználók', command=self.open_admin).pack(side='left')
        ttk.Button(footer, text='Excel-riport', command=self.export_excel).pack(side='left', padx=8)
        ttk.Button(footer, text='Frissítés', command=self.refresh_lists).pack(side='right')

    def _on_card(self, card_id):
        self._reader_events.put(('card', card_id))

    def _reader_error(self, error):
        self._reader_events.put(('error', str(error)))

    def _reader_ready(self):
        self._reader_events.put(('ready', None))

    def _drain_reader_events(self):
        if self._closing:
            return
        while True:
            try:
                event, value = self._reader_events.get_nowait()
            except queue.Empty:
                break
            if event == 'card':
                self._process_card(value)
            elif event == 'error':
                self._reader_message = f'NFC olvasóhiba: {value}'
                self.status_label.config(text=self._reader_message)
            elif event == 'ready':
                self._reader_message = 'NFC olvasó csatlakoztatva'
                self.status_label.config(text=self._reader_message)
        self.root.after(50, self._drain_reader_events)

    def _process_card(self, card_id):
        if self._closing:
            return
        if self.admin_panel is not None:
            try:
                if self.admin_panel.win.winfo_exists() and self.admin_panel.handle_card(card_id):
                    return
            except tk.TclError:
                self.admin_panel = None
        try:
            attendance = self.session_service.record_active_nfc(card_id)
            result = self.access_service.record_scan(card_id)
            messages = {'ENTRY':'belépett', 'EXIT':'kilépett', 'UNKNOWN_CARD':'Ismeretlen kártya', 'DENIED':'A kártya le van tiltva', 'COOLDOWN':'Túl gyors ismételt érintés'}
            state = result.get('status', 'ERROR')
            attendance_messages={'PRESENT':'órai jelenlét rögzítve','LATE':'késés rögzítve','ALREADY_MARKED':'órai jelenlét már megvan','NOT_ENROLLED':'nincs felvéve erre az órára','AMBIGUOUS_SESSION':'több óra is aktív erre a kártyára'}
            attendance_text=attendance_messages.get(attendance.get('status'))
            suffix=f" · {attendance_text}" if attendance_text else ''
            self.status_label.config(text=f"{result.get('name', result.get('card_id', ''))} {messages.get(state, state)}{suffix}")
            if state in {'ENTRY','EXIT'}:
                self.refresh_lists()
        except Exception:
            log.exception('Kártya feldolgozási hiba')
            self.status_label.config(text='Adatbázis-hiba a kártya feldolgozásakor')

    def refresh_lists(self):
        if self._closing:
            return
        self._refresh_timer = None
        try:
            inside = self.access_service.get_currently_inside()
            logs = self.access_service.get_last_logs(20)
            self.inside_table.delete(*self.inside_table.get_children())
            self.log_table.delete(*self.log_table.get_children())
            for user in inside:
                self.inside_table.insert('', tk.END, values=(user.get('name'), user.get('neptun') or '', user.get('last_seen') or ''))
            for row in logs:
                self.log_table.insert('', tk.END, values=(row.get('name') or '', row.get('card_id'), row.get('action'), row.get('timestamp')))
            self.status_label.config(text=f'Adatbázis elérhető · bent: {len(inside)} · {self._reader_message}')
        except Exception as exc:
            self.status_label.config(text=f'Adatbázis nem elérhető: {exc}')
        self._refresh_timer = self.root.after(5000, self.refresh_lists)

    def open_admin(self):
        from gui.admin_panel import AdminPanel
        self.admin_panel = AdminPanel(self.root, self.reader)

    def export_excel(self):
        try:
            from reports.excel_export import ExcelExport
            path = ExcelExport().export()
            messagebox.showinfo('Riport', f'Az Excel-riport elkészült:\n{path}')
        except Exception as exc:
            messagebox.showerror('Riporthiba', str(exc))

    def close(self):
        self._closing = True
        if self._refresh_timer is not None:
            self.root.after_cancel(self._refresh_timer)
        self.reader.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
