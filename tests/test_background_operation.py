import threading
import unittest

from JSForm.background_operation import BackgroundOperationController, OperationResult


class BackgroundOperationControllerTests(unittest.TestCase):
    def controller(self):
        return BackgroundOperationController(dispatch=lambda callback, *args: callback(*args))

    def test_success_result_is_normalized_and_reported(self):
        finished = threading.Event()
        observed = []
        controller = self.controller()
        self.assertTrue(controller.start(
            lambda: "Finished safely.",
            on_success=lambda result: (observed.append(result), finished.set()),
            on_failure=lambda error: self.fail(str(error)),
        ))
        self.assertTrue(finished.wait(2))
        self.assertEqual(observed, [OperationResult("Finished safely.")])
        self.assertFalse(controller.running)

    def test_failure_restores_idle_state(self):
        finished = threading.Event()
        observed = []
        controller = self.controller()

        def fail():
            raise RuntimeError("sample failure")

        controller.start(
            fail,
            on_success=lambda _result: self.fail("unexpected success"),
            on_failure=lambda error: (observed.append(str(error)), finished.set()),
        )
        self.assertTrue(finished.wait(2))
        self.assertEqual(observed, ["sample failure"])
        self.assertFalse(controller.running)

    def test_duplicate_start_is_rejected(self):
        release = threading.Event()
        finished = threading.Event()
        controller = self.controller()
        self.assertTrue(controller.start(
            lambda: release.wait(2),
            on_success=lambda _result: finished.set(),
            on_failure=lambda _error: finished.set(),
        ))
        self.assertFalse(controller.start(
            lambda: None, on_success=lambda _result: None, on_failure=lambda _error: None,
        ))
        release.set()
        self.assertTrue(finished.wait(2))

    def test_restart_required_is_preserved(self):
        finished = threading.Event()
        observed = []
        result = OperationResult("Restart now.", restart_required=True, payload=42)
        self.controller().start(
            lambda: result,
            on_success=lambda value: (observed.append(value), finished.set()),
            on_failure=lambda error: self.fail(str(error)),
        )
        self.assertTrue(finished.wait(2))
        self.assertEqual(observed, [result])


if __name__ == "__main__":
    unittest.main()
