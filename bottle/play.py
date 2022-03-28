from functools import lru_cache
from hashlib import sha256
import ipdb
from collections import defaultdict
from enum import Enum, auto
from datetime import date
import json
import re
import string

import click
import requests

from .config import DAY_0

WIDE_CHAR_OFFSET = ord("ａ") - ord("a")
SOLVED = "🟩🟩🟩🟩🟩"
CONSONANTS = "bcdfghjklmnpwrstvwxyz"
solutions = None
dictionary = None


def widen_chars(s):
    return "".join(chr(ord(x) + WIDE_CHAR_OFFSET) for x in s)


class Failure(Exception):
    pass


@lru_cache()
def _load_words():
    global solutions
    global dictionary
    click.echo(f"Loading words from nytimes")
    # get the wordle HTML
    r = requests.get("https://www.nytimes.com/games/wordle/index.html")
    r.raise_for_status()
    m = re.search(r'<script src="(main\.\w+\.js)"></script>', r.text)

    # get the wordle JS
    url = f"https://www.nytimes.com/games/wordle/{m.group(1)}"
    r = requests.get(url)
    r.raise_for_status()

    # Look for the word list in the JS
    m = re.search(r'\["cigar","rebut","sissy","humph","awake",.+?\]', r.text)
    solutions = json.loads(m.group(0))
    # Look for the word list in the JS
    m = re.search(r'\["aahed",.+?\]', r.text)
    dictionary = sorted(set(solutions + json.loads(m.group(0))))


def get_today_number():
    return (date.today() - DAY_0).days


def get_todays_word(today_number: int = None):
    if today_number is None:
        today_number = get_today_number()
    click.echo(f"Loading Wordle #{today_number}")

    _load_words()
    return solutions[today_number]


