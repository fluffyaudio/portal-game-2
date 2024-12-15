from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit
import random
import json
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app)

# Game state
players = {}
game_started = False
initial_board = None
BOARD_SIZE = 16  # 4x4 board
game_timer = None
GAME_DURATION = 1800  # 30 minutes in seconds

def generate_board():
    """Generate a random solvable 15 puzzle board"""
    numbers = list(range(16))  # 0-15, where 0 represents the empty space
    random.shuffle(numbers)
    return numbers

def count_correct_tiles(board):
    """Count number of tiles in their correct position"""
    return sum(1 for i, num in enumerate(board) if (num == i + 1) or (i == 15 and num == 0))

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    """Handle new player joining"""
    global initial_board
    player_name = data['name'].strip()
    
    # Validate player name
    if not player_name or player_name in players:
        emit('error', {'message': 'Invalid or duplicate player name'})
        return
        
    if not game_started:
        if not initial_board:
            initial_board = generate_board()
        players[player_name] = {
            'ready': False,
            'board': initial_board.copy(),
            'correct_tiles': count_correct_tiles(initial_board)
        }
        emit('update_players', get_sorted_players(), broadcast=True)
    else:
        emit('error', {'message': 'Game already in progress'})

@socketio.on('ready')
def on_ready(data):
    """Handle player ready status"""
    global game_started
    player_name = data['name']
    if player_name in players:
        players[player_name]['ready'] = True
        
        # Check if all players are ready
        if all(player['ready'] for player in players.values()):
            game_started = True
            global game_timer
            if game_timer:
                game_timer.cancel()
            game_timer = threading.Timer(GAME_DURATION, timer_expired)
            game_timer.start()
            emit('game_start', {'board': initial_board}, broadcast=True)
        
        emit('update_players', get_sorted_players(), broadcast=True)

@socketio.on('move')
def on_move(data):
    """Handle player moves"""
    player_name = data['name']
    new_board = data['board']
    
    # Validate the move
    if not player_name in players or not game_started:
        return
        
    # Validate board state
    if not isinstance(new_board, list) or len(new_board) != BOARD_SIZE:
        return
        
    if not all(isinstance(x, int) and 0 <= x < BOARD_SIZE for x in new_board):
        return
        
    # Verify only one tile moved
    old_board = players[player_name]['board']
    differences = sum(1 for i in range(BOARD_SIZE) if old_board[i] != new_board[i])
    if differences != 2:  # Only 2 positions should change in a valid move
        return
        
    players[player_name]['board'] = new_board
    players[player_name]['correct_tiles'] = count_correct_tiles(new_board)
    
    # Check for win condition
    if count_correct_tiles(new_board) == BOARD_SIZE:
        emit('game_won', {'winner': player_name}, broadcast=True)
        reset_game()
    else:
        emit('update_players', get_sorted_players(), broadcast=True)

def get_sorted_players():
    """Get players sorted by correct tiles"""
    sorted_players = [
        {'name': name, 'correct_tiles': data['correct_tiles'], 'ready': data['ready']}
        for name, data in players.items()
    ]
    return sorted(sorted_players, key=lambda x: x['correct_tiles'], reverse=True)

@socketio.on('disconnect')
def on_disconnect():
    """Handle player disconnection"""
    for player_name, player_data in list(players.items()):
        if request.sid == player_data.get('sid', None):
            del players[player_name]
            emit('update_players', get_sorted_players(), broadcast=True)
            break

def reset_game():
    """Reset the game state"""
    global game_started, initial_board, game_timer
    game_started = False
    initial_board = None
    players.clear()  # Clear all players instead of just resetting their state
    if game_timer:
        game_timer.cancel()
        game_timer = None
    emit('game_reset', broadcast=True)

def timer_expired():
    """Handle game timer expiration"""
    emit('game_won', {'winner': 'Time Expired - No Winner'}, broadcast=True)
    reset_game()

if __name__ == '__main__':
    socketio.run(app, debug=True)
