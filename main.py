import tkinter as tk
from tkinter import messagebox
import json, os, sys, random
from PIL import Image, ImageTk
import webbrowser
from datetime import datetime

# --- Update checking imports ---
import threading
import urllib.request
import urllib.error

APP_NAME = "Dead by Daylight Perk Shuffle"
APP_VERSION = "1.0.0"  # keep numeric for comparisons
GITHUB_REPO = "starrstrukk/Dead-by-Daylight-Perk-Shuffle"  # <-- change later to: "starrstrukk/dbd-perk-shuffle"

WINDOW_W = 700
WINDOW_H = 700
HISTORY_MAX = 25
DRAFT_CHOICES = 3

def resource_path(path: str) -> str:
    """Get absolute path to resource, works for dev + PyInstaller."""
    try:
        base = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base = os.path.abspath(".")
    return os.path.join(base, path)

# ✅ Installer-safe settings location (AppData)
def user_data_dir() -> str:
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path

SETTINGS_FILE = os.path.join(user_data_dir(), "settings.json")

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            s = json.load(f)
    else:
        s = {}
    s.setdefault("theme", "Black")
    s.setdefault("owned_perks", [])
    s.setdefault("history", [])
    s.setdefault("always_on_top", False)
    return s

def save_settings():
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

settings = load_settings()

THEMES = {
    "Neon Blue":   {"bg": "#0b0b0f", "fg": "#ffffff", "accent": "#00e5ff"},
    "Neon Pink":   {"bg": "#0b0b0f", "fg": "#ffffff", "accent": "#ff4fd8"},
    "Neon Green":  {"bg": "#0b0b0f", "fg": "#ffffff", "accent": "#34ff7a"},
    "Neon Yellow": {"bg": "#0b0b0f", "fg": "#ffffff", "accent": "#ffe84a"},

    "Black":  {"bg": "#101010", "fg": "#ffffff", "accent": "#6b6b6b"},
    "White":  {"bg": "#f5f5f5", "fg": "#000000", "accent": "#444444"},
    "Blue":   {"bg": "#0b1020", "fg": "#ffffff", "accent": "#3aa0ff"},
    "Red":    {"bg": "#1b0b0b", "fg": "#ffffff", "accent": "#ff3a3a"},
    "Purple": {"bg": "#120b1b", "fg": "#ffffff", "accent": "#b26bff"},
    "Green":  {"bg": "#071a10", "fg": "#ffffff", "accent": "#34e27a"},
}

def current_theme():
    return THEMES.get(settings["theme"], THEMES["Black"])

def is_neon_theme() -> bool:
    return settings.get("theme", "").startswith("Neon")

def rounded_rect(c, x1, y1, x2, y2, r, **kw):
    pts = [
        x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
        x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
        x1, y2, x1, y2-r, x1, y1+r, x1, y1
    ]
    return c.create_polygon(pts, smooth=True, **kw)

class RoundedButton(tk.Frame):
    def __init__(self, parent, text, command, w=220, h=40):
        super().__init__(parent, bd=0)
        self.text = text
        self.command = command
        self.w, self.h = w, h
        self.c = tk.Canvas(self, width=w, height=h, bd=0, highlightthickness=0)
        self.c.pack()
        self.c.bind("<Button-1>", lambda e: self.command())
        self.c.bind("<Enter>", lambda e: self.draw(True))
        self.c.bind("<Leave>", lambda e: self.draw(False))
        self.draw(False)

    def draw(self, hover):
        t = current_theme()
        neon = is_neon_theme()

        bg = t["bg"]
        accent = t["accent"]
        fg = t["fg"]

        self.c.configure(bg=bg)
        self.c.delete("all")

        if neon:
            fill = bg
            outline_w = 3 if hover else 2
            text_color = accent if hover else fg

            rounded_rect(self.c, 2, 2, self.w - 2, self.h - 2, 14,
                        fill=fill, outline=accent, width=outline_w)

            if hover:
                rounded_rect(self.c, 6, 6, self.w - 6, self.h - 6, 12,
                            fill="", outline=accent, width=1)

            self.c.create_text(self.w // 2, self.h // 2,
                               text=self.text, fill=text_color,
                               font=("Arial", 11, "bold"))
        else:
            fill = accent if hover else bg
            text_color = "#000000" if hover else fg

            rounded_rect(self.c, 2, 2, self.w - 2, self.h - 2, 14,
                        fill=fill, outline=accent, width=2)

            self.c.create_text(self.w // 2, self.h // 2,
                               text=self.text, fill=text_color,
                               font=("Arial", 11, "bold"))

