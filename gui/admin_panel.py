import tkinter as tk
from tkinter import ttk, messagebox
from services.user_service import UserService

class AdminPanel:
    def __init__(self, root, reader):
        self.root, self.reader = root, reader
        self.user_service = UserService()
        self.selected_user_id = None
        self.waiting_for_card = False
        self._build()

    def _build(self):
        self.win = tk.Toplevel(self.root)
        self.win.title('Felhasználók kezelése')
        self.win.geometry('640x520')
        form = ttk.LabelFrame(self.win, text='Új felhasználó', padding=10)
        form.pack(fill='x', padx=12, pady=10)
        ttk.Label(form, text='Név').grid(row=0, column=0, sticky='w', padx=4, pady=4)
        self.name_entry = ttk.Entry(form, width=34); self.name_entry.grid(row=0, column=1, padx=4)
        ttk.Label(form, text='Neptun-kód').grid(row=1, column=0, sticky='w', padx=4, pady=4)
        self.neptun_entry = ttk.Entry(form, width=34); self.neptun_entry.grid(row=1, column=1, padx=4)
        ttk.Button(form, text='Létrehozás', command=self.create_user).grid(row=0, column=2, rowspan=2, padx=8)
        self.card_label = ttk.Label(self.win, text='Válassz felhasználót a kártya hozzárendeléséhez.')
        self.card_label.pack(anchor='w', padx=14, pady=4)
        self.listbox = tk.Listbox(self.win, font=('Segoe UI', 10), activestyle='dotbox')
        self.listbox.pack(fill='both', expand=True, padx=12, pady=8)
        self.listbox.bind('<<ListboxSelect>>', self.on_select)
        actions = ttk.Frame(self.win, padding=8); actions.pack(fill='x')
        ttk.Button(actions, text='Kártya hozzárendelése', command=self.start_card_assign).pack(side='left')
        ttk.Button(actions, text='Aktív állapot váltása', command=self.toggle_user).pack(side='left', padx=8)
        ttk.Button(actions, text='Törlés / kártya felszabadítása', command=self.delete_user).pack(side='left')
        ttk.Button(actions, text='Frissítés', command=self.refresh).pack(side='right')
        self.refresh()

    def refresh(self):
        self.listbox.delete(0, tk.END)
        try:
            self.users = self.user_service.get_all_users(include_admin=False,include_archived=False)
            for user in self.users:
                status = 'AKTÍV' if user['active'] else 'TILTOTT'
                card = user.get('card_id') or 'nincs kártya'
                self.listbox.insert(tk.END, f"{user['id']} · {user['name']} · {user.get('neptun') or '-'} · {card} · {status}")
        except Exception as exc:
            messagebox.showerror('Adatbázis-hiba', str(exc), parent=self.win)

    def create_user(self):
        try:
            self.user_service.create_user(self.name_entry.get(), self.neptun_entry.get())
            self.name_entry.delete(0, tk.END); self.neptun_entry.delete(0, tk.END)
            self.refresh()
        except Exception as exc:
            messagebox.showerror('Nem sikerült létrehozni', str(exc), parent=self.win)

    def on_select(self, _event):
        selected = self.listbox.curselection()
        if selected:
            self.selected_user_id = self.users[selected[0]]['id']

    def toggle_user(self):
        if not self.selected_user_id:
            return
        try:
            self.user_service.toggle_active(self.selected_user_id)
            self.refresh()
        except Exception as exc:
            messagebox.showerror('Műveleti hiba', str(exc), parent=self.win)

    def delete_user(self):
        if not self.selected_user_id:
            messagebox.showinfo('Válassz felhasználót', 'Előbb jelölj ki valakit a listában.', parent=self.win)
            return
        user=next((item for item in self.users if item['id']==self.selected_user_id),None)
        if not user:
            return
        if not messagebox.askyesno(
            'Felhasználó törlése',
            f"Archiválod ezt a felhasználót: {user['name']}? A hozzá tartozó kártya felszabadul, a jelenléti napló megmarad.",
            parent=self.win
        ):
            return
        try:
            result=self.user_service.delete_user(self.selected_user_id)
            self.waiting_for_card=False
            self.selected_user_id=None
            self.card_label.config(text='A kártyás felhasználó eltávolítva; a kártya újra hozzárendelhető.')
            self.refresh()
            if result.get('released_card'):
                messagebox.showinfo('Törlés kész',f"A kártya felszabadult: {result['released_card']}",parent=self.win)
        except Exception as exc:
            messagebox.showerror('Törlési hiba', str(exc), parent=self.win)

    def start_card_assign(self):
        if not self.selected_user_id:
            messagebox.showinfo('Válassz felhasználót', 'Előbb jelölj ki valakit a listában.', parent=self.win)
            return
        self.waiting_for_card = True
        self.card_label.config(text='Érintsd a hozzárendelendő kártyát az olvasóhoz…')

    def handle_card(self, card_id):
        if not self.waiting_for_card or not self.selected_user_id:
            return False
        try:
            self.user_service.assign_card(self.selected_user_id, card_id)
            self.waiting_for_card = False
            self.card_label.config(text=f'Kártya hozzárendelve: {card_id}')
            self.refresh()
            return True
        except Exception as exc:
            self.waiting_for_card = False
            messagebox.showerror('Kártyahiba', str(exc), parent=self.win)
            return True
