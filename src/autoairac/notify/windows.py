"""Windows toast notifications via winotify."""

from __future__ import annotations

import logging
from enum import Enum

from winotify import Notification, audio

logger = logging.getLogger(__name__)


class NotifyLevel(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class WindowsNotifier:
    """Send native Windows toast notifications for pipeline steps."""

    def __init__(self, app_id: str = "AutoAIRAC", enabled: bool = True) -> None:
        self._app_id = app_id
        self._enabled = enabled

    def notify(
        self,
        title: str,
        message: str,
        *,
        level: NotifyLevel = NotifyLevel.INFO,
    ) -> None:
        if not self._enabled:
            logger.info("[%s] %s — %s", level.value, title, message)
            return

        toast = Notification(app_id=self._app_id, title=title, msg=message, duration="short")
        toast.set_audio(audio.Default, loop=False)

        if level == NotifyLevel.SUCCESS:
            toast.add_actions(label="OK")
        elif level == NotifyLevel.ERROR:
            toast.set_audio(audio.Reminder, loop=False)

        try:
            toast.show()
        except Exception:
            logger.exception("Failed to show toast: %s — %s", title, message)

    def step(self, step: str, detail: str, *, level: NotifyLevel = NotifyLevel.INFO) -> None:
        self.notify(f"AutoAIRAC — {step}", detail, level=level)