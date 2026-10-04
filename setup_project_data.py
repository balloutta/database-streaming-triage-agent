import json
from pathlib import Path


# ============================================================
# PROJECT DIRECTORIES
# ============================================================

BASE_DIR = Path.cwd()

DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"
EVALUATION_DIR = BASE_DIR / "evaluation"

DATA_DIR.mkdir(exist_ok=True)
CONFIG_DIR.mkdir(exist_ok=True)
EVALUATION_DIR.mkdir(exist_ok=True)


# ============================================================
# CONFIGURABLE HEALTH THRESHOLDS
# ============================================================

thresholds = {
    "replication_lag_warning_seconds": 60,

    "kafka_consumer_lag_warning": 10000,
    "kafka_consumer_lag_critical": 40000,

    "cpu_warning_percent": 85,
    "memory_warning_percent": 85,

    "disk_warning_percent": 85,
    "disk_critical_percent": 95,

    "database_connection_warning_percent": 90
}


# ============================================================
# FOUR INCIDENT SCENARIOS
# ============================================================

scenarios = {

    # --------------------------------------------------------
    # SCENARIO 1
    # Streaming problem
    # --------------------------------------------------------

    "scenario_1": {
        "name": "Kafka consumer slowdown",

        "user_report": (
            "The analytics dashboard has not updated for around "
            "20 minutes. Please investigate."
        ),

        "environment": "PROD",

        "replication": {
            "io_running": True,
            "sql_running": True,
            "lag_seconds": 0,
            "last_io_error": "",
            "last_sql_error": ""
        },

        "debezium": {
            "connector": "analytics-connector",
            "status": "RUNNING",
            "tasks_running": 1,
            "tasks_failed": 0,
            "last_error": ""
        },

        "kafka": {
            "consumer_group": "analytics-consumer",
            "lag": 24000,
            "trend": "increasing"
        },

        "database_connections": {
            "threads_connected": 32,
            "max_connections": 100,
            "connection_errors": 0
        },

        "server_metrics": {
            "host": "streaming-01",
            "cpu_percent": 31,
            "memory_percent": 52,
            "disk_percent": 64,
            "network_status": "NORMAL"
        },

        "services": {
            "analytics_consumer": "RUNNING",
            "kafka": "RUNNING",
            "mariadb": "RUNNING"
        },

        "logs": {
            "analytics_consumer": [
                "Consumer processing rate is below incoming message rate.",
                "Processing batch took 18.4 seconds.",
                "Processing batch took 19.1 seconds."
            ],
            "mariadb": [],
            "kafka": []
        }
    },


    # --------------------------------------------------------
    # SCENARIO 2
    # Database replication failure
    # --------------------------------------------------------

    "scenario_2": {
        "name": "MariaDB replication failure",

        "user_report": (
            "Data in the reporting system suddenly stopped refreshing. "
            "Please investigate."
        ),

        "environment": "PROD",

        "replication": {
            "io_running": True,
            "sql_running": False,
            "lag_seconds": None,
            "last_io_error": "",
            "last_sql_error": (
                "Duplicate entry '983421' for key 'PRIMARY' "
                "while applying relay log event."
            )
        },

        "debezium": {
            "connector": "analytics-connector",
            "status": "RUNNING",
            "tasks_running": 1,
            "tasks_failed": 0,
            "last_error": ""
        },

        "kafka": {
            "consumer_group": "analytics-consumer",
            "lag": 350,
            "trend": "stable"
        },

        "database_connections": {
            "threads_connected": 28,
            "max_connections": 100,
            "connection_errors": 0
        },

        "server_metrics": {
            "host": "database-01",
            "cpu_percent": 35,
            "memory_percent": 58,
            "disk_percent": 61,
            "network_status": "NORMAL"
        },

        "services": {
            "analytics_consumer": "RUNNING",
            "kafka": "RUNNING",
            "mariadb": "RUNNING"
        },

        "logs": {
            "analytics_consumer": [],
            "mariadb": [
                "Slave SQL thread stopped.",
                "Duplicate entry '983421' for key 'PRIMARY'.",
                "Error executing replicated transaction."
            ],
            "kafka": []
        }
    },


    # --------------------------------------------------------
    # SCENARIO 3
    # Infrastructure disk exhaustion
    # --------------------------------------------------------

    "scenario_3": {
        "name": "Infrastructure disk exhaustion",

        "user_report": (
            "The streaming service keeps stopping and the dashboard "
            "is delayed. Please investigate."
        ),

        "environment": "PROD",

        "replication": {
            "io_running": True,
            "sql_running": True,
            "lag_seconds": 0,
            "last_io_error": "",
            "last_sql_error": ""
        },

        "debezium": {
            "connector": "analytics-connector",
            "status": "RUNNING",
            "tasks_running": 1,
            "tasks_failed": 0,
            "last_error": ""
        },

        "kafka": {
            "consumer_group": "analytics-consumer",
            "lag": 6200,
            "trend": "increasing"
        },

        "database_connections": {
            "threads_connected": 34,
            "max_connections": 100,
            "connection_errors": 0
        },

        "server_metrics": {
            "host": "streaming-01",
            "cpu_percent": 43,
            "memory_percent": 61,
            "disk_percent": 97,
            "network_status": "NORMAL"
        },

        "services": {
            "analytics_consumer": "DEGRADED",
            "kafka": "RUNNING",
            "mariadb": "RUNNING"
        },

        "logs": {
            "analytics_consumer": [
                "No space left on device.",
                "Unable to write consumer state file.",
                "Service restarted after write failure."
            ],
            "mariadb": [],
            "kafka": [
                "Failed to write log segment: No space left on device."
            ]
        }
    },


    # --------------------------------------------------------
    # SCENARIO 4
    # Complex recurring incident
    # --------------------------------------------------------

    "scenario_4": {
        "name": "Recurring consumer backlog with DB connection exhaustion",

        "user_report": (
            "The dashboard is becoming increasingly delayed even though "
            "the main services appear to be running. Please investigate."
        ),

        "environment": "PROD",

        "replication": {
            "io_running": True,
            "sql_running": True,
            "lag_seconds": 0,
            "last_io_error": "",
            "last_sql_error": ""
        },

        "debezium": {
            "connector": "analytics-connector",
            "status": "RUNNING",
            "tasks_running": 1,
            "tasks_failed": 0,
            "last_error": ""
        },

        "kafka": {
            "consumer_group": "analytics-consumer",
            "lag": 52000,
            "trend": "rapidly_increasing"
        },

        "database_connections": {
            "threads_connected": 98,
            "max_connections": 100,
            "connection_errors": 37
        },

        "server_metrics": {
            "host": "streaming-01",
            "cpu_percent": 48,
            "memory_percent": 68,
            "disk_percent": 86,
            "network_status": "NORMAL"
        },

        "services": {
            "analytics_consumer": "RUNNING",
            "kafka": "RUNNING",
            "mariadb": "RUNNING"
        },

        "logs": {
            "analytics_consumer": [
                "Database connection timeout.",
                "Failed to obtain database connection from pool.",
                "Database connection timeout.",
                "Too many connections."
            ],
            "mariadb": [
                "Aborted connection: Too many connections.",
                "Connection rejected because connection limit was reached."
            ],
            "kafka": []
        }
    }
}


