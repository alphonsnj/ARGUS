from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.documents import router
from app.db.session import get_db_session
from app.models import User
from app.repositories.documents import DocumentRepository


def test_list_query_is_bounded_ordered_and_owner_scoped() -> None:
    session = MagicMock(spec=Session)
    session.scalars.return_value = []
    owner = uuid4()
    DocumentRepository(session).list_for_owner(owner, "evidence", limit=21, offset=20)
    statement = session.scalars.call_args.args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "documents.owner_id =" in sql
    assert "websearch_to_tsquery" in sql
    assert "ORDER BY documents.created_at DESC, documents.id DESC" in sql
    assert "LIMIT" in sql and "OFFSET" in sql
    assert owner in compiled.params.values()
    assert 21 in compiled.params.values() and 20 in compiled.params.values()


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": 101}, {"offset": -1}, {"offset": 10001},
])
def test_api_rejects_unbounded_paging(params: dict[str, int]) -> None:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: User(id=uuid4())
    session = MagicMock(spec=Session)
    app.dependency_overrides[get_db_session] = lambda: session
    assert TestClient(app).get("/documents", params=params).status_code == 422
    session.scalars.assert_not_called()


def test_api_passes_paging_to_repository() -> None:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: User(id=uuid4())
    session = MagicMock(spec=Session)
    session.scalars.return_value = []
    app.dependency_overrides[get_db_session] = lambda: session
    response = TestClient(app).get("/documents", params={"limit": 10, "offset": 30})
    assert response.status_code == 200 and response.json() == []
    params = session.scalars.call_args.args[0].compile().params
    assert 10 in params.values() and 30 in params.values()
