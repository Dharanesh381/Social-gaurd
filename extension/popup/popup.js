/**
 * Social Guard: Extension Controller (Phase 6)
 * Supports REAL POST mode (live extracted browser post) and DEMO mode (academic test presets).
 * Displays target post information, credibility verdict, claims & fact-check evidence,
 * module breakdowns, orthogonal AI detection, XAI explanations, animated pipeline loading steps,
 * and categorized error diagnostics.
 */

import { SocialGuardApiClient, SocialGuardApiError } from "./api_client.js";

// ==============================================================================
// 1. ACADEMIC TEST PRESET SCENARIOS (Demarcated Demo Data)
// ==============================================================================

const TEST_PRESETS = {
  real: {
    platform: "twitter",
    post_url: "https://x.com/science_reporter/status/1888223344",
    text: "NASA planetary science rovers confirm detection of subsurface water ice reserves on Mars through deep radar soundings. #Space #Mars #NASA",
    hashtags: ["#Space", "#Mars", "#NASA"],
    media: [
      { url: "https://example.com/mars_chart.png", media_type: "image" }
    ],
    author: {
      username: "science_reporter",
      account_age_days: 1400,
      followers: 24000,
      following: 380,
      posts_per_day: 2.2,
      comments_per_day: 3.5,
      engagement_rate: 0.045,
      duplicate_content_ratio: 0.01,
      hashtag_repetition_rate: 0.08
    },
    engagement: {
      likes: 12500,
      replies: 890,
      reposts: 3400
    },
    comments: [
      {
        comment_id: "c_r1",
        text: "Incredible discovery if confirmed by independent peer review! 🚀",
        likes: 12,
        emojis: ["🚀"]
      },
      {
        comment_id: "c_r2",
        text: "Does this match the earlier radar reflection datasets?",
        likes: 5,
        emojis: []
      }
    ]
  },
  uncertain: {
    platform: "reddit",
    post_url: "https://reddit.com/r/science/comments/superconductor_claim/",
    text: "Local researchers claim to have created a stable room-temperature superconductor in a prototype laboratory setup.",
    hashtags: ["#Physics", "#Superconductor"],
    media: [],
    author: {
      username: "curious_physicist",
      account_age_days: 650,
      followers: 320,
      following: 190,
      posts_per_day: 1.1,
      comments_per_day: 2.0,
      engagement_rate: 0.03,
      duplicate_content_ratio: 0.02,
      hashtag_repetition_rate: 0.05
    },
    engagement: {
      likes: 450,
      replies: 88,
      reposts: 0
    },
    comments: [
      {
        comment_id: "c_u1",
        text: "Exciting if true, but we need independent lab replication before celebrating.",
        likes: 7,
        emojis: []
      }
    ]
  },
  fake: {
    platform: "twitter",
    post_url: "https://x.com/super_cure_blast_bot/status/99911223344",
    text: "BREAKING: Drinking boiling bleach completely cures all respiratory viral infections in 5 minutes! Share to save lives! #MiracleCure #HealthAlert",
    hashtags: ["#MiracleCure", "#HealthAlert"],
    media: [],
    author: {
      username: "super_cure_blast_bot",
      account_age_days: 1,
      followers: 2,
      following: 4800,
      posts_per_day: 450.0,
      comments_per_day: 650.0,
      engagement_rate: 0.0001,
      duplicate_content_ratio: 0.96,
      hashtag_repetition_rate: 0.92
    },
    engagement: {
      likes: 18,
      replies: 520,
      reposts: 12
    },
    comments: [
      {
        comment_id: "c_f1",
        text: "BUY THE BLEACH MIRACLE PROTOCOL NOW AT WWW.SCAM-CURE.FAKE 💊🚨",
        likes: 0,
        emojis: ["💊", "🚨"]
      },
      {
        comment_id: "c_f2",
        text: "BUY THE BLEACH MIRACLE PROTOCOL NOW AT WWW.SCAM-CURE.FAKE 💊🚨",
        likes: 0,
        emojis: ["💊", "🚨"]
      }
    ]
  }
};

let currentMode = "real"; // "real" | "preset"
let rawExtractedData = null; // Store raw live extraction data
let activePayload = null;    // Post payload prepared for UI / analysis

function computeSimpleHash(str) {
  if (!str) return "00000000";
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash |= 0;
  }
  return Math.abs(hash).toString(16).padStart(8, "0");
}

/**
 * Validate and map an extracted post or preset into the strict AnalysisRequest schema.
 * Prevents fabricated values: unprovided fields remain null or empty lists.
 */
