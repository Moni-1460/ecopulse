/* EcoPulse frontend logic. No build step -- plain fetch + DOM. */

const API = "/api";

const PLATFORM_COLORS = {
  instagram: "var(--instagram)",
  twitter: "var(--twitter)",
  linkedin: "var(--linkedin)",
  facebook: "var(--facebook)",
};
const PLATFORM_HEX = {
  instagram: "#C98BAE",
  twitter: "#7FB0C9",
  linkedin: "#6F9BC9",
  facebook: "#8FA0D9",
};

// ---------- Tabs ----------
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => { b.classList.remove("active"); b.setAttribute("aria-selected", "false"); });
    btn.classList.add("active");
    btn.setAttribute("aria-selected", "true");
    const target = btn.dataset.tab;
    document.querySelectorAll(".tab-panel").forEach(p => p.hidden = true);
    document.getElementById(`tab-${target}`).hidden = false;
    if (target === "history") loadHistory();
    if (target === "analytics") loadAnalytics();
  });
});

// ---------- Pill groups (platform / tone) ----------
document.querySelectorAll(".pill-group").forEach(group => {
  group.addEventListener("click", (e) => {
    const btn = e.target.closest(".pill");
    if (!btn) return;
    group.querySelectorAll(".pill").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    group.dataset.value = btn.dataset.value;
  });
});

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { el.hidden = true; }, 3200);
}

// ---------- Generate ----------
const form = document.getElementById("generate-form");
const generateBtn = document.getElementById("generate-btn");
const formError = document.getElementById("form-error");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  formError.hidden = true;

  const payload = {
    topic: document.getElementById("topic").value.trim(),
    platform: document.getElementById("platform-group").dataset.value,
    tone: document.getElementById("tone-group").dataset.value,
    keywords: document.getElementById("keywords").value.trim() || null,
    use_past_examples: document.getElementById("use-examples").checked,
  };

  generateBtn.disabled = true;
  generateBtn.querySelector(".btn-label").textContent = "Growing your post...";

  try {
    const res = await fetch(`${API}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Request failed (${res.status})`);
    }
    const post = await res.json();
    renderResult(post);
    toast("New post generated 🌱");
  } catch (err) {
    formError.textContent = err.message;
    formError.hidden = false;
  } finally {
    generateBtn.disabled = false;
    generateBtn.querySelector(".btn-label").textContent = "Generate post";
  }
});

function renderResult(post) {
  document.getElementById("result-empty").hidden = true;
  const card = document.getElementById("result-card");
  card.hidden = false;
  card.innerHTML = postCardHTML(post);
  attachCardHandlers(card, post);
}

// ---------- Post card builder (shared between Generate + History) ----------
function postCardHTML(post) {
  const dotColor = PLATFORM_HEX[post.platform] || "#8FA876";
  const hashtags = (post.hashtags || "")
    .split(",")
    .map(h => h.trim())
    .filter(Boolean)
    .map(h => `#${h}`)
    .join("  ");
  const scheduled = post.scheduled_at
    ? `<span class="schedule-note">📅 scheduled for ${new Date(post.scheduled_at).toLocaleString()}</span>`
    : `<span class="schedule-note"></span>`;

  return `
    <div class="card-meta">
      <span class="platform-dot" style="background:${dotColor}"></span>
      ${post.platform} · ${post.tone}
    </div>
    <p class="card-topic">"${escapeHTML(post.topic)}"</p>
    <p class="card-content">${escapeHTML(post.content)}</p>
    ${hashtags ? `<p class="card-hashtags">${escapeHTML(hashtags)}</p>` : ""}
    ${post.cta ? `<p class="card-cta">${escapeHTML(post.cta)}</p>` : ""}
    <div class="card-actions" data-id="${post.id}">
      <button class="icon-btn up ${post.rating === "up" ? "rated-up" : ""}" title="Rate up">👍 good</button>
      <button class="icon-btn down ${post.rating === "down" ? "rated-down" : ""}" title="Rate down">👎 skip</button>
      <button class="icon-btn copy-btn" title="Copy post text">📋 copy</button>
      <input type="datetime-local" class="schedule-input" title="Schedule this post">
      <button class="icon-btn schedule-btn" title="Save schedule time">🗓 schedule</button>
      <button class="icon-btn delete-btn" title="Delete post">🗑</button>
      ${scheduled}
    </div>
  `;
}

