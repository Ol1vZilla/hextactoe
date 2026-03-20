import sys
import math
from PyQt6.QtWidgets import (QApplication, QGraphicsView, QGraphicsScene, 
                             QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QWidget)
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygonF, QBrush, QPixmap
from PyQt6.QtCore import Qt, QPointF, QEvent, QTimer

class InfiniteHexScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hex_size = 40
        self.on_win = None
        self.on_state_change = None 
        self.hovered_hex = None
        self.show_highlights = True
        self.reset_state()

    def reset_state(self):
        """Clears the board and resets all game variables."""
        self.board = {}
        self.current_player = 'X'
        self.is_first_turn = True
        self.pieces_placed_this_turn = 0
        self.game_over = False
        self.origin_offset = (0, 0)
        
        self.current_turn_moves = []
        self.last_turn_moves = []
        
        self.x_threats = set()
        self.o_threats = set()
        
        self.invalidate()
        if hasattr(self, 'on_state_change') and self.on_state_change:
            self.on_state_change()

    def pixel_to_axial(self, x, y):
        q_float = (math.sqrt(3)/3 * x - 1/3 * y) / self.hex_size
        r_float = (2/3 * y) / self.hex_size
        
        s_float = -q_float - r_float
        q, r, s = round(q_float), round(r_float), round(s_float)
        q_diff, r_diff, s_diff = abs(q - q_float), abs(r - r_float), abs(s - s_float)
        
        if q_diff > r_diff and q_diff > s_diff:
            q = -r - s
        elif r_diff > s_diff:
            r = -q - s
            
        return q, r

    def update_hover(self, x, y):
        if self.game_over:
            return
            
        raw_q, raw_r = self.pixel_to_axial(x, y)
        q = raw_q - self.origin_offset[0]
        r = raw_r - self.origin_offset[1]
        
        if self.hovered_hex != (q, r):
            self.hovered_hex = (q, r)
            self.invalidate()

    def get_winning_threats(self, player):
        threats = set()
        directions = [(1, 0), (0, 1), (1, -1)]
        opponent = 'O' if player == 'X' else 'X'

        for (q, r), piece in self.board.items():
            if piece != player:
                continue

            for dq, dr in directions:
                for i in range(6):
                    start_q = q - i * dq
                    start_r = r - i * dr

                    empty_cells = []
                    player_count = 0
                    blocked = False

                    for j in range(6):
                        curr_q = start_q + j * dq
                        curr_r = start_r + j * dr
                        cell_piece = self.board.get((curr_q, curr_r))

                        if cell_piece == player:
                            player_count += 1
                        elif cell_piece == opponent:
                            blocked = True
                            break 
                        else:
                            empty_cells.append((curr_q, curr_r))

                    if not blocked and player_count >= 4:
                        for cell in empty_cells:
                            threats.add(cell)
                            
        return threats

    def update_threats(self):
        self.x_threats = self.get_winning_threats('X')
        self.o_threats = self.get_winning_threats('O')

    def check_win(self, q, r, player):
        directions = [
            ((1, 0), (-1, 0)),
            ((0, 1), (0, -1)),
            ((1, -1), (-1, 1))
        ]
        
        for dir1, dir2 in directions:
            count = 1
            for dq, dr in (dir1, dir2):
                cur_q, cur_r = q + dq, r + dr
                while self.board.get((cur_q, cur_r)) == player:
                    count += 1
                    cur_q += dq
                    cur_r += dr
                    
            if count >= 6:
                return True
        return False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.game_over:
            pos = event.scenePos()
            raw_q, raw_r = self.pixel_to_axial(pos.x(), pos.y())
            
            if not self.board:
                self.origin_offset = (raw_q, raw_r)
                
            q = raw_q - self.origin_offset[0]
            r = raw_r - self.origin_offset[1]
            
            if (q, r) not in self.board:
                self.board[(q, r)] = self.current_player
                self.pieces_placed_this_turn += 1
                self.current_turn_moves.append((q, r))
                
                self.update_threats()
                
                if self.check_win(q, r, self.current_player):
                    self.game_over = True
                    self.hovered_hex = None 
                    self.last_turn_moves = list(self.current_turn_moves) 
                    self.invalidate()
                    if self.on_win:
                        self.on_win("Red (X)" if self.current_player == 'X' else "Blue (O)")
                    if self.on_state_change:
                        self.on_state_change()
                    return
                
                max_pieces = 1 if (self.is_first_turn and self.current_player == 'X') else 2
                
                if self.pieces_placed_this_turn >= max_pieces:
                    self.current_player = 'O' if self.current_player == 'X' else 'X'
                    self.pieces_placed_this_turn = 0
                    self.is_first_turn = False
                    self.last_turn_moves = list(self.current_turn_moves) 
                    self.current_turn_moves = [] 
                
                self.invalidate()
                if self.on_state_change:
                    self.on_state_change()
        else:
            super().mousePressEvent(event)

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor("#ffffff"))
        
        s = self.hex_size
        w = math.sqrt(3) * s
        h = 2 * s
        
        left, right = rect.left(), rect.right()
        top, bottom = rect.top(), rect.bottom()
        
        min_col = int(left / w) - 1
        max_col = int(right / w) + 1
        min_row = int(top / (h * 0.75)) - 1
        max_row = int(bottom / (h * 0.75)) + 1
        
        hex_pen = QPen(QColor("#000000"), 1.5)
        x_pen = QPen(QColor("#d32f2f"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        o_pen = QPen(QColor("#1976d2"), 4, Qt.PenStyle.SolidLine)
        
        hover_brush = QBrush(QColor("#eeeeee")) 
        last_move_brush = QBrush(QColor("#fff9c4"))     
        x_threat_brush = QBrush(QColor("#ffcdd2"))      
        o_threat_brush = QBrush(QColor("#bbdefb"))      
        both_threat_brush = QBrush(QColor("#e1bee7"))   

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                x = col * w
                y = row * h * 0.75
                
                if row % 2 != 0:
                    x += w / 2
                    
                points = [
                    QPointF(x, y - s), QPointF(x + w/2, y - s/2), QPointF(x + w/2, y + s/2),
                    QPointF(x, y + s), QPointF(x - w/2, y + s/2), QPointF(x - w/2, y - s/2),
                ]
                
                raw_q = col - (row // 2)
                raw_r = row
                
                q = raw_q - self.origin_offset[0]
                r = raw_r - self.origin_offset[1]
                
                if (q, r) == self.hovered_hex and (q, r) not in self.board:
                    painter.setBrush(hover_brush)
                elif (q, r) in self.board and (q, r) in self.last_turn_moves:
                    painter.setBrush(last_move_brush)
                elif (q, r) not in self.board and self.show_highlights:
                    is_x_threat = (q, r) in self.x_threats
                    is_o_threat = (q, r) in self.o_threats
                    
                    if is_x_threat and is_o_threat:
                        painter.setBrush(both_threat_brush)
                    elif is_x_threat:
                        painter.setBrush(x_threat_brush)
                    elif is_o_threat:
                        painter.setBrush(o_threat_brush)
                    else:
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                else:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                
                painter.setPen(hex_pen)
                painter.drawPolygon(QPolygonF(points))
                
                if (q, r) in self.board:
                    player = self.board[(q, r)]
                    radius = s * 0.55 
                    
                    if player == 'X':
                        painter.setPen(x_pen)
                        offset = radius * 0.707 
                        painter.drawLine(QPointF(x - offset, y - offset), QPointF(x + offset, y + offset))
                        painter.drawLine(QPointF(x - offset, y + offset), QPointF(x + offset, y - offset))
                    else:
                        painter.setPen(o_pen)
                        painter.drawEllipse(QPointF(x, y), radius, radius)


class HexBoardView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = InfiniteHexScene(self)
        self.scene.setSceneRect(-1e7, -1e7, 2e7, 2e7)
        self.scene.on_win = self.show_win_screen
        self.scene.on_state_change = self.update_turn_display 
        self.setScene(self.scene)
        
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.centerOn(0, 0)
        self.current_zoom = 1.0
        
        self.setMouseTracking(True)
        
        self._is_panning = False
        self._pan_start_pos = None
        self.keys_pressed = set()
        self.pan_speed = 15 
        self.pan_timer = QTimer(self)
        self.pan_timer.timeout.connect(self.smooth_pan)
        self.pan_timer.start(16) 
        
        self._just_activated = False
        
        self.setup_ui_overlay()    
        self.setup_hud()           
        self.setup_escape_menu()   
        
        self.update_center_coords()
        self.update_turn_display()

    def _clear_activation_flag(self):
        self._just_activated = False

    def setup_escape_menu(self):
        self.esc_menu = QFrame(self)
        self.esc_menu.setStyleSheet("background-color: rgba(0, 0, 0, 180); border: none;")
        self.esc_menu.hide()

        self.esc_layout = QVBoxLayout(self.esc_menu)
        self.esc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.menu_content = QWidget()
        self.menu_content.setStyleSheet("background: transparent; border: none;")
        content_layout = QVBoxLayout(self.menu_content)
        content_layout.setSpacing(20)
        
        title = QLabel("Config")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: white; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        cb_style = "QCheckBox { color: white; font-size: 18px; border: none; } QCheckBox::indicator { width: 18px; height: 18px; }"

        self.cb_coords = QCheckBox("Coordinates")
        self.cb_coords.setChecked(True)
        self.cb_coords.setStyleSheet(cb_style)
        self.cb_coords.toggled.connect(self.toggle_coords)
        
        self.cb_next_turn = QCheckBox("Next Turn")
        self.cb_next_turn.setChecked(True)
        self.cb_next_turn.setStyleSheet(cb_style)
        self.cb_next_turn.toggled.connect(self.toggle_next_turn)
        
        self.cb_checks = QCheckBox("Checks")
        self.cb_checks.setChecked(True)
        self.cb_checks.setStyleSheet(cb_style)
        self.cb_checks.toggled.connect(self.toggle_checks)
        
        resume_btn = QPushButton("Resume")
        resume_btn.setStyleSheet("padding: 10px 30px; font-size: 18px; color: black; background-color: white; border-radius: 5px;")
        resume_btn.clicked.connect(self.toggle_esc_menu)
        
        content_layout.addWidget(title)
        content_layout.addWidget(self.cb_coords)
        content_layout.addWidget(self.cb_next_turn)
        content_layout.addWidget(self.cb_checks)
        content_layout.addWidget(resume_btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        self.esc_layout.addWidget(self.menu_content)

    def toggle_coords(self, checked):
        self.center_coord_label.setVisible(checked)
        self.mouse_coord_label.setVisible(checked)
        self.update_hud_visibility()

    def toggle_next_turn(self, checked):
        self.turn_container.setVisible(checked)
        self.update_hud_visibility()

    def update_hud_visibility(self):
        if not self.cb_coords.isChecked() and not self.cb_next_turn.isChecked():
            self.hud_panel.hide()
        else:
            self.hud_panel.show()
            self.hud_panel.adjustSize()

    def toggle_checks(self, checked):
        self.scene.show_highlights = checked
        self.scene.invalidate() 
        self.viewport().update()

    def toggle_esc_menu(self):
        if self.esc_menu.isVisible():
            self.esc_menu.hide()
        else:
            self.esc_menu.resize(self.size())
            self.esc_menu.show()
            self.esc_menu.raise_()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.toggle_esc_menu()
        elif event.key() == Qt.Key.Key_R:
            self.centerOn(0, 0) 
            self.update_center_coords()
        else:
            self.keys_pressed.add(event.key())
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in self.keys_pressed:
            self.keys_pressed.remove(event.key())
        super().keyReleaseEvent(event)

    def smooth_pan(self):
        if not self.keys_pressed: return

        dx = dy = 0
        if Qt.Key.Key_Left in self.keys_pressed:  dx = -self.pan_speed
        if Qt.Key.Key_Right in self.keys_pressed: dx = self.pan_speed
        if Qt.Key.Key_Up in self.keys_pressed:    dy = -self.pan_speed
        if Qt.Key.Key_Down in self.keys_pressed:  dy = self.pan_speed

        if dx != 0 or dy != 0:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + dx)
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + dy)
            self.update_center_coords()

    def mousePressEvent(self, event):
        if self._just_activated:
            self._just_activated = False
            event.accept()
            return

        if event.button() == Qt.MouseButton.RightButton:
            self._is_panning = True
            self._pan_start_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_panning:
            delta = event.pos() - self._pan_start_pos
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._pan_start_pos = event.pos()
            self.update_center_coords()
            event.accept()
        else:
            pos = self.mapToScene(event.pos())
            self.scene.update_hover(pos.x(), pos.y())
            
            raw_q, raw_r = self.scene.pixel_to_axial(pos.x(), pos.y())
            q = raw_q - self.scene.origin_offset[0]
            r = raw_r - self.scene.origin_offset[1]
            
            self.mouse_coord_label.setText(f"Mouse:  ({q + r}, {-r})")
            self.hud_panel.adjustSize()
            
            super().mouseMoveEvent(event)

    def setup_hud(self):
        self.hud_panel = QFrame(self)
        self.hud_panel.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 220);
                border: 2px solid #000000;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self.hud_panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        label_style = "border: none; background: transparent; font-family: monospace; font-size: 14px; font-weight: bold; color: #000000;"
        
        self.center_coord_label = QLabel("Center: (0, 0)")
        self.center_coord_label.setStyleSheet(label_style)
        
        self.mouse_coord_label = QLabel("Mouse:  (-, -)")
        self.mouse_coord_label.setStyleSheet(label_style)
        
        self.turn_container = QWidget()
        self.turn_container.setStyleSheet("background: transparent; border: none;")
        turn_layout = QHBoxLayout(self.turn_container)
        turn_layout.setContentsMargins(0, 5, 0, 0) 
        
        self.turn_icon_label = QLabel()
        self.turn_icon_label.setStyleSheet("border: none; background: transparent;")
        
        self.turn_text_label = QLabel("0 placements left")
        self.turn_text_label.setStyleSheet(label_style)
        
        turn_layout.addWidget(self.turn_icon_label)
        turn_layout.addWidget(self.turn_text_label)
        turn_layout.addStretch() 
        
        layout.addWidget(self.center_coord_label)
        layout.addWidget(self.mouse_coord_label)
        layout.addWidget(self.turn_container)
        
        self.hud_panel.move(20, 20)
        self.hud_panel.show()

    def update_turn_display(self):
        if not hasattr(self, 'hud_panel'): return
            
        player = self.scene.current_player
        is_first = self.scene.is_first_turn
        placed = self.scene.pieces_placed_this_turn
        game_over = self.scene.game_over
        
        max_pieces = 1 if (is_first and player == 'X') else 2
        pieces_left = max_pieces - placed
        
        if game_over:
            self.turn_text_label.setText("Game Over")
        else:
            plural = "s" if pieces_left > 1 else ""
            self.turn_text_label.setText(f"{pieces_left} placement{plural} left")
        
        pixmap = QPixmap(20, 20)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if player == 'X':
            pen = QPen(QColor("#d32f2f"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(3, 3, 17, 17)
            painter.drawLine(3, 17, 17, 3)
        else:
            pen = QPen(QColor("#1976d2"), 3, Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawEllipse(3, 3, 14, 14)
            
        painter.end()
        self.turn_icon_label.setPixmap(pixmap)
        self.hud_panel.adjustSize()

    def update_center_coords(self):
        if not hasattr(self, 'hud_panel'): return
            
        center_pixel = self.viewport().rect().center()
        scene_pos = self.mapToScene(center_pixel)
        raw_q, raw_r = self.scene.pixel_to_axial(scene_pos.x(), scene_pos.y())
        
        q = raw_q - self.scene.origin_offset[0]
        r = raw_r - self.scene.origin_offset[1]
        
        self.center_coord_label.setText(f"Center: ({q + r}, {-r})")
        self.hud_panel.adjustSize() 

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.update_center_coords()

    def setup_ui_overlay(self):
        self.overlay = QFrame(self)
        self.overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 230); 
                border: 2px solid black; 
                border-radius: 10px;
            }
        """)
        
        layout = QVBoxLayout(self.overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        self.win_label = QLabel("Winner!")
        self.win_label.setStyleSheet("font-size: 24px; font-weight: bold; color: black; border: none; background: transparent;")
        self.win_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.reset_btn = QPushButton("New Game")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                padding: 10px; font-size: 16px; color: black; background-color: #f0f0f0; 
                border: 1px solid black; border-radius: 5px;
            }
            QPushButton:hover { background-color: #e0e0e0; }
        """)
        self.reset_btn.clicked.connect(self.reset_game)
        
        layout.addWidget(self.win_label)
        layout.addWidget(self.reset_btn)
        
        self.overlay.resize(300, 150)
        self.overlay.hide()

    def show_win_screen(self, winner_text):
        # Determine color based on who won, and wrap the name in an HTML span tag
        color = "#d32f2f" if "Red" in winner_text else "#1976d2"
        self.win_label.setText(f'<span style="color: {color};">{winner_text}</span> wins!')
        self.overlay.show()
        self.overlay.raise_()

    def reset_game(self):
        self.scene.reset_state()
        self.overlay.hide()
        
        self.resetTransform()
        self.current_zoom = 1.0
        self.centerOn(0, 0)
        self.update_center_coords()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'overlay'):
            x = (self.width() - self.overlay.width()) // 2
            y = (self.height() - self.overlay.height()) // 2
            self.overlay.move(x, y)
            
        if hasattr(self, 'esc_menu') and self.esc_menu.isVisible():
            self.esc_menu.resize(self.size())
            
        self.update_center_coords()

    def event(self, event):
        if event.type() == QEvent.Type.WindowActivate:
            self._just_activated = True
            QTimer.singleShot(100, self._clear_activation_flag)

        if event.type() == QEvent.Type.NativeGesture:
            if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                zoom_factor = 1.0 + event.value()
                new_zoom = self.current_zoom * zoom_factor
                if 0.2 < new_zoom < 5.0:
                    self.scale(zoom_factor, zoom_factor)
                    self.current_zoom = new_zoom
                    self.update_center_coords() 
                return True
        return super().event(event)

    def wheelEvent(self, event):
        is_trackpad = event.phase() != Qt.ScrollPhase.NoScrollPhase

        if is_trackpad:
            pixel_delta = event.pixelDelta()
            angle_delta = event.angleDelta()
            
            dx = pixel_delta.x() if not pixel_delta.isNull() else angle_delta.x() / 8
            dy = pixel_delta.y() if not pixel_delta.isNull() else angle_delta.y() / 8
            
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - dx))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - dy))
            event.accept()
            
        else:
            angle_delta = event.angleDelta()
            if not angle_delta.isNull():
                zoom_in_factor = 1.15
                zoom_out_factor = 1.0 / zoom_in_factor
                
                if angle_delta.y() > 0:
                    zoom_factor = zoom_in_factor
                else:
                    zoom_factor = zoom_out_factor
                    
                new_zoom = self.current_zoom * zoom_factor
                if 0.2 < new_zoom < 5.0:
                    self.scale(zoom_factor, zoom_factor)
                    self.current_zoom = new_zoom
                    self.update_center_coords() 
                    
            event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    view = HexBoardView()
    view.setWindowTitle("Hex-Tac-Toe")
    view.resize(1000, 800)
    view.show()
    sys.exit(app.exec())
