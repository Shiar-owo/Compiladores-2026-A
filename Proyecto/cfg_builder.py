"""
cfg_builder.py — Control Flow Graph Builder
=======================================

Modela todos los caminos de ejecución posibles:
- condicionales (if/elif/else)
- loops (while/for)
- excepciones
- llamadas a funciones
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set

from ast_nodes import (
    ASTNode,
    Module, AssignStatement, AugAssignStatement, ExprStatement,
    IfStatement, WhileStatement, ForStatement, FunctionDef, ReturnStatement,
    FCall, Attribute, Name, BinaryOp, UnaryOp, BoolOp, Compare,
)


class CFGNodeType(Enum):
    """Tipos de nodos en el CFG."""
    ENTRY = auto()
    EXIT = auto()
    ASSIGN = auto()
    CALL = auto()
    IF = auto()
    CONDITION = auto()
    WHILE = auto()
    FOR = auto()
    RETURN = auto()
    RAISE = auto()
    TRY = auto()


@dataclass
class CFGNode:
    """Nodo del CFG representando una operación."""
    id: int
    type: CFGNodeType
    ast_node: Optional[ASTNode] = None
    label: str = ""
    line: int = 0
    col: int = 0
    successors: List[CFGNode] = field(default_factory=list)
    predecessors: List[CFGNode] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"CFGNode({self.id}, {self.type.name})"


@dataclass
class CFGBlock:
    """Bloque básico del CFG."""
    id: int
    nodes: List[CFGNode] = field(default_factory=list)
    entry: Optional[CFGNode] = None
    exit: Optional[CFGNode] = None


class CFG:
    """Control Flow Graph completo."""
    
    def __init__(self):
        self.nodes: Dict[int, CFGNode] = {}
        self.entry: Optional[CFGNode] = None
        self.exit: Optional[CFGNode] = None
        self._next_id = 0

    def new_node(
        self,
        node_type: CFGNodeType,
        ast_node: Optional[ASTNode] = None,
        label: str = "",
    ) -> CFGNode:
        node = CFGNode(
            id=self._next_id,
            type=node_type,
            ast_node=ast_node,
            label=label or node_type.name,
            line=ast_node.line if ast_node else 0,
            col=ast_node.col if ast_node else 0,
        )
        self._next_id += 1
        self.nodes[node.id] = node
        return node

    def add_edge(self, from_: CFGNode, to: CFGNode):
        """Agrega una arista directed."""
        from_.successors.append(to)
        to.predecessors.append(from_)

    def add_edges(self, from_: CFGNode, tos: List[CFGNode]):
        """Agrega múltiples aristas."""
        for to in tos:
            self.add_edge(from_, to)

    def get_all_paths(
        self,
        start: Optional[CFGNode] = None,
        end: Optional[CFGNode] = None,
    ) -> List[List[CFGNode]]:
        """Encuentra todos los caminos entre dos nodos."""
        if start is None:
            start = self.entry
        if end is None:
            end = self.exit

        paths: List[List[CFGNode]] = []
        current_path: List[CFGNode] = [start]
        visited: Set[int] = set()

        def dfs(node: CFGNode):
            if node == end:
                paths.append(current_path[:])
                return
            
            visited.add(node.id)
            for succ in node.successors:
                if succ.id not in visited:
                    current_path.append(succ)
                    dfs(succ)
                    current_path.pop()
            visited.remove(node.id)

        dfs(start)
        return paths

    def __repr__(self) -> str:
        lines = [f"CFG(entry={self.entry}, exit={self.exit})"]
        for node in self.nodes.values():
            succs = [s.id for s in node.successors]
            lines.append(f"  {node.id}: {node.type.name} -> {succs}")
        return "\n".join(lines)


class CFGBuilder:
    """
    Construye el CFG a partir del AST.

    Uso:
        builder = CFGBuilder()
        cfg = builder.build(module)
    """

    def __init__(self):
        self.cfg: Optional[CFG] = None
        self._node_stack: List[CFGNode] = []

    def build(self, module: Module) -> CFG:
        """Construye el CFG completo."""
        self.cfg = CFG()
        self.cfg.entry = self.cfg.new_node(CFGNodeType.ENTRY)
        
        current = self.cfg.entry
        for stmt in module.body:
            stmt_node = self._build_stmt(stmt)
            if stmt_node:
                self.cfg.add_edge(current, stmt_node)
                current = stmt_node
        
        self.cfg.exit = self.cfg.new_node(CFGNodeType.EXIT)
        if current != self.cfg.entry:
            self.cfg.add_edge(current, self.cfg.exit)
        else:
            self.cfg.add_edge(self.cfg.entry, self.cfg.exit)

        return self.cfg

    def _build_stmt(self, stmt: ASTNode) -> Optional[CFGNode]:
        """Convierte una sentencia a nodo(s) del CFG."""
        if isinstance(stmt, AssignStatement):
            return self._build_assign(stmt)
        if isinstance(stmt, AugAssignStatement):
            return self._build_augassign(stmt)
        if isinstance(stmt, ExprStatement):
            return self._build_expr_stmt(stmt)
        if isinstance(stmt, IfStatement):
            return self._build_if(stmt)
        if isinstance(stmt, WhileStatement):
            return self._build_while(stmt)
        if isinstance(stmt, ForStatement):
            return self._build_for(stmt)
        if isinstance(stmt, FunctionDef):
            return self._build_function(stmt)
        if isinstance(stmt, ReturnStatement):
            return self._build_return(stmt)
        return None

    def _build_assign(self, stmt: AssignStatement) -> CFGNode:
        target_name = self._get_name_from_target(stmt.targets[0]) if stmt.targets else "?"
        label = f"{target_name} = <expr>"
        return self.cfg.new_node(
            CFGNodeType.ASSIGN,
            ast_node=stmt,
            label=label,
        )

    def _build_augassign(self, stmt: AugAssignStatement) -> CFGNode:
        target_name = self._get_target_name(stmt.target)
        label = f"{target_name} {stmt.op}= <expr>"
        return self.cfg.new_node(
            CFGNodeType.ASSIGN,
            ast_node=stmt,
            label=label,
        )

    def _build_expr_stmt(self, stmt: ExprStatement) -> CFGNode:
        label = "<expression>"
        return self.cfg.new_node(
            CFGNodeType.CALL,
            ast_node=stmt,
            label=label,
        )

    def _build_if(self, stmt: IfStatement) -> CFGNode:
        """Construye CFG para if-elif-else."""
        cond_node = self.cfg.new_node(
            CFGNodeType.CONDITION,
            ast_node=stmt,
            label="if <cond>",
        )
        
        then_nodes = []
        for s in stmt.then_body:
            s_node = self._build_stmt(s)
            if s_node:
                then_nodes.append(s_node)
        
        else_nodes = []
        for s in stmt.else_body:
            s_node = self._build_stmt(s)
            if s_node:
                else_nodes.append(s_node)
        
        for elif_clause in stmt.elif_clauses:
            elif_node = self.cfg.new_node(
                CFGNodeType.CONDITION,
                ast_node=elif_clause,
                label="elif <cond>",
            )
            for s in elif_clause.body:
                s_node = self._build_stmt(s)
                if s_node:
                    elif_node.successors.append(s_node)
                    s_node.predecessors.append(elif_node)

        return cond_node

    def _build_while(self, stmt: WhileStatement) -> CFGNode:
        loop_node = self.cfg.new_node(
            CFGNodeType.WHILE,
            ast_node=stmt,
            label="while <cond>",
        )
        
        body_nodes = []
        for s in stmt.body:
            s_node = self._build_stmt(s)
            if s_node:
                body_nodes.append(s_node)
        
        for body_node in body_nodes:
            self.cfg.add_edge(body_node, loop_node)

        return loop_node

    def _build_for(self, stmt: ForStatement) -> CFGNode:
        target_name = self._get_target_name(stmt.target)
        label = f"for {target_name} in <iter>"
        return self.cfg.new_node(
            CFGNodeType.FOR,
            ast_node=stmt,
            label=label,
        )

    def _build_function(self, stmt: FunctionDef) -> Optional[CFGNode]:
        func_node = self.cfg.new_node(
            CFGNodeType.CALL,
            ast_node=stmt,
            label=f"def {stmt.name}",
        )
        
        for s in stmt.body:
            s_node = self._build_stmt(s)
            if s_node:
                self.cfg.add_edge(func_node, s_node)

        return func_node

    def _build_return(self, stmt: ReturnStatement) -> CFGNode:
        return self.cfg.new_node(
            CFGNodeType.RETURN,
            ast_node=stmt,
            label="return",
        )

    def _get_name_from_target(self, node: ASTNode) -> str:
        if isinstance(node, Name):
            return node.name
        if isinstance(node, Attribute):
            obj = self._get_name_from_target(node.obj)
            return f"{obj}.{node.attr}"
        return "?"

    def _get_target_name(self, node: ASTNode) -> str:
        return self._get_name_from_target(node)