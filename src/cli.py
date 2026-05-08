import sys
from .config import SUPPORTED_PLATFORMS, SUPPORTED_HOTELS


def get_user_input():
    print("=" * 50)
    print("        Welcome to the Product Alert Script")
    print("=" * 50)
    print(f"Products: {', '.join(SUPPORTED_PLATFORMS)}")
    print(f"Hotels: {', '.join(SUPPORTED_HOTELS)}\n")
    print("You can set up alerts for: Stock availability, Low price")
    print("-" * 50)

    # URL input
    url = input("Enter the product URL (or type 'exit' to quit): ")
    if url.strip().lower() == 'exit':
        print("Stopped by user.")
        sys.exit()  

    # Alert type input
    print("\nSelect alert type:")
    print("  1. Stock alert")
    print("  2. Low price alert")
    print("  3. Exit")
    alert_type = input("Enter 1, 2, or 3: ")
    if alert_type.strip() == "3" or alert_type.strip().lower() == 'exit':
        print("Stopped by user.")
        sys.exit()

    if alert_type == "2":
        while True:
            price_input = input("Enter your target price (or type 'exit' to quit): ")
            if price_input.strip().lower() == 'exit':
                print("Stopped by user.")
                sys.exit()
            try:
                price_threshold = float(price_input)
                break
            except ValueError:
                print("Please enter a valid number for the price.")
    else:
        price_threshold = None

    # Email input
    email = input("Enter your email for notifications (or type 'exit' to quit): ")
    if email.strip().lower() == 'exit':
        print("Stopped by user.")
        sys.exit()

    print("=" * 50)
    return url, alert_type, price_threshold, email
