"""
Agents module for FoundryIQ Multi-Agent Demo.

Specialist agents grounded on domain-specific Knowledge Sources:
- AI Research → ks-ai-research (transformer papers, BERT, GPT-4)
- Space Science → ks-space-science (NASA publications, earth observation)
- Standards → ks-standards (NIST cybersecurity & AI frameworks)
- Cloud & Sustainability → ks-cloud-sustainability (Azure whitepapers, sustainability)
"""

from .ai_research_agent import run_ai_research_agent, AI_RESEARCH_INSTRUCTIONS
from .space_science_agent import run_space_science_agent, SPACE_SCIENCE_INSTRUCTIONS
from .standards_agent import run_standards_agent, STANDARDS_INSTRUCTIONS
from .cloud_sustainability_agent import run_cloud_sustainability_agent, CLOUD_SUSTAINABILITY_INSTRUCTIONS
from .orchestrator import run_orchestrator, run_single_query

__all__ = [
    "run_ai_research_agent",
    "run_space_science_agent",
    "run_standards_agent",
    "run_cloud_sustainability_agent",
    "AI_RESEARCH_INSTRUCTIONS",
    "SPACE_SCIENCE_INSTRUCTIONS",
    "STANDARDS_INSTRUCTIONS",
    "CLOUD_SUSTAINABILITY_INSTRUCTIONS",
    "run_orchestrator",
    "run_single_query",
]
