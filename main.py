
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fastlane-development-key")


# PROTECT MANAGEMENT PAGES
@app.before_request
def protect_management_pages():
    public_pages = [
        "home",
        "setup_admin",
        "admin_login",
        "statistics",
        "match_statistics",
        "standings",
        "static"
    ]

    if request.endpoint in public_pages:
        return

    if "admin_id" not in session:
        return redirect("/admin-login")


# DATABASE CONNECTION
def connect_db():
    return sqlite3.connect("fastlane.db")


# CREATE DATABASE TABLES
def create_database():
    conn = connect_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            phone TEXT,
            sport TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT NOT NULL,
            sport TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            sport TEXT NOT NULL,
            match_date TEXT NOT NULL,
            home_score INTEGER DEFAULT 0,
            away_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Scheduled'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            player_id INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            goals INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            yellow_cards INTEGER DEFAULT 0,
            red_cards INTEGER DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# FIRST ADMIN SETUP
@app.route("/setup-admin", methods=["GET", "POST"])
def setup_admin():
    conn = connect_db()

    count = conn.execute(
        "SELECT COUNT(*) FROM admins"
    ).fetchone()[0]

    if count > 0:
        conn.close()
        return "Admin setup is already complete.", 403

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username:
            conn.close()
            return "Please enter a username."

        if len(password) < 8:
            conn.close()
            return "Password must have at least 8 characters."

        try:
            password_hash = generate_password_hash(password)

            conn.execute(
                "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                (username, password_hash)
            )

            conn.commit()
            conn.close()

            return redirect("/admin-login")

        except sqlite3.IntegrityError:
            conn.close()
            return "That username already exists."

    conn.close()
    return render_template("setup_admin.html")


# ADMIN LOGIN
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = connect_db()

        admin = conn.execute(
            "SELECT id, username, password_hash FROM admins WHERE username=?",
            (username,)
        ).fetchone()

        conn.close()

        if admin and check_password_hash(admin[2], password):
            session.clear()
            session["admin_id"] = admin[0]
            session["admin_username"] = admin[1]
            return redirect("/admin-dashboard")

        return render_template(
            "admin_login.html",
            error="Incorrect username or password"
        )

    return render_template("admin_login.html")


# ADMIN DASHBOARD
@app.route("/admin-dashboard")
def admin_dashboard():
    conn = connect_db()

    players = conn.execute(
        "SELECT COUNT(*) FROM players"
    ).fetchone()[0]

    teams = conn.execute(
        "SELECT COUNT(*) FROM teams"
    ).fetchone()[0]

    games = conn.execute(
        "SELECT COUNT(*) FROM games"
    ).fetchone()[0]

    admins = conn.execute(
        "SELECT COUNT(*) FROM admins"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "admin_dashboard.html",
        players=players,
        teams=teams,
        games=games,
        admins=admins
    )


# CREATE ANOTHER ADMIN
@app.route("/create-admin", methods=["GET", "POST"])
def create_admin():
    error = None

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username:
            error = "Please enter a username."

        elif len(password) < 8:
            error = "Password must have at least 8 characters."

        else:
            conn = connect_db()

            try:
                password_hash = generate_password_hash(password)

                conn.execute(
                    "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
                    (username, password_hash)
                )

                conn.commit()
                conn.close()
                return redirect("/admin-dashboard")

            except sqlite3.IntegrityError:
                conn.close()
                error = "That username already exists."

    return render_template("create_admin.html", error=error)


# ADMIN LOGOUT
@app.route("/admin-logout")
def admin_logout():
    session.clear()
    return redirect("/admin-login")


# MAIN DASHBOARD
@app.route("/")
def home():
    conn = connect_db()

    total_players = conn.execute(
        "SELECT COUNT(*) FROM players"
    ).fetchone()[0]

    total_teams = conn.execute(
        "SELECT COUNT(*) FROM teams"
    ).fetchone()[0]

    total_games = conn.execute(
        "SELECT COUNT(*) FROM games"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        total_players=total_players,
        total_teams=total_teams,
        total_games=total_games
    )


# REGISTER PLAYER
@app.route("/players", methods=["GET", "POST"])
def players():
    if request.method == "POST":
        conn = connect_db()

        conn.execute("""
            INSERT INTO players (name, age, phone, sport)
            VALUES (?, ?, ?, ?)
        """, (
            request.form["name"],
            request.form["age"],
            request.form["phone"],
            request.form["sport"]
        ))

        conn.commit()
        conn.close()
        return redirect("/players-list")

    return render_template("players.html")


