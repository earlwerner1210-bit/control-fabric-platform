"""Reconciliation module - cross-domain linking, evidence assembly, conflict detection, and margin diagnosis."""

from .linkers import ContractWorkOrderLinker, CrossPlaneLink, WorkOrderIncidentLinker
from .evidence import EvidenceAssembler, EvidenceBundle, EvidenceChainValidator
from .conflict_detector import ConflictDetector, CrossPlaneConflict, LeakageTrigger
from .margin_reconciler import MarginDiagnosisBundle, MarginDiagnosisReconciler

__all__ = [
    "ContractWorkOrderLinker",
    "ConflictDetector",
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
