"""Mouse-transparent alignment guides, scoped to one Refined canvas."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget


class AlignmentGuides(QWidget):
    def __init__(self,canvas):
        super().__init__(canvas)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground,True)
        self.setStyleSheet("background: transparent; border: none;")
        self.x=None;self.y=None
        self.hide()

    def display(self,x,y):
        self.x=x;self.y=y
        self.setGeometry(self.parentWidget().rect())
        self.setVisible(x is not None or y is not None)
        if self.isVisible():self.raise_();self.update()

    def paintEvent(self,event):
        painter=QPainter(self)
        pen=QPen(self.palette().highlight().color(),1,Qt.PenStyle.DashLine)
        painter.setPen(pen)
        if self.x is not None:painter.drawLine(self.x,0,self.x,self.height())
        if self.y is not None:painter.drawLine(0,self.y,self.width(),self.y)
