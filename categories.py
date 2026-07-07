"""
Shared story-category metadata for the AI News Digest.

Kept in its own module (rather than digest.py) so email_template.py and
publisher.py can import it without creating a circular import with digest.py.
"""

DEFAULT_CATEGORY = "news"

CATEGORY_LABELS: dict = {
    "news":              "News",
    "research":          "Research & Methodology",
    "cost_optimization": "Cost & Efficiency",
    "systems_design":    "Systems Design",
    "gpu_hardware":      "GPU & Hardware",
}

CATEGORY_COLORS: dict = {
    "news":              "#3b82f6",
    "research":          "#8b5cf6",
    "cost_optimization": "#16a34a",
    "systems_design":    "#f59e0b",
    "gpu_hardware":      "#ef4444",
}


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, CATEGORY_LABELS[DEFAULT_CATEGORY])


def category_color(category: str) -> str:
    return CATEGORY_COLORS.get(category, CATEGORY_COLORS[DEFAULT_CATEGORY])
