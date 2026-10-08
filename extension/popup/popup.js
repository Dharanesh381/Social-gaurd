/**
 * Social Guard: Explainable AI Verification Popup Controller
 * Manages live post extraction, academic demo presets, 6-stage verification progress,
 * and renders a comprehensive 12-section Explainable AI report.
 */

import { SocialGuardApiClient, SocialGuardApiError } from "./api_client.js";

// ==============================================================================
// 1. CURATED DEMO PRESET SCENARIOS
// ==============================================================================

const DEMO_PRESETS = {
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
        text: "Does this match the earlier radar reflection datasets from ESA?",
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
  },

  ai_factual: {
    platform: "twitter",
    post_url: "https://x.com/astro_briefs/status/555123456",
    text: "The James Webb Space Telescope has successfully captured high-resolution transmission spectra of exoplanet WASP-96b, providing detailed atmospheric composition data.",
    hashtags: ["#JWST", "#Exoplanets", "#Astronomy"],
    media: [
      { url: "https://example.com/wasp96b_spectrum.png", media_type: "image" }
    ],
    author: {
      username: "astro_briefs",
      account_age_days: 900,
      followers: 18500,
      following: 220,
      posts_per_day: 3.0,
      comments_per_day: 4.0,
      engagement_rate: 0.05,
      duplicate_content_ratio: 0.02,
      hashtag_repetition_rate: 0.10
    },
    engagement: {
      likes: 8400,
      replies: 310,
      reposts: 1950
    },
    comments: [
      {
        comment_id: "c_ai1",
        text: "Incredible spectral fidelity from NIRISS instrument!",
        likes: 34,
        emojis: []
      }
    ]
  },

  recycled: {
    platform: "facebook",
    post_url: "https://facebook.com/viral_alerts/posts/1029384756",
    text: "BREAKING: Emergency nationwide lockdown declared tonight across all major international airports due to unknown airborne pathogen outbreak! Stock up immediately!",
    hashtags: ["#BreakingNews", "#Lockdown", "#Emergency"],
    media: [],
    author: {
      username: "viral_alerts_page",
      account_age_days: 12,
      followers: 85,
      following: 3400,
      posts_per_day: 95.0,
      comments_per_day: 40.0,
      engagement_rate: 0.002,
      duplicate_content_ratio: 0.85,
      hashtag_repetition_rate: 0.90
    },
    engagement: {
      likes: 120,
      replies: 840,
      reposts: 650
    },
    comments: [
      {
        comment_id: "c_rec1",
        text: "This is completely fake news and an old 2020 rumor! Stop lying.",
        likes: 92,
        emojis: []
      },
      {
        comment_id: "c_rec2",
        text: "False alarm, airport authorities already debunked this hoax.",
        likes: 64,
        emojis: []
      },
      {
        comment_id: "c_rec3",
        text: "Old recycled scam reposted from years ago. Reported as misinformation.",
        likes: 45,
        emojis: []
      }
    ]
  }
};

let currentMode = "real";    // "real" | "demo"
let rawExtractedData = null; // Stored live extraction data
let activePayload = null;    // Post payload prepared for UI and analysis

// ==============================================================================
// 2. PAYLOAD NORMALIZATION & VALIDATION
// ==============================================================================

/**
 * Validate and map an extracted post or preset into the strict AnalysisRequest schema.
 */
