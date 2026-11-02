"""Typed, whole-question grammar for deterministic descriptive analytics.

Every accepted token belongs to a named grammar rule. No keyword extraction,
LLM execution, partial-match fallback, or silent removal of business qualifiers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import unicodedata


@dataclass(frozen=True)
class QuestionIntent:
    measure_alias: str
    aggregation: str
    dimension_alias: str | None
    direction: str | None
    grammar_rule: str
    normalized_question: str

    def to_dict(self):
        return asdict(self)


BLOCKED = re.compile(r"\b(?:last|next|yesterday|today|tomorrow|monthly|weekly|daily|yearly|quarterly|since|before|after|during|between|forecast|predict|projection|cause|caused|why|because|growth|increase|decrease|change|correlation|ratio|percent|percentage|margin|excluding|exclude|except|only|without|where|when|if|in|and|versus|vs)\b|\b(?:19|20)\d{2}\b")


def normalize_question(question):
    if not isinstance(question, str) or len(question) > 2000:
        return None
    text = unicodedata.normalize("NFKC", question).lower().strip()
    text = re.sub(r"^what['’]s\b", "what is", text)
    text = text.rstrip("?!. ")
    text = re.sub(r"_+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # The word 'in' is consumed only in the explicit earning verb, never as a filter.
    guarded = re.sub(r"\bbrought in\b", "brought", text)
    if re.search(r"[^a-z0-9 ]", text) or BLOCKED.search(guarded):
        return None
    text = re.sub(r"^please ", "", text)
    text = re.sub(r"^(?:can|could|would) you (?:please )?", "", text)
    text = re.sub(r" please$", "", text)
    return text


def parse_question(question, measures, dimensions):
    text = normalize_question(question)
    if not text:
        return None
    measure = "|".join(re.escape(name) for name in sorted(measures, key=len, reverse=True))
    dimension = "|".join(re.escape(name) for name in sorted(dimensions, key=len, reverse=True))
    if not measure or not dimension:
        return None
    m = rf"(?P<measure>{measure})"
    d = rf"(?P<dimension>{dimension})"
    prefix = r"(?:(?:what is|what are|show(?: me)?|calculate|give me|tell me|compute|report|can i see)(?: (?:the|our|my))? )?"
    agg = r"(?:(?P<aggregation>total|sum|average|mean) (?:of )?(?:(?:the|our|my) )?)?"
    grouping = rf"(?: (?:by|per|for each|for every|for each of the|grouped by|broken down by) {d})?"
    rank = r"(?P<rank>highest|lowest|most|least|maximum|minimum|largest|smallest)"
    rules = [
        ("aggregate", prefix + agg + m + grouping),
        ("all_groups_total", prefix + r"(?:(?P<aggregation>total|sum) (?:of )?)?" + m + rf" across all {d}"),
        ("earned_amount", rf"how much {m}(?:(?: (?:did|do) (?:we|i) (?:earn|make|generate|record|spend))|(?: have we (?:earned|made|generated|recorded|spent)))?"),
        ("ranked_group", rf"(?:which|what) {d} (?:has|have|earned|generated|produced|recorded|made|delivered|brought in) (?:the )?{rank} (?:(?P<aggregation>average|mean|total|sum) )?{m}"),
        ("ranked_modifier", prefix + rank + rf" {d} (?:(?P<aggregation>total|sum) )?{m}"),
        ("group_with_rank", prefix + d + rf" with (?:the )?{rank} (?:(?P<aggregation>average|mean|total|sum) )?{m}"),
        ("grouped_listing", rf"(?:list|break down) {m} by {d}"),
        ("measure_totals", prefix + m + rf" (?P<aggregation>totals|averages){grouping}"),
    ]
    matches = {}
    for name, pattern in rules:
        match = re.fullmatch(pattern, text)
        if match is None:
            continue
        fields = match.groupdict()
        aggregation = "mean" if fields.get("aggregation") in {"average", "mean", "averages"} else "sum"
        direction = ("lowest" if fields.get("rank") in {"lowest", "least", "minimum", "smallest"} else "highest") if fields.get("rank") else None
        dim = None if name == "all_groups_total" else fields.get("dimension")
        intent = QuestionIntent(fields["measure"], aggregation, dim, direction, name, text)
        matches[(intent.measure_alias, aggregation, dim, direction)] = intent
    return next(iter(matches.values())) if len(matches) == 1 else None
