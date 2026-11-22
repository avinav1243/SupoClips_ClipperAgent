import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('campaign_render', Path(__file__).resolve().parents[1] / 'supoclip-campaign/scripts/render.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class ThreadBudgetTests(unittest.TestCase):
    def test_auto_uses_the_available_cpu_budget(self):
        plan = renderer.thread_plan({}, available=12)
        self.assertEqual(plan['encode_threads'], 11)
        self.assertEqual(plan['filter_threads'], 8)
        self.assertEqual(plan['decode_threads'], 4)

    def test_multiple_renders_share_cpu_capacity(self):
        plan = renderer.thread_plan({'concurrent_renders': 3}, available=12)
        self.assertEqual(plan['encode_threads'], 3)
        self.assertEqual(plan['filter_threads'], 3)
        self.assertEqual(plan['decode_threads'], 3)

    def test_explicit_counts_cannot_exceed_the_job_budget(self):
        plan = renderer.thread_plan({'cpu_threads': 64, 'filter_threads': 64, 'decode_threads': 64, 'concurrent_renders': 2}, available=8)
        self.assertEqual(plan['encode_threads'], 3)
        self.assertEqual(plan['filter_threads'], 3)
        self.assertEqual(plan['decode_threads'], 3)

    def test_single_cpu_and_manual_legacy_settings_work(self):
        self.assertEqual(renderer.thread_plan({}, available=1)['encode_threads'], 1)
        self.assertEqual(renderer.thread_plan({'cpu_threads': 4}, available=12)['encode_threads'], 4)
        self.assertEqual(renderer.thread_plan({'cpu_reserve': 0}, available=12)['encode_threads'], 12)

    def test_invalid_thread_configuration_fails(self):
        for settings in ({'cpu_threads': 0}, {'cpu_threads': True}, {'filter_threads': 'eight'}, {'decode_threads': 65}, {'cpu_reserve': -1}, {'concurrent_renders': 0}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                renderer.thread_plan(settings, available=12)

    def test_container_quota_limits_detected_host_cpus(self):
        with patch.object(renderer.os, 'cpu_count', return_value=12), patch.object(renderer.os, 'process_cpu_count', return_value=12, create=True), patch.object(renderer.os, 'sched_getaffinity', return_value=set(range(12)), create=True), patch.object(Path, 'read_text', return_value='200000 100000'):
            self.assertEqual(renderer.available_cpu_count(), 2)


if __name__ == '__main__':
    unittest.main()
