"""
tests/conftest.py
~~~~~~~~~~~~~~~~

Общая конфигурация pytest.
"""

import os
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH, чтобы pytest находил пакеты bot/, services/, utils/.
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# Тесты не требуют реального токена: подставляем фейк.
os.environ.setdefault("BOT_TOKEN", "123:test-fake-token-for-tests-only")
