import importlib.util
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock


class PackagingTests(unittest.TestCase):
    def test_build_waits_for_windowed_smoke_process(self) -> None:
        script = (Path(__file__).resolve().parents[1] / "packaging" / "Build-Transportable.ps1").read_text()
        self.assertIn('-ArgumentList "--smoke-test" -WindowStyle Hidden -PassThru -Wait', script)
        self.assertIn('if ($smokeProcess.ExitCode -ne 0)', script)

    def test_spec_includes_every_registered_sheet(self) -> None:
        from app.ui.sheet_types import SHEET_TYPE_REGISTRY

        root = Path(__file__).resolve().parents[1]
        analysis = Mock()
        runpy.run_path(
            str(root / "packaging" / "CharacterSheetApp.spec"),
            init_globals={
                "SPECPATH": str(root / "packaging"),
                "Analysis": analysis, "PYZ": Mock(), "EXE": Mock(), "COLLECT": Mock(),
            },
        )
        bundled = set(analysis.call_args.kwargs["hiddenimports"])
        for descriptor in SHEET_TYPE_REGISTRY.values():
            self.assertIn(descriptor.factory_path.split(":", 1)[0], bundled)

    def test_spec_data_supports_relocated_class_package_loader(self) -> None:
        root = Path(__file__).resolve().parents[1]
        analysis = Mock()
        runpy.run_path(
            str(root / "packaging" / "CharacterSheetApp.spec"),
            init_globals={
                "SPECPATH": str(root / "packaging"),
                "Analysis": analysis, "PYZ": Mock(), "EXE": Mock(), "COLLECT": Mock(),
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "_internal"
            for source, destination in analysis.call_args.kwargs["datas"]:
                if Path(destination).parts[:2] == ("app", "class_packages"):
                    shutil.copytree(source, bundle / destination)
            module_path = bundle / "app" / "class_packages" / "loader.py"
            module_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / "app" / "class_packages" / "loader.py", module_path)
            spec = importlib.util.spec_from_file_location("bundled_class_loader", module_path)
            loader = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(loader)

            # Use the loader's real __file__ resolution, without patching its roots
            # or reusing already-cached source definitions.
            self.assertEqual(module_path.parent / "definitions", loader.PACKAGE_ROOT)
            wizard = loader.class_package("pathfinder-class:wizard")
            self.assertIsNotNone(wizard)
            self.assertEqual("bonded_object_spell", wizard.resource_modules[0].resources[0].key)
            self.assertEqual("prodigy", loader.class_package("prodigy").class_key)
            aerochemist = "pathfinder-archetype:pathfinder-class:alchemist:aerochemist"
            self.assertIn("mutagen", loader.archetype_package(aerochemist)["replaces_features"])
            sapper = "pathfinder-archetype:pathfinder-class:alchemist:alchemical-sapper"
            runtime = loader.archetype_runtime_package(sapper)
            self.assertEqual("alchemical_sapper", runtime["resource_modules"][0]["key"])
            profile = loader.reviewed_archetype_profile(sapper)
            self.assertEqual(-1, profile["class_modifications"]["casting"]["daily_slot_adjustment"])
            self.assertIn(
                "spheres-archetype:spheres-class:crimson-dancer:crimson-tempest",
                {entry["key"] for entry in loader.supplemental_archetype_entries()},
            )


if __name__ == "__main__":
    unittest.main()
