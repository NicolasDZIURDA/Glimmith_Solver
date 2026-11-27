from ._shape_set import SameShapeRule


def build(ctx):
    return SameShapeRule(ctx) if "match" in ctx.rule_types else None