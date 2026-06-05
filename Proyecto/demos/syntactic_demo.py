"""
syntactic_demo.py — Syntactic Analysis Demo
============================================

How the Security Linter's PARSER works (Phase 1).

This file demonstrates the syntactic analysis phase using Python's
built-in ast module and our custom ASTConsumer.

It does NOT run the linter — it shows how source code is parsed
into an Abstract Syntax Tree (AST) and then translated into the
project's custom AST nodes.

Two ASTs are shown side-by-side:
  1. Standard Python AST  — produced by ast.parse()
  2. Custom Security AST  — produced by ASTConsumer (ast_nodes.py)

Usage
-----
    python demos/syntactic_demo.py
"""

import ast
import sys
import os

# Add project root to path so we can import ASTConsumer
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ast_consumer import ASTConsumer
from ast_printer   import print_ast_tree
from ast_nodes     import (
    Module, AssignStatement, AugAssignStatement, ExprStatement,
    IfStatement, WhileStatement, ForStatement,
    FunctionDef, Param, ReturnStatement, ImportStatement,
    Literal, Name, BinaryOp, UnaryOp, BoolOp, Compare,
    Keyword, FCall, Attribute, Subscript,
    JoinedStr, FormattedValue, PercentFormat,
    Tuple, PyList,
)

from rich.console import Console
from rich.panel   import Panel
from rich.rule    import Rule

con = Console()


# Sample cases that demonstrate different AST constructs
SAMPLES = {
    "Simple assignment": (
        'user_id = input("Enter ID: ")\n'
    ),
    "String concatenation (SQLi pattern)": (
        'user_id = input("ID: ")\n'
        'query = "SELECT * FROM users WHERE id = " + user_id\n'
        'cursor.execute(query)\n'
    ),
    "f-string (SQLi pattern)": (
        'name = request.args.get("name")\n'
        'query = f"SELECT * FROM users WHERE name = \'{name}\'"\n'
        'cursor.execute(query)\n'
    ),
    "printf-style % (SQLi pattern)": (
        'username = request.form.get("user")\n'
        'sql = "SELECT id FROM accounts WHERE login = \'%s\'" % username\n'
        'db.execute(sql)\n'
    ),
    "Conditional (if/elif/else)": (
        'if user_input:\n'
        '    query = "SELECT * FROM users WHERE id = " + user_input\n'
        'elif admin:\n'
        '    query = "SELECT * FROM admin WHERE id = " + user_input\n'
        'else:\n'
        '    query = "SELECT * FROM backup"\n'
        'db.execute(query)\n'
    ),
    "Function definition": (
        'def get_user(user_id):\n'
        '    query = "SELECT * FROM users WHERE id = " + user_id\n'
        '    cursor.execute(query)\n'
        '    return cursor.fetchone()\n'
    ),
}


def dump_python_ast(node: ast.AST, indent: int = 0) -> str:
    """Dump a Python AST node tree in a readable format."""
    prefix = "  " * indent
    fields = []

    # Get the node's fields
    for field, value in ast.iter_fields(node):
        if value is None or (isinstance(value, list) and len(value) == 0):
            continue
        if isinstance(value, list):
            items = []
            for item in value:
                if isinstance(item, ast.AST):
                    items.append(dump_python_ast(item, indent + 2))
                else:
                    items.append(f"{'  ' * (indent + 2)}repr({item})")
            fields.append(f"{prefix}  {field}: [\n" + "\n".join(items) + f"\n{prefix}  ]")
        elif isinstance(value, ast.AST):
            fields.append(f"{prefix}  {field}: {dump_python_ast(value, indent + 1)}")
        else:
            fields.append(f"{prefix}  {field}: {value!r}")

    # Include lineno/col_offset for helpful context
    location = ""
    if hasattr(node, 'lineno') and node.lineno:
        location = f"  [L{node.lineno}:{node.col_offset}]"

    body = "\n".join(fields)
    return f"{prefix}{type(node).__name__}{location}\n{body}"