export function validateAndBuildAnalysisPayload(data, isDemo = false) {
  if (!data || typeof data !== "object") {
    throw new Error("No post data provided for verification.");
  }

  // 1. Post Text Validation
  const text = (data.text || "").trim();
  if (!text || text.length < 1) {
    throw new Error("Post text cannot be empty. Please open a social media post with readable content.");
  }
  if (text.length > 50000) {
    throw new Error("Post text exceeds maximum permitted length (50,000 characters).");
  }

  // 2. Platform Normalization
  let platform = (data.platform || "generic").toLowerCase().trim();
  if (platform === "x") platform = "twitter";

  // 3. Author Validation (Do NOT fabricate if unavailable)
  let author = null;
  const username = data.author?.username || data.author_username;
  if (username && typeof username === "string" && username.trim().length > 0) {
    const cleanUsername = username.trim().slice(0, 150);
    author = {
      username: cleanUsername,
      account_age_days: data.author?.account_age_days != null ? Math.max(0, parseInt(data.author.account_age_days, 10)) : null,
      account_created_at: null,
      followers: data.author?.followers != null ? Math.max(0, parseInt(data.author.followers, 10)) : 0,
      following: data.author?.following != null ? Math.max(0, parseInt(data.author.following, 10)) : 0,
      posts_per_day: data.author?.posts_per_day != null ? Math.max(0, parseFloat(data.author.posts_per_day)) : 0.0,
      comments_per_day: data.author?.comments_per_day != null ? Math.max(0, parseFloat(data.author.comments_per_day)) : 0.0,
      engagement_rate: data.author?.engagement_rate != null ? Math.max(0, parseFloat(data.author.engagement_rate)) : null,
      duplicate_content_ratio: data.author?.duplicate_content_ratio != null ? Math.min(1.0, Math.max(0, parseFloat(data.author.duplicate_content_ratio))) : null,
      hashtag_repetition_rate: data.author?.hashtag_repetition_rate != null ? Math.min(1.0, Math.max(0, parseFloat(data.author.hashtag_repetition_rate))) : null
    };

    if (!isDemo && author.engagement_rate === null && data.engagement?.likes != null && data.engagement?.replies != null) {
      author.engagement_rate = Math.min(1.0, (data.engagement.likes + data.engagement.replies) / 5000);
    }
  }

  // 4. Media Sanitization
  const validMedia = [];
  const rawMedia = data.media || [];
  if (Array.isArray(rawMedia)) {
    rawMedia.forEach(m => {
      if (!m || !m.url || typeof m.url !== "string") return;
      const url = m.url.trim();
      if (!url.startsWith("http://") && !url.startsWith("https://")) return;

      let mediaType = "image";
      if (m.media_type === "video") mediaType = "video";
      else if (m.media_type === "audio") mediaType = "audio";
      else if (m.media_type === "other") mediaType = "other";

      validMedia.push({
        url: url,
        media_type: mediaType,
        ocr_extracted_text: m.ocr_extracted_text || null,
        perceptual_hash: m.perceptual_hash || null
      });
    });
  }

  // 5. Hashtags Sanitization
  const validHashtags = [];
  const rawHashtags = data.hashtags || [];
  if (Array.isArray(rawHashtags)) {
    rawHashtags.forEach(tag => {
      if (!tag || typeof tag !== "string") return;
      const cleaned = tag.trim();
      if (cleaned.length > 0) {
        validHashtags.push(cleaned.startsWith("#") ? cleaned : `#${cleaned}`);
      }
    });
  }

  // 6. Comments Sanitization
  const validComments = [];
  const rawComments = data.comments || [];
  if (Array.isArray(rawComments)) {
    rawComments.forEach((c, idx) => {
      if (!c || !c.text || typeof c.text !== "string" || c.text.trim().length === 0) return;
      const commentText = c.text.trim().slice(0, 10000);
      const commentId = c.comment_id ? String(c.comment_id).slice(0, 100) : `c_${idx + 1}`;
      const authorId = c.author_id || c.username ? String(c.author_id || c.username).trim().slice(0, 100) : null;
      const likes = Math.max(0, parseInt(c.likes, 10) || 0);

      let commentTs = null;
      if (c.timestamp && !isNaN(Date.parse(c.timestamp))) {
        try {
          commentTs = new Date(c.timestamp).toISOString();
        } catch (_) {
          commentTs = null;
        }
      }

      let emojis = Array.isArray(c.emojis) ? c.emojis : [];
      if (emojis.length === 0) {
        const found = commentText.match(/\p{Extended_Pictographic}/gu) || [];
        emojis = Array.from(new Set(found));
      }

      validComments.push({
        comment_id: commentId,
        text: commentText,
        author_id: authorId,
        likes: likes,
        timestamp: commentTs,
        emojis: emojis,
        emoji_count: emojis.length
      });
    });
  }

  // 7. Post Timestamp Validation
  let postTimestamp = null;
  if (data.timestamp && !isNaN(Date.parse(data.timestamp))) {
    try {
      postTimestamp = new Date(data.timestamp).toISOString();
    } catch (_) {
      postTimestamp = null;
    }
  }

  const modePrefix = isDemo ? "demo" : "real";
  const requestId = `sg_${modePrefix}_${Date.now()}_${computeSimpleHash(text)}`;

  return {
    request_id: requestId,
    post: {
      post_id: data.post_id ? String(data.post_id).slice(0, 100) : null,
      platform: platform,
      text: text,
      hashtags: validHashtags,
      media: validMedia,
      timestamp: postTimestamp,
      author: author,
      comments: validComments
    },
    custom_weights: null
  };
}

