import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from app.config import settings


ASSERTION_MARKER = "# --- Automated Test Assertion Layer ---"


def run_in_sandbox(patched_code: str, test_file_path: str | None = None) -> dict[str, Any]:
    return run_files_in_sandbox({settings.TARGET_FILE_PATH: patched_code}, test_file_path)


def run_files_in_sandbox(patched_files: dict[str, str], test_file_path: str | None = None) -> dict[str, Any]:
    """Validate a candidate patch by running its tests in an isolated backend.

    Backend selection is config-driven so the same pipeline runs on a Docker
    host (hardened container) or on a Docker-less machine (restricted
    subprocess). The AST guard remains the primary defense in both cases.
    """
    backend = settings.SANDBOX_BACKEND.lower()
    if backend == "local":
        return _run_local(patched_files, test_file_path)
    if backend == "docker":
        return _run_docker(patched_files, test_file_path)
    if _docker_available():
        return _run_docker(patched_files, test_file_path)
    return _run_local(patched_files, test_file_path)


def _run_docker(patched_files: dict[str, str], test_file_path: str | None = None) -> dict[str, Any]:
    import docker  # imported lazily so the local backend has no hard dependency

    test_path = Path(test_file_path or settings.TARGET_FILE_PATH)
    if not test_path.exists():
        return {"success": False, "logs": f"missing test file: {test_path}"}

    try:
        docker_client = docker.from_env()
    except Exception as exc:
        return {"success": False, "logs": f"docker unavailable: {exc}"}

    scratchpad = _new_scratchpad()
    try:
        error = _materialize_files(patched_files, test_path, scratchpad)
        if error:
            return {"success": False, "logs": error}

        logs = docker_client.containers.run(
            image=settings.SANDBOX_IMAGE,
            command=["pytest", "-q", "test_target.py"],
            volumes={str(scratchpad): {"bind": "/sandbox", "mode": "rw"}},
            working_dir="/sandbox",
            network_mode="none",
            mem_limit=settings.SANDBOX_MEMORY_LIMIT,
            nano_cpus=settings.SANDBOX_NANO_CPUS,
            detach=False,
            stdout=True,
            stderr=True,
            remove=True,
            read_only=False,
            security_opt=["no-new-privileges"],
        )
        return {"success": True, "logs": logs.decode("utf-8", errors="replace")}
    except docker.errors.ContainerError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        return {"success": False, "logs": stderr}
    except Exception as exc:
        return {"success": False, "logs": str(exc)}
    finally:
        shutil.rmtree(scratchpad, ignore_errors=True)


def _run_local(patched_files: dict[str, str], test_file_path: str | None = None) -> dict[str, Any]:
    test_path = Path(test_file_path or settings.TARGET_FILE_PATH)
    if not test_path.exists():
        return {"success": False, "logs": f"missing test file: {test_path}"}

    scratchpad = _new_scratchpad()
    try:
        error = _materialize_files(patched_files, test_path, scratchpad)
        if error:
            return {"success": False, "logs": error}

        proc = subprocess.run(
            [sys.executable, "-I", "-B", "-m", "pytest", "-q", "test_target.py"],
            cwd=str(scratchpad),
            env=_restricted_env(),
            capture_output=True,
            text=True,
            timeout=settings.SANDBOX_TIMEOUT_SECONDS,
        )
        logs = (proc.stdout or "") + (proc.stderr or "")
        return {"success": proc.returncode == 0, "logs": logs}
    except subprocess.TimeoutExpired:
        return {"success": False, "logs": f"sandbox timeout after {settings.SANDBOX_TIMEOUT_SECONDS}s"}
    except Exception as exc:
        return {"success": False, "logs": str(exc)}
    finally:
        shutil.rmtree(scratchpad, ignore_errors=True)


def _materialize_files(patched_files: dict[str, str], test_path: Path, dest_dir: Path) -> str | None:
    """Write patched files into ``dest_dir``, returning an error string on failure.

    The test target is rewritten as ``test_target.py`` with the project's
    assertion layer re-appended so the model can never weaken the oracle.
    """
    assertions = _extract_assertions(test_path.read_text(encoding="utf-8"))
    target_key = str(test_path).replace("\\", "/")
    wrote_test_target = False

    for path, content in patched_files.items():
        normalized_path = path.replace("\\", "/")
        if normalized_path == target_key or Path(normalized_path).name == test_path.name:
            target = dest_dir / "test_target.py"
            target.write_text(
                f"{content.rstrip()}\n\n{ASSERTION_MARKER}\n{assertions.lstrip()}",
                encoding="utf-8",
            )
            wrote_test_target = True
            continue

        output_path = (dest_dir / normalized_path).resolve()
        try:
            output_path.relative_to(dest_dir)
        except ValueError:
            return f"unsafe sandbox path: {path}"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")

    if not wrote_test_target:
        return f"patch missing test target: {target_key}"
    return None


def _new_scratchpad() -> Path:
    scratchpad = Path(settings.SANDBOX_DIR).resolve() / str(uuid.uuid4())
    scratchpad.mkdir(parents=True, exist_ok=False)
    return scratchpad


def _restricted_env() -> dict[str, str]:
    """Minimal environment for the local backend: no inherited secrets/keys."""
    keep = ("PATH", "SYSTEMROOT", "PATHEXT", "TEMP", "TMP", "LANG", "LC_ALL")
    env = {name: os.environ[name] for name in keep if name in os.environ}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = ""
    return env


def _docker_available() -> bool:
    try:
        import docker

        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


def _extract_assertions(content: str) -> str:
    if ASSERTION_MARKER not in content:
        return content
    return content.split(ASSERTION_MARKER, 1)[1]
