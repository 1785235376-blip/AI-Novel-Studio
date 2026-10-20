"""Pure finite packaged-profile selector, shared before runtime initialization."""

DEFAULT_PROFILE = "default"
V2_PROFILE = "v2"
PROFILE_ENV = "AI_NOVEL_PACKAGED_PROFILE"
PROFILES = (DEFAULT_PROFILE, V2_PROFILE)


def validate_profile(value: str) -> str:
    if not isinstance(value, str) or value not in PROFILES:
        raise ValueError("PACKAGED_PROFILE_UNSUPPORTED")
    return value
