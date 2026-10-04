import asyncio
import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

MCP_SERVER = BASE_DIR / "mcp_server.py"
SCENARIOS_FILE = BASE_DIR / "data" / "scenarios.json"


# ============================================================
# LOAD ONLY USER-FACING SCENARIO INFORMATION
#
# This test never loads evaluation/ground_truth.json.
# ============================================================

with open(
    SCENARIOS_FILE,
    "r",
    encoding="utf-8"
) as f:
    SCENARIOS = json.load(f)


# ============================================================
# LOCAL OLLAMA MODEL
#
# Context/output limits are intentionally bounded.
# ============================================================

llm = ChatOllama(
    model="gemma4:e4b",
    temperature=0,
    num_ctx=16384,
    num_predict=900
)


# ============================================================
# HEALTH AGENT STRUCTURED RESULT
# ============================================================

class HealthAssessment(BaseModel):

    health_status: Literal[
        "healthy",
        "degraded",
        "critical"
    ]

    abnormal_signals: list[str] = Field(
        description=(
            "Abnormal operational observations obtained from "
            "the health monitoring tool."
        )
    )

    normal_signals: list[str] = Field(
        description=(
            "Important healthy observations useful for excluding "
            "possible causes."
        )
    )

    triage_summary: str = Field(
        description=(
            "Short evidence-based summary of current system health."
        )
    )

    confidence: Literal[
        "low",
        "medium",
        "high"
    ]


# ============================================================
# SUPERVISOR STRUCTURED DECISION
# ============================================================

class SupervisorDecision(BaseModel):

    next_agent: Literal[
        "database_agent",
        "streaming_agent",
        "infrastructure_agent",
        "verification_agent"
    ]

    reason: str = Field(
        description=(
            "Concise evidence-based reason for selecting the next agent. "
            "Do not provide private chain-of-thought."
        )
    )

    priority: Literal[
        "low",
        "medium",
        "high",
        "critical"
    ]


# ============================================================
# HEALTH AGENT PROMPT
# ============================================================

HEALTH_SYSTEM_PROMPT = """
You are the Health and Anomaly Detection Agent in a multi-agent
database and streaming incident-triage system.

Your job is initial screening only.

You MUST call check_health_summary exactly once before returning
your assessment.

Your responsibilities are:
- identify abnormal operational signals,
- identify important healthy signals,
- summarize system health,
- avoid diagnosing a final root cause.

RULES:

1. Use only evidence returned by the monitoring tool.
2. Do not invent metrics.
3. Do not recommend production changes.
4. Do not restart services.
5. Do not decide which specialist agent should run next.
6. Do not claim a final root cause.
7. Keep the result short because another agent will consume it.
8. Do not reveal private chain-of-thought.

Return the validated HealthAssessment structure.
"""


# ============================================================
# SUPERVISOR PROMPT
# ============================================================

SUPERVISOR_SYSTEM_PROMPT = """
You are the Triage Supervisor in a multi-agent database and
streaming incident-response system.

You do NOT call operational monitoring tools yourself.

You receive:
- the user's incident report,
- a structured health assessment from the Health Agent.

Your job is to select the specialist that should investigate NEXT.

Available specialists:

database_agent
    Investigates MariaDB replication, connection utilization,
    connection errors, and database logs.

streaming_agent
    Investigates Kafka consumer lag, Debezium, and streaming
    consumer logs.

infrastructure_agent
    Investigates CPU, memory, disk, network, service state,
    and infrastructure logs.

verification_agent
    Reviews evidence and performs historical-memory comparison
    before the final assessment.

ROUTING RULES:

1. Base your decision only on the incident and available evidence.
2. Do not use a predefined scenario-to-agent mapping.
3. Route to the specialist whose domain best explains the most
   important unresolved abnormal evidence.
4. Healthy components should reduce the need to investigate them
   unless another finding later contradicts that evidence.
5. A secondary warning should not automatically outrank a more
   severe or directly relevant abnormality.
6. Choose verification_agent only when specialist investigation
   is not needed before verification.
7. Keep the reason concise and evidence-based.
8. Do not reveal private chain-of-thought.
9. Do not execute or recommend production-changing actions.

Return only the validated SupervisorDecision structure.
"""


# ============================================================
# HEALTH TRACE
# ============================================================

def print_health_trace(messages):

    for message in messages:

        class_name = type(message).__name__

        if class_name == "AIMessage":

            tool_calls = getattr(
                message,
                "tool_calls",
                None
            )

            if tool_calls:

                for call in tool_calls:

                    # Hide the synthetic structured-output call.
                    if call["name"] == "HealthAssessment":
                        continue

                    print(
                        f"    Gemma selected MCP tool: "
                        f"{call['name']}"
                    )

                    print(
                        f"    Arguments: {call['args']}"
                    )

        elif class_name == "ToolMessage":

            tool_name = getattr(
                message,
                "name",
                "unknown"
            )

            if tool_name == "HealthAssessment":
                continue

            print(
                f"    MCP observation from {tool_name}:"
            )

            print(
                f"    {message.content}"
            )


# ============================================================
# RUN HEALTH AGENT
# ============================================================

