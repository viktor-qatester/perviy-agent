"""Habr Career must not treat Middle/Senior/Lead listings as internships."""

from __future__ import annotations

import unittest

from src.sources.habr_career import _extract_grade, _matches_qa_junior, _parse_cards

# Live Habr cards put the grade chip after company/rating markup (often >2000 chars
# from aria-label). This fixture keeps that distance so a short slice would miss it.
_PADDING = "x" * 2400

_SENIOR_CARD = f"""
<div class="vacancy-card">
<a aria-label="QA Automation-инженер" class="vacancy-card__backdrop-link" href="/vacancies/1000166782"></a>
<div class="vacancy-card__inner">
<div class="vacancy-card__company"><a class="link-comp" href="/companies/agima">AGIMA</a>{_PADDING}</div>
<div class="vacancy-card__title"><a class="vacancy-card__title-link" href="/vacancies/1000166782">QA Automation-инженер</a></div>
<div class="vacancy-card__meta"><div class="vacancy-meta">
<div class="basic-chip">
<div class="chip-with-icon__icon">
<svg class="svg-icon svg-icon--icon-grade"></svg>
</div>
<div class="chip-with-icon__text">Senior</div>
</div>
</div></div>
</div></div>
"""

_JUNIOR_CARD = """
<div class="vacancy-card">
<a aria-label="QA инженер" class="vacancy-card__backdrop-link" href="/vacancies/1000128807"></a>
<div class="vacancy-card__inner">
<div class="vacancy-card__title"><a href="/vacancies/1000128807">QA инженер</a></div>
<div class="vacancy-card__meta"><div class="vacancy-meta">
<div class="basic-chip">
<div class="chip-with-icon__icon">
<svg class="svg-icon svg-icon--icon-grade"></svg>
</div>
<div class="chip-with-icon__text">Junior</div>
</div>
</div></div>
</div></div>
"""

_MIDDLE_CARD = """
<div class="vacancy-card">
<a aria-label="QA инженер" class="vacancy-card__backdrop-link" href="/vacancies/1000168414"></a>
<div class="vacancy-card__meta">
<svg class="svg-icon svg-icon--icon-grade"></svg>
<div class="chip-with-icon__text">Middle</div>
</div>
</div>
"""


class HabrGradeFilterTests(unittest.TestCase):
    def test_senior_grade_rejected_even_on_intern_search(self) -> None:
        self.assertFalse(
            _matches_qa_junior(
                "QA Automation-инженер",
                require_junior_hint=False,
                grade="Senior",
            )
        )

    def test_middle_grade_rejected(self) -> None:
        self.assertFalse(
            _matches_qa_junior("QA инженер", require_junior_hint=False, grade="Middle")
        )

    def test_lead_grade_rejected(self) -> None:
        self.assertFalse(
            _matches_qa_junior(
                "QA Lead / Руководитель отдела тестирования",
                require_junior_hint=False,
                grade="Lead",
            )
        )

    def test_junior_grade_keeps_title_without_junior_word(self) -> None:
        self.assertTrue(
            _matches_qa_junior("QA инженер", require_junior_hint=False, grade="Junior")
        )

    def test_intern_grade_kept(self) -> None:
        self.assertTrue(
            _matches_qa_junior("QA Engineer", require_junior_hint=False, grade="Intern")
        )

    def test_missing_grade_requires_junior_in_title(self) -> None:
        self.assertFalse(
            _matches_qa_junior("QA инженер", require_junior_hint=False, grade=None)
        )
        self.assertTrue(
            _matches_qa_junior("QA Intern", require_junior_hint=False, grade=None)
        )

    def test_parse_extracts_senior_chip_beyond_old_2000_char_window(self) -> None:
        cards = _parse_cards(_SENIOR_CARD)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].grade, "Senior")
        self.assertFalse(
            _matches_qa_junior(
                cards[0].title,
                require_junior_hint=False,
                grade=cards[0].grade,
            )
        )

    def test_parse_junior_and_middle_chips(self) -> None:
        html = _JUNIOR_CARD + _MIDDLE_CARD
        cards = {c.vacancy_id: c for c in _parse_cards(html)}
        self.assertEqual(cards["1000128807"].grade, "Junior")
        self.assertEqual(cards["1000168414"].grade, "Middle")
        self.assertTrue(
            _matches_qa_junior(
                cards["1000128807"].title,
                require_junior_hint=False,
                grade=cards["1000128807"].grade,
            )
        )
        self.assertFalse(
            _matches_qa_junior(
                cards["1000168414"].title,
                require_junior_hint=False,
                grade=cards["1000168414"].grade,
            )
        )

    def test_extract_grade_from_icon(self) -> None:
        self.assertEqual(_extract_grade(_SENIOR_CARD), "Senior")
        self.assertEqual(_extract_grade(_JUNIOR_CARD), "Junior")


if __name__ == "__main__":
    unittest.main()
