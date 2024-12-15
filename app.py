from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit
import random
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app)

# Game state
players = {}
game_started = False
initial_board = None

def generate_board():
    """Generate a random solvable 15 puzzle board"""
    numbers = list(range(16))  # 0-15, where 0 represents the empty space
    random.shuffle(numbers)
    return numbers

def count_correct_tiles(board):
    """Count number of tiles in their correct position"""
    return sum(1 for i, num in enumerate(board) if num == i)

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join')
def on_join(data):
    """Handle new player joining"""
    global initial_board
    player_name = data['name']
    if not game_started:
        if not initial_board:
            initial_board = generate_board()
        players[player_name] = {
            'ready': False,
            'board': initial_board.copy(),
            'correct_tiles': count_correct_tiles(initial_board)
        }
        emit('update_players', get_sorted_players(), broadcast=True)

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
            emit('game_start', {'board': initial_board}, broadcast=True)
        
        emit('update_players', get_sorted_players(), broadcast=True)

@socketio.on('move')
def on_move(data):
    """Handle player moves"""
    player_name = data['name']
    new_board = data['board']
    if player_name in players:
        players[player_name]['board'] = new_board
        players[player_name]['correct_tiles'] = count_correct_tiles(new_board)
        emit('update_players', get_sorted_players(), broadcast=True)

def get_sorted_players():
    """Get players sorted by correct tiles"""
    sorted_players = [
        {'name': name, 'correct_tiles': data['correct_tiles'], 'ready': data['ready']}
        for name, data in players.items()
    ]
    return sorted(sorted_players, key=lambda x: x['correct_tiles'], reverse=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)
