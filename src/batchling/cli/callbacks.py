from pathlib import Path

import typer

from batchling.cli.enums import OrderByFields


def order_by_callback(ctx: typer.Context, value: str):
    if ctx.resilient_parsing:
        return
    if value not in OrderByFields.__members__.values():
        raise typer.BadParameter(
            message=f"'{value}' is not a valid order by field, supported fields are: {', '.join(OrderByFields.__members__.values())}",
            param_hint="--order-by, -o",
        )
    return value


def load_file_callback(ctx: typer.Context, value: Path):
    if ctx.resilient_parsing:
        return
    if not value.exists():
        raise typer.BadParameter(
            message=f"file at path: '{value.as_posix()}' does not exist",
        )
    return value
