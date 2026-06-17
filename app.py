import os
import re
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
import pymysql
import pymysql.cursors
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables and initialize Flask app
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'scholarship_db_secret_key_123!')

# Decorators for auth
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Please log in as an administrator to access this page.", "warning")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def user_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        student_id = kwargs.get('student_id') or kwargs.get('id')
        is_admin = session.get('is_admin')
        is_authorized_applicant = session.get('applicant_id') == student_id
        if not (is_admin or is_authorized_applicant):
            flash("Access denied. You are not authorized to access or modify this application.", "danger")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def redirect_to_dossier(student_id):
    if session.get('is_admin'):
        return redirect(url_for('admin_view', id=student_id))
    return redirect(url_for('applicant_view', student_id=student_id))

@app.route('/')
def home():
    """
    Renders the public landing page.
    """
    return render_template('home.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('is_admin'):
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin1' and password == 'sintangiskolar':
            session['is_admin'] = True
            session.pop('applicant_id', None)
            flash("Admin login successful. Welcome to the Sintang Iskolar coordinator dashboard!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid admin username or password.", "danger")
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    flash("You have been logged out of the admin panel.", "info")
    return redirect(url_for('home'))

@app.route('/applicant/login', methods=['GET', 'POST'])
def applicant_login():
    if session.get('applicant_id'):
        return redirect(url_for('applicant_view', student_id=session.get('applicant_id')))
    if request.method == 'POST':
        student_id = request.form.get('student_id', '').strip()
        email = request.form.get('email', '').strip()
        
        if not student_id or not email:
            flash("Please enter both Student ID and Email.", "warning")
            return render_template('applicant_login.html')
            
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute(
                "SELECT * FROM Student WHERE Student_ID = %s AND Email_Address = %s",
                (student_id, email)
            )
            student = cursor.fetchone()
            if student:
                session['applicant_id'] = student_id
                session.pop('is_admin', None)
                flash(f"Login successful! Welcome back, {student['Name']}.", "success")
                return redirect(url_for('applicant_view', student_id=student_id))
            else:
                flash("No matching applicant found with those credentials. Please check your Student ID and Email.", "danger")
        except Exception as e:
            flash(f"Database login error: {str(e)}", "danger")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    return render_template('applicant_login.html')

@app.route('/applicant/logout')
def applicant_logout():
    session.pop('applicant_id', None)
    flash("You have successfully logged out.", "info")
    return redirect(url_for('home'))

@app.route('/applicant/view/<string:student_id>')
def applicant_view(student_id):
    if session.get('applicant_id') != student_id and not session.get('is_admin'):
        flash("Access denied. You can only view your own application profile.", "danger")
        return redirect(url_for('home'))
        
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM Student WHERE Student_ID = %s", (student_id,))
        student = cursor.fetchone()
        if not student:
            flash("Student profile not found.", "danger")
            return redirect(url_for('home'))
            
        sub_class = None
        other_scholar_cleaned = student.get('Other_Scholarship', '')
        if other_scholar_cleaned:
            match = re.search(r'\\[(.*?)\\]', other_scholar_cleaned)
            if match:
                sub_class = match.group(1)
                other_scholar_cleaned = other_scholar_cleaned.replace(f'[{sub_class}]', '').strip()
                
        student['Scholar_Sub_Classification'] = sub_class
        student['Other_Scholarship_Cleaned'] = other_scholar_cleaned
        
        if student['Scholar_Classification'] == 'Upperclassman':
            student['Lowest_Subject_Grade'] = student['Grade_11_GWA']
            student['College_GWA'] = student['Grade_12_GWA']
        
        cursor.execute("SELECT * FROM Family WHERE Student_ID = %s ORDER BY Family_ID ASC", (student_id,))
        family = cursor.fetchall()
        
        cursor.execute("SELECT * FROM School WHERE Student_ID = %s ORDER BY School_From ASC", (student_id,))
        schools = cursor.fetchall()
        
        cursor.execute("SELECT * FROM Extra_Curricular WHERE Student_ID = %s ORDER BY Extra_Curricular_Year ASC", (student_id,))
        extracurs = cursor.fetchall()
        
        return render_template(
            'view_scholar.html', 
            student=student, 
            family=family, 
            schools=schools, 
            extracurs=extracurs
        )
    except Exception as e:
        flash(f"Database error loading dossier: {str(e)}", "danger")
        return redirect(url_for('home'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



def get_db_connection():
    """
    Establish a connection to the TiDB Database.
    """
    return pymysql.connect(
        host=os.getenv('TIDB_HOST'),
        port=int(os.getenv('TIDB_PORT', 4000)),
        user=os.getenv('TIDB_USER'),
        password=os.getenv('TIDB_PASSWORD'),
        database=os.getenv('TIDB_DATABASE'),
        ssl={'ssl_check_hostname': False}
    )

def clean_input(val, is_num=False, is_date=False):
    """
    Converts empty form inputs to None (so they map to NULL in MySQL)
    and formats types correctly.
    """
    if val is None or str(val).strip() == '':
        return None
    val_str = str(val).strip()
    
    if is_num:
        try:
            return float(val_str) if '.' in val_str else int(val_str)
        except ValueError:
            return None
    if is_date:
        try:
            # HTML5 date inputs submit as YYYY-MM-DD
            return datetime.strptime(val_str, '%Y-%m-%d').date()
        except ValueError:
            return None
            
    return val_str

def round_to_closest_standard(grade):
    """
    Rounds a college grade to the closest standard step (1.00, 1.25, ..., 3.00, 5.00).
    """
    if grade is None:
        return None
    try:
        grade = float(grade)
        standards = [1.00, 1.25, 1.50, 1.75, 2.00, 2.25, 2.50, 2.75, 3.00, 5.00]
        return min(standards, key=lambda x: abs(x - grade))
    except (ValueError, TypeError):
        return None

@app.route('/admin')
@admin_required
def index():
    """
    Fetch all students, calculate statistics, and render the dashboard.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Fetch all students
        cursor.execute("SELECT * FROM Student ORDER BY Student_ID ASC")
        students = cursor.fetchall()
        
        # Calculate statistics
        total_students = len(students)
        merit_scholars = [s for s in students if s['Scholarship_Type'] == 'Merit']
        financial_scholars = [s for s in students if s['Scholarship_Type'] == 'Financial Aid']
        working_scholars = [s for s in students if s['Working_Student'] == 1]
        freshmen_scholars = [s for s in students if s['Scholar_Classification'] == 'Freshmen']
        upperclassmen_scholars = [s for s in students if s['Scholar_Classification'] == 'Upperclassman']

        merit_count = len(merit_scholars)
        fin_aid_count = len(financial_scholars)
        working_count = len(working_scholars)
        
        # Calculate Working Students percentage
        working_pct = 0.0
        if total_students > 0:
            working_pct = (working_count / total_students) * 100
            
        # Calculate overall and split average GWAs
        gwa_values = []
        freshmen_gwas = []
        upper_gwas = []
        for s in students:
            if s['Grade_12_GWA'] is not None:
                gwa_values.append(float(s['Grade_12_GWA']))
                if s['Scholar_Classification'] == 'Freshmen':
                    freshmen_gwas.append(float(s['Grade_12_GWA']))
                else:
                    upper_gwas.append(float(s['Grade_12_GWA']))
                
        avg_gwa = sum(gwa_values) / len(gwa_values) if gwa_values else 0.0
        avg_freshman_gwa = sum(freshmen_gwas) / len(freshmen_gwas) if freshmen_gwas else 0.0
        avg_upper_gwa = sum(upper_gwas) / len(upper_gwas) if upper_gwas else 0.0
        
        stats = {
            'total': total_students,
            'merit': merit_count,
            'fin_aid': fin_aid_count,
            'working_pct': round(working_pct, 1),
            'working_count': working_count,
            'avg_gwa': round(avg_gwa, 2),
            'avg_freshman_gwa': round(avg_freshman_gwa, 2),
            'avg_upper_gwa': round(avg_upper_gwa, 2),
            'merit_scholars': merit_scholars,
            'financial_scholars': financial_scholars,
            'working_scholars': working_scholars,
            'freshmen_scholars': freshmen_scholars,
            'upperclassmen_scholars': upperclassmen_scholars
        }
        
        return render_template('index.html', students=students, stats=stats)
        
    except Exception as e:
        flash(f"Database connection error: {str(e)}", "danger")
        return render_template('index.html', students=[], stats={'total': 0, 'merit': 0, 'fin_aid': 0, 'working_pct': 0.0, 'avg_gwa': 0.0}, db_error=str(e))
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/apply', methods=['GET', 'POST'])
def apply():
    """
    Form to add a new Student, incorporating constraints and business validation rules.
    """
    if session.get('applicant_id'):
        flash("You are already registered in the database. You can manage your profile here.", "warning")
        return redirect(url_for('applicant_view', student_id=session.get('applicant_id')))
    if request.method == 'POST':
        # Extract fields
        student_id = clean_input(request.form.get('Student_ID'))
        scholarship_type = clean_input(request.form.get('Scholarship_Type'))
        scholar_classification = clean_input(request.form.get('Scholar_Classification'))
        name = clean_input(request.form.get('Name'))
        landline = clean_input(request.form.get('Landline'))
        mobile_number = clean_input(request.form.get('Mobile_Number'))
        email_address = clean_input(request.form.get('Email_Address'))
        college_enrolled = clean_input(request.form.get('College_Enrolled'))
        program = clean_input(request.form.get('Program'))
        year_and_section = clean_input(request.form.get('Year_and_Section'))
        address = clean_input(request.form.get('Address'))
        date_of_birth = clean_input(request.form.get('Date_of_Birth'), is_date=True)
        age = clean_input(request.form.get('Age'), is_num=True)
        civil_status = clean_input(request.form.get('Civil_Status'))
        citizenship = clean_input(request.form.get('Citizenship'))
        religion = clean_input(request.form.get('Religion'))
        working_student = 1 if request.form.get('Working_Student') == '1' else 0
        job_title = clean_input(request.form.get('Job_Title'))
        
        # Enforce regular status check
        is_regular = request.form.get('Is_Regular') == '1'
        
        # Sibling limit is checked when adding families, vehicle count is parsed here
        vehicles_count = clean_input(request.form.get('Vehicles_Owned_Count'), is_num=True) or 0
        family_own_vehicle = 1 if vehicles_count >= 1 else 0
        
        # Parse scholar sub classification
        scholar_sub_class = clean_input(request.form.get('Scholar_Sub_Classification'))
        other_scholarship = clean_input(request.form.get('Other_Scholarship'))
        
        # Store scholar_sub_class inside other_scholarship column using prefix brackets [Existing Scholar]
        if scholar_classification == 'Upperclassman' and scholar_sub_class:
            if other_scholarship:
                other_scholarship = f"[{scholar_sub_class}] {other_scholarship}"
            else:
                other_scholarship = f"[{scholar_sub_class}]"
                
        # Parse grades and GWA
        lowest_subject_grade = clean_input(request.form.get('Lowest_Subject_Grade'), is_num=True)
        if scholar_classification == 'Upperclassman':
            lowest_subject_grade = round_to_closest_standard(lowest_subject_grade)
        
        if scholar_classification == 'Freshmen':
            grade_11_gwa = clean_input(request.form.get('Grade_11_GWA'), is_num=True)
            grade_12_gwa = clean_input(request.form.get('Grade_12_GWA'), is_num=True)
        else:
            # For Upperclassmen, we store College GWA in Grade_12_GWA and Lowest Subject Grade in Grade_11_GWA
            grade_12_gwa = round_to_closest_standard(clean_input(request.form.get('College_GWA'), is_num=True))
            grade_11_gwa = lowest_subject_grade
            
        house_ownership = clean_input(request.form.get('House_Ownership'))
        total_annual_income = clean_input(request.form.get('Total_Annual_Household_Income'), is_num=True)
        cor = clean_input(request.form.get('COR'))
        ctc = clean_input(request.form.get('CTC'))
        form137 = clean_input(request.form.get('FORM137'))
        proof_of_income = clean_input(request.form.get('Proof_of_Income'))

        # Server-Side Validations & Business Rules
        errors = []
        if not student_id: errors.append("Student ID is required.")
        if not scholarship_type: errors.append("Scholarship Type is required.")
        if not scholar_classification: errors.append("Scholar Classification is required.")
        if not name: errors.append("Full Name is required.")
        if not email_address: errors.append("Email Address is required.")
        if not date_of_birth: errors.append("Date of Birth is required.")
        if not college_enrolled: errors.append("College Enrolled is required.")
        if not program: errors.append("Academic Program is required.")
        if not year_and_section: errors.append("Year and Section is required.")
        if not address: errors.append("Home Address is required.")
        if not civil_status: errors.append("Civil Status is required.")
        if not citizenship: errors.append("Citizenship is required.")
        if not proof_of_income: errors.append("Proof of Income document name is required.")
        if not house_ownership: errors.append("House Ownership is required.")
        if total_annual_income is None: errors.append("Total Annual Household Income is required.")

        # Business Rule: Only regular students can apply
        if not is_regular:
            errors.append("Application denied: Only regular students (no failing, dropped, or incomplete grades) can apply.")

        # Age Constraint Check
        if age is not None and (age < 16 or age > 99):
            errors.append("Age must be between 16 and 99.")
            
        # Income Constraint Check
        if total_annual_income is not None and (total_annual_income < 0.00 or total_annual_income > 1000000.00):
            errors.append("Total Annual Household Income must be between 0.00 and 1,000,000.00.")

        # Business Rule: Financial Aid Specifics
        if scholarship_type == 'Financial Aid':
            if total_annual_income is not None and total_annual_income > 200000.00:
                errors.append("Application denied: Total Annual Household Income must not exceed PHP 200,000 for Financial Aid.")
            if vehicles_count > 1:
                errors.append("Application denied: Vehicle ownership is limited to a maximum of one (1) primary vehicle to qualify for Financial Aid.")

        # Business Rule: Merit Specifics
        if scholarship_type == 'Merit':
            if scholar_classification == 'Freshmen':
                if grade_12_gwa is not None and grade_12_gwa < 90.0:
                    errors.append("Application denied: Minimum General Average of 90 is required for Freshman Merit scholarship.")
                if lowest_subject_grade is not None and lowest_subject_grade < 85.0:
                    errors.append("Application denied: Minimum Subject Grade of 85 is required for Freshman Merit scholarship.")
            elif scholar_classification == 'Upperclassman':
                # In college grading scale, smaller is better (1.0 = Excellent, 3.0 = Passing, 5.0 = Failed)
                if grade_12_gwa is not None and grade_12_gwa > 2.0:
                    errors.append("Application denied: Minimum General Average of 2.0 (i.e., between 1.0 and 2.0) is required for Upperclassman Merit.")
                if lowest_subject_grade is not None and lowest_subject_grade > 2.0:
                    errors.append("Application denied: Minimum Subject Grade of 2.0 (i.e., between 1.0 and 2.0) is required for Upperclassman Merit.")

        # DDL Database Check Constraints compliance
        if scholar_classification == 'Freshmen':
            if grade_11_gwa is None or grade_12_gwa is None or not form137:
                errors.append("For Freshmen, Grade 11 GWA, Grade 12 GWA, and FORM137 are required.")
        elif scholar_classification == 'Upperclassman':
            if not cor or not ctc:
                errors.append("For Upperclassman, COR (Certificate of Registration) and CTC (Certified True Copy) are required.")

        if errors:
            for err in errors:
                flash(err, "warning")
            return render_template('add_scholar.html', form_data=request.form)

        # Execute insertion
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            query = """
                INSERT INTO Student (
                    Student_ID, Scholarship_Type, Scholar_Classification, Name, Landline, Mobile_Number,
                    Email_Address, College_Enrolled, Program, Year_and_Section, Address, Date_of_Birth,
                    Age, Civil_Status, Citizenship, Religion, Working_Student, Job_Title, Other_Scholarship,
                    Grade_11_GWA, Grade_12_GWA, House_Ownership, Total_Annual_Household_Income,
                    Family_own_a_vehicle, COR, CTC, FORM137, Proof_of_Income
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            params = (
                student_id, scholarship_type, scholar_classification, name, landline, mobile_number,
                email_address, college_enrolled, program, year_and_section, address, date_of_birth,
                age, civil_status, citizenship, religion, working_student, job_title, other_scholarship,
                grade_11_gwa, grade_12_gwa, house_ownership, total_annual_income,
                family_own_vehicle, cor, ctc, form137, proof_of_income
            )
            
            cursor.execute(query, params)
            conn.commit()
            
            session['applicant_id'] = student_id
            flash(f"Scholar applicant `{name}` (ID: {student_id}) successfully registered! You can now add family, school, and extracurricular details below.", "success")
            return redirect(url_for('applicant_view', student_id=student_id))
            
        except pymysql.Error as err:
            errno = err.args[0] if len(err.args) > 0 else None
            errmsg = err.args[1] if len(err.args) > 1 else str(err)
            if errno == 1062:
                if "PRIMARY" in errmsg or "Student_ID" in errmsg:
                    flash(f"Student ID `{student_id}` is already registered.", "danger")
                else:
                    flash("An applicant with this Email Address is already registered.", "danger")
            else:
                flash(f"Database error: {errmsg}", "danger")
            return render_template('add_scholar.html', form_data=request.form)
        except Exception as e:
            flash(f"System error: {str(e)}", "danger")
            return render_template('add_scholar.html', form_data=request.form)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
                
    return render_template('add_scholar.html')

@app.route('/admin/edit/<string:id>', methods=['GET', 'POST'])
@user_or_admin_required
def admin_edit(id):
    """
    Edit view for an existing scholar student, parsing custom columns.
    """
    conn = None
    cursor = None
    student = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM Student WHERE Student_ID = %s", (id,))
        student = cursor.fetchone()
        
        if not student:
            flash("Student record not found.", "warning")
            return redirect(url_for('index'))
            
        # Parse sub-classification from Other_Scholarship
        sub_class = ""
        other_scholar_cleaned = student['Other_Scholarship']
        if other_scholar_cleaned:
            if other_scholar_cleaned.startswith('[Existing Scholar]'):
                sub_class = 'Existing Scholar'
                other_scholar_cleaned = other_scholar_cleaned.replace('[Existing Scholar]', '').strip()
            elif other_scholar_cleaned.startswith('[Prospective Scholar]'):
                sub_class = 'Prospective Scholar'
                other_scholar_cleaned = other_scholar_cleaned.replace('[Prospective Scholar]', '').strip()
                
        # Inject parsed items into student dict to pass to form
        student['Scholar_Sub_Classification'] = sub_class
        student['Other_Scholarship_Cleaned'] = other_scholar_cleaned
        
        # Inject Lowest Subject Grade
        if student['Scholar_Classification'] == 'Upperclassman':
            student['Lowest_Subject_Grade'] = student['Grade_11_GWA']
            student['College_GWA'] = student['Grade_12_GWA']
            
    except Exception as e:
        flash(f"Database error fetching student: {str(e)}", "danger")
        return redirect(url_for('index'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    if request.method == 'POST':
        # Extract parameters
        scholarship_type = clean_input(request.form.get('Scholarship_Type'))
        scholar_classification = clean_input(request.form.get('Scholar_Classification'))
        name = clean_input(request.form.get('Name'))
        landline = clean_input(request.form.get('Landline'))
        mobile_number = clean_input(request.form.get('Mobile_Number'))
        email_address = clean_input(request.form.get('Email_Address'))
        college_enrolled = clean_input(request.form.get('College_Enrolled'))
        program = clean_input(request.form.get('Program'))
        year_and_section = clean_input(request.form.get('Year_and_Section'))
        address = clean_input(request.form.get('Address'))
        date_of_birth = clean_input(request.form.get('Date_of_Birth'), is_date=True)
        age = clean_input(request.form.get('Age'), is_num=True)
        civil_status = clean_input(request.form.get('Civil_Status'))
        citizenship = clean_input(request.form.get('Citizenship'))
        religion = clean_input(request.form.get('Religion'))
        working_student = 1 if request.form.get('Working_Student') == '1' else 0
        job_title = clean_input(request.form.get('Job_Title'))
        
        is_regular = request.form.get('Is_Regular') == '1'
        vehicles_count = clean_input(request.form.get('Vehicles_Owned_Count'), is_num=True) or 0
        family_own_vehicle = 1 if vehicles_count >= 1 else 0
        
        # Parse sub-classification
        scholar_sub_class = clean_input(request.form.get('Scholar_Sub_Classification'))
        other_scholarship = clean_input(request.form.get('Other_Scholarship'))
        if scholar_classification == 'Upperclassman' and scholar_sub_class:
            if other_scholarship:
                other_scholarship = f"[{scholar_sub_class}] {other_scholarship}"
            else:
                other_scholarship = f"[{scholar_sub_class}]"
                
        lowest_subject_grade = clean_input(request.form.get('Lowest_Subject_Grade'), is_num=True)
        if scholar_classification == 'Upperclassman':
            lowest_subject_grade = round_to_closest_standard(lowest_subject_grade)
        
        if scholar_classification == 'Freshmen':
            grade_11_gwa = clean_input(request.form.get('Grade_11_GWA'), is_num=True)
            grade_12_gwa = clean_input(request.form.get('Grade_12_GWA'), is_num=True)
        else:
            grade_12_gwa = round_to_closest_standard(clean_input(request.form.get('College_GWA'), is_num=True))
            grade_11_gwa = lowest_subject_grade
            
        house_ownership = clean_input(request.form.get('House_Ownership'))
        total_annual_income = clean_input(request.form.get('Total_Annual_Household_Income'), is_num=True)
        cor = clean_input(request.form.get('COR'))
        ctc = clean_input(request.form.get('CTC'))
        form137 = clean_input(request.form.get('FORM137'))
        proof_of_income = clean_input(request.form.get('Proof_of_Income'))

        # Validations
        errors = []
        if not scholarship_type: errors.append("Scholarship Type is required.")
        if not scholar_classification: errors.append("Scholar Classification is required.")
        if not name: errors.append("Full Name is required.")
        if not email_address: errors.append("Email Address is required.")
        if not date_of_birth: errors.append("Date of Birth is required.")
        if not college_enrolled: errors.append("College Enrolled is required.")
        if not program: errors.append("Academic Program is required.")
        if not year_and_section: errors.append("Year and Section is required.")
        if not address: errors.append("Home Address is required.")
        if not civil_status: errors.append("Civil Status is required.")
        if not citizenship: errors.append("Citizenship is required.")
        if not proof_of_income: errors.append("Proof of Income document name is required.")
        if not house_ownership: errors.append("House Ownership is required.")
        if total_annual_income is None: errors.append("Total Annual Household Income is required.")

        # Business Rule Check
        if not is_regular:
            errors.append("Application denied: Only regular students (no failing, dropped, or incomplete grades) can apply.")
        if age is not None and (age < 16 or age > 99):
            errors.append("Age must be between 16 and 99.")
        if total_annual_income is not None and (total_annual_income < 0.00 or total_annual_income > 1000000.00):
            errors.append("Total Annual Household Income must be between 0.00 and 1,000,000.00.")

        # Financial Aid
        if scholarship_type == 'Financial Aid':
            if total_annual_income is not None and total_annual_income > 200000.00:
                errors.append("Application denied: Total Annual Household Income must not exceed PHP 200,000 for Financial Aid.")
            if vehicles_count > 1:
                errors.append("Application denied: Vehicle ownership is limited to a maximum of one (1) primary vehicle to qualify for Financial Aid.")

        # Merit
        if scholarship_type == 'Merit':
            if scholar_classification == 'Freshmen':
                if grade_12_gwa is not None and grade_12_gwa < 90.0:
                    errors.append("Application denied: Minimum General Average of 90 is required for Freshman Merit scholarship.")
                if lowest_subject_grade is not None and lowest_subject_grade < 85.0:
                    errors.append("Application denied: Minimum Subject Grade of 85 is required for Freshman Merit scholarship.")
            elif scholar_classification == 'Upperclassman':
                if grade_12_gwa is not None and grade_12_gwa > 2.0:
                    errors.append("Application denied: Minimum General Average of 2.0 (between 1.0 and 2.0) is required for Upperclassman Merit.")
                if lowest_subject_grade is not None and lowest_subject_grade > 2.0:
                    errors.append("Application denied: Minimum Subject Grade of 2.0 (between 1.0 and 2.0) is required for Upperclassman Merit.")

        if scholar_classification == 'Freshmen':
            if grade_11_gwa is None or grade_12_gwa is None or not form137:
                errors.append("For Freshmen, Grade 11 GWA, Grade 12 GWA, and FORM137 are required.")
            cor, ctc = None, None
        elif scholar_classification == 'Upperclassman':
            if not cor or not ctc:
                errors.append("For Upperclassman, COR and CTC are required.")
            form137 = None

        if errors:
            for err in errors:
                flash(err, "warning")
            form_dict = dict(request.form)
            form_dict['Student_ID'] = id
            return render_template('edit_scholar.html', student=form_dict)

        # Update Database
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            query = """
                UPDATE Student SET
                    Scholarship_Type = %s, Scholar_Classification = %s, Name = %s, Landline = %s, Mobile_Number = %s,
                    Email_Address = %s, College_Enrolled = %s, Program = %s, Year_and_Section = %s, Address = %s,
                    Date_of_Birth = %s, Age = %s, Civil_Status = %s, Citizenship = %s, Religion = %s,
                    Working_Student = %s, Job_Title = %s, Other_Scholarship = %s, Grade_11_GWA = %s, Grade_12_GWA = %s,
                    House_Ownership = %s, Total_Annual_Household_Income = %s, Family_own_a_vehicle = %s, COR = %s,
                    CTC = %s, FORM137 = %s, Proof_of_Income = %s
                WHERE Student_ID = %s
            """
            
            params = (
                scholarship_type, scholar_classification, name, landline, mobile_number,
                email_address, college_enrolled, program, year_and_section, address, date_of_birth,
                age, civil_status, citizenship, religion, working_student, job_title, other_scholarship,
                grade_11_gwa, grade_12_gwa, house_ownership, total_annual_income,
                family_own_vehicle, cor, ctc, form137, proof_of_income, id
            )
            
            cursor.execute(query, params)
            conn.commit()
            
            flash(f"Scholar `{name}` (ID: {id}) successfully updated!", "success")
            if session.get('is_admin'):
                return redirect(url_for('index'))
            return redirect(url_for('applicant_view', student_id=id))
            
        except pymysql.Error as err:
            errno = err.args[0] if len(err.args) > 0 else None
            errmsg = err.args[1] if len(err.args) > 1 else str(err)
            if errno == 1062:
                flash("An applicant with this Email Address is already registered.", "danger")
            else:
                flash(f"Database error: {errmsg}", "danger")
            form_dict = dict(request.form)
            form_dict['Student_ID'] = id
            return render_template('edit_scholar.html', student=form_dict)
        except Exception as e:
            flash(f"System error: {str(e)}", "danger")
            form_dict = dict(request.form)
            form_dict['Student_ID'] = id
            return render_template('edit_scholar.html', student=form_dict)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template('edit_scholar.html', student=student)

@app.route('/admin/view/<string:id>')
@admin_required
def admin_view(id):
    """
    Renders the dossier (detailed review) profile for a candidate, 
    joining Student details with Family, School, and Extra-curricular activities.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 1. Fetch Student profile
        cursor.execute("SELECT * FROM Student WHERE Student_ID = %s", (id,))
        student = cursor.fetchone()
        
        if not student:
            flash("Student record not found.", "warning")
            return redirect(url_for('index'))
            
        # Parse sub-classification and cleaned other scholarship
        sub_class = ""
        other_scholar_cleaned = student['Other_Scholarship']
        if other_scholar_cleaned:
            if other_scholar_cleaned.startswith('[Existing Scholar]'):
                sub_class = 'Existing Scholar'
                other_scholar_cleaned = other_scholar_cleaned.replace('[Existing Scholar]', '').strip()
            elif other_scholar_cleaned.startswith('[Prospective Scholar]'):
                sub_class = 'Prospective Scholar'
                other_scholar_cleaned = other_scholar_cleaned.replace('[Prospective Scholar]', '').strip()
                
        student['Scholar_Sub_Classification'] = sub_class
        student['Other_Scholarship_Cleaned'] = other_scholar_cleaned
        
        if student['Scholar_Classification'] == 'Upperclassman':
            student['Lowest_Subject_Grade'] = student['Grade_11_GWA']
            student['College_GWA'] = student['Grade_12_GWA']
            
        # 2. Fetch Family members
        cursor.execute("SELECT * FROM Family WHERE Student_ID = %s ORDER BY Family_ID ASC", (id,))
        family = cursor.fetchall()
        
        # 3. Fetch Educational History
        cursor.execute("SELECT * FROM School WHERE Student_ID = %s ORDER BY School_From ASC", (id,))
        schools = cursor.fetchall()
        
        # 4. Fetch Extra-curricular history
        cursor.execute("SELECT * FROM Extra_Curricular WHERE Student_ID = %s ORDER BY Extra_Curricular_Year ASC", (id,))
        extracurs = cursor.fetchall()
        
        return render_template(
            'view_scholar.html', 
            student=student, 
            family=family, 
            schools=schools, 
            extracurs=extracurs
        )
        
    except Exception as e:
        flash(f"Database error loading dossier: {str(e)}", "danger")
        return redirect(url_for('index'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

@app.route('/admin/delete/<string:id>', methods=['POST'])
@admin_required
def admin_delete(id):
    """
    Removes a student from the database. Child tables (Family, School, Extra-Curricular) 
    are automatically deleted by the ON DELETE CASCADE constraint.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Student WHERE Student_ID = %s", (id,))
        conn.commit()
        flash(f"Student ID `{id}` successfully deleted from database.", "success")
    except Exception as e:
        flash(f"Database error deleting record: {str(e)}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    return redirect(url_for('index'))

# --- Relation Table Helpers ---

@app.route('/view/<string:student_id>/add_family', methods=['POST'])
@user_or_admin_required
def add_family(student_id):
    """
    Inserts a family member linked to the student with sibling and working relative limits.
    """
    role = clean_input(request.form.get('Member_Role'))
    name = clean_input(request.form.get('Member_Name'))
    age = clean_input(request.form.get('Member_Age'), is_num=True)
    mobile = clean_input(request.form.get('Member_Mobile_Number'))
    civil_status = clean_input(request.form.get('Member_Civil_Status'))
    employed = 1 if request.form.get('Member_Employed') == '1' else 0
    occupation = clean_input(request.form.get('Member_Course_or_Occupation'))
    employer = clean_input(request.form.get('Member_School_or_Employer'))
    department = clean_input(request.form.get('Member_Department'))
    position = clean_input(request.form.get('Member_Position'))
    own_business = 1 if request.form.get('Member_With_Own_Business') == '1' else 0
    biz_address = clean_input(request.form.get('Member_Office_or_Business_Name_Address'))
    monthly_income = clean_input(request.form.get('Member_Monthly_Income'), is_num=True) or 0.00

    if not role or not name:
        flash("Member Role and Name are required.", "warning")
        return redirect_to_dossier(student_id)

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Enforce Business Rule: Siblings of applicant are limited to a max of 3
        if role == 'Sibling':
            cursor.execute("SELECT COUNT(*) FROM Family WHERE Student_ID = %s AND Member_Role = 'Sibling'", (student_id,))
            sibling_count = cursor.fetchone()[0]
            if sibling_count >= 3:
                flash("Family threshold limit exceeded: A maximum of three (3) siblings are allowed.", "warning")
                return redirect_to_dossier(student_id)
                
        # Enforce Business Rule: Institution employed relatives are limited to a max of 2
        if role == 'Relative' and employed == 1:
            cursor.execute("SELECT COUNT(*) FROM Family WHERE Student_ID = %s AND Member_Role = 'Relative' AND Member_Employed = 1", (student_id,))
            relative_count = cursor.fetchone()[0]
            if relative_count >= 2:
                flash("Family threshold limit exceeded: Relatives working in the institution are limited to a maximum of two (2) entries.", "warning")
                return redirect_to_dossier(student_id)
        
        query = """
            INSERT INTO Family (
                Student_ID, Member_Role, Member_Name, Member_Age, Member_Mobile_Number, Member_Civil_Status,
                Member_Employed, Member_Course_or_Occupation, Member_School_or_Employer, Member_Department,
                Member_Position, Member_With_Own_Business, Member_Office_or_Business_Name_Address, Member_Monthly_Income
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            student_id, role, name, age, mobile, civil_status,
            employed, occupation, employer, department,
            position, own_business, biz_address, monthly_income
        )
        cursor.execute(query, params)
        conn.commit()
        flash(f"Family member `{name}` added successfully.", "success")
    except Exception as e:
        flash(f"Failed to add family member: {str(e)}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return redirect_to_dossier(student_id)

@app.route('/view/<string:student_id>/add_school', methods=['POST'])
@user_or_admin_required
def add_school(student_id):
    """
    Inserts a historical education level record linked to the student.
    """
    level = clean_input(request.form.get('History_Education_Level'))
    name = clean_input(request.form.get('School_Name'))
    address = clean_input(request.form.get('School_Address'))
    from_year = clean_input(request.form.get('School_From'), is_num=True)
    to_year = clean_input(request.form.get('School_To'), is_num=True)
    honors = clean_input(request.form.get('School_Honors'))

    if not level or not name or not address:
        flash("Education Level, School Name, and Address are required.", "warning")
        return redirect_to_dossier(student_id)

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO School (
                History_Education_Level, Student_ID, School_Name, School_Address, School_From, School_To, School_Honors
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (level, student_id, name, address, from_year, to_year, honors))
        conn.commit()
        flash("Educational history record added successfully.", "success")
    except Exception as e:
        flash(f"Failed to add education record: {str(e)}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return redirect_to_dossier(student_id)

@app.route('/view/<string:student_id>/add_extracur', methods=['POST'])
@user_or_admin_required
def add_extracur(student_id):
    """
    Inserts an extra-curricular activity record linked to the student.
    """
    year = clean_input(request.form.get('Extra_Curricular_Year'))
    name = clean_input(request.form.get('Extra_Curricular_Name'))
    position = clean_input(request.form.get('Extra_Curricular_Position'))

    if not name:
        flash("Activity Name is required.", "warning")
        return redirect_to_dossier(student_id)

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO Extra_Curricular (
                Student_ID, Extra_Curricular_Year, Extra_Curricular_Name, Extra_Curricular_Position
            ) VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (student_id, year, name, position))
        conn.commit()
        flash("Extra-curricular activity record added.", "success")
    except Exception as e:
        flash(f"Failed to add activity: {str(e)}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return redirect_to_dossier(student_id)

@app.route('/delete_relation/<string:student_id>/<string:relation>/<int:id>', methods=['POST'])
@user_or_admin_required
def delete_relation(student_id, relation, id):
    """
    Utility route to delete an item from child tables (Family, School, Extra_Curricular).
    """
    table_map = {
        'family': ('Family', 'Family_ID'),
        'school': ('School', 'School_ID'),
        'extracur': ('Extra_Curricular', 'Extra_Curricular_ID')
    }
    
    if relation not in table_map:
        flash("Invalid relation parameter.", "danger")
        return redirect_to_dossier(student_id)
        
    table_name, col_name = table_map[relation]
    
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM `{table_name}` WHERE `{col_name}` = %s AND `Student_ID` = %s", (id, student_id))
        conn.commit()
        flash(f"Record deleted from {relation}.", "success")
    except Exception as e:
        flash(f"Failed to delete record: {str(e)}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return redirect_to_dossier(student_id)

@app.route('/view/<string:student_id>/edit_family/<int:id>', methods=['POST'])
@user_or_admin_required
def edit_family(student_id, id):
    """
    Updates a family member linked to the student with sibling and working relative limits.
    """
    role = clean_input(request.form.get('Member_Role'))
    name = clean_input(request.form.get('Member_Name'))
    age = clean_input(request.form.get('Member_Age'), is_num=True)
    mobile = clean_input(request.form.get('Member_Mobile_Number'))
    civil_status = clean_input(request.form.get('Member_Civil_Status'))
    employed = 1 if request.form.get('Member_Employed') == '1' else 0
    occupation = clean_input(request.form.get('Member_Course_or_Occupation'))
    employer = clean_input(request.form.get('Member_School_or_Employer'))
    department = clean_input(request.form.get('Member_Department'))
    position = clean_input(request.form.get('Member_Position'))
    own_business = 1 if request.form.get('Member_With_Own_Business') == '1' else 0
    biz_address = clean_input(request.form.get('Member_Office_or_Business_Name_Address'))
    monthly_income = clean_input(request.form.get('Member_Monthly_Income'), is_num=True) or 0.00

    if not role or not name:
        flash("Member Role and Name are required.", "warning")
        return redirect_to_dossier(student_id)

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Enforce Business Rule: Siblings of applicant are limited to a max of 3
        if role == 'Sibling':
            cursor.execute("SELECT COUNT(*) FROM Family WHERE Student_ID = %s AND Member_Role = 'Sibling' AND Family_ID != %s", (student_id, id))
            sibling_count = cursor.fetchone()[0]
            if sibling_count >= 3:
                flash("Family threshold limit exceeded: A maximum of three (3) siblings are allowed.", "warning")
                return redirect_to_dossier(student_id)
                
        # Enforce Business Rule: Institution employed relatives are limited to a max of 2
        if role == 'Relative' and employed == 1:
            cursor.execute("SELECT COUNT(*) FROM Family WHERE Student_ID = %s AND Member_Role = 'Relative' AND Member_Employed = 1 AND Family_ID != %s", (student_id, id))
            relative_count = cursor.fetchone()[0]
            if relative_count >= 2:
                flash("Family threshold limit exceeded: Relatives working in the institution are limited to a maximum of two (2) entries.", "warning")
                return redirect_to_dossier(student_id)
        
        query = """
            UPDATE Family SET
                Member_Role = %s, Member_Name = %s, Member_Age = %s, Member_Mobile_Number = %s, Member_Civil_Status = %s,
                Member_Employed = %s, Member_Course_or_Occupation = %s, Member_School_or_Employer = %s, Member_Department = %s,
                Member_Position = %s, Member_With_Own_Business = %s, Member_Office_or_Business_Name_Address = %s, Member_Monthly_Income = %s
            WHERE Family_ID = %s AND Student_ID = %s
        """
        params = (
            role, name, age, mobile, civil_status,
            employed, occupation, employer, department,
            position, own_business, biz_address, monthly_income,
            id, student_id
        )
        cursor.execute(query, params)
        conn.commit()
        flash(f"Family member `{name}` updated successfully.", "success")
    except Exception as e:
        flash(f"Failed to update family member: {str(e)}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return redirect_to_dossier(student_id)

@app.route('/view/<string:student_id>/edit_school/<int:id>', methods=['POST'])
@user_or_admin_required
def edit_school(student_id, id):
    """
    Updates a historical education level record linked to the student.
    """
    level = clean_input(request.form.get('History_Education_Level'))
    name = clean_input(request.form.get('School_Name'))
    address = clean_input(request.form.get('School_Address'))
    from_year = clean_input(request.form.get('School_From'), is_num=True)
    to_year = clean_input(request.form.get('School_To'), is_num=True)
    honors = clean_input(request.form.get('School_Honors'))

    if not level or not name or not address:
        flash("Education Level, School Name, and Address are required.", "warning")
        return redirect_to_dossier(student_id)

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            UPDATE School SET
                History_Education_Level = %s, School_Name = %s, School_Address = %s, School_From = %s, School_To = %s, School_Honors = %s
            WHERE School_ID = %s AND Student_ID = %s
        """
        cursor.execute(query, (level, name, address, from_year, to_year, honors, id, student_id))
        conn.commit()
        flash("Educational history record updated successfully.", "success")
    except Exception as e:
        flash(f"Failed to update education record: {str(e)}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return redirect_to_dossier(student_id)

@app.route('/view/<string:student_id>/edit_extracur/<int:id>', methods=['POST'])
@user_or_admin_required
def edit_extracur(student_id, id):
    """
    Updates an extra-curricular activity record linked to the student.
    """
    year = clean_input(request.form.get('Extra_Curricular_Year'))
    name = clean_input(request.form.get('Extra_Curricular_Name'))
    position = clean_input(request.form.get('Extra_Curricular_Position'))

    if not name:
        flash("Activity Name is required.", "warning")
        return redirect_to_dossier(student_id)

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            UPDATE Extra_Curricular SET
                Extra_Curricular_Year = %s, Extra_Curricular_Name = %s, Extra_Curricular_Position = %s
            WHERE Extra_Curricular_ID = %s AND Student_ID = %s
        """
        cursor.execute(query, (year, name, position, id, student_id))
        conn.commit()
        flash("Extra-curricular activity record updated.", "success")
    except Exception as e:
        flash(f"Failed to update activity: {str(e)}", "danger")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            
    return redirect_to_dossier(student_id)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
