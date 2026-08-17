"""
A safe arithmetic evaluator built on Python's `ast` module.

This NEVER calls eval() or exec(). It parses the expression into an AST
and walks it, only permitting a small allow-list of node types and
operators. Anything else (attribute access, function calls to arbitrary
names, imports, comprehensions, lambdas, subscripts, etc.) is rejected.

This is the implementation used by the `calculate` tool exposed to the
agent, and it must reject code-injection attempts, not just bad math.
"""
from __future__ import annotations

import ast
import math
import operator
from dataclasses import dataclass

# Allowed binary operators
_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Allowed unary operators
_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Allowed "function calls" -- a tiny, fixed allow-list of pure math
# functions. No arbitrary name resolution.
_ALLOWED_FUNCS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
}

_MAX_EXPR_LENGTH = 200
_MAX_POWER_EXPONENT = 100  # guard against 10**10**10-style blowups


class UnsafeExpressionError(Exception):
    pass


@dataclass
class CalcResult:
    ok: bool
    value: float | None = None
    error: str | None = None
    expression: str = ""


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            raise UnsafeExpressionError("booleans are not allowed")
        if isinstance(node.value, (int, float)):
            return node.value
        raise UnsafeExpressionError(f"unsupported constant type: {type(node.value)}")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise UnsafeExpressionError(f"operator not allowed: {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if op_type is ast.Pow:
            if abs(right) > _MAX_POWER_EXPONENT:
                raise UnsafeExpressionError("exponent too large")
        if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right == 0:
            raise UnsafeExpressionError("division by zero")
        return _BIN_OPS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise UnsafeExpressionError(f"unary operator not allowed: {op_type.__name__}")
        return _UNARY_OPS[op_type](_eval_node(node.operand))

    if isinstance(node, ast.Call):
        # Only allow calls to plain names in our fixed allow-list.
        # No attribute calls (os.system), no calls on results of other
        # calls that aren't in the allow-list, no starargs/kwargs tricks.
        if not isinstance(node.func, ast.Name):
            raise UnsafeExpressionError("only direct function calls are allowed")
        fname = node.func.id
        if fname not in _ALLOWED_FUNCS:
            raise UnsafeExpressionError(f"function not allowed: {fname}")
        if node.keywords:
            raise UnsafeExpressionError("keyword arguments are not allowed")
        args = [_eval_node(a) for a in node.args]
        return _ALLOWED_FUNCS[fname](*args)

    # Explicitly reject everything else: Name (bare variables), Attribute,
    # Subscript, Lambda, comprehensions, Import, Assign, calls via
    # attributes, string formatting, etc.
    raise UnsafeExpressionError(
        f"disallowed expression element: {type(node).__name__}"
    )


def safe_calculate(expression: str) -> CalcResult:
    """
    Evaluate a pure arithmetic expression safely.

    Only numeric literals, + - * / // % **, unary +/-, parentheses, and a
    tiny allow-list of math functions (abs, round, min, max, sqrt) are
    permitted. No names, attributes, subscripts, calls to anything else,
    or any Python statement is accepted -- eval()/exec() are never used.
    """
    if expression is None:
        return CalcResult(ok=False, error="expression is required", expression="")

    expr = expression.strip()
    if not expr:
        return CalcResult(ok=False, error="expression must not be empty", expression=expr)
    if len(expr) > _MAX_EXPR_LENGTH:
        return CalcResult(ok=False, error="expression too long", expression=expr)

    try:
        parsed = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return CalcResult(ok=False, error=f"syntax error: {e}", expression=expr)

    try:
        value = _eval_node(parsed)
    except UnsafeExpressionError as e:
        return CalcResult(ok=False, error=f"rejected: {e}", expression=expr)
    except ZeroDivisionError:
        return CalcResult(ok=False, error="division by zero", expression=expr)
    except OverflowError:
        return CalcResult(ok=False, error="numeric overflow", expression=expr)
    except Exception as e:  # defensive catch-all, still no eval/exec involved
        return CalcResult(ok=False, error=f"evaluation error: {e}", expression=expr)

    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return CalcResult(ok=False, error="result is not a finite number", expression=expr)

    return CalcResult(ok=True, value=float(value), expression=expr)
