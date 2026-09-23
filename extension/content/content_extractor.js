/**
 * Social Guard: High-Precision Multi-Platform Content Extractor
 * Strictly scopes extraction to the primary post container on Instagram, Reddit, Twitter/X, and Web.
 * Rejects avatars, sidebar images, recommended posts, unrelated comments, and navigation text.
 */

// Simple deterministic string hash for debugging and payload differentiation
function computeSimpleHash(str) {
  if (!str) return "00000000";
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0; // Convert to 32bit integer
  }
  return Math.abs(hash).toString(16).padStart(8, "0");
}

// Global extractor entrypoint
window.__SOCIAL_GUARD_EXTRACT__ = function() {
  const platform = detectPlatform();
  if (platform === "instagram") {
    return extractInstagramContent();
  } else if (platform === "reddit") {
    return extractRedditContent();
  } else if (platform === "twitter") {
    return extractTwitterContent();
  }
  return extractGenericWebContent(platform);
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
 * 1. INSTAGRAM EXTRACTOR (Scoped to active dialog or post container)
 */
function extractInstagramContent() {
  const url = window.location.href;
  const postId = extractInstagramPostId(url);

  // User manual selection priority
  const selectedText = getWindowSelectionText();
  if (selectedText && selectedText.length > 5) {
    return buildExtractedResult({
      platform: "instagram",
      post_id: postId,
      text: selectedText,
      hashtags: extractHashtags(selectedText),
      image_urls: extractInstagramScopedImages(),
      author: extractInstagramAuthor() || { username: "instagram_user" },
      comments: extractInstagramScopedComments()
    });
  }

  // Scoped Instagram Post Container
  const postContainer = document.querySelector("div[role='dialog'], article, main") || document.body;

  const caption = extractInstagramCaption(postContainer);
  const author = extractInstagramAuthor(postContainer);
  const comments = extractInstagramScopedComments(postContainer);
  const images = extractInstagramScopedImages(postContainer);

  return buildExtractedResult({
    platform: "instagram",
    post_id: postId,
    text: caption || "Instagram post content detected.",
    hashtags: extractHashtags(caption),
    image_urls: images,
    author: author || { username: "instagram_user" },
    comments: comments
  });
}

function extractInstagramPostId(url) {
  const match = url.match(/\/(?:p|reel|tv)\/([a-zA-Z0-9_-]+)/);
  return match ? match[1] : null;
}

function extractInstagramCaption(container) {
  // 1. Check direct h1
  const h1 = container.querySelector("h1");
  if (h1 && h1.innerText.trim().length > 3) {
    return h1.innerText.trim();
  }

  // 2. Check caption inside ul list (first item)
  const captionCandidates = Array.from(container.querySelectorAll("ul li span[dir='auto'], ul li div[dir='auto'], div[role='button'] + div[dir='auto'], span[dir='auto']"))
    .map(el => el.innerText.trim())
    .filter(txt => {
      if (!txt || txt.length < 5) return false;
      const lower = txt.toLowerCase();
      if (lower.startsWith("view all") || lower.startsWith("reply") || lower.startsWith("see translation") || lower === "verified" || lower.startsWith("liked by") || lower.endsWith("ago")) {
        return false;
      }
      return true;
    });

  if (captionCandidates.length > 0) {
    return captionCandidates[0];
  }

  // 3. Fallback to OpenGraph / Meta Description
  const ogDesc = getMetaContent('meta[property="og:description"]') || getMetaContent('meta[name="description"]');
  if (ogDesc) {
    const quoteMatch = ogDesc.match(/:\s*["“'](.+?)["”']\s*$/s) || ogDesc.match(/:\s*(.+)$/s);
    if (quoteMatch && quoteMatch[1]) return quoteMatch[1].trim();
    return ogDesc.trim();
  }

  // 4. Alt text on main post image
  const postImgs = container.querySelectorAll("img[alt]");
  for (const img of postImgs) {
    const alt = img.getAttribute("alt") || "";
    if (alt && alt.includes("Photo by") && alt.includes("with caption")) {
      const match = alt.match(/with caption:\s*(.+)/i);
      if (match && match[1]) return match[1].trim();
    } else if (alt && alt.length > 20 && !alt.startsWith("Profile picture") && !alt.startsWith("Photo by")) {
      return alt.trim();
    }
  }

  return "";
}

function extractInstagramAuthor(container) {
  const scope = container || document.querySelector("div[role='dialog'], article, main") || document.body;
  const headerLinks = Array.from(scope.querySelectorAll("header a, a[role='link'], [data-testid*='user' i], a[href*='/']"));
  
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

  // OpenGraph author fallback
  const ogTitle = getMetaContent('meta[property="og:title"]');
  if (ogTitle) {
    const match = ogTitle.match(/@([a-zA-Z0-9._]+)/) || ogTitle.match(/([a-zA-Z0-9._]+)\s+on\s+Instagram/i);
    if (match && match[1]) {
      return { username: cleanUsername(match[1]), followers: 0, following: 0 };
    }
  }

  return null;
}

function extractInstagramScopedComments(container) {
  const comments = [];
  const scope = container || document.querySelector("div[role='dialog'], article, main") || document.body;
  const commentItems = scope.querySelectorAll("ul li, div[role='button'] + div[dir='auto']");
  
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
        comment_id: `c_ig_${idx + 1}`,
        text: commentBody.slice(0, 300),
        likes: 0
      });
      idx++;
    }
  }

  return comments;
}

