"""
skills/fortigate.py — FortiGate administration, management, and support skill.

Connects to FortiGate REST API (v2) using an API token.
All calls are read-only by default. Write operations are gated behind
FORTIGATE_ALLOW_WRITES=true to prevent accidental changes.

Configuration (loaded from .env):
  FORTIGATE_HOST          IP or hostname of the FortiGate (e.g. 192.168.1.1)
  FORTIGATE_PORT          HTTPS port (default: 443)
  FORTIGATE_TOKEN         API token generated in FortiGate admin UI
  FORTIGATE_VDOM          Target VDOM (default: root)
  FORTIGATE_VERIFY_SSL    Verify TLS certificate — set false for self-signed (default: false)
  FORTIGATE_ALLOW_WRITES  Enable write/change operations (default: false)

Enabled via: SKILL_FORTIGATE=true (default: true)

Tools available:
  MONITORING
  - fortigate_get_status         System status: firmware, hostname, serial, uptime
  - fortigate_get_interfaces     Interface list with IP, status, speed
  - fortigate_get_ha_status      HA cluster status and member info
  - fortigate_get_resources      CPU, memory, session count

  NETWORK & ROUTING
  - fortigate_get_routes         IPv4 routing table
  - fortigate_get_sessions       Active session summary (top talkers)

  SECURITY POLICIES
  - fortigate_list_policies      Firewall policy list for a VDOM
  - fortigate_get_policy         Single policy detail by ID
  - fortigate_list_address_objects  Address objects in a VDOM

  VPN
  - fortigate_get_ipsec_tunnels  IPSec VPN tunnel status
  - fortigate_get_ssl_vpn        SSL-VPN active sessions

  LOGS & DIAGNOSTICS
  - fortigate_get_log_stats      Disk log usage and stats
  - fortigate_run_diag           Run a safe read-only diagnose command

  CONFIGURATION (write-gated)
  - fortigate_set_policy_status  Enable or disable a firewall policy by ID
"""

import os
import json
import httpx
from langchain.tools import tool

# ---------------------------------------------------------------------------
# Client helpers
# ---------------------------------------------------------------------------

def _client() -> httpx.Client:
    """Build an httpx client pre-configured for this FortiGate instance."""
    host    = os.getenv("FORTIGATE_HOST", "")
    port    = os.getenv("FORTIGATE_PORT", "443")
    token   = os.getenv("FORTIGATE_TOKEN", "")
    verify  = os.getenv("FORTIGATE_VERIFY_SSL", "false").lower() == "true"

    if not host:
        raise ValueError("FORTIGATE_HOST is not set in .env")
    if not token:
        raise ValueError("FORTIGATE_TOKEN is not set in .env")

    base_url = f"https://{host}:{port}"

    return httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {token}"},
        verify=verify,
        timeout=15.0,
    )


def _vdom() -> str:
    return os.getenv("FORTIGATE_VDOM", "root")


def _writes_allowed() -> bool:
    return os.getenv("FORTIGATE_ALLOW_WRITES", "false").lower() == "true"


def _get(path: str, params: dict = None) -> dict:
    """GET request to FortiGate API. Returns parsed JSON."""
    with _client() as c:
        resp = c.get(path, params=params or {})
        resp.raise_for_status()
        return resp.json()


def _post(path: str, payload: dict) -> dict:
    """POST/PUT request — only allowed when FORTIGATE_ALLOW_WRITES=true."""
    if not _writes_allowed():
        raise PermissionError(
            "Write operations are disabled. Set FORTIGATE_ALLOW_WRITES=true in .env to enable."
        )
    with _client() as c:
        resp = c.put(path, json=payload)
        resp.raise_for_status()
        return resp.json()


def _fmt(data: dict | list, indent: int = 2) -> str:
    """Pretty-print a dict or list as JSON string."""
    return json.dumps(data, indent=indent, default=str)


