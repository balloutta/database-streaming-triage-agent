import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_ollama import ChatOllama


# ============================================================
# MODEL CONFIGURATION
# ============================================================

MODEL_NAME = "gemma4:e4b"
MODEL_CONTEXT = 16384

SPECIALIST_MAX_OUTPUT = 900
VERIFIER_PHASE_MAX_OUTPUT = 1200


def make_llm(
    num_predict: int = SPECIALIST_MAX_OUTPUT
) -> ChatOllama:

    return ChatOllama(
        model=MODEL_NAME,
        temperature=0,
        num_ctx=MODEL_CONTEXT,
        num_predict=num_predict
    )


# ============================================================
# STRUCTURED MODELS
# ============================================================

class HealthAssessment(BaseModel):

    health_status: Literal[
        "healthy",
        "degraded",
        "critical"
    ]

    abnormal_signals: list[str]

    normal_signals: list[str]

    triage_summary: str

    confidence: Literal[
        "low",
        "medium",
        "high"
    ]


class StreamingInvestigationResult(BaseModel):

    streaming_finding: str

    evidence: list[str]

    cross_domain_finding: str

    recommended_next_agent: Literal[
        "database_agent",
        "infrastructure_agent",
        "verification_agent",
        "none"
    ]

    confidence: Literal[
        "low",
        "medium",
        "high"
    ]

    safety_note: str


class DatabaseInvestigationResult(BaseModel):

    database_finding: str

    evidence: list[str]

    streaming_hypothesis: Literal[
        "supported",
        "partially_supported",
        "not_supported",
        "not_applicable"
    ]

    historical_memory_lookup: Literal[
        "recommended",
        "not_required"
    ]

    recommended_next_agent: Literal[
        "verification_agent",
        "streaming_agent",
        "infrastructure_agent",
        "none"
    ]

    confidence: Literal[
        "low",
        "medium",
        "high"
    ]

    safety_note: str


class InfrastructureInvestigationResult(BaseModel):

    infrastructure_finding: str

    evidence: list[str]

    affected_components: list[str]

    primary_or_secondary: Literal[
        "primary",
        "secondary",
        "unclear"
    ]

    recommended_next_agent: Literal[
        "database_agent",
        "streaming_agent",
        "verification_agent",
        "none"
    ]

    confidence: Literal[
        "low",
        "medium",
        "high"
    ]

    safety_note: str


class SupervisorDecision(BaseModel):

    next_agent: Literal[
        "database_agent",
        "streaming_agent",
        "infrastructure_agent",
        "verification_agent"
    ]

    reason: str

    priority: Literal[
        "low",
        "medium",
        "high",
        "critical"
    ]


class MemoryQuery(BaseModel):

    query: str = Field(
        max_length=400
    )

    reason: str


# ============================================================
# FINAL REPORT
# ============================================================

class VerificationResult(BaseModel):

    verification_status: Literal[
        "verified",
        "partially_verified",
        "insufficient_evidence"
    ]

    final_root_cause: str

    supporting_evidence: list[str]

    secondary_observations: list[str]

    historical_match_found: bool

    historical_incident_id: str

    historical_incident_title: str

    historical_match_strength: Literal[
        "none",
        "weak",
        "moderate",
        "strong"
    ]

    matching_points: list[str]

    current_differences: list[str]

    historical_solution_applicability: Literal[
        "applicable_with_review",
        "partially_applicable",
        "not_applicable"
    ]

    applicability_reason: str

    recommended_actions: list[str]

    confidence: Literal[
        "low",
        "medium",
        "high"
    ]

    safety_note: str


# ============================================================
# INTERNAL VERIFICATION MODELS
# ============================================================

class VerificationCoreResult(BaseModel):

    verification_status: Literal[
        "verified",
        "partially_verified",
        "insufficient_evidence"
    ]

    final_root_cause: str

    supporting_evidence: list[str] = Field(
        max_length=4
    )

    secondary_observations: list[str] = Field(
        description=(
            "Abnormal observations outside the primary causal chain. "
            "Do not repeat supporting evidence or the root cause."
        ),
        max_length=3
    )

    confidence: Literal[
        "low",
        "medium",
        "high"
    ]

    safety_note: str


class HistoricalAssessmentResult(BaseModel):

    historical_match_found: bool

    historical_incident_id: str

    historical_incident_title: str

    historical_match_strength: Literal[
        "none",
        "weak",
        "moderate",
        "strong"
    ]

    matching_points: list[str] = Field(
        max_length=4
    )

    current_differences: list[str] = Field(
        max_length=3
    )

    historical_solution_applicability: Literal[
        "applicable_with_review",
        "partially_applicable",
        "not_applicable"
    ]

    applicability_reason: str

    recommended_actions: list[str] = Field(
        max_length=4
    )


# ============================================================
# SYSTEM PROMPTS
# ============================================================

