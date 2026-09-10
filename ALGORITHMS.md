# Social Guard: Algorithmic Architecture & Mathematical Foundations

**Project:** Social Guard: An Explainable AI Framework for Social Media Content Verification  
**Academic Reference Document:** ALGORITHMS.md  
**Status:** Canonical Reference (Production Implemented & Audited)

---

## Overview of Analytical Engine

Social Guard evaluates social media content credibility across 5 specialized analytical modules and an independent AI generation detector.

| Module | Purpose | Status |
| :--- | :--- | :---: |
| **Module 1: Comment Analysis Engine** | Duplicate detection, semantic coordination, emoji manipulation, and temporal burst analysis. | **IMPLEMENTED** |
| **Module 2: Evidence-Based Verification** | Claim extraction, Google Fact Check Tools API retrieval, rating normalization, and source weighting. | **IMPLEMENTED** |
| **Module 3: User Behaviour Analysis** | Tabular feature engineering, Isolation Forest anomaly scoring, and velocity rules. | **IMPLEMENTED** |
| **Module 4: Similar Content & Hashtags** | Jaccard hashtag overlap, keyword extraction, S-BERT semantic search, pHash perceptual image comparison, and recycling temporal decay. | **IMPLEMENTED** |
| **Module 5: Score Fusion & XAI Engine** | Linear weighted fusion, 5-tier classification bands, grounded explainability synthesis. | **IMPLEMENTED** |
| **Orthogonal AI Media Detector** | Statistical frequency gradient variance and lexical uniformity text detection. | **IMPLEMENTED** |
| **OCR & Vision-Language CLIP** | Deep optical text extraction and multi-modal image-text semantic alignment. | **FUTURE WORK** |

---

# Module 1: Comment Analysis Engine

### 1.1 Natural Language Preprocessing (NLP)
- **Status:** **IMPLEMENTED**
- **1. What it is:** Text cleaning, URL stripping, unicode normalization, and tokenization pipeline designed for social media comments.
- **2. Why Social Guard uses it:** Comment threads contain excessive noise (emojis, URLs, non-alphanumeric symbols) that distort distance metrics.
- **3. Input:** Raw comment string $c_i \in C$.
- **4. Processing:** Strips HTTP/HTTPS URLs, normalizes whitespace, separates unicode emojis, and lowercases text.
- **5. Output:** Cleaned text string for semantic embedding and normalized string for exact deduplication.
- **6. Limitations:** May strip meaningful semantic content embedded inside URL slugs.

### 1.2 Sentence-BERT Embeddings
- **Status:** **IMPLEMENTED**
- **1. What it is:** Siamese/Triplet transformer neural network (`all-MiniLM-L6-v2`) generating dense vector representations $\mathbf{v} \in \mathbb{R}^{384}$.
- **2. Why Social Guard uses it:** Captures paraphrased, semantically identical bot spam that evades exact string matching.
- **3. Input:** Cleaned comment text strings.
- **4. Processing:** Computes mean-pooled contextual embeddings across subword tokens.
- **5. Output:** 384-dimensional dense floating-point vector for each comment.
- **6. Limitations:** Higher computational inference cost compared to bag-of-words methods.

### 1.3 Cosine Similarity
- **Status:** **IMPLEMENTED**
- **1. What it is:** Angle-based similarity metric between vector pairs:
  $$\text{CosineSim}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2}$$
- **2. Why Social Guard uses it:** Measures semantic closeness independent of comment length.
- **3. Input:** Vector embeddings for all comment pairs $(c_i, c_j)$.
- **4. Processing:** Computes pairwise cosine similarity matrix; pairs exceeding threshold $\tau = 0.85$ are flagged as near-duplicates.
- **5. Output:** Pairwise similarity scores and aggregate `average_similarity` metric $\in [0.0, 1.0]$.
- **6. Limitations:** Pairwise computation has quadratic complexity $O(N^2)$ with comment count $N$.

### 1.4 Emoji Entropy & Distribution Analysis
- **Status:** **IMPLEMENTED**
- **1. What it is:** Shannon entropy metric measuring the informational diversity of emoji usage:
  $$H(E) = -\sum_{e \in E} p(e) \log_2 p(e)$$
