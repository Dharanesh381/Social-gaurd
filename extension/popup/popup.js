/**
 * Social Guard: Professional Academic Extension Controller
 * Handles live DOM extraction, academic preset test cases, FastAPI communication,
 * and high-clarity rendering of scores, XAI reasoning, fact checks, and corpus matches.
 */

import { SocialGuardApiClient } from "./api_client.js";

// ==============================================================================
// 1. ACADEMIC TEST PRESET SCENARIOS
// ==============================================================================

const TEST_PRESETS = {
  real: {
    platform: "twitter",
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
    platform: "facebook",
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

let activePayload = JSON.parse(JSON.stringify(TEST_PRESETS.real));

function sanitizeHTML(str) {
  if (!str) return "";
  const temp = document.createElement("div");
  temp.textContent = str;
  return temp.innerHTML;
}

// ==============================================================================
// 2. DOM CONTROLLER & EVENT WIRING
// ==============================================================================

document.addEventListener("DOMContentLoaded", async () => {
  const statusBadge = document.getElementById("backend-status-badge");
  const postTextInput = document.getElementById("post-text-input");
  const platformChip = document.getElementById("detected-platform");
  const commentsChip = document.getElementById("detected-comments-count");
  const mediaChip = document.getElementById("detected-media-count");

  const presetRealBtn = document.getElementById("preset-real-btn");
  const presetUncertainBtn = document.getElementById("preset-uncertain-btn");
  const presetFakeBtn = document.getElementById("preset-fake-btn");
  const extractPageBtn = document.getElementById("extract-page-btn");
  const runVerifyBtn = document.getElementById("run-verify-btn");

  const loadingSpinner = document.getElementById("loading-spinner");
  const errorBox = document.getElementById("error-box");
  const errorMessage = document.getElementById("error-message");
  const resultsContainer = document.getElementById("results-container");

  // Load initial preset
  loadPreset("real");

  // Health check
  await refreshBackendStatus();

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

  function loadPreset(presetKey) {
    activePayload = JSON.parse(JSON.stringify(TEST_PRESETS[presetKey]));
    postTextInput.value = activePayload.text;
    platformChip.innerText = `Platform: ${activePayload.platform.toUpperCase()}`;
    commentsChip.innerText = `Comments: ${activePayload.comments.length}`;
    mediaChip.innerText = `Media: ${activePayload.media.length}`;
    errorBox.classList.add("hidden");
  }

  presetRealBtn.addEventListener("click", () => loadPreset("real"));
  presetUncertainBtn.addEventListener("click", () => loadPreset("uncertain"));
  presetFakeBtn.addEventListener("click", () => loadPreset("fake"));

  // Extract from current page
  extractPageBtn.addEventListener("click", async () => {
    try {
      if (typeof chrome === "undefined" || !chrome.tabs) {
        alert("Chrome extension runtime not detected. Use the preset test buttons to test the UI.");
        return;
      }

      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab) {
        alert("No active browser tab found.");
        return;
      }

      chrome.tabs.sendMessage(tab.id, { action: "EXTRACT_PAGE_CONTENT" }, (response) => {
        if (chrome.runtime.lastError || !response || response.status !== "SUCCESS") {
          alert("Could not extract structured text from this page. You can paste text manually into the box.");
          return;
        }

        const data = response.data;
        activePayload = {
          platform: data.platform || "generic",
          text: data.text ? data.text.trim() : "No text available.",
          hashtags: data.hashtags || [],
          media: (data.image_urls || []).map(url => ({ url, media_type: "image" })),
          author: {
            username: "page_author",
            followers: 0,
            following: 0
          },
          comments: data.comments || []
        };

        postTextInput.value = activePayload.text;
        platformChip.innerText = `Platform: ${activePayload.platform.toUpperCase()}`;
        commentsChip.innerText = `Comments: ${activePayload.comments.length}`;
        mediaChip.innerText = `Media: ${activePayload.media.length}`;
      });
    } catch (err) {
      console.warn("Extraction error:", err);
      alert("Extraction failed: " + err.message);
    }
  });

  // Execute Verification
  runVerifyBtn.addEventListener("click", async () => {
    const rawText = postTextInput.value.trim();
    if (!rawText || rawText.length < 5) {
      alert("Please provide at least 5 characters of post content to verify.");
      return;
    }

    activePayload.text = rawText;
    loadingSpinner.classList.remove("hidden");
    resultsContainer.classList.add("hidden");
    errorBox.classList.add("hidden");

    try {
      const result = await SocialGuardApiClient.analyzePost({
        request_id: `sg_ext_${Date.now()}`,
        post: activePayload
      });

      renderResults(result);
    } catch (err) {
      errorBox.classList.remove("hidden");
      errorMessage.innerText = `Verification request failed: ${err.message}. Please verify the FastAPI backend is running on http://127.0.0.1:8000.`;
      await refreshBackendStatus();
    } finally {
      loadingSpinner.classList.add("hidden");
    }
  });

  // ============================================================================
  // 3. RESULTS RENDERER (Strictly Aligned with Prompt Specification)
  // ============================================================================

  function renderResults(res) {
    resultsContainer.classList.remove("hidden");

    // 1. Classification & Score
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

    // 2. AI Probability (Decoupled Output)
    const aiProbEl = document.getElementById("ai-probability-val");
    if (res.ai_generation_probability != null) {
      const pct = Math.round(res.ai_generation_probability * 100);
      aiProbEl.innerText = `${pct}%`;
    } else {
      aiProbEl.innerText = "N/A (No Media/Insufficient Text)";
    }

    // 3. Module Scores (0 - 100)
    const scores = res.module_scores || {};
    updateModuleScore("comment", scores.comment_analysis);
    updateModuleScore("evidence", scores.evidence_verification);
    updateModuleScore("behaviour", scores.user_behaviour);
    updateModuleScore("similarity", scores.similar_content);

    // 4. WHY THIS RESULT? (Explainability Synthesis)
    const summaryEl = document.getElementById("explanation-summary");
    summaryEl.innerText = res.explanation || "Verification analysis complete.";

    const reasonsList = document.getElementById("reasons-list");
    reasonsList.innerHTML = "";

    const xai = res.module_results?.explainability || {};
    const factors = [...(xai.negative_factors || []), ...(xai.positive_factors || [])];

    if (factors.length > 0) {
      factors.slice(0, 5).forEach(f => {
        const li = document.createElement("li");
        li.className = "reason-item";
        li.textContent = typeof f === "object" && f.factor ? f.factor : String(f);
        reasonsList.appendChild(li);
      });
    }

    // 5. EVIDENCE (Fact checks & Sources)
    const evidenceContainer = document.getElementById("evidence-container");
    evidenceContainer.innerHTML = "";

    const evData = res.module_results?.module_breakdowns?.evidence || {};
    const factChecks = evData.fact_checks || [];

    if (factChecks.length > 0) {
      factChecks.forEach(fc => {
        const itemDiv = document.createElement("div");
        itemDiv.className = "evidence-item";

        const headerDiv = document.createElement("div");
        headerDiv.className = "evidence-header";

        const pubSpan = document.createElement("span");
        pubSpan.className = "evidence-pub";
        pubSpan.textContent = fc.publisher || "Fact Check Organization";

        const ratingSpan = document.createElement("span");
        ratingSpan.className = "evidence-rating";
        const cat = fc.rating_category || "UNKNOWN";
        ratingSpan.textContent = fc.raw_rating || cat;

        if (cat === "TRUE" || cat === "MOSTLY_TRUE") ratingSpan.classList.add("rating-true");
        else if (cat === "FALSE" || cat === "MOSTLY_FALSE") ratingSpan.classList.add("rating-false");
        else ratingSpan.classList.add("rating-mixed");

        headerDiv.appendChild(pubSpan);
        headerDiv.appendChild(ratingSpan);
        itemDiv.appendChild(headerDiv);

        if (fc.publisher_url) {
          const link = document.createElement("a");
          link.href = fc.publisher_url;
          link.target = "_blank";
          link.className = "evidence-link";
          link.textContent = `View Source: ${fc.claim || "Fact check review"}`;
          itemDiv.appendChild(link);
        }

        evidenceContainer.appendChild(itemDiv);
      });
    } else {
      const emptyDiv = document.createElement("div");
      emptyDiv.className = "empty-state";
      emptyDiv.textContent = "No existing third-party fact-check records found for this claim (Neutral 50/100 baseline applied).";
      evidenceContainer.appendChild(emptyDiv);
    }

    // 6. SIMILAR CONTENT (Corpus matches & Timestamps)
    const similarContainer = document.getElementById("similar-content-container");
    similarContainer.innerHTML = "";

    const simData = res.module_results?.module_breakdowns?.similarity || {};
    if (simData.recycled_content) {
      const matchDiv = document.createElement("div");
      matchDiv.className = "evidence-item";

      const headerDiv = document.createElement("div");
      headerDiv.className = "evidence-header";

      const titleSpan = document.createElement("span");
      titleSpan.className = "evidence-pub";
      titleSpan.style.color = "var(--color-probably-fake)";
      titleSpan.textContent = "⚠️ Recycled Content Detected";

      const badgeSpan = document.createElement("span");
      badgeSpan.className = "evidence-rating rating-false";
      badgeSpan.textContent = "Recycled";

      headerDiv.appendChild(titleSpan);
      headerDiv.appendChild(badgeSpan);
      matchDiv.appendChild(headerDiv);

      const p = document.createElement("p");
      p.style.marginTop = "4px";
      p.style.color = "var(--text-muted)";
      p.textContent = `Matches previously recorded viral narrative${simData.earliest_matching_timestamp ? ` (First recorded: ${simData.earliest_matching_timestamp})` : ""}.`;
      matchDiv.appendChild(p);

      similarContainer.appendChild(matchDiv);
    } else if (simData.similar_content_count > 0) {
      const matchDiv = document.createElement("div");
      matchDiv.className = "empty-state";
      matchDiv.textContent = `Found ${simData.similar_content_count} related content references in the local knowledge corpus (Semantic text similarity: ${Math.round((simData.text_similarity || 0) * 100)}%).`;
      similarContainer.appendChild(matchDiv);
    } else {
      const emptyDiv = document.createElement("div");
      emptyDiv.className = "empty-state";
      emptyDiv.textContent = "No matching older or recycled viral narratives found in historical corpus (High originality).";
      similarContainer.appendChild(emptyDiv);
    }
  }

  function updateModuleScore(moduleName, score) {
    const textEl = document.getElementById(`score-${moduleName}`);
    const barEl = document.getElementById(`bar-${moduleName}`);
    if (score != null) {
      const rounded = Math.round(score);
      textEl.innerText = `${rounded}/100`;
      barEl.style.width = `${rounded}%`;
      if (rounded >= 80) barEl.style.backgroundColor = "var(--color-likely-real)";
      else if (rounded >= 60) barEl.style.backgroundColor = "var(--color-probably-real)";
      else if (rounded >= 40) barEl.style.backgroundColor = "var(--color-uncertain)";
      else if (rounded >= 20) barEl.style.backgroundColor = "var(--color-probably-fake)";
      else barEl.style.backgroundColor = "var(--color-likely-fake)";
    } else {
      textEl.innerText = "N/A";
      barEl.style.width = "0%";
    }
  }
});
