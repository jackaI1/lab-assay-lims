"""Conservative lexical suggestions; similarity is not clinical probability."""

from collections import defaultdict
from difflib import SequenceMatcher
import re
import unicodedata

from .ontology import Ontology


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    # Preserve punctuation and modifiers: dropping them can change a clinical meaning.
    return " ".join(text.split())


def trigrams(text: str) -> set[str]:
    text = f"  {text}  "
    return {text[i : i + 3] for i in range(len(text) - 2)}


class Mapper:
    def __init__(self, ontology: Ontology):
        self.ontology = ontology
        self.index: dict[str, set[str]] = defaultdict(set)
        self.grams: dict[str, set[str]] = defaultdict(set)
        for term in ontology.terms.values():
            if term.obsolete or not ontology.is_phenotype(term.id):
                continue
            for phrase in [term.name, *term.synonyms]:
                self.index[normalize(phrase)].add(term.id)
        for phrase in self.index:
            for gram in trigrams(phrase):
                self.grams[gram].add(phrase)

    def suggest(self, phrase: str) -> dict:
        query = normalize(phrase)
        if not query:
            return {"id": None, "status": "unmapped", "score": 0.0, "candidates": []}
        context = re.search(
            r"\b(no|not|denies|without|possible|possibly|suspected|maybe|history|negative)\b|\?",
            query,
        )
        if context:
            return {"id": None, "status": "context_review", "score": 0.0, "candidates": []}
        exact = self.index.get(query, set())
        if exact:
            candidates = [self._candidate(key, 1.0, query) for key in sorted(exact)]
            return {
                "id": candidates[0]["id"] if len(exact) == 1 else None,
                "status": "exact" if len(exact) == 1 else "ambiguous",
                "score": 1.0,
                "candidates": candidates,
            }
        # Bound expensive edit comparisons with a deterministic trigram shortlist.
        overlaps = defaultdict(int)
        for gram in trigrams(query):
            for text in self.grams.get(gram, ()):
                overlaps[text] += 1
        shortlist = sorted(overlaps, key=lambda text: (-overlaps[text], text))[:300]
        scores = {}
        for text in shortlist:
            score = SequenceMatcher(None, query, text, autojunk=False).ratio()
            for key in self.index[text]:
                previous = scores.get(key)
                if previous is None or score > previous[0]:
                    scores[key] = (score, text)
        candidates = [
            self._candidate(key, score, text)
            for key, (score, text) in sorted(
                scores.items(), key=lambda item: (-item[1][0], item[0])
            )[:3]
        ]
        return {
            "id": None,
            "status": "review",
            "score": candidates[0]["score"] if candidates else 0.0,
            "candidates": candidates,
        }

    def _candidate(self, key: str, score: float, matched: str) -> dict:
        return {
            "id": key,
            "label": self.ontology.terms[key].name,
            "score": round(score, 4),
            "matched_text": matched,
        }
