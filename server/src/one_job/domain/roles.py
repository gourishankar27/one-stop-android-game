"""Seeded ownership and immutable instructions, separate from ship rules."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from random import Random
from types import MappingProxyType

from one_job.domain._validation import enumeration, frozen_sequence
from one_job.domain.models import Player, RoleAssignment
from one_job.domain.types import Role


@dataclass(frozen=True, slots=True)
class StationMetadata:
    role: Role
    title: str
    steps: tuple[str, ...]

    def __post_init__(self) -> None:
        enumeration(self.role, Role, "role")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("station title is required")
        steps = frozen_sequence(self.steps, str, "steps")
        if not 1 <= len(steps) <= 4 or any(not step.strip() for step in steps):
            raise ValueError("station needs one to four short instructions")
        object.__setattr__(self, "steps", steps)


STATIONS: Mapping[Role, StationMetadata] = MappingProxyType(
    {
        Role.PILOT: StationMetadata(
            Role.PILOT,
            "Pilot",
            (
                "Choose the ship's lane and call out where cover is needed.",
                "Ask Engineer for enough output before an evasive maneuver.",
            ),
        ),
        Role.ENGINEER: StationMetadata(
            Role.ENGINEER,
            "Engineer",
            (
                "Balance engine output against heat and the crew's power needs.",
                "Use coolant when needed and tell Shields when power is tight.",
            ),
        ),
        Role.SHIELDS: StationMetadata(
            Role.SHIELDS,
            "Shields",
            (
                "Point protection toward the danger and watch shield energy.",
                "Coordinate power with Engineer and announce which side is covered.",
            ),
        ),
    }
)


def assign_roles(players: Sequence[Player], rng: Random) -> RoleAssignment:
    """Validate before consuming RNG; shuffle a copy, preserving input roster order."""
    roster = frozen_sequence(players, Player, "players")
    if (
        len(roster) not in (2, 3)
        or any(not isinstance(player, Player) for player in roster)
        or len({player.player_id for player in roster}) != len(roster)
    ):
        raise ValueError("role assignment needs two or three distinct players")
    if not isinstance(rng, Random):
        raise ValueError("role assignment needs an injected Random")
    owners = [player.player_id for player in roster]
    rng.shuffle(owners)
    return RoleAssignment(
        tuple(player.player_id for player in roster),
        {
            Role.PILOT: owners[0],
            Role.ENGINEER: owners[1],
            Role.SHIELDS: owners[2] if len(owners) == 3 else owners[1],
        },
    )