HEALTH_SYSTEM_PROMPT = """
You are the Health and Anomaly Detection Agent in a multi-agent
database and streaming incident-triage system.

You perform initial screening only.

You MUST call check_health_summary exactly once.

Responsibilities:
- identify abnormal operational signals,
- identify useful healthy signals,
- summarize current system health,
- do NOT identify a final root cause,
- do NOT choose the next specialist.

SEVERITY RULE:

If any anomaly has severity "critical":
health_status = "critical"

Otherwise, if one or more anomalies exist:
health_status = "degraded"

If no anomalies exist:
health_status = "healthy"

Rules:

1. Use only monitoring evidence.
2. Never invent values.
3. Do not perform remediation.
4. Do not restart services.
5. Do not modify production.
6. Keep the result concise.
7. Do not reveal private chain-of-thought.

Return the validated HealthAssessment structure.
"""


STREAMING_SYSTEM_PROMPT = """
You are the Streaming Investigation Agent in a multi-agent
database and streaming incident-triage system.

Your domain is:
- Kafka consumer lag,
- Kafka processing behavior,
- Debezium connector health,
- streaming-consumer logs.

Rules:

1. Gather evidence using the available MCP tools.
2. Do not assume the Health Agent's interpretation is correct.
3. Do not invent telemetry.
4. Stop when enough evidence exists.
5. Avoid duplicate tool calls.
6. If evidence points to another subsystem, request that specialist.
7. Do not restart services.
8. Do not change configuration.
9. Do not claim a production action was executed.
10. Keep findings concise.
11. Do not reveal private chain-of-thought.

Return StreamingInvestigationResult.
"""


DATABASE_SYSTEM_PROMPT = """
You are the Database Investigation Agent in a multi-agent
database and streaming incident-triage system.

Your domain is:
- MariaDB replication,
- database connection utilization,
- database connection errors,
- MariaDB operational logs.

Rules:

1. Gather database evidence before concluding.
2. Findings from another agent are hypotheses.
3. Do not invent metrics.
4. Avoid duplicate monitoring calls.
5. Distinguish primary and secondary conditions.
6. Do not modify data.
7. Do not restart replication.
8. Do not change max_connections.
9. Do not kill sessions.
10. Do not change production configuration.
11. Keep the result concise.
12. Do not reveal private chain-of-thought.

Historical retrieval occurs later for every incident.

Return DatabaseInvestigationResult.
"""


INFRASTRUCTURE_SYSTEM_PROMPT = """
You are the Infrastructure Investigation Agent in a multi-agent
database and streaming incident-triage system.

Your domain is:
- CPU,
- memory,
- filesystem utilization,
- network health,
- operating-system service state,
- infrastructure-related logs.

Rules:

1. Gather evidence using available monitoring tools.
2. Do not invent metrics.
3. Inspect relevant logs when useful.
4. Distinguish a primary infrastructure cause from a secondary warning.
5. Do not delete files.
6. Do not restart services.
7. Do not change operating-system configuration.
8. Do not execute remediation.
9. If evidence points elsewhere, recommend that specialist.
10. Avoid repeated tool calls.
11. Keep the result concise.
12. Do not reveal private chain-of-thought.

Return InfrastructureInvestigationResult.
"""


# ============================================================
# HELPERS
# ============================================================

def select_tools(
    all_tools: list[Any],
    allowed_names: set[str]
) -> list[Any]:

    selected = [
        tool
        for tool in all_tools
        if tool.name in allowed_names
    ]

    found = {
        tool.name
        for tool in selected
    }

    missing = (
        allowed_names
        - found
    )

    if missing:

        raise RuntimeError(
            "Required MCP tools were not discovered: "
            + ", ".join(
                sorted(
                    missing
                )
            )
        )

    return selected


def compact_json(
    value: Any
) -> str:

    if isinstance(
        value,
        BaseModel
    ):

        value = value.model_dump()

    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":")
    )


def extract_trace(
    messages: list[Any],
    agent_name: str,
    structured_tool_name: str
) -> list[dict]:

    events = []

    for message in messages:

        class_name = type(
            message
        ).__name__

        if class_name == "AIMessage":

            tool_calls = getattr(
                message,
                "tool_calls",
                None
            )

            if not tool_calls:
                continue

            for call in tool_calls:

                if (
                    call["name"]
                    == structured_tool_name
                ):
                    continue

                events.append(
                    {
                        "type": "tool_call",
                        "agent": agent_name,
                        "tool": call["name"],
                        "arguments": call["args"]
                    }
                )

        elif class_name == "ToolMessage":

            tool_name = getattr(
                message,
                "name",
                "unknown"
            )

            if (
                tool_name
                == structured_tool_name
            ):
                continue

            content = str(
                message.content
            )

            if len(content) > 2500:

                content = (
                    content[:2500]
                    + "... [trace truncated]"
                )

            events.append(
                {
                    "type": "tool_result",
                    "agent": agent_name,
                    "tool": tool_name,
                    "result": content
                }
            )

    return events


