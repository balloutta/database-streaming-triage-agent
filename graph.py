import time
from typing import Any, TypedDict, Callable

from langgraph.graph import StateGraph, START, END

from agents import (
    HealthAssessment,
    SupervisorDecision,
    MemoryQuery,
    VerificationResult,
    run_health_agent,
    run_streaming_agent,
    run_database_agent,
    run_infrastructure_agent,
    run_supervisor,
    build_memory_query,
    retrieve_history,
    run_verification_agent,
)


# ============================================================
# LOGICAL WORKFLOW LIMIT
#
# This is NOT a time limit.
#
# A specialist can be repeated when useful, but this prevents
# an uncontrolled Supervisor -> Specialist loop.
# ============================================================

MAX_SPECIALIST_INVESTIGATIONS = 5


# ============================================================
# GRAPH STATE
# ============================================================

class TriageState(TypedDict, total=False):

    scenario_id: str
    user_report: str

    health: HealthAssessment

    specialist_findings: list[dict]
    visited_agents: list[str]

    supervisor_decision: SupervisorDecision
    next_agent: str

    specialist_count: int

    memory_query: MemoryQuery
    memory_result: Any

    final_report: VerificationResult

    trace: list[dict]


# ============================================================
# TRACE HELPERS
# ============================================================

def append_trace(
    state: TriageState,
    *events: dict
) -> list[dict]:

    existing = list(
        state.get(
            "trace",
            []
        )
    )

    existing.extend(
        events
    )

    return existing


def timing_event(
    *,
    agent: str,
    elapsed_seconds: float,
    operation: str
) -> dict:

    return {
        "type": "timing",
        "agent": agent,
        "operation": operation,
        "elapsed_seconds": round(
            elapsed_seconds,
            2
        )
    }


# ============================================================
# BUILD LANGGRAPH WORKFLOW
# ============================================================

