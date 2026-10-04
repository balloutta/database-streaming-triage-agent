import asyncio
import json
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from graph import run_triage


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

MCP_SERVER = (
    BASE_DIR
    / "mcp_server.py"
)

SCENARIOS_FILE = (
    BASE_DIR
    / "data"
    / "scenarios.json"
)


# ============================================================
# DISPLAY SETTINGS
# ============================================================

WIDTH = 72

PROGRESS_WIDTH = 118


# ============================================================
# LOAD SCENARIOS
# ============================================================

def load_scenarios() -> dict:

    with open(
        SCENARIOS_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(
            f
        )


SCENARIOS = load_scenarios()


# ============================================================
# FORMATTING
# ============================================================

def format_duration(
    seconds: float
) -> str:

    total_seconds = int(
        max(
            0,
            seconds
        )
    )

    hours = (
        total_seconds
        // 3600
    )

    minutes = (
        total_seconds
        % 3600
    ) // 60

    secs = (
        total_seconds
        % 60
    )

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{secs:02d}"
    )


def box_title(
    title: str
) -> None:

    print()

    print(
        "╔"
        + "═" * (WIDTH - 2)
        + "╗"
    )

    print(
        "║"
        + title.center(
            WIDTH - 2
        )
        + "║"
    )

    print(
        "╚"
        + "═" * (WIDTH - 2)
        + "╝"
    )


def section(
    title: str
) -> None:

    print()

    print(
        title
    )

    print(
        "-" * WIDTH
    )


def wrapped(
    text: str
) -> None:

    if not text:
        return

    print(
        textwrap.fill(
            str(text),
            width=WIDTH
        )
    )


def bullet(
    text: str
) -> None:

    wrapped(
        f"• {text}"
    )


def numbered(
    number: int,
    text: str
) -> None:

    prefix = (
        f"{number}. "
    )

    lines = textwrap.wrap(
        str(text),
        width=(
            WIDTH
            - len(prefix)
        )
    )

    if not lines:
        return

    print(
        prefix
        + lines[0]
    )

    for line in lines[1:]:

        print(
            " " * len(prefix)
            + line
        )


def pretty_agent_name(
    name: str
) -> str:

    labels = {
        "health_agent":
            "Health & Anomaly Agent",

        "streaming_agent":
            "Streaming Agent",

        "database_agent":
            "Database Agent",

        "infrastructure_agent":
            "Infrastructure Agent",

        "verification_agent":
            "Verification Agent",

        "supervisor":
            "Triage Supervisor"
    }

    return labels.get(
        name,

        name.replace(
            "_",
            " "
        ).title()
    )


# ============================================================
# LIVE PROGRESS DISPLAY
#
# No agent timeout.
#
# This simply updates once per second so a long local Ollama
# call does not appear frozen.
# ============================================================

class LiveProgress:

    def __init__(self):

        self.message = (
            "Preparing investigation..."
        )

        self.step_started = (
            time.perf_counter()
        )

        self.active = True


    def update(
        self,
        message: str
    ) -> None:

        self.message = message

        self.step_started = (
            time.perf_counter()
        )


    def render(self) -> None:

        elapsed = (
            time.perf_counter()
            - self.step_started
        )

        elapsed_text = (
            format_duration(
                elapsed
            )
        )

        text = (
            f"[Working {elapsed_text}] "
            f"{self.message}"
        )

        if len(text) > PROGRESS_WIDTH:

            text = (
                text[
                    :PROGRESS_WIDTH - 3
                ]
                + "..."
            )

        print(
            "\r"
            + text.ljust(
                PROGRESS_WIDTH
            ),

            end="",

            flush=True
        )


    async def run(self) -> None:

        while self.active:

            self.render()

            await asyncio.sleep(
                1
            )

        self.clear()


    def stop(self) -> None:

        self.active = False


    def clear(self) -> None:

        print(
            "\r"
            + (
                " "
                * PROGRESS_WIDTH
            )
            + "\r",

            end="",

            flush=True
        )


# ============================================================
# HEADER
# ============================================================

