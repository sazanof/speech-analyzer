from enum import Enum


class RecordingTaskStatus(Enum):
    NEW = 0
    PENDING = 1
    FINISHED = 2
    FAILED = 3