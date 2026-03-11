"""Compliance evaluation package for section-based grant review."""

from backend.app.compliance.service import build_default_service, ComplianceEvaluationService

__all__ = ["ComplianceEvaluationService", "build_default_service"]