# ============================================================
# MCP TOOL AGENT
#
# Primary path:
#   ReAct agent uses MCP tools and returns validated structure.
#
# Fallback path:
#   If the tool investigation completes but LangChain does not
#   produce structured_response, DO NOT rerun the tools.
#
#   Instead:
#   - preserve the actual MCP observations,
#   - preserve the model's final textual finding if available,
#   - perform one bounded structured synthesis using only that
#     evidence.
#
# This avoids wasting several minutes repeating the same MCP
# investigation simply because the final formatting step failed.
# ============================================================

async def invoke_tool_agent(
    *,
    agent_name: str,
    llm: ChatOllama,
    tools: list[Any],
    system_prompt: str,
    schema: type[BaseModel],
    request: str
) -> tuple[BaseModel, list[dict]]:

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,

        response_format=ToolStrategy(
            schema=schema,

            handle_errors=(
                "Your structured response was incomplete or invalid. "
                "Return every required field according to the schema. "
                "Keep the response concise."
            )
        )
    )


    # ========================================================
    # RUN TOOL INVESTIGATION
    #
    # No wall-clock timeout.
    # ========================================================

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": request
                }
            ]
        },

        config={
            # Logical ReAct/tool-loop protection only.
            "recursion_limit": 12
        }
    )


    messages = result.get(
        "messages",
        []
    )


    # ========================================================
    # ALWAYS EXTRACT MCP TRACE
    #
    # Even if structured output failed, we preserve the actual
    # tool calls and observations.
    # ========================================================

    trace = extract_trace(
        messages=messages,
        agent_name=agent_name,
        structured_tool_name=schema.__name__
    )


    # ========================================================
    # NORMAL SUCCESS PATH
    # ========================================================

    structured = result.get(
        "structured_response"
    )


    if structured is not None:

        return (
            structured,
            trace
        )


    # ========================================================
    # STRUCTURED OUTPUT WAS MISSING
    #
    # Gather the evidence already produced during the tool run.
    # We do NOT execute the MCP tools again.
    # ========================================================

    tool_evidence = []


    for event in trace:

        if (
            event.get(
                "type"
            )
            == "tool_result"
        ):

            tool_evidence.append(
                {
                    "tool":
                        event.get(
                            "tool"
                        ),

                    "result":
                        event.get(
                            "result"
                        )
                }
            )


    # ========================================================
    # CAPTURE FINAL MODEL TEXT IF AVAILABLE
    #
    # This is optional supporting context.
    # Actual MCP observations remain the authoritative evidence.
    # ========================================================

    final_text = ""


    for message in reversed(
        messages
    ):

        if (
            type(message).__name__
            != "AIMessage"
        ):

            continue


        content = getattr(
            message,
            "content",
            ""
        )


        if isinstance(
            content,
            str
        ):

            candidate = (
                content.strip()
            )


        elif isinstance(
            content,
            list
        ):

            pieces = []


            for item in content:

                if isinstance(
                    item,
                    dict
                ):

                    text_value = item.get(
                        "text",
                        ""
                    )


                    if text_value:

                        pieces.append(
                            str(
                                text_value
                            )
                        )

                else:

                    pieces.append(
                        str(
                            item
                        )
                    )


            candidate = " ".join(
                pieces
            ).strip()


        else:

            candidate = str(
                content
            ).strip()


        if candidate:

            final_text = (
                candidate[
                    :1500
                ]
            )

            break


    # ========================================================
    # REQUIRE ACTUAL TOOL EVIDENCE
    #
    # If the agent returned neither a structure nor tool
    # observations, then this was a genuine investigation
    # failure and must not be disguised as success.
    # ========================================================

    if not tool_evidence:

        raise RuntimeError(
            f"{agent_name} did not return a validated structured "
            "response and produced no usable MCP observations."
        )


    # ========================================================
    # FALLBACK STRUCTURED SYNTHESIS
    #
    # This call receives ONLY:
    # - the original investigation request,
    # - MCP observations already gathered,
    # - optional final textual summary.
    #
    # It cannot call tools and cannot invent new telemetry.
    # ========================================================

    synthesis_package = {

        "original_investigation_request":
            request,

        "mcp_observations":
            tool_evidence,

        "agent_final_text":
            final_text
    }


    synthesis_request = f"""
The operational investigation already completed its MCP tool calls,
but the final structured formatting step was missing.

DO NOT perform another investigation.

Use ONLY the evidence below to construct the required structured result.

EVIDENCE PACKAGE:

{compact_json(synthesis_package)}

Rules:

1. MCP observations are authoritative.

2. Do not invent telemetry, log lines, service states, errors,
   or metrics.

3. The previous agent text is only a draft interpretation.
   Validate it against the MCP observations.

4. Preserve the read-only safety boundary.

5. Keep every field concise.

6. Return every field required by {schema.__name__}.

7. Do not reveal private chain-of-thought.
"""


    synthesis_system_prompt = f"""
You are completing the structured output for {agent_name}.

The MCP investigation has already happened.

Your task is formatting and evidence-based synthesis only.

Use only the supplied MCP observations.
Do not call tools.
Do not invent evidence.
Do not execute remediation.

Return a complete {schema.__name__}.
"""


    try:

        structured = await invoke_structured_only(

            agent_name=(
                f"{agent_name}_structured_synthesis"
            ),

            llm=make_llm(
                num_predict=SPECIALIST_MAX_OUTPUT
            ),

            system_prompt=(
                synthesis_system_prompt
            ),

            schema=schema,

            request=(
                synthesis_request
            )
        )


    except Exception as exc:

        raise RuntimeError(
            f"{agent_name} completed MCP investigation but its "
            "structured result could not be recovered from the "
            f"collected evidence. Recovery error: {exc}"
        ) from exc


    # ========================================================
    # RECORD THAT FALLBACK WAS USED
    # ========================================================

    trace.append(
        {
            "type":
                "agent",

            "agent":
                agent_name,

            "message":
                (
                    "The MCP investigation completed, but the initial "
                    "structured result was missing. The existing MCP "
                    "evidence was converted into the required structure "
                    "without rerunning monitoring tools."
                )
        }
    )


    return (
        structured,
        trace
    )


