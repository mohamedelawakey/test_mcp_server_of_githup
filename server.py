import os
import json
import logging
from typing import Optional, Dict, Any, List
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Context
import base64

# Setup
load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", "server.log")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
        logging.StreamHandler()
    ],
)

log = logging.getLogger("GitHub")

# Get host and port from environment
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Initialize MCP with host and port
mcp = FastMCP("GitHub MCP Server", host=HOST, port=PORT)

BASE_URL = os.getenv("GITHUB_BASE_URL", "https://api.github.com").rstrip("/")

log.info("=" * 70)
log.info("🚀 Multi-User GitHub MCP Server")
log.info("=" * 70)
log.info("Each user provides their own GITHUB_TOKEN and GITHUB_USERNAME")
log.info("via MCP client configuration")
log.info("=" * 70)


# User credentials holder
class UserCredentials:
    """Holds user credentials extracted from context"""
    def __init__(self, token: str, username: str):
        if not token:
            raise ValueError(
                "GITHUB_TOKEN not provided. Please add it to your MCP client configuration:\n"
                '"env": {"GITHUB_TOKEN": "your_token_here", "GITHUB_USERNAME": "your_username"}'
            )
        if not username:
            raise ValueError(
                "GITHUB_USERNAME not provided. Please add it to your MCP client configuration:\n"
                '"env": {"GITHUB_TOKEN": "your_token", "GITHUB_USERNAME": "your_username_here"}'
            )
        self.token = token
        self.username = username
        log.info(f"✓ User authenticated: {username}")

    def get_headers(self) -> Dict[str, str]:
        """Get GitHub API headers with user's token"""
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": f"mcp-github/{self.username}"
        }


def get_user_credentials(context: Context) -> UserCredentials:
    """
    Extract user credentials from MCP context.
    This is called automatically before each tool execution.
    """
    # FastMCP passes env vars through context.request_context
    # Try multiple ways to get the credentials
    token = ""
    username = ""
    
    # Method 1: From request_context (when available)
    if hasattr(context, 'request_context') and context.request_context:
        rc = context.request_context
        if hasattr(rc, 'env'):
            token = rc.env.get("GITHUB_TOKEN", "")
            username = rc.env.get("GITHUB_USERNAME", "")
    
    # Method 2: Try to get from environment as fallback (for testing)
    if not token:
        token = os.getenv("GITHUB_TOKEN", "")
    if not username:
        username = os.getenv("GITHUB_USERNAME", "")
    
    return UserCredentials(token.strip(), username.strip())


def suggest_description(name: str) -> str:
    name = (name or "").strip()
    return f"{name or 'test'}: Repository for testing and experiments"


def log_request(req: httpx.Request):
    safe_headers = {
        k: ("<hidden>" if k.lower() == "authorization" else v)
        for k, v in req.headers.items()
    }
    log.info(f"=> {req.method} {req.url}")
    log.debug(f"Headers: {safe_headers}")
    try:
        log.debug(f"Body: {req.content.decode()[:1000]}")
    except Exception:
        pass


def log_response(res: httpx.Response):
    res.read()
    log.info(f"<= {res.status_code} {res.request.method} {res.request.url}")
    try:
        log.debug(f"Response: {res.text[:2000]}")
    except Exception as e:
        log.debug(f"Response decode failed: {e}")


def build_client() -> httpx.Client:
    """Create a sync HTTP client with logging hooks"""
    return httpx.Client(
        follow_redirects=False,
        timeout=30.0,
        event_hooks={
            "request": [log_request],
            "response": [log_response]
        },
    )


def format_error(prefix: str, e: Exception) -> str:
    """Format different error types"""
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        text = e.response.text
        rl = e.response.headers.get("X-RateLimit-Remaining")
        rst = e.response.headers.get("X-RateLimit-Reset")
        base = f"{prefix}: {code}"
        if code in (301, 302, 307, 308):
            return f"{base} - Redirect detected. Probably web UI, not API."
        if "CSRF" in text:
            return f"{base} - CSRF error. Wrong domain."
        if code in (401, 403):
            return f"{base} - Invalid or expired API key. RL={rl}, reset={rst}"
        return f"{base} - {text[:500]} RL={rl}, reset={rst}"
    return f"{prefix}: {str(e)}"


# Core API calls (sync)
def api_create_repo(
    creds: UserCredentials,
    name: str,
    description: Optional[str] = None,
    private: bool = False
) -> Dict[str, Any]:
    """Create a repository"""
    payload = {
        "name": name,
        "description": description or suggest_description(name),
        "private": private
    }
    with build_client() as client:
        res = client.post(
            f"{BASE_URL}/user/repos",
            headers=creds.get_headers(),
            json=payload
        )
        res.raise_for_status()
        return res.json()


