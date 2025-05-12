from typing import Annotated, List
import operator
from typing import TypedDict
from .struct import Section, Feedback, Query, SearchResult, ResponseFormat
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    report_structure: str
    sections: List[Section]
    final_section_content: Annotated[List[str], operator.add] = []
    final_report_content: str
    structured_response: ResponseFormat

class ResearchState(TypedDict):
    section: Section
    knowledge: str
    reflection_feedback: Feedback = Feedback(feedback="")
    generated_queries: List[Query] = []
    searched_queries: Annotated[List[Query], operator.add] = []
    search_results: Annotated[List[SearchResult], operator.add] = []
    accumulated_content: str = ""
    reflection_count: int = 1
    final_section_content: List[str] = []