from rich.console import Console
from rich.theme import Theme

ARIA_THEME = Theme({
    "aria.primary":   "bold #7C3AED",
    "aria.cyan":      "#06B6D4",
    "aria.success":   "#22C55E",
    "aria.warning":   "#EAB308",
    "aria.error":     "#EF4444",
    "aria.dim":       "#6B7280",
    "aria.tool":      "bold #06B6D4",
    "aria.plan":      "bold #7C3AED",
    "aria.step":      "#EAB308",
})

console = Console(theme=ARIA_THEME)
