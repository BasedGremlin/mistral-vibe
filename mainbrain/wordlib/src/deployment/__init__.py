"""WORDLIB deployment package -- state machine, stage engine, repair, logging."""

from .errors import (DeploymentError, RecoverableError, FatalError,
                     UserActionRequired)
from .state import DeploymentState
from .stages import Stage, StageEngine, StageResult
from .repair import Repairer
from .logging_setup import get_deployment_logger

__all__ = [
    "DeploymentError", "RecoverableError", "FatalError", "UserActionRequired",
    "DeploymentState", "Stage", "StageEngine", "StageResult",
    "Repairer", "get_deployment_logger",
]

from .scaling import DeploymentMode, ScalingProfile, detect_mode, get_profile
__all__ += ["DeploymentMode", "ScalingProfile", "detect_mode", "get_profile"]
