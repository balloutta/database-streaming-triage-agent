# Database and Streaming Incident Triage Agent

A local multi-agent incident-triage system for investigating database and streaming-platform problems.

The project uses LangGraph, LangChain, MCP, and a local Ollama model to coordinate specialized agents. It investigates simulated production incidents involving MariaDB replication, Kafka consumers, Debezium, database connections, Linux resources, service state, and logs.

The system is intentionally read-only. It can inspect diagnostic information and recommend actions, but it cannot restart services, modify databases, delete files, execute shell commands, or change production configuration.

---

## 1. Project Goal

Operational incidents in database and streaming systems often involve several components at the same time. A delayed analytics dashboard could be caused by Kafka consumer lag, database connection exhaustion, replication failure, Debezium failure, disk exhaustion, or service degradation.

The goal of this project is to demonstrate how a coordinated multi-agent system can investigate these incidents using specialized roles instead of relying on one general-purpose agent.

The system performs:

1. Initial health screening
2. Dynamic specialist routing
3. Domain-specific investigation
4. Historical incident retrieval
5. Final verification
6. Read-only recommendations

---

## 2. Architecture

The application follows a supervisor-based multi-agent architecture.

```text
                         ┌─────────────────────┐
                         │     User Report     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Health & Anomaly    │
                         │ Agent               │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Triage Supervisor   │
                         └──────────┬──────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
          ┌────────────────┐ ┌──────────────┐ ┌────────────────┐
          │ Streaming      │ │ Database     │ │ Infrastructure │
          │ Agent          │ │ Agent        │ │ Agent          │
          └────────┬───────┘ └──────┬───────┘ └────────┬───────┘
                   │                │                  │
                   └────────────────┼──────────────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Historical Incident │
                         │ Retrieval           │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Verification Agent  │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Final Incident      │
                         │ Report              │
                         └─────────────────────┘
```

Routing is dynamic. The system does not use scenario IDs or the evaluation ground-truth file to decide which specialist should investigate an incident.

---

## 3. Agents

### Health & Anomaly Agent

Performs the initial system-health assessment. It identifies abnormal signals, healthy signals, incident severity, and initial operational context. It does not determine the final root cause.

### Triage Supervisor

Chooses which specialist should investigate next:

- Streaming Agent
- Database Agent
- Infrastructure Agent
- Verification Agent

The Supervisor also supports cross-domain investigation. A specialist can hand the incident to another specialist when evidence points outside its own domain.

A high-confidence specialist finding can proceed to verification when no additional specialist investigation is required.

### Streaming Agent

Investigates Kafka consumer lag, Kafka lag trends, Debezium health, consumer processing behavior, and streaming-related logs.

### Database Agent

Investigates MariaDB replication, replication SQL and I/O state, database connection utilization, database connection errors, and database-related logs.

### Infrastructure Agent

Investigates CPU, memory, disk, network status, service state, and infrastructure-related logs.

### Verification Agent

The Verification Agent performs two stages. The first validates the current diagnosis using current telemetry and logs. The second compares the verified incident with retrieved historical incidents.

The verifier distinguishes between symptom similarity, causal similarity, and historical remediation relevance. This prevents a historical incident from being treated as applicable only because it shares a generic symptom such as Kafka lag.

---

## 4. Model Context Protocol

The project uses an MCP server to expose diagnostic capabilities to the agents.

The MCP server provides eight tools:

```text
check_health_summary
check_replication_status
check_database_connections
check_debezium
check_kafka_lag
check_server_metrics
read_logs
retrieve_incident_memory
```

All tools are read-only.

There are no tools for restarting services, deleting files, executing shell commands, modifying databases, changing MariaDB or Kafka configuration, killing database sessions, or restarting replication.

This creates a capability-level safety boundary.

---

## 5. Historical Incident Memory

Historical incidents are stored in:

```text
data/incidents.json
```

The system performs historical retrieval after the technical investigation.

The retrieval query is generated from current observations such as abnormal health signals, specialist evidence, and relevant healthy signals. The retrieval layer uses deterministic lexical matching.

Historical memory is advisory only.

The Verification Agent classifies historical match strength as:

```text
NONE
WEAK
MODERATE
STRONG
```

Historical solution applicability is classified as:

```text
NOT APPLICABLE
PARTIALLY APPLICABLE
APPLICABLE WITH REVIEW
```

The system does not automatically apply historical remediation.

---

## 6. Included Incident Scenarios

The project contains four simulated production incidents.

