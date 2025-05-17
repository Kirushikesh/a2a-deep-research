import logging
import os

import click
from agent import DeepResearchAgent
from common.server import A2AServer
from common.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    MissingAPIKeyError,
)
from common.utils.push_notification_auth import PushNotificationSenderAuth
from dotenv import load_dotenv
from task_manager import AgentTaskManager

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@click.command()
@click.option("--host", "host", default="localhost")
@click.option("--port", "port", default=10000)
def main(host, port):
    """Starts the Research Agent server."""
    try:
        if not os.getenv("GOOGLE_API_KEY"):
            raise MissingAPIKeyError("GOOGLE_API_KEY environment variable not set.")

        capabilities = AgentCapabilities(streaming=True, pushNotifications=False)
        research_skill = AgentSkill(
            id="deep_research",
            name="Deep Research Analysis",
            description="Performs comprehensive research and analysis on complex topics",
            tags=["research", "analysis", "academic", "literature review"],
            examples=[
                "Research the latest advancements in quantum computing",
                "Analyze the impact of AI on healthcare",
                "Summarize recent papers on climate change mitigation",
            ],
        )
        agent_card = AgentCard(
            name="Deep Research Agent",
            description="Advanced AI agent for comprehensive research and analysis",
            url=f"http://{host}:{port}/",
            version="1.0.0",
            defaultInputModes=DeepResearchAgent.SUPPORTED_CONTENT_TYPES,
            defaultOutputModes=DeepResearchAgent.SUPPORTED_CONTENT_TYPES,
            capabilities=capabilities,
            skills=[research_skill],
        )

        notification_sender_auth = PushNotificationSenderAuth()
        notification_sender_auth.generate_jwk()
        server = A2AServer(
            agent_card=agent_card,
            task_manager=AgentTaskManager(
                agent=DeepResearchAgent(),
                notification_sender_auth=notification_sender_auth,
            ),
            host=host,
            port=port,
        )

        server.app.add_route(
            "/.well-known/jwks.json",
            notification_sender_auth.handle_jwks_endpoint,
            methods=["GET"],
        )

        logger.info(f"Starting server on {host}:{port}")
        server.start()
    except MissingAPIKeyError as e:
        logger.error(f"Error: {e}")
        exit(1)
    except Exception as e:
        logger.error(f"An error occurred during server startup: {e}")
        exit(1)


if __name__ == "__main__":
    main()