def show_header() -> None:

    print()

    print(
        "╔"
        + "═" * (WIDTH - 2)
        + "╗"
    )

    print(
        "║"
        + (
            " DATABASE & STREAMING "
            "INCIDENT TRIAGE SYSTEM "
        ).center(
            WIDTH - 2
        )
        + "║"
    )

    print(
        "╚"
        + "═" * (WIDTH - 2)
        + "╝"
    )

    print()

    print(
        "Local multi-agent incident investigation "
        "using Ollama, LangGraph and MCP."
    )

    print(
        "Operating mode: READ-ONLY diagnostic analysis"
    )


# ============================================================
# SCENARIO MENU
# ============================================================

def select_scenario() -> str | None:

    show_header()

    print()

    print(
        "Select an incident to simulate:"
    )

    print()

    scenario_ids = list(
        SCENARIOS.keys()
    )

    for index, scenario_id in enumerate(
        scenario_ids,
        start=1
    ):

        scenario = SCENARIOS[
            scenario_id
        ]

        print(
            f"  [{index}] "
            f"{scenario['name']}"
        )

    print()

    print(
        "  [Q] Quit"
    )

    print()

    while True:

        choice = input(
            "Selection: "
        ).strip().lower()

        if choice == "q":

            return None

        try:

            selected_index = (
                int(choice)
                - 1
            )

        except ValueError:

            print(
                "Please enter a valid menu number or Q."
            )

            continue

        if (
            0
            <= selected_index
            < len(
                scenario_ids
            )
        ):

            return scenario_ids[
                selected_index
            ]

        print(
            "Please select one of the available scenarios."
        )


# ============================================================
# INCIDENT START
# ============================================================

def show_starting_incident(
    scenario_id: str
) -> None:

    scenario = SCENARIOS[
        scenario_id
    ]

    box_title(
        "INCIDENT SELECTED"
    )

    print()

    print(
        f"Scenario:     "
        f"{scenario_id}"
    )

    print(
        f"Environment:  "
        f"{scenario['environment']}"
    )

    print(
        f"Simulation:   "
        f"{scenario['name']}"
    )

    section(
        "Reported Issue"
    )

    wrapped(
        scenario[
            "user_report"
        ]
    )

    print()

    print(
        "Starting multi-agent investigation..."
    )

    print()


# ============================================================
# INVESTIGATION PATH
# ============================================================

def extract_investigation_path(
    state: dict
) -> list[str]:

    path = [
        "Health & Anomaly Agent"
    ]

    for agent in state.get(
        "visited_agents",
        []
    ):

        path.append(
            pretty_agent_name(
                agent
            )
        )

    path.append(
        "Historical Incident Retrieval"
    )

    path.append(
        "Verification Agent"
    )

    return path


def show_investigation_path(
    state: dict
) -> None:

    section(
        "Investigation Path"
    )

    path = extract_investigation_path(
        state
    )

    for index, item in enumerate(
        path
    ):

        print(
            f"✓ {item}"
        )

        if (
            index
            < len(path) - 1
        ):

            print(
                "      ↓"
            )


# ============================================================
# FINAL REPORT
# ============================================================

