/**
 * Social Guard: High-Precision Multi-Platform Content Extractor (Phase 2)
 * 
 * Supports:
 * 1. X / Twitter (Focal status tweet, author, media, engagement, threaded replies)
 * 2. Reddit (shreddit-post, classic post container, author, media, upvotes, shreddit-comment)
 * 3. Instagram (Dialog modal, standalone post, caption, author, media, likes, comments)
 * 4. Generic Web Pages (Article / Selection fallback with graceful unsupported detection)
 * 
 * Communication protocol:
 * Request:  { action: "EXTRACT_CURRENT_POST" } or { action: "EXTRACT_PAGE_CONTENT" }
 * Response: { success: true, data: NormalizedPost } | { success: false, error: string, platform: string }
 */

// ------------------------------------------------------------------------------
// 1. GLOBAL ENTRYPOINTS & MESSAGE DISPATCHER
// ------------------------------------------------------------------------------

window.__SOCIAL_GUARD_EXTRACT__ = function () {
  return extractCurrentlyViewedPost();
};

if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.onMessage) {
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "EXTRACT_CURRENT_POST" || message.action === "EXTRACT_PAGE_CONTENT") {
      try {
        const result = extractCurrentlyViewedPost();
        sendResponse(result);
      } catch (err) {
        console.error("[Social Guard Content Script] Unhandled extraction error:", err);
        sendResponse({
          success: false,
          error: `Extraction failed: ${err?.message || String(err)}`,
          platform: detectPlatform()
        });
      }
    }
    return true;
  });
}

function extractCurrentlyViewedPost() {
  // Check for restricted / internal pages or incomplete DOM
  if (!document || !document.body) {
    return {
      success: false,
      error: "Page DOM is not ready. Please wait for the page to finish loading.",
      platform: "unknown"
    };
  }

  const platform = detectPlatform();

  if (platform === "twitter") {
    return extractTwitterPost();
  } else if (platform === "reddit") {
    return extractRedditPost();
  } else if (platform === "instagram") {
    return extractInstagramPost();
  } else {
    return extractGenericWebPost(platform);
  }
}

// ------------------------------------------------------------------------------
// 2. PLATFORM 1: X / TWITTER EXTRACTOR
// ------------------------------------------------------------------------------

