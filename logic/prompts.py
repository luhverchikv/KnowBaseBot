# logic/prompts.py

# ==================== ВИКТОРИНА ====================
QUIZ_DIFFICULTY_PROMPTS = {
    'easy': "Вопрос должен быть простым, прямым и проверять базовое запоминание фактов. Подходит для новичков.",
    'medium': "Вопрос должен быть умеренно сложным, требовать понимания материала и применения знаний на практике.",
    'hard': "Вопрос должен быть сложным, требовать глубокого анализа, синтеза информации или оценки нескольких концепций одновременно."
}

QUIZ_GENERATION_SYSTEM_PROMPT = (
    "Return strictly valid JSON with keys 'question' and 'correct_answer'. No extra text.\n"
    "Difficulty level: {difficulty}. {diff_instr}"
)

QUIZ_GENERATION_USER_PROMPT = (
    "Generate ONE clear quiz question and its exact correct answer based on this text:\n"
    "{safe_text}"
)

# ==================== ОЦЕНКА ОТВЕТА ====================
EVALUATION_SYSTEM_PROMPT = (
    "Return strictly valid JSON with keys: 'correctness' (one of: 'правильно','частично','неправильно'), "
    "'feedback' (short explanation in Russian), 'rating' (1-5)."
)

EVALUATION_USER_PROMPT = (
    "Question: {question}\n"
    "Correct: {correct}\n"
    "User: {user}\n"
    "Evaluate and return JSON only."
)

# ==================== ОПИСАНИЕ ФАЙЛА ====================
FILE_DESCRIPTION_SYSTEM_PROMPT = (
    "Вы — ассистент базы знаний. Проанализируйте текст и составьте его очень краткое описание "
    "на русском языке (1-2 предложения, максимум 150 символов), отражающее суть документа.\n"
    "Верните ответ СТРОГО в формате JSON с единственным ключом 'description'. Никакого другого текста."
)

FILE_DESCRIPTION_USER_PROMPT = (
    "Составь краткое описание для следующего текста:\n\n"
    "{safe_text}"
)
