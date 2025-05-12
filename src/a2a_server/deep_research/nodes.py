from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import (
    ChatPromptTemplate, 
    SystemMessagePromptTemplate, 
    HumanMessagePromptTemplate, 
    MessagesPlaceholder
)
from langchain_core.messages import HumanMessage
from langgraph.types import Command, Send
from typing import Literal, Dict
from langchain_tavily import TavilySearch
from .state import AgentState, ResearchState
from .prompts import (
    REPORT_STRUCTURE_PLANNER_SYSTEM_PROMPT_TEMPLATE,
    SECTION_FORMATTER_SYSTEM_PROMPT_TEMPLATE,
    SECTION_KNOWLEDGE_SYSTEM_PROMPT_TEMPLATE,
    QUERY_GENERATOR_SYSTEM_PROMPT_TEMPLATE,
    RESULT_ACCUMULATOR_SYSTEM_PROMPT_TEMPLATE,
    REFLECTION_FEEDBACK_SYSTEM_PROMPT_TEMPLATE,
    FINAL_SECTION_FORMATTER_SYSTEM_PROMPT_TEMPLATE,
    FINAL_REPORT_WRITER_SYSTEM_PROMPT_TEMPLATE,
)
from .struct import (
    Sections,
    Queries,
    SearchResult,
    SearchResults,
    Feedback,
    Route,
    ResponseFormat,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from .configuration import Configuration

from dotenv import load_dotenv
load_dotenv()

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash')

def report_structure_planner_node(state: AgentState, config: RunnableConfig):
    """
    Plans and generates the initial structure of a research report based on a given topic and outline.

    This node uses an LLM to generate a structured outline for the research report. It takes the topic
    and outline from the agent state and produces a detailed report structure that will guide the rest
    of the research and writing process.

    Args:
        state (AgentState): The current state of the agent, containing the topic and outline
        config (RunnableConfig): Configuration object containing LLM settings like provider, model, and temperature

    Returns:
        Dict: A dictionary containing the 'messages' key with the LLM's response about the report structure
    """

    report_structure_planner_system_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(REPORT_STRUCTURE_PLANNER_SYSTEM_PROMPT_TEMPLATE),
        MessagesPlaceholder(variable_name="messages")
    ])

    report_structure_planner_llm = report_structure_planner_system_prompt | llm

    result = report_structure_planner_llm.invoke(state)
    return {"messages": [result]}

def human_feedback_node(state: AgentState, config: RunnableConfig)->Command[Literal["output", "section_formatter"]]:
    """
    Handles human feedback on the generated report structure.

    This node prompts the user for feedback on the report structure and processes their response.
    If the user types 'continue', it proceeds to format the sections. Otherwise, it returns to the
    report structure planner with the feedback for revision.

    Args:
        state (AgentState): The current state containing the generated report structure messages
        config (RunnableConfig): Configuration object (unused in this node)

    Returns:
        Command: A Command object directing the flow either to:
            - "section_formatter" with the approved report structure
            - "report_structure_planner" with feedback for revision
    """
    response = (
        llm
        .with_structured_output(Route).invoke(
            state["messages"]
        )
    )
    step = response.step

    if step == "input_required":
        return Command(
            goto="output"
        )
    else:
        return Command(
            goto="section_formatter",
        )
    
def output(state: AgentState, config: RunnableConfig):
    """
    Returns the final report content or the last message if no final content is available.

    Args:
        state (AgentState): The current state containing the final report content or messages
        config (RunnableConfig): Configuration object (unused in this node)

    Returns:
        Dict: A dictionary containing the 'structured_response' key with the final report content or last message
    """
    if(state.get('final_report_content',None)):
        return {"structured_response": ResponseFormat(status='completed',message=state['final_report_content'])}
    else:
        return {"structured_response": ResponseFormat(status='input_required',message=state['messages'][-1].content)}


def section_formatter_node(state: AgentState, config: RunnableConfig) -> Command[Literal["research_agent"]]:
    """
    Formats the report structure into discrete sections for processing.

    This node takes the approved report structure and uses an LLM to format it into a structured
    Sections object containing individual sections and their subsections. The formatted sections
    are saved to a JSON file for logging and initialized in the state for sequential processing.

    Args:
        state (AgentState): The current state containing the approved report structure
        config (RunnableConfig): Configuration object containing LLM and other settings

    Returns:
        Command: A Command object directing flow to "queue_next_section" with:
            - sections: List of formatted Section objects
            - current_section_index: Initialized to 0 to begin processing
    """

    section_formatter_system_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(SECTION_FORMATTER_SYSTEM_PROMPT_TEMPLATE),
        MessagesPlaceholder(variable_name="messages")
    ])

    section_formatter_llm = section_formatter_system_prompt | llm.with_structured_output(Sections)
    
    result = section_formatter_llm.invoke(state)
    return Command(
        update={"sections": result.sections},
        goto=[
            Send(
                "research_agent",
                {
                    "section": s,
                }
            ) for s in result.sections
        ]
    )


