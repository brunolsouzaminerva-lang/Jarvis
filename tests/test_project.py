import unittest
from pathlib import Path


class ProjectStructureTests(unittest.TestCase):
    def test_readme_exists(self):
        self.assertTrue((Path(__file__).resolve().parents[1] / "README.md").is_file())


if __name__ == "__main__":
    unittest.main()