def api_update_repo(
    creds: UserCredentials,
    repo: str,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    private: Optional[bool] = None
) -> Dict[str, Any]:
    """Update repository metadata via PATCH only"""
    payload: Dict[str, Any] = {}
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if private is not None:
        payload["private"] = bool(private)
    if not payload:
        raise ValueError("No fields to update")

    with build_client() as client:
        url = f"{BASE_URL}/repos/{creds.username}/{repo}"
        res = client.patch(url, headers=creds.get_headers(), json=payload)
        if res.status_code == 405:
            res = client.put(url, headers=creds.get_headers(), json=payload)
        res.raise_for_status()
        return res.json() if res.text else {"status": "ok"}


def api_delete_repo(creds: UserCredentials, repo: str) -> Dict[str, Any]:
    """Delete repository"""
    with build_client() as client:
        url = f"{BASE_URL}/repos/{creds.username}/{repo}"
        res = client.delete(url, headers=creds.get_headers())
        if res.status_code in (200, 202, 204):
            return {"status": "deleted"}
        res.raise_for_status()
        return {"status": "deleted"}


def api_create_readme(creds: UserCredentials, repo: str, content: str) -> Dict[str, Any]:
    """Create README.md file in the repo (GitHub API version)"""
    with build_client() as client:
        url = f"{BASE_URL}/repos/{creds.username}/{repo}/contents/README.md"
        body = {
            "message": "Add README",
            "content": base64.b64encode(content.encode()).decode("utf-8")
        }
        res = client.put(url, headers=creds.get_headers(), json=body)
        res.raise_for_status()
        return res.json()


