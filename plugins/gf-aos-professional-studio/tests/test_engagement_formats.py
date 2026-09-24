import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "engagement_formats.py"
SPEC = importlib.util.spec_from_file_location("engagement_formats", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class EngagementFormatsTest(unittest.TestCase):
    def test_specialties_do_not_activate_crisis_implicitly(self):
        for family in module.FAMILIES:
            text = module.render(family)
            self.assertIn("BOZZA DA VALIDARE", text)
            self.assertIn("[DA COMPILARE]", text)
            if family != "crisi":
                self.assertNotIn("`CRISIS_001`", text)

    def test_existing_brief_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "brief.md"
            destination.write_text("originale", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), "lavoro", "--output", str(destination)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(destination.read_text(encoding="utf-8"), "originale")


if __name__ == "__main__":
    unittest.main()
