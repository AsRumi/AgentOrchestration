"""
Agent nodes — the individual agents in the workflow.

Each agent is a plain Python function that:
  1. Receives the current AgentState
  2. Does its work (calls LLM, uses tools, etc.)
  3. Returns a dict with ONLY the fields it wants to update in state

LangGraph merges the returned dict into the existing state.
Returning a partial dict (not the full state) is intentional and correct.

Agents defined here:
  - planner_node       → Creates the research plan
  - researcher_node    → Researches one question (called in a loop)
  - synthesizer_node   → Synthesizes all findings
  - writer_node        → Writes the final report
  - should_continue_research → Conditional edge logic (not a node)
"""
import json
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from src.agents.state import AgentState, ResearchItem
from src.agents.tools import RESEARCHER_TOOLS, web_search
from src.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM Factory
# ---------------------------------------------------------------------------

def get_llm(temperature: float = 0.3) -> ChatGoogleGenerativeAI:
    """
    Returns a Gemini LLM instance.

    We use gemini-2.0-flash for all agents — it's fast and capable.
    Temperature 0.3 gives focused, consistent outputs (lower = more deterministic).
    """
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# Planner Node
# ---------------------------------------------------------------------------

def planner_node(state: AgentState) -> dict:
    """
    PLANNER AGENT

    Responsibility: Take the user's topic and decompose it into 3–5
    specific, answerable research questions.

    Why: A single broad query produces shallow results. Breaking it into
    targeted sub-questions lets the Researcher go deep on each aspect.

    Output: Updates `research_plan` and `research_index` in state.
    """
    logger.info(f"[Planner] Creating research plan for: {state['topic']}")
    llm = get_llm(temperature=0.2)

    system_prompt = """You are a research strategist. Your job is to decompose a broad topic
into 3 to 5 specific, focused research questions that together provide comprehensive coverage.

Rules:
- Each question must be answerable with web search
- Questions should cover different aspects (definition, mechanics, examples, applications, limitations)
- Be specific, not vague

IMPORTANT: Respond with ONLY a valid JSON array of strings. No preamble, no explanation, no markdown.
Example output: ["What is X?", "How does X work mechanically?", "What are real-world applications of X?"]"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Decompose this research topic: {state['topic']}")
    ])

    try:
        # Strip any accidental markdown code fences
        content = response.content.strip().strip("```json").strip("```").strip()
        plan = json.loads(content)
        if not isinstance(plan, list):
            raise ValueError("Expected a list")
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"[Planner] Failed to parse JSON, using fallback. Error: {e}")
        # Fallback: create basic questions from the topic
        plan = [
            f"What is {state['topic']} and how does it work?",
            f"What are the key components of {state['topic']}?",
            f"What are practical applications and real-world examples of {state['topic']}?",
        ]

    logger.info(f"[Planner] Created {len(plan)} research questions")
    return {
        "research_plan": plan,
        "research_index": 0,
        "status": f"planning_complete_{len(plan)}_questions",
    }


# ---------------------------------------------------------------------------
# Researcher Node
# ---------------------------------------------------------------------------

def researcher_node(state: AgentState) -> dict:
    """
    RESEARCHER AGENT

    Responsibility: Research ONE question from the plan. This node is called
    in a loop (once per question) by the conditional edge logic below.

    How it works:
    1. Gets the current question (research_plan[research_index])
    2. Searches the web using the DuckDuckGo tool
    3. Uses the LLM to extract and structure the key findings
    4. Appends a ResearchItem to research_items
    5. Increments research_index so the next call gets the next question

    Output: Appends to `research_items`, increments `research_index`.
    """
    current_index = state["research_index"]
    total = len(state["research_plan"])
    current_query = state["research_plan"][current_index]

    logger.info(f"[Researcher] Question {current_index + 1}/{total}: {current_query}")

    # Step 1: Search the web
    search_results = web_search.invoke({"query": current_query, "max_results": 5})

    # Step 2: LLM extracts structured findings from raw search results
    llm = get_llm(temperature=0.2)
    system_prompt = """You are a research analyst. Given a research question and raw web search results,
extract the most relevant, factual information.