def section_knowledge_node(state: ResearchState, config: RunnableConfig):
    """
    Generates initial knowledge and understanding about a section before conducting research.

    This node uses an LLM to analyze the section details and generate foundational knowledge
    that will guide the subsequent research process. It processes the section information 
    through a system prompt to establish context and requirements.

    Args:
        state (ResearchState): The current research state containing section information
        config (RunnableConfig): Configuration object containing LLM and other settings

    Returns:
        dict: A dictionary containing the generated knowledge with key:
            - knowledge (str): The LLM-generated understanding and context for the section
    """

    section_knowledge_system_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(SECTION_KNOWLEDGE_SYSTEM_PROMPT_TEMPLATE),
        HumanMessagePromptTemplate.from_template(template="{section}"),
    ])

    section_knowledge_llm = section_knowledge_system_prompt | llm

    result = section_knowledge_llm.invoke(state)
    return {"knowledge": result.content}



def query_generator_node(state: ResearchState, config: RunnableConfig):
    """
    Generates search queries based on the current section content and research state.

    This node uses an LLM to generate targeted search queries for gathering information about
    the current section. It takes into account any previous queries that have been searched
    and feedback from reflection to avoid redundancy and improve query relevance.

    Args:
        state (ResearchState): The current research state containing section information,
            previous queries, and reflection feedback
        config (RunnableConfig): Configuration object containing LLM and other settings

    Returns:
        dict: A dictionary containing:
            - generated_queries (List[Query]): The newly generated search queries
            - searched_queries (List[Query]): Updated list of all searched queries
    """

    configurable = Configuration.from_runnable_config(config)

    query_generator_system_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(QUERY_GENERATOR_SYSTEM_PROMPT_TEMPLATE),
        HumanMessagePromptTemplate.from_template(template="Section: {section}\nPrevious Queries: {searched_queries}\nReflection Feedback: {reflection_feedback}"),
    ])

    query_generator_llm = query_generator_system_prompt | llm.with_structured_output(Queries)

    result = query_generator_llm.invoke({
        "max_queries": configurable.max_queries,
        "reflection_feedback": state.get("reflection_feedback",Feedback(feedback="")),
        "searched_queries": state.get("searched_queries",[]),
        "section": state["section"]
    })

    return {"generated_queries": result.queries, "searched_queries": result.queries}


def tavily_search_node(state: ResearchState, config: RunnableConfig):
    """
    Performs web searches using the Tavily search API for each generated query.

    This node takes the generated queries from the previous node and executes searches
    using the Tavily search engine. For each query, it retrieves search results up to
    the configured search depth, extracting the URL, title, and raw content from each result.

    Args:
        state (ResearchState): The current research state containing generated queries
            and other research context
        config (RunnableConfig): Configuration object containing search depth and other settings

    Returns:
        dict: A dictionary containing:
            - search_results (List[SearchResults]): List of search results for each query,
              where each SearchResults object contains the original query and a list of
              SearchResult objects with URL, title and raw content
    """

    configurable = Configuration.from_runnable_config(config)

    tavily_client = TavilySearch(
        topic="general",
        # include_answer=False,
        include_raw_content=True,
        # include_images=False,
        # include_image_descriptions=False,
        # search_depth="basic",
        # time_range="day",
        # include_domains=None,
        # exclude_domains=None
    )

    queries = state["generated_queries"]
    search_results = []
    for query in queries:
        search_content = []
        response = tavily_client.invoke({"query": query.query, "max_results":configurable.search_depth})
        for result in response["results"]:
            if result['raw_content'] and result['url'] and result['title']:
                search_content.append(SearchResult(url=result['url'], title=result['title'], raw_content=result['raw_content']))
        search_results.append(SearchResults(query=query, results=search_content))

    return {"search_results": search_results}


