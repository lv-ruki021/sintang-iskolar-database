import os
import mysql.connector
from dotenv import load_dotenv

# Load environmental variables
load_dotenv()

def inspect():
    config = {
        'host': os.getenv('TIDB_HOST'),
        'port': int(os.getenv('TIDB_PORT', 4000)),
        'user': os.getenv('TIDB_USER'),
        'password': os.getenv('TIDB_PASSWORD'),
        'ssl_verify_cert': False
    }
    
    try:
        print("Connecting to TiDB server...")
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        
        # Show all databases
        cursor.execute("SHOW DATABASES")
        databases = [row[0] for row in cursor.fetchall()]
        print("Available databases:", databases)
        
        # We check if 'Scholarship' or similar databases exist
        # Or check tables in 'Infoman Database' (which is set in .env)
        target_db = 'Scholarship'
        print(f"\nSwitching to database: {target_db}")
        cursor.execute(f"USE `{target_db}`")
        
        cursor.execute("SHOW TABLES")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tables in `{target_db}`:", tables)
        
        for table in tables:
            print(f"\n--- Columns in table `{table}` ---")
            cursor.execute(f"DESCRIBE `{table}`")
            for col in cursor.fetchall():
                print(col)
                
            print(f"\n--- Create Table syntax for `{table}` ---")
            cursor.execute(f"SHOW CREATE TABLE `{table}`")
            print(cursor.fetchone()[1])
            
        cursor.close()
        conn.close()
    except Exception as e:
        print("Error during inspection:", e)

if __name__ == '__main__':
    inspect()
