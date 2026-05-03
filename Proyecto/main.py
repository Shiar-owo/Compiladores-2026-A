"""
main.py — Security Linter — Fase 1 + Fase 2
============================================

Fase 1: "No reimplementa el lexer ni el parser; consume directamente el AST
producido por el compilador huésped."

Fase 2: Análisis semántico extendido (núcleo del linter)
- CFG Builder modela todos los caminos de ejecución posibles
- DFG Builder rastrea cómo los valores fluyen de variable en variable
- Taint Propagation Engine marca variables de fuentes controladas por usuario

Estructura de directorios
--------------------------
  samples/          ← código fuente de entrada (un .py por caso)
  output/
  │   ├── ast/          ← AST PNG
  │   ├── cfg/          ← CFG PNG (NUEVO)
  │   ├── dfg/          ← DFG PNG (NUEVO)
  │   └── legend/       ← leyendas

Pipeline por cada archivo en samples/
--------------------------------------
  1. Leer el .py desde samples/
  2. AST Consumer → AST (Module)
  3. CFG Builder → CFG → output/cfg/
  4. DFG Builder → DFG → output/dfg/
  5. Symbol Table + Taint Engine
  6. Exportar AST, CFG, DFG como PNG
"""

import os
import sys

from rich.console import Console
from rich.panel   import Panel
from rich.rule    import Rule
from rich.text    import Text

from ast_consumer    import ASTConsumer
from ast_printer     import print_ast_tree
from ast_visualizer  import ASTVisualizer
from cfg_builder     import CFGBuilder
from cfg_visualizer  import CFGVisualizer
from dfg_builder    import DFGBuilder
from dfg_visualizer import DFGVisualizer
from symbol_table   import SymbolTable
from taint_engine  import TaintPropagationEngine

con = Console()

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(BASE_DIR, "samples")
AST_DIR     = os.path.join(BASE_DIR, "output", "ast")
CFG_DIR     = os.path.join(BASE_DIR, "output", "cfg")
DFG_DIR     = os.path.join(BASE_DIR, "output", "dfg")
LEGEND_DIR  = os.path.join(BASE_DIR, "output", "legend")

CASE_META: dict[str, str] = {
    "case1_simple_assignment.py":    "Figure 1. Simple Assignment (Safe)",
    "case2_sqli_concatenation.py":   "Figure 2. SQLi via String Concatenation",
    "case3_sqli_fstring.py":         "Figure 3. SQLi via f-string (Flask)",
    "case4_sqli_printf.py":         "Figure 4. SQLi via printf-style",
    "case5_safe_sanitizer.py":     "Figure 5. Safe Path with int() Sanitizer",
    "case6_augassign_conditional.py":"Figure 6. Conditional SQLi via AugAssign",
}


