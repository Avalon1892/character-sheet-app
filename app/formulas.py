from __future__ import annotations

import ast
import math
import random
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass


class FormulaError(ValueError):
    """A safe, user-facing formula validation or evaluation error."""


class UnknownReferenceError(FormulaError):
    pass


class FormulaCycleError(FormulaError):
    pass


FormulaResolver = Callable[[str], int | float | bool]


@dataclass(frozen=True, slots=True)
class SymbolicDiceResult:
    """A formula result whose dice remain unevaluated until an explicit roll."""

    constant: float = 0.0
    dice: tuple[tuple[int, int], ...] = ()

    @property
    def has_dice(self) -> bool:
        return bool(self.dice)

    def format(self) -> str:
        parts: list[str] = []
        for count, sides in self.dice:
            sign = "-" if count < 0 else "+"
            term = f"{abs(count)}d{sides}"
            parts.append(term if not parts and sign == "+" else f"{sign}{term}")
        if self.constant or not parts:
            value = int(self.constant) if float(self.constant).is_integer() else self.constant
            sign = "+" if parts and value >= 0 else ""
            parts.append(f"{sign}{value}")
        return "".join(parts)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _if(condition, value_if_true, value_if_false):
    """Registry marker; FormulaEngine evaluates IF lazily below."""
    return value_if_true if condition else value_if_false


def _dice(_count, _sides):
    """Registry marker; FormulaEngine validates and rolls dice below."""
    raise RuntimeError("dice() is evaluated by FormulaEngine")


FUNCTIONS: dict[str, Callable] = {
    "abs": abs,
    "ceil": math.ceil,
    "clamp": _clamp,
    "dice": _dice,
    "floor": math.floor,
    "IF": _if,
    "max": max,
    "min": min,
    "round": round,
}


_DICE_NOTATION = re.compile(
    r"(?<![A-Za-z0-9_.])(\d+)\s*[dD]\s*(\d+)(?![A-Za-z0-9_.])"
)


def _normalize_dice_notation(expression: str) -> str:
    """Translate familiar ``3d8`` notation into the safe dice function."""

    return _DICE_NOTATION.sub(
        lambda match: f"dice({match.group(1)},{match.group(2)})",
        expression,
    )


def _reference_path(node: ast.AST) -> str | None:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        if current.attr.startswith("_"):
            return None
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name) or current.id.startswith("_"):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def parse_formula(expression: str) -> ast.Expression:
    clean = expression.strip()
    if clean.startswith("="):
        clean = clean[1:].strip()
    # ``&`` is a user-facing alias for boolean ``and``.  Normalizing before
    # parsing gives it exactly the same precedence and lazy behavior instead
    # of Python's very different bitwise-operator precedence.
    clean = clean.replace("&", " and ")
    # Spreadsheet users commonly use semicolons as argument separators in
    # European locales.  Formulas contain no string literals, so this alias is
    # unambiguous and keeps IF(a; b; c) interchangeable with IF(a, b, c).
    clean = clean.replace(";", ",")
    clean = _normalize_dice_notation(clean)
    if not clean:
        raise FormulaError("Enter a formula.")
    if len(clean) > 500:
        raise FormulaError("Formula is too long (maximum 500 characters).")
    try:
        parsed = ast.parse(clean, mode="eval")
    except SyntaxError as error:
        raise FormulaError(f"Invalid formula near column {error.offset or 1}.") from None
    allowed = (
        ast.Expression, ast.Constant, ast.Name, ast.Attribute, ast.Load,
        ast.BinOp, ast.UnaryOp, ast.Call, ast.Compare, ast.BoolOp, ast.IfExp,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
        ast.UAdd, ast.USub, ast.Not, ast.And, ast.Or,
        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    )
    for node in ast.walk(parsed):
        if not isinstance(node, allowed):
            raise FormulaError(f"Unsupported formula element: {type(node).__name__}.")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float, bool)):
            raise FormulaError("Only numeric constants are allowed.")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
                raise FormulaError("That function is not allowed.")
            if node.keywords:
                raise FormulaError("Named function arguments are not allowed.")
        if isinstance(node, (ast.Name, ast.Attribute)) and _reference_path(node) is None:
            raise FormulaError("Invalid value reference.")
    return parsed


