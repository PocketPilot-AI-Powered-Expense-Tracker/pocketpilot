import pytest

from app.utils.categorize import suggest_category
from app.utils.upi_parser import NotAPayment, parse_notification


@pytest.mark.parametrize("title,text,amount,party,ref", [
    ("Payment Successful", "₹120 paid to Campus Cafe. UPI Ref No. 432112345678", 12000, "Campus Cafe", "432112345678"),
    ("", "You paid ₹500.00 to Rahul Sharma using UPI. UPI transaction ID 532198765432", 50000, "Rahul Sharma", "532198765432"),
    ("Paytm", "Rs.249 paid to Swiggy successfully. Ref: 612345098765", 24900, "Swiggy", "612345098765"),
    ("Money sent", "Sent Rs 1,250.5 to Hostel Mess", 125050, "Hostel Mess", None),
    ("", "INR 80 debited from your account", 8000, None, None),
])
def test_parses_successful_debits(title, text, amount, party, ref):
    p = parse_notification(title, text)
    assert (p.amount_paise, p.counterparty, p.transaction_ref) == (amount, party, ref)


@pytest.mark.parametrize("title,text", [
    ("Money received", "Received ₹1,000 from Mom"),
    ("", "₹500 credited to your account"),
    ("Payment request", "Riya requested ₹300 from you"),
    ("", "Payment of ₹80 to Auto failed"),
    ("", "₹50 cashback won!"),
    ("", "Refund of ₹199 processed"),
    ("Offer", "Get 10% off on your next order"),
    ("", "Paid to Ravi"),  # no amount
])
def test_ignores_non_payments(title, text):
    with pytest.raises(NotAPayment):
        parse_notification(title, text)


@pytest.mark.parametrize("name,cat", [
    ("Campus Cafe", "food"), ("SWIGGY", "food"), ("Uber India", "transportation"), ("Amazon Pay", "shopping"),
    ("Netflix", "subscriptions"), ("BookMyShow", "entertainment"), ("Apollo Pharmacy", "personal_care"),
    ("Rahul Sharma", "other"), (None, "other"),
])
def test_category_suggestion(name, cat):
    assert suggest_category(name) == cat
