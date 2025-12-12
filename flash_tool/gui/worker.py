"""Simple background worker utilities for GUI tasks.

This module provides a small, test-friendly `Worker` that runs a callable
in a daemon thread, a cooperative `CancelToken`, and a `ProgressEvent`
type. The worker normalizes progress callbacks so GUI code can receive
`ProgressEvent` instances regardless of the underlying task's callback
signature.
"""
import threading
from threading import Thread
from dataclasses import dataclass
from typing import Callable, Any, Optional, Tuple


@dataclass
class ProgressEvent:
    progress: float
    message: str = ""


class CancelToken:
    def __init__(self):
        self._cancel = threading.Event()

    def request_cancel(self) -> None:
        self._cancel.set()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()


class Worker(Thread):
    """Run `task(*args, **kwargs)` in a background thread.

    The worker will inject two keyword arguments into the task if they are
    not already present: `progress_cb` (callable taking either
    `(message, percent)` or a `ProgressEvent`) and `cancel_token` (the
    cooperative CancelToken instance).
    """

    def __init__(self, task: Callable[..., Any], args: Tuple = (), kwargs: Optional[dict] = None, progress_cb: Optional[Callable[[ProgressEvent], None]] = None, cancel_token: Optional[CancelToken] = None):
        super().__init__(daemon=True)
        self.task = task
        self.args = args
        self.kwargs = kwargs or {}
        self.progress_cb = progress_cb
        self.cancel_token = cancel_token or CancelToken()
        self._result = None
        self._exception: Optional[Exception] = None

    def run(self) -> None:
        try:
            # Prepare kwargs for the task: provide progress_cb and cancel_token
            kwargs = dict(self.kwargs)
            kwargs.setdefault("progress_cb", self._emit_progress)
            kwargs.setdefault("cancel_token", self.cancel_token)
            self._result = self.task(*self.args, **kwargs)
        except Exception as exc:
            self._exception = exc

    def _emit_progress(self, message: str, value: float = 0.0) -> None:
        """Normalize progress notifications into ProgressEvent objects.

        Accepts multiple common callback signatures used across the codebase:
        - _emit_progress(message: str, value: float)
        - _emit_progress(value: float, message: str)
        - _emit_progress(ProgressEvent)

        The function attempts to infer argument order when types differ and
        forwards a `ProgressEvent` to the user's provided `progress_cb`.
        """
        if not self.progress_cb:
            return

        try:
            # If a ProgressEvent is passed directly, forward it
            if isinstance(message, ProgressEvent):
                evt = message
            else:
                # If first arg is numeric, treat it as progress value
                if isinstance(message, (int, float)):
                    pct = float(message)
                    msg = str(value or "")
                else:
                    # otherwise, treat first arg as message and second as value
                    msg = str(message or "")
                    try:
                        pct = float(value) if value is not None else 0.0
                    except Exception:
                        pct = 0.0
                evt = ProgressEvent(progress=pct, message=msg)

            self.progress_cb(evt)
        except Exception:
            # Swallow errors from user callbacks to avoid crashing the worker
            pass

    def result(self) -> Any:
        if self._exception:
            raise self._exception
        return self._result


def run_in_background(task: Callable[..., Any], args: Tuple = (), kwargs: Optional[dict] = None, progress_cb: Optional[Callable[[ProgressEvent], None]] = None, cancel_token: Optional[CancelToken] = None) -> Worker:
    w = Worker(task, args=args, kwargs=kwargs, progress_cb=progress_cb, cancel_token=cancel_token)
    w.start()
    return w
