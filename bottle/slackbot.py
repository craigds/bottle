from datetime import timedelta
import json
import os
import re
from functools import lru_cache

import click
import yaml
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler


from .config import DAY_0
from .play import get_todays_word, get_today_number, GameBot, LosingGameBot, play_game

try:
    with open("env.yaml") as f:
        os.environ.update(yaml.safe_load(f))
except FileNotFoundError:
    pass

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))


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


@lru_cache()
def get_username(user_id):
    return app.client.users_info(user=user_id).data["user"]["name"]


@app.message(re.compile(r"Wordle #(\d+) (\d|X)/6(\*)?"))
def on_user_played_wordle(message, say, context):
    username = get_username(message["user"])

    m = context["matches"]
    number = int(m[0])
    solved = m[1] != "X"
    num_lines = int(m[1]) if solved else 6
    hard_mode = bool(m[2])

    lines = [nicen(line) for line in message["text"].splitlines()]
    lines = [line for line in lines if line]

    for i, line in enumerate(lines):
        if line.startswith("Wordle #"):
            break
    else:
        # bad parse
        return
    lines = lines[i + 1 : i + num_lines + 1]
    if len(lines) != num_lines:
        # bad parse
        return

    game = Game(lines, username, number, hard_mode)
    assert game.solved == solved
    assert game.score == num_lines
    print(game)


def _mentions_me(block_or_element, bot_user_id):
    # Because these nested block things suck.
    if (
        block_or_element.get("type") == "user"
        and block_or_element.get("user_id") == bot_user_id
    ):
        return True
    children = block_or_element.get("elements") or []
    children += block_or_element.get("blocks") or []
    return any(_mentions_me(child, bot_user_id) for child in children)


def mentions_me(message, context):
    """
    Returns True iff the message mentions the bottle bot.
    """
    return _mentions_me(message, context["bot_user_id"])


def populate_message_history(channel_id):
    history = {}
    newest_ts = 0.0
    try:
        with open("channel-history.json", "r") as f:
            history = json.load(f)
    except FileNotFoundError:
        pass
    messages = history.setdefault(channel_id, [])
    if messages:
        newest_ts = float(messages[0]["ts"])
    resp = app.client.conversations_history(
        channel=channel_id, oldest=str(newest_ts + 0.000001)
    )
    messages += resp["messages"]
    while resp.data["has_more"]:
        messages += resp["messages"]
        resp = app.client.conversations_history(
            channel=channel_id,
            oldest=str(newest_ts + 0.000001),
            cursor=resp.data["response_metadata"]["next_cursor"],
        )
    messages.sort(key=lambda m: -float(m["ts"]))
    with open("channel-history.json", "w") as f:
        json.dump(history, f)
    return history[channel_id]


# TODO: auto play at 4pm.
@app.message(re.compile(rf"play(?:\s+(badly|well|better))?"))
def on_play_command(message, say, context):
    if not mentions_me(message, context):
        return
    quality = context["matches"][0]
    if quality == "badly":
        say("I'll do my ~best~ worst!")
        cls = LosingGameBot
        use_solutions_list = False
    else:
        cls = GameBot
        use_solutions_list = quality in ("well", "better")

    number = get_today_number()
    solution = get_todays_word(number)

    # channel_id = context['channel_id']
    channel_id = "C02UCSYFH3L"  # #wordle channel
    populate_message_history(channel_id)

    bot = cls(number, share=True, use_solutions_list=use_solutions_list)
    play_game(bot, solution)
    say("\n".join(bot.output))


@click.command()
@click.pass_context
def slackbot(ctx):
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
