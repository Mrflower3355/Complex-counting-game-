"""
Complex Number Guessing Game - v3.1.2
Adds: Themes (light/dark), sounds, points, achievements,
expanded leaderboard (stores points/time/attempts), game history,
Daily Challenge (date-seeded), Survival Mode (multi-stage),
Improved deterministic solver with visual log, UI improvements,
and defensive UI destruction checks.

Save this file and run with: python complex_guess_game_v3_1.2_all_features.py
"""

import json
import logging
import math
import os
import random
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText

# optional winsound (Windows only)
try:
    import winsound
    WINSOUND_AVAILABLE = True
except Exception:
    WINSOUND_AVAILABLE = False

# --- Constants & Storage ---
DEBUG = False
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO,
                    format='[%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

APP_DIR = os.path.join(os.path.expanduser("~"), ".complex_guess_game")
os.makedirs(APP_DIR, exist_ok=True)
LEADERBOARD_FILE = os.path.join(APP_DIR, "leaderboard.json")
HISTORY_FILE = os.path.join(APP_DIR, "history.json")
ACHIEVEMENTS_FILE = os.path.join(APP_DIR, "achievements.json")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
MAX_LEADERBOARD = 10

INPUT_DISABLE_MS = 200
AUTO_STEP_DELAY_MS = 150

DIFFICULTY_SETTINGS = {
    1: {"range": 10, "attempts": 15, "timer": 120},
    2: {"range": 50, "attempts": 10, "timer": 180},
    3: {"range": 100, "attempts": 8, "timer": 300},
}

# Achievements definitions (simple)
ACHIEVEMENTS_DEF = {
    "one_shot": {"title": "One-Shot", "desc": "Win in 1 attempt"},
    "quick_win": {"title": "Quick Win", "desc": "Win under 30 seconds"},
    "no_hints": {"title": "Pure Luck", "desc": "Win without component hints"},
    "speed_runner": {"title": "Speed Runner", "desc": "Win under 10 seconds"},
}

# --- JSON helpers ---


def safe_load_json(path, default=None):
    if default is None:
        default = []
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        log.exception(f"Failed loading JSON: {path}")
        return default


