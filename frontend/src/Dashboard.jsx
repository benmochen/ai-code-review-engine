import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from "recharts";
import { api } from "./api.js";

const SEV = {
  critical: { label: "Critical", ink: "#7c1d1d", bg: "#fbeaea", dot: "#c0392b", rank: 4 },
  error:    { label: "Error",    ink: "#8a3d12", bg: "#fbeee3", dot: "#d9631a", rank: 3 },
  warning:  { label: "Warning",  ink: "#7a5c00", bg: "#fbf5df", dot: "#c79a13", rank: 2 },
  info:     { label: "Info",     ink: "#1f4d6b", bg: "#e9f2f8", dot: "#3d7fb0", rank: 1 },
};
const STATUS = {
  completed:   { label: "Completed",   ink: "#25623b", bg: "#e6f2ea" },
  in_progress: { label: "In progress", ink: "#6b4e12", bg: "#f6efdc" },
  failed:      { label: "Failed",      ink: "#7c1d1d", bg: "#fbeaea" },
  pending:     { label: "Pending",     ink: "#3a4250", bg: "#eceef1" },
};

function timeAgo(iso) {
  const d = (Date.now() - new Date(iso)) / 3600000;
  if (isNaN(d)) return "";
  if (d < 1) return `${Math.round(d * 60)}m ago`;
  if (d < 24) return `${Math.round(d)}h ago`;
  return `${Math.round(d / 24)}d ago`;
}

