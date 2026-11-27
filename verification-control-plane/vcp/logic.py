"""Restricted AST; no eval, arbitrary callables, or executable contract strings."""
from enum import Enum
from itertools import product


class Truth(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


def negate(value):
    return {Truth.TRUE: Truth.FALSE, Truth.FALSE: Truth.TRUE, Truth.UNKNOWN: Truth.UNKNOWN}[value]


def conjunction(values):
    values = tuple(values)
    if not values:
        return Truth.UNKNOWN
    if Truth.FALSE in values:
        return Truth.FALSE
    return Truth.UNKNOWN if Truth.UNKNOWN in values else Truth.TRUE


def disjunction(values):
    values = tuple(values)
    if not values:
        return Truth.UNKNOWN
    if Truth.TRUE in values:
        return Truth.TRUE
    return Truth.UNKNOWN if Truth.UNKNOWN in values else Truth.FALSE


def leaves(expr):
    if expr.kind == "compare":
        return (expr,)
    if expr.kind == "not":
        return leaves(expr.item)
    return tuple(x for item in expr.items for x in leaves(item))


def evaluate(expr, facts):
    if expr.kind == "compare":
        if expr.fact not in facts or type(facts[expr.fact]) is not type(expr.expected):
            return Truth.UNKNOWN
        actual = facts[expr.fact]
        if expr.op == "eq":
            value = actual == expr.expected
        elif expr.op == "ne":
            value = actual != expr.expected
        elif expr.op == "ge":
            value = actual >= expr.expected
        elif expr.op == "le":
            value = actual <= expr.expected
        else:
            return Truth.UNKNOWN
        return Truth.TRUE if value else Truth.FALSE
    if expr.kind == "not":
        return negate(evaluate(expr.item, facts))
    if expr.kind == "all":
        return conjunction(evaluate(x, facts) for x in expr.items)
    if expr.kind == "any":
        return disjunction(evaluate(x, facts) for x in expr.items)
    return Truth.UNKNOWN


def validate_contract(contract):
    """Finite exact satisfiability for bounded scalar comparison ASTs.

    For integers, thresholds and adjacent integers cover all comparison cells.
    Strings need each named value and one unnamed value; booleans both values.
    Reject semantic uncertainty above a bounded product rather than guess.
    """
    if not any(x.role == "success" for x in contract.conditions):
        raise ValueError("nonempty explicit success criteria required")
    if not any(x.role == "authorization" for x in contract.conditions):
        raise ValueError("authorization observation required")
    if len({x.id for x in contract.conditions}) != len(contract.conditions):
        raise ValueError("duplicate condition ID")
    if len({b.fact for b in contract.bindings}) != len(contract.bindings):
        raise ValueError("duplicate evidence binding")
    stack = [(c.expression,1) for c in contract.conditions]
    count = 0
    while stack:
        expr,depth = stack.pop()
        count += 1
        if count > 256 or depth > 32:
            raise ValueError("AST node/depth budget exceeded")
        if expr.kind == "not":
            stack.append((expr.item,depth+1))
        elif expr.kind in ("all","any"):
            stack.extend((item,depth+1) for item in expr.items)
    atoms = tuple(a for c in contract.conditions for a in leaves(c.expression))
    if len(atoms) > 128:
        raise ValueError("predicate budget exceeded")
    facts = {a.fact for a in atoms}
    if facts != {b.fact for b in contract.bindings}:
        raise ValueError("exact claim-to-evidence mappings required")
    domains = {}
    for fact in sorted(facts):
        expected = [a.expected for a in atoms if a.fact == fact]
        types = {type(v) for v in expected}
        if len(types) != 1:
            raise ValueError("inconsistent fact types")
        if types == {bool}:
            values = (False, True)
        elif types == {int}:
            values = tuple(sorted({i for x in expected for i in (x-1, x, x+1)}))
        else:
            other = "__unmentioned__"
            while other in expected:
                other += "_"
            values = tuple(sorted(set(expected))) + (other,)
        domains[fact] = values
    size = 1
    for values in domains.values():
        size *= len(values)
    if size > 100_000:
        raise ValueError("semantic search budget exceeded; owner must simplify/split")
    satisfiable = False
    can_fail_success = False
    for row in product(*domains.values()):
        values = dict(zip(domains, row))
        results = [(c.role, evaluate(c.expression, values)) for c in contract.conditions]
        success = all(t == Truth.TRUE for role, t in results if role != "failure")
        no_failure = all(t == Truth.FALSE for role, t in results if role == "failure")
        satisfiable |= success and no_failure
        can_fail_success |= any(t != Truth.TRUE for role, t in results if role == "success")
        if satisfiable and can_fail_success:
            return
    raise ValueError("contradictory contract or tautological success criteria")
