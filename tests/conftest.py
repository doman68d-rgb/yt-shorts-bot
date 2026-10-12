"""
tests/conftest.py
~~~~~~~~~~~~~~~~

Общая конфигурация pytest.
"""

import os
import sys

# Добавляем корень проекта в PYTHONPATH, чтобы pytest находил пакеты bot/, services/, utils/.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


# Тесты не требуют реального токена: подставляем фейк.
os.environ.setdefault("BOT_TOKEN", "123:test-fake-token-for-tests-only")
