"""
Schedule Formatter Service
Handles normalization and formatting of schedule availability strings.
"""

def normalize_schedule_availability(schedule_availability: str) -> str:
    """
    Normalize schedule availability string.

    Args:
        schedule_availability: Raw schedule availability string (can be None)

    Returns:
        Normalized schedule availability string, or empty string if None
    """
    if not schedule_availability:
        return ""

    # Strip whitespace and normalize
    normalized = schedule_availability.strip()

    # Basic normalization - could be extended for more complex formatting
    # For now, just return the stripped string
    return normalized