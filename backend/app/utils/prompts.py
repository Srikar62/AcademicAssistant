"""
Prompt templates for LLM interactions.

All prompts are kept in one place so they're easy to review, iterate on,
and swap without touching business logic.
"""

# ═══════════════════════════════════════════════════════════════
#  Q&A (RAG-grounded)
# ═══════════════════════════════════════════════════════════════

QA_SYSTEM_PROMPT = """\
You are an expert academic tutor. Answer the student's question using ONLY \
the provided context from their study materials. Follow these rules strictly:

1. Base your answer entirely on the provided context chunks.
2. If the context does not contain enough information to answer, say so clearly \
   — do NOT fabricate information.
3. Cite your sources using the format [Source: <label>] where <label> is the \
   source label (e.g., "Page 3", "Slide 7") provided with each chunk.
4. Structure your answer clearly with paragraphs or bullet points as appropriate.
5. Use precise academic language suitable for a university student.
6. If the question is ambiguous, address the most likely interpretation and \
   note the ambiguity.
"""

QA_USER_PROMPT_TEMPLATE = """\
## Context from study materials

{context}

---

## Student's Question

{question}

---

Please provide a well-structured answer based on the context above. \
Include [Source: <label>] citations for every factual claim.
"""


def format_context_chunks(chunks: list, max_total_chars: int = 10000) -> str:
    """
    Format retrieved chunks into a numbered context block for the prompt,
    safely capped at max_total_chars to prevent LLM TPM / payload overflow.

    Args:
        chunks: List of dicts with 'text', 'source_label', 'original_filename', etc.
        max_total_chars: Max character length for total formatted context (~2500 tokens).

    Returns:
        Formatted string suitable for insertion into prompt templates.
    """
    parts = []
    total_chars = 0

    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source_label", f"Chunk {i}")
        filename = chunk.get("original_filename", "")
        text = chunk.get("text", "")

        header = f"### Chunk {i} — {source}"
        if filename:
            header += f" (from {filename})"

        block = f"{header}\n{text}"
        if total_chars + len(block) > max_total_chars:
            remaining = max_total_chars - total_chars
            if remaining > 100:
                parts.append(f"{header}\n{text[:remaining]}...")
            break

        parts.append(block)
        total_chars += len(block)

    return "\n\n".join(parts)


def build_qa_messages(question: str, chunks: list) -> list:
    """
    Build the full message list for a RAG Q&A request.

    Args:
        question: The student's question.
        chunks: Retrieved context chunks.

    Returns:
        List of message dicts ready for the LLM client.
    """
    context = format_context_chunks(chunks)
    return [
        {"role": "system", "content": QA_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": QA_USER_PROMPT_TEMPLATE.format(
                context=context, question=question
            ),
        },
    ]


# ═══════════════════════════════════════════════════════════════
#  Quiz Generation
# ═══════════════════════════════════════════════════════════════

QUIZ_SYSTEM_PROMPT = """\
You are an expert academic quiz generator. Create multiple-choice questions \
based ONLY on the provided study material context. Follow these rules:

1. Each question must be answerable from the provided context.
2. Create exactly the number of questions requested.
3. Each question must have exactly 4 options labeled A, B, C, D.
4. Exactly one option must be correct.
5. Include a brief explanation for the correct answer.
6. Vary question difficulty (mix recall, understanding, and application).
7. Do NOT fabricate facts — only test knowledge present in the context.

Respond with valid JSON in this exact format:
{
  "questions": [
    {
      "question": "question text",
      "options": ["A) option1", "B) option2", "C) option3", "D) option4"],
      "correct_answer": "A",
      "explanation": "brief explanation",
      "source_label": "Page 3"
    }
  ]
}
"""

QUIZ_USER_PROMPT_TEMPLATE = """\
## Study Material Context

{context}

---

Generate {num_questions} multiple-choice quiz questions{topic_clause} \
based on the context above. Return valid JSON only.
"""


def build_quiz_messages(
    chunks: list, num_questions: int = 5, topic: str = None
) -> list:
    """Build messages for quiz generation."""
    context = format_context_chunks(chunks)
    topic_clause = f" about {topic}" if topic else ""
    return [
        {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": QUIZ_USER_PROMPT_TEMPLATE.format(
                context=context,
                num_questions=num_questions,
                topic_clause=topic_clause,
            ),
        },
    ]


