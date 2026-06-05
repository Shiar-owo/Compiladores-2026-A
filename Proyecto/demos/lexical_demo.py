"""
lexical_demo.py — Lexical Analysis Demo
========================================

How the Security Linter's LEXER works (Phase 1).

This file demonstrates the lexical analysis phase using Python's
built-in tokenizer. It does NOT run the linter itself — it simply
shows how source code is decomposed into tokens, which is the first
step before syntactic analysis.

Terminology
-----------
Lexeme  : a raw substring from the source ("input", "(", "42", ";")
Token   : a (type, value) pair produced by the tokenizer
Lexer   : the component that performs lexical analysis

Usage
-----
    python demos/lexical_demo.py
"""

import io
import token
import tokenize

SAMPLE_CODE = '''
user_id = input("Enter ID: ")
query = "SELECT * FROM users WHERE id = " + user_id
cursor.execute(query)
'''


def tokenize_source(code: str):
    """
    Tokenize the source string using Python's standard tokenizer
    and yield (token_number, token_value, start_line, start_col) tuples.
    """
    tokens = tokenize.generate_tokens(io.StringIO(code).readline)
    for tok in tokens:
        # Skip encoding and end-of-stream markers for clarity
        if tok.type in (token.ENCODING, token.ENDMARKER, token.NL):
            continue
        yield tok


_OPERATOR_NAMES = {
    "+":  "PLUS",
    "-":  "MINUS",
    "*":  "STAR",
    "/":  "SLASH",
    "//": "FLOOR_DIV",
    "%":  "MOD",
    "**": "POW",
    "=":  "ASSIGN",
    "+=": "PLUS_ASSIGN",
    "-=": "MINUS_ASSIGN",
    "==": "EQ",
    "!=": "NEQ",
    "<":  "LT",
    ">":  "GT",
    "<=": "LE",
    ">=": "GE",
    "(":  "LPAREN",
    ")":  "RPAREN",
    "[":  "LSQB",
    "]":  "RSQB",
    "{":  "LBRACE",
    "}":  "RBRACE",
    ".":  "DOT",
    ",":  "COMMA",
    ";":  "SEMI",
    ":":  "COLON",
    "&":  "AMPERSAND",
    "|":  "VBAR",
    "^":  "CIRCUMFLEX",
    "~":  "TILDE",
    "!":  "BANG",
    "@":  "AT",
}


def token_type_name(tok: tokenize.TokenInfo) -> str:
    """Return a human-readable name for a token.

    For operators (OP), returns the exact kind (PLUS, ASSIGN, DOT, …).
    For other tokens, returns the standard category name.
    """
    if tok.type == token.OP:
        return "OP_" + _OPERATOR_NAMES.get(tok.string, f"OP_{tok.string!r}")
    names = {
        token.NAME:       "IDENTIFIER",
        token.NUMBER:     "NUMBER",
        token.STRING:     "STRING",
        token.NEWLINE:    "NEWLINE",
        token.INDENT:     "INDENT",
        token.DEDENT:     "DEDENT",
        token.COMMENT:    "COMMENT",
    }
    return names.get(tok.type, f"TOKEN_{tok.type}")


def main():
    print("=" * 65)
    print("  LEXICAL ANALYSIS DEMO")
    print("  How Python's tokenizer decomposes source code into tokens")
    print("=" * 65)

    print("\n\x1b[1mSource code:\x1b[0m")
    for i, line in enumerate(SAMPLE_CODE.splitlines(), 1):
        print(f"  {i:>3} │ {line}")

    print("\n\x1b[1mToken stream:\x1b[0m")
    print(f"  {'Line:Col':<10} {'Type':<12} {'Lexeme':<35} {'Purpose'}")
    print(f"  {'─'*9:<10} {'─'*11:<12} {'─'*34:<35} {'─'*20}")

    tokens = list(tokenize_source(SAMPLE_CODE))
    for tok in tokens:
        location = f"{tok.start[0]}:{tok.start[1]}"
        ttype = token_type_name(tok)
        value = repr(tok.string)

        # Determine the purpose description
        if tok.type == token.NAME:
            if tok.string in ("def", "if", "for", "while", "return", "import",
                              "from", "class", "elif", "else", "and", "or",
                              "not", "in", "is", "True", "False", "None"):
                purpose = "keyword"
            elif tok.string in ("input", "print", "int", "str"):
                purpose = "built-in function"
            else:
                purpose = "identifier (variable/function name)"
        elif tok.type == token.STRING:
            if tok.string.startswith("f") or tok.string.startswith("F"):
                purpose = "f-string literal"
            else:
                purpose = "string literal"
        elif tok.type == token.NUMBER:
            purpose = "numeric literal"
        elif tok.type == token.OP:
            if tok.string == "+":
                purpose = "concatenation / addition"
            elif tok.string == "=":
                purpose = "assignment"
            elif tok.string == "(":
                purpose = "open parenthesis (call start)"
            elif tok.string == ")":
                purpose = "close parenthesis (call end)"
            elif tok.string == "%":
                purpose = "modulo / printf-style format"
            else:
                purpose = "operator / punctuation"
        elif tok.type == token.NEWLINE:
            purpose = "end of line"
        elif tok.type in (token.INDENT, token.DEDENT):
            purpose = "indentation change"
        else:
            purpose = ""

        print(f"  {location:<10} {ttype:<12} {value:<35} {purpose}")

    print(f"\x1b[1mTotal tokens:\x1b[0m {len(tokens)}")
    print("=" * 65)


if __name__ == "__main__":
    main()
