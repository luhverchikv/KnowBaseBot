# database/models.py
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, String, Text, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .engine import Base

# ==========================================
# 👤 Пользователи
# ==========================================
class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("difficulty IN ('easy', 'medium', 'hard')", name="chk_user_difficulty"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    max_files: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("3"))
    max_file_size_mb: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0.25"))
    max_questions_per_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    reminders: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))  # 0/1
    difficulty: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'medium'"))

    def __repr__(self) -> str:
        return f"<User(id={self.id}, tg_id={self.user_id}, diff={self.difficulty})>"

# ==========================================
# 📝 Вопросы квиза
# ==========================================
class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        CheckConstraint("correctness IN ('правильно','частично','неправильно')", name="chk_correctness"),
        CheckConstraint("rating BETWEEN 0 AND 5", name="chk_rating"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    source_file: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    user_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    correctness: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Токены генерации
    gen_prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    gen_completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    gen_total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # Токены оценки
    eval_prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    eval_completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    eval_total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

# ==========================================
# 💬 Отзывы
# ==========================================
class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    is_read: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    
    
    
    
# ==========================================
# 💾 Файлы
# ==========================================

class File(Base):
    __tablename__ = "files"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(500))
    file_path: Mapped[str] = mapped_column(String(1000))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

