/* global React, ReactDOM */
const { useState, useEffect, useRef, useMemo } = React;

// ============ TWEAKS ============
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "green",
  "density": "comfortable",
  "summaryShape": "cards",
  "theme": "dark"
}/*EDITMODE-END*/;

const ACCENTS = {
  green:  { name: "green",  hex: "oklch(0.82 0.17 145)", dim: "oklch(0.55 0.12 145)", glow: "oklch(0.82 0.17 145 / 0.18)" },
  amber:  { name: "amber",  hex: "oklch(0.82 0.17 75)",  dim: "oklch(0.55 0.12 75)",  glow: "oklch(0.82 0.17 75 / 0.18)"  },
  cyan:   { name: "cyan",   hex: "oklch(0.82 0.12 220)", dim: "oklch(0.55 0.10 220)", glow: "oklch(0.82 0.12 220 / 0.18)" },
  magenta:{ name: "magenta",hex: "oklch(0.78 0.17 340)", dim: "oklch(0.55 0.13 340)", glow: "oklch(0.78 0.17 340 / 0.18)" },
  paper:  { name: "paper",  hex: "oklch(0.92 0.01 90)",  dim: "oklch(0.60 0.01 90)",  glow: "oklch(0.92 0.01 90 / 0.12)"  },
};

// ============ DATA ============
const TODAY = "2026-04-18";
const USER = { name: "evgeny.fomin", email: "evgenyfomin999@gmail.com", joined: "2026-02-04" };

const TOPICS = [
  { id: "foundation", tag: "foundation-models", count: 4 },
  { id: "robotics",   tag: "robotics",          count: 2 },
  { id: "chips",      tag: "silicon",           count: 3 },
  { id: "regulation", tag: "policy",            count: 1 },
  { id: "opensrc",    tag: "open-source",       count: 3 },
  { id: "apps",       tag: "consumer-apps",     count: 2 },
];

const STORIES = [
  {
    id: "s1",
    tag: "foundation-models",
    title: "Anthropic ships Claude 4 Opus with 2M-token context",
    tldr: "Opus 4 extends context to 2M tokens and posts a 71% score on SWE-bench verified, per the model card. Pricing held at the Opus 3.5 tier.",
    body: [
      "The release doubles the previous ceiling. Latency on full-window requests remains the open question — early reports from the preview program suggest p50 around 18s for 1M-token prompts.",
      "Benchmark gains concentrated on long-horizon coding and multi-document synthesis; MMLU effectively flat.",
    ],
    sources: [
      { name: "anthropic.com/news", kind: "blog" },
      { name: "arxiv:2604.01182",   kind: "paper" },
    ],
    time: "06:14",
    readMin: 4,
    impact: 0.92,
  },
  {
    id: "s2",
    tag: "silicon",
    title: "TSMC 2nm risk production slips to Q3; Apple and NVIDIA re-allocate wafers",
    tldr: "Yield at N2 reportedly stuck near 55%. Apple A20 Pro and NVIDIA Rubin initial shipments pushed one quarter.",
    body: [
      "Supply chain notes from three independent analysts converged on the same delay window. Samsung Foundry is pitching 2nm GAA as a fallback, but customer interest remains limited.",
    ],
    sources: [
      { name: "digitimes",     kind: "report" },
      { name: "semianalysis",  kind: "blog" },
    ],
    time: "08:02",
    readMin: 3,
    impact: 0.74,
  },
  {
    id: "s3",
    tag: "robotics",
    title: "Figure 03 demos continuous 8-hour warehouse shift at BMW plant",
    tldr: "First public footage of a humanoid completing a full shift without teleop. Cycle-time still 1.8× human baseline.",
    body: [
      "Figure released telemetry for 412 pick-and-place operations. Battery swap took 94 seconds; no unplanned interventions in the documented window.",
    ],
    sources: [{ name: "figure.ai/blog", kind: "blog" }],
    time: "11:40",
    readMin: 2,
    impact: 0.68,
  },
  {
    id: "s4",
    tag: "open-source",
    title: "Mistral releases Magistral-Large under Apache 2.0",
    tldr: "123B MoE model, 22B active. Matches Llama 4 Maverick on open benchmarks. Weights live on HuggingFace.",
    body: [
      "License is notably permissive — commercial use unrestricted. Inference requires 2×H100 at bf16; q4 community ports expected within 48h.",
    ],
    sources: [
      { name: "mistral.ai",     kind: "blog" },
      { name: "huggingface.co", kind: "repo" },
    ],
    time: "13:55",
    readMin: 3,
    impact: 0.81,
  },
  {
    id: "s5",
    tag: "policy",
    title: "EU AI Act: first enforcement action against undisclosed training data",
    tldr: "€34M fine against a mid-tier European lab for training corpus non-disclosure under Article 52.",
    body: [
      "The ruling sets precedent on what 'sufficiently detailed summary' of training data means. Industry groups have 60 days to appeal.",
    ],
    sources: [{ name: "europa.eu/press", kind: "press" }],
    time: "15:20",
    readMin: 2,
    impact: 0.55,
  },
  {
    id: "s6",
    tag: "consumer-apps",
    title: "Perplexity crosses 40M MAU; rolls out agentic browser to all users",
    tldr: "Comet exits beta. New data: 31% of queries now involve multi-step actions (booking, purchase, filing).",
    body: [
      "Commerce take-rate disclosed for the first time at 2.1%. Search ad revenue growing 9% QoQ despite the shift.",
    ],
    sources: [{ name: "perplexity.ai/blog", kind: "blog" }],
    time: "17:08",
    readMin: 3,
    impact: 0.63,
  },
];