function extractInstagramScopedImages(container) {
  const scope = container || document.querySelector("div[role='dialog'], article, main") || document.body;
  const imgs = Array.from(scope.querySelectorAll("article img, div[role='dialog'] img, main img"))
    .map(img => img.currentSrc || img.src)
    .filter(src => {
      if (!src || !isValidHttpUrl(src)) return false;
      const lower = src.toLowerCase();
      if (lower.includes("avatar") || lower.includes("profile_pic") || lower.includes("icon") || lower.includes("badge") || lower.includes("150x150") || lower.includes("50x50")) {
        return false;
      }
      return true;
    });

  return Array.from(new Set(imgs)).slice(0, 3);
}

/**
 * 2. REDDIT EXTRACTOR (Scoped to shreddit-post or post container)
 */
function extractRedditContent() {
  const url = window.location.href;
  const postId = extractRedditPostId(url);

  // User manual selection priority
  const selectedText = getWindowSelectionText();
  if (selectedText && selectedText.length > 5) {
    return buildExtractedResult({
      platform: "reddit",
      post_id: postId,
      text: selectedText,
      hashtags: extractHashtags(selectedText),
      image_urls: extractRedditScopedImages(),
      author: extractRedditAuthor() || { username: "reddit_user" },
      comments: extractRedditScopedComments()
    });
  }

  // Find primary Reddit post element
  const postElement = document.querySelector("shreddit-post, div[data-testid='post-container'], article, .Post") || document.body;

  // 1. Post Title
  let title = "";
  const titleEl = postElement.querySelector("h1, [slot='title'], a[data-testid='post-title'], div[data-adclicklocation='title'], h2");
  if (titleEl) {
    title = titleEl.innerText.trim();
  }

  // 2. Post Body Text
  let bodyText = "";
  const bodyEl = postElement.querySelector("[slot='text-body'], div[data-testid='post-rtjson-content'], div.RichTextJSON-root, div.usertext-body");
  if (bodyEl) {
    const paragraphs = Array.from(bodyEl.querySelectorAll("p, li")).map(p => p.innerText.trim()).filter(Boolean);
    bodyText = paragraphs.length > 0 ? paragraphs.join("\n\n") : bodyEl.innerText.trim();
  }

  let combinedText = title ? (bodyText ? `${title}\n\n${bodyText}` : title) : bodyText;
  if (!combinedText) {
    const ogTitle = getMetaContent('meta[property="og:title"]');
    const ogDesc = getMetaContent('meta[property="og:description"]');
    combinedText = ogTitle ? (ogDesc ? `${ogTitle}\n\n${ogDesc}` : ogTitle) : (document.title || "Reddit post content.");
  }

  const author = extractRedditAuthor(postElement);
  const comments = extractRedditScopedComments();
  const images = extractRedditScopedImages(postElement);

  return buildExtractedResult({
    platform: "reddit",
    post_id: postId,
    text: combinedText,
    hashtags: extractHashtags(combinedText),
    image_urls: images,
    author: author || { username: "reddit_user" },
    comments: comments
  });
}

function extractRedditPostId(url) {
  const match = url.match(/\/comments\/([a-zA-Z0-9]+)/);
  if (match) return match[1];
  const shreddit = document.querySelector("shreddit-post");
  if (shreddit && shreddit.getAttribute("id")) {
    return shreddit.getAttribute("id").replace(/^t3_/, "");
  }
  return null;
}