- **2. Why Social Guard uses it:** Coordinated bot farms frequently spam identical alarmist emojis (e.g. 🚨🚨🚨) resulting in $H(E) \to 0$.
- **3. Input:** Array of extracted unicode emojis across comments.
- **4. Processing:** Computes frequency distribution $p(e)$, calculates Shannon entropy $H(E)$, and measures `excessive_emoji_ratio`.
- **5. Output:** Entropy value $H(E) \geq 0$ and emoji manipulation penalty.
- **6. Limitations:** Sarcasm or authentic cultural meme trends may also exhibit low emoji diversity.

### 1.5 Z-score & IQR Temporal Burst Detection
- **Status:** **IMPLEMENTED**
- **1. What it is:** Parametric (Z-score) and non-parametric (Interquartile Range) statistical anomaly detection on comment arrival rates.
  $$Z = \frac{x - \mu}{\sigma}, \quad \text{IQR} = Q_3 - Q_1$$
- **2. Why Social Guard uses it:** Identifies inorganic brigading where dozens of comments flood a post within seconds.
- **3. Input:** Comment arrival timestamps sorted chronologically.
- **4. Processing:** Bins comments into 1-minute intervals; flags intervals where $Z > 3.0$ or $x > Q_3 + 1.5 \times \text{IQR}$.
- **5. Output:** `temporal_anomaly_score` $\in [0.0, 1.0]$ and boolean burst flags.
- **6. Limitations:** Breaking authentic viral events can naturally cause high arrival spikes.

---

# Module 2: Evidence-Based Verification Engine

### 2.1 Rule-Based Claim Extraction
- **Status:** **IMPLEMENTED**
- **1. What it is:** Syntactic filter that isolates verifiable factual assertions from subjective opinion statements.
- **2. Why Social Guard uses it:** Prevents querying fact-check search engines with conversational chatter or personal opinions.
- **3. Input:** Full social media post text.
- **4. Processing:** Regex filtering of opinion prefixes ("I think", "In my opinion") and entity boundary isolation.
- **5. Output:** List of clean factual claim strings.
- **6. Limitations:** Does not parse complex multi-clause dependent assertions as effectively as fine-tuned LLM claim extractors.

### 2.2 Google Fact Check Tools API Integration
- **Status:** **IMPLEMENTED**
- **1. What it is:** REST client querying the Google Fact Check Tools API (`FactCheckClaimSearch`).
- **2. Why Social Guard uses it:** Connects directly to global verified journalistic fact-check databases (e.g., Reuters, Snopes, AFP, PolitiFact).
- **3. Input:** Extracted claim query strings.
- **4. Processing:** Asynchronous HTTP GET requests with API rate-limit and timeout handling.
- **5. Output:** JSON claim review objects including publisher names, ratings, and URLs.
- **6. Limitations:** Dependent on external network availability and API quotas.

### 2.3 Fact-Check Rating Normalization
- **Status:** **IMPLEMENTED**
- **1. What it is:** Deterministic mapping translating heterogeneous text ratings into a continuous truth score $S_{\text{truth}} \in [0.0, 1.0]$.
  - `"True"`, `"Correct"` $\to 1.0$ (`TRUE`)
  - `"Mostly True"`, `"Half True"` $\to 0.75$ (`MOSTLY_TRUE`)
  - `"Mixture"`, `"Unproven"` $\to 0.50$ (`MIXED`)
  - `"Mostly False"` $\to 0.25$ (`MOSTLY_FALSE`)
  - `"False"`, `"Pants on Fire"`, `"Hoax"` $\to 0.0$ (`FALSE`)
- **2. Why Social Guard uses it:** Fact-checkers use non-standardized terminology that must be normalized for mathematical fusion.
- **3. Input:** Textual rating string from publisher review.
- **4. Processing:** Case-insensitive keyword matching and category mapping.
- **5. Output:** Normalized float score $S_{\text{truth}} \in [0.0, 1.0]$ and categorical rating.
- **6. Limitations:** Nuanced contextual ratings may lose slight qualitative subtleties during continuous quantization.

### 2.4 Publisher Source Credibility Weighting
- **Status:** **IMPLEMENTED**
- **1. What it is:** Curated tier-weighting assigning credibility coefficients $W_{\text{src}} \in [0.5, 1.0]$ based on IFCN accreditation.
- **2. Why Social Guard uses it:** Gives higher mathematical priority to established international fact-checking organizations.
- **3. Input:** Publisher organization name and site domain.
- **4. Processing:** Lookup against IFCN signatory registry; defaults unlisted sources to baseline $0.70$.
- **5. Output:** Source weight coefficient $W_{\text{src}}$.
- **6. Limitations:** Curated list requires periodic manual maintenance.