// ============ HELPERS ============
const ascii = {
  box: (w) => "─".repeat(Math.max(0, w)),
  bar: (v, w = 20) => {
    const filled = Math.round(v * w);
    return "█".repeat(filled) + "░".repeat(w - filled);
  },
};

function useLocalState(key, initial) {
  const [v, setV] = useState(() => {
    try { const r = localStorage.getItem(key); return r ? JSON.parse(r) : initial; } catch { return initial; }
  });
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(v)); } catch {} }, [key, v]);
  return [v, setV];
}

// ============ ROOT ============
function App() {
  const [tweaks, setTweaks] = useState(TWEAK_DEFAULTS);
  const [tweaksOpen, setTweaksOpen] = useState(false);
  const [page, setPage] = useLocalState("ain:page", "signin"); // signin | home | settings
  const [clock, setClock] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Tweaks protocol
  useEffect(() => {
    const handler = (e) => {
      if (!e.data) return;
      if (e.data.type === "__activate_edit_mode")   setTweaksOpen(true);
      if (e.data.type === "__deactivate_edit_mode") setTweaksOpen(false);
    };
    window.addEventListener("message", handler);
    window.parent.postMessage({ type: "__edit_mode_available" }, "*");
    return () => window.removeEventListener("message", handler);
  }, []);

  const updateTweak = (patch) => {
    const next = { ...tweaks, ...patch };
    setTweaks(next);
    window.parent.postMessage({ type: "__edit_mode_set_keys", edits: patch }, "*");
  };

  const accent = ACCENTS[tweaks.accent] || ACCENTS.green;
  const isLight = tweaks.theme === "light";

  // theme vars
  const vars = isLight ? {
    "--bg":     "oklch(0.97 0.005 90)",
    "--bg2":    "oklch(0.94 0.005 90)",
    "--panel":  "oklch(1 0 0)",
    "--line":   "oklch(0.86 0.01 90)",
    "--text":   "oklch(0.24 0.01 260)",
    "--dim":    "oklch(0.50 0.01 260)",
    "--faint":  "oklch(0.72 0.01 260)",
    "--accent": accent.hex.replace("0.82", "0.52").replace("0.78", "0.48").replace("0.92", "0.55"),
    "--glow":   accent.glow,
  } : {
    "--bg":     "oklch(0.17 0.01 260)",
    "--bg2":    "oklch(0.21 0.01 260)",
    "--panel":  "oklch(0.20 0.01 260)",
    "--line":   "oklch(0.30 0.01 260)",
    "--text":   "oklch(0.93 0.01 90)",
    "--dim":    "oklch(0.68 0.01 260)",
    "--faint":  "oklch(0.45 0.01 260)",
    "--accent": accent.hex,
    "--glow":   accent.glow,
  };

  const densityPad = tweaks.density === "dense" ? 10 : tweaks.density === "comfortable" ? 16 : 24;

  return (
    <div className="root" style={{ ...vars, "--pad": densityPad + "px" }}>
      <TopBar page={page} setPage={setPage} clock={clock} tweaks={tweaks} />
      <main className="main">
        {page === "signin"   && <SignIn onSignIn={() => setPage("home")} accent={accent} />}
        {page === "home"     && <Home setPage={setPage} tweaks={tweaks} />}
        {page === "settings" && <Settings setPage={setPage} tweaks={tweaks} />}
      </main>
      <StatusBar page={page} clock={clock} tweaks={tweaks} />
      {tweaksOpen && <TweaksPanel tweaks={tweaks} update={updateTweak} onClose={() => setTweaksOpen(false)} />}
    </div>
  );
}

