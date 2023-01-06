import ast


class Transformer(ast.NodeTransformer):
    ALLOWED_NODE_TYPES = set(
        [
            "Expression",
            "Attribute",
            "Slice",
            "Subscript",
            "Index",
            "Constant",
            "Tuple",
            "Name",
            "Load",
            "Str",
            "BinOp",
            "Num",
            "List",
            "Dict",
            "Add",
            "Sub",
            "Mult",
            "Div",
            "FloorDiv",
            "Mod",
            "Pow",
            "LShift",
            "RShift",
            "BitOr",
            "BitXor",
            "BitAnd",
            "MatMult",
            "And",
            "Or",
            "Compare",
            "Eq",
            "NotEq",
            "Lt",
            "LtE",
            "Gt",
            "GtE",
            "Is",
            "IsNot",
            "In",
            "NotIn",
        ]
    )

    def generic_visit(self, node):
        nodetype = type(node).__name__
        if nodetype not in self.ALLOWED_NODE_TYPES:
            raise RuntimeError(f"Invalid expression: {nodetype} not allowed !")

        return ast.NodeTransformer.generic_visit(self, node)


transformer = Transformer()


def safe_eval(source: str, locals_dict=None):
    tree = ast.parse(source, mode="eval")

    transformer.visit(tree)
    clause = compile(tree, "<AST>", "eval")
    result = eval(clause, {"__builtins__": {}}, locals_dict)
    print("EVAL", source, locals_dict, result)

    return result
