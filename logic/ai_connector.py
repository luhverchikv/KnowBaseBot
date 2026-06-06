# logic/ai_connector.py
import json
import asyncio
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from openai import AsyncOpenAI, APIError, APIConnectionError, RateLimitError
from config import config
from utils.logger import logger

from logic.prompts import (
    QUIZ_DIFFICULTY_PROMPTS,
    QUIZ_GENERATION_SYSTEM_PROMPT, QUIZ_GENERATION_USER_PROMPT,
    QUIZ_POOL_SYSTEM_PROMPT, QUIZ_POOL_USER_PROMPT,
    EVALUATION_SYSTEM_PROMPT, EVALUATION_USER_PROMPT,
    FILE_DESCRIPTION_SYSTEM_PROMPT, FILE_DESCRIPTION_USER_PROMPT
)

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

    
    async def generate_quiz_question(self, md_text: str, difficulty: str = 'medium') -> Tuple[bool, Dict, str, Optional[TokenUsage]]:
        diff_instr = QUIZ_DIFFICULTY_PROMPTS.get(difficulty, QUIZ_DIFFICULTY_PROMPTS['medium'])
        
        # Подставляем переменные в шаблон из prompts.py
        system = QUIZ_GENERATION_SYSTEM_PROMPT.format(
            difficulty=difficulty.upper(), 
            diff_instr=diff_instr
        )
        safe_text = md_text[:3000]
        prompt = QUIZ_GENERATION_USER_PROMPT.format(safe_text=safe_text)
        
        return await self._call_api(system, prompt)


    async def evaluate_answer(self, question: str, correct: str, user: str) -> Tuple[bool, Dict, str, Optional[TokenUsage]]:
        system = EVALUATION_SYSTEM_PROMPT
        prompt = EVALUATION_USER_PROMPT.format(
            question=question, 
            correct=correct, 
            user=user
        )
        return await self._call_api(system, prompt)
    
    
    async def generate_file_description(self, md_text: str) -> Tuple[bool, Optional[str], str, Optional[TokenUsage]]:
        system = FILE_DESCRIPTION_SYSTEM_PROMPT
        safe_text = md_text[:4000]
        prompt = FILE_DESCRIPTION_USER_PROMPT.format(safe_text=safe_text)
        
        success, data, error, token_usage = await self._call_api(system, prompt)
        
        if success and data and "description" in data:
            return True, data["description"], "", token_usage
        
        err_msg = error or "ИИ не вернул ключ 'description' в JSON."
        return False, None, err_msg, token_usage


    async def generate_quiz_pool(self, md_text: str, difficulty: str = 'medium', count: int = 10) -> Tuple[bool, List[Dict], str, Optional[TokenUsage]]:
        diff_instr = QUIZ_DIFFICULTY_PROMPTS.get(difficulty, QUIZ_DIFFICULTY_PROMPTS['medium'])
        
        system = QUIZ_POOL_SYSTEM_PROMPT.format(
            count=count,
            difficulty=difficulty.upper(), 
            diff_instr=diff_instr
        )
        
        safe_text = md_text[:6000] 
        prompt = QUIZ_POOL_USER_PROMPT.format(count=count, safe_text=safe_text)
        
        try:
            success, data, error, token_usage = await self._call_api(system, prompt)
            
            if success and isinstance(data, list) and len(data) > 0:
                valid_pool = []
                for item in data:
                    if isinstance(item, dict) and 'question' in item and 'correct_answer' in item:
                        valid_pool.append({
                            'question': str(item['question']).strip(),
                            'correct_answer': str(item['correct_answer']).strip()
                        })
                
                if valid_pool:
                    return True, valid_pool, "", token_usage
                else:
                    return False, [], "ИИ вернул массив, но элементы не содержат ключей 'question' или 'correct_answer'.", token_usage
            else:
                return False, [], error or "ИИ не вернул корректный JSON-массив.", token_usage
                
        except Exception as e:
            logger.exception("Unexpected error in generate_quiz_pool")
            return False, [], f"Неизвестная ошибка: {e}", None


    async def close(self):
        pass


ai_client = AIConnector()