def formula_references(expression: str) -> tuple[str, ...]:
    parsed = parse_formula(expression)
    parents = {id(node.value) for node in ast.walk(parsed) if isinstance(node, ast.Attribute)}
    calls = {id(node.func) for node in ast.walk(parsed) if isinstance(node, ast.Call)}
    references: list[str] = []
    for node in ast.walk(parsed):
        if id(node) in parents or id(node) in calls:
            continue
        if isinstance(node, (ast.Name, ast.Attribute)):
            path = _reference_path(node)
            if path and path not in FUNCTIONS and path not in references:
                references.append(path)
    return tuple(sorted(references, key=str.casefold))


class FormulaEngine:
    """Small expression interpreter; formulas never pass through ``eval``."""

    def __init__(self, randint: Callable[[int, int], int] | None = None) -> None:
        # Dependency injection keeps dice behavior testable without weakening
        # the single shared production engine.
        self._randint = randint or random.SystemRandom().randint

    def evaluate(
        self,
        expression: str,
        values: Mapping[str, int | float | bool] | None = None,
        resolver: FormulaResolver | None = None,
    ) -> float:
        parsed = parse_formula(expression)
        supplied = values or {}

        def resolve(path: str) -> int | float | bool:
            if path in supplied:
                return supplied[path]
            if resolver is not None:
                try:
                    return resolver(path)
                except UnknownReferenceError:
                    raise
                except (KeyError, LookupError):
                    pass
            raise UnknownReferenceError(f"Unknown value: {path}")

        result = self._node(parsed.body, resolve)
        if isinstance(result, bool):
            result = int(result)
        if not isinstance(result, (int, float)) or not math.isfinite(float(result)):
            raise FormulaError("Formula must produce a finite number.")
        if abs(float(result)) > 1_000_000_000_000:
            raise FormulaError("Formula result is too large.")
        return float(result)

    def evaluate_symbolic_dice(
        self,
        expression: str,
        values: Mapping[str, int | float | bool] | None = None,
        resolver: FormulaResolver | None = None,
    ) -> SymbolicDiceResult:
        """Resolve numbers and references while preserving every ``XdY`` term.

        Dice may be added or subtracted and multiplied by a whole-number scalar.
        Operations that inherently need a concrete roll (for example comparing a
        die result or passing dice to ``max``) are rejected with a readable error.
        """

        parsed = parse_formula(expression)
        supplied = values or {}

        def resolve(path: str) -> int | float | bool:
            if path in supplied:
                return supplied[path]
            if resolver is not None:
                try:
                    return resolver(path)
                except UnknownReferenceError:
                    raise
                except (KeyError, LookupError):
                    pass
            raise UnknownReferenceError(f"Unknown value: {path}")

        value = self._symbolic_node(parsed.body, resolve)
        result = self._as_symbolic(value)
        if not math.isfinite(float(result.constant)):
            raise FormulaError("Formula must produce a finite number.")
        if abs(float(result.constant)) > 1_000_000_000_000:
            raise FormulaError("Formula result is too large.")
        return result

    @staticmethod
    def _as_symbolic(value) -> SymbolicDiceResult:
        if isinstance(value, SymbolicDiceResult):
            return value
        if isinstance(value, bool):
            value = int(value)
        if not isinstance(value, (int, float)):
            raise FormulaError("Formula must produce a number or dice expression.")
        return SymbolicDiceResult(float(value))

    @staticmethod
    def _plain_number(value, context: str = "This operation") -> int | float | bool:
        if isinstance(value, SymbolicDiceResult):
            if value.dice:
                raise FormulaError(f"{context} requires a fixed number, not dice.")
            return value.constant
        return value

    @staticmethod
    def _scale_symbolic(value: SymbolicDiceResult, scalar: int) -> SymbolicDiceResult:
        if abs(scalar) > 1000:
            raise FormulaError("Dice multiplier is limited to 1,000.")
        return SymbolicDiceResult(
            value.constant * scalar,
            tuple((count * scalar, sides) for count, sides in value.dice if count * scalar),
        )

    def _symbolic_node(self, node: ast.AST, resolve: FormulaResolver):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, (ast.Name, ast.Attribute)):
            path = _reference_path(node)
            if not path:
                raise FormulaError("Invalid value reference.")
            return resolve(path)
        if isinstance(node, ast.BinOp):
            left = self._symbolic_node(node.left, resolve)
            right = self._symbolic_node(node.right, resolve)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                left_result = self._as_symbolic(left)
                right_result = self._as_symbolic(right)
                sign = -1 if isinstance(node.op, ast.Sub) else 1
                return SymbolicDiceResult(
                    left_result.constant + sign * right_result.constant,
                    left_result.dice
                    + tuple((sign * count, sides) for count, sides in right_result.dice),
                )
            if isinstance(node.op, ast.Mult):
                left_result = self._as_symbolic(left)
                right_result = self._as_symbolic(right)
                if left_result.has_dice and right_result.has_dice:
                    raise FormulaError("Dice cannot be multiplied by dice.")
                if left_result.has_dice:
                    scalar = self._plain_number(right_result, "A dice multiplier")
                    if int(scalar) != scalar:
                        raise FormulaError("A dice multiplier must be a whole number.")
                    return self._scale_symbolic(left_result, int(scalar))
                if right_result.has_dice:
                    scalar = self._plain_number(left_result, "A dice multiplier")
                    if int(scalar) != scalar:
                        raise FormulaError("A dice multiplier must be a whole number.")
                    return self._scale_symbolic(right_result, int(scalar))
                return left_result.constant * right_result.constant
            left_number = self._plain_number(left)
            right_number = self._plain_number(right)
            try:
                if isinstance(node.op, ast.Div): return left_number / right_number
                if isinstance(node.op, ast.FloorDiv): return left_number // right_number
                if isinstance(node.op, ast.Mod): return left_number % right_number
                if isinstance(node.op, ast.Pow): return left_number ** right_number
            except ZeroDivisionError:
                raise FormulaError("Division by zero.") from None
            raise FormulaError("That operator is not supported for symbolic dice.")
        if isinstance(node, ast.UnaryOp):
            value = self._symbolic_node(node.operand, resolve)
            if isinstance(node.op, ast.Not):
                return not bool(self._plain_number(value, "Boolean not"))
            result = self._as_symbolic(value)
            if isinstance(node.op, ast.UAdd): return result
            if isinstance(node.op, ast.USub): return self._scale_symbolic(result, -1)
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else ""
            if name == "IF":
                if len(node.args) != 3:
                    raise FormulaError("IF() requires three arguments.")
                condition = self._plain_number(
                    self._symbolic_node(node.args[0], resolve), "An IF condition"
                )
                return self._symbolic_node(node.args[1] if condition else node.args[2], resolve)
            if name == "dice":
                if len(node.args) != 2:
                    raise FormulaError("dice() requires a number of dice and a die size.")
                count = self._plain_number(self._symbolic_node(node.args[0], resolve), "Dice count")
                sides = self._plain_number(self._symbolic_node(node.args[1], resolve), "Die size")
                if int(count) != count or int(sides) != sides:
                    raise FormulaError("Dice count and die size must be whole numbers.")
                count, sides = int(count), int(sides)
                if not 1 <= count <= 1000 or not 2 <= sides <= 1_000_000:
                    raise FormulaError("Dice are outside the supported range.")
                return SymbolicDiceResult(0.0, ((count, sides),))
            arguments = [
                self._plain_number(self._symbolic_node(argument, resolve), f"{name}()")
                for argument in node.args
            ]
            try:
                return FUNCTIONS[name](*arguments)
            except (TypeError, ValueError) as error:
                raise FormulaError(f"Invalid {name}() arguments: {error}") from None
        if isinstance(node, ast.Compare):
            left = self._plain_number(self._symbolic_node(node.left, resolve), "A comparison")
            for operator, comparator in zip(node.ops, node.comparators):
                right = self._plain_number(self._symbolic_node(comparator, resolve), "A comparison")
                matched = (
                    left == right if isinstance(operator, ast.Eq) else
                    left != right if isinstance(operator, ast.NotEq) else
                    left < right if isinstance(operator, ast.Lt) else
                    left <= right if isinstance(operator, ast.LtE) else
                    left > right if isinstance(operator, ast.Gt) else
                    left >= right if isinstance(operator, ast.GtE) else False
                )
                if not matched: return False
                left = right
            return True
        if isinstance(node, ast.BoolOp):
            values = [
                bool(self._plain_number(self._symbolic_node(value, resolve), "A boolean condition"))
                for value in node.values
            ]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.IfExp):
            condition = self._plain_number(self._symbolic_node(node.test, resolve), "A condition")
            return self._symbolic_node(node.body if condition else node.orelse, resolve)
        raise FormulaError(f"Unsupported formula element: {type(node).__name__}.")

    def _node(self, node: ast.AST, resolve: FormulaResolver):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float, bool)):
                return node.value
            raise FormulaError("Only numeric constants are allowed.")
        if isinstance(node, (ast.Name, ast.Attribute)):
            path = _reference_path(node)
            if not path:
                raise FormulaError("Invalid value reference.")
            return resolve(path)
        if isinstance(node, ast.BinOp):
            left, right = self._node(node.left, resolve), self._node(node.right, resolve)
            try:
                if isinstance(node.op, ast.Add): return left + right
                if isinstance(node.op, ast.Sub): return left - right
                if isinstance(node.op, ast.Mult): return left * right
                if isinstance(node.op, ast.Div): return left / right
                if isinstance(node.op, ast.FloorDiv): return left // right
                if isinstance(node.op, ast.Mod): return left % right
                if isinstance(node.op, ast.Pow):
                    if abs(float(right)) > 10:
                        raise FormulaError("Exponent is limited to 10.")
                    return left ** right
            except ZeroDivisionError:
                raise FormulaError("Division by zero.") from None
            raise FormulaError("That operator is not allowed.")
        if isinstance(node, ast.UnaryOp):
            value = self._node(node.operand, resolve)
            if isinstance(node.op, ast.UAdd): return +value
            if isinstance(node.op, ast.USub): return -value
            if isinstance(node.op, ast.Not): return not value
            raise FormulaError("That unary operator is not allowed.")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
                raise FormulaError("That function is not allowed.")
            if node.keywords:
                raise FormulaError("Named function arguments are not allowed.")
            if node.func.id == "IF":
                if len(node.args) != 3:
                    raise FormulaError(
                        "IF() requires a condition, a value when true, and a value when false."
                    )
                condition = self._node(node.args[0], resolve)
                branch = node.args[1] if condition else node.args[2]
                return self._node(branch, resolve)
            if node.func.id == "dice":
                if len(node.args) != 2:
                    raise FormulaError("dice() requires a number of dice and a die size.")
                count = self._node(node.args[0], resolve)
                sides = self._node(node.args[1], resolve)
                if (
                    isinstance(count, bool)
                    or isinstance(sides, bool)
                    or int(count) != count
                    or int(sides) != sides
                ):
                    raise FormulaError("Dice count and die size must be whole numbers.")
                count, sides = int(count), int(sides)
                if not 1 <= count <= 1000:
                    raise FormulaError("Dice count must be between 1 and 1,000.")
                if not 2 <= sides <= 1_000_000:
                    raise FormulaError("Die size must be between 2 and 1,000,000.")
                return sum(self._randint(1, sides) for _ in range(count))
            arguments = [self._node(argument, resolve) for argument in node.args]
            try:
                return FUNCTIONS[node.func.id](*arguments)
            except (TypeError, ValueError) as error:
                raise FormulaError(f"Invalid {node.func.id}() arguments: {error}") from None
        if isinstance(node, ast.Compare):
            left = self._node(node.left, resolve)
            for operator, comparator_node in zip(node.ops, node.comparators):
                right = self._node(comparator_node, resolve)
                matched = (
                    left == right if isinstance(operator, ast.Eq) else
                    left != right if isinstance(operator, ast.NotEq) else
                    left < right if isinstance(operator, ast.Lt) else
                    left <= right if isinstance(operator, ast.LtE) else
                    left > right if isinstance(operator, ast.Gt) else
                    left >= right if isinstance(operator, ast.GtE) else None
                )
                if matched is None:
                    raise FormulaError("That comparison is not allowed.")
                if not matched:
                    return False
                left = right
            return True
        if isinstance(node, ast.BoolOp):
            values = [bool(self._node(value, resolve)) for value in node.values]
            if isinstance(node.op, ast.And): return all(values)
            if isinstance(node.op, ast.Or): return any(values)
            raise FormulaError("That boolean operator is not allowed.")
        if isinstance(node, ast.IfExp):
            branch = node.body if self._node(node.test, resolve) else node.orelse
            return self._node(branch, resolve)
        raise FormulaError(f"Unsupported formula element: {type(node).__name__}.")


DEFAULT_FORMULA_ENGINE = FormulaEngine()
