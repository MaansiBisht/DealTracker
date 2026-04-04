import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
PINCODE = os.getenv("PINCODE")

SUPPORTED_PLATFORMS = ["AMUL", "MYNTRA", "FLIPKART", "AMAZON", "AMAZFIT"]
SUPPORTED_HOTELS = ["BOOKING.COM", "MAKEMYTRIP", "GOIBIBO", "AGODA"]