### Scenario 1 — Kafka Consumer Slowdown

Reported symptom:

```text
The analytics dashboard has not updated for around 20 minutes.
```

Expected technical issue:

```text
Kafka consumer processing is falling behind the incoming message rate.
```

### Scenario 2 — MariaDB Replication Failure

Reported symptom:

```text
Data in the reporting system suddenly stopped refreshing.
```

Expected technical issue:

```text
MariaDB SQL replication stopped because of a duplicate-key error.
```

### Scenario 3 — Infrastructure Disk Exhaustion

Reported symptom:

```text
The streaming service keeps stopping and the dashboard is delayed.
```

Expected technical issue:

```text
Critical disk utilization is disrupting the streaming service.
```

### Scenario 4 — Database Connection Exhaustion

Reported symptom:

```text
The dashboard is becoming increasingly delayed even though the main
services appear to be running.
```

Expected technical issue:

```text
Database connection exhaustion is slowing consumer processing
and causing Kafka lag to grow.
```

This scenario demonstrates cross-domain reasoning because the visible symptom is Kafka backlog while the underlying bottleneck is database connection saturation.

---

## 7. Requirements

Tested with:

```text
Python 3.12
Ollama >= 0.20.0
```

Python packages:

```text
mcp==1.30.0
langchain-mcp-adapters==0.3.2
langchain==1.4.3
langgraph==1.2.11
langchain-ollama==1.1.0
pydantic==2.13.4
```

Local model:

```text
gemma4:e4b
```

Tested model information:

```text
Architecture:  gemma4
Parameters:    8.0B
Quantization:  Q4_K_M
```

The application uses:

```python
MODEL_CONTEXT = 16384
```

---

## 8. Installation

Clone the repository and enter the project directory:

```powershell
git clone https://github.com/balloutta/database-streaming-triage-agent.git
cd database-streaming-triage-agent
```

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Verify the environment:

```powershell
python -m pip check
```

Expected result:

```text
No broken requirements found.
```

---

## 9. Ollama Setup

Verify Ollama:

```powershell
ollama --version
```

Download the model:

```powershell
ollama pull gemma4:e4b
```

Verify that it is available:

```powershell
ollama show gemma4:e4b
```

Make sure Ollama is running before starting the triage application.

No external API key is required.

---

## 10. Generate the Simulation Data

The repository already contains generated configuration and scenario data.

To regenerate them:

```powershell
python setup_project_data.py
```

This creates or updates:

```text
config/thresholds.json
data/scenarios.json
data/incidents.json
evaluation/ground_truth.json
```

The ground-truth file is for evaluation only. Operational agents do not load or use it.

---

## 11. Run the Application

Start the interactive application:

```powershell
python main.py
```

Choose a scenario number and the multi-agent workflow begins.

An example investigation path is:

```text
Health & Anomaly Agent
        ↓
Streaming Agent
        ↓
Database Agent
        ↓
Historical Incident Retrieval
        ↓
Verification Agent
```

The exact path can vary according to the evidence.

---

## 12. Example Final Report

A successful investigation produces sections for:

```text
Incident
Investigation Path
Primary Finding
Key Evidence
Secondary Observations
Historical Incident Comparison
Historical Solution Assessment
Recommended Actions
Safety Status
Overall Assessment
```

The output separates the primary root cause from secondary warnings and healthy exclusionary evidence.

---

## 13. Tests

### Routing Smoke Test

Run:

```powershell
python tests/test_routing_smoke.py
```

This verifies that the Health Agent and Supervisor can identify the appropriate initial investigation domain across the four incidents without loading the ground-truth file.

### Safety and Adversarial Test

Run:

```powershell
python tests/test_safety.py
```

The test verifies that:

- exactly the expected read-only MCP tools are exposed,
- no destructive tools are available,
- adversarial requests have no executable production-changing capability,
- required monitoring capabilities remain available.

The protection is architectural: the MCP server simply does not expose destructive capabilities.

---

## 14. Evaluation

The system was manually validated using four incidents with different causal mechanisms.

| Scenario | Diagnosis | Result |
|---|---|---|
| Kafka consumer slowdown | Consumer processing slower than incoming rate | Passed |
| MariaDB replication failure | SQL replication stopped on duplicate-key conflict | Passed |
| Disk exhaustion | Critical disk utilization disrupting service | Passed |
| DB connection exhaustion | Connection saturation slowing consumer processing | Passed |

Representative end-to-end runtimes on the local test machine:

```text
Scenario 1: 00:15:09
Scenario 2: 00:16:55
Scenario 3: 00:16:03
Scenario 4: 00:27:20
```

The evaluation focused on diagnostic correctness, evidence grounding, dynamic routing, historical-memory use, causal reasoning, and safety behavior.

---

## 15. Safety Design

The main safeguard is structural rather than prompt-only.

The model receives read-only diagnostic tools. Even if a prompt attempts to override safety instructions, the agent has no MCP capability to perform destructive actions.

The application follows a least-privilege pattern:

```text
Observe
   ↓
Reason
   ↓
Recommend
```

It does not autonomously modify production.

Any recommendation involving production changes requires operator review.

---

## 16. Reliability and Failure Handling

Several reliability problems were identified during development.

### Structured-output failures

The local model occasionally completed a tool investigation but failed to return a valid structured response. The final implementation preserves collected MCP evidence and performs structured synthesis instead of rerunning the entire investigation.

### Supervisor formatting

Structured JSON was unnecessarily fragile for a small routing decision. The Supervisor therefore uses:

```text
AGENT|PRIORITY|REASON
```

with deterministic fallback behavior if formatting fails.

### Repeated specialist execution

An early graph version could repeatedly invoke the same specialist after a high-confidence finding. The graph now proceeds toward verification when a specialist returns high confidence and no additional specialist is required.

Low- or medium-confidence findings can still lead to further investigation.

### Historical overmatching

A retrieved incident may share symptoms without sharing the same root cause. The Verification Agent therefore distinguishes symptom similarity from causal similarity before deciding whether historical remediation is relevant.

### Local inference time

The project runs entirely with a local LLM, so complex investigations can take several minutes. No artificial wall-clock timeout is imposed on model inference. Logical recursion limits remain in place to prevent uncontrolled graph or agent loops.

---

## 17. Project Structure

```text
database-streaming-triage-agent/
│
├── agents.py
├── graph.py
├── main.py
├── mcp_server.py
├── setup_project_data.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── config/
│   └── thresholds.json
│
├── data/
│   ├── incidents.json
│   └── scenarios.json
│
├── evaluation/
│   └── ground_truth.json
│
├── tests/
│   ├── test_routing_smoke.py
│   └── test_safety.py
│
└── docs/
    └── sample_output.txt
```

---

## 18. Main Files

- `main.py` — interactive command-line application and report presentation.
- `graph.py` — LangGraph workflow, routing, specialist execution, memory stage, and verification stage.
- `agents.py` — schemas, prompts, local Ollama configuration, specialist implementations, Supervisor logic, memory query construction, and verification logic.
- `mcp_server.py` — read-only MCP diagnostic tools.
- `setup_project_data.py` — generates simulation scenarios, thresholds, historical incidents, and evaluation ground truth.
- `data/scenarios.json` — simulated current incident telemetry and logs.
- `data/incidents.json` — historical incidents used by memory retrieval.
- `evaluation/ground_truth.json` — expected incident outcomes used only for evaluation and validation.

---

## 19. Limitations

This project is a controlled simulation rather than a direct production integration.

The MCP tools read simulated telemetry from JSON instead of connecting to live MariaDB, Kafka, Debezium, or Linux systems.

Other limitations include:

- local-model inference can be slow,
- model output may vary between runs,
- lexical historical retrieval is simpler than embedding-based retrieval,
- the Verification Agent can still make wording or prioritization errors,
- the system recommends actions but does not execute remediation,
- routing quality depends on the quality of observed telemetry.

The read-only limitation is intentional because autonomous production remediation would require stronger authorization, audit, rollback, and approval mechanisms.

---

## 20. Future Work

Possible extensions include:

- live read-only MariaDB monitoring,
- live Kafka consumer-group inspection,
- live Debezium REST status checks,
- Linux monitoring integration,
- embedding-based historical incident retrieval,
- persistent operational memory,
- human approval workflows for remediation,
- authentication and role-based access control,
- structured audit logging,
- Agent-to-Agent communication for distributed deployments.

Agent-to-Agent communication is not implemented in the current project.

---

## 21. Academic Scope

This project was created as an Agentic AI capstone demonstrating:

- multi-agent specialization,
- dynamic coordination,
- MCP tool use,
- historical memory,
- evidence-based verification,
- failure handling,
- least-privilege safety controls,
- adversarial safety testing.

The system is intended as an educational prototype and should not be used to make unattended production changes.

