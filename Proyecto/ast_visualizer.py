"""
ast_visualizer.py — Generador de PNG formal estilo paper científico
====================================================================

Produce grafos del AST en blanco y negro con tipografía y estilo
apropiados para su inclusión en un artículo académico o tesis:

  • Fondo blanco puro (#ffffff)
  • Nodos con borde negro sólido, fill blanco o gris muy claro
  • Tipografía Times New Roman (serif) para el cuerpo del nodo,
    Courier para valores literales y operadores
  • Distinción visual por categoría semántica usando solo:
      – Grosor de borde  (nodos de alto interés: borde doble)
      – Tono de gris     (blanco puro → gris claro → gris medio)
      – Forma del nodo   (box para sentencias, ellipse para literales)
  • Aristas en negro con punta de flecha triangular rellena
  • Sin color: totalmente imprimible en B/N sin pérdida de información
  • Leyenda integrada al pie del grafo

Categorías visuales
-------------------
  Categoría                   Relleno    Borde       Forma
  ────────────────────────── ─────────  ──────────  ───────────
  Module (raíz)              #f0f0f0    negro 2.5   box
  Sentencias estructurales   #f8f8f8    negro 1.5   box
  Sentencias simples         #ffffff    negro 1.0   box
  FCall / Attribute          #ffffff    negro 2.0   box (doble*)
  JoinedStr / PercentFormat  #ececec    negro 1.5   box
  Name (variable)            #ffffff    negro 1.0   box
  Expresiones                #ffffff    negro 0.8   box
  Literal                    #f5f5f5    negro 0.6   ellipse

  (*) doble borde se logra vía peripheries=2 en Graphviz

Cada nodo muestra:
  TIPO_NODO          ← Times New Roman 11pt negrita
  campo = valor      ← Times New Roman 9pt regular
  [línea:col]        ← Times New Roman 8pt itálica
"""

from __future__ import annotations

import os
from typing import Optional

import graphviz

from ast_nodes import ASTNode


# ──────────────────────────────────────────────────────────────────────────────
# Esquema visual formal (solo grises + negro)
# ──────────────────────────────────────────────────────────────────────────────

# (fillcolor, penwidth, peripheries, shape)
_STYLE: dict[str, tuple[str, str, str, str]] = {
    # Raíz
    "Module":              ("#e8e8e8", "2.5", "1", "box"),

    # Sentencias estructurales
    "FunctionDef":         ("#f2f2f2", "1.8", "1", "box"),
    "IfStatement":         ("#f2f2f2", "1.8", "1", "box"),
    "ElifClause":          ("#f5f5f5", "1.2", "1", "box"),
    "WhileStatement":      ("#f2f2f2", "1.8", "1", "box"),
    "ForStatement":        ("#f2f2f2", "1.8", "1", "box"),

    # Sentencias simples
    "AssignStatement":     ("#ffffff", "1.2", "1", "box"),
    "AugAssignStatement":  ("#ffffff", "1.2", "1", "box"),
    "ExprStatement":       ("#ffffff", "1.0", "1", "box"),
    "ReturnStatement":     ("#ffffff", "1.0", "1", "box"),
    "ImportStatement":     ("#ffffff", "1.0", "1", "box"),
    "Param":               ("#ffffff", "0.8", "1", "box"),

    # Interés de seguridad ALTO — borde doble
    "FCall":               ("#ffffff", "1.8", "2", "box"),
    "Attribute":           ("#f8f8f8", "1.5", "2", "box"),
    "Subscript":           ("#f8f8f8", "1.5", "2", "box"),

    # Construcciones de cadena — sombreado leve
    "JoinedStr":           ("#ececec", "1.5", "1", "box"),
    "FormattedValue":      ("#f0f0f0", "1.2", "1", "box"),
    "PercentFormat":       ("#ececec", "1.5", "1", "box"),

    # Variables
    "Name":                ("#ffffff", "1.0", "1", "box"),

    # Expresiones aritméticas / lógicas
    "BinaryOp":            ("#ffffff", "0.8", "1", "box"),
    "UnaryOp":             ("#ffffff", "0.8", "1", "box"),
    "BoolOp":              ("#ffffff", "0.8", "1", "box"),
    "Compare":             ("#ffffff", "0.8", "1", "box"),
    "Keyword":             ("#ffffff", "0.8", "1", "box"),
    "Tuple":               ("#fafafa", "0.8", "1", "box"),
    "PyList":              ("#fafafa", "0.8", "1", "box"),

    # Literales — forma elipse para distinguirlos visualmente
    "Literal":             ("#f5f5f5", "0.8", "1", "ellipse"),
}

