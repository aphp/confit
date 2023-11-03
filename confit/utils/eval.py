import ast
from typing import Any, Dict, Optional


class Transformer(ast.NodeTransformer):
    """
    An ast NodeTransformer that only allows a subset of the Python AST.
    """

    ALLOWED_NODE_TYPES = {
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
        "Set",
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
        "Starred",
    }

    def generic_visit(self, node):
        """
        Checks that the node type is allowed.
        """
        nodetype = type(node).__name__
        if nodetype not in self.ALLOWED_NODE_TYPES:
            raise RuntimeError(f"Invalid expression: {nodetype} not allowed !")

        return ast.NodeTransformer.generic_visit(self, node)


transformer = Transformer()


def safe_eval(source: str, locals_dict: Optional[Dict[str, Any]] = None):
    """
    Evaluate a Python string expression in a safe way.
    For instance, imports, function calls and builtins are disabled.


    Parameters
    ----------
    source: str
        The expression to evaluate
    locals_dict: Optional[Dict[str, Any]]
        The local variables to use in the evaluation

    Returns
    -------
    Any
        The result of the evaluation
    """
    tree = ast.parse(source, mode="eval")

    transformer.visit(tree)
    clause = compile(tree, "<AST>", "eval")
    result = eval(clause, {"__builtins__": {}}, locals_dict)

    return result
