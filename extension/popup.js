/**
 * consumed.ai Chrome Extension — Popup UI
 *
 * Phase 11: connection management, quick command execution,
 * status display. Stores API key in chrome.storage.local.
 */

const $ = (id) => document.getElementById(id);

// Load saved config
chrome.storage.local.get(["apiKey", "apiUrl"], (config) => {
  $("apiKey").value = config.apiKey || "";
  $("apiUrl").value = config.apiUrl || "https://api.consumed.ai";
  checkStatus();
});

// Save button
$("saveBtn").addEventListener("click", () => {
  const apiKey = $("apiKey").value.trim();
  const apiUrl = $("apiUrl").value.trim() || "https://api.consumed.ai";

  chrome.storage.local.set({ apiKey, apiUrl }, () => {
    $("saveBtn").textContent = "Saved!";
    setTimeout(() => {
      $("saveBtn").textContent = "Connect";
    }, 1500);
    checkStatus();
  });
});

// Check connection status
function checkStatus() {
  chrome.runtime.sendMessage({ type: "getStatus" }, (resp) => {
    if (resp && resp.connected) {
      $("statusDot").className = "dot green";
      $("statusText").textContent = "Connected to daemon";
    } else {
      chrome.storage.local.get(["apiKey"], (config) => {
        if (config.apiKey) {
          $("statusDot").className = "dot red";
          $("statusText").textContent = "Disconnected — check API key";
        } else {
          $("statusDot").className = "dot yellow";
          $("statusText").textContent = "Enter API key to connect";
        }
      });
    }
  });
}

// Execute quick command
$("sendBtn").addEventListener("click", async () => {
  const command = $("command").value.trim();
  if (!command) return;

  $("sendBtn").textContent = "Running...";
  $("sendBtn").disabled = true;

  try {
    const config = await chrome.storage.local.get(["apiKey", "apiUrl"]);
    const apiUrl = config.apiUrl || "https://api.consumed.ai";
    const apiKey = config.apiKey || "";

    const resp = await fetch(`${apiUrl}/api/execute`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      body: JSON.stringify({ shortcode: command }),
    });

    const data = await resp.json();

    if (data.success) {
      const result = data.data || data.result || data;
      $("result").innerHTML = `<span class="success">Success</span><pre>${JSON.stringify(result, null, 2).substring(0, 2000)}</pre>`;
    } else {
      $("result").innerHTML = `<span class="error">Error: ${data.error || "Unknown"}</span>`;
    }
  } catch (e) {
    $("result").innerHTML = `<span class="error">Error: ${e.message}</span>`;
  }

  $("sendBtn").textContent = "Execute";
  $("sendBtn").disabled = false;
});

// Enter key in command box
$("command").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("sendBtn").click();
  }
});
