# logic/ai_connector.py
import json
import asyncio
import aiohttp
from typing import Dict, Tuple, Optional
from config import config
from utils.logger import logger
from dataclasses import dataclass

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
        self.max_retries = 3
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90))

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

    async def _call_api(self, prompt: str, system_prompt: str) -> Tuple[bool, Optional[Dict], str]:
        await self._ensure_session()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        for attempt in range(self.max_retries):
            try:
                async with self.session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers
                ) as resp:
                    # В методе _call_api, внутри блока if resp.status == 200:
                    if resp.status == 200:
                        data = await resp.json()
                        raw = data["choices"][0]["message"]["content"]
                        
                        # ✅ Извлекаем статистику токенов
                        usage_data = data.get("usage", {})
                        token_usage = TokenUsage(
                            prompt_tokens=usage_data.get("prompt_tokens", 0),
                            completion_tokens=usage_data.get("completion_tokens", 0),
                            total_tokens=usage_data.get("total_tokens", 0)
                        )
                        
                        try:
                            cleaned = await self._clean_json(raw)
                            return True, json.loads(cleaned), "", token_usage  # ✅ Возвращаем 4 значения
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON decode failed. Raw: {raw[:200]}...")
                            return False, None, f"AI вернул невалидный JSON: {e}", None
                    
                    
                    elif resp.status == 429:
                        wait = 2 ** attempt
                        logger.warning(f"429. Retry {attempt+1} in {wait}s")
                        await asyncio.sleep(wait)
                    else:
                        error_text = await resp.text()
                        return False, None, f"HTTP {resp.status}: {error_text[:300]}"
            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    return False, None, "Timeout after retries"
            except aiohttp.ClientError as e:
                return False, None, f"Network error: {e}"
            except Exception as e:
                logger.exception("Unexpected error in _call_api")
                return False, None, f"Unexpected error: {type(e).__name__}: {e}"
        
        return False, None, "Max retries exceeded"

    async def generate_quiz_question(self, md_text: str) -> Tuple[bool, Dict, str, Optional[TokenUsage]]:
        system = "Return strictly valid JSON with keys 'question' and 'correct_answer'. No extra text."
        safe_text = md_text[:3000]
        prompt = f"Generate ONE clear quiz question and its exact correct answer based on this text:\n{safe_text}"
        return await self._call_api(prompt, system)


    async def evaluate_answer(self, question: str, correct: str, user: str) -> Tuple[bool, Dict, str, Optional[TokenUsage]]:
        system = "Return strictly valid JSON with keys: 'correctness' (one of: 'правильно','частично','неправильно'), 'feedback' (short explanation in Russian), 'rating' (1-5)."
        prompt = f"Question: {question}\nCorrect: {correct}\nUser: {user}\nEvaluate and return JSON only."
        return await self._call_api(prompt, system)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

# Синглтон для удобного импорта
ai_client = AIConnector()

