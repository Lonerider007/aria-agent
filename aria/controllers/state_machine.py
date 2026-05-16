"""Plan/Approval state machine.

Replaces prompt-based "never call write_file before create_plan APPROVED" rule
with deterministic code enforcement. Mutating tools blocked unless state == EXECUTING.
"""
from enum import Enum

MUTATING_TOOLS = {
    "write_file", "edit_file", "delete_file",
    "run_command", "run_tests", "git_commit",
    "git_create_branch", "new_project",
}

READ_ONLY_TOOLS = {
    "read_file", "list_files", "search_in_files",
    "git_status", "git_diff", "git_log",
    "load_project_context", "read_memory", "list_projects",
    "search_web", "save_memory", "save_checkpoint",
    "load_checkpoint", "clear_checkpoint", "get_checkpoint_data",
    "mark_milestone", "notify_user",
}

# Tools that drive state transitions themselves
CONTROL_TOOLS = {
    "create_plan", "ask_clarification", "request_approval",
}


class State(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    DONE = "done"
    REJECTED = "rejected"


APPROVAL_TOKENS = {
    "approve", "approved", "yes", "y", "haan", "han", "ha",
    "ok", "okay", "chalo", "go", "proceed", "do it", "kar",
    "sahi hai", "theek", "thik",
}

REJECTION_TOKENS = {
    "reject", "rejected", "no", "n", "nahi", "stop", "cancel",
    "abort", "ruk", "ruko", "mat",
}


class PlanFSM:
    """Track plan/approval state for a single task. Reset per user turn."""

    def __init__(self):
        self.state = State.IDLE
        self.pending_plan = None
        self.goal = ""               # captured from create_plan
        self.verified = False        # verify_goal returned ok
        self.acceptance_passed = False  # acceptance_test returned ok
        self.spec_fetched_domains = set()  # domains for which fetch_api_spec was called
        self.skip_verification = False    # set when task is non-functional (e.g., just reading)

    def reset(self):
        self.state = State.IDLE
        self.pending_plan = None
        self.goal = ""
        self.verified = False
        self.acceptance_passed = False
        self.spec_fetched_domains = set()
        self.skip_verification = False

    def begin_task(self):
        """Called when entering task mode for a new user input."""
        self.state = State.PLANNING

    def on_create_plan(self, plan: dict):
        """Tool call create_plan was made. Capture plan, await user approval."""
        self.pending_plan = plan
        self.goal = plan.get("goal", "") if isinstance(plan, dict) else ""
        self.state = State.AWAITING_APPROVAL

    def on_user_response(self, text: str) -> str | None:
        """Inspect user's response to a pending plan. Returns 'approved' / 'rejected' / None."""
        if self.state != State.AWAITING_APPROVAL:
            return None
        t = text.strip().lower()
        if t in APPROVAL_TOKENS or any(t.startswith(tok + " ") or t == tok for tok in APPROVAL_TOKENS):
            self.state = State.EXECUTING
            return "approved"
        if t in REJECTION_TOKENS or any(t.startswith(tok + " ") or t == tok for tok in REJECTION_TOKENS):
            self.state = State.REJECTED
            return "rejected"
        return None

    def can_call(self, tool_name: str) -> tuple[bool, str]:
        """Check if tool call is allowed in current state.

        Returns (allowed, reason_if_blocked).
        """
        if tool_name in READ_ONLY_TOOLS or tool_name in CONTROL_TOOLS:
            return True, ""

        if tool_name in MUTATING_TOOLS:
            if self.state == State.EXECUTING:
                return True, ""
            return False, (
                f"STATE_ERROR: tool '{tool_name}' requires approved plan. "
                f"Current state: {self.state.value}. "
                f"Call create_plan first and wait for user approval."
            )

        # Unknown tool — allow, let agent's TOOL_MAP handle it
        return True, ""

    def mark_done(self):
        self.state = State.DONE