Your output should:
- Directly answer the research question
- Include specific facts, numbers, or examples where available
- Be 200–400 words
- Be in clear prose (not bullet points)
- Focus on accuracy, not comprehensiveness"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Research Question: {current_query}\n\nSearch Results:\n{search_results}")
    ])

    research_item: ResearchItem = {
        "query": current_query,
        "findings": response.content,
    }

    logger.info(f"[Researcher] Completed question {current_index + 1}/{total}")
    return {
        "research_items": [research_item],   # operator.add will APPEND this
        "research_index": current_index + 1,
        "status": f"researched_{current_index + 1}_of_{total}",
    }


# ---------------------------------------------------------------------------
# Conditional Edge Logic
# ---------------------------------------------------------------------------

def should_continue_research(state: AgentState) -> str:
    """
    This is NOT a node — it's the conditional routing logic for the loop.

    LangGraph calls this function after each Researcher call to decide
    what happens next:
      - If there are more questions: route back to researcher_node
      - If all questions done: route to synthesizer_node

    The returned string must match keys in `add_conditional_edges(...)`.
    """
    if state["research_index"] < len(state["research_plan"]):
        return "continue_research"
    return "synthesize"


# ---------------------------------------------------------------------------
# Synthesizer Node
# ---------------------------------------------------------------------------

def synthesizer_node(state: AgentState) -> dict:
    """
    SYNTHESIZER AGENT

    Responsibility: Take all the individual research findings and produce
    a cohesive synthesis — identifying themes, patterns, and key insights.

    Why a separate synthesis step: Raw research findings are a pile of facts.
    The synthesizer connects them, finds patterns, and resolves contradictions
    before the writer turns them into prose.

    Output: Sets `synthesis` in state.
    """
    logger.info(f"[Synthesizer] Synthesizing {len(state['research_items'])} research items")
    llm = get_llm(temperature=0.4)

    # Format all research items for the LLM
    research_text = "\n\n---\n\n".join([
        f"**Research Question:** {item['query']}\n\n**Findings:** {item['findings']}"
        for item in state["research_items"]
    ])

    system_prompt = """You are a research synthesizer. Given multiple research findings on a topic,
produce a structured synthesis that:

1. Identifies the 3–5 most important themes that cut across the findings
2. Highlights the most significant insights and facts
3. Notes any tensions, contradictions, or open questions
4. Groups related information together logically

Write in clear, organized prose. Use headers for each theme. Be analytical, not just descriptive.
Length: 400–600 words."""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Topic: {state['topic']}\n\nResearch Findings:\n\n{research_text}")
    ])

    logger.info("[Synthesizer] Synthesis complete")
    return {
        "synthesis": response.content,
        "status": "synthesis_complete",
    }


# ---------------------------------------------------------------------------
# Writer Node
# ---------------------------------------------------------------------------

def writer_node(state: AgentState) -> dict:
    """
    WRITER AGENT

    Responsibility: Turn the synthesis into a polished, professional
    research report that a reader would find genuinely useful.

    Why a separate writer: The synthesizer is analytical but terse. The writer's
    job is to make the output readable — adding context, transitions, and structure.

    Output: Sets `final_report` in state (markdown formatted).
    """
    logger.info("[Writer] Writing final report")
    llm = get_llm(temperature=0.5)

    system_prompt = """You are a professional technical writer. Given a research synthesis,
produce a well-structured research report in Markdown.

Required structure:
# [Title based on topic]

## Executive Summary
2–3 sentence overview of the key findings.

## Background
Brief context for the topic.

## Key Findings
### [Theme 1]
### [Theme 2]
### [Theme 3]
(etc.)

## Analysis & Implications
What do these findings mean? Why does it matter?

## Conclusion
Wrap up with the most important takeaways.

---
*Report generated by Conductor Multi-Agent System*

Style: Clear, professional, accessible to a technical audience. Use concrete examples.
Length: 600–900 words."""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"Topic: {state['topic']}\n\nSynthesis to expand into a report:\n\n{state['synthesis']}"
        )
    ])

    logger.info("[Writer] Report complete")
    return {
        "final_report": response.content,
        "status": "complete",
    }
