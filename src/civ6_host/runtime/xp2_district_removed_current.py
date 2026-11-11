"""Select the existing district-removal codec for the current XP2 callback."""
from types import MappingProxyType

from .a0_family_source import A0FamilyProfile
from . import xp2_capture_notification_source as registered

SOURCE = registered.SOURCE
KIND, RECORD_TYPE, RECORD_SIZE = 0xfdf12323, 0xa0, 128


def source():
    return registered.route('district_removed', KIND, {(RECORD_TYPE, RECORD_SIZE)})


def event_profile(execution_image):
    registered.source_dependencies(execution_image)
    source()
    return A0FamilyProfile(MappingProxyType({KIND: frozenset((RECORD_TYPE,))}),
                           MappingProxyType({RECORD_TYPE: RECORD_SIZE}), SOURCE[1])


def verify_live(core, read):
    registered.verify_live(core, read, source())
