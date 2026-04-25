"""
main.py — Demo de la Fase 1: Lexer + Parser + AST
==================================================

Pipeline completo para seis casos de código Python con patrones de SQLi.
Por cada caso:
  1. Imprime los tokens en una tabla de consola (rich).
  2. Imprime el AST como árbol jerárquico en consola (rich + Unicode).
  3. Exporta la representación gráfica del AST como .png (Graphviz).

Casos incluidos
---------------
  1  Asignación simple y llamada a función
  2  Concatenación con input()            → SQLi clásico
  3  F-string con request.args.get()      → SQLi moderno (Flask)
  4  Printf-style  "%s" % val             → SQLi legacy
  5  Función con sanitizador int()        → ruta segura
  6  Acumulación con += dentro de if      → SQLi condicional
"""

import os
import sys

from rich.console import Console
from rich.panel   import Panel
from rich.rule    import Rule
from rich.text    import Text

from lexer          import Lexer, TokenStream
from parser         import Parser
from ast_printer    import print_ast_tree, print_token_table
from ast_visualizer import ASTVisualizer

con = Console()

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# ──────────────────────────────────────────────────────────────────────────────
# Casos de prueba
# ──────────────────────────────────────────────────────────────────────────────

# slug, título consola, caption figura, fuente
CASES: list[tuple[str, str, str, str]] = [
    (
        "1_asignacion_simple",
        "1 · Asignación simple y llamada a función",
        "Figure 1. AST for Case 1: Simple Assignment and Function Call",
        """
x = 42
y = "hello"
print(x)
""",
    ),
    (
        "2_sqli_concatenacion",
        "2 · SQLi clásico — concatenación con input()",
        "Figure 2. AST for Case 2: Classic SQLi via String Concatenation",
        """
user_id = input("ID: ")
query = "SELECT * FROM users WHERE id = " + user_id
cursor.execute(query)
""",
    ),
    (
        "3_sqli_fstring",
        "3 · SQLi moderno — f-string con request.args",
        "Figure 3. AST for Case 3: SQLi via f-string Interpolation (Flask)",
        """
from flask import request

def get_user():
    name = request.args.get("name")
    query = f"SELECT * FROM users WHERE name = '{name}'"
    cursor.execute(query)
""",
    ),
    (
        "4_sqli_printf",
        "4 · SQLi legacy — printf-style",
        "Figure 4. AST for Case 4: Legacy SQLi via printf-style Formatting",
        """
username = request.form.get("user")
sql = "SELECT id FROM accounts WHERE login = '%s'" % username
db.execute(sql)
""",
    ),
    (
        "5_ruta_segura",
        "5 · Función con sanitizador int() — ruta segura",
        "Figure 5. AST for Case 5: Safe Path with int() Sanitizer",
        """
import re

def fetch_product(product_id):
    safe_id = int(product_id)
    query = "SELECT * FROM products WHERE id = " + str(safe_id)
    cursor.execute(query)
    return cursor.fetchone()
""",
    ),
    (
        "6_augassign_condicional",
        "6 · SQLi condicional — acumulación con +=",
        "Figure 6. AST for Case 6: Conditional SQLi via Augmented Assignment",
        """
base_query = "SELECT * FROM logs WHERE 1=1"
if user_filter:
    base_query += " AND user = '" + user_input + "'"
db.execute(base_query)
""",
    ),
]


# ──────────────────────────────────────────────────────────────────────────────
# Runner de un caso
# ──────────────────────────────────────────────────────────────────────────────

