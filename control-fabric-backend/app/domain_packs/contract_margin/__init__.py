"""
Contract Margin Domain Pack.

Provides contract parsing, billability assessment, leakage detection,
penalty analysis, scope conflict detection, recovery recommendations,
prompt templates, report rendering, and evaluation cases for telecom
field-service contract margin assurance.
"""

from app.domain_packs.contract_margin.parsers import ContractParser
from app.domain_packs.contract_margin.rules import (
    BillabilityRuleEngine,
    LeakageRuleEngine,
    PenaltyExposureAnalyzer,
    PenaltyExposureSummary,
    RecoveryRecommendationEngine,
    ScopeConflictDetector,
)
from app.domain_packs.contract_margin.templates import MarginReportTemplate

__all__ = [
    "BillabilityRuleEngine",
    "ContractParser",
    "LeakageRuleEngine",
    "MarginReportTemplate",
    "PenaltyExposureAnalyzer",
    "PenaltyExposureSummary",
    "RecoveryRecommendationEngine",
    "ScopeConflictDetector",
]
