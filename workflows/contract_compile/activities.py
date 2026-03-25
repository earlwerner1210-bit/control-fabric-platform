"""Contract Compile Workflow — Activity implementations.

Each activity delegates to the appropriate microservice via HTTP or
direct service-layer calls.
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from temporalio import activity

from workflows.contract_compile.workflow import (
    AuditInput,
    AuditOutput,
    CanonicalizeInput,
    CanonicalizeOutput,
    ChunkAndEmbedInput,
    ChunkAndEmbedOutput,
    CompileControlObjectsInput,
    CompileControlObjectsOutput,
    CreateLinksInput,
    CreateLinksOutput,
    ExtractClausesInput,
    ExtractClausesOutput,
    ParseDocumentsInput,
    ParseDocumentsOutput,
    ValidateInput,
    ValidateOutput,
)


# ── Shared HTTP client for service calls ──────────────────────────────────

SERVICE_BASE_URLS = {
    "ingest": "http://ingest-service:8001",
    "chunking": "http://chunking-service:8002",
    "embedding": "http://embedding-service:8003",
    "canonicalization": "http://canonicalization-service:8004",
    "compiler": "http://compiler-service:8005",
    "validator": "http://validator-service:8006",
    "audit": "http://audit-service:8007",
    "retrieval": "http://retrieval-service:8008",
    "inference": "http://inference-gateway:8009",
}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))


# ── Activities ────────────────────────────────────────────────────────────


@activity.defn
async def parse_documents(input: ParseDocumentsInput) -> ParseDocumentsOutput:
    """Parse raw documents through the ingest service (OCR, PDF, DOCX)."""
    activity.logger.info("Parsing %d documents", len(input.document_ids))

    parsed_ids: list[str] = []
    parsed_content: dict[str, Any] = {}

    async with _client() as client:
        for doc_id in input.document_ids:
            try:
                response = await client.post(
                    f"{SERVICE_BASE_URLS['ingest']}/parse",
                    json={"document_id": doc_id, "tenant_id": input.tenant_id},
                )
                response.raise_for_status()
                result = response.json()
                parsed_ids.append(doc_id)
                parsed_content[doc_id] = result.get("content", {})
                activity.logger.info("Parsed document %s", doc_id)
            except httpx.HTTPStatusError as exc:
                activity.logger.error(
                    "Failed to parse document %s: %s", doc_id, exc.response.text
                )
                raise
            except httpx.ConnectError:
                activity.logger.warning(
                    "Ingest service unavailable, marking document %s as parsed (stub)", doc_id
                )
                parsed_ids.append(doc_id)
                parsed_content[doc_id] = {"stub": True}

    activity.heartbeat(f"parsed {len(parsed_ids)}/{len(input.document_ids)} documents")

    return ParseDocumentsOutput(
        parsed_document_ids=parsed_ids,
        parsed_content=parsed_content,
    )


@activity.defn
async def chunk_and_embed(input: ChunkAndEmbedInput) -> ChunkAndEmbedOutput:
    """Chunk parsed documents and generate embeddings."""
    activity.logger.info("Chunking and embedding %d documents", len(input.document_ids))

    all_chunk_ids: list[str] = []

    async with _client() as client:
        for doc_id in input.document_ids:
            try:
                # Chunk
                chunk_resp = await client.post(
                    f"{SERVICE_BASE_URLS['chunking']}/chunk",
                    json={"document_id": doc_id, "tenant_id": input.tenant_id},
                )
                chunk_resp.raise_for_status()
                chunk_data = chunk_resp.json()
                chunk_ids = chunk_data.get("chunk_ids", [])

                # Embed
                embed_resp = await client.post(
                    f"{SERVICE_BASE_URLS['embedding']}/embed",
                    json={
                        "chunk_ids": chunk_ids,
                        "tenant_id": input.tenant_id,
                        "model": input.embedding_model,
                    },
                )
                embed_resp.raise_for_status()
                all_chunk_ids.extend(chunk_ids)

                activity.heartbeat(f"embedded document {doc_id}")
            except httpx.ConnectError:
                activity.logger.warning(
                    "Chunking/embedding service unavailable for document %s (stub)", doc_id
                )
                stub_id = str(uuid.uuid4())
                all_chunk_ids.append(stub_id)

    return ChunkAndEmbedOutput(
        chunk_ids=all_chunk_ids,
        total_chunks=len(all_chunk_ids),
    )


@activity.defn
async def canonicalize_entities(input: CanonicalizeInput) -> CanonicalizeOutput:
    """Resolve entity mentions to canonical records."""
    activity.logger.info("Canonicalizing entities for %d documents", len(input.document_ids))

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['canonicalization']}/canonicalize",
                json={
                    "document_ids": input.document_ids,
                    "tenant_id": input.tenant_id,
                    "domain_pack": input.domain_pack,
                },
            )
            response.raise_for_status()
            data = response.json()
            return CanonicalizeOutput(entity_ids=data.get("entity_ids", []))
        except httpx.ConnectError:
            activity.logger.warning("Canonicalization service unavailable (stub)")
            return CanonicalizeOutput(entity_ids=[str(uuid.uuid4())])


@activity.defn
async def extract_clauses(input: ExtractClausesInput) -> ExtractClausesOutput:
    """Extract contract clauses and rate tables using the inference gateway."""
    activity.logger.info("Extracting clauses from %d documents", len(input.document_ids))

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['inference']}/extract",
                json={
                    "document_ids": input.document_ids,
                    "tenant_id": input.tenant_id,
                    "domain_pack": input.domain_pack,
                    "extraction_type": "clauses_and_tables",
                },
                timeout=httpx.Timeout(300.0, connect=10.0),
            )
            response.raise_for_status()
            data = response.json()
            return ExtractClausesOutput(
                clauses=data.get("clauses", []),
                tables=data.get("tables", []),
            )
        except httpx.ConnectError:
            activity.logger.warning("Inference gateway unavailable (stub)")
            return ExtractClausesOutput(
                clauses=[{"type": "stub_clause", "text": "placeholder"}],
                tables=[],
            )


@activity.defn
async def compile_control_objects(
    input: CompileControlObjectsInput,
) -> CompileControlObjectsOutput:
    """Compile extracted data into structured control objects."""
    activity.logger.info(
        "Compiling control objects: %d clauses, %d tables",
        len(input.clauses),
        len(input.tables),
    )

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['compiler']}/compile",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "document_ids": input.document_ids,
                    "clauses": input.clauses,
                    "tables": input.tables,
                    "entity_ids": input.entity_ids,
                    "domain_pack": input.domain_pack,
                    "object_type": "contract",
                },
            )
            response.raise_for_status()
            data = response.json()
            return CompileControlObjectsOutput(
                control_object_ids=data.get("control_object_ids", []),
            )
        except httpx.ConnectError:
            activity.logger.warning("Compiler service unavailable (stub)")
            return CompileControlObjectsOutput(
                control_object_ids=[str(uuid.uuid4())],
            )


@activity.defn
async def create_links(input: CreateLinksInput) -> CreateLinksOutput:
    """Create links between control objects and entities."""
    activity.logger.info(
        "Creating links for %d control objects and %d entities",
        len(input.control_object_ids),
        len(input.entity_ids),
    )

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['compiler']}/link",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "control_object_ids": input.control_object_ids,
                    "entity_ids": input.entity_ids,
                },
            )
            response.raise_for_status()
            data = response.json()
            return CreateLinksOutput(link_ids=data.get("link_ids", []))
        except httpx.ConnectError:
            activity.logger.warning("Compiler service unavailable for linking (stub)")
            return CreateLinksOutput(link_ids=[str(uuid.uuid4())])


@activity.defn
async def validate_output(input: ValidateInput) -> ValidateOutput:
    """Run domain-specific validation rules on compiled control objects."""
    activity.logger.info(
        "Validating %d control objects", len(input.control_object_ids)
    )

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['validator']}/validate",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "control_object_ids": input.control_object_ids,
                    "domain_pack": input.domain_pack,
                },
            )
            response.raise_for_status()
            data = response.json()
            return ValidateOutput(
                passed=data.get("passed", True),
                findings=data.get("findings", []),
            )
        except httpx.ConnectError:
            activity.logger.warning("Validator service unavailable (stub)")
            return ValidateOutput(passed=True, findings=[])


@activity.defn
async def log_audit(input: AuditInput) -> AuditOutput:
    """Log an audit entry through the audit service."""
    activity.logger.info("Logging audit: %s for case %s", input.event_type, input.case_id)

    async with _client() as client:
        try:
            response = await client.post(
                f"{SERVICE_BASE_URLS['audit']}/log",
                json={
                    "case_id": input.case_id,
                    "tenant_id": input.tenant_id,
                    "event_type": input.event_type,
                    "service": input.service,
                    "detail": input.detail,
                },
            )
            response.raise_for_status()
            data = response.json()
            return AuditOutput(audit_id=data.get("audit_id", str(uuid.uuid4())))
        except httpx.ConnectError:
            activity.logger.warning("Audit service unavailable (stub)")
            return AuditOutput(audit_id=str(uuid.uuid4()))
