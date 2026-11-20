"""Tests for the GitHub tools.

Every test installs a mock transport, so the suite never reaches the network.
The handler is given the real httpx.Request, which lets a test assert on the
URL and query string the tool actually built, not just on what it returned.
"""

from __future__ import annotations

import base64

import httpx
import pytest

from atlas.tools import github

REPO = "octocat/hello-world"


@pytest.fixture(autouse=True)
def repo_env(monkeypatch):
    """Every tool reads GITHUB_REPO, and none should see a real token."""
    monkeypatch.setenv("GITHUB_REPO", REPO)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


@pytest.fixture
def mock_api(monkeypatch):
    """Install a request handler behind every tool call.

    Returns the list the handler records requests into, so a test can assert
    on the URL the tool built.
    """
    seen: list[httpx.Request] = []

    def install(handler):
        def wrapped(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        def fake_client() -> httpx.AsyncClient:
            return httpx.AsyncClient(
                base_url=github.API_BASE, transport=httpx.MockTransport(wrapped)
            )

        monkeypatch.setattr(github, "_client", fake_client)
        return seen

    return install


def always(payload, status: int = 200):
    """A handler that answers every request with the same response."""
    return lambda request: httpx.Response(status, json=payload)


def encoded(text: bytes, encoding: str = "base64") -> dict:
    return {"encoding": encoding, "content": base64.b64encode(text).decode("ascii")}


# --- list_repo_files ------------------------------------------------------


async def test_list_returns_entries(mock_api):
    mock_api(always([{"name": "agent.py", "path": "src/agent.py", "type": "file", "size": 42}]))
    result = await github.list_repo_files("src")
    assert result["repo"] == REPO
    assert result["entries"] == [
        {"name": "agent.py", "path": "src/agent.py", "type": "file", "size": 42}
    ]


async def test_list_reports_root_as_slash(mock_api):
    mock_api(always([]))
    result = await github.list_repo_files("")
    assert result["path"] == "/"


async def test_list_strips_surrounding_slashes(mock_api):
    seen = mock_api(always([]))
    await github.list_repo_files("/src/atlas/")
    assert seen[0].url.path == f"/repos/{REPO}/contents/src/atlas"


async def test_list_entry_without_size_defaults_to_zero(mock_api):
    mock_api(always([{"name": "src", "path": "src", "type": "dir"}]))
    result = await github.list_repo_files("")
    assert result["entries"][0]["size"] == 0


async def test_list_missing_path_returns_error(mock_api):
    mock_api(always({"message": "Not Found"}, status=404))
    result = await github.list_repo_files("nope")
    assert result["error"] == "path not found"
    assert "entries" not in result


async def test_list_on_a_file_points_at_the_other_tool(mock_api):
    mock_api(always({"name": "README.md", "type": "file"}))
    result = await github.list_repo_files("README.md")
    assert "read_repo_file" in result["error"]


async def test_list_raises_on_server_error(mock_api):
    mock_api(always({"message": "boom"}, status=500))
    with pytest.raises(httpx.HTTPStatusError):
        await github.list_repo_files("src")


# --- read_repo_file -------------------------------------------------------


async def test_read_decodes_base64_content(mock_api):
    mock_api(always(encoded(b"hello world")))
    result = await github.read_repo_file("README.md")
    assert result["text"] == "hello world"
    assert result["truncated"] is False


async def test_read_missing_file_returns_error(mock_api):
    mock_api(always({"message": "Not Found"}, status=404))
    result = await github.read_repo_file("nope.py")
    assert result["error"] == "file not found"


async def test_read_on_a_directory_points_at_the_other_tool(mock_api):
    mock_api(always([{"name": "a.py", "path": "a.py", "type": "file"}]))
    result = await github.read_repo_file("src")
    assert "list_repo_files" in result["error"]


async def test_read_rejects_unexpected_encoding(mock_api):
    mock_api(always({"encoding": "none", "content": ""}))
    result = await github.read_repo_file("big.bin")
    assert result["error"] == "unsupported content encoding"


async def test_read_rejects_non_utf8_bytes(mock_api):
    mock_api(always(encoded(bytes([0xFF, 0xFE, 0x00]))))
    result = await github.read_repo_file("logo.png")
    assert result["error"] == "file is not utf-8 text"


async def test_read_truncates_a_long_file(mock_api):
    body = ("a" * (github.MAX_CHARS + 500)).encode("utf-8")
    mock_api(always(encoded(body)))
    result = await github.read_repo_file("huge.py")
    assert len(result["text"]) == github.MAX_CHARS
    assert result["truncated"] is True


async def test_read_keeps_a_file_at_the_limit_whole(mock_api):
    body = ("a" * github.MAX_CHARS).encode("utf-8")
    mock_api(always(encoded(body)))
    result = await github.read_repo_file("exact.py")
    assert result["truncated"] is False


# --- search_repo_code -----------------------------------------------------


async def test_search_returns_path_and_url(mock_api):
    mock_api(
        always(
            {
                "total_count": 1,
                "items": [{"path": "src/a.py", "html_url": "https://example.test/a"}],
            }
        )
    )
    result = await github.search_repo_code("BaseModel")
    assert result["total"] == 1
    assert result["matches"] == [{"path": "src/a.py", "url": "https://example.test/a"}]


async def test_search_scopes_the_query_to_the_repo(mock_api):
    seen = mock_api(always({"total_count": 0, "items": []}))
    await github.search_repo_code("BaseModel")
    assert seen[0].url.params["q"] == f"BaseModel repo:{REPO}"
    assert seen[0].url.params["per_page"] == "20"


async def test_search_with_no_matches_returns_empty(mock_api):
    mock_api(always({"total_count": 0, "items": []}))
    result = await github.search_repo_code("nothing")
    assert result["matches"] == []
    assert result["total"] == 0


async def test_search_rate_limited_returns_error(mock_api):
    mock_api(always({"message": "rate limited"}, status=403))
    result = await github.search_repo_code("BaseModel")
    assert result["error"] == "search rate limit reached"


# --- configuration --------------------------------------------------------


def test_missing_repo_env_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    with pytest.raises(RuntimeError, match="GITHUB_REPO"):
        github._repo()


def test_client_sends_the_token_when_one_is_set(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret-value")
    client = github._client()
    assert client.headers["Authorization"] == "Bearer secret-value"


def test_client_sends_no_auth_header_without_a_token():
    client = github._client()
    assert "Authorization" not in client.headers
