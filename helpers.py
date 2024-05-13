import os
import csv
import datetime
import pytz
import requests
import urllib
import uuid

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user."""

    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [
            ("-", "--"),
            (" ", "-"),
            ("_", "__"),
            ("?", "~q"),
            ("%", "~p"),
            ("#", "~h"),
            ("/", "~s"),
            ('"', "''"),
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function


def lookup(symbol):
    """Look up quote for symbol."""

    # Print out the API key and symbol for debugging
    print("API Key:", os.environ.get("API_KEY"))
    print("Symbol:", symbol)

    try:
        api_key = os.environ.get("API_KEY")
        response = requests.get(f"https://api.iex.cloud/v1/data/core/quote/{symbol}?token={api_key}")
        response.raise_for_status()
    except requests.RequestException as e:
        # Print out the exception for debugging
        print("Request Exception:", e)
        return None

    try:
        quote = response.json()
        print("Response:", quote)  # Print out the response for debugging

        # If the response is a list, get the first element
        if isinstance(quote, list):
            quote = quote[0]

        return {
            "name": quote["companyName"],
            "price": float(quote["latestPrice"]),
            "symbol": quote["symbol"]
        }
    except (KeyError, TypeError, ValueError) as e:
        # Print out the exception for debugging
        print("JSON Exception:", e)
        return None


def usd(value):
    """Format value as USD."""
    try:
        return f"${float(value):,.2f}"
    except ValueError:
        return value
