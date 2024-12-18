import morph
from morph import MorphGlobalContext


@morph.func(name="alias1")
@morph.variables("score_limit")
@morph.load_data("alias2")
def main(context: MorphGlobalContext):
    print("Data in alias1:", context.data)
    print("Variable in alias1:", context.vars)

    alias2_data = context.data["alias2"]
    filtered_alias2_data = alias2_data[
        alias2_data["score"] > context.vars["score_limit"]
    ]

    return filtered_alias2_data
