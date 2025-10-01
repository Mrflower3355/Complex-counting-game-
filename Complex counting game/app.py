# welcome to the complex number guessing game!
# This version includes multiple difficulty levels, a timer, a hint system, and a high score tracker.
# credits to github AI for helping me code this.
import os
import winsound
import random
import time
# Initial game settings
number_to_guess = random.randint(1, 100)
max_attempts = 10
attempts = 0

print("Welcome to the Complex Number Guessing Game!")
print(
    f"You have {max_attempts} attempts and 2 minutes to guess the number between 1 and 100.")

start_time = time.time()
# Function to check if a number is prime


def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True
# Function to get hot/cold feedback


def get_hot_cold(guess, target):
    diff = abs(guess - target)
    if diff == 0:
        return "Correct!"
    elif diff <= 2:
        return "Boiling hot!"
    elif diff <= 5:
        return "Very hot!"
    elif diff <= 10:
        return "Hot!"
    elif diff <= 20:
        return "Warm."
    else:
        return "Cold."
# Load and save high score


def load_high_score():
    if os.path.exists("highscore.txt"):
        with open("highscore.txt", "r") as f:
            try:
                return int(f.read().strip())
            except:
                return None
    return None

# Save high score


def save_high_score(score):
    with open("highscore.txt", "w") as f:
        f.write(str(score))
# Main game loop


def main():
    print("Welcome to the Complex Number Guessing Game!")
    print("Select difficulty: 1) Easy 2) Medium 3) Hard")
    diff = input("Enter choice (1/2/3): ").strip()
    if diff == '1':
        min_num, max_num, max_attempts, timer = 1, 50, 12, 120
    elif diff == '2':
        min_num, max_num, max_attempts, timer = 1, 100, 10, 120
    else:
        min_num, max_num, max_attempts, timer = 1, 500, 7, 180

    custom = input(
        f"Do you want to set a custom range? (y/n): ").strip().lower()
    if custom == 'y':
        try:
            min_num = int(input("Enter minimum number: "))
            max_num = int(input("Enter maximum number: "))
        except ValueError:
            print("Invalid input, using default range.")
# Start game
    number_to_guess = random.randint(min_num, max_num)
    attempts = 0
    time_penalty = 0
    guesses = []
    start_time = time.time()
    high_score = load_high_score()
    print(
        f"You have {max_attempts} attempts and {timer//60} minutes to guess the number between {min_num} and {max_num}.")
    print(
        f"Current high score (fewest attempts): {high_score if high_score else 'None'}")
# Cheat code
    while attempts < max_attempts:
        elapsed_time = time.time() - start_time + time_penalty
        remaining_time = max(0, timer - int(elapsed_time))
        if elapsed_time > timer:
            print(
                f"Time's up! You exceeded {timer//60} minutes. The number was {number_to_guess}.")
            winsound.Beep(400, 700)
            break
        print(f"Time left: {remaining_time} seconds.")
        user_input = input(
            f"Attempt {attempts + 1}/{max_attempts} - Enter your guess: ")
        if user_input.strip().upper() == 'P':
            print(
                f"Cheat activated! You win! The number was {number_to_guess}.")
            winsound.Beep(1000, 500)
            break
        try:
            guess = int(user_input)
        except ValueError:
            print("Please enter a valid integer.")
            continue
        guesses.append(guess)
        attempts += 1
        time_penalty += 10
        elapsed_time = time.time() - start_time + time_penalty
        if guess == number_to_guess:
            print(
                f"Congratulations! You guessed the number in {attempts} attempts and {int(elapsed_time)} seconds.")
            winsound.Beep(1000, 500)
            if not high_score or attempts < high_score:
                print("New high score!")
                save_high_score(attempts)
            break
        else:
            print(get_hot_cold(guess, number_to_guess))
            if guess < number_to_guess:
                print("Too low!")
            else:
                print("Too high!")
            # Hint system
            hint = []
            if number_to_guess % 2 == 0:
                hint.append("even")
            else:
                hint.append("odd")
            if number_to_guess % 3 == 0:
                hint.append("divisible by 3")
            if number_to_guess % 5 == 0:
                hint.append("divisible by 5")
            if is_prime(number_to_guess):
                hint.append("prime number")
            if number_to_guess <= (min_num + max_num)//2:
                hint.append(
                    f"in the lower half ({min_num}-{(min_num+max_num)//2})")
            else:
                hint.append(
                    f"in the upper half ({(min_num+max_num)//2+1}-{max_num})")
            print(f"Hint: The number is {', '.join(hint)}.")
# End of game
    if attempts == max_attempts and guess != number_to_guess:
        print(f"Game over! The number was {number_to_guess}.")
        winsound.Beep(400, 700)

    print("Your guesses:", guesses)
# Ask to play again
    replay = input("Do you want to play again? (y/n): ").strip().lower()
    if replay == 'y':
        main()
    else:
        print("Thank you for playing! Goodbye.")


# Start the game
if __name__ == "__main__":
    main()
