import typer

from batchling.cli.enums import OrderByFields


def order_by_callback(value: str):
    if value not in OrderByFields.__members__.values():
        raise typer.BadParameter(
            message=f"'{value}' is not a valid order by field, supported fields are: {', '.join(OrderByFields.__members__.values())}",
            param_hint="--order-by, -o",
        )
    return value
