/**
 * consumed.ai Chrome Extension — Background Service Worker
 *
 * Phase 11: manages WebSocket connection to consumed-bot daemon,
 * receives RPA commands from agents, routes them to content scripts,
 * returns results.
 *
 * Architecture:
 *   consumed-bot agent → WebSocket → background.js → content.js → page DOM
 *   page DOM → content.js → background.js → WebSocket → consumed-bot agent
 */

const DEFAULT_API_URL = "https://api.consumed.ai";
let ws = null;
let connected = false;
let reconnectTimer = null;
let apiKey = "";
let apiUrl = DEFAULT_API_URL;

// ── WebSocket Connection ────────────────────────────────

async function connect() {
  const config = await chrome.storage.local.get(["apiKey", "apiUrl"]);
  apiKey = config.apiKey || "";
  apiUrl = config.apiUrl || DEFAULT_API_URL;

  if (!apiKey) {
    console.log("consumed.ai: no API key configured");
    updateBadge("!", "#f59e0b");
    return;
  }

  const wsUrl = apiUrl.replace("https://", "wss://").replace("http://", "ws://");
  const wsEndpoint = `${wsUrl}/ws?token=${apiKey}`;

  try {
    ws = new WebSocket(wsEndpoint);

    ws.onopen = () => {
      connected = true;
      console.log("consumed.ai: connected to daemon");
      updateBadge("", "#22c55e");
      clearReconnectTimer();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleDaemonMessage(msg);
      } catch (e) {
        console.warn("consumed.ai: invalid message", e);
      }
    };

    ws.onclose = () => {
      connected = false;
      console.log("consumed.ai: disconnected");
      updateBadge("", "#ef4444");
      scheduleReconnect();
    };

    ws.onerror = (err) => {
      console.warn("consumed.ai: WebSocket error", err);
      connected = false;
    };
  } catch (e) {
    console.warn("consumed.ai: connection failed", e);
    scheduleReconnect();
  }
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, 5000);
}

function clearReconnectTimer() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
}

function sendToDaemon(type, data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type, data }));
  }
}

function updateBadge(text, color) {
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color });
}

// ── Handle Commands from Daemon ─────────────────────────

async function handleDaemonMessage(msg) {
  const type = msg.type || msg.data?.type || "";

  if (type === "rpa.command") {
    const command = msg.data || {};
    const result = await executeRPACommand(command);
    sendToDaemon("rpa.result", {
      command_id: command.command_id,
      ...result,
    });
  }
}

async function executeRPACommand(command) {
  const action = command.action || "";
  const tabId = await getActiveTabId();

  if (!tabId) {
    return { success: false, error: "No active tab" };
  }

  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: contentExecuteCommand,
      args: [command],
    });

    if (results && results[0]) {
      return results[0].result || { success: false, error: "No result from content script" };
    }
    return { success: false, error: "Script execution returned no results" };
  } catch (e) {
    return { success: false, error: e.message };
  }
}

async function getActiveTabId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab?.id;
}

/**
 * This function is injected into the page context via chrome.scripting.executeScript.
 * It receives an RPA command and executes it against the page DOM.
 */
