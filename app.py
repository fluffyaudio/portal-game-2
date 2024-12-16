# Monkey patch for eventlet must come before any other imports
import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, render_template, request, session
from dotenv import load_dotenv
from flask_socketio import SocketIO, emit
import random
import json
import threading
import time

load_dotenv()

# Check if we're running on render.com
IS_RENDER = os.environ.get('RENDER', False)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    logger=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1e6,
    manage_session=True,
    engineio_logger=True,
    always_connect=True,
    cookie=None
)

# Game state
game_rooms = {}  # Dictionary to store multiple game instances
BOARD_SIZE = 16  # 4x4 board
GAME_DURATION = 1800  # 30 minutes in seconds

class GameRoom:
    def __init__(self, room_id):
        self.room_id = room_id
        self.players = {}
        self.game_started = False
        self.initial_board = None
        self.game_timer = None
        
    def add_player(self, player_name, sid):
        if not self.initial_board:
            self.initial_board = generate_board()
        self.players[player_name] = {
            'ready': False,
            'board': self.initial_board.copy(),
            'correct_tiles': count_correct_tiles(self.initial_board),
            'sid': sid
        }
        
    def get_sorted_players(self):
        sorted_players = [
            {'name': name, 'correct_tiles': data['correct_tiles'], 'ready': data['ready']}
            for name, data in self.players.items()
        ]
        return sorted(sorted_players, key=lambda x: x['correct_tiles'], reverse=True)
        
    def reset(self):
        self.game_started = False
        self.initial_board = None
        self.players.clear()
        if self.game_timer:
            self.game_timer.cancel()
            self.game_timer = None

def generate_board():
    """Generate a random solvable 15 puzzle board"""
    numbers = list(range(16))  # 0-15, where 0 represents the empty space
    random.shuffle(numbers)
    return numbers

def count_correct_tiles(board):
    """Count number of tiles in their correct position"""
    correct = 0
    print("\n[DEBUG] Counting correct tiles")
    for i, num in enumerate(board):
        if num != 0 and num == i + 1:
            correct += 1
            print(f"[DEBUG] Position {i}: Tile {num} is correct")
        else:
            print(f"[DEBUG] Position {i}: Tile {num} is incorrect (should be {i+1})")
    print(f"[DEBUG] Total correct tiles found: {correct}")
    return correct

@app.route('/')
@app.route('/<game_id>')
def index(game_id=None):
    return render_template('index.html', game_id=game_id, is_render=IS_RENDER)

@socketio.on('join')
def on_join(data):
    """Handle new player joining"""
    player_name = data['name'].strip()
    game_id = data.get('game_id', 'default')
    
    # Validate player name
    if not player_name:
        emit('error', {'message': 'Invalid player name'})
        return
        
    # Create game room if it doesn't exist
    if game_id not in game_rooms:
        game_rooms[game_id] = GameRoom(game_id)
    
    room = game_rooms[game_id]
    
    if player_name in room.players:
        emit('error', {'message': 'Duplicate player name'})
        return
        
    if not room.game_started:
        room.add_player(player_name, request.sid)
        socketio.server.enter_room(request.sid, game_id)
        socketio.emit('update_players', room.get_sorted_players(), room=game_id)
    else:
        emit('error', {'message': 'Game already in progress'})

@socketio.on('ready')
def on_ready(data):
    """Handle player ready status"""
    player_name = data['name']
    game_id = data.get('game_id', 'default')
    
    print(f"[DEBUG] Ready event received from {player_name} in room {game_id}")
    
    if game_id not in game_rooms:
        print(f"[ERROR] Game room {game_id} not found")
        emit('error', {'message': 'Game room not found'})
        return
        
    room = game_rooms[game_id]
    if player_name in room.players:
        room.players[player_name]['ready'] = True
        
        # Check if all players are ready
        if all(player['ready'] for player in room.players.values()):
            room.game_started = True
            if room.game_timer:
                room.game_timer.cancel()
            room.game_timer = threading.Timer(GAME_DURATION, lambda: timer_expired(game_id))
            room.game_timer.start()
            socketio.emit('game_start', {'board': room.initial_board}, room=game_id)
        
        socketio.emit('update_players', room.get_sorted_players(), room=game_id)