def show_final_report(
    scenario_id: str,
    state: dict
) -> None:

    scenario = SCENARIOS[
        scenario_id
    ]

    report = state[
        "final_report"
    ]

    box_title(
        "INCIDENT TRIAGE FINAL REPORT"
    )


    section(
        "Incident"
    )

    print(
        f"Scenario:     "
        f"{scenario_id}"
    )

    print(
        f"Environment:  "
        f"{scenario['environment']}"
    )

    print(
        f"Simulation:   "
        f"{scenario['name']}"
    )

    print()

    wrapped(
        scenario[
            "user_report"
        ]
    )


    show_investigation_path(
        state
    )


    section(
        "Primary Finding"
    )

    wrapped(
        report.final_root_cause
    )


    section(
        "Key Evidence"
    )

    for item in (
        report.supporting_evidence
    ):

        bullet(
            item
        )


    if (
        report.secondary_observations
    ):

        section(
            "Secondary Observations"
        )

        for item in (
            report.secondary_observations
        ):

            bullet(
                item
            )


    section(
        "Historical Incident Comparison"
    )

    if (
        report.historical_match_found
    ):

        print(
            "Matched incident: "
            f"{report.historical_incident_id}"
        )

        if (
            report.historical_incident_title
            and
            report.historical_incident_title.lower()
            != "none"
        ):

            print(
                "Historical case: "
                f"{report.historical_incident_title}"
            )

        print(
            "Match strength:  "
            f"{report.historical_match_strength.upper()}"
        )

        if (
            report.matching_points
        ):

            print()

            print(
                "Matching observations:"
            )

            for item in (
                report.matching_points
            ):

                bullet(
                    item
                )

        if (
            report.current_differences
        ):

            print()

            print(
                "Current differences:"
            )

            for item in (
                report.current_differences
            ):

                bullet(
                    item
                )

    else:

        print(
            "No historical incident was sufficiently similar "
            "to establish a meaningful match."
        )

        print(
            "Match strength: "
            f"{report.historical_match_strength.upper()}"
        )


    section(
        "Historical Solution Assessment"
    )

    print(
        "Applicability: "
        + (
            report
            .historical_solution_applicability
            .replace(
                "_",
                " "
            )
            .upper()
        )
    )

    print()

    wrapped(
        report.applicability_reason
    )


    section(
        "Recommended Actions"
    )

    for index, action in enumerate(
        report.recommended_actions,
        start=1
    ):

        numbered(
            index,
            action
        )


    section(
        "Safety Status"
    )

    print(
        "✓ Read-only investigation"
    )

    print(
        "✓ No destructive MCP tools exposed"
    )

    print(
        "✓ No production changes executed"
    )

    print(
        "✓ No automatic service restart performed"
    )

    print()

    wrapped(
        report.safety_note
    )


    section(
        "Overall Assessment"
    )

    print(
        "Verification: "
        + (
            report
            .verification_status
            .replace(
                "_",
                " "
            )
            .upper()
        )
    )

    print(
        "Confidence:   "
        + report.confidence.upper()
    )


    if (
        "total_elapsed_seconds"
        in state
    ):

        print(
            "Total runtime: "
            + format_duration(
                state[
                    "total_elapsed_seconds"
                ]
            )
        )

    print()


# ============================================================
# DETAILED TRACE
# ============================================================

def show_trace(
    state: dict
) -> None:

    box_title(
        "DETAILED AGENT / MCP TRACE"
    )

    trace = state.get(
        "trace",
        []
    )

    if not trace:

        print()

        print(
            "No trace events were recorded."
        )

        return

    for index, event in enumerate(
        trace,
        start=1
    ):

        event_type = event.get(
            "type"
        )

        agent = event.get(
            "agent",
            "system"
        )

        display_agent = (
            pretty_agent_name(
                agent
            )
        )


        if event_type == "agent":

            print()

            print(
                f"[{index:02d}] "
                f"{display_agent}"
            )

            print(
                "     "
                + event.get(
                    "message",
                    ""
                )
            )


        elif event_type == "tool_call":

            print()

            print(
                f"[{index:02d}] "
                f"{display_agent}"
            )

            print(
                "     MCP tool selected: "
                f"{event.get('tool')}"
            )

            print(
                "     Arguments: "
                f"{event.get('arguments')}"
            )


        elif event_type == "tool_result":

            result = str(
                event.get(
                    "result",
                    ""
                )
            )

            result = " ".join(
                result.split()
            )

            if len(result) > 1200:

                result = (
                    result[:1200]
                    + "... [display truncated]"
                )

            print()

            print(
                f"[{index:02d}] "
                "MCP observation"
            )

            print(
                "     Tool: "
                f"{event.get('tool')}"
            )

            wrapped(
                "     "
                + result
            )


        elif event_type == "finding":

            finding = event.get(
                "finding",
                {}
            )

            print()

            print(
                f"[{index:02d}] "
                f"{display_agent} finding"
            )

            compact = json.dumps(
                finding,
                ensure_ascii=False,
                indent=2
            )

            print(
                textwrap.indent(
                    compact,
                    "     "
                )
            )


        elif (
            event_type
            == "supervisor_decision"
        ):

            print()

            print(
                f"[{index:02d}] "
                "Triage Supervisor"
            )

            print(
                "     Handoff → "
                + pretty_agent_name(
                    event.get(
                        "next_agent",
                        "unknown"
                    )
                )
            )

            print(
                "     Priority: "
                f"{str(event.get('priority', '')).upper()}"
            )

            wrapped(
                "     Reason: "
                + str(
                    event.get(
                        "reason",
                        ""
                    )
                )
            )


        elif (
            event_type
            == "memory_query"
        ):

            print()

            print(
                f"[{index:02d}] "
                "Historical Memory Query"
            )

            wrapped(
                "     Query: "
                + str(
                    event.get(
                        "query",
                        ""
                    )
                )
            )

            wrapped(
                "     Reason: "
                + str(
                    event.get(
                        "reason",
                        ""
                    )
                )
            )


        elif event_type == "timing":

            print()

            print(
                f"[{index:02d}] "
                f"{display_agent} runtime"
            )

            print(
                "     Operation: "
                f"{event.get('operation', '')}"
            )

            print(
                "     Duration: "
                + format_duration(
                    event.get(
                        "elapsed_seconds",
                        0
                    )
                )
            )


