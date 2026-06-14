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

