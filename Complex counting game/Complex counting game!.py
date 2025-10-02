# ===============================
# Complex Number Guessing Game (GUI) - Final Version
# Features: difficulties, timer, detailed hints, local leaderboard (top 5),
# Auto-Test (GUI button), Debug (colored console output), cheat via 'p' key or entering 'p'.
# ===============================

import tkinter as tk
from tkinter import messagebox, simpledialog
import random
import time
import os
import json
import threading
from colorama import Fore, Style, init

# Try to import winsound for beep on Windows (optional)
try:
    import winsound
    WINSOUND_AVAILABLE = True
except Exception:
    WINSOUND_AVAILABLE = False

# Initialize colorama for colored debug output
init(autoreset=True)

# ===============================
# Debug Mode
# ===============================
DEBUG = "True"  # set "True" or "False" (as strings)

def debug_info(msg):
    if DEBUG == "True": print(Fore.BLUE + "[INFO] " + msg)
def debug_attempt(msg):
    if DEBUG == "True": print(Fore.YELLOW + "[ATTEMPT] " + msg)
def debug_hint(msg):
    if DEBUG == "True": print(Fore.GREEN + "[HINT] " + msg)
def debug_leaderboard(msg):
    if DEBUG == "True": print(Fore.MAGENTA + "[LEADERBOARD] " + msg)

# ===============================
# Leaderboard Settings
# ===============================
LEADERBOARD_FILE = "leaderboard.json"
MAX_LEADERBOARD = 5

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE, "r") as f:
                board = json.load(f)
                debug_leaderboard(f"Loaded leaderboard: {board}")
                return board
        except:
            debug_leaderboard("Leaderboard file corrupted, starting fresh.")
            return []
    debug_leaderboard("Leaderboard file not found, starting fresh.")
    return []

def save_leaderboard(board):
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(board, f, indent=2)
    debug_leaderboard(f"Saved leaderboard: {board}")

def update_leaderboard(name, score):
    board = load_leaderboard()
    board.append({"name": name, "score": score})
    board = sorted(board, key=lambda x: x["score"])[:MAX_LEADERBOARD]
    save_leaderboard(board)
    debug_leaderboard(f"Updated leaderboard with {name} - {score} attempts")
    return board

def leaderboard_str():
    board = load_leaderboard()
    text = "🏆 Leaderboard (Top 5)\n"
    for i, entry in enumerate(board, 1):
        text += f"{i}. {entry['name']} - {entry['score']} attempts\n"
    return text if board else "No scores yet."

# ===============================
# Utility Functions
# ===============================
def is_prime(n):
    if n < 2: return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0: return False
    return True

