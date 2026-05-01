/**
 * Qualified-coin dashboard (Milestones Q4, Q7–Q19): snapshot JSON; sort/filter/search;
 * expandable rows; stale banner; theme (Q15); export (Q16); deep links (Q17); a11y (Q18);
 * optional chart thumb (Q19); scan health strip (Q20); tier-A alerts; tier-B Web Push (Q21). Snapshot: ?api=… or window.__SNAPSHOT_URL__.
 */
(function () {
  const POLL_INTERVAL_MS = 15 * 60 * 1000;
  const LS_DIGEST = "qualified_dash_last_snap_digest";
  const LS_PREV_SYMBOLS = "qualified_dash_prev_symbols_json";
  const LS_PREV_SCHEMA = "qualified_dash_prev_schema_version";
  const LS_THEME = "qualified_dash_theme";
  /** Tier-A poll: previous filtered symbol list under current UI filters (JSON array string). */
  const LS_POLL_FILTERED_SYMS = "qualified_dash_poll_filtered_syms";
  const SEARCH_DEBOUNCE_MS = 250;
  /** Fallback when snapshot omits scan_interval_seconds (older files). */
  const NOMINAL_SCAN_FALLBACK_SEC = 3600;

  function getSavedThemeMode() {
    const v = localStorage.getItem(LS_THEME);
    if (v === "light" || v === "dark" || v === "system") return v;
    return "system";
  }

  function effectiveTheme() {
    const m = getSavedThemeMode();
    if (m === "light" || m === "dark") return m;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function applyDomTheme() {
    const eff = effectiveTheme();
    document.documentElement.setAttribute("data-theme", eff);
    const meta = document.getElementById("themeColorMeta") || document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", eff === "dark" ? "#0f172a" : "#f8fafc");
  }

  function themeModeLabel() {
    return getSavedThemeMode();
  }

  function updateThemeButtonLabel() {
    const el = document.getElementById("themeCycleBtn");
    if (el) el.textContent = `Theme: ${themeModeLabel()}`;
  }

  function cycleThemeMode() {
    const order = ["system", "light", "dark"];
    const cur = getSavedThemeMode();
    const ix = Math.max(0, order.indexOf(cur));
    const next = order[(ix + 1) % order.length];
    localStorage.setItem(LS_THEME, next);
    applyDomTheme();
    updateThemeButtonLabel();
  }

  const mqlScheme = window.matchMedia("(prefers-color-scheme: dark)");
  if (typeof mqlScheme.addEventListener === "function") {
    mqlScheme.addEventListener("change", () => {
      if (getSavedThemeMode() === "system") applyDomTheme();
    });
  } else if (typeof mqlScheme.addListener === "function") {
    mqlScheme.addListener(() => {
      if (getSavedThemeMode() === "system") applyDomTheme();
    });
  }
  applyDomTheme();

  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("api");
  const snapshotUrl = fromQuery || window.__SNAPSHOT_URL__ || "";

  const elError = document.getElementById("error");
  const elMeta = document.getElementById("meta");
  const elTbody = document.getElementById("tbody");
  const elDiffBanner = document.getElementById("diffBanner");
  const elStaleBanner = document.getElementById("staleBanner");
  const elHealthStrip = document.getElementById("healthStrip");
  const elInput = document.getElementById("apiInput");
  const elLoad = document.getElementById("loadBtn");
  const elNotify = document.getElementById("notifyBtn");
  const elSearch = document.getElementById("searchInput");
  const elThemeCycle = document.getElementById("themeCycleBtn");
  const elExportCsv = document.getElementById("exportCsvBtn");
  const elExportJson = document.getElementById("exportJsonBtn");
  const elPushTierB = document.getElementById("pushTierBBtn");
  const elExchangeFilter = document.getElementById("exchangeFilter");
  const elBacktestModal = document.getElementById("backtestModal");
  const elBacktestModalTitle = document.getElementById("backtestModalTitle");
  const elBacktestModalBody = document.getElementById("backtestModalBody");
  const elBacktestModalClose = document.getElementById("backtestModalClose");

  let pollTimer = null;
  let notifyAlertsEnabled = false;
  let lastPayload = null;
  /** @type {Set<string>} */
  let lastAddedSet = new Set();
  let sortKey = "health";
  let sortDir = -1;
  /** @type {number | null} */
  let filterHealthMin = null;
  let searchQuery = "";
  let searchDebounceTimer = null;
  /** @type {string} exchange id or "" for all */
  let filterExchange = "";
  /** @type {number | null} */
  let hashHighlightTimer = null;

  updateThemeButtonLabel();

  if (elInput) {
    elInput.value = snapshotUrl;
  }

  function getSnapshotUrl() {
    return (elInput && elInput.value.trim()) || snapshotUrl || "";
  }

  function pushApiBase() {
    return String(window.__PUSH_API_BASE__ || "")
      .trim()
      .replace(/\/+$/, "");
  }

  function vapidPublicKey() {
    return String(window.__VAPID_PUBLIC_KEY__ || "").trim();
  }

  function pushSubscribeToken() {
    return String(window.__PUSH_SUBSCRIBE_TOKEN__ || "").trim();
  }

  function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  function pushTierBAvailable() {
    return (
      "serviceWorker" in navigator &&
      "PushManager" in window &&
      !!pushApiBase() &&
      !!vapidPublicKey()
    );
  }

  async function refreshPushTierBLabel() {
    if (!elPushTierB || !pushTierBAvailable()) return;
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      elPushTierB.textContent = sub ? "Disable remote scan push" : "Enable remote scan push";
    } catch (e) {
      console.warn("push tier-B state", e);
    }
  }

  function syncPushTierBVisibility() {
    if (!elPushTierB) return;
    if (!pushTierBAvailable()) {
      elPushTierB.hidden = true;
      return;
    }
    elPushTierB.hidden = false;
    void refreshPushTierBLabel();
  }

  async function tierBUnsubscribeRemote() {
    const base = pushApiBase();
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (!sub) return;
    const ep = sub.endpoint;
    await sub.unsubscribe();
    const headers = { "Content-Type": "application/json" };
    const t = pushSubscribeToken();
    if (t) headers.Authorization = `Bearer ${t}`;
    const body = { endpoint: ep };
    if (t) body.token = t;
    const res = await fetch(`${base}/v1/unsubscribe`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      credentials: "omit",
    });
    if (!res.ok) console.warn("push unsubscribe relay HTTP", res.status);
  }

  async function tierBSubscribeRemote() {
    const base = pushApiBase();
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(vapidPublicKey()),
    });
    const headers = { "Content-Type": "application/json" };
    const t = pushSubscribeToken();
    if (t) headers.Authorization = `Bearer ${t}`;
    const payload = { subscription: sub.toJSON() };
    if (t) payload.token = t;
    const res = await fetch(`${base}/v1/subscribe`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      credentials: "omit",
    });
    if (!res.ok) {
      await sub.unsubscribe().catch(() => {});
      throw new Error(`Push subscribe relay HTTP ${res.status}`);
    }
  }

  function showError(msg) {
    elError.textContent = msg;
    elError.hidden = false;
    elTbody.innerHTML = "";
    if (elDiffBanner) {
      elDiffBanner.hidden = true;
      elDiffBanner.textContent = "";
    }
    if (elStaleBanner) {
      elStaleBanner.hidden = true;
      elStaleBanner.textContent = "";
    }
    if (elHealthStrip) {
      elHealthStrip.hidden = true;
      elHealthStrip.textContent = "";
    }
  }

  function clearError() {
    elError.textContent = "";
    elError.hidden = true;
  }

  function readPrevSymbolSet() {
    try {
      const raw = localStorage.getItem(LS_PREV_SYMBOLS);
      if (!raw) return new Set();
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return new Set();
      return new Set(arr.map((s) => String(s).toUpperCase()).filter(Boolean));
    } catch {
      return new Set();
    }
  }

  function writeSnapshotVisitState(data) {
    const coins = Array.isArray(data.coins) ? data.coins : [];
    const sorted = [
      ...new Set(coins.map((c) => String(c.symbol || "").toUpperCase()).filter(Boolean)),
    ].sort();
    localStorage.setItem(LS_PREV_SYMBOLS, JSON.stringify(sorted));
    localStorage.setItem(LS_PREV_SCHEMA, String(data.schema_version ?? ""));
  }

  function updateDiffBanner(data, added, dropped, prevSchema) {
    if (!elDiffBanner) return;
    const curSchema = String(data.schema_version ?? "");
    const schemaChanged = prevSchema !== "" && prevSchema !== curSchema;
    const parts = [];
    if (added.length) {
      parts.push(
        `${added.length} new: ${added.slice(0, 14).join(", ")}${added.length > 14 ? "…" : ""}`,
      );
    }
    if (dropped.length) {
      parts.push(
        `${dropped.length} dropped: ${dropped.slice(0, 14).join(", ")}${dropped.length > 14 ? "…" : ""}`,
      );
    }
    if (schemaChanged) {
      parts.push(`schema_version ${prevSchema} → ${curSchema}`);
    }
    if (!parts.length) {
      elDiffBanner.hidden = true;
      elDiffBanner.textContent = "";
      return;
    }
    elDiffBanner.hidden = false;
    elDiffBanner.textContent = parts.join(" · ");
  }

  function coinG30(c) {
    const g = c.gains || {};
    return typeof g["30d"] === "number" ? g["30d"] : null;
  }

  function coinHealth(c) {
    if (c.health_score == null || c.health_score === "") return null;
    const n = Number(c.health_score);
    return Number.isFinite(n) ? n : null;
  }

  function coinG7(c) {
    const g = c.gains || {};
    return typeof g["7d"] === "number" ? g["7d"] : null;
  }

  function coinVolAccelPct(c) {
    const v = c.volume_acceleration_pct;
    if (v == null || v === "") return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function formatUsdVolDisplay(val) {
    if (val == null || val === "" || val === "N/A") return "—";
    if (typeof val === "number" && Number.isFinite(val)) {
      const x = Math.abs(val);
      if (x >= 1e9) return `$${(val / 1e9).toFixed(2)}B`;
      if (x >= 1e6) return `$${(val / 1e6).toFixed(2)}M`;
      if (x >= 1e3) return `$${(val / 1e3).toFixed(1)}k`;
      return `$${val.toFixed(0)}`;
    }
    return String(val);
  }

  function exchangeVolumeCellHtml(c) {
    const listed = Array.isArray(c.listed_on) ? c.listed_on : [];
    const ev = c.exchange_volumes && typeof c.exchange_volumes === "object" ? c.exchange_volumes : {};
    const keys = listed.length ? listed : Object.keys(ev);
    if (!keys.length) {
      return '<span class="cell-muted">—</span>';
    }
    const lines = [];
    for (const ex of keys.slice(0, 7)) {
      const raw = ev[ex];
      lines.push(
        `<span class="exch-line"><strong>${escapeHtml(String(ex))}</strong> ${escapeHtml(formatUsdVolDisplay(raw))}</span>`,
      );
    }
    if (keys.length > 7) {
      lines.push(`<span class="cell-muted">+${keys.length - 7} more</span>`);
    }
    return `<div class="exch-cell">${lines.join("")}</div>`;
  }

  function populateExchangeFilterOptions(coins) {
    if (!elExchangeFilter) return;
    const union = new Set();
    for (const c of coins) {
      const lo = c.listed_on;
      if (!Array.isArray(lo)) continue;
      for (const x of lo) {
        const id = String(x || "").trim().toLowerCase();
        if (id) union.add(id);
      }
    }
    const sorted = [...union].sort();
    const cur = filterExchange;
    elExchangeFilter.innerHTML = '<option value="">All exchanges</option>';
    for (const id of sorted) {
      const opt = document.createElement("option");
      opt.value = id;
      opt.textContent = id;
      elExchangeFilter.appendChild(opt);
    }
    if (cur && sorted.includes(cur)) {
      elExchangeFilter.value = cur;
    } else if (cur && !sorted.includes(cur)) {
      filterExchange = "";
      elExchangeFilter.value = "";
    }
  }

  function sortCoinsInPlace(rows) {
    const dir = sortDir;
    const mult = dir;
    rows.sort((a, b) => {
      let va;
      let vb;
      switch (sortKey) {
        case "symbol":
          va = String(a.symbol || "").toUpperCase();
          vb = String(b.symbol || "").toUpperCase();
          return mult * va.localeCompare(vb);
        case "name":
          va = String(a.name || "").toLowerCase();
          vb = String(b.name || "").toLowerCase();
          return mult * va.localeCompare(vb);
        case "g30": {
          const na = coinG30(a);
          const nb = coinG30(b);
          const fa = na != null ? na : -1e9;
          const fb = nb != null ? nb : -1e9;
          return mult * (fa - fb);
        }
        case "g7": {
          const na = coinG7(a);
          const nb = coinG7(b);
          const fa = na != null ? na : -1e9;
          const fb = nb != null ? nb : -1e9;
          return mult * (fa - fb);
        }
        case "volaccel": {
          const na = coinVolAccelPct(a);
          const nb = coinVolAccelPct(b);
          const fa = na != null ? na : -1e9;
          const fb = nb != null ? nb : -1e9;
          return mult * (fa - fb);
        }
        case "uniformity": {
          const ua = typeof a.uniformity_score === "number" ? a.uniformity_score : -1e9;
          const ub = typeof b.uniformity_score === "number" ? b.uniformity_score : -1e9;
          return mult * (ua - ub);
        }
        case "health":
        default: {
          const ha = coinHealth(a);
          const hb = coinHealth(b);
          const fa = ha != null ? ha : -1e9;
          const fb = hb != null ? hb : -1e9;
          return mult * (fa - fb);
        }
      }
    });
  }

  function updateSortHeaderClasses() {
    document.querySelectorAll("th[data-sort-key]").forEach((th) => {
      th.classList.remove("sort-asc", "sort-desc");
      th.setAttribute("aria-sort", "none");
      if (th.getAttribute("data-sort-key") === sortKey) {
        th.classList.add(sortDir > 0 ? "sort-asc" : "sort-desc");
        th.setAttribute("aria-sort", sortDir > 0 ? "ascending" : "descending");
      }
    });
  }

  function applyFilters(coins) {
    let rows = coins.slice();
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      rows = rows.filter((c) => {
        const sym = String(c.symbol || "").toLowerCase();
        const nm = String(c.name || "").toLowerCase();
        return sym.includes(q) || nm.includes(q);
      });
    }
    if (filterHealthMin != null) {
      rows = rows.filter((c) => {
        const h = coinHealth(c);
        return h != null && h >= filterHealthMin;
      });
    }
    if (filterExchange) {
      const fx = filterExchange.toLowerCase();
      rows = rows.filter((c) => {
        const lo = c.listed_on;
        if (!Array.isArray(lo)) return false;
        return lo.some((x) => String(x || "").trim().toLowerCase() === fx);
      });
    }
    return rows;
  }

  function getFilteredSortedCoins() {
    if (!lastPayload) return [];
    const coins = Array.isArray(lastPayload.coins) ? lastPayload.coins : [];
    const filtered = applyFilters(coins);
    const copy = filtered.slice();
    sortCoinsInPlace(copy);
    return copy;
  }

  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function getSymbolFromUrl() {
    const h = window.location.hash.replace(/^#/, "");
    if (h.startsWith("symbol=")) {
      const v = h.slice("symbol=".length).trim();
      return v ? v.toUpperCase() : "";
    }
    const q = new URLSearchParams(window.location.search).get("symbol");
    return q ? String(q).trim().toUpperCase() : "";
  }

  function applyHashHighlight() {
    window.clearTimeout(hashHighlightTimer);
    document.querySelectorAll("tr.coin-row.row-highlight").forEach((r) => r.classList.remove("row-highlight"));
    if (!elTbody) return;
    const want = getSymbolFromUrl();
    if (!want) return;
    let row = null;
    elTbody.querySelectorAll("tr.coin-row").forEach((r) => {
      if ((r.getAttribute("data-symbol") || "").toUpperCase() === want) row = r;
    });
    if (!row) return;
    row.classList.add("row-highlight");
    row.scrollIntoView({ block: "nearest", behavior: prefersReducedMotion() ? "auto" : "smooth" });
    hashHighlightTimer = window.setTimeout(() => {
      row.classList.remove("row-highlight");
    }, 4000);
  }

  function formatUpdatedHuman(iso) {
    const t = Date.parse(iso);
    if (!Number.isFinite(t)) return String(iso || "—");
    const d = Math.max(0, Date.now() - t);
    const mins = Math.round(d / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins} min ago`;
    const hrs = Math.round(mins / 60);
    if (hrs < 48) return `${hrs} h ago`;
    return new Date(t).toUTCString().slice(5, 22);
  }

  /** Relative label for a future ISO timestamp (next nominal scan). */
  function formatNextScanLabel(iso) {
    const t = Date.parse(iso);
    if (!Number.isFinite(t)) return iso || "";
    const untilMs = t - Date.now();
    if (untilMs <= 0) return "past due";
    const mins = Math.round(untilMs / 60000);
    if (mins < 1) return "in under 1 min";
    if (mins < 60) return `in ~${mins} min`;
    const hrs = Math.round(mins / 60);
    if (hrs < 72) return `in ~${hrs} h`;
    return iso.slice(0, 19) + "Z";
  }

  function updateStaleBanner(data) {
    if (!elStaleBanner) return;
    const iso = data.updated_at;
    const intervalRaw =
      typeof data.scan_interval_seconds === "number" && Number.isFinite(data.scan_interval_seconds)
        ? data.scan_interval_seconds
        : NOMINAL_SCAN_FALLBACK_SEC;
    const intervalSec = Math.max(60, intervalRaw);
    if (!iso) {
      elStaleBanner.hidden = true;
      elStaleBanner.textContent = "";
      return;
    }
    const snapTs = Date.parse(iso);
    if (!Number.isFinite(snapTs)) {
      elStaleBanner.hidden = true;
      elStaleBanner.textContent = "";
      return;
    }
    const ageSec = Math.max(0, (Date.now() - snapTs) / 1000);
    const stale = ageSec > 2 * intervalSec;
    elStaleBanner.hidden = !stale;
    if (!stale) {
      elStaleBanner.textContent = "";
      return;
    }
    const ageMin = Math.round(ageSec / 60);
    const nomMin = Math.round(intervalSec / 60);
    elStaleBanner.textContent = `Snapshot looks stale (${ageMin} min old). Expected refresh about every ${nomMin} min — check the worker or snapshot URL.`;
  }

  function updateHealthStrip(data) {
    if (!elHealthStrip) return;
    const dur = data.scan_duration_s;
    const ev = data.coins_evaluated;
    const err = data.errors_count;
    const hasDur = typeof dur === "number" && Number.isFinite(dur);
    const hasEv = typeof ev === "number" && Number.isFinite(ev);
    const hasErr = typeof err === "number" && Number.isFinite(err);
    if (!hasDur && !hasEv && !hasErr) {
      elHealthStrip.hidden = true;
      elHealthStrip.textContent = "";
      return;
    }
    const parts = [];
    if (hasDur) parts.push(`Last scan wall time: ${dur.toFixed(1)}s`);
    if (hasEv) parts.push(`Symbols evaluated: ${Math.round(ev)}`);
    if (hasErr) parts.push(`Metric errors: ${Math.round(err)}`);
    elHealthStrip.textContent = parts.join(" · ");
    elHealthStrip.hidden = false;
  }

  function escapeHtml(s) {
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  function detailBlockHtml(c) {
    const parts = [];
    const u = c.uniformity_score;
    const h = c.health_score;
    parts.push(
      `<div class="detail-grid"><div><strong>Uniformity</strong> ${escapeHtml(u != null ? String(u) : "—")}</div>` +
        `<div><strong>Health</strong> ${escapeHtml(h != null && h !== "" ? String(h) : "—")}</div></div>`,
    );
    const chartRaw = c.chart_image_url;
    if (typeof chartRaw === "string" && /^https:\/\//i.test(chartRaw.trim())) {
      const chartUrl = chartRaw.trim();
      const symLabel = escapeAttr(String(c.symbol || "coin"));
      parts.push('<div class="detail-heading">Chart</div>');
      parts.push(
        `<p class="detail-chart"><img class="chart-thumb" src="${escapeAttr(chartUrl)}" alt="${symLabel} chart thumbnail" loading="lazy" width="320" height="180" /></p>`,
      );
    }
    const bt = c.backtest_top_strategies;
    if (Array.isArray(bt) && bt.length) {
      parts.push('<div class="detail-heading">Backtest top strategies</div>');
      parts.push(`<pre class="detail-pre">${escapeHtml(JSON.stringify(bt, null, 2))}</pre>`);
    } else {
      parts.push(
        '<p class="detail-muted">No backtest strategy rows in this snapshot (field_set <code>full</code> after a scan includes them when available).</p>',
      );
    }
    const bh = c.backtest_buy_hold;
    if (bh != null && (typeof bh === "object" || typeof bh === "number")) {
      parts.push('<div class="detail-heading">Buy &amp; hold</div>');
      parts.push(`<pre class="detail-pre">${escapeHtml(JSON.stringify(bh, null, 2))}</pre>`);
    }
    return parts.join("");
  }

  function toggleRowDetail(row) {
    const id = row.getAttribute("aria-controls");
    const det = id ? document.getElementById(id) : null;
    if (!det) return;
    const open = row.getAttribute("aria-expanded") === "true";
    row.setAttribute("aria-expanded", open ? "false" : "true");
    det.hidden = open;
  }

  const COL_COUNT = 9;

  function renderRowsHtml(coins) {
    if (!coins.length) {
      return `<tr><td colspan="${COL_COUNT}" class="empty">No qualified coins match the current filters.</td></tr>`;
    }
    return coins
      .map((c, idx) => {
        const rawSym = String(c.symbol || "").toUpperCase();
        const sym = escapeHtml(String(c.symbol || ""));
        const nameRaw = String(c.name || "");
        const name = escapeHtml(nameRaw);
        const g = c.gains || {};
        const g7 = typeof g["7d"] === "number" ? g["7d"].toFixed(1) : "—";
        const g30 = typeof g["30d"] === "number" ? g["30d"].toFixed(1) : "—";
        const u = typeof c.uniformity_score === "number" ? c.uniformity_score.toFixed(1) : "—";
        const h =
          c.health_score != null && c.health_score !== ""
            ? Number(c.health_score).toFixed(1)
            : "—";
        const vac = coinVolAccelPct(c);
        const vwd = c.volume_acceleration_window_days;
        const volStr =
          vac != null
            ? `${vac >= 0 ? "+" : ""}${vac.toFixed(0)}%${typeof vwd === "number" ? ` / ${vwd}d` : ""}`
            : "—";
        const url = c.source_url ? String(c.source_url) : "";
        const link = url
          ? `<a href="${escapeAttr(url)}" rel="noopener noreferrer" target="_blank">View</a>`
          : "—";
        const badge = lastAddedSet.has(rawSym)
          ? '<span class="badge badge-new" title="New since last visit">New</span>'
          : "";
        const detailId = `coin-detail-${idx}`;
        const detail = detailBlockHtml(c);
        const exchHtml = exchangeVolumeCellHtml(c);
        return `<tr class="coin-row" role="button" tabindex="0" aria-expanded="false" aria-controls="${detailId}" data-symbol="${escapeAttr(rawSym)}">
          <td headers="col-symbol"><strong>${sym}</strong>${badge}</td>
          <td headers="col-name"><button type="button" class="coin-name-btn" data-symbol="${escapeAttr(rawSym)}">${name}</button></td>
          <td headers="col-g7" class="num"><span class="visually-hidden">7-day gain </span>${g7}%</td>
          <td headers="col-g30" class="num"><span class="visually-hidden">30-day gain </span>${g30}%</td>
          <td headers="col-uniformity" class="num"><span class="visually-hidden">Uniformity </span>${u}</td>
          <td headers="col-health" class="num"><span class="visually-hidden">Health </span>${h}</td>
          <td headers="col-volaccel" class="num"><span class="visually-hidden">Volume acceleration </span>${volStr}</td>
          <td headers="col-exch" class="exch-col">${exchHtml}</td>
          <td headers="col-link">${link}</td>
        </tr><tr class="coin-detail" id="${detailId}" hidden><td colspan="${COL_COUNT}" class="detail-cell">${detail}</td></tr>`;
      })
      .join("");
  }

  function applyTableView() {
    if (!lastPayload) return;
    const filtered = getFilteredSortedCoins();
    elTbody.innerHTML = renderRowsHtml(filtered);
    updateSortHeaderClasses();
    applyHashHighlight();
  }

  function downloadBlob(filename, mime, body) {
    const blob = new Blob([body], { type: mime });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.rel = "noopener";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function escapeCsvCell(v) {
    const s = v == null ? "" : String(v);
    if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  }

  function exportViewCsv() {
    const rows = getFilteredSortedCoins();
    const header = [
      "symbol",
      "name",
      "gain_7d_pct",
      "gain_30d_pct",
      "uniformity",
      "health",
      "volume_acceleration_pct",
      "volume_acceleration_window_days",
      "listed_on",
      "source_url",
    ];
    const lines = [header.join(",")];
    for (const c of rows) {
      const g = c.gains || {};
      const g7 = typeof g["7d"] === "number" ? g["7d"] : "";
      const g30 = typeof g["30d"] === "number" ? g["30d"] : "";
      const u = typeof c.uniformity_score === "number" ? c.uniformity_score : "";
      const h = c.health_score != null && c.health_score !== "" ? c.health_score : "";
      const vac = c.volume_acceleration_pct;
      const vwd = c.volume_acceleration_window_days;
      const lo = Array.isArray(c.listed_on) ? c.listed_on.join("|") : "";
      const url = c.source_url ? String(c.source_url) : "";
      lines.push(
        [c.symbol, c.name, g7, g30, u, h, vac, vwd, lo, url].map(escapeCsvCell).join(","),
      );
    }
    const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    downloadBlob(`qualified_export_${stamp}.csv`, "text/csv;charset=utf-8", lines.join("\r\n"));
  }

  function exportViewJson() {
    const rows = getFilteredSortedCoins();
    const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    downloadBlob(
      `qualified_export_${stamp}.json`,
      "application/json;charset=utf-8",
      JSON.stringify({ exported_at: new Date().toISOString(), count: rows.length, coins: rows }, null, 2),
    );
  }

  function render(data) {
    clearError();
    lastPayload = data;
    const coins = Array.isArray(data.coins) ? data.coins : [];
    const updatedRaw = data.updated_at || "";
    const updatedDisplay = updatedRaw || "—";
    const updatedHuman = updatedRaw ? formatUpdatedHuman(updatedRaw) : "—";
    const fieldSet = data.field_set || "full";
    const intervalSec =
      typeof data.scan_interval_seconds === "number" && Number.isFinite(data.scan_interval_seconds)
        ? Math.max(60, data.scan_interval_seconds)
        : NOMINAL_SCAN_FALLBACK_SEC;
    let nextHint = "";
    if (updatedRaw) {
      const snapTs = Date.parse(updatedRaw);
      if (Number.isFinite(snapTs) && intervalSec > 0) {
        const nextIso = new Date(snapTs + intervalSec * 1000).toISOString();
        nextHint = ` · next scan ${formatNextScanLabel(nextIso)} (${nextIso.slice(0, 19)}Z)`;
      }
    }
    elMeta.textContent = `Updated ${updatedHuman} (${updatedDisplay}) · field_set=${fieldSet} · ${coins.length} coin(s)${nextHint}`;

    const prevSyms = readPrevSymbolSet();
    const prevSchema = localStorage.getItem(LS_PREV_SCHEMA) ?? "";
    const currSet = new Set(
      coins.map((c) => String(c.symbol || "").toUpperCase()).filter(Boolean),
    );
    const added =
      prevSyms.size === 0 ? [] : [...currSet].filter((s) => !prevSyms.has(s)).sort();
    const dropped =
      prevSyms.size === 0 ? [] : [...prevSyms].filter((s) => !currSet.has(s)).sort();
    lastAddedSet = new Set(added);

    updateDiffBanner(data, added, dropped, prevSchema);
    updateStaleBanner(data);
    updateHealthStrip(data);

    populateExchangeFilterOptions(coins);
    applyTableView();
    writeSnapshotVisitState(data);
  }

  if (elTbody) {
    elTbody.addEventListener("click", (ev) => {
      const nameBtn = ev.target.closest(".coin-name-btn");
      if (nameBtn) {
        ev.preventDefault();
        ev.stopPropagation();
        const sym = nameBtn.getAttribute("data-symbol") || "";
        const coins = getFilteredSortedCoins();
        const coin = coins.find((x) => String(x.symbol || "").toUpperCase() === sym.toUpperCase());
        if (coin && elBacktestModal && elBacktestModalTitle && elBacktestModalBody) {
          elBacktestModalTitle.textContent = `${String(coin.symbol || "")} · ${String(coin.name || "")}`;
          elBacktestModalBody.innerHTML = detailBlockHtml(coin);
          elBacktestModal.showModal();
        }
        return;
      }
      const row = ev.target.closest("tr.coin-row");
      if (!row || ev.target.closest("a")) return;
      toggleRowDetail(row);
    });
    elTbody.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter" && ev.key !== " ") return;
      const row = ev.target.closest("tr.coin-row");
      if (!row || row !== ev.target) return;
      ev.preventDefault();
      toggleRowDetail(row);
    });
    elTbody.addEventListener("focusin", (ev) => {
      const row = ev.target.closest("tr.coin-row");
      if (!row) return;
      const sym = row.getAttribute("data-symbol");
      if (!sym) return;
      const nextHash = `#symbol=${encodeURIComponent(sym)}`;
      const path = window.location.pathname + window.location.search;
      if (window.location.hash !== nextHash) {
        history.replaceState(null, "", path + nextHash);
      }
    });
  }

  window.addEventListener("hashchange", () => applyHashHighlight());

  async function digestHex(text) {
    if (window.crypto && crypto.subtle) {
      const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
      return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
    }
    return String(text.length) + ":" + text.slice(0, 2000);
  }

  /** Tier-A alerts: only when the **filtered** coin list (current UI filters) changes vs last poll. */
  async function notifySnapshotChangedFiltered(text, data) {
    const coins = Array.isArray(data.coins) ? data.coins : [];
    const filtered = applyFilters(coins);
    const syms = [
      ...new Set(filtered.map((c) => String(c.symbol || "").toUpperCase()).filter(Boolean)),
    ].sort();
    const key = JSON.stringify(syms);
    const nextDigest = await digestHex(text);
    const prevFilteredRaw = localStorage.getItem(LS_POLL_FILTERED_SYMS);
    localStorage.setItem(LS_DIGEST, nextDigest);
    if (prevFilteredRaw === null || prevFilteredRaw === "") {
      localStorage.setItem(LS_POLL_FILTERED_SYMS, key);
      return;
    }
    if (prevFilteredRaw === key) {
      return;
    }
    localStorage.setItem(LS_POLL_FILTERED_SYMS, key);
    let prevArr = [];
    try {
      prevArr = JSON.parse(prevFilteredRaw);
    } catch {
      prevArr = [];
    }
    const prevSet = new Set(Array.isArray(prevArr) ? prevArr.map((s) => String(s).toUpperCase()) : []);
    const curSet = new Set(syms);
    const added = syms.filter((s) => !prevSet.has(s));
    const removed = [...prevSet].filter((s) => !curSet.has(s)).sort();
    let body = `Filtered view: ${syms.length} coin(s)`;
    if (added.length) {
      body += ` · New: ${added.slice(0, 14).join(", ")}${added.length > 14 ? "…" : ""}`;
    }
    if (removed.length) {
      body += ` · Out: ${removed.slice(0, 10).join(", ")}${removed.length > 10 ? "…" : ""}`;
    }
    try {
      const reg = await navigator.serviceWorker.ready;
      if (reg && typeof reg.showNotification === "function") {
        await reg.showNotification("Qualified list updated", {
          body,
          tag: "qualified-snapshot-filtered",
          renotify: true,
        });
      } else if (typeof Notification === "function") {
        new Notification("Qualified list updated", { body });
      }
    } catch (e) {
      console.warn("showNotification failed", e);
    }
  }

  async function loadSnapshot(options) {
    const showErrors = options && options.showErrors;
    const forNotify = options && options.forNotify;
    const url = getSnapshotUrl();
    if (!url || !url.trim()) {
      if (showErrors) {
        showError("Set a snapshot JSON URL (?api=…) or define window.__SNAPSHOT_URL__ in config.js.");
      }
      return;
    }
    try {
      const res = await fetch(url.trim(), { credentials: "omit" });
      if (!res.ok) {
        if (showErrors) showError(`HTTP ${res.status} loading snapshot`);
        return;
      }
      const text = await res.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch (parseErr) {
        if (showErrors) showError("Invalid JSON in snapshot response");
        return;
      }
      render(data);
      if (forNotify && notifyAlertsEnabled) {
        await notifySnapshotChangedFiltered(text, data);
      } else {
        localStorage.setItem(LS_DIGEST, await digestHex(text));
      }
    } catch (e) {
      if (showErrors) showError(String(e && e.message ? e.message : e));
    }
  }

  async function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) return;
    try {
      await navigator.serviceWorker.register("./sw.js", { scope: "./" });
    } catch (e) {
      console.warn("Service worker registration failed", e);
    }
  }

  function stopPoll() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function startPoll() {
    stopPoll();
    pollTimer = window.setInterval(() => {
      loadSnapshot({ showErrors: false, forNotify: true });
    }, POLL_INTERVAL_MS);
  }

  document.querySelectorAll("thead .sort-btn").forEach((btn) => {
    const th = btn.closest("th");
    const key = btn.getAttribute("data-sort");
    if (th && key) th.setAttribute("data-sort-key", key);
    btn.addEventListener("click", () => {
      if (sortKey === key) {
        sortDir = -sortDir;
      } else {
        sortKey = key;
        sortDir = key === "symbol" || key === "name" ? 1 : -1;
      }
      applyTableView();
    });
  });

  document.querySelectorAll(".chip-filter[data-min]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const raw = btn.getAttribute("data-min");
      filterHealthMin = raw === "" || raw == null ? null : Number(raw);
      document.querySelectorAll(".chip-filter[data-min]").forEach((b) => b.classList.remove("is-active"));
      btn.classList.add("is-active");
      applyTableView();
    });
  });

  if (elSearch) {
    elSearch.addEventListener("input", () => {
      window.clearTimeout(searchDebounceTimer);
      searchDebounceTimer = window.setTimeout(() => {
        searchQuery = elSearch.value || "";
        applyTableView();
      }, SEARCH_DEBOUNCE_MS);
    });
  }

  if (elExchangeFilter) {
    elExchangeFilter.addEventListener("change", () => {
      filterExchange = String(elExchangeFilter.value || "").trim().toLowerCase();
      applyTableView();
    });
  }

  if (elBacktestModalClose && elBacktestModal) {
    elBacktestModalClose.addEventListener("click", () => elBacktestModal.close());
  }
  if (elBacktestModal) {
    elBacktestModal.addEventListener("click", (ev) => {
      if (ev.target === elBacktestModal) elBacktestModal.close();
    });
  }

  if (elLoad) {
    elLoad.addEventListener("click", () => loadSnapshot({ showErrors: true, forNotify: false }));
  }

  if (elThemeCycle) {
    elThemeCycle.addEventListener("click", () => cycleThemeMode());
  }

  if (elExportCsv) {
    elExportCsv.addEventListener("click", () => {
      if (!lastPayload) return;
      exportViewCsv();
    });
  }

  if (elExportJson) {
    elExportJson.addEventListener("click", () => {
      if (!lastPayload) return;
      exportViewJson();
    });
  }

  if (elNotify) {
    elNotify.addEventListener("click", async () => {
      if (!("Notification" in window)) {
        showError("Browser notifications are not supported here.");
        return;
      }
      let perm = Notification.permission;
      if (perm === "default") {
        perm = await Notification.requestPermission();
      }
      if (perm !== "granted") {
        showError(
          "Notification permission not granted. On iOS, add the site to the Home Screen and try again from the installed PWA.",
        );
        return;
      }
      await registerServiceWorker();
      notifyAlertsEnabled = true;
      localStorage.removeItem(LS_POLL_FILTERED_SYMS);
      clearError();
      await loadSnapshot({ showErrors: true, forNotify: false });
      startPoll();
      elMeta.textContent =
        (elMeta.textContent || "") + " · Update alerts on (poll every 15 min)";
      syncPushTierBVisibility();
      void refreshPushTierBLabel();
    });
  }

  if (elPushTierB) {
    elPushTierB.addEventListener("click", async () => {
      if (!pushTierBAvailable()) return;
      if (!("Notification" in window)) {
        showError("Browser notifications are not supported here.");
        return;
      }
      let perm = Notification.permission;
      if (perm === "default") {
        perm = await Notification.requestPermission();
      }
      if (perm !== "granted") {
        showError(
          "Notification permission not granted. On iOS, add the site to the Home Screen and try again from the installed PWA.",
        );
        return;
      }
      await registerServiceWorker();
      clearError();
      try {
        const reg = await navigator.serviceWorker.ready;
        const existing = await reg.pushManager.getSubscription();
        if (existing) {
          await tierBUnsubscribeRemote();
        } else {
          await tierBSubscribeRemote();
        }
        await refreshPushTierBLabel();
      } catch (e) {
        showError(String(e && e.message ? e.message : e));
        await refreshPushTierBLabel();
      }
    });
  }

  window.addEventListener("load", () => {
    void (async () => {
      await registerServiceWorker();
      syncPushTierBVisibility();
      await refreshPushTierBLabel();
    })();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && notifyAlertsEnabled) {
      loadSnapshot({ showErrors: false, forNotify: true });
    }
  });

  if (snapshotUrl) {
    loadSnapshot({ showErrors: true, forNotify: false });
  } else {
    showError("Set a snapshot JSON URL (?api=…) or define window.__SNAPSHOT_URL__ in config.js.");
  }
})();
