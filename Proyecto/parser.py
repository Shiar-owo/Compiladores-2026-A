"""
parser.py — Parser recursivo descendente
=========================================

Convierte el TokenStream producido por el Lexer en un AST tipado.

Gramática del subconjunto soportado
------------------------------------
module       ::= stmt* EOF
stmt         ::= import_stmt
               | func_def
               | if_stmt
               | while_stmt
               | for_stmt
               | return_stmt
               | expr_stmt NEWLINE
               | NEWLINE

import_stmt  ::= ('import' NAME ('.' NAME)* |
                  'from' NAME ('.' NAME)* 'import' NAME (',' NAME)*)
                 NEWLINE

func_def     ::= 'def' NAME '(' params? ')' ':' NEWLINE INDENT stmt+ DEDENT

params       ::= param (',' param)*
param        ::= NAME ('=' expr)?

if_stmt      ::= 'if' expr ':' suite
                 ('elif' expr ':' suite)*
                 ('else' ':' suite)?

while_stmt   ::= 'while' expr ':' suite
for_stmt     ::= 'for' NAME 'in' expr ':' suite
return_stmt  ::= 'return' expr? NEWLINE
suite        ::= NEWLINE INDENT stmt+ DEDENT

expr_stmt    ::= expr ('=' expr | augop expr)?
augop        ::= '+=' | '-=' | '*=' | '/=' | '%='

expr         ::= bool_expr
bool_expr    ::= not_expr (('and'|'or') not_expr)*
not_expr     ::= 'not' not_expr | compare
compare      ::= add_expr (cmp_op add_expr)*
cmp_op       ::= '==' | '!=' | '<' | '>' | '<=' | '>=' | 'in' | 'is'
add_expr     ::= mul_expr (('+' | '-') mul_expr)*
mul_expr     ::= unary_expr (('*' | '/' | '//' | '%') unary_expr)*
unary_expr   ::= ('-' | '+' | '~') unary_expr | power
power        ::= postfix ('**' unary_expr)?
postfix      ::= atom (call_trailer | index_trailer | attr_trailer)*
call_trailer ::= '(' arg_list? ')'
index_trailer::= '[' expr ']'
attr_trailer ::= '.' NAME
atom         ::= NAME | literal | '(' expr ')' | '[' list_items ']'
               | '(' tuple_items ')' | fstring
literal      ::= STRING | INTEGER | FLOAT | BOOL | NONE
"""

from __future__ import annotations

from typing import List, Optional

from lexer import (
    TT, Token, TokenStream, LexerError, ParseError
)
from ast_nodes import (
    ASTNode,
    Module, AssignStatement, AugAssignStatement, ExprStatement,
    IfStatement, ElifClause, WhileStatement, ForStatement,
    FunctionDef, Param, ReturnStatement, ImportStatement,
    Literal, Name, BinaryOp, UnaryOp, BoolOp, Compare,
    Keyword, FCall, Attribute, Subscript,
    JoinedStr, FormattedValue, PercentFormat,
    Tuple, PyList,
)

# Mapeo de TT de augmented-assign al operador string
AUG_OPS: dict[TT, str] = {
    TT.PLUSEQ:    "+=",
    TT.MINUSEQ:   "-=",
    TT.STAREQ:    "*=",
    TT.SLASHEQ:   "/=",
    TT.PERCENTEQ: "%=",
}

# Operadores de comparación soportados
CMP_OPS: dict[TT, str] = {
    TT.EQ:    "==", TT.NEQ: "!=",
    TT.LT:    "<",  TT.GT:  ">",
    TT.LEQ:   "<=", TT.GEQ: ">=",
    TT.KW_IN: "in", TT.KW_IS: "is",
}


