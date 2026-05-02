"""
dfg_builder.py — Data Flow Graph Builder
======================================

Rastrea cómo los valores fluyen de variable en variable
a través de asignaciones.
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
    Literal, Subscript,
)


class DFGNodeType(Enum):
    """Tipos de nodos en el DFG."""
    VALUE = auto()
    VARIABLE = auto()
    PARAMETER = auto()
    FUNCTION_CALL = auto()
    OPERATOR = auto()
    CONSTANT = auto()
    PHI = auto()


@dataclass
class DFGNode:
    """Nodo del DFG representando un valor."""
    id: int
    name: str
    type: DFGNodeType
    ast_node: Optional[ASTNode] = None
    line: int = 0
    col: int = 0
    value: Any = None
    outgoing: List[DFGNode] = field(default_factory=list)
    incoming: List[DFGNode] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"DFG({self.id}, {self.name})"


@dataclass
class DataFlow:
    """Representa un flujo de datos entre nodos."""
    source: DFGNode
    target: DFGNode
    is_control_flow: bool = False
    is_alias: bool = False


class DFG:
    """Data Flow Graph completo."""
    
    def __init__(self):
        self.nodes: Dict[str, DFGNode] = {}
        self.edges: List[DataFlow] = []
        self._next_id = 0

    def new_node(
        self,
        name: str,
        node_type: DFGNodeType,
        ast_node: Optional[ASTNode] = None,
        value: Any = None,
    ) -> DFGNode:
        node = DFGNode(
            id=self._next_id,
            name=name,
            type=node_type,
            ast_node=ast_node,
            line=ast_node.line if ast_node else 0,
            col=ast_node.col if ast_node else 0,
            value=value,
        )
        self._next_id += 1
        self.nodes[name] = node
        return node

    def get_or_create(
        self,
        name: str,
        node_type: DFGNodeType,
        ast_node: Optional[ASTNode] = None,
        value: Any = None,
    ) -> DFGNode:
        if name in self.nodes:
            return self.nodes[name]
        return self.new_node(name, node_type, ast_node, value)

    def add_edge(self, source: DFGNode, target: DFGNode, is_alias: bool = False):
        """Agrega una arista de flujo de datos."""
        source.outgoing.append(target)
        target.incoming.append(source)
        self.edges.append(DataFlow(source=source, target=target, is_alias=is_alias))

    def get_definition(self, var_name: str) -> Optional[DFGNode]:
        """Obtiene el nodo que define una variable."""
        return self.nodes.get(var_name)

    def get_uses(self, var_name: str) -> List[DFGNode]:
        """Obtiene los nodos que usan una variable."""
        node = self.nodes.get(var_name)
        return list(node.outgoing) if node else []

    def get_all_paths(
        self,
        source_name: str,
        target_name: str,
    ) -> List[List[DFGNode]]:
        """Encuentra todos los caminos entre dos variables."""
        source = self.nodes.get(source_name)
        target = self.nodes.get(target_name)
        
        if not source or not target:
            return []

        paths: List[List[DFGNode]] = []
        current_path: List[DFGNode] = [source]
        visited: Set[int] = set()

        def dfs(node: DFGNode):
            if node == target:
                paths.append(current_path[:])
                return
            
            visited.add(node.id)
            for succ in node.outgoing:
                if succ.id not in visited:
                    current_path.append(succ)
                    dfs(succ)
                    current_path.pop()
            visited.remove(node.id)

        dfs(source)
        return paths

    def __repr__(self) -> str:
        lines = [f"DFG({len(self.nodes)} nodes, {len(self.edges)} edges)"]
        for name, node in self.nodes.items():
            if node.outgoing:
                targets = [n.name for n in node.outgoing]
                lines.append(f"  {name} -> {targets}")
        return "\n".join(lines)


class DFGBuilder:
    """
    Construye el DFG a partir del AST.

    Uso:
        builder = DFGBuilder()
        dfg = builder.build(module)
    """

    def __init__(self):
        self.dfg: Optional[DFG] = None
        self._variable_nodes: Dict[str, DFGNode] = {}

    def build(self, module: Module) -> DFG:
        """Construye el DFG completo."""
        self.dfg = DFG()
        self._variable_nodes = {}
        
        for stmt in module.body:
            self._build_stmt(stmt)

        return self.dfg

    def _build_stmt(self, stmt: ASTNode):
        """Procesa una sentencia."""
        if isinstance(stmt, AssignStatement):
            self._build_assign(stmt)
        elif isinstance(stmt, AugAssignStatement):
            self._build_augassign(stmt)
        elif isinstance(stmt, ExprStatement):
            self._build_expr_stmt(stmt)
        elif isinstance(stmt, IfStatement):
            self._build_if(stmt)
        elif isinstance(stmt, WhileStatement):
            self._build_while(stmt)
        elif isinstance(stmt, ForStatement):
            self._build_for(stmt)
        elif isinstance(stmt, FunctionDef):
            self._build_function(stmt)

    def _build_assign(self, stmt: AssignStatement):
        """Procesa asignación."""
        value_node = self._build_expr(stmt.value)
        
        for target in stmt.targets:
            target_name = self._get_var_name(target)
            if target_name:
                var_node = self.dfg.get_or_create(
                    target_name,
                    DFGNodeType.VARIABLE,
                    ast_node=target,
                )
                if value_node:
                    self.dfg.add_edge(value_node, var_node)
                self._variable_nodes[target_name] = var_node

    def _build_augassign(self, stmt: AugAssignStatement):
        """Procesa asignación aumentada (+=, etc.)."""
        target_name = self._get_var_name(stmt.target)
        value_node = self._build_expr(stmt.value)
        
        if target_name and value_node:
            target_node = self.dfg.get_or_create(
                target_name,
                DFGNodeType.VARIABLE,
                ast_node=stmt.target,
            )
            self.dfg.add_edge(value_node, target_node)
            self._variable_nodes[target_name] = target_node

    def _build_expr_stmt(self, stmt: ExprStatement):
        """Procesa sentencia de expresión."""
        if stmt.expression:
            self._build_expr(stmt.expression)

    def _build_if(self, stmt: IfStatement):
        """Procesa if."""
        self._build_expr(stmt.condition)
        for s in stmt.then_body:
            self._build_stmt(s)
        for s in stmt.else_body:
            self._build_stmt(s)
        for elif_cl in stmt.elif_clauses:
            self._build_expr(elif_cl.condition)
            for s in elif_cl.body:
                self._build_stmt(s)

    def _build_while(self, stmt: WhileStatement):
        """Procesa while."""
        self._build_expr(stmt.condition)
        for s in stmt.body:
            self._build_stmt(s)

    def _build_for(self, stmt: ForStatement):
        """Procesa for."""
        target_name = self._get_var_name(stmt.target)
        iter_node = self._build_expr(stmt.iter)
        
        if target_name and iter_node:
            var_node = self.dfg.get_or_create(
                target_name,
                DFGNodeType.VARIABLE,
                ast_node=stmt.target,
            )
            self.dfg.add_edge(iter_node, var_node)
        
        for s in stmt.body:
            self._build_stmt(s)

    def _build_function(self, stmt: FunctionDef):
        """Procesa función."""
        for param in stmt.params:
            param_node = self.dfg.get_or_create(
                param.name,
                DFGNodeType.PARAMETER,
                line=param.line,
                col=param.col,
            )
            self._variable_nodes[param.name] = param_node
        
        for s in stmt.body:
            self._build_stmt(s)

    def _build_expr(self, expr: Optional[ASTNode]) -> Optional[DFGNode]:
        """Procesa una expresión y retorna el nodo DFG."""
        if expr is None:
            return None
        
        if isinstance(expr, Name):
            return self.dfg.get_or_create(
                expr.name,
                DFGNodeType.VARIABLE,
                ast_node=expr,
            )
        
        if isinstance(expr, Literal):
            return self.dfg.new_node(
                str(expr.value),
                DFGNodeType.CONSTANT,
                ast_node=expr,
                value=expr.value,
            )
        
        if isinstance(expr, BinaryOp):
            return self._build_binary_op(expr)
        
        if isinstance(expr, UnaryOp):
            operand_node = self._build_expr(expr.operand)
            if isinstance(expr.op, str) and expr.op in ("-", "+", "~"):
                return operand_node
            return operand_node
        
        if isinstance(expr, BoolOp):
            values = [self._build_expr(v) for v in expr.values if v]
            if values:
                return values[0]
            return None
        
        if isinstance(expr, Compare):
            left = self._build_expr(expr.left)
            return left
        
        if isinstance(expr, FCall):
            func_node = self._build_expr(expr.func)
            for arg in expr.args:
                self._build_expr(arg)
            return func_node
        
        if isinstance(expr, Attribute):
            obj_node = self._build_expr(expr.obj)
            attr_name = f"{obj_node.name if obj_node else '?'}.{expr.attr}" if obj_node else expr.attr
            return self.dfg.get_or_create(
                attr_name,
                DFGNodeType.VARIABLE,
                ast_node=expr,
            )
        
        if isinstance(expr, Subscript):
            obj_node = self._build_expr(expr.obj)
            key_node = self._build_expr(expr.key)
            return obj_node
        
        return None

    def _build_binary_op(self, expr: BinaryOp) -> Optional[DFGNode]:
        """Procesa operación binaria."""
        left_node = self._build_expr(expr.left)
        right_node = self._build_expr(expr.right)
        
        if expr.op in ("+", "-", "*", "/", "%"):
            result_name = f"_binop_{expr.op}"
            result = self.dfg.new_node(
                result_name,
                DFGNodeType.OPERATOR,
                ast_node=expr,
            )
            if left_node:
                self.dfg.add_edge(left_node, result)
            if right_node:
                self.dfg.add_edge(right_node, result)
            return result
        
        return left_node

    def _get_var_name(self, node: ASTNode) -> Optional[str]:
        """Extrae el nombre de variable de un nodo."""
        if isinstance(node, Name):
            return node.name
        if isinstance(node, Attribute):
            obj_name = self._get_var_name(node.obj)
            if obj_name:
                return f"{obj_name}.{node.attr}"
        if isinstance(node, Subscript):
            return self._get_var_name(node.obj)
        return None