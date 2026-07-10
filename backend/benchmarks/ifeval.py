import re
import json
import logging
from typing import Dict, Any, List
from backend.benchmarks.base import BaseBenchmark, resolve_data_file

logger = logging.getLogger(__name__)


def _check_no_comma(response: str, kwargs: dict) -> bool:
    return "," not in response


def _check_english_capital(response: str, kwargs: dict) -> bool:
    return response.isupper()


def _check_english_lowercase(response: str, kwargs: dict) -> bool:
    return response.islower()


def _check_capital_word_frequency(response: str, kwargs: dict) -> bool:
    freq = kwargs["capital_frequency"]
    relation = kwargs["capital_relation"]
    words = response.split()
    capital_count = sum(1 for w in words if w.isupper() and len(w) > 0)
    if relation == "at_least":
        return capital_count >= freq
    elif relation == "at_most":
        return capital_count <= freq
    return capital_count == freq


def _check_keywords_existence(response: str, kwargs: dict) -> bool:
    keywords = kwargs.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [keywords]
    resp_lower = response.lower()
    return all(kw.lower() in resp_lower for kw in keywords)


def _check_keywords_forbidden_words(response: str, kwargs: dict) -> bool:
    forbidden = kwargs.get("forbidden_words", [])
    if isinstance(forbidden, str):
        forbidden = [forbidden]
    resp_lower = response.lower()
    return all(fw.lower() not in resp_lower for fw in forbidden)


def _check_keywords_frequency(response: str, kwargs: dict) -> bool:
    freq = kwargs["frequency"]
    keyword = kwargs["keyword"]
    relation = kwargs["relation"]
    count = response.lower().count(keyword.lower())
    if relation == "at_least":
        return count >= freq
    elif relation == "at_most":
        return count <= freq
    return count == freq


def _check_keywords_letter_frequency(response: str, kwargs: dict) -> bool:
    letter = kwargs["letter"]
    freq = kwargs["let_frequency"]
    relation = kwargs["let_relation"]
    count = response.lower().count(letter.lower())
    if relation == "at_least":
        return count >= freq
    elif relation == "at_most":
        return count <= freq
    return count == freq


def _check_length_constraints_number_words(response: str, kwargs: dict) -> bool:
    num_words = kwargs["num_words"]
    relation = kwargs["relation"]
    count = len(response.split())
    if relation == "at_least":
        return count >= num_words
    elif relation == "at_most":
        return count <= num_words
    return count == num_words


def _check_length_constraints_number_sentences(response: str, kwargs: dict) -> bool:
    num_sentences = kwargs["num_sentences"]
    relation = kwargs["relation"]
    count = len(re.split(r'[.!?]+', response)) - 1
    count = max(count, 1 if response.strip() else 0)
    if relation == "at_least":
        return count >= num_sentences
    elif relation == "at_most":
        return count <= num_sentences
    return count == num_sentences


def _check_length_constraints_number_paragraphs(response: str, kwargs: dict) -> bool:
    num_paragraphs = kwargs["num_paragraphs"]
    relation = kwargs["relation"]
    paragraphs = [p for p in response.split("\n\n") if p.strip()]
    count = len(paragraphs) if paragraphs else 1
    if relation == "at_least":
        return count >= num_paragraphs
    elif relation == "at_most":
        return count <= num_paragraphs
    return count == num_paragraphs


def _check_length_constraints_nth_paragraph_first_word(response: str, kwargs: dict) -> bool:
    nth = kwargs["nth_paragraph"]
    first_word = kwargs["first_word"]
    paragraphs = [p.strip() for p in response.split("\n\n") if p.strip()]
    if nth < 1 or nth > len(paragraphs):
        return False
    para_words = paragraphs[nth - 1].split()
    if not para_words:
        return False
    return para_words[0].lower() == first_word.lower()


def _check_detectable_content_number_placeholders(response: str, kwargs: dict) -> bool:
    num_placeholders = kwargs["num_placeholders"]
    count = 0
    count += len(re.findall(r'\{[^}]*\}', response))
    count += len(re.findall(r'\[[^\]]*\]', response))
    count += len(re.findall(r'\([^)]*\)', response))
    return count == num_placeholders


def _check_detectable_content_postscript(response: str, kwargs: dict) -> bool:
    marker = kwargs["postscript_marker"]
    return marker in response


def _check_detectable_format_number_bullet_lists(response: str, kwargs: dict) -> bool:
    num_bullets = kwargs["num_bullets"]
    count = 0
    for line in response.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* ") or re.match(r'^\d+\.\s', stripped):
            count += 1
    return count == num_bullets


def _check_detectable_format_number_highlighted_sections(response: str, kwargs: dict) -> bool:
    num_highlights = kwargs["num_highlights"]
    count = len(re.findall(r'\*\*(.*?)\*\*', response))
    return count == num_highlights


def _check_detectable_format_json_format(response: str, kwargs: dict) -> bool:
    try:
        json.loads(response)
        return True
    except (json.JSONDecodeError, ValueError):
        stripped = response.strip()
        if (stripped.startswith("{") and stripped.endswith("}")) or \
           (stripped.startswith("[") and stripped.endswith("]")):
            try:
                json.loads(stripped)
                return True
            except (json.JSONDecodeError, ValueError):
                pass
        # Try to find JSON embedded in text
        for pattern in [r'\{.*\}', r'\[.*\]']:
            m = re.search(pattern, response, re.DOTALL)
            if m:
                try:
                    json.loads(m.group(0))
                    return True
                except (json.JSONDecodeError, ValueError):
                    continue
        return False


