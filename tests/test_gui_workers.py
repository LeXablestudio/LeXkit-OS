"""Extended tests for ToolWorker and run_in_worker convenience function."""

import pytest


def _has_gui_deps() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(not _has_gui_deps(), reason="PySide6 not installed")


@pytest.fixture(scope="module")
def qapp():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class TestToolWorkerExtended:
    def test_args_passed(self, qapp):
        from lexkit.gui.workers import ToolWorker

        results = {"done": False, "value": None}

        def add(a, b):
            return a + b

        w = ToolWorker(add, args=(3, 4))
        w.finished_ok.connect(lambda r: results.update(done=True, value=r))
        w.start()
        for _ in range(500):
            qapp.processEvents()
            if results["done"]:
                break
            w.wait(10)
        assert results["done"]
        assert results["value"] == 7

    def test_kwargs_passed(self, qapp):
        from lexkit.gui.workers import ToolWorker

        results = {"done": False, "value": None}

        def greet(name="world"):
            return f"hello {name}"

        w = ToolWorker(greet, kwargs={"name": "pytest"})
        w.finished_ok.connect(lambda r: results.update(done=True, value=r))
        w.start()
        for _ in range(500):
            qapp.processEvents()
            if results["done"]:
                break
            w.wait(10)
        assert results["done"]
        assert results["value"] == "hello pytest"

    def test_result_property(self, qapp):
        from lexkit.gui.workers import ToolWorker

        def compute():
            return 99

        w = ToolWorker(compute)
        w.start()
        for _ in range(500):
            qapp.processEvents()
            if w.result is not None:
                break
            w.wait(10)
        assert w.result == 99

    def test_log_line_signals(self, qapp):
        from lexkit.gui.workers import ToolWorker

        lines = []

        def noisy():
            print("aaa")
            print("bbb")
            print("ccc")

        w = ToolWorker(noisy)
        w.log_line.connect(lines.append)
        done = {"ok": False}
        w.finished_ok.connect(lambda _: done.__setitem__("ok", True))
        w.start()
        for _ in range(500):
            qapp.processEvents()
            if done["ok"]:
                break
            w.wait(10)
        text = "".join(lines)
        assert "aaa" in text
        assert "bbb" in text
        assert "ccc" in text

    def test_started_signal_emitted(self, qapp):
        from lexkit.gui.workers import ToolWorker

        started = {"fired": False}
        w = ToolWorker(lambda: None)
        w.started_signal.connect(lambda: started.__setitem__("fired", True))
        w.start()
        for _ in range(200):
            qapp.processEvents()
            if started["fired"]:
                break
            w.wait(10)
        assert started["fired"]

    def test_error_message_in_failed_signal(self, qapp):
        from lexkit.gui.workers import ToolWorker

        def boom():
            raise RuntimeError("test-error-12345")

        results = {"msg": ""}
        w = ToolWorker(boom)
        w.failed.connect(lambda m: results.__setitem__("msg", m))
        w.start()
        for _ in range(500):
            qapp.processEvents()
            if results["msg"]:
                break
            w.wait(10)
        assert "RuntimeError" in results["msg"]
        assert "test-error-12345" in results["msg"]


class TestRunInWorker:
    def test_convenience_function(self, qapp):
        from lexkit.gui.workers import run_in_worker

        done = {"val": None}
        w = run_in_worker(lambda: 100, on_done=lambda r: done.__setitem__("val", r))
        for _ in range(500):
            qapp.processEvents()
            if done["val"] is not None:
                break
            w.wait(10)
        assert done["val"] == 100

    def test_on_fail_callback(self, qapp):
        from lexkit.gui.workers import run_in_worker

        fail_msg = {"msg": ""}

        def bad():
            raise ValueError("oops")

        w = run_in_worker(bad, on_fail=lambda m: fail_msg.__setitem__("msg", m))
        for _ in range(500):
            qapp.processEvents()
            if fail_msg["msg"]:
                break
            w.wait(10)
        assert "oops" in fail_msg["msg"]

    def test_on_log_callback(self, qapp):
        from lexkit.gui.workers import run_in_worker

        logs = []
        w = run_in_worker(lambda: print("hi"), on_log=logs.append)
        done = {"ok": False}
        w.finished_ok.connect(lambda _: done.__setitem__("ok", True))
        for _ in range(500):
            qapp.processEvents()
            if done["ok"]:
                break
            w.wait(10)
        assert any("hi" in l for l in logs)

    def test_returned_worker_is_running_then_done(self, qapp):
        from lexkit.gui.workers import run_in_worker

        done = {"ok": False}
        w = run_in_worker(lambda: None, on_done=lambda _: done.__setitem__("ok", True))
        # Worker should be started.
        assert w.isRunning() or done["ok"]
        for _ in range(500):
            qapp.processEvents()
            if done["ok"]:
                break
            w.wait(10)
        assert not w.isRunning()