### 2.5 Optical Character Recognition (OCR)
- **Status:** **FUTURE WORK**
- **1. What it is:** Computer vision extraction of embedded text overlay within image/video frames (e.g. via Tesseract or EasyOCR).
- **2. Why Social Guard uses it:** Social media hoaxes frequently circulate as screenshots of fake news headlines or quote graphics.
- **3. Current State:** Architecture interfaces and database schemas include `ocr_extracted_text` fields; pipeline currently relies on direct post text input pending vision model runtime integration.

---

# Module 3: User Behaviour Analysis Engine

### 3.1 Tabular Feature Engineering
- **Status:** **IMPLEMENTED**
- **1. What it is:** Feature extraction mapping raw public profile metadata to 10 normalized statistical behavioral signals:
  1. `account_age_days`
  2. `followers`
  3. `following`
  4. `follower_following_ratio`
  5. `posts_per_day`
  6. `comments_per_day`
  7. `average_posting_interval_seconds`
  8. `engagement_rate`
  9. `duplicate_content_ratio`
  10. `hashtag_repetition_rate`
- **2. Why Social Guard uses it:** Quantifies behavioral automation, account maturity, and posting velocity.
- **3. Input:** Public `UserProfile` object.
- **4. Processing:** Feature extraction, median imputation for missing values, and min-max/log scaling.
- **5. Output:** 10-dimensional real feature vector $\mathbf{x} \in \mathbb{R}^{10}$.
- **6. Limitations:** Relies on visible profile metadata; private accounts or platforms with restricted metadata require median imputation.

### 3.2 Isolation Forest Anomaly Detection
- **Status:** **IMPLEMENTED**
- **1. What it is:** Tree-based unsupervised ensemble algorithm that isolates anomalies by randomly partitioning feature space.
- **2. Why Social Guard uses it:** Identifies non-linear multidimensional outliers without requiring labeled bot training sets.
- **3. Input:** Vectorized user feature representation $\mathbf{x}$.
- **4. Processing:** Evaluates average path length $h(\mathbf{x})$ across isolation trees; short path lengths indicate anomalous behavioral profiles.
- **5. Output:** Continuous anomaly score $\in [0.0, 1.0]$ and decision flag.
- **6. Limitations:** An anomalous user pattern indicates unusual automation or behavior, not guaranteed factual falsity.

### 3.3 Parametric Z-score & IQR Profile Outliers
- **Status:** **IMPLEMENTED**
- **1. What it is:** Univariate statistical testing against reference baseline distributions for velocity and duplication.
- **2. Why Social Guard uses it:** Provides interpretable individual feature diagnostics (e.g. `posts_per_day > 100`).
- **3. Input:** Specific scalar feature values.
- **4. Processing:** Evaluates Z-score and boxplot quartile boundaries.
- **5. Output:** Diagnostic metrics (`posts_per_day_zscore`, `duplicate_iqr_outlier`).
- **6. Limitations:** Assumes approximately normal distribution for parametric Z-score tests.

### 3.4 Rule-Based Behavioural Scoring
- **Status:** **IMPLEMENTED**
- **1. What it is:** Transparent multi-penalty formula calculating final `behaviour_score` $\in [0, 100]$:
  $$\text{Score} = 100 - (\text{Velocity Penalty} + \text{Duplication Penalty} + \text{Asymmetry Penalty} + \text{Anomaly Penalty})$$
- **2. Why Social Guard uses it:** Ensures clear, auditable reasoning for why an account was scored high or low.
- **3. Input:** Feature values and Isolation Forest output.
- **4. Processing:** Clamped linear deductions with bounded output $[0, 100]$.
- **5. Output:** Final Behaviour Score (0–100) and human-readable flags.
- **6. Limitations:** Fixed heuristic deduction weights.

---

# Module 4: Similar Content & Hashtag Analysis Engine

### 4.1 Hashtag Jaccard Similarity
- **Status:** **IMPLEMENTED**
- **1. What it is:** Set intersection over union:
  $$J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$
