import json
import logging
import re
import sys
from collections.abc import AsyncGenerator
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.context import Context
from google.adk.apps import App
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.tools import AgentTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.workflow import START, Edge, Workflow, node
from google.genai import types
from mcp import StdioServerParameters
from pydantic import BaseModel, Field, model_validator

from .config import config

# Setup logging for security audit
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent_security")


def log_audit(event_type: str, severity: str, details: dict):
    log_entry = {"event_type": event_type, "severity": severity, "details": details}
    logger.info(json.dumps(log_entry))
    try:
        # Log to a file in the project directory
        with open("security_audit.log", "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write to audit log file: {e}")


# PII Scrubbing
def scrub_pii(text: str) -> tuple[str, bool]:
    phone_pattern = r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"

    scrubbed = text
    modified = False

    if re.search(phone_pattern, text):
        scrubbed = re.sub(phone_pattern, "[PHONE_REDACTED]", scrubbed)
        modified = True
    if re.search(email_pattern, text):
        scrubbed = re.sub(email_pattern, "[EMAIL_REDACTED]", scrubbed)
        modified = True

    return scrubbed, modified


# Injection keywords
INJECTION_KEYWORDS = [
    "ignore previous",
    "override system",
    "system prompt",
    "developer mode",
    "jailbreak",
    "you must instead",
    "ignore instructions",
]


# Domain-specific rule: medical prescriptions / dangerous goals
def check_domain_safety(text: str) -> tuple[bool, str]:
    medical_keywords = [
        "prescribe",
        "ozempic",
        "adderall",
        "xanax",
        "insulin",
        "steroids",
        "medication",
    ]
    for word in medical_keywords:
        if word in text.lower():
            return (
                False,
                f"Request for medical prescription/medication '{word}' is blocked.",
            )

    if (
        "starve" in text.lower()
        or "no food" in text.lower()
        or "0 calories" in text.lower()
    ):
        return False, "Unsafe dietary goals (starvation/zero calories) are blocked."

    return True, ""


# Pydantic models for structured output
class MealPlan(BaseModel):
    meals: list[str] = Field(description="List of suggested meals/recipes")
    grocery_list: list[str] = Field(description="Grocery list for the meals")
    dietary_notes: str = Field(description="Dietary notes/allergies considerations")


class WorkoutPlan(BaseModel):
    exercises: list[str] = Field(description="List of exercises in the workout routine")
    duration_minutes: int = Field(
        description="Total duration of the workout in minutes"
    )
    tips: str = Field(description="Safety or execution tips")


class CoachPlan(BaseModel):
    meal_plan: MealPlan
    workout_plan: WorkoutPlan
    summary: str


class WorkflowInput(BaseModel):
    query: str = Field(description="User request (e.g. goals, dietary preferences)")

    @model_validator(mode="before")
    @classmethod
    def parse_input(cls, data: Any) -> dict:
        if isinstance(data, dict):
            if "query" in data:
                return data
            if "parts" in data:
                text = ""
                for part in data["parts"]:
                    if isinstance(part, dict) and "text" in part:
                        text += part["text"]
                    elif hasattr(part, "text") and part.text:
                        text += part.text
                return {"query": text}
            if "text" in data:
                return {"query": data["text"]}
        if isinstance(data, str):
            return {"query": data}
        if hasattr(data, "parts") and data.parts:
            text = ""
            for part in data.parts:
                if hasattr(part, "text") and part.text:
                    text += part.text
                elif isinstance(part, dict) and "text" in part:
                    text += part["text"]
            return {"query": text}
        return {"query": str(data)}


class WorkflowState(BaseModel):
    query: str = ""
    coach_plan: dict = {}
    feedback: str = ""
    approved: bool = False
    audit_log: list[dict] = []


# Local MCP toolset stdio parameters
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["app/mcp_server.py"],
        )
    )
)

# Specialized sub-agents
meal_planner_agent = LlmAgent(
    name="meal_planner_agent",
    model=config.model,
    instruction="You are a professional nutritionist. Design a meal plan with recipes and a grocery list based on user goals and restrictions. Use the search_recipes tool if needed to fetch healthy recipes. Do not ask follow-up questions; always generate a complete plan with the information provided.",
    output_schema=MealPlan,
    tools=[mcp_toolset],
)

workout_planner_agent = LlmAgent(
    name="workout_planner_agent",
    model=config.model,
    instruction="You are a professional fitness coach. Design a personalized workout routine based on the user's fitness level and goals. Use the get_exercise_guidelines tool if needed to check safe form or exercises. Do not ask follow-up questions; always generate a complete plan with the information provided.",
    output_schema=WorkoutPlan,
    tools=[mcp_toolset],
)

# Orchestrator agent
orchestrator_agent = LlmAgent(
    name="orchestrator_agent",
    model=config.model,
    instruction="You are the head Coach Coordinator. Use meal_planner_agent and workout_planner_agent tools to gather meal and workout plans. Present a unified CoachPlan to the user. Always use the tools provided to compile the sub-plans.",
    tools=[AgentTool(meal_planner_agent), AgentTool(workout_planner_agent)],
    output_schema=CoachPlan,
)


