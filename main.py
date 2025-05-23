from pathlib import Path
from dotenv import load_dotenv
import os

# Use pathlib to get the path to your .env file (for example, in the project root)
env_path = Path(__file__).parent / '.env'

# Load the .env file
load_dotenv(dotenv_path=env_path)

# Access a secret or environment variable
db_password = os.getenv('DB_PASSWORD')
print(f"Database password: {db_password}")