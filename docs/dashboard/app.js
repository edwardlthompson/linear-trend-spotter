/**
 * Qualified-coin dashboard (Milestone Q4): fetches snapshot JSON only.
 * Snapshot URL: ?api=<encoded-url> or window.__SNAPSHOT_URL__ from config.js.
 */
(function () {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get("api");
  const snapshotUrl = fromQuery || window.__SNAPSHOT_URL__ || "";

  const elError = document.getElementById("error");
  const elMeta = document.getElementById("meta");
  const elTbody = document.getElementById("tbody");
  const elInput = document.getElementById("apiInput");
  const elLoad = document.getElementById("loadBtn");

  if (elInput) {
    elInput.value = snapshotUrl;
  }

  function showError(msg) {
    elError.textContent = msg;
    elError.hidden = false;
    elTbody.innerHTML = "";
  }

  function clearError() {
    elError.textContent = "";
    elError.hidden = true;
  }

  function render(data) {
    clearError();
    const coins = Array.isArray(data.coins) ? data.coins : [];
    const updated = data.updated_at || "—";
    const fieldSet = data.field_set || "full";
    elMeta.textContent = `Updated ${updated} · field_set=${fieldSet} · ${coins.length} coin(s)`;

    if (!coins.length) {
      elTbody.innerHTML =
        '<tr><td colspan="6" class="empty">No qualified coins in this snapshot.</td></tr>';
      return;
    }

    const rows = coins
      .map((c) => {
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
        return `<tr>
          <td><strong>${sym}</strong></td>
          <td>${name}</td>
          <td class="num">${g30}%</td>
          <td class="num">${u}</td>
          <td class="num">${h}</td>
          <td>${link}</td>
        </tr>`;
      })
      .join("");
    elTbody.innerHTML = rows;
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

  async function load(url) {
    if (!url || !url.trim()) {
      showError("Set a snapshot JSON URL (?api=…) or define window.__SNAPSHOT_URL__ in config.js.");
      return;
    }
    try {
      const res = await fetch(url.trim(), { credentials: "omit" });
      if (!res.ok) {
        showError(`HTTP ${res.status} loading snapshot`);
        return;
      }
      const data = await res.json();
      render(data);
    } catch (e) {
      showError(String(e && e.message ? e.message : e));
    }
  }

  if (elLoad) {
    elLoad.addEventListener("click", () => load(elInput ? elInput.value : snapshotUrl));
  }

  if (snapshotUrl) {
    load(snapshotUrl);
  } else {
    showError("Set a snapshot JSON URL (?api=…) or define window.__SNAPSHOT_URL__ in config.js.");
  }
})();