# Workflow node functions
@node
def security_checkpoint(ctx: Context, node_input: WorkflowInput) -> Event:
    query = node_input.query

    # 1. PII Scrubbing
    scrubbed_query, pii_found = scrub_pii(query)
    if pii_found:
        log_audit(
            "PII_REDACTION", "INFO", {"original": query, "scrubbed": scrubbed_query}
        )

    # 2. Prompt Injection Detection
    for keyword in INJECTION_KEYWORDS:
        if keyword in scrubbed_query.lower():
            log_audit(
                "PROMPT_INJECTION",
                "CRITICAL",
                {"keyword": keyword, "query": scrubbed_query},
            )
            return Event(
                output="Request blocked: Prompt injection attempt detected.",
                route="SECURITY_EVENT",
            )

    # 3. Domain Specific Check
    safe, reason = check_domain_safety(scrubbed_query)
    if not safe:
        log_audit(
            "DOMAIN_SAFETY_VIOLATION",
            "WARNING",
            {"reason": reason, "query": scrubbed_query},
        )
        return Event(output=f"Request blocked: {reason}", route="SECURITY_EVENT")

    log_audit("INPUT_CLEAN", "INFO", {"query": scrubbed_query})
    return Event(output=scrubbed_query, route="clean", state={"query": scrubbed_query})


@node
def security_violation(node_input: str) -> Event:
    content = types.Content(
        role="model", parts=[types.Part.from_text(text=f"⚠️ {node_input}")]
    )
    return Event(content=content, output=node_input)


@node(rerun_on_resume=True)
async def orchestrator_node(
    ctx: Context, node_input: str
) -> AsyncGenerator[Event, None]:
    feedback = ctx.state.get("feedback", "")
    prompt = f"User goals: {node_input}"
    if feedback:
        prompt += f"\n\nThe user requested changes: {feedback}\nPlease adjust the plan accordingly."

    result = await ctx.run_node(orchestrator_agent, node_input=prompt)

    yield Event(output=result, state={"coach_plan": result})


@node(rerun_on_resume=True)
async def hitl_approval_node(
    ctx: Context, node_input: dict
) -> AsyncGenerator[Event, None]:
    if not ctx.resume_inputs:
        meal_plan = node_input.get("meal_plan", {})
        workout_plan = node_input.get("workout_plan", {})

        # Construct human-friendly presentation
        plan_text = (
            f"### Proposed Coach Plan 📋\n\n"
            f"**Summary:** {node_input.get('summary', '')}\n\n"
            f"#### 🍏 Diet & Meal Plan\n"
            f"- **Meals:**\n  "
            + "\n  ".join([f"* {m}" for m in meal_plan.get("meals", [])])
            + "\n"
            "- **Grocery List:**\n  "
            + "\n  ".join([f"* {g}" for g in meal_plan.get("grocery_list", [])])
            + "\n"
            f"- **Dietary Notes:** {meal_plan.get('dietary_notes', 'None')}\n\n"
            f"#### 🏋️ Workout Plan\n"
            f"- **Exercises:**\n  "
            + "\n  ".join([f"* {e}" for e in workout_plan.get("exercises", [])])
            + "\n"
            f"- **Duration:** {workout_plan.get('duration_minutes', 0)} minutes\n"
            f"- **Tips:** {workout_plan.get('tips', 'None')}\n\n"
            f"Do you approve this plan? (Type 'approve' to finalize, or describe your desired changes)."
        )

        yield Event(
            content=types.Content(
                role="model", parts=[types.Part.from_text(text=plan_text)]
            )
        )
        yield RequestInput(
            interrupt_id="approval", message="Please approve or request modifications."
        )
        return

    user_response = ctx.resume_inputs.get("approval", "").strip()
    if user_response.lower() == "approve":
        yield Event(
            output=node_input,
            route="approved",
            state={"approved": True, "feedback": ""},
        )
    else:
        yield Event(
            output=user_response,
            route="change_requested",
            state={"feedback": user_response},
        )


@node
def final_output(node_input: dict) -> Event:
    success_msg = "### Plan Confirmed! 🏆\nYour meal and workout plan is officially saved. Happy training!"
    content = types.Content(
        role="model", parts=[types.Part.from_text(text=success_msg)]
    )
    return Event(content=content, output=node_input)


# Constructing Workflow
root_agent = Workflow(
    name="coach_workflow",
    edges=[
        Edge(from_node=START, to_node=security_checkpoint),
        Edge(from_node=security_checkpoint, to_node=orchestrator_node, route="clean"),
        Edge(
            from_node=security_checkpoint,
            to_node=security_violation,
            route="SECURITY_EVENT",
        ),
        Edge(from_node=orchestrator_node, to_node=hitl_approval_node),
        Edge(
            from_node=hitl_approval_node,
            to_node=orchestrator_node,
            route="change_requested",
        ),
        Edge(from_node=hitl_approval_node, to_node=final_output, route="approved"),
    ],
    input_schema=WorkflowInput,
    state_schema=WorkflowState,
    description="Orchestrates personalized health plans, verifying safety and requesting human approval.",
)

app = App(
    root_agent=root_agent,
    name="app",
)
