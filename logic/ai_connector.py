# logic/ai_connector.py
import aiohttp
import json
from config import config
from utils.logger import logger

async def _call_ai(prompt: str, system_prompt: str = "You are a helpful assistant.") -> str:
    headers = {
        "Authorization": f"Bearer {config.ai.api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": config.ai.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(config.ai.api_url, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["choices"][0]["message"]["content"]

async def generate_quiz_question(md_text: str) -> dict:
    """Генерирует вопрос и ответ по Markdown тексту."""
    # Обрезаем текст, чтобы не превысить контекстное окно
    safe_text = md_text[:3000]
    prompt = f"Based on this Markdown knowledge base, generate ONE clear quiz question and its correct answer. Return ONLY valid JSON with keys 'question' and 'correct_answer'.\n\nText:\n{safe_text}"
    system = "You are an expert quiz generator. Return strictly JSON."
    
    response = await _call_ai(prompt, system)
    try:
        clean = response.replace("
```json", "").replace("
```", "").strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        logger.warning(f"AI returned invalid JSON: {response}")
        return {"question": "Ошибка генерации вопроса.", "correct_answer": "N/A"}

async def evaluate_answer(question: str, correct: str, user: str) -> dict:
    """Оценивает ответ пользователя."""
    prompt = f"Question: {question}\nCorrect Answer: {correct}\nUser Answer: {user}\n\nEvaluate the user's answer. Return JSON with keys: 'correctness' (one of: 'правильно','частично','неправильно'), 'feedback' (short explanation in Russian), and 'rating' (1-5)."
    system = "You are a strict but fair evaluator. Return strictly JSON."
    
    response = await _call_ai(prompt, system)
    try:
        clean = response.replace("
```json", "").replace("
```", "").strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"correctness": "неправильно", "feedback": "Не удалось оценить ответ.", "rating": 1}

