from abc import ABC, abstractmethod
from typing import Any
from src.utils.logger import get_agent_logger

class BaseAgent(ABC):
    """Abstract base class for all agents"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_agent_logger(name)
    
    @abstractmethod
    def execute(self, input_data: Any) -> Any:
        """Execute agent's main task"""
        pass
    
    def log(self, message: str):
        """Log agent activity"""
        self.logger.info(message)

