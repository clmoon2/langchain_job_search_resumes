import unittest

import job_automation_langchain as mod


class UtilsTestCase(unittest.TestCase):
    def test_format_salary_handles_structs(self):
        payload = [{"min": 100000, "max": 120000, "currency": "USD", "period": "year"}]
        result = mod.format_salary_info(payload)
        self.assertIn("USD", result)
        self.assertIn("100000", result)

    def test_clean_latex_strips_fences_and_ends(self):
        raw = "```latex\n\\documentclass{article}\n\\begin{document}\nHello\n\\end{document}\n```"
        cleaned = mod.clean_latex(raw)
        self.assertTrue(cleaned.startswith("\\documentclass"))
        self.assertTrue(cleaned.strip().endswith("\\end{document}"))
        self.assertNotIn("```", cleaned)

    def test_build_job_key_is_stable(self):
        job = {
            "id": "123",
            "companyName": "OpenAI",
            "title": "ML Intern",
            "postedAt": "2024-01-01",
            "link": "https://example.com/job",
        }
        key1 = mod.build_job_key(job)
        key2 = mod.build_job_key(job.copy())
        self.assertEqual(key1, key2)
        self.assertTrue(key1)

    def test_validate_latex_output_guards_length(self):
        self.assertFalse(mod.validate_latex_output("short"))
        valid = "\\documentclass{article}\n\\begin{document}\n" + ("a" * 210) + "\n\\end{document}"
        self.assertTrue(mod.validate_latex_output(valid))


if __name__ == "__main__":
    unittest.main()

