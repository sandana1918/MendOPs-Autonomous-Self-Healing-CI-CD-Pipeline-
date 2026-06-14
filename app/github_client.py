import base64
import logging
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger("patchforge.github")


@dataclass(frozen=True)
class PullRequestResult:
    ok: bool
    url: str = ""
    error: str = ""


async def commit_patch_and_open_pr(
    branch_name: str,
    file_content: str,
    pr_title: str,
    summary: str,
    target_file_path: str | None = None,
) -> PullRequestResult:
    if not settings.GITHUB_TOKEN:
        return PullRequestResult(False, error="GITHUB_TOKEN missing")

    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repo_url = f"{settings.GITHUB_API_URL.rstrip('/')}/repos/{settings.REPOSITORY_NAME}"
    path = target_file_path or settings.TARGET_FILE_PATH

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            base_sha = await _get_base_sha(client, repo_url, headers)
            await _create_branch(client, repo_url, headers, branch_name, base_sha)
            file_sha = await _get_file_sha(client, repo_url, headers, path)
            await _put_file(client, repo_url, headers, branch_name, path, file_content, file_sha, pr_title)
            pr_url = await _open_pr(client, repo_url, headers, branch_name, pr_title, summary)
            return PullRequestResult(True, url=pr_url)
        except Exception as exc:
            logger.exception("GitHub PR creation failed")
            return PullRequestResult(False, error=str(exc))


async def _get_base_sha(client: httpx.AsyncClient, repo_url: str, headers: dict[str, str]) -> str:
    response = await client.get(
        f"{repo_url}/git/ref/heads/{settings.GITHUB_DEFAULT_BRANCH}",
        headers=headers,
    )
    response.raise_for_status()
    return response.json()["object"]["sha"]


async def _create_branch(
    client: httpx.AsyncClient,
    repo_url: str,
    headers: dict[str, str],
    branch_name: str,
    base_sha: str,
) -> None:
    response = await client.post(
        f"{repo_url}/git/refs",
        headers=headers,
        json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
    )
    if response.status_code not in {201, 422}:
        response.raise_for_status()


async def _get_file_sha(
    client: httpx.AsyncClient,
    repo_url: str,
    headers: dict[str, str],
    path: str,
) -> str | None:
    response = await client.get(
        f"{repo_url}/contents/{path}",
        headers=headers,
        params={"ref": settings.GITHUB_DEFAULT_BRANCH},
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()["sha"]


async def _put_file(
    client: httpx.AsyncClient,
    repo_url: str,
    headers: dict[str, str],
    branch_name: str,
    path: str,
    file_content: str,
    file_sha: str | None,
    pr_title: str,
) -> None:
    payload = {
        "message": f"PatchForge fix: {pr_title}",
        "content": base64.b64encode(file_content.encode("utf-8")).decode("ascii"),
        "branch": branch_name,
    }
    if file_sha:
        payload["sha"] = file_sha

    response = await client.put(f"{repo_url}/contents/{path}", headers=headers, json=payload)
    response.raise_for_status()


async def _open_pr(
    client: httpx.AsyncClient,
    repo_url: str,
    headers: dict[str, str],
    branch_name: str,
    pr_title: str,
    summary: str,
) -> str:
    response = await client.post(
        f"{repo_url}/pulls",
        headers=headers,
        json={
            "title": f"PatchForge fix: {pr_title}",
            "head": branch_name,
            "base": settings.GITHUB_DEFAULT_BRANCH,
            "body": summary,
        },
    )
    response.raise_for_status()
    return response.json().get("html_url", "")

