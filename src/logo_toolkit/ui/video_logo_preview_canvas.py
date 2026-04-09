from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QImage, QMouseEvent, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from logo_toolkit.core.models import PixelLogoPlacement


class VideoLogoPreviewCanvas(QWidget):
    placement_changed = Signal(int, int, int, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(540, 380)
        self.setMouseTracking(True)
        self._base_pixmap = QPixmap()
        self._logo_pixmap = QPixmap()
        self._placement = PixelLogoPlacement()
        self._image_rect = QRectF()
        self._drag_offset = QPointF()
        self._resize_anchor = QPointF()
        self._interaction_mode = ""
        self._keep_aspect_ratio = True

    def set_images(
        self,
        image_path: Path | None,
        logo_path: Path | None,
        placement: PixelLogoPlacement,
        keep_aspect_ratio: bool = True,
    ) -> None:
        self._base_pixmap = QPixmap(str(image_path)) if image_path else QPixmap()
        self._logo_pixmap = QPixmap(str(logo_path)) if logo_path else QPixmap()
        self._placement = placement.normalized()
        self._keep_aspect_ratio = keep_aspect_ratio
        self.update()

    def set_placement(self, placement: PixelLogoPlacement) -> None:
        self._placement = placement.normalized()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        card_rect = QRectF(self.rect()).adjusted(5, 5, -5, -5)
        card_path = QPainterPath()
        card_path.addRoundedRect(card_rect, 18, 18)
        painter.fillPath(card_path, QColor("#ffffff"))
        painter.setPen(QPen(QColor("#e5e5ea"), 1.2))
        painter.drawPath(card_path)

        if self._base_pixmap.isNull():
            empty_rect = card_rect.adjusted(26, 26, -26, -26)
            painter.setPen(QColor("#6e6e73"))
            painter.drawText(
                empty_rect,
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                "选择视频和 Logo 后在这里直接校准\n\n拖动 Logo 调整位置，拖动右下角控制点调整大小。",
            )
            return

        self._image_rect = self._fit_rect(self._base_pixmap.width(), self._base_pixmap.height())
        image_frame = self._image_rect.adjusted(-6, -6, 6, 6)
        painter.setBrush(QColor("#f8f8fa"))
        painter.setPen(QPen(QColor("#e5e5ea"), 1.2))
        painter.drawRoundedRect(image_frame, 14, 14)
        painter.drawPixmap(self._image_rect.toRect(), self._base_pixmap)

        logo_rect = self._logo_rect()
        if not self._logo_pixmap.isNull():
            painter.drawPixmap(logo_rect.toRect(), self._logo_pixmap)
            painter.setBrush(QColor(0, 113, 227, 28))
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.drawRoundedRect(logo_rect, 10, 10)
            pen = QPen(QColor("#0071e3"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRoundedRect(logo_rect, 10, 10)
            painter.setBrush(QColor("#0071e3"))
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.drawEllipse(self._handle_rect())
        else:
            painter.setPen(QColor("#86868b"))
            painter.drawText(
                card_rect.adjusted(0, 0, 0, -16),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                "选择 Logo 后即可在这里预览定位",
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._logo_pixmap.isNull():
            return
        logo_rect = self._logo_rect()
        handle_rect = self._handle_rect()
        if handle_rect.contains(event.position()):
            self._interaction_mode = "resize"
            self._resize_anchor = QPointF(logo_rect.left(), logo_rect.top())
            self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
            return
        if logo_rect.contains(event.position()):
            self._interaction_mode = "move"
            self._drag_offset = event.position() - logo_rect.topLeft()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

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
        else:
            logo_rect = self._logo_rect()
            if self._handle_rect().contains(event.position()):
                self.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
            elif logo_rect.contains(event.position()):
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            else:
                self.unsetCursor()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: ARG002
        self._interaction_mode = ""
        self.unsetCursor()

    def _fit_rect(self, image_width: int, image_height: int) -> QRectF:
        area = self.rect().adjusted(24, 24, -24, -24)
        scale = min(area.width() / image_width, area.height() / image_height)
        draw_width = image_width * scale
        draw_height = image_height * scale
        x = area.x() + (area.width() - draw_width) / 2
        y = area.y() + (area.height() - draw_height) / 2
        return QRectF(x, y, draw_width, draw_height)

    def _logo_rect(self) -> QRectF:
        if self._base_pixmap.isNull() or self._logo_pixmap.isNull():
            return QRectF()
        x, y, width, height = self._placement.to_overlay_box(
            frame_width=self._base_pixmap.width(),
            frame_height=self._base_pixmap.height(),
            logo_width=self._logo_pixmap.width(),
            logo_height=self._logo_pixmap.height(),
            keep_aspect_ratio=self._keep_aspect_ratio,
        )
        scale_x, scale_y = self._display_scale()
        return QRectF(
            self._image_rect.left() + x * scale_x,
            self._image_rect.top() + y * scale_y,
            width * scale_x,
            height * scale_y,
        )

    def _handle_rect(self) -> QRectF:
        logo_rect = self._logo_rect()
        handle_size = 14.0
        return QRectF(
            logo_rect.right() - handle_size / 2,
            logo_rect.bottom() - handle_size / 2,
            handle_size,
            handle_size,
        )

    def _update_from_canvas(self, left: float, top: float, width: float) -> None:
        if self._image_rect.isEmpty():
            return
        scale_x, scale_y = self._display_scale()
        if scale_x <= 0.0 or scale_y <= 0.0:
            return
        local_left = left - self._image_rect.left()
        local_top = top - self._image_rect.top()
        source_left = local_left / scale_x
        source_top = local_top / scale_y
        source_width = width / scale_x
        if self._keep_aspect_ratio:
            source_height = source_width * (self._logo_pixmap.height() / max(self._logo_pixmap.width(), 1))
        else:
            source_height = width / scale_y
        placement = PixelLogoPlacement.auto_from_overlay_box(
            left=source_left,
            top=source_top,
            overlay_width=source_width,
            overlay_height=source_height,
            frame_width=self._base_pixmap.width(),
            frame_height=self._base_pixmap.height(),
        )
        self._placement = placement
        self.placement_changed.emit(
            placement.margin_x_px,
            placement.margin_y_px,
            placement.width_px,
            placement.anchor,
        )
        self.update()

    def _display_scale(self) -> tuple[float, float]:
        if self._base_pixmap.isNull() or self._image_rect.isEmpty():
            return 1.0, 1.0
        return (
            self._image_rect.width() / max(float(self._base_pixmap.width()), 1.0),
            self._image_rect.height() / max(float(self._base_pixmap.height()), 1.0),
        )

    def export_preview_image(self) -> QImage | None:
        if self._base_pixmap.isNull():
            return None
        image = QImage(self.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor("#f5f5f7"))
        painter = QPainter(image)
        self.render(painter)
        painter.end()
        return image
