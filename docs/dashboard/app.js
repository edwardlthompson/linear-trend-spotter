/**
 * Qualified-coin dashboard (Milestones Q4, Q7–Q10): snapshot JSON only; optional tier-A alerts.
 * Snapshot URL: ?api=<encoded-url> or window.__SNAPSHOT_URL__ from config.js.
 */
(function () {
  const POLL_INTERVAL_MS = 15 * 60 * 1000;
  const LS_DIGEST = "qualified_dash_last_snap_digest";
  const LS_PREV_SYMBOLS = "qualified_dash_prev_symbols_json";
  const LS_PREV_SCHEMA = "qualified_dash_prev_schema_version";

  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("api");
  const snapshotUrl = fromQuery || window.__SNAPSHOT_URL__ || "";

  const elError = document.getElementById("error");
  const elMeta = document.getElementById("meta");
  const elTbody = document.getElementById("tbody");
  const elDiffBanner = document.getElementById("diffBanner");
  const elInput = document.getElementById("apiInput");
  const elLoad = document.getElementById("loadBtn");
  const elNotify = document.getElementById("notifyBtn");

  let pollTimer = null;
  let notifyAlertsEnabled = false;

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

  function render(data) {
    clearError();
    const coins = Array.isArray(data.coins) ? data.coins : [];
    const updated = data.updated_at || "—";
    const fieldSet = data.field_set || "full";
    elMeta.textContent = `Updated ${updated} · field_set=${fieldSet} · ${coins.length} coin(s)`;

    const prevSyms = readPrevSymbolSet();
    const prevSchema = localStorage.getItem(LS_PREV_SCHEMA) ?? "";
    const currSet = new Set(
      coins.map((c) => String(c.symbol || "").toUpperCase()).filter(Boolean),
    );
    const added =
      prevSyms.size === 0 ? [] : [...currSet].filter((s) => !prevSyms.has(s)).sort();
    const dropped =
      prevSyms.size === 0 ? [] : [...prevSyms].filter((s) => !currSet.has(s)).sort();
    const addedSet = new Set(added);

    updateDiffBanner(data, added, dropped, prevSchema);

    if (!coins.length) {
      elTbody.innerHTML =
        '<tr><td colspan="6" class="empty">No qualified coins in this snapshot.</td></tr>';
      writeSnapshotVisitState(data);
      return;
    }

    const rows = coins
      .map((c) => {
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
        const badge = addedSet.has(rawSym)
          ? '<span class="badge badge-new" title="New since last visit">New</span>'
          : "";
        return `<tr>
          <td><strong>${sym}</strong>${badge}</td>
          <td>${name}</td>
          <td class="num">${g30}%</td>
          <td class="num">${u}</td>
          <td class="num">${h}</td>
          <td>${link}</td>
        </tr>`;
      })
      .join("");
    elTbody.innerHTML = rows;
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
