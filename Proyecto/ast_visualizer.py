"""
ast_visualizer.py — Generador de PNG formal estilo paper científico
====================================================================

Produce grafos del AST en blanco y negro con tipografía y estilo
apropiados para su inclusión en un artículo académico o tesis.

Convenciones visuales
---------------------
  Categoría                   Relleno    Borde       Forma
  ────────────────────────── ─────────  ──────────  ──────────
  Module (raíz)              #e8e8e8    2.5pt        box
  Sentencias estructurales   #f2f2f2    1.8pt        box
  Sentencias simples         #ffffff    1.2pt        box
  FCall / Attribute          #ffffff    1.8pt doble  box
  JoinedStr / PercentFormat  #ececec    1.5pt        box
  Variables (Name)           #ffffff    1.0pt        box
  Expresiones                #ffffff    0.8pt        box
  Literales                  #f5f5f5    0.8pt        ellipse

La leyenda se genera como un PNG independiente mediante render_legend().

Salidas
-------
  output/ast/   → un PNG por caso  (sin leyenda incorporada)
  output/legend/ → legend.png       (leyenda standalone)
"""

from __future__ import annotations

import os
from typing import Optional

import graphviz

from ast_nodes import ASTNode


# ──────────────────────────────────────────────────────────────────────────────
# Esquema visual formal (escala de grises)
# ──────────────────────────────────────────────────────────────────────────────

# (fillcolor, penwidth, peripheries, shape)
_STYLE: dict[str, tuple[str, str, str, str]] = {
    "Module":              ("#e8e8e8", "2.5", "1", "box"),
    "FunctionDef":         ("#f2f2f2", "1.8", "1", "box"),
    "IfStatement":         ("#f2f2f2", "1.8", "1", "box"),
    "ElifClause":          ("#f5f5f5", "1.2", "1", "box"),
    "WhileStatement":      ("#f2f2f2", "1.8", "1", "box"),
    "ForStatement":        ("#f2f2f2", "1.8", "1", "box"),
    "AssignStatement":     ("#ffffff", "1.2", "1", "box"),
    "AugAssignStatement":  ("#ffffff", "1.2", "1", "box"),
    "ExprStatement":       ("#ffffff", "1.0", "1", "box"),
    "ReturnStatement":     ("#ffffff", "1.0", "1", "box"),
    "ImportStatement":     ("#ffffff", "1.0", "1", "box"),
    "Param":               ("#ffffff", "0.8", "1", "box"),
    "FCall":               ("#ffffff", "1.8", "2", "box"),   # doble borde
    "Attribute":           ("#f8f8f8", "1.5", "2", "box"),   # doble borde
    "Subscript":           ("#f8f8f8", "1.5", "2", "box"),   # doble borde
    "JoinedStr":           ("#ececec", "1.5", "1", "box"),
    "FormattedValue":      ("#f0f0f0", "1.2", "1", "box"),
    "PercentFormat":       ("#ececec", "1.5", "1", "box"),
    "Name":                ("#ffffff", "1.0", "1", "box"),
    "BinaryOp":            ("#ffffff", "0.8", "1", "box"),
    "UnaryOp":             ("#ffffff", "0.8", "1", "box"),
    "BoolOp":              ("#ffffff", "0.8", "1", "box"),
    "Compare":             ("#ffffff", "0.8", "1", "box"),
    "Keyword":             ("#ffffff", "0.8", "1", "box"),
    "Tuple":               ("#fafafa", "0.8", "1", "box"),
    "PyList":              ("#fafafa", "0.8", "1", "box"),
    "Literal":             ("#f5f5f5", "0.8", "1", "ellipse"),
}

_DEFAULT_STYLE = ("#ffffff", "0.8", "1", "box")

