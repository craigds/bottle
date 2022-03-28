import click

from . import play, parse


@click.group()
def main():
    ...


main.add_command(parse.parse)
main.add_command(play.play)
main.add_command(play.bulk)
main.add_command(play.debug_scores, name="debug-scores")