def _check_detectable_format_multiple_sections(response: str, kwargs: dict) -> bool:
    num_sections = kwargs["num_sections"]
    spliter = kwargs.get("section_spliter", "##")
    sections = response.split(spliter)
    sections = [s for s in sections if s.strip()]
    return len(sections) == num_sections


def _check_detectable_format_title(response: str, kwargs: dict) -> bool:
    lines = response.strip().split("\n")
    if not lines:
        return False
    first = lines[0].strip()
    if first.startswith("#"):
        return True
    if len(lines) >= 2 and re.match(r'^={3,}\s*$', lines[1].strip()):
        return True
    return False


def _check_detectable_format_constrained_response(response: str, kwargs: dict) -> bool:
    return bool(response.strip())


def _check_language_response_language(response: str, kwargs: dict) -> bool:
    logger.warning("Language response checker is a stub — always returns True")
    return True


def _check_startend_end_checker(response: str, kwargs: dict) -> bool:
    end_phrase = kwargs["end_phrase"]
    return response.strip().endswith(end_phrase)


def _check_startend_quotation(response: str, kwargs: dict) -> bool:
    stripped = response.strip()
    if len(stripped) < 2:
        return False
    if stripped.startswith('"') and stripped.endswith('"'):
        return True
    if stripped.startswith("'") and stripped.endswith("'"):
        return True
    if stripped.startswith("\u201c") and stripped.endswith("\u201d"):
        return True
    return False


def _check_combination_repeat_prompt(response: str, kwargs: dict) -> bool:
    prompt = kwargs.get("prompt", "")
    return prompt.strip() in response


def _check_combination_two_responses(response: str, kwargs: dict) -> bool:
    separators = ["---", "---", "===", "___"]
    for sep in separators:
        if sep in response:
            return True
    return False


CHECKERS = {
    "punctuation:no_comma": _check_no_comma,
    "change_case:english_capital": _check_english_capital,
    "change_case:english_lowercase": _check_english_lowercase,
    "change_case:capital_word_frequency": _check_capital_word_frequency,
    "keywords:existence": _check_keywords_existence,
    "keywords:forbidden_words": _check_keywords_forbidden_words,
    "keywords:frequency": _check_keywords_frequency,
    "keywords:letter_frequency": _check_keywords_letter_frequency,
    "length_constraints:number_words": _check_length_constraints_number_words,
    "length_constraints:number_sentences": _check_length_constraints_number_sentences,
    "length_constraints:number_paragraphs": _check_length_constraints_number_paragraphs,
    "length_constraints:nth_paragraph_first_word": _check_length_constraints_nth_paragraph_first_word,
    "detectable_content:number_placeholders": _check_detectable_content_number_placeholders,
    "detectable_content:postscript": _check_detectable_content_postscript,
    "detectable_format:number_bullet_lists": _check_detectable_format_number_bullet_lists,
    "detectable_format:number_highlighted_sections": _check_detectable_format_number_highlighted_sections,
    "detectable_format:json_format": _check_detectable_format_json_format,
    "detectable_format:multiple_sections": _check_detectable_format_multiple_sections,
    "detectable_format:title": _check_detectable_format_title,
    "detectable_format:constrained_response": _check_detectable_format_constrained_response,
    "language:response_language": _check_language_response_language,
    "startend:end_checker": _check_startend_end_checker,
    "startend:quotation": _check_startend_quotation,
    "combination:repeat_prompt": _check_combination_repeat_prompt,
    "combination:two_responses": _check_combination_two_responses,
}


class IFEvalBenchmark(BaseBenchmark):
    def __init__(self, db, client, quick_test=False):
        super().__init__(db, client, quick_test)

    def load_dataset(self) -> List[Dict[str, Any]]:
        filename = "ifeval_mini.json" if self.quick_test else "ifeval_full.json"
        self.dataset_path = resolve_data_file(__file__, filename)
        if not self.dataset_path:
            raise FileNotFoundError(
                "IFEval dataset not found. "
                "Run 'scripts/fetch_ifeval.py' to download it."
            )
        return self._load_json_cached(self.dataset_path)

    async def evaluate_sample(self, sample: Dict[str, Any], params: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        prompt = sample["prompt"]
        instruction_ids = sample.get("instruction_id_list", [])
        kwargs_list = sample.get("kwargs", [])

        gen = await self.client.generate_completion(
            prompt=prompt,
            system_prompt=params.get("system_prompt"),
            temperature=params.get("temperature", 0.0),
            max_completion_tokens=params.get("max_completion_tokens"),
            stop_tokens=params.get("stop_tokens"),
            model_name=model_name,
        )

        answer_content = gen.get("answer_content", "").strip()
        raw_response = gen.get("raw_response", "")

        response = answer_content or raw_response

        failed = []
        for i, instr_id in enumerate(instruction_ids):
            checker = CHECKERS.get(instr_id)
            if checker is None:
                failed.append(f"{instr_id}:unknown_checker")
                continue
            kw = dict(kwargs_list[i]) if i < len(kwargs_list) else {}
            if instr_id == "combination:repeat_prompt":
                kw["prompt"] = prompt
            try:
                if not checker(response, kw):
                    failed.append(instr_id)
            except Exception as e:
                failed.append(f"{instr_id}:{e}")

        correct = len(failed) == 0
        error_message = "; ".join(failed) if failed else None

        return {
            "prompt": prompt,
            "raw_response": raw_response,
            "extracted_code": answer_content,
            "correct": correct,
            "error_message": error_message,
            "elapsed_time": gen["elapsed_time"],
            "tps": gen["tps"],
            "ttft": gen["ttft"],
            "thinking_tokens": gen["thinking_tokens"],
            "response_tokens": gen["response_tokens"]
        }