def _safe_call(fn):
    """Decorator-like wrapper that catches connection errors gracefully."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as e:
            return f"CONFIG ERROR: {e}"
        except httpx.ConnectError:
            return "CONNECTION ERROR: Cannot reach FortiGate. Check FORTIGATE_HOST and network."
        except httpx.HTTPStatusError as e:
            return f"HTTP ERROR {e.response.status_code}: {e.response.text[:300]}"
        except PermissionError as e:
            return f"PERMISSION ERROR: {e}"
        except Exception as e:
            return f"ERROR: {e}"
    return wrapper


# ---------------------------------------------------------------------------
# MONITORING TOOLS
# ---------------------------------------------------------------------------

@tool
def fortigate_get_status(dummy: str = "") -> str:
    """
    Returns FortiGate system status: hostname, firmware version, serial number,
    uptime, and build info.
    Use this to identify the device and confirm connectivity.
    Input: leave empty or pass any string.
    """
    @_safe_call
    def _run(_):
        data = _get("/api/v2/monitor/system/status")
        result = data.get("results", data)
        summary = {
            "hostname":        result.get("hostname", "N/A"),
            "serial":          result.get("serial", "N/A"),
            "version":         result.get("version", "N/A"),
            "build":           result.get("build", "N/A"),
            "uptime_seconds":  result.get("uptime", "N/A"),
            "vdom_enabled":    result.get("vdom_enabled", False),
        }
        return _fmt(summary)
    return _run(dummy)


@tool
def fortigate_get_interfaces(dummy: str = "") -> str:
    """
    Returns the list of all network interfaces with their IP address,
    link status (up/down), speed, and type (physical, vlan, loopback, etc.).
    Use this to check interface health or find IP assignments.
    Input: leave empty or pass any string.
    """
    @_safe_call
    def _run(_):
        data = _get("/api/v2/monitor/system/interface/select", {"include_vdom": _vdom()})
        results = data.get("results", {})
        interfaces = []
        for name, info in results.items():
            interfaces.append({
                "name":   name,
                "ip":     info.get("ip", "N/A"),
                "status": "up" if info.get("link") else "down",
                "speed":  info.get("speed", "N/A"),
                "type":   info.get("type", "N/A"),
            })
        interfaces.sort(key=lambda x: x["name"])
        return _fmt(interfaces)
    return _run(dummy)


@tool
def fortigate_get_ha_status(dummy: str = "") -> str:
    """
    Returns High Availability (HA) cluster status: mode, members,
    sync status, and which unit is the master.
    Use this to verify HA health or failover state.
    Input: leave empty or pass any string.
    """
    @_safe_call
    def _run(_):
        data = _get("/api/v2/monitor/system/ha-statistics")
        return _fmt(data.get("results", data))
    return _run(dummy)


@tool
def fortigate_get_resources(dummy: str = "") -> str:
    """
    Returns real-time CPU usage, memory usage (%), current session count,
    and disk usage. Use this for performance monitoring and capacity checks.
    Input: leave empty or pass any string.
    """
    @_safe_call
    def _run(_):
        data = _get("/api/v2/monitor/system/resource/usage")
        results = data.get("results", {})
        cpu  = results.get("cpu", [])
        mem  = results.get("mem", [])
        sess = results.get("session", [])
        summary = {
            "cpu_percent":      cpu[0].get("current") if cpu else "N/A",
            "memory_percent":   mem[0].get("current") if mem else "N/A",
            "sessions_current": sess[0].get("current") if sess else "N/A",
            "sessions_max":     sess[0].get("max") if sess else "N/A",
        }
        return _fmt(summary)
    return _run(dummy)


# ---------------------------------------------------------------------------
# NETWORK & ROUTING TOOLS
# ---------------------------------------------------------------------------

@tool
def fortigate_get_routes(dummy: str = "") -> str:
    """
    Returns the IPv4 routing table: destination, gateway, interface,
    distance, and metric for each route.
    Use this to verify routing or troubleshoot connectivity.
    Input: leave empty or pass any string.
    """
    @_safe_call
    def _run(_):
        data = _get("/api/v2/monitor/router/ipv4", {"vdom": _vdom()})
        results = data.get("results", [])
        routes = [
            {
                "destination": r.get("ip_mask", "N/A"),
                "gateway":     r.get("gateway", "N/A"),
                "interface":   r.get("interface", "N/A"),
                "type":        r.get("type", "N/A"),
                "distance":    r.get("distance", "N/A"),
                "metric":      r.get("metric", "N/A"),
            }
            for r in results
        ]
        return _fmt(routes)
    return _run(dummy)


@tool
def fortigate_get_sessions(top_n: str = "20") -> str:
    """
    Returns a summary of active firewall sessions, limited to top N entries.
    Shows source IP, destination IP, protocol, bytes, and policy ID.
    Use this for traffic analysis or troubleshooting connectivity issues.
    Input: number of sessions to return (default: 20).
    """
    @_safe_call
    def _run(n_str):
        n = int(n_str) if str(n_str).isdigit() else 20
        data = _get(
            "/api/v2/monitor/firewall/session",
            {"vdom": _vdom(), "count": n, "summary": True}
        )
        return _fmt(data.get("results", data))
    return _run(top_n)


# ---------------------------------------------------------------------------
# SECURITY POLICY TOOLS
# ---------------------------------------------------------------------------

@tool
def fortigate_list_policies(vdom: str = "") -> str:
    """
    Lists all firewall policies for the specified VDOM (or default VDOM if empty).
    Returns policy ID, name, source/destination interfaces, action (accept/deny),
    enabled status, and associated services.
    Use this to audit or review security policies.
    Input: VDOM name, or leave empty to use the default VDOM.
    """
    @_safe_call
    def _run(v):
        target_vdom = v.strip() or _vdom()
        data = _get("/api/v2/cmdb/firewall/policy", {"vdom": target_vdom})
        results = data.get("results", [])
        policies = []
        for p in results:
            policies.append({
                "id":      p.get("policyid"),
                "name":    p.get("name", ""),
                "srcintf": [i.get("name") for i in p.get("srcintf", [])],
                "dstintf": [i.get("name") for i in p.get("dstintf", [])],
                "srcaddr": [i.get("name") for i in p.get("srcaddr", [])],
                "dstaddr": [i.get("name") for i in p.get("dstaddr", [])],
                "service": [i.get("name") for i in p.get("service", [])],
                "action":  p.get("action", "N/A"),
                "status":  p.get("status", "N/A"),
                "comments": p.get("comments", ""),
            })
        return _fmt(policies)
    return _run(vdom)


@tool
def fortigate_get_policy(policy_id: str) -> str:
    """
    Returns full details of a single firewall policy identified by its numeric ID.
    Includes NAT, logging, schedule, application control, and all configured options.
    Use this when you need to inspect a specific policy in depth.
    Input: policy ID as a number string (e.g. '5').
    """
    @_safe_call
    def _run(pid):
        data = _get(f"/api/v2/cmdb/firewall/policy/{pid}", {"vdom": _vdom()})
        results = data.get("results", [])
        return _fmt(results[0] if results else {})
    return _run(policy_id)


@tool
def fortigate_list_address_objects(filter_name: str = "") -> str:
    """
    Lists address objects defined in FortiGate (host, subnet, range, FQDN).
    Optionally filter by partial name match.
    Use this to find address objects referenced in policies or to audit definitions.
    Input: partial name to filter (e.g. 'DMZ'), or leave empty for all.
    """
    @_safe_call
    def _run(name_filter):
        params = {"vdom": _vdom()}
        if name_filter.strip():
            params["filter"] = f"name=@{name_filter.strip()}"
        data = _get("/api/v2/cmdb/firewall/address", params)
        results = data.get("results", [])
        objects = [
            {
                "name":    o.get("name"),
                "type":    o.get("type"),
                "subnet":  o.get("subnet", ""),
                "fqdn":    o.get("fqdn", ""),
                "comment": o.get("comment", ""),
            }
            for o in results
        ]
        return _fmt(objects)
    return _run(filter_name)


# ---------------------------------------------------------------------------
# VPN TOOLS
# ---------------------------------------------------------------------------

@tool
def fortigate_get_ipsec_tunnels(dummy: str = "") -> str:
    """
    Returns status of all IPSec VPN tunnels: tunnel name, remote gateway,
    phase1/phase2 status (up/down), bytes in/out, and uptime.
    Use this to verify VPN connectivity or troubleshoot tunnel drops.
    Input: leave empty or pass any string.
    """
    @_safe_call
    def _run(_):
        data = _get("/api/v2/monitor/vpn/ipsec", {"vdom": _vdom()})
        results = data.get("results", [])
        tunnels = []
        for t in results:
            tunnels.append({
                "name":           t.get("name"),
                "remote_gw":      t.get("rgwy", "N/A"),
                "status":         t.get("tun_id", "N/A"),
                "proxyid":        [
                    {
                        "status":    p.get("status"),
                        "bytes_in":  p.get("bytes_in"),
                        "bytes_out": p.get("bytes_out"),
                    }
                    for p in t.get("proxyid", [])
                ],
            })
        return _fmt(tunnels)
    return _run(dummy)


@tool
def fortigate_get_ssl_vpn(dummy: str = "") -> str:
    """
    Returns active SSL-VPN sessions: username, source IP, virtual IP assigned,
    bytes transferred, and session duration.
    Use this to see who is connected via SSL-VPN right now.
    Input: leave empty or pass any string.
    """
    @_safe_call
    def _run(_):
        data = _get("/api/v2/monitor/vpn/ssl", {"vdom": _vdom()})
        results = data.get("results", [])
        sessions = [
            {
                "user":        s.get("user_name", "N/A"),
                "src_ip":      s.get("src_ip", "N/A"),
                "virtual_ip":  s.get("virtual_ip", "N/A"),
                "bytes_in":    s.get("bytes_in", 0),
                "bytes_out":   s.get("bytes_out", 0),
                "duration_s":  s.get("duration", 0),
            }
            for s in results
        ]
        return _fmt(sessions)
    return _run(dummy)


# ---------------------------------------------------------------------------
# LOGS & DIAGNOSTICS TOOLS
# ---------------------------------------------------------------------------

@tool
def fortigate_get_log_stats(dummy: str = "") -> str:
    """
    Returns disk log statistics: total disk size, used space, log rate,
    and estimated time until disk full.
    Use this to monitor log storage and plan rotation or forwarding.
    Input: leave empty or pass any string.
    """
    @_safe_call
    def _run(_):
        data = _get("/api/v2/monitor/log/current-disk-usage")
        return _fmt(data.get("results", data))
    return _run(dummy)


@tool
def fortigate_run_diag(command: str) -> str:
    """
    Runs a safe read-only FortiGate diagnose command via the API and returns output.
    Only a curated list of safe commands is allowed to prevent accidental changes.

    Allowed commands:
      diagnose sys top           — running processes
      diagnose hardware sysinfo  — hardware info
      diagnose debug crashlog    — crash log
      diagnose netlink brctl     — bridge info
      diagnose ip route list     — kernel routes

    Input: the diagnose command string (e.g. 'diagnose sys top').
    """
    ALLOWED_PREFIXES = [
        "diagnose sys top",
        "diagnose hardware sysinfo",
        "diagnose debug crashlog",
        "diagnose netlink brctl",
        "diagnose ip route list",
    ]

    @_safe_call
    def _run(cmd):
        cmd = cmd.strip()
        if not any(cmd.startswith(p) for p in ALLOWED_PREFIXES):
            allowed = "\n".join(f"  - {p}" for p in ALLOWED_PREFIXES)
            return f"DENIED: Command not in allowed list.\nAllowed:\n{allowed}"

        data = _post("/api/v2/monitor/system/cli", {"commands": cmd})
        return data.get("results", _fmt(data))
    return _run(command)


# ---------------------------------------------------------------------------
# CONFIGURATION TOOLS (write-gated)
# ---------------------------------------------------------------------------

@tool
def fortigate_set_policy_status(input: str) -> str:
    """
    Enables or disables a firewall policy by ID.
    REQUIRES: FORTIGATE_ALLOW_WRITES=true in .env

    Input format: 'policy_id::enable' or 'policy_id::disable'
    Example: '10::disable'

    Use this to quickly disable a compromised or misconfigured policy
    without deleting it.
    """
    @_safe_call
    def _run(inp):
        if "::" not in inp:
            return "ERROR: Input must be in format 'policy_id::enable|disable'"
        pid, action = inp.split("::", 1)
        pid = pid.strip()
        action = action.strip().lower()
        if action not in ("enable", "disable"):
            return "ERROR: action must be 'enable' or 'disable'"
        payload = {"status": action}
        data = _post(
            f"/api/v2/cmdb/firewall/policy/{pid}",
            {"vdom": _vdom(), **payload},
        )
        return f"Policy {pid} set to '{action}'. Response: {_fmt(data)}"
    return _run(input)


# ---------------------------------------------------------------------------
# Skill metadata
# ---------------------------------------------------------------------------

SKILL = {
    "name": "FortiGate",
    "description": (
        "Administer, monitor, and support FortiGate firewalls via REST API. "
        "Covers system status, interfaces, HA, routing, sessions, policies, "
        "VPN tunnels, SSL-VPN, logs, diagnostics, and policy management."
    ),
    "env_key": "SKILL_FORTIGATE",
    "get_tools": lambda: [
        # Monitoring
        fortigate_get_status,
        fortigate_get_interfaces,
        fortigate_get_ha_status,
        fortigate_get_resources,
        # Network & Routing
        fortigate_get_routes,
        fortigate_get_sessions,
        # Security Policies
        fortigate_list_policies,
        fortigate_get_policy,
        fortigate_list_address_objects,
        # VPN
        fortigate_get_ipsec_tunnels,
        fortigate_get_ssl_vpn,
        # Logs & Diagnostics
        fortigate_get_log_stats,
        fortigate_run_diag,
        # Configuration (write-gated)
        fortigate_set_policy_status,
    ],
}