- **2. Why Social Guard uses it:** Detects coordinated hashtag campaigns across posts.
- **3. Input:** Extracted hashtag sets from post and historical corpus.
- **4. Processing:** Tokenizes, lowercases, and calculates set overlap.
- **5. Output:** Jaccard similarity index $\in [0.0, 1.0]$.
- **6. Limitations:** Sensitive to minor hashtag spelling variations.

### 4.2 Keyword Tokenization & Matching
- **Status:** **IMPLEMENTED**
- **1. What it is:** Stopword-filtered lexical token overlap.
- **2. Why Social Guard uses it:** Fast initial candidate retrieval from historical database.
- **3. Input:** Post text and corpus items.
- **4. Processing:** Tokenization, stopword removal, and term frequency intersection.
- **5. Output:** Lexical overlap ratio.
- **6. Limitations:** Does not capture synonyms or paraphrased wording.

### 4.3 Sentence-BERT Semantic Search & Cosine Similarity
- **Status:** **IMPLEMENTED**
- **1. What it is:** Dense semantic embedding comparison against historical knowledge corpus.
- **2. Why Social Guard uses it:** Matches recycled textual hoaxes even when wording has been slightly modified.
- **3. Input:** Post text embedding and corpus embeddings.
- **4. Processing:** Dot product of normalized embedding vectors.
- **5. Output:** Continuous `text_similarity` $\in [0.0, 1.0]$.
- **6. Limitations:** Requires corpus vector index for sub-millisecond retrieval at scale.

### 4.4 Perceptual Image Hashing (pHash) & Hamming Distance
- **Status:** **IMPLEMENTED**
- **1. What it is:** Frequency-domain Discrete Cosine Transform (DCT) based image fingerprinting producing 64-bit hex hash.
- **2. Why Social Guard uses it:** Matches recycled misinformation images even if resized, compressed, or re-encoded.
- **3. Input:** Attached image bytes or URL.
- **4. Processing:** Resizes to 32x32 grayscale, computes DCT, extracts 8x8 low frequencies, generates 64-bit hash, and measures Hamming distance $D_H$.
  $$\text{Similarity} = 1.0 - \frac{D_H}{64}$$
- **5. Output:** `image_similarity` $\in [0.0, 1.0]$ and exact hash match boolean.
- **6. Limitations:** Severe cropping or heavy image overlays can alter the hash.

### 4.5 Temporal Content Recycling Decay
- **Status:** **IMPLEMENTED**
- **1. What it is:** Age difference calculation between current post timestamp $T_{\text{curr}}$ and earliest historical match $T_{\text{orig}}$:
  $$\Delta t = T_{\text{curr}} - T_{\text{orig}}$$
- **2. Why Social Guard uses it:** Recirculating old crisis footage/hoaxes years later as "breaking news" is a major vector of disinformation.
- **3. Input:** Post timestamp and matched historical corpus item timestamp.
- **4. Processing:** If text/image similarity $> 0.80$ and $\Delta t > 90\text{ days}$, flags `recycled_content = True` and deducts similarity score.
- **5. Output:** `recycled_content` flag, `recycled_age_days`, and penalized score.
- **6. Limitations:** Requires historical items to have accurate creation timestamps.

### 4.6 Vision-Language Alignment (CLIP)
- **Status:** **OPTIONAL / FUTURE WORK**
- **1. What it is:** OpenAI Contrastive Language-Image Pretraining (CLIP) mapping image and text into a shared multi-modal embedding space.
- **2. Why Social Guard uses it:** Detects "out-of-context" image captions (e.g. real earthquake photo paired with unrelated fake war headline).
- **3. Current State:** Abstracted interface defined; basic implementation uses decoupled pHash + S-BERT to remain lightweight for college project resource constraints.

---

# Module 5: Score Fusion & Explainability Engine

### 5.1 Score Normalization & Clamping
- **Status:** **IMPLEMENTED**
- **1. What it is:** Mathematical validation and bounded clamping ensuring all module inputs satisfy $S_i \in [0.0, 100.0]$.
- **2. Why Social Guard uses it:** Protects against out-of-bounds inputs or module calculation anomalies.
- **3. Input:** Raw module scores ($S_{\text{comment}}, S_{\text{evidence}}, S_{\text{behaviour}}, S_{\text{similarity}}$).
- **4. Processing:** Missing scores default to neutral baseline $50.0$; values are clamped: $\min(100.0, \max(0.0, S))$.
- **5. Output:** Calibrated scores $\in [0.0, 100.0]$.
- **6. Limitations:** Neutral default (50.0) represents uncertainty, not verified balance.

