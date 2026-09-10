"""Bounded retry budgets; exhaustion always routes to human escalation."""

from pydantic import BaseModel

DEFAULT_MAX_ATTEMPTS = 3


class RetryBudget(BaseModel):
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    attempts_used: int = 0

    @property
    def exhausted(self) -> bool:
        return self.attempts_used >= self.max_attempts

    @property
    def remaining(self) -> int:
        return max(self.max_attempts - self.attempts_used, 0)

    def consume(self) -> "RetryBudget":
        return RetryBudget(max_attempts=self.max_attempts, attempts_used=self.attempts_used + 1)
