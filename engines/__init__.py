"""
Engines package for news sources
"""

from .registry import registry, EngineRegistry
from .base import SourceEngine, MediaExtractor, ContentValidator

# Импортируем движки
from .politico import PoliticoEngine
from .washingtonpost import WashingtonPostEngine
from .twitter import TwitterEngine
from .nbcnews import NBCNewsEngine
from .abcnews import ABCNewsEngine
from .telegrampost import TelegramPostEngine
from .financialtimes import FinancialTimesEngine
from .thehill import TheHillEngine
from .nypost import NYPostEngine
# from .wsj import WSJEngine  # Отключен: требует подписку WSJ + блокируется Cloudflare

__version__ = "1.0.0"
__all__ = ['registry', 'EngineRegistry', 'SourceEngine', 'MediaExtractor', 'ContentValidator', 'PoliticoEngine', 'WashingtonPostEngine', 'TwitterEngine', 'NBCNewsEngine', 'ABCNewsEngine', 'TelegramPostEngine', 'FinancialTimesEngine', 'TheHillEngine', 'NYPostEngine']  # 'WSJEngine' отключен