# ===============================
# Main Game Class
# ===============================
class GuessingGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Complex Number Guessing Game")
        # Bind keypress globally to detect 'p' cheat
        self.root.bind("<Key>", self._on_keypress)
        self.create_menu()

    # Keypress handler: if 'p' pressed => cheat win
    def _on_keypress(self, event):
        try:
            if event.char.lower() == 'p':
                debug_info("Keypress 'p' detected -> activating cheat.")
                self.cheat_win()
        except Exception:
            pass  # ignore any unexpected key events

    # Main menu: difficulty buttons + Auto-Test + leaderboard display
    def create_menu(self):
        self.clear()
        tk.Label(self.root, text="Select Difficulty", font=("Arial", 14)).pack(pady=10)
        tk.Button(self.root, text="Easy (1-50)", command=lambda: self.start(1)).pack(pady=5)
        tk.Button(self.root, text="Medium (1-500)", command=lambda: self.start(2)).pack(pady=5)
        tk.Button(self.root, text="Hard (1-1000)", command=lambda: self.start(3)).pack(pady=5)
        tk.Button(self.root, text="Auto-Test", command=self.run_auto_test).pack(pady=5)
        tk.Label(self.root, text=leaderboard_str(), font=("Arial", 12), justify="left").pack(pady=10)

    # Start game with chosen difficulty
    def start(self, difficulty):
        if difficulty == 1:
            self.min_num, self.max_num, self.max_attempts, self.timer = 1, 50, 12, 120
        elif difficulty == 2:
            self.min_num, self.max_num, self.max_attempts, self.timer = 1, 500, 8, 180
        else:
            self.min_num, self.max_num, self.max_attempts, self.timer = 1, 1000, 6, 300

        self.number = random.randint(self.min_num, self.max_num)
        debug_info(f"Number to guess: {self.number}")

        self.attempts = 0
        self.guesses = []
        self.start_time = time.time()
        self._cheat_ended = False  # reset cheat flag

        self.clear()
        self.status = tk.Label(self.root, text=f"Guess a number between {self.min_num} and {self.max_num}", font=("Arial", 12))
        self.status.pack(pady=10)
        self.entry = tk.Entry(self.root, font=("Arial", 12))
        self.entry.pack(pady=5)
        tk.Button(self.root, text="Submit", command=self.check_guess).pack(pady=5)
        # Optional visible cheat button (commented out by default)
        # tk.Button(self.root, text="Cheat (P)", command=self.cheat_win).pack(pady=5)
        self.info = tk.Label(self.root, text="", font=("Arial", 11))
        self.info.pack(pady=10)
        self.timer_label = tk.Label(self.root, text="", font=("Arial", 12), fg="blue")
        self.timer_label.pack(pady=10)
        self.update_timer()

    # Timer update function
    def update_timer(self):
        elapsed = int(time.time() - self.start_time)
        remaining = self.timer - elapsed
        debug_info(f"Timer update - remaining: {remaining}s")
        if remaining <= 0:
            self.end_game(False, "Time's up!")
            return
        self.timer_label.config(text=f"⏳ Time left: {remaining//60}:{remaining%60:02d}")
        self.root.after(1000, self.update_timer)

    # Generate detailed hints
    def give_hint(self):
        hints = []
        if self.number % 2 == 0: hints.append("even")
        else: hints.append("odd")
        if self.number % 3 == 0: hints.append("divisible by 3")
        if self.number % 5 == 0: hints.append("divisible by 5")
        if is_prime(self.number): hints.append("prime number")

        mid = (self.min_num + self.max_num) // 2
        quarter1 = self.min_num + (self.max_num - self.min_num) // 4
        quarter3 = self.min_num + 3*(self.max_num - self.min_num) // 4
        if self.number <= quarter1: hints.append("in first quarter")
        elif self.number <= mid: hints.append("in second quarter")
        elif self.number <= quarter3: hints.append("in third quarter")
        else: hints.append("in fourth quarter")

        if self.number % 10 == 0: hints.append("multiple of 10")
        elif self.number % 10 <= 2: hints.append("close to lower multiple of 10")
        elif self.number % 10 >= 8: hints.append("close to higher multiple of 10")

        if abs(self.number - mid) <= (self.max_num - self.min_num)//20:
            hints.append("very close to mid of range")

        debug_hint(f"Hints for {self.number}: {hints}")
        return hints

    # Check player's guess (Submit)
    def check_guess(self):
        guess_str = self.entry.get()
        # Cheat by entering 'p' in the entry box
        if isinstance(guess_str, str) and guess_str.strip().lower() == 'p':
            debug_info("Entry 'p' detected -> activating cheat via entry.")
            self.cheat_win()
            return

        if not guess_str.isdigit():
            messagebox.showerror("Error", "Enter a valid number")
            return

        guess = int(guess_str)
        self.guesses.append(guess)
        self.attempts += 1
        debug_attempt(f"Attempt {self.attempts}: Player guessed {guess}")

        if guess == self.number:
            name = "AutoTester" if DEBUG == "True" else simpledialog.askstring("Name", "Enter your name for the leaderboard:")
            if name:
                update_leaderboard(name, self.attempts)
            self.end_game(True, f"Correct! You guessed in {self.attempts} attempts.")
            return

        if self.attempts >= self.max_attempts:
            self.end_game(False, "Out of attempts!")
            return

        diff = abs(guess - self.number)
        if diff <= 2: feedback = "🔥 Boiling hot!"
        elif diff <= 5: feedback = "Very hot!"
        elif diff <= 10: feedback = "Hot!"
        elif diff <= 20: feedback = "Warm."
        else: feedback = "Cold."
        feedback += " Too low!" if guess < self.number else " Too high!"

        hints = ", ".join(self.give_hint())
        self.info.config(text=f"{feedback}\nHint: {hints}")
        self.entry.delete(0, tk.END)

    # Cheat win: reveal number and end game as win (does NOT update leaderboard)
    def cheat_win(self):
        try:
            if WINSOUND_AVAILABLE:
                winsound.Beep(1000, 500)
        except Exception:
            pass
        messagebox.showinfo("Cheat activated!", f"Cheat activated! You win!\nThe number was {self.number}.")
        debug_info(f"Cheat activated: number was {self.number}. Ending round as win (no leaderboard update).")
        self._cheat_ended = True
        self.end_game(True, f"Cheat activated! The number was {self.number}.")

    # End game: show result and leaderboard; cheat path does not double-add score
    def end_game(self, win, msg):
        # If cheat triggered, prevent asking for name / double-update
        cheat_flag = getattr(self, "_cheat_ended", False)
        if cheat_flag:
            self._cheat_ended = False

        self.clear()
        if win:
            tk.Label(self.root, text="🎉 You Win!", font=("Arial", 16), fg="green").pack(pady=10)
        else:
            tk.Label(self.root, text="❌ Game Over!", font=("Arial", 16), fg="red").pack(pady=10)

        tk.Label(self.root, text=f"{msg}\nThe number was {self.number}", font=("Arial", 12)).pack(pady=10)
        tk.Label(self.root, text=leaderboard_str(), font=("Arial", 12), justify="left").pack(pady=10)
        tk.Button(self.root, text="Play Again", command=self.create_menu).pack(pady=5)
        tk.Button(self.root, text="Exit", command=self.root.quit).pack(pady=5)

    # Clear all widgets helper
    def clear(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    # Auto-Test: runs in separate thread so GUI doesn't freeze
    def run_auto_test(self):
        threading.Thread(target=self.auto_test_thread, daemon=True).start()

    def auto_test_thread(self):
        difficulties = [1,2,3]
        for diff in difficulties:
            debug_info(f"Auto-Test: Starting difficulty {diff}")
            self.start(diff)
            number = self.number
            guesses = [self.min_num, self.max_num, (self.min_num+self.max_num)//2, number]
            for g in guesses:
                self.entry.delete(0, tk.END)
                self.entry.insert(0, str(g))
                self.check_guess()
                time.sleep(0.5)
            time.sleep(1)
        debug_info("Auto-Test Completed.")

# ===============================
# Run Game
# ===============================
if __name__ == "__main__":
    root = tk.Tk()
    game = GuessingGame(root)
    root.mainloop()