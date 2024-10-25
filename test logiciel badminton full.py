import sys
import sqlite3
import csv
import random
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QLineEdit,
    QVBoxLayout, QHBoxLayout, QMessageBox, QTableWidget, QTableWidgetItem,
    QComboBox, QFileDialog, QDialog, QListWidget, QListWidgetItem, QFormLayout,
    QMenu, QSpinBox, QDialogButtonBox, QAbstractItemView, 
    QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QDialog,
    QScrollArea, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, 
    QDialog, QToolTip, QFrame, QSpacerItem, QSizePolicy)

from PyQt5.QtCore import Qt, QSize, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QMovie, QFont



# Constants
DATABASE = 'badminton_app.db'

# Initialize the database
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    #cursor.execute('''DROP TABLE IF EXISTS matches''')
    #cursor.execute('''DROP TABLE IF EXISTS sessions''')
    #cursor.execute('''DROP TABLE IF EXISTS players''')

    # Create players table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            elo_rating REAL DEFAULT 1500,
            matches_played INTEGER DEFAULT 0,
            last_played DATETIME
        )
    ''')

    # Create sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            match_type TEXT,
            date TEXT
        )
    ''')
    
    # Create matches table with session_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            session_id INTEGER,
            player_a1_id INTEGER,
            player_a2_id INTEGER,
            player_b1_id INTEGER,
            player_b2_id INTEGER,
            team_a_names TEXT,
            team_b_names TEXT,
            score_a INTEGER,
            score_b INTEGER,
            winner1_id INTEGER,
            winner2_id INTEGER,
            match_type TEXT,
            field_number INTEGER,
            FOREIGN KEY(player_a1_id) REFERENCES players(id),
            FOREIGN KEY(player_a2_id) REFERENCES players(id),
            FOREIGN KEY(player_b1_id) REFERENCES players(id),
            FOREIGN KEY(player_b2_id) REFERENCES players(id),
            FOREIGN KEY(winner1_id) REFERENCES players(id),
            FOREIGN KEY(winner2_id) REFERENCES players(id),
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Elo Rating System Functions
def calculate_expected_score(rating_a1, rating_a2, rating_b1, rating_b2):
    return 1 / (1 + 10 ** (((rating_b1 + rating_b2) - (rating_a1 + rating_a2)) / 400))

def get_k_factor(matches_played):
    if matches_played < 30:
        return 40
    else:
        return 20

def update_elo(player_a1_id, player_a2_id, player_b1_id, player_b2_id, winner1_id, winner2_id, session_id, match_type, field_number):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Fetch current ratings and match counts for each player (handle None for singles matches)
    if player_a1_id:
        cursor.execute('SELECT elo_rating, matches_played FROM players WHERE id = ?', (player_a1_id,))
        result_a1 = cursor.fetchone()
        if not result_a1:
            conn.close()
            return
        rating_a1, matches_a1 = result_a1
    else:
        rating_a1, matches_a1 = 0, 0

    if player_a2_id:  # Optional for singles
        cursor.execute('SELECT elo_rating, matches_played FROM players WHERE id = ?', (player_a2_id,))
        result_a2 = cursor.fetchone()
        rating_a2, matches_a2 = result_a2
    else:
        rating_a2, matches_a2 = rating_a1, matches_a1  # Copy values for singles

    cursor.execute('SELECT elo_rating, matches_played FROM players WHERE id = ?', (player_b1_id,))
    result_b1 = cursor.fetchone()
    if not result_b1:
        conn.close()
        return
    rating_b1, matches_b1 = result_b1

    if player_b2_id:  # Optional for singles
        cursor.execute('SELECT elo_rating, matches_played FROM players WHERE id = ?', (player_b2_id,))
        result_b2 = cursor.fetchone()
        rating_b2, matches_b2 = result_b2
    else:
        rating_b2, matches_b2 = rating_b1, matches_b1  # Copy values for singles

    # Calculate expected scores (handle both singles and doubles cases)
    if match_type == 'Doubles':
        expected_a = calculate_expected_score(rating_a1, rating_a2, rating_b1, rating_b2)
    else:  # Singles
        expected_a = calculate_expected_score(rating_a1, 0, rating_b1, 0)  # Only 1 player per team
    expected_b = 1 - expected_a

    # Determine actual scores based on winners
    if winner1_id == player_a1_id and (match_type == 'Singles' or winner2_id == player_a2_id):
        score_a, score_b = 1, 0
    elif winner1_id == player_b1_id and (match_type == 'Singles' or winner2_id == player_b2_id):
        score_a, score_b = 0, 1
    else:
        score_a, score_b = 0.5, 0.5  # Handle draw if necessary

    # Determine K-factors
    k_a = get_k_factor(matches_a1 + matches_a2)
    k_b = get_k_factor(matches_b1 + matches_b2)

    # Update ratings
    new_rating_a1 = rating_a1 + k_a * (score_a - expected_a)
    new_rating_a2 = rating_a2 + k_a * (score_a - expected_a)
    new_rating_b1 = rating_b1 + k_b * (score_b - expected_b)
    new_rating_b2 = rating_b2 + k_b * (score_b - expected_b)

    # Update players' ratings, match counts, and last_played field (handle both singles and doubles)
    date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        UPDATE players 
        SET elo_rating = ?, matches_played = ?, last_played = ?
        WHERE id = ?
    ''', (new_rating_a1, matches_a1 + 1, date_str, player_a1_id))

    if match_type == 'Doubles':  # Update player_a2 only in doubles
        cursor.execute('''
            UPDATE players 
            SET elo_rating = ?, matches_played = ?, last_played = ?
            WHERE id = ?
        ''', (new_rating_a2, matches_a2 + 1, date_str, player_a2_id))

    cursor.execute('''
        UPDATE players 
        SET elo_rating = ?, matches_played = ?, last_played = ?
        WHERE id = ?
    ''', (new_rating_b1, matches_b1 + 1, date_str, player_b1_id))

    if match_type == 'Doubles':  # Update player_b2 only in doubles
        cursor.execute('''
            UPDATE players 
            SET elo_rating = ?, matches_played = ?, last_played = ?
            WHERE id = ?
        ''', (new_rating_b2, matches_b2 + 1, date_str, player_b2_id))

    # Record the match
    cursor.execute('''
        INSERT INTO matches (date, session_id, player_a1_id, player_a2_id, player_b1_id, player_b2_id, score_a, score_b, winner1_id, winner2_id, match_type, field_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), session_id, player_a1_id, player_a2_id, player_b1_id, player_b2_id,
          int(score_a), int(score_b), winner1_id if winner1_id else None, winner2_id if winner2_id else None, match_type, field_number))

    conn.commit()
    conn.close()

