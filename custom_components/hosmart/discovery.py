"""Local network discovery helpers for Ho-Smart receivers."""

from __future__ import annotations

import asyncio
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network

from homeassistant.components import dhcp, network
from homeassistant.core import HomeAssistant

DEFAULT_DISCOVERY_PORT = 8080
DISCOVERY_CONNECT_TIMEOUT = 0.35
DISCOVERY_CONCURRENCY = 96
MAX_ACTIVE_SCAN_HOSTS = 4094


def _usable_ipv4(value: str) -> IPv4Address | None:
    try:
        address = ip_address(value)
    except ValueError:
        return None

    if not isinstance(address, IPv4Address):
        return None
    if address.is_loopback or address.is_link_local or address.is_multicast:
        return None
    return address


def _active_scan_network(local_address: IPv4Address, prefix: int) -> IPv4Network:
    """Return a bounded directly-connected network to scan.

    Home Assistant installations sometimes report very large connected networks.
    Scanning an entire /16 or larger would be unnecessarily slow and noisy, so
    discovery limits active probing to at most a /20 around the Home Assistant
    interface. DHCP-cached addresses are still probed regardless of subnet size.
    """
    safe_prefix = max(int(prefix), 20)
    return ip_network(f"{local_address}/{safe_prefix}", strict=False)


async def _async_port_open(host: str, port: int) -> bool:
    writer = None
    try:
        async with asyncio.timeout(DISCOVERY_CONNECT_TIMEOUT):
            _reader, writer = await asyncio.open_connection(host, port)
        return True
    except (TimeoutError, ConnectionError, OSError):
        return False
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass


async def async_discover_hosts(
    hass: HomeAssistant,
    port: int = DEFAULT_DISCOVERY_PORT,
) -> list[str]:
    """Return reachable local IPv4 hosts accepting the Ho-Smart control port."""
    candidates: set[str] = set()
    local_addresses: set[str] = set()

    adapters = await network.async_get_adapters(hass)
    for adapter in adapters:
        if not adapter.get("enabled", True):
            continue

        for ip_info in adapter.get("ipv4", []):
            address = _usable_ipv4(str(ip_info.get("address", "")))
            if address is None:
                continue

            local_addresses.add(str(address))
            prefix = int(ip_info.get("network_prefix", 24))
            active_network = _active_scan_network(address, prefix)

            if active_network.num_addresses - 2 > MAX_ACTIVE_SCAN_HOSTS:
                continue

            candidates.update(str(host) for host in active_network.hosts())

    # DHCP discovery gives us useful addresses outside a bounded active scan and
    # can also catch receivers on larger routed networks without probing every IP.
    try:
        for service_info in dhcp.async_discovered_service_info(hass):
            address = _usable_ipv4(str(service_info.ip))
            if address is not None:
                candidates.add(str(address))
    except (AttributeError, RuntimeError):
        # DHCP may not be available in every supported Home Assistant install.
        pass

    candidates.difference_update(local_addresses)
    if not candidates:
        return []

    semaphore = asyncio.Semaphore(DISCOVERY_CONCURRENCY)

    async def probe(host: str) -> str | None:
        async with semaphore:
            return host if await _async_port_open(host, port) else None

    results = await asyncio.gather(*(probe(host) for host in candidates))
    found = [host for host in results if host is not None]
    return sorted(found, key=lambda value: int(ip_address(value)))
