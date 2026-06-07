# logic/prompts.py

# ==================== СЛОВАРЬ СЛОЖНОСТЕЙ ====================
QUIZ_DIFFICULTY_PROMPTS = {
    'easy': "Вопрос должен быть простым, прямым и проверять базовое запоминание фактов. Подходит для новичков.",
    'medium': "Вопрос должен быть умеренно сложным, требовать понимания материала и применения знаний на практике.",
    'hard': "Вопрос должен быть сложным, требовать глубокого анализа, синтеза информации или оценки нескольких концепций одновременно."
}

# ==================== ГЕНЕРАЦИЯ ОДНОГО ВОПРОСА ====================
QUIZ_GENERATION_SYSTEM_PROMPT = (
    "Return strictly valid JSON with keys 'question' and 'correct_answer'. No extra text.\n"
    "CRITICAL: The question and answer MUST be written in RUSSIAN language (same as source text).\n"
    "Difficulty level: {difficulty}. {diff_instr}"
)

QUIZ_GENERATION_USER_PROMPT = (
    "Generate ONE clear quiz question and its exact correct answer based on this text:\n"
    "{safe_text}"
)

# ==================== ГЕНЕРАЦИЯ ПУЛА ВОПРОСОВ (УЛУЧШЕННЫЙ) ====================
QUIZ_POOL_SYSTEM_PROMPT = (
    "Return STRICTLY a valid JSON array of {count} objects. "
    "Each object MUST have exactly two keys: 'question' (string) and 'correct_answer' (string). "
    "No extra text, no markdown formatting outside the JSON array.\n"
    "CRITICAL REQUIREMENTS:\n"
    "1. ALL questions and answers MUST be written in RUSSIAN language (same as source text). Never use English.\n"
    "2. Questions MUST cover DIFFERENT topics/aspects from the text. Do NOT generate multiple questions about the same concept.\n"
    "3. First, mentally identify all key topics/sections in the text, then distribute questions evenly across them to maximize coverage.\n"
    "4. Each question must be unique and non-repetitive.\n"
    "Difficulty level: {difficulty}. {diff_instr}"
)

QUIZ_POOL_USER_PROMPT = (
    "Generate {count} distinct quiz questions covering ALL different topics from this text:\n"
    "{safe_text}"
)

# ==================== ОЦЕНКА ОТВЕТА ====================
EVALUATION_SYSTEM_PROMPT = (
    "Return strictly valid JSON with keys: 'correctness' (one of: 'правильно','частично','неправильно'), "
    "'feedback' (short explanation in Russian), 'rating' (1-5).\n"
    "Be fair but strict: 'частично' is for answers that are mostly correct but miss important details."
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

