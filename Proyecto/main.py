"""
main.py — Demo de la Fase 1: Lexer + Parser + AST
==================================================

Estructura de directorios
--------------------------
  phase1/
  ├── samples/          ← código fuente de entrada (un .py por caso)
  ├── output/
  │   ├── ast/          ← un PNG por caso (AST sin leyenda)
  │   └── legend/       ← legend.png (leyenda standalone)
  └── *.py              ← módulos del compilador

Pipeline por cada archivo en samples/
--------------------------------------
  1. Leer el .py desde samples/
  2. Lexer  → lista de tokens
  3. Parser → AST (Module)
  4. Imprimir tokens en tabla (rich)
  5. Imprimir AST como árbol (rich + Unicode)
  6. Exportar AST como PNG en output/ast/

Al final se genera output/legend/legend.png (una sola vez).
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

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")
AST_DIR     = os.path.join(BASE_DIR, "output", "ast")
LEGEND_DIR  = os.path.join(BASE_DIR, "output", "legend")

# ── Metadatos de cada caso (nombre de archivo → caption de figura) ─────────────
# El orden en esta lista determina el orden de procesamiento.
CASE_META: dict[str, str] = {
    "case1_simple_assignment.py":    "Figure 1. AST for Case 1: Simple Assignment and Function Call",
    "case2_sqli_concatenation.py":   "Figure 2. AST for Case 2: Classic SQLi via String Concatenation",
    "case3_sqli_fstring.py":         "Figure 3. AST for Case 3: SQLi via f-string Interpolation (Flask)",
    "case4_sqli_printf.py":          "Figure 4. AST for Case 4: Legacy SQLi via printf-style Formatting",
    "case5_safe_sanitizer.py":       "Figure 5. AST for Case 5: Safe Path with int() Sanitizer",
    "case6_augassign_conditional.py":"Figure 6. AST for Case 6: Conditional SQLi via Augmented Assignment",
}


# ──────────────────────────────────────────────────────────────────────────────
# Runner de un caso
# ──────────────────────────────────────────────────────────────────────────────

def run_case(
    sample_path: str,
    caption: str,
    visualizer: ASTVisualizer,
) -> bool:
    filename = os.path.basename(sample_path)
    slug     = os.path.splitext(filename)[0]
    title    = caption.split(". ", 1)[-1]   # texto sin "Figure N."

    con.print()
    con.print(Rule(f"[bold white]{caption}[/bold white]", style="dim white"))

    # ── Leer fuente ───────────────────────────────────────────────────────────
    try:
        with open(sample_path, encoding="utf-8") as f:
            source = f.read()
    except OSError as exc:
        con.print(f"  [bold red]✗ No se pudo leer {sample_path}:[/bold red] {exc}")
        return False

    con.print(Rule("[dim cyan]📄  Source — " + filename + "[/dim cyan]", style="dim white"))
    for i, line in enumerate(source.splitlines(), 1):
        con.print(Text(f"  {i:>3} │ ", style="dim white") + Text(line, style="white"))
    con.print()

    # ── Lexer ─────────────────────────────────────────────────────────────────
    con.print(Rule("[dim cyan]🔤  Tokens[/dim cyan]", style="dim white"))
    try:
        tokens = list(Lexer(source).tokenize())
    except Exception as exc:
        con.print(f"  [bold red]✗ Lexer error:[/bold red] {exc}")
        return False
    print_token_table(tokens, con)

    # ── Parser → AST (consola) ────────────────────────────────────────────────
    con.print(Rule("[dim cyan]🌳  AST[/dim cyan]", style="dim white"))
    try:
        tree = Parser(TokenStream(tokens)).parse()
    except Exception as exc:
        con.print(f"  [bold red]✗ Parser error:[/bold red] {exc}")
        return False
    print_ast_tree(tree, con=con)

    node_count = _count_nodes(tree)
    con.print(
        f"  [green]✓[/green] Parsed — "
        f"[bold]{len(tree.body)}[/bold] top-level statement(s), "
        f"[bold]{node_count}[/bold] total AST node(s)"
    )
    con.print()

    # ── AST → PNG ─────────────────────────────────────────────────────────────
    try:
        png_path = visualizer.render(tree, filename=slug, caption=caption)
        con.print(
            f"  [green]✓[/green] AST graph → "
            f"[bold cyan]{os.path.relpath(png_path, BASE_DIR)}[/bold cyan]"
        )
    except Exception as exc:
        con.print(f"  [bold red]✗ PNG error:[/bold red] {exc}")
        return False

    return True


def _count_nodes(node) -> int:
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
            "[bold cyan]SECURITY LINTER — PHASE 1[/bold cyan]\n"
            "[dim white]Lexer  ·  Parser  ·  AST  (Python subset)[/dim white]\n\n"
            f"[dim white]samples/[/dim white]  [white]→[/white]  "
            f"[dim white]output/ast/   output/legend/[/dim white]",
            border_style="cyan",
            expand=False,
            padding=(1, 4),
        )
    )

    # Validar que exista la carpeta de samples
    if not os.path.isdir(SAMPLES_DIR):
        con.print(f"[bold red]✗ samples/ directory not found at {SAMPLES_DIR}[/bold red]")
        sys.exit(1)

    visualizer = ASTVisualizer(output_dir=AST_DIR, dpi=200, rankdir="TB")

    # Procesar solo los archivos listados en CASE_META (en orden)
    results: list[tuple[str, bool]] = []
    for filename, caption in CASE_META.items():
        path = os.path.join(SAMPLES_DIR, filename)
        if not os.path.isfile(path):
            con.print(f"  [yellow]⚠ Skipping missing file: {filename}[/yellow]")
            results.append((caption, False))
            continue
        ok = run_case(path, caption, visualizer)
        results.append((caption, ok))

    # ── Leyenda standalone ────────────────────────────────────────────────────
    con.print()
    con.print(Rule("[dim cyan]📐  Legend[/dim cyan]", style="dim white"))
    try:
        leg_path = ASTVisualizer.render_legend(output_dir=LEGEND_DIR, dpi=200)
        con.print(
            f"  [green]✓[/green] Legend PNG → "
            f"[bold cyan]{os.path.relpath(leg_path, BASE_DIR)}[/bold cyan]"
        )
    except Exception as exc:
        con.print(f"  [bold red]✗ Legend error:[/bold red] {exc}")

    # ── Resumen ───────────────────────────────────────────────────────────────
    con.print()
    con.print(Rule("[bold white]Summary[/bold white]", style="dim white"))
    ok_count = sum(1 for _, ok in results if ok)
    for caption, ok in results:
        icon  = "[green]✓[/green]" if ok else "[red]✗[/red]"
        label = caption.split(". ", 1)[-1]
        style = "white" if ok else "red"
        con.print(f"  {icon}  [{style}]{label}[/{style}]")

    con.print()
    con.print(
        f"  [bold]{ok_count}/{len(results)}[/bold] cases processed. "
        f"PNGs → [bold cyan]{os.path.relpath(AST_DIR, BASE_DIR)}/[/bold cyan]  "
        f"Legend → [bold cyan]{os.path.relpath(LEGEND_DIR, BASE_DIR)}/[/bold cyan]"
    )
    con.print()
    con.print("  [dim]Next phase: CFG Builder · DFG Builder · Taint Propagation Engine[/dim]")
    con.print()

    sys.exit(0 if ok_count == len(results) else 1)


if __name__ == "__main__":
    main()