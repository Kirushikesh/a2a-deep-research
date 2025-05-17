import operator
from typing import Annotated, List, TypedDict

from langgraph.graph.message import add_messages

from .struct import Feedback, Query, ResponseFormat, SearchResults, Section


class ResearchState(TypedDict):
    section: Section
    knowledge: str
    reflection_feedback: Feedback
    generated_queries: List[Query]
    searched_queries: Annotated[List[Query], operator.add]
    search_results: Annotated[List[SearchResults], operator.add]
    accumulated_content: str
    reflection_count: int
    final_section_content: List[str]
    current_section_index: int


class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    report_structure: str
    sections: List[Section]
    current_section_index: int
    final_section_content: Annotated[List[str], operator.add]
    search_results: Annotated[List[SearchResults], operator.add]
    structured_response: ResponseFormat
    final_report_content: str
