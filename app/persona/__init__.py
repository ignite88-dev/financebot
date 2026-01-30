# path: app/persona/__init__.py
"""
Persona module - Manages bot personas and speaking styles.
"""

from app.persona.loader import PersonaLoader
from app.persona.style import StyleFormatter
from app.persona.prompts import PromptBuilder

__all__ = [
    "PersonaLoader",
    "StyleFormatter",
    "PromptBuilder"
]
