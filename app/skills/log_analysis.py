"""
skills/log_analysis.py — FortiGate log analysis skill.

Parses and analyzes FortiGate log files (traffic, event, UTM).
Log files are read from the workspace/ or any accessible path.

Supported log formats:
  - FortiGate key=value format (standard syslog output)
  - Plain text logs (grep-style search)

Tools:
  - parse_fortigate_log    : parse a log file into structured summary
  - top_blocked_ips        : find top N source IPs with blocked/denied traffic
  - search_log             : search for a keyword/IP/port in a log file
  - generate_log_report    : full analysis report saved to workspace/

Enabled via: SKILL_LOG_ANALYSIS=true (default: true)
"""

import os
import re
import json
from collections import Counter, defaultdict
from datetime import datetime
from langchain.tools import tool


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_line(line: str) -> dict:
    """
    Parse a single FortiGate key=value log line into a dict.
    Handles both quoted and unquoted values.
    Example line:
      date=2024-01-15 time=10:23:45 type="traffic" action="accept" srcip=1.2.3.4 ...
    """
    result = {}
    # Match key="value" or key=value (no spaces in unquoted values)
    for m in re.finditer(r'(\w+)=("(?:[^"\\]|\\.)*"|[^\s]+)', line):
        key = m.group(1)
        val = m.group(2).strip('"')
        result[key] = val
    return result


def _read_lines(path: str) -> list[str]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return [l.rstrip() for l in f if l.strip()]


def _workspace_path(filename: str) -> str:
    workspace = os.getenv("WORKSPACE_PATH", "/app/workspace")
    return os.path.join(workspace, filename)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def parse_fortigate_log(path: str) -> str:
    """
    Parses a FortiGate log file and returns a structured summary including:
    - total lines parsed
    - log types found (traffic, event, utm, etc.)
    - action breakdown (accept, deny, drop, close, etc.)
    - top 10 source IPs
    - top 10 destination IPs
    - top 10 services/ports
    - time range of the log

    Use this for a quick overview of what a log file contains.
    Input: full path to the log file (e.g. /app/workspace/traffic.log).
    """
    try:
        lines = _read_lines(path)
    except FileNotFoundError:
        return f"ERROR: File not found — {path}"
    except Exception as e:
        return f"ERROR: {e}"

    if not lines:
        return f"ERROR: File is empty — {path}"

    parsed = [_parse_line(l) for l in lines]
    parsed = [p for p in parsed if p]  # skip unparseable lines

    if not parsed:
        return (
            f"WARNING: Could not parse any key=value pairs from {path}.\n"
            "Make sure it is a FortiGate syslog file."
        )

    types    = Counter(p.get("type", "unknown") for p in parsed)
    actions  = Counter(p.get("action", "unknown") for p in parsed)
    src_ips  = Counter(p.get("srcip", "") for p in parsed if p.get("srcip"))
    dst_ips  = Counter(p.get("dstip", "") for p in parsed if p.get("dstip"))
    services = Counter(p.get("service", p.get("dstport", "")) for p in parsed if p.get("service") or p.get("dstport"))

    dates = [p.get("date", "") for p in parsed if p.get("date")]
    time_range = f"{min(dates)} → {max(dates)}" if dates else "N/A"

    summary = {
        "file":            path,
        "total_lines":     len(lines),
        "parsed_entries":  len(parsed),
        "time_range":      time_range,
        "log_types":       dict(types.most_common()),
        "actions":         dict(actions.most_common()),
        "top_10_src_ips":  dict(src_ips.most_common(10)),
        "top_10_dst_ips":  dict(dst_ips.most_common(10)),
        "top_10_services": dict(services.most_common(10)),
    }

    return json.dumps(summary, indent=2)