_FONT_TITLE = "Times New Roman"
_FONT_MONO  = "Courier"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
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
    """Etiqueta HTML-like con cabecera sombreada, atributos y posición."""
    node_type = type(node).__name__

    rows = (
        f'<TR>'
        f'<TD ALIGN="CENTER" COLSPAN="2" BGCOLOR="#dddddd">'
        f'<B><FONT FACE="{_FONT_TITLE}" POINT-SIZE="11">{node_type}</FONT></B>'
        f'</TD></TR>'
    )
    for attr_name, attr_val in _scalar_attrs(node):
        rows += (
            f'<TR>'
            f'<TD ALIGN="LEFT">'
            f'<FONT FACE="{_FONT_TITLE}" POINT-SIZE="9"><I>{attr_name}</I></FONT>'
            f'</TD>'
            f'<TD ALIGN="LEFT">'
            f'<FONT FACE="{_FONT_MONO}" POINT-SIZE="9">{attr_val}</FONT>'
            f'</TD></TR>'
        )
    rows += (
        f'<TR>'
        f'<TD COLSPAN="2" ALIGN="RIGHT">'
        f'<FONT FACE="{_FONT_TITLE}" POINT-SIZE="8"><I>[{node.line}:{node.col}]</I></FONT>'
        f'</TD></TR>'
    )
    return (
        f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="1" '
        f'CELLPADDING="3">{rows}</TABLE>>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# Visualizador principal
# ──────────────────────────────────────────────────────────────────────────────

class ASTVisualizer:
    """
    Genera PNGs del AST en estilo paper científico.

    Métodos públicos
    ----------------
    render(root, filename, caption)  → PNG del AST sin leyenda
    render_legend(output_dir)        → PNG de leyenda standalone
    """

    def __init__(
        self,
        output_dir: str = "output/ast",
        dpi: int = 200,
        rankdir: str = "TB",
    ):
        self.output_dir = output_dir
        self.dpi        = dpi
        self.rankdir    = rankdir
        self._uid       = 0
        os.makedirs(output_dir, exist_ok=True)

    # ── Render del AST ────────────────────────────────────────────────────────

    def render(self, root: ASTNode, filename: str, caption: str = "") -> str:
        """
        Genera el PNG del AST para un nodo raíz dado.

        Parámetros
        ----------
        root     : Module node del parser
        filename : nombre base del archivo de salida (sin extensión)
        caption  : texto de pie de figura, p.ej. "Figure 2. AST for Case 2"

        Retorna la ruta absoluta del .png generado.
        """
        self._uid = 0
        g = graphviz.Digraph(name=filename, comment=f"AST — {filename}")
        self._configure_graph(g, caption)
        self._visit(g, root, parent_id=None, edge_label="")

        out_base = os.path.join(self.output_dir, filename)
        g.render(out_base, format="png", cleanup=True, quiet=True)
        return os.path.abspath(out_base + ".png")

    # ── Render de la leyenda standalone ──────────────────────────────────────

    @staticmethod
    def render_legend(output_dir: str = "output/legend", dpi: int = 200) -> str:
        """
        Genera un PNG independiente con la leyenda completa del esquema visual.
        No requiere un AST; puede invocarse una sola vez por ejecución.

        Parámetros
        ----------
        output_dir : directorio donde se guardará legend.png
        dpi        : resolución de salida

        Retorna la ruta absoluta del legend.png generado.
        """
        os.makedirs(output_dir, exist_ok=True)

        g = graphviz.Digraph(name="legend", comment="AST Visualizer — Legend")
        g.attr(
            rankdir   = "LR",
            bgcolor   = "white",
            fontname  = _FONT_TITLE,
            fontsize  = "11",
            splines   = "ortho",
            nodesep   = "0.35",
            ranksep   = "0.80",
            pad       = "0.6",
            dpi       = str(dpi),
            label     = (
                f'<<B><FONT FACE="{_FONT_TITLE}" POINT-SIZE="13">'
                f'Figure A. Node Classification Legend for AST Diagrams'
                f'</FONT></B>>'
            ),
            labelloc  = "t",
            labeljust = "c",
        )
        g.attr("node",
            fontname  = _FONT_TITLE,
            fontsize  = "10",
            fontcolor = "black",
            color     = "black",
            style     = "filled",
            margin    = "0.14,0.08",
        )
        g.attr("edge",
            color     = "black",
            fontname  = _FONT_TITLE,
            fontsize  = "9",
            arrowhead = "normal",
            arrowsize = "0.6",
            penwidth  = "0.8",
        )

        # ── Cada entrada: nodo de ejemplo + nodo de descripción ───────────────
        entries = [
            # (id, fill, penwidth, peripheries, shape, type_label, description)
            (
                "module",
                "#e8e8e8", "2.5", "1", "box",
                "Module",
                "Root node of the program.\nThick border signals hierarchy apex.",
            ),
            (
                "structural",
                "#f2f2f2", "1.8", "1", "box",
                "FunctionDef / IfStatement\nWhileStatement / ForStatement",
                "Structural control-flow statements.\nDefine block scope boundaries.",
            ),
            (
                "simple",
                "#ffffff", "1.2", "1", "box",
                "AssignStatement / AugAssignStatement\nReturnStatement / ImportStatement",
                "Simple statements.\nNo nested block structure.",
            ),
            (
                "sink",
                "#ffffff", "1.8", "2", "box",
                "FCall / Attribute / Subscript",
                "High-security-interest nodes (double border).\nPotential taint sources or SQL sinks.",
            ),
            (
                "strfmt",
                "#ececec", "1.5", "1", "box",
                "JoinedStr / PercentFormat\nFormattedValue",
                "String format constructs.\nCommon SQLi propagation paths.",
            ),
            (
                "name",
                "#ffffff", "1.0", "1", "box",
                "Name",
                "Identifier (variable reference).\nCarries taint state in Phase 2.",
            ),
            (
                "expr",
                "#ffffff", "0.8", "1", "box",
                "BinaryOp / UnaryOp\nBoolOp / Compare",
                "Arithmetic and logical expressions.\nPropagate taint transitively.",
            ),
            (
                "literal",
                "#f5f5f5", "0.8", "1", "ellipse",
                "Literal",
                "Constant value (str, int, float, bool, None).\nAlways taint-free by definition.",
            ),
        ]

        # Columna A: nodos de ejemplo
        # Columna B: descripción textual
        # Se usan subgrafos de rango para alinear por filas

        prev_ex = None
        for entry in entries:
            eid, fill, pw, peri, shape, type_lbl, desc = entry

            ex_id   = f"ex_{eid}"
            desc_id = f"desc_{eid}"

            # Nodo de ejemplo (replica el estilo real)
            ex_label = (
                f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="1" CELLPADDING="3">'
                f'<TR><TD ALIGN="CENTER" BGCOLOR="#dddddd">'
                f'<B><FONT FACE="{_FONT_TITLE}" POINT-SIZE="10">'
                f'{_esc(type_lbl)}</FONT></B></TD></TR>'
                f'<TR><TD ALIGN="LEFT">'
                f'<FONT FACE="{_FONT_MONO}" POINT-SIZE="8"><I>name</I> = \'example\'</FONT>'
                f'</TD></TR>'
                f'<TR><TD ALIGN="RIGHT">'
                f'<FONT FACE="{_FONT_TITLE}" POINT-SIZE="7"><I>[line:col]</I></FONT>'
                f'</TD></TR>'
                f'</TABLE>>'
            )
            g.node(
                ex_id,
                label       = ex_label,
                shape       = shape,
                fillcolor   = fill,
                penwidth    = pw,
                peripheries = peri,
                color       = "black",
                width       = "2.6",
            )

            # Nodo de descripción textual (sin borde especial)
            desc_escaped = _esc(desc).replace("\\n", "<BR/>")
            desc_label = (
                f'<<FONT FACE="{_FONT_TITLE}" POINT-SIZE="9">'
                f'{desc_escaped}'
                f'</FONT>>'
            )
            g.node(
                desc_id,
                label     = desc_label,
                shape     = "plaintext",
                fillcolor = "white",
                penwidth  = "0",
                width     = "3.6",
            )

            # Arista de ejemplo → descripción
            g.edge(ex_id, desc_id,
                   arrowhead="none",
                   penwidth="0.6",
                   style="dashed",
                   color="#555555")

            # Arista invisible entre filas para controlar el orden vertical
            if prev_ex:
                g.edge(prev_ex, ex_id, style="invis")

            prev_ex = ex_id

        out_base = os.path.join(output_dir, "legend")
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
            label     = label_attr,
            labelloc  = "b",
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

    # ── Recorrido recursivo del AST ───────────────────────────────────────────

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
