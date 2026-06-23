import ast
from dataclasses import dataclass
from typing import Iterable


# Modules that grant filesystem, network, process, reflection, serialization,
# or interpreter-level access. Patches are pure-logic fixes, so none belong in
# generated code. Matched on the dotted root (``os.path`` -> ``os``).
DENIED_IMPORT_ROOTS = frozenset(
    {
        "asyncio",
        "builtins",
        "code",
        "codeop",
        "ctypes",
        "docker",
        "fcntl",
        "ftplib",
        "gc",
        "glob",
        "http",
        "httpx",
        "imaplib",
        "importlib",
        "inspect",
        "marshal",
        "mmap",
        "multiprocessing",
        "os",
        "pathlib",
        "pickle",
        "platform",
        "pty",
        "requests",
        "resource",
        "runpy",
        "shutil",
        "signal",
        "smtplib",
        "socket",
        "socketserver",
        "ssl",
        "subprocess",
        "sys",
        "telnetlib",
        "tempfile",
        "threading",
        "urllib",
        "webbrowser",
        "xmlrpc",
    }
)

# Builtins that enable dynamic execution, importing, I/O, or attribute-based
# escapes. Flagged whether they are invoked directly (``eval(x)``) or merely
# bound to another name for later use (``f = eval``).
DENIED_NAMES = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "eval",
        "exec",
        "getattr",
        "globals",
        "input",
        "locals",
        "memoryview",
        "open",
        "setattr",
        "vars",
    }
)

# Dunder attributes used to climb from a harmless object to dangerous builtins,
# e.g. the classic ``().__class__.__bases__[0].__subclasses__()`` escape.
DENIED_ATTRS = frozenset(
    {
        "__base__",
        "__bases__",
        "__builtins__",
        "__class__",
        "__closure__",
        "__code__",
        "__dict__",
        "__func__",
        "__getattribute__",
        "__globals__",
        "__import__",
        "__loader__",
        "__mro__",
        "__reduce__",
        "__reduce_ex__",
        "__self__",
        "__spec__",
        "__subclasses__",
    }
)


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    errors: tuple[str, ...] = ()


class _GuardVisitor(ast.NodeVisitor):
    """Collects every policy violation in a single AST pass."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self._handled_call_funcs: set[int] = set()

    def visit_Import(self, node: ast.Import) -> None:
        _check_imports((alias.name for alias in node.names), self.errors)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        _check_imports((node.module or "",), self.errors)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node.func)
        if name in DENIED_NAMES:
            self.errors.append(f"denied call: {name}")
            # Remember this func node so visit_Name does not double-report it.
            self._handled_call_funcs.add(id(node.func))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if (
            isinstance(node.ctx, ast.Load)
            and node.id in DENIED_NAMES
            and id(node) not in self._handled_call_funcs
        ):
            self.errors.append(f"denied reference: {node.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in DENIED_ATTRS:
            self.errors.append(f"denied attribute: {node.attr}")
        self.generic_visit(node)


def verify_patch(code: str) -> GuardResult:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return GuardResult(False, (f"syntax error: {exc.msg}",))

    visitor = _GuardVisitor()
    visitor.visit(tree)
    # Preserve order while removing duplicate messages from repeated patterns.
    errors = tuple(dict.fromkeys(visitor.errors))
    return GuardResult(not errors, errors)


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
