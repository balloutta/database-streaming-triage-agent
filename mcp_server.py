import json
import re
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SCENARIOS_FILE = BASE_DIR / "data" / "scenarios.json"
INCIDENTS_FILE = BASE_DIR / "data" / "incidents.json"
THRESHOLDS_FILE = BASE_DIR / "config" / "thresholds.json"


# ============================================================
# LOAD PROJECT DATA
# ============================================================

def load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


SCENARIOS = load_json(SCENARIOS_FILE)
INCIDENTS = load_json(INCIDENTS_FILE)
THRESHOLDS = load_json(THRESHOLDS_FILE)


# ============================================================
# MCP SERVER
# ============================================================

mcp = FastMCP("database-streaming-triage-tools")


# ============================================================
# INTERNAL HELPERS
# ============================================================

def get_scenario(scenario_id: str) -> dict:
    """
    Internal helper that validates and returns a scenario.
    """

    if scenario_id not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())

        raise ValueError(
            f"Unknown scenario_id '{scenario_id}'. "
            f"Available scenarios: {available}"
        )

    return SCENARIOS[scenario_id]


def log_tool_call(tool_name: str, details: str) -> None:
    """
    Write diagnostic information to stderr.

    stdout is reserved for the MCP stdio protocol.
    """

    print(
        f"[MCP TOOL] {tool_name}: {details}",
        file=sys.stderr,
        flush=True
    )


def tokenize(text: str) -> set[str]:
    """
    Normalize text into useful tokens for simple retrieval.
    """

    words = re.findall(r"[a-zA-Z0-9_]+", text.lower())

    stop_words = {
        "the", "a", "an", "and", "or", "is", "are", "was",
        "were", "to", "of", "in", "on", "for", "with",
        "that", "this", "be", "by", "as", "at", "from"
    }

    return {
        word
        for word in words
        if word not in stop_words and len(word) > 2
    }


# ============================================================
# TOOL 1
# HIGH-LEVEL HEALTH SUMMARY
# ============================================================