# ============================================================
# STRUCTURED-ONLY CALL
# ============================================================

async def invoke_structured_only(
    *,
    agent_name: str,
    llm: ChatOllama,
    system_prompt: str,
    schema: type[BaseModel],
    request: str
) -> BaseModel:

    MAX_ATTEMPTS = 3

    structured_llm = (
        llm.with_structured_output(
            schema,
            include_raw=True
        )
    )

    required_fields = ", ".join(
        schema.model_fields.keys()
    )

    correction = ""
    last_error = None

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1
    ):

        current_request = request

        if correction:

            current_request += f"""

CORRECTION FROM PREVIOUS ATTEMPT:

{correction}

Return the COMPLETE structure again.

Required fields:
{required_fields}

Keep every field concise.
Do not omit fields.
"""

        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": current_request
            }
        ]

        try:

            response = await structured_llm.ainvoke(
                messages
            )

        except Exception as exc:

            last_error = exc

            correction = (
                "The previous response failed to parse. "
                "Return a shorter complete structured response. "
                f"Error: {str(exc)[:700]}"
            )

            continue

        if isinstance(
            response,
            dict
        ):

            parsed = response.get(
                "parsed"
            )

            parsing_error = response.get(
                "parsing_error"
            )

            raw = response.get(
                "raw"
            )

        else:

            parsed = response
            parsing_error = None
            raw = None

        if parsed is not None:

            return parsed

        last_error = parsing_error

        raw_preview = ""

        if raw is not None:

            raw_content = getattr(
                raw,
                "content",
                ""
            )

            raw_tool_calls = getattr(
                raw,
                "tool_calls",
                None
            )

            if raw_content:

                raw_preview = str(
                    raw_content
                )[:500]

            elif raw_tool_calls:

                raw_preview = str(
                    raw_tool_calls
                )[:700]

        correction = (
            "The previous response was incomplete or invalid. "
            "Use shorter sentences and return every required field."
        )

        if parsing_error:

            correction += (
                "\nValidation error: "
                + str(
                    parsing_error
                )[:700]
            )

        if raw_preview:

            correction += (
                "\nPrevious output started with: "
                + raw_preview
            )

    raise RuntimeError(
        f"{agent_name} failed to produce a complete "
        f"{schema.__name__} after {MAX_ATTEMPTS} attempts. "
        f"Last error: {last_error}"
    )


# ============================================================
# HEALTH AGENT
# ============================================================

async def run_health_agent(
    *,
    scenario_id: str,
    user_report: str,
    all_tools: list[Any]
) -> tuple[
    HealthAssessment,
    list[dict]
]:

    tools = select_tools(
        all_tools,
        {
            "check_health_summary"
        }
    )

    request = f"""
INCIDENT:
{user_report}

Use scenario_id "{scenario_id}" when calling check_health_summary.

Perform initial health screening.

Call check_health_summary exactly once.

Do not diagnose the final root cause.
"""

    return await invoke_tool_agent(
        agent_name="health_agent",
        llm=make_llm(),
        tools=tools,
        system_prompt=HEALTH_SYSTEM_PROMPT,
        schema=HealthAssessment,
        request=request
    )


# ============================================================
# STREAMING AGENT
# ============================================================

async def run_streaming_agent(
    *,
    scenario_id: str,
    user_report: str,
    evidence_context: dict,
    all_tools: list[Any]
) -> tuple[
    StreamingInvestigationResult,
    list[dict]
]:

    tools = select_tools(
        all_tools,
        {
            "check_kafka_lag",
            "check_debezium",
            "read_logs"
        }
    )

    request = f"""
INCIDENT:
{user_report}

CURRENT EVIDENCE:
{compact_json(evidence_context)}

Use scenario_id "{scenario_id}" for monitoring tool calls.

Investigate the streaming subsystem.

Determine:
- whether streaming behavior contributes,
- what evidence supports the finding,
- whether another subsystem should be investigated,
- which specialist should receive the incident next.

Return all required fields.
"""

    return await invoke_tool_agent(
        agent_name="streaming_agent",
        llm=make_llm(),
        tools=tools,
        system_prompt=STREAMING_SYSTEM_PROMPT,
        schema=StreamingInvestigationResult,
        request=request
    )


