import logging
from dotenv import load_dotenv


def setup(logging_level: int = logging.INFO) -> None:
    """Load environment variables and configure logging."""
    load_dotenv()
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging_level,
    )

