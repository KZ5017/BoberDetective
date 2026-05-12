from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.analysis import AnalysisRunModel
from app.services.analysis_runs import AnalysisRunValidationError, finish_analysis_run


class _FakeDb:
    def add(self, item):
        self.item = item

    def flush(self):
        pass

    def commit(self):
        pass

    def refresh(self, item):
        pass


def test_finish_analysis_run_rejects_non_terminal_status() -> None:
    run = AnalysisRunModel(
        id=uuid4(),
        case_id=uuid4(),
        run_type="llm_smoke",
        status="running",
        started_by_user_id=uuid4(),
        started_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )

    with pytest.raises(AnalysisRunValidationError):
        finish_analysis_run(_FakeDb(), run, status="running")