export function validateAndBuildAnalysisPayload(data, isDemo = false) {
  if (!data || typeof data !== "object") {
    throw new Error("No post data provided for verification.");
  }

  // 1. Text Validation
  const text = (data.text || "").trim();
  if (!text || text.length < 1) {
    throw new Error("Post text cannot be empty. Please enter or extract readable social media text.");
  }
  if (text.length > 50000) {
    throw new Error("Post text exceeds maximum allowed length (50,000 characters).");
  }

  // 2. Platform Normalization
  let platform = (data.platform || "generic").toLowerCase().trim();
  if (platform === "x") platform = "twitter";
  const validPlatforms = ["twitter", "reddit", "facebook", "instagram", "generic"];
  if (!validPlatforms.includes(platform)) platform = "generic";

  // 3. Post URL & ID
  let postUrl = (data.post_url || "").trim();
  let postId = data.post_id ? String(data.post_id).trim() : null;
  if (!postId) {
    let hash = 0;
    for (let i = 0; i < text.length; i++) {
      hash = ((hash << 5) - hash) + text.charCodeAt(i);
      hash |= 0;
    }
    const cleanHash = Math.abs(hash).toString(16).padStart(8, "0");
    postId = `${platform.slice(0, 2)}_${cleanHash}`;
  }

  // 4. Media Normalization
  const safeMedia = (data.media || [])
    .filter(m => m && typeof m.url === "string" && (m.url.startsWith("http://") || m.url.startsWith("https://")))
    .map(m => ({
      url: m.url.trim(),
      media_type: m.media_type || "image"
    }));

  // 5. Hashtags Normalization
  let hashtags = [];
  if (Array.isArray(data.hashtags)) {
    hashtags = data.hashtags.map(t => String(t).trim()).filter(t => t.length > 0);
  } else {
    const extractedTags = text.match(/#[a-zA-Z0-9_]+/g);
    if (extractedTags) hashtags = extractedTags;
  }

  // 6. Author Profile Normalization
  let authorObj = null;
  if (data.author && typeof data.author === "object") {
    const a = data.author;
    const authorUsername = (a.username || data.author_username || "author").trim();
    authorObj = {
      username: authorUsername,
      account_age_days: (a.account_age_days != null && !isNaN(a.account_age_days)) ? Math.max(0, Number(a.account_age_days)) : null,
      followers_count: (a.followers != null || a.followers_count != null) ? Math.max(0, parseInt(a.followers ?? a.followers_count, 10)) : 0,
      following_count: (a.following != null || a.following_count != null) ? Math.max(0, parseInt(a.following ?? a.following_count, 10)) : 0,
      posts_count: (a.posts_count != null) ? Math.max(0, parseInt(a.posts_count, 10)) : 0,
      recent_posts_frequency_per_day: (a.posts_per_day != null || a.recent_posts_frequency_per_day != null) ?
        Math.max(0.0, Number(a.posts_per_day ?? a.recent_posts_frequency_per_day)) : null,
      recent_comments_frequency_per_day: (a.comments_per_day != null || a.recent_comments_frequency_per_day != null) ?
        Math.max(0.0, Number(a.comments_per_day ?? a.recent_comments_frequency_per_day)) : null,
      duplicate_posts_ratio: (a.duplicate_content_ratio != null || a.duplicate_posts_ratio != null) ?
        Math.min(1.0, Math.max(0.0, Number(a.duplicate_content_ratio ?? a.duplicate_posts_ratio))) : null,
      hashtag_repetition_rate: (a.hashtag_repetition_rate != null) ?
        Math.min(1.0, Math.max(0.0, Number(a.hashtag_repetition_rate))) : null,
      average_engagement_rate: (a.engagement_rate != null || a.average_engagement_rate != null) ?
        Math.min(1.0, Math.max(0.0, Number(a.engagement_rate ?? a.average_engagement_rate))) : null,
      average_posting_interval_seconds: null
    };
  } else if (data.author_username) {
    authorObj = {
      username: String(data.author_username).trim(),
      followers_count: 0,
      following_count: 0,
      posts_count: 0
    };
  }

  // 7. Comments Normalization
  let commentsList = [];
  if (Array.isArray(data.comments)) {
    commentsList = data.comments.map((c, idx) => {
      if (typeof c === "string") {
        return {
          comment_id: `c_${idx + 1}`,
          text: c.trim(),
          likes: 0,
          timestamp: null,
          author: { username: `commenter_${idx + 1}` }
        };
      }
      return {
        comment_id: c.comment_id || `c_${idx + 1}`,
        text: (c.text || "").trim(),
        likes: (c.likes != null && !isNaN(c.likes)) ? Math.max(0, parseInt(c.likes, 10)) : 0,
        timestamp: c.timestamp || null,
        author: { username: c.username || c.author_id || c.author?.username || `commenter_${idx + 1}` }
      };
    }).filter(c => c.text.length > 0);
  }

  // 8. Engagement Normalization
  const engagement = data.engagement || null;

  return {
    request_id: `ext_req_${Date.now()}`,
    post: {
      platform: platform,
      post_id: postId,
      post_url: postUrl || null,
      text: text,
      timestamp: data.timestamp || new Date().toISOString(),
      hashtags: hashtags,
      media: safeMedia,
      author: authorObj,
      comments: commentsList,
      engagement: engagement
    }
  };
}

// ==============================================================================
// 3. UI INITIALIZATION & EVENT LISTENERS
// ==============================================================================

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", async () => {
    // Mode tabs
    const modeLiveBtn = document.getElementById("mode-live-btn");
    const modeDemoBtn = document.getElementById("mode-demo-btn");
    const demoPresetsContainer = document.getElementById("demo-presets-container");

    // Input elements
    const postTextInput = document.getElementById("post-text-input");
    const extractPageBtn = document.getElementById("extract-page-btn");
    const runVerifyBtn = document.getElementById("run-verify-btn");
    const contentSourceBadge = document.getElementById("content-source-badge");

    // Detection chips
    const detectedPlatformChip = document.getElementById("detected-platform");
    const detectedAuthorChip = document.getElementById("detected-author");
    const detectedCommentsChip = document.getElementById("detected-comments-count");
    const detectedMediaChip = document.getElementById("detected-media-count");
    const detectedEngagementChip = document.getElementById("detected-engagement");

    // Status & Loading
    const backendStatusBadge = document.getElementById("backend-status-badge");
    const backendStatusText = document.getElementById("backend-status-text");
    const loadingSpinner = document.getElementById("loading-spinner");
    const loadingStageLabel = document.getElementById("loading-stage-label");

    // Error Box
    const errorBox = document.getElementById("error-box");
    const errorCategoryTag = document.getElementById("error-category-tag");
    const errorBoxTitle = document.getElementById("error-box-title");
    const errorMessage = document.getElementById("error-message");
    const errorActionHint = document.getElementById("error-action-hint");
    const errorDismissBtn = document.getElementById("error-dismiss-btn");

    // Results container
    const resultsContainer = document.getElementById("results-container");
    const resetViewBtn = document.getElementById("reset-view-btn");

    // Demo buttons
    const presetRealBtn = document.getElementById("preset-real-btn");
    const presetUncertainBtn = document.getElementById("preset-uncertain-btn");
    const presetFakeBtn = document.getElementById("preset-fake-btn");
    const presetAiFactualBtn = document.getElementById("preset-ai-factual-btn");
    const presetRecycledBtn = document.getElementById("preset-recycled-btn");

    // Check backend health immediately on startup
    await refreshBackendStatus();
    setInterval(refreshBackendStatus, 15000);

    // Auto-attempt extraction if in Live mode on initial open
    await attemptLiveTabExtraction(true);

    // Mode Switcher Handlers
    modeLiveBtn.addEventListener("click", () => {
      currentMode = "real";
      modeLiveBtn.classList.add("active");
      modeLiveBtn.setAttribute("aria-selected", "true");
      modeDemoBtn.classList.remove("active");
      modeDemoBtn.setAttribute("aria-selected", "false");
      demoPresetsContainer.classList.add("hidden");

      if (rawExtractedData) {
        applyExtractedData(rawExtractedData);
      } else {
        setSourceBadge("live", "LIVE TAB");
      }
    });

    modeDemoBtn.addEventListener("click", () => {
      currentMode = "demo";
      modeDemoBtn.classList.add("active");
      modeDemoBtn.setAttribute("aria-selected", "true");
      modeLiveBtn.classList.remove("active");
      modeLiveBtn.setAttribute("aria-selected", "false");
      demoPresetsContainer.classList.remove("hidden");

      // Auto-load Real preset as initial showcase if input is blank
      if (!postTextInput.value || postTextInput.value.trim().length === 0) {
        loadPreset("real");
      }
    });

    // Preset button click events
    if (presetRealBtn) presetRealBtn.addEventListener("click", () => loadPreset("real"));
    if (presetUncertainBtn) presetUncertainBtn.addEventListener("click", () => loadPreset("uncertain"));
    if (presetFakeBtn) presetFakeBtn.addEventListener("click", () => loadPreset("fake"));
    if (presetAiFactualBtn) presetAiFactualBtn.addEventListener("click", () => loadPreset("ai_factual"));
    if (presetRecycledBtn) presetRecycledBtn.addEventListener("click", () => loadPreset("recycled"));

    // Extract Page button
    extractPageBtn.addEventListener("click", async () => {
      errorBox.classList.add("hidden");
      resultsContainer.classList.add("hidden");
      await attemptLiveTabExtraction(false);
    });

    // Dismiss error button
    if (errorDismissBtn) {
      errorDismissBtn.addEventListener("click", () => {
        errorBox.classList.add("hidden");
      });
    }

    // Reset View button
    if (resetViewBtn) {
      resetViewBtn.addEventListener("click", () => {
        resultsContainer.classList.add("hidden");
        errorBox.classList.add("hidden");
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    }

    // Load a preset payload
    function loadPreset(presetKey) {
      const presetData = DEMO_PRESETS[presetKey];
      if (!presetData) return;

      activePayload = JSON.parse(JSON.stringify(presetData));
      postTextInput.value = activePayload.text;

      const labelMap = {
        real: "DEMO: LIKELY REAL",
        uncertain: "DEMO: UNCERTAIN",
        fake: "DEMO: LIKELY FAKE",
        ai_factual: "DEMO: AI FACTUAL",
        recycled: "DEMO: RECYCLED HOAX"
      };
      setSourceBadge("demo", labelMap[presetKey] || "DEMO PRESET");
      updateMetadataUI(activePayload, activePayload.engagement);

      errorBox.classList.add("hidden");
      resultsContainer.classList.add("hidden");
    }

    // Set source badge UI
    function setSourceBadge(mode, labelText) {
      if (!contentSourceBadge) return;
      contentSourceBadge.innerText = labelText;
      contentSourceBadge.className = "source-badge";
      if (mode === "live") {
        contentSourceBadge.classList.add("source-live");
      } else {
        contentSourceBadge.classList.add("source-manual");
      }
    }

    // Update detected metadata chips
    function updateMetadataUI(payload, engagement) {
      if (detectedPlatformChip) {
        detectedPlatformChip.innerText = `Platform: ${(payload.platform || "generic").toUpperCase()}`;
      }
      if (detectedAuthorChip) {
        const username = payload.author?.username || payload.author_username || "--";
        detectedAuthorChip.innerText = `Author: @${username}`;
      }
      if (detectedCommentsChip) {
        const count = Array.isArray(payload.comments) ? payload.comments.length : 0;
        detectedCommentsChip.innerText = `Comments: ${count}`;
      }
      if (detectedMediaChip) {
        const mCount = Array.isArray(payload.media) ? payload.media.length : 0;
        detectedMediaChip.innerText = `Media: ${mCount}`;
      }
      if (detectedEngagementChip) {
        if (engagement && engagement.likes != null) {
          detectedEngagementChip.classList.remove("hidden");
          detectedEngagementChip.innerText = `Likes: ${Number(engagement.likes).toLocaleString()}`;
        } else {
          detectedEngagementChip.classList.add("hidden");
        }
      }
    }

    // Backend health checker
    async function refreshBackendStatus() {
      if (!backendStatusBadge) return;
      try {
        const health = await SocialGuardApiClient.checkHealth();
        if (health && health.status === "ok") {
          backendStatusBadge.className = "badge-status badge-online";
          backendStatusText.innerText = "API Online";
          backendStatusBadge.title = `FastAPI v${health.version || "1.0.0"} connected on :8000`;
        } else {
          backendStatusBadge.className = "badge-status badge-offline";
          backendStatusText.innerText = "API Offline";
          backendStatusBadge.title = "FastAPI backend unreachable at http://localhost:8000";
        }
      } catch (err) {
        backendStatusBadge.className = "badge-status badge-offline";
        backendStatusText.innerText = "API Offline";
        backendStatusBadge.title = `Error: ${err.message}`;
      }
    }

    // Live tab extraction routine
    async function attemptLiveTabExtraction(isAutoInit = false) {
      if (typeof chrome === "undefined" || !chrome.tabs) return false;

      try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab || !tab.id) {
          handleExtractionFailure("No active tab detected.", isAutoInit);
          return false;
        }

        const tabUrl = tab.url || "";
        const isRestrictedUrl = tabUrl.startsWith("chrome://") || tabUrl.startsWith("chrome-extension://") || tabUrl.startsWith("edge://") || tabUrl.startsWith("about:");
        if (isRestrictedUrl) {
          if (isAutoInit) {
            setSourceBadge("manual", "MANUAL INPUT");
          } else {
            handleExtractionFailure("Cannot extract from browser internal pages. Navigate to a social media post or paste the text below.", false);
          }
          return false;
        }

        // Helper to send extraction message with timeout
        const sendExtractMessage = () => new Promise((resolve) => {
          chrome.tabs.sendMessage(tab.id, { action: "EXTRACT_CURRENT_POST" }, (response) => {
            if (chrome.runtime.lastError) {
              resolve({ error: chrome.runtime.lastError.message });
              return;
            }
            resolve(response || { error: "No response from page extractor." });
          });
        });

        let response = await sendExtractMessage();

        // If content script was not injected on this pre-existing tab, inject it on demand and retry
        if (response?.error && chrome.scripting) {
          try {
            await chrome.scripting.executeScript({
              target: { tabId: tab.id },
              files: ["content/content_extractor.js"]
            });
            // Brief wait for script execution
            await new Promise(r => setTimeout(r, 120));
            response = await sendExtractMessage();
          } catch (scriptErr) {
            console.warn("[Social Guard] Dynamic script injection attempt:", scriptErr);
          }
        }

        if (response && response.success && response.data) {
          rawExtractedData = response.data;
          if (!rawExtractedData.post_url && tabUrl) {
            rawExtractedData.post_url = tabUrl;
          }
          applyExtractedData(response.data);
          return true;
        } else {
          const err = response?.error || "No post detected on active page.";
          handleExtractionFailure(err, isAutoInit);
          return false;
        }
      } catch (err) {
        handleExtractionFailure(err.message, isAutoInit);
        return false;
      }
    }

    function applyExtractedData(data) {
      if (!data || !data.text || data.text.trim().length < 1) {
        handleExtractionFailure("Extracted post text was empty.", false);
        return;
      }

      const safeMedia = (data.media || [])
        .filter(m => m && typeof m.url === "string" && (m.url.startsWith("http://") || m.url.startsWith("https://")))
        .map(m => ({ url: m.url, media_type: m.media_type || "image" }));

      activePayload = {
        source: "live_tab",
        platform: (data.platform || "generic").toLowerCase(),
        post_id: data.post_id || null,
        post_url: data.post_url || "",
        text: data.text.trim(),
        hashtags: data.hashtags || [],
        media: safeMedia,
        timestamp: data.timestamp || null,
        author: data.author_username ? {
          username: data.author_username,
          account_age_days: null,
          followers: 0,
          following: 0
        } : null,
        engagement: data.engagement || null,
        comments: (data.comments || []).map((c, idx) => ({
          comment_id: c.comment_id || `c_${idx + 1}`,
          username: c.username || `commenter_${idx + 1}`,
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
        setSourceBadge("manual", "MANUAL INPUT");
      } else {
        setSourceBadge("manual", "EXTRACTION FAILED");
        showCategorizedError(
          "EXTRACTION_ERROR",
          "Extraction Failed",
          msg || "Could not detect a social-media post on this page.",
          "Open a specific tweet, reddit thread, or instagram post and try again."
        );
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

    // 10. Multi-Stage Pipeline Progress Stepper
    function setProgressStep(stepNum, label) {
      if (loadingStageLabel) loadingStageLabel.innerText = label;
      for (let i = 1; i <= 6; i++) {
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

    // "Run Explainable Verification" button click
    runVerifyBtn.addEventListener("click", async () => {
      errorBox.classList.add("hidden");
      resultsContainer.classList.add("hidden");

      // 1. In Live Mode, if no active payload yet, attempt live extraction first
      if (currentMode === "real" && (!activePayload || !activePayload.text)) {
        const extracted = await attemptLiveTabExtraction(false);
        if (!extracted && (!postTextInput.value || postTextInput.value.trim().length === 0)) {
          showCategorizedError(
            "NO_POST_DETECTED",
            "No Post Found",
            "No social media post detected on the active browser tab.",
            "Navigate to a public post or switch to Demo Mode to test."
          );
          return;
        }
      }

      // 2. Synchronize current text input
      const currentText = postTextInput.value.trim();
      if (!currentText || currentText.length < 1) {
        showCategorizedError(
          "INSUFFICIENT_DATA",
          "Post Text Empty",
          "Please enter or extract social media post text.",
          "Type text in the input box or click 'Extract Tab'."
        );
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
      } catch (valErr) {
        showCategorizedError("VALIDATION_ERROR", "Payload Validation Error", valErr.message, "Check the post content format.");
        return;
      }

      // 4. Begin Multi-Stage Pipeline Animation (Prompt Requirement 10: 6 Steps)
      loadingSpinner.classList.remove("hidden");
      setProgressStep(1, "Extracting post content & metadata...");

      const t1 = setTimeout(() => setProgressStep(2, "Module 1: Analysing comments & sentiment..."), 300);
      const t2 = setTimeout(() => setProgressStep(3, "Module 2: Verifying claims against Google Fact Check..."), 700);
      const t3 = setTimeout(() => setProgressStep(4, "Module 3: Evaluating user behaviour & Isolation Forest..."), 1200);
      const t4 = setTimeout(() => setProgressStep(5, "Module 4: Matching similar content & image hashes..."), 1700);
      const t5 = setTimeout(() => setProgressStep(6, "Generating Explainable AI verification report..."), 2200);

      try {
        const result = await SocialGuardApiClient.analyzePost(analysisRequest);

        clearTimeout(t1);
        clearTimeout(t2);
        clearTimeout(t3);
        clearTimeout(t4);
        clearTimeout(t5);
        setProgressStep(6, "Verification Complete!");

        renderResults(result, activePayload);
      } catch (err) {
        clearTimeout(t1);
        clearTimeout(t2);
        clearTimeout(t3);
        clearTimeout(t4);
        clearTimeout(t5);

        if (err instanceof SocialGuardApiError) {
          if (err.errorType === "OfflineError") {
            showCategorizedError(
              "BACKEND_OFFLINE",
              "Backend Offline",
              "FastAPI server at http://localhost:8000 is unreachable.",
              "Start the backend using: .\\venv\\Scripts\\python -m uvicorn app.main:app --port 8000"
            );
          } else if (err.errorType === "ValidationError") {
            showCategorizedError("VALIDATION_ERROR", "Validation Error (HTTP 422)", err.message, "Ensure valid post format.");
          } else if (err.errorType === "TimeoutError") {
            showCategorizedError("NETWORK_TIMEOUT", "Request Timeout (30s)", err.message, "Backend took too long. Check server load.");
          } else {
            showCategorizedError("API_ERROR", `Server Error (${err.status || "Unknown"})`, err.message);
          }
        } else {
          showCategorizedError("APP_ERROR", "Verification Error", err.message);
        }
        await refreshBackendStatus();
      } finally {
        loadingSpinner.classList.add("hidden");
      }
    });

    // ============================================================================
    // 4. COMPREHENSIVE 12-SECTION EXPLAINABLE AI REPORT RENDERER
    // ============================================================================

    function renderResults(res, postData = null) {
      resultsContainer.classList.remove("hidden");

      // Robust fallback access for top-level vs nested responses
      const currentPost = postData || res.post_info || activePayload || {};
      const m1 = res.module_1 || res.module_results?.module_breakdowns?.comments || {};
      const m2 = res.module_2 || res.module_results?.module_breakdowns?.evidence || {};
      const m3 = res.module_3 || res.module_results?.module_breakdowns?.user_behaviour || {};
      const m4 = res.module_4 || res.module_results?.module_breakdowns?.similarity || {};
      const m5 = res.module_5 || res.module_results?.module_breakdowns?.fusion || {};
      const xai = res.xai_explanation || res.module_results?.explainability || {};

      // --------------------------------------------------------------------------
      // SECTION 3: Post Preview Card
      // --------------------------------------------------------------------------
      const platformBadge = document.getElementById("result-platform-badge");
      if (platformBadge) {
        platformBadge.innerText = (currentPost.platform || "generic").toUpperCase();
      }

      const authorHandle = document.getElementById("result-author-handle");
      const cleanAuthor = currentPost.author?.username || currentPost.author_username;
      if (authorHandle) {
        authorHandle.innerText = cleanAuthor ? `@${cleanAuthor}` : "@author_unavailable";
      }

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
      if (postTextEl) {
        postTextEl.innerText = currentPost.text || "";
      }

      const commentCountEl = document.getElementById("result-comment-count");
      if (commentCountEl) {
        const cLen = m1.comment_count != null ? m1.comment_count :
          (Array.isArray(currentPost.comments) ? currentPost.comments.length : 0);
        const totalReplies = currentPost.engagement?.replies;
        if (totalReplies != null && totalReplies > cLen) {
          commentCountEl.innerText = `💬 ${Number(totalReplies).toLocaleString()} replies (${cLen} analyzed)`;
        } else {
          commentCountEl.innerText = `💬 ${cLen} comments`;
        }
      }

      const mediaCountEl = document.getElementById("result-media-count");
      if (mediaCountEl) {
        const mLen = Array.isArray(currentPost.media) ? currentPost.media.length : (res.post_info?.media_count || 0);
        mediaCountEl.innerText = `📷 ${mLen} media`;
      }

      const likesCountEl = document.getElementById("result-likes-count");
      if (likesCountEl) {
        const likes = currentPost.engagement?.likes;
        likesCountEl.innerText = likes != null ? `❤️ ${Number(likes).toLocaleString()} likes` : `❤️ 0 likes`;
      }

      const sharesCountEl = document.getElementById("result-shares-count");
      if (sharesCountEl) {
        const shares = currentPost.engagement?.reposts;
        if (shares != null && shares > 0) {
          sharesCountEl.classList.remove("hidden");
          sharesCountEl.innerText = `🔁 ${Number(shares).toLocaleString()} reposts`;
        } else {
          sharesCountEl.classList.add("hidden");
        }
      }

      // --------------------------------------------------------------------------
      // SECTION 4: Main Verification Card (Credibility Score & 5-Tier Classification)
      // --------------------------------------------------------------------------
      const finalScore = res.consolidated_score != null ? Math.round(res.consolidated_score) : 50;
      const scoreValEl = document.getElementById("credibility-score-val");
      if (scoreValEl) scoreValEl.innerText = finalScore;

      // Radial Gauge Animation
      // Circle radius = 42, circumference = 2 * PI * 42 ≈ 263.89
      const circleProgress = document.getElementById("score-circle-progress");
      if (circleProgress) {
        const circumference = 264;
        const offset = circumference - (Math.max(0, Math.min(100, finalScore)) / 100) * circumference;
        circleProgress.style.strokeDashoffset = offset;

        // Color gauge stroke according to score
        if (finalScore >= 80) circleProgress.style.stroke = "var(--color-likely-real)";
        else if (finalScore >= 60) circleProgress.style.stroke = "var(--color-probably-real)";
        else if (finalScore >= 40) circleProgress.style.stroke = "var(--color-uncertain)";
        else if (finalScore >= 20) circleProgress.style.stroke = "var(--color-probably-fake)";
        else circleProgress.style.stroke = "var(--color-likely-fake)";
      }

      // 5-Tier Classification Badge
      const classificationBadge = document.getElementById("classification-badge");
      const classification = res.classification || m5.classification || "UNCERTAIN";
      if (classificationBadge) {
        classificationBadge.innerText = classification;
        classificationBadge.className = "classification-badge";

        if (classification === "LIKELY REAL") classificationBadge.classList.add("verdict-likely-real");
        else if (classification === "PROBABLY REAL") classificationBadge.classList.add("verdict-probably-real");
        else if (classification === "UNCERTAIN") classificationBadge.classList.add("verdict-uncertain");
        else if (classification === "PROBABLY FAKE") classificationBadge.classList.add("verdict-probably-fake");
        else classificationBadge.classList.add("verdict-likely-fake");
      }

      // Confidence badge & interval
      const confBadge = document.getElementById("confidence-badge");
      const confInterval = document.getElementById("confidence-interval-text");
      const confLevel = m5.confidence_level || "MEDIUM";
      if (confBadge) {
        confBadge.innerText = confLevel;
        confBadge.className = "confidence-pill";
        if (confLevel === "HIGH") confBadge.classList.add("confidence-high");
        else if (confLevel === "LOW") confBadge.classList.add("confidence-low");
        else confBadge.classList.add("confidence-med");
      }

      if (confInterval) {
        if (m5.confidence_interval && Array.isArray(m5.confidence_interval)) {
          const spread = Math.round((m5.confidence_interval[1] - m5.confidence_interval[0]) / 2);
          confInterval.innerText = `±${spread}%`;
        } else {
          confInterval.innerText = "±5.0%";
        }
      }

      const formulaText = document.getElementById("formula-applied-text");
      if (formulaText && m5.formula_applied) {
        formulaText.innerText = m5.formula_applied;
      }

      // --------------------------------------------------------------------------
      // SECTION 9: AI Detection Section (Visually Decoupled from Credibility)
      // --------------------------------------------------------------------------
      const aiProbBadge = document.getElementById("ai-probability-val");
      const aiProbBar = document.getElementById("ai-probability-bar");
      const aiProb = res.ai_generation_probability != null ? res.ai_generation_probability : null;

      if (aiProb !== null && aiProb !== undefined) {
        const pct = Math.round(aiProb * 100);
        if (aiProbBadge) aiProbBadge.innerText = `${pct}% Synthetic`;
        if (aiProbBar) aiProbBar.style.width = `${pct}%`;
      } else {
        if (aiProbBadge) aiProbBadge.innerText = "0% Synthetic";
        if (aiProbBar) aiProbBar.style.width = "0%";
      }

      // --------------------------------------------------------------------------
      // SECTION 5: Analysis Breakdown (Four Modular Cards)
      // --------------------------------------------------------------------------
      // Module 1: Comments
      renderModuleCard(
        "comment",
        m1.score,
        m1.status || "COMPLETED",
        m1.explanation || "Comment sentiment, duplicate coordination, and debunking ratios evaluated."
      );
      updateElementText("m1-metric-count", m1.comment_count != null ? m1.comment_count : 0);
      updateElementText("m1-metric-dups", m1.duplicate_ratio != null ? `${Math.round(m1.duplicate_ratio * 100)}%` : "0%");
      updateElementText("m1-metric-zscore", m1.z_score != null ? Number(m1.z_score).toFixed(1) : "0.0");
      updateElementText("m1-metric-debunk", m1.debunk_ratio != null ? `${Math.round(m1.debunk_ratio * 100)}%` : "0%");

      // Module 2: Evidence
      renderModuleCard(
        "evidence",
        m2.score,
        m2.status || "COMPLETED",
        m2.explanation || "Cross-referenced claims against Google Fact Check Tools and accredited publishers."
      );
      const claimsCount = Array.isArray(m2.claims) ? m2.claims.length : 0;
      const factChecksCount = Array.isArray(m2.fact_checks) ? m2.fact_checks.length : 0;
      updateElementText("m2-metric-claims", claimsCount);
      updateElementText("m2-metric-matches", factChecksCount);
      updateElementText("m2-metric-verified", m2.verified_count != null ? m2.verified_count : 0);
      updateElementText("m2-metric-false", m2.false_count != null ? m2.false_count : 0);

      // Module 3: User Behaviour
      renderModuleCard(
        "behaviour",
        m3.score,
        m3.status || "COMPLETED",
        m3.explanation || "Account age, velocity, and Isolation Forest anomaly score evaluated."
      );
      const isAnomalous = m3.is_anomalous === true;
      const anomalyText = isAnomalous ? "ANOMALOUS" : (m3.status === "UNAVAILABLE" ? "N/A" : "NORMAL");
      updateElementText("m3-metric-anomaly", anomalyText);
      const m3Metrics = m3.metrics || {};
      updateElementText("m3-metric-age", m3Metrics.account_age_days != null ? `${Math.round(m3Metrics.account_age_days)}d` : "--");
      updateElementText("m3-metric-posts-day", m3Metrics.posts_per_day != null ? Number(m3Metrics.posts_per_day).toFixed(1) : "--");
      updateElementText("m3-metric-eng", m3Metrics.engagement_rate != null ? `${(m3Metrics.engagement_rate * 100).toFixed(1)}%` : "--");

      // Module 4: Similar Content
      renderModuleCard(
        "similarity",
        m4.score,
        m4.status || "COMPLETED",
        m4.explanation || "Scanned for perceptual image matches and semantic narrative duplication."
      );
      const isRecycled = m4.recycled_content === true;
      updateElementText("m4-metric-recycled", isRecycled ? "YES" : "NO");
      updateElementText("m4-metric-visual", m4.visual_similarity != null ? `${Math.round(m4.visual_similarity * 100)}%` : "0%");
      updateElementText("m4-metric-semantic", m4.semantic_similarity != null ? `${Math.round(m4.semantic_similarity * 100)}%` : "0%");
      updateElementText("m4-metric-keywords", m4.keyword_similarity != null ? `${Math.round(m4.keyword_similarity * 100)}%` : "0%");

      // --------------------------------------------------------------------------
      // SECTION 6: XAI Section ("Why did Social Guard give this result?")
      // --------------------------------------------------------------------------
      const explanationSummaryEl = document.getElementById("explanation-summary");
      if (explanationSummaryEl) {
        explanationSummaryEl.innerText = xai.summary || res.explanation || "Evaluation completed across all 4 analytical engines.";
      }

      // Positive Factors
      const posFactorsList = document.getElementById("positive-factors-list");
      if (posFactorsList) {
        posFactorsList.innerHTML = "";
        const posFactors = xai.positive_factors || [];
        if (posFactors.length > 0) {
          posFactors.forEach(factor => {
            const li = document.createElement("li");
            li.className = "factor-item factor-item-positive";
            const desc = factor.description || factor.factor || factor;
            li.innerHTML = `<span class="factor-pill-badge pill-pos">Support</span> <span>${escapeHtml(desc)}</span>`;
            posFactorsList.appendChild(li);
          });
        } else {
          posFactorsList.innerHTML = `<li class="factor-item" style="color:var(--text-dim);">No significant positive credibility factors detected.</li>`;
        }
      }

      // Negative Factors
      const negFactorsList = document.getElementById("negative-factors-list");
      if (negFactorsList) {
        negFactorsList.innerHTML = "";
        const negFactors = xai.negative_factors || [];
        if (negFactors.length > 0) {
          negFactors.forEach(factor => {
            const li = document.createElement("li");
            li.className = "factor-item factor-item-negative";
            const desc = factor.description || factor.factor || factor;
            li.innerHTML = `<span class="factor-pill-badge pill-neg">Risk</span> <span>${escapeHtml(desc)}</span>`;
            negFactorsList.appendChild(li);
          });
        } else {
          negFactorsList.innerHTML = `<li class="factor-item" style="color:var(--text-dim);">No significant risk flags or contradictions identified.</li>`;
        }
      }

      // Confidence Notes
      const confNotesList = document.getElementById("confidence-notes-list");
      if (confNotesList) {
        confNotesList.innerHTML = "";
        const notes = xai.confidence_notes || [];
        if (notes.length > 0) {
          notes.forEach(note => {
            const li = document.createElement("li");
            li.className = "factor-item factor-item-confidence";
            li.innerHTML = `<span class="factor-pill-badge pill-note">Note</span> <span>${escapeHtml(note)}</span>`;
            confNotesList.appendChild(li);
          });
        } else {
          const fallbackNote = confLevel === "HIGH" ? "Strong consensus between fact-checking and engagement metrics." :
            "Evaluated with standard conservative baselines for missing or unindexed metadata.";
          confNotesList.innerHTML = `<li class="factor-item factor-item-confidence"><span class="factor-pill-badge pill-note">Note</span> <span>${fallbackNote}</span></li>`;
        }
      }

      // --------------------------------------------------------------------------
      // SECTION 7: Evidence Section (Extracted Claims & Fact Checks)
      // --------------------------------------------------------------------------
      const evidenceCountBadge = document.getElementById("evidence-count-badge");
      const factChecksList = m2.fact_checks || [];
      if (evidenceCountBadge) {
        evidenceCountBadge.innerText = `${factChecksList.length} Checks`;
      }

      const claimsCheckedBlock = document.getElementById("claims-checked-block");
      const claimsCheckedList = document.getElementById("claims-checked-list");
      const extractedClaims = m2.claims || [];

      if (claimsCheckedBlock && claimsCheckedList) {
        if (extractedClaims.length > 0) {
          claimsCheckedBlock.classList.remove("hidden");
          claimsCheckedList.innerHTML = "";
          extractedClaims.forEach(claimStr => {
            const li = document.createElement("li");
            li.className = "claim-item";
            li.innerText = `"${claimStr}"`;
            claimsCheckedList.appendChild(li);
          });
        } else {
          claimsCheckedBlock.classList.add("hidden");
        }
      }

      const evContainer = document.getElementById("evidence-container");
      if (evContainer) {
        evContainer.innerHTML = "";
        if (factChecksList.length > 0) {
          factChecksList.forEach(fc => {
            const item = document.createElement("div");
            item.className = "evidence-item-card";

            const ratingText = fc.rating || fc.review_rating || fc.raw_rating || "Checked";
            const ratingCategory = (fc.rating_category || "").toUpperCase();
            let ratingBadgeClass = "rating-badge-mixed";
            if (ratingCategory === "FALSE" || ratingCategory === "MOSTLY_FALSE") ratingBadgeClass = "rating-badge-false";
            else if (ratingCategory === "TRUE" || ratingCategory === "MOSTLY_TRUE") ratingBadgeClass = "rating-badge-true";

            const rawLink = fc.source_url || fc.publisher_url;
            const safeLink = (rawLink && typeof rawLink === "string" && (rawLink.startsWith("http://") || rawLink.startsWith("https://"))) ? rawLink : null;

            item.innerHTML = `
              <div class="evidence-item-header">
                <span class="evidence-publisher">${escapeHtml(fc.publisher || "Fact Checker")}</span>
                <span class="evidence-rating-badge ${ratingBadgeClass}">${escapeHtml(ratingText)}</span>
              </div>
              <p class="evidence-claim-quote">"${escapeHtml(fc.claim || "")}"</p>
              ${safeLink ? `<a href="${escapeHtml(safeLink)}" target="_blank" rel="noopener noreferrer" class="evidence-source-link">Read Full Review &rarr;</a>` : ""}
            `;
            evContainer.appendChild(item);
          });
        } else {
          const evExplanation = m2.explanation || "No direct third-party fact-check matches found on Google Fact Check Tools.";
          evContainer.innerHTML = `
            <div class="empty-notice-card">
              <span class="empty-main">${escapeHtml(evExplanation)}</span>
              <span class="empty-sub">Evidence module assigned a neutral 50.0 baseline according to XAI standards.</span>
            </div>
          `;
        }
      }

      // --------------------------------------------------------------------------
      // SECTION 8: Similar Content Section (Historical Matches & Recycling)
      // --------------------------------------------------------------------------
      const recycledStatusPill = document.getElementById("recycled-status-pill");
      if (recycledStatusPill) {
        if (isRecycled) {
          recycledStatusPill.innerText = "Recycled Warning";
          recycledStatusPill.style.color = "var(--color-likely-fake)";
        } else {
          recycledStatusPill.innerText = "Original";
          recycledStatusPill.style.color = "var(--color-likely-real)";
        }
      }

      const simContainer = document.getElementById("similar-content-container");
      if (simContainer) {
        simContainer.innerHTML = "";
        if (isRecycled) {
          const matchDate = m4.earliest_matching_timestamp ? m4.earliest_matching_timestamp.slice(0, 10) : "Historical";
          simContainer.innerHTML = `
            <div class="recycled-warning-card">
              <div class="recycled-header">
                <span class="badge-recycled">Recycled Viral Hoax Detected</span>
                <span class="recycled-date">${escapeHtml(matchDate)}</span>
              </div>
              <p class="recycled-explanation">${escapeHtml(m4.explanation || "This narrative closely matches previously debunked viral hoaxes.")}</p>
            </div>
          `;
        } else {
          simContainer.innerHTML = `
            <div class="empty-notice-card">
              <span class="empty-main">Original narrative structure.</span>
              <span class="empty-sub">No recycled viral hoax matches detected in local reference corpus.</span>
            </div>
          `;
        }

        // Show matching items if any exist
        const matches = m4.matches || [];
        if (matches.length > 0) {
          matches.forEach(m => {
            const mEl = document.createElement("div");
            mEl.className = "similar-match-item";
            mEl.innerHTML = `
              <span class="match-title">${escapeHtml(m.title || m.id || "Corpus Match")}</span>
              <span class="match-meta">Visual: ${Math.round((m.visual_similarity || 0) * 100)}% | Semantic: ${Math.round((m.semantic_similarity || 0) * 100)}%</span>
            `;
            simContainer.appendChild(mEl);
          });
        }
      }

      // Scroll smoothly to top of results
      resultsContainer.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    // Helper: Module card updater
    function renderModuleCard(name, score, status, explanation) {
      const scoreEl = document.getElementById(`score-${name}`);
      const barEl = document.getElementById(`bar-${name}`);
      const statusEl = document.getElementById(`status-${name}`);
      const descEl = document.getElementById(`desc-${name}`);

      if (descEl && explanation) {
        descEl.innerText = explanation;
      }

      if (score != null) {
        const val = Math.round(score);
        if (scoreEl) scoreEl.innerText = `${val}/100`;
        if (barEl) {
          barEl.style.width = `${Math.min(100, Math.max(0, val))}%`;
          if (val >= 70) barEl.className = "progress-bar-fill bar-high";
          else if (val >= 40) barEl.className = "progress-bar-fill bar-mid";
          else barEl.className = "progress-bar-fill bar-low";
        }
      } else {
        if (scoreEl) scoreEl.innerText = "--/100";
        if (barEl) {
          barEl.style.width = "0%";
          barEl.className = "progress-bar-fill";
        }
      }

      if (statusEl) {
        statusEl.innerText = (status || "COMPLETED").toUpperCase();
        statusEl.className = "module-status-badge";
        const st = (status || "").toUpperCase();
        if (st === "COMPLETED") statusEl.classList.add("status-completed");
        else if (st === "PARTIAL") statusEl.classList.add("status-partial");
        else if (st === "UNAVAILABLE") statusEl.classList.add("status-unavailable");
        else if (st === "ERROR") statusEl.classList.add("status-error");
        else statusEl.classList.add("status-pending");
      }
    }

    function updateElementText(id, text) {
      const el = document.getElementById(id);
      if (el) el.innerText = text;
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
