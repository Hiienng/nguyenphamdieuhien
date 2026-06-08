// ===========================================================================
// GetifyCo Ads Spy — Service Worker (Background)
// Captures Etsy Ads API responses into chrome.storage.local, then writes them
// DIRECTLY to the user's own Neon Postgres over Neon's HTTP SQL endpoint.
// The user only configures a Neon connection string — no app/relay server.
// ===========================================================================

const MAX_AGE_DAYS = 30;
const STORAGE_KEY = "getify_sessions";
const DB_CONFIG_KEY = "getify_db_config";

// Single-user app: all data is keyed to this fixed tenant id (matches the
// desktop app, which reads the same Neon under this tenant).
const TENANT_ID = "b7b81ef3-8a1a-42ca-8a56-efb40358ff91";

const INSERT_CHUNK = 400;

// --- MESSAGE HANDLER ---

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "CAPTURE") {
    handleCapture(message.data);
    sendResponse({ ok: true });
  } else if (message.action === "GET_ALL") {
    handleGetAll(sendResponse);
    return true;
  } else if (message.action === "CLEAR_ALL") {
    handleClearAll(sendResponse);
    return true;
  } else if (message.action === "GET_STATS") {
    handleGetStats(sendResponse);
    return true;
  } else if (message.action === "SAVE_DB_CONFIG") {
    handleSaveDbConfig(message.data, sendResponse);
    return true;
  } else if (message.action === "GET_DB_CONFIG") {
    handleGetDbConfig(sendResponse);
    return true;
  } else if (message.action === "TEST_DB_CONNECTION") {
    handleTestConnection(sendResponse);
    return true;
  } else if (message.action === "INGEST_LISTING") {
    handleIngestListing(message.rows, message.importer, sendResponse);
    return true;
  } else if (message.action === "INGEST_KEYWORD") {
    handleIngestKeyword(message.rows, message.importer, sendResponse);
    return true;
  }
});

// =====================================================================
// SESSION CAPTURE (unchanged)
// =====================================================================

async function handleCapture(data) {
  try {
    const result = await chrome.storage.local.get(STORAGE_KEY);
    const sessions = result[STORAGE_KEY] || [];
    let parsedBody = null;
    try { parsedBody = JSON.parse(data.body); } catch (e) { parsedBody = data.body; }
    sessions.push({
      id: generateId(),
      timestamp: new Date(data.timestamp).toISOString(),
      url: data.url,
      status: data.status,
      body: parsedBody,
      sizeBytes: data.sizeBytes,
    });
    const cutoff = Date.now() - MAX_AGE_DAYS * 24 * 60 * 60 * 1000;
    const cleaned = sessions.filter((s) => new Date(s.timestamp).getTime() > cutoff);
    await chrome.storage.local.set({ [STORAGE_KEY]: cleaned });
    updateBadge(cleaned.length);
  } catch (e) {
    console.error("[Getify] Storage write error:", e);
  }
}

async function handleGetAll(sendResponse) {
  try {
    const result = await chrome.storage.local.get(STORAGE_KEY);
    sendResponse({ sessions: result[STORAGE_KEY] || [] });
  } catch (e) { sendResponse({ sessions: [] }); }
}

async function handleClearAll(sendResponse) {
  try {
    await chrome.storage.local.set({ [STORAGE_KEY]: [] });
    updateBadge(0);
    sendResponse({ ok: true });
  } catch (e) { sendResponse({ ok: false }); }
}

async function handleGetStats(sendResponse) {
  try {
    const result = await chrome.storage.local.get(STORAGE_KEY);
    const sessions = result[STORAGE_KEY] || [];
    let totalSize = 0;
    sessions.forEach((s) => (totalSize += s.sizeBytes || 0));
    sendResponse({
      count: sessions.length,
      totalSizeBytes: totalSize,
      oldestEntry: sessions.length > 0 ? sessions[0].timestamp : null,
      newestEntry: sessions.length > 0 ? sessions[sessions.length - 1].timestamp : null,
    });
  } catch (e) { sendResponse({ count: 0, totalSizeBytes: 0 }); }
}

// =====================================================================
// DATABASE CONFIG — just a Neon connection string (+ optional VM label)
// =====================================================================

async function handleSaveDbConfig(data, sendResponse) {
  try {
    await chrome.storage.local.set({
      [DB_CONFIG_KEY]: {
        connString: (data.connString || "").trim(),
        vmName: (data.vmName || "").trim(),
      },
    });
    sendResponse({ ok: true });
  } catch (e) { sendResponse({ ok: false, error: e.message }); }
}

async function handleGetDbConfig(sendResponse) {
  try {
    const result = await chrome.storage.local.get(DB_CONFIG_KEY);
    const config = result[DB_CONFIG_KEY] || {};
    sendResponse({ connString: config.connString || "", vmName: config.vmName || "" });
  } catch (e) { sendResponse({ connString: "", vmName: "" }); }
}

async function _getConnString() {
  const result = await chrome.storage.local.get(DB_CONFIG_KEY);
  return ((result[DB_CONFIG_KEY] || {}).connString || "").trim();
}

async function handleTestConnection(sendResponse) {
  try {
    const conn = await _getConnString();
    if (!conn) { sendResponse({ ok: false, error: "Chưa nhập Database connection." }); return; }
    await neonExec(conn, "select 1", []);
    sendResponse({ ok: true });
  } catch (e) { sendResponse({ ok: false, error: e.message }); }
}

// =====================================================================
// NEON HTTP SQL
// =====================================================================