// ============ TOP BAR ============
function TopBar({ page, setPage, clock, tweaks }) {
  const signed = page !== "signin";
  return (
    <header className="topbar">
      <div className="topbar-left">
        <Logo />
        <span className="crumb">
          <span className="dim">~/</span>
          <span className="ln">ai-news</span>
          <span className="dim">/</span>
          <span className="ln">{page}</span>
        </span>
      </div>
      <div className="topbar-right">
        <span className="dim mono small hide-sm">{TODAY} · v0.42.1</span>
        {signed && (
          <>
            <button className="btn-ghost" onClick={() => setPage("home")}>home</button>
            <button className="btn-ghost" onClick={() => setPage("settings")}>settings</button>
            <button className="btn-ghost" onClick={() => setPage("signin")}>logout</button>
          </>
        )}
      </div>
    </header>
  );
}

function Logo() {
  return (
    <div className="logo" aria-label="AI News">
      <span className="logo-bracket">[</span>
      <span className="logo-a">AI</span>
      <span className="logo-dot">·</span>
      <span className="logo-n">news</span>
      <span className="logo-bracket">]</span>
    </div>
  );
}

// ============ STATUS BAR ============
function StatusBar({ page, clock, tweaks }) {
  const t = clock.toISOString().slice(11, 19) + " UTC";
  return (
    <footer className="statusbar">
      <span>● connected</span>
      <span className="dim">│</span>
      <span>transport: telegram</span>
      <span className="dim">│</span>
      <span className="hide-sm">feed: 6 items · 2026-04-18</span>
      <span className="spacer" />
      <span className="hide-sm">{tweaks.density} · {tweaks.accent}</span>
      <span className="dim">│</span>
      <span>{t}</span>
    </footer>
  );
}