def build_triage_graph(
    all_tools: list[Any],
    progress_callback: Callable[[str], None] | None = None
):

    # --------------------------------------------------------
    # DISPLAY-ONLY STATUS CALLBACK
    # --------------------------------------------------------

    def status(
        message: str
    ) -> None:

        if progress_callback is not None:

            progress_callback(
                message
            )


    workflow = StateGraph(
        TriageState
    )


    # ========================================================
    # HEALTH AGENT
    # ========================================================

    async def health_node(
        state: TriageState
    ) -> dict:

        status(
            "Health & Anomaly Agent is checking overall system health..."
        )

        started = time.perf_counter()


        health, tool_trace = (
            await run_health_agent(

                scenario_id=state[
                    "scenario_id"
                ],

                user_report=state[
                    "user_report"
                ],

                all_tools=all_tools
            )
        )


        elapsed = (
            time.perf_counter()
            - started
        )


        trace = append_trace(

            state,

            {
                "type": "agent",
                "agent": "health_agent",
                "message": (
                    "Initial operational health screening completed."
                )
            },

            *tool_trace,

            {
                "type": "finding",
                "agent": "health_agent",
                "finding": health.model_dump()
            },

            timing_event(
                agent="health_agent",
                elapsed_seconds=elapsed,
                operation="Initial health screening"
            )
        )


        return {

            "health":
                health,

            "specialist_findings":
                [],

            "visited_agents":
                [],

            "specialist_count":
                0,

            "trace":
                trace
        }


    # ========================================================
    # SUPERVISOR
    #
    # IMPORTANT COORDINATION RULE:
    #
    # LOW / MEDIUM confidence:
    #     Supervisor is free to repeat the same specialist or
    #     select another specialist.
    #
    # HIGH confidence + next = none:
    #     Go to verification.
    #
    # HIGH confidence + next = verification_agent:
    #     Go to verification.
    #
    # HIGH confidence + another specialist:
    #     Supervisor may follow the cross-domain handoff.
    #
    # Example:
    #
    # Infrastructure:
    #     confidence = high
    #     recommended_next_agent = none
    #
    # -> do NOT investigate Infrastructure repeatedly.
    # -> move to historical retrieval + verification.
    #
    # Streaming:
    #     confidence = high
    #     recommended_next_agent = database_agent
    #
    # -> cross-domain investigation remains valid.
    # ========================================================

    async def supervisor_node(
        state: TriageState
    ) -> dict:

        status(
            "Triage Supervisor is reviewing evidence and choosing the next agent..."
        )

        started = time.perf_counter()


        specialist_count = state.get(
            "specialist_count",
            0
        )


        specialist_findings = state.get(
            "specialist_findings",
            []
        )


        decision = None


        # ====================================================
        # HIGH-CONFIDENCE COMPLETION GUARD
        # ====================================================

        if specialist_findings:

            latest_finding = (
                specialist_findings[
                    -1
                ]
                .get(
                    "result",
                    {}
                )
            )


            latest_confidence = (
                str(
                    latest_finding.get(
                        "confidence",
                        ""
                    )
                )
                .lower()
                .strip()
            )


            recommended_next = (
                latest_finding.get(
                    "recommended_next_agent"
                )
            )


            # ------------------------------------------------
            # High-confidence specialist has completed its
            # investigation and does not request another
            # specialist.
            #
            # There is no value in asking the same domain to
            # inspect static telemetry repeatedly.
            # ------------------------------------------------

            if (
                latest_confidence == "high"
                and
                recommended_next in {
                    "none",
                    "verification_agent"
                }
            ):

                decision = SupervisorDecision(

                    next_agent=(
                        "verification_agent"
                    ),

                    reason=(
                        "The most recent specialist reached a "
                        "high-confidence conclusion and reported "
                        "that no additional specialist investigation "
                        "is required. The collected evidence is "
                        "ready for verification."
                    ),

                    priority="high"
                )


        # ====================================================
        # HARD LOOP PROTECTION
        #
        # This is an engineering safeguard only.
        # It does NOT decide the diagnosis.
        # ====================================================

        if (
            decision is None
            and
            specialist_count
            >= MAX_SPECIALIST_INVESTIGATIONS
        ):

            decision = SupervisorDecision(

                next_agent=(
                    "verification_agent"
                ),

                reason=(
                    "The specialist investigation limit was reached. "
                    "The collected evidence will now be verified."
                ),

                priority="high"
            )


        # ====================================================
        # NORMAL LLM SUPERVISOR
        #
        # Used when:
        #
        # - no specialist has investigated yet,
        # - confidence is low,
        # - confidence is medium,
        # - high-confidence evidence recommends another
        #   specialist.
        # ====================================================

        if decision is None:

            decision = await run_supervisor(

                user_report=state[
                    "user_report"
                ],

                health=state[
                    "health"
                ],

                specialist_findings=(
                    specialist_findings
                ),

                visited_agents=state.get(
                    "visited_agents",
                    []
                )
            )


        elapsed = (
            time.perf_counter()
            - started
        )


        trace = append_trace(

            state,

            {
                "type":
                    "supervisor_decision",

                "agent":
                    "supervisor",

                "next_agent":
                    decision.next_agent,

                "priority":
                    decision.priority,

                "reason":
                    decision.reason
            },

            timing_event(
                agent="supervisor",
                elapsed_seconds=elapsed,
                operation="Routing decision"
            )
        )


        return {

            "supervisor_decision":
                decision,

            "next_agent":
                decision.next_agent,

            "trace":
                trace
        }


    # ========================================================
    # STREAMING AGENT
    # ========================================================

    async def streaming_node(
        state: TriageState
    ) -> dict:

        status(
            "Streaming Agent is investigating Kafka, Debezium and consumer behavior..."
        )

        started = time.perf_counter()


        evidence_context = {

            "health":
                state[
                    "health"
                ].model_dump(),

            "previous_specialist_findings":
                state.get(
                    "specialist_findings",
                    []
                )
        }


        result, tool_trace = (
            await run_streaming_agent(

                scenario_id=state[
                    "scenario_id"
                ],

                user_report=state[
                    "user_report"
                ],

                evidence_context=evidence_context,

                all_tools=all_tools
            )
        )


        elapsed = (
            time.perf_counter()
            - started
        )


        finding = {

            "agent":
                "streaming_agent",

            "result":
                result.model_dump()
        }


        findings = list(
            state.get(
                "specialist_findings",
                []
            )
        )

        findings.append(
            finding
        )


        visited = list(
            state.get(
                "visited_agents",
                []
            )
        )

        visited.append(
            "streaming_agent"
        )


        trace = append_trace(

            state,

            {
                "type":
                    "agent",

                "agent":
                    "streaming_agent",

                "message":
                    "Streaming investigation completed."
            },

            *tool_trace,

            {
                "type":
                    "finding",

                "agent":
                    "streaming_agent",

                "finding":
                    result.model_dump()
            },

            timing_event(
                agent="streaming_agent",
                elapsed_seconds=elapsed,
                operation="Streaming investigation"
            )
        )


        return {

            "specialist_findings":
                findings,

            "visited_agents":
                visited,

            "specialist_count":
                state.get(
                    "specialist_count",
                    0
                ) + 1,

            "trace":
                trace
        }


    # ========================================================
    # DATABASE AGENT
    # ========================================================

    async def database_node(
        state: TriageState
    ) -> dict:

        status(
            "Database Agent is investigating MariaDB and connection health..."
        )

        started = time.perf_counter()


        evidence_context = {

            "health":
                state[
                    "health"
                ].model_dump(),

            "previous_specialist_findings":
                state.get(
                    "specialist_findings",
                    []
                )
        }


        result, tool_trace = (
            await run_database_agent(

                scenario_id=state[
                    "scenario_id"
                ],

                user_report=state[
                    "user_report"
                ],

                evidence_context=evidence_context,

                all_tools=all_tools
            )
        )


        elapsed = (
            time.perf_counter()
            - started
        )


        finding = {

            "agent":
                "database_agent",

            "result":
                result.model_dump()
        }


        findings = list(
            state.get(
                "specialist_findings",
                []
            )
        )

        findings.append(
            finding
        )


        visited = list(
            state.get(
                "visited_agents",
                []
            )
        )

        visited.append(
            "database_agent"
        )


        trace = append_trace(

            state,

            {
                "type":
                    "agent",

                "agent":
                    "database_agent",

                "message":
                    "Database investigation completed."
            },

            *tool_trace,

            {
                "type":
                    "finding",

                "agent":
                    "database_agent",

                "finding":
                    result.model_dump()
            },

            timing_event(
                agent="database_agent",
                elapsed_seconds=elapsed,
                operation="Database investigation"
            )
        )


        return {

            "specialist_findings":
                findings,

            "visited_agents":
                visited,

            "specialist_count":
                state.get(
                    "specialist_count",
                    0
                ) + 1,

            "trace":
                trace
        }


    # ========================================================
    # INFRASTRUCTURE AGENT
    # ========================================================

    async def infrastructure_node(
        state: TriageState
    ) -> dict:

        status(
            "Infrastructure Agent is checking server resources and service health..."
        )

        started = time.perf_counter()


        evidence_context = {

            "health":
                state[
                    "health"
                ].model_dump(),

            "previous_specialist_findings":
                state.get(
                    "specialist_findings",
                    []
                )
        }


        result, tool_trace = (
            await run_infrastructure_agent(

                scenario_id=state[
                    "scenario_id"
                ],

                user_report=state[
                    "user_report"
                ],

                evidence_context=evidence_context,

                all_tools=all_tools
            )
        )


        elapsed = (
            time.perf_counter()
            - started
        )


        finding = {

            "agent":
                "infrastructure_agent",

            "result":
                result.model_dump()
        }


        findings = list(
            state.get(
                "specialist_findings",
                []
            )
        )

        findings.append(
            finding
        )


        visited = list(
            state.get(
                "visited_agents",
                []
            )
        )

        visited.append(
            "infrastructure_agent"
        )


        trace = append_trace(

            state,

            {
                "type":
                    "agent",

                "agent":
                    "infrastructure_agent",

                "message":
                    "Infrastructure investigation completed."
            },

            *tool_trace,

            {
                "type":
                    "finding",

                "agent":
                    "infrastructure_agent",

                "finding":
                    result.model_dump()
            },

            timing_event(
                agent="infrastructure_agent",
                elapsed_seconds=elapsed,
                operation="Infrastructure investigation"
            )
        )


        return {

            "specialist_findings":
                findings,

            "visited_agents":
                visited,

            "specialist_count":
                state.get(
                    "specialist_count",
                    0
                ) + 1,

            "trace":
                trace
        }


    # ========================================================
    # MANDATORY HISTORICAL MEMORY RETRIEVAL
    # ========================================================

    async def memory_node(
        state: TriageState
    ) -> dict:

        status(
            "Building and executing the historical incident search..."
        )

        started = time.perf_counter()


        memory_query = (
            await build_memory_query(

                user_report=state[
                    "user_report"
                ],

                health=state[
                    "health"
                ],

                specialist_findings=state.get(
                    "specialist_findings",
                    []
                )
            )
        )


        status(
            "Searching historical incident memory for similar cases..."
        )


        memory_result, memory_trace = (
            await retrieve_history(

                memory_query=memory_query,

                all_tools=all_tools
            )
        )


        elapsed = (
            time.perf_counter()
            - started
        )


        trace = append_trace(

            state,

            {
                "type":
                    "memory_query",

                "agent":
                    "verification_agent",

                "query":
                    memory_query.query,

                "reason":
                    memory_query.reason
            },

            *memory_trace,

            timing_event(
                agent="verification_agent",
                elapsed_seconds=elapsed,
                operation="Historical incident retrieval"
            )
        )


        return {

            "memory_query":
                memory_query,

            "memory_result":
                memory_result,

            "trace":
                trace
        }


    # ========================================================
    # FINAL VERIFICATION
    # ========================================================

    async def verification_node(
        state: TriageState
    ) -> dict:

        status(
            "Verification Agent is validating current evidence and historical matches..."
        )

        started = time.perf_counter()


        final_report = (
            await run_verification_agent(

                user_report=state[
                    "user_report"
                ],

                health=state[
                    "health"
                ],

                specialist_findings=state.get(
                    "specialist_findings",
                    []
                ),

                memory_query=state[
                    "memory_query"
                ],

                memory_result=state[
                    "memory_result"
                ]
            )
        )


        elapsed = (
            time.perf_counter()
            - started
        )


        trace = append_trace(

            state,

            {
                "type":
                    "finding",

                "agent":
                    "verification_agent",

                "finding":
                    final_report.model_dump()
            },

            timing_event(
                agent="verification_agent",
                elapsed_seconds=elapsed,
                operation="Two-phase final verification"
            )
        )


        return {

            "final_report":
                final_report,

            "trace":
                trace
        }


    # ========================================================
    # CONDITIONAL ROUTER
    #
    # This does NOT decide which agent to use.
    #
    # The SupervisorDecision already contains that decision.
    # ========================================================

    def route_supervisor(
        state: TriageState
    ) -> str:

        next_agent = state.get(
            "next_agent"
        )


        allowed = {

            "database_agent",

            "streaming_agent",

            "infrastructure_agent",

            "verification_agent"
        }


        if next_agent not in allowed:

            raise RuntimeError(
                f"Supervisor returned invalid route: "
                f"{next_agent}"
            )


        return next_agent


    # ========================================================
    # REGISTER NODES
    # ========================================================

    workflow.add_node(
        "health_agent",
        health_node
    )

    workflow.add_node(
        "supervisor",
        supervisor_node
    )

    workflow.add_node(
        "streaming_agent",
        streaming_node
    )

    workflow.add_node(
        "database_agent",
        database_node
    )

    workflow.add_node(
        "infrastructure_agent",
        infrastructure_node
    )

    workflow.add_node(
        "memory_retrieval",
        memory_node
    )

    workflow.add_node(
        "verification_agent",
        verification_node
    )


    # ========================================================
    # INITIAL FLOW
    # ========================================================

    workflow.add_edge(
        START,
        "health_agent"
    )

    workflow.add_edge(
        "health_agent",
        "supervisor"
    )


    # ========================================================
    # DYNAMIC SUPERVISOR ROUTING
    # ========================================================

    workflow.add_conditional_edges(

        "supervisor",

        route_supervisor,

        {

            "streaming_agent":
                "streaming_agent",

            "database_agent":
                "database_agent",

            "infrastructure_agent":
                "infrastructure_agent",

            # Verification always passes through historical
            # retrieval first.
            "verification_agent":
                "memory_retrieval"
        }
    )


    # ========================================================
    # SPECIALISTS RETURN TO SUPERVISOR
    # ========================================================

    workflow.add_edge(
        "streaming_agent",
        "supervisor"
    )

    workflow.add_edge(
        "database_agent",
        "supervisor"
    )

    workflow.add_edge(
        "infrastructure_agent",
        "supervisor"
    )


    # ========================================================
    # MEMORY -> VERIFICATION -> END
    # ========================================================

    workflow.add_edge(
        "memory_retrieval",
        "verification_agent"
    )

    workflow.add_edge(
        "verification_agent",
        END
    )


    return workflow.compile()


