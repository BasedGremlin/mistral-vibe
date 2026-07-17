"""
Deployment error hierarchy.
Three categories drive how the installer responds:
  - Recoverable:     retry with backoff (transient network, service warmup)
  - UserActionRequired: stop, tell the user exactly what to do
  - Fatal:           stop, this cannot continue (corrupt files, no disk)
"""

from __future__ import annotations


class DeploymentError(Exception):
    """Base for all deployment errors. Carries a category + a concrete fix."""
    category = "fatal"

    def __init__(self, message: str, fix: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.fix = fix

    def as_dict(self) -> dict:
        return {"category": self.category, "message": self.message, "fix": self.fix}


class RecoverableError(DeploymentError):
    """Transient -- safe to retry (network blip, service still warming up)."""
    category = "recoverable"


class UserActionRequired(DeploymentError):
    """Cannot proceed without the user doing something (install Python, connect net)."""
    category = "user_action"


class FatalError(DeploymentError):
    """Unrecoverable -- corrupt structure, no disk space, write-protected USB."""
    category = "fatal"