class GameBot:
    """
    Plays the game, guessing words until it wins or loses.
    """

    # Tuned based on wordle #282 - increased until the puzzle passed :)
    # Since this is so high it means we'll basically always choose consonants over vowels
    # whenever possible.
    CONSONANT_BOOST = 1.0

    SHARE_EMOJI = [
        "😮👯‍♂️🎉",
        "🎉",
        "🤌",
        "😑",
        "😢",
        "😭",
        "😖",
    ]

    def __init__(
        self, number, *, cache_starting_words=True, debug_scores=False, share=False
    ):
        self.possible_words = dictionary[:]

        self.possible_chars = [
            set(string.ascii_lowercase),
            set(string.ascii_lowercase),
            set(string.ascii_lowercase),
            set(string.ascii_lowercase),
            set(string.ascii_lowercase),
        ]
        self.number = number
        self.required_chars = set()
        self.cache_starting_words = cache_starting_words
        self.debug_scores = debug_scores
        self.share = share
        self._refresh_frequencies()

        # character frequences overall (we don't recalculate this later)
        # This is so that we're more likely to choose words with popular letters rather
        # than really uncommon ones
        char_counts = defaultdict(int)
        for word in self.possible_words:
            for char in word:
                char_counts[char] += 1
        self._overall_char_weights = {
            char: (count / sum(char_counts.values()))
            for (char, count) in char_counts.items()
        }
        key = (
            self.__class__.__name__
            + sha256("\n".join(self.possible_words).encode()).hexdigest()
        )
        starting_words = {}
        try:
            with open("starting-words.json", "r") as f:
                if self.cache_starting_words:
                    starting_words = json.load(f)
                self.starting_word = starting_words[key]
        except (FileNotFoundError, KeyError):
            click.echo("starting word not found in cache; chonking splerticles")
            starting_words[key] = self.get_best_scoring_word(self.possible_words)
            if self.cache_starting_words:
                with open("starting-words.json", "w") as f:
                    f.write(json.dumps(starting_words, indent=4))
            self.starting_word = starting_words[key]

    def _refresh_frequencies(self):
        pass

    def _refresh_possible_words(self):
        self.possible_words[:] = [
            word for word in self.possible_words if self._is_possible(word)
        ]
        self._refresh_frequencies()

    def _is_possible(self, word, possible_chars=None):
        if not set(word).issuperset(self.required_chars):
            return False
        if possible_chars is None:
            possible_chars = self.possible_chars
        for char, possibles in zip(word, possible_chars):
            if char not in possibles:
                # word is impossible
                return False
        return True

    def _score_word(self, word):
        """
        Scores a word based on the assumption that all characters will be missing from the solution,
        and figures out how many of the dictionary words this word will rule out.
        The more words it rules out, the better this word scores.
        """
        # These are the chars that we'll assume will give us no match.
        chars_to_remove = set(word) - self.required_chars
        other_chars = [x - chars_to_remove for x in self.possible_chars]
        remaining_words = [
            other
            for other in self.possible_words
            if self._is_possible(other, possible_chars=other_chars)
        ]
        # The score is the *factor* by which this word reduces the problem space.
        try:
            score = len(self.possible_words) / len(remaining_words)
        except ZeroDivisionError:
            # If no words remain, that's sort of good; it means this word is very likely to be
            # the *only* remaining word (and hence is likely the solution!)
            # However, we don't use inf because it can't be affected by maths later.
            # so we use a high normal number instead
            score = 30.0

        # weight popular letters higher
        score *= sum(self._overall_char_weights[char] for char in word)

        # boost consonants. This helps avoid the bot getting trapped in hard-mode traps
        # where it has to keep guessing a single position, .e.g this one:
        #     Loading Wordle #283
        #     ＡＬＯＥＳ
        #     ⬜⬜🟨⬜⬜
        #     ＣＯＲＮＹ
        #     ⬜🟩⬜🟩⬜
        #     ＰＯＵＮＤ
        #     ⬜🟩🟩🟩🟩
        #     ＭＯＵＮＤ
        #     ⬜🟩🟩🟩🟩
        #     ＨＯＵＮＤ
        #     ⬜🟩🟩🟩🟩
        #     ＢＯＵＮＤ
        #     ⬜🟩🟩🟩🟩
        num_consonants = sum(
            self.CONSONANT_BOOST for char in word if char in CONSONANTS
        )
        score *= 1.0 + num_consonants**2
        return score

    def get_best_scoring_word(self, words):
        word_scores = [(self._score_word(word), word) for word in self.possible_words]
        word_scores.sort(reverse=True)
        if self.debug_scores:
            for score, word in word_scores:
                click.echo(f"            {word} -> {score:16.6f}")

        return word_scores[0][1]

    def share_output(self, guesses, feedbacks):
        solved = feedbacks[-1] == SOLVED
        n = len(guesses) if solved else "X"

        click.echo(f"Wordle #{self.number} {n}/6*\n")
        for guess, feedback in zip(guesses, feedbacks):
            if not self.share:
                click.echo(guess)
            click.echo(feedback)

        i = len(guesses) - 1 if solved else -1
        click.echo(self.SHARE_EMOJI[i])

    def __iter__(self):
        guesses = []
        feedbacks = []
        for i in range(6):
            if i == 0:
                # optimisation; starting word is cached in a file
                candidate = self.starting_word
            else:
                candidate = self.get_best_scoring_word(self.possible_words)
            feedback = yield candidate
            guesses.append(f"{widen_chars(candidate).upper()}")
            feedbacks.append(f"{feedback}")
            if feedback == SOLVED:
                self.share_output(guesses, feedbacks)
                return
            for char, f, pc_set in zip(candidate, feedback, self.possible_chars):
                if f == "⬜":
                    # this char can no longer be considered in any position
                    # EXCEPT if that position is already green
                    for x_feedback, x_possible in zip(feedback, self.possible_chars):
                        if x_feedback != "🟩":
                            x_possible.discard(char)
                elif f == "🟩":
                    # this char is now the only possible candidate for this position
                    pc_set.intersection_update({char})
                elif f == "🟨":
                    # this char can no longer be considered in this position
                    pc_set.discard(char)
                    # Also, future guesses must include this char
                    self.required_chars.add(char)
            self._refresh_possible_words()
        self.share_output(guesses, feedbacks)
        raise Failure


