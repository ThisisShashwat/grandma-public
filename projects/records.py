"""Plain records for project templates: dataclasses only, never a model."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectRow:
    id: int
    name: str
    status: str
    status_label: str
    hardware: bool
    can_ship_build: bool
    can_finish: bool