buttons = []
def make_button(parent, text, cmd, w=220):
    b = RoundedButton(parent, text, cmd, w=w)
    buttons.append(b)
    return b

# ---------- Update checker (GitHub Releases) ----------
def parse_version(v: str):
    v = (v or "").strip().lower()
    if v.startswith("v"):
        v = v[1:]
    parts = v.split(".")
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])

def fetch_latest_github_release(repo: str):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": f"{APP_NAME} update-check"}
    )
    with urllib.request.urlopen(req, timeout=6) as resp:
        data = resp.read().decode("utf-8")
    return json.loads(data)

def check_for_updates(show_up_to_date_popup: bool = False):
    def worker():
        try:
            # If user hasn't set a real repo yet, don't spam requests.
            if "/" not in (GITHUB_REPO or "") or "yourusername" in GITHUB_REPO:
                if show_up_to_date_popup:
                    root.after(0, lambda: messagebox.showinfo("Updates",
                        "Update checking isn't configured yet.\n\nSet GITHUB_REPO to your GitHub repo (username/repo)."))
                return

            info = fetch_latest_github_release(GITHUB_REPO)
            tag = (info.get("tag_name") or "").strip()      # e.g. "v1.0.1"
            html_url = (info.get("html_url") or "").strip() # release page

            if not tag or not html_url:
                return

            latest = parse_version(tag)
            current = parse_version(APP_VERSION)

            def on_ui():
                if latest > current:
                    if messagebox.askyesno(
                        "Update available",
                        f"A new version is available!\n\n"
                        f"Current: {APP_VERSION}\nLatest: {tag}\n\n"
                        f"Open download page?"
                    ):
                        webbrowser.open(html_url)
                else:
                    if show_up_to_date_popup:
                        messagebox.showinfo("Up to date", f"You're on the latest version ({APP_VERSION}).")

            root.after(0, on_ui)

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            if show_up_to_date_popup:
                root.after(0, lambda: messagebox.showwarning(
                    "Update check failed",
                    "Couldn't check for updates right now (no internet or GitHub blocked)."
                ))
        except Exception:
            if show_up_to_date_popup:
                root.after(0, lambda: messagebox.showwarning(
                    "Update check failed",
                    "Couldn't check for updates right now."
                ))

    threading.Thread(target=worker, daemon=True).start()

# ---------- Data ----------
try:
    with open(resource_path("perks.json"), "r", encoding="utf-8") as f:
        perks = json.load(f)
except FileNotFoundError:
    messagebox.showerror("Missing file", "perks.json was not found. Make sure it's next to the app or bundled correctly.")
    raise

# ---------- App ----------
root = tk.Tk()

# Always on top option
root.attributes("-topmost", bool(settings.get("always_on_top", False)))

root.title(f"{APP_NAME} v{APP_VERSION}")
# ---- Window icon (best compatibility) ----
try:
    png = ImageTk.PhotoImage(Image.open(resource_path("app_icon.png")))
    root.iconphoto(True, png)
    root._icon_ref = png  # keep ref so it doesn't get garbage-collected
except Exception:
    ico_path = resource_path("app_icon.ico")
    try:
        root.iconbitmap(ico_path)
    except Exception:
        try:
            root.iconbitmap(default=ico_path)
        except Exception:
            pass

root.geometry(f"{WINDOW_W}x{WINDOW_H}")
root.resizable(False, False)
root.minsize(700, 700)
root.maxsize(700, 700)

home = tk.Frame(root)
selector = tk.Frame(root)
history = tk.Frame(root)
draft = tk.Frame(root)

frames, labels, icons = [], [], []

checks = []
selector_check_rows = []

