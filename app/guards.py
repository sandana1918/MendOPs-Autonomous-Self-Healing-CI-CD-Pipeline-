import ast
from dataclasses import dataclass
from typing import Iterable


DENIED_IMPORT_ROOTS = {
    "asyncio",
    "builtins",
    "ctypes",
    "docker",
    "ftplib",
    "glob",
    "http",
    "httpx",
    "importlib",
    "inspect",
    "multiprocessing",
    "os",
    "pathlib",
    "pickle",
    "requests",
    "shutil",
    "signal",
    "socket",
    "subprocess",
    "sys",
    "tempfile",
    "threading",
    "urllib",
}

DENIED_CALLS = {
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
}

DENIED_ATTRS = {
    "__class__",
    "__dict__",
    "__globals__",
    "__mro__",
    "__subclasses__",
}


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    errors: tuple[str, ...] = ()


def verify_patch(code: str) -> GuardResult:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return GuardResult(False, (f"syntax error: {exc.msg}",))

    errors: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            _check_imports((alias.name for alias in node.names), errors)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            _check_imports((module,), errors)
        elif isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in DENIED_CALLS:
                errors.append(f"denied call: {name}")
        elif isinstance(node, ast.Attribute):
            if node.attr in DENIED_ATTRS:
                errors.append(f"denied attribute: {node.attr}")

    return GuardResult(not errors, tuple(errors))


def verify_syntax(code: str) -> bool:
    return verify_patch(code).ok


def _check_imports(names: Iterable[str], errors: list[str]) -> None:
    for name in names:
        root = name.split(".", 1)[0]
        if root in DENIED_IMPORT_ROOTS:
            errors.append(f"denied import: {name}")


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""

