# ===============================
# Complex Number Guessing Game - Patch 2.2.1
# ===============================
# Changelog:
# 2.2 (Base)
#   - Improved hints system
#   - Debug mode added
#   - Cheat code 'P' implemented
#   - Improved leaderboard (local file)
#
# 2.2.1 (Current Patch)
#   - Robust leaderboard (handles corrupt/missing files)
#   - Safety check for custom range (min < max)
#   - Hints progressive (details every 2 attempts)
#   - Winsound optional (prevents crash on non-Windows)
#   - Cheat 'P' does not update leaderboard
#   - Reset variables on new game
#   - Time/attempt safeguards
#   - Auto-Test thread safe
# ===============================

import tkinter as tk
from tkinter import messagebox, simpledialog
import random
import time
import os
import json
import threading
from colorama import Fore, Style, init

# Optional winsound
try:
    import winsound
    WINSOUND_AVAILABLE = True
except Exception:
    WINSOUND_AVAILABLE = False

# Initialize colorama
init(autoreset=True)

# Debug mode ("True"/"False")
DEBUG = "True"

def debug_info(msg):
    if DEBUG == "True": print(Fore.BLUE + "[INFO] " + msg)
def debug_attempt(msg):
    if DEBUG == "True": print(Fore.YELLOW + "[ATTEMPT] " + msg)
def debug_hint(msg):
    if DEBUG == "True": print(Fore.GREEN + "[HINT] " + msg)
def debug_leaderboard(msg):
    if DEBUG == "True": print(Fore.MAGENTA + "[LEADERBOARD] " + msg)

# Leaderboard
LEADERBOARD_FILE = "leaderboard.json"
MAX_LEADERBOARD = 5

def safe_load_leaderboard():
    if not os.path.exists(LEADERBOARD_FILE):
        debug_leaderboard("Leaderboard file not found, starting fresh.")
        return []
    try:
        with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                debug_leaderboard("Leaderboard file invalid, resetting.")
                return []
            clean = []
            for e in data:
                if isinstance(e, dict) and 'name' in e and 'score' in e:
                    try:
                        score = int(e['score'])
                        clean.append({'name': str(e['name']), 'score': score})
                    except: continue
            debug_leaderboard(f"Loaded leaderboard: {clean}")
            return clean
    except Exception as ex:
        debug_leaderboard(f"Error reading leaderboard: {ex}")
        return []

def safe_save_leaderboard(board):
    try:
        tmp = LEADERBOARD_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(board, f, indent=2, ensure_ascii=False)
        os.replace(tmp, LEADERBOARD_FILE)
        debug_leaderboard(f"Saved leaderboard: {board}")
    except Exception as ex:
        debug_leaderboard(f"Failed to save leaderboard: {ex}")

def update_leaderboard(name, score):
    board = safe_load_leaderboard()
    board.append({"name": str(name), "score": int(score)})
    board = sorted(board, key=lambda x: x["score"])[:MAX_LEADERBOARD]
    safe_save_leaderboard(board)
    debug_leaderboard(f"Updated leaderboard with {name} - {score} attempts")
    return board

def leaderboard_str():
    board = safe_load_leaderboard()
    if not board:
        return "No scores yet."
    text = "🏆 Leaderboard (Top 5)\n"
    for i, entry in enumerate(board, 1):
        text += f"{i}. {entry['name']} - {entry['score']} attempts\n"
    return text

# Utility
def is_prime(n):
    if n < 2: return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0: return False
    return True

# Main Game Class
class GuessingGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Complex Number Guessing Game")
        self.root.bind("<Key>", self._on_keypress)
        self.auto_test_running = False
        self.create_menu()

    def _on_keypress(self, event):
        try:
            if getattr(event, "char", "").lower() == 'p':
                debug_info("Keypress 'p' detected -> activating cheat.")
                if hasattr(self, "number"):
                    self.cheat_win()
        except Exception: pass

    def create_menu(self):
        self.clear()
        tk.Label(self.root, text="Select Difficulty", font=("Arial", 14)).pack(pady=10)
        tk.Button(self.root, text="Easy (1-50)", command=lambda: self.start(1)).pack(pady=5)
        tk.Button(self.root, text="Medium (1-500)", command=lambda: self.start(2)).pack(pady=5)
        tk.Button(self.root, text="Hard (1-1000)", command=lambda: self.start(3)).pack(pady=5)
        tk.Button(self.root, text="Auto-Test", command=self.run_auto_test).pack(pady=5)
        tk.Label(self.root, text=leaderboard_str(), font=("Arial", 12), justify="left").pack(pady=10)

    def start(self, difficulty):
        if difficulty == 1: self.min_num, self.max_num, self.max_attempts, self.timer = 1, 50, 12, 120
        elif difficulty == 2: self.min_num, self.max_num, self.max_attempts, self.timer = 1, 500, 8, 180
        else: self.min_num, self.max_num, self.max_attempts, self.timer = 1, 1000, 6, 300

        if self.min_num >= self.max_num: self.max_num = self.min_num + 50
        self.number = random.randint(self.min_num, self.max_num)
        debug_info(f"Number to guess: {self.number}")
        self.attempts = 0
        self.guesses = []
        self.start_time = time.time()
        self._cheat_ended = False

        self.clear()
        self.status = tk.Label(self.root, text=f"Guess a number between {self.min_num} and {self.max_num}", font=("Arial", 12))
        self.status.pack(pady=10)
        self.entry = tk.Entry(self.root, font=("Arial", 12))
        self.entry.pack(pady=5)
        tk.Button(self.root, text="Submit", command=self.check_guess).pack(pady=5)
        self.info = tk.Label(self.root, text="", font=("Arial", 11))
        self.info.pack(pady=10)
        self.timer_label = tk.Label(self.root, text="", font=("Arial", 12), fg="blue")
        self.timer_label.pack(pady=10)
        self.update_timer()

    def update_timer(self):
        elapsed = int(time.time() - self.start_time)
        remaining = self.timer - elapsed
        debug_info(f"Timer update - remaining: {remaining}s")
        if remaining <= 0: self.end_game(False, "Time's up!"); return
        try: self.timer_label.config(text=f"⏳ Time left: {remaining//60}:{remaining%60:02d}")
        except Exception: pass
        self.root.after(1000, self.update_timer)

    def give_hint(self):
        hints = []
        try:
            hints.append("even" if self.number % 2 == 0 else "odd")
            if self.attempts > 0 and self.attempts % 2 == 0:
                if self.number % 3 == 0: hints.append("divisible by 3")
                if self.number % 5 == 0: hints.append("divisible by 5")
                if is_prime(self.number): hints.append("prime number")
        except Exception: pass
        debug_hint(f"Hints: {hints}")
        return hints

    def check_guess(self):
        guess_str = self.entry.get()
        if guess_str.strip().lower() == 'p': self.cheat_win(); return
        if not guess_str.isdigit(): messagebox.showerror("Error", "Enter a valid number"); return
        guess = int(guess_str)
        if guess < self.min_num or guess > self.max_num:
            messagebox.showwarning("Out of range", f"Enter between {self.min_num}-{self.max_num}."); return

        self.guesses.append(guess)
        self.attempts += 1
        debug_attempt(f"Attempt {self.attempts}: {guess}")

        if guess == self.number:
            if DEBUG == "True": name = "AutoTester"
            else: name = simpledialog.askstring("Name", "Enter your name for leaderboard:")
            if name and not getattr(self, "_cheat_ended", False): update_leaderboard(name, self.attempts)
            self.end_game(True, f"Correct! Guessed in {self.attempts} attempts."); return

        if