### 5.2 Linear Weighted Fusion
- **Status:** **IMPLEMENTED**
- **1. What it is:** Multi-criteria weighted linear combination:
  $$S_{\text{final}} = w_c \cdot S_c + w_e \cdot S_e + w_b \cdot S_b + w_s \cdot S_s$$
  $$\text{where } w_c = 0.20, \; w_e = 0.40, \; w_b = 0.15, \; w_s = 0.25, \quad \sum w_i = 1.0$$
- **2. Why Social Guard uses it:** Evidence verification carries primary weight (0.40), while comments, behaviour, and similarity provide vital contextual signals.
- **3. Input:** 4 normalized module scores and weight vector.
- **4. Processing:** Computes linear sum and individual module absolute contributions $C_i = w_i \cdot S_i$.
- **5. Output:** Final Consolidated Credibility Score $S_{\text{final}} \in [0.0, 100.0]$.
- **6. Limitations:** Linear weights assume additive independence between dimensions.

### 5.3 5-Tier Categorical Classification
- **Status:** **IMPLEMENTED**
- **1. What it is:** Threshold decision rule mapping continuous score to human-interpretable credibility bands:
  - **80.0 – 100.0:** `LIKELY REAL`
  - **60.0 – 79.99:** `PROBABLY REAL`
  - **40.0 – 59.99:** `UNCERTAIN`
  - **20.0 – 39.99:** `PROBABLY FAKE`
  - **0.0 – 19.99:** `LIKELY FAKE`
- **2. Why Social Guard uses it:** Communicates actionable trust levels to end-users without ambiguity.
- **3. Input:** $S_{\text{final}} \in [0.0, 100.0]$.
- **4. Processing:** Range conditional branching.
- **5. Output:** `CredibilityClassification` enum value.
- **6. Limitations:** Sharp boundary transitions near band cutoffs (e.g. 79.9 vs 80.0).

### 5.4 Explainability (XAI) Synthesis
- **Status:** **IMPLEMENTED**
- **1. What it is:** Factor-ranking engine that identifies the strongest positive and negative signals across all modules to generate concise, grounded explanations.
- **2. Why Social Guard uses it:** Black-box scores lack user trust; XAI provides grounded reasons (e.g. "Contradicted by Snopes fact-check", "Anomalous posting velocity detected").
- **3. Input:** Final score, module breakdowns, flags, and AI probability.
- **4. Processing:** Ranks factors by deviation from neutral 50.0 baseline; synthesizes a natural language summary without fabricating unobserved evidence.
- **5. Output:** Structured explanation object containing `summary`, `positive_factors`, `negative_factors`, and `module_reasons`.
- **6. Limitations:** Template-guided synthesis rather than generative LLM paragraph generation.

---

# Independent Component: AI-Generated Media & Text Detection

### 6.1 Statistical Gradient Variance & Frequency Analysis
- **Status:** **IMPLEMENTED**
- **1. What it is:** High-frequency gradient smoothness analysis and color histogram entropy detection on images.
- **2. Why Social Guard uses it:** Diffusion and GAN models often leave distinct smooth textures or frequency artifacts.
- **3. Input:** Image byte array.
- **4. Processing:** Converts image to grayscale, computes 2D spatial gradients $\nabla I = (\frac{\partial I}{\partial x}, \frac{\partial I}{\partial y})$, and calculates gradient variance.
- **5. Output:** `ai_generation_probability` $\in [0.0, 100.0]$.
- **6. Limitations:** High-end modern diffusion models (e.g. Midjourney v6, FLUX) produce subtle artifacts that require deep vision transformer classifiers.

### 6.2 Lexical Uniformity Text Detector
- **Status:** **IMPLEMENTED**
- **1. What it is:** Statistical text analyzer measuring Type-Token Ratio (TTR) and sentence length variance.
- **2. Why Social Guard uses it:** Synthetic LLM text typically exhibits lower burstiness and highly uniform lexical distributions.
- **3. Input:** Post text.
- **4. Processing:** Computes vocabulary ratio and sentence length standard deviation.
- **5. Output:** Standalone synthetic text probability $\in [0.0, 100.0]$.
- **6. Limitations:** Short sentences ($< 15$ words) return `TEXT_TOO_SHORT` due to insufficient sample variance.
