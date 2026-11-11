"""Start the hosted demo with a fresh synthetic inventory database."""
from pathlib import Path
import tempfile

import booking_inventory
from booking_inventory import initialize_inventory
from web_demo_server import serve

# Keep hosted demo inventory separate from any local database or bookings.
booking_inventory.DB = str(Path(tempfile.gettempdir()) / "masaraat_demo_inventory.db")
initialize_inventory(reset=True)
serve()