_DEFAULT_STYLE = ("#ffffff", "0.8", "1", "box")

# Fuentes formales
_FONT_TITLE  = "Times New Roman"
_FONT_BODY   = "Times New Roman"
_FONT_MONO   = "Courier"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Escapa caracteres especiales para etiquetas HTML de Graphviz."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _trunc(value: str, n: int = 30) -> str:
    s = str(value)
    return s if len(s) <= n else s[: n - 1] + "…"


def _scalar_attrs(node: ASTNode) -> list[tuple[str, str]]:
    """Devuelve (nombre, valor_repr) de los atributos escalares del nodo."""
    result = []
    for k, v in node.__dict__.items():
        if k in ("line", "col"):
            continue
        if isinstance(v, ASTNode):
            continue
        if isinstance(v, list) and any(isinstance(i, ASTNode) for i in v):
            continue
        if v is None or v == [] or v == "":
            continue
        result.append((k, _trunc(_esc(repr(v)))))
    return result


def _children(node: ASTNode) -> list[tuple[str, ASTNode]]:
    """Devuelve (etiqueta, nodo_hijo) para todos los hijos ASTNode del nodo."""
    result = []
    for k, v in node.__dict__.items():
        if k in ("line", "col"):
            continue
        if isinstance(v, ASTNode):
            result.append((k, v))
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, ASTNode):
                    result.append((f"{k}[{i}]", item))
    return result


