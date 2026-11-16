"""Render cached camera frames; stale images never appear to be live."""

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

from .theme import set_state


class CameraPreviewRenderer:
    def __init__(self, page):
        self.page = page
        self._last_render = None

    @staticmethod
    def _pixmap(image_rgb):
        if image_rgb is None:
            return None
        image = np.asarray(image_rgb)
        if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
            return None
        image = np.ascontiguousarray(image)
        height, width = image.shape[:2]
        return QPixmap.fromImage(
            QImage(image.data, width, height, int(image.strides[0]), QImage.Format_RGB888).copy()
        )

    def render(self, preview):
        page = self.page
        labels = (page.base_preview, page.wrist_preview, page.roi_preview)
        images = (preview.base_rgb, preview.wrist_rgb, preview.roi_rgb)
        statuses = []
        for i, title in enumerate(page.preview_titles):
            title.setText(preview.stream_names[i])
            title.setToolTip(preview.stream_descriptions[i] if preview.stream_descriptions else "")
            stream = preview.streams[i] if i < len(preview.streams) else {}
            status = stream.get("status", "OK" if images[i] is not None else "OFFLINE")
            statuses.append(status)
            age = f"{stream['age_s'] * 1000:.0f} ms" if stream.get("age_s") is not None else "—"
            fps = stream.get("fps", 0) if status == "OK" else 0
            page.camera_metrics[i].setText(f"{status} · {fps:.1f} FPS · Age {age}")
            page.camera_metrics[i].setToolTip(str(stream.get("error", "")))
            set_state(
                page.camera_metrics[i],
                "success"
                if status == "OK"
                else "error"
                if status == "ERROR"
                else "warning"
                if status == "STALE"
                else "neutral",
            )
        key = (
            preview.base_timestamp,
            preview.wrist_timestamp,
            preview.roi_timestamp,
            tuple((label.width(), label.height()) for label in labels),
            tuple(statuses),
        )
        if key == self._last_render:
            return
        self._last_render = key
        for label, image, name, status in zip(
            labels, images, preview.stream_names, statuses, strict=True
        ):
            pixmap = self._pixmap(image) if status == "OK" else None
            if pixmap is None:
                label.clear()
                reason = {"STALE": "画面已过期", "ERROR": "相机连接丢失"}.get(status, "等待相机")
                label.setText(f"{name} · {reason}")
            else:
                label.setPixmap(
                    pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
