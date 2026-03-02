"""
tools/validators.py — Cross-validate LLM numeric outputs against tool outputs.
Tools always win on numbers. Discrepancies are logged and flagged.
"""
import re
from decimal import Decimal, InvalidOperation

from backend.app.models.schemas import ValidatorResult, ValidationDiscrepancy

_ONE_PCT = Decimal("0.01")
_TEN_PCT = Decimal("0.10")


def _extract_numbers_from_text(text: str) -> dict[str, Decimal]:
    """
    Extract key=value numeric pairs from LLM output text.
    Looks for patterns like 'runway: 8.5', 'burn rate: $45,000', etc.
    """
    numbers: dict[str, Decimal] = {}

    # Match patterns like "runway: 8.5 months", "burn rate: $45,000"
    pattern = re.compile(
        r"([\w\s]+?):\s*\$?([\d,]+(?:\.\d+)?)\s*(?:months?|%|k|M)?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        key = match.group(1).strip().lower().replace(" ", "_")
        raw = match.group(2).replace(",", "")
        try:
            numbers[key] = Decimal(raw)
        except InvalidOperation:
            pass

    return numbers


def cross_validate(
    tool_numbers: dict[str, Decimal],
    llm_text: str,
) -> ValidatorResult:
    """
    Extract numbers from LLM text and compare against tool-calculated values.

    Rules:
    - Discrepancy > 1%  → WARNING
    - Discrepancy > 10% → ERROR
    - Tool numbers always win in final output.
    """
    llm_numbers = _extract_numbers_from_text(llm_text)
    discrepancies: list[ValidationDiscrepancy] = []

    for field, tool_val in tool_numbers.items():
        normalized_field = field.lower().replace(" ", "_")
        if normalized_field not in llm_numbers:
            continue

        llm_val = llm_numbers[normalized_field]

        if tool_val == Decimal("0"):
            if llm_val != Decimal("0"):
                pct = Decimal("999")
            else:
                continue
        else:
            pct = abs(tool_val - llm_val) / abs(tool_val)

        if pct > _ONE_PCT:
            severity = "ERROR" if pct > _TEN_PCT else "WARNING"
            discrepancies.append(ValidationDiscrepancy(
                field=field,
                tool_value=tool_val,
                llm_value=llm_val,
                discrepancy_pct=pct * Decimal("100"),
                severity=severity,
            ))

    return ValidatorResult(
        discrepancies=discrepancies,
        is_clean=len(discrepancies) == 0,
    )