def main():
    con.print()
    con.print(Panel(
        "[bold cyan]SYNTACTIC ANALYSIS DEMO[/bold cyan]\n"
        "[dim white]Python AST → Custom Security AST[/dim white]\n\n"
        "[dim]How the Security Linter parses source code and translates[/dim]\n"
        "[dim]standard Python AST nodes into security-specific nodes.[/dim]",
        border_style="cyan",
        expand=False,
        padding=(1, 4),
    ))

    consumer = ASTConsumer()

    for title, code in SAMPLES.items():
        con.print()
        con.print(Rule(f"[bold white]{title}[/bold white]", style="dim white"))

        # Show source code
        con.print(f"\n[dim]Source code:[/dim]")
        for i, line in enumerate(code.splitlines(), 1):
            con.print(f"  {i:>3} │ {line}")

        # 1. Standard Python AST
        con.print(f"\n[bold yellow]Step 1: Python's ast.parse() → Standard AST[/bold yellow]")
        try:
            std_tree = ast.parse(code)
            std_dump = dump_python_ast(std_tree)
            con.print(std_dump)
        except SyntaxError as e:
            con.print(f"  [red]Syntax error: {e}[/red]")
            continue

        # 2. Custom Security AST
        con.print(f"\n[bold green]Step 2: ASTConsumer.consume() → Custom Security AST[/bold green]")
        try:
            custom_tree = consumer.consume(code)
            print_ast_tree(custom_tree, con=con)
        except Exception as e:
            con.print(f"  [red]Translation error: {e}[/red]")
            continue

        # 3. Key mapping explanation
        con.print(f"\n[bold cyan]Key translations in this example:[/bold cyan]")
        explain_translations(code, con)
        con.print()



def explain_translations(code: str, con: Console):
    """Explain which AST constructs mapped to custom nodes."""

    # Detect SQLi patterns in the source and explain the mapping
    explanations = []

    if 'f"' in code or "f'" in code:
        explanations.append(
            '  • [green]f-string[/green] → [yellow]JoinedStr[/yellow] (contains '
            '[yellow]FormattedValue[/yellow] children)\n'
            '    Each {expr} is an independent taint trackable unit'
        )

    if "'%s'" in code or '"%s"' in code or "'%'" in code or '"%"' in code:
        explanations.append(
            '  • [green]% operator[/green] → [yellow]PercentFormat[/yellow] '
            '(not generic BinaryOp)\n'
            '    Recognized as a SQLi-prone pattern (printf-style injection)'
        )

    if '" + ' in code or "' + " in code:
        explanations.append(
            '  • [green]+ concatenation[/green] → [yellow]BinaryOp[/yellow] (op="+")\n'
            '    Taint propagates: if either operand is tainted, result is tainted'
        )

    if '(' in code and ')' in code:
        explanations.append(
            '  • [green]function call[/green] → [yellow]FCall[/yellow] '
            '(with [yellow]Keyword[/yellow] for kwargs)\n'
            '    The taint engine checks if callee is Source, Sink, or Sanitizer'
        )

    if 'def ' in code:
        explanations.append(
            '  • [green]function definition[/green] → [yellow]FunctionDef[/yellow] '
            '(with [yellow]Param[/yellow] children)\n'
            '    Parameters are conservatively marked TAINTED for interprocedural analysis'
        )

    if 'if ' in code or 'elif ' in code:
        explanations.append(
            '  • [green]if/elif/else[/green] → [yellow]IfStatement[/yellow] '
            '(with [yellow]ElifClause[/yellow] list)\n'
            '    elif chains are explicitly extracted (not nested If) for clean CFG building'
        )

    if not explanations:
        explanations.append('  • Simple nodes only (Literal, Name, AssignStatement)')

    for exp in explanations:
        con.print(exp)


if __name__ == "__main__":
    main()
