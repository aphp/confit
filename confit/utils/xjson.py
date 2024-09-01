import ast
from typing import Any, Callable

from lark import Lark, Transformer, Tree


class Reference:
    """
    A path reference to a value in the configuration.
    """

    def __init__(self, value: str):
        """
        Parameters
        ----------
        value: str
            The path to the value in the configuration.
        """
        self.value = value

    def __repr__(self):
        return f"${{{self.value}}}"

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        return self.value == other.value


# Extended JSON grammar to parse references and tuples
# and ignore Python-style comments.
xjson_grammar = r"""
    ?value: dict
          | list
          | tuple
          | string
          | SIGNED_FLOAT       -> float
          | SIGNED_INT         -> int
          | "Infinity"         -> plus_inf
          | "-Infinity"        -> minus_inf
          | "NaN"              -> nan
          | "true"             -> true
          | "true"             -> true
          | "True"             -> true
          | "false"            -> false
          | "False"            -> false
          | "null"             -> null
          | "None"             -> null
          | reference

    list : "[" (value ("," value) * ","?)? "]"
    tuple : "(" (value ("," value) * ","?)? ")"

    dict : "{" (pair ("," pair)*) ? "}"
    pair : string ":" value

    string : STRING
    reference : "${" reference_content "}"
    !reference_content : NON_BRACES ? ( "{" reference_content "}" ? ) *
    NON_BRACES : /[^{}]+/

    // https://github.com/lark-parser/lark/blob/master/lark/grammars/python.lark#L284
    STRING : /([ubf]?r?|r[ubf])("(?!"").*?(?<!\\)(\\\\)*?"|'(?!'').*?(?<!\\)(\\\\)*?')/i
    VARNAME : ("_"|"-"|LETTER) ("_"|"-"|LETTER|DIGIT)*
    COMMENT: /#[^\n]*/

    SIGNED_FLOAT: ["+"|"-"] FLOAT
    SIGNED_INT: ["+"|"-"] INT

    %import common.LETTER
    %import common.DIGIT
    %import common.FLOAT
    %import common.INT
    %import common.WS
    %ignore WS
    %ignore COMMENT
    """


class XJsonTransformer(Transformer):
    """
    A Lark transformer to parse extended JSON.
    """

    def __init__(self, input_string: str):
        """
        Parameters
        ----------
        input_string: str
            The input string to parse.
        """
        super().__init__()
        self.input_string = input_string

    def string(self, s):
        """Parse string"""
        (s,) = s
        return ast.literal_eval(s)

    def float(self, n):
        """Parse number"""
        (n,) = n
        return float(n)

    def int(self, n):
        """Parse number"""
        (n,) = n
        return int(n)

    def reference(self, tree: Tree):
        """Parse reference"""
        meta = tree[0].meta
        return Reference(self.input_string[meta.start_pos : meta.end_pos])

    list = list
    tuple = tuple
    pair = tuple
    dict = dict

    def null(self, _):
        """Parse null"""
        return None

    def true(self, _):
        """Parse true"""
        return True

    def false(self, _):
        """Parse false"""
        return False

    def plus_inf(self, _):
        """Parse infinity"""
        return float("inf")

    def minus_inf(self, _):
        """Parse -infinity"""
        return -float("inf")

    def nan(self, _):
        """Parse nan"""
        return float("nan")


_json_parser = Lark(
    xjson_grammar, start="value", parser="lalr", propagate_positions=True
)


def _floatstr(o, _repr=float.__repr__, _inf=float("inf"), _neginf=-float("inf")):
    if o != o:
        text = "NaN"
    elif o == _inf:
        text = "Infinity"
    elif o == _neginf:
        text = "-Infinity"
    else:
        return _repr(o)

    return text


def _encode_str(s):
    """Return an ASCII-only JSON representation of a Python string"""
    r = repr(s)
    if s.count('"') <= s.count("'") and r.startswith("'"):
        r = '"' + s.replace('"', '\\"').replace("\\'", "'") + '"'
    return r


def _make_iterencode(
    floatstr: Callable[[float], str] = _floatstr,
    encoder: Callable[[str], str] = _encode_str,
    intstr: Callable[[int], str] = int.__repr__,
    separator=",",
):
    """
    Heavily inspired by Python's `json.encoder._make_iterencode`
    The main difference is that it allows to encode `Reference` and `tuple` objects.

    Parameters
    ----------
    floatstr: Callable[[float], str]
        Float serializer
    encoder: Callable[[str], str]
        String serializer
    intstr: Callable[[int], str]
        Int serializer
    separator: str
        JSON separator

    Returns
    -------
    Callable[[Any], Iterator[str]]
    """

    def _iterencode_sequence_content(o):
        first = True
        for value in o:
            if not first:
                yield separator + " "
            first = False
            yield from _iterencode(value)

    def _iterencode_list(o):
        yield "["
        yield from _iterencode_sequence_content(o)
        yield "]"

    def _iterencode_tuple(o):
        yield "("
        yield from _iterencode_sequence_content(o)
        yield ")"

    def _iterencode_dict(o):
        yield "{"
        first = True
        for key, value in o.items():
            if not first:
                yield separator + " "
            first = False
            assert isinstance(key, str)
            yield "{}: ".format(encoder(key))
            yield from _iterencode(value)
        yield "}"

    def _iterencode(o):
        if isinstance(o, Reference):
            yield str(o)
        elif isinstance(o, str):
            yield encoder(o)
        elif o is None:
            yield "null"
        elif o is True:
            yield "true"
        elif o is False:
            yield "false"
        elif isinstance(o, int):
            yield intstr(o)
        elif isinstance(o, float):
            yield floatstr(o)
        elif isinstance(o, list):
            yield from _iterencode_list(o)
        elif isinstance(o, tuple):
            yield from _iterencode_tuple(o)
        elif isinstance(o, dict):
            yield from _iterencode_dict(o)
        else:
            raise TypeError("Cannot serialize {}".format(o))

    return _iterencode


class MalformedValueError(ValueError):
    def __init__(self, value: str):
        self.value = value
        super().__init__(f"Malformed value: {value!r}")


def loads(s: str):
    """
    Load an extended JSON string into a python object.
    Takes care of detecting references and tuples

    Parameters
    ----------
    s: str

    Returns
    -------
    Any
    """
    try:
        return XJsonTransformer(s).transform(_json_parser.parse(s))
    except Exception:
        # Fail if we suspect that it is a malformed object
        # (e.g. has ', ", {, }, [, ] in it)
        if set(s) & set(",'\"{}[]$"):
            raise MalformedValueError(s)
        return s


def dumps(o: Any):
    """
    Dump a python object into an extended JSON string.
    Takes care of serializing references and tuples

    Parameters
    ----------
    o: Any

    Returns
    -------
    str
    """
    return "".join(_make_iterencode()(o))