draft_option_buttons = []
draft_option_imgs = []
draft_state = {"slot": 0, "chosen": [], "remaining": [], "current_choices": []}

# ---------- Helpers ----------
def owned_pool():
    pool = []
    for p in perks:
        if p["name"] in settings["owned_perks"]:
            if os.path.exists(resource_path(p["icon"])):
                pool.append(p)
    return pool

def set_build_on_home(chosen_perks):
    for i, p in enumerate(chosen_perks):
        labels[i].config(text=p["name"])
        img = Image.open(resource_path(p["icon"])).resize((64, 64))
        tkimg = ImageTk.PhotoImage(img)
        icons[i].config(image=tkimg)
        icons[i].image = tkimg

def format_history_entry(entry):
    prefix = entry.get("type", "Shuffle")
    return f'{entry["time"]}  —  {prefix}: ' + " | ".join(entry["perks"])

def refresh_history_listbox():
    history_listbox.delete(0, tk.END)
    for entry in settings.get("history", []):
        history_listbox.insert(tk.END, format_history_entry(entry))

def add_history_entry(perk_names, entry_type="Shuffle"):
    stamp = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    entry = {"time": stamp, "perks": perk_names, "type": entry_type}
    settings["history"].insert(0, entry)
    settings["history"] = settings["history"][:HISTORY_MAX]
    save_settings()
    refresh_history_listbox()

def set_theme(name):
    if name not in THEMES:
        return
    settings["theme"] = name
    save_settings()
    apply_theme()

def toggle_always_on_top():
    settings["always_on_top"] = not bool(settings.get("always_on_top", False))
    save_settings()
    root.attributes("-topmost", bool(settings["always_on_top"]))
    apply_theme()

# ---------- Navigation ----------
def show_home():
    selector.pack_forget()
    history.pack_forget()
    draft.pack_forget()
    home.pack(fill="both", expand=True)
    root.unbind_all("<MouseWheel>")

