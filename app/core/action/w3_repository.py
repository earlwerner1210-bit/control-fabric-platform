"""Wave 3 action repositories — proposal and release persistence abstractions."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.core.action.domain_types import (
    W3ActionId,
    W3ActionProposal,
    W3ActionRelease,
    W3ActionStatus,
)


class W3ActionProposalRepository(ABC):
    @abstractmethod
    def store_proposal(self, proposal: W3ActionProposal) -> None: ...

    @abstractmethod
    def get_proposal(self, action_id: W3ActionId) -> W3ActionProposal | None: ...

    @abstractmethod
    def list_proposals(
        self, tenant_id: uuid.UUID, status: W3ActionStatus | None = None
    ) -> list[W3ActionProposal]: ...


class W3ActionReleaseRepository(ABC):
    @abstractmethod
    def store_release(self, release: W3ActionRelease) -> None: ...

    @abstractmethod
    def get_release(self, action_id: W3ActionId) -> W3ActionRelease | None: ...

    @abstractmethod
    def list_releases(self, tenant_id: uuid.UUID) -> list[W3ActionRelease]: ...


class InMemoryW3ActionProposalRepository(W3ActionProposalRepository):
    def __init__(self) -> None:
        self._proposals: dict[W3ActionId, W3ActionProposal] = {}

    def store_proposal(self, proposal: W3ActionProposal) -> None:
        self._proposals[proposal.id] = proposal

    def get_proposal(self, action_id: W3ActionId) -> W3ActionProposal | None:
        return self._proposals.get(action_id)

    def list_proposals(
        self, tenant_id: uuid.UUID, status: W3ActionStatus | None = None
    ) -> list[W3ActionProposal]:
        results = [p for p in self._proposals.values() if p.tenant_id == tenant_id]
        if status:
            results = [p for p in results if p.status == status]
        return results

    @property
    def count(self) -> int:
        return len(self._proposals)


class InMemoryW3ActionReleaseRepository(W3ActionReleaseRepository):
    def __init__(self) -> None:
        self._releases: dict[W3ActionId, W3ActionRelease] = {}

    def store_release(self, release: W3ActionRelease) -> None:
        self._releases[release.action_id] = release

    def get_release(self, action_id: W3ActionId) -> W3ActionRelease | None:
        return self._releases.get(action_id)

    def list_releases(self, tenant_id: uuid.UUID) -> list[W3ActionRelease]:
        return [r for r in self._releases.values() if r.tenant_id == tenant_id]

    @property
    def count(self) -> int:
        return len(self._releases)