def _make_label(node: ASTNode) -> str:
    """
    Construye la etiqueta HTML-like formal del nodo.

    Estructura:
      ┌─────────────────────────────┐
      │  TIPO_NODO                  │  ← negrita, Times New Roman 11pt
      ├─────────────────────────────┤
      │  campo    valor             │  ← 9pt, Courier para el valor
      ├─────────────────────────────┤
      │              [línea:col]    │  ← 8pt itálica
      └─────────────────────────────┘
    """
    node_type = type(node).__name__

    # Fila de tipo
    rows = (
        f'<TR>'
        f'<TD ALIGN="CENTER" COLSPAN="2" BGCOLOR="#dddddd">'
        f'<B><FONT FACE="{_FONT_TITLE}" POINT-SIZE="11">{node_type}</FONT></B>'
        f'</TD>'
        f'</TR>'
    )

    # Filas de atributos escalares
    for attr_name, attr_val in _scalar_attrs(node):
        rows += (
            f'<TR>'
            f'<TD ALIGN="LEFT">'
            f'<FONT FACE="{_FONT_BODY}" POINT-SIZE="9"><I>{attr_name}</I></FONT>'
            f'</TD>'
            f'<TD ALIGN="LEFT">'
            f'<FONT FACE="{_FONT_MONO}" POINT-SIZE="9">{attr_val}</FONT>'
            f'</TD>'
            f'</TR>'
        )

    # Fila de posición
    rows += (
        f'<TR>'
        f'<TD COLSPAN="2" ALIGN="RIGHT">'
        f'<FONT FACE="{_FONT_BODY}" POINT-SIZE="8"><I>[{node.line}:{node.col}]</I></FONT>'
        f'</TD>'
        f'</TR>'
    )

    return (
        f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="1" '
        f'CELLPADDING="3">{rows}</TABLE>>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# Visualizador
# ──────────────────────────────────────────────────────────────────────────────

class ASTVisualizer:
    """
    Genera un grafo Graphviz del AST en estilo paper científico y lo
    exporta como .png con fondo blanco, tipografía serif y escala de grises.

    Parámetros
    ----------
    output_dir : str   Directorio destino de los PNGs.
    dpi        : int   Resolución (default 200 para calidad de impresión).
    rankdir    : str   "TB" (top→bottom) o "LR" (left→right).
    title      : str   Título opcional que aparece como caption bajo el grafo.
    """

    def __init__(
        self,
        output_dir: str = "output",
        dpi: int = 200,
        rankdir: str = "TB",
    ):
        self.output_dir = output_dir
        self.dpi        = dpi
        self.rankdir    = rankdir
        self._uid       = 0
        os.makedirs(output_dir, exist_ok=True)

    # ── API pública ───────────────────────────────────────────────────────────

    def render(self, root: ASTNode, filename: str, caption: str = "") -> str:
        """
        Genera el grafo del AST y lo guarda como <output_dir>/<filename>.png.

        Parámetros
        ----------
        root     : nodo raíz del AST (Module)
        filename : nombre base del archivo (sin extensión)
        caption  : texto de pie de figura (ej. "Figure 3: AST for Case 2")

        Retorna la ruta absoluta del .png generado.
        """
        self._uid = 0

        g = graphviz.Digraph(name=filename, comment=f"AST — {filename}")
        self._configure_graph(g, caption)
        self._add_legend(g)
        self._visit(g, root, parent_id=None, edge_label="")

        out_base = os.path.join(self.output_dir, filename)
        g.render(out_base, format="png", cleanup=True, quiet=True)
        return os.path.abspath(out_base + ".png")

    # ── Configuración global del grafo ────────────────────────────────────────

    def _configure_graph(self, g: graphviz.Digraph, caption: str):
        label_attr = ""
        if caption:
            label_attr = (
                f'<<FONT FACE="{_FONT_TITLE}" POINT-SIZE="11">'
                f'<I>{_esc(caption)}</I></FONT>>'
            )

        g.attr(
            rankdir   = self.rankdir,
            bgcolor   = "white",
            fontname  = _FONT_TITLE,
            fontsize  = "11",
            splines   = "ortho",
            nodesep   = "0.40",
            ranksep   = "0.55",
            pad       = "0.5",
            dpi       = str(self.dpi),
            label     = label_attr if caption else "",
            labelloc  = "b",           # caption al pie
            labeljust = "c",
        )
        g.attr("node",
            fontname  = _FONT_TITLE,
            fontsize  = "10",
            fontcolor = "black",
            color     = "black",
            style     = "filled",
            margin    = "0.10,0.06",
        )
        g.attr("edge",
            color     = "black",
            fontname  = _FONT_TITLE,
            fontsize  = "8",
            fontcolor = "#333333",
            arrowsize = "0.6",
            penwidth  = "0.8",
            arrowhead = "normal",
        )

    # ── Leyenda ───────────────────────────────────────────────────────────────

    def _add_legend(self, g: graphviz.Digraph):
        """
        Añade un subgrafo de leyenda en la esquina inferior derecha.
        Explica las convenciones visuales del grafo.
        """
        with g.subgraph(name="cluster_legend") as leg:
            leg.attr(
                label     = (
                    f'<<B><FONT FACE="{_FONT_TITLE}" POINT-SIZE="9">'
                    f'Legend</FONT></B>>'
                ),
                style     = "solid",
                color     = "black",
                penwidth  = "0.8",
                fontname  = _FONT_TITLE,
                fontsize  = "9",
                bgcolor   = "white",
            )

            entries = [
                ("leg_root",   "#e8e8e8", "1",   "1", "box",     "Module (root)"),
                ("leg_struct", "#f2f2f2", "1.8", "1", "box",     "Structural stmt."),
                ("leg_simple", "#ffffff", "1.2", "1", "box",     "Simple stmt."),
                ("leg_fcall",  "#ffffff", "1.8", "2", "box",     "FCall / Sink  (double border)"),
                ("leg_str",    "#ececec", "1.5", "1", "box",     "String format expr."),
                ("leg_lit",    "#f5f5f5", "0.8", "1", "ellipse", "Literal"),
            ]

            prev = None
            for nid, fill, pw, peri, shape, lbl in entries:
                leg.node(
                    nid,
                    label       = (
                        f'<<FONT FACE="{_FONT_TITLE}" POINT-SIZE="8">'
                        f'{lbl}</FONT>>'
                    ),
                    shape       = shape,
                    fillcolor   = fill,
                    penwidth    = pw,
                    peripheries = peri,
                    style       = "filled",
                    color       = "black",
                    width       = "2.0",
                    height      = "0.30",
                    fixedsize   = "false",
                )
                if prev:
                    leg.edge(prev, nid, style="invis")
                prev = nid

    # ── Recorrido recursivo ───────────────────────────────────────────────────

    def _next_id(self) -> str:
        self._uid += 1
        return f"n{self._uid}"

    def _visit(
        self,
        g: graphviz.Digraph,
        node: ASTNode,
        parent_id: Optional[str],
        edge_label: str,
    ) -> str:
        node_id   = self._next_id()
        node_type = type(node).__name__
        fill, pw, peri, shape = _STYLE.get(node_type, _DEFAULT_STYLE)

        g.node(
            node_id,
            label       = _make_label(node),
            shape       = shape,
            fillcolor   = fill,
            penwidth    = pw,
            peripheries = peri,
            color       = "black",
        )

        if parent_id is not None:
            g.edge(
                parent_id,
                node_id,
                label = (
                    f'<<FONT FACE="{_FONT_TITLE}" POINT-SIZE="8">'
                    f'<I>{_esc(edge_label)}</I></FONT>>'
                ),
            )

        for field_label, child in _children(node):
            self._visit(g, child, node_id, field_label)

        return node_id
