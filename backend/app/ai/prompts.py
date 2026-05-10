"""Prompt templates for LLM calls — question generation, explanation, etc."""

SYSTEM_QGEN = """You are an expert question paper setter for Indian banking exams (IBPS PO, Clerk, SBI PO, RRB).
You create high-quality MCQs that match the exact style, difficulty, and patterns seen in real IBPS exams.
Always respond with valid JSON only — no markdown, no commentary outside the JSON."""

PROMPT_QGEN = """Generate {count} unique MCQ(s) for the following:
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
    "stem": "What is the simple interest on Rs. 5000 at 8% per annum for 3 years?",
    "options": ["Rs. 1000", "Rs. 1200", "Rs. 1400", "Rs. 800"],
    "correct_index": 1,
    "explanation": "SI = P × R × T / 100 = 5000 × 8 × 3 / 100 = Rs. 1200.",
    "difficulty": 2
  }}
]

Avoid these stems (already in the bank):
{avoid_stems}

Generate exactly {count} question(s) now:"""

PROMPT_EXPLANATION = """You are an expert IBPS exam tutor. A student answered a question and needs a clear explanation.

Question: {stem}
Options: {options}
Correct answer: {correct_option} (option {correct_letter})
Student's answer: {user_option} (option {user_letter})

Provide:
1. A clear step-by-step solution showing why the correct answer is right.
2. If the student was wrong, explain why their chosen option is incorrect.

Keep it concise (3-5 sentences). Use simple language suitable for exam prep."""
