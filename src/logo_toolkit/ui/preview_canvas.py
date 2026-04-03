from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from logo_toolkit.core.models import LogoPlacement


class PreviewCanvas(QWidget):
    placement_changed = Signal(float, float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(680, 540)
        self.setMouseTracking(True)
        self._base_pixmap = QPixmap()
        self._logo_pixmap = QPixmap()
        self._placement = LogoPlacement()
        self._image_rect = QRectF()
        self._drag_offset = QPointF()
        self._resize_anchor = QPointF()
        self._interaction_mode = ""

    def set_images(self, image_path: Path | None, logo_path: Path | None, placement: LogoPlacement) -> None:
        self._base_pixmap = QPixmap(str(image_path)) if image_path else QPixmap()
        self._logo_pixmap = QPixmap(str(logo_path)) if logo_path else QPixmap()
        self._placement = placement.normalized()
        self.update()

    def set_placement(self, placement: LogoPlacement) -> None:
        self._placement = placement.normalized()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#fff9ef"))

        if self._base_pixmap.isNull():
            painter.setPen(QColor("#84775f"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "拖入图片后在这里预览")
            return

        self._image_rect = self._fit_rect(self._base_pixmap.width(), self._base_pixmap.height())
        painter.drawPixmap(self._image_rect.toRect(), self._base_pixmap)

        logo_rect = self._logo_rect()
        if not self._logo_pixmap.isNull():
            painter.drawPixmap(logo_rect.toRect(), self._logo_pixmap)
            pen = QPen(QColor("#c24f3d"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(logo_rect)
            painter.setBrush(QColor("#c24f3d"))
            handle_size = 10
            painter.drawRect(
                QRectF(
                    logo_rect.right() - handle_size / 2,
                    logo_rect.bottom() - handle_size / 2,
                    handle_size,
                    handle_size,
                )
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._logo_pixmap.isNull():
            return
        logo_rect = self._logo_rect()
        handle_rect = QRectF(logo_rect.right() - 8, logo_rect.bottom() - 8, 16, 16)
        if handle_rect.contains(event.position()):
            self._interaction_mode = "resize"
            self._resize_anchor = QPointF(logo_rect.left(), logo_rect.top())
            return
        if logo_rect.contains(event.position()):
            self._interaction_mode = "move"
            self._drag_offset = event.position() - logo_rect.topLeft()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._base_pixmap.isNull() or self._logo_pixmap.isNull():
            return
        if self._interaction_mode == "move":
            new_left = event.position().x() - self._drag_offset.x()
            new_top = event.position().y() - self._drag_offset.y()
            self._update_from_canvas(new_left, new_top, self._logo_rect().width())
        elif self._interaction_mode == "resize":
            width = max(18.0, event.position().x() - self._resize_anchor.x())
            self._update_from_canvas(self._resize_anchor.x(), self._resize_anchor.y(), width)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: ARG002
        self._interaction_mode = ""

    def _fit_rect(self, image_width: int, image_height: int) -> QRectF:
        area = self.rect().adjusted(18, 18, -18, -18)
        scale = min(area.width() / image_width, area.height() / image_height)
        draw_width = image_width * scale
        draw_height = image_height * scale
        x = area.x() + (area.width() - draw_width) / 2
        y = area.y() + (area.height() - draw_height) / 2
        return QRectF(x, y, draw_width, draw_height)

    def _logo_rect(self) -> QRectF:
        if self._base_pixmap.isNull() or self._logo_pixmap.isNull():
            return QRectF()
        width = self._image_rect.width() * self._placement.width_ratio
        height = width * (self._logo_pixmap.height() / max(self._logo_pixmap.width(), 1))
        x = self._image_rect.left() + self._image_rect.width() * self._placement.x_ratio
        y = self._image_rect.top() + self._image_rect.height() * self._placement.y_ratio
        if x + width > self._image_rect.right():
            x = self._image_rect.right() - width
        if y + height > self._image_rect.bottom():
            y = self._image_rect.bottom() - height
        return QRectF(x, y, width, height)

    def _update_from_canvas(self, left: float, top: float, width: float) -> None:
        if self._image_rect.isEmpty():
            return
        x_ratio = (left - self._image_rect.left()) / self._image_rect.width()
        y_ratio = (top - self._image_rect.top()) / self._image_rect.height()
        width_ratio = width / self._image_rect.width()
        normalized = LogoPlacement(x_ratio=x_ratio, y_ratio=y_ratio, width_ratio=width_ratio).normalized()
        self._placement = normalized
        self.placement_changed.emit(normalized.x_ratio, normalized.y_ratio, normalized.width_ratio)
        self.update()

    def export_preview_image(self) -> QImage | None:
        if self._base_pixmap.isNull():
            return None
        image = QImage(self.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("#fff9ef"))
        painter = QPainter(image)
        self.render(painter)
        painter.end()
        return image
