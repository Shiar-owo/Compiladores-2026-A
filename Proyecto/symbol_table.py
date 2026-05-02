"""
symbol_table.py — Tabla de símbolos enriquecida
==========================================

Almacena no solo tipos, sino el estado de taint de cada símbolo.
Necesaria para el Type Checker usar información de taint para
descartar rutas semánticamente imposibles y reducir falsos positivos.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set


class TaintStatus(Enum):
    """Estado de contaminación de un símbolo."""
    UNKNOWN = auto()
    SAFE = auto()
    TAINTED = auto()
    SANITIZED = auto()


@dataclass
class Symbol:
    """Representa un símbolo (variable, función, etc.)."""
    name: str
    type: Optional[str] = None
    taint_status: TaintStatus = TaintStatus.UNKNOWN
    line: int = 0
    col: int = 0
    sources: List[str] = field(default_factory=list)
    is_function_param: bool = False
    function_scope: Optional[str] = None


@dataclass
class FunctionSignature:
    """Firma de función para análisis interprocedural."""
    name: str
    params: List[str] = field(default_factory=list)
    param_types: List[Optional[str]] = field(default_factory=list)
    return_type: Optional[str] = None
    calls: List[str] = field(default_factory=list)


class SymbolTable:
    """
    Tabla de símbolos con tracking de taint.

    Uso:
        table = SymbolTable()
        table.define("x", line=1, col=1)
        table.mark_tainted("x", source="input()")
        table.get("x")  # -> Symbol with taint_status=TAINTED
    """

    def __init__(self, parent: Optional[SymbolTable] = None):
        self._symbols: Dict[str, Symbol] = {}
        self._functions: Dict[str, FunctionSignature] = {}
        self._parent = parent
        self._scope_name: Optional[str] = None
        self._builtin_sources: Set[str] = {
            "input", "raw_input", "sys.stdin.read",
        }
        self._web_sources: Set[str] = {
            "request.args", "request.form", "request.GET", "request.POST",
            "request.values", "request.json", "cookies", "session",
        }
        self._builtin_sanitizers: Set[str] = {
            "int", "float", "bool", "str", "repr",
            "escape", "html.escape", "quote", "pg_escape_string",
            "mysqli_escape_string", "sqlite_escape_string",
        }
        self._sql_sinks: Set[str] = {
            "execute", "executemany", "cursor.execute",
            "db.execute", "connection.execute", "session.execute",
            "query", "raw_query",
        }

    def set_scope(self, name: str):
        """Establece el nombre del scope actual."""
        self._scope_name = name

    def define(
        self,
        name: str,
        type_: Optional[str] = None,
        line: int = 0,
        col: int = 0,
    ) -> Symbol:
        """Define un nuevo símbolo en la tabla."""
        sym = Symbol(
            name=name,
            type=type_,
            line=line,
            col=col,
            function_scope=self._scope_name,
        )
        self._symbols[name] = sym
        return sym

    def get(self, name: str) -> Optional[Symbol]:
        """Obtiene un símbolo por nombre."""
        if name in self._symbols:
            return self._symbols[name]
        if self._parent:
            return self._parent.get(name)
        return None

    def has(self, name: str) -> bool:
        """Verifica si existe un símbolo."""
        return (
            name in self._symbols
            or (self._parent and self._parent.has(name))
        )

    def define_function(self, name: str) -> FunctionSignature:
        """Define una función."""
        sig = FunctionSignature(name=name)
        self._functions[name] = sig
        return sig

    def get_function(self, name: str) -> Optional[FunctionSignature]:
        """Obtiene la firma de una función."""
        return self._functions.get(name)

    def is_source(self, name: str) -> bool:
        """Determina si un nombre es una fuente de datos controlada por usuario."""
        return name in self._builtin_sources or name in self._web_sources

    def is_web_source(self, name: str) -> bool:
        """Determina si es una fuente web (request.*, etc.)."""
        return name in self._web_sources

    def is_sanitizer(self, name: str) -> bool:
        """Determina si es un sanitizador conocido."""
        base = name.split(".")[-1] if "." in name else name
        return base in self._builtin_sanitizers

    def is_sink(self, name: str) -> bool:
        """Determina si es un sumidero SQL."""
        base = name.split(".")[-1] if "." in name else name
        return base in self._sql_sinks

    def mark_tainted(
        self,
        name: str,
        source: str = "unknown",
        line: int = 0,
        col: int = 0,
    ):
        """Marca un símbolo como contaminado."""
        sym = self.get(name)
        if sym is None:
            sym = self.define(name, line=line, col=col)
        sym.taint_status = TaintStatus.TAINTED
        if source not in sym.sources:
            sym.sources.append(source)

    def mark_safe(self, name: str):
        """Marca un símbolo como seguro."""
        sym = self.get(name)
        if sym:
            sym.taint_status = TaintStatus.SAFE

    def is_tainted(self, name: str) -> bool:
        """Verifica si un símbolo está contaminado."""
        sym = self.get(name)
        return sym is not None and sym.taint_status == TaintStatus.TAINTED

    def is_safe(self, name: str) -> bool:
        """Verifica si un símbolo es seguro."""
        sym = self.get(name)
        return sym is not None and sym.taint_status == TaintStatus.SAFE

    def inherits_taint(self, target: str, source: str):
        """Propaga taint desde source hacia target."""
        src = self.get(source)
        if src and src.taint_status == TaintStatus.TAINTED:
            self.mark_tainted(target, source=source)

    def create_child(self) -> SymbolTable:
        """Crea una tabla hija (para nuevos scopes)."""
        child = SymbolTable(parent=self)
        return child

    def get_all_tainted(self) -> List[Symbol]:
        """Retorna todos los símbolos contaminados."""
        result = []
        for sym in self._symbols.values():
            if sym.taint_status == TaintStatus.TAINTED:
                result.append(sym)
        return result

    def __repr__(self) -> str:
        lines = [f"SymbolTable({self._scope_name}):"]
        for sym in self._symbols.values():
            lines.append(f"  {sym.name}: {sym.type} [{sym.taint_status.name}]")
        return "\n".join(lines)