from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .nodes import (
    final_section_formatter_node,
    finalizer_node,
    human_feedback_node,
    output,
    query_generator_node,
    queue_next_section_node,
    reflection_feedback_node,
    report_structure_planner_node,
    result_accumulator_node,
    section_formatter_node,
    section_knowledge_node,
    tavily_search_node,
)
from .state import AgentState, ResearchState
from .struct import SectionOutput

# <<< ----- RESEARCH AGENT ----- >>>

research_builder = StateGraph(ResearchState, output=SectionOutput)

research_builder.add_node("section_knowledge", section_knowledge_node)
research_builder.add_node("query_generator", query_generator_node)
research_builder.add_node("tavily_search", tavily_search_node)
research_builder.add_node("result_accumulator", result_accumulator_node)
research_builder.add_node("reflection", reflection_feedback_node)
research_builder.add_node("final_section_formatter", final_section_formatter_node)

research_builder.add_edge(START, "section_knowledge")
research_builder.add_edge("section_knowledge", "query_generator")
research_builder.add_edge("query_generator", "tavily_search")
research_builder.add_edge("tavily_search", "result_accumulator")
research_builder.add_edge("result_accumulator", "reflection")
research_builder.add_edge("final_section_formatter", END)


builder = StateGraph(AgentState)

builder.add_node("report_structure_planner", report_structure_planner_node)
builder.add_node("human_feedback", human_feedback_node)
builder.add_node("section_formatter", section_formatter_node)
builder.add_node("queue_next_section", queue_next_section_node)
builder.add_node("research_agent", research_builder.compile())
builder.add_node("finalizer", finalizer_node)
builder.add_node("output", output)

builder.set_entry_point("report_structure_planner")
builder.add_edge("report_structure_planner", "human_feedback")
builder.add_edge("section_formatter", "queue_next_section")
builder.add_edge("research_agent", "queue_next_section")
builder.add_edge("finalizer", "output")
builder.add_edge("output", END)
