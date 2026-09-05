"""Configuration-only tests; these do not claim a physical GPU render passed."""
import contextlib
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

spec = importlib.util.spec_from_file_location("render_gpu", Path(__file__).resolve().parents[1] / "tools/render_gpu.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fake_bpy(devices):
    prefs = NS(compute_device_type="NONE", devices=devices, refresh_devices=lambda: None)
    return NS(context=NS(preferences=NS(addons={"cycles": NS(preferences=prefs)})))


def device(name, kind):
    return NS(name=name, type=kind, use=True)


class GPUConfigurationTests(unittest.TestCase):
    def configure(self, devices, backend="OPTIX", name_filter=""):
        with contextlib.redirect_stdout(io.StringIO()):
            return module.configure_gpu(fake_bpy(devices), backend, name_filter)

    def test_selects_gpu_and_disables_cpu_and_other_backend(self):
        devices = [device("CPU", "CPU"), device("RTX", "OPTIX"), device("RTX", "CUDA")]
        self.assertEqual(self.configure(devices), ["RTX"])
        self.assertEqual([d.use for d in devices], [False, True, False])

    def test_case_insensitive_name_filter(self):
        devices = [device("RTX 3080", "OPTIX"), device("RTX 4090", "OPTIX")]
        self.assertEqual(self.configure(devices, "optix", "rtx 4090"), ["RTX 4090"])
        self.assertEqual([d.use for d in devices], [False, True])

    def test_no_gpu_is_error_not_cpu_fallback(self):
        devices = [device("CPU", "CPU")]
        with self.assertRaisesRegex(RuntimeError, "CPU fallback is disabled"):
            self.configure(devices)
        self.assertFalse(devices[0].use)

    def test_unknown_filter_is_error(self):
        with self.assertRaises(RuntimeError):
            self.configure([device("RTX", "OPTIX")], name_filter="not-present")

    def test_cpu_backend_is_rejected(self):
        with self.assertRaises(ValueError):
            self.configure([device("CPU", "CPU")], backend="CPU")

    def test_supported_non_nvidia_backends(self):
        for backend in ("HIP", "ONEAPI", "METAL", "CUDA"):
            with self.subTest(backend=backend):
                self.assertEqual(self.configure([device("GPU", backend)], backend), ["GPU"])


if __name__ == "__main__":
    unittest.main()
