import threading

import pytest

from gello_cr.app.background import BackgroundJobs


def test_close_waits_for_owned_job_and_rejects_late_submissions():
    jobs = BackgroundJobs()
    started, release = threading.Event(), threading.Event()
    results = []

    def operation():
        started.set()
        release.wait(2)
        return 42

    thread = jobs.start(operation, lambda value, error: results.append((value, error)), name="Job")
    assert started.wait(1)
    with pytest.raises(TimeoutError):
        jobs.close(timeout=0.01)
    assert jobs.start(lambda: 0, name="Late") is None
    release.set()
    jobs.close(timeout=1)
    assert not thread.is_alive()
    assert results == [(42, None)]


def test_job_delivers_operation_error_to_callback():
    jobs = BackgroundJobs()
    received = []

    def fail():
        raise ValueError("discovery failed")

    jobs.start(fail, lambda value, error: received.append(error), name="Failure")
    jobs.close(timeout=1)
    assert isinstance(received[0], ValueError)
