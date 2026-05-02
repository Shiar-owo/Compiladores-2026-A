"""
taint_engine.py — Taint Propagation Engine
=======================================

El corazón de la Fase 2:
- Marca cada variable que proviene de una fuente controlada por el usuario
  (input(), $_GET, $_POST, STDIN, request.args, etc.)
- Propaga esa "mancha" a través de todo el DFG
- Incluye llamadas a funciones y retornos
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set

from ast_nodes import (
    ASTNode,
    Module, AssignStatement, AugAssignStatement, ExprStatement,
    IfStatement, WhileStatement, ForStatement, FunctionDef,
    FCall, Attribute, Name, BinaryOp, UnaryOp, BoolOp, Compare,
    Literal, Subscript, JoinedStr, FormattedValue, PercentFormat,
)

from symbol_table import SymbolTable, Symbol, TaintStatus
from dfg_builder import DFG, DFGNode, DFGNodeType


class TaintSource(Enum):
    """Fuentes conocidas de datos contaminados."""
    INPUT = auto()
    STDIN = auto()
    REQUEST_ARGS = auto()
    REQUEST_FORM = auto()
    REQUEST_JSON = auto()
    COOKIES = auto()
    SESSION = auto()
    ENV = auto()
    UNKNOWN = auto()


@dataclass
class TaintRecord:
    """Registro de taint propagado."""
    variable: str
    source: str
    source_type: TaintSource
    line: int
    col: int
    path: List[str] = field(default_factory=list)


class TaintPropagationResult:
    """Resultado del análisis de propagación de taint."""
    def __init__(self):
        self.sources: List[TaintRecord] = []
        self.propagations: List[TaintRecord] = []
        self.sanitizations: List[str] = []
    
    def add_source(
        self,
        variable: str,
        source: str,
        source_type: TaintSource,
        line: int,
        col: int,
    ):
        self.sources.append(TaintRecord(
            variable=variable,
            source=source,
            source_type=source_type,
            line=line,
            col=col,
        ))
    
    def add_propagation(
        self,
        variable: str,
        source: str,
        source_type: TaintSource,
        line: int,
        col: int,
    ):
        self.propagations.append(TaintRecord(
            variable=variable,
            source=source,
            source_type=source_type,
            line=line,
            col=col,
        ))


class TaintPropagationEngine:
    """
    Motor de propagación de taint.
    
    Marca cada variable que proviene de una fuente controlada
    por el usuario y propaga esa "mancha" a través del DFG.

    Uso:
        engine = TaintPropagationEngine()
        result = engine.analyze(module, dfg, symbol_table)
        # result.sources containing tainted variables
    """

    def __init__(self):
        self._builtin_sources: Set[str] = {
            "input", "raw_input", "sys.stdin.read",
            "sys.stdin.readline", "getpass.getpass",
        }
        self._web_sources: Set[str] = {
            "request.args", "request.form", "request.values",
            "request.GET", "request.POST", "request.json",
            "request.cookies", "request.session", "request.headers",
            "cookies", "session", "request",
        }
        self._sanitizers: Set[str] = {
            "int", "float", "bool", "str", "repr",
            "escape", "html.escape", "cgi.escape",
            "quote", "pg_escape_string", "mysqli_escape_string",
            "sqlite3.escape_string", "re.escape",
            "urlencode", "urlquote",
        }

    def analyze(
        self,
        module: Module,
        dfg: DFG,
        symbol_table: SymbolTable,
    ) -> TaintPropagationResult:
        """
        Analiza el módulo y propaga taint.
        
        Returns:
            TaintPropagationResult con todas las fuentes y propagaciones.
        """
        result = TaintPropagationResult()
        
        for stmt in module.body:
            self._analyze_stmt(stmt, dfg, symbol_table, result)
        
        self._propagate_through_dfg(dfg, symbol_table, result)
        
        return result

    def _analyze_stmt(
        self,
        stmt: ASTNode,
        dfg: DFG,
        symbol_table: SymbolTable,
        result: TaintPropagationResult,
    ):
        """Analiza una sentencia en busca de fuentes de taint."""
        if isinstance(stmt, AssignStatement):
            self._analyze_assign(stmt, dfg, symbol_table, result)
        elif isinstance(stmt, AugAssignStatement):
            self._analyze_augassign(stmt, dfg, symbol_table, result)
        elif isinstance(stmt, ExprStatement):
            self._analyze_expr_stmt(stmt, dfg, symbol_table, result)
        elif isinstance(stmt, IfStatement):
            self._analyze_if(stmt, dfg, symbol_table, result)
        elif isinstance(stmt, WhileStatement):
            self._analyze_while(stmt, dfg, symbol_table, result)
        elif isinstance(stmt, ForStatement):
            self._analyze_for(stmt, dfg, symbol_table, result)
        elif isinstance(stmt, FunctionDef):
            self._analyze_function(stmt, dfg, symbol_table, result)

    def _analyze_assign(
        self,
        stmt: AssignStatement,
        dfg: DFG,
        symbol_table: SymbolTable,
        result: TaintPropagationResult,
    ):
        """Analiza asignación en busca de taint."""
        right_node = stmt.value
        if right_node is None:
            return
            
        right_tainted = self._is_tainted_expression(right_node, symbol_table)
        source_info = self._detect_source(right_node)
        
        for target in stmt.targets:
            target_name = self._get_var_name(target)
            if target_name:
                if right_tainted or source_info:
                    symbol_table.mark_tainted(
                        target_name,
                        source=source_info or "unknown",
                        line=stmt.line,
                        col=stmt.col,
                    )
                    result.add_source(
                        target_name,
                        source_info or "unknown",
                        self._classify_source(source_info),
                        stmt.line,
                        stmt.col,
                    )
                
                self._propagate_from_value(
                    target_name,
                    right_node,
                    dfg,
                    symbol_table,
                    result,
                )

    def _analyze_augassign(
        self,
        stmt: AugAssignStatement,
        dfg: DFG,
        symbol_table: SymbolTable,
        result: TaintPropagationResult,
    ):
        """Analiza asignación aumentada."""
        target_name = self._get_var_name(stmt.target)
        value_tainted = self._is_tainted_expression(stmt.value, symbol_table)
        
        if target_name and value_tainted:
            symbol_table.mark_tainted(target_name, line=stmt.line, col=stmt.col)
            result.add_propagation(
                target_name,
                "augmented",
                TaintSource.UNKNOWN,
                stmt.line,
                stmt.col,
            )

    def _analyze_expr_stmt(
        self,
        stmt: ExprStatement,
        dfg: DFG,
        symbol_table: SymbolTable,
        result: TaintPropagationResult,
    ):
        """Analiza sentencia de expresión."""
        if stmt.expression:
            self._check_sink(stmt.expression, symbol_table)

    def _analyze_if(
        self,
        stmt: IfStatement,
        dfg: DFG,
        symbol_table: SymbolTable,
        result: TaintPropagationResult,
    ):
        """Analiza if."""
        self._analyze_expr(stmt.condition, symbol_table)
        
        for s in stmt.then_body:
            self._analyze_stmt(s, dfg, symbol_table, result)
        
        for s in stmt.else_body:
            self._analyze_stmt(s, dfg, symbol_table, result)
        
        for elif_cl in stmt.elif_clauses:
            self._analyze_expr(elif_cl.condition, symbol_table)
            for s in elif_cl.body:
                self._analyze_stmt(s, dfg, symbol_table, result)

    def _analyze_while(
        self,
        stmt: WhileStatement,
        dfg: DFG,
        symbol_table: SymbolTable,
        result: TaintPropagationResult,
    ):
        """Analiza while."""
        self._analyze_expr(stmt.condition, symbol_table)
        
        for s in stmt.body:
            self._analyze_stmt(s, dfg, symbol_table, result)

    def _analyze_for(
        self,
        stmt: ForStatement,
        dfg: DFG,
        symbol_table: SymbolTable,
        result: TaintPropagationResult,
    ):
        """Analiza for."""
        iter_tainted = self._is_tainted_expression(stmt.iter, symbol_table)
        
        target_name = self._get_var_name(stmt.target)
        if target_name and iter_tainted:
            symbol_table.mark_tainted(target_name, line=stmt.line, col=stmt.col)
        
        for s in stmt.body:
            self._analyze_stmt(s, dfg, symbol_table, result)

    def _analyze_function(
        self,
        stmt: FunctionDef,
        dfg: DFG,
        symbol_table: SymbolTable,
        result: TaintPropagationResult,
    ):
        """Analiza función."""
        func_table = symbol_table.create_child()
        func_table.set_scope(stmt.name)
        
        for param in stmt.params:
            func_table.define(param.name, line=param.line, col=param.col)
        
        for s in stmt.body:
            self._analyze_stmt(s, dfg, func_table, result)

    def _analyze_expr(
        self,
        expr: Optional[ASTNode],
        symbol_table: SymbolTable,
    ) -> bool:
        """Analiza expresión y retorna si está contaminada."""
        if expr is None:
            return False
        return self._is_tainted_expression(expr, symbol_table)

    def _is_tainted_expression(
        self,
        expr: Optional[ASTNode],
        symbol_table: SymbolTable,
    ) -> bool:
        """Determina si una expresión produce taint."""
        if expr is None:
            return False
        
        if isinstance(expr, Name):
            return symbol_table.is_tainted(expr.name)
        
        if isinstance(expr, FCall):
            func_name = self._get_func_name(expr.func)
            if func_name in self._builtin_sources:
                return True
            if symbol_table.is_web_source(func_name):
                return True
        
        if isinstance(expr, Attribute):
            full_name = self._get_attribute_name(expr)
            if full_name is not None and (symbol_table.is_web_source(full_name) or full_name in self._web_sources):
                return True
        
        if isinstance(expr, BinaryOp) and expr.op == "+":
            left_tainted = self._is_tainted_expression(expr.left, symbol_table)
            right_tainted = self._is_tainted_expression(expr.right, symbol_table)
            return left_tainted or right_tainted
        
        if isinstance(expr, JoinedStr):
            for val in expr.values:
                if isinstance(val, FormattedValue):
                    if self._is_tainted_expression(val.value, symbol_table):
                        return True
        
        if isinstance(expr, PercentFormat):
            right_tainted = self._is_tainted_expression(expr.right, symbol_table)
            if right_tainted:
                return True
        
        return False

    def _detect_source(self, expr: ASTNode) -> Optional[str]:
        """Detecta si una expresión es una fuente conocida."""
        if expr is None:
            return None
        
        if isinstance(expr, FCall):
            func_name = self._get_func_name(expr.func)
            if func_name in self._builtin_sources:
                return func_name
        
        if isinstance(expr, Attribute):
            full_name = self._get_attribute_name(expr)
            if full_name is not None and full_name in self._web_sources:
                return full_name
        
        return None

    def _classify_source(self, source: str) -> TaintSource:
        """Clasifica el tipo de fuente."""
        if source is None:
            return TaintSource.UNKNOWN
        if source in self._builtin_sources:
            return TaintSource.INPUT
        if source in self._web_sources or "request" in source:
            return TaintSource.REQUEST_ARGS
        if source in ("cookies", "session"):
            return TaintSource.COOKIES
        return TaintSource.UNKNOWN

    def _propagate_from_value(
        self,
        target: str,
        value: Optional[ASTNode],
        dfg: DFG,
        symbol_table: SymbolTable,
        result: TaintPropagationResult,
    ):
        """Propaga taint desde el valor hacia el target."""
        if value is None:
            return
        
        if isinstance(value, Name):
            if symbol_table.is_tainted(value.name):
                symbol_table.mark_tainted(target, source=value.name)
                result.add_propagation(
                    target,
                    value.name,
                    TaintSource.UNKNOWN,
                    value.line,
                    value.col,
                )
        
        if isinstance(value, BinaryOp) and value.op == "+":
            if self._is_tainted_expression(value.left, symbol_table):
                symbol_table.mark_tainted(target, source="binary_op")
                result.add_propagation(target, "binary_op", TaintSource.UNKNOWN, value.line, value.col)
            if self._is_tainted_expression(value.right, symbol_table):
                symbol_table.mark_tainted(target, source="binary_op")
                result.add_propagation(target, "binary_op", TaintSource.UNKNOWN, value.line, value.col)
        
        if isinstance(value, JoinedStr):
            for val in value.values:
                if isinstance(val, FormattedValue):
                    if self._is_tainted_expression(val.value, symbol_table):
                        symbol_table.mark_tainted(target, source="fstring")
                        result.add_propagation(target, "fstring", TaintSource.UNKNOWN, value.line, value.col)
        
        if isinstance(value, PercentFormat):
            if self._is_tainted_expression(value.right, symbol_table):
                symbol_table.mark_tainted(target, source="percent_format")
                result.add_propagation(target, "percent_format", TaintSource.UNKNOWN, value.line, value.col)

    def _propagate_through_dfg(
        self,
        dfg: DFG,
        symbol_table: SymbolTable,
        result: TaintPropagationResult,
    ):
        """Propaga taint a través de las aristas del DFG."""
        for source_name, source_node in dfg.nodes.items():
            if not source_name or not symbol_table.is_tainted(source_name):
                continue
            
            for target_node in source_node.outgoing:
                if target_node is None or not target_node.name:
                    continue
                target_name = target_node.name
                
                if target_name and not symbol_table.is_tainted(target_name):
                    is_sanitizer = self._check_sanitizer(target_name)
                    
                    if not is_sanitizer:
                        symbol_table.mark_tainted(
                            target_name,
                            source=source_name,
                        )
                        result.add_propagation(
                            target_name,
                            source_name,
                            TaintSource.UNKNOWN,
                            target_node.line,
                            target_node.col,
                        )

    def _check_sanitizer(self, name: str) -> bool:
        """Verifica si un nombre es un sanitizador."""
        if name is None:
            return False
        base = name.split(".")[-1] if "." in name else name
        return base in self._sanitizers

    def _check_sink(
        self,
        expr: ASTNode,
        symbol_table: SymbolTable,
    ) -> Optional[str]:
        """Verifica si es un sink (lugar de inyección)."""
        if expr is None:
            return None
        if isinstance(expr, FCall):
            func_name = self._get_func_name(expr.func)
            if symbol_table.is_sink(func_name):
                return func_name
            
            for arg in expr.args:
                if isinstance(arg, Name) and symbol_table.is_tainted(arg.name):
                    return func_name
        
        return None

    def _get_func_name(self, func: Optional[ASTNode]) -> str:
        """Obtiene el nombre de una función."""
        if isinstance(func, Name):
            return func.name
        if isinstance(func, Attribute):
            obj_name = self._get_func_name(func.obj)
            return f"{obj_name}.{func.attr}"
        return ""

    def _get_attribute_name(self, expr: Attribute) -> str:
        """Obtiene nombre completo de atributo."""
        obj_name = self._get_func_name(expr.obj) if expr.obj else ""
        return f"{obj_name}.{expr.attr}" if obj_name else expr.attr

    def _get_var_name(self, node: ASTNode) -> Optional[str]:
        """Extrae nombre de variable de un nodo."""
        if isinstance(node, Name):
            return node.name
        if isinstance(node, Attribute):
            obj_name = self._get_var_name(node.obj)
            return f"{obj_name}.{node.attr}" if obj_name else node.attr
        if isinstance(node, Subscript):
            return self._get_var_name(node.obj)
        return None