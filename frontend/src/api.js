// Thin fetch wrapper around the FastAPI backend.
// In dev, Vite proxies /api → http://localhost:8000 (see vite.config.js).

async function get(path) {
  const res = await fetch(`/api${path}`, { credentials: "include" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  me: () => get("/auth/me"),
  repos: () => get("/repos/"),
  reviews: (repoId) => get(`/reviews/${repoId ? `?repo_id=${repoId}` : ""}`),
  review: (id) => get(`/reviews/${id}`),
  loginUrl: "/api/auth/login",
};