# Issues
def api_list_issues(
    creds: UserCredentials,
    repo: str,
    state: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List issues. state can be 'open', 'closed', or 'all'"""
    params = {}
    if state:
        params["state"] = state
    with build_client() as client:
        url = f"{BASE_URL}/repos/{creds.username}/{repo}/issues"
        res = client.get(url, headers=creds.get_headers(), params=params)
        res.raise_for_status()
        return res.json()


def api_create_issue(
    creds: UserCredentials,
    repo: str,
    title: str,
    body: str = "",
    labels: Optional[List[str]] = None,
    assignees: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Create a new issue"""
    payload: Dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    if assignees:
        payload["assignees"] = assignees
    with build_client() as client:
        url = f"{BASE_URL}/repos/{creds.username}/{repo}/issues"
        res = client.post(url, headers=creds.get_headers(), json=payload)
        res.raise_for_status()
        return res.json()


def api_update_issue(
    creds: UserCredentials,
    repo: str,
    issue: str,
    title: Optional[str] = None,
    body: Optional[str] = None,
    state: Optional[str] = None,
    labels: Optional[List[str]] = None,
    assignees: Optional[List[str]] = None,
    comment: Optional[str] = None
) -> Dict[str, Any]:
    """Update an issue and/or add a comment"""
    out: Dict[str, Any] = {}
    issue_number = int(issue)

    with build_client() as client:
        patch_payload: Dict[str, Any] = {}
        if title is not None:
            patch_payload["title"] = title
        if body is not None:
            patch_payload["body"] = body
        if state is not None:
            patch_payload["state"] = state
        if labels is not None:
            patch_payload["labels"] = labels
        if assignees is not None:
            patch_payload["assignees"] = assignees

        if patch_payload:
            url = f"{BASE_URL}/repos/{creds.username}/{repo}/issues/{issue_number}"
            res = client.patch(url, headers=creds.get_headers(), json=patch_payload)
            res.raise_for_status()
            out["update"] = res.json() if res.text else {"status": "ok"}

        if comment:
            url_c = f"{BASE_URL}/repos/{creds.username}/{repo}/issues/{issue_number}/comments"
            res_c = client.post(url_c, headers=creds.get_headers(), json={"body": comment})
            res_c.raise_for_status()
            out["comment"] = res_c.json() if res_c.text else {"status": "commented"}

    return out or {"status": "no-op"}


# Pull Requests
def api_open_pr(
    creds: UserCredentials,
    repo: str,
    title: str,
    head: str,
    base: str,
    body: str = ""
) -> Dict[str, Any]:
    """Open a pull request from head -> base"""
    payload = {"title": title, "head": head, "base": base, "body": body}
    with build_client() as client:
        url = f"{BASE_URL}/repos/{creds.username}/{repo}/pulls"
        res = client.post(url, headers=creds.get_headers(), json=payload)
        res.raise_for_status()
        return res.json()


# MCP Tools
@mcp.tool()
def create_repo(
    name: str,
    description: str = "",
    private: bool = False,
    create_readme: bool = True,
    readme_content: str = "# Test Repository\n\nThis repository is for testing.\n",
    context: Context = None
) -> str:
    """Create repo and optional README"""
    try:
        creds = get_user_credentials(context)
        desc = description or suggest_description(name)
        log.info(f"Creating repo: {name} for user: {creds.username}")
        
        repo = api_create_repo(creds, name, desc, private)
        repo_url = repo.get("html_url", "N/A")
        readme_status = "skipped"
        if create_readme:
            try:
                api_create_readme(creds, name, readme_content)
                readme_status = "created"
            except Exception as e:
                readme_status = f"failed: {e}"
        
        result = {
            "status": "success",
            "name": name,
            "description": desc,
            "private": private,
            "repo_url": repo_url,
            "readme": readme_status
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)
    except httpx.HTTPStatusError as e:
        return format_error("Repo creation failed", e)
    except Exception as e:
        log.exception("Unexpected error")
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@mcp.tool()
def update_repo(
    repo: str,
    name: str = "",
    description: str = "",
    set_private: bool = False,
    private: bool = False,
    context: Context = None
) -> str:
    """Update a repository metadata"""
    try:
        creds = get_user_credentials(context)
        out = api_update_repo(
            creds, repo,
            name=name or None,
            description=description or None,
            private=private if set_private else None
        )
        return json.dumps({"status": "success", "repo": repo, "result": out}, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)
    except httpx.HTTPStatusError as e:
        return format_error("Repo update failed", e)
    except Exception as e:
        log.exception("Unexpected error")
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@mcp.tool()
def delete_repo(repo: str, context: Context = None) -> str:
    """Delete a repository"""
    try:
        creds = get_user_credentials(context)
        out = api_delete_repo(creds, repo)
        return json.dumps({"status": "success", "repo": repo, "result": out}, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)
    except httpx.HTTPStatusError as e:
        return format_error("Repo delete failed", e)
    except Exception as e:
        log.exception("Unexpected error")
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@mcp.tool()
def issues_list(repo: str, state: str = "open", context: Context = None) -> str:
    """List issues. state: open|closed|all"""
    try:
        creds = get_user_credentials(context)
        items = api_list_issues(creds, repo, state if state in ("open", "closed", "all") else None)
        return json.dumps({"status": "success", "count": len(items), "items": items}, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)
    except httpx.HTTPStatusError as e:
        return format_error("Issues list failed", e)
    except Exception as e:
        log.exception("Unexpected error")
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@mcp.tool()
def issue_create(
    repo: str,
    title: str,
    body: str = "",
    labels_csv: str = "",
    assignees_csv: str = "",
    context: Context = None
) -> str:
    """Create issue. labels_csv and assignees_csv are comma-separated"""
    try:
        creds = get_user_credentials(context)
        labels = [x.strip() for x in labels_csv.split(",") if x.strip()] if labels_csv else None
        assignees = [x.strip() for x in assignees_csv.split(",") if x.strip()] if assignees_csv else None
        item = api_create_issue(creds, repo, title=title, body=body, labels=labels, assignees=assignees)
        return json.dumps({"status": "success", "item": item}, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)
    except httpx.HTTPStatusError as e:
        return format_error("Issue create failed", e)
    except Exception as e:
        log.exception("Unexpected error")
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@mcp.tool()
def issue_update(
    repo: str,
    issue: str,
    title: str = "",
    body: str = "",
    state: str = "",
    labels_csv: str = "",
    assignees_csv: str = "",
    comment: str = "",
    context: Context = None
) -> str:
    """Update issue fields and/or add a comment"""
    try:
        creds = get_user_credentials(context)
        labels = [x.strip() for x in labels_csv.split(",") if x.strip()] if labels_csv else None
        assignees = [x.strip() for x in assignees_csv.split(",") if x.strip()] if assignees_csv else None
        out = api_update_issue(
            creds, repo, issue,
            title=title or None,
            body=body or None,
            state=state or None,
            labels=labels,
            assignees=assignees,
            comment=comment or None
        )
        return json.dumps({"status": "success", "result": out}, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)
    except httpx.HTTPStatusError as e:
        return format_error("Issue update failed", e)
    except Exception as e:
        log.exception("Unexpected error")
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@mcp.tool()
def pr_open(
    repo: str,
    title: str,
    head: str,
    base: str,
    body: str = "",
    context: Context = None
) -> str:
    """Open a pull request from head -> base"""
    try:
        creds = get_user_credentials(context)
        pr = api_open_pr(creds, repo, title=title, head=head, base=base, body=body)
        return json.dumps({"status": "success", "pr": pr}, ensure_ascii=False)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)
    except httpx.HTTPStatusError as e:
        return format_error("PR open failed", e)
    except Exception as e:
        log.exception("Unexpected error")
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


# Entry Point
if __name__ == "__main__":
    log.info(f"Starting Multi-User GitHub MCP server | BASE_URL={BASE_URL}")
    log.info(f"Binding to {HOST}:{PORT}")
    log.info("Users will provide their own GITHUB_TOKEN and GITHUB_USERNAME")
    mcp.run(transport="sse")
