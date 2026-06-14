import shutil
import uuid
from pathlib import Path
from typing import Any

import docker

from app.config import settings


ASSERTION_MARKER = "# --- Automated Test Assertion Layer ---"


def run_in_sandbox(patched_code: str, test_file_path: str | None = None) -> dict[str, Any]:
    test_path = Path(test_file_path or settings.TARGET_FILE_PATH)
    if not test_path.exists():
        return {"success": False, "logs": f"missing test file: {test_path}"}

    try:
        docker_client = docker.from_env()
    except Exception as exc:
        return {"success": False, "logs": f"docker unavailable: {exc}"}

    scratchpad = Path(settings.SANDBOX_DIR).resolve() / str(uuid.uuid4())
    scratchpad.mkdir(parents=True, exist_ok=False)

    try:
        assertions = _extract_assertions(test_path.read_text(encoding="utf-8"))
        target = scratchpad / "test_target.py"
        target.write_text(
            f"{patched_code.rstrip()}\n\n{ASSERTION_MARKER}\n{assertions.lstrip()}",
            encoding="utf-8",
        )

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


def _extract_assertions(content: str) -> str:
    if ASSERTION_MARKER not in content:
        return content
    return content.split(ASSERTION_MARKER, 1)[1]

