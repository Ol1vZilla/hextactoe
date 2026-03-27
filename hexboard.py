import sys
import math
import json
import base64
from PyQt6.QtWidgets import (QApplication, QGraphicsView, QGraphicsScene, 
                             QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QCheckBox, QWidget, QComboBox, QLineEdit, QTextEdit,
                             QScrollArea)
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygonF, QBrush, QPixmap, QKeySequence
from PyQt6.QtCore import Qt, QPointF, QEvent, QTimer, QRectF

class InfiniteHexScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hex_size = 40
        self.on_win = None
        self.on_state_change = None 
        self.hovered_hex = None
        self.show_highlights = True
        self.render_mode = "Tic-Tac-Toe" 
        self.board_style = "Flush"
        self.win_border_type = "Yellow Pieces + Border"
        
        self.last_move_style = "Transparent"
        self.last_move_color_name = "Yellow"
        
        self.bg_color_name = "White"
        self.border_color_name = "Black"
        
        self.bg_colors = {
            "White": "#ffffff",
            "Dark": "#121212",
            "Paper": "#f4f1ea",
            "Navy": "#0e172a",
            "Custom": "#ffffff"
        }
        
        self.border_colors = {
            "Black": "#000000",
            "White": "#ffffff",
            "Gray": "#273044",
            "None": "None",
            "Custom": "#000000"
        }

        self.last_move_colors = {
            "Yellow": "#ffee58",
            "White": "#ffffff",
            "Cyan": "#00ffff",
            "Custom": "#ffee58"
        }
        
        self.placement_animation_type = "None"
        self.active_animations = {}
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self._step_animations)
        
        # Time Control variables
        self.tc_mode_config = "Unlimited"
        self.tc_turn_sec = 30
        self.tc_move_sec = 15
        self.tc_match_m_config = 10
        self.tc_match_i_config = 5
        
        self.active_tc_mode = "Unlimited"
        self.active_time_left = 0
        self.p1_time = 0
        self.p2_time = 0
        self.tc_match_inc_sec = 0
        self.is_paused = False
        
        self.game_clock = QTimer()
        self.game_clock.timeout.connect(self._tick_timer)
        self.on_time_tick = None
        
        # Color mapping for players
        self.color_map = {
            "Red": {"base": "#d32f2f"},
            "Blue": {"base": "#1976d2"},
            "Green": {"base": "#388e3c"},
            "Yellow": {"base": "#fbc02d"},
            "Purple": {"base": "#7b1fa2"},
            "Orange": {"base": "#f57c00"},
            "Black": {"base": "#000000"},
            "Custom P1": {"base": "#d32f2f"},
            "Custom P2": {"base": "#1976d2"}
        }
        self.p1_color_name = "Red"
        self.p2_color_name = "Blue"
        
        self.history = [] 
        self.reset_state()

    def _tick_timer(self):
        if self.game_over or self.active_tc_mode == "Unlimited" or self.is_paused:
            return

        if self.active_tc_mode in ["Turn Based", "Move Based"]:
            self.active_time_left -= 1
            if self.active_time_left <= 0:
                self.active_time_left = 0
                self.time_out_win()
        elif self.active_tc_mode == "Match Based":
            if self.current_player == 'X':
                self.p1_time -= 1
                if self.p1_time <= 0:
                    self.p1_time = 0
                    self.time_out_win('O')
            else:
                self.p2_time -= 1
                if self.p2_time <= 0:
                    self.p2_time = 0
                    self.time_out_win('X')

        if self.on_time_tick:
            self.on_time_tick()

    def time_out_win(self, winner=None):
        self.game_over = True
        self.anim_timer.stop()
        self.game_clock.stop()
        if not winner:
            winner = 'O' if self.current_player == 'X' else 'X'
        if self.on_win:
            winner_color = self.p1_color_name if winner == 'X' else self.p2_color_name
            self.on_win(f"{winner_color} ({winner})", True)
        if self.on_state_change:
            self.on_state_change()

    def reset_state(self):
        """Clears the board and resets all game variables."""
        self.board = {}
        self.current_player = 'X'
        self.is_first_turn = True
        self.pieces_placed_this_turn = 0
        self.game_over = False
        self.origin_offset = (0, 0)
        self.is_paused = False
        
        self.current_turn_moves = []
        self.last_turn_moves = []
        
        self.x_threats = set()
        self.o_threats = set()
        self.winning_hexes = set()
        self.history = []
        
        self.active_tc_mode = getattr(self, 'tc_mode_config', "Unlimited")
        self.p1_time = getattr(self, 'tc_match_m_config', 10) * 60
        self.p2_time = getattr(self, 'tc_match_m_config', 10) * 60
        self.tc_match_inc_sec = getattr(self, 'tc_match_i_config', 5)
        self.active_time_left = getattr(self, 'tc_turn_sec', 30) if self.active_tc_mode == "Turn Based" else getattr(self, 'tc_move_sec', 15)
        
        self.active_animations = {}
        if hasattr(self, 'anim_timer'):
            self.anim_timer.stop()
            
        if hasattr(self, 'game_clock'):
            self.game_clock.stop()
        
        self.invalidate()
        if hasattr(self, 'on_state_change') and self.on_state_change:
            self.on_state_change()
        if hasattr(self, 'on_time_tick') and self.on_time_tick:
            self.on_time_tick()

    def _step_animations(self):
        to_remove = []
        for coords in self.active_animations:
            self.active_animations[coords] += 0.08
            if self.active_animations[coords] >= 1.0:
                self.active_animations[coords] = 1.0
                to_remove.append(coords)
                
        for coords in to_remove:
            del self.active_animations[coords]
            
        self.invalidate()
        if not self.active_animations:
            self.anim_timer.stop()

    def undo_move(self):
        if not self.history or self.game_over:
            return

        last_state = self.history.pop()
        self.board = last_state['board']
        self.current_player = last_state['current_player']
        self.is_first_turn = last_state['is_first_turn']
        self.pieces_placed_this_turn = last_state['pieces_placed_this_turn']
        self.current_turn_moves = last_state['current_turn_moves']
        self.last_turn_moves = last_state['last_turn_moves']
        
        if self.active_tc_mode in ["Turn Based", "Move Based"]:
            self.active_time_left = self.tc_turn_sec if self.active_tc_mode == "Turn Based" else self.tc_move_sec
        elif self.active_tc_mode == "Match Based":
            if self.p1_time <= 0: self.p1_time = 5
            if self.p2_time <= 0: self.p2_time = 5
            
        if not self.game_over and self.board and self.active_tc_mode != "Unlimited":
            self.game_clock.start(1000)
            
        self.active_animations.clear()
        self.anim_timer.stop()
        
        self.update_threats()
        self.invalidate()
        if self.on_state_change:
            self.on_state_change()
        if self.on_time_tick:
            self.on_time_tick()

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
            winning_line = [(q, r)]
            for dq, dr in (dir1, dir2):
                cur_q, cur_r = q + dq, r + dr
                while self.board.get((cur_q, cur_r)) == player:
                    count += 1
                    winning_line.append((cur_q, cur_r))
                    cur_q += dq
                    cur_r += dr
                    
            if count >= 6:
                self.winning_hexes = set(winning_line)
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
                self.history.append({
                    'board': self.board.copy(),
                    'current_player': self.current_player,
                    'is_first_turn': self.is_first_turn,
                    'pieces_placed_this_turn': self.pieces_placed_this_turn,
                    'current_turn_moves': list(self.current_turn_moves),
                    'last_turn_moves': list(self.last_turn_moves)
                })

                self.board[(q, r)] = self.current_player
                self.pieces_placed_this_turn += 1
                self.current_turn_moves.append((q, r))
                
                # Start clock on the very first placement of the game
                if self.is_first_turn and self.pieces_placed_this_turn == 1 and len(self.board) == 1:
                    if self.active_tc_mode != "Unlimited":
                        self.game_clock.start(1000)
                        
                if self.active_tc_mode == "Move Based":
                    self.active_time_left = self.tc_move_sec
                    if self.on_time_tick: self.on_time_tick()
                
                if self.placement_animation_type != "None":
                    self.active_animations[(q, r)] = 0.0
                    if not self.anim_timer.isActive():
                        self.anim_timer.start(16)
                
                self.update_threats()
                
                if self.check_win(q, r, self.current_player):
                    self.game_over = True
                    self.hovered_hex = None 
                    self.last_turn_moves = list(self.current_turn_moves) 
                    self.invalidate()
                    self.game_clock.stop()
                    if self.on_win:
                        winner_color_name = self.p1_color_name if self.current_player == 'X' else self.p2_color_name
                        self.on_win(f"{winner_color_name} ({self.current_player})", False)
                    if self.on_state_change:
                        self.on_state_change()
                    return
                
                max_pieces = 1 if (self.is_first_turn and self.current_player == 'X') else 2
                
                if self.pieces_placed_this_turn >= max_pieces:
                    # Apply match increment
                    if self.active_tc_mode == "Match Based":
                        if self.current_player == 'X':
                            self.p1_time += self.tc_match_inc_sec
                        else:
                            self.p2_time += self.tc_match_inc_sec
                            
                    self.current_player = 'O' if self.current_player == 'X' else 'X'
                    self.pieces_placed_this_turn = 0
                    self.is_first_turn = False
                    self.last_turn_moves = list(self.current_turn_moves) 
                    self.current_turn_moves = [] 
                    
                    if self.active_tc_mode == "Turn Based":
                        self.active_time_left = self.tc_turn_sec
                        
                    if self.on_time_tick: self.on_time_tick()
                
                self.invalidate()
                if self.on_state_change:
                    self.on_state_change()
        else:
            super().mousePressEvent(event)

    def drawBackground(self, painter, rect):
        bg_hex = self.bg_colors.get(self.bg_color_name, "#ffffff")
        painter.fillRect(rect, QColor(bg_hex))
        
        s = self.hex_size
        w = math.sqrt(3) * s
        h = 2 * s
        
        # Calculate visual parameters for Flush vs Separated vs Circle
        shrink_factor = 0.90 if self.board_style in ["Separated", "Circle"] else 1.0
        draw_s = s * shrink_factor
        draw_w = math.sqrt(3) * draw_s
        
        left, right = rect.left(), rect.right()
        top, bottom = rect.top(), rect.bottom()
        
        min_col = int(left / w) - 1
        max_col = int(right / w) + 1
        min_row = int(top / (h * 0.75)) - 1
        max_row = int(bottom / (h * 0.75)) + 1
        
        # Setup dynamic colors
        x_base = self.color_map[self.p1_color_name]["base"]
        o_base = self.color_map[self.p2_color_name]["base"]

        border_val = self.border_colors.get(self.border_color_name, "#000000")
        if border_val == "None":
            hex_pen = QPen(Qt.PenStyle.NoPen)
        else:
            hex_pen = QPen(QColor(border_val), 1.5)

        x_pen = QPen(QColor(x_base), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        o_pen = QPen(QColor(o_base), 4, Qt.PenStyle.SolidLine)
        
        # Neutral transparent hover brush
        hover_brush = QBrush(QColor(128, 128, 128, 80)) 
        
        lm_color_hex = self.last_move_colors.get(self.last_move_color_name, "#ffee58")
        lm_qcolor = QColor(lm_color_hex)
        lm_qcolor.setAlpha(80) 
        last_move_brush = QBrush(lm_qcolor)    
        
        # True transparent threat highlights based on base color
        x_threat_c = QColor(x_base)
        x_threat_c.setAlpha(80)
        x_threat_brush = QBrush(x_threat_c)      
        
        o_threat_c = QColor(o_base)
        o_threat_c.setAlpha(80)
        o_threat_brush = QBrush(o_threat_c)      
        
        # Blend the two colors for overlapping threats
        both_c = QColor((x_threat_c.red() + o_threat_c.red()) // 2, 
                        (x_threat_c.green() + o_threat_c.green()) // 2, 
                        (x_threat_c.blue() + o_threat_c.blue()) // 2, 80)
        both_threat_brush = QBrush(both_c)   
        
        x_fill_brush = QBrush(QColor(x_base))
        o_fill_brush = QBrush(QColor(o_base))

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for row in range(min_row, max_row + 1):
            for col in range(min_col, max_col + 1):
                # Grid coordinates use standard 'w' and 'h'
                x = col * w
                y = row * h * 0.75
                
                if row % 2 != 0:
                    x += w / 2
                    
                # Visual points use 'draw_w' and 'draw_s' to separate them visually if selected
                points = [
                    QPointF(x, y - draw_s), QPointF(x + draw_w/2, y - draw_s/2), QPointF(x + draw_w/2, y + draw_s/2),
                    QPointF(x, y + draw_s), QPointF(x - draw_w/2, y + draw_s/2), QPointF(x - draw_w/2, y - draw_s/2),
                ]
                
                raw_q = col - (row // 2)
                raw_r = row
                
                q = raw_q - self.origin_offset[0]
                r = raw_r - self.origin_offset[1]
                
                # --- 1. DETERMINE BACKGROUND BRUSH ---
                bg_brush = Qt.BrushStyle.NoBrush
                if (q, r) == self.hovered_hex and (q, r) not in self.board:
                    bg_brush = hover_brush
                elif (q, r) in self.board and (q, r) in self.last_turn_moves and self.last_move_style == "Transparent":
                    bg_brush = last_move_brush
                elif (q, r) not in self.board and self.show_highlights:
                    is_x_threat = (q, r) in self.x_threats
                    is_o_threat = (q, r) in self.o_threats
                    if is_x_threat and is_o_threat:
                        bg_brush = both_threat_brush
                    elif is_x_threat:
                        bg_brush = x_threat_brush
                    elif is_o_threat:
                        bg_brush = o_threat_brush
                
                # --- 2. DRAW BASE HEX (Border & Non-piece background) ---
                painter.setBrush(bg_brush)
                painter.setPen(hex_pen)
                if self.board_style == "Circle":
                    circle_radius = draw_s * 0.866
                    painter.drawEllipse(QPointF(x, y), circle_radius, circle_radius)
                else:
                    painter.drawPolygon(QPolygonF(points))
                
                # --- 3. DRAW PIECE (Animated if applicable) ---
                if (q, r) in self.board:
                    painter.save()
                    anim_progress = 1.0
                    anim_type = "None"
                    
                    if (q, r) in self.active_animations:
                        anim_progress = self.active_animations[(q, r)]
                        anim_type = self.placement_animation_type
                        
                        painter.translate(x, y)
                        if anim_type == "Zoom In":
                            painter.scale(anim_progress, anim_progress)
                        elif anim_type == "Fade In":
                            painter.setOpacity(anim_progress)
                        elif anim_type == "Pop":
                            if anim_progress < 0.7:
                                s_anim = anim_progress / 0.7 * 1.2
                            else:
                                s_anim = 1.2 - ((anim_progress - 0.7) / 0.3) * 0.2
                            painter.scale(s_anim, s_anim)
                        elif anim_type == "Drop In":
                            y_offset = -(h / 3.0) * (1.0 - anim_progress) 
                            painter.translate(0, y_offset)
                        painter.translate(-x, -y)
                        
                    player = self.board[(q, r)]
                    
                    # Override piece colors to yellow if it's a winning piece and the option is selected
                    is_winning_piece = (q, r) in self.winning_hexes
                    turn_yellow = self.win_border_type in ["Yellow Pieces + Border", "Yellow Pieces Only"]
                    
                    if is_winning_piece and turn_yellow:
                        piece_color = QColor("#FFFF00")
                        current_x_pen = QPen(piece_color, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                        current_o_pen = QPen(piece_color, 4, Qt.PenStyle.SolidLine)
                        current_fill_brush = QBrush(piece_color)
                    else:
                        current_x_pen = x_pen
                        current_o_pen = o_pen
                        current_fill_brush = x_fill_brush if player == 'X' else o_fill_brush
                    
                    if self.render_mode == "Color Fill":
                        painter.setBrush(current_fill_brush)
                        painter.setPen(hex_pen) 
                        if self.board_style == "Circle":
                            circle_radius = draw_s * 0.866
                            painter.drawEllipse(QPointF(x, y), circle_radius, circle_radius)
                        else:
                            painter.drawPolygon(QPolygonF(points))
                    else:
                        painter.setBrush(Qt.BrushStyle.NoBrush) 
                        radius = draw_s * 0.55 
                        if player == 'X':
                            painter.setPen(current_x_pen)
                            offset = radius * 0.707 
                            painter.drawLine(QPointF(x - offset, y - offset), QPointF(x + offset, y + offset))
                            painter.drawLine(QPointF(x - offset, y + offset), QPointF(x + offset, y - offset))
                        else:
                            painter.setPen(current_o_pen)
                            painter.drawEllipse(QPointF(x, y), radius, radius)
                                    
                    painter.restore()

        # Draw last move highlights (if applicable)
        if self.last_turn_moves and self.last_move_style == "Border":
            lm_pen = QPen(QColor(lm_color_hex), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(lm_pen)
            
            for mq, mr in self.last_turn_moves:
                raw_q = mq + self.origin_offset[0]
                raw_r = mr + self.origin_offset[1]
                row = raw_r
                col = raw_q + (row // 2)
                
                x = col * w
                y = row * h * 0.75
                if row % 2 != 0:
                    x += w / 2
                    
                points = [
                    QPointF(x, y - draw_s), QPointF(x + draw_w/2, y - draw_s/2), QPointF(x + draw_w/2, y + draw_s/2),
                    QPointF(x, y + draw_s), QPointF(x - draw_w/2, y + draw_s/2), QPointF(x - draw_w/2, y - draw_s/2),
                ]
                
                if self.board_style == "Circle":
                    circle_radius = draw_s * 0.866
                    painter.drawEllipse(QPointF(x, y), circle_radius, circle_radius)
                else:
                    painter.drawPolygon(QPolygonF(points))

        # Check if this hexagon is part of the winning path and draw boundaries on top
        if self.winning_hexes and self.win_border_type not in ["None", "Yellow Pieces Only"]:
            win_pen = QPen(QColor("#FFFF00"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(win_pen)
            
            for wq, wr in self.winning_hexes:
                raw_q = wq + self.origin_offset[0]
                raw_r = wr + self.origin_offset[1]
                row = raw_r
                col = raw_q + (row // 2)
                
                x = col * w
                y = row * h * 0.75
                if row % 2 != 0:
                    x += w / 2
                    
                points = [
                    QPointF(x, y - draw_s), QPointF(x + draw_w/2, y - draw_s/2), QPointF(x + draw_w/2, y + draw_s/2),
                    QPointF(x, y + draw_s), QPointF(x - draw_w/2, y + draw_s/2), QPointF(x - draw_w/2, y - draw_s/2),
                ]
                
                if self.win_border_type in ["Highlight Each", "Yellow Pieces + Border"]:
                    if self.board_style == "Circle":
                        circle_radius = draw_s * 0.866
                        painter.drawEllipse(QPointF(x, y), circle_radius, circle_radius)
                    else:
                        painter.drawPolygon(QPolygonF(points))

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
        self._current_cluster_idx = 0
        
        self.setup_ui_overlay()    
        self.setup_confirm_overlay() 
        self.setup_settings_confirm_overlay() 
        self.setup_export_overlay()
        self.setup_import_overlay()
        self.setup_quit_confirm_overlay()
        self.setup_snap_buttons() 
        self.setup_hud()            
        self.setup_escape_menu()   
        
        self.update_center_coords()
        self.update_turn_display()
        self.update_ui_theme()

    def _clear_activation_flag(self):
        self._just_activated = False

    def get_action_clusters(self):
        if not self.scene.board:
            return []
            
        unvisited = set(self.scene.board.keys())
        clusters = []
        
        def hex_distance(h1, h2):
            q1, r1 = h1
            q2, r2 = h2
            return max(abs(q1 - q2), abs(r1 - r2), abs(-q1-r1 - (-q2-r2)))

        while unvisited:
            start_hex = unvisited.pop()
            current_cluster = {start_hex}
            queue = [start_hex]
            
            while queue:
                curr = queue.pop(0)
                to_remove = []
                for other in unvisited:
                    # If areas are 6 tiles apart they are considered separate.
                    # Therefore, distance <= 5 groups them in the same area.
                    if hex_distance(curr, other) <= 5: 
                        current_cluster.add(other)
                        queue.append(other)
                        to_remove.append(other)
                for item in to_remove:
                    unvisited.remove(item)
            clusters.append(current_cluster)
        
        # Sort by size to snap to the primary action area first
        clusters.sort(key=len, reverse=True)
        return clusters

    def update_ui_theme(self):
        """Updates the styling of all HUD components and overlays to match the game board colors."""
        bg_name = self.scene.bg_color_name
        bo_name = self.scene.border_color_name
        
        bg_hex = self.scene.bg_colors.get(bg_name, "#ffffff")
        bo_hex = self.scene.border_colors.get(bo_name, "#000000")
        if bo_hex == "None":
            bo_hex = "transparent"
            
        is_dark = bg_name in ["Dark", "Navy"]
        text_color = "#ffffff" if is_dark else "#000000"
        btn_bg = "rgba(255, 255, 255, 30)" if is_dark else "rgba(255, 255, 255, 220)"
        btn_hover = "rgba(255, 255, 255, 50)" if is_dark else "rgba(230, 230, 230, 220)"
        input_bg = "#2a2a2a" if is_dark else "#ffffff"
        
        hover_colors = {
            "White": "#e6e6e6",
            "Dark": "#2c2c2c",
            "Paper": "#e8e4db",
            "Navy": "#1e293b",
            "Custom": "#e6e6e6"
        }
        window_btn_hover = hover_colors.get(bg_name, "#e6e6e6")
        
        hud_style = f"""
            QFrame {{ background-color: {bg_hex}; border: 2px solid {bo_hex}; border-radius: 8px; }}
            QLabel {{ color: {text_color}; border: none; background: transparent; font-family: monospace; font-size: 14px; font-weight: bold; }}
        """
        self.hud_panel.setStyleSheet(hud_style)
        
        if hasattr(self, 'standalone_timer_panel'):
            self.standalone_timer_panel.setStyleSheet(hud_style)
            self.standalone_timer_label.setStyleSheet(f"color: {text_color}; border: none; background: transparent; font-family: monospace; font-size: 18px; font-weight: bold;")
        if hasattr(self, 'hud_timer_label'):
            self.hud_timer_label.setStyleSheet(f"color: {text_color}; border: none; background: transparent; font-family: monospace; font-size: 16px; font-weight: bold;")
            
        overlay_style = f"""
            QFrame {{ background-color: {bg_hex}; border: 2px solid {bo_hex}; border-radius: 10px; }}
            QLabel {{ color: {text_color}; border: none; background: transparent; }}
            QPushButton {{
                background-color: {btn_bg};
                border: 2px solid {bo_hex};
                border-radius: 8px;
                font-family: monospace;
                font-size: 14px;
                font-weight: bold;
                color: {text_color};
                padding: 10px 15px;
            }}
            QPushButton:hover {{ background-color: {btn_hover}; }}
            QTextEdit, QLineEdit {{
                background-color: {input_bg};
                border: 1px solid {bo_hex};
                color: {text_color};
                border-radius: 4px;
                font-family: monospace;
                font-size: 14px;
            }}
        """
        
        self.overlay.setStyleSheet(overlay_style)
        self.confirm_overlay.setStyleSheet(overlay_style)
        self.settings_confirm_overlay.setStyleSheet(overlay_style)
        self.quit_confirm_overlay.setStyleSheet(overlay_style)
        self.export_overlay.setStyleSheet(overlay_style)
        self.import_overlay.setStyleSheet(overlay_style)
        
        window_btn_style = f"""
            QPushButton {{
                background-color: {bg_hex};
                border: 2px solid {bo_hex};
                border-radius: 8px;
                font-family: monospace;
                font-size: 14px;
                font-weight: bold;
                color: {text_color};
                padding: 10px 15px;
            }}
            QPushButton:hover {{ background-color: {window_btn_hover}; }}
        """
        
        if hasattr(self, 'bottom_new_game_btn'):
            self.bottom_new_game_btn.setStyleSheet(window_btn_style)
        if hasattr(self, 'snap_action_btn'):
            self.snap_action_btn.setStyleSheet(window_btn_style)
        if hasattr(self, 'snap_origin_btn'):
            self.snap_origin_btn.setStyleSheet(window_btn_style)
            
        if hasattr(self, 'reset_settings_btn'):
            self.reset_settings_btn.setStyleSheet(window_btn_style)
            self.resume_btn.setStyleSheet(window_btn_style)
            self.export_btn.setStyleSheet(window_btn_style)
            self.import_btn.setStyleSheet(window_btn_style)
            self.quit_btn.setStyleSheet(window_btn_style)
            
        if hasattr(self, 'reset_btn'):
            self.reset_btn.setStyleSheet(window_btn_style)
        if hasattr(self, 'spectate_btn'):
            self.spectate_btn.setStyleSheet(window_btn_style)

    def setup_escape_menu(self):
        self.esc_menu = QFrame(self)
        self.esc_menu.setStyleSheet("background-color: rgba(0, 0, 0, 180); border: none;")
        self.esc_menu.hide()

        self.esc_layout = QVBoxLayout(self.esc_menu)
        self.esc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.menu_content = QWidget()
        self.menu_content.setStyleSheet("background: transparent; border: none;")
        self.menu_content.setFixedWidth(430) 
        content_layout = QVBoxLayout(self.menu_content)
        content_layout.setSpacing(10)
        
        title = QLabel("Config")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: white; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        content_layout.addWidget(title)
        content_layout.addSpacing(10)

        def add_subtitle(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #aaaaaa; border: none; margin-top: 15px; margin-bottom: 5px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            content_layout.addWidget(lbl)

        def add_config_row(label_text, widget):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: white; font-size: 16px; font-weight: bold; border: none;")
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(widget)
            content_layout.addLayout(row)

        cb_style = "QCheckBox::indicator { width: 22px; height: 22px; }"
        dropdown_style = """
            QComboBox { 
                color: white; 
                border: 2px solid white; 
                padding: 5px; 
                font-size: 14px; 
                border-radius: 3px; 
                background: transparent;
                min-width: 140px;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(0, 0, 0, 200);
                color: white;
                selection-background-color: rgba(255, 255, 255, 50);
            }
        """

        # --- GAMEPLAY SETTINGS ---
        add_subtitle("Gameplay")

        self.cb_next_turn = QCheckBox()
        self.cb_next_turn.setChecked(True)
        self.cb_next_turn.setStyleSheet(cb_style)
        self.cb_next_turn.toggled.connect(self.toggle_next_turn)
        add_config_row("Show Next Turn:", self.cb_next_turn)
        
        self.cb_checks = QCheckBox()
        self.cb_checks.setChecked(True)
        self.cb_checks.setStyleSheet(cb_style)
        self.cb_checks.toggled.connect(self.toggle_checks)
        add_config_row("Show Threat Checks:", self.cb_checks)
        
        self.cb_coords = QCheckBox()
        self.cb_coords.setChecked(True)
        self.cb_coords.setStyleSheet(cb_style)
        self.cb_coords.toggled.connect(self.toggle_coords)
        add_config_row("Show Coordinates:", self.cb_coords)

        # --- TIME CONTROL SETTINGS ---
        add_subtitle("Time Control")
        
        self.tc_mode_dropdown = QComboBox()
        self.tc_mode_dropdown.addItems(["Unlimited", "Turn Based", "Move Based", "Match Based"])
        self.tc_mode_dropdown.setStyleSheet(dropdown_style)
        add_config_row("Timer Mode:", self.tc_mode_dropdown)
        
        def create_tc_input(label, default_val):
            w = QWidget()
            l = QHBoxLayout(w)
            l.setContentsMargins(0,0,0,0)
            lbl = QLabel(label)
            lbl.setStyleSheet("color: white; font-size: 16px; font-weight: bold; border: none;")
            l.addWidget(lbl)
            l.addStretch()
            inp = QLineEdit(default_val)
            inp.setFixedWidth(50)
            inp.setStyleSheet("background: #2a2a2a; color: white; border: 1px solid white; border-radius: 3px; font-size: 14px; padding: 2px;")
            l.addWidget(inp)
            return w, inp

        self.tc_turn_w, self.tc_turn_input = create_tc_input("Turn Time (5-120s):", "30")
        self.tc_move_w, self.tc_move_input = create_tc_input("Move Time (5-120s):", "15")
        
        self.tc_match_w = QWidget()
        m_lay = QHBoxLayout(self.tc_match_w)
        m_lay.setContentsMargins(0,0,0,0)
        lbl_m = QLabel("Match (Min | Inc):")
        lbl_m.setStyleSheet("color: white; font-size: 16px; font-weight: bold; border: none;")
        m_lay.addWidget(lbl_m)
        m_lay.addStretch()
        self.tc_match_main_input = QLineEdit("10")
        self.tc_match_main_input.setFixedWidth(40)
        self.tc_match_main_input.setStyleSheet("background: #2a2a2a; color: white; border: 1px solid white; border-radius: 3px; font-size: 14px; padding: 2px;")
        self.tc_match_inc_input = QLineEdit("5")
        self.tc_match_inc_input.setFixedWidth(40)
        self.tc_match_inc_input.setStyleSheet("background: #2a2a2a; color: white; border: 1px solid white; border-radius: 3px; font-size: 14px; padding: 2px;")
        m_lay.addWidget(self.tc_match_main_input)
        m_lay.addWidget(self.tc_match_inc_input)

        content_layout.addWidget(self.tc_turn_w)
        content_layout.addWidget(self.tc_move_w)
        content_layout.addWidget(self.tc_match_w)
        
        self.timer_pos_dropdown = QComboBox()
        self.timer_pos_dropdown.addItems(["Top Middle", "Bottom Middle", "Bottom Left", "Top Right", "Bottom Right", "Top Left"])
        self.timer_pos_dropdown.setStyleSheet(dropdown_style)
        add_config_row("Timer Position:", self.timer_pos_dropdown)
        
        self.tc_mode_dropdown.currentTextChanged.connect(self.on_tc_mode_change)
        self.timer_pos_dropdown.currentTextChanged.connect(self.on_timer_pos_change)
        self.on_tc_mode_change("Unlimited")

        # --- COLOR SETTINGS ---
        add_subtitle("Color")

        color_options = ["Red", "Blue", "Green", "Yellow", "Purple", "Orange", "Black", "Custom"]
        
        # P1 Setup
        self.p1_dropdown = QComboBox()
        self.p1_dropdown.addItems(color_options)
        self.p1_dropdown.setCurrentText("Red")
        self.p1_dropdown.setStyleSheet(dropdown_style)
        
        p1_container = QWidget()
        p1_lay = QHBoxLayout(p1_container)
        p1_lay.setContentsMargins(0,0,0,0)
        p1_lay.addWidget(self.p1_dropdown)
        self.p1_hex_input = QLineEdit()
        self.p1_hex_input.setFixedWidth(80)
        self.p1_hex_input.setStyleSheet("background: #2a2a2a; color: white; border: 1px solid white; border-radius: 3px; font-size: 14px; padding: 2px;")
        self.p1_hex_input.setText(self.scene.color_map["Red"]["base"])
        p1_lay.addWidget(self.p1_hex_input)
        
        self.p1_dropdown.currentTextChanged.connect(self.change_p1_color)
        self.p1_hex_input.textChanged.connect(self.change_p1_hex_input)
        add_config_row("P1 (X) Color:", p1_container)

        # P2 Setup
        self.p2_dropdown = QComboBox()
        self.p2_dropdown.addItems(color_options)
        self.p2_dropdown.setCurrentText("Blue")
        self.p2_dropdown.setStyleSheet(dropdown_style)

        p2_container = QWidget()
        p2_lay = QHBoxLayout(p2_container)
        p2_lay.setContentsMargins(0,0,0,0)
        p2_lay.addWidget(self.p2_dropdown)
        self.p2_hex_input = QLineEdit()
        self.p2_hex_input.setFixedWidth(80)
        self.p2_hex_input.setStyleSheet("background: #2a2a2a; color: white; border: 1px solid white; border-radius: 3px; font-size: 14px; padding: 2px;")
        self.p2_hex_input.setText(self.scene.color_map["Blue"]["base"])
        p2_lay.addWidget(self.p2_hex_input)

        self.p2_dropdown.currentTextChanged.connect(self.change_p2_color)
        self.p2_hex_input.textChanged.connect(self.change_p2_hex_input)
        add_config_row("P2 (O) Color:", p2_container)

        # Background Setup
        self.bg_dropdown = QComboBox()
        self.bg_dropdown.addItems(["White", "Dark", "Paper", "Navy", "Custom"])
        self.bg_dropdown.setCurrentText("White")
        self.bg_dropdown.setStyleSheet(dropdown_style)

        bg_container = QWidget()
        bg_lay = QHBoxLayout(bg_container)
        bg_lay.setContentsMargins(0,0,0,0)
        bg_lay.addWidget(self.bg_dropdown)
        self.bg_hex_input = QLineEdit()
        self.bg_hex_input.setFixedWidth(80)
        self.bg_hex_input.setStyleSheet("background: #2a2a2a; color: white; border: 1px solid white; border-radius: 3px; font-size: 14px; padding: 2px;")
        self.bg_hex_input.setText(self.scene.bg_colors["White"])
        bg_lay.addWidget(self.bg_hex_input)
        
        self.bg_dropdown.currentTextChanged.connect(self.change_bg_color)
        self.bg_hex_input.textChanged.connect(self.change_bg_hex_input)
        add_config_row("Background:", bg_container)

        # Borders Setup
        self.border_dropdown = QComboBox()
        self.border_dropdown.addItems(["Black", "White", "Gray", "None", "Custom"])
        self.border_dropdown.setCurrentText("Black")
        self.border_dropdown.setStyleSheet(dropdown_style)
        
        bo_container = QWidget()
        bo_lay = QHBoxLayout(bo_container)
        bo_lay.setContentsMargins(0,0,0,0)
        bo_lay.addWidget(self.border_dropdown)
        self.border_hex_input = QLineEdit()
        self.border_hex_input.setFixedWidth(80)
        self.border_hex_input.setStyleSheet("background: #2a2a2a; color: white; border: 1px solid white; border-radius: 3px; font-size: 14px; padding: 2px;")
        self.border_hex_input.setText(self.scene.border_colors["Black"])
        bo_lay.addWidget(self.border_hex_input)

        self.border_dropdown.currentTextChanged.connect(self.change_border_color)
        self.border_hex_input.textChanged.connect(self.change_border_hex_input)
        add_config_row("Borders:", bo_container)

        # Last Move Color Setup (Moved to Color Section)
        self.last_move_color_dropdown = QComboBox()
        self.last_move_color_dropdown.addItems(["Yellow", "White", "Cyan", "Custom"])
        self.last_move_color_dropdown.setCurrentText("Yellow")
        self.last_move_color_dropdown.setStyleSheet(dropdown_style)

        lmc_container = QWidget()
        lmc_lay = QHBoxLayout(lmc_container)
        lmc_lay.setContentsMargins(0,0,0,0)
        lmc_lay.addWidget(self.last_move_color_dropdown)
        self.last_move_hex_input = QLineEdit()
        self.last_move_hex_input.setFixedWidth(80)
        self.last_move_hex_input.setStyleSheet("background: #2a2a2a; color: white; border: 1px solid white; border-radius: 3px; font-size: 14px; padding: 2px;")
        self.last_move_hex_input.setText(self.scene.last_move_colors["Yellow"])
        lmc_lay.addWidget(self.last_move_hex_input)

        self.last_move_color_dropdown.currentTextChanged.connect(self.change_last_move_color)
        self.last_move_hex_input.textChanged.connect(self.change_last_move_hex_input)
        add_config_row("Last Move Color:", lmc_container)

        # --- VISUALS SETTINGS ---
        add_subtitle("Visuals")

        self.board_style_dropdown = QComboBox()
        self.board_style_dropdown.addItems(["Flush", "Separated", "Circle"])
        self.board_style_dropdown.setCurrentText("Flush")
        self.board_style_dropdown.setStyleSheet(dropdown_style)
        self.board_style_dropdown.currentTextChanged.connect(self.change_board_style)
        add_config_row("Board Style:", self.board_style_dropdown)

        self.mode_dropdown = QComboBox()
        self.mode_dropdown.addItems(["Tic-Tac-Toe", "Color Fill"])
        self.mode_dropdown.setStyleSheet(dropdown_style)
        self.mode_dropdown.currentTextChanged.connect(self.change_render_mode)
        add_config_row("Piece Mode:", self.mode_dropdown)
        
        self.anim_dropdown = QComboBox()
        self.anim_dropdown.addItems(["None", "Zoom In", "Fade In", "Pop", "Drop In"])
        self.anim_dropdown.setCurrentText("None")
        self.anim_dropdown.setStyleSheet(dropdown_style)
        self.anim_dropdown.currentTextChanged.connect(self.change_animation)
        add_config_row("Placement Animation:", self.anim_dropdown)
        
        self.last_move_dropdown = QComboBox()
        self.last_move_dropdown.addItems(["Transparent", "Border"])
        self.last_move_dropdown.setCurrentText("Transparent")
        self.last_move_dropdown.setStyleSheet(dropdown_style)
        self.last_move_dropdown.currentTextChanged.connect(self.change_last_move_style)
        add_config_row("Last Move Style:", self.last_move_dropdown)

        self.win_border_dropdown = QComboBox()
        self.win_border_dropdown.addItems([
            "Yellow Pieces + Border", 
            "Yellow Pieces Only", 
            "Highlight Each", 
            "None"
        ])
        self.win_border_dropdown.setCurrentText("Yellow Pieces + Border")
        self.win_border_dropdown.setStyleSheet(dropdown_style)
        self.win_border_dropdown.currentTextChanged.connect(self.change_win_border)
        add_config_row("Win Border Style:", self.win_border_dropdown)

        content_layout.addSpacing(20)

        self.reset_settings_btn = QPushButton("Reset Settings")
        self.reset_settings_btn.clicked.connect(self.show_settings_confirm)
        
        self.resume_btn = QPushButton("Resume")
        self.resume_btn.clicked.connect(self.toggle_esc_menu)
        
        self.export_btn = QPushButton("Export Config")
        self.export_btn.clicked.connect(self.export_config)

        self.import_btn = QPushButton("Import Config")
        self.import_btn.clicked.connect(self.import_config)

        self.quit_btn = QPushButton("Quit Game")
        self.quit_btn.clicked.connect(self.show_quit_confirm)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.reset_settings_btn)
        btn_layout.addWidget(self.resume_btn)
        content_layout.addLayout(btn_layout)
        
        io_layout = QHBoxLayout()
        io_layout.addWidget(self.export_btn)
        io_layout.addWidget(self.import_btn)
        content_layout.addLayout(io_layout)
        
        content_layout.addSpacing(10)
        content_layout.addWidget(self.quit_btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.menu_content)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 10px; background: rgba(0,0,0,100); border-radius: 5px; margin: 0px 0px 0px 0px; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,150); border-radius: 5px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)

        self.esc_layout.addWidget(self.scroll_area, 0, Qt.AlignmentFlag.AlignCenter)

    def on_tc_mode_change(self, text):
        self.tc_turn_w.setVisible(text == "Turn Based")
        self.tc_move_w.setVisible(text == "Move Based")
        self.tc_match_w.setVisible(text == "Match Based")
        self.update_esc_menu_size()

    def on_timer_pos_change(self, text):
        self.update_timer_display()
        self.position_timer()
        self.update_hud_visibility()

    def apply_time_settings(self):
        try: turn_v = max(5, min(120, int(self.tc_turn_input.text())))
        except: turn_v = 30
        try: move_v = max(5, min(120, int(self.tc_move_input.text())))
        except: move_v = 15
        try: match_m = max(1, min(60, int(self.tc_match_main_input.text())))
        except: match_m = 10
        try: match_i = max(0, min(60, int(self.tc_match_inc_input.text())))
        except: match_i = 5
        
        mode = self.tc_mode_dropdown.currentText()
        self.scene.tc_mode_config = mode
        self.scene.tc_turn_sec = turn_v
        self.scene.tc_move_sec = move_v
        self.scene.tc_match_m_config = match_m
        self.scene.tc_match_i_config = match_i
        
        if mode in ["Turn Based", "Move Based"]:
            if self.scene.active_tc_mode != mode:
                self.scene.active_tc_mode = mode
                self.scene.active_time_left = turn_v if mode == "Turn Based" else move_v
            if not self.scene.game_over and self.scene.board:
                self.scene.game_clock.start(1000)
        elif mode == "Unlimited":
            self.scene.active_tc_mode = "Unlimited"
            self.scene.game_clock.stop()
        
        self.update_timer_display()

    def update_esc_menu_size(self):
        if hasattr(self, 'scroll_area') and hasattr(self, 'menu_content'):
            content_h = self.menu_content.sizeHint().height()
            available_h = self.height() - 80 
            target_h = min(content_h, max(available_h, 200))
            self.scroll_area.setFixedSize(465, target_h) 

    def change_p1_color(self, text):
        scene_name = "Custom P1" if text == "Custom" else text
        self.scene.p1_color_name = scene_name
        
        if hasattr(self, 'p1_hex_input'):
            self.p1_hex_input.blockSignals(True)
            self.p1_hex_input.setText(self.scene.color_map[scene_name]["base"])
            self.p1_hex_input.blockSignals(False)
            
        self.scene.update_threats() 
        self.scene.invalidate()
        self.viewport().update()
        self.update_turn_display()
        self.update_timer_display()

    def change_p1_hex_input(self, text):
        matched_preset = None
        for name, data in self.scene.color_map.items():
            if not name.startswith("Custom") and data["base"].lower() == text.lower():
                matched_preset = name
                break

        self.p1_dropdown.blockSignals(True)
        if matched_preset:
            self.p1_dropdown.setCurrentText(matched_preset)
            self.scene.p1_color_name = matched_preset
        else:
            self.p1_dropdown.setCurrentText("Custom")
            self.scene.p1_color_name = "Custom P1"
            self.scene.color_map["Custom P1"]["base"] = text
        self.p1_dropdown.blockSignals(False)

        self.scene.update_threats() 
        self.scene.invalidate()
        self.viewport().update()
        self.update_turn_display()
        self.update_timer_display()

    def change_p2_color(self, text):
        scene_name = "Custom P2" if text == "Custom" else text
        self.scene.p2_color_name = scene_name
        
        if hasattr(self, 'p2_hex_input'):
            self.p2_hex_input.blockSignals(True)
            self.p2_hex_input.setText(self.scene.color_map[scene_name]["base"])
            self.p2_hex_input.blockSignals(False)
            
        self.scene.update_threats() 
        self.scene.invalidate()
        self.viewport().update()
        self.update_turn_display()
        self.update_timer_display()

    def change_p2_hex_input(self, text):
        matched_preset = None
        for name, data in self.scene.color_map.items():
            if not name.startswith("Custom") and data["base"].lower() == text.lower():
                matched_preset = name
                break

        self.p2_dropdown.blockSignals(True)
        if matched_preset:
            self.p2_dropdown.setCurrentText(matched_preset)
            self.scene.p2_color_name = matched_preset
        else:
            self.p2_dropdown.setCurrentText("Custom")
            self.scene.p2_color_name = "Custom P2"
            self.scene.color_map["Custom P2"]["base"] = text
        self.p2_dropdown.blockSignals(False)

        self.scene.update_threats() 
        self.scene.invalidate()
        self.viewport().update()
        self.update_turn_display()
        self.update_timer_display()

    def change_bg_color(self, text):
        self.scene.bg_color_name = text
        if hasattr(self, 'bg_hex_input'):
            self.bg_hex_input.blockSignals(True)
            self.bg_hex_input.setText(self.scene.bg_colors.get(text, "#ffffff"))
            self.bg_hex_input.blockSignals(False)
            
        self.scene.invalidate()
        self.viewport().update()
        self.update_ui_theme()

    def change_bg_hex_input(self, text):
        matched_preset = None
        for name, hex_code in self.scene.bg_colors.items():
            if name != "Custom" and hex_code.lower() == text.lower():
                matched_preset = name
                break

        self.bg_dropdown.blockSignals(True)
        if matched_preset:
            self.bg_dropdown.setCurrentText(matched_preset)
            self.scene.bg_color_name = matched_preset
        else:
            self.bg_dropdown.setCurrentText("Custom")
            self.scene.bg_color_name = "Custom"
            self.scene.bg_colors["Custom"] = text
        self.bg_dropdown.blockSignals(False)

        self.scene.invalidate()
        self.viewport().update()
        self.update_ui_theme()

    def change_border_color(self, text):
        self.scene.border_color_name = text
        if hasattr(self, 'border_hex_input'):
            self.border_hex_input.blockSignals(True)
            val = self.scene.border_colors.get(text, "#000000")
            self.border_hex_input.setText(val)
            self.border_hex_input.blockSignals(False)
            
        self.scene.invalidate()
        self.viewport().update()
        self.update_ui_theme()

    def change_border_hex_input(self, text):
        matched_preset = None
        for name, hex_code in self.scene.border_colors.items():
            if name != "Custom" and hex_code.lower() == text.lower() and name != "None":
                matched_preset = name
                break
                
        if text.lower() == "none":
            matched_preset = "None"

        self.border_dropdown.blockSignals(True)
        if matched_preset:
            self.border_dropdown.setCurrentText(matched_preset)
            self.scene.border_color_name = matched_preset
        else:
            self.border_dropdown.setCurrentText("Custom")
            self.scene.border_color_name = "Custom"
            self.scene.border_colors["Custom"] = text
        self.border_dropdown.blockSignals(False)

        self.scene.invalidate()
        self.viewport().update()
        self.update_ui_theme()

    def change_board_style(self, text):
        self.scene.board_style = text
        self.scene.invalidate()
        self.viewport().update()

    def change_render_mode(self, text):
        self.scene.render_mode = text
        if text == "Color Fill":
            item = self.last_move_dropdown.model().item(0)
            if item: item.setEnabled(False)
            if self.last_move_dropdown.currentText() == "Transparent":
                self.last_move_dropdown.setCurrentText("Border")
        else:
            item = self.last_move_dropdown.model().item(0)
            if item: item.setEnabled(True)

        self.scene.invalidate()
        self.viewport().update()
        self.update_turn_display()
        
    def change_animation(self, text):
        self.scene.placement_animation_type = text

    def change_last_move_style(self, text):
        self.scene.last_move_style = text
        self.scene.invalidate()
        self.viewport().update()

    def change_last_move_color(self, text):
        self.scene.last_move_color_name = text
        if hasattr(self, 'last_move_hex_input'):
            self.last_move_hex_input.blockSignals(True)
            self.last_move_hex_input.setText(self.scene.last_move_colors.get(text, "#ffffff"))
            self.last_move_hex_input.blockSignals(False)
            
        self.scene.invalidate()
        self.viewport().update()

    def change_last_move_hex_input(self, text):
        matched_preset = None
        for name, hex_code in self.scene.last_move_colors.items():
            if name != "Custom" and hex_code.lower() == text.lower():
                matched_preset = name
                break

        self.last_move_color_dropdown.blockSignals(True)
        if matched_preset:
            self.last_move_color_dropdown.setCurrentText(matched_preset)
            self.scene.last_move_color_name = matched_preset
        else:
            self.last_move_color_dropdown.setCurrentText("Custom")
            self.scene.last_move_color_name = "Custom"
            self.scene.last_move_colors["Custom"] = text
        self.last_move_color_dropdown.blockSignals(False)

        self.scene.invalidate()
        self.viewport().update()
        
    def change_win_border(self, text):
        self.scene.win_border_type = text
        self.scene.invalidate()
        self.viewport().update()

    def toggle_coords(self, checked):
        self.center_coord_label.setVisible(checked)
        self.mouse_coord_label.setVisible(checked)
        self.update_hud_visibility()

    def toggle_next_turn(self, checked):
        self.turn_container.setVisible(checked)
        self.update_hud_visibility()

    def update_hud_visibility(self):
        if not hasattr(self, 'hud_panel'): return
        
        show_timer = (self.scene.active_tc_mode != "Unlimited" and self.timer_pos_dropdown.currentText() == "Top Left")
        if not self.cb_coords.isChecked() and not self.cb_next_turn.isChecked() and not show_timer:
            self.hud_panel.hide()
        else:
            self.hud_panel.show()

    def toggle_checks(self, checked):
        self.scene.show_highlights = checked
        self.scene.invalidate() 
        self.viewport().update()

    def toggle_esc_menu(self):
        if self.esc_menu.isVisible():
            self.apply_time_settings()
            self.esc_menu.hide()
            self.scene.is_paused = False
        else:
            self.keys_pressed.clear()
            self.esc_menu.resize(self.size())
            self.update_esc_menu_size()
            self.esc_menu.show()
            self.esc_menu.raise_()
            self.scene.is_paused = True

    def show_settings_confirm(self):
        self.settings_confirm_overlay.show()
        self.settings_confirm_overlay.raise_()

    def confirm_reset_settings(self):
        self.cb_coords.setChecked(True)
        self.cb_next_turn.setChecked(True)
        self.cb_checks.setChecked(True)
        
        self.p1_dropdown.setCurrentText("Red")
        self.p2_dropdown.setCurrentText("Blue")
        self.bg_dropdown.setCurrentText("White")
        self.border_dropdown.setCurrentText("Black")
        self.board_style_dropdown.setCurrentText("Flush")
        self.mode_dropdown.setCurrentText("Tic-Tac-Toe")
        self.anim_dropdown.setCurrentText("None")
        self.last_move_dropdown.setCurrentText("Transparent")
        self.last_move_color_dropdown.setCurrentText("Yellow")
        self.win_border_dropdown.setCurrentText("Yellow Pieces + Border")
        
        self.tc_mode_dropdown.setCurrentText("Unlimited")
        self.tc_turn_input.setText("30")
        self.tc_move_input.setText("15")
        self.tc_match_main_input.setText("10")
        self.tc_match_inc_input.setText("5")
        self.timer_pos_dropdown.setCurrentText("Top Middle")

        self.update_ui_theme()
        self.settings_confirm_overlay.hide()
        self.viewport().update()

    def export_config(self):
        config = {
            "c": self.cb_coords.isChecked(),
            "n": self.cb_next_turn.isChecked(),
            "ch": self.cb_checks.isChecked(),
            "p1": self.p1_dropdown.currentText(),
            "p1_hex": self.scene.color_map["Custom P1"]["base"],
            "p2": self.p2_dropdown.currentText(),
            "p2_hex": self.scene.color_map["Custom P2"]["base"],
            "bg": self.bg_dropdown.currentText(),
            "bg_hex": self.scene.bg_colors.get("Custom", "#ffffff"),
            "bo": self.border_dropdown.currentText(),
            "bo_hex": self.scene.border_colors.get("Custom", "#000000"),
            "bs": self.board_style_dropdown.currentText(),
            "m": self.mode_dropdown.currentText(),
            "a": self.anim_dropdown.currentText(),
            "lms": self.last_move_dropdown.currentText(),
            "lmc": self.last_move_color_dropdown.currentText(),
            "lmc_hex": self.scene.last_move_colors.get("Custom", "#ffee58"),
            "wb": self.win_border_dropdown.currentText(),
            "tc_m": self.tc_mode_dropdown.currentText(),
            "tc_t": self.tc_turn_input.text(),
            "tc_v": self.tc_move_input.text(),
            "tc_mm": self.tc_match_main_input.text(),
            "tc_mi": self.tc_match_inc_input.text(),
            "tp": self.timer_pos_dropdown.currentText()
        }
        json_str = json.dumps(config)
        code = base64.b64encode(json_str.encode('utf-8')).decode('utf-8')
        
        self.export_text.setText(code)
        self.export_overlay.show()
        self.export_overlay.raise_()

    def copy_export_code(self):
        QApplication.clipboard().setText(self.export_text.toPlainText())
        self.export_overlay.hide()

    def import_config(self):
        self.import_input.clear()
        self.import_error_label.setText("")
        self.import_overlay.show()
        self.import_overlay.raise_()

    def process_import(self):
        code = self.import_input.text().strip()
        if not code:
            return
            
        try:
            json_str = base64.b64decode(code.encode('utf-8')).decode('utf-8')
            config = json.loads(json_str)
            
            self.cb_coords.setChecked(config.get("c", True))
            self.cb_next_turn.setChecked(config.get("n", True))
            self.cb_checks.setChecked(config.get("ch", True))
            
            if "p1_hex" in config: self.scene.color_map["Custom P1"]["base"] = config["p1_hex"]
            if "p1" in config: self.p1_dropdown.setCurrentText(config["p1"])
            
            if "p2_hex" in config: self.scene.color_map["Custom P2"]["base"] = config["p2_hex"]
            if "p2" in config: self.p2_dropdown.setCurrentText(config["p2"])
            
            if "bg_hex" in config: self.scene.bg_colors["Custom"] = config["bg_hex"]
            if "bg" in config: self.bg_dropdown.setCurrentText(config["bg"])
            
            if "bo_hex" in config: self.scene.border_colors["Custom"] = config["bo_hex"]
            if "bo" in config: self.border_dropdown.setCurrentText(config["bo"])
            
            if "bs" in config: self.board_style_dropdown.setCurrentText(config["bs"])
            if "m" in config: self.mode_dropdown.setCurrentText(config["m"])
            if "a" in config: self.anim_dropdown.setCurrentText(config["a"])
            
            if "lms" in config:
                lms_val = config["lms"]
                if lms_val not in ["Transparent", "Border"]:
                    lms_val = "Border"
                if self.mode_dropdown.currentText() == "Color Fill" and lms_val == "Transparent":
                    lms_val = "Border"
                self.last_move_dropdown.setCurrentText(lms_val)
                
            if "lmc_hex" in config: self.scene.last_move_colors["Custom"] = config["lmc_hex"]
            if "lmc" in config: self.last_move_color_dropdown.setCurrentText(config["lmc"])
            
            if "wb" in config: 
                wb_val = config["wb"]
                valid_wb = ["Yellow Pieces + Border", "Yellow Pieces Only", "Highlight Each", "None"]
                if wb_val not in valid_wb:
                    wb_val = "Yellow Pieces + Border"
                self.win_border_dropdown.setCurrentText(wb_val)
                
            if "tc_m" in config: self.tc_mode_dropdown.setCurrentText(config["tc_m"])
            if "tc_t" in config: self.tc_turn_input.setText(config["tc_t"])
            if "tc_v" in config: self.tc_move_input.setText(config["tc_v"])
            if "tc_mm" in config: self.tc_match_main_input.setText(config["tc_mm"])
            if "tc_mi" in config: self.tc_match_inc_input.setText(config["tc_mi"])
            if "tp" in config: self.timer_pos_dropdown.setCurrentText(config["tp"])
            
            self.update_ui_theme()
            self.import_overlay.hide()
        except Exception:
            self.import_error_label.setText("Invalid config code.")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.toggle_esc_menu()
        elif event.key() == Qt.Key.Key_R:
            self.confirm_overlay.show()
            self.confirm_overlay.raise_()
        elif event.matches(QKeySequence.StandardKey.Undo):
            self.scene.undo_move()
        else:
            pan_zoom_keys = (
                Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down, 
                Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D,
                Qt.Key.Key_Equal, Qt.Key.Key_Plus, Qt.Key.Key_Minus
            )
            
            if event.key() in pan_zoom_keys:
                if hasattr(self, 'esc_menu') and self.esc_menu.isVisible():
                    super().keyPressEvent(event)
                    return
                self.keys_pressed.add(event.key())
                event.accept()
            else:
                super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in self.keys_pressed:
            self.keys_pressed.remove(event.key())
            
        pan_zoom_keys = (
            Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down, 
            Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D,
            Qt.Key.Key_Equal, Qt.Key.Key_Plus, Qt.Key.Key_Minus
        )
            
        if event.key() in pan_zoom_keys:
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def smooth_pan(self):
        if not self.keys_pressed or (hasattr(self, 'esc_menu') and self.esc_menu.isVisible()): 
            return

        dx = dy = 0
        
        if Qt.Key.Key_Left in self.keys_pressed: dx -= self.pan_speed
        if Qt.Key.Key_A in self.keys_pressed:    dx -= self.pan_speed
        if Qt.Key.Key_Right in self.keys_pressed: dx += self.pan_speed
        if Qt.Key.Key_D in self.keys_pressed:    dx += self.pan_speed
        
        if Qt.Key.Key_Up in self.keys_pressed:   dy -= self.pan_speed
        if Qt.Key.Key_W in self.keys_pressed:    dy -= self.pan_speed
        if Qt.Key.Key_Down in self.keys_pressed: dy += self.pan_speed
        if Qt.Key.Key_S in self.keys_pressed:    dy += self.pan_speed

        if dx != 0 or dy != 0:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + dx)
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + dy)
            self.update_center_coords()

        zoom_in = Qt.Key.Key_Equal in self.keys_pressed or Qt.Key.Key_Plus in self.keys_pressed
        zoom_out = Qt.Key.Key_Minus in self.keys_pressed
        
        if zoom_in and not zoom_out:
            zoom_factor = 1.015
        elif zoom_out and not zoom_in:
            zoom_factor = 1.0 / 1.015
        else:
            zoom_factor = 1.0
            
        if zoom_factor != 1.0:
            new_zoom = self.current_zoom * zoom_factor
            if 0.2 < new_zoom < 5.0:
                self.scale(zoom_factor, zoom_factor)
                self.current_zoom = new_zoom
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
            
            super().mouseMoveEvent(event)

    def setup_snap_buttons(self):
        self.snap_container = QWidget(self)
        layout = QVBoxLayout(self.snap_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        self.snap_action_btn = QPushButton("Snap to Action")
        self.snap_action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.snap_action_btn.clicked.connect(self.snap_to_action)
        
        self.snap_origin_btn = QPushButton("Snap to Origin")
        self.snap_origin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.snap_origin_btn.clicked.connect(self.snap_to_origin)
        
        layout.addWidget(self.snap_action_btn)
        layout.addWidget(self.snap_origin_btn)
        
        self.snap_container.hide()

    def check_snap_visibility(self):
        if not hasattr(self, 'snap_container'): return
        
        if not self.scene.board:
            if self.snap_container.isVisible():
                self.snap_container.hide()
                self.snap_action_btn.setText("Snap to Action")
                self._current_cluster_idx = 0
                if hasattr(self, 'position_timer'):
                    self.position_timer()
            return

        visible_rect = self.mapToScene(self.viewport().rect()).boundingRect()
        s = self.scene.hex_size
        w = math.sqrt(3) * s
        h = 2 * s

        clusters = self.get_action_clusters()
        visible_clusters = 0
        
        for cluster in clusters:
            cluster_visible = False
            for (q, r) in cluster:
                raw_q = q + self.scene.origin_offset[0]
                raw_r = r + self.scene.origin_offset[1]
                row = raw_r
                col = raw_q + (row // 2)
                
                x = col * w
                y = row * h * 0.75
                if row % 2 != 0:
                    x += w / 2
                    
                piece_rect = QRectF(x - w/2, y - s, w, 2*s)
                if visible_rect.intersects(piece_rect):
                    cluster_visible = True
                    break
            if cluster_visible:
                visible_clusters += 1
        
        # Show the snap container if NO clusters are visible, OR if there are multiple clusters and not all of them are visible
        should_show = (visible_clusters == 0) or (len(clusters) > 1 and visible_clusters < len(clusters))
        
        if not should_show:
            if self.snap_container.isVisible():
                self.snap_container.hide()
                self.snap_action_btn.setText("Snap to Action")
                self._current_cluster_idx = 0
                if hasattr(self, 'position_timer'):
                    self.position_timer()
        else:
            if len(clusters) > 1 and visible_clusters > 0:
                self.snap_action_btn.setText(f"Next Area ({self._current_cluster_idx % len(clusters) + 1}/{len(clusters)})")
            elif len(clusters) <= 1:
                self.snap_action_btn.setText("Snap to Action")

            if not self.snap_container.isVisible():
                self.snap_container.show()
                self.snap_container.raise_()
                self.snap_container.adjustSize()
                self.snap_container.move(self.width() - self.snap_container.width() - 20, self.height() - self.snap_container.height() - 20)
                if hasattr(self, 'position_timer'):
                    self.position_timer()

    def snap_to_action(self):
        if not self.scene.board:
            self.snap_to_origin()
            return

        clusters = self.get_action_clusters()
        
        if len(clusters) > 1:
            target_cluster = clusters[self._current_cluster_idx % len(clusters)]
            self._current_cluster_idx += 1
        else:
            target_cluster = self.scene.board.keys()
            self._current_cluster_idx = 0

        s = self.scene.hex_size
        w = math.sqrt(3) * s
        h = 2 * s

        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')

        for (q, r) in target_cluster:
            raw_q = q + self.scene.origin_offset[0]
            raw_r = r + self.scene.origin_offset[1]
            row = raw_r
            col = raw_q + (row // 2)
            
            x = col * w
            y = row * h * 0.75
            if row % 2 != 0:
                x += w / 2
            
            min_x = min(min_x, x - w)
            max_x = max(max_x, x + w)
            min_y = min(min_y, y - h)
            max_y = max(max_y, y + h)

        board_rect = QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
        padding = w * 1.5
        board_rect.adjust(-padding, -padding, padding, padding)
        center = board_rect.center()

        view_w = self.viewport().width()
        view_h = self.viewport().height()
        
        if board_rect.width() > 0 and board_rect.height() > 0:
            zoom_x = view_w / board_rect.width()
            zoom_y = view_h / board_rect.height()
            target_zoom = min(zoom_x, zoom_y)
            target_zoom = max(0.2, min(target_zoom, 1.2)) 
        else:
            target_zoom = 1.0

        if target_zoom != self.current_zoom:
            self.scale(target_zoom / self.current_zoom, target_zoom / self.current_zoom)
            self.current_zoom = target_zoom
            
        self.centerOn(center)
        self.update_center_coords()
        self.check_snap_visibility()

    def snap_to_origin(self):
        if self.current_zoom != 1.0:
            self.scale(1.0 / self.current_zoom, 1.0 / self.current_zoom)
            self.current_zoom = 1.0
        self.centerOn(0, 0)
        self.update_center_coords()
        self.check_snap_visibility()

    def setup_hud(self):
        self.hud_panel = QFrame(self)
        layout = QVBoxLayout(self.hud_panel)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        self.hud_timer_label = QLabel("00:00")
        layout.insertWidget(0, self.hud_timer_label)
        self.hud_timer_label.hide()
        
        self.center_coord_label = QLabel("Center: (0, 0)")
        self.mouse_coord_label = QLabel("Mouse:  (-, -)")
        
        self.turn_container = QWidget()
        turn_layout = QHBoxLayout(self.turn_container)
        turn_layout.setContentsMargins(0, 5, 0, 0) 
        
        self.turn_icon_label = QLabel()
        self.turn_text_label = QLabel("0 placements left")
        
        turn_layout.addWidget(self.turn_icon_label)
        turn_layout.addWidget(self.turn_text_label)
        turn_layout.addStretch() 
        
        layout.addWidget(self.center_coord_label)
        layout.addWidget(self.mouse_coord_label)
        layout.addWidget(self.turn_container)
        
        self.hud_panel.move(20, 20)
        self.hud_panel.show()
        
        self.standalone_timer_panel = QFrame(self)
        t_lay = QVBoxLayout(self.standalone_timer_panel)
        t_lay.setContentsMargins(15, 10, 15, 10)
        self.standalone_timer_label = QLabel("00:00")
        t_lay.addWidget(self.standalone_timer_label)
        self.standalone_timer_panel.hide()
        
        self.scene.on_time_tick = self.update_timer_display

    def format_time(self, seconds):
        m = seconds // 60
        s = seconds % 60
        return f"{m:02d}:{s:02d}"

    def update_timer_display(self):
        if not hasattr(self, 'standalone_timer_panel'): return
        
        mode = self.scene.active_tc_mode
        if mode == "Unlimited":
            self.standalone_timer_panel.hide()
            self.hud_timer_label.hide()
            self.update_hud_visibility()
            return
            
        text = ""
        if mode == "Match Based":
            p1_color = self.scene.p1_color_name
            p2_color = self.scene.p2_color_name
            text = f"{p1_color}: {self.format_time(self.scene.p1_time)}  |  {p2_color}: {self.format_time(self.scene.p2_time)}"
        else:
            text = f"Time: {self.format_time(self.scene.active_time_left)}"
            
        pos = self.timer_pos_dropdown.currentText()
        if pos == "Top Left":
            self.standalone_timer_panel.hide()
            self.hud_timer_label.setText(text)
            self.hud_timer_label.show()
            self.update_hud_visibility()
        else:
            self.hud_timer_label.hide()
            self.standalone_timer_label.setText(text)
            self.standalone_timer_panel.show()
            self.standalone_timer_panel.adjustSize()
            self.position_timer()
            self.update_hud_visibility()

    def position_timer(self):
        if not hasattr(self, 'standalone_timer_panel') or not self.standalone_timer_panel.isVisible(): 
            return
        
        pos = self.timer_pos_dropdown.currentText()
        w = self.standalone_timer_panel.width()
        h = self.standalone_timer_panel.height()
        
        if pos == "Top Middle":
            x = (self.width() - w) // 2
            y = 20
        elif pos == "Bottom Middle":
            x = (self.width() - w) // 2
            y = self.height() - h - 20
        elif pos == "Bottom Left":
            x = 20
            y = self.height() - h - 20
        elif pos == "Top Right":
            x = self.width() - w - 20
            y = 20
        elif pos == "Bottom Right":
            x = self.width() - w - 20
            y = self.height() - h - 20
            if hasattr(self, 'snap_container') and self.snap_container.isVisible():
                y -= (self.snap_container.height() + 10)
        else:
            return 
            
        self.standalone_timer_panel.move(x, y)

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
        
        p1_base = self.scene.color_map[self.scene.p1_color_name]["base"]
        p2_base = self.scene.color_map[self.scene.p2_color_name]["base"]
        
        if self.scene.render_mode == "Color Fill":
            color = QColor(p1_base) if player == 'X' else QColor(p2_base)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor("#000000"), 1.5))
            
            s = 9
            w = math.sqrt(3) * s
            x, y = 10, 10
            
            points = [
                QPointF(x, y - s), QPointF(x + w/2, y - s/2), QPointF(x + w/2, y + s/2),
                QPointF(x, y + s), QPointF(x - w/2, y + s/2), QPointF(x - w/2, y - s/2),
            ]
            painter.drawPolygon(QPolygonF(points))
        else:
            if player == 'X':
                pen = QPen(QColor(p1_base), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
                painter.drawLine(3, 3, 17, 17)
                painter.drawLine(3, 17, 17, 3)
            else:
                pen = QPen(QColor(p2_base), 3, Qt.PenStyle.SolidLine)
                painter.setPen(pen)
                painter.drawEllipse(3, 3, 14, 14)
            
        painter.end()
        self.turn_icon_label.setPixmap(pixmap)

    def update_center_coords(self):
        if not hasattr(self, 'hud_panel'): return
            
        center_pixel = self.viewport().rect().center()
        scene_pos = self.mapToScene(center_pixel)
        raw_q, raw_r = self.scene.pixel_to_axial(scene_pos.x(), scene_pos.y())
        
        q = raw_q - self.scene.origin_offset[0]
        r = raw_r - self.scene.origin_offset[1]
        
        self.center_coord_label.setText(f"Center: ({q + r}, {-r})")
        self.check_snap_visibility()

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        self.update_center_coords()

    def setup_ui_overlay(self):
        self.overlay = QFrame(self)
        layout = QVBoxLayout(self.overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        self.win_label = QLabel("Winner!")
        self.win_label.setStyleSheet("font-size: 24px; font-weight: bold; border: none; background: transparent;")
        self.win_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_container = QHBoxLayout()
        self.reset_btn = QPushButton("New Game")
        self.reset_btn.clicked.connect(self.reset_game)

        self.spectate_btn = QPushButton("Spectate")
        self.spectate_btn.clicked.connect(self.spectate_game)
        
        btn_container.addWidget(self.reset_btn)
        btn_container.addWidget(self.spectate_btn)

        layout.addWidget(self.win_label)
        layout.addLayout(btn_container)
        
        self.overlay.resize(320, 150)
        self.overlay.hide()

        self.bottom_new_game_btn = QPushButton("New Game", self)
        self.bottom_new_game_btn.clicked.connect(self.reset_game)
        self.bottom_new_game_btn.hide()

    def setup_confirm_overlay(self):
        self.confirm_overlay = QFrame(self)
        layout = QVBoxLayout(self.confirm_overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Reset Board?")
        title.setStyleSheet("font-size: 20px; font-weight: bold; border: none; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_container = QHBoxLayout()
        yes_btn = QPushButton("Yes")
        yes_btn.clicked.connect(self.reset_game)

        no_btn = QPushButton("No")
        no_btn.clicked.connect(self.confirm_overlay.hide)
        
        btn_container.addWidget(yes_btn)
        btn_container.addWidget(no_btn)

        layout.addWidget(title)
        layout.addLayout(btn_container)
        
        self.confirm_overlay.resize(250, 130)
        self.confirm_overlay.hide()

    def setup_settings_confirm_overlay(self):
        self.settings_confirm_overlay = QFrame(self)
        layout = QVBoxLayout(self.settings_confirm_overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Reset Settings?")
        title.setStyleSheet("font-size: 20px; font-weight: bold; border: none; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_container = QHBoxLayout()
        yes_btn = QPushButton("Yes")
        yes_btn.clicked.connect(self.confirm_reset_settings)

        no_btn = QPushButton("No")
        no_btn.clicked.connect(self.settings_confirm_overlay.hide)
        
        btn_container.addWidget(yes_btn)
        btn_container.addWidget(no_btn)

        layout.addWidget(title)
        layout.addLayout(btn_container)
        
        self.settings_confirm_overlay.resize(250, 130)
        self.settings_confirm_overlay.hide()

    def setup_quit_confirm_overlay(self):
        self.quit_confirm_overlay = QFrame(self)
        layout = QVBoxLayout(self.quit_confirm_overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Quit Game?")
        title.setStyleSheet("font-size: 20px; font-weight: bold; border: none; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_container = QHBoxLayout()
        yes_btn = QPushButton("Yes")
        yes_btn.clicked.connect(QApplication.instance().quit)

        no_btn = QPushButton("No")
        no_btn.clicked.connect(self.quit_confirm_overlay.hide)
        
        btn_container.addWidget(yes_btn)
        btn_container.addWidget(no_btn)

        layout.addWidget(title)
        layout.addLayout(btn_container)
        
        self.quit_confirm_overlay.resize(250, 130)
        self.quit_confirm_overlay.hide()

    def show_quit_confirm(self):
        self.quit_confirm_overlay.show()
        self.quit_confirm_overlay.raise_()

    def setup_export_overlay(self):
        self.export_overlay = QFrame(self)
        layout = QVBoxLayout(self.export_overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Export Config")
        title.setStyleSheet("font-size: 20px; font-weight: bold; border: none; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.export_text = QTextEdit()
        self.export_text.setReadOnly(True)
        self.export_text.setFixedHeight(120)
        
        btn_container = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(self.copy_export_code)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.export_overlay.hide)
        
        btn_container.addWidget(copy_btn)
        btn_container.addWidget(close_btn)

        layout.addWidget(title)
        layout.addWidget(self.export_text)
        layout.addLayout(btn_container)
        
        self.export_overlay.resize(380, 260)
        self.export_overlay.hide()

    def setup_import_overlay(self):
        self.import_overlay = QFrame(self)
        layout = QVBoxLayout(self.import_overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Import Config")
        title.setStyleSheet("font-size: 20px; font-weight: bold; border: none; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.import_input = QLineEdit()
        self.import_input.setPlaceholderText("Paste config code here...")
        self.import_input.setFixedHeight(40)
        
        self.import_error_label = QLabel("")
        self.import_error_label.setStyleSheet("color: red; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        self.import_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_container = QHBoxLayout()
        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self.process_import)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.import_overlay.hide)
        
        btn_container.addWidget(import_btn)
        btn_container.addWidget(cancel_btn)

        layout.addWidget(title)
        layout.addWidget(self.import_input)
        layout.addWidget(self.import_error_label)
        layout.addLayout(btn_container)
        
        self.import_overlay.resize(380, 260)
        self.import_overlay.hide()

    def show_win_screen(self, winner_text, on_time=False):
        color_name = winner_text.split(" ")[0]
        color_hex = self.scene.color_map.get(color_name, {"base": "#000000"})["base"]
        
        if on_time:
            self.win_label.setText(f'<span style="color: {color_hex};">{winner_text}</span> wins on time!')
        else:
            self.win_label.setText(f'<span style="color: {color_hex};">{winner_text}</span> wins!')
            
        self.overlay.show()
        self.overlay.raise_()

    def spectate_game(self):
        self.overlay.hide()
        self.bottom_new_game_btn.show()
        self.update_bottom_button_pos()

    def update_bottom_button_pos(self):
        if self.bottom_new_game_btn.isVisible():
            btn_w = 150
            btn_h = 45
            self.bottom_new_game_btn.setFixedSize(btn_w, btn_h)
            self.bottom_new_game_btn.move((self.width() - btn_w) // 2, self.height() - btn_h - 20)

    def reset_game(self):
        self.scene.reset_state()
        self.overlay.hide()
        self.confirm_overlay.hide()
        self.bottom_new_game_btn.hide()
        self._current_cluster_idx = 0
        
        self.resetTransform()
        self.current_zoom = 1.0
        self.centerOn(0, 0)
        self.update_center_coords()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'overlay'):
            ox = (self.width() - self.overlay.width()) // 2
            oy = (self.height() - self.overlay.height()) // 2
            self.overlay.move(ox, oy)
        
        if hasattr(self, 'confirm_overlay'):
            cx = (self.width() - self.confirm_overlay.width()) // 2
            cy = (self.height() - self.confirm_overlay.height()) // 2
            self.confirm_overlay.move(cx, cy)
            
        if hasattr(self, 'settings_confirm_overlay'):
            sx = (self.width() - self.settings_confirm_overlay.width()) // 2
            sy = (self.height() - self.settings_confirm_overlay.height()) // 2
            self.settings_confirm_overlay.move(sx, sy)
            
        if hasattr(self, 'quit_confirm_overlay'):
            qx = (self.width() - self.quit_confirm_overlay.width()) // 2
            qy = (self.height() - self.quit_confirm_overlay.height()) // 2
            self.quit_confirm_overlay.move(qx, qy)
            
        if hasattr(self, 'export_overlay'):
            ex = (self.width() - self.export_overlay.width()) // 2
            ey = (self.height() - self.export_overlay.height()) // 2
            self.export_overlay.move(ex, ey)
            
        if hasattr(self, 'import_overlay'):
            ix = (self.width() - self.import_overlay.width()) // 2
            iy = (self.height() - self.import_overlay.height()) // 2
            self.import_overlay.move(ix, iy)
        
        self.update_bottom_button_pos()
        
        if hasattr(self, 'snap_container') and self.snap_container.isVisible():
            self.snap_container.move(self.width() - self.snap_container.width() - 20, self.height() - self.snap_container.height() - 20)
            
        if hasattr(self, 'position_timer'):
            self.position_timer()
            
        if hasattr(self, 'esc_menu') and self.esc_menu.isVisible():
            self.esc_menu.resize(self.size())
            self.update_esc_menu_size()
            
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
