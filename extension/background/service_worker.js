/**
 * Social Guard: Background Service Worker (Manifest V3)
 */

chrome.runtime.onInstalled.addListener(() => {
  console.log("[Social Guard] Extension installed and background worker active.");
});

// Listener for messages from popup or content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "PING") {
    sendResponse({ status: "PONG" });
  }
  return true;
});
