# Complex Number Guessing Game - Patch 3.0.1 (Final Stable Release)
#
# --- CHANGE LOG 3.0.1 (Final Stability & Crash Fixes) ---
# - FIXED: Critical Race Condition Crash in timer cancellation (TclError/AttributeError)
#   by wrapping root.after_cancel in a try/except block in cancel_timer().
# - FIXED: TclError crash when inputs were disabled but the game ended prematurely.
#   Added winfo_exists() checks to update_timer() and disable_inputs_temporarily().
# - FIXED: Smart Solver state inconsistency crash. Solver now checks if the game 
#   ended immediately after check_guess() to prevent accessing null state.
# - IMPROVED: Solver radius logic refined with aggressive clamping to max_range * 1.5 
#   for more focused and faster auto-solving.
# - IMPROVED: Component hint logic simplified using math.trunc() for clearer 
#   integer conversion of complex number components.
# - IMPROVED: General state handling in end_game() for cleaner transition back to menu.

import json
import logging
import math
import os
import random
import time
import tkinter as tk
from tkinter import messagebox, simpledialog

# Optional winsound (Windows only)
try:
    import winsound
    WINSOUND_AVAILABLE = True
except ImportError:
    WINSOUND_AVAILABLE = False

# --- Constants and Configuration ---
DEBUG = False # Set to False for production stability
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO, format='[%(levelname)s] %(message)s')
log = logging.getLogger(__name__)

# App Storage
APP_DIR = os.path.join(os.path.expanduser("~"), ".complex_guess_game")
os.makedirs(APP_DIR, exist_ok=True)
LEADERBOARD_FILE = os.path.join(APP_DIR, "leaderboard.json")
MAX_LEADERBOARD = 5

# UI Timings
INPUT_DISABLE_MS = 200
AUTO_STEP_DELAY_MS = 250

# Difficulty Configuration
DIFFICULTY_SETTINGS = {
    1: {"range": 10, "attempts": 15, "timer": 120},  # Easy
    2: {"range": 50, "attempts": 10, "timer": 180},  # Medium
    3: {"range": 100, "attempts": 8, "timer": 300},  # Hard
}


# --- Helper Functions ---
def safe_load_leaderboard():
    if not os.path.exists(LEADERBOARD_FILE):
        return []
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        clean = [
            e for e in data
            if isinstance(e, dict) and 'name' in e and isinstance(e.get('score'), int)
        ]
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
    except Exception:
        log.exception("Failed to save leaderboard.")

def update_leaderboard(name, score):
    board = safe_load_leaderboard()
    board.append({"name": str(name), "score": int(score)})
    board = sorted(board, key=lambda x: x["score"])[:MAX_LEADERBOARD]
    safe_save_leaderboard(board)
    log.debug(f"Updated leaderboard with {name} - {score} attempts")

def leaderboard_str():
    board = safe_load_leaderboard()
    if not board:
        return "No scores yet."
    text = "🏆 Leaderboard (Top 5)\n"
    for i, entry in enumerate(board, 1):
        text += f"{i}. {entry['name']} - {entry['score']} attempts\n"
    return text

def is_prime(n):
    n = abs(int(n))
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True


