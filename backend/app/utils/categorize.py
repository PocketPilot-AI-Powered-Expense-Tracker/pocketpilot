"""Deterministic category suggestion from a merchant/recipient name.
Only a suggestion: the user always confirms the category before anything is saved."""
import re

_RULES = [
    ("rent", r"\brent\b|\bpg\b|paying guest|landlord|room rent|flat rent|house rent|hostel fee|nobroker|nestaway|zolo|stanza|housing"),
    ("food", r"mess|lunch|dinner|breakfast|snack|meal|coffee|samosa|maggi|cafe|café|canteen|restaurant|swiggy|zomato|domino|pizza|burger|kfc|mcdonald|starbucks|chai|tea|"
             r"bakery|food|dhaba|juice|momo|biryani|kitchen|mess|blinkit|zepto|instamart|bigbasket"),
    ("transportation", r"uber|ola|rapido|metro|irctc|railway|bus|redbus|petrol|fuel|fastag|auto|cab|parking"),
    ("shopping", r"amazon|flipkart|myntra|ajio|meesho|nykaa|mall|store|mart|shop|decathlon|croma"),
    ("subscriptions", r"netflix|spotify|hotstar|prime|youtube|jio|airtel|vi\b|recharge|google play|apple"),
    ("entertainment", r"bookmyshow|pvr|inox|cinema|movie|game|steam|concert|club"),
    ("education", r"book|stationery|xerox|print|college|university|school|course|udemy|coursera|exam|library"),
    ("personal_care", r"salon|pharmacy|medical|apollo|chemist|clinic|hospital|gym|spa|barber|1mg|pharmeasy"),
]


def suggest_category(counterparty: str | None) -> str:
    name = (counterparty or "").lower()
    for category, pattern in _RULES:
        if re.search(pattern, name):
            return category
    return "other"