# ============================================================
# HISTORICAL INCIDENT MEMORY
#
# The agent CAN retrieve this information.
# It does NOT contain the answers to the current scenarios.
# ============================================================

historical_incidents = [

    {
        "incident_id": "INC-001",

        "title": "Replication stopped after duplicate-key error",

        "symptoms": [
            "reporting data stopped refreshing",
            "Slave_SQL_Running was No",
            "duplicate primary key error",
            "replication lag unavailable"
        ],

        "root_cause": (
            "The MariaDB SQL replication thread stopped while applying "
            "a transaction that conflicted with an existing row."
        ),

        "resolution": [
            "Review the conflicting transaction and affected row.",
            "Correct the data inconsistency using the approved DBA procedure.",
            "Resume replication only after the inconsistency is understood."
        ],

        "verification": [
            "Confirm Slave_IO_Running is Yes.",
            "Confirm Slave_SQL_Running is Yes.",
            "Confirm Seconds_Behind_Master returns to an expected value."
        ]
    },

    {
        "incident_id": "INC-002",

        "title": "Streaming service failure caused by full filesystem",

        "symptoms": [
            "streaming service repeatedly stopped",
            "disk usage above 95 percent",
            "No space left on device",
            "failed log writes"
        ],

        "root_cause": (
            "The streaming server filesystem became full and prevented "
            "the service from writing required files."
        ),

        "resolution": [
            "Identify which filesystem is full.",
            "Review logs and temporary files using the approved cleanup procedure.",
            "Restore sufficient free disk space.",
            "Restart the affected service only after operator approval."
        ],

        "verification": [
            "Confirm disk usage returned below the warning threshold.",
            "Confirm the service remains running.",
            "Confirm message processing resumes."
        ]
    },

    {
        "incident_id": "INC-003",

        "title": "Consumer backlog caused by database connection exhaustion",

        "symptoms": [
            "Kafka consumer lag increasing rapidly",
            "database connection timeout",
            "too many connections",
            "failed to obtain database connection",
            "replication healthy",
            "Debezium healthy"
        ],

        "root_cause": (
            "Consumer workers exhausted the available MariaDB connections. "
            "Messages accumulated in Kafka while workers waited for database "
            "connections."
        ),

        "resolution": [
            "Review the connection pool configured for each consumer worker.",
            "Reduce excessive per-worker database connection usage where appropriate.",
            "Review MariaDB max_connections against expected workload.",
            "Recycle affected consumers only after configuration review and operator approval."
        ],

        "verification": [
            "Confirm database connection utilization returns to a safe level.",
            "Confirm database timeout errors stop.",
            "Confirm Kafka consumer lag begins decreasing."
        ]
    },

    {
        "incident_id": "INC-004",

        "title": "Debezium connector task failure",

        "symptoms": [
            "connector not running",
            "failed Debezium task",
            "CDC events stopped",
            "Kafka consumer had no new events"
        ],

        "root_cause": (
            "The Debezium connector task failed and stopped publishing "
            "new change events."
        ),

        "resolution": [
            "Inspect the connector task error.",
            "Correct the underlying connector or source issue.",
            "Restart the connector only after operator approval."
        ],

        "verification": [
            "Confirm connector status is RUNNING.",
            "Confirm all tasks are RUNNING.",
            "Confirm new CDC events appear in Kafka."
        ]
    }
]


