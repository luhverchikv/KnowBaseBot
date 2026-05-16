# logic/ai_connector.py

import json
import asyncio
import aiohttp
from typing import Dict, Tuple, Optional
from config import config
from utils.logger import logger

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
        # ✅ Правильная проверка на три обратных кавычки
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("\n", 1)[0]
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
                    if resp.status == 200:
                        data = await resp.json()
                        raw = data["choices"][0]["message"]["content"]
                        return True, json.loads(await self._clean_json(raw)), ""
                    elif resp.status == 429:
                        wait = 2 ** attempt
                        logger.warning(f"429. Retry {attempt+1} in {wait}s")
                        await asyncio.sleep(wait)
                    else:
                        return False, None, f"HTTP {resp.status}: {await resp.text()}"
            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    return False, None, "Timeout"
            except aiohttp.ClientError as e:
                return False, None, f"Network: {e}"
            except Exception as e:
                return False, None, f"Error: {e}"
        return False, None, "Max retries"

    async def generate_quiz_question(self, md_text: str) -> Tuple[bool, Dict, str]:
        system = "Return strictly valid JSON with keys 'question' and 'correct_answer'. No extra text."
        prompt = f"Generate ONE clear quiz question and its exact correct answer based on this text:\n{md_text[:3000]}"
        return await self._call_api(prompt, system)

    async def evaluate_answer(self, question: str, correct: str, user: str) -> Tuple[bool, Dict, str]:
        system = "Return strictly valid JSON with keys: 'correctness' (one of: 'правильно','частично','неправильно'), 'feedback' (short explanation in Russian), 'rating' (1-5)."
        prompt = f"Question: {question}\nCorrect: {correct}\nUser: {user}\nEvaluate."
        return await self._call_api(prompt, system)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

# Синглтон для удобного импорта
ai_client = AIConnector()


