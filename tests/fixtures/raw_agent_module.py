"""Stub OpenAI Agent definitions for adapter testing."""

class StubAgent:
    def __init__(self, label: str = "stub") -> None:
        self.label = label
        self.instructions = f"{label} instructions"


agent = StubAgent()


def build_agent(**_: object) -> StubAgent:
    """Factory-style export returning an Agent-like object."""

    return StubAgent(label="factory")
