"""Reconciliation module - cross-domain linking, evidence assembly, conflict detection, and margin diagnosis."""

from .conflict_detector import ConflictDetector, CrossPlaneConflict, LeakageTrigger
from .evidence import EvidenceAssembler, EvidenceBundle, EvidenceChainValidator
from .linkers import ContractWorkOrderLinker, CrossPlaneLink, WorkOrderIncidentLinker
from .margin_reconciler import MarginDiagnosisBundle, MarginDiagnosisReconciler

__all__ = [
    "ConflictDetector",
    "ContractWorkOrderLinker",
    "CrossPlaneConflict",
    "CrossPlaneLink",
    "EvidenceAssembler",
    "EvidenceBundle",
    "EvidenceChainValidator",
    "LeakageTrigger",
    "MarginDiagnosisBundle",
    "MarginDiagnosisReconciler",
    "WorkOrderIncidentLinker",
]