# SEARCH PLAYERS
@app.route("/search-players")
def search_players():
    query = request.args.get("q", "")

    conn = connect_db()
    records = conn.execute("""
        SELECT * FROM players
        WHERE name LIKE ?
        ORDER BY name
    """, ("%" + query + "%",)).fetchall()
    conn.close()

    return render_template(
        "search_players.html",
        players=records,
        query=query
    )


# VIEW PLAYERS
@app.route("/players-list")
def players_list():
    conn = connect_db()
    records = conn.execute("SELECT * FROM players").fetchall()
    conn.close()

    return render_template("players_list.html", players=records)


# EDIT PLAYER
@app.route("/edit-player/<int:player_id>", methods=["GET", "POST"])
def edit_player(player_id):
    conn = connect_db()

    if request.method == "POST":
        conn.execute("""
            UPDATE players
            SET name=?, age=?, phone=?, sport=?
            WHERE id=?
        """, (
            request.form["name"],
            request.form["age"],
            request.form["phone"],
            request.form["sport"],
            player_id
        ))

        conn.commit()
        conn.close()
        return redirect("/players-list")

    player = conn.execute(
        "SELECT * FROM players WHERE id=?",
        (player_id,)
    ).fetchone()

    conn.close()
    return render_template("edit_player.html", player=player)


# DELETE PLAYER
@app.route("/delete-player/<int:player_id>", methods=["POST"])
def delete_player(player_id):
    conn = connect_db()
    conn.execute("DELETE FROM players WHERE id=?", (player_id,))
    conn.commit()
    conn.close()

    return redirect("/players-list")


# STATISTICS
@app.route("/statistics")
def statistics():
    conn = connect_db()

    football = conn.execute(
        "SELECT COUNT(*) FROM players WHERE sport='Football'"
    ).fetchone()[0]

    basketball = conn.execute(
        "SELECT COUNT(*) FROM players WHERE sport='Basketball'"
    ).fetchone()[0]

    volleyball = conn.execute(
        "SELECT COUNT(*) FROM players WHERE sport='Volleyball'"
    ).fetchone()[0]

    freezeb = conn.execute(
        "SELECT COUNT(*) FROM players WHERE sport='FreeSE B'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "statistics.html",
        football=football,
        basketball=basketball,
        volleyball=volleyball,
        freezeb=freezeb
    )


# CREATE TEAM
@app.route("/teams", methods=["GET", "POST"])
def teams():
    if request.method == "POST":
        conn = connect_db()

        conn.execute("""
            INSERT INTO teams (team_name, sport)
            VALUES (?, ?)
        """, (
            request.form["team_name"],
            request.form["sport"]
        ))

        conn.commit()
        conn.close()
        return redirect("/teams-list")

    return render_template("teams.html")


# SEARCH TEAMS
@app.route("/search-teams")
def search_teams():
    query = request.args.get("q", "")

    conn = connect_db()
    records = conn.execute("""
        SELECT * FROM teams
        WHERE team_name LIKE ?
        ORDER BY team_name
    """, ("%" + query + "%",)).fetchall()
    conn.close()

    return render_template(
        "search_teams.html",
        teams=records,
        query=query
    )


# ASSIGN PLAYERS TO TEAMS
@app.route("/assign-players", methods=["GET", "POST"])
def assign_players():
    conn = connect_db()

    if request.method == "POST":
        team_id = request.form["team_id"]
        player_id = request.form["player_id"]

        existing = conn.execute("""
            SELECT id FROM team_players
            WHERE team_id=? AND player_id=?
        """, (team_id, player_id)).fetchone()

        if not existing:
            conn.execute("""
                INSERT INTO team_players (team_id, player_id)
                VALUES (?, ?)
            """, (team_id, player_id))

        conn.commit()
        conn.close()
        return redirect("/assign-players")

    teams = conn.execute("SELECT * FROM teams").fetchall()
    player_records = conn.execute("SELECT * FROM players").fetchall()

    assignments = conn.execute("""
        SELECT team_players.id, teams.team_name, players.name
        FROM team_players
        JOIN teams ON teams.id = team_players.team_id
        JOIN players ON players.id = team_players.player_id
        ORDER BY teams.team_name
    """).fetchall()

    conn.close()

    return render_template(
        "assign_players.html",
        teams=teams,
        players=player_records,
        assignments=assignments
    )