// ============ SIGN IN ============
function SignIn({ onSignIn, accent }) {
  const [typed, setTyped] = useState("");
  const target = "$ auth --provider=google --scope=read:news";
  useEffect(() => {
    let i = 0;
    const iv = setInterval(() => {
      i++;
      setTyped(target.slice(0, i));
      if (i >= target.length) clearInterval(iv);
    }, 35);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="signin">
      <div className="signin-grid">
        <section className="signin-left">
          <div className="kicker">
            <span className="blink">▊</span> daily brief · ingested overnight
          </div>
          <h1 className="hero">
            A terminal<br/>for everything<br/>shipping in AI.
          </h1>
          <p className="lead">
            <span className="accent">AI News</span> reads the firehose so you don't. Tell it what
            you care about, wake up to a signed-off brief in your inbox or Telegram.
          </p>
          <div className="ascii-block">
{`╭──────────────────────────────────────────╮
│  today's digest · ${TODAY}              │
│  ──────────────────────────────────────  │
│  06:14  foundation-models    opus 4      │
│  08:02  silicon              tsmc n2     │
│  11:40  robotics             figure 03   │
│  13:55  open-source          mistral     │
│  15:20  policy               eu ai act   │
│  17:08  consumer-apps        perplexity  │
╰──────────────────────────────────────────╯`}
          </div>
          <div className="stats">
            <Stat k="sources scanned" v="1,284" />
            <Stat k="avg read time" v="6 min" />
            <Stat k="delivered at" v="07:00 local" />
          </div>
        </section>

        <section className="signin-right">
          <div className="auth-card">
            <div className="auth-head">
              <span className="dot dot-r"/><span className="dot dot-y"/><span className="dot dot-g"/>
              <span className="auth-title">sign_in.sh</span>
            </div>
            <pre className="auth-term">
              <span className="dim">#!/bin/sh</span>{"\n"}
              <span className="dim"># authenticate to ai-news</span>{"\n"}
              {"\n"}
              <span className="accent">{typed}</span>
              <span className="blink">▊</span>
            </pre>
            <button className="btn-primary" onClick={onSignIn}>
              <GoogleMark /> continue with google
            </button>
            <button className="btn-secondary" onClick={onSignIn}>
              continue with magic link
            </button>
            <div className="auth-foot">
              <span className="dim">by continuing you accept</span>{" "}
              <a href="#" className="ln-underline">/terms</a>{" · "}
              <a href="#" className="ln-underline">/privacy</a>
            </div>
          </div>
          <div className="sidecard">
            <div className="sidecard-row">
              <span className="dim">status</span>
              <span><span className="dot-live"/> all systems operational</span>
            </div>
            <div className="sidecard-row">
              <span className="dim">last incident</span>
              <span>14 days ago</span>
            </div>
            <div className="sidecard-row">
              <span className="dim">readers</span>
              <span>4,281 active</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function Stat({ k, v }) {
  return (
    <div className="stat">
      <div className="stat-v">{v}</div>
      <div className="stat-k">{k}</div>
    </div>
  );
}

function GoogleMark() {
  return (
    <svg width="14" height="14" viewBox="0 0 48 48" aria-hidden>
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.5l6.7-6.7C35.6 2.3 30.1 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.8 6c1.9-5.6 7.2-9.7 13.6-9.7z"/>
      <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.2-.4-4.7H24v9h12.6c-.5 2.9-2.2 5.3-4.7 6.9l7.6 5.9c4.4-4 7-10 7-17.1z"/>
      <path fill="#FBBC05" d="M10.4 28.8c-.5-1.4-.8-2.9-.8-4.4s.3-3 .8-4.4l-7.8-6C.9 17.3 0 20.6 0 24s.9 6.7 2.6 9.8l7.8-6z"/>
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.6-5.9c-2.1 1.4-4.8 2.3-8.3 2.3-6.4 0-11.7-4.1-13.6-9.7l-7.8 6C6.5 42.6 14.6 48 24 48z"/>
    </svg>
  );
}

// ============ HOME ============
function Home({ setPage, tweaks }) {
  const [filter, setFilter] = useState("all");
  const [expanded, setExpanded] = useState(null);
  const filtered = filter === "all" ? STORIES : STORIES.filter(s => s.tag === filter);

  return (
    <div className="home">
      <section className="home-head">
        <div className="home-head-l">
          <div className="kicker"><span className="accent">●</span> brief · {TODAY}</div>
          <h2 className="h2">
            good morning, <span className="accent">{USER.name}</span>
            <span className="dim h2-dim"> — here's what happened while you slept.</span>
          </h2>
          <div className="meta-row">
            <span className="pill"><span className="accent">6</span> stories</span>
            <span className="pill"><span className="accent">~14</span> min read</span>
            <span className="pill">confidence <span className="accent">hi</span></span>
            <span className="pill">sources <span className="accent">1,284</span></span>
          </div>
        </div>
        <div className="home-head-r">
          <ImpactChart />
          <div className="impact-cap">signal / noise · last 7d</div>
        </div>
      </section>

      <section className="filter-row">
        <Chip active={filter === "all"} onClick={() => setFilter("all")}>all</Chip>
        {TOPICS.map(t => (
          <Chip key={t.id} active={filter === t.tag} onClick={() => setFilter(t.tag)}>
            {t.tag} <span className="dim">·{t.count}</span>
          </Chip>
        ))}
        <span className="spacer" />
        <button className="btn-ghost" onClick={() => setPage("settings")}>⚙ tune interests</button>
        <button className="btn-primary small">↻ regenerate</button>
      </section>

      {tweaks.summaryShape === "cards" && (
        <div className="cards-grid">
          {filtered.map((s, i) => (
            <StoryCard key={s.id} s={s} i={i} expanded={expanded === s.id} onExpand={() => setExpanded(expanded === s.id ? null : s.id)} />
          ))}
        </div>
      )}
      {tweaks.summaryShape === "bullets" && (
        <div className="bullet-list">
          {filtered.map((s, i) => <BulletRow key={s.id} s={s} i={i} />)}
        </div>
      )}
      {tweaks.summaryShape === "longform" && (
        <div className="longform">
          {filtered.map((s, i) => <LongformBlock key={s.id} s={s} i={i} />)}
        </div>
      )}
    </div>
  );
}

function Chip({ active, onClick, children }) {
  return (
    <button className={"chip" + (active ? " chip-active" : "")} onClick={onClick}>
      <span className="dim">&gt;</span> {children}
    </button>
  );
}

function StoryCard({ s, i, expanded, onExpand }) {
  return (
    <article className={"card" + (expanded ? " card-exp" : "")}>
      <div className="card-head">
        <span className="card-idx">{String(i + 1).padStart(2, "0")}</span>
        <span className="card-tag">#{s.tag}</span>
        <span className="spacer" />
        <span className="card-time dim">{s.time}</span>
      </div>
      <h3 className="card-title">{s.title}</h3>
      <p className="card-tldr">{s.tldr}</p>
      {expanded && (
        <div className="card-body">
          {s.body.map((p, k) => <p key={k}>{p}</p>)}
          <div className="card-sources">
            {s.sources.map((src, k) => (
              <span key={k} className="src">
                <span className="dim">[{src.kind}]</span> {src.name}
              </span>
            ))}
          </div>
        </div>
      )}
      <div className="card-foot">
        <span className="ascii-bar" title={`impact ${Math.round(s.impact * 100)}%`}>
          impact <span className="accent">{ascii.bar(s.impact, 12)}</span>
        </span>
        <span className="spacer" />
        <span className="dim small">{s.readMin}m read</span>
        <button className="btn-ghost small" onClick={onExpand}>{expanded ? "collapse" : "expand"} →</button>
      </div>
    </article>
  );
}

function BulletRow({ s, i }) {
  return (
    <div className="bullet">
      <span className="bullet-idx">{String(i + 1).padStart(2, "0")}</span>
      <span className="bullet-tag">#{s.tag}</span>
      <div className="bullet-body">
        <div className="bullet-title">{s.title}</div>
        <div className="bullet-tldr dim">{s.tldr}</div>
      </div>
      <span className="bullet-time dim">{s.time}</span>
    </div>
  );
}

function LongformBlock({ s, i }) {
  return (
    <section className="long">
      <header className="long-head">
        <span className="long-idx">§{String(i + 1).padStart(2, "0")}</span>
        <span className="long-tag">#{s.tag}</span>
        <span className="spacer" />
        <span className="dim small">{s.time} · {s.readMin}m</span>
      </header>
      <h3 className="long-title">{s.title}</h3>
      <p className="long-tldr"><span className="accent">TL;DR — </span>{s.tldr}</p>
      {s.body.map((p, k) => <p key={k} className="long-p">{p}</p>)}
      <div className="long-sources">
        sources: {s.sources.map((src, k) => (
          <span key={k} className="src-inline">
            {k > 0 && <span className="dim"> · </span>}
            <span className="ln-underline">{src.name}</span>
          </span>
        ))}
      </div>
    </section>
  );
}

function ImpactChart() {
  const data = [0.4, 0.55, 0.3, 0.7, 0.45, 0.82, 0.74];
  const days = ["M","T","W","T","F","S","S"];
  return (
    <div className="impact">
      {data.map((v, i) => (
        <div key={i} className="impact-col">
          <div className="impact-bar" style={{ height: (v * 100) + "%" }} />
          <div className="impact-lbl">{days[i]}</div>
        </div>
      ))}
    </div>
  );
}

// ============ SETTINGS ============
const SUGGESTED_TAGS = [
  "foundation-models","robotics","silicon","policy","open-source","consumer-apps",
  "agents","evaluations","multimodal","biotech","bci","quantum","safety","voice",
  "image-gen","video-gen","llm-ops","fine-tuning","rag","coding-copilots"
];

function Settings({ setPage, tweaks }) {
  const [interests, setInterests] = useLocalState("ain:interests", ["foundation-models","open-source","silicon","agents"]);
  const [draft, setDraft] = useState("");
  const [schedule, setSchedule] = useLocalState("ain:schedule", "07:00");
  const [tz, setTz] = useLocalState("ain:tz", "Europe/Amsterdam");
  const [transport, setTransport] = useLocalState("ain:transport", "telegram");
  const [telegramLinked, setTelegramLinked] = useLocalState("ain:tg", true);

  const addInterest = (t) => {
    const v = (t || draft).trim().toLowerCase().replace(/\s+/g, "-");
    if (!v) return;
    if (!interests.includes(v)) setInterests([...interests, v]);
    setDraft("");
  };
  const remove = (t) => setInterests(interests.filter(x => x !== t));

  return (
    <div className="settings">
      <div className="set-head">
        <button className="btn-ghost" onClick={() => setPage("home")}>← back</button>
        <h2 className="h2">settings<span className="accent">.</span>config</h2>
        <span className="spacer" />
        <span className="dim small">last saved · 12m ago</span>
      </div>

      <div className="set-grid">
        <Panel title="account" section="01">
          <Row k="display name" v={
            <span>Evgeny Fomin <span className="dim">· {USER.name}</span></span>
          } />
          <Row k="email" v={USER.email} />
          <Row k="joined" v={USER.joined} />
          <Row k="plan" v={<span><span className="accent">pro</span> · $8/mo · renews 2026-05-04</span>} />
        </Panel>

        <Panel title="interests" section="02" sub="chips feed the overnight summarizer. 4–12 recommended.">
          <div className="chips-input">
            {interests.map(t => (
              <span key={t} className="tag">
                <span className="dim">&gt;</span> {t}
                <button onClick={() => remove(t)} className="tag-x">×</button>
              </span>
            ))}
            <input
              className="tag-input"
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter") { e.preventDefault(); addInterest(); } if (e.key === "Backspace" && !draft) { setInterests(interests.slice(0, -1)); } }}
              placeholder={interests.length ? "" : "type and press enter…"}
            />
          </div>
          <div className="sugg">
            <span className="dim small">suggestions &nbsp;</span>
            {SUGGESTED_TAGS.filter(t => !interests.includes(t)).slice(0, 10).map(t => (
              <button key={t} className="sugg-chip" onClick={() => addInterest(t)}>+ {t}</button>
            ))}
          </div>
          <div className="interest-meter">
            <span className="dim small">coverage </span>
            <span className="accent">{ascii.bar(Math.min(interests.length / 8, 1), 18)}</span>
            <span className="dim small"> &nbsp; {interests.length}/8 ideal</span>
          </div>
        </Panel>

        <Panel title="delivery" section="03" sub="when and where your brief arrives.">
          <Row k="schedule" v={
            <div className="time-row">
              {["06:00","07:00","08:00","09:00","21:00"].map(t => (
                <button key={t} className={"time-pill" + (schedule === t ? " on" : "")} onClick={() => setSchedule(t)}>{t}</button>
              ))}
            </div>
          } />
          <Row k="timezone" v={
            <select className="select" value={tz} onChange={e => setTz(e.target.value)}>
              <option>Europe/Amsterdam</option>
              <option>Europe/London</option>
              <option>America/New_York</option>
              <option>America/Los_Angeles</option>
              <option>Asia/Singapore</option>
              <option>UTC</option>
            </select>
          } />
          <Row k="channel" v={
            <div className="channels">
              {[
                { id: "telegram", lbl: "telegram" },
                { id: "email",    lbl: "email" },
                { id: "rss",      lbl: "rss" },
                { id: "web",      lbl: "web only" },
              ].map(c => (
                <button key={c.id} className={"channel" + (transport === c.id ? " on" : "")} onClick={() => setTransport(c.id)}>
                  <span className="dim">[{transport === c.id ? "×" : " "}]</span> {c.lbl}
                </button>
              ))}
            </div>
          } />
        </Panel>

        <Panel title="telegram" section="04" sub={transport === "telegram" ? "primary transport" : "available transport"}>
          {telegramLinked ? (
            <>
              <div className="tg-linked">
                <span className="dot-live" /> linked to <span className="ln">@evgeny_fomin</span>
                <span className="dim"> · chat_id 943311563</span>
              </div>
              <div className="tg-actions">
                <button className="btn-secondary small">send test message</button>
                <button className="btn-secondary small">rotate token</button>
                <button className="btn-danger small" onClick={() => setTelegramLinked(false)}>unlink</button>
              </div>
              <pre className="tg-preview">
{`┌─ preview ─────────────────────────────
│ AI News · ${TODAY}
│ ──────────────────────────────────────
│ 1. Anthropic ships Claude 4 Opus…
│ 2. TSMC 2nm risk production slips…
│ 3. Figure 03 demos 8-hour shift…
│ + 3 more · tap to open web
└───────────────────────────────────────`}
              </pre>
            </>
          ) : (
            <>
              <Row k="bot token" v={<input className="input mono" placeholder="paste new token…" />} />
              <Row k="chat id"   v={<input className="input mono" placeholder="943311563" />} />
              <div className="tg-actions">
                <button className="btn-primary small" onClick={() => setTelegramLinked(true)}>link account</button>
                <button className="btn-secondary small">send /start to @ai_news_bot</button>
              </div>
            </>
          )}
        </Panel>

        <Panel title="danger" section="05" sub="irreversible operations.">
          <div className="danger">
            <button className="btn-secondary small">export all data (.json)</button>
            <button className="btn-secondary small">purge cache</button>
            <button className="btn-danger small">delete account</button>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Panel({ title, section, sub, children }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <span className="panel-sec">§{section}</span>
        <span className="panel-title">{title}</span>
        <span className="panel-dots">{".".repeat(40)}</span>
      </header>
      {sub && <p className="panel-sub">{sub}</p>}
      <div className="panel-body">{children}</div>
    </section>
  );
}

function Row({ k, v }) {
  return (
    <div className="row">
      <div className="row-k">{k}</div>
      <div className="row-v">{v}</div>
    </div>
  );
}

// ============ TWEAKS PANEL ============
function TweaksPanel({ tweaks, update, onClose }) {
  return (
    <aside className="tweaks">
      <header className="tweaks-head">
        <span className="accent">tweaks</span>
        <span className="dim">· live</span>
        <span className="spacer" />
        <button className="tweaks-x" onClick={onClose}>×</button>
      </header>
      <div className="tweaks-body">
        <div className="tw-group">
          <div className="tw-label">accent</div>
          <div className="tw-row">
            {Object.keys(ACCENTS).map(k => (
              <button key={k}
                className={"swatch" + (tweaks.accent === k ? " on" : "")}
                onClick={() => update({ accent: k })}
                title={k}
              >
                <span className="swatch-chip" style={{ background: ACCENTS[k].hex }} />
                <span className="swatch-lbl">{k}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="tw-group">
          <div className="tw-label">density</div>
          <div className="tw-row">
            {["dense","comfortable","spacious"].map(d => (
              <button key={d} className={"tw-pill" + (tweaks.density === d ? " on" : "")} onClick={() => update({ density: d })}>{d}</button>
            ))}
          </div>
        </div>
        <div className="tw-group">
          <div className="tw-label">summary shape</div>
          <div className="tw-row">
            {[
              { id: "cards",    lbl: "cards" },
              { id: "bullets",  lbl: "bullets" },
              { id: "longform", lbl: "long-form" },
            ].map(s => (
              <button key={s.id} className={"tw-pill" + (tweaks.summaryShape === s.id ? " on" : "")} onClick={() => update({ summaryShape: s.id })}>{s.lbl}</button>
            ))}
          </div>
        </div>
        <div className="tw-group">
          <div className="tw-label">theme</div>
          <div className="tw-row">
            {["dark","light"].map(t => (
              <button key={t} className={"tw-pill" + (tweaks.theme === t ? " on" : "")} onClick={() => update({ theme: t })}>{t}</button>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
