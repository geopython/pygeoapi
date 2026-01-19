import os
import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 1. Locate and Load the Config File
# This looks for pygeoapi-config.yml one level up from the 'src' folder
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, 'pygeoapi-config.yml')

if not os.path.exists(CONFIG_PATH):
    raise FileNotFoundError(f"Config file not found at: {CONFIG_PATH}")

with open(CONFIG_PATH, 'r') as f:
    config = yaml.safe_load(f)

# 2. Construct Database URL
db_conf = config['database']
DATABASE_URL = f"postgresql://{db_conf['username']}:{db_conf['password']}@{db_conf['host']}:{db_conf['port']}/{db_conf['database']}"

# 3. Create the Engine
# 'echo=True' prints actual SQL queries to the console (great for debugging)
engine = create_engine(DATABASE_URL, echo=True)

# 4. Create a Session Factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 5. Dependency helper (useful if you use FastAPI later)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 6. Quick Connection Test
if __name__ == "__main__":
    try:
        with engine.connect() as connection:
            # Check PostGIS version to verify spatial features are working
            result = connection.execute(text("SELECT postgis_full_version();"))
            version = result.fetchone()[0]
            print("\n✅ SUCCESS: Connected to Database!")
            print(f"🌍 PostGIS Version: {version}\n")
    except Exception as e:
        print("\n❌ CONNECTION FAILED")
        print(e)