# ============================================================
# DATABASE AGENT
# ============================================================

async def run_database_agent(
    *,
    scenario_id: str,
    user_report: str,
    evidence_context: dict,
    all_tools: list[Any]
) -> tuple[
    DatabaseInvestigationResult,
    list[dict]
]:

    tools = select_tools(
        all_tools,
        {
            "check_replication_status",
            "check_database_connections",
            "read_logs"
        }
    )

    request = f"""
INCIDENT:
{user_report}

CURRENT EVIDENCE:
{compact_json(evidence_context)}

Use scenario_id "{scenario_id}" for monitoring tool calls.

Investigate the database subsystem.

Determine:
- whether replication contributes,
- whether database connections contribute,
- what evidence supports or rejects current hypotheses,
- which specialist should investigate next.

Historical retrieval occurs later for every incident.

Return all required fields.
"""

    return await invoke_tool_agent(
        agent_name="database_agent",
        llm=make_llm(),
        tools=tools,
        system_prompt=DATABASE_SYSTEM_PROMPT,
        schema=DatabaseInvestigationResult,
        request=request
    )


# ============================================================
# INFRASTRUCTURE AGENT
# ============================================================

async def run_infrastructure_agent(
    *,
    scenario_id: str,
    user_report: str,
    evidence_context: dict,
    all_tools: list[Any]
) -> tuple[
    InfrastructureInvestigationResult,
    list[dict]
]:

    tools = select_tools(
        all_tools,
        {
            "check_server_metrics",
            "read_logs"
        }
    )

    request = f"""
INCIDENT:
{user_report}

CURRENT EVIDENCE:
{compact_json(evidence_context)}

Use scenario_id "{scenario_id}" for monitoring calls.

Investigate the infrastructure subsystem.

Determine:
- whether resource exhaustion or service state explains the incident,
- what evidence supports the finding,
- whether the condition is primary or secondary,
- whether another specialist should investigate.

Return all required fields.
"""

    return await invoke_tool_agent(
        agent_name="infrastructure_agent",
        llm=make_llm(),
        tools=tools,
        system_prompt=INFRASTRUCTURE_SYSTEM_PROMPT,
        schema=InfrastructureInvestigationResult,
        request=request
    )


# ============================================================
# SUPERVISOR
#
# Plain-text routing is deliberate.
# JSON output is unnecessary for a four-way route decision.
# ============================================================