# ============================================================
# GROUND TRUTH
#
# IMPORTANT:
# This file is ONLY for evaluation.
# Agents must never read this file.
# ============================================================

ground_truth = {

    "scenario_1": {
        "expected_primary_agents": [
            "health_agent",
            "streaming_agent",
            "verification_agent"
        ],

        "expected_root_cause": (
            "Kafka consumer processing is falling behind the incoming "
            "message rate."
        ),

        "important_evidence": [
            "Kafka lag is 24000",
            "Kafka lag is increasing",
            "replication is healthy",
            "Debezium is healthy",
            "server resources are normal"
        ],

        "historical_memory_required": False
    },


    "scenario_2": {
        "expected_primary_agents": [
            "health_agent",
            "database_agent",
            "verification_agent"
        ],

        "expected_root_cause": (
            "MariaDB SQL replication stopped because of a duplicate-key "
            "error while applying a replicated transaction."
        ),

        "important_evidence": [
            "SQL replication thread is stopped",
            "IO replication thread is running",
            "duplicate entry error is present",
            "Kafka lag is normal"
        ],

        "historical_memory_required": False
    },


    "scenario_3": {
        "expected_primary_agents": [
            "health_agent",
            "infrastructure_agent",
            "verification_agent"
        ],

        "expected_root_cause": (
            "Disk exhaustion is disrupting the streaming service."
        ),

        "important_evidence": [
            "disk usage is 97 percent",
            "No space left on device appears in logs",
            "streaming service is degraded",
            "replication is healthy"
        ],

        "historical_memory_required": False
    },


    "scenario_4": {
        "expected_primary_agents": [
            "health_agent",
            "streaming_agent",
            "database_agent",
            "verification_agent"
        ],

        "expected_root_cause": (
            "Database connection exhaustion is slowing consumer processing "
            "and causing Kafka lag to grow."
        ),

        "important_evidence": [
            "Kafka lag is 52000 and rapidly increasing",
            "database connection timeouts are present",
            "threads_connected is 98 of 100",
            "too many connections errors are present",
            "replication is healthy",
            "Debezium is healthy"
        ],

        "historical_memory_required": True,

        "expected_memory_match": "INC-003",

        "historical_solution_expected_to_be_relevant": True,

        "important_difference": (
            "Current disk usage is 86 percent and should be monitored, "
            "but it does not by itself explain the database connection failures."
        )
    }
}


# ============================================================
# WRITE JSON FILES
# ============================================================

files_to_write = {
    CONFIG_DIR / "thresholds.json": thresholds,
    DATA_DIR / "scenarios.json": scenarios,
    DATA_DIR / "incidents.json": historical_incidents,
    EVALUATION_DIR / "ground_truth.json": ground_truth
}


for file_path, content in files_to_write.items():

    with open(file_path, "w", encoding="utf-8") as f:

        json.dump(
            content,
            f,
            indent=4,
            ensure_ascii=False
        )

    print(f"Created: {file_path}")


# ============================================================
# VERIFY
# ============================================================

print("\n" + "=" * 70)
print("PROJECT DATA CREATED")
print("=" * 70)

print("\nScenarios:", len(scenarios))
print("Historical incidents:", len(historical_incidents))

print("\nAvailable scenarios:")

for scenario_id, scenario in scenarios.items():

    print(
        f"  {scenario_id}: "
        f"{scenario['name']}"
    )

print("\nGround truth is stored separately under evaluation/")
print("and must NEVER be exposed to the agents.")