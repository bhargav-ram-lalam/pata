"""
Pata Agent Package
==================
Five single-responsibility agents that form the address resolution pipeline.

Agent 1 — DeterministicParserAgent  (always runs, ~5ms)
Agent 2 — LandmarkNERAgent          (selective ML, ~200-800ms)
Agent 3 — LandmarkResolutionAgent   (selective OSM, ~300-2000ms)
Agent 4 — ConfidenceArbitrationAgent (rules + optional LLM)
Agent 5 — SelfCheckAgent            (validation pass)
"""
from agents.agent1_parser import DeterministicParserAgent
from agents.agent2_ner import LandmarkNERAgent
from agents.agent3_landmark import LandmarkResolutionAgent
from agents.agent4_arbitration import ConfidenceArbitrationAgent
from agents.agent5_selfcheck import SelfCheckAgent

__all__ = [
    "DeterministicParserAgent",
    "LandmarkNERAgent",
    "LandmarkResolutionAgent",
    "ConfidenceArbitrationAgent",
    "SelfCheckAgent",
]