async def run_supervisor(
    *,
    user_report: str,
    health: HealthAssessment,
    specialist_findings: list[dict],
    visited_agents: list[str]
) -> SupervisorDecision:

    llm = make_llm(
        num_predict=160
    )

    state_for_supervisor = {

        "health": {
            "status":
                health.health_status,

            "abnormal_signals":
                health.abnormal_signals,

            "normal_signals":
                health.normal_signals
        },

        "specialist_findings":
            specialist_findings,

        "visited_agents":
            visited_agents
    }

    allowed_agents = {
        "database_agent",
        "streaming_agent",
        "infrastructure_agent",
        "verification_agent"
    }

    allowed_priorities = {
        "low",
        "medium",
        "high",
        "critical"
    }

    if (
        health.health_status
        == "critical"
    ):

        fallback_priority = (
            "critical"
        )

    elif (
        health.health_status
        == "degraded"
    ):

        fallback_priority = (
            "high"
        )

    else:

        fallback_priority = (
            "medium"
        )


    # ========================================================
    # GENERIC FALLBACK
    # ========================================================

    def deterministic_fallback() -> SupervisorDecision:

        if specialist_findings:

            latest = (
                specialist_findings[
                    -1
                ]
                .get(
                    "result",
                    {}
                )
            )

            recommended = (
                latest.get(
                    "recommended_next_agent"
                )
            )

            if (
                recommended
                in allowed_agents
            ):

                return SupervisorDecision(
                    next_agent=recommended,

                    reason=(
                        "Fallback routing used the most recent "
                        "specialist handoff because the Supervisor "
                        "did not return a usable routing format."
                    ),

                    priority=fallback_priority
                )

            return SupervisorDecision(
                next_agent="verification_agent",

                reason=(
                    "Fallback routing moved the collected specialist "
                    "evidence to verification because no usable "
                    "cross-domain handoff was available."
                ),

                priority=fallback_priority
            )

        signals = " ".join(
            health.abnormal_signals
        ).lower()

        database_score = sum(
            signals.count(word)
            for word in [
                "database",
                "mariadb",
                "replication",
                "connection",
                "sql"
            ]
        )

        streaming_score = sum(
            signals.count(word)
            for word in [
                "kafka",
                "consumer",
                "lag",
                "debezium",
                "stream"
            ]
        )

        infrastructure_score = sum(
            signals.count(word)
            for word in [
                "disk",
                "filesystem",
                "cpu",
                "memory",
                "service",
                "network",
                "space"
            ]
        )

        scores = {
            "database_agent":
                database_score,

            "streaming_agent":
                streaming_score,

            "infrastructure_agent":
                infrastructure_score
        }

        selected_agent = max(
            scores,
            key=scores.get
        )

        if (
            scores[
                selected_agent
            ]
            == 0
        ):

            selected_agent = (
                "verification_agent"
            )

        return SupervisorDecision(
            next_agent=selected_agent,

            reason=(
                "Fallback routing selected a domain from the "
                "current abnormal health signals because the "
                "Supervisor did not return a usable route."
            ),

            priority=fallback_priority
        )


    request = f"""
You are the Triage Supervisor for a database and streaming
incident investigation.

USER REPORT:

{user_report}

CURRENT EVIDENCE:

{compact_json(state_for_supervisor)}

Choose exactly ONE next agent:

database_agent
streaming_agent
infrastructure_agent
verification_agent

Routing rules:

- base the decision only on current evidence,
- never use scenario ID,
- follow unresolved evidence,
- follow useful cross-domain findings,
- avoid unnecessary repeated investigation,
- use verification_agent once enough evidence exists.

Return ONE short line:

AGENT|PRIORITY|REASON

Example:

streaming_agent|high|Kafka consumer lag is the strongest unresolved signal.

Do not return JSON.
Do not use markdown.
"""

    system_prompt = """
You are the Triage Supervisor.

Select the next investigation agent from current evidence.

Do not call tools.
Do not invent observations.
Do not route using scenario IDs.
Do not reveal private reasoning.

Return one compact routing line only.
"""

    for attempt in range(
        1,
        4
    ):

        current_request = (
            request
        )

        if (
            attempt
            > 1
        ):

            current_request += """

Your previous response could not be parsed.

Return only:

database_agent|high|short reason
streaming_agent|high|short reason
infrastructure_agent|high|short reason
verification_agent|high|short reason

Returning only the agent name is also accepted.
"""

        response = await llm.ainvoke(
            [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": current_request
                }
            ]
        )

        content = getattr(
            response,
            "content",
            ""
        )

        if isinstance(
            content,
            str
        ):

            raw_text = (
                content
            )

        elif isinstance(
            content,
            list
        ):

            pieces = []

            for item in content:

                if isinstance(
                    item,
                    dict
                ):

                    text_value = item.get(
                        "text",
                        ""
                    )

                    if text_value:

                        pieces.append(
                            str(
                                text_value
                            )
                        )

                else:

                    pieces.append(
                        str(
                            item
                        )
                    )

            raw_text = " ".join(
                pieces
            )

        else:

            raw_text = str(
                content
            )

        raw_text = (
            raw_text
            .replace(
                "```",
                ""
            )
            .strip()
        )

        normalized = (
            raw_text.lower()
        )

        selected_agent = None

        first_field = (
            normalized
            .split(
                "|",
                1
            )[0]
            .strip()
        )

        if (
            first_field
            in allowed_agents
        ):

            selected_agent = (
                first_field
            )

        else:

            for candidate in [
                "database_agent",
                "streaming_agent",
                "infrastructure_agent",
                "verification_agent"
            ]:

                if (
                    candidate
                    in normalized
                ):

                    selected_agent = (
                        candidate
                    )

                    break

        if (
            selected_agent
            is None
        ):

            continue

        selected_priority = (
            fallback_priority
        )

        parts = [
            item.strip()
            for item in raw_text.split(
                "|"
            )
        ]

        if (
            len(parts)
            >= 2
        ):

            possible_priority = (
                parts[
                    1
                ].lower()
            )

            if (
                possible_priority
                in allowed_priorities
            ):

                selected_priority = (
                    possible_priority
                )

        if (
            len(parts)
            >= 3
            and
            parts[2].strip()
        ):

            reason = (
                parts[
                    2
                ].strip()
            )

        else:

            reason = (
                "The Supervisor selected this agent from "
                "the current investigation evidence."
            )

        reason = (
            " ".join(
                reason.split()
            )[:500]
        )

        return SupervisorDecision(
            next_agent=selected_agent,
            reason=reason,
            priority=selected_priority
        )

    return deterministic_fallback()


# ============================================================
# DETERMINISTIC HISTORICAL QUERY
# ============================================================

