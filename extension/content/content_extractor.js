/**
 * Social Guard: Content Extractor Script
 * Platform-independent DOM text and visible selection extractor.
 */

// Global message listener for extractor triggers from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "EXTRACT_PAGE_CONTENT") {
    try {
      const extractedData = extractVisibleContent();
      sendResponse({ status: "SUCCESS", data: extractedData });
    } catch (err) {
      console.error("[Social Guard Content Script] Extraction error:", err);
      sendResponse({ status: "ERROR", message: err.message });
    }
  }
  return true;
});

/**
 * Platform-independent content extraction.
 * Prioritizes user's highlighted selection, falling back to visible paragraphs and hashtags.
 */
function extractVisibleContent() {
  // 1. Check for highlighted text selection
  const selectedText = window.getSelection ? window.getSelection().toString().trim() : "";

  // 2. Extract visible post text
  let postText = selectedText;
  if (!postText) {
    // Collect text from prominent article / main container
    const mainEl = document.querySelector("article, main, [role='main'], [role='article']") || document.body;
    const paragraphs = Array.from(mainEl.querySelectorAll("p, h1, h2, h3, span[dir='auto']"))
      .map(el => el.innerText.trim())
      .filter(t => t.length > 25);
    
    postText = paragraphs.slice(0, 3).join("\n\n");
  }

  // 3. Extract hashtags
  const hashtagRegex = /#[\w\u0590-\u05ff]+/gi;
  const foundHashtags = (postText.match(hashtagRegex) || []).map(h => h.trim());

  // 4. Extract attached images
  const images = Array.from(document.querySelectorAll("article img, [role='article'] img, main img"))
    .map(img => img.src)
    .filter(src => src && src.startsWith("http") && !src.includes("avatar") && !src.includes("icon"))
    .slice(0, 2);

  // 5. Extract visible comments if accessible in DOM
  const comments = [];
  const commentElements = document.querySelectorAll("[data-testid='tweet'] ~ div, .comment, [aria-label*='comment' i]");
  commentElements.forEach((el, idx) => {
    if (idx < 5) {
      const txt = el.innerText.trim();
      if (txt && txt.length > 10 && txt !== postText) {
        comments.push({
          comment_id: `c_dom_${idx}`,
          text: txt.slice(0, 300),
          likes: 0
        });
      }
    }
  });

  return {
    platform: detectPlatform(),
    text: postText || "No text highlighted or selected. Please select post text on the page or test with sample data.",
    hashtags: foundHashtags,
    image_urls: images,
    comments: comments,
    url: window.location.href,
    title: document.title
  };
}

function detectPlatform() {
  const host = window.location.hostname.toLowerCase();
  if (host.includes("twitter.com") || host.includes("x.com")) return "twitter";
  if (host.includes("reddit.com")) return "reddit";
  if (host.includes("facebook.com")) return "facebook";
  return "generic";
}
