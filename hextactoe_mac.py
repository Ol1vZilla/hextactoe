import sys
import math
from PyQt6.QtWidgets import (QApplication, QGraphicsView, QGraphicsScene, 
                             QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton)
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygonF, QBrush, QPixmap
from PyQt6.QtCore import Qt, QPointF, QEvent

class InfiniteHexScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hex_size = 40
        self.on_win = None
        self.on_state_change = None 
        self.hovered_hex = None
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
        
        # Track winning threats for highlighting
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
        """Finds all empty hexagons that would complete a 6-in-a-row for the given player."""
        threats = set()
        directions = [(1, 0), (0, 1), (1, -1)]
        opponent = 'O' if player == 'X' else 'X'

        # Check every piece belonging to the player
        for (q, r), piece in self.board.items():
            if piece != player:
                continue

            # For each piece, check the 3 axes
            for dq, dr in directions:
                # Shift the start of the 6-hex window backward to check all overlapping segments
                for i in range(6):
                    start_q = q - i * dq
                    start_r = r - i * dr

                    empty_cells = []
                    player_count = 0
                    blocked = False

                    # Check the 6-hexagon window
                    for j in range(6):
                        curr_q = start_q + j * dq
                        curr_r = start_r + j * dr
                        cell_piece = self.board.get((curr_q, curr_r))

                        if cell_piece == player:
                            player_count += 1
                        elif cell_piece == opponent:
                            blocked = True
                            break # Window is dead, opponent blocked it
                        else:
                            empty_cells.append((curr_q, curr_r))

                    # If no opponent pieces and we have at least 4 pieces, the empty spots are lethal threats
                    if not blocked and player_count >= 4:
                        for cell in empty_cells:
                            threats.add(cell)
                            
        return threats

    def update_threats(self):
        """Refreshes the threat sets after a move."""
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
                
                # Update the threat highlights after every placement
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
        
        # Brushes for all our different highlight states
        hover_brush = QBrush(QColor("#eeeeee")) 
        last_move_brush = QBrush(QColor("#fff9c4"))     # Yellow
        x_threat_brush = QBrush(QColor("#ffcdd2"))      # Red
        o_threat_brush = QBrush(QColor("#bbdefb"))      # Blue
        both_threat_brush = QBrush(QColor("#e1bee7"))   # Purple (if both threaten same hex)

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
                
                # Determine what background color this hex should get
                if (q, r) == self.hovered_hex and (q, r) not in self.board:
                    painter.setBrush(hover_brush)
                elif (q, r) in self.board and (q, r) in self.last_turn_moves:
                    painter.setBrush(last_move_brush)
                elif (q, r) not in self.board:
                    # Check for threats on empty hexagons
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
        
        self.setup_ui_overlay()
        self.setup_hud()
        
        self.update_center_coords()
        self.update_turn_display()

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
        
        turn_layout = QHBoxLayout()
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
        layout.addLayout(turn_layout)
        
        self.hud_panel.move(20, 20)
        self.hud_panel.show()

    def update_turn_display(self):
        if not hasattr(self, 'hud_panel'):
            return
            
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
        if not hasattr(self, 'hud_panel'):
            return
            
        center_pixel = self.viewport().rect().center()
        scene_pos = self.mapToScene(center_pixel)
        raw_q, raw_r = self.scene.pixel_to_axial(scene_pos.x(), scene_pos.y())
        
        q = raw_q - self.scene.origin_offset[0]
        r = raw_r - self.scene.origin_offset[1]
        
        user_x = q + r 
        user_y = -r    
        
        self.center_coord_label.setText(f"Center: ({user_x}, {user_y})")
        self.hud_panel.adjustSize() 

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.update_center_coords()

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.pos())
        self.scene.update_hover(pos.x(), pos.y())
        
        raw_q, raw_r = self.scene.pixel_to_axial(pos.x(), pos.y())
        q = raw_q - self.scene.origin_offset[0]
        r = raw_r - self.scene.origin_offset[1]
        
        user_x = q + r
        user_y = -r
        self.mouse_coord_label.setText(f"Mouse:  ({user_x}, {user_y})")
        self.hud_panel.adjustSize()
        
        super().mouseMoveEvent(event)

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
        self.win_label.setStyleSheet("font-size: 24px; font-weight: bold; border: none; background: transparent;")
        self.win_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.reset_btn = QPushButton("New Game")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                padding: 10px; font-size: 16px; background-color: #f0f0f0; 
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
        self.win_label.setText(f"{winner_text} wins!")
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
        self.update_center_coords()

    def event(self, event):
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
        pixel_delta = event.pixelDelta()
        if not pixel_delta.isNull():
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - pixel_delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - pixel_delta.y())
            event.accept()
        else:
            angle_delta = event.angleDelta()
            if not angle_delta.isNull():
                self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - angle_delta.x())
                self.verticalScrollBar().setValue(self.verticalScrollBar().value() - angle_delta.y())
                event.accept()
            else:
                super().wheelEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    view = HexBoardView()
    view.setWindowTitle("Hex-Mac-Toe")
    view.resize(1000, 800)
    view.show()
    sys.exit(app.exec())