class WeightedScoreGameBot(GameBot):
    def _score_word(self, word):
        """
        Scores a word based on the 'simple' score, but also based on the frequency of letters
        at each position and thus their probability of getting a 🟩 or 🟨.
        """
        simple_score = super()._score_word(word)
        score_from_letter_frequency = 0.0
        for i, char in enumerate(word):
            freq = self._char_frequencies[i][char]
            score_from_letter_frequency += freq
        return simple_score * score_from_letter_frequency

    def _refresh_frequencies(self):
        char_counts = [
            defaultdict(int),
            defaultdict(int),
            defaultdict(int),
            defaultdict(int),
            defaultdict(int),
        ]
        for word in self.possible_words:
            for i, char in enumerate(word):
                char_counts[i][char] += 1

        # character frequencies *in each of the five positions*
        self._char_frequencies = [
            {char: (count / sum(d.values())) for (char, count) in d.items()}
            for d in char_counts
        ]
        if self.debug_scores:
            click.echo("letter frequencies:")
            for x in self._char_frequencies:
                for char, freq in sorted(x.items(), key=lambda item: -item[1]):
                    click.echo(f"\t{char}\t{freq:1.3f}")
                click.echo()


def play_game(bot, solution):
    bot_iter = iter(bot)
    word = next(bot_iter)
    guesses = 1
    try:
        while True:
            feedback = []
            nongreens_in_solution = {
                soln_char
                for i, (char, soln_char) in enumerate(zip(word, solution))
                if char != soln_char
            }
            for i, (char, soln_char) in enumerate(zip(word, solution)):
                if char == soln_char:
                    feedback.append("🟩")
                elif char not in solution:
                    feedback.append("⬜")
                else:
                    # Only give a 🟨 if we haven't already allocated a 🟩 for this char
                    if char in nongreens_in_solution:
                        feedback.append("🟨")
                    else:
                        feedback.append("⬜")
            word = bot_iter.send("".join(feedback))
            guesses += 1
    except StopIteration:
        return guesses, 1
    except Failure:
        return guesses, 0


@click.command()
@click.option(
    "--strategy",
    type=click.Choice(["weighted", "simple"]),
    default="simple",
)
@click.argument(
    "number",
    type=int,
    nargs=1,
    required=False,
    default=get_today_number(),
)
@click.option("--share", is_flag=True)
@click.pass_context
def play(ctx, strategy, number, share):
    try:
        solution = get_todays_word(number)

        bot_cls = GameBot if strategy == "simple" else WeightedScoreGameBot
        bot = bot_cls(number, share=share)
        play_game(bot, solution)
    except Exception:
        ipdb.post_mortem()


@click.command()
@click.option(
    "--strategy",
    type=click.Choice(["weighted", "simple"]),
    default="simple",
)
@click.argument(
    "number",
    type=int,
    nargs=1,
    required=False,
    default=get_today_number(),
)
@click.pass_context
def debug_scores(ctx, strategy, number):
    try:
        solution = get_todays_word(number)

        bot_cls = GameBot if strategy == "simple" else WeightedScoreGameBot
        bot = bot_cls(number, cache_starting_words=False, debug_scores=True)
        play_game(bot, solution)
    except Exception:
        ipdb.post_mortem()


@click.command()
@click.option(
    "--strategy",
    type=click.Choice(["weighted", "simple"]),
    default="simple",
)
@click.option(
    "-n", type=int, default=None, help="How many puzzles to do (default: all)"
)
@click.pass_context
def bulk(ctx, strategy, n):
    total_guesses = 0
    successes = 0
    if not n:
        n = get_today_number()
    try:
        for number in range(1, n + 1):
            solution = get_todays_word(number)

            bot_cls = GameBot if strategy == "simple" else WeightedScoreGameBot
            bot = bot_cls(number)
            guesses, success = play_game(bot, solution)
            total_guesses += guesses
            successes += success
        click.secho(
            f"Did {n} puzzles in {total_guesses} total guesses ({total_guesses/n:.1f} avg) "
            f"(successes={successes} ({successes/n * 100:.2f}%)",
            bold=True,
        )
    except Exception:
        ipdb.post_mortem()
