"""The fake sibling environment, created once per session, and each test's own caches."""

from pathlib import Path

import pytest

from tests.corpus.siblings._fake_sibling import Caches, create_environment, make_caches


@pytest.fixture(scope="session")
def sibling_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return create_environment(tmp_path_factory.mktemp("sibling-env"))


@pytest.fixture
def caches(tmp_path: Path) -> Caches:
    return make_caches(tmp_path / "caches")