# ═══════════════════════════════════════════════════════════════
#  Summarization (map-reduce)
# ═══════════════════════════════════════════════════════════════

SUMMARIZE_MAP_SYSTEM_PROMPT = """\
You are an expert academic summarizer. Summarize the provided study \
material section concisely, preserving all key concepts, definitions, \
and important details. Use clear academic language.
"""

SUMMARIZE_MAP_USER_TEMPLATE = """\
Summarize the following section from the study materials:

{chunk_text}

Provide a concise summary that captures all important points.
"""

SUMMARIZE_REDUCE_SYSTEM_PROMPT = """\
You are an expert academic summarizer. You will be given multiple \
section summaries from a study document. Synthesize them into one \
coherent, well-structured summary.

Respond with valid JSON in this exact format:
{
  "summary": "The full synthesized summary text here...",
  "key_points": [
    "Key point 1",
    "Key point 2",
    "Key point 3"
  ]
}
"""

SUMMARIZE_REDUCE_USER_TEMPLATE = """\
## Section Summaries

{section_summaries}

---

Synthesize these section summaries into one {length} summary. \
Extract 5-10 key points as bullet highlights. \
{topic_clause}Return valid JSON only.
"""


def build_summarize_map_messages(chunk_text: str) -> list:
    """Build messages for the map step (summarize one chunk group)."""
    return [
        {"role": "system", "content": SUMMARIZE_MAP_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": SUMMARIZE_MAP_USER_TEMPLATE.format(chunk_text=chunk_text),
        },
    ]


def build_summarize_reduce_messages(
    section_summaries: list,
    length: str = "medium",
    topic: str = None,
) -> list:
    """Build messages for the reduce step (synthesize summaries)."""
    summaries_text = "\n\n".join(
        f"### Section {i + 1}\n{s}" for i, s in enumerate(section_summaries)
    )
    topic_clause = f"Focus on aspects related to {topic}. " if topic else ""

    length_map = {
        "brief": "brief (2-3 paragraphs)",
        "medium": "medium-length (4-6 paragraphs)",
        "detailed": "detailed and comprehensive (8-10 paragraphs)",
    }
    length_desc = length_map.get(length, length_map["medium"])

    return [
        {"role": "system", "content": SUMMARIZE_REDUCE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": SUMMARIZE_REDUCE_USER_TEMPLATE.format(
                section_summaries=summaries_text,
                length=length_desc,
                topic_clause=topic_clause,
            ),
        },
    ]


# ═══════════════════════════════════════════════════════════════
#  Mind Map
# ═══════════════════════════════════════════════════════════════

MINDMAP_SYSTEM_PROMPT = """\
You are an expert at extracting hierarchical concept structures from \
academic material. Given study material context, extract a mind map \
as a tree of concepts.

Respond with valid JSON in this exact format:
{
  "root": {
    "label": "Main Topic",
    "children": [
      {
        "label": "Subtopic 1",
        "children": [
          {"label": "Detail 1a", "children": []},
          {"label": "Detail 1b", "children": []}
        ]
      },
      {
        "label": "Subtopic 2",
        "children": [
          {"label": "Detail 2a", "children": []}
        ]
      }
    ]
  }
}

Rules:
1. The root node should be the main topic/subject.
2. Create 3-6 major subtopics as children of the root.
3. Each subtopic should have 2-5 detail nodes.
4. Keep labels concise (3-8 words each).
5. Go at most 4 levels deep.
6. Only include concepts present in the provided context.
"""

MINDMAP_USER_PROMPT_TEMPLATE = """\
## Study Material Context

{context}

---

Extract a hierarchical mind map{topic_clause} from the context above. \
Return valid JSON only.
"""


def build_mindmap_messages(chunks: list, topic: str = None) -> list:
    """Build messages for mind map generation."""
    context = format_context_chunks(chunks)
    topic_clause = f" focused on {topic}" if topic else ""
    return [
        {"role": "system", "content": MINDMAP_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": MINDMAP_USER_PROMPT_TEMPLATE.format(
                context=context,
                topic_clause=topic_clause,
            ),
        },
    ]