def safe_save_json(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        log.exception(f"Failed saving JSON: {path}")


# --- Leaderboard / History / Achievements ---

def load_leaderboard():
    return safe_load_json(LEADERBOARD_FILE, [])


def save_leaderboard(board):
    safe_save_json(LEADERBOARD_FILE, board)


def update_leaderboard(name, points, attempts, time_seconds, mode):
    board = load_leaderboard()
    entry = {
        "name": str(name),
        "points": int(points),
        "attempts": int(attempts),
        "time": int(time_seconds),
        "mode": mode,
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    board.append(entry)
    # sort by points desc
    board = sorted(board, key=lambda x: x["points"], reverse=True)[
        :MAX_LEADERBOARD]
    save_leaderboard(board)


def leaderboard_str():
    board = load_leaderboard()
    if not board:
        return "No scores yet."
    txt = "🏆 Leaderboard\n"
    for i, e in enumerate(board, 1):
        txt += f"{i}. {e['name']} - {e['points']} pts ({e['attempts']} attempts, {e['time']}s)\n"
    return txt


def load_history():
    return safe_load_json(HISTORY_FILE, [])


def save_history_entry(entry):
    h = load_history()
    h.insert(0, entry)
    safe_save_json(HISTORY_FILE, h[:200])


def load_achievements():
    return safe_load_json(ACHIEVEMENTS_FILE, {})


def save_achievements(data):
    safe_save_json(ACHIEVEMENTS_FILE, data)


# --- Utilities ---

def is_prime(n):
    n = abs(int(n))
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True


# --- Main Game ---
class GuessingGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Complex Number Guessing Game v3.1")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # State
        self.solver_running = False
        self.timer_after_id = None
        self.auto_after_id = None
        self._cheat_ended = False
        self._auto_mode = False
        self.start_time = None
        self.hint_used = False
        self.mode = "standard"
        self.difficulty = 1

        # Theme
        self.settings = safe_load_json(SETTINGS_FILE, {"theme": "light"})
        self.theme = self.settings.get("theme", "light")
        self.THEMES = {
            "light": {"bg": "#f0f0f0", "fg": "#000000", "btn_bg": "#e0e0e0"},
            "dark": {"bg": "#222222", "fg": "#f5f5f5", "btn_bg": "#333333"},
        }

        self.root.bind_all("<Control-p>", self._on_ctrl_p)
        self.create_menu()

    def on_close(self):
        # ensure cleanup
        self.stop_all_auto_tasks()
        self.root.destroy()

    def _on_ctrl_p(self, event=None):
        if hasattr(self, "target_number"):
            log.info("Ctrl+P detected -> activating cheat.")
            self.cheat_win()

    def apply_theme(self, widget=None):
        th = self.THEMES.get(self.theme, self.THEMES["light"])
        self.root.configure(bg=th["bg"])
        # if widget provided, attempt to configure relevant children
        if hasattr(self, 'widgets'):
            for w in self.widgets:
                try:
                    w_type = w.winfo_class()
                    if w_type in ("Label", "Frame", "Button", "Entry", "Text"):
                        if w_type == "Button":
                            w.configure(
                                bg=th["btn_bg"], fg=th["fg"], activebackground=th["bg"])
                        else:
                            w.configure(bg=th["bg"], fg=th["fg"])
                except Exception:
                    pass

    def create_menu(self):
        self.stop_all_auto_tasks()
        self.clear()
        self.widgets = []
        th = self.THEMES.get(self.theme)

        title = tk.Label(self.root, text="Complex Number Guessing Game",
                         font=("Arial", 16, "bold"), bg=th["bg"], fg=th["fg"])
        title.pack(pady=8)
        self.widgets.append(title)

        info = tk.Label(self.root, text=leaderboard_str(), font=(
            "Arial", 11), justify="left", bg=th["bg"], fg=th["fg"])
        info.pack(pady=6)
        self.widgets.append(info)

        btn_frame = tk.Frame(self.root, bg=th["bg"])
        btn_frame.pack(pady=6)
        self.widgets.append(btn_frame)

        def add_btn(text, cmd, parent=btn_frame):
            b = tk.Button(parent, text=text, width=22,
                          command=cmd, bg=th['btn_bg'], fg=th['fg'])
            b.pack(pady=3)
            self.widgets.append(b)
            return b

        add_btn("Easy (±10)", lambda: self.start(1))
        add_btn("Medium (±50)", lambda: self.start(2))
        add_btn("Hard (±100)", lambda: self.start(3))
        add_btn("Run Deterministic Solver (Easy)",
                lambda: self.run_improved_solver())
        add_btn("Daily Challenge", lambda: self.start_daily_challenge())
        add_btn("Survival Mode (3 rounds)",
                lambda: self.start_survival_mode(3))
        add_btn("View History", lambda: self.show_history())
        add_btn("View Achievements", lambda: self.show_achievements())
        add_btn("Toggle Theme", lambda: self.toggle_theme())
        add_btn("Clear Leaderboard", lambda: self.clear_leaderboard())
        add_btn("Exit", lambda: self.root.destroy())

        self.apply_theme()

    def clear(self):
        for widget in self.root.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass

    def stop_all_auto_tasks(self):
        self.cancel_timer()
        if self.auto_after_id:
            try:
                self.root.after_cancel(self.auto_after_id)
            except Exception:
                pass
            self.auto_after_id = None
        self.solver_running = False
        self._auto_mode = False
        log.debug("Stopped all auto tasks and cleared flags")

    def start(self, difficulty, stop_auto=True, custom_range=None, mode='standard', daily_seed=None, survival_rounds=0):
        self._cheat_ended = False
        if stop_auto:
            self.stop_all_auto_tasks()

        self.difficulty = difficulty
        conf = DIFFICULTY_SETTINGS.get(
            difficulty, DIFFICULTY_SETTINGS[1]).copy()
        if custom_range:
            conf['range'] = custom_range
        self.max_range = conf['range']
        self.max_attempts = conf['attempts']
        self.timer = conf['timer']
        self.mode = mode
        self.survival_rounds = survival_rounds

        if daily_seed is not None:
            rng = random.Random(daily_seed)
            real_part = rng.randint(-self.max_range, self.max_range)
            imag_part = rng.randint(-self.max_range, self.max_range)
        else:
            real_part = random.randint(-self.max_range, self.max_range)
            imag_part = random.randint(-self.max_range, self.max_range)

        self.target_number = complex(real_part, imag_part)
        self.target_magnitude = abs(self.target_number)
        log.debug(f"Target number: {self.target_number}")

        self.attempts = 0
        self.start_time = time.time()
        self.hint_used = False
        self.mode = mode

        self.setup_game_ui()
        self.update_timer()

    def setup_game_ui(self):
        self.clear()
        self.widgets = []
        th = self.THEMES.get(self.theme)

        range_str = f"Guess a complex number (a + bi) where 'a' and 'b' are between {-self.max_range} and {self.max_range}"
        lbl = tk.Label(self.root, text=range_str, font=(
            "Arial", 12), wraplength=460, bg=th['bg'], fg=th['fg'])
        lbl.pack(pady=6)
        self.widgets.append(lbl)

        input_frame = tk.Frame(self.root, bg=th['bg'])
        input_frame.pack(pady=4)
        self.widgets.append(input_frame)

        tk.Label(input_frame, text="Real (a):", font=("Arial", 12),
                 bg=th['bg'], fg=th['fg']).pack(side="left", padx=5)
        self.entry_real = tk.Entry(input_frame, font=("Arial", 12), width=8)
        self.entry_real.pack(side="left")
        tk.Label(input_frame, text="Imaginary (b):", font=("Arial", 12),
                 bg=th['bg'], fg=th['fg']).pack(side="left", padx=5)
        self.entry_imag = tk.Entry(input_frame, font=("Arial", 12), width=8)
        self.entry_imag.pack(side="left")

        self.entry_real.bind("<Return>", lambda e: self.check_guess())
        self.entry_imag.bind("<Return>", lambda e: self.check_guess())
        self.entry_real.focus_set()

        self.submit_btn = tk.Button(
            self.root, text="Submit Guess", command=self.check_guess, bg=th['btn_bg'], fg=th['fg'])
        self.submit_btn.pack(pady=8)
        self.widgets.append(self.submit_btn)

        self.info_label = tk.Label(self.root, text="", font=(
            "Arial", 11), justify="center", bg=th['bg'], fg=th['fg'])
        self.info_label.pack(pady=6)
        self.widgets.append(self.info_label)

        self.timer_label = tk.Label(self.root, text="", font=(
            "Arial", 12), fg="blue", bg=th['bg'])
        self.timer_label.pack(pady=4)
        self.widgets.append(self.timer_label)

        # Log area (visual feedback & solver log)
        self.log_text = ScrolledText(self.root, height=8)
        self.log_text.pack(fill="both", expand=False, padx=8, pady=6)
        self.widgets.append(self.log_text)
        self.log_text.insert(tk.END, "Game log:\n")
        self.log_text.configure(state='disabled')

        # helper small buttons
        small_frame = tk.Frame(self.root, bg=th['bg'])
        small_frame.pack(pady=4)
        self.widgets.append(small_frame)
        tk.Button(small_frame, text="Cheat (Ctrl+P)", command=self.cheat_win,
                  bg=th['btn_bg'], fg=th['fg']).pack(side='left', padx=4)
        tk.Button(small_frame, text="Hint", command=self.show_hint,
                  bg=th['btn_bg'], fg=th['fg']).pack(side='left', padx=4)
        tk.Button(small_frame, text="Give Up", command=lambda: self.end_game(
            False, f"Gave up. The number was {self.target_number}"), bg=th['btn_bg'], fg=th['fg']).pack(side='left', padx=4)

        self.apply_theme()

    def update_timer(self):
        if not self.start_time:
            return
        elapsed = int(time.time() - self.start_time)
        remaining = self.timer - elapsed

        if hasattr(self, 'timer_label') and self.timer_label.winfo_exists():
            self.timer_label.config(
                text=f"⏳ Time left: {max(0, remaining)//60}:{max(0, remaining) % 60:02d}")
        else:
            self.cancel_timer()
            return

        if remaining <= 0:
            self.end_game(
                False, f"Time's up! The number was {self.target_number}")
            return
        try:
            self.timer_after_id = self.root.after(1000, self.update_timer)
        except Exception:
            self.timer_after_id = None

    def check_guess(self):
        if not hasattr(self, 'entry_real'):
            return
        try:
            real = int(self.entry_real.get().strip())
            imag = int(self.entry_imag.get().strip())
        except Exception:
            messagebox.showerror(
                "Invalid Input", "Please enter valid integers for both real and imaginary parts.")
            return

        self.attempts += 1
        guess = complex(real, imag)
        self.log_message(f"Attempt {self.attempts}: {guess} (|{abs(guess)}|)")
        self.disable_inputs_temporarily()

        if guess == self.target_number:
            time_taken = time.time() - self.start_time if self.start_time else 0
            points = max(0, 1000 - self.attempts * 40 - int(time_taken) * 2)
            name_to_save = None
            if not DEBUG and not self._auto_mode and not self._cheat_ended:
                name_to_save = simpledialog.askstring(
                    "You Won!", f"Correct in {self.attempts} attempts. Points: {points}\nEnter your name for the leaderboard:")
                if name_to_save:
                    update_leaderboard(
                        name_to_save, points, self.attempts, int(time_taken), self.mode)
            # save history
            save_history_entry({
                "result": "win",
                "target": str(self.target_number),
                "attempts": self.attempts,
                "time": int(time_taken),
                "points": int(points),
                "mode": self.mode,
                "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            })

            # achievements
            new_ach = self.check_and_award_achievements(
                self.attempts, time_taken, self.hint_used)
            msg = f"Correct! You guessed {self.target_number} in {self.attempts} attempts. Points: {points}."
            if new_ach:
                msg += "\nNew Achievements: " + ", ".join(new_ach)

            self.end_game(True, msg)
            return

        guess_magnitude = abs(guess)
        magnitude_hint = "Magnitude is TOO LOW." if guess_magnitude < self.target_magnitude else "Magnitude is TOO HIGH."
        component_hints = self.give_component_hints()
        if component_hints:
            self.hint_used = True
        full_hint = magnitude_hint + \
            ("\n" + component_hints if component_hints else "")

        if hasattr(self, 'info_label') and self.info_label.winfo_exists():
            self.info_label.config(text=full_hint)

        if self.attempts >= self.max_attempts:
            self.end_game(
                False, f"Out of attempts! The number was {self.target_number}")

    def show_hint(self):
        # manual hint: show component hint immediately
        h = self.give_component_hints(force=True)
        if h:
            self.hint_used = True
            messagebox.showinfo("Hint", h)
        else:
            messagebox.showinfo(
                "Hint", "No extra component hints at this time.")

    def give_component_hints(self, force=False):
        # give component hints every 2 attempts or if forced
        if (self.attempts % 2 != 0) and not force:
            return ""
        tr = math.trunc(self.target_number.real)
        ti = math.trunc(self.target_number.imag)
        hints = []
        hints.append("Real part is even" if tr %
                     2 == 0 else "Real part is odd")
        if is_prime(ti):
            hints.append("Imaginary part is prime")
        return "Hint: " + ", ".join(hints)

    def end_game(self, win, msg):
        self.cancel_timer()
        try:
            if win:
                if WINSOUND_AVAILABLE:
                    winsound.MessageBeep(winsound.MB_ICONINFORMATION)
                messagebox.showinfo("Victory!", msg)
            else:
                if WINSOUND_AVAILABLE:
                    winsound.MessageBeep(winsound.MB_ICONHAND)
                messagebox.showerror("Game Over", msg)
        except Exception:
            pass

        # stop auto tasks, then return to menu
        self.stop_all_auto_tasks()
        # small delay to ensure messageboxes closed
        try:
            self.root.after(200, self.create_menu)
        except Exception:
            self.create_menu()

    def cheat_win(self):
        self._cheat_ended = True
        try:
            messagebox.showinfo("Cheat Activated",
                                f"The number was {self.target_number}.")
        except Exception:
            pass
        self.end_game(
            False, f"Cheat used. The number was {self.target_number}")

    def disable_inputs_temporarily(self):
        if hasattr(self, 'submit_btn') and self.submit_btn.winfo_exists():
            self.submit_btn.config(state="disabled")

            def enable_inputs():
                try:
                    if self.submit_btn.winfo_exists():
                        self.submit_btn.config(state="normal")
                except Exception:
                    pass

            try:
                self.root.after(INPUT_DISABLE_MS, enable_inputs)
            except Exception:
                pass

    def cancel_timer(self):
        if self.timer_after_id:
            try:
                self.root.after_cancel(self.timer_after_id)
            except Exception:
                pass
            self.timer_after_id = None
        self.start_time = None

    def log_message(self, text):
        try:
            if hasattr(self, 'log_text') and self.log_text.winfo_exists():
                self.log_text.configure(state='normal')
                self.log_text.insert(
                    tk.END, f"{time.strftime('%H:%M:%S')} - {text}\n")
                self.log_text.see(tk.END)
                # trim
                content = self.log_text.get('1.0', tk.END).splitlines()
                if len(content) > 500:
                    self.log_text.delete('1.0', f'{len(content)-400}.0')
                self.log_text.configure(state='disabled')
        except Exception:
            pass

    # ---------------- Solver (deterministic spiral) ----------------
    def run_improved_solver(self):
        if self.solver_running:
            messagebox.showwarning("Busy", "Solver already running.")
            return
        # restrict to safe range
        if getattr(self, 'max_range', 0) > 30:
            messagebox.showwarning(
                "Too Large", "Solver only runs reliably on ranges <= 30. Start Easy mode first.")
            return
        self._auto_mode = True
        self.start(1, stop_auto=False)
        self.solver_running = True
        self.log_message("Solver started (deterministic spiral).")
        self.solver_radius = int(self.max_range)
        self.solver_coords = self._generate_spiral_coords(self.solver_radius)
        self.root.after(AUTO_STEP_DELAY_MS, self._solver_step)

    def _generate_spiral_coords(self, radius):
        coords = []
        # ring-by-ring deterministic square spiral
        for r in range(0, radius+1):
            if r == 0:
                coords.append((0, 0))
                continue
            x0, y0 = -r, -r
            # top row left->right
            for x in range(x0, x0 + 2*r + 1):
                coords.append((x, y0))
            # right col top+1 -> bottom
            for y in range(y0 + 1, y0 + 2*r + 1):
                coords.append((x0 + 2*r, y))
            # bottom row right-1 -> left
            for x in range(x0 + 2*r - 1, x0 - 1, -1):
                coords.append((x, y0 + 2*r))
            # left col bottom-1 -> top+1
            for y in range(y0 + 2*r - 1, y0, -1):
                coords.append((x0, y))
        # filter coords within radius bounds
        filtered = [c for c in coords if abs(
            c[0]) <= radius and abs(c[1]) <= radius]
        # remove duplicates while preserving order
        seen = set()
        out = []
        for c in filtered:
            if c not in seen:
                seen.add(c)
                out.append(c)
        return out

    def _solver_step(self):
        if not self.solver_running:
            return
        if self.attempts >= self.max_attempts:
            self.end_game(
                False, f"Solver failed in {self.max_attempts} attempts. The number was {self.target_number}")
            self.solver_running = False
            return
        if not hasattr(self, 'entry_real') or not self.entry_real.winfo_exists():
            self.solver_running = False
            return

        if not self.solver_coords:
            self.end_game(
                False, f"Solver exhausted search. The number was {self.target_number}")
            self.solver_running = False
            return

        rx, ry = self.solver_coords.pop(0)
        # clamp within allowed range for safety
        rx = max(-self.max_range, min(self.max_range, rx))
        ry = max(-self.max_range, min(self.max_range, ry))

        self.entry_real.delete(0, tk.END)
        self.entry_real.insert(0, str(rx))
        self.entry_imag.delete(0, tk.END)
        self.entry_imag.insert(0, str(ry))

        self.check_guess()

        if not self.solver_running:
            return

        # small heuristic: if last guess magnitude is far, skip some coords.
        self.auto_after_id = self.root.after(
            AUTO_STEP_DELAY_MS, self._solver_step)

    # ---------------- Survival Mode ----------------
    def start_survival_mode(self, rounds=3):
        # survival: short timer, multiple consecutive wins
        self.survival_target_rounds = rounds
        self.survival_wins = 0
        self.survival_round = 1
        # make shorter timer and smaller ranges
        self.start(1, stop_auto=True, custom_range=8, mode='survival')
        self.timer = 25
        self.log_message(f"Survival mode: {rounds} rounds. Good luck!")

    # ---------------- Daily Challenge ----------------
    def start_daily_challenge(self):
        today = time.strftime('%Y-%m-%d')
        seed = f"daily-{today}"
        self.start(2, stop_auto=True, mode='daily', daily_seed=seed)
        self.log_message(f"Daily challenge for {today} started.")

    # ---------------- Achievements/History UI ----------------
    def check_and_award_achievements(self, attempts, time_taken, hint_used):
        unlocked = []
        ach_store = load_achievements()
        if attempts == 1 and not ach_store.get('one_shot'):
            ach_store['one_shot'] = time.strftime('%Y-%m-%d')
            unlocked.append(ACHIEVEMENTS_DEF['one_shot']['title'])
        if time_taken < 10 and not ach_store.get('speed_runner'):
            ach_store['speed_runner'] = time.strftime('%Y-%m-%d')
            unlocked.append(ACHIEVEMENTS_DEF['speed_runner']['title'])
        if time_taken < 30 and not ach_store.get('quick_win'):
            ach_store['quick_win'] = time.strftime('%Y-%m-%d')
            unlocked.append(ACHIEVEMENTS_DEF['quick_win']['title'])
        if not hint_used and not ach_store.get('no_hints'):
            ach_store['no_hints'] = time.strftime('%Y-%m-%d')
            unlocked.append(ACHIEVEMENTS_DEF['no_hints']['title'])
        if unlocked:
            save_achievements(ach_store)
            self.log_message(f"New achievements: {', '.join(unlocked)}")
        return unlocked

    def show_history(self):
        h = load_history()
        win = tk.Toplevel(self.root)
        win.title("Game History")
        txt = ScrolledText(win, width=60, height=20)
        txt.pack(fill='both', expand=True)
        for e in h[:200]:
            txt.insert(tk.END, json.dumps(e, ensure_ascii=False) + "\n")
        txt.configure(state='disabled')

    def show_achievements(self):
        a = load_achievements()
        lines = []
        for k, v in ACHIEVEMENTS_DEF.items():
            unlocked = a.get(k)
            lines.append(
                f"{v['title']}: {v['desc']} - {'Unlocked on ' + a[k] if unlocked else 'Locked'}")
        messagebox.showinfo("Achievements", "\n".join(lines))

    def toggle_theme(self):
        self.theme = 'dark' if self.theme == 'light' else 'light'
        self.settings['theme'] = self.theme
        safe_save_json(SETTINGS_FILE, self.settings)
        self.apply_theme()

    def clear_leaderboard(self):
        if messagebox.askyesno("Confirm", "Clear leaderboard?"):
            save_leaderboard([])
            messagebox.showinfo("Cleared", "Leaderboard cleared.")
            self.create_menu()


if __name__ == '__main__':
    root = tk.Tk()
    root.geometry('520x640')
    game = GuessingGame(root)
    root.mainloop()
