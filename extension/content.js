/**
 * consumed.ai Chrome Extension — Content Script
 *
 * Phase 11: injected into every page. Listens for RPA commands from
 * the background service worker and executes them against the page DOM.
 * Also provides page context to the daemon on request.
 */

// Listen for messages from background
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "rpa.command") {
    // Commands are now executed via chrome.scripting.executeScript in background.js
    // This content script is kept for future direct messaging if needed
    sendResponse({ received: true });
  }

  if (msg.type === "getPageContext") {
    sendResponse({
      url: window.location.href,
      title: document.title,
      forms: document.querySelectorAll("form").length,
      inputs: document.querySelectorAll("input").length,
      tables: document.querySelectorAll("table").length,
      links: document.querySelectorAll("a").length,
    });
  }
});