async def build_memory_query(
    *,
    user_report: str,
    health: HealthAssessment,
    specialist_findings: list[dict]
) -> MemoryQuery:

    MAX_QUERY_LENGTH = 380

    evidence_parts = []
    seen = set()

    def add_evidence(
        value: str
    ) -> None:

        if not value:
            return

        cleaned = " ".join(
            str(value).split()
        ).strip()

        if not cleaned:
            return

        normalized = (
            cleaned.lower()
        )

        if normalized in seen:
            return

        seen.add(
            normalized
        )

        evidence_parts.append(
            cleaned
        )

    for signal in (
        health.abnormal_signals[:4]
    ):

        add_evidence(
            signal
        )

    for finding in (
        specialist_findings[-3:]
    ):

        result = finding.get(
            "result",
            {}
        )

        evidence = result.get(
            "evidence",
            []
        )

        for item in evidence[:4]:

            add_evidence(
                item
            )

    for signal in (
        health.normal_signals[:2]
    ):

        add_evidence(
            signal
        )

    if not evidence_parts:

        add_evidence(
            user_report
        )

    selected_parts = []
    current_length = 0

    for part in evidence_parts:

        separator_length = (
            3
            if selected_parts
            else 0
        )

        proposed_length = (
            current_length
            + separator_length
            + len(part)
        )

        if (
            proposed_length
            <= MAX_QUERY_LENGTH
        ):

            selected_parts.append(
                part
            )

            current_length = (
                proposed_length
            )

            continue

        if not selected_parts:

            selected_parts.append(
                part[
                    :MAX_QUERY_LENGTH
                ].rstrip()
            )

        break

    query = " | ".join(
        selected_parts
    ).strip()

    if not query:

        raise RuntimeError(
            "Historical memory query could not be built "
            "from current evidence."
        )

    return MemoryQuery(
        query=query,

        reason=(
            "Historical retrieval query built deterministically "
            "from current observed health and specialist evidence."
        )
    )


# ============================================================
# HISTORICAL MEMORY RETRIEVAL
# ============================================================

async def retrieve_history(
    *,
    memory_query: MemoryQuery,
    all_tools: list[Any]
) -> tuple[
    Any,
    list[dict]
]:

    tools = select_tools(
        all_tools,
        {
            "retrieve_incident_memory"
        }
    )

    tool = tools[0]

    arguments = {
        "query":
            memory_query.query,

        "top_k":
            3
    }

    result = await tool.ainvoke(
        arguments
    )

    result_text = str(
        result
    )

    trace_result = (
        result_text
    )

    if len(
        trace_result
    ) > 5000:

        trace_result = (
            trace_result[:5000]
            + "... [trace truncated]"
        )

    trace = [
        {
            "type": "tool_call",
            "agent": "verification_agent",
            "tool": "retrieve_incident_memory",
            "arguments": arguments
        },

        {
            "type": "tool_result",
            "agent": "verification_agent",
            "tool": "retrieve_incident_memory",
            "result": trace_result
        }
    ]

    return (
        result,
        trace
    )


# ============================================================
# TWO-PHASE FINAL VERIFICATION
# ============================================================

