import os
import mysql.connector
from dotenv import load_dotenv

# Load environmental variables from .env file
load_dotenv()

def get_db_connection(include_db=True):
    """
    Establishes a connection to the TiDB (MySQL-compatible) database.
    """
    config = {
        'host': os.getenv('TIDB_HOST'),
        'port': int(os.getenv('TIDB_PORT', 4000)),
        'user': os.getenv('TIDB_USER'),
        'password': os.getenv('TIDB_PASSWORD'),
    }
    
    # TiDB Cloud connections usually require secure connections
    # Passing ssl_verify_cert=False allows SSL without requiring a local CA bundle path
    # If the driver throws errors, we fallback.
    config['ssl_verify_cert'] = False
    
    if include_db:
        config['database'] = os.getenv('TIDB_DATABASE')
        
    return mysql.connector.connect(**config)

def init_db():
    db_name = os.getenv('TIDB_DATABASE')
    print(f"Establishing connection to TiDB host: {os.getenv('TIDB_HOST')}...")
    
    try:
        # Connect to TiDB server without selecting a specific database first
        conn = get_db_connection(include_db=False)
        cursor = conn.cursor()
        
        # Create database if it does not exist. Wrap database name in backticks because it contains a space.
        print(f"Creating database `{db_name}` if it doesn't exist...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
        cursor.close()
        conn.close()
        
        # Connect to the newly created / existing database to run schema.sql
        print(f"Connecting to database `{db_name}`...")
        conn = get_db_connection(include_db=True)
        cursor = conn.cursor()
        
        # Load and run schema.sql
        schema_file_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        print(f"Reading schema definition from {schema_file_path}...")
        with open(schema_file_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            
        print("Initializing database tables...")
        # mysql-connector-python supports executing multiple statements using multi=True
        results = cursor.execute(schema_sql, multi=True)
        for result in results:
            pass  # Ensure all statements in iterator are executed
            
        conn.commit()
        print("Database schema successfully initialized!")
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Database initialization failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    init_db()
