"""
main.py — Demo de la Fase 1: Lexer + Parser + AST
==================================================

Ejecuta el frontend del compilador sobre cinco casos representativos:
  1. Asignación simple y llamada a función
  2. Concatenación directa de input() → SQLi clásico
  3. F-string con datos de usuario → SQLi moderno
  4. Printf-style ("%s" % val) → SQLi legacy
  5. Código con función, if y return (análisis interprocedural futuro)

Para cada caso muestra:
  - Los tokens producidos por el Lexer
  - El AST producido por el Parser (representación en árbol)
"""

import textwrap
from lexer  import Lexer, TokenStream
from parser import Parser


# ──────────────────────────────────────────────────────────────────────────────
# Casos de prueba
# ──────────────────────────────────────────────────────────────────────────────

CASES = {

    "1 · Asignación y llamada simple": """
x = 42
y = "hello"
print(x)
""",

    "2 · SQLi clásico — concatenación con input()": """
user_id = input("ID: ")
query = "SELECT * FROM users WHERE id = " + user_id
cursor.execute(query)
""",

    "3 · SQLi moderno — f-string": """
from flask import request

def get_user():
    name = request.args.get("name")
    query = f"SELECT * FROM users WHERE name = '{name}'"
    cursor.execute(query)
""",

    "4 · SQLi legacy — printf-style": """
username = request.form.get("user")
sql = "SELECT id FROM accounts WHERE login = '%s'" % username
db.execute(sql)
""",

    "5 · Función con sanitizador (ruta segura)": """
import re

def fetch_product(product_id):
    safe_id = int(product_id)
    query = "SELECT * FROM products WHERE id = " + str(safe_id)
    cursor.execute(query)
    return cursor.fetchone()
""",

    "6 · Acumulación con +=": """
base_query = "SELECT * FROM logs WHERE 1=1"
if user_filter:
    base_query += " AND user = '" + user_input + "'"
db.execute(base_query)
""",

}


# ──────────────────────────────────────────────────────────────────────────────
# Impresor de AST (visitante de representación textual)
# ──────────────────────────────────────────────────────────────────────────────

def print_ast(node, indent: int = 0, label: str = ""):
    """
    Imprime el AST de forma recursiva mostrando tipo de nodo,
    atributos escalares y posición en el fuente.
    """
    from ast_nodes import ASTNode

    prefix = "  " * indent
    name   = type(node).__name__

    # Atributos escalares relevantes (no hijos ASTNode ni listas)
    scalars = {}
    for k, v in node.__dict__.items():
        if k in ("line", "col"):
            continue
        if isinstance(v, ASTNode):
            continue
        if isinstance(v, list) and all(isinstance(i, ASTNode) for i in v):
            continue
        if v is not None and v != [] and v != "":
            scalars[k] = v

    scalar_str = "  ".join(f"{k}={v!r}" for k, v in scalars.items())
    loc_str    = f"  [{node.line}:{node.col}]"
    lbl        = f"{label}: " if label else ""

    print(f"{prefix}{lbl}\033[1;36m{name}\033[0m  {scalar_str}{loc_str}")

    # Hijos
    for k, v in node.__dict__.items():
        if k in ("line", "col"):
            continue
        if isinstance(v, ASTNode):
            print_ast(v, indent + 1, label=k)
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, ASTNode):
                    print_ast(item, indent + 1, label=f"{k}[{i}]")


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

def run_case(title: str, source: str):
    print("\n" + "═" * 72)
    print(f"  CASO: {title}")
    print("═" * 72)

    # ── Código fuente ────────────────────────────────────────────────────────
    print("\n📄  FUENTE:")
    for i, line in enumerate(source.strip().splitlines(), 1):
        print(f"  {i:>3} │ {line}")

    # ── Lexer ────────────────────────────────────────────────────────────────
    print("\n🔤  TOKENS:")
    try:
        lexer  = Lexer(source)
        tokens = list(lexer.tokenize())
    except Exception as e:
        print(f"  ✗ Error léxico: {e}")
        return

    for tok in tokens:
        print(f"  {tok.type.name:<22} {tok.value!r:<30} línea {tok.line}")

    # ── Parser → AST ─────────────────────────────────────────────────────────
    print("\n🌳  AST:")
    try:
        stream = TokenStream(tokens)
        tree   = Parser(stream).parse()
        print_ast(tree)
    except Exception as e:
        print(f"  ✗ Error de análisis: {e}")
        return

    print(f"\n  ✓ Parseado correctamente — {len(tree.body)} nodo(s) en el cuerpo del módulo")


def main():
    print("\n" + "╔" + "═" * 70 + "╗")
    print("║" + " " * 18 + "SECURITY LINTER — FASE 1" + " " * 28 + "║")
    print("║" + " " * 14 + "Lexer + Parser + AST  (Python subset)" + " " * 19 + "║")
    print("╚" + "═" * 70 + "╝")

    for title, source in CASES.items():
        run_case(title, source)

    print("\n\n" + "═" * 72)
    print("  Fase 1 completada. El AST está listo para las fases 2 y 3.")
    print("  Próximo: CFG Builder + DFG Builder + Taint Propagation Engine")
    print("═" * 72 + "\n")


if __name__ == "__main__":
    main()
