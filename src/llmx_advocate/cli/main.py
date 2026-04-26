import click

from llmx_advocate import __version__
from llmx_advocate.cli.eval_cmd import eval_group
from llmx_advocate.cli.task_cmd import task_group


@click.group(help="llmx-advocate-agent CLI — talks to the API.")
@click.version_option(version=__version__, prog_name="llmx")
def cli() -> None:
    pass


cli.add_command(task_group, name="task")
cli.add_command(eval_group, name="eval")


if __name__ == "__main__":
    cli()
