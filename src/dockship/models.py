import re

from pydantic import BaseModel, Field, field_validator

NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}[a-z0-9]$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,100}$")
REPO_RE = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+$")
RESERVED = {"platform"}


def norm_repo(url: str) -> str:
    return url.rstrip("/").removesuffix(".git").rstrip("/").lower()


class AppCreate(BaseModel):
    name: str
    repo_url: str
    branch: str = "main"
    health_path: str = Field(default="/health", pattern=r"^/[A-Za-z0-9._/-]*$")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not NAME_RE.fullmatch(value) or value in RESERVED:
            raise ValueError("invalid or reserved app name")
        return value

    @field_validator("repo_url")
    @classmethod
    def validate_repo(cls, value: str) -> str:
        if not REPO_RE.fullmatch(value):
            raise ValueError("repo_url must be an HTTPS GitHub repository URL")
        return norm_repo(value)

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, value: str) -> str:
        if not BRANCH_RE.fullmatch(value) or value.startswith("-"):
            raise ValueError("invalid branch")
        return value
