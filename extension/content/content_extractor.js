/**
 * Social Guard: Robust Multi-Platform Content Extractor
 * Multi-strategy DOM, OpenGraph metadata, JSON-LD, and visible content extractor
 * with tailored support for modern Instagram (posts/reels/modals), Twitter/X, Reddit, Facebook, and generic web pages.
 */

// Define global extractor function
window.__SOCIAL_GUARD_EXTRACT__ = function() {
  const platform = detectPlatform();
  if (platform === "instagram") {
    return extractInstagramContent();
  }
  return extractGenericOrSocialContent(platform);
};

// Global message listener for extractor triggers from popup
if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "EXTRACT_PAGE_CONTENT") {
      try {
        const extractedData = window.__SOCIAL_GUARD_EXTRACT__();
        sendResponse({ status: "SUCCESS", data: extractedData });
      } catch (err) {
        console.error("[Social Guard Content Script] Extraction error:", err);
        sendResponse({ status: "ERROR", message: err.message });
      }
    }
    return true;
  });
}

/**
 * Robust Instagram Post, Reel & Modal Extractor
 */
function extractInstagramContent() {
  // 1. Check for manual user highlight selection first
  const selectedText = getWindowSelectionText();
  if (selectedText && selectedText.length > 5) {
    return buildExtractedResult({
      platform: "instagram",
      text: selectedText,
      hashtags: extractHashtags(selectedText),
      image_urls: extractInstagramImages(),
      author: extractInstagramAuthor() || { username: "instagram_user" },
      comments: extractInstagramComments()
    });
  }

  // 2. Extract from DOM (Modal dialog, article, right-side comment pane, post page)
  const domCaption = extractInstagramDomCaption();
  const domAuthor = extractInstagramAuthor();
  const domComments = extractInstagramComments();
  const domImages = extractInstagramImages();

  // 3. Try JSON-LD Structured Data
  const jsonLdData = extractJsonLdData();
  let jsonCaption = "";
  let jsonAuthor = null;
  let jsonImages = [];

  if (jsonLdData) {
    if (jsonLdData.articleBody) jsonCaption = jsonLdData.articleBody;
    else if (jsonLdData.caption) jsonCaption = jsonLdData.caption;
    else if (jsonLdData.description) jsonCaption = jsonLdData.description;

    if (jsonLdData.author) {
      const authName = typeof jsonLdData.author === "string" 
        ? jsonLdData.author 
        : (jsonLdData.author.name || jsonLdData.author.identifier || "");
      if (authName) jsonAuthor = { username: cleanUsername(authName) };
    }

    if (jsonLdData.image) {
      const imgs = Array.isArray(jsonLdData.image) ? jsonLdData.image : [jsonLdData.image];
      jsonImages = imgs.map(img => (typeof img === "string" ? img : img.url)).filter(isValidHttpUrl);
    }
  }

  // 4. Try OpenGraph / Meta Tags
  const ogDesc = getMetaContent('meta[property="og:description"]') || getMetaContent('meta[name="description"]');
  const ogTitle = getMetaContent('meta[property="og:title"]') || getMetaContent('meta[name="twitter:title"]');
  const ogImage = getMetaContent('meta[property="og:image"]') || getMetaContent('meta[name="twitter:image"]');

  let ogCaption = "";
  let ogAuthorName = "";
  if (ogDesc) {
    const quoteMatch = ogDesc.match(/:\s*["“'](.+?)["”']\s*$/s) || ogDesc.match(/:\s*(.+)$/s);
    if (quoteMatch && quoteMatch[1]) {
      ogCaption = quoteMatch[1].trim();
    } else {
      ogCaption = ogDesc;
    }

    const authorMatch = ogDesc.match(/-\s*([a-zA-Z0-9._]+)\s+on\s+/i);
    if (authorMatch && authorMatch[1]) {
      ogAuthorName = authorMatch[1].trim();
    }
  }

  if (!ogAuthorName && ogTitle) {
    const titleAuthorMatch = ogTitle.match(/@([a-zA-Z0-9._]+)/) || ogTitle.match(/([a-zA-Z0-9._]+)\s+on\s+Instagram/i);
    if (titleAuthorMatch && titleAuthorMatch[1]) {
      ogAuthorName = titleAuthorMatch[1].trim();
    }
  }

  // 5. Fallback to document title (cleanly stripped of site suffix)
  let fallbackTitle = "";
  if (document.title && !document.title.toLowerCase().startsWith("instagram")) {
    fallbackTitle = document.title.replace(/\s*•\s*Instagram.*$/i, "").replace(/^.*on\s+Instagram:\s*["“']?/i, "").replace(/["”']\s*$/i, "").trim();
  }

  // 6. Broad Semantic Fallback across visible spans
  let candidateSpansText = "";
  const mainScope = document.querySelector("div[role='dialog'], article, main") || document.body;
  const candidateSpans = Array.from(mainScope.querySelectorAll("h1, h2, span[dir='auto'], div[dir='auto'], p"))
    .map(el => el.innerText.trim())
    .filter(t => {
      if (!t || t.length < 10) return false;
      const lower = t.toLowerCase();
      if (lower.startsWith("view all") || lower.startsWith("log in") || lower.startsWith("sign up") || lower.startsWith("follow") || lower.startsWith("liked by") || lower.startsWith("see translation") || lower === "verified") {
        return false;
      }
      return true;
    });

  if (candidateSpans.length > 0) {
    candidateSpansText = candidateSpans.slice(0, 3).join("\n\n");
  }

  // Determine the most descriptive post text available
  let postText = domCaption || candidateSpansText || jsonCaption || ogCaption || fallbackTitle || "";
  
  // Clean off leading author username if string starts with "username\nText"
  if (postText) {
    const lines = postText.split("\n").map(l => l.trim()).filter(Boolean);
    if (lines.length > 1 && lines[0].length < 30 && !lines[0].includes(" ") && !lines[0].includes("#")) {
      postText = lines.slice(1).join("\n");
    }
  }

  const finalAuthor = domAuthor || (ogAuthorName ? { username: ogAuthorName } : null) || jsonAuthor || { username: "instagram_user" };
  const combinedImages = Array.from(new Set([...domImages, ...jsonImages, ...(ogImage && isValidHttpUrl(ogImage) ? [ogImage] : [])])).slice(0, 3);

  return buildExtractedResult({
    platform: "instagram",
    text: postText || "Instagram post content detected.",
    hashtags: extractHashtags(postText),
    image_urls: combinedImages,
    author: finalAuthor,
    comments: domComments
  });
}

/**
 * Extract Instagram caption from DOM elements (overlay dialog, article, right side comments pane)
 */
function extractInstagramDomCaption() {
  const container = document.querySelector("div[role='dialog'], article, main, [role='main']") || document.body;
  
  // 1. Look for h1 elements inside post
  const h1 = container.querySelector("h1");
  if (h1 && h1.innerText.trim().length > 3) {
    return h1.innerText.trim();
  }

  // 2. Look for first comment row / caption block inside ul
  const captionNodes = Array.from(container.querySelectorAll("ul li span[dir='auto'], ul li div[dir='auto'], div[role='button'] + div[dir='auto'], span[dir='auto']"))
    .map(el => el.innerText.trim())
    .filter(txt => {
      if (!txt || txt.length < 5) return false;
      const lower = txt.toLowerCase();
      if (lower.startsWith("view all") || lower.startsWith("reply") || lower.startsWith("see translation") || lower === "verified" || lower.startsWith("liked by") || lower.endsWith("ago")) {
        return false;
      }
      return true;
    });

  if (captionNodes.length > 0) {
    return captionNodes[0];
  }

  // 3. Fallback: Check alt text of the main Instagram post image
  const postImgs = container.querySelectorAll("img[alt]");
  for (const img of postImgs) {
    const alt = img.getAttribute("alt") || "";
    if (alt && alt.length > 15 && !alt.startsWith("Photo by") && !alt.startsWith("Profile picture")) {
      return alt;
    } else if (alt && alt.includes("Photo by") && alt.includes("with caption")) {
      const match = alt.match(/with caption:\s*(.+)/i);
      if (match && match[1]) return match[1].trim();
    }
  }

  return "";
}

/**
 * Extract author username from Instagram DOM
 */
function extractInstagramAuthor() {
  const container = document.querySelector("div[role='dialog'], article, main") || document.body;
  const headerLinks = Array.from(container.querySelectorAll("header a, a[role='link'], [data-testid*='user' i], a[href*='/']"));
  
  for (const link of headerLinks) {
    const href = link.getAttribute("href") || "";
    const cleanHref = href.replace(/^\/+|\/+$/g, "");
    if (cleanHref && !cleanHref.includes("/") && !["explore", "reels", "direct", "stories", "accounts", "p"].includes(cleanHref)) {
      const username = link.innerText.trim() || cleanHref;
      if (username && username.length > 1 && !username.includes("\n") && !username.includes(" ") && !username.includes("•")) {
        return {
          username: cleanUsername(username),
          account_age_days: null,
          followers: 0,
          following: 0
        };
      }
    }
  }
  return null;
}

/**
 * Extract visible comments from Instagram DOM
 */
function extractInstagramComments() {
  const comments = [];
  const container = document.querySelector("div[role='dialog'], article, main") || document.body;
  const commentItems = container.querySelectorAll("ul li, div[role='button'] + div[dir='auto']");
  
  let idx = 0;
  let isFirst = true;
  for (const item of commentItems) {
    if (idx >= 6) break;
    const txt = item.innerText.trim();
    if (!txt || txt.length < 4 || txt.startsWith("View all") || txt.startsWith("Reply") || txt.startsWith("See translation") || txt === "Verified" || txt.startsWith("Liked by")) {
      continue;
    }

    if (isFirst) {
      isFirst = false;
      continue; // Skip the main post caption
    }

    const parts = txt.split("\n").map(p => p.trim()).filter(Boolean);
    const commentBody = parts.length > 1 ? parts.slice(1).join(" ") : parts[0];

    if (commentBody.length > 3) {
      comments.push({
        comment_id: `c_ig_${idx}`,
        text: commentBody.slice(0, 300),
        likes: 0
      });
      idx++;
    }
  }

  return comments;
}

/**
 * Extract Instagram Images safely
 */
function extractInstagramImages() {
  const container = document.querySelector("div[role='dialog'], article, main") || document.body;
  const imgs = Array.from(container.querySelectorAll("img"))
    .map(img => img.currentSrc || img.src)
    .filter(src => {
      if (!src || !isValidHttpUrl(src)) return false;
      const lower = src.toLowerCase();
      if (lower.includes("avatar") || lower.includes("profile_pic") || lower.includes("icon") || lower.includes("badge") || lower.includes("150x150")) {
        return false;
      }
      return true;
    });

  return Array.from(new Set(imgs)).slice(0, 3);
}

/**
 * Generic & Web/Social Extractor (Twitter, Reddit, Facebook, News, Blogs)
 */
function extractGenericOrSocialContent(platform) {
  // 1. Highlighted selection
  const selectedText = getWindowSelectionText();
  if (selectedText && selectedText.length > 5) {
    return buildExtractedResult({
      platform: platform,
      text: selectedText,
      hashtags: extractHashtags(selectedText),
      image_urls: extractSafeImages(),
      author: extractGenericAuthor(),
      comments: extractGenericComments()
    });
  }

  // 2. OpenGraph / Twitter Meta Tags
  const ogDesc = getMetaContent('meta[property="og:description"]') || getMetaContent('meta[name="twitter:description"]');
  const ogTitle = getMetaContent('meta[property="og:title"]') || getMetaContent('meta[name="twitter:title"]');
  const ogImage = getMetaContent('meta[property="og:image"]') || getMetaContent('meta[name="twitter:image"]');

  // 3. Semantic Article/Main Text
  let postText = "";
  const mainEl = document.querySelector("article, main, [role='main'], [role='article']") || document.body;
  if (mainEl) {
    const paragraphs = Array.from(mainEl.querySelectorAll("p, h1, h2, span[dir='auto']"))
      .map(el => el.innerText.trim())
      .filter(t => t.length > 25 && !t.includes("Cookie") && !t.includes("Privacy") && !t.includes("Terms"));
    
    if (paragraphs.length > 0) {
      postText = paragraphs.slice(0, 4).join("\n\n");
    }
  }

  if (!postText) {
    postText = ogDesc || ogTitle || document.title || "No readable content found on page.";
  }

  const safeImgs = extractSafeImages();
  if (ogImage && isValidHttpUrl(ogImage) && !safeImgs.includes(ogImage)) {
    safeImgs.unshift(ogImage);
  }

  return buildExtractedResult({
    platform: platform,
    text: postText,
    hashtags: extractHashtags(postText),
    image_urls: safeImgs.slice(0, 3),
    author: extractGenericAuthor(),
    comments: extractGenericComments()
  });
}

/**
 * Generic visible comment finder
 */
function extractGenericComments() {
  const comments = [];
  const commentElements = document.querySelectorAll(".comment, [data-testid*='comment' i], [aria-label*='comment' i], .reply");
  
  commentElements.forEach((el, idx) => {
    if (idx < 5) {
      const txt = el.innerText.trim();
      if (txt && txt.length > 10) {
        comments.push({
          comment_id: `c_dom_${idx}`,
          text: txt.slice(0, 300),
          likes: 0
        });
      }
    }
  });

  return comments;
}

/**
 * Generic Author finder
 */
function extractGenericAuthor() {
  const metaAuthor = getMetaContent('meta[name="author"]') || getMetaContent('meta[property="article:author"]');
  if (metaAuthor) {
    return { username: cleanUsername(metaAuthor), followers: 0, following: 0 };
  }

  const authorEl = document.querySelector("[rel='author'], [data-testid='User-Name'], .author-name, .byline");
  if (authorEl) {
    const txt = authorEl.innerText.trim().split("\n")[0];
    if (txt) {
      return { username: cleanUsername(txt), followers: 0, following: 0 };
    }
  }

  return { username: "page_author", followers: 0, following: 0 };
}

/**
 * Safe Image Extractor: Only returns absolute http:// or https:// URLs
 */
function extractSafeImages() {
  const imgs = Array.from(document.querySelectorAll("article img, [role='article'] img, main img, img[src*='scontent']"))
    .map(img => img.currentSrc || img.src)
    .filter(src => {
      if (!src || !isValidHttpUrl(src)) return false;
      const lower = src.toLowerCase();
      if (lower.includes("avatar") || lower.includes("profile_pic") || lower.includes("icon") || lower.includes("emoji") || lower.includes("badge")) {
        return false;
      }
      return true;
    });

  return Array.from(new Set(imgs)).slice(0, 3);
}

/**
 * Parse JSON-LD if available
 */
function extractJsonLdData() {
  try {
    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
    for (const script of scripts) {
      const content = script.textContent ? script.textContent.trim() : "";
      if (content) {
        const parsed = JSON.parse(content);
        if (Array.isArray(parsed)) return parsed[0];
        return parsed;
      }
    }
  } catch {
    // Ignore JSON-LD parse errors
  }
  return null;
}

/**
 * Helpers
 */
function detectPlatform() {
  const host = window.location.hostname.toLowerCase();
  if (host.includes("instagram.com")) return "instagram";
  if (host.includes("twitter.com") || host.includes("x.com")) return "twitter";
  if (host.includes("reddit.com")) return "reddit";
  if (host.includes("facebook.com")) return "facebook";
  if (host.includes("threads.net")) return "threads";
  return "generic";
}

function getWindowSelectionText() {
  return window.getSelection ? window.getSelection().toString().trim() : "";
}

function getMetaContent(selector) {
  const el = document.querySelector(selector);
  return el ? (el.getAttribute("content") || "").trim() : "";
}

function extractHashtags(text) {
  if (!text) return [];
  const hashtagRegex = /#[\w\u0590-\u05ff]+/gi;
  return Array.from(new Set((text.match(hashtagRegex) || []).map(h => h.trim())));
}

function isValidHttpUrl(urlStr) {
  if (!urlStr || typeof urlStr !== "string") return false;
  const lower = urlStr.trim().toLowerCase();
  return lower.startsWith("http://") || lower.startsWith("https://");
}

function cleanUsername(name) {
  return name.replace(/^@+/, "").trim().slice(0, 50);
}

function buildExtractedResult(params) {
  return {
    source: "live_tab",
    platform: params.platform || "generic",
    text: params.text || "No text available.",
    hashtags: params.hashtags || [],
    image_urls: params.image_urls || [],
    author: params.author || { username: "page_author", followers: 0, following: 0 },
    comments: params.comments || [],
    url: window.location.href,
    title: document.title
  };
}