# --- Main Game Class ---
class GuessingGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Complex Number Guessing Game")

        # State flags
        self.solver_running = False
        self.timer_after_id = None
        self.auto_after_id = None
        self._cheat_ended = False
        self._auto_mode = False
        self.start_time = None

        self.root.bind_all("<Control-p>", self._on_ctrl_p)
        self.create_menu()

    def _on_ctrl_p(self, event=None):
        if hasattr(self, "target_number"):
            log.info("Ctrl+P detected -> activating cheat.")
            self.cheat_win()

    def clear(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def create_menu(self):
        self.clear()
        tk.Label(self.root, text="Select Difficulty", font=("Arial", 16, "bold")).pack(pady=10)
        tk.Button(self.root, text="Easy (±10)", width=25, command=lambda: self.start(1)).pack(pady=5)
        tk.Button(self.root, text="Medium (±50)", width=25, command=lambda: self.start(2)).pack(pady=5)
        tk.Button(self.root, text="Hard (±100)", width=25, command=lambda: self.start(3)).pack(pady=5)
        tk.Button(self.root, text="Run Smart Solver (Easy)", width=25, command=self.run_smart_solver).pack(pady=20)
        tk.Label(self.root, text=leaderboard_str(), font=("Arial", 12), justify="left").pack(pady=10)

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

    def start(self, difficulty, stop_auto=True):
        self._cheat_ended = False
        if stop_auto:
            self.stop_all_auto_tasks()

        config = DIFFICULTY_SETTINGS[difficulty]
        self.max_range = config["range"]
        self.max_attempts = config["attempts"]
        self.timer = config["timer"]

        real_part = random.randint(-self.max_range, self.max_range)
        imag_part = random.randint(-self.max_range, self.max_range)
        self.target_number = complex(real_part, imag_part)
        self.target_magnitude = abs(self.target_number)
        log.debug(f"Target number to guess: {self.target_number}")

        self.attempts = 0
        self.start_time = time.time()

        self.setup_game_ui()
        self.update_timer()

    def setup_game_ui(self):
        self.clear()
        range_str = f"Guess a complex number (a + bi) where 'a' and 'b' are between {-self.max_range} and {self.max_range}"
        tk.Label(self.root, text=range_str, font=("Arial", 12), wraplength=380).pack(pady=10)

        input_frame = tk.Frame(self.root)
        input_frame.pack(pady=5)
        tk.Label(input_frame, text="Real (a):", font=("Arial", 12)).pack(side="left", padx=5)
        self.entry_real = tk.Entry(input_frame, font=("Arial", 12), width=8)
        self.entry_real.pack(side="left")
        tk.Label(input_frame, text="Imaginary (b):", font=("Arial", 12)).pack(side="left", padx=5)
        self.entry_imag = tk.Entry(input_frame, font=("Arial", 12), width=8)
        self.entry_imag.pack(side="left")

        self.entry_real.bind("<Return>", lambda e: self.check_guess())
        self.entry_imag.bind("<Return>", lambda e: self.check_guess())
        self.entry_real.focus_set()

        self.submit_btn = tk.Button(self.root, text="Submit Guess", command=self.check_guess)
        self.submit_btn.pack(pady=10)

        self.info_label = tk.Label(self.root, text="", font=("Arial", 11), justify="center")
        self.info_label.pack(pady=10)
        self.timer_label = tk.Label(self.root, text="", font=("Arial", 12), fg="blue")
        self.timer_label.pack(pady=10)

    def update_timer(self):
        if not self.start_time: return
        elapsed = int(time.time() - self.start_time)
        remaining = self.timer - elapsed
        
        # FIXED: TclError crash on rapid UI destruction
        if self.timer_label.winfo_exists():
            self.timer_label.config(text=f"⏳ Time left: {max(0, remaining)//60}:{max(0, remaining)%60:02d}")
        else:
            self.cancel_timer()
            return

        if remaining <= 0:
            self.end_game(False, f"Time's up! The number was {self.target_number}")
            return
        self.timer_after_id = self.root.after(1000, self.update_timer)

    def check_guess(self):
        try:
            real = int(self.entry_real.get().strip())
            imag = int(self.entry_imag.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid integers for both real and imaginary parts.")
            return

        self.attempts += 1
        guess = complex(real, imag)
        log.debug(f"Attempt {self.attempts}: {guess}")
        self.disable_inputs_temporarily()

        if guess == self.target_number:
            name_to_save = None
            if not DEBUG and not self._auto_mode and not self._cheat_ended:
                name_to_save = simpledialog.askstring("You Won!", "Enter your name for the leaderboard:")
                if name_to_save:
                    update_leaderboard(name_to_save, self.attempts)
            self.end_game(True, f"Correct! You guessed {self.target_number} in {self.attempts} attempts.")
            return

        guess_magnitude = abs(guess)
        if guess_magnitude < self.target_magnitude:
            magnitude_hint = "Magnitude is TOO LOW."
        else:
            magnitude_hint = "Magnitude is TOO HIGH."
        
        hints = self.give_component_hints()
        full_hint = magnitude_hint + "\n" + hints
        
        # FIXED: TclError crash on rapid UI destruction
        if self.info_label.winfo_exists():
            self.info_label.config(text=full_hint)

        if self.attempts >= self.max_attempts:
            self.end_game(False, f"Out of attempts! The number was {self.target_number}")

    def give_component_hints(self):
        if self.attempts % 2 != 0:
            return ""
        # IMPROVED: Use math.trunc for cleaner integer conversion
        tr = math.trunc(self.target_number.real)
        ti = math.trunc(self.target_number.imag)
        hints = []
        if tr % 2 == 0:
            hints.append("Real part is even")
        else:
            hints.append("Real part is odd")
        if is_prime(ti):
            hints.append("Imaginary part is prime")
        return "Hint: " + ", ".join(hints)

    def end_game(self, win, msg):
        self.cancel_timer()
        if win:
            if WINSOUND_AVAILABLE: winsound.MessageBeep(winsound.MB_ICONINFORMATION)
            messagebox.showinfo("Victory!", msg)
        else:
            messagebox.showerror("Game Over", msg)
            
        # IMPROVED: Ensure auto flags and tasks are fully stopped before menu creation
        self.stop_all_auto_tasks() 
        self.root.after(200, self.create_menu)

    def cheat_win(self):
        self._cheat_ended = True
        messagebox.showinfo("Cheat Activated", f"The number was {self.target_number}.")
        self.end_game(False, f"Cheat used. The number was {self.target_number}")

    def disable_inputs_temporarily(self):
        # FIXED: TclError crash on rapid UI destruction
        if self.submit_btn.winfo_exists():
            self.submit_btn.config(state="disabled")
            
            def enable_inputs():
                if self.submit_btn.winfo_exists():
                    self.submit_btn.config(state="normal")
                    
            self.root.after(INPUT_DISABLE_MS, enable_inputs)

    def cancel_timer(self):
        if self.timer_after_id:
            # FIXED: Critical Race Condition Crash (TclError/AttributeError)
            try:
                self.root.after_cancel(self.timer_after_id)
            except Exception:
                pass
            self.timer_after_id = None
        self.start_time = None

    # ---------- Smart Solver ----------
    def run_smart_solver(self):
        if self.solver_running:
            messagebox.showwarning("Busy", "The Smart Solver is already running.")
            return
        self._auto_mode = True
        self.start(1, stop_auto=False)
        self.solver_running = True
        self.solver_state = {"last_mag_diff": float('inf'), "current_radius": self.max_range}
        self.root.after(AUTO_STEP_DELAY_MS, self._solver_step)

    def _solver_step(self):
        if not self.solver_running:
            return
            
        if self.attempts >= self.max_attempts:
            self.end_game(False, f"Smart Solver failed in {self.max_attempts} attempts. The number was {self.target_number}")
            return
            
        if not hasattr(self, 'entry_real') or not self.entry_real.winfo_exists():
            self.solver_running = False
            return

        radius = self.solver_state["current_radius"]
        search_limit = math.ceil(radius) 
        guess_real = random.randint(-search_limit, search_limit)
        guess_imag = random.randint(-search_limit, search_limit)

        self.entry_real.delete(0, tk.END)
        self.entry_real.insert(0, str(guess_real))
        self.entry_imag.delete(0, tk.END)
        self.entry_imag.insert(0, str(guess_imag))
        
        self.check_guess()
        
        # FIXED: Smart Solver state inconsistency crash (ensuring stop if game ended)
        if not self.solver_running:
            return

        guess_mag = abs(complex(guess_real, guess_imag))
        mag_diff = abs(guess_mag - self.target_magnitude)
        
        # IMPROVED: Heuristic update for search radius (more aggressive bounds)
        if guess_mag > self.target_magnitude:
            self.solver_state["current_radius"] = (self.target_magnitude + guess_mag) / 2.1
        
        if mag_diff < self.solver_state["last_mag_diff"]:
            self.solver_state["current_radius"] *= 0.98 
        else:
            self.solver_state["current_radius"] *= 1.1   
            
        # IMPROVED: Clamp radius to a sensible range
        self.solver_state["current_radius"] = min(self.max_range * 1.5, max(1.0, self.solver_state["current_radius"])) 

        self.solver_state["last_mag_diff"] = mag_diff

        if self.solver_running:
            self.auto_after_id = self.root.after(AUTO_STEP_DELAY_MS, self._solver_step)


# --- Run Application ---
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("400x500")
    game = GuessingGame(root)
    root.mainloop()
