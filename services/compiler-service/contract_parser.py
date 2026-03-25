"""Contract parser -- extracts structured data from contract JSON/documents."""

from __future__ import annotations

import re
from typing import Any


class ContractParser:
    """Parses contract documents into structured control objects."""

    def parse_contract(self, contract_data: dict[str, Any]) -> dict[str, Any]:
        """Parse a full contract document and return structured output."""
        result: dict[str, Any] = {
            "document_type": contract_data.get("document_type", "unknown"),
            "title": contract_data.get("title", ""),
            "effective_date": contract_data.get("effective_date"),
            "expiry_date": contract_data.get("expiry_date"),
            "parties": contract_data.get("parties", []),
            "clauses": self.extract_clauses(contract_data),
            "sla_table": self.extract_sla_table(contract_data),
            "rate_card": self.extract_rate_card(contract_data),
        }
        return result

    def extract_clauses(self, contract_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract and classify clauses from a contract."""
        raw_clauses = contract_data.get("clauses", [])
        parsed: list[dict[str, Any]] = []

        for clause in raw_clauses:
            parsed_clause: dict[str, Any] = {
                "id": clause.get("id", ""),
                "type": clause.get("type", "general"),
                "text": clause.get("text", ""),
                "section": clause.get("section", ""),
            }

            # Extract structured data based on clause type
            clause_type = clause.get("type", "")
            clause_text = clause.get("text", "")

            if clause_type == "penalty":
                parsed_clause["penalty_details"] = self._extract_penalty_details(clause_text)
            elif clause_type == "sla":
                parsed_clause["sla_details"] = self._extract_sla_from_text(clause_text)
            elif clause_type == "rate":
                parsed_clause["rate_details"] = self._extract_rates_from_text(clause_text)
            elif clause_type == "obligation":
                parsed_clause["obligation_details"] = self._extract_obligation_details(clause_text)

            parsed.append(parsed_clause)

        return parsed

    def extract_sla_table(self, contract_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract the SLA table from a contract."""
        sla_table = contract_data.get("sla_table", [])
        parsed: list[dict[str, Any]] = []

        for entry in sla_table:
            parsed.append({
                "priority": entry.get("priority", ""),
                "response_time_hours": entry.get("response_time_hours", 0),
                "resolution_time_hours": entry.get("resolution_time_hours", 0),
                "availability": entry.get("availability", "business_hours"),
            })

        return parsed

    def extract_rate_card(self, contract_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract rate card entries from a contract."""
        rate_card = contract_data.get("rate_card", [])
        parsed: list[dict[str, Any]] = []

        for entry in rate_card:
            parsed.append({
                "activity": entry.get("activity", ""),
                "unit": entry.get("unit", ""),
                "rate": float(entry.get("rate", 0)),
                "currency": entry.get("currency", "USD"),
            })

        return parsed

    @staticmethod
    def _extract_penalty_details(text: str) -> dict[str, Any]:
        """Extract penalty percentage and conditions from clause text."""
        details: dict[str, Any] = {"raw_text": text}
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if pct_match:
            details["penalty_percentage"] = float(pct_match.group(1))
        if "monthly invoice" in text.lower():
            details["basis"] = "monthly_invoice_value"
        elif "annual" in text.lower():
            details["basis"] = "annual_contract_value"
        return details

    @staticmethod
    def _extract_sla_from_text(text: str) -> list[dict[str, Any]]:
        """Extract SLA targets from free-text clause."""
        results: list[dict[str, Any]] = []
        pattern = r"(P\d)\s*(?:incidents?)?\s*:\s*(\d+)\s*hours?"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            results.append({
                "priority": match.group(1).upper(),
                "resolution_time_hours": int(match.group(2)),
            })
        return results

    @staticmethod
    def _extract_rates_from_text(text: str) -> list[dict[str, Any]]:
        """Extract rate information from free-text clause."""
        results: list[dict[str, Any]] = []
        pattern = r"(?:(\w[\w\s/]*?))\s*(?:rate)?\s*:\s*\$\s*([\d,]+(?:\.\d{2})?)\s*/?\s*hr"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            results.append({
                "category": match.group(1).strip().lower(),
                "rate": float(match.group(2).replace(",", "")),
                "unit": "hour",
            })
        return results

    @staticmethod
    def _extract_obligation_details(text: str) -> dict[str, Any]:
        """Extract obligation parameters from clause text."""
        details: dict[str, Any] = {"raw_text": text}
        time_match = re.search(r"(\d+)\s*(?:business\s+)?hours?", text, re.IGNORECASE)
        if time_match:
            details["time_limit_hours"] = int(time_match.group(1))
        if "certification" in text.lower() or "certified" in text.lower():
            details["requires_certification"] = True
        return details
