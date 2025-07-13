from batchling.cli.enums import OrderByFields


def complete_order_by(value: str):
    for field in OrderByFields.__members__.values():
        if field.startswith(value):
            yield field