async def run_verification_agent(
    *,
    user_report: str,
    health: HealthAssessment,
    specialist_findings: list[dict],
    memory_query: MemoryQuery,
    memory_result: Any
) -> VerificationResult:


    # ========================================================
    # PHASE 1
    # CURRENT EVIDENCE
    # ========================================================

    current_evidence_package = {

        "user_report":
            user_report,

        "health_assessment":
            health.model_dump(),

        "specialist_findings":
            specialist_findings
    }


    core_request = f"""
CURRENT INCIDENT:

{compact_json(current_evidence_package)}

Verify the CURRENT incident only.

Tasks:

1. Determine the PRIMARY technical root cause supported by the
   strongest current causal evidence.

2. Treat every specialist conclusion as a hypothesis until supported
   by telemetry or logs.

3. Prefer direct causal evidence such as:
   - explicit error messages,
   - failed service/thread state,
   - resource-limit rejection,
   - logs showing why processing stopped or slowed.

4. Do NOT combine multiple abnormal conditions into one root cause
   unless current evidence shows that each condition participates in
   the same causal chain.

5. A warning-level metric must NOT be promoted to a primary cause
   merely because it is abnormal.

6. If one condition has direct causal evidence and another condition
   is only a warning with no associated failure evidence:
   - use the first as the primary root cause,
   - place the warning in secondary_observations.

7. Return maximum four strongest supporting evidence items.

8. supporting_evidence must directly support the primary causal chain.

9. A secondary observation must be:
   - abnormal,
   - relevant,
   - outside the primary causal chain.

10. Healthy states are NOT secondary abnormalities.
    Use healthy states only as supporting/exclusionary evidence when
    they help rule out competing causes.

11. Do NOT place the same fact in both supporting_evidence and
    secondary_observations.

12. Do NOT repeat the root cause as a secondary observation.

13. If there are no genuine secondary abnormalities,
    secondary_observations should be an empty list.

14. Do not discuss historical incidents in this phase.

15. Keep the answer concise.

Return every VerificationCoreResult field.
"""

    core = await invoke_structured_only(

        agent_name=(
            "verification_agent_current_evidence"
        ),

        llm=make_llm(
            num_predict=VERIFIER_PHASE_MAX_OUTPUT
        ),

        system_prompt="""
You are the current-evidence phase of the Verification Agent.

Identify one primary causal explanation from current telemetry and logs.

Direct causal evidence outranks generic warnings.

Do not promote an abnormal warning to a co-primary root cause unless
there is evidence connecting it to the failure.

Healthy states can rule out alternative causes but are not secondary
abnormalities.

Specialist conclusions are hypotheses, not facts.
Do not invent telemetry.
Do not execute remediation.
Do not reveal private chain-of-thought.
Keep the structured result concise.
""",

        schema=VerificationCoreResult,

        request=core_request
    )


    # ========================================================
    # PHASE 2
    # HISTORICAL COMPARISON
    # ========================================================

    historical_package = {

        "verified_current_incident": {

            "root_cause":
                core.final_root_cause,

            "supporting_evidence":
                core.supporting_evidence,

            "secondary_observations":
                core.secondary_observations,

            "confidence":
                core.confidence
        },

        "historical_query":
            memory_query.query,

        "historical_results":
            str(
                memory_result
            )
    }


    historical_request = f"""
COMPARE THE VERIFIED CURRENT INCIDENT WITH HISTORICAL MEMORY:

{compact_json(historical_package)}

Apply these match rules strictly.

MATCH STRENGTH RULES:

NONE
- no meaningful similarity.

WEAK
- similar symptoms or affected component,
- but the historical causal mechanism/root cause is NOT supported
  by current evidence.

MODERATE
- symptoms are similar,
- and there is some current evidence that the same causal mechanism
  may be involved,
- but the causal mechanism is not fully confirmed.

STRONG
- current evidence directly supports essentially the same causal
  mechanism or root cause as the historical incident.

IMPORTANT:

A shared symptom such as Kafka consumer lag, service degradation,
dashboard delay, or slow processing is NOT enough for a moderate
or strong match.

Root-cause similarity matters more than symptom similarity.

REMEDIATION APPLICABILITY RULES:

NOT_APPLICABLE
- historical root cause is absent from current evidence,
- or only symptoms overlap,
- or applying the historical fix would require assuming an
  unverified cause.

PARTIALLY_APPLICABLE
- part of the historical causal mechanism is supported by current
  evidence,
- but differences mean only some historical remediation applies.

APPLICABLE_WITH_REVIEW
- current evidence supports essentially the same causal mechanism,
- and the historical remediation directly addresses that mechanism,
- but production changes still require operator review.

Additional requirements:

1. Do NOT automatically accept the top retrieval result.

2. Do NOT increase match strength merely because many generic words
   overlap.

3. Explicitly identify important causal differences.

4. Do NOT recommend a historical remediation unless the current
   evidence independently supports the condition that remediation
   addresses.

5. Recommended actions should primarily follow from the verified
   CURRENT diagnosis.

6. If historical remediation is not applicable, do not include its
   specific remediation steps as recommendations merely because they
   appeared in memory.

7. Production changes require operator review and approval.

8. Return at most four concise recommendations.

9. Do not reveal private chain-of-thought.

If no meaningful historical match exists:

historical_match_found = false
historical_incident_id = "none"
historical_incident_title = "none"
historical_match_strength = "none"
historical_solution_applicability = "not_applicable"

Return every HistoricalAssessmentResult field.
"""


    history = await invoke_structured_only(

        agent_name=(
            "verification_agent_historical_comparison"
        ),

        llm=make_llm(
            num_predict=VERIFIER_PHASE_MAX_OUTPUT
        ),

        system_prompt="""
You are the historical-comparison phase of the Verification Agent.

Evaluate causal similarity, not merely symptom similarity.

A historical incident that shares only symptoms must be rated weak.

Moderate or strong matching requires current evidence supporting
the same causal mechanism.

If the historical root cause is absent from current evidence,
historical remediation should normally be not_applicable.

Never invent historical facts.
Never blindly reuse historical remediation.
Production changes require operator approval.
Keep the structured result concise.
Do not reveal private chain-of-thought.
""",

        schema=HistoricalAssessmentResult,

        request=historical_request
    )


    # ========================================================
    # FINAL ASSEMBLY
    # ========================================================

    return VerificationResult(

        verification_status=(
            core.verification_status
        ),

        final_root_cause=(
            core.final_root_cause
        ),

        supporting_evidence=(
            core.supporting_evidence
        ),

        secondary_observations=(
            core.secondary_observations
        ),

        historical_match_found=(
            history.historical_match_found
        ),

        historical_incident_id=(
            history.historical_incident_id
        ),

        historical_incident_title=(
            history.historical_incident_title
        ),

        historical_match_strength=(
            history.historical_match_strength
        ),

        matching_points=(
            history.matching_points
        ),

        current_differences=(
            history.current_differences
        ),

        historical_solution_applicability=(
            history.historical_solution_applicability
        ),

        applicability_reason=(
            history.applicability_reason
        ),

        recommended_actions=(
            history.recommended_actions
        ),

        confidence=(
            core.confidence
        ),

        safety_note=(
            core.safety_note
        )
    )