def _on_mousewheel(event):
    try:
        selector_canvas.yview_scroll(-1 * (event.delta // 120), "units")
    except Exception:
        pass

def show_selector():
    for k, v in vars_map.items():
        v.set(k in settings["owned_perks"])
    home.pack_forget()
    history.pack_forget()
    draft.pack_forget()
    selector.pack(fill="both", expand=True)
    root.bind_all("<MouseWheel>", _on_mousewheel)
    refresh_selector_filter()

def show_history():
    home.pack_forget()
    selector.pack_forget()
    draft.pack_forget()
    history.pack(fill="both", expand=True)
    root.unbind_all("<MouseWheel>")
    refresh_history_listbox()

def show_draft():
    home.pack_forget()
    selector.pack_forget()
    history.pack_forget()
    draft.pack(fill="both", expand=True)
    root.unbind_all("<MouseWheel>")
    apply_theme()

# ---------- Modes ----------
def shuffle_perks():
    pool = owned_pool()
    if len(pool) < 4:
        messagebox.showwarning("Not enough perks", "Select at least 4 owned perks first.")
        return
    chosen = random.sample(pool, 4)
    set_build_on_home(chosen)
    add_history_entry([p["name"] for p in chosen], entry_type="Shuffle")

def start_draft():
    pool = owned_pool()
    if len(pool) < 4:
        messagebox.showwarning("Not enough perks", "Select at least 4 owned perks first.")
        return
    draft_state["slot"] = 0
    draft_state["chosen"] = []
    draft_state["remaining"] = pool[:]
    draft_state["current_choices"] = []
    show_draft()
    next_draft_round()

def next_draft_round():
    slot = draft_state["slot"]
    if slot >= 4:
        finalize_draft()
        return

    remaining = draft_state["remaining"]
    if not remaining:
        finalize_draft()
        return

    k = min(DRAFT_CHOICES, len(remaining))
    choices = random.sample(remaining, k)
    draft_state["current_choices"] = choices

    draft_progress_lbl.config(text=f"Pick for Slot {slot + 1} of 4")
    draft_selected_lbl.config(text="Chosen: " + (" | ".join([p["name"] for p in draft_state["chosen"]]) or "None yet"))

    for btn in draft_option_buttons:
        btn.grid_forget()
    draft_option_buttons.clear()
    draft_option_imgs.clear()

    for idx, p in enumerate(choices):
        img = Image.open(resource_path(p["icon"])).resize((72, 72))
        tkimg = ImageTk.PhotoImage(img)
        draft_option_imgs.append(tkimg)

        b = tk.Button(
            draft_options_frame,
            text=p["name"],
            image=tkimg,
            compound="top",
            command=lambda perk=p: choose_draft_perk(perk),
            padx=10,
            pady=10,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            wraplength=150,
            justify="center"
        )
        draft_option_buttons.append(b)

        r = idx // 3
        c = idx % 3
        b.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")

    for c in range(3):
        draft_options_frame.grid_columnconfigure(c, weight=1)

    apply_theme()

def choose_draft_perk(perk):
    draft_state["chosen"].append(perk)
    draft_state["remaining"] = [p for p in draft_state["remaining"] if p["name"] != perk["name"]]
    draft_state["slot"] += 1
    next_draft_round()

def finalize_draft():
    chosen = draft_state["chosen"]
    if len(chosen) >= 4:
        chosen = chosen[:4]
        set_build_on_home(chosen)
        add_history_entry([p["name"] for p in chosen], entry_type="Draft")
    else:
        messagebox.showinfo("Draft ended", "Not enough perks were available to complete 4 slots.")
    show_home()

def clear_draft():
    draft_state["slot"] = 0
    draft_state["chosen"] = []
    draft_state["remaining"] = []
    draft_state["current_choices"] = []
    for btn in draft_option_buttons:
        btn.grid_forget()
    draft_option_buttons.clear()
    draft_option_imgs.clear()
    draft_progress_lbl.config(text="Pick for Slot 1 of 4")
    draft_selected_lbl.config(text="Chosen: None yet")

# ---------- HOME UI ----------
title = tk.Label(home, text=f"{APP_NAME} v{APP_VERSION}", font=("Arial", 14, "bold"))
title.pack(pady=10)

for _ in range(4):
    f = tk.Frame(home)
    f.pack(pady=6)
    i = tk.Label(f)
    i.pack(side="left", padx=6)
    l = tk.Label(f, font=("Arial", 12))
    l.pack(side="left")
    frames.append(f)
    icons.append(i)
    labels.append(l)

theme_var = tk.StringVar(value=settings["theme"])
tk.OptionMenu(home, theme_var, *THEMES.keys()).pack(pady=6)
theme_var.trace_add("write", lambda *_: set_theme(theme_var.get()))

make_button(home, "Shuffle Perks", shuffle_perks, w=240).pack(pady=6)
make_button(home, "Draft Mode", start_draft, w=240).pack(pady=4)
make_button(home, "Select Owned Perks", show_selector, w=240).pack(pady=4)
make_button(home, "Shuffle History", show_history, w=240).pack(pady=4)

# ✅ update button
make_button(home, "Check for Updates", lambda: check_for_updates(True), w=240).pack(pady=4)

always_var = tk.BooleanVar(value=bool(settings.get("always_on_top", False)))
always_chk = tk.Checkbutton(home, text="Always on top", variable=always_var, command=toggle_always_on_top)
always_chk.pack(pady=(6, 0))

credit = tk.Label(
    home,
    text="Created for the fog by u/blah2k03 • GitHub @starrstrukk",
    fg="gray",
    cursor="hand2"
)
credit.pack(side="bottom", pady=10)
credit.bind("<Button-1>", lambda e: webbrowser.open("https://www.reddit.com/u/blah2k03"))

home.pack(fill="both", expand=True)

# ---------- SELECTOR UI ----------
for w in selector.winfo_children():
    w.destroy()

selector.grid_rowconfigure(2, weight=1)
selector.grid_columnconfigure(0, weight=1)

selector_top = tk.Frame(selector)
selector_top.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 6))
tk.Label(selector_top, text="Select Owned Perks", font=("Arial", 13, "bold")).pack(side="left")
make_button(selector_top, "Back", show_home, w=140).pack(side="right")

