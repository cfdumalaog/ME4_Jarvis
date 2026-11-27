"""Dynamic voice orb adapted from the ME4-Initial voice HUD.

The source ME4-Initial interface is browser-rendered.  ME4_Jarvis is a native
Qt application, so this module keeps the visual language—voice-reactive core,
orbit rings, level spikes, state colours, and live label—but renders it with
the same QPainter surface as the rest of the Jarvis HUD.  It deliberately has
no audio or model dependencies: ``HudCanvas`` supplies the real smoothed
microphone/playback level and state.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QRadialGradient,
)


def _alpha(color: QColor, value: float) -> QColor:
    result = QColor(color)
    result.setAlphaF(max(0.0, min(1.0, float(value))))
    return result


class DynamicVoiceOrb:
    """A lightweight, voice-reactive centrepiece for the native HUD."""

    def __init__(self) -> None:
        self.phase = 0.0
        self.level = 0.0

    def step(self, dt: float, level: float, *, speaking: bool,
             thinking: bool, muted: bool) -> None:
        dt = min(0.10, max(0.0, float(dt)))
        level = max(0.0, min(1.0, float(level)))
        self.level += (level - self.level) * (0.48 if level > self.level else 0.18)
        rate = 0.30 + (1.55 if thinking else 0.0) + (1.10 if speaking else 0.0)
        if muted:
            rate = 0.12
        self.phase += dt * rate

    @staticmethod
    def _state_color(main: QColor, accent: QColor, state: str,
                     speaking: bool, muted: bool) -> QColor:
        if muted:
            return QColor(main)
        if speaking:
            return QColor(accent)
        if state in ("THINKING", "PROCESSING"):
            return QColor(accent)
        if state == "LISTENING":
            return QColor(104, 239, 190)
        return QColor(main)

    def paint(self, painter: QPainter, cx: float, cy: float, radius: float,
              main: QColor, accent: QColor, white: QColor, level: float,
              *, speaking: bool, thinking: bool, muted: bool,
              state: str, name: str = "") -> None:
        level = max(0.0, min(1.0, max(float(level), self.level)))
        live = (speaking or level > 0.035) and not muted
        live_color = self._state_color(main, accent, state, speaking, muted)
        phase = self.phase

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Wide glow: the ME4-Initial orb is a field of light before it is a
        # machine.  The opacity is driven by the real audio level.
        glow = QRadialGradient(QPointF(cx, cy), radius * 1.18)
        glow.setColorAt(0.0, _alpha(live_color, 0.18 + level * 0.20))
        glow.setColorAt(0.42, _alpha(live_color, 0.08 + level * 0.10))
        glow.setColorAt(1.0, _alpha(live_color, 0.0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(glow))
        painter.drawEllipse(QPointF(cx, cy), radius * 1.18, radius * 1.18)

        # Three elliptical orbits, each with a different orientation and
        # motion speed.  They stay sparse so the voice spikes remain legible.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for index, (rx, ry, tilt, speed, opacity, width) in enumerate((
            (0.96, 0.39, 16.0, 1.00, 0.58, 1.7),
            (0.82, 0.56, -34.0, -0.72, 0.38, 1.2),
            (0.68, 0.87, 62.0, 0.55, 0.26, 1.0),
        )):
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(tilt + math.degrees(phase * speed))
            orbit = QRectF(-radius * rx, -radius * ry,
                           radius * rx * 2.0, radius * ry * 2.0)
            painter.setPen(QPen(_alpha(live_color, opacity), width))
            painter.drawEllipse(orbit)
            painter.restore()

        # Voice spikes around the outside of the core.  This is the native
        # equivalent of ME4-Initial's .voice-spikes element.
        count = 72
        ring = radius * 0.73
        painter.setPen(Qt.PenStyle.NoPen)
        for index in range(count):
            angle = phase * 0.70 + index * (2.0 * math.pi / count)
            wobble = 0.5 + 0.5 * math.sin(phase * 4.2 + index * 0.61)
            idle = 0.012 + 0.008 * math.sin(phase * 1.3 + index * 0.43)
            height = radius * (idle + (level * (0.07 + 0.10 * wobble) if live else 0.0))
            inner = ring
            outer = ring + height
            x0, y0 = cx + math.cos(angle) * inner, cy + math.sin(angle) * inner
            x1, y1 = cx + math.cos(angle) * outer, cy + math.sin(angle) * outer
            painter.setPen(QPen(_alpha(live_color, 0.30 + level * 0.62),
                                1.2 if index % 3 else 1.7))
            painter.drawLine(int(x0), int(y0), int(x1), int(y1))

        # Core glow and bright centre.  Thinking uses the secondary accent;
        # speech uses the primary live accent; muted is intentionally dim.
        core_radius = radius * (0.285 + level * 0.055)
        core = QRadialGradient(QPointF(cx - radius * 0.08, cy - radius * 0.10),
                               core_radius * 1.35)
        core.setColorAt(0.0, _alpha(white, 0.90 if not muted else 0.42))
        core.setColorAt(0.20, _alpha(live_color, 0.72 if not muted else 0.30))
        core.setColorAt(0.72, _alpha(live_color, 0.16 if not muted else 0.08))
        core.setColorAt(1.0, _alpha(live_color, 0.0))
        painter.setBrush(QBrush(core))
        painter.drawEllipse(QPointF(cx, cy), core_radius * 1.35, core_radius * 1.35)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(_alpha(live_color, 0.70 if live else 0.40), 1.4))
        painter.drawEllipse(QPointF(cx, cy), core_radius, core_radius)

        # Scanning arc gives the idle state motion without pretending that it
        # is audio.  Its speed increases while the model is thinking.
        scan_radius = radius * 0.45
        scan_box = QRectF(cx - scan_radius, cy - scan_radius,
                          scan_radius * 2.0, scan_radius * 2.0)
        scan_speed = 18.0 if thinking else (12.0 if live else 6.0)
        painter.setPen(QPen(_alpha(white, 0.52 if live else 0.28), 1.2))
        painter.drawArc(scan_box, int((phase * scan_speed) % 360.0 * 16), 78 * 16)

        # The source UI keeps the state and caption attached to the orb.  The
        # surrounding HudCanvas still owns the larger state line and waveform.
        if name:
            font = QFont("Segoe UI")
            font.setPixelSize(max(10, int(radius * 0.085)))
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, max(1.5, radius * 0.018))
            painter.setFont(font)
            painter.setPen(QPen(_alpha(white, 0.78 if not muted else 0.42)))
            painter.drawText(QRectF(cx - radius, cy + radius * 0.42,
                                    radius * 2.0, radius * 0.25),
                             Qt.AlignmentFlag.AlignCenter, name)
        painter.restore()
