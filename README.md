# Complex Number Guessing Game

![Python](https://img.shields.io/badge/Python-3.x-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Cross--Platform-orange)
---

## Features

- **Multiple Difficulty Levels**  
  - Easy: 1–50, 12 attempts, 2 minutes  
  - Medium: 1–500, 8 attempts, 3 minutes  
  - Hard: 1–1000, 6 attempts, 5 minutes  

- **Hints System**  
  - Even/Odd, divisible by 3/5, prime  
  - Quarter ranges (first/second/third/fourth)  
  - Multiple of 10 or near multiples  
  - Close to midpoint of range  

- **Timer** with automatic game over  
- **Leaderboard (Top 5)** stored locally in `leaderboard.json`  
- **Cheat System**: press `p` key or enter `'p'` to win instantly  
- **GUI** using Tkinter with Play Again / Exit buttons  
- **Debug Mode** (`DEBUG = "True"`) shows internal states  
- **Auto-Test Mode** for automated gameplay testing  
- **Cross-platform**: Windows, macOS, Linux (optional sound on Windows)

---
### Changelogs are in the code
### finally a stable version 3.0.1

## How to Play

1. Run `Complex Counting_game.py` in Python 3.x  
2. Choose a difficulty or custom range  
3. Enter guesses in the input box  
4. Use hints to narrow the number  
5. Press `p` to activate cheat and win  
6. Try to guess in the fewest attempts to appear on the leaderboard  

---

## Requirements

- Python 3.x  
- Tkinter (usually included with Python)  
- colorama (`pip install colorama`)  
- Visual Studio Code (recommended)

---

## Notes

- Fully offline, no internet needed  
- Future updates may enhance hints, GUI, and leaderboard
