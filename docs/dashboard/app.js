/**
 * Qualified-coin dashboard (Milestones Q4, Q7–Q19): snapshot JSON; sort/filter;
 * stale banner; theme (Q15); export CSV/JSON (Q16); deep links (Q17); a11y (Q18);
 * optional chart thumb (Q19); scan health strip (Q20); tier-A alerts; tier-B Web Push (Q21); Qualified / Watchlist / Logs / Settings tabs; coin bell popover; rolling 24h ops log. 7d/30d sparklines from `closes_1h` (7d only when ≥168 bars; 30d uses last 720 hourly bars). Watchlist pins are `SYMBOL|venue` row keys. Snapshot URL from ?api=… or window.__SNAPSHOT_URL__ in config.js (no URL field in UI).
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
  const DEFAULT_POLL_MS = 60 * 60 * 1000;
  const LS_POLL_INTERVAL_MS = "qualified_dash_poll_interval_ms";
  const LS_DIGEST = "qualified_dash_last_snap_digest";
  const LS_PREV_SYMBOLS = "qualified_dash_prev_symbols_json";
  const LS_PREV_SCHEMA = "qualified_dash_prev_schema_version";
  const LS_THEME = "qualified_dash_theme";
  /** Last measured `#mainDataPanel` width so Logs/Settings match the qualified column when it is hidden. */
  const LS_SHELL_MIN_W = "qualified_dash_shell_min_w_v1";
  /** Tier-A poll: previous filtered symbol list under current UI filters (JSON array string). */
  /** Tier-A: JSON array of `SYMBOL|exchangeId` row keys for filtered table diff (v2). */
  const LS_POLL_FILTERED_ROWS = "qualified_dash_poll_filtered_rows_v2";
  /** @deprecated cleared on upgrade; replaced by LS_POLL_FILTERED_ROWS */
  const LS_POLL_FILTERED_SYMS_LEGACY = "qualified_dash_poll_filtered_syms";
  /** Tier-A poll: last snapshot body digest after a poll (avoids duplicate “refresh” vs filtered-change notify). */
  const LS_LAST_POLL_SNAPSHOT_DIGEST = "qualified_dash_last_poll_snapshot_digest";
  /** Rolling ops log (24h retention); survives refresh in this browser (localStorage). */
  const LS_OPS_FEED_STORE = "qualified_dash_ops_feed_store_v1";
  /** Table sort + filters: survive refresh and PWA relaunch (same origin). */
  const LS_UI_SORT_KEY = "qualified_dash_ui_sort_key";
  const LS_UI_SORT_DIR = "qualified_dash_ui_sort_dir";
  const LS_UI_HEALTH_MIN = "qualified_dash_ui_health_min";
  const LS_UI_UNIFORMITY_MIN = "qualified_dash_ui_uniformity_min";
  /** ``, `pos`, `25`, or `50` — volume acceleration filter. */
  const LS_UI_VOL_ACCEL = "qualified_dash_ui_vol_accel";
  /** Minimum 24h volume (USD) on the row’s venue; empty = no floor. */
  const LS_UI_VOL_MIN_USD = "qualified_dash_ui_vol_min_usd";
  /** Max % below window high per chart; empty = no filter. Values: 5, 10, 15. */
  const LS_UI_CHART_DIST_MAX_7 = "qualified_dash_ui_chart_dist_max_7";
  const LS_UI_CHART_DIST_MAX_30 = "qualified_dash_ui_chart_dist_max_30";
  /** @deprecated migrated on restore to LS_UI_CHART_DIST_MAX_7 / _30 */
  const LS_UI_CHART_DIST_MAX_LEGACY = "qualified_dash_ui_chart_dist_max";
  /** @deprecated use LS_UI_EXCHANGES_JSON */
  const LS_UI_EXCHANGE = "qualified_dash_ui_exchange";
  const LS_UI_EXCHANGES_JSON = "qualified_dash_ui_exchanges_json";
  /** Uppercase symbols — legacy watch list only (migrated once to row keys). */
  const LS_PINNED_SYMBOLS_JSON = "qualified_dash_pinned_symbols_json";
  /** Watch pins: `SYMBOL|exchangeId` (e.g. `PENDLE|coinbase`) so each venue row is independent. */
  const LS_PINNED_ROW_KEYS_JSON = "qualified_dash_pinned_row_keys_json";
  /** Maps symbol → was qualified on last snapshot (boolean). */
  const LS_PINNED_WAS_QUALIFIED_JSON = "qualified_dash_pinned_was_qualified_json";
  /** ``qualified`` | ``watchlist`` | ``logs`` | ``settings`` — which main tab is active. */
  const LS_UI_ACTIVE_VIEW = "qualified_dash_active_view";
  /** Persist Tier-A browser poll alerts on/off (requires Notification permission). */
  const LS_TIER_A_ALERTS_ENABLED = "qualified_dash_tier_a_alerts_enabled";
  /** ``qualified`` = list + filtered table OS alerts; ``watchlist`` = pinned symbols in/out of qualified set only. */
  const LS_TIER_A_NOTIFY_SCOPE = "qualified_dash_tier_a_notify_scope_v1";
  /** Session: hide scan health / relay / regime strip cluster until tab closes. */
  const LS_SNAPSHOT_TELEMETRY_DISMISSED = "qualified_dash_snapshot_telemetry_dismissed";
  /** Milliseconds: operational feed items at or before this time count as read (Logs tab badge). */
  const LS_OPS_LAST_ACK_MS = "qualified_dash_ops_last_ack_ms";
  /** Digest of coin-only banners last acknowledged with the bell drawer (localStorage). */
  const LS_COIN_ALERTS_ACK_DIGEST = "qualified_dash_coin_alerts_ack_digest";
  /** Persisted qualified-list enter/exit lines for the bell dropdown (newest appended). */
  const LS_COIN_ALERT_FEED_JSON = "qualified_dash_coin_alert_feed_v1";
  const COIN_ALERT_FEED_MAX = 50;
  /** Starting point when no localStorage yet; raise here if you reset storage mid-cycle. */
  const DASHBOARD_COINGECKO_DEMO_BASELINE = 3650;
  const DASHBOARD_COINGECKO_DEMO_CREDITS_MONTHLY = 10000;
  const DASHBOARD_COINGECKO_DEMO_RPM = 30;
  const LS_CG_CREDITS_USED = "qualified_dash_cg_credits_used_v2";
  const LS_CG_LAST_SNAP_ISO = "qualified_dash_cg_last_snapshot_iso_v2";
  /** First-visit prompt for browser notifications (Tier-A); dismissed after user chooses. */
  const LS_NOTIFY_FIRST_PROMPT_DONE = "qualified_dash_notify_first_prompt_done_v1";
  /** Fallback when snapshot omits scan_interval_seconds (older files). */
  const NOMINAL_SCAN_FALLBACK_SEC = 3600;
  /** Treat snapshot timestamps before this as invalid for age/stale (epoch placeholders, corrupt data). */
  const MIN_VALID_SNAPSHOT_MS = Date.UTC(2000, 0, 1, 0, 0, 0, 0);

  const ALLOWED_POLL_MS = new Set(POLL_INTERVAL_OPTIONS.map((o) => o.ms));
  const ALLOWED_SORT_KEYS = new Set([
    "symbol",
    "name",
    "g7pct",
    "g7hi",
    "g30pct",
    "g30hi",
    "btbest",
    "btvbh",
    "uniformity",
    "health",
    "volaccel",
    "venue",
    "vol24h",
    "rvol7",
    "mdd30",
  ]);
  const VOL_MIN_FILTER_OPTIONS = [
    { v: 100000, label: "$100k" },
    { v: 500000, label: "$500k" },
    { v: 1000000, label: "$1M" },
    { v: 10000000, label: "$10M" },
  ];
  /** Scanner default target exchanges — must match worker `TARGET_EXCHANGES` / snapshot `listed_on`. */
  const TARGET_EXCHANGES_LIST = ["coinbase", "kraken"];
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

  function updateThemeButtonLabel() {
    const el = document.getElementById("themeToggleBtn");
    if (!el) return;
    const mode = getSavedThemeMode();
    const m = mode === "light" || mode === "dark" ? mode : "system";
    el.classList.remove("theme-toggle-btn--system", "theme-toggle-btn--light", "theme-toggle-btn--dark");
    el.classList.add(`theme-toggle-btn--${m}`);
    for (const svg of el.querySelectorAll(".theme-toggle-svg")) {
      svg.hidden = true;
    }
    const active = el.querySelector(`.theme-toggle-svg--${mode}`) || el.querySelector(".theme-toggle-svg--system");
    if (active) active.hidden = false;
    const labels = { system: "follow system", light: "light", dark: "dark" };
    const lab = labels[mode] || mode;
    el.setAttribute("aria-label", `Theme: ${lab}. Click to switch (system → light → dark).`);
    el.title = `Theme: ${lab}. Click to cycle: system, light, dark (saved in this browser).`;
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

  const elError = document.getElementById("error");
  const elMeta = document.getElementById("meta");
  const elKpiQualifiedCount = document.getElementById("kpiQualifiedCount");
  const elKpiCoinbaseCount = document.getElementById("kpiCoinbaseCount");
  const elKpiKrakenCount = document.getElementById("kpiKrakenCount");
  const elSnapshotLoadingOverlay = document.getElementById("snapshotLoadingOverlay");
  const elApiBudgetPanelSettings = document.getElementById("apiBudgetPanelSettings");
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
  const elVolAccelFilterSelect = document.getElementById("volAccelFilterSelect");
  const elVolumeMinSelect = document.getElementById("volumeMinSelect");
  const elChartDistMax7Select = document.getElementById("chartDistMax7Select");
  const elChartDistMax30Select = document.getElementById("chartDistMax30Select");
  const elChartFsDialog = document.getElementById("chartFsDialog");
  const elChartFsTitle = document.getElementById("chartFsTitle");
  const elChartFsStats = document.getElementById("chartFsStats");
  const elChartFsSvg = document.getElementById("chartFsSvg");
  const elChartFsClose = document.getElementById("chartFsClose");
  const elWatchlistBadge = document.getElementById("watchlistBadge");
  const elEmptyBanner = document.getElementById("emptyBanner");
  const elStaleBanner = document.getElementById("staleBanner");
  const elSnapshotValidationBanner = document.getElementById("snapshotValidationBanner");
  const elCompareBar = document.getElementById("compareBar");
  const elCompareBarLabel = document.getElementById("compareBarLabel");
  const elCompareOpenBtn = document.getElementById("compareOpenBtn");
  const elCompareClearBtn = document.getElementById("compareClearBtn");
  const elCompareDialog = document.getElementById("compareDialog");
  const elCompareDialogClose = document.getElementById("compareDialogClose");
  const elCompareDialogBody = document.getElementById("compareDialogBody");
  /** @type {string[]} max two pin keys `SYMBOL|exchange` */
  let comparePickKeys = [];
  const elHealthStrip = document.getElementById("healthStrip");
  const elRelayHealthStrip = document.getElementById("relayHealthStrip");
  const elRegimeStrip = document.getElementById("regimeStrip");
  const elSnapshotTelemetryPanel = document.getElementById("snapshotTelemetryPanel");
  const elTelemetryStripDismiss = document.getElementById("telemetryStripDismiss");
  const elOpsMarkReadBtn = document.getElementById("opsMarkReadBtn");
  const elThemeToggle = document.getElementById("themeToggleBtn");
  const elNotifyPromptDialog = document.getElementById("notifyPromptDialog");
  const elNotifyPromptEnable = document.getElementById("notifyPromptEnable");
  const elNotifyPromptLater = document.getElementById("notifyPromptLater");
  const elCoinAlertsBell = document.getElementById("coinAlertsBell");
  const elCoinAlertsPopover = document.getElementById("coinAlertsPopover");
  const elCoinAlertsDropdownRoot = document.getElementById("coinAlertsDropdownRoot");
  const elCoinAlertsBadge = document.getElementById("coinAlertsBadge");
  const elOpsTabBadge = document.getElementById("opsTabBadge");
  const elNotify = document.getElementById("notifyBtn");
  const elPollInterval = document.getElementById("pollIntervalSelect");
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
  /** Appended to meta line once after loading `../qualified_public_snapshot.json` when the relay returns 503. */
  let snapshotMetaSuffix = "";
  /** True when the last successful snapshot fetch used the committed-repo fallback (relay 503). */
  let snapshotLoadWasCommittedFallback = false;
  /** @type {Set<string>} */
  let lastAddedSet = new Set();
  let sortKey = "health";
  let sortDir = -1;
  /** @type {number | null} */
  let filterHealthMin = null;
  /** @type {number | null} */
  let filterUniformityMin = null;
  /** @type {"" | "pos" | "25" | "50"} */
  let filterVolAccel = "";
  /** @type {number | null} minimum 24h volume USD on the row’s venue */
  let filterVolMinUsd = null;
  /** @type {5 | 10 | 15 | null} hide rows where 7d % below window high is >= this */
  let filterChartDistMax7 = null;
  /** @type {5 | 10 | 15 | null} hide rows where 30d % below window high is >= this */
  let filterChartDistMax30 = null;
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
  /** @type {"qualified" | "watchlist" | "logs" | "settings"} */
  let activeView = "qualified";
  const OPS_LOG_RETENTION_MS = 24 * 60 * 60 * 1000;
  /** @type {{ t: number, iso: string, html: string, k?: string }[]} */
  let opsFeedItems = [];
  const opsFeedDedupe = new Set();
  let opsFeedPersistTimer = 0;
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
    if (unread === 0) {
      elOpsTabBadge.hidden = true;
      elOpsTabBadge.textContent = "";
      return;
    }
    elOpsTabBadge.hidden = false;
    elOpsTabBadge.textContent = unread > 99 ? "99+" : String(unread);
  }

  /** Reset Tier-A poll diff baseline so filter changes do not fire bogus in/out alerts. */
  function resetTierAPollBaselineIfAlerts() {
    if (!notifyAlertsEnabled) return;
    try {
      localStorage.removeItem(LS_POLL_FILTERED_ROWS);
      localStorage.removeItem(LS_POLL_FILTERED_SYMS_LEGACY);
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
      if (!filterVolAccel) localStorage.removeItem(LS_UI_VOL_ACCEL);
      else localStorage.setItem(LS_UI_VOL_ACCEL, filterVolAccel);
      if (filterVolMinUsd == null) localStorage.removeItem(LS_UI_VOL_MIN_USD);
      else localStorage.setItem(LS_UI_VOL_MIN_USD, String(filterVolMinUsd));
      if (filterChartDistMax7 == null) localStorage.removeItem(LS_UI_CHART_DIST_MAX_7);
      else localStorage.setItem(LS_UI_CHART_DIST_MAX_7, String(filterChartDistMax7));
      if (filterChartDistMax30 == null) localStorage.removeItem(LS_UI_CHART_DIST_MAX_30);
      else localStorage.setItem(LS_UI_CHART_DIST_MAX_30, String(filterChartDistMax30));
      try {
        localStorage.removeItem(LS_UI_CHART_DIST_MAX_LEGACY);
      } catch {
        /* ignore */
      }
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
      if (sk === "g7") sortKey = "g7pct";
      else if (sk === "g30") sortKey = "g30pct";
      else if (sk && ALLOWED_SORT_KEYS.has(sk)) sortKey = sk;
      const sd = localStorage.getItem(LS_UI_SORT_DIR);
      if (sd === "1" || sd === "-1") sortDir = Number(sd);
      const hm = localStorage.getItem(LS_UI_HEALTH_MIN);
      if (hm === null || hm === "") filterHealthMin = null;
      else {
        const n = Number(hm);
        if (Number.isNaN(n)) filterHealthMin = null;
        else if (n === 60 || n === 65 || n === 70) filterHealthMin = n;
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
      const vac = localStorage.getItem(LS_UI_VOL_ACCEL);
      if (vac === "pos" || vac === "25" || vac === "50") filterVolAccel = vac;
      else filterVolAccel = "";
      const vmin = localStorage.getItem(LS_UI_VOL_MIN_USD);
      filterVolMinUsd = null;
      if (vmin != null && vmin !== "") {
        const vn = Number(vmin);
        if (Number.isFinite(vn) && VOL_MIN_FILTER_OPTIONS.some((o) => o.v === vn)) filterVolMinUsd = vn;
      }
      filterChartDistMax7 = null;
      filterChartDistMax30 = null;
      const c7 = localStorage.getItem(LS_UI_CHART_DIST_MAX_7);
      const c30 = localStorage.getItem(LS_UI_CHART_DIST_MAX_30);
      if (c7 === "5" || c7 === "10" || c7 === "15") filterChartDistMax7 = Number(c7);
      if (c30 === "5" || c30 === "10" || c30 === "15") filterChartDistMax30 = Number(c30);
      if (filterChartDistMax7 == null && filterChartDistMax30 == null) {
        const legacy = localStorage.getItem(LS_UI_CHART_DIST_MAX_LEGACY);
        if (legacy === "5" || legacy === "10" || legacy === "15") {
          const n = Number(legacy);
          filterChartDistMax7 = n;
          filterChartDistMax30 = n;
        }
      }
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
      if (av === "watchlist" || av === "qualified" || av === "logs" || av === "settings") activeView = av;
      else if (av === "alerts") activeView = "logs";
    } catch (e) {
      console.warn("restoreUiPreferences", e);
    }
  }

  function syncHealthMinSelect() {
    if (!elHealthMinSelect) return;
    const v = filterHealthMin == null ? "" : String(filterHealthMin);
    elHealthMinSelect.value = v === "60" || v === "65" || v === "70" ? v : "";
  }

  function syncVolumeMinSelect() {
    if (!elVolumeMinSelect) return;
    const v = filterVolMinUsd == null ? "" : String(filterVolMinUsd);
    const ok = VOL_MIN_FILTER_OPTIONS.some((o) => String(o.v) === v);
    elVolumeMinSelect.value = ok ? v : "";
  }

  function syncUniformityMinSelect() {
    if (!elUniformityMinSelect) return;
    const v = filterUniformityMin == null ? "" : String(filterUniformityMin);
    elUniformityMinSelect.value = v === "60" || v === "65" ? v : "";
  }

  function syncVolAccelFilterSelect() {
    if (!elVolAccelFilterSelect) return;
    const v = filterVolAccel === "pos" || filterVolAccel === "25" || filterVolAccel === "50" ? filterVolAccel : "";
    elVolAccelFilterSelect.value = v;
  }

  function syncChartDistFilterSelects() {
    const applyOne = (el, val) => {
      if (!el) return;
      const v = val == null ? "" : String(val);
      el.value = v === "5" || v === "10" || v === "15" ? v : "";
    };
    applyOne(elChartDistMax7Select, filterChartDistMax7);
    applyOne(elChartDistMax30Select, filterChartDistMax30);
  }

  function updateWatchlistBadge() {
    if (!elWatchlistBadge) return;
    const n = getPinnedRowKeySet().size;
    elWatchlistBadge.textContent = n ? String(n) : "";
    elWatchlistBadge.hidden = n === 0;
  }

  /** Tier-A: turn notifications on or off (same logic as Settings “Enable update alerts”). */
  async function toggleTierANotifications() {
    if (!("Notification" in window)) {
      showError("Browser notifications are not supported here.");
      return;
    }
    if (notifyAlertsEnabled) {
      stopPoll();
      notifyAlertsEnabled = false;
      try {
        localStorage.removeItem(LS_TIER_A_ALERTS_ENABLED);
        localStorage.removeItem(LS_LAST_POLL_SNAPSHOT_DIGEST);
      } catch {
        /* ignore */
      }
      syncNotifyTierAButton();
      if (lastPayload) render(lastPayload);
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
      syncNotifyTierAButton();
      return;
    }
    await registerServiceWorker();
    notifyAlertsEnabled = true;
    try {
      localStorage.setItem(LS_TIER_A_ALERTS_ENABLED, "1");
    } catch {
      /* ignore */
    }
    persistPollIntervalFromUi();
    localStorage.removeItem(LS_POLL_FILTERED_ROWS);
    localStorage.removeItem(LS_POLL_FILTERED_SYMS_LEGACY);
    try {
      localStorage.removeItem(LS_LAST_POLL_SNAPSHOT_DIGEST);
    } catch {
      /* ignore */
    }
    clearError();
    await loadSnapshot({ showErrors: true, forNotify: false });
    startPoll();
    syncPushTierBVisibility();
    void refreshPushTierBLabel();
    syncNotifyTierAButton();
  }

  function syncNotifyTierAButton() {
    if (!elNotify) return;
    const perm = "Notification" in window ? Notification.permission : "denied";
    if (notifyAlertsEnabled && perm !== "granted") {
      notifyAlertsEnabled = false;
      try {
        localStorage.removeItem(LS_TIER_A_ALERTS_ENABLED);
      } catch {
        /* ignore */
      }
    }
    const on = notifyAlertsEnabled && perm === "granted";
    elNotify.classList.toggle("notify-tier-a-btn--on", on);
    elNotify.textContent = on ? "Update alerts on" : "Enable update alerts";
  }

  function closeCoinAlertsPopover() {
    if (elCoinAlertsPopover) elCoinAlertsPopover.hidden = true;
    if (elCoinAlertsBell) elCoinAlertsBell.setAttribute("aria-expanded", "false");
  }

  function toggleCoinAlertsPopover() {
    if (!elCoinAlertsPopover || !elCoinAlertsBell) return;
    const willOpen = elCoinAlertsPopover.hidden;
    elCoinAlertsPopover.hidden = !willOpen;
    elCoinAlertsBell.setAttribute("aria-expanded", willOpen ? "true" : "false");
    if (willOpen) renderCoinAlertsList();
    syncCoinBellBadge();
  }

  function readCachedShellMinWidth() {
    try {
      const v = parseFloat(localStorage.getItem(LS_SHELL_MIN_W));
      return Number.isFinite(v) && v > 0 ? v : null;
    } catch {
      return null;
    }
  }

  function persistShellMinWidth(w) {
    try {
      localStorage.setItem(LS_SHELL_MIN_W, String(Math.round(w)));
    } catch {
      /* ignore */
    }
  }

  function capShellWidthToBody(px) {
    const shell = document.querySelector(".dashboard-shell");
    if (!shell || !Number.isFinite(px)) return px;
    const host = shell.parentElement;
    const cap = host ? host.getBoundingClientRect().width : document.documentElement.clientWidth;
    return Math.min(Math.max(0, px), cap);
  }

  /** Keep `.dashboard-shell` at least as wide as the main data column (KPI + table), including when that panel is hidden. */
  function refreshDashboardShellWidth() {
    const shell = document.querySelector(".dashboard-shell");
    if (!shell) return;
    const mainP = document.getElementById("mainDataPanel");
    let w = null;
    if (mainP && !mainP.hidden) {
      const rw = mainP.getBoundingClientRect().width;
      if (rw > 0) {
        w = rw;
        persistShellMinWidth(rw);
      }
    }
    if (w == null) w = readCachedShellMinWidth();
    if (w != null && w > 0) {
      shell.style.minWidth = `${Math.ceil(capShellWidthToBody(w))}px`;
    }
  }

  function syncTabVisuals() {
    const mainPPre = document.getElementById("mainDataPanel");
    if (mainPPre && !mainPPre.hidden) {
      refreshDashboardShellWidth();
    }
    const onQ = activeView === "qualified";
    const onW = activeView === "watchlist";
    const onLogs = activeView === "logs";
    const onSettings = activeView === "settings";
    const tq = document.getElementById("tabQualified");
    const tw = document.getElementById("tabWatchlist");
    const tLogs = document.getElementById("tabLogs");
    const tSettings = document.getElementById("tabSettings");
    const mainP = mainPPre || document.getElementById("mainDataPanel");
    const opsP = document.getElementById("opsPanel");
    const settingsP = document.getElementById("settingsPanel");
    if (tq && tw && tLogs && tSettings) {
      tq.classList.toggle("is-active", onQ);
      tw.classList.toggle("is-active", onW);
      tLogs.classList.toggle("is-active", onLogs);
      tSettings.classList.toggle("is-active", onSettings);
      tq.setAttribute("aria-selected", onQ ? "true" : "false");
      tw.setAttribute("aria-selected", onW ? "true" : "false");
      tLogs.setAttribute("aria-selected", onLogs ? "true" : "false");
      tSettings.setAttribute("aria-selected", onSettings ? "true" : "false");
    }
    if (mainP) {
      mainP.hidden = onLogs || onSettings;
      if (onW) mainP.setAttribute("aria-labelledby", "tabWatchlist");
      else if (onQ) mainP.setAttribute("aria-labelledby", "tabQualified");
      else mainP.setAttribute("aria-labelledby", "tabQualified");
    }
    if (opsP) opsP.hidden = !onLogs;
    if (settingsP) settingsP.hidden = !onSettings;
    if (elMainHeading) {
      if (onLogs) elMainHeading.textContent = "Logs";
      else if (onSettings) elMainHeading.textContent = "Settings";
      else if (onW) elMainHeading.textContent = "Watchlist";
      else elMainHeading.textContent = "Qualified list";
    }
    if (onLogs || onSettings) closeCoinAlertsPopover();
    updateWatchlistBadge();
    syncOpsTabBadge();
    syncCoinBellBadge();
    syncNotifyTierAButton();
    if (mainP && !mainP.hidden) {
      window.requestAnimationFrame(() => {
        refreshDashboardShellWidth();
      });
    } else {
      refreshDashboardShellWidth();
    }
  }

  function setActiveView(view) {
    if (view === "logs" || view === "alerts") activeView = "logs";
    else if (view === "settings") activeView = "settings";
    else activeView = view === "watchlist" ? "watchlist" : "qualified";
    if (activeView === "logs") ackOpsNotificationsFromUi();
    syncTabVisuals();
    persistUiPreferences();
    if (activeView !== "logs" && activeView !== "settings") applyTableView();
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
      el.textContent = "All";
      return;
    }
    const labels = [...filterExchangeSet].sort().map((id) => EXCHANGE_LABELS[id] || id);
    el.textContent = labels.join(", ");
  }

  updateThemeButtonLabel();

  populatePollIntervalSelect();
  restoreUiPreferences();
  const elTierANotifyScopeSelect = document.getElementById("tierANotifyScopeSelect");
  function syncTierANotifyScopeSelect() {
    if (!elTierANotifyScopeSelect) return;
    elTierANotifyScopeSelect.value = tierANotifyScope();
  }
  syncTierANotifyScopeSelect();
  if (elTierANotifyScopeSelect) {
    elTierANotifyScopeSelect.addEventListener("change", () => {
      const v = elTierANotifyScopeSelect.value === "watchlist" ? "watchlist" : "qualified";
      try {
        localStorage.setItem(LS_TIER_A_NOTIFY_SCOPE, v);
      } catch {
        /* ignore */
      }
      resetTierAPollBaselineIfAlerts();
    });
  }
  syncHealthMinSelect();
  syncUniformityMinSelect();
  syncVolAccelFilterSelect();
  syncVolumeMinSelect();
  syncChartDistFilterSelects();
  syncExchangeCheckboxesFromSet();
  updateExchangeFilterSummary();
  try {
    if (
      localStorage.getItem(LS_TIER_A_ALERTS_ENABLED) === "1" &&
      typeof Notification !== "undefined" &&
      Notification.permission === "granted"
    ) {
      notifyAlertsEnabled = true;
    }
  } catch {
    /* ignore */
  }
  if (notifyAlertsEnabled) {
    void registerServiceWorker().then(() => {
      startPoll();
    });
  }
  syncTabVisuals();
  renderCoinAlertsList();
  updateSortHeaderClasses();

  const elMainDataPanelRo = document.getElementById("mainDataPanel");
  if (typeof ResizeObserver !== "undefined" && elMainDataPanelRo) {
    const shellRo = new ResizeObserver(() => {
      refreshDashboardShellWidth();
    });
    shellRo.observe(elMainDataPanelRo);
  }
  window.addEventListener("resize", () => {
    refreshDashboardShellWidth();
  });
  refreshDashboardShellWidth();

  function getSnapshotUrl() {
    const params = new URLSearchParams(window.location.search);
    const rawQ = params.get("api");
    const fromQuery = typeof rawQ === "string" && rawQ.trim() !== "" ? rawQ.trim() : "";
    const configured =
      typeof window.__SNAPSHOT_URL__ === "string" && window.__SNAPSHOT_URL__.trim() !== ""
        ? window.__SNAPSHOT_URL__.trim()
        : "";
    return fromQuery || configured || "";
  }

  /** Same-origin committed snapshot (one level up from `docs/dashboard/`). Used when the live relay has no file yet (503). */
  function getCommittedSnapshotFallbackUrl() {
    try {
      return new URL("../qualified_public_snapshot.json", window.location.href).href;
    } catch {
      return "";
    }
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

  /** Session: hide scan / relay / regime strips in the Logs tab only. */
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
    if (elApiBudgetPanelSettings) {
      elApiBudgetPanelSettings.hidden = true;
      elApiBudgetPanelSettings.innerHTML = "";
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

  function normalizeRowPinKey(raw) {
    const s = String(raw || "").trim();
    const i = s.indexOf("|");
    if (i === -1) {
      const sym = normalizeWatchSymbol(s);
      return sym ? `${sym}|` : "";
    }
    const sym = normalizeWatchSymbol(s.slice(0, i));
    const ex = s.slice(i + 1).trim().toLowerCase();
    if (!sym) return "";
    return ex ? `${sym}|${ex}` : `${sym}|`;
  }

  function parseRowPinKey(key) {
    const s = String(key || "").trim();
    const i = s.indexOf("|");
    if (i === -1) return { sym: normalizeWatchSymbol(s), ex: "" };
    return { sym: normalizeWatchSymbol(s.slice(0, i)), ex: s.slice(i + 1).trim().toLowerCase() };
  }

  function rowViewPinKey(r) {
    const sym = normalizeWatchSymbol(r.coin && r.coin.symbol);
    const ex = r.exchangeId ? String(r.exchangeId).trim().toLowerCase() : "";
    return ex ? `${sym}|${ex}` : `${sym}|`;
  }

  function rowPinKeyDisplayLabel(key) {
    const { sym, ex } = parseRowPinKey(key);
    if (!sym) return String(key || "");
    if (!ex) return sym;
    const lab = EXCHANGE_LABELS[ex] || ex;
    return `${sym} (${lab})`;
  }

  function migrateLegacyPinsToRowKeys(coins, legacySymbols) {
    const bySym = new Map();
    for (const c of coins) {
      if (c && !c._watchlist_only) bySym.set(String(c.symbol || "").toUpperCase(), c);
    }
    const keys = new Set();
    for (const item of legacySymbols) {
      const sym = normalizeWatchSymbol(item);
      if (!sym) continue;
      const hit = bySym.get(sym);
      if (!hit) {
        keys.add(`${sym}|`);
        continue;
      }
      const rows = explodeCoinRowsForTable([hit]).filter((row) => !row.coin._watchlist_only);
      for (const row of rows) {
        if (row.exchangeId) keys.add(`${sym}|${row.exchangeId}`);
      }
      if (!rows.length) keys.add(`${sym}|`);
    }
    const sorted = [...keys].sort();
    if (sorted.length) localStorage.setItem(LS_PINNED_ROW_KEYS_JSON, JSON.stringify(sorted));
    else localStorage.removeItem(LS_PINNED_ROW_KEYS_JSON);
    localStorage.removeItem(LS_PINNED_SYMBOLS_JSON);
  }

  /** Pinned table row keys `SYMBOL|venue` (after optional one-time migration from symbol-only storage). */
  function getPinnedRowKeySet() {
    const coins = Array.isArray(lastPayload?.coins) ? lastPayload.coins : [];
    try {
      const rawNew = localStorage.getItem(LS_PINNED_ROW_KEYS_JSON);
      if (rawNew) {
        const arr = JSON.parse(rawNew);
        if (Array.isArray(arr) && arr.length) {
          return new Set(arr.map(normalizeRowPinKey).filter(Boolean));
        }
      }
    } catch {
      /* fall through */
    }
    try {
      const rawLeg = localStorage.getItem(LS_PINNED_SYMBOLS_JSON);
      if (rawLeg && coins.length) {
        const leg = JSON.parse(rawLeg);
        if (Array.isArray(leg) && leg.length) {
          migrateLegacyPinsToRowKeys(coins, leg);
          const raw2 = localStorage.getItem(LS_PINNED_ROW_KEYS_JSON);
          if (raw2) {
            const arr2 = JSON.parse(raw2);
            if (Array.isArray(arr2) && arr2.length) {
              return new Set(arr2.map(normalizeRowPinKey).filter(Boolean));
            }
          }
        }
      }
    } catch {
      /* ignore */
    }
    return new Set();
  }

  function persistPinnedRowKeys(set) {
    const sorted = [...set].map(normalizeRowPinKey).filter(Boolean).sort();
    if (!sorted.length) {
      localStorage.removeItem(LS_PINNED_ROW_KEYS_JSON);
      return;
    }
    localStorage.setItem(LS_PINNED_ROW_KEYS_JSON, JSON.stringify(sorted));
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
   * Compare each pinned row key against the full qualified set (by symbol). Updates stored was-qualified map.
   * First time a pin appears in storage it baselines without enter/leave.
   */
  function reconcilePinnedQualifiedState(currSet) {
    const pinned = [...getPinnedRowKeySet()];
    const raw = readPinnedWasQualObject();
    const entered = [];
    const left = [];
    const pinSet = new Set(pinned);
    for (const p of pinned) {
      const { sym } = parseRowPinKey(p);
      const nowQ = sym ? currSet.has(sym) : false;
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

  function bootstrapPinStateForRowKey(rowKey) {
    const k = normalizeRowPinKey(rowKey);
    if (!k || !lastPayload) return;
    const { sym } = parseRowPinKey(k);
    if (!sym) return;
    const coins = Array.isArray(lastPayload.coins) ? lastPayload.coins : [];
    const currSet = new Set(coins.map((c) => String(c.symbol || "").toUpperCase()).filter(Boolean));
    const raw = readPinnedWasQualObject();
    raw[k] = currSet.has(sym);
    writePinnedWasQualObject(raw);
  }

  function togglePinRow(rawKey) {
    const k = normalizeRowPinKey(rawKey);
    if (!k) return;
    const set = getPinnedRowKeySet();
    if (set.has(k)) {
      set.delete(k);
      const raw = readPinnedWasQualObject();
      delete raw[k];
      writePinnedWasQualObject(raw);
    } else {
      set.add(k);
      bootstrapPinStateForRowKey(k);
    }
    persistPinnedRowKeys(set);
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
    const leftLbl = left.map((k) => rowPinKeyDisplayLabel(k)).join(", ");
    elWatchLeaveBannerText.textContent = `Watched rows left the qualified list: ${leftLbl}`;
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

  function coinRiskHv7(c) {
    const r = c.risk_context;
    if (!r || typeof r !== "object") return null;
    const v = r.hv_7d_annualized_pct;
    return typeof v === "number" && Number.isFinite(v) ? v : null;
  }

  function coinRiskMdd30(c) {
    const r = c.risk_context;
    if (!r || typeof r !== "object") return null;
    const v = r.max_drawdown_30d_pct;
    return typeof v === "number" && Number.isFinite(v) ? v : null;
  }

  function tierANotifyScope() {
    try {
      const v = localStorage.getItem(LS_TIER_A_NOTIFY_SCOPE);
      return v === "watchlist" ? "watchlist" : "qualified";
    } catch {
      return "qualified";
    }
  }

  /** Public icon CDN; may miss some symbols, so callers should provide visual fallback. */
  function coinLogoUrl(c) {
    const sym = String(c.symbol || "").trim().toLowerCase();
    if (!sym) return "";
    /* Windows reserves CON; batch download stores that ticker as con_win.png. */
    const fileBase = sym === "con" ? "con_win" : sym;
    return `./icons/coins/${encodeURIComponent(fileBase)}.png`;
  }

  function coinIdentityCmcId(c) {
    if (!c || typeof c !== "object") return null;
    const id =
      c.identity && c.identity.cmc_id != null ? c.identity.cmc_id : c.cmc_id;
    if (typeof id === "number" && Number.isFinite(id)) return id;
    if (typeof id === "string" && /^\d+$/.test(id.trim())) return Number(id.trim());
    return null;
  }

  /** Remote URLs tried in order after the local bundled PNG fails (see coinLogoImgHtml). */
  function coinLogoRemoteFallbackUrls(c) {
    const urls = [];
    const cmcId = coinIdentityCmcId(c);
    if (cmcId != null) {
      urls.push(`https://s2.coinmarketcap.com/static/img/coins/64x64/${cmcId}.png`);
    }
    const sym = String(c.symbol || "").trim().toLowerCase();
    if (sym) {
      urls.push(`https://coinicons-api.vercel.app/api/icon/${encodeURIComponent(sym)}`);
      urls.push(
        `https://cdn.jsdelivr.net/gh/spothq/cryptocurrency-icons@master/128/color/${encodeURIComponent(sym)}.png`,
      );
    }
    return urls;
  }

  function coinLogoImgHtml(c) {
    const logoUrl = coinLogoUrl(c);
    if (!logoUrl) {
      return '<span class="coin-logo coin-logo--fallback" aria-hidden="true"></span>';
    }
    const chain = coinLogoRemoteFallbackUrls(c).join("|");
    const logoMonogram = coinLogoMonogramDataUrl(c.symbol);
    const onerr =
      "(function(el){var ch=(el.dataset.fallbackChain||'').split('|').filter(Boolean);var i=Number(el.dataset.logoStep||0)||0;if(i<ch.length){el.dataset.logoStep=String(i+1);el.src=ch[i];return;}if(el.dataset.fallbackSvg){el.src=el.dataset.fallbackSvg;return;}el.style.display='none';})(this)";
    return `<img class="coin-logo" src="${escapeAttr(logoUrl)}" alt="" loading="lazy" decoding="async" data-fallback-chain="${escapeAttr(chain)}" data-fallback-svg="${escapeAttr(logoMonogram)}" data-logo-step="0" onerror="${onerr}" />`;
  }

  function coinLogoMonogramDataUrl(symbol) {
    const raw = String(symbol || "").trim().toUpperCase();
    const label = (raw || "?").slice(0, 3);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"><rect width="128" height="128" rx="64" ry="64" fill="#1f2937"/><text x="50%" y="55%" text-anchor="middle" font-family="Arial,sans-serif" font-size="44" font-weight="700" fill="#f8fafc">${label}</text></svg>`;
    return `data:image/svg+xml,${encodeURIComponent(svg)}`;
  }

  function exchangeLogoUrl(exchangeId) {
    const ex = String(exchangeId || "").trim().toLowerCase();
    if (ex === "coinbase") return "./icons/exchanges/coinbase.png";
    if (ex === "kraken") return "./icons/exchanges/kraken.png";
    if (ex === "mexc") return "./icons/exchanges/mexc.png";
    return "";
  }

  function rowBestBacktestNetPct(r) {
    const winner = rowBestBacktestWinnerRow(r.coin);
    if (!winner) return null;
    const n = Number(winner.net_pct);
    return Number.isFinite(n) ? n : null;
  }

  /** Strategy row with highest net_pct (includes buy & hold when present). */
  function rowBestBacktestWinnerRow(c) {
    if (!c || typeof c !== "object") return null;
    const rows = Array.isArray(c.backtest_top_strategies)
      ? c.backtest_top_strategies.filter((x) => x && typeof x === "object")
      : [];
    const out = rows.map((x) => x);
    const bh = c.backtest_buy_hold != null && typeof c.backtest_buy_hold === "object" ? c.backtest_buy_hold : null;
    if (bh && !out.some((x) => backtestRowIsBuyHold(x))) out.push(bh);
    let bestRow = null;
    let bestNet = null;
    for (const x of out) {
      const n = Number(x.net_pct);
      if (!Number.isFinite(n)) continue;
      if (bestNet == null || n > bestNet) {
        bestNet = n;
        bestRow = x;
      }
    }
    return bestRow;
  }

  function backtestRowTslPct(row) {
    if (!row || backtestRowIsBuyHold(row)) return null;
    const raw = row.trailing_stop_loss_pct != null ? row.trailing_stop_loss_pct : row.trailing_stop_pct;
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? n : null;
  }

  function formatBacktestTslLabel(tsl) {
    if (tsl == null || !Number.isFinite(tsl)) return "";
    return `${Number.isInteger(tsl) ? tsl.toFixed(0) : tsl.toFixed(1)}%`;
  }

  function backtestRowTslHitPct(row) {
    if (!row || backtestRowIsBuyHold(row)) return null;
    const trades = Number(row.trades);
    const hits = Number(row.tsl_hits);
    if (!Number.isFinite(trades) || trades <= 0) return null;
    if (!Number.isFinite(hits) || hits < 0) return null;
    return (hits / trades) * 100;
  }

  function formatBacktestTslHitLabel(pct) {
    if (pct == null || !Number.isFinite(pct)) return "—";
    return `${pct.toFixed(1)}%`;
  }

  function rowBuyHoldNetPct(r) {
    const c = r.coin;
    if (!c.backtest_buy_hold || typeof c.backtest_buy_hold !== "object") return null;
    const n = Number(c.backtest_buy_hold.net_pct);
    return Number.isFinite(n) ? n : null;
  }

  /** Max `net_pct` among `backtest_top_strategies` rows that are not buy-and-hold (B&H comes from `backtest_buy_hold`). */
  function rowBestStrategyNetPctExcludingBh(r) {
    const c = r.coin;
    const rows = Array.isArray(c.backtest_top_strategies) ? c.backtest_top_strategies : [];
    let best = null;
    for (const x of rows) {
      if (!x || typeof x !== "object") continue;
      if (String(x.indicator || "").trim() === "B&H") continue;
      const n = Number(x.net_pct);
      if (!Number.isFinite(n)) continue;
      best = best == null ? n : Math.max(best, n);
    }
    return best;
  }

  /** Positive gap (strategy net % minus buy & hold) when the best strategy beats B&H; otherwise null. */
  function rowBotVsBhPositiveGap(r) {
    const bh = rowBuyHoldNetPct(r);
    const strat = rowBestStrategyNetPctExcludingBh(r);
    if (bh == null || strat == null) return null;
    const gap = strat - bh;
    if (!Number.isFinite(gap) || gap <= 0) return null;
    return gap;
  }

  function computeScoreRanges(viewRows) {
    const rows = Array.isArray(viewRows) ? viewRows : [];
    const finiteStats = (vals) => {
      const nums = vals.filter((n) => Number.isFinite(n));
      if (!nums.length) return { min: null, max: null };
      return { min: Math.min(...nums), max: Math.max(...nums) };
    };
    return {
      health: finiteStats(rows.map((r) => coinHealth(r.coin))),
      uniformity: finiteStats(rows.map((r) => coinUniformity(r.coin))),
      btBest: finiteStats(rows.map((r) => rowBestBacktestNetPct(r))),
    };
  }

  function pctInRange(val, range) {
    if (!Number.isFinite(val)) return null;
    if (!range || !Number.isFinite(range.min) || !Number.isFinite(range.max)) return null;
    if (range.max <= range.min) return 100;
    const pct = ((val - range.min) / (range.max - range.min)) * 100;
    return Math.max(0, Math.min(100, pct));
  }

  function formatUsdVolDisplay(val) {
    if (val == null || val === "" || val === "N/A") return "—";
    if (typeof val === "number" && Number.isFinite(val)) {
      const rounded = Math.round(Math.abs(val));
      const neg = val < 0 ? "-" : "";
      return `${neg}$${rounded.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
    }
    return String(val);
  }

  function parseVolUsd(raw) {
    if (raw == null || raw === "" || raw === "N/A") return null;
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  }

  /**
   * @param {object[]} coins
   * @returns {{ coin: object, exchangeId: string | null, volUsd: number | null }[]}
   */
  function explodeCoinRowsForTable(coins) {
    const out = [];
    for (const c of coins) {
      if (!c) continue;
      if (c._watchlist_only) {
        out.push({ coin: c, exchangeId: null, volUsd: null });
        continue;
      }
      const ev = c.exchange_volumes && typeof c.exchange_volumes === "object" ? c.exchange_volumes : {};
      const listedRaw = Array.isArray(c.listed_on) ? c.listed_on : [];
      const listed = listedRaw.map((x) => String(x || "").trim().toLowerCase()).filter(Boolean);
      const fromVol = Object.keys(ev)
        .map((k) => String(k || "").trim().toLowerCase())
        .filter(Boolean);
      const keysSource = listed.length ? listed : fromVol;
      const uniq = [...new Set(keysSource.filter((k) => TARGET_EXCHANGE_IDS.has(k)))].sort();
      if (!uniq.length) {
        out.push({ coin: c, exchangeId: null, volUsd: null });
      } else {
        for (const ex of uniq) {
          out.push({ coin: c, exchangeId: ex, volUsd: parseVolUsd(ev[ex]) });
        }
      }
    }
    return out;
  }

  function applyFiltersToViewRows(viewRows) {
    let rows = viewRows.slice();
    if (filterHealthMin != null) {
      rows = rows.filter((r) => {
        if (r.coin._watchlist_only) return true;
        const h = coinHealth(r.coin);
        return h != null && h >= filterHealthMin;
      });
    }
    if (filterUniformityMin != null) {
      rows = rows.filter((r) => {
        if (r.coin._watchlist_only) return true;
        const u = coinUniformity(r.coin);
        return u != null && u >= filterUniformityMin;
      });
    }
    if (filterVolAccel) {
      rows = rows.filter((r) => {
        if (r.coin._watchlist_only) return true;
        const v = coinVolAccelPct(r.coin);
        if (v == null) return false;
        if (filterVolAccel === "pos") return v > 0;
        const n = Number(filterVolAccel);
        return Number.isFinite(n) && v >= n;
      });
    }
    if (filterVolMinUsd != null) {
      rows = rows.filter((r) => {
        if (r.coin._watchlist_only) return true;
        return r.volUsd != null && Number.isFinite(r.volUsd) && r.volUsd >= filterVolMinUsd;
      });
    }
    if (filterExchangeSet.size > 0) {
      rows = rows.filter((r) => {
        if (r.coin._watchlist_only) return true;
        if (!r.exchangeId) return false;
        return filterExchangeSet.has(r.exchangeId);
      });
    }
    if (filterChartDistMax7 != null) {
      const cap = filterChartDistMax7;
      rows = rows.filter((r) => {
        if (r.coin._watchlist_only) return true;
        const g7 = rowG7Hi(r);
        const bad = g7 != null && Number.isFinite(g7) && g7 >= cap;
        return !bad;
      });
    }
    if (filterChartDistMax30 != null) {
      const cap = filterChartDistMax30;
      rows = rows.filter((r) => {
        if (r.coin._watchlist_only) return true;
        const g30 = rowG30Hi(r);
        const bad = g30 != null && Number.isFinite(g30) && g30 >= cap;
        return !bad;
      });
    }
    return rows;
  }

  function closesPctFromHigh(closes) {
    if (!closes || closes.length < 2) return null;
    const max = Math.max(...closes);
    const last = closes[closes.length - 1];
    if (!(max > 0)) return null;
    return ((max - last) / max) * 100;
  }

  function rowG7Hi(r) {
    return closesPctFromHigh(effectiveSparklineCloses7d(r.coin));
  }

  function rowG30Hi(r) {
    return closesPctFromHigh(effectiveSparklineCloses(r.coin));
  }

  function cmpTieBreakRows(a, b) {
    const sa = String(a.coin.symbol || "").toUpperCase();
    const sb = String(b.coin.symbol || "").toUpperCase();
    const c1 = sa.localeCompare(sb);
    if (c1 !== 0) return c1;
    return String(a.exchangeId || "").localeCompare(String(b.exchangeId || ""));
  }

  function sortViewRowsInPlace(rows) {
    const mult = sortDir;
    rows.sort((a, b) => {
      const ca = a.coin;
      const cb = b.coin;
      let cmp = 0;
      switch (sortKey) {
        case "symbol": {
          cmp = String(ca.symbol || "")
            .toUpperCase()
            .localeCompare(String(cb.symbol || "").toUpperCase());
          break;
        }
        case "name": {
          const va = `${String(ca.name || "").toLowerCase()}|${String(a.exchangeId || "")}`;
          const vb = `${String(cb.name || "").toLowerCase()}|${String(b.exchangeId || "")}`;
          cmp = va.localeCompare(vb);
          break;
        }
        case "g7pct": {
          const na = coinG7(ca);
          const nb = coinG7(cb);
          cmp = (na != null ? na : -1e9) - (nb != null ? nb : -1e9);
          break;
        }
        case "g30pct": {
          const na = coinG30(ca);
          const nb = coinG30(cb);
          cmp = (na != null ? na : -1e9) - (nb != null ? nb : -1e9);
          break;
        }
        case "g7hi": {
          const fa = rowG7Hi(a);
          const fb = rowG7Hi(b);
          cmp = (fa != null ? fa : -1e9) - (fb != null ? fb : -1e9);
          break;
        }
        case "g30hi": {
          const fa = rowG30Hi(a);
          const fb = rowG30Hi(b);
          cmp = (fa != null ? fa : -1e9) - (fb != null ? fb : -1e9);
          break;
        }
        case "btbest": {
          const na = rowBestBacktestNetPct(a);
          const nb = rowBestBacktestNetPct(b);
          cmp = (na != null ? na : -1e9) - (nb != null ? nb : -1e9);
          break;
        }
        case "btvbh": {
          const na = rowBotVsBhPositiveGap(a);
          const nb = rowBotVsBhPositiveGap(b);
          cmp = (na != null ? na : -1e9) - (nb != null ? nb : -1e9);
          break;
        }
        case "volaccel": {
          const na = coinVolAccelPct(ca);
          const nb = coinVolAccelPct(cb);
          cmp = (na != null ? na : -1e9) - (nb != null ? nb : -1e9);
          break;
        }
        case "uniformity": {
          cmp =
            (typeof ca.uniformity_score === "number" ? ca.uniformity_score : -1e9) -
            (typeof cb.uniformity_score === "number" ? cb.uniformity_score : -1e9);
          break;
        }
        case "venue": {
          cmp = String(a.exchangeId || "").localeCompare(String(b.exchangeId || ""));
          break;
        }
        case "vol24h": {
          cmp =
            (a.volUsd != null && Number.isFinite(a.volUsd) ? a.volUsd : -1) -
            (b.volUsd != null && Number.isFinite(b.volUsd) ? b.volUsd : -1);
          break;
        }
        case "rvol7": {
          const na = coinRiskHv7(ca);
          const nb = coinRiskHv7(cb);
          cmp = (na != null ? na : -1e9) - (nb != null ? nb : -1e9);
          break;
        }
        case "mdd30": {
          const na = coinRiskMdd30(ca);
          const nb = coinRiskMdd30(cb);
          cmp = (na != null ? na : -1e9) - (nb != null ? nb : -1e9);
          break;
        }
        case "health":
        default: {
          const ha = coinHealth(ca);
          const hb = coinHealth(cb);
          cmp = (ha != null ? ha : -1e9) - (hb != null ? hb : -1e9);
          break;
        }
      }
      if (cmp !== 0) return mult * cmp;
      return cmpTieBreakRows(a, b);
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

  /** One table row per pinned `SYMBOL|venue` key (same shape as `explodeCoinRowsForTable`). */
  function getWatchlistViewRows() {
    if (!lastPayload) return [];
    const coins = Array.isArray(lastPayload.coins) ? lastPayload.coins : [];
    const bySym = new Map();
    for (const c of coins) {
      if (c && !c._watchlist_only) bySym.set(String(c.symbol || "").toUpperCase(), c);
    }
    const pinned = [...getPinnedRowKeySet()].sort((a, b) => a.localeCompare(b));
    return pinned.map((key) => {
      const { sym, ex } = parseRowPinKey(key);
      const hit = bySym.get(sym);
      if (hit) {
        const ev = hit.exchange_volumes && typeof hit.exchange_volumes === "object" ? hit.exchange_volumes : {};
        const exKey = ex || null;
        const volUsd = exKey ? parseVolUsd(ev[exKey]) : null;
        return { coin: hit, exchangeId: exKey, volUsd };
      }
      return {
        coin: {
          symbol: sym,
          name: "",
          gains: {},
          listed_on: ex ? [ex] : [],
          _watchlist_only: true,
        },
        exchangeId: ex || null,
        volUsd: null,
      };
    });
  }

  function getFilteredSortedViewRows() {
    if (!lastPayload) return [];
    const exploded =
      activeView === "watchlist"
        ? getWatchlistViewRows()
        : explodeCoinRowsForTable(Array.isArray(lastPayload.coins) ? lastPayload.coins : []);
    const filtered = applyFiltersToViewRows(exploded);
    const copy = filtered.slice();
    sortViewRowsInPlace(copy);
    return copy;
  }

  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function getSymbolFromUrl() {
    return "";
  }

  function applyHashHighlight() {
    window.clearTimeout(hashHighlightTimer);
    document.querySelectorAll("tr.coin-row.row-highlight").forEach((r) => r.classList.remove("row-highlight"));
    if (!elTbody) return;
    const want = getSymbolFromUrl();
    if (!want) return;
    const matches = [];
    elTbody.querySelectorAll("tr.coin-row").forEach((r) => {
      if ((r.getAttribute("data-symbol") || "").toUpperCase() === want) {
        r.classList.add("row-highlight");
        matches.push(r);
      }
    });
    if (!matches.length) return;
    matches[0].scrollIntoView({ block: "nearest", behavior: prefersReducedMotion() ? "auto" : "smooth" });
    hashHighlightTimer = window.setTimeout(() => {
      matches.forEach((r) => r.classList.remove("row-highlight"));
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

  function getSnapshotValidation(data) {
    const embedded = data && data.snapshot_validation && typeof data.snapshot_validation === "object"
      ? data.snapshot_validation
      : null;
    if (embedded) return embedded;
    const issues = [];
    if (!data || typeof data !== "object") issues.push("snapshot is not an object");
    if (!Array.isArray(data && data.coins)) issues.push("coins is not an array");
    const coins = Array.isArray(data && data.coins) ? data.coins : [];
    let nSym = 0;
    for (const c of coins) {
      if (c && String(c.symbol || "").trim()) nSym += 1;
    }
    if (coins.length > 0 && nSym < coins.length) issues.push("some coin rows lack symbol");
    const iso = data && data.updated_at ? String(data.updated_at) : "";
    if (!iso.trim()) issues.push("missing updated_at");
    else if (!isValidSnapshotTimeMs(Date.parse(iso))) issues.push("updated_at not a valid timestamp");
    const level = issues.length ? "warn" : "ok";
    return {
      schema_version: 1,
      ok: issues.length === 0,
      level,
      issues,
      stats: { coin_count: coins.length, coins_with_symbol: nSym },
    };
  }

  function updateSnapshotValidationBanner(data) {
    if (!elSnapshotValidationBanner) return;
    const v = getSnapshotValidation(data);
    const issues = Array.isArray(v.issues) ? v.issues : [];
    if (!issues.length && v.level === "ok") {
      elSnapshotValidationBanner.hidden = true;
      elSnapshotValidationBanner.textContent = "";
      elSnapshotValidationBanner.classList.remove("snapshot-validation-banner--warn", "snapshot-validation-banner--error");
      return;
    }
    elSnapshotValidationBanner.hidden = false;
    elSnapshotValidationBanner.classList.toggle("snapshot-validation-banner--error", v.level === "error");
    elSnapshotValidationBanner.classList.toggle("snapshot-validation-banner--warn", v.level === "warn");
    const head =
      v.level === "error" ? "Snapshot validation error: " : "Snapshot quality warning: ";
    elSnapshotValidationBanner.textContent = head + issues.join(" · ");
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
      const vq = s.vendor_quota && typeof s.vendor_quota === "object" ? s.vendor_quota : null;
      if (vq && vq.ok === true && Number(vq.limit) > 0) {
        line += ` · vendor credits ${Number(vq.used) || 0} / ${Number(vq.limit) || 0} (${String(vq.source || "API")})`;
      }
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

  function getCgCreditsStoredOrBaseline() {
    try {
      const raw = localStorage.getItem(LS_CG_CREDITS_USED);
      if (raw != null && raw !== "") {
        const n = Math.round(Number(raw));
        if (Number.isFinite(n)) {
          return Math.min(DASHBOARD_COINGECKO_DEMO_CREDITS_MONTHLY, Math.max(0, n));
        }
      }
    } catch {
      /* ignore */
    }
    return DASHBOARD_COINGECKO_DEMO_BASELINE;
  }

  /**
   * First snapshot seen: store baseline (3650) and freeze to that file’s updated_at (no add — baseline is current total).
   * Later snapshots with a new updated_at: add this scan’s CoinGecko HTTP count as estimated credits (1 HTTP ≈ 1 credit).
   */
  function syncCgCreditsForSnapshot(data, coingeckoHttpThisScan) {
    const iso = data && data.updated_at != null ? String(data.updated_at).trim() : "";
    if (!iso) return;
    const cap = DASHBOARD_COINGECKO_DEMO_CREDITS_MONTHLY;
    let lastIso = "";
    try {
      lastIso = localStorage.getItem(LS_CG_LAST_SNAP_ISO) || "";
    } catch {
      /* ignore */
    }
    const add = Math.max(0, Math.round(Number(coingeckoHttpThisScan)) || 0);
    if (lastIso === iso) return;
    const usedBefore = getCgCreditsStoredOrBaseline();
    if (lastIso === "") {
      try {
        localStorage.setItem(LS_CG_CREDITS_USED, String(Math.min(cap, usedBefore)));
        localStorage.setItem(LS_CG_LAST_SNAP_ISO, iso);
      } catch {
        /* ignore */
      }
      return;
    }
    const next = Math.min(cap, usedBefore + add);
    try {
      localStorage.setItem(LS_CG_CREDITS_USED, String(next));
      localStorage.setItem(LS_CG_LAST_SNAP_ISO, iso);
    } catch {
      /* ignore */
    }
  }

  function updateApiBudgetPanel(data) {
    if (!elApiBudgetPanelSettings) return;
    const setBudgetPanel = (hidden, html) => {
      elApiBudgetPanelSettings.hidden = hidden;
      elApiBudgetPanelSettings.innerHTML = html;
    };
    const panel = data.api_cost_panel;
    const intervalSec =
      typeof data.scan_interval_seconds === "number" && Number.isFinite(data.scan_interval_seconds)
        ? Math.max(60, data.scan_interval_seconds)
        : NOMINAL_SCAN_FALLBACK_SEC;
    if (!panel || !Array.isArray(panel.sources)) {
      setBudgetPanel(true, "");
      return;
    }
    const cgSourceForSync = panel.sources.find((s) => {
      const id = String(s.id || "").toLowerCase();
      const nm = String(s.name || "").toLowerCase();
      return id.includes("coingecko") || nm.includes("coingecko");
    });
    if (cgSourceForSync) {
      const rawN = Number(cgSourceForSync.this_scan_http);
      const nSync = Number.isFinite(rawN) ? Math.round(rawN) : 0;
      syncCgCreditsForSnapshot(data, nSync);
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
      const idLc = String(s.id || "").toLowerCase();
      const nameLc = String(s.name || "").toLowerCase();
      const isCg = idLc.includes("coingecko") || nameLc.includes("coingecko");
      const vq = s.vendor_quota && typeof s.vendor_quota === "object" ? s.vendor_quota : null;
      let vendorOk = Boolean(vq && vq.ok === true && Number(vq.limit) > 0);
      let vUsed = vendorOk ? Math.round(Number(vq.used) || 0) : 0;
      let vLim = vendorOk ? Math.round(Number(vq.limit) || 0) : 0;
      if (isCg) {
        vendorOk = true;
        vUsed = getCgCreditsStoredOrBaseline();
        vLim = DASHBOARD_COINGECKO_DEMO_CREDITS_MONTHLY;
      }
      const vPct = vendorOk && vLim > 0 ? (vUsed / vLim) * 100 : 0;
      let riskClass = "budget-meter--neutral";
      let riskText;
      let barPct = 0;
      let capLabel = "";
      let ariaMax = 0;
      let ariaNow = 0;
      let overCap = false;
      let progressAttrs = "";
      if (vendorOk) {
        barPct = Math.min(100, vPct);
        if (vPct >= 100) riskClass = "budget-meter--danger";
        else if (vPct >= 85) riskClass = "budget-meter--warn";
        else riskClass = "budget-meter--ok";
        if (isCg) {
          riskText = `CoinGecko Demo credits (running estimate in this browser): ${vUsed.toLocaleString()} / ${vLim.toLocaleString()} this billing month (${vPct.toFixed(1)}% used). Each new snapshot adds this scan’s HTTP total (${n}) as estimated credits (1 HTTP ≈ 1 credit). Rate limit reference: ${DASHBOARD_COINGECKO_DEMO_RPM} req/min.`;
          if (cap > 0 && Number.isFinite(cap)) {
            const perScanPct = (n / cap) * 100;
            const projectedPct = ((n * scansPerMonth) / cap) * 100;
            riskText += ` Configured HTTP cap projection: ~${projectedPct.toFixed(1)}% if every scan matches this load; this scan ${perScanPct.toFixed(2)}% of that cap (${n} / ${Math.round(cap)}).`;
          }
          capLabel = `${n} HTTP this scan · ${vUsed.toLocaleString()} / ${vLim.toLocaleString()} Demo credits (est.)`;
        } else {
          const src = vq && vq.source != null ? String(vq.source) : "vendor API";
          riskText = `Account credits (from ${src}): ${vUsed.toLocaleString()} / ${vLim.toLocaleString()} this billing month (${vPct.toFixed(2)}% of plan). This scan: ${n} HTTP.`;
          if (cap > 0 && Number.isFinite(cap)) {
            const perScanPct = (n / cap) * 100;
            const projectedPct = ((n * scansPerMonth) / cap) * 100;
            riskText += ` Configured HTTP cap projection: ~${projectedPct.toFixed(1)}% if every scan matches this load; this scan ${perScanPct.toFixed(2)}% of that cap (${n} / ${Math.round(cap)}).`;
          }
          capLabel = `${n} HTTP this scan · ${vUsed.toLocaleString()} / ${vLim.toLocaleString()} vendor credits`;
        }
        ariaMax = vLim;
        ariaNow = Math.min(vUsed, vLim);
        overCap = vUsed > vLim;
        progressAttrs = !overCap
          ? ` role="progressbar" aria-valuemin="0" aria-valuemax="${ariaMax}" aria-valuenow="${ariaNow}" aria-label="${escapeAttr(name)}: ${vUsed} of ${vLim} credits this month"`
          : ` role="img" aria-label="${escapeAttr(name)}: credits over plan (${vUsed} / ${vLim})"`;
      } else if (cap > 0 && Number.isFinite(cap)) {
        const perScanPct = (n / cap) * 100;
        barPct = Math.min(100, perScanPct);
        const projectedPct = ((n * scansPerMonth) / cap) * 100;
        if (projectedPct >= 100) riskClass = "budget-meter--danger";
        else if (projectedPct >= 70) riskClass = "budget-meter--warn";
        else riskClass = "budget-meter--ok";
        riskText = `Projected ~${projectedPct.toFixed(1)}% of monthly cap if every scan matches this load (~${scansPerMonth.toFixed(0)} scans/mo at ${intervalMin}m interval). This scan: ${perScanPct.toFixed(2)}% of cap (${n} / ${Math.round(cap)} HTTP).`;
        capLabel = `${n} HTTP this scan · monthly cap ${Math.round(cap)} HTTP`;
        ariaMax = Math.round(cap);
        overCap = ariaMax > 0 && n > ariaMax;
        ariaNow = ariaMax > 0 ? Math.min(n, ariaMax) : 0;
        progressAttrs = !overCap
          ? ` role="progressbar" aria-valuemin="0" aria-valuemax="${ariaMax}" aria-valuenow="${ariaNow}" aria-label="${escapeAttr(name)}: ${n} of ${ariaMax} HTTP this scan"`
          : ` role="img" aria-label="${escapeAttr(name)}: ${n} HTTP this scan, over monthly cap of ${ariaMax}"`;
      } else {
        const vErr = vq && vq.error != null ? String(vq.error) : "";
        riskText = vErr
          ? `Vendor quota not available (${vErr}). ${n} HTTP this scan (local metrics). Set SCAN_COST_PANEL_* caps or fix API keys to see a limit bar.`
          : `Configure monthly HTTP caps in the scanner (SCAN_COST_PANEL_*), or set COINGECKO_API_KEY / CMC_API_KEY so the worker can read vendor usage from /key endpoints. This scan: ${n} HTTP.`;
        capLabel = `${n} HTTP this scan · no vendor quota or monthly cap in snapshot`;
        progressAttrs = ` role="img" aria-label="${escapeAttr(name)}: ${n} HTTP this scan (no vendor quota or cap)"`;
      }
      const riskTitle = escapeAttr(riskText);

      const breakdown = Array.isArray(s.breakdown) ? s.breakdown : [];
      let breakdownHtml = "";
      if (breakdown.length && n > 0) {
        const rows = [];
        for (const b of breakdown) {
          const suf = escapeHtml(String(b.suffix || "?"));
          const c = Math.round(Number(b.count) || 0);
          const share = Math.min(100, (c / n) * 100);
          rows.push(
            `<li class="api-budget-br-row"><span class="api-budget-br-label" title="${escapeAttr(suf)}">${suf}</span><span class="api-budget-br-count">${c}</span><div class="api-budget-bar-track api-budget-bar-track--thin" title="${c} of ${n} HTTP this scan"><div class="api-budget-bar-fill api-budget-bar-fill--share" style="width:${share.toFixed(1)}%"></div></div></li>`,
          );
        }
        breakdownHtml = `<ul class="api-budget-breakdown">${rows.join("")}</ul>`;
      }

      const fillStyle =
        vendorOk || (cap > 0 && Number.isFinite(cap)) ? `width:${barPct.toFixed(2)}%` : "width:0%";
      const cgBarFill = `<div class="api-budget-bar-fill ${riskClass}" style="${fillStyle}"></div>`;
      const cgOnBar =
        isCg && vendorOk
          ? `<span class="api-budget-cg-onbar">${vUsed.toLocaleString()} / ${vLim.toLocaleString()} est. · ${vPct.toFixed(1)}%</span>`
          : "";
      const barTrackClass = isCg && vendorOk ? " api-budget-bar-track--cg" : "";
      let li = `<li class="api-budget-item"><div class="api-budget-rowhead"><strong>${name}</strong><span class="api-budget-meta">${escapeHtml(capLabel)}</span></div>`;
      li += `<div class="api-budget-bar-track${barTrackClass}"${progressAttrs}>${cgBarFill}${cgOnBar}</div>`;
      li += `<p class="api-budget-risk ${riskClass}" title="${riskTitle}">${escapeHtml(riskText)}</p>`;
      li += breakdownHtml;
      if (pricing) {
        li += `<a href="${escapeAttr(pricing)}" class="api-budget-link" rel="noopener noreferrer" target="_blank" title="Open vendor pricing page">Vendor pricing</a>`;
      }
      li += `</li>`;
      items.push(li);
    }
    if (!items.length) {
      setBudgetPanel(true, "");
      return;
    }
    const note =
      panel.note != null && String(panel.note).trim()
        ? `<p class="api-budget-note">${escapeHtml(String(panel.note))}</p>`
        : "";
    const inner = `<h2 class="api-budget-heading" title="Per-vendor HTTP counts this scan and projected share of monthly caps">API usage &amp; budget</h2>${note}<ul class="api-budget-list" title="Hover each line for budget risk details">${items.join("")}</ul>`;
    setBudgetPanel(false, inner);
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

  function pruneOpsFeedToRetention() {
    const cutoff = Date.now() - OPS_LOG_RETENTION_MS;
    const before = opsFeedItems.length;
    opsFeedItems = opsFeedItems.filter((it) => it.t >= cutoff);
    if (opsFeedItems.length !== before) schedulePersistOpsFeed();
  }

  function schedulePersistOpsFeed() {
    if (opsFeedPersistTimer) window.clearTimeout(opsFeedPersistTimer);
    opsFeedPersistTimer = window.setTimeout(() => {
      opsFeedPersistTimer = 0;
      try {
        pruneOpsFeedToRetention();
        const serial = opsFeedItems.map((it) => ({
          t: it.t,
          iso: it.iso,
          html: it.html,
          k: typeof it.k === "string" ? it.k : "",
        }));
        localStorage.setItem(LS_OPS_FEED_STORE, JSON.stringify(serial));
      } catch (e) {
        console.warn("persist ops feed", e);
      }
    }, 400);
  }

  function loadOpsFeedFromStorage() {
    try {
      const raw = localStorage.getItem(LS_OPS_FEED_STORE);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return;
      const now = Date.now();
      const cutoff = now - OPS_LOG_RETENTION_MS;
      const next = [];
      for (const row of parsed) {
        if (!row || typeof row !== "object") continue;
        const t = Number(row.t);
        const iso = row.iso != null ? String(row.iso) : "—";
        const html = row.html != null ? String(row.html) : "";
        const k = row.k != null ? String(row.k) : "";
        if (!Number.isFinite(t) || t < cutoff) continue;
        if (!html.trim()) continue;
        next.push({ t, iso, html, k: k || undefined });
        if (k) opsFeedDedupe.add(k);
      }
      next.sort((a, b) => b.t - a.t);
      opsFeedItems = next.slice(0, 200);
      opsFeedDedupe.clear();
      for (const it of opsFeedItems) {
        if (it.k) opsFeedDedupe.add(it.k);
      }
      renderOpsFeedList();
      syncOpsTabBadge();
    } catch (e) {
      console.warn("load ops feed", e);
    }
  }

  function renderOpsFeedList() {
    pruneOpsFeedToRetention();
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
    opsFeedItems.unshift({ t: Date.now(), iso: iso || "—", html: html, k: key });
    pruneOpsFeedToRetention();
    opsFeedItems = opsFeedItems.slice(0, 200);
    renderOpsFeedList();
    schedulePersistOpsFeed();
    if (activeView === "logs") setOpsLastAckToNow();
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
    if (!d && !w) return "";
    return `${d}\n---\n${w}`;
  }

  /** @returns {{ id: string, t: number, line: string }[]} */
  function readCoinAlertFeed() {
    try {
      const raw = localStorage.getItem(LS_COIN_ALERT_FEED_JSON);
      if (!raw) return [];
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return [];
      return arr
        .filter((x) => x && typeof x.id === "string" && typeof x.line === "string")
        .map((x) => ({ id: x.id, t: Number(x.t) || 0, line: x.line }));
    } catch {
      return [];
    }
  }

  /** @param {{ id: string, t: number, line: string }[]} items */
  function writeCoinAlertFeed(items) {
    try {
      const trimmed = items.slice(-COIN_ALERT_FEED_MAX);
      localStorage.setItem(LS_COIN_ALERT_FEED_JSON, JSON.stringify(trimmed));
    } catch (e) {
      console.warn("coin alert feed", e);
    }
  }

  function removeCoinAlertById(id) {
    const want = String(id || "");
    if (!want) return;
    writeCoinAlertFeed(readCoinAlertFeed().filter((x) => x.id !== want));
  }

  function clearCoinAlertFeed() {
    try {
      localStorage.removeItem(LS_COIN_ALERT_FEED_JSON);
    } catch (e) {
      console.warn("coin alert feed clear", e);
    }
  }

  /** @param {object} data snapshot payload */
  function qualificationExitReasonMap(data) {
    const m = new Map();
    const arr = data && Array.isArray(data.qualification_exits) ? data.qualification_exits : [];
    for (const row of arr) {
      if (!row || typeof row !== "object") continue;
      const sym = String(row.symbol || "").toUpperCase().trim();
      const reason = String(row.exit_reason || "").trim();
      if (sym && reason) m.set(sym, reason);
    }
    return m;
  }

  /**
   * Append one in-app line per symbol when the qualified set changes (not the first baseline load).
   * @param {string[]} added
   * @param {string[]} dropped
   * @param {boolean} isFirstBaseline
   * @param {Map<string, string>} exitReasonBySym from payload qualification_exits (this scan only)
   * @returns {{ enters: string[], exits: string[] }} symbols newly written to the feed (for OS alerts)
   */
  function appendQualifiedListNotifications(added, dropped, isFirstBaseline, exitReasonBySym) {
    if (isFirstBaseline) return { enters: [], exits: [] };
    if (!added.length && !dropped.length) return { enters: [], exits: [] };
    const snapIso = lastPayload && lastPayload.updated_at ? String(lastPayload.updated_at) : "";
    const reasons = exitReasonBySym instanceof Map ? exitReasonBySym : new Map();
    const cur = readCoinAlertFeed();
    const have = new Set(cur.map((x) => x.id));
    const now = Date.now();
    const next = [...cur];
    const enters = [];
    const exits = [];
    for (const sym of added) {
      const s = String(sym || "").toUpperCase();
      if (!s) continue;
      const id = `enter|${snapIso}|${s}`;
      if (!have.has(id)) {
        next.push({ id, t: now, line: `Entered: ${s}` });
        have.add(id);
        enters.push(s);
      }
    }
    for (const sym of dropped) {
      const s = String(sym || "").toUpperCase();
      if (!s) continue;
      const id = `exit|${snapIso}|${s}`;
      if (!have.has(id)) {
        const why = reasons.get(s);
        const line = why ? `Left: ${s} — ${why}` : `Left: ${s}`;
        next.push({ id, t: now, line });
        have.add(id);
        exits.push(s);
      }
    }
    if (enters.length || exits.length) {
      writeCoinAlertFeed(next);
    }
    return { enters, exits };
  }

  /** @param {{ id: string, t: number, line: string }} it */
  function coinAlertItemTimeMs(it) {
    const n = Number(it.t);
    if (Number.isFinite(n) && n > 0) return n;
    const m = String(it.id || "").match(/^(?:enter|exit)\|([^|]+)\|/);
    if (m && m[1]) {
      const parsed = Date.parse(m[1]);
      if (Number.isFinite(parsed) && isValidSnapshotTimeMs(parsed)) return parsed;
    }
    return 0;
  }

  function formatCoinAlertListTime(ms) {
    if (!Number.isFinite(ms) || ms <= 0) return "";
    const d = new Date(ms);
    const sameYear = d.getFullYear() === new Date().getFullYear();
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      ...(sameYear ? {} : { year: "numeric" }),
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  function renderCoinAlertsList() {
    const ul = document.getElementById("coinAlertsFeedList");
    const emptyEl = document.getElementById("coinAlertsFeedEmpty");
    const dismissAllBtn = document.getElementById("coinAlertsDismissAll");
    if (!ul) return;
    const items = readCoinAlertFeed();
    ul.innerHTML = "";
    if (emptyEl) {
      emptyEl.hidden = items.length > 0;
    }
    if (dismissAllBtn) {
      dismissAllBtn.hidden = items.length === 0;
    }
    const newestFirst = items.slice().reverse();
    for (const it of newestFirst) {
      const li = document.createElement("li");
      li.className = "coin-alerts-feed-item";
      const tMs = coinAlertItemTimeMs(it);
      const timeStr = formatCoinAlertListTime(tMs);
      if (timeStr) {
        const timeEl = document.createElement("time");
        timeEl.className = "coin-alerts-feed-time";
        timeEl.dateTime = new Date(tMs).toISOString();
        timeEl.textContent = timeStr;
        timeEl.title = new Date(tMs).toLocaleString();
        li.appendChild(timeEl);
      }
      const span = document.createElement("span");
      span.className = "coin-alerts-feed-text";
      span.textContent = it.line;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "coin-alerts-feed-dismiss";
      btn.setAttribute("aria-label", "Dismiss this notification");
      btn.setAttribute("data-coin-alert-dismiss", it.id);
      btn.textContent = "×";
      li.appendChild(span);
      li.appendChild(btn);
      ul.appendChild(li);
    }
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
    const drawerOpen = elCoinAlertsPopover && !elCoinAlertsPopover.hidden;
    const feedN = readCoinAlertFeed().length;
    const bannerUnread = dig !== "" && dig !== ack;
    const show = !drawerOpen && (feedN > 0 || bannerUnread);
    elCoinAlertsBadge.hidden = !show;
    if (!show) {
      elCoinAlertsBadge.textContent = "";
      return;
    }
    if (feedN > 0) {
      elCoinAlertsBadge.textContent = feedN > 9 ? "9+" : String(feedN);
    } else {
      elCoinAlertsBadge.textContent = "!";
    }
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

  /** Snapshot `closes_1h`: 1h closes oldest→newest (scanner attaches up to 30d of bars). */
  const SPARKLINE_1H_BARS_7D = 7 * 24;
  const SPARKLINE_1H_BARS_30D = 30 * 24;

  function hourlyClosesNumeric(c) {
    const h1 = c.closes_1h;
    if (!Array.isArray(h1) || h1.length < 2) return null;
    const nums = h1.map((x) => Number(x)).filter((x) => Number.isFinite(x));
    return nums.length >= 2 ? nums : null;
  }

  /** Last 7 full days of hourly closes only; omit chart if fewer than 168 bars (no 30d slice). */
  function effectiveSparklineCloses7d(c) {
    const nums = hourlyClosesNumeric(c);
    if (!nums || nums.length < SPARKLINE_1H_BARS_7D) return [];
    return nums.slice(-SPARKLINE_1H_BARS_7D);
  }

  /** Last 30 days of real hourly closes only (no synthetic). */
  function effectiveSparklineCloses(c) {
    const nums = hourlyClosesNumeric(c);
    if (!nums) return [];
    return nums.length > SPARKLINE_1H_BARS_30D ? nums.slice(-SPARKLINE_1H_BARS_30D) : nums.slice();
  }

  /** @returns {{ svgHtml: string, pctFromHigh: number | null } | null} */
  function sparklineMarkup(closes, w, h) {
    if (!closes || closes.length < 2) return null;
    const pctFromHigh = closesPctFromHigh(closes);
    const min = Math.min(...closes);
    const max = Math.max(...closes);
    const pad = 2;
    const iw = w - pad * 2;
    const ih = h - pad * 2;
    const strokeW = closes.length > 200 ? 1 : closes.length > 48 ? 1.2 : 1.75;
    const normY = (v) => {
      if (!(max > min)) return pad + ih / 2;
      return pad + ih - ((v - min) / (max - min)) * ih;
    };
    const lastClose = closes[closes.length - 1];
    const yRef = normY(lastClose);
    const x2 = pad + iw;
    const yLow = normY(min);
    const yHigh = normY(max);
    const rangeFlat = !(max > min);
    const hiloLow = rangeFlat
      ? ""
      : `<line class="spark-hilo-line spark-hilo-low" x1="${pad}" y1="${yLow.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${yLow.toFixed(2)}" />`;
    const hiloHigh = rangeFlat
      ? ""
      : `<line class="spark-hilo-line spark-hilo-high" x1="${pad}" y1="${yHigh.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${yHigh.toFixed(2)}" />`;
    const refLine = `<line class="spark-ref-line" x1="${pad}" y1="${yRef.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${yRef.toFixed(2)}" />`;
    const pts = closes.map((v, i) => {
      const x = pad + (i / (closes.length - 1)) * iw;
      const y = normY(v);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    });
    const svgHtml = `<svg class="spark-svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">${hiloLow}${hiloHigh}<polyline class="spark-line-main" fill="none" stroke-width="${strokeW}" vector-effect="non-scaling-stroke" points="${pts.join(" ")}" />${refLine}</svg><span class="visually-hidden">Price trend; white lines are window low and high; orange is last close</span>`;
    return { svgHtml, pctFromHigh };
  }

  function formatChartPrice(v) {
    if (!Number.isFinite(v)) return "—";
    const a = Math.abs(v);
    if (a >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
    if (a >= 1) return v.toFixed(4);
    if (a >= 0.0001) return v.toFixed(6);
    return v.toExponential(3);
  }

  function escapeSvgText(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  /**
   * Fullscreen modal chart: area + grid + Y labels (distinct from the table sparkline).
   * @param {number[]} closes
   * @param {"7" | "30"} kind
   */
  function buildFullscreenChartSvg(closes, kind) {
    const is30 = kind === "30";
    if (!closes || closes.length < 2) return { svgHtml: "", statsHtml: "" };
    const W = 960;
    const H = 440;
    const padL = 58;
    const padR = 16;
    const padT = 32;
    const padB = 50;
    const cw = W - padL - padR;
    const ch = H - padT - padB;
    const min = Math.min(...closes);
    const max = Math.max(...closes);
    const last = closes[closes.length - 1];
    const pctFromHigh = closesPctFromHigh(closes);
    const pctStr =
      pctFromHigh != null && Number.isFinite(pctFromHigh) ? `${pctFromHigh.toFixed(2)}% below window high` : "—";
    const normY = (v) => {
      if (!(max > min)) return padT + ch / 2;
      return padT + ch - ((v - min) / (max - min)) * ch;
    };
    const lastX = padL + cw;
    const yBot = padT + ch;
    let d = `M ${padL} ${yBot}`;
    for (let i = 0; i < closes.length; i += 1) {
      const x = padL + (i / (closes.length - 1)) * cw;
      const y = normY(closes[i]);
      d += ` L ${x.toFixed(2)} ${y.toFixed(2)}`;
    }
    d += ` L ${lastX.toFixed(2)} ${yBot} Z`;
    const polyPts = closes
      .map((v, i) => {
        const x = padL + (i / (closes.length - 1)) * cw;
        return `${x.toFixed(2)},${normY(v).toFixed(2)}`;
      })
      .join(" ");
    const gradId = is30 ? "chartFsGrad30" : "chartFsGrad7";
    const gHi = is30 ? "#8b5cf6" : "#0ea5e9";
    let grid = "";
    for (let g = 0; g <= 4; g += 1) {
      const yy = padT + (ch * g) / 4;
      grid += `<line class="chart-fs-grid" x1="${padL}" y1="${yy.toFixed(2)}" x2="${lastX.toFixed(2)}" y2="${yy.toFixed(2)}" />`;
    }
    const yLabels = [0, 0.25, 0.5, 0.75, 1]
      .map((t) => {
        const val = min + (max - min) * (1 - t);
        const yy = padT + ch * t;
        return `<text class="chart-fs-ylab" x="${padL - 8}" y="${(yy + 4).toFixed(2)}" text-anchor="end">${escapeSvgText(formatChartPrice(val))}</text>`;
      })
      .join("");
    const svgClass = is30 ? "chart-fs-svg chart-fs-svg--30d" : "chart-fs-svg chart-fs-svg--7d";
    const capMid = (padL + lastX) / 2;
    const sub = is30
      ? "30-day window · up to 720 hourly closes (closes_1h)"
      : "7-day window · 168 hourly closes (closes_1h)";
    const yLast = normY(last);
    const labelTop = is30 ? "Older ← 30d hourly → Newer" : "Older ← 7d hourly → Newer";
    const aria = is30 ? "Thirty-day hourly close price chart" : "Seven-day hourly close price chart";
    const svgHtml = `<svg class="${svgClass}" viewBox="0 0 ${W} ${H}" width="100%" height="auto" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${escapeAttr(aria)}">
  <defs>
    <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${gHi}" stop-opacity="0.4" />
      <stop offset="100%" stop-color="${gHi}" stop-opacity="0.04" />
    </linearGradient>
  </defs>
  ${grid}
  <path class="chart-fs-area" d="${d}" fill="url(#${gradId})" />
  <polyline class="chart-fs-line" fill="none" stroke-width="2.4" vector-effect="non-scaling-stroke" points="${polyPts}" />
  <line class="chart-fs-ref-last" x1="${padL}" y1="${yLast.toFixed(2)}" x2="${lastX.toFixed(2)}" y2="${yLast.toFixed(2)}" />
  ${yLabels}
  <text class="chart-fs-caption chart-fs-caption--top" x="${capMid.toFixed(2)}" y="20" text-anchor="middle">${escapeSvgText(labelTop)}</text>
  <text class="chart-fs-caption" x="${padL}" y="${H - 12}" text-anchor="start">${escapeSvgText(`${sub} · ${closes.length} bars`)}</text>
</svg>`;
    const statsHtml = `<dl class="chart-fs-dl">
    <div><dt>Last close</dt><dd>${escapeHtml(formatChartPrice(last))}</dd></div>
    <div><dt>Window high</dt><dd>${escapeHtml(formatChartPrice(max))}</dd></div>
    <div><dt>Window low</dt><dd>${escapeHtml(formatChartPrice(min))}</dd></div>
    <div><dt>Below high</dt><dd>${escapeHtml(pctStr)}</dd></div>
  </dl>`;
    return { svgHtml, statsHtml };
  }

  function openSparkFullscreen(coin, kind) {
    const is30 = kind === "30";
    const closes = is30 ? effectiveSparklineCloses(coin) : effectiveSparklineCloses7d(coin);
    if (!closes || closes.length < 2) return;
    const sym = String(coin.symbol || "").toUpperCase();
    const name = String(coin.name || "").trim();
    if (elChartFsTitle) elChartFsTitle.textContent = name ? `${sym} · ${name}` : sym;
    const { svgHtml, statsHtml } = buildFullscreenChartSvg(closes, kind);
    if (elChartFsSvg) elChartFsSvg.innerHTML = svgHtml;
    if (elChartFsStats) elChartFsStats.innerHTML = statsHtml;
    if (elChartFsDialog && typeof elChartFsDialog.showModal === "function") elChartFsDialog.showModal();
  }

  /** @param {"7" | "30"} chartKind */
  function sparklineChartCellHtml(closes, w, h, chartKind) {
    const m = sparklineMarkup(closes, w, h);
    if (!m) return '<span class="cell-muted">—</span>';
    const pctStr =
      m.pctFromHigh != null && Number.isFinite(m.pctFromHigh) ? `${m.pctFromHigh.toFixed(1)}%` : "—";
    const t = escapeAttr(
      "% distance of last close below the window high (closes_1h). Lower = closer to the high.",
    );
    const fsHint =
      chartKind === "30"
        ? "Open full-screen 30-day hourly chart (area plot)"
        : "Open full-screen 7-day hourly chart (area plot)";
    return `<div class="spark-cell" title="${t}"><button type="button" class="spark-fs-btn" data-spark-kind="${chartKind}" aria-label="${escapeAttr(fsHint)}" title="${escapeAttr(fsHint)}"><span class="spark-cell-chart">${m.svgHtml}</span><span class="spark-from-high">${pctStr}</span></button></div>`;
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

  /** Omitted from Backtest Results strategy table (TP columns; TSL shown as trailing_stop_loss_pct). */
  const BACKTEST_SHEET_EXCLUDED_KEYS = new Set([
    "symbol",
    "take_profit_pct",
    "trailing_stop_pct",
    "trailing_take_profit_pct",
    "skipped_combos",
  ]);

  /** Always shown in strategy comparison table even when absent from row keys. */
  const BACKTEST_FORCED_COLUMNS = new Set(["trailing_stop_loss_pct", "tsl_hit_pct"]);

  const BACKTEST_COLUMN_PRIORITY = [
    "indicator",
    "strategy",
    "timeframe",
    "params",
    "trailing_stop_loss_pct",
    "net_pct",
    "win_pct",
    "trades",
    "tsl_hits",
    "tsl_hit_pct",
    "final_equity",
    "rank",
    "combos_evaluated",
    "stops_tested",
    "total_runs",
  ];

  function backtestSheetHeaderLabel(key) {
    const labels = {
      indicator: "Indicator",
      strategy: "Strategy",
      timeframe: "Timeframe",
      params: "Params",
      trailing_stop_loss_pct: "TSL %",
      net_pct: "Net %",
      win_pct: "Win %",
      trades: "Trades",
      tsl_hits: "TSL hits",
      tsl_hit_pct: "TSL hit %",
      final_equity: "Equity",
      rank: "Rank",
      combos_evaluated: "Combos evaluated",
      stops_tested: "Stops tested",
      total_runs: "Total runs",
    };
    return labels[key] || key;
  }

  /** @param {string} columnKey */
  function formatBacktestSheetCell(columnKey, val) {
    if (columnKey === "final_equity") {
      if (typeof val === "number" && Number.isFinite(val)) {
        const neg = val < 0 ? "-" : "";
        const abs = Math.abs(val);
        return `${neg}$${abs.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      }
      return fmtSheetCell(val);
    }
    if (columnKey === "net_pct" || columnKey === "win_pct" || columnKey === "trailing_stop_loss_pct") {
      if (typeof val === "number" && Number.isFinite(val)) return `${val.toFixed(1)}%`;
      const n = Number(val);
      if (Number.isFinite(n)) return `${n.toFixed(1)}%`;
      return fmtSheetCell(val);
    }
    return fmtSheetCell(val);
  }

  function backtestRowIsBuyHold(r) {
    return String(r.indicator || "").trim() === "B&H";
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
    const keySet = new Set();
    for (const r of rows) {
      if (r && typeof r === "object") {
        for (const k of Object.keys(r)) {
          if (!BACKTEST_SHEET_EXCLUDED_KEYS.has(k)) keySet.add(k);
        }
      }
    }
    const allKeys = [...keySet];
    const useKeys = [
      ...BACKTEST_COLUMN_PRIORITY.filter((k) => allKeys.includes(k) || BACKTEST_FORCED_COLUMNS.has(k)),
      ...allKeys.filter((k) => !BACKTEST_COLUMN_PRIORITY.includes(k) && !BACKTEST_FORCED_COLUMNS.has(k)).sort(),
    ];
    if (!useKeys.length) return '<p class="detail-muted">No columns.</p>';
    const th = useKeys
      .map(
        (k) =>
          `<th scope="col" title="${escapeAttr(`Backtest field: ${k}`)}">${escapeHtml(backtestSheetHeaderLabel(k))}</th>`,
      )
      .join("");
    const tb = rows
      .map((r) => {
        if (!r || typeof r !== "object") return "";
        const cells = useKeys
          .map((k) => {
            if (k === "indicator") {
              const ind = String(r.indicator ?? "");
              const inner = backtestRowIsBuyHold(r)
                ? `<span class="sheet-bh-name">${escapeHtml(ind)}</span>`
                : escapeHtml(ind || "—");
              return `<td>${inner}</td>`;
            }
            if (k === "trailing_stop_loss_pct") {
              const tsl = backtestRowTslPct(r);
              const text = tsl != null ? formatBacktestTslLabel(tsl) : "—";
              return `<td>${escapeHtml(text)}</td>`;
            }
            if (k === "tsl_hit_pct") {
              return `<td>${escapeHtml(formatBacktestTslHitLabel(backtestRowTslHitPct(r)))}</td>`;
            }
            return `<td>${escapeHtml(formatBacktestSheetCell(k, r[k]))}</td>`;
          })
          .join("");
        return `<tr>${cells}</tr>`;
      })
      .join("");
    return `<table class="sheet-table sheet-table--strategy"><thead><tr>${th}</tr></thead><tbody>${tb}</tbody></table>`;
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

  const COL_COUNT = 17;

  function syncCompareUi() {
    if (!elCompareBar || !elCompareBarLabel) return;
    const n = comparePickKeys.length;
    if (n === 0) {
      elCompareBar.hidden = true;
      elCompareBarLabel.textContent = "";
      return;
    }
    elCompareBar.hidden = false;
    const labels = comparePickKeys.map((pk) => rowPinKeyDisplayLabel(pk));
    elCompareBarLabel.textContent =
      n === 1 ? `Compare: ${labels[0]} (pick one more row)` : `Compare: ${labels[0]} vs ${labels[1]}`;
    if (elCompareOpenBtn) elCompareOpenBtn.disabled = n < 2;
  }

  function toggleComparePick(pk, checked) {
    const key = String(pk || "");
    if (!key) return;
    if (checked) {
      const next = comparePickKeys.filter((k) => k !== key);
      next.push(key);
      while (next.length > 2) next.shift();
      comparePickKeys = next;
    } else {
      comparePickKeys = comparePickKeys.filter((k) => k !== key);
    }
    syncCompareUi();
  }

  function clearComparePicks() {
    comparePickKeys = [];
    syncCompareUi();
    applyTableView();
  }

  function findViewRowByPinKey(pk) {
    const want = String(pk || "");
    if (!want) return null;
    const rows = getFilteredSortedViewRows();
    for (const r of rows) {
      if (rowViewPinKey(r) === want) return r;
    }
    return null;
  }

  function buildCompareColumnHtml(r) {
    const c = r.coin;
    const sym = String(c.symbol || "").toUpperCase();
    const name = String(c.name || "").trim();
    const g = c.gains || {};
    const g7 = typeof g["7d"] === "number" ? `${g["7d"].toFixed(1)}%` : "—";
    const g30 = typeof g["30d"] === "number" ? `${g["30d"].toFixed(1)}%` : "—";
    const hv = coinRiskHv7(c);
    const mdd = coinRiskMdd30(c);
    const h = coinHealth(c);
    const u = coinUniformity(c);
    const hi7 = rowG7Hi(r);
    const hi30 = rowG30Hi(r);
    const spark7 = effectiveSparklineCloses7d(c);
    const spark30 = effectiveSparklineCloses(c);
    const m7 = spark7 && spark7.length >= 2 ? sparklineMarkup(spark7, 200, 48) : null;
    const m30 = spark30 && spark30.length >= 2 ? sparklineMarkup(spark30, 200, 48) : null;
    const title = name ? `${sym} · ${name}` : sym;
    let dl = `<dl>
      <dt>7d %</dt><dd>${escapeHtml(g7)}</dd>
      <dt>30d %</dt><dd>${escapeHtml(g30)}</dd>
      <dt>HV 7d ann.</dt><dd>${hv != null ? escapeHtml(`${hv.toFixed(1)}%`) : "—"}</dd>
      <dt>Max DD 30d</dt><dd>${mdd != null ? escapeHtml(`${mdd.toFixed(1)}%`) : "—"}</dd>
      <dt>Health</dt><dd>${h != null ? escapeHtml(String(h.toFixed(1))) : "—"}</dd>
      <dt>Uniformity</dt><dd>${u != null ? escapeHtml(String(u.toFixed(1))) : "—"}</dd>
      <dt>% below high 7d</dt><dd>${hi7 != null ? escapeHtml(`${hi7.toFixed(1)}%`) : "—"}</dd>
      <dt>% below high 30d</dt><dd>${hi30 != null ? escapeHtml(`${hi30.toFixed(1)}%`) : "—"}</dd>
    </dl>`;
    let sparks = "";
    if (m7 && m7.svgHtml) {
      sparks += `<div class="compare-spark-wrap"><div class="spark-cell-inner" aria-hidden="true">${m7.svgHtml}</div><span class="cell-muted">7d</span></div>`;
    }
    if (m30 && m30.svgHtml) {
      sparks += `<div class="compare-spark-wrap"><div class="spark-cell-inner" aria-hidden="true">${m30.svgHtml}</div><span class="cell-muted">30d</span></div>`;
    }
    return `<div class="compare-col"><h3>${escapeHtml(title)}</h3>${dl}${sparks}</div>`;
  }

  function openCompareDialog() {
    if (!elCompareDialog || !elCompareDialogBody || comparePickKeys.length < 2) return;
    const a = findViewRowByPinKey(comparePickKeys[0]);
    const b = findViewRowByPinKey(comparePickKeys[1]);
    if (!a || !b) return;
    elCompareDialogBody.innerHTML = buildCompareColumnHtml(a) + buildCompareColumnHtml(b);
    if (typeof elCompareDialog.showModal === "function") elCompareDialog.showModal();
  }

  function renderRowsHtml(viewRows, pinnedSet, pinEnterSet, scoreRanges) {
    if (!viewRows.length) {
      let msg;
      if (activeView === "watchlist") {
        msg =
          getPinnedRowKeySet().size === 0
            ? "Your watchlist is empty. On the Qualified tab, click the star next to a symbol to add it here."
            : "No watchlist rows match the current filters.";
      } else {
        msg = "No qualified coins match the current filters.";
      }
      return `<tr><td colspan="${COL_COUNT}" class="empty">${escapeHtml(msg)}</td></tr>`;
    }
    return viewRows
      .map((r) => {
        const c = r.coin;
        const rawSym = String(c.symbol || "").toUpperCase();
        const watchOnly = c._watchlist_only === true;
        const dash = '<span class="cell-muted">\u2014</span>';
        if (watchOnly) {
          const pk = rowViewPinKey(r);
          const sym = escapeHtml(String(c.symbol || ""));
          const logoHtml = coinLogoImgHtml(c);
          const pinLab = rowPinKeyDisplayLabel(pk);
          const pinLabel = `Remove ${pinLab} from watchlist`;
          const pinBtn = `<button type="button" class="pin-btn" data-pin-key="${escapeAttr(pk)}" aria-pressed="true" aria-label="${escapeAttr(pinLabel)}" title="${escapeAttr(pinLabel)}">\u2605</button>`;
          const exchTitle = r.exchangeId ? EXCHANGE_LABELS[r.exchangeId] || r.exchangeId : "";
          const exLogoUrl = r.exchangeId ? exchangeLogoUrl(r.exchangeId) : "";
          const exLogo = exLogoUrl
            ? `<img class="exchange-logo" src="${escapeAttr(exLogoUrl)}" alt="" loading="lazy" decoding="async" onerror="this.style.display='none'" />`
            : "";
          const venueCell =
            r.exchangeId && exchTitle
              ? `<span class="venue-cell exchange-chip exchange-chip--${escapeAttr(r.exchangeId)}" title="${escapeAttr(`Watchlist pin for ${exchTitle}`)}">${exLogo}<span>${escapeHtml(exchTitle)}</span></span>`
              : dash;
          const exAttr = r.exchangeId ? escapeAttr(r.exchangeId) : "";
          const isPinEnter = pinEnterSet.has(pk);
          const wlRowClass = ["coin-row", "coin-row--watchlist-only"];
          if (isPinEnter) wlRowClass.push("coin-row--pin-enter");
          return `<tr class="${wlRowClass.join(" ")}" data-symbol="${escapeAttr(rawSym)}" data-exchange="${exAttr}">
          <td headers="col-symbol" class="sym-cell"><span class="sym-cell-inner" title="${escapeAttr(sym || "Unknown symbol")}">${pinBtn}${logoHtml}</span></td>
          <td headers="col-compare" class="compare-td">${dash}</td>
          <td headers="col-name"><span class="cell-muted" title="Symbol not in the current qualified snapshot">Not in snapshot</span></td>
          <td headers="col-g7pct" class="num">${dash}</td>
          <td headers="col-g7chart" class="num">${dash}</td>
          <td headers="col-g30pct" class="num">${dash}</td>
          <td headers="col-g30chart" class="num">${dash}</td>
          <td headers="col-btbest" class="num">${dash}</td>
          <td headers="col-btvbh" class="num">${dash}</td>
          <td headers="col-uniformity" class="num">${dash}</td>
          <td headers="col-health" class="num">${dash}</td>
          <td headers="col-rvol7" class="num">${dash}</td>
          <td headers="col-mdd30" class="num">${dash}</td>
          <td headers="col-volaccel" class="num">${dash}</td>
          <td headers="col-venue" class="exch-col">${venueCell}</td>
          <td headers="col-vol24h" class="num">${dash}</td>
          <td headers="col-backtest">${dash}</td>
        </tr>`;
        }
        const pk = rowViewPinKey(r);
        const isPinned = pinnedSet.has(pk);
        const isPinEnter = pinEnterSet.has(pk);
        const rowClasses = ["coin-row"];
        if (isPinned) rowClasses.push("coin-row--pinned");
        if (isPinEnter) rowClasses.push("coin-row--pin-enter");
        const sym = escapeHtml(String(c.symbol || ""));
        const nameRaw = String(c.name || "");
        const name = escapeHtml(nameRaw);
        const g = c.gains || {};
        const g7 = typeof g["7d"] === "number" ? g["7d"].toFixed(1) : "—";
        const g30pct = typeof g["30d"] === "number" ? g["30d"].toFixed(1) : "—";
        const hSeries = hourlyClosesNumeric(c);
        const nHour = hSeries ? hSeries.length : 0;
        const rawSpark7 = effectiveSparklineCloses7d(c);
        const rawSpark30 = effectiveSparklineCloses(c);
        const g7Title = !hSeries
          ? "7-day % from snapshot; no hourly closes_1h series in this snapshot for a chart"
          : nHour < SPARKLINE_1H_BARS_7D
            ? `7-day % from snapshot; 7d chart needs ${SPARKLINE_1H_BARS_7D} hourly closes (have ${nHour}) — chart hidden`
            : `7-day % from snapshot; sparkline plots last ${SPARKLINE_1H_BARS_7D} hourly closes (1h bars); orange line = last close in window`;
        const g30Title = !hSeries
          ? "30-day % from snapshot; no hourly closes_1h series in this snapshot for a chart"
          : nHour < SPARKLINE_1H_BARS_30D
            ? `30-day % from snapshot; sparkline plots ${rawSpark30.length} hourly closes on file (full month = ${SPARKLINE_1H_BARS_30D} bars); orange line = last close in window`
            : `30-day % from snapshot; sparkline plots last ${SPARKLINE_1H_BARS_30D} hourly closes (1h bars); orange line = last close in window`;
        const spark7Cell = sparklineChartCellHtml(rawSpark7, 168, 44, "7");
        const spark30Cell = sparklineChartCellHtml(rawSpark30, 168, 44, "30");
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
        const exchTitle = r.exchangeId ? EXCHANGE_LABELS[r.exchangeId] || r.exchangeId : "";
        const nameCore = listing
          ? `<a href="${escapeAttr(listing)}" class="coin-listing-link" rel="noopener noreferrer" target="_blank" data-symbol="${escapeAttr(rawSym)}" title="Open listing or reference page in a new tab">${name}</a>`
          : `<span title="Name from snapshot (no listing URL)">${name}</span>`;
        const symbolTag = sym ? `<span class="coin-token">${sym}</span>` : "";
        const logoHtml = coinLogoImgHtml(c);
        const nameCell = `<span class="name-col-wrap"><span class="coin-name-line">${nameCore}</span>${symbolTag}</span>`;
        const badge = lastAddedSet.has(rawSym)
          ? '<span class="badge badge-new" title="New since last visit">New</span>'
          : "";
        const pinLab = rowPinKeyDisplayLabel(pk);
        const pinLabel = isPinned ? `Remove ${pinLab} from watchlist` : `Add ${pinLab} to watchlist`;
        const pinChar = isPinned ? "\u2605" : "\u2606";
        const pinBtn = `<button type="button" class="pin-btn" data-pin-key="${escapeAttr(pk)}" aria-pressed="${isPinned ? "true" : "false"}" aria-label="${escapeAttr(pinLabel)}" title="${escapeAttr(pinLabel)}">${pinChar}</button>`;
        const exLogoUrl = r.exchangeId ? exchangeLogoUrl(r.exchangeId) : "";
        const exLogo = exLogoUrl
          ? `<img class="exchange-logo" src="${escapeAttr(exLogoUrl)}" alt="" loading="lazy" decoding="async" onerror="this.style.display='none'" />`
          : "";
        const venueCell =
          r.exchangeId && exchTitle
            ? `<span class="venue-cell exchange-chip exchange-chip--${escapeAttr(r.exchangeId)}" title="${escapeAttr(`24h volume row for ${exchTitle}`)}">${exLogo}<span>${escapeHtml(exchTitle)}</span></span>`
            : '<span class="cell-muted">—</span>';
        const volCell = `<span title="Approximate 24h USD volume on this venue from snapshot">${escapeHtml(formatUsdVolDisplay(r.volUsd))}</span>`;
        const btHtml = backtestCellHtml(c);
        const btBest = rowBestBacktestNetPct(r);
        const btWinner = rowBestBacktestWinnerRow(c);
        const btTsl = backtestRowTslPct(btWinner);
        const btBestText = btBest != null ? `${btBest >= 0 ? "+" : ""}${btBest.toFixed(1)}%` : "—";
        const btTslText = btTsl != null ? formatBacktestTslLabel(btTsl) : "";
        const btBestTitle =
          btTsl != null
            ? `Highest backtest net percent; winning trailing stop ${btTslText}`
            : "Highest backtest net percent";
        const gain7Class = g7 !== "—" && Number(g7) > 0 ? "gain-pos" : "";
        const gain30Class = g30pct !== "—" && Number(g30pct) > 0 ? "gain-pos" : "";
        const healthVal = coinHealth(c);
        const healthPct = healthVal != null ? pctInRange(healthVal, scoreRanges && scoreRanges.health) : null;
        const healthChip =
          healthVal != null && healthPct != null
            ? `<span class="health-chip"><span class="health-ring" style="--pct:${healthPct.toFixed(1)}"></span><span>${h}</span></span>`
            : `<span>${h}</span>`;
        const uniformVal = coinUniformity(c);
        const uniformPct = uniformVal != null ? pctInRange(uniformVal, scoreRanges && scoreRanges.uniformity) : null;
        const uniformChip =
          uniformVal != null && uniformPct != null
            ? `<span class="health-chip"><span class="health-ring health-ring--uniformity" style="--pct:${uniformPct.toFixed(1)}"></span><span>${u}</span></span>`
            : `<span>${u}</span>`;
        const btBestPctRaw = btBest != null ? pctInRange(btBest, scoreRanges && scoreRanges.btBest) : null;
        const btBestPct = btBestPctRaw == null ? 0 : btBestPctRaw;
        const btCellClass = `btbest-cell${btBest == null ? " btbest-cell--na" : ""}`;
        const btTextClass = btBest != null && btBestPct >= 56 ? "btbest-text--dark" : "btbest-text--light";
        const btBestStyle = ` style="--pct:${btBestPct.toFixed(1)}"`;
        const btvbhGap = rowBotVsBhPositiveGap(r);
        const btvbhTitle =
          "Best non–buy/hold strategy net % minus buy & hold (shown only when the strategy wins)";
        const btvbhCell =
          btvbhGap != null
            ? `<span class="gain-pos" title="${escapeAttr(btvbhTitle)}">+${btvbhGap.toFixed(1)}%</span>`
            : dash;
        const exAttr = r.exchangeId ? escapeAttr(r.exchangeId) : "";
        const hv = coinRiskHv7(c);
        const mdd = coinRiskMdd30(c);
        const hvStr = hv != null ? `${hv.toFixed(1)}%` : "—";
        const mddStr = mdd != null ? `${mdd.toFixed(1)}%` : "—";
        const hvTitle = "Annualized hist. vol. from ~7d hourly closes (snapshot risk_context)";
        const mddTitle = "Max peak-to-trough drawdown % over ~30d hourly closes";
        const cmpChecked = comparePickKeys.includes(pk);
        const compareCell = `<td headers="col-compare" class="compare-td"><input type="checkbox" class="compare-cb" data-compare-pk="${escapeAttr(pk)}" ${cmpChecked ? "checked" : ""} aria-label="Select ${escapeAttr(rowPinKeyDisplayLabel(pk))} for compare" title="Compare (max 2)" /></td>`;
        return `<tr class="${rowClasses.join(" ")}" data-symbol="${escapeAttr(rawSym)}" data-exchange="${exAttr}">
          <td headers="col-symbol" class="sym-cell"><span class="sym-cell-inner">${pinBtn}${logoHtml}${badge}</span></td>
          ${compareCell}
          <td headers="col-name" class="name-col">${nameCell}</td>
          <td headers="col-g7pct" class="num"><span class="visually-hidden">7-day gain </span><span class="${gain7Class}" title="${escapeAttr(g7Title)}">${g7}%</span></td>
          <td headers="col-g7chart" class="num spark-td" title="${escapeAttr(g7Title)}">${spark7Cell}</td>
          <td headers="col-g30pct" class="num"><span class="visually-hidden">30-day gain </span><span class="${gain30Class}" title="${escapeAttr(g30Title)}">${g30pct}%</span></td>
          <td headers="col-g30chart" class="num spark-td" title="${escapeAttr(g30Title)}">${spark30Cell}</td>
          <td headers="col-btbest" class="num ${btCellClass}"${btBestStyle}><span class="btbest-cell-inner"><span class="${btTextClass}" title="${escapeAttr(btBestTitle)}">${btBestText}</span>${btTslText ? `<span class="btbest-tsl" title="Winning trailing stop loss">${escapeHtml(btTslText)} TSL</span>` : ""}</span></td>
          <td headers="col-btvbh" class="num"><span class="visually-hidden">Bot vs buy and hold </span>${btvbhCell}</td>
          <td headers="col-uniformity" class="num"><span class="visually-hidden">Uniformity </span><span title="OHLCV uniformity score (higher = more consistent bar structure)">${uniformChip}</span></td>
          <td headers="col-health" class="num"><span class="visually-hidden">Health </span><span title="Composite health score from snapshot">${healthChip}</span></td>
          <td headers="col-rvol7" class="num" title="${escapeAttr(hvTitle)}">${escapeHtml(hvStr)}</td>
          <td headers="col-mdd30" class="num" title="${escapeAttr(mddTitle)}">${escapeHtml(mddStr)}</td>
          <td headers="col-volaccel" class="num"><span class="visually-hidden">Volume acceleration </span><span title="Volume vs baseline window from snapshot">${volStr}</span></td>
          <td headers="col-venue" class="exch-col">${venueCell}</td>
          <td headers="col-vol24h" class="num">${volCell}</td>
          <td headers="col-backtest">${btHtml}</td>
        </tr>`;
      })
      .join("");
  }

  function applyTableView() {
    if (!lastPayload) return;
    const filtered = getFilteredSortedViewRows();
    const pinned = getPinnedRowKeySet();
    const scoreRanges = computeScoreRanges(filtered);
    elTbody.innerHTML = renderRowsHtml(filtered, pinned, pinEnterFlashSet, scoreRanges);
    updateKpiStrip(filtered);
    updateSortHeaderClasses();
    syncCompareUi();
    if (pinEnterFlashSet.size > 0) {
      window.clearTimeout(pinEnterClearTimer);
      pinEnterClearTimer = window.setTimeout(() => {
        document.querySelectorAll("tr.coin-row--pin-enter").forEach((r) => r.classList.remove("coin-row--pin-enter"));
      }, 12000);
    }
  }

  function setSnapshotLoadingVisible(show) {
    if (!elSnapshotLoadingOverlay) return;
    elSnapshotLoadingOverlay.hidden = !show;
    elSnapshotLoadingOverlay.setAttribute("aria-busy", show ? "true" : "false");
  }

  function updateKpiStrip(viewRows) {
    if (!elKpiQualifiedCount) return;
    const rows = Array.isArray(viewRows) ? viewRows : [];
    const count = rows.filter((r) => !r.coin._watchlist_only).length;
    const exchangeCounts = { coinbase: 0, kraken: 0 };
    for (const r of rows) {
      if (r.coin && r.coin._watchlist_only) continue;
      if (r.exchangeId && Object.prototype.hasOwnProperty.call(exchangeCounts, r.exchangeId)) {
        exchangeCounts[r.exchangeId] += 1;
      }
    }
    elKpiQualifiedCount.textContent = count.toLocaleString("en-US");
    if (elKpiCoinbaseCount) elKpiCoinbaseCount.textContent = exchangeCounts.coinbase.toLocaleString("en-US");
    if (elKpiKrakenCount) elKpiKrakenCount.textContent = exchangeCounts.kraken.toLocaleString("en-US");
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
    const viewRows = getFilteredSortedViewRows();
    const header = [
      "symbol",
      "name",
      "row_exchange",
      "row_vol_24h_usd",
      "gain_7d_pct",
      "gain_30d_pct",
      "chart_7d_pct_below_high",
      "chart_30d_pct_below_high",
      "uniformity",
      "health",
      "hv_7d_annualized_pct",
      "max_drawdown_30d_pct",
      "volume_acceleration_pct",
      "volume_acceleration_window_days",
      "listed_on",
      "source_url",
    ];
    const lines = [header.join(",")];
    for (const r of viewRows) {
      const c = r.coin;
      const g = c.gains || {};
      const g7 = typeof g["7d"] === "number" ? g["7d"] : "";
      const g30 = typeof g["30d"] === "number" ? g["30d"] : "";
      const hi7 = rowG7Hi(r);
      const hi30 = rowG30Hi(r);
      const u = typeof c.uniformity_score === "number" ? c.uniformity_score : "";
      const h = c.health_score != null && c.health_score !== "" ? c.health_score : "";
      const hv = coinRiskHv7(c);
      const mdd = coinRiskMdd30(c);
      const vac = c.volume_acceleration_pct;
      const vwd = c.volume_acceleration_window_days;
      const lo = Array.isArray(c.listed_on) ? c.listed_on.join("|") : "";
      const url = c.source_url ? String(c.source_url) : "";
      const ex = r.exchangeId != null ? String(r.exchangeId) : "";
      const vol = r.volUsd != null && Number.isFinite(r.volUsd) ? r.volUsd : "";
      lines.push(
        [
          c.symbol,
          c.name,
          ex,
          vol,
          g7,
          g30,
          hi7 != null ? Number(hi7.toFixed(4)) : "",
          hi30 != null ? Number(hi30.toFixed(4)) : "",
          u,
          h,
          hv != null ? Number(hv.toFixed(4)) : "",
          mdd != null ? Number(mdd.toFixed(4)) : "",
          vac,
          vwd,
          lo,
          url,
        ]
          .map(escapeCsvCell)
          .join(","),
      );
    }
    const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    downloadBlob(`qualified_export_${stamp}.csv`, "text/csv;charset=utf-8", lines.join("\r\n"));
  }

  function exportViewJson() {
    const viewRows = getFilteredSortedViewRows();
    const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const coins = viewRows.map((r) => {
      const c = r.coin;
      if (c._watchlist_only) return { ...c };
      const hi7 = rowG7Hi(r);
      const hi30 = rowG30Hi(r);
      return {
        ...c,
        dashboard_row_exchange: r.exchangeId,
        dashboard_row_vol_24h_usd: r.volUsd,
        dashboard_chart_7d_pct_below_high: hi7 != null ? Number(hi7.toFixed(4)) : null,
        dashboard_chart_30d_pct_below_high: hi30 != null ? Number(hi30.toFixed(4)) : null,
      };
    });
    downloadBlob(
      `qualified_export_${stamp}.json`,
      "application/json;charset=utf-8",
      JSON.stringify({ exported_at: new Date().toISOString(), count: coins.length, coins }, null, 2),
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
    const nWatch = getPinnedRowKeySet().size;
    const watchHint = nWatch ? ` · ${nWatch} watched` : "";
    const snapExtra = snapshotMetaSuffix;
    snapshotMetaSuffix = "";
    elMeta.textContent = `Updated ${updatedHuman} (${updatedDisplay}) · field_set=${fieldSet} · ${coins.length} coin(s)${watchHint}${nextHint}${alertSuffix}${snapExtra}`;

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
          ? "No qualified coins in this snapshot — the BTC regime filter blocked all uniformity passes (see the Regime strip on the Logs tab). This is expected when `REGIME_FILTER_ENABLED` is on and BTC 7d/30d fails the gate."
          : snapshotLoadWasCommittedFallback
            ? "The live snapshot relay returned HTTP 503 (no snapshot file on the server yet), so this page loaded the committed repo file `docs/qualified_public_snapshot.json`, which currently has 0 coins. Fix: wait for the worker to POST after a scan, or run `python scripts/sync_snapshot_to_docs.py` after a local scan and deploy the updated JSON. Check Render snapshot service logs if 503 persists."
            : "This JSON has 0 coins. The file committed at `docs/qualified_public_snapshot.json` is a placeholder; live scans from the Render worker do not update GitHub automatically. Point this dashboard at your relay: set `window.__SNAPSHOT_URL__` in `docs/dashboard/config.js` to `https://<your-snapshot>.onrender.com/qualified_public_snapshot.json`, or add `?api=` with that URL. Alternatively run `python scripts/sync_snapshot_to_docs.py` after a scan and push the updated file.";
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
    const exitReasonBySym = qualificationExitReasonMap(data);
    const listNotifyDelta = appendQualifiedListNotifications(
      added,
      dropped,
      prevSyms.size === 0,
      exitReasonBySym,
    );
    renderCoinAlertsList();
    if (
      notifyAlertsEnabled &&
      tierANotifyScope() === "qualified" &&
      (listNotifyDelta.enters.length || listNotifyDelta.exits.length)
    ) {
      const stamp = String(updatedRaw || "snap").replace(/[^a-z0-9]+/gi, "").slice(0, 24);
      void (async () => {
        for (const sym of listNotifyDelta.enters) {
          await showDashboardNotification({
            title: `Entered: ${sym}`,
            body: `${sym} entered the qualified list.`,
            tag: `qfeed-ent-${sym}-${stamp}-${Date.now()}`.slice(0, 64),
            symbol: sym,
          });
        }
        for (const sym of listNotifyDelta.exits) {
          const why = exitReasonBySym.get(sym) || "";
          let body = why
            ? `${sym} left the qualified list. ${why}`
            : `${sym} left the qualified list.`;
          if (body.length > 240) body = `${body.slice(0, 236)}…`;
          await showDashboardNotification({
            title: `Left: ${sym}`,
            body,
            tag: `qfeed-out-${sym}-${stamp}-${Date.now()}`.slice(0, 64),
            symbol: sym,
          });
        }
      })();
    }
    updateStaleBanner(data);
    updateSnapshotValidationBanner(data);
    updateHealthStrip(data);
    updateRegimeStrip(data.regime_gate);
    void refreshRelayHealthStrip();

    syncSnapshotTelemetryPanel();
    scheduleOpsFeedSnapshotSummary(data);
    syncCoinBellBadge();

    applyTableView();
    updateWatchlistBadge();
    writeSnapshotVisitState(data);
    window.requestAnimationFrame(() => {
      refreshDashboardShellWidth();
    });
  }

  if (elTbody) {
    elTbody.addEventListener("change", (ev) => {
      const t = ev.target;
      if (t && t.classList && t.classList.contains("compare-cb")) {
        const pk = t.getAttribute("data-compare-pk") || "";
        toggleComparePick(pk, t.checked);
        applyTableView();
      }
    });
    elTbody.addEventListener("click", (ev) => {
      const pinBtn = ev.target.closest(".pin-btn");
      if (pinBtn) {
        ev.preventDefault();
        ev.stopPropagation();
        const pk = pinBtn.getAttribute("data-pin-key") || pinBtn.getAttribute("data-symbol") || "";
        togglePinRow(pk);
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
      const fsBtn = ev.target.closest(".spark-fs-btn");
      if (fsBtn) {
        ev.preventDefault();
        ev.stopPropagation();
        const kind = fsBtn.getAttribute("data-spark-kind") === "30" ? "30" : "7";
        const row = fsBtn.closest("tr.coin-row");
        const sym = row ? row.getAttribute("data-symbol") : "";
        if (!sym || !lastPayload) return;
        const pool = Array.isArray(lastPayload.coins) ? lastPayload.coins : [];
        const coin = pool.find((x) => String(x.symbol || "").toUpperCase() === sym.toUpperCase());
        if (coin) openSparkFullscreen(coin, kind);
      }
    });
  }

  if (elCompareOpenBtn) {
    elCompareOpenBtn.addEventListener("click", () => openCompareDialog());
  }
  if (elCompareClearBtn) {
    elCompareClearBtn.addEventListener("click", () => clearComparePicks());
  }
  if (elCompareDialogClose && elCompareDialog) {
    elCompareDialogClose.addEventListener("click", () => {
      if (typeof elCompareDialog.close === "function") elCompareDialog.close();
    });
  }

  async function digestHex(text) {
    if (window.crypto && crypto.subtle) {
      const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
      return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
    }
    return String(text.length) + ":" + text.slice(0, 2000);
  }

  function notificationAssetUrl(relPath) {
    try {
      return new URL(relPath, window.location.href).href;
    } catch {
      return relPath;
    }
  }

  /** System-level (service worker) notifications with absolute icon URLs for Android and desktop. */
  async function showDashboardNotification(opts) {
    const title = String(opts.title || "Qualified dashboard");
    const body = String(opts.body || "");
    const tag = opts.tag != null ? String(opts.tag) : "qualified-dash";
    const sym = String(opts.symbol || "").trim().toLowerCase();
    const iconBase = sym === "con" ? "con_win" : sym;
    const icon = sym
      ? notificationAssetUrl(`./icons/coins/${encodeURIComponent(iconBase)}.png`)
      : notificationAssetUrl("./icons/icon-192.png");
    const badge = notificationAssetUrl("./icons/icon-192.png");
    const options = {
      body,
      tag,
      renotify: true,
      icon,
      badge,
      vibrate: [180, 80, 180],
    };
    try {
      if ("serviceWorker" in navigator) {
        const reg = await navigator.serviceWorker.ready;
        if (reg && typeof reg.showNotification === "function") {
          await reg.showNotification(title, options);
          return;
        }
      }
      if (typeof Notification === "function" && Notification.permission === "granted") {
        new Notification(title, { body, tag, icon });
      }
    } catch (e) {
      console.warn("showNotification", e);
    }
  }

  /**
   * Tier-A alerts: only when the **filtered** list (health, **exchanges**, etc.) changes vs last poll — same
   * membership rule as the table (e.g. Kraken-only hides MEXC-only coins).
   * @returns {Promise<boolean>} true if a list-change notification was shown
   */
  async function notifySnapshotChangedFiltered(data, nextDigest) {
    if (tierANotifyScope() !== "qualified") return false;
    const coins = Array.isArray(data.coins) ? data.coins : [];
    const exploded = explodeCoinRowsForTable(coins);
    const filtered = applyFiltersToViewRows(exploded);
    const keys = filtered
      .map((row) => {
        const sym = String(row.coin.symbol || "").toUpperCase();
        if (!sym) return null;
        const ex = row.exchangeId || "";
        return `${sym}|${ex}`;
      })
      .filter(Boolean)
      .sort();
    const key = JSON.stringify(keys);
    try {
      localStorage.removeItem(LS_POLL_FILTERED_SYMS_LEGACY);
    } catch {
      /* ignore */
    }
    const prevFilteredRaw = localStorage.getItem(LS_POLL_FILTERED_ROWS);
    localStorage.setItem(LS_DIGEST, nextDigest);
    if (prevFilteredRaw === null || prevFilteredRaw === "") {
      localStorage.setItem(LS_POLL_FILTERED_ROWS, key);
      return false;
    }
    if (prevFilteredRaw === key) {
      return false;
    }
    localStorage.setItem(LS_POLL_FILTERED_ROWS, key);
    let prevArr = [];
    try {
      prevArr = JSON.parse(prevFilteredRaw);
    } catch {
      prevArr = [];
    }
    const prevSet = new Set(Array.isArray(prevArr) ? prevArr.map((s) => String(s)) : []);
    const curSet = new Set(keys);
    const added = keys.filter((s) => !prevSet.has(s));
    const removed = [...prevSet].filter((s) => !curSet.has(s)).sort();
    const exchHint =
      filterExchangeSet.size > 0
        ? ` · Listings: ${[...filterExchangeSet]
            .sort()
            .map((id) => EXCHANGE_LABELS[id] || id)
            .join(", ")}`
        : "";
    const rowKeyLabel = (k) => {
      const parts = String(k).split("|");
      if (parts.length < 2) return String(k);
      const sym = parts[0];
      const ex = parts[1] ? EXCHANGE_LABELS[parts[1]] || parts[1] : "";
      return ex ? `${sym} (${ex})` : sym;
    };
    const stamp = Date.now();
    for (let i = 0; i < added.length; i += 1) {
      const k = added[i];
      const sym = String(k).split("|")[0] || "";
      await showDashboardNotification({
        title: "Qualified list updated",
        body: `New in filtered view: ${rowKeyLabel(k)} (${keys.length} row(s)${exchHint})`,
        tag: `qf-new-${String(k).replace(/[^a-z0-9]+/gi, "").slice(0, 48)}-${stamp}-${i}`.slice(0, 64),
        symbol: sym,
      });
    }
    for (let i = 0; i < removed.length; i += 1) {
      const k = removed[i];
      const sym = String(k).split("|")[0] || "";
      await showDashboardNotification({
        title: "Qualified list updated",
        body: `Removed from filtered view: ${rowKeyLabel(k)} (${keys.length} row(s)${exchHint})`,
        tag: `qf-out-${String(k).replace(/[^a-z0-9]+/gi, "").slice(0, 48)}-${stamp}-${i}`.slice(0, 64),
        symbol: sym,
      });
    }
    return added.length > 0 || removed.length > 0;
  }

  /** Tier-A: notify when a watched symbol enters or leaves the full qualified set (independent of table filters). */
  async function notifyPinnedWatch(entered, left) {
    if (tierANotifyScope() !== "watchlist") return;
    if (!notifyAlertsEnabled || (!entered.length && !left.length)) return;
    const coins = Array.isArray(lastPayload?.coins) ? lastPayload.coins : [];
    const exploded = explodeCoinRowsForTable(coins);
    const filtered = applyFiltersToViewRows(exploded);
    const filteredSet = new Set(
      filtered.map((r) => String(r.coin.symbol || "").toUpperCase()).filter(Boolean),
    );
    const enteredFiltered = [
      ...new Set(
        entered.map((k) => parseRowPinKey(String(k || "")).sym).filter((s) => s && filteredSet.has(s)),
      ),
    ];
    const stamp = Date.now();
    let n = 0;
    for (const sym of enteredFiltered) {
      await showDashboardNotification({
        title: "Watch: entered qualified set",
        body: `${sym} entered the qualified list (matches your watch + filters).`,
        tag: `watch-in-${sym}-${stamp}-${n++}`.slice(0, 64),
        symbol: sym,
      });
    }
    for (const k of left) {
      const sym = parseRowPinKey(String(k || "")).sym || "";
      await showDashboardNotification({
        title: "Watch: left qualified set",
        body: `${rowPinKeyDisplayLabel(k)} left the qualified list.`,
        tag: `watch-out-${String(k).replace(/[^a-z0-9]+/gi, "").slice(0, 32)}-${stamp}-${n++}`.slice(0, 64),
        symbol: sym,
      });
    }
  }

  async function loadSnapshot(options) {
    const showErrors = options && options.showErrors;
    const forNotify = options && options.forNotify;
    const shouldShowLoading = !forNotify && !lastPayload;
    if (shouldShowLoading) setSnapshotLoadingVisible(true);
    const url = getSnapshotUrl();
    if (!url || !url.trim()) {
      if (showErrors) {
        showError("Set a snapshot JSON URL (?api=…) or define window.__SNAPSHOT_URL__ in docs/dashboard/config.js.");
      }
      if (shouldShowLoading) setSnapshotLoadingVisible(false);
      return;
    }
    try {
      const primary = url.trim();
      const fallback = getCommittedSnapshotFallbackUrl();
      let res = await fetch(primary, { credentials: "omit" });
      let text = await res.text();
      let usedRelay503Fallback = false;
      if (!res.ok && res.status === 503 && fallback && fallback !== primary) {
        const resFb = await fetch(fallback, { credentials: "omit" });
        const textFb = await resFb.text();
        if (resFb.ok) {
          res = resFb;
          text = textFb;
          usedRelay503Fallback = true;
        }
      }
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
      if (usedRelay503Fallback) {
        snapshotMetaSuffix =
          " · Showing committed docs/qualified_public_snapshot.json (live relay has no file yet; HTTP 503).";
        snapshotLoadWasCommittedFallback = true;
      } else {
        snapshotMetaSuffix = "";
        snapshotLoadWasCommittedFallback = false;
      }
      render(data);
      const snapDigest = await digestHex(text);
      if (forNotify && notifyAlertsEnabled) {
        const scope = tierANotifyScope();
        if (scope === "qualified") {
          await notifySnapshotChangedFiltered(data, snapDigest);
        }
        if (scope === "watchlist") {
          await notifyPinnedWatch(lastPinWatchDelta.entered, lastPinWatchDelta.left);
        }
        try {
          localStorage.setItem(LS_LAST_POLL_SNAPSHOT_DIGEST, snapDigest);
        } catch {
          /* ignore */
        }
      } else {
        localStorage.setItem(LS_DIGEST, snapDigest);
        if (notifyAlertsEnabled) {
          try {
            localStorage.setItem(LS_LAST_POLL_SNAPSHOT_DIGEST, snapDigest);
          } catch {
            /* ignore */
          }
        }
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
    } finally {
      if (shouldShowLoading) setSnapshotLoadingVisible(false);
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

  async function forceResetDashboardCachesOnce() {
    const KEY = "dash_sw_cache_reset_v99_done";
    if (!("serviceWorker" in navigator) || !("caches" in window)) return;
    try {
      if (sessionStorage.getItem(KEY) === "1") return;
      const regs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map((r) => r.unregister()));
      const names = await caches.keys();
      await Promise.all(
        names
          .filter((n) => String(n).startsWith("qualified-dash-assets-"))
          .map((n) => caches.delete(n)),
      );
      sessionStorage.setItem(KEY, "1");
      window.location.reload();
    } catch (e) {
      console.warn("Cache reset skipped", e);
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
        sortDir = key === "symbol" || key === "name" || key === "venue" ? 1 : -1;
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
      if (filterHealthMin != null && filterHealthMin !== 60 && filterHealthMin !== 65 && filterHealthMin !== 70) {
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

  if (elVolAccelFilterSelect) {
    elVolAccelFilterSelect.addEventListener("change", () => {
      const raw = elVolAccelFilterSelect.value;
      if (raw === "pos" || raw === "25" || raw === "50") filterVolAccel = raw;
      else filterVolAccel = "";
      syncVolAccelFilterSelect();
      applyTableView();
      persistUiPreferences();
      resetTierAPollBaselineIfAlerts();
      void syncPushNotifyExchangesIfSubscribed();
    });
  }

  if (elVolumeMinSelect) {
    elVolumeMinSelect.addEventListener("change", () => {
      const raw = elVolumeMinSelect.value;
      if (raw === "") filterVolMinUsd = null;
      else {
        const n = Number(raw);
        filterVolMinUsd = Number.isFinite(n) && VOL_MIN_FILTER_OPTIONS.some((o) => o.v === n) ? n : null;
      }
      syncVolumeMinSelect();
      applyTableView();
      persistUiPreferences();
      resetTierAPollBaselineIfAlerts();
      void syncPushNotifyExchangesIfSubscribed();
    });
  }

  function onChartDistFilterChange() {
    applyTableView();
    persistUiPreferences();
    resetTierAPollBaselineIfAlerts();
    void syncPushNotifyExchangesIfSubscribed();
  }

  if (elChartDistMax7Select) {
    elChartDistMax7Select.addEventListener("change", () => {
      const raw = elChartDistMax7Select.value;
      if (raw === "5" || raw === "10" || raw === "15") filterChartDistMax7 = Number(raw);
      else filterChartDistMax7 = null;
      syncChartDistFilterSelects();
      onChartDistFilterChange();
    });
  }
  if (elChartDistMax30Select) {
    elChartDistMax30Select.addEventListener("change", () => {
      const raw = elChartDistMax30Select.value;
      if (raw === "5" || raw === "10" || raw === "15") filterChartDistMax30 = Number(raw);
      else filterChartDistMax30 = null;
      syncChartDistFilterSelects();
      onChartDistFilterChange();
    });
  }

  if (elChartFsClose && elChartFsDialog) {
    elChartFsClose.addEventListener("click", () => elChartFsDialog.close());
  }
  if (elChartFsDialog) {
    elChartFsDialog.addEventListener("click", (ev) => {
      if (ev.target === elChartFsDialog) elChartFsDialog.close();
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
  const tabLogsEl = document.getElementById("tabLogs");
  if (tabLogsEl) {
    tabLogsEl.addEventListener("click", () => setActiveView("logs"));
  }
  const tabSettingsEl = document.getElementById("tabSettings");
  if (tabSettingsEl) {
    tabSettingsEl.addEventListener("click", () => setActiveView("settings"));
  }

  if (elOpsMarkReadBtn) {
    elOpsMarkReadBtn.addEventListener("click", () => ackOpsNotificationsFromUi());
  }

  if (elCoinAlertsBell) {
    elCoinAlertsBell.addEventListener("click", (ev) => {
      ev.stopPropagation();
      toggleCoinAlertsPopover();
    });
  }

  document.addEventListener("click", (ev) => {
    if (!elCoinAlertsDropdownRoot || !elCoinAlertsPopover || elCoinAlertsPopover.hidden) return;
    if (!elCoinAlertsDropdownRoot.contains(ev.target)) closeCoinAlertsPopover();
  });

  if (elCoinAlertsPopover) {
    elCoinAlertsPopover.addEventListener("click", (ev) => {
      const dismissOne = ev.target.closest("[data-coin-alert-dismiss]");
      if (dismissOne) {
        ev.preventDefault();
        ev.stopPropagation();
        removeCoinAlertById(dismissOne.getAttribute("data-coin-alert-dismiss"));
        renderCoinAlertsList();
        syncCoinBellBadge();
        return;
      }
      const dismissAllBtn = ev.target.closest("#coinAlertsDismissAll");
      if (dismissAllBtn) {
        ev.preventDefault();
        ev.stopPropagation();
        clearCoinAlertFeed();
        writeCoinAlertsAckDigest(coinSignalsDigest());
        renderCoinAlertsList();
        syncCoinBellBadge();
      }
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

  if (elThemeToggle) {
    elThemeToggle.addEventListener("click", () => cycleThemeMode());
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
    elNotify.addEventListener("click", () => {
      void toggleTierANotifications();
    });
  }

  function dismissNotifyFirstPrompt() {
    try {
      localStorage.setItem(LS_NOTIFY_FIRST_PROMPT_DONE, "1");
    } catch {
      /* ignore */
    }
    if (elNotifyPromptDialog && elNotifyPromptDialog.open) elNotifyPromptDialog.close();
  }

  function maybeShowNotifyFirstPrompt() {
    try {
      if (localStorage.getItem(LS_NOTIFY_FIRST_PROMPT_DONE) === "1") return;
      if (!("Notification" in window)) {
        localStorage.setItem(LS_NOTIFY_FIRST_PROMPT_DONE, "1");
        return;
      }
      if (Notification.permission !== "default") {
        localStorage.setItem(LS_NOTIFY_FIRST_PROMPT_DONE, "1");
        return;
      }
      if (notifyAlertsEnabled) {
        localStorage.setItem(LS_NOTIFY_FIRST_PROMPT_DONE, "1");
        return;
      }
      if (!elNotifyPromptDialog || typeof elNotifyPromptDialog.showModal !== "function") return;
      window.setTimeout(() => {
        try {
          if (!elNotifyPromptDialog.open) elNotifyPromptDialog.showModal();
        } catch {
          /* ignore */
        }
      }, 500);
    } catch {
      /* ignore */
    }
  }

  if (elNotifyPromptLater) {
    elNotifyPromptLater.addEventListener("click", () => dismissNotifyFirstPrompt());
  }
  if (elNotifyPromptEnable) {
    elNotifyPromptEnable.addEventListener("click", () => {
      void (async () => {
        await toggleTierANotifications();
        dismissNotifyFirstPrompt();
      })();
    });
  }
  if (elNotifyPromptDialog) {
    elNotifyPromptDialog.addEventListener("click", (ev) => {
      if (ev.target === elNotifyPromptDialog) dismissNotifyFirstPrompt();
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
      await forceResetDashboardCachesOnce();
      await registerServiceWorker();
      syncPushTierBVisibility();
      await refreshPushTierBLabel();
      syncNotifyTierAButton();
      maybeShowNotifyFirstPrompt();
    })();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      syncNotifyTierAButton();
      if (notifyAlertsEnabled) {
        loadSnapshot({ showErrors: false, forNotify: true });
      }
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
  loadOpsFeedFromStorage();

  if (getSnapshotUrl().trim()) {
    loadSnapshot({ showErrors: true, forNotify: false });
  } else {
    showError("Set a snapshot JSON URL (?api=…) or define window.__SNAPSHOT_URL__ in docs/dashboard/config.js.");
  }
})();
