from struct import unpack, calcsize
from dataclasses import dataclass

animation_names = [
    "Stationary",
    "Idle 0",
    "Idle 1",
    "Move Start",
    "Move Stop",
    "Move",
    "Turn Left",
    "Turn Right",
    "Fire 0",
    "Fire 1",
    "Fire 2",
    "Fire 3",
    "Fire 4",
    "Explode",
    "Blow Up 1",
    "Blow Up 2",
    "Shot 1",
    "Shot 2",
    "Burnt 1",
    "Run Over 1",
    "Gassed 1",
    "Deployed Death 1",
    "Deployed Death 2",
    "Deploy Gun",
    "Deploy Gun Hold",
    "Undeploy Gun",
    "Deployed Idle 0",
    "Deployed Fire",
    "DeployedDeath0",
    "Harv Unload Start",
    "Harv Unload Hold",
    "Harv Unload End",
    "Harv Eat Start",
    "Harv Eat Hold",
    "Harv Eat End",
    "Repair Arms Out",
    "Repair Arms Hold",
    "Repair Arms In",
    "Sink",
    "SinkHold",
    "Surface",
    "SinkMove",
    "Move Special",
    "StandToLayDown",
    "LayDownToStand",
    "Lay Down",
    "Crawl",
    "Lay Down Fire",
    "Crouch",
    "CrouchFire",
    "Construct",
    "Deconstruct",
    "Takeoff",
    "Land",
    "Hover",
    "Fly",
    "FlyToHover",
    "HoverToFly",
    "StartPickup",
    "Pickup",
    "EndPickup",
    "Enter Portal",
    "Exit Portal",
    "Win",
    "Leeched",
    "Leech Death",
    "Born",
    "Refinery Pad 1",
    "Refinery Pad 2",
    "Sell",
]


@dataclass
class AnimationSegment:
    start: int
    end: int
    repeat: int
    unknown: int

    def __str__(self):
        return f"Frames {self.start} to {self.end}, Repeat {self.repeat}"


@dataclass
class Animation:
    name: str
    segments: list[AnimationSegment]
    unknown: int

    @classmethod
    def frombytes(cls, octets):
        header_format = "<32si"
        header_size = calcsize(header_format)
        name, anim_unknown = unpack(header_format, octets[:header_size])
        name = name.split(b"\x00")[0].decode("ascii")

        segment_format = "<3i?3s2i"
        segment_size = calcsize(segment_format)
        segments = []
        is_last = False
        i = 0
        while not is_last:
            octets_slice = octets[
                header_size + i * segment_size : header_size + (i + 1) * segment_size
            ]
            segment_unknown, repeat, body_part, is_last, padding, start, end = unpack(
                segment_format, octets_slice
            )
            segments.append(AnimationSegment(start, end, repeat, segment_unknown))
            i += 1

        return cls(name, segments, anim_unknown)


def parse_animations(fxdata):
    animations = []

    for animation_name in animation_names:
        offset = fxdata.rfind(animation_name.encode("ascii") + b"\x00")
        if offset == -1:
            continue
        animations.append(Animation.frombytes(fxdata[offset:]))

    return animations
