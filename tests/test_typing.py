import jedi
import parso

SNIPPET_1 = """
from file_with_function import get_len
value = get_len(string=ok)
"""

SNIPPET_2 = """
from file_with_function import get_len
draft_value = get_len.draft(string=ok)
value = draft_value.instantiate()
"""

def test_typing_1():
    interpreter = jedi.Interpreter(SNIPPET_1, [{}])

    def iter_names(root):
        if isinstance(root, parso.python.tree.Name):
            yield root
        for child in getattr(root, "children", ()):
            yield from iter_names(child)

    types = {
        str(name): [str(x) for x in interpreter.infer(*name.start_pos)]
        for name in iter_names(interpreter._module_node)
    }
    print(types)
    assert types["<Name: value@3,0>"] == [
        "<Name full_name='torch._tensor.Tensor', description='instance Tensor'>"
    ]


def test_typing_2():
    interpreter = jedi.Interpreter(SNIPPET_2, [{}])

    def iter_names(root):
        if isinstance(root, parso.python.tree.Name):
            yield root
        for child in getattr(root, "children", ()):
            yield from iter_names(child)

    types = {
        str(name): [str(x) for x in interpreter.infer(*name.start_pos)]
        for name in iter_names(interpreter._module_node)
    }
    print(types)
    assert types["<Name: draft_value@3,0>"] == [
        "<Name full_name='confit.draft.Draft', description='instance Draft'>"
    ]
    assert types["<Name: value@4,0>"] == [
        "<Name full_name='torch._tensor.Tensor', description='instance Tensor'>"
    ]
