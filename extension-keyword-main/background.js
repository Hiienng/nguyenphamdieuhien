// ===========================================================================
// Getify Ads Spy — Service Worker (Background)
// Data warehouse: stores captured API responses in chrome.storage.local.
// Database: connects directly to Neon PostgreSQL via HTTP SQL API.
// No local relay server needed.
// ===========================================================================

const MAX_AGE_DAYS = 30;
const STORAGE_KEY = "getify_sessions";
const DB_CONFIG_KEY = "getify_db_config";

// Note: webNavigation auto-clear listeners removed — Etsy Ads dashboard is a SPA and fires history events on filter/tab clicks, which was wiping captured rows before the user could push to DB. Manual Clear button + MAX_AGE_DAYS cleanup in handleCapture still apply.

// --- MESSAGE HANDLER ---

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "CAPTURE") {
    handleCapture(message.data);
    sendResponse({ ok: true });
  } else if (message.action === "GET_ALL") {
    handleGetAll(sendResponse);
    return true; // Keep channel open for async response
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
    // Legacy no-op — test is now done directly in popup.js via fetch
    sendResponse({ ok: true });
    return true;
  } else if (message.action === "INGEST_LISTING") {
    handleIngestListing(message.rows, message.apiUrl, message.token, message.importer, sendResponse);
    return true;
  } else if (message.action === "INGEST_KEYWORD") {
    handleIngestKeyword(message.rows, message.apiUrl, message.token, message.importer, sendResponse);
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

    // Parse body to see if it's valid JSON
    let parsedBody = null;
    try {
      parsedBody = JSON.parse(data.body);
    } catch (e) {
      // Not JSON — store as raw text
      parsedBody = data.body;
    }

    const entry = {
      id: generateId(),
      timestamp: new Date(data.timestamp).toISOString(),
      url: data.url,
      status: data.status,
      body: parsedBody,
      sizeBytes: data.sizeBytes,
    };

    sessions.push(entry);

    // Auto-cleanup old entries
    const cutoff = Date.now() - MAX_AGE_DAYS * 24 * 60 * 60 * 1000;
    const cleaned = sessions.filter(
      (s) => new Date(s.timestamp).getTime() > cutoff
    );

    await chrome.storage.local.set({ [STORAGE_KEY]: cleaned });

    // Update badge count
    updateBadge(cleaned.length);
  } catch (e) {
    console.error("[Getify] Storage write error:", e);
  }
}

async function handleGetAll(sendResponse) {
  try {
    const result = await chrome.storage.local.get(STORAGE_KEY);
    const sessions = result[STORAGE_KEY] || [];
    sendResponse({ sessions: sessions });
  } catch (e) {
    sendResponse({ sessions: [] });
  }
}

async function handleClearAll(sendResponse) {
  try {
    await chrome.storage.local.set({ [STORAGE_KEY]: [] });
    updateBadge(0);
    sendResponse({ ok: true });
  } catch (e) {
    sendResponse({ ok: false });
  }
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
      newestEntry:
        sessions.length > 0 ? sessions[sessions.length - 1].timestamp : null,
    });
  } catch (e) {
    sendResponse({ count: 0, totalSizeBytes: 0 });
  }
}

// =====================================================================
// DATABASE CONFIG
// =====================================================================

async function handleSaveDbConfig(data, sendResponse) {
  try {
    await chrome.storage.local.set({
      [DB_CONFIG_KEY]: {
        apiUrl: (data.apiUrl || "").trim(),
        token: (data.token || "").trim(),
        vmName: (data.vmName || "").trim(),
      },
    });
    sendResponse({ ok: true });
  } catch (e) {
    sendResponse({ ok: false, error: e.message });
  }
}

async function handleGetDbConfig(sendResponse) {
  try {
    const result = await chrome.storage.local.get(DB_CONFIG_KEY);
    const config = result[DB_CONFIG_KEY] || {};
    sendResponse({
      apiUrl: config.apiUrl || "",
      token: config.token || "",
      vmName: config.vmName || "",
    });
  } catch (e) {
    sendResponse({ apiUrl: "", token: "", vmName: "" });
  }
}

// =====================================================================
// BACKEND API INGEST — replaces direct Neon SQL
// =====================================================================

async function handleIngestListing(rows, apiUrl, token, importer, sendResponse) {
  try {
    if (!apiUrl || !token) {
      sendResponse({ ok: false, error: "API URL hoặc Token chưa được cấu hình." });
      return;
    }
    if (!Array.isArray(rows) || rows.length === 0) {
      sendResponse({ ok: false, error: "No rows to insert." });
      return;
    }
    const vmName = importer || "extension";
    const res = await fetch(apiUrl.replace(/\/+$/, "") + "/api/v1/internal/ingest/listing", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
      },
      body: JSON.stringify({ rows, importer: vmName }),
    });
    if (!res.ok) {
      const err = await res.text();
      sendResponse({ ok: false, error: `HTTP ${res.status}: ${err}` });
      return;
    }
    const data = await res.json();
    sendResponse({ ok: true, inserted: data.inserted || rows.length });
  } catch (e) {
    sendResponse({ ok: false, error: e.message });
  }
}

async function handleIngestKeyword(rows, apiUrl, token, importer, sendResponse) {
  try {
    if (!apiUrl || !token) {
      sendResponse({ ok: false, error: "API URL hoặc Token chưa được cấu hình." });
      return;
    }
    if (!Array.isArray(rows) || rows.length === 0) {
      sendResponse({ ok: false, error: "No rows to insert." });
      return;
    }
    const vmName = importer || "extension";
    const res = await fetch(apiUrl.replace(/\/+$/, "") + "/api/v1/internal/ingest/keyword", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token,
      },
      body: JSON.stringify({ rows, importer: vmName }),
    });
    if (!res.ok) {
      const err = await res.text();
      sendResponse({ ok: false, error: `HTTP ${res.status}: ${err}` });
      return;
    }
    const data = await res.json();
    sendResponse({ ok: true, inserted: data.inserted || rows.length });
  } catch (e) {
    sendResponse({ ok: false, error: e.message });
  }
}

// =====================================================================
// HELPERS
// =====================================================================

function generateId() {
  return (
    Date.now().toString(36) + Math.random().toString(36).substring(2, 8)
  );
}

function updateBadge(count) {
  const text = count > 0 ? String(count) : "";
  chrome.action.setBadgeText({ text: text });
  chrome.action.setBadgeBackgroundColor({ color: "#4CAF50" });
}

// Reset badge on extension install/update
chrome.runtime.onInstalled.addListener(() => {
  updateBadge(0);
});

