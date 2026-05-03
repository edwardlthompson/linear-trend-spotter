/**
 * Qualified-coin dashboard (Milestones Q4, Q7–Q19): snapshot JSON; sort/filter/search;
 * stale banner; theme (Q15); export CSV/JSON (Q16); deep links (Q17); a11y (Q18);
 * optional chart thumb (Q19); scan health strip (Q20); tier-A alerts; tier-B Web Push (Q21); star = browser watchlist (Qualified vs Watchlist vs Alerts tabs; ops feed + coin bell drawer); UI sort/filters in localStorage. Snapshot URL under collapsible Data source; ?api=… or window.__SNAPSHOT_URL__.
 */
(function () {
  /** TradingView-style steps from 1h through 1D (Tier-A browser poll; not server scan rate). */
  const POLL_INTERVAL_OPTIONS = [
    { ms: 60 * 60 * 1000, label: "1h" },
    { ms: 2 * 60 * 60 * 1000, label: "2h" },
    { ms: 3 * 60 * 60 * 1000, label: "3h" },
    { ms: 4 * 60 * 60 * 1000, label: "4h" },
    { ms: 6 * 60 * 60 * 1000, label: "6h" },
    { ms: 8 * 60 * 60 * 1000, label: "8h" },
    { ms: 12 * 60 * 60 * 1000, label: "12h" },
    { ms: 24 * 60 * 60 * 1000, label: "1D" },
  ];
  /** Interpolated sparkline points when snapshot series is short (display-only). */
  const SPARKLINE_TARGET_POINTS = 120;
  const DEFAULT_POLL_MS = 60 * 60 * 1000;
  const LS_POLL_INTERVAL_MS = "qualified_dash_poll_interval_ms";
  const LS_DIGEST = "qualified_dash_last_snap_digest";
  const LS_PREV_SYMBOLS = "qualified_dash_prev_symbols_json";
  const LS_PREV_SCHEMA = "qualified_dash_prev_schema_version";
  const LS_THEME = "qualified_dash_theme";
  /** Tier-A poll: previous filtered symbol list under current UI filters (JSON array string). */
  const LS_POLL_FILTERED_SYMS = "qualified_dash_poll_filtered_syms";
  /** Table sort + filters: survive refresh and PWA relaunch (same origin). */
  const LS_UI_SORT_KEY = "qualified_dash_ui_sort_key";
  const LS_UI_SORT_DIR = "qualified_dash_ui_sort_dir";
  const LS_UI_HEALTH_MIN = "qualified_dash_ui_health_min";
  const LS_UI_UNIFORMITY_MIN = "qualified_dash_ui_uniformity_min";
  const LS_UI_SEARCH = "qualified_dash_ui_search";
  /** @deprecated use LS_UI_EXCHANGES_JSON */
  const LS_UI_EXCHANGE = "qualified_dash_ui_exchange";
  const LS_UI_EXCHANGES_JSON = "qualified_dash_ui_exchanges_json";
  /** Uppercase symbols — user watch list; transitions vs full snapshot qualified set (not table filters). */
  const LS_PINNED_SYMBOLS_JSON = "qualified_dash_pinned_symbols_json";
  /** Maps symbol → was qualified on last snapshot (boolean). */
  const LS_PINNED_WAS_QUALIFIED_JSON = "qualified_dash_pinned_was_qualified_json";
  /** ``qualified`` | ``watchlist`` — which main tab is active. */
  const LS_UI_ACTIVE_VIEW = "qualified_dash_active_view";
  /** Session: hide scan health / relay / regime strip cluster until tab closes. */
  const LS_SNAPSHOT_TELEMETRY_DISMISSED = "qualified_dash_snapshot_telemetry_dismissed";
  /** Milliseconds: operational feed items at or before this time count as read (Alerts tab badge). */
  const LS_OPS_LAST_ACK_MS = "qualified_dash_ops_last_ack_ms";
  /** Digest of coin-only banners last acknowledged with the bell drawer (localStorage). */
  const LS_COIN_ALERTS_ACK_DIGEST = "qualified_dash_coin_alerts_ack_digest";
  const SEARCH_DEBOUNCE_MS = 250;
  /** Fallback when snapshot omits scan_interval_seconds (older files). */
  const NOMINAL_SCAN_FALLBACK_SEC = 3600;
  /** Treat snapshot timestamps before this as invalid for age/stale (epoch placeholders, corrupt data). */
  const MIN_VALID_SNAPSHOT_MS = Date.UTC(2000, 0, 1, 0, 0, 0, 0);

  const ALLOWED_POLL_MS = new Set(POLL_INTERVAL_OPTIONS.map((o) => o.ms));
  const ALLOWED_SORT_KEYS = new Set(["symbol", "name", "g7", "g30", "uniformity", "health", "volaccel"]);
  /** Scanner default target exchanges — must match `listed_on` ids in snapshot JSON. */
  const TARGET_EXCHANGES_LIST = ["coinbase", "kraken", "mexc"];
  const EXCHANGE_LABELS = { coinbase: "Coinbase", kraken: "Kraken", mexc: "MEXC" };
  const TARGET_EXCHANGE_IDS = new Set(TARGET_EXCHANGES_LIST);

  /** @param {number} t ms since epoch from Date.parse */
  function isValidSnapshotTimeMs(t) {
    return Number.isFinite(t) && t >= MIN_VALID_SNAPSHOT_MS;
  }

  function parseStoredPollMs(raw) {
    const n = Number(raw);
    if (!Number.isFinite(n) || !ALLOWED_POLL_MS.has(n)) return DEFAULT_POLL_MS;
    return n;
  }

  function getPollIntervalMs() {
    try {
      return parseStoredPollMs(localStorage.getItem(LS_POLL_INTERVAL_MS));
    } catch {
      return DEFAULT_POLL_MS;
    }
  }

  /** @param {number} ms */
  function pollIntervalHumanPhrase(ms) {
    const opt = POLL_INTERVAL_OPTIONS.find((o) => o.ms === ms);
    if (opt) return `every ${opt.label}`;
    return `every ${Math.round(ms / 3600000)}h`;
  }

  function populatePollIntervalSelect() {
    if (!elPollInterval) return;
    elPollInterval.innerHTML = "";
    for (const o of POLL_INTERVAL_OPTIONS) {
      const opt = document.createElement("option");
      opt.value = String(o.ms);
      opt.textContent = o.label;
      opt.title = `Re-fetch snapshot ${pollIntervalHumanPhrase(o.ms)} while Tier-A alerts are on`;
      elPollInterval.appendChild(opt);
    }
    elPollInterval.value = String(getPollIntervalMs());
  }

  function persistPollIntervalFromUi() {
    if (!elPollInterval) return;
    const ms = parseStoredPollMs(elPollInterval.value);
    localStorage.setItem(LS_POLL_INTERVAL_MS, String(ms));
    elPollInterval.value = String(ms);
  }

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
  const elApiBudgetPanel = document.getElementById("apiBudgetPanel");
  const elExchangeFilterDetails = document.getElementById("exchangeFilterDetails");
  const elExchangeFilterApply = document.getElementById("exchangeFilterApply");
  const elExchangeFilterSelectAll = document.getElementById("exchangeFilterSelectAll");
  const elTbody = document.getElementById("tbody");
  const elDiffBanner = document.getElementById("diffBanner");
  const elWatchLeaveBanner = document.getElementById("watchLeaveBanner");
  const elWatchLeaveBannerText = document.getElementById("watchLeaveBannerText");
  const elWatchLeaveBannerDismiss = document.getElementById("watchLeaveBannerDismiss");
  const elMainHeading = document.getElementById("mainHeading");
  const elHealthMinSelect = document.getElementById("healthMinSelect");
  const elUniformityMinSelect = document.getElementById("uniformityMinSelect");
  const elWatchlistBadge = document.getElementById("watchlistBadge");
  const elEmptyBanner = document.getElementById("emptyBanner");
  const elStaleBanner = document.getElementById("staleBanner");
  const elHealthStrip = document.getElementById("healthStrip");
  const elRelayHealthStrip = document.getElementById("relayHealthStrip");
  const elRegimeStrip = document.getElementById("regimeStrip");
  const elSnapshotTelemetryPanel = document.getElementById("snapshotTelemetryPanel");
  const elTelemetryStripDismiss = document.getElementById("telemetryStripDismiss");
  const elOpsMarkReadBtn = document.getElementById("opsMarkReadBtn");
  const elCoinAlertsBell = document.getElementById("coinAlertsBell");
  const elCoinAlertsDrawer = document.getElementById("coinAlertsDrawer");
  const elCoinAlertsBadge = document.getElementById("coinAlertsBadge");
  const elCoinAlertsToolbarSlot = document.getElementById("coinAlertsToolbarSlot");
  const elOpsTabBadge = document.getElementById("opsTabBadge");
  const elInput = document.getElementById("apiInput");
  const elLoad = document.getElementById("loadBtn");
  const elNotify = document.getElementById("notifyBtn");
  const elPollInterval = document.getElementById("pollIntervalSelect");
  const elSearch = document.getElementById("searchInput");
  const elThemeCycle = document.getElementById("themeCycleBtn");
  const elExportBtn = document.getElementById("exportBtn");
  const elExportFormatSelect = document.getElementById("exportFormatSelect");
  const elPushTierB = document.getElementById("pushTierBBtn");
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
  /** @type {number | null} */
  let filterUniformityMin = null;
  let searchQuery = "";
  let searchDebounceTimer = null;
  /** When non-empty, coin must be listed on **at least one** selected exchange (`listed_on`). Empty = all. */
  /** @type {Set<string>} */
  let filterExchangeSet = new Set();
  /** @type {number | null} */
  let hashHighlightTimer = null;
  /** Pinned symbols that became qualified on this snapshot (row highlight until timeout). */
  let pinEnterFlashSet = new Set();
  /** @type {{ entered: string[], left: string[] }} */
  let lastPinWatchDelta = { entered: [], left: [] };
  let pinEnterClearTimer = 0;
  let prevPollWatchLeaveSig = "__init__";
  let suppressedWatchLeaveSig = "";
  /** @type {"qualified" | "watchlist" | "alerts"} */
  let activeView = "qualified";
  /** @type {{ t: number, iso: string, html: string }[]} */
  let opsFeedItems = [];
  const opsFeedDedupe = new Set();
  let opsSummaryDebounceTimer = 0;
  let lastStaleBannerShown = false;

  function getOpsLastAckMs() {
    try {
      const n = Number(localStorage.getItem(LS_OPS_LAST_ACK_MS));
      return Number.isFinite(n) && n > 0 ? n : 0;
    } catch {
      return 0;
    }
  }

  function setOpsLastAckToNow() {
    try {
      localStorage.setItem(LS_OPS_LAST_ACK_MS, String(Date.now()));
    } catch (e) {
      console.warn("ops ack", e);
    }
  }

  function ackOpsNotificationsFromUi() {
    setOpsLastAckToNow();
    syncOpsTabBadge();
  }

  function syncOpsTabBadge() {
    if (!elOpsTabBadge) return;
    const ack = getOpsLastAckMs();
    const unread = opsFeedItems.filter((i) => i.t > ack).length;
    elOpsTabBadge.hidden = unread === 0;
    elOpsTabBadge.textContent = unread > 99 ? "99+" : String(unread);
  }

  /** Reset Tier-A poll diff baseline so filter changes do not fire bogus in/out alerts. */
  function resetTierAPollBaselineIfAlerts() {
    if (!notifyAlertsEnabled) return;
    try {
      localStorage.removeItem(LS_POLL_FILTERED_SYMS);
    } catch (e) {
      console.warn("reset poll baseline", e);
    }
  }

  function persistUiPreferences() {
    try {
      localStorage.setItem(LS_UI_SORT_KEY, sortKey);
      localStorage.setItem(LS_UI_SORT_DIR, String(sortDir));
      if (filterHealthMin == null) localStorage.removeItem(LS_UI_HEALTH_MIN);
      else localStorage.setItem(LS_UI_HEALTH_MIN, String(filterHealthMin));
      if (filterUniformityMin == null) localStorage.removeItem(LS_UI_UNIFORMITY_MIN);
      else localStorage.setItem(LS_UI_UNIFORMITY_MIN, String(filterUniformityMin));
      localStorage.setItem(LS_UI_SEARCH, searchQuery);
      if (filterExchangeSet.size === 0) {
        localStorage.removeItem(LS_UI_EXCHANGES_JSON);
        localStorage.removeItem(LS_UI_EXCHANGE);
      } else {
        localStorage.setItem(LS_UI_EXCHANGES_JSON, JSON.stringify([...filterExchangeSet].sort()));
        localStorage.removeItem(LS_UI_EXCHANGE);
      }
      localStorage.setItem(LS_UI_ACTIVE_VIEW, activeView);
    } catch (e) {
      console.warn("persistUiPreferences", e);
    }
  }

  function restoreUiPreferences() {
    try {
      const sk = localStorage.getItem(LS_UI_SORT_KEY);
      if (sk && ALLOWED_SORT_KEYS.has(sk)) sortKey = sk;
      const sd = localStorage.getItem(LS_UI_SORT_DIR);
      if (sd === "1" || sd === "-1") sortDir = Number(sd);
      const hm = localStorage.getItem(LS_UI_HEALTH_MIN);
      if (hm === null || hm === "") filterHealthMin = null;
      else {
        const n = Number(hm);
        if (Number.isNaN(n)) filterHealthMin = null;
        else if (n === 60 || n === 70) filterHealthMin = n;
        else filterHealthMin = null;
      }
      const um = localStorage.getItem(LS_UI_UNIFORMITY_MIN);
      if (um === null || um === "") filterUniformityMin = null;
      else {
        const nu = Number(um);
        if (Number.isNaN(nu)) filterUniformityMin = null;
        else if (nu === 60 || nu === 65) filterUniformityMin = nu;
        else filterUniformityMin = null;
      }
      const sq = localStorage.getItem(LS_UI_SEARCH);
      if (sq != null) searchQuery = sq;
      filterExchangeSet = new Set();
      const exJson = localStorage.getItem(LS_UI_EXCHANGES_JSON);
      if (exJson) {
        try {
          const arr = JSON.parse(exJson);
          if (Array.isArray(arr)) {
            for (const x of arr) {
              const id = String(x || "").trim().toLowerCase();
              if (TARGET_EXCHANGE_IDS.has(id)) filterExchangeSet.add(id);
            }
          }
        } catch {
          /* ignore */
        }
      }
      if (filterExchangeSet.size === 0) {
        const exLegacy = localStorage.getItem(LS_UI_EXCHANGE);
        if (exLegacy && String(exLegacy).trim()) {
          const id = String(exLegacy).trim().toLowerCase();
          if (TARGET_EXCHANGE_IDS.has(id)) filterExchangeSet.add(id);
        }
      }
      const av = localStorage.getItem(LS_UI_ACTIVE_VIEW);
      if (av === "watchlist" || av === "qualified" || av === "alerts") activeView = av;
    } catch (e) {
      console.warn("restoreUiPreferences", e);
    }
  }

  function syncHealthMinSelect() {
    if (!elHealthMinSelect) return;
    const v = filterHealthMin == null ? "" : String(filterHealthMin);
    elHealthMinSelect.value = v === "60" || v === "70" ? v : "";
  }

  function syncUniformityMinSelect() {
    if (!elUniformityMinSelect) return;
    const v = filterUniformityMin == null ? "" : String(filterUniformityMin);
    elUniformityMinSelect.value = v === "60" || v === "65" ? v : "";
  }

  function updateWatchlistBadge() {
    if (!elWatchlistBadge) return;
    const n = getPinnedSet().size;
    elWatchlistBadge.textContent = n ? String(n) : "";
    elWatchlistBadge.hidden = n === 0;
  }

  function syncTabVisuals() {
    const onQ = activeView === "qualified";
    const onW = activeView === "watchlist";
    const onA = activeView === "alerts";
    const tq = document.getElementById("tabQualified");
    const tw = document.getElementById("tabWatchlist");
    const ta = document.getElementById("tabOps");
    const mainP = document.getElementById("mainDataPanel");
    const opsP = document.getElementById("opsPanel");
    if (tq && tw && ta) {
      tq.classList.toggle("is-active", onQ);
      tw.classList.toggle("is-active", onW);
      ta.classList.toggle("is-active", onA);
      tq.setAttribute("aria-selected", onQ ? "true" : "false");
      tw.setAttribute("aria-selected", onW ? "true" : "false");
      ta.setAttribute("aria-selected", onA ? "true" : "false");
    }
    if (mainP) {
      mainP.hidden = onA;
      mainP.setAttribute("aria-labelledby", onW ? "tabWatchlist" : "tabQualified");
    }
    if (opsP) opsP.hidden = !onA;
    if (elMainHeading) {
      elMainHeading.textContent = onA ? "Alerts" : onW ? "Watchlist" : "Qualified list";
    }
    if (elCoinAlertsToolbarSlot) elCoinAlertsToolbarSlot.hidden = onA;
    if (onA && elCoinAlertsDrawer) {
      elCoinAlertsDrawer.hidden = true;
      if (elCoinAlertsBell) elCoinAlertsBell.setAttribute("aria-expanded", "false");
    }
    updateWatchlistBadge();
    syncOpsTabBadge();
    syncCoinBellBadge();
  }

  function setActiveView(view) {
    if (view === "alerts") activeView = "alerts";
    else activeView = view === "watchlist" ? "watchlist" : "qualified";
    if (activeView === "alerts") ackOpsNotificationsFromUi();
    syncTabVisuals();
    persistUiPreferences();
    if (activeView !== "alerts") applyTableView();
  }

  function syncExchangeCheckboxesFromSet() {
    document.querySelectorAll("input[data-exchange-cb]").forEach((inp) => {
      const id = String(inp.value || "").trim().toLowerCase();
      inp.checked = filterExchangeSet.has(id);
    });
  }

  function updateExchangeFilterSummary() {
    const el = document.getElementById("exchangeFilterSummary");
    if (!el) return;
    if (filterExchangeSet.size === 0) {
      el.textContent = "All exchanges";
      return;
    }
    const labels = [...filterExchangeSet].sort().map((id) => EXCHANGE_LABELS[id] || id);
    el.textContent = labels.join(", ");
  }

  updateThemeButtonLabel();

  if (elInput) {
    elInput.value = snapshotUrl;
  }
  populatePollIntervalSelect();
  restoreUiPreferences();
  if (elSearch) elSearch.value = searchQuery;
  syncHealthMinSelect();
  syncUniformityMinSelect();
  syncExchangeCheckboxesFromSet();
  updateExchangeFilterSummary();
  syncTabVisuals();
  updateSortHeaderClasses();

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
      elPushTierB.textContent = sub ? "Disable list-change push" : "Enable list-change push";
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
    const notifyExchanges =
      filterExchangeSet.size > 0 ? [...filterExchangeSet].sort() : [];
    const payload = { subscription: sub.toJSON(), notify_exchanges: notifyExchanges };
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

  /** Re-POST subscription so relay stores current exchange checkboxes as push filter prefs. */
  async function syncPushNotifyExchangesIfSubscribed() {
    if (!pushTierBAvailable()) return;
    try {
      const reg = await navigator.serviceWorker.ready;
      const existing = await reg.pushManager.getSubscription();
      if (!existing) return;
      const base = pushApiBase();
      const headers = { "Content-Type": "application/json" };
      const tok = pushSubscribeToken();
      if (tok) headers.Authorization = `Bearer ${tok}`;
      const notifyExchanges =
        filterExchangeSet.size > 0 ? [...filterExchangeSet].sort() : [];
      const payload = { subscription: existing.toJSON(), notify_exchanges: notifyExchanges };
      if (tok) payload.token = tok;
      const res = await fetch(`${base}/v1/subscribe`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
        credentials: "omit",
      });
      if (!res.ok) console.warn("push notify_exchanges sync HTTP", res.status);
    } catch (e) {
      console.warn("syncPushNotifyExchanges", e);
    }
  }

  function snapshotTelemetryDismissed() {
    try {
      return sessionStorage.getItem(LS_SNAPSHOT_TELEMETRY_DISMISSED) === "1";
    } catch {
      return false;
    }
  }

  function setSnapshotTelemetryDismissed() {
    try {
      sessionStorage.setItem(LS_SNAPSHOT_TELEMETRY_DISMISSED, "1");
    } catch (e) {
      console.warn("persist snapshot telemetry dismiss", e);
    }
  }

  /** Session: hide scan / relay / regime strips in the Alerts tab only. */
  function dismissOpsScanStripsForSession() {
    setSnapshotTelemetryDismissed();
    syncSnapshotTelemetryPanel();
  }

  function dismissWatchLeaveOnly() {
    if (elWatchLeaveBanner) elWatchLeaveBanner.hidden = true;
    if (elWatchLeaveBannerText) elWatchLeaveBannerText.textContent = "";
    suppressedWatchLeaveSig = watchLeaveSig(lastPinWatchDelta.left);
    syncCoinBellBadge();
  }

  function syncSnapshotTelemetryPanel() {
    if (!elSnapshotTelemetryPanel) return;
    if (snapshotTelemetryDismissed()) {
      elSnapshotTelemetryPanel.hidden = true;
      return;
    }
    const strips = [elHealthStrip, elRelayHealthStrip, elRegimeStrip].filter(Boolean);
    const anyVisible = strips.some((el) => !el.hidden);
    elSnapshotTelemetryPanel.hidden = !anyVisible;
  }

  function showError(msg) {
    elError.textContent = msg;
    elError.hidden = false;
    appendOpsFeedDeduped(`err|${String(msg).slice(0, 200)}`, "—", `Load error: ${msg}`);
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
    if (elRelayHealthStrip) {
      elRelayHealthStrip.hidden = true;
      elRelayHealthStrip.textContent = "";
      elRelayHealthStrip.classList.remove("is-warn");
    }
    if (elRegimeStrip) {
      elRegimeStrip.hidden = true;
      elRegimeStrip.textContent = "";
      elRegimeStrip.classList.remove("is-warn");
    }
    if (elEmptyBanner) {
      elEmptyBanner.hidden = true;
      elEmptyBanner.textContent = "";
    }
    if (elWatchLeaveBanner) {
      elWatchLeaveBanner.hidden = true;
      if (elWatchLeaveBannerText) elWatchLeaveBannerText.textContent = "";
    }
    if (elApiBudgetPanel) {
      elApiBudgetPanel.hidden = true;
      elApiBudgetPanel.innerHTML = "";
    }
    syncSnapshotTelemetryPanel();
    syncCoinBellBadge();
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

  function normalizeWatchSymbol(raw) {
    return String(raw || "")
      .trim()
      .toUpperCase()
      .replace(/\s+/g, "");
  }

  function getPinnedSet() {
    try {
      const raw = localStorage.getItem(LS_PINNED_SYMBOLS_JSON);
      if (!raw) return new Set();
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return new Set();
      return new Set(arr.map((s) => normalizeWatchSymbol(s)).filter(Boolean));
    } catch {
      return new Set();
    }
  }

  function persistPinnedSet(set) {
    const sorted = [...set].sort();
    if (!sorted.length) localStorage.removeItem(LS_PINNED_SYMBOLS_JSON);
    else localStorage.setItem(LS_PINNED_SYMBOLS_JSON, JSON.stringify(sorted));
  }

  function readPinnedWasQualObject() {
    try {
      const raw = localStorage.getItem(LS_PINNED_WAS_QUALIFIED_JSON);
      if (!raw) return {};
      const o = JSON.parse(raw);
      return o && typeof o === "object" && !Array.isArray(o) ? o : {};
    } catch {
      return {};
    }
  }

  function writePinnedWasQualObject(o) {
    const keys = Object.keys(o);
    if (!keys.length) localStorage.removeItem(LS_PINNED_WAS_QUALIFIED_JSON);
    else localStorage.setItem(LS_PINNED_WAS_QUALIFIED_JSON, JSON.stringify(o));
  }

  /**
   * Compare each pinned symbol against the full qualified set (unfiltered). Updates stored was-qualified map.
   * First time a pin appears in storage it baselines without enter/leave.
   */
  function reconcilePinnedQualifiedState(currSet) {
    const pinned = [...getPinnedSet()];
    const raw = readPinnedWasQualObject();
    const entered = [];
    const left = [];
    const pinSet = new Set(pinned);
    for (const p of pinned) {
      const nowQ = currSet.has(p);
      if (!Object.prototype.hasOwnProperty.call(raw, p)) {
        raw[p] = nowQ;
        continue;
      }
      const wasQ = raw[p] === true;
      if (!wasQ && nowQ) entered.push(p);
      if (wasQ && !nowQ) left.push(p);
      raw[p] = nowQ;
    }
    for (const k of Object.keys(raw)) {
      if (!pinSet.has(k)) delete raw[k];
    }
    writePinnedWasQualObject(raw);
    entered.sort();
    left.sort();
    return { entered, left };
  }

  function bootstrapPinStateForSymbol(sym) {
    const s = normalizeWatchSymbol(sym);
    if (!s || !lastPayload) return;
    const coins = Array.isArray(lastPayload.coins) ? lastPayload.coins : [];
    const currSet = new Set(coins.map((c) => String(c.symbol || "").toUpperCase()).filter(Boolean));
    const raw = readPinnedWasQualObject();
    raw[s] = currSet.has(s);
    writePinnedWasQualObject(raw);
  }

  function togglePin(rawSym) {
    const s = normalizeWatchSymbol(rawSym);
    if (!s) return;
    const set = getPinnedSet();
    if (set.has(s)) {
      set.delete(s);
      const raw = readPinnedWasQualObject();
      delete raw[s];
      writePinnedWasQualObject(raw);
    } else {
      set.add(s);
      bootstrapPinStateForSymbol(s);
    }
    persistPinnedSet(set);
    if (lastPayload) {
      applyTableView();
      updateWatchlistBadge();
    }
  }

  function watchLeaveSig(arr) {
    return [...arr]
      .map((x) => String(x).toUpperCase())
      .sort()
      .join(",");
  }

  function updateWatchLeaveBanner(left) {
    if (!elWatchLeaveBanner || !elWatchLeaveBannerText) return;
    const sig = watchLeaveSig(left);
    if (sig !== prevPollWatchLeaveSig) {
      suppressedWatchLeaveSig = "";
    }
    prevPollWatchLeaveSig = sig;
    if (!left.length) {
      elWatchLeaveBanner.hidden = true;
      elWatchLeaveBannerText.textContent = "";
      syncCoinBellBadge();
      return;
    }
    if (sig === suppressedWatchLeaveSig) {
      elWatchLeaveBanner.hidden = true;
      syncCoinBellBadge();
      return;
    }
    elWatchLeaveBanner.hidden = false;
    elWatchLeaveBannerText.textContent = `Watched symbols left the qualified list: ${left.join(", ")}`;
    syncCoinBellBadge();
  }

  /** Qualified-set additions and removals only (schema changes go to the Alerts feed). */
  function updateCoinListDiffBanner(added, dropped) {
    if (!elDiffBanner) return;
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
    if (!parts.length) {
      elDiffBanner.hidden = true;
      elDiffBanner.textContent = "";
      syncCoinBellBadge();
      return;
    }
    elDiffBanner.hidden = false;
    elDiffBanner.textContent = parts.join(" · ");
    syncCoinBellBadge();
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

  function coinUniformity(c) {
    const u = c.uniformity_score;
    if (typeof u !== "number" || !Number.isFinite(u)) return null;
    return u;
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
    const slice = keys.slice(0, 8);
    const rows = slice
      .map((ex) => {
        const raw = ev[ex];
        return `<tr><td>${escapeHtml(String(ex))}</td><td class="num">${escapeHtml(formatUsdVolDisplay(raw))}</td></tr>`;
      })
      .join("");
    const more =
      keys.length > 8
        ? `<tr><td colspan="2" class="cell-muted">+${keys.length - 8} more</td></tr>`
        : "";
    return `<table class="exch-sheet"><thead><tr><th scope="col" title="Exchange venue">Exch</th><th scope="col" title="Approximate 24h volume on that venue from snapshot">Vol</th></tr></thead><tbody>${rows}${more}</tbody></table>`;
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
        if (c._watchlist_only) return true;
        const h = coinHealth(c);
        return h != null && h >= filterHealthMin;
      });
    }
    if (filterUniformityMin != null) {
      rows = rows.filter((c) => {
        if (c._watchlist_only) return true;
        const u = coinUniformity(c);
        return u != null && u >= filterUniformityMin;
      });
    }
    if (filterExchangeSet.size > 0) {
      rows = rows.filter((c) => {
        if (c._watchlist_only) return true;
        const lo = c.listed_on;
        if (!Array.isArray(lo)) return false;
        const listed = new Set(
          lo.map((x) => String(x || "").trim().toLowerCase()).filter(Boolean),
        );
        for (const id of filterExchangeSet) {
          if (listed.has(id)) return true;
        }
        return false;
      });
    }
    return rows;
  }

  function getWatchlistCoinRows() {
    if (!lastPayload) return [];
    const coins = Array.isArray(lastPayload.coins) ? lastPayload.coins : [];
    const bySym = new Map();
    for (const c of coins) {
      bySym.set(String(c.symbol || "").toUpperCase(), c);
    }
    const pinned = [...getPinnedSet()].sort((a, b) => a.localeCompare(b));
    return pinned.map((sym) => {
      const hit = bySym.get(sym);
      if (hit) return hit;
      return {
        symbol: sym,
        name: "",
        gains: {},
        listed_on: [],
        _watchlist_only: true,
      };
    });
  }

  function getFilteredSortedCoins() {
    if (!lastPayload) return [];
    const base =
      activeView === "watchlist"
        ? getWatchlistCoinRows()
        : Array.isArray(lastPayload.coins)
          ? lastPayload.coins
          : [];
    const filtered = applyFilters(base);
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
    if (!isValidSnapshotTimeMs(t)) return "—";
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
      lastStaleBannerShown = false;
      return;
    }
    const snapTs = Date.parse(iso);
    if (!isValidSnapshotTimeMs(snapTs)) {
      elStaleBanner.hidden = true;
      elStaleBanner.textContent = "";
      lastStaleBannerShown = false;
      return;
    }
    const ageSec = Math.max(0, (Date.now() - snapTs) / 1000);
    const stale = ageSec > 2 * intervalSec;
    elStaleBanner.hidden = !stale;
    if (!stale) {
      elStaleBanner.textContent = "";
      lastStaleBannerShown = false;
      return;
    }
    const ageMin = Math.round(ageSec / 60);
    const nomMin = Math.round(intervalSec / 60);
    elStaleBanner.textContent = `Snapshot looks stale (${ageMin} min old). Expected refresh about every ${nomMin} min — check the worker or snapshot URL.`;
    if (stale && !lastStaleBannerShown) {
      appendOpsFeedDeduped(`stale|${iso}`, iso, elStaleBanner.textContent);
    }
    lastStaleBannerShown = stale;
  }

  function formatApiCostPanelLines(panel) {
    if (!panel || !Array.isArray(panel.sources) || !panel.sources.length) return [];
    const lines = [];
    for (const s of panel.sources) {
      const name = s.name != null ? String(s.name) : String(s.id || "API");
      const n = Number(s.this_scan_http);
      const total = Number.isFinite(n) ? Math.round(n) : 0;
      const sub =
        Array.isArray(s.breakdown) && s.breakdown.length
          ? s.breakdown.map((b) => `${String(b.suffix || "?")}: ${Math.round(Number(b.count) || 0)}`).join(", ")
          : "";
      let line = `• ${name}: ${total} HTTP this scan`;
      if (sub) line += ` (${sub})`;
      const cap = s.monthly_budget_http;
      const pct = s.pct_of_monthly_budget;
      if (cap != null && Number(cap) > 0 && pct != null && Number.isFinite(Number(pct))) {
        line += ` · ~${Number(pct).toFixed(3)}% of configured monthly cap (${Math.round(Number(cap))})`;
      }
      line += `\n  ${String(s.pricing_url || "").trim()}`;
      lines.push(line);
    }
    return lines;
  }

  function updateApiBudgetPanel(data) {
    if (!elApiBudgetPanel) return;
    const panel = data.api_cost_panel;
    const intervalSec =
      typeof data.scan_interval_seconds === "number" && Number.isFinite(data.scan_interval_seconds)
        ? Math.max(60, data.scan_interval_seconds)
        : NOMINAL_SCAN_FALLBACK_SEC;
    if (!panel || !Array.isArray(panel.sources)) {
      elApiBudgetPanel.hidden = true;
      elApiBudgetPanel.innerHTML = "";
      return;
    }
    const secMonth = 30 * 86400;
    const scansPerMonth = secMonth / intervalSec;
    const intervalMin = Math.max(1, Math.round(intervalSec / 60));
    const items = [];
    for (const s of panel.sources) {
      const scanHttp = Number(s.this_scan_http);
      const n = Number.isFinite(scanHttp) ? Math.round(scanHttp) : 0;
      const capRaw = s.monthly_budget_http;
      const cap = capRaw != null ? Number(capRaw) : 0;
      const name = escapeHtml(s.name != null ? String(s.name) : String(s.id || "API"));
      const pricing = String(s.pricing_url || "").trim();
      const sub =
        Array.isArray(s.breakdown) && s.breakdown.length
          ? s.breakdown
              .map((b) => `${escapeHtml(String(b.suffix || "?"))}: ${Math.round(Number(b.count) || 0)}`)
              .join(", ")
          : "";
      let riskClass = "budget-meter--neutral";
      let riskText;
      if (cap > 0 && Number.isFinite(cap)) {
        const perScanPct = (n / cap) * 100;
        const projectedPct = ((n * scansPerMonth) / cap) * 100;
        if (projectedPct >= 100) riskClass = "budget-meter--danger";
        else if (projectedPct >= 70) riskClass = "budget-meter--warn";
        else riskClass = "budget-meter--ok";
        riskText = `Projected ~${projectedPct.toFixed(1)}% of monthly cap if every scan matches this load (~${scansPerMonth.toFixed(0)} scans/mo at ${intervalMin}m interval). This scan alone: ${perScanPct.toFixed(3)}% of cap.`;
      } else {
        riskText =
          "Configure monthly HTTP caps in the scanner (SCAN_COSTS + per-vendor cap settings) to see a green/yellow/red traffic-light vs overage risk.";
      }
      const riskTitle = escapeAttr(riskText);
      let li = `<li title="${riskTitle}"><strong>${name}</strong>: ${n} HTTP this scan`;
      if (sub) li += `<br/><span class="api-budget-sub">${sub}</span>`;
      li += `<br/><span class="${riskClass}" title="${riskTitle}">${escapeHtml(riskText)}</span>`;
      if (pricing) {
        li += `<br/><a href="${escapeAttr(pricing)}" class="api-budget-link" rel="noopener noreferrer" target="_blank" title="Open vendor pricing page">Vendor pricing</a>`;
      }
      li += `</li>`;
      items.push(li);
    }
    if (!items.length) {
      elApiBudgetPanel.hidden = true;
      elApiBudgetPanel.innerHTML = "";
      return;
    }
    const note =
      panel.note != null && String(panel.note).trim()
        ? `<p class="api-budget-note">${escapeHtml(String(panel.note))}</p>`
        : "";
    elApiBudgetPanel.hidden = false;
    elApiBudgetPanel.innerHTML = `<h2 class="api-budget-heading" title="Per-vendor HTTP counts this scan and projected share of monthly caps">API usage &amp; budget</h2>${note}<ul class="api-budget-list" title="Hover each line for budget risk details">${items.join("")}</ul>`;
  }

  function updateHealthStrip(data) {
    if (!elHealthStrip) return;
    const dur = data.scan_duration_s;
    const ev = data.coins_evaluated;
    const err = data.errors_count;
    const hasDur = typeof dur === "number" && Number.isFinite(dur);
    const hasEv = typeof ev === "number" && Number.isFinite(ev);
    const hasErr = typeof err === "number" && Number.isFinite(err);
    const apiLines = formatApiCostPanelLines(data.api_cost_panel);
    const hasApi = apiLines.length > 0;
    if (!hasDur && !hasEv && !hasErr && !hasApi) {
      elHealthStrip.hidden = true;
      elHealthStrip.textContent = "";
      return;
    }
    const parts = [];
    if (hasDur) parts.push(`Last scan wall time: ${dur.toFixed(1)}s`);
    if (hasEv) parts.push(`Symbols evaluated: ${Math.round(ev)}`);
    if (hasErr) parts.push(`Metric errors: ${Math.round(err)}`);
    let text = parts.join(" · ");
    if (hasApi) {
      text += `\n\nLast scan API cost estimate (HTTP counts; set monthly caps in config for %):\n${apiLines.join("\n")}`;
    }
    elHealthStrip.textContent = text;
    elHealthStrip.hidden = false;
  }

  function relayHealthUrlFromSnapshotUrl(snapUrl) {
    const raw = (snapUrl || "").trim();
    if (!raw) return "";
    try {
      const u = new URL(raw, window.location.href);
      if (u.protocol !== "http:" && u.protocol !== "https:") return "";
      u.pathname = u.pathname.replace(/[^/]+$/, "relay-health");
      u.search = "";
      u.hash = "";
      return u.href;
    } catch {
      return "";
    }
  }

  function formatByteSize(n) {
    if (typeof n !== "number" || !Number.isFinite(n) || n < 0) return "—";
    if (n < 1024) return `${Math.round(n)} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KiB`;
    return `${(n / (1024 * 1024)).toFixed(2)} MiB`;
  }

  async function refreshRelayHealthStrip() {
    if (!elRelayHealthStrip) return;
    const snapUrl = getSnapshotUrl().trim();
    const override =
      typeof window.__RELAY_HEALTH_URL__ === "string" ? window.__RELAY_HEALTH_URL__.trim() : "";
    const relayUrl = override || relayHealthUrlFromSnapshotUrl(snapUrl);
    elRelayHealthStrip.classList.remove("is-warn");
    if (!relayUrl) {
      elRelayHealthStrip.hidden = true;
      elRelayHealthStrip.textContent = "";
      syncSnapshotTelemetryPanel();
      return;
    }
    const ac = new AbortController();
    const to = window.setTimeout(() => ac.abort(), 8000);
    try {
      const res = await fetch(relayUrl, { credentials: "omit", signal: ac.signal });
      if (res.status === 404) {
        elRelayHealthStrip.hidden = true;
        elRelayHealthStrip.textContent = "";
        return;
      }
      if (!res.ok) {
        elRelayHealthStrip.hidden = false;
        elRelayHealthStrip.classList.add("is-warn");
        elRelayHealthStrip.textContent = `Snapshot relay health: HTTP ${res.status}`;
        return;
      }
      const text = await res.text();
      let j;
      try {
        j = JSON.parse(text);
      } catch {
        elRelayHealthStrip.hidden = true;
        elRelayHealthStrip.textContent = "";
        return;
      }
      const parts = [];
      parts.push("Snapshot relay");
      if (j.has_snapshot_file) parts.push("file ready");
      else parts.push("no file on relay yet");
      const okAt = j.last_successful_ingest_at;
      if (okAt) {
        parts.push(`last ingest ${formatUpdatedHuman(okAt)} (${okAt})`);
        const st = j.last_ingest_http_status;
        if (typeof st === "number") parts.push(`HTTP ${st}`);
        const b = j.last_successful_ingest_bytes;
        if (typeof b === "number") parts.push(formatByteSize(b));
      } else if (j.last_ingest_attempt_at) {
        parts.push(`last attempt ${formatUpdatedHuman(j.last_ingest_attempt_at)}`);
        const st = j.last_ingest_http_status;
        if (typeof st === "number") parts.push(`HTTP ${st}`);
        const err = j.last_error;
        if (err) parts.push(String(err));
        elRelayHealthStrip.classList.add("is-warn");
      }
      elRelayHealthStrip.textContent = parts.join(" · ");
      elRelayHealthStrip.hidden = false;
    } catch {
      elRelayHealthStrip.hidden = false;
      elRelayHealthStrip.classList.add("is-warn");
      elRelayHealthStrip.textContent =
        "Snapshot relay health: unreachable (timeout, CORS, or offline) — check relay URL";
    } finally {
      window.clearTimeout(to);
      syncSnapshotTelemetryPanel();
      if (lastPayload) scheduleOpsFeedSnapshotSummary(lastPayload);
    }
  }

  /** BTC regime gate from snapshot (`REGIME_FILTER_*`); strip when gate blocked all passes. */
  function updateRegimeStrip(rg) {
    if (!elRegimeStrip) return;
    elRegimeStrip.classList.remove("is-warn");
    if (!rg || rg.enabled !== true || rg.blocked !== true) {
      elRegimeStrip.hidden = true;
      elRegimeStrip.textContent = "";
      return;
    }
    const g7 = Number(rg.btc_7d_pct);
    const g30 = Number(rg.btc_30d_pct);
    const min30 = Number(rg.btc_min_30d_gain_pct);
    const max7 = Number(rg.btc_max_abs_7d_gain_pct);
    const reason = rg.reason != null ? String(rg.reason) : "";
    const f = (n) => (Number.isFinite(n) ? n.toFixed(2) : "—");
    elRegimeStrip.hidden = false;
    elRegimeStrip.classList.add("is-warn");
    elRegimeStrip.textContent = `Regime filter blocked all qualifications (BTC gate). BTC 7d: ${f(g7)}% (require |7d| ≤ ${f(max7)}%), 30d: ${f(g30)}% (require ≥ ${f(min30)}%). ${reason}`;
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

  function renderOpsFeedList() {
    const ul = document.getElementById("opsFeedList");
    const empty = document.getElementById("opsFeedEmpty");
    if (!ul) return;
    ul.innerHTML = "";
    for (const it of opsFeedItems) {
      const li = document.createElement("li");
      li.className = "ops-feed-item";
      const isoEsc = escapeHtml(it.iso);
      li.innerHTML = `<time class="ops-feed-time" datetime="${escapeAttr(it.iso)}">${isoEsc}</time><div class="ops-feed-body">${it.html}</div>`;
      ul.appendChild(li);
    }
    if (empty) empty.hidden = opsFeedItems.length > 0;
  }

  /** Append one operational feed row (deduped by key). Plain text is escaped; use only trusted DOM-derived strings. */
  function appendOpsFeedDeduped(key, iso, plainText) {
    if (!plainText || !String(plainText).trim()) return;
    if (opsFeedDedupe.has(key)) return;
    opsFeedDedupe.add(key);
    if (opsFeedDedupe.size > 200) {
      opsFeedDedupe.clear();
      opsFeedDedupe.add(key);
    }
    const html = escapeHtml(String(plainText).trim()).replace(/\n/g, "<br/>");
    opsFeedItems.unshift({ t: Date.now(), iso: iso || "—", html: html });
    opsFeedItems = opsFeedItems.slice(0, 50);
    renderOpsFeedList();
    if (activeView === "alerts") setOpsLastAckToNow();
    syncOpsTabBadge();
  }

  function buildOpsSummaryPlain() {
    const bits = [];
    if (elHealthStrip && !elHealthStrip.hidden) {
      const t = (elHealthStrip.textContent || "").trim();
      const head = t.split(/\n\n/)[0].trim();
      if (head) bits.push(head);
    }
    if (elRelayHealthStrip && !elRelayHealthStrip.hidden) bits.push((elRelayHealthStrip.textContent || "").trim());
    if (elRegimeStrip && !elRegimeStrip.hidden) bits.push((elRegimeStrip.textContent || "").trim());
    if (elStaleBanner && !elStaleBanner.hidden) bits.push((elStaleBanner.textContent || "").trim());
    if (elEmptyBanner && !elEmptyBanner.hidden) bits.push((elEmptyBanner.textContent || "").trim());
    if (elApiBudgetPanel && !elApiBudgetPanel.hidden) {
      const t = (elApiBudgetPanel.textContent || "").trim().slice(0, 1200);
      if (t) bits.push(`API / budget: ${t}`);
    }
    return bits.join("\n\n");
  }

  function tryAppendOpsSnapshotSummaryForIso(iso) {
    if (!lastPayload || String(lastPayload.updated_at || "") !== iso) return;
    const body = buildOpsSummaryPlain();
    if (!body.trim()) return;
    appendOpsFeedDeduped(`summary|${iso}`, iso, body);
  }

  function scheduleOpsFeedSnapshotSummary(data) {
    const iso = data && data.updated_at ? String(data.updated_at) : "";
    if (!iso) return;
    window.clearTimeout(opsSummaryDebounceTimer);
    opsSummaryDebounceTimer = window.setTimeout(() => {
      opsSummaryDebounceTimer = 0;
      tryAppendOpsSnapshotSummaryForIso(iso);
    }, 900);
  }

  function coinSignalsDigest() {
    const d = elDiffBanner && !elDiffBanner.hidden ? (elDiffBanner.textContent || "").trim() : "";
    const w =
      elWatchLeaveBanner && !elWatchLeaveBanner.hidden
        ? (elWatchLeaveBannerText && elWatchLeaveBannerText.textContent
            ? elWatchLeaveBannerText.textContent.trim()
            : "")
        : "";
    return `${d}\n---\n${w}`;
  }

  function readCoinAlertsAckDigest() {
    try {
      return localStorage.getItem(LS_COIN_ALERTS_ACK_DIGEST) || "";
    } catch {
      return "";
    }
  }

  function writeCoinAlertsAckDigest(dig) {
    try {
      localStorage.setItem(LS_COIN_ALERTS_ACK_DIGEST, dig);
    } catch (e) {
      console.warn("coin alerts ack", e);
    }
  }

  function syncCoinBellBadge() {
    if (!elCoinAlertsBadge) return;
    const dig = coinSignalsDigest();
    const ack = readCoinAlertsAckDigest();
    const drawerOpen = elCoinAlertsDrawer && !elCoinAlertsDrawer.hidden;
    const show = Boolean(dig) && dig !== ack && !drawerOpen;
    elCoinAlertsBadge.hidden = !show;
    elCoinAlertsBadge.textContent = show ? "!" : "0";
  }

  function coinListingUrl(c) {
    const cmc = c.cmc_slug && String(c.cmc_slug).trim();
    if (cmc) return `https://coinmarketcap.com/currencies/${encodeURIComponent(cmc)}/`;
    const su = c.source_url && String(c.source_url).trim();
    if (su && /^https?:\/\//i.test(su)) {
      if (/coinmarketcap\.com/i.test(su) || /coingecko\.com/i.test(su)) return su;
    }
    const slug = c.slug && String(c.slug).trim();
    if (slug) return `https://www.coingecko.com/en/coins/${encodeURIComponent(slug)}`;
    if (su && /^https?:\/\//i.test(su)) return su;
    const sym = String(c.symbol || "").trim();
    if (sym) return `https://coinmarketcap.com/search/?q=${encodeURIComponent(sym)}`;
    return "";
  }

  /** Approximate 30 daily closes from 7d/30d % gains when `closes_30d` is absent. */
  function syntheticClosesFromGains(c) {
    const g = c.gains || {};
    const g7 = typeof g["7d"] === "number" ? g["7d"] : 0;
    const g30 = typeof g["30d"] === "number" ? g["30d"] : 0;
    const f7 = 1 + g7 / 100;
    const f30 = 1 + g30 / 100;
    if (!Number.isFinite(f7) || !Number.isFinite(f30) || f7 === 0 || f30 === 0) {
      return [100, 100];
    }
    const end = 100;
    const p22 = end / f7;
    const p0 = end / f30;
    const out = [];
    for (let i = 0; i < 30; i++) {
      if (i <= 22) {
        out.push(p0 + (p22 - p0) * (i / 22));
      } else {
        out.push(p22 + (end - p22) * ((i - 22) / 7));
      }
    }
    return out;
  }

  function effectiveCloses30d(c) {
    const raw = c.closes_30d;
    if (Array.isArray(raw) && raw.length >= 2) {
      const nums = raw.map((x) => Number(x)).filter((x) => Number.isFinite(x));
      if (nums.length >= 2) return nums;
    }
    return syntheticClosesFromGains(c);
  }

  /** Prefer 1h closes (Telegram chart parity); else daily snapshot series; else synthetic from gains. */
  function effectiveSparklineCloses(c) {
    const h1 = c.closes_1h;
    if (Array.isArray(h1) && h1.length >= 2) {
      const nums = h1.map((x) => Number(x)).filter((x) => Number.isFinite(x));
      if (nums.length >= 2) return nums;
    }
    return effectiveCloses30d(c);
  }

  /** Linearly upsample for smoother sparklines when the snapshot has few points (e.g. synthetic 30d). */
  function densifySparklinePoints(closes, targetLen) {
    if (!Array.isArray(closes) || closes.length < 2) return closes || [];
    const seq = closes.map((x) => Number(x)).filter((x) => Number.isFinite(x));
    if (seq.length < 2) return seq;
    const target = Math.max(targetLen, seq.length);
    if (seq.length >= target) return seq;
    const out = [];
    const n = seq.length - 1;
    for (let i = 0; i < target; i++) {
      const pos = (i / (target - 1)) * n;
      const j = Math.floor(pos);
      const t = pos - j;
      const a = seq[j];
      const b = seq[Math.min(j + 1, n)];
      out.push(a + (b - a) * t);
    }
    return out;
  }

  function sparklineSvg(closes, w, h) {
    if (!closes || closes.length < 2) return '<span class="cell-muted">—</span>';
    const min = Math.min(...closes);
    const max = Math.max(...closes);
    const pad = 2;
    const iw = w - pad * 2;
    const ih = h - pad * 2;
    const strokeW = closes.length > 48 ? 1.2 : 1.75;
    const normY = (v) => {
      if (!(max > min)) return pad + ih / 2;
      return pad + ih - ((v - min) / (max - min)) * ih;
    };
    const pts = closes.map((v, i) => {
      const x = pad + (i / (closes.length - 1)) * iw;
      const y = normY(v);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    });
    return `<svg class="spark-svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true"><polyline fill="none" stroke="currentColor" stroke-width="${strokeW}" vector-effect="non-scaling-stroke" points="${pts.join(" ")}" /></svg><span class="visually-hidden">Recent price trend</span>`;
  }

  function fmtSheetCell(v) {
    if (v == null) return "—";
    if (typeof v === "number" && Number.isFinite(v)) {
      if (Math.abs(v) >= 1e6 || (Math.abs(v) > 0 && Math.abs(v) < 1e-4)) return v.toExponential(4);
      return String(Math.round(v * 1e6) / 1e6);
    }
    if (typeof v === "object") return JSON.stringify(v);
    const s = String(v);
    return s.length > 64 ? `${s.slice(0, 63)}…` : s;
  }

  /** Top strategies plus buy & hold (if present), sorted by net_pct for side-by-side comparison. */
  function backtestModalStrategyRows(c) {
    const strategies = Array.isArray(c.backtest_top_strategies)
      ? c.backtest_top_strategies.filter((r) => r && typeof r === "object")
      : [];
    const out = strategies.map((r) => ({ ...r }));
    const bh = c.backtest_buy_hold != null && typeof c.backtest_buy_hold === "object" ? c.backtest_buy_hold : null;
    const hasBh = out.some((r) => String(r.indicator || "").trim() === "B&H");
    if (bh && !hasBh) out.push({ ...bh });
    out.sort((a, b) => {
      const na = Number(a.net_pct);
      const nb = Number(b.net_pct);
      const fa = Number.isFinite(na) ? na : Number.NEGATIVE_INFINITY;
      const fb = Number.isFinite(nb) ? nb : Number.NEGATIVE_INFINITY;
      return fb - fa;
    });
    return out;
  }

  function backtestStrategiesTableHtml(rows) {
    if (!Array.isArray(rows) || !rows.length) {
      return '<p class="detail-muted">No strategy rows in this snapshot.</p>';
    }
    const preferred = ["indicator", "strategy", "net_pct", "win_pct", "trades", "tsl_hits", "rank"];
    const allKeys = [...new Set(rows.flatMap((r) => (r && typeof r === "object" ? Object.keys(r) : [])))];
    const useKeys = [
      ...preferred.filter((k) => allKeys.includes(k)),
      ...allKeys.filter((k) => !preferred.includes(k)).sort(),
    ];
    if (!useKeys.length) return '<p class="detail-muted">No columns.</p>';
    const th = useKeys
      .map((k) => `<th scope="col" title="${escapeAttr(`Backtest optimizer field: ${k}`)}">${escapeHtml(k)}</th>`)
      .join("");
    const tb = rows
      .map((r) => {
        if (!r || typeof r !== "object") return "";
        return `<tr>${useKeys.map((k) => `<td>${escapeHtml(fmtSheetCell(r[k]))}</td>`).join("")}</tr>`;
      })
      .join("");
    return `<table class="sheet-table"><thead><tr>${th}</tr></thead><tbody>${tb}</tbody></table>`;
  }

  function backtestModalHtml(c) {
    const parts = [];
    const chartRaw = c.chart_image_url;
    if (typeof chartRaw === "string" && /^https:\/\//i.test(chartRaw.trim())) {
      const u = chartRaw.trim();
      parts.push(
        `<p class="bt-modal-chart"><a href="${escapeAttr(u)}" target="_blank" rel="noopener noreferrer" title="Open full-size backtest chart in a new tab">Open backtest chart image</a></p>`,
      );
      const symLabel = escapeAttr(String(c.symbol || "coin"));
      parts.push(
        `<p class="bt-modal-thumb"><img class="chart-thumb-modal" src="${escapeAttr(u)}" alt="${symLabel} backtest chart" loading="lazy" width="480" /></p>`,
      );
    }
    parts.push('<h3 class="sheet-heading">Strategy comparison</h3>');
    parts.push(backtestStrategiesTableHtml(backtestModalStrategyRows(c)));
    return parts.join("");
  }

  function backtestCellHtml(c) {
    const chartRaw = c.chart_image_url;
    const hasChart = typeof chartRaw === "string" && /^https:\/\//i.test(chartRaw.trim());
    const strategies = Array.isArray(c.backtest_top_strategies) ? c.backtest_top_strategies : [];
    const hasBh = c.backtest_buy_hold != null && typeof c.backtest_buy_hold === "object";
    const hasSheet = strategies.length > 0 || hasBh;
    const rawSym = escapeAttr(String(c.symbol || ""));
    const parts = [];
    if (hasChart) {
      const u = chartRaw.trim();
      parts.push(
        `<a href="${escapeAttr(u)}" class="bt-chart-link" rel="noopener noreferrer" target="_blank" title="Open backtest chart image in a new tab">Chart</a>`,
      );
    }
    if (hasSheet) {
      parts.push(
        `<button type="button" class="bt-sheet-btn secondary" data-symbol="${rawSym}" title="View strategy table and buy/hold summary for this symbol">Results</button>`,
      );
    }
    if (!parts.length) return '<span class="cell-muted">—</span>';
    return `<div class="bt-cell">${parts.join("")}</div>`;
  }

  const COL_COUNT = 9;

  function renderRowsHtml(coins, pinnedSet, pinEnterSet) {
    if (!coins.length) {
      let msg;
      if (activeView === "watchlist") {
        msg =
          getPinnedSet().size === 0
            ? "Your watchlist is empty. On the Qualified tab, click the star next to a symbol to add it here."
            : "No watchlist rows match the current filters.";
      } else {
        msg = "No qualified coins match the current filters.";
      }
      return `<tr><td colspan="${COL_COUNT}" class="empty">${escapeHtml(msg)}</td></tr>`;
    }
    return coins
      .map((c) => {
        const rawSym = String(c.symbol || "").toUpperCase();
        const watchOnly = c._watchlist_only === true;
        if (watchOnly) {
          const sym = escapeHtml(String(c.symbol || ""));
          const pinLabel = `Remove ${rawSym} from watchlist`;
          const pinBtn = `<button type="button" class="pin-btn" data-symbol="${escapeAttr(rawSym)}" aria-pressed="true" aria-label="${escapeAttr(pinLabel)}" title="${escapeAttr(pinLabel)}">\u2605</button>`;
          const dash = '<span class="cell-muted">\u2014</span>';
          return `<tr class="coin-row coin-row--watchlist-only" data-symbol="${escapeAttr(rawSym)}">
          <td headers="col-symbol" class="sym-cell"><span class="sym-cell-inner">${pinBtn}<strong>${sym}</strong></span></td>
          <td headers="col-name"><span class="cell-muted" title="Symbol not in the current qualified snapshot">Not in snapshot</span></td>
          <td headers="col-g7" class="num">${dash}</td>
          <td headers="col-g30" class="num">${dash}</td>
          <td headers="col-uniformity" class="num">${dash}</td>
          <td headers="col-health" class="num">${dash}</td>
          <td headers="col-volaccel" class="num">${dash}</td>
          <td headers="col-exch" class="exch-col">${dash}</td>
          <td headers="col-backtest">${dash}</td>
        </tr>`;
        }
        const isPinned = pinnedSet.has(rawSym);
        const isPinEnter = pinEnterSet.has(rawSym);
        const rowClasses = ["coin-row"];
        if (isPinned) rowClasses.push("coin-row--pinned");
        if (isPinEnter) rowClasses.push("coin-row--pin-enter");
        const sym = escapeHtml(String(c.symbol || ""));
        const nameRaw = String(c.name || "");
        const name = escapeHtml(nameRaw);
        const g = c.gains || {};
        const g7 = typeof g["7d"] === "number" ? g["7d"].toFixed(1) : "—";
        const g30pct = typeof g["30d"] === "number" ? g["30d"].toFixed(1) : "—";
        const rawSpark = effectiveSparklineCloses(c);
        const closes = densifySparklinePoints(rawSpark, SPARKLINE_TARGET_POINTS);
        const has1h = Array.isArray(c.closes_1h) && c.closes_1h.length >= 2;
        const hasRealDaily = Array.isArray(c.closes_30d) && c.closes_30d.length >= 2;
        const g30Title = has1h
          ? "30-day % from snapshot; sparkline uses recent 1h closes (interpolated for display when needed)"
          : hasRealDaily
            ? "30-day % and price trend from snapshot daily closes (interpolated for display when needed)"
            : "30-day % from snapshot; trend line is estimated from 7d/30d returns then smoothed for display until the scanner adds closes_1h or closes_30d";
        const spark = sparklineSvg(closes, 168, 44);
        const g30Cell = `<div class="g30-cell" title="${escapeAttr(g30Title)}"><span class="g30-pct"><span class="visually-hidden">30-day gain </span>${g30pct}%</span>${spark}</div>`;
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
        const listing = coinListingUrl(c);
        const nameCell = listing
          ? `<a href="${escapeAttr(listing)}" class="coin-listing-link" rel="noopener noreferrer" target="_blank" data-symbol="${escapeAttr(rawSym)}" title="Open listing or reference page in a new tab">${name}</a>`
          : `<span title="Name from snapshot (no listing URL)">${name}</span>`;
        const badge = lastAddedSet.has(rawSym)
          ? '<span class="badge badge-new" title="New since last visit">New</span>'
          : "";
        const pinLabel = isPinned ? `Remove ${rawSym} from watchlist` : `Add ${rawSym} to watchlist`;
        const pinChar = isPinned ? "\u2605" : "\u2606";
        const pinBtn = `<button type="button" class="pin-btn" data-symbol="${escapeAttr(rawSym)}" aria-pressed="${isPinned ? "true" : "false"}" aria-label="${escapeAttr(pinLabel)}" title="${escapeAttr(pinLabel)}">${pinChar}</button>`;
        const exchHtml = exchangeVolumeCellHtml(c);
        const btHtml = backtestCellHtml(c);
        return `<tr class="${rowClasses.join(" ")}" data-symbol="${escapeAttr(rawSym)}">
          <td headers="col-symbol" class="sym-cell"><span class="sym-cell-inner">${pinBtn}<strong>${sym}</strong>${badge}</span></td>
          <td headers="col-name">${nameCell}</td>
          <td headers="col-g7" class="num"><span class="visually-hidden">7-day gain </span><span title="7-day percentage gain from snapshot">${g7}%</span></td>
          <td headers="col-g30" class="num">${g30Cell}</td>
          <td headers="col-uniformity" class="num"><span class="visually-hidden">Uniformity </span><span title="OHLCV uniformity score (higher = more consistent bar structure)">${u}</span></td>
          <td headers="col-health" class="num"><span class="visually-hidden">Health </span><span title="Composite health score from snapshot">${h}</span></td>
          <td headers="col-volaccel" class="num"><span class="visually-hidden">Volume acceleration </span><span title="Volume vs baseline window from snapshot">${volStr}</span></td>
          <td headers="col-exch" class="exch-col">${exchHtml}</td>
          <td headers="col-backtest">${btHtml}</td>
        </tr>`;
      })
      .join("");
  }

  function applyTableView() {
    if (!lastPayload) return;
    const filtered = getFilteredSortedCoins();
    const pinned = getPinnedSet();
    elTbody.innerHTML = renderRowsHtml(filtered, pinned, pinEnterFlashSet);
    updateSortHeaderClasses();
    applyHashHighlight();
    if (pinEnterFlashSet.size > 0) {
      window.clearTimeout(pinEnterClearTimer);
      pinEnterClearTimer = window.setTimeout(() => {
        document.querySelectorAll("tr.coin-row--pin-enter").forEach((r) => r.classList.remove("coin-row--pin-enter"));
      }, 12000);
    }
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
      if (isValidSnapshotTimeMs(snapTs) && intervalSec > 0) {
        const nextIso = new Date(snapTs + intervalSec * 1000).toISOString();
        nextHint = ` · next scan ${formatNextScanLabel(nextIso)} (${nextIso.slice(0, 19)}Z)`;
      }
    }
    let alertSuffix = "";
    if (notifyAlertsEnabled) {
      alertSuffix = ` · Tier-A update alerts on (${pollIntervalHumanPhrase(getPollIntervalMs())})`;
    }
    const nWatch = getPinnedSet().size;
    const watchHint = nWatch ? ` · ${nWatch} watched` : "";
    elMeta.textContent = `Updated ${updatedHuman} (${updatedDisplay}) · field_set=${fieldSet} · ${coins.length} coin(s)${watchHint}${nextHint}${alertSuffix}`;

    updateApiBudgetPanel(data);

    if (elEmptyBanner) {
      const rg = data.regime_gate;
      const regimeBlocked = rg && rg.enabled === true && rg.blocked === true;
      if (coins.length > 0) {
        elEmptyBanner.hidden = true;
        elEmptyBanner.textContent = "";
      } else {
        elEmptyBanner.hidden = false;
        elEmptyBanner.textContent = regimeBlocked
          ? "No qualified coins in this snapshot — the BTC regime filter blocked all uniformity passes (see the Regime strip on the Alerts tab). This is expected when `REGIME_FILTER_ENABLED` is on and BTC 7d/30d fails the gate."
          : "This JSON has 0 coins. The file committed at `docs/qualified_public_snapshot.json` is a placeholder; live scans (Telegram / Render worker) do not update GitHub automatically. Point this dashboard at your relay: set `window.__SNAPSHOT_URL__` in `docs/dashboard/config.js` to `https://<your-snapshot>.onrender.com/qualified_public_snapshot.json`, or add `?api=` with that URL. Alternatively run `python scripts/sync_snapshot_to_docs.py` after a scan and push the updated file.";
      }
    }

    const prevSyms = readPrevSymbolSet();
    const prevSchema = localStorage.getItem(LS_PREV_SCHEMA) ?? "";
    const currSet = new Set(
      coins.map((c) => String(c.symbol || "").toUpperCase()).filter(Boolean),
    );
    lastPinWatchDelta = reconcilePinnedQualifiedState(currSet);
    pinEnterFlashSet = new Set(lastPinWatchDelta.entered);
    updateWatchLeaveBanner(lastPinWatchDelta.left);
    const added =
      prevSyms.size === 0 ? [] : [...currSet].filter((s) => !prevSyms.has(s)).sort();
    const dropped =
      prevSyms.size === 0 ? [] : [...prevSyms].filter((s) => !currSet.has(s)).sort();
    lastAddedSet = new Set(added);

    const curSchema = String(data.schema_version ?? "");
    const schemaChanged = prevSchema !== "" && prevSchema !== curSchema;
    if (schemaChanged) {
      appendOpsFeedDeduped(
        `schema|${prevSchema}|${curSchema}`,
        updatedRaw || "—",
        `schema_version ${prevSchema} → ${curSchema}`,
      );
    }

    updateCoinListDiffBanner(added, dropped);
    updateStaleBanner(data);
    updateHealthStrip(data);
    updateRegimeStrip(data.regime_gate);
    void refreshRelayHealthStrip();

    syncSnapshotTelemetryPanel();
    scheduleOpsFeedSnapshotSummary(data);
    syncCoinBellBadge();

    applyTableView();
    updateWatchlistBadge();
    writeSnapshotVisitState(data);
  }

  if (elTbody) {
    elTbody.addEventListener("click", (ev) => {
      const pinBtn = ev.target.closest(".pin-btn");
      if (pinBtn) {
        ev.preventDefault();
        ev.stopPropagation();
        togglePin(pinBtn.getAttribute("data-symbol") || "");
        return;
      }
      const sheetBtn = ev.target.closest(".bt-sheet-btn");
      if (sheetBtn) {
        ev.preventDefault();
        ev.stopPropagation();
        const sym = sheetBtn.getAttribute("data-symbol") || "";
        const pool = Array.isArray(lastPayload?.coins) ? lastPayload.coins : [];
        const coin = pool.find((x) => String(x.symbol || "").toUpperCase() === sym.toUpperCase());
        if (coin && elBacktestModal && elBacktestModalTitle && elBacktestModalBody) {
          elBacktestModalTitle.textContent = `${String(coin.symbol || "")} · ${String(coin.name || "")}`;
          elBacktestModalBody.innerHTML = backtestModalHtml(coin);
          elBacktestModal.showModal();
        }
        return;
      }
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

  /** Tier-A alerts: only when the **filtered** list (search, health, **exchanges**) changes vs last poll — same membership rule as the table (e.g. Kraken-only hides MEXC-only coins). */
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
    const exchHint =
      filterExchangeSet.size > 0
        ? ` · Listings: ${[...filterExchangeSet]
            .sort()
            .map((id) => EXCHANGE_LABELS[id] || id)
            .join(", ")}`
        : "";
    let body = `Filtered view: ${syms.length} coin(s)${exchHint}`;
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

  /** Tier-A: notify when a watched symbol enters or leaves the full qualified set (independent of table filters). */
  async function notifyPinnedWatch(entered, left) {
    if (!notifyAlertsEnabled || (!entered.length && !left.length)) return;
    const coins = Array.isArray(lastPayload?.coins) ? lastPayload.coins : [];
    const filtered = applyFilters(coins);
    const filteredSet = new Set(
      filtered.map((c) => String(c.symbol || "").toUpperCase()).filter(Boolean),
    );
    const enteredFiltered = entered
      .map((s) => String(s || "").toUpperCase())
      .filter((s) => filteredSet.has(s));
    const parts = [];
    if (enteredFiltered.length) {
      parts.push(
        `In: ${enteredFiltered.slice(0, 12).join(", ")}${enteredFiltered.length > 12 ? "…" : ""}`,
      );
    }
    if (left.length) {
      parts.push(`Out: ${left.slice(0, 12).join(", ")}${left.length > 12 ? "…" : ""}`);
    }
    if (!parts.length) return;
    const body = `Watch · ${parts.join(" · ")}`;
    try {
      const reg = await navigator.serviceWorker.ready;
      if (reg && typeof reg.showNotification === "function") {
        await reg.showNotification("Watched symbols (qualified set)", {
          body,
          tag: "qualified-pinned-watch",
          renotify: true,
        });
      } else if (typeof Notification === "function") {
        new Notification("Watched symbols (qualified set)", { body });
      }
    } catch (e) {
      console.warn("pinned watch notification failed", e);
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
      const text = await res.text();
      if (!res.ok) {
        if (showErrors) {
          let msg = `HTTP ${res.status} loading snapshot`;
          if (res.status === 503) {
            try {
              const errBody = JSON.parse(text);
              if (errBody && errBody.error) msg += ` (${errBody.error})`;
            } catch {
              /* body may not be JSON */
            }
            msg +=
              ". The relay is running but has no file yet. After a worker scan completes, it POSTs JSON here (worker env QUALIFIED_SNAPSHOT_RELAY_URL + QUALIFIED_SNAPSHOT_RELAY_SECRET matching the snapshot service; worker config PUBLIC_QUALIFIED_SNAPSHOT_ENABLED true). Wait for the next scan or check Render worker logs for relay errors.";
          }
          showError(msg);
        }
        return;
      }
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
        await notifyPinnedWatch(lastPinWatchDelta.entered, lastPinWatchDelta.left);
      } else {
        localStorage.setItem(LS_DIGEST, await digestHex(text));
      }
    } catch (e) {
      if (!showErrors) return;
      const raw = String(e && e.message ? e.message : e);
      const low = raw.toLowerCase();
      const u = url.trim();
      let hint = "";
      if (u.includes("YOUR-SNAPSHOT-SERVICE") || u.includes("YOUR-SERVICE")) {
        hint =
          " Replace the placeholder in docs/dashboard/config.js with your snapshot relay HTTPS URL (see README).";
      } else if (
        low.includes("failed to fetch") ||
        low.includes("networkerror") ||
        low.includes("load failed")
      ) {
        hint =
          " Often CORS, a bad URL, or pointing at the worker — use the snapshot web relay (not the background worker), HTTPS, and CORS allowing this origin.";
      }
      showError(raw + hint);
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
    const ms = getPollIntervalMs();
    pollTimer = window.setInterval(() => {
      loadSnapshot({ showErrors: false, forNotify: true });
    }, ms);
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
      persistUiPreferences();
    });
  });

  if (elHealthMinSelect) {
    elHealthMinSelect.addEventListener("change", () => {
      const raw = elHealthMinSelect.value;
      filterHealthMin = raw === "" ? null : Number(raw);
      if (filterHealthMin != null && !Number.isFinite(filterHealthMin)) filterHealthMin = null;
      if (filterHealthMin != null && filterHealthMin !== 60 && filterHealthMin !== 70) {
        filterHealthMin = null;
      }
      syncHealthMinSelect();
      applyTableView();
      persistUiPreferences();
      resetTierAPollBaselineIfAlerts();
      void syncPushNotifyExchangesIfSubscribed();
    });
  }

  if (elUniformityMinSelect) {
    elUniformityMinSelect.addEventListener("change", () => {
      const raw = elUniformityMinSelect.value;
      filterUniformityMin = raw === "" ? null : Number(raw);
      if (filterUniformityMin != null && !Number.isFinite(filterUniformityMin)) filterUniformityMin = null;
      if (filterUniformityMin != null && filterUniformityMin !== 60 && filterUniformityMin !== 65) {
        filterUniformityMin = null;
      }
      syncUniformityMinSelect();
      applyTableView();
      persistUiPreferences();
      resetTierAPollBaselineIfAlerts();
      void syncPushNotifyExchangesIfSubscribed();
    });
  }

  const tabQ = document.getElementById("tabQualified");
  const tabW = document.getElementById("tabWatchlist");
  if (tabQ) {
    tabQ.addEventListener("click", () => setActiveView("qualified"));
  }
  if (tabW) {
    tabW.addEventListener("click", () => setActiveView("watchlist"));
  }
  const tabA = document.getElementById("tabOps");
  if (tabA) {
    tabA.addEventListener("click", () => setActiveView("alerts"));
  }

  if (elOpsMarkReadBtn) {
    elOpsMarkReadBtn.addEventListener("click", () => ackOpsNotificationsFromUi());
  }

  if (elCoinAlertsBell && elCoinAlertsDrawer) {
    elCoinAlertsBell.addEventListener("click", () => {
      const open = elCoinAlertsDrawer.hidden;
      elCoinAlertsDrawer.hidden = !open;
      elCoinAlertsBell.setAttribute("aria-expanded", open ? "true" : "false");
      if (open) writeCoinAlertsAckDigest(coinSignalsDigest());
      syncCoinBellBadge();
    });
  }

  if (elSearch) {
    elSearch.addEventListener("input", () => {
      window.clearTimeout(searchDebounceTimer);
      searchDebounceTimer = window.setTimeout(() => {
        searchQuery = elSearch.value || "";
        applyTableView();
        persistUiPreferences();
        resetTierAPollBaselineIfAlerts();
        void syncPushNotifyExchangesIfSubscribed();
      }, SEARCH_DEBOUNCE_MS);
    });
  }

  function onExchangeCheckboxChange() {
    filterExchangeSet = new Set();
    document.querySelectorAll("input[data-exchange-cb]:checked").forEach((inp) => {
      const id = String(inp.value || "").trim().toLowerCase();
      if (TARGET_EXCHANGE_IDS.has(id)) filterExchangeSet.add(id);
    });
    updateExchangeFilterSummary();
    applyTableView();
    persistUiPreferences();
    resetTierAPollBaselineIfAlerts();
    void syncPushNotifyExchangesIfSubscribed();
  }

  document.querySelectorAll("input[data-exchange-cb]").forEach((inp) => {
    inp.addEventListener("change", onExchangeCheckboxChange);
  });

  if (elExchangeFilterApply && elExchangeFilterDetails) {
    elExchangeFilterApply.addEventListener("click", () => {
      elExchangeFilterDetails.open = false;
    });
  }

  if (elExchangeFilterSelectAll) {
    elExchangeFilterSelectAll.addEventListener("click", () => {
      document.querySelectorAll("input[data-exchange-cb]").forEach((inp) => {
        inp.checked = true;
      });
      onExchangeCheckboxChange();
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

  if (elExportBtn) {
    elExportBtn.addEventListener("click", () => {
      if (!lastPayload) return;
      const fmt = elExportFormatSelect && elExportFormatSelect.value === "json" ? "json" : "csv";
      if (fmt === "json") exportViewJson();
      else exportViewCsv();
    });
  }

  if (elPollInterval) {
    elPollInterval.addEventListener("change", () => {
      persistPollIntervalFromUi();
      if (notifyAlertsEnabled) {
        startPoll();
        if (lastPayload) render(lastPayload);
      }
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
      persistPollIntervalFromUi();
      localStorage.removeItem(LS_POLL_FILTERED_SYMS);
      clearError();
      await loadSnapshot({ showErrors: true, forNotify: false });
      startPoll();
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

  async function copyTextToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    try {
      return document.execCommand("copy");
    } finally {
      document.body.removeChild(ta);
    }
  }

  function wireDonateCopyButtons() {
    for (const btn of document.querySelectorAll("button[data-donate-copy]")) {
      const fullLabel = btn.getAttribute("aria-label") || "Copy address";
      btn.addEventListener("click", async () => {
        const text = btn.getAttribute("data-donate-copy");
        if (!text) return;
        try {
          const ok = await copyTextToClipboard(text);
          if (ok) {
            btn.setAttribute("aria-label", "Copied");
            btn.classList.add("is-copied");
            window.setTimeout(() => {
              btn.setAttribute("aria-label", fullLabel);
              btn.classList.remove("is-copied");
            }, 1600);
          } else {
            btn.setAttribute("aria-label", "Copy failed");
            window.setTimeout(() => btn.setAttribute("aria-label", fullLabel), 2000);
          }
        } catch {
          btn.setAttribute("aria-label", "Copy failed");
          window.setTimeout(() => btn.setAttribute("aria-label", fullLabel), 2000);
        }
      });
    }
  }

  wireDonateCopyButtons();

  if (elWatchLeaveBannerDismiss) {
    elWatchLeaveBannerDismiss.addEventListener("click", () => dismissWatchLeaveOnly());
  }

  if (elTelemetryStripDismiss) {
    elTelemetryStripDismiss.addEventListener("click", () => dismissOpsScanStripsForSession());
  }

  syncSnapshotTelemetryPanel();

  if (snapshotUrl) {
    loadSnapshot({ showErrors: true, forNotify: false });
  } else {
    showError("Set a snapshot JSON URL (?api=…) or define window.__SNAPSHOT_URL__ in config.js.");
  }
})();
