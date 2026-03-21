import sys
import math
import json
import base64
from PyQt6.QtWidgets import (QApplication, QGraphicsView, QGraphicsScene, 
                             QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QCheckBox, QWidget, QComboBox, QLineEdit, QTextEdit,
                             QScrollArea)
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygonF, QBrush, QPixmap, QKeySequence
from PyQt6.QtCore import Qt, QPointF, QEvent, QTimer

class InfiniteHexScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hex_size = 40
        self.on_win = None
        self.on_state_change = None 
        self.hovered_hex = None
        self.show_highlights = True
        self.render_mode = "Tic-Tac-Toe" 
        self.win_border_type = "Highlight Each"
        self.last_move_style = "Transparent"
        
        self.bg_color_name = "White"
        self.border_color_name = "Black"
        
        self.bg_colors = {
            "White": "#ffffff",
            "Dark": "#121212",
            "Paper": "#f4f1ea",
            "Slate": "#263238"
        }
        
        self.border_colors = {
            "Black": "#000000",
            "White": "#ffffff",
            "Gray": "#9e9e9e",
            "None": "None"
        }
        
        self.placement_animation_type = "None"
        self.active_animations = {}
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self._step_animations)
        
        # Color mapping for players and threats
        self.color_map = {
            "Red": {"base": "#d32f2f", "threat": "#ffcdd2"},
            "Blue": {"base": "#1976d2", "threat": "#bbdefb"},
            "Green": {"base": "#388e3c", "threat": "#c8e6c9"},
            "Yellow": {"base": "#fbc02d", "threat": "#fff9c4"},
            "Purple": {"base": "#7b1fa2", "threat": "#e1bee7"},
            "Orange": {"base": "#f57c00", "threat": "#ffe0b2"},
            "Black": {"base": "#000000", "threat": "#9e9e9e"}
        }
        self.p1_color_name = "Red"
        self.p2_color_name = "Blue"
        
        self.history = [] 
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
        self.winning_hexes = set()
        self.history = []
        
        self.active_animations = {}
        if hasattr(self, 'anim_timer'):
            self.anim_timer.stop()
        
        self.invalidate()
        if hasattr(self, 'on_state_change') and self.on_state_change:
            self.on_state_change()

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
        
        self.active_animations.clear()
        self.anim_timer.stop()
        
        self.update_threats()
        self.invalidate()
        if self.on_state_change:
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
                    if self.on_win:
                        winner_color_name = self.p1_color_name if self.current_player == 'X' else self.p2_color_name
                        self.on_win(f"{winner_color_name} ({self.current_player})")
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
        bg_hex = self.bg_colors.get(self.bg_color_name, "#ffffff")
        painter.fillRect(rect, QColor(bg_hex))
        
        s = self.hex_size
        w = math.sqrt(3) * s
        h = 2 * s
        
        left, right = rect.left(), rect.right()
        top, bottom = rect.top(), rect.bottom()
        
        min_col = int(left / w) - 1
        max_col = int(right / w) + 1
        min_row = int(top / (h * 0.75)) - 1
        max_row = int(bottom / (h * 0.75)) + 1
        
        # Setup dynamic colors
        x_base = self.color_map[self.p1_color_name]["base"]
        o_base = self.color_map[self.p2_color_name]["base"]
        x_threat = self.color_map[self.p1_color_name]["threat"]
        o_threat = self.color_map[self.p2_color_name]["threat"]

        border_val = self.border_colors.get(self.border_color_name, "#000000")
        if border_val == "None":
            hex_pen = QPen(Qt.PenStyle.NoPen)
        else:
            hex_pen = QPen(QColor(border_val), 1.5)

        x_pen = QPen(QColor(x_base), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        o_pen = QPen(QColor(o_base), 4, Qt.PenStyle.SolidLine)
        
        hover_brush = QBrush(QColor(238, 238, 238, 180)) # Slightly transparent to blend with any background
        last_move_brush = QBrush(QColor(255, 249, 196, 200))     
        x_threat_brush = QBrush(QColor(x_threat))      
        o_threat_brush = QBrush(QColor(o_threat))      
        both_threat_brush = QBrush(QColor("#e1bee7"))   
        
        x_fill_brush = QBrush(QColor(x_base))
        o_fill_brush = QBrush(QColor(o_base))

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Define axial directions to neighbors (from top-right, clockwise)
        neighbor_dirs = [(1, -1), (1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1)]

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
                    
                    if self.render_mode == "Color Fill":
                        fill_brush = x_fill_brush if player == 'X' else o_fill_brush
                        painter.setBrush(fill_brush)
                        painter.setPen(hex_pen) 
                        painter.drawPolygon(QPolygonF(points))
                    else:
                        radius = s * 0.55 
                        if player == 'X':
                            painter.setPen(x_pen)
                            offset = radius * 0.707 
                            painter.drawLine(QPointF(x - offset, y - offset), QPointF(x + offset, y + offset))
                            painter.drawLine(QPointF(x - offset, y + offset), QPointF(x + offset, y - offset))
                        else:
                            painter.setPen(o_pen)
                            painter.drawEllipse(QPointF(x, y), radius, radius)
                                    
                    painter.restore()

        # Draw last move highlights (if applicable)
        if self.last_turn_moves and self.last_move_style in ["Highlight Each", "Solid Line"]:
            lm_pen = QPen(QColor("#ffee58"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
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
                    QPointF(x, y - s), QPointF(x + w/2, y - s/2), QPointF(x + w/2, y + s/2),
                    QPointF(x, y + s), QPointF(x - w/2, y + s/2), QPointF(x - w/2, y - s/2),
                ]
                
                if self.last_move_style == "Highlight Each":
                    painter.drawPolygon(QPolygonF(points))
                elif self.last_move_style == "Solid Line":
                    for i, (dq, dr) in enumerate(neighbor_dirs):
                        neighbor_q = mq + dq
                        neighbor_r = mr + dr
                        
                        if (neighbor_q, neighbor_r) not in self.last_turn_moves:
                            painter.drawLine(points[i], points[(i+1) % 6])

        # Check if this hexagon is part of the winning path and draw boundaries on top
        if self.winning_hexes and self.win_border_type != "None":
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
                    QPointF(x, y - s), QPointF(x + w/2, y - s/2), QPointF(x + w/2, y + s/2),
                    QPointF(x, y + s), QPointF(x - w/2, y + s/2), QPointF(x - w/2, y - s/2),
                ]
                
                if self.win_border_type == "Highlight Each":
                    painter.drawPolygon(QPolygonF(points))
                elif self.win_border_type == "Solid Line":
                    for i, (dq, dr) in enumerate(neighbor_dirs):
                        neighbor_q = wq + dq
                        neighbor_r = wr + dr
                        
                        if (neighbor_q, neighbor_r) not in self.winning_hexes:
                            painter.drawLine(points[i], points[(i+1) % 6])

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
        self.setup_confirm_overlay() 
        self.setup_settings_confirm_overlay() 
        self.setup_export_overlay()
        self.setup_import_overlay()
        self.setup_quit_confirm_overlay()
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
        self.menu_content.setFixedWidth(430) 
        content_layout = QVBoxLayout(self.menu_content)
        content_layout.setSpacing(10)
        
        title = QLabel("Config")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: white; border: none;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        content_layout.addWidget(title)
        content_layout.addSpacing(10)

        # Helpers for styling rows and subtitles
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

        # --- COLOR SETTINGS ---
        add_subtitle("Color")

        color_options = ["Red", "Blue", "Green", "Yellow", "Purple", "Orange", "Black"]
        
        self.p1_dropdown = QComboBox()
        self.p1_dropdown.addItems(color_options)
        self.p1_dropdown.setCurrentText("Red")
        self.p1_dropdown.setStyleSheet(dropdown_style)
        self.p1_dropdown.currentTextChanged.connect(self.change_p1_color)
        add_config_row("P1 (X) Color:", self.p1_dropdown)

        self.p2_dropdown = QComboBox()
        self.p2_dropdown.addItems(color_options)
        self.p2_dropdown.setCurrentText("Blue")
        self.p2_dropdown.setStyleSheet(dropdown_style)
        self.p2_dropdown.currentTextChanged.connect(self.change_p2_color)
        add_config_row("P2 (O) Color:", self.p2_dropdown)

        self.bg_dropdown = QComboBox()
        self.bg_dropdown.addItems(["White", "Dark", "Paper", "Slate"])
        self.bg_dropdown.setCurrentText("White")
        self.bg_dropdown.setStyleSheet(dropdown_style)
        self.bg_dropdown.currentTextChanged.connect(self.change_bg_color)
        add_config_row("Background:", self.bg_dropdown)

        self.border_dropdown = QComboBox()
        self.border_dropdown.addItems(["Black", "White", "Gray", "None"])
        self.border_dropdown.setCurrentText("Black")
        self.border_dropdown.setStyleSheet(dropdown_style)
        self.border_dropdown.currentTextChanged.connect(self.change_border_color)
        add_config_row("Borders:", self.border_dropdown)

        # --- VISUALS SETTINGS ---
        add_subtitle("Visuals")

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
        self.last_move_dropdown.addItems(["Transparent", "Highlight Each", "Solid Line", "None"])
        self.last_move_dropdown.setCurrentText("Transparent")
        self.last_move_dropdown.setStyleSheet(dropdown_style)
        self.last_move_dropdown.currentTextChanged.connect(self.change_last_move_style)
        add_config_row("Last Move Style:", self.last_move_dropdown)

        self.win_border_dropdown = QComboBox()
        self.win_border_dropdown.addItems(["Highlight Each", "Solid Line", "None"])
        self.win_border_dropdown.setCurrentText("Highlight Each")
        self.win_border_dropdown.setStyleSheet(dropdown_style)
        self.win_border_dropdown.currentTextChanged.connect(self.change_win_border)
        add_config_row("Win Border Style:", self.win_border_dropdown)

        # --- BUTTONS ---
        btn_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 220);
                border: 2px solid #000000;
                border-radius: 8px;
                font-family: monospace;
                font-size: 14px;
                font-weight: bold;
                color: #000000;
                padding: 10px 15px;
            }
            QPushButton:hover { background-color: rgba(230, 230, 230, 220); }
        """

        content_layout.addSpacing(20)

        self.reset_settings_btn = QPushButton("Reset Settings")
        self.reset_settings_btn.setStyleSheet(btn_style)
        self.reset_settings_btn.clicked.connect(self.show_settings_confirm)
        
        resume_btn = QPushButton("Resume")
        resume_btn.setStyleSheet(btn_style)
        resume_btn.clicked.connect(self.toggle_esc_menu)
        
        export_btn = QPushButton("Export Config")
        export_btn.setStyleSheet(btn_style)
        export_btn.clicked.connect(self.export_config)

        import_btn = QPushButton("Import Config")
        import_btn.setStyleSheet(btn_style)
        import_btn.clicked.connect(self.import_config)

        quit_btn = QPushButton("Quit Game")
        quit_btn.setStyleSheet(btn_style)
        quit_btn.clicked.connect(self.show_quit_confirm)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.reset_settings_btn)
        btn_layout.addWidget(resume_btn)
        content_layout.addLayout(btn_layout)
        
        io_layout = QHBoxLayout()
        io_layout.addWidget(export_btn)
        io_layout.addWidget(import_btn)
        content_layout.addLayout(io_layout)
        
        content_layout.addSpacing(10)
        content_layout.addWidget(quit_btn, 0, Qt.AlignmentFlag.AlignCenter)
        
        # Wrap menu in a scroll area so it dynamically shrinks/scrolls on small screens
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

    def update_esc_menu_size(self):
        if hasattr(self, 'scroll_area') and hasattr(self, 'menu_content'):
            content_h = self.menu_content.sizeHint().height()
            available_h = self.height() - 80 
            target_h = min(content_h, max(available_h, 200))
            self.scroll_area.setFixedSize(465, target_h) # slightly wider to fit scrollbar comfortably

    def change_p1_color(self, text):
        self.scene.p1_color_name = text
        self.scene.update_threats() 
        self.scene.invalidate()
        self.viewport().update()
        self.update_turn_display()

    def change_p2_color(self, text):
        self.scene.p2_color_name = text
        self.scene.update_threats() 
        self.scene.invalidate()
        self.viewport().update()
        self.update_turn_display()

    def change_bg_color(self, text):
        self.scene.bg_color_name = text
        self.scene.invalidate()
        self.viewport().update()

    def change_border_color(self, text):
        self.scene.border_color_name = text
        self.scene.invalidate()
        self.viewport().update()

    def change_render_mode(self, text):
        self.scene.render_mode = text
        if text == "Color Fill":
            item = self.last_move_dropdown.model().item(0)
            if item: item.setEnabled(False)
            if self.last_move_dropdown.currentText() == "Transparent":
                self.last_move_dropdown.setCurrentText("Highlight Each")
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
        if not self.cb_coords.isChecked() and not self.cb_next_turn.isChecked():
            self.hud_panel.hide()
        else:
            self.hud_panel.show()

    def toggle_checks(self, checked):
        self.scene.show_highlights = checked
        self.scene.invalidate() 
        self.viewport().update()

    def toggle_esc_menu(self):
        if self.esc_menu.isVisible():
            self.esc_menu.hide()
        else:
            self.esc_menu.resize(self.size())
            self.update_esc_menu_size()
            self.esc_menu.show()
            self.esc_menu.raise_()

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
        self.mode_dropdown.setCurrentText("Tic-Tac-Toe")
        self.anim_dropdown.setCurrentText("None")
        self.last_move_dropdown.setCurrentText("Transparent")
        self.win_border_dropdown.setCurrentText("Highlight Each")

        self.settings_confirm_overlay.hide()
        self.viewport().update()

    def export_config(self):
        config = {
            "c": self.cb_coords.isChecked(),
            "n": self.cb_next_turn.isChecked(),
            "ch": self.cb_checks.isChecked(),
            "p1": self.p1_dropdown.currentText(),
            "p2": self.p2_dropdown.currentText(),
            "bg": self.bg_dropdown.currentText(),
            "bo": self.border_dropdown.currentText(),
            "m": self.mode_dropdown.currentText(),
            "a": self.anim_dropdown.currentText(),
            "lms": self.last_move_dropdown.currentText(),
            "wb": self.win_border_dropdown.currentText()
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
            
            if "p1" in config: self.p1_dropdown.setCurrentText(config["p1"])
            if "p2" in config: self.p2_dropdown.setCurrentText(config["p2"])
            if "bg" in config: self.bg_dropdown.setCurrentText(config["bg"])
            if "bo" in config: self.border_dropdown.setCurrentText(config["bo"])
            if "m" in config: self.mode_dropdown.setCurrentText(config["m"])
            if "a" in config: self.anim_dropdown.setCurrentText(config["a"])
            
            if "lms" in config:
                lms_val = config["lms"]
                if self.mode_dropdown.currentText() == "Color Fill" and lms_val == "Transparent":
                    lms_val = "Highlight Each"
                self.last_move_dropdown.setCurrentText(lms_val)
                
            if "wb" in config: self.win_border_dropdown.setCurrentText(config["wb"])
            
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
        elif event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down, 
                             Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D):
            # Intercept arrow keys to stop native QGraphicsView scrolling
            self.keys_pressed.add(event.key())
            event.accept()
        else:
            self.keys_pressed.add(event.key())
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in self.keys_pressed:
            self.keys_pressed.remove(event.key())
            
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down, 
                           Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D):
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def smooth_pan(self):
        if not self.keys_pressed: return

        dx = dy = 0
        if Qt.Key.Key_Left in self.keys_pressed or Qt.Key.Key_A in self.keys_pressed:  dx = -self.pan_speed
        if Qt.Key.Key_Right in self.keys_pressed or Qt.Key.Key_D in self.keys_pressed: dx = self.pan_speed
        if Qt.Key.Key_Up in self.keys_pressed or Qt.Key.Key_W in self.keys_pressed:    dy = -self.pan_speed
        if Qt.Key.Key_Down in self.keys_pressed or Qt.Key.Key_S in self.keys_pressed:  dy = self.pan_speed

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
        # Using SetFixedSize forces the QFrame to continuously auto-resize based on the layout contents!
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
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
        
        btn_container = QHBoxLayout()
        btn_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 220);
                border: 2px solid #000000;
                border-radius: 8px;
                font-family: monospace;
                font-size: 14px;
                font-weight: bold;
                color: #000000;
                padding: 10px;
            }
            QPushButton:hover { background-color: rgba(230, 230, 230, 220); }
        """

        self.reset_btn = QPushButton("New Game")
        self.reset_btn.setStyleSheet(btn_style)
        self.reset_btn.clicked.connect(self.reset_game)

        self.spectate_btn = QPushButton("Spectate")
        self.spectate_btn.setStyleSheet(btn_style)
        self.spectate_btn.clicked.connect(self.spectate_game)
        
        btn_container.addWidget(self.reset_btn)
        btn_container.addWidget(self.spectate_btn)

        layout.addWidget(self.win_label)
        layout.addLayout(btn_container)
        
        self.overlay.resize(320, 150)
        self.overlay.hide()

        self.bottom_new_game_btn = QPushButton("New Game", self)
        self.bottom_new_game_btn.setStyleSheet(btn_style)
        self.bottom_new_game_btn.clicked.connect(self.reset_game)
        self.bottom_new_game_btn.hide()

    def setup_confirm_overlay(self):
        self.confirm_overlay = QFrame(self)
        self.confirm_overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 230); 
                border: 2px solid black; 
                border-radius: 10px;
            }
        """)
        
        layout = QVBoxLayout(self.confirm_overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Reset Board?")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: black; border: none; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_container = QHBoxLayout()
        btn_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 220);
                border: 2px solid #000000;
                border-radius: 8px;
                font-family: monospace;
                font-size: 14px;
                font-weight: bold;
                color: #000000;
                padding: 10px;
            }
            QPushButton:hover { background-color: rgba(230, 230, 230, 220); }
        """

        yes_btn = QPushButton("Yes")
        yes_btn.setStyleSheet(btn_style)
        yes_btn.clicked.connect(self.reset_game)

        no_btn = QPushButton("No")
        no_btn.setStyleSheet(btn_style)
        no_btn.clicked.connect(self.confirm_overlay.hide)
        
        btn_container.addWidget(yes_btn)
        btn_container.addWidget(no_btn)

        layout.addWidget(title)
        layout.addLayout(btn_container)
        
        self.confirm_overlay.resize(250, 130)
        self.confirm_overlay.hide()

    def setup_settings_confirm_overlay(self):
        self.settings_confirm_overlay = QFrame(self)
        self.settings_confirm_overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 230); 
                border: 2px solid black; 
                border-radius: 10px;
            }
        """)
        
        layout = QVBoxLayout(self.settings_confirm_overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Reset Settings?")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: black; border: none; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_container = QHBoxLayout()
        btn_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 220);
                border: 2px solid #000000;
                border-radius: 8px;
                font-family: monospace;
                font-size: 14px;
                font-weight: bold;
                color: #000000;
                padding: 10px;
            }
            QPushButton:hover { background-color: rgba(230, 230, 230, 220); }
        """

        yes_btn = QPushButton("Yes")
        yes_btn.setStyleSheet(btn_style)
        yes_btn.clicked.connect(self.confirm_reset_settings)

        no_btn = QPushButton("No")
        no_btn.setStyleSheet(btn_style)
        no_btn.clicked.connect(self.settings_confirm_overlay.hide)
        
        btn_container.addWidget(yes_btn)
        btn_container.addWidget(no_btn)

        layout.addWidget(title)
        layout.addLayout(btn_container)
        
        self.settings_confirm_overlay.resize(250, 130)
        self.settings_confirm_overlay.hide()

    def setup_quit_confirm_overlay(self):
        self.quit_confirm_overlay = QFrame(self)
        self.quit_confirm_overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 230); 
                border: 2px solid black; 
                border-radius: 10px;
            }
        """)
        
        layout = QVBoxLayout(self.quit_confirm_overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Quit Game?")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: black; border: none; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_container = QHBoxLayout()
        btn_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 220);
                border: 2px solid #000000;
                border-radius: 8px;
                font-family: monospace;
                font-size: 14px;
                font-weight: bold;
                color: #000000;
                padding: 10px;
            }
            QPushButton:hover { background-color: rgba(230, 230, 230, 220); }
        """

        yes_btn = QPushButton("Yes")
        yes_btn.setStyleSheet(btn_style)
        yes_btn.clicked.connect(QApplication.instance().quit)

        no_btn = QPushButton("No")
        no_btn.setStyleSheet(btn_style)
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
        self.export_overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 240); 
                border: 2px solid black; 
                border-radius: 10px;
            }
        """)
        
        layout = QVBoxLayout(self.export_overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Export Config")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: black; border: none; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.export_text = QTextEdit()
        self.export_text.setReadOnly(True)
        self.export_text.setStyleSheet("border: 1px solid gray; border-radius: 4px; background: white; font-family: monospace; font-size: 12px; color: black;")
        self.export_text.setFixedHeight(120)
        
        btn_container = QHBoxLayout()
        btn_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 220);
                border: 2px solid #000000;
                border-radius: 8px;
                font-family: monospace;
                font-size: 14px;
                font-weight: bold;
                color: #000000;
                padding: 10px 15px;
            }
            QPushButton:hover { background-color: rgba(230, 230, 230, 220); }
        """

        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.setStyleSheet(btn_style)
        copy_btn.clicked.connect(self.copy_export_code)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(btn_style)
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
        self.import_overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 240); 
                border: 2px solid black; 
                border-radius: 10px;
            }
        """)
        
        layout = QVBoxLayout(self.import_overlay)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title = QLabel("Import Config")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: black; border: none; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.import_input = QLineEdit()
        self.import_input.setPlaceholderText("Paste config code here...")
        self.import_input.setFixedHeight(40)
        self.import_input.setStyleSheet("border: 1px solid gray; border-radius: 4px; background: white; font-family: monospace; font-size: 14px; color: black; padding: 5px;")
        
        self.import_error_label = QLabel("")
        self.import_error_label.setStyleSheet("color: red; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        self.import_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn_container = QHBoxLayout()
        btn_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 220);
                border: 2px solid #000000;
                border-radius: 8px;
                font-family: monospace;
                font-size: 14px;
                font-weight: bold;
                color: #000000;
                padding: 10px 15px;
            }
            QPushButton:hover { background-color: rgba(230, 230, 230, 220); }
        """

        import_btn = QPushButton("Import")
        import_btn.setStyleSheet(btn_style)
        import_btn.clicked.connect(self.process_import)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(btn_style)
        cancel_btn.clicked.connect(self.import_overlay.hide)
        
        btn_container.addWidget(import_btn)
        btn_container.addWidget(cancel_btn)

        layout.addWidget(title)
        layout.addWidget(self.import_input)
        layout.addWidget(self.import_error_label)
        layout.addLayout(btn_container)
        
        self.import_overlay.resize(380, 260)
        self.import_overlay.hide()

    def show_win_screen(self, winner_text):
        color_name = winner_text.split(" ")[0]
        color_hex = self.scene.color_map.get(color_name, {"base": "#000000"})["base"]
        
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
