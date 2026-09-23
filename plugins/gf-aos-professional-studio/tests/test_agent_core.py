import json
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
PLUGIN = ROOT / "plugins" / "gf-aos-professional-studio"
CONFIG = ROOT / ".codex" / "config.toml"
AGENTS_DIR = ROOT / ".codex" / "agents"


class AgentCoreTest(unittest.TestCase):
    def test_manifest_and_agent_registry_are_v011(self):
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.11.0")

        config = tomllib.loads(CONFIG.read_text(encoding="utf-8"))
        agents = config["agents"]
        roles = {name: value for name, value in agents.items() if isinstance(value, dict)}
        self.assertEqual(len(roles), 12)
        self.assertEqual(agents["max_concurrent_threads_per_session"], 4)

        for role, declaration in roles.items():
            path = CONFIG.parent / declaration["config_file"]
            self.assertTrue(path.is_file(), role)
            profile = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(profile["name"], role)
            self.assertEqual(profile["sandbox_mode"], "read-only")
            self.assertTrue(profile["description"])
            self.assertTrue(profile["developer_instructions"])

    def test_professional_gates_are_present(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in AGENTS_DIR.glob("*.toml"))
        for control in ("BOZZA DA VALIDARE", "APPROVO OUTPUT", "CRISIS_001", "sola lettura"):
            self.assertIn(control, text)

    def test_agentic_skills_are_packaged(self):
        for relative in (
            "skills/agent-orchestrator/SKILL.md",
            "skills/agent-orchestrator/references/agent-registry.md",
            "skills/agent-orchestrator/references/handoff-contract.md",
            "skills/strategic-context/SKILL.md",
            "skills/strategic-context/references/case-memory-template.md",
        ):
            self.assertTrue((PLUGIN / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
