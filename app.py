import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Check if API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Create users table
db.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    hash TEXT NOT NULL,
    cash NUMERIC NOT NULL DEFAULT 10000.00
)
""")

# Create portfolio table
db.execute("""
CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    userid INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    shares INTEGER NOT NULL,
    FOREIGN KEY(userid) REFERENCES users(id)
)
""")

# Create history table
db.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    userid INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    shares INTEGER NOT NULL,
    method TEXT NOT NULL,
    price NUMERIC NOT NULL,
    transacted DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(userid) REFERENCES users(id)
)
""")

# Make sure there is no cache
@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    # retrieve user's cash balance
    cash_rows = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    cash = cash_rows[0]['cash'] if cash_rows else 0

    # retrieve user's stock portfolio
    rows = db.execute(
        """
        SELECT portfolio.*
        FROM portfolio
        WHERE userid = :id
        """,
        id=session["user_id"])

    # add stock name, add current lookup value, add total value
    rows = [{
        **row,
        'name': (look := lookup(row['symbol'])).get('name', 'N/A'),
        'price': look.get('price', 0),
        'total': (total := look.get('price', 0) * row['shares']),
        'price_usd': usd(look.get('price', 0)),
        'total_usd': usd(total),
    } for row in rows]

    # calculate total value of stocks
    total_stock_value = sum(row['total'] for row in rows)

    # calculate total value of portfolio
    portfolio_value = cash + total_stock_value

    return render_template("index.html", rows=rows, cash=usd(cash), total_stock_value=usd(total_stock_value), sum=usd(portfolio_value))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "GET":
        return render_template("buy.html")

    else:
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        # Validate shares
        if not shares.isdigit() or int(shares) <= 0:
            return apology("must provide a positive integer for shares", 400)

        shares = int(shares)
        quote = lookup(symbol)

        if quote == None:
            return apology("must provide valid stock symbol", 400)

        purchase = quote['price'] * shares

        rows = db.execute(
            """
            SELECT cash, shares
            FROM users
            JOIN portfolio ON users.id = portfolio.userid
            WHERE users.id = :id AND symbol = :symbol
            """,
            id=session["user_id"], symbol=symbol)

        if len(rows) == 0:
            cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])[0]['cash']
            if cash < purchase:
                return apology("insufficient funds", 400)
            db.execute(
                """
                INSERT INTO portfolio (userid, symbol, shares)
                VALUES (:id, :symbol, :shares)
                """,
                id=session["user_id"], symbol=symbol, shares=shares)
        else:
            cash, oldshares = rows[0]['cash'], rows[0]['shares']
            if cash < purchase:
                return apology("insufficient funds", 400)
            db.execute(
                """
                UPDATE portfolio SET shares = :newshares
                WHERE userid = :id AND symbol = :symbol
                """,
                newshares=oldshares + shares, id=session["user_id"], symbol=symbol)

        remainder = cash - purchase
        db.execute(
            "UPDATE users SET cash = :remainder WHERE id = :id",
            remainder=remainder, id=session["user_id"])

        db.execute(
            """
            INSERT INTO history (userid, symbol, shares, method, price)
            VALUES (:userid, :symbol, :shares, 'Buy', :price)
            """,
            userid=session["user_id"], symbol=symbol, shares=shares, price=quote['price'])

    return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    rows = db.execute("SELECT * FROM history WHERE userid = :userid ORDER BY transacted DESC", userid=session["user_id"])

    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "GET":
        return render_template("quote.html")
    else:
        # get symbol from form
        symbol_form = request.form.get("symbol")

        # lookup ticker symbol from quote.html form
        symbol = lookup(symbol_form)

        if symbol == None:
            return apology("invalid stock symbol", 400)

        return render_template("quoted.html", symbol=symbol)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("must provide username", 400)
        elif not password:
            return apology("must provide password", 400)
        elif password != confirmation:
            return apology("passwords do not match", 400)

        hash = generate_password_hash(password)

        try:
            db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                       username=username, hash=hash)
        except:
            return apology("username is already taken", 400)

        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "GET":
        portfolio = db.execute("SELECT symbol FROM portfolio WHERE userid = :id",
                               id=session["user_id"])
        return render_template("sell.html", portfolio=portfolio)
    else:
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        quote = lookup(symbol)
        rows = db.execute("SELECT * FROM portfolio WHERE userid = :id AND symbol = :symbol",
                          id=session["user_id"], symbol=symbol)

        if len(rows) != 1:
            return apology("must provide valid stock symbol", 400)
        if not shares:
            return apology("must provide number of shares", 400)

        oldshares = rows[0]['shares']

        if shares > oldshares:
            return apology("shares sold can't exceed shares owned", 400)

        sold = quote['price'] * shares

        db.execute("UPDATE users SET cash = cash + :sold WHERE id = :id",
                   sold=sold, id=session["user_id"])

        newshares = oldshares - shares

        if newshares > 0:
            db.execute("UPDATE portfolio SET shares = :newshares WHERE userid = :id AND symbol = :symbol",
                       newshares=newshares, id=session["user_id"], symbol=symbol)
        else:
            db.execute("DELETE FROM portfolio WHERE symbol = :symbol AND userid = :id",
                       symbol=symbol, id=session["user_id"])

        db.execute("INSERT INTO history (userid, symbol, shares, method, price) VALUES (:userid, :symbol, :shares, 'Sell', :price)",
                   userid=session["user_id"], symbol=symbol, shares=shares, price=quote['price'])

        return redirect("/")