function _neonHost(conn) {
  const m = conn.match(/@([^/?#]+)/);
  if (!m) return null;
  return m[1].split(":")[0]; // strip optional :port
}

async function neonExec(conn, query, params) {
  const host = _neonHost(conn);
  if (!host) throw new Error("Connection string không hợp lệ (thiếu host).");
  const res = await fetch(`https://${host}/sql`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Neon-Connection-String": conn,
    },
    body: JSON.stringify({ query, params: params || [] }),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`Neon HTTP ${res.status}: ${txt.slice(0, 200)}`);
  }
  return res.json();
}

function _buildInsert(table, cols, rows) {
  const params = [];
  const tuples = rows.map((r) => {
    const ph = cols.map((c) => {
      const v = r[c];
      params.push(v === undefined ? null : v);
      return `$${params.length}`;
    });
    return `(${ph.join(",")})`;
  });
  return { query: `INSERT INTO ${table} (${cols.join(",")}) VALUES ${tuples.join(",")}`, params };
}

async function _insertChunked(conn, table, cols, rows) {
  let inserted = 0;
  for (let i = 0; i < rows.length; i += INSERT_CHUNK) {
    const chunk = rows.slice(i, i + INSERT_CHUNK);
    const { query, params } = _buildInsert(table, cols, chunk);
    await neonExec(conn, query, params);
    inserted += chunk.length;
  }
  return inserted;
}

const DDL_LISTING = `CREATE TABLE IF NOT EXISTS listing_report (
  id SERIAL PRIMARY KEY, listing_id VARCHAR(32) NOT NULL, title TEXT, image_url TEXT, no_vm VARCHAR(16),
  price NUMERIC(10,2), stock INTEGER, category VARCHAR(64), lifetime_orders INTEGER,
  lifetime_revenue NUMERIC(12,2), period VARCHAR(32) NOT NULL, views INTEGER, clicks INTEGER,
  orders INTEGER, revenue NUMERIC(12,2), spend NUMERIC(12,2), roas NUMERIC(8,2),
  import_time TIMESTAMPTZ, importer VARCHAR(64), tenant_id VARCHAR(36))`;

// existing installs: add the column if the table predates image_url
const DDL_LISTING_ALTER = `ALTER TABLE listing_report ADD COLUMN IF NOT EXISTS image_url TEXT`;

const DDL_KEYWORD = `CREATE TABLE IF NOT EXISTS keyword_report (
  id SERIAL PRIMARY KEY, listing_id VARCHAR(32) NOT NULL, keyword TEXT NOT NULL,
  no_vm VARCHAR(16), period VARCHAR(32) NOT NULL, roas NUMERIC(8,2), orders INTEGER,
  spend NUMERIC(12,2), revenue NUMERIC(12,2), clicks INTEGER, click_rate VARCHAR(8),
  views INTEGER, relevant VARCHAR(8), import_time TIMESTAMPTZ, importer VARCHAR(64),
  tenant_id VARCHAR(36))`;

const LISTING_COLS = ["listing_id", "title", "image_url", "no_vm", "price", "stock", "category",
  "lifetime_orders", "lifetime_revenue", "period", "views", "clicks", "orders",
  "revenue", "spend", "roas", "import_time", "importer", "tenant_id"];

const KEYWORD_COLS = ["listing_id", "keyword", "no_vm", "period", "roas", "orders",
  "spend", "revenue", "clicks", "click_rate", "views", "relevant", "import_time",
  "importer", "tenant_id"];

function _prepare(rows, vmName) {
  return rows.map((r) => ({
    ...r,
    importer: r.importer || vmName,
    no_vm: r.no_vm || vmName,
    tenant_id: TENANT_ID,
    import_time: r.import_time || new Date().toISOString(),
  }));
}

async function handleIngestListing(rows, importer, sendResponse) {
  try {
    const conn = await _getConnString();
    if (!conn) { sendResponse({ ok: false, error: "Chưa nhập Database connection." }); return; }
    if (!Array.isArray(rows) || rows.length === 0) { sendResponse({ ok: false, error: "No rows to insert." }); return; }
    await neonExec(conn, DDL_LISTING, []);
    await neonExec(conn, DDL_LISTING_ALTER, []);
    const inserted = await _insertChunked(conn, "listing_report", LISTING_COLS, _prepare(rows, importer || "extension"));
    sendResponse({ ok: true, inserted });
  } catch (e) { sendResponse({ ok: false, error: e.message }); }
}

async function handleIngestKeyword(rows, importer, sendResponse) {
  try {
    const conn = await _getConnString();
    if (!conn) { sendResponse({ ok: false, error: "Chưa nhập Database connection." }); return; }
    if (!Array.isArray(rows) || rows.length === 0) { sendResponse({ ok: false, error: "No rows to insert." }); return; }
    await neonExec(conn, DDL_KEYWORD, []);
    const inserted = await _insertChunked(conn, "keyword_report", KEYWORD_COLS, _prepare(rows, importer || "extension"));
    sendResponse({ ok: true, inserted });
  } catch (e) { sendResponse({ ok: false, error: e.message }); }
}

// =====================================================================
// HELPERS
// =====================================================================

function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).substring(2, 8);
}

function updateBadge(count) {
  chrome.action.setBadgeText({ text: count > 0 ? String(count) : "" });
  chrome.action.setBadgeBackgroundColor({ color: "#4CAF50" });
}

chrome.runtime.onInstalled.addListener(() => { updateBadge(0); });