# REMOVE PLAYER FROM TEAM
@app.route("/remove-assignment/<int:assignment_id>", methods=["POST"])
def remove_assignment(assignment_id):
    conn = connect_db()
    conn.execute(
        "DELETE FROM team_players WHERE id=?",
        (assignment_id,)
    )
    conn.commit()
    conn.close()

    return redirect("/assign-players")


# TEAM PROFILE
@app.route("/team-profile/<int:team_id>")
def team_profile(team_id):
    conn = connect_db()

    team = conn.execute(
        "SELECT * FROM teams WHERE id=?",
        (team_id,)
    ).fetchone()

    if team is None:
        conn.close()
        return "Team not found", 404

    games = conn.execute("""
        SELECT * FROM games
        WHERE home_team=? OR away_team=?
        ORDER BY match_date DESC
    """, (team[1], team[1])).fetchall()

    conn.close()

    return render_template(
        "team_profile.html",
        team=team,
        games=games
    )


# TEAM ROSTER
@app.route("/team-roster/<int:team_id>")
def team_roster(team_id):
    conn = connect_db()

    team = conn.execute(
        "SELECT * FROM teams WHERE id=?",
        (team_id,)
    ).fetchone()

    if not team:
        conn.close()
        return "Team not found", 404

    player_records = conn.execute("""
        SELECT players.*
        FROM players
        JOIN team_players
        ON players.id = team_players.player_id
        WHERE team_players.team_id=?
    """, (team_id,)).fetchall()

    conn.close()

    return render_template(
        "team_roster.html",
        team=team,
        players=player_records
    )


# VIEW TEAMS
@app.route("/teams-list")
def teams_list():
    conn = connect_db()
    records = conn.execute("SELECT * FROM teams").fetchall()
    conn.close()

    return render_template("teams_list.html", teams=records)


# EDIT TEAM
@app.route("/edit-team/<int:team_id>", methods=["GET", "POST"])
def edit_team(team_id):
    conn = connect_db()

    if request.method == "POST":
        conn.execute("""
            UPDATE teams
            SET team_name=?, sport=?
            WHERE id=?
        """, (
            request.form["team_name"],
            request.form["sport"],
            team_id
        ))

        conn.commit()
        conn.close()
        return redirect("/teams-list")

    team = conn.execute(
        "SELECT * FROM teams WHERE id=?",
        (team_id,)
    ).fetchone()

    conn.close()
    return render_template("edit_team.html", team=team)


# DELETE TEAM
@app.route("/delete-team/<int:team_id>", methods=["POST"])
def delete_team(team_id):
    conn = connect_db()
    conn.execute("DELETE FROM teams WHERE id=?", (team_id,))
    conn.commit()
    conn.close()

    return redirect("/teams-list")


# REGISTER GAME
@app.route("/games", methods=["GET", "POST"])
def games():
    if request.method == "POST":
        conn = connect_db()

        conn.execute("""
            INSERT INTO games
            (home_team, away_team, sport, match_date)
            VALUES (?, ?, ?, ?)
        """, (
            request.form["home_team"],
            request.form["away_team"],
            request.form["sport"],
            request.form["match_date"]
        ))

        conn.commit()
        conn.close()
        return redirect("/games-list")

    return render_template("games.html")


# SEARCH GAMES
@app.route("/search-games")
def search_games():
    query = request.args.get("q", "")

    conn = connect_db()
    records = conn.execute("""
        SELECT * FROM games
        WHERE home_team LIKE ? OR away_team LIKE ?
        ORDER BY match_date DESC
    """, ("%" + query + "%", "%" + query + "%")).fetchall()
    conn.close()

    return render_template(
        "search_games.html",
        games=records,
        query=query
    )


# VIEW GAMES
@app.route("/games-list")
def games_list():
    conn = connect_db()

    records = conn.execute("""
        SELECT id, home_team, away_team, sport, match_date,
               home_score, away_score, status
        FROM games
    """).fetchall()

    conn.close()
    return render_template("games_list.html", games=records)


# EDIT GAME
@app.route("/edit-game/<int:game_id>", methods=["GET", "POST"])
def edit_game(game_id):
    conn = connect_db()

    if request.method == "POST":
        conn.execute("""
            UPDATE games
            SET home_team=?, away_team=?, sport=?, match_date=?
            WHERE id=?
        """, (
            request.form["home_team"],
            request.form["away_team"],
            request.form["sport"],
            request.form["match_date"],
            game_id
        ))

        conn.commit()
        conn.close()
        return redirect("/games-list")

    game = conn.execute(
        "SELECT * FROM games WHERE id=?",
        (game_id,)
    ).fetchone()

    conn.close()
    return render_template("edit_game.html", game=game)


