from pathlib import Path

from app.sandbox import _materialize_files, run_files_in_sandbox


TARGET = "tests/test_target.py"

FIXED_CODE = (
    "def calculate_average_rating(ratings_list):\n"
    "    if not ratings_list:\n"
    "        return 0.0\n"
    "    return sum(ratings_list) / len(ratings_list)\n"
)

BUGGY_CODE = (
    "def calculate_average_rating(ratings_list):\n"
    "    return sum(ratings_list) / len(ratings_list)\n"
)


def test_local_backend_passes_for_correct_patch(monkeypatch):
    monkeypatch.setattr("app.sandbox.settings.SANDBOX_BACKEND", "local")
    result = run_files_in_sandbox({TARGET: FIXED_CODE}, TARGET)
    assert result["success"], result["logs"]


def test_local_backend_fails_for_buggy_patch(monkeypatch):
    monkeypatch.setattr("app.sandbox.settings.SANDBOX_BACKEND", "local")
    result = run_files_in_sandbox({TARGET: BUGGY_CODE}, TARGET)
    assert not result["success"]


def test_local_backend_reports_missing_target(monkeypatch):
    monkeypatch.setattr("app.sandbox.settings.SANDBOX_BACKEND", "local")
    result = run_files_in_sandbox({"app/helpers.py": "x = 1\n"}, TARGET)
    assert not result["success"]
    assert "missing test target" in result["logs"]


def test_materialize_rejects_path_traversal(tmp_path):
    target = Path(TARGET)
    error = _materialize_files({"../escape.py": "x = 1\n", TARGET: FIXED_CODE}, target, tmp_path)
    assert error is not None
    assert "unsafe sandbox path" in error
