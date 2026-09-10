"""Module 2: Evidence-Based Verification Engine package."""

from app.modules.evidence_verification.analyzer import (
    EvidenceVerifier,
    evidence_verifier,
)
from app.modules.evidence_verification.claim_extractor import (
    BaseClaimExtractor,
    SimpleClaimExtractor,
    claim_extractor,
)
from app.modules.evidence_verification.factcheck_client import (
    GoogleFactCheckClient,
    fact_check_client,
)
from app.modules.evidence_verification.normalization import (
    compute_source_credibility,
    normalize_fact_check_rating,
)
from app.modules.evidence_verification.ocr import (
    BaseOCRService,
    TesseractOCRService,
    ocr_service,
)

__all__ = [
    "BaseClaimExtractor",
    "BaseOCRService",
    "EvidenceVerifier",
    "GoogleFactCheckClient",
    "SimpleClaimExtractor",
    "TesseractOCRService",
    "claim_extractor",
    "compute_source_credibility",
    "evidence_verifier",
    "fact_check_client",
    "normalize_fact_check_rating",
    "ocr_service",
]
