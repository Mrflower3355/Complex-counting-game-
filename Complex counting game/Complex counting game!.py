# Complex Number Guessing Game - Patch 2.2.1 (Improved + Auto-Simulation)
# - Thread-safe (no UI calls from background threads)
# - Timer cancel, safe parsing, safer leaderboard file location
# - Cheat via Ctrl+P and via entry 'p' (doesn't update leaderboard)
# - Auto-Test (main-thread) and Auto-Simulation (multiple rounds)
# - DEBUG via logging

import tkinter as tk
from tkinter import messagebox, simpledialog
import random
import time
import os
import json
import logging

# Optional winsound (Windows only)
try:
    import winsound
    WINSOUND_AVAILABLE = True
except Exception:
    WINSOUND_AVAILABLE = False

# Logging setup
DEBUG = True
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# App storage (leaderboard)
APP_DIR = os.path.join(os.path.expanduser("~"), ".complex_guess_game")
os.makedirs(APP_DIR, exist_ok=True)
LEADERBOARD_FILE = os.path.join(APP_DIR, "leaderboard.json")
MAX_LEADERBOARD = 5

def safe_load_leaderboard():
    if not os.path.exists(LEADERBOARD_FILE):
        log.debug("Leaderboard file not found, starting fresh.")
        return []
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            log.debug("Leaderboard file invalid, resetting.")
            return []
        clean = []
        for e in data:
            if isinstance(e, dict) and 'name' in e and 'score' in e:
                try:
                    score = int(e['score'])
                    clean.append({'name': str(e['name']), 'score': score})
                except Exception:
                    continue
        log.debug(f"Loaded leaderboard: {clean}")
        return clean
    except Exception:
        log.exception("Error reading leaderboard file; resetting.")
        return []

def safe_save_leaderboard(board):
    try:
        tmp = LEADERBOARD_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(board, f, indent=2, ensure_ascii=False)
        os.replace(tmp, LEADERBOARD_FILE)
        log.debug(f"Saved leaderboard: {board}")
    except Exception:
        log.exception("Failed to save leaderboard.")

def update_leaderboard(name, score):
    board = safe_load_leaderboard()
    board.append({"name": str(name), "score": int(score)})
    board = sorted(board, key=lambda x: x["score"])[:MAX_LEADERBOARD]
    safe_save_leaderboard(board)
    log.debug(f"Updated leaderboard with {name} - {score} attempts")
    return board

def leaderboard_str():
    board = safe_load_leaderboard()
    if not board:
        return "No scores yet."
    text = "🏆 Leaderboard (Top 5)\n"
    for i, entry in enumerate(board, 1):
        text += f"{i}. {entry['name']} - {entry['score']} attempts\n"
    return text

def is_prime(n):
    if n < 2: return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0: return False
    return True

class GuessingGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Complex Number Guessing Game")
        self.auto_test_running = False
        self.timer_after_id = None
        self.auto_after_id = None
        self.timer_running = False
        self._cheat_ended = False
        self._auto_mode = False

        # Auto-simulation state
        self.sim_running = False
        self.sim_results = []
        self.sim_config = None  # tuple(difficulties, rounds_each)
        self.sim_state = None   # internal iterator/state

        # bind safer cheat: Ctrl+P
        self.root.bind_all("<Control-p>", self._on_ctrl_p)
        self.create_menu()

    def _on_ctrl_p(self, event=None):
        if getattr(self, "number", None) is not None:
            log.info("Ctrl+P detected -> activating cheat.")
            self.cheat_win()

    def clear(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def create_menu(self):
        self.clear()
        tk.Label(self.root, text="Select Difficulty", font=("Arial", 14)).pack(pady=10)
        tk.Button(self.root, text="Easy (1-50)", width=20, command=lambda: self.start(1)).pack(pady=5)
        tk.Button(self.root, text="Medium (1-500)", width=20, command=lambda: self.start(2)).pack(pady=5)
        tk.Button(self.root, text="Hard (1-1000)", width=20, command=lambda: self.start(3)).pack(pady=5)
        tk.Button(self.root, text="Auto-Test", width=20, command=self.run_auto_test).pack(pady=5)
        tk.Button(self.root, text="Auto-Simulation", width=20, command=self.start_auto_simulation_dialog).pack(pady=5)
        tk.Label(self.root, text=leaderboard_str(), font=("Arial", 12), justify="left").pack(pady=10)

    def start(self, difficulty):
        # reset scheduled tasks and flags
        self._cheat_ended = False
        self._auto_mode = False
        self.cancel_timer()
        self.cancel_auto_schedule()

        if difficulty == 1:
            self.min_num, self.max_num, self.max_attempts, self.timer = 1, 50, 12, 120
        elif difficulty == 2:
            self.min_num, self.max_num, self.max_attempts, self.timer = 1, 500, 8, 180
        else:
            self.min_num, self.max_num, self.max_attempts, self.timer = 1, 1000, 6, 300

        if self.min_num >= self.max_num:
            self.max_num = self.min_num + 50

        self.number = random.randint(self.min_num, self.max_num)
        log.debug(f"Number to guess: {self.number}")
        self.attempts = 0
        self.guesses = []
        self.start_time = time.time()

        self.clear()
        self.status = tk.Label(self.root, text=f"Guess a number between {self.min_num} and {self.max_num}", font=("Arial", 12))
        self.status.pack(pady=10)
        self.entry = tk.Entry(self.root, font=("Arial", 12))
        self.entry.pack(pady=5)
        self.entry.bind("<Return>", lambda e: self.check_guess())
        self.entry.focus_set()
        self.submit_btn = tk.Button(self.root, text="Submit", command=self.check_guess)
        self.submit_btn.pack(pady=5)
        self.info = tk.Label(self.root, text="", font=("Arial", 11))
        self.info.pack(pady=10)
        self.timer_label = tk.Label(self.root, text="", font=("Arial", 12), fg="blue")
        self.timer_label.pack(pady=10)

        self.timer_running = True
        self.update_timer()

    def update_timer(self):
        if not getattr(self, "timer_running", False):
            return
        elapsed = int(time.time() - self.start_time)
        remaining = self.timer - elapsed
        log.debug(f"Timer update - remaining: {remaining}s")
        if getattr(self, "timer_label", None) and self.timer_label.winfo_exists():
            try:
                self.timer_label.config(text=f"⏳ Time left: {remaining//60}:{remaining%60:02d}")
            except Exception:
                log.exception("Failed updating timer_label")
        if remaining <= 0:
            self.timer_running = False
            self.end_game(False, "Time's up! The number was {}".format(getattr(self, "number", "N/A")))
            return
        try:
            self.timer_after_id = self.root.after(1000, self.update_timer)
        except Exception:
            log.exception("Failed to schedule timer update")

    def give_hint(self):
        hints = []
        try:
            hints.append("even" if self.number % 2 == 0 else "odd")
            if self.attempts > 0 and self.attempts % 2 == 0:
                if self.number % 3 == 0: hints.append("divisible by 3")
                if self.number % 5 == 0: hints.append("divisible by 5")
                if is_prime(self.number): hints.append("prime number")
        except Exception:
            log.exception("give_hint error")
        log.debug(f"Hints: {hints}")
        return hints

    def check_guess(self):
        if not getattr(self, "entry", None) or not self.entry.winfo_exists():
            return
        guess_str = self.entry.get()
        if guess_str.strip().lower() == 'p':
            self.cheat_win()
            return

        try:
            guess = int(guess_str.strip())
        except ValueError:
            messagebox.showerror("Error", "Enter a valid integer.")
            return

        if guess < self.min_num or guess > self.max_num:
            messagebox.showwarning("Out of range", f"Enter between {self.min_num}-{self.max_num}.")
            return

        self.guesses.append(guess)
        self.attempts += 1
        log.debug(f"Attempt {self.attempts}: {guess}")

        # disable inputs briefly
        self.disable_inputs_temporarily()

        if guess == self.number:
            if DEBUG:
                name = "AutoTester"
            else:
                try:
                    name = simpledialog.askstring("Name", "Enter your name for leaderboard:")
                except Exception:
                    name = None
            if name and not getattr(self, "_cheat_ended", False) and not getattr(self, "_auto_mode", False):
                update_leaderboard(name, self.attempts)
            self.end_game(True, f"Correct! Guessed in {self.attempts} attempts.")
            return

        # wrong guess handling
        if guess < self.number:
            self.info.config(text="Too low! Try again.")
        else:
            self.info.config(text="Too high! Try again.")

        hints = self.give_hint()
        if hints:
            try:
                self.info.config(text=self.info.cget("text") + "\nHint: " + ", ".join(hints))
            except Exception:
                log.exception("Failed to append hints to info label")

        if self.attempts >= self.max_attempts:
            self.end_game(False, f"Out of attempts! Number was {self.number}")

    def end_game(self, win, msg):
        # cancel scheduled tasks to avoid lingering callbacks
        self.cancel_timer()
        self.cancel_auto_schedule()
        try:
            if win:
                if WINSOUND_AVAILABLE:
                    try:
                        winsound.MessageBeep()
                    except Exception:
                        pass
                messagebox.showinfo("Victory", msg)
            else:
                messagebox.showerror("Game Over", msg)
        except Exception:
            log.exception("Failed showing end dialog")
        self._cheat_ended = False
        self._auto_mode = False
        self.auto_test_running = False
        # rebuild menu
        self.create_menu()

    def cheat_win(self):
        self._cheat_ended = True
        try:
            messagebox.showinfo("Cheat Activated", f"Cheat used! The number was {getattr(self, 'number', 'N/A')}.")
        except Exception:
            log.exception("Failed showing cheat message")
        # do not update leaderboard
        self.end_game(False, f"Cheat used. The number was {getattr(self, 'number', 'N/A')}")

    def disable_inputs_temporarily(self, millis=300):
        try:
            if getattr(self, "submit_btn", None) and self.submit_btn.winfo_exists():
                self.submit_btn.config(state="disabled")
                self.root.after(millis, lambda: self.submit_btn.config(state="normal"))
        except Exception:
            log.exception("Failed to toggle inputs")

    # ---------- Auto-Test (single run, main-thread) ----------
    def run_auto_test(self):
        if self.auto_test_running:
            log.info("Auto-test already running; ignoring request.")
            return
        self.auto_test_running = True
        self._auto_mode = True
        self.start(1)  # start easy mode
        # prepare brute-force sequential iterator
        self._auto_next = iter(range(self.min_num, self.max_num + 1))

        def _auto_step():
            if not self.auto_test_running:
                return
            try:
                guess = next(self._auto_next)
            except StopIteration:
                # shouldn't normally happen because number in range
                self.auto_test_running = False
                return
            if not getattr(self, "entry", None) or not self.entry.winfo_exists():
                self.auto_test_running = False
                return
            try:
                self.entry.delete(0, tk.END)
                self.entry.insert(0, str(guess))
                self.check_guess()
            except Exception:
                log.exception("Auto-test step failure")
                self.auto_test_running = False
                return
            # schedule next step if still running
            if self.auto_test_running and getattr(self, "number", None) is not None:
                try:
                    self.auto_after_id = self.root.after(150, _auto_step)
                except Exception:
                    log.exception("Failed to schedule auto step")
                    self.auto_test_running = False

        try:
            self.auto_after_id = self.root.after(150, _auto_step)
        except Exception:
            log.exception("Failed to start auto-test")
            self.auto_test_running = False

    def cancel_timer(self):
        self.timer_running = False
        if getattr(self, "timer_after_id", None):
            try:
                self.root.after_cancel(self.timer_after_id)
            except Exception:
                pass
            self.timer_after_id = None

    def cancel_auto_schedule(self):
        self.auto_test_running = False
        if getattr(self, "auto_after_id", None):
            try:
                self.root.after_cancel(self.auto_after_id)
            except Exception:
                pass
            self.auto_after_id = None

    # ---------- Auto-Simulation (multiple rounds, safe via after) ----------
    def start_auto_simulation_dialog(self):
        if self.sim_running:
            messagebox.showinfo("Simulation", "Simulation already running.")
            return
        # ask config: difficulties and rounds each (simple)
        try:
            rounds = simpledialog.askinteger("Auto-Simulation", "How many rounds per difficulty? (e.g. 3)", minvalue=1, maxvalue=20)
            if rounds is None:
                return
        except Exception:
            rounds = 3
        # default difficulties: [1,2,3]
        self.start_auto_simulation(difficulties=[1,2,3], rounds_each=rounds)

    def start_auto_simulation(self, difficulties=[1,2,3], rounds_each=3):
        """Start auto-simulation: runs rounds_each rounds for each difficulty in difficulties.
        Results collected into self.sim_results as tuples (difficulty, round_index, attempts or 'fail').
        Implemented with `after` to stay on main thread (safe)."""
        if self.sim_running:
            log.info("Simulation already running.")
            return
        self.sim_running = True
        self.sim_results = []
        self.sim_config = (list(difficulties), rounds_each)
        # state indices
        self.sim_state = {
            "diff_idx": 0,
            "round_idx": 0,
            "current_attempts": 0,
            "current_guess_iter": None
        }
        log.info(f"Starting Auto-Simulation: difficulties={difficulties}, rounds_each={rounds_each}")
        # start first round via after to ensure UI stable
        self.root.after(200, self._sim_step_start_round)

    def _sim_step_start_round(self):
        if not self.sim_running or not self.sim_config:
            return
        difficulties, rounds_each = self.sim_config
        s = self.sim_state
        if s["diff_idx"] >= len(difficulties):
            # finished all difficulties
            self.sim_running = False
            log.info(f"Auto-Simulation finished. Results: {self.sim_results}")
            try:
                messagebox.showinfo("Auto-Simulation", f"Simulation finished.\nResults:\n{self.sim_results}")
            except Exception:
                pass
            return
        difficulty = difficulties[s["diff_idx"]]
        if s["round_idx"] >= rounds_each:
            # advance difficulty
            s["diff_idx"] += 1
            s["round_idx"] = 0
            self.root.after(100, self._sim_step_start_round)
            return

        # start a new game for this difficulty
        self._cheat_ended = False
        self._auto_mode = True
        self.start(difficulty)
        self.sim_state["current_attempts"] = 0
        self.sim_state["current_guess_iter"] = iter(range(self.min_num, self.max_num + 1))
        log.debug(f"Sim: starting difficulty {difficulty}, round {s['round_idx']+1}")
        # schedule first guess
        self.root.after(150, self._sim_step_make_guess)

    def _sim_step_make_guess(self):
        if not self.sim_running or not self.sim_config:
            return
        s = self.sim_state
        # if entry gone stop
        if not getattr(self, "entry", None) or not self.entry.winfo_exists():
            self.sim_running = False
            return
        try:
            guess = next(s["current_guess_iter"])
        except StopIteration:
            # shouldn't happen
            guess = None

        if guess is None:
            # fail to find
            self.sim_results.append((s["diff_idx"], s["round_idx"], "fail"))
            s["round_idx"] += 1
            self.root.after(100, self._sim_step_start_round)
            return

        # perform guess
        try:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, str(guess))
            # increment attempt counter BEFORE check (check_guess also increments attempts)
            # but to keep consistent with normal flow, let check_guess increment
            self.check_guess()
        except Exception:
            log.exception("Auto-sim guess error")
            self.sim_running = False
            return

        # if game ended due to correct guess or attempts exhausted, detect via create_menu presence
        # We rely on end_game calling create_menu -> entry will be missing then
        if not getattr(self, "entry", None) or not self.entry.winfo_exists():
            # game finished this round; record attempts (from self.attempts) or fail
            attempts = getattr(self, "attempts", None)
            if attempts is None:
                self.sim_results.append((s["diff_idx"], s["round_idx"], "fail"))
            else:
                self.sim_results.append((s["diff_idx"], s["round_idx"], attempts))
            # advance round index and start next
            s["round_idx"] += 1
            # small pause before next round
            self.root.after(200, self._sim_step_start_round)
            return

        # otherwise schedule next guess
        self.root.after(120, self._sim_step_make_guess)

    # ---------- cleanup helpers ----------
    def cancel_timer(self):
        self.timer_running = False
        if getattr(self, "timer_after_id", None):
            try:
                self.root.after_cancel(self.timer_after_id)
            except Exception:
                pass
            self.timer_after_id = None

    def cancel_auto_schedule(self):
        self.auto_test_running = False
        if getattr(self, "auto_after_id", None):
            try:
                self.root.after_cancel(self.auto_after_id)
            except Exception:
                pass
            self.auto_after_id = None

# Run
if __name__ == "__main__":
    root = tk.Tk()
    game = GuessingGame(root)
    root.mainloop()