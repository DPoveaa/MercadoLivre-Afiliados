import os


def load_whatsapp_destinations() -> list:
    """
    Loads WhatsApp destinations from env.

    Expected vars:
    - TEST_MODE=true|false
    - WHATSAPP_GROUPS / WHATSAPP_GROUPS_TESTE (comma-separated)
    - WHATSAPP_CHANNELS / WHATSAPP_CHANNELS_TESTE (comma-separated)
    """
    test = os.getenv("TEST_MODE", "false").lower() == "true"

    if test:
        groups = os.getenv("WHATSAPP_GROUPS_TESTE", "")
        channels = os.getenv("WHATSAPP_CHANNELS_TESTE", "")
    else:
        groups = os.getenv("WHATSAPP_GROUPS", "")
        channels = os.getenv("WHATSAPP_CHANNELS", "")

    destinations = []
    if groups:
        destinations.extend([g.strip() for g in groups.split(",") if g.strip()])
    if channels:
        destinations.extend([c.strip() for c in channels.split(",") if c.strip()])

    return destinations

