"""Plain records for project templates: dataclasses only, never a model."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectRow:
    id: int
    public_id: str      # the random id of its public address (Public page link), never the number
    name: str
    status: str
    status_label: str