@mcp.tool()
def check_health_summary(scenario_id: str) -> dict:
    """
    Return a high-level operational health summary for an incident.

    Use this as the first monitoring tool during triage. It checks
    replication, Debezium, Kafka consumer lag, database connection
    utilization, server resources, and service state against configured
    operational thresholds.

    Input:
        scenario_id: Incident scenario identifier such as "scenario_1".
    """

    log_tool_call(
        "check_health_summary",
        f"scenario_id={scenario_id}"
    )

    scenario = get_scenario(scenario_id)

    replication = scenario["replication"]
    debezium = scenario["debezium"]
    kafka = scenario["kafka"]
    db_connections = scenario["database_connections"]
    server = scenario["server_metrics"]
    services = scenario["services"]

    anomalies = []

    # --------------------------------------------------------
    # Replication
    # --------------------------------------------------------

    if not replication["io_running"]:
        anomalies.append({
            "component": "database_replication",
            "severity": "critical",
            "observation": "Replication IO thread is not running."
        })

    if not replication["sql_running"]:
        anomalies.append({
            "component": "database_replication",
            "severity": "critical",
            "observation": "Replication SQL thread is not running."
        })

    lag = replication["lag_seconds"]

    if (
        lag is not None
        and lag > THRESHOLDS["replication_lag_warning_seconds"]
    ):
        anomalies.append({
            "component": "database_replication",
            "severity": "warning",
            "observation": f"Replication lag is {lag} seconds."
        })

    # --------------------------------------------------------
    # Debezium
    # --------------------------------------------------------

    if debezium["status"] != "RUNNING":
        anomalies.append({
            "component": "debezium",
            "severity": "critical",
            "observation": (
                f"Debezium connector status is "
                f"{debezium['status']}."
            )
        })

    if debezium["tasks_failed"] > 0:
        anomalies.append({
            "component": "debezium",
            "severity": "critical",
            "observation": (
                f"{debezium['tasks_failed']} Debezium task(s) failed."
            )
        })

    # --------------------------------------------------------
    # Kafka
    # --------------------------------------------------------

    kafka_lag = kafka["lag"]

    if kafka_lag >= THRESHOLDS["kafka_consumer_lag_critical"]:
        severity = "critical"

    elif kafka_lag >= THRESHOLDS["kafka_consumer_lag_warning"]:
        severity = "warning"

    else:
        severity = None

    if severity:
        anomalies.append({
            "component": "kafka_consumer",
            "severity": severity,
            "observation": (
                f"Consumer lag is {kafka_lag} "
                f"and trend is {kafka['trend']}."
            )
        })

    # --------------------------------------------------------
    # Database connections
    # --------------------------------------------------------

    max_connections = db_connections["max_connections"]
    threads_connected = db_connections["threads_connected"]

    connection_usage = (
        (threads_connected / max_connections) * 100
        if max_connections > 0
        else 0
    )

    if (
        connection_usage
        >= THRESHOLDS["database_connection_warning_percent"]
    ):
        anomalies.append({
            "component": "database_connections",
            "severity": "warning",
            "observation": (
                f"Database connection utilization is "
                f"{connection_usage:.1f}% "
                f"({threads_connected}/{max_connections})."
            )
        })

    # --------------------------------------------------------
    # CPU
    # --------------------------------------------------------

    if server["cpu_percent"] >= THRESHOLDS["cpu_warning_percent"]:
        anomalies.append({
            "component": "cpu",
            "severity": "warning",
            "observation": (
                f"CPU usage is {server['cpu_percent']}%."
            )
        })

    # --------------------------------------------------------
    # Memory
    # --------------------------------------------------------

    if (
        server["memory_percent"]
        >= THRESHOLDS["memory_warning_percent"]
    ):
        anomalies.append({
            "component": "memory",
            "severity": "warning",
            "observation": (
                f"Memory usage is {server['memory_percent']}%."
            )
        })

    # --------------------------------------------------------
    # Disk
    # --------------------------------------------------------

    disk_percent = server["disk_percent"]

    if disk_percent >= THRESHOLDS["disk_critical_percent"]:
        disk_severity = "critical"

    elif disk_percent >= THRESHOLDS["disk_warning_percent"]:
        disk_severity = "warning"

    else:
        disk_severity = None

    if disk_severity:
        anomalies.append({
            "component": "disk",
            "severity": disk_severity,
            "observation": f"Disk usage is {disk_percent}%."
        })

    # --------------------------------------------------------
    # Services
    # --------------------------------------------------------

    for service_name, status in services.items():

        if status != "RUNNING":
            anomalies.append({
                "component": f"service:{service_name}",
                "severity": "warning",
                "observation": (
                    f"Service {service_name} status is {status}."
                )
            })

    return {
        "scenario_id": scenario_id,
        "environment": scenario["environment"],

        "summary": {
            "replication": (
                "HEALTHY"
                if (
                    replication["io_running"]
                    and replication["sql_running"]
                    and (
                        lag is None
                        or lag
                        <= THRESHOLDS[
                            "replication_lag_warning_seconds"
                        ]
                    )
                )
                else "ABNORMAL"
            ),

            "debezium": (
                "HEALTHY"
                if (
                    debezium["status"] == "RUNNING"
                    and debezium["tasks_failed"] == 0
                )
                else "ABNORMAL"
            ),

            "kafka_consumer_lag": kafka_lag,

            "kafka_lag_trend": kafka["trend"],

            "database_connection_usage_percent": round(
                connection_usage,
                1
            ),

            "cpu_percent": server["cpu_percent"],
            "memory_percent": server["memory_percent"],
            "disk_percent": server["disk_percent"]
        },

        "anomalies": anomalies
    }


# ============================================================
# TOOL 2
# DATABASE REPLICATION
# ============================================================

@mcp.tool()
def check_replication_status(scenario_id: str) -> dict:
    """
    Return detailed MariaDB replication status and replication errors.

    Use this when database replication appears abnormal or when stale
    downstream data could be caused by replication.

    Input:
        scenario_id: Incident scenario identifier.
    """

    log_tool_call(
        "check_replication_status",
        f"scenario_id={scenario_id}"
    )

    scenario = get_scenario(scenario_id)

    return {
        "scenario_id": scenario_id,
        **scenario["replication"]
    }


# ============================================================
# TOOL 3
# DATABASE CONNECTIONS
# ============================================================

@mcp.tool()
def check_database_connections(scenario_id: str) -> dict:
    """
    Return MariaDB connection utilization and connection-error metrics.

    Use this when logs mention connection timeouts, too many
    connections, connection-pool problems, or when consumer processing
    may be blocked waiting for database connections.

    Input:
        scenario_id: Incident scenario identifier.
    """

    log_tool_call(
        "check_database_connections",
        f"scenario_id={scenario_id}"
    )

    scenario = get_scenario(scenario_id)

    data = scenario["database_connections"]

    max_connections = data["max_connections"]
    threads_connected = data["threads_connected"]

    usage_percent = (
        (threads_connected / max_connections) * 100
        if max_connections > 0
        else 0
    )

    return {
        "scenario_id": scenario_id,
        **data,
        "usage_percent": round(usage_percent, 1)
    }


# ============================================================
# TOOL 4
# DEBEZIUM
# ============================================================