def run_case(
    sample_path: str,
    caption: str,
    ast_viz: ASTVisualizer,
    cfg_viz: CFGVisualizer,
    dfg_viz: DFGVisualizer,
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

    con.print(Rule("[dim cyan]🌳  AST[/dim cyan]", style="dim white"))
    print_ast_tree(tree, con=con)
    con.print(f"  [green]✓[/green] AST: {len(tree.body)} statements, {_count_nodes(tree)} nodes")

    con.print(Rule("[dim cyan]🔗  CFG Build[/dim cyan]", style="dim white"))
    cfg_builder = CFGBuilder()
    try:
        cfg = cfg_builder.build(tree)
        con.print(f"  [green]✓[/green] CFG built — {len(cfg.nodes)} nodes")
    except Exception as exc:
        con.print(f"  [bold red]✗ CFG error:[/bold red] {exc}")
        cfg = None

    con.print(Rule("[dim cyan]🔗  DFG Build[/dim cyan]", style="dim white"))
    dfg_builder = DFGBuilder()
    try:
        dfg = dfg_builder.build(tree)
        con.print(f"  [green]✓[/green] DFG built — {len(dfg.nodes)} nodes, {len(dfg.edges)} edges")
    except Exception as exc:
        con.print(f"  [bold red]✗ DFG error:[/bold red] {exc}")
        dfg = None

    con.print(Rule("[dim cyan]🔍  Taint Analysis[/dim cyan]", style="dim white"))
    symbol_table = SymbolTable()
    taint_engine = TaintPropagationEngine()
    try:
        if dfg:
            taint_result = taint_engine.analyze(tree, dfg, symbol_table)
            if taint_result.sources:
                con.print(f"  [yellow]⚠[/yellow] Taint sources:")
                for rec in taint_result.sources:
                    con.print(f"    • {rec.variable} @ line {rec.line} (source: {rec.source})")
            elif taint_result.propagations:
                con.print(f"  [yellow]↪[/yellow] Propagations: {len(taint_result.propagations)}")
            else:
                con.print(f"  [green]✓[/green] No taint detected")
        else:
            con.print(f"  [dim]Skipped (no DFG)[/dim]")
    except Exception as exc:
        con.print(f"  [bold red]✗ Taint error:[/bold red] {exc}")

    outputs = []

    try:
        png = ast_viz.render(tree, filename=slug, caption=caption)
        outputs.append(("AST", os.path.relpath(png, BASE_DIR)))
    except Exception as exc:
        con.print(f"  [red]✗ AST PNG: {exc}[/red]")

    try:
        if cfg:
            png = cfg_viz.render(cfg, filename=slug, caption=caption)
            outputs.append(("CFG", os.path.relpath(png, BASE_DIR)))
    except Exception as exc:
        con.print(f"  [red]✗ CFG PNG: {exc}[/red]")

    try:
        if dfg:
            png = dfg_viz.render(dfg, filename=slug, caption=caption)
            outputs.append(("DFG", os.path.relpath(png, BASE_DIR)))
    except Exception as exc:
        con.print(f"  [red]✗ DFG PNG: {exc}[/red]")

    for label, path in outputs:
        con.print(f"  [green]✓[/green] {label} → [cyan]{path}[/cyan]")

    return bool(outputs)


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
            "[dim white]CFG + DFG + Taint + Visualization[/dim white]\n\n"
            f"[dim white]samples/ → output/ast/ | cfg/ | dfg/[/dim white]",
            border_style="cyan",
            expand=False,
            padding=(1, 4),
        )
    )

    os.makedirs(CFG_DIR, exist_ok=True)
    os.makedirs(DFG_DIR, exist_ok=True)

    if not os.path.isdir(SAMPLES_DIR):
        con.print(f"[bold red]✗ samples/ not found[/bold red]")
        sys.exit(1)

    ast_viz = ASTVisualizer(output_dir=AST_DIR, dpi=200, rankdir="TB")
    cfg_viz = CFGVisualizer(output_dir=CFG_DIR, dpi=200, rankdir="TB")
    dfg_viz = DFGVisualizer(output_dir=DFG_DIR, dpi=200, rankdir="LR")
    consumer = ASTConsumer()

    results = []
    for filename, caption in CASE_META.items():
        path = os.path.join(SAMPLES_DIR, filename)
        if not os.path.isfile(path):
            con.print(f"  [yellow]⚠ Skipping: {filename}[/yellow]")
            results.append((caption, False))
            continue
        ok = run_case(path, caption, ast_viz, cfg_viz, dfg_viz, consumer)
        results.append((caption, ok))

    con.print()
    con.print(Rule("[bold white]Summary[/bold white]", style="dim white"))
    ok_count = sum(1 for _, ok in results if ok)
    for caption, ok in results:
        icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
        label = caption.split(". ", 1)[-1]
        con.print(f"  {icon}  {label}")

    con.print()
    con.print(f"  [bold]{ok_count}/{len(results)}[/bold] cases")
    con.print(f"  AST → [cyan]{os.path.relpath(AST_DIR, BASE_DIR)}/[/cyan]")
    con.print(f"  CFG → [cyan]{os.path.relpath(CFG_DIR, BASE_DIR)}/[/cyan]")
    con.print(f"  DFG → [cyan]{os.path.relpath(DFG_DIR, BASE_DIR)}/[/cyan]")
    con.print()
    con.print("  [dim]Fase 2 completada.[/dim]")
    con.print()

    sys.exit(0 if ok_count == len(results) else 1)


if __name__ == "__main__":
    main()