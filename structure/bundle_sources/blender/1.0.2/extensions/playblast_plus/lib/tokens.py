"""Token system — self-contained copy bundled with the Blender extension.

Tokens are short placeholder strings that are replaced with live scene values
when formatting output filenames.  e.g. ``<scene>_<user>_<camera>``
"""

import getpass

_registered_tokens: dict = {}


def format_tokens(string: str, options) -> str:
    """Replace all registered tokens in *string* with their resolved values.

    Args:
        string (str): Filename template that may contain ``<token>`` strings.
        options: Passed through to each token resolver function.

    Returns:
        str: The string with every known token replaced.
    """
    if not string:
        return string
    for token, value in _registered_tokens.items():
        if token in string:
            string = string.replace(token, value['func'](options))
    return string


def register_token(token: str, func, label: str = ""):
    assert token.startswith("<") and token.endswith(">")
    assert callable(func)
    _registered_tokens[token] = {"func": func, "label": label}


def list_tokens() -> dict:
    return _registered_tokens.copy()


# Built-in token — always available
register_token(
    "<user>",
    lambda options: getpass.getuser(),
    label="Insert current user's name",
)