export default function Dashboard() {
  const [me, setMe] = useState(undefined);      // undefined = loading, null = logged out
  const [repos, setRepos] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [repoFilter, setRepoFilter] = useState("all");
  const [openId, setOpenId] = useState(null);
  const [detail, setDetail] = useState({});     // review_id -> full review with comments
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showConnect, setShowConnect] = useState(false);
  const [available, setAvailable] = useState(null);   // null = not fetched yet
  const [connectErr, setConnectErr] = useState(null);
  const [busyRepo, setBusyRepo] = useState(null);     // github_id being toggled

  // Auth check on mount
  useEffect(() => {
    api.me().then(setMe).catch(() => setMe(null));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [repoList, reviewList] = await Promise.all([api.repos(), api.reviews()]);
      setRepos(repoList);
      setReviews(reviewList);
    } catch (e) {
      setError("Couldn't reach the API. Is the backend running on :8000?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (me) load(); }, [me, load]);

  // Lazy-load a review's comments when expanded
  const toggle = async (id) => {
    if (openId === id) { setOpenId(null); return; }
    setOpenId(id);
    if (!detail[id]) {
      try {
        const full = await api.review(id);
        setDetail((d) => ({ ...d, [id]: full }));
      } catch { /* leave undefined; body shows a fallback */ }
    }
  };

  const openConnect = useCallback(async () => {
    setShowConnect((v) => !v);
    if (available !== null) return;          // already fetched once
    setConnectErr(null);
    try {
      setAvailable(await api.availableRepos());
    } catch (e) {
      setAvailable([]);
      setConnectErr(e.message);
    }
  }, [available]);

  const toggleRepo = useCallback(async (entry) => {
    setBusyRepo(entry.github_id);
    setConnectErr(null);
    try {
      if (entry.enabled) {
        const mine = repos.find((r) => r.github_id === entry.github_id);
        if (mine) await api.disableRepo(mine.id);
      } else {
        await api.enableRepo(entry.github_id, entry.full_name);
      }
      const [fresh, mine] = await Promise.all([api.availableRepos(), api.repos()]);
      setAvailable(fresh);
      setRepos(mine);
    } catch (e) {
      setConnectErr(e.message);
    } finally {
      setBusyRepo(null);
    }
  }, [repos]);

  const filtered = useMemo(
    () => repoFilter === "all" ? reviews : reviews.filter(r => r.repository_id === repoFilter),
    [reviews, repoFilter]
  );

  const repoName = useCallback(
    (id) => repos.find(r => r.id === id)?.full_name || "unknown/repo",
    [repos]
  );

  // ── auth gate ──
  if (me === undefined) return <Screen><Spinner /> Checking your session…</Screen>;
  if (me === null) return (
    <Screen>
      <style>{CSS}</style>
      <div style={{textAlign:"center"}}>
        <div style={{fontSize:32, color:"#c0392b", marginBottom:12}}>◇</div>
        <h1 style={S.brand}>codereview<span style={{opacity:.4}}>.bot</span></h1>
        <p style={{color:"#7c776b", margin:"10px 0 22px"}}>Sign in to see your pull-request reviews.</p>
        <a href={api.loginUrl} style={S.loginBtn}>Sign in with GitHub</a>
      </div>
    </Screen>
  );

  return (
    <div style={S.page}>
      <style>{CSS}</style>
      <div style={S.shell}>
        <header style={S.head}>
          <div style={S.brandRow}>
            <span style={S.mark}>◇</span>
            <h1 style={S.brand}>codereview<span style={{opacity:.4}}>.bot</span></h1>
            <span style={{flex:1}} />
            <span style={S.user}>@{me.username}</span>
          </div>
          <p style={S.tag}>Automated pull-request review, one queue at a time.</p>
        </header>

        <StatBand reviews={reviews} detail={detail} />

        <div style={S.filters}>
          <Chip active={repoFilter === "all"} onClick={() => setRepoFilter("all")}>All repos</Chip>
          {repos.map(r => (
            <Chip key={r.id} active={repoFilter === r.id} onClick={() => setRepoFilter(r.id)}>
              {r.full_name.split("/")[1] || r.full_name}
              {!r.webhook_active && <span style={S.off}>off</span>}
            </Chip>
          ))}
          <button onClick={openConnect} style={{...S.chip, ...S.connectChip}}>
            {showConnect ? "Close" : "+ Connect a repo"}
          </button>
        </div>

        {showConnect && (
          <ConnectPanel
            available={available}
            error={connectErr}
            busyRepo={busyRepo}
            onToggle={toggleRepo}
          />
        )}

        {loading && <div style={S.empty}><Spinner /> Loading reviews…</div>}
        {error && <div style={S.errorBox}>{error} <button onClick={load} style={S.retry}>Retry</button></div>}

        {!loading && !error && (
          <div style={S.list}>
            {filtered.length === 0 && (
              <div style={S.empty}>
                <div style={{fontSize:28, marginBottom:8}}>◇</div>
                No reviews yet. Open a pull request on a connected repo and the bot picks it up.
              </div>
            )}
            {filtered.map(rv => {
              const open = openId === rv.id;
              const full = detail[rv.id];
              const comments = full?.comments || [];
              const top = comments.length
                ? [...comments].sort((a,b) => SEV[b.severity].rank - SEV[a.severity].rank)[0]
                : null;
              return (
                <article key={rv.id} style={{...S.row, ...(open ? S.rowOpen : {})}}>
                  <button style={S.rowHead} onClick={() => toggle(rv.id)}>
                    <div style={S.rowMain}>
                      <div style={S.rowTitleLine}>
                        <span style={S.pr}>#{rv.pr_number}</span>
                        <span style={S.rowTitle}>{rv.pr_title}</span>
                      </div>
                      <div style={S.rowMeta}>
                        <span style={S.repoTag}>{repoName(rv.repository_id)}</span>
                        <span style={S.dot}>·</span>
                        <span>{timeAgo(rv.created_at)}</span>
                      </div>
                    </div>
                    <div style={S.rowRight}>
                      {top && <SevPill sev={top.severity} />}
                      <StatusPill status={rv.status} />
                      <span style={{...S.chev, transform: open ? "rotate(90deg)" : "none"}}>›</span>
                    </div>
                  </button>
                  {open && (
                    <div style={S.body}>
                      {!full ? (
                        <div style={S.noFindings}><Spinner /> Loading findings…</div>
                      ) : comments.length === 0 ? (
                        <div style={S.noFindings}>
                          {rv.status === "in_progress" && "Review running — findings will appear here shortly."}
                          {rv.status === "failed" && "This review didn't finish. Check the worker logs and re-run the PR."}
                          {rv.status === "completed" && "Clean pass. No issues found."}
                          {rv.status === "pending" && "Queued — waiting for a worker to pick it up."}
                        </div>
                      ) : comments.map((c) => (
                        <div key={c.id} style={S.finding}>
                          <span style={{...S.sevBar, background: SEV[c.severity].dot}} />
                          <div style={{flex:1}}>
                            <div style={S.findingTop}>
                              <SevPill sev={c.severity} />
                              <code style={S.loc}>{c.file_path}{c.line_number != null ? `:${c.line_number}` : ""}</code>
                            </div>
                            <p style={S.findingBody}>{c.body}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function ConnectPanel({ available, error, busyRepo, onToggle }) {
  return (
    <section style={S.connectPanel}>
      <div style={S.connectHead}>
        Your GitHub repositories
        <span style={S.connectHint}>
          Enabling adds a webhook so new pull requests get reviewed.
        </span>
      </div>
      {error && <div style={S.connectErr}>{error}</div>}
      {available === null && <div style={S.noFindings}><Spinner /> Loading from GitHub…</div>}
      {available !== null && available.length === 0 && !error && (
        <div style={S.noFindings}>No repositories you can administer.</div>
      )}
      {(available || []).map((r) => (
        <div key={r.github_id} style={S.connectRow}>
          <div style={{minWidth: 0}}>
            <span style={S.connectName}>{r.full_name}</span>
            {r.private && <span style={S.privateTag}>private</span>}
          </div>
          <button
            onClick={() => onToggle(r)}
            disabled={busyRepo === r.github_id}
            style={{...S.connectBtn, ...(r.enabled ? S.connectBtnOn : {})}}
          >
            {busyRepo === r.github_id ? "…" : r.enabled ? "Disconnect" : "Connect"}
          </button>
        </div>
      ))}
    </section>
  );
}

function StatBand({ reviews, detail }) {
  // Findings counts come from whatever detail we've loaded; the reviews list
  // alone doesn't include comments, so this fills in as the user explores.
  const all = Object.values(detail).flatMap(r => r.comments || []);
  const bySev = Object.keys(SEV).map(k => ({
    key: k, label: SEV[k].label, value: all.filter(c => c.severity === k).length, fill: SEV[k].dot,
  }));
  const critical = all.filter(c => c.severity === "critical").length;
  return (
    <section style={S.band}>
      <Stat n={all.length} label="findings loaded" accent />
      <Stat n={critical} label="critical, needs eyes" />
      <Stat n={reviews.length} label="PRs reviewed" />
      <div style={S.chartCard}>
        <div style={S.chartLabel}>findings by severity</div>
        <ResponsiveContainer width="100%" height={72}>
          <BarChart data={bySev} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#8a8578" }} axisLine={false} tickLine={false} />
            <YAxis hide />
            <Tooltip cursor={{ fill: "rgba(0,0,0,.04)" }} contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid #e7e2d6" }} />
            <Bar dataKey="value" radius={[3, 3, 0, 0]}>
              {bySev.map((e) => <Cell key={e.key} fill={e.fill} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function Stat({ n, label, accent }) {
  return (
    <div style={S.stat}>
      <div style={{...S.statN, ...(accent ? {color:"#c0392b"} : {})}}>{n}</div>
      <div style={S.statL}>{label}</div>
    </div>
  );
}
function Chip({ active, onClick, children }) {
  return <button onClick={onClick} style={{...S.chip, ...(active ? S.chipOn : {})}}>{children}</button>;
}
function SevPill({ sev }) {
  const s = SEV[sev] || SEV.info;
  return <span style={{...S.pill, color:s.ink, background:s.bg}}><span style={{...S.pillDot, background:s.dot}} />{s.label}</span>;
}
function StatusPill({ status }) {
  const s = STATUS[status] || STATUS.pending;
  return <span style={{...S.pill, color:s.ink, background:s.bg}}>{s.label}</span>;
}
function Spinner() {
  return <span style={S.spinner} />;
}
function Screen({ children }) {
  return <div style={{...S.page, display:"flex", alignItems:"center", justifyContent:"center", minHeight:"100vh"}}>
    <div style={{color:"#7c776b", fontSize:14, display:"flex", alignItems:"center", gap:8}}>{children}</div>
  </div>;
}

const CSS = `
* { box-sizing: border-box; }
body { margin: 0; }
@keyframes fade { from { opacity: 0; transform: translateY(4px);} to {opacity:1; transform:none;} }
@keyframes spin { to { transform: rotate(360deg); } }
button { font-family: inherit; cursor: pointer; }
a { text-decoration: none; }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; } }
`;

const mono = "ui-monospace, 'SF Mono', Menlo, monospace";
const S = {
  page: { minHeight: "100vh", background: "#f7f5ef", fontFamily: "ui-sans-serif, -apple-system, 'Segoe UI', system-ui, sans-serif", color: "#2b2822", padding: "28px 20px" },
  shell: { maxWidth: 860, margin: "0 auto" },
  head: { marginBottom: 22 },
  brandRow: { display: "flex", alignItems: "center", gap: 10 },
  mark: { fontSize: 20, color: "#c0392b" },
  brand: { fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", margin: 0 },
  user: { fontFamily: mono, fontSize: 13, color: "#7c776b" },
  tag: { margin: "6px 0 0 30px", color: "#7c776b", fontSize: 14 },

  band: { display: "grid", gridTemplateColumns: "repeat(3, auto) 1fr", gap: 14, alignItems: "stretch", padding: "18px 20px", background: "#fff", border: "1px solid #e7e2d6", borderRadius: 14, marginBottom: 20 },
  stat: { paddingRight: 18, borderRight: "1px solid #efeae0" },
  statN: { fontSize: 30, fontWeight: 700, lineHeight: 1, letterSpacing: "-0.03em" },
  statL: { fontSize: 12, color: "#8a8578", marginTop: 5 },
  chartCard: { paddingLeft: 6 },
  chartLabel: { fontSize: 11, color: "#8a8578", marginBottom: 2, textTransform: "uppercase", letterSpacing: "0.06em" },

  filters: { display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 },
  chip: { border: "1px solid #e2ddd0", background: "#fff", color: "#5f5a4f", padding: "6px 13px", borderRadius: 999, fontSize: 13, display: "inline-flex", alignItems: "center", gap: 6 },
  chipOn: { background: "#2b2822", color: "#f7f5ef", borderColor: "#2b2822" },
  off: { fontSize: 10, textTransform: "uppercase", letterSpacing: "0.05em", opacity: 0.5 },

  list: { display: "flex", flexDirection: "column", gap: 10 },
  row: { background: "#fff", border: "1px solid #e7e2d6", borderRadius: 12, overflow: "hidden" },
  rowOpen: { borderColor: "#d8d1c0" },
  rowHead: { width: "100%", border: 0, background: "transparent", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 16px", textAlign: "left", gap: 12 },
  rowMain: { minWidth: 0 },
  rowTitleLine: { display: "flex", alignItems: "baseline", gap: 8 },
  pr: { fontFamily: mono, fontSize: 13, color: "#c0392b", fontWeight: 600 },
  rowTitle: { fontSize: 15, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  rowMeta: { display: "flex", alignItems: "center", gap: 7, marginTop: 5, fontSize: 12.5, color: "#8a8578" },
  repoTag: { fontFamily: mono, fontSize: 12 },
  dot: { opacity: 0.4 },
  rowRight: { display: "flex", alignItems: "center", gap: 9, flexShrink: 0 },
  chev: { fontSize: 20, color: "#b8b2a4", transition: "transform .15s", display: "inline-block", width: 12 },

  body: { padding: "4px 16px 16px", animation: "fade .18s ease" },
  finding: { display: "flex", gap: 12, padding: "12px 0", borderTop: "1px solid #f0ece2" },
  sevBar: { width: 3, borderRadius: 3, flexShrink: 0 },
  findingTop: { display: "flex", alignItems: "center", gap: 9, marginBottom: 5 },
  loc: { fontFamily: mono, fontSize: 12, color: "#6f6a5e", background: "#f4f1e8", padding: "2px 7px", borderRadius: 5 },
  findingBody: { margin: 0, fontSize: 14, lineHeight: 1.5, color: "#413d34" },
  noFindings: { padding: "14px 0", color: "#8a8578", fontSize: 13.5, fontStyle: "italic", display:"flex", alignItems:"center", gap:8 },

  pill: { display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, fontWeight: 600, padding: "3px 9px", borderRadius: 999, whiteSpace: "nowrap" },
  pillDot: { width: 6, height: 6, borderRadius: 999 },

  empty: { textAlign: "center", padding: "48px 20px", color: "#8a8578", fontSize: 14, background: "#fff", border: "1px dashed #ddd6c6", borderRadius: 12, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:8 },
  errorBox: { padding: "16px 18px", background: "#fbeaea", border: "1px solid #f0d4d4", borderRadius: 12, color: "#7c1d1d", fontSize: 14, display:"flex", alignItems:"center", gap:12 },
  retry: { border:"1px solid #d9a", background:"#fff", color:"#7c1d1d", padding:"4px 12px", borderRadius:8, fontSize:13 },

  connectChip: { borderStyle: "dashed", color: "#7c776b" },
  connectPanel: { background: "#fff", border: "1px solid #e7e2d6", borderRadius: 12, padding: "14px 16px", marginBottom: 16 },
  connectHead: { fontSize: 13, fontWeight: 600, marginBottom: 10, display: "flex", flexDirection: "column", gap: 3 },
  connectHint: { fontWeight: 400, fontSize: 12, color: "#8a8578" },
  connectErr: { background: "#fbeaea", border: "1px solid #f0d4d4", color: "#7c1d1d", fontSize: 13, borderRadius: 8, padding: "8px 11px", marginBottom: 10 },
  connectRow: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "9px 0", borderTop: "1px solid #f0ece2" },
  connectName: { fontFamily: mono, fontSize: 13 },
  privateTag: { fontSize: 10, textTransform: "uppercase", letterSpacing: "0.05em", color: "#8a8578", border: "1px solid #e2ddd0", borderRadius: 4, padding: "1px 5px", marginLeft: 8 },
  connectBtn: { border: "1px solid #2b2822", background: "#2b2822", color: "#f7f5ef", padding: "5px 13px", borderRadius: 8, fontSize: 12.5, fontWeight: 600, flexShrink: 0 },
  connectBtnOn: { background: "#fff", color: "#7c1d1d", borderColor: "#e0c4c4" },

  loginBtn: { display:"inline-block", background:"#2b2822", color:"#f7f5ef", padding:"11px 22px", borderRadius:10, fontSize:14, fontWeight:600 },
  spinner: { width:13, height:13, border:"2px solid #d8d1c0", borderTopColor:"#c0392b", borderRadius:"50%", display:"inline-block", animation:"spin .7s linear infinite" },
};