@mcp.tool()
def check_debezium(scenario_id: str) -> dict:
    """
    Return Debezium connector and task health.

    Use this when investigating change-data-capture failures,
    missing CDC events, or streaming-pipeline freshness issues.

    Input:
        scenario_id: Incident scenario identifier.
    """

    log_tool_call(
        "check_debezium",
        f"scenario_id={scenario_id}"
    )

    scenario = get_scenario(scenario_id)

    return {
        "scenario_id": scenario_id,
        **scenario["debezium"]
    }


# ============================================================
# TOOL 5
# KAFKA CONSUMER LAG
# ============================================================

@mcp.tool()
def check_kafka_lag(scenario_id: str) -> dict:
    """
    Return Kafka consumer-group lag and lag trend.

    Use this when investigating delayed downstream processing,
    consumer backlog, or stale analytics data.

    Input:
        scenario_id: Incident scenario identifier.
    """

    log_tool_call(
        "check_kafka_lag",
        f"scenario_id={scenario_id}"
    )

    scenario = get_scenario(scenario_id)

    return {
        "scenario_id": scenario_id,
        **scenario["kafka"]
    }


# ============================================================
# TOOL 6
# SERVER / INFRASTRUCTURE METRICS
# ============================================================

@mcp.tool()
def check_server_metrics(scenario_id: str) -> dict:
    """
    Return server CPU, memory, disk, network, and service state.

    Use this when an incident may be caused by infrastructure,
    resource exhaustion, or an unhealthy operating-system service.

    Input:
        scenario_id: Incident scenario identifier.
    """

    log_tool_call(
        "check_server_metrics",
        f"scenario_id={scenario_id}"
    )

    scenario = get_scenario(scenario_id)

    return {
        "scenario_id": scenario_id,
        "server_metrics": scenario["server_metrics"],
        "services": scenario["services"]
    }


# ============================================================
# TOOL 7
# LOG RETRIEVAL
# ============================================================

@mcp.tool()
def read_logs(
    scenario_id: str,
    service: str,
    max_lines: int = 10
) -> dict:
    """
    Return a bounded number of recent simulated log messages.

    Use this when another observation indicates that a specific
    service needs deeper investigation.

    Valid services depend on the incident and may include:
    analytics_consumer, mariadb, or kafka.

    Inputs:
        scenario_id: Incident scenario identifier.
        service: Service whose logs should be inspected.
        max_lines: Maximum number of lines to return. Maximum is 20.
    """

    log_tool_call(
        "read_logs",
        (
            f"scenario_id={scenario_id}, "
            f"service={service}, "
            f"max_lines={max_lines}"
        )
    )

    scenario = get_scenario(scenario_id)

    logs = scenario["logs"]

    if service not in logs:

        return {
            "scenario_id": scenario_id,
            "service": service,
            "error": "Unknown service.",
            "available_services": list(logs.keys())
        }

    safe_max_lines = max(
        1,
        min(max_lines, 20)
    )

    selected = logs[service][-safe_max_lines:]

    return {
        "scenario_id": scenario_id,
        "service": service,
        "returned_lines": len(selected),
        "logs": selected
    }


# ============================================================
# TOOL 8
# HISTORICAL INCIDENT MEMORY / RETRIEVAL
# ============================================================

@mcp.tool()
def retrieve_incident_memory(
    query: str,
    top_k: int = 3
) -> dict:
    """
    Search historical incident memory for similar previous incidents.

    Use this when current symptoms may match a known incident or when
    previous remediation guidance could help the investigation.

    The returned historical solution must be treated as evidence and
    guidance only. The agent must compare it with current telemetry
    before deciding whether it applies.

    Inputs:
        query: Description of the current symptoms or findings.
        top_k: Maximum number of historical incidents to return.
    """

    log_tool_call(
        "retrieve_incident_memory",
        f"query={query!r}, top_k={top_k}"
    )

    query_tokens = tokenize(query)

    ranked = []

    for incident in INCIDENTS:

        searchable_text = " ".join([
            incident["title"],
            " ".join(incident["symptoms"]),
            incident["root_cause"]
        ])

        incident_tokens = tokenize(searchable_text)

        overlap = query_tokens.intersection(incident_tokens)

        # Simple deterministic lexical retrieval score.
        score = (
            len(overlap) / len(query_tokens)
            if query_tokens
            else 0
        )

        ranked.append({
            "score": round(score, 3),
            "matched_terms": sorted(overlap),
            "incident": incident
        })

    ranked.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    safe_top_k = max(
        1,
        min(top_k, 3)
    )

    results = ranked[:safe_top_k]

    return {
        "query": query,
        "results": results
    }


# ============================================================
# START MCP SERVER
# ============================================================

if __name__ == "__main__":

    mcp.run(
        transport="stdio"
    )