// ==============================================================================
// 2. DOM CONTROLLER & EVENT WIRING
// ==============================================================================

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", async () => {
    const statusBadge = document.getElementById("backend-status-badge");
    const sourceBadge = document.getElementById("content-source-badge");
    const postTextInput = document.getElementById("post-text-input");
    const platformChip = document.getElementById("detected-platform");
    const authorChip = document.getElementById("detected-author");
    const commentsChip = document.getElementById("detected-comments-count");
    const mediaChip = document.getElementById("detected-media-count");
    const engagementChip = document.getElementById("detected-engagement");

    const modeRealBtn = document.getElementById("mode-real-btn");
    const modeDemoBtn = document.getElementById("mode-demo-btn");
    const demoPresetsContainer = document.getElementById("demo-presets-container");

    const presetRealBtn = document.getElementById("preset-real-btn");
    const presetUncertainBtn = document.getElementById("preset-uncertain-btn");
    const presetFakeBtn = document.getElementById("preset-fake-btn");
    const extractPageBtn = document.getElementById("extract-page-btn");
    const runVerifyBtn = document.getElementById("run-verify-btn");

    const loadingSpinner = document.getElementById("loading-spinner");
    const loadingStageLabel = document.getElementById("loading-stage-label");

    const errorBox = document.getElementById("error-box");
    const errorBoxTitle = document.getElementById("error-box-title");
    const errorCategoryTag = document.getElementById("error-category-tag");
    const errorMessage = document.getElementById("error-message");
    const errorActionHint = document.getElementById("error-action-hint");

    const resultsContainer = document.getElementById("results-container");

    // 1. Initial Health check
    await refreshBackendStatus();

    // 2. Initial Mode Selection & Extraction on Popup Open (Real Mode)
    switchMode("real");

    // Backend Health check
    async function refreshBackendStatus() {
      statusBadge.innerText = "Connecting...";
      statusBadge.className = "badge-status badge-connecting";
      const health = await SocialGuardApiClient.checkHealth();
      if (health.status === "ok" || health.status === "healthy") {
        statusBadge.innerText = "API Online";
        statusBadge.className = "badge-status badge-online";
      } else {
        statusBadge.innerText = "API Offline (Port 8000)";
        statusBadge.className = "badge-status badge-offline";
      }
    }

    // Mode Switcher Logic
    function switchMode(newMode) {
      currentMode = newMode;
      errorBox.classList.add("hidden");
      resultsContainer.classList.add("hidden");

      if (newMode === "real") {
        modeRealBtn.classList.add("active");
        modeRealBtn.setAttribute("aria-selected", "true");
        modeDemoBtn.classList.remove("active");
        modeDemoBtn.setAttribute("aria-selected", "false");
        demoPresetsContainer.classList.add("hidden");
        extractPageBtn.classList.remove("hidden");

        setSourceBadge("live", "REAL POST MODE");

        if (rawExtractedData) {
          applyExtractedData(rawExtractedData);
        } else {
          attemptLiveTabExtraction(true);
        }
      } else {
        // Demo Mode
        modeDemoBtn.classList.add("active");
        modeDemoBtn.setAttribute("aria-selected", "true");
        modeRealBtn.classList.remove("active");
        modeRealBtn.setAttribute("aria-selected", "false");
        demoPresetsContainer.classList.remove("hidden");

        loadPreset("real");
      }
    }

    modeRealBtn.addEventListener("click", () => switchMode("real"));
    modeDemoBtn.addEventListener("click", () => switchMode("demo"));

    function setSourceBadge(mode, label) {
      if (!sourceBadge) return;
      sourceBadge.className = "source-badge";
      if (mode === "live") {
        sourceBadge.classList.add("source-live");
        sourceBadge.innerText = label || "LIVE TAB CONTENT";
      } else if (mode === "preset") {
        sourceBadge.classList.add("source-preset");
        sourceBadge.innerText = label || "TEST SCENARIO";
      } else {
        sourceBadge.classList.add("source-manual");
        sourceBadge.innerText = label || "MANUAL INPUT";
      }
    }

    function updateMetadataUI(payload, engagement = null) {
      const platform = (payload.platform || "generic").toUpperCase();
      platformChip.innerText = `Platform: ${platform}`;

      const authorName = payload.author?.username ? `@${payload.author.username}` : (payload.author_username ? `@${payload.author_username}` : "None");
      if (authorChip) authorChip.innerText = `Author: ${authorName}`;

      const totalReplies = engagement?.replies != null ? engagement.replies :
        (payload.engagement?.replies != null ? payload.engagement.replies :
          (payload.replies != null ? payload.replies :
            (Array.isArray(payload.comments) ? payload.comments.length : 0)));
      const extractedCount = Array.isArray(payload.comments) ? payload.comments.length : 0;
      if (totalReplies > 0 && extractedCount > 0 && totalReplies !== extractedCount) {
        commentsChip.innerText = `Comments: ${totalReplies.toLocaleString()} (${extractedCount} fetched)`;
      } else {
        commentsChip.innerText = `Comments: ${totalReplies.toLocaleString()}`;
      }

      const mediaCount = Array.isArray(payload.media) ? payload.media.length : 0;
      mediaChip.innerText = `Media: ${mediaCount}`;

      if (engagementChip) {
        const likes = engagement?.likes != null ? engagement.likes : (payload.likes_count != null ? payload.likes_count : null);
        if (likes !== null && likes !== undefined) {
          engagementChip.classList.remove("hidden");
          engagementChip.innerText = `Likes: ${likes.toLocaleString()}`;
        } else {
          engagementChip.classList.add("hidden");
        }
      }
    }

    // Demo Preset Handler
    function loadPreset(presetKey) {
      activePayload = JSON.parse(JSON.stringify(TEST_PRESETS[presetKey]));
      activePayload.source = "preset";
      postTextInput.value = activePayload.text;
      setSourceBadge("preset", `PRESET: ${presetKey.toUpperCase()}`);
      updateMetadataUI(activePayload, activePayload.engagement);
      errorBox.classList.add("hidden");
      resultsContainer.classList.add("hidden");
    }

    presetRealBtn.addEventListener("click", () => loadPreset("real"));
    presetUncertainBtn.addEventListener("click", () => loadPreset("uncertain"));
    presetFakeBtn.addEventListener("click", () => loadPreset("fake"));

    // Track edits in textarea
    postTextInput.addEventListener("input", () => {
      errorBox.classList.add("hidden");
      if (activePayload) {
        activePayload.text = postTextInput.value;
      }
    });

    // Real Mode Extraction Handler
    async function attemptLiveTabExtraction(isAutoInit = false) {
      try {
        if (typeof chrome === "undefined" || !chrome.tabs || !chrome.tabs.query) {
          if (!isAutoInit) {
            showCategorizedError("EXTRACTION_ERROR", "Tab Access Unavailable", "Chrome extension tab API is not accessible in this context.", "Please verify extension permissions.");
          }
          return false;
        }

        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab || !tab.id) {
          if (!isAutoInit) showCategorizedError("EXTRACTION_ERROR", "No Active Tab", "No active browser tab detected.", "Ensure a browser tab is selected.");
          return false;
        }

        const tabUrl = tab.url || "";
        if (tabUrl.startsWith("chrome://") || tabUrl.startsWith("chrome-extension://") || tabUrl.startsWith("about:") || tabUrl.startsWith("edge://")) {
          setSourceBadge("manual", "INTERNAL PAGE");
          if (!isAutoInit) {
            showCategorizedError("EXTRACTION_ERROR", "Internal Browser Page", "Cannot inspect internal browser settings or extension pages.", "Please navigate to a public post on X, Reddit, or Instagram.");
          }
          return false;
        }

        return new Promise((resolve) => {
          chrome.tabs.sendMessage(tab.id, { action: "EXTRACT_CURRENT_POST" }, async (response) => {
            if (chrome.runtime.lastError || !response) {
              if (chrome.scripting && chrome.scripting.executeScript) {
                try {
                  await chrome.scripting.executeScript({
                    target: { tabId: tab.id },
                    files: ["content/content_extractor.js"]
                  });

                  chrome.tabs.sendMessage(tab.id, { action: "EXTRACT_CURRENT_POST" }, (retryResponse) => {
                    if (chrome.runtime.lastError || !retryResponse) {
                      handleExtractionFailure("Content script did not respond. The page may still be loading or restricted.", isAutoInit);
                      resolve(false);
                    } else {
                      resolve(processExtractionResponse(retryResponse, isAutoInit, tabUrl));
                    }
                  });
                  return;
                } catch (injectErr) {
                  console.warn("[Social Guard] Script injection failed:", injectErr);
                }
              }
              handleExtractionFailure("Could not connect to the current web page.", isAutoInit);
              resolve(false);
              return;
            }

            resolve(processExtractionResponse(response, isAutoInit, tabUrl));
          });
        });
      } catch (err) {
        console.warn("[Social Guard] Extraction exception:", err);
        handleExtractionFailure(err.message, isAutoInit);
        return false;
      }
    }

    function processExtractionResponse(response, isAutoInit, tabUrl = "") {
      if (response.success && response.data) {
        rawExtractedData = response.data;
        if (!rawExtractedData.post_url && tabUrl) {
          rawExtractedData.post_url = tabUrl;
        }
        applyExtractedData(response.data);
        return true;
      } else {
        const err = response.error || "No post detected on the active page.";
        handleExtractionFailure(err, isAutoInit);
        return false;
      }
    }

    function applyExtractedData(data) {
      if (!data || !data.text || data.text.trim().length < 1) {
        handleExtractionFailure("Extracted post text was empty or incomplete.", false);
        return;
      }

      const safeMedia = (data.media || [])
        .filter(m => m && typeof m.url === "string" && (m.url.startsWith("http://") || m.url.startsWith("https://")))
        .map(m => ({ url: m.url, media_type: m.media_type || "image" }));

      activePayload = {
        source: "live_tab",
        platform: (data.platform || "generic").toLowerCase(),
        post_id: data.post_id || null,
        post_url: data.post_url || window.location?.href || "",
        text: data.text.trim(),
        hashtags: data.hashtags || [],
        media: safeMedia,
        timestamp: data.timestamp || null,
        author: data.author_username ? {
          username: data.author_username,
          account_age_days: null,
          followers: 0,
          following: 0,
          engagement_rate: (data.engagement?.likes && data.engagement?.replies) ?
            Math.min(1.0, (data.engagement.likes + data.engagement.replies) / 5000) : null
        } : null,
        engagement: data.engagement || null,
        comments: (data.comments || []).map((c, idx) => ({
          comment_id: c.comment_id || `c_${idx + 1}`,
          author_id: c.username || `commenter_${idx + 1}`,
          text: c.text,
          likes: c.likes || 0,
          timestamp: c.timestamp || null
        }))
      };

      postTextInput.value = activePayload.text;
      const platformLabel = (data.platform || "post").toUpperCase();
      setSourceBadge("live", `LIVE: ${platformLabel}`);
      updateMetadataUI(activePayload, data.engagement);
      errorBox.classList.add("hidden");
      resultsContainer.classList.add("hidden");
    }

    function handleExtractionFailure(msg, isAutoInit) {
      if (isAutoInit) {
        setSourceBadge("manual", "NO POST DETECTED");
        platformChip.innerText = "Platform: --";
        if (authorChip) authorChip.innerText = "Author: --";
        commentsChip.innerText = "Comments: 0";
        mediaChip.innerText = "Media: 0";
        if (engagementChip) engagementChip.classList.add("hidden");
      } else {
        setSourceBadge("manual", "EXTRACTION FAILED");
        showCategorizedError("EXTRACTION_ERROR", "Extraction Failed", msg || "Could not detect a social-media post on this page.", "Open a specific tweet, reddit thread, or instagram post and try again.");
      }
    }

    function showCategorizedError(category, title, msg, hint = "") {
      errorBox.classList.remove("hidden");
      errorCategoryTag.innerText = category.replace(/_/g, " ");
      errorBoxTitle.innerText = title;
      errorMessage.innerText = msg;

      if (hint) {
        errorActionHint.classList.remove("hidden");
        errorActionHint.innerText = `Recommendation: ${hint}`;
      } else {
        errorActionHint.classList.add("hidden");
      }
    }

    // Step Progress Animator for Loading State
    function setLoadingStep(stepNum, label) {
      if (loadingStageLabel) loadingStageLabel.innerText = label;
      for (let i = 1; i <= 5; i++) {
        const stepEl = document.getElementById(`step-${i}`);
        if (!stepEl) continue;
        stepEl.classList.remove("active", "completed");
        if (i < stepNum) {
          stepEl.classList.add("completed");
        } else if (i === stepNum) {
          stepEl.classList.add("active");
        }
      }
    }

    // "Extract from Tab" button click
    extractPageBtn.addEventListener("click", async () => {
      errorBox.classList.add("hidden");
      resultsContainer.classList.add("hidden");
      await attemptLiveTabExtraction(false);
    });

    // "Analyze & Verify Content" button click
    runVerifyBtn.addEventListener("click", async () => {
      errorBox.classList.add("hidden");
      resultsContainer.classList.add("hidden");

      // 1. In Real Mode, if no active payload yet, attempt live extraction first
      if (currentMode === "real" && (!activePayload || !activePayload.text)) {
        const extracted = await attemptLiveTabExtraction(false);
        if (!extracted && (!postTextInput.value || postTextInput.value.trim().length === 0)) {
          showCategorizedError("NO_CLAIM_FOUND", "No Post Detected", "No social media post detected on the active page.", "Navigate to a public post or switch to Demo Mode.");
          return;
        }
      }

      // 2. Synchronize current text input
      const currentText = postTextInput.value.trim();
      if (!currentText || currentText.length < 1) {
        showCategorizedError("INSUFFICIENT_DATA", "Post Text Empty", "Please provide post content to verify.", "Enter text in the box or extract from an open post.");
        return;
      }

      if (!activePayload) {
        activePayload = {
          platform: "generic",
          post_url: "",
          text: currentText,
          hashtags: [],
          media: [],
          author: null,
          comments: []
        };
      } else {
        activePayload.text = currentText;
      }

      // 3. Pre-dispatch Validation & Schema Normalization
      let analysisRequest;
      try {
        const isDemo = (currentMode === "demo");
        analysisRequest = validateAndBuildAnalysisPayload(activePayload, isDemo);
        console.log(`[Social Guard] Dispatching ${isDemo ? "DEMO" : "REAL"} payload to /analyze:`, JSON.stringify(analysisRequest, null, 2));
      } catch (valErr) {
        showCategorizedError("INSUFFICIENT_DATA", "Payload Validation Failed", valErr.message, "Check post content format.");
        return;
      }

      // 4. Begin Multi-Stage Pipeline Animation
      loadingSpinner.classList.remove("hidden");
      setLoadingStep(1, "Extracting post...");

      let stageTimer1 = setTimeout(() => setLoadingStep(2, "Checking claims..."), 350);
      let stageTimer2 = setTimeout(() => setLoadingStep(3, "Analysing comments & user behaviour..."), 900);
      let stageTimer3 = setTimeout(() => setLoadingStep(4, "Checking similar content & image hashes..."), 1600);
      let stageTimer4 = setTimeout(() => setLoadingStep(5, "Generating explainable credibility result..."), 2400);

      try {
        const result = await SocialGuardApiClient.analyzePost(analysisRequest);

        clearTimeout(stageTimer1);
        clearTimeout(stageTimer2);
        clearTimeout(stageTimer3);
        clearTimeout(stageTimer4);
        setLoadingStep(5, "Analysis Complete!");

        renderResults(result, activePayload);
      } catch (err) {
        clearTimeout(stageTimer1);
        clearTimeout(stageTimer2);
        clearTimeout(stageTimer3);
        clearTimeout(stageTimer4);

        if (err instanceof SocialGuardApiError) {
          if (err.errorType === "OfflineError") {
            showCategorizedError(
              "BACKEND_ERROR",
              "Backend Offline",
              "FastAPI server at http://localhost:8000 is unreachable.",
              "Ensure the server is running on port 8000 (uvicorn app.main:app)."
            );
          } else if (err.errorType === "ValidationError") {
            showCategorizedError(
              "API_ERROR",
              "Validation Error (HTTP 422)",
              err.message,
              "Review the schema requirements in the post content."
            );
          } else if (err.errorType === "TimeoutError") {
            showCategorizedError(
              "API_ERROR",
              "Request Timeout (15s)",
              err.message,
              "The verification pipeline took too long. Check server load."
            );
          } else if (err.errorType === "BadRequestError") {
            showCategorizedError(
              "API_ERROR",
              "Bad Request (HTTP 400)",
              err.message,
              "Check for malformed input values."
            );
          } else if (err.errorType === "InternalServerError") {
            showCategorizedError(
              "BACKEND_ERROR",
              "Server Error (HTTP 500)",
              err.message,
              "Check backend server logs for trace details."
            );
          } else {
            showCategorizedError(
              "API_ERROR",
              `Server Error (${err.status || "Unknown"})`,
              err.message
            );
          }
        } else {
          showCategorizedError("API_ERROR", "Analysis Error", err.message);
        }
        await refreshBackendStatus();
      } finally {
        loadingSpinner.classList.add("hidden");
      }
    });

    // ============================================================================
    // 3. RESULTS RENDERER (Phase 6 Comprehensive Layout)
    // ============================================================================

    function renderResults(res, postData = null) {
      resultsContainer.classList.remove("hidden");

      // 1. Post Information Section
      const currentPost = postData || activePayload || {};
      const platformName = (currentPost.platform || "generic").toUpperCase();
      const platformBadge = document.getElementById("result-platform-badge");
      if (platformBadge) platformBadge.innerText = platformName;

      const authorHandle = document.getElementById("result-author-handle");
      const cleanAuthor = currentPost.author?.username || currentPost.author_username;
      if (authorHandle) authorHandle.innerText = cleanAuthor ? `@${cleanAuthor}` : "@author_unavailable";

      const postUrlEl = document.getElementById("result-post-url");
      const postUrl = currentPost.post_url || currentPost.url || "";
      if (postUrlEl) {
        if (postUrl && (postUrl.startsWith("http://") || postUrl.startsWith("https://"))) {
          postUrlEl.href = postUrl;
          postUrlEl.classList.remove("hidden");
        } else {
          postUrlEl.classList.add("hidden");
        }
      }

      const postTextEl = document.getElementById("result-post-text");
      if (postTextEl) postTextEl.innerText = currentPost.text || "";

      const commentCountEl = document.getElementById("result-comment-count");
      if (commentCountEl) {
        const totalReplies = currentPost.engagement?.replies != null ? currentPost.engagement.replies :
          (currentPost.replies != null ? currentPost.replies :
            (Array.isArray(currentPost.comments) ? currentPost.comments.length : 0));
        const cLen = Array.isArray(currentPost.comments) ? currentPost.comments.length : 0;
        if (totalReplies > 0 && cLen > 0 && totalReplies !== cLen) {
          commentCountEl.innerText = `Comments: ${Number(totalReplies).toLocaleString()} (${cLen} analyzed)`;
        } else {
          commentCountEl.innerText = `Comments: ${Number(totalReplies).toLocaleString()}`;
        }
      }

      const likesCountEl = document.getElementById("result-likes-count");
      if (likesCountEl) {
        const likesVal = currentPost.engagement?.likes ?? currentPost.likes_count ?? null;
        likesCountEl.innerText = likesVal !== null ? `Likes: ${Number(likesVal).toLocaleString()}` : "Likes: N/A";
      }

      const sharesCountEl = document.getElementById("result-shares-count");
      if (sharesCountEl) {
        const sharesVal = currentPost.engagement?.reposts ?? currentPost.shares_count ?? null;
        if (sharesVal !== null && sharesVal !== undefined) {
          sharesCountEl.classList.remove("hidden");
          sharesCountEl.innerText = `Shares: ${Number(sharesVal).toLocaleString()}`;
        } else {
          sharesCountEl.classList.add("hidden");
        }
      }

      const mediaCountEl = document.getElementById("result-media-count");
      if (mediaCountEl) {
        const mLen = Array.isArray(currentPost.media) ? currentPost.media.length : 0;
        mediaCountEl.innerText = `Media: ${mLen}`;
      }

      // 2. Main Verdict Banner: Credibility Score & Classification
      const finalScore = res.consolidated_score != null ? Math.round(res.consolidated_score) : "--";
      document.getElementById("credibility-score-val").innerText = finalScore;

      const badgeEl = document.getElementById("classification-badge");
      const classification = res.classification || "UNCERTAIN";
      badgeEl.innerText = classification;

      badgeEl.className = "classification-badge";
      if (classification === "LIKELY REAL") badgeEl.classList.add("verdict-likely-real");
      else if (classification === "PROBABLY REAL") badgeEl.classList.add("verdict-probably-real");
      else if (classification === "UNCERTAIN") badgeEl.classList.add("verdict-uncertain");
      else if (classification === "PROBABLY FAKE") badgeEl.classList.add("verdict-probably-fake");
      else badgeEl.classList.add("verdict-likely-fake");

      // 3. AI Detector: Orthogonal Decoupled Metric
      const aiProbEl = document.getElementById("ai-probability-val");
      if (res.ai_generation_probability != null) {
        const pct = Math.round(res.ai_generation_probability * 100);
        aiProbEl.innerText = `${pct}%`;
      } else {
        aiProbEl.innerText = "N/A";
      }

      // 4. Module Results Section (Module 1 - 4)
      const mScores = res.module_scores || {};
      renderModuleBar("comment", mScores.comment_analysis);
      renderModuleBar("evidence", mScores.evidence_verification);
      renderModuleBar("behaviour", mScores.user_behaviour);
      renderModuleBar("similarity", mScores.similar_content);

      // 5. Explanation Section: "Why did Social Guard give this result?"
      const summaryEl = document.getElementById("explanation-summary");
      summaryEl.innerText = res.explanation || "Verification completed.";

      const reasonsList = document.getElementById("reasons-list");
      reasonsList.innerHTML = "";

      const xaiData = res.module_results?.explainability || {};
      const posFactors = xaiData.positive_factors || [];
      const negFactors = xaiData.negative_factors || [];

      posFactors.slice(0, 3).forEach(factor => {
        const li = document.createElement("li");
        li.className = "reason-item reason-positive";
        li.innerHTML = `<span class="factor-badge badge-pos">Support</span> ${escapeHtml(factor.description || factor.factor || "")}`;
        reasonsList.appendChild(li);
      });

      negFactors.slice(0, 3).forEach(factor => {
        const li = document.createElement("li");
        li.className = "reason-item reason-negative";
        li.innerHTML = `<span class="factor-badge badge-neg">Risk</span> ${escapeHtml(factor.description || factor.factor || "")}`;
        reasonsList.appendChild(li);
      });

      // 5.5 Community & Comment Fact-Check Section
      const commData = res.module_results?.module_breakdowns?.comments || res.module_results?.comments || {};
      const commFactCheck = commData.fact_check || {};
      const commVerdict = commFactCheck.verdict || "ORGANIC_DISCUSSION";
      const commVerdictBadge = document.getElementById("comment-verdict-badge");
      const commRatioStat = document.getElementById("comment-ratio-stat");
      const commSummaryEl = document.getElementById("comment-factcheck-summary");
      const debunkingListEl = document.getElementById("debunking-comments-list");

      if (commVerdictBadge) {
        commVerdictBadge.innerText = commVerdict.replace(/_/g, " ");
        commVerdictBadge.className = "comment-verdict-badge";
        if (commVerdict === "DEBUNKED_BY_COMMUNITY") {
          commVerdictBadge.classList.add("verdict-likely-fake");
        } else if (commVerdict === "CONTESTED_BY_COMMENTS") {
          commVerdictBadge.classList.add("verdict-probably-fake");
        } else if (commVerdict === "SUPPORTED_BY_COMMENTS") {
          commVerdictBadge.classList.add("verdict-likely-real");
        } else {
          commVerdictBadge.classList.add("verdict-uncertain");
        }
      }

      if (commRatioStat) {
        if (commFactCheck.debunk_ratio != null && commFactCheck.debunk_ratio > 0) {
          commRatioStat.innerText = `${Math.round(commFactCheck.debunk_ratio * 100)}% debunking/skepticism`;
        } else if (commFactCheck.support_ratio != null && commFactCheck.support_ratio > 0) {
          commRatioStat.innerText = `${Math.round(commFactCheck.support_ratio * 100)}% corroboration`;
        } else {
          commRatioStat.innerText = "";
        }
      }

      if (commSummaryEl) {
        commSummaryEl.innerText = commFactCheck.summary || "No comment fact-checking signals detected.";
      }

      if (debunkingListEl) {
        const debunkRemarks = commFactCheck.debunking_comments || [];
        if (debunkRemarks.length > 0) {
          debunkingListEl.classList.remove("hidden");
          debunkingListEl.innerHTML = "<span class='sub-label'>Sample remarks from commenters:</span>" +
            debunkRemarks.slice(0, 3).map(r => `<div class='debunk-item'>💬 "${escapeHtml(r)}"</div>`).join("");
        } else {
          debunkingListEl.classList.add("hidden");
          debunkingListEl.innerHTML = "";
        }
      }

      // 6. Evidence & Fact-Checks Section
      const evModule = res.module_results?.module_breakdowns?.evidence || {};
      const claimsBlock = document.getElementById("claims-checked-block");
      const claimsList = document.getElementById("claims-checked-list");
      const extractedClaims = evModule.claims || [];

      if (claimsBlock && claimsList) {
        if (extractedClaims.length > 0) {
          claimsBlock.classList.remove("hidden");
          claimsList.innerHTML = "";
          extractedClaims.forEach(claimStr => {
            const cli = document.createElement("li");
            cli.className = "claim-list-item";
            cli.innerText = claimStr;
            claimsList.appendChild(cli);
          });
        } else {
          claimsBlock.classList.add("hidden");
        }
      }

      const evContainer = document.getElementById("evidence-container");
      evContainer.innerHTML = "";
      const factChecks = evModule.fact_checks || [];

      if (factChecks.length > 0) {
        factChecks.forEach(fc => {
          const item = document.createElement("div");
          item.className = "evidence-item";

          const ratingText = fc.rating || fc.raw_rating || "Checked";
          const ratingCategory = (fc.rating_category || "").toUpperCase();
          let ratingBadgeClass = "rating-mixed";
          if (ratingCategory === "FALSE" || ratingCategory === "MOSTLY_FALSE") ratingBadgeClass = "rating-false";
          else if (ratingCategory === "TRUE" || ratingCategory === "MOSTLY_TRUE") ratingBadgeClass = "rating-true";

          const rawLink = fc.source_url || fc.publisher_url;
          const safeLink = (rawLink && typeof rawLink === "string" && (rawLink.trim().startsWith("https://") || rawLink.trim().startsWith("http://"))) ? rawLink.trim() : null;

          item.innerHTML = `
            <div class="evidence-header">
              <span class="evidence-pub">${escapeHtml(fc.publisher || "Fact Checker")}</span>
              <span class="evidence-rating ${ratingBadgeClass}">${escapeHtml(ratingText)}</span>
            </div>
            <p class="evidence-claim">"${escapeHtml(fc.claim || "")}"</p>
            ${safeLink ? `<a href="${escapeHtml(safeLink)}" target="_blank" rel="noopener noreferrer" class="evidence-link">Read full review &rarr;</a>` : ""}
          `;
          evContainer.appendChild(item);
        });
      } else {
        const evExplanation = evModule.explanation || "No direct third-party fact-check matches found on Google Fact Check Tools.";
        evContainer.innerHTML = `
          <div class="empty-notice">
            <span>${escapeHtml(evExplanation)}</span>
            <span class="empty-sub">Evidence module assigned neutral baseline (50.0).</span>
          </div>
        `;
      }

      // 7. Similar Content Section
      const simContainer = document.getElementById("similar-content-container");
      simContainer.innerHTML = "";
      const simModule = res.module_results?.module_breakdowns?.similarity || {};

      if (simModule.recycled_content) {
        simContainer.innerHTML = `
          <div class="similar-item recycled-warning">
            <div class="similar-header">
              <span class="badge-recycled">Recycled Hoax Warning</span>
              <span class="similar-date">${escapeHtml(simModule.earliest_matching_timestamp ? simModule.earliest_matching_timestamp.slice(0, 10) : "Historical")}</span>
            </div>
            <p class="similar-text">${escapeHtml(simModule.explanation || "This narrative matches historical debunked records.")}</p>
          </div>
        `;
      } else {
        simContainer.innerHTML = `
          <div class="empty-notice">
            <span>Original narrative structure. No recycled viral hoax matches detected in local corpus.</span>
          </div>
        `;
      }
    }

    function renderModuleBar(name, score) {
      const scoreTextEl = document.getElementById(`score-${name}`);
      const barEl = document.getElementById(`bar-${name}`);
      const statusEl = document.getElementById(`status-${name}`);

      if (score != null) {
        const val = Math.round(score);
        scoreTextEl.innerText = `${val}/100`;
        barEl.style.width = `${Math.min(100, Math.max(0, val))}%`;

        if (val >= 70) {
          barEl.className = "bar bar-high";
          statusEl.innerText = "Status: Strong";
          statusEl.className = "module-status-tag tag-high";
        } else if (val >= 40) {
          barEl.className = "bar bar-mid";
          statusEl.innerText = "Status: Neutral";
          statusEl.className = "module-status-tag tag-mid";
        } else {
          barEl.className = "bar bar-low";
          statusEl.innerText = "Status: Suspicious";
          statusEl.className = "module-status-tag tag-low";
        }
      } else {
        scoreTextEl.innerText = "--/100";
        barEl.style.width = "0%";
        barEl.className = "bar";
        statusEl.innerText = "Status: Unavailable";
        statusEl.className = "module-status-tag";
      }
    }

    function escapeHtml(str) {
      if (!str) return "";
      return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }
  });
}
