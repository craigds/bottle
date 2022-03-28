#!/usr/bin/env python3
from datetime import timedelta, date
import re

import click
import ipdb

from .config import DAY_0


class RE:
    _username = r"[ a-zA-Z.]+"
    _timestamp = r"\d?\d:\d\d [AP]M"
    post_start = re.compile(rf"^({_username})  {_timestamp}\s*$", re.M)
    game_start = re.compile(r"^Wordle (\d+) (\d|X)/6(\*?)\s*$")


NICEN = {
    ":white_large_square:": "⬜️",
    ":black_large_square:": "⬜️",
    ":large_yellow_square:": "🟨",
    ":large_green_square:": "🟩",
}


def nicen(line):
    for yuck, nice in NICEN.items():
        line = line.replace(yuck, nice)
    return line.strip()


class Game:
    def __init__(self, lines, username, number, hard_mode):
        self.lines = tuple(lines)
        self.username = username
        self.number = number
        self.date = DAY_0 + timedelta(days=number)
        self.solved = self.lines[-1] == "🟩🟩🟩🟩🟩"
        self.score = len(lines)
        self.hard_mode = hard_mode

    def __str__(self):
        u = click.style(self.username, fg="green", bold=True)
        d = (
            click.style("hard mode", fg="red", bold=True)
            if self.hard_mode
            else click.style("easy mode", fg="green", bold=True)
        )
        w = click.style(f"Wordle #{self.number} ({self.date})", fg="yellow", bold=True)
        return "\n".join(
            [
                click.style(f"{u} played {w} in {d}"),
                *self.lines,
                "\n",
            ]
        )


def read_game(
    input_file, username: str, number: int, num_lines: int, solved: bool, hard_mode
):
    lines = []
    while len(lines) < num_lines:
        line = input_file.readline().strip()
        if not line:
            continue
        lines.append(nicen(line))
    game = Game(lines, username, number, hard_mode)
    assert game.solved == solved
    assert game.score == num_lines
    return game


def find_games(input_file):
    last_username = None
    while True:
        line = input_file.readline()
        if not line:
            return
        if m := RE.post_start.match(line):
            # we're now in a post
            last_username = m.group(1)
        elif m := RE.game_start.match(line):
            # we're now in a game
            assert last_username
            game_number = int(m.group(1))
            if m.group(2) == "X":
                num_lines = 6
                solved = False
            else:
                num_lines = int(m.group(2))
                solved = True
            hard_mode = bool(m.group(3))
            yield read_game(
                input_file, last_username, game_number, num_lines, solved, hard_mode
            )


def game_sort_key(g):
    return g.number, g.hard_mode, g.username


@click.command()
@click.argument("input_file", type=click.File(mode="r"))
@click.pass_context
def parse(ctx, input_file):

    try:
        games = list(find_games(input_file))
        games.sort(key=game_sort_key)
        click.echo(f"loaded {len(games)} games")
        for game in games:
            print(game)
    except Exception:
        ipdb.post_mortem()
