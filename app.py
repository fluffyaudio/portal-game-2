import os
from flask import Flask, render_template, request, session
from dotenv import load_dotenv

load_dotenv()
from flask_socketio import SocketIO, emit
import random
import json
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='eventlet',
    logger=True,
    engineio_logger=True,
    ping_timeout=20,
    ping_interval=25,
    max_http_buffer_size=1e8,
    manage_session=False
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
        
    def add_player(self, player_name):
        if not self.initial_board:
            self.initial_board = generate_board()
        self.players[player_name] = {
            'ready': False,
            'board': self.initial_board.copy(),
            'correct_tiles': count_correct_tiles(self.initial_board)
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
    return sum(1 for i, num in enumerate(board) if num != 0 and num == i + 1)

@app.route('/')
@app.route('/<game_id>')
def index(game_id=None):
    return render_template('index.html', game_id=game_id)

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
        room.add_player(player_name)
        socketio.server.enter_room(request.sid, game_id)
        emit('update_players', room.get_sorted_players(), room=game_id)
    else:
        emit('error', {'message': 'Game already in progress'})

@socketio.on('ready')
def on_ready(data):
    """Handle player ready status"""
    player_name = data['name']
    game_id = data.get('game_id', 'default')
    
    if game_id not in game_rooms:
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
            emit('game_start', {'board': room.initial_board}, room=game_id)
        
        emit('update_players', room.get_sorted_players(), room=game_id)

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
    if not player_name in room.players or not room.game_started:
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
        
    # Update the current player's board and correct tile count
    room.players[player_name]['board'] = new_board
    correct_tiles = count_correct_tiles(new_board)
    room.players[player_name]['correct_tiles'] = correct_tiles
    
    # Broadcast the updated board and player states
    emit('board_update', {
        'board': new_board,
        'correct_tiles': correct_tiles
    }, room=game_id)
    # Broadcast to all players the updated player list with new correct tile counts
    socketio.emit('update_players', room.get_sorted_players(), room=game_id)
    
    # Check for win condition
    if correct_tiles == BOARD_SIZE - 1:  # All tiles except empty space
        emit('game_won', {'winner': player_name}, room=game_id)
        room.reset()


@socketio.on('connect')
def on_connect():
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    print(f"Client disconnected: {request.sid}")
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
        game_rooms[game_id].reset()
        emit('game_reset', room=game_id)

def timer_expired(game_id):
    """Handle game timer expiration"""
    emit('game_won', {'winner': 'Time Expired - No Winner'}, room=game_id)
    reset_game(game_id)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5001))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
