import os
import pymysql
from dotenv import load_dotenv

# Load environmental variables
load_dotenv()

def update_schema():
    conn = None
    cursor = None
    try:
        print("Connecting to TiDB database...")
        conn = pymysql.connect(
            host=os.getenv('TIDB_HOST'),
            port=int(os.getenv('TIDB_PORT', 4000)),
            user=os.getenv('TIDB_USER'),
            password=os.getenv('TIDB_PASSWORD'),
            database=os.getenv('TIDB_DATABASE'),
            ssl={'ssl_check_hostname': False}
        )
        cursor = conn.cursor()
        
        # Add new columns to Student table
        columns_to_add = [
            ("Is_Regular", "TINYINT(1) DEFAULT 1"),
            ("Lowest_Subject_Grade", "DECIMAL(5,2) DEFAULT NULL"),
            ("Scholar_Sub_Classification", "VARCHAR(50) DEFAULT NULL"),
            ("Vehicles_Owned_Count", "INT DEFAULT 0")
        ]
        
        for col_name, col_type in columns_to_add:
            print(f"Checking column `{col_name}`...")
            try:
                # Attempt to add column
                cursor.execute(f"ALTER TABLE Student ADD COLUMN `{col_name}` {col_type}")
                print(f"Column `{col_name}` added successfully.")
            except pymysql.Error as err:
                errno = err.args[0] if len(err.args) > 0 else None
                if errno == 1060: # Duplicate column name
                    print(f"Column `{col_name}` already exists.")
                else:
                    errmsg = err.args[1] if len(err.args) > 1 else str(err)
                    print(f"Error adding column `{col_name}`: {errmsg}")
                    
        conn.commit()
        print("Database migration completed successfully!")
        
    except Exception as e:
        print("Migration failed:", e)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    update_schema()
