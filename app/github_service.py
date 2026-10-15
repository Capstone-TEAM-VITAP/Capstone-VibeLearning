import io
import os
import re
import shutil
import zipfile
from pathlib import Path
import requests
from app.repository_utils import resolve_repository_path
from app.chunking.code_chunker import EXTENSION_TO_LANGUAGE

API = "https://api.github.com"
MAX_ARCHIVE_SIZE = 50 * 1024 * 1024
MAX_ENTRIES = 5000
MAX_SOURCE_SIZE = 1 * 1024 * 1024
TIMEOUT = 30

def headers():
    result = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "CodeAI"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        result["Authorization"] = f"Bearer {token}"
    return result

def validate_name(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", value) or value in {".", ".."}:
        raise ValueError(f"Invalid {label}.")
    return value

def api_get(url, params=None):
    try:
        response = requests.get(url, headers=headers(), params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise RuntimeError(f"GitHub connection failed: {exc}") from exc
    if response.status_code == 403:
        msg = response.text[:400]
        reset = response.headers.get("X-RateLimit-Reset")
        raise RuntimeError(f"GitHub 403/rate limit or policy restriction. Reset timestamp: {reset}. Response: {msg}")
    if response.status_code == 401:
        raise RuntimeError("GitHub rejected GITHUB_TOKEN. Check the token in .env.")
    if response.status_code == 404:
        raise RuntimeError("GitHub user/repository/branch not found.")
    if not response.ok:
        raise RuntimeError(f"GitHub HTTP {response.status_code}: {response.text[:400]}")
    return response

def list_public_repositories(username):
    validate_name(username, "username")
    result, page = [], 1
    while True:
        data = api_get(f"{API}/users/{username}/repos", {
            "type": "public", "per_page": 100, "sort": "updated", "page": page
        }).json()
        if not isinstance(data, list):
            raise RuntimeError("Unexpected GitHub API response.")
        for repo in data:
            if not repo.get("private", True):
                result.append({
                    "name": repo.get("name", ""),
                    "full_name": repo.get("full_name", ""),
                    "default_branch": repo.get("default_branch") or "main",
                    "description": repo.get("description") or "",
                    "html_url": repo.get("html_url", ""),
                })
        if len(data) < 100:
            break
        page += 1
    return result

def download_public_repository(owner, repo, branch):
    validate_name(owner, "owner")
    validate_name(repo, "repository")
    # Slash-containing branch names are intentionally rejected by this first version.
    validate_name(branch, "branch")
    repository_id = f"github:{owner}/{repo}"
    destination = resolve_repository_path(repository_id)
    url = f"{API}/repos/{owner}/{repo}/zipball/{branch}"

    try:
        response = requests.get(url, headers=headers(), stream=True, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not download GitHub archive: {exc}") from exc

    archive_data = bytearray()
    try:
        if not response.ok:
            raise RuntimeError(f"GitHub archive HTTP {response.status_code}: {response.text[:400]}")
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_ARCHIVE_SIZE:
            raise RuntimeError("Repository archive exceeds 50 MB.")
        for block in response.iter_content(65536):
            if block:
                archive_data.extend(block)
                if len(archive_data) > MAX_ARCHIVE_SIZE:
                    raise RuntimeError("Repository archive exceeds 50 MB.")
    finally:
        response.close()

    try:
        archive = zipfile.ZipFile(io.BytesIO(archive_data))
    except zipfile.BadZipFile as exc:
        raise RuntimeError("GitHub returned an invalid ZIP archive.") from exc

    with archive:
        members = archive.infolist()
        if len(members) > MAX_ENTRIES:
            raise RuntimeError(f"Archive has more than {MAX_ENTRIES} entries.")
        selected = []
        for member in members:
            if member.is_dir():
                continue
            parts = Path(member.filename).parts
            if len(parts) < 2:
                continue
            relative = Path(*parts[1:])
            if relative.is_absolute() or ".." in relative.parts:
                continue
            if relative.suffix.lower() not in EXTENSION_TO_LANGUAGE:
                continue
            if member.file_size > MAX_SOURCE_SIZE:
                continue
            selected.append((member, relative))
        if not selected:
            raise RuntimeError("No supported source files found in this repository archive.")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_name(destination.name + "_tmp")
        backup = destination.with_name(destination.name + "_backup")
        if temp.exists():
            shutil.rmtree(temp)
        temp.mkdir(parents=True)
        try:
            count = 0
            for member, relative in selected:
                out = (temp / relative).resolve()
                if not out.is_relative_to(temp.resolve()):
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with archive.open(member) as src, out.open("wb") as dst:
                    while True:
                        block = src.read(65536)
                        if not block:
                            break
                        written += len(block)
                        if written > MAX_SOURCE_SIZE:
                            raise RuntimeError(f"Extracted source file too large: {relative}")
                        dst.write(block)
                count += 1
            if count == 0:
                raise RuntimeError("No safe source files extracted.")
            if backup.exists():
                shutil.rmtree(backup)
            if destination.exists():
                destination.rename(backup)
            try:
                temp.rename(destination)
            except Exception:
                if backup.exists():
                    backup.rename(destination)
                raise
            if backup.exists():
                shutil.rmtree(backup)
        except Exception:
            if temp.exists():
                shutil.rmtree(temp)
            raise
    return destination, count