# ============================================================
# PUBLIC TRIAGE FUNCTION
# ============================================================

async def run_triage(
    *,
    scenario_id: str,
    user_report: str,
    all_tools: list[Any],
    progress_callback: Callable[[str], None] | None = None
) -> TriageState:

    graph = build_triage_graph(

        all_tools=all_tools,

        progress_callback=(
            progress_callback
        )
    )


    initial_state: TriageState = {

        "scenario_id":
            scenario_id,

        "user_report":
            user_report,

        "specialist_findings":
            [],

        "visited_agents":
            [],

        "specialist_count":
            0,

        "trace":
            []
    }


    final_state = await graph.ainvoke(

        initial_state,

        config={
            # Logical graph-step protection only.
            # This is NOT a wall-clock timeout.
            "recursion_limit": 30
        }
    )


    # ========================================================
    # COMPLETION CHECKS
    # ========================================================

    if "health" not in final_state:

        raise RuntimeError(
            "Triage ended without a Health Agent result."
        )


    if "memory_query" not in final_state:

        raise RuntimeError(
            "Triage ended without mandatory "
            "historical-memory retrieval."
        )


    if "memory_result" not in final_state:

        raise RuntimeError(
            "Historical-memory retrieval returned no result."
        )


    if "final_report" not in final_state:

        raise RuntimeError(
            "Triage ended without a verified final report."
        )


    if progress_callback is not None:

        progress_callback(
            "Investigation complete. Preparing final report..."
        )


    return final_state