# DELETE GAME
@app.route("/delete-game/<int:game_id>", methods=["POST"])
def delete_game(game_id):
    conn = connect_db()
    conn.execute("DELETE FROM games WHERE id=?", (game_id,))
    conn.commit()
    conn.close()

    return redirect("/games-list")


# UPDATE GAME RESULT
@app.route("/update-result/<int:game_id>", methods=["POST"])
def update_result(game_id):
    try:
        home_score = int(request.form["home_score"])
        away_score = int(request.form["away_score"])
    except (ValueError, KeyError):
        return redirect("/games-list")

    status = request.form["status"]

    if home_score < 0 or away_score < 0:
        return redirect("/games-list")

    if status not in ["Scheduled", "Live", "Completed"]:
        return redirect("/games-list")

    conn = connect_db()
    conn.execute("""
        UPDATE games
        SET home_score=?, away_score=?, status=?
        WHERE id=?
    """, (home_score, away_score, status, game_id))

    conn.commit()
    conn.close()

    return redirect("/games-list")


# RECORD ATTENDANCE
@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    conn = connect_db()

    if request.method == "POST":
        player_id = request.form["player_id"]
        attendance_date = request.form["attendance_date"]
        status = request.form["status"]

        conn.execute("""
            INSERT INTO attendance
            (player_id, attendance_date, status)
            VALUES (?, ?, ?)
        """, (player_id, attendance_date, status))

        conn.commit()
        conn.close()
        return redirect("/attendance-list")

    player_records = conn.execute(
        "SELECT * FROM players"
    ).fetchall()

    conn.close()
    return render_template("attendance.html", players=player_records)


# EDIT ATTENDANCE
@app.route("/edit-attendance/<int:attendance_id>", methods=["GET", "POST"])
def edit_attendance(attendance_id):
    conn = connect_db()

    if request.method == "POST":
        conn.execute("""
            UPDATE attendance
            SET player_id=?, attendance_date=?, status=?
            WHERE id=?
        """, (
            request.form["player_id"],
            request.form["attendance_date"],
            request.form["status"],
            attendance_id
        ))

        conn.commit()
        conn.close()
        return redirect("/attendance-list")

    attendance_record = conn.execute(
        "SELECT * FROM attendance WHERE id=?",
        (attendance_id,)
    ).fetchone()

    player_records = conn.execute(
        "SELECT * FROM players"
    ).fetchall()

    conn.close()

    return render_template(
        "edit_attendance.html",
        attendance=attendance_record,
        players=player_records
    )


# DELETE ATTENDANCE
@app.route("/delete-attendance/<int:attendance_id>", methods=["POST"])
def delete_attendance(attendance_id):
    conn = connect_db()
    conn.execute(
        "DELETE FROM attendance WHERE id=?",
        (attendance_id,)
    )
    conn.commit()
    conn.close()

    return redirect("/attendance-list")


# VIEW ATTENDANCE
@app.route("/attendance-list")
def attendance_list():
    conn = connect_db()

    records = conn.execute("""
        SELECT attendance.id, players.name,
               attendance.attendance_date,
               attendance.status
        FROM attendance
        JOIN players ON players.id = attendance.player_id
        ORDER BY attendance.attendance_date DESC
    """).fetchall()

    conn.close()

    return render_template(
        "attendance_list.html",
        records=records
    )


# PLAYER PROFILE
@app.route("/player-profile/<int:player_id>")
def player_profile(player_id):
    conn = connect_db()

    player = conn.execute(
        "SELECT * FROM players WHERE id=?",
        (player_id,)
    ).fetchone()

    if player is None:
        conn.close()
        return "Player not found", 404

    attendance_records = conn.execute("""
        SELECT attendance_date, status
        FROM attendance
        WHERE player_id=?
        ORDER BY attendance_date DESC
    """, (player_id,)).fetchall()

    conn.close()

    return render_template(
        "player_profile.html",
        player=player,
        attendance=attendance_records
    )


# PLAYER ATTENDANCE REPORTS
@app.route("/player-reports")
def player_reports():
    conn = connect_db()

    reports = conn.execute("""
        SELECT
            players.id,
            players.name,
            COUNT(attendance.id),
            SUM(CASE WHEN attendance.status='Present' THEN 1 ELSE 0 END),
            SUM(CASE WHEN attendance.status='Absent' THEN 1 ELSE 0 END),
            SUM(CASE WHEN attendance.status='Late' THEN 1 ELSE 0 END)
        FROM players
        LEFT JOIN attendance
        ON players.id = attendance.player_id
        GROUP BY players.id, players.name
        ORDER BY players.name
    """).fetchall()

    conn.close()

    return render_template("player_reports.html", reports=reports)