@socketio.on('move')
def on_move(data):
    """Handle player moves"""
    player_name = data['name']
    new_board = data['board']
    game_id = data.get('game_id', 'default')
    
    if game_id not in game_rooms:
        return
        
    room = game_rooms[game_id]
    
    # Validate the move
    if not player_name in room.players:
        print(f"[DEBUG] Room {game_id} - Player {player_name} not found in room")
        return
        
    if not room.game_started:
        print(f"[DEBUG] Room {game_id} - Game not started yet")
        return
        
    # Validate board state
    if not isinstance(new_board, list) or len(new_board) != BOARD_SIZE:
        return
        
    if not all(isinstance(x, int) and 0 <= x < BOARD_SIZE for x in new_board):
        return
        
    # Verify only one tile moved
    old_board = room.players[player_name]['board']
    differences = sum(1 for i in range(BOARD_SIZE) if old_board[i] != new_board[i])
    if differences != 2:  # Only 2 positions should change in a valid move
        return
        
    # Update the player's state
    old_correct = room.players[player_name]['correct_tiles']
    correct_tiles = 0
    for i, num in enumerate(new_board):
        if num != 0 and num == i + 1:
            correct_tiles += 1
    
    room.players[player_name]['board'] = new_board.copy()
    room.players[player_name]['correct_tiles'] = correct_tiles
    
    print(f"\n[DEBUG] Room {game_id} - Player {player_name}:")
    print(f"[DEBUG] Room {game_id} - Previous correct tiles: {old_correct}")
    print(f"[DEBUG] Room {game_id} - New correct tiles: {correct_tiles}")
    
    print(f"\n[DEBUG] Room {game_id} - Player {player_name} made a move:")
    print(f"[DEBUG] Room {game_id} - Board state: {new_board}")
    print(f"[DEBUG] Room {game_id} - Previous correct tiles: {old_correct}")
    print(f"[DEBUG] Room {game_id} - Calculating correct tiles...")
    print(f"[DEBUG] Room {game_id} - Checking each position:")
    total_correct = 0
    for i, num in enumerate(new_board):
        if num != 0 and num == i + 1:
            total_correct += 1
            print(f"[DEBUG] Room {game_id} - Tile {num} is in correct position {i}")
    print(f"[DEBUG] Room {game_id} - Total correct tiles found: {total_correct}")
    print(f"[DEBUG] Room {game_id} - New correct tiles count: {correct_tiles}")
    print(f"[DEBUG] Room {game_id} - Current room state: {json.dumps(room.get_sorted_players(), indent=2)}")

    # Broadcast updates to all clients in the room
    update_data = {
        'board': new_board,
        'correct_tiles': correct_tiles,
        'player': player_name,
        'game_id': game_id
    }
    
    # Update player list for everyone in the room
    player_list = room.get_sorted_players()
    
    # Send board update to everyone in the room
    socketio.emit('board_update', update_data, room=game_id)
    print(f"[DEBUG] Room {game_id} - Broadcasting player list update: {json.dumps(player_list, indent=2)}")
    socketio.emit('update_players', player_list, room=game_id)
    
    # Check for win condition - any player with all tiles correct wins
    if any(player['correct_tiles'] == BOARD_SIZE - 1 for player in room.players.values()):
        print(f"[DEBUG] Win condition met in room {game_id} by player {player_name}")
        socketio.emit('game_won', {'winner': player_name}, room=game_id)
        # Reset game after a short delay
        def delayed_reset():
            if game_id in game_rooms:
                reset_game(game_id)
        threading.Timer(2.0, delayed_reset).start()


@socketio.on('connect')
def on_connect():
    print(f"[DEBUG] Client connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    print(f"[DEBUG] Client disconnected: {request.sid}")
    """Handle player disconnection"""
    # Check all game rooms for the disconnected player
    for game_id, room in game_rooms.items():
        for player_name, player_data in list(room.players.items()):
            if request.sid == player_data.get('sid', None):
                del room.players[player_name]
                emit('update_players', room.get_sorted_players(), room=game_id)
                break

def reset_game(game_id):
    """Reset the game state"""
    if game_id in game_rooms:
        print(f"[DEBUG] Resetting game in room {game_id}")
        game_rooms[game_id].reset()
        socketio.emit('game_reset', room=game_id)
        # Clean up the room if it's empty
        if not game_rooms[game_id].players:
            del game_rooms[game_id]
            print(f"[DEBUG] Removed empty room {game_id}")

def timer_expired(game_id):
    """Handle game timer expiration"""
    emit('game_won', {'winner': 'Time Expired - No Winner'}, room=game_id)
    reset_game(game_id)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    print(f"Starting server on http://localhost:{port}")
    socketio.run(app, 
                host='0.0.0.0',
                port=port, 
                debug=True,
                allow_unsafe_werkzeug=True)
