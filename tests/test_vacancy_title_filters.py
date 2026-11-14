"""QA intern title filters must accept Russian stems and no-experience QA roles."""

from __future__ import annotations

import unittest

from src.sources.habr_career import _JUNIOR_RE as HABR_JUNIOR_RE
from src.sources.habr_career import _matches_qa_junior as habr_matches
from src.sources.rabota_by import _VacancyCard, _matches_qa_junior


def _rabota(title: str, *, internship_page: bool = False) -> _VacancyCard:
    return _VacancyCard(
        vacancy_id="1",
        title=title,
        url="https://rabota.by/vacancy/1",
        location="Минск",
        is_internship_page=internship_page,
    )


class RabotaByTitleFilterTests(unittest.TestCase):
    def test_russian_tester_titles_match(self) -> None:
        for title in (
            "Тестировщик",
            "Инженер-тестировщик",
            "Инженер по тестированию Java (стажер)",
            "Стажер-тестировщик",
        ):
            with self.subTest(title=title):
                self.assertTrue(
                    _matches_qa_junior(_rabota(title, internship_page=True)),
                    title,
                )

    def test_no_experience_qa_engineer_is_kept(self) -> None:
        # Search URL already has experience=noExperience; title need not say junior.
        self.assertTrue(_matches_qa_junior(_rabota("QA Engineer", internship_page=True)))

    def test_non_qa_internship_titles_are_dropped(self) -> None:
        self.assertFalse(
            _matches_qa_junior(
                _rabota("Менеджер по работе с клиентами в логистике", internship_page=True)
            )
        )
        self.assertFalse(
            _matches_qa_junior(_rabota("Стикеровщик-упаковщик", internship_page=True))
        )

    def test_latin_intern_titles_still_match(self) -> None:
        self.assertTrue(
            _matches_qa_junior(_rabota("Full Stack Test Engineer Trainee", internship_page=True))
        )
        self.assertTrue(_matches_qa_junior(_rabota("Trainee QA Engineer (Минск)", internship_page=True)))


class HabrCareerTitleFilterTests(unittest.TestCase):
    def test_russian_tester_titles_match_on_intern_page(self) -> None:
        self.assertTrue(habr_matches("Тестировщик", require_junior_hint=False))
        self.assertTrue(habr_matches("Инженер по тестированию", require_junior_hint=False))
        self.assertTrue(habr_matches("Стажёр-тестировщик", require_junior_hint=False))

    def test_stazhirovka_counts_as_junior_hint(self) -> None:
        title = "Функциональный тестировщик / QA инженер (стажировка)"
        self.assertTrue(HABR_JUNIOR_RE.search(title))
        self.assertTrue(habr_matches(title, require_junior_hint=True))

    def test_senior_without_junior_is_dropped(self) -> None:
        self.assertFalse(
            habr_matches("Senior QA Python Automation Engineer", require_junior_hint=False)
        )
        self.assertFalse(
            habr_matches("QA Lead / Руководитель отдела тестирования", require_junior_hint=False)
        )

    def test_qa_engineer_kept_on_intern_qualification_page(self) -> None:
        self.assertTrue(habr_matches("QA инженер", require_junior_hint=False))


if __name__ == "__main__":
    unittest.main()