function extractRedditAuthor(postElement) {
  const scope = postElement || document.querySelector("shreddit-post, div[data-testid='post-container']") || document.body;
  
  if (scope.getAttribute && scope.getAttribute("author")) {
    const auth = scope.getAttribute("author");
    if (auth && auth !== "[deleted]") {
      return { username: cleanUsername(auth), followers: 0, following: 0 };
    }
  }

  const authorEl = scope.querySelector("a[href*='/user/'], a[data-testid='post_author_link'], span[class*='author']");
  if (authorEl) {
    const raw = authorEl.innerText.trim().replace(/^u\//, "").replace(/^r\//, "");
    if (raw && raw.toLowerCase() !== "deleted") {
      return { username: cleanUsername(raw), followers: 0, following: 0 };
    }
  }

  return { username: "reddit_user", followers: 0, following: 0 };
}

function extractRedditScopedComments() {
  const comments = [];
  // Scope specifically to comment elements belonging to the thread
  const commentElements = Array.from(document.querySelectorAll("shreddit-comment, div[data-testid='comment'], div.Comment, div.entry.comment")).slice(0, 8);

  commentElements.forEach((el, idx) => {
    const textEl = el.querySelector("[slot='comment'], div[data-testid='comment-content'], div.md, p");
    const rawText = textEl ? textEl.innerText.trim() : "";

    if (rawText && rawText.length > 5) {
      // Comment author
      const authEl = el.querySelector("a[href*='/user/']");
      const authName = authEl ? authEl.innerText.trim().replace(/^u\//, "") : `commenter_${idx + 1}`;

      comments.push({
        comment_id: `c_rd_${idx + 1}`,
        author_id: cleanUsername(authName),
        text: rawText.slice(0, 400),
        likes: 0
      });
    }
  });

  return comments;
}

function extractRedditScopedImages(postElement) {
  const scope = postElement || document.querySelector("shreddit-post, div[data-testid='post-container'], article") || document.body;
  const imgs = Array.from(scope.querySelectorAll("img"))
    .map(img => img.currentSrc || img.src)
    .filter(src => {
      if (!src || !isValidHttpUrl(src)) return false;
      const lower = src.toLowerCase();
      // Exclude subreddit icons, avatars, emoji reactions, badges, UI elements
      if (lower.includes("avatar") || lower.includes("icon") || lower.includes("badge") || lower.includes("emoji") || lower.includes("styles/communityIcon") || lower.includes("award")) {
        return false;
      }
      return lower.includes("i.redd.it") || lower.includes("preview.redd.it") || lower.includes("external-preview") || lower.includes("redditmedia");
    });

  return Array.from(new Set(imgs)).slice(0, 3);
}

/**
 * 3. TWITTER / X EXTRACTOR (Scoped to primary tweet article)
 */
function extractTwitterContent() {
  const url = window.location.href;
  const postIdMatch = url.match(/\/status\/(\d+)/);
  const postId = postIdMatch ? postIdMatch[1] : null;

  const tweetArticle = document.querySelector("article[data-testid='tweet']") || document.querySelector("article") || document.body;
  
  let tweetText = "";
  const textEl = tweetArticle.querySelector("[data-testid='tweetText']");
  if (textEl) {
    tweetText = textEl.innerText.trim();
  } else {
    tweetText = getMetaContent('meta[property="og:description"]') || document.title || "Twitter content.";
  }

  let authorName = "twitter_user";
  const userEl = tweetArticle.querySelector("[data-testid='User-Name']");
  if (userEl) {
    const handleMatch = userEl.innerText.match(/@([a-zA-Z0-9_]+)/);
    if (handleMatch && handleMatch[1]) authorName = handleMatch[1];
  }

  const imgs = Array.from(tweetArticle.querySelectorAll("[data-testid='tweetPhoto'] img, img[src*='pbs.twimg.com/media']"))
    .map(img => img.currentSrc || img.src)
    .filter(isValidHttpUrl)
    .filter(src => !src.includes("profile_images") && !src.includes("icon"));

  return buildExtractedResult({
    platform: "twitter",
    post_id: postId,
    text: tweetText,
    hashtags: extractHashtags(tweetText),
    image_urls: Array.from(new Set(imgs)).slice(0, 3),
    author: { username: cleanUsername(authorName), followers: 0, following: 0 },
    comments: []
  });
}

/**
 * 4. GENERIC WEB & NEWS EXTRACTOR
 */
function extractGenericWebContent(platform) {
  const selectedText = getWindowSelectionText();
  if (selectedText && selectedText.length > 5) {
    return buildExtractedResult({
      platform: platform,
      post_id: computeSimpleHash(window.location.href),
      text: selectedText,
      hashtags: extractHashtags(selectedText),
      image_urls: extractGenericScopedImages(),
      author: extractGenericAuthor(),
      comments: []
    });
  }

  const ogDesc = getMetaContent('meta[property="og:description"]') || getMetaContent('meta[name="description"]');
  const ogTitle = getMetaContent('meta[property="og:title"]') || getMetaContent('meta[name="twitter:title"]');
  const ogImage = getMetaContent('meta[property="og:image"]') || getMetaContent('meta[name="twitter:image"]');

  let bodyText = "";
  const mainEl = document.querySelector("article, main, [role='main']") || document.body;
  if (mainEl) {
    const paragraphs = Array.from(mainEl.querySelectorAll("p, h1, h2"))
      .map(el => el.innerText.trim())
      .filter(t => t.length > 25 && !t.toLowerCase().includes("cookie") && !t.toLowerCase().includes("privacy") && !t.toLowerCase().includes("terms of service"));
    
    if (paragraphs.length > 0) {
      bodyText = paragraphs.slice(0, 4).join("\n\n");
    }
  }

  const postText = bodyText || ogDesc || ogTitle || document.title || "Web page content.";
  const imgs = extractGenericScopedImages();
  if (ogImage && isValidHttpUrl(ogImage) && !imgs.includes(ogImage)) {
    imgs.unshift(ogImage);
  }

  return buildExtractedResult({
    platform: platform,
    post_id: computeSimpleHash(window.location.href),
    text: postText,
    hashtags: extractHashtags(postText),
    image_urls: imgs.slice(0, 3),
    author: extractGenericAuthor(),
    comments: []
  });
}

function extractGenericScopedImages() {
  const scope = document.querySelector("article, main, [role='main']") || document.body;
  const imgs = Array.from(scope.querySelectorAll("img"))
    .map(img => img.currentSrc || img.src)
    .filter(src => {
      if (!src || !isValidHttpUrl(src)) return false;
      const lower = src.toLowerCase();
      if (lower.includes("avatar") || lower.includes("logo") || lower.includes("icon") || lower.includes("badge") || lower.includes("ad_") || lower.includes("tracking")) {
        return false;
      }
      return true;
    });

  return Array.from(new Set(imgs)).slice(0, 3);
}

function extractGenericAuthor() {
  const metaAuthor = getMetaContent('meta[name="author"]') || getMetaContent('meta[property="article:author"]');
  if (metaAuthor) {
    return { username: cleanUsername(metaAuthor), followers: 0, following: 0 };
  }
  const authorEl = document.querySelector("[rel='author'], .author-name, .byline");
  if (authorEl) {
    const txt = authorEl.innerText.trim().split("\n")[0];
    if (txt) return { username: cleanUsername(txt), followers: 0, following: 0 };
  }
  return { username: "page_author", followers: 0, following: 0 };
}

/**
 * HELPER UTILITIES
 */
function detectPlatform() {
  const host = window.location.hostname.toLowerCase();
  if (host.includes("instagram.com")) return "instagram";
  if (host.includes("reddit.com")) return "reddit";
  if (host.includes("twitter.com") || host.includes("x.com")) return "twitter";
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
  const cleanText = params.text || "No text content available.";
  const textHash = computeSimpleHash(cleanText);

  const debugDiagnostics = {
    platform: params.platform || "generic",
    post_id: params.post_id || null,
    text_hash: textHash,
    text_length: cleanText.length,
    text_preview: cleanText.slice(0, 80),
    author: params.author?.username || "unknown",
    comment_count: Array.isArray(params.comments) ? params.comments.length : 0,
    media_count: Array.isArray(params.image_urls) ? params.image_urls.length : 0,
    media_domains: (params.image_urls || []).map(u => {
      try { return new URL(u).hostname; } catch { return "unknown"; }
    }),
    source_mode: "live_tab"
  };

  console.log("[Social Guard Content Script] LIVE_EXTRACTION_DEBUG:", debugDiagnostics);

  return {
    source: "live_tab",
    platform: params.platform || "generic",
    post_id: params.post_id || null,
    text: cleanText,
    hashtags: params.hashtags || [],
    image_urls: params.image_urls || [],
    author: params.author || { username: "page_author", followers: 0, following: 0 },
    comments: params.comments || [],
    url: window.location.href,
    title: document.title,
    diagnostics: debugDiagnostics
  };
}
