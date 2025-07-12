from enum import Enum


class ExperimentStatus(str, Enum):
    CREATED = "created"
    SETUP = "setup"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