class Parser:
    """
    Parser recursivo descendente para el subconjunto de Python.

    Uso:
        from lexer import Lexer, TokenStream
        from parser import Parser

        tokens = list(Lexer(source).tokenize())
        stream = TokenStream(tokens)
        tree   = Parser(stream).parse()
    """

    def __init__(self, stream: TokenStream):
        self.s = stream

    # ─────────────────────────────────────────────────────────────────────────
    # Punto de entrada
    # ─────────────────────────────────────────────────────────────────────────

    def parse(self) -> Module:
        """Parsea el módulo completo y devuelve el nodo raíz."""
        line = self.s.current_line
        self.s.skip_newlines()
        body = self._parse_stmt_list(top_level=True)
        self.s.expect(TT.EOF)
        return Module(body=body, line=line, col=1)

    # ─────────────────────────────────────────────────────────────────────────
    # Listas de sentencias
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_stmt_list(self, top_level: bool = False) -> List[ASTNode]:
        """Parsea cero o más sentencias hasta DEDENT o EOF."""
        stmts: List[ASTNode] = []
        while True:
            self.s.skip_newlines()
            tt = self.s.peek().type
            if tt in (TT.EOF, TT.DEDENT):
                break
            stmt = self._parse_stmt()
            if stmt is not None:
                stmts.append(stmt)
        return stmts

    def _parse_suite(self) -> List[ASTNode]:
        """
        Parsea un bloque indentado: NEWLINE INDENT stmt+ DEDENT
        Usado por if/elif/else/while/for/def.
        """
        self.s.expect(TT.NEWLINE)
        self.s.skip_newlines()
        self.s.expect(TT.INDENT)
        body = self._parse_stmt_list()
        self.s.expect(TT.DEDENT)
        return body

    # ─────────────────────────────────────────────────────────────────────────
    # Sentencias
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_stmt(self) -> Optional[ASTNode]:
        tok = self.s.peek()

        if tok.type == TT.KW_DEF:
            return self._parse_func_def()
        if tok.type == TT.KW_IF:
            return self._parse_if()
        if tok.type == TT.KW_WHILE:
            return self._parse_while()
        if tok.type == TT.KW_FOR:
            return self._parse_for()
        if tok.type == TT.KW_RETURN:
            return self._parse_return()
        if tok.type in (TT.KW_IMPORT, TT.KW_FROM):
            return self._parse_import()
        if tok.type in (TT.KW_PASS, TT.KW_BREAK, TT.KW_CONTINUE):
            self.s.advance()
            self.s.expect(TT.NEWLINE)
            return None
        if tok.type == TT.NEWLINE:
            self.s.advance()
            return None

        return self._parse_expr_stmt()

    # ── Importaciones ─────────────────────────────────────────────────────────

    def _parse_import(self) -> ImportStatement:
        tok  = self.s.advance()
        line = tok.line

        if tok.type == TT.KW_IMPORT:
            module = self._parse_dotted_name()
            self.s.expect(TT.NEWLINE)
            return ImportStatement(
                module=module, names=[], is_from=False,
                line=line, col=tok.col
            )

        # from X import Y [, Z ...]
        module = self._parse_dotted_name()
        self.s.expect(TT.KW_IMPORT)
        names = [self.s.expect(TT.NAME).value]
        while self.s.peek().type == TT.COMMA:
            self.s.advance()
            names.append(self.s.expect(TT.NAME).value)
        self.s.expect(TT.NEWLINE)
        return ImportStatement(
            module=module, names=names, is_from=True,
            line=line, col=tok.col
        )

    def _parse_dotted_name(self) -> str:
        """module.sub.mod → 'module.sub.mod'"""
        parts = [self.s.expect(TT.NAME).value]
        while self.s.peek().type == TT.DOT:
            self.s.advance()
            parts.append(self.s.expect(TT.NAME).value)
        return ".".join(parts)

    # ── Definición de función ─────────────────────────────────────────────────

    def _parse_func_def(self) -> FunctionDef:
        tok  = self.s.expect(TT.KW_DEF)
        name = self.s.expect(TT.NAME)
        self.s.expect(TT.LPAREN)
        params = self._parse_params()
        self.s.expect(TT.RPAREN)
        self.s.expect(TT.COLON)
        body = self._parse_suite()
        return FunctionDef(
            name=name.value, params=params, body=body,
            line=tok.line, col=tok.col
        )

    def _parse_params(self) -> List[Param]:
        params: List[Param] = []
        while self.s.peek().type != TT.RPAREN:
            tok  = self.s.expect(TT.NAME)
            default = None
            if self.s.peek().type == TT.ASSIGN:
                self.s.advance()
                default = self._parse_expr()
            params.append(Param(name=tok.value, default=default,
                                line=tok.line, col=tok.col))
            if not self.s.match(TT.COMMA):
                break
        return params

    # ── if / elif / else ──────────────────────────────────────────────────────

    def _parse_if(self) -> IfStatement:
        tok  = self.s.expect(TT.KW_IF)
        cond = self._parse_expr()
        self.s.expect(TT.COLON)
        then = self._parse_suite()

        elifs: List[ElifClause] = []
        while self.s.peek().type == TT.KW_ELIF:
            etok  = self.s.advance()
            econd = self._parse_expr()
            self.s.expect(TT.COLON)
            ebody = self._parse_suite()
            elifs.append(ElifClause(
                condition=econd, body=ebody,
                line=etok.line, col=etok.col
            ))

        else_body: List[ASTNode] = []
        if self.s.peek().type == TT.KW_ELSE:
            self.s.advance()
            self.s.expect(TT.COLON)
            else_body = self._parse_suite()

        return IfStatement(
            condition=cond, then_body=then,
            elif_clauses=elifs, else_body=else_body,
            line=tok.line, col=tok.col
        )

    # ── while ─────────────────────────────────────────────────────────────────

    def _parse_while(self) -> WhileStatement:
        tok  = self.s.expect(TT.KW_WHILE)
        cond = self._parse_expr()
        self.s.expect(TT.COLON)
        body = self._parse_suite()
        return WhileStatement(
            condition=cond, body=body,
            line=tok.line, col=tok.col
        )

    # ── for ───────────────────────────────────────────────────────────────────

    def _parse_for(self) -> ForStatement:
        tok    = self.s.expect(TT.KW_FOR)
        target = Name(
            name=self.s.expect(TT.NAME).value,
            line=self.s.peek().line, col=self.s.peek().col
        )
        self.s.expect(TT.KW_IN)
        iter_  = self._parse_expr()
        self.s.expect(TT.COLON)
        body   = self._parse_suite()
        return ForStatement(
            target=target, iter=iter_, body=body,
            line=tok.line, col=tok.col
        )

    # ── return ────────────────────────────────────────────────────────────────

    def _parse_return(self) -> ReturnStatement:
        tok = self.s.expect(TT.KW_RETURN)
        val = None
        if self.s.peek().type not in (TT.NEWLINE, TT.EOF, TT.DEDENT):
            val = self._parse_expr()
        self.s.expect(TT.NEWLINE)
        return ReturnStatement(value=val, line=tok.line, col=tok.col)

    # ── Sentencia de expresión / asignación ───────────────────────────────────

    def _parse_expr_stmt(self) -> ASTNode:
        """
        expr
        expr = expr        → AssignStatement
        expr += expr       → AugAssignStatement
        expr               → ExprStatement
        """
        line = self.s.current_line
        col  = self.s.current_col
        left = self._parse_expr()

        # Asignación aumentada
        if self.s.peek().type in AUG_OPS:
            op_tok = self.s.advance()
            right  = self._parse_expr()
            self.s.expect(TT.NEWLINE)
            return AugAssignStatement(
                target=left, op=AUG_OPS[op_tok.type], value=right,
                line=line, col=col
            )

        # Asignación simple (puede ser encadenada: a = b = expr)
        if self.s.peek().type == TT.ASSIGN:
            targets = [left]
            while self.s.peek().type == TT.ASSIGN:
                self.s.advance()
                # Si lo que sigue parece otra expresión antes de '=',
                # es un target adicional; si no, es el valor final.
                next_expr = self._parse_expr()
                targets.append(next_expr)
            # El último elemento de targets es el valor
            value = targets.pop()
            self.s.expect(TT.NEWLINE)
            return AssignStatement(
                targets=targets, value=value,
                line=line, col=col
            )

        self.s.expect(TT.NEWLINE)
        return ExprStatement(expression=left, line=line, col=col)

    # ─────────────────────────────────────────────────────────────────────────
    # Expresiones (precedencia ascendente)
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_expr(self) -> ASTNode:
        return self._parse_bool_expr()

    # ── bool: and / or ───────────────────────────────────────────────────────

    def _parse_bool_expr(self) -> ASTNode:
        left = self._parse_not_expr()

        while self.s.peek().type in (TT.KW_AND, TT.KW_OR):
            op_tok = self.s.advance()
            op     = "and" if op_tok.type == TT.KW_AND else "or"
            right  = self._parse_not_expr()
            # Agrupar en BoolOp: si left ya es BoolOp del mismo operador,
            # añadimos al mismo nodo (como hace CPython).
            if isinstance(left, BoolOp) and left.op == op:
                left.values.append(right)
            else:
                left = BoolOp(
                    op=op, values=[left, right],
                    line=op_tok.line, col=op_tok.col
                )
        return left

    # ── not ──────────────────────────────────────────────────────────────────

    def _parse_not_expr(self) -> ASTNode:
        if self.s.peek().type == TT.KW_NOT:
            tok = self.s.advance()
            return UnaryOp(
                op="not", operand=self._parse_not_expr(),
                line=tok.line, col=tok.col
            )
        return self._parse_compare()

    # ── comparaciones ────────────────────────────────────────────────────────

    def _parse_compare(self) -> ASTNode:
        left = self._parse_add_expr()
        ops, comparators = [], []

        while self.s.peek().type in CMP_OPS:
            op_tok = self.s.advance()
            ops.append(CMP_OPS[op_tok.type])
            comparators.append(self._parse_add_expr())

        if not ops:
            return left
        return Compare(
            left=left, ops=ops, comparators=comparators,
            line=left.line, col=left.col
        )

    # ── suma / resta (y concatenación de cadenas con +) ───────────────────────

    def _parse_add_expr(self) -> ASTNode:
        left = self._parse_mul_expr()

        while self.s.peek().type in (TT.PLUS, TT.MINUS):
            op_tok = self.s.advance()
            right  = self._parse_mul_expr()
            left   = BinaryOp(
                left=left, op=op_tok.value, right=right,
                line=op_tok.line, col=op_tok.col
            )
        return left

    # ── multiplicación / división / módulo ───────────────────────────────────

    def _parse_mul_expr(self) -> ASTNode:
        left = self._parse_unary()

        while self.s.peek().type in (
            TT.STAR, TT.SLASH, TT.DOUBLESLASH, TT.PERCENT
        ):
            op_tok = self.s.advance()
            right  = self._parse_unary()

            # "fmt_string" % args → PercentFormat (semántica especial de taint)
            if op_tok.type == TT.PERCENT:
                left = PercentFormat(
                    left=left, right=right,
                    line=op_tok.line, col=op_tok.col
                )
            else:
                left = BinaryOp(
                    left=left, op=op_tok.value, right=right,
                    line=op_tok.line, col=op_tok.col
                )
        return left

    # ── unario ────────────────────────────────────────────────────────────────

    def _parse_unary(self) -> ASTNode:
        if self.s.peek().type in (TT.MINUS, TT.PLUS):
            tok = self.s.advance()
            return UnaryOp(
                op=tok.value, operand=self._parse_unary(),
                line=tok.line, col=tok.col
            )
        return self._parse_power()

    # ── potencia ─────────────────────────────────────────────────────────────

    def _parse_power(self) -> ASTNode:
        base = self._parse_postfix()
        if self.s.peek().type == TT.DOUBLESTAR:
            tok = self.s.advance()
            exp = self._parse_unary()
            return BinaryOp(
                left=base, op="**", right=exp,
                line=tok.line, col=tok.col
            )
        return base

    # ── postfijos: llamada, índice, atributo ──────────────────────────────────

    def _parse_postfix(self) -> ASTNode:
        node = self._parse_atom()

        while True:
            tt = self.s.peek().type

            # Llamada a función / método: func(args)
            if tt == TT.LPAREN:
                self.s.advance()
                args, keywords = self._parse_arg_list()
                self.s.expect(TT.RPAREN)
                node = FCall(
                    func=node, args=args, keywords=keywords,
                    line=node.line, col=node.col
                )

            # Acceso por índice: obj[key]
            elif tt == TT.LBRACKET:
                self.s.advance()
                key = self._parse_expr()
                self.s.expect(TT.RBRACKET)
                node = Subscript(
                    obj=node, key=key,
                    line=node.line, col=node.col
                )

            # Acceso a atributo: obj.attr
            elif tt == TT.DOT:
                self.s.advance()
                attr_tok = self.s.expect(TT.NAME)
                node = Attribute(
                    obj=node, attr=attr_tok.value,
                    line=node.line, col=node.col
                )

            else:
                break

        return node

    def _parse_arg_list(self):
        """Parsea la lista de argumentos de una llamada a función."""
        args:     List[ASTNode] = []
        keywords: List[Keyword] = []

        while self.s.peek().type != TT.RPAREN:
            # ¿keyword argument? NAME '=' expr
            if (self.s.peek().type == TT.NAME
                    and self.s.peek(1).type == TT.ASSIGN):
                key_tok = self.s.advance()
                self.s.advance()   # '='
                val = self._parse_expr()
                keywords.append(Keyword(
                    key=key_tok.value, value=val,
                    line=key_tok.line, col=key_tok.col
                ))
            else:
                args.append(self._parse_expr())

            if not self.s.match(TT.COMMA):
                break

        return args, keywords

    # ── átomos ───────────────────────────────────────────────────────────────

    def _parse_atom(self) -> ASTNode:
        tok = self.s.peek()
        tt  = tok.type

        # Identificador
        if tt == TT.NAME:
            self.s.advance()
            return Name(name=tok.value, line=tok.line, col=tok.col)

        # Literales simples
        if tt == TT.STRING:
            self.s.advance()
            return Literal(value=tok.value, kind="str",
                           line=tok.line, col=tok.col)
        if tt == TT.INTEGER:
            self.s.advance()
            return Literal(value=int(tok.value, 0), kind="int",
                           line=tok.line, col=tok.col)
        if tt == TT.FLOAT:
            self.s.advance()
            return Literal(value=float(tok.value), kind="float",
                           line=tok.line, col=tok.col)
        if tt == TT.BOOL:
            self.s.advance()
            return Literal(value=(tok.value == "True"), kind="bool",
                           line=tok.line, col=tok.col)
        if tt == TT.NONE:
            self.s.advance()
            return Literal(value=None, kind="none",
                           line=tok.line, col=tok.col)

        # F-string
        if tt == TT.FSTRING_START:
            return self._parse_fstring()

        # Expresión entre paréntesis o tupla
        if tt == TT.LPAREN:
            return self._parse_paren_or_tuple()

        # Lista literal
        if tt == TT.LBRACKET:
            return self._parse_list()

        raise ParseError(
            f"Token inesperado en expresión: {tt.name} ({tok.value!r})",
            tok.line, tok.col
        )

    # ── F-string ──────────────────────────────────────────────────────────────

    def _parse_fstring(self) -> JoinedStr:
        """
        Reconstruye el nodo JoinedStr a partir de los tokens especiales
        emitidos por el lexer para f-strings.
        """
        tok = self.s.expect(TT.FSTRING_START)
        values: List[ASTNode] = []

        while self.s.peek().type != TT.FSTRING_END:
            tt = self.s.peek().type

            if tt == TT.FSTRING_PART:
                part = self.s.advance()
                values.append(Literal(
                    value=part.value, kind="str",
                    line=part.line, col=part.col
                ))

            elif tt == TT.FSTRING_EXPR_START:
                expr_tok = self.s.advance()
                expr     = self._parse_expr()
                # Conversión opcional !s, !r, !a  (simplificado: ignoramos)
                conv = None
                self.s.expect(TT.FSTRING_EXPR_END)
                values.append(FormattedValue(
                    value=expr, conversion=conv,
                    line=expr_tok.line, col=expr_tok.col
                ))

            elif tt == TT.EOF:
                raise ParseError(
                    "F-string sin cerrar al llegar a EOF",
                    tok.line, tok.col
                )
            else:
                break

        self.s.expect(TT.FSTRING_END)
        return JoinedStr(values=values, line=tok.line, col=tok.col)

    # ── Paréntesis / tupla ────────────────────────────────────────────────────

    def _parse_paren_or_tuple(self) -> ASTNode:
        tok = self.s.expect(TT.LPAREN)
        if self.s.peek().type == TT.RPAREN:
            self.s.advance()
            return Tuple(elements=[], line=tok.line, col=tok.col)

        first = self._parse_expr()
        if self.s.peek().type == TT.COMMA:
            # Es una tupla
            elements = [first]
            while self.s.match(TT.COMMA):
                if self.s.peek().type == TT.RPAREN:
                    break
                elements.append(self._parse_expr())
            self.s.expect(TT.RPAREN)
            return Tuple(elements=elements, line=tok.line, col=tok.col)

        self.s.expect(TT.RPAREN)
        return first   # Paréntesis de agrupación, no es tupla

    # ── Lista literal ─────────────────────────────────────────────────────────

    def _parse_list(self) -> PyList:
        tok      = self.s.expect(TT.LBRACKET)
        elements = []
        while self.s.peek().type != TT.RBRACKET:
            elements.append(self._parse_expr())
            if not self.s.match(TT.COMMA):
                break
        self.s.expect(TT.RBRACKET)
        return PyList(elements=elements, line=tok.line, col=tok.col)
