"""
Пакет обработчиков команд бота
"""
from . import commands
from . import schedule
from . import notifications
from . import deadlines
from . import progress

__all__ = ['commands', 'schedule', 'notifications', 'deadlines', 'progress']
