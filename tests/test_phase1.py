import pytest
from pydantic import ValidationError

from dockship.models import AppCreate, norm_repo


def test_app_input_is_normalized_and_validated():
    app = AppCreate(
        name="hello-app",
        repo_url="https://github.com/Owner/Repo.git",
        branch="main",
    )
    assert app.repo_url == "https://github.com/owner/repo"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "platform", "repo_url": "https://github.com/a/b"},
        {"name": "bad_name!", "repo_url": "https://github.com/a/b"},
        {"name": "hello", "repo_url": "http://github.com/a/b"},
        {"name": "hello", "repo_url": "https://gitlab.com/a/b"},
        {"name": "hello", "repo_url": "https://github.com/a/b", "branch": "-main"},
    ],
)
def test_app_input_rejects_unsafe_values(payload):
    with pytest.raises(ValidationError):
        AppCreate(**payload)


def test_norm_repo_removes_git_suffix_and_trailing_slash():
    assert norm_repo("https://github.com/Owner/Repo.git/") == "https://github.com/owner/repo"
