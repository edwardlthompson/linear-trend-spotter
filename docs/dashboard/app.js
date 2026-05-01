/**
 * Qualified-coin dashboard (Milestones Q4, Q7–Q14): snapshot JSON; sort/filter/search; expandable rows;
 * stale snapshot banner; optional alerts. Snapshot URL: ?api=… or window.__SNAPSHOT_URL__ from config.js.
 */
(function () {
  const POLL_INTERVAL_MS = 15 * 60 * 1000;
  const LS_DIGEST = "qualified_dash_last_snap_digest";
  const LS_PREV_SYMBOLS = "qualified_dash_prev_symbols_json";
  const LS_PREV_SCHEMA = "qualified_dash_prev_schema_version";
  const SEARCH_DEBOUNCE_MS = 250;
  /** Fallback when snapshot omits scan_interval_seconds (older files). */
  const NOMINAL_SCAN_FALLBACK_SEC = 3600;

  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("api");
  const snapshotUrl = fromQuery || window.__SNAPSHOT_URL__ || "";

  const elError = document.getElementById("error");
  const elMeta = document.getElementById("meta");
  const elTbody = document.getElementById("tbody");
  const elDiffBanner = document.getElementById("diffBanner");
  const elStaleBanner = document.getElementById("staleBanner");
  const elInput = document.getElementById("apiInput");
  const elLoad = document.getElementById("loadBtn");
  const elNotify = document.getElementById("notifyBtn");
  const elSearch = document.getElementById("searchInput");

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

  if (elInput) {
    elInput.value = snapshotUrl;
  }

  function getSnapshotUrl() {
    return (elInput && elInput.value.trim()) || snapshotUrl || "";
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
      if (th.getAttribute("data-sort-key") === sortKey) {
        th.classList.add(sortDir > 0 ? "sort-asc" : "sort-desc");
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
    return rows;
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

  function detailBlockHtml(c) {
    const parts = [];
    const u = c.uniformity_score;
    const h = c.health_score;
    parts.push(
      `<div class="detail-grid"><div><strong>Uniformity</strong> ${escapeHtml(u != null ? String(u) : "—")}</div>` +
        `<div><strong>Health</strong> ${escapeHtml(h != null && h !== "" ? String(h) : "—")}</div></div>`,
    );
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

  function renderRowsHtml(coins) {
    if (!coins.length) {
      return '<tr><td colspan="6" class="empty">No qualified coins in this snapshot.</td></tr>';
    }
    return coins
      .map((c, idx) => {
        const rawSym = String(c.symbol || "").toUpperCase();
        const sym = escapeHtml(String(c.symbol || ""));
        const name = escapeHtml(String(c.name || ""));
        const g = c.gains || {};
        const g30 = typeof g["30d"] === "number" ? g["30d"].toFixed(1) : "—";
        const u = typeof c.uniformity_score === "number" ? c.uniformity_score.toFixed(1) : "—";
        const h =
          c.health_score != null && c.health_score !== ""
            ? Number(c.health_score).toFixed(1)
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
        return `<tr class="coin-row" role="button" tabindex="0" aria-expanded="false" aria-controls="${detailId}" data-symbol="${escapeAttr(rawSym)}">
          <td><strong>${sym}</strong>${badge}</td>
          <td>${name}</td>
          <td class="num">${g30}%</td>
          <td class="num">${u}</td>
          <td class="num">${h}</td>
          <td>${link}</td>
        </tr><tr class="coin-detail" id="${detailId}" hidden><td colspan="6" class="detail-cell">${detail}</td></tr>`;
      })
      .join("");
  }

  function applyTableView() {
    if (!lastPayload) return;
    const coins = Array.isArray(lastPayload.coins) ? lastPayload.coins : [];
    const filtered = applyFilters(coins);
    sortCoinsInPlace(filtered);
    elTbody.innerHTML = renderRowsHtml(filtered);
    updateSortHeaderClasses();
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

    applyTableView();
    writeSnapshotVisitState(data);
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

  if (elTbody) {
    elTbody.addEventListener("click", (ev) => {
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
  }

  async function digestHex(text) {
    if (window.crypto && crypto.subtle) {
      const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
      return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
    }
    return String(text.length) + ":" + text.slice(0, 2000);
  }

  async function notifySnapshotChanged(text, data) {
    const next = await digestHex(text);
    const prev = localStorage.getItem(LS_DIGEST);
    if (prev === null || prev === "") {
      localStorage.setItem(LS_DIGEST, next);
      return;
    }
    if (prev === next) {
      return;
    }
    localStorage.setItem(LS_DIGEST, next);
    const n = Array.isArray(data.coins) ? data.coins.length : 0;
    const body = `Snapshot changed · ${n} qualified coin(s)`;
    try {
      const reg = await navigator.serviceWorker.ready;
      if (reg && typeof reg.showNotification === "function") {
        await reg.showNotification("Qualified list updated", {
          body,
          tag: "qualified-snapshot",
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
        await notifySnapshotChanged(text, data);
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

  if (elLoad) {
    elLoad.addEventListener("click", () => loadSnapshot({ showErrors: true, forNotify: false }));
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
      clearError();
      await loadSnapshot({ showErrors: true, forNotify: false });
      startPoll();
      elMeta.textContent =
        (elMeta.textContent || "") + " · Update alerts on (poll every 15 min)";
    });
  }

  window.addEventListener("load", () => {
    registerServiceWorker();
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
