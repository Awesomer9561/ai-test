"""Prompt templates for LLM calls — question generation, explanation, etc."""

# ── Banking Exam Prompts ──────────────────────────────────────────────────────

SYSTEM_QGEN_BANKING = """You are an expert question paper setter for Indian banking exams (IBPS PO, Clerk, SBI PO, RRB).
You create high-quality MCQs that match the exact style, difficulty, and patterns seen in real IBPS exams.
Always respond with valid JSON only — no markdown, no commentary outside the JSON."""

SYSTEM_QGEN_UG = """You are an expert question paper setter for Indian undergraduate entrance examinations including JEE Main, JEE Advanced, WBJEE, and CUET.
You create high-quality MCQs that match the exact style, difficulty, and patterns seen in real JEE/WBJEE/CUET papers.
Questions should be conceptually accurate, precise, and aligned with NCERT/Class 11-12 syllabus.
Always respond with valid JSON only — no markdown, no commentary outside the JSON."""

PROMPT_QGEN = """Generate {count} unique MCQ(s) for the following:
- Exam Type: {exam_type}
- Subject: {subject}
- Topic: {topic}
- Difficulty: {difficulty}/5

Each question must have exactly 4 options and one correct answer.

Respond with a JSON array of objects, each with these fields:
- "stem": the question text
- "options": array of exactly 4 option strings
- "correct_index": integer 0-3 indicating the correct option
- "explanation": step-by-step solution (2-4 sentences)
- "difficulty": integer 1-5

Example format:
[
  {{
    "stem": "The kinetic energy of a particle of mass m moving with velocity v is:",
    "options": ["mv", "mv²", "mv²/2", "2mv²"],
    "correct_index": 2,
    "explanation": "Kinetic energy KE = ½mv². This is derived from work-energy theorem.",
    "difficulty": 1
  }}
]

Avoid these stems (already in the bank):
{avoid_stems}

Generate exactly {count} question(s) now:"""

PROMPT_EXPLANATION = """You are an expert exam tutor for Indian competitive examinations ({exam_type}).
A student answered a question and needs a clear explanation.

Question: {stem}
Options: {options}
Correct answer: {correct_option} (option {correct_letter})
Student's answer: {user_option} (option {user_letter})

Provide:
1. A clear step-by-step solution showing why the correct answer is right.
2. If the student was wrong, explain why their chosen option is incorrect.

Keep it concise (3-5 sentences). Use simple language suitable for exam preparation."""