@tool
def top_blocked_ips(input: str) -> str:
    """
    Returns the top N source IPs that were blocked or denied in a log file.
    Useful for identifying attackers, scanners, or misconfigured hosts.

    Input format: 'path::N'  (path to log file and number of results)
    Example: '/app/workspace/traffic.log::20'
    If N is omitted, defaults to 10.
    """
    try:
        if "::" in input:
            path, n_str = input.split("::", 1)
            n = int(n_str.strip()) if n_str.strip().isdigit() else 10
        else:
            path, n = input.strip(), 10

        lines = _read_lines(path)
    except FileNotFoundError:
        return f"ERROR: File not found — {path}"
    except Exception as e:
        return f"ERROR: {e}"

    blocked_actions = {"deny", "drop", "block", "reset", "timeout"}
    blocked_ips: Counter = Counter()

    for line in lines:
        p = _parse_line(line)
        action = p.get("action", "").lower()
        src_ip = p.get("srcip", "")
        if action in blocked_actions and src_ip:
            blocked_ips[src_ip] += 1

    if not blocked_ips:
        return "No blocked/denied entries found in this log file."

    results = []
    for ip, count in blocked_ips.most_common(n):
        results.append({"src_ip": ip, "blocked_count": count})

    return json.dumps({
        "file":          path,
        "top_blocked":   results,
        "total_blocked": sum(blocked_ips.values()),
    }, indent=2)


@tool
def search_log(input: str) -> str:
    """
    Searches a log file for lines containing a specific keyword, IP address,
    port, or any string pattern. Returns matching lines with line numbers.

    Input format: 'path::keyword'
    Example: '/app/workspace/traffic.log::192.168.1.100'
    Example: '/app/workspace/event.log::admin'
    Example: '/app/workspace/traffic.log::action=deny'
    """
    if "::" not in input:
        return "ERROR: Input must be in format 'path::keyword'"

    path, keyword = input.split("::", 1)
    path = path.strip()
    keyword = keyword.strip()

    try:
        lines = _read_lines(path)
    except FileNotFoundError:
        return f"ERROR: File not found — {path}"
    except Exception as e:
        return f"ERROR: {e}"

    matches = [
        f"[line {i+1}] {line}"
        for i, line in enumerate(lines)
        if keyword.lower() in line.lower()
    ]

    if not matches:
        return f"No lines matching '{keyword}' found in {path}."

    MAX_RESULTS = 50
    truncated = len(matches) > MAX_RESULTS
    output_lines = matches[:MAX_RESULTS]

    result = f"Found {len(matches)} match(es) for '{keyword}' in {path}"
    if truncated:
        result += f" (showing first {MAX_RESULTS})"
    result += ":\n\n" + "\n".join(output_lines)
    return result