# ATTENDANCE STATISTICS
@app.route("/attendance-statistics")
def attendance_statistics():
    conn = connect_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM attendance"
    ).fetchone()[0]

    present = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE status='Present'"
    ).fetchone()[0]

    absent = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE status='Absent'"
    ).fetchone()[0]

    late = conn.execute(
        "SELECT COUNT(*) FROM attendance WHERE status='Late'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "attendance_statistics.html",
        total=total,
        present=present,
        absent=absent,
        late=late
    )


# MATCH STATISTICS
@app.route("/match-statistics")
def match_statistics():
    conn = connect_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM games"
    ).fetchone()[0]

    completed = conn.execute(
        "SELECT COUNT(*) FROM games WHERE status='Completed'"
    ).fetchone()[0]

    scheduled = conn.execute(
        "SELECT COUNT(*) FROM games WHERE status='Scheduled'"
    ).fetchone()[0]

    live = conn.execute(
        "SELECT COUNT(*) FROM games WHERE status='Live'"
    ).fetchone()[0]

    goals = conn.execute("""
        SELECT COALESCE(SUM(home_score), 0) +
               COALESCE(SUM(away_score), 0)
        FROM games
        WHERE status='Completed'
    """).fetchone()[0]

    conn.close()

    return render_template(
        "match_statistics.html",
        total=total,
        completed=completed,
        scheduled=scheduled,
        live=live,
        goals=goals
    )


# TEAM STANDINGS
@app.route("/standings")
def standings():
    conn = connect_db()

    teams = conn.execute(
        "SELECT team_name, sport FROM teams ORDER BY team_name"
    ).fetchall()

    games = conn.execute("""
        SELECT home_team, away_team, sport, home_score, away_score
        FROM games
        WHERE status='Completed'
    """).fetchall()

    conn.close()

    table = {}

    for team_name, sport in teams:
        key = (team_name, sport)
        table[key] = {
            "team": team_name,
            "sport": sport,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "points": 0
        }

    for home, away, sport, home_score, away_score in games:
        home_key = (home, sport)
        away_key = (away, sport)

        if home_key not in table or away_key not in table:
            continue

        h = table[home_key]
        a = table[away_key]

        h["played"] += 1
        a["played"] += 1

        if home_score > away_score:
            h["wins"] += 1
            h["points"] += 3
            a["losses"] += 1

        elif away_score > home_score:
            a["wins"] += 1
            a["points"] += 3
            h["losses"] += 1

        else:
            h["draws"] += 1
            a["draws"] += 1
            h["points"] += 1
            a["points"] += 1

    standings_table = sorted(
        table.values(),
        key=lambda x: (
            x["sport"], -x["points"], -x["wins"], x["team"]
        )
    )

    return render_template(
        "standings.html",
        standings=standings_table
    )


# PLAYER PERFORMANCE
@app.route("/player-performance", methods=["GET", "POST"])
def player_performance():
    conn = connect_db()

    if request.method == "POST":
        try:
            player_id = int(request.form["player_id"])
            game_id = int(request.form["game_id"])
            goals = int(request.form["goals"])
            assists = int(request.form["assists"])
            yellow = int(request.form["yellow_cards"])
            red = int(request.form["red_cards"])

            if min(goals, assists, yellow, red) < 0:
                raise ValueError

        except (ValueError, KeyError):
            conn.close()
            return "Please enter valid performance values.", 400

        conn.execute("""
            INSERT INTO player_performance
            (player_id, game_id, goals, assists,
             yellow_cards, red_cards)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (player_id, game_id, goals, assists, yellow, red))

        conn.commit()
        conn.close()
        return redirect("/player-performance")

    player_records = conn.execute(
        "SELECT * FROM players"
    ).fetchall()

    game_records = conn.execute(
        "SELECT * FROM games"
    ).fetchall()

    records = conn.execute("""
        SELECT player_performance.id, players.name,
               player_performance.game_id,
               player_performance.goals,
               player_performance.assists,
               player_performance.yellow_cards,
               player_performance.red_cards
        FROM player_performance
        JOIN players ON players.id = player_performance.player_id
        ORDER BY player_performance.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "player_performance.html",
        players=player_records,
        games=game_records,
        records=records
    )


# START APPLICATION
create_database()

if __name__ == "__main__":
    app.run(debug=False)

