"""WORDLIB multi-agent package. ClawOrchestrator + 9 specialized agents."""

from .base import Agent, AgentContext, AgentResult, Task
from .orchestrator import ClawOrchestrator, get_orchestrator
from .specialized import (ArchitectAgent, CodeAgent, TestAgent, DeployAgent,
                          GuardianAgent, ResearcherAgent, ReasoningAgent,
                          MathAgent, AbsorptionAgent, MarketAgent)
from .gremlin_agent import GremlinAgent
from .evolution_architect import EvolutionArchitect
from .dispatch_agent import DispatchAgent

__all__ = [
    "Agent", "AgentContext", "AgentResult", "Task",
    "ClawOrchestrator", "get_orchestrator",
    "ArchitectAgent", "CodeAgent", "TestAgent", "DeployAgent",
    "GuardianAgent", "ResearcherAgent", "ReasoningAgent",
    "MathAgent", "AbsorptionAgent", "MarketAgent", "GremlinAgent",
    "EvolutionArchitect", "DispatchAgent",
]
