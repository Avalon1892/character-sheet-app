"""Rules-free metric surfaces, also applicable to existing movement frames."""
from PySide6.QtCore import Qt, QEvent, QObject
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy


class MetricInteraction(QObject):
    def __init__(self, card, callback):
        super().__init__(card)
        self.card, self.callback = card, callback
        self.press = None
        card.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        for widget in (card, *card.findChildren(QLabel)):
            widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self.press = event.globalPosition().toPoint()
            self.card.setFocus(Qt.FocusReason.MouseFocusReason)
            return True
        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            start, self.press = self.press, None
            if start is not None and (event.globalPosition().toPoint()-start).manhattanLength() < QApplication.startDragDistance():
                if self.card.rect().contains(self.card.mapFromGlobal(event.globalPosition().toPoint())):
                    self.callback()
            return True
        if event.type() == QEvent.Type.KeyPress and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if not event.isAutoRepeat(): self.callback()
            return True
        return False


def decorate_metric(card, value, title, callback, *, primary=False, compact=False):
    """Keep widget identities/bindings intact while adding a common surface."""
    card.setObjectName("refinedMetricCard")
    card.setProperty("primaryMetric", primary)
    card.setProperty("compactMetric", compact)
    card.setAccessibleName(title)
    card.setToolTip("View " + title.lower() + " details")
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    value.setObjectName("refinedMetricValue")
    value.setProperty("primaryMetric", primary)
    value.setProperty("compactMetric", compact)
    card._metric_interaction = MetricInteraction(card, callback)


class MetricCard(QFrame):
    def __init__(self, title, callback, *, primary=False, compact=False, hint=""):
        super().__init__()
        layout = QHBoxLayout(self) if compact else QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(3)
        self.title = QLabel(title)
        self.title.setObjectName("refinedMetricLabel")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value = QLabel("—")
        self.value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.value, 1)
        if hint:
            label = QLabel(hint)
            label.setObjectName("refinedMuted")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
        decorate_metric(self, self.value, title, callback, primary=primary, compact=compact)


def metric_group(title, *, magic=False):
    group = QFrame()
    group.setObjectName("refinedMetricGroup")
    group.setProperty("magicMetric", magic)
    group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    layout = QVBoxLayout(group)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)
    label = QLabel(title)
    label.setObjectName("refinedMetricHeading")
    layout.addWidget(label)
    return group
