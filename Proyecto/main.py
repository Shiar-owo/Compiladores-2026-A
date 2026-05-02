"""
main.py — Security Linter — Fase 1 + Fase 2
============================================

Fase 1: "No reimplementa el lexer ni el parser; consume directamente el AST
producido por el compilador huésped."

Fase 2: Análisis semántico extendido (núcleo del linter)
- CFG Builder modela todos los caminos de ejecución posibles
- DFG Builder rastrea cómo los valores fluyen de variable en variable
- Taint Propagation Engine marca variables de fuentes controladas por usuario
  y propaga esa "mancha" a través del DFG

Estructura de directorios
--------------------------
  samples/          ← código fuente de entrada (un .py por caso)
  output/
  │   ├── ast/          ← un PNG por caso (AST sin leyenda)
  │   └── legend/       ← legend.png (leyenda standalone)

Pipeline por cada archivo en samples/
--------------------------------------
  1. Leer el .py desde samples/
  2. AST Consumer → AST (Module)  (usa ast.parse del compilador huésped)
  3. CFG Builder → grafo de flujo de control
  4. DFG Builder → grafo de flujo de datos
  5. Symbol Table → tabla de símbolos con tipos y taint
  6. Taint Propagation Engine → Análisis de taint
  7. Imprimir resultados del análisis
  8. Exportar AST como PNG en output/ast/

Al final se genera output/legend/legend.png (una sola vez).
"""

import os
import sys

from rich.console import Console
from rich.panel   import Panel
from rich.rule    import Rule
from rich.text    import Text

from ast_consumer   import ASTConsumer
from ast_printer    import print_ast_tree
from ast_visualizer import ASTVisualizer
from cfg_builder    import CFGBuilder
from dfg_builder   import DFGBuilder
from symbol_table  import SymbolTable
from taint_engine  import TaintPropagationEngine, TaintSource

con = Console()

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")
AST_DIR     = os.path.join(BASE_DIR, "output", "ast")
LEGEND_DIR  = os.path.join(BASE_DIR, "output", "legend")

CASE_META: dict[str, str] = {
    "case1_simple_assignment.py":    "Figure 1. Simple Assignment (Safe)",
    "case2_sqli_concatenation.py":   "Figure 2. SQLi via String Concatenation",
    "case3_sqli_fstring.py":         "Figure 3. SQLi via f-string (Flask)",
    "case4_sqli_printf.py":          "Figure 4. SQLi via printf-style",
    "case5_safe_sanitizer.py":       "Figure 5. Safe Path with int() Sanitizer",
    "case6_augassign_conditional.py":"Figure 6. Conditional SQLi via AugAssign",
}


def run_case(
    sample_path: str,
    caption: str,
    visualizer: ASTVisualizer,
    consumer: ASTConsumer,
) -> bool:
    filename = os.path.basename(sample_path)
    slug     = os.path.splitext(filename)[0]

    con.print()
    con.print(Rule(f"[bold white]{caption}[/bold white]", style="dim white"))

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

    try:
        tree = consumer.consume(source)
    except Exception as exc:
        con.print(f"  [bold red]✗ AST Consumer error:[/bold red] {exc}")
        return False

    con.print(Rule("[dim cyan]🌳  AST (from Python compiler)[/dim cyan]", style="dim white"))
    print_ast_tree(tree, con=con)

    node_count = _count_nodes(tree)
    con.print(
        f"  [green]✓[/green] AST consumed — "
        f"[bold]{len(tree.body)}[/bold] statements, [bold]{node_count}[/bold] nodes"
    )
    con.print()

    con.print(Rule("[dim cyan]🔗  CFG Build[/dim cyan]", style="dim white"))
    cfg_builder = CFGBuilder()
    try:
        cfg = cfg_builder.build(tree)
        con.print(f"  [green]✓[/green] CFG built — {len(cfg.nodes)} nodes")
    except Exception as exc:
        con.print(f"  [bold red]✗ CFG Builder error:[/bold red] {exc}")

    con.print(Rule("[dim cyan]🔗  DFG Build[/dim cyan]", style="dim white"))
    dfg_builder = DFGBuilder()
    try:
        dfg = dfg_builder.build(tree)
        con.print(f"  [green]✓[/green] DFG built — {len(dfg.nodes)} nodes, {len(dfg.edges)} edges")
    except Exception as exc:
        con.print(f"  [bold red]✗ DFG Builder error:[/bold red] {exc}")

    con.print(Rule("[dim cyan]🔍  Taint Analysis[/dim cyan]", style="dim white"))
    symbol_table = SymbolTable()
    taint_engine = TaintPropagationEngine()
    try:
        taint_result = taint_engine.analyze(tree, dfg, symbol_table)
        
        if taint_result.sources:
            con.print(f"  [yellow]⚠[/yellow] Taint sources found:")
            for rec in taint_result.sources:
                con.print(f"    • {rec.variable} @ line {rec.line} (source: {rec.source})")
        
        if taint_result.propagations:
            con.print(f"  [yellow]↪[/yellow] Propagations:")
            for rec in taint_result.propagations[:5]:
                con.print(f"    • {rec.variable} <- {rec.source}")
            if len(taint_result.propagations) > 5:
                con.print(f"    ... and {len(taint_result.propagations) - 5} more")
        
        if not taint_result.sources and not taint_result.propagations:
            con.print(f"  [green]✓[/green] No taint detected")
        
    except Exception as exc:
        con.print(f"  [bold red]✗ Taint Engine error:[/bold red] {exc}")

    try:
        png_path = visualizer.render(tree, filename=slug, caption=caption)
        con.print(
            f"  [green]✓[/green] AST graph → "
            f"[bold cyan]{os.path.relpath(png_path, BASE_DIR)}[/bold cyan]"
        )
    except Exception as exc:
        con.print(f"  [bold red]✗ PNG error:[/bold red] {exc}")

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


def main():
    con.print()
    con.print(
        Panel(
            "[bold cyan]SECURITY LINTER — PHASE 1+2[/bold cyan]\n"
            "[dim white]AST + CFG + DFG + Taint Propagation[/dim white]\n\n"
            f"[dim white]samples/[/dim white]  [white]→[/white]  "
            f"[dim white]output/ast/   output/legend/[/dim white]",
            border_style="cyan",
            expand=False,
            padding=(1, 4),
        )
    )

    if not os.path.isdir(SAMPLES_DIR):
        con.print(f"[bold red]✗ samples/ not found at {SAMPLES_DIR}[/bold red]")
        sys.exit(1)

    visualizer = ASTVisualizer(output_dir=AST_DIR, dpi=200, rankdir="TB")
    consumer = ASTConsumer()

    results: list[tuple[str, bool]] = []
    for filename, caption in CASE_META.items():
        path = os.path.join(SAMPLES_DIR, filename)
        if not os.path.isfile(path):
            con.print(f"  [yellow]⚠ Skipping missing: {filename}[/yellow]")
            results.append((caption, False))
            continue
        ok = run_case(path, caption, visualizer, consumer)
        results.append((caption, ok))

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
        f"PNGs → [bold cyan]{os.path.relpath(AST_DIR, BASE_DIR)}/[/bold cyan]"
    )
    con.print()
    con.print("  [dim]Next: Phase 3 — Critical Path Finder + Phase 4 — Reporting[/dim]")
    con.print()
    con.print("  [dim]Fase 2 completada: CFG + DFG + Taint Propagation Engine.[/dim]")
    con.print()

    sys.exit(0 if ok_count == len(results) else 1)


if __name__ == "__main__":
    main()