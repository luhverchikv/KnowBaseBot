# logic/ai_connector.py
import json
import asyncio
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

# ✅ Используем официальную асинхронную библиотеку
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError

from config import config
from utils.logger import logger

@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class AIConnector:
    def __init__(self):
        self.api_key = config.ai.api_key
        self.base_url = config.ai.base_url.rstrip('/')
        self.model = config.ai.model
        self.temperature = config.ai.temperature
        self.max_tokens = config.ai.max_tokens
        
        # ✅ Инициализируем официальный клиент
        # Он сам управляет сессиями, повторными попытками и таймаутами
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=90.0,
            max_retries=3
        )

    async def _clean_json(self, text: str) -> str:
        """Убирает markdown-обёртки ```json ... ``` из ответа AI"""
        text = text.strip()
        
        # Удаляем открывающую обёртку с любым суффиксом (```json, ```python и т.д.)
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            else:
                text = text[3:]
        
        # Удаляем закрывающую обёртку
        if text.endswith("```"):
            text = text[:-3]
        
        return text.strip()

    async def _call_api(self, system_prompt: str, user_prompt: str) -> Tuple[bool, Optional[Dict], str, Optional[TokenUsage]]:
        """
        Универсальный метод для вызова API.
        Возвращает: (success, data_dict, error_message, token_usage)
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            content = response.choices[0].message.content
            
            # ✅ Извлечение токенов (безопасная проверка, т.к. некоторые провайдеры могут не возвращать usage)
            usage_obj = response.usage
            token_usage = TokenUsage(
                prompt_tokens=usage_obj.prompt_tokens if usage_obj else 0,
                completion_tokens=usage_obj.completion_tokens if usage_obj else 0,
                total_tokens=usage_obj.total_tokens if usage_obj else 0
            )
            
            logger.info(f"🤖 AI Response received. Usage: {token_usage.total_tokens} tokens.")
            
            try:
                cleaned_content = await self._clean_json(content)
                data = json.loads(cleaned_content)
                return True, data, "", token_usage
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode failed. Raw: {content[:200]}...")
                return False, None, f"AI вернул невалидный JSON: {e}", token_usage

        except RateLimitError:
            return False, None, "Превышен лимит запросов к AI (Rate Limit).", None
        except APIConnectionError:
            return False, None, "Ошибка подключения к серверу AI.", None
        except APIError as e:
            return False, None, f"Ошибка API: {e}", None
        except Exception as e:
            logger.exception("Unexpected error in AIConnector")
            return False, None, f"Неизвестная ошибка: {e}", None

    # logic/ai_connector.py (замените метод generate_quiz_question)
    async def generate_quiz_question(self, md_text: str, difficulty: str = 'medium') -> Tuple[bool, Dict, str, Optional[TokenUsage]]:
        difficulty_prompts = {
            'easy': "Вопрос должен быть простым, прямым и проверять базовое запоминание фактов. Подходит для новичков.",
            'medium': "Вопрос должен быть умеренно сложным, требовать понимания материала и применения знаний на практике.",
            'hard': "Вопрос должен быть сложным, требовать глубокого анализа, синтеза информации или оценки нескольких концепций одновременно."
        }
        diff_instr = difficulty_prompts.get(difficulty, difficulty_prompts['medium'])
        
        system = f"Return strictly valid JSON with keys 'question' and 'correct_answer'. No extra text.\nDifficulty level: {difficulty.upper()}. {diff_instr}"
        safe_text = md_text[:3000]
        prompt = f"Generate ONE clear quiz question and its exact correct answer based on this text:\n{safe_text}"
        return await self._call_api(system, prompt)


    async def evaluate_answer(self, question: str, correct: str, user: str) -> Tuple[bool, Dict, str, Optional[TokenUsage]]:
        system = "Return strictly valid JSON with keys: 'correctness' (one of: 'правильно','частично','неправильно'), 'feedback' (short explanation in Russian), 'rating' (1-5)."
        prompt = f"Question: {question}\nCorrect: {correct}\nUser: {user}\nEvaluate and return JSON only."
        return await self._call_api(system, prompt)
    
    
    async def generate_file_description(self, md_text: str) -> Tuple[bool, Optional[str], str, Optional[TokenUsage]]:
        """
        Генерирует краткое описание (summary) для загруженного markdown-файла.
        Возвращает: (success, description_text, error_message, token_usage)
        """
        system = (
            "Вы — ассистент базы знаний. Проанализируйте текст и составьте его очень краткое описание "
            "на русском языке (1-2 предложения, максимум 150 символов), отражающее суть документа.\n"
            "Верните ответ СТРОГО в формате JSON с единственным ключом 'description'. Никакого другого текста."
        )
        # Ограничиваем срез текста, чтобы не выйти за лимиты токенов
        safe_text = md_text[:4000]
        prompt = f"Составь краткое описание для следующего текста:\n\n{safe_text}"
        
        # Вызываем универсальный метод API
        success, data, error, token_usage = await self._call_api(system, prompt)
        
        if success and data and "description" in data:
            return True, data["description"], "", token_usage
        
        # Если ИИ вернул JSON, но без нужного ключа, или произошла ошибка API
        err_msg = error or "ИИ не вернул ключ 'description' в JSON."
        return False, None, err_msg, token_usage


    async def close(self):
        # В AsyncOpenAI нет явного метода close, сессии закрываются автоматически при сборке мусора,
        # но для совместимости с вашим main.py оставляем заглушку или pass.
        pass

# Синглтон для удобного импорта
ai_client = AIConnector()

