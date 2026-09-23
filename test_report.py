"""PDF regressions. Install requirements-dev.txt for rendered-PDF checks."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
local_renderer = Path(__file__).resolve().parent / '.pdf-tools'
if local_renderer.exists():
    sys.path.insert(0, str(local_renderer))
try:
    import pymupdf
except ImportError:
    pymupdf = None
from utilities.report import generate_comprehensive_pdf, SECTION_TITLES, count_issues


@unittest.skipIf(pymupdf is None, 'Install requirements-dev.txt for PDF inspection')
class ReportTests(unittest.TestCase):
    def report(self, errors, ai=None):
        path = generate_comprehensive_pdf(errors, ai)
        self.assertIsNotNone(path)
        self.addCleanup(lambda: Path(path).parent.rmdir())
        self.addCleanup(lambda: Path(path).unlink(missing_ok=True))
        pdf = pymupdf.open(path)
        self.addCleanup(pdf.close)
        for page in pdf:
            for x0, y0, x1, y1, word, *_ in page.get_text('words'):
                self.assertGreaterEqual(x0, 50, word)
                self.assertLessEqual(x1, 561, word)
                self.assertGreaterEqual(y0, 10, word)
                self.assertLessEqual(y1, 773, word)
        return pdf

    def test_long_reference_wraps_without_empty_detail_page(self):
        pdf = self.report(['Reference Errors', 'Error: ' + 'A <title> & author. ' * 900])
        self.assertGreater(len(pdf), 2)
        self.assertIn('A <title> & author.', pdf[1].get_text())
        text = ''.join(page.get_text() for page in pdf)
        self.assertEqual(text.count('<title>'), 900)
        for index, page in enumerate(pdf, 1):
            self.assertIn(f'Page {index}', page.get_text())

    def test_clean_report_is_one_page_and_has_no_compliance_claim(self):
        pdf = self.report(SECTION_TITLES)
        self.assertEqual(len(pdf), 1)
        text = pdf[0].get_text()
        self.assertIn('No issues detected by the automated checks.', text)
        self.assertNotIn('meets all', text)

    def test_missing_categories_not_reported_as_passed(self):
        pdf = self.report(['Font Size Errors'])
        self.assertIn('Incomplete review', pdf[0].get_text())
        self.assertIn('Not supplied', pdf[0].get_text())

    def test_counts_match_and_status_symbols_removed(self):
        errors = ['Margin Errors', '\u274c Section 1: margins.',
                  'Font Size Errors', 'Total Font Size Errors: 900',
                  'Error: Incorrect size', '\u2022 Page 1: Paragraphs 1, 2']
        pdf = self.report(errors, {'error': 'Unavailable'})
        text = '\n'.join(page.get_text() for page in pdf)
        self.assertEqual(count_issues(errors), 2)
        self.assertIn('2 issue group(s)', text)
        self.assertNotIn('900', text)
        self.assertNotIn('\u274c', text)
        self.assertIn('unavailable', text)

    def test_invalid_ai_result_does_not_break_report(self):
        pdf = self.report(SECTION_TITLES, {'human': 'invalid', 'ai': None})
        self.assertIn('invalid service response', pdf[0].get_text())


class FailureCleanupTests(unittest.TestCase):
    def test_failed_build_removes_its_temporary_directory(self):
        with tempfile.TemporaryDirectory() as parent:
            folder = Path(parent) / 'report'
            folder.mkdir()
            with patch('utilities.report.tempfile.mkdtemp', return_value=str(folder)), \
                 patch('utilities.report.SimpleDocTemplate.build', side_effect=RuntimeError('test failure')), \
                 self.assertLogs('utilities.report', level='ERROR'):
                self.assertIsNone(generate_comprehensive_pdf(SECTION_TITLES))
            self.assertFalse(folder.exists())