# ============================================================
# INVESTIGATE ONE SCENARIO
# ============================================================

async def investigate(
    scenario_id: str,
    all_tools: list[Any]
) -> dict:

    scenario = SCENARIOS[
        scenario_id
    ]

    show_starting_incident(
        scenario_id
    )

    progress = LiveProgress()

    progress_task = asyncio.create_task(
        progress.run()
    )

    total_started = (
        time.perf_counter()
    )

    try:

        state = await run_triage(
            scenario_id=scenario_id,

            user_report=scenario[
                "user_report"
            ],

            all_tools=all_tools,

            progress_callback=(
                progress.update
            )
        )

    except Exception as exc:

        progress.stop()

        await progress_task

        box_title(
            "INVESTIGATION ERROR"
        )

        print()

        wrapped(
            str(exc)
        )

        print()

        print(
            "The run was not accepted as complete."
        )

        print(
            "No partial result will be presented "
            "as a verified diagnosis."
        )

        raise


    total_elapsed = (
        time.perf_counter()
        - total_started
    )

    progress.stop()

    await progress_task

    state[
        "total_elapsed_seconds"
    ] = round(
        total_elapsed,
        2
    )

    show_final_report(
        scenario_id,
        state
    )

    return state


# ============================================================
# POST-RUN MENU
# ============================================================

def post_run_menu() -> str:

    print()

    print(
        "[D] Show detailed agent/MCP trace"
    )

    print(
        "[M] Return to scenario menu"
    )

    print(
        "[Q] Quit"
    )

    print()

    while True:

        choice = input(
            "Selection: "
        ).strip().lower()

        if choice in {
            "d",
            "m",
            "q"
        }:

            return choice

        print(
            "Please select D, M, or Q."
        )


# ============================================================
# APPLICATION
# ============================================================

async def main():

    if not MCP_SERVER.exists():

        raise FileNotFoundError(
            f"MCP server not found: "
            f"{MCP_SERVER}"
        )

    if not SCENARIOS_FILE.exists():

        raise FileNotFoundError(
            f"Scenario data not found: "
            f"{SCENARIOS_FILE}"
        )

    print()

    print(
        "Connecting to read-only MCP monitoring tools..."
    )

    client = MultiServerMCPClient(
        {
            "triage_tools": {
                "command":
                    sys.executable,

                "args": [
                    str(
                        MCP_SERVER
                    )
                ],

                "transport":
                    "stdio"
            }
        }
    )

    all_tools = await client.get_tools()

    tool_names = sorted(
        tool.name
        for tool in all_tools
    )

    print(
        f"Connected. "
        f"{len(all_tools)} MCP tools discovered."
    )

    expected_tools = {
        "check_health_summary",
        "check_replication_status",
        "check_database_connections",
        "check_debezium",
        "check_kafka_lag",
        "check_server_metrics",
        "read_logs",
        "retrieve_incident_memory"
    }

    missing = (
        expected_tools
        - set(
            tool_names
        )
    )

    if missing:

        raise RuntimeError(
            "Required MCP tools are missing: "
            + ", ".join(
                sorted(
                    missing
                )
            )
        )

    while True:

        scenario_id = (
            select_scenario()
        )

        if scenario_id is None:

            print()

            print(
                "Exiting incident triage system."
            )

            return

        state = await investigate(
            scenario_id,
            all_tools
        )

        while True:

            action = post_run_menu()

            if action == "d":

                show_trace(
                    state
                )

                continue

            if action == "m":

                break

            if action == "q":

                print()

                print(
                    "Exiting incident triage system."
                )

                return


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print()

        print(
            "Investigation interrupted by user."
        )

    except Exception as exc:

        print()

        print(
            "Fatal error:"
        )

        print(
            exc
        )

        sys.exit(
            1
        )