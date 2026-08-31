"""Thin async wrapper around the GitHub REST API."""
import httpx

GITHUB_API = "https://api.github.com"
GITHUB_OAUTH = "https://github.com/login/oauth"


class GitHubClient:
    def __init__(self, access_token: str | None = None):
        self.access_token = access_token

    def _headers(self) -> dict:
        headers = {"Accept": "application/vnd.github+json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    @staticmethod
    def authorize_url(client_id: str, redirect_uri: str, state: str) -> str:
        return (
            f"{GITHUB_OAUTH}/authorize"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&scope=repo,read:user"
            f"&state={state}"
        )

    @staticmethod
    async def exchange_code_for_token(client_id: str, client_secret: str, code: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{GITHUB_OAUTH}/access_token",
                headers={"Accept": "application/json"},
                data={"client_id": client_id, "client_secret": client_secret, "code": code},
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                raise ValueError(f"GitHub OAuth error: {data.get('error_description', data['error'])}")
            return data["access_token"]

    async def get_authenticated_user(self) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{GITHUB_API}/user", headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def get_pr_diff(self, repo_full_name: str, pr_number: int) -> str:
        headers = self._headers()
        headers["Accept"] = "application/vnd.github.v3.diff"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}",
                headers=headers,
            )
            resp.raise_for_status()
            return resp.text

    async def post_issue_comment(
        self, repo_full_name: str, issue_number: int, body: str
    ) -> dict:
        """Post a comment on a PR. PRs are issues as far as this endpoint cares."""
        url = f"{GITHUB_API}/repos/{repo_full_name}/issues/{issue_number}/comments"
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self._headers(), json={"body": body})
            resp.raise_for_status()
            return resp.json()

    async def list_repositories(self, per_page: int = 100) -> list[dict]:
        """
        List repositories the token can administer.

        Only repos where the user has admin rights can receive a webhook, so
        the caller sees exactly the set it can actually enable.
        """
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GITHUB_API}/user/repos",
                headers=self._headers(),
                params={"per_page": per_page, "sort": "updated", "affiliation": "owner"},
            )
            resp.raise_for_status()
            return [r for r in resp.json() if r.get("permissions", {}).get("admin")]

    async def create_webhook(
        self, repo_full_name: str, callback_url: str, secret: str
    ) -> dict:
        """Register a pull_request webhook on a repository."""
        url = f"{GITHUB_API}/repos/{repo_full_name}/hooks"
        payload = {
            "name": "web",
            "active": True,
            "events": ["pull_request"],
            "config": {
                "url": callback_url,
                "content_type": "json",
                "secret": secret,
                "insecure_ssl": "0",
            },
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
            resp.raise_for_status()
            return resp.json()

    async def delete_webhook(self, repo_full_name: str, hook_id: int) -> None:
        """Remove a webhook. A hook already gone on GitHub's side is not an error."""
        url = f"{GITHUB_API}/repos/{repo_full_name}/hooks/{hook_id}"
        async with httpx.AsyncClient() as client:
            resp = await client.delete(url, headers=self._headers())
            if resp.status_code != 404:
                resp.raise_for_status()