import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import NAME, __version__
from .patcher import Patcher, PatchError

DEFAULTS = [
    Path('C:/Program Files (x86)/itch/apps/night-runners-private-alpha'),
    Path.home() / 'AppData/Roaming/itch/apps/night-runners-private-alpha',
    Path.cwd(),
]


class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        root.title('%s %s' % (NAME, __version__))
        root.geometry('640x420')
        root.minsize(520, 320)
        frame = ttk.Frame(root, padding=12)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=NAME, font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Applies the REDUX changes to a stock NIGHT-RUNNERS PRIVATE ALPHA 3.2.7 or 3.2.8.').pack(anchor='w', pady=(2, 10))
        row = ttk.Frame(frame)
        row.pack(fill='x')
        self.folder = tk.StringVar(value=next((str(p) for p in DEFAULTS if (p / 'GameAssembly.dll').exists()), ''))
        ttk.Entry(row, textvariable=self.folder).pack(side='left', fill='x', expand=True)
        ttk.Button(row, text='Browse...', command=self.browse).pack(side='left', padx=(6, 0))
        self.status = tk.StringVar(value='Select the game folder.')
        ttk.Label(frame, textvariable=self.status).pack(anchor='w', pady=(8, 4))
        self.text = tk.Text(frame, height=12, state='disabled', wrap='word')
        self.text.pack(fill='both', expand=True)
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=(10, 0))
        self.install_btn = ttk.Button(buttons, text='Install REDUX', command=lambda: self.start('install'))
        self.install_btn.pack(side='right')
        self.restore_btn = ttk.Button(buttons, text='Restore stock', command=lambda: self.start('restore'))
        self.restore_btn.pack(side='right', padx=(0, 6))
        self.folder.trace_add('write', lambda *_: self.refresh())
        self.refresh()
        root.after(100, self.pump)

    def browse(self):
        d = filedialog.askdirectory(title='NIGHT-RUNNERS PRIVATE ALPHA folder')
        if d:
            self.folder.set(d)

    def say(self, line):
        self.events.put(('log', line))

    def refresh(self):
        try:
            version, patched = Patcher(self.folder.get(), self.say).detect()
            self.status.set('NIGHT-RUNNERS %s, %s' % (version, 'REDUX installed' if patched else 'stock'))
            self.install_btn.state(['disabled'] if patched else ['!disabled'])
            self.restore_btn.state(['!disabled'] if patched else ['disabled'])
        except (PatchError, OSError) as e:
            self.status.set(str(e) if self.folder.get() else 'Select the game folder.')
            self.install_btn.state(['disabled'])
            self.restore_btn.state(['!disabled'] if (Path(self.folder.get()) / '_redux_backup').exists() else ['disabled'])

    def start(self, action):
        if action == 'install' and not messagebox.askyesno(NAME, 'Close the game, then press Yes to patch it. Original files are backed up to _redux_backup.'):
            return
        self.install_btn.state(['disabled'])
        self.restore_btn.state(['disabled'])
        threading.Thread(target=self.work, args=(action,), daemon=True).start()

    def work(self, action):
        try:
            p = Patcher(self.folder.get(), self.say)
            p.install() if action == 'install' else p.restore()
            self.events.put(('done', None))
        except Exception as e:
            self.events.put(('error', str(e)))

    def pump(self):
        while not self.events.empty():
            kind, value = self.events.get()
            if kind == 'log':
                self.text.configure(state='normal')
                self.text.insert('end', value + '\n')
                self.text.see('end')
                self.text.configure(state='disabled')
            elif kind == 'error':
                messagebox.showerror(NAME, value)
                self.refresh()
            else:
                self.refresh()
        self.root.after(100, self.pump)


def run():
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0
