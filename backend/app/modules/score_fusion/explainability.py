"""Explainability Engine for Social Guard.

Synthesizes multi-module signals, ranks positive and negative factors,
generates factual diagnostic audit trails, and strictly separates
factual credibility, behavioral suspicion, and AI-generation likelihood.
"""

from typing import Any


class ExplainabilityEngine:
    """Explainable AI (XAI) summary generator for Social Guard.

    Translates granular numerical outputs, flags, and states from Modules 1-5
    into ranked positive/negative contributing factors and plain-language audit trails.

    STRICT CONSTRAINTS:
    - Never invent evidence.
    - Never claim a signal exists if the module metrics/flags do not report it.
    - Clearly separate factual credibility from user behaviour anomalies and AI probability.
    - If no fact-check is found, explicitly explain that the claim remains unverified.
    - Never claim author account longevity unless account_age_days is explicitly present in metadata.
    - Clearly denote the local 3-item historical corpus boundary when no match is found in M4.
    """

    def generate_explanation(
        self,
        final_score: float,
        classification: str,
        module_breakdowns: dict[str, dict[str, Any]],
        ai_generated_probability: float | None = None,
    ) -> dict[str, Any]:
        """Generate structured explainability response with complete factual trace.

        Args:
            final_score: Consolidated credibility score [0.0 - 100.0]
            classification: Verdict category (e.g. 'LIKELY REAL', 'PROBABLY FAKE')
            module_breakdowns: Dict containing raw outputs of all modules:
                - 'comments': {score, metrics, flags}
                - 'evidence': {score, status, claims, fact_checks, flags, explanation, diagnostics}
                - 'user_behaviour': {score, anomaly_score, metrics, flags, explanation}
                - 'similarity': {score, text_similarity, image_similarity, recycled_content, flags, ...}
                - 'fusion': {final_score, module_contributions, confidence_level, ...}
            ai_generated_probability: Optional decoupled probability [0.0 - 1.0]

        Returns:
            Dict conforming to:
            {
                "summary": str,
                "positive_factors": List[Dict[str, Any]],
                "negative_factors": List[Dict[str, Any]],
                "module_explanations": Dict[str, str],
                "confidence_notes": List[str]
            }
        """
        positive_factors: list[dict[str, Any]] = []
        negative_factors: list[dict[str, Any]] = []
        module_explanations: dict[str, str] = {}
        confidence_notes: list[str] = []

        # ----------------------------------------------------------------------
        # 1. EVALUATE MODULE 2: EVIDENCE VERIFICATION (Weight 40%)
        # ----------------------------------------------------------------------
        ev_data = module_breakdowns.get("evidence", {})
        ev_status = ev_data.get("status", "NO_FACT_CHECK_FOUND")
        ev_score = ev_data.get("score", 50.0)
        ev_checks = ev_data.get("fact_checks", [])
        ev_flags = ev_data.get("flags", [])

        if ev_status == "SUPPORTED":
            top_pub = ev_checks[0].get("publisher", "fact-checking registry") if ev_checks else "fact-checking registry"
            top_rating = ev_checks[0].get("raw_rating") or ev_checks[0].get("textual_rating") or "Verified"
            pos_msg = f"Evidence strongly supports the claim (verified by {top_pub}: '{top_rating}')."
            positive_factors.append({
                "factor": pos_msg,
                "module": "evidence_verification",
                "impact_weight": 0.40,
                "evidence_score": ev_score,
            })
            module_explanations["evidence_verification"] = pos_msg
        elif ev_status == "CONTRADICTED":
            top_pub = ev_checks[0].get("publisher", "fact-checking registry") if ev_checks else "fact-checking registry"
            top_rating = ev_checks[0].get("raw_rating") or ev_checks[0].get("textual_rating") or "False"
            neg_msg = f"Evidence strongly contradicts the claim (debunked by {top_pub}: '{top_rating}')."
            negative_factors.append({
                "factor": neg_msg,
                "module": "evidence_verification",
                "impact_weight": 0.40,
                "evidence_score": ev_score,
            })
            module_explanations["evidence_verification"] = neg_msg
        elif ev_status == "MIXED/MISLEADING":
            neg_msg = "Fact-check reviews indicate the claim is mixed, misleading, or missing context."
            negative_factors.append({
                "factor": neg_msg,
                "module": "evidence_verification",
                "impact_weight": 0.30,
                "evidence_score": ev_score,
            })
            module_explanations["evidence_verification"] = neg_msg
        elif "GOOGLE_FACT_CHECK_API_KEY_NOT_CONFIGURED" in ev_flags:
            neutral_msg = "Google Fact Check API key is not configured; evidence module remained neutral (50/100)."
            module_explanations["evidence_verification"] = neutral_msg
            confidence_notes.append("Fact Check API key unconfigured; evidence module defaulted to neutral.")
        else:
            neutral_msg = "No existing fact-check was found on Google Fact Check Tools; evidence module remained neutral (50/100)."
            module_explanations["evidence_verification"] = neutral_msg
            confidence_notes.append("Absence of indexed fact-checks does not verify or disprove the post.")

        # ----------------------------------------------------------------------
        # 2. EVALUATE MODULE 4: SIMILAR CONTENT & TEMPORAL (Weight 25%)
        # ----------------------------------------------------------------------
        sim_data = module_breakdowns.get("similarity", {})
        sim_score = sim_data.get("score", 75.0)
        sim_recycled = sim_data.get("recycled_content", False)
        sim_flags = sim_data.get("flags", [])
        corpus_count = sim_data.get("corpus_size", 3)
        earliest_ts = sim_data.get("earliest_matching_timestamp")

        if sim_recycled:
            ts_str = f" from {earliest_ts[:10]}" if earliest_ts else ""
            neg_msg = f"Similar content was found from an earlier timestamp{ts_str}, indicating recycled material in local corpus."
            if "MATCHES_KNOWN_DEBUNKED_VIRAL_NARRATIVE" in sim_flags:
                neg_msg = f"Content matched a known debunked historical viral narrative in local corpus{ts_str}."
            negative_factors.append({
                "factor": neg_msg,
                "module": "similar_content",
                "impact_weight": 0.25,
                "similarity_score": sim_score,
            })
            module_explanations["similar_content"] = f"Similar content was found from an earlier timestamp{ts_str}, indicating recycled material."
        elif sim_score >= 80.0:
            pos_msg = f"No matching item found in current {corpus_count}-item local historical corpus (no recycled hoax detected)."
            positive_factors.append({
                "factor": pos_msg,
                "module": "similar_content",
                "impact_weight": 0.20,
                "similarity_score": sim_score,
            })
            module_explanations["similar_content"] = pos_msg
        else:
            module_explanations["similar_content"] = (
                f"Moderate similarity ({sim_data.get('text_similarity', 0.0):.2f}) detected against {corpus_count}-item local historical corpus."
            )

        # ----------------------------------------------------------------------
        # 3. EVALUATE MODULE 1: COMMENT ANALYSIS (Weight 20%)
        # ----------------------------------------------------------------------
        comm_data = module_breakdowns.get("comments", {})
        comm_score = comm_data.get("score", 50.0)
        comm_metrics = comm_data.get("metrics", {})
        comm_flags = comm_data.get("flags", [])
        n_comm = comm_metrics.get("comment_count", 0)

        comm_reasons = []
        if "HIGH_DUPLICATE_COMMENT_RATIO" in comm_flags or (n_comm >= 3 and comm_metrics.get("duplicate_ratio", 0) >= 0.35):
            neg_msg = f"Multiple repeated/near-duplicate comments were detected ({comm_metrics.get('duplicate_ratio', 0)*100:.0f}% duplicate ratio), indicating potential coordinated copypasta."
            negative_factors.append({
                "factor": neg_msg,
                "module": "comment_analysis",
                "impact_weight": 0.20,
                "duplicate_ratio": comm_metrics.get("duplicate_ratio", 0),
            })
            comm_reasons.append(neg_msg)

        if "TEMPORAL_BURST_ACTIVITY_DETECTED" in comm_flags and n_comm >= 5:
            neg_msg = "Comment activity exhibits an abnormal arrival burst (potential brigading spike)."
            negative_factors.append({
                "factor": neg_msg,
                "module": "comment_analysis",
                "impact_weight": 0.15,
            })
            comm_reasons.append(neg_msg)

        if "EXCESSIVE_EMOJI_SPAM" in comm_flags and n_comm >= 3:
            neg_msg = "Repetitive emoji flooding detected in discussion thread."
            negative_factors.append({
                "factor": neg_msg,
                "module": "comment_analysis",
                "impact_weight": 0.10,
            })
            comm_reasons.append(neg_msg)

        if n_comm == 0 or "NO_COMMENTS_AVAILABLE" in comm_flags:
            module_explanations["comment_analysis"] = "No comments were extracted from the post; comment analysis module remained neutral (50/100)."
        elif n_comm <= 2 and not comm_reasons:
            module_explanations["comment_analysis"] = f"{n_comm} comment(s) extracted; sample size too small for statistical coordination analysis."
        elif comm_score >= 80.0 and not comm_reasons:
            pos_msg = f"Discussion thread ({n_comm} comments) displays organic, healthy, diverse user responses."
            positive_factors.append({
                "factor": pos_msg,
                "module": "comment_analysis",
                "impact_weight": 0.15,
                "comment_score": comm_score,
            })
            module_explanations["comment_analysis"] = pos_msg
        elif comm_reasons:
            module_explanations["comment_analysis"] = " ".join(comm_reasons)
        else:
            module_explanations["comment_analysis"] = f"Comment thread ({n_comm} comments) shows standard baseline activity with no major anomalies."

        # ----------------------------------------------------------------------
        # 4. EVALUATE MODULE 3: USER BEHAVIOUR (Weight 15%)
        # ----------------------------------------------------------------------
        user_data = module_breakdowns.get("user_behaviour", {})
        user_score = user_data.get("score", 50.0)
        user_flags = user_data.get("flags", [])
        user_anom = user_data.get("anomaly_score", 0.0)
        user_metrics = user_data.get("metrics", {})
        has_age = user_metrics.get("account_age_days") is not None

        user_reasons = []
        if "USER_METADATA_UNAVAILABLE" in user_flags or (not user_flags and not user_metrics and user_score == 50.0):
            module_explanations["user_behaviour"] = "User profile metadata was unavailable from the page; user behaviour module remained neutral (50/100)."
        else:
            if "ANOMALOUS_BEHAVIOURAL_PATTERN" in user_flags or user_anom >= 0.60:
                neg_msg = "Author activity contains anomalous behavioural patterns (e.g. unusual posting velocity or timeline repetition)."
                negative_factors.append({
                    "factor": neg_msg,
                    "module": "user_behaviour",
                    "impact_weight": 0.15,
                    "anomaly_score": user_anom,
                })
                user_reasons.append(neg_msg)

            if "NEW_ACCOUNT_HIGH_POSTING_VELOCITY" in user_flags:
                neg_msg = f"Brand new account ({user_metrics.get('account_age_days', 0):.0f} days) exhibiting aggressive posting velocity."
                negative_factors.append({
                    "factor": neg_msg,
                    "module": "user_behaviour",
                    "impact_weight": 0.15,
                })
                user_reasons.append(neg_msg)

            if user_score >= 80.0 and not user_reasons and has_age:
                pos_msg = f"Author account demonstrates mature longevity ({user_metrics.get('account_age_days', 0):.0f} days) and balanced activity."
                positive_factors.append({
                    "factor": pos_msg,
                    "module": "user_behaviour",
                    "impact_weight": 0.15,
                    "behaviour_score": user_score,
                })
                module_explanations["user_behaviour"] = pos_msg
            elif user_reasons:
                module_explanations["user_behaviour"] = " ".join(user_reasons)
            else:
                module_explanations["user_behaviour"] = "Author behaviour metrics show standard baseline activity."

        # ----------------------------------------------------------------------
        # 5. SORT & RANK CONTRIBUTING FACTORS
        # ----------------------------------------------------------------------
        positive_factors.sort(key=lambda x: x.get("impact_weight", 0.0), reverse=True)
        negative_factors.sort(key=lambda x: x.get("impact_weight", 0.0), reverse=True)

        # ----------------------------------------------------------------------
        # 6. ASSEMBLE COHESIVE EXECUTIVE SUMMARY
        # ----------------------------------------------------------------------
        summary_sentences: list[str] = [
            f"Social Guard evaluates this content as {classification} (Credibility Score: {final_score:.1f}/100)."
        ]

        if negative_factors:
            top_neg = negative_factors[0]["factor"]
            summary_sentences.append(f"Key risk: {top_neg}")
        elif positive_factors:
            top_pos = positive_factors[0]["factor"]
            summary_sentences.append(f"Key strength: {top_pos}")

        if ev_status == "NO_FACT_CHECK_FOUND":
            summary_sentences.append("No matching indexed fact-check was found on Google Fact Check Tools; evidence module remained neutral.")

        # ----------------------------------------------------------------------
        # 7. DECOUPLED AI-GENERATION PROBABILITY NOTE
        # ----------------------------------------------------------------------
        if ai_generated_probability is not None:
            ai_pct = ai_generated_probability if ai_generated_probability > 1.0 else ai_generated_probability * 100.0
            if ai_pct >= 70.0:
                ai_note = f"Statistical AI-generation indicator suggests high probability ({ai_pct:.1f}%) of synthetic/AI generation. Note: Stylistic indicators are orthogonal to factual credibility and do not prove content is false."
            elif ai_pct <= 30.0:
                ai_note = f"Text displays human-written stylistic distribution (Statistical AI indicator: {ai_pct:.1f}%)."
            else:
                ai_note = f"Text stylistic markers are mixed (Statistical AI indicator: {ai_pct:.1f}%)."
            confidence_notes.append(ai_note)

        return {
            "summary": " ".join(summary_sentences),
            "positive_factors": positive_factors,
            "negative_factors": negative_factors,
            "module_explanations": module_explanations,
            "confidence_notes": confidence_notes,
        }


explainability_engine = ExplainabilityEngine()