function escapeHTML(str) {
  return (str || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function attachCardHandlers(cardEl, post) {
  const actions = cardEl.querySelector(".card-actions");
  const id = post.id;

  actions.querySelector(".up").addEventListener("click", () => rate(id, "up", cardEl));
  actions.querySelector(".down").addEventListener("click", () => rate(id, "down", cardEl));
  actions.querySelector(".delete-btn").addEventListener("click", () => removePost(id, cardEl));
  actions.querySelector(".copy-btn").addEventListener("click", () => {
    const text = `${post.content}\n\n${(post.hashtags || "").split(",").map(h => "#" + h.trim()).join(" ")}`;
    navigator.clipboard.writeText(text).then(() => toast("Copied to clipboard"));
  });
  actions.querySelector(".schedule-btn").addEventListener("click", async () => {
    const input = actions.querySelector(".schedule-input");
    if (!input.value) { toast("Pick a date/time first"); return; }
    const res = await fetch(`${API}/posts/${id}/schedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scheduled_at: new Date(input.value).toISOString() }),
    });
    if (res.ok) {
      const updated = await res.json();
      cardEl.innerHTML = postCardHTML(updated);
      attachCardHandlers(cardEl, updated);
      toast("Scheduled 🗓");
    }
  });
}

async function rate(id, rating, cardEl) {
  const res = await fetch(`${API}/posts/${id}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating }),
  });
  if (res.ok) {
    const updated = await res.json();
    cardEl.innerHTML = postCardHTML(updated);
    attachCardHandlers(cardEl, updated);
    toast(rating === "up" ? "Marked as a keeper 👍" : "Noted, we'll steer away from this style");
  }
}

async function removePost(id, cardEl) {
  const res = await fetch(`${API}/posts/${id}`, { method: "DELETE" });
  if (res.ok) {
    cardEl.remove();
    toast("Post removed");
  }
}

// ---------- History ----------
async function loadHistory() {
  const platform = document.getElementById("filter-platform").value;
  const tone = document.getElementById("filter-tone").value;
  const params = new URLSearchParams();
  if (platform) params.set("platform", platform);
  if (tone) params.set("tone", tone);

  const res = await fetch(`${API}/posts?${params.toString()}`);
  const posts = await res.json();
  const list = document.getElementById("history-list");
  const empty = document.getElementById("history-empty");
  list.innerHTML = "";

  if (!posts.length) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  posts.forEach(post => {
    const div = document.createElement("div");
    div.className = "post-card";
    div.innerHTML = postCardHTML(post);
    list.appendChild(div);
    attachCardHandlers(div, post);
  });
}

document.getElementById("filter-platform").addEventListener("change", loadHistory);
document.getElementById("filter-tone").addEventListener("change", loadHistory);
document.getElementById("refresh-history").addEventListener("click", loadHistory);

// ---------- Analytics: growth rings ----------
async function loadAnalytics() {
  const res = await fetch(`${API}/analytics`);
  const data = await res.json();

  document.getElementById("stat-total").textContent = data.total_posts;
  document.getElementById("stat-up").textContent = data.upvotes;
  document.getElementById("stat-down").textContent = data.downvotes;

  drawRings(data.by_platform);
  drawToneBars(data.by_tone, data.total_posts);
}

function drawRings(byPlatform) {
  const svg = document.getElementById("rings-svg");
  const legend = document.getElementById("rings-legend");
  svg.innerHTML = "";
  legend.innerHTML = "";

  const entries = Object.entries(byPlatform);
  const center = 110;
  const baseRadius = 30;
  const ringGap = 20;

  if (!entries.length) {
    svg.innerHTML = `<circle cx="${center}" cy="${center}" r="${baseRadius}" fill="none" stroke="#33402E" stroke-width="2" stroke-dasharray="4 4"/>`;
    legend.innerHTML = `<li>No data yet — generate a few posts.</li>`;
    return;
  }

  const max = Math.max(...entries.map(([, v]) => v));

  entries.forEach(([platform, count], i) => {
    const radius = baseRadius + i * ringGap;
    const circumference = 2 * Math.PI * radius;
    const fraction = max ? count / max : 0;
    const dash = circumference * fraction;
    const color = PLATFORM_HEX[platform] || "#8FA876";

    const track = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    track.setAttribute("cx", center); track.setAttribute("cy", center); track.setAttribute("r", radius);
    track.setAttribute("fill", "none"); track.setAttribute("stroke", "#2A3427"); track.setAttribute("stroke-width", "8");
    svg.appendChild(track);

    const ring = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    ring.setAttribute("cx", center); ring.setAttribute("cy", center); ring.setAttribute("r", radius);
    ring.setAttribute("fill", "none");
    ring.setAttribute("stroke", color);
    ring.setAttribute("stroke-width", "8");
    ring.setAttribute("stroke-linecap", "round");
    ring.setAttribute("stroke-dasharray", `${dash} ${circumference}`);
    ring.setAttribute("transform", `rotate(-90 ${center} ${center})`);
    svg.appendChild(ring);

    const li = document.createElement("li");
    li.innerHTML = `<span class="swatch" style="background:${color}"></span> ${platform} — ${count}`;
    legend.appendChild(li);
  });
}

function drawToneBars(byTone, total) {
  const container = document.getElementById("tone-bars");
  container.innerHTML = "";
  const entries = Object.entries(byTone);
  if (!entries.length) return;
  entries.forEach(([tone, count]) => {
    const pct = total ? Math.round((count / total) * 100) : 0;
    const row = document.createElement("div");
    row.className = "tone-bar-row";
    row.innerHTML = `
      <span class="tone-bar-label">${tone}</span>
      <span class="tone-bar-track"><span class="tone-bar-fill" style="width:${pct}%"></span></span>
      <span class="tone-bar-count">${count}</span>
    `;
    container.appendChild(row);
  });
}
