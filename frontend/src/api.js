// Thin fetch wrapper around the FastAPI backend.
// In dev, Vite proxies /api → http://localhost:8000 (see vite.config.js).

async function request(method, path, body) {
  const res = await fetch(`/api${path}`, {
    method,
    credentials: "include",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    // Surface the backend's detail message when there is one; it explains
    // things the status code alone can't (missing token, GitHub API failure).
    let detail = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      if (j?.detail) detail = j.detail;
    } catch { /* non-JSON error body */ }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? null : res.json();
}

const get = (path) => request("GET", path);

export const api = {
  me: () => get("/auth/me"),
  repos: () => get("/repos/"),
  availableRepos: () => get("/repos/available"),
  enableRepo: (githubId, fullName) =>
    request("POST", "/repos/", { github_id: githubId, full_name: fullName }),
  disableRepo: (id) => request("DELETE", `/repos/${id}`),
  reviews: (repoId) => get(`/reviews/${repoId ? `?repo_id=${repoId}` : ""}`),
  review: (id) => get(`/reviews/${id}`),
  loginUrl: "/api/auth/login",
};