def run_case(
    slug: str,
    title: str,
    caption: str,
    source: str,
    visualizer: ASTVisualizer,
) -> bool:
    """
    Ejecuta el pipeline completo sobre un fragmento de código.
    Retorna True si el caso se procesó sin errores.
    """

    # ── Cabecera ──────────────────────────────────────────────────────────────
    con.print()
    con.print(Rule(f"[bold white]{title}[/bold white]", style="dim white"))

    # ── Código fuente ─────────────────────────────────────────────────────────
    con.print(Rule("[dim cyan]📄  Código fuente[/dim cyan]", style="dim white"))
    lines = source.strip().splitlines()
    for i, line in enumerate(lines, 1):
        num  = Text(f"  {i:>3} │ ", style="dim white")
        code = Text(line, style="white")
        con.print(num + code)
    con.print()

    # ── Lexer → Tokens ────────────────────────────────────────────────────────
    con.print(Rule("[dim cyan]🔤  Tokens[/dim cyan]", style="dim white"))
    try:
        tokens = list(Lexer(source).tokenize())
    except Exception as exc:
        con.print(f"  [bold red]✗ Error léxico:[/bold red] {exc}")
        return False

    print_token_table(tokens, con)

    # ── Parser → AST (consola) ────────────────────────────────────────────────
    con.print(Rule("[dim cyan]🌳  AST — árbol[/dim cyan]", style="dim white"))
    try:
        tree = Parser(TokenStream(tokens)).parse()
    except Exception as exc:
        con.print(f"  [bold red]✗ Error de sintaxis:[/bold red] {exc}")
        return False

    print_ast_tree(tree, con=con)

    node_count = _count_nodes(tree)
    con.print(
        f"  [green]✓[/green] Parseado correctamente — "
        f"[bold]{len(tree.body)}[/bold] sentencia(s) en el módulo, "
        f"[bold]{node_count}[/bold] nodo(s) totales en el AST"
    )
    con.print()

    # ── AST → PNG ─────────────────────────────────────────────────────────────
    try:
        png_path = visualizer.render(tree, filename=slug, caption=caption)
        con.print(
            f"  [green]✓[/green] Grafo PNG guardado → "
            f"[bold cyan]{png_path}[/bold cyan]"
        )
    except Exception as exc:
        con.print(f"  [bold red]✗ Error al generar PNG:[/bold red] {exc}")
        return False

    return True


def _count_nodes(node) -> int:
    """Cuenta el total de nodos ASTNode en el árbol."""
    from ast_nodes import ASTNode
    total = 1
    for v in node.__dict__.values():
        if isinstance(v, ASTNode):
            total += _count_nodes(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, ASTNode):
                    total += _count_nodes(item)
    return total


# ──────────────────────────────────────────────────────────────────────────────
# Punto de entrada
# ──────────────────────────────────────────────────────────────────────────────

def main():
    con.print()
    con.print(
        Panel(
            "[bold cyan]SECURITY LINTER — FASE 1[/bold cyan]\n"
            "[dim white]Lexer  ·  Parser  ·  AST  (subconjunto Python)[/dim white]",
            border_style="cyan",
            expand=False,
            padding=(1, 6),
        )
    )

    visualizer = ASTVisualizer(output_dir=OUTPUT_DIR, dpi=150, rankdir="TB")

    results: list[tuple[str, bool]] = []
    for slug, title, caption, source in CASES:
        ok = run_case(slug, title, caption, source, visualizer)
        results.append((title, ok))

    # ── Resumen final ─────────────────────────────────────────────────────────
    con.print()
    con.print(Rule("[bold white]Resumen[/bold white]", style="dim white"))
    ok_count = sum(1 for _, ok in results if ok)
    for title, ok in results:
        icon  = "[green]✓[/green]" if ok else "[red]✗[/red]"
        style = "white" if ok else "red"
        con.print(f"  {icon}  [{style}]{title}[/{style}]")

    con.print()
    con.print(
        f"  [bold]{ok_count}/{len(results)}[/bold] casos procesados correctamente. "
        f"PNGs guardados en [bold cyan]{os.path.abspath(OUTPUT_DIR)}[/bold cyan]"
    )
    con.print()
    con.print(
        "  [dim]Siguiente fase: CFG Builder · DFG Builder · "
        "Taint Propagation Engine[/dim]"
    )
    con.print()

    sys.exit(0 if ok_count == len(results) else 1)


if __name__ == "__main__":
    main()
