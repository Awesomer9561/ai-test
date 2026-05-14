"""AI-powered question generation using Ollama — validates output with Pydantic."""

import json
import logging
from tenacity import retry, stop_after_attempt, wait_fixed

from app.config import settings
from app.ai.ollama_client import ollama
from app.ai.prompts import SYSTEM_QGEN_BANKING, SYSTEM_QGEN_UG, PROMPT_QGEN, PROMPT_EXPLANATION
from app.schemas import GeneratedQuestion

logger = logging.getLogger(__name__)


class QuestionGenerator:
    """Generates IBPS-style MCQs via local Ollama models."""

    UG_SUBJECTS = {"physics", "chemistry", "mathematics", "cuet english", "cuet general test"}

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    async def generate_questions(
        self,
        subject: str,
        topic: str,
        count: int = 3,
        difficulty: int = 3,
        avoid_stems: list[str] | None = None,
    ) -> list[GeneratedQuestion]:
        """
        Generate MCQs for a given topic.
        Routes to math model for Quant/Physics/Chemistry/Maths, general 7B for everything else.
        Validates each question against the Pydantic schema.
        """
        is_ug = subject.lower() in self.UG_SUBJECTS
        system_prompt = SYSTEM_QGEN_UG if is_ug else SYSTEM_QGEN_BANKING
        exam_type = "JEE/WBJEE/CUET" if is_ug else "IBPS/SBI Banking"
        model = settings.get_model_for_subject(subject)
        avoid_text = "\n".join(f"- {s[:80]}" for s in (avoid_stems or [])[:10]) or "None"

        prompt = PROMPT_QGEN.format(
            count=count,
            exam_type=exam_type,
            subject=subject,
            topic=topic,
            difficulty=difficulty,
            avoid_stems=avoid_text,
        )

        logger.info(f"Generating {count} questions for {subject}/{topic} (difficulty={difficulty}) using {model}")

        response = await ollama.generate(
            prompt=prompt,
            model=model,
            system=system_prompt,
            temperature=0.7,
            format_json=True,
        )

        # Parse the JSON response
        questions = self._parse_response(response, count)
        logger.info(f"Successfully generated {len(questions)} valid questions for {topic}")
        return questions

    def _parse_response(self, response: str, expected_count: int) -> list[GeneratedQuestion]:
        """Parse and validate the LLM JSON output."""
        try:
            data = json.loads(response)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed: {e}. Response: {response[:200]}")
            raise ValueError(f"LLM returned invalid JSON: {e}")

        # Handle both single object and array responses
        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            raise ValueError(f"Unexpected response type: {type(data)}")

        # Validate each question
        valid_questions = []
        for item in data:
            try:
                q = GeneratedQuestion.model_validate(item)
                # Extra sanity checks
                if len(set(q.options)) < 3:
                    logger.warning(f"Skipping question with too many duplicate options: {q.stem[:50]}")
                    continue
                if len(q.stem) < 15:
                    logger.warning(f"Skipping question with very short stem: {q.stem}")
                    continue
                valid_questions.append(q)
            except Exception as e:
                logger.warning(f"Validation failed for item: {e}")
                continue

        if not valid_questions:
            raise ValueError("No valid questions produced by LLM")

        return valid_questions[:expected_count]

    async def generate_explanation(
        self,
        stem: str,
        options: list[str],
        correct_index: int,
        user_answer_index: int | None,
        subject: str = "",
    ) -> str:
        """Generate a personalized explanation for a question."""
        letters = ["A", "B", "C", "D"]
        correct_option = options[correct_index]
        correct_letter = letters[correct_index]

        if user_answer_index is not None and user_answer_index != correct_index:
            user_option = options[user_answer_index]
            user_letter = letters[user_answer_index]
        else:
            user_option = "N/A (correct or skipped)"
            user_letter = "-"

        is_ug = subject.lower() in self.UG_SUBJECTS
        exam_type = "JEE/WBJEE/CUET" if is_ug else "IBPS/SBI Banking"

        prompt = PROMPT_EXPLANATION.format(
            exam_type=exam_type,
            stem=stem,
            options="\n".join(f"  {letters[i]}. {opt}" for i, opt in enumerate(options)),
            correct_option=correct_option,
            correct_letter=correct_letter,
            user_option=user_option,
            user_letter=user_letter,
        )

        response = await ollama.generate(
            prompt=prompt,
            model=settings.model_live,  # Use fast model for explanations
            temperature=0.3,
        )

        return response.strip()


# Singleton
question_generator = QuestionGenerator()