def result_accumulator_node(state: ResearchState, config: RunnableConfig):
    """
    Accumulates and synthesizes search results into coherent content.

    This node takes the search results from the previous node and uses an LLM to process
    and combine them into a unified, coherent piece of content. The LLM analyzes the 
    search results and extracts relevant information to build knowledge about the section topic.

    Args:
        state (ResearchState): The current research state containing search results
            and other research context
        config (RunnableConfig): Configuration object containing LLM settings and other parameters

    Returns:
        dict: A dictionary containing:
            - accumulated_content (str): The synthesized content generated from processing
              the search results
    """

    result_accumulator_system_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(RESULT_ACCUMULATOR_SYSTEM_PROMPT_TEMPLATE),
        HumanMessagePromptTemplate.from_template(template="{search_results}"),
    ])

    result_accumulator_llm = result_accumulator_system_prompt | llm

    result = result_accumulator_llm.invoke(state)
    return {"accumulated_content": result.content}


def reflection_feedback_node(state: ResearchState, config: RunnableConfig) -> Command[Literal["final_section_formatter", "query_generator"]]:
    """
    Evaluates the quality and completeness of accumulated research content and determines next steps.

    This node uses an LLM to analyze the current section's accumulated content and provide feedback
    on whether it adequately covers the section requirements. Based on the feedback and number of
    reflection iterations, it decides whether to proceed to final formatting or generate more queries
    for additional research.

    Args:
        state (ResearchState): The current research state containing the section info and
            accumulated content to evaluate
        config (RunnableConfig): Configuration object containing LLM settings and reflection parameters

    Returns:
        Command: A Command object directing the flow to either:
            - final_section_formatter: If content is sufficient or max reflections reached
            - query_generator: If content needs improvement and more iterations remain
            The Command includes updated reflection feedback and count in its state updates.
    """

    reflection_count = state.get("reflection_count",1)
    configurable = Configuration.from_runnable_config(config)

    reflection_feedback_system_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(REFLECTION_FEEDBACK_SYSTEM_PROMPT_TEMPLATE),
        HumanMessagePromptTemplate.from_template(template="Section: {section}\nAccumulated Content: {accumulated_content}"),
    ])

    reflection_feedback_llm = reflection_feedback_system_prompt | llm.with_structured_output(Feedback)

    result = reflection_feedback_llm.invoke(state)
    feedback = result.feedback
    if (feedback == True) or (str(feedback).lower() == "true") or (reflection_count < configurable.num_reflections):
        return Command(
            update={"reflection_feedback": feedback},
            goto="final_section_formatter"
        )
    else:
        return Command(
            update={"reflection_feedback": feedback, "reflection_count": reflection_count + 1},
            goto="query_generator"
        )

def final_section_formatter_node(state: ResearchState, config: RunnableConfig):
    """
    Formats the final content for a section of the research report.

    This node uses an LLM to take the accumulated research content and internal knowledge
    about the section, and format it into a cohesive, well-structured section of the report.

    Args:
        state (ResearchState): The current research state containing the section info,
            internal knowledge, and accumulated content to format
        config (RunnableConfig): Configuration object containing LLM settings

    Returns:
        dict: A dictionary containing the formatted section content in the 'final_section_content' key
    """

    final_section_formatter_system_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(FINAL_SECTION_FORMATTER_SYSTEM_PROMPT_TEMPLATE),
        HumanMessagePromptTemplate.from_template(template="Internal Knowledge: {knowledge}\nSearch Result content: {accumulated_content}"),
    ])

    final_section_formatter_llm = final_section_formatter_system_prompt | llm

    result = final_section_formatter_llm.invoke(state)
    return {"final_section_content": [result.content]}


def final_report_writer_node(state: AgentState, config: RunnableConfig):
    """
    Finalizes the research report by generating a conclusion, references, and combining all sections.

    This node takes the accumulated section content and search results from the agent state and:
    1. Uses an LLM to generate a conclusion and curated list of references
    2. Combines all section content into a single markdown document
    3. Returns the final report
    
    Args:
        state (AgentState): The current agent state containing all section content and search results
        config (RunnableConfig): Configuration object containing LLM settings

    Returns:
        dict: A dictionary containing the complete report content in the 'final_report_content' key
    """

    final_report_writer_system_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(FINAL_REPORT_WRITER_SYSTEM_PROMPT_TEMPLATE),
        MessagesPlaceholder(variable_name="messages"),
        HumanMessagePromptTemplate.from_template(template="The above contents covers the report structure\nSection Contents: {final_section_content}"),
    ])

    final_report_writer_llm = final_report_writer_system_prompt | llm

    result = final_report_writer_llm.invoke(state)
    return {"final_report_content": result.content}