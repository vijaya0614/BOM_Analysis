from src.providers.base import PartProvider, ProviderPart
from src.providers.settings import get_settings

def __getattr__(name: str):
    if name == "DigiKeyProvider":
        from src.providers.digikey_provider import DigiKeyProvider
        return DigiKeyProvider
    if name == "NexarProvider":
        from src.providers.nexar_provider import NexarProvider
        return NexarProvider
    if name == "MouserProvider":
        from src.providers.mouser_provider import MouserProvider
        return MouserProvider
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = ["PartProvider", "ProviderPart", "DigiKeyProvider", "NexarProvider", "MouserProvider", "get_settings"]

