"""
llm_proxy.py

LLMProxy — единая точка доступа к языковым моделям (LLM) для Евы 2.0.

Зачем нужен:
- Скрывает детали SDK OpenAI и переменных окружения.
- Даёт единый интерфейс: "сделай запрос" -> "получи ответ".
- Маршрутизирует запросы по моделям:
  - OPENAI_CHAT_MODEL (например, gpt-4o) для диалога/планов/объяснений
  - OPENAI_CODE_MODEL (например, gpt-5.2) строго для кода/тестов/рефакторинга

Правило архитектуры:
- В других модулях НЕ должно быть прямых вызовов OpenAI SDK.
- Только через LLMProxy (одна дверь = контроль и безопасность).
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from openai import APIError, APITimeoutError, RateLimitError


@dataclass(frozen=True)
class LLMModels:
    """
    Контейнер имён моделей.

    Зачем:
    - Явно фиксируем, какие модели используются.
    - Упрощаем самодиагностику и будущую замену моделей.
    """
    chat: str
    code: str


class LLMProxy:
    """
    Прокси для запросов к LLM.

    Реализует реальные вызовы к OpenAI API с обработкой ошибок и таймаутами.
    """

    def __init__(self, timeout: float = 60.0):
        """
        Инициализирует LLMProxy.

        Args:
            timeout: Таймаут для запросов в секундах (по умолчанию 60).
        """
        # Что делаем:
        # - Загружаем .env (если он есть).
        # Зачем:
        # - Чтобы конфигурация (ключи/модели) не хранилась в коде.
        load_dotenv()

        # Что берём:
        # - Ключ API для реальных запросов.
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to .env file. "
                "Example: OPENAI_API_KEY=sk-..."
            )

        # Что берём:
        # - Имена моделей для двух режимов работы.
        self.models = LLMModels(
            chat=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o").strip(),
            code=os.getenv("OPENAI_CODE_MODEL", "gpt-4o").strip(),  # По умолчанию gpt-4o, т.к. gpt-5.2 может не существовать
        )

        # Создаём клиент OpenAI
        self._client = OpenAI(api_key=self.api_key, timeout=timeout)
        self._timeout = timeout

    def choose_model(self, task_type: str) -> str:
        """
        Что делает:
        - Выбирает модель по типу задачи.

        task_type:
        - "chat" -> модель диалога/планирования
        - "code" -> модель кода/тестов

        Зачем:
        - DecisionEngine и остальные модули дают только тип задачи,
          а выбор модели централизован.
        """
        task_type = (task_type or "").strip().lower()

        if task_type == "code":
            return self.models.code

        # По умолчанию — "chat"
        return self.models.chat

    def request(
        self,
        task_type: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Единая точка запроса к LLM.

        Args:
            task_type: Тип задачи ("chat" или "code").
            prompt: Основной промпт для модели.
            system_prompt: Системный промпт (опционально). Если не указан,
                          используется базовый для типа задачи.
            temperature: Температура генерации (0.0-2.0). По умолчанию 0.7.
            max_tokens: Максимальное количество токенов в ответе (опционально).

        Returns:
            Ответ модели в виде строки.

        Raises:
            RuntimeError: Если API ключ не установлен или произошла ошибка API.
            ValueError: Если промпт пустой.
        """
        if not prompt or not prompt.strip():
            raise ValueError("prompt cannot be empty")

        model = self.choose_model(task_type=task_type)

        # Формируем системный промпт
        if system_prompt is None:
            if task_type == "code":
                system_prompt = (
                    "Ты — эксперт по программированию на Python. "
                    "Генерируй чистый, читаемый код, следуя лучшим практикам. "
                    "Включай обработку ошибок и документацию."
                )
            else:
                system_prompt = (
                    "Ты — интеллектуальный ассистент Ева 2.0. "
                    "Помогай с планированием, анализом и принятием решений. "
                    "Будь точным и структурированным в ответах."
                )

        # Формируем сообщения для Chat API
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        try:
            # Выполняем запрос к OpenAI API
            response = self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Извлекаем текст ответа
            if not response.choices:
                raise RuntimeError("OpenAI API returned empty response")

            answer = response.choices[0].message.content
            if answer is None:
                raise RuntimeError("OpenAI API returned None content")

            return answer.strip()

        except RateLimitError as e:
            raise RuntimeError(
                f"OpenAI API rate limit exceeded. Please wait before retrying. {e}"
            ) from e
        except APITimeoutError as e:
            raise RuntimeError(
                f"OpenAI API request timed out after {self._timeout}s. {e}"
            ) from e
        except APIError as e:
            raise RuntimeError(
                f"OpenAI API error: {e}. Check your API key and model name."
            ) from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error in LLM request: {e}") from e
