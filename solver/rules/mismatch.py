from ._shape_set import ShapeSetRule

def build(ctx):
    return ShapeSetRule(ctx, same=False) if "mismatch" in ctx.rule_types else None