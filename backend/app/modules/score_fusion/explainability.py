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
    """

    def generate_explanation(
        self,
        final_score: float,
        classification: str,
        module_breakdowns: dict[str, dict[str, Any]],
        ai_generated_probability: float | None = None,
    ) -> dict[str, Any]:
        """Generate structured explainability response.

        Args:
            final_score: Consolidated credibility score [0.0 - 100.0]
            classification: Verdict category (e.g. 'LIKELY REAL', 'PROBABLY FAKE')
            module_breakdowns: Dict containing raw outputs of all modules:
                - 'comments': {score, metrics, flags}
                - 'evidence': {score, status, claims, fact_checks, flags, explanation}
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
            top_pub = ev_checks[0]["publisher"] if ev_checks else "fact-checking registry"
            pos_msg = f"Evidence strongly supports the claim (verified by {top_pub})."
            positive_factors.append({
                "factor": pos_msg,
                "module": "evidence_verification",
                "impact_weight": 0.40,
                "evidence_score": ev_score,
            })
            module_explanations["evidence_verification"] = pos_msg
        elif ev_status == "CONTRADICTED":
            top_pub = ev_checks[0]["publisher"] if ev_checks else "fact-checking registry"
            neg_msg = f"Evidence strongly contradicts the claim (debunked by {top_pub})."
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
        else:
            neutral_msg = "No existing fact-check was found for the extracted claims; factual veracity remains uncertain."
            module_explanations["evidence_verification"] = neutral_msg
            confidence_notes.append("Absence of indexed fact-checks does not verify or disprove the post.")

        # ----------------------------------------------------------------------
        # 2. EVALUATE MODULE 4: SIMILAR CONTENT & TEMPORAL (Weight 25%)
        # ----------------------------------------------------------------------
        sim_data = module_breakdowns.get("similarity", {})
        sim_score = sim_data.get("score", 75.0)
        sim_recycled = sim_data.get("recycled_content", False)
        sim_flags = sim_data.get("flags", [])
        earliest_ts = sim_data.get("earliest_matching_timestamp")

        if sim_recycled:
            ts_str = f" from {earliest_ts[:10]}" if earliest_ts else ""
            neg_msg = f"Similar content was found from an earlier timestamp{ts_str}, indicating recycled material."
            if "MATCHES_KNOWN_DEBUNKED_VIRAL_NARRATIVE" in sim_flags:
                neg_msg = f"Similar content was found from an earlier timestamp{ts_str}, matching a known debunked historical viral narrative."
            negative_factors.append({
                "factor": neg_msg,
                "module": "similar_content",
                "impact_weight": 0.25,
                "similarity_score": sim_score,
            })
            module_explanations["similar_content"] = neg_msg
        elif sim_score >= 80.0:
            pos_msg = "Post displays high original context with no match against recycled hoax databases."
            positive_factors.append({
                "factor": pos_msg,
                "module": "similar_content",
                "impact_weight": 0.20,
                "similarity_score": sim_score,
            })
            module_explanations["similar_content"] = pos_msg
        else:
            module_explanations["similar_content"] = (
                f"Moderate similarity ({sim_data.get('text_similarity', 0.0):.2f}) detected against related corpus."
            )

        # ----------------------------------------------------------------------
        # 3. EVALUATE MODULE 1: COMMENT ANALYSIS (Weight 20%)
        # ----------------------------------------------------------------------
        comm_data = module_breakdowns.get("comments", {})
        comm_score = comm_data.get("score", 50.0)
        comm_metrics = comm_data.get("metrics", {})
        comm_flags = comm_data.get("flags", [])

        comm_reasons = []
        if "HIGH_DUPLICATE_COMMENT_RATIO" in comm_flags or comm_metrics.get("duplicate_ratio", 0) >= 0.30:
            neg_msg = "Multiple repeated/near-duplicate comments were detected (potential copypasta/bot campaign)."
            negative_factors.append({
                "factor": neg_msg,
                "module": "comment_analysis",
                "impact_weight": 0.20,
                "duplicate_ratio": comm_metrics.get("duplicate_ratio", 0),
            })
            comm_reasons.append(neg_msg)

        if "TEMPORAL_BURST_ACTIVITY_DETECTED" in comm_flags:
            neg_msg = "Comment activity shows an abnormal arrival burst (potential brigading spike)."
            negative_factors.append({
                "factor": neg_msg,
                "module": "comment_analysis",
                "impact_weight": 0.15,
            })
            comm_reasons.append(neg_msg)

        if "EXCESSIVE_EMOJI_SPAM" in comm_flags:
            neg_msg = "Disproportionate repetitive emoji flooding detected in comments."
            negative_factors.append({
                "factor": neg_msg,
                "module": "comment_analysis",
                "impact_weight": 0.10,
            })
            comm_reasons.append(neg_msg)

        if comm_score >= 80.0 and not comm_reasons:
            pos_msg = "Discussion thread displays organic, healthy, diverse user responses."
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
            module_explanations["comment_analysis"] = "Comment discussion is moderate with no major anomaly detected."

        # ----------------------------------------------------------------------
        # 4. EVALUATE MODULE 3: USER BEHAVIOUR (Weight 15%)
        # ----------------------------------------------------------------------
        user_data = module_breakdowns.get("user_behaviour", {})
        user_score = user_data.get("score", 50.0)
        user_flags = user_data.get("flags", [])
        user_anom = user_data.get("anomaly_score", 0.0)

        user_reasons = []
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
            neg_msg = "Brand new account exhibiting aggressive posting velocity."
            negative_factors.append({
                "factor": neg_msg,
                "module": "user_behaviour",
                "impact_weight": 0.15,
            })
            user_reasons.append(neg_msg)

        if user_score >= 80.0 and not user_reasons:
            pos_msg = "Author account demonstrates mature longevity, balanced follower ratio, and normal activity."
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
            summary_sentences.append("No authoritative fact-check was found; verification relies on social and temporal provenance.")

        # ----------------------------------------------------------------------
        # 7. DECOUPLED AI-GENERATION PROBABILITY NOTE
        # ----------------------------------------------------------------------
        if ai_generated_probability is not None:
            # Handle both 0.0 - 1.0 fraction or 0.0 - 100.0 percentage
            ai_pct = ai_generated_probability if ai_generated_probability > 1.0 else ai_generated_probability * 100.0
            if ai_pct >= 70.0:
                ai_note = f"Text demonstrates high probability ({ai_pct:.1f}%) of synthetic/AI generation. Note: AI-generated text is not inherently false."
            elif ai_pct <= 30.0:
                ai_note = f"Text displays human-written stylistic distribution (AI probability: {ai_pct:.1f}%)."
            else:
                ai_note = f"Text stylistic markers are mixed (AI probability: {ai_pct:.1f}%)."
            confidence_notes.append(ai_note)

        return {
            "summary": " ".join(summary_sentences),
            "positive_factors": positive_factors,
            "negative_factors": negative_factors,
            "module_explanations": module_explanations,
            "confidence_notes": confidence_notes,
        }


explainability_engine = ExplainabilityEngine()