search_row = tk.Frame(selector)
search_row.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
search_row.grid_columnconfigure(1, weight=1)

search_label = tk.Label(search_row, text="Search:", font=("Arial", 10, "bold"))
search_label.grid(row=0, column=0, sticky="w", padx=(0, 8))

search_var = tk.StringVar(value="")
search_entry = tk.Entry(search_row, textvariable=search_var)
search_entry.grid(row=0, column=1, sticky="ew")

def clear_search():
    search_var.set("")
    search_entry.focus_set()

clear_btn = tk.Button(search_row, text="Clear", command=clear_search)
clear_btn.grid(row=0, column=2, sticky="e", padx=(8, 0))

selector_center = tk.Frame(selector)
selector_center.grid(row=2, column=0, sticky="nsew", padx=10)

selector_canvas = tk.Canvas(selector_center, highlightthickness=0)
selector_scroll = tk.Scrollbar(selector_center, orient="vertical", command=selector_canvas.yview)
selector_canvas.configure(yscrollcommand=selector_scroll.set)
selector_canvas.pack(side="left", fill="both", expand=True)
selector_scroll.pack(side="right", fill="y")

selector_inner = tk.Frame(selector_canvas)
selector_win = selector_canvas.create_window((0, 0), window=selector_inner, anchor="nw")

def _selector_update_scroll(_=None):
    selector_canvas.configure(scrollregion=selector_canvas.bbox("all"))

selector_inner.bind("<Configure>", _selector_update_scroll)
selector_canvas.bind("<Configure>", lambda e: selector_canvas.itemconfig(selector_win, width=e.width))

vars_map = {}
for p in perks:
    v = tk.BooleanVar(value=p["name"] in settings["owned_perks"])
    chk = tk.Checkbutton(selector_inner, text=p["name"], variable=v, bd=0, highlightthickness=0)
    chk.pack(anchor="w", padx=10, pady=2)
    vars_map[p["name"]] = v
    checks.append(chk)
    selector_check_rows.append((p["name"].lower(), chk))

selector_bottom = tk.Frame(selector)
selector_bottom.grid(row=3, column=0, sticky="ew", padx=10, pady=(6, 10))

def select_all():
    for v in vars_map.values():
        v.set(True)

def select_none():
    for v in vars_map.values():
        v.set(False)

def save_owned():
    settings["owned_perks"] = [k for k, v in vars_map.items() if v.get()]
    save_settings()
    messagebox.showinfo("Saved", "Owned perks saved")

make_button(selector_bottom, "Select All", select_all, w=160).pack(side="left", padx=4)
make_button(selector_bottom, "Select None", select_none, w=160).pack(side="left", padx=4)
make_button(selector_bottom, "Save", save_owned, w=140).pack(side="right")

def refresh_selector_filter(*_):
    q = search_var.get().strip().lower()
    for name_lower, chk in selector_check_rows:
        if q == "" or q in name_lower:
            if not chk.winfo_ismapped():
                chk.pack(anchor="w", padx=10, pady=2)
        else:
            if chk.winfo_ismapped():
                chk.pack_forget()

    selector_inner.update_idletasks()
    selector_canvas.configure(scrollregion=selector_canvas.bbox("all"))
    selector_canvas.yview_moveto(0)

search_var.trace_add("write", refresh_selector_filter)

# ---------- HISTORY UI ----------
for w in history.winfo_children():
    w.destroy()

history.grid_rowconfigure(1, weight=1)
history.grid_columnconfigure(0, weight=1)

history_top = tk.Frame(history)
history_top.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 6))
tk.Label(history_top, text="Shuffle History", font=("Arial", 13, "bold")).pack(side="left")
make_button(history_top, "Back", show_home, w=140).pack(side="right")

history_center = tk.Frame(history)
history_center.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 6))
history_center.grid_rowconfigure(0, weight=1)
history_center.grid_columnconfigure(0, weight=1)

history_listbox = tk.Listbox(history_center, activestyle="none")
history_listbox.grid(row=0, column=0, sticky="nsew")