# Utility Functions
def get_player_id(name):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM players WHERE name = ?', (name,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_player_elo_rating(player_name):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT elo_rating FROM players WHERE name = ?
    ''', (player_name,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0  # Return 0 if no ELO found 

def remove_matches_without_winner():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Delete rows where winner1_id is NULL
    cursor.execute('DELETE FROM matches WHERE winner1_id IS NULL')
    
    conn.commit()
    conn.close()

def get_match_history():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT m.date,
                CASE
                    WHEN pa2.name IS NOT NULL THEN pa1.name || ' & ' || pa2.name
                    ELSE pa1.name
                END AS team_a_names, 
                   
                CASE
                    WHEN pb2.name IS NOT NULL THEN pb1.name || ' & ' || pb2.name
                    ELSE pb1.name
                END AS team_b_names, 
                   
                m.score_a, m.score_b,
                CASE
                    WHEN pw1.name IS NOT NULL AND pw2.name IS NOT NULL THEN pw1.name || ' & ' || pw2.name
                    WHEN pw1.name IS NOT NULL THEN pw1.name
                    WHEN pw2.name IS NOT NULL THEN pw2.name
                    ELSE 'N/A'
                END AS winner_team,
                m.match_type, m.field_number
        FROM matches m
        JOIN players pa1 ON m.player_a1_id = pa1.id
        LEFT JOIN players pa2 ON m.player_a2_id = pa2.id
        JOIN players pb1 ON m.player_b1_id = pb1.id
        LEFT JOIN players pb2 ON m.player_b2_id = pb2.id
        LEFT JOIN players pw1 ON m.winner1_id = pw1.id
        LEFT JOIN players pw2 ON m.winner2_id = pw2.id
        JOIN sessions s ON m.session_id = s.id
        ORDER BY m.date DESC
    ''')
    matches = cursor.fetchall()
    conn.close()
    return matches


def get_performance_data():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT name, elo_rating, matches_played FROM players
            order by elo_rating desc
    ''')
    players = cursor.fetchall()
    conn.close()

    # Calculate win rates
    performance_data = []
    for name, elo, matches_played in players:
        if matches_played == 0:
            win_rate = 'N/A'
        else:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM matches 
                WHERE (player_a1_id = (SELECT id FROM players WHERE name = ?) AND winner1_id = player_a1_id)
                   OR (player_a2_id = (SELECT id FROM players WHERE name = ?) AND winner2_id = player_a2_id)
                   OR (player_b1_id = (SELECT id FROM players WHERE name = ?) AND winner1_id = player_b1_id)
                   OR (player_b2_id = (SELECT id FROM players WHERE name = ?) AND winner2_id = player_b2_id)
            ''', (name, name, name, name))
            wins = cursor.fetchone()[0]
            conn.close()
            win_rate = f"{(wins / matches_played * 100) / 2 :.2f}%"
        performance_data.append((name, int(elo), matches_played, win_rate))
    return performance_data

# Custom QListWidget for Assigned Players with Drag-and-Drop and Removal
class AssignedPlayersList(QListWidget):
    def __init__(self, available_list, parent=None):
        super().__init__(parent)
        self.available_list = available_list
        self.players = []  # Initialize the list to store players with their elo_rating
        self.setAcceptDrops(True)
        self.setDragEnabled(True)  # Enable dragging from this list
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Allow multiple selection
        self.setContextMenuPolicy(Qt.CustomContextMenu)  # Enable right-click context menu
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, position):
        """Create and display the right-click context menu."""
        menu = QMenu()
        remove_action = menu.addAction("Remove Selected")
        action = menu.exec_(self.mapToGlobal(position))
        if action == remove_action:
            self.remove_selected_players()

    def remove_selected_players(self):
        """Remove selected players from the assigned list and move them back to the available list."""
        selected_items = self.selectedItems()
        for item in selected_items:
            player_name = item.text().split(" (")[0]  # Extract the player name
            
            # Remove the player from the assigned list
            self.takeItem(self.row(item))
            
            # Remove the player from the internal players list (used to populate the assigned list)
            self.players = [p for p in self.players if p[0] != player_name]

            # Check if the player already exists in the available list before adding
            if not self.is_in_list(player_name, self.available_list):
                available_item = QListWidgetItem(player_name)
                self.available_list.addItem(available_item)

    def is_in_list(self, player_name, list_widget):
        """Check if a player is already in a list to avoid duplication."""
        for i in range(list_widget.count()):
            if player_name == list_widget.item(i).text():
                return True
        return False

    def dropEvent(self, event):
        """Handle the drop event to move players between lists."""
        # Handle drop back to the available players list
        if event.source() == self:
            selected_items = self.selectedItems()
            for item in selected_items:
                player_name = item.text().split(" (")[0]  # Extract the player name
                self.takeItem(self.row(item))  # Remove from assigned list

                # Remove the player from the internal players list
                self.players = [p for p in self.players if p[0] != player_name]

                # Move the player back to the available list if not already present
                if not self.is_in_list(player_name, self.available_list):
                    available_item = QListWidgetItem(player_name)
                    self.available_list.addItem(available_item)
        else:
            super().dropEvent(event)

            # Collect the dropped players from the available list
            selected_items = self.available_list.selectedItems()
            for item in selected_items:
                player_name = item.text()

                # Get the elo_rating for the player from the database
                elo_rating = self.get_player_elo_rating(player_name)

                # Ensure the player is not already in the assigned list
                if not self.is_in_list(player_name, self):
                    # Add the player to the assigned list and the internal players list
                    self.players.append((player_name, elo_rating))

                    # Remove the player from the available list
                    self.available_list.takeItem(self.available_list.row(item))

            # Sort players by elo_rating in descending order
            self.players.sort(key=lambda x: x[1], reverse=True)

            # Clear the assigned list and re-populate it
            self.clear()
            for player_name, elo_rating in self.players:
                self.addItem(f"{player_name} ({int(elo_rating)})")

    def get_player_elo_rating(self, player_name):
        """Fetch the ELO rating of a player from the database."""
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT elo_rating FROM players WHERE name = ?
        ''', (player_name,))
        elo_rating = cursor.fetchone()[0]
        conn.close()
        return elo_rating

    def dragEnterEvent(self, event):
        """Allow dragging players back from the assigned list."""
        if event.source() == self or event.source() == self.available_list:
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        """Allow drag movements for the players."""
        event.acceptProposedAction()



# Assuming you have a method to add a player to the database
def add_player_to_db(self, name, elo_rating):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO players (name, elo_rating)
            VALUES (?, ?)
        ''', (name, elo_rating))
        conn.commit()
    except sqlite3.IntegrityError:
        QMessageBox.warning(self, "Database Error", "Player with this name already exists.")
    finally:
        conn.close()

class ManagePlayersDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Manage Players')
        self.setGeometry(150, 150, 500, 500)
        self.initUI()


    def import_players_from_csv(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(self, "Open CSV File", "", "CSV Files (*.csv);;All Files (*)", options=options)
        if file_name:
            try:
                with open(file_name, newline='') as csvfile:
                    reader = csv.reader(csvfile)
                    headers = next(reader)  # Skip the header row
                    conn = sqlite3.connect(DATABASE)
                    cursor = conn.cursor()
                    for row in reader:
                        player_id = int(row[0])
                        name = row[1]
                        elo_rating = int(row[2]) if row[2] else 1500  # Default ELO rating
                        cursor.execute('''
                            INSERT OR IGNORE INTO players (id, name, elo_rating)
                            VALUES (?, ?, ?)
                        ''', (player_id, name, elo_rating))
                    conn.commit()
                    conn.close()
                    QMessageBox.information(self, 'Success', 'Players imported successfully.')
                    self.load_players()  # Refresh the UI to show the newly imported players
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'An error occurred while importing players: {str(e)}')

    def export_players_info(self):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, elo_rating FROM players')
        players_data = cursor.fetchall()
        conn.close()

        file_path, _ = QFileDialog.getSaveFileName(self, 'Save File', '', 'CSV(*.csv)')
        if file_path:
            with open(file_path, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['ID', "Name", 'Elo Rating'])
                for row in players_data:
                    writer.writerow(row)
            QMessageBox.information(self, 'Success', 'Players information exported successfully.')
    
    def initUI(self):
        layout = QVBoxLayout()

        # Players Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(['ID', 'Name', 'Elo Rating'])
        self.load_players()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()
        self.add_button = QPushButton('Add Player')
        self.add_button.clicked.connect(self.add_player)
        self.remove_button = QPushButton('Remove Selected Player(s)')
        self.remove_button.clicked.connect(self.remove_players)
        self.export_players_button = QPushButton('Export Players Info')
        self.export_players_button.clicked.connect(self.export_players_info)
        self.import_players_button = QPushButton('Import Players from CSV')
        self.import_players_button.clicked.connect(self.import_players_from_csv)
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.export_players_button)
        button_layout.addWidget(self.import_players_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)
        self.table.resizeColumnsToContents()
    
    def load_players(self):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, elo_rating FROM players')
        players = cursor.fetchall()

        self.table.setRowCount(len(players))

        for row, (id, name, elo) in enumerate(players):
            self.table.setItem(row, 0, QTableWidgetItem(str(id)))
            self.table.setItem(row, 1, QTableWidgetItem(name))
            self.table.setItem(row, 2, QTableWidgetItem(str(int(elo))))
        
        conn.close()

    def add_player_to_db(self, name, elo_rating):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO players (name, elo_rating) VALUES (?, ?)', (name, elo_rating))
        conn.commit()
        conn.close()

    def add_player(self):
        dialog = AddPlayerDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            name, elo_rating = dialog.get_player_data()
            self.add_player_to_db(name, elo_rating)
            self.load_players()  # Reload players after adding
            self.refresh_available_players()

    def remove_players(self):
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        if not selected_rows:
            QMessageBox.warning(self, 'Selection Error', 'Please select at least one player to remove.')
            return
        confirm = QMessageBox.question(
            self, 'Confirm Removal',
            f'Are you sure you want to remove {len(selected_rows)} player(s)?',
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm == QMessageBox.Yes:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            for row in selected_rows:
                player_id = int(self.table.item(row, 0).text())
                cursor.execute('DELETE FROM players WHERE id = ?', (player_id,))
            conn.commit()
            conn.close()
            QMessageBox.information(self, 'Success', 'Selected player(s) removed successfully.')
            self.load_players()
            self.refresh_available_players()  # Refresh available players list after removal

    def refresh_available_players(self):
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute('SELECT id, name, elo_rating FROM players')
            players = cursor.fetchall()
            conn.close()
            
            # Reference the MainWindow's `schedule_session_dialog`
            if self.parent().schedule_session_dialog:
                self.parent().schedule_session_dialog.populate_available_players()

class AddPlayerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Player")
        
        self.layout = QFormLayout()
        
        self.name_input = QLineEdit()
        self.elo_input = QLineEdit()
        
        self.layout.addRow("Name:", self.name_input)
        self.layout.addRow("ELO Rating:", self.elo_input)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        
        self.layout.addWidget(self.buttons)
        self.setLayout(self.layout)
    
    def get_player_data(self):
        name = self.name_input.text()
        elo = float(self.elo_input.text())
        return name, elo


class ImportPlayersDialog(QDialog):

    def initUI(self):
        layout = QVBoxLayout()

        self.file_label = QLabel('Select CSV File:')
        self.file_path = QLineEdit()
        self.browse_button = QPushButton('Browse')
        self.browse_button.clicked.connect(self.browse_file)

        file_layout = QHBoxLayout()
        file_layout.addWidget(self.file_path)
        file_layout.addWidget(self.browse_button)
        layout.addWidget(self.file_label)
        layout.addLayout(file_layout)

        self.import_button = QPushButton('Import Players')
        self.import_button.clicked.connect(self.import_players)
        layout.addWidget(self.import_button)

        self.setLayout(layout)
    
    def browse_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, 'Open CSV File', '', 'CSV Files (*.csv)')
        if file_name:
            self.file_path.setText(file_name)
    
    def import_players(self):
        file_path = self.file_path.text().strip()
        if not file_path:
            QMessageBox.warning(self, 'Input Error', 'Please select a CSV file.')
            return

        try:
            with open(file_path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()
                for row in reader:
                    name = row['name'].strip()
                    cursor.execute('''
                        INSERT OR IGNORE INTO players (name, elo_rating)
                        VALUES (?, ?)
                    ''', (name, elo))
                conn.commit()
                conn.close()
            QMessageBox.information(self, 'Success', 'Players imported successfully.')
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to import players.\nError: {str(e)}')
             


class ScheduleSessionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Generate Matchups')
        self.setGeometry(100, 100, 700, 700)
        self.session_id = None
        self.initUI(parent)
        self.setWindowIcon(QIcon("badminton_icon.png"))
        

    def initUI(self, parent):
        layout = QVBoxLayout()

        # Add buttons at the top
        button_layout = QHBoxLayout()
        
        self.manage_players_button = QPushButton("Manage Players")
        self.view_leaderboard_button = QPushButton("View Leaderboard")
        self.view_match_history_button = QPushButton("View Match History")
        self.tutorial_button = QPushButton('Tutorial')
        
        # Connect buttons to methods in the parent (MainWindow)
        self.manage_players_button.clicked.connect(parent.open_manage_players)
        self.view_leaderboard_button.clicked.connect(parent.open_leaderboard)
        self.view_match_history_button.clicked.connect(parent.open_match_history)
        self.tutorial_button.clicked.connect(parent.open_tutorial)
        
        button_layout.addWidget(self.manage_players_button)
        button_layout.addWidget(self.view_leaderboard_button)
        button_layout.addWidget(self.view_match_history_button)
        button_layout.addWidget(self.tutorial_button)
        
        layout.addLayout(button_layout)

        form_layout = QFormLayout()
        
        self.match_type_combo = QComboBox()
        self.match_type_combo.addItems(['Doubles', 'Singles'])
        form_layout.addRow('Match Type:', self.match_type_combo)

        # Add field number selection
        self.field_number_spin = QSpinBox()
        self.field_number_spin.setMinimum(1)
        self.field_number_spin.setMaximum(10)  # You can adjust this maximum as needed
        self.field_number_spin.setValue(4)  # Default to 4 fields
        form_layout.addRow('Number of Fields:', self.field_number_spin)

        # Initialize num_fields
        self.num_fields = self.field_number_spin.value()  # Set initial value

        # Connect the signal to update num_fields directly
        self.field_number_spin.valueChanged.connect(lambda value: setattr(self, 'num_fields', value))
        layout.addLayout(form_layout)

        # Drag and Drop Setup
        drag_drop_layout = QHBoxLayout()

        # Available Players List
        available_layout = QVBoxLayout()
        available_label = QLabel('Available Players:')
        
        # Add search bar for available players
        self.search_bar = QLineEdit(self)
        self.search_bar.setPlaceholderText("Search for players...")
        self.search_bar.textChanged.connect(self.filter_available_players)
        
        # Add search bar to the available_layout
        available_layout.addWidget(available_label)
        available_layout.addWidget(self.search_bar)  # Add search bar here
        self.available_list = QListWidget()
        self.available_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.available_list.setDragEnabled(True)
        available_layout.addWidget(self.available_list)
        drag_drop_layout.addLayout(available_layout)

        # Assigned Players List
        assigned_layout = QVBoxLayout()
        assigned_label = QLabel('Assigned Players:')
        self.assigned_list = AssignedPlayersList(self.available_list)
        assigned_layout.addWidget(assigned_label)
        assigned_layout.addWidget(self.assigned_list)
        drag_drop_layout.addLayout(assigned_layout)

        layout.addLayout(drag_drop_layout)

        # Populate Available Players
        self.populate_available_players()

        # Assuming you have a QTableWidget for scores
        self.scores_table = QTableWidget()
        self.scores_table.setColumnCount(4)
        self.scores_table.setHorizontalHeaderLabels(["Team A", "Team B", "Score A", "Score B"])

        # Example: Adding a row with editable score columns
        row_position = self.scores_table.rowCount()
        self.scores_table.insertRow(row_position)

        Team_a_item = QTableWidgetItem("Team A Name")
        Team_b_item = QTableWidgetItem("Team B Name")
        score_a_item = QTableWidgetItem("")
        score_b_item = QTableWidgetItem()

        # Make score columns editable
        score_a_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)  # Make it editable
        score_b_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled)

        self.scores_table.setItem(row_position, 0, Team_a_item)
        self.scores_table.setItem(row_position, 1, Team_b_item)
        self.scores_table.setItem(row_position, 2, score_a_item)
        self.scores_table.setItem(row_position, 3, score_b_item)

        # Submit Button
        self.submit_button = QPushButton('Create Matchup')
        self.submit_button.clicked.connect(self.create_matchup)
        layout.addWidget(self.submit_button)

        # Matchups Display (Now using QTableWidget for score input)
        self.matchups_label = QLabel('Matchups:')
        layout.addWidget(self.matchups_label)

        self.matchups_table = QTableWidget()
        self.matchups_table.setColumnCount(5)  # Field, Team A, Team B, Score A, Score B
        self.matchups_table.setHorizontalHeaderLabels(['Field Number', 'Team A', 'Team B', 'Score A', 'Score B'])
        self.matchups_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        layout.addWidget(self.matchups_table)

        # Button to Submit Scores
        self.submit_scores_button = QPushButton('Submit Scores')
        self.submit_scores_button.clicked.connect(self.submit_scores)
        self.submit_scores_button.setEnabled(True)  # Disabled until a session is scheduled
        layout.addWidget(self.submit_scores_button)

        self.setLayout(layout)

    def filter_available_players(self):
        search_text = self.search_bar.text().lower()
        for i in range(self.available_list.count()):  # Use self.available_list here
            item = self.available_list.item(i)
            item.setHidden(search_text not in item.text().lower())

    def populate_available_players(self):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Modify the query to select players and order by last_participation (DESC to get most recent first)
        cursor.execute('''
            SELECT name, last_played
            FROM players
            ORDER BY last_played DESC
        ''')
        players = cursor.fetchall()
        conn.close()

        # Get names of currently assigned players
        assigned_player_names = [self.assigned_list.item(i).text().split(" (")[0] for i in range(self.assigned_list.count())]

        self.available_list.clear()

        # Add players to the available list, but skip those who are already assigned
        for name, last_played in players:
            if name not in assigned_player_names:
                item = QListWidgetItem(name)
                self.available_list.addItem(item)
    

    def create_matchup(self):
        global date_str
        date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # Current date
        match_type = self.match_type_combo.currentText()

        remove_matches_without_winner()

        assigned_players = []
        player_elos = {}  # Dictionary to store players and their ELO ratings

        # Gather assigned players and their ELO ratings
        for index in range(self.assigned_list.count()):
            item = self.assigned_list.item(index)
            # Extract player name before any additional info (e.g., "(ELO: XXX)")
            player_name = item.text().split(" (")[0]  # Adjust based on your actual naming convention
            elo = get_player_elo_rating(player_name)
            assigned_players.append(player_name)
            player_elos[player_name] = elo

        if not assigned_players:
            QMessageBox.warning(self, 'Input Error', 'No players assigned for matchups.')
            return

        # Sort players by ELO ratings (strongest to weakest)
        sorted_players = sorted(assigned_players, key=lambda player: player_elos[player], reverse=False)

        # Determine number of tiers (2 to 4)
        num_tiers = random.randint(2, 4)
        print("Number of Tiers:", num_tiers)

        # Calculate the size of each tier
        players_per_tier = len(sorted_players) // num_tiers
        remainder = len(sorted_players) % num_tiers

        # Create tiers
        tiers = []
        start_index = 0

        for tier_index in range(num_tiers):
            # Distribute the remainder among the first 'remainder' tiers
            end_index = start_index + players_per_tier + (1 if tier_index < remainder else 0)
            tier = sorted_players[start_index:end_index]
            tiers.append(tier)
            start_index = end_index

        matches = []
        matched_players = set()  # To track players already in a match
        bench_players = []  # To track players left on the bench

        # Generate matchups starting from the weakest tier
        for tier_index in range(num_tiers):
            tier = tiers[tier_index]
            num_players = len(tier)
            print(f"Processing Tier {tier_index + 1} with {num_players} players.")

            if match_type == 'Doubles':
                # Shuffle players within the tier to randomize team assignments
                random.shuffle(tier)
                teams = []

                # Pair players into teams of two
                for i in range(0, num_players, 2):
                    if i + 1 < num_players:
                        team = (tier[i], tier[i + 1])
                        teams.append(team)
                        matched_players.update(team)
                    else:
                        # Handle odd player by leaving them for singles
                        leftover_player = tier[i]
                        # Try to pair with the next tier
                        if tier_index + 1 < num_tiers:
                            tiers[tier_index + 1].append(leftover_player)
                        else:
                            bench_players.append(leftover_player)
                        print(f"Leftover Player in Tier {tier_index + 1}: {leftover_player}")

                # Shuffle teams to randomize match pairings
                random.shuffle(teams)

                # Pair teams against each other within the same tier
                for i in range(0, len(teams), 2):
                    if i + 1 < len(teams):
                        team_a = teams[i]
                        team_b = teams[i + 1]
                        matches.append((team_a, team_b))
                    else:
                        # Handle odd number of teams by leaving the last team for singles
                        leftover_team = teams[i]
                        bench_players.extend(leftover_team)  # Add all team members to the bench
                        print(f"Leftover Team in Tier {tier_index + 1}: {leftover_team}")

            else:  # Singles
                # Shuffle players within the tier to randomize match pairings
                random.shuffle(tier)

                # Pair players directly
                for i in range(0, num_players, 2):
                    if i + 1 < num_players:
                        player_a = tier[i]
                        player_b = tier[i + 1]
                        matches.append((player_a, player_b))
                        matched_players.update([player_a, player_b])
                    else:
                        # Handle odd player by leaving them on the bench
                        leftover_player = tier[i]
                        # Try to pair with the next tier
                        if tier_index + 1 < num_tiers:
                            tiers[tier_index + 1].append(leftover_player)
                        else:
                            bench_players.append(leftover_player)
                        print(f"Leftover Player on Bench in Tier {tier_index + 1}: {leftover_player}")

        # Step 2: Try to form additional doubles using bench players
        while len(bench_players) >= 4:
            # Take the first four players to form two teams for a doubles match
            team_a = (bench_players.pop(0), bench_players.pop(0))
            team_b = (bench_players.pop(0), bench_players.pop(0))
            matches.append((team_a, team_b))

        # Step 3: Create singles matches if 3 or fewer players are left on the bench and fields are available
        max_matches = self.num_fields

        while len(bench_players) >= 2 and len(matches) < max_matches:
            player_a = bench_players.pop(0)
            player_b = bench_players.pop(0)
            matches.append((player_a, player_b))

        # Shuffle matches for random assignment to fields
        random.shuffle(matches)

        # Respect the maximum number of fields
        if len(matches) > max_matches:
            matches = matches[:max_matches]

        # Display which players are on the bench
        if bench_players:
            print(bench_players)
            bench_message = "Players on the bench:\n" + "\n".join(bench_players)
            QMessageBox.information(self, 'Bench Players', bench_message)

        # Assign matches to fields
        field_number = 1
        self.matchups_table.setRowCount(0)  # Clear any existing rows

        try:
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()

                # Insert new session
                cursor.execute('''INSERT INTO sessions (name, match_type, date) VALUES (?, ?, ?)''',
                            (f"Session on {date_str}", match_type, date_str))
                session_id = cursor.lastrowid

                for match in matches:
                    if match_type == 'Doubles':
                        # Determine if this match is Doubles or Singles based on match structure
                        if len(match) == 2 and isinstance(match[0], tuple) and isinstance(match[1], tuple):
                            # Doubles Match
                            team_a, team_b = match
                            player_a1, player_a2 = team_a
                            player_b1, player_b2 = team_b

                            player_a1_id = get_player_id(player_a1)
                            player_a2_id = get_player_id(player_a2)
                            player_b1_id = get_player_id(player_b1)
                            player_b2_id = get_player_id(player_b2)

                            cursor.execute('''INSERT INTO matches (date, session_id, player_a1_id, player_a2_id,
                            player_b1_id, player_b2_id, score_a, score_b, winner1_id, winner2_id, match_type, field_number)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                                date_str, session_id, player_a1_id, player_a2_id,
                                player_b1_id, player_b2_id, 0, 0,
                                None, None, 'Doubles', field_number
                            ))

                            # Update the matchups_table UI
                            row_position = self.matchups_table.rowCount()
                            self.matchups_table.insertRow(row_position)
                            self.matchups_table.setItem(row_position, 0, QTableWidgetItem(str(field_number)))
                            self.matchups_table.setItem(row_position, 1, QTableWidgetItem(f"({player_a1} & {player_a2})"))
                            self.matchups_table.setItem(row_position, 2, QTableWidgetItem(f"({player_b1} & {player_b2})"))
                            self.matchups_table.setItem(row_position, 3, QTableWidgetItem(""))  # Score A
                            self.matchups_table.setItem(row_position, 4, QTableWidgetItem(""))  # Score B

                        elif len(match) == 2 and isinstance(match[0], str) and isinstance(match[1], str):
                            # Singles Match within Doubles Session
                            player_a, player_b = match

                            player_a_id = get_player_id(player_a)
                            player_b_id = get_player_id(player_b)
                            player_a_name = player_a if player_a_id else "N/A"
                            player_b_name = player_b if player_b_id else "N/A"

                            cursor.execute('''INSERT INTO matches (date, session_id, player_a1_id, player_b1_id,
                            score_a, score_b, winner1_id, match_type, field_number)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                                date_str, session_id, player_a_id, player_b_id,
                                0, 0, None, 'Singles', field_number
                            ))

                            # Update the matchups_table UI
                            row_position = self.matchups_table.rowCount()
                            self.matchups_table.insertRow(row_position)
                            self.matchups_table.setItem(row_position, 0, QTableWidgetItem(str(field_number)))
                            self.matchups_table.setItem(row_position, 1, QTableWidgetItem(player_a_name))
                            self.matchups_table.setItem(row_position, 2, QTableWidgetItem(player_b_name))
                            self.matchups_table.setItem(row_position, 3, QTableWidgetItem(""))  # Score A
                            self.matchups_table.setItem(row_position, 4, QTableWidgetItem(""))  # Score B

                    else:  # Singles match
                        player_a, player_b = match

                        player_a_id = get_player_id(player_a)
                        player_b_id = get_player_id(player_b)

                        cursor.execute('''INSERT INTO matches (date, session_id, player_a1_id, player_b1_id,
                        score_a, score_b, winner1_id, match_type, field_number)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                            date_str, session_id, player_a_id, player_b_id,
                            0, 0, None, 'Singles', field_number
                        ))

                        # Update the matchups_table UI
                        row_position = self.matchups_table.rowCount()
                        self.matchups_table.insertRow(row_position)
                        self.matchups_table.setItem(row_position, 0, QTableWidgetItem(str(field_number)))
                        self.matchups_table.setItem(row_position, 1, QTableWidgetItem(player_a))
                        self.matchups_table.setItem(row_position, 2, QTableWidgetItem(player_b))
                        self.matchups_table.setItem(row_position, 3, QTableWidgetItem(""))  # Score A
                        self.matchups_table.setItem(row_position, 4, QTableWidgetItem(""))  # Score B

                    field_number += 1

                conn.commit()  # Commit all changes to the database
                self.matchups_table.resizeColumnsToContents() # Adapt size of columns to length of text

        except sqlite3.Error as e:
            print(f"Database error: {e}")
            QMessageBox.critical(self, 'Database Error', f"An error occurred while saving matchups: {e}")



    def submit_scores(self):
        row_count = self.matchups_table.rowCount()
        if row_count == 0:
            QMessageBox.warning(self, 'Error', 'No matches found to submit scores.')
            return

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        for row in range(row_count):
            field_number_item = self.matchups_table.item(row, 0)
            team_a_item = self.matchups_table.item(row, 1)
            team_b_item = self.matchups_table.item(row, 2)
            score_a_item = self.matchups_table.item(row, 3)
            score_b_item = self.matchups_table.item(row, 4)

            field_number = int(field_number_item.text()) if field_number_item.text().isdigit() else None
            team_a = team_a_item.text()
            team_b = team_b_item.text()
            score_a = score_a_item.text()
            score_b = score_b_item.text()

            # Replace 'N/A' with 0
            if score_a == 'N/A':
                score_a = 0
            if score_b == 'N/A':
                score_b = 0
            # Validate scores
            if not score_a.isdigit() or not score_b.isdigit():
                QMessageBox.warning(self, 'Input Error', f'Please enter valid scores for Field {field_number}.')
                return

            # Determine winner
            if int(score_a) > int(score_b):
                winner_team = team_a
            elif int(score_b) > int(score_a):
                winner_team = team_b
            else:
                winner_team = None  # Handle draw if necessary

            # Fetch match_id from the database based on field_number
            cursor.execute('''
                            SELECT id, player_a1_id, player_a2_id, player_b1_id, player_b2_id, match_type FROM matches
                            WHERE field_number = ? AND date = ? 
                        ''', (field_number, date_str))
            match = cursor.fetchone()
            if match:
                match_id, player_a1_id, player_a2_id, player_b1_id, player_b2_id, match_type = match

                # Update match scores and winner_id
                if winner_team == team_a:
                    winner1_id, winner2_id = player_a1_id, player_a2_id
                elif winner_team == team_b:
                    winner1_id, winner2_id = player_b1_id, player_b2_id
                else:
                    winner1_id, winner2_id = None, None  # Handle draw if necessary

                if match_type == 'Singles':
                    cursor.execute('''
                        UPDATE matches
                        SET score_a = ?, score_b = ?, winner1_id = ?, winner2_id = NULL
                        WHERE id = ?
                    ''', (score_a, score_b, winner1_id, match_id))
                else:
                    cursor.execute('''
                        UPDATE matches
                        SET score_a = ?, score_b = ?, winner1_id = ?, winner2_id = ?
                        WHERE id = ?
                    ''', (score_a, score_b, winner1_id, winner2_id, match_id))
            
        conn.commit()
        conn.close()

        # Update Elo ratings based on the submitted scores
        self.update_elo_ratings()

        QMessageBox.information(self, 'Success', 'Scores submitted and records updated successfully.')

    def update_elo_ratings(self):
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Fetch all matches in the latest session
        cursor.execute('''
            SELECT id, player_a1_id, player_a2_id, player_b1_id, player_b2_id, score_a, score_b, winner1_id, winner2_id, match_type, field_number
            FROM matches
            WHERE session_id = (
                SELECT id FROM sessions ORDER BY id DESC LIMIT 1
            )
        ''')
        matches = cursor.fetchall()

        for match in matches:
            match_id, player_a1_id, player_a2_id, player_b1_id, player_b2_id, score_a, score_b, winner1_id, winner2_id, match_type, field_number = match
            # Update Elo based on the scores
            if match_type == 'Singles':
                if score_a > score_b:
                    winner1_id = player_a1_id
                    winner2_id = None
                elif score_b > score_a:
                    winner1_id = player_b1_id
                    winner2_id = None
                else:
                    winner1_id = None
                    winner2_id = None  # Draw
                update_elo(player_a1_id, None, player_b1_id, None, winner1_id, winner2_id, session_id=None, match_type=match_type, field_number=field_number)
            else:
                # For doubles, determine winner based on team scores
                if score_a > score_b:
                    winner1_id = player_a1_id
                    winner2_id = player_a2_id
                elif score_b > score_a:
                    winner1_id = player_b1_id
                    winner2_id = player_b2_id
                else:
                    winner1_id = None
                    winner2_id = None  # Draw
                update_elo(player_a1_id, player_a2_id, player_b1_id, player_b2_id, winner1_id, winner2_id, session_id=None, match_type=match_type, field_number=field_number)

        conn.close()


class LeaderboardWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Leaderboard')
        self.setGeometry(150, 150, 480, 450) 
        self.setWindowFlags(Qt.Window)      
        self.setWindowIcon(QIcon("badminton_icon.png"))
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['Name', 'Elo Rating', 'Matchs Played', 'Win Rate'])
        self.load_leaderboard()
        layout.addWidget(self.table)

        # Add export button
        self.export_button = QPushButton('Export Leaderboard')
        self.export_button.clicked.connect(self.export_leaderboard)
        layout.addWidget(self.export_button)

        self.setLayout(layout)
        self.table.resizeColumnsToContents()
    
    def load_leaderboard(self):
        performance_data = get_performance_data()
        self.table.setRowCount(len(performance_data))
        for row_idx, (name, elo, MatchesPlayed, WinRate) in enumerate(performance_data):
            self.table.setItem(row_idx, 0, QTableWidgetItem(name))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(int(elo))))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(MatchesPlayed)))
            self.table.setItem(row_idx, 3, QTableWidgetItem(WinRate))

    def export_leaderboard(self):
        file_path, _ = QFileDialog.getSaveFileName(self, 'Save File', '', 'CSV(*.csv)')
        if file_path:
            with open(file_path, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['Name', 'Elo Rating', 'Matchs Played', 'Win Rate'])
                for row_idx in range(self.table.rowCount()):
                    row_data = []
                    for col_idx in range(self.table.columnCount()):
                        item = self.table.item(row_idx, col_idx)
                        row_data.append(item.text() if item else '')
                    writer.writerow(row_data)
            QMessageBox.information(self, 'Success', 'Leaderboard exported successfully.')


class MatchHistoryWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Match History')
        self.setGeometry(150, 150, 1000, 500)
        self.setWindowIcon(QIcon("badminton_icon.png"))
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            'Date', 'Team A', 'Team B',
            'Score A', 'Score B', 'Winner', 'Match Type', 'Field Number'
        ])
        self.load_match_history()
        layout.addWidget(self.table)

        self.setLayout(layout)
        self.table.resizeColumnsToContents()
    
    def load_match_history(self):
        matches = get_match_history()
        self.table.setRowCount(len(matches))
        for row_idx, match in enumerate(matches):
            date, teamA, teamB, ScoreA, ScoreB, Winners, MatchType, FieldNumber = match[:8]  # Adjust this line based on the actual number of values returned
            self.table.setItem(row_idx, 0, QTableWidgetItem(date))
            self.table.setItem(row_idx, 1, QTableWidgetItem(teamA))
            self.table.setItem(row_idx, 2, QTableWidgetItem(teamB))
            self.table.setItem(row_idx, 3, QTableWidgetItem(str(ScoreA)))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(ScoreB)))
            self.table.setItem(row_idx, 5, QTableWidgetItem(Winners if Winners else "N/A"))
            self.table.setItem(row_idx, 6, QTableWidgetItem(MatchType))
            self.table.setItem(row_idx, 7, QTableWidgetItem(str(FieldNumber) if FieldNumber else 'N/A'))



class TutorialWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tutorial")
        self.setGeometry(100, 100, 800, 600)  
        self.setWindowIcon(QIcon("badminton_icon.png"))
        self.initUI()
        self.setStyleSheet("""
            QPushButton {
        background-color: #4CAF50;
        color: white;
        border-radius: 5px;
        padding: 8px 16px;
        font-size: 14px;
    }
    QPushButton:hover {
        background-color: #45a049;
    }
    QLabel, QLineEdit, QComboBox {
        font-family: Arial, sans-serif;
        font-size: 14px;
        padding: 5px;
    }
    QTableWidget {
        font-family: Arial, sans-serif;
        font-size: 14px;
        padding: 5px;
    }
    QMainWindow {
        background-color: #F0F0F0;
    }
    QListWidget {
        background-color: #fff;
        border: 1px solid #ddd;
    }
        """)  # Your existing stylesheet here

    def initUI(self):
        # Create main layout
        main_layout = QVBoxLayout()
        
        # Create scroll area for the tutorial steps
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QFrame()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Define the tutorial steps with corresponding tips
        steps = [
            ("Manage Players", 
            "In the Manage Players menu, add players name and an estimation of their ELO Rating compared to the other players in your league", 
            "tutorial/add_players.gif", 
            "Tip: You can select multiple players to remove with ctrl + click",
            720, 480),

            ("Schedule Matches", 
            """1. Create matchups by drag and dropping available players into the assigned players section.\r
                                        2. Specify Singles or Doubles and the number of fields.\r
                                        3. Click 'Create Matchup' to generate games.""", 
            "tutorial/schedule_matches.gif", 
            """Tip: Remove players from the available section by right-clicking them.\r
                    Add or Remove multiple players with ctrl + click or ctrl + A \r
                    Matches are made by grouping people based on their ELO Rating and then pairing them up.
                    Elo Rating adapts overtime based on the results of the matches""",
            480, 480),

            ("Submit Scores", 
            "Enter match results and click on the 'Submit Scores' button", 
            "tutorial/submit_scores.gif", 
            "Tip: Ensure you have the correct players' scores before submitting.",
             480, 480),
        ]
        
        # Add each step to the scrollable layout
        for title, description, gif_name, tip_text, gif_width, gif_length in steps:
            step_layout = QVBoxLayout()

            # Title
            title_label = QLabel(title)
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet("font-weight: bold; font-size: 18px;")
            step_layout.addWidget(title_label)
            
            # Description
            description_label = QLabel(description)
            description_label.setWordWrap(True)
            description_label.setAlignment(Qt.AlignCenter)
            step_layout.addWidget(description_label)
            
            # GIF
            gif_label = QLabel()
            gif_label.setScaledContents(True)  # Enable scaling of the contents
            gif_label.setFixedSize(gif_width, gif_length)  # Set a fixed size for the label
            gif_label.setAlignment(Qt.AlignCenter)
            movie = QMovie(gif_name)
            gif_label.setMovie(movie)
            movie.start()
            step_layout.addWidget(gif_label, alignment=Qt.AlignCenter)



            # Tip Section for each GIF
            tip_label = QLabel(tip_text)
            tip_label.setWordWrap(True)
            tip_label.setAlignment(Qt.AlignCenter)
            tip_label.setStyleSheet("font-size: 12px; color: #666666;")  # Smaller font for the tip
            step_layout.addWidget(tip_label)

            # Add some space below each step
            step_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))
            
            # Add step layout to scroll layout
            scroll_layout.addLayout(step_layout)
        
        # Add a "Finish" button at the bottom
        finish_button = QPushButton("Finish")
        finish_button.clicked.connect(self.finish_tutorial)
        finish_button.setFixedSize(150, 40)
        
        # Add scroll content to scroll area
        scroll_area.setWidget(scroll_content)
        
        # Add everything to the main layout
        main_layout.addWidget(scroll_area)
        main_layout.addWidget(finish_button, alignment=Qt.AlignCenter)
        
        self.setLayout(main_layout)

    def finish_tutorial(self):
        self.close()




# Main Application Window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.schedule_session_dialog = None
        self.initUI()
        
        

    def initUI(self):
        self.setWindowTitle('Badminton App')
        self.setGeometry(100, 100, 800, 600)
        self.setWindowIcon(QIcon("badminton_icon.png"))
        # Apply custom styles to the window
        self.setStyleSheet("""
            QPushButton {
        background-color: #4CAF50;
        color: white;
        border-radius: 5px;
        padding: 8px 16px;
        font-size: 14px;
    }
    QPushButton:hover {
        background-color: #45a049;
    }
    QLabel, QLineEdit, QComboBox {
        font-family: Arial, sans-serif;
        font-size: 14px;
        padding: 5px;
    }
    QTableWidget {
        font-family: Arial, sans-serif;
        font-size: 14px;
        padding: 5px;
    }
    QMainWindow {
        background-color: #F0F0F0;
    }
    QListWidget {
        background-color: #fff;
        border: 1px solid #ddd;
    }
        """)

        # Call the method to open the "generate match ups" interface
        self.open_create_matchup()
        
        

    def open_manage_players(self):
        manage_players_dialog = ManagePlayersDialog(self)
        manage_players_dialog.exec_()

    def open_leaderboard(self):
        leaderboard_window = LeaderboardWindow(self)
        leaderboard_window.exec_()

    def open_match_history(self):
        match_history_window = MatchHistoryWindow(self)
        match_history_window.exec_()

    def open_create_matchup(self):
        if not self.schedule_session_dialog:
            self.schedule_session_dialog = ScheduleSessionDialog(self)  # Create and store the instance
        self.schedule_session_dialog.exec_()
    
    def open_tutorial(self):
        self.tutorial_window = TutorialWindow()
        self.tutorial_window.exec_()
  
# Main Execution
if __name__ == "__main__":
    init_db()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.close()
    sys.exit()
    