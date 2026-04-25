"""
lexer.py — Tokenizador para el subconjunto de Python
=====================================================

Convierte código fuente en una secuencia de tokens con posición exacta
(línea, columna) para mensajes de error precisos en el reporte de seguridad.

Tokens reconocidos
------------------
  Literales:    STRING, FSTRING_START, FSTRING_END, FSTRING_EXPR_START,
                FSTRING_EXPR_END, INTEGER, FLOAT, BOOL, NONE
  Identificadores y palabras clave: NAME, + keywords individuales
  Operadores:   PLUS, MINUS, STAR, SLASH, PERCENT, DOUBLESLASH, DOUBLESTAR,
                EQ, NEQ, LT, GT, LEQ, GEQ, AND, OR, NOT, IN, IS,
                ASSIGN, PLUSEQ, MINUSEQ, STAREQ, SLASHEQ, PERCENTEQ,
                DOT, COMMA, COLON, LPAREN, RPAREN, LBRACKET, RBRACKET
  Control:      NEWLINE, INDENT, DEDENT, EOF

Diseño
------
- Indentación significativa: el lexer emite INDENT / DEDENT tal como
  hace CPython, para que el parser pueda construir bloques correctamente.
- Los f-strings se descomponen en tokens estructurados para que el parser
  pueda construir nodos JoinedStr / FormattedValue directamente.
- El lexer es un iterador perezoso: produce tokens de uno en uno, lo que
  permite al parser pedir el siguiente token sin cargar todo en memoria.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Iterator, List, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Tipos de token
# ──────────────────────────────────────────────────────────────────────────────

class TT(Enum):
    """Token Type — enumeración de todos los tipos de token."""
    # Literales
    STRING          = auto()
    FSTRING_START   = auto()   # f"  o  f'
    FSTRING_PART    = auto()   # texto literal dentro del f-string
    FSTRING_EXPR_START = auto() # {
    FSTRING_EXPR_END   = auto() # }
    FSTRING_END     = auto()   # cierre de comilla del f-string
    INTEGER         = auto()
    FLOAT           = auto()
    BOOL            = auto()
    NONE            = auto()
    # Identificador / keywords
    NAME            = auto()
    # Keywords (se derivan de NAME durante el escaneo)
    KW_DEF          = auto()
    KW_RETURN       = auto()
    KW_IF           = auto()
    KW_ELIF         = auto()
    KW_ELSE         = auto()
    KW_WHILE        = auto()
    KW_FOR          = auto()
    KW_IN           = auto()
    KW_IMPORT       = auto()
    KW_FROM         = auto()
    KW_AND          = auto()
    KW_OR           = auto()
    KW_NOT          = auto()
    KW_IS           = auto()
    KW_NONE         = auto()
    KW_TRUE         = auto()
    KW_FALSE        = auto()
    KW_PASS         = auto()
    KW_BREAK        = auto()
    KW_CONTINUE     = auto()
    # Operadores aritméticos / cadena
    PLUS            = auto()   # +
    MINUS           = auto()   # -
    STAR            = auto()   # *
    SLASH           = auto()   # /
    PERCENT         = auto()   # %
    DOUBLESLASH     = auto()   # //
    DOUBLESTAR      = auto()   # **
    # Operadores de comparación
    EQ              = auto()   # ==
    NEQ             = auto()   # !=
    LT              = auto()   # <
    GT              = auto()   # >
    LEQ             = auto()   # <=
    GEQ             = auto()   # >=
    # Asignación
    ASSIGN          = auto()   # =
    PLUSEQ          = auto()   # +=
    MINUSEQ         = auto()   # -=
    STAREQ          = auto()   # *=
    SLASHEQ         = auto()   # /=
    PERCENTEQ       = auto()   # %=
    # Delimitadores
    DOT             = auto()   # .
    COMMA           = auto()   # ,
    COLON           = auto()   # :
    LPAREN          = auto()   # (
    RPAREN          = auto()   # )
    LBRACKET        = auto()   # [
    RBRACKET        = auto()   # ]
    # Control de estructura
    NEWLINE         = auto()
    INDENT          = auto()
    DEDENT          = auto()
    EOF             = auto()


KEYWORDS: dict[str, TT] = {
    "def":      TT.KW_DEF,
    "return":   TT.KW_RETURN,
    "if":       TT.KW_IF,
    "elif":     TT.KW_ELIF,
    "else":     TT.KW_ELSE,
    "while":    TT.KW_WHILE,
    "for":      TT.KW_FOR,
    "in":       TT.KW_IN,
    "import":   TT.KW_IMPORT,
    "from":     TT.KW_FROM,
    "and":      TT.KW_AND,
    "or":       TT.KW_OR,
    "not":      TT.KW_NOT,
    "is":       TT.KW_IS,
    "None":     TT.KW_NONE,
    "True":     TT.KW_TRUE,
    "False":    TT.KW_FALSE,
    "pass":     TT.KW_PASS,
    "break":    TT.KW_BREAK,
    "continue": TT.KW_CONTINUE,
}


# ──────────────────────────────────────────────────────────────────────────────
# Token
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Token:
    type:   TT
    value:  str
    line:   int
    col:    int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.col})"


# ──────────────────────────────────────────────────────────────────────────────
# Errores léxicos
# ──────────────────────────────────────────────────────────────────────────────

class LexerError(Exception):
    def __init__(self, msg: str, line: int, col: int):
        super().__init__(f"[Línea {line}, Col {col}] Error léxico: {msg}")
        self.line = line
        self.col  = col


# ──────────────────────────────────────────────────────────────────────────────
# Lexer
# ──────────────────────────────────────────────────────────────────────────────

class Lexer:
    """
    Tokenizador de un solo paso.

    Uso:
        lexer  = Lexer(source_code)
        tokens = list(lexer.tokenize())

    El método tokenize() es un generador: produce tokens de uno en uno.
    """

    def __init__(self, source: str):
        self.source   = source
        self.pos      = 0
        self.line     = 1
        self.col      = 1
        # Pila de niveles de indentación (en espacios); empieza en 0.
        self._indent_stack: List[int] = [0]
        # Conteo de paréntesis/corchetes abiertos: cuando > 0, las
        # newlines son implícitas y se ignoran (continuación de línea).
        self._paren_depth = 0

    # ── Navegación por el fuente ──────────────────────────────────────────────

    @property
    def _current(self) -> str:
        """Carácter actual o '' si llegamos al final."""
        return self.source[self.pos] if self.pos < len(self.source) else ""

    def _peek(self, offset: int = 1) -> str:
        i = self.pos + offset
        return self.source[i] if i < len(self.source) else ""

    def _advance(self) -> str:
        """Consume el carácter actual y actualiza línea/columna."""
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col   = 1
        else:
            self.col += 1
        return ch

    def _match(self, expected: str) -> bool:
        """Consume el carácter actual si coincide con expected."""
        if self._current == expected:
            self._advance()
            return True
        return False

    # ── Generador principal ───────────────────────────────────────────────────

    def tokenize(self) -> Iterator[Token]:
        """
        Genera todos los tokens del fuente.
        Al final emite los DEDENT pendientes y luego EOF.
        """
        at_line_start = True   # ¿estamos al inicio de una línea lógica?

        while self.pos < len(self.source):
            # 1. Inicio de línea: gestionar indentación
            if at_line_start:
                indent_tokens = list(self._handle_indent())
                for tok in indent_tokens:
                    yield tok
                at_line_start = False
                if self.pos >= len(self.source):
                    break
                # Si la línea completa era un comentario o estaba vacía,
                # _handle_indent habrá consumido hasta el final de línea.
                continue

            ch = self._current
            line, col = self.line, self.col

            # 2. Espacios y tabulaciones (dentro de una línea)
            if ch in (" ", "\t"):
                self._advance()
                continue

            # 3. Comentarios
            if ch == "#":
                while self._current and self._current != "\n":
                    self._advance()
                continue

            # 4. Fin de línea lógica
            if ch == "\n":
                self._advance()
                if self._paren_depth == 0:
                    yield Token(TT.NEWLINE, "\n", line, col)
                    at_line_start = True
                continue

            # 5. Barra invertida: continuación de línea explícita
            if ch == "\\" and self._peek() == "\n":
                self._advance()   # \
                self._advance()   # \n
                continue

            # 6. F-strings
            if ch in ("f", "F") and self._peek() in ('"', "'"):
                yield from self._scan_fstring(line, col)
                continue

            # 7. Strings normales
            if ch in ('"', "'"):
                yield self._scan_string(line, col)
                continue

            # 8. Números
            if ch.isdigit() or (ch == "." and self._peek().isdigit()):
                yield self._scan_number(line, col)
                continue

            # 9. Identificadores y keywords
            if ch.isalpha() or ch == "_":
                yield self._scan_name(line, col)
                continue

            # 10. Operadores y delimitadores
            tok = self._scan_operator(line, col)
            if tok is not None:
                # Rastrear profundidad de paréntesis / corchetes
                if tok.type in (TT.LPAREN, TT.LBRACKET):
                    self._paren_depth += 1
                elif tok.type in (TT.RPAREN, TT.RBRACKET):
                    self._paren_depth = max(0, self._paren_depth - 1)
                yield tok
                continue

            raise LexerError(
                f"Carácter inesperado: {ch!r}", self.line, self.col
            )

        # Fin del fuente: cerrar todos los niveles de indentación abiertos
        if self._indent_stack[-1] > 0:
            yield Token(TT.NEWLINE, "", self.line, self.col)
        while len(self._indent_stack) > 1:
            self._indent_stack.pop()
            yield Token(TT.DEDENT, "", self.line, self.col)

        yield Token(TT.EOF, "", self.line, self.col)

    # ── Indentación ───────────────────────────────────────────────────────────

    def _handle_indent(self) -> Iterator[Token]:
        """
        Llamado al inicio de cada línea lógica.
        Mide los espacios iniciales y emite INDENT / DEDENT según corresponda.
        Omite líneas vacías y líneas de solo comentario.
        """
        line, col = self.line, self.col

        # Contar espacios iniciales (4 espacios = 1 nivel en Python estándar,
        # pero respetamos cualquier cantidad consistente)
        spaces = 0
        while self._current == " ":
            spaces += 1
            self._advance()
        # Tabs: convertir a espacios (1 tab = 8 en CPython, usamos 4)
        while self._current == "\t":
            spaces += 4
            self._advance()

        # ¿Línea vacía o solo comentario? → saltar sin emitir INDENT/DEDENT
        if self._current in ("\n", "#", ""):
            while self._current and self._current != "\n":
                self._advance()
            if self._current == "\n":
                self._advance()
            return

        # Si estamos dentro de paréntesis, la indentación es irrelevante
        if self._paren_depth > 0:
            return

        current_level = self._indent_stack[-1]

        if spaces > current_level:
            self._indent_stack.append(spaces)
            yield Token(TT.INDENT, " " * spaces, line, 1)

        elif spaces < current_level:
            while self._indent_stack[-1] > spaces:
                self._indent_stack.pop()
                yield Token(TT.DEDENT, "", line, 1)
            if self._indent_stack[-1] != spaces:
                raise LexerError(
                    "Nivel de indentación inconsistente", line, 1
                )
        # spaces == current_level: misma indentación, no se emite nada

    # ── Strings ───────────────────────────────────────────────────────────────

    def _scan_string(self, line: int, col: int) -> Token:
        """
        Reconoce cadenas simples y dobles (no f-strings).
        Soporta strings de triple comilla (multilinea).
        """
        quote = self._advance()   # ' o "

        # Triple comilla
        if self._current == quote and self._peek() == quote:
            self._advance()
            self._advance()
            return self._scan_triple_string(quote, line, col)

        # Cadena de una sola línea
        buf = ""
        while self._current and self._current != quote:
            if self._current == "\\":
                buf += self._scan_escape()
            else:
                buf += self._advance()
        if not self._current:
            raise LexerError("Cadena sin cerrar", line, col)
        self._advance()   # cierre de comilla
        return Token(TT.STRING, buf, line, col)

    def _scan_triple_string(self, quote: str, line: int, col: int) -> Token:
        """Cadena de triple comilla."""
        buf   = ""
        end   = quote * 3
        while self.pos < len(self.source):
            if self.source[self.pos:self.pos + 3] == end:
                self._advance(); self._advance(); self._advance()
                return Token(TT.STRING, buf, line, col)
            if self._current == "\\":
                buf += self._scan_escape()
            else:
                buf += self._advance()
        raise LexerError("String triple sin cerrar", line, col)

    def _scan_escape(self) -> str:
        """Procesa una secuencia de escape \\x."""
        self._advance()  # consume '\'
        ch = self._advance()
        return {
            "n": "\n", "t": "\t", "r": "\r",
            "\\": "\\", "'": "'", '"': '"', "0": "\0",
        }.get(ch, "\\" + ch)

    # ── F-strings ─────────────────────────────────────────────────────────────

    def _scan_fstring(self, line: int, col: int) -> Iterator[Token]:
        """
        Descompone un f-string en:
          FSTRING_START  →  f"
          FSTRING_PART   →  texto literal entre llaves
          FSTRING_EXPR_START  →  {
          ... tokens de la expresión interior ...
          FSTRING_EXPR_END    →  }
          FSTRING_END    →  "
        El parser construirá JoinedStr / FormattedValue a partir de esto.
        """
        self._advance()                     # consume 'f' o 'F'
        quote = self._advance()             # consume ' o "
        yield Token(TT.FSTRING_START, f"f{quote}", line, col)

        # ¿Triple comilla?
        triple = False
        if self._current == quote and self._peek() == quote:
            self._advance(); self._advance()
            triple = True

        buf = ""
        while self.pos < len(self.source):
            ch = self._current

            # Fin del f-string
            if not triple and ch == quote:
                if buf:
                    yield Token(TT.FSTRING_PART, buf, self.line, self.col)
                    buf = ""
                self._advance()
                yield Token(TT.FSTRING_END, quote, self.line, self.col)
                return
            if triple and self.source[self.pos:self.pos + 3] == quote * 3:
                if buf:
                    yield Token(TT.FSTRING_PART, buf, self.line, self.col)
                self._advance(); self._advance(); self._advance()
                yield Token(TT.FSTRING_END, quote * 3, self.line, self.col)
                return

            # Llave de apertura de expresión
            if ch == "{":
                if self._peek() == "{":      # {{ → literal {
                    buf += "{"
                    self._advance(); self._advance()
                    continue
                if buf:
                    yield Token(TT.FSTRING_PART, buf, self.line, self.col)
                    buf = ""
                expr_line, expr_col = self.line, self.col
                self._advance()             # consume '{'
                yield Token(TT.FSTRING_EXPR_START, "{", expr_line, expr_col)

                # Tokenizar la expresión hasta encontrar '}' balanceado
                depth = 1
                while self._current and depth > 0:
                    inner_line, inner_col = self.line, self.col
                    inner_ch = self._current
                    if inner_ch == "{":
                        depth += 1
                        yield Token(TT.LPAREN, "{", inner_line, inner_col)
                        self._advance()
                    elif inner_ch == "}":
                        depth -= 1
                        if depth == 0:
                            yield Token(
                                TT.FSTRING_EXPR_END, "}",
                                self.line, self.col
                            )
                            self._advance()
                        else:
                            yield Token(TT.RPAREN, "}", inner_line, inner_col)
                            self._advance()
                    elif inner_ch in (" ", "\t"):
                        self._advance()
                    elif inner_ch == "#":
                        while self._current and self._current != "\n":
                            self._advance()
                    elif inner_ch in ("f", "F") and self._peek() in ('"', "'"):
                        yield from self._scan_fstring(inner_line, inner_col)
                    elif inner_ch in ('"', "'"):
                        yield self._scan_string(inner_line, inner_col)
                    elif inner_ch.isdigit():
                        yield self._scan_number(inner_line, inner_col)
                    elif inner_ch.isalpha() or inner_ch == "_":
                        yield self._scan_name(inner_line, inner_col)
                    else:
                        tok = self._scan_operator(inner_line, inner_col)
                        if tok:
                            yield tok
                        else:
                            self._advance()
                continue

            # Llave de cierre literal
            if ch == "}" and self._peek() == "}":
                buf += "}"
                self._advance(); self._advance()
                continue

            # Escape
            if ch == "\\":
                buf += self._scan_escape()
                continue

            buf += self._advance()

        raise LexerError("F-string sin cerrar", line, col)

    # ── Números ───────────────────────────────────────────────────────────────

    def _scan_number(self, line: int, col: int) -> Token:
        """Reconoce enteros y flotantes (incluye notación científica)."""
        buf   = ""
        is_float = False

        # Prefijos hexadecimales / binarios / octales
        if self._current == "0" and self._peek() in ("x", "X", "b", "B", "o", "O"):
            buf += self._advance()   # '0'
            buf += self._advance()   # prefijo
            while self._current and (
                self._current.isalnum() or self._current == "_"
            ):
                buf += self._advance()
            return Token(TT.INTEGER, buf, line, col)

        while self._current.isdigit() or self._current == "_":
            buf += self._advance()

        if self._current == "." and self._peek().isdigit():
            is_float = True
            buf += self._advance()   # '.'
            while self._current.isdigit():
                buf += self._advance()

        if self._current in ("e", "E"):
            is_float = True
            buf += self._advance()
            if self._current in ("+", "-"):
                buf += self._advance()
            while self._current.isdigit():
                buf += self._advance()

        return Token(TT.FLOAT if is_float else TT.INTEGER, buf, line, col)

    # ── Identificadores y keywords ────────────────────────────────────────────

    def _scan_name(self, line: int, col: int) -> Token:
        """Reconoce un identificador y lo convierte a keyword si corresponde."""
        buf = ""
        while self._current and (self._current.isalnum() or self._current == "_"):
            buf += self._advance()

        tt = KEYWORDS.get(buf)
        if tt == TT.KW_NONE:
            return Token(TT.NONE, buf, line, col)
        if tt == TT.KW_TRUE:
            return Token(TT.BOOL, buf, line, col)
        if tt == TT.KW_FALSE:
            return Token(TT.BOOL, buf, line, col)
        if tt is not None:
            return Token(tt, buf, line, col)
        return Token(TT.NAME, buf, line, col)

    # ── Operadores ────────────────────────────────────────────────────────────

    def _scan_operator(self, line: int, col: int) -> Optional[Token]:
        """
        Reconoce operadores y delimitadores.
        Los operadores de dos caracteres tienen prioridad sobre los de uno.
        """
        ch   = self._current
        nxt  = self._peek()

        two_char = {
            "==": TT.EQ,       "!=": TT.NEQ,     "<=": TT.LEQ,
            ">=": TT.GEQ,      "//": TT.DOUBLESLASH, "**": TT.DOUBLESTAR,
            "+=": TT.PLUSEQ,   "-=": TT.MINUSEQ, "*=": TT.STAREQ,
            "/=": TT.SLASHEQ,  "%=": TT.PERCENTEQ,
        }
        one_char = {
            "+":  TT.PLUS,   "-":  TT.MINUS,    "*":  TT.STAR,
            "/":  TT.SLASH,  "%":  TT.PERCENT,  "=":  TT.ASSIGN,
            "<":  TT.LT,     ">":  TT.GT,       ".":  TT.DOT,
            ",":  TT.COMMA,  ":":  TT.COLON,
            "(":  TT.LPAREN, ")":  TT.RPAREN,
            "[":  TT.LBRACKET, "]": TT.RBRACKET,
        }

        pair = ch + nxt
        if pair in two_char:
            self._advance(); self._advance()
            return Token(two_char[pair], pair, line, col)
        if ch in one_char:
            self._advance()
            return Token(one_char[ch], ch, line, col)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Utilidad: lista de tokens con look-ahead
# ──────────────────────────────────────────────────────────────────────────────

class TokenStream:
    """
    Envuelve la lista de tokens y expone una API de look-ahead de N posiciones
    que el parser recursivo descendente necesita.

    Métodos:
        peek(offset=0)  → Token sin consumir
        advance()       → Token actual y avanza el puntero
        expect(tt)      → avanza si el token es del tipo esperado, si no lanza error
        match(*types)   → True/avanza si el token actual es alguno de los tipos dados
    """

    def __init__(self, tokens: List[Token]):
        self._tokens = tokens
        self._pos    = 0

    def peek(self, offset: int = 0) -> Token:
        i = self._pos + offset
        if i < len(self._tokens):
            return self._tokens[i]
        return self._tokens[-1]   # EOF

    def advance(self) -> Token:
        tok = self._tokens[self._pos]
        if self._pos < len(self._tokens) - 1:
            self._pos += 1
        return tok

    def expect(self, *types: TT) -> Token:
        tok = self.peek()
        if tok.type not in types:
            expected = " | ".join(t.name for t in types)
            raise ParseError(
                f"Se esperaba {expected}, se encontró {tok.type.name} ({tok.value!r})",
                tok.line, tok.col
            )
        return self.advance()

    def match(self, *types: TT) -> bool:
        if self.peek().type in types:
            self.advance()
            return True
        return False

    def skip_newlines(self):
        """Consume todos los NEWLINE consecutivos."""
        while self.peek().type == TT.NEWLINE:
            self.advance()

    @property
    def current_line(self) -> int:
        return self.peek().line

    @property
    def current_col(self) -> int:
        return self.peek().col


class ParseError(Exception):
    def __init__(self, msg: str, line: int, col: int):
        super().__init__(f"[Línea {line}, Col {col}] Error de sintaxis: {msg}")
        self.line = line
        self.col  = col