history_scroll = tk.Scrollbar(history_center, orient="vertical", command=history_listbox.yview)
history_scroll.grid(row=0, column=1, sticky="ns")
history_listbox.configure(yscrollcommand=history_scroll.set)

history_bottom = tk.Frame(history)
history_bottom.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

def clear_history():
    settings["history"] = []
    save_settings()
    refresh_history_listbox()

make_button(history_bottom, "Clear History", clear_history, w=200).pack(side="left")

refresh_history_listbox()

# ---------- DRAFT UI ----------
for w in draft.winfo_children():
    w.destroy()

draft.grid_rowconfigure(2, weight=1)
draft.grid_columnconfigure(0, weight=1)

draft_top = tk.Frame(draft)
draft_top.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 6))
tk.Label(draft_top, text="Draft Mode", font=("Arial", 13, "bold")).pack(side="left")
make_button(draft_top, "Back", show_home, w=140).pack(side="right")

draft_info = tk.Frame(draft)
draft_info.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
draft_info.grid_columnconfigure(0, weight=1)

draft_progress_lbl = tk.Label(draft_info, text="Pick for Slot 1 of 4", font=("Arial", 12, "bold"))
draft_progress_lbl.pack(anchor="w")

draft_selected_lbl = tk.Label(draft_info, text="Chosen: None yet", font=("Arial", 10))
draft_selected_lbl.pack(anchor="w", pady=(4, 0))

draft_options_frame = tk.Frame(draft)
draft_options_frame.grid(row=2, column=0, sticky="nsew", padx=10)

draft_bottom = tk.Frame(draft)
draft_bottom.grid(row=3, column=0, sticky="ew", padx=10, pady=(6, 10))
make_button(draft_bottom, "Restart Draft", lambda: (clear_draft(), start_draft()), w=200).pack(side="left")
make_button(draft_bottom, "Cancel", lambda: (clear_draft(), show_home()), w=140).pack(side="right")

# ---------- Theme application ----------
def apply_theme():
    t = current_theme()
    root.configure(bg=t["bg"])

    for w in (
        home, selector, history, draft,
        selector_top, search_row, selector_center, selector_inner, selector_bottom,
        history_top, history_center, history_bottom,
        draft_top, draft_info, draft_options_frame, draft_bottom
    ):
        w.configure(bg=t["bg"])

    title.configure(bg=t["bg"], fg=t["fg"])
    credit.configure(bg=t["bg"], fg="gray")

    for f in frames:
        f.configure(bg=t["bg"])
    for l in labels:
        l.configure(bg=t["bg"], fg=t["fg"])
    for i in icons:
        i.configure(bg=t["bg"])

    always_chk.configure(
        bg=t["bg"], fg=t["fg"],
        activebackground=t["bg"], activeforeground=t["fg"],
        selectcolor=t["bg"],
        bd=0, highlightthickness=0
    )
    always_var.set(bool(settings.get("always_on_top", False)))

    search_label.configure(bg=t["bg"], fg=t["fg"])
    search_entry.configure(bg=t["bg"], fg=t["fg"], insertbackground=t["fg"])
    clear_btn.configure(bg=t["accent"], fg="#000000", activebackground=t["accent"], activeforeground="#000000", bd=0)

    for chk in checks:
        chk.configure(
            bg=t["bg"], fg=t["fg"],
            activebackground=t["bg"], activeforeground=t["fg"],
            selectcolor=t["bg"],
            bd=0, highlightthickness=0
        )

    history_listbox.configure(
        bg=t["bg"], fg=t["fg"],
        selectbackground=t["accent"], selectforeground="#000000",
        highlightthickness=0, bd=0
    )

    draft_progress_lbl.configure(bg=t["bg"], fg=t["fg"])
    draft_selected_lbl.configure(bg=t["bg"], fg=t["fg"])

    for b in draft_option_buttons:
        b.configure(bg=t["bg"], fg=t["fg"], activebackground=t["accent"], activeforeground="#000000")

    for b in buttons:
        b.draw(False)

apply_theme()

# ✅ silent update check on launch (only shows popup if update exists)
root.after(1200, lambda: check_for_updates(False))

root.mainloop()