function contentExecuteCommand(command) {
  const action = command.action || "";
  const selector = command.selector || "";
  const value = command.value || "";

  try {
    switch (action) {
      case "click": {
        const el = document.querySelector(selector);
        if (!el) return { success: false, error: `Element not found: ${selector}` };
        el.click();
        return { success: true, action: "click", selector };
      }

      case "fill": {
        const el = document.querySelector(selector);
        if (!el) return { success: false, error: `Element not found: ${selector}` };
        el.value = value;
        el.dispatchEvent(new Event("input", { bubbles: true }));
        el.dispatchEvent(new Event("change", { bubbles: true }));
        return { success: true, action: "fill", selector, value_length: value.length };
      }

      case "extract_text": {
        const el = selector ? document.querySelector(selector) : document.body;
        if (!el) return { success: false, error: `Element not found: ${selector}` };
        const text = el.innerText || el.textContent || "";
        return { success: true, action: "extract_text", text: text.substring(0, 10000) };
      }

      case "extract_html": {
        const el = selector ? document.querySelector(selector) : document.body;
        if (!el) return { success: false, error: `Element not found: ${selector}` };
        return { success: true, action: "extract_html", html: el.innerHTML.substring(0, 50000) };
      }

      case "extract_table": {
        const table = document.querySelector(selector || "table");
        if (!table) return { success: false, error: "No table found" };
        const rows = [];
        for (const tr of table.querySelectorAll("tr")) {
          const cells = [];
          for (const td of tr.querySelectorAll("td, th")) {
            cells.push(td.textContent.trim());
          }
          rows.push(cells);
        }
        return { success: true, action: "extract_table", rows, row_count: rows.length };
      }

      case "extract_links": {
        const container = selector ? document.querySelector(selector) : document;
        if (!container) return { success: false, error: `Container not found: ${selector}` };
        const links = [];
        for (const a of container.querySelectorAll("a[href]")) {
          links.push({ href: a.href, text: (a.textContent || "").trim().substring(0, 200) });
        }
        return { success: true, action: "extract_links", links: links.slice(0, 500), count: links.length };
      }

      case "extract_forms": {
        const forms = [];
        for (const form of document.querySelectorAll("form")) {
          const fields = [];
          for (const input of form.querySelectorAll("input, select, textarea")) {
            fields.push({
              type: input.type || input.tagName.toLowerCase(),
              name: input.name || "",
              id: input.id || "",
              placeholder: input.placeholder || "",
              value: input.type === "password" ? "[hidden]" : (input.value || "").substring(0, 200),
            });
          }
          forms.push({
            action: form.action || "",
            method: form.method || "GET",
            fields,
          });
        }
        return { success: true, action: "extract_forms", forms, count: forms.length };
      }

      case "screenshot": {
        // Can't screenshot from content script — signal background to use chrome.tabs.captureVisibleTab
        return { success: false, error: "screenshot_via_background", needs_background: true };
      }

      case "get_url": {
        return { success: true, action: "get_url", url: window.location.href, title: document.title };
      }

      case "scroll": {
        const direction = command.direction || "down";
        const amount = command.amount || 500;
        if (direction === "down") window.scrollBy(0, amount);
        else if (direction === "up") window.scrollBy(0, -amount);
        else if (direction === "top") window.scrollTo(0, 0);
        else if (direction === "bottom") window.scrollTo(0, document.body.scrollHeight);
        return { success: true, action: "scroll", direction };
      }

      case "wait_for": {
        const el = document.querySelector(selector);
        return { success: !!el, action: "wait_for", found: !!el, selector };
      }

      case "select": {
        const el = document.querySelector(selector);
        if (!el || el.tagName !== "SELECT") return { success: false, error: `Select not found: ${selector}` };
        el.value = value;
        el.dispatchEvent(new Event("change", { bubbles: true }));
        return { success: true, action: "select", selector, value };
      }

      case "check": {
        const el = document.querySelector(selector);
        if (!el) return { success: false, error: `Element not found: ${selector}` };
        if (!el.checked) el.click();
        return { success: true, action: "check", selector, checked: true };
      }

      case "uncheck": {
        const el = document.querySelector(selector);
        if (!el) return { success: false, error: `Element not found: ${selector}` };
        if (el.checked) el.click();
        return { success: true, action: "uncheck", selector, checked: false };
      }

      default:
        return { success: false, error: `Unknown action: ${action}` };
    }
  } catch (e) {
    return { success: false, error: e.message, action };
  }
}

// ── Screenshot (background-only capability) ─────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "screenshot") {
    chrome.tabs.captureVisibleTab(null, { format: "png" }, (dataUrl) => {
      sendResponse({ success: true, screenshot: dataUrl });
    });
    return true; // async response
  }

  if (msg.type === "getStatus") {
    sendResponse({ connected, apiUrl });
    return false;
  }
});

// ── Lifecycle ───────────────────────────────────────────

chrome.storage.onChanged.addListener((changes) => {
  if (changes.apiKey || changes.apiUrl) {
    if (ws) ws.close();
    connect();
  }
});

// Connect on install/startup
connect();