async def run_health_agent(
    scenario_id: str,
    user_report: str,
    health_tool
) -> HealthAssessment:

    agent = create_agent(
        model=llm,
        tools=[health_tool],
        system_prompt=HEALTH_SYSTEM_PROMPT,
        response_format=ToolStrategy(
            schema=HealthAssessment,
            handle_errors=True
        )
    )

    request = f"""
INCIDENT ID:
{scenario_id}

USER REPORT:
{user_report}

Use scenario_id "{scenario_id}" when calling
check_health_summary.

Perform the initial health assessment.
"""

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": request
                }
            ]
        }
    )

    print_health_trace(
        result["messages"]
    )

    structured = result.get(
        "structured_response"
    )

    if structured is None:
        raise RuntimeError(
            "Health Agent failed to return a validated result."
        )

    return structured


# ============================================================
# RUN SUPERVISOR
# ============================================================

async def run_supervisor(
    scenario_id: str,
    user_report: str,
    health: HealthAssessment
) -> SupervisorDecision:

    supervisor = llm.with_structured_output(
        SupervisorDecision
    )

    health_json = json.dumps(
        health.model_dump(),
        indent=2
    )

    user_message = f"""
INCIDENT ID:
{scenario_id}

USER REPORT:
{user_report}

HEALTH AGENT ASSESSMENT:
{health_json}

Choose the specialist that should investigate next.
"""

    decision = await supervisor.ainvoke(
        [
            SystemMessage(
                content=SUPERVISOR_SYSTEM_PROMPT
            ),
            HumanMessage(
                content=user_message
            )
        ]
    )

    return decision


# ============================================================
# PRETTY SCENARIO OUTPUT
# ============================================================

def print_scenario_result(
    scenario_id: str,
    scenario_name: str,
    user_report: str,
    health: HealthAssessment,
    decision: SupervisorDecision
):

    print("\n" + "╔" + "═" * 68 + "╗")

    title = (
        f" {scenario_id.upper()} — {scenario_name} "
    )

    print(
        "║" + title.center(68) + "║"
    )

    print(
        "╚" + "═" * 68 + "╝"
    )

    print("\nUser Report")
    print("-" * 68)
    print(user_report)

    print("\nHealth Assessment")
    print("-" * 68)

    print(
        "Status:",
        health.health_status.upper()
    )

    print(
        "Confidence:",
        health.confidence.upper()
    )

    print("\nAbnormal signals:")

    if health.abnormal_signals:

        for signal in health.abnormal_signals:
            print(f"• {signal}")

    else:
        print("• None detected")

    print("\nImportant healthy signals:")

    if health.normal_signals:

        for signal in health.normal_signals:
            print(f"• {signal}")

    else:
        print("• None reported")

    print("\nHealth summary:")
    print(health.triage_summary)

    print("\nSupervisor Handoff")
    print("-" * 68)

    print(
        "Next agent:",
        decision.next_agent
        .replace("_", " ")
        .title()
    )

    print(
        "Priority:",
        decision.priority.upper()
    )

    print(
        "Reason:",
        decision.reason
    )


# ============================================================
# MAIN ROUTING TEST
# ============================================================

async def main():

    print(
        "╔" + "═" * 68 + "╗"
    )

    print(
        "║"
        + " HEALTH AGENT + SUPERVISOR ROUTING TEST ".center(68)
        + "║"
    )

    print(
        "╚" + "═" * 68 + "╝"
    )

    print(
        "\nThis test runs all four incidents."
    )

    print(
        "No ground-truth file is loaded by the agents."
    )


    # ========================================================
    # MCP CONNECTION
    # ========================================================

    client = MultiServerMCPClient(
        {
            "triage_tools": {
                "command": sys.executable,
                "args": [str(MCP_SERVER)],
                "transport": "stdio"
            }
        }
    )

    tools = await client.get_tools()

    tool_map = {
        tool.name: tool
        for tool in tools
    }


    # ========================================================
    # HEALTH AGENT GETS ONE TOOL ONLY
    # ========================================================

    if "check_health_summary" not in tool_map:

        raise RuntimeError(
            "MCP tool check_health_summary was not discovered."
        )

    health_tool = tool_map[
        "check_health_summary"
    ]


    # ========================================================
    # RUN ALL FOUR SCENARIOS
    # ========================================================

    routing_results = []

    for scenario_id, scenario in SCENARIOS.items():

        scenario_name = scenario["name"]
        user_report = scenario["user_report"]

        print(
            "\n\n"
            + "=" * 70
        )

        print(
            f"RUNNING {scenario_id}: {scenario_name}"
        )

        print(
            "=" * 70
        )

        print("\n[HEALTH AGENT]")

        health = await run_health_agent(
            scenario_id=scenario_id,
            user_report=user_report,
            health_tool=health_tool
        )

        print("\n[SUPERVISOR]")

        decision = await run_supervisor(
            scenario_id=scenario_id,
            user_report=user_report,
            health=health
        )

        print(
            "    Gemma selected:",
            decision.next_agent
        )

        print(
            "    Reason:",
            decision.reason
        )

        routing_results.append(
            {
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "next_agent": decision.next_agent,
                "priority": decision.priority
            }
        )

        print_scenario_result(
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            user_report=user_report,
            health=health,
            decision=decision
        )


    # ========================================================
    # SUMMARY
    # ========================================================

    print(
        "\n\n"
        + "╔"
        + "═" * 68
        + "╗"
    )

    print(
        "║"
        + " ROUTING SUMMARY ".center(68)
        + "║"
    )

    print(
        "╚"
        + "═" * 68
        + "╝"
    )

    for result in routing_results:

        print(
            f"\n{result['scenario_id']}: "
            f"{result['scenario_name']}"
        )

        print(
            "  →",
            result["next_agent"]
            .replace("_", " ")
            .title()
        )

        print(
            "  Priority:",
            result["priority"].upper()
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())