function extractTwitterPost() {
  const url = window.location.href;
  const statusMatch = window.location.pathname.match(/\/status\/(\d+)/);
  const targetPostId = statusMatch ? statusMatch[1] : null;

  // 1. Locate tweet articles on page
  const tweetArticles = Array.from(document.querySelectorAll("article[data-testid='tweet']"));

  if (tweetArticles.length === 0) {
    // Check if on feed or loading
    const anyArticle = document.querySelector("article");
    if (!anyArticle) {
      return {
        success: false,
        error: "No tweet detected on this page. Please open a tweet or wait for the page to finish loading.",
        platform: "twitter"
      };
    }
  }

  // 2. Identify the focal tweet
  let focalTweet = null;
  if (targetPostId) {
    // Find the specific tweet that matches the URL status ID
    focalTweet = tweetArticles.find(article => {
      const link = article.querySelector(`a[href*="/status/${targetPostId}"]`);
      return link !== null;
    });
  }

  // Fallback: Use the first tweet article in the thread / timeline
  if (!focalTweet) {
    focalTweet = tweetArticles[0] || document.querySelector("article");
  }

  if (!focalTweet) {
    return {
      success: false,
      error: "Could not identify the active tweet container.",
      platform: "twitter"
    };
  }

  // 3. Extract Author (handle + display name)
  let username = "twitter_user";
  let displayName = null;
  const userEl = focalTweet.querySelector("[data-testid='User-Name']");
  if (userEl) {
    const rawText = userEl.innerText || "";
    const handleMatch = rawText.match(/@([a-zA-Z0-9_]+)/);
    if (handleMatch && handleMatch[1]) {
      username = handleMatch[1];
    }
    const lines = rawText.split("\n").map(s => s.trim()).filter(Boolean);
    if (lines.length > 0 && !lines[0].startsWith("@")) {
      displayName = lines[0];
    }
  } else if (statusMatch) {
    // Infer handle from URL path: /<username>/status/<id>
    const userMatch = window.location.pathname.match(/^\/([a-zA-Z0-9_]+)\/status\//);
    if (userMatch && userMatch[1]) {
      username = userMatch[1];
    }
  }

  // 4. Extract Post Text
  let text = "";
  const tweetTextEl = focalTweet.querySelector("[data-testid='tweetText']");
  if (tweetTextEl) {
    text = tweetTextEl.innerText.trim();
  } else {
    // Fallback to meta description if image-only or truncated
    const ogDesc = getMetaContent('meta[property="og:description"]');
    if (ogDesc && ogDesc.length > 5) {
      text = ogDesc;
    }
  }

  // 5. Extract Timestamp
  let timestamp = null;
  const timeEl = focalTweet.querySelector("time");
  if (timeEl && timeEl.getAttribute("datetime")) {
    timestamp = timeEl.getAttribute("datetime");
  }

  // 6. Extract Engagement (Likes, Replies, Retweets)
  let repliesCount = parseMetricCount(
    focalTweet.querySelector("[data-testid='reply'], button[aria-label*='reply'], button[aria-label*='Reply'], [data-testid='reply-count']")
  );
  if (repliesCount === null) {
    const groupButtons = focalTweet.querySelectorAll("[role='group'] button");
    if (groupButtons.length > 0) {
      repliesCount = parseMetricCount(groupButtons[0]);
    }
  }

  const engagement = {
    likes: parseMetricCount(focalTweet.querySelector("[data-testid='like'], [data-testid='unlike'], button[aria-label*='like'], button[aria-label*='Like']")),
    replies: repliesCount,
    reposts: parseMetricCount(focalTweet.querySelector("[data-testid='retweet'], [data-testid='unretweet'], button[aria-label*='repost'], button[aria-label*='retweet']"))
  };

  // 7. Extract Media (Images & Videos)
  const mediaItems = [];
  const tweetPhotos = Array.from(focalTweet.querySelectorAll("[data-testid='tweetPhoto'] img, img[src*='pbs.twimg.com/media']"));
  tweetPhotos.forEach(img => {
    const src = img.currentSrc || img.src;
    if (src && isValidHttpUrl(src) && !src.includes("profile_images") && !src.includes("emoji")) {
      if (!mediaItems.some(m => m.url === src)) {
        mediaItems.push({ url: src, media_type: "image" });
      }
    }
  });

  const videos = Array.from(focalTweet.querySelectorAll("video"));
  videos.forEach(v => {
    const vSrc = v.currentSrc || v.src || v.poster;
    if (vSrc && isValidHttpUrl(vSrc)) {
      if (!mediaItems.some(m => m.url === vSrc)) {
        mediaItems.push({ url: vSrc, media_type: "video" });
      }
    }
  });

  // 8. Extract Comments / Replies (Subsequent tweets on page)
  const comments = [];
  const replyArticles = tweetArticles.filter(art => art !== focalTweet).slice(0, 25);
  replyArticles.forEach((repArt, idx) => {
    const repTextEl = repArt.querySelector("[data-testid='tweetText']");
    const repText = repTextEl ? repTextEl.innerText.trim() : "";
    if (repText && repText.length > 2) {
      let repUser = `commenter_${idx + 1}`;
      const repUserEl = repArt.querySelector("[data-testid='User-Name']");
      if (repUserEl) {
        const uMatch = repUserEl.innerText.match(/@([a-zA-Z0-9_]+)/);
        if (uMatch && uMatch[1]) repUser = uMatch[1];
      }
      const repTimeEl = repArt.querySelector("time");
      const repTime = repTimeEl ? repTimeEl.getAttribute("datetime") : null;
      const repLikes = parseMetricCount(repArt.querySelector("[data-testid='like'], [data-testid='unlike']"));

      comments.push({
        comment_id: `c_tw_${idx + 1}`,
        username: cleanUsername(repUser),
        text: repText.slice(0, 500),
        likes: repLikes,
        timestamp: repTime
      });
    }
  });

  if ((engagement.replies === null || engagement.replies === 0) && comments.length > 0) {
    engagement.replies = comments.length;
  }

  if (!text && mediaItems.length === 0) {
    return {
      success: false,
      error: "Found tweet container, but no readable text or media was detected.",
      platform: "twitter"
    };
  }

  return {
    success: true,
    data: {
      platform: "twitter",
      post_url: url,
      post_id: targetPostId,
      author_username: cleanUsername(username),
      author_display_name: displayName,
      text: text || "Tweet media with no text caption.",
      timestamp: timestamp,
      hashtags: extractHashtags(text),
      engagement: engagement,
      media: mediaItems,
      comments: comments
    }
  };
}

// ------------------------------------------------------------------------------
// 3. PLATFORM 2: REDDIT EXTRACTOR
// ------------------------------------------------------------------------------

function extractRedditPost() {
  const url = window.location.href;
  const postMatch = url.match(/\/comments\/([a-zA-Z0-9]+)/);
  const postIdFromUrl = postMatch ? postMatch[1] : null;

  // 1. Locate primary Reddit post container
  // Modern Reddit uses custom web component <shreddit-post>; classic uses div[data-testid='post-container'] or .Post
  const shredditPost = document.querySelector("shreddit-post");
  const postContainer = shredditPost ||
    document.querySelector("div[data-testid='post-container'], article, .Post, div[id^='t3_']");

  if (!postContainer && !postIdFromUrl) {
    return {
      success: false,
      error: "No Reddit post detected on this page. Please open a discussion thread.",
      platform: "reddit"
    };
  }

  const scope = postContainer || document.body;

  // 2. Post ID
  let postId = postIdFromUrl;
  if (!postId && shredditPost && shredditPost.getAttribute("id")) {
    postId = shredditPost.getAttribute("id").replace(/^t3_/, "");
  }

  // 3. Author
  let authorUsername = "reddit_user";
  if (shredditPost && shredditPost.getAttribute("author")) {
    const rawAuth = shredditPost.getAttribute("author");
    if (rawAuth && rawAuth !== "[deleted]") authorUsername = rawAuth;
  } else {
    const authorEl = scope.querySelector("a[href*='/user/'], [data-testid='post_author_link'], span[class*='author']");
    if (authorEl) {
      const rawAuth = authorEl.innerText.trim().replace(/^u\//, "").replace(/^r\//, "");
      if (rawAuth && rawAuth.toLowerCase() !== "deleted") {
        authorUsername = rawAuth;
      }
    }
  }

  // 4. Post Title & Text
  let title = "";
  if (shredditPost && shredditPost.getAttribute("post-title")) {
    title = shredditPost.getAttribute("post-title").trim();
  }
  if (!title) {
    const titleEl = scope.querySelector("h1, [slot='title'], a[data-testid='post-title'], h2");
    if (titleEl) title = titleEl.innerText.trim();
  }

  let bodyText = "";
  const bodyEl = scope.querySelector("[slot='text-body'], div[data-testid='post-rtjson-content'], div.usertext-body, div.md");
  if (bodyEl) {
    const paragraphs = Array.from(bodyEl.querySelectorAll("p, li")).map(p => p.innerText.trim()).filter(Boolean);
    bodyText = paragraphs.length > 0 ? paragraphs.join("\n\n") : bodyEl.innerText.trim();
  }

  let combinedText = title ? (bodyText ? `${title}\n\n${bodyText}` : title) : bodyText;
  if (!combinedText) {
    const ogTitle = getMetaContent('meta[property="og:title"]');
    const ogDesc = getMetaContent('meta[property="og:description"]');
    combinedText = ogTitle ? (ogDesc ? `${ogTitle}\n\n${ogDesc}` : ogTitle) : (document.title || "");
  }

  // 5. Timestamp
  let timestamp = null;
  if (shredditPost && shredditPost.getAttribute("created-timestamp")) {
    timestamp = shredditPost.getAttribute("created-timestamp");
  } else {
    const timeEl = scope.querySelector("time");
    if (timeEl && timeEl.getAttribute("datetime")) {
      timestamp = timeEl.getAttribute("datetime");
    }
  }

  // 6. Engagement (Score / Upvotes & Comment count)
  let upvotes = null;
  let commentsCount = null;
  if (shredditPost) {
    const rawScore = shredditPost.getAttribute("score");
    if (rawScore !== null && rawScore !== "") {
      const parsed = parseInt(rawScore, 10);
      if (!isNaN(parsed)) upvotes = parsed;
    }
    const rawComments = shredditPost.getAttribute("comment-count") ||
      shredditPost.getAttribute("comments-count") ||
      shredditPost.getAttribute("comments");
    if (rawComments !== null && rawComments !== "") {
      const parsed = parseInt(rawComments, 10);
      if (!isNaN(parsed)) commentsCount = parsed;
    }
  }
  if (upvotes === null) {
    const scoreEl = scope.querySelector("[data-testid='post-vote-arrows'], .score");
    if (scoreEl) upvotes = parseEngagementNumber(scoreEl.innerText);
  }
  if (commentsCount === null) {
    const commentEl = scope.querySelector(
      "a[slot='comment-button'], a[name='comments'], a.comments, [data-testid='comments-count'], [data-testid='comments-button'], faceplate-number[noun='comment'], button[aria-label*='comment'], button[aria-label*='Comment'], a[href*='/comments/']"
    );
    if (commentEl) commentsCount = parseMetricCount(commentEl);
  }
  if (commentsCount === null) {
    const allLinks = Array.from(scope.querySelectorAll("a, button, span, faceplate-tracker"));
    for (const el of allLinks) {
      const txt = (el.innerText || "").trim();
      const m = txt.match(/([\d,.]+\s*[KMkm]?)\s+comments?/i);
      if (m) {
        commentsCount = parseEngagementNumber(m[1]);
        break;
      }
    }
  }

  const engagement = {
    likes: upvotes,
    replies: commentsCount,
    reposts: null
  };

  // 7. Media (Images & Videos)
  const mediaItems = [];
  const redditImgs = Array.from(scope.querySelectorAll("img")).map(img => img.currentSrc || img.src).filter(src => {
    if (!src || !isValidHttpUrl(src)) return false;
    const lower = src.toLowerCase();
    if (lower.includes("avatar") || lower.includes("icon") || lower.includes("badge") || lower.includes("styles/communityicon") || lower.includes("emoji") || lower.includes("award")) {
      return false;
    }
    return lower.includes("i.redd.it") || lower.includes("preview.redd.it") || lower.includes("external-preview") || lower.includes("redditmedia");
  });

  Array.from(new Set(redditImgs)).slice(0, 3).forEach(url => {
    mediaItems.push({ url, media_type: "image" });
  });

  const redditPlayer = scope.querySelector("shreddit-player, video");
  if (redditPlayer) {
    const vSrc = redditPlayer.getAttribute("src") || (redditPlayer.querySelector("source")?.getAttribute("src"));
    if (vSrc && isValidHttpUrl(vSrc)) {
      mediaItems.push({ url: vSrc, media_type: "video" });
    }
  }

  // 8. Comments (shreddit-comment or classic comment divs)
  const comments = [];
  const shredditComments = Array.from(document.querySelectorAll("shreddit-comment, div[data-testid='comment'], div.Comment")).slice(0, 25);
  shredditComments.forEach((cEl, idx) => {
    let cUser = cEl.getAttribute?.("author") || "";
    if (!cUser || cUser === "[deleted]") {
      const uLink = cEl.querySelector("a[href*='/user/']");
      cUser = uLink ? uLink.innerText.trim().replace(/^u\//, "") : `commenter_${idx + 1}`;
    }

    const cScore = cEl.getAttribute?.("score") ? parseInt(cEl.getAttribute("score"), 10) : null;
    const cTextEl = cEl.querySelector("[slot='comment'], div[data-testid='comment-content'], div.md, p");
    const cText = cTextEl ? cTextEl.innerText.trim() : "";

    const cTimeEl = cEl.querySelector("time");
    const cTime = cTimeEl ? cTimeEl.getAttribute("datetime") : null;

    if (cText && cText.length > 2) {
      comments.push({
        comment_id: `c_rd_${idx + 1}`,
        username: cleanUsername(cUser),
        text: cText.slice(0, 500),
        likes: cScore || 0,
        timestamp: cTime
      });
    }
  });

  if ((engagement.replies === null || engagement.replies === 0) && comments.length > 0) {
    engagement.replies = comments.length;
  }

  if (!combinedText && mediaItems.length === 0) {
    return {
      success: false,
      error: "Found Reddit post container, but could not extract text or media.",
      platform: "reddit"
    };
  }

  return {
    success: true,
    data: {
      platform: "reddit",
      post_url: url,
      post_id: postId,
      author_username: cleanUsername(authorUsername),
      author_display_name: null,
      text: combinedText || "Reddit post with media.",
      timestamp: timestamp,
      hashtags: extractHashtags(combinedText),
      engagement: engagement,
      media: mediaItems,
      comments: comments
    }
  };
}

// ------------------------------------------------------------------------------
// 4. PLATFORM 3: INSTAGRAM EXTRACTOR (MODERN DOM + VIEWPORT + REELS + FEED AWARE)
// ------------------------------------------------------------------------------

const IG_SYSTEM_PATHS = new Set([
  "explore", "reels", "direct", "stories", "accounts", "p", "reel", "tv",
  "about", "legal", "developer", "help", "privacy", "settings", "terms",
  "directory", "login", "emails", "support", "home"
]);

function extractInstagramPost() {
  const pageUrl = window.location.href;
  const path = window.location.pathname;

  // 1. Identify post ID from current URL if on a dedicated post or reel page
  const urlMatch = path.match(/\/(?:p|reel|tv|reels)(?:\/videos)?\/([a-zA-Z0-9_-]+)/i);
  let postId = urlMatch ? urlMatch[1] : null;
  let postUrl = postId ? `https://www.instagram.com/p/${postId}/` : pageUrl;

  // 2. Identify the active container
  // Checks for: Modal dialog -> Single post layout -> Viewport-centered feed/reel card
  const activeContainer = findActiveInstagramContainer();

  if (!activeContainer && !postId) {
    return {
      success: false,
      error: "No Instagram post detected. Please open a post, reel, or scroll to a post in the feed.",
      platform: "instagram"
    };
  }

  const scope = activeContainer || document.querySelector("main") || document.body;

  // If on feed, extract post ID and canonical permalink from links within the active post card
  if (!postId) {
    const postLink = scope.querySelector("a[href*='/p/'], a[href*='/reel/']");
    if (postLink) {
      const linkHref = postLink.getAttribute("href") || "";
      const m = linkHref.match(/\/(?:p|reel)\/([a-zA-Z0-9_-]+)/);
      if (m && m[1]) {
        postId = m[1];
        postUrl = `https://www.instagram.com/p/${postId}/`;
      }
    }
  }

  // 3. Extract Author
  const authorInfo = extractInstagramAuthor(scope);
  const authorUsername = authorInfo.username;
  const authorDisplayName = authorInfo.displayName;

  // 4. Extract Caption / Post text
  const caption = extractInstagramCaption(scope, authorUsername);

  // 5. Extract Timestamp
  const timestamp = extractInstagramTimestamp(scope);

  // 6. Extract Engagement (Likes & Comments count)
  const engagement = extractInstagramEngagement(scope);

  // 7. Extract Media (Images & Videos)
  const mediaItems = extractInstagramMedia(scope);

  // 8. Extract Comments
  const comments = extractInstagramComments(scope, authorUsername);
  if ((engagement.replies === null || engagement.replies === 0) && comments.length > 0) {
    engagement.replies = comments.length;
  }

  if (!caption && mediaItems.length === 0) {
    return {
      success: false,
      error: "Found Instagram post container, but could not extract caption or media. Please ensure the post has finished loading.",
      platform: "instagram"
    };
  }

  return {
    success: true,
    data: {
      platform: "instagram",
      post_url: postUrl,
      post_id: postId,
      author_username: cleanUsername(authorUsername),
      author_display_name: authorDisplayName,
      text: caption || "Instagram post with media.",
      timestamp: timestamp,
      hashtags: extractHashtags(caption),
      engagement: engagement,
      media: mediaItems,
      comments: comments
    }
  };
}

function findActiveInstagramContainer() {
  // A. Check for open Dialog Modal
  const modal = document.querySelector("div[role='dialog']");
  if (modal) return modal;

  // B. Check for dedicated single post/reel page
  const isPostPage = /\/(?:p|reel|tv)\/([a-zA-Z0-9_-]+)/i.test(window.location.pathname);
  if (isPostPage) {
    const article = document.querySelector("article");
    if (article) return article;
    const mainSection = document.querySelector("main section, main");
    if (mainSection) return mainSection;
  }

  // C. Feed / Reels view: detect post container closest to vertical viewport center
  const candidates = Array.from(document.querySelectorAll(
    "article, main section > div > div > div, main div[style*='max-width'], div[role='presentation']"
  ));

  const validCards = candidates.filter(el => {
    const rect = el.getBoundingClientRect();
    if (rect.height < 150 || rect.width < 200) return false;
    if (rect.height > window.innerHeight * 3) return false;
    const hasMedia = el.querySelector("img, video");
    const hasPostLinkOrAction = el.querySelector(
      "a[href*='/p/'], a[href*='/reel/'], svg[aria-label*='Like' i], svg[aria-label*='Comment' i], section"
    );
    return Boolean(hasMedia && hasPostLinkOrAction);
  });

  if (validCards.length > 0) {
    const centerY = window.innerHeight / 2;
    validCards.sort((a, b) => {
      const rA = a.getBoundingClientRect();
      const rB = b.getBoundingClientRect();
      const distA = Math.abs((rA.top + rA.bottom) / 2 - centerY);
      const distB = Math.abs((rB.top + rB.bottom) / 2 - centerY);
      return distA - distB;
    });
    return validCards[0];
  }

  return document.querySelector("article") || document.querySelector("main");
}

function extractInstagramAuthor(scope) {
  let username = "instagram_user";
  let displayName = null;

  // 1. Check header links inside the post container
  const candidateLinks = Array.from(scope.querySelectorAll(
    "header a[role='link'], header a, h2 a, h3 a, a[role='link'][href^='/']"
  ));

  for (const link of candidateLinks) {
    const href = (link.getAttribute("href") || "").trim();
    const cleanHref = href.replace(/^\/+|\/+$/g, "");
    if (cleanHref && !cleanHref.includes("/") && !cleanHref.includes("?") && !IG_SYSTEM_PATHS.has(cleanHref.toLowerCase())) {
      const txt = (link.innerText || link.textContent || "").trim();
      const uText = txt && !txt.includes("\n") && !txt.includes("•") ? txt : cleanHref;
      username = cleanUsername(uText);
      break;
    }
  }

  // 2. Check Reels overlay author link
  if (username === "instagram_user") {
    const reelsAuthorLink = scope.querySelector("div[class*='reels'] a[role='link'], div[class*='overlay'] a[role='link'], a[href^='/'][role='link']");
    if (reelsAuthorLink) {
      const cleanHref = (reelsAuthorLink.getAttribute("href") || "").replace(/^\/+|\/+$/g, "");
      if (cleanHref && !cleanHref.includes("/") && !cleanHref.includes("?") && !IG_SYSTEM_PATHS.has(cleanHref.toLowerCase())) {
        username = cleanUsername(cleanHref);
      }
    }
  }

  // 3. Fallback from URL pathname (e.g. /username/p/postId/)
  if (username === "instagram_user") {
    const pathMatch = window.location.pathname.match(/^\/([a-zA-Z0-9._]+)\/(?:p|reel|tv)\//);
    if (pathMatch && pathMatch[1] && !IG_SYSTEM_PATHS.has(pathMatch[1].toLowerCase())) {
      username = cleanUsername(pathMatch[1]);
    }
  }

  // 4. Fallback from og:title meta tag
  if (username === "instagram_user") {
    const ogTitle = getMetaContent('meta[property="og:title"]');
    if (ogTitle) {
      const match = ogTitle.match(/@([a-zA-Z0-9._]+)/) ||
                    ogTitle.match(/^([a-zA-Z0-9._]+)\s+on\s+Instagram/i) ||
                    ogTitle.match(/^(.+?)\s*\(@([a-zA-Z0-9._]+)\)/);
      if (match) {
        if (match[2]) {
          displayName = match[1].trim();
          username = cleanUsername(match[2]);
        } else if (match[1]) {
          username = cleanUsername(match[1]);
        }
      }
    }
  }

  return { username, displayName };
}

function extractInstagramCaption(scope, authorUsername) {
  let caption = "";

  // Strategy 1: Look for h1 element (primary post / reel caption)
  const h1 = scope.querySelector("h1");
  if (h1) {
    const h1Text = (h1.innerText || h1.textContent || "").trim();
    if (h1Text && h1Text.length > 5 && !h1Text.toLowerCase().includes("instagram")) {
      caption = h1Text;
    }
  }

  // Strategy 2: Look for dedicated caption containers
  if (!caption) {
    const captionContainer = scope.querySelector("div._a9zs, span._aaco, div[class*='caption' i]");
    if (captionContainer) {
      caption = (captionContainer.innerText || captionContainer.textContent || "").trim();
    }
  }

  // Strategy 3: Find span or div near the author's handle
  if (!caption && authorUsername && authorUsername !== "instagram_user") {
    const allLinks = Array.from(scope.querySelectorAll("a[role='link']"));
    const authorLink = allLinks.find(a => (a.innerText || "").trim().toLowerCase() === authorUsername.toLowerCase());
    if (authorLink) {
      const parentRow = authorLink.closest("div, li, span");
      if (parentRow) {
        const textSpans = Array.from(parentRow.querySelectorAll("span[dir='auto'], div[dir='auto']"));
        for (const sp of textSpans) {
          const txt = (sp.innerText || "").trim();
          if (txt && txt.length > 5 && txt.toLowerCase() !== authorUsername.toLowerCase() && !txt.startsWith("Verified")) {
            caption = txt;
            break;
          }
        }
      }
    }
  }

  // Strategy 4: Filter candidate strings inside scope, ignoring navigation & interface elements
  if (!caption) {
    const candidates = Array.from(scope.querySelectorAll("span[dir='auto'], div[dir='auto']"))
      .map(el => (el.innerText || "").trim())
      .filter(txt => {
        if (!txt || txt.length < 5) return false;
        const lower = txt.toLowerCase();
        if (lower.startsWith("view all") || lower.startsWith("reply") || lower.startsWith("see translation") ||
            lower === "verified" || lower.startsWith("liked by") || lower.startsWith("follow") ||
            lower === "search" || lower === "explore" || lower === "reels" || lower === "home" ||
            lower === "messages" || lower === "notifications" || lower === "create" || lower === "profile") {
          return false;
        }
        return true;
      });
    if (candidates.length > 0) {
      caption = candidates[0];
    }
  }

  // Strategy 5: Meta tag og:description fallback (un-truncated original caption)
  const ogDesc = getMetaContent('meta[property="og:description"]');
  if (ogDesc) {
    const quoteMatch = ogDesc.match(/:\s*["“']([\s\S]+?)["”']\s*$/) || ogDesc.match(/:\s*(.+)$/s);
    const metaCaption = quoteMatch && quoteMatch[1] ? quoteMatch[1].trim() : "";
    if (metaCaption && (!caption || caption.length < metaCaption.length || caption.endsWith("...") || caption.endsWith("more"))) {
      caption = metaCaption;
    }
  }

  // Clean trailing "... more" or "more" buttons text
  if (caption) {
    caption = caption.replace(/\s*\.{3}\s*more$/i, "").replace(/\s+more$/i, "").trim();
  }

  return caption;
}

function extractInstagramTimestamp(scope) {
  const timeEl = scope.querySelector("time");
  if (timeEl) {
    return timeEl.getAttribute("datetime") || timeEl.getAttribute("title") || timeEl.innerText.trim();
  }
  return null;
}

function extractInstagramEngagement(scope) {
  let likes = null;
  let commentsCount = null;

  // 1. Likes from DOM
  const likeEl = scope.querySelector("section a[href*='/liked_by/'] span, section span:has(> svg[aria-label*='Like' i])");
  if (likeEl) {
    likes = parseEngagementNumber(likeEl.innerText);
  }
  if (likes === null) {
    const allSpans = Array.from(scope.querySelectorAll("section span, div span, button span"));
    for (const sp of allSpans) {
      const txt = (sp.innerText || "").trim();
      const m = txt.match(/([\d,.]+\s*[KMkm]?)\s+likes?/i);
      if (m) {
        likes = parseEngagementNumber(m[1]);
        break;
      }
      const likedByMatch = txt.match(/liked\s+by.+and\s+([\d,.]+\s*[KMkm]?)\s+others?/i);
      if (likedByMatch) {
        likes = (parseEngagementNumber(likedByMatch[1]) || 0) + 1;
        break;
      }
    }
  }

  // 2. Comments count from DOM
  const allElements = Array.from(scope.querySelectorAll("span, button, a"));
  for (const el of allElements) {
    const txt = (el.innerText || el.textContent || "").trim();
    const m = txt.match(/view\s+all\s+([\d,.]+\s*[KMkm]?)\s+comments/i) || txt.match(/^([\d,.]+\s*[KMkm]?)\s+comments?$/i);
    if (m) {
      commentsCount = parseEngagementNumber(m[1]);
      break;
    }
  }

  // 3. Fallback to og:description meta tag
  const ogMetaDesc = getMetaContent('meta[property="og:description"]');
  if (ogMetaDesc) {
    const countMatch = ogMetaDesc.match(/([\d,.]+[KMkm]?)\s+likes?,\s+([\d,.]+[KMkm]?)\s+comments?/i);
    if (countMatch) {
      if (likes === null) likes = parseEngagementNumber(countMatch[1]);
      if (commentsCount === null) commentsCount = parseEngagementNumber(countMatch[2]);
    }
  }

  return {
    likes: likes,
    replies: commentsCount,
    reposts: null
  };
}

function extractInstagramMedia(scope) {
  const mediaItems = [];
  const seenUrls = new Set();

  // 1. Extract Images
  const imgs = Array.from(scope.querySelectorAll("img"));
  imgs.forEach(img => {
    const rect = img.getBoundingClientRect();
    if (rect.width > 0 && rect.width < 80 && rect.height > 0 && rect.height < 80) return;

    let src = img.currentSrc || img.src || "";
    // If srcset exists, take highest-res candidate
    const srcset = img.getAttribute("srcset");
    if (srcset) {
      const parts = srcset.split(",").map(s => s.trim().split(" "));
      if (parts.length > 0) {
        const best = parts[parts.length - 1][0];
        if (best && isValidHttpUrl(best)) src = best;
      }
    }

    if (!src || !isValidHttpUrl(src)) return;
    const lower = src.toLowerCase();
    if (lower.includes("profile_pic") || lower.includes("avatar") || lower.includes("150x150") || lower.includes("50x50") || lower.includes("emoji")) {
      return;
    }

    if (!seenUrls.has(src)) {
      seenUrls.add(src);
      mediaItems.push({ url: src, media_type: "image" });
    }
  });

  // 2. Extract Videos
  const videos = Array.from(scope.querySelectorAll("video"));
  videos.forEach(v => {
    // If poster image is available, extract thumbnail image (vital for OCR and image analysis)
    const poster = v.getAttribute("poster") || v.poster;
    if (poster && isValidHttpUrl(poster) && !seenUrls.has(poster)) {
      seenUrls.add(poster);
      mediaItems.push({ url: poster, media_type: "image" });
    }

    const vSrc = v.currentSrc || v.src;
    if (vSrc && isValidHttpUrl(vSrc) && !seenUrls.has(vSrc)) {
      seenUrls.add(vSrc);
      mediaItems.push({ url: vSrc, media_type: "video" });
    }
  });

  return mediaItems.slice(0, 5);
}

function extractInstagramComments(scope, authorUsername) {
  const comments = [];
  const rows = Array.from(scope.querySelectorAll("div[role='button'], div[role='listitem'], ul li, div[class*='Comment' i]"));
  const seenComments = new Set();

  for (const row of rows) {
    if (comments.length >= 25) break;

    const uLink = row.querySelector("h3 a, a[role='link'][href^='/'], a[href^='/']");
    if (!uLink) continue;

    const uHref = (uLink.getAttribute("href") || "").replace(/^\/+|\/+$/g, "");
    if (!uHref || IG_SYSTEM_PATHS.has(uHref.toLowerCase())) continue;

    const commenter = cleanUsername(uLink.innerText.trim() || uHref);
    if (authorUsername && commenter.toLowerCase() === authorUsername.toLowerCase()) continue;

    const textEl = row.querySelector("span[dir='auto'], div[dir='auto']");
    const cText = textEl ? textEl.innerText.trim() : "";
    if (!cText || cText.length < 2 || cText.startsWith("View all") || cText.startsWith("Reply") || seenComments.has(cText)) {
      continue;
    }

    seenComments.add(cText);
    const timeEl = row.querySelector("time");
    const cTime = timeEl ? timeEl.getAttribute("datetime") : null;

    comments.push({
      comment_id: `c_ig_${comments.length + 1}`,
      username: commenter,
      text: cText.slice(0, 500),
      likes: null,
      timestamp: cTime
    });
  }

  return comments;
}

// ------------------------------------------------------------------------------
// 5. PLATFORM 4: GENERIC WEB / FALLBACK EXTRACTOR
// ------------------------------------------------------------------------------

function extractGenericWebPost(platform) {
  // 1. Check user text selection
  const selectedText = window.getSelection ? window.getSelection().toString().trim() : "";
  if (selectedText && selectedText.length > 10) {
    return {
      success: true,
      data: {
        platform: "generic",
        post_url: window.location.href,
        post_id: null,
        author_username: extractGenericAuthor(),
        author_display_name: null,
        text: selectedText,
        timestamp: null,
        hashtags: extractHashtags(selectedText),
        engagement: { likes: null, replies: null, reposts: null },
        media: [],
        comments: []
      }
    };
  }

  // 2. Check for structured article or main container
  const articleEl = document.querySelector("article, main, [role='main']");
  let bodyText = "";
  if (articleEl) {
    const paragraphs = Array.from(articleEl.querySelectorAll("p, h1, h2"))
      .map(p => p.innerText.trim())
      .filter(t => t.length > 25 && !t.toLowerCase().includes("cookie") && !t.toLowerCase().includes("privacy"));
    if (paragraphs.length > 0) {
      bodyText = paragraphs.slice(0, 5).join("\n\n");
    }
  }

  if (!bodyText) {
    bodyText = getMetaContent('meta[property="og:description"]') || getMetaContent('meta[name="description"]');
  }

  if (!bodyText || bodyText.length < 15) {
    return {
      success: false,
      error: "Unsupported website or no readable article/post content detected on this page.",
      platform: "generic"
    };
  }

  const genericComments = [];
  const commentElements = Array.from(
    document.querySelectorAll(".comment-body, .comment-content, .comment-text, [data-testid='comment'], #comments li, .comments-area .comment")
  ).slice(0, 25);
  commentElements.forEach((cEl, idx) => {
    const txt = (cEl.innerText || "").trim();
    if (txt.length > 5) {
      genericComments.push({
        comment_id: `c_gen_${idx + 1}`,
        username: `commenter_${idx + 1}`,
        text: txt.slice(0, 500),
        likes: null,
        timestamp: null
      });
    }
  });

  let genReplies = parseMetricCount(
    document.querySelector(".comments-count, .comment-count, a[href*='#comments'], [aria-label*='comment']")
  );
  if ((genReplies === null || genReplies === 0) && genericComments.length > 0) {
    genReplies = genericComments.length;
  }

  return {
    success: true,
    data: {
      platform: "generic",
      post_url: window.location.href,
      post_id: null,
      author_username: extractGenericAuthor(),
      author_display_name: null,
      text: bodyText,
      timestamp: null,
      hashtags: extractHashtags(bodyText),
      engagement: { likes: null, replies: genReplies, reposts: null },
      media: [],
      comments: genericComments
    }
  };
}

// ------------------------------------------------------------------------------
// 6. HELPER UTILITIES
// ------------------------------------------------------------------------------

function detectPlatform() {
  const host = window.location.hostname.toLowerCase();
  if (host.includes("twitter.com") || host.includes("x.com")) return "twitter";
  if (host.includes("reddit.com")) return "reddit";
  if (host.includes("instagram.com")) return "instagram";
  return "generic";
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
  if (!name) return "user";
  return name
    .replace(/^@+/, "")
    .replace(/^u\//i, "")
    .replace(/^r\//i, "")
    .trim()
    .slice(0, 50);
}

function parseMetricCount(el) {
  if (!el) return null;
  const aria = el.getAttribute("aria-label") || el.getAttribute("title") || "";
  if (aria) {
    const match = aria.match(/([\d,.]+\s*[KMkm]?)/);
    if (match) {
      const num = parseEngagementNumber(match[1]);
      if (num !== null) return num;
    }
    const lowerAria = aria.toLowerCase().trim();
    if (lowerAria === "reply" || lowerAria === "replies" || lowerAria === "comment" || lowerAria === "comments") {
      return 0;
    }
  }

  const txt = (el.innerText || el.textContent || "").trim();
  if (txt) {
    const match = txt.match(/([\d,.]+\s*[KMkm]?)/);
    if (match) {
      const num = parseEngagementNumber(match[1]);
      if (num !== null) return num;
    }
  }

  // Check child spans or numbers
  const childNum = el.querySelector("span, faceplate-number, div");
  if (childNum) {
    const childText = (childNum.innerText || childNum.textContent || "").trim();
    const match = childText.match(/([\d,.]+\s*[KMkm]?)/);
    if (match) return parseEngagementNumber(match[1]);
  }

  return null;
}

function parseEngagementNumber(text) {
  if (!text || typeof text !== "string") return null;
  const clean = text.trim().replace(/,/g, "");
  const match = clean.match(/([\d.]+)\s*([KMkm])?/i);
  if (!match) {
    const intMatch = clean.match(/\d+/);
    return intMatch ? parseInt(intMatch[0], 10) : null;
  }
  let val = parseFloat(match[1]);
  if (isNaN(val)) return null;
  const unit = match[2] ? match[2].toUpperCase() : "";
  if (unit === "K") val *= 1000;
  if (unit === "M") val *= 1000000;
  return Math.round(val);
}

function extractGenericAuthor() {
  const metaAuthor = getMetaContent('meta[name="author"]') || getMetaContent('meta[property="article:author"]');
  if (metaAuthor) return cleanUsername(metaAuthor);
  const authorEl = document.querySelector("[rel='author'], .author-name, .byline");
  if (authorEl) return cleanUsername(authorEl.innerText.split("\n")[0]);
  return "page_author";
}