@tool
def generate_log_report(path: str) -> str:
    """
    Generates a full human-readable analysis report for a FortiGate log file
    and saves it to workspace/report_<timestamp>.txt.

    The report includes:
    - Executive summary
    - Action breakdown with percentages
    - Top talkers (src/dst IPs)
    - Top blocked IPs with counts
    - Top services
    - Anomaly flags (high deny rate, single IP flooding)

    Use this to produce a written incident or daily report.
    Input: full path to the log file.
    """
    try:
        lines = _read_lines(path)
    except FileNotFoundError:
        return f"ERROR: File not found — {path}"
    except Exception as e:
        return f"ERROR: {e}"

    if not lines:
        return f"ERROR: File is empty — {path}"

    parsed = [_parse_line(l) for l in lines if _parse_line(l)]
    total = len(parsed)

    if total == 0:
        return "ERROR: No parseable entries found."

    # Counters
    actions  = Counter(p.get("action", "unknown") for p in parsed)
    src_ips  = Counter(p.get("srcip", "") for p in parsed if p.get("srcip"))
    dst_ips  = Counter(p.get("dstip", "") for p in parsed if p.get("dstip"))
    services = Counter(p.get("service", p.get("dstport", "")) for p in parsed if p.get("service") or p.get("dstport"))
    policies = Counter(p.get("policyid", "") for p in parsed if p.get("policyid"))
    dates    = [p.get("date", "") for p in parsed if p.get("date")]

    blocked_actions = {"deny", "drop", "block", "reset"}
    blocked_total = sum(v for k, v in actions.items() if k.lower() in blocked_actions)
    deny_rate = (blocked_total / total * 100) if total else 0

    # Anomaly detection
    anomalies = []
    if deny_rate > 30:
        anomalies.append(f"HIGH DENY RATE: {deny_rate:.1f}% of traffic was blocked/denied.")
    top_src = src_ips.most_common(1)
    if top_src and top_src[0][1] > total * 0.2:
        anomalies.append(
            f"SINGLE IP FLOOD: {top_src[0][0]} generated {top_src[0][1]} entries "
            f"({top_src[0][1]/total*100:.1f}% of total traffic)."
        )

    # Build report text
    time_range = f"{min(dates)} to {max(dates)}" if dates else "N/A"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_lines = [
        "=" * 60,
        f"  FORTIGATE LOG ANALYSIS REPORT",
        f"  Generated : {now}",
        f"  Log file  : {path}",
        "=" * 60,
        "",
        "SUMMARY",
        "-" * 40,
        f"  Total entries   : {total}",
        f"  Time range      : {time_range}",
        f"  Blocked/Denied  : {blocked_total} ({deny_rate:.1f}%)",
        "",
        "ACTIONS",
        "-" * 40,
    ]
    for action, count in actions.most_common():
        pct = count / total * 100
        report_lines.append(f"  {action:<15} {count:>6}  ({pct:.1f}%)")

    report_lines += ["", "TOP 10 SOURCE IPs", "-" * 40]
    for ip, count in src_ips.most_common(10):
        report_lines.append(f"  {ip:<20} {count:>6} events")

    report_lines += ["", "TOP 10 DESTINATION IPs", "-" * 40]
    for ip, count in dst_ips.most_common(10):
        report_lines.append(f"  {ip:<20} {count:>6} events")

    report_lines += ["", "TOP BLOCKED SOURCE IPs", "-" * 40]
    blocked_by_ip: Counter = Counter()
    for p in parsed:
        if p.get("action", "").lower() in blocked_actions and p.get("srcip"):
            blocked_by_ip[p["srcip"]] += 1
    for ip, count in blocked_by_ip.most_common(10):
        report_lines.append(f"  {ip:<20} {count:>6} blocked")

    report_lines += ["", "TOP SERVICES / PORTS", "-" * 40]
    for svc, count in services.most_common(10):
        report_lines.append(f"  {svc:<20} {count:>6} events")

    report_lines += ["", "TOP POLICIES", "-" * 40]
    for pol, count in policies.most_common(10):
        report_lines.append(f"  Policy {pol:<10} {count:>6} matches")

    if anomalies:
        report_lines += ["", "ANOMALIES DETECTED", "-" * 40]
        for a in anomalies:
            report_lines.append(f"  [!] {a}")
    else:
        report_lines += ["", "ANOMALIES", "-" * 40, "  None detected."]

    report_lines += ["", "=" * 60]
    report_text = "\n".join(report_lines)

    # Save to workspace
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f"report_{timestamp}.txt"
    workspace = os.getenv("WORKSPACE_PATH", "/app/workspace")
    report_path = os.path.join(workspace, report_filename)

    os.makedirs(workspace, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    return f"Report saved to: {report_path}\n\n{report_text}"


# ---------------------------------------------------------------------------
# Skill metadata
# ---------------------------------------------------------------------------

SKILL = {
    "name": "Log Analysis",
    "description": (
        "Parse and analyze FortiGate log files. "
        "Identify top blocked IPs, traffic patterns, anomalies, "
        "and generate written reports."
    ),
    "env_key": "SKILL_LOG_ANALYSIS",
    "get_tools": lambda: [
        parse_fortigate_log,
        top_blocked_ips,
        search_log,
        generate_log_report,
    ],
}
