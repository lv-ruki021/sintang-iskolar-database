import os
import sys
import pymysql
from dotenv import load_dotenv

# Ensure the project directory is in the Python path so we can import app
sys.path.insert(0, r"C:\Users\Lance Valerio\Downloads\CODING\scholarship_database")

# Load environment variables
load_dotenv(r"C:\Users\Lance Valerio\Downloads\CODING\scholarship_database\.env")

# 1. Fetch current student record from the database
conn = pymysql.connect(
    host=os.getenv('TIDB_HOST'),
    port=int(os.getenv('TIDB_PORT', 4000)),
    user=os.getenv('TIDB_USER'),
    password=os.getenv('TIDB_PASSWORD'),
    database=os.getenv('TIDB_DATABASE'),
    ssl={'ssl_check_hostname': False}
)

student_id = "2024-02603-MN-0"
try:
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT * FROM Student WHERE Student_ID = %s", (student_id,))
        student = cursor.fetchone()
        if not student:
            print("Student not found!")
            sys.exit(1)
        
        original_religion = student['Religion']
        original_landline = student['Landline']
        print(f"Original Religion: {original_religion}, Original Landline: {original_landline}")
finally:
    conn.close()

# 2. Setup Flask test client
from app import app

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False

# Toggle test values
test_religion = "Agnostic" if original_religion != "Agnostic" else "Roman Catholic"
test_landline = "1234567" if original_landline != "1234567" else "7654321"

# Prepare request payload
payload = {
    'Scholarship_Type': student['Scholarship_Type'],
    'Scholar_Classification': student['Scholar_Classification'],
    'Name': student['Name'],
    'Landline': test_landline,
    'Mobile_Number': student['Mobile_Number'],
    'Email_Address': student['Email_Address'],
    'College_Enrolled': student['College_Enrolled'],
    'Program': student['Program'],
    'Year_and_Section': student['Year_and_Section'],
    'Address': student['Address'],
    'Date_of_Birth': student['Date_of_Birth'].strftime('%Y-%m-%d') if student['Date_of_Birth'] else '',
    'Age': student['Age'],
    'Civil_Status': student['Civil_Status'],
    'Citizenship': student['Citizenship'],
    'Religion': test_religion,
    'Working_Student': '1' if student['Working_Student'] else '0',
    'Job_Title': student['Job_Title'] or '',
    'Is_Regular': '1',
    'Vehicles_Owned_Count': student.get('Vehicles_Owned_Count') or 0,
    'Other_Scholarship': student['Other_Scholarship'] or '',
    'Lowest_Subject_Grade': student['Grade_11_GWA'] or '',
    'College_GWA': student['Grade_12_GWA'] or '',
    'House_Ownership': student['House_Ownership'],
    'Total_Annual_Household_Income': student['Total_Annual_Household_Income'],
    'COR': student['COR'] or '',
    'CTC': student['CTC'] or '',
    'FORM137': student['FORM137'] or '',
    'Proof_of_Income': student['Proof_of_Income']
}

print(f"\nSubmitting POST request to /admin/edit/{student_id} with Religion={test_religion} and Landline={test_landline}...")

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['is_admin'] = True  # Authenticate session
    
    response = client.post(f'/admin/edit/{student_id}', data=payload, follow_redirects=True)
    print(f"Response Status Code: {response.status_code}")

# 3. Verify database updates
conn = pymysql.connect(
    host=os.getenv('TIDB_HOST'),
    port=int(os.getenv('TIDB_PORT', 4000)),
    user=os.getenv('TIDB_USER'),
    password=os.getenv('TIDB_PASSWORD'),
    database=os.getenv('TIDB_DATABASE'),
    ssl={'ssl_check_hostname': False}
)

try:
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("SELECT * FROM Student WHERE Student_ID = %s", (student_id,))
        updated_student = cursor.fetchone()
        
        print("\nVerification Results:")
        print(f"Updated Religion: {updated_student['Religion']} (Expected: {test_religion})")
        print(f"Updated Landline: {updated_student['Landline']} (Expected: {test_landline})")
        
        success = updated_student['Religion'] == test_religion and updated_student['Landline'] == test_landline
        if success:
            print("\n>>> SUCCESS: MySQL properly updates itself with changes from the web app! <<<")
        else:
            print("\n>>> FAILURE: Database updates do not match web app input! <<<")
            
        # 4. Restore original values
        cursor.execute(
            "UPDATE Student SET Religion = %s, Landline = %s WHERE Student_ID = %s",
            (original_religion, original_landline, student_id)
        )
        conn.commit()
        print("\nRestored original values in the database.")
finally:
    conn.close()
