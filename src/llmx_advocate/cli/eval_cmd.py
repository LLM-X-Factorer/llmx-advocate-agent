import click


@click.group(help="Evaluation commands — A/B compare across model × opening_style.")
def eval_group() -> None:
    pass


@eval_group.command("compare")
@click.argument("task_a_id")
@click.argument("task_b_id")
def eval_compare(task_a_id, task_b_id) -> None:
    click.echo(f"[stub] eval compare {task_a_id} vs {task_b_id}")


@eval_group.command("batch")
@click.option("--source", required=True)
@click.option("--models", required=True, help="Comma-separated model list.")
@click.option("--opening-styles", default="auto", help="Comma-separated styles.")
def eval_batch(source, models, opening_styles) -> None:
    click.echo(f"[stub] eval batch source={source} models={models} styles={opening_styles}")
