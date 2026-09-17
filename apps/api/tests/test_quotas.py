from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.repositories.documents import DocumentRepository


@pytest.mark.parametrize("count,used,incoming,allowed", [
    (0, 0, 10, True), (0, 0, 11, False), (1, 5, 5, True),
    (1, 5, 6, False), (2, 0, 1, False),
])
def test_quota_boundaries(count: int, used: int, incoming: int, allowed: bool) -> None:
    session = MagicMock(spec=Session)
    session.execute.return_value.one.return_value = (count, used)
    result = DocumentRepository(session).reserve_capacity(uuid4(), incoming, 10, 2)
    assert result is allowed
    assert "FOR UPDATE" in str(session.execute.call_args_list[0].args[0])


def test_settings_reject_invalid_quotas() -> None:
    from app.core.config import get_settings

    values = get_settings().model_dump()
    values["max_user_documents"] = 0
    with pytest.raises(ValueError):
        type(get_settings())(**values)
